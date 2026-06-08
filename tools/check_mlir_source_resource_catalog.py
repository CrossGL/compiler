#!/usr/bin/env python3
"""Generate and validate MLIR source/resource preservation evidence.

The catalog is derived from committed report-only fixture inventories. It does
not import compiler modules, lower HIR, probe MLIR, or inspect package outputs.
It also keeps entry-point identity and target-independent type facts visible in
the source/resource readiness inventory.
"""

from __future__ import annotations

import argparse
import copy
import json
import sys
import tempfile
from pathlib import Path
from typing import Any


CATALOG_PATH = Path("experimental/mlir/source_resource_catalog.v0.json")
BOUNDARY_PATH = Path("experimental/mlir/boundary_inventory.v0.json")
FIXTURE_PATH = Path("experimental/mlir/fixture_inventory.json")
MANIFEST_PATH = Path("experimental/mlir/experiment_manifest.json")
OP_TYPE_CATALOG_PATH = Path("experimental/mlir/op_type_catalog.v0.json")

CATALOG_KIND = "crossgl-mlir-source-resource-catalog-v0"
BOUNDARY_KIND = "crossgl-mlir-boundary-inventory-v0"
FIXTURE_KIND = "crossgl-mlir-experiment-fixture-inventory"
MANIFEST_KIND = "crossgl-mlir-experiment-manifest"
OP_TYPE_CATALOG_KIND = "crossgl-mlir-op-type-catalog-v0"
OP_TYPE_CATALOG_STATUS = "report-only-derived-from-hir-facts"
CATALOG_STATUS = "report-only-derived-from-hir-source-resource-facts"
DERIVED_FROM = (
    BOUNDARY_PATH.as_posix(),
    FIXTURE_PATH.as_posix(),
    MANIFEST_PATH.as_posix(),
    OP_TYPE_CATALOG_PATH.as_posix(),
)
REQUIRED_TOP_LEVEL_KEYS = (
    "schemaVersion",
    "kind",
    "status",
    "scope",
    "generation",
    "sourceMapDebugContract",
    "resourceContract",
    "catalogConsistency",
    "parityCoverageMatrix",
    "fixtures",
    "coverageSummary",
)
GENERATION_KEYS = (
    "deterministic",
    "derivedFrom",
    "optionalMlirToolingRequired",
    "productionLinked",
    "normalBuildRequired",
    "separatesPseudoMlir",
)
FIXTURE_KEYS = (
    "path",
    "stage",
    "entryPoint",
    "experimentSlice",
    "loweringStatus",
    "resourceFactMode",
    "entryPointIdentity",
    "sourceLocations",
    "targetIndependentTypeFacts",
    "sourceMapDebugFacts",
    "resourceFacts",
    "targetIndependentResourceMetadata",
    "sourceResourceEntrypointPreservation",
    "parityEvidence",
)
ENTRY_POINT_IDENTITY_KEYS = (
    "requiredFields",
    "manifestFacts",
    "missingManifestFields",
)
SOURCE_LOCATION_KEYS = (
    "inventoryFacts",
    "manifestFacts",
    "requiredByBoundary",
    "missingFromManifest",
)
TYPE_FACT_KEYS = (
    "inventoryFacts",
    "manifestFacts",
    "missingFromManifest",
)
RESOURCE_FACT_KEYS = (
    "localSize",
    "manifestFields",
    "descriptors",
    "storageBuffers",
    "storageImages",
    "textures",
    "samplers",
    "emptyCollections",
    "missingManifestFields",
)
RESOURCE_METADATA_KEYS = (
    "manifestFields",
    "records",
    "missingManifestFields",
)
CATALOG_CONSISTENCY_KEYS = (
    "opTypeCatalog",
    "fixtureUniverse",
    "targetIndependentTypeFacts",
    "operationFixtureCoverage",
)
OP_TYPE_CATALOG_REFERENCE_KEYS = ("path", "kind", "status")
CATALOG_FIXTURE_UNIVERSE_KEYS = (
    "sourceResourceFixtures",
    "opTypeCatalogFixtures",
    "missingFromOpTypeCatalog",
    "missingFromSourceResourceCatalog",
    "matches",
)
CATALOG_TYPE_FACT_UNIVERSE_KEYS = (
    "sourceResourceFacts",
    "opTypeCatalogFacts",
    "missingFromOpTypeCatalog",
    "missingFromSourceResourceCatalog",
    "matches",
)
CATALOG_OPERATION_FIXTURE_COVERAGE_KEYS = (
    "operationCount",
    "fixtureCoverageRowCount",
    "referencedFixtures",
    "fixturesOutsideSourceResourceCatalog",
    "sourceResourceFixturesWithoutOperationCoverage",
    "missingRequiredFactRows",
    "matches",
)
CATALOG_MISSING_REQUIRED_FACT_ROW_KEYS = (
    "operation",
    "path",
    "missingRequiredFacts",
)
SOURCE_RESOURCE_ENTRYPOINT_KEYS = (
    "requiredFields",
    "sourceEntrypointFields",
    "resourceFields",
    "targetIndependentResourceMetadataFields",
    "manifestRequiredFields",
    "missingManifestFields",
)
PARITY_EVIDENCE_KEYS = (
    "entryPointRequirementFields",
    "sourceLocationRequirementFields",
    "typeFactRequirementFields",
    "sourceMapDebugRequirementFields",
    "resourceRequirementFields",
    "targetIndependentResourceMetadataRequirementFields",
    "reportFields",
)
REPORT_FIELD_KEYS = (
    "sourceFile",
    "entryPoint",
    "entryPointIdentity",
    "workgroupSize",
    "resourceBindings",
    "targetIndependentResourceMetadata",
    "typeFacts",
    "sourceMapDebugPreservation",
)
ENTRY_POINT_IDENTITY_FIELDS = (
    "stage",
    "entryPoint",
    "sourceLocationFacts.shader_module",
    "sourceLocationFacts.compute_stage",
    "sourceLocationFacts.entry_point",
    "typeFacts.void_entry_point",
    "resourceFacts.localSize",
)
ENTRY_POINT_IDENTITY_REPORT_FIELDS = ENTRY_POINT_IDENTITY_FIELDS[:-1]
SOURCE_RESOURCE_ENTRYPOINT_FIELDS = (
    "path",
    "stage",
    "entryPoint",
    "sourceLocationFacts.source_file",
    "sourceLocationFacts.shader_module",
    "sourceLocationFacts.compute_stage",
    "sourceLocationFacts.entry_point",
    "sourceLocationFacts.layout_local_size",
    "typeFacts.void_entry_point",
    "resourceFacts.localSize",
)
REQUIRED_SOURCE_MAP_DEBUG_FACTS = (
    "manifest.artifacts.debugMetadata",
    "manifest.artifacts.hirSourceMap",
    "ir/debug-metadata.json",
    "ir/hir-source-map.json",
    "debugMetadata.schemaVersion=11",
    "hirSourceMap.schemaVersion=7",
    "debugMetadata.hirSourceLocations",
    "hirSourceMap.hirSourceLocations",
    "hirSourceMap.categoryCounts",
    "hirSourceMap.filters.activeCount=0",
    "hirSourceMap.pagination.activeCount=0",
    "hirSourceMap.records.enabled=false",
)
RESOURCE_COLLECTION_FIELDS = (
    "resourceFacts.descriptors",
    "resourceFacts.storageBuffers",
    "resourceFacts.storageImages",
    "resourceFacts.textures",
    "resourceFacts.samplers",
)
RESOURCE_METADATA_COLLECTION = "resourceFacts.targetIndependentResourceMetadata"
RESOURCE_DESCRIPTOR_ITEM_FIELDS = (
    "resourceFacts.descriptors[].stage",
    "resourceFacts.descriptors[].name",
    "resourceFacts.descriptors[].kind",
    "resourceFacts.descriptors[].set",
    "resourceFacts.descriptors[].binding",
)
RESOURCE_STORAGE_BUFFER_ITEM_FIELDS = (
    "resourceFacts.storageBuffers[].name",
    "resourceFacts.storageBuffers[].type",
    "resourceFacts.storageBuffers[].elementType",
    "resourceFacts.storageBuffers[].addressSpace",
    "resourceFacts.storageBuffers[].writeAccess",
)
RESOURCE_TEXTURE_ITEM_FIELDS = (
    "resourceFacts.textures[].name",
    "resourceFacts.textures[].type",
    "resourceFacts.textures[].sampledType",
    "resourceFacts.textures[].dimension",
    "resourceFacts.textures[].arrayed",
    "resourceFacts.textures[].comparison",
    "resourceFacts.textures[].set",
    "resourceFacts.textures[].binding",
)
RESOURCE_SAMPLER_ITEM_FIELDS = (
    "resourceFacts.samplers[].name",
    "resourceFacts.samplers[].type",
    "resourceFacts.samplers[].comparison",
    "resourceFacts.samplers[].set",
    "resourceFacts.samplers[].binding",
)
RESOURCE_METADATA_ITEM_FIELDS = (
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
PARITY_COVERAGE_MATRIX_KEYS = ("status", "dimensions", "fixtures")
PARITY_COVERAGE_MATRIX_STATUS_COVERED = "covered"
PARITY_COVERAGE_MATRIX_STATUS_INCOMPLETE = "incomplete"
PARITY_COVERAGE_DIMENSIONS = (
    "sourceLocations",
    "entryPointIdentity",
    "resources",
    "targetIndependentResourceMetadata",
    "sourceResourceEntrypointPreservation",
    "sourceMapDebugPreservation",
)
PARITY_COVERAGE_DIMENSION_KEYS = (
    "name",
    "fixtureCount",
    "coveredFixtureCount",
    "missingFixtureCount",
    "requiredForEveryFixture",
)
PARITY_COVERAGE_FIXTURE_KEYS = ("path", "status", "dimensions")
PARITY_COVERAGE_DIMENSION_RECORD_KEYS = (
    "covered",
    "requiredFieldCount",
    "manifestFieldCount",
    "missingManifestFields",
)


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def write_json(path: Path, value: dict[str, Any]) -> None:
    path.write_text(
        json.dumps(value, indent=2, sort_keys=False) + "\n", encoding="utf-8"
    )


def load_json(path: Path) -> Any:
    try:
        return json.loads(read_text(path))
    except json.JSONDecodeError as error:
        raise ValueError(f"invalid JSON: {error}") from error


def require_loaded_object(path: Path, kind: str) -> dict[str, Any]:
    value = load_json(path)
    if not isinstance(value, dict):
        raise ValueError(f"{path}: must be a JSON object")
    if value.get("kind") != kind:
        raise ValueError(f"{path}: kind must be {kind!r}")
    return value


def require_object(value: object, field: str, errors: list[str]) -> dict[str, Any]:
    if not isinstance(value, dict):
        errors.append(f"{field} must be an object")
        return {}
    return value


def require_list(value: object, field: str, errors: list[str]) -> list[Any]:
    if not isinstance(value, list):
        errors.append(f"{field} must be a list")
        return []
    return value


def string_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, str)]


