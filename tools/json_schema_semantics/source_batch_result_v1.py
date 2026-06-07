"""Semantic checks for source-batch-result-v1.schema.json."""

from . import diagnostics_v1
from .common import add_equal_error


def _diagnostic_report_error(error):
    if error.startswith("$"):
        return "$.diagnosticReport" + error[1:]
    return "$.diagnosticReport: " + error


def validate_semantics(instance):
    errors = []
    entries = instance["entries"]
    diagnostics = instance["diagnosticReport"]["diagnostics"]

    add_equal_error(
        errors,
        "$.entryCount",
        instance["entryCount"],
        len(entries),
        "entries length",
    )

    has_error_diagnostic = any(
        diagnostic["severity"] == "error" for diagnostic in diagnostics
    )
    expected_success = (
        not has_error_diagnostic and all(entry["success"] for entry in entries)
    )
    add_equal_error(
        errors,
        "$.success",
        instance["success"],
        expected_success,
        "complete no-error batch status",
    )

    for error in diagnostics_v1.validate_semantics(instance["diagnosticReport"]):
        errors.append(_diagnostic_report_error(error))

    return errors
