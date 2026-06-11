"""Semantic checks for package-verify-v1.schema.json."""

from collections import Counter
import re

from .common import (
    PACKAGE_TARGETS_REQUIRING_NATIVE_STATUS,
    add_equal_error,
    validate_normalized_package_path,
    validate_package_summary_minimums,
    validate_source_location_span,
)


SEVERITIES = ("note", "warning", "error")
NATIVE_ARTIFACT_OPTIMIZATION_EVIDENCE_FIELDS = (
    "requestedLevel",
    "effectiveLevel",
    "policy",
    "status",
)

TARGET_LEGALIZATION_TOOL_FIELDS = (
    "requiredToolCount",
    "missingToolCount",
    "requiredToolIds",
    "missingToolIds",
    "optionalNativeToolMissing",
    "optionalNativeToolStatus",
    "toolRequirementEvidenceIds",
)
TARGET_LEGALIZATION_EVIDENCE_PREFIX = "target-legalization.v1"
TARGET_LEGALIZATION_RESOURCE_BINDING_EVIDENCE_RE = re.compile(
    r"^target-legalization\.v1\."
    r"(?P<target>metal|vulkan|directx|opengl)\."
    r"resource-binding\.[A-Za-z0-9_.-]+$"
)
TARGET_LEGALIZATION_TARGET_FEATURE_EVIDENCE_RE = re.compile(
    r"^target-legalization\.v1\."
    r"(?P<target>metal|vulkan|directx|opengl)\."
    r"(?:(?:capability\.(?:required|missing)\."
    r"(?P<capability_target>metal|vulkan|directx|opengl)\.[A-Za-z0-9_.-]+)"
    r"|(?:abi\.(?:required|missing)\.[A-Za-z0-9_.-]+))$"
)
LOWERCASE_SHA256 = re.compile(r"^[0-9a-f]{64}$")
TARGET_BACKEND_LANGUAGES = {
    "directx": "hlsl",
    "metal": "msl",
    "opengl": "glsl",
    "vulkan": "spvasm",
}
SOURCE_REMAP_PROVENANCE_CHECKS = (
    "identityMatchesContract",
    "targetMatchesPackage",
    "generatedFilePresent",
    "mappingGranularityMatchesContract",
    "mappingCountPositive",
    "sourcePathPresent",
    "sourceHashPresent",
    "sourceSizeBytesPresent",
)
SOURCE_REMAP_PROVENANCE_CONTENT_FIELDS = (
    "target",
    "generatedFile",
    "mappingGranularity",
    "mappingCount",
    "sourcePath",
    "sourceSha256",
    "sourceSizeBytes",
    "sourceRemapTarget",
    "sourceRemapMappingGranularity",
    "sourceRemapSourceBackend",
    "sourceRemapVariant",
)
BACKEND_SOURCE_MAP_CHECKS = (
    "identityMatchesContract",
    "targetMatchesPackage",
    "moduleMatchesPackage",
    "mappingGranularityMatchesContract",
    "sourceBackendPresent",
    "targetBackendMatchesBackendLanguage",
    "backendLanguagePresent",
    "backendLineCountPresent",
    "backendLineCountMatchesSource",
    "backendSpansWithinSource",
    "mappingCountMatchesMappings",
)
BACKEND_SOURCE_MAP_CONTENT_FIELDS = (
    "target",
    "module",
    "mappingGranularity",
    "sourceBackend",
    "targetBackend",
    "backendLanguage",
    "backendLineCount",
    "backendSourceLineCount",
    "mappingCount",
    "mappingRecordCount",
    "backendMaxMappedLine",
)
VULKAN_NATIVE_PROFILE_CHECKS = (
    "targetMatchesPackage",
    "moduleMatchesPackage",
    "nativeBinaryMatchesManifest",
    "backendAssemblyMatchesManifest",
    "emittedDisassemblyExists",
    "spirvProfilePresent",
)


