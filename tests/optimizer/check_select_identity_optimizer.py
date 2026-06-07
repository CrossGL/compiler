#!/usr/bin/env python3
"""Check target-independent HIR select identity cleanup evidence."""

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
    fixture = str(FIXTURE)

    hir = run_cglc(cglc, root, "dump-ir", fixture, "--stage", "hir")
    require_contains(hir, "decl int selectSameInt = dynamicIndex : int")
    require_contains(hir, "decl bool selectSameBool = base : bool")
    require_contains(
        hir,
        "decl int selectSameUnknownCondition = "
        "unknownFlag(dynamicIndex) ? dynamicIndex : dynamicIndex : int",
    )
    require_absent(hir, "selectSameInt = base ? dynamicIndex : dynamicIndex")
    require_absent(hir, "selectSameBool = (dynamicIndex > 6) ? base : base")

    trace_text = run_cglc(cglc, root, "dump-ir", fixture, "--stage", "hir-pass-trace")
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
            "same-arm select fixture did not mark simplify-algebraic changed"
        )
    if simplify.get("status") != "completed":
        raise SystemExit("simplify-algebraic pass did not complete")
    stats = simplify.get("moduleStats", {})
    before = stats.get("before", {}).get("expressionCount", 0)
    after = stats.get("after", {}).get("expressionCount", 0)
    if after >= before:
        raise SystemExit(
            "same-arm select cleanup should reduce expressionCount in pass trace"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
