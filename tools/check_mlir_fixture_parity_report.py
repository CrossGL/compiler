#!/usr/bin/env python3
"""Validate report-only parity fields for admitted MLIR experiment fixtures.

By default this checker is intentionally toolchain-free and validates inventory
metadata only. The optional HIR dump parity mode invokes cglc against admitted
fixtures to compare current C++ HIR facts with the inventory; it does not invoke
MLIR, lower HIR, or inspect production package outputs.
"""

from __future__ import annotations

import argparse
import copy
import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any


INVENTORY_PATH = Path("experimental/mlir/fixture_inventory.json")
INVENTORY_KIND = "crossgl-mlir-experiment-fixture-inventory"
PARITY_REQUIREMENT_KEY = "parityRequirements"
REPORT_FIELD_KEY = "parityReportFields"
LOWERING_EVIDENCE_KEY = "loweringEvidence"
REQUIRED_PARITY_REQUIREMENT_SECTIONS = (
    "sourceLocations",
    "typeFacts",
    "entryPoint",
    "resources",
    "targetIndependentResourceMetadata",
    "diagnosticsProvenance",
    "sourceMapDebugPreservation",
)
REQUIRED_REPORT_SECTIONS = (
    "sourceFile",
    "entryPoint",
    "entryPointIdentity",
    "localSize",
    "workgroupSize",
    "resourceBindings",
    "targetIndependentResourceMetadata",
    "typeFacts",
    "diagnosticsProvenance",
    "sourceMapDebugPreservation",
    "controlFlowSlice",
    "blockedFamilyRationale",
)
ENTRY_POINT_IDENTITY_SOURCE_FACTS = (
    "shader_module",
    "compute_stage",
    "entry_point",
)
ENTRY_POINT_IDENTITY_TYPE_FACTS = ("void_entry_point",)
WORKGROUP_SOURCE_FACT = "layout_local_size"
BLOCKED_FAMILY_REPORT_FIELDS = (
    "unsupportedHirFamilies[].id",
    "unsupportedHirFamilies[].reason",
)
REQUIRED_FACT_CATEGORIES = (
    "sourceLocations",
    "types",
    "resources",
    "targetIndependentResourceMetadata",
    "diagnosticsProvenance",
    "sourceMapDebugPreservation",
)
SOURCE_MAP_DEBUG_ARTIFACT_FIELDS = (
    "manifest.artifacts.debugMetadata",
    "manifest.artifacts.hirSourceMap",
    "ir/debug-metadata.json",
    "ir/hir-source-map.json",
)
SOURCE_MAP_DEBUG_SCHEMA_FIELDS = (
    "debugMetadata.schemaVersion=11",
    "hirSourceMap.schemaVersion=7",
)
SOURCE_MAP_DEBUG_LOCATION_FIELDS = (
    "debugMetadata.hirSourceLocations",
    "hirSourceMap.hirSourceLocations",
    "hirSourceMap.categoryCounts",
    "hirSourceMap.filters.activeCount=0",
    "hirSourceMap.pagination.activeCount=0",
    "hirSourceMap.records.enabled=false",
)
RESOURCE_FACT_COLLECTIONS = (
    "descriptors",
    "storageBuffers",
    "storageImages",
    "textures",
    "samplers",
)
RESOURCE_METADATA_COLLECTION = "targetIndependentResourceMetadata"
RESOURCE_FACT_LIST_FIELDS = (*RESOURCE_FACT_COLLECTIONS, RESOURCE_METADATA_COLLECTION)
RESOURCE_ITEM_FIELDS = {
    "descriptors": (
        "resourceFacts.descriptors[].stage",
        "resourceFacts.descriptors[].name",
        "resourceFacts.descriptors[].kind",
        "resourceFacts.descriptors[].set",
        "resourceFacts.descriptors[].binding",
    ),
    "storageBuffers": (
        "resourceFacts.storageBuffers[].name",
        "resourceFacts.storageBuffers[].type",
        "resourceFacts.storageBuffers[].elementType",
        "resourceFacts.storageBuffers[].addressSpace",
        "resourceFacts.storageBuffers[].writeAccess",
    ),
    "storageImages": (
        "resourceFacts.storageImages[].name",
        "resourceFacts.storageImages[].type",
        "resourceFacts.storageImages[].elementType",
        "resourceFacts.storageImages[].format",
        "resourceFacts.storageImages[].dimension",
        "resourceFacts.storageImages[].arrayed",
        "resourceFacts.storageImages[].access",
        "resourceFacts.storageImages[].set",
        "resourceFacts.storageImages[].binding",
    ),
    "textures": (
        "resourceFacts.textures[].name",
        "resourceFacts.textures[].type",
        "resourceFacts.textures[].sampledType",
        "resourceFacts.textures[].dimension",
        "resourceFacts.textures[].arrayed",
        "resourceFacts.textures[].comparison",
        "resourceFacts.textures[].set",
        "resourceFacts.textures[].binding",
    ),
    "samplers": (
        "resourceFacts.samplers[].name",
        "resourceFacts.samplers[].type",
        "resourceFacts.samplers[].comparison",
        "resourceFacts.samplers[].set",
        "resourceFacts.samplers[].binding",
    ),
}
RESOURCE_ITEM_OPTIONAL_FIELDS = {
    "descriptors": (
        ("descriptorArray", "resourceFacts.descriptors[].descriptorArray"),
        ("arraySize", "resourceFacts.descriptors[].arraySize"),
        ("indexingMode", "resourceFacts.descriptors[].indexingMode"),
        (
            "fixedDescriptorIndices",
            "resourceFacts.descriptors[].fixedDescriptorIndices",
        ),
    ),
    "storageBuffers": (
        ("descriptorArray", "resourceFacts.storageBuffers[].descriptorArray"),
        ("arraySize", "resourceFacts.storageBuffers[].arraySize"),
        ("indexingMode", "resourceFacts.storageBuffers[].indexingMode"),
        (
            "fixedDescriptorIndices",
            "resourceFacts.storageBuffers[].fixedDescriptorIndices",
        ),
    ),
    "textures": (
        ("descriptorArray", "resourceFacts.textures[].descriptorArray"),
        ("arraySize", "resourceFacts.textures[].arraySize"),
        ("indexingMode", "resourceFacts.textures[].indexingMode"),
        ("fixedDescriptorIndices", "resourceFacts.textures[].fixedDescriptorIndices"),
    ),
    "samplers": (
        ("descriptorArray", "resourceFacts.samplers[].descriptorArray"),
        ("arraySize", "resourceFacts.samplers[].arraySize"),
        ("indexingMode", "resourceFacts.samplers[].indexingMode"),
        ("fixedDescriptorIndices", "resourceFacts.samplers[].fixedDescriptorIndices"),
    ),
    RESOURCE_METADATA_COLLECTION: (
        (
            "descriptorArray",
            "resourceFacts.targetIndependentResourceMetadata[].descriptorArray",
        ),
        ("arraySize", "resourceFacts.targetIndependentResourceMetadata[].arraySize"),
        (
            "indexingMode",
            "resourceFacts.targetIndependentResourceMetadata[].indexingMode",
        ),
        (
            "fixedDescriptorIndices",
            "resourceFacts.targetIndependentResourceMetadata[].fixedDescriptorIndices",
        ),
    ),
}
TARGET_INDEPENDENT_RESOURCE_METADATA_FIELDS = (
    "resourceFacts.targetIndependentResourceMetadata",
    "resourceFacts.targetIndependentResourceMetadata[].stage",
    "resourceFacts.targetIndependentResourceMetadata[].name",
    "resourceFacts.targetIndependentResourceMetadata[].kind",
    "resourceFacts.targetIndependentResourceMetadata[].sourceType",
    "resourceFacts.targetIndependentResourceMetadata[].elementType",
    "resourceFacts.targetIndependentResourceMetadata[].addressSpace",
    "resourceFacts.targetIndependentResourceMetadata[].access",
    "resourceFacts.targetIndependentResourceMetadata[].set",
    "resourceFacts.targetIndependentResourceMetadata[].binding",
    "resourceFacts.targetIndependentResourceMetadata[].targetIndependent",
)
RESOURCE_ITEM_REQUIRED_KEYS = {
    "descriptors": ("stage", "name", "kind", "set", "binding"),
    "storageBuffers": (
        "name",
        "type",
        "elementType",
        "addressSpace",
        "writeAccess",
    ),
    "storageImages": (
        "name",
        "type",
        "elementType",
        "format",
        "dimension",
        "arrayed",
        "access",
        "set",
        "binding",
    ),
    "textures": (
        "name",
        "type",
        "sampledType",
        "dimension",
        "arrayed",
        "comparison",
        "set",
        "binding",
    ),
    "samplers": ("name", "type", "comparison", "set", "binding"),
    "targetIndependentResourceMetadata": (
        "stage",
        "name",
        "kind",
        "sourceType",
        "elementType",
        "addressSpace",
        "access",
        "set",
        "binding",
        "targetIndependent",
    ),
}
RESOURCE_ITEM_OPTIONAL_KEYS = {
    collection: tuple(key for key, _ in fields)
    for collection, fields in RESOURCE_ITEM_OPTIONAL_FIELDS.items()
}
CONTROL_FLOW_FAMILY = "control_flow_and_statements"
CONTROL_FLOW_SOURCE_FACTS = (
    "if_statement",
    "then_block_assignment",
    "else_block_assignment",
    "return_statement",
)
CONTROL_FLOW_TYPE_FACTS = (
    "branch_condition_bool",
    "assignment_expression_result_types",
    "unary_expression_result_types",
)
LOWERING_EVIDENCE_SECTIONS = (
    "status",
    "entryPointIdentity",
    "sourceLocationExpectation",
    "resourceMode",
    "typeFacts",
    "controlFlowCategory",
)
LOWERING_EVIDENCE_STATUS = "report-only"
RESOURCE_MODE_EMPTY = "empty-resource-facts"
RESOURCE_MODE_STORAGE_BUFFER = "single-storage-buffer-binding"
RESOURCE_MODE_TEXTURE_SAMPLER = "sampled-texture-sampler-binding"
RESOURCE_MODE_STORAGE_IMAGE = "direct-storage-image-binding"
CONTROL_FLOW_CATEGORY_STRAIGHT_LINE = "straight-line"
CONTROL_FLOW_CATEGORY_STRUCTURED_IF_ELSE = "structured-if-else"
HIR_OPT_LEVEL_FOR_PARITY = "O0"


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def load_json(path: Path) -> Any:
    try:
        return json.loads(read_text(path))
    except json.JSONDecodeError as error:
        raise ValueError(f"invalid JSON: {error}") from error


def require_object(value: object, field: str, errors: list[str]) -> dict[str, Any]:
    if not isinstance(value, dict):
        errors.append(f"{field} must be an object")
        return {}
    return value


def require_string(value: object, field: str, errors: list[str]) -> str | None:
    if not isinstance(value, str) or not value:
        errors.append(f"{field} must be a non-empty string")
        return None
    return value


def require_string_list(
    value: object, field: str, errors: list[str], *, allow_empty: bool = False
) -> list[str]:
    if not isinstance(value, list) or (not allow_empty and not value):
        qualifier = "a list" if allow_empty else "a non-empty list"
        errors.append(f"{field} must be {qualifier}")
        return []
    result: list[str] = []
    for index, item in enumerate(value):
        if isinstance(item, str) and item:
            result.append(item)
        else:
            errors.append(f"{field}[{index}] must be a non-empty string")
    return result


def validate_relative_path(
    root: Path, value: object, field: str, errors: list[str]
) -> str | None:
    path_text = require_string(value, field, errors)
    if path_text is None:
        return None
    if "\\" in path_text:
        errors.append(f"{field} must use POSIX separators: {path_text!r}")
        return None
    path = Path(path_text)
    if path.is_absolute() or any(
        part in {"", ".", ".."} for part in path_text.split("/")
    ):
        errors.append(f"{field} must be repository-relative without dot segments")
        return None
    if not (root / path).exists():
        errors.append(f"{field} does not exist: {path_text}")
    return path_text


