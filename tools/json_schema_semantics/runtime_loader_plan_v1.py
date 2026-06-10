"""Semantic checks for runtime-loader-plan-v1.schema.json."""

from collections import Counter

from package_target_contracts import TARGET_REQUIRED_PATH_ARTIFACTS

from .common import add_equal_error


REQUIRED_METADATA_INPUTS = ["manifest.json", "reflection.json", "diagnostics.json"]
SEVERITIES = ("note", "warning", "error")


def validate_diagnostic_counts(errors, instance):
    counts = Counter(diagnostic["severity"] for diagnostic in instance["diagnostics"])
    for severity in SEVERITIES:
        add_equal_error(
            errors,
            f"$.diagnosticCounts.{severity}",
            instance["diagnosticCounts"][severity],
            counts[severity],
            f"{severity} diagnostic count",
        )
    return counts


def validate_metadata_only_contract(errors, instance):
    if instance["metadataOnly"] is not True:
        errors.append("$.metadataOnly: runtime loader plan must be metadata-only")
    if instance["compilerInvocationRequired"] is not False:
        errors.append(
            "$.compilerInvocationRequired: runtime loader plan must not require "
            "compiler invocation"
        )
    if instance["deviceExecutionRequired"] is not False:
        errors.append(
            "$.deviceExecutionRequired: runtime loader plan must not require "
            "device execution"
        )
    if instance["requiredMetadataInputs"] != REQUIRED_METADATA_INPUTS:
        errors.append(
            "$.requiredMetadataInputs: expected stable root metadata inputs "
            f"{REQUIRED_METADATA_INPUTS!r}"
        )


def validate_target_and_mode(errors, instance):
    package_target = instance["packageTarget"]
    requested_target = instance["requestedLoaderTarget"]
    targets_match = (
        package_target is not None
        and requested_target is not None
        and package_target == requested_target
    )
    add_equal_error(
        errors,
        "$.targetMatchesPackage",
        instance["targetMatchesPackage"],
        targets_match,
        "package/requested target equality",
    )

    selected_mode = instance["selectedPackageMode"]
    selected_artifact = instance["selectedArtifact"]
    if instance["success"]:
        if selected_mode is None:
            errors.append("$.selectedPackageMode: successful plan requires mode")
        if selected_artifact is None:
            errors.append("$.selectedArtifact: successful plan requires artifact")
        if not instance["targetMatchesPackage"]:
            errors.append("$.success: successful plan requires matching target")
    else:
        if instance["diagnosticCounts"]["error"] == 0:
            errors.append("$.success: failed plan requires at least one error")

    if selected_artifact is None:
        if selected_mode is not None:
            errors.append(
                "$.selectedPackageMode: must be null when selectedArtifact is null"
            )
        return

    add_equal_error(
        errors,
        "$.selectedArtifact.packageMode",
        selected_artifact["packageMode"],
        selected_mode,
        "$.selectedPackageMode",
    )
    if selected_mode is None:
        errors.append(
            "$.selectedPackageMode: selectedArtifact requires selectedPackageMode"
        )
        return
    expected_artifact = {
        "native": "nativeBinary",
        "source-package": "backendSource",
    }[selected_mode]
    add_equal_error(
        errors,
        "$.selectedArtifact.name",
        selected_artifact["name"],
        expected_artifact,
        f"{selected_mode} artifact",
    )
    if not selected_artifact["packageRelative"]:
        errors.append("$.selectedArtifact.packageRelative: expected true")
    if not selected_artifact["exists"]:
        errors.append("$.selectedArtifact.exists: expected true")
    if selected_artifact["path"].startswith("/") or "\\" in selected_artifact["path"]:
        errors.append("$.selectedArtifact.path: expected normalized package path")

    requested_mode = instance["requestedPackageMode"]
    if requested_mode != "auto" and selected_mode != requested_mode:
        errors.append(
            "$.selectedPackageMode: explicit requestedPackageMode must select "
            f"{requested_mode!r}"
        )


