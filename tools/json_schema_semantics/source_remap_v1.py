"""Semantic checks for source-remap-v1.schema.json."""

from .common import validate_source_location_span


def is_stable_relative_path(path):
    if path == "":
        return False
    if "\\" in path:
        return False
    if path.startswith("/") or (
        len(path) >= 2 and path[0].isalpha() and path[1] == ":"
    ):
        return False
    return all(segment not in ("", ".", "..") for segment in path.split("/"))


def validate_source_span(errors, path, span):
    if not is_stable_relative_path(span["file"]):
        errors.append(f"{path}.file: expected stable relative POSIX source path")
    validate_source_location_span(errors, path, span)
    if span["length"] <= 0:
        errors.append(f"{path}.length: expected > 0")
    if (
        span["length"] > 0
        and span["endLine"] == span["line"]
        and span["endColumn"] <= span["column"]
    ):
        errors.append(f"{path}.endColumn: expected > column for same-line span")


def validate_semantics(instance):
    errors = []
    generated_file = instance["generatedFile"]
    if not is_stable_relative_path(generated_file):
        errors.append("$.generatedFile: expected stable relative POSIX source path")

    for index, mapping in enumerate(instance["mappings"]):
        mapping_path = f"$.mappings[{index}]"
        generated = mapping["generated"]
        original = mapping["original"]
        validate_source_span(errors, f"{mapping_path}.generated", generated)
        validate_source_span(errors, f"{mapping_path}.original", original)
        if generated["file"] != generated_file:
            errors.append(
                f"{mapping_path}.generated.file: expected to match $.generatedFile"
            )
    return errors
