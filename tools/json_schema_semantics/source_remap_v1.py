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


def span_identity(span):
    return (
        span["file"],
        span["line"],
        span["column"],
        span["offset"],
        span["length"],
        span["endLine"],
        span["endColumn"],
        span["endOffset"],
    )


def spans_overlap(left, right):
    if left["file"] != right["file"]:
        return False
    return left["offset"] < right["endOffset"] and right["offset"] < left["endOffset"]


def generated_span_order_drift(previous, current):
    if previous["file"] != current["file"]:
        return False
    return current["offset"] < previous["endOffset"]


def validate_semantics(instance):
    errors = []
    generated_file = instance["generatedFile"]
    if not is_stable_relative_path(generated_file):
        errors.append("$.generatedFile: expected stable relative POSIX source path")

    seen_mappings = set()
    generated_spans = []
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
        for prior_index, prior_generated in generated_spans:
            if spans_overlap(prior_generated, generated):
                errors.append(
                    f"{mapping_path}.generated: overlaps $.mappings[{prior_index}].generated"
                )
                break
        if generated_spans:
            previous_index, previous_generated = generated_spans[-1]
            if generated_span_order_drift(previous_generated, generated):
                errors.append(
                    f"{mapping_path}.generated.offset: expected >= "
                    f"$.mappings[{previous_index}].generated.endOffset"
                )
        generated_spans.append((index, generated))
        mapping_identity = (span_identity(generated), span_identity(original))
        if mapping_identity in seen_mappings:
            errors.append(f"{mapping_path}: duplicate generated/original span pair")
        seen_mappings.add(mapping_identity)
    return errors