def validate_diagnostic_counts(errors, diagnostic_counts, diagnostics):
    counts = Counter(diagnostic["severity"] for diagnostic in diagnostics)
    for severity in SEVERITIES:
        add_equal_error(
            errors,
            f"$.diagnosticCounts.{severity}",
            diagnostic_counts[severity],
            counts[severity],
            f"{severity} diagnostic count",
        )
    return counts


def validate_success(errors, success, counts):
    add_equal_error(
        errors,
        "$.success",
        success,
        counts["error"] == 0,
        "no-error diagnostic status",
    )


def validate_summary(errors, success, summary):
    if success and summary is None:
        errors.append("$.summary: successful package verification requires summary")
        return

    if not success or summary is None:
        return

    validate_package_summary_minimums(
        errors,
        "$.summary",
        summary,
        "successful verification",
        artifact_context_label="successful",
        enforce_target_native_status=not has_recorded_native_package_mode(summary),
    )
    validate_source_remap_summary(errors, summary)
    validate_backend_source_map_summary(errors, summary)
    validate_native_artifact_descriptor_summary(errors, summary)
    validate_vulkan_native_profile_summary(errors, summary)
    validate_reflection_summary(errors, summary)
    validate_native_ready_descriptor_evidence(errors, summary)
    validate_target_legalization_evidence_summary(errors, summary)


def validate_reflection_summary(errors, summary):
    reflection = summary.get("reflection")
    if not isinstance(reflection, dict):
        return

    bindings = reflection["selectedTargetResourceBindings"]
    add_equal_error(
        errors,
        "$.summary.reflection.selectedTargetResourceBindingCount",
        reflection["selectedTargetResourceBindingCount"],
        len(bindings),
        "selected target resource binding count",
    )

    target = summary["target"]
    seen_evidence_ids = set()
    for index, binding in enumerate(bindings):
        binding_path = f"$.summary.reflection.selectedTargetResourceBindings[{index}]"
        add_equal_error(
            errors,
            f"{binding_path}.target",
            binding["target"],
            target,
            "$.summary.target",
        )

        evidence_id = binding["evidenceId"]
        if evidence_id is None:
            errors.append(
                f"{binding_path}.evidenceId: successful selected-target "
                "resource binding evidence must not be null"
            )
            continue

        if evidence_id in seen_evidence_ids:
            errors.append(
                f"{binding_path}.evidenceId: duplicate target resource binding "
                f"evidence id {evidence_id!r}"
            )
        seen_evidence_ids.add(evidence_id)

        match = TARGET_LEGALIZATION_RESOURCE_BINDING_EVIDENCE_RE.fullmatch(evidence_id)
        if match is None:
            continue

        expected_prefix = (
            f"{TARGET_LEGALIZATION_EVIDENCE_PREFIX}.{target}.resource-binding."
        )
        if not evidence_id.startswith(expected_prefix):
            errors.append(
                f"{binding_path}.evidenceId: expected target resource binding "
                f"evidence prefix {expected_prefix!r}, got {evidence_id!r}"
            )

    target_feature_count = reflection.get("targetFeatureCount")
    target_feature_evidence_ids = reflection.get("targetFeatureEvidenceIds")
    if target_feature_count is not None and target_feature_count < 0:
        errors.append(
            "$.summary.reflection.targetFeatureCount: expected non-negative count"
        )
    if target_feature_evidence_ids is None:
        return
    if target_feature_count == 0 and target_feature_evidence_ids:
        errors.append(
            "$.summary.reflection.targetFeatureEvidenceIds: expected no evidence IDs "
            "when targetFeatureCount is zero"
        )

    seen_feature_evidence_ids = set()
    expected_feature_prefix = f"{TARGET_LEGALIZATION_EVIDENCE_PREFIX}.{target}."
    for index, evidence_id in enumerate(target_feature_evidence_ids):
        evidence_path = f"$.summary.reflection.targetFeatureEvidenceIds[{index}]"
        if evidence_id in seen_feature_evidence_ids:
            errors.append(
                f"{evidence_path}: duplicate target feature evidence id {evidence_id!r}"
            )
        seen_feature_evidence_ids.add(evidence_id)

        match = TARGET_LEGALIZATION_TARGET_FEATURE_EVIDENCE_RE.fullmatch(evidence_id)
        if match is None:
            continue
        if not evidence_id.startswith(expected_feature_prefix):
            errors.append(
                f"{evidence_path}: expected target feature evidence prefix "
                f"{expected_feature_prefix!r}, got {evidence_id!r}"
            )
            continue

        capability_target = match.group("capability_target")
        if capability_target is not None and capability_target != target:
            errors.append(
                f"{evidence_path}: expected target feature capability evidence "
                f"target {target!r}, got {capability_target!r}"
            )


