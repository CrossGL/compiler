#!/usr/bin/env python3
"""Check that committed CrossGL .cgl fixtures are registered by tests.

The guard intentionally works from source files instead of configured CTest
metadata so it can catch missing fixture variables before a test is even added.
"""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass
from pathlib import Path


FIXTURE_ROOTS = (
    "tests/fixtures",
    "tests/frontend/fixtures",
    "tests/directx/fixtures",
    "tests/metal/fixtures",
    "tests/opengl/fixtures",
    "tests/vulkan/fixtures",
    "tests/optimizer/fixtures",
    "tests/check-failures",
)
FIXTURE_VARIABLE_FILE = Path("tests/cmake/CrossGLTestFixtures.cmake")

# These Vulkan fixtures are committed policy probes for unsupported frontend
# shapes. They are intentionally fixture-only on the current mainline; any new
# fixture-only file should either be registered or documented here with a reason.
ALLOWLISTED_UNREGISTERED_FIXTURES = {
    "tests/vulkan/fixtures/VulkanFunctionParameterArrayWriteUnsupportedShader.cgl",
}

SET_CGL_RE = re.compile(
    r"""
    \bset\s*\(
      \s*(?P<variable>[A-Za-z_][A-Za-z0-9_]*)
      \s+
      (?P<quote>["']?)
      (?P<path>(?:\$\{CMAKE_CURRENT_SOURCE_DIR\}/)?tests/
        (?:
          fixtures
          |frontend/fixtures
          |directx/fixtures
          |metal/fixtures
          |opengl/fixtures
          |vulkan/fixtures
          |optimizer/fixtures
          |check-failures
        )
        /[^\s"')]+\.cgl)
      (?P=quote)
    """,
    re.VERBOSE,
)
CGL_PATH_RE = re.compile(
    r"""
    (?P<path>(?:\$\{CMAKE_CURRENT_SOURCE_DIR\}/)?tests/
      (?:
        fixtures
        |frontend/fixtures
        |directx/fixtures
        |metal/fixtures
        |opengl/fixtures
        |vulkan/fixtures
        |optimizer/fixtures
        |check-failures
      )
      /[^\s"');]+\.cgl)
    """,
    re.VERBOSE,
)


@dataclass(frozen=True, order=True)
class Reference:
    fixture: str
    source: str
    line: int
    variable: str | None = None


def relative_posix(root: Path, path: Path) -> str:
    return path.relative_to(root).as_posix()


def normalize_fixture_path(path_text: str) -> str:
    return path_text.replace("\\", "/").removeprefix("${CMAKE_CURRENT_SOURCE_DIR}/")


def cmake_files(root: Path) -> list[Path]:
    files = [root / "CMakeLists.txt"]
    files.extend(sorted((root / "cmake").glob("*.cmake")))
    files.extend(sorted((root / "tests" / "cmake").glob("*.cmake")))
    return [path for path in files if path.exists()]


def line_number(text: str, offset: int) -> int:
    return text.count("\n", 0, offset) + 1


def discover_fixtures(root: Path) -> set[str]:
    fixtures: set[str] = set()
    for fixture_root in FIXTURE_ROOTS:
        directory = root / fixture_root
        if not directory.is_dir():
            raise ValueError(f"missing fixture root {fixture_root}")
        fixtures.update(relative_posix(root, path) for path in directory.glob("*.cgl"))
    return fixtures


def discover_references(
    root: Path,
) -> tuple[set[str], list[Reference], list[Reference]]:
    all_references: set[str] = set()
    fixture_variable_references: list[Reference] = []
    direct_references: list[Reference] = []

    for path in cmake_files(root):
        text = path.read_text(encoding="utf-8")
        source = relative_posix(root, path)

        for match in CGL_PATH_RE.finditer(text):
            fixture = normalize_fixture_path(match.group("path"))
            all_references.add(fixture)
            direct_references.append(
                Reference(fixture, source, line_number(text, match.start()))
            )

        if path == root / FIXTURE_VARIABLE_FILE:
            for match in SET_CGL_RE.finditer(text):
                fixture = normalize_fixture_path(match.group("path"))
                fixture_variable_references.append(
                    Reference(
                        fixture,
                        source,
                        line_number(text, match.start()),
                        match.group("variable"),
                    )
                )

    return all_references, fixture_variable_references, direct_references


def format_reference(reference: Reference) -> str:
    location = f"{reference.source}:{reference.line}"
    if reference.variable:
        return f"{reference.fixture} ({reference.variable} at {location})"
    return f"{reference.fixture} ({location})"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=".", help="CrossGL-Compiler repository root")
    args = parser.parse_args()

    root = Path(args.root).resolve()
    errors: list[str] = []

    try:
        fixtures = discover_fixtures(root)
        referenced_fixtures, fixture_variables, direct_references = discover_references(
            root
        )
    except (OSError, ValueError) as exc:
        print(f"fixture registration check failed: {exc}", file=sys.stderr)
        return 1

    unknown_allowlist_entries = sorted(ALLOWLISTED_UNREGISTERED_FIXTURES - fixtures)
    for fixture in unknown_allowlist_entries:
        errors.append(f"allowlist entry does not exist: {fixture}")

    missing_registration = sorted(
        fixtures - referenced_fixtures - ALLOWLISTED_UNREGISTERED_FIXTURES
    )
    for fixture in missing_registration:
        errors.append(
            f"{fixture}: no CrossGLTestFixtures.cmake variable or direct CMake "
            "CTest reference"
        )

    missing_fixture_variables = sorted(
        reference
        for reference in fixture_variables
        if not (root / reference.fixture).is_file()
    )
    for reference in missing_fixture_variables:
        errors.append(
            f"fixture variable points at missing file: {format_reference(reference)}"
        )

    missing_direct_references = sorted(
        reference
        for reference in direct_references
        if not (root / reference.fixture).is_file()
        and reference.fixture not in ALLOWLISTED_UNREGISTERED_FIXTURES
    )
    for reference in missing_direct_references:
        errors.append(
            "CMake fixture reference points at missing file: "
            f"{format_reference(reference)}"
        )

    if errors:
        for error in errors:
            print(f"fixture registration check failed: {error}", file=sys.stderr)
        return 1

    print(
        "validated "
        f"{len(fixtures)} .cgl fixtures; "
        f"{len(fixture_variables)} CrossGLTestFixtures.cmake variables; "
        f"{len(ALLOWLISTED_UNREGISTERED_FIXTURES)} documented fixture-only files"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
