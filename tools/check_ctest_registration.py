#!/usr/bin/env python3
"""Validate CrossGL CTest registration metadata.

The checker intentionally uses CTest's generated JSON inventory instead of
re-parsing every CMake helper. That keeps the guard focused on what CTest will
actually run after configuration.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from itertools import combinations
from pathlib import Path
from typing import Any


OPTIONAL_NATIVE_TARGETS = ("vulkan", "metal", "directx", "opengl")
OPTIONAL_NATIVE_AVAILABILITY_LABELS = (
    "native-tool-available",
    "native-tool-unavailable",
)
OPTIONAL_NATIVE_STATE_LABELS = (
    *OPTIONAL_NATIVE_AVAILABILITY_LABELS,
    "native-tool-policy",
)
KNOWN_FIXTURE_FAMILIES = (
    "tests/fixtures",
    "tests/frontend/fixtures",
    "tests/directx/fixtures",
    "tests/metal/fixtures",
    "tests/optimizer/fixtures",
    "tests/opengl/fixtures",
    "tests/vulkan/fixtures",
    "tests/check-failures",
)
COMMON_CTEST_CONFIGS = ("Release", "Debug", "RelWithDebInfo", "MinSizeRel")
FIXTURE_FAMILY_CONTEXTS: dict[str, tuple[str, tuple[str, ...]]] = {
    "tests/check-failures": (
        "diagnostics/check-failure lane",
        ("tests/cmake/CrossGLCheckTests.cmake",),
    ),
    "tests/directx/fixtures": (
        "directx backend fixture lane",
        ("tests/cmake/CrossGLSourcePackageBuildTests.cmake",),
    ),
    "tests/fixtures": (
        "core shared fixture lane",
        (
            "tests/cmake/CrossGLCheckTests.cmake",
            "tests/cmake/CrossGLSourcePackageBuildTests.cmake",
        ),
    ),
    "tests/frontend/fixtures": (
        "frontend/HIR fixture lane",
        ("tests/cmake/CrossGLCheckTests.cmake",),
    ),
    "tests/metal/fixtures": (
        "metal backend fixture lane",
        (
            "tests/cmake/CrossGLSourcePackageBuildTests.cmake",
            "tests/cmake/CrossGLMetalNativeBuildTests.cmake",
        ),
    ),
    "tests/optimizer/fixtures": (
        "optimizer fixture lane",
        ("tests/cmake/CrossGLOptimizerTests.cmake",),
    ),
    "tests/opengl/fixtures": (
        "opengl backend fixture lane",
        ("tests/cmake/CrossGLSourcePackageBuildTests.cmake",),
    ),
    "tests/vulkan/fixtures": (
        "vulkan backend fixture lane",
        (
            "tests/cmake/CrossGLSourcePackageBuildTests.cmake",
            "tests/cmake/CrossGLVulkanNativeBuildTests.cmake",
        ),
    ),
}
TARGET_CONTEXTS: dict[str, tuple[str, tuple[str, ...]]] = {
    "directx": (
        "directx backend lane",
        ("tests/cmake/CrossGLSourcePackageBuildTests.cmake",),
    ),
    "metal": (
        "metal backend lane",
        (
            "tests/cmake/CrossGLSourcePackageBuildTests.cmake",
            "tests/cmake/CrossGLMetalNativeBuildTests.cmake",
        ),
    ),
    "opengl": (
        "opengl backend lane",
        ("tests/cmake/CrossGLSourcePackageBuildTests.cmake",),
    ),
    "vulkan": (
        "vulkan backend lane",
        (
            "tests/cmake/CrossGLSourcePackageBuildTests.cmake",
            "tests/cmake/CrossGLVulkanNativeBuildTests.cmake",
        ),
    ),
}
OPTIONAL_NATIVE_HELPER = "tests/cmake/CrossGLOptionalNativeTools.cmake"
FIXTURE_VARIABLE_FILE = "tests/cmake/CrossGLTestFixtures.cmake"
LANGUAGE_CONTRACT_MANIFEST = "tools/cross_repo_language_contract.json"
INTENTIONAL_FAILURE_SUFFIXES = (
    "_planned_failure",
    "_unsupported_failure",
    "_target_failure",
    "_tool_failure",
    "_unavailable",
)
REQUIRED_CTEST_REGISTRATIONS: tuple[tuple[str, tuple[str, ...]], ...] = ()
PACKAGE_SMOKE_REGISTRATIONS = (
    (
        "cglc_install_layout_smoke",
        "native install layout smoke lane",
        "cmake/CrossGLInstallSmoke.cmake",
        (
            "BUILD_DIR",
            "SOURCE_DIR",
            "INSTALL_PREFIX",
            "CMAKE_CONFIGURATION_TYPES",
            "CMAKE_BUILD_TYPE",
            "CROSSGL_SMOKE_PARALLEL_LEVEL",
        ),
        ("readiness", "native-install-smoke", "package-layout-smoke"),
    ),
    (
        "cglc_cpack_layout_smoke",
        "native package layout smoke lane",
        "cmake/CrossGLCPackSmoke.cmake",
        (
            "BUILD_DIR",
            "SOURCE_DIR",
            "CPACK_CONFIG",
            "CPACK_COMMAND",
            "CMAKE_CONFIGURATION_TYPES",
            "CMAKE_BUILD_TYPE",
            "CROSSGL_SMOKE_PARALLEL_LEVEL",
        ),
        ("readiness", "native-package-smoke", "package-layout-smoke"),
    ),
)
MUTABLE_OUTPUT_DEFINITIONS = ("OUTPUT",)


def run(
    command: list[str], cwd: Path | None = None
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        cwd=cwd,
        check=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )


def load_ctest_inventory(
    build_dir: Path, ctest_config: str | None = None
) -> dict[str, Any]:
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
    return json.loads(result.stdout)


def property_map(test: dict[str, Any]) -> dict[str, Any]:
    return {item["name"]: item.get("value") for item in test.get("properties", [])}


def labels_for(test: dict[str, Any]) -> set[str]:
    labels = property_map(test).get("LABELS", [])
    if isinstance(labels, str):
        return {label for label in labels.split(";") if label}
    return set(labels)


def property_values(test: dict[str, Any], name: str) -> list[str]:
    value = property_map(test).get(name)
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item) for item in value]
    return [str(value)]


def ctest_list_property_values(test: dict[str, Any], name: str) -> set[str]:
    values: set[str] = set()
    for value in property_values(test, name):
        values.update(item for item in value.split(";") if item)
    return values


def processor_values_for(test: dict[str, Any]) -> list[str]:
    values = property_values(test, "PROCESSORS")
    for key in ("processors", "PROCESSORS"):
        value = test.get(key)
        if value is None:
            continue
        if isinstance(value, list):
            values.extend(str(item) for item in value)
        else:
            values.append(str(value))
    return values


def bool_property(test: dict[str, Any], name: str) -> bool:
    values = property_values(test, name)
    return any(value.upper() in ("1", "ON", "TRUE", "YES") for value in values)


def command_text(test: dict[str, Any]) -> str:
    return " ".join(str(part) for part in test.get("command", []))


def normalized_path_text(value: object) -> str:
    text = str(value).replace("\\", "/")
    text = re.sub(r"/+", "/", text)
    return text.lower()


def normalized_command_text(test: dict[str, Any]) -> str:
    return normalized_path_text(command_text(test))


def cmake_definition(test: dict[str, Any], name: str) -> str | None:
    plain_prefix = f"-D{name}="
    typed_prefix = f"-D{name}:"
    for part in test.get("command", []):
        text = str(part)
        if text.startswith(plain_prefix):
            return text[len(plain_prefix) :]
        if text.startswith(typed_prefix):
            _, separator, value = text.partition("=")
            if separator:
                return value
    return None


def cmake_definitions(test: dict[str, Any], name: str) -> list[str]:
    plain_prefix = f"-D{name}="
    typed_prefix = f"-D{name}:"
    values: list[str] = []
    for part in test.get("command", []):
        text = str(part)
        if text.startswith(plain_prefix):
            values.append(text[len(plain_prefix) :])
        elif text.startswith(typed_prefix):
            _, separator, value = text.partition("=")
            if separator:
                values.append(value)
    return values


def display_path(root: Path, value: str) -> str:
    text = str(value).replace("\\", "/")
    normalized_text = normalized_path_text(text)
    root_text = str(root).replace("\\", "/").rstrip("/")
    normalized_root = normalized_path_text(root_text).rstrip("/")
    root_prefix = f"{normalized_root}/"
    if normalized_text.startswith(root_prefix):
        return text[len(root_text) + 1 :]

    for family in fixture_families(root):
        normalized_family = normalized_path_text(family)
        index = normalized_text.find(normalized_family)
        if index >= 0:
            return text[index:]
    return text


def fixture_family_match_tokens(root: Path, family: str) -> set[str]:
    family_path = root / family
    return {
        normalized_path_text(family),
        normalized_path_text(f"/{family}"),
        normalized_path_text(family_path),
        normalized_path_text(family_path.resolve()),
    }


def fixture_families(root: Path) -> list[str]:
    families = set(KNOWN_FIXTURE_FAMILIES)
    tests_dir = root / "tests"
    if tests_dir.exists():
        for family_dir in tests_dir.glob("*/fixtures"):
            if family_dir.is_dir():
                families.add(family_dir.relative_to(root).as_posix())
    return sorted(families)


def command_references_fixture_family(
    command_blob: str, root: Path, family: str
) -> bool:
    return any(
        token and token in command_blob
        for token in fixture_family_match_tokens(root, family)
    )


def fixture_family_for_text(root: Path, text: str) -> str | None:
    command_blob = normalized_path_text(text)
    for family in fixture_families(root):
        if command_references_fixture_family(command_blob, root, family):
            return family
    return None


def fixture_family_for_test(root: Path, test: dict[str, Any]) -> str | None:
    input_path = cmake_definition(test, "INPUT")
    if input_path:
        family = fixture_family_for_text(root, input_path)
        if family:
            return family
    return fixture_family_for_text(root, command_text(test))


def target_for_test(test: dict[str, Any]) -> str | None:
    target = cmake_definition(test, "TARGET")
    if target:
        return target.lower()

    labels = labels_for(test)
    for candidate in OPTIONAL_NATIVE_TARGETS:
        if f"{candidate}-native" in labels:
            return candidate

    name = str(test.get("name", "")).lower()
    for candidate in OPTIONAL_NATIVE_TARGETS:
        if re.search(rf"(^|[_-]){re.escape(candidate)}([_-]|$)", name):
            return candidate
    return None


def target_from_test_name(name: str) -> str | None:
    normalized_name = name.lower()
    matches = [
        target
        for target in OPTIONAL_NATIVE_TARGETS
        if re.search(rf"(^|[_-]){re.escape(target)}([_-]|$)", normalized_name)
    ]
    if len(matches) == 1:
        return matches[0]
    return None


def unreferenced_fixture_families(root: Path, tests: list[dict[str, Any]]) -> list[str]:
    command_blob = "\n".join(normalized_command_text(test) for test in tests)
    return [
        family
        for family in fixture_families(root)
        if not command_references_fixture_family(command_blob, root, family)
    ]


def ctest_config_candidates() -> list[str]:
    candidates: list[str] = []
    env_config = os.environ.get("CTEST_CONFIGURATION_TYPE")
    if env_config:
        candidates.append(env_config)
    for config in COMMON_CTEST_CONFIGS:
        if config not in candidates:
            candidates.append(config)
    return candidates


def load_ctest_inventory_for_fixture_scan(
    root: Path, build_dir: Path, ctest_config: str | None
) -> tuple[dict[str, Any], str | None]:
    inventory = load_ctest_inventory(build_dir, ctest_config)
    if ctest_config:
        return inventory, ctest_config

    missing = unreferenced_fixture_families(root, inventory.get("tests", []))
    if not missing:
        return inventory, None

    best_inventory = inventory
    best_missing = missing
    best_config: str | None = None
    for candidate in ctest_config_candidates():
        try:
            candidate_inventory = load_ctest_inventory(build_dir, candidate)
        except RuntimeError:
            continue
        candidate_missing = unreferenced_fixture_families(
            root, candidate_inventory.get("tests", [])
        )
        if len(candidate_missing) < len(best_missing):
            best_inventory = candidate_inventory
            best_missing = candidate_missing
            best_config = candidate
        if not candidate_missing:
            break
    return best_inventory, best_config


def owner_for(inventory: dict[str, Any], test: dict[str, Any]) -> str:
    graph = inventory.get("backtraceGraph", {})
    nodes = graph.get("nodes", [])
    files = graph.get("files", [])
    node_index = test.get("backtrace")
    while isinstance(node_index, int) and 0 <= node_index < len(nodes):
        node = nodes[node_index]
        file_index = node.get("file")
        line = node.get("line")
        if isinstance(file_index, int) and 0 <= file_index < len(files) and line:
            return f"{files[file_index]}:{line}"
        node_index = node.get("parent")
    return "<unknown CMake registration site>"


def context_from_mapping(
    lane: str, files: tuple[str, ...], *, include_fixture_file: bool = False
) -> str:
    details = [f"lane={lane}", f"owner_files={', '.join(files)}"]
    if include_fixture_file:
        details.insert(1, f"fixture_vars={FIXTURE_VARIABLE_FILE}")
    return "; ".join(details)


def fixture_family_lane_and_files(family: str) -> tuple[str, tuple[str, ...]]:
    return FIXTURE_FAMILY_CONTEXTS.get(
        family, (f"{family} fixture lane", ("tests/cmake/CrossGLTests.cmake",))
    )


def fixture_family_context(family: str) -> str:
    lane, files = fixture_family_lane_and_files(family)
    return context_from_mapping(lane, files, include_fixture_file=True)


def target_lane_and_files(target: str) -> tuple[str, tuple[str, ...]]:
    return TARGET_CONTEXTS.get(
        target,
        (
            f"{target} backend lane",
            ("tests/cmake/CrossGLSourcePackageBuildTests.cmake",),
        ),
    )


def target_context(target: str) -> str:
    lane, files = target_lane_and_files(target)
    return context_from_mapping(lane, files)


def optional_native_context(target: str) -> str:
    return f"{target_context(target)}; label_helper={OPTIONAL_NATIVE_HELPER}"


def package_smoke_context(lane: str, script: str) -> str:
    return (
        f"lane={lane}; owner_files=CMakeLists.txt, {script}; "
        "processor_source=CROSSGL_PACKAGE_SMOKE_PROCESSORS"
    )


def package_smoke_processor_source_contract(root: Path, name: str) -> bool:
    cmake_file = root / "CMakeLists.txt"
    if not cmake_file.exists():
        return False
    text = cmake_file.read_text(encoding="utf-8")
    pattern = (
        rf"set_tests_properties\(\s*{re.escape(name)}\s+PROPERTIES"
        r"[\s\S]*?"
        rf"PROCESSORS\s+\"\$\{{CROSSGL_PACKAGE_SMOKE_PROCESSORS\}}\""
        r"[\s\S]*?\)"
    )
    return re.search(pattern, text) is not None


def test_context(root: Path, inventory: dict[str, Any], test: dict[str, Any]) -> str:
    details: list[str] = []
    target = target_for_test(test)
    family = fixture_family_for_test(root, test)
    mode = cmake_definition(test, "MODE")
    input_path = cmake_definition(test, "INPUT")

    if target:
        lane, _ = target_lane_and_files(target)
        details.append(f"lane={lane}")
    elif family:
        lane, _ = fixture_family_lane_and_files(family)
        details.append(f"lane={lane}")
    details.append(f"registration={owner_for(inventory, test)}")
    if target:
        details.append(f"target={target}")
    if mode:
        details.append(f"mode={mode}")
    if family:
        details.append(f"fixture_family={family}")
    if input_path:
        details.append(f"input={display_path(root, input_path)}")
    return "context: " + "; ".join(details)


def check_required_ctest_registrations(
    root: Path, inventory: dict[str, Any], tests: list[dict[str, Any]]
) -> list[str]:
    errors: list[str] = []
    tests_by_name = {
        str(test.get("name", "")): test for test in tests if test.get("name")
    }
    for name, required_fragments in REQUIRED_CTEST_REGISTRATIONS:
        test = tests_by_name.get(name)
        if test is None:
            errors.append(f"{name}: required CTest is not registered")
            continue

        command_blob = normalized_command_text(test)
        for fragment in required_fragments:
            if normalized_path_text(fragment) not in command_blob:
                errors.append(
                    f"{name}: command is missing required fragment "
                    f"{fragment!r}; {test_context(root, inventory, test)}"
                )
    return errors


def check_package_smoke_registrations(
    root: Path, inventory: dict[str, Any], tests: list[dict[str, Any]]
) -> list[str]:
    errors: list[str] = []
    tests_by_name = {
        str(test.get("name", "")): test for test in tests if test.get("name")
    }
    for (
        name,
        lane,
        script,
        required_definitions,
        required_labels,
    ) in PACKAGE_SMOKE_REGISTRATIONS:
        test = tests_by_name.get(name)
        if test is None:
            errors.append(
                f"{name}: required native package/install smoke CTest is not "
                f"registered; context: {package_smoke_context(lane, script)}"
            )
            continue

        command_blob = normalized_command_text(test)
        if normalized_path_text(script) not in command_blob:
            errors.append(
                f"{name}: command is missing required smoke script {script!r}; "
                f"{test_context(root, inventory, test)}"
            )
        for definition in required_definitions:
            if cmake_definition(test, definition) is None:
                errors.append(
                    f"{name}: command is missing required -D{definition}= "
                    f"definition; {test_context(root, inventory, test)}"
                )

        labels = labels_for(test)
        missing_labels = sorted(set(required_labels) - labels)
        if missing_labels:
            errors.append(
                f"{name}: smoke CTest is missing required label(s) "
                f"{missing_labels}; {test_context(root, inventory, test)}"
            )

        processor_values = processor_values_for(test)
        smoke_parallel_level = cmake_definition(test, "CROSSGL_SMOKE_PARALLEL_LEVEL")
        if smoke_parallel_level is not None and not re.fullmatch(
            r"[1-9][0-9]*", smoke_parallel_level
        ):
            errors.append(
                f"{name}: CROSSGL_SMOKE_PARALLEL_LEVEL must be a positive "
                f"integer, got {smoke_parallel_level!r}; "
                f"{test_context(root, inventory, test)}"
            )
        if not processor_values:
            if not package_smoke_processor_source_contract(root, name):
                errors.append(
                    f"{name}: smoke CTest must reserve CTest processors so "
                    "parallel runs do not oversubscribe nested consumer "
                    "builds; source contract missing "
                    'PROCESSORS "${CROSSGL_PACKAGE_SMOKE_PROCESSORS}"; '
                    f"{test_context(root, inventory, test)}"
                )
            elif smoke_parallel_level is None:
                errors.append(
                    f"{name}: smoke CTest omitted PROCESSORS metadata and "
                    "does not pass CROSSGL_SMOKE_PARALLEL_LEVEL; "
                    f"{test_context(root, inventory, test)}"
                )
        elif not any(re.fullmatch(r"[1-9][0-9]*", value) for value in processor_values):
            errors.append(
                f"{name}: smoke CTest PROCESSORS must be a positive integer, "
                f"got {processor_values}; {test_context(root, inventory, test)}"
            )
    return errors


def mutable_output_paths(test: dict[str, Any]) -> list[tuple[str, str]]:
    paths: list[tuple[str, str]] = []
    for definition in MUTABLE_OUTPUT_DEFINITIONS:
        for value in cmake_definitions(test, definition):
            paths.append((definition, value))
    return paths


def registrations_are_serialized(left: dict[str, Any], right: dict[str, Any]) -> bool:
    if bool_property(left, "RUN_SERIAL") or bool_property(right, "RUN_SERIAL"):
        return True
    return bool(
        ctest_list_property_values(left, "RESOURCE_LOCK")
        & ctest_list_property_values(right, "RESOURCE_LOCK")
    )


def check_mutable_output_path_collisions(
    root: Path, inventory: dict[str, Any], tests: list[dict[str, Any]]
) -> list[str]:
    errors: list[str] = []
    paths: dict[str, list[tuple[str, str, dict[str, Any]]]] = {}
    for test in tests:
        for definition, value in mutable_output_paths(test):
            normalized = normalized_path_text(value)
            paths.setdefault(normalized, []).append((definition, value, test))

    for entries in paths.values():
        if len(entries) < 2:
            continue

        active_entries = [
            entry for entry in entries if intentional_failure_reason(entry[2]) is None
        ]
        if len(active_entries) < 2:
            continue

        unsafe_pairs = [
            (left, right)
            for left, right in combinations(active_entries, 2)
            if not registrations_are_serialized(left[2], right[2])
        ]
        if not unsafe_pairs:
            continue

        definition, value, _ = active_entries[0]
        names = sorted({str(entry[2].get("name", "")) for entry in active_entries})
        contexts = "; ".join(
            test_context(root, inventory, entry[2]) for entry in active_entries[:3]
        )
        suffix = "" if len(active_entries) <= 3 else "; ..."
        errors.append(
            f"{display_path(root, value)}: mutable -D{definition}= path is "
            "shared by parallel-capable tests "
            f"{names}; use unique output paths or shared RESOURCE_LOCK/RUN_SERIAL; "
            f"{contexts}{suffix}"
        )
    return errors


def check_optional_native_labels(
    root: Path, inventory: dict[str, Any], tests: list[dict[str, Any]]
) -> list[str]:
    errors: list[str] = []
    native_name = re.compile(r"(_native$|_native_tools_unavailable$)")
    for test in tests:
        name = test["name"]
        labels = labels_for(test)
        looks_optional_native = native_name.search(name) is not None
        name_target = target_from_test_name(name)
        availability_labels = labels & set(OPTIONAL_NATIVE_AVAILABILITY_LABELS)
        state_labels = labels & set(OPTIONAL_NATIVE_STATE_LABELS)
        skip_sentinel = name.endswith("_unavailable") and "SKIP:" in command_text(test)
        looks_optional_native_unavailable = (
            skip_sentinel and name_target in OPTIONAL_NATIVE_TARGETS
        )
        if state_labels and "optional-native" not in labels:
            errors.append(
                f"{name}: native-tool state label requires "
                "optional-native label; "
                f"{test_context(root, inventory, test)}"
            )
        if looks_optional_native_unavailable and "optional-native" not in labels:
            errors.append(
                f"{name}: optional native unavailable sentinel is missing "
                "optional-native label; "
                f"{test_context(root, inventory, test)}"
            )
        if "optional-native" in labels:
            target_labels = [
                label
                for label in labels
                if any(
                    label == f"{target}-native" for target in OPTIONAL_NATIVE_TARGETS
                )
            ]
            if len(target_labels) != 1:
                errors.append(
                    f"{name}: optional-native test must have exactly one "
                    f"<target>-native label, got {sorted(target_labels)}; "
                    f"{test_context(root, inventory, test)}"
                )
            elif (
                name_target is not None and target_labels[0] != f"{name_target}-native"
            ):
                errors.append(
                    f"{name}: optional-native target label {target_labels[0]!r} "
                    f"does not match target named by test ({name_target}); "
                    f"{test_context(root, inventory, test)}"
                )
            if len(state_labels) != 1:
                errors.append(
                    f"{name}: optional-native test must have exactly one "
                    "native-tool state label; "
                    f"{test_context(root, inventory, test)}"
                )
            if "native-tool-unavailable" in state_labels:
                skip_regex = property_values(test, "SKIP_REGULAR_EXPRESSION")
                if not any("SKIP:" in value for value in skip_regex):
                    errors.append(
                        f"{name}: native-tool-unavailable sentinel must skip "
                        "with SKIP_REGULAR_EXPRESSION matching SKIP:; "
                        f"{test_context(root, inventory, test)}"
                    )
                if "SKIP:" not in command_text(test):
                    errors.append(
                        f"{name}: native-tool-unavailable sentinel command "
                        "must advertise SKIP:; "
                        f"{test_context(root, inventory, test)}"
                    )
            if "native-tool-available" in state_labels:
                skip_regex = property_values(test, "SKIP_REGULAR_EXPRESSION")
                if any("SKIP:" in value for value in skip_regex):
                    errors.append(
                        f"{name}: native-tool-available test is registered "
                        "as a skip sentinel; "
                        f"{test_context(root, inventory, test)}"
                    )
        elif looks_optional_native:
            errors.append(
                f"{name}: optional native test is missing optional-native label; "
                f"{test_context(root, inventory, test)}"
            )
    return errors


def check_optional_native_target_coverage(tests: list[dict[str, Any]]) -> list[str]:
    errors: list[str] = []
    target_statuses = {target: set() for target in OPTIONAL_NATIVE_TARGETS}
    for test in tests:
        labels = labels_for(test)
        if "optional-native" not in labels:
            continue
        availability_labels = labels & set(OPTIONAL_NATIVE_AVAILABILITY_LABELS)
        for target in OPTIONAL_NATIVE_TARGETS:
            if f"{target}-native" in labels:
                target_statuses[target].update(availability_labels)

    for target, statuses in target_statuses.items():
        if not statuses:
            errors.append(
                f"{target}: no optional-native CTest coverage registered "
                "for native tool availability; "
                f"context: {optional_native_context(target)}"
            )
        elif len(statuses) != 1:
            errors.append(
                f"{target}: optional-native CTest coverage mixes availability "
                f"states {sorted(statuses)}; "
                f"context: {optional_native_context(target)}"
            )
    return errors


def check_optional_native_filter_contract(tests: list[dict[str, Any]]) -> list[str]:
    """Verify single-label CTest filters stay useful for optional native coverage."""
    errors: list[str] = []
    label_counts = {
        label: sum(1 for test in tests if label in labels_for(test))
        for label in ("optional-native", *OPTIONAL_NATIVE_STATE_LABELS)
    }
    if label_counts["optional-native"] == 0:
        errors.append(
            "optional-native: no CTest registrations match the label filter; "
            f"context: label_helper={OPTIONAL_NATIVE_HELPER}"
        )

    state_total = sum(label_counts[label] for label in OPTIONAL_NATIVE_STATE_LABELS)
    if state_total != label_counts["optional-native"]:
        errors.append(
            "native-tool state label filters must partition "
            "optional-native coverage, got "
            f"optional-native={label_counts['optional-native']}, "
            f"native-tool-available={label_counts['native-tool-available']} and "
            f"native-tool-unavailable={label_counts['native-tool-unavailable']} and "
            f"native-tool-policy={label_counts['native-tool-policy']}; "
            f"context: label_helper={OPTIONAL_NATIVE_HELPER}"
        )

    for target in OPTIONAL_NATIVE_TARGETS:
        target_label = f"{target}-native"
        target_count = sum(1 for test in tests if target_label in labels_for(test))
        if target_count == 0:
            errors.append(
                f"{target_label}: no CTest registrations match the label filter; "
                f"context: {optional_native_context(target)}"
            )
    return errors


def check_fixture_families(root: Path, tests: list[dict[str, Any]]) -> list[str]:
    errors: list[str] = []
    unreferenced = set(unreferenced_fixture_families(root, tests))
    for family in fixture_families(root):
        family_dir = root / family
        if not family_dir.exists():
            errors.append(
                f"{family}: fixture family directory is missing; "
                f"context: {fixture_family_context(family)}"
            )
            continue
        if not any(family_dir.rglob("*.cgl")):
            errors.append(
                f"{family}: fixture family has no .cgl fixtures; "
                f"context: {fixture_family_context(family)}"
            )
            continue
        if family in unreferenced:
            errors.append(
                f"{family}: no registered CTest command references this family; "
                f"context: {fixture_family_context(family)}"
            )
    return errors


def iter_negative_contract_cases(manifest: dict[str, Any]):
    groups = manifest.get("negative_contracts", {})
    if not isinstance(groups, dict):
        raise ValueError("negative_contracts must be an object")

    for group_name, group in sorted(groups.items()):
        if isinstance(group, dict):
            cases = group.get("cases", [])
        elif isinstance(group, list):
            cases = group
        else:
            raise ValueError(
                f"negative_contracts.{group_name} must be an object or list"
            )
        if not isinstance(cases, list):
            raise ValueError(f"negative_contracts.{group_name}.cases must be a list")
        for case in cases:
            if not isinstance(case, dict):
                raise ValueError(
                    f"negative_contracts.{group_name} contains a non-object case"
                )
            yield case


def load_language_contract_negative_fixture_paths(
    root: Path,
) -> tuple[list[str], list[str]]:
    manifest_path = root / LANGUAGE_CONTRACT_MANIFEST
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except OSError as exc:
        return [], [f"could not read {LANGUAGE_CONTRACT_MANIFEST}: {exc}"]
    except json.JSONDecodeError as exc:
        return [], [f"could not parse {LANGUAGE_CONTRACT_MANIFEST}: {exc}"]

    paths: set[str] = set()
    errors: list[str] = []
    try:
        cases = list(iter_negative_contract_cases(manifest))
    except ValueError as exc:
        return [], [f"{LANGUAGE_CONTRACT_MANIFEST}: {exc}"]

    for case in cases:
        if case.get("root", "compiler") != "compiler":
            continue
        path = case.get("path")
        if not isinstance(path, str) or not path.startswith("tests/check-failures/"):
            continue
        paths.add(path)
        if not (root / path).is_file():
            case_id = case.get("id", path)
            errors.append(
                f"{case_id}: negative language contract fixture is missing: {path}"
            )

    return sorted(paths), errors


def check_language_contract_negative_ctest_coverage(
    root: Path,
    tests: list[dict[str, Any]],
    contract_paths: list[str] | None = None,
) -> list[str]:
    errors: list[str] = []
    if contract_paths is None:
        contract_paths, load_errors = load_language_contract_negative_fixture_paths(
            root
        )
        errors.extend(load_errors)
        if load_errors:
            return errors

    command_blob = "\n".join(normalized_command_text(test) for test in tests)
    for path in sorted(contract_paths):
        if normalized_path_text(path) in command_blob:
            continue
        errors.append(
            f"{path}: compiler negative language contract fixture is not "
            "referenced by any CTest command; "
            f"context: {fixture_family_context('tests/check-failures')}; "
            f"manifest={LANGUAGE_CONTRACT_MANIFEST}"
        )
    return errors


def planned_failure_tests(tests: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        test
        for test in tests
        if "-DMODE=planned-build-failure" in test.get("command", [])
    ]


def has_intentional_failure_suffix(name: str) -> bool:
    return (
        name.endswith(INTENTIONAL_FAILURE_SUFFIXES)
        or re.search(r"(^|_)requires_[a-z0-9_]+$", name) is not None
    )


def intentional_failure_reason(test: dict[str, Any]) -> str | None:
    name = str(test.get("name", ""))
    labels = labels_for(test)
    mode = cmake_definition(test, "MODE")
    toolchain_path = cmake_definition(test, "TOOLCHAIN_PATH")

    if mode == "planned-build-failure":
        return "planned-build-failure mode"
    if mode == "metal-build-failure":
        return "metal build failure mode"
    if bool_property(test, "WILL_FAIL"):
        return "WILL_FAIL sentinel"
    if "native-tool-unavailable" in labels:
        return "native-tool-unavailable sentinel"

    # Fake tool failure tests still pass overall, but their purpose is to
    # exercise a failed external compiler/validator invocation.
    toolchain_blob = normalized_path_text(toolchain_path) if toolchain_path else ""
    _, fake_toolchain_marker, fake_toolchain_tail = toolchain_blob.partition(
        "/fake-toolchain/"
    )
    if (
        "fake" in name
        and fake_toolchain_marker
        and re.search(r"(^|[-_/])failure([-_/]|$)", fake_toolchain_tail)
    ):
        return "fake native/tool failure"
    return None


def check_intentional_failure_names(
    root: Path, inventory: dict[str, Any], tests: list[dict[str, Any]]
) -> list[str]:
    errors: list[str] = []
    for test in tests:
        reason = intentional_failure_reason(test)
        if reason is None:
            continue
        name = test["name"]
        if not has_intentional_failure_suffix(name):
            errors.append(
                f"{name}: intentional failure test name does not advertise "
                "planned/unsupported/target/tool/unavailable/requires intent "
                f"({reason}); "
                f"{test_context(root, inventory, test)}"
            )
    return errors


def run_planned_failure_tests(
    root: Path,
    build_dir: Path,
    inventory: dict[str, Any],
    tests: list[dict[str, Any]],
    ctest_config: str | None,
) -> list[str]:
    errors: list[str] = []
    ctest = shutil.which("ctest")
    if ctest is None:
        return ["ctest was not found on PATH"]
    for test in planned_failure_tests(tests):
        name = test["name"]
        command = [ctest, "--test-dir", str(build_dir)]
        if ctest_config:
            command.extend(["-C", ctest_config])
        command.extend(["--output-on-failure", "-R", f"^{re.escape(name)}$"])
        result = run(command)
        if result.returncode != 0:
            errors.append(
                f"{name}: planned-failure expectation is stale or drifting; "
                f"{test_context(root, inventory, test)}\n"
                f"{result.stdout}{result.stderr}"
            )
    return errors


def run_self_test() -> int:
    root = Path("D:/a/compiler/compiler")
    tests = [
        {
            "name": "windows_root_fixture",
            "command": [
                r"C:\Program Files\CMake\bin\cmake.exe",
                r"-DINPUT=D:\a\compiler\compiler\tests\fixtures\SimpleShader.cgl",
            ],
        },
        {
            "name": "windows_frontend_fixture",
            "command": [
                "cmake",
                r"-DINPUT=D:\a\compiler\compiler\tests\frontend\fixtures\ForIncrementDecrementHIRShader.cgl",
            ],
        },
        {
            "name": "windows_directx_fixture",
            "command": [
                "cmake",
                "D:/a/compiler/compiler/tests/directx/fixtures/DirectXFunctionParameterArrayShader.cgl",
            ],
        },
        {
            "name": "windows_metal_fixture",
            "command": [
                "cmake",
                r"-DINPUT=D:\a\compiler\compiler\tests\metal\fixtures\MetalFunctionParameterArrayShader.cgl",
            ],
        },
        {
            "name": "windows_optimizer_fixture",
            "command": [
                "cmake",
                r"-DINPUT=D:\a\compiler\compiler\tests\optimizer\fixtures\WorkgroupBarrierOptimizerBoundaryShader.cgl",
            ],
        },
        {
            "name": "windows_opengl_fixture",
            "command": [
                "cmake",
                r"-DINPUT=D:\a\compiler\compiler\tests\opengl\fixtures\OpenGLFunctionParameterArrayShader.cgl",
            ],
        },
        {
            "name": "windows_vulkan_fixture",
            "command": [
                "cmake",
                r"-DINPUT=D:\a\compiler\compiler\tests\vulkan\fixtures\VulkanFunctionParameterArrayShader.cgl",
            ],
        },
        {
            "name": "windows_check_failure_fixture",
            "command": [
                "cmake",
                r"-DINPUT=D:\a\compiler\compiler\tests\check-failures\BadSwizzleShader.cgl",
            ],
        },
    ]
    missing = unreferenced_fixture_families(root, tests)
    if missing:
        print(
            "Windows-style fixture path probe failed; unreferenced "
            f"families: {', '.join(missing)}",
            file=sys.stderr,
        )
        return 1
    inventory = {
        "backtraceGraph": {
            "files": ["tests/cmake/CrossGLSourcePackageBuildTests.cmake"],
            "nodes": [{"file": 0, "line": 2363}],
        }
    }
    planned_failure = {
        "name": "cglc_build_opengl_shadow_case_planned_failure",
        "backtrace": 0,
        "command": [
            "cmake",
            r"-DINPUT=D:\a\compiler\compiler\tests\fixtures\TextureArrayShadowCompareLodUnsupportedShader.cgl",
            "-DTARGET=opengl",
            "-DMODE=planned-build-failure",
        ],
    }
    context = test_context(root, inventory, planned_failure)
    expected_context_fragments = [
        "lane=opengl backend lane",
        "registration=tests/cmake/CrossGLSourcePackageBuildTests.cmake:2363",
        "target=opengl",
        "mode=planned-build-failure",
        "fixture_family=tests/fixtures",
        "input=tests/fixtures/TextureArrayShadowCompareLodUnsupportedShader.cgl",
    ]
    missing_fragments = [
        fragment for fragment in expected_context_fragments if fragment not in context
    ]
    if missing_fragments:
        print(
            "Diagnostic context probe failed; missing fragments: "
            f"{', '.join(missing_fragments)}\ncontext was: {context}",
            file=sys.stderr,
        )
        return 1
    family_context = fixture_family_context("tests/metal/fixtures")
    if (
        "lane=metal backend fixture lane" not in family_context
        or "tests/cmake/CrossGLMetalNativeBuildTests.cmake" not in family_context
    ):
        print(
            f"Fixture-family context probe failed; context was: {family_context}",
            file=sys.stderr,
        )
        return 1

    contract_fixture = "tests/check-failures/BadContractFixture.cgl"
    contract_coverage_errors = check_language_contract_negative_ctest_coverage(
        root, tests, [contract_fixture]
    )
    if not any(contract_fixture in error for error in contract_coverage_errors):
        print(
            "Language contract negative fixture probe failed to report missing "
            f"CTest coverage; errors were: {contract_coverage_errors}",
            file=sys.stderr,
        )
        return 1
    contract_coverage_ok = check_language_contract_negative_ctest_coverage(
        root,
        [
            {
                "name": "contract_check_failure",
                "command": [
                    "cmake",
                    r"-DINPUT=D:\a\compiler\compiler\tests\check-failures\BadContractFixture.cgl",
                ],
            }
        ],
        [contract_fixture],
    )
    if contract_coverage_ok:
        print(
            "Language contract negative fixture probe rejected a registered "
            f"CTest fixture; errors were: {contract_coverage_ok}",
            file=sys.stderr,
        )
        return 1

    package_smoke_inventory = {
        "backtraceGraph": {
            "files": ["CMakeLists.txt"],
            "nodes": [{"file": 0, "line": 290}, {"file": 0, "line": 308}],
        }
    }
    package_smoke_tests = [
        {
            "name": "cglc_install_layout_smoke",
            "backtrace": 0,
            "command": [
                "cmake",
                r"-DBUILD_DIR=D:\a\compiler\compiler\build",
                r"-DSOURCE_DIR=D:\a\compiler\compiler",
                r"-DINSTALL_PREFIX=D:\a\compiler\compiler\build\install-ctest-smoke",
                "-DCMAKE_CONFIGURATION_TYPES=Debug;Release",
                "-DCMAKE_BUILD_TYPE=Release",
                "-DCROSSGL_SMOKE_PARALLEL_LEVEL=4",
                "-P",
                r"D:\a\compiler\compiler\cmake\CrossGLInstallSmoke.cmake",
            ],
            "properties": [
                {
                    "name": "LABELS",
                    "value": [
                        "readiness",
                        "native-install-smoke",
                        "package-layout-smoke",
                    ],
                },
                {"name": "PROCESSORS", "value": "4"},
            ],
        },
        {
            "name": "cglc_cpack_layout_smoke",
            "backtrace": 1,
            "command": [
                "cmake",
                r"-DBUILD_DIR=D:\a\compiler\compiler\build",
                r"-DSOURCE_DIR=D:\a\compiler\compiler",
                r"-DCPACK_CONFIG=D:\a\compiler\compiler\build\CPackConfig.cmake",
                r"-DCPACK_COMMAND=C:\Program Files\CMake\bin\cpack.exe",
                "-DCMAKE_CONFIGURATION_TYPES=Debug;Release",
                "-DCMAKE_BUILD_TYPE=Release",
                "-DCROSSGL_SMOKE_PARALLEL_LEVEL=4",
                "-P",
                r"D:\a\compiler\compiler\cmake\CrossGLCPackSmoke.cmake",
            ],
            "properties": [
                {
                    "name": "LABELS",
                    "value": [
                        "readiness",
                        "native-package-smoke",
                        "package-layout-smoke",
                    ],
                },
                {"name": "PROCESSORS", "value": "4"},
            ],
        },
    ]
    package_smoke_errors = check_package_smoke_registrations(
        root, package_smoke_inventory, package_smoke_tests
    )
    if package_smoke_errors:
        print(
            "Native package/install smoke registration probe failed:\n"
            + "\n".join(f"- {error}" for error in package_smoke_errors),
            file=sys.stderr,
        )
        return 1
    omitted_processor_package_smoke = [
        dict(
            package_smoke_tests[0],
            properties=package_smoke_tests[0]["properties"][:1],
        ),
        dict(
            package_smoke_tests[1],
            properties=package_smoke_tests[1]["properties"][:1],
        ),
    ]
    omitted_processor_errors = check_package_smoke_registrations(
        Path(__file__).resolve().parents[1],
        package_smoke_inventory,
        omitted_processor_package_smoke,
    )
    if omitted_processor_errors:
        print(
            "Native package/install smoke omitted-processor probe failed:\n"
            + "\n".join(f"- {error}" for error in omitted_processor_errors),
            file=sys.stderr,
        )
        return 1
    top_level_processor_package_smoke = [
        dict(
            package_smoke_tests[0],
            properties=package_smoke_tests[0]["properties"][:1],
            processors=4,
        ),
        package_smoke_tests[1],
    ]
    top_level_processor_errors = check_package_smoke_registrations(
        root, package_smoke_inventory, top_level_processor_package_smoke
    )
    if top_level_processor_errors:
        print(
            "Native package/install smoke top-level processor probe failed:\n"
            + "\n".join(f"- {error}" for error in top_level_processor_errors),
            file=sys.stderr,
        )
        return 1
    missing_package_smoke_errors = check_package_smoke_registrations(
        root, package_smoke_inventory, package_smoke_tests[:1]
    )
    if not any(
        "cglc_cpack_layout_smoke" in error
        and "required native package/install smoke CTest is not registered" in error
        for error in missing_package_smoke_errors
    ):
        print(
            "Native package smoke missing-registration negative probe failed; "
            f"errors were: {missing_package_smoke_errors}",
            file=sys.stderr,
        )
        return 1
    missing_processor_package_smoke = [
        dict(
            package_smoke_tests[0],
            properties=package_smoke_tests[0]["properties"][:1],
        ),
        package_smoke_tests[1],
    ]
    missing_processor_errors = check_package_smoke_registrations(
        root / "__missing_processor_source_contract_probe",
        package_smoke_inventory,
        missing_processor_package_smoke,
    )
    if not any(
        "must reserve CTest processors" in error for error in missing_processor_errors
    ):
        print(
            "Native package/install smoke processor negative probe failed; "
            f"errors were: {missing_processor_errors}",
            file=sys.stderr,
        )
        return 1
    missing_label_package_smoke = [
        dict(
            package_smoke_tests[0],
            properties=[
                {
                    "name": "LABELS",
                    "value": ["readiness", "package-layout-smoke"],
                },
                {"name": "PROCESSORS", "value": "4"},
            ],
        ),
        package_smoke_tests[1],
    ]
    missing_label_errors = check_package_smoke_registrations(
        root, package_smoke_inventory, missing_label_package_smoke
    )
    if not any("native-install-smoke" in error for error in missing_label_errors):
        print(
            "Native install smoke label negative probe failed; "
            f"errors were: {missing_label_errors}",
            file=sys.stderr,
        )
        return 1

    output_collision_inventory = {
        "backtraceGraph": {
            "files": ["tests/cmake/CrossGLSourcePackageBuildTests.cmake"],
            "nodes": [{"file": 0, "line": 512}],
        }
    }
    output_collision_tests = [
        {
            "name": "cglc_build_directx_alpha_source_package",
            "backtrace": 0,
            "command": [
                "cmake",
                r"-DOUTPUT=D:\a\compiler\compiler\build\shared-output.cglb",
                "-DTARGET=directx",
                "-DMODE=source-package-build",
            ],
        },
        {
            "name": "cglc_build_directx_beta_source_package",
            "backtrace": 0,
            "command": [
                "cmake",
                r"-DOUTPUT=D:\a\compiler\compiler\build\shared-output.cglb",
                "-DTARGET=directx",
                "-DMODE=source-package-build",
            ],
        },
    ]
    output_collision_errors = check_mutable_output_path_collisions(
        root, output_collision_inventory, output_collision_tests
    )
    if not any("mutable -DOUTPUT= path" in error for error in output_collision_errors):
        print(
            "Mutable output collision negative probe failed; "
            f"errors were: {output_collision_errors}",
            file=sys.stderr,
        )
        return 1
    serialized_output_tests = [
        dict(
            test,
            properties=[{"name": "RESOURCE_LOCK", "value": "shared-output"}],
        )
        for test in output_collision_tests
    ]
    serialized_output_errors = check_mutable_output_path_collisions(
        root, output_collision_inventory, serialized_output_tests
    )
    if serialized_output_errors:
        print(
            "Mutable output collision RESOURCE_LOCK probe failed:\n"
            + "\n".join(f"- {error}" for error in serialized_output_errors),
            file=sys.stderr,
        )
        return 1
    planned_output_collision_errors = check_mutable_output_path_collisions(
        root,
        output_collision_inventory,
        [
            output_collision_tests[0],
            {
                "name": "cglc_build_directx_shadow_case_planned_failure",
                "backtrace": 0,
                "command": [
                    "cmake",
                    r"-DOUTPUT=D:\a\compiler\compiler\build\shared-output.cglb",
                    "-DTARGET=directx",
                    "-DMODE=planned-build-failure",
                ],
            },
        ],
    )
    if planned_output_collision_errors:
        print(
            "Mutable output collision planned-failure probe failed:\n"
            + "\n".join(f"- {error}" for error in planned_output_collision_errors),
            file=sys.stderr,
        )
        return 1

    will_fail_errors = check_intentional_failure_names(
        root,
        inventory,
        [
            {
                "name": "cglc_requires_diagnostics_json",
                "backtrace": 0,
                "command": ["cmake", "-P", "ExpectCommand.cmake"],
                "properties": [{"name": "WILL_FAIL", "value": True}],
            }
        ],
    )
    if will_fail_errors:
        print(
            "WILL_FAIL naming probe failed:\n"
            + "\n".join(f"- {error}" for error in will_fail_errors),
            file=sys.stderr,
        )
        return 1
    bad_tool_failure_errors = check_intentional_failure_names(
        root,
        inventory,
        [
            {
                "name": "cglc_build_directx_fake_dxc_failure",
                "backtrace": 0,
                "command": [
                    "cmake",
                    "-DTOOLCHAIN_PATH=D:/a/compiler/compiler/build/fake-toolchain/dxc-failure",
                ],
            }
        ],
    )
    if not any(
        "fake native/tool failure" in error for error in bad_tool_failure_errors
    ):
        print(
            "Fake tool failure naming negative probe failed; "
            f"errors were: {bad_tool_failure_errors}",
            file=sys.stderr,
        )
        return 1
    optimizer_family_context = fixture_family_context("tests/optimizer/fixtures")
    if (
        "lane=optimizer fixture lane" not in optimizer_family_context
        or "tests/cmake/CrossGLOptimizerTests.cmake" not in optimizer_family_context
    ):
        print(
            "Optimizer fixture-family context probe failed; "
            f"context was: {optimizer_family_context}",
            file=sys.stderr,
        )
        return 1
    native_context = optional_native_context("directx")
    if (
        "lane=directx backend lane" not in native_context
        or OPTIONAL_NATIVE_HELPER not in native_context
    ):
        print(
            f"Optional-native context probe failed; context was: {native_context}",
            file=sys.stderr,
        )
        return 1

    optional_native_inventory = {
        "backtraceGraph": {
            "files": [OPTIONAL_NATIVE_HELPER],
            "nodes": [{"file": 0, "line": 135}],
        }
    }
    available_tests = [
        {
            "name": f"cglc_build_{target}_native",
            "backtrace": 0,
            "command": ["cmake", "-P", "ExpectCommand.cmake"],
            "properties": [
                {
                    "name": "LABELS",
                    "value": [
                        "optional-native",
                        f"{target}-native",
                        "native-tool-available",
                    ],
                }
            ],
        }
        for target in OPTIONAL_NATIVE_TARGETS
    ]
    unavailable_tests = [
        {
            "name": f"cglc_build_{target}_native_tools_unavailable",
            "backtrace": 0,
            "command": ["cmake", "-E", "echo", f"SKIP: {target} tools missing"],
            "properties": [
                {
                    "name": "LABELS",
                    "value": [
                        "optional-native",
                        f"{target}-native",
                        "native-tool-unavailable",
                    ],
                },
                {"name": "SKIP_REGULAR_EXPRESSION", "value": "^SKIP:"},
            ],
        }
        for target in OPTIONAL_NATIVE_TARGETS
    ]
    policy_tests = [
        {
            "name": f"cglc_build_{target}_native_fake_tool_failure",
            "backtrace": 0,
            "command": [
                "cmake",
                f"-DTOOLCHAIN_PATH=D:/a/compiler/compiler/build/fake-toolchain/{target}-failure",
            ],
            "properties": [
                {
                    "name": "LABELS",
                    "value": [
                        "optional-native",
                        f"{target}-native",
                        "native-tool-policy",
                    ],
                }
            ],
        }
        for target in OPTIONAL_NATIVE_TARGETS
    ]
    optional_native_checks = [
        check_optional_native_labels,
        check_intentional_failure_names,
        lambda _root, _inventory, tests: check_optional_native_target_coverage(tests),
        lambda _root, _inventory, tests: check_optional_native_filter_contract(tests),
    ]
    for label_state, sample_tests in (
        ("available", available_tests),
        ("unavailable", unavailable_tests),
    ):
        sample_errors: list[str] = []
        for checker in optional_native_checks:
            sample_errors.extend(checker(root, optional_native_inventory, sample_tests))
        if sample_errors:
            print(
                f"Optional-native {label_state} label probe failed:\n"
                + "\n".join(f"- {error}" for error in sample_errors),
                file=sys.stderr,
            )
            return 1

    policy_errors: list[str] = []
    for checker in (
        check_optional_native_labels,
        check_intentional_failure_names,
        lambda _root, _inventory, tests: check_optional_native_filter_contract(tests),
    ):
        policy_errors.extend(checker(root, optional_native_inventory, policy_tests))
    if policy_errors:
        print(
            "Optional-native policy label probe failed:\n"
            + "\n".join(f"- {error}" for error in policy_errors),
            file=sys.stderr,
        )
        return 1

    bad_unavailable = [
        dict(
            unavailable_tests[0],
            properties=unavailable_tests[0]["properties"][:1],
        )
    ]
    bad_unavailable_errors = check_optional_native_labels(
        root, optional_native_inventory, bad_unavailable
    )
    if not any(
        "must skip with SKIP_REGULAR_EXPRESSION" in error
        for error in bad_unavailable_errors
    ):
        print(
            "Optional-native skip sentinel negative probe failed; "
            f"errors were: {bad_unavailable_errors}",
            file=sys.stderr,
        )
        return 1
    missing_optional_native_unavailable = [
        dict(
            unavailable_tests[0],
            properties=[
                {
                    "name": "LABELS",
                    "value": [
                        "vulkan-native",
                        "native-tool-unavailable",
                    ],
                },
                {"name": "SKIP_REGULAR_EXPRESSION", "value": "^SKIP:"},
            ],
        )
    ]
    missing_optional_native_unavailable_errors = check_optional_native_labels(
        root, optional_native_inventory, missing_optional_native_unavailable
    )
    if not any(
        "native-tool state label requires optional-native label" in error
        for error in missing_optional_native_unavailable_errors
    ) or not any(
        "optional native unavailable sentinel is missing optional-native label" in error
        for error in missing_optional_native_unavailable_errors
    ):
        print(
            "Optional-native unavailable missing-label negative probe failed; "
            f"errors were: {missing_optional_native_unavailable_errors}",
            file=sys.stderr,
        )
        return 1
    mismatched_target_label = [
        dict(
            unavailable_tests[0],
            name="cglc_build_metal_native_tools_unavailable",
        )
    ]
    mismatched_target_label_errors = check_optional_native_labels(
        root, optional_native_inventory, mismatched_target_label
    )
    if not any(
        "does not match target named by test (metal)" in error
        for error in mismatched_target_label_errors
    ):
        print(
            "Optional-native target-label mismatch negative probe failed; "
            f"errors were: {mismatched_target_label_errors}",
            file=sys.stderr,
        )
        return 1
    bad_unavailable_name = [
        dict(
            unavailable_tests[0],
            name="cglc_package_verify_json_schema_metal_native",
        )
    ]
    bad_unavailable_name_errors = check_intentional_failure_names(
        root, optional_native_inventory, bad_unavailable_name
    )
    if not any(
        "native-tool-unavailable sentinel" in error
        for error in bad_unavailable_name_errors
    ):
        print(
            "Optional-native unavailable naming negative probe failed; "
            f"errors were: {bad_unavailable_name_errors}",
            file=sys.stderr,
        )
        return 1
    print("Windows-style fixture path probe passed.")
    print("Diagnostic owner context probes passed.")
    print("Native package/install smoke registration probes passed.")
    print("Mutable output collision probes passed.")
    print("Optional-native label contract probes passed.")
    return 0


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path)
    parser.add_argument("--build-dir", type=Path)
    parser.add_argument(
        "--ctest-config",
        help="CTest configuration to use when reading or running multi-config tests.",
    )
    parser.add_argument(
        "--metadata-only",
        action="store_true",
        help="Skip executing planned-failure tests; useful when called by CTest.",
    )
    parser.add_argument(
        "--self-test",
        action="store_true",
        help="Run checker-internal portability probes and exit.",
    )
    args = parser.parse_args(argv)

    if args.self_test:
        return run_self_test()
    if args.root is None or args.build_dir is None:
        parser.error("--root and --build-dir are required unless --self-test is used")

    root = args.root.resolve()
    build_dir = args.build_dir.resolve()
    ctest_config = args.ctest_config or None
    inventory, selected_config = load_ctest_inventory_for_fixture_scan(
        root, build_dir, ctest_config
    )
    tests = inventory.get("tests", [])
    errors: list[str] = []

    errors.extend(check_required_ctest_registrations(root, inventory, tests))
    errors.extend(check_package_smoke_registrations(root, inventory, tests))
    errors.extend(check_mutable_output_path_collisions(root, inventory, tests))
    errors.extend(check_optional_native_labels(root, inventory, tests))
    errors.extend(check_optional_native_target_coverage(tests))
    errors.extend(check_optional_native_filter_contract(tests))
    errors.extend(check_fixture_families(root, tests))
    errors.extend(check_language_contract_negative_ctest_coverage(root, tests))
    errors.extend(check_intentional_failure_names(root, inventory, tests))
    if not args.metadata_only:
        errors.extend(
            run_planned_failure_tests(
                root, build_dir, inventory, tests, selected_config
            )
        )

    if errors:
        print("CTest registration health check failed:", file=sys.stderr)
        for error in errors:
            print(f"- {error}", file=sys.stderr)
        return 1

    planned_count = len(planned_failure_tests(tests))
    mode = "metadata-only" if args.metadata_only else "with planned-failure execution"
    print(
        f"CTest registration health passed for {len(tests)} tests "
        f"({planned_count} planned-failure tests, {mode})."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