def validate_native_artifact_descriptor_summary(errors, summary):
    descriptor = summary["nativeArtifactDescriptor"]
    artifact_present = descriptor["artifactPresent"]
    descriptor_exists = descriptor["descriptorExists"]
    health = descriptor["health"]

    if not artifact_present:
        expected = {
            "descriptorExists": False,
            "health": "not-present",
            "path": None,
            "optimizationLevel": None,
            "optimizationEvidence": None,
        }
        for field, expected_value in expected.items():
            add_equal_error(
                errors,
                f"$.summary.nativeArtifactDescriptor.{field}",
                descriptor[field],
                expected_value,
                "absent native artifact descriptor summary",
            )
        return

    if not descriptor_exists:
        add_equal_error(
            errors,
            "$.summary.nativeArtifactDescriptor.health",
            health,
            "incomplete",
            "unreadable native artifact descriptor summary",
        )
        if descriptor["optimizationLevel"] is not None:
            errors.append(
                "$.summary.nativeArtifactDescriptor.optimizationLevel: "
                "expected null when native artifact descriptor is unreadable"
            )
        if descriptor["optimizationEvidence"] is not None:
            errors.append(
                "$.summary.nativeArtifactDescriptor.optimizationEvidence: "
                "expected null when native artifact descriptor is unreadable"
            )
        return

    evidence = descriptor["optimizationEvidence"]
    if not isinstance(evidence, dict):
        return

    for field in NATIVE_ARTIFACT_OPTIMIZATION_EVIDENCE_FIELDS:
        if field not in evidence:
            errors.append(
                "$.summary.nativeArtifactDescriptor.optimizationEvidence: "
                f"missing required optimization evidence field {field!r}"
            )

    if health != "ok":
        errors.append(
            "$.summary.nativeArtifactDescriptor.optimizationEvidence: "
            "expected null unless native artifact descriptor health is ok"
        )

    status = evidence.get("status")
    if status == "applied" and descriptor["optimizationLevel"] is None:
        errors.append(
            "$.summary.nativeArtifactDescriptor.optimizationEvidence.status: "
            "applied optimization evidence requires optimizationLevel"
        )
    if status == "applied" and summary["nativeBinaryStatus"] == "planned":
        errors.append(
            "$.summary.nativeArtifactDescriptor.optimizationEvidence.status: "
            "planned source-package descriptors must not claim applied optimization"
        )


