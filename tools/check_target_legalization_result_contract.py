#!/usr/bin/env python3
"""Check target-legalization-result-v0 contract fixtures."""

import argparse
import subprocess
import sys
from pathlib import Path


def run_validator(root, validator, schema_path, instance_path):
    return subprocess.run(
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


def fixture_paths(root, subdir):
    fixture_dir = root / "tests" / "target-legalization-result-contract" / subdir
    if not fixture_dir.exists():
        raise ValueError(f"missing {fixture_dir.relative_to(root)}")
    return sorted(fixture_dir.glob("*.json"))


def check_valid_fixtures(root, validator, schema_path):
    errors = []
    valid_paths = fixture_paths(root, "valid")
    if not valid_paths:
        errors.append("tests/target-legalization-result-contract/valid has no fixtures")
        return errors, 0

    for instance_path in valid_paths:
        result = run_validator(root, validator, schema_path, instance_path)
        if result.returncode != 0:
            output = (result.stderr + result.stdout).strip()
            errors.append(
                f"{instance_path.relative_to(root)}: expected validation success; "
                f"got {output!r}"
            )
    return errors, len(valid_paths)


def check_invalid_fixtures(root, validator, schema_path):
    errors = []
    invalid_paths = fixture_paths(root, "invalid")
    if not invalid_paths:
        errors.append(
            "tests/target-legalization-result-contract/invalid has no fixtures"
        )
        return errors, 0

    for instance_path in invalid_paths:
        expected_path = instance_path.with_suffix(".expected.txt")
        if not expected_path.exists():
            errors.append(
                f"{instance_path.relative_to(root)}: missing expected error "
                f"{expected_path.name}"
            )
            continue
        expected = expected_path.read_text(encoding="utf-8").strip()
        if not expected:
            errors.append(f"{expected_path.relative_to(root)}: empty expected error")
            continue

        result = run_validator(root, validator, schema_path, instance_path)
        output = result.stderr + result.stdout
        if result.returncode == 0:
            errors.append(
                f"{instance_path.relative_to(root)}: expected validation failure"
            )
        if "schema validation failed:" not in result.stderr:
            errors.append(
                f"{instance_path.relative_to(root)}: missing validator failure prefix"
            )
        if expected not in output:
            errors.append(
                f"{instance_path.relative_to(root)}: expected error substring "
                f"{expected!r}; got {output.strip()!r}"
            )
    return errors, len(invalid_paths)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=".", help="CrossGL-Compiler repository root")
    args = parser.parse_args()

    root = Path(args.root).resolve()
    schema_path = (
        root / "docs" / "schemas" / "target-legalization-result-v0.schema.json"
    )
    validator = root / "tools" / "validate_json_schema.py"

    errors = []
    try:
        valid_errors, valid_count = check_valid_fixtures(root, validator, schema_path)
        invalid_errors, invalid_count = check_invalid_fixtures(
            root, validator, schema_path
        )
    except (OSError, ValueError) as exc:
        print(
            f"target legalization result contract check failed: {exc}", file=sys.stderr
        )
        return 1

    errors.extend(valid_errors)
    errors.extend(invalid_errors)
    if errors:
        for error in errors:
            print(
                f"target legalization result contract check failed: {error}",
                file=sys.stderr,
            )
        return 1

    print(
        "validated "
        f"{valid_count} valid and {invalid_count} invalid "
        "target-legalization-result contract fixtures"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
