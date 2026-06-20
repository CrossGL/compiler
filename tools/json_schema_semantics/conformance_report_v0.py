"""Semantic checks for conformance-report-v0.schema.json."""

from .common import add_equal_error

TARGET_FEATURE_EVIDENCE_KINDS = (
    "planned-unsupported",
    "target-metadata",
    "target-package-explanation",
)
AUXILIARY_EVIDENCE_KINDS = (
    "backend-dump",
    "debug-dump",
    "package-inspection",
    "target-explanation",
)


def _count_by(entries, key):
    counts = {}
    for entry in entries:
        value = entry[key]
        counts[value] = counts.get(value, 0) + 1
    return dict(sorted(counts.items()))


def _evidence_kind_counts(entries, field):
    counts = {kind: 0 for kind in TARGET_FEATURE_EVIDENCE_KINDS}
    for entry in entries:
        for kind in entry.get(field, []):
            counts[kind] = counts.get(kind, 0) + 1
    return dict(sorted(counts.items()))


def _auxiliary_evidence_kind(test_name):
    if test_name.startswith("cglc_dump_backend_"):
        return "backend-dump"
    if test_name.startswith("cglc_dump_debug_"):
        return "debug-dump"
    if test_name.startswith("cglc_package_verify_"):
        return "package-inspection"
    if test_name.startswith(("cglc_doctor_json_", "cglc_explain_targets_")):
        return "target-explanation"
    return "unknown"


def _auxiliary_evidence_kind_counts(entries):
    counts = {kind: 0 for kind in AUXILIARY_EVIDENCE_KINDS}
    for entry in entries:
        for test_name in entry.get("auxiliaryEvidenceTests", []):
            kind = _auxiliary_evidence_kind(test_name)
            counts[kind] = counts.get(kind, 0) + 1
    return dict(sorted(counts.items()))


def _validate_summary_count_map(errors, path, actual, expected):
    if actual != expected:
        errors.append(f"{path}: expected counts {expected!r}, got {actual!r}")


def _validate_evidence_summary(errors, path, summary, entries, field, kind_counts):
    entries_with_evidence = [entry for entry in entries if field in entry]
    test_count = sum(len(entry[field]) for entry in entries_with_evidence)

    add_equal_error(
        errors,
        f"{path}.entryCount",
        summary["entryCount"],
        len(entries_with_evidence),
        "entries with evidence",
    )
    add_equal_error(
        errors,
        f"{path}.testCount",
        summary["testCount"],
        test_count,
        "evidence test count",
    )
    _validate_summary_count_map(
        errors,
        f"{path}.byFeatureGroup",
        summary["byFeatureGroup"],
        _count_by(entries_with_evidence, "featureGroup")
        if entries_with_evidence
        else {},
    )
    _validate_summary_count_map(
        errors,
        f"{path}.byEvidenceKind",
        summary["byEvidenceKind"],
        kind_counts(entries_with_evidence),
    )


def _validate_execution_summary(errors, summary, entries):
    if "execution" not in summary:
        return

    execution = summary["execution"]
    executed = 0
    skipped = 0
    passed = 0
    failed = 0
    failures = []
    diagnostic_mismatches = []

    for entry in entries:
        entry_execution = entry.get("execution")
        if entry_execution is None:
            errors.append(f"$.entries[{entry['id']}].execution: expected execution")
            continue

        status = entry_execution["status"]
        if status == "skipped":
            skipped += 1
            if entry_execution["exitCode"] is not None:
                errors.append(
                    f"$.entries[{entry['id']}].execution.exitCode: "
                    "expected null for skipped execution"
                )
        else:
            executed += 1

        if status == "passed":
            passed += 1
            if "failure" in entry_execution:
                errors.append(
                    f"$.entries[{entry['id']}].execution.failure: "
                    "unexpected for passed execution"
                )
        elif status == "failed":
            failed += 1
            failure = entry_execution.get("failure")
            if not failure:
                errors.append(
                    f"$.entries[{entry['id']}].execution.failure: "
                    "expected failure message"
                )
            else:
                failures.append({"id": entry["id"], "failure": failure})

        if entry_execution.get("diagnosticMatchesExpected") is False:
            diagnostic_mismatches.append(
                {
                    "actual": entry_execution.get("diagnosticCodes", []),
                    "expected": entry.get("expectedDiagnostic"),
                    "id": entry["id"],
                }
            )

    add_equal_error(
        errors,
        "$.summary.execution.entryCount",
        execution["entryCount"],
        len(entries),
        "entries length",
    )
    add_equal_error(
        errors, "$.summary.execution.executed", execution["executed"], executed, "count"
    )
    add_equal_error(
        errors, "$.summary.execution.skipped", execution["skipped"], skipped, "count"
    )
    add_equal_error(
        errors, "$.summary.execution.passed", execution["passed"], passed, "count"
    )
    add_equal_error(
        errors, "$.summary.execution.failed", execution["failed"], failed, "count"
    )
    add_equal_error(
        errors,
        "$.summary.execution.diagnosticMismatchCount",
        execution["diagnosticMismatchCount"],
        len(diagnostic_mismatches),
        "diagnostic mismatch count",
    )
    add_equal_error(
        errors, "$.summary.execution.failures", execution["failures"], failures, "list"
    )
    add_equal_error(
        errors,
        "$.summary.execution.diagnosticMismatches",
        execution["diagnosticMismatches"],
        diagnostic_mismatches,
        "list",
    )


def validate_semantics(instance):
    errors = []
    entries = instance["entries"]
    summary = instance["summary"]

    add_equal_error(
        errors,
        "$.summary.total",
        summary["total"],
        len(entries),
        "entries length",
    )
    _validate_summary_count_map(
        errors, "$.summary.byStatus", summary["byStatus"], _count_by(entries, "status")
    )
    _validate_summary_count_map(
        errors,
        "$.summary.byFeatureGroup",
        summary["byFeatureGroup"],
        _count_by(entries, "featureGroup"),
    )
    _validate_summary_count_map(
        errors,
        "$.summary.byLanguageCategory",
        summary["byLanguageCategory"],
        _count_by(entries, "languageCategory"),
    )
    _validate_summary_count_map(
        errors,
        "$.summary.byCommandProfile",
        summary["byCommandProfile"],
        _count_by(entries, "commandProfile"),
    )
    _validate_evidence_summary(
        errors,
        "$.summary.auxiliaryEvidence",
        summary["auxiliaryEvidence"],
        entries,
        "auxiliaryEvidenceTests",
        _auxiliary_evidence_kind_counts,
    )
    _validate_evidence_summary(
        errors,
        "$.summary.targetFeatureEvidence",
        summary["targetFeatureEvidence"],
        entries,
        "targetFeatureEvidenceTests",
        lambda values: _evidence_kind_counts(values, "targetFeatureEvidenceKinds"),
    )
    _validate_execution_summary(errors, summary, entries)

    return errors
