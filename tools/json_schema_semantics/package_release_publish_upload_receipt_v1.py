"""Semantic checks for package-release-publish-upload-receipt-v1.schema.json."""

import hashlib
from collections import Counter

from .common import (
    add_equal_error,
    add_length_count_error,
    validate_diagnostic_message,
    validate_source_location_span,
)
from .package_release_publish_upload_manifest_v1 import (
    SHA256_RE,
    request_object_prefix,
    validate_request,
)


SEVERITIES = ("note", "warning", "error")
COMPLETED_STATUSES = ("uploaded", "already-present")


def expected_idempotency_key(request):
    fingerprint_input = "\n".join(
        (
            request["targetKind"],
            request["uploadUri"],
            str(request["sizeBytes"]),
            request["sha256"],
        )
    )
    return hashlib.sha256(fingerprint_input.encode("utf-8")).hexdigest()


def validate_attempt(errors, path, attempt, upload_mode):
    provider = attempt["provider"]
    if upload_mode in ("mock", "gcs") and provider != upload_mode:
        errors.append(
            f"{path}.provider: expected {upload_mode} provider for {upload_mode} upload"
        )
    if upload_mode in ("mock", "gcs"):
        if not SHA256_RE.match(attempt["idempotencyKey"]):
            errors.append(
                f"{path}.idempotencyKey: expected lowercase SHA-256 fingerprint"
            )
        elif attempt["idempotencyKey"] != expected_idempotency_key(attempt["request"]):
            errors.append(
                f"{path}.idempotencyKey: expected deterministic upload "
                "request fingerprint"
            )

    if provider == "mock":
        if attempt["overwrite"]:
            errors.append(f"{path}.overwrite: mock attempts must not request overwrite")
        for field in (
            "preconditionKind",
            "preconditionValue",
            "generation",
            "metageneration",
            "crc32c",
            "md5Hash",
        ):
            if attempt[field] != "":
                errors.append(f"{path}.{field}: expected empty value for mock upload")
    elif provider == "gcs":
        if attempt["overwrite"]:
            if attempt["preconditionKind"] != "" or attempt["preconditionValue"] != "":
                errors.append(
                    f"{path}.preconditionKind: expected no create-only "
                    "precondition for overwrite"
                )
        elif (
            attempt["preconditionKind"] != "ifGenerationMatch"
            or attempt["preconditionValue"] != "0"
        ):
            errors.append(
                f"{path}.preconditionKind: expected ifGenerationMatch=0 "
                "create-only precondition"
            )
        if attempt["status"] == "failed":
            for field in ("generation", "metageneration", "crc32c", "md5Hash"):
                if attempt[field] != "":
                    errors.append(
                        f"{path}.{field}: expected empty value for failed upload"
                    )
        elif attempt["status"] in COMPLETED_STATUSES:
            for field in ("generation", "metageneration", "crc32c", "md5Hash"):
                if attempt[field] == "":
                    errors.append(
                        f"{path}.{field}: expected non-empty value for completed "
                        "GCS upload"
                    )


def validate_semantics(instance):
    errors = []

    if instance["uploadMode"] in ("mock", "gcs") and instance["manifestPath"] == "":
        errors.append(
            "$.manifestPath: expected non-empty path for manifest-backed upload"
        )
    if instance["receiptWritten"] and instance["receiptPath"] == "":
        errors.append("$.receiptPath: expected non-empty path when receiptWritten")

    attempts = instance["attempts"]
    add_length_count_error(
        errors,
        "$.attemptCount",
        instance["attemptCount"],
        attempts,
        "attempt length",
    )
    attempt_bytes = sum(attempt["request"]["sizeBytes"] for attempt in attempts)
    add_equal_error(
        errors,
        "$.attemptBytes",
        instance["attemptBytes"],
        attempt_bytes,
        "attempt byte sum",
    )
    if instance["attemptCount"] > instance["requestCount"]:
        errors.append("$.attemptCount: expected <= requestCount")
    if instance["attemptBytes"] > instance["requestBytes"]:
        errors.append("$.attemptBytes: expected <= requestBytes")

    completed_attempts = [
        attempt for attempt in attempts if attempt["status"] in COMPLETED_STATUSES
    ]
    add_equal_error(
        errors,
        "$.completedAttemptCount",
        instance["completedAttemptCount"],
        len(completed_attempts),
        "completed attempt length",
    )
    completed_bytes = sum(
        attempt["request"]["sizeBytes"] for attempt in completed_attempts
    )
    add_equal_error(
        errors,
        "$.completedAttemptBytes",
        instance["completedAttemptBytes"],
        completed_bytes,
        "completed attempt byte sum",
    )
    if instance["completedAttemptCount"] > instance["requestCount"]:
        errors.append("$.completedAttemptCount: expected <= requestCount")
    if instance["completedAttemptBytes"] > instance["requestBytes"]:
        errors.append("$.completedAttemptBytes: expected <= requestBytes")

    destination_paths = [attempt["request"]["destinationPath"] for attempt in attempts]
    if destination_paths != sorted(destination_paths):
        errors.append("$.attempts: destination paths must be sorted")
    if len(destination_paths) != len(set(destination_paths)):
        errors.append("$.attempts: duplicate destination paths")

    object_prefixes = [
        prefix
        for attempt in attempts
        if (prefix := request_object_prefix(attempt["request"]))
    ]
    if object_prefixes and len(object_prefixes) != len(attempts):
        errors.append("$.attempts: expected object names with release-scoped prefixes")
    elif len(set(object_prefixes)) > 1:
        errors.append("$.attempts: expected one release-scoped object prefix")

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
        and instance["completedAttemptCount"] == instance["requestCount"]
        and instance["completedAttemptBytes"] == instance["requestBytes"]
    )
    add_equal_error(
        errors,
        "$.success",
        instance["success"],
        expected_success,
        "complete no-error upload receipt status",
    )

    for index, attempt in enumerate(attempts):
        attempt_path = f"$.attempts[{index}]"
        validate_request(errors, f"{attempt_path}.request", attempt["request"])
        validate_attempt(errors, attempt_path, attempt, instance["uploadMode"])
        if attempt["status"] == "failed" and attempt["errorMessage"] == "":
            errors.append(
                f"{attempt_path}.errorMessage: expected failed attempt message"
            )
        if attempt["status"] in COMPLETED_STATUSES and attempt["errorMessage"] != "":
            errors.append(
                f"{attempt_path}.errorMessage: expected empty completed attempt message"
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