def validate_source_remap_summary(errors, summary):
    source_remap = summary.get("sourceRemap")
    if not isinstance(source_remap, dict):
        return

    artifact_present = source_remap["artifactPresent"]
    exists = source_remap["exists"]
    checks = source_remap["checks"]
    check_values = [checks[name] for name in SOURCE_REMAP_PROVENANCE_CHECKS]

    if artifact_present and not summary["debugArtifactsPresent"]:
        errors.append(
            "$.summary.sourceRemap.artifactPresent: sourceRemap provenance "
            "requires debug artifacts"
        )

    if not artifact_present:
        add_equal_error(
            errors,
            "$.summary.sourceRemap.exists",
            exists,
            False,
            "absent sourceRemap artifact file existence",
        )
        expected_health = "not-present"
        expected_checks = [None] * len(check_values)
        for field in ("path", *SOURCE_REMAP_PROVENANCE_CONTENT_FIELDS):
            if source_remap.get(field) is not None:
                errors.append(
                    f"$.summary.sourceRemap.{field}: expected null when absent"
                )
    elif not exists:
        expected_health = "incomplete"
        expected_checks = [None] * len(check_values)
        for field in SOURCE_REMAP_PROVENANCE_CONTENT_FIELDS:
            if source_remap.get(field) is not None:
                errors.append(
                    f"$.summary.sourceRemap.{field}: expected null when unreadable"
                )
    else:
        add_equal_error(
            errors,
            "$.summary.sourceRemap.checks.targetMatchesPackage",
            checks["targetMatchesPackage"],
            source_remap["target"] == summary["target"],
            "sourceRemap provenance target matches package",
        )
        add_equal_error(
            errors,
            "$.summary.sourceRemap.checks.generatedFilePresent",
            checks["generatedFilePresent"],
            bool(source_remap["generatedFile"]),
            "sourceRemap provenance generatedFile presence",
        )
        add_equal_error(
            errors,
            "$.summary.sourceRemap.checks.mappingGranularityMatchesContract",
            checks["mappingGranularityMatchesContract"],
            source_remap["mappingGranularity"] == "source-span",
            "sourceRemap provenance mappingGranularity contract",
        )
        add_equal_error(
            errors,
            "$.summary.sourceRemap.checks.mappingCountPositive",
            checks["mappingCountPositive"],
            source_remap["mappingCount"] is not None
            and source_remap["mappingCount"] > 0,
            "sourceRemap provenance positive mapping count",
        )
        add_equal_error(
            errors,
            "$.summary.sourceRemap.checks.sourcePathPresent",
            checks["sourcePathPresent"],
            bool(source_remap["sourcePath"]),
            "sourceRemap provenance source path presence",
        )
        add_equal_error(
            errors,
            "$.summary.sourceRemap.checks.sourceHashPresent",
            checks["sourceHashPresent"],
            source_remap["sourceSha256"] is not None
            and LOWERCASE_SHA256.fullmatch(source_remap["sourceSha256"]) is not None,
            "sourceRemap provenance source hash presence",
        )
        add_equal_error(
            errors,
            "$.summary.sourceRemap.checks.sourceSizeBytesPresent",
            checks["sourceSizeBytesPresent"],
            source_remap["sourceSizeBytes"] is not None,
            "sourceRemap provenance source size presence",
        )
        expected_health = (
            "ok" if all(value is True for value in check_values) else "drift"
        )
        expected_checks = None

    add_equal_error(
        errors,
        "$.summary.sourceRemap.health",
        source_remap["health"],
        expected_health,
        "sourceRemap provenance health from checks",
    )
    if expected_checks is not None and check_values != expected_checks:
        errors.append(
            "$.summary.sourceRemap.checks: expected null checks when absent "
            "or incomplete"
        )


