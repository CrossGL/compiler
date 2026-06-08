#!/usr/bin/env python3
"""Check package inspect behavior with synthetic packages."""

import argparse
import copy
import hashlib
import json
import os
import subprocess
import sys
import tempfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from check_package_integrity_fixtures import (
    MODULE_NAME,
    add_native_artifact_descriptor,
    duplicate_manifest_artifact,
    hir_source_map_with_all_record_kinds,
    hir_source_map_with_expression,
    mark_native_artifact_validated,
    make_package,
    nonuniform_target_features,
    package_path,
    rewrite_debug_metadata_locations,
    rewrite_manifest,
    storage_image_target_features,
    TARGET_ARTIFACT_PATHS,
    write_nonuniform_diagnostics,
    write_nonuniform_reflection,
    write_storage_image_reflection,
    write_json,
    write_text,
)
from package_fixture_json_contracts import (
    expect_array,
    expect_equal,
    expect_object,
    expect_package_path_contract,
    expect_package_summary_manifest_contract,
    expected_manifest_artifact_names,
    expected_summary_native_binary_status,
)
from source_location_fixture_checks import (
    expect_location,
    expect_location_overlaps_text,
    expect_location_spans_file,
    expect_location_span_coherent,
    expect_location_text_equals,
)


EXPECTED_ROOT_FILES = {
    "manifest": "manifest.json",
    "reflection": "reflection.json",
    "diagnostics": "diagnostics.json",
}
SYNTHETIC_STORAGE_IMAGE_ARRAY_SOURCE_COORDINATES = {
    "maskAtlases": {"stage": "compute", "set": 0, "binding": 1},
    "unsignedAtlases": {"stage": "compute", "set": 0, "binding": 1},
}

CROSSGL_PACKAGE_INSPECT_FIXTURE_JOBS = "CROSSGL_PACKAGE_INSPECT_FIXTURE_JOBS"


def parse_jobs(value, label):
    if value is None or value == "":
        return 1
    try:
        jobs = int(value)
    except ValueError as exc:
        raise ValueError(f"{label} must be a positive integer") from exc
    if jobs < 1:
        raise ValueError(f"{label} must be a positive integer")
    return jobs


def collect_case_errors(jobs, cases):
    if jobs <= 1 or len(cases) <= 1:
        errors = []
        for case in cases:
            errors.extend(case())
        return errors

    errors = []
    with ThreadPoolExecutor(max_workers=min(jobs, len(cases))) as executor:
        for case_errors in executor.map(lambda case: case(), cases):
            errors.extend(case_errors)
    return errors


def case_tmp_dir(tmp_dir, case_name):
    return tmp_dir / case_name


def run_inspect(cglc, package, json_output=True):
    command = [str(cglc), "package", "inspect", str(package)]
    if json_output:
        command.append("--json")
    return subprocess.run(
        command,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )


