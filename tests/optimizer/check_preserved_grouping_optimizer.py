#!/usr/bin/env python3
"""Check that optimizer child replacements preserve required grouping."""

from __future__ import annotations

import argparse
import subprocess
from pathlib import Path


FIXTURE = Path("tests/optimizer/fixtures/BooleanAlgebraOptimizerShader.cgl")


def run_cglc(cglc: Path, root: Path, *args: str) -> str:
    result = subprocess.run(
        [str(cglc), *args],
        cwd=root,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if result.returncode != 0:
        raise SystemExit(
            f"cglc {' '.join(args)} failed with exit code {result.returncode}\n"
            f"stdout:\n{result.stdout}\n"
            f"stderr:\n{result.stderr}"
        )
    return result.stdout


def require_contains(text: str, needle: str) -> None:
    if needle not in text:
        raise SystemExit(f"expected output to contain {needle!r}\n{text}")


def require_absent(text: str, needle: str) -> None:
    if needle in text:
        raise SystemExit(f"expected output to omit {needle!r}\n{text}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--cglc", type=Path, default=Path("build/cglc"))
    args = parser.parse_args()

    root = args.root.resolve()
    cglc = args.cglc
    if not cglc.is_absolute():
        cglc = root / cglc

    hir = run_cglc(cglc, root, "dump-ir", str(FIXTURE), "--stage", "hir")
    for declaration in (
        "decl bool boolLiteralNestedKeep = "
        "base && ((dynamicIndex > 74) || (dynamicIndex > 75)) : bool",
        "decl bool selectNestedKeep = "
        "base && ((dynamicIndex > 76) || (dynamicIndex > 77)) : bool",
        "decl bool sameArmSelectNestedKeep = "
        "base && ((dynamicIndex > 78) || (dynamicIndex > 79)) : bool",
        "decl bool algebraicChildNestedKeep = "
        "base && ((dynamicIndex > 80) || (dynamicIndex > 81)) : bool",
        "decl bool literalSelectNestedKeep = "
        "base && ((dynamicIndex > 82) || (dynamicIndex > 83)) : bool",
    ):
        require_contains(hir, declaration)

    for ambiguous in (
        "boolLiteralNestedKeep = base && dynamicIndex > 74 || dynamicIndex > 75",
        "selectNestedKeep = base && dynamicIndex > 76 || dynamicIndex > 77",
        "sameArmSelectNestedKeep = base && dynamicIndex > 78 || dynamicIndex > 79",
        "algebraicChildNestedKeep = base && dynamicIndex > 80 || dynamicIndex > 81",
        "literalSelectNestedKeep = base && dynamicIndex > 82 || dynamicIndex > 83",
    ):
        require_absent(hir, ambiguous)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
