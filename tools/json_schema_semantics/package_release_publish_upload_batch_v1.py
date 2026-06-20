"""Semantic checks for package-release-publish-upload-batch-v1.schema.json."""

from collections import Counter

from .common import (
    add_equal_error,
    add_length_count_error,
    validate_diagnostic_message,
    validate_source_location_span,
)
from .package_release_publish_upload_manifest_v1 import (
    request_object_prefix,
    validate_request,
)


SEVERITIES = ("note", "warning", "error")


def validate_semantics(instance):
    errors = []

    if instance["uploadMode"] in ("mock", "gcs") and instance["manifestPath"] == "":
        errors.append(
            "$.manifestPath: expected non-empty path for manifest-backed upload"
        )
    if instance["reportWritten"] and instance["reportPath"] == "":
        errors.append("$.reportPath: expected non-empty path when reportWritten")

    requests = instance["uploadedRequests"]
    add_length_count_error(
        errors,
        "$.uploadedArtifactCount",
        instance["uploadedArtifactCount"],
        requests,
        "uploaded request length",
    )
    uploaded_bytes = sum(request["sizeBytes"] for request in requests)
    add_equal_error(
        errors,
        "$.uploadedArtifactBytes",
        instance["uploadedArtifactBytes"],
        uploaded_bytes,
        "uploaded request byte sum",
    )
    if instance["uploadedArtifactCount"] > instance["requestCount"]:
        errors.append("$.uploadedArtifactCount: expected <= requestCount")
    if instance["uploadedArtifactBytes"] > instance["requestBytes"]:
        errors.append("$.uploadedArtifactBytes: expected <= requestBytes")

    destination_paths = [request["destinationPath"] for request in requests]
    if destination_paths != sorted(destination_paths):
        errors.append("$.uploadedRequests: destination paths must be sorted")
    if len(destination_paths) != len(set(destination_paths)):
        errors.append("$.uploadedRequests: duplicate destination paths")

    object_prefixes = [
        prefix for request in requests if (prefix := request_object_prefix(request))
    ]
    if object_prefixes and len(object_prefixes) != len(requests):
        errors.append(
            "$.uploadedRequests: expected object names with release-scoped prefixes"
        )
    elif len(set(object_prefixes)) > 1:
        errors.append("$.uploadedRequests: expected one release-scoped object prefix")

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
    if not instance["success"] and counts["error"] == 0:
        errors.append("$.diagnostics: expected error diagnostic when success is false")

    expected_success = (
        instance["diagnosticCounts"]["error"] == 0
        and instance["uploadedArtifactCount"] == instance["requestCount"]
        and instance["uploadedArtifactBytes"] == instance["requestBytes"]
    )
    add_equal_error(
        errors,
        "$.success",
        instance["success"],
        expected_success,
        "complete no-error upload batch status",
    )

    for index, request in enumerate(requests):
        validate_request(errors, f"$.uploadedRequests[{index}]", request)

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
