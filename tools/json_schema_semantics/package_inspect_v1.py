"""Semantic checks for package-inspect-v1.schema.json."""

import re

from package_target_contracts import PACKAGE_DEBUG_ARTIFACT_COUNT
from package_target_contracts import PACKAGE_TARGET_MIN_ARTIFACT_COUNTS
from package_target_contracts import PACKAGE_TARGETS_REQUIRING_NATIVE_STATUS

from .common import (
    add_equal_error,
    add_length_count_error,
    validate_normalized_package_path,
    validate_package_summary_minimums,
    validate_source_location_span,
)


EXPECTED_ROOT_FILES = {
    "manifest": "manifest.json",
    "reflection": "reflection.json",
    "diagnostics": "diagnostics.json",
}

LOWERCASE_SHA256 = re.compile(r"^[0-9a-f]{64}$")
WINDOWS_DRIVE_PATH = re.compile(r"^[A-Za-z]:")

NATIVE_ARTIFACT_DESCRIPTOR_CHECKS = (
    "descriptorIdentityMatchesContract",
    "targetMatchesPackage",
    "nativeBinaryStatusMatchesPackage",
    "sourcePathMatchesManifest",
    "sourceHashMatchesFile",
    "artifactPathMatchesManifest",
    "artifactHashMatchesFile",
    "sizeBytesMatchesFile",
    "validationStatusMatchesNativeStatus",
)

NATIVE_ARTIFACT_DESCRIPTOR_CONTENT_FIELDS = (
    "schemaVersion",
    "kind",
    "contractVersion",
    "target",
    "binaryKind",
    "sourcePath",
    "sourceHash",
    "artifactPath",
    "artifactHash",
    "sizeBytes",
    "optimizationLevel",
    "optimizationEvidence",
    "validationStatus",
    "nativeBinaryStatus",
)

SOURCE_REMAP_PROVENANCE_CHECKS = (
    "identityMatchesContract",
    "targetMatchesPackage",
    "generatedFilePresent",
    "mappingCountPositive",
    "sourcePathPresent",
    "sourceHashPresent",
    "sourceSizeBytesPresent",
)

SOURCE_REMAP_PROVENANCE_CONTENT_FIELDS = (
    "schemaVersion",
    "kind",
    "contractVersion",
    "target",
    "generatedFile",
    "mappingGranularity",
    "mappingCount",
    "sourcePath",
    "sourceSha256",
    "sourceSizeBytes",
)

OPTIMIZED_VULKAN_EVIDENCE = {
    "requestedLevel": "O2",
    "effectiveLevel": "O2",
    "status": "applied",
    "tool": "spirv-opt",
}

TARGET_LEGALIZATION_TOOL_FIELDS = (
    "requiredToolCount",
    "missingToolCount",
    "requiredToolIds",
    "missingToolIds",
    "optionalNativeToolMissing",
    "optionalNativeToolStatus",
    "toolRequirementEvidenceIds",
)

REFLECTION_V1_REQUIRED_FIELDS = frozenset(
    {
        "schemaVersion",
        "module",
        "target",
        "nativeBinary",
        "entryPoints",
        "structs",
        "resources",
        "targetResourceBindings",
        "pushConstants",
        "functionConstants",
        "vertexLayouts",
        "workgroupSizes",
        "manualTextureCompareKernelSummary",
        "manualTextureCompareKernels",
        "targetFeatures",
    }
)


def records_by_name(errors, path, records, label):
    by_name = {}
    for index, record in enumerate(records):
        name = record["name"]
        if name in by_name:
            errors.append(f"{path}: duplicate {label} record {name!r}")
        else:
            by_name[name] = record
        if "location" in record:
            validate_source_location_span(
                errors,
                f"{path}[{index}].location",
                record["location"],
            )
    return by_name


def validate_record_sha256(errors, path, record):
    digest = record.get("sha256")
    if digest is None:
        if record.get("exists") is True:
            errors.append(f"{path}.sha256: expected digest when file exists")
        return
    elif not isinstance(digest, str) or LOWERCASE_SHA256.fullmatch(digest) is None:
        errors.append(f"{path}.sha256: expected lowercase SHA-256 digest or null")
    if record.get("exists") is False:
        errors.append(f"{path}.sha256: expected null when file does not exist")


def validate_record_size(errors, path, record):
    size = record.get("sizeBytes")
    if record.get("exists") is True and size is None:
        errors.append(f"{path}.sizeBytes: expected size when file exists")
    if record.get("exists") is False and size is not None:
        errors.append(f"{path}.sizeBytes: expected null when file does not exist")


def validate_record_file_state(errors, path, record):
    validate_record_size(errors, path, record)
    validate_record_sha256(errors, path, record)


def is_package_relative_artifact_path(value):
    if value == "":
        return False
    if "\\" in value:
        return False
    if value.startswith("/") or WINDOWS_DRIVE_PATH.match(value):
        return False
    if ".." in value.split("/"):
        return False
    return True


def validate_artifact_path_identity(errors, path, record):
    expected_package_relative = is_package_relative_artifact_path(record["path"])
    add_equal_error(
        errors,
        f"{path}.packageRelative",
        record["packageRelative"],
        expected_package_relative,
        "artifact path package-relative flag",
    )
    if not expected_package_relative and record["exists"] is True:
        errors.append(
            f"{path}.exists: expected false when artifact path is not package-relative"
        )


def validate_root_files(errors, root_files):
    by_name = records_by_name(errors, "$.rootFiles", root_files, "root file")
    names = sorted(by_name)
    expected_names = sorted(EXPECTED_ROOT_FILES)
    if names != expected_names:
        errors.append(
            f"$.rootFiles: expected root file records {expected_names!r}, got {names!r}"
        )
    for name, expected_path in EXPECTED_ROOT_FILES.items():
        record = by_name.get(name)
        if record is not None:
            add_equal_error(
                errors,
                f"$.rootFiles.{name}.path",
                record["path"],
                expected_path,
                "package root path",
            )
            add_equal_error(
                errors,
                f"$.rootFiles.{name}.provenance",
                record["provenance"],
                {
                    "kind": "packageRootFile",
                    "source": "packageRoot",
                },
                "root file provenance",
            )
            validate_record_file_state(errors, f"$.rootFiles.{name}", record)


