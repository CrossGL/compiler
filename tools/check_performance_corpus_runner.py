#!/usr/bin/env python3
"""Self-test performance corpus runner list and dry-run JSON contracts."""

from __future__ import annotations

import argparse
import copy
import importlib.util
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any


REQUIRED_CASE_FIELDS = [
    "artifactSummary",
    "case",
    "command",
    "commandProfile",
    "compilerPath",
    "diagnosticSummary",
    "elapsedNs",
    "exitStatus",
    "fixtureCategory",
    "fixtureName",
    "fixturePath",
    "nativeValidationRequested",
    "optLevel",
    "outputPath",
    "packageMode",
    "passTraceProvenance",
    "profile",
    "profileBuildType",
    "skipReason",
    "skipped",
    "status",
    "success",
    "target",
    "timing",
    "unavailableTools",
    "verification",
]
REQUIRED_TOP_LEVEL_FIELDS = [
    "advisoryThresholdPolicy",
    "baselinePolicy",
    "cases",
    "config",
    "corpusVersion",
    "dryRun",
    "metadata",
    "schemaVersion",
    "summary",
    "thresholdBaselineReadiness",
    "tool",
    "toolAvailability",
]
REQUIRED_BASELINE_POLICY_FIELDS = [
    "comparisonWindow",
    "hostClass",
    "optLevel",
    "targetProfile",
    "toolchainLabel",
]
REQUIRED_CONFIG_FIELDS = [
    "commandProfiles",
    "compilerPath",
    "corpus",
    "corpusVersion",
    "fixtures",
    "manifestPath",
    "profiles",
    "repeat",
    "root",
    "targets",
    "warmup",
    "workDir",
]
REQUIRED_METADATA_FIELDS = [
    "advisoryThresholdPolicy",
    "benchmarkProfile",
    "caseCategories",
    "commandProfiles",
    "comparisonWindow",
    "dryRun",
    "measurementWindow",
    "optLevel",
    "passTraceProvenance",
    "reportPolicy",
    "runtimeEnvironment",
    "targetProfile",
    "thresholdBaselineReadiness",
    "timedCaseCount",
    "tool",
]
REQUIRED_RUNTIME_ENVIRONMENT_FIELDS = [
    "machine",
    "platform",
    "pythonExecutable",
    "pythonImplementation",
    "pythonVersion",
    "system",
    "systemRelease",
]
REQUIRED_COMMAND_PROFILE_FIELDS = [
    "buildType",
    "cglcArgs",
    "compilerConfig",
    "environment",
    "name",
    "nativeValidationRequested",
    "packageMode",
]
REQUIRED_ARTIFACT_SUMMARY_FIELDS = [
    "available",
    "byteSize",
    "debugArtifactsPresent",
    "emittedManifestArtifactCount",
    "fileCount",
    "files",
    "manifestArtifactByteSize",
    "manifestArtifactCount",
    "manifestArtifacts",
    "manifestAvailable",
    "manifestPackageMode",
    "manifestTarget",
    "missingManifestArtifactCount",
    "nativeArtifactDescriptor",
    "nativeBinaryStatus",
    "nativeProfile",
    "optLevel",
    "outputKind",
    "outputPath",
    "packageFormat",
    "profile",
    "requestedPackageMode",
    "target",
]
REQUIRED_NATIVE_PROFILE_FIELDS = [
    "api",
    "available",
    "declared",
    "optimization",
    "optimizationEvidenceStatus",
    "parseError",
    "path",
    "profileName",
    "schemaVersion",
    "target",
]
REQUIRED_NATIVE_ARTIFACT_DESCRIPTOR_FIELDS = [
    "available",
    "declared",
    "optimizationEvidence",
    "optimizationEvidenceStatus",
    "optimizationLevel",
    "parseError",
    "path",
    "schemaVersion",
    "target",
]
REQUIRED_NATIVE_ARTIFACT_DESCRIPTOR_OPTIMIZATION_EVIDENCE_FIELDS = [
    "effectiveLevel",
    "policy",
    "requestedLevel",
    "status",
]
REQUIRED_NATIVE_OPTIMIZATION_FIELDS = [
    "level",
    "policy",
    "requestedLevel",
    "status",
    "tool",
]
REQUIRED_NATIVE_OPTIMIZATION_RUN_IDENTITY_FIELDS = [
    "hostClass",
    "hostLabel",
    "toolchainLabel",
    "toolchainVersion",
]
REQUIRED_SUMMARY_FIELDS = [
    "artifactAvailableCount",
    "artifactByteSize",
    "artifactFileCount",
    "caseCategories",
    "caseCount",
    "caseCountByCategory",
    "caseCountByCategoryTarget",
    "caseCountByCommandProfile",
    "caseCountByNativeArtifactDescriptorOptimizationEvidenceStatus",
    "caseCountByNativeArtifactDescriptorOptimizationStatus",
    "caseCountByNativeOptimizationEvidenceStatus",
    "caseCountByNativeOptimizationStatus",
    "caseCountByOptLevel",
    "caseCountByPassTraceStatus",
    "caseCountByProfile",
    "caseCountByTarget",
    "categoryCount",
    "commandProfileCount",
    "commandProfiles",
    "dryRunCount",
    "failureCount",
    "fixtureCount",
    "fixtureCountByCategory",
    "manifestArtifactKindCaseCount",
    "manifestArtifactKindCount",
    "manifestArtifactKinds",
    "measurementWindow",
    "measuredRunCount",
    "nativeArtifactDescriptorOptimizationEvidence",
    "nativeArtifactDescriptorOptimizationStatuses",
    "nativeOptimizationStatuses",
    "nativeOptimizationEvidence",
    "nativeValidationRequestedCount",
    "optLevelCount",
    "optLevels",
    "passTraceProvenance",
    "skippedCaseCountByReason",
    "skippedCasesWithUnavailableTools",
    "skippedCount",
    "skippedToolCaseCountByTool",
    "skippedToolCasesByTool",
    "successCount",
    "timedCaseCount",
    "timingWindow",
    "unavailableToolCount",
    "verificationPassedCount",
    "verificationRequestedCount",
    "verificationSkippedCount",
    "warmupRunCount",
]
REQUIRED_VERIFICATION_FIELDS = [
    "reason",
    "requested",
    "status",
    "tool",
    "toolAvailable",
]
REQUIRED_TOOL_AVAILABILITY_FIELDS = [
    "available",
    "path",
    "reason",
    "role",
    "status",
]
EXPECTED_REPORT_POLICY = {
    "artifactSize": "report-only",
    "baselineCuration": "report-only",
    "nativeOptimization": "report-only",
    "packageArtifacts": "report-only",
    "structural": "hard-fail",
    "timing": "report-only",
}
ADVISORY_THRESHOLD_POLICY_KIND = "advisory-threshold-policy"
ADVISORY_THRESHOLD_POLICY_NAME = "milestone6-runner-provenance"
TIMING_ADVISORY_MIN_SAMPLE_COUNT = 2
TIMING_BASELINE_STABILITY_POLICY = (
    "No checked-in stable multi-run timing baseline is available for this "
    "runner report, so numeric thresholds are intentionally omitted."
)
REQUIRED_BASELINE_PROVENANCE_FIELDS = [
    "hostLabel",
    "hostClass",
    "targetProfile",
    "optLevel",
    "comparisonWindow",
    "runtimeEnvironment",
    "toolchains",
]
REQUIRED_THRESHOLD_CASE_IDENTITY_FIELDS = [
    "fixtureName",
    "target",
    "profile",
    "optLevel",
]
REQUIRED_ADVISORY_THRESHOLD_POLICY_FIELDS = [
    "description",
    "enforcement",
    "evidencePolicy",
    "failurePolicy",
    "kind",
    "mode",
    "name",
    "releaseBlockerPolicy",
    "ruleCount",
    "rules",
    "schemaVersion",
    "stableBaselineDataPresent",
    "status",
    "thresholdSource",
    "tool",
]
REQUIRED_THRESHOLD_ENFORCEMENT_FIELDS = [
    "enforced",
    "exitStatusAffected",
    "failureMode",
    "hardFail",
    "mode",
    "policy",
    "releaseBlocker",
]
REQUIRED_THRESHOLD_BASELINE_READINESS_FIELDS = [
    "advisory",
    "baselineProvenance",
    "failureMode",
    "incompleteTimedCaseIdentityCaseCount",
    "incompleteTimedCaseIdentityCases",
    "minimumSampleCount",
    "mode",
    "optionalSkippedCaseCount",
    "optionalSkippedToolLabels",
    "policy",
    "readyForThresholdBaseline",
    "reasonCount",
    "reasons",
    "repeatedTimingEvidence",
    "requiredOrUnclassifiedSkippedCaseCount",
    "requiredOrUnclassifiedSkippedToolLabels",
    "satisfiedThresholdBaselineRequirementCount",
    "stableBaselineDataPresent",
    "status",
    "thresholdBaselineRequirementCount",
    "thresholdBaselineRequirements",
    "thresholdBaselineRequirementsPolicy",
    "timedCaseCount",
    "timedCaseIdentity",
    "unsatisfiedThresholdBaselineRequirementCount",
    "unsatisfiedThresholdBaselineRequirements",
]
THRESHOLD_BASELINE_REQUIREMENT_SPECS = [
    ("stableBaselineData", "stable-baseline-data-not-present"),
    ("baselineProvenance", "missing-baseline-provenance"),
    ("timedCases", "no-timed-cases"),
    ("explicitTimedCaseIdentity", "incomplete-timed-case-identity"),
    ("repeatedTimingEvidence", "insufficient-repeated-timing-evidence"),
    ("requiredToolCoverage", "required-or-unclassified-skipped-tools"),
]

REQUIRED_NATIVE_OPTIMIZATION_EVIDENCE_FIELDS = [
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
]
REQUIRED_NATIVE_ARTIFACT_DESCRIPTOR_OPTIMIZATION_EVIDENCE_SUMMARY_FIELDS = [
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
]
REQUIRED_MANIFEST_ARTIFACT_KIND_FIELDS = [
    "byteSize",
    "caseCount",
    "count",
    "emittedCaseCount",
    "emittedCount",
    "missingCaseCount",
    "missingCount",
]
PASS_TRACE_SIDECAR_PATH = "ir/hir-pass-trace.json"
PASS_TRACE_KIND = "hir-pass-trace"
PASS_TRACE_STATUSES = {
    "artifact-unavailable",
    "available",
    "not-requested",
    "not-run",
    "requested-missing",
    "skipped",
    "unparsable",
}
REQUIRED_PASS_TRACE_METADATA_FIELDS = [
    "artifactKind",
    "captureMode",
    "commandFlag",
    "manifestPolicy",
    "reportPolicy",
    "schemaVersion",
    "sidecarPath",
]
REQUIRED_PASS_TRACE_PROVENANCE_FIELDS = [
    "available",
    "captureMode",
    "completed",
    "expectedOptimizationLevel",
    "kind",
    "manifestDeclared",
    "optimizationLevel",
    "optimizationPolicyId",
    "parseError",
    "passCount",
    "passScheduleFingerprint",
    "passScheduleFingerprintPolicy",
    "passScheduleStability",
    "path",
    "profile",
    "reason",
    "requested",
    "schemaVersion",
    "scheduledPassCount",
    "sidecarPath",
    "status",
    "target",
]
REQUIRED_PASS_TRACE_SUMMARY_FIELDS = [
    "availableCount",
    "caseCount",
    "caseCountByPassScheduleFingerprint",
    "caseCountByStatus",
    "manifestDeclaredCount",
    "passScheduleFingerprintCount",
    "passScheduleFingerprints",
    "parseErrorCount",
    "reportPolicy",
    "requestedCount",
    "schemaVersion",
    "sidecarPath",
    "unexpectedOptimizationLevelCases",
    "unexpectedOptimizationLevelCount",
]


