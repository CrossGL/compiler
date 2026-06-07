#!/usr/bin/env python3
"""Exercise CrossTL language spec extractor CLI guardrails."""

from __future__ import annotations

import subprocess
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def run_command(
    args: list[str], expect_success: bool = True
) -> subprocess.CompletedProcess[str]:
    process = subprocess.run(
        args,
        cwd=ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if (process.returncode == 0) == expect_success:
        return process
    print("$ " + " ".join(args), file=sys.stderr)
    if process.stdout:
        print(process.stdout, file=sys.stderr)
    if process.stderr:
        print(process.stderr, file=sys.stderr)
    raise SystemExit(process.returncode or 1)


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="crossgl-crosstl-extractor-") as tmp:
        wrong_root = Path(tmp) / "not-translator"
        wrong_root.mkdir()
        failed = run_command(
            [
                sys.executable,
                "tools/extract_crosstl_language_spec.py",
                "--root",
                ".",
                "--translator-root",
                str(wrong_root),
                "--check",
            ],
            expect_success=False,
        )
    stderr = failed.stderr
    expected_fragments = (
        "missing required CrossTL frontend authority files",
        "crosstl/translator/lexer.py",
        "crosstl/translator/parser.py",
        "crosstl/translator/ast.py",
        "crosstl/translator/validation.py",
        "crosstl/translator/language_spec.py",
    )
    for fragment in expected_fragments:
        if fragment not in stderr:
            raise SystemExit(
                "extractor did not report missing translator root fragment: " + fragment
            )

    print("validated CrossTL language spec extractor CLI guardrails")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