def require_unique(values: list[str], field: str, errors: list[str]) -> None:
    seen: set[str] = set()
    duplicates: set[str] = set()
    for value in values:
        if value in seen:
            duplicates.add(value)
        seen.add(value)
    if duplicates:
        errors.append(
            f"{field} must not contain duplicate entries: "
            f"{', '.join(sorted(duplicates))}"
        )


def require_parity_section(
    value: object,
    field: str,
    errors: list[str],
    *,
    allow_empty_fields: bool = False,
    allowed_keys: set[str] | None = None,
) -> tuple[dict[str, Any], list[str]]:
    section = require_object(value, field, errors)
    if not section:
        return section, []
    if section.get("required") is not True:
        errors.append(f"{field}.required must be true")
    if allowed_keys is not None:
        stale_keys = sorted(set(section) - allowed_keys)
        if stale_keys:
            errors.append(f"{field} has unknown key(s): {', '.join(stale_keys)}")
    fields = require_string_list(
        section.get("fields"),
        f"{field}.fields",
        errors,
        allow_empty=allow_empty_fields,
    )
    require_unique(fields, f"{field}.fields", errors)
    return section, fields


def compare_fields(
    actual: list[str], expected: list[str], field: str, errors: list[str]
) -> None:
    if actual != expected:
        errors.append(f"{field}.fields must be {expected!r}, got {actual!r}")


def expected_resource_binding_fields(resource_facts: dict[str, Any]) -> list[str]:
    fields: list[str] = []
    for collection in RESOURCE_FACT_COLLECTIONS:
        fields.append(f"resourceFacts.{collection}")
        value = resource_facts.get(collection)
        if isinstance(value, list) and value:
            fields.extend(RESOURCE_ITEM_FIELDS[collection])
            fields.extend(optional_resource_item_fields(collection, value))
    return fields


def expected_resource_requirement_fields(resource_facts: dict[str, Any]) -> list[str]:
    return [
        "resourceFacts.localSize",
        *expected_resource_binding_fields(resource_facts),
    ]


def expected_target_independent_resource_metadata_fields(
    resource_facts: dict[str, Any],
) -> list[str]:
    metadata = resource_facts.get(RESOURCE_METADATA_COLLECTION)
    if isinstance(metadata, list) and metadata:
        return [
            *TARGET_INDEPENDENT_RESOURCE_METADATA_FIELDS,
            *optional_resource_item_fields(RESOURCE_METADATA_COLLECTION, metadata),
        ]
    return [f"resourceFacts.{RESOURCE_METADATA_COLLECTION}"]


def optional_resource_item_fields(collection: str, records: list[Any]) -> list[str]:
    fields: list[str] = []
    for key, field in RESOURCE_ITEM_OPTIONAL_FIELDS.get(collection, ()):
        if any(isinstance(item, dict) and key in item for item in records):
            fields.append(field)
    return fields


def prefixed_fact_fields(prefix: str, facts: list[str]) -> list[str]:
    return [f"{prefix}.{fact}" for fact in facts]


def expected_entry_point_identity_fields() -> list[str]:
    return [
        "stage",
        "entryPoint",
        *prefixed_fact_fields(
            "sourceLocationFacts", list(ENTRY_POINT_IDENTITY_SOURCE_FACTS)
        ),
        *prefixed_fact_fields("typeFacts", list(ENTRY_POINT_IDENTITY_TYPE_FACTS)),
    ]


def expected_workgroup_size_fields() -> list[str]:
    return ["resourceFacts.localSize", f"sourceLocationFacts.{WORKGROUP_SOURCE_FACT}"]


def expected_type_fact_fields(type_facts: list[str]) -> list[str]:
    return prefixed_fact_fields("typeFacts", type_facts)


def expected_diagnostics_provenance_fields(
    source_facts: list[str], type_facts: list[str]
) -> list[str]:
    return [
        "path",
        "stage",
        "entryPoint",
        *prefixed_fact_fields("sourceLocationFacts", source_facts),
        *expected_type_fact_fields(type_facts),
        "resourceFacts.localSize",
    ]


def expected_source_map_debug_preservation_fields(
    source_facts: list[str], type_facts: list[str]
) -> list[str]:
    return [
        "path",
        "stage",
        "entryPoint",
        *SOURCE_MAP_DEBUG_ARTIFACT_FIELDS,
        *SOURCE_MAP_DEBUG_SCHEMA_FIELDS,
        *SOURCE_MAP_DEBUG_LOCATION_FIELDS,
        *prefixed_fact_fields("sourceLocationFacts", source_facts),
        *expected_type_fact_fields(type_facts),
        "resourceFacts.localSize",
    ]


def expected_control_flow_report(
    families: set[str], source_facts: list[str], type_facts: list[str]
) -> tuple[str, list[str]]:
    if CONTROL_FLOW_FAMILY not in families:
        return "none", []

    fields: list[str] = []
    for fact in CONTROL_FLOW_SOURCE_FACTS:
        if fact in source_facts:
            fields.append(f"sourceLocationFacts.{fact}")
    for fact in CONTROL_FLOW_TYPE_FACTS:
        if fact in type_facts:
            fields.append(f"typeFacts.{fact}")
    return "structured-if-else", fields


def expected_resource_mode(resource_facts: dict[str, Any]) -> str:
    if resource_facts.get("storageImages"):
        return RESOURCE_MODE_STORAGE_IMAGE
    if resource_facts.get("textures") or resource_facts.get("samplers"):
        return RESOURCE_MODE_TEXTURE_SAMPLER
    has_resource_binding = any(
        resource_facts.get(collection) for collection in RESOURCE_FACT_COLLECTIONS
    )
    return RESOURCE_MODE_STORAGE_BUFFER if has_resource_binding else RESOURCE_MODE_EMPTY


def expected_control_flow_category(families: set[str]) -> str:
    if CONTROL_FLOW_FAMILY in families:
        return CONTROL_FLOW_CATEGORY_STRUCTURED_IF_ELSE
    return CONTROL_FLOW_CATEGORY_STRAIGHT_LINE


def expected_lowering_evidence(
    stage: str | None,
    entry_point: str | None,
    source_facts: list[str],
    type_facts: list[str],
    families: set[str],
    resource_facts: dict[str, Any],
) -> dict[str, object]:
    return {
        "status": LOWERING_EVIDENCE_STATUS,
        "entryPointIdentity": {
            "stage": stage,
            "entryPoint": entry_point,
            "fields": expected_entry_point_identity_fields(),
        },
        "sourceLocationExpectation": {
            "required": True,
            "facts": source_facts,
        },
        "resourceMode": expected_resource_mode(resource_facts),
        "typeFacts": {
            "required": True,
            "facts": type_facts,
        },
        "controlFlowCategory": expected_control_flow_category(families),
    }


def require_exact_keys(
    value: dict[str, Any], field: str, expected_keys: tuple[str, ...], errors: list[str]
) -> None:
    actual = set(value)
    expected = set(expected_keys)
    missing = sorted(expected - actual)
    stale = sorted(actual - expected)
    if missing:
        errors.append(f"{field} missing required key(s): {', '.join(missing)}")
    if stale:
        errors.append(f"{field} has unknown key(s): {', '.join(stale)}")


def require_resource_item_keys(
    value: dict[str, Any], field: str, collection: str, errors: list[str]
) -> None:
    required = set(RESOURCE_ITEM_REQUIRED_KEYS[collection])
    optional = set(RESOURCE_ITEM_OPTIONAL_KEYS.get(collection, ()))
    actual = set(value)
    missing = sorted(required - actual)
    stale = sorted(actual - required - optional)
    if missing:
        errors.append(f"{field} missing required key(s): {', '.join(missing)}")
    if stale:
        errors.append(f"{field} has unknown key(s): {', '.join(stale)}")


def check_fixed_descriptor_array_fields(
    record: dict[str, Any], field: str, errors: list[str]
) -> None:
    has_array_fact = any(
        key in record
        for key in (
            "descriptorArray",
            "arraySize",
            "indexingMode",
            "fixedDescriptorIndices",
        )
    )
    if not has_array_fact:
        return
    if record.get("descriptorArray") is not True:
        errors.append(f"{field}.descriptorArray must be true for array facts")
    array_size = record.get("arraySize")
    if not isinstance(array_size, int) or array_size <= 0:
        errors.append(f"{field}.arraySize must be a positive integer")
    if record.get("indexingMode") != "fixed-literal":
        errors.append(f"{field}.indexingMode must be 'fixed-literal'")
    indices = record.get("fixedDescriptorIndices")
    if (
        not isinstance(indices, list)
        or not indices
        or not all(isinstance(index, int) for index in indices)
    ):
        errors.append(
            f"{field}.fixedDescriptorIndices must be a non-empty integer list"
        )
    elif isinstance(array_size, int) and any(
        index < 0 or index >= array_size for index in indices
    ):
        errors.append(f"{field}.fixedDescriptorIndices must be within fixed arraySize")


