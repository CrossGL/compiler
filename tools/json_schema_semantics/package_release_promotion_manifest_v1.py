"""Semantic checks for package-release-promotion-manifest-v1.schema.json."""

from collections import Counter

from .common import (
    add_equal_error,
    add_length_count_error,
    validate_native_binary_state,
    validate_release_package_artifacts_against_requirements,
    validate_target_feature_reflection_summary,
)
from .package_maintenance_set_verification_v1 import SEVERITIES


def validate_diagnostic_counts(errors, path, counts):
    for severity in SEVERITIES:
        if counts[severity] < 0:
            errors.append(f"{path}.{severity}: expected non-negative count")


def validate_relative_path(errors, path, value):
    if value == "":
        errors.append(f"{path}: expected non-empty path")
        return
    if "\\" in value:
        errors.append(f"{path}: expected normalized '/' separators")
    if value.startswith("/"):
        errors.append(f"{path}: expected relative path")
    parts = value.split("/")
    if any(part in ("", ".", "..") for part in parts):
        errors.append(f"{path}: expected normalized relative path")


def validate_evidence_path(errors, path, value):
    if value == "":
        errors.append(f"{path}: expected non-empty path")
        return
    if value.strip() != value:
        errors.append(f"{path}: expected normalized relative path")
    validate_relative_path(errors, path, value)


def validate_summary_counts(errors, summary):
    expected_release_eligible = summary["success"] and summary["matches"]
    add_equal_error(
        errors,
        "$.summary.releaseEligible",
        summary["releaseEligible"],
        expected_release_eligible,
        "summary release eligibility",
    )

    verification_claims = (
        summary["matchedCount"] + summary["mismatchedCount"] + summary["failedCount"]
    )
    if verification_claims > summary["verificationCount"]:
        errors.append(
            "$.summary.verificationCount: expected >= matched+mismatched+failed counts"
        )
    if summary["missingFromSetCount"] > summary["scannedPackageCount"]:
        errors.append("$.summary.missingFromSetCount: expected <= scannedPackageCount")
    if summary["extraInSetCount"] > summary["setPackageCount"]:
        errors.append("$.summary.extraInSetCount: expected <= setPackageCount")

    if summary["success"] and not summary["matches"]:
        errors.append("$.summary.success: expected false when summary does not match")
    if summary["success"] and summary["diagnosticCounts"]["error"] != 0:
        errors.append("$.summary.success: expected no error diagnostics")

    if summary["matches"]:
        for field in (
            "mismatchedCount",
            "failedCount",
            "missingFromSetCount",
            "extraInSetCount",
        ):
            if summary[field] != 0:
                errors.append(f"$.summary.{field}: expected zero when matches")

    if summary["releaseEligible"]:
        if summary["verificationCount"] == 0:
            errors.append(
                "$.summary.verificationCount: release eligible summary "
                "requires at least one verification"
            )
        if summary["diagnosticCounts"]["error"] != 0:
            errors.append(
                "$.summary.diagnosticCounts.error: release eligible summary "
                "requires zero errors"
            )