def validate_artifacts(errors, summary, artifacts, manifest):
    by_name = records_by_name(errors, "$.artifacts", artifacts, "artifact")
    names = set(by_name)
    if "nativeBinaryStatus" in names:
        errors.append("$.artifacts: nativeBinaryStatus is metadata, not an artifact")

    for name, record in by_name.items():
        validate_artifact_path_identity(errors, f"$.artifacts.{name}", record)

    add_length_count_error(
        errors,
        "$.summary.artifactCount",
        summary["artifactCount"],
        artifacts,
        "artifacts length",
    )
    add_equal_error(
        errors,
        "$.summary.debugArtifactsPresent",
        summary["debugArtifactsPresent"],
        {"debugMetadata", "hirSourceMap"}.issubset(names),
        "debug artifact record presence",
    )

    manifest_artifacts = manifest.get("artifacts")
    if not isinstance(manifest_artifacts, dict):
        return

    manifest_artifact_names = {
        name for name in manifest_artifacts if name != "nativeBinaryStatus"
    }
    if names != manifest_artifact_names:
        errors.append(
            "$.artifacts: expected artifact records "
            f"{sorted(manifest_artifact_names)!r}, got {sorted(names)!r}"
        )

    for name, expected_path in manifest_artifacts.items():
        if name == "nativeBinaryStatus":
            continue
        record = by_name.get(name)
        if record is not None:
            add_equal_error(
                errors,
                f"$.artifacts.{name}.path",
                record["path"],
                expected_path,
                "manifest artifact path",
            )
            add_equal_error(
                errors,
                f"$.artifacts.{name}.provenance.kind",
                record["provenance"]["kind"],
                "manifestArtifact",
                "artifact provenance kind",
            )
            add_equal_error(
                errors,
                f"$.artifacts.{name}.provenance.source",
                record["provenance"]["source"],
                "manifest.artifacts",
                "artifact provenance source",
            )
            add_equal_error(
                errors,
                f"$.artifacts.{name}.provenance.manifestKey",
                record["provenance"]["manifestKey"],
                name,
                "artifact provenance manifest key",
            )
            validate_record_file_state(errors, f"$.artifacts.{name}", record)


def embedded_reflection_error_path(error):
    if error == "$":
        return "$.reflection"
    if error.startswith("$."):
        return f"$.reflection{error[1:]}"
    return f"$.reflection: {error}"


def validate_embedded_reflection_semantics(errors, reflection):
    if not REFLECTION_V1_REQUIRED_FIELDS.issubset(reflection):
        return

    from . import reflection_v1

    for error in reflection_v1.validate_semantics(reflection):
        errors.append(embedded_reflection_error_path(error))


def fixed_array_element_count(dimensions):
    if not dimensions:
        return None

    product = 1
    for dimension in dimensions:
        if dimension.get("kind") != "fixed" or "elementCount" not in dimension:
            return None
        product *= dimension["elementCount"]
    return product


def validate_descriptor_array_binding_metadata(errors, reflection):
    resources = reflection.get("resources")
    bindings = reflection.get("targetResourceBindings")
    if not isinstance(resources, list) or not isinstance(bindings, list):
        return

    resource_map = {}
    for resource in resources:
        key = (resource.get("stage"), resource.get("name"), resource.get("kind"))
        resource_map.setdefault(key, resource)

    for index, binding in enumerate(bindings):
        key = (binding.get("stage"), binding.get("name"), binding.get("kind"))
        resource = resource_map.get(key)
        if resource is None:
            continue

        fixed_product = fixed_array_element_count(resource.get("arrayDimensions", []))
        if fixed_product is None:
            continue

        binding_path = f"$.reflection.targetResourceBindings[{index}]"
        if "arrayElementCount" not in binding:
            errors.append(
                f"{binding_path}.arrayElementCount: required for fixed descriptor "
                "array binding"
            )


def validate_manifest_summary(errors, summary, manifest, reflection):
    if "module" in manifest:
        add_equal_error(
            errors,
            "$.summary.module",
            summary["module"],
            manifest["module"],
            "manifest module",
        )
    if "target" in manifest:
        add_equal_error(
            errors,
            "$.summary.target",
            summary["target"],
            manifest["target"],
            "manifest target",
        )
    manifest_artifacts = manifest.get("artifacts")
    if isinstance(manifest_artifacts, dict):
        manifest_status = manifest_artifacts.get("nativeBinaryStatus")
        requires_native_status = package_requires_native_binary_status(
            manifest,
            summary,
        )
        if manifest_status is not None and not requires_native_status:
            errors.append(
                "$.manifest.artifacts.nativeBinaryStatus: "
                f"{summary['target']} packages must not declare nativeBinaryStatus"
            )
        elif manifest_status is not None and "nativeBinary" not in manifest_artifacts:
            errors.append(
                "$.manifest.artifacts.nativeBinary: "
                "nativeBinaryStatus requires nativeBinary"
            )
        if requires_native_status:
            add_equal_error(
                errors,
                "$.summary.nativeBinaryStatus",
                summary["nativeBinaryStatus"],
                manifest_status,
                "manifest nativeBinaryStatus",
            )
    if "module" in reflection:
        add_equal_error(
            errors,
            "$.reflection.module",
            reflection["module"],
            summary["module"],
            "summary module",
        )
    if "target" in reflection:
        add_equal_error(
            errors,
            "$.reflection.target",
            reflection["target"],
            summary["target"],
            "summary target",
        )


def validate_recorded_manifest_summary_minimums(errors, summary):
    target = summary["target"]
    minimum_artifacts = PACKAGE_TARGET_MIN_ARTIFACT_COUNTS[target]
    if summary["debugArtifactsPresent"]:
        minimum_artifacts += PACKAGE_DEBUG_ARTIFACT_COUNT
    if summary["artifactCount"] < minimum_artifacts:
        errors.append(
            "$.summary.artifactCount: expected package summary "
            f"{target} artifact count >= {minimum_artifacts}, "
            f"got {summary['artifactCount']}"
        )