def check_resource_facts(
    resource_facts: dict[str, Any],
    field: str,
    stage: str | None,
    errors: list[str],
) -> None:
    local_size = resource_facts.get("localSize")
    if (
        not isinstance(local_size, list)
        or len(local_size) != 3
        or not all(isinstance(item, int) and item > 0 for item in local_size)
    ):
        errors.append(f"{field}.localSize must be a three-positive-integer list")
    for collection in RESOURCE_FACT_LIST_FIELDS:
        if not isinstance(resource_facts.get(collection), list):
            errors.append(f"{field}.{collection} must be a list")
            continue
    descriptors = resource_facts.get("descriptors")
    if isinstance(descriptors, list):
        for index, item in enumerate(descriptors):
            item_field = f"{field}.descriptors[{index}]"
            descriptor = require_object(item, item_field, errors)
            if not descriptor:
                continue
            require_resource_item_keys(
                descriptor,
                item_field,
                "descriptors",
                errors,
            )
            if descriptor.get("stage") != stage:
                errors.append(f"{item_field}.stage must match fixture stage")
            if descriptor.get("kind") not in {
                "storageBuffer",
                "storageImage",
                "sampledTexture",
                "sampler",
            }:
                errors.append(
                    f"{item_field}.kind must be 'storageBuffer', 'storageImage', "
                    "'sampledTexture', or 'sampler'"
                )
            for integer_field in ("set", "binding"):
                value = descriptor.get(integer_field)
                if not isinstance(value, int) or value < 0:
                    errors.append(
                        f"{item_field}.{integer_field} must be a non-negative integer"
                    )
            require_string(descriptor.get("name"), f"{item_field}.name", errors)
            check_fixed_descriptor_array_fields(descriptor, item_field, errors)

    storage_buffers = resource_facts.get("storageBuffers")
    if isinstance(storage_buffers, list):
        for index, item in enumerate(storage_buffers):
            item_field = f"{field}.storageBuffers[{index}]"
            storage_buffer = require_object(item, item_field, errors)
            if not storage_buffer:
                continue
            require_resource_item_keys(
                storage_buffer,
                item_field,
                "storageBuffers",
                errors,
            )
            require_string(storage_buffer.get("name"), f"{item_field}.name", errors)
            source_type = require_string(
                storage_buffer.get("type"), f"{item_field}.type", errors
            )
            element_type = require_string(
                storage_buffer.get("elementType"),
                f"{item_field}.elementType",
                errors,
            )
            if source_type is not None and not (
                source_type.endswith("*") or re.fullmatch(r".+\*\[\d+\]", source_type)
            ):
                errors.append(f"{item_field}.type must be a pointer resource type")
            if (
                source_type is not None
                and element_type is not None
                and source_type != f"{element_type}*"
                and not re.fullmatch(
                    rf"{re.escape(element_type)}\*\[\d+\]", source_type
                )
            ):
                errors.append(
                    f"{item_field}.type must match elementType with a pointer suffix"
                )
            if storage_buffer.get("addressSpace") != "storage":
                errors.append(f"{item_field}.addressSpace must be 'storage'")
            if not isinstance(storage_buffer.get("writeAccess"), bool):
                errors.append(f"{item_field}.writeAccess must be a boolean")
            check_fixed_descriptor_array_fields(storage_buffer, item_field, errors)

    storage_images = resource_facts.get("storageImages")
    if isinstance(storage_images, list):
        for index, item in enumerate(storage_images):
            item_field = f"{field}.storageImages[{index}]"
            storage_image = require_object(item, item_field, errors)
            if not storage_image:
                continue
            require_exact_keys(
                storage_image,
                item_field,
                RESOURCE_ITEM_REQUIRED_KEYS["storageImages"],
                errors,
            )
            require_string(storage_image.get("name"), f"{item_field}.name", errors)
            require_string(storage_image.get("type"), f"{item_field}.type", errors)
            require_string(
                storage_image.get("elementType"),
                f"{item_field}.elementType",
                errors,
            )
            require_string(storage_image.get("format"), f"{item_field}.format", errors)
            require_string(
                storage_image.get("dimension"), f"{item_field}.dimension", errors
            )
            if not isinstance(storage_image.get("arrayed"), bool):
                errors.append(f"{item_field}.arrayed must be a boolean")
            if storage_image.get("access") != "read_write":
                errors.append(f"{item_field}.access must be 'read_write'")
            for integer_field in ("set", "binding"):
                value = storage_image.get(integer_field)
                if not isinstance(value, int) or value < 0:
                    errors.append(
                        f"{item_field}.{integer_field} must be a non-negative integer"
                    )

    textures = resource_facts.get("textures")
    if isinstance(textures, list):
        for index, item in enumerate(textures):
            item_field = f"{field}.textures[{index}]"
            texture = require_object(item, item_field, errors)
            if not texture:
                continue
            require_resource_item_keys(
                texture,
                item_field,
                "textures",
                errors,
            )
            require_string(texture.get("name"), f"{item_field}.name", errors)
            require_string(texture.get("type"), f"{item_field}.type", errors)
            require_string(
                texture.get("sampledType"), f"{item_field}.sampledType", errors
            )
            require_string(texture.get("dimension"), f"{item_field}.dimension", errors)
            if not isinstance(texture.get("arrayed"), bool):
                errors.append(f"{item_field}.arrayed must be a boolean")
            if not isinstance(texture.get("comparison"), bool):
                errors.append(f"{item_field}.comparison must be a boolean")
            for integer_field in ("set", "binding"):
                value = texture.get(integer_field)
                if not isinstance(value, int) or value < 0:
                    errors.append(
                        f"{item_field}.{integer_field} must be a non-negative integer"
                    )
            check_fixed_descriptor_array_fields(texture, item_field, errors)

    samplers = resource_facts.get("samplers")
    if isinstance(samplers, list):
        for index, item in enumerate(samplers):
            item_field = f"{field}.samplers[{index}]"
            sampler = require_object(item, item_field, errors)
            if not sampler:
                continue
            require_resource_item_keys(
                sampler,
                item_field,
                "samplers",
                errors,
            )
            require_string(sampler.get("name"), f"{item_field}.name", errors)
            require_string(sampler.get("type"), f"{item_field}.type", errors)
            if not isinstance(sampler.get("comparison"), bool):
                errors.append(f"{item_field}.comparison must be a boolean")
            for integer_field in ("set", "binding"):
                value = sampler.get(integer_field)
                if not isinstance(value, int) or value < 0:
                    errors.append(
                        f"{item_field}.{integer_field} must be a non-negative integer"
                    )
            check_fixed_descriptor_array_fields(sampler, item_field, errors)

    metadata = resource_facts.get(RESOURCE_METADATA_COLLECTION)
    if isinstance(metadata, list):
        for index, item in enumerate(metadata):
            item_field = f"{field}.{RESOURCE_METADATA_COLLECTION}[{index}]"
            record = require_object(item, item_field, errors)
            if not record:
                continue
            require_resource_item_keys(
                record,
                item_field,
                RESOURCE_METADATA_COLLECTION,
                errors,
            )
            if record.get("stage") != stage:
                errors.append(f"{item_field}.stage must match fixture stage")
            kind = record.get("kind")
            if kind not in {
                "storageBuffer",
                "storageImage",
                "sampledTexture",
                "sampler",
            }:
                errors.append(
                    f"{item_field}.kind must be 'storageBuffer', 'storageImage', "
                    "'sampledTexture', or 'sampler'"
                )
            require_string(record.get("name"), f"{item_field}.name", errors)
            require_string(record.get("sourceType"), f"{item_field}.sourceType", errors)
            require_string(
                record.get("elementType"), f"{item_field}.elementType", errors
            )
            expected_address_space = (
                "storage"
                if kind in {"storageBuffer", "storageImage"}
                else "uniform_constant"
            )
            if record.get("addressSpace") != expected_address_space:
                errors.append(
                    f"{item_field}.addressSpace must be {expected_address_space!r}"
                )
            expected_access = (
                "read_write" if kind in {"storageBuffer", "storageImage"} else "read"
            )
            if record.get("access") != expected_access:
                errors.append(f"{item_field}.access must be {expected_access!r}")
            for integer_field in ("set", "binding"):
                value = record.get(integer_field)
                if not isinstance(value, int) or value < 0:
                    errors.append(
                        f"{item_field}.{integer_field} must be a non-negative integer"
                    )
            if record.get("targetIndependent") is not True:
                errors.append(f"{item_field}.targetIndependent must be true")
            check_fixed_descriptor_array_fields(record, item_field, errors)

    if isinstance(descriptors, list) and isinstance(storage_buffers, list):
        descriptor_names = {
            item.get("name")
            for item in descriptors
            if isinstance(item, dict) and item.get("kind") == "storageBuffer"
        }
        storage_buffer_names = {
            item.get("name") for item in storage_buffers if isinstance(item, dict)
        }
        if descriptor_names != storage_buffer_names:
            errors.append(
                f"{field} storageBuffer descriptor names must match "
                "resourceFacts.storageBuffers names"
            )
        if isinstance(metadata, list):
            metadata_names = {
                item.get("name")
                for item in metadata
                if isinstance(item, dict) and item.get("kind") == "storageBuffer"
            }
            if descriptor_names != metadata_names:
                errors.append(
                    f"{field} target-independent resource metadata names must match "
                    "storageBuffer descriptor names"
                )
            descriptor_bindings = {
                (item.get("name"), item.get("set"), item.get("binding"))
                for item in descriptors
                if isinstance(item, dict) and item.get("kind") == "storageBuffer"
            }
            metadata_bindings = {
                (item.get("name"), item.get("set"), item.get("binding"))
                for item in metadata
                if isinstance(item, dict) and item.get("kind") == "storageBuffer"
            }
            if descriptor_bindings != metadata_bindings:
                errors.append(
                    f"{field} target-independent resource metadata set/binding "
                    "must match descriptor set/binding"
                )
    if isinstance(descriptors, list) and isinstance(storage_images, list):
        descriptor_names = {
            item.get("name")
            for item in descriptors
            if isinstance(item, dict) and item.get("kind") == "storageImage"
        }
        storage_image_names = {
            item.get("name") for item in storage_images if isinstance(item, dict)
        }
        if descriptor_names != storage_image_names:
            errors.append(
                f"{field} storageImage descriptor names must match "
                "resourceFacts.storageImages names"
            )
        if isinstance(metadata, list):
            metadata_names = {
                item.get("name")
                for item in metadata
                if isinstance(item, dict) and item.get("kind") == "storageImage"
            }
            if descriptor_names != metadata_names:
                errors.append(
                    f"{field} target-independent resource metadata names must match "
                    "storageImage descriptor names"
                )
            descriptor_bindings = {
                (item.get("name"), item.get("set"), item.get("binding"))
                for item in descriptors
                if isinstance(item, dict) and item.get("kind") == "storageImage"
            }
            metadata_bindings = {
                (item.get("name"), item.get("set"), item.get("binding"))
                for item in metadata
                if isinstance(item, dict) and item.get("kind") == "storageImage"
            }
            if descriptor_bindings != metadata_bindings:
                errors.append(
                    f"{field} target-independent resource metadata set/binding "
                    "must match storageImage descriptor set/binding"
                )
    if isinstance(descriptors, list) and isinstance(textures, list):
        descriptor_names = {
            item.get("name")
            for item in descriptors
            if isinstance(item, dict) and item.get("kind") == "sampledTexture"
        }
        texture_names = {
            item.get("name") for item in textures if isinstance(item, dict)
        }
        if descriptor_names != texture_names:
            errors.append(
                f"{field} sampledTexture descriptor names must match "
                "resourceFacts.textures names"
            )
    if isinstance(descriptors, list) and isinstance(samplers, list):
        descriptor_names = {
            item.get("name")
            for item in descriptors
            if isinstance(item, dict) and item.get("kind") == "sampler"
        }
        sampler_names = {
            item.get("name") for item in samplers if isinstance(item, dict)
        }
        if descriptor_names != sampler_names:
            errors.append(
                f"{field} sampler descriptor names must match "
                "resourceFacts.samplers names"
            )


def check_required_facts(inventory: dict[str, Any], errors: list[str]) -> None:
    required_facts = require_object(
        inventory.get("requiredFacts"), f"{INVENTORY_PATH}: requiredFacts", errors
    )
    if not required_facts:
        return
    missing = sorted(set(REQUIRED_FACT_CATEGORIES) - set(required_facts))
    stale = sorted(set(required_facts) - set(REQUIRED_FACT_CATEGORIES))
    if missing:
        errors.append(
            f"{INVENTORY_PATH}: requiredFacts missing category/categories: "
            + ", ".join(missing)
        )
    if stale:
        errors.append(
            f"{INVENTORY_PATH}: requiredFacts has unknown category/categories: "
            + ", ".join(stale)
        )
    for category in REQUIRED_FACT_CATEGORIES:
        records = required_facts.get(category)
        if not isinstance(records, list) or not records:
            errors.append(
                f"{INVENTORY_PATH}: requiredFacts.{category} must be a non-empty list"
            )
            continue
        ids: list[str] = []
        for index, item in enumerate(records):
            field = f"{INVENTORY_PATH}: requiredFacts.{category}[{index}]"
            record = require_object(item, field, errors)
            if not record:
                continue
            fact_id = require_string(record.get("id"), f"{field}.id", errors)
            if fact_id is not None:
                ids.append(fact_id)
            if record.get("required") is not True:
                errors.append(f"{field}.required must be true")
            require_string(record.get("description"), f"{field}.description", errors)
        require_unique(ids, f"{INVENTORY_PATH}: requiredFacts.{category}[].id", errors)


def check_blocked_families(inventory: dict[str, Any], errors: list[str]) -> list[str]:
    records = inventory.get("unsupportedHirFamilies")
    if not isinstance(records, list) or not records:
        errors.append(
            f"{INVENTORY_PATH}: unsupportedHirFamilies must be a non-empty list"
        )
        return []
    family_ids: list[str] = []
    for index, item in enumerate(records):
        field = f"{INVENTORY_PATH}: unsupportedHirFamilies[{index}]"
        record = require_object(item, field, errors)
        if not record:
            continue
        family_id = require_string(record.get("id"), f"{field}.id", errors)
        if family_id is not None:
            family_ids.append(family_id)
        reason = require_string(record.get("reason"), f"{field}.reason", errors)
        if reason is not None and len(reason.split()) < 6:
            errors.append(f"{field}.reason must explain the blocked-family rationale")
    require_unique(family_ids, f"{INVENTORY_PATH}: unsupportedHirFamilies[].id", errors)
    return family_ids