def validate_schema(root, tmp_dir, case_name, inspect_json):
    instance_path = tmp_dir / f"{case_name}.package-inspect.json"
    instance_path.write_text(inspect_json, encoding="utf-8")
    result = subprocess.run(
        [
            sys.executable,
            str(root / "tools" / "validate_json_schema.py"),
            "--schema",
            str(root / "docs" / "schemas" / "package-inspect-v1.schema.json"),
            "--instance",
            str(instance_path),
        ],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if result.returncode != 0:
        return [
            f"{case_name}: package inspect JSON failed schema validation: "
            f"{result.stderr}{result.stdout}".strip()
        ]
    return []


def record_by_name(records, name):
    for record in records:
        if record.get("name") == name:
            return record
    raise KeyError(name)


def reflection_source_coordinate(record):
    return {
        "stage": record.get("stage"),
        "set": record.get("set"),
        "binding": record.get("binding"),
    }


def reflection_target_binding_coordinate(target, record):
    if target == "directx":
        return {
            "target": record.get("target"),
            "stage": record.get("stage"),
            "entryPoint": record.get("entryPoint"),
            "abi": record.get("abi"),
            "addressSpace": record.get("addressSpace"),
            "registerClass": record.get("bindingClass"),
            "descriptorType": record.get("descriptorType"),
            "registerSpace": record.get("set"),
            "register": record.get("binding"),
            "argumentIndex": record.get("argumentIndex"),
        }
    if target == "opengl":
        return {
            "target": record.get("target"),
            "stage": record.get("stage"),
            "entryPoint": record.get("entryPoint"),
            "abi": record.get("abi"),
            "addressSpace": record.get("addressSpace"),
            "bindingClass": record.get("bindingClass"),
            "programResourceBinding": record.get("argumentIndex"),
            "sourceSet": record.get("set"),
            "sourceBinding": record.get("binding"),
        }
    if target == "metal":
        return {
            "target": record.get("target"),
            "stage": record.get("stage"),
            "entryPoint": record.get("entryPoint"),
            "abi": record.get("abi"),
            "addressSpace": record.get("addressSpace"),
            "bindingClass": record.get("bindingClass"),
            "argumentIndex": record.get("argumentIndex"),
            "sourceSet": record.get("set"),
            "sourceBinding": record.get("binding"),
        }
    if target == "vulkan":
        return {
            "target": record.get("target"),
            "stage": record.get("stage"),
            "entryPoint": record.get("entryPoint"),
            "abi": record.get("abi"),
            "addressSpace": record.get("addressSpace"),
            "bindingClass": record.get("bindingClass"),
            "descriptorType": record.get("descriptorType"),
            "storageClass": record.get("storageClass"),
            "descriptorSet": record.get("set"),
            "descriptorBinding": record.get("binding"),
        }
    raise ValueError(f"unsupported storage-image parity target {target!r}")


def expected_storage_image_array_target_coordinate(target, resource):
    source_set = resource.get("set")
    source_binding = resource.get("binding")
    if target == "directx":
        return {
            "target": "directx",
            "stage": "compute",
            "entryPoint": "compute_main",
            "abi": "registerBinding",
            "addressSpace": "unordered-access",
            "registerClass": "uav",
            "descriptorType": "UAV",
            "registerSpace": source_set,
            "register": source_binding,
            "argumentIndex": source_binding,
        }
    if target == "opengl":
        return {
            "target": "opengl",
            "stage": "compute",
            "entryPoint": "compute_main",
            "abi": "programResourceBinding",
            "addressSpace": "image",
            "bindingClass": "image",
            "programResourceBinding": source_binding,
            "sourceSet": source_set,
            "sourceBinding": source_binding,
        }
    if target == "metal":
        return {
            "target": "metal",
            "stage": "compute",
            "entryPoint": "compute_main",
            "abi": "kernelArgument",
            "addressSpace": "texture",
            "bindingClass": "texture",
            "argumentIndex": source_binding,
            "sourceSet": source_set,
            "sourceBinding": source_binding,
        }
    if target == "vulkan":
        return {
            "target": "vulkan",
            "stage": "compute",
            "entryPoint": "compute_main",
            "abi": "descriptor",
            "addressSpace": "UniformConstant",
            "bindingClass": "storageImage",
            "descriptorType": "VK_DESCRIPTOR_TYPE_STORAGE_IMAGE",
            "storageClass": "UniformConstant",
            "descriptorSet": source_set,
            "descriptorBinding": source_binding,
        }
    raise ValueError(f"unsupported storage-image parity target {target!r}")


def expected_synthetic_storage_image_array_source_coordinate(array_name):
    return dict(SYNTHETIC_STORAGE_IMAGE_ARRAY_SOURCE_COORDINATES[array_name])


def expected_array_element_count(resource):
    if resource.get("arrayElementCount") is not None:
        return resource.get("arrayElementCount")
    dimensions = resource.get("arrayDimensions")
    if not isinstance(dimensions, list) or not dimensions:
        return None
    element_count = 1
    for dimension in dimensions:
        if not isinstance(dimension, dict):
            return None
        dimension_count = dimension.get("elementCount")
        if dimension_count is None:
            return None
        element_count *= dimension_count
    return element_count


def sha256_file(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def is_package_relative_artifact_path(value):
    if not isinstance(value, str) or value == "":
        return False
    if "\\" in value:
        return False
    if value.startswith("/"):
        return False
    if len(value) >= 2 and value[0].isalpha() and value[1] == ":":
        return False
    if ".." in value.split("/"):
        return False
    return True


def expect_artifact_path_identity(errors, case_name, path, record):
    artifact_path = record.get("path")
    expected_package_relative = is_package_relative_artifact_path(artifact_path)
    expect_equal(
        errors,
        case_name,
        f"{path}.packageRelative",
        record.get("packageRelative"),
        expected_package_relative,
    )
    if not expected_package_relative and record.get("exists") is True:
        errors.append(
            f"{case_name}: expected {path}.exists to be false when artifact path "
            "is not package-relative"
        )


def parse_sidecar_path(path):
    name = path.name
    if not name.startswith("."):
        return None
    markers = []
    for marker, kind in ((".staging-", "staging"), (".previous-", "previous")):
        position = name.rfind(marker)
        if position > 1:
            markers.append((position, marker, kind))
    if not markers:
        return None
    position, marker, kind = max(markers)
    payload = name[position + len(marker) :]
    token, separator, attempt_text = payload.rpartition("-")
    if not separator or not token or not attempt_text.isdigit():
        return None
    requested = path.with_name(name[1:position])
    return {
        "kind": kind,
        "state": "staged" if kind == "staging" else kind,
        "token": token,
        "attempt": int(attempt_text),
        "requested": requested,
    }


def records_by_name(errors, case_name, path, records, label):
    by_name = {}
    for index, record in enumerate(records):
        record_path = f"{path}[{index}]"
        if not isinstance(record, dict):
            errors.append(f"{case_name}: expected {record_path} to be an object")
            continue

        name = record.get("name")
        if not isinstance(name, str):
            errors.append(f"{case_name}: expected {record_path}.name to be a string")
        elif name in by_name:
            errors.append(f"{case_name}: duplicate {label} record {name!r}")
        else:
            by_name[name] = record

        if "location" in record:
            expect_location_span_coherent(
                errors,
                case_name,
                f"{record_path}.location",
                record["location"],
            )
    return by_name


def expect_record_file_facts(
    errors,
    case_name,
    path,
    record,
    file_path,
    *,
    package_relative=True,
):
    expected_size = None
    expected = None
    if package_relative and record.get("exists") is True and file_path.is_file():
        expected_size = file_path.stat().st_size
        expected = sha256_file(file_path)
    expect_equal(
        errors,
        case_name,
        f"{path}.sizeBytes",
        record.get("sizeBytes"),
        expected_size,
    )
    expect_equal(errors, case_name, f"{path}.sha256", record.get("sha256"), expected)


def expect_root_file_contract(errors, case_name, package, root_files):
    by_name = records_by_name(errors, case_name, "rootFiles", root_files, "root file")
    names = sorted(by_name)
    expected_names = sorted(EXPECTED_ROOT_FILES)
    if names != expected_names:
        errors.append(
            f"{case_name}: expected root file records {expected_names!r}, got {names!r}"
        )

    for name, expected_path in EXPECTED_ROOT_FILES.items():
        record = by_name.get(name)
        if record is not None:
            expect_equal(
                errors,
                case_name,
                f"rootFiles.{name}.path",
                record.get("path"),
                expected_path,
            )
            provenance = expect_object(
                errors,
                case_name,
                f"rootFiles.{name}.provenance",
                record.get("provenance"),
            )
            expect_equal(
                errors,
                case_name,
                f"rootFiles.{name}.provenance.kind",
                provenance.get("kind"),
                "packageRootFile",
            )
            expect_equal(
                errors,
                case_name,
                f"rootFiles.{name}.provenance.source",
                provenance.get("source"),
                "packageRoot",
            )
            expect_record_file_facts(
                errors,
                case_name,
                f"rootFiles.{name}",
                record,
                package / expected_path,
            )
            expect_location_spans_file(
                errors,
                case_name,
                f"rootFiles.{name}.location",
                record.get("location"),
                package / expected_path,
            )


def expect_artifact_contract(errors, case_name, package, summary, artifacts, manifest):
    by_name = records_by_name(errors, case_name, "artifacts", artifacts, "artifact")
    names = set(by_name)
    if "nativeBinaryStatus" in names:
        errors.append(f"{case_name}: nativeBinaryStatus is metadata, not an artifact")

    expect_package_summary_manifest_contract(
        errors,
        case_name,
        summary,
        manifest,
        artifact_count=len(artifacts),
        debug_artifact_names=names,
    )

    manifest_artifacts = manifest.get("artifacts")
    if not isinstance(manifest_artifacts, dict):
        return

    manifest_names = expected_manifest_artifact_names(manifest)
    if names != manifest_names:
        errors.append(
            f"{case_name}: expected artifact records {sorted(manifest_names)!r}, "
            f"got {sorted(names)!r}"
        )

    for name, expected_path in manifest_artifacts.items():
        if name == "nativeBinaryStatus":
            continue
        record = by_name.get(name)
        if record is not None:
            expect_equal(
                errors,
                case_name,
                f"artifacts.{name}.path",
                record.get("path"),
                expected_path,
            )
            provenance = expect_object(
                errors,
                case_name,
                f"artifacts.{name}.provenance",
                record.get("provenance"),
            )
            expect_equal(
                errors,
                case_name,
                f"artifacts.{name}.provenance.kind",
                provenance.get("kind"),
                "manifestArtifact",
            )
            expect_equal(
                errors,
                case_name,
                f"artifacts.{name}.provenance.source",
                provenance.get("source"),
                "manifest.artifacts",
            )
            expect_equal(
                errors,
                case_name,
                f"artifacts.{name}.provenance.manifestKey",
                provenance.get("manifestKey"),
                name,
            )
            expect_artifact_path_identity(
                errors,
                case_name,
                f"artifacts.{name}",
                record,
            )
            expect_record_file_facts(
                errors,
                case_name,
                f"artifacts.{name}",
                record,
                package / expected_path,
                package_relative=record.get("packageRelative") is True,
            )
            expect_location_overlaps_text(
                errors,
                case_name,
                f"artifacts.{name}.location",
                record.get("location"),
                package / "manifest.json",
                json.dumps(expected_path),
            )


def expect_reflection_summary_contract(errors, case_name, summary, reflection):
    if "module" in reflection:
        expect_equal(
            errors,
            case_name,
            "reflection.module",
            reflection["module"],
            summary.get("module"),
        )
    if "target" in reflection:
        expect_equal(
            errors,
            case_name,
            "reflection.target",
            reflection["target"],
            summary.get("target"),
        )


def expect_package_artifact_requirements_contract(
    errors,
    case_name,
    package,
    payload,
    manifest,
):
    manifest_requirements = manifest.get("packageArtifactRequirements")
    if manifest_requirements is None:
        if "packageArtifactRequirements" in payload:
            errors.append(
                f"{case_name}: expected packageArtifactRequirements to be absent "
                "for legacy manifest"
            )
        return

    requirements = expect_object(
        errors,
        case_name,
        "packageArtifactRequirements",
        payload.get("packageArtifactRequirements"),
    )
    for field in (
        "target",
        "packageMode",
        "requiresNativeBinaryStatus",
        "allowsPlannedNativeBinary",
        "allowsPlannedNativeSourceEvidence",
    ):
        expect_equal(
            errors,
            case_name,
            f"packageArtifactRequirements.{field}",
            requirements.get(field),
            manifest_requirements[field],
        )

    required_artifacts = expect_array(
        errors,
        case_name,
        "packageArtifactRequirements.requiredPathArtifacts",
        requirements.get("requiredPathArtifacts"),
    )
    expect_equal(
        errors,
        case_name,
        "packageArtifactRequirements.requiredPathArtifacts.names",
        [record.get("name") for record in required_artifacts],
        manifest_requirements["requiredPathArtifacts"],
    )
    if "evidenceIds" in manifest_requirements:
        expect_equal(
            errors,
            case_name,
            "packageArtifactRequirements.evidenceIds",
            requirements.get("evidenceIds"),
            manifest_requirements["evidenceIds"],
        )
    elif "evidenceIds" in requirements:
        errors.append(
            f"{case_name}: expected packageArtifactRequirements.evidenceIds "
            "to be absent when manifest omits evidenceIds"
        )

    expect_location(
        errors,
        case_name,
        "packageArtifactRequirements.location",
        requirements.get("location"),
        "manifest.json",
        min_offset=1,
        min_length=1,
    )
    expect_location_text_equals(
        errors,
        case_name,
        "packageArtifactRequirements.targetLocation",
        requirements.get("targetLocation"),
        package / "manifest.json",
        json.dumps(manifest_requirements["target"]),
    )
    expect_location_text_equals(
        errors,
        case_name,
        "packageArtifactRequirements.packageModeLocation",
        requirements.get("packageModeLocation"),
        package / "manifest.json",
        json.dumps(manifest_requirements["packageMode"]),
    )
    expect_location(
        errors,
        case_name,
        "packageArtifactRequirements.requiredPathArtifactsLocation",
        requirements.get("requiredPathArtifactsLocation"),
        "manifest.json",
        min_offset=1,
        min_length=1,
    )
    if "evidenceIds" in manifest_requirements:
        expect_location(
            errors,
            case_name,
            "packageArtifactRequirements.evidenceIdsLocation",
            requirements.get("evidenceIdsLocation"),
            "manifest.json",
            min_offset=1,
            min_length=1,
        )
    elif "evidenceIdsLocation" in requirements:
        errors.append(
            f"{case_name}: expected packageArtifactRequirements.evidenceIdsLocation "
            "to be absent when manifest omits evidenceIds"
        )
    for index, artifact in enumerate(required_artifacts):
        expect_location_text_equals(
            errors,
            case_name,
            f"packageArtifactRequirements.requiredPathArtifacts[{index}].location",
            artifact.get("location"),
            package / "manifest.json",
            json.dumps(artifact.get("name")),
        )


def expect_artifact_requirements_projection_contract(
    errors,
    case_name,
    payload,
    manifest,
):
    projection = expect_object(
        errors,
        case_name,
        "artifactRequirementsProjection",
        payload.get("artifactRequirementsProjection"),
    )
    descriptor = expect_object(
        errors,
        case_name,
        "nativeArtifactDescriptor",
        payload.get("nativeArtifactDescriptor"),
    )
    has_requirements = isinstance(manifest.get("packageArtifactRequirements"), dict)
    descriptor_present = descriptor.get("artifactPresent") is True
    expected_basis = "legacy-missing-packageArtifactRequirements"
    if has_requirements:
        expected_basis = "recorded-packageArtifactRequirements"
    elif descriptor_present:
        expected_basis = "recorded-nativeArtifactDescriptor-health"

    expect_equal(
        errors,
        case_name,
        "artifactRequirementsProjection.basis",
        projection.get("basis"),
        expected_basis,
    )
    expect_equal(
        errors,
        case_name,
        "artifactRequirementsProjection.reportOnly",
        projection.get("reportOnly"),
        True,
    )
    expect_equal(
        errors,
        case_name,
        "artifactRequirementsProjection.packageArtifactRequirementsPresent",
        projection.get("packageArtifactRequirementsPresent"),
        has_requirements,
    )
    expect_equal(
        errors,
        case_name,
        "artifactRequirementsProjection.packageArtifactRequirementsSource",
        projection.get("packageArtifactRequirementsSource"),
        "manifest.packageArtifactRequirements" if has_requirements else None,
    )
    expected_native_status_match = None
    if has_requirements:
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
    expect_equal(
        errors,
        case_name,
        "artifactRequirementsProjection.nativeBinaryStatusMatchesRequirements",
        projection.get("nativeBinaryStatusMatchesRequirements"),
        expected_native_status_match,
    )
    expect_equal(
        errors,
        case_name,
        "artifactRequirementsProjection.legacyManifestAbsence",
        projection.get("legacyManifestAbsence"),
        not has_requirements,
    )
    expect_equal(
        errors,
        case_name,
        "artifactRequirementsProjection.nativeArtifactDescriptorArtifactPresent",
        projection.get("nativeArtifactDescriptorArtifactPresent"),
        descriptor.get("artifactPresent"),
    )
    expect_equal(
        errors,
        case_name,
        "artifactRequirementsProjection.nativeArtifactDescriptorHealth",
        projection.get("nativeArtifactDescriptorHealth"),
        descriptor.get("health"),
    )
    expect_equal(
        errors,
        case_name,
        "artifactRequirementsProjection.nativeArtifactDescriptorPath",
        projection.get("nativeArtifactDescriptorPath"),
        descriptor.get("path"),
    )


def read_artifact_json(package, manifest, artifact_name):
    artifact_path = manifest.get("artifacts", {}).get(artifact_name)
    if not isinstance(artifact_path, str):
        return None
    path = package_path(package, artifact_path)
    if not path.is_file():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def target_record(records, target):
    for record in records or []:
        if isinstance(record, dict) and record.get("target") == target:
            return record
    return {}


def first_nonempty_string_array(*values):
    for value in values:
        if isinstance(value, list) and len(value) > 0:
            return value
    return None


def first_present(*values):
    for value in values:
        if value is not None:
            return value
    return None


TARGET_LEGALIZATION_TOOL_FIELD_PAIRS = (
    ("requiredToolCount", "selectedTargetRequiredToolCount", "requiredToolCount"),
    ("missingToolCount", "selectedTargetMissingToolCount", "missingToolCount"),
    ("requiredToolIds", "selectedTargetRequiredToolIds", "requiredToolIds"),
    ("missingToolIds", "selectedTargetMissingToolIds", "missingToolIds"),
    (
        "optionalNativeToolMissing",
        "selectedTargetOptionalNativeToolMissing",
        "optionalNativeToolMissing",
    ),
    (
        "optionalNativeToolStatus",
        "selectedTargetOptionalNativeToolStatus",
        "optionalNativeToolStatus",
    ),
    (
        "toolRequirementEvidenceIds",
        "selectedTargetToolRequirementEvidenceIds",
        "toolRequirementEvidenceIds",
    ),
)


def target_tool_sidecars_drift(left, right):
    for field, _, _ in TARGET_LEGALIZATION_TOOL_FIELD_PAIRS:
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
    if not manifest_tool_requirements.get("present") or not sidecar.get(
        "artifactExists"
    ):
        return None
    for field, _, _ in TARGET_LEGALIZATION_TOOL_FIELD_PAIRS:
        if sidecar.get(field) is None or sidecar.get(
            field
        ) != manifest_tool_requirements.get(field):
            return False
    return True


def expected_target_legalization_health(evidence):
    checks = evidence.get("checks", {})
    for name in (
        "manifestToolRequirementsTargetMatchesPackage",
        "manifestToolRequirementsPackageModeMatchesRequirements",
        "debugMetadataTargetMatchesPackage",
        "targetExplanationTargetMatchesPackage",
        "debugMetadataPackageModeMatchesRequirements",
        "targetExplanationPackageModeMatchesRequirements",
        "debugMetadataToolRequirementsMatchManifest",
        "targetExplanationToolRequirementsMatchManifest",
    ):
        if checks.get(name) is False:
            return "drift"
    if target_tool_sidecars_drift(
        evidence.get("debugMetadata", {}),
        evidence.get("targetExplanation", {}),
    ):
        return "drift"
    for sidecar_name in ("debugMetadata", "targetExplanation"):
        sidecar = evidence.get(sidecar_name, {})
        if sidecar.get("artifactPresent") and (
            not sidecar.get("artifactExists")
            or sidecar.get("target") is None
            or sidecar.get("packageMode") is None
            or not sidecar.get("legalizationCoreEvidenceIds")
        ):
            return "incomplete"
    if (
        checks.get("packageArtifactRequirementEvidenceIdsPresent") is False
        or checks.get("manifestToolRequirementEvidenceIdsPresent") is False
    ):
        return "partial"
    return "ok"


def expect_target_legalization_sidecar(
    errors,
    case_name,
    path,
    actual,
    artifact_record,
    expected_record,
):
    artifact_present = artifact_record is not None
    artifact_exists = artifact_present and artifact_record.get("exists") is True
    expect_equal(
        errors,
        case_name,
        f"{path}.artifactPresent",
        actual.get("artifactPresent"),
        artifact_present,
    )
    expect_equal(
        errors,
        case_name,
        f"{path}.artifactExists",
        actual.get("artifactExists"),
        artifact_exists,
    )
    if not artifact_exists:
        return
    expect_equal(
        errors,
        case_name,
        f"{path}.target",
        actual.get("target"),
        expected_record.get("target"),
    )
    expect_equal(
        errors,
        case_name,
        f"{path}.packageMode",
        actual.get("packageMode"),
        expected_record.get("packageMode"),
    )
    expect_equal(
        errors,
        case_name,
        f"{path}.packageDecisionReason",
        actual.get("packageDecisionReason"),
        expected_record.get("packageDecisionReason"),
    )
    for field, _, _ in TARGET_LEGALIZATION_TOOL_FIELD_PAIRS:
        expect_equal(
            errors,
            case_name,
            f"{path}.{field}",
            actual.get(field),
            expected_record.get(field),
        )
    expect_equal(
        errors,
        case_name,
        f"{path}.legalizationCoreEvidenceIds",
        actual.get("legalizationCoreEvidenceIds"),
        expected_record.get("legalizationCoreEvidenceIds"),
    )
    expect_equal(
        errors,
        case_name,
        f"{path}.packageArtifactRequirementEvidenceIds",
        actual.get("packageArtifactRequirementEvidenceIds"),
        expected_record.get("packageArtifactRequirementEvidenceIds"),
    )


def expect_target_legalization_evidence_contract(
    errors,
    case_name,
    package,
    payload,
    manifest,
):
    evidence = expect_object(
        errors,
        case_name,
        "targetLegalizationEvidence",
        payload.get("targetLegalizationEvidence"),
    )
    artifacts = expect_array(errors, case_name, "artifacts", payload.get("artifacts"))
    artifact_records = {
        record.get("name"): record for record in artifacts if isinstance(record, dict)
    }
    target = payload.get("summary", {}).get("target")

    debug_doc = read_artifact_json(package, manifest, "debugMetadata")
    debug_decision = (debug_doc or {}).get("targetDecision", {})
    debug_summary = target_record(
        (debug_doc or {}).get("targetCapabilities", {}).get("summaries", []),
        debug_decision.get("selectedTarget"),
    )
    expected_debug = {
        "target": debug_decision.get("selectedTarget"),
        "packageMode": debug_decision.get("selectedTargetPackageMode"),
        "packageDecisionReason": debug_summary.get("packageDecisionReason"),
        "legalizationCoreEvidenceIds": debug_decision.get(
            "selectedTargetLegalizationCoreEvidenceIds"
        ),
    }
    for field, decision_field, summary_field in TARGET_LEGALIZATION_TOOL_FIELD_PAIRS:
        expected_debug[field] = first_present(
            debug_decision.get(decision_field),
            debug_summary.get(summary_field),
        )
    expected_debug_requirement_ids = first_nonempty_string_array(
        debug_decision.get("packageArtifactRequirementEvidenceIds"),
        debug_summary.get("packageArtifactRequirementEvidenceIds"),
    )
    expected_debug["packageArtifactRequirementEvidenceIds"] = (
        expected_debug_requirement_ids
    )
    expect_target_legalization_sidecar(
        errors,
        case_name,
        "targetLegalizationEvidence.debugMetadata",
        evidence.get("debugMetadata", {}),
        artifact_records.get("debugMetadata"),
        expected_debug,
    )

    explanation_doc = read_artifact_json(package, manifest, "targetExplanation")
    explanation_record = target_record(
        (explanation_doc or {}).get("targets", []), target
    )
    explanation_record = dict(explanation_record)
    requirements = manifest.get("packageArtifactRequirements")
    manifest_requirement_ids = (
        requirements.get("evidenceIds") if isinstance(requirements, dict) else None
    )
    expected_requirement_ids = first_nonempty_string_array(
        manifest_requirement_ids,
        expected_debug_requirement_ids,
        explanation_record.get("packageArtifactRequirementEvidenceIds"),
    )
    expect_target_legalization_sidecar(
        errors,
        case_name,
        "targetLegalizationEvidence.targetExplanation",
        evidence.get("targetExplanation", {}),
        artifact_records.get("targetExplanation"),
        explanation_record,
    )

    manifest_tool_requirements = manifest.get("targetLegalizationToolRequirements")
    actual_manifest_tool_requirements = expect_object(
        errors,
        case_name,
        "targetLegalizationEvidence.manifestToolRequirements",
        evidence.get("manifestToolRequirements"),
    )
    if isinstance(manifest_tool_requirements, dict):
        expect_equal(
            errors,
            case_name,
            "targetLegalizationEvidence.manifestToolRequirements.present",
            actual_manifest_tool_requirements.get("present"),
            True,
        )
        for field in ("target", "packageMode"):
            expect_equal(
                errors,
                case_name,
                f"targetLegalizationEvidence.manifestToolRequirements.{field}",
                actual_manifest_tool_requirements.get(field),
                manifest_tool_requirements.get(field),
            )
        for field, _, _ in TARGET_LEGALIZATION_TOOL_FIELD_PAIRS:
            expect_equal(
                errors,
                case_name,
                f"targetLegalizationEvidence.manifestToolRequirements.{field}",
                actual_manifest_tool_requirements.get(field),
                manifest_tool_requirements.get(field),
            )
    else:
        expect_equal(
            errors,
            case_name,
            "targetLegalizationEvidence.manifestToolRequirements.present",
            actual_manifest_tool_requirements.get("present"),
            False,
        )

    if isinstance(requirements, dict):
        expect_equal(
            errors,
            case_name,
            "targetLegalizationEvidence.packageMode",
            evidence.get("packageMode"),
            requirements.get("packageMode"),
        )
        expect_equal(
            errors,
            case_name,
            "targetLegalizationEvidence.packageModeSource",
            evidence.get("packageModeSource"),
            "manifest.packageArtifactRequirements",
        )
        expect_equal(
            errors,
            case_name,
            "targetLegalizationEvidence.packageArtifactRequirementEvidenceIds",
            evidence.get("packageArtifactRequirementEvidenceIds"),
            expected_requirement_ids,
        )
        expect_equal(
            errors,
            case_name,
            "targetLegalizationEvidence.checks.packageArtifactRequirementEvidenceIdsPresent",
            evidence.get("checks", {}).get(
                "packageArtifactRequirementEvidenceIdsPresent"
            ),
            expected_requirement_ids is not None,
        )
        missing_evidence = evidence.get("missingEvidence", [])
        if (
            expected_requirement_ids is None
            and "packageArtifactRequirementEvidenceIds" not in missing_evidence
        ):
            errors.append(
                f"{case_name}: expected targetLegalizationEvidence.missingEvidence "
                "to include 'packageArtifactRequirementEvidenceIds'"
            )
    else:
        expect_equal(
            errors,
            case_name,
            "targetLegalizationEvidence.packageArtifactRequirementEvidenceIds",
            evidence.get("packageArtifactRequirementEvidenceIds"),
            None,
        )
        expect_equal(
            errors,
            case_name,
            "targetLegalizationEvidence.checks.packageArtifactRequirementEvidenceIdsPresent",
            evidence.get("checks", {}).get(
                "packageArtifactRequirementEvidenceIdsPresent"
            ),
            None,
        )

    checks = evidence.get("checks", {})
    if isinstance(manifest_tool_requirements, dict):
        expect_equal(
            errors,
            case_name,
            "targetLegalizationEvidence.checks.manifestToolRequirementsTargetMatchesPackage",
            checks.get("manifestToolRequirementsTargetMatchesPackage"),
            manifest_tool_requirements.get("target") == target,
        )
        if isinstance(requirements, dict):
            expect_equal(
                errors,
                case_name,
                "targetLegalizationEvidence.checks.manifestToolRequirementsPackageModeMatchesRequirements",
                checks.get("manifestToolRequirementsPackageModeMatchesRequirements"),
                manifest_tool_requirements.get("packageMode")
                == requirements.get("packageMode"),
            )
        expect_equal(
            errors,
            case_name,
            "targetLegalizationEvidence.checks.manifestToolRequirementEvidenceIdsPresent",
            checks.get("manifestToolRequirementEvidenceIdsPresent"),
            bool(manifest_tool_requirements.get("toolRequirementEvidenceIds")),
        )
    for sidecar_name, expected_record in (
        ("debugMetadata", expected_debug),
        ("targetExplanation", explanation_record),
    ):
        target_value = expected_record.get("target")
        if target_value is not None:
            expect_equal(
                errors,
                case_name,
                f"targetLegalizationEvidence.checks.{sidecar_name}TargetMatchesPackage",
                checks.get(f"{sidecar_name}TargetMatchesPackage"),
                target_value == target,
            )
        mode = expected_record.get("packageMode")
        if isinstance(requirements, dict) and mode is not None:
            expect_equal(
                errors,
                case_name,
                f"targetLegalizationEvidence.checks.{sidecar_name}PackageModeMatchesRequirements",
                checks.get(f"{sidecar_name}PackageModeMatchesRequirements"),
                mode == requirements.get("packageMode"),
            )
        expect_equal(
            errors,
            case_name,
            f"targetLegalizationEvidence.checks.{sidecar_name}ToolRequirementsMatchManifest",
            checks.get(f"{sidecar_name}ToolRequirementsMatchManifest"),
            target_tool_sidecar_matches_manifest(
                actual_manifest_tool_requirements,
                evidence.get(sidecar_name, {}),
            ),
        )

    expect_equal(
        errors,
        case_name,
        "targetLegalizationEvidence.health",
        evidence.get("health"),
        expected_target_legalization_health(evidence),
    )


def expect_debug_artifacts_contract(errors, case_name, payload):
    debug_artifacts = expect_object(
        errors,
        case_name,
        "debugArtifacts",
        payload.get("debugArtifacts"),
    )
    checks = expect_object(
        errors,
        case_name,
        "debugArtifacts.checks",
        debug_artifacts.get("checks"),
    )
    summary = expect_object(errors, case_name, "summary", payload.get("summary"))
    artifacts = expect_array(errors, case_name, "artifacts", payload.get("artifacts"))
    names = {record.get("name") for record in artifacts if isinstance(record, dict)}
    debug_declared = "debugMetadata" in names
    source_map_declared = "hirSourceMap" in names
    debug_exists = (
        record_by_name(artifacts, "debugMetadata")["exists"]
        if debug_declared
        else False
    )
    source_map_exists = (
        record_by_name(artifacts, "hirSourceMap")["exists"]
        if source_map_declared
        else False
    )

    expect_equal(
        errors,
        case_name,
        "debugArtifacts.debugMetadataArtifactPresent",
        debug_artifacts.get("debugMetadataArtifactPresent"),
        debug_declared,
    )
    expect_equal(
        errors,
        case_name,
        "debugArtifacts.hirSourceMapArtifactPresent",
        debug_artifacts.get("hirSourceMapArtifactPresent"),
        source_map_declared,
    )
    expect_equal(
        errors,
        case_name,
        "debugArtifacts.debugMetadataExists",
        debug_artifacts.get("debugMetadataExists"),
        debug_exists,
    )
    expect_equal(
        errors,
        case_name,
        "debugArtifacts.hirSourceMapExists",
        debug_artifacts.get("hirSourceMapExists"),
        source_map_exists,
    )
    expect_equal(
        errors,
        case_name,
        "summary.debugArtifactsPresent",
        summary.get("debugArtifactsPresent"),
        debug_declared and source_map_declared,
    )

    if not debug_exists or not source_map_exists:
        expect_equal(
            errors,
            case_name,
            "debugArtifacts.health",
            debug_artifacts.get("health"),
            "incomplete",
        )
        for name, value in checks.items():
            expect_equal(
                errors,
                case_name,
                f"debugArtifacts.checks.{name}",
                value,
                None,
            )


def expect_debug_artifact_check(errors, case_name, payload, name, expected):
    expect_equal(
        errors,
        case_name,
        f"debugArtifacts.checks.{name}",
        payload["debugArtifacts"]["checks"][name],
        expected,
    )


def expect_vulkan_native_profile_contract(errors, case_name, payload):
    profile = expect_object(
        errors,
        case_name,
        "vulkanNativeProfile",
        payload.get("vulkanNativeProfile"),
    )
    checks = expect_object(
        errors,
        case_name,
        "vulkanNativeProfile.checks",
        profile.get("checks"),
    )
    summary = expect_object(errors, case_name, "summary", payload.get("summary"))
    artifacts = expect_array(errors, case_name, "artifacts", payload.get("artifacts"))
    names = {record.get("name") for record in artifacts if isinstance(record, dict)}
    is_vulkan = summary.get("target") == "vulkan"
    profile_declared = "nativeProfile" in names
    profile_exists = (
        record_by_name(artifacts, "nativeProfile")["exists"]
        if profile_declared
        else False
    )

    expect_equal(
        errors,
        case_name,
        "vulkanNativeProfile.applicable",
        profile.get("applicable"),
        is_vulkan,
    )
    expect_equal(
        errors,
        case_name,
        "vulkanNativeProfile.nativeProfileArtifactPresent",
        profile.get("nativeProfileArtifactPresent"),
        profile_declared,
    )
    expect_equal(
        errors,
        case_name,
        "vulkanNativeProfile.nativeProfileExists",
        profile.get("nativeProfileExists"),
        profile_exists,
    )

    if not is_vulkan:
        expect_equal(
            errors,
            case_name,
            "vulkanNativeProfile.health",
            profile.get("health"),
            "not-applicable",
        )
        for name, value in checks.items():
            expect_equal(
                errors,
                case_name,
                f"vulkanNativeProfile.checks.{name}",
                value,
                None,
            )
    elif not profile_exists:
        expect_equal(
            errors,
            case_name,
            "vulkanNativeProfile.health",
            profile.get("health"),
            "incomplete",
        )
        for name, value in checks.items():
            expect_equal(
                errors,
                case_name,
                f"vulkanNativeProfile.checks.{name}",
                value,
                None,
            )


def expect_native_artifact_descriptor_contract(errors, case_name, payload):
    descriptor = expect_object(
        errors,
        case_name,
        "nativeArtifactDescriptor",
        payload.get("nativeArtifactDescriptor"),
    )
    checks = expect_object(
        errors,
        case_name,
        "nativeArtifactDescriptor.checks",
        descriptor.get("checks"),
    )
    manifest = expect_object(errors, case_name, "manifest", payload.get("manifest"))
    manifest_artifacts = manifest.get("artifacts", {})
    if not isinstance(manifest_artifacts, dict):
        manifest_artifacts = {}
    artifacts = expect_array(errors, case_name, "artifacts", payload.get("artifacts"))
    names = {record.get("name") for record in artifacts if isinstance(record, dict)}
    descriptor_declared = "nativeArtifactDescriptor" in names
    descriptor_exists = (
        record_by_name(artifacts, "nativeArtifactDescriptor")["exists"]
        if descriptor_declared
        else False
    )
    descriptor_path = manifest_artifacts.get("nativeArtifactDescriptor")

    expect_equal(
        errors,
        case_name,
        "nativeArtifactDescriptor.artifactPresent",
        descriptor.get("artifactPresent"),
        descriptor_declared,
    )
    expect_equal(
        errors,
        case_name,
        "nativeArtifactDescriptor.descriptorExists",
        descriptor.get("descriptorExists"),
        descriptor_exists,
    )
    expect_equal(
        errors,
        case_name,
        "nativeArtifactDescriptor.path",
        descriptor.get("path"),
        descriptor_path,
    )
    if not descriptor_declared:
        expect_equal(
            errors,
            case_name,
            "nativeArtifactDescriptor.health",
            descriptor.get("health"),
            "not-present",
        )
        for name, value in checks.items():
            expect_equal(
                errors,
                case_name,
                f"nativeArtifactDescriptor.checks.{name}",
                value,
                None,
            )
    elif not descriptor_exists:
        expect_equal(
            errors,
            case_name,
            "nativeArtifactDescriptor.health",
            descriptor.get("health"),
            "incomplete",
        )


def expect_publication_contract(errors, case_name, package, payload):
    publication = expect_object(
        errors,
        case_name,
        "publication",
        payload.get("publication"),
    )
    sidecars = expect_array(
        errors,
        case_name,
        "publication.siblingSidecars",
        publication.get("siblingSidecars"),
    )
    parsed = parse_sidecar_path(package)
    expected_requested = parsed["requested"] if parsed else package
    expected_state = parsed["state"] if parsed else "published"

    expect_equal(
        errors,
        case_name,
        "publication.state",
        publication.get("state"),
        expected_state,
    )
    expect_equal(
        errors,
        case_name,
        "publication.requestedPath",
        publication.get("requestedPath"),
        expected_requested.as_posix(),
    )
    expect_equal(
        errors,
        case_name,
        "publication.siblingSidecarCount",
        publication.get("siblingSidecarCount"),
        len(sidecars),
    )

    if parsed:
        expect_equal(
            errors,
            case_name,
            "publication.sidecarKind",
            publication.get("sidecarKind"),
            parsed["kind"],
        )
        expect_equal(
            errors,
            case_name,
            "publication.sidecarToken",
            publication.get("sidecarToken"),
            parsed["token"],
        )
        expect_equal(
            errors,
            case_name,
            "publication.sidecarAttempt",
            publication.get("sidecarAttempt"),
            parsed["attempt"],
        )
    else:
        expect_equal(
            errors,
            case_name,
            "publication.sidecarKind",
            publication.get("sidecarKind"),
            None,
        )
        expect_equal(
            errors,
            case_name,
            "publication.sidecarToken",
            publication.get("sidecarToken"),
            None,
        )
        expect_equal(
            errors,
            case_name,
            "publication.sidecarAttempt",
            publication.get("sidecarAttempt"),
            None,
        )

    for index, sidecar in enumerate(sidecars):
        if "\\" in sidecar.get("path", ""):
            errors.append(
                f"{case_name}: expected publication sidecar path to use '/' "
                f"separators at index {index}"
            )
        if sidecar.get("kind") not in {"staging", "previous"}:
            errors.append(
                f"{case_name}: expected publication sidecar kind at index {index}"
            )
        if not sidecar.get("token"):
            errors.append(
                f"{case_name}: expected publication sidecar token at index {index}"
            )
        if not isinstance(sidecar.get("attempt"), int):
            errors.append(
                f"{case_name}: expected publication sidecar attempt at index {index}"
            )
        if not isinstance(sidecar.get("directory"), bool):
            errors.append(
                f"{case_name}: expected publication sidecar directory flag at "
                f"index {index}"
            )


def expect_json_contract(errors, case_name, payload, package):
    if not isinstance(payload, dict):
        errors.append(f"{case_name}: expected inspect JSON output to be an object")
        return

    expect_equal(errors, case_name, "schemaVersion", payload.get("schemaVersion"), 1)
    expect_package_path_contract(
        errors,
        case_name,
        payload.get("packagePath"),
        package,
    )
    expect_equal(
        errors,
        case_name,
        "packageFormat",
        payload.get("packageFormat"),
        "directory",
    )

    summary = expect_object(errors, case_name, "summary", payload.get("summary"))
    manifest = expect_object(errors, case_name, "manifest", payload.get("manifest"))
    reflection = expect_object(
        errors,
        case_name,
        "reflection",
        payload.get("reflection"),
    )
    root_files = expect_array(errors, case_name, "rootFiles", payload.get("rootFiles"))
    artifacts = expect_array(errors, case_name, "artifacts", payload.get("artifacts"))

    expect_root_file_contract(errors, case_name, package, root_files)
    expect_artifact_contract(errors, case_name, package, summary, artifacts, manifest)
    expect_reflection_summary_contract(errors, case_name, summary, reflection)
    expect_package_artifact_requirements_contract(
        errors,
        case_name,
        package,
        payload,
        manifest,
    )
    expect_artifact_requirements_projection_contract(
        errors,
        case_name,
        payload,
        manifest,
    )
    if "targetLegalizationEvidence" in payload or isinstance(
        manifest.get("packageArtifactRequirements"), dict
    ):
        expect_target_legalization_evidence_contract(
            errors,
            case_name,
            package,
            payload,
            manifest,
        )
    expect_debug_artifacts_contract(errors, case_name, payload)
    expect_vulkan_native_profile_contract(errors, case_name, payload)
    expect_native_artifact_descriptor_contract(errors, case_name, payload)
    expect_publication_contract(errors, case_name, package, payload)


def expect_success(root, cglc, tmp_dir, case_name, package, check):
    result = run_inspect(cglc, package)
    errors = []
    if result.returncode != 0:
        return [
            f"{case_name}: expected inspect success, got "
            f"{result.stderr}{result.stdout}".strip()
        ]
    if result.stderr:
        errors.append(f"{case_name}: expected no diagnostics, got {result.stderr!r}")
    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        return [f"{case_name}: inspect output is not JSON: {exc}: {result.stdout!r}"]
    errors.extend(validate_schema(root, tmp_dir, case_name, result.stdout))
    expect_json_contract(errors, case_name, payload, package)
    try:
        errors.extend(check(package, payload))
    except (KeyError, TypeError) as exc:
        errors.append(f"{case_name}: failed to inspect expected JSON shape: {exc}")
    return errors


def expect_failure(
    cglc,
    case_name,
    package,
    expected,
    json_output=True,
    expected_file=None,
    require_precise_location=False,
):
    result = run_inspect(cglc, package, json_output=json_output)
    output = result.stderr + result.stdout
    errors = []
    matching_diagnostic = None
    if result.returncode == 0:
        errors.append(f"{case_name}: expected inspect failure")
    if json_output:
        if result.stderr:
            errors.append(
                f"{case_name}: package inspect --json must not emit "
                f"human diagnostics on stderr: {result.stderr!r}"
            )
        try:
            payload = json.loads(result.stdout)
        except json.JSONDecodeError as exc:
            errors.append(
                f"{case_name}: inspect failure output is not JSON: "
                f"{exc}: {result.stdout!r}"
            )
            payload = {}
        diagnostics = payload.get("diagnostics")
        if isinstance(diagnostics, list):
            for diagnostic in diagnostics:
                if not isinstance(diagnostic, dict):
                    continue
                code = diagnostic.get("code")
                message = diagnostic.get("message")
                if expected in {code, message} or (
                    isinstance(message, str) and expected in message
                ):
                    matching_diagnostic = diagnostic
                    break
        output = result.stdout

    if matching_diagnostic is None and expected not in output:
        errors.append(
            f"{case_name}: expected error substring {expected!r}; "
            f"got {output.strip()!r}"
        )
    if expected_file is not None:
        expected_path = Path(expected_file)
        if matching_diagnostic is not None:
            location = matching_diagnostic.get("location", {})
            location_file = location.get("file") if isinstance(location, dict) else None
            if not isinstance(location_file, str) or (
                expected_path.name not in location_file
            ):
                errors.append(
                    f"{case_name}: expected diagnostic for {expected!r} to "
                    f"reference {expected_path.name!r}; got "
                    f"{location_file!r}"
                )
            if (
                require_precise_location
                and isinstance(location, dict)
                and location.get("line") == 1
                and location.get("column") == 1
            ):
                errors.append(
                    f"{case_name}: expected diagnostic to point past file "
                    f"start; got {location!r}"
                )
        else:
            matching_line = next(
                (line for line in output.splitlines() if expected in line),
                "",
            )
            if expected_path.name not in matching_line:
                errors.append(
                    f"{case_name}: expected diagnostic for {expected!r} to "
                    f"reference {expected_path.name!r}; got "
                    f"{matching_line!r}"
                )
            if require_precise_location and ":1:1:" in matching_line:
                errors.append(
                    f"{case_name}: expected diagnostic to point past file "
                    f"start; got {matching_line!r}"
                )
    return errors


def expect_args_failure(cglc, case_name, args, expected):
    result = subprocess.run(
        [str(cglc), *args],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    output = result.stderr + result.stdout
    errors = []
    if result.returncode == 0:
        errors.append(f"{case_name}: expected command failure")
    if expected not in output:
        errors.append(
            f"{case_name}: expected output substring {expected!r}; "
            f"got {output.strip()!r}"
        )
    return errors


def check_valid_planned(package, payload):
    errors = []
    expect_equal(errors, "valid-planned", "schemaVersion", payload["schemaVersion"], 1)
    expect_equal(
        errors,
        "valid-planned",
        "summary.module",
        payload["summary"]["module"],
        "StorageBufferComputeShader",
    )
    expect_equal(
        errors,
        "valid-planned",
        "summary.target",
        payload["summary"]["target"],
        "directx",
    )
    expect_equal(
        errors,
        "valid-planned",
        "summary.nativeBinaryStatus",
        payload["summary"]["nativeBinaryStatus"],
        "planned",
    )
    expect_equal(
        errors,
        "valid-planned",
        "summary.artifactCount",
        payload["summary"]["artifactCount"],
        5,
    )
    expect_equal(
        errors,
        "valid-planned",
        "summary.debugArtifactsPresent",
        payload["summary"]["debugArtifactsPresent"],
        True,
    )
    expect_equal(
        errors,
        "valid-planned",
        "debugArtifacts.health",
        payload["debugArtifacts"]["health"],
        "ok",
    )
    for check_name in (
        "hirSourceLocationsMatch",
        "sourceMapUnfiltered",
        "sourceMapUnpaged",
        "sourceMapRecordsDisabled",
        "sourceMapCategoryCountsConsistent",
        "recordsTotalCountMatchesCategoryCounts",
    ):
        expect_debug_artifact_check(
            errors,
            "valid-planned",
            payload,
            check_name,
            True,
        )
    expect_equal(
        errors,
        "valid-planned",
        "rootFiles.manifest.exists",
        record_by_name(payload["rootFiles"], "manifest")["exists"],
        True,
    )
    expect_location(
        errors,
        "valid-planned",
        "rootFiles.manifest.location",
        record_by_name(payload["rootFiles"], "manifest")["location"],
        "manifest.json",
        expected_offset=0,
        min_length=1,
    )
    expect_location_overlaps_text(
        errors,
        "valid-planned",
        "rootFiles.manifest.location",
        record_by_name(payload["rootFiles"], "manifest")["location"],
        package / "manifest.json",
        '"schemaVersion"',
    )
    expect_location_overlaps_text(
        errors,
        "valid-planned",
        "rootFiles.reflection.location",
        record_by_name(payload["rootFiles"], "reflection")["location"],
        package / "reflection.json",
        '"entryPoints"',
    )
    expect_location_overlaps_text(
        errors,
        "valid-planned",
        "rootFiles.diagnostics.location",
        record_by_name(payload["rootFiles"], "diagnostics")["location"],
        package / "diagnostics.json",
        '"diagnostics"',
    )
    backend_source = record_by_name(payload["artifacts"], "backendSource")
    expect_equal(
        errors,
        "valid-planned",
        "artifacts.backendSource.exists",
        backend_source["exists"],
        True,
    )
    expect_location(
        errors,
        "valid-planned",
        "artifacts.backendSource.location",
        backend_source["location"],
        "manifest.json",
        min_offset=1,
        min_length=1,
    )
    expect_location_overlaps_text(
        errors,
        "valid-planned",
        "artifacts.backendSource.location",
        backend_source["location"],
        package / "manifest.json",
        json.dumps(backend_source["path"]),
    )
    debug_metadata = record_by_name(payload["artifacts"], "debugMetadata")
    expect_location_overlaps_text(
        errors,
        "valid-planned",
        "artifacts.debugMetadata.location",
        debug_metadata["location"],
        package / "manifest.json",
        json.dumps(debug_metadata["path"]),
    )
    target_explanation = record_by_name(payload["artifacts"], "targetExplanation")
    expect_equal(
        errors,
        "valid-planned",
        "artifacts.targetExplanation.exists",
        target_explanation["exists"],
        True,
    )
    expect_location_overlaps_text(
        errors,
        "valid-planned",
        "artifacts.targetExplanation.location",
        target_explanation["location"],
        package / "manifest.json",
        json.dumps(target_explanation["path"]),
    )
    expect_equal(
        errors,
        "valid-planned",
        "artifacts.nativeBinary.exists",
        record_by_name(payload["artifacts"], "nativeBinary")["exists"],
        False,
    )
    return errors


def check_valid_emitted(_package, payload):
    errors = []
    expect_equal(
        errors,
        "valid-emitted",
        "summary.nativeBinaryStatus",
        payload["summary"]["nativeBinaryStatus"],
        "emitted",
    )
    expect_equal(
        errors,
        "valid-emitted",
        "artifacts.nativeBinary.exists",
        record_by_name(payload["artifacts"], "nativeBinary")["exists"],
        True,
    )
    return errors


def check_legacy_no_artifact_requirements(
    _package,
    payload,
    case_name="legacy-no-artifact-requirements",
):
    errors = []
    if "packageArtifactRequirements" in payload:
        errors.append(
            f"{case_name}: expected inspect output to omit "
            "packageArtifactRequirements for legacy manifest"
        )
    expect_equal(
        errors,
        case_name,
        "summary.nativeBinaryStatus",
        payload["summary"]["nativeBinaryStatus"],
        "planned",
    )
    projection = payload["artifactRequirementsProjection"]
    expect_equal(
        errors,
        case_name,
        "artifactRequirementsProjection.basis",
        projection["basis"],
        "recorded-nativeArtifactDescriptor-health",
    )
    expect_equal(
        errors,
        case_name,
        "artifactRequirementsProjection.legacyManifestAbsence",
        projection["legacyManifestAbsence"],
        True,
    )
    expect_equal(
        errors,
        case_name,
        "artifactRequirementsProjection.nativeArtifactDescriptorHealth",
        projection["nativeArtifactDescriptorHealth"],
        "ok",
    )
    expect_equal(
        errors,
        case_name,
        "nativeArtifactDescriptor.health",
        payload["nativeArtifactDescriptor"]["health"],
        "ok",
    )
    return errors


def check_legacy_missing_artifact_requirements(_package, payload):
    errors = []
    if "packageArtifactRequirements" in payload:
        errors.append(
            "legacy-missing-artifact-requirements: expected inspect output to omit "
            "packageArtifactRequirements for legacy manifest"
        )
    projection = payload["artifactRequirementsProjection"]
    expect_equal(
        errors,
        "legacy-missing-artifact-requirements",
        "artifactRequirementsProjection.basis",
        projection["basis"],
        "legacy-missing-packageArtifactRequirements",
    )
    expect_equal(
        errors,
        "legacy-missing-artifact-requirements",
        "artifactRequirementsProjection.reportOnly",
        projection["reportOnly"],
        True,
    )
    expect_equal(
        errors,
        "legacy-missing-artifact-requirements",
        "artifactRequirementsProjection.packageArtifactRequirementsPresent",
        projection["packageArtifactRequirementsPresent"],
        False,
    )
    expect_equal(
        errors,
        "legacy-missing-artifact-requirements",
        "artifactRequirementsProjection.nativeArtifactDescriptorHealth",
        projection["nativeArtifactDescriptorHealth"],
        "not-present",
    )
    return errors


def add_sidecar_package_requirement_evidence(package, manifest, evidence_ids):
    debug_path = package_path(package, manifest["artifacts"]["debugMetadata"])
    debug_metadata = json.loads(debug_path.read_text(encoding="utf-8"))
    decision = debug_metadata["targetDecision"]
    decision["packageArtifactRequirementEvidenceIds"] = list(evidence_ids)
    selected_target = decision["selectedTarget"]
    for summary in debug_metadata["targetCapabilities"]["summaries"]:
        if summary.get("target") == selected_target:
            summary["packageArtifactRequirementEvidenceIds"] = list(evidence_ids)
    write_json(debug_path, debug_metadata)

    explanation_path = package_path(
        package,
        manifest["artifacts"]["targetExplanation"],
    )
    explanation = json.loads(explanation_path.read_text(encoding="utf-8"))
    for record in explanation["targets"]:
        if record.get("target") == manifest["target"]:
            record["packageArtifactRequirementEvidenceIds"] = list(evidence_ids)
    write_json(explanation_path, explanation)


def check_legacy_sidecar_requirement_evidence_report_only(_package, payload):
    errors = []
    if "packageArtifactRequirements" in payload:
        errors.append(
            "legacy-sidecar-requirement-evidence: expected inspect output to omit "
            "packageArtifactRequirements for legacy manifest"
        )
    projection = payload["artifactRequirementsProjection"]
    expect_equal(
        errors,
        "legacy-sidecar-requirement-evidence",
        "artifactRequirementsProjection.basis",
        projection["basis"],
        "legacy-missing-packageArtifactRequirements",
    )
    expect_equal(
        errors,
        "legacy-sidecar-requirement-evidence",
        "artifactRequirementsProjection.reportOnly",
        projection["reportOnly"],
        True,
    )
    expect_equal(
        errors,
        "legacy-sidecar-requirement-evidence",
        "artifactRequirementsProjection.packageArtifactRequirementsPresent",
        projection["packageArtifactRequirementsPresent"],
        False,
    )
    evidence = payload["targetLegalizationEvidence"]
    expect_equal(
        errors,
        "legacy-sidecar-requirement-evidence",
        "targetLegalizationEvidence.packageArtifactRequirementEvidenceIds",
        evidence["packageArtifactRequirementEvidenceIds"],
        None,
    )
    expect_equal(
        errors,
        "legacy-sidecar-requirement-evidence",
        "targetLegalizationEvidence.checks.packageArtifactRequirementEvidenceIdsPresent",
        evidence["checks"]["packageArtifactRequirementEvidenceIdsPresent"],
        None,
    )
    if "packageArtifactRequirementEvidenceIds" in evidence.get("missingEvidence", []):
        errors.append(
            "legacy-sidecar-requirement-evidence: legacy manifests must not report "
            "packageArtifactRequirementEvidenceIds as missing recorded evidence"
        )
    return errors


def check_recorded_artifact_requirements(_package, payload):
    errors = []
    projection = payload["artifactRequirementsProjection"]
    expect_equal(
        errors,
        "recorded-artifact-requirements",
        "artifactRequirementsProjection.basis",
        projection["basis"],
        "recorded-packageArtifactRequirements",
    )
    expect_equal(
        errors,
        "recorded-artifact-requirements",
        "artifactRequirementsProjection.packageArtifactRequirementsPresent",
        projection["packageArtifactRequirementsPresent"],
        True,
    )
    expect_equal(
        errors,
        "recorded-artifact-requirements",
        "artifactRequirementsProjection.packageArtifactRequirementsSource",
        projection["packageArtifactRequirementsSource"],
        "manifest.packageArtifactRequirements",
    )
    expect_equal(
        errors,
        "recorded-artifact-requirements",
        "artifactRequirementsProjection.legacyManifestAbsence",
        projection["legacyManifestAbsence"],
        False,
    )
    return errors


def check_recorded_sidecar_requirement_evidence(evidence_ids):
    def check(_package, payload):
        errors = []
        projection = payload["artifactRequirementsProjection"]
        expect_equal(
            errors,
            "recorded-sidecar-requirement-evidence",
            "artifactRequirementsProjection.basis",
            projection["basis"],
            "recorded-packageArtifactRequirements",
        )
        expect_equal(
            errors,
            "recorded-sidecar-requirement-evidence",
            "artifactRequirementsProjection.packageArtifactRequirementsPresent",
            projection["packageArtifactRequirementsPresent"],
            True,
        )
        evidence = payload["targetLegalizationEvidence"]
        expect_equal(
            errors,
            "recorded-sidecar-requirement-evidence",
            "targetLegalizationEvidence.packageModeSource",
            evidence["packageModeSource"],
            "manifest.packageArtifactRequirements",
        )
        expect_equal(
            errors,
            "recorded-sidecar-requirement-evidence",
            "targetLegalizationEvidence.packageArtifactRequirementEvidenceIds",
            evidence["packageArtifactRequirementEvidenceIds"],
            evidence_ids,
        )
        expect_equal(
            errors,
            "recorded-sidecar-requirement-evidence",
            "targetLegalizationEvidence.checks.packageArtifactRequirementEvidenceIdsPresent",
            evidence["checks"]["packageArtifactRequirementEvidenceIdsPresent"],
            True,
        )
        if "packageArtifactRequirementEvidenceIds" in evidence.get(
            "missingEvidence", []
        ):
            errors.append(
                "recorded-sidecar-requirement-evidence: recorded sidecar evidence "
                "must not be reported as missing"
            )
        return errors

    return check


def check_recorded_requirements_drift(
    case_name,
    expected_package_mode,
    expected_required_artifacts,
):
    def check(_package, payload):
        errors = []
        requirements = payload["packageArtifactRequirements"]
        evidence = payload["targetLegalizationEvidence"]
        checks = evidence["checks"]
        expect_equal(
            errors,
            case_name,
            "artifactRequirementsProjection.basis",
            payload["artifactRequirementsProjection"]["basis"],
            "recorded-packageArtifactRequirements",
        )
        expect_equal(
            errors,
            case_name,
            "packageArtifactRequirements.packageMode",
            requirements["packageMode"],
            expected_package_mode,
        )
        expect_equal(
            errors,
            case_name,
            "packageArtifactRequirements.requiredPathArtifacts.names",
            [record.get("name") for record in requirements["requiredPathArtifacts"]],
            expected_required_artifacts,
        )
        expect_equal(
            errors,
            case_name,
            "targetLegalizationEvidence.health",
            evidence["health"],
            "drift",
        )
        expect_equal(
            errors,
            case_name,
            "targetLegalizationEvidence.checks.debugMetadataPackageModeMatchesRequirements",
            checks["debugMetadataPackageModeMatchesRequirements"],
            False,
        )
        expect_equal(
            errors,
            case_name,
            "targetLegalizationEvidence.checks.targetExplanationPackageModeMatchesRequirements",
            checks["targetExplanationPackageModeMatchesRequirements"],
            False,
        )
        return errors

    return check


def check_recorded_planned_status_policy_drift(_package, payload):
    case_name = "recorded-planned-status-policy-drift"
    errors = []
    projection = payload["artifactRequirementsProjection"]
    descriptor = payload["nativeArtifactDescriptor"]

    expect_equal(
        errors,
        case_name,
        "summary.nativeBinaryStatus",
        payload["summary"]["nativeBinaryStatus"],
        "planned",
    )
    expect_equal(
        errors,
        case_name,
        "artifactRequirementsProjection.nativeBinaryStatusMatchesRequirements",
        projection["nativeBinaryStatusMatchesRequirements"],
        False,
    )
    expect_equal(
        errors,
        case_name,
        "packageArtifactRequirements.allowsPlannedNativeBinary",
        payload["packageArtifactRequirements"]["allowsPlannedNativeBinary"],
        False,
    )
    expect_equal(
        errors,
        case_name,
        "nativeArtifactDescriptor.nativeBinaryStatus",
        descriptor["nativeBinaryStatus"],
        "planned",
    )
    expect_equal(
        errors,
        case_name,
        "nativeArtifactDescriptor.checks.nativeBinaryStatusMatchesPackage",
        descriptor["checks"]["nativeBinaryStatusMatchesPackage"],
        True,
    )
    return errors


def check_recorded_source_free_native_requirements(target):
    case_name = f"recorded-source-free-native-{target}"

    def check(_package, payload):
        errors = []
        manifest_artifacts = payload["manifest"]["artifacts"]
        requirements = payload["packageArtifactRequirements"]
        descriptor = payload["nativeArtifactDescriptor"]
        evidence = payload["targetLegalizationEvidence"]
        checks = evidence["checks"]
        expected_sidecar_mode_matches = target in {"metal", "vulkan"}
        expected_requirement_evidence_ids = [
            f"target-legalization.v1.{target}.package-artifacts.native",
            f"target-legalization.v1.{target}.package-artifact.required.nativeBinary",
        ]

        if "nativeBinaryStatus" in manifest_artifacts:
            errors.append(
                f"{case_name}: expected recorded native fixture to omit "
                "manifest.artifacts.nativeBinaryStatus"
            )
        expect_equal(
            errors,
            case_name,
            "summary.nativeBinaryStatus",
            payload["summary"]["nativeBinaryStatus"],
            None,
        )
        expect_equal(
            errors,
            case_name,
            "artifactRequirementsProjection.basis",
            payload["artifactRequirementsProjection"]["basis"],
            "recorded-packageArtifactRequirements",
        )
        expect_equal(
            errors,
            case_name,
            "artifactRequirementsProjection.nativeArtifactDescriptorHealth",
            payload["artifactRequirementsProjection"]["nativeArtifactDescriptorHealth"],
            "ok",
        )
        expect_equal(
            errors,
            case_name,
            "packageArtifactRequirements.packageMode",
            requirements["packageMode"],
            "native",
        )
        expect_equal(
            errors,
            case_name,
            "packageArtifactRequirements.requiredPathArtifacts.names",
            [record.get("name") for record in requirements["requiredPathArtifacts"]],
            ["nativeBinary"],
        )
        expect_equal(
            errors,
            case_name,
            "packageArtifactRequirements.evidenceIds",
            requirements["evidenceIds"],
            expected_requirement_evidence_ids,
        )
        expect_equal(
            errors,
            case_name,
            "packageArtifactRequirements.requiresNativeBinaryStatus",
            requirements["requiresNativeBinaryStatus"],
            False,
        )
        expect_equal(
            errors,
            case_name,
            "packageArtifactRequirements.allowsPlannedNativeBinary",
            requirements["allowsPlannedNativeBinary"],
            False,
        )
        expect_equal(
            errors,
            case_name,
            "packageArtifactRequirements.allowsPlannedNativeSourceEvidence",
            requirements["allowsPlannedNativeSourceEvidence"],
            False,
        )
        expect_equal(
            errors,
            case_name,
            "nativeArtifactDescriptor.health",
            descriptor["health"],
            "ok",
        )
        expect_equal(
            errors,
            case_name,
            "nativeArtifactDescriptor.nativeBinaryStatus",
            descriptor["nativeBinaryStatus"],
            None,
        )
        expect_equal(
            errors,
            case_name,
            "nativeArtifactDescriptor.checks.nativeBinaryStatusMatchesPackage",
            descriptor["checks"]["nativeBinaryStatusMatchesPackage"],
            True,
        )
        expect_equal(
            errors,
            case_name,
            "targetLegalizationEvidence.packageModeSource",
            evidence["packageModeSource"],
            "manifest.packageArtifactRequirements",
        )
        expect_equal(
            errors,
            case_name,
            "targetLegalizationEvidence.packageArtifactRequirementEvidenceIds",
            evidence["packageArtifactRequirementEvidenceIds"],
            expected_requirement_evidence_ids,
        )
        expect_equal(
            errors,
            case_name,
            "targetLegalizationEvidence.checks.debugMetadataPackageModeMatchesRequirements",
            checks["debugMetadataPackageModeMatchesRequirements"],
            expected_sidecar_mode_matches,
        )
        expect_equal(
            errors,
            case_name,
            "targetLegalizationEvidence.checks.targetExplanationPackageModeMatchesRequirements",
            checks["targetExplanationPackageModeMatchesRequirements"],
            expected_sidecar_mode_matches,
        )
        if target == "vulkan":
            expected_core_evidence_ids = [
                "target-legalization.v1.vulkan.decision",
                "target-legalization.v1.vulkan.state.legalized",
                "target-legalization.v1.vulkan.support.native",
                "target-legalization.v1.vulkan.package-mode.native",
                "target-legalization.v1.vulkan.package-provenance.native-package-available",
                "target-legalization.v1.vulkan.package-reason.native-package-available",
            ]
            expect_equal(
                errors,
                case_name,
                "targetLegalizationEvidence.debugMetadata.legalizationCoreEvidenceIds",
                evidence["debugMetadata"]["legalizationCoreEvidenceIds"],
                expected_core_evidence_ids,
            )
            expect_equal(
                errors,
                case_name,
                "targetLegalizationEvidence.targetExplanation.legalizationCoreEvidenceIds",
                evidence["targetExplanation"]["legalizationCoreEvidenceIds"],
                expected_core_evidence_ids,
            )
        return errors

    return check


def check_native_artifact_descriptor(package, payload):
    errors = []
    descriptor = payload["nativeArtifactDescriptor"]
    checks = descriptor["checks"]
    expect_equal(
        errors,
        "native-artifact-descriptor",
        "nativeArtifactDescriptor.health",
        descriptor["health"],
        "ok",
    )
    expect_equal(
        errors,
        "native-artifact-descriptor",
        "nativeArtifactDescriptor.path",
        descriptor["path"],
        "metadata/native-artifact.json",
    )
    expect_equal(
        errors,
        "native-artifact-descriptor",
        "nativeArtifactDescriptor.kind",
        descriptor["kind"],
        "crossgl.nativeArtifact",
    )
    expect_equal(
        errors,
        "native-artifact-descriptor",
        "nativeArtifactDescriptor.contractVersion",
        descriptor["contractVersion"],
        "native-artifact-v0",
    )
    expect_equal(
        errors,
        "native-artifact-descriptor",
        "nativeArtifactDescriptor.target",
        descriptor["target"],
        "directx",
    )
    expect_equal(
        errors,
        "native-artifact-descriptor",
        "nativeArtifactDescriptor.binaryKind",
        descriptor["binaryKind"],
        "directx.dxil",
    )
    expect_equal(
        errors,
        "native-artifact-descriptor",
        "nativeArtifactDescriptor.sourcePath",
        descriptor["sourcePath"],
        "backend/directx/StorageBufferComputeShader.hlsl",
    )
    expect_equal(
        errors,
        "native-artifact-descriptor",
        "nativeArtifactDescriptor.artifactPath",
        descriptor["artifactPath"],
        None,
    )
    optimization_evidence = expect_object(
        errors,
        "native-artifact-descriptor",
        "nativeArtifactDescriptor.optimizationEvidence",
        descriptor["optimizationEvidence"],
    )
    expect_equal(
        errors,
        "native-artifact-descriptor",
        "nativeArtifactDescriptor.optimizationEvidence.requestedLevel",
        optimization_evidence.get("requestedLevel"),
        "O2",
    )
    expect_equal(
        errors,
        "native-artifact-descriptor",
        "nativeArtifactDescriptor.optimizationEvidence.toolFlag",
        optimization_evidence.get("toolFlag"),
        "-O3",
    )
    for name, value in checks.items():
        expected = (
            None
            if name in {"artifactHashMatchesFile", "sizeBytesMatchesFile"}
            else True
        )
        expect_equal(
            errors,
            "native-artifact-descriptor",
            f"nativeArtifactDescriptor.checks.{name}",
            value,
            expected,
        )
    descriptor_artifact = record_by_name(
        payload["artifacts"],
        "nativeArtifactDescriptor",
    )
    expect_equal(
        errors,
        "native-artifact-descriptor",
        "artifacts.nativeArtifactDescriptor.exists",
        descriptor_artifact["exists"],
        True,
    )
    expect_location_overlaps_text(
        errors,
        "native-artifact-descriptor",
        "artifacts.nativeArtifactDescriptor.location",
        descriptor_artifact["location"],
        package / "manifest.json",
        json.dumps(descriptor_artifact["path"]),
    )
    return errors


def check_native_target_artifact_descriptor(target):
    def check(package, payload):
        errors = []
        descriptor = payload["nativeArtifactDescriptor"]
        checks = descriptor["checks"]
        expect_equal(
            errors,
            f"native-artifact-descriptor-{target}",
            "summary.module",
            payload["summary"]["module"],
            MODULE_NAME,
        )
        expect_equal(
            errors,
            f"native-artifact-descriptor-{target}",
            "summary.target",
            payload["summary"]["target"],
            target,
        )
        expect_equal(
            errors,
            f"native-artifact-descriptor-{target}",
            "reflection.module",
            payload["reflection"]["module"],
            MODULE_NAME,
        )
        expect_equal(
            errors,
            f"native-artifact-descriptor-{target}",
            "reflection.target",
            payload["reflection"]["target"],
            target,
        )
        expect_equal(
            errors,
            f"native-artifact-descriptor-{target}",
            "nativeArtifactDescriptor.health",
            descriptor["health"],
            "ok",
        )
        expect_equal(
            errors,
            f"native-artifact-descriptor-{target}",
            "nativeArtifactDescriptor.target",
            descriptor["target"],
            target,
        )
        expect_equal(
            errors,
            f"native-artifact-descriptor-{target}",
            "nativeArtifactDescriptor.validationStatus",
            descriptor["validationStatus"],
            "validated",
        )
        expect_equal(
            errors,
            f"native-artifact-descriptor-{target}",
            "nativeArtifactDescriptor.nativeBinaryStatus",
            descriptor["nativeBinaryStatus"],
            None,
        )
        for name, value in descriptor["checks"].items():
            expect_equal(
                errors,
                f"native-artifact-descriptor-{target}",
                f"nativeArtifactDescriptor.checks.{name}",
                value,
                True,
            )
        return errors

    return check


def check_invalid_native_artifact_descriptor(package, payload):
    errors = []
    descriptor = payload["nativeArtifactDescriptor"]
    expect_equal(
        errors,
        "native-artifact-descriptor-invalid",
        "nativeArtifactDescriptor.health",
        descriptor["health"],
        "invalid",
    )
    expect_equal(
        errors,
        "native-artifact-descriptor-invalid",
        "nativeArtifactDescriptor.descriptorExists",
        descriptor["descriptorExists"],
        True,
    )
    return errors


def check_missing_native_artifact_descriptor(package, payload):
    errors = []
    descriptor = payload["nativeArtifactDescriptor"]
    expect_equal(
        errors,
        "native-artifact-descriptor-missing",
        "nativeArtifactDescriptor.artifactPresent",
        descriptor["artifactPresent"],
        True,
    )
    expect_equal(
        errors,
        "native-artifact-descriptor-missing",
        "nativeArtifactDescriptor.path",
        descriptor["path"],
        "metadata/native-artifact.json",
    )
    expect_equal(
        errors,
        "native-artifact-descriptor-missing",
        "nativeArtifactDescriptor.descriptorExists",
        descriptor["descriptorExists"],
        False,
    )
    expect_equal(
        errors,
        "native-artifact-descriptor-missing",
        "nativeArtifactDescriptor.health",
        descriptor["health"],
        "incomplete",
    )
    descriptor_artifact = record_by_name(
        payload["artifacts"],
        "nativeArtifactDescriptor",
    )
    expect_equal(
        errors,
        "native-artifact-descriptor-missing",
        "artifacts.nativeArtifactDescriptor.exists",
        descriptor_artifact["exists"],
        False,
    )
    expect_equal(
        errors,
        "native-artifact-descriptor-missing",
        "artifacts.nativeArtifactDescriptor.path",
        descriptor_artifact["path"],
        "metadata/native-artifact.json",
    )
    return errors


def check_native_artifact_descriptor_target_kind_mismatch(_package, payload):
    case_name = "native-artifact-descriptor-target-kind-mismatch"
    errors = []
    descriptor = payload["nativeArtifactDescriptor"]
    checks = descriptor["checks"]
    projection = payload["artifactRequirementsProjection"]

    expect_equal(
        errors,
        case_name,
        "summary.target",
        payload["summary"]["target"],
        "directx",
    )
    expect_equal(
        errors,
        case_name,
        "nativeArtifactDescriptor.health",
        descriptor["health"],
        "invalid",
    )
    expect_equal(
        errors,
        case_name,
        "nativeArtifactDescriptor.target",
        descriptor["target"],
        "vulkan",
    )
    expect_equal(
        errors,
        case_name,
        "nativeArtifactDescriptor.binaryKind",
        descriptor["binaryKind"],
        "vulkan.spirv-module",
    )
    expect_equal(
        errors,
        case_name,
        "nativeArtifactDescriptor.checks.descriptorIdentityMatchesContract",
        checks["descriptorIdentityMatchesContract"],
        True,
    )
    expect_equal(
        errors,
        case_name,
        "nativeArtifactDescriptor.checks.targetMatchesPackage",
        checks["targetMatchesPackage"],
        False,
    )
    expect_equal(
        errors,
        case_name,
        "nativeArtifactDescriptor.checks.sourcePathMatchesManifest",
        checks["sourcePathMatchesManifest"],
        False,
    )
    expect_equal(
        errors,
        case_name,
        "nativeArtifactDescriptor.checks.nativeBinaryStatusMatchesPackage",
        checks["nativeBinaryStatusMatchesPackage"],
        True,
    )
    expect_equal(
        errors,
        case_name,
        "nativeArtifactDescriptor.checks.artifactPathMatchesManifest",
        checks["artifactPathMatchesManifest"],
        True,
    )
    expect_equal(
        errors,
        case_name,
        "artifactRequirementsProjection.nativeArtifactDescriptorHealth",
        projection["nativeArtifactDescriptorHealth"],
        "invalid",
    )
    return errors


def expect_target_artifact_matrix(errors, case_name, manifest, payload):
    target = manifest["target"]
    expected_paths = TARGET_ARTIFACT_PATHS[target]
    expected_status = manifest["artifacts"].get("nativeBinaryStatus")
    artifacts = {
        record.get("name"): record
        for record in payload.get("artifacts", [])
        if isinstance(record, dict)
    }

    for name, expected_path in expected_paths.items():
        record = artifacts.get(name)
        if record is None:
            errors.append(f"{case_name}: missing artifact record {name!r}")
            continue
        expect_equal(
            errors,
            case_name,
            f"artifacts.{name}.path",
            record.get("path"),
            expected_path,
        )

    native_binary = artifacts.get("nativeBinary")
    if native_binary is not None:
        expect_equal(
            errors,
            case_name,
            "artifacts.nativeBinary.exists",
            native_binary.get("exists"),
            expected_status != "planned",
        )


def check_valid_target(case_name, manifest):
    expected_artifact_names = sorted(expected_manifest_artifact_names(manifest))
    expected_native_status = expected_summary_native_binary_status(manifest)

    def check(_package, payload):
        errors = []
        expect_equal(
            errors,
            case_name,
            "summary.target",
            payload["summary"]["target"],
            manifest["target"],
        )
        expect_equal(
            errors,
            case_name,
            "summary.nativeBinaryStatus",
            payload["summary"]["nativeBinaryStatus"],
            expected_native_status,
        )
        if (
            "graphicsAbi" not in manifest.get("artifacts", {})
            and "graphicsAbi" in payload
        ):
            errors.append(
                f"{case_name}: inspect report must omit graphicsAbi when "
                "manifest.artifacts.graphicsAbi is absent"
            )
        artifact_names = sorted(
            record.get("name") for record in payload.get("artifacts", [])
        )
        expect_equal(
            errors,
            case_name,
            "artifacts.names",
            artifact_names,
            expected_artifact_names,
        )
        expect_target_artifact_matrix(errors, case_name, manifest, payload)
        if manifest["target"] == "vulkan":
            native_profile = payload["vulkanNativeProfile"]
            expect_equal(
                errors,
                case_name,
                "vulkanNativeProfile.health",
                native_profile["health"],
                "ok",
            )
            expect_equal(
                errors,
                case_name,
                "vulkanNativeProfile.spirvVersion",
                native_profile["spirvVersion"],
                "1.0",
            )
            expect_equal(
                errors,
                case_name,
                "vulkanNativeProfile.nativeBinary",
                native_profile["nativeBinary"],
                manifest["artifacts"]["nativeBinary"],
            )
            for check_name, value in native_profile["checks"].items():
                expect_equal(
                    errors,
                    case_name,
                    f"vulkanNativeProfile.checks.{check_name}",
                    value,
                    True,
                )
        return errors

    return check


def check_nonuniform_feature_metadata(case_name, manifest, expected_diagnostics):
    expected_features = nonuniform_target_features(manifest["target"])
    expected_native_status = expected_summary_native_binary_status(manifest)

    def check(_package, payload):
        errors = []
        expect_equal(
            errors,
            case_name,
            "summary.target",
            payload["summary"]["target"],
            manifest["target"],
        )
        expect_equal(
            errors,
            case_name,
            "summary.nativeBinaryStatus",
            payload["summary"]["nativeBinaryStatus"],
            expected_native_status,
        )
        expect_equal(
            errors,
            case_name,
            "reflection.targetFeatures",
            payload["reflection"].get("targetFeatures"),
            expected_features,
        )
        expect_equal(
            errors,
            case_name,
            "diagnostics",
            payload.get("diagnostics"),
            expected_diagnostics,
        )
        return errors

    return check


def expect_storage_image_binding_parity(
    errors,
    case_name,
    target,
    resource,
    binding,
    expected_source_coordinate=None,
):
    source_coordinate = (
        expected_source_coordinate
        if expected_source_coordinate is not None
        else reflection_source_coordinate(resource)
    )
    expect_equal(
        errors,
        case_name,
        f"reflection.resources.{resource.get('name')}.sourceCoordinate",
        reflection_source_coordinate(resource),
        source_coordinate,
    )
    expect_equal(
        errors,
        case_name,
        f"reflection.targetResourceBindings.{binding.get('name')}.sourceCoordinate",
        reflection_source_coordinate(binding),
        source_coordinate,
    )
    expect_equal(
        errors,
        case_name,
        f"reflection.targetResourceBindings.{binding.get('name')}.targetCoordinate",
        reflection_target_binding_coordinate(target, binding),
        expected_storage_image_array_target_coordinate(target, resource),
    )
    expect_equal(
        errors,
        case_name,
        f"reflection.targetResourceBindings.{binding.get('name')}.arrayDimensions",
        binding.get("arrayDimensions"),
        resource.get("arrayDimensions"),
    )
    expect_equal(
        errors,
        case_name,
        f"reflection.targetResourceBindings.{binding.get('name')}.arrayElementCount",
        binding.get("arrayElementCount"),
        expected_array_element_count(resource),
    )


def expect_source_package_debug_parity(errors, case_name, package, manifest, payload):
    target = manifest["target"]
    requirements = payload.get("packageArtifactRequirements", {})
    evidence = payload.get("targetLegalizationEvidence", {})
    debug_sidecar = evidence.get("debugMetadata", {})
    debug_doc = read_artifact_json(package, manifest, "debugMetadata") or {}
    decision = debug_doc.get("targetDecision", {})
    expected_evidence_ids = decision.get("selectedTargetLegalizationCoreEvidenceIds")

    expect_equal(
        errors,
        case_name,
        "packageArtifactRequirements.target",
        requirements.get("target"),
        target,
    )
    expect_equal(
        errors,
        case_name,
        "packageArtifactRequirements.packageMode",
        requirements.get("packageMode"),
        "source-package",
    )
    expect_equal(
        errors,
        case_name,
        "debugMetadata.targetDecision.selectedTarget",
        decision.get("selectedTarget"),
        target,
    )
    expect_equal(
        errors,
        case_name,
        "debugMetadata.targetDecision.selectedTargetPackageMode",
        decision.get("selectedTargetPackageMode"),
        "source-package",
    )
    expect_equal(
        errors,
        case_name,
        "debugMetadata.targetDecision.selectedTargetSourcePackageSupported",
        decision.get("selectedTargetSourcePackageSupported"),
        True,
    )
    expect_equal(
        errors,
        case_name,
        "targetLegalizationEvidence.debugMetadata.target",
        debug_sidecar.get("target"),
        target,
    )
    expect_equal(
        errors,
        case_name,
        "targetLegalizationEvidence.debugMetadata.packageMode",
        debug_sidecar.get("packageMode"),
        "source-package",
    )
    expect_equal(
        errors,
        case_name,
        "targetLegalizationEvidence.debugMetadata.legalizationCoreEvidenceIds",
        debug_sidecar.get("legalizationCoreEvidenceIds"),
        expected_evidence_ids,
    )
    expect_equal(
        errors,
        case_name,
        "targetLegalizationEvidence.packageMode",
        evidence.get("packageMode"),
        "source-package",
    )
    expect_equal(
        errors,
        case_name,
        "targetLegalizationEvidence.checks.debugMetadataTargetMatchesPackage",
        evidence.get("checks", {}).get("debugMetadataTargetMatchesPackage"),
        True,
    )
    expect_equal(
        errors,
        case_name,
        "targetLegalizationEvidence.checks.debugMetadataPackageModeMatchesRequirements",
        evidence.get("checks", {}).get("debugMetadataPackageModeMatchesRequirements"),
        True,
    )


def check_storage_image_metadata(case_name, manifest, atomic=False):
    target = manifest["target"]
    expected_features = storage_image_target_features(target, atomic=atomic)
    first_name = "signedCounters" if atomic else "colorImage"
    first_type = "iimage2D" if atomic else "image2D"
    first_format = "r32i" if atomic else "rgba32f"
    array_name = "unsignedAtlases" if atomic else "maskAtlases"
    array_type = "uimage2DArray[IMAGE_COUNT]"
    array_format = "r32ui" if atomic else "rgba32ui"
    array_dimensions = [
        {
            "source": "IMAGE_COUNT",
            "kind": "fixed",
            "elementCount": 2,
        }
    ]
    first_binding_fields = {
        "target": target,
        "kind": "storage_image",
        "sourceType": first_type,
        "storageImageFormat": first_format,
    }
    array_binding_fields = {
        "sourceType": array_type,
        "storageImageFormat": array_format,
        "arraySize": "IMAGE_COUNT",
        "arrayElementCount": 2,
        "arrayDimensions": array_dimensions,
    }

    if target == "directx":
        first_binding_fields.update(
            bindingClass="uav",
            descriptorType="UAV",
            argumentIndex=0,
        )
    elif target == "opengl":
        first_binding_fields.update(
            abi="programResourceBinding",
            bindingClass="image",
        )
        array_binding_fields["argumentIndex"] = 1
    elif target == "vulkan":
        first_binding_fields.update(
            abi="descriptor",
            bindingClass="storageImage",
            descriptorType="VK_DESCRIPTOR_TYPE_STORAGE_IMAGE",
            storageClass="UniformConstant",
            spirvType=(
                "OpTypeImage<int, 2D, sampled=2, format=R32i>"
                if atomic
                else "OpTypeImage<float, 2D, sampled=2, format=Rgba32f>"
            ),
        )
        array_binding_fields["storageClass"] = "UniformConstant"
        array_binding_fields["spirvType"] = (
            "OpTypeArray<OpTypeImage<uint, 2DArray, sampled=2, "
            f"format={'R32ui' if atomic else 'Rgba32ui'}>, IMAGE_COUNT>"
        )
    elif target == "metal":
        first_binding_fields.update(
            abi="kernelArgument",
            bindingClass="texture",
            metalType=(
                "texture2d<int, access::read_write>"
                if atomic
                else "texture2d<float, access::read_write>"
            ),
        )
        array_binding_fields["argumentIndex"] = 1
        array_binding_fields["metalType"] = (
            "array<texture2d_array<uint, access::read_write>, IMAGE_COUNT>"
        )

    def check(package, payload):
        errors = []
        reflection = payload["reflection"]
        resources = reflection.get("resources", [])
        bindings = reflection.get("targetResourceBindings", [])
        function_constants = reflection.get("functionConstants", [])

        expect_equal(
            errors,
            case_name,
            "reflection.targetFeatures",
            reflection.get("targetFeatures"),
            expected_features,
        )
        expect_equal(
            errors,
            case_name,
            "reflection.resources.length",
            len(resources),
            2,
        )
        expect_equal(
            errors,
            case_name,
            "reflection.targetResourceBindings.length",
            len(bindings),
            2,
        )

        expected_records = (
            (
                "reflection.resources",
                record_by_name(resources, first_name),
                first_name,
                {
                    "kind": "storage_image",
                    "type": first_type,
                    "storageImageFormat": first_format,
                    "binding": 0,
                },
            ),
            (
                "reflection.resources",
                record_by_name(resources, array_name),
                array_name,
                {
                    "kind": "storage_image",
                    "type": array_type,
                    "storageImageFormat": array_format,
                    "arrayDimensions": array_dimensions,
                },
            ),
            (
                "reflection.targetResourceBindings",
                record_by_name(bindings, first_name),
                first_name,
                first_binding_fields,
            ),
            (
                "reflection.targetResourceBindings",
                record_by_name(bindings, array_name),
                array_name,
                array_binding_fields,
            ),
        )
        for path, record, name, expected_fields in expected_records:
            for field, expected_value in expected_fields.items():
                expect_equal(
                    errors,
                    case_name,
                    f"{path}.{name}.{field}",
                    record.get(field),
                    expected_value,
                )

        expect_equal(
            errors,
            case_name,
            "reflection.functionConstants.0.name",
            function_constants[0].get("name") if function_constants else None,
            "IMAGE_COUNT",
        )
        expect_equal(
            errors,
            case_name,
            "reflection.functionConstants.0.value",
            function_constants[0].get("value") if function_constants else None,
            "2",
        )
        expect_storage_image_binding_parity(
            errors,
            case_name,
            target,
            record_by_name(resources, array_name),
            record_by_name(bindings, array_name),
            expected_source_coordinate=(
                expected_synthetic_storage_image_array_source_coordinate(array_name)
            ),
        )
        if target in {"directx", "opengl"}:
            expect_source_package_debug_parity(
                errors,
                case_name,
                package,
                manifest,
                payload,
            )
        return errors

    return check


def check_missing_backend_source(_package, payload):
    errors = []
    expect_equal(
        errors,
        "missing-backend-source",
        "artifacts.backendSource.exists",
        record_by_name(payload["artifacts"], "backendSource")["exists"],
        False,
    )
    return errors


def check_escaping_artifact(package, payload):
    errors = []
    backend_source = record_by_name(payload["artifacts"], "backendSource")
    expect_equal(
        errors,
        "escaping-artifact",
        "artifacts.backendSource.packageRelative",
        backend_source["packageRelative"],
        False,
    )
    expect_equal(
        errors,
        "escaping-artifact",
        "artifacts.backendSource.exists",
        backend_source["exists"],
        False,
    )
    expect_location(
        errors,
        "escaping-artifact",
        "artifacts.backendSource.location",
        backend_source["location"],
        "manifest.json",
        min_offset=1,
        min_length=1,
    )
    expect_location_overlaps_text(
        errors,
        "escaping-artifact",
        "artifacts.backendSource.location",
        backend_source["location"],
        package / "manifest.json",
        json.dumps(backend_source["path"]),
    )
    return errors


def check_missing_hir_source_map(_package, payload):
    errors = []
    expect_equal(
        errors,
        "missing-hir-source-map-file",
        "debugArtifacts.health",
        payload["debugArtifacts"]["health"],
        "incomplete",
    )
    expect_equal(
        errors,
        "missing-hir-source-map-file",
        "debugArtifacts.hirSourceMapExists",
        payload["debugArtifacts"]["hirSourceMapExists"],
        False,
    )
    expect_debug_artifact_check(
        errors,
        "missing-hir-source-map-file",
        payload,
        "hirSourceLocationsMatch",
        None,
    )
    return errors


def check_hir_source_location_drift(_package, payload):
    errors = []
    expect_equal(
        errors,
        "hir-source-location-drift",
        "debugArtifacts.health",
        payload["debugArtifacts"]["health"],
        "drift",
    )
    expect_debug_artifact_check(
        errors,
        "hir-source-location-drift",
        payload,
        "hirSourceLocationsMatch",
        False,
    )
    return errors


def check_filtered_hir_source_map(_package, payload):
    errors = []
    expect_equal(
        errors,
        "filtered-hir-source-map",
        "debugArtifacts.health",
        payload["debugArtifacts"]["health"],
        "drift",
    )
    expect_debug_artifact_check(
        errors,
        "filtered-hir-source-map",
        payload,
        "sourceMapUnfiltered",
        False,
    )
    return errors


def check_category_drift(_package, payload):
    errors = []
    expect_equal(
        errors,
        "category-drift",
        "debugArtifacts.health",
        payload["debugArtifacts"]["health"],
        "drift",
    )
    expect_debug_artifact_check(
        errors,
        "category-drift",
        payload,
        "sourceMapCategoryCountsConsistent",
        False,
    )
    return errors


def check_published_with_sidecar(_package, payload):
    errors = []
    publication = payload["publication"]
    sidecars = publication["siblingSidecars"]
    expect_equal(
        errors,
        "published-with-sidecar",
        "publication.state",
        publication["state"],
        "published",
    )
    expect_equal(
        errors,
        "published-with-sidecar",
        "publication.siblingSidecarCount",
        publication["siblingSidecarCount"],
        1,
    )
    expect_equal(
        errors,
        "published-with-sidecar",
        "publication.siblingSidecars[0].kind",
        sidecars[0]["kind"],
        "previous",
    )
    expect_equal(
        errors,
        "published-with-sidecar",
        "publication.siblingSidecars[0].token",
        sidecars[0]["token"],
        "12345",
    )
    expect_equal(
        errors,
        "published-with-sidecar",
        "publication.siblingSidecars[0].attempt",
        sidecars[0]["attempt"],
        7,
    )
    expect_equal(
        errors,
        "published-with-sidecar",
        "publication.siblingSidecars[0].directory",
        sidecars[0]["directory"],
        True,
    )
    return errors


def check_staged_sidecar(package, payload):
    errors = []
    publication = payload["publication"]
    expect_equal(
        errors,
        "staged-sidecar",
        "publication.state",
        publication["state"],
        "staged",
    )
    expect_equal(
        errors,
        "staged-sidecar",
        "publication.requestedPath",
        publication["requestedPath"],
        package.with_name("staged-sidecar.cglb").as_posix(),
    )
    expect_equal(
        errors,
        "staged-sidecar",
        "publication.sidecarKind",
        publication["sidecarKind"],
        "staging",
    )
    expect_equal(
        errors,
        "staged-sidecar",
        "publication.sidecarToken",
        publication["sidecarToken"],
        "67890",
    )
    expect_equal(
        errors,
        "staged-sidecar",
        "publication.sidecarAttempt",
        publication["sidecarAttempt"],
        3,
    )
    expect_equal(
        errors,
        "staged-sidecar",
        "publication.siblingSidecarCount",
        publication["siblingSidecarCount"],
        1,
    )
    expect_equal(
        errors,
        "staged-sidecar",
        "publication.siblingSidecars[0].path",
        publication["siblingSidecars"][0]["path"],
        package.as_posix(),
    )
    return errors


def run_cases(root, cglc, jobs=1):
    errors = []
    with tempfile.TemporaryDirectory() as tmp:
        tmp_dir = Path(tmp)

        package, _source, _manifest = make_package(tmp_dir, "valid-planned")
        errors.extend(
            expect_success(
                root, cglc, tmp_dir, "valid-planned", package, check_valid_planned
            )
        )

        package, _source, manifest = make_package(
            tmp_dir,
            "native-artifact-descriptor",
        )

        def add_optimization_evidence(descriptor):
            descriptor["optimizationEvidence"] = {
                "requestedLevel": "O2",
                "effectiveLevel": "O2",
                "policy": "crossgl-to-dxc-optimization-map",
                "status": "metadata-only",
                "tool": "dxc",
                "toolFlag": "-O3",
                "debugInfo": False,
                "profile": "cs_6_0",
                "flags": ["-O3"],
                "evidenceSource": {
                    "kind": "compiler-policy",
                },
            }

        add_native_artifact_descriptor(
            package, manifest, mutate=add_optimization_evidence
        )
        errors.extend(
            expect_success(
                root,
                cglc,
                tmp_dir,
                "native-artifact-descriptor",
                package,
                check_native_artifact_descriptor,
            )
        )

        def check_native_artifact_descriptor_target(target):
            case_name = f"native-artifact-descriptor-{target}"
            case_dir = case_tmp_dir(tmp_dir, case_name)
            package, _source, manifest = make_package(
                case_dir,
                case_name,
                target=target,
            )
            add_native_artifact_descriptor(
                package, manifest, mutate=mark_native_artifact_validated
            )
            return expect_success(
                root,
                cglc,
                case_dir,
                case_name,
                package,
                check_native_target_artifact_descriptor(target),
            )

        errors.extend(
            collect_case_errors(
                jobs,
                [
                    lambda target=target: check_native_artifact_descriptor_target(
                        target
                    )
                    for target in ("metal", "vulkan")
                ],
            )
        )

        package, _source, manifest = make_package(
            tmp_dir,
            "native-artifact-descriptor-invalid",
        )

        def remove_toolchain_provenance(descriptor):
            del descriptor["toolchainProvenance"]

        add_native_artifact_descriptor(
            package, manifest, mutate=remove_toolchain_provenance
        )
        errors.extend(
            expect_success(
                root,
                cglc,
                tmp_dir,
                "native-artifact-descriptor-invalid",
                package,
                check_invalid_native_artifact_descriptor,
            )
        )

        package, _source, manifest = make_package(
            tmp_dir,
            "native-artifact-descriptor-missing",
        )
        add_native_artifact_descriptor(package, manifest)
        package_path(
            package,
            manifest["artifacts"]["nativeArtifactDescriptor"],
        ).unlink()
        errors.extend(
            expect_success(
                root,
                cglc,
                tmp_dir,
                "native-artifact-descriptor-missing",
                package,
                check_missing_native_artifact_descriptor,
            )
        )

        package, _source, manifest = make_package(
            tmp_dir,
            "native-artifact-descriptor-target-kind-mismatch",
        )

        def retarget_descriptor_to_vulkan(descriptor):
            descriptor["target"] = "vulkan"
            descriptor["binaryKind"] = "vulkan.spirv-module"

        add_native_artifact_descriptor(
            package,
            manifest,
            mutate=retarget_descriptor_to_vulkan,
        )
        errors.extend(
            expect_success(
                root,
                cglc,
                tmp_dir,
                "native-artifact-descriptor-target-kind-mismatch",
                package,
                check_native_artifact_descriptor_target_kind_mismatch,
            )
        )

        package, _source, manifest = make_package(
            tmp_dir,
            "native-artifact-descriptor-source-hash-extra-property",
        )

        def add_source_hash_extra_property(descriptor):
            descriptor["sourceHash"]["unexpected"] = True

        add_native_artifact_descriptor(
            package, manifest, mutate=add_source_hash_extra_property
        )
        errors.extend(
            expect_success(
                root,
                cglc,
                tmp_dir,
                "native-artifact-descriptor-source-hash-extra-property",
                package,
                check_invalid_native_artifact_descriptor,
            )
        )

        package, _source, manifest = make_package(
            tmp_dir,
            "native-artifact-descriptor-artifact-hash-extra-property",
            status="emitted",
        )

        def add_artifact_hash_extra_property(descriptor):
            descriptor["artifactHash"]["unexpected"] = True

        add_native_artifact_descriptor(
            package, manifest, mutate=add_artifact_hash_extra_property
        )
        errors.extend(
            expect_success(
                root,
                cglc,
                tmp_dir,
                "native-artifact-descriptor-artifact-hash-extra-property",
                package,
                check_invalid_native_artifact_descriptor,
            )
        )

        package, _source, _manifest = make_package(
            tmp_dir, "valid-emitted", status="emitted"
        )
        errors.extend(
            expect_success(
                root, cglc, tmp_dir, "valid-emitted", package, check_valid_emitted
            )
        )

        package, _source, _manifest = make_package(
            tmp_dir,
            "recorded-artifact-requirements",
        )
        errors.extend(
            expect_success(
                root,
                cglc,
                tmp_dir,
                "recorded-artifact-requirements",
                package,
                check_recorded_artifact_requirements,
            )
        )

        package, _source, manifest = make_package(
            tmp_dir,
            "recorded-sidecar-requirement-evidence",
        )
        recorded_evidence_ids = manifest["packageArtifactRequirements"]["evidenceIds"]
        add_sidecar_package_requirement_evidence(
            package,
            manifest,
            recorded_evidence_ids,
        )
        errors.extend(
            expect_success(
                root,
                cglc,
                tmp_dir,
                "recorded-sidecar-requirement-evidence",
                package,
                check_recorded_sidecar_requirement_evidence(recorded_evidence_ids),
            )
        )

        package, _source, manifest = make_package(
            tmp_dir,
            "legacy-missing-artifact-requirements",
        )
        legacy_missing_manifest = copy.deepcopy(manifest)
        del legacy_missing_manifest["packageArtifactRequirements"]
        rewrite_manifest(package, legacy_missing_manifest)
        errors.extend(
            expect_success(
                root,
                cglc,
                tmp_dir,
                "legacy-missing-artifact-requirements",
                package,
                check_legacy_missing_artifact_requirements,
            )
        )

        package, _source, manifest = make_package(
            tmp_dir,
            "legacy-sidecar-requirement-evidence",
        )
        add_sidecar_package_requirement_evidence(
            package,
            manifest,
            ["target-legalization.v1.directx.package-artifacts.source-package"],
        )
        legacy_sidecar_manifest = copy.deepcopy(manifest)
        del legacy_sidecar_manifest["packageArtifactRequirements"]
        rewrite_manifest(package, legacy_sidecar_manifest)
        errors.extend(
            expect_success(
                root,
                cglc,
                tmp_dir,
                "legacy-sidecar-requirement-evidence",
                package,
                check_legacy_sidecar_requirement_evidence_report_only,
            )
        )

        package, _source, manifest = make_package(
            tmp_dir,
            "legacy-no-artifact-requirements",
        )
        add_native_artifact_descriptor(package, manifest)
        legacy_manifest = copy.deepcopy(manifest)
        del legacy_manifest["packageArtifactRequirements"]
        rewrite_manifest(package, legacy_manifest)
        errors.extend(
            expect_success(
                root,
                cglc,
                tmp_dir,
                "legacy-no-artifact-requirements",
                package,
                check_legacy_no_artifact_requirements,
            )
        )

        package, _source, manifest = make_package(
            tmp_dir,
            "legacy-no-artifact-requirements-opengl",
            target="opengl",
        )
        add_native_artifact_descriptor(package, manifest)
        legacy_manifest = copy.deepcopy(manifest)
        del legacy_manifest["packageArtifactRequirements"]
        rewrite_manifest(package, legacy_manifest)
        errors.extend(
            expect_success(
                root,
                cglc,
                tmp_dir,
                "legacy-no-artifact-requirements-opengl",
                package,
                lambda package, payload: check_legacy_no_artifact_requirements(
                    package,
                    payload,
                    "legacy-no-artifact-requirements-opengl",
                ),
            )
        )

        package, _source, manifest = make_package(
            tmp_dir,
            "null-artifact-requirements",
        )
        null_requirements_manifest = copy.deepcopy(manifest)
        null_requirements_manifest["packageArtifactRequirements"] = None
        rewrite_manifest(package, null_requirements_manifest)
        errors.extend(
            expect_failure(
                cglc,
                "null-artifact-requirements",
                package,
                "package manifest packageArtifactRequirements is invalid",
                expected_file=package / "manifest.json",
            )
        )

        package, _source, manifest = make_package(
            tmp_dir,
            "recorded-requirements-no-native-status",
            target="directx",
            status="emitted",
        )
        manifest["packageArtifactRequirements"] = {
            "target": "directx",
            "packageMode": "native",
            "requiredPathArtifacts": ["backendSource", "nativeBinary"],
            "requiresNativeBinaryStatus": False,
            "allowsPlannedNativeBinary": False,
            "allowsPlannedNativeSourceEvidence": False,
        }
        del manifest["artifacts"]["nativeBinaryStatus"]
        add_native_artifact_descriptor(
            package,
            manifest,
            mutate=mark_native_artifact_validated,
        )
        errors.extend(
            expect_success(
                root,
                cglc,
                tmp_dir,
                "recorded-requirements-no-native-status",
                package,
                check_recorded_requirements_drift(
                    "recorded-requirements-no-native-status",
                    "native",
                    ["backendSource", "nativeBinary"],
                ),
            )
        )

        def check_recorded_source_free_native_target(target):
            case_name = f"recorded-source-free-native-{target}"
            case_dir = case_tmp_dir(tmp_dir, case_name)
            package, _source, manifest = make_package(
                case_dir,
                case_name,
                target=target,
                status="emitted",
            )
            manifest["packageArtifactRequirements"] = {
                "target": target,
                "packageMode": "native",
                "requiredPathArtifacts": ["nativeBinary"],
                "requiresNativeBinaryStatus": False,
                "allowsPlannedNativeBinary": False,
                "allowsPlannedNativeSourceEvidence": False,
                "evidenceIds": [
                    f"target-legalization.v1.{target}.package-artifacts.native",
                    f"target-legalization.v1.{target}."
                    "package-artifact.required.nativeBinary",
                ],
            }
            manifest["artifacts"].pop("nativeBinaryStatus", None)
            add_native_artifact_descriptor(
                package,
                manifest,
                mutate=mark_native_artifact_validated,
            )
            return expect_success(
                root,
                cglc,
                case_dir,
                case_name,
                package,
                check_recorded_source_free_native_requirements(target),
            )

        errors.extend(
            collect_case_errors(
                jobs,
                [
                    lambda target=target: check_recorded_source_free_native_target(
                        target
                    )
                    for target in ("metal", "vulkan", "directx", "opengl")
                ],
            )
        )

        package, _source, manifest = make_package(
            tmp_dir,
            "recorded-planned-status-policy-drift",
            status="emitted",
        )
        manifest["artifacts"]["nativeBinaryStatus"] = "planned"
        manifest["packageArtifactRequirements"]["allowsPlannedNativeBinary"] = False
        manifest["packageArtifactRequirements"]["allowsPlannedNativeSourceEvidence"] = (
            False
        )
        add_native_artifact_descriptor(package, manifest)
        errors.extend(
            expect_success(
                root,
                cglc,
                tmp_dir,
                "recorded-planned-status-policy-drift",
                package,
                check_recorded_planned_status_policy_drift,
            )
        )

        package, _source, manifest = make_package(
            tmp_dir,
            "recorded-requirements-planned-native",
            target="metal",
        )
        manifest["packageArtifactRequirements"] = {
            "target": "metal",
            "packageMode": "source-package",
            "requiredPathArtifacts": ["backendSource", "nativeBinary"],
            "requiresNativeBinaryStatus": True,
            "allowsPlannedNativeBinary": True,
            "allowsPlannedNativeSourceEvidence": True,
        }
        manifest["artifacts"]["nativeBinaryStatus"] = "planned"
        package_path(package, manifest["artifacts"]["nativeBinary"]).unlink()

        def mark_metal_planned_source_package(descriptor):
            descriptor["toolchainProvenance"]["tools"] = [
                {
                    "name": "CrossGL metal source package fixture",
                    "role": "generator",
                    "version": "fixture",
                    "executable": "cglc",
                }
            ]

        add_native_artifact_descriptor(
            package,
            manifest,
            mutate=mark_metal_planned_source_package,
        )
        errors.extend(
            expect_success(
                root,
                cglc,
                tmp_dir,
                "recorded-requirements-planned-native",
                package,
                check_recorded_requirements_drift(
                    "recorded-requirements-planned-native",
                    "source-package",
                    ["backendSource", "nativeBinary"],
                ),
            )
        )

        package, _source, manifest = make_package(
            tmp_dir, "valid-opengl-emitted", target="opengl", status="emitted"
        )
        errors.extend(
            expect_success(
                root,
                cglc,
                tmp_dir,
                "valid-opengl-emitted",
                package,
                check_valid_target("valid-opengl-emitted", manifest),
            )
        )

        def check_valid_target_case(target):
            case_name = f"valid-{target}"
            case_dir = case_tmp_dir(tmp_dir, case_name)
            package, _source, manifest = make_package(
                case_dir,
                case_name,
                target=target,
            )
            return expect_success(
                root,
                cglc,
                case_dir,
                case_name,
                package,
                check_valid_target(case_name, manifest),
            )

        errors.extend(
            collect_case_errors(
                jobs,
                [
                    lambda target=target: check_valid_target_case(target)
                    for target in ("metal", "vulkan", "opengl")
                ],
            )
        )

        def check_nonuniform_feature_metadata_case(target):
            case_name = f"nonuniform-feature-metadata-{target}"
            case_dir = case_tmp_dir(tmp_dir, case_name)
            package, _source, manifest = make_package(
                case_dir,
                case_name,
                target=target,
            )
            write_nonuniform_reflection(package, manifest)
            diagnostics = write_nonuniform_diagnostics(package, target)
            return expect_success(
                root,
                cglc,
                case_dir,
                case_name,
                package,
                check_nonuniform_feature_metadata(
                    case_name,
                    manifest,
                    diagnostics,
                ),
            )

        errors.extend(
            collect_case_errors(
                jobs,
                [
                    lambda target=target: check_nonuniform_feature_metadata_case(target)
                    for target in ("directx", "opengl", "vulkan", "metal")
                ],
            )
        )

        def check_storage_image_metadata_case(target, atomic):
            family = "storage-image-atomic" if atomic else "storage-image-read-write"
            case_name = f"{family}-metadata-{target}"
            case_dir = case_tmp_dir(tmp_dir, case_name)
            package, _source, manifest = make_package(
                case_dir,
                case_name,
                target=target,
            )
            write_storage_image_reflection(package, manifest, atomic=atomic)
            return expect_success(
                root,
                cglc,
                case_dir,
                case_name,
                package,
                check_storage_image_metadata(
                    case_name,
                    manifest,
                    atomic=atomic,
                ),
            )

        errors.extend(
            collect_case_errors(
                jobs,
                [
                    lambda target=target, atomic=atomic: (
                        check_storage_image_metadata_case(target, atomic)
                    )
                    for target in ("directx", "opengl", "vulkan", "metal")
                    for atomic in (False, True)
                ],
            )
        )

        package, _source, _manifest = make_package(tmp_dir, "published-with-sidecar")
        (tmp_dir / ".published-with-sidecar.cglb.previous-12345-7").mkdir()
        errors.extend(
            expect_success(
                root,
                cglc,
                tmp_dir,
                "published-with-sidecar",
                package,
                check_published_with_sidecar,
            )
        )

        package, _source, _manifest = make_package(tmp_dir, "staged-sidecar")
        staged_package = tmp_dir / ".staged-sidecar.cglb.staging-67890-3"
        package.rename(staged_package)
        errors.extend(
            expect_success(
                root,
                cglc,
                tmp_dir,
                "staged-sidecar",
                staged_package,
                check_staged_sidecar,
            )
        )

        package, _source, manifest = make_package(tmp_dir, "missing-backend-source")
        package_path(package, manifest["artifacts"]["backendSource"]).unlink()
        errors.extend(
            expect_success(
                root,
                cglc,
                tmp_dir,
                "missing-backend-source",
                package,
                check_missing_backend_source,
            )
        )

        package, _source, manifest = make_package(
            tmp_dir,
            "missing-hir-source-map-file",
        )
        package_path(package, manifest["artifacts"]["hirSourceMap"]).unlink()
        errors.extend(
            expect_success(
                root,
                cglc,
                tmp_dir,
                "missing-hir-source-map-file",
                package,
                check_missing_hir_source_map,
            )
        )

        package, _source, manifest = make_package(
            tmp_dir,
            "hir-source-location-drift",
        )
        write_json(
            package_path(package, manifest["artifacts"]["hirSourceMap"]),
            hir_source_map_with_all_record_kinds(),
        )
        errors.extend(
            expect_success(
                root,
                cglc,
                tmp_dir,
                "hir-source-location-drift",
                package,
                check_hir_source_location_drift,
            )
        )

        package, _source, manifest = make_package(
            tmp_dir,
            "filtered-hir-source-map",
        )
        filtered_source_map = hir_source_map_with_all_record_kinds()
        rewrite_debug_metadata_locations(package, manifest, filtered_source_map)
        filtered_source_map["filters"] = {
            "activeCount": 1,
            "expressionKind": "literal",
        }
        write_json(
            package_path(package, manifest["artifacts"]["hirSourceMap"]),
            filtered_source_map,
        )
        errors.extend(
            expect_success(
                root,
                cglc,
                tmp_dir,
                "filtered-hir-source-map",
                package,
                check_filtered_hir_source_map,
            )
        )

        package, _source, manifest = make_package(tmp_dir, "category-drift")
        category_source_map = hir_source_map_with_all_record_kinds()
        rewrite_debug_metadata_locations(package, manifest, category_source_map)
        category_source_map["categoryCounts"]["expressionKinds"] = [
            {
                "name": "binary",
                "count": 1,
            },
        ]
        write_json(
            package_path(package, manifest["artifacts"]["hirSourceMap"]),
            category_source_map,
        )
        errors.extend(
            expect_success(
                root,
                cglc,
                tmp_dir,
                "category-drift",
                package,
                check_category_drift,
            )
        )

        package, _source, manifest = make_package(tmp_dir, "escaping-artifact")
        escaping_manifest = copy.deepcopy(manifest)
        outside = tmp_dir / "outside.hlsl"
        write_text(outside, "// outside\n")
        escaping_manifest["artifacts"]["backendSource"] = "../outside.hlsl"
        rewrite_manifest(package, escaping_manifest)
        errors.extend(
            expect_success(
                root,
                cglc,
                tmp_dir,
                "escaping-artifact",
                package,
                check_escaping_artifact,
            )
        )

        missing_package = tmp_dir / "missing.cglb"
        errors.extend(
            expect_failure(
                cglc,
                "missing-package",
                missing_package,
                "package.inspect.missing-package",
            )
        )

        plain_file = tmp_dir / "plain-file.cglb"
        write_text(plain_file, "not a directory\n")
        errors.extend(
            expect_failure(
                cglc,
                "plain-file",
                plain_file,
                "package.inspect.unsupported-format",
            )
        )

        package, _source, _manifest = make_package(tmp_dir, "missing-manifest")
        (package / "manifest.json").unlink()
        errors.extend(
            expect_failure(
                cglc,
                "missing-manifest",
                package,
                "package.inspect.read-failed",
                expected_file=package / "manifest.json",
            )
        )

        package, _source, _manifest = make_package(tmp_dir, "bad-reflection-json")
        write_text(package / "reflection.json", "[]\n")
        errors.extend(
            expect_failure(
                cglc,
                "bad-reflection-json",
                package,
                "package.inspect.invalid-json",
                expected_file=package / "reflection.json",
            )
        )

        package, _source, _manifest = make_package(tmp_dir, "bad-manifest-json")
        write_text(package / "manifest.json", "[]\n")
        errors.extend(
            expect_failure(
                cglc,
                "bad-manifest-json",
                package,
                "package.inspect.invalid-json",
                expected_file=package / "manifest.json",
            )
        )

        package, _source, manifest = make_package(tmp_dir, "missing-artifacts")
        missing_artifacts = copy.deepcopy(manifest)
        del missing_artifacts["artifacts"]
        rewrite_manifest(package, missing_artifacts)
        errors.extend(
            expect_failure(
                cglc,
                "missing-artifacts",
                package,
                "package.inspect.missing-artifacts",
                expected_file=package / "manifest.json",
            )
        )

        package, _source, manifest = make_package(tmp_dir, "array-artifacts")
        array_artifacts = copy.deepcopy(manifest)
        array_artifacts["artifacts"] = []
        rewrite_manifest(package, array_artifacts)
        errors.extend(
            expect_failure(
                cglc,
                "array-artifacts",
                package,
                "package.inspect.invalid-artifacts",
                expected_file=package / "manifest.json",
                require_precise_location=True,
            )
        )

        package, _source, manifest = make_package(tmp_dir, "empty-artifacts")
        empty_artifacts = copy.deepcopy(manifest)
        empty_artifacts["artifacts"] = {}
        rewrite_manifest(package, empty_artifacts)
        errors.extend(
            expect_failure(
                cglc,
                "empty-artifacts",
                package,
                "package.inspect.invalid-artifacts",
                expected_file=package / "manifest.json",
                require_precise_location=True,
            )
        )

        package, _source, manifest = make_package(tmp_dir, "duplicate-artifact-key")
        duplicate_manifest_artifact(package, manifest, "backendSource")
        errors.extend(
            expect_failure(
                cglc,
                "duplicate-artifact-key",
                package,
                "package.inspect.duplicate-key",
                expected_file=package / "manifest.json",
                require_precise_location=True,
            )
        )

        package, _source, manifest = make_package(tmp_dir, "non-string-artifact")
        non_string_artifact = copy.deepcopy(manifest)
        non_string_artifact["artifacts"]["backendSource"] = ["backend.hlsl"]
        rewrite_manifest(package, non_string_artifact)
        errors.extend(
            expect_failure(
                cglc,
                "non-string-artifact",
                package,
                "package.inspect.invalid-artifacts",
                expected_file=package / "manifest.json",
                require_precise_location=True,
            )
        )

        package, _source, manifest = make_package(tmp_dir, "missing-module")
        missing_module = copy.deepcopy(manifest)
        del missing_module["module"]
        rewrite_manifest(package, missing_module)
        errors.extend(
            expect_failure(
                cglc,
                "missing-module",
                package,
                "package.inspect.invalid-manifest",
                expected_file=package / "manifest.json",
            )
        )

        package, _source, manifest = make_package(tmp_dir, "non-string-target")
        non_string_target = copy.deepcopy(manifest)
        non_string_target["target"] = 42
        rewrite_manifest(package, non_string_target)
        errors.extend(
            expect_failure(
                cglc,
                "non-string-target",
                package,
                "package.inspect.invalid-manifest",
                expected_file=package / "manifest.json",
            )
        )

        package, _source, manifest = make_package(tmp_dir, "invalid-target")
        invalid_target = copy.deepcopy(manifest)
        invalid_target["target"] = "webgpu"
        rewrite_manifest(package, invalid_target)
        errors.extend(
            expect_failure(
                cglc,
                "invalid-target",
                package,
                "package manifest target is not supported",
                expected_file=package / "manifest.json",
                require_precise_location=True,
            )
        )

        package, _source, manifest = make_package(tmp_dir, "invalid-native-status")
        invalid_status = copy.deepcopy(manifest)
        invalid_status["artifacts"]["nativeBinaryStatus"] = "unknown"
        rewrite_manifest(package, invalid_status)
        errors.extend(
            expect_failure(
                cglc,
                "invalid-native-status",
                package,
                "package manifest nativeBinaryStatus is invalid",
                expected_file=package / "manifest.json",
                require_precise_location=True,
            )
        )

        package, _source, _manifest = make_package(tmp_dir, "json-required")
        errors.extend(
            expect_failure(
                cglc,
                "json-required",
                package,
                "package inspect currently requires --json",
                json_output=False,
            )
        )

        errors.extend(
            expect_args_failure(
                cglc,
                "json-path-required",
                ["package", "inspect", "--json"],
                "Usage:",
            )
        )

    return errors


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--root",
        default=".",
        help="CrossGL-Compiler repository root",
    )
    parser.add_argument("--cglc", required=True, help="path to cglc executable")
    parser.add_argument(
        "--jobs",
        default=None,
        help=(
            "Opt-in worker count for independent fixture cases. Defaults to "
            f"${CROSSGL_PACKAGE_INSPECT_FIXTURE_JOBS} or 1."
        ),
    )
    args = parser.parse_args()

    try:
        jobs = parse_jobs(
            args.jobs
            if args.jobs is not None
            else os.environ.get(CROSSGL_PACKAGE_INSPECT_FIXTURE_JOBS),
            "--jobs" if args.jobs is not None else CROSSGL_PACKAGE_INSPECT_FIXTURE_JOBS,
        )
    except ValueError as exc:
        parser.error(str(exc))

    errors = run_cases(Path(args.root).resolve(), Path(args.cglc).resolve(), jobs=jobs)
    if errors:
        for error in errors:
            print(f"package inspect fixture check failed: {error}", file=sys.stderr)
        return 1

    print("validated package inspect fixtures")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