def validate_package_artifact_requirements(
    errors,
    requirements,
    manifest,
    summary,
    artifacts,
):
    if "packageArtifactRequirements" not in manifest:
        if requirements is not None:
            errors.append(
                "$.packageArtifactRequirements: expected absent when manifest "
                "does not record packageArtifactRequirements"
            )
        return

    manifest_requirements = manifest["packageArtifactRequirements"]
    if not isinstance(manifest_requirements, dict):
        errors.append("$.manifest.packageArtifactRequirements: expected object")
        return

    if not isinstance(requirements, dict):
        errors.append(
            "$.packageArtifactRequirements: expected object when manifest records "
            "packageArtifactRequirements"
        )
        return

    for field in (
        "target",
        "packageMode",
        "requiresNativeBinaryStatus",
        "allowsPlannedNativeBinary",
        "allowsPlannedNativeSourceEvidence",
    ):
        add_equal_error(
            errors,
            f"$.packageArtifactRequirements.{field}",
            requirements[field],
            manifest_requirements[field],
            "manifest package artifact requirement",
        )

    add_equal_error(
        errors,
        "$.packageArtifactRequirements.target",
        requirements["target"],
        summary["target"],
        "summary target",
    )

    expected_names = manifest_requirements["requiredPathArtifacts"]
    actual_records = requirements["requiredPathArtifacts"]
    actual_names = [record["name"] for record in actual_records]
    add_equal_error(
        errors,
        "$.packageArtifactRequirements.requiredPathArtifacts",
        actual_names,
        expected_names,
        "manifest required path artifacts",
    )
    if len(set(actual_names)) != len(actual_names):
        errors.append(
            "$.packageArtifactRequirements.requiredPathArtifacts: "
            "expected unique artifact names"
        )

    manifest_evidence_ids = manifest_requirements.get("evidenceIds")
    if isinstance(manifest_evidence_ids, list):
        add_equal_error(
            errors,
            "$.packageArtifactRequirements.evidenceIds",
            requirements.get("evidenceIds"),
            manifest_evidence_ids,
            "manifest package artifact requirement evidence IDs",
        )
        if "evidenceIdsLocation" not in requirements:
            errors.append(
                "$.packageArtifactRequirements.evidenceIdsLocation: expected "
                "source location when manifest packageArtifactRequirements "
                "record evidenceIds"
            )
    else:
        if "evidenceIds" in requirements:
            errors.append(
                "$.packageArtifactRequirements.evidenceIds: expected absent "
                "when manifest packageArtifactRequirements omit evidenceIds"
            )
        if "evidenceIdsLocation" in requirements:
            errors.append(
                "$.packageArtifactRequirements.evidenceIdsLocation: expected "
                "absent when manifest packageArtifactRequirements omit evidenceIds"
            )

    manifest_artifacts = manifest.get("artifacts")
    artifact_names = {
        record["name"] for record in artifacts if record["name"] != "nativeBinaryStatus"
    }
    if isinstance(manifest_artifacts, dict):
        manifest_artifact_names = {
            name for name in manifest_artifacts if name != "nativeBinaryStatus"
        }
        for index, name in enumerate(expected_names):
            if name not in manifest_artifact_names:
                errors.append(
                    "$.manifest.artifacts: recorded packageArtifactRequirements "
                    f"requiredPathArtifacts[{index}] {name!r} is not declared"
                )
            if name not in artifact_names:
                errors.append(
                    "$.artifacts: recorded packageArtifactRequirements "
                    f"requiredPathArtifacts[{index}] {name!r} is not inventoried"
                )
        if (
            manifest_requirements["requiresNativeBinaryStatus"]
            and manifest_artifacts.get("nativeBinaryStatus") is None
        ):
            errors.append(
                "$.manifest.artifacts.nativeBinaryStatus: recorded "
                "packageArtifactRequirements require nativeBinaryStatus"
            )

    for path in (
        "$.packageArtifactRequirements.location",
        "$.packageArtifactRequirements.targetLocation",
        "$.packageArtifactRequirements.packageModeLocation",
        "$.packageArtifactRequirements.requiredPathArtifactsLocation",
        "$.packageArtifactRequirements.evidenceIdsLocation",
    ):
        field = path.rsplit(".", 1)[-1]
        if field in requirements:
            validate_source_location_span(errors, path, requirements[field])

    for index, record in enumerate(actual_records):
        if "location" in record:
            validate_source_location_span(
                errors,
                f"$.packageArtifactRequirements.requiredPathArtifacts[{index}].location",
                record["location"],
            )


def validate_artifact_requirements_projection(
    errors,
    projection,
    manifest,
    native_artifact_descriptor,
):
    manifest_has_requirements = isinstance(
        manifest.get("packageArtifactRequirements"), dict
    )
    descriptor_present = (
        isinstance(native_artifact_descriptor, dict)
        and native_artifact_descriptor["artifactPresent"]
    )
    expected_basis = "legacy-missing-packageArtifactRequirements"
    if manifest_has_requirements:
        expected_basis = "recorded-packageArtifactRequirements"
    elif descriptor_present:
        expected_basis = "recorded-nativeArtifactDescriptor-health"

    add_equal_error(
        errors,
        "$.artifactRequirementsProjection.basis",
        projection["basis"],
        expected_basis,
        "artifact requirements projection basis",
    )
    add_equal_error(
        errors,
        "$.artifactRequirementsProjection.reportOnly",
        projection["reportOnly"],
        True,
        "artifact requirements projection report-only marker",
    )
    add_equal_error(
        errors,
        "$.artifactRequirementsProjection.packageArtifactRequirementsPresent",
        projection["packageArtifactRequirementsPresent"],
        manifest_has_requirements,
        "manifest packageArtifactRequirements presence",
    )
    add_equal_error(
        errors,
        "$.artifactRequirementsProjection.packageArtifactRequirementsSource",
        projection["packageArtifactRequirementsSource"],
        "manifest.packageArtifactRequirements" if manifest_has_requirements else None,
        "manifest packageArtifactRequirements source",
    )
    expected_native_status_match = None
    if manifest_has_requirements:
        requirements = manifest["packageArtifactRequirements"]
        native_status = manifest.get("artifacts", {}).get("nativeBinaryStatus")
        if native_status is None:
            expected_native_status_match = not requirements[
                "requiresNativeBinaryStatus"
            ]
        elif not requirements["requiresNativeBinaryStatus"]:
            expected_native_status_match = False
        elif native_status == "planned":
            expected_native_status_match = requirements["allowsPlannedNativeBinary"]
        else:
            expected_native_status_match = True
    add_equal_error(
        errors,
        "$.artifactRequirementsProjection.nativeBinaryStatusMatchesRequirements",
        projection["nativeBinaryStatusMatchesRequirements"],
        expected_native_status_match,
        "manifest nativeBinaryStatus agreement with packageArtifactRequirements",
    )
    add_equal_error(
        errors,
        "$.artifactRequirementsProjection.legacyManifestAbsence",
        projection["legacyManifestAbsence"],
        not manifest_has_requirements,
        "legacy manifest absence marker",
    )

    if isinstance(native_artifact_descriptor, dict):
        add_equal_error(
            errors,
            "$.artifactRequirementsProjection.nativeArtifactDescriptorArtifactPresent",
            projection["nativeArtifactDescriptorArtifactPresent"],
            native_artifact_descriptor["artifactPresent"],
            "native artifact descriptor artifact presence",
        )
        add_equal_error(
            errors,
            "$.artifactRequirementsProjection.nativeArtifactDescriptorHealth",
            projection["nativeArtifactDescriptorHealth"],
            native_artifact_descriptor["health"],
            "native artifact descriptor health",
        )
        add_equal_error(
            errors,
            "$.artifactRequirementsProjection.nativeArtifactDescriptorPath",
            projection["nativeArtifactDescriptorPath"],
            native_artifact_descriptor["path"],
            "native artifact descriptor path",
        )