def validate_artifact_requirements(errors, instance):
    requirements = instance["packageArtifactRequirements"]
    package_target = instance["packageTarget"]
    if requirements is None:
        if instance["success"]:
            errors.append(
                "$.packageArtifactRequirements: successful plan requires requirements"
            )
        return

    add_equal_error(
        errors,
        "$.packageArtifactRequirements.target",
        requirements["target"],
        package_target,
        "$.packageTarget",
    )

    expected_artifacts = TARGET_REQUIRED_PATH_ARTIFACTS.get(requirements["target"])
    if expected_artifacts is not None:
        expected_artifacts = list(expected_artifacts)
        if requirements["requiredPathArtifacts"] != expected_artifacts:
            errors.append(
                "$.packageArtifactRequirements.requiredPathArtifacts: expected "
                f"target contract artifacts {expected_artifacts!r}, got "
                f"{requirements['requiredPathArtifacts']!r}"
            )

    selected_artifact = instance["selectedArtifact"]
    if selected_artifact is not None and (
        selected_artifact["name"] not in requirements["requiredPathArtifacts"]
    ):
        errors.append(
            "$.selectedArtifact.name: expected artifact required by package "
            "artifact requirements"
        )


def validate_target_legalization_summary(errors, instance):
    summary = instance["targetLegalizationEvidenceSummary"]
    if summary is None:
        if instance["success"]:
            errors.append(
                "$.targetLegalizationEvidenceSummary: successful plan requires summary"
            )
        return

    if summary["toolRequirementsPresent"]:
        add_equal_error(
            errors,
            "$.targetLegalizationEvidenceSummary.target",
            summary["target"],
            instance["packageTarget"],
            "$.packageTarget",
        )
        if summary["packageMode"] is not None and instance["packageArtifactRequirements"]:
            add_equal_error(
                errors,
                "$.targetLegalizationEvidenceSummary.packageMode",
                summary["packageMode"],
                instance["packageArtifactRequirements"]["packageMode"],
                "$.packageArtifactRequirements.packageMode",
            )
    else:
        for field in ("target", "packageMode"):
            if summary[field] is not None:
                errors.append(
                    f"$.targetLegalizationEvidenceSummary.{field}: expected null "
                    "when tool requirements are absent"
                )

    add_equal_error(
        errors,
        "$.targetLegalizationEvidenceSummary.requiredToolCount",
        summary["requiredToolCount"],
        len(summary["requiredToolIds"]),
        "requiredToolIds length",
    )
    add_equal_error(
        errors,
        "$.targetLegalizationEvidenceSummary.missingToolCount",
        summary["missingToolCount"],
        len(summary["missingToolIds"]),
        "missingToolIds length",
    )


def validate_reflection_summary(errors, instance):
    summary = instance["reflectionSummary"]
    if summary is None:
        if instance["success"]:
            errors.append("$.reflectionSummary: successful plan requires summary")
        return

    if summary["threadgroupShapeSource"] != "reflection.workgroupSizes":
        errors.append(
            "$.reflectionSummary.threadgroupShapeSource: expected "
            "reflection.workgroupSizes"
        )
    if (
        summary["workgroupSizeCount"] is not None
        and summary["entryPointCount"] is not None
        and summary["workgroupSizeCount"] > summary["entryPointCount"]
    ):
        errors.append(
            "$.reflectionSummary.workgroupSizeCount: expected <= entryPointCount"
        )


def validate_semantics(instance):
    errors = []
    counts = validate_diagnostic_counts(errors, instance)
    validate_metadata_only_contract(errors, instance)
    validate_target_and_mode(errors, instance)
    validate_artifact_requirements(errors, instance)
    validate_target_legalization_summary(errors, instance)
    validate_reflection_summary(errors, instance)

    add_equal_error(
        errors,
        "$.success",
        instance["success"],
        counts["error"] == 0,
        "zero-error diagnostic status",
    )
    return errors
