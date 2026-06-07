"""Semantic checks for package-maintenance-report-v1.schema.json."""

from collections import Counter

from .common import add_equal_error, add_length_count_error
from .package_stale_sidecars_v1 import validate_semantics as validate_cleanup


SEVERITIES = ("note", "warning", "error")


def validate_semantics(instance):
    errors = []
    packages = instance["packages"]
    diagnostics = instance["diagnostics"]

    add_length_count_error(
        errors,
        "$.packageCount",
        instance["packageCount"],
        packages,
        "maintenance package result length",
    )
    add_equal_error(
        errors,
        "$.retainedCount",
        instance["retainedCount"],
        sum(package["retainedCount"] for package in packages),
        "aggregate retained count",
    )
    add_equal_error(
        errors,
        "$.candidateCount",
        instance["candidateCount"],
        sum(package["candidateCount"] for package in packages),
        "aggregate candidate count",
    )
    add_equal_error(
        errors,
        "$.discardedCount",
        instance["discardedCount"],
        sum(package["discardedCount"] for package in packages),
        "aggregate discarded count",
    )
    add_equal_error(
        errors,
        "$.failedCount",
        instance["failedCount"],
        sum(package["failedCount"] for package in packages),
        "aggregate failed count",
    )

    package_paths = [package["packagePath"] for package in packages]
    if package_paths != sorted(package_paths):
        errors.append("$.packages: expected sorted package paths")
    if len(package_paths) != len(set(package_paths)):
        errors.append("$.packages: duplicate package paths")

    for index, package in enumerate(packages):
        package_path = f"$.packages[{index}]"
        if package["dryRun"] != instance["dryRun"]:
            errors.append(f"{package_path}.dryRun: expected aggregate dryRun")
        if package["keepLast"] != instance["keepLast"]:
            errors.append(f"{package_path}.keepLast: expected aggregate keepLast")
        if package["olderThanSeconds"] != instance["olderThanSeconds"]:
            errors.append(
                f"{package_path}.olderThanSeconds: expected aggregate olderThanSeconds"
            )
        if package["publication"]["requestedPath"] != package["packagePath"]:
            errors.append(
                f"{package_path}.publication.requestedPath: expected packagePath"
            )
        for cleanup_error in validate_cleanup(package):
            errors.append(f"{package_path}{cleanup_error[1:]}")

    expected_success = all(package["success"] for package in packages) and not any(
        diagnostic["severity"] == "error" for diagnostic in diagnostics
    )
    add_equal_error(
        errors,
        "$.success",
        instance["success"],
        expected_success,
        "aggregate success",
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

    nested_diagnostics = []
    for package in packages:
        nested_diagnostics.extend(package["diagnostics"])
    if (
        nested_diagnostics
        and diagnostics[-len(nested_diagnostics) :] != nested_diagnostics
    ):
        errors.append("$.diagnostics: expected package diagnostics to be appended")

    return errors