def check_fixture_parity_requirements(
    record: dict[str, Any],
    field: str,
    source_facts: list[str],
    type_facts: list[str],
    resource_facts: dict[str, Any],
    errors: list[str],
) -> None:
    parity = require_object(
        record.get(PARITY_REQUIREMENT_KEY),
        f"{field}.{PARITY_REQUIREMENT_KEY}",
        errors,
    )
    if not parity:
        return

    missing_sections = [
        section
        for section in REQUIRED_PARITY_REQUIREMENT_SECTIONS
        if section not in parity
    ]
    if missing_sections:
        errors.append(
            f"{field}.{PARITY_REQUIREMENT_KEY} missing required section(s): "
            + ", ".join(missing_sections)
        )
    stale_sections = sorted(set(parity) - set(REQUIRED_PARITY_REQUIREMENT_SECTIONS))
    if stale_sections:
        errors.append(
            f"{field}.{PARITY_REQUIREMENT_KEY} has unknown section(s): "
            + ", ".join(stale_sections)
        )

    _, source_fields = require_parity_section(
        parity.get("sourceLocations"),
        f"{field}.{PARITY_REQUIREMENT_KEY}.sourceLocations",
        errors,
        allowed_keys={"required", "fields"},
    )
    compare_fields(
        source_fields,
        source_facts,
        f"{field}.{PARITY_REQUIREMENT_KEY}.sourceLocations",
        errors,
    )

    _, type_fields = require_parity_section(
        parity.get("typeFacts"),
        f"{field}.{PARITY_REQUIREMENT_KEY}.typeFacts",
        errors,
        allowed_keys={"required", "fields"},
    )
    compare_fields(
        type_fields,
        type_facts,
        f"{field}.{PARITY_REQUIREMENT_KEY}.typeFacts",
        errors,
    )

    _, entry_fields = require_parity_section(
        parity.get("entryPoint"),
        f"{field}.{PARITY_REQUIREMENT_KEY}.entryPoint",
        errors,
        allowed_keys={"required", "fields"},
    )
    compare_fields(
        entry_fields,
        ["stage", "entryPoint", "resourceFacts.localSize"],
        f"{field}.{PARITY_REQUIREMENT_KEY}.entryPoint",
        errors,
    )

    _, resource_fields = require_parity_section(
        parity.get("resources"),
        f"{field}.{PARITY_REQUIREMENT_KEY}.resources",
        errors,
        allowed_keys={"required", "fields"},
    )
    compare_fields(
        resource_fields,
        expected_resource_requirement_fields(resource_facts),
        f"{field}.{PARITY_REQUIREMENT_KEY}.resources",
        errors,
    )

    _, metadata_fields = require_parity_section(
        parity.get("targetIndependentResourceMetadata"),
        f"{field}.{PARITY_REQUIREMENT_KEY}.targetIndependentResourceMetadata",
        errors,
        allowed_keys={"required", "fields"},
    )
    compare_fields(
        metadata_fields,
        expected_target_independent_resource_metadata_fields(resource_facts),
        f"{field}.{PARITY_REQUIREMENT_KEY}.targetIndependentResourceMetadata",
        errors,
    )

    _, diagnostics_fields = require_parity_section(
        parity.get("diagnosticsProvenance"),
        f"{field}.{PARITY_REQUIREMENT_KEY}.diagnosticsProvenance",
        errors,
        allowed_keys={"required", "fields"},
    )
    compare_fields(
        diagnostics_fields,
        expected_diagnostics_provenance_fields(source_facts, type_facts),
        f"{field}.{PARITY_REQUIREMENT_KEY}.diagnosticsProvenance",
        errors,
    )

    _, source_map_debug_fields = require_parity_section(
        parity.get("sourceMapDebugPreservation"),
        f"{field}.{PARITY_REQUIREMENT_KEY}.sourceMapDebugPreservation",
        errors,
        allowed_keys={"required", "fields"},
    )
    compare_fields(
        source_map_debug_fields,
        expected_source_map_debug_preservation_fields(source_facts, type_facts),
        f"{field}.{PARITY_REQUIREMENT_KEY}.sourceMapDebugPreservation",
        errors,
    )


def check_fixture_parity_report(
    record: dict[str, Any],
    field: str,
    source_facts: list[str],
    type_facts: list[str],
    families: set[str],
    resource_facts: dict[str, Any],
    blocked_family_ids: list[str],
    errors: list[str],
) -> None:
    report = require_object(
        record.get(REPORT_FIELD_KEY), f"{field}.{REPORT_FIELD_KEY}", errors
    )
    if not report:
        return

    missing_sections = [
        section for section in REQUIRED_REPORT_SECTIONS if section not in report
    ]
    if missing_sections:
        errors.append(
            f"{field}.{REPORT_FIELD_KEY} missing required section(s): "
            + ", ".join(missing_sections)
        )
    stale_sections = sorted(set(report) - set(REQUIRED_REPORT_SECTIONS))
    if stale_sections:
        errors.append(
            f"{field}.{REPORT_FIELD_KEY} has unknown section(s): "
            + ", ".join(stale_sections)
        )

    _, source_fields = require_parity_section(
        report.get("sourceFile"),
        f"{field}.{REPORT_FIELD_KEY}.sourceFile",
        errors,
        allowed_keys={"required", "fields"},
    )
    compare_fields(
        source_fields,
        ["path", "sourceLocationFacts.source_file"],
        f"{field}.{REPORT_FIELD_KEY}.sourceFile",
        errors,
    )
    if "source_file" not in source_facts:
        errors.append(f"{field}.sourceLocationFacts must include 'source_file'")
    for source_fact in ENTRY_POINT_IDENTITY_SOURCE_FACTS:
        if source_fact not in source_facts:
            errors.append(
                f"{field}.sourceLocationFacts must include {source_fact!r} "
                "for entry-point identity parity"
            )
    if WORKGROUP_SOURCE_FACT not in source_facts:
        errors.append(
            f"{field}.sourceLocationFacts must include {WORKGROUP_SOURCE_FACT!r} "
            "for workgroup-size provenance"
        )
    for type_fact in ENTRY_POINT_IDENTITY_TYPE_FACTS:
        if type_fact not in type_facts:
            errors.append(
                f"{field}.typeFacts must include {type_fact!r} "
                "for entry-point identity parity"
            )

    _, entry_fields = require_parity_section(
        report.get("entryPoint"),
        f"{field}.{REPORT_FIELD_KEY}.entryPoint",
        errors,
        allowed_keys={"required", "fields"},
    )
    compare_fields(
        entry_fields,
        ["stage", "entryPoint"],
        f"{field}.{REPORT_FIELD_KEY}.entryPoint",
        errors,
    )

    _, entry_identity_fields = require_parity_section(
        report.get("entryPointIdentity"),
        f"{field}.{REPORT_FIELD_KEY}.entryPointIdentity",
        errors,
        allowed_keys={"required", "fields"},
    )
    compare_fields(
        entry_identity_fields,
        expected_entry_point_identity_fields(),
        f"{field}.{REPORT_FIELD_KEY}.entryPointIdentity",
        errors,
    )

    _, local_size_fields = require_parity_section(
        report.get("localSize"),
        f"{field}.{REPORT_FIELD_KEY}.localSize",
        errors,
        allowed_keys={"required", "fields"},
    )
    compare_fields(
        local_size_fields,
        ["resourceFacts.localSize"],
        f"{field}.{REPORT_FIELD_KEY}.localSize",
        errors,
    )

    _, workgroup_size_fields = require_parity_section(
        report.get("workgroupSize"),
        f"{field}.{REPORT_FIELD_KEY}.workgroupSize",
        errors,
        allowed_keys={"required", "fields"},
    )
    compare_fields(
        workgroup_size_fields,
        expected_workgroup_size_fields(),
        f"{field}.{REPORT_FIELD_KEY}.workgroupSize",
        errors,
    )

    _, resource_fields = require_parity_section(
        report.get("resourceBindings"),
        f"{field}.{REPORT_FIELD_KEY}.resourceBindings",
        errors,
        allowed_keys={"required", "fields"},
    )
    compare_fields(
        resource_fields,
        expected_resource_binding_fields(resource_facts),
        f"{field}.{REPORT_FIELD_KEY}.resourceBindings",
        errors,
    )

    _, metadata_fields = require_parity_section(
        report.get("targetIndependentResourceMetadata"),
        f"{field}.{REPORT_FIELD_KEY}.targetIndependentResourceMetadata",
        errors,
        allowed_keys={"required", "fields"},
    )
    compare_fields(
        metadata_fields,
        expected_target_independent_resource_metadata_fields(resource_facts),
        f"{field}.{REPORT_FIELD_KEY}.targetIndependentResourceMetadata",
        errors,
    )

    _, type_fields = require_parity_section(
        report.get("typeFacts"),
        f"{field}.{REPORT_FIELD_KEY}.typeFacts",
        errors,
        allowed_keys={"required", "fields"},
    )
    compare_fields(
        type_fields,
        expected_type_fact_fields(type_facts),
        f"{field}.{REPORT_FIELD_KEY}.typeFacts",
        errors,
    )

    _, diagnostics_fields = require_parity_section(
        report.get("diagnosticsProvenance"),
        f"{field}.{REPORT_FIELD_KEY}.diagnosticsProvenance",
        errors,
        allowed_keys={"required", "fields"},
    )
    compare_fields(
        diagnostics_fields,
        expected_diagnostics_provenance_fields(source_facts, type_facts),
        f"{field}.{REPORT_FIELD_KEY}.diagnosticsProvenance",
        errors,
    )

    _, source_map_debug_fields = require_parity_section(
        report.get("sourceMapDebugPreservation"),
        f"{field}.{REPORT_FIELD_KEY}.sourceMapDebugPreservation",
        errors,
        allowed_keys={"required", "fields"},
    )
    compare_fields(
        source_map_debug_fields,
        expected_source_map_debug_preservation_fields(source_facts, type_facts),
        f"{field}.{REPORT_FIELD_KEY}.sourceMapDebugPreservation",
        errors,
    )

    control_section, control_fields = require_parity_section(
        report.get("controlFlowSlice"),
        f"{field}.{REPORT_FIELD_KEY}.controlFlowSlice",
        errors,
        allow_empty_fields=True,
        allowed_keys={"required", "slice", "fields"},
    )
    expected_slice, expected_control_fields = expected_control_flow_report(
        families, source_facts, type_facts
    )
    actual_slice = control_section.get("slice")
    if actual_slice != expected_slice:
        errors.append(
            f"{field}.{REPORT_FIELD_KEY}.controlFlowSlice.slice must be "
            f"{expected_slice!r}, got {actual_slice!r}"
        )
    compare_fields(
        control_fields,
        expected_control_fields,
        f"{field}.{REPORT_FIELD_KEY}.controlFlowSlice",
        errors,
    )
    if CONTROL_FLOW_FAMILY in families and not expected_control_fields:
        errors.append(
            f"{field}.{REPORT_FIELD_KEY}.controlFlowSlice must enumerate the "
            "admitted control-flow facts"
        )

    blocked_section, blocked_fields = require_parity_section(
        report.get("blockedFamilyRationale"),
        f"{field}.{REPORT_FIELD_KEY}.blockedFamilyRationale",
        errors,
        allowed_keys={"required", "fields", "families"},
    )
    compare_fields(
        blocked_fields,
        list(BLOCKED_FAMILY_REPORT_FIELDS),
        f"{field}.{REPORT_FIELD_KEY}.blockedFamilyRationale",
        errors,
    )
    families = require_string_list(
        blocked_section.get("families"),
        f"{field}.{REPORT_FIELD_KEY}.blockedFamilyRationale.families",
        errors,
    )
    require_unique(
        families,
        f"{field}.{REPORT_FIELD_KEY}.blockedFamilyRationale.families",
        errors,
    )
    if families != blocked_family_ids:
        errors.append(
            f"{field}.{REPORT_FIELD_KEY}.blockedFamilyRationale.families "
            "must match unsupportedHirFamilies order"
        )


