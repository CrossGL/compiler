"""Semantic checks for package-release-publish-receipt-v2.schema.json."""

from collections import Counter
from pathlib import PurePosixPath

from .common import (
    add_equal_error,
    add_length_count_error,
    validate_diagnostic_message,
    validate_source_location_span,
)
from .package_release_publish_target_v1 import (
    is_gcs_bucket_name,
    is_normalized_relative_path,
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


def expected_published_path(instance, artifact):
    if instance["targetKind"] == "gcs":
        return f"{instance['targetUri'].rstrip('/')}/{artifact['destinationPath']}"
    return str(PurePosixPath(instance["targetPath"]) / artifact["destinationPath"])


def validate_gcs_target_uri(errors, path, value):
    if not value.startswith("gs://"):
        errors.append(f"{path}: expected gs:// URI for gcs target")
        return
    remainder = value[len("gs://") :]
    if "/" not in remainder:
        errors.append(f"{path}: expected gs://bucket/prefix URI for gcs target")
        return
    bucket, prefix = remainder.split("/", 1)
    if not is_gcs_bucket_name(bucket):
        errors.append(f"{path}: expected valid gcs bucket name")
    if not is_normalized_relative_path(prefix):
        errors.append(f"{path}: expected normalized release-scoped object prefix")


def validate_source_path(errors, path, artifact):
    if artifact["sourcePath"].endswith("/" + artifact["packageArtifactPath"]):
        return
    if (
        artifact["sourcePath"]
        == artifact["packagePath"] + "/" + artifact["packageArtifactPath"]
    ):
        return
    errors.append(f"{path}.sourcePath: expected packagePath/packageArtifactPath")


def validate_artifact(errors, path, artifact, instance):
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
    expected_path = expected_published_path(instance, artifact)
    if artifact["publishedPath"] != expected_path:
        errors.append(f"{path}.publishedPath: expected target destination path")
    if artifact["published"] and artifact["publishedPath"] == artifact["stagedPath"]:
        errors.append(f"{path}.publishedPath: expected distinct stagedPath")
    if artifact["planned"] and not artifact["staged"]:
        errors.append(f"{path}.planned: expected staged artifact before planning")
    if artifact["published"] and not artifact["staged"]:
        errors.append(f"{path}.published: expected staged artifact before publish")
    if artifact["published"] and not artifact["planned"]:
        errors.append(f"{path}.published: expected planned artifact before publish")


def validate_semantics(instance):
    errors = []

    if instance["stageReportPath"] == "":
        errors.append("$.stageReportPath: expected non-empty path")
    if instance["targetKind"] == "":
        errors.append("$.targetKind: expected non-empty target kind")
    if instance["targetKind"] == "local-filesystem":
        if instance["targetPath"] == "":
            errors.append("$.targetPath: expected non-empty path for local target")
        if instance["targetUri"] == "":
            errors.append("$.targetUri: expected non-empty URI for local target")
        elif instance["targetPath"] and instance["targetUri"] != instance["targetPath"]:
            errors.append("$.targetUri: expected normalized local targetPath")
    elif instance["targetKind"] == "gcs":
        if instance["targetDescriptorPath"] and instance["targetPath"] != "":
            errors.append("$.targetPath: expected empty path for gcs target")
        if instance["success"] and instance["targetDescriptorPath"] == "":
            errors.append("$.targetDescriptorPath: expected descriptor path for gcs")
        if instance["success"] and instance["targetUri"] == "":
            errors.append("$.targetUri: expected gs:// URI for successful gcs target")
        if instance["success"] and not instance["dryRun"]:
            errors.append("$.dryRun: expected true for gcs validation target")
        if instance["success"] and instance["targetEnabled"]:
            errors.append("$.targetEnabled: expected false for gcs validation target")
        if instance["targetUri"]:
            validate_gcs_target_uri(errors, "$.targetUri", instance["targetUri"])
    elif instance["success"]:
        errors.append("$.targetKind: expected supported target kind on success")
    if instance["receiptWritten"] and instance["receiptPath"] == "":
        errors.append("$.receiptPath: expected non-empty path when receiptWritten")
    if not instance["receiptWritten"] and instance["receiptPath"] != "":
        errors.append("$.receiptPath: expected empty path when not receiptWritten")

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
    planned_artifacts = [artifact for artifact in artifacts if artifact["planned"]]
    published_artifacts = [artifact for artifact in artifacts if artifact["published"]]
    planned_bytes = sum(artifact["sizeBytes"] for artifact in planned_artifacts)
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
        "$.plannedArtifactCount",
        instance["plannedArtifactCount"],
        len(planned_artifacts),
        "planned artifact length",
    )
    add_equal_error(
        errors,
        "$.plannedArtifactBytes",
        instance["plannedArtifactBytes"],
        planned_bytes,
        "planned artifact byte sum",
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

    if instance["dryRun"]:
        expected_success = (
            instance["diagnosticCounts"]["error"] == 0
            and instance["plannedArtifactCount"] == instance["artifactCount"]
            and instance["publishedArtifactCount"] == 0
        )
    else:
        expected_success = (
            instance["diagnosticCounts"]["error"] == 0
            and instance["plannedArtifactCount"] == instance["artifactCount"]
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
            instance,
        )
        if instance["dryRun"] and artifact["published"]:
            errors.append(
                f"$.artifacts[{index}].published: dry-run receipt must not publish"
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
