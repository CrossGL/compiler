#!/usr/bin/env python3
"""Validate the v0 CrossGL conformance manifest seed.

The checker is intentionally offline by default. It validates the manifest
schema, fixture paths and hashes, v0 classification buckets, command-profile
mapping, and evidence test names without invoking cglc. When given a configured
build directory it also checks that evidence tests are present in the CTest
inventory.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any


SCHEMA_VERSION = "crossgl-conformance-manifest-v0"
REPORT_SCHEMA_VERSION = "crossgl-conformance-report-v0"
DEFAULT_MANIFEST = Path("tests/conformance/manifest.v0.json")
DEFAULT_EXECUTION_TIMEOUT_SECONDS = 30.0

REQUIRED_TOP_LEVEL_FIELDS = {
    "schema_version",
    "suite",
    "description",
    "coverage_contract",
    "entries",
}

REQUIRED_COVERAGE_CONTRACT_FIELDS = {
    "required_feature_statuses",
    "target_feature_evidence",
}

REQUIRED_FEATURE_STATUS_FIELDS = {
    "feature_group",
    "status",
    "min_entries",
}

REQUIRED_TARGET_FEATURE_EVIDENCE_FIELDS = {
    "required_kinds",
}

REQUIRED_ENTRY_FIELDS = {
    "id",
    "feature_group",
    "language_category",
    "status",
    "command_profile",
    "fixture",
    "fixture_sha256",
    "evidence_tests",
    "notes",
}

OPTIONAL_ENTRY_EVIDENCE_FIELDS = {
    "auxiliary_evidence_tests": "auxiliaryEvidenceTests",
    "target_feature_evidence_tests": "targetFeatureEvidenceTests",
}

ALLOWED_TOP_LEVEL_FIELDS = REQUIRED_TOP_LEVEL_FIELDS
ALLOWED_COVERAGE_CONTRACT_FIELDS = REQUIRED_COVERAGE_CONTRACT_FIELDS
ALLOWED_FEATURE_STATUS_FIELDS = REQUIRED_FEATURE_STATUS_FIELDS
ALLOWED_TARGET_FEATURE_EVIDENCE_FIELDS = REQUIRED_TARGET_FEATURE_EVIDENCE_FIELDS
ALLOWED_ENTRY_FIELDS = (
    REQUIRED_ENTRY_FIELDS
    | set(OPTIONAL_ENTRY_EVIDENCE_FIELDS)
    | {"expected_diagnostic", "target"}
)

ALLOWED_FEATURE_GROUPS = {
    "atomics",
    "compute-basics",
    "control-flow",
    "graphics-stages",
    "known-native-v0-unsupported",
    "resources",
    "storage-images",
    "texture-sampling",
}

ALLOWED_LANGUAGE_CATEGORIES = {
    "compute",
    "graphics",
    "image-operations",
    "native-v0",
    "resource-declarations",
    "statements",
    "texture-operations",
}

ALLOWED_STATUSES = {
    "accepted",
    "unsupported",
}

FEATURE_GROUP_LANGUAGE_CATEGORIES = {
    "atomics": {"compute"},
    "compute-basics": {"compute"},
    "control-flow": {"statements"},
    "graphics-stages": {"graphics"},
    "known-native-v0-unsupported": {"native-v0"},
    "resources": {"resource-declarations"},
    "storage-images": {"image-operations"},
    "texture-sampling": {"texture-operations"},
}

REQUIRED_FEATURE_STATUS_COVERAGE = (
    ("atomics", "accepted"),
    ("compute-basics", "accepted"),
    ("control-flow", "accepted"),
    ("graphics-stages", "accepted"),
    ("known-native-v0-unsupported", "unsupported"),
    ("resources", "accepted"),
    ("storage-images", "accepted"),
    ("texture-sampling", "accepted"),
)

REQUIRED_FEATURE_STATUS_MIN_ENTRIES = {
    ("atomics", "accepted"): 5,
    ("compute-basics", "accepted"): 19,
    ("control-flow", "accepted"): 7,
    ("graphics-stages", "accepted"): 7,
    ("known-native-v0-unsupported", "unsupported"): 16,
    ("resources", "accepted"): 16,
    ("storage-images", "accepted"): 18,
    ("texture-sampling", "accepted"): 34,
}

ALLOWED_TARGETS = {
    "directx",
    "metal",
    "opengl",
    "vulkan",
}

OPTIONAL_NATIVE_UNAVAILABLE_TESTS = {
    "directx": {
        "cglc_directx_toolchain_native_smoke_unavailable",
    },
    "metal": {
        "cglc_build_metal_native_tools_unavailable",
        "cglc_metal_toolchain_native_smoke_unavailable",
    },
    "opengl": {
        "cglc_opengl_toolchain_native_smoke_unavailable",
    },
    "vulkan": {
        "cglc_build_vulkan_native_tools_unavailable",
        "cglc_vulkan_toolchain_native_smoke_unavailable",
    },
}

TARGET_FEATURE_EVIDENCE_KINDS = {
    "planned-unsupported",
    "target-metadata",
    "target-package-explanation",
}

TARGET_PACKAGE_EXPLANATION_EVIDENCE_RE = re.compile(
    r"^cglc_(?:doctor_json|explain_targets)_(?P<target>[A-Za-z0-9]+)_graphics_"
    r".+_(?:(?P<source_package_kind>source)_package|"
    r"(?P<native_package_kind>native)(?:_package)?)_evidence$"
)

TARGET_FEATURE_EVIDENCE_KIND_PATTERNS = {
    "planned-unsupported": re.compile(r"_planned_failure$"),
    "target-metadata": re.compile(
        r"^(?:cglc_dump_debug|cglc_explain_targets)_.*"
        r"(?:metadata|target_capabilities)$"
    ),
    "target-package-explanation": TARGET_PACKAGE_EXPLANATION_EVIDENCE_RE,
}

AUXILIARY_EVIDENCE_KIND_PATTERNS = {
    "backend-dump": re.compile(r"^cglc_dump_backend_"),
    "debug-dump": re.compile(r"^cglc_dump_debug_"),
    "package-inspection": re.compile(r"^cglc_package_verify_"),
    "target-explanation": re.compile(r"^cglc_(?:doctor_json|explain_targets)_"),
}

# Expected diagnostics are concrete compiler codes for the fixture, not just the
# compatibility bucket attached to the unsupported native-v0 entry.
UNSUPPORTED_NATIVE_V0_DIAGNOSTICS = {
    "parse.unsupported-resource-layout-key",
    "parse.unsupported-var-address-space",
    "spec.unsupported-for-native-v0",
}

ALLOWED_DIAGNOSTICS = UNSUPPORTED_NATIVE_V0_DIAGNOSTICS

COMMAND_PROFILES: dict[str, dict[str, Any]] = {
    "frontend-check": {
        "status": "accepted",
        "command": "cglc check {fixture}",
    },
    "hir-dump": {
        "status": "accepted",
        "command": "cglc dump-ir {fixture} --stage hir",
    },
    "source-package-build": {
        "status": "accepted",
        "command": (
            "cglc build {fixture} --target {target} --output <work-dir>/<case>.cglb"
        ),
        "requires_target": "true",
    },
    "native-package-build": {
        "status": "accepted",
        "command": (
            "cglc build {fixture} --target {target} --output <work-dir>/<case>.cglb"
        ),
        "requires_target": "true",
    },
    "unsupported-native-v0-check": {
        "status": "unsupported",
        "command": "cglc check {fixture} --diagnostics-json",
        "diagnostics": sorted(UNSUPPORTED_NATIVE_V0_DIAGNOSTICS),
    },
}

ENTRY_ID_RE = re.compile(r"^[a-z0-9][a-z0-9.-]*$")
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
EVIDENCE_TEST_RE = re.compile(r"\bcglc_[A-Za-z0-9_]+\b")
UNSUPPORTED_ENTRY_ID_PREFIX = "native-v0-unsupported."
UNSUPPORTED_EVIDENCE_RE = re.compile(
    r"^cglc_check_unsupported_native_v0_[A-Za-z0-9_]+_failure$"
)
HIR_EVIDENCE_RE = re.compile(r"^(?:cglc_dump_hir_|cglc_check_.*_hir(?:_|$))")
FRONTEND_CHECK_EVIDENCE_RE = re.compile(r"^cglc_check_")
PACKAGE_BUILD_EVIDENCE_RE = re.compile(
    r"^cglc_build_(?P<target>[A-Za-z0-9]+)_.+_"
    r"(?:(?P<source_package_kind>source)_package|"
    r"(?P<native_package_kind>native)(?:_package)?)$"
)
PLANNED_FAILURE_EVIDENCE_RE = re.compile(r"^cglc_build_[A-Za-z0-9_]+_planned_failure$")


def validate_allowed_fields(
    errors: list[str],
    value: dict[str, Any],
    allowed_fields: set[str],
    label: str,
) -> None:
    unexpected = sorted(set(value) - allowed_fields)
    if unexpected:
        errors.append(f"{label}: unsupported field(s): " + ", ".join(unexpected))


def load_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise ValueError(f"{path}: could not read JSON: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise ValueError(f"{path}: invalid JSON: {exc}") from exc
    if not isinstance(payload, dict):
        raise ValueError(f"{path}: manifest must be a JSON object")
    return payload


def normalized_path_text(value: object) -> str:
    return str(value).replace("\\", "/").lower()


def path_for_report(root: Path, path: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def normalize_source_text(text: str) -> str:
    return text.replace("\r\n", "\n").replace("\r", "\n")


def source_file_sha256(path: Path) -> str:
    return hashlib.sha256(
        normalize_source_text(path.read_text(encoding="utf-8")).encode("utf-8")
    ).hexdigest()


def require_string(
    errors: list[str], entry: dict[str, Any], field: str, entry_label: str
) -> str | None:
    value = entry.get(field)
    if not isinstance(value, str) or not value:
        errors.append(f"{entry_label}: {field!r} must be a non-empty string")
        return None
    return value


def require_string_list(
    errors: list[str], entry: dict[str, Any], field: str, entry_label: str
) -> list[str]:
    value = entry.get(field)
    if not isinstance(value, list) or not value:
        errors.append(f"{entry_label}: {field!r} must be a non-empty array")
        return []

    strings: list[str] = []
    for value_index, item in enumerate(value):
        if not isinstance(item, str) or not item:
            errors.append(
                f"{entry_label}: {field}[{value_index}] must be a non-empty string"
            )
            continue
        strings.append(item)
    return strings


def optional_string_list(
    errors: list[str], entry: dict[str, Any], field: str, entry_label: str
) -> list[str]:
    if field not in entry:
        return []
    return require_string_list(errors, entry, field, entry_label)


def validate_evidence_tests(
    errors: list[str],
    entry_label: str,
    field: str,
    evidence_tests: list[str],
    known_evidence_tests: set[str],
    ctest_names: set[str] | None,
    command_profile: str | None = None,
    target: object = None,
) -> None:
    if evidence_tests != sorted(evidence_tests):
        errors.append(f"{entry_label}: {field} must be sorted")
    if len(set(evidence_tests)) != len(evidence_tests):
        errors.append(f"{entry_label}: {field} contains duplicates")
    for test_name in evidence_tests:
        noun = "evidence test" if field == "evidence_tests" else f"{field} entry"
        if not test_name.startswith("cglc_"):
            errors.append(f"{entry_label}: {noun} must start with cglc_: {test_name}")
        if test_name not in known_evidence_tests:
            errors.append(f"{entry_label}: unknown {noun} {test_name!r}")
        allows_missing_optional_native = (
            ctest_names is not None
            and field == "evidence_tests"
            and ctest_inventory_allows_missing_optional_native_evidence(
                command_profile,
                target,
                test_name,
                ctest_names,
            )
        )
        if (
            ctest_names is not None
            and test_name not in ctest_names
            and not allows_missing_optional_native
        ):
            errors.append(
                f"{entry_label}: CTest inventory is missing {noun} {test_name!r}"
            )


def ctest_inventory_allows_missing_optional_native_evidence(
    command_profile: str | None,
    target: object,
    test_name: str,
    ctest_names: set[str],
) -> bool:
    if command_profile != "native-package-build" or not isinstance(target, str):
        return False
    match = PACKAGE_BUILD_EVIDENCE_RE.match(test_name)
    if match is None or match.group("target") != target:
        return False
    package_kind = match.group("source_package_kind") or match.group(
        "native_package_kind"
    )
    if package_kind != "native":
        return False
    unavailable_tests = OPTIONAL_NATIVE_UNAVAILABLE_TESTS.get(target, set())
    return bool(unavailable_tests.intersection(ctest_names))


def target_feature_evidence_kind(test_name: str) -> str | None:
    matches = [
        kind
        for kind, pattern in TARGET_FEATURE_EVIDENCE_KIND_PATTERNS.items()
        if pattern.search(test_name)
    ]
    if len(matches) != 1:
        return None
    return matches[0]


def auxiliary_evidence_kind(test_name: str) -> str | None:
    matches = [
        kind
        for kind, pattern in AUXILIARY_EVIDENCE_KIND_PATTERNS.items()
        if pattern.search(test_name)
    ]
    if len(matches) != 1:
        return None
    return matches[0]


def validate_auxiliary_evidence_tests(
    errors: list[str],
    entry_label: str,
    evidence_tests: list[str],
    target_feature_evidence_tests: list[str],
    auxiliary_evidence_tests: list[str],
) -> None:
    shared_evidence_tests = sorted(
        set(evidence_tests).intersection(auxiliary_evidence_tests)
    )
    if shared_evidence_tests:
        errors.append(
            f"{entry_label}: auxiliary_evidence_tests must not duplicate "
            "evidence_tests: " + ", ".join(shared_evidence_tests)
        )

    shared_target_feature_tests = sorted(
        set(target_feature_evidence_tests).intersection(auxiliary_evidence_tests)
    )
    if shared_target_feature_tests:
        errors.append(
            f"{entry_label}: auxiliary_evidence_tests must not duplicate "
            "target_feature_evidence_tests: " + ", ".join(shared_target_feature_tests)
        )

    for test_name in auxiliary_evidence_tests:
        if auxiliary_evidence_kind(test_name) is None:
            errors.append(
                f"{entry_label}: auxiliary_evidence_tests entry {test_name!r} "
                "must be a backend-dump, debug-dump, package-inspection, or "
                "target-explanation evidence test"
            )


def validate_target_feature_evidence_tests(
    errors: list[str],
    entry_label: str,
    command_profile: str | None,
    target: object,
    evidence_tests: list[str],
) -> None:
    for test_name in evidence_tests:
        kind = target_feature_evidence_kind(test_name)
        if kind is None:
            errors.append(
                f"{entry_label}: target_feature_evidence_tests entry {test_name!r} "
                "must be a planned-unsupported, target-metadata, or "
                "target-package-explanation evidence test"
            )
        elif kind == "planned-unsupported":
            if not PLANNED_FAILURE_EVIDENCE_RE.match(test_name):
                errors.append(
                    f"{entry_label}: planned unsupported target evidence must be a "
                    f"cglc_build_*_planned_failure test: {test_name!r}"
                )
            tokens = set(test_name.split("_"))
            if not tokens.intersection(ALLOWED_TARGETS):
                errors.append(
                    f"{entry_label}: planned unsupported target evidence must carry "
                    f"one target token from {sorted(ALLOWED_TARGETS)!r}: {test_name!r}"
                )
        elif kind == "target-package-explanation":
            match = TARGET_PACKAGE_EXPLANATION_EVIDENCE_RE.match(test_name)
            if match is None:
                continue
            if command_profile not in {"source-package-build", "native-package-build"}:
                errors.append(
                    f"{entry_label}: target package explanation evidence is only "
                    f"valid for package build entries: {test_name!r}"
                )
                continue
            expected_package_kind = (
                "source" if command_profile == "source-package-build" else "native"
            )
            package_kind = match.group("source_package_kind") or match.group(
                "native_package_kind"
            )
            if match.group("target") != target:
                errors.append(
                    f"{entry_label}: target package explanation evidence target must "
                    f"be {target!r}: {test_name!r}"
                )
            if package_kind != expected_package_kind:
                errors.append(
                    f"{entry_label}: target package explanation evidence must be a "
                    f"{expected_package_kind} package test: {test_name!r}"
                )


def validate_classification_metadata(
    errors: list[str],
    entry_label: str,
    entry_id: str | None,
    feature_group: str | None,
    language_category: str | None,
    status: str | None,
) -> None:
    if feature_group and language_category:
        allowed_categories = FEATURE_GROUP_LANGUAGE_CATEGORIES.get(feature_group)
        if (
            allowed_categories is not None
            and language_category not in allowed_categories
        ):
            errors.append(
                f"{entry_label}: language_category {language_category!r} is not valid "
                f"for feature_group {feature_group!r}; expected one of "
                f"{sorted(allowed_categories)!r}"
            )

    if (
        status == "accepted"
        and entry_id
        and feature_group
        and feature_group != "known-native-v0-unsupported"
        and not entry_id.startswith(f"{feature_group}.")
    ):
        errors.append(
            f"{entry_label}: accepted entry id must use feature_group prefix "
            f"{feature_group + '.'!r}"
        )
    if status == "accepted" and feature_group == "known-native-v0-unsupported":
        errors.append(
            f"{entry_label}: accepted entries must not use feature_group "
            "'known-native-v0-unsupported'"
        )


def validate_command_profile_evidence(
    errors: list[str],
    entry_label: str,
    command_profile: str | None,
    target: object,
    evidence_tests: list[str],
) -> None:
    if command_profile == "frontend-check":
        for test_name in evidence_tests:
            if not FRONTEND_CHECK_EVIDENCE_RE.match(test_name):
                errors.append(
                    f"{entry_label}: frontend-check evidence must be a cglc_check_* "
                    f"test: {test_name!r}"
                )
    elif command_profile == "hir-dump":
        for test_name in evidence_tests:
            if not HIR_EVIDENCE_RE.match(test_name):
                errors.append(
                    f"{entry_label}: hir-dump evidence must name HIR coverage: "
                    f"{test_name!r}"
                )
    elif command_profile in {"source-package-build", "native-package-build"}:
        if not isinstance(target, str) or not target:
            return
        expected_package_kind = (
            "source" if command_profile == "source-package-build" else "native"
        )
        target_build_tests = []
        for test_name in evidence_tests:
            match = PACKAGE_BUILD_EVIDENCE_RE.match(test_name)
            if match is None:
                continue
            package_kind = match.group("source_package_kind") or match.group(
                "native_package_kind"
            )
            if match.group("target") != target:
                errors.append(
                    f"{entry_label}: {command_profile} package evidence target must "
                    f"be {target!r}: {test_name!r}"
                )
                continue
            if package_kind != expected_package_kind:
                errors.append(
                    f"{entry_label}: {command_profile} package evidence must be a "
                    f"{expected_package_kind} package test: {test_name!r}"
                )
                continue
            target_build_tests.append(test_name)
        if not target_build_tests:
            errors.append(
                f"{entry_label}: {command_profile} evidence_tests must include a "
                f"cglc_build_{target}_*_{expected_package_kind}_package "
                "evidence test"
            )


def target_feature_evidence_kind_counts(
    entries: list[dict[str, Any]],
) -> dict[str, int]:
    counts = {kind: 0 for kind in sorted(TARGET_FEATURE_EVIDENCE_KINDS)}
    for entry in entries:
        evidence_tests = entry.get("target_feature_evidence_tests")
        if not isinstance(evidence_tests, list):
            continue
        for test_name in evidence_tests:
            if isinstance(test_name, str):
                kind = target_feature_evidence_kind(test_name)
                if kind is not None:
                    counts[kind] += 1
    return counts


def cmake_test_sources(root: Path) -> list[Path]:
    sources = [root / "CMakeLists.txt"]
    sources.extend(sorted((root / "cmake").glob("*.cmake")))
    sources.extend(sorted((root / "tests" / "cmake").glob("*.cmake")))
    return [path for path in sources if path.exists()]


def discover_known_evidence_tests(root: Path) -> set[str]:
    names: set[str] = set()
    for path in cmake_test_sources(root):
        try:
            text = path.read_text(encoding="utf-8")
        except OSError:
            continue
        names.update(EVIDENCE_TEST_RE.findall(text))
    return names


def run(command: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        check=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )


def load_ctest_inventory(build_dir: Path, ctest_config: str | None) -> set[str]:
    ctest = shutil.which("ctest")
    if ctest is None:
        raise RuntimeError("ctest was not found on PATH")

    command = [ctest, "--test-dir", str(build_dir)]
    if ctest_config:
        command.extend(["-C", ctest_config])
    command.append("--show-only=json-v1")

    result = run(command)
    if result.returncode != 0:
        raise RuntimeError(
            "ctest JSON inventory failed:\n"
            f"stdout:\n{result.stdout}\n"
            f"stderr:\n{result.stderr}"
        )

    try:
        inventory = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"ctest JSON inventory was invalid: {exc}") from exc

    tests = inventory.get("tests", [])
    if not isinstance(tests, list):
        raise RuntimeError("ctest JSON inventory tests field was not an array")
    return {str(test.get("name")) for test in tests if isinstance(test, dict)}


def entry_profile_name(entry: dict[str, Any]) -> str:
    return str(entry.get("command_profile", entry.get("commandProfile")))


def entry_expected_diagnostic(entry: dict[str, Any]) -> str | None:
    value = entry.get("expected_diagnostic", entry.get("expectedDiagnostic"))
    if isinstance(value, str) and value:
        return value
    return None


def render_command(entry: dict[str, Any]) -> str:
    profile = entry_profile_name(entry)
    fixture = str(entry["fixture"])
    target = str(entry.get("target", "<target>"))
    return str(COMMAND_PROFILES[profile]["command"]).format(
        fixture=fixture,
        target=target,
        case=str(entry["id"]).replace(".", "-"),
    )


def profile_expected_diagnostics(profile: dict[str, Any] | None) -> set[str]:
    if profile is None:
        return set()
    diagnostics = profile.get("diagnostics")
    if isinstance(diagnostics, list):
        return {diagnostic for diagnostic in diagnostics if isinstance(diagnostic, str)}
    diagnostic = profile.get("diagnostic")
    if isinstance(diagnostic, str) and diagnostic:
        return {diagnostic}
    return set()


def executable_profile_supports_unsupported(profile: dict[str, Any]) -> bool:
    command = str(profile.get("command", ""))
    return (
        bool(profile_expected_diagnostics(profile)) and "--diagnostics-json" in command
    )


def entry_execution_skip_reason(
    entry: dict[str, Any], skip_native_package_builds: bool = False
) -> str | None:
    profile_name = entry_profile_name(entry)
    if skip_native_package_builds and profile_name == "native-package-build":
        return "native package build profile skipped for platform-stable execution"

    status = str(entry["status"])
    if status == "accepted":
        return None

    profile = COMMAND_PROFILES[profile_name]
    if status == "unsupported" and executable_profile_supports_unsupported(profile):
        return None
    return "unsupported entry does not use a diagnostics-json command profile"


def output_path_for_entry(work_dir: Path, entry: dict[str, Any]) -> Path:
    case = str(entry["id"]).replace(".", "-")
    return work_dir / f"{case}.cglb"


def remove_existing_output_artifact(output_path: Path) -> bool:
    if not output_path.exists() and not output_path.is_symlink():
        return False
    if output_path.is_dir() and not output_path.is_symlink():
        shutil.rmtree(output_path)
    else:
        output_path.unlink()
    return True


def command_argv_for_entry(
    root: Path, cglc: Path, work_dir: Path, entry: dict[str, Any]
) -> tuple[list[str], Path | None]:
    fixture = root / str(entry["fixture"])
    profile = entry_profile_name(entry)
    if profile == "frontend-check":
        return [str(cglc), "check", str(fixture)], None
    if profile == "hir-dump":
        return [str(cglc), "dump-ir", str(fixture), "--stage", "hir"], None
    if profile in {"source-package-build", "native-package-build"}:
        output_path = output_path_for_entry(work_dir, entry)
        return (
            [
                str(cglc),
                "build",
                str(fixture),
                "--target",
                str(entry["target"]),
                "--output",
                str(output_path),
            ],
            output_path,
        )
    if profile == "unsupported-native-v0-check":
        return [str(cglc), "check", str(fixture), "--diagnostics-json"], None
    raise ValueError(f"unsupported command_profile {profile!r}")


def diagnostics_codes(stdout: str) -> tuple[list[str], str | None]:
    try:
        payload = json.loads(stdout)
    except json.JSONDecodeError as exc:
        return [], f"diagnostics-json stdout was invalid: {exc}"

    diagnostics = payload.get("diagnostics")
    if not isinstance(diagnostics, list):
        return [], "diagnostics-json stdout did not contain a diagnostics array"

    codes: list[str] = []
    for diagnostic in diagnostics:
        if not isinstance(diagnostic, dict):
            continue
        code = diagnostic.get("code")
        if isinstance(code, str) and code:
            codes.append(code)
    return sorted(set(codes)), None


def execution_result_for_completed_process(
    root: Path,
    entry: dict[str, Any],
    result: subprocess.CompletedProcess[str],
    output_path: Path | None,
    artifact_preexisting: bool = False,
) -> dict[str, Any]:
    execution: dict[str, Any] = {
        "command": render_command(entry),
        "exitCode": result.returncode,
        "status": "passed",
    }

    if output_path is not None:
        artifact_exists = output_path.exists()
        execution["output"] = path_for_report(root, output_path)
        execution["artifactPreExisting"] = artifact_preexisting
        execution["artifactExists"] = artifact_exists
    else:
        artifact_exists = True

    if entry["status"] == "accepted":
        if result.returncode != 0:
            execution["status"] = "failed"
            execution["failure"] = f"expected exit 0, got {result.returncode}"
        elif not artifact_exists:
            execution["status"] = "failed"
            execution["failure"] = "expected build artifact was not created"
        return execution

    diagnostic_codes, diagnostic_error = diagnostics_codes(result.stdout)
    execution["diagnosticCodes"] = diagnostic_codes
    expected_diagnostic = entry_expected_diagnostic(entry)
    if expected_diagnostic is not None:
        diagnostic_matches_expected = expected_diagnostic in diagnostic_codes
        execution["diagnosticMatchesExpected"] = diagnostic_matches_expected

    if result.returncode == 0:
        execution["status"] = "failed"
        execution["failure"] = "expected diagnostics failure, got exit 0"
    elif diagnostic_error is not None:
        execution["status"] = "failed"
        execution["failure"] = diagnostic_error
    elif expected_diagnostic is not None and not diagnostic_matches_expected:
        execution["status"] = "failed"
        execution["failure"] = (
            f"expected diagnostic {expected_diagnostic!r}, got {diagnostic_codes!r}"
        )
    return execution


def execute_entry(
    root: Path,
    cglc: Path,
    work_dir: Path,
    entry: dict[str, Any],
    timeout_seconds: float,
    skip_native_package_builds: bool = False,
) -> dict[str, Any]:
    skip_reason = entry_execution_skip_reason(entry, skip_native_package_builds)
    if skip_reason is not None:
        return {
            "command": render_command(entry),
            "exitCode": None,
            "reason": skip_reason,
            "status": "skipped",
        }

    argv, output_path = command_argv_for_entry(root, cglc, work_dir, entry)
    artifact_preexisting = False
    if output_path is not None:
        try:
            artifact_preexisting = remove_existing_output_artifact(output_path)
        except OSError as exc:
            return {
                "command": render_command(entry),
                "exitCode": None,
                "output": path_for_report(root, output_path),
                "artifactPreExisting": True,
                "artifactExists": output_path.exists(),
                "failure": f"could not clear existing build artifact: {exc}",
                "status": "failed",
            }

    try:
        result = subprocess.run(
            argv,
            check=False,
            cwd=str(root),
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout_seconds,
        )
    except subprocess.TimeoutExpired:
        return {
            "command": render_command(entry),
            "exitCode": None,
            "failure": f"command timed out after {timeout_seconds:g}s",
            "status": "failed",
        }

    return execution_result_for_completed_process(
        root, entry, result, output_path, artifact_preexisting
    )


def add_execution_results(
    root: Path,
    report: dict[str, Any],
    cglc: Path,
    work_dir: Path,
    timeout_seconds: float,
    skip_native_package_builds: bool = False,
) -> dict[str, Any]:
    work_dir.mkdir(parents=True, exist_ok=True)

    entries = report["entries"]
    failures: list[dict[str, str]] = []
    diagnostic_mismatches: list[dict[str, Any]] = []
    executed = 0
    skipped = 0
    passed = 0
    failed = 0

    for entry in entries:
        execution = execute_entry(
            root,
            cglc,
            work_dir,
            entry,
            timeout_seconds,
            skip_native_package_builds,
        )
        entry["execution"] = execution
        status = execution["status"]
        if status == "skipped":
            skipped += 1
        else:
            executed += 1
        if status == "passed":
            passed += 1
        elif status == "failed":
            failed += 1
            failures.append(
                {
                    "id": str(entry["id"]),
                    "failure": str(execution.get("failure", "execution failed")),
                }
            )
        if execution.get("diagnosticMatchesExpected") is False:
            diagnostic_mismatches.append(
                {
                    "actual": execution.get("diagnosticCodes", []),
                    "expected": entry_expected_diagnostic(entry),
                    "id": str(entry["id"]),
                }
            )

    report["summary"]["execution"] = {
        "cglc": path_for_report(root, cglc),
        "diagnosticMismatchCount": len(diagnostic_mismatches),
        "diagnosticMismatches": diagnostic_mismatches,
        "entryCount": len(entries),
        "executed": executed,
        "failed": failed,
        "failures": failures,
        "passed": passed,
        "skipped": skipped,
        "workDir": path_for_report(root, work_dir),
    }
    return report


def sorted_count_map(entries: list[dict[str, Any]], key: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for entry in entries:
        value = str(entry[key])
        counts[value] = counts.get(value, 0) + 1
    return dict(sorted(counts.items()))


def evidence_field_summary(entries: list[dict[str, Any]], field: str) -> dict[str, Any]:
    entries_with_evidence = [
        entry for entry in entries if isinstance(entry.get(field), list)
    ]
    return {
        "entryCount": len(entries_with_evidence),
        "testCount": sum(len(entry[field]) for entry in entries_with_evidence),
        "byFeatureGroup": sorted_count_map(entries_with_evidence, "feature_group")
        if entries_with_evidence
        else {},
    }


def target_feature_evidence_summary(entries: list[dict[str, Any]]) -> dict[str, Any]:
    summary = evidence_field_summary(entries, "target_feature_evidence_tests")
    summary["byEvidenceKind"] = target_feature_evidence_kind_counts(entries)
    return summary


def build_report(
    root: Path, manifest_path: Path, payload: dict[str, Any]
) -> dict[str, Any]:
    entries = payload["entries"]
    report_entries: list[dict[str, Any]] = []
    for entry in entries:
        report_entry: dict[str, Any] = {
            "id": entry["id"],
            "status": entry["status"],
            "featureGroup": entry["feature_group"],
            "languageCategory": entry["language_category"],
            "fixture": entry["fixture"],
            "fixtureSha256": entry["fixture_sha256"],
            "commandProfile": entry["command_profile"],
            "command": render_command(entry),
            "evidenceTests": entry["evidence_tests"],
        }
        if "target" in entry:
            report_entry["target"] = entry["target"]
        if "expected_diagnostic" in entry:
            report_entry["expectedDiagnostic"] = entry["expected_diagnostic"]
        for manifest_field, report_field in OPTIONAL_ENTRY_EVIDENCE_FIELDS.items():
            if manifest_field in entry:
                report_entry[report_field] = entry[manifest_field]
                if manifest_field == "target_feature_evidence_tests":
                    report_entry["targetFeatureEvidenceKinds"] = [
                        target_feature_evidence_kind(test_name)
                        for test_name in entry[manifest_field]
                    ]
        report_entries.append(report_entry)

    return {
        "schemaVersion": REPORT_SCHEMA_VERSION,
        "manifestSchemaVersion": payload["schema_version"],
        "suite": payload["suite"],
        "manifestPath": path_for_report(root, manifest_path),
        "summary": {
            "total": len(entries),
            "byStatus": sorted_count_map(entries, "status"),
            "byFeatureGroup": sorted_count_map(entries, "feature_group"),
            "byLanguageCategory": sorted_count_map(entries, "language_category"),
            "byCommandProfile": sorted_count_map(entries, "command_profile"),
            "targetFeatureEvidence": target_feature_evidence_summary(entries),
        },
        "entries": report_entries,
    }


def validate_entry(
    root: Path,
    manifest_path: Path,
    entry: dict[str, Any],
    index: int,
    known_evidence_tests: set[str],
    ctest_names: set[str] | None,
) -> list[str]:
    errors: list[str] = []
    entry_label = f"{manifest_path}: entries[{index}]"
    validate_allowed_fields(errors, entry, ALLOWED_ENTRY_FIELDS, entry_label)

    missing_entry = sorted(REQUIRED_ENTRY_FIELDS - entry.keys())
    if missing_entry:
        errors.append(
            f"{entry_label}: missing required field(s): " + ", ".join(missing_entry)
        )

    entry_id = require_string(errors, entry, "id", entry_label)
    if entry_id and not ENTRY_ID_RE.match(entry_id):
        errors.append(f"{entry_label}: invalid id {entry_id!r}")

    feature_group = require_string(errors, entry, "feature_group", entry_label)
    if feature_group and feature_group not in ALLOWED_FEATURE_GROUPS:
        errors.append(f"{entry_label}: unsupported feature_group {feature_group!r}")

    language_category = require_string(errors, entry, "language_category", entry_label)
    if language_category and language_category not in ALLOWED_LANGUAGE_CATEGORIES:
        errors.append(
            f"{entry_label}: unsupported language_category {language_category!r}"
        )

    status = require_string(errors, entry, "status", entry_label)
    if status and status not in ALLOWED_STATUSES:
        errors.append(f"{entry_label}: unsupported status {status!r}")

    validate_classification_metadata(
        errors, entry_label, entry_id, feature_group, language_category, status
    )

    command_profile = require_string(errors, entry, "command_profile", entry_label)
    profile = COMMAND_PROFILES.get(command_profile or "")
    if command_profile and profile is None:
        errors.append(f"{entry_label}: unsupported command_profile {command_profile!r}")
    elif profile is not None and status and status != profile["status"]:
        errors.append(
            f"{entry_label}: status {status!r} does not match command_profile "
            f"{command_profile!r} expected status {profile['status']!r}"
        )

    target = entry.get("target")
    if profile and profile.get("requires_target") == "true":
        if not isinstance(target, str) or not target:
            errors.append(f"{entry_label}: target is required for {command_profile!r}")
        elif target not in ALLOWED_TARGETS:
            errors.append(f"{entry_label}: unsupported target {target!r}")
    elif target is not None:
        errors.append(f"{entry_label}: target is only valid for package profiles")

    fixture = require_string(errors, entry, "fixture", entry_label)
    fixture_file: Path | None = None
    if fixture:
        fixture_path = Path(fixture)
        if fixture_path.is_absolute() or ".." in fixture_path.parts:
            errors.append(f"{entry_label}: fixture must be a repository-relative path")
        elif fixture_path.suffix != ".cgl":
            errors.append(f"{entry_label}: fixture must use the .cgl extension")
        elif not (root / fixture_path).is_file():
            errors.append(f"{entry_label}: fixture does not exist: {fixture}")
        else:
            fixture_file = root / fixture_path

    fixture_sha256 = require_string(errors, entry, "fixture_sha256", entry_label)
    if fixture_sha256:
        if not SHA256_RE.match(fixture_sha256):
            errors.append(
                f"{entry_label}: fixture_sha256 must be a lowercase SHA-256 hex digest"
            )
        elif fixture_file is not None:
            try:
                actual_sha256 = source_file_sha256(fixture_file)
            except UnicodeDecodeError as exc:
                errors.append(
                    f"{entry_label}: fixture must be UTF-8 text for hashing: {exc}"
                )
            except OSError as exc:
                errors.append(f"{entry_label}: could not hash fixture: {exc}")
            else:
                if fixture_sha256 != actual_sha256:
                    errors.append(
                        f"{entry_label}: fixture_sha256 mismatch for {fixture}; "
                        f"expected {actual_sha256}, got {fixture_sha256}"
                    )

    evidence_tests = require_string_list(errors, entry, "evidence_tests", entry_label)
    validate_evidence_tests(
        errors,
        entry_label,
        "evidence_tests",
        evidence_tests,
        known_evidence_tests,
        ctest_names,
        command_profile,
        target,
    )
    validate_command_profile_evidence(
        errors, entry_label, command_profile, target, evidence_tests
    )

    optional_evidence_tests_by_field: dict[str, list[str]] = {}
    for optional_field in OPTIONAL_ENTRY_EVIDENCE_FIELDS:
        optional_tests = optional_string_list(
            errors, entry, optional_field, entry_label
        )
        optional_evidence_tests_by_field[optional_field] = optional_tests
        validate_evidence_tests(
            errors,
            entry_label,
            optional_field,
            optional_tests,
            known_evidence_tests,
            ctest_names,
            command_profile,
            target,
        )
        if optional_field == "target_feature_evidence_tests":
            if optional_tests and status != "accepted":
                errors.append(
                    f"{entry_label}: target_feature_evidence_tests is only valid for "
                    "accepted entries"
                )
            shared_tests = sorted(set(evidence_tests).intersection(optional_tests))
            if shared_tests:
                errors.append(
                    f"{entry_label}: target_feature_evidence_tests must not duplicate "
                    "evidence_tests: " + ", ".join(shared_tests)
                )
            validate_target_feature_evidence_tests(
                errors, entry_label, command_profile, target, optional_tests
            )

    validate_auxiliary_evidence_tests(
        errors,
        entry_label,
        evidence_tests,
        optional_evidence_tests_by_field.get("target_feature_evidence_tests", []),
        optional_evidence_tests_by_field.get("auxiliary_evidence_tests", []),
    )

    if status == "unsupported":
        if entry_id and not entry_id.startswith(UNSUPPORTED_ENTRY_ID_PREFIX):
            errors.append(
                f"{entry_label}: unsupported entries must use id prefix "
                f"{UNSUPPORTED_ENTRY_ID_PREFIX!r}"
            )
        if feature_group != "known-native-v0-unsupported":
            errors.append(
                f"{entry_label}: unsupported entries must use "
                "feature_group 'known-native-v0-unsupported'"
            )
        if language_category != "native-v0":
            errors.append(
                f"{entry_label}: unsupported entries must use "
                "language_category 'native-v0'"
            )
        expected_diagnostic = require_string(
            errors, entry, "expected_diagnostic", entry_label
        )
        if expected_diagnostic and expected_diagnostic not in ALLOWED_DIAGNOSTICS:
            errors.append(
                f"{entry_label}: unsupported expected_diagnostic "
                f"{expected_diagnostic!r}"
            )
        profile_diagnostics = profile_expected_diagnostics(profile)
        if expected_diagnostic and expected_diagnostic not in profile_diagnostics:
            errors.append(
                f"{entry_label}: expected_diagnostic {expected_diagnostic!r} "
                "does not match command_profile diagnostics "
                f"{sorted(profile_diagnostics)!r}"
            )
        if fixture and normalized_path_text(fixture).split("/")[0:2] != [
            "tests",
            "check-failures",
        ]:
            errors.append(
                f"{entry_label}: unsupported fixtures must live under "
                "tests/check-failures"
            )
        for test_name in evidence_tests:
            if not UNSUPPORTED_EVIDENCE_RE.match(test_name):
                errors.append(
                    f"{entry_label}: unsupported evidence test must match "
                    f"{UNSUPPORTED_EVIDENCE_RE.pattern}: {test_name}"
                )
    elif "expected_diagnostic" in entry:
        errors.append(
            f"{entry_label}: expected_diagnostic is only valid for unsupported entries"
        )

    require_string(errors, entry, "notes", entry_label)
    return errors


def validate_required_feature_statuses(
    errors: list[str],
    manifest_path: Path,
    required_statuses: object,
    entries: list[dict[str, Any]],
) -> None:
    context = f"{manifest_path}: coverage_contract.required_feature_statuses"
    if not isinstance(required_statuses, list) or not required_statuses:
        errors.append(f"{context} must be a non-empty array")
        return

    valid_entries = [entry for entry in entries if isinstance(entry, dict)]
    actual_counts: dict[tuple[str, str], int] = {}
    for entry in valid_entries:
        feature_group = entry.get("feature_group")
        status = entry.get("status")
        if isinstance(feature_group, str) and isinstance(status, str):
            key = (feature_group, status)
            actual_counts[key] = actual_counts.get(key, 0) + 1

    seen: set[tuple[str, str]] = set()
    coverage_pairs: list[tuple[str, str]] = []
    for index, requirement in enumerate(required_statuses):
        requirement_label = f"{context}[{index}]"
        if not isinstance(requirement, dict):
            errors.append(f"{requirement_label}: requirement must be a JSON object")
            continue
        validate_allowed_fields(
            errors,
            requirement,
            ALLOWED_FEATURE_STATUS_FIELDS,
            requirement_label,
        )

        missing = sorted(REQUIRED_FEATURE_STATUS_FIELDS - requirement.keys())
        if missing:
            errors.append(
                f"{requirement_label}: missing required field(s): " + ", ".join(missing)
            )

        feature_group = require_string(
            errors, requirement, "feature_group", requirement_label
        )
        if feature_group and feature_group not in ALLOWED_FEATURE_GROUPS:
            errors.append(
                f"{requirement_label}: unsupported feature_group {feature_group!r}"
            )

        status = require_string(errors, requirement, "status", requirement_label)
        if status and status not in ALLOWED_STATUSES:
            errors.append(f"{requirement_label}: unsupported status {status!r}")

        min_entries = requirement.get("min_entries")
        if not isinstance(min_entries, int) or isinstance(min_entries, bool):
            errors.append(f"{requirement_label}: min_entries must be an integer")
        elif min_entries < 1:
            errors.append(f"{requirement_label}: min_entries must be at least 1")

        if not feature_group or not status:
            continue
        key = (feature_group, status)
        if key in seen:
            errors.append(
                f"{requirement_label}: duplicate feature/status coverage "
                f"{feature_group!r}/{status!r}"
            )
        seen.add(key)
        coverage_pairs.append(key)

        if isinstance(min_entries, int) and not isinstance(min_entries, bool):
            required_floor = REQUIRED_FEATURE_STATUS_MIN_ENTRIES.get(key)
            if required_floor is not None and min_entries < required_floor:
                errors.append(
                    f"{requirement_label}: min_entries for feature_group "
                    f"{feature_group!r} status {status!r} must be at least "
                    f"{required_floor}, got {min_entries}"
                )
            actual = actual_counts.get(key, 0)
            if actual < min_entries:
                errors.append(
                    f"{requirement_label}: requires at least {min_entries} "
                    f"{status} entr{'y' if min_entries == 1 else 'ies'} for "
                    f"feature_group {feature_group!r}, found {actual}"
                )

    expected_pairs = sorted(REQUIRED_FEATURE_STATUS_COVERAGE)
    if sorted(coverage_pairs) != expected_pairs:
        errors.append(
            f"{context} must cover exactly these feature/status pairs: "
            + ", ".join(f"{group}/{status}" for group, status in expected_pairs)
        )
    if coverage_pairs != sorted(coverage_pairs):
        errors.append(f"{context} must be sorted by feature_group and status")


def validate_target_feature_evidence_contract(
    errors: list[str],
    manifest_path: Path,
    target_feature_contract: object,
    entries: list[dict[str, Any]],
) -> None:
    context = f"{manifest_path}: coverage_contract.target_feature_evidence"
    if not isinstance(target_feature_contract, dict):
        errors.append(f"{context} must be a JSON object")
        return
    validate_allowed_fields(
        errors,
        target_feature_contract,
        ALLOWED_TARGET_FEATURE_EVIDENCE_FIELDS,
        context,
    )

    missing = sorted(
        REQUIRED_TARGET_FEATURE_EVIDENCE_FIELDS - target_feature_contract.keys()
    )
    if missing:
        errors.append(f"{context}: missing required field(s): " + ", ".join(missing))

    required_kinds = target_feature_contract.get("required_kinds")
    if not isinstance(required_kinds, list) or not required_kinds:
        errors.append(f"{context}.required_kinds must be a non-empty array")
        return

    kinds: list[str] = []
    for index, kind in enumerate(required_kinds):
        kind_label = f"{context}.required_kinds[{index}]"
        if not isinstance(kind, str) or not kind:
            errors.append(f"{kind_label} must be a non-empty string")
            continue
        if kind not in TARGET_FEATURE_EVIDENCE_KINDS:
            errors.append(f"{kind_label}: unsupported evidence kind {kind!r}")
        kinds.append(kind)

    if len(kinds) != len(set(kinds)):
        errors.append(f"{context}.required_kinds contains duplicates")
    if kinds != sorted(kinds):
        errors.append(f"{context}.required_kinds must be sorted")
    expected_kinds = sorted(TARGET_FEATURE_EVIDENCE_KINDS)
    if sorted(kinds) != expected_kinds:
        errors.append(
            f"{context}.required_kinds must cover exactly these target feature "
            "evidence kinds: " + ", ".join(expected_kinds)
        )

    kind_counts = target_feature_evidence_kind_counts(entries)
    for kind in kinds:
        if kind in TARGET_FEATURE_EVIDENCE_KINDS and kind_counts.get(kind, 0) == 0:
            errors.append(
                f"{context}: required target feature evidence kind {kind!r} "
                "has no matching tests"
            )


def validate_coverage_contract(
    errors: list[str],
    manifest_path: Path,
    payload: dict[str, Any],
    entries: list[dict[str, Any]],
) -> None:
    contract = payload.get("coverage_contract")
    context = f"{manifest_path}: coverage_contract"
    if not isinstance(contract, dict):
        errors.append(f"{context} must be a JSON object")
        return
    validate_allowed_fields(errors, contract, ALLOWED_COVERAGE_CONTRACT_FIELDS, context)

    missing = sorted(REQUIRED_COVERAGE_CONTRACT_FIELDS - contract.keys())
    if missing:
        errors.append(f"{context}: missing required field(s): " + ", ".join(missing))

    validate_required_feature_statuses(
        errors,
        manifest_path,
        contract.get("required_feature_statuses"),
        entries,
    )
    validate_target_feature_evidence_contract(
        errors,
        manifest_path,
        contract.get("target_feature_evidence"),
        entries,
    )


def validate_manifest(
    root: Path,
    manifest_path: Path,
    build_dir: Path | None = None,
    ctest_config: str | None = None,
) -> tuple[dict[str, Any] | None, list[str]]:
    errors: list[str] = []
    try:
        payload = load_json(manifest_path)
    except ValueError as exc:
        return None, [str(exc)]

    validate_allowed_fields(
        errors, payload, ALLOWED_TOP_LEVEL_FIELDS, str(manifest_path)
    )

    missing_top_level = sorted(REQUIRED_TOP_LEVEL_FIELDS - payload.keys())
    if missing_top_level:
        errors.append(
            f"{manifest_path}: missing required field(s): "
            + ", ".join(missing_top_level)
        )

    schema_version = payload.get("schema_version")
    if schema_version != SCHEMA_VERSION:
        errors.append(
            f"{manifest_path}: schema_version must be {SCHEMA_VERSION!r}, "
            f"got {schema_version!r}"
        )

    for field in ("suite", "description"):
        value = payload.get(field)
        if not isinstance(value, str) or not value:
            errors.append(f"{manifest_path}: {field!r} must be a non-empty string")

    entries = payload.get("entries")
    if not isinstance(entries, list) or not entries:
        errors.append(f"{manifest_path}: entries must be a non-empty array")
        return None, errors

    known_evidence_tests = discover_known_evidence_tests(root)
    if not known_evidence_tests:
        errors.append(f"{manifest_path}: no CTest evidence names discovered")

    ctest_names: set[str] | None = None
    if build_dir is not None:
        try:
            ctest_names = load_ctest_inventory(build_dir, ctest_config)
        except RuntimeError as exc:
            errors.append(str(exc))

    seen_ids: set[str] = set()
    entry_ids: list[str] = []
    for index, entry in enumerate(entries):
        entry_label = f"{manifest_path}: entries[{index}]"
        if not isinstance(entry, dict):
            errors.append(f"{entry_label}: entry must be a JSON object")
            continue

        entry_id = entry.get("id")
        if isinstance(entry_id, str):
            if entry_id in seen_ids:
                errors.append(f"{entry_label}: duplicate id {entry_id!r}")
            seen_ids.add(entry_id)
            entry_ids.append(entry_id)

        errors.extend(
            validate_entry(
                root,
                manifest_path,
                entry,
                index,
                known_evidence_tests,
                ctest_names,
            )
        )

    if entry_ids != sorted(entry_ids):
        errors.append(f"{manifest_path}: entries must be sorted by id")

    validate_coverage_contract(errors, manifest_path, payload, entries)

    if errors:
        return None, errors
    return build_report(root, manifest_path, payload), []


def write_json_report(path: Path, report: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


def write_text_report(path: Path, report: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    summary = report["summary"]
    lines = [
        f"schemaVersion: {report['schemaVersion']}",
        f"suite: {report['suite']}",
        f"manifest: {report['manifestPath']}",
        f"entries: {summary['total']}",
        "status: "
        + ", ".join(f"{name}={count}" for name, count in summary["byStatus"].items()),
        "commandProfiles: "
        + ", ".join(
            f"{name}={count}" for name, count in summary["byCommandProfile"].items()
        ),
        "targetFeatureEvidence: "
        f"entries={summary['targetFeatureEvidence']['entryCount']}, "
        f"tests={summary['targetFeatureEvidence']['testCount']}, "
        "featureGroups="
        + (
            ", ".join(
                f"{name}={count}"
                for name, count in summary["targetFeatureEvidence"][
                    "byFeatureGroup"
                ].items()
            )
            or "none"
        )
        + ", kinds="
        + (
            ", ".join(
                f"{name}={count}"
                for name, count in summary["targetFeatureEvidence"][
                    "byEvidenceKind"
                ].items()
            )
            or "none"
        ),
        "",
    ]
    execution_summary = summary.get("execution")
    if isinstance(execution_summary, dict):
        lines.extend(
            [
                "execution: "
                f"executed={execution_summary['executed']}, "
                f"skipped={execution_summary['skipped']}, "
                f"passed={execution_summary['passed']}, "
                f"failed={execution_summary['failed']}, "
                f"diagnosticMismatches="
                f"{execution_summary.get('diagnosticMismatchCount', 0)}",
                "",
            ]
        )
    for entry in report["entries"]:
        diagnostic = ""
        if "expectedDiagnostic" in entry:
            diagnostic = f" diagnostic={entry['expectedDiagnostic']}"
        target = ""
        if "target" in entry:
            target = f" target={entry['target']}"
        execution = entry.get("execution")
        execution_text = ""
        if isinstance(execution, dict):
            exit_code = execution.get("exitCode")
            execution_text = f" execution={execution.get('status')} exit={exit_code}"
        target_feature_evidence = ""
        if "targetFeatureEvidenceTests" in entry:
            target_feature_evidence = (
                f" targetFeatureEvidence={len(entry['targetFeatureEvidenceTests'])}"
            )
        auxiliary_evidence = ""
        if "auxiliaryEvidenceTests" in entry:
            auxiliary_evidence = (
                f" auxiliaryEvidence={len(entry['auxiliaryEvidenceTests'])}"
            )
        lines.append(
            f"{entry['id']} status={entry['status']} "
            f"profile={entry['commandProfile']}{target}{diagnostic}"
            f"{auxiliary_evidence}{target_feature_evidence}{execution_text}"
        )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_manifest(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def add_fixture_hashes(root: Path, payload: dict[str, Any]) -> None:
    for entry in payload["entries"]:
        fixture = root / str(entry["fixture"])
        entry["fixture_sha256"] = source_file_sha256(fixture)


def set_entry_fixture(root: Path, entry: dict[str, Any], fixture: str) -> None:
    entry["fixture"] = fixture
    entry["fixture_sha256"] = source_file_sha256(root / fixture)


def self_test_manifest(root: Path | None = None) -> dict[str, Any]:
    manifest = {
        "schema_version": SCHEMA_VERSION,
        "suite": "self-test",
        "description": "self-test manifest",
        "coverage_contract": {
            "required_feature_statuses": [
                {
                    "feature_group": feature_group,
                    "status": status,
                    "min_entries": REQUIRED_FEATURE_STATUS_MIN_ENTRIES[
                        (feature_group, status)
                    ],
                }
                for feature_group, status in REQUIRED_FEATURE_STATUS_COVERAGE
            ],
            "target_feature_evidence": {
                "required_kinds": sorted(TARGET_FEATURE_EVIDENCE_KINDS),
            },
        },
        "entries": [
            {
                "id": "atomics.self-test",
                "feature_group": "atomics",
                "language_category": "compute",
                "status": "accepted",
                "command_profile": "hir-dump",
                "fixture": "tests/frontend/fixtures/AtomicSelfTest.cgl",
                "evidence_tests": ["cglc_dump_hir_atomic_self_test"],
                "notes": "accepted atomics fixture",
            },
            {
                "id": "compute-basics.self-test-check",
                "feature_group": "compute-basics",
                "language_category": "compute",
                "status": "accepted",
                "command_profile": "frontend-check",
                "fixture": "tests/frontend/fixtures/CheckSelfTest.cgl",
                "evidence_tests": ["cglc_check_self_test"],
                "target_feature_evidence_tests": [
                    "cglc_dump_debug_self_test_target_capabilities"
                ],
                "notes": "accepted fixture",
            },
            {
                "id": "compute-basics.self-test-hir",
                "feature_group": "compute-basics",
                "language_category": "compute",
                "status": "accepted",
                "command_profile": "hir-dump",
                "fixture": "tests/frontend/fixtures/SelfTest.cgl",
                "evidence_tests": ["cglc_dump_hir_self_test"],
                "notes": "accepted fixture",
            },
            {
                "id": "control-flow.self-test",
                "feature_group": "control-flow",
                "language_category": "statements",
                "status": "accepted",
                "command_profile": "frontend-check",
                "fixture": "tests/frontend/fixtures/ControlFlowSelfTest.cgl",
                "evidence_tests": ["cglc_check_control_flow_self_test"],
                "notes": "accepted control-flow fixture",
            },
            {
                "id": "graphics-stages.self-test",
                "feature_group": "graphics-stages",
                "language_category": "graphics",
                "status": "accepted",
                "command_profile": "hir-dump",
                "fixture": "tests/frontend/fixtures/GraphicsSelfTest.cgl",
                "evidence_tests": ["cglc_dump_hir_graphics_self_test"],
                "notes": "accepted graphics fixture",
            },
            {
                "id": "graphics-stages.self-test-native",
                "feature_group": "graphics-stages",
                "language_category": "graphics",
                "status": "accepted",
                "command_profile": "native-package-build",
                "target": "metal",
                "fixture": "tests/metal/fixtures/NativePackageSelfTest.cgl",
                "evidence_tests": ["cglc_build_metal_self_test_native"],
                "target_feature_evidence_tests": [
                    "cglc_doctor_json_metal_graphics_self_test_native_evidence",
                    "cglc_explain_targets_metal_graphics_self_test_native_evidence",
                ],
                "notes": "accepted native graphics package fixture",
            },
            {
                "id": "native-v0-unsupported.self-test",
                "feature_group": "known-native-v0-unsupported",
                "language_category": "native-v0",
                "status": "unsupported",
                "command_profile": "unsupported-native-v0-check",
                "fixture": "tests/check-failures/BadSelfTest.cgl",
                "expected_diagnostic": "spec.unsupported-for-native-v0",
                "evidence_tests": [
                    "cglc_check_unsupported_native_v0_self_test_failure"
                ],
                "notes": "unsupported fixture",
            },
            {
                "id": "native-v0-unsupported.targeted-diagnostic-self-test",
                "feature_group": "known-native-v0-unsupported",
                "language_category": "native-v0",
                "status": "unsupported",
                "command_profile": "unsupported-native-v0-check",
                "fixture": "tests/check-failures/BadTargetedSelfTest.cgl",
                "expected_diagnostic": "parse.unsupported-var-address-space",
                "evidence_tests": [
                    "cglc_check_unsupported_native_v0_targeted_self_test_failure"
                ],
                "notes": "targeted unsupported fixture",
            },
            {
                "id": "resources.self-test-source-package",
                "feature_group": "resources",
                "language_category": "resource-declarations",
                "status": "accepted",
                "command_profile": "source-package-build",
                "target": "opengl",
                "fixture": "tests/opengl/fixtures/SourcePackageSelfTest.cgl",
                "evidence_tests": ["cglc_build_opengl_self_test_source_package"],
                "auxiliary_evidence_tests": [
                    "cglc_dump_backend_opengl_self_test",
                    "cglc_package_verify_json_schema_opengl_self_test_source_package",
                ],
                "notes": "accepted package fixture",
            },
            {
                "id": "storage-images.self-test",
                "feature_group": "storage-images",
                "language_category": "image-operations",
                "status": "accepted",
                "command_profile": "frontend-check",
                "fixture": "tests/frontend/fixtures/StorageImageSelfTest.cgl",
                "evidence_tests": ["cglc_check_storage_image_self_test"],
                "notes": "accepted storage-image fixture",
            },
            {
                "id": "texture-sampling.self-test-target-rejection",
                "feature_group": "texture-sampling",
                "language_category": "texture-operations",
                "status": "accepted",
                "command_profile": "frontend-check",
                "fixture": "tests/frontend/fixtures/TextureSelfTest.cgl",
                "evidence_tests": ["cglc_check_texture_self_test"],
                "target_feature_evidence_tests": [
                    "cglc_build_opengl_self_test_planned_failure"
                ],
                "notes": "accepted texture fixture with planned target rejection evidence",
            },
        ],
    }
    base_entries_by_key = {
        (entry["feature_group"], entry["status"]): entry
        for entry in manifest["entries"]
    }
    counts: dict[tuple[str, str], int] = {}
    for entry in manifest["entries"]:
        key = (entry["feature_group"], entry["status"])
        counts[key] = counts.get(key, 0) + 1
    for key, required_count in REQUIRED_FEATURE_STATUS_MIN_ENTRIES.items():
        base_entry = base_entries_by_key[key]
        while counts.get(key, 0) < required_count:
            clone = dict(base_entry)
            for optional_field in OPTIONAL_ENTRY_EVIDENCE_FIELDS:
                clone.pop(optional_field, None)
            id_prefix = (
                UNSUPPORTED_ENTRY_ID_PREFIX.rstrip(".")
                if key == ("known-native-v0-unsupported", "unsupported")
                else base_entry["feature_group"]
            )
            clone["id"] = f"{id_prefix}.floor-self-test-{counts.get(key, 0) + 1:02d}"
            clone["notes"] = "synthetic self-test entry for coverage floor validation"
            manifest["entries"].append(clone)
            counts[key] = counts.get(key, 0) + 1
    manifest["entries"].sort(key=lambda entry: entry["id"])
    if root is not None:
        add_fixture_hashes(root, manifest)
    return manifest


def require_self_test_error(errors: list[str], fragment: str) -> None:
    if not any(fragment in error for error in errors):
        raise AssertionError(f"expected error containing {fragment!r}, got {errors!r}")


def self_test_entry(payload: dict[str, Any], entry_id: str) -> dict[str, Any]:
    for entry in payload["entries"]:
        if entry["id"] == entry_id:
            return entry
    raise AssertionError(f"missing self-test entry {entry_id!r}")


def write_fake_cglc(root: Path) -> Path:
    script = root / "fake_cglc.py"
    script.write_text(
        "\n".join(
            [
                "import json",
                "import sys",
                "from pathlib import Path",
                "",
                "args = sys.argv[1:]",
                "if any('FailSelfTest.cgl' in arg for arg in args):",
                "    print('intentional self-test failure', file=sys.stderr)",
                "    raise SystemExit(7)",
                "",
                "if args and args[0] == 'check':",
                "    if '--diagnostics-json' in args:",
                "        code = 'spec.unsupported-for-native-v0'",
                "        if any('BadTargetedSelfTest.cgl' in arg for arg in args):",
                "            code = 'parse.unsupported-var-address-space'",
                "        print(json.dumps({",
                "            'diagnostics': [{",
                "                'code': code,",
                "                'severity': 'error',",
                "            }]",
                "        }, sort_keys=True))",
                "        raise SystemExit(1)",
                "    raise SystemExit(0)",
                "",
                "if args and args[0] == 'dump-ir':",
                "    print('fake hir')",
                "    raise SystemExit(0)",
                "",
                "if args and args[0] == 'build':",
                "    if any('NoWritePackageSelfTest.cgl' in arg for arg in args):",
                "        raise SystemExit(0)",
                "    output = Path(args[args.index('--output') + 1])",
                "    output.parent.mkdir(parents=True, exist_ok=True)",
                "    output.write_text('fake package\\n', encoding='utf-8')",
                "    raise SystemExit(0)",
                "",
                "raise SystemExit(2)",
                "",
            ]
        ),
        encoding="utf-8",
    )

    if os.name == "nt":
        wrapper = root / "fake-cglc.cmd"
        wrapper.write_text(
            f'@echo off\r\n"{sys.executable}" "{script}" %*\r\n',
            encoding="utf-8",
        )
        return wrapper

    wrapper = root / "fake-cglc"
    wrapper.write_text(
        f'#!/bin/sh\nexec "{sys.executable}" "{script}" "$@"\n',
        encoding="utf-8",
    )
    wrapper.chmod(0o755)
    return wrapper


def run_self_test() -> int:
    with tempfile.TemporaryDirectory(prefix="crossgl-conformance-self-test-") as temp:
        root = Path(temp)
        (root / "tests" / "frontend" / "fixtures").mkdir(parents=True)
        (root / "tests" / "check-failures").mkdir(parents=True)
        (root / "tests" / "metal" / "fixtures").mkdir(parents=True)
        (root / "tests" / "opengl" / "fixtures").mkdir(parents=True)
        (root / "tests" / "cmake").mkdir(parents=True)
        (root / "tests" / "frontend" / "fixtures" / "AtomicSelfTest.cgl").write_text(
            "shader AtomicSelfTest { compute { void main() {} } }\n",
            encoding="utf-8",
        )
        (root / "tests" / "frontend" / "fixtures" / "CheckSelfTest.cgl").write_text(
            "shader CheckSelfTest { compute { void main() {} } }\n",
            encoding="utf-8",
        )
        (root / "tests" / "frontend" / "fixtures" / "SelfTest.cgl").write_text(
            "shader SelfTest { compute { void main() {} } }\n",
            encoding="utf-8",
        )
        (
            root / "tests" / "frontend" / "fixtures" / "ControlFlowSelfTest.cgl"
        ).write_text(
            "shader ControlFlowSelfTest { compute { void main() {} } }\n",
            encoding="utf-8",
        )
        (root / "tests" / "frontend" / "fixtures" / "GraphicsSelfTest.cgl").write_text(
            "shader GraphicsSelfTest { vertex { void main() {} } }\n",
            encoding="utf-8",
        )
        (
            root / "tests" / "metal" / "fixtures" / "NativePackageSelfTest.cgl"
        ).write_text(
            "shader NativePackageSelfTest { vertex { void main() {} } }\n",
            encoding="utf-8",
        )
        (root / "tests" / "frontend" / "fixtures" / "FailSelfTest.cgl").write_text(
            "shader FailSelfTest { compute { void main() {} } }\n",
            encoding="utf-8",
        )
        (root / "tests" / "check-failures" / "BadSelfTest.cgl").write_text(
            "fn main() {}\n",
            encoding="utf-8",
        )
        (root / "tests" / "check-failures" / "BadTargetedSelfTest.cgl").write_text(
            "shader BadTargetedSelfTest { compute { var<storage> x: int; } }\n",
            encoding="utf-8",
        )
        (
            root / "tests" / "opengl" / "fixtures" / "SourcePackageSelfTest.cgl"
        ).write_text(
            "shader SourcePackageSelfTest { vertex { void main() {} } }\n",
            encoding="utf-8",
        )
        (
            root / "tests" / "opengl" / "fixtures" / "NoWritePackageSelfTest.cgl"
        ).write_text(
            "shader NoWritePackageSelfTest { vertex { void main() {} } }\n",
            encoding="utf-8",
        )
        (
            root / "tests" / "frontend" / "fixtures" / "StorageImageSelfTest.cgl"
        ).write_text(
            "shader StorageImageSelfTest { compute { void main() {} } }\n",
            encoding="utf-8",
        )
        (root / "tests" / "frontend" / "fixtures" / "TextureSelfTest.cgl").write_text(
            "shader TextureSelfTest { compute { void main() {} } }\n",
            encoding="utf-8",
        )
        (root / "tests" / "cmake" / "SelfTest.cmake").write_text(
            "add_test(NAME cglc_dump_hir_atomic_self_test COMMAND cglc --version)\n"
            "add_test(NAME cglc_check_self_test COMMAND cglc --version)\n"
            "add_test(NAME cglc_dump_debug_self_test_target_capabilities "
            "COMMAND cglc --version)\n"
            "add_test(NAME cglc_dump_hir_self_test COMMAND cglc --version)\n"
            "add_test(NAME cglc_check_control_flow_self_test COMMAND cglc --version)\n"
            "add_test(NAME cglc_dump_hir_graphics_self_test COMMAND cglc --version)\n"
            "add_test(NAME cglc_build_metal_self_test_native COMMAND cglc --version)\n"
            "add_test(NAME cglc_dump_backend_metal_self_test COMMAND cglc --version)\n"
            "add_test(NAME cglc_doctor_json_metal_graphics_self_test_native_evidence "
            "COMMAND cglc --version)\n"
            "add_test(NAME cglc_explain_targets_metal_graphics_self_test_native_evidence "
            "COMMAND cglc --version)\n"
            "add_test(NAME cglc_build_opengl_self_test_source_package COMMAND cglc --version)\n"
            "add_test(NAME cglc_dump_backend_opengl_self_test COMMAND cglc --version)\n"
            "add_test(NAME cglc_package_verify_json_schema_opengl_self_test_source_package "
            "COMMAND cglc --version)\n"
            "add_test(NAME cglc_build_opengl_self_test_native_package COMMAND cglc --version)\n"
            "add_test(NAME cglc_check_storage_image_self_test COMMAND cglc --version)\n"
            "add_test(NAME cglc_check_texture_self_test COMMAND cglc --version)\n"
            "add_test(NAME cglc_build_opengl_self_test_planned_failure COMMAND cglc --version)\n"
            "cglc_check_unsupported_native_v0_self_test_failure\n"
            "cglc_check_unsupported_native_v0_targeted_self_test_failure\n",
            encoding="utf-8",
        )

        manifest_path = root / DEFAULT_MANIFEST
        manifest_path.parent.mkdir(parents=True)
        payload = self_test_manifest(root)
        write_manifest(manifest_path, payload)
        report, errors = validate_manifest(root, manifest_path)
        if errors or report is None:
            raise AssertionError(f"expected valid self-test manifest, got {errors!r}")
        expected_by_status: dict[str, int] = {}
        for (_, status), minimum in REQUIRED_FEATURE_STATUS_MIN_ENTRIES.items():
            expected_by_status[status] = expected_by_status.get(status, 0) + minimum
        expected_total = sum(expected_by_status.values())
        if report["summary"]["byStatus"] != expected_by_status:
            raise AssertionError(f"unexpected self-test report: {report!r}")
        if report["summary"]["targetFeatureEvidence"] != {
            "entryCount": 3,
            "testCount": 4,
            "byFeatureGroup": {
                "compute-basics": 1,
                "graphics-stages": 1,
                "texture-sampling": 1,
            },
            "byEvidenceKind": {
                "planned-unsupported": 1,
                "target-metadata": 1,
                "target-package-explanation": 2,
            },
        }:
            raise AssertionError(
                f"unexpected target feature evidence summary: {report!r}"
            )

        native_entry = self_test_entry(payload, "graphics-stages.self-test-native")
        known_evidence_tests = discover_known_evidence_tests(root)
        optional_native_unavailable_ctest_names = {
            "cglc_build_metal_native_tools_unavailable",
            "cglc_doctor_json_metal_graphics_self_test_native_evidence",
            "cglc_explain_targets_metal_graphics_self_test_native_evidence",
        }
        optional_native_errors = validate_entry(
            root,
            manifest_path,
            native_entry,
            0,
            known_evidence_tests,
            optional_native_unavailable_ctest_names,
        )
        if optional_native_errors:
            raise AssertionError(
                "expected optional native evidence to be allowed when the "
                f"target unavailable sentinel is registered: {optional_native_errors!r}"
            )
        missing_native_errors = validate_entry(
            root,
            manifest_path,
            native_entry,
            0,
            known_evidence_tests,
            optional_native_unavailable_ctest_names
            - {"cglc_build_metal_native_tools_unavailable"},
        )
        require_self_test_error(
            missing_native_errors,
            "CTest inventory is missing evidence test "
            "'cglc_build_metal_self_test_native'",
        )
        native_auxiliary_entry = dict(native_entry)
        native_auxiliary_entry["auxiliary_evidence_tests"] = [
            "cglc_dump_backend_metal_self_test"
        ]
        native_auxiliary_errors = validate_entry(
            root,
            manifest_path,
            native_auxiliary_entry,
            0,
            known_evidence_tests,
            optional_native_unavailable_ctest_names
            | {"cglc_dump_backend_metal_self_test"},
        )
        if native_auxiliary_errors:
            raise AssertionError(
                "expected auxiliary evidence to be allowed when its CTest is "
                f"registered: {native_auxiliary_errors!r}"
            )
        missing_auxiliary_errors = validate_entry(
            root,
            manifest_path,
            native_auxiliary_entry,
            0,
            known_evidence_tests,
            optional_native_unavailable_ctest_names,
        )
        require_self_test_error(
            missing_auxiliary_errors,
            "CTest inventory is missing auxiliary_evidence_tests entry "
            "'cglc_dump_backend_metal_self_test'",
        )
        native_build_as_auxiliary_entry = dict(native_entry)
        native_build_as_auxiliary_entry["auxiliary_evidence_tests"] = [
            "cglc_build_metal_self_test_native"
        ]
        native_build_as_auxiliary_errors = validate_entry(
            root,
            manifest_path,
            native_build_as_auxiliary_entry,
            0,
            known_evidence_tests,
            optional_native_unavailable_ctest_names,
        )
        require_self_test_error(
            native_build_as_auxiliary_errors,
            "CTest inventory is missing auxiliary_evidence_tests entry "
            "'cglc_build_metal_self_test_native'",
        )
        require_self_test_error(
            native_build_as_auxiliary_errors,
            "auxiliary_evidence_tests entry 'cglc_build_metal_self_test_native' "
            "must be a backend-dump",
        )
        if not ctest_inventory_allows_missing_optional_native_evidence(
            "native-package-build",
            "vulkan",
            "cglc_build_vulkan_self_test_native",
            {"cglc_build_vulkan_native_tools_unavailable"},
        ):
            raise AssertionError(
                "expected Vulkan native evidence to be optional when the "
                "native-tools-unavailable sentinel is registered"
            )
        if ctest_inventory_allows_missing_optional_native_evidence(
            "source-package-build",
            "vulkan",
            "cglc_build_vulkan_self_test_native",
            {"cglc_build_vulkan_native_tools_unavailable"},
        ):
            raise AssertionError(
                "source-package evidence must not be treated as optional native"
            )

        cglc = write_fake_cglc(root)
        report = add_execution_results(
            root,
            report,
            cglc,
            root / "execution-work",
            DEFAULT_EXECUTION_TIMEOUT_SECONDS,
        )
        execution = report["summary"]["execution"]
        if (
            execution["entryCount"] != expected_total
            or execution["executed"] != expected_total
        ):
            raise AssertionError(f"unexpected self-test execution summary: {report!r}")
        if execution["failed"] != 0 or execution["passed"] != expected_total:
            raise AssertionError(f"expected self-test execution to pass: {report!r}")
        if execution["diagnosticMismatchCount"] != 0:
            raise AssertionError(f"unexpected diagnostic mismatch: {report!r}")
        unsupported_execution = next(
            entry
            for entry in report["entries"]
            if entry["id"] == "native-v0-unsupported.self-test"
        )["execution"]
        if unsupported_execution.get("exitCode") != 1:
            raise AssertionError(
                "expected unsupported diagnostics execution to record exit 1"
            )

        failing_payload = self_test_manifest(root)
        set_entry_fixture(
            root,
            self_test_entry(failing_payload, "compute-basics.self-test-check"),
            "tests/frontend/fixtures/FailSelfTest.cgl",
        )
        write_manifest(manifest_path, failing_payload)
        failing_report, errors = validate_manifest(root, manifest_path)
        if errors or failing_report is None:
            raise AssertionError(f"expected valid failing manifest, got {errors!r}")
        failing_report = add_execution_results(
            root,
            failing_report,
            cglc,
            root / "execution-failure-work",
            DEFAULT_EXECUTION_TIMEOUT_SECONDS,
        )
        failing_execution = failing_report["summary"]["execution"]
        if failing_execution["failed"] != 1:
            raise AssertionError(f"expected one execution failure: {failing_report!r}")
        if failing_execution["failures"][0]["id"] != "compute-basics.self-test-check":
            raise AssertionError(f"unexpected execution failure: {failing_report!r}")

        diagnostic_mismatch_payload = self_test_manifest(root)
        self_test_entry(diagnostic_mismatch_payload, "native-v0-unsupported.self-test")[
            "expected_diagnostic"
        ] = "parse.unsupported-var-address-space"
        write_manifest(manifest_path, diagnostic_mismatch_payload)
        diagnostic_mismatch_report, errors = validate_manifest(root, manifest_path)
        if errors or diagnostic_mismatch_report is None:
            raise AssertionError(
                f"expected valid diagnostic mismatch manifest, got {errors!r}"
            )
        diagnostic_mismatch_report = add_execution_results(
            root,
            diagnostic_mismatch_report,
            cglc,
            root / "execution-diagnostic-mismatch-work",
            DEFAULT_EXECUTION_TIMEOUT_SECONDS,
        )
        diagnostic_mismatch_execution = diagnostic_mismatch_report["summary"][
            "execution"
        ]
        if (
            diagnostic_mismatch_execution["failed"] != 1
            or diagnostic_mismatch_execution["diagnosticMismatchCount"] != 1
        ):
            raise AssertionError(
                "expected one execution failure and diagnostic mismatch: "
                f"{diagnostic_mismatch_report!r}"
            )
        if (
            diagnostic_mismatch_execution["failures"][0]["id"]
            != "native-v0-unsupported.self-test"
        ):
            raise AssertionError(
                f"unexpected diagnostic mismatch failure: {diagnostic_mismatch_report!r}"
            )

        stale_payload = self_test_manifest(root)
        stale_entry = self_test_entry(
            stale_payload, "resources.self-test-source-package"
        )
        set_entry_fixture(
            root,
            stale_entry,
            "tests/opengl/fixtures/NoWritePackageSelfTest.cgl",
        )
        stale_work_dir = root / "execution-stale-work"
        stale_output = output_path_for_entry(stale_work_dir, stale_entry)
        stale_output.mkdir(parents=True)
        (stale_output / "old-package.txt").write_text(
            "stale package\n", encoding="utf-8"
        )
        write_manifest(manifest_path, stale_payload)
        stale_report, errors = validate_manifest(root, manifest_path)
        if errors or stale_report is None:
            raise AssertionError(f"expected valid stale manifest, got {errors!r}")
        stale_report = add_execution_results(
            root,
            stale_report,
            cglc,
            stale_work_dir,
            DEFAULT_EXECUTION_TIMEOUT_SECONDS,
        )
        stale_execution = stale_report["summary"]["execution"]
        if stale_execution["failed"] != 1:
            raise AssertionError(
                f"expected stale package execution failure: {stale_report!r}"
            )
        package_execution = next(
            entry
            for entry in stale_report["entries"]
            if entry["id"] == "resources.self-test-source-package"
        )["execution"]
        if (
            package_execution.get("failure")
            != "expected build artifact was not created"
        ):
            raise AssertionError(
                f"unexpected stale package execution failure: {stale_report!r}"
            )
        if package_execution.get("artifactPreExisting") is not True:
            raise AssertionError(
                f"expected stale package artifact to be detected: {stale_report!r}"
            )
        if package_execution.get("artifactExists") is not False:
            raise AssertionError(
                f"expected stale package artifact to be removed: {stale_report!r}"
            )

        payload = self_test_manifest(root)
        self_test_entry(payload, "compute-basics.self-test-check")["fixture_sha256"] = (
            "0" * 64
        )
        write_manifest(manifest_path, payload)
        _, errors = validate_manifest(root, manifest_path)
        require_self_test_error(errors, "fixture_sha256 mismatch")

        payload = self_test_manifest(root)
        self_test_entry(payload, "compute-basics.self-test-check")[
            "command_profile"
        ] = "unknown-profile"
        write_manifest(manifest_path, payload)
        _, errors = validate_manifest(root, manifest_path)
        require_self_test_error(errors, "unsupported command_profile")

        payload = self_test_manifest(root)
        self_test_entry(payload, "compute-basics.self-test-check")["owner"] = "v0"
        write_manifest(manifest_path, payload)
        _, errors = validate_manifest(root, manifest_path)
        require_self_test_error(errors, "unsupported field(s): owner")

        payload = self_test_manifest(root)
        self_test_entry(payload, "resources.self-test-source-package")[
            "language_category"
        ] = "compute"
        write_manifest(manifest_path, payload)
        _, errors = validate_manifest(root, manifest_path)
        require_self_test_error(errors, "language_category 'compute' is not valid")

        payload = self_test_manifest(root)
        self_test_entry(payload, "resources.self-test-source-package")[
            "evidence_tests"
        ] = ["cglc_check_self_test"]
        write_manifest(manifest_path, payload)
        _, errors = validate_manifest(root, manifest_path)
        require_self_test_error(
            errors, "source-package-build evidence_tests must include"
        )

        payload = self_test_manifest(root)
        self_test_entry(payload, "resources.self-test-source-package")[
            "evidence_tests"
        ] = ["cglc_build_opengl_self_test_native_package"]
        write_manifest(manifest_path, payload)
        _, errors = validate_manifest(root, manifest_path)
        require_self_test_error(
            errors,
            "source-package-build package evidence must be a source package test",
        )

        payload = self_test_manifest(root)
        self_test_entry(payload, "native-v0-unsupported.self-test").pop(
            "expected_diagnostic"
        )
        write_manifest(manifest_path, payload)
        _, errors = validate_manifest(root, manifest_path)
        require_self_test_error(errors, "expected_diagnostic")

        payload = self_test_manifest(root)
        self_test_entry(payload, "compute-basics.self-test-check")["evidence_tests"] = [
            "cglc_missing_self_test"
        ]
        write_manifest(manifest_path, payload)
        _, errors = validate_manifest(root, manifest_path)
        require_self_test_error(errors, "unknown evidence test")

        payload = self_test_manifest(root)
        self_test_entry(payload, "compute-basics.self-test-check")[
            "target_feature_evidence_tests"
        ] = ["cglc_missing_target_feature_self_test"]
        write_manifest(manifest_path, payload)
        _, errors = validate_manifest(root, manifest_path)
        require_self_test_error(errors, "unknown target_feature_evidence_tests entry")

        payload = self_test_manifest(root)
        self_test_entry(payload, "compute-basics.self-test-check")[
            "auxiliary_evidence_tests"
        ] = ["cglc_missing_auxiliary_self_test"]
        write_manifest(manifest_path, payload)
        _, errors = validate_manifest(root, manifest_path)
        require_self_test_error(errors, "unknown auxiliary_evidence_tests entry")

        payload = self_test_manifest(root)
        payload["coverage_contract"]["required_feature_statuses"] = [
            requirement
            for requirement in payload["coverage_contract"]["required_feature_statuses"]
            if requirement["feature_group"] != "atomics"
        ]
        write_manifest(manifest_path, payload)
        _, errors = validate_manifest(root, manifest_path)
        require_self_test_error(errors, "must cover exactly these feature/status pairs")

        payload = self_test_manifest(root)
        payload["coverage_contract"]["target_feature_evidence"]["required_kinds"] = [
            "planned-unsupported"
        ]
        write_manifest(manifest_path, payload)
        _, errors = validate_manifest(root, manifest_path)
        require_self_test_error(
            errors,
            "required_kinds must cover exactly these target feature evidence kinds",
        )

        payload = self_test_manifest(root)
        for requirement in payload["coverage_contract"]["required_feature_statuses"]:
            if requirement["feature_group"] == "atomics":
                requirement["min_entries"] = 1
        write_manifest(manifest_path, payload)
        _, errors = validate_manifest(root, manifest_path)
        atomics_floor = REQUIRED_FEATURE_STATUS_MIN_ENTRIES[("atomics", "accepted")]
        require_self_test_error(errors, f"must be at least {atomics_floor}, got 1")

        payload = self_test_manifest(root)
        self_test_entry(payload, "texture-sampling.self-test-target-rejection")[
            "target_feature_evidence_tests"
        ] = ["cglc_check_texture_self_test"]
        write_manifest(manifest_path, payload)
        _, errors = validate_manifest(root, manifest_path)
        require_self_test_error(
            errors, "target_feature_evidence_tests must not duplicate evidence_tests"
        )
        require_self_test_error(
            errors,
            "must be a planned-unsupported, target-metadata, or "
            "target-package-explanation evidence test",
        )

        payload = self_test_manifest(root)
        self_test_entry(payload, "texture-sampling.self-test-target-rejection")[
            "target_feature_evidence_tests"
        ] = ["cglc_build_self_test_planned_failure"]
        write_manifest(manifest_path, payload)
        _, errors = validate_manifest(root, manifest_path)
        require_self_test_error(
            errors, "planned unsupported target evidence must carry one target token"
        )

        payload = self_test_manifest(root)
        self_test_entry(payload, "native-v0-unsupported.self-test")[
            "evidence_tests"
        ] = ["cglc_check_self_test"]
        write_manifest(manifest_path, payload)
        _, errors = validate_manifest(root, manifest_path)
        require_self_test_error(errors, "unsupported evidence test must match")

        payload = self_test_manifest(root)
        accepted_unsupported_bucket_entry = {
            "id": "native-v0-unsupported.accepted-self-test",
            "feature_group": "known-native-v0-unsupported",
            "language_category": "native-v0",
            "status": "accepted",
            "command_profile": "frontend-check",
            "fixture": "tests/frontend/fixtures/CheckSelfTest.cgl",
            "fixture_sha256": source_file_sha256(
                root / "tests/frontend/fixtures/CheckSelfTest.cgl"
            ),
            "evidence_tests": ["cglc_check_self_test"],
            "notes": "accepted fixture in the unsupported bucket must be rejected",
        }
        payload["entries"].append(accepted_unsupported_bucket_entry)
        payload["entries"].sort(key=lambda entry: entry["id"])
        write_manifest(manifest_path, payload)
        _, errors = validate_manifest(root, manifest_path)
        require_self_test_error(
            errors,
            "accepted entries must not use feature_group 'known-native-v0-unsupported'",
        )

    print("v0 conformance manifest self-test: OK")
    return 0


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--root",
        type=Path,
        default=Path.cwd(),
        help="Repository root. Defaults to the current working directory.",
    )
    parser.add_argument(
        "--manifest",
        type=Path,
        default=DEFAULT_MANIFEST,
        help=f"Manifest path relative to --root. Defaults to {DEFAULT_MANIFEST}.",
    )
    parser.add_argument(
        "--build-dir",
        type=Path,
        help="Optional configured CMake build directory for CTest inventory checks.",
    )
    parser.add_argument(
        "--ctest-config",
        help="CTest configuration to use for multi-config generators.",
    )
    parser.add_argument(
        "--cglc",
        type=Path,
        help=(
            "Optional built cglc executable path. Requires --work-dir and enables "
            "manifest entry execution."
        ),
    )
    parser.add_argument(
        "--work-dir",
        type=Path,
        help="Work directory for execution artifacts. Requires --cglc.",
    )
    parser.add_argument(
        "--execution-timeout-seconds",
        type=float,
        default=DEFAULT_EXECUTION_TIMEOUT_SECONDS,
        help=(
            "Per-entry execution timeout in seconds. Defaults to "
            f"{DEFAULT_EXECUTION_TIMEOUT_SECONDS:g}."
        ),
    )
    parser.add_argument(
        "--skip-native-package-builds",
        action="store_true",
        help=(
            "Skip native-package-build entries during execution. This keeps "
            "manifest execution stable on hosts without optional native tools."
        ),
    )
    parser.add_argument(
        "--report-json",
        type=Path,
        help="Optional path for a deterministic JSON conformance report.",
    )
    parser.add_argument(
        "--report-text",
        type=Path,
        help="Optional path for a deterministic text conformance report.",
    )
    parser.add_argument(
        "--self-test",
        action="store_true",
        help="Run checker self-tests instead of validating the repository manifest.",
    )
    return parser.parse_args(argv)


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    if args.self_test:
        try:
            return run_self_test()
        except AssertionError as exc:
            print(f"v0 conformance manifest self-test failed: {exc}", file=sys.stderr)
            return 1

    root = args.root.resolve()
    manifest_path = args.manifest
    if not manifest_path.is_absolute():
        manifest_path = root / manifest_path

    if (args.cglc is None) != (args.work_dir is None):
        print("--cglc and --work-dir must be provided together", file=sys.stderr)
        return 2
    if args.execution_timeout_seconds <= 0:
        print("--execution-timeout-seconds must be positive", file=sys.stderr)
        return 2

    build_dir = args.build_dir.resolve() if args.build_dir else None
    report, errors = validate_manifest(
        root,
        manifest_path,
        build_dir,
        args.ctest_config or None,
    )
    if errors or report is None:
        print("v0 conformance manifest check failed:", file=sys.stderr)
        for error in errors:
            print(f"- {error}", file=sys.stderr)
        return 1

    execution_failed = 0
    if args.cglc is not None and args.work_dir is not None:
        cglc = args.cglc.resolve()
        if not cglc.is_file():
            print(f"--cglc does not exist or is not a file: {cglc}", file=sys.stderr)
            return 2
        report = add_execution_results(
            root,
            report,
            cglc,
            args.work_dir.resolve(),
            args.execution_timeout_seconds,
            args.skip_native_package_builds,
        )
        execution_failed = report["summary"]["execution"]["failed"]

    if args.report_json:
        write_json_report(args.report_json, report)
    if args.report_text:
        write_text_report(args.report_text, report)

    summary = report["summary"]
    status_counts = ", ".join(
        f"{name}={count}" for name, count in summary["byStatus"].items()
    )
    profile_counts = ", ".join(
        f"{name}={count}" for name, count in summary["byCommandProfile"].items()
    )
    print(
        f"validated {summary['total']} v0 conformance manifest entries "
        f"({status_counts}; {profile_counts})"
    )
    target_feature_evidence = summary["targetFeatureEvidence"]
    print(
        "target feature evidence "
        f"entries={target_feature_evidence['entryCount']}, "
        f"tests={target_feature_evidence['testCount']}, "
        "kinds="
        + ", ".join(
            f"{name}={count}"
            for name, count in target_feature_evidence["byEvidenceKind"].items()
        )
    )
    if "execution" in summary:
        execution = summary["execution"]
        print(
            "executed "
            f"{execution['executed']} entries, skipped {execution['skipped']}, "
            f"failed {execution['failed']}, diagnostic mismatches "
            f"{execution.get('diagnosticMismatchCount', 0)}"
        )
    if execution_failed:
        print("v0 conformance manifest execution failed:", file=sys.stderr)
        for failure in summary["execution"]["failures"]:
            print(
                f"- {failure['id']}: {failure['failure']}",
                file=sys.stderr,
            )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