def validate_debug_artifacts(errors, debug_artifacts, summary, artifacts):
    by_name = records_by_name(
        errors,
        "$.artifacts",
        artifacts,
        "artifact",
    )
    debug_declared = "debugMetadata" in by_name
    source_map_declared = "hirSourceMap" in by_name
    source_remap_declared = "sourceRemap" in by_name
    debug_exists = debug_declared and by_name["debugMetadata"]["exists"]
    source_map_exists = source_map_declared and by_name["hirSourceMap"]["exists"]
    source_remap_exists = source_remap_declared and by_name["sourceRemap"]["exists"]

    add_equal_error(
        errors,
        "$.debugArtifacts.debugMetadataArtifactPresent",
        debug_artifacts["debugMetadataArtifactPresent"],
        debug_declared,
        "debugMetadata artifact record presence",
    )
    add_equal_error(
        errors,
        "$.debugArtifacts.hirSourceMapArtifactPresent",
        debug_artifacts["hirSourceMapArtifactPresent"],
        source_map_declared,
        "hirSourceMap artifact record presence",
    )
    add_equal_error(
        errors,
        "$.debugArtifacts.debugMetadataExists",
        debug_artifacts["debugMetadataExists"],
        debug_exists,
        "debugMetadata artifact file existence",
    )
    add_equal_error(
        errors,
        "$.debugArtifacts.hirSourceMapExists",
        debug_artifacts["hirSourceMapExists"],
        source_map_exists,
        "hirSourceMap artifact file existence",
    )
    add_equal_error(
        errors,
        "$.summary.debugArtifactsPresent",
        summary["debugArtifactsPresent"],
        debug_artifacts["debugMetadataArtifactPresent"]
        and debug_artifacts["hirSourceMapArtifactPresent"],
        "debug artifact pair presence",
    )

    source_remap_health = "not-present"
    source_remap = debug_artifacts.get("sourceRemap")
    if isinstance(source_remap, dict):
        add_equal_error(
            errors,
            "$.debugArtifacts.sourceRemap.artifactPresent",
            source_remap["artifactPresent"],
            source_remap_declared,
            "sourceRemap artifact record presence",
        )
        add_equal_error(
            errors,
            "$.debugArtifacts.sourceRemap.exists",
            source_remap["exists"],
            source_remap_exists,
            "sourceRemap artifact file existence",
        )
        if source_remap_declared:
            add_equal_error(
                errors,
                "$.debugArtifacts.sourceRemap.path",
                source_remap["path"],
                by_name["sourceRemap"]["path"],
                "sourceRemap artifact path",
            )
        elif source_remap["path"] is not None:
            errors.append(
                "$.debugArtifacts.sourceRemap.path: expected null when absent"
            )

        source_remap_checks = source_remap["checks"]
        source_remap_check_values = [
            source_remap_checks[name] for name in SOURCE_REMAP_PROVENANCE_CHECKS
        ]
        if not source_remap_declared:
            expected_source_remap_health = "not-present"
            expected_source_remap_checks = [None] * len(source_remap_check_values)
            for field in SOURCE_REMAP_PROVENANCE_CONTENT_FIELDS:
                if source_remap[field] is not None:
                    errors.append(
                        f"$.debugArtifacts.sourceRemap.{field}: "
                        "expected null when absent"
                    )
        elif not source_remap_exists:
            expected_source_remap_health = "incomplete"
            expected_source_remap_checks = [None] * len(source_remap_check_values)
        elif all(value is True for value in source_remap_check_values):
            expected_source_remap_health = "ok"
            expected_source_remap_checks = None
        else:
            expected_source_remap_health = "drift"
            expected_source_remap_checks = None

        add_equal_error(
            errors,
            "$.debugArtifacts.sourceRemap.health",
            source_remap["health"],
            expected_source_remap_health,
            "sourceRemap provenance health from checks",
        )
        source_remap_health = source_remap["health"]
        if (
            expected_source_remap_checks is not None
            and source_remap_check_values != expected_source_remap_checks
        ):
            errors.append(
                "$.debugArtifacts.sourceRemap.checks: expected null checks "
                "when absent or incomplete"
            )
        if source_remap["sourceSha256"] is not None and not LOWERCASE_SHA256.fullmatch(
            source_remap["sourceSha256"]
        ):
            errors.append(
                "$.debugArtifacts.sourceRemap.sourceSha256: expected lowercase SHA-256"
            )
    elif source_remap_declared:
        source_remap_health = "drift"
        errors.append(
            "$.debugArtifacts.sourceRemap: expected provenance summary when "
            "sourceRemap artifact is declared"
        )

    checks = debug_artifacts["checks"]
    check_values = list(checks.values())
    if not debug_exists or not source_map_exists:
        expected_health = "incomplete"
        expected_checks = [None] * len(check_values)
    elif all(value is True for value in check_values) and source_remap_health in (
        "ok",
        "not-present",
    ):
        expected_health = "ok"
        expected_checks = None
    else:
        expected_health = "drift"
        expected_checks = None

    add_equal_error(
        errors,
        "$.debugArtifacts.health",
        debug_artifacts["health"],
        expected_health,
        "debug artifact health from checks",
    )
    if expected_checks is not None and check_values != expected_checks:
        errors.append("$.debugArtifacts.checks: expected null checks when incomplete")


def validate_native_artifact_descriptor(
    errors,
    descriptor,
    artifacts,
    manifest,
    summary,
):
    by_name = records_by_name(
        errors,
        "$.artifacts",
        artifacts,
        "artifact",
    )
    descriptor_declared = "nativeArtifactDescriptor" in by_name
    descriptor_exists = (
        descriptor_declared and by_name["nativeArtifactDescriptor"]["exists"]
    )

    add_equal_error(
        errors,
        "$.nativeArtifactDescriptor.artifactPresent",
        descriptor["artifactPresent"],
        descriptor_declared,
        "nativeArtifactDescriptor artifact record presence",
    )
    add_equal_error(
        errors,
        "$.nativeArtifactDescriptor.descriptorExists",
        descriptor["descriptorExists"],
        descriptor_exists,
        "nativeArtifactDescriptor file existence",
    )

    manifest_artifacts = manifest.get("artifacts")
    expected_path = (
        manifest_artifacts.get("nativeArtifactDescriptor")
        if isinstance(manifest_artifacts, dict)
        else None
    )
    add_equal_error(
        errors,
        "$.nativeArtifactDescriptor.path",
        descriptor["path"],
        expected_path,
        "manifest nativeArtifactDescriptor path",
    )

    checks = descriptor["checks"]
    check_values = list(checks.values())
    if not descriptor_declared:
        expected_health = "not-present"
        expected_checks = [None] * len(check_values)
    elif not descriptor_exists:
        expected_health = "incomplete"
        expected_checks = None
    elif checks["descriptorIdentityMatchesContract"] is False or any(
        descriptor[field] is None
        for field in (
            "target",
            "binaryKind",
            "sourcePath",
            "sourceHash",
            "optimizationLevel",
            "validationStatus",
        )
    ):
        expected_health = "invalid"
        expected_checks = None
    elif native_artifact_descriptor_health_self_invalid(descriptor, check_values):
        expected_health = "ok"
        expected_checks = None
    elif descriptor["health"] == "invalid":
        expected_health = "invalid"
        expected_checks = None
    elif native_artifact_descriptor_checks_report_ok(check_values):
        expected_health = "ok"
        expected_checks = None
    else:
        expected_health = "drift"
        expected_checks = None

    add_equal_error(
        errors,
        "$.nativeArtifactDescriptor.health",
        descriptor["health"],
        expected_health,
        "native artifact descriptor health from checks",
    )
    if expected_checks is not None and check_values != expected_checks:
        errors.append(
            "$.nativeArtifactDescriptor.checks: expected null checks when inactive"
        )

    if not descriptor_declared:
        validate_inactive_native_artifact_descriptor_content(
            errors,
            descriptor,
            "not present",
        )
    elif not descriptor_exists:
        validate_inactive_native_artifact_descriptor_content(
            errors,
            descriptor,
            "not readable",
        )

    if descriptor_declared and descriptor_exists:
        validate_native_artifact_descriptor_checks(
            errors,
            descriptor,
            by_name,
            manifest,
            summary,
        )

    if descriptor["health"] != "ok":
        return

    expected_identity = {
        "schemaVersion": 1,
        "kind": "crossgl.nativeArtifact",
        "contractVersion": "native-artifact-v0",
        "target": summary["target"],
    }
    for field, expected in expected_identity.items():
        add_equal_error(
            errors,
            f"$.nativeArtifactDescriptor.{field}",
            descriptor[field],
            expected,
            "native artifact descriptor identity",
        )


