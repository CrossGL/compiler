#!/usr/bin/env python3
"""Compare two CrossGL performance corpus JSON reports."""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation, ROUND_CEILING
from pathlib import Path
from typing import Any, Iterable


SCHEMA_VERSION = 1
TOOL_NAME = "compare_performance_reports"
ADVISORY_THRESHOLD_POLICY_KIND = "advisory-threshold-policy"
ADVISORY_THRESHOLD_POLICY_SCHEMA_VERSION = 1
DEFAULT_ADVISORY_THRESHOLD_PROFILE = "milestone6"
STABILITY_MIN_SAMPLE_COUNT = 2
STABILITY_RECOMMENDED_MAX_SPREAD_PERCENT = Decimal("10")
TIMING_ADVISORY_MIN_SAMPLE_COUNT = STABILITY_MIN_SAMPLE_COUNT
TIMING_ADVISORY_EVIDENCE_POLICY = (
    "Timing threshold claims require repeated baseline and candidate samples "
    "and comparable baseline-policy metadata, with explicit timed-case "
    "fixtureName, target, profile, and optLevel identity. Cases without at "
    "least two samples on both sides, pairs with missing/drifting metadata, or "
    "timed cases that rely on inferred identity are reported as timing "
    "observations, but threshold-exceeded claims are withheld."
)
TIMING_ADVISORY_RELEASE_BLOCKER_POLICY = (
    "Timing advisory thresholds are report-only and are not release blockers "
    "without explicit owner approval."
)
TIMING_THRESHOLD_ENFORCEMENT_POLICY = (
    "Timing thresholds are emitted as report-only observations. They are not "
    "enforced, do not affect comparator exit status, and cannot become release "
    "blockers without explicit owner approval."
)
TIMING_THRESHOLD_RELEASE_CLAIM_MIN_REPEATED_REPORTS = 3
TIMING_THRESHOLD_RELEASE_CLAIM_POLICY = (
    "A timing threshold proposal can become a release claim only after at "
    "least three repeated report pairs with complete structural shape, "
    "compatible host/toolchain/target-profile metadata, explicit timed-case "
    "identity, repeated samples on both sides, and stable report-only "
    "classification. Until then proposals remain advisory observations."
)
TIMING_ADVISORY_METADATA_COMPARABILITY_POLICY = (
    "Timing threshold claims require matching recognized host, toolchain, "
    "target-profile, optimization, comparison-window, and skipped-tool metadata "
    "on both reports. Metadata drift is advisory context only; it never changes "
    "comparator exit status."
)
ADVISORY_THRESHOLD_FAILURE_POLICY = (
    "report-only; advisory timing threshold observations never change "
    "comparator exit status"
)

POLICY_FIELD_PATHS = {
    "hostLabel": (
        ("baselinePolicy", "hostLabel"),
        ("metadata", "hostLabel"),
        ("environment", "hostLabel"),
        ("config", "hostLabel"),
        ("host", "label"),
        ("hostLabel",),
    ),
    "hostClass": (
        ("baselinePolicy", "hostClass"),
        ("metadata", "hostClass"),
        ("environment", "hostClass"),
        ("config", "hostClass"),
        ("host", "class"),
        ("hostClass",),
    ),
    "targetProfile": (
        ("baselinePolicy", "targetProfile"),
        ("metadata", "targetProfile"),
        ("config", "targetProfile"),
        ("targetProfile",),
    ),
    "optLevel": (
        ("baselinePolicy", "optLevel"),
        ("metadata", "optLevel"),
        ("config", "optLevel"),
        ("optLevel",),
    ),
}

TOOLCHAIN_POLICY_FIELD_PATHS = {
    "toolchainLabel": (
        ("baselinePolicy", "toolchainLabel"),
        ("metadata", "toolchainLabel"),
        ("config", "toolchainLabel"),
        ("toolchain", "label"),
        ("toolchain", "name"),
        ("toolchainLabel",),
    ),
    "toolchainClass": (
        ("baselinePolicy", "toolchainClass"),
        ("metadata", "toolchainClass"),
        ("config", "toolchainClass"),
        ("toolchain", "class"),
        ("toolchain", "toolchainClass"),
        ("toolchainClass",),
    ),
    "toolchainVersion": (
        ("baselinePolicy", "toolchainVersion"),
        ("metadata", "toolchainVersion"),
        ("config", "toolchainVersion"),
        ("toolchain", "version"),
        ("toolchainVersion",),
    ),
}

COMPARISON_WINDOW_PATHS = (
    ("baselinePolicy", "comparisonWindow"),
    ("metadata", "comparisonWindow"),
    ("config", "comparisonWindow"),
    ("comparisonWindow",),
)

MEASUREMENT_WINDOW_PATHS = (
    ("metadata", "measurementWindow"),
    ("summary", "measurementWindow"),
    ("measurementWindow",),
)

RUNTIME_ENVIRONMENT_PATHS = (
    ("metadata", "runtimeEnvironment"),
    ("runtimeEnvironment",),
    ("environment", "runtimeEnvironment"),
)

PRODUCER_ADVISORY_THRESHOLD_POLICY_PATHS = {
    "topLevel": ("advisoryThresholdPolicy",),
    "metadata": ("metadata", "advisoryThresholdPolicy"),
}

PRODUCER_THRESHOLD_BASELINE_READINESS_PATHS = {
    "topLevel": ("thresholdBaselineReadiness",),
    "metadata": ("metadata", "thresholdBaselineReadiness"),
}

ADVISORY_CONTEXT_FIELD_NAMES = (
    "hostLabel",
    "hostClass",
    "targetProfile",
    "optLevel",
    "comparisonWindow",
)
REQUIRED_ADVISORY_CONTEXT_FIELDS = (
    *ADVISORY_CONTEXT_FIELD_NAMES,
    "runtimeEnvironment",
    "toolchains",
)
REQUIRED_RUNTIME_ENVIRONMENT_FIELDS = (
    "machine",
    "platform",
    "pythonExecutable",
    "pythonImplementation",
    "pythonVersion",
    "system",
    "systemRelease",
)
REQUIRED_THRESHOLD_CASE_IDENTITY_FIELDS = (
    "fixtureName",
    "target",
    "profile",
    "optLevel",
)

REPORT_ARTIFACT_TOP_LEVEL_FIELDS = (
    "schemaVersion",
    "tool",
    "status",
    "baseline",
    "candidate",
    "metadata",
    "policy",
    "structure",
    "timing",
    "artifactSize",
    "nativeOptimization",
    "reportArtifacts",
)

REQUIRED_SUMMARY_ACCOUNTING_FIELDS = (
    "caseCount",
    "caseCategories",
    "caseCountByCategory",
    "optLevels",
    "caseCountByOptLevel",
    "commandProfiles",
    "caseCountByCommandProfile",
    "caseCountByProfile",
    "caseCountByTarget",
)

REQUIRED_SKIPPED_SUMMARY_ACCOUNTING_FIELDS = (
    "skippedCaseCountByReason",
    "skippedCasesWithUnavailableTools",
    "skippedToolCaseCountByTool",
    "skippedToolCasesByTool",
)

REQUIRED_MANIFEST_ARTIFACT_KIND_FIELDS = (
    "byteSize",
    "caseCount",
    "count",
    "emittedCaseCount",
    "emittedCount",
    "missingCaseCount",
    "missingCount",
)

REQUIRED_NATIVE_OPTIMIZATION_EVIDENCE_FIELDS = (
    "caseCount",
    "caseCountByEvidenceStatus",
    "declaredNativeProfileCount",
    "knownStatusCount",
    "missingDebugOptimizationCount",
    "missingOrUnparsableEvidenceCount",
    "nativeProfileDeclaredButMissingCount",
    "nativeProfileNotDeclaredCount",
    "optimizationWithoutStatusCount",
    "unparsableNativeProfileCount",
)

REQUIRED_NATIVE_ARTIFACT_DESCRIPTOR_OPTIMIZATION_EVIDENCE_FIELDS = (
    "caseCount",
    "caseCountByEvidenceStatus",
    "declaredNativeArtifactDescriptorCount",
    "knownStatusCount",
    "missingOptimizationEvidenceCount",
    "missingOrUnparsableEvidenceCount",
    "nativeArtifactDescriptorDeclaredButMissingCount",
    "nativeArtifactDescriptorNotDeclaredCount",
    "optimizationWithoutStatusCount",
    "unparsableNativeArtifactDescriptorCount",
)

TOOLCHAIN_ENTRY_STRING_FIELDS = (
    "class",
    "classification",
    "label",
    "name",
    "path",
    "requirement",
    "role",
    "status",
    "toolchainClass",
    "version",
)

TOOLCHAIN_ENTRY_BOOL_FIELDS = (
    "available",
    "optional",
    "required",
)

TOOLCHAIN_CANONICAL_BOOL_FIELDS = (
    "available",
    "optional",
    "required",
)


class PerformanceReportComparisonError(RuntimeError):
    """Raised for user-facing report comparison failures."""


@dataclass(frozen=True)
class ReportCase:
    key: str
    report_key: str
    category: str
    command_profile: str | None
    fixture_name: str | None
    opt_level: str | None
    package_mode: str | None
    profile: str | None
    target: str | None
    backend: str | None
    threshold_identity_missing_fields: tuple[str, ...]
    skipped: bool
    skip_reason: str | None
    unavailable_tools: tuple[str, ...]
    status: str | None
    success: bool | None
    elapsed_ns: int | None
    timing_sample_count: int | None
    timing_sample_source: str
    artifact_byte_size: int | None
    artifact_file_count: int | None
    artifact_kind_metrics: dict[str, dict[str, int]]
    native_artifact_descriptor_optimization_evidence: dict[str, Any] | None
    native_artifact_descriptor_optimization_evidence_status: str
    native_artifact_descriptor_optimization_status: str | None
    native_optimization_evidence_status: str
    native_optimization_status: str | None


@dataclass(frozen=True)
class ReportPolicyMetadata:
    fields: dict[str, Any]
    runtime_environment_missing_fields: tuple[str, ...]
    toolchains: dict[str, dict[str, Any]]
    skipped_tool_accounting: dict[str, Any]


@dataclass(frozen=True)
class AdvisoryThresholdRule:
    category: str
    profile: str
    max_regression_percent: Decimal
    label: str
    target: str = "*"
    backend: str = "*"


@dataclass(frozen=True)
class AdvisoryThresholdProfile:
    name: str
    description: str
    rules: tuple[AdvisoryThresholdRule, ...]


ADVISORY_THRESHOLD_PROFILES = {
    "none": AdvisoryThresholdProfile(
        name="none",
        description="Disable report-only threshold proposal classification.",
        rules=(),
    ),
    "milestone6": AdvisoryThresholdProfile(
        name="milestone6",
        description=(
            "Report-only Milestone 6 threshold proposals grouped by fixture "
            "category and benchmark profile. These proposals do not fail the "
            "comparison in v0."
        ),
        rules=(
            AdvisoryThresholdRule(
                category="storage-buffers",
                profile="release",
                max_regression_percent=Decimal("12"),
                label="release storage buffer compile lane",
            ),
            AdvisoryThresholdRule(
                category="texture-sampling",
                profile="release",
                max_regression_percent=Decimal("12"),
                label="release texture sampling compile lane",
            ),
            AdvisoryThresholdRule(
                category="descriptor-arrays",
                profile="release",
                max_regression_percent=Decimal("15"),
                label="release descriptor array compile lane",
            ),
            AdvisoryThresholdRule(
                category="storage-images",
                profile="release",
                max_regression_percent=Decimal("15"),
                label="release storage image compile lane",
            ),
            AdvisoryThresholdRule(
                category="control-flow",
                profile="release",
                max_regression_percent=Decimal("12"),
                label="release control-flow compile lane",
            ),
            AdvisoryThresholdRule(
                category="atomics",
                profile="release",
                max_regression_percent=Decimal("18"),
                label="release atomic operation compile lane",
            ),
            AdvisoryThresholdRule(
                category="*",
                profile="debug",
                max_regression_percent=Decimal("25"),
                label="debug profile compile lane",
            ),
            AdvisoryThresholdRule(
                category="*",
                profile="*",
                max_regression_percent=Decimal("20"),
                label="fallback compile lane",
            ),
        ),
    ),
}


