"""Semantic checks for backend-source-map-v1.schema.json."""

import re

from .common import add_length_count_error
from .common import validate_source_location_span


SOURCE_REMAP_GRANULARITIES = frozenset({"file", "line", "statement", "token"})
SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")
BACKEND_SPAN_DETAIL_FIELDS = frozenset(
    {"startColumn", "offset", "length", "endColumn", "endOffset"}
)
TARGET_BACKEND_LANGUAGES = {
    "directx": "hlsl",
    "metal": "msl",
    "opengl": "glsl",
    "vulkan": "spvasm",
}


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
    present_span_detail_fields = BACKEND_SPAN_DETAIL_FIELDS.intersection(span)
    if (
        present_span_detail_fields
        and present_span_detail_fields != BACKEND_SPAN_DETAIL_FIELDS
    ):
        missing = sorted(BACKEND_SPAN_DETAIL_FIELDS.difference(span))
        errors.append(
            f"{path}: backend byte span fields must be emitted together; "
            f"missing {missing!r}"
        )
    if present_span_detail_fields == BACKEND_SPAN_DETAIL_FIELDS:
        if span["endOffset"] != span["offset"] + span["length"]:
            errors.append(f"{path}.endOffset: expected offset + length")
        if (
            span["endLine"] == span["startLine"]
            and span["endColumn"] <= span["startColumn"]
        ):
            errors.append(
                f"{path}.endColumn: expected > startColumn for same-line span"
            )
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


def validate_source_remap(errors, source_remap):
    if source_remap is None:
        return

    sha256 = source_remap["sha256"]
    if sha256["algorithm"] != "sha256":
        errors.append("$.sourceRemap.sha256.algorithm: expected 'sha256'")
    if not SHA256_PATTERN.match(sha256["value"]):
        errors.append(
            "$.sourceRemap.sha256.value: expected 64 lowercase hexadecimal sha256"
        )

    mapping_granularity = source_remap.get("mappingGranularity")
    if (
        mapping_granularity is not None
        and mapping_granularity not in SOURCE_REMAP_GRANULARITIES
    ):
        errors.append(
            "$.sourceRemap.mappingGranularity: expected file, line, statement, or token"
        )

    for field_name in ("sourceBackend", "variant"):
        value = source_remap.get(field_name)
        if value is not None and value.strip() == "":
            errors.append(f"$.sourceRemap.{field_name}: expected non-empty string")


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
    expected_backend_language = TARGET_BACKEND_LANGUAGES.get(instance["target"])
    if (
        expected_backend_language is not None
        and backend["language"] != expected_backend_language
    ):
        errors.append(
            "$.backend.language: expected "
            f"{expected_backend_language!r} for {instance['target']} target"
        )
    if instance["mappingGranularity"] != "statement":
        errors.append("$.mappingGranularity: expected 'statement'")
    if instance["targetBackend"] != backend["language"]:
        errors.append(
            "$.targetBackend: expected to match $.backend.language "
            f"{backend['language']!r}, got {instance['targetBackend']!r}"
        )
    if "sourceRemap" in instance:
        validate_source_remap(errors, instance["sourceRemap"])
    has_source_remap = instance.get("sourceRemap") is not None
    source_remap_generated_file = None
    if isinstance(instance.get("sourceRemap"), dict):
        source_remap_generated_file = instance["sourceRemap"].get("generatedFile")

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
        if (
            has_source_remap
            and isinstance(source_remap_generated_file, str)
            and mapping["location"]["file"] != source_remap_generated_file
        ):
            errors.append(
                f"{mapping_path}.location.file: expected to match "
                f"$.sourceRemap.generatedFile {source_remap_generated_file!r}"
            )
        if "originalLocation" in mapping:
            validate_source_location_range(
                errors,
                f"{mapping_path}.originalLocation",
                mapping["originalLocation"],
            )
        elif has_source_remap:
            errors.append(
                f"{mapping_path}.originalLocation: required when $.sourceRemap is non-null"
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
