"""Semantic checks for package-verify-v1.schema.json."""

from collections import Counter

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
    validate_native_artifact_descriptor_summary(errors, summary)
    validate_native_ready_descriptor_evidence(errors, summary)
    validate_target_legalization_evidence_summary(errors, summary)


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
