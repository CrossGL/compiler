"""Semantic checks for package-maintenance-set-verification-batch-report-v1."""

from collections import Counter

from .common import add_equal_error, add_length_count_error
from .package_maintenance_set_verification_v1 import (
    validate_diagnostic_reasons,
    validate_semantics as validate_verification,
)


SEVERITIES = ("note", "warning", "error")


def prefixed(errors, prefix):
    return [
        f"{prefix}{error[1:]}" if error.startswith("$") else error for error in errors
    ]


def is_mismatched(verification):
    return bool(verification["missingFromSet"] or verification["extraInSet"])


def validate_unique_verification_pairs(errors, path, verifications):
    seen = set()
    for index, verification in enumerate(verifications):
        key = (verification["rootPath"], verification["setPath"])
        if key in seen:
            errors.append(f"{path}[{index}]: duplicate rootPath/setPath pair")
        seen.add(key)


def validate_semantics(instance):
    errors = []
    verifications = instance["verifications"]
    diagnostics = instance["diagnostics"]

    validate_diagnostic_reasons(errors, "$.diagnostics", diagnostics)

    add_length_count_error(
        errors,
        "$.verificationCount",
        instance["verificationCount"],
        verifications,
        "verification length",
    )
    validate_unique_verification_pairs(errors, "$.verifications", verifications)

    expected_matched = sum(
        1 for verification in verifications if verification["matches"]
    )
    add_equal_error(
        errors,
        "$.matchedCount",
        instance["matchedCount"],
        expected_matched,
        "matched verification count",
    )

    expected_mismatched = sum(
        1 for verification in verifications if is_mismatched(verification)
    )
    add_equal_error(
        errors,
        "$.mismatchedCount",
        instance["mismatchedCount"],
        expected_mismatched,
        "mismatched verification count",
    )

    expected_failed = sum(
        1
        for verification in verifications
        if not verification["success"] and not is_mismatched(verification)
    )
    add_equal_error(
        errors,
        "$.failedCount",
        instance["failedCount"],
        expected_failed,
        "failed verification count",
    )
    expected_partition_count = (
        instance["matchedCount"] + instance["mismatchedCount"] + instance["failedCount"]
    )
    add_equal_error(
        errors,
        "$.matchedCount/$.mismatchedCount/$.failedCount",
        expected_partition_count,
        instance["verificationCount"],
        "partitioned verification count",
    )

    for index, verification in enumerate(verifications):
        errors.extend(
            prefixed(
                validate_verification(verification),
                f"$.verifications[{index}]",
            )
        )

    nested_diagnostics = []
    for verification in verifications:
        nested_diagnostics.extend(verification["diagnostics"])
    if (
        nested_diagnostics
        and diagnostics[-len(nested_diagnostics) :] != nested_diagnostics
    ):
        errors.append(
            "$.diagnostics: expected nested verification diagnostics to be "
            "preserved at the end of the aggregate diagnostic list"
        )

    counts = Counter(diagnostic["severity"] for diagnostic in diagnostics)
    for severity in SEVERITIES:
        add_equal_error(
            errors,
            f"$.diagnosticCounts.{severity}",
            instance["diagnosticCounts"][severity],
            counts[severity],
            f"{severity} diagnostic count",
        )

    has_error_diagnostic = counts["error"] != 0
    expected_success = (
        not has_error_diagnostic
        and bool(verifications)
        and all(verification["success"] for verification in verifications)
    )
    add_equal_error(
        errors,
        "$.success",
        instance["success"],
        expected_success,
        "successful verification batch",
    )

    expected_matches = expected_success and all(
        verification["matches"] for verification in verifications
    )
    add_equal_error(
        errors,
        "$.matches",
        instance["matches"],
        expected_matches,
        "matching verification batch",
    )

    return errors
