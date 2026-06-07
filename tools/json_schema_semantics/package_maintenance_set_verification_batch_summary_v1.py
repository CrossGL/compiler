"""Semantic checks for package-maintenance-set-verification-batch-summary-v1."""

from .common import add_equal_error, add_length_count_error
from .package_maintenance_set_verification_v1 import (
    SEVERITIES,
    validate_normalized_non_empty_path,
    validate_sorted_unique_paths,
)


def is_mismatched(verification):
    return bool(verification["missingFromSet"] or verification["extraInSet"])


def diagnostic_total(diagnostic_counts):
    return sum(diagnostic_counts[severity] for severity in SEVERITIES)


def diagnostic_code_count_map(entries):
    return {entry["code"]: entry["count"] for entry in entries}


def validate_diagnostic_code_counts(errors, path, entries, diagnostic_counts):
    codes = [entry["code"] for entry in entries]
    if codes != sorted(codes):
        errors.append(f"{path}: diagnostic codes must be sorted")
    if len(codes) != len(set(codes)):
        errors.append(f"{path}: duplicate diagnostic codes")
    for index, code in enumerate(codes):
        if code == "":
            errors.append(f"{path}[{index}].code: expected non-empty code")
    add_equal_error(
        errors,
        path,
        sum(entry["count"] for entry in entries),
        diagnostic_total(diagnostic_counts),
        "diagnostic code count total",
    )


def validate_unique_verification_pairs(errors, path, verifications):
    seen = set()
    for index, verification in enumerate(verifications):
        key = (verification["rootPath"], verification["setPath"])
        if key in seen:
            errors.append(f"{path}[{index}]: duplicate rootPath/setPath pair")
        seen.add(key)


def validate_verification_summary(errors, path, verification):
    missing_from_set = verification["missingFromSet"]
    extra_in_set = verification["extraInSet"]
    diagnostic_counts = verification["diagnosticCounts"]

    validate_normalized_non_empty_path(
        errors, f"{path}.rootPath", verification["rootPath"]
    )
    validate_normalized_non_empty_path(
        errors, f"{path}.setPath", verification["setPath"]
    )

    add_length_count_error(
        errors,
        f"{path}.missingFromSetCount",
        verification["missingFromSetCount"],
        missing_from_set,
        "missing-from-set path length",
    )
    add_length_count_error(
        errors,
        f"{path}.extraInSetCount",
        verification["extraInSetCount"],
        extra_in_set,
        "extra-in-set path length",
    )
    add_equal_error(
        errors,
        f"{path}.scannedPackageCount",
        verification["scannedPackageCount"],
        verification["setPackageCount"]
        + verification["missingFromSetCount"]
        - verification["extraInSetCount"],
        "scanned package count from set/missing/extra counts",
    )

    validate_sorted_unique_paths(errors, f"{path}.missingFromSet", missing_from_set)
    validate_sorted_unique_paths(errors, f"{path}.extraInSet", extra_in_set)
    validate_diagnostic_code_counts(
        errors,
        f"{path}.diagnosticCodeCounts",
        verification["diagnosticCodeCounts"],
        diagnostic_counts,
    )

    has_error_diagnostic = diagnostic_counts["error"] != 0
    expected_matches = (
        not has_error_diagnostic and not missing_from_set and not extra_in_set
    )
    add_equal_error(
        errors,
        f"{path}.matches",
        verification["matches"],
        expected_matches,
        "empty package path differences",
    )
    expected_success = expected_matches and not has_error_diagnostic
    add_equal_error(
        errors,
        f"{path}.success",
        verification["success"],
        expected_success,
        "successful verification",
    )


def validate_semantics(instance):
    errors = []
    verifications = instance["verifications"]

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

    add_equal_error(
        errors,
        "$.scannedPackageCount",
        instance["scannedPackageCount"],
        sum(verification["scannedPackageCount"] for verification in verifications),
        "sum of scanned package counts",
    )
    add_equal_error(
        errors,
        "$.setPackageCount",
        instance["setPackageCount"],
        sum(verification["setPackageCount"] for verification in verifications),
        "sum of set package counts",
    )
    add_equal_error(
        errors,
        "$.missingFromSetCount",
        instance["missingFromSetCount"],
        sum(verification["missingFromSetCount"] for verification in verifications),
        "sum of missing-from-set counts",
    )
    add_equal_error(
        errors,
        "$.extraInSetCount",
        instance["extraInSetCount"],
        sum(verification["extraInSetCount"] for verification in verifications),
        "sum of extra-in-set counts",
    )

    for index, verification in enumerate(verifications):
        validate_verification_summary(
            errors,
            f"$.verifications[{index}]",
            verification,
        )

    aggregate_counts = instance["diagnosticCounts"]
    validate_diagnostic_code_counts(
        errors,
        "$.diagnosticCodeCounts",
        instance["diagnosticCodeCounts"],
        aggregate_counts,
    )

    nested_counts = {severity: 0 for severity in SEVERITIES}
    nested_codes = {}
    for verification in verifications:
        for severity in SEVERITIES:
            nested_counts[severity] += verification["diagnosticCounts"][severity]
        for code, count in diagnostic_code_count_map(
            verification["diagnosticCodeCounts"]
        ).items():
            nested_codes[code] = nested_codes.get(code, 0) + count

    for severity in SEVERITIES:
        if aggregate_counts[severity] < nested_counts[severity]:
            errors.append(
                f"$.diagnosticCounts.{severity}: expected aggregate count to "
                "include nested verification diagnostics"
            )

    aggregate_codes = diagnostic_code_count_map(instance["diagnosticCodeCounts"])
    for code, count in nested_codes.items():
        if aggregate_codes.get(code, 0) < count:
            errors.append(
                f"$.diagnosticCodeCounts: expected aggregate count for {code!r} "
                "to include nested verification diagnostics"
            )

    has_error_diagnostic = aggregate_counts["error"] != 0
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
    add_equal_error(
        errors,
        "$.releaseEligible",
        instance["releaseEligible"],
        expected_success and expected_matches,
        "release eligibility",
    )

    return errors
