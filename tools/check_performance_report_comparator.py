#!/usr/bin/env python3
"""Self-test the performance report comparator with synthetic reports."""

from __future__ import annotations

import argparse
import copy
import importlib.util
import json
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any


def expect(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


FIXTURE_DIR = Path(__file__).resolve().parents[1] / "tests" / "performance"
ADVISORY_BASELINE = FIXTURE_DIR / "report-comparator-advisory-baseline.json"
ADVISORY_CANDIDATE = FIXTURE_DIR / "report-comparator-advisory-candidate.json"
ADVISORY_WINDOW_BASELINE = (
    FIXTURE_DIR / "report-comparator-advisory-window-baseline.json"
)
ADVISORY_WINDOW_CANDIDATE = (
    FIXTURE_DIR / "report-comparator-advisory-window-candidate.json"
)
STRUCTURAL_LOSS_CANDIDATE = (
    FIXTURE_DIR / "report-comparator-structural-loss-candidate.json"
)
SKIP_TOOLCHAIN_CANDIDATE = (
    FIXTURE_DIR / "report-comparator-skip-toolchain-candidate.json"
)
OPTIONAL_TOOL_SKIP_CANDIDATE = (
    FIXTURE_DIR / "report-comparator-optional-tool-skip-candidate.json"
)
TOOLCHAIN_METADATA_BASELINE = (
    FIXTURE_DIR / "report-comparator-toolchain-metadata-baseline.json"
)
TOOLCHAIN_METADATA_CONFLICT_CANDIDATE = (
    FIXTURE_DIR / "report-comparator-toolchain-metadata-conflict-candidate.json"
)
INCOMPLETE_THRESHOLD_BASELINE = (
    FIXTURE_DIR / "report-comparator-incomplete-threshold-baseline.json"
)
INCOMPLETE_THRESHOLD_CANDIDATE = (
    FIXTURE_DIR / "report-comparator-incomplete-threshold-candidate.json"
)
GENERATED_ADVISORY_THRESHOLD_POLICY = (
    FIXTURE_DIR / "report-comparator-generated-advisory-threshold-policy.json"
)
CUSTOM_ADVISORY_THRESHOLD_POLICY = (
    FIXTURE_DIR / "report-comparator-custom-advisory-threshold-policy.json"
)
MALFORMED_ADVISORY_THRESHOLD_POLICIES = (
    (
        FIXTURE_DIR
        / "report-comparator-malformed-advisory-threshold-policy-hard-fail.json",
        "mode must be 'report-only'",
    ),
    (
        FIXTURE_DIR
        / "report-comparator-malformed-advisory-threshold-policy-missing-enforcement.json",
        "enforcement is required",
    ),
    (
        FIXTURE_DIR
        / "report-comparator-malformed-advisory-threshold-policy-missing-evidence-policy.json",
        "evidencePolicy is required",
    ),
    (
        FIXTURE_DIR
        / "report-comparator-malformed-advisory-threshold-policy-release-blocker.json",
        "releaseBlockerPolicy must match the comparator report-only release blocker policy",
    ),
    (
        FIXTURE_DIR
        / "report-comparator-malformed-advisory-threshold-policy-duplicate.json",
        "duplicate category/profile rule",
    ),
)
STRUCTURAL_AND_TIMING_CANDIDATE = (
    FIXTURE_DIR / "report-comparator-structural-and-timing-candidate.json"
)
FUNCTIONAL_FAILURE_CANDIDATE = (
    FIXTURE_DIR / "report-comparator-functional-failure-candidate.json"
)
INCOMPLETE_THRESHOLD_MISSING_CONTEXT_FIELDS = [
    "hostLabel",
    "hostClass",
    "targetProfile",
    "optLevel",
    "comparisonWindow",
    "runtimeEnvironment",
    "toolchains",
]
REQUIRED_ADVISORY_CONTEXT_FIELDS = INCOMPLETE_THRESHOLD_MISSING_CONTEXT_FIELDS
FIXTURE_RUNTIME_ENVIRONMENT = {
    "machine": "x86_64",
    "platform": "Linux-fixture",
    "pythonExecutable": "/usr/bin/python3",
    "pythonImplementation": "CPython",
    "pythonVersion": "3.11.0",
    "system": "Linux",
    "systemRelease": "fixture",
}


def report(cases: list[dict[str, Any]]) -> dict[str, Any]:
    command_profile_counts: dict[str, int] = {}
    category_counts: dict[str, int] = {}
    category_target_counts: dict[str, dict[str, int]] = {}
    opt_level_counts: dict[str, int] = {}
    profile_counts: dict[str, int] = {}
    target_counts: dict[str, int] = {}
    skipped_reason_counts: dict[str, int] = {}
    skipped_tool_counts: dict[str, int] = {}
    skipped_tool_cases: dict[str, list[str]] = {}
    skipped_cases_with_tools: set[str] = set()
    unavailable_tools: set[str] = set()
    for case in cases:
        command_profile = case.get("commandProfile")
        if isinstance(command_profile, dict):
            name = command_profile.get("name")
            if isinstance(name, str) and name:
                command_profile_counts[name] = command_profile_counts.get(name, 0) + 1
        case_key = case.get("case")
        skipped = case.get("skipped") is True or case.get("status") == "skipped"
        case_tools = [
            tool
            for tool in case.get("unavailableTools", [])
            if isinstance(tool, str) and tool
        ]
        unavailable_tools.update(case_tools)
        if skipped:
            reason = case.get("skipReason")
            if not isinstance(reason, str) or not reason:
                reason = "unspecified"
            skipped_reason_counts[reason] = skipped_reason_counts.get(reason, 0) + 1
            if isinstance(case_key, str) and case_key and case_tools:
                skipped_cases_with_tools.add(case_key)
            for tool in case_tools:
                skipped_tool_counts[tool] = skipped_tool_counts.get(tool, 0) + 1
                if isinstance(case_key, str) and case_key:
                    skipped_tool_cases.setdefault(tool, []).append(case_key)
        for field, counts in (
            ("fixtureCategory", category_counts),
            ("optLevel", opt_level_counts),
            ("profile", profile_counts),
            ("target", target_counts),
        ):
            value = case.get(field)
            if isinstance(value, str) and value:
                counts[value] = counts.get(value, 0) + 1
        category = case.get("fixtureCategory")
        target = case.get("target")
        if (
            isinstance(category, str)
            and category
            and isinstance(target, str)
            and target
        ):
            category_targets = category_target_counts.setdefault(category, {})
            category_targets[target] = category_targets.get(target, 0) + 1
    return {
        "schemaVersion": 1,
        "tool": "benchmark_performance_corpus",
        "corpusVersion": "milestone6-smoke-v1",
        "cases": cases,
        "summary": {
            "caseCount": len(cases),
            "caseCategories": sorted(category_counts),
            "caseCountByCategory": dict(sorted(category_counts.items())),
            "caseCountByCategoryTarget": {
                category: dict(sorted(target_counts.items()))
                for category, target_counts in sorted(category_target_counts.items())
            },
            "caseCountByCommandProfile": dict(sorted(command_profile_counts.items())),
            "caseCountByOptLevel": dict(sorted(opt_level_counts.items())),
            "caseCountByProfile": dict(sorted(profile_counts.items())),
            "caseCountByTarget": dict(sorted(target_counts.items())),
            "commandProfiles": sorted(command_profile_counts),
            "optLevels": sorted(opt_level_counts),
            "skippedCount": sum(1 for case in cases if case.get("skipped") is True),
            "skippedCaseCountByReason": dict(sorted(skipped_reason_counts.items())),
            "skippedCasesWithUnavailableTools": sorted(skipped_cases_with_tools),
            "skippedToolCaseCountByTool": dict(sorted(skipped_tool_counts.items())),
            "skippedToolCasesByTool": {
                tool: sorted(case_keys)
                for tool, case_keys in sorted(skipped_tool_cases.items())
            },
            "timedCaseCount": sum(
                1
                for case in cases
                if isinstance(case.get("timing"), dict)
                and isinstance(case["timing"].get("elapsedNs"), int)
            ),
            "unavailableToolCount": len(unavailable_tools),
        },
    }


def write_report(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


def run_tool(
    root: Path,
    baseline: Path,
    candidate: Path,
    *args: str,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            sys.executable,
            str(root / "tools" / "compare_performance_reports.py"),
            str(baseline),
            str(candidate),
            *args,
        ],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )


def run_comparator(root: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            sys.executable,
            str(root / "tools" / "compare_performance_reports.py"),
            *args,
        ],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )


def run_aggregate(root: Path, *reports: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            sys.executable,
            str(root / "tools" / "compare_performance_reports.py"),
            "--aggregate",
            *(str(report) for report in reports),
        ],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )


def run_corpus_runner(root: Path, *args: str) -> subprocess.CompletedProcess[str]:
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
    )