def load_json_report(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise PerformanceReportComparisonError(
            f"could not read report: {path}"
        ) from exc
    except json.JSONDecodeError as exc:
        raise PerformanceReportComparisonError(
            f"invalid report JSON at {path}:{exc.lineno}:{exc.colno}"
        ) from exc
    if not isinstance(payload, dict):
        raise PerformanceReportComparisonError(f"report must be a JSON object: {path}")
    return payload


def case_key_labels(key: str) -> tuple[str | None, str | None]:
    parts = key.split("::")
    if len(parts) < 3:
        return None, None
    return parts[-1], parts[-2]


def case_key_fixture_label(key: str) -> str | None:
    parts = key.split("::")
    if len(parts) < 3:
        return None
    fixture = "::".join(parts[:-2])
    return fixture or None


def normalized_case_key(case: dict[str, Any], report_key: str) -> str:
    """Return the stable comparison identity for a report case.

    Corpus reports are expected to carry structured fixture/profile/target labels.
    Older reports can still be compared by falling back to the legacy case-key
    convention of <fixture>::<target>::<profile>.
    """

    derived_profile, derived_target = case_key_labels(report_key)
    fixture = case_string_label(case, "fixtureName") or case_key_fixture_label(
        report_key
    )
    target = case_string_label(case, "target") or derived_target
    profile = case_string_label(case, "profile") or derived_profile
    if fixture and target and profile:
        return f"{fixture}::{target}::{profile}"
    return report_key


def case_string_label(case: dict[str, Any], field: str) -> str | None:
    value = case.get(field)
    if isinstance(value, str) and value:
        return value
    return None


def case_backend_label(case: dict[str, Any]) -> str | None:
    return (
        case_string_label(case, "backend")
        or case_string_label(case, "targetBackend")
        or case_string_label(case, "backendTarget")
    )


def case_command_profile(case: dict[str, Any]) -> str | None:
    command_profile = case.get("commandProfile")
    if not isinstance(command_profile, dict):
        return None
    return string_value(command_profile.get("name"))


def case_opt_level(case: dict[str, Any]) -> str | None:
    opt_level = case_string_label(case, "optLevel")
    if opt_level is not None:
        return opt_level
    command_profile = case.get("commandProfile")
    if isinstance(command_profile, dict):
        return string_value(command_profile.get("compilerConfig"))
    return None


def case_success(case: dict[str, Any]) -> bool | None:
    value = case.get("success")
    return value if isinstance(value, bool) else None


def case_functional_failure(case: dict[str, Any]) -> bool:
    success = case_success(case)
    if success is False:
        return True
    return case.get("status") == "failed"


def case_unavailable_tools(case: dict[str, Any]) -> tuple[str, ...]:
    values = case.get("unavailableTools")
    if not isinstance(values, list):
        return ()
    labels = sorted({value for value in values if isinstance(value, str) and value})
    return tuple(labels)


def case_skipped(case: dict[str, Any]) -> bool:
    skipped = case.get("skipped")
    if isinstance(skipped, bool):
        return skipped
    return case.get("status") == "skipped"


def raw_case_objects(report: dict[str, Any]) -> list[dict[str, Any]]:
    cases = report.get("cases")
    if not isinstance(cases, list):
        return []
    return [case for case in cases if isinstance(case, dict)]


def report_cases(
    report: dict[str, Any],
    label: str,
    validation_issues: list[str] | None = None,
) -> dict[str, ReportCase]:
    cases = report.get("cases")
    if not isinstance(cases, list):
        if validation_issues is not None:
            validation_issues.append(f"{label}.cases must be an array")
            return {}
        raise PerformanceReportComparisonError(f"{label} report has no cases array")

    indexed: dict[str, ReportCase] = {}
    for index, item in enumerate(cases):
        if not isinstance(item, dict):
            if validation_issues is not None:
                validation_issues.append(f"{label}.cases[{index}] must be an object")
                continue
            raise PerformanceReportComparisonError(
                f"{label} report case {index} must be an object"
            )
        report_key = item.get("case")
        if not isinstance(report_key, str) or not report_key:
            if validation_issues is not None:
                validation_issues.append(
                    f"{label}.cases[{index}].case must be a non-empty string"
                )
                continue
            raise PerformanceReportComparisonError(
                f"{label} report case {index} has no case key"
            )
        key = normalized_case_key(item, report_key)
        if key in indexed:
            existing = indexed[key].report_key
            if validation_issues is not None:
                validation_issues.append(
                    f"{label}.cases[{index}] duplicates normalized case {key!r} "
                    f"from earlier case label {existing!r}"
                )
                continue
            raise PerformanceReportComparisonError(
                f"{label} report contains duplicate normalized case {key!r} "
                f"from case labels {existing!r} and {report_key!r}"
            )
        category = item.get("fixtureCategory")
        if not isinstance(category, str) or not category:
            category = "uncategorized"
        derived_profile, derived_target = case_key_labels(report_key)
        threshold_identity_missing_fields = tuple(
            field
            for field in REQUIRED_THRESHOLD_CASE_IDENTITY_FIELDS
            if case_string_label(item, field) is None
        )
        target = case_string_label(item, "target") or derived_target
        backend = case_backend_label(item) or target
        skipped = case_skipped(item)
        skip_reason = case_string_label(item, "skipReason")
        elapsed_ns = case_elapsed_ns(item)
        sample_count, sample_source = case_timing_sample_count(item, report)
        indexed[key] = ReportCase(
            key=key,
            report_key=report_key,
            category=category,
            command_profile=case_command_profile(item),
            fixture_name=case_string_label(item, "fixtureName")
            or case_key_fixture_label(report_key),
            opt_level=case_opt_level(item),
            package_mode=case_string_label(item, "packageMode"),
            profile=case_string_label(item, "profile") or derived_profile,
            target=target,
            backend=backend,
            threshold_identity_missing_fields=threshold_identity_missing_fields,
            skipped=skipped,
            skip_reason=skip_reason if skipped else None,
            unavailable_tools=case_unavailable_tools(item),
            status=case_string_label(item, "status"),
            success=case_success(item),
            elapsed_ns=elapsed_ns,
            timing_sample_count=sample_count if elapsed_ns is not None else None,
            timing_sample_source=sample_source if elapsed_ns is not None else "untimed",
            artifact_byte_size=case_artifact_metric(item, "byteSize"),
            artifact_file_count=case_artifact_metric(item, "fileCount"),
            artifact_kind_metrics=case_manifest_artifact_kind_metrics(item),
            native_artifact_descriptor_optimization_evidence=(
                case_native_artifact_descriptor_optimization_evidence(item)
            ),
            native_artifact_descriptor_optimization_evidence_status=(
                case_native_artifact_descriptor_optimization_evidence_status(item)
            ),
            native_artifact_descriptor_optimization_status=(
                case_native_artifact_descriptor_optimization_status(item)
            ),
            native_optimization_evidence_status=(
                case_native_optimization_evidence_status(item)
            ),
            native_optimization_status=case_native_optimization_status(item),
        )
    return indexed


def report_config_labels(report: dict[str, Any], field: str) -> set[str]:
    config = report.get("config")
    if not isinstance(config, dict):
        return set()
    values = config.get(field)
    if not isinstance(values, list):
        return set()
    return {value for value in values if isinstance(value, str) and value}


def report_profiles(report: dict[str, Any], cases: dict[str, ReportCase]) -> set[str]:
    return report_config_labels(report, "profiles") | {
        case.profile for case in cases.values() if case.profile
    }


def report_targets(report: dict[str, Any], cases: dict[str, ReportCase]) -> set[str]:
    return report_config_labels(report, "targets") | {
        case.target for case in cases.values() if case.target
    }


def report_command_profiles(
    report: dict[str, Any], cases: dict[str, ReportCase]
) -> set[str]:
    return report_config_labels(report, "commandProfiles") | {
        case.command_profile for case in cases.values() if case.command_profile
    }


def report_toolchain_labels(
    report: dict[str, Any], cases: dict[str, ReportCase]
) -> set[str]:
    labels: set[str] = set()
    tool_availability = report.get("toolAvailability")
    if isinstance(tool_availability, dict):
        labels.update(
            label for label in tool_availability if isinstance(label, str) and label
        )
    for case in cases.values():
        labels.update(case.unavailable_tools)
    return labels


def report_unavailable_toolchain_labels(
    report: dict[str, Any], cases: dict[str, ReportCase]
) -> set[str]:
    labels: set[str] = set()
    tool_availability = report.get("toolAvailability")
    if isinstance(tool_availability, dict):
        for label, value in tool_availability.items():
            if not isinstance(label, str) or not label:
                continue
            if not isinstance(value, dict):
                continue
            if value.get("available") is False or value.get("status") == "unavailable":
                labels.add(label)
    for case in cases.values():
        labels.update(case.unavailable_tools)
    return labels


def skipped_cases(cases: dict[str, ReportCase]) -> dict[str, str | None]:
    return {key: case.skip_reason for key, case in cases.items() if case.skipped}


def functional_failure_cases(cases: dict[str, ReportCase]) -> dict[str, str]:
    failures: dict[str, str] = {}
    for key, case in cases.items():
        if case.success is False:
            failures[key] = case.status or "success=false"
        elif case.status == "failed":
            failures[key] = "failed"
    return failures


def case_elapsed_ns(case: dict[str, Any]) -> int | None:
    timing = case.get("timing")
    if not isinstance(timing, dict):
        return None
    elapsed_ns = timing.get("elapsedNs")
    if isinstance(elapsed_ns, bool) or not isinstance(elapsed_ns, int):
        return None
    if elapsed_ns < 0:
        return None
    return elapsed_ns


def report_comparison_window_sample_count(report: dict[str, Any]) -> int | None:
    for path in COMPARISON_WINDOW_PATHS:
        value = value_at_path(report, path)
        if not isinstance(value, dict):
            continue
        sample_count = nonnegative_int_value(value.get("sampleCount"))
        if sample_count is not None:
            return sample_count
    return None


def report_measurement_window_sample_count(
    report: dict[str, Any],
) -> tuple[int | None, str | None]:
    for path in MEASUREMENT_WINDOW_PATHS:
        value = value_at_path(report, path)
        if not isinstance(value, dict):
            continue
        sample_count = nonnegative_int_value(value.get("sampleCount"))
        if sample_count is not None:
            return sample_count, f"{dotted_path(path)}.sampleCount"
    return None, None


def case_timing_sample_count(
    case: dict[str, Any], report: dict[str, Any]
) -> tuple[int | None, str]:
    timing = case.get("timing")
    if not isinstance(timing, dict):
        return None, "untimed"

    sample_count = nonnegative_int_value(timing.get("sampleCount"))
    if sample_count is not None:
        return sample_count, "timing.sampleCount"

    runs = timing.get("runs")
    if isinstance(runs, list):
        return len(runs), "timing.runs"

    measurement_sample_count, measurement_sample_source = (
        report_measurement_window_sample_count(report)
    )
    if measurement_sample_count is not None:
        return (
            measurement_sample_count,
            measurement_sample_source or "measurementWindow.sampleCount",
        )

    report_sample_count = report_comparison_window_sample_count(report)
    if report_sample_count is not None:
        return report_sample_count, "comparisonWindow.sampleCount"

    return None, "missing"


def case_artifact_summary(case: dict[str, Any]) -> dict[str, Any]:
    summary = case.get("artifactSummary")
    return summary if isinstance(summary, dict) else {}


def case_artifact_metric(case: dict[str, Any], field: str) -> int | None:
    summary = case_artifact_summary(case)
    if summary.get("available") is not True:
        return None
    return nonnegative_int_value(summary.get(field))


def case_manifest_artifact_kind_metrics(
    case: dict[str, Any],
) -> dict[str, dict[str, int]]:
    summary = case_artifact_summary(case)
    artifacts = summary.get("manifestArtifacts")
    if not isinstance(artifacts, list):
        return {}

    metrics: dict[str, dict[str, int]] = {}
    for artifact in artifacts:
        if not isinstance(artifact, dict):
            continue
        kind = string_value(artifact.get("kind"))
        if kind is None:
            continue
        kind_metrics = metrics.setdefault(
            kind,
            {
                "byteSize": 0,
                "count": 0,
                "emittedCount": 0,
                "missingCount": 0,
            },
        )
        kind_metrics["count"] += 1
        exists = artifact.get("exists")
        if exists is True:
            kind_metrics["emittedCount"] += 1
            kind_metrics["byteSize"] += (
                nonnegative_int_value(artifact.get("bytes")) or 0
            )
        elif exists is False:
            kind_metrics["missingCount"] += 1
    return {kind: metrics[kind] for kind in sorted(metrics)}


def manifest_artifact_kind_summary(
    cases: list[dict[str, Any]],
) -> dict[str, dict[str, int]]:
    summary: dict[str, dict[str, int]] = {}
    for case in cases:
        for kind, metrics in case_manifest_artifact_kind_metrics(case).items():
            kind_summary = summary.setdefault(
                kind,
                {
                    "byteSize": 0,
                    "caseCount": 0,
                    "count": 0,
                    "emittedCaseCount": 0,
                    "emittedCount": 0,
                    "missingCaseCount": 0,
                    "missingCount": 0,
                },
            )
            kind_summary["byteSize"] += metrics["byteSize"]
            kind_summary["caseCount"] += 1
            kind_summary["count"] += metrics["count"]
            kind_summary["emittedCount"] += metrics["emittedCount"]
            kind_summary["missingCount"] += metrics["missingCount"]
            if metrics["emittedCount"] > 0:
                kind_summary["emittedCaseCount"] += 1
            if metrics["missingCount"] > 0:
                kind_summary["missingCaseCount"] += 1
    return {kind: summary[kind] for kind in sorted(summary)}


def manifest_artifact_kind_case_count(cases: list[dict[str, Any]]) -> int:
    return sum(1 for case in cases if case_manifest_artifact_kind_metrics(case))


def case_native_artifact_descriptor(case: dict[str, Any]) -> dict[str, Any] | None:
    summary = case_artifact_summary(case)
    descriptor = summary.get("nativeArtifactDescriptor")
    return descriptor if isinstance(descriptor, dict) else None


def case_native_artifact_descriptor_optimization_evidence(
    case: dict[str, Any],
) -> dict[str, Any] | None:
    descriptor = case_native_artifact_descriptor(case)
    if not isinstance(descriptor, dict):
        return None
    evidence = descriptor.get("optimizationEvidence")
    return normalized_json_value(evidence) if isinstance(evidence, dict) else None


def case_native_artifact_descriptor_optimization_status(
    case: dict[str, Any],
) -> str | None:
    evidence = case_native_artifact_descriptor_optimization_evidence(case)
    if not isinstance(evidence, dict):
        return None
    return string_value(evidence.get("status"))


def case_native_artifact_descriptor_optimization_evidence_status(
    case: dict[str, Any],
) -> str:
    descriptor = case_native_artifact_descriptor(case)
    if not isinstance(descriptor, dict):
        return "native-artifact-descriptor-not-declared"
    evidence = descriptor.get("optimizationEvidence")
    if isinstance(evidence, dict):
        if string_value(evidence.get("status")) is not None:
            return "known-status"
        if descriptor.get("available") is True or descriptor.get("declared") is True:
            return "optimization-without-status"
    if descriptor.get("declared") is True and descriptor.get("available") is not True:
        return "declared-native-artifact-descriptor-missing"
    if descriptor.get("available") is True and descriptor.get("parseError") is not None:
        return "unparsable-native-artifact-descriptor"
    if descriptor.get("available") is True:
        return "missing-optimization-evidence"
    return "native-artifact-descriptor-not-declared"


def case_native_optimization_status(case: dict[str, Any]) -> str | None:
    summary = case_artifact_summary(case)
    native_profile = summary.get("nativeProfile")
    if not isinstance(native_profile, dict):
        return None
    optimization = native_profile.get("optimization")
    if not isinstance(optimization, dict):
        return None
    return string_value(optimization.get("status"))


def case_native_optimization_evidence_status(case: dict[str, Any]) -> str:
    summary = case_artifact_summary(case)
    native_profile = summary.get("nativeProfile")
    if not isinstance(native_profile, dict):
        return "native-profile-not-declared"
    optimization = native_profile.get("optimization")
    if not isinstance(optimization, dict):
        if (
            native_profile.get("declared") is True
            and native_profile.get("available") is not True
        ):
            return "declared-native-profile-missing"
        if (
            native_profile.get("available") is True
            and native_profile.get("parseError") is not None
        ):
            return "unparsable-native-profile"
        if native_profile.get("available") is True:
            return "missing-debug-optimization"
        return "native-profile-not-declared"
    if string_value(optimization.get("status")) is not None:
        return "known-status"
    if (
        native_profile.get("available") is True
        or native_profile.get("declared") is True
    ):
        return "optimization-without-status"
    if (
        native_profile.get("declared") is True
        and native_profile.get("available") is not True
    ):
        return "declared-native-profile-missing"
    if (
        native_profile.get("available") is True
        and native_profile.get("parseError") is not None
    ):
        return "unparsable-native-profile"
    if native_profile.get("available") is True:
        return "missing-debug-optimization"
    return "native-profile-not-declared"


def case_verification(case: dict[str, Any]) -> dict[str, Any]:
    verification = case.get("verification")
    return verification if isinstance(verification, dict) else {}


def nonnegative_int_value(value: Any) -> int | None:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        return None
    return value


def skipped_tool_case_count_by_tool(cases: list[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for case in cases:
        if not case_skipped(case):
            continue
        for tool in case_unavailable_tools(case):
            counts[tool] = counts.get(tool, 0) + 1
    return dict(sorted(counts.items()))


def skipped_tool_cases_by_tool_from_raw(
    cases: list[dict[str, Any]],
) -> dict[str, list[str]]:
    cases_by_tool: dict[str, list[str]] = {}
    for case in cases:
        if not case_skipped(case):
            continue
        case_key = case_string_label(case, "case")
        if case_key is None:
            continue
        for tool in case_unavailable_tools(case):
            cases_by_tool.setdefault(tool, []).append(case_key)
    return {
        tool: sorted(case_keys) for tool, case_keys in sorted(cases_by_tool.items())
    }


def skipped_tool_cases_by_tool(cases: dict[str, ReportCase]) -> dict[str, list[str]]:
    cases_by_tool: dict[str, list[str]] = {}
    for key, case in cases.items():
        if not case.skipped:
            continue
        for tool in case.unavailable_tools:
            cases_by_tool.setdefault(tool, []).append(key)
    return {tool: sorted(keys) for tool, keys in sorted(cases_by_tool.items())}


def skipped_case_count_by_reason(cases: list[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for case in cases:
        if not case_skipped(case):
            continue
        reason = case_string_label(case, "skipReason") or "unspecified"
        counts[reason] = counts.get(reason, 0) + 1
    return dict(sorted(counts.items()))


def skipped_cases_with_unavailable_tools(cases: list[dict[str, Any]]) -> list[str]:
    return sorted(
        {
            case_key
            for case in cases
            if case_skipped(case) and case_unavailable_tools(case)
            for case_key in [case_string_label(case, "case")]
            if case_key is not None
        }
    )


def artifact_accounting(cases: list[dict[str, Any]]) -> dict[str, int]:
    artifact_available_count = 0
    artifact_byte_size = 0
    artifact_file_count = 0
    for case in cases:
        summary = case_artifact_summary(case)
        if summary.get("available") is True:
            artifact_available_count += 1
        artifact_byte_size += nonnegative_int_value(summary.get("byteSize")) or 0
        artifact_file_count += nonnegative_int_value(summary.get("fileCount")) or 0
    return {
        "artifactAvailableCount": artifact_available_count,
        "artifactByteSize": artifact_byte_size,
        "artifactFileCount": artifact_file_count,
    }


def verification_accounting(cases: list[dict[str, Any]]) -> dict[str, int]:
    requested_count = 0
    passed_count = 0
    skipped_count = 0
    for case in cases:
        verification = case_verification(case)
        if verification.get("requested") is True:
            requested_count += 1
        if verification.get("status") in ("passed", "build-passed"):
            passed_count += 1
        if verification.get("status") == "skipped":
            skipped_count += 1
    return {
        "verificationPassedCount": passed_count,
        "verificationRequestedCount": requested_count,
        "verificationSkippedCount": skipped_count,
    }


def case_timing_label(case: dict[str, Any], index: int) -> str:
    value = case_string_label(case, "case")
    return value if value is not None else f"cases[{index}]"


def timing_runs_value(timing: dict[str, Any], field: str) -> list[Any]:
    value = timing.get(field)
    return value if isinstance(value, list) else []


def timing_run_accounting(cases: list[dict[str, Any]]) -> dict[str, int]:
    timed_cases = [case for case in cases if isinstance(case.get("timing"), dict)]
    return {
        "measuredRunCount": sum(
            len(timing_runs_value(case["timing"], "runs")) for case in timed_cases
        ),
        "timedCaseCount": len(timed_cases),
        "warmupRunCount": sum(
            len(timing_runs_value(case["timing"], "warmups")) for case in timed_cases
        ),
    }


def timing_run_array_validation(
    value: Any, path: str, issues: list[str]
) -> tuple[list[int], int | None, bool]:
    if value is None:
        return [], None, True
    if not isinstance(value, list):
        issues.append(f"{path} must be an array")
        return [], None, False

    durations: list[int] = []
    valid = True
    for index, entry in enumerate(value):
        entry_path = f"{path}[{index}]"
        if not isinstance(entry, dict):
            issues.append(f"{entry_path} must be an object")
            valid = False
            continue
        duration = nonnegative_int_value(entry.get("durationNs"))
        if duration is None:
            issues.append(f"{entry_path}.durationNs must be a non-negative integer")
            valid = False
        else:
            durations.append(duration)
        for field in ("iteration", "outputBytes", "stderrBytes", "stdoutBytes"):
            if field not in entry or entry[field] is None:
                continue
            if nonnegative_int_value(entry[field]) is None:
                issues.append(f"{entry_path}.{field} must be a non-negative integer")
                valid = False
        if "exitStatus" in entry and entry["exitStatus"] is not None:
            if isinstance(entry["exitStatus"], bool) or not isinstance(
                entry["exitStatus"], int
            ):
                issues.append(f"{entry_path}.exitStatus must be an integer")
                valid = False
    return durations, len(value), valid


def timing_summary_validation_issues(
    cases: list[dict[str, Any]], label: str
) -> list[str]:
    issues: list[str] = []
    for index, case in enumerate(cases):
        timing = case.get("timing")
        if timing is None:
            continue
        path = f"{label}.cases[{index}].timing"
        if not isinstance(timing, dict):
            issues.append(f"{path} must be an object or null")
            continue

        elapsed_ns = nonnegative_int_value(timing.get("elapsedNs"))
        if elapsed_ns is None:
            issues.append(f"{path}.elapsedNs must be a non-negative integer")

        case_elapsed_ns = case.get("elapsedNs")
        if case_elapsed_ns is not None:
            if nonnegative_int_value(case_elapsed_ns) is None:
                issues.append(
                    f"{label}.cases[{index}].elapsedNs must be a non-negative integer"
                )
            elif elapsed_ns is not None and case_elapsed_ns != elapsed_ns:
                issues.append(
                    f"{label}.cases[{index}].elapsedNs={case_elapsed_ns} does not "
                    f"match timing.elapsedNs ({elapsed_ns})"
                )

        run_durations, run_count, runs_valid = timing_run_array_validation(
            timing.get("runs"), f"{path}.runs", issues
        )
        _, warmup_count, _ = timing_run_array_validation(
            timing.get("warmups"), f"{path}.warmups", issues
        )

        sample_count = timing.get("sampleCount")
        if sample_count is not None:
            if nonnegative_int_value(sample_count) is None:
                issues.append(f"{path}.sampleCount must be a non-negative integer")
            elif run_count is not None and sample_count != run_count:
                issues.append(
                    f"{path}.sampleCount={sample_count} does not match runs length "
                    f"({run_count})"
                )

        declared_warmup_count = timing.get("warmupCount")
        if declared_warmup_count is not None:
            if nonnegative_int_value(declared_warmup_count) is None:
                issues.append(f"{path}.warmupCount must be a non-negative integer")
            elif warmup_count is not None and declared_warmup_count != warmup_count:
                issues.append(
                    f"{path}.warmupCount={declared_warmup_count} does not match "
                    f"warmups length ({warmup_count})"
                )

        if not runs_valid or not run_durations:
            continue

        sorted_durations = sorted(run_durations)
        expected_summary = {
            "maxNs": sorted_durations[-1],
            "meanNs": sum(sorted_durations) // len(sorted_durations),
            "medianNs": sorted_durations[len(sorted_durations) // 2],
            "minNs": sorted_durations[0],
        }
        if elapsed_ns is not None and elapsed_ns != expected_summary["medianNs"]:
            issues.append(
                f"{path}.elapsedNs={elapsed_ns} does not match median run duration "
                f"({expected_summary['medianNs']})"
            )
        for field, expected in expected_summary.items():
            value = timing.get(field)
            if value is None:
                continue
            if nonnegative_int_value(value) is None:
                issues.append(f"{path}.{field} must be a non-negative integer")
            elif value != expected:
                issues.append(
                    f"{path}.{field}={value} does not match runs ({expected})"
                )

        exit_statuses = timing.get("exitStatuses")
        if exit_statuses is None:
            continue
        if not isinstance(exit_statuses, list) or any(
            isinstance(status, bool) or not isinstance(status, int)
            for status in exit_statuses
        ):
            issues.append(f"{path}.exitStatuses must be a list of integers")
            continue
        run_exit_statuses = sorted(
            {
                entry["exitStatus"]
                for entry in timing.get("runs", [])
                if isinstance(entry, dict)
                and isinstance(entry.get("exitStatus"), int)
                and not isinstance(entry.get("exitStatus"), bool)
            }
        )
        if (
            len(run_exit_statuses)
            == len(
                {
                    entry.get("exitStatus")
                    for entry in timing.get("runs", [])
                    if isinstance(entry, dict) and "exitStatus" in entry
                }
            )
            and exit_statuses != run_exit_statuses
        ):
            issues.append(
                f"{path}.exitStatuses={exit_statuses!r} does not match runs "
                f"({run_exit_statuses!r})"
            )
    return issues


def valid_measurement_window(
    value: Any, path: str
) -> tuple[dict[str, Any] | None, list[str]]:
    if not isinstance(value, dict):
        return None, [f"{path} must be an object"]

    issues: list[str] = []
    normalized: dict[str, Any] = {}
    for field in ("sampleCount", "warmupCount"):
        field_value = value.get(field)
        normalized_value = nonnegative_int_value(field_value)
        if normalized_value is None:
            issues.append(f"{path}.{field} must be a non-negative integer")
        else:
            normalized[field] = normalized_value

    unit = value.get("unit")
    if not isinstance(unit, str) or not unit:
        issues.append(f"{path}.unit must be a non-empty string")
    else:
        normalized["unit"] = unit

    return (normalized if not issues else None), issues


def timing_window_accounting_from_cases(
    cases: list[dict[str, Any]], sample_count: int, warmup_count: int
) -> dict[str, Any]:
    timed_cases = [
        (index, case)
        for index, case in enumerate(cases)
        if isinstance(case.get("timing"), dict)
    ]
    measured_run_count = sum(
        len(timing_runs_value(case["timing"], "runs")) for _, case in timed_cases
    )
    warmup_run_count = sum(
        len(timing_runs_value(case["timing"], "warmups")) for _, case in timed_cases
    )
    mismatched_cases = sorted(
        case_timing_label(case, index)
        for index, case in timed_cases
        if case["timing"].get("sampleCount") != sample_count
        or case["timing"].get("warmupCount") != warmup_count
        or len(timing_runs_value(case["timing"], "runs")) != sample_count
        or len(timing_runs_value(case["timing"], "warmups")) != warmup_count
    )
    expected_measured_run_count = len(timed_cases) * sample_count
    expected_warmup_run_count = len(timed_cases) * warmup_count
    return {
        "consistent": (
            not mismatched_cases
            and measured_run_count == expected_measured_run_count
            and warmup_run_count == expected_warmup_run_count
        ),
        "expectedMeasuredRunCount": expected_measured_run_count,
        "expectedSampleCount": sample_count,
        "expectedWarmupCount": warmup_count,
        "expectedWarmupRunCount": expected_warmup_run_count,
        "measuredRunCount": measured_run_count,
        "mismatchedCaseCount": len(mismatched_cases),
        "mismatchedCases": mismatched_cases,
        "timedCaseCount": len(timed_cases),
        "warmupRunCount": warmup_run_count,
    }


def timing_measurement_window_issues(
    cases: list[dict[str, Any]],
    measurement_window: dict[str, Any],
    label: str,
) -> list[str]:
    issues: list[str] = []
    sample_count = measurement_window["sampleCount"]
    warmup_count = measurement_window["warmupCount"]
    for index, case in enumerate(cases):
        timing = case.get("timing")
        if not isinstance(timing, dict):
            continue
        path = f"{label}.cases[{index}].timing"
        for field, expected in (
            ("sampleCount", sample_count),
            ("warmupCount", warmup_count),
        ):
            value = timing.get(field)
            if value is None:
                continue
            if nonnegative_int_value(value) is None:
                issues.append(f"{path}.{field} must be a non-negative integer")
            elif value != expected:
                issues.append(
                    f"{path}.{field}={value} does not match "
                    f"measurementWindow.{field} ({expected})"
                )
        for field, expected in (("runs", sample_count), ("warmups", warmup_count)):
            value = timing.get(field)
            if value is None:
                continue
            if not isinstance(value, list):
                issues.append(f"{path}.{field} must be an array")
            elif len(value) != expected:
                issues.append(
                    f"{path}.{field} has {len(value)} entr"
                    f"{'y' if len(value) == 1 else 'ies'}; expected {expected} "
                    f"from measurementWindow"
                )
    return issues


def timing_window_summary_issues(
    summary: dict[str, Any],
    cases: list[dict[str, Any]],
    measurement_window: dict[str, Any] | None,
    label: str,
) -> list[str]:
    timing_window = summary.get("timingWindow")
    if timing_window is None:
        return []
    path = f"{label}.summary.timingWindow"
    if not isinstance(timing_window, dict):
        return [f"{path} must be an object"]

    issues: list[str] = []
    integer_fields = (
        "expectedMeasuredRunCount",
        "expectedSampleCount",
        "expectedWarmupCount",
        "expectedWarmupRunCount",
        "measuredRunCount",
        "mismatchedCaseCount",
        "timedCaseCount",
        "warmupRunCount",
    )
    for field in integer_fields:
        value = timing_window.get(field)
        if nonnegative_int_value(value) is None:
            issues.append(f"{path}.{field} must be a non-negative integer")

    if not isinstance(timing_window.get("consistent"), bool):
        issues.append(f"{path}.consistent must be a boolean")

    mismatched_cases = timing_window.get("mismatchedCases")
    if not isinstance(mismatched_cases, list) or any(
        not isinstance(case_key, str) or not case_key for case_key in mismatched_cases
    ):
        issues.append(f"{path}.mismatchedCases must be a list of case keys")

    if issues:
        return issues

    expected_sample_count = timing_window["expectedSampleCount"]
    expected_warmup_count = timing_window["expectedWarmupCount"]
    if measurement_window is not None:
        if expected_sample_count != measurement_window["sampleCount"]:
            issues.append(
                f"{path}.expectedSampleCount={expected_sample_count} does not "
                f"match measurementWindow.sampleCount "
                f"({measurement_window['sampleCount']})"
            )
        if expected_warmup_count != measurement_window["warmupCount"]:
            issues.append(
                f"{path}.expectedWarmupCount={expected_warmup_count} does not "
                f"match measurementWindow.warmupCount "
                f"({measurement_window['warmupCount']})"
            )

    expected = timing_window_accounting_from_cases(
        cases, expected_sample_count, expected_warmup_count
    )
    for field, expected_value in expected.items():
        if timing_window.get(field) != expected_value:
            issues.append(
                f"{path}.{field}={timing_window.get(field)!r} does not match "
                f"cases ({expected_value!r})"
            )
    if expected["consistent"] is not True:
        issues.append(
            f"{path}.consistent must be true; mismatched cases: "
            f"{expected['mismatchedCases']!r}"
        )
    return issues


def measurement_window_validation_issues(
    report: dict[str, Any], cases: list[dict[str, Any]], label: str
) -> list[str]:
    issues: list[str] = []
    metadata = report.get("metadata")
    summary = report.get("summary")
    metadata_window: dict[str, Any] | None = None
    summary_window: dict[str, Any] | None = None

    if isinstance(metadata, dict) and "measurementWindow" in metadata:
        metadata_window, window_issues = valid_measurement_window(
            metadata["measurementWindow"], f"{label}.metadata.measurementWindow"
        )
        issues.extend(window_issues)

    if isinstance(summary, dict) and "measurementWindow" in summary:
        summary_window, window_issues = valid_measurement_window(
            summary["measurementWindow"], f"{label}.summary.measurementWindow"
        )
        issues.extend(window_issues)

    if metadata_window is not None and summary_window is not None:
        if metadata_window != summary_window:
            issues.append(
                f"{label}.summary.measurementWindow={summary_window!r} does not "
                f"match metadata.measurementWindow ({metadata_window!r})"
            )

    measurement_window = summary_window or metadata_window
    if measurement_window is not None:
        issues.extend(
            timing_measurement_window_issues(cases, measurement_window, label)
        )

    if isinstance(summary, dict):
        issues.extend(
            timing_window_summary_issues(summary, cases, measurement_window, label)
        )
    return issues


def execution_accounting(cases: list[dict[str, Any]]) -> dict[str, int]:
    return {
        "dryRunCount": sum(1 for case in cases if case.get("status") == "dry-run"),
        "failureCount": sum(1 for case in cases if case_functional_failure(case)),
        "successCount": sum(1 for case in cases if case_success(case) is True),
    }


def count_report_case_field(cases: dict[str, ReportCase], field: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for case in cases.values():
        value = getattr(case, field)
        if not isinstance(value, str) or not value:
            continue
        counts[value] = counts.get(value, 0) + 1
    return dict(sorted(counts.items()))


def summary_count_mapping_issue(
    summary: dict[str, Any], field: str, expected: dict[str, int], label: str
) -> str | None:
    value = summary.get(field)
    if value is None:
        return None
    if not isinstance(value, dict):
        return f"{label}.summary.{field} must be an object"
    if value != expected:
        return f"{label}.summary.{field}={value!r} does not match cases ({expected!r})"
    return None


def summary_label_list_issue(
    summary: dict[str, Any], field: str, expected: list[str], label: str
) -> str | None:
    value = summary.get(field)
    if value is None:
        return None
    if not isinstance(value, list) or any(
        not isinstance(entry, str) or not entry for entry in value
    ):
        return f"{label}.summary.{field} must be a list of strings"
    if value != expected:
        return f"{label}.summary.{field}={value!r} does not match cases ({expected!r})"
    return None


def case_count_by_category_target(
    cases: dict[str, ReportCase],
) -> dict[str, dict[str, int]]:
    counts: dict[str, dict[str, int]] = {}
    for case in cases.values():
        if not case.target:
            continue
        target_counts = counts.setdefault(case.category, {})
        target_counts[case.target] = target_counts.get(case.target, 0) + 1
    return {
        category: dict(sorted(target_counts.items()))
        for category, target_counts in sorted(counts.items())
    }


def summary_nested_count_mapping_issue(
    summary: dict[str, Any],
    field: str,
    expected: dict[str, dict[str, int]],
    label: str,
) -> str | None:
    value = summary.get(field)
    if value is None:
        return None
    if not isinstance(value, dict):
        return f"{label}.summary.{field} must be an object"
    for outer_key, nested_value in value.items():
        if not isinstance(outer_key, str) or not outer_key:
            return f"{label}.summary.{field} must use non-empty string keys"
        if not isinstance(nested_value, dict):
            return f"{label}.summary.{field}.{outer_key} must be an object"
        for inner_key, count in nested_value.items():
            if not isinstance(inner_key, str) or not inner_key:
                return (
                    f"{label}.summary.{field}.{outer_key} must use non-empty "
                    "string keys"
                )
            if isinstance(count, bool) or not isinstance(count, int) or count < 0:
                return (
                    f"{label}.summary.{field}.{outer_key}.{inner_key} must be "
                    "a non-negative integer"
                )
    if value != expected:
        return f"{label}.summary.{field}={value!r} does not match cases ({expected!r})"
    return None


def manifest_artifact_kind_summary_issues(
    summary: dict[str, Any], cases: list[dict[str, Any]], label: str
) -> list[str]:
    issues: list[str] = []
    expected_kinds = manifest_artifact_kind_summary(cases)
    expected_case_count = manifest_artifact_kind_case_count(cases)

    kind_case_count = summary.get("manifestArtifactKindCaseCount")
    if kind_case_count is not None:
        if (
            isinstance(kind_case_count, bool)
            or not isinstance(kind_case_count, int)
            or kind_case_count < 0
        ):
            issues.append(
                f"{label}.summary.manifestArtifactKindCaseCount must be an integer"
            )
        elif kind_case_count != expected_case_count:
            issues.append(
                f"{label}.summary.manifestArtifactKindCaseCount={kind_case_count} "
                f"does not match cases ({expected_case_count})"
            )

    kind_count = summary.get("manifestArtifactKindCount")
    if kind_count is not None:
        if (
            isinstance(kind_count, bool)
            or not isinstance(kind_count, int)
            or kind_count < 0
        ):
            issues.append(
                f"{label}.summary.manifestArtifactKindCount must be an integer"
            )
        elif kind_count != len(expected_kinds):
            issues.append(
                f"{label}.summary.manifestArtifactKindCount={kind_count} "
                f"does not match cases ({len(expected_kinds)})"
            )

    value = summary.get("manifestArtifactKinds")
    if value is None:
        return issues
    if not isinstance(value, dict):
        issues.append(f"{label}.summary.manifestArtifactKinds must be an object")
        return issues

    for kind, kind_metrics in value.items():
        kind_path = f"{label}.summary.manifestArtifactKinds.{kind}"
        if not isinstance(kind, str) or not kind:
            issues.append(f"{label}.summary.manifestArtifactKinds must use kind keys")
            continue
        if not isinstance(kind_metrics, dict):
            issues.append(f"{kind_path} must be an object")
            continue
        for field in REQUIRED_MANIFEST_ARTIFACT_KIND_FIELDS:
            if field not in kind_metrics:
                issues.append(f"{kind_path}.{field} is required")
                continue
            metric_value = kind_metrics[field]
            if (
                isinstance(metric_value, bool)
                or not isinstance(metric_value, int)
                or metric_value < 0
            ):
                issues.append(f"{kind_path}.{field} must be a non-negative integer")
    if value != expected_kinds:
        issues.append(
            f"{label}.summary.manifestArtifactKinds={value!r} "
            f"does not match cases ({expected_kinds!r})"
        )
    return issues


def native_optimization_evidence_summary_from_counts(
    *, case_count: int, evidence_counts: dict[str, int]
) -> dict[str, Any]:
    known_status_count = evidence_counts.get("known-status", 0)
    missing_count = evidence_counts.get("missing-debug-optimization", 0)
    unparsable_count = evidence_counts.get("unparsable-native-profile", 0)
    declared_missing_count = evidence_counts.get("declared-native-profile-missing", 0)
    without_status_count = evidence_counts.get("optimization-without-status", 0)
    not_declared_count = evidence_counts.get("native-profile-not-declared", 0)
    return {
        "caseCount": case_count,
        "caseCountByEvidenceStatus": evidence_counts,
        "declaredNativeProfileCount": case_count - not_declared_count,
        "knownStatusCount": known_status_count,
        "missingDebugOptimizationCount": missing_count,
        "missingOrUnparsableEvidenceCount": (
            missing_count + unparsable_count + declared_missing_count
        ),
        "nativeProfileDeclaredButMissingCount": declared_missing_count,
        "nativeProfileNotDeclaredCount": not_declared_count,
        "optimizationWithoutStatusCount": without_status_count,
        "unparsableNativeProfileCount": unparsable_count,
    }


def native_artifact_descriptor_evidence_summary_from_counts(
    *, case_count: int, evidence_counts: dict[str, int]
) -> dict[str, Any]:
    known_status_count = evidence_counts.get("known-status", 0)
    missing_count = evidence_counts.get("missing-optimization-evidence", 0)
    unparsable_count = evidence_counts.get("unparsable-native-artifact-descriptor", 0)
    declared_missing_count = evidence_counts.get(
        "declared-native-artifact-descriptor-missing", 0
    )
    without_status_count = evidence_counts.get("optimization-without-status", 0)
    not_declared_count = evidence_counts.get(
        "native-artifact-descriptor-not-declared", 0
    )
    return {
        "caseCount": case_count,
        "caseCountByEvidenceStatus": evidence_counts,
        "declaredNativeArtifactDescriptorCount": case_count - not_declared_count,
        "knownStatusCount": known_status_count,
        "missingOptimizationEvidenceCount": missing_count,
        "missingOrUnparsableEvidenceCount": (
            missing_count + unparsable_count + declared_missing_count
        ),
        "nativeArtifactDescriptorDeclaredButMissingCount": declared_missing_count,
        "nativeArtifactDescriptorNotDeclaredCount": not_declared_count,
        "optimizationWithoutStatusCount": without_status_count,
        "unparsableNativeArtifactDescriptorCount": unparsable_count,
    }


def native_optimization_summary_issues(
    summary: dict[str, Any], cases: dict[str, ReportCase], label: str
) -> list[str]:
    issues: list[str] = []
    status_counts = count_report_case_field(cases, "native_optimization_status")
    evidence_counts = count_report_case_field(
        cases, "native_optimization_evidence_status"
    )
    descriptor_status_counts = count_report_case_field(
        cases, "native_artifact_descriptor_optimization_status"
    )
    descriptor_evidence_counts = count_report_case_field(
        cases, "native_artifact_descriptor_optimization_evidence_status"
    )
    for issue in (
        summary_count_mapping_issue(
            summary,
            "caseCountByNativeOptimizationStatus",
            status_counts,
            label,
        ),
        summary_label_list_issue(
            summary,
            "nativeOptimizationStatuses",
            sorted(status_counts),
            label,
        ),
        summary_count_mapping_issue(
            summary,
            "caseCountByNativeOptimizationEvidenceStatus",
            evidence_counts,
            label,
        ),
        summary_count_mapping_issue(
            summary,
            "caseCountByNativeArtifactDescriptorOptimizationStatus",
            descriptor_status_counts,
            label,
        ),
        summary_label_list_issue(
            summary,
            "nativeArtifactDescriptorOptimizationStatuses",
            sorted(descriptor_status_counts),
            label,
        ),
        summary_count_mapping_issue(
            summary,
            "caseCountByNativeArtifactDescriptorOptimizationEvidenceStatus",
            descriptor_evidence_counts,
            label,
        ),
    ):
        if issue is not None:
            issues.append(issue)

    if "nativeOptimizationEvidence" in summary:
        value = summary.get("nativeOptimizationEvidence")
        path = f"{label}.summary.nativeOptimizationEvidence"
        if not isinstance(value, dict):
            issues.append(f"{path} must be an object")
        else:
            for field in REQUIRED_NATIVE_OPTIMIZATION_EVIDENCE_FIELDS:
                if field not in value:
                    issues.append(f"{path}.{field} is required")

            expected = native_optimization_evidence_summary_from_counts(
                case_count=len(cases), evidence_counts=evidence_counts
            )
            if value != expected:
                issues.append(f"{path}={value!r} does not match cases ({expected!r})")

    if "nativeArtifactDescriptorOptimizationEvidence" not in summary:
        return issues

    descriptor_value = summary.get("nativeArtifactDescriptorOptimizationEvidence")
    descriptor_path = f"{label}.summary.nativeArtifactDescriptorOptimizationEvidence"
    if not isinstance(descriptor_value, dict):
        issues.append(f"{descriptor_path} must be an object")
        return issues

    for field in REQUIRED_NATIVE_ARTIFACT_DESCRIPTOR_OPTIMIZATION_EVIDENCE_FIELDS:
        if field not in descriptor_value:
            issues.append(f"{descriptor_path}.{field} is required")

    descriptor_expected = native_artifact_descriptor_evidence_summary_from_counts(
        case_count=len(cases), evidence_counts=descriptor_evidence_counts
    )
    if descriptor_value != descriptor_expected:
        issues.append(
            f"{descriptor_path}={descriptor_value!r} "
            f"does not match cases ({descriptor_expected!r})"
        )
    return issues


def config_string_list_issues(
    config: dict[str, Any], field: str, label: str
) -> tuple[list[str], list[str] | None]:
    value = config.get(field)
    if value is None:
        return [], None
    if not isinstance(value, list) or any(
        not isinstance(entry, str) or not entry for entry in value
    ):
        return [f"{label}.config.{field} must be a list of strings"], None

    duplicates = sorted({entry for entry in value if value.count(entry) > 1})
    issues = (
        [f"{label}.config.{field} has duplicate label(s): {', '.join(duplicates)}"]
        if duplicates
        else []
    )
    return issues, value


def case_fixture_labels(cases: list[dict[str, Any]]) -> set[str]:
    labels: set[str] = set()
    for case in cases:
        label = case_string_label(case, "fixtureName")
        if label is None:
            key = case_string_label(case, "case")
            label = case_key_fixture_label(key) if key is not None else None
        if label is not None:
            labels.add(label)
    return labels


def config_coverage_issues(
    report: dict[str, Any],
    cases: dict[str, ReportCase],
    raw_cases: list[dict[str, Any]],
    label: str,
) -> list[str]:
    config = report.get("config")
    if config is None:
        return []
    if not isinstance(config, dict):
        return [f"{label}.config must be an object when present"]

    issues: list[str] = []
    expected_labels = {
        "commandProfiles": {
            case.command_profile for case in cases.values() if case.command_profile
        },
        "fixtures": case_fixture_labels(raw_cases),
        "profiles": {case.profile for case in cases.values() if case.profile},
        "targets": {case.target for case in cases.values() if case.target},
    }
    for field, expected in expected_labels.items():
        field_issues, declared = config_string_list_issues(config, field, label)
        issues.extend(field_issues)
        if declared is None:
            continue
        if set(declared) != expected:
            issues.append(
                f"{label}.config.{field}={declared!r} does not match cases "
                f"({sorted(expected)!r})"
            )
    return issues


def value_at_path(payload: dict[str, Any], path: tuple[str, ...]) -> Any:
    value: Any = payload
    for key in path:
        if not isinstance(value, dict) or key not in value:
            return None
        value = value[key]
    return value


def value_at_path_if_present(
    payload: dict[str, Any], path: tuple[str, ...]
) -> tuple[bool, Any]:
    value: Any = payload
    for key in path:
        if not isinstance(value, dict) or key not in value:
            return False, None
        value = value[key]
    return True, value


def dotted_path(path: tuple[str, ...]) -> str:
    return ".".join(path)


def normalized_json_value(value: Any) -> Any:
    return json.loads(json.dumps(value, sort_keys=True))


def string_value(value: Any) -> str | None:
    if isinstance(value, str) and value:
        return value
    return None


def first_string_at_paths(
    report: dict[str, Any], paths: Iterable[tuple[str, ...]]
) -> str | None:
    for path in paths:
        value = string_value(value_at_path(report, path))
        if value is not None:
            return value
    return None


def first_present_at_paths(
    report: dict[str, Any], paths: Iterable[tuple[str, ...]]
) -> Any:
    for path in paths:
        value = value_at_path(report, path)
        if value is not None:
            return normalized_json_value(value)
    return None


def runtime_environment_metadata(
    report: dict[str, Any],
) -> tuple[dict[str, Any] | None, tuple[str, ...]]:
    for path in RUNTIME_ENVIRONMENT_PATHS:
        value = value_at_path(report, path)
        if value is None:
            continue
        if not isinstance(value, dict):
            return None, REQUIRED_RUNTIME_ENVIRONMENT_FIELDS
        missing_fields = tuple(
            field
            for field in REQUIRED_RUNTIME_ENVIRONMENT_FIELDS
            if string_value(value.get(field)) is None
        )
        if missing_fields:
            return None, missing_fields
        return normalized_json_value(value), ()
    return None, REQUIRED_RUNTIME_ENVIRONMENT_FIELDS


def string_values_at_paths(
    report: dict[str, Any], paths: Iterable[tuple[str, ...]]
) -> list[tuple[str, str]]:
    values: list[tuple[str, str]] = []
    for path in paths:
        value = string_value(value_at_path(report, path))
        if value is not None:
            values.append((dotted_path(path), value))
    return values


def bool_value(value: Any) -> bool | None:
    return value if isinstance(value, bool) else None


def add_toolchain(
    toolchains: dict[str, dict[str, Any]],
    label: str | None,
    *,
    toolchain_class: str | None = None,
    version: str | None = None,
    status: str | None = None,
    available: bool | None = None,
    optional: bool | None = None,
    required: bool | None = None,
    role: str | None = None,
    classification: str | None = None,
) -> None:
    if label is None:
        return
    entry = toolchains.setdefault(label, {})
    if toolchain_class is not None:
        entry["class"] = toolchain_class
    if version is not None:
        entry["version"] = version
    if status is not None:
        entry["status"] = status
    if available is not None:
        entry["available"] = available
    if optional is not None:
        entry["optional"] = optional
    if required is not None:
        entry["required"] = required
    if role is not None:
        entry["role"] = role
    if classification is not None:
        entry["classification"] = classification


def add_toolchain_from_mapping(
    toolchains: dict[str, dict[str, Any]], label: str, value: dict[str, Any]
) -> None:
    add_toolchain(
        toolchains,
        label,
        toolchain_class=string_value(value.get("class"))
        or string_value(value.get("toolchainClass")),
        version=string_value(value.get("version")),
        status=string_value(value.get("status")),
        available=bool_value(value.get("available")),
        optional=bool_value(value.get("optional")),
        required=bool_value(value.get("required")),
        role=string_value(value.get("role")),
        classification=string_value(value.get("classification"))
        or string_value(value.get("requirement")),
    )


def report_toolchain_metadata(report: dict[str, Any]) -> dict[str, dict[str, Any]]:
    toolchains: dict[str, dict[str, Any]] = {}

    policy = report.get("baselinePolicy")
    if isinstance(policy, dict):
        add_toolchain(
            toolchains,
            string_value(policy.get("toolchainLabel")),
            toolchain_class=string_value(policy.get("toolchainClass")),
            version=string_value(policy.get("toolchainVersion")),
        )

    metadata = report.get("metadata")
    if isinstance(metadata, dict):
        add_toolchain(
            toolchains,
            string_value(metadata.get("toolchainLabel")),
            toolchain_class=string_value(metadata.get("toolchainClass")),
            version=string_value(metadata.get("toolchainVersion")),
        )

    toolchain = report.get("toolchain")
    if isinstance(toolchain, dict):
        add_toolchain(
            toolchains,
            string_value(toolchain.get("label")) or string_value(toolchain.get("name")),
            toolchain_class=string_value(toolchain.get("class"))
            or string_value(toolchain.get("toolchainClass")),
            version=string_value(toolchain.get("version")),
            status=string_value(toolchain.get("status")),
        )

    explicit_label = first_string_at_paths(
        report, (("toolchainLabel",), ("config", "toolchainLabel"))
    )
    explicit_class = first_string_at_paths(
        report, (("toolchainClass",), ("config", "toolchainClass"))
    )
    explicit_version = first_string_at_paths(
        report, (("toolchainVersion",), ("config", "toolchainVersion"))
    )
    add_toolchain(
        toolchains,
        explicit_label,
        toolchain_class=explicit_class,
        version=explicit_version,
    )

    listed_toolchains = report.get("toolchains")
    if isinstance(listed_toolchains, dict):
        for label, value in listed_toolchains.items():
            if not isinstance(label, str) or not label:
                continue
            if isinstance(value, dict):
                add_toolchain_from_mapping(toolchains, label, value)
            elif isinstance(value, str) and value:
                add_toolchain(toolchains, label, version=value)
    elif isinstance(listed_toolchains, list):
        for value in listed_toolchains:
            if not isinstance(value, dict):
                continue
            label = string_value(value.get("label")) or string_value(value.get("name"))
            if label is not None:
                add_toolchain_from_mapping(toolchains, label, value)

    tool_availability = report.get("toolAvailability")
    if isinstance(tool_availability, dict):
        for label, value in tool_availability.items():
            if not isinstance(label, str) or not label:
                continue
            if isinstance(value, dict):
                add_toolchain_from_mapping(toolchains, label, value)
            else:
                add_toolchain(toolchains, label)

    return dict(sorted(toolchains.items()))


def toolchain_role(entry: dict[str, Any]) -> str:
    role = string_value(entry.get("role")) or string_value(entry.get("classification"))
    if role is not None:
        normalized = role.lower()
        if normalized in ("optional", "advisory", "best-effort"):
            return "optional"
        if normalized in ("required", "mandatory"):
            return "required"
        return normalized
    if entry.get("optional") is True or entry.get("required") is False:
        return "optional"
    if entry.get("required") is True or entry.get("optional") is False:
        return "required"
    return "unspecified"


def toolchain_availability(entry: dict[str, Any]) -> str:
    available = entry.get("available")
    if available is True:
        return "available"
    if available is False:
        return "unavailable"
    status = string_value(entry.get("status"))
    if status is not None:
        return status
    return "unspecified"


def toolchain_classifications(
    toolchains: dict[str, dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    return {
        label: {
            "availability": toolchain_availability(entry),
            "role": toolchain_role(entry),
            "status": entry.get("status"),
            "available": entry.get("available"),
        }
        for label, entry in sorted(toolchains.items())
    }


def toolchain_classes(toolchains: dict[str, dict[str, Any]]) -> dict[str, str]:
    return {
        label: string_value(entry.get("class")) or "unspecified"
        for label, entry in sorted(toolchains.items())
    }


def toolchain_role_for_label(
    classifications: dict[str, dict[str, Any]], label: str
) -> str:
    classification = classifications.get(label)
    if not isinstance(classification, dict):
        return "unspecified"
    role = classification.get("role")
    return role if isinstance(role, str) and role else "unspecified"


def toolchain_is_optional(
    classifications: dict[str, dict[str, Any]], label: str
) -> bool:
    return toolchain_role_for_label(classifications, label) == "optional"


def skipped_tool_accounting_report(
    cases: dict[str, ReportCase],
    unavailable_toolchain_labels: list[str],
    classifications: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    cases_by_tool = skipped_tool_cases_by_tool(cases)
    skipped_case_reasons = skipped_cases(cases)
    optional_skipped_tools = sorted(
        tool for tool in cases_by_tool if toolchain_is_optional(classifications, tool)
    )
    required_skipped_tools = sorted(
        tool
        for tool in cases_by_tool
        if not toolchain_is_optional(classifications, tool)
    )
    skipped_case_keys = sorted({key for keys in cases_by_tool.values() for key in keys})
    skipped_cases_without_tools = sorted(
        set(skipped_case_reasons) - set(skipped_case_keys)
    )
    return {
        "skippedCaseCount": len(skipped_case_reasons),
        "skippedCases": sorted(skipped_case_reasons),
        "skippedCasesWithoutUnavailableToolCount": len(skipped_cases_without_tools),
        "skippedCasesWithoutUnavailableTools": skipped_cases_without_tools,
        "skippedToolCaseCountByTool": {
            tool: len(keys) for tool, keys in cases_by_tool.items()
        },
        "skippedToolCasesByTool": cases_by_tool,
        "optionalSkippedToolLabels": optional_skipped_tools,
        "optionalSkippedCaseCount": len(
            {
                key
                for tool in optional_skipped_tools
                for key in cases_by_tool.get(tool, [])
            }
        ),
        "requiredOrUnclassifiedSkippedToolLabels": required_skipped_tools,
        "requiredOrUnclassifiedSkippedCaseCount": len(
            {
                key
                for tool in required_skipped_tools
                for key in cases_by_tool.get(tool, [])
            }
        ),
        "skippedCasesWithUnavailableTools": skipped_case_keys,
        "unavailableToolchainLabelCount": len(unavailable_toolchain_labels),
        "unavailableToolchainLabels": unavailable_toolchain_labels,
    }


def report_policy_metadata(
    report: dict[str, Any], cases: dict[str, ReportCase]
) -> ReportPolicyMetadata:
    fields: dict[str, Any] = {}
    for name, paths in POLICY_FIELD_PATHS.items():
        value = first_string_at_paths(report, paths)
        if value is not None:
            fields[name] = value

    comparison_window = first_present_at_paths(report, COMPARISON_WINDOW_PATHS)
    if comparison_window is not None:
        fields["comparisonWindow"] = comparison_window
    runtime_environment, runtime_environment_missing_fields = (
        runtime_environment_metadata(report)
    )
    if runtime_environment is not None:
        fields["runtimeEnvironment"] = runtime_environment

    unavailable_toolchain_labels = sorted(
        report_unavailable_toolchain_labels(report, cases)
    )
    toolchains = report_toolchain_metadata(report)
    classifications = toolchain_classifications(toolchains)
    skipped_tool_accounting = skipped_tool_accounting_report(
        cases,
        unavailable_toolchain_labels,
        classifications,
    )
    return ReportPolicyMetadata(
        fields=dict(sorted(fields.items())),
        runtime_environment_missing_fields=runtime_environment_missing_fields,
        toolchains=toolchains,
        skipped_tool_accounting=skipped_tool_accounting,
    )


def policy_metadata_shape_issues(report: dict[str, Any], label: str) -> list[str]:
    issues: list[str] = []
    for paths in (*POLICY_FIELD_PATHS.values(), *TOOLCHAIN_POLICY_FIELD_PATHS.values()):
        for path in paths:
            present, value = value_at_path_if_present(report, path)
            if not present:
                continue
            if string_value(value) is None:
                issues.append(f"{label}.{dotted_path(path)} must be a non-empty string")

    comparison_windows: list[tuple[str, dict[str, Any]]] = []
    for path in COMPARISON_WINDOW_PATHS:
        present, value = value_at_path_if_present(report, path)
        if not present:
            continue
        path_label = f"{label}.{dotted_path(path)}"
        normalized, window_issues = valid_measurement_window(value, path_label)
        issues.extend(window_issues)
        if normalized is not None:
            comparison_windows.append((dotted_path(path), normalized))

    unique_windows = {
        json.dumps(window, sort_keys=True) for _, window in comparison_windows
    }
    if len(unique_windows) > 1:
        rendered = ", ".join(
            f"{path}={window!r}" for path, window in comparison_windows
        )
        issues.append(
            f"{label}.comparisonWindow policy metadata has conflicting values: "
            f"{rendered}"
        )

    issues.extend(toolchain_metadata_shape_issues(report, label))
    return issues


def toolchain_entry_shape_issues(
    entry: Any,
    path: str,
    *,
    map_label: str | None,
    allow_version_string: bool,
) -> list[str]:
    if isinstance(entry, str):
        if allow_version_string and entry:
            return []
        if allow_version_string:
            return [f"{path} must be an object or non-empty version string"]
        return [f"{path} must be an object"]
    if not isinstance(entry, dict):
        return [f"{path} must be an object"]

    issues: list[str] = []
    for field in TOOLCHAIN_ENTRY_STRING_FIELDS:
        if field not in entry or entry[field] is None:
            continue
        if string_value(entry[field]) is None:
            issues.append(f"{path}.{field} must be a non-empty string")

    for field in TOOLCHAIN_ENTRY_BOOL_FIELDS:
        if field not in entry or entry[field] is None:
            continue
        if not isinstance(entry[field], bool):
            issues.append(f"{path}.{field} must be a boolean or null")

    if map_label is not None:
        for field in ("label", "name"):
            mirror = string_value(entry.get(field))
            if mirror is not None and mirror != map_label:
                issues.append(
                    f"{path}.{field}={mirror!r} does not match map key {map_label!r}"
                )

    optional = entry.get("optional")
    required = entry.get("required")
    if isinstance(optional, bool) and isinstance(required, bool):
        if optional == required:
            issues.append(
                f"{path}.optional and {path}.required must be opposite booleans "
                "when both are present"
            )
    return issues


def toolchain_mapping_shape_issues(
    value: dict[Any, Any],
    path: str,
    *,
    allow_version_strings: bool,
) -> list[str]:
    issues: list[str] = []
    for raw_label in sorted(value, key=lambda item: str(item)):
        entry = value[raw_label]
        if not isinstance(raw_label, str) or not raw_label:
            issues.append(f"{path} must use non-empty string labels")
            continue
        issues.extend(
            toolchain_entry_shape_issues(
                entry,
                f"{path}.{raw_label}",
                map_label=raw_label,
                allow_version_string=allow_version_strings,
            )
        )
    return issues


def toolchain_list_shape_issues(value: list[Any], path: str) -> list[str]:
    issues: list[str] = []
    for index, entry in enumerate(value):
        entry_path = f"{path}[{index}]"
        if not isinstance(entry, dict):
            issues.append(f"{entry_path} must be an object")
            continue
        label = string_value(entry.get("label")) or string_value(entry.get("name"))
        if label is None:
            issues.append(f"{entry_path}.label or {entry_path}.name is required")
        issues.extend(
            toolchain_entry_shape_issues(
                entry,
                entry_path,
                map_label=None,
                allow_version_string=False,
            )
        )
    return issues


def toolchain_metadata_shape_issues(report: dict[str, Any], label: str) -> list[str]:
    issues: list[str] = []

    listed_toolchains = report.get("toolchains")
    if listed_toolchains is not None:
        path = f"{label}.toolchains"
        if isinstance(listed_toolchains, dict):
            issues.extend(
                toolchain_mapping_shape_issues(
                    listed_toolchains,
                    path,
                    allow_version_strings=True,
                )
            )
        elif isinstance(listed_toolchains, list):
            issues.extend(toolchain_list_shape_issues(listed_toolchains, path))
        else:
            issues.append(f"{path} must be an object or array when present")

    tool_availability = report.get("toolAvailability")
    if isinstance(tool_availability, dict):
        issues.extend(
            toolchain_mapping_shape_issues(
                tool_availability,
                f"{label}.toolAvailability",
                allow_version_strings=False,
            )
        )

    issues.extend(toolchain_metadata_conflict_issues(report, label))
    return issues


def add_toolchain_metadata_source_values(
    values: dict[tuple[str, str], list[tuple[str, Any]]],
    toolchain_label: str | None,
    path: str,
    entry: dict[str, Any],
) -> None:
    if toolchain_label is None:
        return

    class_values = [
        ("class", string_value(entry.get("class"))),
        ("toolchainClass", string_value(entry.get("toolchainClass"))),
    ]
    for field, value in class_values:
        if value is not None:
            values.setdefault((toolchain_label, "class"), []).append(
                (f"{path}.{field}", value)
            )

    for field in (
        "version",
        "toolchainVersion",
        "status",
        "role",
        "classification",
        "requirement",
    ):
        value = string_value(entry.get(field))
        if value is None:
            continue
        canonical_field = {
            "requirement": "classification",
            "toolchainVersion": "version",
        }.get(field, field)
        values.setdefault((toolchain_label, canonical_field), []).append(
            (f"{path}.{field}", value)
        )

    for field in TOOLCHAIN_CANONICAL_BOOL_FIELDS:
        value = entry.get(field)
        if isinstance(value, bool):
            values.setdefault((toolchain_label, field), []).append(
                (f"{path}.{field}", value)
            )


def toolchain_metadata_conflict_issues(report: dict[str, Any], label: str) -> list[str]:
    values: dict[tuple[str, str], list[tuple[str, Any]]] = {}

    policy = report.get("baselinePolicy")
    if isinstance(policy, dict):
        toolchain_label = string_value(policy.get("toolchainLabel"))
        add_toolchain_metadata_source_values(
            values,
            toolchain_label,
            f"{label}.baselinePolicy",
            {
                "toolchainClass": policy.get("toolchainClass"),
                "toolchainVersion": policy.get("toolchainVersion"),
            },
        )

    metadata = report.get("metadata")
    if isinstance(metadata, dict):
        toolchain_label = string_value(metadata.get("toolchainLabel"))
        add_toolchain_metadata_source_values(
            values,
            toolchain_label,
            f"{label}.metadata",
            {
                "toolchainClass": metadata.get("toolchainClass"),
                "toolchainVersion": metadata.get("toolchainVersion"),
            },
        )

    toolchain = report.get("toolchain")
    if isinstance(toolchain, dict):
        toolchain_label = string_value(toolchain.get("label")) or string_value(
            toolchain.get("name")
        )
        add_toolchain_metadata_source_values(
            values, toolchain_label, f"{label}.toolchain", toolchain
        )

    config = report.get("config")
    for source_path, source in (
        (label, report),
        (f"{label}.config", config if isinstance(config, dict) else None),
    ):
        if not isinstance(source, dict):
            continue
        toolchain_label = string_value(source.get("toolchainLabel"))
        add_toolchain_metadata_source_values(
            values,
            toolchain_label,
            source_path,
            {
                "toolchainClass": source.get("toolchainClass"),
                "toolchainVersion": source.get("toolchainVersion"),
            },
        )

    listed_toolchains = report.get("toolchains")
    if isinstance(listed_toolchains, dict):
        for raw_label in sorted(listed_toolchains, key=lambda item: str(item)):
            if not isinstance(raw_label, str) or not raw_label:
                continue
            entry = listed_toolchains[raw_label]
            path = f"{label}.toolchains.{raw_label}"
            if isinstance(entry, dict):
                add_toolchain_metadata_source_values(values, raw_label, path, entry)
            elif isinstance(entry, str) and entry:
                values.setdefault((raw_label, "version"), []).append((path, entry))
    elif isinstance(listed_toolchains, list):
        for index, entry in enumerate(listed_toolchains):
            if not isinstance(entry, dict):
                continue
            toolchain_label = string_value(entry.get("label")) or string_value(
                entry.get("name")
            )
            add_toolchain_metadata_source_values(
                values,
                toolchain_label,
                f"{label}.toolchains[{index}]",
                entry,
            )

    tool_availability = report.get("toolAvailability")
    if isinstance(tool_availability, dict):
        for raw_label in sorted(tool_availability, key=lambda item: str(item)):
            if not isinstance(raw_label, str) or not raw_label:
                continue
            entry = tool_availability[raw_label]
            if isinstance(entry, dict):
                add_toolchain_metadata_source_values(
                    values,
                    raw_label,
                    f"{label}.toolAvailability.{raw_label}",
                    entry,
                )

    issues: list[str] = []
    for (toolchain_label, field), field_values in sorted(values.items()):
        unique_values = {json.dumps(value, sort_keys=True) for _, value in field_values}
        if len(unique_values) <= 1:
            continue
        rendered_values = ", ".join(f"{path}={value!r}" for path, value in field_values)
        issues.append(
            f"{label}.toolchain metadata for {toolchain_label!r} has conflicting "
            f"{field} values: {rendered_values}"
        )
    return issues


def report_validation_issues(
    report: dict[str, Any], cases: dict[str, ReportCase], label: str
) -> list[str]:
    issues: list[str] = []
    if report.get("schemaVersion") != SCHEMA_VERSION:
        issues.append(
            f"{label}.schemaVersion must be {SCHEMA_VERSION} "
            f"(got {report.get('schemaVersion')!r})"
        )
    if report.get("tool") != "benchmark_performance_corpus":
        issues.append(
            f"{label}.tool must be 'benchmark_performance_corpus' "
            f"(got {report.get('tool')!r})"
        )
    if not isinstance(report.get("corpusVersion"), str) or not report.get(
        "corpusVersion"
    ):
        issues.append(f"{label}.corpusVersion must be a non-empty string")

    issues.extend(policy_metadata_shape_issues(report, label))

    for field, paths in {
        **POLICY_FIELD_PATHS,
        **TOOLCHAIN_POLICY_FIELD_PATHS,
    }.items():
        values = string_values_at_paths(report, paths)
        unique_values = sorted({value for _, value in values})
        if len(unique_values) <= 1:
            continue
        rendered_values = ", ".join(f"{path}={value!r}" for path, value in values)
        issues.append(
            f"{label}.{field} policy metadata has conflicting values: {rendered_values}"
        )

    raw_cases = raw_case_objects(report)
    issues.extend(config_coverage_issues(report, cases, raw_cases, label))
    for index, case in enumerate(raw_cases):
        path = f"{label}.cases[{index}]"
        profile = case.get("profile")
        target = case.get("target")
        category = case.get("fixtureCategory")
        if not isinstance(category, str) or not category:
            issues.append(f"{path}.fixtureCategory must be a non-empty string")
        if not isinstance(profile, str) or not profile:
            issues.append(f"{path}.profile must be a non-empty string")
        if not isinstance(target, str) or not target:
            issues.append(f"{path}.target must be a non-empty string")

        skipped = case_skipped(case)
        skip_reason = case.get("skipReason")
        if skipped:
            if not isinstance(skip_reason, str) or not skip_reason:
                issues.append(
                    f"{path}.skipReason must be a non-empty string for skipped cases"
                )
            if not case_unavailable_tools(case):
                issues.append(
                    f"{path}.unavailableTools must name at least one unavailable "
                    "tool for skipped cases"
                )
            if "timing" in case and case.get("timing") is not None:
                issues.append(f"{path}.timing must be null for skipped cases")
            status = case.get("status")
            if status is not None and status != "skipped":
                issues.append(f"{path}.status must be 'skipped' for skipped cases")
            if case.get("success") is True:
                issues.append(f"{path}.success must not be true for skipped cases")
        elif skip_reason not in (None, ""):
            issues.append(f"{path}.skipReason must be null unless the case is skipped")

        command_profile = case.get("commandProfile")
        if not isinstance(command_profile, dict):
            issues.append(f"{path}.commandProfile must be an object")
        else:
            command_profile_name = command_profile.get("name")
            if not isinstance(command_profile_name, str) or not command_profile_name:
                issues.append(f"{path}.commandProfile.name must be a non-empty string")
            elif (
                isinstance(profile, str) and profile and command_profile_name != profile
            ):
                issues.append(
                    f"{path}.commandProfile.name={command_profile_name!r} "
                    f"does not match profile {profile!r}"
                )
            for command_field, case_field in (
                ("compilerConfig", "optLevel"),
                ("buildType", "profileBuildType"),
                ("packageMode", "packageMode"),
            ):
                command_value = command_profile.get(command_field)
                case_value = case.get(case_field)
                if command_value is None:
                    continue
                if not isinstance(command_value, str) or not command_value:
                    issues.append(
                        f"{path}.commandProfile.{command_field} must be a "
                        "non-empty string"
                    )
                    continue
                if not isinstance(case_value, str) or not case_value:
                    issues.append(f"{path}.{case_field} must be a non-empty string")
                    continue
                if command_value != case_value:
                    issues.append(
                        f"{path}.{case_field}={case_value!r} does not match "
                        f"commandProfile.{command_field} {command_value!r}"
                    )
            command_native_validation = command_profile.get("nativeValidationRequested")
            case_native_validation = case.get("nativeValidationRequested")
            if command_native_validation is not None:
                if not isinstance(command_native_validation, bool):
                    issues.append(
                        f"{path}.commandProfile.nativeValidationRequested must be "
                        "a boolean"
                    )
                elif not isinstance(case_native_validation, bool):
                    issues.append(f"{path}.nativeValidationRequested must be a boolean")
                elif command_native_validation != case_native_validation:
                    issues.append(
                        f"{path}.nativeValidationRequested="
                        f"{case_native_validation!r} does not match "
                        "commandProfile.nativeValidationRequested "
                        f"{command_native_validation!r}"
                    )

    summary = report.get("summary")
    if not isinstance(summary, dict):
        issues.append(f"{label}.summary must be an object")
        summary = None

    if isinstance(summary, dict):
        run_accounting = timing_run_accounting(raw_cases)
        package_mode_counts = count_report_case_field(cases, "package_mode")
        expected_counts = {
            "caseCount": len(cases),
            "skippedCount": len(skipped_cases(cases)),
            "timedCaseCount": sum(
                1 for case in cases.values() if case.elapsed_ns is not None
            ),
            "unavailableToolCount": len(
                report_unavailable_toolchain_labels(report, cases)
            ),
            **artifact_accounting(raw_cases),
            **execution_accounting(raw_cases),
            "measuredRunCount": run_accounting["measuredRunCount"],
            "packageModeCount": len(package_mode_counts),
            **verification_accounting(raw_cases),
            "warmupRunCount": run_accounting["warmupRunCount"],
        }
        for field, expected in expected_counts.items():
            value = summary.get(field)
            if value is None:
                continue
            if isinstance(value, bool) or not isinstance(value, int):
                issues.append(f"{label}.summary.{field} must be an integer")
                continue
            if value != expected:
                issues.append(
                    f"{label}.summary.{field}={value} does not match cases ({expected})"
                )
        skipped_tool_counts = summary.get("skippedToolCaseCountByTool")
        if skipped_tool_counts is not None:
            expected = skipped_tool_case_count_by_tool(raw_cases)
            if not isinstance(skipped_tool_counts, dict):
                issues.append(
                    f"{label}.summary.skippedToolCaseCountByTool must be an object"
                )
            elif skipped_tool_counts != expected:
                issues.append(
                    f"{label}.summary.skippedToolCaseCountByTool="
                    f"{skipped_tool_counts!r} does not match cases ({expected!r})"
                )
        skipped_tool_cases = summary.get("skippedToolCasesByTool")
        if skipped_tool_cases is not None:
            expected = skipped_tool_cases_by_tool_from_raw(raw_cases)
            valid_shape = isinstance(skipped_tool_cases, dict) and all(
                isinstance(tool, str)
                and tool
                and isinstance(case_keys, list)
                and all(
                    isinstance(case_key, str) and case_key for case_key in case_keys
                )
                for tool, case_keys in skipped_tool_cases.items()
            )
            if not valid_shape:
                issues.append(
                    f"{label}.summary.skippedToolCasesByTool must map tools to "
                    "case-key lists"
                )
            elif skipped_tool_cases != expected:
                issues.append(
                    f"{label}.summary.skippedToolCasesByTool="
                    f"{skipped_tool_cases!r} does not match cases ({expected!r})"
                )
        skipped_reason_counts = summary.get("skippedCaseCountByReason")
        if skipped_reason_counts is not None:
            expected = skipped_case_count_by_reason(raw_cases)
            valid_shape = isinstance(skipped_reason_counts, dict) and all(
                isinstance(reason, str)
                and reason
                and not isinstance(count, bool)
                and isinstance(count, int)
                and count >= 0
                for reason, count in skipped_reason_counts.items()
            )
            if not valid_shape:
                issues.append(
                    f"{label}.summary.skippedCaseCountByReason must map reasons "
                    "to integer counts"
                )
            elif skipped_reason_counts != expected:
                issues.append(
                    f"{label}.summary.skippedCaseCountByReason="
                    f"{skipped_reason_counts!r} does not match cases ({expected!r})"
                )
        skipped_cases_with_tools = summary.get("skippedCasesWithUnavailableTools")
        if skipped_cases_with_tools is not None:
            expected = skipped_cases_with_unavailable_tools(raw_cases)
            if not isinstance(skipped_cases_with_tools, list) or any(
                not isinstance(case_key, str) or not case_key
                for case_key in skipped_cases_with_tools
            ):
                issues.append(
                    f"{label}.summary.skippedCasesWithUnavailableTools must be a "
                    "list of case keys"
                )
            elif skipped_cases_with_tools != expected:
                issues.append(
                    f"{label}.summary.skippedCasesWithUnavailableTools="
                    f"{skipped_cases_with_tools!r} does not match cases "
                    f"({expected!r})"
                )
        if skipped_cases(cases):
            for field in REQUIRED_SKIPPED_SUMMARY_ACCOUNTING_FIELDS:
                if field not in summary:
                    issues.append(
                        f"{label}.summary.{field} is required when cases are skipped"
                    )
        issues.extend(manifest_artifact_kind_summary_issues(summary, raw_cases, label))
        issues.extend(native_optimization_summary_issues(summary, cases, label))
        category_counts = count_report_case_field(cases, "category")
        category_target_counts = case_count_by_category_target(cases)
        command_profile_counts = count_report_case_field(cases, "command_profile")
        opt_level_counts = count_report_case_field(cases, "opt_level")
        profile_counts = count_report_case_field(cases, "profile")
        target_counts = count_report_case_field(cases, "target")
        if ("packageModes" in summary) != ("caseCountByPackageMode" in summary):
            issues.append(
                f"{label}.summary.packageModes and "
                "caseCountByPackageMode must be emitted together"
            )
        for field in REQUIRED_SUMMARY_ACCOUNTING_FIELDS:
            if field not in summary:
                issues.append(f"{label}.summary.{field} is required")
        for issue in (
            summary_label_list_issue(
                summary, "caseCategories", sorted(category_counts), label
            ),
            summary_label_list_issue(
                summary, "commandProfiles", sorted(command_profile_counts), label
            ),
            summary_label_list_issue(
                summary, "optLevels", sorted(opt_level_counts), label
            ),
            summary_count_mapping_issue(
                summary, "caseCountByCategory", category_counts, label
            ),
            summary_nested_count_mapping_issue(
                summary,
                "caseCountByCategoryTarget",
                category_target_counts,
                label,
            ),
            summary_count_mapping_issue(
                summary,
                "caseCountByCommandProfile",
                command_profile_counts,
                label,
            ),
            summary_count_mapping_issue(
                summary,
                "caseCountByOptLevel",
                opt_level_counts,
                label,
            ),
            summary_label_list_issue(
                summary, "packageModes", sorted(package_mode_counts), label
            )
            if "packageModes" in summary
            else None,
            summary_count_mapping_issue(
                summary,
                "caseCountByPackageMode",
                package_mode_counts,
                label,
            )
            if "caseCountByPackageMode" in summary
            else None,
            summary_count_mapping_issue(
                summary, "caseCountByProfile", profile_counts, label
            ),
            summary_count_mapping_issue(
                summary, "caseCountByTarget", target_counts, label
            ),
        ):
            if issue is not None:
                issues.append(issue)

    issues.extend(timing_summary_validation_issues(raw_cases, label))
    issues.extend(measurement_window_validation_issues(report, raw_cases, label))

    skipped_tool_counts = skipped_tool_case_count_by_tool(raw_cases)
    tool_availability = report.get("toolAvailability")
    if tool_availability is None and skipped_tool_counts:
        issues.append(f"{label}.toolAvailability must describe skipped tools")
    elif tool_availability is not None and not isinstance(tool_availability, dict):
        issues.append(f"{label}.toolAvailability must be an object when present")
    elif isinstance(tool_availability, dict):
        for tool in sorted(skipped_tool_counts):
            value = tool_availability.get(tool)
            if not isinstance(value, dict):
                issues.append(
                    f"{label}.toolAvailability.{tool} must describe skipped tool"
                )
                continue
            if (
                value.get("available") is not False
                and value.get("status") != "unavailable"
            ):
                issues.append(
                    f"{label}.toolAvailability.{tool} must mark skipped tool unavailable"
                )
    return issues


def compare_mapping_values(
    baseline: dict[str, Any], candidate: dict[str, Any], *, prefix: str = ""
) -> list[dict[str, Any]]:
    mismatches: list[dict[str, Any]] = []
    for key in sorted(set(baseline) & set(candidate)):
        baseline_value = baseline[key]
        candidate_value = candidate[key]
        if baseline_value == candidate_value:
            continue
        name = f"{prefix}.{key}" if prefix else key
        mismatches.append(
            {
                "field": name,
                "baseline": baseline_value,
                "candidate": candidate_value,
            }
        )
    return mismatches


def compare_policy_metadata(
    baseline: ReportPolicyMetadata, candidate: ReportPolicyMetadata
) -> dict[str, Any]:
    missing_fields = sorted(set(baseline.fields) - set(candidate.fields))
    added_fields = sorted(set(candidate.fields) - set(baseline.fields))
    mismatches = compare_mapping_values(baseline.fields, candidate.fields)

    baseline_toolchains = set(baseline.toolchains)
    candidate_toolchains = set(candidate.toolchains)
    missing_toolchains = sorted(baseline_toolchains - candidate_toolchains)
    added_toolchains = sorted(candidate_toolchains - baseline_toolchains)

    for label in sorted(baseline_toolchains & candidate_toolchains):
        mismatches.extend(
            compare_mapping_values(
                baseline.toolchains[label],
                candidate.toolchains[label],
                prefix=f"toolchains.{label}",
            )
        )

    accounting_mismatches = compare_mapping_values(
        baseline.skipped_tool_accounting,
        candidate.skipped_tool_accounting,
        prefix="skippedToolAccounting",
    )
    mismatches.extend(accounting_mismatches)

    mismatch_count = (
        len(missing_fields)
        + len(added_fields)
        + len(missing_toolchains)
        + len(added_toolchains)
        + len(mismatches)
    )
    return {
        "advisory": True,
        "compatible": mismatch_count == 0,
        "mismatchCount": mismatch_count,
        "missingCandidateFields": missing_fields,
        "addedCandidateFields": added_fields,
        "missingCandidateToolchains": missing_toolchains,
        "addedCandidateToolchains": added_toolchains,
        "mismatches": mismatches,
    }


def advisory_warning_summary(
    baseline: ReportPolicyMetadata,
    candidate: ReportPolicyMetadata,
    compatibility: dict[str, Any],
) -> dict[str, Any]:
    baseline_context = policy_context_report(baseline)
    candidate_context = policy_context_report(candidate)
    mismatched_fields = [
        mismatch["field"]
        for mismatch in compatibility["mismatches"]
        if isinstance(mismatch.get("field"), str)
    ]
    skipped_tool_mismatches = [
        field
        for field in mismatched_fields
        if field == "skippedToolAccounting"
        or field.startswith("skippedToolAccounting.")
    ]
    toolchain_metadata_mismatches = [
        field for field in mismatched_fields if field.startswith("toolchains.")
    ]
    warning_types: list[str] = []
    if baseline_context["missingFields"]:
        warning_types.append("baseline-missing-context")
    if candidate_context["missingFields"]:
        warning_types.append("candidate-missing-context")
    if compatibility["missingCandidateFields"] or compatibility["addedCandidateFields"]:
        warning_types.append("policy-field-set-drift")
    if (
        compatibility["missingCandidateToolchains"]
        or compatibility["addedCandidateToolchains"]
        or toolchain_metadata_mismatches
    ):
        warning_types.append("toolchain-metadata-drift")
    non_toolchain_policy_mismatches = [
        field
        for field in mismatched_fields
        if not field.startswith("toolchains.")
        and not field.startswith("skippedToolAccounting.")
        and field != "skippedToolAccounting"
    ]
    if non_toolchain_policy_mismatches:
        warning_types.append("policy-value-drift")
    if skipped_tool_mismatches:
        warning_types.append("skipped-tool-accounting-drift")

    return {
        "advisory": True,
        "baselineMissingFieldCount": len(baseline_context["missingFields"]),
        "baselineMissingFields": baseline_context["missingFields"],
        "candidateMissingFieldCount": len(candidate_context["missingFields"]),
        "candidateMissingFields": candidate_context["missingFields"],
        "metadataCompatible": (
            not baseline_context["missingFields"]
            and not candidate_context["missingFields"]
            and compatibility["compatible"]
        ),
        "metadataDriftCount": compatibility["mismatchCount"],
        "mismatchedFieldCount": len(mismatched_fields),
        "mismatchedFields": mismatched_fields,
        "missingCandidateFieldCount": len(compatibility["missingCandidateFields"]),
        "missingCandidateFields": compatibility["missingCandidateFields"],
        "addedCandidateFieldCount": len(compatibility["addedCandidateFields"]),
        "addedCandidateFields": compatibility["addedCandidateFields"],
        "missingCandidateToolchainCount": len(
            compatibility["missingCandidateToolchains"]
        ),
        "missingCandidateToolchains": compatibility["missingCandidateToolchains"],
        "addedCandidateToolchainCount": len(compatibility["addedCandidateToolchains"]),
        "addedCandidateToolchains": compatibility["addedCandidateToolchains"],
        "skippedToolAccountingDriftCount": len(skipped_tool_mismatches),
        "skippedToolAccountingDriftFields": skipped_tool_mismatches,
        "toolchainMetadataDriftFields": toolchain_metadata_mismatches,
        "warningCount": len(warning_types),
        "warningTypes": warning_types,
        "mode": "report-only",
        "failureMode": "report-only",
        "policy": (
            "Advisory warning summaries classify metadata and skipped-tool drift "
            "for report triage only; they never change comparator exit status."
        ),
    }


def policy_context_report(metadata: ReportPolicyMetadata) -> dict[str, Any]:
    toolchain_labels = sorted(metadata.toolchains)
    missing_fields = [
        field
        for field in REQUIRED_ADVISORY_CONTEXT_FIELDS
        if (field == "toolchains" and not metadata.toolchains)
        or (
            field == "runtimeEnvironment"
            and metadata.runtime_environment_missing_fields
        )
        or (field != "toolchains" and field not in metadata.fields)
    ]
    return {
        "fields": metadata.fields,
        "missingFields": missing_fields,
        "requiredFields": list(REQUIRED_ADVISORY_CONTEXT_FIELDS),
        "requiredRuntimeEnvironmentFields": list(REQUIRED_RUNTIME_ENVIRONMENT_FIELDS),
        "runtimeEnvironmentMissingFields": list(
            metadata.runtime_environment_missing_fields
        ),
        "skippedToolAccounting": metadata.skipped_tool_accounting,
        "toolchainClassifications": toolchain_classifications(metadata.toolchains),
        "toolchainClasses": toolchain_classes(metadata.toolchains),
        "toolchainLabelCount": len(metadata.toolchains),
        "toolchainLabels": toolchain_labels,
        "toolchains": metadata.toolchains,
    }


def string_list_value(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, str) and item]


def bool_value(value: Any) -> bool | None:
    return value if isinstance(value, bool) else None


def producer_threshold_enforcement_summary(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        return {"present": False}
    return {
        "present": True,
        "mode": string_value(value.get("mode")),
        "failureMode": string_value(value.get("failureMode")),
        "enforced": bool_value(value.get("enforced")),
        "hardFail": bool_value(value.get("hardFail")),
        "exitStatusAffected": bool_value(value.get("exitStatusAffected")),
        "releaseBlocker": bool_value(value.get("releaseBlocker")),
    }


def producer_advisory_threshold_policy_summary(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        return {
            "object": False,
            "shape": type(value).__name__ if value is not None else "null",
        }
    rules = value.get("rules")
    rule_count = nonnegative_int_value(value.get("ruleCount"))
    rules_length = len(rules) if isinstance(rules, list) else None
    enforcement = producer_threshold_enforcement_summary(value.get("enforcement"))
    return {
        "object": True,
        "schemaVersion": nonnegative_int_value(value.get("schemaVersion")),
        "tool": string_value(value.get("tool")),
        "kind": string_value(value.get("kind")),
        "mode": string_value(value.get("mode")),
        "name": string_value(value.get("name")),
        "status": string_value(value.get("status")),
        "thresholdSource": string_value(value.get("thresholdSource")),
        "ruleCount": rule_count if rule_count is not None else rules_length,
        "rulesLength": rules_length,
        "stableBaselineDataPresent": bool_value(value.get("stableBaselineDataPresent")),
        "declaresReportOnlyMode": value.get("mode") == "report-only",
        "enforcement": enforcement,
    }


def producer_threshold_baseline_readiness_summary(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        return {
            "object": False,
            "shape": type(value).__name__ if value is not None else "null",
            "readyForThresholdBaseline": None,
            "status": None,
        }
    requirements = value.get("thresholdBaselineRequirements")
    requirement_names: list[str] = []
    if isinstance(requirements, list):
        for requirement in requirements:
            if not isinstance(requirement, dict):
                continue
            name = string_value(requirement.get("name"))
            if name is not None:
                requirement_names.append(name)
    return {
        "object": True,
        "mode": string_value(value.get("mode")),
        "failureMode": string_value(value.get("failureMode")),
        "readyForThresholdBaseline": bool_value(value.get("readyForThresholdBaseline")),
        "stableBaselineDataPresent": bool_value(value.get("stableBaselineDataPresent")),
        "status": string_value(value.get("status")),
        "reasonCount": nonnegative_int_value(value.get("reasonCount")),
        "reasons": string_list_value(value.get("reasons")),
        "satisfiedThresholdBaselineRequirementCount": nonnegative_int_value(
            value.get("satisfiedThresholdBaselineRequirementCount")
        ),
        "thresholdBaselineRequirementCount": nonnegative_int_value(
            value.get("thresholdBaselineRequirementCount")
        ),
        "thresholdBaselineRequirementNames": requirement_names,
        "unsatisfiedThresholdBaselineRequirementCount": nonnegative_int_value(
            value.get("unsatisfiedThresholdBaselineRequirementCount")
        ),
        "unsatisfiedThresholdBaselineRequirements": string_list_value(
            value.get("unsatisfiedThresholdBaselineRequirements")
        ),
    }


def producer_claim_source_report(
    report: dict[str, Any],
    paths: dict[str, tuple[str, ...]],
    summary_fn: Any,
) -> dict[str, Any]:
    top_level_path = paths["topLevel"]
    metadata_path = paths["metadata"]
    top_level_present, top_level_value = value_at_path_if_present(
        report, top_level_path
    )
    metadata_present, metadata_value = value_at_path_if_present(report, metadata_path)
    top_level_normalized = (
        normalized_json_value(top_level_value) if top_level_present else None
    )
    metadata_normalized = (
        normalized_json_value(metadata_value) if metadata_present else None
    )
    mirrors_match = None
    if top_level_present and metadata_present:
        mirrors_match = top_level_normalized == metadata_normalized
        mirror_status = "matching" if mirrors_match else "mismatch"
    elif top_level_present:
        mirror_status = "top-level-only"
    elif metadata_present:
        mirror_status = "metadata-only"
    else:
        mirror_status = "absent"

    if top_level_present:
        effective_source = "top-level"
        effective_path = dotted_path(top_level_path)
        effective = top_level_normalized
    elif metadata_present:
        effective_source = "metadata"
        effective_path = dotted_path(metadata_path)
        effective = metadata_normalized
    else:
        effective_source = None
        effective_path = None
        effective = None

    return {
        "present": top_level_present or metadata_present,
        "topLevelPath": dotted_path(top_level_path),
        "topLevelPresent": top_level_present,
        "topLevel": top_level_normalized if top_level_present else None,
        "metadataPath": dotted_path(metadata_path),
        "metadataPresent": metadata_present,
        "metadata": metadata_normalized if metadata_present else None,
        "effectiveSource": effective_source,
        "effectivePath": effective_path,
        "mirrorStatus": mirror_status,
        "mirrorMismatch": mirror_status == "mismatch",
        "mirrorsMatch": mirrors_match,
        "summary": summary_fn(effective) if effective_source is not None else None,
    }


def producer_readiness_reconciliation_report(
    claims: dict[str, Any], recomputed_readiness: dict[str, Any]
) -> dict[str, Any]:
    summary = claims["thresholdBaselineReadiness"]["summary"]
    producer_ready = None
    producer_status = None
    producer_reason_count = None
    producer_reasons: list[str] = []
    if isinstance(summary, dict):
        producer_ready = summary.get("readyForThresholdBaseline")
        producer_status = summary.get("status")
        producer_reason_count = summary.get("reasonCount")
        producer_reasons = summary.get("reasons") or []
    recomputed_ready = recomputed_readiness["readyForThresholdBaseline"]
    recomputed_status = recomputed_readiness["status"]
    ready_matches = (
        None if producer_ready is None else producer_ready == recomputed_ready
    )
    status_matches = (
        None if producer_status is None else producer_status == recomputed_status
    )
    if producer_ready is None and producer_status is None:
        reconciliation_status = "missing-producer-readiness"
    elif ready_matches is False or status_matches is False:
        reconciliation_status = "producer-differs-from-comparator"
    else:
        reconciliation_status = "producer-matches-comparator"
    return {
        "advisory": True,
        "mode": "report-only",
        "producerReadyForThresholdBaseline": producer_ready,
        "producerStatus": producer_status,
        "producerReasonCount": producer_reason_count,
        "producerReasons": producer_reasons,
        "producerSource": claims["thresholdBaselineReadiness"]["effectiveSource"],
        "comparatorReadyForThresholdBaseline": recomputed_ready,
        "comparatorStatus": recomputed_status,
        "comparatorReasonCount": recomputed_readiness["reasonCount"],
        "comparatorReasons": recomputed_readiness["reasons"],
        "readyMatchesComparator": ready_matches,
        "statusMatchesComparator": status_matches,
        "status": reconciliation_status,
        "policy": (
            "Producer-declared threshold-baseline readiness is preserved for "
            "dashboard provenance only. Comparator-recomputed readiness remains "
            "the authoritative report-only curation hint and never changes "
            "comparator exit status."
        ),
    }


def producer_policy_claims_report(
    report: dict[str, Any], recomputed_readiness: dict[str, Any]
) -> dict[str, Any]:
    claims = {
        "advisoryThresholdPolicy": producer_claim_source_report(
            report,
            PRODUCER_ADVISORY_THRESHOLD_POLICY_PATHS,
            producer_advisory_threshold_policy_summary,
        ),
        "thresholdBaselineReadiness": producer_claim_source_report(
            report,
            PRODUCER_THRESHOLD_BASELINE_READINESS_PATHS,
            producer_threshold_baseline_readiness_summary,
        ),
    }
    mirror_mismatches = [
        name for name, claim in claims.items() if claim["mirrorMismatch"]
    ]
    result = {
        "advisory": True,
        "mode": "report-only",
        **claims,
        "mirrorMismatchCount": len(mirror_mismatches),
        "mirrorMismatches": mirror_mismatches,
        "policy": (
            "Producer-declared advisory threshold policy and readiness claims "
            "are copied from top-level and metadata mirror fields for provenance "
            "only. They are not validated as comparator policy inputs and never "
            "affect comparator exit status."
        ),
    }
    result["readinessReconciliation"] = producer_readiness_reconciliation_report(
        result, recomputed_readiness
    )
    return result


def producer_claims_pair_summary(
    baseline_claims: dict[str, Any],
    candidate_claims: dict[str, Any],
    *,
    compatible_ready_pair: bool,
) -> dict[str, Any]:
    report_claims = {
        "baseline": baseline_claims,
        "candidate": candidate_claims,
    }
    mirror_mismatches = [
        f"{label}.{claim_name}"
        for label, claims in report_claims.items()
        for claim_name in claims["mirrorMismatches"]
    ]
    readiness_mismatches = [
        label
        for label, claims in report_claims.items()
        if claims["readinessReconciliation"]["status"]
        == "producer-differs-from-comparator"
    ]
    producer_ready_values = [
        claims["readinessReconciliation"]["producerReadyForThresholdBaseline"]
        for claims in report_claims.values()
    ]
    producer_ready_pair = (
        None
        if any(value is None for value in producer_ready_values)
        else all(value is True for value in producer_ready_values)
    )
    return {
        "advisory": True,
        "mode": "report-only",
        "reportsWithProducerAdvisoryThresholdPolicy": [
            label
            for label, claims in report_claims.items()
            if claims["advisoryThresholdPolicy"]["present"]
        ],
        "reportsWithProducerThresholdBaselineReadiness": [
            label
            for label, claims in report_claims.items()
            if claims["thresholdBaselineReadiness"]["present"]
        ],
        "mirrorMismatchCount": len(mirror_mismatches),
        "mirrorMismatches": mirror_mismatches,
        "readinessMismatchCount": len(readiness_mismatches),
        "readinessMismatches": readiness_mismatches,
        "producerReadyForThresholdBaselineCount": sum(
            1 for value in producer_ready_values if value is True
        ),
        "producerReadyPairClaim": producer_ready_pair,
        "comparatorCompatibleReadyPair": compatible_ready_pair,
        "policy": (
            "Producer claim summaries are report-only provenance. Comparator "
            "structural status, recomputed readiness, and metadata compatibility "
            "remain separate; producer claim mismatch never fails comparison."
        ),
    }


def readiness_context_report(
    metadata: ReportPolicyMetadata, cases: dict[str, ReportCase]
) -> dict[str, Any]:
    context = policy_context_report(metadata)
    categories = sorted({case.category for case in cases.values()})
    command_profiles = sorted(
        {case.command_profile for case in cases.values() if case.command_profile}
    )
    opt_level_values = {case.opt_level for case in cases.values() if case.opt_level}
    metadata_opt_level = metadata.fields.get("optLevel")
    if isinstance(metadata_opt_level, str) and metadata_opt_level:
        opt_level_values.add(metadata_opt_level)
    opt_levels = sorted(opt_level_values)
    profiles = sorted({case.profile for case in cases.values() if case.profile})
    targets = sorted({case.target for case in cases.values() if case.target})
    return {
        "categories": categories,
        "categoryCount": len(categories),
        "commandProfileCount": len(command_profiles),
        "commandProfiles": command_profiles,
        "fields": context["fields"],
        "missingFields": context["missingFields"],
        "optLevelCount": len(opt_levels),
        "optLevels": opt_levels,
        "profileCount": len(profiles),
        "profiles": profiles,
        "requiredFields": context["requiredFields"],
        "targetCount": len(targets),
        "targets": targets,
        "toolchainClassifications": context["toolchainClassifications"],
        "toolchainClasses": context["toolchainClasses"],
        "toolchainLabelCount": context["toolchainLabelCount"],
        "toolchainLabels": context["toolchainLabels"],
        "toolchains": context["toolchains"],
    }


def comparison_dimensions_report(
    metadata: ReportPolicyMetadata, cases: dict[str, ReportCase]
) -> dict[str, Any]:
    context = readiness_context_report(metadata, cases)
    fields = context["fields"]
    return {
        "caseCategories": context["categories"],
        "caseCategoryCount": context["categoryCount"],
        "commandProfileCount": context["commandProfileCount"],
        "commandProfiles": context["commandProfiles"],
        "comparisonWindow": fields.get("comparisonWindow"),
        "fields": fields,
        "hostClass": fields.get("hostClass"),
        "hostLabel": fields.get("hostLabel"),
        "missingFields": context["missingFields"],
        "optLevel": fields.get("optLevel"),
        "optLevelCount": context["optLevelCount"],
        "optLevels": context["optLevels"],
        "profileCount": context["profileCount"],
        "profiles": context["profiles"],
        "requiredFields": context["requiredFields"],
        "skippedToolAccounting": metadata.skipped_tool_accounting,
        "targetCount": context["targetCount"],
        "targetProfile": fields.get("targetProfile"),
        "targets": context["targets"],
        "toolchainClassifications": context["toolchainClassifications"],
        "toolchainClasses": context["toolchainClasses"],
        "toolchainLabelCount": context["toolchainLabelCount"],
        "toolchainLabels": context["toolchainLabels"],
        "toolchains": context["toolchains"],
    }


def threshold_baseline_requirement(
    name: str,
    *,
    satisfied: bool,
    reason_if_unsatisfied: str,
    observed: dict[str, Any],
) -> dict[str, Any]:
    return {
        "name": name,
        "observed": observed,
        "reasonIfUnsatisfied": reason_if_unsatisfied,
        "satisfied": satisfied,
    }


def case_repeated_timing_evidence(case: ReportCase) -> dict[str, Any]:
    sample_count = case.timing_sample_count
    sufficient = (
        sample_count is not None and sample_count >= TIMING_ADVISORY_MIN_SAMPLE_COUNT
    )
    if sample_count is None:
        reason = "missingSampleCount"
    elif sample_count < TIMING_ADVISORY_MIN_SAMPLE_COUNT:
        reason = "insufficientSampleCount"
    else:
        reason = None
    return {
        "case": case.key,
        "minimumSampleCount": TIMING_ADVISORY_MIN_SAMPLE_COUNT,
        "reason": reason,
        "sampleCount": sample_count,
        "sampleSource": case.timing_sample_source,
        "sufficient": sufficient,
    }


def case_threshold_identity_evidence(case: ReportCase) -> dict[str, Any]:
    missing_fields = list(case.threshold_identity_missing_fields)
    return {
        "case": case.key,
        "complete": not missing_fields,
        "missingFieldCount": len(missing_fields),
        "missingFields": missing_fields,
        "requiredFields": list(REQUIRED_THRESHOLD_CASE_IDENTITY_FIELDS),
    }


def timed_case_identity_report(cases: dict[str, ReportCase]) -> dict[str, Any]:
    timed_cases = [case for case in cases.values() if case.elapsed_ns is not None]
    case_evidence = [case_threshold_identity_evidence(case) for case in timed_cases]
    incomplete = [
        evidence for evidence in case_evidence if evidence["complete"] is not True
    ]
    return {
        "caseEvidence": sorted(case_evidence, key=lambda evidence: evidence["case"]),
        "incompleteCaseCount": len(incomplete),
        "incompleteCases": [
            evidence["case"]
            for evidence in sorted(incomplete, key=lambda item: item["case"])
        ],
        "policy": (
            "Threshold-baseline evidence requires explicit fixtureName, target, "
            "profile, and optLevel labels on timed cases. Legacy case-key "
            "inference remains usable for report comparison but is not strong "
            "enough for threshold claims."
        ),
        "requiredFields": list(REQUIRED_THRESHOLD_CASE_IDENTITY_FIELDS),
        "timedCaseCount": len(timed_cases),
    }


def repeated_timing_evidence_report(cases: dict[str, ReportCase]) -> dict[str, Any]:
    timed_cases = [case for case in cases.values() if case.elapsed_ns is not None]
    case_evidence = [case_repeated_timing_evidence(case) for case in timed_cases]
    insufficient = [
        evidence for evidence in case_evidence if evidence["sufficient"] is not True
    ]
    repeated_count = len(case_evidence) - len(insufficient)
    return {
        "caseEvidence": sorted(case_evidence, key=lambda evidence: evidence["case"]),
        "insufficientRepeatedEvidenceCaseCount": len(insufficient),
        "insufficientRepeatedEvidenceCases": [
            evidence["case"]
            for evidence in sorted(insufficient, key=lambda item: item["case"])
        ],
        "minimumSampleCount": TIMING_ADVISORY_MIN_SAMPLE_COUNT,
        "policy": TIMING_ADVISORY_EVIDENCE_POLICY,
        "repeatedTimedCaseCount": repeated_count,
        "timedCaseCount": len(timed_cases),
    }


def threshold_baseline_requirements(
    context: dict[str, Any],
    *,
    timed_case_count: int,
    timed_case_identity: dict[str, Any],
    repeated_timing_evidence: dict[str, Any],
    validation_issues: list[str],
    functional_failures: dict[str, str],
    skipped_accounting: dict[str, Any],
) -> list[dict[str, Any]]:
    required_skipped_case_count = skipped_accounting[
        "requiredOrUnclassifiedSkippedCaseCount"
    ]
    skipped_cases_without_tools = skipped_accounting[
        "skippedCasesWithoutUnavailableTools"
    ]
    insufficient_repeated_evidence = repeated_timing_evidence[
        "insufficientRepeatedEvidenceCases"
    ]
    incomplete_identity_cases = timed_case_identity["incompleteCases"]
    return [
        threshold_baseline_requirement(
            "recognizedContextFields",
            satisfied=not context["missingFields"],
            reason_if_unsatisfied="missingContextFields",
            observed={
                "missingFieldCount": len(context["missingFields"]),
                "missingFields": context["missingFields"],
                "requiredFields": context["requiredFields"],
            },
        ),
        threshold_baseline_requirement(
            "timedCases",
            satisfied=timed_case_count > 0,
            reason_if_unsatisfied="noTimedCases",
            observed={"timedCaseCount": timed_case_count},
        ),
        threshold_baseline_requirement(
            "explicitTimedCaseIdentity",
            satisfied=timed_case_count == 0 or not incomplete_identity_cases,
            reason_if_unsatisfied="missingTimedCaseIdentityFields",
            observed={
                "incompleteCaseCount": len(incomplete_identity_cases),
                "incompleteCases": incomplete_identity_cases,
                "requiredFields": timed_case_identity["requiredFields"],
                "timedCaseCount": timed_case_count,
            },
        ),
        threshold_baseline_requirement(
            "repeatedTimingEvidence",
            satisfied=timed_case_count > 0 and not insufficient_repeated_evidence,
            reason_if_unsatisfied="insufficientRepeatedTimingEvidence",
            observed={
                "insufficientRepeatedEvidenceCaseCount": len(
                    insufficient_repeated_evidence
                ),
                "insufficientRepeatedEvidenceCases": insufficient_repeated_evidence,
                "minimumSampleCount": TIMING_ADVISORY_MIN_SAMPLE_COUNT,
                "repeatedTimedCaseCount": repeated_timing_evidence[
                    "repeatedTimedCaseCount"
                ],
                "timedCaseCount": timed_case_count,
            },
        ),
        threshold_baseline_requirement(
            "cleanReportShape",
            satisfied=not validation_issues,
            reason_if_unsatisfied="validationIssues",
            observed={"validationIssueCount": len(validation_issues)},
        ),
        threshold_baseline_requirement(
            "functionalSuccess",
            satisfied=not functional_failures,
            reason_if_unsatisfied="functionalFailures",
            observed={
                "functionalFailureCaseCount": len(functional_failures),
                "functionalFailureCases": sorted(functional_failures),
            },
        ),
        threshold_baseline_requirement(
            "requiredToolCoverage",
            satisfied=required_skipped_case_count == 0,
            reason_if_unsatisfied="requiredOrUnclassifiedSkippedTools",
            observed={
                "requiredOrUnclassifiedSkippedCaseCount": (required_skipped_case_count),
                "requiredOrUnclassifiedSkippedToolLabels": skipped_accounting[
                    "requiredOrUnclassifiedSkippedToolLabels"
                ],
            },
        ),
        threshold_baseline_requirement(
            "skippedToolEvidence",
            satisfied=not skipped_cases_without_tools,
            reason_if_unsatisfied="skippedCasesWithoutUnavailableTools",
            observed={
                "skippedCasesWithoutUnavailableToolCount": len(
                    skipped_cases_without_tools
                ),
                "skippedCasesWithoutUnavailableTools": skipped_cases_without_tools,
            },
        ),
    ]


def baseline_readiness_report(
    metadata: ReportPolicyMetadata,
    cases: dict[str, ReportCase],
    validation_issues: list[str],
) -> dict[str, Any]:
    context = policy_context_report(metadata)
    skipped_accounting = metadata.skipped_tool_accounting
    functional_failures = functional_failure_cases(cases)
    timed_case_count = sum(1 for case in cases.values() if case.elapsed_ns is not None)
    timed_case_identity = timed_case_identity_report(cases)
    repeated_timing_evidence = repeated_timing_evidence_report(cases)
    required_skipped_case_count = skipped_accounting[
        "requiredOrUnclassifiedSkippedCaseCount"
    ]
    skipped_cases_without_tools = skipped_accounting[
        "skippedCasesWithoutUnavailableTools"
    ]
    requirements = threshold_baseline_requirements(
        context,
        timed_case_count=timed_case_count,
        timed_case_identity=timed_case_identity,
        repeated_timing_evidence=repeated_timing_evidence,
        validation_issues=validation_issues,
        functional_failures=functional_failures,
        skipped_accounting=skipped_accounting,
    )
    unsatisfied_requirements = [
        requirement["name"]
        for requirement in requirements
        if not requirement["satisfied"]
    ]

    reasons = [
        requirement["reasonIfUnsatisfied"]
        for requirement in requirements
        if not requirement["satisfied"]
    ]

    return {
        "advisory": True,
        "readyForThresholdBaseline": not reasons,
        "status": "ready" if not reasons else "incomplete",
        "reasonCount": len(reasons),
        "reasons": reasons,
        "satisfiedThresholdBaselineRequirementCount": (
            len(requirements) - len(unsatisfied_requirements)
        ),
        "thresholdBaselineRequirementCount": len(requirements),
        "thresholdBaselineRequirements": requirements,
        "thresholdBaselineRequirementsPolicy": (
            "These deterministic checks explain threshold-baseline eligibility "
            "for dashboard curation only; unsatisfied checks do not change "
            "comparator exit status."
        ),
        "context": readiness_context_report(metadata, cases),
        "timedCaseIdentity": timed_case_identity,
        "repeatedTimingEvidence": repeated_timing_evidence,
        "unsatisfiedThresholdBaselineRequirementCount": len(unsatisfied_requirements),
        "unsatisfiedThresholdBaselineRequirements": unsatisfied_requirements,
        "missingContextFields": context["missingFields"],
        "timedCaseCount": timed_case_count,
        "incompleteTimedCaseIdentityCaseCount": timed_case_identity[
            "incompleteCaseCount"
        ],
        "incompleteTimedCaseIdentityCases": timed_case_identity["incompleteCases"],
        "validationIssueCount": len(validation_issues),
        "functionalFailureCaseCount": len(functional_failures),
        "functionalFailureCases": sorted(functional_failures),
        "requiredOrUnclassifiedSkippedCaseCount": required_skipped_case_count,
        "requiredOrUnclassifiedSkippedToolLabels": skipped_accounting[
            "requiredOrUnclassifiedSkippedToolLabels"
        ],
        "optionalSkippedCaseCount": skipped_accounting["optionalSkippedCaseCount"],
        "optionalSkippedToolLabels": skipped_accounting["optionalSkippedToolLabels"],
        "skippedCasesWithoutUnavailableToolCount": skipped_accounting[
            "skippedCasesWithoutUnavailableToolCount"
        ],
        "skippedCasesWithoutUnavailableTools": skipped_cases_without_tools,
        "policy": (
            "Readiness is advisory. Incomplete reports can still be compared, but "
            "should not be promoted to timing-threshold baselines until required "
            "context, clean validation, timed samples, and required tool coverage "
            "are present."
        ),
    }


def advisory_context_report(
    baseline: ReportPolicyMetadata, candidate: ReportPolicyMetadata
) -> dict[str, Any]:
    compatibility = compare_policy_metadata(baseline, candidate)
    return {
        "advisory": True,
        "advisorySummary": advisory_warning_summary(baseline, candidate, compatibility),
        "baseline": policy_context_report(baseline),
        "candidate": policy_context_report(candidate),
        "caseContextFields": [
            "case",
            "fixtureCategory",
            "fixtureName",
            "profile",
            "reportCase",
            "target",
        ],
        "missingFieldPolicy": (
            "Recognized host, toolchain, and run-policy fields are reported only "
            "when present; missingFields lists absent context instead of inferring it."
        ),
    }


def timing_metadata_comparability_evidence(
    baseline: ReportPolicyMetadata,
    candidate: ReportPolicyMetadata,
    compatibility: dict[str, Any],
) -> dict[str, Any]:
    baseline_context = policy_context_report(baseline)
    candidate_context = policy_context_report(candidate)
    reasons: list[str] = []
    if baseline_context["missingFields"]:
        reasons.append("baseline:missingMetadataFields")
    if candidate_context["missingFields"]:
        reasons.append("candidate:missingMetadataFields")
    if compatibility["compatible"] is not True:
        reasons.append("pair:metadataDrift")

    metadata_drift_free = compatibility["compatible"] is True
    metadata_fields_complete = (
        not baseline_context["missingFields"] and not candidate_context["missingFields"]
    )
    comparable = metadata_fields_complete and metadata_drift_free
    return {
        "advisory": True,
        "baselineMissingFields": baseline_context["missingFields"],
        "candidateMissingFields": candidate_context["missingFields"],
        "compatible": comparable,
        "compatibility": compatibility,
        "metadataCompatible": comparable,
        "metadataDriftFree": metadata_drift_free,
        "metadataFieldsComplete": metadata_fields_complete,
        "minimumSampleCount": TIMING_ADVISORY_MIN_SAMPLE_COUNT,
        "mode": "report-only",
        "policy": TIMING_ADVISORY_METADATA_COMPARABILITY_POLICY,
        "reasonCount": len(reasons),
        "reasons": reasons,
        "releaseBlockerPolicy": TIMING_ADVISORY_RELEASE_BLOCKER_POLICY,
        "requiresComparableMetadata": True,
        "requiresRepeatedBaselineAndCandidateSamples": True,
    }


def timing_claim_eligibility_disposition(
    *,
    repeated_sufficient: bool,
    metadata_compatible: bool,
    case_identity_complete: bool,
) -> str:
    if repeated_sufficient and metadata_compatible and case_identity_complete:
        return "claim-eligible"
    if not repeated_sufficient:
        return "insufficient-repeated-evidence"
    if not metadata_compatible:
        return "incomparable-metadata"
    if not case_identity_complete:
        return "incomplete-case-identity"
    return "insufficient-advisory-evidence"


def case_dimension_context(case: ReportCase) -> dict[str, Any]:
    return {
        "backend": case.backend,
        "case": case.key,
        "fixtureCategory": case.category,
        "fixtureName": case.fixture_name,
        "profile": case.profile,
        "reportCase": case.report_key,
        "target": case.target,
    }


def case_comparison_context(
    baseline_case: ReportCase, candidate_case: ReportCase
) -> dict[str, Any]:
    baseline = case_dimension_context(baseline_case)
    candidate = case_dimension_context(candidate_case)
    mismatches = compare_mapping_values(baseline, candidate)
    return {
        "baseline": baseline,
        "candidate": candidate,
        "matches": not mismatches,
        "mismatches": mismatches,
    }


def timing_advisory_claim_evidence(
    baseline_case: ReportCase,
    candidate_case: ReportCase,
    metadata_evidence: dict[str, Any],
) -> dict[str, Any]:
    baseline_evidence = case_repeated_timing_evidence(baseline_case)
    candidate_evidence = case_repeated_timing_evidence(candidate_case)
    baseline_identity = case_threshold_identity_evidence(baseline_case)
    candidate_identity = case_threshold_identity_evidence(candidate_case)
    reasons: list[str] = []
    if baseline_evidence["sufficient"] is not True:
        reasons.append(f"baseline:{baseline_evidence['reason']}")
    if candidate_evidence["sufficient"] is not True:
        reasons.append(f"candidate:{candidate_evidence['reason']}")
    repeated_sufficient = not reasons
    if metadata_evidence["compatible"] is not True:
        reasons.extend(metadata_evidence["reasons"])
    metadata_compatible = metadata_evidence["compatible"] is True
    identity_reasons: list[str] = []
    if baseline_identity["complete"] is not True:
        identity_reasons.append("baseline:missingCaseIdentityFields")
    if candidate_identity["complete"] is not True:
        identity_reasons.append("candidate:missingCaseIdentityFields")
    reasons.extend(identity_reasons)
    case_identity_complete = not identity_reasons
    sufficient = repeated_sufficient and metadata_compatible and case_identity_complete
    claim_eligibility_disposition = timing_claim_eligibility_disposition(
        repeated_sufficient=repeated_sufficient,
        metadata_compatible=metadata_compatible,
        case_identity_complete=case_identity_complete,
    )
    return {
        "advisory": True,
        "baseline": baseline_evidence,
        "candidate": candidate_evidence,
        "caseIdentity": {
            "baseline": baseline_identity,
            "candidate": candidate_identity,
            "complete": case_identity_complete,
            "policy": (
                "Timed case identity must be explicit for threshold claims; "
                "case-key inference is retained only for coverage comparison."
            ),
            "reasonCount": len(identity_reasons),
            "reasons": identity_reasons,
            "requiredFields": list(REQUIRED_THRESHOLD_CASE_IDENTITY_FIELDS),
        },
        "caseIdentityComplete": case_identity_complete,
        "claimEligible": sufficient,
        "claimEligibilityDisposition": claim_eligibility_disposition,
        "claimSuppressionReasons": [] if sufficient else reasons,
        "metadata": metadata_evidence,
        "metadataCompatible": metadata_compatible,
        "minimumSampleCount": TIMING_ADVISORY_MIN_SAMPLE_COUNT,
        "mode": "report-only",
        "policy": TIMING_ADVISORY_EVIDENCE_POLICY,
        "reasonCount": len(reasons),
        "reasons": reasons,
        "releaseBlockerPolicy": TIMING_ADVISORY_RELEASE_BLOCKER_POLICY,
        "requiresExplicitTimedCaseIdentity": True,
        "sufficientRepeatedEvidence": repeated_sufficient,
        "sufficientCaseIdentity": case_identity_complete,
        "sufficientForAdvisoryThresholdClaim": sufficient,
        "sufficientForExplicitThresholdClaim": sufficient,
        "sufficientForTimingAdvisoryClaim": sufficient,
    }


def threshold_claim_disposition(
    evidence: dict[str, Any], *, measured_exceeds: bool
) -> str:
    if evidence["sufficientForAdvisoryThresholdClaim"]:
        return "threshold-exceeded" if measured_exceeds else "within-threshold"
    if evidence["sufficientRepeatedEvidence"] is not True:
        return "insufficient-repeated-evidence"
    if evidence["metadataCompatible"] is not True:
        return "incomparable-metadata"
    if evidence["caseIdentityComplete"] is not True:
        return "incomplete-case-identity"
    return "insufficient-advisory-evidence"


def threshold_evidence_summary(evidence: dict[str, Any]) -> dict[str, Any]:
    return {
        "baselineSampleCount": evidence["baseline"]["sampleCount"],
        "baselineSampleSource": evidence["baseline"]["sampleSource"],
        "baselineSampleSufficient": evidence["baseline"]["sufficient"],
        "candidateSampleCount": evidence["candidate"]["sampleCount"],
        "candidateSampleSource": evidence["candidate"]["sampleSource"],
        "candidateSampleSufficient": evidence["candidate"]["sufficient"],
        "caseIdentityComplete": evidence["caseIdentityComplete"],
        "caseIdentityReasons": evidence["caseIdentity"]["reasons"],
        "claimEligible": evidence["claimEligible"],
        "claimEligibilityDisposition": evidence["claimEligibilityDisposition"],
        "claimSuppressionReasons": evidence["claimSuppressionReasons"],
        "metadataCompatible": evidence["metadataCompatible"],
        "minimumSampleCount": evidence["minimumSampleCount"],
        "requiresExplicitTimedCaseIdentity": True,
        "releaseBlockerPolicy": TIMING_ADVISORY_RELEASE_BLOCKER_POLICY,
        "sufficientCaseIdentity": evidence["sufficientCaseIdentity"],
        "sufficientRepeatedEvidence": evidence["sufficientRepeatedEvidence"],
    }


def regression_policy_disposition(
    evidence: dict[str, Any],
    *,
    explicit_threshold_enabled: bool,
    explicit_threshold_exceeded: bool,
) -> str:
    if evidence["sufficientRepeatedEvidence"] is not True:
        if explicit_threshold_enabled:
            return "advisory-threshold-insufficient-repeated-evidence"
        return "advisory-insufficient-repeated-evidence"
    if evidence["metadataCompatible"] is not True:
        if explicit_threshold_enabled:
            return "advisory-threshold-incomparable-metadata"
        return "advisory-incomparable-metadata"
    if evidence["caseIdentityComplete"] is not True:
        if explicit_threshold_enabled:
            return "advisory-threshold-incomplete-case-identity"
        return "advisory-incomplete-case-identity"
    if not explicit_threshold_enabled:
        return "advisory"
    if explicit_threshold_exceeded:
        return "advisory-threshold-exceeded"
    return "within-advisory-threshold"


def apply_explicit_threshold_evidence(
    entry: dict[str, Any], evidence: dict[str, Any]
) -> None:
    entry["timingEvidence"] = evidence
    entry["timingAdvisoryClaimEligible"] = evidence["sufficientForTimingAdvisoryClaim"]
    measured_exceeds = entry["exceedsExplicitThreshold"]
    entry["measuredExceedsExplicitThreshold"] = measured_exceeds
    explicit_threshold = entry.get("explicitThreshold")
    if explicit_threshold is None:
        return

    claim_eligible = evidence["sufficientForExplicitThresholdClaim"]
    explicit_threshold["claimEligible"] = claim_eligible
    explicit_threshold["claimPolicy"] = TIMING_ADVISORY_EVIDENCE_POLICY
    explicit_threshold["evidence"] = threshold_evidence_summary(evidence)
    explicit_threshold["caseIdentityComplete"] = evidence["caseIdentityComplete"]
    explicit_threshold["metadataCompatible"] = evidence["metadataCompatible"]
    explicit_threshold["minimumSampleCount"] = evidence["minimumSampleCount"]
    explicit_threshold["requiresExplicitTimedCaseIdentity"] = True
    explicit_threshold["releaseBlockerPolicy"] = TIMING_ADVISORY_RELEASE_BLOCKER_POLICY
    explicit_threshold["reportOnlyReason"] = TIMING_ADVISORY_RELEASE_BLOCKER_POLICY
    explicit_threshold["sufficientCaseIdentity"] = evidence["sufficientCaseIdentity"]
    explicit_threshold["sufficientRepeatedEvidence"] = evidence[
        "sufficientRepeatedEvidence"
    ]
    explicit_threshold["measuredExceedsThreshold"] = measured_exceeds
    if claim_eligible:
        explicit_threshold["claimDisposition"] = threshold_claim_disposition(
            evidence, measured_exceeds=measured_exceeds
        )
        return

    explicit_threshold["claimDisposition"] = threshold_claim_disposition(
        evidence, measured_exceeds=measured_exceeds
    )
    entry["exceedsExplicitThreshold"] = False
    entry["wouldFailExplicitThresholdIfEnforced"] = False


def report_summary(path: Path, report: dict[str, Any], cases: dict[str, ReportCase]):
    categories = sorted({case.category for case in cases.values()})
    command_profiles = sorted(report_command_profiles(report, cases))
    functional_failures = functional_failure_cases(cases)
    native_optimization = native_optimization_case_accounting(cases.values())
    opt_levels = sorted({case.opt_level for case in cases.values() if case.opt_level})
    package_modes = sorted(
        {case.package_mode for case in cases.values() if case.package_mode}
    )
    profiles = sorted(report_profiles(report, cases))
    targets = sorted(report_targets(report, cases))
    skipped = skipped_cases(cases)
    toolchain_labels = sorted(report_toolchain_labels(report, cases))
    unavailable_toolchain_labels = sorted(
        report_unavailable_toolchain_labels(report, cases)
    )
    raw_cases = raw_case_objects(report)
    return {
        **artifact_accounting(raw_cases),
        "caseCount": len(cases),
        "caseCountByNativeArtifactDescriptorOptimizationEvidenceStatus": (
            native_optimization["caseCountByNativeArtifactDescriptorEvidenceStatus"]
        ),
        "caseCountByNativeArtifactDescriptorOptimizationStatus": (
            native_optimization["caseCountByNativeArtifactDescriptorStatus"]
        ),
        "caseCountByNativeOptimizationEvidenceStatus": native_optimization[
            "caseCountByEvidenceStatus"
        ],
        "caseCountByNativeOptimizationStatus": native_optimization["caseCountByStatus"],
        "categoryCount": len(categories),
        "commandProfileCount": len(command_profiles),
        "corpusVersion": report.get("corpusVersion"),
        "functionalFailureCaseCount": len(functional_failures),
        "functionalFailureCases": sorted(functional_failures),
        "nativeArtifactDescriptorOptimizationEvidence": native_optimization[
            "nativeArtifactDescriptorOptimizationEvidence"
        ],
        "nativeArtifactDescriptorOptimizationStatusCount": native_optimization[
            "nativeArtifactDescriptorOptimizationStatusCaseCount"
        ],
        "nativeArtifactDescriptorOptimizationStatuses": native_optimization[
            "nativeArtifactDescriptorOptimizationStatuses"
        ],
        "nativeOptimizationEvidence": native_optimization["nativeOptimizationEvidence"],
        "nativeOptimizationStatusCount": native_optimization[
            "nativeOptimizationStatusCaseCount"
        ],
        "nativeOptimizationStatuses": native_optimization["nativeOptimizationStatuses"],
        "path": path.as_posix(),
        "packageModeCount": len(package_modes),
        "packageModes": package_modes,
        "profileCount": len(profiles),
        "schemaVersion": report.get("schemaVersion"),
        "optLevelCount": len(opt_levels),
        "optLevels": opt_levels,
        "skippedCaseCount": len(skipped),
        "skippedCaseCountByReason": skipped_case_count_by_reason(raw_cases),
        "skippedCasesWithUnavailableTools": skipped_cases_with_unavailable_tools(
            raw_cases
        ),
        "skippedToolCaseCountByTool": skipped_tool_case_count_by_tool(raw_cases),
        "skippedToolCasesByTool": skipped_tool_cases_by_tool_from_raw(raw_cases),
        "targetCount": len(targets),
        "timedCaseCount": sum(
            1 for case in cases.values() if case.elapsed_ns is not None
        ),
        "toolchainLabelCount": len(toolchain_labels),
        "tool": report.get("tool"),
        "unavailableToolchainLabelCount": len(unavailable_toolchain_labels),
        **execution_accounting(raw_cases),
        **verification_accounting(raw_cases),
    }


def native_optimization_case_accounting(
    cases: Iterable[ReportCase],
) -> dict[str, Any]:
    case_list = list(cases)
    descriptor_status_counts: dict[str, int] = {}
    descriptor_evidence_counts: dict[str, int] = {}
    status_counts: dict[str, int] = {}
    evidence_counts: dict[str, int] = {}
    for case in case_list:
        if case.native_artifact_descriptor_optimization_status is not None:
            add_count(
                descriptor_status_counts,
                case.native_artifact_descriptor_optimization_status,
            )
        add_count(
            descriptor_evidence_counts,
            case.native_artifact_descriptor_optimization_evidence_status,
        )
        if case.native_optimization_status is not None:
            add_count(status_counts, case.native_optimization_status)
        add_count(evidence_counts, case.native_optimization_evidence_status)

    descriptor_evidence_counts = sorted_counts(descriptor_evidence_counts)
    descriptor_status_counts = sorted_counts(descriptor_status_counts)
    evidence_counts = sorted_counts(evidence_counts)
    status_counts = sorted_counts(status_counts)
    return {
        "caseCount": len(case_list),
        "caseCountByNativeArtifactDescriptorEvidenceStatus": (
            descriptor_evidence_counts
        ),
        "caseCountByNativeArtifactDescriptorStatus": descriptor_status_counts,
        "caseCountByEvidenceStatus": evidence_counts,
        "caseCountByStatus": status_counts,
        "nativeArtifactDescriptorOptimizationEvidence": (
            native_artifact_descriptor_evidence_summary_from_counts(
                case_count=len(case_list), evidence_counts=descriptor_evidence_counts
            )
        ),
        "nativeArtifactDescriptorOptimizationStatusCaseCount": sum(
            descriptor_status_counts.values()
        ),
        "nativeArtifactDescriptorOptimizationStatuses": sorted(
            descriptor_status_counts
        ),
        "evidenceCaseCount": sum(evidence_counts.values()),
        "knownStatusCount": evidence_counts.get("known-status", 0),
        "missingDebugOptimizationCount": evidence_counts.get(
            "missing-debug-optimization", 0
        ),
        "missingOrUnparsableEvidenceCount": (
            evidence_counts.get("missing-debug-optimization", 0)
            + evidence_counts.get("unparsable-native-profile", 0)
            + evidence_counts.get("declared-native-profile-missing", 0)
        ),
        "nativeOptimizationEvidence": native_optimization_evidence_summary_from_counts(
            case_count=len(case_list), evidence_counts=evidence_counts
        ),
        "nativeOptimizationStatusCaseCount": sum(status_counts.values()),
        "nativeOptimizationStatuses": sorted(status_counts),
        "nativeProfileDeclaredButMissingCount": evidence_counts.get(
            "declared-native-profile-missing", 0
        ),
        "nativeProfileNotDeclaredCount": evidence_counts.get(
            "native-profile-not-declared", 0
        ),
        "optimizationWithoutStatusCount": evidence_counts.get(
            "optimization-without-status", 0
        ),
        "unparsableNativeProfileCount": evidence_counts.get(
            "unparsable-native-profile", 0
        ),
    }


def dimension_label(value: Any) -> str:
    if isinstance(value, str) and value:
        return value
    return "unspecified"


def stable_group_key(fields: dict[str, str]) -> str:
    return "|".join(f"{name}={fields[name]}" for name in sorted(fields))


def toolchain_dimension(metadata: ReportPolicyMetadata) -> dict[str, Any]:
    classifications = toolchain_classifications(metadata.toolchains)
    if not metadata.toolchains:
        return {
            "key": "toolchains=unspecified",
            "labels": [],
            "toolchains": {},
            "classifications": {},
        }

    parts: list[str] = []
    for label, entry in metadata.toolchains.items():
        version = dimension_label(entry.get("version"))
        role = toolchain_role(entry)
        availability = toolchain_availability(entry)
        parts.append(f"{label}@{version}:{role}:{availability}")
    return {
        "key": "toolchains=" + ",".join(parts),
        "labels": sorted(metadata.toolchains),
        "toolchains": metadata.toolchains,
        "classifications": classifications,
    }


def aggregate_baseline_dimensions(metadata: ReportPolicyMetadata) -> dict[str, str]:
    toolchains = toolchain_dimension(metadata)
    return {
        "hostClass": dimension_label(metadata.fields.get("hostClass")),
        "hostLabel": dimension_label(metadata.fields.get("hostLabel")),
        "optLevel": dimension_label(metadata.fields.get("optLevel")),
        "targetProfile": dimension_label(metadata.fields.get("targetProfile")),
        "toolchains": toolchains["key"],
    }


def aggregate_case_dimensions(
    metadata: ReportPolicyMetadata, case: ReportCase
) -> dict[str, str]:
    baseline = aggregate_baseline_dimensions(metadata)
    return {
        **baseline,
        "category": dimension_label(case.category),
        "commandProfile": dimension_label(case.command_profile),
        "optLevel": dimension_label(case.opt_level or metadata.fields.get("optLevel")),
        "target": dimension_label(case.target),
    }


def aggregate_case_stability_dimensions(
    metadata: ReportPolicyMetadata, case: ReportCase
) -> dict[str, str]:
    return {
        **aggregate_case_dimensions(metadata, case),
        "case": dimension_label(case.key),
        "fixtureName": dimension_label(case.fixture_name),
        "profile": dimension_label(case.profile),
    }


def add_count(counts: dict[str, int], label: str, amount: int = 1) -> None:
    counts[label] = counts.get(label, 0) + amount


def sorted_counts(counts: dict[str, int]) -> dict[str, int]:
    return dict(sorted(counts.items()))


def median_ns(values: list[int]) -> int | float | None:
    if not values:
        return None
    sorted_values = sorted(values)
    midpoint = len(sorted_values) // 2
    if len(sorted_values) % 2:
        return sorted_values[midpoint]
    middle_total = sorted_values[midpoint - 1] + sorted_values[midpoint]
    if middle_total % 2 == 0:
        return middle_total // 2
    return middle_total / 2


def timing_sample(case: ReportCase, report_index: int, path: Path) -> dict[str, Any]:
    return {
        "case": case.key,
        "elapsedNs": case.elapsed_ns,
        "reportIndex": report_index,
        "reportPath": path.as_posix(),
    }


def stability_timing_sample(
    case: ReportCase,
    report_index: int,
    path: Path,
    readiness: dict[str, Any],
) -> dict[str, Any]:
    return {
        **timing_sample(case, report_index, path),
        "readyForThresholdBaseline": readiness["readyForThresholdBaseline"],
    }


def aggregate_timing_summary(samples: list[dict[str, Any]]) -> dict[str, Any]:
    elapsed_values = [
        sample["elapsedNs"]
        for sample in samples
        if isinstance(sample["elapsedNs"], int)
    ]
    if not elapsed_values:
        return {
            "averageNs": None,
            "maxNs": None,
            "medianNs": None,
            "minNs": None,
            "sampleCount": 0,
            "spreadNs": None,
            "spreadPercentOfMin": None,
            "totalNs": 0,
        }
    min_ns = min(elapsed_values)
    max_ns = max(elapsed_values)
    spread_ns = max_ns - min_ns
    total = sum(elapsed_values)
    return {
        "averageNs": total / len(elapsed_values),
        "maxNs": max_ns,
        "medianNs": median_ns(elapsed_values),
        "minNs": min_ns,
        "sampleCount": len(elapsed_values),
        "spreadNs": spread_ns,
        "spreadPercentOfMin": regression_percent(min_ns, max_ns),
        "totalNs": total,
    }


def timing_stability_class(timing: dict[str, Any]) -> str:
    sample_count = timing["sampleCount"]
    if sample_count == 0:
        return "untimed"
    if sample_count == 1:
        return "single-sample"
    if timing["spreadNs"] == 0:
        return "identical"
    return "variable"


def aggregate_stability_summary(groups: list[dict[str, Any]]) -> dict[str, Any]:
    class_counts: dict[str, int] = {}
    for group in groups:
        add_count(class_counts, group["stabilityClass"])

    multi_sample_groups = [
        group for group in groups if group["timing"]["sampleCount"] >= 2
    ]
    spread_values = [
        group["timing"]["spreadNs"]
        for group in multi_sample_groups
        if isinstance(group["timing"]["spreadNs"], int)
    ]
    spread_percent_values = [
        group["timing"]["spreadPercentOfMin"]
        for group in multi_sample_groups
        if isinstance(group["timing"]["spreadPercentOfMin"], float)
    ]
    return {
        "caseStabilityGroupCount": len(groups),
        "identicalCaseStabilityGroupCount": class_counts.get("identical", 0),
        "maxSpreadNs": max(spread_values) if spread_values else None,
        "maxSpreadPercentOfMin": (
            max(spread_percent_values) if spread_percent_values else None
        ),
        "multiSampleCaseStabilityGroupCount": len(multi_sample_groups),
        "sampleCount": sum(group["timing"]["sampleCount"] for group in groups),
        "singleSampleCaseStabilityGroupCount": class_counts.get("single-sample", 0),
        "stabilityClassCounts": sorted_counts(class_counts),
        "untimedCaseStabilityGroupCount": class_counts.get("untimed", 0),
        "variableCaseStabilityGroupCount": class_counts.get("variable", 0),
    }


def aggregate_readiness_report(entries: list[dict[str, Any]]) -> dict[str, Any]:
    readiness_status_counts: dict[str, int] = {}
    reason_counts: dict[str, int] = {}
    requirement_counts: dict[str, int] = {}
    missing_context_counts: dict[str, int] = {}
    report_indexes_by_reason: dict[str, list[int]] = {}
    report_paths_by_reason: dict[str, list[str]] = {}
    report_indexes_by_requirement: dict[str, list[int]] = {}
    report_paths_by_requirement: dict[str, list[str]] = {}
    report_indexes_by_missing_context: dict[str, list[int]] = {}
    report_paths_by_missing_context: dict[str, list[str]] = {}
    insufficient_repeated_evidence_reports: list[int] = []
    required_skipped_tool_labels: set[str] = set()
    total_required_skipped_cases = 0
    total_skipped_cases_without_tools = 0
    total_insufficient_repeated_evidence_cases = 0

    for entry in entries:
        readiness = entry["readiness"]
        report_index = entry["reportIndex"]
        report_path = entry["path"].as_posix()
        status = "ready" if readiness["readyForThresholdBaseline"] else "incomplete"
        add_count(readiness_status_counts, status)

        for reason in readiness["reasons"]:
            add_count(reason_counts, reason)
            report_indexes_by_reason.setdefault(reason, []).append(report_index)
            report_paths_by_reason.setdefault(reason, []).append(report_path)

        for requirement in readiness["unsatisfiedThresholdBaselineRequirements"]:
            add_count(requirement_counts, requirement)
            report_indexes_by_requirement.setdefault(requirement, []).append(
                report_index
            )
            report_paths_by_requirement.setdefault(requirement, []).append(report_path)

        for field in readiness["missingContextFields"]:
            add_count(missing_context_counts, field)
            report_indexes_by_missing_context.setdefault(field, []).append(report_index)
            report_paths_by_missing_context.setdefault(field, []).append(report_path)

        repeated_evidence = readiness["repeatedTimingEvidence"]
        insufficient_case_count = repeated_evidence[
            "insufficientRepeatedEvidenceCaseCount"
        ]
        if insufficient_case_count:
            insufficient_repeated_evidence_reports.append(report_index)
            total_insufficient_repeated_evidence_cases += insufficient_case_count

        total_required_skipped_cases += readiness[
            "requiredOrUnclassifiedSkippedCaseCount"
        ]
        total_skipped_cases_without_tools += readiness[
            "skippedCasesWithoutUnavailableToolCount"
        ]
        required_skipped_tool_labels.update(
            readiness["requiredOrUnclassifiedSkippedToolLabels"]
        )

    ready_count = readiness_status_counts.get("ready", 0)
    incomplete_count = readiness_status_counts.get("incomplete", 0)
    return {
        "advisory": True,
        "mode": "report-only",
        "policy": (
            "Aggregate threshold-baseline readiness summarizes deterministic "
            "curation blockers only. It never evaluates timing thresholds, never "
            "changes aggregate exit status, and should be used as promotion "
            "evidence rather than a CI timing gate."
        ),
        "minimumSampleCount": TIMING_ADVISORY_MIN_SAMPLE_COUNT,
        "reportCount": len(entries),
        "readyReportCount": ready_count,
        "incompleteReportCount": incomplete_count,
        "readinessStatusCounts": sorted_counts(readiness_status_counts),
        "reasonCountByReason": sorted_counts(reason_counts),
        "reportIndexesByReason": {
            reason: sorted(indexes)
            for reason, indexes in sorted(report_indexes_by_reason.items())
        },
        "reportPathsByReason": {
            reason: sorted(paths)
            for reason, paths in sorted(report_paths_by_reason.items())
        },
        "unsatisfiedRequirementCountByName": sorted_counts(requirement_counts),
        "reportIndexesByUnsatisfiedRequirement": {
            requirement: sorted(indexes)
            for requirement, indexes in sorted(report_indexes_by_requirement.items())
        },
        "reportPathsByUnsatisfiedRequirement": {
            requirement: sorted(paths)
            for requirement, paths in sorted(report_paths_by_requirement.items())
        },
        "missingContextFieldCountByField": sorted_counts(missing_context_counts),
        "reportIndexesByMissingContextField": {
            field: sorted(indexes)
            for field, indexes in sorted(report_indexes_by_missing_context.items())
        },
        "reportPathsByMissingContextField": {
            field: sorted(paths)
            for field, paths in sorted(report_paths_by_missing_context.items())
        },
        "insufficientRepeatedTimingEvidenceCaseCount": (
            total_insufficient_repeated_evidence_cases
        ),
        "insufficientRepeatedTimingEvidenceReportCount": len(
            insufficient_repeated_evidence_reports
        ),
        "insufficientRepeatedTimingEvidenceReports": sorted(
            insufficient_repeated_evidence_reports
        ),
        "requiredOrUnclassifiedSkippedCaseCount": total_required_skipped_cases,
        "requiredOrUnclassifiedSkippedToolLabels": sorted(required_skipped_tool_labels),
        "skippedCasesWithoutUnavailableToolCount": total_skipped_cases_without_tools,
    }


def aggregate_release_claim_requirement(
    name: str,
    *,
    satisfied: bool,
    reason_if_unsatisfied: str,
    observed: dict[str, Any],
) -> dict[str, Any]:
    return {
        "name": name,
        "observed": observed,
        "reasonIfUnsatisfied": reason_if_unsatisfied,
        "satisfied": satisfied,
    }


def aggregate_release_claim_group_report(
    baseline_group: dict[str, Any],
    case_stability_groups_by_key: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    stability_groups = [
        case_stability_groups_by_key[key]
        for key in baseline_group["caseStabilityGroupKeys"]
        if key in case_stability_groups_by_key
    ]
    insufficient_sample_cases = sorted(
        group["case"]
        for group in stability_groups
        if group["timing"]["sampleCount"]
        < TIMING_THRESHOLD_RELEASE_CLAIM_MIN_REPEATED_REPORTS
    )
    spread_exceeded_cases = sorted(
        group["case"]
        for group in stability_groups
        if timing_spread_exceeds_stability_recommendation(group["timing"])
    )
    ready_report_count = baseline_group["reportsReadyForThresholdBaseline"]
    report_count = baseline_group["reportCount"]
    validation_issue_count = baseline_group["validationIssueCount"]
    requirements = [
        aggregate_release_claim_requirement(
            "minimumRepeatedReadyReports",
            satisfied=(
                ready_report_count
                >= TIMING_THRESHOLD_RELEASE_CLAIM_MIN_REPEATED_REPORTS
            ),
            reason_if_unsatisfied="insufficientRepeatedReadyReports",
            observed={
                "minimumReadyReportCount": (
                    TIMING_THRESHOLD_RELEASE_CLAIM_MIN_REPEATED_REPORTS
                ),
                "readyReportCount": ready_report_count,
                "remainingReadyReports": max(
                    0,
                    TIMING_THRESHOLD_RELEASE_CLAIM_MIN_REPEATED_REPORTS
                    - ready_report_count,
                ),
            },
        ),
        aggregate_release_claim_requirement(
            "allReportsReadyForThresholdBaseline",
            satisfied=ready_report_count == report_count,
            reason_if_unsatisfied="incompleteThresholdBaselineReports",
            observed={
                "incompleteReportCount": baseline_group[
                    "reportsIncompleteForThresholdBaseline"
                ],
                "readyReportCount": ready_report_count,
                "reportCount": report_count,
            },
        ),
        aggregate_release_claim_requirement(
            "cleanAggregateValidation",
            satisfied=validation_issue_count == 0,
            reason_if_unsatisfied="aggregateValidationIssues",
            observed={"validationIssueCount": validation_issue_count},
        ),
        aggregate_release_claim_requirement(
            "timedCaseStabilityEvidence",
            satisfied=bool(stability_groups),
            reason_if_unsatisfied="noTimedCaseStabilityEvidence",
            observed={"caseStabilityGroupCount": len(stability_groups)},
        ),
        aggregate_release_claim_requirement(
            "releaseMinimumSamplesPerCase",
            satisfied=not insufficient_sample_cases,
            reason_if_unsatisfied="insufficientReleaseRepeatedSamples",
            observed={
                "minimumSampleCount": (
                    TIMING_THRESHOLD_RELEASE_CLAIM_MIN_REPEATED_REPORTS
                ),
                "insufficientSampleCaseCount": len(insufficient_sample_cases),
                "insufficientSampleCases": insufficient_sample_cases,
            },
        ),
        aggregate_release_claim_requirement(
            "recommendedTimingSpread",
            satisfied=not spread_exceeded_cases,
            reason_if_unsatisfied="unstableTimingSpread",
            observed={
                "recommendedMaxSpreadPercentOfMin": decimal_percent_value(
                    STABILITY_RECOMMENDED_MAX_SPREAD_PERCENT
                ),
                "spreadExceededCaseCount": len(spread_exceeded_cases),
                "spreadExceededCases": spread_exceeded_cases,
            },
        ),
    ]
    unsatisfied_requirements = [
        requirement["name"]
        for requirement in requirements
        if requirement["satisfied"] is not True
    ]
    reasons = [
        requirement["reasonIfUnsatisfied"]
        for requirement in requirements
        if requirement["satisfied"] is not True
    ]
    ready = not reasons
    return {
        "advisory": True,
        "baselineGroupKey": baseline_group["key"],
        "caseStabilityGroupCount": len(stability_groups),
        "dimensions": baseline_group["dimensions"],
        "mode": "report-only",
        "readyForReleaseClaimReview": ready,
        "readyReportCount": ready_report_count,
        "reasonCount": len(reasons),
        "reasons": reasons,
        "releaseClaimRepeatedReportMinimum": (
            TIMING_THRESHOLD_RELEASE_CLAIM_MIN_REPEATED_REPORTS
        ),
        "remainingReadyReportsForReleaseClaim": max(
            0,
            TIMING_THRESHOLD_RELEASE_CLAIM_MIN_REPEATED_REPORTS - ready_report_count,
        ),
        "reportCount": report_count,
        "reportIndexes": baseline_group["reportIndexes"],
        "reportPaths": baseline_group["reportPaths"],
        "requirementCount": len(requirements),
        "requirements": requirements,
        "satisfiedRequirementCount": len(requirements) - len(unsatisfied_requirements),
        "status": "ready" if ready else "incomplete",
        "unsatisfiedRequirementCount": len(unsatisfied_requirements),
        "unsatisfiedRequirements": unsatisfied_requirements,
        "validationIssueCount": validation_issue_count,
    }


def aggregate_release_claim_readiness_report(
    baseline_groups: list[dict[str, Any]],
    case_stability_groups_by_key: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    group_reports = [
        aggregate_release_claim_group_report(group, case_stability_groups_by_key)
        for group in baseline_groups
    ]
    reason_counts: dict[str, int] = {}
    requirement_counts: dict[str, int] = {}
    for group in group_reports:
        for reason in group["reasons"]:
            add_count(reason_counts, reason)
        for requirement in group["unsatisfiedRequirements"]:
            add_count(requirement_counts, requirement)

    ready_groups = [
        group for group in group_reports if group["readyForReleaseClaimReview"]
    ]
    if ready_groups and len(ready_groups) == len(group_reports):
        status = "ready"
    elif ready_groups:
        status = "partial"
    else:
        status = "incomplete"
    return {
        "advisory": True,
        "baselineGroupCount": len(group_reports),
        "baselineGroups": sorted(
            group_reports, key=lambda group: group["baselineGroupKey"]
        ),
        "incompleteBaselineGroupCount": len(group_reports) - len(ready_groups),
        "minimumSampleCount": TIMING_THRESHOLD_RELEASE_CLAIM_MIN_REPEATED_REPORTS,
        "mode": "report-only",
        "policy": (
            "Aggregate release-claim readiness summarizes whether repeated "
            "reports have enough complete, comparable, stable evidence for "
            "human review. It never promotes timing thresholds automatically, "
            "never changes aggregate exit status, and is not a CI timing gate."
        ),
        "readyBaselineGroupCount": len(ready_groups),
        "reasonCountByReason": sorted_counts(reason_counts),
        "releaseClaimPolicy": TIMING_THRESHOLD_RELEASE_CLAIM_POLICY,
        "releaseClaimRepeatedReportMinimum": (
            TIMING_THRESHOLD_RELEASE_CLAIM_MIN_REPEATED_REPORTS
        ),
        "status": status,
        "unsatisfiedRequirementCountByName": sorted_counts(requirement_counts),
    }


def timing_spread_exceeds_stability_recommendation(timing: dict[str, Any]) -> bool:
    if timing["sampleCount"] < STABILITY_MIN_SAMPLE_COUNT:
        return False
    spread_ns = timing["spreadNs"]
    if not isinstance(spread_ns, int) or spread_ns == 0:
        return False
    spread_percent = timing["spreadPercentOfMin"]
    if isinstance(spread_percent, bool) or not isinstance(spread_percent, (float, int)):
        return True
    return Decimal(str(spread_percent)) > STABILITY_RECOMMENDED_MAX_SPREAD_PERCENT


def timing_stability_disposition(
    timing: dict[str, Any], *, spread_exceeded: bool
) -> str:
    if timing["sampleCount"] < STABILITY_MIN_SAMPLE_COUNT:
        return "insufficient-samples"
    if timing["spreadNs"] == 0:
        return "identical"
    if spread_exceeded:
        return "exceeds-recommended-spread"
    return "within-recommended-spread"


def pairwise_baseline_stability_report(
    baseline_path: Path,
    candidate_path: Path,
    baseline_metadata: ReportPolicyMetadata,
    candidate_metadata: ReportPolicyMetadata,
    baseline_cases: dict[str, ReportCase],
    candidate_cases: dict[str, ReportCase],
    baseline_readiness: dict[str, Any],
    candidate_readiness: dict[str, Any],
    policy_metadata_comparison: dict[str, Any],
) -> dict[str, Any]:
    groups: list[dict[str, Any]] = []
    untimed_cases: list[str] = []
    dimension_mismatch_cases: list[dict[str, Any]] = []

    for key in sorted(set(baseline_cases) & set(candidate_cases)):
        baseline_case = baseline_cases[key]
        candidate_case = candidate_cases[key]
        if baseline_case.elapsed_ns is None or candidate_case.elapsed_ns is None:
            untimed_cases.append(key)
            continue

        samples = [
            {
                "case": key,
                "elapsedNs": baseline_case.elapsed_ns,
                "reportPath": baseline_path.as_posix(),
                "reportRole": "baseline",
            },
            {
                "case": key,
                "elapsedNs": candidate_case.elapsed_ns,
                "reportPath": candidate_path.as_posix(),
                "reportRole": "candidate",
            },
        ]
        timing = aggregate_timing_summary(samples)
        spread_exceeded = timing_spread_exceeds_stability_recommendation(timing)
        baseline_dimensions = aggregate_case_stability_dimensions(
            baseline_metadata, baseline_case
        )
        candidate_dimensions = aggregate_case_stability_dimensions(
            candidate_metadata, candidate_case
        )
        dimension_mismatches = compare_mapping_values(
            baseline_dimensions, candidate_dimensions
        )
        if dimension_mismatches:
            dimension_mismatch_cases.append(
                {
                    "case": key,
                    "mismatches": dimension_mismatches,
                }
            )

        groups.append(
            {
                "baselineDimensions": baseline_dimensions,
                "baselineNs": baseline_case.elapsed_ns,
                "candidateNs": candidate_case.elapsed_ns,
                "candidateDimensions": candidate_dimensions,
                "case": key,
                "dimensionsMatch": not dimension_mismatches,
                "dimensionMismatches": dimension_mismatches,
                "recommendedMaxSpreadPercentOfMin": decimal_percent_value(
                    STABILITY_RECOMMENDED_MAX_SPREAD_PERCENT
                ),
                "recommendedSpreadExceeded": spread_exceeded,
                "stabilityClass": timing_stability_class(timing),
                "stabilityDisposition": timing_stability_disposition(
                    timing, spread_exceeded=spread_exceeded
                ),
                "timing": timing,
            }
        )

    stability_summary = aggregate_stability_summary(groups)
    spread_exceeded_cases = [
        group["case"] for group in groups if group["recommendedSpreadExceeded"]
    ]
    compatible_ready_pair = (
        baseline_readiness["readyForThresholdBaseline"]
        and candidate_readiness["readyForThresholdBaseline"]
        and policy_metadata_comparison["compatible"]
    )
    requirements = [
        threshold_baseline_requirement(
            "compatibleReadyPair",
            satisfied=compatible_ready_pair,
            reason_if_unsatisfied="incompatibleOrIncompleteReports",
            observed={
                "baselineReadyForThresholdBaseline": baseline_readiness[
                    "readyForThresholdBaseline"
                ],
                "candidateReadyForThresholdBaseline": candidate_readiness[
                    "readyForThresholdBaseline"
                ],
                "metadataCompatible": policy_metadata_comparison["compatible"],
                "metadataMismatchCount": policy_metadata_comparison["mismatchCount"],
            },
        ),
        threshold_baseline_requirement(
            "comparableTimedCases",
            satisfied=bool(groups),
            reason_if_unsatisfied="noComparableTimedCases",
            observed={
                "comparableTimedCaseCount": len(groups),
                "untimedComparableCaseCount": len(untimed_cases),
            },
        ),
        threshold_baseline_requirement(
            "matchingStabilityDimensions",
            satisfied=not dimension_mismatch_cases,
            reason_if_unsatisfied="stabilityDimensionMismatches",
            observed={
                "dimensionMismatchCaseCount": len(dimension_mismatch_cases),
                "dimensionMismatchCases": dimension_mismatch_cases,
            },
        ),
        threshold_baseline_requirement(
            "recommendedTimingSpread",
            satisfied=not spread_exceeded_cases,
            reason_if_unsatisfied="unstableTimingSpread",
            observed={
                "recommendedMaxSpreadPercentOfMin": decimal_percent_value(
                    STABILITY_RECOMMENDED_MAX_SPREAD_PERCENT
                ),
                "spreadExceededCaseCount": len(spread_exceeded_cases),
                "spreadExceededCases": spread_exceeded_cases,
                "maxSpreadPercentOfMin": stability_summary["maxSpreadPercentOfMin"],
            },
        ),
    ]
    unsatisfied_requirements = [
        requirement["name"]
        for requirement in requirements
        if not requirement["satisfied"]
    ]
    reasons = [
        requirement["reasonIfUnsatisfied"]
        for requirement in requirements
        if not requirement["satisfied"]
    ]
    stable_enough = not reasons

    return {
        "advisory": True,
        "mode": "report-only",
        "stableEnoughForThresholdBaseline": stable_enough,
        "status": "stable"
        if stable_enough
        else ("unstable" if spread_exceeded_cases else "incomplete"),
        "reasonCount": len(reasons),
        "reasons": reasons,
        "policy": (
            "Pairwise stability is advisory curation evidence for future timing "
            "threshold baselines. It never changes comparator exit status."
        ),
        "unit": "elapsedNs",
        "minimumSampleCount": STABILITY_MIN_SAMPLE_COUNT,
        "recommendedMaxSpreadPercentOfMin": decimal_percent_value(
            STABILITY_RECOMMENDED_MAX_SPREAD_PERCENT
        ),
        "satisfiedStabilityRequirementCount": (
            len(requirements) - len(unsatisfied_requirements)
        ),
        "stabilityRequirementCount": len(requirements),
        "stabilityRequirements": requirements,
        "unsatisfiedStabilityRequirementCount": len(unsatisfied_requirements),
        "unsatisfiedStabilityRequirements": unsatisfied_requirements,
        "context": {
            "baseline": readiness_context_report(baseline_metadata, baseline_cases),
            "candidate": readiness_context_report(candidate_metadata, candidate_cases),
        },
        "caseStabilityGroups": groups,
        "dimensionMismatchCaseCount": len(dimension_mismatch_cases),
        "dimensionMismatchCases": dimension_mismatch_cases,
        "recommendedSpreadExceededCaseCount": len(spread_exceeded_cases),
        "recommendedSpreadExceededCases": spread_exceeded_cases,
        "untimedComparableCaseCount": len(untimed_cases),
        "untimedComparableCases": untimed_cases,
        **stability_summary,
    }


def aggregate_reports(report_paths: list[Path]) -> dict[str, Any]:
    entries: list[dict[str, Any]] = []
    all_categories: set[str] = set()
    all_command_profiles: set[str] = set()
    all_opt_levels: set[str] = set()
    all_profiles: set[str] = set()
    all_targets: set[str] = set()
    skipped_tool_counts: dict[str, int] = {}
    skipped_tool_cases: dict[str, list[dict[str, Any]]] = {}

    for report_index, path in enumerate(report_paths):
        report = load_json_report(path)
        case_validation_issues: list[str] = []
        cases = report_cases(
            report,
            f"reports[{report_index}]",
            validation_issues=case_validation_issues,
        )
        metadata = report_policy_metadata(report, cases)
        validation_issues = report_validation_issues(
            report, cases, f"reports[{report_index}]"
        )
        validation_issues = case_validation_issues + validation_issues
        categories = sorted({case.category for case in cases.values()})
        command_profiles = sorted(report_command_profiles(report, cases))
        opt_levels = sorted(
            {case.opt_level for case in cases.values() if case.opt_level}
            | {
                value
                for value in (metadata.fields.get("optLevel"),)
                if isinstance(value, str) and value
            }
        )
        profiles = sorted(report_profiles(report, cases))
        targets = sorted(report_targets(report, cases))
        all_categories.update(categories)
        all_command_profiles.update(command_profiles)
        all_opt_levels.update(opt_levels)
        all_profiles.update(profiles)
        all_targets.update(targets)

        for tool, case_keys in metadata.skipped_tool_accounting[
            "skippedToolCasesByTool"
        ].items():
            add_count(skipped_tool_counts, tool, len(case_keys))
            skipped_tool_cases.setdefault(tool, []).extend(
                {
                    "case": case_key,
                    "reportIndex": report_index,
                    "reportPath": path.as_posix(),
                }
                for case_key in case_keys
            )

        entries.append(
            {
                "cases": cases,
                "categories": categories,
                "commandProfiles": command_profiles,
                "metadata": metadata,
                "optLevels": opt_levels,
                "path": path,
                "profiles": profiles,
                "readiness": baseline_readiness_report(
                    metadata, cases, validation_issues
                ),
                "report": report,
                "reportIndex": report_index,
                "targets": targets,
                "validationIssues": validation_issues,
            }
        )

    baseline_groups: dict[str, dict[str, Any]] = {}
    dimension_groups: dict[str, dict[str, Any]] = {}
    case_stability_groups: dict[str, dict[str, Any]] = {}
    report_summaries: list[dict[str, Any]] = []

    expected_categories = sorted(all_categories)
    expected_command_profiles = sorted(all_command_profiles)
    expected_opt_levels = sorted(all_opt_levels)
    expected_profiles = sorted(all_profiles)
    expected_targets = sorted(all_targets)
    aggregate_native_optimization = native_optimization_case_accounting(
        case for entry in entries for case in entry["cases"].values()
    )

    for entry in entries:
        metadata = entry["metadata"]
        report_index = entry["reportIndex"]
        path = entry["path"]
        cases = entry["cases"]
        baseline_dimensions = aggregate_baseline_dimensions(metadata)
        baseline_toolchains = toolchain_dimension(metadata)
        baseline_key = stable_group_key(baseline_dimensions)
        baseline_group = baseline_groups.setdefault(
            baseline_key,
            {
                "caseCount": 0,
                "caseCountByNativeArtifactDescriptorOptimizationEvidenceStatus": {},
                "caseCountByNativeArtifactDescriptorOptimizationStatus": {},
                "caseCountByNativeOptimizationEvidenceStatus": {},
                "caseCountByNativeOptimizationStatus": {},
                "dimensions": baseline_dimensions,
                "key": baseline_key,
                "caseStabilityGroupKeys": set(),
                "missingContextFields": set(),
                "reportCount": 0,
                "reportIndexes": [],
                "reportPaths": [],
                "readinessReasonCountByReason": {},
                "reportsReadyForThresholdBaseline": 0,
                "reportsIncompleteForThresholdBaseline": 0,
                "skippedCaseCount": 0,
                "timedCaseCount": 0,
                "toolchainClassifications": baseline_toolchains["classifications"],
                "toolchains": baseline_toolchains["toolchains"],
                "unsatisfiedReadinessRequirementCountByName": {},
                "validationIssueCount": 0,
            },
        )
        baseline_group["caseCount"] += len(cases)
        baseline_group["reportCount"] += 1
        baseline_group["reportIndexes"].append(report_index)
        baseline_group["reportPaths"].append(path.as_posix())
        baseline_group["skippedCaseCount"] += len(skipped_cases(cases))
        baseline_group["timedCaseCount"] += sum(
            1 for case in cases.values() if case.elapsed_ns is not None
        )
        baseline_group["validationIssueCount"] += len(entry["validationIssues"])
        baseline_group["missingContextFields"].update(
            policy_context_report(metadata)["missingFields"]
        )
        if entry["readiness"]["readyForThresholdBaseline"]:
            baseline_group["reportsReadyForThresholdBaseline"] += 1
        else:
            baseline_group["reportsIncompleteForThresholdBaseline"] += 1
        for reason in entry["readiness"]["reasons"]:
            add_count(baseline_group["readinessReasonCountByReason"], reason)
        for requirement in entry["readiness"][
            "unsatisfiedThresholdBaselineRequirements"
        ]:
            add_count(
                baseline_group["unsatisfiedReadinessRequirementCountByName"],
                requirement,
            )

        report_summaries.append(
            {
                **report_summary(path, entry["report"], cases),
                "baselineGroupKey": baseline_key,
                "baselineReadiness": entry["readiness"],
                "missingCategories": sorted(
                    set(expected_categories) - set(entry["categories"])
                ),
                "missingCommandProfiles": sorted(
                    set(expected_command_profiles) - set(entry["commandProfiles"])
                ),
                "missingOptLevels": sorted(
                    set(expected_opt_levels) - set(entry["optLevels"])
                ),
                "missingProfiles": sorted(
                    set(expected_profiles) - set(entry["profiles"])
                ),
                "missingTargets": sorted(set(expected_targets) - set(entry["targets"])),
                "validationIssueCount": len(entry["validationIssues"]),
                "validationIssues": entry["validationIssues"],
            }
        )

        for case in cases.values():
            dimensions = aggregate_case_dimensions(metadata, case)
            key = stable_group_key(dimensions)
            group = dimension_groups.setdefault(
                key,
                {
                    "caseCount": 0,
                    "caseCountByNativeArtifactDescriptorOptimizationEvidenceStatus": {},
                    "caseCountByNativeArtifactDescriptorOptimizationStatus": {},
                    "caseCountByNativeOptimizationEvidenceStatus": {},
                    "caseCountByNativeOptimizationStatus": {},
                    "caseKeys": set(),
                    "dimensions": dimensions,
                    "functionalFailureCaseCount": 0,
                    "key": key,
                    "reportCount": 0,
                    "reportIndexes": set(),
                    "skippedCaseCount": 0,
                    "skippedToolCaseCountByTool": {},
                    "timedCaseCount": 0,
                    "timingSamples": [],
                    "unavailableToolLabels": set(),
                },
            )
            group["caseCount"] += 1
            add_count(
                baseline_group[
                    "caseCountByNativeArtifactDescriptorOptimizationEvidenceStatus"
                ],
                case.native_artifact_descriptor_optimization_evidence_status,
            )
            add_count(
                group["caseCountByNativeArtifactDescriptorOptimizationEvidenceStatus"],
                case.native_artifact_descriptor_optimization_evidence_status,
            )
            if case.native_artifact_descriptor_optimization_status is not None:
                add_count(
                    baseline_group[
                        "caseCountByNativeArtifactDescriptorOptimizationStatus"
                    ],
                    case.native_artifact_descriptor_optimization_status,
                )
                add_count(
                    group["caseCountByNativeArtifactDescriptorOptimizationStatus"],
                    case.native_artifact_descriptor_optimization_status,
                )
            add_count(
                baseline_group["caseCountByNativeOptimizationEvidenceStatus"],
                case.native_optimization_evidence_status,
            )
            add_count(
                group["caseCountByNativeOptimizationEvidenceStatus"],
                case.native_optimization_evidence_status,
            )
            if case.native_optimization_status is not None:
                add_count(
                    baseline_group["caseCountByNativeOptimizationStatus"],
                    case.native_optimization_status,
                )
                add_count(
                    group["caseCountByNativeOptimizationStatus"],
                    case.native_optimization_status,
                )
            group["caseKeys"].add(case.key)
            group["reportIndexes"].add(report_index)
            group["reportCount"] = len(group["reportIndexes"])
            if case_functional_failure(
                {"success": case.success, "status": case.status}
            ):
                group["functionalFailureCaseCount"] += 1
            if case.skipped:
                group["skippedCaseCount"] += 1
                for tool in case.unavailable_tools:
                    add_count(group["skippedToolCaseCountByTool"], tool)
            if case.elapsed_ns is not None:
                group["timedCaseCount"] += 1
                group["timingSamples"].append(timing_sample(case, report_index, path))
            group["unavailableToolLabels"].update(case.unavailable_tools)

            if case.elapsed_ns is not None:
                stability_dimensions = aggregate_case_stability_dimensions(
                    metadata, case
                )
                stability_key = stable_group_key(stability_dimensions)
                baseline_group["caseStabilityGroupKeys"].add(stability_key)
                stability_group = case_stability_groups.setdefault(
                    stability_key,
                    {
                        "case": case.key,
                        "dimensions": stability_dimensions,
                        "key": stability_key,
                        "readyReportCount": 0,
                        "reportIndexes": set(),
                        "reportPaths": set(),
                        "reportsWithValidationIssues": set(),
                        "timingSamples": [],
                    },
                )
                stability_group["reportIndexes"].add(report_index)
                stability_group["reportPaths"].add(path.as_posix())
                if entry["readiness"]["readyForThresholdBaseline"]:
                    stability_group["readyReportCount"] += 1
                if entry["validationIssues"]:
                    stability_group["reportsWithValidationIssues"].add(report_index)
                stability_group["timingSamples"].append(
                    stability_timing_sample(
                        case,
                        report_index,
                        path,
                        entry["readiness"],
                    )
                )

    normalized_case_stability_groups = []
    for group in case_stability_groups.values():
        timing_samples = sorted(
            group["timingSamples"],
            key=lambda sample: (
                sample["reportPath"],
                sample["case"],
                sample.get("elapsedNs") or -1,
            ),
        )
        timing = aggregate_timing_summary(timing_samples)
        normalized_case_stability_groups.append(
            {
                **group,
                "reportCount": len(group["reportIndexes"]),
                "reportIndexes": sorted(group["reportIndexes"]),
                "reportPaths": sorted(group["reportPaths"]),
                "reportsWithValidationIssues": sorted(
                    group["reportsWithValidationIssues"]
                ),
                "stabilityClass": timing_stability_class(timing),
                "timing": timing,
                "timingSamples": timing_samples,
            }
        )
    case_stability_groups_by_key = {
        group["key"]: group for group in normalized_case_stability_groups
    }

    normalized_baseline_groups = []
    for group in baseline_groups.values():
        case_stability_group_keys = sorted(group["caseStabilityGroupKeys"])
        group_stability = [
            case_stability_groups_by_key[key]
            for key in case_stability_group_keys
            if key in case_stability_groups_by_key
        ]
        normalized_baseline_groups.append(
            {
                **group,
                "caseStabilityGroupKeys": case_stability_group_keys,
                "caseCountByNativeArtifactDescriptorOptimizationEvidenceStatus": (
                    sorted_counts(
                        group[
                            "caseCountByNativeArtifactDescriptorOptimizationEvidenceStatus"
                        ]
                    )
                ),
                "caseCountByNativeArtifactDescriptorOptimizationStatus": (
                    sorted_counts(
                        group["caseCountByNativeArtifactDescriptorOptimizationStatus"]
                    )
                ),
                "caseCountByNativeOptimizationEvidenceStatus": sorted_counts(
                    group["caseCountByNativeOptimizationEvidenceStatus"]
                ),
                "caseCountByNativeOptimizationStatus": sorted_counts(
                    group["caseCountByNativeOptimizationStatus"]
                ),
                "missingContextFields": sorted(group["missingContextFields"]),
                "nativeArtifactDescriptorOptimizationStatuses": sorted(
                    group["caseCountByNativeArtifactDescriptorOptimizationStatus"]
                ),
                "nativeOptimizationStatuses": sorted(
                    group["caseCountByNativeOptimizationStatus"]
                ),
                "readinessReasonCountByReason": sorted_counts(
                    group["readinessReasonCountByReason"]
                ),
                "timingStability": aggregate_stability_summary(group_stability),
                "unsatisfiedReadinessRequirementCountByName": sorted_counts(
                    group["unsatisfiedReadinessRequirementCountByName"]
                ),
            }
        )

    normalized_dimension_groups = []
    for group in dimension_groups.values():
        timing_samples = sorted(
            group["timingSamples"],
            key=lambda sample: (
                sample["reportPath"],
                sample["case"],
                sample.get("elapsedNs") or -1,
            ),
        )
        normalized_dimension_groups.append(
            {
                **group,
                "caseKeys": sorted(group["caseKeys"]),
                "caseCountByNativeArtifactDescriptorOptimizationEvidenceStatus": (
                    sorted_counts(
                        group[
                            "caseCountByNativeArtifactDescriptorOptimizationEvidenceStatus"
                        ]
                    )
                ),
                "caseCountByNativeArtifactDescriptorOptimizationStatus": (
                    sorted_counts(
                        group["caseCountByNativeArtifactDescriptorOptimizationStatus"]
                    )
                ),
                "caseCountByNativeOptimizationEvidenceStatus": sorted_counts(
                    group["caseCountByNativeOptimizationEvidenceStatus"]
                ),
                "caseCountByNativeOptimizationStatus": sorted_counts(
                    group["caseCountByNativeOptimizationStatus"]
                ),
                "nativeOptimizationStatuses": sorted(
                    group["caseCountByNativeOptimizationStatus"]
                ),
                "nativeArtifactDescriptorOptimizationStatuses": sorted(
                    group["caseCountByNativeArtifactDescriptorOptimizationStatus"]
                ),
                "reportIndexes": sorted(group["reportIndexes"]),
                "skippedToolCaseCountByTool": sorted_counts(
                    group["skippedToolCaseCountByTool"]
                ),
                "timing": aggregate_timing_summary(timing_samples),
                "timingSamples": timing_samples,
                "unavailableToolLabels": sorted(group["unavailableToolLabels"]),
            }
        )

    validation_issue_count = sum(len(entry["validationIssues"]) for entry in entries)
    reports_with_validation_issues = [
        entry["reportIndex"] for entry in entries if entry["validationIssues"]
    ]
    threshold_baseline_readiness = aggregate_readiness_report(entries)
    threshold_release_claim_readiness = aggregate_release_claim_readiness_report(
        normalized_baseline_groups,
        case_stability_groups_by_key,
    )
    return {
        "schemaVersion": SCHEMA_VERSION,
        "tool": TOOL_NAME,
        "mode": "aggregate",
        "status": "pass",
        "policy": {
            "mode": "report-only",
            "timingThresholdsEvaluated": False,
            "exitStatusPolicy": (
                "Aggregation validates and summarizes readable reports, but does "
                "not apply timing thresholds or convert timing deltas into CI "
                "failures."
            ),
        },
        "summary": {
            "baselineGroupCount": len(baseline_groups),
            "caseCountByNativeArtifactDescriptorOptimizationEvidenceStatus": (
                aggregate_native_optimization[
                    "caseCountByNativeArtifactDescriptorEvidenceStatus"
                ]
            ),
            "caseCountByNativeArtifactDescriptorOptimizationStatus": (
                aggregate_native_optimization[
                    "caseCountByNativeArtifactDescriptorStatus"
                ]
            ),
            "caseCountByNativeOptimizationEvidenceStatus": (
                aggregate_native_optimization["caseCountByEvidenceStatus"]
            ),
            "caseCountByNativeOptimizationStatus": aggregate_native_optimization[
                "caseCountByStatus"
            ],
            "caseDimensionGroupCount": len(dimension_groups),
            "caseStabilityGroupCount": len(case_stability_groups),
            "multiSampleCaseStabilityGroupCount": aggregate_stability_summary(
                normalized_case_stability_groups
            )["multiSampleCaseStabilityGroupCount"],
            "nativeOptimizationEvidence": aggregate_native_optimization[
                "nativeOptimizationEvidence"
            ],
            "nativeArtifactDescriptorOptimizationEvidence": (
                aggregate_native_optimization[
                    "nativeArtifactDescriptorOptimizationEvidence"
                ]
            ),
            "nativeArtifactDescriptorOptimizationStatusCount": (
                aggregate_native_optimization[
                    "nativeArtifactDescriptorOptimizationStatusCaseCount"
                ]
            ),
            "nativeArtifactDescriptorOptimizationStatuses": (
                aggregate_native_optimization[
                    "nativeArtifactDescriptorOptimizationStatuses"
                ]
            ),
            "nativeOptimizationStatusCount": aggregate_native_optimization[
                "nativeOptimizationStatusCaseCount"
            ],
            "nativeOptimizationStatuses": aggregate_native_optimization[
                "nativeOptimizationStatuses"
            ],
            "reportCount": len(entries),
            "reportsIncompleteForThresholdBaselineCount": (
                threshold_baseline_readiness["incompleteReportCount"]
            ),
            "reportsReadyForThresholdBaselineCount": sum(
                1
                for entry in entries
                if entry["readiness"]["readyForThresholdBaseline"]
            ),
            "reportsWithValidationIssueCount": len(reports_with_validation_issues),
            "skippedToolCaseCountByTool": sorted_counts(skipped_tool_counts),
            "thresholdBaselineReadinessReasonCountByReason": (
                threshold_baseline_readiness["reasonCountByReason"]
            ),
            "thresholdBaselineUnsatisfiedRequirementCountByName": (
                threshold_baseline_readiness["unsatisfiedRequirementCountByName"]
            ),
            "thresholdReleaseClaimReadyBaselineGroupCount": (
                threshold_release_claim_readiness["readyBaselineGroupCount"]
            ),
            "thresholdReleaseClaimIncompleteBaselineGroupCount": (
                threshold_release_claim_readiness["incompleteBaselineGroupCount"]
            ),
            "validationIssueCount": validation_issue_count,
        },
        "thresholdBaselineReadiness": threshold_baseline_readiness,
        "thresholdReleaseClaimReadiness": threshold_release_claim_readiness,
        "baselineStability": {
            "advisory": True,
            "mode": "report-only",
            "policy": (
                "Aggregate stability evidence summarizes repeated timed samples "
                "for the same normalized case and baseline dimensions. It is "
                "advisory inventory only; timing variance never changes aggregate "
                "exit status and does not create CI timing failures."
            ),
            "unit": "elapsedNs",
            **aggregate_stability_summary(normalized_case_stability_groups),
        },
        "coverage": {
            "categories": expected_categories,
            "commandProfiles": expected_command_profiles,
            "optLevels": expected_opt_levels,
            "profiles": expected_profiles,
            "targets": expected_targets,
            "nativeArtifactDescriptorOptimizationEvidenceStatuses": sorted(
                aggregate_native_optimization[
                    "caseCountByNativeArtifactDescriptorEvidenceStatus"
                ]
            ),
            "nativeArtifactDescriptorOptimizationStatuses": (
                aggregate_native_optimization[
                    "nativeArtifactDescriptorOptimizationStatuses"
                ]
            ),
            "nativeOptimizationEvidenceStatuses": sorted(
                aggregate_native_optimization["caseCountByEvidenceStatus"]
            ),
            "nativeOptimizationStatuses": aggregate_native_optimization[
                "nativeOptimizationStatuses"
            ],
        },
        "nativeOptimization": {
            "advisory": True,
            "mode": "report-only",
            "policy": (
                "Aggregate native optimization status and evidence coverage are "
                "report-only inventory. They never change aggregate exit status."
            ),
            "reportCount": len(entries),
            "reportsWithKnownStatusCount": sum(
                1
                for entry in entries
                if any(
                    case.native_optimization_status is not None
                    for case in entry["cases"].values()
                )
            ),
            "reportsWithNativeProfileEvidenceCount": sum(
                1
                for entry in entries
                if any(
                    case.native_optimization_evidence_status
                    != "native-profile-not-declared"
                    for case in entry["cases"].values()
                )
            ),
            "reportsWithNativeArtifactDescriptorEvidenceCount": sum(
                1
                for entry in entries
                if any(
                    case.native_artifact_descriptor_optimization_evidence_status
                    != "native-artifact-descriptor-not-declared"
                    for case in entry["cases"].values()
                )
            ),
            "reportsWithNativeArtifactDescriptorKnownStatusCount": sum(
                1
                for entry in entries
                if any(
                    case.native_artifact_descriptor_optimization_status is not None
                    for case in entry["cases"].values()
                )
            ),
            **aggregate_native_optimization,
        },
        "validation": {
            "issueCount": validation_issue_count,
            "reportsWithIssues": reports_with_validation_issues,
        },
        "baselineGroups": sorted(
            normalized_baseline_groups, key=lambda group: group["key"]
        ),
        "caseDimensionGroups": sorted(
            normalized_dimension_groups, key=lambda group: group["key"]
        ),
        "caseStabilityGroups": sorted(
            normalized_case_stability_groups, key=lambda group: group["key"]
        ),
        "reports": sorted(report_summaries, key=lambda report: report["path"]),
        "skippedToolAccounting": {
            "skippedToolCaseCountByTool": sorted_counts(skipped_tool_counts),
            "skippedToolCasesByTool": {
                tool: sorted(
                    cases,
                    key=lambda item: (item["reportPath"], item["case"]),
                )
                for tool, cases in sorted(skipped_tool_cases.items())
            },
        },
    }


def parse_nonnegative_decimal(value: str) -> Decimal:
    try:
        parsed = Decimal(value)
    except InvalidOperation as exc:
        raise argparse.ArgumentTypeError(f"invalid decimal value: {value!r}") from exc
    if not parsed.is_finite() or parsed < 0:
        raise argparse.ArgumentTypeError("value must be a non-negative finite number")
    return parsed


def regression_percent(baseline_ns: int, candidate_ns: int) -> float | None:
    if baseline_ns <= 0:
        return None
    return float(
        ((Decimal(candidate_ns) - Decimal(baseline_ns)) / Decimal(baseline_ns))
        * Decimal(100)
    )


def rounded_ratio(baseline_ns: int, candidate_ns: int) -> float | None:
    if baseline_ns <= 0:
        return None
    return round(float(Decimal(candidate_ns) / Decimal(baseline_ns)), 6)


def decimal_percent_value(value: Decimal) -> float | int:
    if value == value.to_integral_value():
        return int(value)
    return float(value)


def threshold_enforcement_json() -> dict[str, Any]:
    return {
        "enforced": False,
        "exitStatusAffected": False,
        "failureMode": "report-only",
        "hardFail": False,
        "mode": "report-only",
        "policy": TIMING_THRESHOLD_ENFORCEMENT_POLICY,
        "releaseBlocker": False,
        "releaseBlockerPolicy": TIMING_ADVISORY_RELEASE_BLOCKER_POLICY,
    }


def threshold_limit(
    baseline_ns: int, max_regression_percent: Decimal
) -> tuple[int, str]:
    exact = Decimal(baseline_ns) * (
        Decimal(1) + (max_regression_percent / Decimal(100))
    )
    return int(exact.to_integral_value(rounding=ROUND_CEILING)), str(exact)


def threshold_delta_report(entry: dict[str, Any], allowed_ns: int) -> dict[str, Any]:
    threshold_delta_ns = entry["candidateNs"] - allowed_ns
    return {
        "baselineNs": entry["baselineNs"],
        "candidateNs": entry["candidateNs"],
        "deltaNs": entry["deltaNs"],
        "regressionPercent": entry["regressionPercent"],
        "thresholdDeltaNs": threshold_delta_ns,
        "thresholdDeltaPercentOfAllowed": regression_percent(
            allowed_ns, entry["candidateNs"]
        ),
        "thresholdExcessNs": max(0, threshold_delta_ns),
        "thresholdHeadroomNs": max(0, -threshold_delta_ns),
    }


def threshold_rule_json(rule: AdvisoryThresholdRule) -> dict[str, Any]:
    payload = {
        "category": rule.category,
        "label": rule.label,
        "maxRegressionPercent": decimal_percent_value(rule.max_regression_percent),
        "profile": rule.profile,
        "ruleSpecificity": threshold_rule_specificity(rule),
    }
    if rule.target != "*":
        payload["target"] = rule.target
    if rule.backend != "*":
        payload["backend"] = rule.backend
    return payload


def threshold_rule_specificity_from_labels(
    category: str,
    profile: str,
    target: str = "*",
    backend: str = "*",
) -> str:
    dimensions = [
        name
        for name, value in (
            ("category", category),
            ("profile", profile),
            ("target", target),
            ("backend", backend),
        )
        if value != "*"
    ]
    if len(dimensions) == 1:
        return f"{dimensions[0]}-only"
    if dimensions:
        return "-".join(dimensions)
    return "fallback"


def threshold_rule_specificity(rule: AdvisoryThresholdRule) -> str:
    return threshold_rule_specificity_from_labels(
        rule.category,
        rule.profile,
        rule.target,
        rule.backend,
    )


def advisory_threshold_policy_json(
    profile: AdvisoryThresholdProfile,
) -> dict[str, Any]:
    return {
        "schemaVersion": ADVISORY_THRESHOLD_POLICY_SCHEMA_VERSION,
        "tool": TOOL_NAME,
        "kind": ADVISORY_THRESHOLD_POLICY_KIND,
        "mode": "report-only",
        "name": profile.name,
        "description": profile.description,
        "evidencePolicy": {
            "metadataComparabilityPolicy": (
                TIMING_ADVISORY_METADATA_COMPARABILITY_POLICY
            ),
            "minimumSampleCount": TIMING_ADVISORY_MIN_SAMPLE_COUNT,
            "policy": TIMING_ADVISORY_EVIDENCE_POLICY,
            "requiresComparableMetadata": True,
            "requiresExplicitTimedCaseIdentity": True,
            "requiresRepeatedBaselineAndCandidateSamples": True,
        },
        "enforcement": threshold_enforcement_json(),
        "failurePolicy": ADVISORY_THRESHOLD_FAILURE_POLICY,
        "releaseBlockerPolicy": TIMING_ADVISORY_RELEASE_BLOCKER_POLICY,
        "ruleCount": len(profile.rules),
        "rules": [threshold_rule_json(rule) for rule in profile.rules],
    }


def advisory_threshold_policy_payload(payload: dict[str, Any]) -> dict[str, Any]:
    if "rules" in payload:
        return payload

    timing = payload.get("timing")
    if isinstance(timing, dict):
        thresholds = timing.get("advisoryThresholds")
        if isinstance(thresholds, dict):
            policy = thresholds.get("policy")
            if isinstance(policy, dict) and "rules" in policy:
                return policy

        profile = timing.get("advisoryThresholdProfile")
        if isinstance(profile, dict) and "rules" in profile:
            return profile

    raise PerformanceReportComparisonError(
        "malformed advisory threshold policy: expected an object with a rules array"
    )


def decimal_policy_value(value: Any, path: str) -> Decimal:
    if isinstance(value, bool):
        raise PerformanceReportComparisonError(
            f"malformed advisory threshold policy: {path} must be numeric"
        )
    if not isinstance(value, (int, float, str)):
        raise PerformanceReportComparisonError(
            f"malformed advisory threshold policy: {path} must be numeric"
        )
    try:
        parsed = Decimal(str(value))
    except InvalidOperation as exc:
        raise PerformanceReportComparisonError(
            f"malformed advisory threshold policy: {path} must be numeric"
        ) from exc
    if not parsed.is_finite() or parsed < 0:
        raise PerformanceReportComparisonError(
            f"malformed advisory threshold policy: {path} must be non-negative"
        )
    return parsed


def require_policy_string_field(
    payload: dict[str, Any],
    field: str,
    path: str,
    *,
    expected: str | None = None,
    expected_label: str | None = None,
) -> str:
    field_path = f"{path}.{field}" if path else field
    if field not in payload:
        raise PerformanceReportComparisonError(
            f"malformed advisory threshold policy: {field_path} is required"
        )
    value = string_value(payload.get(field))
    if value is None:
        raise PerformanceReportComparisonError(
            f"malformed advisory threshold policy: {field_path} must be "
            "a non-empty string"
        )
    if expected is not None and value != expected:
        label = expected_label or repr(expected)
        raise PerformanceReportComparisonError(
            f"malformed advisory threshold policy: {field_path} must match {label}"
        )
    return value


def validate_threshold_enforcement_payload(value: Any, path: str) -> None:
    if not isinstance(value, dict):
        raise PerformanceReportComparisonError(
            f"malformed advisory threshold policy: {path} must be an object"
        )

    expected = {
        "enforced": False,
        "exitStatusAffected": False,
        "failureMode": "report-only",
        "hardFail": False,
        "mode": "report-only",
        "releaseBlocker": False,
    }
    for field, expected_value in expected.items():
        if field not in value:
            raise PerformanceReportComparisonError(
                f"malformed advisory threshold policy: {path}.{field} is required"
            )
        if value[field] != expected_value:
            raise PerformanceReportComparisonError(
                f"malformed advisory threshold policy: {path}.{field} must be "
                f"{expected_value!r}"
            )

    require_policy_string_field(
        value,
        "policy",
        path,
        expected=TIMING_THRESHOLD_ENFORCEMENT_POLICY,
        expected_label="the comparator report-only enforcement policy",
    )
    require_policy_string_field(
        value,
        "releaseBlockerPolicy",
        path,
        expected=TIMING_ADVISORY_RELEASE_BLOCKER_POLICY,
        expected_label="the comparator report-only release blocker policy",
    )


def validate_threshold_evidence_policy_payload(value: Any, path: str) -> None:
    if not isinstance(value, dict):
        raise PerformanceReportComparisonError(
            f"malformed advisory threshold policy: {path} must be an object"
        )

    expected = {
        "minimumSampleCount": TIMING_ADVISORY_MIN_SAMPLE_COUNT,
        "requiresComparableMetadata": True,
        "requiresExplicitTimedCaseIdentity": True,
        "requiresRepeatedBaselineAndCandidateSamples": True,
    }
    for field, expected_value in expected.items():
        if field not in value:
            raise PerformanceReportComparisonError(
                f"malformed advisory threshold policy: {path}.{field} is required"
            )
        if value[field] != expected_value:
            raise PerformanceReportComparisonError(
                f"malformed advisory threshold policy: {path}.{field} must be "
                f"{expected_value!r}"
            )

    require_policy_string_field(
        value,
        "metadataComparabilityPolicy",
        path,
        expected=TIMING_ADVISORY_METADATA_COMPARABILITY_POLICY,
        expected_label="the comparator metadata comparability policy",
    )
    require_policy_string_field(
        value,
        "policy",
        path,
        expected=TIMING_ADVISORY_EVIDENCE_POLICY,
        expected_label="the comparator report-only evidence policy",
    )


def advisory_threshold_profile_from_policy_json(
    payload: dict[str, Any],
) -> AdvisoryThresholdProfile:
    policy = advisory_threshold_policy_payload(payload)

    schema_version = policy.get("schemaVersion")
    if schema_version != ADVISORY_THRESHOLD_POLICY_SCHEMA_VERSION:
        raise PerformanceReportComparisonError(
            "malformed advisory threshold policy: schemaVersion must be "
            f"{ADVISORY_THRESHOLD_POLICY_SCHEMA_VERSION}"
        )
    kind = policy.get("kind")
    if kind != ADVISORY_THRESHOLD_POLICY_KIND:
        raise PerformanceReportComparisonError(
            f"malformed advisory threshold policy: kind must be "
            f"{ADVISORY_THRESHOLD_POLICY_KIND!r}"
        )
    tool = policy.get("tool")
    if tool != TOOL_NAME:
        raise PerformanceReportComparisonError(
            f"malformed advisory threshold policy: tool must be {TOOL_NAME!r}"
        )
    mode = policy.get("mode")
    if mode != "report-only":
        raise PerformanceReportComparisonError(
            "malformed advisory threshold policy: mode must be 'report-only'"
        )

    name = require_policy_string_field(policy, "name", "")
    description = require_policy_string_field(policy, "description", "")
    if "enforcement" not in policy:
        raise PerformanceReportComparisonError(
            "malformed advisory threshold policy: enforcement is required"
        )
    validate_threshold_enforcement_payload(policy["enforcement"], "enforcement")
    if "evidencePolicy" not in policy:
        raise PerformanceReportComparisonError(
            "malformed advisory threshold policy: evidencePolicy is required"
        )
    validate_threshold_evidence_policy_payload(
        policy["evidencePolicy"], "evidencePolicy"
    )
    require_policy_string_field(
        policy,
        "failurePolicy",
        "",
        expected=ADVISORY_THRESHOLD_FAILURE_POLICY,
        expected_label="the comparator report-only failure policy",
    )
    require_policy_string_field(
        policy,
        "releaseBlockerPolicy",
        "",
        expected=TIMING_ADVISORY_RELEASE_BLOCKER_POLICY,
        expected_label="the comparator report-only release blocker policy",
    )
    raw_rules = policy.get("rules")
    if not isinstance(raw_rules, list):
        raise PerformanceReportComparisonError(
            "malformed advisory threshold policy: rules must be an array"
        )
    rule_count = policy.get("ruleCount")
    if "ruleCount" not in policy:
        raise PerformanceReportComparisonError(
            "malformed advisory threshold policy: ruleCount is required"
        )
    if nonnegative_int_value(rule_count) is None:
        raise PerformanceReportComparisonError(
            "malformed advisory threshold policy: ruleCount must be a "
            "non-negative integer"
        )
    if rule_count != len(raw_rules):
        raise PerformanceReportComparisonError(
            "malformed advisory threshold policy: ruleCount must match rules "
            f"length ({len(raw_rules)})"
        )

    rules: list[AdvisoryThresholdRule] = []
    for index, raw_rule in enumerate(raw_rules):
        path = f"rules[{index}]"
        if not isinstance(raw_rule, dict):
            raise PerformanceReportComparisonError(
                f"malformed advisory threshold policy: {path} must be an object"
            )
        category = string_value(raw_rule.get("category"))
        if category is None:
            raise PerformanceReportComparisonError(
                f"malformed advisory threshold policy: {path}.category must be "
                "a non-empty string"
            )
        benchmark_profile = string_value(raw_rule.get("profile"))
        if benchmark_profile is None:
            raise PerformanceReportComparisonError(
                f"malformed advisory threshold policy: {path}.profile must be "
                "a non-empty string"
            )
        target = string_value(raw_rule.get("target")) if "target" in raw_rule else "*"
        if target is None:
            raise PerformanceReportComparisonError(
                f"malformed advisory threshold policy: {path}.target must be "
                "a non-empty string"
            )
        backend = (
            string_value(raw_rule.get("backend")) if "backend" in raw_rule else "*"
        )
        if backend is None:
            raise PerformanceReportComparisonError(
                f"malformed advisory threshold policy: {path}.backend must be "
                "a non-empty string"
            )
        if "maxRegressionPercent" not in raw_rule:
            raise PerformanceReportComparisonError(
                f"malformed advisory threshold policy: "
                f"{path}.maxRegressionPercent is required"
            )
        max_regression_percent = decimal_policy_value(
            raw_rule.get("maxRegressionPercent"),
            f"{path}.maxRegressionPercent",
        )
        label = string_value(raw_rule.get("label")) or (
            f"{benchmark_profile} {category} advisory threshold"
        )
        if "label" in raw_rule and string_value(raw_rule.get("label")) is None:
            raise PerformanceReportComparisonError(
                f"malformed advisory threshold policy: {path}.label must be "
                "a non-empty string"
            )
        expected_specificity = threshold_rule_specificity_from_labels(
            category,
            benchmark_profile,
            target,
            backend,
        )
        if "ruleSpecificity" in raw_rule:
            rule_specificity = string_value(raw_rule.get("ruleSpecificity"))
            if rule_specificity is None:
                raise PerformanceReportComparisonError(
                    f"malformed advisory threshold policy: "
                    f"{path}.ruleSpecificity must be a non-empty string"
                )
            if rule_specificity != expected_specificity:
                raise PerformanceReportComparisonError(
                    f"malformed advisory threshold policy: "
                    f"{path}.ruleSpecificity must be {expected_specificity!r}"
                )
        rules.append(
            AdvisoryThresholdRule(
                category=category,
                profile=benchmark_profile,
                max_regression_percent=max_regression_percent,
                label=label,
                target=target,
                backend=backend,
            )
        )

    profile = AdvisoryThresholdProfile(
        name=name,
        description=description,
        rules=tuple(rules),
    )
    validate_advisory_threshold_profile(profile)
    return profile


def load_advisory_threshold_policy(path: Path) -> AdvisoryThresholdProfile:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise PerformanceReportComparisonError(
            f"could not read advisory threshold policy: {path}"
        ) from exc
    except json.JSONDecodeError as exc:
        raise PerformanceReportComparisonError(
            f"invalid advisory threshold policy JSON at {path}:{exc.lineno}:{exc.colno}"
        ) from exc
    if not isinstance(payload, dict):
        raise PerformanceReportComparisonError(
            f"advisory threshold policy must be a JSON object: {path}"
        )
    return advisory_threshold_profile_from_policy_json(payload)


def advisory_threshold_policy_source(
    *,
    profile_name: str,
    policy_path: Path | None,
    profile: AdvisoryThresholdProfile,
) -> dict[str, Any]:
    if policy_path is not None:
        return {
            "kind": "file",
            "name": profile.name,
            "path": policy_path.as_posix(),
        }
    return {
        "kind": "builtin",
        "name": profile.name,
        "profile": profile_name,
    }


def resolve_advisory_threshold_profile(
    *,
    profile_name: str,
    policy_path: Path | None = None,
) -> tuple[AdvisoryThresholdProfile, dict[str, Any]]:
    if policy_path is not None:
        profile = load_advisory_threshold_policy(policy_path)
        return profile, advisory_threshold_policy_source(
            profile_name=profile_name,
            policy_path=policy_path,
            profile=profile,
        )

    try:
        profile = ADVISORY_THRESHOLD_PROFILES[profile_name]
    except KeyError as exc:
        raise PerformanceReportComparisonError(
            f"unknown advisory threshold profile: {profile_name}"
        ) from exc
    validate_advisory_threshold_profile(profile)
    return profile, advisory_threshold_policy_source(
        profile_name=profile_name,
        policy_path=None,
        profile=profile,
    )


def threshold_rule_matches(rule: AdvisoryThresholdRule, case: ReportCase) -> bool:
    profile_label = case.profile or "uncategorized"
    target_label = case.target or "unspecified"
    backend_label = case.backend or target_label
    return (
        (rule.category == "*" or rule.category == case.category)
        and (rule.profile == "*" or rule.profile == profile_label)
        and (rule.target == "*" or rule.target == target_label)
        and (rule.backend == "*" or rule.backend == backend_label)
    )


def threshold_rule_match_report(
    rule: AdvisoryThresholdRule, case: ReportCase
) -> dict[str, Any]:
    report = {
        "caseCategory": case.category,
        "caseTarget": case.target,
        "caseProfile": case.profile,
        "categoryMatch": "wildcard" if rule.category == "*" else "exact",
        "profileMatch": "wildcard" if rule.profile == "*" else "exact",
        "ruleCategory": rule.category,
        "ruleProfile": rule.profile,
        "ruleSpecificity": threshold_rule_specificity(rule),
    }
    if rule.target != "*":
        report["ruleTarget"] = rule.target
        report["targetMatch"] = "exact"
    if rule.backend != "*":
        report["caseBackend"] = case.backend
        report["ruleBackend"] = rule.backend
        report["backendMatch"] = "exact"
    return report


def advisory_threshold_rule_for_case(
    profile: AdvisoryThresholdProfile, case: ReportCase
) -> AdvisoryThresholdRule | None:
    for rule in profile.rules:
        if threshold_rule_matches(rule, case):
            return rule
    return None


def advisory_threshold_profile_report(
    profile: AdvisoryThresholdProfile,
    *,
    matched_case_count: int,
    claim_eligible_case_count: int,
    claim_disposition_counts: dict[str, int],
    rule_specificity_counts: dict[str, int],
    insufficient_evidence_cases: list[str],
    measured_threshold_exceeded_cases: list[str],
    unmatched_cases: list[str],
) -> dict[str, Any]:
    return {
        "advisory": True,
        "claimEligibleCaseCount": claim_eligible_case_count,
        "claimDispositionCounts": sorted_counts(claim_disposition_counts),
        "description": profile.description,
        "evidencePolicy": {
            "metadataComparabilityPolicy": (
                TIMING_ADVISORY_METADATA_COMPARABILITY_POLICY
            ),
            "minimumSampleCount": TIMING_ADVISORY_MIN_SAMPLE_COUNT,
            "policy": TIMING_ADVISORY_EVIDENCE_POLICY,
            "requiresComparableMetadata": True,
            "requiresExplicitTimedCaseIdentity": True,
            "requiresRepeatedBaselineAndCandidateSamples": True,
        },
        "enforcement": threshold_enforcement_json(),
        "failurePolicy": (
            "report-only; this profile never changes comparator exit status"
        ),
        "insufficientEvidenceCaseCount": len(insufficient_evidence_cases),
        "insufficientEvidenceCases": insufficient_evidence_cases,
        "matchedCaseCount": matched_case_count,
        "measuredThresholdExceededCaseCount": len(measured_threshold_exceeded_cases),
        "measuredThresholdExceededCases": measured_threshold_exceeded_cases,
        "mode": "report-only",
        "name": profile.name,
        "releaseBlockerPolicy": TIMING_ADVISORY_RELEASE_BLOCKER_POLICY,
        "ruleSpecificityCounts": sorted_counts(rule_specificity_counts),
        "ruleCount": len(profile.rules),
        "rules": [threshold_rule_json(rule) for rule in profile.rules],
        "unmatchedCaseCount": len(unmatched_cases),
        "unmatchedCases": unmatched_cases,
    }


def advisory_threshold_policy_report(
    profile: AdvisoryThresholdProfile,
    *,
    metadata_evidence: dict[str, Any],
    matched_case_count: int,
    claim_eligible_case_count: int,
    claim_disposition_counts: dict[str, int],
    rule_specificity_counts: dict[str, int],
    threshold_exceeded_count: int,
    measured_threshold_exceeded_cases: list[str],
    insufficient_evidence_cases: list[str],
) -> dict[str, Any]:
    return {
        "advisory": True,
        "claimEligibleCaseCount": claim_eligible_case_count,
        "claimDispositionCounts": sorted_counts(claim_disposition_counts),
        "enforcement": threshold_enforcement_json(),
        "failurePolicy": ADVISORY_THRESHOLD_FAILURE_POLICY,
        "insufficientEvidenceCaseCount": len(insufficient_evidence_cases),
        "insufficientEvidenceCases": insufficient_evidence_cases,
        "matchedCaseCount": matched_case_count,
        "measuredThresholdExceededCaseCount": len(measured_threshold_exceeded_cases),
        "measuredThresholdExceededCases": measured_threshold_exceeded_cases,
        "metadataComparability": metadata_evidence,
        "metadataCompatible": metadata_evidence["compatible"],
        "minimumSampleCount": TIMING_ADVISORY_MIN_SAMPLE_COUNT,
        "mode": "report-only",
        "profile": profile.name,
        "releaseBlockerPolicy": TIMING_ADVISORY_RELEASE_BLOCKER_POLICY,
        "requiresComparableMetadata": True,
        "requiresExplicitTimedCaseIdentity": True,
        "requiresRepeatedBaselineAndCandidateSamples": True,
        "ruleSpecificityCounts": sorted_counts(rule_specificity_counts),
        "thresholdExceededCount": threshold_exceeded_count,
    }


def advisory_thresholds_report(
    profile: AdvisoryThresholdProfile,
    source: dict[str, Any],
    *,
    profile_report: dict[str, Any],
    policy_report: dict[str, Any],
    threshold_exceeded_cases: list[str],
) -> dict[str, Any]:
    return {
        "advisory": True,
        "mode": "report-only",
        "source": source,
        "policy": advisory_threshold_policy_json(profile),
        "enforcement": threshold_enforcement_json(),
        "classification": {
            "claimDispositionCounts": profile_report["claimDispositionCounts"],
            "claimEligibleCaseCount": profile_report["claimEligibleCaseCount"],
            "insufficientEvidenceCaseCount": profile_report[
                "insufficientEvidenceCaseCount"
            ],
            "insufficientEvidenceCases": profile_report["insufficientEvidenceCases"],
            "matchedCaseCount": profile_report["matchedCaseCount"],
            "measuredThresholdExceededCaseCount": profile_report[
                "measuredThresholdExceededCaseCount"
            ],
            "measuredThresholdExceededCases": profile_report[
                "measuredThresholdExceededCases"
            ],
            "ruleSpecificityCounts": profile_report["ruleSpecificityCounts"],
            "thresholdExceededCaseCount": policy_report["thresholdExceededCount"],
            "thresholdExceededCases": threshold_exceeded_cases,
            "unmatchedCaseCount": profile_report["unmatchedCaseCount"],
            "unmatchedCases": profile_report["unmatchedCases"],
        },
        "failurePolicy": policy_report["failurePolicy"],
        "metadataComparability": policy_report["metadataComparability"],
        "releaseBlockerPolicy": TIMING_ADVISORY_RELEASE_BLOCKER_POLICY,
    }


def proposal_dimension_value(value: Any) -> Any:
    return value if value is not None else "unspecified"


def proposal_toolchain_dimension(metadata: ReportPolicyMetadata) -> list[str]:
    labels = []
    for label, fields in sorted(metadata.toolchains.items()):
        version = fields.get("version")
        toolchain_class = fields.get("class")
        suffix_parts = [
            str(part)
            for part in (version, toolchain_class)
            if isinstance(part, str) and part
        ]
        labels.append(
            f"{label}@{'/'.join(suffix_parts)}" if suffix_parts else str(label)
        )
    return labels


def proposal_group_key_value(value: Any) -> str:
    if value is None:
        return "unspecified"
    if isinstance(value, (dict, list)):
        return json.dumps(value, sort_keys=True)
    return str(value)


def threshold_proposal_dimensions(
    baseline_metadata: ReportPolicyMetadata,
    candidate_metadata: ReportPolicyMetadata,
) -> dict[str, Any]:
    return {
        "baseline": {
            "comparisonWindow": proposal_dimension_value(
                baseline_metadata.fields.get("comparisonWindow")
            ),
            "hostClass": proposal_dimension_value(
                baseline_metadata.fields.get("hostClass")
            ),
            "hostLabel": proposal_dimension_value(
                baseline_metadata.fields.get("hostLabel")
            ),
            "optLevel": proposal_dimension_value(
                baseline_metadata.fields.get("optLevel")
            ),
            "targetProfile": proposal_dimension_value(
                baseline_metadata.fields.get("targetProfile")
            ),
            "skippedToolAccounting": baseline_metadata.skipped_tool_accounting,
            "toolchainClasses": toolchain_classes(baseline_metadata.toolchains),
            "toolchainLabels": sorted(baseline_metadata.toolchains),
            "toolchains": proposal_toolchain_dimension(baseline_metadata),
        },
        "candidate": {
            "comparisonWindow": proposal_dimension_value(
                candidate_metadata.fields.get("comparisonWindow")
            ),
            "hostClass": proposal_dimension_value(
                candidate_metadata.fields.get("hostClass")
            ),
            "hostLabel": proposal_dimension_value(
                candidate_metadata.fields.get("hostLabel")
            ),
            "optLevel": proposal_dimension_value(
                candidate_metadata.fields.get("optLevel")
            ),
            "targetProfile": proposal_dimension_value(
                candidate_metadata.fields.get("targetProfile")
            ),
            "skippedToolAccounting": candidate_metadata.skipped_tool_accounting,
            "toolchainClasses": toolchain_classes(candidate_metadata.toolchains),
            "toolchainLabels": sorted(candidate_metadata.toolchains),
            "toolchains": proposal_toolchain_dimension(candidate_metadata),
        },
    }


def threshold_proposal_observation(
    entry: dict[str, Any],
    baseline_case: ReportCase,
    candidate_case: ReportCase,
) -> dict[str, Any]:
    advisory_threshold = entry.get("advisoryThreshold")
    advisory_rule_match = (
        advisory_threshold.get("ruleMatch")
        if isinstance(advisory_threshold, dict)
        else None
    )
    advisory_rule_specificity = (
        advisory_threshold.get("ruleSpecificity")
        if isinstance(advisory_threshold, dict)
        else None
    )
    explicit_threshold = entry.get("explicitThreshold")
    return {
        "advisoryThresholdClaimedExceeded": entry.get(
            "exceedsAdvisoryThreshold", False
        ),
        "advisoryThresholdDeltaNs": (
            advisory_threshold.get("thresholdDeltaNs")
            if isinstance(advisory_threshold, dict)
            else None
        ),
        "advisoryThresholdExcessNs": (
            advisory_threshold.get("thresholdExcessNs")
            if isinstance(advisory_threshold, dict)
            else None
        ),
        "advisoryThresholdHeadroomNs": (
            advisory_threshold.get("thresholdHeadroomNs")
            if isinstance(advisory_threshold, dict)
            else None
        ),
        "advisoryThresholdMeasuredExceeded": entry.get(
            "measuredExceedsAdvisoryThreshold", False
        ),
        "advisoryThresholdRuleMatch": advisory_rule_match,
        "advisoryThresholdRuleSpecificity": advisory_rule_specificity,
        "backend": baseline_case.backend,
        "case": entry["case"],
        "caseCategory": baseline_case.category,
        "candidateNs": entry["candidateNs"],
        "changeKind": entry["changeKind"],
        "commandProfile": baseline_case.command_profile,
        "currentPolicyDisposition": entry["currentPolicyDisposition"],
        "deltaNs": entry["deltaNs"],
        "explicitThresholdClaimedExceeded": entry.get(
            "exceedsExplicitThreshold", False
        ),
        "explicitThresholdDeltaNs": (
            explicit_threshold.get("thresholdDeltaNs")
            if isinstance(explicit_threshold, dict)
            else None
        ),
        "explicitThresholdExcessNs": (
            explicit_threshold.get("thresholdExcessNs")
            if isinstance(explicit_threshold, dict)
            else None
        ),
        "explicitThresholdHeadroomNs": (
            explicit_threshold.get("thresholdHeadroomNs")
            if isinstance(explicit_threshold, dict)
            else None
        ),
        "explicitThresholdMeasuredExceeded": entry.get(
            "measuredExceedsExplicitThreshold", False
        ),
        "fixtureName": baseline_case.fixture_name,
        "matchedAdvisoryThresholdRule": advisory_threshold is not None,
        "optLevel": baseline_case.opt_level,
        "profile": baseline_case.profile,
        "regressionPercent": entry["regressionPercent"],
        "target": baseline_case.target,
        "timingClaimEligible": entry.get("timingAdvisoryClaimEligible", False),
        "timingClaimEligibilityDisposition": entry.get("timingEvidence", {}).get(
            "claimEligibilityDisposition"
        ),
        "timingObservation": True,
    }


def threshold_proposal_group_key(
    dimensions: dict[str, Any], observation: dict[str, Any]
) -> tuple[Any, ...]:
    baseline = dimensions["baseline"]
    candidate = dimensions["candidate"]
    return (
        proposal_group_key_value(baseline["comparisonWindow"]),
        baseline["hostClass"],
        baseline["hostLabel"],
        baseline["optLevel"],
        tuple(sorted(baseline["toolchainClasses"].items())),
        tuple(baseline["toolchainLabels"]),
        tuple(baseline["toolchains"]),
        proposal_group_key_value(baseline["skippedToolAccounting"]),
        baseline["targetProfile"],
        proposal_group_key_value(candidate["comparisonWindow"]),
        candidate["hostClass"],
        candidate["hostLabel"],
        candidate["optLevel"],
        tuple(sorted(candidate["toolchainClasses"].items())),
        tuple(candidate["toolchainLabels"]),
        tuple(candidate["toolchains"]),
        proposal_group_key_value(candidate["skippedToolAccounting"]),
        candidate["targetProfile"],
        observation["caseCategory"],
        observation["target"],
        observation["backend"],
        observation["profile"],
    )


def threshold_proposal_groups(
    dimensions: dict[str, Any], observations: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    grouped: dict[tuple[Any, ...], dict[str, Any]] = {}
    for observation in observations:
        key = threshold_proposal_group_key(dimensions, observation)
        group = grouped.setdefault(
            key,
            {
                "advisoryThresholdClaimedExceededCases": [],
                "advisoryThresholdMeasuredExceededCases": [],
                "advisoryThresholdRuleSpecificityCounts": {},
                "caseCategory": observation["caseCategory"],
                "cases": [],
                "candidateComparisonWindow": dimensions["candidate"][
                    "comparisonWindow"
                ],
                "candidateHostClass": dimensions["candidate"]["hostClass"],
                "candidateHostLabel": dimensions["candidate"]["hostLabel"],
                "candidateOptLevel": dimensions["candidate"]["optLevel"],
                "candidateTargetProfile": dimensions["candidate"]["targetProfile"],
                "candidateSkippedToolAccounting": dimensions["candidate"][
                    "skippedToolAccounting"
                ],
                "candidateToolchainClasses": dimensions["candidate"][
                    "toolchainClasses"
                ],
                "candidateToolchainLabels": dimensions["candidate"]["toolchainLabels"],
                "candidateToolchains": dimensions["candidate"]["toolchains"],
                "claimEligibleCaseCount": 0,
                "currentPolicyDispositionCounts": {},
                "profile": observation["profile"],
                "baselineComparisonWindow": dimensions["baseline"]["comparisonWindow"],
                "baselineHostClass": dimensions["baseline"]["hostClass"],
                "baselineHostLabel": dimensions["baseline"]["hostLabel"],
                "baselineOptLevel": dimensions["baseline"]["optLevel"],
                "baselineTargetProfile": dimensions["baseline"]["targetProfile"],
                "baselineSkippedToolAccounting": dimensions["baseline"][
                    "skippedToolAccounting"
                ],
                "baselineToolchainClasses": dimensions["baseline"]["toolchainClasses"],
                "baselineToolchainLabels": dimensions["baseline"]["toolchainLabels"],
                "baselineToolchains": dimensions["baseline"]["toolchains"],
                "backend": observation["backend"],
                "target": observation["target"],
                "timingObservationCaseCount": 0,
                "unmatchedAdvisoryThresholdRuleCaseCount": 0,
            },
        )
        group["cases"].append(observation["case"])
        group["timingObservationCaseCount"] += 1
        if observation["timingClaimEligible"]:
            group["claimEligibleCaseCount"] += 1
        rule_specificity = observation["advisoryThresholdRuleSpecificity"]
        if isinstance(rule_specificity, str) and rule_specificity:
            add_count(group["advisoryThresholdRuleSpecificityCounts"], rule_specificity)
        else:
            group["unmatchedAdvisoryThresholdRuleCaseCount"] += 1
        add_count(
            group["currentPolicyDispositionCounts"],
            observation["currentPolicyDisposition"],
        )
        if observation["advisoryThresholdMeasuredExceeded"]:
            group["advisoryThresholdMeasuredExceededCases"].append(observation["case"])
        if observation["advisoryThresholdClaimedExceeded"]:
            group["advisoryThresholdClaimedExceededCases"].append(observation["case"])

    proposal_groups = []
    for group in grouped.values():
        proposal_groups.append(
            {
                **group,
                "advisoryThresholdClaimedExceededCaseCount": len(
                    group["advisoryThresholdClaimedExceededCases"]
                ),
                "advisoryThresholdClaimedExceededCases": sorted(
                    group["advisoryThresholdClaimedExceededCases"]
                ),
                "advisoryThresholdMeasuredExceededCaseCount": len(
                    group["advisoryThresholdMeasuredExceededCases"]
                ),
                "advisoryThresholdMeasuredExceededCases": sorted(
                    group["advisoryThresholdMeasuredExceededCases"]
                ),
                "advisoryThresholdRuleSpecificityCounts": sorted_counts(
                    group["advisoryThresholdRuleSpecificityCounts"]
                ),
                "cases": sorted(group["cases"]),
                "currentPolicyDispositionCounts": sorted_counts(
                    group["currentPolicyDispositionCounts"]
                ),
            }
        )
    return sorted(
        proposal_groups,
        key=lambda group: (
            group["baselineHostClass"],
            group["baselineHostLabel"],
            proposal_group_key_value(group["baselineComparisonWindow"]),
            group["baselineOptLevel"],
            tuple(sorted(group["baselineToolchainClasses"].items())),
            tuple(group["baselineToolchainLabels"]),
            tuple(group["baselineToolchains"]),
            proposal_group_key_value(group["baselineSkippedToolAccounting"]),
            group["baselineTargetProfile"],
            group["candidateHostClass"],
            group["candidateHostLabel"],
            proposal_group_key_value(group["candidateComparisonWindow"]),
            group["candidateOptLevel"],
            tuple(sorted(group["candidateToolchainClasses"].items())),
            tuple(group["candidateToolchainLabels"]),
            tuple(group["candidateToolchains"]),
            proposal_group_key_value(group["candidateSkippedToolAccounting"]),
            group["candidateTargetProfile"],
            group["caseCategory"],
            group["target"],
            group["profile"] or "",
        ),
    )


def threshold_proposal_pair_requirement(
    name: str,
    *,
    satisfied: bool,
    reason_if_unsatisfied: str,
    observed: dict[str, Any],
) -> dict[str, Any]:
    return {
        "name": name,
        "observed": observed,
        "reasonIfUnsatisfied": reason_if_unsatisfied,
        "satisfied": satisfied,
    }


def threshold_proposal_pair_readiness_report(
    *,
    structural_failure: bool,
    structural_failure_reasons: list[str],
    baseline_readiness: dict[str, Any],
    candidate_readiness: dict[str, Any],
    timing_metadata_evidence: dict[str, Any],
    timing_evidence_sufficiency: dict[str, Any],
    observation_count: int,
    group_count: int,
) -> dict[str, Any]:
    stable_dispositions = {
        "advisory",
        "advisory-threshold-exceeded",
        "non-regression",
        "within-advisory-threshold",
    }
    current_policy_dispositions = timing_evidence_sufficiency[
        "currentPolicyDispositionCounts"
    ]
    unstable_dispositions = sorted(
        disposition
        for disposition in current_policy_dispositions
        if disposition not in stable_dispositions
    )
    requirements = [
        threshold_proposal_pair_requirement(
            "cleanStructuralComparison",
            satisfied=not structural_failure,
            reason_if_unsatisfied="structuralFailure",
            observed={
                "failed": structural_failure,
                "failureReasons": structural_failure_reasons,
            },
        ),
        threshold_proposal_pair_requirement(
            "baselineReadyForThresholdBaseline",
            satisfied=baseline_readiness["readyForThresholdBaseline"],
            reason_if_unsatisfied="baselineReadinessIncomplete",
            observed={
                "readyForThresholdBaseline": baseline_readiness[
                    "readyForThresholdBaseline"
                ],
                "reasons": baseline_readiness["reasons"],
                "unsatisfiedThresholdBaselineRequirements": (
                    baseline_readiness["unsatisfiedThresholdBaselineRequirements"]
                ),
            },
        ),
        threshold_proposal_pair_requirement(
            "candidateReadyForThresholdBaseline",
            satisfied=candidate_readiness["readyForThresholdBaseline"],
            reason_if_unsatisfied="candidateReadinessIncomplete",
            observed={
                "readyForThresholdBaseline": candidate_readiness[
                    "readyForThresholdBaseline"
                ],
                "reasons": candidate_readiness["reasons"],
                "unsatisfiedThresholdBaselineRequirements": (
                    candidate_readiness["unsatisfiedThresholdBaselineRequirements"]
                ),
            },
        ),
        threshold_proposal_pair_requirement(
            "compatibleMetadata",
            satisfied=timing_metadata_evidence["compatible"],
            reason_if_unsatisfied="metadataIncompatible",
            observed={
                "baselineMissingFields": timing_metadata_evidence[
                    "baselineMissingFields"
                ],
                "candidateMissingFields": timing_metadata_evidence[
                    "candidateMissingFields"
                ],
                "metadataCompatible": timing_metadata_evidence["compatible"],
                "reasons": timing_metadata_evidence["reasons"],
            },
        ),
        threshold_proposal_pair_requirement(
            "timingObservations",
            satisfied=observation_count > 0,
            reason_if_unsatisfied="noTimingObservations",
            observed={
                "groupCount": group_count,
                "timingObservationCaseCount": observation_count,
            },
        ),
        threshold_proposal_pair_requirement(
            "claimEligibleTimingEvidence",
            satisfied=(
                observation_count > 0
                and timing_evidence_sufficiency["claimEligibleCaseCount"]
                == observation_count
                and timing_evidence_sufficiency["insufficientEvidenceCaseCount"] == 0
            ),
            reason_if_unsatisfied="claimIneligibleTimingEvidence",
            observed={
                "claimEligibleCaseCount": timing_evidence_sufficiency[
                    "claimEligibleCaseCount"
                ],
                "insufficientEvidenceCaseCount": timing_evidence_sufficiency[
                    "insufficientEvidenceCaseCount"
                ],
                "insufficientEvidenceCases": timing_evidence_sufficiency[
                    "insufficientEvidenceCases"
                ],
                "timingObservationCaseCount": observation_count,
            },
        ),
        threshold_proposal_pair_requirement(
            "stableReportOnlyClassification",
            satisfied=not unstable_dispositions,
            reason_if_unsatisfied="unstableReportOnlyClassification",
            observed={
                "stableDispositionAllowList": sorted(stable_dispositions),
                "currentPolicyDispositionCounts": current_policy_dispositions,
                "unstableDispositionCount": len(unstable_dispositions),
                "unstableDispositions": unstable_dispositions,
            },
        ),
    ]
    unsatisfied_requirements = [
        requirement["name"]
        for requirement in requirements
        if requirement["satisfied"] is not True
    ]
    reasons = [
        requirement["reasonIfUnsatisfied"]
        for requirement in requirements
        if requirement["satisfied"] is not True
    ]
    ready = not reasons
    return {
        "advisory": True,
        "mode": "report-only",
        "readyForRepeatedReportTrend": ready,
        "status": "ready" if ready else "incomplete",
        "reasonCount": len(reasons),
        "reasons": reasons,
        "releaseClaimRepeatedReportPairMinimum": (
            TIMING_THRESHOLD_RELEASE_CLAIM_MIN_REPEATED_REPORTS
        ),
        "repeatedReportPairContribution": 1 if ready else 0,
        "remainingRepeatedReportPairsForReleaseClaim": (
            TIMING_THRESHOLD_RELEASE_CLAIM_MIN_REPEATED_REPORTS - 1
            if ready
            else TIMING_THRESHOLD_RELEASE_CLAIM_MIN_REPEATED_REPORTS
        ),
        "requirementCount": len(requirements),
        "requirements": requirements,
        "satisfiedRequirementCount": len(requirements) - len(unsatisfied_requirements),
        "unsatisfiedRequirementCount": len(unsatisfied_requirements),
        "unsatisfiedRequirements": unsatisfied_requirements,
        "policy": (
            "This pair-readiness summary is advisory trend evidence only. A "
            "single comparison can contribute at most one repeated report pair "
            "toward the documented release-claim minimum, and readiness never "
            "changes comparator exit status."
        ),
        "releaseClaimPolicy": TIMING_THRESHOLD_RELEASE_CLAIM_POLICY,
    }


def threshold_proposal_layer_report(
    *,
    baseline_metadata: ReportPolicyMetadata,
    candidate_metadata: ReportPolicyMetadata,
    structural_failure: bool,
    structural_failure_reasons: list[str],
    baseline_readiness: dict[str, Any],
    candidate_readiness: dict[str, Any],
    timing_metadata_evidence: dict[str, Any],
    timing_evidence_sufficiency: dict[str, Any],
    observations: list[dict[str, Any]],
) -> dict[str, Any]:
    dimensions = threshold_proposal_dimensions(baseline_metadata, candidate_metadata)
    groups = threshold_proposal_groups(dimensions, observations)
    pair_readiness = threshold_proposal_pair_readiness_report(
        structural_failure=structural_failure,
        structural_failure_reasons=structural_failure_reasons,
        baseline_readiness=baseline_readiness,
        candidate_readiness=candidate_readiness,
        timing_metadata_evidence=timing_metadata_evidence,
        timing_evidence_sufficiency=timing_evidence_sufficiency,
        observation_count=len(observations),
        group_count=len(groups),
    )
    return {
        "advisory": True,
        "dimensions": dimensions,
        "failureMode": "report-only",
        "groupCount": len(groups),
        "groups": groups,
        "mode": "report-only",
        "policy": (
            "Threshold proposal inputs are classified for dashboard/release-note "
            "review only. Structural failures are reported separately from timing "
            "observations; host, toolchain, target-profile, optimization, "
            "comparison-window, case-category, and skipped-tool dimensions are "
            "advisory context only. Timing proposal output never changes "
            "comparator exit status."
        ),
        "releaseClaimPolicy": TIMING_THRESHOLD_RELEASE_CLAIM_POLICY,
        "releaseClaimRepeatedReportPairMinimum": (
            TIMING_THRESHOLD_RELEASE_CLAIM_MIN_REPEATED_REPORTS
        ),
        "repeatedReportTrendReadiness": pair_readiness,
        "structural": {
            "failed": structural_failure,
            "failureReasons": structural_failure_reasons,
            "mode": "hard-fail",
        },
        "timingObservationCaseCount": len(observations),
        "timingObservations": observations,
    }


def validate_advisory_threshold_profile(profile: AdvisoryThresholdProfile) -> None:
    if not isinstance(profile, AdvisoryThresholdProfile):
        raise PerformanceReportComparisonError(
            "malformed advisory threshold profile: profile must be an "
            "AdvisoryThresholdProfile"
        )
    if not isinstance(profile.name, str) or not profile.name:
        raise PerformanceReportComparisonError(
            "malformed advisory threshold profile: name must be a non-empty string"
        )
    if not isinstance(profile.description, str) or not profile.description:
        raise PerformanceReportComparisonError(
            f"malformed advisory threshold profile {profile.name!r}: "
            "description must be a non-empty string"
        )
    if not isinstance(profile.rules, tuple):
        raise PerformanceReportComparisonError(
            f"malformed advisory threshold profile {profile.name!r}: "
            "rules must be a tuple"
        )

    seen: set[tuple[str, str, str, str]] = set()
    prior_rules: list[tuple[int, tuple[str, str, str, str]]] = []
    for index, rule in enumerate(profile.rules):
        path = f"advisory threshold profile {profile.name!r} rule {index}"
        if not isinstance(rule, AdvisoryThresholdRule):
            raise PerformanceReportComparisonError(
                f"malformed {path}: rule must be an AdvisoryThresholdRule"
            )
        if not isinstance(rule.category, str) or not rule.category:
            raise PerformanceReportComparisonError(
                f"malformed {path}: category must be a non-empty string"
            )
        if not isinstance(rule.profile, str) or not rule.profile:
            raise PerformanceReportComparisonError(
                f"malformed {path}: profile must be a non-empty string"
            )
        if not isinstance(rule.target, str) or not rule.target:
            raise PerformanceReportComparisonError(
                f"malformed {path}: target must be a non-empty string"
            )
        if not isinstance(rule.backend, str) or not rule.backend:
            raise PerformanceReportComparisonError(
                f"malformed {path}: backend must be a non-empty string"
            )
        if (
            not isinstance(rule.max_regression_percent, Decimal)
            or not rule.max_regression_percent.is_finite()
            or rule.max_regression_percent < 0
        ):
            raise PerformanceReportComparisonError(
                f"malformed {path}: max_regression_percent must be non-negative"
            )
        if not isinstance(rule.label, str) or not rule.label:
            raise PerformanceReportComparisonError(
                f"malformed {path}: label must be a non-empty string"
            )
        key = (rule.category, rule.profile, rule.target, rule.backend)
        selector_label = (
            "category/profile rule"
            if key[2:] == ("*", "*")
            else "category/profile/target/backend rule"
        )
        if key in seen:
            raise PerformanceReportComparisonError(
                f"malformed {path}: duplicate {selector_label} {key!r}"
            )
        seen.add(key)
        for prior_index, prior_key in prior_rules:
            if all(
                prior_value == "*" or prior_value == value
                for prior_value, value in zip(prior_key, key)
            ):
                raise PerformanceReportComparisonError(
                    f"malformed {path}: {selector_label} {key!r} is "
                    f"unreachable after earlier rule {prior_index} {prior_key!r}"
                )
        prior_rules.append((index, key))


def advisory_threshold_diagnostic(
    entry: dict[str, Any],
    case: ReportCase,
    rule: AdvisoryThresholdRule,
    *,
    allowed_ns: int,
    measured_exceeds_threshold: bool,
) -> str:
    status = "exceeded" if measured_exceeds_threshold else "within"
    threshold_excess_ns = max(0, entry["candidateNs"] - allowed_ns)
    threshold_headroom_ns = max(0, allowed_ns - entry["candidateNs"])
    return (
        f"{case.key} {status} selected advisory threshold {rule.label!r} "
        f"(category={case.category}, profile={case.profile or 'unspecified'}, "
        f"target={case.target or 'unspecified'}, "
        f"backend={case.backend or case.target or 'unspecified'}, "
        f"maxRegressionPercent={decimal_percent_value(rule.max_regression_percent)}, "
        f"baselineNs={entry['baselineNs']}, candidateNs={entry['candidateNs']}, "
        f"allowedNs={allowed_ns}, thresholdExcessNs={threshold_excess_ns}, "
        f"thresholdHeadroomNs={threshold_headroom_ns})"
    )


def annotate_advisory_threshold(
    entry: dict[str, Any],
    case: ReportCase,
    profile: AdvisoryThresholdProfile,
    evidence: dict[str, Any],
) -> bool:
    rule = advisory_threshold_rule_for_case(profile, case)
    if rule is None:
        entry["advisoryThreshold"] = None
        entry["advisoryThresholdClaimEligible"] = False
        entry["exceedsAdvisoryThreshold"] = False
        entry["measuredExceedsAdvisoryThreshold"] = False
        entry["wouldFailAdvisoryProfileIfEnforced"] = False
        return False

    allowed_ns, allowed_ns_exact = threshold_limit(
        entry["baselineNs"], rule.max_regression_percent
    )
    measured_exceeds_threshold = (
        entry["deltaNs"] > 0 and entry["candidateNs"] > allowed_ns
    )
    claim_eligible = evidence["sufficientForAdvisoryThresholdClaim"]
    claim_exceeds_threshold = measured_exceeds_threshold and claim_eligible
    rule_specificity = threshold_rule_specificity(rule)
    entry["advisoryThreshold"] = {
        "allowedNs": allowed_ns,
        "allowedNsExact": allowed_ns_exact,
        **threshold_delta_report(entry, allowed_ns),
        "claimDisposition": threshold_claim_disposition(
            evidence, measured_exceeds=measured_exceeds_threshold
        ),
        "claimEligible": claim_eligible,
        "claimPolicy": TIMING_ADVISORY_EVIDENCE_POLICY,
        "caseIdentityComplete": evidence["caseIdentityComplete"],
        "caseBackend": case.backend,
        "enforcement": threshold_enforcement_json(),
        "evidence": threshold_evidence_summary(evidence),
        "caseCategory": case.category,
        "caseTarget": case.target,
        "diagnostic": advisory_threshold_diagnostic(
            entry,
            case,
            rule,
            allowed_ns=allowed_ns,
            measured_exceeds_threshold=measured_exceeds_threshold,
        ),
        "label": rule.label,
        "maxRegressionPercent": decimal_percent_value(rule.max_regression_percent),
        "measuredExceedsThreshold": measured_exceeds_threshold,
        "metadataCompatible": evidence["metadataCompatible"],
        "minimumSampleCount": evidence["minimumSampleCount"],
        "profile": profile.name,
        "requiresExplicitTimedCaseIdentity": True,
        "releaseBlockerPolicy": TIMING_ADVISORY_RELEASE_BLOCKER_POLICY,
        "reportOnlyReason": TIMING_ADVISORY_RELEASE_BLOCKER_POLICY,
        "ruleMatch": threshold_rule_match_report(rule, case),
        "ruleBackend": rule.backend,
        "ruleCategory": rule.category,
        "ruleProfile": rule.profile,
        "ruleSpecificity": rule_specificity,
        "ruleTarget": rule.target,
        "sufficientCaseIdentity": evidence["sufficientCaseIdentity"],
        "sufficientRepeatedEvidence": evidence["sufficientRepeatedEvidence"],
        "benchmarkProfile": case.profile,
    }
    entry["advisoryThresholdClaimEligible"] = claim_eligible
    entry["exceedsAdvisoryThreshold"] = claim_exceeds_threshold
    entry["measuredExceedsAdvisoryThreshold"] = measured_exceeds_threshold
    entry["wouldFailAdvisoryProfileIfEnforced"] = claim_exceeds_threshold
    return True


def timing_change_kind(delta_ns: int) -> str:
    if delta_ns > 0:
        return "regression"
    if delta_ns < 0:
        return "improvement"
    return "unchanged"


def timing_entry(
    key: str,
    baseline_ns: int,
    candidate_ns: int,
    *,
    threshold_percent: Decimal | None,
) -> dict[str, Any]:
    delta_ns = candidate_ns - baseline_ns
    entry = {
        "baselineNs": baseline_ns,
        "candidateNs": candidate_ns,
        "case": key,
        "changeKind": timing_change_kind(delta_ns),
        "deltaNs": delta_ns,
        "currentPolicyDisposition": "non-regression",
        "regressionPercent": regression_percent(baseline_ns, candidate_ns),
        "ratio": rounded_ratio(baseline_ns, candidate_ns),
        "wouldFailExplicitThresholdIfEnforced": False,
    }
    if threshold_percent is not None:
        allowed_ns, allowed_ns_exact = threshold_limit(baseline_ns, threshold_percent)
        entry["allowedNs"] = allowed_ns
        entry["allowedNsExact"] = allowed_ns_exact
        entry["exceedsExplicitThreshold"] = delta_ns > 0 and candidate_ns > allowed_ns
        entry["explicitThreshold"] = {
            "allowedNs": allowed_ns,
            "allowedNsExact": allowed_ns_exact,
            "enforcement": threshold_enforcement_json(),
            "maxRegressionPercent": decimal_percent_value(threshold_percent),
            "mode": "report-only",
            **threshold_delta_report(entry, allowed_ns),
        }
        entry["thresholdPercent"] = decimal_percent_value(threshold_percent)
        entry["wouldFailExplicitThresholdIfEnforced"] = entry[
            "exceedsExplicitThreshold"
        ]
    else:
        entry["exceedsExplicitThreshold"] = False
        entry["explicitThreshold"] = None
    return entry


def timing_warning_summary(
    *,
    advisory_regressions: list[dict[str, Any]],
    advisory_threshold_measured_exceeded_cases: list[str],
    advisory_threshold_exceeded_regressions: list[dict[str, Any]],
    explicit_threshold_measured_exceeded_cases: list[str],
    explicit_threshold_exceeded_regressions: list[dict[str, Any]],
    timing_insufficient_evidence_cases: list[str],
    untimed_cases: list[str],
) -> dict[str, Any]:
    timing_regression_cases = [entry["case"] for entry in advisory_regressions]
    advisory_threshold_claimed_exceeded_cases = [
        entry["case"] for entry in advisory_threshold_exceeded_regressions
    ]
    explicit_threshold_claimed_exceeded_cases = [
        entry["case"] for entry in explicit_threshold_exceeded_regressions
    ]
    warning_types: list[str] = []
    if timing_regression_cases:
        warning_types.append("timing-regression")
    if advisory_threshold_measured_exceeded_cases:
        warning_types.append("advisory-threshold-measured-exceeded")
    if advisory_threshold_claimed_exceeded_cases:
        warning_types.append("advisory-threshold-claimed-exceeded")
    if explicit_threshold_measured_exceeded_cases:
        warning_types.append("explicit-threshold-measured-exceeded")
    if explicit_threshold_claimed_exceeded_cases:
        warning_types.append("explicit-threshold-claimed-exceeded")
    if timing_insufficient_evidence_cases:
        warning_types.append("insufficient-advisory-evidence")
    if untimed_cases:
        warning_types.append("untimed-cases")

    warning_cases = sorted(
        {
            *timing_regression_cases,
            *advisory_threshold_measured_exceeded_cases,
            *advisory_threshold_claimed_exceeded_cases,
            *explicit_threshold_measured_exceeded_cases,
            *explicit_threshold_claimed_exceeded_cases,
            *timing_insufficient_evidence_cases,
            *untimed_cases,
        }
    )
    return {
        "advisory": True,
        "mode": "report-only",
        "failureMode": "report-only",
        "timingRegressionCaseCount": len(timing_regression_cases),
        "timingRegressionCases": timing_regression_cases,
        "advisoryThresholdMeasuredExceededCaseCount": len(
            advisory_threshold_measured_exceeded_cases
        ),
        "advisoryThresholdMeasuredExceededCases": (
            advisory_threshold_measured_exceeded_cases
        ),
        "advisoryThresholdClaimedExceededCaseCount": len(
            advisory_threshold_claimed_exceeded_cases
        ),
        "advisoryThresholdClaimedExceededCases": (
            advisory_threshold_claimed_exceeded_cases
        ),
        "explicitThresholdMeasuredExceededCaseCount": len(
            explicit_threshold_measured_exceeded_cases
        ),
        "explicitThresholdMeasuredExceededCases": (
            explicit_threshold_measured_exceeded_cases
        ),
        "explicitThresholdClaimedExceededCaseCount": len(
            explicit_threshold_claimed_exceeded_cases
        ),
        "explicitThresholdClaimedExceededCases": (
            explicit_threshold_claimed_exceeded_cases
        ),
        "insufficientEvidenceCaseCount": len(timing_insufficient_evidence_cases),
        "insufficientEvidenceCases": timing_insufficient_evidence_cases,
        "untimedCaseCount": len(untimed_cases),
        "untimedCases": untimed_cases,
        "warningCaseCount": len(warning_cases),
        "warningCases": warning_cases,
        "warningCount": len(warning_types),
        "warningTypes": warning_types,
        "policy": (
            "Timing delta warnings summarize slower cases, measured threshold "
            "excesses, insufficient evidence, and untimed cases for report triage "
            "only. They never change comparator exit status."
        ),
    }


def size_change_kind(delta_bytes: int) -> str:
    if delta_bytes > 0:
        return "increase"
    if delta_bytes < 0:
        return "decrease"
    return "unchanged"


def artifact_size_entry(
    key: str,
    baseline_bytes: int,
    candidate_bytes: int,
    *,
    baseline_file_count: int | None,
    candidate_file_count: int | None,
) -> dict[str, Any]:
    delta_bytes = candidate_bytes - baseline_bytes
    file_count_delta = (
        candidate_file_count - baseline_file_count
        if baseline_file_count is not None and candidate_file_count is not None
        else None
    )
    return {
        "baselineBytes": baseline_bytes,
        "baselineFileCount": baseline_file_count,
        "candidateBytes": candidate_bytes,
        "candidateFileCount": candidate_file_count,
        "case": key,
        "changeKind": size_change_kind(delta_bytes),
        "changePercent": regression_percent(baseline_bytes, candidate_bytes),
        "currentPolicyDisposition": "advisory" if delta_bytes > 0 else "non-increase",
        "deltaBytes": delta_bytes,
        "fileCountDelta": file_count_delta,
        "ratio": rounded_ratio(baseline_bytes, candidate_bytes),
        "wouldFailExplicitHardPolicy": False,
    }


def artifact_size_warning_summary(
    *,
    advisory_size_increases: list[dict[str, Any]],
    unsized_cases: list[str],
) -> dict[str, Any]:
    size_increase_cases = [entry["case"] for entry in advisory_size_increases]
    warning_types: list[str] = []
    if size_increase_cases:
        warning_types.append("artifact-size-increase")
    if unsized_cases:
        warning_types.append("insufficient-size-evidence")
        warning_types.append("unmeasured-size-cases")

    warning_cases = sorted({*size_increase_cases, *unsized_cases})
    return {
        "advisory": True,
        "mode": "report-only",
        "failureMode": "report-only",
        "artifactSizeIncreaseCaseCount": len(size_increase_cases),
        "artifactSizeIncreaseCases": size_increase_cases,
        "thresholdExceededCaseCount": 0,
        "thresholdExceededCases": [],
        "thresholdPolicy": "not-supported-v0-report-only",
        "insufficientEvidenceCaseCount": len(unsized_cases),
        "insufficientEvidenceCases": unsized_cases,
        "unmeasuredSizeCaseCount": len(unsized_cases),
        "unmeasuredSizeCases": unsized_cases,
        "warningCaseCount": len(warning_cases),
        "warningCases": warning_cases,
        "warningCount": len(warning_types),
        "warningTypes": warning_types,
        "policy": (
            "Artifact-size warnings summarize byte-size increases and cases "
            "without comparable size evidence for report triage only. "
            "Artifact-size thresholds are not supported in v0, and these "
            "warnings never change comparator exit status."
        ),
    }


def manifest_artifact_kind_delta_entry(
    key: str,
    baseline_metrics: dict[str, dict[str, int]],
    candidate_metrics: dict[str, dict[str, int]],
) -> dict[str, Any]:
    kinds: list[dict[str, Any]] = []
    for kind in sorted(set(baseline_metrics) | set(candidate_metrics)):
        baseline = baseline_metrics.get(kind) or {
            "byteSize": 0,
            "count": 0,
            "emittedCount": 0,
            "missingCount": 0,
        }
        candidate = candidate_metrics.get(kind) or {
            "byteSize": 0,
            "count": 0,
            "emittedCount": 0,
            "missingCount": 0,
        }
        kinds.append(
            {
                "baselineBytes": baseline["byteSize"],
                "baselineCount": baseline["count"],
                "baselineEmittedCount": baseline["emittedCount"],
                "baselineMissingCount": baseline["missingCount"],
                "candidateBytes": candidate["byteSize"],
                "candidateCount": candidate["count"],
                "candidateEmittedCount": candidate["emittedCount"],
                "candidateMissingCount": candidate["missingCount"],
                "deltaBytes": candidate["byteSize"] - baseline["byteSize"],
                "emittedCountDelta": (
                    candidate["emittedCount"] - baseline["emittedCount"]
                ),
                "kind": kind,
                "manifestCountDelta": candidate["count"] - baseline["count"],
                "missingCountDelta": (
                    candidate["missingCount"] - baseline["missingCount"]
                ),
            }
        )

    return {
        "case": key,
        "currentPolicyDisposition": "advisory",
        "kinds": kinds,
        "kindDeltaCount": sum(
            1
            for kind in kinds
            if kind["deltaBytes"] != 0
            or kind["manifestCountDelta"] != 0
            or kind["emittedCountDelta"] != 0
            or kind["missingCountDelta"] != 0
        ),
        "policy": "report-only",
    }


def summary_native_optimization_status_counts(
    report: dict[str, Any],
) -> dict[str, int] | None:
    summary = report.get("summary")
    if not isinstance(summary, dict):
        return None
    value = summary.get("caseCountByNativeOptimizationStatus")
    if not isinstance(value, dict):
        return None

    counts: dict[str, int] = {}
    for status, count in value.items():
        if (
            not isinstance(status, str)
            or not status
            or isinstance(count, bool)
            or not isinstance(count, int)
            or count < 0
        ):
            return None
        counts[status] = count
    return dict(sorted(counts.items()))


def summary_native_optimization_statuses(report: dict[str, Any]) -> list[str] | None:
    summary = report.get("summary")
    if not isinstance(summary, dict):
        return None
    value = summary.get("nativeOptimizationStatuses")
    if not isinstance(value, list) or any(
        not isinstance(status, str) or not status for status in value
    ):
        return None
    return sorted(value)


def summary_native_optimization_evidence_counts(
    report: dict[str, Any],
) -> dict[str, int] | None:
    summary = report.get("summary")
    if not isinstance(summary, dict):
        return None
    value = summary.get("caseCountByNativeOptimizationEvidenceStatus")
    if not isinstance(value, dict):
        evidence = summary.get("nativeOptimizationEvidence")
        if isinstance(evidence, dict):
            value = evidence.get("caseCountByEvidenceStatus")
    if not isinstance(value, dict):
        return None

    counts: dict[str, int] = {}
    for status, count in value.items():
        if (
            not isinstance(status, str)
            or not status
            or isinstance(count, bool)
            or not isinstance(count, int)
            or count < 0
        ):
            return None
        counts[status] = count
    return dict(sorted(counts.items()))


def summary_native_artifact_descriptor_optimization_status_counts(
    report: dict[str, Any],
) -> dict[str, int] | None:
    summary = report.get("summary")
    if not isinstance(summary, dict):
        return None
    value = summary.get("caseCountByNativeArtifactDescriptorOptimizationStatus")
    if not isinstance(value, dict):
        return None

    counts: dict[str, int] = {}
    for status, count in value.items():
        if (
            not isinstance(status, str)
            or not status
            or isinstance(count, bool)
            or not isinstance(count, int)
            or count < 0
        ):
            return None
        counts[status] = count
    return dict(sorted(counts.items()))


def summary_native_artifact_descriptor_optimization_statuses(
    report: dict[str, Any],
) -> list[str] | None:
    summary = report.get("summary")
    if not isinstance(summary, dict):
        return None
    value = summary.get("nativeArtifactDescriptorOptimizationStatuses")
    if not isinstance(value, list) or any(
        not isinstance(status, str) or not status for status in value
    ):
        return None
    return sorted(value)


def summary_native_artifact_descriptor_optimization_evidence_counts(
    report: dict[str, Any],
) -> dict[str, int] | None:
    summary = report.get("summary")
    if not isinstance(summary, dict):
        return None
    value = summary.get("caseCountByNativeArtifactDescriptorOptimizationEvidenceStatus")
    if not isinstance(value, dict):
        evidence = summary.get("nativeArtifactDescriptorOptimizationEvidence")
        if isinstance(evidence, dict):
            value = evidence.get("caseCountByEvidenceStatus")
    if not isinstance(value, dict):
        return None

    counts: dict[str, int] = {}
    for status, count in value.items():
        if (
            not isinstance(status, str)
            or not status
            or isinstance(count, bool)
            or not isinstance(count, int)
            or count < 0
        ):
            return None
        counts[status] = count
    return dict(sorted(counts.items()))


def status_count_deltas(
    baseline_counts: dict[str, int],
    candidate_counts: dict[str, int],
) -> list[dict[str, Any]]:
    deltas: list[dict[str, Any]] = []
    for status in sorted(set(baseline_counts) | set(candidate_counts)):
        baseline_count = baseline_counts.get(status, 0)
        candidate_count = candidate_counts.get(status, 0)
        delta = candidate_count - baseline_count
        if delta == 0:
            continue
        deltas.append(
            {
                "baselineCount": baseline_count,
                "candidateCount": candidate_count,
                "delta": delta,
                "status": status,
            }
        )
    return deltas


def native_optimization_status_accounting(
    report: dict[str, Any], cases: dict[str, ReportCase]
) -> dict[str, Any]:
    case_counts = count_report_case_field(cases, "native_optimization_status")
    evidence_counts = count_report_case_field(
        cases, "native_optimization_evidence_status"
    )
    descriptor_case_counts = count_report_case_field(
        cases, "native_artifact_descriptor_optimization_status"
    )
    descriptor_evidence_counts = count_report_case_field(
        cases, "native_artifact_descriptor_optimization_evidence_status"
    )
    summary_counts = summary_native_optimization_status_counts(report)
    summary_statuses = summary_native_optimization_statuses(report)
    summary_evidence_counts = summary_native_optimization_evidence_counts(report)
    summary_descriptor_counts = (
        summary_native_artifact_descriptor_optimization_status_counts(report)
    )
    summary_descriptor_statuses = (
        summary_native_artifact_descriptor_optimization_statuses(report)
    )
    summary_descriptor_evidence_counts = (
        summary_native_artifact_descriptor_optimization_evidence_counts(report)
    )
    return {
        "caseCountByEvidenceStatus": evidence_counts,
        "caseCountByStatus": case_counts,
        "caseCountByNativeArtifactDescriptorEvidenceStatus": (
            descriptor_evidence_counts
        ),
        "caseCountByNativeArtifactDescriptorStatus": descriptor_case_counts,
        "descriptorEvidenceCaseCount": sum(descriptor_evidence_counts.values()),
        "descriptorKnownStatusCount": descriptor_evidence_counts.get("known-status", 0),
        "descriptorMissingOptimizationEvidenceCount": (
            descriptor_evidence_counts.get("missing-optimization-evidence", 0)
        ),
        "descriptorMissingOrUnparsableEvidenceCount": (
            descriptor_evidence_counts.get("missing-optimization-evidence", 0)
            + descriptor_evidence_counts.get("unparsable-native-artifact-descriptor", 0)
            + descriptor_evidence_counts.get(
                "declared-native-artifact-descriptor-missing", 0
            )
        ),
        "descriptorNativeArtifactDescriptorDeclaredButMissingCount": (
            descriptor_evidence_counts.get(
                "declared-native-artifact-descriptor-missing", 0
            )
        ),
        "descriptorNativeArtifactDescriptorNotDeclaredCount": (
            descriptor_evidence_counts.get("native-artifact-descriptor-not-declared", 0)
        ),
        "descriptorOptimizationEvidence": (
            native_artifact_descriptor_evidence_summary_from_counts(
                case_count=len(cases), evidence_counts=descriptor_evidence_counts
            )
        ),
        "descriptorOptimizationStatusCaseCount": sum(descriptor_case_counts.values()),
        "descriptorOptimizationStatuses": sorted(descriptor_case_counts),
        "descriptorOptimizationWithoutStatusCount": descriptor_evidence_counts.get(
            "optimization-without-status", 0
        ),
        "descriptorUnparsableNativeArtifactDescriptorCount": (
            descriptor_evidence_counts.get("unparsable-native-artifact-descriptor", 0)
        ),
        "evidenceCaseCount": sum(evidence_counts.values()),
        "knownStatusCount": evidence_counts.get("known-status", 0),
        "missingDebugOptimizationCount": evidence_counts.get(
            "missing-debug-optimization", 0
        ),
        "missingOrUnparsableEvidenceCount": (
            evidence_counts.get("missing-debug-optimization", 0)
            + evidence_counts.get("unparsable-native-profile", 0)
            + evidence_counts.get("declared-native-profile-missing", 0)
        ),
        "nativeProfileDeclaredButMissingCount": evidence_counts.get(
            "declared-native-profile-missing", 0
        ),
        "nativeProfileNotDeclaredCount": evidence_counts.get(
            "native-profile-not-declared", 0
        ),
        "nativeOptimizationStatusCaseCount": sum(case_counts.values()),
        "nativeOptimizationStatuses": sorted(case_counts),
        "optimizationWithoutStatusCount": evidence_counts.get(
            "optimization-without-status", 0
        ),
        "summaryCaseCountByStatus": summary_counts,
        "summaryCountsMatchCases": (
            summary_counts == case_counts if summary_counts is not None else None
        ),
        "summaryCaseCountByEvidenceStatus": summary_evidence_counts,
        "summaryEvidenceCountsMatchCases": (
            summary_evidence_counts == evidence_counts
            if summary_evidence_counts is not None
            else None
        ),
        "summaryCaseCountByNativeArtifactDescriptorStatus": (summary_descriptor_counts),
        "summaryDescriptorCountsMatchCases": (
            summary_descriptor_counts == descriptor_case_counts
            if summary_descriptor_counts is not None
            else None
        ),
        "summaryCaseCountByNativeArtifactDescriptorEvidenceStatus": (
            summary_descriptor_evidence_counts
        ),
        "summaryDescriptorEvidenceCountsMatchCases": (
            summary_descriptor_evidence_counts == descriptor_evidence_counts
            if summary_descriptor_evidence_counts is not None
            else None
        ),
        "summaryNativeArtifactDescriptorOptimizationStatuses": (
            summary_descriptor_statuses
        ),
        "summaryDescriptorStatusesMatchCases": (
            summary_descriptor_statuses == sorted(descriptor_case_counts)
            if summary_descriptor_statuses is not None
            else None
        ),
        "summaryNativeOptimizationStatuses": summary_statuses,
        "summaryStatusesMatchCases": (
            summary_statuses == sorted(case_counts)
            if summary_statuses is not None
            else None
        ),
        "unparsableNativeProfileCount": evidence_counts.get(
            "unparsable-native-profile", 0
        ),
    }


def status_transition_label(
    baseline_status: str | None, candidate_status: str | None
) -> str:
    baseline_label = baseline_status if baseline_status is not None else "unspecified"
    candidate_label = (
        candidate_status if candidate_status is not None else "unspecified"
    )
    return f"{baseline_label} -> {candidate_label}"


def evidence_transition_label(baseline_status: str, candidate_status: str) -> str:
    return f"{baseline_status} -> {candidate_status}"


def native_artifact_descriptor_evidence_field_drifts(
    baseline_evidence: dict[str, Any] | None,
    candidate_evidence: dict[str, Any] | None,
) -> list[dict[str, Any]]:
    baseline = baseline_evidence or {}
    candidate = candidate_evidence or {}
    drifts: list[dict[str, Any]] = []
    for field in sorted(set(baseline) | set(candidate)):
        baseline_value = baseline.get(field)
        candidate_value = candidate.get(field)
        if baseline_value == candidate_value:
            continue
        drifts.append(
            {
                "field": field,
                "baseline": baseline_value,
                "candidate": candidate_value,
            }
        )
    return drifts


def native_optimization_status_drift_report(
    baseline_report: dict[str, Any],
    candidate_report: dict[str, Any],
    baseline_cases: dict[str, ReportCase],
    candidate_cases: dict[str, ReportCase],
) -> dict[str, Any]:
    baseline_accounting = native_optimization_status_accounting(
        baseline_report, baseline_cases
    )
    candidate_accounting = native_optimization_status_accounting(
        candidate_report, candidate_cases
    )
    status_drifts: list[dict[str, Any]] = []
    transition_counts: dict[str, int] = {}
    evidence_drifts: list[dict[str, Any]] = []
    evidence_transition_counts: dict[str, int] = {}
    descriptor_status_drifts: list[dict[str, Any]] = []
    descriptor_transition_counts: dict[str, int] = {}
    descriptor_evidence_drifts: list[dict[str, Any]] = []
    descriptor_evidence_transition_counts: dict[str, int] = {}
    descriptor_field_drifts: list[dict[str, Any]] = []
    descriptor_field_drift_counts: dict[str, int] = {}

    for key in sorted(set(baseline_cases) & set(candidate_cases)):
        baseline_case = baseline_cases[key]
        candidate_case = candidate_cases[key]
        baseline_status = baseline_case.native_optimization_status
        candidate_status = candidate_case.native_optimization_status
        if baseline_status != candidate_status:
            transition = status_transition_label(baseline_status, candidate_status)
            add_count(transition_counts, transition)
            status_drifts.append(
                {
                    "baselineStatus": baseline_status,
                    "candidateStatus": candidate_status,
                    "case": key,
                    "caseContext": case_comparison_context(
                        baseline_case, candidate_case
                    ),
                    "transition": transition,
                }
            )

        baseline_evidence = baseline_case.native_optimization_evidence_status
        candidate_evidence = candidate_case.native_optimization_evidence_status
        if baseline_evidence != candidate_evidence:
            evidence_transition = evidence_transition_label(
                baseline_evidence, candidate_evidence
            )
            add_count(evidence_transition_counts, evidence_transition)
            evidence_drifts.append(
                {
                    "baselineEvidenceStatus": baseline_evidence,
                    "candidateEvidenceStatus": candidate_evidence,
                    "case": key,
                    "caseContext": case_comparison_context(
                        baseline_case, candidate_case
                    ),
                    "transition": evidence_transition,
                }
            )

        baseline_descriptor_status = (
            baseline_case.native_artifact_descriptor_optimization_status
        )
        candidate_descriptor_status = (
            candidate_case.native_artifact_descriptor_optimization_status
        )
        if baseline_descriptor_status != candidate_descriptor_status:
            descriptor_transition = status_transition_label(
                baseline_descriptor_status, candidate_descriptor_status
            )
            add_count(descriptor_transition_counts, descriptor_transition)
            descriptor_status_drifts.append(
                {
                    "baselineStatus": baseline_descriptor_status,
                    "candidateStatus": candidate_descriptor_status,
                    "case": key,
                    "caseContext": case_comparison_context(
                        baseline_case, candidate_case
                    ),
                    "transition": descriptor_transition,
                }
            )

        baseline_descriptor_evidence = (
            baseline_case.native_artifact_descriptor_optimization_evidence_status
        )
        candidate_descriptor_evidence = (
            candidate_case.native_artifact_descriptor_optimization_evidence_status
        )
        if baseline_descriptor_evidence != candidate_descriptor_evidence:
            descriptor_evidence_transition = evidence_transition_label(
                baseline_descriptor_evidence, candidate_descriptor_evidence
            )
            add_count(
                descriptor_evidence_transition_counts, descriptor_evidence_transition
            )
            descriptor_evidence_drifts.append(
                {
                    "baselineEvidenceStatus": baseline_descriptor_evidence,
                    "candidateEvidenceStatus": candidate_descriptor_evidence,
                    "case": key,
                    "caseContext": case_comparison_context(
                        baseline_case, candidate_case
                    ),
                    "transition": descriptor_evidence_transition,
                }
            )

        field_drifts = native_artifact_descriptor_evidence_field_drifts(
            baseline_case.native_artifact_descriptor_optimization_evidence,
            candidate_case.native_artifact_descriptor_optimization_evidence,
        )
        if field_drifts:
            for drift in field_drifts:
                field = drift["field"]
                if isinstance(field, str):
                    add_count(descriptor_field_drift_counts, field)
            descriptor_field_drifts.append(
                {
                    "case": key,
                    "caseContext": case_comparison_context(
                        baseline_case, candidate_case
                    ),
                    "fieldDriftCount": len(field_drifts),
                    "fieldDrifts": field_drifts,
                }
            )

    baseline_summary_counts = baseline_accounting["summaryCaseCountByStatus"]
    candidate_summary_counts = candidate_accounting["summaryCaseCountByStatus"]
    summary_count_deltas_available = isinstance(
        baseline_summary_counts, dict
    ) and isinstance(candidate_summary_counts, dict)
    baseline_summary_evidence_counts = baseline_accounting[
        "summaryCaseCountByEvidenceStatus"
    ]
    candidate_summary_evidence_counts = candidate_accounting[
        "summaryCaseCountByEvidenceStatus"
    ]
    summary_evidence_deltas_available = isinstance(
        baseline_summary_evidence_counts, dict
    ) and isinstance(candidate_summary_evidence_counts, dict)
    baseline_summary_descriptor_counts = baseline_accounting[
        "summaryCaseCountByNativeArtifactDescriptorStatus"
    ]
    candidate_summary_descriptor_counts = candidate_accounting[
        "summaryCaseCountByNativeArtifactDescriptorStatus"
    ]
    summary_descriptor_deltas_available = isinstance(
        baseline_summary_descriptor_counts, dict
    ) and isinstance(candidate_summary_descriptor_counts, dict)
    baseline_summary_descriptor_evidence_counts = baseline_accounting[
        "summaryCaseCountByNativeArtifactDescriptorEvidenceStatus"
    ]
    candidate_summary_descriptor_evidence_counts = candidate_accounting[
        "summaryCaseCountByNativeArtifactDescriptorEvidenceStatus"
    ]
    summary_descriptor_evidence_deltas_available = isinstance(
        baseline_summary_descriptor_evidence_counts, dict
    ) and isinstance(candidate_summary_descriptor_evidence_counts, dict)

    return {
        "advisory": True,
        "baseline": baseline_accounting,
        "candidate": candidate_accounting,
        "caseCountByEvidenceStatusDeltas": status_count_deltas(
            baseline_accounting["caseCountByEvidenceStatus"],
            candidate_accounting["caseCountByEvidenceStatus"],
        ),
        "caseCountByNativeArtifactDescriptorEvidenceStatusDeltas": (
            status_count_deltas(
                baseline_accounting[
                    "caseCountByNativeArtifactDescriptorEvidenceStatus"
                ],
                candidate_accounting[
                    "caseCountByNativeArtifactDescriptorEvidenceStatus"
                ],
            )
        ),
        "caseCountByNativeArtifactDescriptorStatusDeltas": status_count_deltas(
            baseline_accounting["caseCountByNativeArtifactDescriptorStatus"],
            candidate_accounting["caseCountByNativeArtifactDescriptorStatus"],
        ),
        "caseCountByStatusDeltas": status_count_deltas(
            baseline_accounting["caseCountByStatus"],
            candidate_accounting["caseCountByStatus"],
        ),
        "comparableCaseCount": len(set(baseline_cases) & set(candidate_cases)),
        "descriptorEvidenceDriftCount": len(descriptor_evidence_drifts),
        "descriptorEvidenceDrifts": descriptor_evidence_drifts,
        "descriptorEvidenceTransitionCounts": sorted_counts(
            descriptor_evidence_transition_counts
        ),
        "descriptorFieldDriftCount": len(descriptor_field_drifts),
        "descriptorFieldDriftCounts": sorted_counts(descriptor_field_drift_counts),
        "descriptorFieldDrifts": descriptor_field_drifts,
        "descriptorStatusDriftCount": len(descriptor_status_drifts),
        "descriptorStatusDrifts": descriptor_status_drifts,
        "descriptorStatusTransitionCounts": sorted_counts(descriptor_transition_counts),
        "evidenceDriftCount": len(evidence_drifts),
        "evidenceDrifts": evidence_drifts,
        "evidenceTransitionCounts": sorted_counts(evidence_transition_counts),
        "mode": "report-only",
        "policy": (
            "Native optimization status, descriptor optimizer evidence, and "
            "evidence-coverage drift are report-only evidence. They never "
            "change comparator exit status unless the existing structural or "
            "functional report policies fail for another reason."
        ),
        "status": (
            "drift-detected"
            if (
                status_drifts
                or evidence_drifts
                or descriptor_status_drifts
                or descriptor_evidence_drifts
                or descriptor_field_drifts
            )
            else "unchanged"
        ),
        "statusDriftCount": len(status_drifts),
        "statusDrifts": status_drifts,
        "statusTransitionCounts": sorted_counts(transition_counts),
        "summaryCountByStatusDeltas": (
            status_count_deltas(baseline_summary_counts, candidate_summary_counts)
            if summary_count_deltas_available
            else []
        ),
        "summaryCountDeltaReport": (
            "available"
            if summary_count_deltas_available
            else "missing-or-invalid-summary-counts"
        ),
        "summaryCountByEvidenceStatusDeltas": (
            status_count_deltas(
                baseline_summary_evidence_counts, candidate_summary_evidence_counts
            )
            if summary_evidence_deltas_available
            else []
        ),
        "summaryEvidenceCountDeltaReport": (
            "available"
            if summary_evidence_deltas_available
            else "missing-or-invalid-summary-counts"
        ),
        "summaryCountByNativeArtifactDescriptorStatusDeltas": (
            status_count_deltas(
                baseline_summary_descriptor_counts,
                candidate_summary_descriptor_counts,
            )
            if summary_descriptor_deltas_available
            else []
        ),
        "summaryDescriptorCountDeltaReport": (
            "available"
            if summary_descriptor_deltas_available
            else "missing-or-invalid-summary-counts"
        ),
        "summaryCountByNativeArtifactDescriptorEvidenceStatusDeltas": (
            status_count_deltas(
                baseline_summary_descriptor_evidence_counts,
                candidate_summary_descriptor_evidence_counts,
            )
            if summary_descriptor_evidence_deltas_available
            else []
        ),
        "summaryDescriptorEvidenceCountDeltaReport": (
            "available"
            if summary_descriptor_evidence_deltas_available
            else "missing-or-invalid-summary-counts"
        ),
    }


def report_artifact_expectations() -> dict[str, Any]:
    return {
        "comparisonReport": {
            "format": "json",
            "failureSurfaces": {
                "hardFail": ["structure"],
                "reportOnly": [
                    "timing",
                    "artifactSize",
                    "nativeOptimization",
                    "metadata.baselinePolicy",
                ],
            },
            "schemaVersion": SCHEMA_VERSION,
            "requiredTopLevelFields": list(REPORT_ARTIFACT_TOP_LEVEL_FIELDS),
            "statusPolicy": (
                "Only structural report-shape failures change comparator exit "
                "status in v0."
            ),
        },
        "structure": {
            "path": "structure",
            "failureMode": "hard-fail",
            "requiredFields": [
                "failed",
                "failureMode",
                "failureReasons",
                "missingCaseCount",
                "missingCases",
                "missingCategoryCount",
                "missingCategories",
                "missingCommandProfileCount",
                "missingCommandProfiles",
                "missingTargetCount",
                "missingTargets",
                "mode",
                "newSkippedCaseCount",
                "newSkippedCases",
                "validationIssueCount",
                "validationIssues",
            ],
        },
        "timingAdvisory": {
            "path": "timing",
            "failureMode": "report-only",
            "deltaPath": "timing.timingDeltas",
            "defaultDeltaReport": "regressions-only",
            "evidencePath": "timing.advisoryEvidencePolicy",
            "explicitThresholdPolicy": "report-only",
            "releaseBlockerPolicy": TIMING_ADVISORY_RELEASE_BLOCKER_POLICY,
            "advisoryThresholdsPath": "timing.advisoryThresholds",
            "thresholdProposalLayerPath": "timing.thresholdProposalLayer",
            "warningSummaryPath": "timing.warningSummary",
            "requiredFields": [
                "advisoryEvidencePolicy",
                "advisoryThresholdPolicy",
                "advisoryThresholds",
                "deltaReport",
                "evidenceSufficiency",
                "explicitThresholdPolicy",
                "failedRegressionCount",
                "policy",
                "thresholdProposalLayer",
                "warningSummary",
            ],
            "sufficiencyPath": "timing.evidenceSufficiency",
            "thresholdPolicyPath": "timing.advisoryThresholdPolicy",
        },
        "artifactSizeAdvisory": {
            "path": "artifactSize",
            "failureMode": "report-only",
            "deltaPath": "artifactSize.sizeDeltas",
            "defaultDeltaReport": "increases-only",
            "explicitHardPolicy": "not-supported-v0-report-only",
            "manifestArtifactKindEvidencePath": (
                "artifactSize.manifestArtifactKindEvidence"
            ),
            "warningSummaryPath": "artifactSize.warningSummary",
            "requiredFields": [
                "advisoryIncreaseCount",
                "manifestArtifactKindEvidence",
                "policy",
                "sizeDeltaCount",
                "unsizedCaseCount",
                "warningSummary",
            ],
        },
        "nativeOptimizationAdvisory": {
            "path": "nativeOptimization",
            "failureMode": "report-only",
            "deltaPath": "nativeOptimization.statusDrifts",
            "requiredFields": [
                "baseline",
                "candidate",
                "descriptorFieldDriftCount",
                "descriptorFieldDrifts",
                "descriptorStatusDriftCount",
                "descriptorStatusDrifts",
                "policy",
                "statusDriftCount",
                "statusDrifts",
            ],
        },
        "baselinePolicyAdvisory": {
            "path": "metadata.baselinePolicy",
            "failureMode": "report-only",
            "requiredFields": [
                "compatibility",
                "comparisonDimensions",
                "producerClaims",
                "readiness",
                "stability",
            ],
        },
    }


def compare_reports(
    baseline_path: Path,
    candidate_path: Path,
    *,
    include_timing_deltas: bool,
    include_size_deltas: bool,
    max_regression_percent: Decimal | None,
    advisory_threshold_profile_name: str = DEFAULT_ADVISORY_THRESHOLD_PROFILE,
    advisory_threshold_policy_path: Path | None = None,
) -> dict[str, Any]:
    advisory_threshold_profile, advisory_threshold_source = (
        resolve_advisory_threshold_profile(
            profile_name=advisory_threshold_profile_name,
            policy_path=advisory_threshold_policy_path,
        )
    )
    baseline = load_json_report(baseline_path)
    candidate = load_json_report(candidate_path)
    baseline_case_validation_issues: list[str] = []
    candidate_case_validation_issues: list[str] = []
    baseline_cases = report_cases(
        baseline, "baseline", validation_issues=baseline_case_validation_issues
    )
    candidate_cases = report_cases(
        candidate, "candidate", validation_issues=candidate_case_validation_issues
    )

    baseline_keys = set(baseline_cases)
    candidate_keys = set(candidate_cases)
    baseline_categories = {case.category for case in baseline_cases.values()}
    candidate_categories = {case.category for case in candidate_cases.values()}
    baseline_command_profiles = report_command_profiles(baseline, baseline_cases)
    candidate_command_profiles = report_command_profiles(candidate, candidate_cases)
    baseline_profiles = report_profiles(baseline, baseline_cases)
    candidate_profiles = report_profiles(candidate, candidate_cases)
    baseline_targets = report_targets(baseline, baseline_cases)
    candidate_targets = report_targets(candidate, candidate_cases)
    baseline_skipped_cases = skipped_cases(baseline_cases)
    candidate_skipped_cases = skipped_cases(candidate_cases)
    baseline_functional_failures = functional_failure_cases(baseline_cases)
    candidate_functional_failures = functional_failure_cases(candidate_cases)
    baseline_toolchain_labels = report_toolchain_labels(baseline, baseline_cases)
    candidate_toolchain_labels = report_toolchain_labels(candidate, candidate_cases)
    baseline_unavailable_toolchain_labels = report_unavailable_toolchain_labels(
        baseline, baseline_cases
    )
    candidate_unavailable_toolchain_labels = report_unavailable_toolchain_labels(
        candidate, candidate_cases
    )
    baseline_policy_metadata = report_policy_metadata(baseline, baseline_cases)
    candidate_policy_metadata = report_policy_metadata(candidate, candidate_cases)
    policy_metadata_comparison = compare_policy_metadata(
        baseline_policy_metadata, candidate_policy_metadata
    )
    baseline_validation_issues = baseline_case_validation_issues + (
        report_validation_issues(baseline, baseline_cases, "baseline")
    )
    candidate_validation_issues = candidate_case_validation_issues + (
        report_validation_issues(candidate, candidate_cases, "candidate")
    )
    baseline_readiness = baseline_readiness_report(
        baseline_policy_metadata, baseline_cases, baseline_validation_issues
    )
    candidate_readiness = baseline_readiness_report(
        candidate_policy_metadata, candidate_cases, candidate_validation_issues
    )
    compatible_ready_pair = (
        baseline_readiness["readyForThresholdBaseline"]
        and candidate_readiness["readyForThresholdBaseline"]
        and policy_metadata_comparison["compatible"]
    )
    baseline_producer_claims = producer_policy_claims_report(
        baseline, baseline_readiness
    )
    candidate_producer_claims = producer_policy_claims_report(
        candidate, candidate_readiness
    )
    producer_claim_summary = producer_claims_pair_summary(
        baseline_producer_claims,
        candidate_producer_claims,
        compatible_ready_pair=compatible_ready_pair,
    )

    missing_cases = sorted(baseline_keys - candidate_keys)
    added_cases = sorted(candidate_keys - baseline_keys)
    missing_categories = sorted(baseline_categories - candidate_categories)
    added_categories = sorted(candidate_categories - baseline_categories)
    missing_command_profiles = sorted(
        baseline_command_profiles - candidate_command_profiles
    )
    added_command_profiles = sorted(
        candidate_command_profiles - baseline_command_profiles
    )
    missing_profiles = sorted(baseline_profiles - candidate_profiles)
    added_profiles = sorted(candidate_profiles - baseline_profiles)
    missing_targets = sorted(baseline_targets - candidate_targets)
    added_targets = sorted(candidate_targets - baseline_targets)
    new_skipped_cases = sorted(
        key for key in candidate_skipped_cases if key not in baseline_skipped_cases
    )
    resolved_skipped_cases = sorted(
        key for key in baseline_skipped_cases if key not in candidate_skipped_cases
    )
    changed_skip_reasons = [
        {
            "case": key,
            "baselineSkipReason": baseline_skipped_cases[key],
            "candidateSkipReason": candidate_skipped_cases[key],
        }
        for key in sorted(set(baseline_skipped_cases) & set(candidate_skipped_cases))
        if baseline_skipped_cases[key] != candidate_skipped_cases[key]
    ]
    changed_command_profiles = [
        {
            "case": key,
            "baselineCommandProfile": baseline_cases[key].command_profile,
            "candidateCommandProfile": candidate_cases[key].command_profile,
        }
        for key in sorted(baseline_keys & candidate_keys)
        if baseline_cases[key].command_profile != candidate_cases[key].command_profile
    ]
    changed_case_categories = [
        {
            "case": key,
            "baselineCategory": baseline_cases[key].category,
            "candidateCategory": candidate_cases[key].category,
        }
        for key in sorted(baseline_keys & candidate_keys)
        if baseline_cases[key].category != candidate_cases[key].category
    ]
    changed_report_case_labels = [
        {
            "case": key,
            "baselineReportCase": baseline_cases[key].report_key,
            "candidateReportCase": candidate_cases[key].report_key,
        }
        for key in sorted(baseline_keys & candidate_keys)
        if baseline_cases[key].report_key != candidate_cases[key].report_key
    ]
    new_functional_failure_cases = sorted(
        key
        for key in candidate_functional_failures
        if key not in baseline_functional_failures
    )
    resolved_functional_failure_cases = sorted(
        key
        for key in baseline_functional_failures
        if key not in candidate_functional_failures
    )
    changed_functional_failure_statuses = [
        {
            "case": key,
            "baselineStatus": baseline_functional_failures[key],
            "candidateStatus": candidate_functional_failures[key],
        }
        for key in sorted(
            set(baseline_functional_failures) & set(candidate_functional_failures)
        )
        if baseline_functional_failures[key] != candidate_functional_failures[key]
    ]
    missing_toolchain_labels = sorted(
        baseline_toolchain_labels - candidate_toolchain_labels
    )
    added_toolchain_labels = sorted(
        candidate_toolchain_labels - baseline_toolchain_labels
    )
    new_unavailable_toolchain_labels = sorted(
        candidate_unavailable_toolchain_labels - baseline_unavailable_toolchain_labels
    )
    resolved_unavailable_toolchain_labels = sorted(
        baseline_unavailable_toolchain_labels - candidate_unavailable_toolchain_labels
    )
    baseline_toolchain_classifications = toolchain_classifications(
        baseline_policy_metadata.toolchains
    )
    candidate_toolchain_classifications = toolchain_classifications(
        candidate_policy_metadata.toolchains
    )
    changed_toolchain_classifications = [
        {
            "toolchain": label,
            "baseline": baseline_toolchain_classifications[label],
            "candidate": candidate_toolchain_classifications[label],
        }
        for label in sorted(
            set(baseline_toolchain_classifications)
            & set(candidate_toolchain_classifications)
        )
        if baseline_toolchain_classifications[label]
        != candidate_toolchain_classifications[label]
    ]
    new_optional_unavailable_toolchain_labels = sorted(
        label
        for label in new_unavailable_toolchain_labels
        if toolchain_is_optional(candidate_toolchain_classifications, label)
    )
    new_required_unavailable_toolchain_labels = sorted(
        label
        for label in new_unavailable_toolchain_labels
        if not toolchain_is_optional(candidate_toolchain_classifications, label)
    )
    comparable_case_count = 0
    untimed_cases: list[str] = []
    advisory_regressions: list[dict[str, Any]] = []
    explicit_threshold_exceeded_regressions: list[dict[str, Any]] = []
    advisory_threshold_exceeded_regressions: list[dict[str, Any]] = []
    advisory_threshold_matched_case_count = 0
    advisory_threshold_claim_eligible_case_count = 0
    advisory_threshold_claim_disposition_counts: dict[str, int] = {}
    advisory_threshold_insufficient_evidence_cases: list[str] = []
    advisory_threshold_measured_exceeded_cases: list[str] = []
    advisory_threshold_rule_specificity_counts: dict[str, int] = {}
    advisory_threshold_unmatched_cases: list[str] = []
    timing_claim_eligible_case_count = 0
    timing_claim_eligibility_disposition_counts: dict[str, int] = {}
    timing_case_identity_incomplete_cases: list[str] = []
    timing_insufficient_evidence_cases: list[str] = []
    timing_policy_disposition_counts: dict[str, int] = {}
    timing_deltas: list[dict[str, Any]] = []
    threshold_proposal_observations: list[dict[str, Any]] = []
    explicit_threshold_claim_disposition_counts: dict[str, int] = {}
    explicit_threshold_measured_exceeded_cases: list[str] = []
    comparable_size_case_count = 0
    unsized_cases: list[str] = []
    advisory_size_increases: list[dict[str, Any]] = []
    size_deltas: list[dict[str, Any]] = []
    manifest_artifact_kind_case_count = 0
    manifest_artifact_kind_deltas: list[dict[str, Any]] = []
    manifest_artifact_kind_unreported_cases: list[str] = []
    advisory_context = advisory_context_report(
        baseline_policy_metadata, candidate_policy_metadata
    )
    timing_metadata_evidence = timing_metadata_comparability_evidence(
        baseline_policy_metadata,
        candidate_policy_metadata,
        policy_metadata_comparison,
    )
    native_optimization_drift = native_optimization_status_drift_report(
        baseline, candidate, baseline_cases, candidate_cases
    )

    for key in sorted(baseline_keys & candidate_keys):
        baseline_case = baseline_cases[key]
        candidate_case = candidate_cases[key]
        case_context = case_comparison_context(baseline_case, candidate_case)

        baseline_elapsed = baseline_case.elapsed_ns
        candidate_elapsed = candidate_case.elapsed_ns
        if baseline_elapsed is None or candidate_elapsed is None:
            untimed_cases.append(key)
        else:
            comparable_case_count += 1

            entry = timing_entry(
                key,
                baseline_elapsed,
                candidate_elapsed,
                threshold_percent=max_regression_percent,
            )
            entry["caseContext"] = case_context
            timing_evidence = timing_advisory_claim_evidence(
                baseline_case,
                candidate_case,
                timing_metadata_evidence,
            )
            add_count(
                timing_claim_eligibility_disposition_counts,
                timing_evidence["claimEligibilityDisposition"],
            )
            if timing_evidence["caseIdentityComplete"] is not True:
                timing_case_identity_incomplete_cases.append(key)
            apply_explicit_threshold_evidence(entry, timing_evidence)
            if entry["explicitThreshold"] is not None:
                add_count(
                    explicit_threshold_claim_disposition_counts,
                    entry["explicitThreshold"]["claimDisposition"],
                )
                if entry["measuredExceedsExplicitThreshold"]:
                    explicit_threshold_measured_exceeded_cases.append(key)
            if timing_evidence["sufficientForTimingAdvisoryClaim"]:
                timing_claim_eligible_case_count += 1
            else:
                timing_insufficient_evidence_cases.append(key)
            if annotate_advisory_threshold(
                entry,
                baseline_case,
                advisory_threshold_profile,
                timing_evidence,
            ):
                advisory_threshold_matched_case_count += 1
                if timing_evidence["sufficientForAdvisoryThresholdClaim"]:
                    advisory_threshold_claim_eligible_case_count += 1
                else:
                    advisory_threshold_insufficient_evidence_cases.append(key)
                add_count(
                    advisory_threshold_claim_disposition_counts,
                    entry["advisoryThreshold"]["claimDisposition"],
                )
                add_count(
                    advisory_threshold_rule_specificity_counts,
                    entry["advisoryThreshold"]["ruleSpecificity"],
                )
                if entry["measuredExceedsAdvisoryThreshold"]:
                    advisory_threshold_measured_exceeded_cases.append(key)
            elif advisory_threshold_profile.rules:
                advisory_threshold_unmatched_cases.append(key)

            if entry["exceedsAdvisoryThreshold"]:
                advisory_threshold_exceeded_regressions.append(entry)

            if entry["exceedsExplicitThreshold"]:
                explicit_threshold_exceeded_regressions.append(entry)

            if candidate_elapsed <= baseline_elapsed:
                if include_timing_deltas:
                    timing_deltas.append(entry)
            else:
                entry["currentPolicyDisposition"] = regression_policy_disposition(
                    timing_evidence,
                    explicit_threshold_enabled=max_regression_percent is not None,
                    explicit_threshold_exceeded=entry["exceedsExplicitThreshold"],
                )
                advisory_regressions.append(entry)
                if include_timing_deltas:
                    timing_deltas.append(entry)
            add_count(
                timing_policy_disposition_counts,
                entry["currentPolicyDisposition"],
            )
            threshold_proposal_observations.append(
                threshold_proposal_observation(entry, baseline_case, candidate_case)
            )

        if baseline_case.artifact_kind_metrics or candidate_case.artifact_kind_metrics:
            manifest_artifact_kind_case_count += 1
            kind_entry = manifest_artifact_kind_delta_entry(
                key,
                baseline_case.artifact_kind_metrics,
                candidate_case.artifact_kind_metrics,
            )
            kind_entry["caseContext"] = case_context
            if kind_entry["kindDeltaCount"] > 0:
                manifest_artifact_kind_deltas.append(kind_entry)
        else:
            manifest_artifact_kind_unreported_cases.append(key)

        baseline_size = baseline_case.artifact_byte_size
        candidate_size = candidate_case.artifact_byte_size
        if baseline_size is None or candidate_size is None:
            unsized_cases.append(key)
            continue

        comparable_size_case_count += 1
        size_entry = artifact_size_entry(
            key,
            baseline_size,
            candidate_size,
            baseline_file_count=baseline_case.artifact_file_count,
            candidate_file_count=candidate_case.artifact_file_count,
        )
        size_entry["caseContext"] = case_context
        if size_entry["deltaBytes"] > 0:
            advisory_size_increases.append(size_entry)
        if include_size_deltas:
            size_deltas.append(size_entry)

    baseline_stability = pairwise_baseline_stability_report(
        baseline_path,
        candidate_path,
        baseline_policy_metadata,
        candidate_policy_metadata,
        baseline_cases,
        candidate_cases,
        baseline_readiness,
        candidate_readiness,
        policy_metadata_comparison,
    )

    structural_failure = bool(
        missing_cases
        or missing_categories
        or missing_command_profiles
        or changed_case_categories
        or changed_command_profiles
        or missing_profiles
        or missing_targets
        or new_skipped_cases
        or changed_skip_reasons
        or candidate_functional_failures
        or missing_toolchain_labels
        or new_required_unavailable_toolchain_labels
        or baseline_validation_issues
        or candidate_validation_issues
    )
    timing_failure = False
    status = "fail" if structural_failure else "pass"
    failure_priority = [
        label
        for label, failed in (
            ("structural", structural_failure),
            ("timing", timing_failure),
        )
        if failed
    ]
    failure_class = failure_priority[0] if failure_priority else "pass"
    structural_failure_reasons = [
        name
        for name, failed in (
            ("missingCases", bool(missing_cases)),
            ("missingCategories", bool(missing_categories)),
            ("missingCommandProfiles", bool(missing_command_profiles)),
            ("changedCaseCategories", bool(changed_case_categories)),
            ("changedCommandProfiles", bool(changed_command_profiles)),
            ("missingProfiles", bool(missing_profiles)),
            ("missingTargets", bool(missing_targets)),
            ("newSkippedCases", bool(new_skipped_cases)),
            ("changedSkipReasons", bool(changed_skip_reasons)),
            ("candidateFunctionalFailures", bool(candidate_functional_failures)),
            ("missingToolchainLabels", bool(missing_toolchain_labels)),
            (
                "newRequiredUnavailableToolchains",
                bool(new_required_unavailable_toolchain_labels),
            ),
            ("baselineValidationIssues", bool(baseline_validation_issues)),
            ("candidateValidationIssues", bool(candidate_validation_issues)),
        )
        if failed
    ]

    advisory_threshold_profile_summary = advisory_threshold_profile_report(
        advisory_threshold_profile,
        claim_eligible_case_count=advisory_threshold_claim_eligible_case_count,
        claim_disposition_counts=advisory_threshold_claim_disposition_counts,
        rule_specificity_counts=advisory_threshold_rule_specificity_counts,
        insufficient_evidence_cases=advisory_threshold_insufficient_evidence_cases,
        matched_case_count=advisory_threshold_matched_case_count,
        measured_threshold_exceeded_cases=(advisory_threshold_measured_exceeded_cases),
        unmatched_cases=advisory_threshold_unmatched_cases,
    )
    advisory_threshold_policy_summary = advisory_threshold_policy_report(
        advisory_threshold_profile,
        claim_eligible_case_count=advisory_threshold_claim_eligible_case_count,
        claim_disposition_counts=advisory_threshold_claim_disposition_counts,
        rule_specificity_counts=advisory_threshold_rule_specificity_counts,
        insufficient_evidence_cases=advisory_threshold_insufficient_evidence_cases,
        matched_case_count=advisory_threshold_matched_case_count,
        measured_threshold_exceeded_cases=(advisory_threshold_measured_exceeded_cases),
        metadata_evidence=timing_metadata_evidence,
        threshold_exceeded_count=len(advisory_threshold_exceeded_regressions),
    )
    advisory_thresholds_summary = advisory_thresholds_report(
        advisory_threshold_profile,
        advisory_threshold_source,
        profile_report=advisory_threshold_profile_summary,
        policy_report=advisory_threshold_policy_summary,
        threshold_exceeded_cases=[
            entry["case"] for entry in advisory_threshold_exceeded_regressions
        ],
    )
    policy_timing_advisory_thresholds = {
        "baselineMissingFields": timing_metadata_evidence["baselineMissingFields"],
        "candidateMissingFields": timing_metadata_evidence["candidateMissingFields"],
        "claimEligibleCaseCount": advisory_threshold_claim_eligible_case_count,
        "enforcement": threshold_enforcement_json(),
        "failureMode": "report-only",
        "matchedCaseCount": advisory_threshold_matched_case_count,
        "measuredThresholdExceededCount": len(
            advisory_threshold_measured_exceeded_cases
        ),
        "metadataCompatible": timing_metadata_evidence["metadataCompatible"],
        "metadataMismatchCount": policy_metadata_comparison["mismatchCount"],
        "minimumSampleCount": TIMING_ADVISORY_MIN_SAMPLE_COUNT,
        "mode": "report-only",
        "profile": advisory_threshold_profile.name,
        "releaseBlockerPolicy": TIMING_ADVISORY_RELEASE_BLOCKER_POLICY,
        "requiredMetadataFields": list(REQUIRED_ADVISORY_CONTEXT_FIELDS),
        "requiresComparableMetadata": True,
        "requiresExplicitTimedCaseIdentity": True,
        "requiresRepeatedBaselineAndCandidateSamples": True,
        "ruleSpecificityCounts": sorted_counts(
            advisory_threshold_rule_specificity_counts
        ),
        "source": advisory_threshold_source,
        "thresholdExceededCount": len(advisory_threshold_exceeded_regressions),
    }
    timing_evidence_sufficiency = {
        "advisory": True,
        "advisoryThresholdClaimedExceededCaseCount": len(
            advisory_threshold_exceeded_regressions
        ),
        "advisoryThresholdClaimedExceededCases": [
            entry["case"] for entry in advisory_threshold_exceeded_regressions
        ],
        "advisoryThresholdMeasuredExceededCaseCount": len(
            advisory_threshold_measured_exceeded_cases
        ),
        "advisoryThresholdMeasuredExceededCases": (
            advisory_threshold_measured_exceeded_cases
        ),
        "claimEligibleCaseCount": timing_claim_eligible_case_count,
        "claimEligibilityDispositionCounts": sorted_counts(
            timing_claim_eligibility_disposition_counts
        ),
        "caseIdentityIncompleteCaseCount": len(timing_case_identity_incomplete_cases),
        "caseIdentityIncompleteCases": timing_case_identity_incomplete_cases,
        "caseIdentityRequiredFields": list(REQUIRED_THRESHOLD_CASE_IDENTITY_FIELDS),
        "currentPolicyDispositionCounts": sorted_counts(
            timing_policy_disposition_counts
        ),
        "explicitThresholdClaimedExceededCaseCount": len(
            explicit_threshold_exceeded_regressions
        ),
        "explicitThresholdClaimedExceededCases": [
            entry["case"] for entry in explicit_threshold_exceeded_regressions
        ],
        "explicitThresholdMeasuredExceededCaseCount": len(
            explicit_threshold_measured_exceeded_cases
        ),
        "explicitThresholdMeasuredExceededCases": (
            explicit_threshold_measured_exceeded_cases
        ),
        "enforcement": threshold_enforcement_json(),
        "insufficientEvidenceCaseCount": len(timing_insufficient_evidence_cases),
        "insufficientEvidenceCases": timing_insufficient_evidence_cases,
        "metadataComparability": timing_metadata_evidence,
        "metadataCompatible": timing_metadata_evidence["compatible"],
        "minimumSampleCount": TIMING_ADVISORY_MIN_SAMPLE_COUNT,
        "mode": "report-only",
        "policy": TIMING_ADVISORY_EVIDENCE_POLICY,
        "releaseBlockerPolicy": TIMING_ADVISORY_RELEASE_BLOCKER_POLICY,
        "requiresComparableMetadata": True,
        "requiresExplicitTimedCaseIdentity": True,
        "requiresRepeatedBaselineAndCandidateSamples": True,
        "timingObservationCaseCount": comparable_case_count,
    }
    threshold_proposal_layer = threshold_proposal_layer_report(
        baseline_metadata=baseline_policy_metadata,
        candidate_metadata=candidate_policy_metadata,
        structural_failure=structural_failure,
        structural_failure_reasons=structural_failure_reasons,
        baseline_readiness=baseline_readiness,
        candidate_readiness=candidate_readiness,
        timing_metadata_evidence=timing_metadata_evidence,
        timing_evidence_sufficiency=timing_evidence_sufficiency,
        observations=threshold_proposal_observations,
    )
    metadata_advisory_summary = advisory_warning_summary(
        baseline_policy_metadata,
        candidate_policy_metadata,
        policy_metadata_comparison,
    )
    timing_warnings = timing_warning_summary(
        advisory_regressions=advisory_regressions,
        advisory_threshold_measured_exceeded_cases=(
            advisory_threshold_measured_exceeded_cases
        ),
        advisory_threshold_exceeded_regressions=(
            advisory_threshold_exceeded_regressions
        ),
        explicit_threshold_measured_exceeded_cases=(
            explicit_threshold_measured_exceeded_cases
        ),
        explicit_threshold_exceeded_regressions=(
            explicit_threshold_exceeded_regressions
        ),
        timing_insufficient_evidence_cases=timing_insufficient_evidence_cases,
        untimed_cases=untimed_cases,
    )
    artifact_size_warnings = artifact_size_warning_summary(
        advisory_size_increases=advisory_size_increases,
        unsized_cases=unsized_cases,
    )

    return {
        "schemaVersion": SCHEMA_VERSION,
        "tool": TOOL_NAME,
        "status": status,
        "baseline": report_summary(baseline_path, baseline, baseline_cases),
        "candidate": report_summary(candidate_path, candidate, candidate_cases),
        "metadata": {
            "corpusVersionChanged": baseline.get("corpusVersion")
            != candidate.get("corpusVersion"),
            "baselinePolicy": {
                "baseline": {
                    **baseline_policy_metadata.fields,
                    "skippedToolAccounting": (
                        baseline_policy_metadata.skipped_tool_accounting
                    ),
                    "toolchains": baseline_policy_metadata.toolchains,
                },
                "candidate": {
                    **candidate_policy_metadata.fields,
                    "skippedToolAccounting": (
                        candidate_policy_metadata.skipped_tool_accounting
                    ),
                    "toolchains": candidate_policy_metadata.toolchains,
                },
                "advisorySummary": metadata_advisory_summary,
                "compatibility": policy_metadata_comparison,
                "comparisonDimensions": {
                    "advisory": True,
                    "baseline": comparison_dimensions_report(
                        baseline_policy_metadata, baseline_cases
                    ),
                    "candidate": comparison_dimensions_report(
                        candidate_policy_metadata, candidate_cases
                    ),
                    "compatibility": policy_metadata_comparison,
                    "policy": (
                        "Comparison dimensions are report-only context for "
                        "baseline curation. Host, toolchain, target-profile, "
                        "optimization, category, and skipped-tool drift are "
                        "summarized here without creating timing failure gates."
                    ),
                },
                "producerClaims": {
                    "baseline": baseline_producer_claims,
                    "candidate": candidate_producer_claims,
                    "summary": producer_claim_summary,
                },
                "readiness": {
                    "baseline": baseline_readiness,
                    "candidate": candidate_readiness,
                    "compatibleReadyPair": compatible_ready_pair,
                    "policy": (
                        "Readiness is report-only and does not affect comparator "
                        "exit status; use it to decide whether a passing pair is "
                        "strong enough for future threshold proposals."
                    ),
                },
                "stability": baseline_stability,
            },
        },
        "policy": {
            "artifactSize": {
                "failed": False,
                "mode": "report-only",
            },
            "failureClass": failure_class,
            "failurePriority": failure_priority,
            "failurePriorityPolicy": (
                "Structural and report-shape failures are classified before "
                "timing threshold reports; v0 timing thresholds are advisory and "
                "never change comparator exit status."
            ),
            "failureSurfaces": {
                "hardFail": ["structure"],
                "reportOnly": [
                    "timing",
                    "artifactSize",
                    "nativeOptimization",
                    "metadata.baselinePolicy",
                ],
            },
            "nativeOptimization": {
                "descriptorFieldDriftCount": native_optimization_drift[
                    "descriptorFieldDriftCount"
                ],
                "descriptorStatusDriftCount": native_optimization_drift[
                    "descriptorStatusDriftCount"
                ],
                "failed": False,
                "mode": "report-only",
                "statusDriftCount": native_optimization_drift["statusDriftCount"],
            },
            "structural": {
                "failed": structural_failure,
                "failureReasons": structural_failure_reasons,
                "mode": "hard-fail",
            },
            "timing": {
                "advisoryThresholds": policy_timing_advisory_thresholds,
                "advisoryEvidencePolicy": TIMING_ADVISORY_EVIDENCE_POLICY,
                "failed": timing_failure,
                "failureCount": 0,
                "hardThresholdAvailable": False,
                "mode": "report-only",
                "releaseBlockerPolicy": TIMING_ADVISORY_RELEASE_BLOCKER_POLICY,
                "requiresExplicitHardThreshold": False,
                "thresholdExceededCount": len(explicit_threshold_exceeded_regressions),
                "thresholdEnforcement": threshold_enforcement_json(),
                "thresholdPolicy": "report-only",
            },
        },
        "structure": {
            "addedCaseCount": len(added_cases),
            "addedCases": added_cases,
            "addedCategoryCount": len(added_categories),
            "addedCategories": added_categories,
            "addedCommandProfileCount": len(added_command_profiles),
            "addedCommandProfiles": added_command_profiles,
            "addedProfileCount": len(added_profiles),
            "addedProfiles": added_profiles,
            "addedTargetCount": len(added_targets),
            "addedTargets": added_targets,
            "addedToolchainLabelCount": len(added_toolchain_labels),
            "addedToolchainLabels": added_toolchain_labels,
            "baselineFunctionalFailureCases": sorted(baseline_functional_failures),
            "baselineToolchainClassifications": baseline_toolchain_classifications,
            "candidateFunctionalFailureCaseCount": len(candidate_functional_failures),
            "candidateFunctionalFailureCases": sorted(candidate_functional_failures),
            "candidateToolchainClassifications": candidate_toolchain_classifications,
            "changedCaseCategories": changed_case_categories,
            "changedCaseCategoryCount": len(changed_case_categories),
            "changedCommandProfileCount": len(changed_command_profiles),
            "changedCommandProfiles": changed_command_profiles,
            "changedFunctionalFailureStatuses": changed_functional_failure_statuses,
            "changedReportCaseLabelCount": len(changed_report_case_labels),
            "changedReportCaseLabels": changed_report_case_labels,
            "changedToolchainClassifications": changed_toolchain_classifications,
            "changedSkipReasonCount": len(changed_skip_reasons),
            "changedSkipReasons": changed_skip_reasons,
            "caseIdentityPolicy": (
                "Case coverage is compared by normalized fixtureName/target/profile "
                "identity when those labels are available; raw report case label "
                "changes are reported here but are not structural coverage loss."
            ),
            "functionalFailurePolicy": (
                "Candidate package/build failures are structural failures and are "
                "reported separately from timing deltas."
            ),
            "failed": structural_failure,
            "failureMode": "hard-fail",
            "failureReasons": structural_failure_reasons,
            "missingCaseCount": len(missing_cases),
            "missingCases": missing_cases,
            "missingCategoryCount": len(missing_categories),
            "missingCategories": missing_categories,
            "missingCommandProfileCount": len(missing_command_profiles),
            "missingCommandProfiles": missing_command_profiles,
            "missingProfileCount": len(missing_profiles),
            "missingProfiles": missing_profiles,
            "missingTargetCount": len(missing_targets),
            "missingTargets": missing_targets,
            "missingToolchainLabelCount": len(missing_toolchain_labels),
            "missingToolchainLabels": missing_toolchain_labels,
            "mode": "hard-fail",
            "newFunctionalFailureCaseCount": len(new_functional_failure_cases),
            "newFunctionalFailureCases": new_functional_failure_cases,
            "newOptionalUnavailableToolchainLabels": (
                new_optional_unavailable_toolchain_labels
            ),
            "newRequiredUnavailableToolchainLabels": (
                new_required_unavailable_toolchain_labels
            ),
            "newSkippedCaseCount": len(new_skipped_cases),
            "newSkippedCases": new_skipped_cases,
            "newUnavailableToolchainLabels": new_unavailable_toolchain_labels,
            "resolvedFunctionalFailureCases": resolved_functional_failure_cases,
            "resolvedSkippedCaseCount": len(resolved_skipped_cases),
            "resolvedSkippedCases": resolved_skipped_cases,
            "resolvedUnavailableToolchainLabels": (
                resolved_unavailable_toolchain_labels
            ),
            "toolchainClassificationPolicy": (
                "Toolchains marked optional are reported separately; missing role "
                "metadata is treated as required for structural loss checks."
            ),
            "validationIssueCount": len(baseline_validation_issues)
            + len(candidate_validation_issues),
            "validationIssues": baseline_validation_issues
            + candidate_validation_issues,
        },
        "timing": {
            "advisoryClaimEligibleCaseCount": timing_claim_eligible_case_count,
            "advisoryContext": advisory_context,
            "advisoryEvidencePolicy": {
                "metadataComparabilityPolicy": (
                    TIMING_ADVISORY_METADATA_COMPARABILITY_POLICY
                ),
                "minimumSampleCount": TIMING_ADVISORY_MIN_SAMPLE_COUNT,
                "policy": TIMING_ADVISORY_EVIDENCE_POLICY,
                "releaseBlockerPolicy": TIMING_ADVISORY_RELEASE_BLOCKER_POLICY,
                "requiresComparableMetadata": True,
                "requiresExplicitTimedCaseIdentity": True,
                "requiresRepeatedBaselineAndCandidateSamples": True,
            },
            "advisoryRegressionCount": len(advisory_regressions),
            "advisoryRegressions": advisory_regressions,
            "advisoryThresholdExceededCount": len(
                advisory_threshold_exceeded_regressions
            ),
            "advisoryThresholdExceededRegressions": (
                advisory_threshold_exceeded_regressions
            ),
            "advisoryThresholdProfile": advisory_threshold_profile_summary,
            "advisoryThresholdPolicy": advisory_threshold_policy_summary,
            "advisoryThresholds": advisory_thresholds_summary,
            "comparableCaseCount": comparable_case_count,
            "deltaReport": "all" if include_timing_deltas else "regressions-only",
            "explicitHardPolicy": {
                "enabled": False,
                "enforcement": threshold_enforcement_json(),
                "failureMode": "not-supported-v0-report-only",
                "failedRegressionCount": 0,
                "maxRegressionPercent": None,
                "replacement": "explicitThresholdPolicy",
                "releaseBlockerPolicy": TIMING_ADVISORY_RELEASE_BLOCKER_POLICY,
            },
            "explicitThresholdPolicy": {
                "claimDispositionCounts": sorted_counts(
                    explicit_threshold_claim_disposition_counts
                ),
                "claimEligibleCaseCount": timing_claim_eligible_case_count
                if max_regression_percent is not None
                else 0,
                "enabled": max_regression_percent is not None,
                "enforcement": threshold_enforcement_json(),
                "evidencePolicy": TIMING_ADVISORY_EVIDENCE_POLICY,
                "failurePolicy": (
                    "report-only; this explicit threshold never changes comparator "
                    "exit status in v0"
                ),
                "measuredThresholdExceededCaseCount": len(
                    explicit_threshold_measured_exceeded_cases
                ),
                "measuredThresholdExceededCases": (
                    explicit_threshold_measured_exceeded_cases
                ),
                "mode": "report-only",
                "releaseBlockerPolicy": TIMING_ADVISORY_RELEASE_BLOCKER_POLICY,
                "thresholdExceededCount": len(explicit_threshold_exceeded_regressions),
                "maxRegressionPercent": decimal_percent_value(max_regression_percent)
                if max_regression_percent is not None
                else None,
            },
            "failedRegressionCount": 0,
            "failedRegressions": [],
            "insufficientAdvisoryEvidenceCaseCount": len(
                timing_insufficient_evidence_cases
            ),
            "insufficientAdvisoryEvidenceCases": timing_insufficient_evidence_cases,
            "evidenceSufficiency": timing_evidence_sufficiency,
            "maxRegressionPercent": decimal_percent_value(max_regression_percent)
            if max_regression_percent is not None
            else None,
            "policy": "advisory-threshold"
            if max_regression_percent is not None
            else "advisory-no-threshold",
            "thresholdExceededCount": len(explicit_threshold_exceeded_regressions),
            "thresholdExceededRegressions": explicit_threshold_exceeded_regressions,
            "thresholdEnforcement": threshold_enforcement_json(),
            "thresholdProposalLayer": threshold_proposal_layer,
            "timingDeltaCount": len(timing_deltas),
            "timingDeltas": timing_deltas,
            "untimedCaseCount": len(untimed_cases),
            "untimedCases": untimed_cases,
            "warningSummary": timing_warnings,
        },
        "artifactSize": {
            "advisoryContext": advisory_context,
            "advisoryIncreaseCount": len(advisory_size_increases),
            "advisoryIncreases": advisory_size_increases,
            "comparableCaseCount": comparable_size_case_count,
            "deltaReport": "all" if include_size_deltas else "increases-only",
            "manifestArtifactKindEvidence": {
                "changedCaseCount": len(manifest_artifact_kind_deltas),
                "changedCases": [
                    entry["case"] for entry in manifest_artifact_kind_deltas
                ],
                "comparableCaseCount": manifest_artifact_kind_case_count,
                "deltas": manifest_artifact_kind_deltas,
                "kindDeltaCount": sum(
                    entry["kindDeltaCount"] for entry in manifest_artifact_kind_deltas
                ),
                "policy": "report-only",
                "unreportedCaseCount": len(manifest_artifact_kind_unreported_cases),
                "unreportedCases": manifest_artifact_kind_unreported_cases,
            },
            "policy": "advisory-no-threshold",
            "sizeDeltaCount": len(size_deltas),
            "sizeDeltas": size_deltas,
            "unsizedCaseCount": len(unsized_cases),
            "unsizedCases": unsized_cases,
            "warningSummary": artifact_size_warnings,
        },
        "nativeOptimization": native_optimization_drift,
        "reportArtifacts": report_artifact_expectations(),
    }


def write_json(payload: dict[str, Any], output_path: Path | None) -> None:
    text = json.dumps(payload, indent=2, sort_keys=True) + "\n"
    if output_path is None:
        sys.stdout.write(text)
        return
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(text, encoding="utf-8")


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "reports",
        nargs="*",
        type=Path,
        help=(
            "Performance JSON report paths. Pairwise compare mode requires exactly "
            "baseline and candidate. Aggregate mode accepts one or more reports."
        ),
    )
    parser.add_argument(
        "--aggregate",
        action="store_true",
        help=(
            "Emit a report-only aggregate summary for one or more advisory "
            "benchmark reports instead of pairwise comparison."
        ),
    )
    parser.add_argument(
        "--max-regression-percent",
        type=parse_nonnegative_decimal,
        help=(
            "Report when a comparable timed case is slower than baseline by more "
            "than this percentage. Timing thresholds are advisory only in v0."
        ),
    )
    parser.add_argument(
        "--advisory-threshold-profile",
        choices=sorted(ADVISORY_THRESHOLD_PROFILES),
        default=DEFAULT_ADVISORY_THRESHOLD_PROFILE,
        help=(
            "Named report-only threshold proposal profile to include in timing "
            f"classification. Default: {DEFAULT_ADVISORY_THRESHOLD_PROFILE}."
        ),
    )
    parser.add_argument(
        "--advisory-threshold-policy",
        type=Path,
        help=(
            "Load a report-only advisory threshold policy JSON file. When set, "
            "this overrides --advisory-threshold-profile for pairwise timing "
            "classification."
        ),
    )
    parser.add_argument(
        "--write-advisory-threshold-policy",
        type=Path,
        help=(
            "Write the active advisory threshold policy JSON to this path. With no "
            "report paths, this generates the policy file and exits."
        ),
    )
    parser.add_argument(
        "--include-timing-deltas",
        action="store_true",
        help=(
            "Include every comparable timed case delta in the JSON report. "
            "This is reporting-only, including when --max-regression-percent is set."
        ),
    )
    parser.add_argument(
        "--include-size-deltas",
        action="store_true",
        help=(
            "Include every comparable artifact byte-size delta in the JSON report. "
            "Artifact size changes are advisory only."
        ),
    )
    parser.add_argument(
        "--json-output",
        type=Path,
        help="Write comparison JSON to this path instead of stdout.",
    )
    args = parser.parse_args(argv)
    generate_policy_only = (
        not args.reports and args.write_advisory_threshold_policy is not None
    )
    if args.aggregate:
        if not args.reports:
            parser.error("--aggregate requires at least one report path")
        if args.max_regression_percent is not None:
            parser.error("--aggregate does not accept --max-regression-percent")
        if args.include_timing_deltas:
            parser.error("--aggregate does not accept --include-timing-deltas")
        if args.include_size_deltas:
            parser.error("--aggregate does not accept --include-size-deltas")
        if args.advisory_threshold_policy is not None:
            parser.error("--aggregate does not accept --advisory-threshold-policy")
    elif not generate_policy_only and len(args.reports) != 2:
        parser.error("pairwise comparison requires exactly two report paths")
    return args


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    try:
        advisory_threshold_policy_path = (
            args.advisory_threshold_policy.expanduser().resolve()
            if args.advisory_threshold_policy is not None
            else None
        )
        if args.write_advisory_threshold_policy is not None:
            advisory_threshold_profile, _ = resolve_advisory_threshold_profile(
                profile_name=args.advisory_threshold_profile,
                policy_path=advisory_threshold_policy_path,
            )
            write_json(
                advisory_threshold_policy_json(advisory_threshold_profile),
                args.write_advisory_threshold_policy.expanduser().resolve(),
            )
            if not args.reports:
                return 0

        if args.aggregate:
            result = aggregate_reports(
                [path.expanduser().resolve() for path in args.reports]
            )
        else:
            result = compare_reports(
                args.reports[0].expanduser().resolve(),
                args.reports[1].expanduser().resolve(),
                advisory_threshold_policy_path=advisory_threshold_policy_path,
                advisory_threshold_profile_name=args.advisory_threshold_profile,
                include_size_deltas=args.include_size_deltas,
                include_timing_deltas=args.include_timing_deltas,
                max_regression_percent=args.max_regression_percent,
            )
        write_json(result, args.json_output)
    except PerformanceReportComparisonError as exc:
        print(f"performance report comparison failed: {exc}", file=sys.stderr)
        return 2
    return 0 if result["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