def validate_inactive_native_artifact_descriptor_content(errors, descriptor, state):
    for field in NATIVE_ARTIFACT_DESCRIPTOR_CONTENT_FIELDS:
        if descriptor.get(field) is not None:
            errors.append(
                f"$.nativeArtifactDescriptor.{field}: expected null when "
                f"nativeArtifactDescriptor artifact is {state}"
            )


def expected_native_artifact_source_name(binary_kind):
    if binary_kind == "vulkan.spirv-module":
        return "backendAssembly"
    if binary_kind in {
        "metal.metallib",
        "directx.dxil",
        "directx.dxbc",
        "opengl.source",
        "opengl.package",
    }:
        return "backendSource"
    return None


def native_artifact_file_fact_matches(record, descriptor_value, record_field):
    if (
        record is not None
        and record["packageRelative"]
        and record["exists"]
        and descriptor_value is not None
    ):
        return descriptor_value == record[record_field]
    return None


def native_artifact_descriptor_has_produced_artifact(descriptor):
    return all(
        descriptor.get(field) is not None
        for field in ("artifactPath", "artifactHash", "sizeBytes")
    )


def native_artifact_descriptor_checks_report_ok(check_values):
    return all(value is True or value is None for value in check_values)


def native_artifact_descriptor_health_self_invalid(descriptor, check_values):
    return (
        descriptor["health"] == "invalid"
        and native_artifact_descriptor_checks_report_ok(check_values)
        and isinstance(descriptor.get("optimizationEvidence"), dict)
    )


def validate_native_artifact_descriptor_optimization_evidence(errors, descriptor):
    evidence = descriptor.get("optimizationEvidence")
    if not isinstance(evidence, dict):
        return

    status = evidence.get("status")
    if status == "applied" and not native_artifact_descriptor_has_produced_artifact(
        descriptor,
    ):
        errors.append(
            "$.nativeArtifactDescriptor.optimizationEvidence.status: applied "
            "optimization evidence requires produced artifact facts"
        )

    if descriptor.get("nativeBinaryStatus") == "planned" and status == "applied":
        errors.append(
            "$.nativeArtifactDescriptor.optimizationEvidence.status: planned "
            "source-package descriptors must not claim applied optimization"
        )

    if descriptor.get("target") == "vulkan" and status == "applied":
        for field, expected in OPTIMIZED_VULKAN_EVIDENCE.items():
            actual = evidence.get(field)
            if actual != expected:
                errors.append(
                    "$.nativeArtifactDescriptor.optimizationEvidence."
                    f"{field}: optimized-native Vulkan evidence requires "
                    f"{expected!r}, got {actual!r}"
                )


def package_requires_native_binary_status(manifest, summary):
    requirements = manifest.get("packageArtifactRequirements")
    if isinstance(requirements, dict):
        return requirements.get("requiresNativeBinaryStatus") is True
    return summary["target"] in PACKAGE_TARGETS_REQUIRING_NATIVE_STATUS


def expected_native_artifact_descriptor_checks(
    descriptor,
    artifacts_by_name,
    manifest,
    summary,
):
    source_name = expected_native_artifact_source_name(descriptor["binaryKind"])
    source_record = artifacts_by_name.get(source_name) if source_name else None
    native_binary_record = artifacts_by_name.get("nativeBinary")
    planned = summary["nativeBinaryStatus"] == "planned"
    requires_native_status = package_requires_native_binary_status(manifest, summary)
    source_path_matches = None
    artifact_path_matches = None
    validation_matches = None

    if source_record is not None and descriptor["sourcePath"] is not None:
        source_path_matches = descriptor["sourcePath"] == source_record["path"]
    elif descriptor["sourcePath"] is not None or descriptor["binaryKind"] is not None:
        source_path_matches = False

    if planned:
        artifact_path_matches = descriptor["artifactPath"] is None
    elif native_binary_record is not None and descriptor["artifactPath"] is not None:
        artifact_path_matches = (
            descriptor["artifactPath"] == native_binary_record["path"]
        )
    elif native_binary_record is not None or descriptor["artifactPath"] is not None:
        artifact_path_matches = False

    if descriptor["validationStatus"] is not None:
        descriptor_validated = descriptor["validationStatus"] == "validated"
        if requires_native_status or descriptor["nativeBinaryStatus"]:
            native_validated = descriptor["nativeBinaryStatus"] == "validated"
            validation_matches = descriptor_validated == native_validated
        else:
            validation_matches = True

    return {
        "descriptorIdentityMatchesContract": (
            descriptor["schemaVersion"] == 1
            and descriptor["kind"] == "crossgl.nativeArtifact"
            and descriptor["contractVersion"] == "native-artifact-v0"
        ),
        "targetMatchesPackage": (
            descriptor["target"] is not None
            and descriptor["target"] == summary["target"]
        ),
        "nativeBinaryStatusMatchesPackage": (
            descriptor["nativeBinaryStatus"] == summary["nativeBinaryStatus"]
            if requires_native_status and summary["nativeBinaryStatus"] is not None
            else descriptor["nativeBinaryStatus"] is None
        ),
        "sourcePathMatchesManifest": source_path_matches,
        "sourceHashMatchesFile": native_artifact_file_fact_matches(
            source_record,
            descriptor["sourceHash"],
            "sha256",
        ),
        "artifactPathMatchesManifest": artifact_path_matches,
        "artifactHashMatchesFile": (
            None
            if planned
            else native_artifact_file_fact_matches(
                native_binary_record,
                descriptor["artifactHash"],
                "sha256",
            )
        ),
        "sizeBytesMatchesFile": (
            None
            if planned
            else native_artifact_file_fact_matches(
                native_binary_record,
                descriptor["sizeBytes"],
                "sizeBytes",
            )
        ),
        "validationStatusMatchesNativeStatus": validation_matches,
    }


def validate_native_artifact_descriptor_checks(
    errors,
    descriptor,
    artifacts_by_name,
    manifest,
    summary,
):
    checks = descriptor["checks"]
    expected_check_values = expected_native_artifact_descriptor_checks(
        descriptor,
        artifacts_by_name,
        manifest,
        summary,
    )

    for check_name in NATIVE_ARTIFACT_DESCRIPTOR_CHECKS:
        add_equal_error(
            errors,
            f"$.nativeArtifactDescriptor.checks.{check_name}",
            checks[check_name],
            expected_check_values[check_name],
            f"native artifact descriptor {check_name}",
        )
    validate_native_artifact_descriptor_optimization_evidence(errors, descriptor)