def expect(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def expect_relative_report_path(value: Any, label: str) -> None:
    expect(isinstance(value, str) and value, f"{label} should be a non-empty string")
    expect(not Path(value).is_absolute(), f"{label} should be root-relative")
    expect("\\" not in value, f"{label} should use POSIX separators")


def empty_native_profile_summary() -> dict[str, object]:
    return {
        "api": None,
        "available": False,
        "declared": False,
        "optimization": None,
        "optimizationEvidenceStatus": "native-profile-not-declared",
        "parseError": None,
        "path": None,
        "profileName": None,
        "schemaVersion": None,
        "target": None,
    }


def empty_native_artifact_descriptor_summary() -> dict[str, object]:
    return {
        "available": False,
        "declared": False,
        "optimizationEvidence": None,
        "optimizationEvidenceStatus": "native-artifact-descriptor-not-declared",
        "optimizationLevel": None,
        "parseError": None,
        "path": None,
        "schemaVersion": None,
        "target": None,
    }


def expected_pass_trace_optimization_level(
    command_profile: dict[str, Any] | None,
) -> str | None:
    if not isinstance(command_profile, dict):
        return None
    cglc_args = command_profile.get("cglcArgs")
    if not isinstance(cglc_args, list):
        return None
    for index, arg in enumerate(cglc_args):
        if arg == "--opt-level" and index + 1 < len(cglc_args):
            level = cglc_args[index + 1]
            if isinstance(level, str) and level:
                return level
    return "O1"


def empty_pass_trace_provenance(
    *,
    output_path: str,
    profile: str,
    target: str,
    expected_optimization_level: str = "O1",
    status: str = "not-run",
    reason: str | None = "dry-run",
    requested: bool = False,
) -> dict[str, object]:
    return {
        "available": False,
        "captureMode": "package-sidecar",
        "completed": None,
        "expectedOptimizationLevel": expected_optimization_level,
        "kind": None,
        "manifestDeclared": False,
        "optimizationLevel": None,
        "optimizationPolicyId": None,
        "parseError": None,
        "passCount": None,
        "passScheduleFingerprint": None,
        "passScheduleFingerprintPolicy": None,
        "passScheduleStability": None,
        "path": f"{output_path}/{PASS_TRACE_SIDECAR_PATH}",
        "profile": profile,
        "reason": reason,
        "requested": requested,
        "schemaVersion": None,
        "scheduledPassCount": None,
        "sidecarPath": PASS_TRACE_SIDECAR_PATH,
        "status": status,
        "target": target,
    }


def native_optimization_evidence_status(native_profile: dict[str, Any] | None) -> str:
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
    status = optimization.get("status")
    if isinstance(status, str) and status:
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


def native_artifact_descriptor_evidence_status(
    descriptor: dict[str, Any] | None,
) -> str:
    if not isinstance(descriptor, dict):
        return "native-artifact-descriptor-not-declared"
    evidence = descriptor.get("optimizationEvidence")
    if isinstance(evidence, dict):
        status = evidence.get("status")
        if isinstance(status, str) and status:
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


def native_optimization_evidence_summary(
    case_count: int, counts: dict[str, int]
) -> dict[str, Any]:
    not_declared_count = counts.get("native-profile-not-declared", 0)
    missing_count = counts.get("missing-debug-optimization", 0)
    unparsable_count = counts.get("unparsable-native-profile", 0)
    declared_missing_count = counts.get("declared-native-profile-missing", 0)
    return {
        "caseCount": case_count,
        "caseCountByEvidenceStatus": sorted_counts(counts),
        "declaredNativeProfileCount": case_count - not_declared_count,
        "knownStatusCount": counts.get("known-status", 0),
        "missingDebugOptimizationCount": missing_count,
        "missingOrUnparsableEvidenceCount": (
            missing_count + unparsable_count + declared_missing_count
        ),
        "nativeProfileDeclaredButMissingCount": declared_missing_count,
        "nativeProfileNotDeclaredCount": not_declared_count,
        "optimizationWithoutStatusCount": counts.get("optimization-without-status", 0),
        "unparsableNativeProfileCount": unparsable_count,
    }


def native_artifact_descriptor_evidence_summary(
    case_count: int, counts: dict[str, int]
) -> dict[str, Any]:
    not_declared_count = counts.get("native-artifact-descriptor-not-declared", 0)
    missing_count = counts.get("missing-optimization-evidence", 0)
    unparsable_count = counts.get("unparsable-native-artifact-descriptor", 0)
    declared_missing_count = counts.get(
        "declared-native-artifact-descriptor-missing", 0
    )
    return {
        "caseCount": case_count,
        "caseCountByEvidenceStatus": sorted_counts(counts),
        "declaredNativeArtifactDescriptorCount": case_count - not_declared_count,
        "knownStatusCount": counts.get("known-status", 0),
        "missingOptimizationEvidenceCount": missing_count,
        "missingOrUnparsableEvidenceCount": (
            missing_count + unparsable_count + declared_missing_count
        ),
        "nativeArtifactDescriptorDeclaredButMissingCount": declared_missing_count,
        "nativeArtifactDescriptorNotDeclaredCount": not_declared_count,
        "optimizationWithoutStatusCount": counts.get("optimization-without-status", 0),
        "unparsableNativeArtifactDescriptorCount": unparsable_count,
    }


def pass_trace_provenance_summary(
    *,
    case_count: int,
    fingerprint_counts: dict[str, int],
    status_counts: dict[str, int],
    requested_count: int,
    manifest_declared_count: int,
    parse_error_count: int,
    unexpected_level_cases: list[str],
) -> dict[str, Any]:
    unexpected = sorted(unexpected_level_cases)
    sorted_fingerprint_counts = sorted_counts(fingerprint_counts)
    return {
        "availableCount": status_counts.get("available", 0),
        "caseCount": case_count,
        "caseCountByPassScheduleFingerprint": sorted_fingerprint_counts,
        "caseCountByStatus": sorted_counts(status_counts),
        "manifestDeclaredCount": manifest_declared_count,
        "passScheduleFingerprintCount": len(sorted_fingerprint_counts),
        "passScheduleFingerprints": sorted(sorted_fingerprint_counts),
        "parseErrorCount": parse_error_count,
        "reportPolicy": "report-only",
        "requestedCount": requested_count,
        "schemaVersion": 1,
        "sidecarPath": PASS_TRACE_SIDECAR_PATH,
        "unexpectedOptimizationLevelCases": unexpected,
        "unexpectedOptimizationLevelCount": len(unexpected),
    }


def manifest_artifact_kind_summary(
    cases: list[dict[str, Any]],
) -> dict[str, dict[str, int]]:
    metrics: dict[str, dict[str, int]] = {}
    for case in cases:
        if not isinstance(case, dict):
            continue
        artifact_summary = case.get("artifactSummary")
        if not isinstance(artifact_summary, dict):
            continue
        manifest_artifacts = artifact_summary.get("manifestArtifacts")
        if not isinstance(manifest_artifacts, list):
            continue

        case_kinds: set[str] = set()
        emitted_case_kinds: set[str] = set()
        missing_case_kinds: set[str] = set()
        for manifest_artifact in manifest_artifacts:
            if not isinstance(manifest_artifact, dict):
                continue
            kind = manifest_artifact.get("kind")
            if not isinstance(kind, str) or not kind:
                continue
            kind_metrics = metrics.setdefault(
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
            kind_metrics["count"] += 1
            case_kinds.add(kind)
            exists = manifest_artifact.get("exists")
            if exists is True:
                kind_metrics["emittedCount"] += 1
                emitted_case_kinds.add(kind)
                bytes_value = manifest_artifact.get("bytes")
                if (
                    isinstance(bytes_value, int)
                    and not isinstance(bytes_value, bool)
                    and bytes_value >= 0
                ):
                    kind_metrics["byteSize"] += bytes_value
            elif exists is False:
                kind_metrics["missingCount"] += 1
                missing_case_kinds.add(kind)

        for kind in case_kinds:
            metrics[kind]["caseCount"] += 1
        for kind in emitted_case_kinds:
            metrics[kind]["emittedCaseCount"] += 1
        for kind in missing_case_kinds:
            metrics[kind]["missingCaseCount"] += 1

    return {kind: metrics[kind] for kind in sorted(metrics)}


def manifest_artifact_kind_case_count(cases: list[dict[str, Any]]) -> int:
    count = 0
    for case in cases:
        if not isinstance(case, dict):
            continue
        artifact_summary = case.get("artifactSummary")
        if not isinstance(artifact_summary, dict):
            continue
        manifest_artifacts = artifact_summary.get("manifestArtifacts")
        if isinstance(manifest_artifacts, list) and manifest_artifacts:
            count += 1
    return count


def require_fields(
    value: dict[str, Any],
    fields: list[str],
    path: str,
    errors: list[str],
) -> None:
    for field in fields:
        if field not in value:
            errors.append(f"{path}.{field}: required field is missing")


def object_field(
    value: dict[str, Any],
    key: str,
    path: str,
    errors: list[str],
) -> dict[str, Any] | None:
    field_path = f"{path}.{key}"
    if key not in value:
        errors.append(f"{field_path}: required object field is missing")
        return None
    field = value[key]
    if not isinstance(field, dict):
        errors.append(f"{field_path}: expected object")
        return None
    return field


def list_field(
    value: dict[str, Any],
    key: str,
    path: str,
    errors: list[str],
) -> list[Any] | None:
    field_path = f"{path}.{key}"
    if key not in value:
        errors.append(f"{field_path}: required list field is missing")
        return None
    field = value[key]
    if not isinstance(field, list):
        errors.append(f"{field_path}: expected list")
        return None
    return field


def check_equal(
    actual: Any,
    expected: Any,
    path: str,
    errors: list[str],
) -> None:
    if actual != expected:
        errors.append(f"{path}: expected {expected!r}, got {actual!r}")


def check_non_empty_string_field(
    value: dict[str, Any],
    key: str,
    path: str,
    errors: list[str],
    *,
    reason: str | None = None,
) -> str | None:
    field_path = f"{path}.{key}"
    field = value.get(key)
    if isinstance(field, str) and field:
        return field
    if reason:
        errors.append(f"{field_path}: expected non-empty string {reason}")
    else:
        errors.append(f"{field_path}: expected non-empty string")
    return None


def increment(counts: dict[str, int], value: Any) -> None:
    if isinstance(value, str) and value:
        counts[value] = counts.get(value, 0) + 1


def sorted_counts(counts: dict[str, int]) -> dict[str, int]:
    return dict(sorted(counts.items()))


def sorted_nested_counts(
    counts: dict[str, dict[str, int]],
) -> dict[str, dict[str, int]]:
    return {key: dict(sorted(value.items())) for key, value in sorted(counts.items())}


def sorted_string_list_field(
    value: dict[str, Any],
    key: str,
    path: str,
    errors: list[str],
) -> list[str] | None:
    field = value.get(key)
    if not isinstance(field, list):
        return None
    parsed: list[str] = []
    seen: set[str] = set()
    for index, item in enumerate(field):
        item_path = f"{path}.{key}[{index}]"
        if not isinstance(item, str) or not item:
            errors.append(f"{item_path}: expected non-empty string")
            continue
        if item in seen:
            errors.append(f"{item_path}: duplicate value {item!r}")
        seen.add(item)
        parsed.append(item)
    return sorted(parsed)


def common_opt_level(opt_levels: list[str]) -> str | None:
    levels = sorted({level for level in opt_levels if level})
    if not levels:
        return None
    if len(levels) == 1:
        return levels[0]
    return "mixed:" + ",".join(levels)


def check_native_optimization_run_identity(
    payload: dict[str, Any],
    metadata: dict[str, Any] | None,
    status_counts: dict[str, int],
    errors: list[str],
) -> None:
    if not status_counts:
        return

    reason = "when native optimization status evidence is present"
    if metadata is None:
        return

    identity: dict[str, str] = {}
    for field in REQUIRED_NATIVE_OPTIMIZATION_RUN_IDENTITY_FIELDS:
        value = check_non_empty_string_field(
            metadata,
            field,
            "$.metadata",
            errors,
            reason=reason,
        )
        if value is not None:
            identity[field] = value

    label = identity.get("toolchainLabel")
    version = identity.get("toolchainVersion")
    toolchains = payload.get("toolchains")
    if not isinstance(toolchains, dict):
        errors.append(f"$.toolchains: expected object {reason}")
        return
    if label is None:
        return

    toolchain_path = f"$.toolchains.{label}"
    toolchain = toolchains.get(label)
    if not isinstance(toolchain, dict):
        errors.append(f"{toolchain_path}: expected object {reason}")
        return
    require_fields(
        toolchain,
        ["available", "role", "status", "version"],
        toolchain_path,
        errors,
    )
    check_equal(toolchain.get("role"), "required", f"{toolchain_path}.role", errors)
    if version is not None:
        check_equal(
            toolchain.get("version"),
            version,
            f"{toolchain_path}.version",
            errors,
        )


def check_pass_trace_metadata(
    metadata: dict[str, Any],
    errors: list[str],
) -> None:
    provenance = object_field(
        metadata,
        "passTraceProvenance",
        "$.metadata",
        errors,
    )
    if provenance is None:
        return
    require_fields(
        provenance,
        REQUIRED_PASS_TRACE_METADATA_FIELDS,
        "$.metadata.passTraceProvenance",
        errors,
    )
    expected = {
        "artifactKind": PASS_TRACE_KIND,
        "captureMode": "package-sidecar",
        "commandFlag": "--debug-ir",
        "manifestPolicy": "non-manifest-sidecar",
        "reportPolicy": "report-only",
        "schemaVersion": 1,
        "sidecarPath": PASS_TRACE_SIDECAR_PATH,
    }
    for key, value in expected.items():
        check_equal(
            provenance.get(key),
            value,
            f"$.metadata.passTraceProvenance.{key}",
            errors,
        )


def check_advisory_threshold_policy(
    policy: dict[str, Any],
    path: str,
    errors: list[str],
) -> None:
    require_fields(policy, REQUIRED_ADVISORY_THRESHOLD_POLICY_FIELDS, path, errors)
    expected = {
        "schemaVersion": 1,
        "tool": "benchmark_performance_corpus",
        "kind": ADVISORY_THRESHOLD_POLICY_KIND,
        "mode": "report-only",
        "name": ADVISORY_THRESHOLD_POLICY_NAME,
        "ruleCount": 0,
        "rules": [],
        "stableBaselineDataPresent": False,
        "status": "policy-stub",
        "thresholdSource": "not-configured",
    }
    for key, value in expected.items():
        check_equal(policy.get(key), value, f"{path}.{key}", errors)
    for field in ("description", "failurePolicy", "releaseBlockerPolicy"):
        value = policy.get(field)
        if not isinstance(value, str) or not value:
            errors.append(f"{path}.{field}: expected non-empty string")
    enforcement = object_field(policy, "enforcement", path, errors)
    if enforcement is not None:
        require_fields(
            enforcement,
            REQUIRED_THRESHOLD_ENFORCEMENT_FIELDS,
            f"{path}.enforcement",
            errors,
        )
        expected_enforcement = {
            "mode": "report-only",
            "failureMode": "report-only",
            "enforced": False,
            "hardFail": False,
            "exitStatusAffected": False,
            "releaseBlocker": False,
        }
        for key, value in expected_enforcement.items():
            check_equal(
                enforcement.get(key),
                value,
                f"{path}.enforcement.{key}",
                errors,
            )
        enforcement_policy = enforcement.get("policy")
        if not isinstance(enforcement_policy, str) or not enforcement_policy:
            errors.append(f"{path}.enforcement.policy: expected non-empty string")
        elif "not enforced" not in enforcement_policy:
            errors.append(f"{path}.enforcement.policy: expected not-enforced text")
    evidence_policy = object_field(policy, "evidencePolicy", path, errors)
    if evidence_policy is not None:
        for field in (
            "minimumSampleCount",
            "policy",
            "requiresComparableMetadata",
            "requiresExplicitTimedCaseIdentity",
            "requiresRepeatedBaselineAndCandidateSamples",
            "stableBaselinePolicy",
        ):
            if field not in evidence_policy:
                errors.append(
                    f"{path}.evidencePolicy.{field}: required field is missing"
                )
        check_equal(
            evidence_policy.get("minimumSampleCount"),
            TIMING_ADVISORY_MIN_SAMPLE_COUNT,
            f"{path}.evidencePolicy.minimumSampleCount",
            errors,
        )
        for field in (
            "requiresComparableMetadata",
            "requiresExplicitTimedCaseIdentity",
            "requiresRepeatedBaselineAndCandidateSamples",
        ):
            check_equal(
                evidence_policy.get(field),
                True,
                f"{path}.evidencePolicy.{field}",
                errors,
            )


def threshold_readiness_int(value: Any) -> int | None:
    if isinstance(value, int) and not isinstance(value, bool):
        return value
    return None


def threshold_requirement_observed(
    readiness: dict[str, Any],
    name: str,
) -> dict[str, Any] | None:
    baseline_provenance = readiness.get("baselineProvenance")
    timed_identity = readiness.get("timedCaseIdentity")
    repeated_evidence = readiness.get("repeatedTimingEvidence")
    skipped_accounting = (
        baseline_provenance.get("skippedToolAccounting")
        if isinstance(baseline_provenance, dict)
        else None
    )

    if name == "stableBaselineData":
        return {
            "stableBaselineDataPresent": readiness.get("stableBaselineDataPresent"),
            "policy": TIMING_BASELINE_STABILITY_POLICY,
        }
    if name == "baselineProvenance":
        if not isinstance(baseline_provenance, dict):
            return None
        return {
            "missingFields": baseline_provenance.get("missingFields"),
            "toolchainsMissingVersions": baseline_provenance.get(
                "toolchainsMissingVersions"
            ),
        }
    if name == "timedCases":
        if not isinstance(timed_identity, dict):
            return None
        return {"timedCaseCount": timed_identity.get("timedCaseCount")}
    if name == "explicitTimedCaseIdentity":
        if not isinstance(timed_identity, dict):
            return None
        return {
            "incompleteCaseCount": timed_identity.get("incompleteCaseCount"),
            "incompleteCases": timed_identity.get("incompleteCases"),
        }
    if name == "repeatedTimingEvidence":
        if not isinstance(repeated_evidence, dict):
            return None
        return {
            "insufficientRepeatedEvidenceCaseCount": repeated_evidence.get(
                "insufficientRepeatedEvidenceCaseCount"
            ),
            "minimumSampleCount": TIMING_ADVISORY_MIN_SAMPLE_COUNT,
            "repeatedTimedCaseCount": repeated_evidence.get("repeatedTimedCaseCount"),
        }
    if name == "requiredToolCoverage":
        if not isinstance(skipped_accounting, dict):
            return None
        return {
            "requiredOrUnclassifiedSkippedCaseCount": skipped_accounting.get(
                "requiredOrUnclassifiedSkippedCaseCount"
            ),
            "requiredOrUnclassifiedSkippedToolLabels": skipped_accounting.get(
                "requiredOrUnclassifiedSkippedToolLabels"
            ),
            "skippedCasesWithoutUnavailableToolCount": skipped_accounting.get(
                "skippedCasesWithoutUnavailableToolCount"
            ),
        }
    return None


def threshold_requirement_satisfied(
    readiness: dict[str, Any],
    name: str,
) -> bool | None:
    baseline_provenance = readiness.get("baselineProvenance")
    timed_identity = readiness.get("timedCaseIdentity")
    repeated_evidence = readiness.get("repeatedTimingEvidence")
    skipped_accounting = (
        baseline_provenance.get("skippedToolAccounting")
        if isinstance(baseline_provenance, dict)
        else None
    )

    if name == "stableBaselineData":
        return False
    if name == "baselineProvenance":
        if not isinstance(baseline_provenance, dict):
            return None
        return (
            baseline_provenance.get("missingFields") == []
            and baseline_provenance.get("toolchainsMissingVersionCount") == 0
        )
    if name == "timedCases":
        if not isinstance(timed_identity, dict):
            return None
        timed_count = threshold_readiness_int(timed_identity.get("timedCaseCount"))
        return timed_count is not None and timed_count > 0
    if name == "explicitTimedCaseIdentity":
        if not isinstance(timed_identity, dict):
            return None
        return timed_identity.get("incompleteCaseCount") == 0
    if name == "repeatedTimingEvidence":
        if not isinstance(repeated_evidence, dict):
            return None
        timed_count = threshold_readiness_int(repeated_evidence.get("timedCaseCount"))
        return (
            timed_count is not None
            and timed_count > 0
            and repeated_evidence.get("insufficientRepeatedEvidenceCaseCount") == 0
        )
    if name == "requiredToolCoverage":
        if not isinstance(skipped_accounting, dict):
            return None
        return (
            skipped_accounting.get("requiredOrUnclassifiedSkippedCaseCount") == 0
            and skipped_accounting.get("skippedCasesWithoutUnavailableToolCount") == 0
        )
    return None


def check_skipped_tool_accounting_internal_consistency(
    skipped_accounting: dict[str, Any],
    path: str,
    errors: list[str],
) -> None:
    skipped_cases = skipped_accounting.get("skippedCases")
    skipped_cases_with_tools = skipped_accounting.get(
        "skippedCasesWithUnavailableTools"
    )
    if isinstance(skipped_cases, list):
        check_equal(
            skipped_accounting.get("skippedCaseCount"),
            len(skipped_cases),
            f"{path}.skippedCaseCount",
            errors,
        )
    if (
        isinstance(skipped_cases, list)
        and isinstance(skipped_cases_with_tools, list)
        and all(isinstance(case, str) for case in skipped_cases)
        and all(isinstance(case, str) for case in skipped_cases_with_tools)
    ):
        skipped_without_tools = sorted(
            set(skipped_cases) - set(skipped_cases_with_tools)
        )
        check_equal(
            skipped_accounting.get("skippedCasesWithoutUnavailableTools"),
            skipped_without_tools,
            f"{path}.skippedCasesWithoutUnavailableTools",
            errors,
        )
        check_equal(
            skipped_accounting.get("skippedCasesWithoutUnavailableToolCount"),
            len(skipped_without_tools),
            f"{path}.skippedCasesWithoutUnavailableToolCount",
            errors,
        )

    skipped_tool_cases = skipped_accounting.get("skippedToolCasesByTool")
    classifications = skipped_accounting.get("toolchainClassifications")
    if not isinstance(skipped_tool_cases, dict) or not isinstance(
        classifications, dict
    ):
        return

    optional_tools: list[str] = []
    required_or_unclassified_tools: list[str] = []
    for tool in sorted(skipped_tool_cases):
        classification = classifications.get(tool)
        role = classification.get("role") if isinstance(classification, dict) else None
        if role == "optional":
            optional_tools.append(tool)
        else:
            required_or_unclassified_tools.append(tool)

    optional_cases: set[str] = set()
    for tool in optional_tools:
        case_names = skipped_tool_cases.get(tool)
        if isinstance(case_names, list):
            optional_cases.update(case for case in case_names if isinstance(case, str))
    required_or_unclassified_cases: set[str] = set()
    for tool in required_or_unclassified_tools:
        case_names = skipped_tool_cases.get(tool)
        if isinstance(case_names, list):
            required_or_unclassified_cases.update(
                case for case in case_names if isinstance(case, str)
            )
    check_equal(
        skipped_accounting.get("optionalSkippedToolLabels"),
        optional_tools,
        f"{path}.optionalSkippedToolLabels",
        errors,
    )
    check_equal(
        skipped_accounting.get("optionalSkippedCaseCount"),
        len(optional_cases),
        f"{path}.optionalSkippedCaseCount",
        errors,
    )
    check_equal(
        skipped_accounting.get("requiredOrUnclassifiedSkippedToolLabels"),
        required_or_unclassified_tools,
        f"{path}.requiredOrUnclassifiedSkippedToolLabels",
        errors,
    )
    check_equal(
        skipped_accounting.get("requiredOrUnclassifiedSkippedCaseCount"),
        len(required_or_unclassified_cases),
        f"{path}.requiredOrUnclassifiedSkippedCaseCount",
        errors,
    )


def check_threshold_baseline_readiness_consistency(
    readiness: dict[str, Any],
    path: str,
    errors: list[str],
) -> None:
    requirements = readiness.get("thresholdBaselineRequirements")
    if not isinstance(requirements, list):
        return

    check_equal(
        len(requirements),
        len(THRESHOLD_BASELINE_REQUIREMENT_SPECS),
        f"{path}.thresholdBaselineRequirements",
        errors,
    )

    parsed_requirements: list[dict[str, Any]] = []
    for index, requirement in enumerate(requirements):
        if not isinstance(requirement, dict):
            continue
        parsed_requirements.append(requirement)
        if index >= len(THRESHOLD_BASELINE_REQUIREMENT_SPECS):
            continue

        expected_name, expected_reason = THRESHOLD_BASELINE_REQUIREMENT_SPECS[index]
        requirement_path = f"{path}.thresholdBaselineRequirements[{index}]"
        check_equal(
            requirement.get("name"),
            expected_name,
            f"{requirement_path}.name",
            errors,
        )
        check_equal(
            requirement.get("reasonIfUnsatisfied"),
            expected_reason,
            f"{requirement_path}.reasonIfUnsatisfied",
            errors,
        )

        expected_observed = threshold_requirement_observed(readiness, expected_name)
        if expected_observed is not None:
            check_equal(
                requirement.get("observed"),
                expected_observed,
                f"{requirement_path}.observed",
                errors,
            )

        expected_satisfied = threshold_requirement_satisfied(readiness, expected_name)
        if expected_satisfied is not None:
            check_equal(
                requirement.get("satisfied"),
                expected_satisfied,
                f"{requirement_path}.satisfied",
                errors,
            )

    unsatisfied_requirements = [
        requirement
        for requirement in parsed_requirements
        if requirement.get("satisfied") is not True
    ]
    reasons = [
        requirement.get("reasonIfUnsatisfied")
        for requirement in unsatisfied_requirements
    ]
    check_equal(readiness.get("reasons"), reasons, f"{path}.reasons", errors)
    check_equal(
        readiness.get("reasonCount"),
        len(reasons),
        f"{path}.reasonCount",
        errors,
    )
    check_equal(
        readiness.get("unsatisfiedThresholdBaselineRequirements"),
        unsatisfied_requirements,
        f"{path}.unsatisfiedThresholdBaselineRequirements",
        errors,
    )
    check_equal(
        readiness.get("unsatisfiedThresholdBaselineRequirementCount"),
        len(unsatisfied_requirements),
        f"{path}.unsatisfiedThresholdBaselineRequirementCount",
        errors,
    )
    check_equal(
        readiness.get("satisfiedThresholdBaselineRequirementCount"),
        len(parsed_requirements) - len(unsatisfied_requirements),
        f"{path}.satisfiedThresholdBaselineRequirementCount",
        errors,
    )

    timed_identity = readiness.get("timedCaseIdentity")
    if isinstance(timed_identity, dict):
        check_equal(
            readiness.get("timedCaseCount"),
            timed_identity.get("timedCaseCount"),
            f"{path}.timedCaseCount",
            errors,
        )
        check_equal(
            readiness.get("incompleteTimedCaseIdentityCaseCount"),
            timed_identity.get("incompleteCaseCount"),
            f"{path}.incompleteTimedCaseIdentityCaseCount",
            errors,
        )
        check_equal(
            readiness.get("incompleteTimedCaseIdentityCases"),
            timed_identity.get("incompleteCases"),
            f"{path}.incompleteTimedCaseIdentityCases",
            errors,
        )

    baseline_provenance = readiness.get("baselineProvenance")
    if isinstance(baseline_provenance, dict):
        toolchains = baseline_provenance.get("toolchains")
        if isinstance(toolchains, dict):
            toolchain_labels = sorted(toolchains)
            check_equal(
                baseline_provenance.get("toolchainLabels"),
                toolchain_labels,
                f"{path}.baselineProvenance.toolchainLabels",
                errors,
            )
            check_equal(
                baseline_provenance.get("toolchainLabelCount"),
                len(toolchain_labels),
                f"{path}.baselineProvenance.toolchainLabelCount",
                errors,
            )
        missing_versions = baseline_provenance.get("toolchainsMissingVersions")
        if isinstance(missing_versions, list):
            check_equal(
                baseline_provenance.get("toolchainsMissingVersionCount"),
                len(missing_versions),
                f"{path}.baselineProvenance.toolchainsMissingVersionCount",
                errors,
            )

        skipped_accounting = baseline_provenance.get("skippedToolAccounting")
        if isinstance(skipped_accounting, dict):
            check_threshold_fields = (
                "optionalSkippedCaseCount",
                "optionalSkippedToolLabels",
                "requiredOrUnclassifiedSkippedCaseCount",
                "requiredOrUnclassifiedSkippedToolLabels",
            )
            for field in check_threshold_fields:
                check_equal(
                    readiness.get(field),
                    skipped_accounting.get(field),
                    f"{path}.{field}",
                    errors,
                )
            check_skipped_tool_accounting_internal_consistency(
                skipped_accounting,
                f"{path}.baselineProvenance.skippedToolAccounting",
                errors,
            )


def check_threshold_baseline_readiness_shape(
    readiness: dict[str, Any],
    path: str,
    errors: list[str],
) -> None:
    require_fields(
        readiness,
        REQUIRED_THRESHOLD_BASELINE_READINESS_FIELDS,
        path,
        errors,
    )
    expected = {
        "advisory": True,
        "failureMode": "report-only",
        "minimumSampleCount": TIMING_ADVISORY_MIN_SAMPLE_COUNT,
        "mode": "report-only",
        "readyForThresholdBaseline": False,
        "stableBaselineDataPresent": False,
        "status": "incomplete",
    }
    for key, value in expected.items():
        check_equal(readiness.get(key), value, f"{path}.{key}", errors)
    for field in ("policy", "thresholdBaselineRequirementsPolicy"):
        value = readiness.get(field)
        if not isinstance(value, str) or not value:
            errors.append(f"{path}.{field}: expected non-empty string")

    reasons = readiness.get("reasons")
    if isinstance(reasons, list):
        if "stable-baseline-data-not-present" not in reasons:
            errors.append(f"{path}.reasons: expected stable-baseline-data-not-present")
        check_equal(
            readiness.get("reasonCount"), len(reasons), f"{path}.reasonCount", errors
        )
    else:
        errors.append(f"{path}.reasons: expected list")

    requirements = readiness.get("thresholdBaselineRequirements")
    if isinstance(requirements, list):
        check_equal(
            readiness.get("thresholdBaselineRequirementCount"),
            len(requirements),
            f"{path}.thresholdBaselineRequirementCount",
            errors,
        )
        unsatisfied = [
            item
            for item in requirements
            if isinstance(item, dict) and item.get("satisfied") is not True
        ]
        check_equal(
            readiness.get("unsatisfiedThresholdBaselineRequirementCount"),
            len(unsatisfied),
            f"{path}.unsatisfiedThresholdBaselineRequirementCount",
            errors,
        )
        for index, requirement in enumerate(requirements):
            requirement_path = f"{path}.thresholdBaselineRequirements[{index}]"
            if not isinstance(requirement, dict):
                errors.append(f"{requirement_path}: expected object")
                continue
            require_fields(
                requirement,
                ["name", "observed", "reasonIfUnsatisfied", "satisfied"],
                requirement_path,
                errors,
            )
            if not isinstance(requirement.get("name"), str) or not requirement.get(
                "name"
            ):
                errors.append(f"{requirement_path}.name: expected non-empty string")
            if not isinstance(requirement.get("reasonIfUnsatisfied"), str):
                errors.append(
                    f"{requirement_path}.reasonIfUnsatisfied: expected string"
                )
            if not isinstance(requirement.get("observed"), dict):
                errors.append(f"{requirement_path}.observed: expected object")
            if not isinstance(requirement.get("satisfied"), bool):
                errors.append(f"{requirement_path}.satisfied: expected bool")
    else:
        errors.append(f"{path}.thresholdBaselineRequirements: expected list")

    unsatisfied_requirements = readiness.get("unsatisfiedThresholdBaselineRequirements")
    if not isinstance(unsatisfied_requirements, list):
        errors.append(f"{path}.unsatisfiedThresholdBaselineRequirements: expected list")

    baseline_provenance = object_field(readiness, "baselineProvenance", path, errors)
    if baseline_provenance is not None:
        require_fields(
            baseline_provenance,
            [
                "fields",
                "missingFields",
                "requiredFields",
                "requiredRuntimeEnvironmentFields",
                "runtimeEnvironmentMissingFields",
                "skippedToolAccounting",
                "toolchainLabelCount",
                "toolchainLabels",
                "toolchains",
                "toolchainsMissingVersionCount",
                "toolchainsMissingVersions",
            ],
            f"{path}.baselineProvenance",
            errors,
        )
        check_equal(
            baseline_provenance.get("requiredFields"),
            REQUIRED_BASELINE_PROVENANCE_FIELDS,
            f"{path}.baselineProvenance.requiredFields",
            errors,
        )
        skipped_accounting = object_field(
            baseline_provenance,
            "skippedToolAccounting",
            f"{path}.baselineProvenance",
            errors,
        )
        if skipped_accounting is not None:
            for field in (
                "optionalSkippedCaseCount",
                "optionalSkippedToolLabels",
                "requiredOrUnclassifiedSkippedCaseCount",
                "requiredOrUnclassifiedSkippedToolLabels",
                "skippedCaseCount",
                "skippedCases",
                "skippedCasesWithUnavailableTools",
                "skippedCasesWithoutUnavailableToolCount",
                "skippedCasesWithoutUnavailableTools",
                "skippedToolCaseCountByTool",
                "skippedToolCasesByTool",
                "toolchainClassifications",
                "unavailableToolchainLabelCount",
                "unavailableToolchainLabels",
            ):
                if field not in skipped_accounting:
                    errors.append(
                        f"{path}.baselineProvenance.skippedToolAccounting."
                        f"{field}: required field is missing"
                    )

    timed_identity = object_field(readiness, "timedCaseIdentity", path, errors)
    if timed_identity is not None:
        require_fields(
            timed_identity,
            [
                "caseEvidence",
                "incompleteCaseCount",
                "incompleteCases",
                "policy",
                "requiredFields",
                "timedCaseCount",
            ],
            f"{path}.timedCaseIdentity",
            errors,
        )
        check_equal(
            timed_identity.get("requiredFields"),
            REQUIRED_THRESHOLD_CASE_IDENTITY_FIELDS,
            f"{path}.timedCaseIdentity.requiredFields",
            errors,
        )

    repeated_evidence = object_field(readiness, "repeatedTimingEvidence", path, errors)
    if repeated_evidence is not None:
        require_fields(
            repeated_evidence,
            [
                "caseEvidence",
                "insufficientRepeatedEvidenceCaseCount",
                "insufficientRepeatedEvidenceCases",
                "minimumSampleCount",
                "policy",
                "repeatedTimedCaseCount",
                "timedCaseCount",
            ],
            f"{path}.repeatedTimingEvidence",
            errors,
        )
        check_equal(
            repeated_evidence.get("minimumSampleCount"),
            TIMING_ADVISORY_MIN_SAMPLE_COUNT,
            f"{path}.repeatedTimingEvidence.minimumSampleCount",
            errors,
        )

    check_threshold_baseline_readiness_consistency(readiness, path, errors)


def check_threshold_baseline_readiness_accounting(
    readiness: dict[str, Any],
    path: str,
    *,
    timed_case_count: int,
    skipped_tool_counts: dict[str, int],
    skipped_tool_cases: dict[str, list[str]],
    skipped_cases: list[str],
    skipped_cases_with_tools: list[str],
    errors: list[str],
) -> None:
    check_equal(
        readiness.get("timedCaseCount"),
        timed_case_count,
        f"{path}.timedCaseCount",
        errors,
    )
    timed_identity = readiness.get("timedCaseIdentity")
    if isinstance(timed_identity, dict):
        check_equal(
            timed_identity.get("timedCaseCount"),
            timed_case_count,
            f"{path}.timedCaseIdentity.timedCaseCount",
            errors,
        )
    repeated_evidence = readiness.get("repeatedTimingEvidence")
    if isinstance(repeated_evidence, dict):
        check_equal(
            repeated_evidence.get("timedCaseCount"),
            timed_case_count,
            f"{path}.repeatedTimingEvidence.timedCaseCount",
            errors,
        )
    provenance = readiness.get("baselineProvenance")
    skipped_accounting = (
        provenance.get("skippedToolAccounting")
        if isinstance(provenance, dict)
        else None
    )
    if isinstance(skipped_accounting, dict):
        check_equal(
            skipped_accounting.get("skippedCaseCount"),
            len(skipped_cases),
            f"{path}.baselineProvenance.skippedToolAccounting.skippedCaseCount",
            errors,
        )
        check_equal(
            skipped_accounting.get("skippedCases"),
            sorted(skipped_cases),
            f"{path}.baselineProvenance.skippedToolAccounting.skippedCases",
            errors,
        )
        check_equal(
            skipped_accounting.get("skippedCasesWithUnavailableTools"),
            skipped_cases_with_tools,
            f"{path}.baselineProvenance.skippedToolAccounting"
            ".skippedCasesWithUnavailableTools",
            errors,
        )
        check_equal(
            skipped_accounting.get("skippedToolCaseCountByTool"),
            sorted_counts(skipped_tool_counts),
            f"{path}.baselineProvenance.skippedToolAccounting"
            ".skippedToolCaseCountByTool",
            errors,
        )
        check_equal(
            skipped_accounting.get("skippedToolCasesByTool"),
            skipped_tool_cases,
            f"{path}.baselineProvenance.skippedToolAccounting.skippedToolCasesByTool",
            errors,
        )


def check_pass_trace_provenance(
    pass_trace: dict[str, Any],
    command_profile: dict[str, Any] | None,
    case_value: dict[str, Any],
    case_path: str,
    errors: list[str],
) -> str | None:
    pass_trace_path = f"{case_path}.passTraceProvenance"
    require_fields(
        pass_trace,
        REQUIRED_PASS_TRACE_PROVENANCE_FIELDS,
        pass_trace_path,
        errors,
    )
    check_equal(
        pass_trace.get("captureMode"),
        "package-sidecar",
        f"{pass_trace_path}.captureMode",
        errors,
    )
    check_equal(
        pass_trace.get("sidecarPath"),
        PASS_TRACE_SIDECAR_PATH,
        f"{pass_trace_path}.sidecarPath",
        errors,
    )
    check_equal(
        pass_trace.get("profile"),
        case_value.get("profile"),
        f"{pass_trace_path}.profile",
        errors,
    )
    check_equal(
        pass_trace.get("target"),
        case_value.get("target"),
        f"{pass_trace_path}.target",
        errors,
    )

    path = pass_trace.get("path")
    if isinstance(path, str) and path:
        if "\\" in path:
            errors.append(f"{pass_trace_path}.path: expected POSIX separators")
        if not path.endswith("/" + PASS_TRACE_SIDECAR_PATH):
            errors.append(
                f"{pass_trace_path}.path: expected path ending "
                f"{PASS_TRACE_SIDECAR_PATH!r}"
            )
    else:
        errors.append(f"{pass_trace_path}.path: expected non-empty string")

    requested = pass_trace.get("requested")
    if not isinstance(requested, bool):
        errors.append(f"{pass_trace_path}.requested: expected bool")
    manifest_declared = pass_trace.get("manifestDeclared")
    if not isinstance(manifest_declared, bool):
        errors.append(f"{pass_trace_path}.manifestDeclared: expected bool")
    elif manifest_declared:
        errors.append(
            f"{pass_trace_path}.manifestDeclared: pass trace must remain a "
            "non-manifest sidecar"
        )
    available = pass_trace.get("available")
    if not isinstance(available, bool):
        errors.append(f"{pass_trace_path}.available: expected bool")

    expected_level = expected_pass_trace_optimization_level(command_profile)
    if expected_level is not None:
        check_equal(
            pass_trace.get("expectedOptimizationLevel"),
            expected_level,
            f"{pass_trace_path}.expectedOptimizationLevel",
            errors,
        )

    status = pass_trace.get("status")
    if not isinstance(status, str) or not status:
        errors.append(f"{pass_trace_path}.status: expected non-empty string")
        return None
    if status not in PASS_TRACE_STATUSES:
        errors.append(
            f"{pass_trace_path}.status: expected one of {sorted(PASS_TRACE_STATUSES)!r}"
        )

    reason = pass_trace.get("reason")
    if reason is not None and (not isinstance(reason, str) or not reason):
        errors.append(f"{pass_trace_path}.reason: expected non-empty string or null")
    parse_error = pass_trace.get("parseError")
    if parse_error is not None and (
        not isinstance(parse_error, str) or not parse_error
    ):
        errors.append(
            f"{pass_trace_path}.parseError: expected non-empty string or null"
        )

    if status == "available":
        check_equal(available, True, f"{pass_trace_path}.available", errors)
        check_equal(reason, None, f"{pass_trace_path}.reason", errors)
        check_equal(parse_error, None, f"{pass_trace_path}.parseError", errors)
        check_equal(
            pass_trace.get("schemaVersion"),
            1,
            f"{pass_trace_path}.schemaVersion",
            errors,
        )
        check_equal(
            pass_trace.get("kind"),
            PASS_TRACE_KIND,
            f"{pass_trace_path}.kind",
            errors,
        )
        for field in (
            "optimizationLevel",
            "optimizationPolicyId",
            "passScheduleFingerprint",
            "passScheduleFingerprintPolicy",
            "passScheduleStability",
        ):
            value = pass_trace.get(field)
            if not isinstance(value, str) or not value:
                errors.append(f"{pass_trace_path}.{field}: expected non-empty string")
        fingerprint = pass_trace.get("passScheduleFingerprint")
        if isinstance(fingerprint, str):
            fingerprint_body = fingerprint.removeprefix("fnv1a64:")
            if (
                not fingerprint.startswith("fnv1a64:")
                or len(fingerprint_body) != 16
                or any(
                    character not in "0123456789abcdef"
                    for character in fingerprint_body
                )
            ):
                errors.append(
                    f"{pass_trace_path}.passScheduleFingerprint: expected "
                    "fnv1a64 fingerprint"
                )
        check_equal(
            pass_trace.get("passScheduleFingerprintPolicy"),
            "scheduled-pass-ids-v1",
            f"{pass_trace_path}.passScheduleFingerprintPolicy",
            errors,
        )
        if pass_trace.get("passScheduleStability") not in {
            "stable-opt-level-policy",
            "caller-defined",
        }:
            errors.append(
                f"{pass_trace_path}.passScheduleStability: expected stable "
                "schedule policy label"
            )
        for field in ("passCount", "scheduledPassCount"):
            value = pass_trace.get(field)
            if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                errors.append(f"{pass_trace_path}.{field}: expected non-negative int")
        if not isinstance(pass_trace.get("completed"), bool):
            errors.append(f"{pass_trace_path}.completed: expected bool")
        if expected_level is not None:
            check_equal(
                pass_trace.get("optimizationLevel"),
                expected_level,
                f"{pass_trace_path}.optimizationLevel",
                errors,
            )
    elif status == "unparsable":
        check_equal(available, True, f"{pass_trace_path}.available", errors)
        if parse_error is None:
            errors.append(f"{pass_trace_path}.parseError: expected parse evidence")
        if reason is None:
            errors.append(f"{pass_trace_path}.reason: expected parse reason")
    else:
        check_equal(available, False, f"{pass_trace_path}.available", errors)
        check_equal(parse_error, None, f"{pass_trace_path}.parseError", errors)
        if reason is None:
            errors.append(f"{pass_trace_path}.reason: expected unavailable reason")
        for field in (
            "completed",
            "kind",
            "optimizationLevel",
            "optimizationPolicyId",
            "passCount",
            "passScheduleFingerprint",
            "passScheduleFingerprintPolicy",
            "passScheduleStability",
            "schemaVersion",
            "scheduledPassCount",
        ):
            check_equal(
                pass_trace.get(field), None, f"{pass_trace_path}.{field}", errors
            )
        if status == "requested-missing":
            check_equal(requested, True, f"{pass_trace_path}.requested", errors)
        if status == "not-requested":
            check_equal(requested, False, f"{pass_trace_path}.requested", errors)

    actual_level = pass_trace.get("optimizationLevel")
    if (
        isinstance(actual_level, str)
        and expected_level is not None
        and actual_level != expected_level
    ):
        return str(case_value.get("case"))
    return None


def report_contract_errors(payload: Any) -> list[str]:
    errors: list[str] = []
    if not isinstance(payload, dict):
        return ["$: expected JSON object"]

    require_fields(payload, REQUIRED_TOP_LEVEL_FIELDS, "$", errors)
    check_equal(payload.get("schemaVersion"), 1, "$.schemaVersion", errors)
    check_equal(
        payload.get("tool"),
        "benchmark_performance_corpus",
        "$.tool",
        errors,
    )
    check_equal(
        payload.get("corpusVersion"),
        "milestone6-smoke-v1",
        "$.corpusVersion",
        errors,
    )

    config = object_field(payload, "config", "$", errors)
    metadata = object_field(payload, "metadata", "$", errors)
    summary = object_field(payload, "summary", "$", errors)
    cases = list_field(payload, "cases", "$", errors)
    tool_availability = object_field(payload, "toolAvailability", "$", errors)
    advisory_threshold_policy = object_field(
        payload,
        "advisoryThresholdPolicy",
        "$",
        errors,
    )
    threshold_readiness = object_field(
        payload,
        "thresholdBaselineReadiness",
        "$",
        errors,
    )
    if advisory_threshold_policy is not None:
        check_advisory_threshold_policy(
            advisory_threshold_policy,
            "$.advisoryThresholdPolicy",
            errors,
        )
    if threshold_readiness is not None:
        check_threshold_baseline_readiness_shape(
            threshold_readiness,
            "$.thresholdBaselineReadiness",
            errors,
        )

    command_profile_names: list[str] = []
    command_profile_compiler_configs: list[str] = []
    if config is not None:
        require_fields(config, REQUIRED_CONFIG_FIELDS, "$.config", errors)
        check_equal(
            config.get("corpusVersion"),
            payload.get("corpusVersion"),
            "$.config.corpusVersion",
            errors,
        )
        check_equal(
            config.get("commandProfiles"),
            config.get("profiles"),
            "$.config.commandProfiles",
            errors,
        )

    if metadata is not None:
        require_fields(metadata, REQUIRED_METADATA_FIELDS, "$.metadata", errors)
        check_equal(
            metadata.get("benchmarkProfile"),
            "milestone6-advisory-v1",
            "$.metadata.benchmarkProfile",
            errors,
        )
        check_equal(
            metadata.get("dryRun"),
            payload.get("dryRun"),
            "$.metadata.dryRun",
            errors,
        )
        if not isinstance(metadata.get("optLevel"), str) or not metadata.get(
            "optLevel"
        ):
            errors.append("$.metadata.optLevel: expected non-empty string")
        if not isinstance(metadata.get("targetProfile"), str) or not metadata.get(
            "targetProfile"
        ):
            errors.append("$.metadata.targetProfile: expected non-empty string")

        check_pass_trace_metadata(metadata, errors)
        metadata_advisory_policy = object_field(
            metadata,
            "advisoryThresholdPolicy",
            "$.metadata",
            errors,
        )
        if (
            metadata_advisory_policy is not None
            and advisory_threshold_policy is not None
        ):
            check_equal(
                metadata_advisory_policy,
                advisory_threshold_policy,
                "$.metadata.advisoryThresholdPolicy",
                errors,
            )
        metadata_threshold_readiness = object_field(
            metadata,
            "thresholdBaselineReadiness",
            "$.metadata",
            errors,
        )
        if metadata_threshold_readiness is not None and threshold_readiness is not None:
            check_equal(
                metadata_threshold_readiness,
                threshold_readiness,
                "$.metadata.thresholdBaselineReadiness",
                errors,
            )

        report_policy = object_field(metadata, "reportPolicy", "$.metadata", errors)
        if report_policy is not None:
            for key, expected in EXPECTED_REPORT_POLICY.items():
                check_equal(
                    report_policy.get(key),
                    expected,
                    f"$.metadata.reportPolicy.{key}",
                    errors,
                )

        runtime_environment = object_field(
            metadata, "runtimeEnvironment", "$.metadata", errors
        )
        if runtime_environment is not None:
            require_fields(
                runtime_environment,
                REQUIRED_RUNTIME_ENVIRONMENT_FIELDS,
                "$.metadata.runtimeEnvironment",
                errors,
            )
            for field in REQUIRED_RUNTIME_ENVIRONMENT_FIELDS:
                value = runtime_environment.get(field)
                if not isinstance(value, str) or not value:
                    errors.append(
                        "$.metadata.runtimeEnvironment."
                        f"{field}: expected non-empty string"
                    )

        metadata_tool = object_field(metadata, "tool", "$.metadata", errors)
        if metadata_tool is not None:
            check_equal(
                metadata_tool.get("name"),
                payload.get("tool"),
                "$.metadata.tool.name",
                errors,
            )
            check_equal(
                metadata_tool.get("schemaVersion"),
                payload.get("schemaVersion"),
                "$.metadata.tool.schemaVersion",
                errors,
            )
            check_equal(
                metadata_tool.get("corpusVersion"),
                payload.get("corpusVersion"),
                "$.metadata.tool.corpusVersion",
                errors,
            )

        command_profiles = list_field(metadata, "commandProfiles", "$.metadata", errors)
        if command_profiles is not None:
            for index, profile_value in enumerate(command_profiles):
                profile_path = f"$.metadata.commandProfiles[{index}]"
                if not isinstance(profile_value, dict):
                    errors.append(f"{profile_path}: expected object")
                    continue
                require_fields(
                    profile_value,
                    REQUIRED_COMMAND_PROFILE_FIELDS,
                    profile_path,
                    errors,
                )
                compiler_config = profile_value.get("compilerConfig")
                if not isinstance(compiler_config, str) or not compiler_config:
                    errors.append(
                        f"{profile_path}.compilerConfig: expected non-empty string"
                    )
                else:
                    command_profile_compiler_configs.append(compiler_config)
                cglc_args = profile_value.get("cglcArgs")
                if not isinstance(cglc_args, list):
                    errors.append(f"{profile_path}.cglcArgs: expected list")
                environment = profile_value.get("environment")
                if not isinstance(environment, list):
                    errors.append(f"{profile_path}.environment: expected list")
                native_requested = profile_value.get("nativeValidationRequested")
                if not isinstance(native_requested, bool):
                    errors.append(
                        f"{profile_path}.nativeValidationRequested: expected bool"
                    )
                name = profile_value.get("name")
                if not isinstance(name, str) or not name:
                    errors.append(f"{profile_path}.name: expected non-empty string")
                    continue
                command_profile_names.append(name)
            if config is not None:
                check_equal(
                    command_profile_names,
                    config.get("commandProfiles"),
                    "$.metadata.commandProfiles",
                    errors,
                )
            if payload.get("baselinePolicy") is None:
                expected_metadata_opt_level = common_opt_level(
                    command_profile_compiler_configs
                )
                if expected_metadata_opt_level is not None:
                    check_equal(
                        metadata.get("optLevel"),
                        expected_metadata_opt_level,
                        "$.metadata.optLevel",
                        errors,
                    )

    if summary is not None:
        require_fields(summary, REQUIRED_SUMMARY_FIELDS, "$.summary", errors)

    if tool_availability is not None:
        cglc = object_field(tool_availability, "cglc", "$.toolAvailability", errors)
        if cglc is not None:
            require_fields(
                cglc,
                REQUIRED_TOOL_AVAILABILITY_FIELDS,
                "$.toolAvailability.cglc",
                errors,
            )
            check_equal(
                cglc.get("role"),
                "required",
                "$.toolAvailability.cglc.role",
                errors,
            )

    if cases is None:
        return errors

    category_counts: dict[str, int] = {}
    category_target_counts: dict[str, dict[str, int]] = {}
    command_profile_counts: dict[str, int] = {}
    fixture_category_by_name: dict[str, str] = {}
    descriptor_evidence_counts: dict[str, int] = {}
    descriptor_status_counts: dict[str, int] = {}
    native_evidence_counts: dict[str, int] = {}
    native_status_counts: dict[str, int] = {}
    opt_level_counts: dict[str, int] = {}
    pass_trace_fingerprint_counts: dict[str, int] = {}
    pass_trace_status_counts: dict[str, int] = {}
    profile_counts: dict[str, int] = {}
    target_counts: dict[str, int] = {}
    skipped_reason_counts: dict[str, int] = {}
    skipped_tool_counts: dict[str, int] = {}
    skipped_tool_cases: dict[str, list[str]] = {}
    skipped_cases_with_tools: set[str] = set()
    unavailable_tools: set[str] = set()
    artifact_available_count = 0
    artifact_byte_size = 0
    artifact_file_count = 0
    dry_run_count = 0
    failure_count = 0
    measured_run_count = 0
    native_validation_requested_count = 0
    pass_trace_manifest_declared_count = 0
    pass_trace_parse_error_count = 0
    pass_trace_requested_count = 0
    skipped_count = 0
    success_count = 0
    timed_case_count = 0
    verification_passed_count = 0
    verification_requested_count = 0
    verification_skipped_count = 0
    warmup_run_count = 0
    unexpected_pass_trace_level_cases: list[str] = []

    for index, case_value in enumerate(cases):
        case_path = f"$.cases[{index}]"
        if not isinstance(case_value, dict):
            errors.append(f"{case_path}: expected object")
            continue
        require_fields(case_value, REQUIRED_CASE_FIELDS, case_path, errors)

        command_profile = object_field(case_value, "commandProfile", case_path, errors)
        artifact = object_field(case_value, "artifactSummary", case_path, errors)
        pass_trace = object_field(case_value, "passTraceProvenance", case_path, errors)
        verification = object_field(case_value, "verification", case_path, errors)

        fixture_name = case_value.get("fixtureName")
        category = case_value.get("fixtureCategory")
        target = case_value.get("target")
        profile = case_value.get("profile")
        for field, value in (
            ("fixtureName", fixture_name),
            ("fixtureCategory", category),
            ("target", target),
            ("profile", profile),
        ):
            if not isinstance(value, str) or not value:
                errors.append(f"{case_path}.{field}: expected non-empty string")
        if all(
            isinstance(value, str) and value
            for value in (fixture_name, target, profile)
        ):
            check_equal(
                case_value.get("case"),
                f"{fixture_name}::{target}::{profile}",
                f"{case_path}.case",
                errors,
            )

        increment(category_counts, category)
        if (
            isinstance(category, str)
            and category
            and isinstance(target, str)
            and target
        ):
            target_category_counts = category_target_counts.setdefault(category, {})
            target_category_counts[target] = target_category_counts.get(target, 0) + 1
        if (
            isinstance(fixture_name, str)
            and fixture_name
            and isinstance(category, str)
            and category
        ):
            previous_category = fixture_category_by_name.get(fixture_name)
            if previous_category is None:
                fixture_category_by_name[fixture_name] = category
            elif previous_category != category:
                errors.append(
                    f"{case_path}.fixtureCategory: expected {previous_category!r} "
                    f"for fixture {fixture_name!r}, got {category!r}"
                )
        increment(opt_level_counts, case_value.get("optLevel"))
        increment(profile_counts, profile)
        increment(target_counts, target)

        if case_value.get("status") == "dry-run":
            dry_run_count += 1
        if case_value.get("success") is True:
            success_count += 1
        if case_value.get("success") is False:
            failure_count += 1
        if case_value.get("nativeValidationRequested") is True:
            native_validation_requested_count += 1
        if case_value.get("skipped") is True:
            skipped_count += 1
            if not isinstance(case_value.get("skipReason"), str) or not case_value.get(
                "skipReason"
            ):
                errors.append(f"{case_path}.skipReason: skipped case needs a reason")
            unavailable = case_value.get("unavailableTools")
            if not isinstance(unavailable, list) or not unavailable:
                errors.append(
                    f"{case_path}.unavailableTools: skipped case needs tool evidence"
                )
            if case_value.get("timing") is not None:
                errors.append(f"{case_path}.timing: skipped case must not be timed")
            reason = case_value.get("skipReason") or "unspecified"
            increment(skipped_reason_counts, reason)

        unavailable_case_tools = case_value.get("unavailableTools")
        if isinstance(unavailable_case_tools, list):
            for tool in unavailable_case_tools:
                if not isinstance(tool, str) or not tool:
                    errors.append(f"{case_path}.unavailableTools: expected strings")
                    continue
                unavailable_tools.add(tool)
                if case_value.get("skipped") is True:
                    skipped_tool_counts[tool] = skipped_tool_counts.get(tool, 0) + 1
                    skipped_tool_cases.setdefault(tool, []).append(
                        str(case_value.get("case"))
                    )
                    skipped_cases_with_tools.add(str(case_value.get("case")))

        timing = case_value.get("timing")
        if isinstance(timing, dict):
            timed_case_count += 1
            runs = timing.get("runs")
            warmups = timing.get("warmups")
            if isinstance(runs, list):
                measured_run_count += len(runs)
            else:
                errors.append(f"{case_path}.timing.runs: expected list")
            if isinstance(warmups, list):
                warmup_run_count += len(warmups)
            else:
                errors.append(f"{case_path}.timing.warmups: expected list")
            check_equal(
                case_value.get("elapsedNs"),
                timing.get("elapsedNs"),
                f"{case_path}.elapsedNs",
                errors,
            )
        elif timing is not None:
            errors.append(f"{case_path}.timing: expected object or null")

        if command_profile is not None:
            require_fields(
                command_profile,
                REQUIRED_COMMAND_PROFILE_FIELDS,
                f"{case_path}.commandProfile",
                errors,
            )
            command_name = command_profile.get("name")
            increment(command_profile_counts, command_name)
            check_equal(
                command_name,
                case_value.get("profile"),
                f"{case_path}.commandProfile.name",
                errors,
            )
            check_equal(
                case_value.get("optLevel"),
                command_profile.get("compilerConfig"),
                f"{case_path}.optLevel",
                errors,
            )
            check_equal(
                case_value.get("profileBuildType"),
                command_profile.get("buildType"),
                f"{case_path}.profileBuildType",
                errors,
            )
            check_equal(
                case_value.get("packageMode"),
                command_profile.get("packageMode"),
                f"{case_path}.packageMode",
                errors,
            )
            check_equal(
                case_value.get("nativeValidationRequested"),
                command_profile.get("nativeValidationRequested"),
                f"{case_path}.nativeValidationRequested",
                errors,
            )

        if pass_trace is not None:
            unexpected_case = check_pass_trace_provenance(
                pass_trace,
                command_profile,
                case_value,
                case_path,
                errors,
            )
            if unexpected_case is not None:
                unexpected_pass_trace_level_cases.append(unexpected_case)
            increment(pass_trace_status_counts, pass_trace.get("status"))
            if pass_trace.get("requested") is True:
                pass_trace_requested_count += 1
            if pass_trace.get("manifestDeclared") is True:
                pass_trace_manifest_declared_count += 1
            if pass_trace.get("parseError") is not None:
                pass_trace_parse_error_count += 1
            fingerprint = pass_trace.get("passScheduleFingerprint")
            if isinstance(fingerprint, str) and fingerprint:
                increment(pass_trace_fingerprint_counts, fingerprint)

        if artifact is not None:
            require_fields(
                artifact,
                REQUIRED_ARTIFACT_SUMMARY_FIELDS,
                f"{case_path}.artifactSummary",
                errors,
            )
            check_equal(
                artifact.get("optLevel"),
                case_value.get("optLevel"),
                f"{case_path}.artifactSummary.optLevel",
                errors,
            )
            check_equal(
                artifact.get("profile"),
                case_value.get("profile"),
                f"{case_path}.artifactSummary.profile",
                errors,
            )
            check_equal(
                artifact.get("requestedPackageMode"),
                case_value.get("packageMode"),
                f"{case_path}.artifactSummary.requestedPackageMode",
                errors,
            )
            check_equal(
                artifact.get("target"),
                case_value.get("target"),
                f"{case_path}.artifactSummary.target",
                errors,
            )
            if artifact.get("available") is True:
                artifact_available_count += 1
            if isinstance(artifact.get("byteSize"), int):
                artifact_byte_size += artifact["byteSize"]
            else:
                errors.append(f"{case_path}.artifactSummary.byteSize: expected int")
            if isinstance(artifact.get("fileCount"), int):
                artifact_file_count += artifact["fileCount"]
            else:
                errors.append(f"{case_path}.artifactSummary.fileCount: expected int")
            files = artifact.get("files")
            if isinstance(files, list) and isinstance(artifact.get("fileCount"), int):
                check_equal(
                    len(files),
                    artifact["fileCount"],
                    f"{case_path}.artifactSummary.fileCount",
                    errors,
                )
            manifest_artifacts = artifact.get("manifestArtifacts")
            if isinstance(manifest_artifacts, list) and isinstance(
                artifact.get("manifestArtifactCount"), int
            ):
                check_equal(
                    len(manifest_artifacts),
                    artifact["manifestArtifactCount"],
                    f"{case_path}.artifactSummary.manifestArtifactCount",
                    errors,
                )
                emitted_manifest_artifact_count = 0
                manifest_artifact_byte_size = 0
                missing_manifest_artifact_count = 0
                for artifact_index, manifest_artifact in enumerate(manifest_artifacts):
                    artifact_path = (
                        f"{case_path}.artifactSummary"
                        f".manifestArtifacts[{artifact_index}]"
                    )
                    if not isinstance(manifest_artifact, dict):
                        errors.append(f"{artifact_path}: expected object")
                        continue
                    kind = manifest_artifact.get("kind")
                    if not isinstance(kind, str) or not kind:
                        errors.append(f"{artifact_path}.kind: expected non-empty str")
                    path = manifest_artifact.get("path")
                    if not isinstance(path, str) or not path:
                        errors.append(f"{artifact_path}.path: expected non-empty str")
                    exists = manifest_artifact.get("exists")
                    if not isinstance(exists, bool):
                        errors.append(f"{artifact_path}.exists: expected bool")
                    artifact_bytes = manifest_artifact.get("bytes")
                    if exists is True:
                        emitted_manifest_artifact_count += 1
                        if (
                            isinstance(artifact_bytes, int)
                            and not isinstance(artifact_bytes, bool)
                            and artifact_bytes >= 0
                        ):
                            manifest_artifact_byte_size += artifact_bytes
                        else:
                            errors.append(
                                f"{artifact_path}.bytes: expected non-negative int"
                            )
                    elif exists is False:
                        missing_manifest_artifact_count += 1
                        check_equal(
                            artifact_bytes,
                            None,
                            f"{artifact_path}.bytes",
                            errors,
                        )
                if isinstance(artifact.get("emittedManifestArtifactCount"), int):
                    check_equal(
                        emitted_manifest_artifact_count,
                        artifact["emittedManifestArtifactCount"],
                        f"{case_path}.artifactSummary.emittedManifestArtifactCount",
                        errors,
                    )
                if isinstance(artifact.get("manifestArtifactByteSize"), int):
                    check_equal(
                        manifest_artifact_byte_size,
                        artifact["manifestArtifactByteSize"],
                        f"{case_path}.artifactSummary.manifestArtifactByteSize",
                        errors,
                    )
                if isinstance(artifact.get("missingManifestArtifactCount"), int):
                    check_equal(
                        missing_manifest_artifact_count,
                        artifact["missingManifestArtifactCount"],
                        f"{case_path}.artifactSummary.missingManifestArtifactCount",
                        errors,
                    )

            descriptor = object_field(
                artifact,
                "nativeArtifactDescriptor",
                f"{case_path}.artifactSummary",
                errors,
            )
            if descriptor is not None:
                require_fields(
                    descriptor,
                    REQUIRED_NATIVE_ARTIFACT_DESCRIPTOR_FIELDS,
                    f"{case_path}.artifactSummary.nativeArtifactDescriptor",
                    errors,
                )
                descriptor_status = native_artifact_descriptor_evidence_status(
                    descriptor
                )
                increment(descriptor_evidence_counts, descriptor_status)
                check_equal(
                    descriptor.get("optimizationEvidenceStatus"),
                    descriptor_status,
                    f"{case_path}.artifactSummary.nativeArtifactDescriptor"
                    ".optimizationEvidenceStatus",
                    errors,
                )
                evidence = descriptor.get("optimizationEvidence")
                if isinstance(evidence, dict):
                    require_fields(
                        evidence,
                        REQUIRED_NATIVE_ARTIFACT_DESCRIPTOR_OPTIMIZATION_EVIDENCE_FIELDS,
                        f"{case_path}.artifactSummary.nativeArtifactDescriptor"
                        ".optimizationEvidence",
                        errors,
                    )
                    optimization_status = evidence.get("status")
                    increment(descriptor_status_counts, optimization_status)
                    if isinstance(optimization_status, str) and optimization_status:
                        for field in ("effectiveLevel", "policy", "requestedLevel"):
                            value = evidence.get(field)
                            if not isinstance(value, str) or not value:
                                errors.append(
                                    f"{case_path}.artifactSummary"
                                    ".nativeArtifactDescriptor.optimizationEvidence"
                                    f".{field}: expected non-empty string when "
                                    "descriptor optimization status evidence is "
                                    "present"
                                )
                elif evidence is not None:
                    errors.append(
                        f"{case_path}.artifactSummary.nativeArtifactDescriptor"
                        ".optimizationEvidence: expected object or null"
                    )

            native_profile = object_field(
                artifact,
                "nativeProfile",
                f"{case_path}.artifactSummary",
                errors,
            )
            if native_profile is not None:
                require_fields(
                    native_profile,
                    REQUIRED_NATIVE_PROFILE_FIELDS,
                    f"{case_path}.artifactSummary.nativeProfile",
                    errors,
                )
                increment(
                    native_evidence_counts,
                    native_optimization_evidence_status(native_profile),
                )
                check_equal(
                    native_profile.get("optimizationEvidenceStatus"),
                    native_optimization_evidence_status(native_profile),
                    f"{case_path}.artifactSummary.nativeProfile"
                    ".optimizationEvidenceStatus",
                    errors,
                )
                optimization = native_profile.get("optimization")
                if isinstance(optimization, dict):
                    require_fields(
                        optimization,
                        REQUIRED_NATIVE_OPTIMIZATION_FIELDS,
                        f"{case_path}.artifactSummary.nativeProfile.optimization",
                        errors,
                    )
                    optimization_status = optimization.get("status")
                    increment(native_status_counts, optimization_status)
                    if isinstance(optimization_status, str) and optimization_status:
                        for field in ("tool", "policy", "requestedLevel"):
                            value = optimization.get(field)
                            if not isinstance(value, str) or not value:
                                errors.append(
                                    f"{case_path}.artifactSummary.nativeProfile"
                                    f".optimization.{field}: expected non-empty "
                                    "string when native optimization status "
                                    "evidence is present"
                                )
                elif optimization is not None:
                    errors.append(
                        f"{case_path}.artifactSummary.nativeProfile.optimization: "
                        "expected object or null"
                    )

        if verification is not None:
            require_fields(
                verification,
                REQUIRED_VERIFICATION_FIELDS,
                f"{case_path}.verification",
                errors,
            )
            if verification.get("requested") is True:
                verification_requested_count += 1
            check_equal(
                verification.get("requested"),
                case_value.get("nativeValidationRequested"),
                f"{case_path}.verification.requested",
                errors,
            )
            if verification.get("status") in ("passed", "build-passed"):
                verification_passed_count += 1
            if verification.get("status") == "skipped":
                verification_skipped_count += 1

    expected_categories = sorted(category_counts)
    expected_category_target_counts = sorted_nested_counts(category_target_counts)
    expected_command_profiles = sorted(command_profile_counts)
    expected_emitted_fixtures = sorted(fixture_category_by_name)
    expected_fixture_counts_by_category: dict[str, int] = {}
    for fixture_category in fixture_category_by_name.values():
        expected_fixture_counts_by_category[fixture_category] = (
            expected_fixture_counts_by_category.get(fixture_category, 0) + 1
        )
    expected_fixture_counts_by_category = sorted_counts(
        expected_fixture_counts_by_category
    )
    expected_descriptor_evidence = sorted_counts(descriptor_evidence_counts)
    expected_descriptor_statuses = sorted(descriptor_status_counts)
    expected_native_evidence = sorted_counts(native_evidence_counts)
    expected_native_statuses = sorted(native_status_counts)
    expected_opt_levels = sorted(opt_level_counts)
    expected_pass_trace_status = sorted_counts(pass_trace_status_counts)
    expected_profiles = sorted(profile_counts)
    expected_targets = sorted(target_counts)
    expected_manifest_artifact_kinds = manifest_artifact_kind_summary(cases)
    expected_manifest_artifact_kind_case_count = manifest_artifact_kind_case_count(
        cases
    )
    skipped_tool_cases = {
        tool: sorted(case_names)
        for tool, case_names in sorted(skipped_tool_cases.items())
    }

    if config is not None:
        configured_fixtures = sorted_string_list_field(
            config, "fixtures", "$.config", errors
        )
        if configured_fixtures is not None:
            missing_configured_fixtures = sorted(
                set(expected_emitted_fixtures) - set(configured_fixtures)
            )
            if missing_configured_fixtures:
                errors.append(
                    "$.config.fixtures: emitted case fixture(s) missing from "
                    f"configured fixtures {missing_configured_fixtures!r}"
                )
        configured_profiles = sorted_string_list_field(
            config, "profiles", "$.config", errors
        )
        if configured_profiles is not None:
            check_equal(
                configured_profiles,
                expected_profiles,
                "$.config.profiles",
                errors,
            )
        configured_command_profiles = sorted_string_list_field(
            config, "commandProfiles", "$.config", errors
        )
        if configured_command_profiles is not None:
            check_equal(
                configured_command_profiles,
                configured_profiles
                if configured_profiles is not None
                else expected_command_profiles,
                "$.config.commandProfiles",
                errors,
            )
        configured_targets = sorted_string_list_field(
            config, "targets", "$.config", errors
        )
        if configured_targets is not None:
            missing_configured_targets = sorted(
                set(expected_targets) - set(configured_targets)
            )
            if missing_configured_targets:
                errors.append(
                    "$.config.targets: emitted case target(s) missing from "
                    f"configured targets {missing_configured_targets!r}"
                )

    if metadata is not None:
        check_equal(
            metadata.get("caseCategories"),
            expected_categories,
            "$.metadata.caseCategories",
            errors,
        )
        check_equal(
            metadata.get("timedCaseCount"),
            timed_case_count,
            "$.metadata.timedCaseCount",
            errors,
        )

    if summary is not None:
        check_equal(summary.get("caseCount"), len(cases), "$.summary.caseCount", errors)
        check_equal(
            summary.get("caseCountByCategory"),
            sorted_counts(category_counts),
            "$.summary.caseCountByCategory",
            errors,
        )
        check_equal(
            summary.get("caseCountByCategoryTarget"),
            expected_category_target_counts,
            "$.summary.caseCountByCategoryTarget",
            errors,
        )
        check_equal(
            summary.get("caseCountByCommandProfile"),
            sorted_counts(command_profile_counts),
            "$.summary.caseCountByCommandProfile",
            errors,
        )
        check_equal(
            summary.get(
                "caseCountByNativeArtifactDescriptorOptimizationEvidenceStatus"
            ),
            expected_descriptor_evidence,
            "$.summary.caseCountByNativeArtifactDescriptorOptimizationEvidenceStatus",
            errors,
        )
        descriptor_evidence = object_field(
            summary,
            "nativeArtifactDescriptorOptimizationEvidence",
            "$.summary",
            errors,
        )
        if descriptor_evidence is not None:
            require_fields(
                descriptor_evidence,
                REQUIRED_NATIVE_ARTIFACT_DESCRIPTOR_OPTIMIZATION_EVIDENCE_SUMMARY_FIELDS,
                "$.summary.nativeArtifactDescriptorOptimizationEvidence",
                errors,
            )
            check_equal(
                descriptor_evidence,
                native_artifact_descriptor_evidence_summary(
                    len(cases), descriptor_evidence_counts
                ),
                "$.summary.nativeArtifactDescriptorOptimizationEvidence",
                errors,
            )
        check_equal(
            summary.get("caseCountByNativeArtifactDescriptorOptimizationStatus"),
            sorted_counts(descriptor_status_counts),
            "$.summary.caseCountByNativeArtifactDescriptorOptimizationStatus",
            errors,
        )
        check_equal(
            summary.get("caseCountByNativeOptimizationEvidenceStatus"),
            expected_native_evidence,
            "$.summary.caseCountByNativeOptimizationEvidenceStatus",
            errors,
        )
        native_evidence = object_field(
            summary, "nativeOptimizationEvidence", "$.summary", errors
        )
        if native_evidence is not None:
            require_fields(
                native_evidence,
                REQUIRED_NATIVE_OPTIMIZATION_EVIDENCE_FIELDS,
                "$.summary.nativeOptimizationEvidence",
                errors,
            )
            check_equal(
                native_evidence,
                native_optimization_evidence_summary(
                    len(cases), native_evidence_counts
                ),
                "$.summary.nativeOptimizationEvidence",
                errors,
            )
        check_equal(
            summary.get("caseCountByNativeOptimizationStatus"),
            sorted_counts(native_status_counts),
            "$.summary.caseCountByNativeOptimizationStatus",
            errors,
        )
        check_equal(
            summary.get("caseCountByOptLevel"),
            sorted_counts(opt_level_counts),
            "$.summary.caseCountByOptLevel",
            errors,
        )
        check_equal(
            summary.get("caseCountByPassTraceStatus"),
            expected_pass_trace_status,
            "$.summary.caseCountByPassTraceStatus",
            errors,
        )
        check_equal(
            summary.get("caseCountByProfile"),
            sorted_counts(profile_counts),
            "$.summary.caseCountByProfile",
            errors,
        )
        check_equal(
            summary.get("caseCountByTarget"),
            sorted_counts(target_counts),
            "$.summary.caseCountByTarget",
            errors,
        )
        check_equal(
            summary.get("caseCategories"),
            expected_categories,
            "$.summary.caseCategories",
            errors,
        )
        check_equal(
            summary.get("commandProfiles"),
            expected_command_profiles,
            "$.summary.commandProfiles",
            errors,
        )
        check_equal(
            summary.get("commandProfileCount"),
            len(expected_command_profiles),
            "$.summary.commandProfileCount",
            errors,
        )
        check_equal(
            summary.get("categoryCount"),
            len(expected_categories),
            "$.summary.categoryCount",
            errors,
        )
        check_equal(
            summary.get("dryRunCount"), dry_run_count, "$.summary.dryRunCount", errors
        )
        check_equal(
            summary.get("failureCount"), failure_count, "$.summary.failureCount", errors
        )
        configured_fixture_count = None
        if config is not None and isinstance(config.get("fixtures"), list):
            configured_fixture_count = len(config["fixtures"])
        expected_fixture_count = (
            configured_fixture_count
            if configured_fixture_count is not None
            else len(expected_emitted_fixtures)
        )
        check_equal(
            summary.get("fixtureCount"),
            expected_fixture_count,
            "$.summary.fixtureCount",
            errors,
        )
        fixture_count_by_category = summary.get("fixtureCountByCategory")
        if not isinstance(fixture_count_by_category, dict):
            errors.append("$.summary.fixtureCountByCategory: expected object")
        else:
            parsed_fixture_counts: dict[str, int] = {}
            for category, count in fixture_count_by_category.items():
                if not isinstance(category, str) or not category:
                    errors.append(
                        "$.summary.fixtureCountByCategory: expected category keys"
                    )
                    continue
                if isinstance(count, bool) or not isinstance(count, int) or count < 0:
                    errors.append(
                        "$.summary.fixtureCountByCategory."
                        f"{category}: expected non-negative int"
                    )
                    continue
                parsed_fixture_counts[category] = count
            if configured_fixture_count is not None:
                check_equal(
                    sum(parsed_fixture_counts.values()),
                    configured_fixture_count,
                    "$.summary.fixtureCountByCategory",
                    errors,
                )
            missing_fixture_categories = sorted(
                set(expected_fixture_counts_by_category) - set(parsed_fixture_counts)
            )
            if missing_fixture_categories:
                errors.append(
                    "$.summary.fixtureCountByCategory: emitted fixture "
                    f"category(s) missing from selected fixture accounting "
                    f"{missing_fixture_categories!r}"
                )
        check_equal(
            summary.get("nativeOptimizationStatuses"),
            expected_native_statuses,
            "$.summary.nativeOptimizationStatuses",
            errors,
        )
        check_equal(
            summary.get("nativeArtifactDescriptorOptimizationStatuses"),
            expected_descriptor_statuses,
            "$.summary.nativeArtifactDescriptorOptimizationStatuses",
            errors,
        )
        check_equal(
            summary.get("nativeValidationRequestedCount"),
            native_validation_requested_count,
            "$.summary.nativeValidationRequestedCount",
            errors,
        )
        check_equal(
            summary.get("optLevels"), expected_opt_levels, "$.summary.optLevels", errors
        )
        check_equal(
            summary.get("optLevelCount"),
            len(expected_opt_levels),
            "$.summary.optLevelCount",
            errors,
        )
        pass_trace_summary = object_field(
            summary, "passTraceProvenance", "$.summary", errors
        )
        if pass_trace_summary is not None:
            require_fields(
                pass_trace_summary,
                REQUIRED_PASS_TRACE_SUMMARY_FIELDS,
                "$.summary.passTraceProvenance",
                errors,
            )
            check_equal(
                pass_trace_summary,
                pass_trace_provenance_summary(
                    case_count=len(cases),
                    fingerprint_counts=pass_trace_fingerprint_counts,
                    status_counts=pass_trace_status_counts,
                    requested_count=pass_trace_requested_count,
                    manifest_declared_count=pass_trace_manifest_declared_count,
                    parse_error_count=pass_trace_parse_error_count,
                    unexpected_level_cases=unexpected_pass_trace_level_cases,
                ),
                "$.summary.passTraceProvenance",
                errors,
            )
        check_equal(
            summary.get("skippedCaseCountByReason"),
            sorted_counts(skipped_reason_counts),
            "$.summary.skippedCaseCountByReason",
            errors,
        )
        check_equal(
            summary.get("skippedCasesWithUnavailableTools"),
            sorted(skipped_cases_with_tools),
            "$.summary.skippedCasesWithUnavailableTools",
            errors,
        )
        check_equal(
            summary.get("skippedCount"), skipped_count, "$.summary.skippedCount", errors
        )
        check_equal(
            summary.get("skippedToolCaseCountByTool"),
            sorted_counts(skipped_tool_counts),
            "$.summary.skippedToolCaseCountByTool",
            errors,
        )
        check_equal(
            summary.get("skippedToolCasesByTool"),
            skipped_tool_cases,
            "$.summary.skippedToolCasesByTool",
            errors,
        )
        check_equal(
            summary.get("successCount"), success_count, "$.summary.successCount", errors
        )
        check_equal(
            summary.get("artifactAvailableCount"),
            artifact_available_count,
            "$.summary.artifactAvailableCount",
            errors,
        )
        check_equal(
            summary.get("artifactByteSize"),
            artifact_byte_size,
            "$.summary.artifactByteSize",
            errors,
        )
        check_equal(
            summary.get("artifactFileCount"),
            artifact_file_count,
            "$.summary.artifactFileCount",
            errors,
        )
        manifest_artifact_kinds = summary.get("manifestArtifactKinds")
        if "manifestArtifactKinds" in summary and not isinstance(
            manifest_artifact_kinds, dict
        ):
            errors.append("$.summary.manifestArtifactKinds: expected object")
        if isinstance(manifest_artifact_kinds, dict):
            for kind, kind_metrics in manifest_artifact_kinds.items():
                kind_path = f"$.summary.manifestArtifactKinds.{kind}"
                if not isinstance(kind, str) or not kind:
                    errors.append("$.summary.manifestArtifactKinds: expected kind keys")
                    continue
                if not isinstance(kind_metrics, dict):
                    errors.append(f"{kind_path}: expected object")
                    continue
                require_fields(
                    kind_metrics,
                    REQUIRED_MANIFEST_ARTIFACT_KIND_FIELDS,
                    kind_path,
                    errors,
                )
                for field in REQUIRED_MANIFEST_ARTIFACT_KIND_FIELDS:
                    value = kind_metrics.get(field)
                    if (
                        isinstance(value, bool)
                        or not isinstance(value, int)
                        or value < 0
                    ):
                        errors.append(f"{kind_path}.{field}: expected non-negative int")
            check_equal(
                manifest_artifact_kinds,
                expected_manifest_artifact_kinds,
                "$.summary.manifestArtifactKinds",
                errors,
            )
        check_equal(
            summary.get("manifestArtifactKindCaseCount"),
            expected_manifest_artifact_kind_case_count,
            "$.summary.manifestArtifactKindCaseCount",
            errors,
        )
        check_equal(
            summary.get("manifestArtifactKindCount"),
            len(expected_manifest_artifact_kinds),
            "$.summary.manifestArtifactKindCount",
            errors,
        )
        check_equal(
            summary.get("measuredRunCount"),
            measured_run_count,
            "$.summary.measuredRunCount",
            errors,
        )
        check_equal(
            summary.get("timedCaseCount"),
            timed_case_count,
            "$.summary.timedCaseCount",
            errors,
        )
        check_equal(
            summary.get("unavailableToolCount"),
            len(unavailable_tools),
            "$.summary.unavailableToolCount",
            errors,
        )
        check_equal(
            summary.get("verificationPassedCount"),
            verification_passed_count,
            "$.summary.verificationPassedCount",
            errors,
        )
        check_equal(
            summary.get("verificationRequestedCount"),
            verification_requested_count,
            "$.summary.verificationRequestedCount",
            errors,
        )
        check_equal(
            summary.get("verificationSkippedCount"),
            verification_skipped_count,
            "$.summary.verificationSkippedCount",
            errors,
        )
        check_equal(
            summary.get("warmupRunCount"),
            warmup_run_count,
            "$.summary.warmupRunCount",
            errors,
        )
        if metadata is not None:
            check_equal(
                summary.get("measurementWindow"),
                metadata.get("measurementWindow"),
                "$.summary.measurementWindow",
                errors,
            )
        timing_window = object_field(summary, "timingWindow", "$.summary", errors)
        if timing_window is not None:
            check_equal(
                timing_window.get("measuredRunCount"),
                measured_run_count,
                "$.summary.timingWindow.measuredRunCount",
                errors,
            )
            check_equal(
                timing_window.get("timedCaseCount"),
                timed_case_count,
                "$.summary.timingWindow.timedCaseCount",
                errors,
            )
            check_equal(
                timing_window.get("warmupRunCount"),
                warmup_run_count,
                "$.summary.timingWindow.warmupRunCount",
                errors,
            )

    check_native_optimization_run_identity(
        payload,
        metadata,
        native_status_counts,
        errors,
    )
    if threshold_readiness is not None:
        check_threshold_baseline_readiness_accounting(
            threshold_readiness,
            "$.thresholdBaselineReadiness",
            timed_case_count=timed_case_count,
            skipped_tool_counts=skipped_tool_counts,
            skipped_tool_cases=skipped_tool_cases,
            skipped_cases=sorted(
                str(case.get("case"))
                for case in cases
                if isinstance(case, dict)
                and case.get("skipped") is True
                and case.get("case") is not None
            ),
            skipped_cases_with_tools=sorted(skipped_cases_with_tools),
            errors=errors,
        )

    baseline_policy = payload.get("baselinePolicy")
    if baseline_policy is not None:
        if not isinstance(baseline_policy, dict):
            errors.append("$.baselinePolicy: expected object")
        elif metadata is not None:
            require_fields(
                baseline_policy,
                REQUIRED_BASELINE_POLICY_FIELDS,
                "$.baselinePolicy",
                errors,
            )
            for policy_key in (
                "hostClass",
                "optLevel",
                "targetProfile",
                "toolchainLabel",
            ):
                value = baseline_policy.get(policy_key)
                if not isinstance(value, str) or not value:
                    errors.append(
                        f"$.baselinePolicy.{policy_key}: expected non-empty string"
                    )
            for policy_key, metadata_key in (
                ("optLevel", "optLevel"),
                ("targetProfile", "targetProfile"),
                ("hostLabel", "hostLabel"),
                ("hostClass", "hostClass"),
                ("toolchainLabel", "toolchainLabel"),
                ("toolchainVersion", "toolchainVersion"),
            ):
                policy_value = baseline_policy.get(policy_key)
                if isinstance(policy_value, str) and policy_value:
                    check_equal(
                        metadata.get(metadata_key),
                        policy_value,
                        f"$.metadata.{metadata_key}",
                        errors,
                    )
            if "comparisonWindow" in baseline_policy:
                check_equal(
                    metadata.get("comparisonWindow"),
                    baseline_policy["comparisonWindow"],
                    "$.metadata.comparisonWindow",
                    errors,
                )

            host = payload.get("host")
            if isinstance(baseline_policy.get("hostLabel"), str):
                if not isinstance(host, dict):
                    errors.append("$.host: expected object when hostLabel is supplied")
                else:
                    check_equal(
                        host.get("label"),
                        baseline_policy["hostLabel"],
                        "$.host.label",
                        errors,
                    )
            if isinstance(baseline_policy.get("hostClass"), str):
                if not isinstance(host, dict):
                    errors.append("$.host: expected object when hostClass is supplied")
                else:
                    check_equal(
                        host.get("class"),
                        baseline_policy["hostClass"],
                        "$.host.class",
                        errors,
                    )

            label = baseline_policy.get("toolchainLabel")
            if isinstance(label, str) and label:
                toolchains = object_field(payload, "toolchains", "$", errors)
                toolchain = object_field(payload, "toolchain", "$", errors)
                if toolchains is not None:
                    entry = object_field(toolchains, label, "$.toolchains", errors)
                    if entry is not None:
                        require_fields(
                            entry,
                            ["available", "role", "status"],
                            f"$.toolchains.{label}",
                            errors,
                        )
                        check_equal(
                            entry.get("role"),
                            "required",
                            f"$.toolchains.{label}.role",
                            errors,
                        )
                if toolchain is not None:
                    check_equal(
                        toolchain.get("label"),
                        label,
                        "$.toolchain.label",
                        errors,
                    )
                    if isinstance(baseline_policy.get("toolchainVersion"), str):
                        check_equal(
                            toolchain.get("version"),
                            baseline_policy["toolchainVersion"],
                            "$.toolchain.version",
                            errors,
                        )

    return errors


def assert_report_contract(payload: Any, label: str) -> None:
    errors = report_contract_errors(payload)
    if errors:
        formatted = "\n  - ".join(errors)
        raise AssertionError(f"{label} report contract failed:\n  - {formatted}")


def load_runner(root: Path):
    tool_path = root / "tools" / "benchmark_performance_corpus.py"
    sys.path.insert(0, str(tool_path.parent))
    spec = importlib.util.spec_from_file_location(
        "benchmark_performance_corpus", tool_path
    )
    if spec is None or spec.loader is None:
        raise RuntimeError(f"could not import {tool_path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def run_tool(
    root: Path, *args: str, env: dict[str, str] | None = None
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            sys.executable,
            str(root / "tools" / "benchmark_performance_corpus.py"),
            "--root",
            str(root),
            *args,
        ],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=env,
    )


def fake_cglc_path(tmp_path: Path, *, windows: bool | None = None) -> Path:
    if windows is None:
        windows = os.name == "nt"
    return tmp_path / ("fake-cglc.cmd" if windows else "fake-cglc")


def write_fake_cglc(tmp_path: Path) -> Path:
    fake_cglc = fake_cglc_path(tmp_path)
    fake_script = tmp_path / "fake-cglc.py"
    fake_script.write_text(
        """#!/usr/bin/env python3
import hashlib
import json
import os
import sys
from pathlib import Path


def value_after(args, flag, default=None):
    if flag not in args:
        return default
    index = args.index(flag)
    return args[index + 1]


def write_json(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\\n", encoding="utf-8")


def optimization_record(args):
    mode = os.environ.get("CROSSGL_FAKE_NATIVE_PROFILE_MODE")
    if mode == "optimization-without-status":
        return {
            "tool": "spirv-opt",
            "policy": "use-when-available",
            "requestedLevel": value_after(args, "--opt-level", "O0"),
            "level": "-O",
        }
    requested = value_after(args, "--opt-level", "O0")
    if requested == "O2":
        status = os.environ.get("CROSSGL_FAKE_SPIRV_OPT_STATUS", "applied")
        if status not in {"applied", "skipped-tool-missing"}:
            status = "applied"
        return {
            "tool": "spirv-opt",
            "policy": "use-when-available",
            "requestedLevel": "O2",
            "level": "-O",
            "status": status,
        }
    return {
        "tool": "spirv-opt",
        "policy": "disabled-by-opt-level",
        "requestedLevel": requested if requested in {"O0", "O1"} else "O0",
        "level": "none",
        "status": "skipped-disabled",
    }


def descriptor_optimization_evidence(target, args):
    requested = value_after(args, "--opt-level", "O1")
    if target == "vulkan":
        optimization = optimization_record(args)
        evidence = {
            "requestedLevel": optimization.get("requestedLevel", requested),
            "effectiveLevel": optimization.get("requestedLevel", requested),
            "policy": optimization.get("policy", "use-when-available"),
            "status": optimization.get("status", "planned"),
            "tool": optimization.get("tool", "spirv-opt"),
        }
        level = optimization.get("level")
        if isinstance(level, str) and level != "none":
            evidence["toolFlag"] = level
        evidence["evidenceSource"] = {
            "kind": "native-profile",
            "path": "backend/vulkan",
        }
        return evidence
    return {
        "requestedLevel": requested,
        "effectiveLevel": requested,
        "policy": "source-package-descriptor",
        "status": "planned",
        "tool": "dxc",
        "toolFlag": f"-{requested}",
    }


def native_artifact_descriptor(module, target, artifacts, args):
    return {
        "schemaVersion": 1,
        "kind": "crossgl-native-artifact",
        "contractVersion": "native-artifact-v0",
        "target": target,
        "artifactPath": artifacts["nativeBinary"],
        "optimizationLevel": value_after(args, "--opt-level", "O1"),
        "optimizationEvidence": descriptor_optimization_evidence(target, args),
    }


def pass_trace_record(args):
    level = value_after(args, "--opt-level", "O1")
    return {
        "schemaVersion": 1,
        "kind": "hir-pass-trace",
        "optimizationLevel": level,
        "optimizationPolicy": {
            "id": f"fake-hir-{level.lower()}",
            "name": f"Fake HIR {level}",
            "description": "Fake compiler pass trace for performance runner tests.",
            "backendInputMode": "backend-validated",
        },
        "passSchedule": {
            "fingerprint": "fnv1a64:0123456789abcdef",
            "fingerprintPolicy": "scheduled-pass-ids-v1",
            "stability": "stable-opt-level-policy",
        },
        "scheduledPassCount": 1,
        "passCount": 1,
        "changedPassCount": 0,
        "diagnosticPassCount": 0,
        "errorPassCount": 0,
        "changed": False,
        "completed": True,
        "stopReason": "none",
        "passes": [
            {
                "index": 0,
                "id": "hir.validate.backend-input",
                "name": "hir.validate.backend-input",
                "category": "validation",
                "changed": False,
                "status": "completed",
                "diagnosticCount": 0,
                "errorCount": 0,
            }
        ],
    }


def vulkan_native_profile(module, artifacts, args):
    mode = os.environ.get("CROSSGL_FAKE_NATIVE_PROFILE_MODE")
    optimization = None
    if mode != "missing-debug-optimization":
        optimization = optimization_record(args)
    debug = {
        "binaryFormat": "SPIR-V",
        "assemblyFormat": "SPIR-V assembly",
        "validationTargetEnv": "vulkan1.2",
        "disassembly": {
            "tool": "spirv-dis",
            "policy": "use-when-available",
            "status": "skipped-tool-missing",
            "path": None,
        },
    }
    if optimization is not None:
        debug["optimization"] = optimization
    return {
        "schemaVersion": 1,
        "module": module,
        "target": "vulkan",
        "api": "vulkan",
        "profile": {
            "name": "vulkan-prototype",
            "vulkanVersion": "1.2",
            "spirvVersion": "1.0",
        },
        "generator": "fake-cglc",
        "artifacts": {
            "backendAssembly": artifacts["backendAssembly"],
            "nativeBinary": artifacts["nativeBinary"],
        },
        "debug": debug,
    }


def build(args):
    source = Path(args[1])
    target = value_after(args, "--target")
    output = Path(value_after(args, "--output"))
    module = source.stem
    source_hash = hashlib.sha256(source.read_bytes()).hexdigest()
    if target == "vulkan":
        artifacts = {
            "backendAssembly": f"backend/{target}/{module}.spvasm",
            "nativeBinary": f"backend/{target}/{module}.spv",
            "nativeArtifactDescriptor": "metadata/native-artifact.json",
            "nativeProfile": f"backend/{target}/{module}.profile.json",
            "debugMetadata": "ir/debug-metadata.json",
            "hirSourceMap": "ir/hir-source-map.json",
        }
    else:
        artifacts = {
            "backendSource": f"backend/{target}/{module}.generated",
            "nativeBinary": f"backend/{target}/{module}.native",
            "nativeArtifactDescriptor": "metadata/native-artifact.json",
            "nativeBinaryStatus": "planned",
            "debugMetadata": "ir/debug-metadata.json",
            "hirSourceMap": "ir/hir-source-map.json",
        }
    output.mkdir(parents=True, exist_ok=True)
    native_profile = (
        vulkan_native_profile(module, artifacts, args) if target == "vulkan" else None
    )
    for kind, relative in artifacts.items():
        if kind == "nativeBinaryStatus":
            continue
        artifact_path = output / relative
        artifact_path.parent.mkdir(parents=True, exist_ok=True)
        if kind == "nativeProfile":
            mode = os.environ.get("CROSSGL_FAKE_NATIVE_PROFILE_MODE")
            if mode == "invalid-json":
                artifact_path.write_text("{not-json\\n", encoding="utf-8")
                continue
            if mode == "declared-missing":
                continue
            write_json(artifact_path, native_profile)
            continue
        if kind == "nativeArtifactDescriptor":
            write_json(artifact_path, native_artifact_descriptor(module, target, artifacts, args))
            continue
        artifact_path.write_text(f"{kind}:{module}:{target}\\n", encoding="utf-8")
    write_json(output / "ir/hir-pass-trace.json", pass_trace_record(args))
    write_json(
        output / "manifest.json",
        {
            "schemaVersion": 1,
            "compiler": {
                "name": "CrossGL-Compiler",
                "version": "0.6.0-fixture",
                "llvmVersion": "fixture",
            },
            "module": module,
            "target": target,
            "sourceHash": {"algorithm": "sha256", "value": source_hash},
            "artifacts": artifacts,
        },
    )
    write_json(
        output / "reflection.json",
        {
            "schemaVersion": 1,
            "module": module,
            "target": target,
            "nativeBinary": artifacts["nativeBinary"],
        },
    )
    write_json(output / "diagnostics.json", {"schemaVersion": 1, "diagnostics": []})
    print(json.dumps({"schemaVersion": 1, "diagnostics": []}))
    return 0


def verify(args):
    package = Path(args[2])
    manifest = json.loads((package / "manifest.json").read_text(encoding="utf-8"))
    artifact_count = len(
        [
            value
            for key, value in manifest["artifacts"].items()
            if key != "nativeBinaryStatus" and isinstance(value, str)
        ]
    )
    print(
        json.dumps(
            {
                "schemaVersion": 1,
                "packagePath": package.as_posix(),
                "success": True,
                "summary": {
                    "module": manifest["module"],
                    "target": manifest["target"],
                    "nativeBinaryStatus": manifest["artifacts"].get("nativeBinaryStatus"),
                    "artifactCount": artifact_count,
                    "debugArtifactsPresent": True,
                },
                "diagnosticCounts": {"note": 0, "warning": 0, "error": 0},
                "diagnostics": [],
            },
            sort_keys=True,
        )
    )
    return 0


def main():
    args = sys.argv[1:]
    if args and args[0] == "build":
        return build(args)
    if len(args) >= 3 and args[:2] == ["package", "verify"]:
        return verify(args)
    print(json.dumps({"schemaVersion": 1, "diagnostics": []}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
""",
        encoding="utf-8",
    )
    os.chmod(fake_script, 0o755)
    if os.name == "nt":
        fake_cglc.write_text(
            f'@"{sys.executable}" "{fake_script}" %*\n',
            encoding="utf-8",
        )
    else:
        fake_cglc.write_text(
            "#!/usr/bin/env python3\n"
            "import runpy\n"
            f"runpy.run_path({str(fake_script)!r}, run_name='__main__')\n",
            encoding="utf-8",
        )
    os.chmod(fake_cglc, 0o755)
    return fake_cglc


def check_fake_cglc_path_selection() -> None:
    with tempfile.TemporaryDirectory(prefix="crossgl-perf-runner-path-check-") as tmp:
        tmp_path = Path(tmp)
        expect(
            fake_cglc_path(tmp_path, windows=True).name == "fake-cglc.cmd",
            "Windows fake cglc should use an executable command extension",
        )
        expect(
            fake_cglc_path(tmp_path, windows=False).name == "fake-cglc",
            "POSIX fake cglc should keep the shebang-script path",
        )
        fake_cglc = write_fake_cglc(tmp_path)
        expect(fake_cglc.is_file(), "fake cglc should be written")
        expect(os.access(fake_cglc, os.X_OK), "fake cglc should be executable")


def check_corpus_document(root: Path) -> None:
    runner = load_runner(root)
    document = runner.corpus_document(["milestone6-smoke"])
    expect(document["schemaVersion"] == 1, "corpus schemaVersion")
    expect(document["tool"] == "benchmark_performance_corpus", "corpus tool")
    expect(document["corpusVersion"] == "milestone6-smoke-v1", "corpus version")
    expect(document["defaultCorpus"] == "milestone6-smoke", "default corpus")
    corpora = document["corpora"]
    expect(len(corpora) == 1, "expected one selected corpus")
    fixtures = corpora[0]["fixtures"]
    expect(
        [fixture["name"] for fixture in fixtures]
        == [
            "storage-buffer-compute",
            "texture-sampling-descriptor-array",
            "texture-descriptor-array",
            "mixed-resource-descriptor-array",
            "storage-image-explicit-format",
            "storage-image-descriptor-array",
            "storage-image-atomics",
            "storage-image-atomic-descriptor-array",
            "nested-control-flow",
            "while-control-flow",
            "metal-storage-buffer-folded-descriptor-array",
        ],
        "fixture order changed",
    )
    expect(
        [fixture["category"] for fixture in fixtures]
        == [
            "storage-buffers",
            "texture-sampling",
            "descriptor-arrays",
            "descriptor-arrays",
            "storage-images",
            "storage-images",
            "atomics",
            "atomics",
            "control-flow",
            "control-flow",
            "storage-buffers",
        ],
        "fixture category coverage changed",
    )
    expect(
        all(fixture["path"].startswith("tests/fixtures/") for fixture in fixtures),
        "fixtures should come from the shared fixture directory",
    )
    expect(
        all((root / fixture["path"]).is_file() for fixture in fixtures),
        "manifest fixtures should exist",
    )


def check_cli_list(root: Path) -> None:
    result = run_tool(root, "--list-corpus")
    expect(result.returncode == 0, result.stderr + result.stdout)
    payload = json.loads(result.stdout)
    expect(payload["corpusVersion"] == "milestone6-smoke-v1", "list corpus version")
    expect(payload["corpora"][0]["name"] == "milestone6-smoke", "list corpus name")
    expect(len(payload["corpora"][0]["fixtures"]) == 11, "list fixture count")


def check_cli_dry_run(root: Path) -> None:
    runner = load_runner(root)
    result = run_tool(
        root,
        "--dry-run",
        "--cglc",
        "build/cglc",
        "--profile",
        "debug,release",
        "--target",
        "directx",
    )
    expect(result.returncode == 0, result.stderr + result.stdout)
    payload = json.loads(result.stdout)
    assert_report_contract(payload, "dry-run")
    expect(payload["schemaVersion"] == 1, "dry-run schemaVersion")
    expect(payload["corpusVersion"] == "milestone6-smoke-v1", "dry-run corpus version")
    expect(payload["dryRun"] is True, "dryRun flag")
    expect(
        payload["config"]["corpusVersion"] == "milestone6-smoke-v1",
        "config corpus version",
    )
    expect(payload["config"]["profiles"] == ["debug", "release"], "profiles")
    expect(
        payload["config"]["commandProfiles"] == ["debug", "release"],
        "command profiles",
    )
    expect(payload["config"]["targets"] == ["directx"], "targets")
    expect(payload["config"]["repeat"] == 3, "default repeat")
    expect(payload["config"]["warmup"] == 1, "default warmup")
    expect(payload["config"]["root"] == ".", "normalized dry-run root")
    expect(payload["config"]["compilerPath"] == "build/cglc", "compiler path")
    expect(
        payload["config"]["workDir"] == "build/performance-corpus-dry-run",
        "deterministic dry-run work dir",
    )
    expect(
        payload["config"]["manifestPath"]
        == "tests/performance/performance_corpus_manifest.json",
        "manifest path",
    )
    for label, value in (
        ("config.compilerPath", payload["config"]["compilerPath"]),
        ("config.manifestPath", payload["config"]["manifestPath"]),
        ("config.workDir", payload["config"]["workDir"]),
    ):
        expect_relative_report_path(value, label)
    expect(
        payload["metadata"]["benchmarkProfile"] == "milestone6-advisory-v1",
        "advisory metadata profile",
    )
    expect(
        payload["metadata"]["comparisonWindow"]
        == {"sampleCount": 0, "unit": "elapsedNs", "warmupCount": 0},
        "dry-run comparison window metadata",
    )
    expect(
        payload["metadata"]["measurementWindow"]
        == {"sampleCount": 0, "unit": "elapsedNs", "warmupCount": 0},
        "dry-run measurement window metadata",
    )
    expect(
        payload["metadata"]["optLevel"] == "mixed:Debug,Release",
        "dry-run opt-level metadata",
    )
    expect(
        payload["metadata"]["targetProfile"] == "crossgl-milestone6-smoke",
        "dry-run target profile metadata",
    )
    default_host_class = runner.default_host_class()
    expected_window = {"sampleCount": 0, "unit": "elapsedNs", "warmupCount": 0}
    expect(
        payload["baselinePolicy"]
        == {
            "comparisonWindow": expected_window,
            "hostClass": default_host_class,
            "optLevel": "mixed:Debug,Release",
            "targetProfile": "crossgl-milestone6-smoke",
            "toolchainLabel": "cglc",
        },
        "dry-run default baseline policy metadata",
    )
    expect(
        payload["metadata"]["hostClass"] == default_host_class,
        "dry-run host class metadata",
    )
    expect(
        "hostLabel" not in payload["metadata"],
        "dry-run host label remains explicit-only",
    )
    expect(
        payload["metadata"]["toolchainLabel"] == "cglc",
        "dry-run toolchain label metadata",
    )
    expect(
        payload["host"] == {"class": default_host_class},
        "dry-run host mirror",
    )
    expect(
        payload["toolchain"] == {"label": "cglc", "status": "not-checked"},
        "dry-run toolchain mirror",
    )
    expect(
        payload["toolchains"]["cglc"]["role"] == "required",
        "dry-run required toolchain metadata",
    )
    expect(
        payload["metadata"]["passTraceProvenance"]
        == {
            "artifactKind": PASS_TRACE_KIND,
            "captureMode": "package-sidecar",
            "commandFlag": "--debug-ir",
            "manifestPolicy": "non-manifest-sidecar",
            "reportPolicy": "report-only",
            "schemaVersion": 1,
            "sidecarPath": PASS_TRACE_SIDECAR_PATH,
        },
        "dry-run pass trace provenance metadata",
    )
    expect(
        payload["metadata"]["timedCaseCount"] == 0,
        "dry-run metadata timed count",
    )
    expect(
        payload["metadata"]["reportPolicy"]
        == {
            "artifactSize": "report-only",
            "baselineCuration": "report-only",
            "nativeOptimization": "report-only",
            "packageArtifacts": "report-only",
            "structural": "hard-fail",
            "timing": "report-only",
        },
        "report policy metadata",
    )
    advisory_policy = payload["advisoryThresholdPolicy"]
    expect(
        advisory_policy == payload["metadata"]["advisoryThresholdPolicy"],
        "advisory threshold policy metadata mirror",
    )
    expect(advisory_policy["mode"] == "report-only", "advisory threshold mode")
    expect(
        advisory_policy["failurePolicy"].startswith("report-only"),
        "advisory threshold failure policy",
    )
    expect(advisory_policy["ruleCount"] == 0, "runner emits no threshold rules")
    expect(advisory_policy["rules"] == [], "runner threshold rules omitted")
    expect(
        advisory_policy["stableBaselineDataPresent"] is False,
        "runner has no stable baseline data",
    )
    expect(
        advisory_policy["enforcement"]
        == {
            "mode": "report-only",
            "failureMode": "report-only",
            "enforced": False,
            "hardFail": False,
            "exitStatusAffected": False,
            "releaseBlocker": False,
            "policy": (
                "Runner advisory threshold metadata is not enforced and never "
                "changes benchmark, checker, or CI exit status."
            ),
        },
        "runner advisory threshold enforcement is explicit",
    )
    readiness = payload["thresholdBaselineReadiness"]
    expect(
        readiness == payload["metadata"]["thresholdBaselineReadiness"],
        "threshold readiness metadata mirror",
    )
    expect(readiness["mode"] == "report-only", "threshold readiness mode")
    expect(
        readiness["failureMode"] == "report-only",
        "threshold readiness failure mode",
    )
    expect(
        readiness["readyForThresholdBaseline"] is False,
        "dry-run is not threshold baseline ready",
    )
    expect(
        readiness["stableBaselineDataPresent"] is False,
        "stable baseline data absent from readiness",
    )
    expect(
        "stable-baseline-data-not-present" in readiness["reasons"],
        "readiness explains missing stable baseline data",
    )
    expect(readiness["timedCaseCount"] == 0, "readiness dry-run timed cases")
    expect(
        readiness["baselineProvenance"]["missingFields"] == ["hostLabel"],
        "dry-run readiness missing explicit host label only",
    )
    expect(
        readiness["baselineProvenance"]["toolchainsMissingVersions"] == ["cglc"],
        "dry-run readiness requires toolchain version provenance",
    )
    expect(
        readiness["baselineProvenance"]["skippedToolAccounting"][
            "skippedToolCaseCountByTool"
        ]
        == {},
        "dry-run readiness skipped-tool accounting",
    )
    runtime_environment = payload["metadata"]["runtimeEnvironment"]
    expect(
        set(REQUIRED_RUNTIME_ENVIRONMENT_FIELDS) <= set(runtime_environment),
        "runtime environment metadata fields",
    )
    expect(
        all(
            isinstance(runtime_environment[field], str) and runtime_environment[field]
            for field in REQUIRED_RUNTIME_ENVIRONMENT_FIELDS
        ),
        "runtime environment metadata values",
    )
    expect(
        runtime_environment == runner.runtime_environment_metadata(),
        "dry-run runtime environment metadata should match the producer helper",
    )
    expect(
        Path(runtime_environment["pythonExecutable"]).is_absolute(),
        "runtime environment pythonExecutable should be absolute",
    )
    expect(
        "\\" not in runtime_environment["pythonExecutable"],
        "runtime environment pythonExecutable should use POSIX separators",
    )
    expect(
        [profile["name"] for profile in payload["metadata"]["commandProfiles"]]
        == ["debug", "release"],
        "metadata command profile order",
    )
    expect(payload["summary"]["caseCount"] == 20, "case count")
    expect(
        payload["summary"]["commandProfiles"] == ["debug", "release"],
        "summary command profiles",
    )
    expect(payload["summary"]["commandProfileCount"] == 2, "command profile count")
    expect(payload["summary"]["categoryCount"] == 6, "category count")
    expect(payload["summary"]["dryRunCount"] == 20, "dry-run count")
    expect(payload["summary"]["failureCount"] == 0, "failure count")
    expect(payload["summary"]["fixtureCount"] == 11, "fixture count")
    expect(payload["summary"]["measuredRunCount"] == 0, "dry-run measured runs")
    expect(
        payload["summary"]["measurementWindow"]
        == {"sampleCount": 0, "unit": "elapsedNs", "warmupCount": 0},
        "dry-run summary measurement window",
    )
    expect(
        payload["summary"]["timingWindow"]
        == {
            "consistent": True,
            "expectedMeasuredRunCount": 0,
            "expectedSampleCount": 0,
            "expectedWarmupCount": 0,
            "expectedWarmupRunCount": 0,
            "measuredRunCount": 0,
            "mismatchedCaseCount": 0,
            "mismatchedCases": [],
            "timedCaseCount": 0,
            "warmupRunCount": 0,
        },
        "dry-run timing window accounting",
    )
    expect(
        payload["summary"]["skippedCaseCountByReason"] == {},
        "dry-run skipped reason accounting",
    )
    expect(payload["summary"]["skippedCount"] == 0, "skipped count")
    expect(
        payload["summary"]["skippedCasesWithUnavailableTools"] == [],
        "dry-run skipped case accounting",
    )
    expect(
        payload["summary"]["skippedToolCaseCountByTool"] == {},
        "dry-run skipped tool accounting",
    )
    expect(
        payload["summary"]["skippedToolCasesByTool"] == {},
        "dry-run skipped tool case lists",
    )
    expect(payload["summary"]["successCount"] == 0, "success count")
    expect(payload["summary"]["artifactAvailableCount"] == 0, "artifact count")
    expect(payload["summary"]["artifactByteSize"] == 0, "artifact bytes")
    expect(payload["summary"]["artifactFileCount"] == 0, "artifact files")
    expect(
        payload["summary"]["manifestArtifactKindCaseCount"] == 0,
        "dry-run manifest artifact kind case count",
    )
    expect(
        payload["summary"]["manifestArtifactKindCount"] == 0,
        "dry-run manifest artifact kind count",
    )
    expect(
        payload["summary"]["manifestArtifactKinds"] == {},
        "dry-run manifest artifact kind summary",
    )
    expect(payload["summary"]["timedCaseCount"] == 0, "timed count")
    expect(payload["summary"]["unavailableToolCount"] == 0, "unavailable count")
    expect(payload["summary"]["warmupRunCount"] == 0, "dry-run warmup runs")
    expect(
        payload["summary"]["verificationRequestedCount"] == 0,
        "verification requested count",
    )
    expect(
        payload["summary"]["verificationPassedCount"] == 0,
        "verification passed count",
    )
    expect(
        payload["summary"]["verificationSkippedCount"] == 0,
        "verification skipped count",
    )
    expect(
        payload["summary"]["caseCategories"]
        == [
            "atomics",
            "control-flow",
            "descriptor-arrays",
            "storage-buffers",
            "storage-images",
            "texture-sampling",
        ],
        "case categories",
    )
    expect(
        payload["metadata"]["caseCategories"] == payload["summary"]["caseCategories"],
        "metadata case categories mirror summary",
    )
    expect(
        payload["summary"]["fixtureCountByCategory"]
        == {
            "atomics": 2,
            "control-flow": 2,
            "descriptor-arrays": 2,
            "storage-buffers": 2,
            "storage-images": 2,
            "texture-sampling": 1,
        },
        "fixture category count",
    )
    expect(
        payload["summary"]["caseCountByTarget"] == {"directx": 20},
        "target case count",
    )
    expect(
        payload["summary"]["caseCountByCategoryTarget"]
        == {
            "atomics": {"directx": 4},
            "control-flow": {"directx": 4},
            "descriptor-arrays": {"directx": 4},
            "storage-buffers": {"directx": 2},
            "storage-images": {"directx": 4},
            "texture-sampling": {"directx": 2},
        },
        "category-target case matrix",
    )
    stale_category_target = copy.deepcopy(payload)
    stale_category_target["summary"]["caseCountByCategoryTarget"] = {
        "storage-buffers": {"directx": 1}
    }
    expect_contract_error(
        stale_category_target,
        "stale category-target matrix",
        "$.summary.caseCountByCategoryTarget",
    )
    expect(
        payload["summary"]["caseCountByProfile"] == {"debug": 10, "release": 10},
        "profile case count",
    )
    expect(
        payload["summary"]["caseCountByOptLevel"] == {"Debug": 10, "Release": 10},
        "opt-level case count",
    )
    expect(
        payload["summary"]["caseCountByPassTraceStatus"] == {"not-run": 20},
        "dry-run pass trace status count",
    )
    expect(
        payload["summary"]["passTraceProvenance"]
        == {
            "availableCount": 0,
            "caseCount": 20,
            "caseCountByPassScheduleFingerprint": {},
            "caseCountByStatus": {"not-run": 20},
            "manifestDeclaredCount": 0,
            "passScheduleFingerprintCount": 0,
            "passScheduleFingerprints": [],
            "parseErrorCount": 0,
            "reportPolicy": "report-only",
            "requestedCount": 0,
            "schemaVersion": 1,
            "sidecarPath": PASS_TRACE_SIDECAR_PATH,
            "unexpectedOptimizationLevelCases": [],
            "unexpectedOptimizationLevelCount": 0,
        },
        "dry-run pass trace provenance summary",
    )
    expect(
        payload["summary"]["optLevels"] == ["Debug", "Release"],
        "opt-level coverage",
    )
    expect(payload["summary"]["optLevelCount"] == 2, "opt-level count")
    expect(
        payload["summary"]["caseCountByCommandProfile"] == {"debug": 10, "release": 10},
        "command profile case count",
    )
    expect(
        payload["summary"]["caseCountByNativeOptimizationStatus"] == {},
        "dry-run native optimization status accounting",
    )
    expect(
        payload["summary"]["caseCountByNativeArtifactDescriptorOptimizationStatus"]
        == {},
        "dry-run native descriptor optimization status accounting",
    )
    expect(
        payload["summary"][
            "caseCountByNativeArtifactDescriptorOptimizationEvidenceStatus"
        ]
        == {
            "native-artifact-descriptor-not-declared": (payload["summary"]["caseCount"])
        },
        "dry-run native descriptor evidence accounting",
    )
    expect(
        payload["summary"]["caseCountByNativeOptimizationEvidenceStatus"]
        == {"native-profile-not-declared": payload["summary"]["caseCount"]},
        "dry-run native optimization evidence accounting",
    )
    expect(
        payload["summary"]["nativeOptimizationEvidence"]["knownStatusCount"] == 0,
        "dry-run native optimization known status count",
    )
    expect(
        payload["summary"]["nativeOptimizationEvidence"][
            "nativeProfileNotDeclaredCount"
        ]
        == payload["summary"]["caseCount"],
        "dry-run native optimization undeclared profile count",
    )
    expect(
        payload["summary"]["nativeOptimizationStatuses"] == [],
        "dry-run native optimization status coverage",
    )
    expect(
        payload["summary"]["caseCountByCategory"]
        == {
            "atomics": 4,
            "control-flow": 4,
            "descriptor-arrays": 4,
            "storage-buffers": 2,
            "storage-images": 4,
            "texture-sampling": 2,
        },
        "case category count",
    )

    first = payload["cases"][0]
    expect(list(first.keys()) == REQUIRED_CASE_FIELDS, "case field order")
    expect(first["compilerPath"] == "build/cglc", "case compiler path")
    expect_relative_report_path(first["compilerPath"], "case.compilerPath")
    expect_relative_report_path(first["fixturePath"], "case.fixturePath")
    expect_relative_report_path(first["outputPath"], "case.outputPath")
    expect(first["elapsedNs"] == 0, "dry-run elapsed time")
    expect(first["exitStatus"] is None, "dry-run exit status")
    expect(first["fixtureCategory"] == "storage-buffers", "fixture category")
    expect(first["optLevel"] == "Debug", "opt level")
    expect(first["success"] is None, "dry-run success")
    expect(first["status"] == "dry-run", "dry-run status")
    expect(first["skipped"] is False, "dry-run skipped")
    expect(first["skipReason"] is None, "dry-run skip reason")
    expect(first["timing"] is None, "dry-run timing")
    expect(first["unavailableTools"] == [], "dry-run unavailable tools")
    expect(first["packageMode"] == "source", "package mode")
    expect(
        first["passTraceProvenance"]
        == empty_pass_trace_provenance(
            output_path=first["outputPath"],
            profile="debug",
            target="directx",
        ),
        "dry-run pass trace provenance",
    )
    expect(first["nativeValidationRequested"] is False, "native validation")
    expect(
        first["artifactSummary"]
        == {
            "available": False,
            "byteSize": 0,
            "debugArtifactsPresent": None,
            "emittedManifestArtifactCount": 0,
            "fileCount": 0,
            "files": [],
            "manifestArtifactByteSize": 0,
            "manifestArtifactCount": 0,
            "manifestArtifacts": [],
            "manifestAvailable": False,
            "manifestPackageMode": None,
            "manifestTarget": None,
            "missingManifestArtifactCount": 0,
            "nativeArtifactDescriptor": empty_native_artifact_descriptor_summary(),
            "nativeProfile": empty_native_profile_summary(),
            "nativeBinaryStatus": None,
            "optLevel": "Debug",
            "outputKind": "missing",
            "outputPath": first["outputPath"],
            "packageFormat": None,
            "profile": "debug",
            "requestedPackageMode": "source",
            "target": "directx",
        },
        "dry-run artifact summary",
    )
    expect(
        first["verification"]
        == {
            "reason": "dry-run",
            "requested": False,
            "status": "not-run",
            "tool": "cglc",
            "toolAvailable": True,
        },
        "dry-run verification status",
    )
    expect(
        first["commandProfile"]
        == {
            "buildType": "Debug",
            "cglcArgs": [],
            "compilerConfig": "Debug",
            "environment": [],
            "name": "debug",
            "nativeValidationRequested": False,
            "packageMode": "source",
        },
        "command profile",
    )
    expect(first["command"][0] == "<cglc>", "display command")
    expect("--diagnostics-json" in first["command"], "diagnostics json command")
    expect(
        first["diagnosticSummary"]
        == {
            "schemaVersion": None,
            "total": 0,
            "bySeverity": {},
            "codes": [],
            "stdoutBytes": 0,
            "stderrBytes": 0,
            "stderrLines": 0,
            "parseError": None,
        },
        "dry-run diagnostic summary",
    )
    expect(
        payload["toolAvailability"]
        == {
            "cglc": {
                "available": None,
                "path": "build/cglc",
                "reason": None,
                "role": "required",
                "status": "not-checked",
            }
        },
        "dry-run tool availability",
    )
    expect_relative_report_path(
        payload["toolAvailability"]["cglc"]["path"],
        "toolAvailability.cglc.path",
    )

    repeat = run_tool(
        root,
        "--dry-run",
        "--cglc",
        "build/cglc",
        "--profile",
        "debug,release",
        "--target",
        "directx",
    )
    expect(repeat.returncode == 0, repeat.stderr + repeat.stdout)
    expect(repeat.stdout == result.stdout, "dry-run output should be deterministic")

    native = run_tool(
        root,
        "--dry-run",
        "--cglc",
        "build/cglc",
        "--fixture",
        "storage-buffer-compute",
        "--profile",
        "native-package",
        "--target",
        "directx",
    )
    expect(native.returncode == 0, native.stderr + native.stdout)
    native_payload = json.loads(native.stdout)
    assert_report_contract(native_payload, "native dry-run")
    native_case = native_payload["cases"][0]
    expect(
        native_case["artifactSummary"]["requestedPackageMode"] == "native",
        "native dry-run package mode",
    )
    expect(
        native_case["verification"]["requested"] is True,
        "native dry-run verification requested",
    )
    expect(
        native_payload["summary"]["verificationRequestedCount"] == 1,
        "native dry-run verification requested count",
    )


def check_cli_vulkan_o2_dry_run(root: Path) -> None:
    result = run_tool(
        root,
        "--dry-run",
        "--cglc",
        "build/cglc",
        "--fixture",
        "storage-buffer-compute",
        "--profile",
        "release-o2",
        "--target",
        "vulkan",
        "--target-profile",
        "crossgl-vulkan-o2-package",
    )
    expect(result.returncode == 0, result.stderr + result.stdout)
    payload = json.loads(result.stdout)
    assert_report_contract(payload, "vulkan O2 dry-run")
    expect(payload["summary"]["caseCount"] == 1, "vulkan O2 dry-run case count")
    expect(payload["metadata"]["optLevel"] == "O2", "vulkan O2 metadata opt level")
    expect(
        payload["metadata"]["targetProfile"] == "crossgl-vulkan-o2-package",
        "vulkan O2 target profile",
    )
    expect(
        payload["baselinePolicy"]["optLevel"] == "O2",
        "vulkan O2 baseline opt level",
    )
    expect(
        payload["summary"]["caseCountByOptLevel"] == {"O2": 1},
        "vulkan O2 opt-level count",
    )
    expect(payload["summary"]["optLevels"] == ["O2"], "vulkan O2 opt-level coverage")

    command_profile = payload["metadata"]["commandProfiles"][0]
    expect(command_profile["name"] == "release-o2", "vulkan O2 command profile name")
    expect(
        command_profile["cglcArgs"] == ["--opt-level", "O2"],
        "vulkan O2 metadata cglc args",
    )
    expect(command_profile["compilerConfig"] == "O2", "vulkan O2 compiler config")

    case = payload["cases"][0]
    expect(case["target"] == "vulkan", "vulkan O2 case target")
    expect(case["optLevel"] == "O2", "vulkan O2 case opt level")
    expect(
        case["passTraceProvenance"]
        == empty_pass_trace_provenance(
            output_path=case["outputPath"],
            profile="release-o2",
            target="vulkan",
            expected_optimization_level="O2",
        ),
        "vulkan O2 dry-run pass trace provenance",
    )
    expect(
        case["commandProfile"]["cglcArgs"] == ["--opt-level", "O2"],
        "vulkan O2 case command profile args",
    )
    expect(
        case["command"][-2:] == ["--opt-level", "O2"],
        "vulkan O2 display command args",
    )
    expect(
        case["artifactSummary"]["nativeProfile"] == empty_native_profile_summary(),
        "vulkan O2 dry-run native profile summary",
    )
    expect(
        case["artifactSummary"]["nativeArtifactDescriptor"]
        == empty_native_artifact_descriptor_summary(),
        "vulkan O2 dry-run native descriptor summary",
    )


def check_cli_skip_unavailable(root: Path) -> None:
    result = run_tool(
        root,
        "--cglc",
        "build/definitely-missing-cglc",
        "--profile",
        "release",
        "--target",
        "directx",
        "--skip-unavailable-tools",
    )
    expect(result.returncode == 0, result.stderr + result.stdout)
    payload = json.loads(result.stdout)
    assert_report_contract(payload, "skip unavailable")
    expect(payload["dryRun"] is False, "skip report should not be dry-run")
    expect(payload["summary"]["caseCount"] == 10, "skip case count")
    expect(payload["summary"]["measuredRunCount"] == 0, "skip measured runs")
    expect(payload["summary"]["skippedCount"] == 10, "skip count")
    expect(payload["summary"]["successCount"] == 0, "skip success count")
    expect(payload["summary"]["failureCount"] == 0, "skip failure count")
    expect(payload["summary"]["unavailableToolCount"] == 1, "skip tool count")
    expect(
        payload["summary"]["skippedToolCaseCountByTool"] == {"cglc": 10},
        "skip tool case accounting",
    )
    expect(
        payload["summary"]["caseCountByPassTraceStatus"] == {"skipped": 10},
        "skip pass trace status accounting",
    )
    expect(
        payload["summary"]["passTraceProvenance"]["caseCountByStatus"]
        == {"skipped": 10},
        "skip pass trace summary accounting",
    )
    expected_skipped_cases = [
        "mixed-resource-descriptor-array::directx::release",
        "nested-control-flow::directx::release",
        "storage-buffer-compute::directx::release",
        "storage-image-atomic-descriptor-array::directx::release",
        "storage-image-atomics::directx::release",
        "storage-image-descriptor-array::directx::release",
        "storage-image-explicit-format::directx::release",
        "texture-descriptor-array::directx::release",
        "texture-sampling-descriptor-array::directx::release",
        "while-control-flow::directx::release",
    ]
    expect(
        payload["summary"]["skippedCaseCountByReason"] == {"cglc-unavailable": 10},
        "skip reason accounting",
    )
    expect(
        payload["summary"]["skippedCasesWithUnavailableTools"]
        == expected_skipped_cases,
        "skipped cases with unavailable tools",
    )
    expect(
        payload["summary"]["skippedToolCasesByTool"]
        == {"cglc": expected_skipped_cases},
        "skip tool case list accounting",
    )
    stale_skipped_tool_counts = copy.deepcopy(payload)
    stale_skipped_tool_counts["summary"]["skippedToolCaseCountByTool"] = {}
    expect_contract_error(
        stale_skipped_tool_counts,
        "stale skipped tool count",
        "$.summary.skippedToolCaseCountByTool",
    )
    stale_skipped_tool_cases = copy.deepcopy(payload)
    stale_skipped_tool_cases["summary"]["skippedToolCasesByTool"] = {"cglc": []}
    expect_contract_error(
        stale_skipped_tool_cases,
        "stale skipped tool case list",
        "$.summary.skippedToolCasesByTool",
    )
    expect(
        payload["metadata"]["comparisonWindow"]
        == {"sampleCount": 0, "unit": "elapsedNs", "warmupCount": 0},
        "skip comparison window metadata",
    )
    expect(
        payload["metadata"]["timedCaseCount"] == 0,
        "skip metadata timed count",
    )
    expect(
        payload["summary"]["verificationSkippedCount"] == 10,
        "skip verification accounting",
    )
    expect(payload["summary"]["warmupRunCount"] == 0, "skip warmup runs")
    expect(payload["toolAvailability"]["cglc"]["available"] is False, "tool missing")
    expect(payload["toolAvailability"]["cglc"]["status"] == "unavailable", "status")
    expect(
        payload["toolAvailability"]["cglc"]["role"] == "required",
        "cglc availability role",
    )
    expect(
        payload["thresholdBaselineReadiness"]["requiredOrUnclassifiedSkippedCaseCount"]
        == 10,
        "readiness required skipped cases",
    )
    expect(
        payload["thresholdBaselineReadiness"]["requiredOrUnclassifiedSkippedToolLabels"]
        == ["cglc"],
        "readiness required skipped tool labels",
    )
    stale_required_coverage_observed = copy.deepcopy(payload)
    stale_required_coverage_observed["thresholdBaselineReadiness"][
        "thresholdBaselineRequirements"
    ][5]["observed"]["requiredOrUnclassifiedSkippedCaseCount"] = 0
    sync_threshold_readiness_metadata(stale_required_coverage_observed)
    expect_contract_error(
        stale_required_coverage_observed,
        "stale threshold readiness required coverage observed block",
        "$.thresholdBaselineReadiness.thresholdBaselineRequirements[5].observed",
    )
    stale_required_coverage_accounting = copy.deepcopy(payload)
    stale_required_coverage_accounting["thresholdBaselineReadiness"][
        "baselineProvenance"
    ]["skippedToolAccounting"]["requiredOrUnclassifiedSkippedCaseCount"] = 0
    sync_threshold_readiness_metadata(stale_required_coverage_accounting)
    expect_contract_error(
        stale_required_coverage_accounting,
        "stale threshold readiness skipped accounting",
        "$.thresholdBaselineReadiness.baselineProvenance.skippedToolAccounting"
        ".requiredOrUnclassifiedSkippedCaseCount",
    )
    first = payload["cases"][0]
    expect(first["status"] == "skipped", "case skipped")
    expect(first["skipped"] is True, "skipped marker")
    expect(first["skipReason"] == "cglc-unavailable", "skip reason")
    expect(first["timing"] is None, "skipped timing")
    expect(first["unavailableTools"] == ["cglc"], "unavailable tools")
    expect(first["artifactSummary"]["available"] is False, "skipped artifact")
    expect(
        first["passTraceProvenance"]
        == empty_pass_trace_provenance(
            output_path=first["outputPath"],
            profile="release",
            target="directx",
            status="skipped",
            reason="cglc-unavailable",
        ),
        "skipped pass trace provenance",
    )
    expect(
        first["verification"]["status"] == "skipped",
        "skipped verification status",
    )
    expect(
        first["verification"]["toolAvailable"] is False,
        "skipped verification tool",
    )


def check_cli_vulkan_native_profile_statuses(root: Path) -> None:
    baseline_identity_args = [
        "--host-label",
        "ci-linux-x86_64-pool-a",
        "--host-class",
        "linux-x86_64",
        "--target-profile",
        "crossgl-vulkan-native-profile",
        "--toolchain-label",
        "cglc",
        "--toolchain-version",
        "0.6.0-fixture",
    ]
    scenarios = [
        {
            "profile": "release-o2",
            "env_status": None,
            "expected_status": "applied",
            "expected_policy": "use-when-available",
            "expected_level": "-O",
            "expected_requested": "O2",
            "expected_cglc_args": ["--opt-level", "O2"],
        },
        {
            "profile": "release-o2",
            "env_status": "skipped-tool-missing",
            "expected_status": "skipped-tool-missing",
            "expected_policy": "use-when-available",
            "expected_level": "-O",
            "expected_requested": "O2",
            "expected_cglc_args": ["--opt-level", "O2"],
        },
        {
            "profile": "release",
            "env_status": None,
            "expected_status": "skipped-disabled",
            "expected_policy": "disabled-by-opt-level",
            "expected_level": "none",
            "expected_requested": "O0",
            "expected_cglc_args": [],
        },
    ]

    with tempfile.TemporaryDirectory(prefix="crossgl-perf-runner-vulkan-o2-") as tmp:
        tmp_path = Path(tmp)
        fake_cglc = write_fake_cglc(tmp_path)
        for index, scenario in enumerate(scenarios, start=1):
            env = os.environ.copy()
            if scenario["env_status"] is None:
                env.pop("CROSSGL_FAKE_SPIRV_OPT_STATUS", None)
            else:
                env["CROSSGL_FAKE_SPIRV_OPT_STATUS"] = str(scenario["env_status"])
            result = run_tool(
                root,
                "--cglc",
                str(fake_cglc),
                "--fixture",
                "storage-buffer-compute",
                "--profile",
                str(scenario["profile"]),
                "--target",
                "vulkan",
                "--repeat",
                "1",
                "--warmup",
                "0",
                *baseline_identity_args,
                "--work-dir",
                str(tmp_path / f"out-{index}"),
                env=env,
            )
            expect(result.returncode == 0, result.stderr + result.stdout)
            payload = json.loads(result.stdout)
            assert_report_contract(payload, f"vulkan native profile {index}")
            expect(
                payload["metadata"]["hostLabel"] == "ci-linux-x86_64-pool-a",
                "native optimization host label",
            )
            expect(
                payload["metadata"]["hostClass"] == "linux-x86_64",
                "native optimization host class",
            )
            expect(
                payload["metadata"]["toolchainVersion"] == "0.6.0-fixture",
                "native optimization toolchain version",
            )
            expect(payload["summary"]["caseCount"] == 1, "native profile case count")
            expect(
                payload["summary"]["caseCountByNativeOptimizationStatus"]
                == {scenario["expected_status"]: 1},
                "native optimization status count",
            )
            expect(
                payload["summary"]["caseCountByNativeOptimizationEvidenceStatus"]
                == {"known-status": 1},
                "native optimization evidence status count",
            )
            expect(
                payload["summary"][
                    "caseCountByNativeArtifactDescriptorOptimizationStatus"
                ]
                == {scenario["expected_status"]: 1},
                "native descriptor optimization status count",
            )
            expect(
                payload["summary"][
                    "caseCountByNativeArtifactDescriptorOptimizationEvidenceStatus"
                ]
                == {"known-status": 1},
                "native descriptor optimization evidence status count",
            )
            expect(
                payload["summary"]["nativeOptimizationEvidence"]["knownStatusCount"]
                == 1,
                "native optimization evidence known count",
            )
            expect(
                payload["summary"]["nativeOptimizationStatuses"]
                == [scenario["expected_status"]],
                "native optimization status coverage",
            )

            case = payload["cases"][0]
            expect(case["target"] == "vulkan", "native profile target")
            expect(
                case["commandProfile"]["cglcArgs"] == scenario["expected_cglc_args"],
                "native profile command args",
            )
            artifact = case["artifactSummary"]
            expect(artifact["available"] is True, "native profile artifact available")
            expect(
                artifact["manifestPackageMode"] == "native",
                "vulkan native package mode",
            )
            expect(
                artifact["nativeBinaryStatus"] is None,
                "vulkan native binary status absent",
            )
            descriptor = artifact["nativeArtifactDescriptor"]
            expect(
                descriptor["declared"] is True,
                "native descriptor declared",
            )
            expect(
                descriptor["available"] is True,
                "native descriptor available",
            )
            expect(
                descriptor["optimizationEvidenceStatus"] == "known-status",
                "native descriptor optimization evidence status",
            )
            descriptor_evidence = descriptor["optimizationEvidence"]
            expect(
                descriptor_evidence["status"] == scenario["expected_status"],
                "native descriptor optimization status",
            )
            expect(
                descriptor_evidence["effectiveLevel"] == scenario["expected_requested"],
                "native descriptor effective level",
            )

            native_profile = artifact["nativeProfile"]
            expect(native_profile["declared"] is True, "native profile declared")
            expect(native_profile["available"] is True, "native profile available")
            expect(
                native_profile["optimizationEvidenceStatus"] == "known-status",
                "native profile optimization evidence status",
            )
            expect(native_profile["parseError"] is None, "native profile parse")
            expect(native_profile["schemaVersion"] == 1, "native profile schema")
            expect(native_profile["target"] == "vulkan", "native profile target")
            expect(native_profile["api"] == "vulkan", "native profile api")
            expect(
                native_profile["profileName"] == "vulkan-prototype",
                "native profile name",
            )
            expect(
                native_profile["path"].endswith(".profile.json"),
                "native profile path",
            )

            optimization = native_profile["optimization"]
            expect(isinstance(optimization, dict), "native optimization object")
            expect(optimization["tool"] == "spirv-opt", "native optimization tool")
            expect(
                optimization["status"] == scenario["expected_status"],
                "native optimization status",
            )
            expect(
                optimization["policy"] == scenario["expected_policy"],
                "native optimization policy",
            )
            expect(
                optimization["level"] == scenario["expected_level"],
                "native optimization level",
            )
            expect(
                optimization["requestedLevel"] == scenario["expected_requested"],
                "native optimization requested level",
            )

            if index == 1:
                missing_optimizer_tool = copy.deepcopy(payload)
                missing_optimizer_tool["cases"][0]["artifactSummary"]["nativeProfile"][
                    "optimization"
                ]["tool"] = None
                expect_contract_error(
                    missing_optimizer_tool,
                    "native optimization missing optimizer tool",
                    "$.cases[0].artifactSummary.nativeProfile.optimization.tool: "
                    "expected non-empty string when native optimization status "
                    "evidence is present",
                )

                missing_identity = copy.deepcopy(payload)
                for field in (
                    "baselinePolicy",
                    "host",
                    "toolchain",
                    "toolchains",
                ):
                    missing_identity.pop(field, None)
                for field in REQUIRED_NATIVE_OPTIMIZATION_RUN_IDENTITY_FIELDS:
                    missing_identity["metadata"].pop(field, None)
                missing_identity["toolAvailability"]["cglc"].pop("version", None)
                expect_contract_error(
                    missing_identity,
                    "native optimization missing run identity",
                    "$.metadata.hostClass: expected non-empty string "
                    "when native optimization status evidence is present",
                )

        evidence_scenarios = [
            {
                "mode": "missing-debug-optimization",
                "expected_evidence": "missing-debug-optimization",
                "expected_parse_error": None,
                "expected_available": True,
                "expected_optimization": None,
            },
            {
                "mode": "invalid-json",
                "expected_evidence": "unparsable-native-profile",
                "expected_parse_error": "invalid-json",
                "expected_available": True,
                "expected_optimization": None,
            },
            {
                "mode": "declared-missing",
                "expected_evidence": "declared-native-profile-missing",
                "expected_parse_error": None,
                "expected_available": False,
                "expected_optimization": None,
            },
            {
                "mode": "optimization-without-status",
                "expected_evidence": "optimization-without-status",
                "expected_parse_error": None,
                "expected_available": True,
                "expected_optimization": "object",
            },
        ]
        for index, scenario in enumerate(evidence_scenarios, start=1):
            env = os.environ.copy()
            env["CROSSGL_FAKE_NATIVE_PROFILE_MODE"] = str(scenario["mode"])
            result = run_tool(
                root,
                "--cglc",
                str(fake_cglc),
                "--fixture",
                "storage-buffer-compute",
                "--profile",
                "release-o2",
                "--target",
                "vulkan",
                "--repeat",
                "1",
                "--warmup",
                "0",
                "--work-dir",
                str(tmp_path / f"evidence-out-{index}"),
                env=env,
            )
            expect(result.returncode == 0, result.stderr + result.stdout)
            payload = json.loads(result.stdout)
            assert_report_contract(payload, f"vulkan native profile evidence {index}")
            evidence_status = str(scenario["expected_evidence"])
            expect(
                payload["summary"]["caseCountByNativeOptimizationEvidenceStatus"]
                == {evidence_status: 1},
                "native optimization evidence coverage status count",
            )
            expect(
                payload["summary"]["caseCountByNativeOptimizationStatus"] == {},
                "missing native optimization statuses stay status-uncovered",
            )
            evidence = payload["summary"]["nativeOptimizationEvidence"]
            expect(evidence["caseCount"] == 1, "native evidence case count")
            expect(
                evidence["caseCountByEvidenceStatus"] == {evidence_status: 1},
                "native evidence summary status count",
            )
            native_profile = payload["cases"][0]["artifactSummary"]["nativeProfile"]
            expect(native_profile["declared"] is True, "evidence profile declared")
            expect(
                native_profile["optimizationEvidenceStatus"] == evidence_status,
                "evidence profile optimization evidence status",
            )
            expect(
                native_profile["available"] is scenario["expected_available"],
                "evidence profile availability",
            )
            expect(
                native_profile["parseError"] == scenario["expected_parse_error"],
                "evidence profile parse state",
            )
            if scenario["expected_optimization"] == "object":
                expect(
                    isinstance(native_profile["optimization"], dict),
                    "evidence optimization object",
                )
                expect(
                    native_profile["optimization"]["status"] is None,
                    "evidence optimization status absent",
                )
            else:
                expect(
                    native_profile["optimization"] is None,
                    "evidence optimization absent",
                )


def check_cli_actual_timing(root: Path) -> None:
    with tempfile.TemporaryDirectory(prefix="crossgl-perf-runner-check-") as tmp:
        fake_cglc = write_fake_cglc(Path(tmp))
        result = run_tool(
            root,
            "--cglc",
            str(fake_cglc),
            "--fixture",
            "storage-buffer-compute",
            "--profile",
            "release",
            "--target",
            "directx",
            "--repeat",
            "3",
            "--warmup",
            "2",
            "--comparison-window",
            '{"sampleCount":99,"unit":"elapsedNs","warmupCount":42}',
            "--work-dir",
            str(Path(tmp) / "out"),
        )
    expect(result.returncode == 0, result.stderr + result.stdout)
    payload = json.loads(result.stdout)
    assert_report_contract(payload, "actual timing")
    stale_timed_case_observed = copy.deepcopy(payload)
    stale_timed_case_observed["thresholdBaselineReadiness"][
        "thresholdBaselineRequirements"
    ][2]["observed"]["timedCaseCount"] = 0
    sync_threshold_readiness_metadata(stale_timed_case_observed)
    expect_contract_error(
        stale_timed_case_observed,
        "stale threshold readiness timed case observed block",
        "$.thresholdBaselineReadiness.thresholdBaselineRequirements[2].observed",
    )
    stale_repeated_evidence_observed = copy.deepcopy(payload)
    stale_repeated_evidence_observed["thresholdBaselineReadiness"][
        "thresholdBaselineRequirements"
    ][4]["observed"]["repeatedTimedCaseCount"] = 0
    sync_threshold_readiness_metadata(stale_repeated_evidence_observed)
    expect_contract_error(
        stale_repeated_evidence_observed,
        "stale threshold readiness repeated evidence observed block",
        "$.thresholdBaselineReadiness.thresholdBaselineRequirements[4].observed",
    )
    expect(payload["dryRun"] is False, "actual report should not be dry-run")
    expect(payload["summary"]["caseCount"] == 1, "actual case count")
    expect(payload["summary"]["measuredRunCount"] == 3, "actual measured runs")
    expect(payload["summary"]["timedCaseCount"] == 1, "actual timed count")
    expect(payload["summary"]["warmupRunCount"] == 2, "actual warmup runs")
    expect(
        payload["metadata"]["comparisonWindow"]
        == {"sampleCount": 99, "unit": "elapsedNs", "warmupCount": 42},
        "actual explicit comparison window metadata",
    )
    expect(
        payload["metadata"]["measurementWindow"]
        == {"sampleCount": 3, "unit": "elapsedNs", "warmupCount": 2},
        "actual measurement window metadata",
    )
    expect(
        payload["metadata"]["timedCaseCount"] == 1,
        "actual metadata timed count",
    )
    expect(payload["summary"]["successCount"] == 1, "actual success count")
    expect(payload["summary"]["artifactAvailableCount"] == 1, "artifact available")
    expect(payload["summary"]["artifactFileCount"] == 9, "artifact file count")
    expect(payload["summary"]["artifactByteSize"] > 0, "artifact bytes")
    expect(
        payload["summary"]["caseCountByPassTraceStatus"] == {"available": 1},
        "actual pass trace status count",
    )
    expect(
        payload["summary"]["passTraceProvenance"]
        == {
            "availableCount": 1,
            "caseCount": 1,
            "caseCountByPassScheduleFingerprint": {"fnv1a64:0123456789abcdef": 1},
            "caseCountByStatus": {"available": 1},
            "manifestDeclaredCount": 0,
            "passScheduleFingerprintCount": 1,
            "passScheduleFingerprints": ["fnv1a64:0123456789abcdef"],
            "parseErrorCount": 0,
            "reportPolicy": "report-only",
            "requestedCount": 0,
            "schemaVersion": 1,
            "sidecarPath": PASS_TRACE_SIDECAR_PATH,
            "unexpectedOptimizationLevelCases": [],
            "unexpectedOptimizationLevelCount": 0,
        },
        "actual pass trace provenance summary",
    )
    expect(payload["toolAvailability"]["cglc"]["available"] is True, "tool present")
    expect(payload["config"]["repeat"] == 3, "actual config repeat")
    expect(payload["config"]["warmup"] == 2, "actual config warmup")
    expect(
        payload["summary"]["measurementWindow"]
        == {"sampleCount": 3, "unit": "elapsedNs", "warmupCount": 2},
        "actual summary measurement window",
    )
    expect(
        payload["summary"]["timingWindow"]
        == {
            "consistent": True,
            "expectedMeasuredRunCount": 3,
            "expectedSampleCount": 3,
            "expectedWarmupCount": 2,
            "expectedWarmupRunCount": 2,
            "measuredRunCount": 3,
            "mismatchedCaseCount": 0,
            "mismatchedCases": [],
            "timedCaseCount": 1,
            "warmupRunCount": 2,
        },
        "actual timing window accounting",
    )
    first = payload["cases"][0]
    expect(first["status"] == "passed", "actual status")
    expect(first["success"] is True, "actual success")
    expect(first["elapsedNs"] >= 0, "actual elapsed time")
    timing = first["timing"]
    expect(isinstance(timing, dict), "actual timing object")
    expect(timing["sampleCount"] == 3, "actual timing sample count")
    expect(timing["warmupCount"] == 2, "actual timing warmup count")
    expect(len(timing["runs"]) == 3, "actual measured run records")
    expect(len(timing["warmups"]) == 2, "actual warmup run records")
    expect(
        [run["iteration"] for run in timing["runs"]] == [1, 2, 3],
        "actual measured iterations",
    )
    expect(
        [run["iteration"] for run in timing["warmups"]] == [1, 2],
        "actual warmup iterations",
    )
    durations = sorted(run["durationNs"] for run in timing["runs"])
    expect(timing["minNs"] == durations[0], "actual timing min")
    expect(timing["medianNs"] == durations[len(durations) // 2], "actual timing median")
    expect(timing["meanNs"] == sum(durations) // len(durations), "actual timing mean")
    expect(timing["maxNs"] == durations[-1], "actual timing max")
    expect(timing["elapsedNs"] == timing["medianNs"], "selected elapsed timing")
    expect(first["elapsedNs"] == timing["elapsedNs"], "actual timing elapsed mirror")
    expect(timing["exitStatuses"] == [0], "actual timing exit statuses")
    artifact = first["artifactSummary"]
    expect(artifact["available"] is True, "actual artifact available")
    expect(artifact["outputKind"] == "directory", "actual output kind")
    expect(artifact["packageFormat"] == "directory", "actual package format")
    expect(artifact["fileCount"] == 9, "actual artifact files")
    expect(artifact["manifestAvailable"] is True, "actual manifest")
    expect(artifact["manifestTarget"] == "directx", "actual manifest target")
    expect(
        artifact["manifestPackageMode"] == "source-package",
        "actual manifest package mode",
    )
    expect(artifact["manifestArtifactCount"] == 5, "manifest artifact count")
    expect(
        artifact["emittedManifestArtifactCount"] == 5,
        "emitted manifest artifact count",
    )
    expect(
        artifact["missingManifestArtifactCount"] == 0,
        "missing manifest artifact count",
    )
    expect(artifact["manifestArtifactByteSize"] > 0, "manifest artifact bytes")
    expect(artifact["nativeBinaryStatus"] == "planned", "native binary status")
    expect(
        artifact["nativeProfile"] == empty_native_profile_summary(),
        "actual native profile summary",
    )
    descriptor = artifact["nativeArtifactDescriptor"]
    expect(descriptor["declared"] is True, "actual native descriptor declared")
    expect(descriptor["available"] is True, "actual native descriptor available")
    expect(
        descriptor["optimizationEvidenceStatus"] == "known-status",
        "actual descriptor optimization evidence status",
    )
    expect(
        descriptor["optimizationLevel"] == "O1",
        "actual descriptor optimization level",
    )
    descriptor_evidence = descriptor["optimizationEvidence"]
    expect(
        descriptor_evidence["status"] == "planned",
        "actual descriptor optimization status",
    )
    expect(
        descriptor_evidence["effectiveLevel"] == "O1",
        "actual descriptor effective level",
    )
    expect(
        descriptor_evidence["toolFlag"] == "-O1",
        "actual descriptor tool flag",
    )
    expect(artifact["debugArtifactsPresent"] is True, "debug artifacts")
    expect(
        [record["kind"] for record in artifact["manifestArtifacts"]]
        == [
            "backendSource",
            "debugMetadata",
            "hirSourceMap",
            "nativeArtifactDescriptor",
            "nativeBinary",
        ],
        "manifest artifact order",
    )
    expect(
        first["passTraceProvenance"]
        == {
            "available": True,
            "captureMode": "package-sidecar",
            "completed": True,
            "expectedOptimizationLevel": "O1",
            "kind": PASS_TRACE_KIND,
            "manifestDeclared": False,
            "optimizationLevel": "O1",
            "optimizationPolicyId": "fake-hir-o1",
            "parseError": None,
            "passCount": 1,
            "passScheduleFingerprint": "fnv1a64:0123456789abcdef",
            "passScheduleFingerprintPolicy": "scheduled-pass-ids-v1",
            "passScheduleStability": "stable-opt-level-policy",
            "path": f"{first['outputPath']}/{PASS_TRACE_SIDECAR_PATH}",
            "profile": "release",
            "reason": None,
            "requested": False,
            "schemaVersion": 1,
            "scheduledPassCount": 1,
            "sidecarPath": PASS_TRACE_SIDECAR_PATH,
            "status": "available",
            "target": "directx",
        },
        "actual pass trace provenance",
    )
    expect(
        payload["summary"]["manifestArtifactKindCaseCount"] == 1,
        "actual manifest artifact kind case count",
    )
    expect(
        payload["summary"]["manifestArtifactKindCount"] == 5,
        "actual manifest artifact kind count",
    )
    manifest_artifact_kinds = payload["summary"]["manifestArtifactKinds"]
    expect(
        sorted(manifest_artifact_kinds)
        == [
            "backendSource",
            "debugMetadata",
            "hirSourceMap",
            "nativeArtifactDescriptor",
            "nativeBinary",
        ],
        "actual manifest artifact kind summary keys",
    )
    for kind, metrics in manifest_artifact_kinds.items():
        expect(metrics["caseCount"] == 1, f"{kind} case count")
        expect(metrics["count"] == 1, f"{kind} manifest record count")
        expect(metrics["emittedCaseCount"] == 1, f"{kind} emitted case count")
        expect(metrics["emittedCount"] == 1, f"{kind} emitted count")
        expect(metrics["missingCaseCount"] == 0, f"{kind} missing case count")
        expect(metrics["missingCount"] == 0, f"{kind} missing count")
        expect(metrics["byteSize"] > 0, f"{kind} byte size")
    expect(
        payload["summary"][
            "caseCountByNativeArtifactDescriptorOptimizationEvidenceStatus"
        ]
        == {"known-status": 1},
        "actual descriptor evidence status count",
    )
    expect(
        payload["summary"]["caseCountByNativeArtifactDescriptorOptimizationStatus"]
        == {"planned": 1},
        "actual descriptor optimization status count",
    )
    expect(
        payload["summary"]["nativeArtifactDescriptorOptimizationStatuses"]
        == ["planned"],
        "actual descriptor optimization statuses",
    )
    expect(
        first["verification"]
        == {
            "reason": "profile-does-not-request-native-validation",
            "requested": False,
            "status": "not-requested",
            "tool": "cglc",
            "toolAvailable": True,
        },
        "actual verification status",
    )


def check_cli_baseline_policy_metadata(root: Path) -> None:
    result = run_tool(
        root,
        "--dry-run",
        "--cglc",
        "build/cglc",
        "--fixture",
        "storage-buffer-compute",
        "--profile",
        "release-o2",
        "--target",
        "vulkan",
        "--host-label",
        "ci-linux-x86_64-pool-a",
        "--host-class",
        "linux-x86_64",
        "--target-profile",
        "crossgl-vulkan-o2-package",
        "--comparison-window",
        '{"sampleCount":5,"unit":"elapsedNs","warmupCount":1}',
        "--toolchain-label",
        "cglc",
        "--toolchain-version",
        "0.6.0-fixture",
    )
    expect(result.returncode == 0, result.stderr + result.stdout)
    payload = json.loads(result.stdout)
    assert_report_contract(payload, "baseline policy dry-run")
    expected_window = {"sampleCount": 5, "unit": "elapsedNs", "warmupCount": 1}
    expect(
        payload["baselinePolicy"]
        == {
            "comparisonWindow": expected_window,
            "hostClass": "linux-x86_64",
            "hostLabel": "ci-linux-x86_64-pool-a",
            "optLevel": "O2",
            "targetProfile": "crossgl-vulkan-o2-package",
            "toolchainLabel": "cglc",
            "toolchainVersion": "0.6.0-fixture",
        },
        "baseline policy fields",
    )
    expect(payload["metadata"]["hostLabel"] == "ci-linux-x86_64-pool-a", "host label")
    expect(payload["metadata"]["hostClass"] == "linux-x86_64", "host class")
    expect(payload["metadata"]["toolchainLabel"] == "cglc", "toolchain label")
    expect(
        payload["metadata"]["toolchainVersion"] == "0.6.0-fixture",
        "toolchain version",
    )
    expect(
        payload["metadata"]["comparisonWindow"] == expected_window,
        "comparison window mirror",
    )
    expect(
        payload["metadata"]["measurementWindow"]
        == {"sampleCount": 0, "unit": "elapsedNs", "warmupCount": 0},
        "measurement window remains dry-run",
    )
    expect(
        payload["host"]
        == {
            "class": "linux-x86_64",
            "label": "ci-linux-x86_64-pool-a",
        },
        "host mirror",
    )
    expect(
        payload["toolAvailability"]["cglc"]["version"] == "0.6.0-fixture",
        "tool availability version",
    )
    expect(
        payload["toolchains"]
        == {
            "cglc": {
                "available": None,
                "role": "required",
                "status": "not-checked",
                "version": "0.6.0-fixture",
            }
        },
        "toolchains metadata",
    )
    expect(
        payload["toolchain"]
        == {
            "label": "cglc",
            "status": "not-checked",
            "version": "0.6.0-fixture",
        },
        "toolchain mirror",
    )


def expect_contract_error(
    payload: dict[str, Any],
    label: str,
    expected_error: str,
) -> None:
    errors = report_contract_errors(payload)
    if not errors:
        raise AssertionError(f"{label}: expected report contract error")
    joined = "\n".join(errors)
    if expected_error not in joined:
        raise AssertionError(
            f"{label}: expected {expected_error!r} in errors, got {errors!r}"
        )


def sync_threshold_readiness_metadata(payload: dict[str, Any]) -> None:
    payload["metadata"]["thresholdBaselineReadiness"] = copy.deepcopy(
        payload["thresholdBaselineReadiness"]
    )


def check_report_contract_failure_diagnostics(root: Path) -> None:
    result = run_tool(
        root,
        "--dry-run",
        "--cglc",
        "build/cglc",
        "--fixture",
        "storage-buffer-compute",
        "--profile",
        "release-o2",
        "--target",
        "vulkan",
        "--target-profile",
        "crossgl-vulkan-o2-package",
    )
    expect(result.returncode == 0, result.stderr + result.stdout)
    payload = json.loads(result.stdout)
    assert_report_contract(payload, "contract diagnostic seed")

    missing_opt_level = copy.deepcopy(payload)
    del missing_opt_level["metadata"]["optLevel"]
    expect_contract_error(
        missing_opt_level,
        "missing metadata opt level",
        "$.metadata.optLevel: required field is missing",
    )

    hard_timing_policy = copy.deepcopy(payload)
    hard_timing_policy["metadata"]["reportPolicy"]["timing"] = "hard-fail"
    expect_contract_error(
        hard_timing_policy,
        "hard timing policy",
        "$.metadata.reportPolicy.timing: expected 'report-only'",
    )

    hard_threshold_policy = copy.deepcopy(payload)
    hard_threshold_policy["advisoryThresholdPolicy"]["mode"] = "hard-fail"
    hard_threshold_policy["metadata"]["advisoryThresholdPolicy"]["mode"] = "hard-fail"
    expect_contract_error(
        hard_threshold_policy,
        "hard advisory threshold policy",
        "$.advisoryThresholdPolicy.mode: expected 'report-only'",
    )

    enforced_threshold_policy = copy.deepcopy(payload)
    enforced_threshold_policy["advisoryThresholdPolicy"]["enforcement"]["enforced"] = (
        True
    )
    enforced_threshold_policy["metadata"]["advisoryThresholdPolicy"]["enforcement"][
        "enforced"
    ] = True
    expect_contract_error(
        enforced_threshold_policy,
        "enforced advisory threshold policy",
        "$.advisoryThresholdPolicy.enforcement.enforced: expected False",
    )

    claimed_stable_baseline = copy.deepcopy(payload)
    claimed_stable_baseline["thresholdBaselineReadiness"][
        "stableBaselineDataPresent"
    ] = True
    claimed_stable_baseline["metadata"]["thresholdBaselineReadiness"][
        "stableBaselineDataPresent"
    ] = True
    expect_contract_error(
        claimed_stable_baseline,
        "claimed stable baseline data",
        "$.thresholdBaselineReadiness.stableBaselineDataPresent: expected False",
    )

    stale_requirement_name = copy.deepcopy(payload)
    stale_requirement_name["thresholdBaselineReadiness"][
        "thresholdBaselineRequirements"
    ][1]["name"] = "baselineMetadata"
    sync_threshold_readiness_metadata(stale_requirement_name)
    expect_contract_error(
        stale_requirement_name,
        "stale threshold readiness requirement name",
        "$.thresholdBaselineReadiness.thresholdBaselineRequirements[1].name",
    )

    stale_requirement_reason = copy.deepcopy(payload)
    stale_requirement_reason["thresholdBaselineReadiness"][
        "thresholdBaselineRequirements"
    ][2]["reasonIfUnsatisfied"] = "no-measurements"
    sync_threshold_readiness_metadata(stale_requirement_reason)
    expect_contract_error(
        stale_requirement_reason,
        "stale threshold readiness requirement reason",
        "$.thresholdBaselineReadiness.thresholdBaselineRequirements[2]"
        ".reasonIfUnsatisfied",
    )

    stale_readiness_reasons = copy.deepcopy(payload)
    stale_readiness_reasons["thresholdBaselineReadiness"]["reasons"] = [
        "stable-baseline-data-not-present"
    ]
    sync_threshold_readiness_metadata(stale_readiness_reasons)
    expect_contract_error(
        stale_readiness_reasons,
        "stale threshold readiness reasons",
        "$.thresholdBaselineReadiness.reasons",
    )

    stale_unsatisfied_requirements = copy.deepcopy(payload)
    stale_unsatisfied_requirements["thresholdBaselineReadiness"][
        "unsatisfiedThresholdBaselineRequirements"
    ] = []
    sync_threshold_readiness_metadata(stale_unsatisfied_requirements)
    expect_contract_error(
        stale_unsatisfied_requirements,
        "stale threshold readiness unsatisfied mirror",
        "$.thresholdBaselineReadiness.unsatisfiedThresholdBaselineRequirements",
    )

    stale_satisfied_requirement_count = copy.deepcopy(payload)
    stale_satisfied_requirement_count["thresholdBaselineReadiness"][
        "satisfiedThresholdBaselineRequirementCount"
    ] = 99
    sync_threshold_readiness_metadata(stale_satisfied_requirement_count)
    expect_contract_error(
        stale_satisfied_requirement_count,
        "stale threshold readiness satisfied count",
        "$.thresholdBaselineReadiness.satisfiedThresholdBaselineRequirementCount",
    )

    stale_baseline_observed = copy.deepcopy(payload)
    stale_baseline_observed["thresholdBaselineReadiness"][
        "thresholdBaselineRequirements"
    ][1]["observed"]["missingFields"] = []
    sync_threshold_readiness_metadata(stale_baseline_observed)
    expect_contract_error(
        stale_baseline_observed,
        "stale threshold readiness baseline observed block",
        "$.thresholdBaselineReadiness.thresholdBaselineRequirements[1].observed",
    )

    mismatched_case_opt_level = copy.deepcopy(payload)
    mismatched_case_opt_level["cases"][0]["optLevel"] = "Release"
    expect_contract_error(
        mismatched_case_opt_level,
        "mismatched case opt level",
        "$.cases[0].optLevel: expected 'O2'",
    )

    mismatched_artifact_target = copy.deepcopy(payload)
    mismatched_artifact_target["cases"][0]["artifactSummary"]["target"] = "directx"
    expect_contract_error(
        mismatched_artifact_target,
        "mismatched artifact target",
        "$.cases[0].artifactSummary.target: expected 'vulkan'",
    )

    mismatched_command_profile_count = copy.deepcopy(payload)
    mismatched_command_profile_count["summary"]["caseCountByCommandProfile"] = {}
    expect_contract_error(
        mismatched_command_profile_count,
        "mismatched command profile count",
        "$.summary.caseCountByCommandProfile",
    )

    missing_pass_trace_metadata = copy.deepcopy(payload)
    del missing_pass_trace_metadata["metadata"]["passTraceProvenance"]
    expect_contract_error(
        missing_pass_trace_metadata,
        "missing pass trace metadata",
        "$.metadata.passTraceProvenance: required field is missing",
    )

    mismatched_pass_trace_level = copy.deepcopy(payload)
    mismatched_pass_trace_level["cases"][0]["passTraceProvenance"][
        "expectedOptimizationLevel"
    ] = "O1"
    expect_contract_error(
        mismatched_pass_trace_level,
        "mismatched pass trace expected level",
        "$.cases[0].passTraceProvenance.expectedOptimizationLevel: expected 'O2'",
    )

    manifest_declared_pass_trace = copy.deepcopy(payload)
    manifest_declared_pass_trace["cases"][0]["passTraceProvenance"][
        "manifestDeclared"
    ] = True
    expect_contract_error(
        manifest_declared_pass_trace,
        "manifest declared pass trace",
        "$.cases[0].passTraceProvenance.manifestDeclared: pass trace must remain "
        "a non-manifest sidecar",
    )

    mismatched_pass_trace_summary = copy.deepcopy(payload)
    mismatched_pass_trace_summary["summary"]["caseCountByPassTraceStatus"] = {}
    expect_contract_error(
        mismatched_pass_trace_summary,
        "mismatched pass trace status count",
        "$.summary.caseCountByPassTraceStatus",
    )

    missing_config_fixture = copy.deepcopy(payload)
    missing_config_fixture["config"]["fixtures"] = []
    expect_contract_error(
        missing_config_fixture,
        "missing configured fixture",
        "$.config.fixtures: emitted case fixture(s) missing",
    )

    mismatched_config_profile = copy.deepcopy(payload)
    mismatched_config_profile["config"]["profiles"] = ["release"]
    expect_contract_error(
        mismatched_config_profile,
        "mismatched configured profile",
        "$.config.profiles",
    )

    mismatched_config_target = copy.deepcopy(payload)
    mismatched_config_target["config"]["targets"] = ["directx"]
    expect_contract_error(
        mismatched_config_target,
        "mismatched configured target",
        "$.config.targets: emitted case target(s) missing",
    )

    mismatched_fixture_count = copy.deepcopy(payload)
    mismatched_fixture_count["summary"]["fixtureCount"] = 99
    expect_contract_error(
        mismatched_fixture_count,
        "mismatched fixture count",
        "$.summary.fixtureCount",
    )

    mismatched_fixture_category_count = copy.deepcopy(payload)
    mismatched_fixture_category_count["summary"]["fixtureCountByCategory"] = {
        "storage-buffers": 2
    }
    expect_contract_error(
        mismatched_fixture_category_count,
        "mismatched fixture category count",
        "$.summary.fixtureCountByCategory",
    )

    mismatched_artifact_kind_count = copy.deepcopy(payload)
    mismatched_artifact_kind_count["summary"]["manifestArtifactKindCount"] = 99
    expect_contract_error(
        mismatched_artifact_kind_count,
        "mismatched manifest artifact kind count",
        "$.summary.manifestArtifactKindCount",
    )

    mismatched_native_evidence_status = copy.deepcopy(payload)
    mismatched_native_evidence_status["cases"][0]["artifactSummary"]["nativeProfile"][
        "optimizationEvidenceStatus"
    ] = "missing-debug-optimization"
    expect_contract_error(
        mismatched_native_evidence_status,
        "mismatched native evidence status",
        "$.cases[0].artifactSummary.nativeProfile.optimizationEvidenceStatus",
    )

    mismatched_metadata_opt_level = copy.deepcopy(payload)
    mismatched_metadata_opt_level.pop("baselinePolicy", None)
    mismatched_metadata_opt_level["metadata"]["optLevel"] = "Release"
    expect_contract_error(
        mismatched_metadata_opt_level,
        "mismatched metadata opt level",
        "$.metadata.optLevel: expected 'O2'",
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--root",
        default=Path(__file__).resolve().parents[1],
        type=Path,
        help="CrossGL-Compiler repository root",
    )
    parser.add_argument(
        "--self-test",
        action="store_true",
        help="Run the local runner contract self-test suite.",
    )
    args = parser.parse_args()

    root = args.root.resolve()
    check_corpus_document(root)
    check_cli_list(root)
    check_cli_dry_run(root)
    check_cli_vulkan_o2_dry_run(root)
    check_cli_skip_unavailable(root)
    check_fake_cglc_path_selection()
    check_cli_vulkan_native_profile_statuses(root)
    check_cli_actual_timing(root)
    check_cli_baseline_policy_metadata(root)
    check_report_contract_failure_diagnostics(root)
    print("validated performance corpus runner")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
