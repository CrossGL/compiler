#!/usr/bin/env python3
"""Shared evidence helpers for CrossGL Python validation tools."""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable


SUPPORT_MATRIX_PATH = Path("tests/conformance/hir-verifier-v0-coverage.json")


class UnitTestFunctionAliases:
    def __contains__(self, name: object) -> bool:
        return (
            isinstance(name, str)
            and re.fullmatch(r"test[A-Z][A-Za-z0-9_]*", name) is not None
        )


UNIT_TEST_FUNCTION_ALIASES = UnitTestFunctionAliases()


@dataclass(frozen=True)
class EvidenceReference:
    name: str
    line: int


@dataclass(frozen=True)
class OptionalNativeEvidence:
    name: str
    target: str
    category: str


@dataclass(frozen=True)
class CTestInventory:
    names: set[str]
    labels_by_name: dict[str, set[str]]


def _run(command: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        check=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _walk_evidence_names(value: Any) -> Iterable[str]:
    if isinstance(value, dict):
        kind = value.get("kind")
        name = value.get("name")
        if (
            isinstance(kind, str)
            and kind in {"support-matrix", "diagnostic", "planned-failure"}
            and isinstance(name, str)
            and name
        ):
            yield name
        for child in value.values():
            yield from _walk_evidence_names(child)
    elif isinstance(value, list):
        for item in value:
            yield from _walk_evidence_names(item)


def parse_evidence_references(path: Path) -> list[EvidenceReference]:
    payload = _read_json(path)
    names = list(_walk_evidence_names(payload))
    line_numbers = _name_line_numbers(path, set(names))
    return [
        EvidenceReference(name=name, line=line)
        for name in names
        for line in line_numbers.get(name, [])
    ]


def _name_line_numbers(path: Path, names: set[str]) -> dict[str, list[int]]:
    locations = {name: [] for name in names}
    quoted_names = {
        json.dumps(name, ensure_ascii=False): name for name in sorted(names)
    }
    for index, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if '"name"' not in line:
            continue
        for quoted, name in quoted_names.items():
            if quoted in line:
                locations[name].append(index)
    return locations


def line_locations(
    references: Iterable[EvidenceReference],
) -> dict[str, list[int]]:
    locations: dict[str, list[int]] = {}
    for reference in references:
        locations.setdefault(reference.name, []).append(reference.line)
    return {name: sorted(set(lines)) for name, lines in sorted(locations.items())}


def format_locations(path: Path, locations: dict[str, list[int]], name: str) -> str:
    lines = locations.get(name, [])
    if not lines:
        return str(path)
    return ", ".join(f"{path}:{line}" for line in lines)


def load_ctest_inventory(build_dir: Path, ctest_config: str | None) -> CTestInventory:
    ctest = shutil.which("ctest")
    if ctest is None:
        raise RuntimeError("ctest was not found on PATH")

    command = [ctest, "--test-dir", str(build_dir)]
    if ctest_config:
        command.extend(["-C", ctest_config])
    command.append("--show-only=json-v1")

    result = _run(command)
    if result.returncode != 0:
        raise RuntimeError(
            "ctest JSON inventory failed:\n"
            f"stdout:\n{result.stdout}\n"
            f"stderr:\n{result.stderr}"
        )

    payload = json.loads(result.stdout)
    tests = payload.get("tests", [])
    if not isinstance(tests, list):
        raise RuntimeError("ctest JSON inventory tests field was not an array")

    names: set[str] = set()
    labels_by_name: dict[str, set[str]] = {}
    for test in tests:
        if not isinstance(test, dict):
            continue
        name = test.get("name")
        if not isinstance(name, str) or not name:
            continue
        names.add(name)
        labels_by_name[name] = _test_labels(test)
    return CTestInventory(names=names, labels_by_name=labels_by_name)


def _test_labels(test: dict[str, Any]) -> set[str]:
    labels: set[str] = set()
    for prop in test.get("properties", []):
        if not isinstance(prop, dict) or prop.get("name") != "LABELS":
            continue
        value = prop.get("value")
        if isinstance(value, str):
            labels.update(label for label in value.split(";") if label)
        elif isinstance(value, list):
            labels.update(str(label) for label in value if str(label))
    return labels


def declared_optional_native_evidence_names(
    root: Path,
) -> set[OptionalNativeEvidence]:
    evidence: set[OptionalNativeEvidence] = set()
    for cmake_file in (root / "tests" / "cmake").glob("*.cmake"):
        try:
            text = cmake_file.read_text(encoding="utf-8")
        except OSError:
            continue
        for match in re.finditer(
            r"\bNAME\s+([A-Za-z0-9_]*unavailable[A-Za-z0-9_]*)",
            text,
        ):
            name = match.group(1)
            evidence.add(
                OptionalNativeEvidence(
                    name=name,
                    target=_target_from_evidence_name(name),
                    category="declared-unavailable",
                )
            )
    return evidence


def split_missing_ctest_references(
    ctest_references: set[str],
    inventory: CTestInventory,
    optional_evidence: set[OptionalNativeEvidence],
) -> tuple[list[str], set[OptionalNativeEvidence]]:
    optional_by_name = {item.name: item for item in optional_evidence}
    missing: list[str] = []
    unavailable: set[OptionalNativeEvidence] = set()

    for name in sorted(ctest_references):
        if name not in inventory.names:
            optional_item = optional_by_name.get(name)
            if optional_item is not None:
                unavailable.add(optional_item)
            else:
                missing.append(name)
            continue

        labels = inventory.labels_by_name.get(name, set())
        if "native-tool-unavailable" in labels:
            unavailable.add(
                OptionalNativeEvidence(
                    name=name,
                    target=_target_from_labels_or_name(labels, name),
                    category="native-tool-unavailable",
                )
            )

    return missing, unavailable


def validate_unit_test_aliases(
    root: Path, evidence_names: set[str], ctest_names: set[str]
) -> list[str]:
    unit_aliases = sorted(
        name for name in evidence_names if name in UNIT_TEST_FUNCTION_ALIASES
    )
    if not unit_aliases:
        return []

    unit_test_source = root / "tests" / "unit" / "CompilerUnitTests.cpp"
    try:
        text = unit_test_source.read_text(encoding="utf-8")
    except OSError as exc:
        return [f"{unit_test_source}: could not read unit-test source: {exc}"]

    declared_functions = set(
        re.findall(r"\bvoid\s+(test[A-Z][A-Za-z0-9_]*)\s*\(", text)
    )
    called_functions = set(re.findall(r"\b(test[A-Z][A-Za-z0-9_]*)\s*\(\s*\);", text))
    missing_functions = [
        name for name in unit_aliases if name not in declared_functions
    ]
    missing_calls = [name for name in unit_aliases if name not in called_functions]

    errors: list[str] = []
    if "crossgl_unit_tests" not in ctest_names:
        errors.append(
            "unit-test evidence aliases require the crossgl_unit_tests CTest "
            "to be registered"
        )
    if missing_functions:
        errors.append(
            f"{unit_test_source}: missing unit-test function(s): "
            + ", ".join(missing_functions)
        )
    if missing_calls:
        errors.append(
            f"{unit_test_source}: unit-test function(s) are not called from "
            "main(): " + ", ".join(missing_calls)
        )
    return errors


def _target_from_evidence_name(name: str) -> str:
    for target in ("vulkan", "metal", "directx", "opengl"):
        if f"_{target}_" in name or name.startswith(f"{target}_"):
            return target
    return "unknown"


def _target_from_labels_or_name(labels: set[str], name: str) -> str:
    for label in labels:
        if label.endswith("-native"):
            return label.removesuffix("-native")
    return _target_from_evidence_name(name)