def validate_vulkan_native_profile(errors, profile, summary, artifacts):
    by_name = records_by_name(
        errors,
        "$.artifacts",
        artifacts,
        "artifact",
    )
    is_vulkan = summary["target"] == "vulkan"
    profile_declared = "nativeProfile" in by_name
    profile_exists = profile_declared and by_name["nativeProfile"]["exists"]

    add_equal_error(
        errors,
        "$.vulkanNativeProfile.applicable",
        profile["applicable"],
        is_vulkan,
        "Vulkan profile applicability",
    )
    add_equal_error(
        errors,
        "$.vulkanNativeProfile.nativeProfileArtifactPresent",
        profile["nativeProfileArtifactPresent"],
        profile_declared,
        "nativeProfile artifact record presence",
    )
    add_equal_error(
        errors,
        "$.vulkanNativeProfile.nativeProfileExists",
        profile["nativeProfileExists"],
        profile_exists,
        "nativeProfile artifact file existence",
    )

    checks = profile["checks"]
    check_values = list(checks.values())
    health_check_values = [
        value
        for name, value in checks.items()
        if name != "emittedDisassemblyExists" or value is not None
    ]
    if not is_vulkan:
        expected_health = "not-applicable"
        expected_checks = [None] * len(check_values)
    elif not profile_exists:
        expected_health = "incomplete"
        expected_checks = [None] * len(check_values)
    elif all(value is True for value in health_check_values):
        expected_health = "ok"
        expected_checks = None
    else:
        expected_health = "drift"
        expected_checks = None

    add_equal_error(
        errors,
        "$.vulkanNativeProfile.health",
        profile["health"],
        expected_health,
        "Vulkan native profile health from checks",
    )
    if expected_checks is not None and check_values != expected_checks:
        errors.append(
            "$.vulkanNativeProfile.checks: expected null checks when inactive"
        )


def evidence_ids_present(value):
    return isinstance(value, list) and len(value) > 0


def target_tool_sidecars_drift(left, right):
    for field in TARGET_LEGALIZATION_TOOL_FIELDS:
        left_value = left.get(field)
        right_value = right.get(field)
        if (
            left_value is not None
            and right_value is not None
            and left_value != right_value
        ):
            return True
    return False


def target_tool_sidecar_matches_manifest(manifest_tool_requirements, sidecar):
    if not manifest_tool_requirements["present"] or not sidecar["artifactExists"]:
        return None
    return all(
        sidecar[field] is not None
        and sidecar[field] == manifest_tool_requirements[field]
        for field in TARGET_LEGALIZATION_TOOL_FIELDS
    )


def expected_target_legalization_health(evidence):
    checks = evidence["checks"]
    drift_checks = (
        "manifestToolRequirementsTargetMatchesPackage",
        "manifestToolRequirementsPackageModeMatchesRequirements",
        "debugMetadataTargetMatchesPackage",
        "targetExplanationTargetMatchesPackage",
        "debugMetadataPackageModeMatchesRequirements",
        "targetExplanationPackageModeMatchesRequirements",
        "debugMetadataToolRequirementsMatchManifest",
        "targetExplanationToolRequirementsMatchManifest",
    )
    if any(checks[name] is False for name in drift_checks):
        return "drift"
    if target_tool_sidecars_drift(
        evidence["debugMetadata"],
        evidence["targetExplanation"],
    ):
        return "drift"

    for sidecar_name in ("debugMetadata", "targetExplanation"):
        sidecar = evidence[sidecar_name]
        if sidecar["artifactPresent"] and (
            not sidecar["artifactExists"]
            or sidecar["target"] is None
            or sidecar["packageMode"] is None
            or not evidence_ids_present(sidecar["legalizationCoreEvidenceIds"])
        ):
            return "incomplete"

    if (
        checks["packageArtifactRequirementEvidenceIdsPresent"] is False
        or checks["manifestToolRequirementEvidenceIdsPresent"] is False
    ):
        return "partial"
    return "ok"


def validate_target_legalization_sidecar(
    errors,
    path,
    sidecar,
    artifact_records,
    artifact_name,
):
    artifact = artifact_records.get(artifact_name)
    artifact_present = artifact is not None
    artifact_exists = artifact_present and artifact["exists"]
    add_equal_error(
        errors,
        f"{path}.artifactPresent",
        sidecar["artifactPresent"],
        artifact_present,
        f"{artifact_name} artifact record presence",
    )
    add_equal_error(
        errors,
        f"{path}.artifactExists",
        sidecar["artifactExists"],
        artifact_exists,
        f"{artifact_name} artifact file existence",
    )
    if not artifact_exists:
        if sidecar["target"] is not None:
            errors.append(f"{path}.target: expected null when artifact is unreadable")
        if sidecar["packageMode"] is not None:
            errors.append(
                f"{path}.packageMode: expected null when artifact is unreadable"
            )
        if sidecar["packageDecisionReason"] is not None:
            errors.append(
                f"{path}.packageDecisionReason: expected null when artifact is unreadable"
            )
        if sidecar["legalizationCoreEvidenceIds"] is not None:
            errors.append(
                f"{path}.legalizationCoreEvidenceIds: expected null when artifact is unreadable"
            )
        if sidecar["packageArtifactRequirementEvidenceIds"] is not None:
            errors.append(
                f"{path}.packageArtifactRequirementEvidenceIds: expected null when artifact is unreadable"
            )
        for field in TARGET_LEGALIZATION_TOOL_FIELDS:
            if sidecar[field] is not None:
                errors.append(
                    f"{path}.{field}: expected null when artifact is unreadable"
                )
    validate_target_legalization_tool_sidecar_fields(errors, path, sidecar)


def expected_optional_native_tool_status(sidecar):
    if sidecar["packageMode"] != "source-package":
        return "not-required"
    if sidecar["missingToolIds"]:
        return "missing"
    if sidecar["requiredToolIds"]:
        return "available"
    return "not-required"


def validate_target_legalization_tool_sidecar_fields(errors, path, sidecar):
    present_fields = [
        field for field in TARGET_LEGALIZATION_TOOL_FIELDS if sidecar[field] is not None
    ]
    if present_fields and len(present_fields) != len(TARGET_LEGALIZATION_TOOL_FIELDS):
        missing_fields = sorted(
            set(TARGET_LEGALIZATION_TOOL_FIELDS) - set(present_fields)
        )
        errors.append(
            f"{path}: tool requirement fields must be emitted together, missing "
            f"{missing_fields!r}"
        )
        return
    if not present_fields:
        return

    for count_field, ids_field in (
        ("requiredToolCount", "requiredToolIds"),
        ("missingToolCount", "missingToolIds"),
    ):
        if sidecar[count_field] != len(sidecar[ids_field]):
            errors.append(
                f"{path}.{count_field}: expected {ids_field} length "
                f"{len(sidecar[ids_field])}, got {sidecar[count_field]!r}"
            )

    outside_required = sorted(
        set(sidecar["missingToolIds"]) - set(sidecar["requiredToolIds"])
    )
    if outside_required:
        errors.append(
            f"{path}.missingToolIds: tool ID(s) are not required: {outside_required!r}"
        )

    expected_optional_missing = sidecar["packageMode"] == "source-package" and bool(
        sidecar["missingToolIds"]
    )
    if sidecar["optionalNativeToolMissing"] != expected_optional_missing:
        errors.append(
            f"{path}.optionalNativeToolMissing: expected "
            f"{expected_optional_missing!r} for packageMode "
            f"{sidecar['packageMode']!r} and {len(sidecar['missingToolIds'])} "
            f"missing tool ID(s), got {sidecar['optionalNativeToolMissing']!r}"
        )

    expected_status = expected_optional_native_tool_status(sidecar)
    if sidecar["optionalNativeToolStatus"] != expected_status:
        errors.append(
            f"{path}.optionalNativeToolStatus: expected {expected_status!r}, "
            f"got {sidecar['optionalNativeToolStatus']!r}"
        )

    if not evidence_ids_present(sidecar["toolRequirementEvidenceIds"]):
        errors.append(
            f"{path}.toolRequirementEvidenceIds: expected non-empty tool "
            "requirement evidence IDs when tool requirement fields are present"
        )


