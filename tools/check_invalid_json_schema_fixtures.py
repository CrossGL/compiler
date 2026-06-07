#!/usr/bin/env python3
"""Check committed invalid JSON schema fixtures fail with expected messages."""

import argparse
import subprocess
import sys
from pathlib import Path

from fixture_parallelism import run_fixture_tasks


def positive_jobs(value):
    try:
        jobs = int(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("--jobs must be an integer") from exc
    if jobs < 1:
        raise argparse.ArgumentTypeError("--jobs must be at least 1")
    return jobs


def fixture_cases(root):
    fixture_root = root / "tests" / "schema-failures"
    if not fixture_root.exists():
        raise ValueError(f"missing {fixture_root.relative_to(root)}")

    cases = []
    errors = []
    for schema_dir in sorted(fixture_root.iterdir()):
        if not schema_dir.is_dir():
            continue
        local_schema_path = schema_dir / "schema.schema.json"
        schema_path = local_schema_path
        if not schema_path.exists():
            schema_path = root / "docs" / "schemas" / f"{schema_dir.name}.schema.json"
        if not schema_path.exists():
            errors.append(
                f"{schema_dir.relative_to(root)}: missing schema "
                f"{schema_path.relative_to(root)}"
            )
            continue
        for instance_path in sorted(schema_dir.glob("*.json")):
            if instance_path == local_schema_path:
                continue
            expected_path = instance_path.with_suffix(".expected.txt")
            if not expected_path.exists():
                errors.append(
                    f"{instance_path.relative_to(root)}: missing expected error "
                    f"{expected_path.name}"
                )
                continue
            expected = expected_path.read_text(encoding="utf-8").strip()
            if not expected:
                errors.append(
                    f"{expected_path.relative_to(root)}: empty expected error"
                )
                continue
            cases.append((schema_path, instance_path, expected))

    if errors:
        raise ValueError("\n".join(errors))
    if not cases:
        raise ValueError(f"{fixture_root.relative_to(root)} contains no fixtures")
    return cases


def run_case(root, validator, schema_path, instance_path, expected):
    result = subprocess.run(
        [
            sys.executable,
            str(validator),
            "--schema",
            str(schema_path),
            "--instance",
            str(instance_path),
        ],
        cwd=str(root),
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    output = result.stderr + result.stdout
    relative_instance = instance_path.relative_to(root)
    errors = []
    if result.returncode == 0:
        errors.append(f"{relative_instance}: expected validation failure")
    if "schema validation failed:" not in result.stderr:
        errors.append(f"{relative_instance}: missing validator failure prefix")
    if expected not in output:
        errors.append(
            f"{relative_instance}: expected error substring {expected!r}; "
            f"got {output.strip()!r}"
        )
    return errors


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--root",
        default=".",
        help="CrossGL-Compiler repository root",
    )
    parser.add_argument(
        "--jobs",
        type=positive_jobs,
        help=(
            "Run fixture checks with this many workers; defaults to "
            "CROSSGL_CI_JOBS or 1."
        ),
    )
    args = parser.parse_args()

    root = Path(args.root).resolve()
    validator = root / "tools" / "validate_json_schema.py"
    errors = []

    try:
        cases = fixture_cases(root)
    except (OSError, ValueError) as exc:
        print(f"invalid schema fixture check failed: {exc}", file=sys.stderr)
        return 1

    def check_case(case):
        schema_path, instance_path, expected = case
        return run_case(root, validator, schema_path, instance_path, expected)

    for case_errors in run_fixture_tasks(cases, check_case, jobs=args.jobs):
        errors.extend(case_errors)

    if errors:
        for error in errors:
            print(f"invalid schema fixture check failed: {error}", file=sys.stderr)
        return 1

    print(f"validated {len(cases)} invalid JSON schema fixtures")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
