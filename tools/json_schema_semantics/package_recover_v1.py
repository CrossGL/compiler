"""Semantic checks for package-recover-v1.schema.json."""

from collections import Counter

from .common import (
    add_equal_error,
    validate_normalized_package_path,
    validate_source_location_span,
)


SEVERITIES = ("note", "warning", "error")
RECOVERY_DIAGNOSTIC_PREFIXES = ("package.recover.", "package.verify.")
VERIFY_DIAGNOSTIC_PREFIX = "package.verify."
RECOVERY_VERIFY_FAILED_CODE = "package.recover.verify-failed"
SIDECAR_MARKERS = ((".staging-", "staging"), (".previous-", "previous"))


def package_parent_path(package_path):
    slash = package_path.rfind("/")
    if slash == -1:
        return ""
    return package_path[:slash]


def join_package_path(parent, filename):
    if not parent:
        return filename
    return f"{parent}/{filename}"


def parse_unsigned(text):
    if not text or not text.isdigit():
        return None
    return int(text)


def parse_sidecar_path(sidecar_path):
    filename = sidecar_path.rsplit("/", 1)[-1]
    if len(filename) < 2 or not filename.startswith("."):
        return None

    marker_position = -1
    marker_text = None
    marker_kind = None
    for candidate_text, candidate_kind in SIDECAR_MARKERS:
        candidate_position = filename.rfind(candidate_text)
        if candidate_position > marker_position:
            marker_position = candidate_position
            marker_text = candidate_text
            marker_kind = candidate_kind

    if marker_position <= 1:
        return None

    payload_offset = marker_position + len(marker_text)
    if payload_offset >= len(filename):
        return None

    attempt_separator = filename.rfind("-")
    if (
        attempt_separator == -1
        or attempt_separator < payload_offset
        or attempt_separator + 1 >= len(filename)
    ):
        return None

    token = filename[payload_offset:attempt_separator]
    attempt = parse_unsigned(filename[attempt_separator + 1 :])
    if not token or attempt is None:
        return None

    return {
        "requestedPath": join_package_path(
            package_parent_path(sidecar_path),
            filename[1:marker_position],
        ),
        "kind": marker_kind,
        "token": token,
        "attempt": attempt,
    }


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


def validate_paths(errors, instance):
    validate_normalized_package_path(errors, "$.sidecarPath", instance["sidecarPath"])
    if instance["requestedPath"] is not None:
        validate_normalized_package_path(
            errors,
            "$.requestedPath",
            instance["requestedPath"],
        )
    if instance["backupPath"] is not None:
        validate_normalized_package_path(errors, "$.backupPath", instance["backupPath"])


def validate_sidecar_path_consistency(errors, instance):
    sidecar = parse_sidecar_path(instance["sidecarPath"])
    if sidecar is None:
        if instance["requestedPath"] is not None:
            errors.append("$.requestedPath: invalid sidecar path requires null")
        return

    add_equal_error(
        errors,
        "$.requestedPath",
        instance["requestedPath"],
        sidecar["requestedPath"],
        "sidecar requested path",
    )

    if instance["backupPath"] is None:
        return

    backup = parse_sidecar_path(instance["backupPath"])
    if backup is None:
        errors.append("$.backupPath: expected valid package sidecar path")
        return
    add_equal_error(
        errors,
        "$.backupPath",
        backup["requestedPath"],
        sidecar["requestedPath"],
        "backup sidecar requested path",
    )
    add_equal_error(
        errors,
        "$.backupPath",
        backup["kind"],
        "previous",
        "backup sidecar kind",
    )


def validate_result_consistency(errors, instance, counts):
    add_equal_error(
        errors,
        "$.success",
        instance["success"],
        counts["error"] == 0,
        "no-error diagnostic status",
    )
    add_equal_error(
        errors,
        "$.replacedExisting",
        instance["replacedExisting"],
        instance["backupPath"] is not None,
        "backup path presence",
    )

    if instance["success"] and instance["message"] is None:
        errors.append("$.message: successful recovery requires a message")
    if not instance["success"] and not instance["diagnostics"]:
        errors.append("$.diagnostics: failed recovery requires diagnostics")
    if instance["action"] == "discard" and instance["backupPath"] is not None:
        errors.append("$.backupPath: discard recovery must not create a backup")


def validate_diagnostics(errors, diagnostics):
    for index, diagnostic in enumerate(diagnostics):
        diagnostic_path = f"$.diagnostics[{index}]"
        if not diagnostic["code"].startswith(RECOVERY_DIAGNOSTIC_PREFIXES):
            errors.append(
                f"{diagnostic_path}.code: expected package.recover. or "
                "package.verify. prefix"
            )
        validate_source_location_span(
            errors,
            f"{diagnostic_path}.location",
            diagnostic["location"],
        )


def validate_verify_diagnostic_context(errors, instance):
    diagnostics = instance["diagnostics"]
    has_verify_diagnostic = any(
        diagnostic["code"].startswith(VERIFY_DIAGNOSTIC_PREFIX)
        for diagnostic in diagnostics
    )
    if not has_verify_diagnostic:
        return

    if instance["action"] != "promote":
        errors.append("$.diagnostics: package.verify diagnostics require promotion")

    if not any(
        diagnostic["code"] == RECOVERY_VERIFY_FAILED_CODE
        and diagnostic["severity"] == "error"
        for diagnostic in diagnostics
    ):
        errors.append(
            "$.diagnostics: package.verify diagnostics require "
            "package.recover.verify-failed error"
        )


def validate_semantics(instance):
    errors = []
    diagnostics = instance["diagnostics"]
    counts = validate_diagnostic_counts(
        errors,
        instance["diagnosticCounts"],
        diagnostics,
    )
    validate_paths(errors, instance)
    validate_sidecar_path_consistency(errors, instance)
    validate_result_consistency(errors, instance, counts)
    validate_diagnostics(errors, diagnostics)
    validate_verify_diagnostic_context(errors, instance)
    return errors