def validate_target_legalization_manifest_tool_requirements(
    errors,
    evidence,
    manifest,
    summary,
):
    path = "$.targetLegalizationEvidence.manifestToolRequirements"
    manifest_tool_requirements = evidence["manifestToolRequirements"]
    recorded = manifest.get("targetLegalizationToolRequirements")
    if not isinstance(recorded, dict):
        add_equal_error(
            errors,
            f"{path}.present",
            manifest_tool_requirements["present"],
            False,
            "manifest target legalization tool requirements presence",
        )
        for field in ("target", "packageMode", *TARGET_LEGALIZATION_TOOL_FIELDS):
            if manifest_tool_requirements[field] is not None:
                errors.append(f"{path}.{field}: expected null when absent")
        for check_name in (
            "manifestToolRequirementsTargetMatchesPackage",
            "manifestToolRequirementsPackageModeMatchesRequirements",
            "manifestToolRequirementEvidenceIdsPresent",
        ):
            if evidence["checks"][check_name] is not None:
                errors.append(
                    "$.targetLegalizationEvidence.checks."
                    f"{check_name}: expected null when manifest tool "
                    "requirements are absent"
                )
        return

    add_equal_error(
        errors,
        f"{path}.present",
        manifest_tool_requirements["present"],
        True,
        "manifest target legalization tool requirements presence",
    )
    for field in ("target", "packageMode", *TARGET_LEGALIZATION_TOOL_FIELDS):
        add_equal_error(
            errors,
            f"{path}.{field}",
            manifest_tool_requirements[field],
            recorded[field],
            "manifest target legalization tool requirement field",
        )
    validate_target_legalization_tool_sidecar_fields(
        errors,
        path,
        manifest_tool_requirements,
    )
    add_equal_error(
        errors,
        "$.targetLegalizationEvidence.checks."
        "manifestToolRequirementsTargetMatchesPackage",
        evidence["checks"]["manifestToolRequirementsTargetMatchesPackage"],
        manifest_tool_requirements["target"] == summary["target"],
        "manifest tool requirements target matches package",
    )
    add_equal_error(
        errors,
        "$.targetLegalizationEvidence.checks."
        "manifestToolRequirementsPackageModeMatchesRequirements",
        evidence["checks"]["manifestToolRequirementsPackageModeMatchesRequirements"],
        manifest_tool_requirements["packageMode"]
        == manifest.get("packageArtifactRequirements", {}).get("packageMode"),
        "manifest tool requirements packageMode matches package requirements",
    )
    add_equal_error(
        errors,
        "$.targetLegalizationEvidence.checks.manifestToolRequirementEvidenceIdsPresent",
        evidence["checks"]["manifestToolRequirementEvidenceIdsPresent"],
        evidence_ids_present(manifest_tool_requirements["toolRequirementEvidenceIds"]),
        "manifest tool requirement evidence presence",
    )
    if (
        not evidence_ids_present(
            manifest_tool_requirements["toolRequirementEvidenceIds"]
        )
        and "manifest.targetLegalizationToolRequirements.toolRequirementEvidenceIds"
        not in evidence["missingEvidence"]
    ):
        errors.append(
            "$.targetLegalizationEvidence.missingEvidence: expected manifest "
            "targetLegalizationToolRequirements evidence marker"
        )


def validate_sidecar_requirement_evidence_ids(errors, path, sidecar, expected):
    ids = sidecar["packageArtifactRequirementEvidenceIds"]
    if ids is None:
        return
    if expected is None:
        errors.append(
            f"{path}.packageArtifactRequirementEvidenceIds: expected null "
            "when aggregate packageArtifactRequirementEvidenceIds is null"
        )
        return
    add_equal_error(
        errors,
        f"{path}.packageArtifactRequirementEvidenceIds",
        ids,
        expected,
        "aggregate package artifact requirement evidence IDs",
    )


def validate_target_legalization_evidence(
    errors,
    evidence,
    manifest,
    summary,
    artifacts,
):
    artifacts_by_name = records_by_name(
        errors,
        "$.artifacts",
        artifacts,
        "artifact",
    )
    validate_target_legalization_sidecar(
        errors,
        "$.targetLegalizationEvidence.debugMetadata",
        evidence["debugMetadata"],
        artifacts_by_name,
        "debugMetadata",
    )
    validate_target_legalization_sidecar(
        errors,
        "$.targetLegalizationEvidence.targetExplanation",
        evidence["targetExplanation"],
        artifacts_by_name,
        "targetExplanation",
    )

    validate_target_legalization_manifest_tool_requirements(
        errors,
        evidence,
        manifest,
        summary,
    )

    manifest_requirements = manifest.get("packageArtifactRequirements")
    if isinstance(manifest_requirements, dict):
        add_equal_error(
            errors,
            "$.targetLegalizationEvidence.packageMode",
            evidence["packageMode"],
            manifest_requirements["packageMode"],
            "manifest packageArtifactRequirements packageMode",
        )
        add_equal_error(
            errors,
            "$.targetLegalizationEvidence.packageModeSource",
            evidence["packageModeSource"],
            "manifest.packageArtifactRequirements",
            "target legalization package mode source",
        )
        manifest_evidence_ids = manifest_requirements.get("evidenceIds")
        if isinstance(manifest_evidence_ids, list):
            add_equal_error(
                errors,
                "$.targetLegalizationEvidence.packageArtifactRequirementEvidenceIds",
                evidence["packageArtifactRequirementEvidenceIds"],
                manifest_evidence_ids,
                "manifest package artifact requirement evidence IDs",
            )
        expected_ids_present = evidence_ids_present(
            evidence["packageArtifactRequirementEvidenceIds"]
        )
        add_equal_error(
            errors,
            "$.targetLegalizationEvidence.checks.packageArtifactRequirementEvidenceIdsPresent",
            evidence["checks"]["packageArtifactRequirementEvidenceIdsPresent"],
            expected_ids_present,
            "package artifact requirement evidence presence",
        )
        if (
            not expected_ids_present
            and "packageArtifactRequirementEvidenceIds"
            not in evidence["missingEvidence"]
        ):
            errors.append(
                "$.targetLegalizationEvidence.missingEvidence: expected "
                "packageArtifactRequirementEvidenceIds marker"
            )
        validate_sidecar_requirement_evidence_ids(
            errors,
            "$.targetLegalizationEvidence.debugMetadata",
            evidence["debugMetadata"],
            evidence["packageArtifactRequirementEvidenceIds"],
        )
        validate_sidecar_requirement_evidence_ids(
            errors,
            "$.targetLegalizationEvidence.targetExplanation",
            evidence["targetExplanation"],
            evidence["packageArtifactRequirementEvidenceIds"],
        )
    else:
        if evidence["packageArtifactRequirementEvidenceIds"] is not None:
            errors.append(
                "$.targetLegalizationEvidence.packageArtifactRequirementEvidenceIds: "
                "expected null without manifest packageArtifactRequirements"
            )
        if (
            evidence["checks"]["packageArtifactRequirementEvidenceIdsPresent"]
            is not None
        ):
            errors.append(
                "$.targetLegalizationEvidence.checks."
                "packageArtifactRequirementEvidenceIdsPresent: expected null "
                "without manifest packageArtifactRequirements"
            )

    for sidecar_name, check_prefix in (
        ("debugMetadata", "debugMetadata"),
        ("targetExplanation", "targetExplanation"),
    ):
        sidecar = evidence[sidecar_name]
        if sidecar["target"] is not None:
            add_equal_error(
                errors,
                "$.targetLegalizationEvidence.checks."
                f"{check_prefix}TargetMatchesPackage",
                evidence["checks"][f"{check_prefix}TargetMatchesPackage"],
                sidecar["target"] == summary["target"],
                f"{sidecar_name} target matches package",
            )
        if (
            isinstance(manifest_requirements, dict)
            and sidecar["packageMode"] is not None
        ):
            add_equal_error(
                errors,
                "$.targetLegalizationEvidence.checks."
                f"{check_prefix}PackageModeMatchesRequirements",
                evidence["checks"][f"{check_prefix}PackageModeMatchesRequirements"],
                sidecar["packageMode"] == manifest_requirements["packageMode"],
                f"{sidecar_name} packageMode matches requirements",
            )
        expected_tool_match = target_tool_sidecar_matches_manifest(
            evidence["manifestToolRequirements"],
            sidecar,
        )
        add_equal_error(
            errors,
            "$.targetLegalizationEvidence.checks."
            f"{check_prefix}ToolRequirementsMatchManifest",
            evidence["checks"][f"{check_prefix}ToolRequirementsMatchManifest"],
            expected_tool_match,
            f"{sidecar_name} tool requirements match manifest",
        )

    expected_health = expected_target_legalization_health(evidence)
    add_equal_error(
        errors,
        "$.targetLegalizationEvidence.health",
        evidence["health"],
        expected_health,
        "target legalization evidence health",
    )