def sorted_unique(values: list[str]) -> list[str]:
    return sorted(set(values))


def ordered_unique(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        if value not in seen:
            seen.add(value)
            result.append(value)
    return result


def field_list(section: object) -> list[str]:
    if not isinstance(section, dict):
        return []
    return string_list(section.get("fields"))


def fixture_records(fixture_inventory: dict[str, Any]) -> dict[str, dict[str, Any]]:
    records: dict[str, dict[str, Any]] = {}
    for item in fixture_inventory.get("fixtures", []):
        if isinstance(item, dict) and isinstance(item.get("path"), str):
            records[item["path"]] = item
    return records


def manifest_records(manifest: dict[str, Any]) -> dict[str, dict[str, Any]]:
    records: dict[str, dict[str, Any]] = {}
    for item in manifest.get("eligibleFixtures", []):
        if isinstance(item, dict) and isinstance(item.get("path"), str):
            records[item["path"]] = item
    return records


def boundary_records(boundary: dict[str, Any]) -> dict[str, dict[str, Any]]:
    records: dict[str, dict[str, Any]] = {}
    for item in boundary.get("fixtureBoundary", []):
        if isinstance(item, dict) and isinstance(item.get("path"), str):
            records[item["path"]] = item
    return records


def required_source_facts_for_fixture(
    boundary: dict[str, Any], fixture_path: str, fixture_source_facts: list[str]
) -> list[str]:
    facts: list[str] = []
    fixture_source_fact_set = set(fixture_source_facts)
    for operation in boundary.get("operations", []):
        if not isinstance(operation, dict):
            continue
        if "source_locations" not in string_list(operation.get("preserves")):
            continue
        if fixture_path not in string_list(operation.get("fixtures")):
            continue
        for fact in string_list(operation.get("requiredFixtureFacts")):
            if fact.startswith("resourceFacts.") or fact.startswith("typeFacts."):
                continue
            if fact in {"stage", "entryPoint"}:
                continue
            if fact not in fixture_source_fact_set:
                continue
            facts.append(fact)
    return sorted_unique(facts)


def missing_fields(required: list[str], available: list[str]) -> list[str]:
    available_set = set(available)
    return [item for item in required if item not in available_set]


def sorted_difference(left: list[str], right: list[str]) -> list[str]:
    return sorted(set(left) - set(right))


def prefixed_fact_fields(prefix: str, facts: list[str]) -> list[str]:
    return [f"{prefix}.{fact}" for fact in facts]


def expected_resource_manifest_fields(resource_facts: dict[str, Any]) -> list[str]:
    fields = ["resourceFacts.localSize"]
    fields.append("resourceFacts.descriptors")
    if resource_facts.get("descriptors"):
        fields.extend(RESOURCE_DESCRIPTOR_ITEM_FIELDS)
    fields.append("resourceFacts.storageBuffers")
    if resource_facts.get("storageBuffers"):
        fields.extend(RESOURCE_STORAGE_BUFFER_ITEM_FIELDS)
    fields.append("resourceFacts.storageImages")
    fields.append("resourceFacts.textures")
    if resource_facts.get("textures"):
        fields.extend(RESOURCE_TEXTURE_ITEM_FIELDS)
    fields.append("resourceFacts.samplers")
    if resource_facts.get("samplers"):
        fields.extend(RESOURCE_SAMPLER_ITEM_FIELDS)
    return fields


def expected_resource_binding_fields(resource_facts: dict[str, Any]) -> list[str]:
    return expected_resource_manifest_fields(resource_facts)[1:]


def expected_metadata_manifest_fields(metadata: dict[str, Any]) -> list[str]:
    records = metadata.get("records")
    if isinstance(records, list) and records:
        return [RESOURCE_METADATA_COLLECTION, *RESOURCE_METADATA_ITEM_FIELDS]
    return [RESOURCE_METADATA_COLLECTION]


def expected_metadata_manifest_fields_for_resource(
    resource_facts: dict[str, Any],
) -> list[str]:
    records = resource_facts.get("targetIndependentResourceMetadata")
    if isinstance(records, list) and records:
        return [RESOURCE_METADATA_COLLECTION, *RESOURCE_METADATA_ITEM_FIELDS]
    return [RESOURCE_METADATA_COLLECTION]


def expected_source_resource_entrypoint_fields(
    resource_fields: list[str], metadata_fields: list[str]
) -> list[str]:
    return ordered_unique(
        [
            *SOURCE_RESOURCE_ENTRYPOINT_FIELDS,
            *resource_fields,
            *metadata_fields,
        ]
    )


def manifest_source_resource_entrypoint_fields(
    source_facts: list[str],
    type_facts: list[str],
    resource_fields: list[str],
    metadata_fields: list[str],
) -> list[str]:
    return ordered_unique(
        [
            "path",
            "stage",
            "entryPoint",
            *prefixed_fact_fields("sourceLocationFacts", source_facts),
            *prefixed_fact_fields("typeFacts", type_facts),
            *resource_fields,
            *metadata_fields,
        ]
    )


def expected_source_map_debug_facts(
    source_facts: list[str], type_facts: list[str]
) -> list[str]:
    return [
        "path",
        "stage",
        "entryPoint",
        *REQUIRED_SOURCE_MAP_DEBUG_FACTS,
        *prefixed_fact_fields("sourceLocationFacts", source_facts),
        *prefixed_fact_fields("typeFacts", type_facts),
        "resourceFacts.localSize",
    ]


def parity_dimension_record(
    required_fields: list[str],
    manifest_fields: list[str],
    missing_manifest_fields: list[str],
) -> dict[str, Any]:
    return {
        "covered": not missing_manifest_fields,
        "requiredFieldCount": len(required_fields),
        "manifestFieldCount": len(manifest_fields),
        "missingManifestFields": missing_manifest_fields,
    }


def fixture_parity_dimensions(record: dict[str, Any]) -> dict[str, dict[str, Any]]:
    source_locations = require_object(record.get("sourceLocations"), "", [])
    source_required = string_list(source_locations.get("inventoryFacts"))
    source_manifest = string_list(source_locations.get("manifestFacts"))

    entry_point = require_object(record.get("entryPointIdentity"), "", [])
    entry_required = string_list(entry_point.get("requiredFields"))
    entry_manifest = string_list(entry_point.get("manifestFacts"))

    resource_facts = require_object(record.get("resourceFacts"), "", [])
    resource_required = expected_resource_manifest_fields(resource_facts)
    resource_manifest = string_list(resource_facts.get("manifestFields"))

    metadata = require_object(record.get("targetIndependentResourceMetadata"), "", [])
    metadata_required = expected_metadata_manifest_fields(metadata)
    metadata_manifest = string_list(metadata.get("manifestFields"))

    source_resource = require_object(
        record.get("sourceResourceEntrypointPreservation"), "", []
    )
    source_resource_required = string_list(source_resource.get("requiredFields"))
    source_resource_manifest = string_list(
        source_resource.get("manifestRequiredFields")
    )

    type_facts = require_object(record.get("targetIndependentTypeFacts"), "", [])
    source_map = require_object(record.get("sourceMapDebugFacts"), "", [])
    source_map_required = expected_source_map_debug_facts(
        source_required, string_list(type_facts.get("inventoryFacts"))
    )
    source_map_manifest = string_list(source_map.get("manifestFacts"))

    return {
        "sourceLocations": parity_dimension_record(
            source_required,
            source_manifest,
            missing_fields(source_required, source_manifest),
        ),
        "entryPointIdentity": parity_dimension_record(
            entry_required,
            entry_manifest,
            missing_fields(entry_required, entry_manifest),
        ),
        "resources": parity_dimension_record(
            resource_required,
            resource_manifest,
            missing_fields(resource_required, resource_manifest),
        ),
        "targetIndependentResourceMetadata": parity_dimension_record(
            metadata_required,
            metadata_manifest,
            missing_fields(metadata_required, metadata_manifest),
        ),
        "sourceResourceEntrypointPreservation": parity_dimension_record(
            source_resource_required,
            source_resource_manifest,
            missing_fields(source_resource_required, source_resource_manifest),
        ),
        "sourceMapDebugPreservation": parity_dimension_record(
            source_map_required,
            source_map_manifest,
            missing_fields(source_map_required, source_map_manifest),
        ),
    }


def derive_parity_coverage_matrix(fixtures: list[dict[str, Any]]) -> dict[str, Any]:
    fixture_rows: list[dict[str, Any]] = []
    covered_by_dimension = {dimension: 0 for dimension in PARITY_COVERAGE_DIMENSIONS}

    for record in fixtures:
        dimensions = fixture_parity_dimensions(record)
        for dimension, dimension_record in dimensions.items():
            if dimension_record.get("covered") is True:
                covered_by_dimension[dimension] += 1
        fixture_rows.append(
            {
                "path": record.get("path"),
                "status": (
                    PARITY_COVERAGE_MATRIX_STATUS_COVERED
                    if all(item.get("covered") is True for item in dimensions.values())
                    else PARITY_COVERAGE_MATRIX_STATUS_INCOMPLETE
                ),
                "dimensions": dimensions,
            }
        )

    fixture_count = len(fixtures)
    dimensions_summary = [
        {
            "name": dimension,
            "fixtureCount": fixture_count,
            "coveredFixtureCount": covered_by_dimension[dimension],
            "missingFixtureCount": fixture_count - covered_by_dimension[dimension],
            "requiredForEveryFixture": True,
        }
        for dimension in PARITY_COVERAGE_DIMENSIONS
    ]

    return {
        "status": (
            PARITY_COVERAGE_MATRIX_STATUS_COVERED
            if all(item["missingFixtureCount"] == 0 for item in dimensions_summary)
            else PARITY_COVERAGE_MATRIX_STATUS_INCOMPLETE
        ),
        "dimensions": dimensions_summary,
        "fixtures": fixture_rows,
    }


def op_type_fixture_paths(op_type_catalog: dict[str, Any]) -> list[str]:
    summary = op_type_catalog.get("coverageSummary")
    if not isinstance(summary, dict):
        return []
    return sorted_unique(string_list(summary.get("fixtures")))


def op_type_type_facts(op_type_catalog: dict[str, Any]) -> list[str]:
    facts: list[str] = []
    for item in op_type_catalog.get("types", []):
        if isinstance(item, dict) and isinstance(item.get("typeFact"), str):
            facts.append(item["typeFact"])
    return sorted_unique(facts)


def source_resource_fixture_paths(fixtures: list[dict[str, Any]]) -> list[str]:
    paths = [item.get("path") for item in fixtures]
    return sorted_unique([path for path in paths if isinstance(path, str)])


def source_resource_type_facts(fixtures: list[dict[str, Any]]) -> list[str]:
    facts: list[str] = []
    for item in fixtures:
        type_facts = item.get("targetIndependentTypeFacts")
        if isinstance(type_facts, dict):
            facts.extend(string_list(type_facts.get("manifestFacts")))
    return sorted_unique(facts)


def op_type_operation_fixture_coverage(
    op_type_catalog: dict[str, Any],
) -> tuple[int, int, list[str], list[dict[str, Any]]]:
    operation_count = 0
    row_count = 0
    referenced_fixtures: list[str] = []
    missing_rows: list[dict[str, Any]] = []
    for index, item in enumerate(op_type_catalog.get("operations", [])):
        if not isinstance(item, dict):
            continue
        operation_count += 1
        operation = item.get("operation")
        operation_name = (
            operation if isinstance(operation, str) else f"operation[{index}]"
        )
        referenced_fixtures.extend(string_list(item.get("fixtures")))
        for coverage in item.get("fixtureCoverage", []):
            if not isinstance(coverage, dict):
                continue
            row_count += 1
            missing = string_list(coverage.get("missingRequiredFacts"))
            if missing:
                missing_rows.append(
                    {
                        "operation": operation_name,
                        "path": coverage.get("path"),
                        "missingRequiredFacts": missing,
                    }
                )
    return (
        operation_count,
        row_count,
        sorted_unique(referenced_fixtures),
        missing_rows,
    )


def derive_catalog_consistency(
    fixtures: list[dict[str, Any]], op_type_catalog: dict[str, Any]
) -> dict[str, Any]:
    source_fixtures = source_resource_fixture_paths(fixtures)
    op_fixtures = op_type_fixture_paths(op_type_catalog)
    source_type_facts = source_resource_type_facts(fixtures)
    op_type_facts = op_type_type_facts(op_type_catalog)
    (
        operation_count,
        row_count,
        referenced_fixtures,
        missing_rows,
    ) = op_type_operation_fixture_coverage(op_type_catalog)
    fixtures_outside_source = sorted_difference(referenced_fixtures, source_fixtures)
    fixtures_without_operations = sorted_difference(
        source_fixtures, referenced_fixtures
    )
    fixture_missing_from_op_type = sorted_difference(source_fixtures, op_fixtures)
    fixture_missing_from_source_resource = sorted_difference(
        op_fixtures, source_fixtures
    )
    type_facts_missing_from_op_type = sorted_difference(
        source_type_facts, op_type_facts
    )
    type_facts_missing_from_source_resource = sorted_difference(
        op_type_facts, source_type_facts
    )
    return {
        "opTypeCatalog": {
            "path": OP_TYPE_CATALOG_PATH.as_posix(),
            "kind": op_type_catalog.get("kind"),
            "status": op_type_catalog.get("status"),
        },
        "fixtureUniverse": {
            "sourceResourceFixtures": source_fixtures,
            "opTypeCatalogFixtures": op_fixtures,
            "missingFromOpTypeCatalog": fixture_missing_from_op_type,
            "missingFromSourceResourceCatalog": fixture_missing_from_source_resource,
            "matches": not fixture_missing_from_op_type
            and not fixture_missing_from_source_resource,
        },
        "targetIndependentTypeFacts": {
            "sourceResourceFacts": source_type_facts,
            "opTypeCatalogFacts": op_type_facts,
            "missingFromOpTypeCatalog": type_facts_missing_from_op_type,
            "missingFromSourceResourceCatalog": type_facts_missing_from_source_resource,
            "matches": not type_facts_missing_from_op_type
            and not type_facts_missing_from_source_resource,
        },
        "operationFixtureCoverage": {
            "operationCount": operation_count,
            "fixtureCoverageRowCount": row_count,
            "referencedFixtures": referenced_fixtures,
            "fixturesOutsideSourceResourceCatalog": fixtures_outside_source,
            "sourceResourceFixturesWithoutOperationCoverage": fixtures_without_operations,
            "missingRequiredFactRows": missing_rows,
            "matches": not fixtures_outside_source
            and not fixtures_without_operations
            and not missing_rows,
        },
    }


def compare_fields(
    actual: list[str], expected: list[str], field: str, errors: list[str]
) -> None:
    if actual != expected:
        errors.append(f"{CATALOG_PATH}: {field} must be {expected!r}, got {actual!r}")


def check_parity_coverage_matrix(
    catalog: dict[str, Any], fixtures: list[dict[str, Any]], errors: list[str]
) -> None:
    matrix = require_object(
        catalog.get("parityCoverageMatrix"), "parityCoverageMatrix", errors
    )
    if not matrix:
        return
    if tuple(matrix) != PARITY_COVERAGE_MATRIX_KEYS:
        errors.append(f"{CATALOG_PATH}: parityCoverageMatrix schema changed")
    expected = derive_parity_coverage_matrix(fixtures)
    if matrix != expected:
        errors.append(
            f"{CATALOG_PATH}: parityCoverageMatrix must match source, entry "
            "point, resource, metadata, and source-map/debug fixture evidence"
        )

    dimension_records = require_list(
        matrix.get("dimensions"), "parityCoverageMatrix.dimensions", errors
    )
    dimension_names: list[str] = []
    for index, item in enumerate(dimension_records):
        record = require_object(
            item, f"parityCoverageMatrix.dimensions[{index}]", errors
        )
        if tuple(record) != PARITY_COVERAGE_DIMENSION_KEYS:
            errors.append(
                f"{CATALOG_PATH}: parityCoverageMatrix.dimensions[{index}] "
                "schema changed"
            )
        name = record.get("name")
        if isinstance(name, str):
            dimension_names.append(name)
        if record.get("requiredForEveryFixture") is not True:
            errors.append(
                f"{CATALOG_PATH}: parityCoverageMatrix.dimensions[{index}]."
                "requiredForEveryFixture must be true"
            )
        if record.get("missingFixtureCount") != 0:
            errors.append(
                f"{CATALOG_PATH}: parityCoverageMatrix.dimensions[{index}]."
                "missingFixtureCount must be 0"
            )
    compare_fields(
        dimension_names,
        list(PARITY_COVERAGE_DIMENSIONS),
        "parityCoverageMatrix.dimensions[].name",
        errors,
    )

    matrix_fixtures = require_list(
        matrix.get("fixtures"), "parityCoverageMatrix.fixtures", errors
    )
    for index, item in enumerate(matrix_fixtures):
        record = require_object(item, f"parityCoverageMatrix.fixtures[{index}]", errors)
        if tuple(record) != PARITY_COVERAGE_FIXTURE_KEYS:
            errors.append(
                f"{CATALOG_PATH}: parityCoverageMatrix.fixtures[{index}] schema changed"
            )
        if record.get("status") != PARITY_COVERAGE_MATRIX_STATUS_COVERED:
            errors.append(
                f"{CATALOG_PATH}: parityCoverageMatrix.fixtures[{index}].status "
                f"must be {PARITY_COVERAGE_MATRIX_STATUS_COVERED!r}"
            )
        dimensions = require_object(
            record.get("dimensions"),
            f"parityCoverageMatrix.fixtures[{index}].dimensions",
            errors,
        )
        if tuple(dimensions) != PARITY_COVERAGE_DIMENSIONS:
            errors.append(
                f"{CATALOG_PATH}: parityCoverageMatrix.fixtures[{index}]."
                "dimensions schema changed"
            )
        for dimension, dimension_record_raw in dimensions.items():
            dimension_record = require_object(
                dimension_record_raw,
                f"parityCoverageMatrix.fixtures[{index}].dimensions.{dimension}",
                errors,
            )
            if tuple(dimension_record) != PARITY_COVERAGE_DIMENSION_RECORD_KEYS:
                errors.append(
                    f"{CATALOG_PATH}: parityCoverageMatrix.fixtures[{index}]."
                    f"dimensions.{dimension} schema changed"
                )
            if dimension_record.get("covered") is not True:
                errors.append(
                    f"{CATALOG_PATH}: parityCoverageMatrix.fixtures[{index}]."
                    f"dimensions.{dimension}.covered must be true"
                )
            if dimension_record.get("missingManifestFields") != []:
                errors.append(
                    f"{CATALOG_PATH}: parityCoverageMatrix.fixtures[{index}]."
                    f"dimensions.{dimension}.missingManifestFields must be empty"
                )


def derive_fixture_catalog(
    boundary: dict[str, Any],
    fixture_inventory: dict[str, Any],
    manifest: dict[str, Any],
) -> list[dict[str, Any]]:
    fixtures = fixture_records(fixture_inventory)
    manifest_by_path = manifest_records(manifest)
    boundary_by_path = boundary_records(boundary)
    catalog: list[dict[str, Any]] = []

    for fixture_path in sorted(fixtures):
        fixture = fixtures[fixture_path]
        manifest_record = manifest_by_path.get(fixture_path, {})
        coverage = manifest_record.get("boundaryFactCoverage")
        if not isinstance(coverage, dict):
            coverage = {}
        boundary_record = boundary_by_path.get(fixture_path, {})
        parity_requirements = fixture.get("parityRequirements")
        if not isinstance(parity_requirements, dict):
            parity_requirements = {}
        parity_report_fields = fixture.get("parityReportFields")
        if not isinstance(parity_report_fields, dict):
            parity_report_fields = {}
        resource_facts = fixture.get("resourceFacts")
        if not isinstance(resource_facts, dict):
            resource_facts = {}

        inventory_source_facts = string_list(fixture.get("sourceLocationFacts"))
        manifest_source_facts = string_list(coverage.get("sourceLocationFacts"))
        inventory_type_facts = string_list(fixture.get("typeFacts"))
        manifest_type_facts = string_list(coverage.get("targetIndependentTypeFacts"))
        entry_point_facts = string_list(coverage.get("entryPointFacts"))
        required_source_facts = required_source_facts_for_fixture(
            boundary, fixture_path, inventory_source_facts
        )
        resource_fields = string_list(coverage.get("resourceFactFields"))
        metadata_fields = string_list(
            coverage.get("targetIndependentResourceMetadataFields")
        )
        expected_resource_fields = expected_resource_manifest_fields(resource_facts)
        expected_metadata_fields = expected_metadata_manifest_fields_for_resource(
            resource_facts
        )
        required_source_resource_entrypoint_fields = (
            expected_source_resource_entrypoint_fields(
                expected_resource_fields, expected_metadata_fields
            )
        )
        available_source_resource_entrypoint_fields = (
            manifest_source_resource_entrypoint_fields(
                manifest_source_facts,
                manifest_type_facts,
                resource_fields,
                metadata_fields,
            )
        )
        manifest_required_source_resource_entrypoint_fields = [
            field
            for field in required_source_resource_entrypoint_fields
            if field in available_source_resource_entrypoint_fields
        ]
        source_map_debug_facts = string_list(coverage.get("sourceMapDebugFacts"))
        empty_collections = [
            field
            for field in RESOURCE_COLLECTION_FIELDS
            if field in resource_fields
            and not resource_facts.get(field.removeprefix("resourceFacts."))
        ]

        catalog.append(
            {
                "path": fixture_path,
                "stage": fixture.get("stage"),
                "entryPoint": fixture.get("entryPoint"),
                "experimentSlice": manifest_record.get("experimentSlice"),
                "loweringStatus": manifest_record.get("loweringStatus"),
                "resourceFactMode": boundary_record.get("resourceFactMode"),
                "entryPointIdentity": {
                    "requiredFields": list(ENTRY_POINT_IDENTITY_FIELDS),
                    "manifestFacts": entry_point_facts,
                    "missingManifestFields": missing_fields(
                        list(ENTRY_POINT_IDENTITY_FIELDS), entry_point_facts
                    ),
                },
                "sourceLocations": {
                    "inventoryFacts": inventory_source_facts,
                    "manifestFacts": manifest_source_facts,
                    "requiredByBoundary": required_source_facts,
                    "missingFromManifest": missing_fields(
                        required_source_facts, manifest_source_facts
                    ),
                },
                "targetIndependentTypeFacts": {
                    "inventoryFacts": inventory_type_facts,
                    "manifestFacts": manifest_type_facts,
                    "missingFromManifest": missing_fields(
                        inventory_type_facts, manifest_type_facts
                    ),
                },
                "sourceMapDebugFacts": {
                    "requiredContractFacts": list(REQUIRED_SOURCE_MAP_DEBUG_FACTS),
                    "manifestFacts": source_map_debug_facts,
                    "missingRequiredContractFacts": missing_fields(
                        list(REQUIRED_SOURCE_MAP_DEBUG_FACTS), source_map_debug_facts
                    ),
                },
                "resourceFacts": {
                    "localSize": resource_facts.get("localSize"),
                    "manifestFields": resource_fields,
                    "descriptors": resource_facts.get("descriptors", []),
                    "storageBuffers": resource_facts.get("storageBuffers", []),
                    "storageImages": resource_facts.get("storageImages", []),
                    "textures": resource_facts.get("textures", []),
                    "samplers": resource_facts.get("samplers", []),
                    "emptyCollections": empty_collections,
                    "missingManifestFields": missing_fields(
                        ["resourceFacts.localSize", *RESOURCE_COLLECTION_FIELDS],
                        resource_fields,
                    ),
                },
                "targetIndependentResourceMetadata": {
                    "manifestFields": metadata_fields,
                    "records": resource_facts.get(
                        "targetIndependentResourceMetadata", []
                    ),
                    "missingManifestFields": missing_fields(
                        [RESOURCE_METADATA_COLLECTION], metadata_fields
                    ),
                },
                "sourceResourceEntrypointPreservation": {
                    "requiredFields": required_source_resource_entrypoint_fields,
                    "sourceEntrypointFields": list(SOURCE_RESOURCE_ENTRYPOINT_FIELDS),
                    "resourceFields": expected_resource_fields,
                    "targetIndependentResourceMetadataFields": (
                        expected_metadata_fields
                    ),
                    "manifestRequiredFields": (
                        manifest_required_source_resource_entrypoint_fields
                    ),
                    "missingManifestFields": missing_fields(
                        required_source_resource_entrypoint_fields,
                        available_source_resource_entrypoint_fields,
                    ),
                },
                "parityEvidence": {
                    "entryPointRequirementFields": field_list(
                        parity_requirements.get("entryPoint")
                    ),
                    "sourceLocationRequirementFields": field_list(
                        parity_requirements.get("sourceLocations")
                    ),
                    "typeFactRequirementFields": field_list(
                        parity_requirements.get("typeFacts")
                    ),
                    "sourceMapDebugRequirementFields": field_list(
                        parity_requirements.get("sourceMapDebugPreservation")
                    ),
                    "resourceRequirementFields": field_list(
                        parity_requirements.get("resources")
                    ),
                    "targetIndependentResourceMetadataRequirementFields": field_list(
                        parity_requirements.get("targetIndependentResourceMetadata")
                    ),
                    "reportFields": {
                        "sourceFile": field_list(
                            parity_report_fields.get("sourceFile")
                        ),
                        "entryPoint": field_list(
                            parity_report_fields.get("entryPoint")
                        ),
                        "entryPointIdentity": field_list(
                            parity_report_fields.get("entryPointIdentity")
                        ),
                        "workgroupSize": field_list(
                            parity_report_fields.get("workgroupSize")
                        ),
                        "resourceBindings": field_list(
                            parity_report_fields.get("resourceBindings")
                        ),
                        "targetIndependentResourceMetadata": field_list(
                            parity_report_fields.get(
                                "targetIndependentResourceMetadata"
                            )
                        ),
                        "typeFacts": field_list(parity_report_fields.get("typeFacts")),
                        "sourceMapDebugPreservation": field_list(
                            parity_report_fields.get("sourceMapDebugPreservation")
                        ),
                    },
                },
            }
        )

    return catalog


def derive_catalog(root: Path) -> dict[str, Any]:
    boundary = require_loaded_object(root / BOUNDARY_PATH, BOUNDARY_KIND)
    fixture_inventory = require_loaded_object(root / FIXTURE_PATH, FIXTURE_KIND)
    manifest = require_loaded_object(root / MANIFEST_PATH, MANIFEST_KIND)
    op_type_catalog = require_loaded_object(
        root / OP_TYPE_CATALOG_PATH, OP_TYPE_CATALOG_KIND
    )
    fixtures = derive_fixture_catalog(boundary, fixture_inventory, manifest)
    resource_bound = [
        item["path"]
        for item in fixtures
        if item.get("resourceFactMode") == "single-storage-buffer-binding"
    ]
    texture_sampler_bound = [
        item["path"]
        for item in fixtures
        if item.get("resourceFactMode") == "sampled-texture-sampler-binding"
    ]
    resource_free = [
        item["path"]
        for item in fixtures
        if item.get("resourceFactMode") == "empty-resource-facts"
    ]
    type_facts = sorted_unique(
        [
            type_fact
            for item in fixtures
            for type_fact in item["targetIndependentTypeFacts"]["manifestFacts"]
        ]
    )
    return {
        "schemaVersion": 1,
        "kind": CATALOG_KIND,
        "status": CATALOG_STATUS,
        "scope": "fixture-limited MLIR source-location and resource preservation evidence",
        "generation": {
            "deterministic": True,
            "derivedFrom": list(DERIVED_FROM),
            "optionalMlirToolingRequired": False,
            "productionLinked": False,
            "normalBuildRequired": False,
            "separatesPseudoMlir": True,
        },
        "sourceMapDebugContract": {
            "debugMetadataSchemaVersion": 11,
            "hirSourceMapSchemaVersion": 7,
            "requiredFacts": list(REQUIRED_SOURCE_MAP_DEBUG_FACTS),
            "recordsCombinedInSourceMap": False,
        },
        "resourceContract": {
            "targetIndependentMetadataField": RESOURCE_METADATA_COLLECTION,
            "resourceFieldModeValues": [
                "empty-resource-facts",
                "sampled-texture-sampler-binding",
                "single-storage-buffer-binding",
            ],
            "resourceBoundFixtures": [*resource_bound, *texture_sampler_bound],
            "sampledTextureSamplerFixtures": texture_sampler_bound,
            "resourceFreeFixtures": resource_free,
        },
        "catalogConsistency": derive_catalog_consistency(fixtures, op_type_catalog),
        "parityCoverageMatrix": derive_parity_coverage_matrix(fixtures),
        "fixtures": fixtures,
        "coverageSummary": {
            "fixtureCount": len(fixtures),
            "resourceBoundFixtureCount": len(resource_bound)
            + len(texture_sampler_bound),
            "sampledTextureSamplerFixtureCount": len(texture_sampler_bound),
            "resourceFreeFixtureCount": len(resource_free),
            "targetIndependentTypeFactCount": len(type_facts),
            "targetIndependentTypeFacts": type_facts,
            "fixtures": [item["path"] for item in fixtures],
        },
    }


def check_catalog_shape(catalog: dict[str, Any], errors: list[str]) -> None:
    if tuple(catalog) != REQUIRED_TOP_LEVEL_KEYS:
        errors.append(
            f"{CATALOG_PATH}: top-level key order/schema changed: {', '.join(catalog)}"
        )
    if catalog.get("kind") != CATALOG_KIND:
        errors.append(f"{CATALOG_PATH}: kind must be {CATALOG_KIND!r}")
    if catalog.get("status") != CATALOG_STATUS:
        errors.append(f"{CATALOG_PATH}: status must be {CATALOG_STATUS!r}")

    generation = require_object(catalog.get("generation"), "generation", errors)
    if tuple(generation) != GENERATION_KEYS:
        errors.append(f"{CATALOG_PATH}: generation schema changed")
    expected_flags = {
        "deterministic": True,
        "optionalMlirToolingRequired": False,
        "productionLinked": False,
        "normalBuildRequired": False,
        "separatesPseudoMlir": True,
    }
    for flag, expected in expected_flags.items():
        if generation.get(flag) is not expected:
            errors.append(f"{CATALOG_PATH}: generation.{flag} must be {expected}")
    if generation.get("derivedFrom") != list(DERIVED_FROM):
        errors.append(f"{CATALOG_PATH}: generation.derivedFrom is stale")

    source_contract = require_object(
        catalog.get("sourceMapDebugContract"), "sourceMapDebugContract", errors
    )
    if source_contract.get("requiredFacts") != list(REQUIRED_SOURCE_MAP_DEBUG_FACTS):
        errors.append(f"{CATALOG_PATH}: source-map/debug contract facts are stale")
    if source_contract.get("recordsCombinedInSourceMap") is not False:
        errors.append(
            f"{CATALOG_PATH}: sourceMapDebugContract.recordsCombinedInSourceMap "
            "must be false"
        )

    consistency = require_object(
        catalog.get("catalogConsistency"), "catalogConsistency", errors
    )
    if consistency and tuple(consistency) != CATALOG_CONSISTENCY_KEYS:
        errors.append(f"{CATALOG_PATH}: catalogConsistency schema changed")

    fixtures = require_list(catalog.get("fixtures"), "fixtures", errors)
    fixture_paths: list[str] = []
    fixture_records_for_matrix: list[dict[str, Any]] = []
    for index, item in enumerate(fixtures):
        record = require_object(item, f"fixtures[{index}]", errors)
        if record:
            fixture_records_for_matrix.append(record)
        if tuple(record) != FIXTURE_KEYS:
            errors.append(f"{CATALOG_PATH}: fixtures[{index}] schema changed")
        path = record.get("path")
        if not isinstance(path, str) or not path:
            errors.append(f"{CATALOG_PATH}: fixtures[{index}].path invalid")
        else:
            fixture_paths.append(path)
        if record.get("stage") != "compute":
            errors.append(f"{CATALOG_PATH}: fixtures[{index}].stage must be 'compute'")
        if not isinstance(record.get("entryPoint"), str) or not record["entryPoint"]:
            errors.append(
                f"{CATALOG_PATH}: fixtures[{index}].entryPoint must be non-empty"
            )

        entry_point = require_object(
            record.get("entryPointIdentity"),
            f"fixtures[{index}].entryPointIdentity",
            errors,
        )
        if tuple(entry_point) != ENTRY_POINT_IDENTITY_KEYS:
            errors.append(
                f"{CATALOG_PATH}: fixtures[{index}].entryPointIdentity schema changed"
            )
        if entry_point.get("requiredFields") != list(ENTRY_POINT_IDENTITY_FIELDS):
            errors.append(
                f"{CATALOG_PATH}: fixtures[{index}].entryPointIdentity."
                "requiredFields are stale"
            )
        if entry_point.get("manifestFacts") != list(ENTRY_POINT_IDENTITY_FIELDS):
            errors.append(
                f"{CATALOG_PATH}: fixtures[{index}].entryPointIdentity."
                "manifestFacts must preserve entry point identity"
            )
        if entry_point.get("missingManifestFields") != []:
            errors.append(
                f"{CATALOG_PATH}: fixtures[{index}].entryPointIdentity."
                "missingManifestFields must be empty"
            )

        source_locations = require_object(
            record.get("sourceLocations"), f"fixtures[{index}].sourceLocations", errors
        )
        if tuple(source_locations) != SOURCE_LOCATION_KEYS:
            errors.append(
                f"{CATALOG_PATH}: fixtures[{index}].sourceLocations schema changed"
            )
        inventory_source_facts = string_list(source_locations.get("inventoryFacts"))
        manifest_source_facts = string_list(source_locations.get("manifestFacts"))
        compare_fields(
            manifest_source_facts,
            inventory_source_facts,
            f"fixtures[{index}].sourceLocations.manifestFacts",
            errors,
        )
        if source_locations.get("missingFromManifest") != []:
            errors.append(
                f"{CATALOG_PATH}: fixtures[{index}].sourceLocations."
                "missingFromManifest must be empty"
            )

        type_facts = require_object(
            record.get("targetIndependentTypeFacts"),
            f"fixtures[{index}].targetIndependentTypeFacts",
            errors,
        )
        if tuple(type_facts) != TYPE_FACT_KEYS:
            errors.append(
                f"{CATALOG_PATH}: fixtures[{index}].targetIndependentTypeFacts "
                "schema changed"
            )
        if type_facts.get("manifestFacts") != type_facts.get("inventoryFacts"):
            errors.append(
                f"{CATALOG_PATH}: fixtures[{index}].targetIndependentTypeFacts."
                "manifestFacts must match fixture inventory type facts"
            )
        inventory_type_facts = string_list(type_facts.get("inventoryFacts"))
        if type_facts.get("missingFromManifest") != []:
            errors.append(
                f"{CATALOG_PATH}: fixtures[{index}].targetIndependentTypeFacts."
                "missingFromManifest must be empty"
            )

        source_map = require_object(
            record.get("sourceMapDebugFacts"),
            f"fixtures[{index}].sourceMapDebugFacts",
            errors,
        )
        if source_map.get("missingRequiredContractFacts") != []:
            errors.append(
                f"{CATALOG_PATH}: fixtures[{index}].sourceMapDebugFacts."
                "missingRequiredContractFacts must be empty"
            )
        compare_fields(
            string_list(source_map.get("manifestFacts")),
            expected_source_map_debug_facts(
                inventory_source_facts, inventory_type_facts
            ),
            f"fixtures[{index}].sourceMapDebugFacts.manifestFacts",
            errors,
        )

        resource_facts = require_object(
            record.get("resourceFacts"), f"fixtures[{index}].resourceFacts", errors
        )
        if tuple(resource_facts) != RESOURCE_FACT_KEYS:
            errors.append(
                f"{CATALOG_PATH}: fixtures[{index}].resourceFacts schema changed"
            )
        expected_resource_fields = expected_resource_manifest_fields(resource_facts)
        compare_fields(
            string_list(resource_facts.get("manifestFields")),
            expected_resource_fields,
            f"fixtures[{index}].resourceFacts.manifestFields",
            errors,
        )
        if resource_facts.get("missingManifestFields") != []:
            errors.append(
                f"{CATALOG_PATH}: fixtures[{index}].resourceFacts."
                "missingManifestFields must be empty"
            )

        metadata = require_object(
            record.get("targetIndependentResourceMetadata"),
            f"fixtures[{index}].targetIndependentResourceMetadata",
            errors,
        )
        if tuple(metadata) != RESOURCE_METADATA_KEYS:
            errors.append(
                f"{CATALOG_PATH}: fixtures[{index}]."
                "targetIndependentResourceMetadata schema changed"
            )
        expected_metadata_fields = expected_metadata_manifest_fields(metadata)
        compare_fields(
            string_list(metadata.get("manifestFields")),
            expected_metadata_fields,
            f"fixtures[{index}].targetIndependentResourceMetadata.manifestFields",
            errors,
        )
        if metadata.get("missingManifestFields") != []:
            errors.append(
                f"{CATALOG_PATH}: fixtures[{index}]."
                "targetIndependentResourceMetadata.missingManifestFields "
                "must be empty"
            )

        source_resource_entrypoint = require_object(
            record.get("sourceResourceEntrypointPreservation"),
            f"fixtures[{index}].sourceResourceEntrypointPreservation",
            errors,
        )
        if tuple(source_resource_entrypoint) != SOURCE_RESOURCE_ENTRYPOINT_KEYS:
            errors.append(
                f"{CATALOG_PATH}: fixtures[{index}]."
                "sourceResourceEntrypointPreservation schema changed"
            )
        required_source_resource_entrypoint_fields = (
            expected_source_resource_entrypoint_fields(
                expected_resource_fields, expected_metadata_fields
            )
        )
        compare_fields(
            string_list(source_resource_entrypoint.get("requiredFields")),
            required_source_resource_entrypoint_fields,
            f"fixtures[{index}].sourceResourceEntrypointPreservation.requiredFields",
            errors,
        )
        compare_fields(
            string_list(source_resource_entrypoint.get("sourceEntrypointFields")),
            list(SOURCE_RESOURCE_ENTRYPOINT_FIELDS),
            f"fixtures[{index}].sourceResourceEntrypointPreservation."
            "sourceEntrypointFields",
            errors,
        )
        compare_fields(
            string_list(source_resource_entrypoint.get("resourceFields")),
            expected_resource_fields,
            f"fixtures[{index}].sourceResourceEntrypointPreservation.resourceFields",
            errors,
        )
        compare_fields(
            string_list(
                source_resource_entrypoint.get(
                    "targetIndependentResourceMetadataFields"
                )
            ),
            expected_metadata_fields,
            f"fixtures[{index}].sourceResourceEntrypointPreservation."
            "targetIndependentResourceMetadataFields",
            errors,
        )
        compare_fields(
            string_list(source_resource_entrypoint.get("manifestRequiredFields")),
            required_source_resource_entrypoint_fields,
            f"fixtures[{index}].sourceResourceEntrypointPreservation."
            "manifestRequiredFields",
            errors,
        )
        if source_resource_entrypoint.get("missingManifestFields") != []:
            errors.append(
                f"{CATALOG_PATH}: fixtures[{index}]."
                "sourceResourceEntrypointPreservation.missingManifestFields "
                "must be empty"
            )

        parity = require_object(
            record.get("parityEvidence"), f"fixtures[{index}].parityEvidence", errors
        )
        if tuple(parity) != PARITY_EVIDENCE_KEYS:
            errors.append(
                f"{CATALOG_PATH}: fixtures[{index}].parityEvidence schema changed"
            )
        compare_fields(
            string_list(parity.get("entryPointRequirementFields")),
            ["stage", "entryPoint", "resourceFacts.localSize"],
            f"fixtures[{index}].parityEvidence.entryPointRequirementFields",
            errors,
        )
        compare_fields(
            string_list(parity.get("sourceLocationRequirementFields")),
            inventory_source_facts,
            f"fixtures[{index}].parityEvidence.sourceLocationRequirementFields",
            errors,
        )
        compare_fields(
            string_list(parity.get("typeFactRequirementFields")),
            inventory_type_facts,
            f"fixtures[{index}].parityEvidence.typeFactRequirementFields",
            errors,
        )
        compare_fields(
            string_list(parity.get("sourceMapDebugRequirementFields")),
            expected_source_map_debug_facts(
                inventory_source_facts, inventory_type_facts
            ),
            f"fixtures[{index}].parityEvidence.sourceMapDebugRequirementFields",
            errors,
        )
        compare_fields(
            string_list(parity.get("resourceRequirementFields")),
            expected_resource_fields,
            f"fixtures[{index}].parityEvidence.resourceRequirementFields",
            errors,
        )
        compare_fields(
            string_list(
                parity.get("targetIndependentResourceMetadataRequirementFields")
            ),
            expected_metadata_fields,
            f"fixtures[{index}].parityEvidence."
            "targetIndependentResourceMetadataRequirementFields",
            errors,
        )
        report_fields = require_object(
            parity.get("reportFields"),
            f"fixtures[{index}].parityEvidence.reportFields",
            errors,
        )
        if tuple(report_fields) != REPORT_FIELD_KEYS:
            errors.append(
                f"{CATALOG_PATH}: fixtures[{index}].parityEvidence.reportFields "
                "schema changed"
            )
        compare_fields(
            string_list(report_fields.get("sourceFile")),
            ["path", "sourceLocationFacts.source_file"],
            f"fixtures[{index}].parityEvidence.reportFields.sourceFile",
            errors,
        )
        compare_fields(
            string_list(report_fields.get("entryPoint")),
            ["stage", "entryPoint"],
            f"fixtures[{index}].parityEvidence.reportFields.entryPoint",
            errors,
        )
        compare_fields(
            string_list(report_fields.get("entryPointIdentity")),
            list(ENTRY_POINT_IDENTITY_REPORT_FIELDS),
            f"fixtures[{index}].parityEvidence.reportFields.entryPointIdentity",
            errors,
        )
        compare_fields(
            string_list(report_fields.get("workgroupSize")),
            ["resourceFacts.localSize", "sourceLocationFacts.layout_local_size"],
            f"fixtures[{index}].parityEvidence.reportFields.workgroupSize",
            errors,
        )
        compare_fields(
            string_list(report_fields.get("resourceBindings")),
            expected_resource_binding_fields(resource_facts),
            f"fixtures[{index}].parityEvidence.reportFields.resourceBindings",
            errors,
        )
        compare_fields(
            string_list(report_fields.get("targetIndependentResourceMetadata")),
            expected_metadata_fields,
            f"fixtures[{index}].parityEvidence.reportFields."
            "targetIndependentResourceMetadata",
            errors,
        )
        compare_fields(
            string_list(report_fields.get("typeFacts")),
            prefixed_fact_fields("typeFacts", inventory_type_facts),
            f"fixtures[{index}].parityEvidence.reportFields.typeFacts",
            errors,
        )
        compare_fields(
            string_list(report_fields.get("sourceMapDebugPreservation")),
            expected_source_map_debug_facts(
                inventory_source_facts, inventory_type_facts
            ),
            f"fixtures[{index}].parityEvidence.reportFields.sourceMapDebugPreservation",
            errors,
        )

    if fixture_paths != sorted_unique(fixture_paths):
        errors.append(f"{CATALOG_PATH}: fixtures must be sorted unique by path")
    check_catalog_consistency(consistency, fixture_records_for_matrix, errors)
    check_parity_coverage_matrix(catalog, fixture_records_for_matrix, errors)


def check_catalog_consistency(
    consistency: dict[str, Any], fixtures: list[dict[str, Any]], errors: list[str]
) -> None:
    if not consistency:
        return

    op_type = require_object(
        consistency.get("opTypeCatalog"), "catalogConsistency.opTypeCatalog", errors
    )
    if tuple(op_type) != OP_TYPE_CATALOG_REFERENCE_KEYS:
        errors.append(
            f"{CATALOG_PATH}: catalogConsistency.opTypeCatalog schema changed"
        )
    expected_op_type = {
        "path": OP_TYPE_CATALOG_PATH.as_posix(),
        "kind": OP_TYPE_CATALOG_KIND,
        "status": OP_TYPE_CATALOG_STATUS,
    }
    for key, expected in expected_op_type.items():
        if op_type.get(key) != expected:
            errors.append(
                f"{CATALOG_PATH}: catalogConsistency.opTypeCatalog.{key} "
                f"must be {expected!r}"
            )

    source_fixtures = source_resource_fixture_paths(fixtures)
    fixture_universe = require_object(
        consistency.get("fixtureUniverse"),
        "catalogConsistency.fixtureUniverse",
        errors,
    )
    if tuple(fixture_universe) != CATALOG_FIXTURE_UNIVERSE_KEYS:
        errors.append(
            f"{CATALOG_PATH}: catalogConsistency.fixtureUniverse schema changed"
        )
    compare_fields(
        string_list(fixture_universe.get("sourceResourceFixtures")),
        source_fixtures,
        "catalogConsistency.fixtureUniverse.sourceResourceFixtures",
        errors,
    )
    if fixture_universe.get("missingFromOpTypeCatalog") != []:
        errors.append(
            f"{CATALOG_PATH}: catalogConsistency.fixtureUniverse."
            "missingFromOpTypeCatalog must be empty"
        )
    if fixture_universe.get("missingFromSourceResourceCatalog") != []:
        errors.append(
            f"{CATALOG_PATH}: catalogConsistency.fixtureUniverse."
            "missingFromSourceResourceCatalog must be empty"
        )
    if fixture_universe.get("matches") is not True:
        errors.append(
            f"{CATALOG_PATH}: catalogConsistency.fixtureUniverse.matches must be true"
        )

    source_type_facts = source_resource_type_facts(fixtures)
    type_facts = require_object(
        consistency.get("targetIndependentTypeFacts"),
        "catalogConsistency.targetIndependentTypeFacts",
        errors,
    )
    if tuple(type_facts) != CATALOG_TYPE_FACT_UNIVERSE_KEYS:
        errors.append(
            f"{CATALOG_PATH}: catalogConsistency.targetIndependentTypeFacts "
            "schema changed"
        )
    compare_fields(
        string_list(type_facts.get("sourceResourceFacts")),
        source_type_facts,
        "catalogConsistency.targetIndependentTypeFacts.sourceResourceFacts",
        errors,
    )
    if type_facts.get("missingFromOpTypeCatalog") != []:
        errors.append(
            f"{CATALOG_PATH}: catalogConsistency.targetIndependentTypeFacts."
            "missingFromOpTypeCatalog must be empty"
        )
    if type_facts.get("missingFromSourceResourceCatalog") != []:
        errors.append(
            f"{CATALOG_PATH}: catalogConsistency.targetIndependentTypeFacts."
            "missingFromSourceResourceCatalog must be empty"
        )
    if type_facts.get("matches") is not True:
        errors.append(
            f"{CATALOG_PATH}: catalogConsistency.targetIndependentTypeFacts."
            "matches must be true"
        )

    operation_fixture_coverage = require_object(
        consistency.get("operationFixtureCoverage"),
        "catalogConsistency.operationFixtureCoverage",
        errors,
    )
    if tuple(operation_fixture_coverage) != CATALOG_OPERATION_FIXTURE_COVERAGE_KEYS:
        errors.append(
            f"{CATALOG_PATH}: catalogConsistency.operationFixtureCoverage "
            "schema changed"
        )
    if not isinstance(operation_fixture_coverage.get("operationCount"), int):
        errors.append(
            f"{CATALOG_PATH}: catalogConsistency.operationFixtureCoverage."
            "operationCount must be an integer"
        )
    if not isinstance(operation_fixture_coverage.get("fixtureCoverageRowCount"), int):
        errors.append(
            f"{CATALOG_PATH}: catalogConsistency.operationFixtureCoverage."
            "fixtureCoverageRowCount must be an integer"
        )
    referenced_fixtures = string_list(
        operation_fixture_coverage.get("referencedFixtures")
    )
    if referenced_fixtures != sorted_unique(referenced_fixtures):
        errors.append(
            f"{CATALOG_PATH}: catalogConsistency.operationFixtureCoverage."
            "referencedFixtures must be sorted unique"
        )
    if operation_fixture_coverage.get("fixturesOutsideSourceResourceCatalog") != []:
        errors.append(
            f"{CATALOG_PATH}: catalogConsistency.operationFixtureCoverage."
            "fixturesOutsideSourceResourceCatalog must be empty"
        )
    if (
        operation_fixture_coverage.get("sourceResourceFixturesWithoutOperationCoverage")
        != []
    ):
        errors.append(
            f"{CATALOG_PATH}: catalogConsistency.operationFixtureCoverage."
            "sourceResourceFixturesWithoutOperationCoverage must be empty"
        )
    missing_rows = require_list(
        operation_fixture_coverage.get("missingRequiredFactRows"),
        "catalogConsistency.operationFixtureCoverage.missingRequiredFactRows",
        errors,
    )
    if missing_rows:
        for index, row in enumerate(missing_rows):
            record = require_object(
                row,
                "catalogConsistency.operationFixtureCoverage."
                f"missingRequiredFactRows[{index}]",
                errors,
            )
            if tuple(record) != CATALOG_MISSING_REQUIRED_FACT_ROW_KEYS:
                errors.append(
                    f"{CATALOG_PATH}: catalogConsistency.operationFixtureCoverage."
                    f"missingRequiredFactRows[{index}] schema changed"
                )
        errors.append(
            f"{CATALOG_PATH}: catalogConsistency.operationFixtureCoverage."
            "missingRequiredFactRows must be empty"
        )
    if operation_fixture_coverage.get("matches") is not True:
        errors.append(
            f"{CATALOG_PATH}: catalogConsistency.operationFixtureCoverage."
            "matches must be true"
        )


def check_repo(root: Path, *, update: bool = False) -> tuple[list[str], int]:
    errors: list[str] = []
    try:
        derived = derive_catalog(root)
    except (OSError, ValueError) as error:
        return [str(error)], 0

    if update:
        write_json(root / CATALOG_PATH, derived)
    else:
        try:
            actual = load_json(root / CATALOG_PATH)
        except (OSError, ValueError) as error:
            return [f"{CATALOG_PATH}: {error}"], 0
        if actual != derived:
            errors.append(
                f"{CATALOG_PATH}: stale; regenerate with "
                "tools/check_mlir_source_resource_catalog.py --update"
            )
        if isinstance(actual, dict):
            check_catalog_shape(actual, errors)
        else:
            errors.append(f"{CATALOG_PATH}: catalog must be an object")

    return errors, len(derived["fixtures"])


def run_self_test() -> list[str]:
    errors: list[str] = []
    with tempfile.TemporaryDirectory() as temp_dir:
        root = Path(temp_dir)
        (root / "experimental/mlir").mkdir(parents=True)
        source_facts = [
            "source_file",
            "shader_module",
            "compute_stage",
            "entry_point",
            "layout_local_size",
        ]
        type_facts = ["void_entry_point"]
        source_map_debug_facts = expected_source_map_debug_facts(
            source_facts, type_facts
        )
        resource_fields = ["resourceFacts.localSize", *RESOURCE_COLLECTION_FIELDS]
        resource_fixture_path = "tests/fixtures/ZResourceTest.cgl"
        resource_source_facts = [
            "source_file",
            "shader_module",
            "compute_stage",
            "entry_point",
            "layout_local_size",
            "storage_buffer_declaration",
            "storage_buffer_write",
        ]
        resource_type_facts = [
            "void_entry_point",
            "float_scalar",
            "float_pointer_storage_buffer",
            "storage_buffer_element_type",
        ]
        resource_source_map_debug_facts = expected_source_map_debug_facts(
            resource_source_facts, resource_type_facts
        )
        resource_bound_fields = [
            "resourceFacts.localSize",
            "resourceFacts.descriptors",
            *RESOURCE_DESCRIPTOR_ITEM_FIELDS,
            "resourceFacts.storageBuffers",
            *RESOURCE_STORAGE_BUFFER_ITEM_FIELDS,
            "resourceFacts.storageImages",
            "resourceFacts.textures",
            "resourceFacts.samplers",
        ]
        resource_metadata_fields = [
            RESOURCE_METADATA_COLLECTION,
            *RESOURCE_METADATA_ITEM_FIELDS,
        ]
        boundary = {
            "kind": BOUNDARY_KIND,
            "operations": [
                {
                    "preserves": ["source_locations"],
                    "fixtures": ["tests/fixtures/Test.cgl", resource_fixture_path],
                    "requiredFixtureFacts": ["source_file", "entry_point"],
                },
                {
                    "preserves": ["source_locations", "resource_bindings"],
                    "fixtures": [resource_fixture_path],
                    "requiredFixtureFacts": [
                        "storage_buffer_declaration",
                        "storage_buffer_write",
                        "resourceFacts.descriptors[].binding",
                    ],
                },
            ],
            "fixtureBoundary": [
                {
                    "path": "tests/fixtures/Test.cgl",
                    "resourceFactMode": "empty-resource-facts",
                },
                {
                    "path": resource_fixture_path,
                    "resourceFactMode": "single-storage-buffer-binding",
                },
            ],
        }
        fixture = {
            "kind": FIXTURE_KIND,
            "fixtures": [
                {
                    "path": "tests/fixtures/Test.cgl",
                    "stage": "compute",
                    "entryPoint": "main",
                    "sourceLocationFacts": source_facts,
                    "typeFacts": type_facts,
                    "parityRequirements": {
                        "entryPoint": {
                            "fields": [
                                "stage",
                                "entryPoint",
                                "resourceFacts.localSize",
                            ]
                        },
                        "sourceLocations": {"fields": source_facts},
                        "typeFacts": {"fields": type_facts},
                        "sourceMapDebugPreservation": {
                            "fields": source_map_debug_facts
                        },
                        "resources": {"fields": resource_fields},
                        "targetIndependentResourceMetadata": {
                            "fields": [RESOURCE_METADATA_COLLECTION]
                        },
                    },
                    "parityReportFields": {
                        "sourceFile": {
                            "fields": ["path", "sourceLocationFacts.source_file"]
                        },
                        "entryPoint": {"fields": ["stage", "entryPoint"]},
                        "entryPointIdentity": {
                            "fields": list(ENTRY_POINT_IDENTITY_REPORT_FIELDS)
                        },
                        "workgroupSize": {
                            "fields": [
                                "resourceFacts.localSize",
                                "sourceLocationFacts.layout_local_size",
                            ]
                        },
                        "resourceBindings": {
                            "fields": list(RESOURCE_COLLECTION_FIELDS)
                        },
                        "targetIndependentResourceMetadata": {
                            "fields": [RESOURCE_METADATA_COLLECTION]
                        },
                        "typeFacts": {"fields": ["typeFacts.void_entry_point"]},
                        "sourceMapDebugPreservation": {
                            "fields": source_map_debug_facts
                        },
                    },
                    "resourceFacts": {
                        "localSize": [1, 1, 1],
                        "descriptors": [],
                        "storageBuffers": [],
                        "storageImages": [],
                        "textures": [],
                        "samplers": [],
                        "targetIndependentResourceMetadata": [],
                    },
                },
                {
                    "path": resource_fixture_path,
                    "stage": "compute",
                    "entryPoint": "main",
                    "sourceLocationFacts": resource_source_facts,
                    "typeFacts": resource_type_facts,
                    "parityRequirements": {
                        "entryPoint": {
                            "fields": [
                                "stage",
                                "entryPoint",
                                "resourceFacts.localSize",
                            ]
                        },
                        "sourceLocations": {"fields": resource_source_facts},
                        "typeFacts": {"fields": resource_type_facts},
                        "sourceMapDebugPreservation": {
                            "fields": resource_source_map_debug_facts
                        },
                        "resources": {"fields": resource_bound_fields},
                        "targetIndependentResourceMetadata": {
                            "fields": resource_metadata_fields
                        },
                    },
                    "parityReportFields": {
                        "sourceFile": {
                            "fields": ["path", "sourceLocationFacts.source_file"]
                        },
                        "entryPoint": {"fields": ["stage", "entryPoint"]},
                        "entryPointIdentity": {
                            "fields": list(ENTRY_POINT_IDENTITY_REPORT_FIELDS)
                        },
                        "workgroupSize": {
                            "fields": [
                                "resourceFacts.localSize",
                                "sourceLocationFacts.layout_local_size",
                            ]
                        },
                        "resourceBindings": {"fields": resource_bound_fields[1:]},
                        "targetIndependentResourceMetadata": {
                            "fields": resource_metadata_fields
                        },
                        "typeFacts": {
                            "fields": prefixed_fact_fields(
                                "typeFacts", resource_type_facts
                            )
                        },
                        "sourceMapDebugPreservation": {
                            "fields": resource_source_map_debug_facts
                        },
                    },
                    "resourceFacts": {
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
                    },
                },
            ],
        }
        manifest = {
            "kind": MANIFEST_KIND,
            "eligibleFixtures": [
                {
                    "path": "tests/fixtures/Test.cgl",
                    "experimentSlice": "test",
                    "loweringStatus": "eligible-report-only",
                    "boundaryFactCoverage": {
                        "sourceLocationFacts": source_facts,
                        "entryPointFacts": list(ENTRY_POINT_IDENTITY_FIELDS),
                        "resourceFactFields": resource_fields,
                        "targetIndependentResourceMetadataFields": [
                            RESOURCE_METADATA_COLLECTION
                        ],
                        "targetIndependentTypeFacts": type_facts,
                        "sourceMapDebugFacts": source_map_debug_facts,
                    },
                },
                {
                    "path": resource_fixture_path,
                    "experimentSlice": "resource-test",
                    "loweringStatus": "eligible-report-only",
                    "boundaryFactCoverage": {
                        "sourceLocationFacts": resource_source_facts,
                        "entryPointFacts": list(ENTRY_POINT_IDENTITY_FIELDS),
                        "resourceFactFields": resource_bound_fields,
                        "targetIndependentResourceMetadataFields": (
                            resource_metadata_fields
                        ),
                        "targetIndependentTypeFacts": resource_type_facts,
                        "sourceMapDebugFacts": resource_source_map_debug_facts,
                    },
                },
            ],
        }
        op_type_fixture_paths_for_test = sorted_unique(
            ["tests/fixtures/Test.cgl", resource_fixture_path]
        )
        op_type_catalog = {
            "kind": OP_TYPE_CATALOG_KIND,
            "status": OP_TYPE_CATALOG_STATUS,
            "coverageSummary": {"fixtures": op_type_fixture_paths_for_test},
            "operations": [
                {
                    "operation": "hir.module",
                    "fixtures": op_type_fixture_paths_for_test,
                    "fixtureCoverage": [
                        {
                            "path": path,
                            "missingRequiredFacts": [],
                        }
                        for path in op_type_fixture_paths_for_test
                    ],
                },
                {
                    "operation": "hir.storage_buffer",
                    "fixtures": [resource_fixture_path],
                    "fixtureCoverage": [
                        {
                            "path": resource_fixture_path,
                            "missingRequiredFacts": [],
                        }
                    ],
                },
            ],
            "types": [
                {"typeFact": type_fact}
                for type_fact in sorted_unique([*type_facts, *resource_type_facts])
            ],
        }
        write_json(root / BOUNDARY_PATH, boundary)
        write_json(root / FIXTURE_PATH, fixture)
        write_json(root / MANIFEST_PATH, manifest)
        write_json(root / OP_TYPE_CATALOG_PATH, op_type_catalog)
        generated = derive_catalog(root)
        check_catalog_shape(generated, errors)
        resource_fixture_index = next(
            index
            for index, item in enumerate(generated["fixtures"])
            if item["path"] == resource_fixture_path
        )

        stale = copy.deepcopy(generated)
        stale["fixtures"][0]["sourceLocations"]["missingFromManifest"] = ["entry_point"]
        stale_errors: list[str] = []
        check_catalog_shape(stale, stale_errors)
        if not any(
            "missingFromManifest must be empty" in error for error in stale_errors
        ):
            errors.append("self-test failed to catch missing source-location facts")

        stale = copy.deepcopy(generated)
        stale["fixtures"][0]["sourceLocations"]["manifestFacts"] = source_facts[:-1]
        stale["fixtures"][0]["sourceLocations"]["missingFromManifest"] = []
        stale_errors = []
        check_catalog_shape(stale, stale_errors)
        if not any(
            "sourceLocations.manifestFacts must be" in error for error in stale_errors
        ):
            errors.append("self-test failed to catch hidden source-location omission")

        stale = copy.deepcopy(generated)
        stale["fixtures"][0]["entryPointIdentity"]["missingManifestFields"] = [
            "typeFacts.void_entry_point"
        ]
        stale_errors = []
        check_catalog_shape(stale, stale_errors)
        if not any(
            "entryPointIdentity.missingManifestFields must be empty" in error
            for error in stale_errors
        ):
            errors.append("self-test failed to catch missing entry-point identity")

        stale = copy.deepcopy(generated)
        stale["fixtures"][0]["targetIndependentTypeFacts"]["manifestFacts"] = []
        stale_errors = []
        check_catalog_shape(stale, stale_errors)
        if not any(
            "targetIndependentTypeFacts.manifestFacts must match" in error
            for error in stale_errors
        ):
            errors.append("self-test failed to catch missing type-fact coverage")

        stale = copy.deepcopy(generated)
        stale["fixtures"][0]["sourceMapDebugFacts"]["manifestFacts"] = list(
            REQUIRED_SOURCE_MAP_DEBUG_FACTS
        )
        stale_errors = []
        check_catalog_shape(stale, stale_errors)
        if not any(
            "sourceMapDebugFacts.manifestFacts must be" in error
            for error in stale_errors
        ):
            errors.append("self-test failed to catch missing source-map debug facts")

        stale = copy.deepcopy(generated)
        stale["fixtures"][resource_fixture_index]["resourceFacts"][
            "manifestFields"
        ].remove("resourceFacts.descriptors[].binding")
        stale_errors = []
        check_catalog_shape(stale, stale_errors)
        if not any(
            "resourceFacts.manifestFields must be" in error for error in stale_errors
        ):
            errors.append("self-test failed to catch missing resource binding facts")

        stale = copy.deepcopy(generated)
        stale["fixtures"][resource_fixture_index]["parityEvidence"][
            "resourceRequirementFields"
        ].remove("resourceFacts.storageBuffers[].writeAccess")
        stale_errors = []
        check_catalog_shape(stale, stale_errors)
        if not any(
            "resourceRequirementFields must be" in error for error in stale_errors
        ):
            errors.append("self-test failed to catch stale resource parity evidence")

        stale = copy.deepcopy(generated)
        stale["fixtures"][resource_fixture_index]["targetIndependentResourceMetadata"][
            "manifestFields"
        ].remove("resourceFacts.targetIndependentResourceMetadata[].access")
        stale_errors = []
        check_catalog_shape(stale, stale_errors)
        if not any(
            "targetIndependentResourceMetadata.manifestFields must be" in error
            for error in stale_errors
        ):
            errors.append(
                "self-test failed to catch missing target-independent resource "
                "metadata facts"
            )

        stale = copy.deepcopy(generated)
        stale["fixtures"][resource_fixture_index][
            "sourceResourceEntrypointPreservation"
        ]["manifestRequiredFields"].remove("sourceLocationFacts.layout_local_size")
        stale_errors = []
        check_catalog_shape(stale, stale_errors)
        if not any(
            "sourceResourceEntrypointPreservation.manifestRequiredFields must be"
            in error
            for error in stale_errors
        ):
            errors.append(
                "self-test failed to catch missing source/resource/entrypoint "
                "preservation evidence"
            )

        stale = copy.deepcopy(generated)
        stale["parityCoverageMatrix"]["fixtures"][resource_fixture_index]["dimensions"][
            "resources"
        ]["covered"] = False
        stale_errors = []
        check_catalog_shape(stale, stale_errors)
        if not any(
            "parityCoverageMatrix must match source, entry point, resource, "
            "metadata, and source-map/debug fixture evidence" in error
            for error in stale_errors
        ):
            errors.append("self-test failed to catch stale parity coverage matrix")

        stale = copy.deepcopy(generated)
        stale["catalogConsistency"]["fixtureUniverse"]["missingFromOpTypeCatalog"] = [
            "tests/fixtures/Test.cgl"
        ]
        stale_errors = []
        check_catalog_shape(stale, stale_errors)
        if not any(
            "catalogConsistency.fixtureUniverse.missingFromOpTypeCatalog "
            "must be empty" in error
            for error in stale_errors
        ):
            errors.append("self-test failed to catch catalog fixture drift")

        stale = copy.deepcopy(generated)
        stale["catalogConsistency"]["targetIndependentTypeFacts"][
            "missingFromSourceResourceCatalog"
        ] = ["float_scalar"]
        stale_errors = []
        check_catalog_shape(stale, stale_errors)
        if not any(
            "catalogConsistency.targetIndependentTypeFacts."
            "missingFromSourceResourceCatalog must be empty" in error
            for error in stale_errors
        ):
            errors.append("self-test failed to catch catalog type-fact drift")

        stale = copy.deepcopy(generated)
        stale["catalogConsistency"]["operationFixtureCoverage"][
            "missingRequiredFactRows"
        ] = [
            {
                "operation": "hir.module",
                "path": "tests/fixtures/Test.cgl",
                "missingRequiredFacts": ["source_file"],
            }
        ]
        stale_errors = []
        check_catalog_shape(stale, stale_errors)
        if not any(
            "catalogConsistency.operationFixtureCoverage."
            "missingRequiredFactRows must be empty" in error
            for error in stale_errors
        ):
            errors.append(
                "self-test failed to catch op/type catalog missing-fact drift"
            )

        stale = copy.deepcopy(generated)
        stale["fixtures"][0]["parityEvidence"]["reportFields"]["typeFacts"] = []
        stale_errors = []
        check_catalog_shape(stale, stale_errors)
        if not any("reportFields.typeFacts must be" in error for error in stale_errors):
            errors.append("self-test failed to catch stale parity report type facts")

        stale = copy.deepcopy(generated)
        stale["generation"]["optionalMlirToolingRequired"] = True
        stale_errors = []
        check_catalog_shape(stale, stale_errors)
        if not any(
            "optionalMlirToolingRequired must be False" in error
            for error in stale_errors
        ):
            errors.append("self-test failed to catch MLIR toolchain requirement")
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
        "--update",
        action="store_true",
        help=f"rewrite {CATALOG_PATH} from current report-only inputs",
    )
    parser.add_argument(
        "--self-test",
        action="store_true",
        help="run internal checker tests instead of auditing a repository",
    )
    return parser.parse_args(argv)


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    if args.self_test:
        errors = run_self_test()
        fixture_count = 0
    else:
        errors, fixture_count = check_repo(args.root.resolve(), update=args.update)
    if errors:
        for error in errors:
            print(f"error: {error}", file=sys.stderr)
        return 1
    if args.self_test:
        print("MLIR source/resource catalog self-test passed")
    elif args.update:
        print(f"Updated {CATALOG_PATH} ({fixture_count} fixture preservation records)")
    else:
        print(
            "MLIR source/resource catalog audit passed "
            f"({fixture_count} fixture preservation records)"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
