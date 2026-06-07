"""Semantic checks for package-release-bundle-verification-v1.schema.json."""

from collections import Counter

from .common import add_equal_error, validate_source_location_span


SEVERITIES = ("note", "warning", "error")


def validate_bundle_path(errors, path, value):
    normalized = value.strip()
    if normalized == "":
        errors.append(f"{path}: expected non-empty path")
        return
    if normalized != value:
        errors.append(f"{path}: expected normalized relative path")
    if "\\" in value:
        errors.append(f"{path}: expected normalized '/' separators")
    if value.startswith("/"):
        errors.append(f"{path}: expected relative path")
    parts = value.split("/")
    if any(part in ("", ".", "..") for part in parts):
        errors.append(f"{path}: expected normalized relative path")


def validate_semantics(instance):
    errors = []
    diagnostics = instance["diagnostics"]
    counts = Counter(diagnostic["severity"] for diagnostic in diagnostics)

    validate_bundle_path(errors, "$.bundlePath", instance["bundlePath"])

    for severity in SEVERITIES:
        add_equal_error(
            errors,
            f"$.diagnosticCounts.{severity}",
            instance["diagnosticCounts"][severity],
            counts[severity],
            f"{severity} diagnostic count",
        )

    add_equal_error(
        errors,
        "$.artifactCount",
        instance["artifactCount"],
        instance["existingArtifactCount"] + instance["missingArtifactCount"],
        "existing plus missing artifact count",
    )
    if instance["verifiedArtifactCount"] > instance["existingArtifactCount"]:
        errors.append("$.verifiedArtifactCount: expected <= existingArtifactCount")

    expected_success = (
        instance["releaseEligible"] and instance["diagnosticCounts"]["error"] == 0
    )
    add_equal_error(
        errors,
        "$.success",
        instance["success"],
        expected_success,
        "eligible no-error verification status",
    )
    if expected_success:
        add_equal_error(
            errors,
            "$.verifiedArtifactCount",
            instance["verifiedArtifactCount"],
            instance["existingArtifactCount"],
            "verified artifact count for successful verification",
        )
    if instance["diagnosticCounts"]["error"] == 0:
        add_equal_error(
            errors,
            "$.status",
            instance["status"],
            "eligible" if instance["releaseEligible"] else "blocked",
            "release status",
        )
    if instance["status"] == "eligible" and not instance["releaseEligible"]:
        errors.append("$.releaseEligible: eligible status requires true")
    if instance["status"] == "blocked" and instance["releaseEligible"]:
        errors.append("$.releaseEligible: blocked status requires false")
    if instance["status"] == "invalid" and instance["diagnosticCounts"]["error"] == 0:
        errors.append("$.status: invalid status requires at least one error")
    if instance["status"] == "invalid" and instance["releaseEligible"]:
        errors.append("$.releaseEligible: invalid status requires false")
    if instance["releaseEligible"] and instance["blockerCount"] != 0:
        errors.append(
            "$.blockerCount: release eligible verification must not report blockers"
        )
    if instance["status"] == "blocked" and instance["blockerCount"] <= 0:
        errors.append(
            "$.blockerCount: blocked verification requires at least one blocker"
        )

    for index, diagnostic in enumerate(diagnostics):
        diagnostic_path = f"$.diagnostics[{index}]"
        if not diagnostic["code"].startswith("package.release.bundle."):
            errors.append(
                f"{diagnostic_path}.code: expected package.release.bundle. prefix"
            )
        if diagnostic["message"].strip() == "":
            errors.append(
                f"{diagnostic_path}.message: expected non-empty diagnostic message"
            )
        validate_source_location_span(
            errors,
            f"{diagnostic_path}.location",
            diagnostic["location"],
        )

    return errors