def validate_backend_source_map_summary(errors, summary):
    backend_source_map = summary.get("backendSourceMap")
    if not isinstance(backend_source_map, dict):
        return

    artifact_present = backend_source_map["artifactPresent"]
    exists = backend_source_map["exists"]
    checks = backend_source_map["checks"]
    check_values = [checks[name] for name in BACKEND_SOURCE_MAP_CHECKS]

    if artifact_present and not summary["debugArtifactsPresent"]:
        errors.append(
            "$.summary.backendSourceMap.artifactPresent: backendSourceMap "
            "requires debug artifacts"
        )

    if not artifact_present:
        add_equal_error(
            errors,
            "$.summary.backendSourceMap.exists",
            exists,
            False,
            "absent backendSourceMap artifact file existence",
        )
        expected_health = "not-present"
        expected_checks = [None] * len(check_values)
        for field in ("path", *BACKEND_SOURCE_MAP_CONTENT_FIELDS):
            if backend_source_map[field] is not None:
                errors.append(
                    f"$.summary.backendSourceMap.{field}: expected null when absent"
                )
    elif not exists:
        expected_health = "incomplete"
        expected_checks = [None] * len(check_values)
        for field in BACKEND_SOURCE_MAP_CONTENT_FIELDS:
            if backend_source_map[field] is not None:
                errors.append(
                    f"$.summary.backendSourceMap.{field}: expected null when unreadable"
                )
    else:
        add_equal_error(
            errors,
            "$.summary.backendSourceMap.checks.targetMatchesPackage",
            checks["targetMatchesPackage"],
            backend_source_map["target"] == summary["target"],
            "backendSourceMap target matches package",
        )
        add_equal_error(
            errors,
            "$.summary.backendSourceMap.checks.moduleMatchesPackage",
            checks["moduleMatchesPackage"],
            backend_source_map["module"] == summary["module"],
            "backendSourceMap module matches package",
        )
        add_equal_error(
            errors,
            "$.summary.backendSourceMap.checks.mappingGranularityMatchesContract",
            checks["mappingGranularityMatchesContract"],
            backend_source_map["mappingGranularity"] == "statement",
            "backendSourceMap mapping granularity contract",
        )
        add_equal_error(
            errors,
            "$.summary.backendSourceMap.checks.sourceBackendPresent",
            checks["sourceBackendPresent"],
            bool(backend_source_map["sourceBackend"]),
            "backendSourceMap source backend presence",
        )
        add_equal_error(
            errors,
            "$.summary.backendSourceMap.checks.targetBackendMatchesBackendLanguage",
            checks["targetBackendMatchesBackendLanguage"],
            isinstance(backend_source_map["targetBackend"], str)
            and isinstance(backend_source_map["backendLanguage"], str)
            and backend_source_map["targetBackend"]
            == backend_source_map["backendLanguage"],
            "backendSourceMap target backend language agreement",
        )
        add_equal_error(
            errors,
            "$.summary.backendSourceMap.checks.backendLanguagePresent",
            checks["backendLanguagePresent"],
            bool(backend_source_map["backendLanguage"]),
            "backendSourceMap backend language presence",
        )
        expected_backend_language = TARGET_BACKEND_LANGUAGES.get(summary["target"])
        if expected_backend_language is not None:
            if backend_source_map["targetBackend"] != expected_backend_language:
                errors.append(
                    "$.summary.backendSourceMap.targetBackend: expected "
                    f"{expected_backend_language!r} for {summary['target']} "
                    "package target"
                )
            if backend_source_map["backendLanguage"] != expected_backend_language:
                errors.append(
                    "$.summary.backendSourceMap.backendLanguage: expected "
                    f"{expected_backend_language!r} for {summary['target']} "
                    "package target"
                )
        add_equal_error(
            errors,
            "$.summary.backendSourceMap.checks.backendLineCountPresent",
            checks["backendLineCountPresent"],
            backend_source_map["backendLineCount"] is not None,
            "backendSourceMap backend line count presence",
        )
        if (
            backend_source_map["backendLineCount"] is not None
            and backend_source_map["backendSourceLineCount"] is not None
        ):
            expected_line_count_matches_source = (
                backend_source_map["backendLineCount"]
                == backend_source_map["backendSourceLineCount"]
            )
        else:
            expected_line_count_matches_source = None
        add_equal_error(
            errors,
            "$.summary.backendSourceMap.checks.backendLineCountMatchesSource",
            checks["backendLineCountMatchesSource"],
            expected_line_count_matches_source,
            "backendSourceMap backend line count matches source",
        )
        if (
            backend_source_map["backendSourceLineCount"] is not None
            and backend_source_map["backendMaxMappedLine"] is not None
        ):
            expected_spans_within_source = (
                backend_source_map["backendMaxMappedLine"]
                <= backend_source_map["backendSourceLineCount"]
            )
        else:
            expected_spans_within_source = None
        add_equal_error(
            errors,
            "$.summary.backendSourceMap.checks.backendSpansWithinSource",
            checks["backendSpansWithinSource"],
            expected_spans_within_source,
            "backendSourceMap backend spans within source",
        )
        add_equal_error(
            errors,
            "$.summary.backendSourceMap.checks.mappingCountMatchesMappings",
            checks["mappingCountMatchesMappings"],
            backend_source_map["mappingCount"] is not None
            and backend_source_map["mappingRecordCount"] is not None
            and backend_source_map["mappingCount"]
            == backend_source_map["mappingRecordCount"],
            "backendSourceMap mapping count agreement",
        )
        required_checks = [
            checks[name]
            for name in BACKEND_SOURCE_MAP_CHECKS
            if name not in ("backendLineCountMatchesSource", "backendSpansWithinSource")
        ]
        source_comparison_checks = [
            checks["backendLineCountMatchesSource"],
            checks["backendSpansWithinSource"],
        ]
        expected_health = (
            "ok"
            if all(value is True for value in required_checks)
            and all(value in (True, None) for value in source_comparison_checks)
            else "drift"
        )
        expected_checks = None

    add_equal_error(
        errors,
        "$.summary.backendSourceMap.health",
        backend_source_map["health"],
        expected_health,
        "backendSourceMap health from checks",
    )
    if expected_checks is not None and check_values != expected_checks:
        errors.append(
            "$.summary.backendSourceMap.checks: expected null checks when absent "
            "or incomplete"
        )


