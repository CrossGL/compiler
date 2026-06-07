"""Semantic checks for package-maintenance-set-verification-v1.schema.json."""

from collections import Counter
import posixpath

from .common import (
    add_equal_error,
    add_length_count_error,
    validate_source_location_span,
)


SEVERITIES = ("note", "warning", "error")
PATH_ARRAY_FIELDS = (
    "scannedPackages",
    "setPackages",
    "missingFromSet",
    "extraInSet",
)


def validate_normalized_non_empty_path(errors, path, value):
    if value == "":
        errors.append(f"{path}: expected non-empty path")
        return
    if "\\" in value:
        errors.append(f"{path}: expected normalized '/' path separators")
    if posixpath.normpath(value) != value:
        errors.append(f"{path}: expected normalized path")


def validate_sorted_unique_paths(errors, path, values):
    if values != sorted(values):
        errors.append(f"{path}: expected sorted package paths")
    if len(values) != len(set(values)):
        errors.append(f"{path}: duplicate package paths")
    for index, value in enumerate(values):
        if not isinstance(value, str):
            continue
        if value == "":
            errors.append(f"{path}[{index}]: expected non-empty package path")
        if "\\" in value:
            errors.append(f"{path}[{index}]: expected normalized '/' path separators")
        if posixpath.normpath(value) != value:
            errors.append(f"{path}[{index}]: expected normalized package path")


def validate_diagnostic_reasons(errors, path, diagnostics):
    for index, diagnostic in enumerate(diagnostics):
        if diagnostic["code"] == "":
            errors.append(f"{path}[{index}].code: expected non-empty diagnostic code")
        if diagnostic["message"] == "":
            errors.append(
                f"{path}[{index}].message: expected non-empty diagnostic message"
            )


def validate_semantics(instance):
    errors = []
    diagnostics = instance["diagnostics"]
    scanned_packages = instance["scannedPackages"]
    set_packages = instance["setPackages"]
    missing_from_set = instance["missingFromSet"]
    extra_in_set = instance["extraInSet"]

    validate_normalized_non_empty_path(errors, "$.rootPath", instance["rootPath"])
    validate_normalized_non_empty_path(errors, "$.setPath", instance["setPath"])

    add_length_count_error(
        errors,
        "$.scannedPackageCount",
        instance["scannedPackageCount"],
        scanned_packages,
        "scanned package path length",
    )
    add_length_count_error(
        errors,
        "$.setPackageCount",
        instance["setPackageCount"],
        set_packages,
        "set package path length",
    )
    add_length_count_error(
        errors,
        "$.missingFromSetCount",
        instance["missingFromSetCount"],
        missing_from_set,
        "missing-from-set path length",
    )
    add_length_count_error(
        errors,
        "$.extraInSetCount",
        instance["extraInSetCount"],
        extra_in_set,
        "extra-in-set path length",
    )

    for field in PATH_ARRAY_FIELDS:
        validate_sorted_unique_paths(errors, f"$.{field}", instance[field])

    expected_missing = sorted(set(scanned_packages) - set(set_packages))
    expected_extra = sorted(set(set_packages) - set(scanned_packages))
    add_equal_error(
        errors,
        "$.missingFromSet",
        missing_from_set,
        expected_missing,
        "scan paths absent from set",
    )
    add_equal_error(
        errors,
        "$.extraInSet",
        extra_in_set,
        expected_extra,
        "set paths absent from scan",
    )

    has_error_diagnostic = any(
        diagnostic["severity"] == "error" for diagnostic in diagnostics
    )
    expected_matches = (
        not has_error_diagnostic and not missing_from_set and not extra_in_set
    )
    add_equal_error(
        errors,
        "$.matches",
        instance["matches"],
        expected_matches,
        "empty package path differences",
    )
    expected_success = expected_matches and not has_error_diagnostic
    add_equal_error(
        errors,
        "$.success",
        instance["success"],
        expected_success,
        "successful verification",
    )

    validate_diagnostic_reasons(errors, "$.diagnostics", diagnostics)

    counts = Counter(diagnostic["severity"] for diagnostic in diagnostics)
    for severity in SEVERITIES:
        add_equal_error(
            errors,
            f"$.diagnosticCounts.{severity}",
            instance["diagnosticCounts"][severity],
            counts[severity],
            f"{severity} diagnostic count",
        )

    for index, diagnostic in enumerate(diagnostics):
        validate_source_location_span(
            errors,
            f"$.diagnostics[{index}].location",
            diagnostic["location"],
        )

    return errors