def check_lowering_evidence(
    record: dict[str, Any],
    field: str,
    stage: str | None,
    entry_point: str | None,
    source_facts: list[str],
    type_facts: list[str],
    families: set[str],
    resource_facts: dict[str, Any],
    errors: list[str],
) -> None:
    evidence = require_object(
        record.get(LOWERING_EVIDENCE_KEY),
        f"{field}.{LOWERING_EVIDENCE_KEY}",
        errors,
    )
    if not evidence:
        return

    require_exact_keys(
        evidence,
        f"{field}.{LOWERING_EVIDENCE_KEY}",
        LOWERING_EVIDENCE_SECTIONS,
        errors,
    )
    expected = expected_lowering_evidence(
        stage, entry_point, source_facts, type_facts, families, resource_facts
    )

    if evidence.get("status") != expected["status"]:
        errors.append(
            f"{field}.{LOWERING_EVIDENCE_KEY}.status must be {expected['status']!r}"
        )

    entry_identity = require_object(
        evidence.get("entryPointIdentity"),
        f"{field}.{LOWERING_EVIDENCE_KEY}.entryPointIdentity",
        errors,
    )
    expected_entry_identity = expected["entryPointIdentity"]
    assert isinstance(expected_entry_identity, dict)
    require_exact_keys(
        entry_identity,
        f"{field}.{LOWERING_EVIDENCE_KEY}.entryPointIdentity",
        ("stage", "entryPoint", "fields"),
        errors,
    )
    for key in ("stage", "entryPoint"):
        if entry_identity.get(key) != expected_entry_identity[key]:
            errors.append(
                f"{field}.{LOWERING_EVIDENCE_KEY}.entryPointIdentity.{key} "
                f"must be {expected_entry_identity[key]!r}"
            )
    entry_fields = require_string_list(
        entry_identity.get("fields"),
        f"{field}.{LOWERING_EVIDENCE_KEY}.entryPointIdentity.fields",
        errors,
    )
    require_unique(
        entry_fields,
        f"{field}.{LOWERING_EVIDENCE_KEY}.entryPointIdentity.fields",
        errors,
    )
    if entry_fields != expected_entry_identity["fields"]:
        errors.append(
            f"{field}.{LOWERING_EVIDENCE_KEY}.entryPointIdentity.fields "
            f"must be {expected_entry_identity['fields']!r}"
        )

    source_expectation = require_object(
        evidence.get("sourceLocationExpectation"),
        f"{field}.{LOWERING_EVIDENCE_KEY}.sourceLocationExpectation",
        errors,
    )
    require_exact_keys(
        source_expectation,
        f"{field}.{LOWERING_EVIDENCE_KEY}.sourceLocationExpectation",
        ("required", "facts"),
        errors,
    )
    if source_expectation.get("required") is not True:
        errors.append(
            f"{field}.{LOWERING_EVIDENCE_KEY}."
            "sourceLocationExpectation.required must be true"
        )
    expected_source_expectation = expected["sourceLocationExpectation"]
    assert isinstance(expected_source_expectation, dict)
    evidence_source_facts = require_string_list(
        source_expectation.get("facts"),
        f"{field}.{LOWERING_EVIDENCE_KEY}.sourceLocationExpectation.facts",
        errors,
    )
    require_unique(
        evidence_source_facts,
        f"{field}.{LOWERING_EVIDENCE_KEY}.sourceLocationExpectation.facts",
        errors,
    )
    if evidence_source_facts != expected_source_expectation["facts"]:
        errors.append(
            f"{field}.{LOWERING_EVIDENCE_KEY}.sourceLocationExpectation.facts "
            f"must match {field}.sourceLocationFacts"
        )

    if evidence.get("resourceMode") != expected["resourceMode"]:
        errors.append(
            f"{field}.{LOWERING_EVIDENCE_KEY}.resourceMode must be "
            f"{expected['resourceMode']!r}"
        )

    type_evidence = require_object(
        evidence.get("typeFacts"),
        f"{field}.{LOWERING_EVIDENCE_KEY}.typeFacts",
        errors,
    )
    require_exact_keys(
        type_evidence,
        f"{field}.{LOWERING_EVIDENCE_KEY}.typeFacts",
        ("required", "facts"),
        errors,
    )
    if type_evidence.get("required") is not True:
        errors.append(
            f"{field}.{LOWERING_EVIDENCE_KEY}.typeFacts.required must be true"
        )
    expected_type_evidence = expected["typeFacts"]
    assert isinstance(expected_type_evidence, dict)
    evidence_type_facts = require_string_list(
        type_evidence.get("facts"),
        f"{field}.{LOWERING_EVIDENCE_KEY}.typeFacts.facts",
        errors,
    )
    require_unique(
        evidence_type_facts,
        f"{field}.{LOWERING_EVIDENCE_KEY}.typeFacts.facts",
        errors,
    )
    if evidence_type_facts != expected_type_evidence["facts"]:
        errors.append(
            f"{field}.{LOWERING_EVIDENCE_KEY}.typeFacts.facts "
            f"must match {field}.typeFacts"
        )

    if evidence.get("controlFlowCategory") != expected["controlFlowCategory"]:
        errors.append(
            f"{field}.{LOWERING_EVIDENCE_KEY}.controlFlowCategory must be "
            f"{expected['controlFlowCategory']!r}"
        )