def validate_semantics(instance):
    errors = []
    summary = instance["summary"]

    for field in ("summaryPath", "manifestPath", "batchPath"):
        validate_evidence_path(errors, f"$.{field}", instance[field])
    for field in ("summaryPath", "batchPath"):
        validate_evidence_path(errors, f"$.summary.{field}", summary[field])

    add_equal_error(
        errors,
        "$.summaryPath",
        instance["summaryPath"],
        summary["summaryPath"],
        "summary path",
    )
    add_equal_error(
        errors,
        "$.batchPath",
        instance["batchPath"],
        summary["batchPath"],
        "batch path",
    )
    add_equal_error(
        errors,
        "$.diagnosticCounts",
        instance["diagnosticCounts"],
        summary["diagnosticCounts"],
        "diagnostic counts",
    )

    add_length_count_error(
        errors,
        "$.blockerCount",
        instance["blockerCount"],
        instance["blockers"],
        "blocker length",
    )
    add_length_count_error(
        errors,
        "$.packageCount",
        instance["packageCount"],
        instance["packages"],
        "package length",
    )

    blocker_codes = [blocker["code"] for blocker in instance["blockers"]]
    if blocker_codes != sorted(blocker_codes):
        errors.append("$.blockers: blocker codes must be sorted")
    if len(blocker_codes) != len(set(blocker_codes)):
        errors.append("$.blockers: duplicate blocker codes")
    for index, blocker in enumerate(instance["blockers"]):
        if blocker["code"] == "":
            errors.append(f"$.blockers[{index}].code: expected non-empty code")
        if blocker["message"] == "":
            errors.append(f"$.blockers[{index}].message: expected non-empty message")
        if blocker["count"] <= 0:
            errors.append(f"$.blockers[{index}].count: expected positive count")

    package_paths = [package["packagePath"] for package in instance["packages"]]
    if package_paths != sorted(package_paths):
        errors.append("$.packages: package paths must be sorted")
    if len(package_paths) != len(set(package_paths)):
        errors.append("$.packages: duplicate package paths")
    package_targets = [
        (package["module"], package["target"]) for package in instance["packages"]
    ]
    package_target_counts = Counter(package_targets)
    if len(package_targets) != len(package_target_counts):
        duplicates = sorted(
            package_target
            for package_target, count in package_target_counts.items()
            if count > 1
        )
        errors.append(f"$.packages: duplicate package target record {duplicates[0]!r}")
    for package_index, package in enumerate(instance["packages"]):
        package_path = f"$.packages[{package_index}]"
        if package["packagePath"] == "":
            errors.append(f"{package_path}.packagePath: expected non-empty path")
        if package["module"] == "":
            errors.append(f"{package_path}.module: expected non-empty module")
        if instance["releaseEligible"] and package["sourceHash"] is None:
            errors.append(
                f"{package_path}.sourceHash: release eligible manifest requires sourceHash"
            )
        validate_release_package_artifacts_against_requirements(
            errors, package_path, package
        )
        validate_target_feature_reflection_summary(
            errors,
            f"{package_path}.reflection",
            package["target"],
            package["reflection"],
        )
        validate_native_binary_state(errors, package_path, package)
        add_length_count_error(
            errors,
            f"{package_path}.artifactCount",
            package["artifactCount"],
            package["artifacts"],
            "artifact length",
        )
        artifact_names = [artifact["name"] for artifact in package["artifacts"]]
        if artifact_names != sorted(artifact_names):
            errors.append(f"{package_path}.artifacts: artifact names must be sorted")
        if len(artifact_names) != len(set(artifact_names)):
            errors.append(f"{package_path}.artifacts: duplicate artifact names")
        for artifact_index, artifact in enumerate(package["artifacts"]):
            artifact_path = f"{package_path}.artifacts[{artifact_index}]"
            if artifact["name"] == "":
                errors.append(f"{artifact_path}.name: expected non-empty name")
            if artifact["path"] == "":
                errors.append(f"{artifact_path}.path: expected non-empty path")
            validate_relative_path(errors, f"{artifact_path}.path", artifact["path"])
            if artifact["exists"]:
                if artifact["sizeBytes"] is None:
                    errors.append(
                        f"{artifact_path}.sizeBytes: existing artifact requires size"
                    )
                if artifact["sha256"] is None:
                    errors.append(
                        f"{artifact_path}.sha256: existing artifact requires digest"
                    )
            else:
                if artifact["sizeBytes"] is not None:
                    errors.append(
                        f"{artifact_path}.sizeBytes: missing artifact must use null"
                    )
                if artifact["sha256"] is not None:
                    errors.append(
                        f"{artifact_path}.sha256: missing artifact must use null"
                    )

    validate_diagnostic_counts(
        errors, "$.diagnosticCounts", instance["diagnosticCounts"]
    )
    validate_diagnostic_counts(
        errors,
        "$.summary.diagnosticCounts",
        summary["diagnosticCounts"],
    )
    validate_summary_counts(errors, summary)

    expected_release_eligible = (
        summary["releaseEligible"]
        and summary["success"]
        and summary["matches"]
        and instance["diagnosticCounts"]["error"] == 0
        and instance["blockerCount"] == 0
    )
    add_equal_error(
        errors,
        "$.releaseEligible",
        instance["releaseEligible"],
        expected_release_eligible,
        "release eligibility",
    )
    add_equal_error(
        errors,
        "$.status",
        instance["status"],
        "eligible" if instance["releaseEligible"] else "blocked",
        "release status",
    )

    if instance["releaseEligible"] and instance["blockers"]:
        errors.append("$.blockers: release eligible manifest must not have blockers")
    if not instance["releaseEligible"] and not instance["blockers"]:
        errors.append("$.blockers: blocked manifest requires at least one blocker")

    return errors
