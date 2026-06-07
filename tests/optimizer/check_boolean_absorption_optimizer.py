#!/usr/bin/env python3
"""Check target-independent HIR boolean absorption cleanup evidence."""

from __future__ import annotations

import argparse
import json
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
        "decl bool absorptionAndRightPure = base : bool",
        "decl bool absorptionAndLeftPure = base : bool",
        "decl bool absorptionOrRightPure = base : bool",
        "decl bool absorptionOrLeftPure = base : bool",
        "decl bool absorptionAndRightInnerPure = base : bool",
        "decl bool absorptionAndLeftInnerPure = base : bool",
        "decl bool absorptionOrRightInnerPure = base : bool",
        "decl bool absorptionOrLeftInnerPure = base : bool",
    ):
        require_contains(hir, declaration)

    for declaration in (
        "decl bool absorptionAndUnknownCompound = "
        "base && (base || unknownFlag(dynamicIndex)) : bool",
        "decl bool absorptionOrUnknownCompound = "
        "base || (base && unknownFlag(dynamicIndex)) : bool",
        "decl bool absorptionAndUnknownOperand = "
        "unknownFlag(dynamicIndex) && (unknownFlag(dynamicIndex) || base) : bool",
        "decl bool absorptionOrUnknownOperand = "
        "unknownFlag(dynamicIndex) || (unknownFlag(dynamicIndex) && base) : bool",
        "decl bool absorptionAndUnknownCompoundRightInner = "
        "base && (unknownFlag(dynamicIndex) || base) : bool",
        "decl bool absorptionOrUnknownCompoundRightInner = "
        "base || (unknownFlag(dynamicIndex) && base) : bool",
        "decl bool absorptionAndUnknownOperandRightInner = "
        "unknownFlag(dynamicIndex) && (base || unknownFlag(dynamicIndex)) : bool",
        "decl bool absorptionOrUnknownOperandRightInner = "
        "unknownFlag(dynamicIndex) || (base && unknownFlag(dynamicIndex)) : bool",
    ):
        require_contains(hir, declaration)

    for original in (
        "absorptionAndRightPure = base && (base || (dynamicIndex > 9))",
        "absorptionAndLeftPure = (base || (dynamicIndex > 10)) && base",
        "absorptionOrRightPure = base || (base && (dynamicIndex > 11))",
        "absorptionOrLeftPure = (base && (dynamicIndex > 12)) || base",
        "absorptionAndRightInnerPure = base && ((dynamicIndex > 13) || base)",
        "absorptionAndLeftInnerPure = ((dynamicIndex > 14) || base) && base",
        "absorptionOrRightInnerPure = base || ((dynamicIndex > 15) && base)",
        "absorptionOrLeftInnerPure = ((dynamicIndex > 16) && base) || base",
        "absorptionAndUnknownCompound = base : bool",
        "absorptionOrUnknownCompound = base : bool",
        "absorptionAndUnknownOperand = unknownFlag(dynamicIndex) : bool",
        "absorptionOrUnknownOperand = unknownFlag(dynamicIndex) : bool",
        "absorptionAndUnknownCompoundRightInner = base : bool",
        "absorptionOrUnknownCompoundRightInner = base : bool",
        "absorptionAndUnknownOperandRightInner = unknownFlag(dynamicIndex) : bool",
        "absorptionOrUnknownOperandRightInner = unknownFlag(dynamicIndex) : bool",
    ):
        require_absent(hir, original)

    trace_text = run_cglc(
        cglc, root, "dump-ir", str(FIXTURE), "--stage", "hir-pass-trace"
    )
    trace = json.loads(trace_text)
    simplify = next(
        (
            pass_record
            for pass_record in trace["passes"]
            if pass_record["name"] == "hir.optimize.simplify-algebraic"
        ),
        None,
    )
    if simplify is None:
        raise SystemExit("HIR pass trace omitted hir.optimize.simplify-algebraic")
    if not simplify.get("changed"):
        raise SystemExit(
            "boolean absorption fixture did not mark simplify-algebraic changed"
        )
    if simplify.get("status") != "completed":
        raise SystemExit("simplify-algebraic pass did not complete")
    stats = simplify.get("moduleStats", {})
    before = stats.get("before", {}).get("expressionCount", 0)
    after = stats.get("after", {}).get("expressionCount", 0)
    if after >= before:
        raise SystemExit(
            "boolean absorption cleanup should reduce expressionCount in pass trace"
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