def run_cglc_dump(
    cglc: Path,
    fixture: str,
    stage: str,
    opt_level: str = HIR_OPT_LEVEL_FOR_PARITY,
    *,
    cwd: Path,
) -> str:
    command = [
        str(cglc),
        "dump-ir",
        fixture,
        "--stage",
        stage,
        "--opt-level",
        opt_level,
    ]
    if stage == "hir-source-map":
        command.append("--source-map-records")

    try:
        completed = subprocess.run(
            command,
            cwd=cwd,
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
    except OSError as error:
        raise RuntimeError(f"failed to run {' '.join(command)}: {error}") from error

    if completed.returncode != 0:
        raise RuntimeError(
            f"{' '.join(command)} failed with exit code {completed.returncode}; "
            f"stdout: {completed.stdout.strip()!r}; "
            f"stderr: {completed.stderr.strip()!r}"
        )
    return completed.stdout


def collect_hir_text_facts(text: str) -> dict[str, Any]:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    facts: dict[str, Any] = {
        "lines": lines,
        "modules": set(),
        "stages": set(),
        "workgroupSizes": set(),
        "functions": set(),
        "resources": set(),
        "declaredTypes": set(),
        "hasBoolResult": any(" : bool" in line for line in lines),
        "hasIfBool": any(
            line.startswith("if ") and line.endswith(" : bool") for line in lines
        ),
        "hasElse": "else" in lines,
        "hasReturn": "return" in lines,
        "hasAssignment": any(line.startswith("assign ") for line in lines),
        "hasStorageRead": any(
            not line.startswith("assign ") and re.search(r"\b\w+\[[^\]]+\]", line)
            for line in lines
        ),
        "hasStorageWrite": any(
            line.startswith("assign ") and re.search(r"\b\w+\[[^\]]+\]", line)
            for line in lines
        ),
        "hasImageLoad": any("imageLoad(" in line for line in lines),
        "hasImageStore": any("imageStore(" in line for line in lines),
    }

    module_pattern = re.compile(r"^module\s+([A-Za-z_][A-Za-z0-9_]*)$")
    stage_pattern = re.compile(
        r"^stage\s+([A-Za-z_][A-Za-z0-9_]*)\s+entry\s+([A-Za-z_][A-Za-z0-9_]*)$"
    )
    workgroup_pattern = re.compile(
        r"^workgroup_size\s+([0-9]+),\s*([0-9]+),\s*([0-9]+)$"
    )
    function_pattern = re.compile(
        r"^fn\s+([A-Za-z_][A-Za-z0-9_]*)\(\)\s+->\s+([A-Za-z_][A-Za-z0-9_*]*)$"
    )
    resource_pattern = re.compile(
        r"^resource\s+([A-Za-z_][A-Za-z0-9_]*)\s+(.+?)\s+"
        r"([A-Za-z_][A-Za-z0-9_]*)\s+"
        r"(?:access\s+[A-Za-z_][A-Za-z0-9_]*\s+)?"
        r"(?:format\s+[A-Za-z0-9_]+\s+)?"
        r"set\s+([0-9]+)\s+binding\s+([0-9]+)$"
    )
    declaration_pattern = re.compile(
        r"^decl\s+([A-Za-z_][A-Za-z0-9_*]*)\s+[A-Za-z_][A-Za-z0-9_]*\b"
    )

    for line in lines:
        if match := module_pattern.match(line):
            facts["modules"].add(match.group(1))
            continue
        if match := stage_pattern.match(line):
            facts["stages"].add((match.group(1), match.group(2)))
            continue
        if match := workgroup_pattern.match(line):
            facts["workgroupSizes"].add(tuple(int(match.group(i)) for i in range(1, 4)))
            continue
        if match := function_pattern.match(line):
            facts["functions"].add((match.group(1), match.group(2)))
            continue
        if match := resource_pattern.match(line):
            facts["resources"].add(
                (
                    match.group(1),
                    match.group(2),
                    match.group(3),
                    int(match.group(4)),
                    int(match.group(5)),
                )
            )
            continue
        if match := declaration_pattern.match(line):
            facts["declaredTypes"].add(match.group(1))

    return facts


def collect_hir_source_map_facts(json_text: str) -> dict[str, Any]:
    data = json.loads(json_text)
    records = data.get("records") if isinstance(data.get("records"), dict) else {}
    locations = (
        data.get("hirSourceLocations")
        if isinstance(data.get("hirSourceLocations"), dict)
        else {}
    )
    record_items = (
        records.get("items") if isinstance(records.get("items"), list) else []
    )
    types = locations.get("types") if isinstance(locations.get("types"), list) else []
    statements = (
        locations.get("statements")
        if isinstance(locations.get("statements"), list)
        else []
    )
    expressions = (
        locations.get("expressions")
        if isinstance(locations.get("expressions"), list)
        else []
    )
    return {
        "data": data,
        "records": records,
        "recordItems": record_items,
        "types": types,
        "statements": statements,
        "expressions": expressions,
        "typeTriples": {
            (item.get("ownerKind"), item.get("ownerName"), item.get("type"))
            for item in types
            if isinstance(item, dict)
        },
        "statementTriples": {
            (item.get("statementKind"), item.get("name"), item.get("function"))
            for item in statements
            if isinstance(item, dict)
        },
        "expressionTuples": {
            (
                item.get("statementKind"),
                item.get("kind"),
                item.get("value"),
                item.get("type"),
            )
            for item in expressions
            if isinstance(item, dict)
        },
    }


def source_location_matches(
    location: object, fixture: str, field: str, errors: list[str]
) -> None:
    if not isinstance(location, dict):
        errors.append(f"{field}.location must be an object")
        return
    if location.get("file") != fixture:
        errors.append(
            f"{field}.location.file must be {fixture!r}, got {location.get('file')!r}"
        )
    for key in (
        "line",
        "column",
        "offset",
        "length",
        "endLine",
        "endColumn",
        "endOffset",
    ):
        value = location.get(key)
        if not isinstance(value, int) or value < 0:
            errors.append(f"{field}.location.{key} must be a non-negative integer")


def check_combined_record_locations(
    facts: dict[str, Any], fixture: str, field: str, errors: list[str]
) -> None:
    has_type_record = False
    has_statement_record = False
    for index, item in enumerate(facts["recordItems"]):
        if not isinstance(item, dict):
            errors.append(f"{field}.records.items[{index}] must be an object")
            continue
        record_kind = item.get("recordKind")
        if record_kind == "type":
            has_type_record = True
            payload = item.get("type")
        elif record_kind == "statement":
            has_statement_record = True
            payload = item.get("statement")
        else:
            continue
        if not isinstance(payload, dict):
            errors.append(
                f"{field}.records.items[{index}].{record_kind} must be an object"
            )
            continue
        source_location_matches(
            payload.get("location"),
            fixture,
            f"{field}.records.items[{index}].{record_kind}",
            errors,
        )

    if not has_type_record:
        errors.append(f"{field}.records.items must include type records")
    if not has_statement_record:
        errors.append(f"{field}.records.items must include statement records")


def check_hir_text_parity(
    record: dict[str, Any], field: str, text: str, errors: list[str]
) -> None:
    path = record.get("path")
    stage = record.get("stage")
    entry_point = record.get("entryPoint")
    resource_facts = record.get("resourceFacts")
    if not isinstance(path, str) or not isinstance(resource_facts, dict):
        return

    facts = collect_hir_text_facts(text)
    module_name = Path(path).stem
    if module_name not in facts["modules"]:
        errors.append(f"{field}: HIR text must include module {module_name}")
    if isinstance(stage, str) and isinstance(entry_point, str):
        if (stage, entry_point) not in facts["stages"]:
            errors.append(
                f"{field}: HIR text must include stage {stage} entry {entry_point}"
            )
        if (entry_point, "void") not in facts["functions"]:
            errors.append(f"{field}: HIR text must include fn {entry_point}() -> void")

    local_size = resource_facts.get("localSize")
    if isinstance(local_size, list) and len(local_size) == 3:
        expected_size = tuple(local_size)
        if expected_size not in facts["workgroupSizes"]:
            errors.append(
                f"{field}: HIR text must include workgroup_size "
                f"{expected_size[0]}, {expected_size[1]}, {expected_size[2]}"
            )

    storage_buffers_by_name = {
        item.get("name"): item
        for item in resource_facts.get("storageBuffers", [])
        if isinstance(item, dict)
    }
    storage_images_by_name = {
        item.get("name"): item
        for item in resource_facts.get("storageImages", [])
        if isinstance(item, dict)
    }
    for index, descriptor in enumerate(resource_facts.get("descriptors", [])):
        if not isinstance(descriptor, dict):
            continue
        name = descriptor.get("name")
        kind = descriptor.get("kind")
        hir_kind = {
            "storageBuffer": "buffer",
            "storageImage": "storage_image",
            "sampledTexture": "texture",
            "sampler": "sampler",
        }.get(kind)
        if hir_kind is None:
            continue
        source_type = descriptor.get("sourceType")
        if kind == "storageBuffer":
            storage_buffer = storage_buffers_by_name.get(name)
            source_type = (
                storage_buffer.get("type")
                if isinstance(storage_buffer, dict)
                else descriptor.get("sourceType")
            )
        elif kind == "storageImage":
            storage_image = storage_images_by_name.get(name)
            source_type = (
                storage_image.get("type")
                if isinstance(storage_image, dict)
                else descriptor.get("sourceType")
            )
        elif kind == "sampledTexture":
            for texture in resource_facts.get("textures", []):
                if isinstance(texture, dict) and texture.get("name") == name:
                    source_type = texture.get("type")
                    break
        elif kind == "sampler":
            for sampler in resource_facts.get("samplers", []):
                if isinstance(sampler, dict) and sampler.get("name") == name:
                    source_type = sampler.get("type")
                    break
        expected_resource = (
            hir_kind,
            source_type,
            name,
            descriptor.get("set"),
            descriptor.get("binding"),
        )
        if expected_resource not in facts["resources"]:
            errors.append(
                f"{field}: HIR text missing resource {index}: {expected_resource!r}"
            )

    source_facts = set(record.get("sourceLocationFacts", []))
    type_facts = set(record.get("typeFacts", []))
    allowed_families = set(record.get("allowedHirFamilies", []))

    if "float_scalar" in type_facts and "float" not in facts["declaredTypes"]:
        errors.append(f"{field}: HIR text must include a float scalar declaration")
    if "int_scalar" in type_facts and "int" not in facts["declaredTypes"]:
        errors.append(f"{field}: HIR text must include an int scalar declaration")
    if "bool_scalar" in type_facts and "bool" not in facts["declaredTypes"]:
        errors.append(f"{field}: HIR text must include a bool scalar declaration")
    if {
        "comparison_expression_result_type",
        "branch_condition_bool",
    } & type_facts and not facts["hasBoolResult"]:
        errors.append(f"{field}: HIR text must include a comparison result ': bool'")
    if "storage_buffer_read" in source_facts and not facts["hasStorageRead"]:
        errors.append(f"{field}: HIR text must include a storage-buffer read")
    if "storage_buffer_write" in source_facts and not facts["hasStorageWrite"]:
        errors.append(f"{field}: HIR text must include a storage-buffer write")
    if "storage_image_load" in source_facts and not facts["hasImageLoad"]:
        errors.append(f"{field}: HIR text must include an imageLoad call")
    if "storage_image_store" in source_facts and not facts["hasImageStore"]:
        errors.append(f"{field}: HIR text must include an imageStore call")
    if "return_statement" in source_facts and not facts["hasReturn"]:
        errors.append(f"{field}: HIR text must include return")
    if CONTROL_FLOW_FAMILY in allowed_families:
        if not facts["hasIfBool"]:
            errors.append(f"{field}: HIR text must include if ... : bool")
        if not facts["hasElse"]:
            errors.append(f"{field}: HIR text must include else")
        if not facts["hasAssignment"]:
            errors.append(f"{field}: HIR text must include control-flow assignments")


def check_hir_source_map_parity(
    record: dict[str, Any], field: str, json_text: str, errors: list[str]
) -> None:
    path = record.get("path")
    if not isinstance(path, str):
        return
    try:
        facts = collect_hir_source_map_facts(json_text)
    except json.JSONDecodeError as error:
        errors.append(f"{field}: HIR source-map dump must be valid JSON: {error}")
        return

    data = facts["data"]
    records = facts["records"]
    if data.get("schemaVersion") != 7:
        errors.append(f"{field}: HIR source-map schemaVersion must be 7")
    if records.get("enabled") is not True:
        errors.append(f"{field}: HIR source-map records.enabled must be true")
    if (
        not isinstance(records.get("activeCount"), int)
        or records.get("activeCount") < 1
    ):
        errors.append(f"{field}: HIR source-map records.activeCount must be positive")
    if not facts["recordItems"]:
        errors.append(f"{field}: HIR source-map records.items must be non-empty")
    check_combined_record_locations(facts, path, field, errors)

    for index, item in enumerate(facts["types"]):
        if isinstance(item, dict):
            source_location_matches(
                item.get("location"),
                path,
                f"{field}.hirSourceLocations.types[{index}]",
                errors,
            )
    for index, item in enumerate(facts["statements"]):
        if isinstance(item, dict):
            source_location_matches(
                item.get("location"),
                path,
                f"{field}.hirSourceLocations.statements[{index}]",
                errors,
            )

    type_facts = set(record.get("typeFacts", []))
    source_facts = set(record.get("sourceLocationFacts", []))
    type_triples = facts["typeTriples"]
    expression_tuples = facts["expressionTuples"]
    statement_triples = facts["statementTriples"]
    storage_buffer_names = {
        item.get("name")
        for item in record.get("resourceFacts", {}).get("storageBuffers", [])
        if isinstance(item, dict) and isinstance(item.get("name"), str)
    }

    if (
        "void_entry_point" in type_facts
        and (
            "function-return-type",
            record.get("entryPoint"),
            "void",
        )
        not in type_triples
    ):
        errors.append(f"{field}: HIR source-map missing void entry-point type")
    if "float_scalar" in type_facts and not any(
        owner == "statement-declared-type" and typ == "float"
        for owner, _, typ in type_triples
    ):
        errors.append(f"{field}: HIR source-map missing float scalar type")
    if "int_scalar" in type_facts and not any(
        owner == "statement-declared-type" and typ == "int"
        for owner, _, typ in type_triples
    ):
        errors.append(f"{field}: HIR source-map missing int scalar type")
    if "bool_scalar" in type_facts and not any(
        owner == "statement-declared-type" and typ == "bool"
        for owner, _, typ in type_triples
    ):
        errors.append(f"{field}: HIR source-map missing bool scalar type")
    if "float_pointer_storage_buffer" in type_facts and not any(
        owner == "resource-type" and typ == "float*" for owner, _, typ in type_triples
    ):
        errors.append(f"{field}: HIR source-map missing float* storage-buffer type")
    if "storage_buffer_element_type" in type_facts:
        expected_element_types = {
            item.get("elementType")
            for item in record.get("resourceFacts", {}).get("storageBuffers", [])
            if isinstance(item, dict) and isinstance(item.get("elementType"), str)
        }
        if not any(
            kind == "index" and typ in expected_element_types
            for _, kind, _, typ in expression_tuples
        ):
            errors.append(
                f"{field}: HIR source-map missing storage-buffer element type"
            )
    if "binary_expression_result_types" in type_facts and not any(
        kind == "binary" and isinstance(typ, str) and typ
        for _, kind, _, typ in expression_tuples
    ):
        errors.append(f"{field}: HIR source-map missing binary expression type")
    if "comparison_expression_result_type" in type_facts and not any(
        kind == "binary" and value == ">" and typ == "bool"
        for _, kind, value, typ in expression_tuples
    ):
        errors.append(f"{field}: HIR source-map missing comparison bool type")
    if "branch_condition_bool" in type_facts and not any(
        statement == "if" and kind == "binary" and typ == "bool"
        for statement, kind, _, typ in expression_tuples
    ):
        errors.append(f"{field}: HIR source-map missing bool branch condition")
    if "assignment_expression_result_types" in type_facts and not any(
        statement == "assign" and isinstance(typ, str) and typ
        for statement, _, _, typ in expression_tuples
    ):
        errors.append(f"{field}: HIR source-map missing assignment expression types")
    if "unary_expression_result_types" in type_facts and not any(
        kind == "unary" and isinstance(typ, str) and typ
        for _, kind, _, typ in expression_tuples
    ):
        errors.append(f"{field}: HIR source-map missing unary expression type")
    if "constructor_cast_expression" in type_facts and not any(
        kind == "construct" for _, kind, _, _ in expression_tuples
    ):
        errors.append(f"{field}: HIR source-map missing constructor cast expression")
    if "scalar_literals" in type_facts and not any(
        kind == "literal" for _, kind, _, _ in expression_tuples
    ):
        errors.append(f"{field}: HIR source-map missing scalar literal expressions")

    if "return_statement" in source_facts and not any(
        kind == "return" for kind, _, _ in statement_triples
    ):
        errors.append(f"{field}: HIR source-map missing return statement")
    if "local_variable_declarations" in source_facts and not any(
        kind == "decl" for kind, _, _ in statement_triples
    ):
        errors.append(f"{field}: HIR source-map missing local declarations")
    if "if_statement" in source_facts and not any(
        kind == "if" for kind, _, _ in statement_triples
    ):
        errors.append(f"{field}: HIR source-map missing if statement")
    if "storage_buffer_declaration" in source_facts and not any(
        owner == "resource-type" for owner, _, _ in type_triples
    ):
        errors.append(f"{field}: HIR source-map missing storage-buffer declaration")
    if "storage_buffer_read" in source_facts and not any(
        statement == "decl" and kind == "identifier" and value in storage_buffer_names
        for statement, kind, value, _ in expression_tuples
    ):
        errors.append(f"{field}: HIR source-map missing storage-buffer read")
    if "storage_buffer_write" in source_facts and not any(
        statement == "assign" and kind == "identifier" and value in storage_buffer_names
        for statement, kind, value, _ in expression_tuples
    ):
        errors.append(f"{field}: HIR source-map missing storage-buffer write")
    if "storage_image_declaration" in source_facts and not any(
        owner == "resource-type"
        and isinstance(typ, str)
        and (typ.endswith("image2D") or typ.endswith("image2DArray"))
        for owner, _, typ in type_triples
    ):
        errors.append(f"{field}: HIR source-map missing storage-image declaration")
    if "storage_image_load" in source_facts and not any(
        kind == "call" and value == "imageLoad"
        for _, kind, value, _ in expression_tuples
    ):
        errors.append(f"{field}: HIR source-map missing imageLoad call")
    if "storage_image_store" in source_facts and not any(
        kind == "call" and value == "imageStore"
        for _, kind, value, _ in expression_tuples
    ):
        errors.append(f"{field}: HIR source-map missing imageStore call")


def check_fixture_hir_dump_parity(
    root: Path, cglc: Path, errors: list[str]
) -> dict[str, int]:
    inventory = load_json(root / INVENTORY_PATH)
    cglc_path = cglc if cglc.is_absolute() else root / cglc
    if not cglc_path.exists():
        errors.append(f"--cglc does not exist: {cglc_path}")
        return {"hir_dump_parity_fixtures": 0}

    fixtures = inventory.get("fixtures") if isinstance(inventory, dict) else []
    if not isinstance(fixtures, list):
        errors.append(f"{INVENTORY_PATH}: fixtures must be a list for HIR dump parity")
        return {"hir_dump_parity_fixtures": 0}

    checked = 0
    for index, item in enumerate(fixtures):
        field = f"{INVENTORY_PATH}: fixtures[{index}].hirDumpParity"
        if not isinstance(item, dict) or not isinstance(item.get("path"), str):
            continue
        fixture = item["path"]
        if not (root / fixture).exists():
            errors.append(f"{field}: fixture does not exist: {fixture}")
            continue
        try:
            hir_text = run_cglc_dump(cglc_path, fixture, "hir", cwd=root)
            source_map_text = run_cglc_dump(
                cglc_path, fixture, "hir-source-map", cwd=root
            )
        except RuntimeError as error:
            errors.append(f"{field}: {error}")
            continue
        check_hir_text_parity(item, field, hir_text, errors)
        check_hir_source_map_parity(item, field, source_map_text, errors)
        checked += 1

    return {"hir_dump_parity_fixtures": checked}


def check_inventory(root: Path) -> tuple[list[str], dict[str, int]]:
    inventory_path = root / INVENTORY_PATH
    if not inventory_path.exists():
        return [f"missing {INVENTORY_PATH}"], {
            "fixtures": 0,
            "resource_binding_fixtures": 0,
            "control_flow_slices": 0,
        }
    try:
        inventory = load_json(inventory_path)
    except ValueError as error:
        return [f"{INVENTORY_PATH}: {error}"], {
            "fixtures": 0,
            "resource_binding_fixtures": 0,
            "control_flow_slices": 0,
        }
    if not isinstance(inventory, dict):
        return [f"{INVENTORY_PATH}: inventory must be an object"], {
            "fixtures": 0,
            "resource_binding_fixtures": 0,
            "control_flow_slices": 0,
        }

    errors: list[str] = []
    if inventory.get("schemaVersion") != 1:
        errors.append(f"{INVENTORY_PATH}: schemaVersion must be 1")
    if inventory.get("kind") != INVENTORY_KIND:
        errors.append(f"{INVENTORY_PATH}: kind must be {INVENTORY_KIND!r}")
    check_required_facts(inventory, errors)
    blocked_family_ids = check_blocked_families(inventory, errors)

    fixtures = inventory.get("fixtures")
    if not isinstance(fixtures, list) or not fixtures:
        errors.append(f"{INVENTORY_PATH}: fixtures must be a non-empty list")
        return errors, {
            "fixtures": 0,
            "resource_binding_fixtures": 0,
            "control_flow_slices": 0,
        }

    fixture_paths: list[str] = []
    resource_binding_fixtures = 0
    control_flow_slices = 0
    for index, item in enumerate(fixtures):
        field = f"{INVENTORY_PATH}: fixtures[{index}]"
        record = require_object(item, field, errors)
        if not record:
            continue
        path = validate_relative_path(root, record.get("path"), f"{field}.path", errors)
        if path is not None:
            fixture_paths.append(path)
        stage = require_string(record.get("stage"), f"{field}.stage", errors)
        require_string(record.get("entryPoint"), f"{field}.entryPoint", errors)

        family_list = require_string_list(
            record.get("allowedHirFamilies"),
            f"{field}.allowedHirFamilies",
            errors,
        )
        require_unique(family_list, f"{field}.allowedHirFamilies", errors)
        families = set(family_list)
        blocked_overlap = sorted(families & set(blocked_family_ids))
        if blocked_overlap:
            errors.append(
                f"{field}.allowedHirFamilies overlaps unsupportedHirFamilies: "
                + ", ".join(blocked_overlap)
            )
        source_facts = require_string_list(
            record.get("sourceLocationFacts"),
            f"{field}.sourceLocationFacts",
            errors,
        )
        require_unique(source_facts, f"{field}.sourceLocationFacts", errors)
        type_facts = require_string_list(
            record.get("typeFacts"),
            f"{field}.typeFacts",
            errors,
        )
        require_unique(type_facts, f"{field}.typeFacts", errors)
        resource_facts = require_object(
            record.get("resourceFacts"), f"{field}.resourceFacts", errors
        )
        check_resource_facts(resource_facts, f"{field}.resourceFacts", stage, errors)
        if any(
            resource_facts.get(collection) for collection in RESOURCE_FACT_COLLECTIONS
        ):
            resource_binding_fixtures += 1
        if CONTROL_FLOW_FAMILY in families:
            control_flow_slices += 1

        check_fixture_parity_requirements(
            record,
            field,
            source_facts,
            type_facts,
            resource_facts,
            errors,
        )
        check_fixture_parity_report(
            record,
            field,
            source_facts,
            type_facts,
            families,
            resource_facts,
            blocked_family_ids,
            errors,
        )
        check_lowering_evidence(
            record,
            field,
            stage,
            record.get("entryPoint")
            if isinstance(record.get("entryPoint"), str)
            else None,
            source_facts,
            type_facts,
            families,
            resource_facts,
            errors,
        )

    require_unique(fixture_paths, f"{INVENTORY_PATH}: fixtures[].path", errors)
    return errors, {
        "fixtures": len(fixtures),
        "resource_binding_fixtures": resource_binding_fixtures,
        "control_flow_slices": control_flow_slices,
    }


def source_file_report_fields() -> dict[str, object]:
    return {
        "required": True,
        "fields": ["path", "sourceLocationFacts.source_file"],
    }


def entry_point_report_fields() -> dict[str, object]:
    return {"required": True, "fields": ["stage", "entryPoint"]}


def entry_point_identity_report_fields() -> dict[str, object]:
    return {"required": True, "fields": expected_entry_point_identity_fields()}


def local_size_report_fields() -> dict[str, object]:
    return {"required": True, "fields": ["resourceFacts.localSize"]}


def workgroup_size_report_fields() -> dict[str, object]:
    return {"required": True, "fields": expected_workgroup_size_fields()}


def resource_binding_report_fields(resource_facts: dict[str, Any]) -> dict[str, object]:
    return {
        "required": True,
        "fields": expected_resource_binding_fields(resource_facts),
    }


def target_independent_resource_metadata_report_fields(
    resource_facts: dict[str, Any],
) -> dict[str, object]:
    return {
        "required": True,
        "fields": expected_target_independent_resource_metadata_fields(resource_facts),
    }


def type_fact_report_fields(type_facts: list[str]) -> dict[str, object]:
    return {"required": True, "fields": expected_type_fact_fields(type_facts)}


def diagnostics_provenance_fields(
    source_facts: list[str], type_facts: list[str]
) -> dict[str, object]:
    return {
        "required": True,
        "fields": expected_diagnostics_provenance_fields(source_facts, type_facts),
    }


def source_map_debug_preservation_fields(
    source_facts: list[str], type_facts: list[str]
) -> dict[str, object]:
    return {
        "required": True,
        "fields": expected_source_map_debug_preservation_fields(
            source_facts, type_facts
        ),
    }


def control_flow_report_fields(
    families: set[str], source_facts: list[str], type_facts: list[str]
) -> dict[str, object]:
    slice_name, fields = expected_control_flow_report(
        families, source_facts, type_facts
    )
    return {"required": True, "slice": slice_name, "fields": fields}


def blocked_family_rationale_report_fields(
    blocked_family_ids: list[str],
) -> dict[str, object]:
    return {
        "required": True,
        "fields": list(BLOCKED_FAMILY_REPORT_FIELDS),
        "families": blocked_family_ids,
    }


def build_parity_requirements(record: dict[str, Any]) -> dict[str, object]:
    source_facts = [
        item for item in record["sourceLocationFacts"] if isinstance(item, str)
    ]
    type_facts = [item for item in record["typeFacts"] if isinstance(item, str)]
    resource_facts = require_object(
        record["resourceFacts"], "self-test.resourceFacts", []
    )
    return {
        "sourceLocations": {"required": True, "fields": source_facts},
        "typeFacts": {"required": True, "fields": type_facts},
        "entryPoint": {
            "required": True,
            "fields": ["stage", "entryPoint", "resourceFacts.localSize"],
        },
        "resources": {
            "required": True,
            "fields": expected_resource_requirement_fields(resource_facts),
        },
        "targetIndependentResourceMetadata": {
            "required": True,
            "fields": expected_target_independent_resource_metadata_fields(
                resource_facts
            ),
        },
        "diagnosticsProvenance": diagnostics_provenance_fields(
            source_facts, type_facts
        ),
        "sourceMapDebugPreservation": source_map_debug_preservation_fields(
            source_facts, type_facts
        ),
    }


def build_report_fields(record: dict[str, Any]) -> dict[str, object]:
    families = {item for item in record["allowedHirFamilies"] if isinstance(item, str)}
    source_facts = [
        item for item in record["sourceLocationFacts"] if isinstance(item, str)
    ]
    type_facts = [item for item in record["typeFacts"] if isinstance(item, str)]
    resource_facts = require_object(
        record["resourceFacts"], "self-test.resourceFacts", []
    )
    blocked_family_ids = [
        "remaining_texture_image_intrinsics",
        "descriptor_indexing_and_nonuniform",
        "crosstl_examples_and_backend_policy",
    ]
    return {
        "sourceFile": source_file_report_fields(),
        "entryPoint": entry_point_report_fields(),
        "entryPointIdentity": entry_point_identity_report_fields(),
        "localSize": local_size_report_fields(),
        "workgroupSize": workgroup_size_report_fields(),
        "resourceBindings": resource_binding_report_fields(resource_facts),
        "targetIndependentResourceMetadata": (
            target_independent_resource_metadata_report_fields(resource_facts)
        ),
        "typeFacts": type_fact_report_fields(type_facts),
        "diagnosticsProvenance": diagnostics_provenance_fields(
            source_facts, type_facts
        ),
        "sourceMapDebugPreservation": source_map_debug_preservation_fields(
            source_facts, type_facts
        ),
        "controlFlowSlice": control_flow_report_fields(
            families, source_facts, type_facts
        ),
        "blockedFamilyRationale": blocked_family_rationale_report_fields(
            blocked_family_ids
        ),
    }


def build_lowering_evidence(record: dict[str, Any]) -> dict[str, object]:
    families = {item for item in record["allowedHirFamilies"] if isinstance(item, str)}
    source_facts = [
        item for item in record["sourceLocationFacts"] if isinstance(item, str)
    ]
    type_facts = [item for item in record["typeFacts"] if isinstance(item, str)]
    resource_facts = require_object(
        record["resourceFacts"], "self-test.resourceFacts", []
    )
    stage = record["stage"] if isinstance(record.get("stage"), str) else None
    entry_point = (
        record["entryPoint"] if isinstance(record.get("entryPoint"), str) else None
    )
    return expected_lowering_evidence(
        stage, entry_point, source_facts, type_facts, families, resource_facts
    )


def valid_self_test_inventory() -> dict[str, Any]:
    minimal_resource_facts: dict[str, Any] = {
        "localSize": [1, 1, 1],
        "descriptors": [],
        "storageBuffers": [],
        "storageImages": [],
        "textures": [],
        "samplers": [],
        "targetIndependentResourceMetadata": [],
    }
    storage_resource_facts: dict[str, Any] = {
        "localSize": [1, 1, 1],
        "descriptors": [
            {
                "stage": "compute",
                "name": "values",
                "kind": "storageBuffer",
                "set": 0,
                "binding": 0,
            }
        ],
        "storageBuffers": [
            {
                "name": "values",
                "type": "float*",
                "elementType": "float",
                "addressSpace": "storage",
                "writeAccess": True,
            }
        ],
        "storageImages": [],
        "textures": [],
        "samplers": [],
        "targetIndependentResourceMetadata": [
            {
                "stage": "compute",
                "name": "values",
                "kind": "storageBuffer",
                "sourceType": "float*",
                "elementType": "float",
                "addressSpace": "storage",
                "access": "read_write",
                "set": 0,
                "binding": 0,
                "targetIndependent": True,
            }
        ],
    }
    fixtures: list[dict[str, Any]] = [
        {
            "path": "tests/fixtures/MinimalComputeShader.cgl",
            "stage": "compute",
            "entryPoint": "main",
            "allowedHirFamilies": ["module_stages_and_entry_points"],
            "sourceLocationFacts": [
                "source_file",
                "shader_module",
                "compute_stage",
                "entry_point",
                "layout_local_size",
                "return_statement",
            ],
            "typeFacts": ["void_entry_point"],
            "resourceFacts": minimal_resource_facts,
        },
        {
            "path": "tests/fixtures/IfComputeShader.cgl",
            "stage": "compute",
            "entryPoint": "main",
            "allowedHirFamilies": [
                "module_stages_and_entry_points",
                "control_flow_and_statements",
            ],
            "sourceLocationFacts": [
                "source_file",
                "shader_module",
                "compute_stage",
                "entry_point",
                "layout_local_size",
                "if_statement",
                "then_block_assignment",
                "else_block_assignment",
                "return_statement",
            ],
            "typeFacts": [
                "void_entry_point",
                "branch_condition_bool",
                "assignment_expression_result_types",
                "unary_expression_result_types",
            ],
            "resourceFacts": storage_resource_facts,
        },
    ]
    for fixture in fixtures:
        fixture[PARITY_REQUIREMENT_KEY] = build_parity_requirements(fixture)
        fixture[REPORT_FIELD_KEY] = build_report_fields(fixture)
        fixture[LOWERING_EVIDENCE_KEY] = build_lowering_evidence(fixture)
    return {
        "schemaVersion": 1,
        "kind": INVENTORY_KIND,
        "status": "experimental-fixture-limited",
        "fixtures": fixtures,
        "unsupportedHirFamilies": [
            {
                "id": "remaining_texture_image_intrinsics",
                "reason": (
                    "Texture, sampler, image, and texture intrinsic HIR families "
                    "are outside the fixture-limited MLIR experiment."
                ),
            },
            {
                "id": "descriptor_indexing_and_nonuniform",
                "reason": (
                    "Descriptor arrays, dynamic indexing, and nonuniform metadata "
                    "require target legalization parity first."
                ),
            },
            {
                "id": "crosstl_examples_and_backend_policy",
                "reason": (
                    "CrossTL examples and backend unsupported-policy fixtures are "
                    "outside the fixture-limited MLIR experiment."
                ),
            },
        ],
        "requiredFacts": {
            "sourceLocations": [
                {
                    "id": "fixture_source_locations",
                    "required": True,
                    "description": (
                        "Admitted fixtures must name source locations used by "
                        "the parity report."
                    ),
                }
            ],
            "types": [
                {
                    "id": "fixture_type_facts",
                    "required": True,
                    "description": (
                        "Admitted fixtures must name type facts used by the "
                        "parity report."
                    ),
                }
            ],
            "resources": [
                {
                    "id": "fixture_resource_facts",
                    "required": True,
                    "description": (
                        "Admitted fixtures must name workgroup size and resource "
                        "binding facts."
                    ),
                }
            ],
            "targetIndependentResourceMetadata": [
                {
                    "id": "fixture_target_independent_resource_metadata",
                    "required": True,
                    "description": (
                        "Admitted fixtures must name target-independent resource "
                        "metadata separately from target backend bindings."
                    ),
                }
            ],
            "diagnosticsProvenance": [
                {
                    "id": "fixture_diagnostics_provenance",
                    "required": True,
                    "description": (
                        "Admitted fixtures must tie diagnostics provenance to "
                        "source, type, and entry-point facts."
                    ),
                }
            ],
            "sourceMapDebugPreservation": [
                {
                    "id": "fixture_source_map_debug_artifact_pair",
                    "required": True,
                    "description": (
                        "Admitted fixtures must preserve the debug metadata and "
                        "HIR source-map artifact pair as report-only evidence."
                    ),
                }
            ],
        },
    }


def write_self_test_repo(root: Path, inventory: dict[str, Any]) -> None:
    (root / INVENTORY_PATH.parent).mkdir(parents=True, exist_ok=True)
    (root / "tests/fixtures").mkdir(parents=True, exist_ok=True)
    for fixture in inventory["fixtures"]:
        (root / fixture["path"]).write_text("shader main() {}\n", encoding="utf-8")
    (root / INVENTORY_PATH).write_text(
        json.dumps(inventory, indent=2) + "\n", encoding="utf-8"
    )


def expect_self_test_failure(
    root: Path, inventory: dict[str, Any], label: str, expected: str
) -> list[str]:
    write_self_test_repo(root, inventory)
    errors, _ = check_inventory(root)
    if not errors:
        return [f"self-test {label}: expected validation failure"]
    joined = "\n".join(errors)
    if expected not in joined:
        return [f"self-test {label}: expected {expected!r} in errors, got {joined!r}"]
    return []


def run_self_test() -> list[str]:
    errors: list[str] = []
    with tempfile.TemporaryDirectory(prefix="crossgl-mlir-fixture-parity-") as temp:
        root = Path(temp)
        inventory = valid_self_test_inventory()
        write_self_test_repo(root, inventory)
        valid_errors, summary = check_inventory(root)
        if valid_errors:
            errors.append(f"self-test valid inventory failed: {valid_errors!r}")
        if summary["fixtures"] != 2 or summary["control_flow_slices"] != 1:
            errors.append(f"self-test summary mismatch: {summary!r}")

        missing_section = copy.deepcopy(inventory)
        missing_section["fixtures"][0][REPORT_FIELD_KEY].pop("localSize")
        errors.extend(
            expect_self_test_failure(
                root,
                missing_section,
                "missing-local-size-section",
                "missing required section(s): localSize",
            )
        )

        missing_resource_field = copy.deepcopy(inventory)
        missing_resource_field["fixtures"][0][REPORT_FIELD_KEY]["resourceBindings"][
            "fields"
        ].remove("resourceFacts.samplers")
        errors.extend(
            expect_self_test_failure(
                root,
                missing_resource_field,
                "missing-resource-binding-field",
                "resourceBindings.fields must be",
            )
        )

        missing_metadata_field = copy.deepcopy(inventory)
        missing_metadata_field["fixtures"][1][REPORT_FIELD_KEY][
            "targetIndependentResourceMetadata"
        ]["fields"].remove(
            "resourceFacts.targetIndependentResourceMetadata[].targetIndependent"
        )
        errors.extend(
            expect_self_test_failure(
                root,
                missing_metadata_field,
                "missing-target-independent-resource-metadata-field",
                "targetIndependentResourceMetadata.fields must be",
            )
        )

        target_abi_metadata_field = copy.deepcopy(inventory)
        target_abi_metadata_field["fixtures"][1]["resourceFacts"][
            "targetIndependentResourceMetadata"
        ][0]["abi"] = "hlsl"
        errors.extend(
            expect_self_test_failure(
                root,
                target_abi_metadata_field,
                "target-abi-resource-metadata-field",
                "targetIndependentResourceMetadata[0] has unknown key(s): abi",
            )
        )

        missing_control_field = copy.deepcopy(inventory)
        missing_control_field["fixtures"][1][REPORT_FIELD_KEY]["controlFlowSlice"][
            "fields"
        ].remove("sourceLocationFacts.if_statement")
        errors.extend(
            expect_self_test_failure(
                root,
                missing_control_field,
                "missing-control-flow-field",
                "controlFlowSlice.fields must be",
            )
        )

        missing_lowering_evidence = copy.deepcopy(inventory)
        missing_lowering_evidence["fixtures"][0].pop(LOWERING_EVIDENCE_KEY)
        errors.extend(
            expect_self_test_failure(
                root,
                missing_lowering_evidence,
                "missing-lowering-evidence",
                "loweringEvidence must be an object",
            )
        )

        stale_resource_mode = copy.deepcopy(inventory)
        stale_resource_mode["fixtures"][1][LOWERING_EVIDENCE_KEY]["resourceMode"] = (
            RESOURCE_MODE_EMPTY
        )
        errors.extend(
            expect_self_test_failure(
                root,
                stale_resource_mode,
                "stale-resource-mode",
                f"resourceMode must be {RESOURCE_MODE_STORAGE_BUFFER!r}",
            )
        )

        stale_control_flow_category = copy.deepcopy(inventory)
        stale_control_flow_category["fixtures"][1][LOWERING_EVIDENCE_KEY][
            "controlFlowCategory"
        ] = CONTROL_FLOW_CATEGORY_STRAIGHT_LINE
        errors.extend(
            expect_self_test_failure(
                root,
                stale_control_flow_category,
                "stale-control-flow-category",
                "controlFlowCategory must be "
                f"{CONTROL_FLOW_CATEGORY_STRUCTURED_IF_ELSE!r}",
            )
        )

        missing_source_map_debug_field = copy.deepcopy(inventory)
        missing_source_map_debug_field["fixtures"][0][REPORT_FIELD_KEY][
            "sourceMapDebugPreservation"
        ]["fields"].remove("debugMetadata.hirSourceLocations")
        errors.extend(
            expect_self_test_failure(
                root,
                missing_source_map_debug_field,
                "missing-source-map-debug-field",
                "sourceMapDebugPreservation.fields must be",
            )
        )

        duplicate_source_fact = copy.deepcopy(inventory)
        duplicate_source_fact["fixtures"][0]["sourceLocationFacts"].append(
            "source_file"
        )
        duplicate_source_fact["fixtures"][0][PARITY_REQUIREMENT_KEY] = (
            build_parity_requirements(duplicate_source_fact["fixtures"][0])
        )
        duplicate_source_fact["fixtures"][0][REPORT_FIELD_KEY] = build_report_fields(
            duplicate_source_fact["fixtures"][0]
        )
        errors.extend(
            expect_self_test_failure(
                root,
                duplicate_source_fact,
                "duplicate-source-location-fact",
                "sourceLocationFacts must not contain duplicate entries: source_file",
            )
        )
    return errors


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--root",
        type=Path,
        default=Path.cwd(),
        help="CrossGL-Compiler repository root",
    )
    parser.add_argument(
        "--cglc",
        type=Path,
        help="cglc executable used by optional --hir-dump-parity checks",
    )
    parser.add_argument(
        "--hir-dump-parity",
        action="store_true",
        help=(
            "compare admitted fixture inventory facts with cglc dump-ir HIR and "
            "HIR source-map output at --opt-level O0"
        ),
    )
    parser.add_argument(
        "--self-test",
        action="store_true",
        help="run internal checker self-tests instead of auditing a repository",
    )
    return parser.parse_args(argv)


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    if args.self_test:
        errors = run_self_test()
        summary = None
    else:
        root = args.root.resolve()
        errors, summary = check_inventory(root)
        if args.hir_dump_parity:
            if args.cglc is None:
                errors.append("--hir-dump-parity requires --cglc")
            elif not errors:
                summary.update(check_fixture_hir_dump_parity(root, args.cglc, errors))

    if errors:
        for error in errors:
            print(f"error: {error}", file=sys.stderr)
        return 1

    if args.self_test:
        print("MLIR fixture parity report self-test passed")
    else:
        assert summary is not None
        hir_dump_summary = (
            f"{summary['hir_dump_parity_fixtures']} HIR dump parity fixtures; "
            if args.hir_dump_parity
            else ""
        )
        print(
            "MLIR fixture parity report passed "
            f"({summary['fixtures']} admitted fixtures; "
            f"{summary['resource_binding_fixtures']} resource-binding fixtures; "
            f"{summary['control_flow_slices']} control-flow slices; "
            f"{hir_dump_summary}"
            "fields: sourceFile, entryPoint, entryPointIdentity, "
            "localSize, workgroupSize, resourceBindings, "
            "targetIndependentResourceMetadata, typeFacts, "
            "diagnosticsProvenance, sourceMapDebugPreservation, controlFlowSlice, "
            "blockedFamilyRationale, loweringEvidence)"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
