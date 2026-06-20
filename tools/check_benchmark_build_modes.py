#!/usr/bin/env python3
"""Self-test benchmark build-mode profile JSON contract."""

from __future__ import annotations

import argparse
import importlib.util
import json
import subprocess
import sys
import tempfile
from pathlib import Path


EXPECTED_FIELDS = [
    "name",
    "displayName",
    "description",
    "buildType",
    "compilerConfig",
    "cglcArgs",
    "cmakeArgs",
    "environment",
    "packageMode",
    "nativeValidation",
]
EXPECTED_BASELINE_CONTEXT_FIELDS = [
    "hostLabel",
    "hostClass",
    "targetProfile",
    "optLevel",
    "comparisonWindow",
    "toolchainLabel",
    "toolchainVersion",
]
EXPECTED_BASELINE_TOP_LEVEL_FIELDS = [
    "schemaVersion",
    "tool",
    "corpusVersion",
    "cases",
    "summary",
]
REPORT_COMPARATOR_BASELINE_FIXTURES = (
    Path(__file__).resolve().parents[1]
    / "tests"
    / "performance"
    / "report-comparator-advisory-baseline.json",
    Path(__file__).resolve().parents[1]
    / "tests"
    / "performance"
    / "report-comparator-advisory-window-baseline.json",
    Path(__file__).resolve().parents[1]
    / "tests"
    / "performance"
    / "report-comparator-advisory-window-candidate.json",
)


def load_tool(root: Path):
    tool_path = root / "tools" / "benchmark_build_modes.py"
    spec = importlib.util.spec_from_file_location("benchmark_build_modes", tool_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"could not import {tool_path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def run_tool(root: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            sys.executable,
            str(root / "tools" / "benchmark_build_modes.py"),
            *args,
        ],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )


