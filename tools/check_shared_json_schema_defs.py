#!/usr/bin/env python3
"""Check public schemas keep bundled copies of private shared definitions."""

import argparse
import json
import sys
from pathlib import Path


SHARED_DEFINITION_COPIES = [
    {
        "shared": "source-map-locations-v1.json",
        "definitions": [
            "nonNegativeInteger",
            "sourceLocation",
        ],
        "schemas": [
            "package-inspect-v1.schema.json",
        ],
    },
    {
        "shared": "source-map-locations-v1.json",
        "definitions": [
            "nonNegativeInteger",
            "sourceLocation",
            "expressionSourceLocation",
            "typeSourceLocation",
            "hirSourceLocations",
        ],
        "schemas": [
            "debug-metadata-v10.schema.json",
            "hir-source-map-v6.schema.json",
        ],
    },
    {
        "shared": "source-map-locations-v2.json",
        "definitions": [
            "nonNegativeInteger",
            "sourceLocation",
            "expressionSourceLocation",
            "typeSourceLocation",
            "statementSourceLocation",
            "hirSourceLocations",
        ],
        "schemas": [
            "debug-metadata-v11.schema.json",
            "hir-source-map-v7.schema.json",
        ],
    },
    {
        "shared": "source-map-locations-v3.json",
        "definitions": [
            "nonNegativeInteger",
            "sourceLocation",
            "expressionSourceLocation",
            "typeSourceLocation",
            "statementSourceLocation",
            "resourceSourceLocation",
            "hirSourceLocations",
        ],
        "schemas": [
            "debug-metadata-v12.schema.json",
            "hir-source-map-v8.schema.json",
        ],
    },
    {
        "shared": "target-record-v1.json",
        "definitions": [
            "targetName",
        ],
        "schemas": [
            "doctor-v1.schema.json",
            "manifest-v1.schema.json",
            "package-inspect-v1.schema.json",
            "package-verify-v1.schema.json",
            "reflection-v1.schema.json",
            "target-capability-registry-v1.schema.json",
            "target-explanation-v1.schema.json",
        ],
    },
    {
        "shared": "target-record-v1.json",
        "definitions": [
            "capabilityList",
            "targetRecord",
        ],
        "schemas": [
            "doctor-v1.schema.json",
            "target-explanation-v1.schema.json",
        ],
    },
]


def load_json(path):
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def definition(schema, path, name):
    try:
        return schema["$defs"][name]
    except KeyError as exc:
        raise KeyError(f"{path}: missing $defs.{name}") from exc


def check_group(root, group):
    shared_path = root / "docs" / "schema-defs" / group["shared"]
    shared = load_json(shared_path)
    errors = []
    checked = 0

    for schema_name in group["schemas"]:
        schema_path = root / "docs" / "schemas" / schema_name
        schema = load_json(schema_path)
        for name in group["definitions"]:
            try:
                expected = definition(shared, shared_path.relative_to(root), name)
                actual = definition(schema, schema_path.relative_to(root), name)
            except KeyError as exc:
                errors.append(str(exc))
                continue
            checked += 1
            if actual != expected:
                errors.append(
                    f"{schema_path.relative_to(root)}: $defs.{name} differs from "
                    f"{shared_path.relative_to(root)}"
                )

    return checked, errors


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--root",
        default=".",
        help="CrossGL-Compiler repository root",
    )
    args = parser.parse_args()

    root = Path(args.root).resolve()
    checked = 0
    errors = []
    for group in SHARED_DEFINITION_COPIES:
        try:
            group_checked, group_errors = check_group(root, group)
        except (OSError, json.JSONDecodeError) as exc:
            errors.append(str(exc))
            continue
        checked += group_checked
        errors.extend(group_errors)

    if errors:
        for error in errors:
            print(f"shared schema definition check failed: {error}", file=sys.stderr)
        return 1

    print(f"validated {checked} shared JSON schema definition copies")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