def validate_publication(errors, publication):
    validate_normalized_package_path(
        errors,
        "$.publication.requestedPath",
        publication["requestedPath"],
    )

    state = publication["state"]
    sidecar_kind = publication["sidecarKind"]
    sidecar_token = publication["sidecarToken"]
    sidecar_attempt = publication["sidecarAttempt"]
    sidecars = publication["siblingSidecars"]

    add_length_count_error(
        errors,
        "$.publication.siblingSidecarCount",
        publication["siblingSidecarCount"],
        sidecars,
        "sibling sidecar length",
    )

    expected_kind = {"staged": "staging", "previous": "previous"}.get(state)
    if expected_kind is None:
        if sidecar_kind is not None:
            errors.append("$.publication.sidecarKind: expected null when published")
        if sidecar_token is not None:
            errors.append("$.publication.sidecarToken: expected null when published")
        if sidecar_attempt is not None:
            errors.append("$.publication.sidecarAttempt: expected null when published")
    else:
        add_equal_error(
            errors,
            "$.publication.sidecarKind",
            sidecar_kind,
            expected_kind,
            "publication sidecar kind",
        )
        if not isinstance(sidecar_token, str) or not sidecar_token:
            errors.append(
                "$.publication.sidecarToken: expected non-empty sidecar token"
            )
        if not isinstance(sidecar_attempt, int):
            errors.append("$.publication.sidecarAttempt: expected sidecar attempt")

    for index, sidecar in enumerate(sidecars):
        sidecar_path = f"$.publication.siblingSidecars[{index}]"
        validate_normalized_package_path(
            errors, f"{sidecar_path}.path", sidecar["path"]
        )
        if not sidecar["token"]:
            errors.append(f"{sidecar_path}.token: expected non-empty token")


def validate_failure_diagnostics(errors, instance):
    diagnostics = instance["diagnostics"]
    counts = instance["diagnosticCounts"]
    expected_counts = {"note": 0, "warning": 0, "error": 0}
    for index, diagnostic in enumerate(diagnostics):
        diagnostic_path = f"$.diagnostics[{index}]"
        severity = diagnostic["severity"]
        expected_counts[severity] += 1
        validate_source_location_span(
            errors,
            f"{diagnostic_path}.location",
            diagnostic["location"],
        )
    for severity, expected_count in expected_counts.items():
        add_equal_error(
            errors,
            f"$.diagnosticCounts.{severity}",
            counts[severity],
            expected_count,
            f"{severity} diagnostic count",
        )


def validate_semantics(instance):
    errors = []
    validate_normalized_package_path(errors, "$.packagePath", instance["packagePath"])
    if instance.get("success") is False:
        validate_failure_diagnostics(errors, instance)
        return errors

    summary = instance["summary"]
    manifest = instance["manifest"]
    reflection = instance["reflection"]
    debug_artifacts = instance.get("debugArtifacts")
    vulkan_native_profile = instance.get("vulkanNativeProfile")
    native_artifact_descriptor = instance.get("nativeArtifactDescriptor")
    artifact_requirements_projection = instance.get("artifactRequirementsProjection")
    target_legalization_evidence = instance.get("targetLegalizationEvidence")
    package_artifact_requirements = instance.get("packageArtifactRequirements")
    publication = instance.get("publication")
    if not isinstance(manifest.get("packageArtifactRequirements"), dict):
        validate_package_summary_minimums(
            errors,
            "$.summary",
            summary,
            "package summary",
        )
    else:
        validate_recorded_manifest_summary_minimums(errors, summary)
    validate_root_files(errors, instance["rootFiles"])
    validate_artifacts(errors, summary, instance["artifacts"], manifest)
    validate_manifest_summary(errors, summary, manifest, reflection)
    validate_embedded_reflection_semantics(errors, reflection)
    validate_descriptor_array_binding_metadata(errors, reflection)
    validate_package_artifact_requirements(
        errors,
        package_artifact_requirements,
        manifest,
        summary,
        instance["artifacts"],
    )
    if isinstance(artifact_requirements_projection, dict):
        validate_artifact_requirements_projection(
            errors,
            artifact_requirements_projection,
            manifest,
            native_artifact_descriptor,
        )
    if isinstance(debug_artifacts, dict):
        validate_debug_artifacts(
            errors,
            debug_artifacts,
            summary,
            instance["artifacts"],
        )
    if isinstance(vulkan_native_profile, dict):
        validate_vulkan_native_profile(
            errors,
            vulkan_native_profile,
            summary,
            instance["artifacts"],
        )
    if isinstance(native_artifact_descriptor, dict):
        validate_native_artifact_descriptor(
            errors,
            native_artifact_descriptor,
            instance["artifacts"],
            manifest,
            summary,
        )
    if isinstance(target_legalization_evidence, dict):
        validate_target_legalization_evidence(
            errors,
            target_legalization_evidence,
            manifest,
            summary,
            instance["artifacts"],
        )
    elif isinstance(manifest.get("packageArtifactRequirements"), dict):
        errors.append(
            "$.targetLegalizationEvidence: expected structured missing evidence "
            "when manifest records packageArtifactRequirements"
        )
    if isinstance(publication, dict):
        validate_publication(errors, publication)
    return errors
