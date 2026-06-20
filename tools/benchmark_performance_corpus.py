#!/usr/bin/env python3
"""Run named CrossGL compiler performance corpus measurements."""

from __future__ import annotations

import argparse
import json
import os
import platform
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from time import perf_counter_ns
from typing import Any

from benchmark_build_modes import DEFAULT_PROFILE, PROFILE_ORDER, get_profile


SCHEMA_VERSION = 1
TOOL_NAME = "benchmark_performance_corpus"
REPORT_PROFILE = "milestone6-advisory-v1"
DEFAULT_CORPUS = "milestone6-smoke"
CORPUS_VERSION = "milestone6-smoke-v1"
DEFAULT_TARGETS = ("directx", "opengl")
KNOWN_TARGETS = ("directx", "metal", "opengl", "vulkan")
REPORT_POLICY = {
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
TIMING_ADVISORY_EVIDENCE_POLICY = (
    "Timing threshold claims require repeated baseline and candidate samples, "
    "comparable host/toolchain/target-profile/optimization metadata, explicit "
    "timed-case identity, and stable report-only classification. The corpus "
    "runner records provenance only; it does not emit hard timing gates."
)
TIMING_ADVISORY_RELEASE_BLOCKER_POLICY = (
    "Timing advisory thresholds are report-only and are not release blockers "
    "without explicit owner approval."
)
TIMING_BASELINE_STABILITY_POLICY = (
    "No checked-in stable multi-run timing baseline is available for this "
    "runner report, so numeric thresholds are intentionally omitted."
)
REQUIRED_BASELINE_PROVENANCE_FIELDS = (
    "hostLabel",
    "hostClass",
    "targetProfile",
    "optLevel",
    "comparisonWindow",
    "runtimeEnvironment",
    "toolchains",
)
REQUIRED_THRESHOLD_CASE_IDENTITY_FIELDS = (
    "fixtureName",
    "target",
    "profile",
    "optLevel",
)
PASS_TRACE_SIDECAR_PATH = "ir/hir-pass-trace.json"
PASS_TRACE_KIND = "hir-pass-trace"
DEFAULT_MANIFEST_PATH = (
    Path(__file__).resolve().parents[1]
    / "tests"
    / "performance"
    / "performance_corpus_manifest.json"
)


class CorpusBenchmarkError(RuntimeError):
    """Raised for user-facing corpus benchmark failures."""


def parse_non_negative_int(value: str) -> int:
    try:
        parsed = int(value, 10)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(f"expected integer, got {value!r}") from exc
    if parsed < 0:
        raise argparse.ArgumentTypeError(f"expected non-negative integer, got {value}")
    return parsed


def parse_positive_int(value: str) -> int:
    parsed = parse_non_negative_int(value)
    if parsed == 0:
        raise argparse.ArgumentTypeError("expected positive integer, got 0")
    return parsed


@dataclass(frozen=True)
class CorpusFixture:
    name: str
    path: str
    category: str
    description: str
    targets: tuple[str, ...] = DEFAULT_TARGETS

    def to_json(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "path": self.path,
            "category": self.category,
            "description": self.description,
            "targets": list(self.targets),
        }


def load_corpus_manifest(manifest_path: Path = DEFAULT_MANIFEST_PATH) -> dict[str, Any]:
    try:
        payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise CorpusBenchmarkError(
            f"could not read corpus manifest: {manifest_path}"
        ) from exc
    except json.JSONDecodeError as exc:
        raise CorpusBenchmarkError(
            f"invalid corpus manifest JSON at line {exc.lineno} column {exc.colno}"
        ) from exc

    if payload.get("schemaVersion") != SCHEMA_VERSION:
        raise CorpusBenchmarkError(
            f"unsupported corpus manifest schemaVersion: {payload.get('schemaVersion')!r}"
        )
    if payload.get("defaultCorpus") != DEFAULT_CORPUS:
        raise CorpusBenchmarkError(
            f"corpus manifest defaultCorpus must be {DEFAULT_CORPUS!r}"
        )
    return payload


def load_corpora(
    manifest_path: Path = DEFAULT_MANIFEST_PATH,
) -> dict[str, tuple[CorpusFixture, ...]]:
    payload = load_corpus_manifest(manifest_path)
    corpora: dict[str, tuple[CorpusFixture, ...]] = {}
    for corpus in payload.get("corpora", []):
        name = corpus.get("name")
        if not isinstance(name, str) or not name:
            raise CorpusBenchmarkError("corpus manifest contains an unnamed corpus")
        fixtures: list[CorpusFixture] = []
        seen: set[str] = set()
        for fixture in corpus.get("fixtures", []):
            fixture_name = fixture.get("name")
            if not isinstance(fixture_name, str) or not fixture_name:
                raise CorpusBenchmarkError(
                    f"corpus {name!r} contains an unnamed fixture"
                )
            if fixture_name in seen:
                raise CorpusBenchmarkError(
                    f"corpus {name!r} contains duplicate fixture {fixture_name!r}"
                )
            seen.add(fixture_name)
            targets = tuple(fixture.get("targets", DEFAULT_TARGETS))
            unknown_targets = [
                target for target in targets if target not in KNOWN_TARGETS
            ]
            if unknown_targets:
                raise CorpusBenchmarkError(
                    f"fixture {fixture_name!r} has unknown target(s): "
                    + ", ".join(unknown_targets)
                )
            fixtures.append(
                CorpusFixture(
                    name=fixture_name,
                    path=fixture["path"],
                    category=fixture["category"],
                    description=fixture["description"],
                    targets=targets,
                )
            )
        corpora[name] = tuple(fixtures)
    if DEFAULT_CORPUS not in corpora:
        raise CorpusBenchmarkError(
            f"corpus manifest does not define default corpus {DEFAULT_CORPUS!r}"
        )
    return corpora


CORPORA = load_corpora()


def path_text(path: Path) -> str:
    return path.as_posix()


def display_path(path: Path, root: Path) -> str:
    resolved = path.resolve()
    try:
        return path_text(resolved.relative_to(root))
    except ValueError:
        return path_text(resolved)


def report_path(value: Path | str, root: Path) -> str:
    if isinstance(value, Path):
        return display_path(value, root)
    return value


def corpus_document(corpus_names: list[str] | None = None) -> dict[str, Any]:
    selected = corpus_names or sorted(CORPORA)
    return {
        "schemaVersion": SCHEMA_VERSION,
        "tool": TOOL_NAME,
        "corpusVersion": CORPUS_VERSION,
        "defaultCorpus": DEFAULT_CORPUS,
        "corpora": [
            {
                "name": name,
                "fixtures": [fixture.to_json() for fixture in CORPORA[name]],
            }
            for name in selected
        ],
    }


def resolve_cglc(
    value: str | None, root: Path, *, require_existing: bool
) -> Path | str:
    requested = value or os.environ.get("CGLC") or "cglc"
    looks_like_path = Path(requested).is_absolute() or any(
        separator and separator in requested for separator in (os.sep, os.altsep)
    )

    if looks_like_path:
        candidate = Path(requested).expanduser()
        if not candidate.is_absolute():
            candidate = root / candidate
        path = candidate.resolve()
    elif require_existing:
        found = shutil.which(requested)
        if found is None:
            raise CorpusBenchmarkError(
                f"missing cglc executable {requested!r}; pass --cglc /path/to/cglc "
                "or add cglc to PATH"
            )
        path = Path(found).resolve()
    else:
        return requested

    if require_existing:
        if not path.is_file():
            raise CorpusBenchmarkError(f"missing cglc executable: {path}")
        if not os.access(path, os.X_OK):
            raise CorpusBenchmarkError(f"cglc is not executable: {path}")
    return path


def parse_repeated(values: list[str] | None, default: tuple[str, ...]) -> list[str]:
    parsed: list[str] = []
    seen: set[str] = set()
    for value in values or list(default):
        for item in value.split(","):
            item = item.strip()
            if not item or item in seen:
                continue
            seen.add(item)
            parsed.append(item)
    return parsed


def parse_profiles(values: list[str] | None) -> list[str]:
    profiles = parse_repeated(values, (DEFAULT_PROFILE,))
    for profile in profiles:
        try:
            get_profile(profile)
        except ValueError as exc:
            raise CorpusBenchmarkError(str(exc)) from exc
    return profiles


def parse_targets(values: list[str] | None) -> list[str]:
    targets = parse_repeated(values, DEFAULT_TARGETS)
    unknown = [target for target in targets if target not in KNOWN_TARGETS]
    if unknown:
        choices = ", ".join(KNOWN_TARGETS)
        raise CorpusBenchmarkError(
            f"unknown target(s): {', '.join(unknown)}; choose {choices}"
        )
    return targets


def selected_fixtures(
    corpus_name: str, fixture_names: list[str] | None
) -> list[CorpusFixture]:
    try:
        fixtures = list(CORPORA[corpus_name])
    except KeyError as exc:
        choices = ", ".join(sorted(CORPORA))
        raise CorpusBenchmarkError(
            f"unknown corpus {corpus_name!r}; choose {choices}"
        ) from exc

    if not fixture_names:
        return fixtures

    wanted = set(parse_repeated(fixture_names, ()))
    selected = [fixture for fixture in fixtures if fixture.name in wanted]
    missing = sorted(wanted - {fixture.name for fixture in selected})
    if missing:
        raise CorpusBenchmarkError(f"unknown fixture(s): {', '.join(missing)}")
    return selected


def fixture_path(root: Path, fixture: CorpusFixture) -> Path:
    path = (root / fixture.path).resolve()
    if not path.is_file():
        raise CorpusBenchmarkError(f"corpus fixture does not exist: {fixture.path}")
    return path


def safe_case_stem(fixture: CorpusFixture, target: str, profile: str) -> str:
    return f"{fixture.name}-{target}-{profile}".replace("/", "-")


def output_path_for(
    work_dir: Path, fixture: CorpusFixture, target: str, profile: str
) -> Path:
    return work_dir / f"{safe_case_stem(fixture, target, profile)}.cglb"


def command_profile(profile_name: str) -> dict[str, Any]:
    profile = get_profile(profile_name)
    return {
        "buildType": profile.build_type,
        "cglcArgs": list(profile.cglc_args),
        "compilerConfig": profile.compiler_config,
        "environment": [
            {"name": name, "value": value} for name, value in profile.environment
        ],
        "name": profile.name,
        "nativeValidationRequested": profile.native_validation,
        "packageMode": profile.package_mode,
    }


def profile_requests_pass_trace(profile_name: str) -> bool:
    return "--debug-ir" in get_profile(profile_name).cglc_args


def profile_hir_optimization_level(profile_name: str) -> str:
    args = list(get_profile(profile_name).cglc_args)
    try:
        index = args.index("--opt-level")
    except ValueError:
        return "O1"
    if index + 1 < len(args) and args[index + 1]:
        return args[index + 1]
    return "O1"


def common_opt_level(profile_names: list[str]) -> str:
    levels = sorted(
        {get_profile(profile_name).compiler_config for profile_name in profile_names}
    )
    if len(levels) == 1:
        return levels[0]
    return "mixed:" + ",".join(levels)


def runtime_environment_metadata() -> dict[str, str]:
    return {
        "machine": platform.machine(),
        "platform": platform.platform(),
        "pythonExecutable": Path(sys.executable).resolve().as_posix(),
        "pythonImplementation": platform.python_implementation(),
        "pythonVersion": platform.python_version(),
        "system": platform.system(),
        "systemRelease": platform.release(),
    }


def stable_label_part(value: str | None) -> str:
    if not value:
        return "unknown"
    normalized = "".join(
        character.lower() if character.isalnum() else "-" for character in value.strip()
    ).strip("-")
    return normalized or "unknown"


def default_host_class() -> str:
    system = stable_label_part(platform.system())
    machine = stable_label_part(platform.machine())
    return f"{system}-{machine}"


def parse_policy_value(value: str | None) -> Any:
    if value is None:
        return None
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return value


def build_baseline_policy(
    *,
    corpus_name: str,
    profiles: list[str],
    repeat: int,
    warmup: int,
    dry_run: bool,
    skipped: bool,
    host_label: str | None,
    host_class: str | None,
    target_profile: str | None,
    opt_level: str | None,
    comparison_window: Any,
    toolchain_label: str | None,
    toolchain_version: str | None,
) -> dict[str, Any]:
    policy: dict[str, Any] = {}
    if host_label:
        policy["hostLabel"] = host_label
    policy["hostClass"] = host_class or default_host_class()
    policy["targetProfile"] = target_profile or f"crossgl-{corpus_name}"
    policy["optLevel"] = opt_level or common_opt_level(profiles)
    if comparison_window is not None:
        policy["comparisonWindow"] = comparison_window
    else:
        policy["comparisonWindow"] = {
            "sampleCount": 0 if dry_run or skipped else repeat,
            "unit": "elapsedNs",
            "warmupCount": 0 if dry_run or skipped else warmup,
        }
    policy["toolchainLabel"] = toolchain_label or "cglc"
    if toolchain_version:
        policy["toolchainVersion"] = toolchain_version
    return policy


def build_toolchain_metadata(
    *,
    baseline_policy: dict[str, Any] | None,
    available: bool | None,
    status: str,
    toolchain_version: str | None,
) -> dict[str, dict[str, Any]] | None:
    if baseline_policy is None:
        return None
    label = baseline_policy.get("toolchainLabel")
    if not isinstance(label, str) or not label:
        return None
    entry: dict[str, Any] = {
        "available": available,
        "role": "required",
        "status": status,
    }
    version = toolchain_version or baseline_policy.get("toolchainVersion")
    if isinstance(version, str) and version:
        entry["version"] = version
    return {label: entry}


def default_comparison_window(
    *, dry_run: bool, skipped: bool, repeat: int, warmup: int
) -> dict[str, Any]:
    return {
        "sampleCount": 0 if dry_run or skipped else repeat,
        "unit": "elapsedNs",
        "warmupCount": 0 if dry_run or skipped else warmup,
    }


def timing_window_accounting(
    cases: list[dict[str, Any]], measurement_window: dict[str, Any]
) -> dict[str, Any]:
    sample_count = measurement_window["sampleCount"]
    warmup_count = measurement_window["warmupCount"]
    timed_cases = [case for case in cases if isinstance(case["timing"], dict)]
    measured_run_count = sum(len(case["timing"]["runs"]) for case in timed_cases)
    warmup_run_count = sum(len(case["timing"]["warmups"]) for case in timed_cases)
    mismatched_cases = sorted(
        case["case"]
        for case in timed_cases
        if case["timing"].get("sampleCount") != sample_count
        or case["timing"].get("warmupCount") != warmup_count
        or len(case["timing"].get("runs", [])) != sample_count
        or len(case["timing"].get("warmups", [])) != warmup_count
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


def build_report_metadata(
    *,
    corpus_name: str,
    profiles: list[str],
    cases: list[dict[str, Any]],
    repeat: int,
    warmup: int,
    dry_run: bool,
    skipped: bool,
    baseline_policy: dict[str, Any] | None,
) -> dict[str, Any]:
    policy = baseline_policy or {}
    measurement_window = default_comparison_window(
        dry_run=dry_run,
        skipped=skipped,
        repeat=repeat,
        warmup=warmup,
    )
    return {
        "benchmarkProfile": REPORT_PROFILE,
        "caseCategories": sorted({case["fixtureCategory"] for case in cases}),
        "commandProfiles": [command_profile(profile) for profile in profiles],
        "comparisonWindow": policy.get("comparisonWindow") or measurement_window,
        "dryRun": dry_run,
        "measurementWindow": measurement_window,
        "optLevel": policy.get("optLevel") or common_opt_level(profiles),
        "passTraceProvenance": {
            "artifactKind": PASS_TRACE_KIND,
            "captureMode": "package-sidecar",
            "commandFlag": "--debug-ir",
            "manifestPolicy": "non-manifest-sidecar",
            "reportPolicy": "report-only",
            "schemaVersion": SCHEMA_VERSION,
            "sidecarPath": PASS_TRACE_SIDECAR_PATH,
        },
        "reportPolicy": dict(REPORT_POLICY),
        "runtimeEnvironment": runtime_environment_metadata(),
        "targetProfile": policy.get("targetProfile") or f"crossgl-{corpus_name}",
        "timedCaseCount": sum(1 for case in cases if case["timing"] is not None),
        "tool": {
            "corpusVersion": CORPUS_VERSION,
            "name": TOOL_NAME,
            "schemaVersion": SCHEMA_VERSION,
        },
    }


def add_policy_metadata_mirrors(
    report: dict[str, Any],
    baseline_policy: dict[str, Any] | None,
    tool_availability: dict[str, Any],
    toolchains: dict[str, dict[str, Any]] | None,
) -> None:
    if baseline_policy is None:
        return

    metadata = report["metadata"]
    for field in (
        "hostClass",
        "hostLabel",
        "toolchainLabel",
        "toolchainVersion",
    ):
        value = baseline_policy.get(field)
        if isinstance(value, str) and value:
            metadata[field] = value

    host: dict[str, Any] = {}
    if isinstance(baseline_policy.get("hostLabel"), str):
        host["label"] = baseline_policy["hostLabel"]
    if isinstance(baseline_policy.get("hostClass"), str):
        host["class"] = baseline_policy["hostClass"]
    if host:
        report["host"] = host

    label = baseline_policy.get("toolchainLabel")
    if not isinstance(label, str) or not label:
        return
    entry = (toolchains or {}).get(label) or tool_availability.get(label)
    if not isinstance(entry, dict):
        entry = {}
    toolchain: dict[str, Any] = {"label": label}
    for field in ("available", "status", "version"):
        value = entry.get(field)
        if value is not None:
            toolchain[field] = value
    if "version" not in toolchain:
        version = baseline_policy.get("toolchainVersion")
        if isinstance(version, str) and version:
            toolchain["version"] = version
    report["toolchain"] = toolchain


def display_command(
    input_path: str, target: str, output_path: str, profile_name: str
) -> list[str]:
    profile = get_profile(profile_name)
    return [
        "<cglc>",
        "build",
        input_path,
        "--target",
        target,
        "--output",
        output_path,
        "--diagnostics-json",
        *profile.cglc_args,
    ]


def compiler_command(
    compiler_path: Path,
    input_path: str,
    target: str,
    output_path: Path,
    profile_name: str,
    root: Path,
) -> list[str]:
    profile = get_profile(profile_name)
    return [
        path_text(compiler_path),
        "build",
        input_path,
        "--target",
        target,
        "--output",
        path_text(output_path),
        "--diagnostics-json",
        *profile.cglc_args,
    ]


def run_once(
    command: list[str],
    root: Path,
    env: dict[str, str],
    iteration: int,
) -> tuple[dict[str, int], bytes, bytes]:
    started_ns = perf_counter_ns()
    result = subprocess.run(
        command,
        cwd=root,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    duration_ns = perf_counter_ns() - started_ns
    stdout = result.stdout
    stderr = result.stderr
    return (
        {
            "durationNs": duration_ns,
            "exitStatus": result.returncode,
            "iteration": iteration,
            "outputBytes": len(stdout) + len(stderr),
            "stderrBytes": len(stderr),
            "stdoutBytes": len(stdout),
        },
        stdout,
        stderr,
    )


def summarize_timing_runs(
    *,
    runs: list[dict[str, int]],
    warmups: list[dict[str, int]],
) -> dict[str, Any]:
    durations = sorted(run["durationNs"] for run in runs)
    median_ns = durations[len(durations) // 2]
    return {
        "elapsedNs": median_ns,
        "exitStatuses": sorted({run["exitStatus"] for run in runs}),
        "maxNs": durations[-1],
        "meanNs": sum(durations) // len(durations),
        "medianNs": median_ns,
        "minNs": durations[0],
        "runs": runs,
        "sampleCount": len(runs),
        "warmupCount": len(warmups),
        "warmups": warmups,
    }


def run_timed_command(
    compiler_path: Path,
    input_path: str,
    target: str,
    output_path: Path,
    profile_name: str,
    root: Path,
    warmup: int,
    repeat: int,
) -> tuple[dict[str, Any], int, bytes, bytes]:
    profile = get_profile(profile_name)
    command = compiler_command(
        compiler_path,
        input_path,
        target,
        output_path,
        profile_name,
        root,
    )
    env = os.environ.copy()
    env.update(dict(profile.environment))

    warmups = [
        run_once(command, root, env, iteration)[0] for iteration in range(1, warmup + 1)
    ]
    measured: list[dict[str, int]] = []
    last_stdout = b""
    last_stderr = b""
    for iteration in range(1, repeat + 1):
        run, stdout, stderr = run_once(command, root, env, iteration)
        measured.append(run)
        last_stdout = stdout
        last_stderr = stderr

    timing = summarize_timing_runs(runs=measured, warmups=warmups)
    selected_exit_status = next(
        (run["exitStatus"] for run in measured if run["exitStatus"] != 0),
        measured[-1]["exitStatus"],
    )
    return timing, selected_exit_status, last_stdout, last_stderr


def diagnostic_summary(stdout: bytes, stderr: bytes) -> dict[str, Any]:
    summary: dict[str, Any] = {
        "schemaVersion": None,
        "total": 0,
        "bySeverity": {},
        "codes": [],
        "stdoutBytes": len(stdout),
        "stderrBytes": len(stderr),
        "stderrLines": len(stderr.decode("utf-8", errors="replace").splitlines()),
        "parseError": None,
    }
    if not stdout:
        return summary

    try:
        payload = json.loads(stdout.decode("utf-8"))
    except json.JSONDecodeError as exc:
        summary["parseError"] = f"{exc.msg} at line {exc.lineno} column {exc.colno}"
        return summary

    diagnostics = payload.get("diagnostics", [])
    by_severity: dict[str, int] = {}
    codes: set[str] = set()
    for diagnostic in diagnostics:
        severity = diagnostic.get("severity", "unknown")
        by_severity[severity] = by_severity.get(severity, 0) + 1
        code = diagnostic.get("code")
        if code:
            codes.add(code)

    summary["schemaVersion"] = payload.get("schemaVersion")
    summary["total"] = len(diagnostics)
    summary["bySeverity"] = dict(sorted(by_severity.items()))
    summary["codes"] = sorted(codes)
    return summary


def artifact_file_records(package_path: Path) -> list[dict[str, Any]]:
    if package_path.is_file():
        return [{"path": package_path.name, "bytes": package_path.stat().st_size}]
    if not package_path.is_dir():
        return []

    records: list[dict[str, Any]] = []
    for path in sorted(package_path.rglob("*")):
        if not path.is_file():
            continue
        records.append(
            {
                "path": path.relative_to(package_path).as_posix(),
                "bytes": path.stat().st_size,
            }
        )
    return records


def read_json_file(path: Path) -> dict[str, Any] | None:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return payload if isinstance(payload, dict) else None


def optional_string(value: Any) -> str | None:
    return value if isinstance(value, str) else None


def optional_int(value: Any) -> int | None:
    return value if isinstance(value, int) and not isinstance(value, bool) else None


def manifest_package_mode(manifest: dict[str, Any] | None) -> str | None:
    if not isinstance(manifest, dict):
        return None
    artifacts = manifest.get("artifacts")
    if not isinstance(artifacts, dict):
        return None
    return "source-package" if "nativeBinaryStatus" in artifacts else "native"


def manifest_artifact_records(
    package_path: Path, manifest: dict[str, Any] | None
) -> list[dict[str, Any]]:
    if not isinstance(manifest, dict):
        return []
    artifacts = manifest.get("artifacts")
    if not isinstance(artifacts, dict):
        return []

    records: list[dict[str, Any]] = []
    for kind, value in sorted(artifacts.items()):
        if not isinstance(value, str) or kind == "nativeBinaryStatus":
            continue
        artifact_path = package_path / value
        exists = artifact_path.is_file()
        records.append(
            {
                "kind": kind,
                "path": value,
                "exists": exists,
                "bytes": artifact_path.stat().st_size if exists else None,
            }
        )
    return records


def empty_native_artifact_descriptor_summary(
    *, declared: bool = False, path: str | None = None
) -> dict[str, Any]:
    return {
        "available": False,
        "declared": declared,
        "optimizationEvidence": None,
        "optimizationEvidenceStatus": (
            "declared-native-artifact-descriptor-missing"
            if declared
            else "native-artifact-descriptor-not-declared"
        ),
        "optimizationLevel": None,
        "parseError": None,
        "path": path,
        "schemaVersion": None,
        "target": None,
    }


def native_artifact_descriptor_optimization_evidence_status(
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


def finalize_native_artifact_descriptor_summary(
    summary: dict[str, Any],
) -> dict[str, Any]:
    summary["optimizationEvidenceStatus"] = (
        native_artifact_descriptor_optimization_evidence_status(summary)
    )
    return summary


def native_artifact_descriptor_summary(
    package_path: Path, manifest: dict[str, Any] | None
) -> dict[str, Any]:
    if not isinstance(manifest, dict):
        return empty_native_artifact_descriptor_summary()
    artifacts = manifest.get("artifacts")
    if not isinstance(artifacts, dict):
        return empty_native_artifact_descriptor_summary()

    descriptor_path_value = artifacts.get("nativeArtifactDescriptor")
    if not isinstance(descriptor_path_value, str) or not descriptor_path_value:
        return empty_native_artifact_descriptor_summary()

    summary = empty_native_artifact_descriptor_summary(
        declared=True, path=descriptor_path_value
    )
    descriptor_path = package_path / descriptor_path_value
    if not descriptor_path.is_file():
        return summary

    summary["available"] = True
    try:
        payload = json.loads(descriptor_path.read_text(encoding="utf-8"))
    except OSError as exc:
        summary["parseError"] = f"read-error: {exc}"
        return finalize_native_artifact_descriptor_summary(summary)
    except json.JSONDecodeError:
        summary["parseError"] = "invalid-json"
        return finalize_native_artifact_descriptor_summary(summary)

    if not isinstance(payload, dict):
        summary["parseError"] = "expected-json-object"
        return finalize_native_artifact_descriptor_summary(summary)

    evidence = payload.get("optimizationEvidence")
    summary.update(
        {
            "optimizationEvidence": evidence if isinstance(evidence, dict) else None,
            "optimizationLevel": optional_string(payload.get("optimizationLevel")),
            "schemaVersion": optional_int(payload.get("schemaVersion")),
            "target": optional_string(payload.get("target")),
        }
    )
    return finalize_native_artifact_descriptor_summary(summary)


def empty_native_profile_summary(
    *, declared: bool = False, path: str | None = None
) -> dict[str, Any]:
    return {
        "api": None,
        "available": False,
        "declared": declared,
        "optimization": None,
        "optimizationEvidenceStatus": (
            "declared-native-profile-missing"
            if declared
            else "native-profile-not-declared"
        ),
        "parseError": None,
        "path": path,
        "profileName": None,
        "schemaVersion": None,
        "target": None,
    }


def native_optimization_evidence_status_from_profile(
    profile: dict[str, Any] | None,
) -> str:
    if not isinstance(profile, dict):
        return "native-profile-not-declared"
    optimization = profile.get("optimization")
    if not isinstance(optimization, dict):
        if profile.get("declared") is True and profile.get("available") is not True:
            return "declared-native-profile-missing"
        if profile.get("available") is True and profile.get("parseError") is not None:
            return "unparsable-native-profile"
        if profile.get("available") is True:
            return "missing-debug-optimization"
        return "native-profile-not-declared"
    status = optimization.get("status")
    if isinstance(status, str) and status:
        return "known-status"
    if profile.get("available") is True or profile.get("declared") is True:
        return "optimization-without-status"
    if profile.get("declared") is True and profile.get("available") is not True:
        return "declared-native-profile-missing"
    if profile.get("available") is True and profile.get("parseError") is not None:
        return "unparsable-native-profile"
    if profile.get("available") is True:
        return "missing-debug-optimization"
    return "native-profile-not-declared"


def finalize_native_profile_summary(summary: dict[str, Any]) -> dict[str, Any]:
    summary["optimizationEvidenceStatus"] = (
        native_optimization_evidence_status_from_profile(summary)
    )
    return summary


def native_profile_summary(
    package_path: Path, manifest: dict[str, Any] | None
) -> dict[str, Any]:
    if not isinstance(manifest, dict):
        return empty_native_profile_summary()
    artifacts = manifest.get("artifacts")
    if not isinstance(artifacts, dict):
        return empty_native_profile_summary()

    profile_path_value = artifacts.get("nativeProfile")
    if not isinstance(profile_path_value, str) or not profile_path_value:
        return empty_native_profile_summary()

    summary = empty_native_profile_summary(declared=True, path=profile_path_value)
    profile_path = package_path / profile_path_value
    if not profile_path.is_file():
        return summary

    summary["available"] = True
    profile_payload = read_json_file(profile_path)
    if profile_payload is None:
        summary["parseError"] = "invalid-json"
        return finalize_native_profile_summary(summary)

    profile = profile_payload.get("profile")
    debug = profile_payload.get("debug")
    optimization = debug.get("optimization") if isinstance(debug, dict) else None
    if isinstance(optimization, dict):
        summary["optimization"] = {
            "level": optional_string(optimization.get("level")),
            "policy": optional_string(optimization.get("policy")),
            "requestedLevel": optional_string(optimization.get("requestedLevel")),
            "status": optional_string(optimization.get("status")),
            "tool": optional_string(optimization.get("tool")),
        }

    summary.update(
        {
            "api": optional_string(profile_payload.get("api")),
            "profileName": optional_string(profile.get("name"))
            if isinstance(profile, dict)
            else None,
            "schemaVersion": optional_int(profile_payload.get("schemaVersion")),
            "target": optional_string(profile_payload.get("target")),
        }
    )
    return finalize_native_profile_summary(summary)


def pass_trace_manifest_declared(manifest: dict[str, Any] | None) -> bool:
    if not isinstance(manifest, dict):
        return False
    artifacts = manifest.get("artifacts")
    if not isinstance(artifacts, dict):
        return False
    for kind, value in artifacts.items():
        if kind in {"hirPassTrace", "passTrace", PASS_TRACE_KIND}:
            return True
        if isinstance(value, str) and value == PASS_TRACE_SIDECAR_PATH:
            return True
    return False


def empty_pass_trace_provenance(
    *,
    output_display: str,
    target: str,
    profile_name: str,
    status: str,
    reason: str | None,
    manifest_declared: bool = False,
) -> dict[str, Any]:
    return {
        "available": False,
        "captureMode": "package-sidecar",
        "completed": None,
        "expectedOptimizationLevel": profile_hir_optimization_level(profile_name),
        "kind": None,
        "manifestDeclared": manifest_declared,
        "optimizationLevel": None,
        "optimizationPolicyId": None,
        "parseError": None,
        "passCount": None,
        "passScheduleFingerprint": None,
        "passScheduleFingerprintPolicy": None,
        "passScheduleStability": None,
        "path": f"{output_display}/{PASS_TRACE_SIDECAR_PATH}",
        "profile": get_profile(profile_name).name,
        "reason": reason,
        "requested": profile_requests_pass_trace(profile_name),
        "schemaVersion": None,
        "scheduledPassCount": None,
        "sidecarPath": PASS_TRACE_SIDECAR_PATH,
        "status": status,
        "target": target,
    }


def pass_trace_provenance(
    *,
    output_path: Path,
    output_display: str,
    target: str,
    profile_name: str,
    build_status: str,
    skipped: bool,
    skip_reason: str | None,
) -> dict[str, Any]:
    if build_status == "dry-run":
        return empty_pass_trace_provenance(
            output_display=output_display,
            target=target,
            profile_name=profile_name,
            status="not-run",
            reason="dry-run",
        )
    if skipped:
        return empty_pass_trace_provenance(
            output_display=output_display,
            target=target,
            profile_name=profile_name,
            status="skipped",
            reason=skip_reason,
        )

    manifest = (
        read_json_file(output_path / "manifest.json") if output_path.is_dir() else None
    )
    manifest_declared = pass_trace_manifest_declared(manifest)
    base = empty_pass_trace_provenance(
        output_display=output_display,
        target=target,
        profile_name=profile_name,
        status="artifact-unavailable",
        reason="package-output-missing",
        manifest_declared=manifest_declared,
    )

    if build_status == "failed":
        base["reason"] = "build-failed"
        return base
    if not output_path.exists():
        return base

    trace_path = output_path / PASS_TRACE_SIDECAR_PATH
    if not trace_path.is_file():
        base["status"] = (
            "requested-missing"
            if profile_requests_pass_trace(profile_name)
            else "not-requested"
        )
        base["reason"] = (
            "pass-trace-sidecar-missing"
            if profile_requests_pass_trace(profile_name)
            else "debug-ir-not-requested"
        )
        return base

    base["available"] = True
    base["status"] = "available"
    base["reason"] = None
    try:
        payload = json.loads(trace_path.read_text(encoding="utf-8"))
    except OSError as exc:
        base["status"] = "unparsable"
        base["parseError"] = f"read-error: {exc}"
        base["reason"] = "read-error"
        return base
    except json.JSONDecodeError as exc:
        base["status"] = "unparsable"
        base["parseError"] = f"{exc.msg} at line {exc.lineno} column {exc.colno}"
        base["reason"] = "invalid-json"
        return base

    if not isinstance(payload, dict):
        base["status"] = "unparsable"
        base["parseError"] = "expected JSON object"
        base["reason"] = "invalid-json"
        return base

    policy = payload.get("optimizationPolicy")
    schedule = payload.get("passSchedule")
    base.update(
        {
            "completed": payload.get("completed")
            if isinstance(payload.get("completed"), bool)
            else None,
            "kind": optional_string(payload.get("kind")),
            "optimizationLevel": optional_string(payload.get("optimizationLevel")),
            "optimizationPolicyId": optional_string(policy.get("id"))
            if isinstance(policy, dict)
            else None,
            "passCount": optional_int(payload.get("passCount")),
            "passScheduleFingerprint": optional_string(schedule.get("fingerprint"))
            if isinstance(schedule, dict)
            else None,
            "passScheduleFingerprintPolicy": optional_string(
                schedule.get("fingerprintPolicy")
            )
            if isinstance(schedule, dict)
            else None,
            "passScheduleStability": optional_string(schedule.get("stability"))
            if isinstance(schedule, dict)
            else None,
            "schemaVersion": optional_int(payload.get("schemaVersion")),
            "scheduledPassCount": optional_int(payload.get("scheduledPassCount")),
        }
    )
    return base


def artifact_summary(
    *,
    output_path: Path,
    output_display: str,
    target: str,
    profile_name: str,
) -> dict[str, Any]:
    profile = get_profile(profile_name)
    files = artifact_file_records(output_path)
    manifest = (
        read_json_file(output_path / "manifest.json") if output_path.is_dir() else None
    )
    manifest_artifacts = manifest_artifact_records(output_path, manifest)
    artifacts = manifest.get("artifacts") if isinstance(manifest, dict) else None
    existing_manifest_artifacts = [
        artifact for artifact in manifest_artifacts if artifact["exists"]
    ]
    byte_size = sum(record["bytes"] for record in files)
    manifest_artifact_byte_size = sum(
        artifact["bytes"]
        for artifact in existing_manifest_artifacts
        if isinstance(artifact["bytes"], int)
    )

    if output_path.is_dir():
        output_kind = "directory"
        package_format = "directory"
    elif output_path.is_file():
        output_kind = "file"
        package_format = "file"
    else:
        output_kind = "missing"
        package_format = None

    return {
        "available": output_path.exists(),
        "byteSize": byte_size,
        "debugArtifactsPresent": (
            bool(
                isinstance(artifacts, dict)
                and artifacts.get("debugMetadata")
                and artifacts.get("hirSourceMap")
            )
            if isinstance(manifest, dict)
            else None
        ),
        "emittedManifestArtifactCount": len(existing_manifest_artifacts),
        "fileCount": len(files),
        "files": files,
        "manifestArtifactByteSize": manifest_artifact_byte_size,
        "manifestArtifactCount": len(manifest_artifacts),
        "manifestArtifacts": manifest_artifacts,
        "manifestAvailable": isinstance(manifest, dict),
        "manifestPackageMode": manifest_package_mode(manifest),
        "manifestTarget": manifest.get("target")
        if isinstance(manifest, dict)
        else None,
        "missingManifestArtifactCount": len(manifest_artifacts)
        - len(existing_manifest_artifacts),
        "nativeArtifactDescriptor": native_artifact_descriptor_summary(
            output_path, manifest
        ),
        "nativeProfile": native_profile_summary(output_path, manifest),
        "nativeBinaryStatus": (
            artifacts.get("nativeBinaryStatus") if isinstance(artifacts, dict) else None
        ),
        "optLevel": profile.compiler_config,
        "outputKind": output_kind,
        "outputPath": output_display,
        "packageFormat": package_format,
        "profile": profile.name,
        "requestedPackageMode": profile.package_mode,
        "target": target,
    }


def empty_artifact_summary(
    *,
    output_display: str,
    target: str,
    profile_name: str,
) -> dict[str, Any]:
    profile = get_profile(profile_name)
    return {
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
        "optLevel": profile.compiler_config,
        "outputKind": "missing",
        "outputPath": output_display,
        "packageFormat": None,
        "profile": profile.name,
        "requestedPackageMode": profile.package_mode,
        "target": target,
    }


def count_by_pass_trace_status(cases: list[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for case in cases:
        provenance = case["passTraceProvenance"]
        status = provenance["status"]
        counts[status] = counts.get(status, 0) + 1
    return dict(sorted(counts.items()))


def pass_trace_provenance_summary(
    cases: list[dict[str, Any]], status_counts: dict[str, int]
) -> dict[str, Any]:
    unexpected_level_cases: list[str] = []
    fingerprint_counts: dict[str, int] = {}
    for case in cases:
        provenance = case["passTraceProvenance"]
        actual = provenance.get("optimizationLevel")
        expected = provenance.get("expectedOptimizationLevel")
        if actual is not None and expected is not None and actual != expected:
            unexpected_level_cases.append(case["case"])
        fingerprint = provenance.get("passScheduleFingerprint")
        if isinstance(fingerprint, str) and fingerprint:
            fingerprint_counts[fingerprint] = fingerprint_counts.get(fingerprint, 0) + 1
    unexpected_level_cases.sort()
    return {
        "availableCount": status_counts.get("available", 0),
        "caseCount": len(cases),
        "caseCountByPassScheduleFingerprint": dict(sorted(fingerprint_counts.items())),
        "caseCountByStatus": status_counts,
        "manifestDeclaredCount": sum(
            1 for case in cases if case["passTraceProvenance"]["manifestDeclared"]
        ),
        "passScheduleFingerprintCount": len(fingerprint_counts),
        "passScheduleFingerprints": sorted(fingerprint_counts),
        "parseErrorCount": sum(
            1
            for case in cases
            if case["passTraceProvenance"].get("parseError") is not None
        ),
        "reportPolicy": "report-only",
        "requestedCount": sum(
            1 for case in cases if case["passTraceProvenance"]["requested"]
        ),
        "schemaVersion": SCHEMA_VERSION,
        "sidecarPath": PASS_TRACE_SIDECAR_PATH,
        "unexpectedOptimizationLevelCases": unexpected_level_cases,
        "unexpectedOptimizationLevelCount": len(unexpected_level_cases),
    }


def verification_status(
    *,
    profile_name: str,
    status: str,
    skipped: bool,
    skip_reason: str | None,
    unavailable_tools: list[str] | None,
    artifact_available: bool,
) -> dict[str, Any]:
    profile = get_profile(profile_name)
    tool_available = "cglc" not in set(unavailable_tools or [])
    if skipped:
        verification_state = "skipped"
        reason = skip_reason
    elif status == "dry-run":
        verification_state = "not-run"
        reason = "dry-run"
    elif status == "failed":
        verification_state = "not-run"
        reason = "build-failed"
    elif not profile.native_validation:
        verification_state = "not-requested"
        reason = "profile-does-not-request-native-validation"
    elif artifact_available:
        verification_state = "build-passed"
        reason = None
    else:
        verification_state = "not-run"
        reason = "artifact-unavailable"

    return {
        "requested": profile.native_validation,
        "status": verification_state,
        "reason": reason,
        "tool": "cglc",
        "toolAvailable": tool_available,
    }


def count_by_key(cases: list[dict[str, Any]], key: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for case in cases:
        value = str(case[key])
        counts[value] = counts.get(value, 0) + 1
    return dict(sorted(counts.items()))


def count_by_category_target(cases: list[dict[str, Any]]) -> dict[str, dict[str, int]]:
    counts: dict[str, dict[str, int]] = {}
    for case in cases:
        category = str(case["fixtureCategory"])
        target = str(case["target"])
        target_counts = counts.setdefault(category, {})
        target_counts[target] = target_counts.get(target, 0) + 1
    return {
        category: dict(sorted(target_counts.items()))
        for category, target_counts in sorted(counts.items())
    }


def count_by_command_profile(cases: list[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for case in cases:
        name = case["commandProfile"]["name"]
        counts[name] = counts.get(name, 0) + 1
    return dict(sorted(counts.items()))


def package_modes(cases: list[dict[str, Any]]) -> list[str]:
    return sorted(
        {
            case["packageMode"]
            for case in cases
            if isinstance(case.get("packageMode"), str) and case["packageMode"]
        }
    )


def count_by_native_optimization_status(cases: list[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for case in cases:
        profile = case["artifactSummary"].get("nativeProfile")
        optimization = (
            profile.get("optimization") if isinstance(profile, dict) else None
        )
        status = optimization.get("status") if isinstance(optimization, dict) else None
        if not isinstance(status, str) or not status:
            continue
        counts[status] = counts.get(status, 0) + 1
    return dict(sorted(counts.items()))


def count_by_native_artifact_descriptor_optimization_status(
    cases: list[dict[str, Any]],
) -> dict[str, int]:
    counts: dict[str, int] = {}
    for case in cases:
        descriptor = case["artifactSummary"].get("nativeArtifactDescriptor")
        evidence = (
            descriptor.get("optimizationEvidence")
            if isinstance(descriptor, dict)
            else None
        )
        status = evidence.get("status") if isinstance(evidence, dict) else None
        if not isinstance(status, str) or not status:
            continue
        counts[status] = counts.get(status, 0) + 1
    return dict(sorted(counts.items()))


def native_optimization_evidence_status(case: dict[str, Any]) -> str:
    profile = case["artifactSummary"].get("nativeProfile")
    return native_optimization_evidence_status_from_profile(profile)


def native_artifact_descriptor_evidence_status(case: dict[str, Any]) -> str:
    descriptor = case["artifactSummary"].get("nativeArtifactDescriptor")
    return native_artifact_descriptor_optimization_evidence_status(descriptor)


def count_by_native_optimization_evidence_status(
    cases: list[dict[str, Any]],
) -> dict[str, int]:
    counts: dict[str, int] = {}
    for case in cases:
        status = native_optimization_evidence_status(case)
        counts[status] = counts.get(status, 0) + 1
    return dict(sorted(counts.items()))


def count_by_native_artifact_descriptor_evidence_status(
    cases: list[dict[str, Any]],
) -> dict[str, int]:
    counts: dict[str, int] = {}
    for case in cases:
        status = native_artifact_descriptor_evidence_status(case)
        counts[status] = counts.get(status, 0) + 1
    return dict(sorted(counts.items()))


def native_optimization_evidence_summary(
    cases: list[dict[str, Any]], status_counts: dict[str, int]
) -> dict[str, Any]:
    case_count = len(cases)
    known_status_count = status_counts.get("known-status", 0)
    missing_count = status_counts.get("missing-debug-optimization", 0)
    unparsable_count = status_counts.get("unparsable-native-profile", 0)
    declared_missing_count = status_counts.get("declared-native-profile-missing", 0)
    without_status_count = status_counts.get("optimization-without-status", 0)
    not_declared_count = status_counts.get("native-profile-not-declared", 0)
    return {
        "caseCount": case_count,
        "caseCountByEvidenceStatus": status_counts,
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
    cases: list[dict[str, Any]], status_counts: dict[str, int]
) -> dict[str, Any]:
    case_count = len(cases)
    known_status_count = status_counts.get("known-status", 0)
    missing_count = status_counts.get("missing-optimization-evidence", 0)
    unparsable_count = status_counts.get("unparsable-native-artifact-descriptor", 0)
    declared_missing_count = status_counts.get(
        "declared-native-artifact-descriptor-missing", 0
    )
    without_status_count = status_counts.get("optimization-without-status", 0)
    not_declared_count = status_counts.get("native-artifact-descriptor-not-declared", 0)
    return {
        "caseCount": case_count,
        "caseCountByEvidenceStatus": status_counts,
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


def fixture_count_by_category(fixtures: list[CorpusFixture]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for fixture in fixtures:
        counts[fixture.category] = counts.get(fixture.category, 0) + 1
    return dict(sorted(counts.items()))


def skipped_tool_case_count_by_tool(cases: list[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for case in cases:
        if not case["skipped"]:
            continue
        for tool in case["unavailableTools"]:
            counts[tool] = counts.get(tool, 0) + 1
    return dict(sorted(counts.items()))


def skipped_tool_cases_by_tool(cases: list[dict[str, Any]]) -> dict[str, list[str]]:
    cases_by_tool: dict[str, list[str]] = {}
    for case in cases:
        if not case["skipped"]:
            continue
        for tool in case["unavailableTools"]:
            cases_by_tool.setdefault(tool, []).append(case["case"])
    return {
        tool: sorted(case_keys) for tool, case_keys in sorted(cases_by_tool.items())
    }


def skipped_case_count_by_reason(cases: list[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for case in cases:
        if not case["skipped"]:
            continue
        reason = case["skipReason"] or "unspecified"
        counts[reason] = counts.get(reason, 0) + 1
    return dict(sorted(counts.items()))


def skipped_cases_with_unavailable_tools(cases: list[dict[str, Any]]) -> list[str]:
    return sorted(
        {case["case"] for case in cases if case["skipped"] and case["unavailableTools"]}
    )


def advisory_threshold_policy_stub() -> dict[str, Any]:
    return {
        "schemaVersion": SCHEMA_VERSION,
        "tool": TOOL_NAME,
        "kind": ADVISORY_THRESHOLD_POLICY_KIND,
        "mode": "report-only",
        "name": ADVISORY_THRESHOLD_POLICY_NAME,
        "description": (
            "Report-only Milestone 6 runner provenance stub. Numeric timing "
            "thresholds are not emitted because this repository does not carry "
            "stable multi-run baseline data."
        ),
        "evidencePolicy": {
            "minimumSampleCount": TIMING_ADVISORY_MIN_SAMPLE_COUNT,
            "policy": TIMING_ADVISORY_EVIDENCE_POLICY,
            "requiresComparableMetadata": True,
            "requiresExplicitTimedCaseIdentity": True,
            "requiresRepeatedBaselineAndCandidateSamples": True,
            "stableBaselinePolicy": TIMING_BASELINE_STABILITY_POLICY,
        },
        "failurePolicy": (
            "report-only; advisory timing threshold observations never change "
            "runner, checker, or CI exit status"
        ),
        "enforcement": {
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
        "releaseBlockerPolicy": TIMING_ADVISORY_RELEASE_BLOCKER_POLICY,
        "ruleCount": 0,
        "rules": [],
        "stableBaselineDataPresent": False,
        "status": "policy-stub",
        "thresholdSource": "not-configured",
    }


def toolchain_role(entry: dict[str, Any]) -> str:
    role = entry.get("role") or entry.get("classification")
    if isinstance(role, str) and role:
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


def effective_toolchain_metadata(
    *,
    tool_availability: dict[str, Any],
    toolchains: dict[str, dict[str, Any]] | None,
) -> dict[str, dict[str, Any]]:
    effective: dict[str, dict[str, Any]] = {}
    for label, entry in tool_availability.items():
        if isinstance(label, str) and label and isinstance(entry, dict):
            effective[label] = dict(entry)
    for label, entry in (toolchains or {}).items():
        if not isinstance(label, str) or not label or not isinstance(entry, dict):
            continue
        effective.setdefault(label, {}).update(entry)
    return {label: effective[label] for label in sorted(effective)}


def toolchain_classification(entry: dict[str, Any]) -> dict[str, Any]:
    available = entry.get("available")
    if available is True:
        availability = "available"
    elif available is False:
        availability = "unavailable"
    else:
        status = entry.get("status")
        availability = status if isinstance(status, str) and status else "unspecified"
    return {
        "available": available,
        "availability": availability,
        "role": toolchain_role(entry),
        "status": entry.get("status"),
        "version": entry.get("version")
        if isinstance(entry.get("version"), str)
        else None,
    }


def skipped_tool_accounting_report(
    *,
    cases: list[dict[str, Any]],
    toolchains: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    cases_by_tool = skipped_tool_cases_by_tool(cases)
    classifications = {
        label: toolchain_classification(entry) for label, entry in toolchains.items()
    }
    optional_tools = sorted(
        tool
        for tool in cases_by_tool
        if classifications.get(tool, {}).get("role") == "optional"
    )
    required_or_unclassified_tools = sorted(
        tool
        for tool in cases_by_tool
        if classifications.get(tool, {}).get("role") != "optional"
    )
    skipped_cases = sorted(case["case"] for case in cases if case["skipped"])
    skipped_cases_with_tools = skipped_cases_with_unavailable_tools(cases)
    return {
        "optionalSkippedCaseCount": len(
            {case for tool in optional_tools for case in cases_by_tool.get(tool, [])}
        ),
        "optionalSkippedToolLabels": optional_tools,
        "requiredOrUnclassifiedSkippedCaseCount": len(
            {
                case
                for tool in required_or_unclassified_tools
                for case in cases_by_tool.get(tool, [])
            }
        ),
        "requiredOrUnclassifiedSkippedToolLabels": required_or_unclassified_tools,
        "skippedCaseCount": len(skipped_cases),
        "skippedCases": skipped_cases,
        "skippedCasesWithUnavailableTools": skipped_cases_with_tools,
        "skippedCasesWithoutUnavailableToolCount": len(
            sorted(set(skipped_cases) - set(skipped_cases_with_tools))
        ),
        "skippedCasesWithoutUnavailableTools": sorted(
            set(skipped_cases) - set(skipped_cases_with_tools)
        ),
        "skippedToolCaseCountByTool": skipped_tool_case_count_by_tool(cases),
        "skippedToolCasesByTool": cases_by_tool,
        "toolchainClassifications": classifications,
        "unavailableToolchainLabelCount": len(
            [
                label
                for label, classification in classifications.items()
                if classification["availability"] == "unavailable"
            ]
        ),
        "unavailableToolchainLabels": sorted(
            label
            for label, classification in classifications.items()
            if classification["availability"] == "unavailable"
        ),
    }


def case_timing_sample_count(case: dict[str, Any]) -> int | None:
    timing = case.get("timing")
    if not isinstance(timing, dict):
        return None
    sample_count = timing.get("sampleCount")
    if isinstance(sample_count, int) and not isinstance(sample_count, bool):
        return sample_count
    runs = timing.get("runs")
    if isinstance(runs, list):
        return len(runs)
    return None


def timed_case_identity_report(cases: list[dict[str, Any]]) -> dict[str, Any]:
    evidence: list[dict[str, Any]] = []
    for case in cases:
        if not isinstance(case.get("timing"), dict):
            continue
        missing_fields = [
            field
            for field in REQUIRED_THRESHOLD_CASE_IDENTITY_FIELDS
            if not isinstance(case.get(field), str) or not case.get(field)
        ]
        evidence.append(
            {
                "case": case["case"],
                "complete": not missing_fields,
                "missingFieldCount": len(missing_fields),
                "missingFields": missing_fields,
                "requiredFields": list(REQUIRED_THRESHOLD_CASE_IDENTITY_FIELDS),
            }
        )

    incomplete = [item for item in evidence if item["complete"] is not True]
    return {
        "caseEvidence": sorted(evidence, key=lambda item: item["case"]),
        "incompleteCaseCount": len(incomplete),
        "incompleteCases": sorted(item["case"] for item in incomplete),
        "policy": (
            "Threshold-baseline evidence requires explicit fixtureName, target, "
            "profile, and optLevel labels on timed cases."
        ),
        "requiredFields": list(REQUIRED_THRESHOLD_CASE_IDENTITY_FIELDS),
        "timedCaseCount": len(evidence),
    }


def repeated_timing_evidence_report(cases: list[dict[str, Any]]) -> dict[str, Any]:
    evidence: list[dict[str, Any]] = []
    for case in cases:
        if not isinstance(case.get("timing"), dict):
            continue
        sample_count = case_timing_sample_count(case)
        sufficient = (
            sample_count is not None
            and sample_count >= TIMING_ADVISORY_MIN_SAMPLE_COUNT
        )
        if sample_count is None:
            reason = "missingSampleCount"
        elif sample_count < TIMING_ADVISORY_MIN_SAMPLE_COUNT:
            reason = "insufficientSampleCount"
        else:
            reason = None
        evidence.append(
            {
                "case": case["case"],
                "minimumSampleCount": TIMING_ADVISORY_MIN_SAMPLE_COUNT,
                "reason": reason,
                "sampleCount": sample_count,
                "sufficient": sufficient,
            }
        )

    insufficient = [item for item in evidence if item["sufficient"] is not True]
    return {
        "caseEvidence": sorted(evidence, key=lambda item: item["case"]),
        "insufficientRepeatedEvidenceCaseCount": len(insufficient),
        "insufficientRepeatedEvidenceCases": sorted(
            item["case"] for item in insufficient
        ),
        "minimumSampleCount": TIMING_ADVISORY_MIN_SAMPLE_COUNT,
        "policy": TIMING_ADVISORY_EVIDENCE_POLICY,
        "repeatedTimedCaseCount": len(evidence) - len(insufficient),
        "timedCaseCount": len(evidence),
    }


def baseline_provenance_report(
    *,
    metadata: dict[str, Any],
    toolchains: dict[str, dict[str, Any]],
    cases: list[dict[str, Any]],
) -> dict[str, Any]:
    fields: dict[str, Any] = {}
    for field in ("hostLabel", "hostClass", "targetProfile", "optLevel"):
        value = metadata.get(field)
        if isinstance(value, str) and value:
            fields[field] = value
    comparison_window = metadata.get("comparisonWindow")
    if comparison_window is not None:
        fields["comparisonWindow"] = comparison_window
    runtime_environment = metadata.get("runtimeEnvironment")
    runtime_missing_fields: list[str] = []
    if isinstance(runtime_environment, dict):
        fields["runtimeEnvironment"] = runtime_environment
        for field in (
            "machine",
            "platform",
            "pythonExecutable",
            "pythonImplementation",
            "pythonVersion",
            "system",
            "systemRelease",
        ):
            value = runtime_environment.get(field)
            if not isinstance(value, str) or not value:
                runtime_missing_fields.append(field)
    else:
        runtime_missing_fields = ["runtimeEnvironment"]

    missing_fields = [
        field
        for field in REQUIRED_BASELINE_PROVENANCE_FIELDS
        if (field == "toolchains" and not toolchains)
        or (field == "runtimeEnvironment" and runtime_missing_fields)
        or (field not in ("toolchains", "runtimeEnvironment") and field not in fields)
    ]
    toolchains_missing_versions = sorted(
        label
        for label, entry in toolchains.items()
        if not isinstance(entry.get("version"), str) or not entry.get("version")
    )
    return {
        "fields": fields,
        "missingFields": missing_fields,
        "requiredFields": list(REQUIRED_BASELINE_PROVENANCE_FIELDS),
        "requiredRuntimeEnvironmentFields": [
            "machine",
            "platform",
            "pythonExecutable",
            "pythonImplementation",
            "pythonVersion",
            "system",
            "systemRelease",
        ],
        "runtimeEnvironmentMissingFields": runtime_missing_fields,
        "skippedToolAccounting": skipped_tool_accounting_report(
            cases=cases,
            toolchains=toolchains,
        ),
        "toolchainLabelCount": len(toolchains),
        "toolchainLabels": sorted(toolchains),
        "toolchains": toolchains,
        "toolchainsMissingVersionCount": len(toolchains_missing_versions),
        "toolchainsMissingVersions": toolchains_missing_versions,
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


def threshold_baseline_readiness(
    *,
    metadata: dict[str, Any],
    cases: list[dict[str, Any]],
    tool_availability: dict[str, Any],
    toolchains: dict[str, dict[str, Any]] | None,
) -> dict[str, Any]:
    effective_toolchains = effective_toolchain_metadata(
        tool_availability=tool_availability,
        toolchains=toolchains,
    )
    provenance = baseline_provenance_report(
        metadata=metadata,
        toolchains=effective_toolchains,
        cases=cases,
    )
    timed_identity = timed_case_identity_report(cases)
    repeated_evidence = repeated_timing_evidence_report(cases)
    skipped_accounting = provenance["skippedToolAccounting"]

    requirements = [
        threshold_baseline_requirement(
            "stableBaselineData",
            satisfied=False,
            reason_if_unsatisfied="stable-baseline-data-not-present",
            observed={
                "stableBaselineDataPresent": False,
                "policy": TIMING_BASELINE_STABILITY_POLICY,
            },
        ),
        threshold_baseline_requirement(
            "baselineProvenance",
            satisfied=not provenance["missingFields"]
            and provenance["toolchainsMissingVersionCount"] == 0,
            reason_if_unsatisfied="missing-baseline-provenance",
            observed={
                "missingFields": provenance["missingFields"],
                "toolchainsMissingVersions": provenance["toolchainsMissingVersions"],
            },
        ),
        threshold_baseline_requirement(
            "timedCases",
            satisfied=timed_identity["timedCaseCount"] > 0,
            reason_if_unsatisfied="no-timed-cases",
            observed={"timedCaseCount": timed_identity["timedCaseCount"]},
        ),
        threshold_baseline_requirement(
            "explicitTimedCaseIdentity",
            satisfied=timed_identity["incompleteCaseCount"] == 0,
            reason_if_unsatisfied="incomplete-timed-case-identity",
            observed={
                "incompleteCaseCount": timed_identity["incompleteCaseCount"],
                "incompleteCases": timed_identity["incompleteCases"],
            },
        ),
        threshold_baseline_requirement(
            "repeatedTimingEvidence",
            satisfied=repeated_evidence["timedCaseCount"] > 0
            and repeated_evidence["insufficientRepeatedEvidenceCaseCount"] == 0,
            reason_if_unsatisfied="insufficient-repeated-timing-evidence",
            observed={
                "insufficientRepeatedEvidenceCaseCount": (
                    repeated_evidence["insufficientRepeatedEvidenceCaseCount"]
                ),
                "minimumSampleCount": TIMING_ADVISORY_MIN_SAMPLE_COUNT,
                "repeatedTimedCaseCount": repeated_evidence["repeatedTimedCaseCount"],
            },
        ),
        threshold_baseline_requirement(
            "requiredToolCoverage",
            satisfied=(
                skipped_accounting["requiredOrUnclassifiedSkippedCaseCount"] == 0
                and skipped_accounting["skippedCasesWithoutUnavailableToolCount"] == 0
            ),
            reason_if_unsatisfied="required-or-unclassified-skipped-tools",
            observed={
                "requiredOrUnclassifiedSkippedCaseCount": skipped_accounting[
                    "requiredOrUnclassifiedSkippedCaseCount"
                ],
                "requiredOrUnclassifiedSkippedToolLabels": skipped_accounting[
                    "requiredOrUnclassifiedSkippedToolLabels"
                ],
                "skippedCasesWithoutUnavailableToolCount": skipped_accounting[
                    "skippedCasesWithoutUnavailableToolCount"
                ],
            },
        ),
    ]
    unsatisfied = [
        requirement
        for requirement in requirements
        if requirement["satisfied"] is not True
    ]
    reasons = [requirement["reasonIfUnsatisfied"] for requirement in unsatisfied]
    return {
        "advisory": True,
        "baselineProvenance": provenance,
        "failureMode": "report-only",
        "incompleteTimedCaseIdentityCaseCount": timed_identity["incompleteCaseCount"],
        "incompleteTimedCaseIdentityCases": timed_identity["incompleteCases"],
        "minimumSampleCount": TIMING_ADVISORY_MIN_SAMPLE_COUNT,
        "mode": "report-only",
        "optionalSkippedCaseCount": skipped_accounting["optionalSkippedCaseCount"],
        "optionalSkippedToolLabels": skipped_accounting["optionalSkippedToolLabels"],
        "policy": (
            "Runner threshold-baseline readiness is advisory provenance only. "
            "Unsatisfied checks never change benchmark or checker exit status."
        ),
        "readyForThresholdBaseline": False,
        "reasonCount": len(reasons),
        "reasons": reasons,
        "repeatedTimingEvidence": repeated_evidence,
        "requiredOrUnclassifiedSkippedCaseCount": skipped_accounting[
            "requiredOrUnclassifiedSkippedCaseCount"
        ],
        "requiredOrUnclassifiedSkippedToolLabels": skipped_accounting[
            "requiredOrUnclassifiedSkippedToolLabels"
        ],
        "satisfiedThresholdBaselineRequirementCount": (
            len(requirements) - len(unsatisfied)
        ),
        "stableBaselineDataPresent": False,
        "status": "incomplete",
        "thresholdBaselineRequirementCount": len(requirements),
        "thresholdBaselineRequirements": requirements,
        "thresholdBaselineRequirementsPolicy": (
            "These checks explain future threshold-baseline eligibility only; "
            "timing thresholds remain report-only."
        ),
        "timedCaseCount": timed_identity["timedCaseCount"],
        "timedCaseIdentity": timed_identity,
        "unsatisfiedThresholdBaselineRequirementCount": len(unsatisfied),
        "unsatisfiedThresholdBaselineRequirements": unsatisfied,
    }


def manifest_artifact_kind_summary(cases: list[dict[str, Any]]) -> dict[str, Any]:
    metrics: dict[str, dict[str, int]] = {}
    for case in cases:
        artifact_summary = case["artifactSummary"]
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
    return sum(
        1
        for case in cases
        if isinstance(case["artifactSummary"].get("manifestArtifacts"), list)
        and bool(case["artifactSummary"]["manifestArtifacts"])
    )


def build_case(
    *,
    compiler_path: Path | str,
    root: Path,
    work_dir: Path,
    fixture: CorpusFixture,
    target: str,
    profile_name: str,
    repeat: int,
    warmup: int,
    dry_run: bool,
    skipped: bool = False,
    skip_reason: str | None = None,
    unavailable_tools: list[str] | None = None,
) -> dict[str, Any]:
    profile = get_profile(profile_name)
    source_path = fixture_path(root, fixture)
    source_display = display_path(source_path, root)
    output_path = output_path_for(work_dir, fixture, target, profile_name)
    output_display = display_path(output_path, root)
    command = display_command(source_display, target, output_display, profile_name)

    case = {
        "artifactSummary": empty_artifact_summary(
            output_display=output_display,
            target=target,
            profile_name=profile_name,
        ),
        "case": f"{fixture.name}::{target}::{profile_name}",
        "command": command,
        "commandProfile": command_profile(profile_name),
        "compilerPath": report_path(compiler_path, root),
        "diagnosticSummary": diagnostic_summary(b"", b""),
        "elapsedNs": 0,
        "exitStatus": None,
        "fixtureCategory": fixture.category,
        "fixtureName": fixture.name,
        "fixturePath": source_display,
        "nativeValidationRequested": profile.native_validation,
        "optLevel": profile.compiler_config,
        "outputPath": output_display,
        "packageMode": profile.package_mode,
        "passTraceProvenance": pass_trace_provenance(
            output_path=output_path,
            output_display=output_display,
            target=target,
            profile_name=profile_name,
            build_status="skipped" if skipped else "dry-run",
            skipped=skipped,
            skip_reason=skip_reason,
        ),
        "profile": profile.name,
        "profileBuildType": profile.build_type,
        "skipReason": skip_reason,
        "skipped": skipped,
        "status": "skipped" if skipped else "dry-run",
        "success": None,
        "target": target,
        "timing": None,
        "unavailableTools": sorted(unavailable_tools or []),
        "verification": verification_status(
            profile_name=profile_name,
            status="skipped" if skipped else "dry-run",
            skipped=skipped,
            skip_reason=skip_reason,
            unavailable_tools=unavailable_tools,
            artifact_available=False,
        ),
    }
    if dry_run or skipped:
        return case

    assert isinstance(compiler_path, Path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    timing, exit_status, stdout, stderr = run_timed_command(
        compiler_path,
        source_display,
        target,
        output_path,
        profile_name,
        root,
        warmup,
        repeat,
    )
    elapsed_ns = timing["elapsedNs"]
    success = exit_status == 0
    artifact = (
        artifact_summary(
            output_path=output_path,
            output_display=output_display,
            target=target,
            profile_name=profile_name,
        )
        if success
        else case["artifactSummary"]
    )
    status = "passed" if success else "failed"
    case.update(
        {
            "artifactSummary": artifact,
            "diagnosticSummary": diagnostic_summary(stdout, stderr),
            "elapsedNs": elapsed_ns,
            "exitStatus": exit_status,
            "passTraceProvenance": pass_trace_provenance(
                output_path=output_path,
                output_display=output_display,
                target=target,
                profile_name=profile_name,
                build_status=status,
                skipped=False,
                skip_reason=None,
            ),
            "status": status,
            "success": success,
            "timing": timing,
            "verification": verification_status(
                profile_name=profile_name,
                status=status,
                skipped=False,
                skip_reason=None,
                unavailable_tools=unavailable_tools,
                artifact_available=artifact["available"],
            ),
        }
    )
    return case


def build_report(
    *,
    compiler_path: Path | str,
    root: Path,
    work_dir: Path,
    corpus_name: str,
    fixtures: list[CorpusFixture],
    targets: list[str],
    profiles: list[str],
    repeat: int,
    warmup: int,
    dry_run: bool,
    skipped: bool = False,
    skip_reason: str | None = None,
    unavailable_tools: list[str] | None = None,
    baseline_policy: dict[str, Any] | None = None,
    tool_availability: dict[str, Any] | None = None,
    toolchains: dict[str, dict[str, Any]] | None = None,
) -> dict[str, Any]:
    cases = [
        build_case(
            compiler_path=compiler_path,
            root=root,
            work_dir=work_dir,
            fixture=fixture,
            target=target,
            profile_name=profile,
            repeat=repeat,
            warmup=warmup,
            dry_run=dry_run,
            skipped=skipped,
            skip_reason=skip_reason,
            unavailable_tools=unavailable_tools,
        )
        for profile in profiles
        for fixture in fixtures
        for target in targets
        if target in fixture.targets
    ]
    command_profile_names = sorted({case["commandProfile"]["name"] for case in cases})
    descriptor_optimization_status_counts = (
        count_by_native_artifact_descriptor_optimization_status(cases)
    )
    descriptor_optimization_evidence_counts = (
        count_by_native_artifact_descriptor_evidence_status(cases)
    )
    native_optimization_status_counts = count_by_native_optimization_status(cases)
    native_optimization_evidence_counts = count_by_native_optimization_evidence_status(
        cases
    )
    pass_trace_status_counts = count_by_pass_trace_status(cases)
    manifest_artifact_kinds = manifest_artifact_kind_summary(cases)
    measurement_window = default_comparison_window(
        dry_run=dry_run,
        skipped=skipped,
        repeat=repeat,
        warmup=warmup,
    )
    report = {
        "schemaVersion": SCHEMA_VERSION,
        "tool": TOOL_NAME,
        "corpusVersion": CORPUS_VERSION,
        "dryRun": dry_run,
        "config": {
            "commandProfiles": profiles,
            "compilerPath": report_path(compiler_path, root),
            "corpus": corpus_name,
            "corpusVersion": CORPUS_VERSION,
            "fixtures": [fixture.name for fixture in fixtures],
            "manifestPath": display_path(DEFAULT_MANIFEST_PATH, root),
            "profiles": profiles,
            "repeat": repeat,
            "root": ".",
            "targets": targets,
            "warmup": warmup,
            "workDir": display_path(work_dir, root),
        },
        "cases": cases,
        "metadata": build_report_metadata(
            corpus_name=corpus_name,
            profiles=profiles,
            cases=cases,
            repeat=repeat,
            warmup=warmup,
            dry_run=dry_run,
            skipped=skipped,
            baseline_policy=baseline_policy,
        ),
        "summary": {
            "caseCountByCommandProfile": count_by_command_profile(cases),
            "caseCountByCategory": count_by_key(cases, "fixtureCategory"),
            "caseCountByCategoryTarget": count_by_category_target(cases),
            "caseCountByOptLevel": count_by_key(cases, "optLevel"),
            "caseCountByPackageMode": count_by_key(cases, "packageMode"),
            "caseCountByPassTraceStatus": pass_trace_status_counts,
            "caseCountByProfile": count_by_key(cases, "profile"),
            "caseCountByTarget": count_by_key(cases, "target"),
            "caseCategories": sorted({case["fixtureCategory"] for case in cases}),
            "caseCount": len(cases),
            "commandProfiles": command_profile_names,
            "commandProfileCount": len(command_profile_names),
            "categoryCount": len({case["fixtureCategory"] for case in cases}),
            "dryRunCount": sum(1 for case in cases if case["status"] == "dry-run"),
            "failureCount": sum(1 for case in cases if case["success"] is False),
            "fixtureCount": len(fixtures),
            "fixtureCountByCategory": fixture_count_by_category(fixtures),
            "manifestArtifactKindCaseCount": manifest_artifact_kind_case_count(cases),
            "manifestArtifactKindCount": len(manifest_artifact_kinds),
            "manifestArtifactKinds": manifest_artifact_kinds,
            "nativeValidationRequestedCount": sum(
                1 for case in cases if case["nativeValidationRequested"]
            ),
            "caseCountByNativeOptimizationEvidenceStatus": (
                native_optimization_evidence_counts
            ),
            "caseCountByNativeOptimizationStatus": native_optimization_status_counts,
            "caseCountByNativeArtifactDescriptorOptimizationEvidenceStatus": (
                descriptor_optimization_evidence_counts
            ),
            "caseCountByNativeArtifactDescriptorOptimizationStatus": (
                descriptor_optimization_status_counts
            ),
            "nativeArtifactDescriptorOptimizationEvidence": (
                native_artifact_descriptor_evidence_summary(
                    cases, descriptor_optimization_evidence_counts
                )
            ),
            "nativeArtifactDescriptorOptimizationStatuses": sorted(
                descriptor_optimization_status_counts
            ),
            "nativeOptimizationEvidence": native_optimization_evidence_summary(
                cases, native_optimization_evidence_counts
            ),
            "nativeOptimizationStatuses": sorted(native_optimization_status_counts),
            "optLevelCount": len({case["optLevel"] for case in cases}),
            "optLevels": sorted({case["optLevel"] for case in cases}),
            "packageModeCount": len(package_modes(cases)),
            "packageModes": package_modes(cases),
            "passTraceProvenance": pass_trace_provenance_summary(
                cases, pass_trace_status_counts
            ),
            "skippedCaseCountByReason": skipped_case_count_by_reason(cases),
            "skippedCount": sum(1 for case in cases if case["skipped"]),
            "skippedCasesWithUnavailableTools": skipped_cases_with_unavailable_tools(
                cases
            ),
            "skippedToolCaseCountByTool": skipped_tool_case_count_by_tool(cases),
            "skippedToolCasesByTool": skipped_tool_cases_by_tool(cases),
            "successCount": sum(1 for case in cases if case["success"] is True),
            "artifactAvailableCount": sum(
                1 for case in cases if case["artifactSummary"]["available"]
            ),
            "artifactByteSize": sum(
                case["artifactSummary"]["byteSize"] for case in cases
            ),
            "artifactFileCount": sum(
                case["artifactSummary"]["fileCount"] for case in cases
            ),
            "measuredRunCount": sum(
                len(case["timing"]["runs"])
                for case in cases
                if isinstance(case["timing"], dict)
            ),
            "measurementWindow": measurement_window,
            "timedCaseCount": sum(1 for case in cases if case["timing"] is not None),
            "timingWindow": timing_window_accounting(cases, measurement_window),
            "unavailableToolCount": len(
                sorted({tool for case in cases for tool in case["unavailableTools"]})
            ),
            "verificationPassedCount": sum(
                1
                for case in cases
                if case["verification"]["status"] in ("passed", "build-passed")
            ),
            "verificationRequestedCount": sum(
                1 for case in cases if case["verification"]["requested"]
            ),
            "verificationSkippedCount": sum(
                1 for case in cases if case["verification"]["status"] == "skipped"
            ),
            "warmupRunCount": sum(
                len(case["timing"]["warmups"])
                for case in cases
                if isinstance(case["timing"], dict)
            ),
        },
        "toolAvailability": tool_availability
        or {
            "cglc": {
                "available": None if dry_run else True,
                "path": report_path(compiler_path, root),
                "role": "required",
                "status": "not-checked" if dry_run else "available",
            }
        },
    }
    if baseline_policy is not None:
        report["baselinePolicy"] = baseline_policy
    if toolchains is not None:
        report["toolchains"] = toolchains
    add_policy_metadata_mirrors(
        report,
        baseline_policy,
        report["toolAvailability"],
        toolchains,
    )
    advisory_threshold_policy = advisory_threshold_policy_stub()
    readiness = threshold_baseline_readiness(
        metadata=report["metadata"],
        cases=cases,
        tool_availability=report["toolAvailability"],
        toolchains=toolchains,
    )
    report["advisoryThresholdPolicy"] = advisory_threshold_policy
    report["thresholdBaselineReadiness"] = readiness
    report["metadata"]["advisoryThresholdPolicy"] = advisory_threshold_policy
    report["metadata"]["thresholdBaselineReadiness"] = readiness
    return report


def write_json(payload: dict[str, Any], output_path: Path | None) -> None:
    text = json.dumps(payload, indent=2, sort_keys=True) + "\n"
    if output_path is None:
        sys.stdout.write(text)
        return
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(text, encoding="utf-8")


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument(
        "--cglc",
        help="Path to a built cglc executable. Defaults to CGLC or cglc on PATH.",
    )
    parser.add_argument(
        "--corpus",
        default=DEFAULT_CORPUS,
        choices=sorted(CORPORA),
        help="Named fixture corpus to run.",
    )
    parser.add_argument(
        "--fixture",
        action="append",
        help="Fixture name to run. Repeat or comma-separate values.",
    )
    parser.add_argument(
        "--target",
        action="append",
        help=(
            "Target to run. Repeat or comma-separate values. Supported: "
            + ", ".join(KNOWN_TARGETS)
            + "."
        ),
    )
    parser.add_argument(
        "--profile",
        action="append",
        help=(
            "Build-mode profile from benchmark_build_modes.py. Repeat or "
            f"comma-separate values. Default: {DEFAULT_PROFILE}."
            f" Supported: {', '.join(PROFILE_ORDER)}."
        ),
    )
    parser.add_argument(
        "--work-dir",
        type=Path,
        help="Directory for generated package outputs. Defaults to a temp dir.",
    )
    parser.add_argument(
        "--json-output",
        type=Path,
        help="Write the report to this path instead of stdout.",
    )
    parser.add_argument(
        "--warmup",
        type=parse_non_negative_int,
        default=1,
        help="Warmup command runs per case before measured repeats.",
    )
    parser.add_argument(
        "--repeat",
        type=parse_positive_int,
        default=3,
        help="Measured command runs per case.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Emit the planned JSON report without invoking cglc.",
    )
    parser.add_argument(
        "--list-corpus",
        action="store_true",
        help="Emit the known corpus fixture definitions as JSON and exit.",
    )
    parser.add_argument(
        "--allow-command-failures",
        action="store_true",
        help="Return success even when benchmarked cglc commands fail.",
    )
    parser.add_argument(
        "--skip-unavailable-tools",
        action="store_true",
        help=(
            "Emit skipped cases instead of failing when cglc is unavailable. "
            "Useful for CI jobs that upload trend-shape reports."
        ),
    )
    parser.add_argument(
        "--host-label",
        help=(
            "Optional runner or machine-pool label for baseline policy metadata. "
            "No host label is inferred by default."
        ),
    )
    parser.add_argument(
        "--host-class",
        help=(
            "Optional stable host class, such as OS/architecture/runner family. "
            "Defaults to the producer OS/architecture class."
        ),
    )
    parser.add_argument(
        "--target-profile",
        help=(
            "Optional benchmark target profile label. Defaults to crossgl-<corpus> "
            "when any baseline policy metadata is requested."
        ),
    )
    parser.add_argument(
        "--opt-level",
        help=(
            "Optional top-level optimization label for baseline policy metadata. "
            "Defaults to the selected profile compiler config, or mixed:<levels>."
        ),
    )
    parser.add_argument(
        "--comparison-window",
        help=(
            "Optional comparison-window metadata as JSON or a string, for example "
            '\'{"sampleCount":5,"warmupCount":1,"unit":"elapsedNs"}\'.'
        ),
    )
    parser.add_argument(
        "--toolchain-label",
        help="Optional compiler/toolchain label for baseline policy metadata.",
    )
    parser.add_argument(
        "--toolchain-version",
        help="Optional compiler/toolchain version for baseline policy metadata.",
    )
    return parser.parse_args(argv)


def unavailable_cglc_message(requested: Path | str) -> str | None:
    if isinstance(requested, Path):
        if not requested.is_file():
            return f"missing cglc executable: {requested}"
        if not os.access(requested, os.X_OK):
            return f"cglc is not executable: {requested}"
        return None

    found = shutil.which(requested)
    if found is None:
        return (
            f"missing cglc executable {requested!r}; pass --cglc /path/to/cglc "
            "or add cglc to PATH"
        )
    return None


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    root = args.root.expanduser().resolve()

    try:
        if args.list_corpus:
            write_json(corpus_document([args.corpus]), args.json_output)
            return 0
        if not root.is_dir():
            raise CorpusBenchmarkError(f"root directory does not exist: {root}")

        profiles = parse_profiles(args.profile)
        targets = parse_targets(args.target)
        fixtures = selected_fixtures(args.corpus, args.fixture)
        compiler_path = resolve_cglc(args.cglc, root, require_existing=False)
        cglc_unavailable = (
            None if args.dry_run else unavailable_cglc_message(compiler_path)
        )
        if (
            not args.dry_run
            and cglc_unavailable is None
            and isinstance(compiler_path, str)
        ):
            found_cglc = shutil.which(compiler_path)
            assert found_cglc is not None
            compiler_path = Path(found_cglc).resolve()
        if cglc_unavailable and not args.skip_unavailable_tools:
            raise CorpusBenchmarkError(cglc_unavailable)

        if args.work_dir:
            work_dir = args.work_dir.expanduser()
            if not work_dir.is_absolute():
                work_dir = root / work_dir
            work_dir = work_dir.resolve()
        elif args.dry_run:
            work_dir = (root / "build" / "performance-corpus-dry-run").resolve()
        elif cglc_unavailable:
            work_dir = (root / "build" / "performance-corpus-unavailable").resolve()
        else:
            work_dir = None

        tool_availability = {
            "cglc": {
                "available": None if args.dry_run else cglc_unavailable is None,
                "path": report_path(compiler_path, root),
                "role": "required",
                "status": "not-checked"
                if args.dry_run
                else ("unavailable" if cglc_unavailable else "available"),
                "reason": cglc_unavailable,
            }
        }
        comparison_window = parse_policy_value(args.comparison_window)
        baseline_policy = build_baseline_policy(
            corpus_name=args.corpus,
            profiles=profiles,
            repeat=args.repeat,
            warmup=args.warmup,
            dry_run=args.dry_run,
            skipped=cglc_unavailable is not None,
            host_label=args.host_label,
            host_class=args.host_class,
            target_profile=args.target_profile,
            opt_level=args.opt_level,
            comparison_window=comparison_window,
            toolchain_label=args.toolchain_label,
            toolchain_version=args.toolchain_version,
        )
        if args.toolchain_version and (
            args.toolchain_label is None or args.toolchain_label == "cglc"
        ):
            tool_availability["cglc"]["version"] = args.toolchain_version
        toolchains = build_toolchain_metadata(
            baseline_policy=baseline_policy,
            available=tool_availability["cglc"]["available"],
            status=tool_availability["cglc"]["status"],
            toolchain_version=args.toolchain_version,
        )

        if work_dir is not None:
            report = build_report(
                compiler_path=compiler_path,
                root=root,
                work_dir=work_dir,
                corpus_name=args.corpus,
                fixtures=fixtures,
                targets=targets,
                profiles=profiles,
                repeat=args.repeat,
                warmup=args.warmup,
                dry_run=args.dry_run,
                skipped=cglc_unavailable is not None,
                skip_reason="cglc-unavailable" if cglc_unavailable else None,
                unavailable_tools=["cglc"] if cglc_unavailable else [],
                baseline_policy=baseline_policy,
                tool_availability=tool_availability,
                toolchains=toolchains,
            )
            write_json(report, args.json_output)
        else:
            with tempfile.TemporaryDirectory(prefix="crossgl-perf-corpus-") as tmp:
                report = build_report(
                    compiler_path=compiler_path,
                    root=root,
                    work_dir=Path(tmp).resolve(),
                    corpus_name=args.corpus,
                    fixtures=fixtures,
                    targets=targets,
                    profiles=profiles,
                    repeat=args.repeat,
                    warmup=args.warmup,
                    dry_run=args.dry_run,
                    baseline_policy=baseline_policy,
                    tool_availability=tool_availability,
                    toolchains=toolchains,
                )
                write_json(report, args.json_output)
    except (CorpusBenchmarkError, OSError, subprocess.SubprocessError) as exc:
        print(f"performance corpus benchmark failed: {exc}", file=sys.stderr)
        return 2

    if report["summary"]["failureCount"] and not args.allow_command_failures:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
