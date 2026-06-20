"""Semantic checks for package-release-publish-receipt-v1.schema.json."""

from collections import Counter
from pathlib import PurePosixPath

from .common import (
    add_equal_error,
    add_length_count_error,
    validate_diagnostic_message,
    validate_source_location_span,
)


SEVERITIES = ("note", "warning", "error")


def validate_relative_path(errors, path, value):
    if value == "":
        errors.append(f"{path}: expected non-empty path")
    if "\\" in value:
        errors.append(f"{path}: expected normalized '/' separators")
    if value.startswith("/"):
        errors.append(f"{path}: expected relative path")
    parts = value.split("/")
    if any(part in ("", ".", "..") for part in parts):
        errors.append(f"{path}: expected normalized relative path")


def validate_source_path(errors, path, artifact):
    if artifact["sourcePath"].endswith("/" + artifact["packageArtifactPath"]):
        return
    if (
        artifact["sourcePath"]
        == artifact["packagePath"] + "/" + artifact["packageArtifactPath"]
    ):
        return
    errors.append(f"{path}.sourcePath: expected packagePath/packageArtifactPath")


def validate_artifact(errors, path, artifact, target_path):
    for field in (
        "name",
        "packagePath",
        "module",
        "sourcePath",
        "stagedPath",
        "publishedPath",
    ):
        if artifact[field] == "":
            errors.append(f"{path}.{field}: expected non-empty value")
    validate_relative_path(
        errors,
        f"{path}.packageArtifactPath",
        artifact["packageArtifactPath"],
    )
    validate_relative_path(
        errors, f"{path}.destinationPath", artifact["destinationPath"]
    )
    validate_source_path(errors, path, artifact)
    expected_published_path = str(
        PurePosixPath(target_path) / artifact["destinationPath"]
    )
    if artifact["publishedPath"] != expected_published_path:
        errors.append(f"{path}.publishedPath: expected targetPath/destinationPath")
    if artifact["published"] and not artifact["staged"]:
        errors.append(f"{path}.published: expected staged artifact before publish")


def validate_semantics(instance):
    errors = []

    for field in ("stageReportPath", "targetPath"):
        if instance[field] == "":
            errors.append(f"$.{field}: expected non-empty path")
    if instance["targetKind"] == "":
        errors.append("$.targetKind: expected non-empty target kind")
    if instance["targetKind"] != "local-filesystem":
        errors.append("$.targetKind: expected local-filesystem for v1 receipt")
    if instance["receiptWritten"] and instance["receiptPath"] == "":
        errors.append("$.receiptPath: expected non-empty path when receiptWritten")

    diagnostics = instance["diagnostics"]
    counts = Counter(diagnostic["severity"] for diagnostic in diagnostics)
    for severity in SEVERITIES:
        add_equal_error(
            errors,
            f"$.diagnosticCounts.{severity}",
            instance["diagnosticCounts"][severity],
            counts[severity],
            f"{severity} diagnostic count",
        )

    artifacts = instance["artifacts"]
    add_length_count_error(
        errors,
        "$.artifactCount",
        instance["artifactCount"],
        artifacts,
        "artifact length",
    )
    destination_paths = [artifact["destinationPath"] for artifact in artifacts]
    if destination_paths != sorted(destination_paths):
        errors.append("$.artifacts: destination paths must be sorted")
    if len(destination_paths) != len(set(destination_paths)):
        errors.append("$.artifacts: duplicate destination paths")

    package_identities = {
        (artifact["packagePath"], artifact["module"], artifact["target"])
        for artifact in artifacts
    }
    add_equal_error(
        errors,
        "$.packageCount",
        instance["packageCount"],
        len(package_identities),
        "package identity count",
    )

    total_bytes = sum(artifact["sizeBytes"] for artifact in artifacts)
    published_artifacts = [artifact for artifact in artifacts if artifact["published"]]
    published_bytes = sum(artifact["sizeBytes"] for artifact in published_artifacts)
    add_equal_error(
        errors,
        "$.totalArtifactBytes",
        instance["totalArtifactBytes"],
        total_bytes,
        "artifact byte sum",
    )
    add_equal_error(
        errors,
        "$.publishedArtifactCount",
        instance["publishedArtifactCount"],
        len(published_artifacts),
        "published artifact length",
    )
    add_equal_error(
        errors,
        "$.publishedArtifactBytes",
        instance["publishedArtifactBytes"],
        published_bytes,
        "published artifact byte sum",
    )

    expected_success = (
        instance["diagnosticCounts"]["error"] == 0
        and instance["publishedArtifactCount"] == instance["artifactCount"]
    )
    add_equal_error(
        errors,
        "$.success",
        instance["success"],
        expected_success,
        "complete no-error publish status",
    )

    for index, artifact in enumerate(artifacts):
        validate_artifact(
            errors,
            f"$.artifacts[{index}]",
            artifact,
            instance["targetPath"],
        )

    for index, diagnostic in enumerate(diagnostics):
        diagnostic_path = f"$.diagnostics[{index}]"
        if not diagnostic["code"].startswith("package.release.publish."):
            errors.append(
                f"{diagnostic_path}.code: expected package.release.publish. prefix"
            )
        validate_diagnostic_message(errors, diagnostic_path, diagnostic)
        validate_source_location_span(
            errors,
            f"{diagnostic_path}.location",
            diagnostic["location"],
        )

    return errors