def expect(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def check_profile_document(root: Path) -> None:
    tool = load_tool(root)
    tool.validate_profile_contract()
    expect(tuple(tool.PROFILES.keys()) == tuple(tool.PROFILE_ORDER), "registry order")

    try:
        tool.PROFILES["fast"] = tool.get_profile("release")
    except TypeError:
        pass
    else:
        raise AssertionError("profile registry accepted mutation")

    document = tool.profile_document()

    expect(document["schemaVersion"] == 1, "schemaVersion must remain 1")
    expect(document["defaultProfile"] == "release", "default profile must be release")
    expect(document["profileFields"] == EXPECTED_FIELDS, "profile fields changed")

    profiles = document["profiles"]
    names = [profile["name"] for profile in profiles]
    expect(
        names
        == [
            "debug",
            "release",
            "release-o2",
            "release-o2-debug-ir",
            "native-package",
        ],
        "profile order changed",
    )

    for profile in profiles:
        expect(
            list(profile.keys()) == EXPECTED_FIELDS,
            f"{profile['name']}: field order changed",
        )
        expect(isinstance(profile["cglcArgs"], list), f"{profile['name']}: cglcArgs")
        expect(isinstance(profile["cmakeArgs"], list), f"{profile['name']}: cmakeArgs")
        expect(
            isinstance(profile["environment"], list), f"{profile['name']}: environment"
        )
        expect(
            isinstance(profile["nativeValidation"], bool),
            f"{profile['name']}: nativeValidation",
        )

    release = tool.get_profile("release").to_json()
    expect(release["buildType"] == "Release", "release build type")
    expect(release["cglcArgs"] == [], "release must not request debug IR")
    expect(release["packageMode"] == "source", "release package mode")
    expect(release["nativeValidation"] is False, "release native validation")

    release_o2 = tool.get_profile("release-o2").to_json()
    expect(release_o2["buildType"] == "Release", "release-o2 build type")
    expect(release_o2["compilerConfig"] == "O2", "release-o2 compiler config")
    expect(
        release_o2["cglcArgs"] == ["--opt-level", "O2"],
        "release-o2 cglc args",
    )
    expect("--debug-ir" not in release_o2["cglcArgs"], "release-o2 debug IR")
    expect(release_o2["packageMode"] == "source", "release-o2 package mode")
    expect(release_o2["nativeValidation"] is False, "release-o2 validation")

    release_o2_debug_ir = tool.get_profile("release-o2-debug-ir").to_json()
    expect(
        release_o2_debug_ir["buildType"] == "Release",
        "release-o2-debug-ir build type",
    )
    expect(
        release_o2_debug_ir["compilerConfig"] == "O2",
        "release-o2-debug-ir compiler config",
    )
    expect(
        release_o2_debug_ir["cglcArgs"] == ["--opt-level", "O2", "--debug-ir"],
        "release-o2-debug-ir cglc args",
    )
    expect(
        release_o2_debug_ir["packageMode"] == "source",
        "release-o2-debug-ir package mode",
    )
    expect(
        release_o2_debug_ir["nativeValidation"] is False,
        "release-o2-debug-ir validation",
    )

    native_package = tool.get_profile("native-package").to_json()
    expect(native_package["packageMode"] == "native", "native package mode")
    expect(native_package["cglcArgs"] == [], "native-package cglc args")
    expect(native_package["nativeValidation"] is True, "native package validation")

    invalid_profile = tool.BenchmarkBuildProfile(
        name="wrong-name",
        display_name="Invalid",
        description="Invalid profile used to exercise diagnostics.",
        build_type="Release",
        compiler_config="Release",
        package_mode="native",
        native_validation=False,
    )
    diagnostics = tool.profile_contract_errors(
        profiles={"release": invalid_profile},
        profile_order=("release", "missing"),
        default_profile="fast",
    )
    expect(
        "PROFILE_ORDER contains unknown profile(s): missing" in diagnostics,
        "unknown ordered profile diagnostic",
    )
    expect(
        "DEFAULT_PROFILE 'fast' is not defined" in diagnostics,
        "default profile diagnostic",
    )
    expect(
        "release: name 'wrong-name' does not match registry key" in diagnostics,
        "registry key diagnostic",
    )
    expect(
        "release: native package profiles must request native validation"
        in diagnostics,
        "native validation diagnostic",
    )

    try:
        tool.get_profile("fast")
    except ValueError as error:
        expect(
            "unknown benchmark build profile 'fast'" in str(error),
            "unknown profile error",
        )
    else:
        raise AssertionError("unknown profile was accepted")


def complete_baseline_report() -> dict:
    skipped_case = "texture-sample::opengl::release"
    return {
        "schemaVersion": 1,
        "tool": "benchmark_performance_corpus",
        "corpusVersion": "milestone6-smoke-v1",
        "baselinePolicy": {
            "comparisonWindow": {
                "sampleCount": 3,
                "unit": "elapsedNs",
                "warmupCount": 1,
            },
            "hostClass": "linux-x86_64",
            "hostLabel": "ci-linux-x86_64-pool-a",
            "optLevel": "O2",
            "targetProfile": "crossgl-milestone6-smoke",
            "toolchainLabel": "cglc",
            "toolchainVersion": "0.6.0-fixture",
        },
        "cases": [
            {
                "case": "storage-buffer-compute::directx::release",
                "commandProfile": {"name": "release"},
                "fixtureCategory": "storage-buffers",
                "fixtureName": "storage-buffer-compute",
                "optLevel": "O2",
                "profile": "release",
                "target": "directx",
                "skipped": False,
                "skipReason": None,
                "unavailableTools": [],
                "timing": {"elapsedNs": 100, "sampleCount": 3},
            },
            {
                "case": skipped_case,
                "commandProfile": {"name": "release"},
                "fixtureCategory": "texture-sampling",
                "fixtureName": "texture-sample",
                "optLevel": "O2",
                "profile": "release",
                "target": "opengl",
                "skipped": True,
                "status": "skipped",
                "success": False,
                "skipReason": "spirv-opt unavailable",
                "unavailableTools": ["spirv-opt"],
                "timing": None,
            },
        ],
        "summary": {
            "caseCount": 2,
            "caseCategories": ["storage-buffers", "texture-sampling"],
            "caseCountByCategory": {
                "storage-buffers": 1,
                "texture-sampling": 1,
            },
            "caseCountByCommandProfile": {"release": 2},
            "caseCountByProfile": {"release": 2},
            "caseCountByTarget": {"directx": 1, "opengl": 1},
            "commandProfiles": ["release"],
            "skippedCount": 1,
            "skippedCaseCountByReason": {"spirv-opt unavailable": 1},
            "skippedCasesWithUnavailableTools": [skipped_case],
            "skippedToolCaseCountByTool": {"spirv-opt": 1},
            "skippedToolCasesByTool": {"spirv-opt": [skipped_case]},
            "unavailableToolCount": 1,
        },
        "toolAvailability": {
            "cglc": {
                "available": True,
                "status": "available",
                "version": "0.6.0-fixture",
            },
            "spirv-opt": {
                "available": False,
                "optional": True,
                "status": "unavailable",
            },
        },
    }


def incomplete_baseline_report() -> dict:
    payload = complete_baseline_report()
    del payload["baselinePolicy"]
    payload["toolAvailability"] = {}
    return payload


def write_report(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", "utf-8")


def check_baseline_contract(root: Path) -> None:
    tool = load_tool(root)
    contract = tool.baseline_contract_document()

    expect(contract["schemaVersion"] == 1, "baseline contract schema")
    expect(
        contract["kind"] == "advisory-baseline-structural-contract",
        "baseline contract kind",
    )
    expect(contract["policy"]["mode"] == "report-only", "baseline policy mode")
    expect(
        contract["policy"]["structural"]["mode"] == "hard-fail",
        "baseline structure mode",
    )
    expect(
        contract["policy"]["timing"]["mode"] == "report-only",
        "baseline timing mode",
    )
    expect(
        contract["requiredContextFields"] == EXPECTED_BASELINE_CONTEXT_FIELDS,
        "baseline context fields",
    )
    expect(
        contract["requiredTopLevelFields"] == EXPECTED_BASELINE_TOP_LEVEL_FIELDS,
        "baseline top-level fields",
    )
    expect(
        contract["requiredTimedCaseIdentityFields"]
        == ["fixtureName", "target", "profile", "optLevel"],
        "baseline timed case identity fields",
    )

    valid_report = complete_baseline_report()
    expect(
        tool.baseline_report_contract_errors(valid_report) == [],
        "complete advisory baseline report",
    )
    invalid_errors = tool.baseline_report_contract_errors(incomplete_baseline_report())
    for field in EXPECTED_BASELINE_CONTEXT_FIELDS:
        expect(
            any(
                f"missing baseline context field {field!r}" in error
                for error in invalid_errors
            ),
            f"missing {field} diagnostic",
        )
    expect(
        any(
            "toolAvailability.spirv-opt must describe skipped tool" in error
            for error in invalid_errors
        ),
        "skipped tool metadata diagnostic",
    )

    for fixture_path in REPORT_COMPARATOR_BASELINE_FIXTURES:
        if not fixture_path.exists():
            continue
        fixture = json.loads(fixture_path.read_text("utf-8"))
        expect(
            tool.baseline_report_contract_errors(fixture, label=str(fixture_path))
            == [],
            f"checked-in advisory baseline fixture: {fixture_path.name}",
        )


def check_cli(root: Path) -> None:
    result = run_tool(root)
    expect(result.returncode == 0, result.stderr + result.stdout)
    payload = json.loads(result.stdout)
    expect(payload["defaultProfile"] == "release", "CLI default profile")

    selected = run_tool(
        root,
        "--profile",
        "debug",
        "--profile",
        "release-o2-debug-ir",
    )
    expect(selected.returncode == 0, selected.stderr + selected.stdout)
    selected_payload = json.loads(selected.stdout)
    expect(
        [profile["name"] for profile in selected_payload["profiles"]]
        == ["debug", "release-o2-debug-ir"],
        "CLI selected profile order",
    )

    names = run_tool(root, "--list-names")
    expect(names.returncode == 0, names.stderr + names.stdout)
    expect(
        names.stdout.splitlines()
        == [
            "debug",
            "release",
            "release-o2",
            "release-o2-debug-ir",
            "native-package",
        ],
        "CLI list names",
    )

    baseline_fields = run_tool(root, "--list-baseline-fields")
    expect(
        baseline_fields.returncode == 0,
        baseline_fields.stderr + baseline_fields.stdout,
    )
    expect(
        baseline_fields.stdout.splitlines() == EXPECTED_BASELINE_CONTEXT_FIELDS,
        "CLI list baseline fields",
    )

    baseline_contract = run_tool(root, "--baseline-contract")
    expect(
        baseline_contract.returncode == 0,
        baseline_contract.stderr + baseline_contract.stdout,
    )
    baseline_payload = json.loads(baseline_contract.stdout)
    expect(
        baseline_payload["requiredContextFields"] == EXPECTED_BASELINE_CONTEXT_FIELDS,
        "CLI baseline contract",
    )

    with tempfile.TemporaryDirectory(prefix="crossgl-benchmark-build-modes-") as tmp:
        tmp_path = Path(tmp)
        valid_path = tmp_path / "valid-baseline.json"
        invalid_path = tmp_path / "invalid-baseline.json"
        write_report(valid_path, complete_baseline_report())
        write_report(invalid_path, incomplete_baseline_report())

        valid_result = run_tool(root, "--check-baseline-report", str(valid_path))
        expect(valid_result.returncode == 0, valid_result.stderr + valid_result.stdout)
        expect(
            f"validated advisory baseline report: {valid_path}" in valid_result.stdout,
            "CLI validates baseline report",
        )

        baseline_fixture_args: list[str] = []
        for fixture_path in REPORT_COMPARATOR_BASELINE_FIXTURES:
            baseline_fixture_args.extend(["--check-baseline-report", str(fixture_path)])
        fixture_result = run_tool(root, *baseline_fixture_args)
        expect(
            fixture_result.returncode == 0,
            fixture_result.stderr + fixture_result.stdout,
        )
        for fixture_path in REPORT_COMPARATOR_BASELINE_FIXTURES:
            expect(
                f"validated advisory baseline report: {fixture_path}"
                in fixture_result.stdout,
                f"CLI validates advisory baseline fixture: {fixture_path.name}",
            )

        invalid_result = run_tool(root, "--check-baseline-report", str(invalid_path))
        expect(invalid_result.returncode == 1, invalid_result.stdout)
        expect(
            "missing baseline context field 'hostLabel'" in invalid_result.stderr,
            "CLI rejects missing structural baseline fields",
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
        help="Run the benchmark build-mode and baseline-contract self-test suite.",
    )
    args = parser.parse_args()

    root = args.root.resolve()
    check_profile_document(root)
    check_baseline_contract(root)
    check_cli(root)
    print("validated benchmark build-mode profiles")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