def validate_vulkan_native_profile_summary(errors, summary):
    profile = summary.get("vulkanNativeProfile")
    if not isinstance(profile, dict):
        return

    is_vulkan = summary["target"] == "vulkan"
    profile_declared = profile["nativeProfileArtifactPresent"]
    profile_exists = profile["nativeProfileExists"]
    checks = profile["checks"]
    check_values = [checks[name] for name in VULKAN_NATIVE_PROFILE_CHECKS]
    health_check_values = [
        checks[name]
        for name in VULKAN_NATIVE_PROFILE_CHECKS
        if name != "emittedDisassemblyExists" or checks[name] is not None
    ]

    add_equal_error(
        errors,
        "$.summary.vulkanNativeProfile.applicable",
        profile["applicable"],
        is_vulkan,
        "Vulkan profile applicability",
    )
    if not profile_declared:
        add_equal_error(
            errors,
            "$.summary.vulkanNativeProfile.nativeProfileExists",
            profile_exists,
            False,
            "absent nativeProfile artifact file existence",
        )

    if not is_vulkan:
        expected_health = "not-applicable"
        expected_checks = [None] * len(check_values)
    elif not profile_declared or not profile_exists:
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
        "$.summary.vulkanNativeProfile.health",
        profile["health"],
        expected_health,
        "Vulkan native profile health from checks",
    )
    if expected_checks is not None and check_values != expected_checks:
        errors.append(
            "$.summary.vulkanNativeProfile.checks: expected null checks when inactive"
        )