def load_comparator(root: Path):
    tool_path = root / "tools" / "compare_performance_reports.py"
    spec = importlib.util.spec_from_file_location(
        "compare_performance_reports", tool_path
    )
    if spec is None or spec.loader is None:
        raise RuntimeError(f"could not import {tool_path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


_MISSING = object()


def value_at_dotted_path(payload: dict[str, Any], path: str) -> Any:
    value: Any = payload
    for key in path.split("."):
        if not isinstance(value, dict) or key not in value:
            return _MISSING
        value = value[key]
    return value


def check_threshold_enforcement(enforcement: dict[str, Any], label: str) -> None:
    expect(enforcement["mode"] == "report-only", f"{label}: mode")
    expect(enforcement["failureMode"] == "report-only", f"{label}: failure mode")
    expect(enforcement["enforced"] is False, f"{label}: not enforced")
    expect(enforcement["hardFail"] is False, f"{label}: no hard failure")
    expect(
        enforcement["exitStatusAffected"] is False,
        f"{label}: no exit status effect",
    )
    expect(enforcement["releaseBlocker"] is False, f"{label}: no release blocker")
    expect("not enforced" in enforcement["policy"], f"{label}: policy text")


def check_report_artifact_contract(payload: dict[str, Any], label: str) -> None:
    artifacts = payload["reportArtifacts"]
    comparison = artifacts["comparisonReport"]
    required_top_level = comparison["requiredTopLevelFields"]
    expect(
        isinstance(required_top_level, list)
        and all(isinstance(field, str) and field for field in required_top_level),
        f"{label}: comparison report required fields are named",
    )
    expect(
        set(required_top_level) <= set(payload),
        f"{label}: comparison report required fields are present",
    )
    expect(
        comparison["statusPolicy"]
        == "Only structural report-shape failures change comparator exit status in v0.",
        f"{label}: comparison report status policy",
    )
    expect(
        comparison["failureSurfaces"]["hardFail"] == ["structure"],
        f"{label}: structural hard-fail surface is explicit",
    )
    expect(
        set(comparison["failureSurfaces"]["reportOnly"])
        == {
            "timing",
            "artifactSize",
            "nativeOptimization",
            "metadata.baselinePolicy",
        },
        f"{label}: report-only surfaces are explicit",
    )

    for artifact_name, expected_mode in (
        ("structure", payload["policy"]["structural"]["mode"]),
        ("timingAdvisory", payload["policy"]["timing"]["mode"]),
        ("artifactSizeAdvisory", payload["policy"]["artifactSize"]["mode"]),
        (
            "nativeOptimizationAdvisory",
            payload["policy"]["nativeOptimization"]["mode"],
        ),
        ("baselinePolicyAdvisory", "report-only"),
    ):
        contract = artifacts[artifact_name]
        contract_path = contract["path"]
        artifact_payload = value_at_dotted_path(payload, contract_path)
        expect(
            artifact_payload is not _MISSING,
            f"{label}: {artifact_name} path exists",
        )
        expect(
            contract["failureMode"] == expected_mode,
            f"{label}: {artifact_name} failure mode matches policy",
        )
        for field in contract.get("requiredFields", []):
            expect(
                isinstance(artifact_payload, dict) and field in artifact_payload,
                f"{label}: {artifact_name} required field {field}",
            )
        delta_path = contract.get("deltaPath")
        if delta_path is not None:
            delta_payload = value_at_dotted_path(payload, delta_path)
            expect(
                isinstance(delta_payload, list),
                f"{label}: {artifact_name} delta path is a list",
            )

    expect(
        artifacts["timingAdvisory"]["defaultDeltaReport"]
        == payload["timing"]["deltaReport"],
        f"{label}: timing default delta report matches output",
    )
    expect(
        artifacts["timingAdvisory"]["explicitThresholdPolicy"]
        == payload["timing"]["explicitThresholdPolicy"]["mode"],
        f"{label}: timing explicit threshold policy stays report-only",
    )
    check_threshold_enforcement(
        payload["policy"]["timing"]["thresholdEnforcement"],
        f"{label}: policy timing threshold enforcement",
    )
    check_threshold_enforcement(
        payload["timing"]["thresholdEnforcement"],
        f"{label}: timing threshold enforcement",
    )
    check_threshold_enforcement(
        payload["timing"]["advisoryThresholds"]["enforcement"],
        f"{label}: advisory thresholds enforcement",
    )
    check_threshold_enforcement(
        payload["timing"]["explicitThresholdPolicy"]["enforcement"],
        f"{label}: explicit threshold enforcement",
    )
    expect(
        artifacts["timingAdvisory"]["evidencePath"] == "timing.advisoryEvidencePolicy",
        f"{label}: timing evidence policy path is advertised",
    )
    expect(
        artifacts["timingAdvisory"]["sufficiencyPath"] == "timing.evidenceSufficiency",
        f"{label}: timing evidence sufficiency path is advertised",
    )
    expect(
        isinstance(value_at_dotted_path(payload, "timing.evidenceSufficiency"), dict),
        f"{label}: timing evidence sufficiency artifact exists",
    )
    expect(
        artifacts["timingAdvisory"]["thresholdPolicyPath"]
        == "timing.advisoryThresholdPolicy",
        f"{label}: timing threshold policy path is advertised",
    )
    expect(
        artifacts["timingAdvisory"]["advisoryThresholdsPath"]
        == "timing.advisoryThresholds",
        f"{label}: timing advisory threshold summary path is advertised",
    )
    expect(
        artifacts["timingAdvisory"]["thresholdProposalLayerPath"]
        == "timing.thresholdProposalLayer",
        f"{label}: timing threshold proposal layer path is advertised",
    )
    expect(
        artifacts["timingAdvisory"]["warningSummaryPath"] == "timing.warningSummary",
        f"{label}: timing warning summary path is advertised",
    )
    expect(
        isinstance(
            value_at_dotted_path(payload, "timing.thresholdProposalLayer"), dict
        ),
        f"{label}: timing threshold proposal layer artifact exists",
    )
    expect(
        isinstance(value_at_dotted_path(payload, "timing.warningSummary"), dict),
        f"{label}: timing warning summary artifact exists",
    )
    expect(
        "not release blockers without explicit owner approval"
        in artifacts["timingAdvisory"]["releaseBlockerPolicy"],
        f"{label}: timing advisory release-blocker policy",
    )
    expect(
        artifacts["artifactSizeAdvisory"]["defaultDeltaReport"]
        == payload["artifactSize"]["deltaReport"],
        f"{label}: artifact-size default delta report matches output",
    )
    expect(
        artifacts["artifactSizeAdvisory"]["explicitHardPolicy"]
        == "not-supported-v0-report-only",
        f"{label}: artifact-size hard policy stays unavailable",
    )
    expect(
        artifacts["artifactSizeAdvisory"]["warningSummaryPath"]
        == "artifactSize.warningSummary",
        f"{label}: artifact-size warning summary path is advertised",
    )
    expect(
        isinstance(value_at_dotted_path(payload, "artifactSize.warningSummary"), dict),
        f"{label}: artifact-size warning summary artifact exists",
    )
    expect(
        artifacts["nativeOptimizationAdvisory"]["deltaPath"]
        == "nativeOptimization.statusDrifts",
        f"{label}: native optimization drift path is advertised",
    )


def requirements_by_name(readiness: dict[str, Any]) -> dict[str, dict[str, Any]]:
    requirements = readiness["thresholdBaselineRequirements"]
    return {requirement["name"]: requirement for requirement in requirements}


def proposal_requirements_by_name(
    readiness: dict[str, Any],
) -> dict[str, dict[str, Any]]:
    requirements = readiness["requirements"]
    return {requirement["name"]: requirement for requirement in requirements}


def check_runner_baseline_policy_metadata(root: Path, tmp: Path) -> None:
    result = run_corpus_runner(
        root,
        "--dry-run",
        "--cglc",
        "build/cglc",
        "--fixture",
        "storage-buffer-compute",
        "--profile",
        "release",
        "--target",
        "directx",
        "--host-label",
        "ci-linux-x86_64-pool-a",
        "--host-class",
        "linux-x86_64",
        "--target-profile",
        "crossgl-milestone6-smoke",
        "--comparison-window",
        '{"sampleCount":0,"warmupCount":0,"unit":"elapsedNs"}',
        "--toolchain-label",
        "cglc",
        "--toolchain-version",
        "0.6.0-fixture",
    )
    expect(result.returncode == 0, result.stderr + result.stdout)
    payload = json.loads(result.stdout)
    expect(
        payload["baselinePolicy"]
        == {
            "comparisonWindow": {
                "sampleCount": 0,
                "unit": "elapsedNs",
                "warmupCount": 0,
            },
            "hostClass": "linux-x86_64",
            "hostLabel": "ci-linux-x86_64-pool-a",
            "optLevel": "Release",
            "targetProfile": "crossgl-milestone6-smoke",
            "toolchainLabel": "cglc",
            "toolchainVersion": "0.6.0-fixture",
        },
        "runner emits baseline policy metadata",
    )
    expect(
        payload["metadata"]["hostLabel"] == "ci-linux-x86_64-pool-a",
        "runner mirrors host label into metadata",
    )
    expect(
        payload["metadata"]["hostClass"] == "linux-x86_64",
        "runner mirrors host class into metadata",
    )
    expect(
        payload["metadata"]["toolchainLabel"] == "cglc",
        "runner mirrors toolchain label into metadata",
    )
    expect(
        payload["metadata"]["toolchainVersion"] == "0.6.0-fixture",
        "runner mirrors toolchain version into metadata",
    )
    expect(
        payload["metadata"]["reportPolicy"]["timing"] == "report-only",
        "runner report policy keeps timing advisory",
    )
    expect(
        payload["host"]
        == {
            "class": "linux-x86_64",
            "label": "ci-linux-x86_64-pool-a",
        },
        "runner emits top-level host metadata",
    )
    expect(
        payload["toolchain"]
        == {
            "label": "cglc",
            "status": "not-checked",
            "version": "0.6.0-fixture",
        },
        "runner emits top-level toolchain metadata",
    )
    expect(
        payload["toolchains"]["cglc"]["version"] == "0.6.0-fixture",
        "runner emits toolchain version metadata",
    )
    expect(
        payload["toolchains"]["cglc"]["role"] == "required",
        "runner emits toolchain role metadata",
    )
    expect(
        payload["toolAvailability"]["cglc"]["version"] == "0.6.0-fixture",
        "runner mirrors cglc version in tool availability",
    )

    baseline = tmp / "runner-policy-baseline.json"
    candidate = tmp / "runner-policy-candidate.json"
    write_report(baseline, payload)
    write_report(candidate, payload)
    comparison = run_tool(root, baseline, candidate)
    expect(comparison.returncode == 0, comparison.stderr + comparison.stdout)
    comparison_payload = json.loads(comparison.stdout)
    expect(comparison_payload["status"] == "pass", "runner policy comparison")
    context = comparison_payload["timing"]["advisoryContext"]["baseline"]
    expect(context["missingFields"] == [], "runner policy context is complete")
    expect(
        context["fields"]["runtimeEnvironment"]["pythonImplementation"],
        "runner policy context carries runtime environment provenance",
    )
    expect(
        context["toolchains"]["cglc"]["version"] == "0.6.0-fixture",
        "comparator reads runner toolchain version metadata",
    )


def check_advisory_default(root: Path) -> None:
    result = run_tool(root, ADVISORY_BASELINE, ADVISORY_CANDIDATE)
    expect(result.returncode == 0, result.stderr + result.stdout)
    payload = json.loads(result.stdout)
    expect(payload["status"] == "pass", "advisory comparison should pass")
    check_report_artifact_contract(payload, "default advisory comparison")
    report_artifacts = payload["reportArtifacts"]
    expect(
        report_artifacts["comparisonReport"]["format"] == "json",
        "comparison report artifact format",
    )
    expect(
        report_artifacts["comparisonReport"]["schemaVersion"] == 1,
        "comparison report artifact schema version",
    )
    expect(
        set(report_artifacts["comparisonReport"]["requiredTopLevelFields"])
        <= set(payload),
        "comparison report required top-level fields are present",
    )
    expect(
        report_artifacts["structure"]["failureMode"] == "hard-fail",
        "structure report artifact remains a hard failure surface",
    )
    expect(
        report_artifacts["timingAdvisory"]["path"] == "timing",
        "timing advisory report artifact path",
    )
    expect(
        report_artifacts["timingAdvisory"]["failureMode"] == "report-only",
        "timing advisory report artifact stays report-only",
    )
    expect(
        report_artifacts["timingAdvisory"]["defaultDeltaReport"]
        == payload["timing"]["deltaReport"],
        "timing advisory default delta report is explicit",
    )
    expect(
        report_artifacts["artifactSizeAdvisory"]["path"] == "artifactSize",
        "artifact-size advisory report artifact path",
    )
    expect(
        report_artifacts["artifactSizeAdvisory"]["failureMode"] == "report-only",
        "artifact-size advisory report artifact stays report-only",
    )
    expect(
        report_artifacts["artifactSizeAdvisory"]["defaultDeltaReport"]
        == payload["artifactSize"]["deltaReport"],
        "artifact-size default delta report is explicit",
    )
    expect(
        report_artifacts["baselinePolicyAdvisory"]["path"] == "metadata.baselinePolicy",
        "baseline policy advisory report artifact path",
    )
    expect(
        report_artifacts["baselinePolicyAdvisory"]["failureMode"] == "report-only",
        "baseline policy advisory report artifact stays report-only",
    )
    expect(payload["policy"]["failureClass"] == "pass", "passing failure class")
    expect(payload["policy"]["failurePriority"] == [], "passing failure priority")
    expect(
        payload["policy"]["structural"]["mode"] == "hard-fail",
        "structural policy",
    )
    expect(payload["policy"]["structural"]["failed"] is False, "structural pass")
    expect(payload["policy"]["timing"]["mode"] == "report-only", "timing policy mode")
    expect(
        payload["policy"]["failureSurfaces"]["hardFail"] == ["structure"],
        "policy separates structural hard-fail surface",
    )
    expect(
        set(payload["policy"]["failureSurfaces"]["reportOnly"])
        == {
            "timing",
            "artifactSize",
            "nativeOptimization",
            "metadata.baselinePolicy",
        },
        "policy separates report-only advisory surfaces",
    )
    expect(
        payload["policy"]["timing"]["requiresExplicitHardThreshold"] is False,
        "timing hard threshold is unavailable in v0",
    )
    expect(
        "not release blockers without explicit owner approval"
        in payload["policy"]["timing"]["releaseBlockerPolicy"],
        "timing advisory release-blocker policy",
    )
    expect(
        payload["policy"]["timing"]["hardThresholdAvailable"] is False,
        "timing hard threshold availability",
    )
    policy_thresholds = payload["policy"]["timing"]["advisoryThresholds"]
    expect(
        policy_thresholds["mode"] == "report-only",
        "policy timing advisory thresholds stay report-only",
    )
    expect(
        policy_thresholds["failureMode"] == "report-only",
        "policy timing advisory thresholds failure mode",
    )
    check_threshold_enforcement(
        policy_thresholds["enforcement"],
        "policy timing advisory thresholds enforcement",
    )
    expect(
        policy_thresholds["profile"] == "milestone6",
        "policy timing advisory threshold profile",
    )
    expect(
        policy_thresholds["requiredMetadataFields"] == REQUIRED_ADVISORY_CONTEXT_FIELDS,
        "policy timing advisory thresholds list required metadata",
    )
    expect(
        policy_thresholds["baselineMissingFields"] == [],
        "policy timing advisory thresholds baseline fields are complete",
    )
    expect(
        policy_thresholds["candidateMissingFields"] == [],
        "policy timing advisory thresholds candidate fields are complete",
    )
    expect(
        policy_thresholds["metadataCompatible"] is False,
        "policy timing advisory thresholds record metadata drift",
    )
    expect(
        policy_thresholds["metadataMismatchCount"] == 2,
        "policy timing advisory thresholds count metadata drift",
    )
    expect(
        policy_thresholds["measuredThresholdExceededCount"] == 1,
        "policy timing advisory thresholds keep measured excess visible",
    )
    expect(
        policy_thresholds["ruleSpecificityCounts"] == {"category-profile": 3},
        "policy timing advisory thresholds classify exact rule matches",
    )
    expect(
        policy_thresholds["thresholdExceededCount"] == 0,
        "policy timing advisory thresholds withhold claims under metadata drift",
    )
    expect(
        policy_thresholds["source"]["kind"] == "builtin",
        "policy timing advisory threshold source",
    )
    proposal_layer = payload["timing"]["thresholdProposalLayer"]
    expect(
        proposal_layer["mode"] == "report-only",
        "threshold proposal layer remains report-only",
    )
    expect(
        proposal_layer["failureMode"] == "report-only",
        "threshold proposal layer failure mode",
    )
    expect(
        proposal_layer["releaseClaimRepeatedReportPairMinimum"] == 3,
        "threshold proposal layer documents repeated report minimum",
    )
    expect(
        "three repeated report pairs" in proposal_layer["releaseClaimPolicy"],
        "threshold proposal layer documents release claim policy",
    )
    expect(
        proposal_layer["structural"]["failed"] is False,
        "threshold proposal layer separates clean structural status",
    )
    expect(
        proposal_layer["timingObservationCaseCount"] == 3,
        "threshold proposal layer counts timing observations",
    )
    trend_readiness = proposal_layer["repeatedReportTrendReadiness"]
    expect(
        trend_readiness["mode"] == "report-only",
        "threshold proposal trend readiness remains report-only",
    )
    expect(
        trend_readiness["readyForRepeatedReportTrend"] is False,
        "metadata drift blocks repeated-report trend readiness",
    )
    expect(
        trend_readiness["repeatedReportPairContribution"] == 0,
        "incomplete proposal evidence does not count as a repeated report pair",
    )
    expect(
        trend_readiness["remainingRepeatedReportPairsForReleaseClaim"] == 3,
        "incomplete proposal evidence still needs the full repeated-report minimum",
    )
    expect(
        trend_readiness["reasons"]
        == [
            "metadataIncompatible",
            "claimIneligibleTimingEvidence",
            "unstableReportOnlyClassification",
        ],
        "threshold proposal trend readiness explains blockers",
    )
    trend_requirements = proposal_requirements_by_name(trend_readiness)
    expect(
        trend_requirements["compatibleMetadata"]["satisfied"] is False,
        "threshold proposal trend readiness records metadata incompatibility",
    )
    expect(
        trend_requirements["claimEligibleTimingEvidence"]["observed"][
            "claimEligibleCaseCount"
        ]
        == 0,
        "threshold proposal trend readiness records claim eligibility count",
    )
    expect(
        trend_requirements["stableReportOnlyClassification"]["observed"][
            "unstableDispositions"
        ]
        == ["advisory-incomparable-metadata"],
        "threshold proposal trend readiness records unstable advisory disposition",
    )
    expect(
        proposal_layer["groupCount"] == 3,
        "threshold proposal layer groups by case category/target/profile",
    )
    expect(
        proposal_layer["dimensions"]["baseline"]["hostLabel"]
        == "ci-linux-x86_64-pool-a",
        "threshold proposal layer carries baseline host label",
    )
    expect(
        proposal_layer["dimensions"]["candidate"]["hostLabel"]
        == "ci-linux-x86_64-pool-b",
        "threshold proposal layer carries candidate host label",
    )
    expect(
        proposal_layer["dimensions"]["baseline"]["toolchains"]
        == ["cglc@0.6.0-fixture/crossgl-cglc-fixture"],
        "threshold proposal layer carries baseline toolchain profile",
    )
    expect(
        proposal_layer["dimensions"]["baseline"]["toolchainLabels"] == ["cglc"],
        "threshold proposal layer carries raw baseline toolchain labels",
    )
    expect(
        proposal_layer["dimensions"]["baseline"]["toolchainClasses"]
        == {"cglc": "crossgl-cglc-fixture"},
        "threshold proposal layer carries baseline toolchain class",
    )
    expect(
        proposal_layer["dimensions"]["baseline"]["skippedToolAccounting"][
            "skippedCaseCount"
        ]
        == 0,
        "threshold proposal layer carries baseline skipped-tool accounting",
    )
    expect(
        proposal_layer["dimensions"]["baseline"]["comparisonWindow"]["sampleCount"]
        == 5,
        "threshold proposal layer carries baseline comparison window",
    )
    expect(
        proposal_layer["dimensions"]["candidate"]["comparisonWindow"]["sampleCount"]
        == 7,
        "threshold proposal layer carries candidate comparison window",
    )
    expect(
        proposal_layer["dimensions"]["baseline"]["optLevel"] == "O2",
        "threshold proposal layer carries baseline opt level",
    )
    proposal_groups = {
        (group["caseCategory"], group["target"], group["profile"]): group
        for group in proposal_layer["groups"]
    }
    storage_group = proposal_groups[("storage-buffers", "directx", "release")]
    expect(
        storage_group["baselineHostClass"] == "linux-x86_64",
        "threshold proposal group carries host class",
    )
    expect(
        storage_group["baselineTargetProfile"] == "crossgl-milestone6-smoke",
        "threshold proposal group carries target profile",
    )
    expect(
        storage_group["baselineToolchainClasses"] == {"cglc": "crossgl-cglc-fixture"},
        "threshold proposal group carries toolchain class",
    )
    expect(
        storage_group["baselineToolchainLabels"] == ["cglc"],
        "threshold proposal group carries raw toolchain labels",
    )
    expect(
        storage_group["baselineSkippedToolAccounting"]["skippedToolCasesByTool"] == {},
        "threshold proposal group carries baseline skipped-tool accounting",
    )
    expect(
        storage_group["baselineComparisonWindow"]["sampleCount"] == 5,
        "threshold proposal group carries baseline comparison window",
    )
    expect(
        storage_group["candidateComparisonWindow"]["sampleCount"] == 7,
        "threshold proposal group carries candidate comparison window",
    )
    expect(
        storage_group["baselineOptLevel"] == "O2"
        and storage_group["candidateOptLevel"] == "O2",
        "threshold proposal group carries opt-level context",
    )
    expect(
        storage_group["timingObservationCaseCount"] == 1,
        "threshold proposal group counts observations",
    )
    expect(
        storage_group["currentPolicyDispositionCounts"]
        == {"advisory-incomparable-metadata": 1},
        "threshold proposal group classifies timing disposition",
    )
    expect(
        storage_group["advisoryThresholdRuleSpecificityCounts"]
        == {"category-profile": 1},
        "threshold proposal group classifies advisory rule specificity",
    )
    expect(
        storage_group["advisoryThresholdMeasuredExceededCases"]
        == ["storage-buffer-compute::directx::release"],
        "threshold proposal group separates measured threshold excess",
    )
    expect(
        storage_group["advisoryThresholdClaimedExceededCases"] == [],
        "threshold proposal group withholds claimed threshold excess",
    )
    control_group = proposal_groups[("control-flow", "directx", "release")]
    expect(
        control_group["currentPolicyDispositionCounts"] == {"non-regression": 1},
        "threshold proposal group records non-regression observation",
    )
    proposal_observations = {
        observation["case"]: observation
        for observation in proposal_layer["timingObservations"]
    }
    expect(
        proposal_observations["storage-buffer-compute::directx::release"][
            "caseCategory"
        ]
        == "storage-buffers",
        "threshold proposal observation carries case category",
    )
    expect(
        proposal_observations["storage-buffer-compute::directx::release"][
            "matchedAdvisoryThresholdRule"
        ]
        is True,
        "threshold proposal observation records advisory rule match",
    )
    expect(
        proposal_observations["storage-buffer-compute::directx::release"][
            "advisoryThresholdRuleSpecificity"
        ]
        == "category-profile",
        "threshold proposal observation records advisory rule specificity",
    )
    expect(payload["policy"]["artifactSize"]["mode"] == "report-only", "size policy")
    expect(
        payload["policy"]["nativeOptimization"]["mode"] == "report-only",
        "native optimization policy",
    )
    expect(
        payload["policy"]["nativeOptimization"]["statusDriftCount"] == 2,
        "native optimization policy drift count",
    )
    expect(
        payload["timing"]["policy"] == "advisory-no-threshold",
        "default policy",
    )
    expect(
        payload["timing"]["explicitHardPolicy"]["enabled"] is False,
        "hard policy is disabled by default",
    )
    expect(payload["timing"]["advisoryRegressionCount"] == 2, "advisory count")
    expect(payload["timing"]["failedRegressionCount"] == 0, "failed count")
    expect(
        payload["timing"]["advisoryThresholdProfile"]["name"] == "milestone6",
        "default advisory threshold profile",
    )
    expect(
        payload["timing"]["advisoryThresholdProfile"]["mode"] == "report-only",
        "advisory threshold profile mode",
    )
    check_threshold_enforcement(
        payload["timing"]["advisoryThresholdProfile"]["enforcement"],
        "advisory threshold profile enforcement",
    )
    expect(
        "never changes comparator exit status"
        in payload["timing"]["advisoryThresholdProfile"]["failurePolicy"],
        "advisory threshold profile failure policy",
    )
    expect(
        payload["timing"]["advisoryThresholdProfile"]["matchedCaseCount"] == 3,
        "advisory threshold profile match count",
    )
    expect(
        payload["timing"]["advisoryThresholdProfile"]["claimEligibleCaseCount"] == 0,
        "metadata drift prevents advisory threshold claim eligibility",
    )
    expect(
        payload["timing"]["advisoryThresholdProfile"]["insufficientEvidenceCaseCount"]
        == 3,
        "metadata drift counts matched cases as insufficient advisory evidence",
    )
    expect(
        payload["timing"]["advisoryClaimEligibleCaseCount"] == 0,
        "metadata drift prevents timing advisory claim eligibility",
    )
    expect(
        payload["timing"]["insufficientAdvisoryEvidenceCaseCount"] == 3,
        "metadata drift keeps timing evidence report-only",
    )
    expect(
        payload["timing"]["advisoryEvidencePolicy"]["minimumSampleCount"] == 2,
        "timing advisory evidence minimum sample count",
    )
    expect(
        payload["timing"]["advisoryEvidencePolicy"]["requiresComparableMetadata"]
        is True,
        "timing advisory evidence requires comparable metadata",
    )
    evidence_sufficiency = payload["timing"]["evidenceSufficiency"]
    expect(
        evidence_sufficiency["mode"] == "report-only",
        "timing evidence sufficiency remains report-only",
    )
    expect(
        evidence_sufficiency["minimumSampleCount"] == 2,
        "timing evidence sufficiency records minimum samples",
    )
    expect(
        evidence_sufficiency["metadataCompatible"] is False,
        "timing evidence sufficiency records metadata incompatibility",
    )
    expect(
        evidence_sufficiency["claimEligibilityDispositionCounts"]
        == {"incomparable-metadata": 3},
        "timing evidence sufficiency counts metadata-ineligible claims",
    )
    expect(
        evidence_sufficiency["currentPolicyDispositionCounts"]
        == {"advisory-incomparable-metadata": 2, "non-regression": 1},
        "timing evidence sufficiency explains advisory dispositions",
    )
    expect(
        evidence_sufficiency["advisoryThresholdMeasuredExceededCases"]
        == ["storage-buffer-compute::directx::release"],
        "timing evidence separates measured advisory threshold excess",
    )
    expect(
        evidence_sufficiency["advisoryThresholdClaimedExceededCases"] == [],
        "metadata drift withholds advisory threshold claim list",
    )
    expect(
        payload["timing"]["advisoryThresholdPolicy"]["metadataCompatible"] is False,
        "default fixture metadata drift is recorded",
    )
    check_threshold_enforcement(
        payload["timing"]["advisoryThresholdPolicy"]["enforcement"],
        "advisory threshold policy enforcement",
    )
    expect(
        payload["timing"]["advisoryThresholdPolicy"]["claimDispositionCounts"]
        == {"incomparable-metadata": 3},
        "advisory threshold policy counts claim dispositions",
    )
    expect(
        payload["timing"]["advisoryThresholdPolicy"]["measuredThresholdExceededCases"]
        == ["storage-buffer-compute::directx::release"],
        "advisory threshold policy separates measured excess cases",
    )
    expect(
        payload["timing"]["advisoryThresholdPolicy"]["metadataComparability"]["reasons"]
        == ["pair:metadataDrift"],
        "metadata drift reason is explicit",
    )
    expect(
        payload["timing"]["advisoryThresholdExceededCount"] == 0,
        "metadata drift suppresses proposed threshold-exceeded claims",
    )
    proposed_observation = {
        entry["case"]: entry for entry in payload["timing"]["advisoryRegressions"]
    }["storage-buffer-compute::directx::release"]
    expect(
        proposed_observation["currentPolicyDisposition"]
        == "advisory-incomparable-metadata",
        "metadata drift keeps timing observation advisory",
    )
    expect(
        proposed_observation["wouldFailAdvisoryProfileIfEnforced"] is False,
        "metadata drift prevents proposed threshold hard-policy projection",
    )
    expect(
        proposed_observation["advisoryThreshold"]["claimEligible"] is False,
        "metadata drift withholds proposed threshold claim",
    )
    check_threshold_enforcement(
        proposed_observation["advisoryThreshold"]["enforcement"],
        "per-case advisory threshold enforcement",
    )
    expect(
        proposed_observation["advisoryThreshold"]["claimDisposition"]
        == "incomparable-metadata",
        "proposed threshold disposition explains metadata drift",
    )
    expect(
        proposed_observation["measuredExceedsAdvisoryThreshold"] is True,
        "measured threshold excess remains visible",
    )
    expect(
        proposed_observation["timingEvidence"]["baseline"]["sampleCount"] == 5,
        "proposed threshold carries baseline sample count",
    )
    expect(
        proposed_observation["timingEvidence"]["candidate"]["sampleCount"] == 7,
        "proposed threshold carries candidate sample count",
    )
    expect(
        proposed_observation["timingEvidence"]["metadata"]["reasons"]
        == ["pair:metadataDrift"],
        "timing evidence carries metadata drift reason",
    )
    expect(
        proposed_observation["timingEvidence"]["claimEligibilityDisposition"]
        == "incomparable-metadata",
        "timing evidence carries claim eligibility disposition",
    )
    expect(
        proposed_observation["timingEvidence"]["claimSuppressionReasons"]
        == ["pair:metadataDrift"],
        "timing evidence carries claim suppression reasons",
    )
    expect(
        proposed_observation["advisoryThreshold"]["evidence"][
            "sufficientRepeatedEvidence"
        ]
        is True,
        "advisory threshold embeds repeated evidence sufficiency",
    )
    expect(
        proposed_observation["advisoryThreshold"]["evidence"]["baselineSampleCount"]
        == 5,
        "advisory threshold embeds baseline sample count",
    )
    expect(
        proposed_observation["advisoryThreshold"]["evidence"]["candidateSampleCount"]
        == 7,
        "advisory threshold embeds candidate sample count",
    )
    expect(
        proposed_observation["advisoryThreshold"]["evidence"]["metadataCompatible"]
        is False,
        "advisory threshold embeds metadata comparability",
    )
    expect(
        proposed_observation["advisoryThreshold"]["thresholdDeltaNs"] == 3,
        "advisory threshold reports threshold delta",
    )
    expect(
        proposed_observation["advisoryThreshold"]["thresholdExcessNs"] == 3,
        "advisory threshold reports threshold excess",
    )
    expect(
        proposed_observation["advisoryThreshold"]["thresholdHeadroomNs"] == 0,
        "advisory threshold reports threshold headroom",
    )
    expect(
        "not release blockers"
        in proposed_observation["advisoryThreshold"]["reportOnlyReason"],
        "advisory threshold explains report-only disposition",
    )
    expect(
        proposed_observation["wouldFailExplicitThresholdIfEnforced"] is False,
        "no explicit threshold failure by default",
    )
    expect(
        proposed_observation["advisoryThreshold"]["ruleCategory"] == "storage-buffers",
        "proposed threshold category",
    )
    expect(
        proposed_observation["advisoryThreshold"]["ruleProfile"] == "release",
        "proposed threshold profile",
    )
    expect(
        proposed_observation["advisoryThreshold"]["ruleSpecificity"]
        == "category-profile",
        "proposed threshold rule specificity",
    )
    expect(
        proposed_observation["advisoryThreshold"]["ruleMatch"]
        == {
            "caseCategory": "storage-buffers",
            "caseProfile": "release",
            "caseTarget": "directx",
            "categoryMatch": "exact",
            "profileMatch": "exact",
            "ruleCategory": "storage-buffers",
            "ruleProfile": "release",
            "ruleSpecificity": "category-profile",
        },
        "proposed threshold rule match evidence",
    )
    expect(
        proposed_observation["caseContext"]["baseline"]["profile"] == "release",
        "timing advisory includes case profile context",
    )
    expect(
        proposed_observation["caseContext"]["baseline"]["fixtureCategory"]
        == "storage-buffers",
        "timing advisory includes case category context",
    )
    expect(payload["timing"]["comparableCaseCount"] == 3, "timed comparable count")
    expect(payload["timing"]["timingDeltaCount"] == 0, "default delta count")
    expect(
        payload["timing"]["deltaReport"] == "regressions-only",
        "default delta report",
    )
    expect(payload["timing"]["untimedCaseCount"] == 1, "untimed count")
    timing_warnings = payload["timing"]["warningSummary"]
    expect(
        timing_warnings["mode"] == "report-only"
        and timing_warnings["failureMode"] == "report-only",
        "timing warning summary is report-only",
    )
    expect(
        timing_warnings["warningTypes"]
        == [
            "timing-regression",
            "advisory-threshold-measured-exceeded",
            "insufficient-advisory-evidence",
            "untimed-cases",
        ],
        "timing warning summary classifies advisory delta warnings",
    )
    expect(
        timing_warnings["timingRegressionCases"]
        == [
            "storage-buffer-compute::directx::release",
            "texture-descriptor-array::opengl::release",
        ],
        "timing warning summary lists slower cases",
    )
    expect(
        timing_warnings["advisoryThresholdMeasuredExceededCases"]
        == ["storage-buffer-compute::directx::release"],
        "timing warning summary separates measured threshold excess",
    )
    expect(
        timing_warnings["advisoryThresholdClaimedExceededCases"] == [],
        "timing warning summary withholds ineligible threshold claims",
    )
    expect(
        timing_warnings["warningCaseCount"] == 4,
        "timing warning summary counts unique warning cases",
    )
    expect(
        payload["timing"]["failedRegressionCount"] == 0,
        "timing warnings do not fail the comparison",
    )
    native_optimization = payload["nativeOptimization"]
    expect(
        native_optimization["mode"] == "report-only",
        "native optimization advisory mode",
    )
    expect(
        native_optimization["status"] == "drift-detected",
        "native optimization drift status",
    )
    expect(
        native_optimization["statusDriftCount"] == 2,
        "native optimization drift count",
    )
    expect(
        native_optimization["statusTransitionCounts"]
        == {
            "applied -> skipped-tool-missing": 1,
            "skipped-disabled -> applied": 1,
        },
        "native optimization transition counts",
    )
    expect(
        [entry["transition"] for entry in native_optimization["statusDrifts"]]
        == [
            "skipped-disabled -> applied",
            "applied -> skipped-tool-missing",
        ],
        "native optimization status drift transitions",
    )
    expect(
        native_optimization["statusDrifts"][1]["case"]
        == "storage-buffer-compute::directx::release",
        "native optimization applied-to-skipped case",
    )
    expect(
        native_optimization["caseCountByStatusDeltas"]
        == [
            {
                "baselineCount": 1,
                "candidateCount": 0,
                "delta": -1,
                "status": "skipped-disabled",
            },
            {
                "baselineCount": 0,
                "candidateCount": 1,
                "delta": 1,
                "status": "skipped-tool-missing",
            },
        ],
        "native optimization count deltas",
    )
    expect(
        native_optimization["summaryCountByStatusDeltas"]
        == native_optimization["caseCountByStatusDeltas"],
        "native optimization summary count deltas",
    )
    expect(
        native_optimization["baseline"]["caseCountByStatus"]
        == {"applied": 1, "skipped-disabled": 1},
        "baseline native optimization status counts",
    )
    expect(
        native_optimization["baseline"]["summaryCountsMatchCases"] is True,
        "baseline native optimization summary counts match cases",
    )
    expect(
        native_optimization["candidate"]["caseCountByStatus"]
        == {"applied": 1, "skipped-tool-missing": 1},
        "candidate native optimization status counts",
    )
    expect(
        "never change comparator exit status" in native_optimization["policy"].lower(),
        "native optimization advisory policy text",
    )
    expect(payload["structure"]["missingCaseCount"] == 0, "missing cases")
    expect(payload["structure"]["failed"] is False, "structure artifact pass flag")
    expect(
        payload["structure"]["failureMode"] == "hard-fail",
        "structure artifact failure mode",
    )
    expect(
        payload["structure"]["failureReasons"] == [],
        "structure artifact failure reasons",
    )
    expect(
        payload["structure"]["missingCategoryCount"] == 0,
        "missing category count",
    )
    expect(payload["structure"]["missingProfiles"] == [], "missing profiles")
    expect(payload["structure"]["missingTargets"] == [], "missing targets")
    expect(payload["structure"]["newSkippedCaseCount"] == 0, "new skipped cases")
    expect(
        payload["structure"]["newUnavailableToolchainLabels"] == [],
        "new unavailable toolchains",
    )
    expect(
        payload["structure"]["missingCommandProfiles"] == [],
        "missing command profiles",
    )
    expect(
        payload["structure"]["changedCommandProfileCount"] == 0,
        "changed command profiles",
    )
    expect(
        payload["structure"]["candidateFunctionalFailureCaseCount"] == 0,
        "candidate functional failures",
    )
    expect(
        payload["structure"]["newRequiredUnavailableToolchainLabels"] == [],
        "new required unavailable toolchains",
    )
    expect(
        payload["structure"]["newOptionalUnavailableToolchainLabels"] == [],
        "new optional unavailable toolchains",
    )
    expect(
        payload["structure"]["candidateToolchainClassifications"]["cglc"][
            "availability"
        ]
        == "available",
        "candidate toolchain availability classification",
    )
    expect(payload["structure"]["validationIssueCount"] == 0, "valid fixtures")
    baseline_policy = payload["metadata"]["baselinePolicy"]
    expect(
        baseline_policy["baseline"]["hostClass"] == "linux-x86_64",
        "baseline host class",
    )
    expect(
        baseline_policy["candidate"]["toolchains"]["cglc"]["version"]
        == "0.6.0-fixture",
        "candidate toolchain version",
    )
    expect(
        baseline_policy["compatibility"]["compatible"] is False,
        "advisory metadata incompatibility is surfaced",
    )
    expect(
        baseline_policy["compatibility"]["mismatchCount"] == 2,
        "metadata mismatch count",
    )
    expect(
        [
            mismatch["field"]
            for mismatch in baseline_policy["compatibility"]["mismatches"]
        ]
        == ["comparisonWindow", "hostLabel"],
        "metadata mismatch fields",
    )
    comparison_dimensions = baseline_policy["comparisonDimensions"]
    expect(
        comparison_dimensions["advisory"] is True,
        "comparison dimensions are advisory",
    )
    expect(
        "without creating timing failure gates" in comparison_dimensions["policy"],
        "comparison dimensions policy remains report-only",
    )
    expect(
        comparison_dimensions["compatibility"]["mismatchCount"] == 2,
        "comparison dimensions reuse compatibility summary",
    )
    expect(
        comparison_dimensions["baseline"]["hostLabel"] == "ci-linux-x86_64-pool-a",
        "comparison dimensions carry baseline host label",
    )
    expect(
        comparison_dimensions["baseline"]["fields"]["runtimeEnvironment"]
        == FIXTURE_RUNTIME_ENVIRONMENT,
        "comparison dimensions carry runtime environment provenance",
    )
    expect(
        comparison_dimensions["candidate"]["hostLabel"] == "ci-linux-x86_64-pool-b",
        "comparison dimensions carry candidate host label",
    )
    expect(
        comparison_dimensions["baseline"]["comparisonWindow"]["sampleCount"] == 5,
        "comparison dimensions carry baseline comparison window",
    )
    expect(
        comparison_dimensions["candidate"]["comparisonWindow"]["sampleCount"] == 7,
        "comparison dimensions carry candidate comparison window",
    )
    expect(
        comparison_dimensions["baseline"]["caseCategories"]
        == ["control-flow", "descriptor-arrays", "storage-buffers"],
        "comparison dimensions carry case categories",
    )
    expect(
        comparison_dimensions["baseline"]["commandProfiles"] == ["debug", "release"],
        "comparison dimensions carry command profiles",
    )
    expect(
        comparison_dimensions["baseline"]["optLevel"] == "O2",
        "comparison dimensions carry opt level",
    )
    expect(
        comparison_dimensions["candidate"]["toolchains"]["cglc"]["version"]
        == "0.6.0-fixture",
        "comparison dimensions carry toolchain version",
    )
    expect(
        comparison_dimensions["candidate"]["toolchainLabels"] == ["cglc"],
        "comparison dimensions carry raw toolchain labels",
    )
    expect(
        comparison_dimensions["candidate"]["toolchainClasses"]
        == {"cglc": "crossgl-cglc-fixture"},
        "comparison dimensions carry toolchain class",
    )
    expect(
        comparison_dimensions["baseline"]["skippedToolAccounting"][
            "skippedToolCasesByTool"
        ]
        == {},
        "comparison dimensions carry skipped-tool accounting",
    )
    readiness = baseline_policy["readiness"]
    expect(
        readiness["baseline"]["readyForThresholdBaseline"] is True,
        "complete baseline report is threshold-baseline ready",
    )
    baseline_requirements = readiness["baseline"]["thresholdBaselineRequirements"]
    expect(
        readiness["baseline"]["thresholdBaselineRequirementCount"] == 8,
        "ready baseline threshold requirement count",
    )
    expect(
        readiness["baseline"]["satisfiedThresholdBaselineRequirementCount"] == 8,
        "ready baseline satisfied requirement count",
    )
    expect(
        readiness["baseline"]["unsatisfiedThresholdBaselineRequirements"] == [],
        "ready baseline has no unsatisfied threshold requirements",
    )
    expect(
        [requirement["name"] for requirement in baseline_requirements]
        == [
            "recognizedContextFields",
            "timedCases",
            "explicitTimedCaseIdentity",
            "repeatedTimingEvidence",
            "cleanReportShape",
            "functionalSuccess",
            "requiredToolCoverage",
            "skippedToolEvidence",
        ],
        "threshold readiness requirement order",
    )
    expect(
        all(requirement["satisfied"] is True for requirement in baseline_requirements),
        "ready baseline satisfies every threshold requirement",
    )
    baseline_requirement_map = requirements_by_name(readiness["baseline"])
    expect(
        baseline_requirement_map["recognizedContextFields"]["observed"]["missingFields"]
        == [],
        "ready baseline has complete context requirement evidence",
    )
    expect(
        baseline_requirement_map["recognizedContextFields"]["observed"][
            "requiredFields"
        ]
        == REQUIRED_ADVISORY_CONTEXT_FIELDS,
        "ready baseline records required context fields",
    )
    expect(
        baseline_requirement_map["timedCases"]["observed"]["timedCaseCount"] == 3,
        "ready baseline carries timed-case requirement evidence",
    )
    expect(
        baseline_requirement_map["explicitTimedCaseIdentity"]["observed"][
            "incompleteCaseCount"
        ]
        == 0,
        "ready baseline carries explicit timed-case identity evidence",
    )
    expect(
        baseline_requirement_map["repeatedTimingEvidence"]["observed"][
            "repeatedTimedCaseCount"
        ]
        == 3,
        "ready baseline carries repeated timing evidence",
    )
    expect(
        readiness["candidate"]["readyForThresholdBaseline"] is True,
        "complete candidate report is threshold-baseline ready",
    )
    expect(
        readiness["compatibleReadyPair"] is False,
        "metadata mismatches keep pair readiness advisory",
    )
    expect(
        readiness["baseline"]["reasons"] == [],
        "ready baseline has no readiness reasons",
    )
    expect(
        readiness["baseline"]["context"]["categories"]
        == ["control-flow", "descriptor-arrays", "storage-buffers"],
        "readiness carries category context",
    )
    expect(
        readiness["baseline"]["context"]["profiles"] == ["debug", "release"],
        "readiness carries profile context",
    )
    expect(
        readiness["baseline"]["context"]["toolchains"]["cglc"]["version"]
        == "0.6.0-fixture",
        "readiness carries toolchain context",
    )
    stability = baseline_policy["stability"]
    expect(stability["mode"] == "report-only", "pairwise stability is report-only")
    expect(
        stability["stableEnoughForThresholdBaseline"] is False,
        "metadata drift keeps default pair stability incomplete",
    )
    expect(
        stability["context"]["baseline"]["fields"]["hostLabel"]
        == "ci-linux-x86_64-pool-a",
        "stability carries host context",
    )
    expect(
        stability["context"]["baseline"]["categories"]
        == ["control-flow", "descriptor-arrays", "storage-buffers"],
        "stability carries category context",
    )
    expect(
        stability["context"]["candidate"]["toolchains"]["cglc"]["version"]
        == "0.6.0-fixture",
        "stability carries candidate toolchain context",
    )
    expect(
        stability["recommendedSpreadExceededCases"]
        == [
            "nested-control-flow::directx::release",
            "storage-buffer-compute::directx::release",
        ],
        "stability reports spread outliers without failing",
    )
    advisory_context = payload["timing"]["advisoryContext"]
    advisory_summary = payload["metadata"]["baselinePolicy"]["advisorySummary"]
    expect(
        advisory_summary == advisory_context["advisorySummary"],
        "advisory summary is shared by metadata and timing context",
    )
    expect(
        advisory_summary["mode"] == "report-only"
        and advisory_summary["failureMode"] == "report-only",
        "advisory summary is report-only",
    )
    expect(
        advisory_summary["warningTypes"] == ["policy-value-drift"],
        "advisory summary classifies policy value drift",
    )
    expect(
        advisory_summary["mismatchedFields"] == ["comparisonWindow", "hostLabel"],
        "advisory summary lists mismatched policy fields",
    )
    expect(
        advisory_summary["metadataCompatible"] is False,
        "advisory summary records metadata incompatibility",
    )
    expect(
        advisory_context["baseline"]["fields"]["hostLabel"] == "ci-linux-x86_64-pool-a",
        "advisory context carries baseline host label",
    )
    expect(
        advisory_context["candidate"]["toolchains"]["cglc"]["version"]
        == "0.6.0-fixture",
        "advisory context carries candidate toolchain version",
    )
    expect(
        advisory_context["baseline"]["missingFields"] == [],
        "complete advisory context has no missing baseline fields",
    )
    expect(
        advisory_context["baseline"]["requiredFields"]
        == REQUIRED_ADVISORY_CONTEXT_FIELDS,
        "advisory context records required fields",
    )
    expect(
        advisory_context["baseline"]["runtimeEnvironmentMissingFields"] == [],
        "complete advisory context has runtime environment provenance",
    )
    expect(
        advisory_context["candidate"]["toolchainClassifications"]["cglc"]["role"]
        == "unspecified",
        "advisory context carries toolchain role classification",
    )
    expect(
        advisory_context["candidate"]["toolchainClasses"]
        == {"cglc": "crossgl-cglc-fixture"},
        "advisory context carries toolchain class",
    )
    expect(
        advisory_context["candidate"]["skippedToolAccounting"]["skippedToolCasesByTool"]
        == {},
        "advisory context carries skipped-tool case accounting",
    )
    expect(
        advisory_context["candidate"]["skippedToolAccounting"]["skippedCases"] == [],
        "advisory context carries skipped case list",
    )

    artifact_size = payload["artifactSize"]
    expect(artifact_size["policy"] == "advisory-no-threshold", "size policy")
    expect(
        artifact_size["comparableCaseCount"] == 3,
        "artifact size comparable count",
    )
    expect(artifact_size["unsizedCaseCount"] == 1, "artifact unsized count")
    expect(
        artifact_size["unsizedCases"] == ["dry-run-case::directx::debug"],
        "artifact unsized case list",
    )
    expect(
        artifact_size["advisoryIncreaseCount"] == 1,
        "artifact size advisory increase count",
    )
    size_increase = artifact_size["advisoryIncreases"][0]
    expect(
        size_increase["case"] == "storage-buffer-compute::directx::release",
        "artifact size advisory increase case",
    )
    expect(size_increase["deltaBytes"] == 180, "artifact size delta")
    expect(size_increase["fileCountDelta"] == 1, "artifact file-count delta")
    expect(
        size_increase["currentPolicyDisposition"] == "advisory",
        "artifact size increase remains advisory",
    )
    size_warnings = artifact_size["warningSummary"]
    expect(
        size_warnings["mode"] == "report-only"
        and size_warnings["failureMode"] == "report-only",
        "artifact-size warning summary is report-only",
    )
    expect(
        size_warnings["warningTypes"]
        == [
            "artifact-size-increase",
            "insufficient-size-evidence",
            "unmeasured-size-cases",
        ],
        "artifact-size warning summary classifies advisory size warnings",
    )
    expect(
        size_warnings["artifactSizeIncreaseCases"]
        == ["storage-buffer-compute::directx::release"],
        "artifact-size warning summary lists size increases",
    )
    expect(
        size_warnings["thresholdExceededCaseCount"] == 0
        and size_warnings["thresholdExceededCases"] == [],
        "artifact-size warning summary has no threshold excess without thresholds",
    )
    expect(
        size_warnings["thresholdPolicy"] == "not-supported-v0-report-only",
        "artifact-size warning summary keeps thresholds unsupported",
    )
    expect(
        size_warnings["insufficientEvidenceCases"] == ["dry-run-case::directx::debug"],
        "artifact-size warning summary lists insufficient size evidence",
    )
    expect(
        size_warnings["unmeasuredSizeCases"] == ["dry-run-case::directx::debug"],
        "artifact-size warning summary lists unmeasured size cases",
    )
    expect(
        size_warnings["warningCaseCount"] == 2,
        "artifact-size warning summary counts unique warning cases",
    )
    expect(
        payload["policy"]["artifactSize"]["failed"] is False,
        "artifact-size warnings do not fail the comparison",
    )

    delta_report = run_tool(
        root, ADVISORY_BASELINE, ADVISORY_CANDIDATE, "--include-timing-deltas"
    )
    expect(delta_report.returncode == 0, delta_report.stderr + delta_report.stdout)
    delta_payload = json.loads(delta_report.stdout)
    expect(delta_payload["timing"]["deltaReport"] == "all", "full delta report")
    expect(delta_payload["timing"]["timingDeltaCount"] == 3, "full delta count")
    expect(
        [entry["case"] for entry in delta_payload["timing"]["timingDeltas"]]
        == [
            "nested-control-flow::directx::release",
            "storage-buffer-compute::directx::release",
            "texture-descriptor-array::opengl::release",
        ],
        "full delta case order",
    )
    expect(
        delta_payload["timing"]["timingDeltas"][0]["deltaNs"] == -20,
        "faster delta is reported",
    )
    expect(
        delta_payload["timing"]["timingDeltas"][0]["changeKind"] == "improvement",
        "faster delta is classified",
    )

    size_delta_report = run_tool(
        root, ADVISORY_BASELINE, ADVISORY_CANDIDATE, "--include-size-deltas"
    )
    expect(
        size_delta_report.returncode == 0,
        size_delta_report.stderr + size_delta_report.stdout,
    )
    size_delta_payload = json.loads(size_delta_report.stdout)
    expect(
        size_delta_payload["artifactSize"]["deltaReport"] == "all",
        "full size delta report",
    )
    expect(
        size_delta_payload["artifactSize"]["sizeDeltaCount"] == 3,
        "full size delta count",
    )
    expect(
        [entry["case"] for entry in size_delta_payload["artifactSize"]["sizeDeltas"]]
        == [
            "nested-control-flow::directx::release",
            "storage-buffer-compute::directx::release",
            "texture-descriptor-array::opengl::release",
        ],
        "full size delta case order",
    )
    expect(
        size_delta_payload["artifactSize"]["sizeDeltas"][0]["changeKind"] == "decrease",
        "smaller artifact delta is classified",
    )
    expect(
        size_delta_payload["artifactSize"]["sizeDeltas"][2]["changeKind"]
        == "unchanged",
        "unchanged artifact size is classified",
    )

    no_profile = run_tool(
        root,
        ADVISORY_BASELINE,
        ADVISORY_CANDIDATE,
        "--advisory-threshold-profile",
        "none",
    )
    expect(no_profile.returncode == 0, no_profile.stderr + no_profile.stdout)
    no_profile_payload = json.loads(no_profile.stdout)
    expect(
        no_profile_payload["timing"]["advisoryThresholdProfile"]["name"] == "none",
        "disabled threshold profile",
    )
    expect(
        no_profile_payload["timing"]["advisoryThresholdExceededCount"] == 0,
        "disabled profile proposed failure count",
    )
    expect(
        no_profile_payload["timing"]["advisoryRegressions"][0]["advisoryThreshold"]
        is None,
        "disabled profile omits per-case advisory threshold",
    )

    passing_threshold = run_tool(
        root, ADVISORY_BASELINE, ADVISORY_CANDIDATE, "--max-regression-percent", "20"
    )
    expect(
        passing_threshold.returncode == 0,
        passing_threshold.stderr + passing_threshold.stdout,
    )
    passing_payload = json.loads(passing_threshold.stdout)
    expect(passing_payload["status"] == "pass", "20 percent threshold")
    check_report_artifact_contract(
        passing_payload,
        "explicit advisory threshold comparison",
    )
    expect(
        passing_payload["timing"]["policy"] == "advisory-threshold",
        "advisory threshold policy",
    )
    expect(
        passing_payload["timing"]["explicitHardPolicy"]["enabled"] is False,
        "hard policy remains disabled",
    )
    expect(
        passing_payload["timing"]["explicitThresholdPolicy"]["enabled"] is True,
        "explicit report-only threshold enabled",
    )
    expect(
        passing_payload["timing"]["explicitThresholdPolicy"]["mode"] == "report-only",
        "explicit threshold is report-only",
    )
    expect(
        passing_payload["timing"]["explicitThresholdPolicy"][
            "measuredThresholdExceededCaseCount"
        ]
        == 0,
        "20 percent threshold has no measured explicit excess",
    )
    expect(
        passing_payload["timing"]["thresholdExceededCount"] == 0,
        "20 percent advisory threshold passes",
    )
    expect(
        passing_payload["timing"]["advisoryThresholdExceededCount"] == 0,
        "metadata drift withholds proposed threshold claims",
    )
    expect(
        passing_payload["timing"]["advisoryRegressions"][0]["currentPolicyDisposition"]
        == "advisory-threshold-incomparable-metadata",
        "explicit advisory threshold remains report-only with metadata drift",
    )

    failing_threshold = run_tool(
        root, ADVISORY_BASELINE, ADVISORY_CANDIDATE, "--max-regression-percent", "10"
    )
    expect(failing_threshold.returncode == 0, failing_threshold.stdout)
    failing_payload = json.loads(failing_threshold.stdout)
    expect(failing_payload["status"] == "pass", "10 percent threshold remains advisory")
    check_report_artifact_contract(
        failing_payload,
        "exceeded explicit advisory threshold comparison",
    )
    expect(
        failing_payload["policy"]["failureClass"] == "pass",
        "timing-only advisory threshold does not set failure class",
    )
    expect(
        failing_payload["policy"]["failurePriority"] == [],
        "timing-only advisory threshold does not set failure priority",
    )
    expect(
        failing_payload["timing"]["failedRegressionCount"] == 0,
        "explicit advisory threshold never creates failed regressions",
    )
    expect(
        failing_payload["timing"]["thresholdExceededCount"] == 0,
        "metadata drift withholds explicit threshold claims",
    )
    expect(
        failing_payload["timing"]["explicitThresholdPolicy"][
            "measuredThresholdExceededCases"
        ]
        == ["storage-buffer-compute::directx::release"],
        "metadata drift still reports measured explicit threshold excess",
    )
    expect(
        failing_payload["timing"]["explicitThresholdPolicy"]["claimDispositionCounts"]
        == {"incomparable-metadata": 3},
        "explicit threshold policy counts withheld claim dispositions",
    )
    expect(
        failing_payload["timing"]["evidenceSufficiency"][
            "explicitThresholdMeasuredExceededCaseCount"
        ]
        == 1,
        "evidence sufficiency counts measured explicit threshold excess",
    )
    failing_observation = failing_payload["timing"]["advisoryRegressions"][0]
    expect(
        failing_observation["case"] == "storage-buffer-compute::directx::release",
        "advisory threshold observation case",
    )
    expect(
        failing_observation["measuredExceedsExplicitThreshold"] is True,
        "measured explicit threshold excess remains visible",
    )
    expect(
        failing_observation["exceedsExplicitThreshold"] is False,
        "metadata drift prevents explicit threshold claim",
    )
    expect(
        failing_observation["currentPolicyDisposition"]
        == "advisory-threshold-incomparable-metadata",
        "metadata drift disposition is explicit for explicit thresholds",
    )
    expect(
        failing_observation["explicitThreshold"]["evidence"][
            "claimEligibilityDisposition"
        ]
        == "incomparable-metadata",
        "explicit threshold embeds claim eligibility disposition",
    )


def timed_case(
    key: str,
    *,
    backend: str | None = None,
    category: str,
    elapsed_ns: int,
    opt_level: str | None = None,
    profile: str = "release",
    target: str = "directx",
) -> dict[str, Any]:
    fixture_name = key.split("::", 1)[0]
    if opt_level is None:
        opt_level = "O2" if profile == "release" else "Debug"
    case = {
        "case": key,
        "commandProfile": {"name": profile},
        "fixtureCategory": category,
        "fixtureName": fixture_name,
        "optLevel": opt_level,
        "profile": profile,
        "skipped": False,
        "target": target,
        "timing": {"elapsedNs": elapsed_ns},
        "unavailableTools": [],
    }
    if backend is not None:
        case["backend"] = backend
    return case


def native_profile_case(
    key: str,
    *,
    native_profile: dict[str, Any],
    profile: str = "release",
    target: str = "vulkan",
) -> dict[str, Any]:
    case = timed_case(
        key,
        category="storage-buffers",
        elapsed_ns=100,
        profile=profile,
        target=target,
    )
    case["artifactSummary"] = {
        "available": True,
        "byteSize": 10,
        "fileCount": 1,
        "nativeProfile": native_profile,
    }
    return case


def native_artifact_descriptor_case(
    key: str,
    *,
    optimization_evidence: dict[str, Any] | None,
    profile: str = "release",
    target: str = "vulkan",
) -> dict[str, Any]:
    case = timed_case(
        key,
        category="storage-buffers",
        elapsed_ns=100,
        profile=profile,
        target=target,
    )
    case["artifactSummary"] = {
        "available": True,
        "byteSize": 10,
        "fileCount": 1,
        "nativeArtifactDescriptor": {
            "available": True,
            "declared": True,
            "optimizationEvidence": optimization_evidence,
            "optimizationEvidenceStatus": (
                native_artifact_descriptor_evidence_status_from_evidence(
                    optimization_evidence
                )
            ),
            "optimizationLevel": "O2",
            "parseError": None,
            "path": "metadata/native-artifact.json",
            "schemaVersion": 1,
            "target": target,
        },
    }
    return case


def native_optimization_status(case: dict[str, Any]) -> str | None:
    native_profile = case.get("artifactSummary", {}).get("nativeProfile")
    if not isinstance(native_profile, dict):
        return None
    optimization = native_profile.get("optimization")
    if not isinstance(optimization, dict):
        return None
    status = optimization.get("status")
    return status if isinstance(status, str) and status else None


def native_optimization_evidence_status(case: dict[str, Any]) -> str:
    native_profile = case.get("artifactSummary", {}).get("nativeProfile")
    if not isinstance(native_profile, dict):
        return "native-profile-not-declared"
    optimization = native_profile.get("optimization")
    if isinstance(optimization, dict):
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


def native_artifact_descriptor_optimization_status(case: dict[str, Any]) -> str | None:
    descriptor = case.get("artifactSummary", {}).get("nativeArtifactDescriptor")
    if not isinstance(descriptor, dict):
        return None
    evidence = descriptor.get("optimizationEvidence")
    if not isinstance(evidence, dict):
        return None
    status = evidence.get("status")
    return status if isinstance(status, str) and status else None


def native_artifact_descriptor_evidence_status_from_evidence(
    evidence: dict[str, Any] | None,
) -> str:
    if isinstance(evidence, dict):
        status = evidence.get("status")
        if isinstance(status, str) and status:
            return "known-status"
        return "optimization-without-status"
    return "missing-optimization-evidence"


def native_artifact_descriptor_evidence_status(case: dict[str, Any]) -> str:
    descriptor = case.get("artifactSummary", {}).get("nativeArtifactDescriptor")
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


def add_count(counts: dict[str, int], label: str | None) -> None:
    if not isinstance(label, str) or not label:
        return
    counts[label] = counts.get(label, 0) + 1


def native_optimization_evidence_summary(
    case_count: int, evidence_counts: dict[str, int]
) -> dict[str, Any]:
    known_status_count = evidence_counts.get("known-status", 0)
    missing_count = evidence_counts.get("missing-debug-optimization", 0)
    unparsable_count = evidence_counts.get("unparsable-native-profile", 0)
    declared_missing_count = evidence_counts.get("declared-native-profile-missing", 0)
    without_status_count = evidence_counts.get("optimization-without-status", 0)
    not_declared_count = evidence_counts.get("native-profile-not-declared", 0)
    return {
        "caseCount": case_count,
        "caseCountByEvidenceStatus": dict(sorted(evidence_counts.items())),
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


def native_artifact_descriptor_evidence_summary(
    case_count: int, evidence_counts: dict[str, int]
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
        "caseCountByEvidenceStatus": dict(sorted(evidence_counts.items())),
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


def add_native_optimization_summary(payload: dict[str, Any]) -> None:
    status_counts: dict[str, int] = {}
    evidence_counts: dict[str, int] = {}
    for case in payload["cases"]:
        add_count(status_counts, native_optimization_status(case))
        add_count(evidence_counts, native_optimization_evidence_status(case))
    payload["summary"]["caseCountByNativeOptimizationStatus"] = dict(
        sorted(status_counts.items())
    )
    payload["summary"]["nativeOptimizationStatuses"] = sorted(status_counts)
    payload["summary"]["caseCountByNativeOptimizationEvidenceStatus"] = dict(
        sorted(evidence_counts.items())
    )
    payload["summary"]["nativeOptimizationEvidence"] = (
        native_optimization_evidence_summary(len(payload["cases"]), evidence_counts)
    )


def add_native_artifact_descriptor_optimization_summary(
    payload: dict[str, Any],
) -> None:
    status_counts: dict[str, int] = {}
    evidence_counts: dict[str, int] = {}
    for case in payload["cases"]:
        add_count(status_counts, native_artifact_descriptor_optimization_status(case))
        add_count(evidence_counts, native_artifact_descriptor_evidence_status(case))
    payload["summary"]["caseCountByNativeArtifactDescriptorOptimizationStatus"] = dict(
        sorted(status_counts.items())
    )
    payload["summary"]["nativeArtifactDescriptorOptimizationStatuses"] = sorted(
        status_counts
    )
    payload["summary"][
        "caseCountByNativeArtifactDescriptorOptimizationEvidenceStatus"
    ] = dict(sorted(evidence_counts.items()))
    payload["summary"]["nativeArtifactDescriptorOptimizationEvidence"] = (
        native_artifact_descriptor_evidence_summary(
            len(payload["cases"]), evidence_counts
        )
    )


def artifact_kind_case(
    key: str,
    *,
    artifacts: list[dict[str, Any]],
    byte_size: int,
    file_count: int,
) -> dict[str, Any]:
    case = timed_case(key, category="storage-buffers", elapsed_ns=100)
    case["artifactSummary"] = {
        "available": True,
        "byteSize": byte_size,
        "emittedManifestArtifactCount": sum(
            1 for artifact in artifacts if artifact.get("exists") is True
        ),
        "fileCount": file_count,
        "manifestArtifactByteSize": sum(
            artifact["bytes"]
            for artifact in artifacts
            if artifact.get("exists") is True and isinstance(artifact.get("bytes"), int)
        ),
        "manifestArtifactCount": len(artifacts),
        "manifestArtifacts": artifacts,
        "missingManifestArtifactCount": sum(
            1 for artifact in artifacts if artifact.get("exists") is False
        ),
    }
    return case


def add_manifest_artifact_kind_summary(payload: dict[str, Any]) -> None:
    summary: dict[str, dict[str, int]] = {}
    case_count = 0
    for case in payload["cases"]:
        artifacts = case.get("artifactSummary", {}).get("manifestArtifacts")
        if not isinstance(artifacts, list) or not artifacts:
            continue
        case_count += 1
        case_kinds: set[str] = set()
        emitted_case_kinds: set[str] = set()
        missing_case_kinds: set[str] = set()
        for artifact in artifacts:
            kind = artifact.get("kind")
            if not isinstance(kind, str) or not kind:
                continue
            metrics = summary.setdefault(
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
            metrics["count"] += 1
            case_kinds.add(kind)
            if artifact.get("exists") is True:
                metrics["emittedCount"] += 1
                emitted_case_kinds.add(kind)
                if isinstance(artifact.get("bytes"), int):
                    metrics["byteSize"] += artifact["bytes"]
            elif artifact.get("exists") is False:
                metrics["missingCount"] += 1
                missing_case_kinds.add(kind)
        for kind in case_kinds:
            summary[kind]["caseCount"] += 1
        for kind in emitted_case_kinds:
            summary[kind]["emittedCaseCount"] += 1
        for kind in missing_case_kinds:
            summary[kind]["missingCaseCount"] += 1

    payload["summary"]["manifestArtifactKindCaseCount"] = case_count
    payload["summary"]["manifestArtifactKindCount"] = len(summary)
    payload["summary"]["manifestArtifactKinds"] = {
        kind: summary[kind] for kind in sorted(summary)
    }


def complete_policy_report(
    cases: list[dict[str, Any]],
    *,
    host_label: str = "ci-linux-x86_64-pool-a",
) -> dict[str, Any]:
    payload = report(cases)
    payload["baselinePolicy"] = {
        "comparisonWindow": {
            "sampleCount": 5,
            "unit": "elapsedNs",
            "warmupCount": 1,
        },
        "hostClass": "linux-x86_64",
        "hostLabel": host_label,
        "optLevel": "O2",
        "targetProfile": "crossgl-milestone6-smoke",
        "toolchainClass": "crossgl-cglc-fixture",
        "toolchainLabel": "cglc",
        "toolchainVersion": "0.6.0-fixture",
    }
    payload["metadata"] = {
        "runtimeEnvironment": FIXTURE_RUNTIME_ENVIRONMENT,
    }
    payload["toolAvailability"] = {
        "cglc": {
            "available": True,
            "class": "crossgl-cglc-fixture",
            "status": "available",
            "version": "0.6.0-fixture",
        }
    }
    return payload


def producer_advisory_threshold_policy(
    name: str,
    *,
    rule_count: int = 0,
) -> dict[str, Any]:
    rules = [
        {
            "category": "storage-buffers",
            "label": "synthetic producer threshold",
            "maxRegressionPercent": 12,
            "profile": "release",
            "ruleSpecificity": "category-profile",
        }
        for _ in range(rule_count)
    ]
    return {
        "schemaVersion": 1,
        "tool": "benchmark_performance_corpus",
        "kind": "advisory-threshold-policy",
        "mode": "report-only",
        "name": name,
        "status": "policy-stub",
        "thresholdSource": "synthetic-test",
        "ruleCount": rule_count,
        "rules": rules,
        "stableBaselineDataPresent": False,
        "enforcement": {
            "mode": "report-only",
            "failureMode": "report-only",
            "enforced": False,
            "hardFail": False,
            "exitStatusAffected": False,
            "releaseBlocker": False,
        },
    }


def producer_threshold_readiness(
    *,
    ready: bool,
    status: str,
    reasons: list[str],
) -> dict[str, Any]:
    requirement = {
        "name": "syntheticProducerClaim",
        "observed": {},
        "reasonIfUnsatisfied": reasons[0] if reasons else "synthetic-ready",
        "satisfied": ready,
    }
    return {
        "advisory": True,
        "mode": "report-only",
        "failureMode": "report-only",
        "readyForThresholdBaseline": ready,
        "stableBaselineDataPresent": False,
        "status": status,
        "reasonCount": len(reasons),
        "reasons": reasons,
        "satisfiedThresholdBaselineRequirementCount": 1 if ready else 0,
        "thresholdBaselineRequirementCount": 1,
        "thresholdBaselineRequirements": [requirement],
        "unsatisfiedThresholdBaselineRequirementCount": 0 if ready else 1,
        "unsatisfiedThresholdBaselineRequirements": (
            [] if ready else ["syntheticProducerClaim"]
        ),
    }


def add_producer_claims(
    payload: dict[str, Any],
    *,
    policy: dict[str, Any],
    metadata_policy: dict[str, Any] | None = None,
    readiness: dict[str, Any],
    metadata_readiness: dict[str, Any] | None = None,
) -> None:
    payload["advisoryThresholdPolicy"] = policy
    payload["thresholdBaselineReadiness"] = readiness
    metadata = payload.setdefault("metadata", {})
    metadata["advisoryThresholdPolicy"] = (
        copy.deepcopy(policy)
        if metadata_policy is None
        else copy.deepcopy(metadata_policy)
    )
    metadata["thresholdBaselineReadiness"] = (
        copy.deepcopy(readiness)
        if metadata_readiness is None
        else copy.deepcopy(metadata_readiness)
    )


def timing_run(iteration: int, duration_ns: int) -> dict[str, int]:
    return {
        "durationNs": duration_ns,
        "exitStatus": 0,
        "iteration": iteration,
        "outputBytes": 0,
        "stderrBytes": 0,
        "stdoutBytes": 0,
    }


def add_measurement_window(
    payload: dict[str, Any],
    *,
    sample_count: int,
    warmup_count: int,
) -> None:
    measurement_window = {
        "sampleCount": sample_count,
        "unit": "elapsedNs",
        "warmupCount": warmup_count,
    }
    payload.setdefault("metadata", {})["measurementWindow"] = measurement_window
    payload["summary"]["measurementWindow"] = measurement_window
    timed_cases = [
        case for case in payload["cases"] if isinstance(case.get("timing"), dict)
    ]
    measured_run_count = sum(
        len(case["timing"].get("runs", [])) for case in timed_cases
    )
    warmup_run_count = sum(
        len(case["timing"].get("warmups", [])) for case in timed_cases
    )
    mismatched_cases = sorted(
        case["case"]
        for case in timed_cases
        if case["timing"].get("sampleCount") != sample_count
        or case["timing"].get("warmupCount") != warmup_count
        or len(case["timing"].get("runs", [])) != sample_count
        or len(case["timing"].get("warmups", [])) != warmup_count
    )
    payload["summary"]["measuredRunCount"] = measured_run_count
    payload["summary"]["warmupRunCount"] = warmup_run_count
    payload["summary"]["timingWindow"] = {
        "consistent": (
            not mismatched_cases
            and measured_run_count == len(timed_cases) * sample_count
            and warmup_run_count == len(timed_cases) * warmup_count
        ),
        "expectedMeasuredRunCount": len(timed_cases) * sample_count,
        "expectedSampleCount": sample_count,
        "expectedWarmupCount": warmup_count,
        "expectedWarmupRunCount": len(timed_cases) * warmup_count,
        "measuredRunCount": measured_run_count,
        "mismatchedCaseCount": len(mismatched_cases),
        "mismatchedCases": mismatched_cases,
        "timedCaseCount": len(timed_cases),
        "warmupRunCount": warmup_run_count,
    }


def timed_case_with_runs(
    key: str,
    *,
    category: str,
    elapsed_ns: int,
    sample_count: int = 3,
    warmup_count: int = 2,
) -> dict[str, Any]:
    case = timed_case(key, category=category, elapsed_ns=elapsed_ns)
    case["timing"] = {
        "elapsedNs": elapsed_ns,
        "runs": [
            timing_run(index + 1, max(0, elapsed_ns + index - (sample_count // 2)))
            for index in range(sample_count)
        ],
        "sampleCount": sample_count,
        "warmupCount": warmup_count,
        "warmups": [
            timing_run(index + 1, max(0, elapsed_ns - 10 + index))
            for index in range(warmup_count)
        ],
    }
    return case


def check_native_optimization_evidence_accounting(root: Path, tmp: Path) -> None:
    known_profile = {
        "available": True,
        "declared": True,
        "optimization": {
            "level": "-O",
            "policy": "use-when-available",
            "requestedLevel": "O2",
            "status": "applied",
            "tool": "spirv-opt",
        },
        "parseError": None,
    }
    missing_optimization_profile = {
        "available": True,
        "declared": True,
        "optimization": None,
        "parseError": None,
    }
    invalid_profile = {
        "available": True,
        "declared": True,
        "optimization": None,
        "parseError": "invalid-json",
    }
    baseline = complete_policy_report(
        [
            native_profile_case(
                "storage-buffer-compute::vulkan::release",
                native_profile=known_profile,
            ),
            native_profile_case(
                "nested-control-flow::vulkan::release",
                native_profile=missing_optimization_profile,
            ),
        ]
    )
    candidate = complete_policy_report(
        [
            native_profile_case(
                "storage-buffer-compute::vulkan::release",
                native_profile=missing_optimization_profile,
            ),
            native_profile_case(
                "nested-control-flow::vulkan::release",
                native_profile=invalid_profile,
            ),
        ]
    )
    baseline_path = tmp / "native-evidence-baseline.json"
    candidate_path = tmp / "native-evidence-candidate.json"
    write_report(baseline_path, baseline)
    write_report(candidate_path, candidate)

    result = run_tool(root, baseline_path, candidate_path)
    expect(result.returncode == 0, result.stderr + result.stdout)
    payload = json.loads(result.stdout)
    native_optimization = payload["nativeOptimization"]
    expect(
        native_optimization["status"] == "drift-detected",
        "native evidence drift status",
    )
    expect(
        native_optimization["statusDriftCount"] == 1,
        "native evidence scenario has one status drift",
    )
    expect(
        native_optimization["evidenceDriftCount"] == 2,
        "native evidence scenario has two coverage drifts",
    )
    expect(
        native_optimization["baseline"]["caseCountByEvidenceStatus"]
        == {"known-status": 1, "missing-debug-optimization": 1},
        "baseline native evidence coverage counts",
    )
    expect(
        native_optimization["candidate"]["caseCountByEvidenceStatus"]
        == {"missing-debug-optimization": 1, "unparsable-native-profile": 1},
        "candidate native evidence coverage counts",
    )
    expect(
        native_optimization["caseCountByEvidenceStatusDeltas"]
        == [
            {
                "baselineCount": 1,
                "candidateCount": 0,
                "delta": -1,
                "status": "known-status",
            },
            {
                "baselineCount": 0,
                "candidateCount": 1,
                "delta": 1,
                "status": "unparsable-native-profile",
            },
        ],
        "native evidence coverage deltas",
    )
    expect(
        native_optimization["evidenceTransitionCounts"]
        == {
            "known-status -> missing-debug-optimization": 1,
            "missing-debug-optimization -> unparsable-native-profile": 1,
        },
        "native evidence transition counts",
    )


def check_invalid_native_optimization_evidence_probe(root: Path, tmp: Path) -> None:
    known_profile = {
        "available": True,
        "declared": True,
        "optimization": {
            "level": "-O",
            "policy": "use-when-available",
            "requestedLevel": "O2",
            "status": "applied",
            "tool": "spirv-opt",
        },
        "parseError": None,
    }
    optimization_without_status = {
        "available": True,
        "declared": True,
        "optimization": {
            "level": "-O",
            "policy": "use-when-available",
            "requestedLevel": "O2",
            "tool": "spirv-opt",
        },
        "parseError": None,
    }
    baseline = tmp / "native-invalid-evidence-baseline.json"
    candidate = tmp / "native-invalid-evidence-candidate.json"
    case_key = "storage-buffer-compute::vulkan::release"
    write_report(
        baseline,
        complete_policy_report(
            [
                native_profile_case(
                    case_key,
                    native_profile=known_profile,
                )
            ]
        ),
    )
    write_report(
        candidate,
        complete_policy_report(
            [
                native_profile_case(
                    case_key,
                    native_profile=optimization_without_status,
                )
            ]
        ),
    )

    result = run_tool(root, baseline, candidate, "--max-regression-percent", "1")
    expect(result.returncode == 0, result.stderr + result.stdout)
    payload = json.loads(result.stdout)
    expect(
        payload["status"] == "pass",
        "invalid native optimization evidence remains report-only",
    )
    expect(
        payload["structure"]["validationIssueCount"] == 0,
        "invalid native evidence is not a report-shape failure",
    )
    expect(
        payload["policy"]["nativeOptimization"]["mode"] == "report-only",
        "invalid native evidence native optimization policy",
    )
    expect(
        payload["policy"]["nativeOptimization"]["failed"] is False,
        "invalid native evidence does not fail native optimization policy",
    )
    native_optimization = payload["nativeOptimization"]
    expect(
        native_optimization["candidate"]["caseCountByEvidenceStatus"]
        == {"optimization-without-status": 1},
        "invalid native evidence status is classified",
    )
    expect(
        native_optimization["evidenceTransitionCounts"]
        == {"known-status -> optimization-without-status": 1},
        "invalid native evidence transition is explicit",
    )
    expect(
        native_optimization["statusTransitionCounts"] == {"applied -> unspecified": 1},
        "invalid native status transition is explicit",
    )
    expect(
        "never change comparator exit status" in native_optimization["policy"].lower(),
        "invalid native evidence policy remains advisory",
    )


def check_native_optimization_summary_validation(root: Path, tmp: Path) -> None:
    known_profile = {
        "available": True,
        "declared": True,
        "optimization": {
            "level": "-O",
            "policy": "use-when-available",
            "requestedLevel": "O2",
            "status": "applied",
            "tool": "spirv-opt",
        },
        "parseError": None,
    }
    missing_optimization_profile = {
        "available": True,
        "declared": True,
        "optimization": None,
        "parseError": None,
    }
    cases = [
        native_profile_case(
            "storage-buffer-compute::vulkan::release",
            native_profile=known_profile,
        ),
        native_profile_case(
            "nested-control-flow::vulkan::release",
            native_profile=missing_optimization_profile,
        ),
    ]
    baseline_payload = complete_policy_report(copy.deepcopy(cases))
    candidate_payload = complete_policy_report(copy.deepcopy(cases))
    add_native_optimization_summary(baseline_payload)
    add_native_optimization_summary(candidate_payload)

    baseline = tmp / "native-summary-baseline.json"
    candidate = tmp / "native-summary-candidate.json"
    write_report(baseline, baseline_payload)
    write_report(candidate, candidate_payload)
    result = run_tool(root, baseline, candidate)
    expect(result.returncode == 0, result.stderr + result.stdout)
    payload = json.loads(result.stdout)
    expect(payload["status"] == "pass", "fresh native summaries should compare")
    expect(
        payload["structure"]["validationIssueCount"] == 0,
        "fresh native summaries have no validation issues",
    )
    expect(
        payload["nativeOptimization"]["baseline"]["summaryCountsMatchCases"] is True,
        "fresh native status counts match cases",
    )
    expect(
        payload["nativeOptimization"]["baseline"]["summaryStatusesMatchCases"] is True,
        "fresh native status list matches cases",
    )
    expect(
        payload["nativeOptimization"]["baseline"]["summaryEvidenceCountsMatchCases"]
        is True,
        "fresh native evidence counts match cases",
    )

    stale_payload = copy.deepcopy(candidate_payload)
    stale_payload["summary"]["caseCountByNativeOptimizationStatus"] = {"applied": 2}
    stale_payload["summary"]["nativeOptimizationStatuses"] = [
        "applied",
        "skipped-disabled",
    ]
    stale_payload["summary"]["caseCountByNativeOptimizationEvidenceStatus"] = {
        "known-status": 2
    }
    stale_payload["summary"]["nativeOptimizationEvidence"]["knownStatusCount"] = 2
    stale_candidate = tmp / "native-summary-stale-candidate.json"
    write_report(stale_candidate, stale_payload)

    stale_result = run_tool(root, baseline, stale_candidate)
    expect(stale_result.returncode == 1, stale_result.stderr + stale_result.stdout)
    stale_comparison = json.loads(stale_result.stdout)
    expect(
        stale_comparison["policy"]["structural"]["failureReasons"]
        == ["candidateValidationIssues"],
        "stale native summaries are structural report-shape issues",
    )
    stale_issues = stale_comparison["structure"]["validationIssues"]
    for snippet in (
        "candidate.summary.caseCountByNativeOptimizationStatus={'applied': 2} "
        "does not match cases ({'applied': 1})",
        "candidate.summary.nativeOptimizationStatuses=['applied', "
        "'skipped-disabled'] does not match cases (['applied'])",
        "candidate.summary.caseCountByNativeOptimizationEvidenceStatus="
        "{'known-status': 2} does not match cases ({'known-status': 1, "
        "'missing-debug-optimization': 1})",
        "candidate.summary.nativeOptimizationEvidence={'caseCount': 2",
    ):
        expect(
            any(snippet in issue for issue in stale_issues),
            f"stale native summary diagnostic includes {snippet}",
        )

    older_baseline = tmp / "native-summary-old-baseline.json"
    older_candidate = tmp / "native-summary-old-candidate.json"
    write_report(older_baseline, complete_policy_report(copy.deepcopy(cases)))
    write_report(
        older_candidate,
        complete_policy_report(
            copy.deepcopy(cases),
            host_label="ci-linux-x86_64-pool-b",
        ),
    )
    older_result = run_tool(root, older_baseline, older_candidate)
    expect(older_result.returncode == 0, older_result.stderr + older_result.stdout)
    older_payload = json.loads(older_result.stdout)
    expect(
        older_payload["status"] == "pass",
        "older reports without native summaries still compare",
    )
    expect(
        older_payload["structure"]["validationIssueCount"] == 0,
        "missing native summary fields stay backward-compatible",
    )
    expect(
        older_payload["nativeOptimization"]["baseline"]["summaryCaseCountByStatus"]
        is None,
        "older reports expose missing native status summary as advisory context",
    )
    expect(
        older_payload["nativeOptimization"]["summaryCountDeltaReport"]
        == "missing-or-invalid-summary-counts",
        "older reports skip native summary delta comparisons",
    )
    expect(
        older_payload["metadata"]["baselinePolicy"]["compatibility"]["compatible"]
        is False,
        "older-report probe records advisory metadata drift",
    )
    expect(
        older_payload["policy"]["failureClass"] == "pass",
        "advisory metadata drift does not affect comparator exit status",
    )


def check_native_artifact_descriptor_optimization_evidence_drift(
    root: Path, tmp: Path
) -> None:
    baseline_evidence = {
        "requestedLevel": "O2",
        "effectiveLevel": "O2",
        "policy": "spirv-opt",
        "status": "applied",
        "tool": "spirv-opt",
        "toolFlag": "-O",
    }
    candidate_evidence = {
        "requestedLevel": "O2",
        "effectiveLevel": "O1",
        "policy": "spirv-opt",
        "status": "skipped-tool-missing",
        "tool": "spirv-opt",
        "toolFlag": "-O1",
    }
    case_key = "storage-buffer-compute::vulkan::release"
    baseline_payload = complete_policy_report(
        [
            native_artifact_descriptor_case(
                case_key, optimization_evidence=baseline_evidence
            )
        ]
    )
    candidate_payload = complete_policy_report(
        [
            native_artifact_descriptor_case(
                case_key, optimization_evidence=candidate_evidence
            )
        ]
    )
    add_native_artifact_descriptor_optimization_summary(baseline_payload)
    add_native_artifact_descriptor_optimization_summary(candidate_payload)

    baseline = tmp / "native-descriptor-baseline.json"
    candidate = tmp / "native-descriptor-candidate.json"
    write_report(baseline, baseline_payload)
    write_report(candidate, candidate_payload)

    result = run_tool(root, baseline, candidate)
    expect(result.returncode == 0, result.stderr + result.stdout)
    payload = json.loads(result.stdout)
    expect(
        payload["status"] == "pass",
        "native descriptor optimization drift remains report-only",
    )
    expect(
        payload["structure"]["validationIssueCount"] == 0,
        "native descriptor summaries validate",
    )
    native_optimization = payload["nativeOptimization"]
    expect(
        native_optimization["status"] == "drift-detected",
        "native descriptor drift status",
    )
    expect(
        native_optimization["statusDriftCount"] == 0,
        "native profile status remains unchanged",
    )
    expect(
        native_optimization["descriptorStatusDriftCount"] == 1,
        "native descriptor status drift count",
    )
    expect(
        native_optimization["descriptorFieldDriftCount"] == 1,
        "native descriptor field drift case count",
    )
    expect(
        native_optimization["descriptorFieldDriftCounts"]
        == {"effectiveLevel": 1, "status": 1, "toolFlag": 1},
        "native descriptor field drift counts",
    )
    expect(
        native_optimization["descriptorStatusTransitionCounts"]
        == {"applied -> skipped-tool-missing": 1},
        "native descriptor status transition",
    )
    field_drifts = native_optimization["descriptorFieldDrifts"][0]["fieldDrifts"]
    fields = {drift["field"]: drift for drift in field_drifts}
    expect(
        fields["effectiveLevel"]["candidate"] == "O1",
        "native descriptor effective level drift",
    )
    expect(
        fields["toolFlag"]["candidate"] == "-O1",
        "native descriptor tool flag drift",
    )
    expect(
        native_optimization["caseCountByNativeArtifactDescriptorStatusDeltas"]
        == [
            {
                "baselineCount": 1,
                "candidateCount": 0,
                "delta": -1,
                "status": "applied",
            },
            {
                "baselineCount": 0,
                "candidateCount": 1,
                "delta": 1,
                "status": "skipped-tool-missing",
            },
        ],
        "native descriptor status count deltas",
    )
    expect(
        native_optimization["summaryDescriptorCountDeltaReport"] == "available",
        "native descriptor summary deltas are available",
    )
    expect(
        payload["policy"]["nativeOptimization"]["descriptorStatusDriftCount"] == 1,
        "native descriptor policy status drift count",
    )
    expect(
        payload["policy"]["nativeOptimization"]["descriptorFieldDriftCount"] == 1,
        "native descriptor policy field drift count",
    )
    expect(
        payload["policy"]["failureClass"] == "pass",
        "native descriptor drift does not affect failure class",
    )

    stale_payload = copy.deepcopy(candidate_payload)
    stale_payload["summary"][
        "caseCountByNativeArtifactDescriptorOptimizationStatus"
    ] = {"applied": 1}
    stale_payload["summary"]["nativeArtifactDescriptorOptimizationEvidence"][
        "knownStatusCount"
    ] = 2
    stale_candidate = tmp / "native-descriptor-stale-candidate.json"
    write_report(stale_candidate, stale_payload)

    stale_result = run_tool(root, baseline, stale_candidate)
    expect(stale_result.returncode == 1, stale_result.stderr + stale_result.stdout)
    stale_comparison = json.loads(stale_result.stdout)
    stale_issues = stale_comparison["structure"]["validationIssues"]
    for snippet in (
        "candidate.summary.caseCountByNativeArtifactDescriptorOptimizationStatus",
        "candidate.summary.nativeArtifactDescriptorOptimizationEvidence="
        "{'caseCount': 1",
    ):
        expect(
            any(snippet in issue for issue in stale_issues),
            f"stale native descriptor summary diagnostic includes {snippet}",
        )


def check_manifest_artifact_kind_evidence(root: Path, tmp: Path) -> None:
    baseline = tmp / "artifact-kind-baseline.json"
    candidate = tmp / "artifact-kind-candidate.json"
    stale_candidate = tmp / "artifact-kind-stale-summary-candidate.json"
    case_key = "artifact-kind-evidence::directx::release"
    baseline_payload = report(
        [
            artifact_kind_case(
                case_key,
                byte_size=120,
                file_count=3,
                artifacts=[
                    {
                        "bytes": 100,
                        "exists": True,
                        "kind": "backendSource",
                        "path": "shader.hlsl",
                    },
                    {
                        "bytes": 20,
                        "exists": True,
                        "kind": "debugMetadata",
                        "path": "debug.json",
                    },
                    {
                        "bytes": None,
                        "exists": False,
                        "kind": "nativeBinary",
                        "path": "shader.dxil",
                    },
                ],
            )
        ]
    )
    candidate_payload = report(
        [
            artifact_kind_case(
                case_key,
                byte_size=160,
                file_count=4,
                artifacts=[
                    {
                        "bytes": 130,
                        "exists": True,
                        "kind": "backendSource",
                        "path": "shader.hlsl",
                    },
                    {
                        "bytes": None,
                        "exists": False,
                        "kind": "debugMetadata",
                        "path": "debug.json",
                    },
                    {
                        "bytes": 30,
                        "exists": True,
                        "kind": "hirSourceMap",
                        "path": "source-map.json",
                    },
                    {
                        "bytes": None,
                        "exists": False,
                        "kind": "nativeBinary",
                        "path": "shader.dxil",
                    },
                ],
            )
        ]
    )
    add_manifest_artifact_kind_summary(baseline_payload)
    add_manifest_artifact_kind_summary(candidate_payload)
    write_report(baseline, baseline_payload)
    write_report(candidate, candidate_payload)
    result = run_tool(root, baseline, candidate)
    expect(result.returncode == 0, result.stderr + result.stdout)
    payload = json.loads(result.stdout)
    expect(payload["status"] == "pass", "artifact kind evidence remains advisory")
    expect(payload["structure"]["validationIssueCount"] == 0, "artifact kind summary")
    evidence = payload["artifactSize"]["manifestArtifactKindEvidence"]
    expect(evidence["policy"] == "report-only", "artifact kind policy")
    expect(evidence["comparableCaseCount"] == 1, "artifact kind comparable count")
    expect(evidence["changedCaseCount"] == 1, "artifact kind changed case count")
    expect(evidence["kindDeltaCount"] == 3, "artifact kind delta count")
    expect(evidence["changedCases"] == [case_key], "artifact kind changed case")
    delta = evidence["deltas"][0]
    expect(delta["case"] == case_key, "artifact kind delta case")
    expect(
        delta["currentPolicyDisposition"] == "advisory",
        "artifact kind delta disposition",
    )
    by_kind = {entry["kind"]: entry for entry in delta["kinds"]}
    expect(
        by_kind["backendSource"]["deltaBytes"] == 30,
        "backendSource byte delta",
    )
    expect(
        by_kind["debugMetadata"]["missingCountDelta"] == 1,
        "debugMetadata missing delta",
    )
    expect(
        by_kind["debugMetadata"]["emittedCountDelta"] == -1,
        "debugMetadata emitted delta",
    )
    expect(
        by_kind["hirSourceMap"]["manifestCountDelta"] == 1,
        "hirSourceMap new manifest record",
    )
    expect(
        by_kind["nativeBinary"]["missingCountDelta"] == 0,
        "unchanged missing nativeBinary remains visible",
    )
    expect(
        payload["policy"]["artifactSize"]["mode"] == "report-only",
        "artifact kind evidence does not change artifact-size policy",
    )

    stale_payload = copy.deepcopy(candidate_payload)
    stale_payload["summary"]["manifestArtifactKindCount"] = 99
    write_report(stale_candidate, stale_payload)
    stale_result = run_tool(root, baseline, stale_candidate)
    expect(stale_result.returncode == 1, stale_result.stderr + stale_result.stdout)
    stale_comparison = json.loads(stale_result.stdout)
    expect(
        stale_comparison["policy"]["structural"]["failureReasons"]
        == ["candidateValidationIssues"],
        "stale artifact kind summary is structural report shape",
    )
    expect(
        stale_comparison["structure"]["validationIssues"]
        == ["candidate.summary.manifestArtifactKindCount=99 does not match cases (4)"],
        "stale artifact kind summary issue text",
    )


def check_comparable_repeated_threshold_evidence(root: Path, tmp: Path) -> None:
    baseline = tmp / "comparable-threshold-baseline.json"
    candidate = tmp / "comparable-threshold-candidate.json"
    case_key = "storage-buffer-compute::directx::release"
    write_report(
        baseline,
        complete_policy_report(
            [
                timed_case(
                    case_key,
                    category="storage-buffers",
                    elapsed_ns=100,
                )
            ]
        ),
    )
    write_report(
        candidate,
        complete_policy_report(
            [
                timed_case(
                    case_key,
                    category="storage-buffers",
                    elapsed_ns=115,
                )
            ]
        ),
    )

    result = run_tool(root, baseline, candidate, "--include-timing-deltas")
    expect(result.returncode == 0, result.stderr + result.stdout)
    payload = json.loads(result.stdout)
    expect(payload["status"] == "pass", "comparable threshold evidence stays pass")
    expect(
        payload["timing"]["advisoryThresholdPolicy"]["metadataCompatible"] is True,
        "matching metadata permits advisory threshold claims",
    )
    expect(
        payload["timing"]["advisoryThresholdPolicy"]["claimEligibleCaseCount"] == 1,
        "comparable repeated samples are claim eligible",
    )
    expect(
        payload["timing"]["advisoryThresholdPolicy"]["claimDispositionCounts"]
        == {"threshold-exceeded": 1},
        "comparable repeated samples count threshold claim disposition",
    )
    advisory_thresholds = payload["timing"]["advisoryThresholds"]
    expect(
        advisory_thresholds["mode"] == "report-only",
        "advisory threshold summary remains report-only",
    )
    expect(
        advisory_thresholds["source"]["kind"] == "builtin",
        "default advisory threshold source is builtin",
    )
    expect(
        advisory_thresholds["policy"]["kind"] == "advisory-threshold-policy",
        "advisory threshold policy kind",
    )
    expect(
        advisory_thresholds["policy"]["name"] == "milestone6",
        "advisory threshold policy name",
    )
    expect(
        advisory_thresholds["classification"]["thresholdExceededCases"] == [case_key],
        "advisory threshold summary carries claimed excess cases",
    )
    expect(
        payload["timing"]["advisoryThresholdPolicy"]["measuredThresholdExceededCases"]
        == [case_key],
        "comparable repeated samples count measured threshold excess",
    )
    trend_readiness = payload["timing"]["thresholdProposalLayer"][
        "repeatedReportTrendReadiness"
    ]
    expect(
        trend_readiness["readyForRepeatedReportTrend"] is True,
        "comparable repeated samples are ready as one trend report pair",
    )
    expect(
        trend_readiness["repeatedReportPairContribution"] == 1,
        "ready pair contributes one repeated report pair",
    )
    expect(
        trend_readiness["remainingRepeatedReportPairsForReleaseClaim"] == 2,
        "ready pair still requires additional repeated reports",
    )
    expect(
        trend_readiness["reasons"] == [],
        "ready repeated-report trend evidence has no blockers",
    )
    trend_requirements = proposal_requirements_by_name(trend_readiness)
    expect(
        all(requirement["satisfied"] for requirement in trend_requirements.values()),
        "ready repeated-report trend requirements are all satisfied",
    )
    expect(
        trend_requirements["timingObservations"]["observed"][
            "timingObservationCaseCount"
        ]
        == 1,
        "ready repeated-report trend records timing observation count",
    )
    expect(
        trend_requirements["stableReportOnlyClassification"]["observed"][
            "currentPolicyDispositionCounts"
        ]
        == {"advisory": 1},
        "ready repeated-report trend records stable advisory classification",
    )
    evidence_sufficiency = payload["timing"]["evidenceSufficiency"]
    expect(
        evidence_sufficiency["claimEligibilityDispositionCounts"]
        == {"claim-eligible": 1},
        "comparable repeated samples are evidence-sufficient",
    )
    expect(
        evidence_sufficiency["advisoryThresholdClaimedExceededCases"] == [case_key],
        "comparable repeated samples produce claimed advisory threshold excess",
    )
    expect(
        evidence_sufficiency["advisoryThresholdMeasuredExceededCases"] == [case_key],
        "comparable repeated samples preserve measured advisory threshold excess",
    )
    expect(
        payload["timing"]["advisoryClaimEligibleCaseCount"] == 1,
        "timing advisory claim eligibility count",
    )
    expect(
        payload["timing"]["advisoryThresholdExceededCount"] == 1,
        "comparable repeated samples produce advisory threshold excess evidence",
    )
    exceeded = payload["timing"]["advisoryThresholdExceededRegressions"][0]
    expect(exceeded["case"] == case_key, "advisory threshold excess case")
    expect(
        exceeded["currentPolicyDisposition"] == "advisory",
        "default advisory threshold excess remains report-only",
    )
    expect(
        exceeded["advisoryThreshold"]["claimEligible"] is True,
        "advisory threshold claim is eligible",
    )
    expect(
        exceeded["advisoryThreshold"]["claimDisposition"] == "threshold-exceeded",
        "advisory threshold claim disposition",
    )
    expect(
        exceeded["advisoryThreshold"]["reportOnlyReason"].startswith(
            "Timing advisory thresholds are report-only"
        ),
        "advisory threshold explains why measured excess is report-only",
    )
    expect(
        exceeded["advisoryThreshold"]["evidence"]["claimEligibilityDisposition"]
        == "claim-eligible",
        "advisory threshold embeds eligible evidence disposition",
    )
    expect(
        exceeded["advisoryThreshold"]["evidence"]["baselineSampleCount"] == 5,
        "eligible advisory threshold embeds baseline sample count",
    )
    expect(
        exceeded["advisoryThreshold"]["evidence"]["candidateSampleCount"] == 5,
        "eligible advisory threshold embeds candidate sample count",
    )
    expect(
        exceeded["advisoryThreshold"]["evidence"]["claimSuppressionReasons"] == [],
        "eligible advisory threshold has no suppression reasons",
    )
    expect(
        exceeded["timingEvidence"]["reasons"] == [],
        "comparable repeated evidence has no claim-suppression reasons",
    )
    expect(
        exceeded["timingEvidence"]["claimEligible"] is True,
        "comparable repeated evidence records claim eligibility",
    )
    expect(
        exceeded["timingEvidence"]["metadata"]["compatible"] is True,
        "timing evidence carries comparable metadata",
    )

    expect(
        exceeded["timingEvidence"]["baseline"]["sampleCount"] == 5,
        "baseline comparison window supplies repeated samples",
    )
    expect(
        exceeded["timingEvidence"]["candidate"]["sampleCount"] == 5,
        "candidate comparison window supplies repeated samples",
    )

    explicit = run_tool(
        root,
        baseline,
        candidate,
        "--max-regression-percent",
        "10",
        "--include-timing-deltas",
    )
    expect(explicit.returncode == 0, explicit.stderr + explicit.stdout)
    explicit_payload = json.loads(explicit.stdout)
    expect(
        explicit_payload["status"] == "pass",
        "explicit advisory threshold excess remains non-blocking",
    )
    expect(
        explicit_payload["policy"]["failureClass"] == "pass",
        "explicit advisory threshold excess does not fail policy",
    )
    expect(
        explicit_payload["timing"]["thresholdExceededCount"] == 1,
        "explicit advisory threshold excess evidence is emitted",
    )
    expect(
        explicit_payload["timing"]["explicitThresholdPolicy"]["claimDispositionCounts"]
        == {"threshold-exceeded": 1},
        "explicit advisory threshold counts claim disposition",
    )
    expect(
        explicit_payload["timing"]["explicitThresholdPolicy"][
            "measuredThresholdExceededCases"
        ]
        == [case_key],
        "explicit advisory threshold preserves measured threshold excess",
    )
    explicit_exceeded = explicit_payload["timing"]["thresholdExceededRegressions"][0]
    expect(
        explicit_exceeded["wouldFailExplicitThresholdIfEnforced"] is True,
        "explicit threshold failure projection is visible",
    )
    expect(
        explicit_exceeded["currentPolicyDisposition"] == "advisory-threshold-exceeded",
        "explicit threshold excess disposition",
    )
    expect(
        explicit_exceeded["explicitThreshold"]["reportOnlyReason"].startswith(
            "Timing advisory thresholds are report-only"
        ),
        "explicit threshold explains report-only disposition",
    )
    check_threshold_enforcement(
        explicit_exceeded["explicitThreshold"]["enforcement"],
        "explicit threshold per-case enforcement",
    )


def check_producer_policy_claim_provenance(root: Path, tmp: Path) -> None:
    baseline = tmp / "producer-claims-baseline.json"
    candidate = tmp / "producer-claims-candidate.json"
    structural_candidate = tmp / "producer-claims-structural-candidate.json"
    case_key = "storage-buffer-compute::directx::release"
    baseline_payload = complete_policy_report(
        [
            timed_case(
                case_key,
                category="storage-buffers",
                elapsed_ns=100,
            )
        ]
    )
    candidate_payload = complete_policy_report(
        [
            timed_case(
                case_key,
                category="storage-buffers",
                elapsed_ns=101,
            )
        ]
    )

    stale_top_level_readiness = producer_threshold_readiness(
        ready=False,
        status="incomplete",
        reasons=["producer-stale-baseline-data"],
    )
    stale_metadata_readiness = producer_threshold_readiness(
        ready=False,
        status="incomplete",
        reasons=["producer-metadata-mirror-drift"],
    )
    add_producer_claims(
        baseline_payload,
        policy=producer_advisory_threshold_policy("baseline-top-level"),
        metadata_policy=producer_advisory_threshold_policy(
            "baseline-metadata", rule_count=1
        ),
        readiness=stale_top_level_readiness,
        metadata_readiness=stale_metadata_readiness,
    )
    ready_candidate_readiness = producer_threshold_readiness(
        ready=True,
        status="ready",
        reasons=[],
    )
    add_producer_claims(
        candidate_payload,
        policy=producer_advisory_threshold_policy("candidate-matching"),
        readiness=ready_candidate_readiness,
    )
    write_report(baseline, baseline_payload)
    write_report(candidate, candidate_payload)

    result = run_tool(root, baseline, candidate)
    expect(result.returncode == 0, result.stderr + result.stdout)
    payload = json.loads(result.stdout)
    expect(
        payload["status"] == "pass",
        "producer claim contradictions do not fail comparison",
    )
    check_report_artifact_contract(payload, "producer claims comparison")
    expect(
        payload["policy"]["failureClass"] == "pass",
        "producer claim contradictions do not set failure class",
    )
    producer_claims = payload["metadata"]["baselinePolicy"]["producerClaims"]
    baseline_claims = producer_claims["baseline"]
    candidate_claims = producer_claims["candidate"]
    expect(
        baseline_claims["mirrorMismatchCount"] == 2,
        "baseline producer claim mirror mismatch count",
    )
    expect(
        baseline_claims["mirrorMismatches"]
        == ["advisoryThresholdPolicy", "thresholdBaselineReadiness"],
        "baseline producer claim mirror mismatch list",
    )
    expect(
        baseline_claims["advisoryThresholdPolicy"]["mirrorStatus"] == "mismatch",
        "producer advisory policy mirror mismatch is visible",
    )
    expect(
        baseline_claims["advisoryThresholdPolicy"]["summary"]["name"]
        == "baseline-top-level",
        "producer advisory policy effective top-level summary",
    )
    expect(
        baseline_claims["advisoryThresholdPolicy"]["metadata"]["name"]
        == "baseline-metadata",
        "producer advisory policy metadata mirror is preserved",
    )
    expect(
        baseline_claims["thresholdBaselineReadiness"]["mirrorStatus"] == "mismatch",
        "producer readiness mirror mismatch is visible",
    )
    expect(
        baseline_claims["thresholdBaselineReadiness"]["summary"][
            "readyForThresholdBaseline"
        ]
        is False,
        "producer stale readiness claim is preserved",
    )
    baseline_reconciliation = baseline_claims["readinessReconciliation"]
    expect(
        baseline_reconciliation["producerReadyForThresholdBaseline"] is False,
        "producer readiness claim remains visible",
    )
    expect(
        baseline_reconciliation["comparatorReadyForThresholdBaseline"] is True,
        "comparator recomputed readiness remains visible",
    )
    expect(
        baseline_reconciliation["status"] == "producer-differs-from-comparator",
        "producer/comparator readiness disagreement is explicit",
    )
    expect(
        candidate_claims["mirrorMismatchCount"] == 0,
        "candidate producer mirrors match",
    )
    expect(
        candidate_claims["readinessReconciliation"]["status"]
        == "producer-matches-comparator",
        "matching producer readiness is explicit",
    )
    summary = producer_claims["summary"]
    expect(
        summary["mirrorMismatchCount"] == 2,
        "producer claim pair summary counts mirror mismatches",
    )
    expect(
        summary["readinessMismatchCount"] == 1
        and summary["readinessMismatches"] == ["baseline"],
        "producer claim pair summary counts readiness mismatches",
    )
    expect(
        summary["reportsWithProducerAdvisoryThresholdPolicy"]
        == ["baseline", "candidate"],
        "producer claim summary lists policy-bearing reports",
    )
    expect(
        summary["reportsWithProducerThresholdBaselineReadiness"]
        == ["baseline", "candidate"],
        "producer claim summary lists readiness-bearing reports",
    )
    expect(
        summary["producerReadyPairClaim"] is False,
        "producer ready pair claim reflects producer declarations",
    )
    expect(
        summary["comparatorCompatibleReadyPair"] is True,
        "recomputed compatible ready pair remains separate",
    )
    expect(
        payload["metadata"]["baselinePolicy"]["readiness"]["compatibleReadyPair"]
        is True,
        "producer claims do not override recomputed pair readiness",
    )

    structural_payload = complete_policy_report([])
    add_producer_claims(
        structural_payload,
        policy=producer_advisory_threshold_policy("structural-ready-claim"),
        readiness=producer_threshold_readiness(
            ready=True,
            status="ready",
            reasons=[],
        ),
    )
    write_report(structural_candidate, structural_payload)
    structural_result = run_tool(root, baseline, structural_candidate)
    expect(
        structural_result.returncode == 1,
        structural_result.stderr + structural_result.stdout,
    )
    structural_payload = json.loads(structural_result.stdout)
    expect(
        structural_payload["status"] == "fail",
        "producer ready claim does not hide structural failure",
    )
    expect(
        structural_payload["policy"]["failureClass"] == "structural",
        "structural shape still controls comparator failure class",
    )


def check_advisory_window_fixture_non_regression(root: Path) -> None:
    result = run_tool(
        root,
        ADVISORY_WINDOW_BASELINE,
        ADVISORY_WINDOW_CANDIDATE,
        "--include-timing-deltas",
    )
    expect(result.returncode == 0, result.stderr + result.stdout)
    payload = json.loads(result.stdout)
    expect(payload["status"] == "pass", "advisory window fixture stays passing")
    expect(
        payload["policy"]["structural"]["failed"] is False,
        "advisory window fixture has no structural failure",
    )
    expect(
        payload["policy"]["timing"]["mode"] == "report-only",
        "advisory window fixture keeps timing report-only",
    )
    expect(
        payload["timing"]["advisoryThresholdPolicy"]["metadataCompatible"] is True,
        "advisory window fixture has comparable baseline metadata",
    )
    expect(
        payload["timing"]["advisoryThresholdPolicy"]["claimEligibleCaseCount"] == 3,
        "advisory window fixture samples are threshold claim eligible",
    )
    expect(
        payload["timing"]["advisoryThresholdPolicy"]["claimDispositionCounts"]
        == {"within-threshold": 3},
        "advisory window fixture records within-threshold dispositions",
    )
    expect(
        payload["timing"]["advisoryThresholdExceededCount"] == 0,
        "advisory window fixture has no advisory threshold excess",
    )
    evidence = payload["timing"]["evidenceSufficiency"]
    expect(
        evidence["claimEligibilityDispositionCounts"] == {"claim-eligible": 3},
        "advisory window fixture has repeated evidence",
    )
    expect(
        evidence["currentPolicyDispositionCounts"]
        == {"advisory": 1, "non-regression": 2},
        "advisory window fixture exposes non-regression classifications",
    )
    deltas_by_case = {
        entry["case"]: entry for entry in payload["timing"]["timingDeltas"]
    }
    expect(
        deltas_by_case["debug-control::directx::debug"]["changeKind"] == "unchanged",
        "advisory window fixture unchanged case is explicit",
    )
    expect(
        deltas_by_case["debug-control::directx::debug"]["currentPolicyDisposition"]
        == "non-regression",
        "advisory window fixture unchanged case is non-regression",
    )
    expect(
        deltas_by_case["texture-sample::opengl::release"]["changeKind"]
        == "improvement",
        "advisory window fixture improvement case is explicit",
    )
    expect(
        deltas_by_case["texture-sample::opengl::release"]["currentPolicyDisposition"]
        == "non-regression",
        "advisory window fixture improvement case is non-regression",
    )
    storage_delta = deltas_by_case["storage-buffer-compute::directx::release"]
    expect(
        storage_delta["changeKind"] == "regression",
        "advisory window fixture includes a small regression observation",
    )
    expect(
        storage_delta["advisoryThreshold"]["claimDisposition"] == "within-threshold",
        "advisory window fixture small regression stays within advisory threshold",
    )
    expect(
        storage_delta["advisoryThreshold"]["evidence"]["baselineSampleCount"] == 3,
        "advisory window fixture embeds baseline sample count",
    )
    expect(
        storage_delta["advisoryThreshold"]["evidence"]["candidateSampleCount"] == 3,
        "advisory window fixture embeds candidate sample count",
    )


def check_custom_advisory_threshold_policy(root: Path, tmp: Path) -> None:
    baseline = tmp / "custom-policy-baseline.json"
    candidate = tmp / "custom-policy-candidate.json"
    policy = CUSTOM_ADVISORY_THRESHOLD_POLICY
    generated_policy = tmp / "generated-advisory-threshold-policy.json"
    default_policy = tmp / "default-advisory-threshold-policy.json"
    case_key = "storage-buffer-compute::directx::release"

    write_report(
        baseline,
        complete_policy_report(
            [
                timed_case(
                    case_key,
                    category="storage-buffers",
                    elapsed_ns=100,
                )
            ]
        ),
    )
    write_report(
        candidate,
        complete_policy_report(
            [
                timed_case(
                    case_key,
                    category="storage-buffers",
                    elapsed_ns=111,
                )
            ]
        ),
    )

    generate_only = run_comparator(
        root,
        "--write-advisory-threshold-policy",
        str(default_policy),
    )
    expect(generate_only.returncode == 0, generate_only.stderr + generate_only.stdout)
    expect(generate_only.stdout == "", "policy generation has no comparison stdout")
    generated_default_payload = json.loads(default_policy.read_text(encoding="utf-8"))
    expect(
        generated_default_payload["kind"] == "advisory-threshold-policy",
        "generated policy kind",
    )
    expect(
        generated_default_payload["mode"] == "report-only",
        "generated policy mode",
    )
    check_threshold_enforcement(
        generated_default_payload["enforcement"],
        "generated policy enforcement",
    )
    expect(
        generated_default_payload["name"] == "milestone6",
        "generated default policy name",
    )
    expect(
        generated_default_payload["ruleCount"] == 8,
        "generated default policy rule count",
    )
    expect(
        generated_default_payload["rules"][0]["ruleSpecificity"] == "category-profile",
        "generated default policy marks exact category/profile rules",
    )
    expect(
        generated_default_payload["rules"][6]["ruleSpecificity"] == "profile-only",
        "generated default policy marks profile wildcard rules",
    )
    expect(
        generated_default_payload["rules"][7]["ruleSpecificity"] == "fallback",
        "generated default policy marks global fallback rules",
    )
    expect(
        generated_default_payload
        == json.loads(GENERATED_ADVISORY_THRESHOLD_POLICY.read_text(encoding="utf-8")),
        "generated default policy matches checked-in fixture",
    )

    fixture_result = run_tool(
        root,
        ADVISORY_BASELINE,
        ADVISORY_CANDIDATE,
        "--advisory-threshold-policy",
        str(policy),
        "--include-timing-deltas",
    )
    expect(
        fixture_result.returncode == 0,
        fixture_result.stderr + fixture_result.stdout,
    )
    fixture_payload = json.loads(fixture_result.stdout)
    expect(
        fixture_payload["status"] == "pass",
        "checked-in policy fixture keeps timing report-only",
    )
    expect(
        fixture_payload["policy"]["failureClass"] == "pass",
        "checked-in policy fixture does not create a timing failure class",
    )
    fixture_thresholds = fixture_payload["timing"]["advisoryThresholds"]
    expect(
        fixture_thresholds["mode"] == "report-only",
        "checked-in policy fixture emits report-only threshold summary",
    )
    expect(
        fixture_thresholds["source"]["kind"] == "file",
        "checked-in policy fixture source is file",
    )
    expect(
        fixture_thresholds["source"]["name"] == "fixture-tight-storage-release",
        "checked-in policy fixture source name",
    )
    expect(
        fixture_thresholds["policy"]["mode"] == "report-only",
        "checked-in policy fixture embedded mode",
    )
    check_threshold_enforcement(
        fixture_thresholds["policy"]["enforcement"],
        "checked-in policy fixture embedded enforcement",
    )
    expect(
        fixture_thresholds["classification"]["matchedCaseCount"] == 1,
        "checked-in policy fixture match count",
    )
    expect(
        fixture_thresholds["classification"]["unmatchedCaseCount"] == 2,
        "checked-in policy fixture unmatched count",
    )
    expect(
        fixture_thresholds["classification"]["measuredThresholdExceededCases"]
        == [case_key],
        "checked-in policy fixture measured threshold excess",
    )
    expect(
        fixture_thresholds["classification"]["thresholdExceededCases"] == [],
        "metadata drift withholds checked-in policy threshold claim",
    )
    fixture_delta = {
        entry["case"]: entry for entry in fixture_payload["timing"]["timingDeltas"]
    }[case_key]
    expect(
        fixture_delta["advisoryThreshold"]["label"] == "fixture storage release lane",
        "checked-in policy fixture per-case label",
    )
    expect(
        fixture_delta["advisoryThreshold"]["claimDisposition"]
        == "incomparable-metadata",
        "checked-in policy fixture reports claim suppression",
    )
    expect(
        fixture_delta["measuredExceedsAdvisoryThreshold"] is True,
        "checked-in policy fixture preserves measured excess",
    )
    expect(
        fixture_delta["exceedsAdvisoryThreshold"] is False,
        "checked-in policy fixture keeps claim non-failing",
    )

    result = run_tool(
        root,
        baseline,
        candidate,
        "--advisory-threshold-policy",
        str(policy),
        "--write-advisory-threshold-policy",
        str(generated_policy),
        "--include-timing-deltas",
    )
    expect(result.returncode == 0, result.stderr + result.stdout)
    payload = json.loads(result.stdout)
    expect(payload["status"] == "pass", "custom advisory policy stays report-only")
    expect(
        payload["policy"]["failureClass"] == "pass",
        "custom advisory policy does not create timing failure class",
    )
    expect(
        payload["timing"]["advisoryThresholdExceededCount"] == 1,
        "custom advisory policy records threshold claim",
    )
    advisory_thresholds = payload["timing"]["advisoryThresholds"]
    expect(
        advisory_thresholds["source"]["kind"] == "file",
        "custom policy source is file",
    )
    expect(
        advisory_thresholds["source"]["name"] == "fixture-tight-storage-release",
        "custom policy source carries name",
    )
    expect(
        advisory_thresholds["policy"]["name"] == "fixture-tight-storage-release",
        "custom policy metadata is embedded",
    )
    expect(
        advisory_thresholds["policy"]["ruleCount"] == 1,
        "custom policy rule count",
    )
    expect(
        advisory_thresholds["policy"]["evidencePolicy"]["minimumSampleCount"] == 2,
        "custom policy evidence minimum sample count is embedded",
    )
    expect(
        advisory_thresholds["policy"]["failurePolicy"]
        == "report-only; advisory timing threshold observations never change "
        "comparator exit status",
        "custom policy failure policy is embedded",
    )
    expect(
        advisory_thresholds["policy"]["releaseBlockerPolicy"]
        == "Timing advisory thresholds are report-only and are not release blockers "
        "without explicit owner approval.",
        "custom policy release-blocker policy is embedded",
    )
    check_threshold_enforcement(
        advisory_thresholds["policy"]["enforcement"],
        "custom policy normalized enforcement",
    )
    expect(
        advisory_thresholds["classification"]["thresholdExceededCases"] == [case_key],
        "custom policy claimed threshold excess cases",
    )
    expect(
        advisory_thresholds["classification"]["measuredThresholdExceededCases"]
        == [case_key],
        "custom policy measured threshold excess cases",
    )
    delta = payload["timing"]["timingDeltas"][0]
    expect(
        delta["advisoryThreshold"]["label"] == "fixture storage release lane",
        "custom policy per-case threshold label",
    )
    expect(
        delta["advisoryThreshold"]["maxRegressionPercent"] == 10,
        "custom policy per-case threshold percentage",
    )
    expect(
        delta["currentPolicyDisposition"] == "advisory",
        "custom advisory profile does not harden timing disposition",
    )
    expect(
        json.loads(generated_policy.read_text(encoding="utf-8"))["name"]
        == "fixture-tight-storage-release",
        "custom policy can be normalized back to JSON",
    )


def check_target_backend_advisory_threshold_policy(root: Path, tmp: Path) -> None:
    baseline = tmp / "target-backend-policy-baseline.json"
    candidate = tmp / "target-backend-policy-candidate.json"
    policy_path = tmp / "target-backend-advisory-threshold-policy.json"
    directx_case = "storage-directx::directx::release"
    spirv_case = "storage-spirv::vulkan::release"
    opengl_case = "storage-opengl::opengl::release"

    write_report(
        baseline,
        complete_policy_report(
            [
                timed_case(
                    directx_case,
                    category="storage-buffers",
                    elapsed_ns=100,
                    target="directx",
                ),
                timed_case(
                    spirv_case,
                    backend="spirv",
                    category="storage-buffers",
                    elapsed_ns=100,
                    target="vulkan",
                ),
                timed_case(
                    opengl_case,
                    category="storage-buffers",
                    elapsed_ns=100,
                    target="opengl",
                ),
            ]
        ),
    )
    write_report(
        candidate,
        complete_policy_report(
            [
                timed_case(
                    directx_case,
                    category="storage-buffers",
                    elapsed_ns=111,
                    target="directx",
                ),
                timed_case(
                    spirv_case,
                    backend="spirv",
                    category="storage-buffers",
                    elapsed_ns=109,
                    target="vulkan",
                ),
                timed_case(
                    opengl_case,
                    category="storage-buffers",
                    elapsed_ns=111,
                    target="opengl",
                ),
            ]
        ),
    )

    policy_payload = json.loads(
        GENERATED_ADVISORY_THRESHOLD_POLICY.read_text(encoding="utf-8")
    )
    policy_payload.update(
        {
            "description": "Synthetic target/backend-aware advisory threshold policy.",
            "name": "fixture-target-backend-aware",
            "ruleCount": 5,
            "rules": [
                {
                    "category": "storage-buffers",
                    "label": "directx storage release lane",
                    "maxRegressionPercent": "10",
                    "profile": "release",
                    "ruleSpecificity": "category-profile-target",
                    "target": "directx",
                },
                {
                    "backend": "spirv",
                    "category": "storage-buffers",
                    "label": "spirv storage release lane",
                    "maxRegressionPercent": "8",
                    "profile": "release",
                    "ruleSpecificity": "category-profile-backend",
                },
                {
                    "category": "storage-buffers",
                    "label": "unmatched metal storage release lane",
                    "maxRegressionPercent": "5",
                    "profile": "release",
                    "ruleSpecificity": "category-profile-target",
                    "target": "metal",
                },
                {
                    "backend": "msl",
                    "category": "storage-buffers",
                    "label": "unmatched msl storage release lane",
                    "maxRegressionPercent": "5",
                    "profile": "release",
                    "ruleSpecificity": "category-profile-backend",
                },
                {
                    "category": "storage-buffers",
                    "label": "storage release global fallback",
                    "maxRegressionPercent": "20",
                    "profile": "release",
                    "ruleSpecificity": "category-profile",
                },
            ],
        }
    )
    write_report(policy_path, policy_payload)

    result = run_tool(
        root,
        baseline,
        candidate,
        "--advisory-threshold-policy",
        str(policy_path),
        "--include-timing-deltas",
    )
    expect(result.returncode == 0, result.stderr + result.stdout)
    payload = json.loads(result.stdout)
    expect(payload["status"] == "pass", "target/backend thresholds stay report-only")
    expect(
        payload["timing"]["advisoryThresholdExceededCount"] == 2,
        "target/backend overrides can produce advisory threshold claims",
    )
    expect(
        payload["timing"]["advisoryThresholdPolicy"]["claimDispositionCounts"]
        == {"threshold-exceeded": 2, "within-threshold": 1},
        "selected target/backend/global thresholds are classified",
    )
    expect(
        payload["timing"]["advisoryThresholdPolicy"]["ruleSpecificityCounts"]
        == {
            "category-profile": 1,
            "category-profile-backend": 1,
            "category-profile-target": 1,
        },
        "target/backend/global selectors contribute specificity counts",
    )
    expect(
        payload["timing"]["advisoryThresholds"]["classification"][
            "thresholdExceededCases"
        ]
        == [directx_case, spirv_case],
        "threshold summary reports cases exceeding selected rules",
    )

    emitted_rules = payload["timing"]["advisoryThresholds"]["policy"]["rules"]
    expect(
        emitted_rules[0]["target"] == "directx" and "backend" not in emitted_rules[0],
        "target-specific rule serializes target selector only",
    )
    expect(
        emitted_rules[1]["backend"] == "spirv" and "target" not in emitted_rules[1],
        "backend-specific rule serializes backend selector only",
    )
    expect(
        "target" not in emitted_rules[4] and "backend" not in emitted_rules[4],
        "old/global fallback rule omits target/backend selectors",
    )

    deltas_by_case = {
        entry["case"]: entry for entry in payload["timing"]["timingDeltas"]
    }
    directx_delta = deltas_by_case[directx_case]
    expect(
        directx_delta["advisoryThreshold"]["label"] == "directx storage release lane",
        "target-specific threshold overrides global fallback",
    )
    expect(
        directx_delta["advisoryThreshold"]["maxRegressionPercent"] == 10,
        "target-specific threshold percent",
    )
    expect(
        directx_delta["advisoryThreshold"]["ruleMatch"]["ruleTarget"] == "directx",
        "target-specific rule match records selected target",
    )
    expect(
        directx_delta["advisoryThreshold"]["ruleMatch"]["targetMatch"] == "exact",
        "target-specific rule match records exact target match",
    )
    directx_diagnostic = directx_delta["advisoryThreshold"]["diagnostic"]
    for snippet in (
        "exceeded selected advisory threshold",
        "directx storage release lane",
        "target=directx",
        "backend=directx",
        "allowedNs=110",
        "thresholdExcessNs=1",
    ):
        expect(
            snippet in directx_diagnostic,
            f"target-specific threshold diagnostic includes {snippet}",
        )

    spirv_delta = deltas_by_case[spirv_case]
    expect(
        spirv_delta["advisoryThreshold"]["label"] == "spirv storage release lane",
        "backend-specific threshold overrides global fallback",
    )
    expect(
        spirv_delta["advisoryThreshold"]["caseBackend"] == "spirv",
        "backend-specific threshold records case backend",
    )
    expect(
        spirv_delta["advisoryThreshold"]["ruleMatch"]["caseBackend"] == "spirv",
        "backend-specific rule match records case backend",
    )
    expect(
        spirv_delta["advisoryThreshold"]["ruleMatch"]["ruleBackend"] == "spirv",
        "backend-specific rule match records selected backend",
    )
    expect(
        spirv_delta["advisoryThreshold"]["ruleMatch"]["backendMatch"] == "exact",
        "backend-specific rule match records exact backend match",
    )
    expect(
        spirv_delta["advisoryThreshold"]["thresholdExcessNs"] == 1,
        "backend-specific threshold excess is measured against selected rule",
    )
    spirv_diagnostic = spirv_delta["advisoryThreshold"]["diagnostic"]
    for snippet in (
        "exceeded selected advisory threshold",
        "spirv storage release lane",
        "target=vulkan",
        "backend=spirv",
        "allowedNs=108",
        "thresholdExcessNs=1",
    ):
        expect(
            snippet in spirv_diagnostic,
            f"backend-specific threshold diagnostic includes {snippet}",
        )

    opengl_delta = deltas_by_case[opengl_case]
    expect(
        opengl_delta["advisoryThreshold"]["label"] == "storage release global fallback",
        "unmatched target/backend selectors fall back to old global rule",
    )
    expect(
        opengl_delta["advisoryThreshold"]["maxRegressionPercent"] == 20,
        "global fallback threshold percent",
    )
    expect(
        opengl_delta["advisoryThreshold"]["claimDisposition"] == "within-threshold",
        "global fallback keeps smaller regression within threshold",
    )
    expect(
        "ruleTarget" not in opengl_delta["advisoryThreshold"]["ruleMatch"]
        and "ruleBackend" not in opengl_delta["advisoryThreshold"]["ruleMatch"],
        "old/global rule match keeps legacy selector evidence shape",
    )


def check_measurement_window_sample_evidence(root: Path, tmp: Path) -> None:
    baseline = tmp / "measurement-window-baseline.json"
    candidate = tmp / "measurement-window-candidate.json"
    case_key = "storage-buffer-compute::directx::release"
    baseline_payload = complete_policy_report(
        [
            timed_case(
                case_key,
                category="storage-buffers",
                elapsed_ns=100,
            )
        ]
    )
    candidate_payload = complete_policy_report(
        [
            timed_case(
                case_key,
                category="storage-buffers",
                elapsed_ns=120,
            )
        ]
    )
    for payload in (baseline_payload, candidate_payload):
        payload["baselinePolicy"]["comparisonWindow"]["sampleCount"] = 99
        measurement_window = {
            "sampleCount": 3,
            "unit": "elapsedNs",
            "warmupCount": 2,
        }
        payload.setdefault("metadata", {})["measurementWindow"] = measurement_window
        payload["summary"]["measurementWindow"] = measurement_window
    write_report(baseline, baseline_payload)
    write_report(candidate, candidate_payload)

    result = run_tool(root, baseline, candidate, "--include-timing-deltas")
    expect(result.returncode == 0, result.stderr + result.stdout)
    payload = json.loads(result.stdout)
    evidence = payload["timing"]["timingDeltas"][0]["timingEvidence"]
    expect(
        evidence["baseline"]["sampleCount"] == 3,
        "measurement window supplies baseline sample count",
    )
    expect(
        evidence["baseline"]["sampleSource"]
        == "metadata.measurementWindow.sampleCount",
        "measurement window sample source precedes comparison policy",
    )
    expect(
        evidence["candidate"]["sampleCount"] == 3,
        "measurement window supplies candidate sample count",
    )
    expect(
        payload["timing"]["advisoryThresholdExceededCount"] == 1,
        "measurement-window repeated evidence permits advisory threshold claim",
    )


def check_partial_case_identity_withholds_threshold_claim(
    root: Path, tmp: Path
) -> None:
    baseline = tmp / "partial-identity-baseline.json"
    candidate = tmp / "partial-identity-candidate.json"
    case_key = "storage-buffer-compute::directx::release"
    baseline_payload = complete_policy_report(
        [
            timed_case(
                case_key,
                category="storage-buffers",
                elapsed_ns=100,
            )
        ]
    )
    candidate_payload = complete_policy_report(
        [
            timed_case(
                case_key,
                category="storage-buffers",
                elapsed_ns=130,
            )
        ]
    )
    for payload in (baseline_payload, candidate_payload):
        del payload["cases"][0]["fixtureName"]
        del payload["cases"][0]["optLevel"]
        payload["summary"]["optLevels"] = []
        payload["summary"]["caseCountByOptLevel"] = {}
    write_report(baseline, baseline_payload)
    write_report(candidate, candidate_payload)

    result = run_tool(
        root,
        baseline,
        candidate,
        "--max-regression-percent",
        "10",
        "--include-timing-deltas",
    )
    expect(result.returncode == 0, result.stderr + result.stdout)
    payload = json.loads(result.stdout)
    expect(payload["status"] == "pass", "partial case identity remains report-only")
    expect(
        payload["policy"]["failureClass"] == "pass",
        "partial case identity does not harden timing",
    )
    expect(
        payload["structure"]["validationIssueCount"] == 0,
        "partial case identity is not a structural validation issue",
    )
    readiness = payload["metadata"]["baselinePolicy"]["readiness"]
    expect(
        readiness["compatibleReadyPair"] is False,
        "partial identity reports are not a compatible ready pair",
    )
    for side in ("baseline", "candidate"):
        side_readiness = readiness[side]
        expect(
            side_readiness["readyForThresholdBaseline"] is False,
            f"partial identity {side} is not threshold-baseline ready",
        )
        expect(
            side_readiness["reasons"] == ["missingTimedCaseIdentityFields"],
            f"partial identity {side} readiness reason",
        )
        expect(
            side_readiness["unsatisfiedThresholdBaselineRequirements"]
            == ["explicitTimedCaseIdentity"],
            f"partial identity {side} requirement name",
        )
        requirement = requirements_by_name(side_readiness)["explicitTimedCaseIdentity"]
        expect(
            requirement["observed"]["incompleteCases"] == [case_key],
            f"partial identity {side} incomplete case list",
        )
        identity = side_readiness["timedCaseIdentity"]
        expect(
            identity["incompleteCases"] == [case_key],
            f"partial identity {side} readiness evidence list",
        )
        expect(
            identity["caseEvidence"][0]["missingFields"] == ["fixtureName", "optLevel"],
            f"partial identity {side} missing fields",
        )

    expect(
        payload["timing"]["thresholdExceededCount"] == 0,
        "partial identity withholds explicit threshold claim",
    )
    expect(
        payload["timing"]["advisoryThresholdExceededCount"] == 0,
        "partial identity withholds advisory threshold claim",
    )
    expect(
        payload["timing"]["evidenceSufficiency"]["caseIdentityIncompleteCases"]
        == [case_key],
        "timing sufficiency lists partial identity case",
    )
    expect(
        payload["timing"]["explicitThresholdPolicy"]["claimDispositionCounts"]
        == {"incomplete-case-identity": 1},
        "explicit threshold policy counts partial identity disposition",
    )
    expect(
        payload["timing"]["advisoryThresholdPolicy"]["claimDispositionCounts"]
        == {"incomplete-case-identity": 1},
        "advisory threshold policy counts partial identity disposition",
    )
    delta = payload["timing"]["timingDeltas"][0]
    expect(
        delta["measuredExceedsExplicitThreshold"] is True,
        "partial identity still reports measured explicit excess",
    )
    expect(
        delta["measuredExceedsAdvisoryThreshold"] is True,
        "partial identity still reports measured advisory excess",
    )
    expect(
        delta["exceedsExplicitThreshold"] is False,
        "partial identity suppresses explicit threshold claim",
    )
    expect(
        delta["exceedsAdvisoryThreshold"] is False,
        "partial identity suppresses advisory threshold claim",
    )
    expect(
        delta["currentPolicyDisposition"]
        == "advisory-threshold-incomplete-case-identity",
        "partial identity threshold disposition",
    )
    evidence = delta["timingEvidence"]
    expect(
        evidence["caseIdentityComplete"] is False,
        "timing evidence records incomplete case identity",
    )
    expect(
        evidence["caseIdentity"]["reasons"]
        == [
            "baseline:missingCaseIdentityFields",
            "candidate:missingCaseIdentityFields",
        ],
        "timing evidence names identity suppression reasons",
    )
    expect(
        evidence["claimEligibilityDisposition"] == "incomplete-case-identity",
        "timing evidence identity disposition",
    )


def check_timing_window_validation_failure(root: Path, tmp: Path) -> None:
    baseline = tmp / "timing-window-baseline.json"
    candidate = tmp / "timing-window-candidate.json"
    case_key = "storage-buffer-compute::directx::release"
    baseline_payload = complete_policy_report(
        [
            timed_case_with_runs(
                case_key,
                category="storage-buffers",
                elapsed_ns=100,
            )
        ]
    )
    candidate_payload = complete_policy_report(
        [
            timed_case_with_runs(
                case_key,
                category="storage-buffers",
                elapsed_ns=100,
            )
        ]
    )
    add_measurement_window(baseline_payload, sample_count=3, warmup_count=2)
    add_measurement_window(candidate_payload, sample_count=3, warmup_count=2)
    candidate_payload["summary"]["timingWindow"]["measuredRunCount"] = 2
    write_report(baseline, baseline_payload)
    write_report(candidate, candidate_payload)

    result = run_tool(root, baseline, candidate)
    expect(result.returncode == 1, result.stderr + result.stdout)
    payload = json.loads(result.stdout)
    expect(payload["status"] == "fail", "bad timing-window accounting should fail")
    expect(
        payload["policy"]["structural"]["failureReasons"]
        == ["candidateValidationIssues"],
        "timing-window validation is structural report shape",
    )
    expect(
        payload["structure"]["validationIssues"]
        == [
            "candidate.summary.timingWindow.measuredRunCount=2 does not match cases (3)"
        ],
        "timing-window accounting issue text",
    )


def check_measurement_window_validation_failure(root: Path, tmp: Path) -> None:
    baseline = tmp / "measurement-window-valid-baseline.json"
    candidate = tmp / "measurement-window-invalid-candidate.json"
    case_key = "storage-buffer-compute::directx::release"
    baseline_payload = complete_policy_report(
        [
            timed_case_with_runs(
                case_key,
                category="storage-buffers",
                elapsed_ns=100,
            )
        ]
    )
    candidate_payload = complete_policy_report(
        [
            timed_case_with_runs(
                case_key,
                category="storage-buffers",
                elapsed_ns=100,
            )
        ]
    )
    add_measurement_window(baseline_payload, sample_count=3, warmup_count=2)
    add_measurement_window(candidate_payload, sample_count=3, warmup_count=2)
    candidate_payload["summary"]["measurementWindow"] = {
        "sampleCount": 2,
        "unit": "elapsedNs",
        "warmupCount": 2,
    }
    write_report(baseline, baseline_payload)
    write_report(candidate, candidate_payload)

    result = run_tool(root, baseline, candidate)
    expect(result.returncode == 1, result.stderr + result.stdout)
    payload = json.loads(result.stdout)
    issues = payload["structure"]["validationIssues"]
    expect(
        "candidate.summary.measurementWindow={'sampleCount': 2, "
        "'warmupCount': 2, 'unit': 'elapsedNs'} does not match "
        "metadata.measurementWindow ({'sampleCount': 3, 'warmupCount': 2, "
        "'unit': 'elapsedNs'})" in issues,
        "summary measurement window mismatch is structural",
    )
    expect(
        "candidate.cases[0].timing.sampleCount=3 does not match "
        "measurementWindow.sampleCount (2)" in issues,
        "case timing sample count mismatch is structural",
    )


def check_timing_run_evidence_validation_failure(root: Path, tmp: Path) -> None:
    baseline = tmp / "timing-run-valid-baseline.json"
    candidate = tmp / "timing-run-invalid-candidate.json"
    case_key = "storage-buffer-compute::directx::release"
    baseline_payload = complete_policy_report(
        [
            timed_case_with_runs(
                case_key,
                category="storage-buffers",
                elapsed_ns=100,
            )
        ]
    )
    candidate_payload = complete_policy_report(
        [
            timed_case_with_runs(
                case_key,
                category="storage-buffers",
                elapsed_ns=100,
            )
        ]
    )
    candidate_payload["cases"][0]["timing"]["sampleCount"] = 4
    candidate_payload["cases"][0]["timing"]["elapsedNs"] = 999
    write_report(baseline, baseline_payload)
    write_report(candidate, candidate_payload)

    result = run_tool(root, baseline, candidate)
    expect(result.returncode == 1, result.stderr + result.stdout)
    payload = json.loads(result.stdout)
    expect(payload["status"] == "fail", "bad timing-run evidence should fail")
    expect(
        payload["policy"]["structural"]["failureReasons"]
        == ["candidateValidationIssues"],
        "timing-run validation is structural report shape",
    )
    expect(
        payload["structure"]["validationIssues"]
        == [
            "candidate.cases[0].timing.sampleCount=4 does not match runs length (3)",
            "candidate.cases[0].timing.elapsedNs=999 does not match median run "
            "duration (100)",
        ],
        "timing-run validation issue text",
    )
    expect(
        payload["policy"]["timing"]["failed"] is False,
        "timing-run evidence failure does not harden timing thresholds",
    )


def check_skipped_tool_accounting_validation_failure(root: Path, tmp: Path) -> None:
    baseline = tmp / "skipped-accounting-baseline.json"
    candidate = tmp / "skipped-accounting-candidate.json"
    skipped_case = timed_case(
        "storage-buffer-compute::directx::release",
        category="storage-buffers",
        elapsed_ns=100,
    )
    skipped_case["skipped"] = True
    skipped_case["skipReason"] = "cglc-unavailable"
    skipped_case["status"] = "skipped"
    skipped_case["success"] = None
    skipped_case["timing"] = None
    skipped_case["unavailableTools"] = ["cglc"]
    payload = complete_policy_report([skipped_case])
    payload["toolAvailability"]["cglc"]["available"] = False
    payload["toolAvailability"]["cglc"]["status"] = "unavailable"
    write_report(baseline, payload)

    incomplete = json.loads(json.dumps(payload))
    del incomplete["summary"]["skippedToolCasesByTool"]
    write_report(candidate, incomplete)

    result = run_tool(root, baseline, candidate)
    expect(result.returncode == 1, result.stderr + result.stdout)
    comparison = json.loads(result.stdout)
    expect(comparison["status"] == "fail", "missing skipped accounting should fail")
    expect(
        comparison["policy"]["structural"]["failureReasons"]
        == ["candidateValidationIssues"],
        "skipped accounting validation is structural",
    )
    expect(
        comparison["structure"]["validationIssues"]
        == [
            "candidate.summary.skippedToolCasesByTool is required when cases are skipped"
        ],
        "skipped accounting missing-field diagnostic",
    )
    expect(
        comparison["policy"]["timing"]["mode"] == "report-only",
        "skipped accounting failure does not harden timing",
    )

    inconsistent = json.loads(json.dumps(payload))
    inconsistent["summary"]["skippedToolCaseCountByTool"] = {"cglc": 2}
    inconsistent["summary"]["skippedToolCasesByTool"] = {"cglc": []}
    write_report(candidate, inconsistent)

    inconsistent_result = run_tool(root, baseline, candidate)
    expect(
        inconsistent_result.returncode == 1,
        inconsistent_result.stderr + inconsistent_result.stdout,
    )
    inconsistent_comparison = json.loads(inconsistent_result.stdout)
    expect(
        inconsistent_comparison["status"] == "fail",
        "inconsistent skipped accounting should fail",
    )
    expect(
        inconsistent_comparison["policy"]["structural"]["failureReasons"]
        == ["candidateValidationIssues"],
        "inconsistent skipped accounting is structural",
    )
    expect(
        inconsistent_comparison["structure"]["validationIssues"]
        == [
            "candidate.summary.skippedToolCaseCountByTool={'cglc': 2} "
            "does not match cases ({'cglc': 1})",
            "candidate.summary.skippedToolCasesByTool={'cglc': []} does not "
            "match cases ({'cglc': ['storage-buffer-compute::directx::release']})",
        ],
        "inconsistent skipped accounting diagnostics",
    )
    expect(
        inconsistent_comparison["policy"]["timing"]["failed"] is False,
        "inconsistent skipped accounting does not harden timing",
    )


def check_missing_context_metadata_advisory_probe(root: Path, tmp: Path) -> None:
    baseline = tmp / "missing-context-baseline.json"
    candidate = tmp / "missing-context-candidate.json"
    case_key = "storage-buffer-compute::directx::release"
    baseline_payload = report(
        [
            timed_case_with_runs(
                case_key,
                category="storage-buffers",
                elapsed_ns=100,
            )
        ]
    )
    candidate_payload = report(
        [
            timed_case_with_runs(
                case_key,
                category="storage-buffers",
                elapsed_ns=125,
            )
        ]
    )
    add_measurement_window(baseline_payload, sample_count=3, warmup_count=2)
    add_measurement_window(candidate_payload, sample_count=3, warmup_count=2)
    write_report(baseline, baseline_payload)
    write_report(candidate, candidate_payload)

    result = run_tool(
        root,
        baseline,
        candidate,
        "--max-regression-percent",
        "1",
        "--include-timing-deltas",
    )
    expect(result.returncode == 0, result.stderr + result.stdout)
    payload = json.loads(result.stdout)
    expect(payload["status"] == "pass", "missing context metadata is advisory")
    expect(
        payload["policy"]["failureClass"] == "pass",
        "missing context metadata does not create a hard failure",
    )
    expect(
        payload["structure"]["validationIssueCount"] == 0,
        "missing context metadata is not a shape validation issue",
    )
    expect(
        payload["policy"]["timing"]["mode"] == "report-only",
        "missing context timing policy remains report-only",
    )
    expect(
        payload["policy"]["timing"]["failed"] is False,
        "missing context metadata does not harden timing",
    )
    policy_thresholds = payload["policy"]["timing"]["advisoryThresholds"]
    expect(
        policy_thresholds["baselineMissingFields"] == REQUIRED_ADVISORY_CONTEXT_FIELDS,
        "policy timing threshold summary records missing baseline metadata",
    )
    expect(
        policy_thresholds["candidateMissingFields"] == REQUIRED_ADVISORY_CONTEXT_FIELDS,
        "policy timing threshold summary records missing candidate metadata",
    )
    expect(
        policy_thresholds["metadataCompatible"] is False,
        "policy timing threshold summary records incomplete metadata",
    )
    expect(
        policy_thresholds["measuredThresholdExceededCount"] == 1,
        "policy timing threshold summary keeps measured excess visible",
    )
    expect(
        policy_thresholds["thresholdExceededCount"] == 0,
        "policy timing threshold summary withholds claims for missing metadata",
    )
    expect(
        payload["timing"]["thresholdExceededCount"] == 0,
        "missing context suppresses explicit threshold claims",
    )
    expect(
        payload["timing"]["advisoryThresholdExceededCount"] == 0,
        "missing context suppresses advisory threshold claims",
    )
    readiness = payload["metadata"]["baselinePolicy"]["readiness"]["baseline"]
    expect(
        readiness["readyForThresholdBaseline"] is False,
        "missing context is not threshold-baseline ready",
    )
    expect(
        readiness["reasons"] == ["missingContextFields"],
        "missing context readiness reason",
    )
    expect(
        readiness["unsatisfiedThresholdBaselineRequirements"]
        == ["recognizedContextFields"],
        "missing context requirement name",
    )
    requirement_map = requirements_by_name(readiness)
    expect(
        requirement_map["recognizedContextFields"]["observed"]["missingFields"]
        == REQUIRED_ADVISORY_CONTEXT_FIELDS,
        "missing context records required missing fields",
    )
    expect(
        requirement_map["repeatedTimingEvidence"]["satisfied"] is True,
        "missing context probe still has repeated timing evidence",
    )
    threshold_policy = payload["timing"]["advisoryThresholdPolicy"]
    expect(
        threshold_policy["metadataComparability"]["reasons"]
        == ["baseline:missingMetadataFields", "candidate:missingMetadataFields"],
        "missing context metadata comparability reasons",
    )
    delta = payload["timing"]["timingDeltas"][0]
    expect(
        delta["measuredExceedsExplicitThreshold"] is True,
        "missing context still reports measured explicit threshold excess",
    )
    expect(
        delta["exceedsExplicitThreshold"] is False,
        "missing context withholds explicit threshold claim",
    )
    expect(
        delta["currentPolicyDisposition"] == "advisory-threshold-incomparable-metadata",
        "missing context threshold disposition",
    )
    expect(
        delta["timingEvidence"]["sufficientRepeatedEvidence"] is True,
        "missing context probe isolates metadata from sample sufficiency",
    )


def check_advisory_profile_rule_matching(root: Path, tmp: Path) -> None:
    baseline = tmp / "profile-baseline.json"
    candidate = tmp / "profile-candidate.json"
    write_report(
        baseline,
        report(
            [
                timed_case(
                    "texture-sample::directx::release",
                    category="texture-sampling",
                    elapsed_ns=100,
                ),
                timed_case(
                    "debug-control::directx::debug",
                    category="control-flow",
                    elapsed_ns=100,
                    profile="debug",
                ),
                timed_case(
                    "future-category::directx::release",
                    category="future-category",
                    elapsed_ns=100,
                ),
            ]
        ),
    )
    write_report(
        candidate,
        report(
            [
                timed_case(
                    "texture-sample::directx::release",
                    category="texture-sampling",
                    elapsed_ns=113,
                ),
                timed_case(
                    "debug-control::directx::debug",
                    category="control-flow",
                    elapsed_ns=124,
                    profile="debug",
                ),
                timed_case(
                    "future-category::directx::release",
                    category="future-category",
                    elapsed_ns=121,
                ),
            ]
        ),
    )

    result = run_tool(root, baseline, candidate, "--include-timing-deltas")
    expect(result.returncode == 0, result.stderr + result.stdout)
    payload = json.loads(result.stdout)
    expect(payload["status"] == "pass", "profile proposals stay advisory")
    expect(
        set(payload["timing"]["advisoryContext"]["baseline"]["missingFields"])
        >= {"hostLabel", "hostClass", "comparisonWindow", "toolchains"},
        "missing advisory context fields are documented",
    )
    readiness = payload["metadata"]["baselinePolicy"]["readiness"]["baseline"]
    expect(
        readiness["readyForThresholdBaseline"] is False,
        "missing context prevents threshold-baseline readiness",
    )
    expect(
        readiness["reasons"]
        == ["missingContextFields", "insufficientRepeatedTimingEvidence"],
        "missing context and repeated timing evidence readiness reasons",
    )
    expect(
        readiness["thresholdBaselineRequirementCount"] == 8,
        "incomplete context threshold requirement count",
    )
    expect(
        readiness["satisfiedThresholdBaselineRequirementCount"] == 6,
        "incomplete context satisfied requirement count",
    )
    expect(
        readiness["unsatisfiedThresholdBaselineRequirements"]
        == ["recognizedContextFields", "repeatedTimingEvidence"],
        "incomplete context requirement name",
    )
    requirement_map = requirements_by_name(readiness)
    expect(
        requirement_map["recognizedContextFields"]["satisfied"] is False,
        "missing context requirement is unsatisfied",
    )
    expect(
        requirement_map["recognizedContextFields"]["reasonIfUnsatisfied"]
        == "missingContextFields",
        "missing context requirement reason",
    )
    expect(
        set(requirement_map["recognizedContextFields"]["observed"]["missingFields"])
        >= {"hostLabel", "hostClass", "comparisonWindow", "toolchains"},
        "missing context requirement carries observed fields",
    )
    expect(
        requirement_map["timedCases"]["satisfied"] is True,
        "timed-case requirement stays satisfied",
    )
    expect(
        requirement_map["repeatedTimingEvidence"]["satisfied"] is False,
        "missing sample counts keep repeated evidence unsatisfied",
    )
    expect(
        requirement_map["repeatedTimingEvidence"]["observed"][
            "insufficientRepeatedEvidenceCaseCount"
        ]
        == 3,
        "missing sample counts list all timed cases",
    )
    expect(
        payload["timing"]["advisoryRegressionCount"] == 3,
        "all profile-matching regressions are advisory",
    )
    expect(
        payload["timing"]["advisoryThresholdProfile"]["matchedCaseCount"] == 3,
        "profile rules match all timed cases",
    )
    expect(
        payload["timing"]["advisoryThresholdProfile"]["ruleSpecificityCounts"]
        == {
            "category-profile": 1,
            "fallback": 1,
            "profile-only": 1,
        },
        "profile rules classify exact and fallback matches",
    )
    expect(
        payload["timing"]["advisoryThresholdPolicy"]["ruleSpecificityCounts"]
        == {
            "category-profile": 1,
            "fallback": 1,
            "profile-only": 1,
        },
        "policy summary mirrors rule specificity counts",
    )
    expect(
        payload["timing"]["advisoryThresholds"]["classification"][
            "ruleSpecificityCounts"
        ]
        == {
            "category-profile": 1,
            "fallback": 1,
            "profile-only": 1,
        },
        "compact threshold summary includes rule specificity counts",
    )
    expect(
        payload["timing"]["advisoryThresholdProfile"]["claimEligibleCaseCount"] == 0,
        "missing repeated evidence prevents threshold claims",
    )
    expect(
        payload["timing"]["advisoryThresholdProfile"]["insufficientEvidenceCaseCount"]
        == 3,
        "missing repeated evidence cases are counted",
    )
    expect(
        payload["timing"]["advisoryThresholdExceededCount"] == 0,
        "threshold-exceeded claims require repeated evidence",
    )
    deltas_by_case = {
        entry["case"]: entry for entry in payload["timing"]["timingDeltas"]
    }
    expect(
        deltas_by_case["texture-sample::directx::release"]["advisoryThreshold"][
            "ruleCategory"
        ]
        == "texture-sampling",
        "category-specific release rule",
    )
    expect(
        deltas_by_case["texture-sample::directx::release"]["advisoryThreshold"][
            "ruleSpecificity"
        ]
        == "category-profile",
        "category-specific release rule specificity",
    )
    expect(
        deltas_by_case["debug-control::directx::debug"]["advisoryThreshold"][
            "ruleProfile"
        ]
        == "debug",
        "debug profile wildcard rule",
    )
    expect(
        deltas_by_case["debug-control::directx::debug"]["advisoryThreshold"][
            "ruleMatch"
        ]["categoryMatch"]
        == "wildcard",
        "debug profile wildcard rule records wildcard category match",
    )
    expect(
        deltas_by_case["debug-control::directx::debug"]["advisoryThreshold"][
            "ruleSpecificity"
        ]
        == "profile-only",
        "debug profile wildcard rule specificity",
    )
    expect(
        deltas_by_case["debug-control::directx::debug"]["exceedsAdvisoryThreshold"]
        is False,
        "debug profile remains within advisory proposal",
    )
    expect(
        deltas_by_case["future-category::directx::release"]["advisoryThreshold"][
            "ruleCategory"
        ]
        == "*",
        "fallback category rule",
    )
    expect(
        deltas_by_case["future-category::directx::release"]["advisoryThreshold"][
            "ruleSpecificity"
        ]
        == "fallback",
        "fallback rule specificity",
    )
    expect(
        deltas_by_case["future-category::directx::release"]["advisoryThreshold"][
            "ruleMatch"
        ]["caseTarget"]
        == "directx",
        "fallback rule match keeps case target context",
    )
    expect(
        deltas_by_case["future-category::directx::release"][
            "wouldFailAdvisoryProfileIfEnforced"
        ]
        is False,
        "fallback advisory claim is withheld without repeated evidence",
    )
    expect(
        deltas_by_case["future-category::directx::release"][
            "measuredExceedsAdvisoryThreshold"
        ]
        is True,
        "fallback threshold measurement is still visible",
    )
    expect(
        deltas_by_case["future-category::directx::release"]["advisoryThreshold"][
            "claimDisposition"
        ]
        == "insufficient-repeated-evidence",
        "fallback threshold claim disposition explains weak evidence",
    )


def check_incomplete_threshold_baseline_fixture(root: Path) -> None:
    result = run_tool(
        root, INCOMPLETE_THRESHOLD_BASELINE, INCOMPLETE_THRESHOLD_BASELINE
    )
    expect(result.returncode == 0, result.stderr + result.stdout)
    payload = json.loads(result.stdout)
    expect(payload["status"] == "pass", "incomplete metadata stays report-only")
    expect(
        payload["policy"]["failureClass"] == "pass",
        "incomplete metadata does not create a hard failure",
    )
    readiness = payload["metadata"]["baselinePolicy"]["readiness"]
    expect(
        readiness["compatibleReadyPair"] is False,
        "incomplete reports are not a compatible ready pair",
    )
    baseline_readiness = readiness["baseline"]
    expect(
        baseline_readiness["readyForThresholdBaseline"] is False,
        "incomplete fixture is not threshold-baseline ready",
    )
    expect(
        baseline_readiness["reasons"]
        == ["missingContextFields", "insufficientRepeatedTimingEvidence"],
        "incomplete fixture readiness reasons",
    )
    expect(
        baseline_readiness["unsatisfiedThresholdBaselineRequirements"]
        == ["recognizedContextFields", "repeatedTimingEvidence"],
        "incomplete fixture requirement names",
    )
    requirement_map = requirements_by_name(baseline_readiness)
    expect(
        requirement_map["recognizedContextFields"]["observed"]["missingFields"]
        == INCOMPLETE_THRESHOLD_MISSING_CONTEXT_FIELDS,
        "incomplete fixture records exact missing context fields",
    )
    expect(
        requirement_map["recognizedContextFields"]["observed"]["requiredFields"]
        == REQUIRED_ADVISORY_CONTEXT_FIELDS,
        "incomplete fixture records required context fields",
    )
    comparison_dimensions = payload["metadata"]["baselinePolicy"][
        "comparisonDimensions"
    ]
    expect(
        comparison_dimensions["baseline"]["missingFields"]
        == INCOMPLETE_THRESHOLD_MISSING_CONTEXT_FIELDS,
        "comparison dimensions expose incomplete context fields",
    )
    expect(
        comparison_dimensions["baseline"]["caseCategories"] == ["storage-buffers"],
        "comparison dimensions still expose incomplete report categories",
    )
    expect(
        requirement_map["timedCases"]["observed"]["timedCaseCount"] == 1,
        "incomplete fixture still records timed evidence",
    )
    expect(
        requirement_map["repeatedTimingEvidence"]["observed"][
            "insufficientRepeatedEvidenceCases"
        ]
        == ["storage-buffer-compute::directx::release"],
        "incomplete fixture records missing repeated sample evidence",
    )
    expect(
        all(
            requirement_map[name]["satisfied"] is True
            for name in (
                "timedCases",
                "cleanReportShape",
                "functionalSuccess",
                "requiredToolCoverage",
                "skippedToolEvidence",
            )
        ),
        "shape and coverage are otherwise complete in the fixture",
    )

    regression_result = run_tool(
        root,
        INCOMPLETE_THRESHOLD_BASELINE,
        INCOMPLETE_THRESHOLD_CANDIDATE,
        "--max-regression-percent",
        "10",
        "--include-timing-deltas",
    )
    expect(
        regression_result.returncode == 0,
        regression_result.stderr + regression_result.stdout,
    )
    regression_payload = json.loads(regression_result.stdout)
    regression_readiness = regression_payload["metadata"]["baselinePolicy"]["readiness"]
    expect(
        regression_readiness["compatibleReadyPair"] is False,
        "incomplete baseline/candidate pair is not threshold-baseline ready",
    )
    expect(
        regression_readiness["candidate"]["readyForThresholdBaseline"] is False,
        "incomplete candidate fixture is not threshold-baseline ready",
    )
    expect(
        regression_readiness["candidate"]["unsatisfiedThresholdBaselineRequirements"]
        == ["recognizedContextFields", "repeatedTimingEvidence"],
        "incomplete candidate requirement names",
    )
    expect(
        regression_readiness["candidate"]["missingContextFields"]
        == INCOMPLETE_THRESHOLD_MISSING_CONTEXT_FIELDS,
        "incomplete candidate records exact missing context fields",
    )
    regression_dimensions = regression_payload["metadata"]["baselinePolicy"][
        "comparisonDimensions"
    ]
    expect(
        regression_dimensions["baseline"]["missingFields"]
        == INCOMPLETE_THRESHOLD_MISSING_CONTEXT_FIELDS,
        "regression baseline dimensions expose incomplete context fields",
    )
    expect(
        regression_dimensions["candidate"]["missingFields"]
        == INCOMPLETE_THRESHOLD_MISSING_CONTEXT_FIELDS,
        "regression candidate dimensions expose incomplete context fields",
    )
    advisory_context = regression_payload["timing"]["advisoryContext"]
    expect(
        advisory_context["baseline"]["missingFields"]
        == INCOMPLETE_THRESHOLD_MISSING_CONTEXT_FIELDS,
        "timing advisory context exposes incomplete baseline fields",
    )
    expect(
        advisory_context["candidate"]["missingFields"]
        == INCOMPLETE_THRESHOLD_MISSING_CONTEXT_FIELDS,
        "timing advisory context exposes incomplete candidate fields",
    )
    threshold_policy = regression_payload["timing"]["advisoryThresholdPolicy"]
    expect(
        threshold_policy["mode"] == "report-only",
        "incomplete advisory threshold policy remains report-only",
    )
    expect(
        threshold_policy["metadataCompatible"] is False,
        "incomplete advisory threshold policy records metadata incompatibility",
    )
    expect(
        threshold_policy["metadataComparability"]["baselineMissingFields"]
        == INCOMPLETE_THRESHOLD_MISSING_CONTEXT_FIELDS,
        "threshold policy records missing baseline metadata fields",
    )
    expect(
        threshold_policy["metadataComparability"]["candidateMissingFields"]
        == INCOMPLETE_THRESHOLD_MISSING_CONTEXT_FIELDS,
        "threshold policy records missing candidate metadata fields",
    )
    expect(
        threshold_policy["metadataComparability"]["reasons"]
        == ["baseline:missingMetadataFields", "candidate:missingMetadataFields"],
        "threshold policy names missing metadata reasons",
    )
    expect(
        threshold_policy["insufficientEvidenceCases"]
        == ["storage-buffer-compute::directx::release"],
        "threshold policy records incomplete-evidence case",
    )
    threshold_profile = regression_payload["timing"]["advisoryThresholdProfile"]
    expect(
        threshold_profile["mode"] == "report-only",
        "incomplete advisory threshold profile remains report-only",
    )
    expect(
        threshold_profile["insufficientEvidenceCases"]
        == ["storage-buffer-compute::directx::release"],
        "threshold profile records incomplete-evidence case",
    )
    expect(
        regression_payload["timing"]["thresholdExceededCount"] == 0,
        "explicit threshold claim is withheld for incomplete evidence",
    )
    expect(
        regression_payload["timing"]["advisoryThresholdExceededCount"] == 0,
        "advisory threshold claim is withheld for incomplete evidence",
    )
    delta = regression_payload["timing"]["timingDeltas"][0]
    expect(
        delta["measuredExceedsExplicitThreshold"] is True,
        "incomplete fixture still reports measured explicit threshold excess",
    )
    expect(
        delta["measuredExceedsAdvisoryThreshold"] is True,
        "incomplete fixture still reports measured advisory threshold excess",
    )
    expect(
        delta["exceedsExplicitThreshold"] is False,
        "incomplete evidence prevents explicit threshold claim",
    )
    expect(
        delta["exceedsAdvisoryThreshold"] is False,
        "incomplete evidence prevents advisory threshold claim",
    )
    expect(
        delta["currentPolicyDisposition"]
        == "advisory-threshold-insufficient-repeated-evidence",
        "incomplete evidence disposition is explicit",
    )
    expect(
        delta["timingEvidence"]["reasons"]
        == [
            "baseline:missingSampleCount",
            "candidate:missingSampleCount",
            "baseline:missingMetadataFields",
            "candidate:missingMetadataFields",
        ],
        "incomplete evidence reasons name samples and metadata",
    )
    expect(
        delta["timingEvidence"]["metadata"]["reasons"]
        == ["baseline:missingMetadataFields", "candidate:missingMetadataFields"],
        "incomplete evidence carries metadata reasons separately",
    )


def check_normalized_case_identity(root: Path, tmp: Path) -> None:
    baseline = tmp / "normalized-case-baseline.json"
    candidate = tmp / "normalized-case-candidate.json"
    baseline_case = timed_case(
        "fixtures/StorageBufferComputeShader.cgl::directx::release",
        category="storage-buffers",
        elapsed_ns=100,
    )
    baseline_case["fixtureName"] = "storage-buffer-compute"
    candidate_case = timed_case(
        "storage-buffer-compute::directx::release",
        category="storage-buffers",
        elapsed_ns=112,
    )
    candidate_case["fixtureName"] = "storage-buffer-compute"
    write_report(baseline, report([baseline_case]))
    write_report(candidate, report([candidate_case]))

    result = run_tool(root, baseline, candidate)
    expect(result.returncode == 0, result.stderr + result.stdout)
    payload = json.loads(result.stdout)
    expect(payload["status"] == "pass", "normalized case labels should compare")
    expect(payload["structure"]["missingCaseCount"] == 0, "no normalized case loss")
    expect(
        payload["structure"]["changedReportCaseLabelCount"] == 1,
        "raw report case label drift is reported",
    )
    changed_label = payload["structure"]["changedReportCaseLabels"][0]
    expect(
        changed_label["case"] == "storage-buffer-compute::directx::release",
        "normalized case identity",
    )
    expect(
        changed_label["baselineReportCase"]
        == "fixtures/StorageBufferComputeShader.cgl::directx::release",
        "baseline raw case label",
    )
    regression = payload["timing"]["advisoryRegressions"][0]
    expect(
        regression["caseContext"]["baseline"]["reportCase"]
        == "fixtures/StorageBufferComputeShader.cgl::directx::release",
        "timing context preserves baseline raw case label",
    )
    expect(
        regression["caseContext"]["candidate"]["fixtureName"]
        == "storage-buffer-compute",
        "timing context carries candidate fixture name",
    )
    expect(
        payload["structure"]["caseIdentityPolicy"].startswith(
            "Case coverage is compared by normalized"
        ),
        "case identity policy is explicit",
    )


def check_fractional_threshold_ceiling(root: Path, tmp: Path) -> None:
    baseline = tmp / "fractional-threshold-baseline.json"
    candidate = tmp / "fractional-threshold-candidate.json"
    case_key = "storage-buffer-compute::directx::release"
    write_report(
        baseline,
        complete_policy_report(
            [
                timed_case(
                    case_key,
                    category="storage-buffers",
                    elapsed_ns=101,
                )
            ]
        ),
    )
    write_report(
        candidate,
        complete_policy_report(
            [
                timed_case(
                    case_key,
                    category="storage-buffers",
                    elapsed_ns=114,
                )
            ]
        ),
    )

    result = run_tool(
        root,
        baseline,
        candidate,
        "--max-regression-percent",
        "12.5",
        "--include-timing-deltas",
    )
    expect(result.returncode == 0, result.stderr + result.stdout)
    payload = json.loads(result.stdout)
    delta = payload["timing"]["timingDeltas"][0]
    expect(delta["allowedNs"] == 114, "fractional threshold ceiling")
    expect(delta["allowedNsExact"] == "113.625", "exact threshold value")
    expect(
        delta["explicitThreshold"]["allowedNs"] == 114,
        "explicit threshold ceiling",
    )
    expect(
        delta["exceedsExplicitThreshold"] is False,
        "candidate at the ceiling is within threshold",
    )
    expect(
        delta["currentPolicyDisposition"] == "within-advisory-threshold",
        "fractional threshold disposition",
    )


def check_pairwise_stability_evidence(root: Path, tmp: Path) -> None:
    baseline = tmp / "pairwise-stability-baseline.json"
    stable_candidate = tmp / "pairwise-stability-candidate.json"
    unstable_candidate = tmp / "pairwise-stability-unstable-candidate.json"
    write_report(
        baseline,
        complete_policy_report(
            [
                timed_case(
                    "storage-buffer-compute::directx::release",
                    category="storage-buffers",
                    elapsed_ns=100,
                ),
                timed_case(
                    "nested-control-flow::directx::release",
                    category="control-flow",
                    elapsed_ns=200,
                ),
            ]
        ),
    )
    write_report(
        stable_candidate,
        complete_policy_report(
            [
                timed_case(
                    "storage-buffer-compute::directx::release",
                    category="storage-buffers",
                    elapsed_ns=108,
                ),
                timed_case(
                    "nested-control-flow::directx::release",
                    category="control-flow",
                    elapsed_ns=200,
                ),
            ]
        ),
    )
    write_report(
        unstable_candidate,
        complete_policy_report(
            [
                timed_case(
                    "storage-buffer-compute::directx::release",
                    category="storage-buffers",
                    elapsed_ns=125,
                ),
                timed_case(
                    "nested-control-flow::directx::release",
                    category="control-flow",
                    elapsed_ns=200,
                ),
            ]
        ),
    )

    result = run_tool(root, baseline, stable_candidate)
    expect(result.returncode == 0, result.stderr + result.stdout)
    payload = json.loads(result.stdout)
    stability = payload["metadata"]["baselinePolicy"]["stability"]
    expect(payload["status"] == "pass", "stable pairwise evidence should pass")
    expect(stability["mode"] == "report-only", "pairwise stability mode")
    expect(
        stability["stableEnoughForThresholdBaseline"] is True,
        "pairwise evidence is stable enough",
    )
    expect(stability["status"] == "stable", "stable pairwise status")
    expect(stability["reasons"] == [], "stable pairwise reasons")
    expect(
        stability["stabilityRequirementCount"] == 4,
        "pairwise stability requirement count",
    )
    expect(
        stability["satisfiedStabilityRequirementCount"] == 4,
        "pairwise stability satisfied requirement count",
    )
    expect(
        stability["context"]["baseline"]["fields"]["hostClass"] == "linux-x86_64",
        "pairwise stability carries host class",
    )
    expect(
        stability["context"]["baseline"]["categories"]
        == ["control-flow", "storage-buffers"],
        "pairwise stability carries categories",
    )
    expect(
        stability["context"]["baseline"]["profiles"] == ["release"],
        "pairwise stability carries profiles",
    )
    expect(
        stability["context"]["baseline"]["toolchains"]["cglc"]["version"]
        == "0.6.0-fixture",
        "pairwise stability carries toolchain version",
    )
    expect(
        stability["recommendedSpreadExceededCaseCount"] == 0,
        "stable pair has no spread outliers",
    )
    groups_by_case = {
        group["case"]: group for group in stability["caseStabilityGroups"]
    }
    storage_group = groups_by_case["storage-buffer-compute::directx::release"]
    expect(storage_group["stabilityClass"] == "variable", "storage spread class")
    expect(
        storage_group["stabilityDisposition"] == "within-recommended-spread",
        "storage spread remains within curation heuristic",
    )
    expect(storage_group["timing"]["spreadPercentOfMin"] == 8.0, "storage spread")
    expect(
        storage_group["baselineDimensions"]["category"] == "storage-buffers",
        "storage stability category dimension",
    )
    expect(
        storage_group["baselineDimensions"]["profile"] == "release",
        "storage stability profile dimension",
    )
    expect(
        storage_group["baselineDimensions"]["toolchains"]
        == "toolchains=cglc@0.6.0-fixture:unspecified:available",
        "storage stability toolchain dimension",
    )

    unstable_result = run_tool(root, baseline, unstable_candidate)
    expect(
        unstable_result.returncode == 0,
        unstable_result.stderr + unstable_result.stdout,
    )
    unstable_payload = json.loads(unstable_result.stdout)
    unstable_stability = unstable_payload["metadata"]["baselinePolicy"]["stability"]
    expect(
        unstable_payload["status"] == "pass",
        "unstable timing spread remains report-only",
    )
    expect(
        unstable_payload["policy"]["failureClass"] == "pass",
        "unstable timing spread does not affect failure class",
    )
    expect(
        unstable_stability["stableEnoughForThresholdBaseline"] is False,
        "unstable pair is not threshold-baseline ready",
    )
    expect(unstable_stability["status"] == "unstable", "unstable pair status")
    expect(
        unstable_stability["reasons"] == ["unstableTimingSpread"],
        "unstable pair reason",
    )
    expect(
        unstable_stability["recommendedSpreadExceededCases"]
        == ["storage-buffer-compute::directx::release"],
        "unstable spread case list",
    )


def check_changed_case_category_structural_failure(root: Path, tmp: Path) -> None:
    baseline = tmp / "category-drift-baseline.json"
    candidate = tmp / "category-drift-candidate.json"
    write_report(
        baseline,
        complete_policy_report(
            [
                timed_case(
                    "storage-buffer-compute::directx::release",
                    category="storage-buffers",
                    elapsed_ns=100,
                ),
                timed_case(
                    "nested-control-flow::directx::release",
                    category="control-flow",
                    elapsed_ns=200,
                ),
            ]
        ),
    )
    write_report(
        candidate,
        complete_policy_report(
            [
                timed_case(
                    "storage-buffer-compute::directx::release",
                    category="control-flow",
                    elapsed_ns=125,
                ),
                timed_case(
                    "nested-control-flow::directx::release",
                    category="storage-buffers",
                    elapsed_ns=200,
                ),
            ]
        ),
    )

    result = run_tool(
        root,
        baseline,
        candidate,
        "--max-regression-percent",
        "5",
        "--include-timing-deltas",
    )
    expect(result.returncode == 1, result.stderr + result.stdout)
    payload = json.loads(result.stdout)
    expect(payload["status"] == "fail", "category drift should fail structurally")
    expect(
        payload["policy"]["failureClass"] == "structural",
        "category drift is structural",
    )
    expect(payload["policy"]["timing"]["failed"] is False, "timing stays advisory")
    expect(payload["structure"]["missingCategories"] == [], "no category-set loss")
    expect(
        payload["structure"]["changedCaseCategoryCount"] == 2,
        "per-case category drift count",
    )
    expect(
        payload["structure"]["changedCaseCategories"]
        == [
            {
                "baselineCategory": "control-flow",
                "candidateCategory": "storage-buffers",
                "case": "nested-control-flow::directx::release",
            },
            {
                "baselineCategory": "storage-buffers",
                "candidateCategory": "control-flow",
                "case": "storage-buffer-compute::directx::release",
            },
        ],
        "per-case category drift details",
    )
    expect(
        payload["policy"]["structural"]["failureReasons"] == ["changedCaseCategories"],
        "category drift outranks timing advisory",
    )
    expect(
        payload["timing"]["thresholdExceededCount"] == 1,
        "timing threshold excess remains reported",
    )


def check_aggregate_report_only(root: Path, tmp: Path) -> None:
    result = run_aggregate(root, ADVISORY_BASELINE, STRUCTURAL_LOSS_CANDIDATE)
    expect(result.returncode == 0, result.stderr + result.stdout)
    payload = json.loads(result.stdout)
    expect(payload["mode"] == "aggregate", "aggregate mode")
    expect(payload["status"] == "pass", "aggregate remains report-only")
    expect(
        payload["policy"]["timingThresholdsEvaluated"] is False,
        "aggregate does not evaluate timing thresholds",
    )
    expect(payload["summary"]["reportCount"] == 2, "aggregate report count")
    expect(payload["summary"]["baselineGroupCount"] == 1, "baseline grouping")
    expect(
        payload["summary"]["reportsReadyForThresholdBaselineCount"] == 2,
        "aggregate readiness count",
    )
    expect(
        payload["summary"]["reportsIncompleteForThresholdBaselineCount"] == 0,
        "aggregate incomplete readiness count",
    )
    expect(
        payload["thresholdBaselineReadiness"]["mode"] == "report-only",
        "aggregate readiness stays report-only",
    )
    expect(
        payload["thresholdBaselineReadiness"]["readinessStatusCounts"] == {"ready": 2},
        "aggregate readiness status counts",
    )
    expect(
        payload["thresholdBaselineReadiness"]["reasonCountByReason"] == {},
        "ready aggregate has no readiness blockers",
    )
    release_claim_readiness = payload["thresholdReleaseClaimReadiness"]
    expect(
        release_claim_readiness["mode"] == "report-only",
        "aggregate release-claim readiness stays report-only",
    )
    expect(
        release_claim_readiness["readyBaselineGroupCount"] == 0,
        "two-report aggregate is not release-claim ready",
    )
    expect(
        release_claim_readiness["incompleteBaselineGroupCount"] == 1,
        "two-report aggregate has incomplete release-claim group",
    )
    expect(
        release_claim_readiness["reasonCountByReason"]
        == {
            "insufficientReleaseRepeatedSamples": 1,
            "insufficientRepeatedReadyReports": 1,
            "unstableTimingSpread": 1,
        },
        "two-report aggregate release-claim blockers",
    )
    release_claim_group = release_claim_readiness["baselineGroups"][0]
    expect(
        release_claim_group["remainingReadyReportsForReleaseClaim"] == 1,
        "two-report aggregate names remaining repeated report count",
    )
    expect(
        release_claim_group["unsatisfiedRequirements"]
        == [
            "minimumRepeatedReadyReports",
            "releaseMinimumSamplesPerCase",
            "recommendedTimingSpread",
        ],
        "two-report aggregate release-claim requirements",
    )
    reports_by_name = {
        Path(report["path"]).name: report for report in payload["reports"]
    }
    expect(
        reports_by_name[ADVISORY_BASELINE.name]["baselineReadiness"]["status"]
        == "ready",
        "aggregate report readiness",
    )
    structural_loss = reports_by_name[STRUCTURAL_LOSS_CANDIDATE.name]
    expect(
        structural_loss["missingCategories"] == ["descriptor-arrays"],
        "aggregate missing category",
    )
    expect(
        structural_loss["missingCommandProfiles"] == ["debug"],
        "aggregate missing command profile",
    )
    expect(
        structural_loss["missingTargets"] == ["opengl"],
        "aggregate missing target",
    )
    expect(
        payload["coverage"]["commandProfiles"] == ["debug", "release"],
        "aggregate command-profile coverage",
    )

    skipped_result = run_aggregate(
        root, ADVISORY_BASELINE, OPTIONAL_TOOL_SKIP_CANDIDATE
    )
    expect(
        skipped_result.returncode == 0, skipped_result.stderr + skipped_result.stdout
    )
    skipped_payload = json.loads(skipped_result.stdout)
    expect(
        skipped_payload["summary"]["skippedToolCaseCountByTool"] == {"spirv-val": 1},
        "aggregate skipped-tool count",
    )
    expect(
        skipped_payload["skippedToolAccounting"]["skippedToolCasesByTool"]["spirv-val"][
            0
        ]["case"]
        == "dry-run-case::directx::debug",
        "aggregate skipped-tool case list",
    )
    expect(
        any(
            group["dimensions"]["toolchains"].endswith(
                "spirv-val@fixture-missing:optional:unavailable"
            )
            and group["skippedCaseCount"] == 1
            for group in skipped_payload["baselineGroups"]
        ),
        "aggregate baseline group includes optional skipped tool",
    )

    incomplete_result = run_aggregate(
        root, INCOMPLETE_THRESHOLD_BASELINE, INCOMPLETE_THRESHOLD_CANDIDATE
    )
    expect(
        incomplete_result.returncode == 0,
        incomplete_result.stderr + incomplete_result.stdout,
    )
    incomplete_payload = json.loads(incomplete_result.stdout)
    expect(
        incomplete_payload["status"] == "pass",
        "incomplete aggregate remains report-only",
    )
    expect(
        incomplete_payload["summary"]["reportsReadyForThresholdBaselineCount"] == 0,
        "incomplete aggregate ready count",
    )
    expect(
        incomplete_payload["summary"]["reportsIncompleteForThresholdBaselineCount"]
        == 2,
        "incomplete aggregate blocker count",
    )
    readiness = incomplete_payload["thresholdBaselineReadiness"]
    expect(
        readiness["readyReportCount"] == 0 and readiness["incompleteReportCount"] == 2,
        "aggregate readiness report counts incomplete reports",
    )
    expect(
        readiness["reasonCountByReason"]
        == {"insufficientRepeatedTimingEvidence": 2, "missingContextFields": 2},
        "aggregate readiness reason accounting",
    )
    expect(
        readiness["unsatisfiedRequirementCountByName"]
        == {"recognizedContextFields": 2, "repeatedTimingEvidence": 2},
        "aggregate readiness requirement accounting",
    )
    expect(
        readiness["missingContextFieldCountByField"]
        == {field: 2 for field in INCOMPLETE_THRESHOLD_MISSING_CONTEXT_FIELDS},
        "aggregate readiness missing-context accounting",
    )
    expect(
        readiness["reportIndexesByReason"]["insufficientRepeatedTimingEvidence"]
        == [0, 1],
        "aggregate readiness indexes by repeated-sample reason",
    )
    expect(
        readiness["insufficientRepeatedTimingEvidenceCaseCount"] == 2,
        "aggregate readiness repeated-sample case count",
    )
    incomplete_baseline_group = incomplete_payload["baselineGroups"][0]
    expect(
        incomplete_baseline_group["reportsIncompleteForThresholdBaseline"] == 2,
        "baseline group carries incomplete readiness count",
    )
    expect(
        incomplete_baseline_group["readinessReasonCountByReason"]
        == {"insufficientRepeatedTimingEvidence": 2, "missingContextFields": 2},
        "baseline group carries readiness reasons",
    )
    expect(
        incomplete_baseline_group["unsatisfiedReadinessRequirementCountByName"]
        == {"recognizedContextFields": 2, "repeatedTimingEvidence": 2},
        "baseline group carries unsatisfied readiness requirements",
    )
    incomplete_release_claim = incomplete_payload["thresholdReleaseClaimReadiness"]
    expect(
        incomplete_release_claim["readyBaselineGroupCount"] == 0,
        "incomplete aggregate has no release-claim-ready groups",
    )
    expect(
        incomplete_release_claim["reasonCountByReason"]
        == {
            "incompleteThresholdBaselineReports": 1,
            "insufficientRepeatedReadyReports": 1,
            "insufficientReleaseRepeatedSamples": 1,
            "unstableTimingSpread": 1,
        },
        "incomplete aggregate release-claim reasons",
    )

    bad_report = tmp / "aggregate-bad-summary.json"
    bad_payload = report([])
    bad_payload["summary"]["skippedCount"] = 1
    write_report(bad_report, bad_payload)
    validation_result = run_aggregate(root, bad_report)
    expect(
        validation_result.returncode == 0,
        validation_result.stderr + validation_result.stdout,
    )
    validation_payload = json.loads(validation_result.stdout)
    expect(
        validation_payload["summary"]["validationIssueCount"] == 1,
        "aggregate validation issue count",
    )
    expect(
        validation_payload["validation"]["reportsWithIssues"] == [0],
        "aggregate validation report index",
    )
    expect(
        validation_payload["reports"][0]["validationIssues"]
        == ["reports[0].summary.skippedCount=1 does not match cases (0)"],
        "aggregate validation issue text",
    )


def check_aggregate_native_optimization_accounting(root: Path, tmp: Path) -> None:
    known_profile = {
        "available": True,
        "declared": True,
        "optimization": {
            "level": "-O",
            "policy": "use-when-available",
            "requestedLevel": "O2",
            "status": "applied",
            "tool": "spirv-opt",
        },
        "parseError": None,
    }
    skipped_tool_profile = copy.deepcopy(known_profile)
    skipped_tool_profile["optimization"] = {
        **known_profile["optimization"],
        "status": "skipped-tool-missing",
    }
    missing_optimization_profile = {
        "available": True,
        "declared": True,
        "optimization": None,
        "parseError": None,
    }
    optimization_without_status = {
        "available": True,
        "declared": True,
        "optimization": {
            "level": "-O",
            "policy": "use-when-available",
            "requestedLevel": "O2",
            "tool": "spirv-opt",
        },
        "parseError": None,
    }

    first_payload = complete_policy_report(
        [
            native_profile_case(
                "storage-buffer-compute::vulkan::release",
                native_profile=known_profile,
            ),
            native_profile_case(
                "nested-control-flow::vulkan::release",
                native_profile=missing_optimization_profile,
            ),
        ]
    )
    second_payload = complete_policy_report(
        [
            native_profile_case(
                "texture-sampling::vulkan::release",
                native_profile=skipped_tool_profile,
            ),
            native_profile_case(
                "storage-image-write::vulkan::release",
                native_profile=optimization_without_status,
            ),
        ]
    )
    add_native_optimization_summary(first_payload)
    add_native_optimization_summary(second_payload)

    first_path = tmp / "aggregate-native-a.json"
    second_path = tmp / "aggregate-native-b.json"
    write_report(first_path, first_payload)
    write_report(second_path, second_payload)

    result = run_aggregate(root, first_path, second_path)
    expect(result.returncode == 0, result.stderr + result.stdout)
    payload = json.loads(result.stdout)
    expect(payload["status"] == "pass", "aggregate native accounting is advisory")

    expected_status_counts = {"applied": 1, "skipped-tool-missing": 1}
    expected_evidence_counts = {
        "known-status": 2,
        "missing-debug-optimization": 1,
        "optimization-without-status": 1,
    }
    expected_evidence_summary = native_optimization_evidence_summary(
        4, expected_evidence_counts
    )
    expect(
        payload["summary"]["caseCountByNativeOptimizationStatus"]
        == expected_status_counts,
        "aggregate summary native status counts",
    )
    expect(
        payload["summary"]["nativeOptimizationStatuses"]
        == ["applied", "skipped-tool-missing"],
        "aggregate summary native status list",
    )
    expect(
        payload["summary"]["caseCountByNativeOptimizationEvidenceStatus"]
        == expected_evidence_counts,
        "aggregate summary native evidence counts",
    )
    expect(
        payload["summary"]["nativeOptimizationEvidence"] == expected_evidence_summary,
        "aggregate summary native evidence summary",
    )

    native_optimization = payload["nativeOptimization"]
    expect(
        native_optimization["mode"] == "report-only",
        "aggregate native optimization mode",
    )
    expect(
        native_optimization["caseCountByStatus"] == expected_status_counts,
        "aggregate native status advisory counts",
    )
    expect(
        native_optimization["caseCountByEvidenceStatus"] == expected_evidence_counts,
        "aggregate native evidence advisory counts",
    )
    expect(
        native_optimization["nativeOptimizationEvidence"] == expected_evidence_summary,
        "aggregate native evidence advisory summary",
    )
    expect(
        native_optimization["reportsWithKnownStatusCount"] == 2,
        "aggregate native reports with known statuses",
    )
    expect(
        native_optimization["reportsWithNativeProfileEvidenceCount"] == 2,
        "aggregate native reports with profile evidence",
    )
    expect(
        "never change aggregate exit status" in native_optimization["policy"].lower(),
        "aggregate native policy remains report-only",
    )

    expect(
        payload["coverage"]["nativeOptimizationStatuses"]
        == ["applied", "skipped-tool-missing"],
        "aggregate native status coverage",
    )
    expect(
        payload["coverage"]["nativeOptimizationEvidenceStatuses"]
        == [
            "known-status",
            "missing-debug-optimization",
            "optimization-without-status",
        ],
        "aggregate native evidence coverage",
    )

    baseline_group = payload["baselineGroups"][0]
    expect(
        baseline_group["caseCountByNativeOptimizationStatus"] == expected_status_counts,
        "aggregate baseline group native status counts",
    )
    expect(
        baseline_group["caseCountByNativeOptimizationEvidenceStatus"]
        == expected_evidence_counts,
        "aggregate baseline group native evidence counts",
    )
    dimension_group = payload["caseDimensionGroups"][0]
    expect(
        dimension_group["caseCountByNativeOptimizationStatus"]
        == expected_status_counts,
        "aggregate dimension group native status counts",
    )
    expect(
        dimension_group["caseCountByNativeOptimizationEvidenceStatus"]
        == expected_evidence_counts,
        "aggregate dimension group native evidence counts",
    )

    reports_by_name = {
        Path(report["path"]).name: report for report in payload["reports"]
    }
    expect(
        reports_by_name[first_path.name]["nativeOptimizationEvidence"]
        == native_optimization_evidence_summary(
            2,
            {"known-status": 1, "missing-debug-optimization": 1},
        ),
        "aggregate per-report native evidence summary",
    )
    expect(
        reports_by_name[second_path.name]["caseCountByNativeOptimizationEvidenceStatus"]
        == {"known-status": 1, "optimization-without-status": 1},
        "aggregate per-report native evidence counts",
    )


def check_aggregate_stability_evidence(root: Path, tmp: Path) -> None:
    report_paths: list[Path] = []
    storage_timings = [100, 105, 110]
    for index, storage_elapsed_ns in enumerate(storage_timings):
        report_path = tmp / f"aggregate-stability-{index}.json"
        write_report(
            report_path,
            complete_policy_report(
                [
                    timed_case(
                        "storage-buffer-compute::directx::release",
                        category="storage-buffers",
                        elapsed_ns=storage_elapsed_ns,
                    ),
                    timed_case(
                        "nested-control-flow::directx::release",
                        category="control-flow",
                        elapsed_ns=200,
                    ),
                ]
            ),
        )
        report_paths.append(report_path)

    result = run_aggregate(root, *report_paths)
    expect(result.returncode == 0, result.stderr + result.stdout)
    payload = json.loads(result.stdout)
    expect(payload["status"] == "pass", "aggregate stability remains report-only")
    expect(
        payload["summary"]["caseStabilityGroupCount"] == 2,
        "aggregate stability group count",
    )
    expect(
        payload["summary"]["multiSampleCaseStabilityGroupCount"] == 2,
        "aggregate multi-sample stability count",
    )
    stability = payload["baselineStability"]
    expect(stability["mode"] == "report-only", "stability mode")
    expect(
        stability["caseStabilityGroupCount"] == 2,
        "stability summary group count",
    )
    expect(stability["sampleCount"] == 6, "stability sample count")
    expect(
        stability["stabilityClassCounts"] == {"identical": 1, "variable": 1},
        "stability class counts",
    )
    expect(stability["maxSpreadNs"] == 10, "stability max spread")
    expect(
        stability["maxSpreadPercentOfMin"] == 10.0,
        "stability max spread percent",
    )
    release_claim_readiness = payload["thresholdReleaseClaimReadiness"]
    expect(
        release_claim_readiness["mode"] == "report-only",
        "aggregate release-claim readiness mode",
    )
    expect(
        release_claim_readiness["readyBaselineGroupCount"] == 1,
        "three-report stable aggregate has release-claim-ready group",
    )
    expect(
        release_claim_readiness["incompleteBaselineGroupCount"] == 0,
        "three-report stable aggregate has no release-claim blockers",
    )
    expect(
        release_claim_readiness["reasonCountByReason"] == {},
        "three-report stable aggregate has no release-claim reasons",
    )
    expect(
        payload["summary"]["thresholdReleaseClaimReadyBaselineGroupCount"] == 1,
        "summary mirrors release-claim-ready group count",
    )
    release_claim_group = release_claim_readiness["baselineGroups"][0]
    expect(
        release_claim_group["readyForReleaseClaimReview"] is True,
        "release-claim group is review-ready",
    )
    expect(
        release_claim_group["releaseClaimRepeatedReportMinimum"] == 3,
        "release-claim group pins repeated report minimum",
    )
    expect(
        release_claim_group["remainingReadyReportsForReleaseClaim"] == 0,
        "release-claim group needs no more ready reports",
    )

    groups_by_case = {group["case"]: group for group in payload["caseStabilityGroups"]}
    storage_group = groups_by_case["storage-buffer-compute::directx::release"]
    expect(storage_group["stabilityClass"] == "variable", "variable case stability")
    expect(storage_group["readyReportCount"] == 3, "ready stability samples")
    expect(storage_group["timing"]["sampleCount"] == 3, "storage sample count")
    expect(storage_group["timing"]["minNs"] == 100, "storage min")
    expect(storage_group["timing"]["medianNs"] == 105, "storage median")
    expect(storage_group["timing"]["maxNs"] == 110, "storage max")
    expect(storage_group["timing"]["spreadNs"] == 10, "storage spread")
    expect(
        [
            sample["readyForThresholdBaseline"]
            for sample in storage_group["timingSamples"]
        ]
        == [True, True, True],
        "stability samples keep readiness evidence",
    )

    control_group = groups_by_case["nested-control-flow::directx::release"]
    expect(control_group["stabilityClass"] == "identical", "identical stability")
    expect(control_group["timing"]["spreadNs"] == 0, "identical spread")

    baseline_group = payload["baselineGroups"][0]
    expect(
        baseline_group["timingStability"]["caseStabilityGroupCount"] == 2,
        "baseline group stability count",
    )
    expect(
        baseline_group["timingStability"]["variableCaseStabilityGroupCount"] == 1,
        "baseline group variable count",
    )
    expect(
        len(baseline_group["caseStabilityGroupKeys"]) == 2,
        "baseline group stability keys",
    )


def check_structural_coverage_failure(root: Path) -> None:
    result = run_tool(root, ADVISORY_BASELINE, STRUCTURAL_LOSS_CANDIDATE)
    expect(result.returncode == 1, result.stdout)
    payload = json.loads(result.stdout)
    expect(payload["status"] == "fail", "structural coverage loss should fail")
    expect(
        payload["policy"]["failureClass"] == "structural",
        "structural failure class",
    )
    expect(
        payload["policy"]["failurePriority"] == ["structural"],
        "structural failure priority",
    )
    expect(
        payload["structure"]["missingCases"]
        == [
            "dry-run-case::directx::debug",
            "texture-descriptor-array::opengl::release",
        ],
        "missing cases listed",
    )
    expect(
        payload["structure"]["missingCategories"] == ["descriptor-arrays"],
        "missing category",
    )
    expect(
        payload["structure"]["missingCommandProfiles"] == ["debug"],
        "missing command profile",
    )
    expect(payload["structure"]["missingProfiles"] == ["debug"], "missing profile")
    expect(payload["structure"]["missingTargets"] == ["opengl"], "missing target")


def check_skip_toolchain_failure(root: Path) -> None:
    result = run_tool(root, ADVISORY_BASELINE, SKIP_TOOLCHAIN_CANDIDATE)
    expect(result.returncode == 1, result.stdout)
    payload = json.loads(result.stdout)
    expect(payload["status"] == "fail", "skip/toolchain loss should fail")
    expect(
        payload["structure"]["newSkippedCases"]
        == ["nested-control-flow::directx::release"],
        "new skipped case",
    )
    expect(
        payload["structure"]["newUnavailableToolchainLabels"] == ["cglc"],
        "new unavailable toolchain label",
    )
    expect(
        payload["structure"]["newRequiredUnavailableToolchainLabels"] == ["cglc"],
        "new required unavailable toolchain label",
    )
    expect(
        payload["structure"]["newOptionalUnavailableToolchainLabels"] == [],
        "no optional unavailable toolchain label",
    )
    expect(
        payload["structure"]["candidateToolchainClassifications"]["cglc"][
            "availability"
        ]
        == "unavailable",
        "required toolchain availability classification",
    )
    expect(payload["timing"]["failedRegressionCount"] == 0, "no timing failure")


def check_structural_failure_priority_over_timing(root: Path) -> None:
    result = run_tool(
        root,
        ADVISORY_BASELINE,
        STRUCTURAL_AND_TIMING_CANDIDATE,
        "--max-regression-percent",
        "10",
    )
    expect(result.returncode == 1, result.stdout)
    payload = json.loads(result.stdout)
    expect(payload["status"] == "fail", "combined structural/timing failure")
    expect(
        payload["policy"]["structural"]["failed"] is True,
        "structural side failed",
    )
    expect(payload["policy"]["timing"]["failed"] is False, "timing stays advisory")
    expect(
        payload["policy"]["failureClass"] == "structural",
        "structural failure class wins",
    )
    expect(
        payload["policy"]["failurePriority"] == ["structural"],
        "failure priority lists only hard-fail classes",
    )
    expect(
        payload["structure"]["newSkippedCases"] == ["dry-run-case::directx::debug"],
        "structural skipped case still reported",
    )
    expect(
        payload["structure"]["newOptionalUnavailableToolchainLabels"] == ["spirv-val"],
        "optional unavailable tool still accounted",
    )
    expect(
        payload["timing"]["thresholdExceededCount"] == 0,
        "metadata drift withholds timing threshold claims",
    )
    timing_observation = payload["timing"]["advisoryRegressions"][0]
    expect(
        timing_observation["case"] == "storage-buffer-compute::directx::release",
        "timing observation still reported",
    )
    expect(
        timing_observation["measuredExceedsExplicitThreshold"] is True,
        "measured threshold excess remains visible under structural failure",
    )
    expect(
        timing_observation["currentPolicyDisposition"]
        == "advisory-threshold-incomparable-metadata",
        "timing observation disposition remains advisory",
    )
    proposal_layer = payload["timing"]["thresholdProposalLayer"]
    expect(
        proposal_layer["mode"] == "report-only",
        "threshold proposal layer stays report-only under structural failure",
    )
    expect(
        proposal_layer["structural"]["failed"] is True,
        "threshold proposal layer records structural failure separately",
    )
    expect(
        proposal_layer["structural"]["failureReasons"] == ["newSkippedCases"],
        "threshold proposal layer carries structural reasons",
    )
    trend_readiness = proposal_layer["repeatedReportTrendReadiness"]
    expect(
        trend_readiness["mode"] == "report-only",
        "threshold proposal trend readiness is report-only under structural failure",
    )
    expect(
        trend_readiness["readyForRepeatedReportTrend"] is False,
        "structural failure blocks repeated-report trend readiness",
    )
    expect(
        trend_readiness["repeatedReportPairContribution"] == 0,
        "structural failure contributes no repeated report pair",
    )
    expect(
        trend_readiness["reasons"][0] == "structuralFailure",
        "structural failure is the first trend readiness blocker",
    )
    trend_requirements = proposal_requirements_by_name(trend_readiness)
    expect(
        trend_requirements["cleanStructuralComparison"]["observed"]["failureReasons"]
        == ["newSkippedCases"],
        "trend readiness mirrors structural failure reasons",
    )
    expect(
        proposal_layer["timingObservationCaseCount"] == 3,
        "threshold proposal layer still reports timing observations",
    )
    expect(
        proposal_layer["timingObservations"][0]["timingObservation"] is True,
        "threshold proposal timing observation marker",
    )
    expect(
        payload["metadata"]["baselinePolicy"]["candidate"]["skippedToolAccounting"][
            "skippedCases"
        ]
        == ["dry-run-case::directx::debug"],
        "candidate skipped cases are listed in policy metadata",
    )
    advisory_summary = payload["metadata"]["baselinePolicy"]["advisorySummary"]
    expect(
        advisory_summary["mode"] == "report-only",
        "advisory summary stays report-only under structural failure",
    )
    expect(
        advisory_summary["warningTypes"]
        == ["toolchain-metadata-drift", "skipped-tool-accounting-drift"],
        "advisory summary classifies skipped-tool/toolchain drift",
    )
    expect(
        advisory_summary["skippedToolAccountingDriftCount"] == 9,
        "advisory summary counts skipped-tool accounting fields",
    )
    expect(
        payload["policy"]["failureClass"] == "structural",
        "structural failure still outranks advisory summary warnings",
    )


def check_optional_skipped_tool_accounting(root: Path) -> None:
    result = run_tool(root, ADVISORY_BASELINE, OPTIONAL_TOOL_SKIP_CANDIDATE)
    expect(result.returncode == 1, result.stdout)
    payload = json.loads(result.stdout)
    expect(payload["status"] == "fail", "optional skipped case loses coverage")
    expect(
        payload["structure"]["newSkippedCases"] == ["dry-run-case::directx::debug"],
        "optional skipped case is visible as skipped coverage",
    )
    expect(
        payload["structure"]["newOptionalUnavailableToolchainLabels"] == ["spirv-val"],
        "optional unavailable toolchain label",
    )
    expect(
        payload["structure"]["newRequiredUnavailableToolchainLabels"] == [],
        "optional tool is not classified as required",
    )
    candidate_classification = payload["structure"][
        "candidateToolchainClassifications"
    ]["spirv-val"]
    expect(
        candidate_classification["availability"] == "unavailable",
        "optional tool availability classification",
    )
    expect(
        candidate_classification["role"] == "optional",
        "optional tool role classification",
    )
    skipped_accounting = payload["metadata"]["baselinePolicy"]["candidate"][
        "skippedToolAccounting"
    ]
    expect(
        skipped_accounting["optionalSkippedToolLabels"] == ["spirv-val"],
        "optional skipped tool label accounting",
    )
    expect(
        skipped_accounting["skippedToolCasesByTool"]["spirv-val"]
        == ["dry-run-case::directx::debug"],
        "optional skipped tool case accounting",
    )
    expect(
        skipped_accounting["skippedCases"] == ["dry-run-case::directx::debug"],
        "optional skipped case list",
    )
    expect(
        skipped_accounting["skippedCasesWithoutUnavailableTools"] == [],
        "optional skipped case is fully accounted",
    )
    comparison_dimensions = payload["metadata"]["baselinePolicy"][
        "comparisonDimensions"
    ]
    expect(
        comparison_dimensions["candidate"]["skippedToolAccounting"][
            "optionalSkippedToolLabels"
        ]
        == ["spirv-val"],
        "comparison dimensions carry optional skipped-tool labels",
    )
    expect(
        comparison_dimensions["candidate"]["skippedToolAccounting"][
            "skippedToolCasesByTool"
        ]["spirv-val"]
        == ["dry-run-case::directx::debug"],
        "comparison dimensions carry skipped-tool case mapping",
    )
    proposal_dimensions = payload["timing"]["thresholdProposalLayer"]["dimensions"]
    expect(
        proposal_dimensions["candidate"]["toolchainLabels"] == ["cglc", "spirv-val"],
        "threshold proposal dimensions carry optional skipped tool labels",
    )
    expect(
        proposal_dimensions["candidate"]["skippedToolAccounting"][
            "optionalSkippedToolLabels"
        ]
        == ["spirv-val"],
        "threshold proposal dimensions carry optional skipped-tool accounting",
    )


def check_functional_failure_visibility(root: Path) -> None:
    result = run_tool(root, ADVISORY_BASELINE, FUNCTIONAL_FAILURE_CANDIDATE)
    expect(result.returncode == 1, result.stdout)
    payload = json.loads(result.stdout)
    expect(payload["status"] == "fail", "functional failure should fail structurally")
    expect(
        payload["structure"]["candidateFunctionalFailureCases"]
        == ["storage-buffer-compute::directx::release"],
        "candidate functional failure case",
    )
    expect(
        payload["structure"]["newFunctionalFailureCases"]
        == ["storage-buffer-compute::directx::release"],
        "new functional failure case",
    )
    expect(
        "separately from timing deltas"
        in payload["structure"]["functionalFailurePolicy"],
        "functional failure policy text",
    )
    expect(
        payload["candidate"]["functionalFailureCaseCount"] == 1,
        "candidate summary functional failure count",
    )
    expect(payload["timing"]["failedRegressionCount"] == 0, "no timing failure")


def check_bad_input(root: Path, tmp: Path) -> None:
    baseline = tmp / "baseline.json"
    candidate = tmp / "bad-candidate.json"
    write_report(baseline, report([]))
    candidate.write_text("not json\n", encoding="utf-8")
    result = run_tool(root, baseline, candidate)
    expect(result.returncode == 2, result.stdout + result.stderr)
    expect("invalid report JSON" in result.stderr, "bad JSON diagnostic")


def check_report_validation_failure(root: Path, tmp: Path) -> None:
    baseline = tmp / "bad-accounting-baseline.json"
    candidate = tmp / "candidate.json"
    baseline_payload = report([])
    baseline_payload["summary"]["skippedCount"] = 1
    write_report(baseline, baseline_payload)
    write_report(candidate, report([]))
    result = run_tool(root, baseline, candidate)
    expect(result.returncode == 1, result.stderr + result.stdout)
    payload = json.loads(result.stdout)
    expect(payload["status"] == "fail", "bad accounting should fail structurally")
    expect(payload["structure"]["validationIssueCount"] == 1, "validation count")
    expect(
        payload["structure"]["validationIssues"]
        == ["baseline.summary.skippedCount=1 does not match cases (0)"],
        "validation issue text",
    )


def check_required_case_accounting_validation_failure(root: Path, tmp: Path) -> None:
    baseline = tmp / "required-accounting-baseline.json"
    candidate = tmp / "required-accounting-candidate.json"
    case_key = "storage-buffer-compute::directx::release"
    write_report(
        baseline,
        report(
            [
                timed_case(
                    case_key,
                    category="storage-buffers",
                    elapsed_ns=100,
                )
            ]
        ),
    )
    candidate_payload = report(
        [
            timed_case(
                case_key,
                category="storage-buffers",
                elapsed_ns=100,
            )
        ]
    )
    del candidate_payload["summary"]["caseCount"]
    write_report(candidate, candidate_payload)

    result = run_tool(root, baseline, candidate)
    expect(result.returncode == 1, result.stderr + result.stdout)
    payload = json.loads(result.stdout)
    expect(payload["status"] == "fail", "missing case count should fail")
    expect(
        payload["policy"]["structural"]["failureReasons"]
        == ["candidateValidationIssues"],
        "missing case count is structural report-shape failure",
    )
    expect(
        payload["structure"]["validationIssues"]
        == ["candidate.summary.caseCount is required"],
        "missing required case accounting issue text",
    )


def check_package_mode_accounting_validation_failure(root: Path, tmp: Path) -> None:
    baseline = tmp / "package-mode-accounting-baseline.json"
    candidate = tmp / "package-mode-accounting-candidate.json"
    case_key = "storage-buffer-compute::directx::release"
    case = timed_case(
        case_key,
        category="storage-buffers",
        elapsed_ns=100,
    )
    case["packageMode"] = "source"
    case["commandProfile"]["packageMode"] = "source"
    valid_payload = report([case])
    write_report(baseline, valid_payload)

    candidate_payload = copy.deepcopy(valid_payload)
    candidate_payload["summary"]["packageModeCount"] = 2
    candidate_payload["summary"]["packageModes"] = ["native"]
    candidate_payload["summary"]["caseCountByPackageMode"] = {"native": 1}
    write_report(candidate, candidate_payload)

    result = run_tool(root, baseline, candidate)
    expect(result.returncode == 1, result.stderr + result.stdout)
    payload = json.loads(result.stdout)
    expect(payload["status"] == "fail", "bad package-mode accounting should fail")
    expect(
        payload["policy"]["structural"]["failureReasons"]
        == ["candidateValidationIssues"],
        "package-mode accounting is structural report-shape failure",
    )
    expect(
        payload["structure"]["validationIssues"]
        == [
            "candidate.summary.packageModeCount=2 does not match cases (1)",
            "candidate.summary.packageModes=['native'] does not match cases "
            "(['source'])",
            "candidate.summary.caseCountByPackageMode={'native': 1} does not "
            "match cases ({'source': 1})",
        ],
        "bad package-mode accounting issue text",
    )


def check_required_opt_level_accounting_validation_failure(
    root: Path, tmp: Path
) -> None:
    baseline = tmp / "required-opt-level-accounting-baseline.json"
    candidate = tmp / "required-opt-level-accounting-candidate.json"
    case_key = "storage-buffer-compute::directx::release"
    write_report(
        baseline,
        report(
            [
                timed_case(
                    case_key,
                    category="storage-buffers",
                    elapsed_ns=100,
                )
            ]
        ),
    )
    candidate_payload = report(
        [
            timed_case(
                case_key,
                category="storage-buffers",
                elapsed_ns=100,
            )
        ]
    )
    del candidate_payload["summary"]["optLevels"]
    del candidate_payload["summary"]["caseCountByOptLevel"]
    write_report(candidate, candidate_payload)

    result = run_tool(root, baseline, candidate)
    expect(result.returncode == 1, result.stderr + result.stdout)
    payload = json.loads(result.stdout)
    expect(payload["status"] == "fail", "missing opt-level accounting should fail")
    expect(
        payload["policy"]["structural"]["failureReasons"]
        == ["candidateValidationIssues"],
        "missing opt-level accounting is structural report-shape failure",
    )
    expect(payload["structure"]["validationIssueCount"] == 2, "opt issue count")
    expect(
        payload["structure"]["validationIssues"]
        == [
            "candidate.summary.optLevels is required",
            "candidate.summary.caseCountByOptLevel is required",
        ],
        "missing opt-level accounting issue text",
    )


def check_report_shape_validation_failure(root: Path, tmp: Path) -> None:
    baseline = tmp / "shape-baseline.json"
    candidate = tmp / "shape-candidate.json"
    write_report(
        baseline,
        report(
            [
                timed_case(
                    "storage-buffer-compute::directx::release",
                    category="storage-buffers",
                    elapsed_ns=100,
                )
            ]
        ),
    )
    candidate_case = timed_case(
        "storage-buffer-compute::directx::release",
        category="storage-buffers",
        elapsed_ns=100,
    )
    del candidate_case["commandProfile"]
    del candidate_case["fixtureCategory"]
    candidate_payload = complete_policy_report([candidate_case])
    candidate_payload["summary"] = {
        "caseCategories": ["storage-buffers"],
        "caseCountByCategory": {"storage-buffers": 1},
        "optLevels": ["O2"],
        "caseCountByOptLevel": {"O2": 1},
        "caseCountByProfile": {"debug": 1},
        "caseCountByTarget": {"directx": 1},
    }
    write_report(candidate, candidate_payload)

    result = run_tool(root, baseline, candidate)
    expect(result.returncode == 1, result.stderr + result.stdout)
    payload = json.loads(result.stdout)
    expect(payload["status"] == "fail", "bad report shape should fail")
    expect(payload["structure"]["validationIssueCount"] == 8, "shape issue count")
    expect(
        payload["structure"]["validationIssues"]
        == [
            "candidate.cases[0].fixtureCategory must be a non-empty string",
            "candidate.cases[0].commandProfile must be an object",
            "candidate.summary.caseCount is required",
            "candidate.summary.commandProfiles is required",
            "candidate.summary.caseCountByCommandProfile is required",
            "candidate.summary.caseCategories=['storage-buffers'] does not match "
            "cases (['uncategorized'])",
            "candidate.summary.caseCountByCategory={'storage-buffers': 1} "
            "does not match cases ({'uncategorized': 1})",
            "candidate.summary.caseCountByProfile={'debug': 1} does not match "
            "cases ({'release': 1})",
        ],
        "shape validation issue text",
    )


def check_category_target_matrix_validation_failure(root: Path, tmp: Path) -> None:
    baseline = tmp / "category-target-matrix-baseline.json"
    candidate = tmp / "category-target-matrix-candidate.json"
    case_key = "storage-buffer-compute::directx::release"
    write_report(
        baseline,
        complete_policy_report(
            [
                timed_case(
                    case_key,
                    category="storage-buffers",
                    elapsed_ns=100,
                )
            ]
        ),
    )
    candidate_payload = complete_policy_report(
        [
            timed_case(
                case_key,
                category="storage-buffers",
                elapsed_ns=100,
            )
        ]
    )
    candidate_payload["summary"]["caseCountByCategoryTarget"] = {
        "storage-buffers": {"opengl": 1}
    }
    write_report(candidate, candidate_payload)

    result = run_tool(root, baseline, candidate)
    expect(result.returncode == 1, result.stderr + result.stdout)
    payload = json.loads(result.stdout)
    expect(payload["status"] == "fail", "stale category-target matrix should fail")
    expect(
        payload["policy"]["structural"]["failureReasons"]
        == ["candidateValidationIssues"],
        "stale category-target matrix is report-shape failure",
    )
    expect(
        payload["structure"]["validationIssues"]
        == [
            "candidate.summary.caseCountByCategoryTarget="
            "{'storage-buffers': {'opengl': 1}} does not match cases "
            "({'storage-buffers': {'directx': 1}})"
        ],
        "stale category-target matrix issue text",
    )


def check_case_dimension_metadata_validation_failure(root: Path, tmp: Path) -> None:
    baseline = tmp / "case-dimension-baseline.json"
    candidate = tmp / "case-dimension-candidate.json"
    case_key = "storage-buffer-compute::directx::release"
    write_report(
        baseline,
        complete_policy_report(
            [
                timed_case(
                    case_key,
                    category="storage-buffers",
                    elapsed_ns=100,
                )
            ]
        ),
    )
    candidate_case = timed_case(
        case_key,
        category="storage-buffers",
        elapsed_ns=125,
    )
    del candidate_case["fixtureCategory"]
    del candidate_case["profile"]
    del candidate_case["target"]
    write_report(candidate, complete_policy_report([candidate_case]))

    result = run_tool(
        root,
        baseline,
        candidate,
        "--max-regression-percent",
        "10",
        "--include-timing-deltas",
    )
    expect(result.returncode == 1, result.stderr + result.stdout)
    payload = json.loads(result.stdout)
    expect(payload["status"] == "fail", "missing case dimensions should fail")
    expect(
        payload["policy"]["failureClass"] == "structural",
        "missing case dimensions are structural",
    )
    expect(
        payload["policy"]["timing"]["failed"] is False,
        "case dimension failure does not harden timing",
    )
    expect(
        payload["timing"]["thresholdExceededCount"] == 0,
        "case dimension probe withholds malformed threshold claims",
    )
    expect(
        payload["timing"]["explicitThresholdPolicy"]["measuredThresholdExceededCases"]
        == [case_key],
        "case dimension probe still reports measured threshold evidence",
    )
    expect(
        payload["policy"]["structural"]["failureReasons"]
        == [
            "missingCategories",
            "changedCaseCategories",
            "candidateValidationIssues",
        ],
        "missing case dimensions structural reasons",
    )
    expect(
        payload["structure"]["validationIssues"]
        == [
            "candidate.cases[0].fixtureCategory must be a non-empty string",
            "candidate.cases[0].profile must be a non-empty string",
            "candidate.cases[0].target must be a non-empty string",
            "candidate.summary.caseCategories=[] does not match cases "
            "(['uncategorized'])",
            "candidate.summary.caseCountByCategory={} does not match cases "
            "({'uncategorized': 1})",
            "candidate.summary.caseCountByCategoryTarget={} does not match cases "
            "({'uncategorized': {'directx': 1}})",
            "candidate.summary.caseCountByProfile={} does not match cases "
            "({'release': 1})",
            "candidate.summary.caseCountByTarget={} does not match cases "
            "({'directx': 1})",
        ],
        "missing case dimension validation issues",
    )
    expect(
        payload["structure"]["missingCategories"] == ["storage-buffers"],
        "missing category coverage remains visible",
    )
    expect(
        payload["structure"]["missingProfiles"] == [],
        "profile label is still recoverable from the case key",
    )
    expect(
        payload["structure"]["missingTargets"] == [],
        "target label is still recoverable from the case key",
    )


def check_case_entry_validation_failure(root: Path, tmp: Path) -> None:
    baseline = tmp / "case-entry-baseline.json"
    candidate = tmp / "case-entry-candidate.json"
    case_key = "storage-buffer-compute::directx::release"
    write_report(
        baseline,
        complete_policy_report(
            [
                timed_case(
                    case_key,
                    category="storage-buffers",
                    elapsed_ns=100,
                )
            ]
        ),
    )
    candidate_case = timed_case(
        case_key,
        category="storage-buffers",
        elapsed_ns=120,
    )
    duplicate_case = timed_case(
        "fixtures/StorageBufferComputeShader.cgl::directx::release",
        category="storage-buffers",
        elapsed_ns=130,
    )
    duplicate_case["fixtureName"] = "storage-buffer-compute"
    missing_key_case = timed_case(
        case_key,
        category="storage-buffers",
        elapsed_ns=120,
    )
    missing_key_case["case"] = ""
    candidate_payload = complete_policy_report([candidate_case])
    candidate_payload["cases"].extend(
        [
            "not-a-case-object",
            duplicate_case,
            missing_key_case,
        ]
    )
    write_report(candidate, candidate_payload)

    result = run_tool(
        root,
        baseline,
        candidate,
        "--max-regression-percent",
        "10",
        "--include-timing-deltas",
    )
    expect(result.returncode == 1, result.stderr + result.stdout)
    payload = json.loads(result.stdout)
    expect(payload["status"] == "fail", "bad case entries should fail structurally")
    expect(
        payload["policy"]["failureClass"] == "structural",
        "case-entry validation is structural",
    )
    expect(payload["policy"]["timing"]["failed"] is False, "timing stays advisory")
    expect(
        payload["timing"]["timingDeltaCount"] == 1,
        "valid comparable cases still report timing deltas",
    )
    expect(
        payload["timing"]["thresholdExceededCount"] == 1,
        "timing threshold excess is still reported",
    )
    expect(
        payload["structure"]["validationIssues"]
        == [
            "candidate.cases[1] must be an object",
            "candidate.cases[2] duplicates normalized case "
            "'storage-buffer-compute::directx::release' from earlier case label "
            "'storage-buffer-compute::directx::release'",
            "candidate.cases[3].case must be a non-empty string",
        ],
        "case-entry validation issue text",
    )


def check_top_level_report_shape_validation_failure(root: Path, tmp: Path) -> None:
    baseline = tmp / "top-level-shape-baseline.json"
    candidate = tmp / "top-level-shape-candidate.json"
    write_report(baseline, report([]))
    candidate_payload = report([])
    candidate_payload["schemaVersion"] = 2
    candidate_payload["tool"] = "not_benchmark_performance_corpus"
    del candidate_payload["corpusVersion"]
    write_report(candidate, candidate_payload)

    result = run_tool(root, baseline, candidate)
    expect(result.returncode == 1, result.stderr + result.stdout)
    payload = json.loads(result.stdout)
    expect(payload["status"] == "fail", "bad top-level shape should fail")
    expect(
        payload["policy"]["structural"]["failureReasons"]
        == ["candidateValidationIssues"],
        "top-level shape is structural",
    )
    expect(
        payload["structure"]["validationIssues"]
        == [
            "candidate.schemaVersion must be 1 (got 2)",
            "candidate.tool must be 'benchmark_performance_corpus' "
            "(got 'not_benchmark_performance_corpus')",
            "candidate.corpusVersion must be a non-empty string",
        ],
        "top-level validation issue text",
    )


def check_report_config_coverage_validation_failure(root: Path, tmp: Path) -> None:
    baseline = tmp / "config-coverage-baseline.json"
    candidate = tmp / "config-coverage-candidate.json"
    case_key = "storage-buffer-compute::directx::release"
    write_report(
        baseline,
        report(
            [
                timed_case(
                    case_key,
                    category="storage-buffers",
                    elapsed_ns=100,
                )
            ]
        ),
    )
    candidate_payload = report(
        [
            timed_case(
                case_key,
                category="storage-buffers",
                elapsed_ns=100,
            )
        ]
    )
    candidate_payload["config"] = {
        "fixtures": ["storage-buffer-compute", "missing-fixture"],
        "profiles": ["debug"],
        "targets": ["directx", "opengl"],
    }
    write_report(candidate, candidate_payload)

    result = run_tool(root, baseline, candidate)
    expect(result.returncode == 1, result.stderr + result.stdout)
    payload = json.loads(result.stdout)
    expect(payload["status"] == "fail", "bad config coverage should fail")
    expect(payload["structure"]["validationIssueCount"] == 3, "coverage issue count")
    expect(
        payload["structure"]["validationIssues"]
        == [
            "candidate.config.fixtures=['storage-buffer-compute', 'missing-fixture'] "
            "does not match cases (['storage-buffer-compute'])",
            "candidate.config.profiles=['debug'] does not match cases (['release'])",
            "candidate.config.targets=['directx', 'opengl'] does not match cases "
            "(['directx'])",
        ],
        "config coverage validation issue text",
    )


def check_command_profile_label_validation_failure(root: Path, tmp: Path) -> None:
    baseline = tmp / "command-profile-label-baseline.json"
    candidate = tmp / "command-profile-label-candidate.json"
    case_key = "storage-buffer-compute::directx::release"
    write_report(
        baseline,
        report(
            [
                timed_case(
                    case_key,
                    category="storage-buffers",
                    elapsed_ns=100,
                )
            ]
        ),
    )
    candidate_case = timed_case(
        case_key,
        category="storage-buffers",
        elapsed_ns=100,
    )
    candidate_case["commandProfile"].update(
        {
            "buildType": "Release",
            "compilerConfig": "Release",
            "nativeValidationRequested": False,
            "packageMode": "source",
        }
    )
    candidate_case["nativeValidationRequested"] = True
    candidate_case["optLevel"] = "Debug"
    candidate_case["packageMode"] = "native"
    candidate_case["profileBuildType"] = "Debug"
    write_report(candidate, report([candidate_case]))

    result = run_tool(root, baseline, candidate)
    expect(result.returncode == 1, result.stderr + result.stdout)
    payload = json.loads(result.stdout)
    expect(payload["status"] == "fail", "bad profile labels should fail")
    expect(
        payload["policy"]["structural"]["failureReasons"]
        == ["candidateValidationIssues"],
        "profile label validation is structural",
    )
    expect(payload["structure"]["validationIssueCount"] == 4, "label issue count")
    expect(
        payload["structure"]["validationIssues"]
        == [
            "candidate.cases[0].optLevel='Debug' does not match "
            "commandProfile.compilerConfig 'Release'",
            "candidate.cases[0].profileBuildType='Debug' does not match "
            "commandProfile.buildType 'Release'",
            "candidate.cases[0].packageMode='native' does not match "
            "commandProfile.packageMode 'source'",
            "candidate.cases[0].nativeValidationRequested=True does not match "
            "commandProfile.nativeValidationRequested False",
        ],
        "profile label validation issue text",
    )


def check_policy_metadata_alias_validation_failure(root: Path, tmp: Path) -> None:
    baseline = tmp / "policy-alias-baseline.json"
    candidate = tmp / "policy-alias-candidate.json"
    case_key = "storage-buffer-compute::directx::release"
    baseline_payload = complete_policy_report(
        [
            timed_case(
                case_key,
                category="storage-buffers",
                elapsed_ns=100,
            )
        ]
    )
    candidate_payload = json.loads(json.dumps(baseline_payload))
    candidate_payload["metadata"] = {
        "hostLabel": "ci-linux-x86_64-pool-b",
        "optLevel": "Debug",
        "targetProfile": "crossgl-milestone6-debug",
        "toolchainVersion": "0.7.0-fixture",
    }
    write_report(baseline, baseline_payload)
    write_report(candidate, candidate_payload)

    result = run_tool(root, baseline, candidate)
    expect(result.returncode == 1, result.stderr + result.stdout)
    payload = json.loads(result.stdout)
    expect(payload["status"] == "fail", "conflicting policy aliases should fail")
    expect(
        payload["policy"]["structural"]["failureReasons"]
        == ["candidateValidationIssues"],
        "policy alias conflicts are structural report-shape failures",
    )
    expect(payload["timing"]["failedRegressionCount"] == 0, "timing remains advisory")
    expect(
        payload["structure"]["validationIssues"]
        == [
            "candidate.hostLabel policy metadata has conflicting values: "
            "baselinePolicy.hostLabel='ci-linux-x86_64-pool-a', "
            "metadata.hostLabel='ci-linux-x86_64-pool-b'",
            "candidate.targetProfile policy metadata has conflicting values: "
            "baselinePolicy.targetProfile='crossgl-milestone6-smoke', "
            "metadata.targetProfile='crossgl-milestone6-debug'",
            "candidate.optLevel policy metadata has conflicting values: "
            "baselinePolicy.optLevel='O2', metadata.optLevel='Debug'",
            "candidate.toolchainVersion policy metadata has conflicting values: "
            "baselinePolicy.toolchainVersion='0.6.0-fixture', "
            "metadata.toolchainVersion='0.7.0-fixture'",
        ],
        "policy alias validation issue text",
    )


def check_baseline_policy_field_validation_failure(root: Path, tmp: Path) -> None:
    baseline = tmp / "baseline-policy-field-baseline.json"
    candidate = tmp / "baseline-policy-field-candidate.json"
    case_key = "storage-buffer-compute::directx::release"
    baseline_payload = complete_policy_report(
        [
            timed_case(
                case_key,
                category="storage-buffers",
                elapsed_ns=100,
            )
        ]
    )
    candidate_payload = copy.deepcopy(baseline_payload)
    candidate_payload["baselinePolicy"]["hostLabel"] = 123
    candidate_payload["baselinePolicy"]["comparisonWindow"] = {
        "sampleCount": "five",
        "unit": "",
    }
    write_report(baseline, baseline_payload)
    write_report(candidate, candidate_payload)

    result = run_tool(root, baseline, candidate)
    expect(result.returncode == 1, result.stderr + result.stdout)
    payload = json.loads(result.stdout)
    expect(payload["status"] == "fail", "bad baseline policy fields should fail")
    expect(
        payload["policy"]["structural"]["failureReasons"]
        == ["candidateValidationIssues"],
        "baseline policy field validation is structural report shape",
    )
    expect(
        payload["structure"]["validationIssues"]
        == [
            "candidate.baselinePolicy.hostLabel must be a non-empty string",
            "candidate.baselinePolicy.comparisonWindow.sampleCount must be a "
            "non-negative integer",
            "candidate.baselinePolicy.comparisonWindow.warmupCount must be a "
            "non-negative integer",
            "candidate.baselinePolicy.comparisonWindow.unit must be a non-empty string",
        ],
        "baseline policy field validation issue text",
    )


def check_toolchain_metadata_shape_validation_failure(root: Path, tmp: Path) -> None:
    baseline = tmp / "toolchain-metadata-baseline.json"
    candidate = tmp / "toolchain-metadata-candidate.json"
    case_key = "storage-buffer-compute::directx::release"
    baseline_payload = complete_policy_report(
        [
            timed_case(
                case_key,
                category="storage-buffers",
                elapsed_ns=100,
            )
        ]
    )
    candidate_payload = copy.deepcopy(baseline_payload)
    candidate_payload["toolchains"] = {
        "": {"version": "0.6.0-fixture"},
        "cglc": {
            "available": "yes",
            "label": "cglc-dev",
            "optional": True,
            "required": True,
            "version": "",
        },
    }
    candidate_payload["toolAvailability"]["cglc"]["available"] = "yes"
    candidate_payload["toolAvailability"]["cglc"]["role"] = 3
    candidate_payload["toolAvailability"]["spirv-val"] = "1.3-fixture"
    write_report(baseline, baseline_payload)
    write_report(candidate, candidate_payload)

    result = run_tool(root, baseline, candidate)
    expect(result.returncode == 1, result.stderr + result.stdout)
    payload = json.loads(result.stdout)
    expect(payload["status"] == "fail", "bad toolchain metadata should fail")
    expect(
        payload["policy"]["structural"]["failureReasons"]
        == ["candidateValidationIssues"],
        "toolchain metadata shape is structural report shape",
    )
    expect(payload["timing"]["failedRegressionCount"] == 0, "timing remains advisory")
    expect(
        payload["structure"]["validationIssues"]
        == [
            "candidate.toolchains must use non-empty string labels",
            "candidate.toolchains.cglc.version must be a non-empty string",
            "candidate.toolchains.cglc.available must be a boolean or null",
            "candidate.toolchains.cglc.label='cglc-dev' does not match map key 'cglc'",
            "candidate.toolchains.cglc.optional and "
            "candidate.toolchains.cglc.required must be opposite booleans when "
            "both are present",
            "candidate.toolAvailability.cglc.role must be a non-empty string",
            "candidate.toolAvailability.cglc.available must be a boolean or null",
            "candidate.toolAvailability.spirv-val must be an object",
        ],
        "toolchain metadata validation issue text",
    )


def check_toolchain_metadata_conflict_fixture(root: Path) -> None:
    result = run_tool(
        root,
        TOOLCHAIN_METADATA_BASELINE,
        TOOLCHAIN_METADATA_CONFLICT_CANDIDATE,
    )
    expect(result.returncode == 1, result.stderr + result.stdout)
    payload = json.loads(result.stdout)
    expect(payload["status"] == "fail", "conflicting toolchain metadata should fail")
    expect(
        payload["policy"]["structural"]["failureReasons"]
        == ["candidateValidationIssues"],
        "toolchain metadata conflicts are structural report-shape failures",
    )
    expect(payload["timing"]["failedRegressionCount"] == 0, "timing remains advisory")
    expect(
        payload["structure"]["validationIssues"]
        == [
            "candidate.toolchain metadata for 'cglc' has conflicting version "
            "values: candidate.baselinePolicy.toolchainVersion='0.6.0-fixture', "
            "candidate.toolchains.cglc.version='0.7.0-fixture', "
            "candidate.toolAvailability.cglc.version='0.6.0-fixture'",
        ],
        "toolchain metadata conflict issue text",
    )


def check_skipped_tool_metadata_validation_failure(root: Path, tmp: Path) -> None:
    baseline = tmp / "skipped-tool-baseline.json"
    candidate = tmp / "skipped-tool-candidate.json"
    case_key = "storage-buffer-compute::directx::release"
    write_report(
        baseline,
        report(
            [
                timed_case(
                    case_key,
                    category="storage-buffers",
                    elapsed_ns=100,
                )
            ]
        ),
    )
    candidate_case = timed_case(
        case_key,
        category="storage-buffers",
        elapsed_ns=100,
    )
    candidate_case["skipped"] = True
    candidate_case["skipReason"] = "cglc-unavailable"
    candidate_case["status"] = "skipped"
    candidate_case["timing"] = None
    candidate_case["unavailableTools"] = ["cglc"]
    write_report(candidate, report([candidate_case]))

    result = run_tool(root, baseline, candidate)
    expect(result.returncode == 1, result.stderr + result.stdout)
    payload = json.loads(result.stdout)
    expect(payload["status"] == "fail", "missing skipped tool metadata should fail")
    expect(
        payload["structure"]["validationIssues"]
        == ["candidate.toolAvailability must describe skipped tools"],
        "skipped tool validation issue",
    )


def check_skipped_case_shape_validation_failure(root: Path, tmp: Path) -> None:
    baseline = tmp / "skipped-shape-baseline.json"
    candidate = tmp / "skipped-shape-candidate.json"
    case_key = "storage-buffer-compute::directx::release"
    write_report(
        baseline,
        report(
            [
                timed_case(
                    case_key,
                    category="storage-buffers",
                    elapsed_ns=100,
                )
            ]
        ),
    )
    candidate_case = timed_case(
        case_key,
        category="storage-buffers",
        elapsed_ns=125,
    )
    candidate_case["skipped"] = True
    candidate_case["skipReason"] = None
    candidate_case["status"] = "passed"
    candidate_case["success"] = True
    write_report(candidate, report([candidate_case]))

    result = run_tool(root, baseline, candidate)
    expect(result.returncode == 1, result.stderr + result.stdout)
    payload = json.loads(result.stdout)
    expect(payload["status"] == "fail", "bad skipped shape should fail")
    expect(
        payload["policy"]["structural"]["failureReasons"]
        == ["newSkippedCases", "candidateValidationIssues"],
        "skipped shape validation is structural",
    )
    expect(
        payload["structure"]["validationIssues"]
        == [
            "candidate.cases[0].skipReason must be a non-empty string for "
            "skipped cases",
            "candidate.cases[0].unavailableTools must name at least one "
            "unavailable tool for skipped cases",
            "candidate.cases[0].timing must be null for skipped cases",
            "candidate.cases[0].status must be 'skipped' for skipped cases",
            "candidate.cases[0].success must not be true for skipped cases",
        ],
        "skipped case validation issue text",
    )


def check_malformed_advisory_threshold_profile(root: Path, tmp: Path) -> None:
    comparator = load_comparator(root)
    baseline = tmp / "threshold-profile-baseline.json"
    candidate = tmp / "threshold-profile-candidate.json"
    write_report(baseline, report([]))
    write_report(candidate, report([]))

    def expect_profile_failure(
        profile_name: str,
        profile: object,
        diagnostic: str,
    ) -> None:
        comparator.ADVISORY_THRESHOLD_PROFILES[profile_name] = profile
        try:
            comparator.compare_reports(
                baseline,
                candidate,
                advisory_threshold_profile_name=profile_name,
                include_size_deltas=False,
                include_timing_deltas=False,
                max_regression_percent=None,
            )
        except comparator.PerformanceReportComparisonError as exc:
            expect(diagnostic in str(exc), f"malformed threshold profile: {diagnostic}")
        else:
            raise AssertionError(
                f"malformed threshold profile {profile_name!r} should fail"
            )

    expect_profile_failure(
        "dict-rule",
        comparator.AdvisoryThresholdProfile(
            name="dict-rule",
            description="Malformed dict rule threshold profile fixture.",
            rules=({"category": "storage-buffers"},),
        ),
        "rule must be an AdvisoryThresholdRule",
    )

    expect_profile_failure(
        "shadowed-specific",
        comparator.AdvisoryThresholdProfile(
            name="shadowed-specific",
            description="Malformed shadowed threshold profile fixture.",
            rules=(
                comparator.AdvisoryThresholdRule(
                    category="*",
                    profile="release",
                    max_regression_percent=comparator.Decimal("20"),
                    label="all release cases",
                ),
                comparator.AdvisoryThresholdRule(
                    category="storage-buffers",
                    profile="release",
                    max_regression_percent=comparator.Decimal("10"),
                    label="unreachable storage buffer release cases",
                ),
            ),
        ),
        "unreachable after earlier rule",
    )

    comparator.ADVISORY_THRESHOLD_PROFILES["malformed"] = (
        comparator.AdvisoryThresholdProfile(
            name="malformed",
            description="Malformed duplicate threshold profile fixture.",
            rules=(
                comparator.AdvisoryThresholdRule(
                    category="storage-buffers",
                    profile="release",
                    max_regression_percent=comparator.Decimal("10"),
                    label="first duplicate",
                ),
                comparator.AdvisoryThresholdRule(
                    category="storage-buffers",
                    profile="release",
                    max_regression_percent=comparator.Decimal("12"),
                    label="second duplicate",
                ),
            ),
        )
    )
    expect_profile_failure(
        "malformed",
        comparator.ADVISORY_THRESHOLD_PROFILES["malformed"],
        "duplicate category/profile rule",
    )

    for policy_path, diagnostic in MALFORMED_ADVISORY_THRESHOLD_POLICIES:
        result = run_tool(
            root,
            ADVISORY_BASELINE,
            ADVISORY_CANDIDATE,
            "--advisory-threshold-policy",
            str(policy_path),
        )
        expect(
            result.returncode == 2,
            f"malformed policy file should be a configuration error: {policy_path}",
        )
        expect(
            result.stdout == "",
            f"malformed policy file should not emit comparison JSON: {policy_path}",
        )
        expect(
            "performance report comparison failed:" in result.stderr
            and diagnostic in result.stderr,
            f"malformed policy file diagnostic: {diagnostic}",
        )

    valid_policy = json.loads(
        CUSTOM_ADVISORY_THRESHOLD_POLICY.read_text(encoding="utf-8")
    )
    valid_evidence_policy = json.loads(
        GENERATED_ADVISORY_THRESHOLD_POLICY.read_text(encoding="utf-8")
    )["evidencePolicy"]
    for field, diagnostic in (
        ("schemaVersion", "schemaVersion must be 1"),
        ("kind", "kind must be 'advisory-threshold-policy'"),
        ("tool", "tool must be 'compare_performance_reports'"),
        ("mode", "mode must be 'report-only'"),
        ("name", "name is required"),
        ("description", "description is required"),
        ("enforcement", "enforcement is required"),
        ("evidencePolicy", "evidencePolicy is required"),
        ("failurePolicy", "failurePolicy is required"),
        ("releaseBlockerPolicy", "releaseBlockerPolicy is required"),
        ("ruleCount", "ruleCount is required"),
    ):
        malformed_policy = copy.deepcopy(valid_policy)
        del malformed_policy[field]
        policy_path = tmp / f"missing-{field}-advisory-threshold-policy.json"
        policy_path.write_text(
            json.dumps(malformed_policy, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        result = run_tool(
            root,
            ADVISORY_BASELINE,
            ADVISORY_CANDIDATE,
            "--advisory-threshold-policy",
            str(policy_path),
        )
        expect(
            result.returncode == 2,
            f"missing policy metadata should be a configuration error: {field}",
        )
        expect(
            result.stdout == "",
            f"missing policy metadata should not emit comparison JSON: {field}",
        )
        expect(
            "performance report comparison failed:" in result.stderr
            and diagnostic in result.stderr,
            f"missing policy metadata diagnostic: {field}",
        )

    malformed_policy_cases = (
        (
            "bad-rule-count",
            {"ruleCount": 2},
            "ruleCount must match rules length (1)",
        ),
        (
            "hard-fail-enforcement",
            {
                "enforcement": {
                    **valid_policy["enforcement"],
                    "enforced": True,
                }
            },
            "enforcement.enforced must be False",
        ),
        (
            "wrong-enforcement-policy",
            {
                "enforcement": {
                    **valid_policy["enforcement"],
                    "policy": "Timing thresholds are enforced by this file.",
                }
            },
            "enforcement.policy must match the comparator report-only enforcement policy",
        ),
        (
            "empty-rule-label",
            {"rules": [{**valid_policy["rules"][0], "label": ""}]},
            "rules[0].label must be a non-empty string",
        ),
        (
            "wrong-rule-specificity",
            {
                "rules": [
                    {
                        **valid_policy["rules"][0],
                        "ruleSpecificity": "fallback",
                    }
                ]
            },
            "rules[0].ruleSpecificity must be 'category-profile'",
        ),
        (
            "empty-name",
            {"name": ""},
            "name must be a non-empty string",
        ),
        (
            "hard-fail-evidence-policy",
            {
                "evidencePolicy": {
                    **valid_evidence_policy,
                    "requiresComparableMetadata": False,
                }
            },
            "evidencePolicy.requiresComparableMetadata must be True",
        ),
        (
            "wrong-evidence-policy-text",
            {
                "evidencePolicy": {
                    **valid_evidence_policy,
                    "metadataComparabilityPolicy": "metadata is optional",
                }
            },
            "evidencePolicy.metadataComparabilityPolicy must match the comparator metadata comparability policy",
        ),
        (
            "empty-evidence-policy-text",
            {
                "evidencePolicy": {
                    **valid_evidence_policy,
                    "policy": "",
                }
            },
            "evidencePolicy.policy must be a non-empty string",
        ),
        (
            "empty-failure-policy",
            {"failurePolicy": ""},
            "failurePolicy must be a non-empty string",
        ),
        (
            "wrong-failure-policy",
            {"failurePolicy": "report-only unless the policy says otherwise"},
            "failurePolicy must match the comparator report-only failure policy",
        ),
    )
    for name, updates, diagnostic in malformed_policy_cases:
        malformed_policy = copy.deepcopy(valid_policy)
        malformed_policy.update(updates)
        policy_path = tmp / f"{name}-advisory-threshold-policy.json"
        policy_path.write_text(
            json.dumps(malformed_policy, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        result = run_tool(
            root,
            ADVISORY_BASELINE,
            ADVISORY_CANDIDATE,
            "--advisory-threshold-policy",
            str(policy_path),
        )
        expect(
            result.returncode == 2,
            f"malformed policy field should be a configuration error: {name}",
        )
        expect(
            result.stdout == "",
            f"malformed policy field should not emit comparison JSON: {name}",
        )
        expect(
            "performance report comparison failed:" in result.stderr
            and diagnostic in result.stderr,
            f"malformed policy field diagnostic: {name}",
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
        help="Run the same synthetic self-test suite explicitly.",
    )
    args = parser.parse_args()
    root = args.root.resolve()

    with tempfile.TemporaryDirectory(prefix="crossgl-perf-compare-check-") as tmp_name:
        tmp = Path(tmp_name)
        check_runner_baseline_policy_metadata(root, tmp)
        check_advisory_default(root)
        check_native_optimization_evidence_accounting(root, tmp)
        check_invalid_native_optimization_evidence_probe(root, tmp)
        check_native_optimization_summary_validation(root, tmp)
        check_native_artifact_descriptor_optimization_evidence_drift(root, tmp)
        check_manifest_artifact_kind_evidence(root, tmp)
        check_comparable_repeated_threshold_evidence(root, tmp)
        check_producer_policy_claim_provenance(root, tmp)
        check_advisory_window_fixture_non_regression(root)
        check_custom_advisory_threshold_policy(root, tmp)
        check_target_backend_advisory_threshold_policy(root, tmp)
        check_measurement_window_sample_evidence(root, tmp)
        check_partial_case_identity_withholds_threshold_claim(root, tmp)
        check_timing_window_validation_failure(root, tmp)
        check_measurement_window_validation_failure(root, tmp)
        check_timing_run_evidence_validation_failure(root, tmp)
        check_skipped_tool_accounting_validation_failure(root, tmp)
        check_missing_context_metadata_advisory_probe(root, tmp)
        check_advisory_profile_rule_matching(root, tmp)
        check_incomplete_threshold_baseline_fixture(root)
        check_normalized_case_identity(root, tmp)
        check_fractional_threshold_ceiling(root, tmp)
        check_pairwise_stability_evidence(root, tmp)
        check_changed_case_category_structural_failure(root, tmp)
        check_aggregate_report_only(root, tmp)
        check_aggregate_native_optimization_accounting(root, tmp)
        check_aggregate_stability_evidence(root, tmp)
        check_structural_coverage_failure(root)
        check_skip_toolchain_failure(root)
        check_structural_failure_priority_over_timing(root)
        check_optional_skipped_tool_accounting(root)
        check_functional_failure_visibility(root)
        check_bad_input(root, tmp)
        check_report_validation_failure(root, tmp)
        check_required_case_accounting_validation_failure(root, tmp)
        check_package_mode_accounting_validation_failure(root, tmp)
        check_required_opt_level_accounting_validation_failure(root, tmp)
        check_report_shape_validation_failure(root, tmp)
        check_category_target_matrix_validation_failure(root, tmp)
        check_case_dimension_metadata_validation_failure(root, tmp)
        check_case_entry_validation_failure(root, tmp)
        check_top_level_report_shape_validation_failure(root, tmp)
        check_report_config_coverage_validation_failure(root, tmp)
        check_command_profile_label_validation_failure(root, tmp)
        check_policy_metadata_alias_validation_failure(root, tmp)
        check_baseline_policy_field_validation_failure(root, tmp)
        check_toolchain_metadata_shape_validation_failure(root, tmp)
        check_toolchain_metadata_conflict_fixture(root)
        check_skipped_tool_metadata_validation_failure(root, tmp)
        check_skipped_case_shape_validation_failure(root, tmp)
        check_malformed_advisory_threshold_profile(root, tmp)

    print("validated performance report comparator")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
