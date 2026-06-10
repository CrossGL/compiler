"""Semantic checks for backend-source-map-v1.schema.json."""

from .common import add_length_count_error
from .common import validate_source_location_span


def source_span_identity(span):
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


def backend_span_identity(span):
    return (
        span["startLine"],
        span["endLine"],
    )


def backend_spans_overlap(left, right):
    return (
        left["startLine"] <= right["endLine"] and right["startLine"] <= left["endLine"]
    )


def validate_source_location_range(errors, path, location):
    if "\\" in location["file"]:
        errors.append(f"{path}.file: expected normalized '/' path separators")
    validate_source_location_span(errors, path, location)
    if location["length"] <= 0:
        errors.append(f"{path}.length: expected > 0")
    if (
        location["length"] > 0
        and location["endLine"] == location["line"]
        and location["endColumn"] <= location["column"]
    ):
        errors.append(f"{path}.endColumn: expected > column for same-line span")


def validate_backend_span(errors, path, span, line_count):
    if span["endLine"] < span["startLine"]:
        errors.append(f"{path}.endLine: expected >= startLine")
    if line_count == 0:
        errors.append(f"{path}: backend lineCount 0 cannot contain mapped spans")
        return
    if span["startLine"] > line_count:
        errors.append(
            f"{path}.startLine: expected <= $.backend.lineCount {line_count!r}, "
            f"got {span['startLine']!r}"
        )
    if span["endLine"] > line_count:
        errors.append(
            f"{path}.endLine: expected <= $.backend.lineCount {line_count!r}, "
            f"got {span['endLine']!r}"
        )


def validate_mapping_context(errors, path, mapping):
    if mapping["entryPoint"] and not mapping["stage"]:
        errors.append(f"{path}.stage: expected non-empty when entryPoint is non-empty")
    if mapping["stage"] and not mapping["entryPoint"]:
        errors.append(f"{path}.entryPoint: expected non-empty when stage is non-empty")
    if not mapping["function"]:
        errors.append(f"{path}.function: expected non-empty mapped function")


def validate_semantics(instance):
    errors = []
    mappings = instance["mappings"]
    backend = instance["backend"]
    add_length_count_error(
        errors,
        "$.mappingCount",
        instance["mappingCount"],
        mappings,
        "$.mappings length",
    )
    if instance["target"] == "directx" and backend["language"] != "hlsl":
        errors.append("$.backend.language: expected 'hlsl' for directx target")

    line_count = backend["lineCount"]
    backend_spans = []
    seen_mappings = set()
    for index, mapping in enumerate(mappings):
        mapping_path = f"$.mappings[{index}]"
        if mapping["index"] != index:
            errors.append(
                f"{mapping_path}.index: expected mapping array index {index!r}, "
                f"got {mapping['index']!r}"
            )
        validate_mapping_context(errors, mapping_path, mapping)
        validate_backend_span(
            errors, f"{mapping_path}.backend", mapping["backend"], line_count
        )
        validate_source_location_range(
            errors, f"{mapping_path}.location", mapping["location"]
        )
        if "originalLocation" in mapping:
            validate_source_location_range(
                errors,
                f"{mapping_path}.originalLocation",
                mapping["originalLocation"],
            )

        if backend_spans:
            prior_index, prior_backend = backend_spans[-1]
            if mapping["backend"]["startLine"] <= prior_backend["endLine"]:
                errors.append(
                    f"{mapping_path}.backend.startLine: expected "
                    f"after $.mappings[{prior_index}].backend"
                )

        for prior_index, prior_backend in backend_spans:
            if backend_spans_overlap(prior_backend, mapping["backend"]):
                errors.append(
                    f"{mapping_path}.backend: overlaps "
                    f"$.mappings[{prior_index}].backend"
                )
                break
        backend_spans.append((index, mapping["backend"]))

        mapping_identity = (
            backend_span_identity(mapping["backend"]),
            source_span_identity(mapping["location"]),
            source_span_identity(mapping["originalLocation"])
            if "originalLocation" in mapping
            else None,
        )
        if mapping_identity in seen_mappings:
            errors.append(
                f"{mapping_path}: duplicate backend/location/original span tuple"
            )
        seen_mappings.add(mapping_identity)

    return errors