def validate_native_ready_descriptor_evidence(errors, summary):
    native_binary_status = summary["nativeBinaryStatus"]
    native_ready = (
        has_recorded_native_package_mode(summary)
        or summary["target"] not in PACKAGE_TARGETS_REQUIRING_NATIVE_STATUS
        or native_binary_status
        in {
            "emitted",
            "validated",
        }
    )
    if not native_ready:
        return

    descriptor = summary["nativeArtifactDescriptor"]
    if not descriptor["artifactPresent"]:
        errors.append(
            "$.summary.nativeArtifactDescriptor.artifactPresent: "
            "native-ready package verification requires "
            "nativeArtifactDescriptor artifact evidence"
        )
    elif not descriptor["descriptorExists"] or descriptor["health"] != "ok":
        errors.append(
            "$.summary.nativeArtifactDescriptor.health: native-ready package "
            "verification requires readable nativeArtifactDescriptor evidence "
            "with health 'ok'"
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


def has_recorded_native_package_mode(summary):
    evidence = summary.get("targetLegalizationEvidence")
    return (
        isinstance(evidence, dict)
        and evidence.get("packageModeSource") == "manifest.packageArtifactRequirements"
        and evidence.get("packageMode") == "native"
    )


def expected_target_legalization_evidence_health(evidence):
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

    expected_requirement_ids = evidence["packageArtifactRequirementEvidenceIds"]
    if expected_requirement_ids is not None:
        for sidecar_name in ("debugMetadata", "targetExplanation"):
            sidecar_ids = evidence[sidecar_name][
                "packageArtifactRequirementEvidenceIds"
            ]
            if sidecar_ids is not None and sidecar_ids != expected_requirement_ids:
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
    path,
    manifest_tool_requirements,
    evidence,
    summary,
):
    if not manifest_tool_requirements["present"]:
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
                    "$.summary.targetLegalizationEvidence.checks."
                    f"{check_name}: expected null when manifest tool "
                    "requirements are absent"
                )
        return

    validate_target_legalization_tool_sidecar_fields(
        errors,
        path,
        manifest_tool_requirements,
    )
    add_equal_error(
        errors,
        "$.summary.targetLegalizationEvidence.checks."
        "manifestToolRequirementsTargetMatchesPackage",
        evidence["checks"]["manifestToolRequirementsTargetMatchesPackage"],
        manifest_tool_requirements["target"] == summary["target"],
        "manifest tool requirements target matches package",
    )
    if evidence["packageModeSource"] == "manifest.packageArtifactRequirements":
        add_equal_error(
            errors,
            "$.summary.targetLegalizationEvidence.checks."
            "manifestToolRequirementsPackageModeMatchesRequirements",
            evidence["checks"][
                "manifestToolRequirementsPackageModeMatchesRequirements"
            ],
            manifest_tool_requirements["packageMode"] == evidence["packageMode"],
            "manifest tool requirements packageMode matches requirements",
        )
    add_equal_error(
        errors,
        "$.summary.targetLegalizationEvidence.checks."
        "manifestToolRequirementEvidenceIdsPresent",
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
            "$.summary.targetLegalizationEvidence.missingEvidence: expected "
            "manifest targetLegalizationToolRequirements evidence marker"
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


def validate_target_legalization_evidence_summary(errors, summary):
    evidence = summary.get("targetLegalizationEvidence")
    if evidence is None:
        return

    expected_health = expected_target_legalization_evidence_health(evidence)
    add_equal_error(
        errors,
        "$.summary.targetLegalizationEvidence.health",
        evidence["health"],
        expected_health,
        "target legalization evidence health",
    )

    validate_target_legalization_manifest_tool_requirements(
        errors,
        "$.summary.targetLegalizationEvidence.manifestToolRequirements",
        evidence["manifestToolRequirements"],
        evidence,
        summary,
    )

    if evidence["packageModeSource"] == "manifest.packageArtifactRequirements":
        if evidence["packageMode"] not in {"native", "source-package"}:
            errors.append(
                "$.summary.targetLegalizationEvidence.packageMode: expected "
                "manifest package mode"
            )
        ids_present = evidence_ids_present(
            evidence["packageArtifactRequirementEvidenceIds"]
        )
        add_equal_error(
            errors,
            "$.summary.targetLegalizationEvidence.checks."
            "packageArtifactRequirementEvidenceIdsPresent",
            evidence["checks"]["packageArtifactRequirementEvidenceIdsPresent"],
            ids_present,
            "package artifact requirement evidence presence",
        )
        if (
            not ids_present
            and "packageArtifactRequirementEvidenceIds"
            not in evidence["missingEvidence"]
        ):
            errors.append(
                "$.summary.targetLegalizationEvidence.missingEvidence: expected "
                "packageArtifactRequirementEvidenceIds marker"
            )
        validate_sidecar_requirement_evidence_ids(
            errors,
            "$.summary.targetLegalizationEvidence.debugMetadata",
            evidence["debugMetadata"],
            evidence["packageArtifactRequirementEvidenceIds"],
        )
        validate_sidecar_requirement_evidence_ids(
            errors,
            "$.summary.targetLegalizationEvidence.targetExplanation",
            evidence["targetExplanation"],
            evidence["packageArtifactRequirementEvidenceIds"],
        )

    for sidecar_name, check_prefix in (
        ("debugMetadata", "debugMetadata"),
        ("targetExplanation", "targetExplanation"),
    ):
        sidecar = evidence[sidecar_name]
        validate_target_legalization_tool_sidecar_fields(
            errors,
            f"$.summary.targetLegalizationEvidence.{sidecar_name}",
            sidecar,
        )
        if sidecar["target"] is not None:
            add_equal_error(
                errors,
                "$.summary.targetLegalizationEvidence.checks."
                f"{check_prefix}TargetMatchesPackage",
                evidence["checks"][f"{check_prefix}TargetMatchesPackage"],
                sidecar["target"] == summary["target"],
                f"{sidecar_name} target matches package",
            )
        if (
            evidence["packageMode"] is not None
            and sidecar["packageMode"] is not None
            and evidence["packageModeSource"] == "manifest.packageArtifactRequirements"
        ):
            add_equal_error(
                errors,
                "$.summary.targetLegalizationEvidence.checks."
                f"{check_prefix}PackageModeMatchesRequirements",
                evidence["checks"][f"{check_prefix}PackageModeMatchesRequirements"],
                sidecar["packageMode"] == evidence["packageMode"],
                f"{sidecar_name} packageMode matches requirements",
            )
        expected_tool_match = target_tool_sidecar_matches_manifest(
            evidence["manifestToolRequirements"],
            sidecar,
        )
        add_equal_error(
            errors,
            "$.summary.targetLegalizationEvidence.checks."
            f"{check_prefix}ToolRequirementsMatchManifest",
            evidence["checks"][f"{check_prefix}ToolRequirementsMatchManifest"],
            expected_tool_match,
            f"{sidecar_name} tool requirements match manifest",
        )


def validate_diagnostic_target(errors, diagnostic_path, diagnostic, summary):
    target = diagnostic.get("target")
    missing_capabilities = diagnostic.get("missingCapabilities", [])

    if missing_capabilities and target is None:
        errors.append(
            f"{diagnostic_path}.missingCapabilities: expected diagnostic target"
        )
        return

    if target is not None and summary is not None and target != summary["target"]:
        errors.append(
            f"{diagnostic_path}.target: expected summary target "
            f"{summary['target']!r}, got {target!r}"
        )

    if target is None:
        return

    expected_prefix = f"{target}."
    for capability_index, capability in enumerate(missing_capabilities):
        if not capability.startswith(expected_prefix):
            errors.append(
                f"{diagnostic_path}.missingCapabilities[{capability_index}]: "
                f"expected {expected_prefix!r} capability prefix"
            )


def validate_diagnostics(errors, diagnostics, summary):
    for index, diagnostic in enumerate(diagnostics):
        diagnostic_path = f"$.diagnostics[{index}]"
        if not diagnostic["code"].startswith("package.verify."):
            errors.append(f"{diagnostic_path}.code: expected package.verify. prefix")
        validate_diagnostic_target(errors, diagnostic_path, diagnostic, summary)
        validate_source_location_span(
            errors,
            f"{diagnostic_path}.location",
            diagnostic["location"],
        )


def validate_semantics(instance):
    errors = []
    diagnostics = instance["diagnostics"]
    counts = validate_diagnostic_counts(
        errors,
        instance["diagnosticCounts"],
        diagnostics,
    )
    validate_success(errors, instance["success"], counts)
    validate_summary(errors, instance["success"], instance["summary"])
    validate_normalized_package_path(errors, "$.packagePath", instance["packagePath"])
    validate_diagnostics(errors, diagnostics, instance["summary"])
    return errors
