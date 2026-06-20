#!/usr/bin/env python3
"""Validate JSON with the small JSON Schema subset used by compiler fixtures."""

import argparse
import json
import re
import sys
from pathlib import Path

from json_schema_semantics import validate_semantics


class SchemaError(Exception):
    pass


def load_json(path):
    with Path(path).open("r", encoding="utf-8") as handle:
        return json.load(handle)


def type_name(value):
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, int):
        return "integer"
    if isinstance(value, float):
        return "number"
    if isinstance(value, str):
        return "string"
    if isinstance(value, list):
        return "array"
    if isinstance(value, dict):
        return "object"
    return type(value).__name__


def type_matches(value, expected):
    if expected == "null":
        return value is None
    if expected == "boolean":
        return isinstance(value, bool)
    if expected == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if expected == "number":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    if expected == "string":
        return isinstance(value, str)
    if expected == "array":
        return isinstance(value, list)
    if expected == "object":
        return isinstance(value, dict)
    return False


def resolve_ref(schema_root, ref):
    prefix = "#/$defs/"
    if not isinstance(ref, str) or not ref.startswith(prefix):
        raise SchemaError(f"unsupported $ref: {ref!r}")
    current = schema_root.get("$defs", {})
    for part in ref[len(prefix) :].split("/"):
        if not isinstance(current, dict) or part not in current:
            raise SchemaError(f"unresolved $ref: {ref!r}")
        current = current[part]
    return current


def format_one_of_errors(errors):
    joined = "; ".join(errors[:3])
    if len(errors) > 3:
        joined += f"; ... {len(errors) - 3} more"
    return joined


def validate(instance, schema, schema_root, path="$"):
    if "$ref" in schema:
        validate(instance, resolve_ref(schema_root, schema["$ref"]), schema_root, path)
        return

    if "anyOf" in schema:
        errors = []
        for candidate in schema["anyOf"]:
            try:
                validate(instance, candidate, schema_root, path)
                return
            except SchemaError as exc:
                errors.append(str(exc))
        joined = "; ".join(errors[:3])
        raise SchemaError(f"{path}: did not match any allowed schema: {joined}")

    if "not" in schema:
        try:
            validate(instance, schema["not"], schema_root, path)
        except SchemaError:
            pass
        else:
            raise SchemaError(f"{path}: matched disallowed schema")

    if "oneOf" in schema:
        matches = 0
        errors = []
        for index, candidate in enumerate(schema["oneOf"]):
            try:
                validate(instance, candidate, schema_root, path)
                matches += 1
            except SchemaError as exc:
                errors.append(f"candidate {index}: {exc}")
        if matches != 1:
            if matches == 0:
                detail = format_one_of_errors(errors)
                raise SchemaError(
                    f"{path}: expected exactly one matching schema, got 0: {detail}"
                )
            raise SchemaError(
                f"{path}: expected exactly one matching schema, got {matches}"
            )

    if "const" in schema and instance != schema["const"]:
        raise SchemaError(
            f"{path}: expected constant {schema['const']!r}, got {instance!r}"
        )

    if "enum" in schema and instance not in schema["enum"]:
        raise SchemaError(
            f"{path}: expected one of {schema['enum']!r}, got {instance!r}"
        )

    if "type" in schema:
        expected_types = schema["type"]
        if isinstance(expected_types, str):
            expected_types = [expected_types]
        if not any(type_matches(instance, expected) for expected in expected_types):
            raise SchemaError(
                f"{path}: expected type {expected_types!r}, got {type_name(instance)}"
            )

    if isinstance(instance, (int, float)) and not isinstance(instance, bool):
        if "minimum" in schema and instance < schema["minimum"]:
            raise SchemaError(
                f"{path}: expected value >= {schema['minimum']}, got {instance}"
            )

    if isinstance(instance, str):
        if "minLength" in schema and len(instance) < schema["minLength"]:
            raise SchemaError(
                f"{path}: expected string length >= {schema['minLength']}, got {len(instance)}"
            )
        if "pattern" in schema and re.search(schema["pattern"], instance) is None:
            raise SchemaError(
                f"{path}: expected string to match pattern {schema['pattern']!r}, got {instance!r}"
            )

    if isinstance(instance, dict):
        required = schema.get("required", [])
        for key in required:
            if key not in instance:
                raise SchemaError(f"{path}: missing required property {key!r}")

        properties = schema.get("properties", {})
        for key, value in instance.items():
            child_path = f"{path}.{key}"
            if key in properties:
                validate(value, properties[key], schema_root, child_path)
            elif schema.get("additionalProperties", True) is False:
                raise SchemaError(f"{path}: unexpected property {key!r}")

    if isinstance(instance, list):
        if "minItems" in schema and len(instance) < schema["minItems"]:
            raise SchemaError(
                f"{path}: expected at least {schema['minItems']} items, got {len(instance)}"
            )
        if schema.get("uniqueItems") is True:
            for index, value in enumerate(instance):
                for previous_index, previous_value in enumerate(instance[:index]):
                    if value == previous_value:
                        raise SchemaError(
                            f"{path}: expected unique items, duplicate at index "
                            f"{index} matches index {previous_index}"
                        )
        if "items" in schema:
            item_schema = schema["items"]
            for index, value in enumerate(instance):
                validate(value, item_schema, schema_root, f"{path}[{index}]")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--schema", required=True)
    parser.add_argument("--instance", required=True)
    args = parser.parse_args()

    try:
        schema = load_json(args.schema)
        instance = load_json(args.instance)
        validate(instance, schema, schema)
        semantic_errors = validate_semantics(instance, schema)
        if semantic_errors:
            raise SchemaError("; ".join(semantic_errors[:10]))
    except (OSError, json.JSONDecodeError, SchemaError) as exc:
        print(f"schema validation failed: {exc}", file=sys.stderr)
        return 1

    print(f"validated {args.instance} against {args.schema}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
