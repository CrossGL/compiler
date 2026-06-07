#!/usr/bin/env python3
"""Generate and validate a report-only MLIR textual dialect projection.

The projection is a fixture-limited catalog of future `hir.*` textual operation
shapes plus source/resource preservation facts. It intentionally does not import
compiler modules, lower HIR, register a dialect, invoke MLIR tools, or replace
the production pseudo-MLIR output.
"""

from __future__ import annotations

import argparse
import copy
import json
import re
import sys
import tempfile
from pathlib import Path
from typing import Any


CATALOG_PATH = Path("experimental/mlir/textual_dialect_projection.v0.json")
BOUNDARY_PATH = Path("experimental/mlir/boundary_inventory.v0.json")
FIXTURE_PATH = Path("experimental/mlir/fixture_inventory.json")
MANIFEST_PATH = Path("experimental/mlir/experiment_manifest.json")

CATALOG_KIND = "crossgl-mlir-textual-dialect-projection-v0"
BOUNDARY_KIND = "crossgl-mlir-boundary-inventory-v0"
FIXTURE_KIND = "crossgl-mlir-experiment-fixture-inventory"
MANIFEST_KIND = "crossgl-mlir-experiment-manifest"
CATALOG_STATUS = "report-only-textual-dialect-projection"
DERIVED_FROM = (
    BOUNDARY_PATH.as_posix(),
    FIXTURE_PATH.as_posix(),
    MANIFEST_PATH.as_posix(),
)
REQUIRED_TOP_LEVEL_KEYS = (
    "schemaVersion",
    "kind",
    "status",
    "scope",
    "generation",
    "dialect",
    "textualProjectionContract",
    "fixtures",
    "operations",
    "verificationPlan",
    "coverageSummary",
)
GENERATION_KEYS = (
    "deterministic",
    "derivedFrom",
    "optionalMlirToolingRequired",
    "productionLinked",
    "normalBuildRequired",
    "registersDialect",
    "emitsRealMlir",
    "separatesPseudoMlir",
)
FIXTURE_KEYS = (
    "path",
    "stage",
    "entryPoint",
    "experimentSlice",
    "loweringStatus",
    "resourceFactMode",
    "expectedOperations",
    "textualModuleSkeleton",
    "sourceResourcePreservation",
)
OPERATION_KEYS = (
    "operation",
    "textualForm",
    "emissionStatus",
    "role",
    "allowedHirFamilies",
    "fixtures",
    "sourceLocationFactsRequired",
    "typeFactsRequired",
    "resourceFieldsRequired",
    "fixtureCoverage",
)
SOURCE_RESOURCE_KEYS = (
    "sourceLocationFacts",
    "entryPointFields",
    "targetIndependentTypeFacts",
    "resourceFactFields",
    "targetIndependentResourceMetadataFields",
    "sourceMapDebugFacts",
)
FIXTURE_COVERAGE_KEYS = (
    "path",
    "presentInBoundaryFixture",
    "matchedRequiredFacts",
    "missingRequiredFacts",
)
OPERATION_NAMING_BOUNDARY_KEYS = (
    "operationPrefix",
    "blockedNamespace",
    "boundaryInventoryOperations",
    "projectedOperations",
    "allProjectedOperationsFromBoundaryInventory",
    "allProjectedOperationsUseCanonicalPrefix",
    "blockedNamespaceOperationCount",
)
OPERATION_NAME_PATTERN = re.compile(r"^hir\.[A-Za-z_][A-Za-z0-9_.-]*$")


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


def load_inputs(root: Path) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    boundary = require_loaded_object(root / BOUNDARY_PATH, BOUNDARY_KIND)
    fixture = require_loaded_object(root / FIXTURE_PATH, FIXTURE_KIND)
    manifest = require_loaded_object(root / MANIFEST_PATH, MANIFEST_KIND)
    return boundary, fixture, manifest


def manifest_fixture_records(manifest: dict[str, Any]) -> dict[str, dict[str, Any]]:
    records: dict[str, dict[str, Any]] = {}
    for item in manifest.get("eligibleFixtures", []):
        if isinstance(item, dict) and isinstance(item.get("path"), str):
            records[item["path"]] = item
    return records


def fixture_records(fixture_inventory: dict[str, Any]) -> dict[str, dict[str, Any]]:
    records: dict[str, dict[str, Any]] = {}
    for item in fixture_inventory.get("fixtures", []):
        if isinstance(item, dict) and isinstance(item.get("path"), str):
            records[item["path"]] = item
    return records


def boundary_fixture_records(boundary: dict[str, Any]) -> dict[str, dict[str, Any]]:
    records: dict[str, dict[str, Any]] = {}
    for item in boundary.get("fixtureBoundary", []):
        if isinstance(item, dict) and isinstance(item.get("path"), str):
            records[item["path"]] = item
    return records


def coverage_fact_universe(coverage: dict[str, Any]) -> set[str]:
    facts: set[str] = set()
    for section, value in coverage.items():
        if not isinstance(value, list):
            continue
        for fact in value:
            if not isinstance(fact, str):
                continue
            facts.add(fact)
            if section == "sourceLocationFacts":
                facts.add(f"sourceLocationFacts.{fact}")
            elif section == "targetIndependentTypeFacts":
                facts.add(f"typeFacts.{fact}")
    return facts


def classify_required_facts(
    required_facts: list[str],
) -> tuple[list[str], list[str], list[str]]:
    source_facts: list[str] = []
    type_facts: list[str] = []
    resource_fields: list[str] = []
    for fact in required_facts:
        if fact.startswith("typeFacts."):
            type_facts.append(fact)
        elif fact.startswith("resourceFacts."):
            resource_fields.append(fact)
        elif fact in {"stage", "entryPoint"}:
            source_facts.append(fact)
        else:
            source_facts.append(fact)
    return source_facts, type_facts, resource_fields


def textual_form_for_operation(operation: str) -> str:
    if operation == "hir.module":
        return 'hir.module @${module} attributes {source = "${source_file}"}'
    if operation == "hir.compute_stage":
        return 'hir.compute_stage @compute attributes {stage = "compute"}'
    if operation == "hir.entry_point":
        return "hir.entry_point @${entryPoint} : () -> !hir.void"
    if operation == "hir.workgroup_size":
        return "hir.workgroup_size [${local_size_x}, ${local_size_y}, ${local_size_z}]"
    if operation == "hir.return":
        return "hir.return loc(${return_statement})"
    if operation == "hir.source_location_anchor":
        return "hir.source_location_anchor {source_file, shader_module, compute_stage, entry_point, layout_local_size, return_statement}"
    if operation == "hir.resource":
        return 'hir.resource @${resourceName} {set = ${set}, binding = ${binding}, kind = "${kind}"}'
    if operation == "hir.storage_buffer":
        return "hir.storage_buffer @${resourceName} : !hir.storage_buffer<!hir.f32>"
    if operation == "hir.storage_buffer.read":
        return "hir.storage_buffer.read @${resourceName}[${index}] : !hir.f32"
    if operation == "hir.storage_buffer.write":
        return (
            "hir.storage_buffer.write @${resourceName}[${index}], ${value} : !hir.f32"
        )
    if operation == "hir.if":
        return "hir.if ${condition} : !hir.bool { ... } else { ... }"
    if operation == "hir.scalar_compare":
        return "hir.scalar_compare ${lhs}, ${rhs} : !hir.f32 -> !hir.bool"
    if operation == "hir.scalar_declare":
        return "hir.scalar_declare @${name} : !hir.f32"
    if operation == "hir.scalar_expr":
        return "hir.scalar_expr ${expr} : !hir.f32"
    return f"{operation} ..."


def scalar_value(resource_facts: dict[str, Any], key: str, fallback: str) -> str:
    value = resource_facts.get(key)
    if isinstance(value, (str, int, float)):
        return str(value)
    return fallback


def hir_type_name(source_type: str) -> str:
    return {
        "float": "f32",
        "int": "i32",
        "uint": "ui32",
        "bool": "bool",
    }.get(source_type, source_type)


def resource_lines(resource_facts: dict[str, Any]) -> list[str]:
    descriptors = resource_facts.get("descriptors")
    storage_buffers = resource_facts.get("storageBuffers")
    lines: list[str] = []
    if isinstance(descriptors, list):
        for descriptor in descriptors:
            if not isinstance(descriptor, dict):
                continue
            name = scalar_value(descriptor, "name", "resource")
            kind = scalar_value(descriptor, "kind", "storage_buffer")
            set_index = scalar_value(descriptor, "set", "0")
            binding = scalar_value(descriptor, "binding", "0")
            lines.append(
                f'  hir.resource @{name} {{set = {set_index}, binding = {binding}, kind = "{kind}"}}'
            )
    if isinstance(storage_buffers, list):
        for storage_buffer in storage_buffers:
            if not isinstance(storage_buffer, dict):
                continue
            name = scalar_value(storage_buffer, "name", "resource")
            element_type = hir_type_name(
                scalar_value(storage_buffer, "elementType", "float")
            )
            lines.append(
                f"  hir.storage_buffer @{name} : !hir.storage_buffer<!hir.{element_type}>"
            )
    return lines


def textual_module_skeleton(
    fixture_path: str,
    fixture: dict[str, Any],
    boundary_record: dict[str, Any],
) -> list[str]:
    module_name = Path(fixture_path).stem
    entry_point = fixture.get("entryPoint", "main")
    resource_facts = fixture.get("resourceFacts")
    if not isinstance(resource_facts, dict):
        resource_facts = {}
    local_size = resource_facts.get("localSize")
    if not isinstance(local_size, list) or len(local_size) != 3:
        local_size = [1, 1, 1]
    lines = [
        f'hir.module @{module_name} attributes {{source = "{fixture_path}"}} {{',
        '  hir.compute_stage @compute attributes {stage = "compute"}',
        f"  hir.entry_point @{entry_point} : () -> !hir.void",
        f"  hir.workgroup_size [{local_size[0]}, {local_size[1]}, {local_size[2]}]",
    ]
    lines.extend(resource_lines(resource_facts))
    if "hir.if" in string_list(boundary_record.get("expectedOperations")):
        lines.append("  hir.if %branch_condition : !hir.bool { ... } else { ... }")
    lines.extend(
        [
            "  hir.return loc(return_statement)",
            "  hir.source_location_anchor {source_file, shader_module, compute_stage, entry_point, layout_local_size, return_statement}",
            "}",
        ]
    )
    return lines


def derive_fixture_projection(
    fixture_inventory: dict[str, Any],
    manifest: dict[str, Any],
    boundary: dict[str, Any],
) -> list[dict[str, Any]]:
    fixtures = fixture_records(fixture_inventory)
    manifest_by_path = manifest_fixture_records(manifest)
    boundary_by_path = boundary_fixture_records(boundary)
    projections: list[dict[str, Any]] = []
    for fixture_path in sorted(fixtures):
        fixture = fixtures[fixture_path]
        manifest_record = manifest_by_path.get(fixture_path, {})
        boundary_record = boundary_by_path.get(fixture_path, {})
        coverage = manifest_record.get("boundaryFactCoverage")
        if not isinstance(coverage, dict):
            coverage = {}
        projections.append(
            {
                "path": fixture_path,
                "stage": fixture.get("stage"),
                "entryPoint": fixture.get("entryPoint"),
                "experimentSlice": manifest_record.get("experimentSlice"),
                "loweringStatus": manifest_record.get("loweringStatus"),
                "resourceFactMode": boundary_record.get("resourceFactMode"),
                "expectedOperations": string_list(
                    boundary_record.get("expectedOperations")
                ),
                "textualModuleSkeleton": textual_module_skeleton(
                    fixture_path, fixture, boundary_record
                ),
                "sourceResourcePreservation": {
                    "sourceLocationFacts": string_list(
                        coverage.get("sourceLocationFacts")
                    ),
                    "entryPointFields": string_list(coverage.get("entryPointFacts")),
                    "targetIndependentTypeFacts": string_list(
                        coverage.get("targetIndependentTypeFacts")
                    ),
                    "resourceFactFields": string_list(
                        coverage.get("resourceFactFields")
                    ),
                    "targetIndependentResourceMetadataFields": string_list(
                        coverage.get("targetIndependentResourceMetadataFields")
                    ),
                    "sourceMapDebugFacts": string_list(
                        coverage.get("sourceMapDebugFacts")
                    ),
                },
            }
        )
    return projections


def derive_operation_projection(
    boundary: dict[str, Any],
    manifest: dict[str, Any],
    fixture_projections: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    manifest_by_path = manifest_fixture_records(manifest)
    boundary_expected_by_fixture = {
        item["path"]: string_list(item.get("expectedOperations"))
        for item in fixture_projections
        if isinstance(item.get("path"), str)
    }
    operations: list[dict[str, Any]] = []
    for item in boundary.get("operations", []):
        if not isinstance(item, dict):
            continue
        operation = item.get("operation")
        if not isinstance(operation, str):
            operation = ""
        required_facts = string_list(item.get("requiredFixtureFacts"))
        source_facts, type_facts, resource_fields = classify_required_facts(
            required_facts
        )
        fixture_coverage = []
        for fixture_path in string_list(item.get("fixtures")):
            manifest_record = manifest_by_path.get(fixture_path, {})
            coverage = manifest_record.get("boundaryFactCoverage")
            if not isinstance(coverage, dict):
                coverage = {}
            fact_universe = coverage_fact_universe(coverage)
            matched = [fact for fact in required_facts if fact in fact_universe]
            missing = [fact for fact in required_facts if fact not in fact_universe]
            expected_operations = boundary_expected_by_fixture.get(fixture_path, [])
            fixture_coverage.append(
                {
                    "path": fixture_path,
                    "presentInBoundaryFixture": operation in expected_operations,
                    "matchedRequiredFacts": matched,
                    "missingRequiredFacts": missing,
                }
            )
        operations.append(
            {
                "operation": operation,
                "textualForm": textual_form_for_operation(operation),
                "emissionStatus": "not-emitted-report-only",
                "role": item.get("role"),
                "allowedHirFamilies": string_list(item.get("allowedHirFamilies")),
                "fixtures": string_list(item.get("fixtures")),
                "sourceLocationFactsRequired": source_facts,
                "typeFactsRequired": type_facts,
                "resourceFieldsRequired": resource_fields,
                "fixtureCoverage": fixture_coverage,
            }
        )
    return operations


def derive_catalog(root: Path) -> dict[str, Any]:
    boundary, fixture_inventory, manifest = load_inputs(root)
    source_authority = boundary.get("sourceAuthority")
    if not isinstance(source_authority, dict):
        source_authority = {}
    fixtures = derive_fixture_projection(fixture_inventory, manifest, boundary)
    operations = derive_operation_projection(boundary, manifest, fixtures)
    operation_names = [item["operation"] for item in operations]
    resource_bound = [
        item["path"]
        for item in fixtures
        if item.get("resourceFactMode") == "single-storage-buffer-binding"
    ]
    operation_prefix = source_authority.get("operationPrefix", "hir.")
    if not isinstance(operation_prefix, str):
        operation_prefix = "hir."
    blocked_namespace = source_authority.get("blockedNamespace", "crossgl.")
    if not isinstance(blocked_namespace, str):
        blocked_namespace = "crossgl."
    return {
        "schemaVersion": 1,
        "kind": CATALOG_KIND,
        "status": CATALOG_STATUS,
        "scope": "fixture-limited report-only textual projection for a future CrossGL HIR MLIR dialect",
        "generation": {
            "deterministic": True,
            "derivedFrom": list(DERIVED_FROM),
            "optionalMlirToolingRequired": False,
            "productionLinked": False,
            "normalBuildRequired": False,
            "registersDialect": False,
            "emitsRealMlir": False,
            "separatesPseudoMlir": True,
        },
        "dialect": {
            "canonicalNamespace": source_authority.get("hirNamespace", "hir"),
            "operationPrefix": source_authority.get("operationPrefix", "hir."),
            "blockedNamespace": source_authority.get("blockedNamespace", "crossgl."),
            "authorityAnchors": string_list(source_authority.get("authorityAnchors")),
            "typeNamespace": "hir",
        },
        "textualProjectionContract": {
            "status": "catalog-only-not-parser-input",
            "operationsMustUseCanonicalHirPrefix": True,
            "mustNotRegisterDialect": True,
            "mustNotReplacePseudoMlir": True,
            "mustPreserveSourceLocations": True,
            "mustPreserveEntrypointIdentity": True,
            "mustPreserveTargetIndependentTypes": True,
            "mustPreserveTargetIndependentResources": True,
        },
        "fixtures": fixtures,
        "operations": operations,
        "verificationPlan": {
            "currentStatus": "report-only-no-mlir-tool-required",
            "futureVerifier": "mlir-opt --verify-diagnostics after a real hir dialect exists",
            "currentChecker": "tools/check_mlir_textual_dialect_projection.py",
            "optionalMlirToolingRequired": False,
            "productionLinked": False,
        },
        "coverageSummary": {
            "fixtureCount": len(fixtures),
            "operationCount": len(operations),
            "resourceBoundFixtureCount": len(resource_bound),
            "resourceBoundFixtures": resource_bound,
            "fixtures": [item["path"] for item in fixtures],
            "operationNamingBoundary": {
                "operationPrefix": operation_prefix,
                "blockedNamespace": blocked_namespace,
                "boundaryInventoryOperations": operation_names,
                "projectedOperations": operation_names,
                "allProjectedOperationsFromBoundaryInventory": True,
                "allProjectedOperationsUseCanonicalPrefix": all(
                    operation.startswith(operation_prefix)
                    for operation in operation_names
                ),
                "blockedNamespaceOperationCount": sum(
                    1
                    for operation in operation_names
                    if operation.startswith(blocked_namespace)
                ),
            },
        },
    }


def compare_fields(
    actual: list[str], expected: list[str], field: str, errors: list[str]
) -> None:
    if actual != expected:
        errors.append(f"{CATALOG_PATH}: {field} must be {expected!r}, got {actual!r}")


def check_fixture_projection(
    record: dict[str, Any], index: int, errors: list[str]
) -> str:
    if tuple(record) != FIXTURE_KEYS:
        errors.append(f"{CATALOG_PATH}: fixtures[{index}] schema changed")
    path = record.get("path")
    if not isinstance(path, str) or not path:
        errors.append(f"{CATALOG_PATH}: fixtures[{index}].path invalid")
        path = ""
    if record.get("stage") != "compute":
        errors.append(f"{CATALOG_PATH}: fixtures[{index}].stage must be 'compute'")
    if not isinstance(record.get("entryPoint"), str) or not record["entryPoint"]:
        errors.append(f"{CATALOG_PATH}: fixtures[{index}].entryPoint invalid")
    expected_operations = string_list(record.get("expectedOperations"))
    if not expected_operations:
        errors.append(f"{CATALOG_PATH}: fixtures[{index}].expectedOperations empty")
    for operation in expected_operations:
        if not OPERATION_NAME_PATTERN.match(operation):
            errors.append(
                f"{CATALOG_PATH}: fixtures[{index}].expectedOperations contains "
                f"invalid operation {operation!r}"
            )
    skeleton = string_list(record.get("textualModuleSkeleton"))
    if len(skeleton) < 6:
        errors.append(f"{CATALOG_PATH}: fixtures[{index}].textualModuleSkeleton short")
    if any("crossgl." in line for line in skeleton):
        errors.append(
            f"{CATALOG_PATH}: fixtures[{index}].textualModuleSkeleton uses blocked namespace"
        )
    required_skeleton_tokens = (
        "hir.module",
        "hir.compute_stage",
        "hir.entry_point",
        "hir.workgroup_size",
        "hir.return",
        "hir.source_location_anchor",
    )
    for token in required_skeleton_tokens:
        if not any(token in line for line in skeleton):
            errors.append(
                f"{CATALOG_PATH}: fixtures[{index}].textualModuleSkeleton missing {token}"
            )
    preservation = require_object(
        record.get("sourceResourcePreservation"),
        f"fixtures[{index}].sourceResourcePreservation",
        errors,
    )
    if tuple(preservation) != SOURCE_RESOURCE_KEYS:
        errors.append(
            f"{CATALOG_PATH}: fixtures[{index}].sourceResourcePreservation schema changed"
        )
    for required_source_fact in (
        "source_file",
        "shader_module",
        "compute_stage",
        "entry_point",
        "layout_local_size",
        "return_statement",
    ):
        if required_source_fact not in string_list(
            preservation.get("sourceLocationFacts")
        ):
            errors.append(
                f"{CATALOG_PATH}: fixtures[{index}] missing source fact "
                f"{required_source_fact!r}"
            )
    if "void_entry_point" not in string_list(
        preservation.get("targetIndependentTypeFacts")
    ):
        errors.append(
            f"{CATALOG_PATH}: fixtures[{index}] missing void_entry_point type fact"
        )
    if "resourceFacts.localSize" not in string_list(
        preservation.get("resourceFactFields")
    ):
        errors.append(f"{CATALOG_PATH}: fixtures[{index}] missing local size field")
    if (
        record.get("resourceFactMode") == "single-storage-buffer-binding"
        and "hir.resource" not in expected_operations
    ):
        errors.append(
            f"{CATALOG_PATH}: fixtures[{index}] resource-bound fixture lacks hir.resource"
        )
    return path


def check_operation_projection(
    record: dict[str, Any],
    index: int,
    expected_operations_by_fixture: dict[str, list[str]],
    errors: list[str],
) -> str:
    if tuple(record) != OPERATION_KEYS:
        errors.append(f"{CATALOG_PATH}: operations[{index}] schema changed")
    operation = record.get("operation")
    if not isinstance(operation, str) or not OPERATION_NAME_PATTERN.match(operation):
        errors.append(f"{CATALOG_PATH}: operations[{index}].operation invalid")
        operation = ""
    textual_form = record.get("textualForm")
    if not isinstance(textual_form, str) or not textual_form.startswith(operation):
        errors.append(
            f"{CATALOG_PATH}: operations[{index}].textualForm must start with operation"
        )
    if "crossgl." in str(textual_form):
        errors.append(f"{CATALOG_PATH}: operations[{index}].textualForm blocked")
    if record.get("emissionStatus") != "not-emitted-report-only":
        errors.append(f"{CATALOG_PATH}: operations[{index}].emissionStatus invalid")
    for coverage_index, coverage in enumerate(
        require_list(
            record.get("fixtureCoverage"),
            f"operations[{index}].fixtureCoverage",
            errors,
        )
    ):
        coverage_record = require_object(
            coverage,
            f"operations[{index}].fixtureCoverage[{coverage_index}]",
            errors,
        )
        if tuple(coverage_record) != FIXTURE_COVERAGE_KEYS:
            errors.append(
                f"{CATALOG_PATH}: operations[{index}].fixtureCoverage[{coverage_index}] schema changed"
            )
        fixture_path = coverage_record.get("path")
        if not isinstance(fixture_path, str):
            errors.append(
                f"{CATALOG_PATH}: operations[{index}].fixtureCoverage[{coverage_index}].path invalid"
            )
            continue
        present = operation in expected_operations_by_fixture.get(fixture_path, [])
        if coverage_record.get("presentInBoundaryFixture") is not present:
            errors.append(
                f"{CATALOG_PATH}: operations[{index}].fixtureCoverage[{coverage_index}] "
                "does not match fixture boundary"
            )
        if coverage_record.get("missingRequiredFacts") != []:
            errors.append(
                f"{CATALOG_PATH}: operations[{index}].fixtureCoverage[{coverage_index}] "
                "missingRequiredFacts must be empty"
            )
    return operation


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
        "registersDialect": False,
        "emitsRealMlir": False,
        "separatesPseudoMlir": True,
    }
    for flag, expected in expected_flags.items():
        if generation.get(flag) is not expected:
            errors.append(f"{CATALOG_PATH}: generation.{flag} must be {expected}")
    if generation.get("derivedFrom") != list(DERIVED_FROM):
        errors.append(f"{CATALOG_PATH}: generation.derivedFrom is stale")

    dialect = require_object(catalog.get("dialect"), "dialect", errors)
    if dialect.get("canonicalNamespace") != "hir":
        errors.append(f"{CATALOG_PATH}: dialect.canonicalNamespace must be 'hir'")
    if dialect.get("operationPrefix") != "hir.":
        errors.append(f"{CATALOG_PATH}: dialect.operationPrefix must be 'hir.'")
    if dialect.get("blockedNamespace") == "hir.":
        errors.append(f"{CATALOG_PATH}: dialect.blockedNamespace invalid")

    contract = require_object(
        catalog.get("textualProjectionContract"), "textualProjectionContract", errors
    )
    for key in (
        "operationsMustUseCanonicalHirPrefix",
        "mustNotRegisterDialect",
        "mustNotReplacePseudoMlir",
        "mustPreserveSourceLocations",
        "mustPreserveEntrypointIdentity",
        "mustPreserveTargetIndependentTypes",
        "mustPreserveTargetIndependentResources",
    ):
        if contract.get(key) is not True:
            errors.append(f"{CATALOG_PATH}: textualProjectionContract.{key} true")
    if contract.get("status") != "catalog-only-not-parser-input":
        errors.append(f"{CATALOG_PATH}: textualProjectionContract.status invalid")

    fixtures = require_list(catalog.get("fixtures"), "fixtures", errors)
    fixture_paths: list[str] = []
    expected_operations_by_fixture: dict[str, list[str]] = {}
    for index, item in enumerate(fixtures):
        record = require_object(item, f"fixtures[{index}]", errors)
        path = check_fixture_projection(record, index, errors)
        fixture_paths.append(path)
        expected_operations_by_fixture[path] = string_list(
            record.get("expectedOperations")
        )
    if fixture_paths != sorted_unique(fixture_paths):
        errors.append(f"{CATALOG_PATH}: fixtures must be sorted unique by path")

    operations = require_list(catalog.get("operations"), "operations", errors)
    operation_names: list[str] = []
    for index, item in enumerate(operations):
        record = require_object(item, f"operations[{index}]", errors)
        operation_names.append(
            check_operation_projection(
                record, index, expected_operations_by_fixture, errors
            )
        )
    if len(operation_names) != len(set(operation_names)):
        errors.append(f"{CATALOG_PATH}: operations must be unique")
    expected_operation_set = {
        operation
        for expected_operations in expected_operations_by_fixture.values()
        for operation in expected_operations
    }
    missing_operations = sorted(expected_operation_set - set(operation_names))
    if missing_operations:
        errors.append(
            f"{CATALOG_PATH}: operations missing boundary fixtures: {missing_operations}"
        )

    verification = require_object(
        catalog.get("verificationPlan"), "verificationPlan", errors
    )
    if verification.get("optionalMlirToolingRequired") is not False:
        errors.append(f"{CATALOG_PATH}: verificationPlan must be MLIR-tool-free")
    if verification.get("productionLinked") is not False:
        errors.append(f"{CATALOG_PATH}: verificationPlan.productionLinked false")

    summary = require_object(catalog.get("coverageSummary"), "coverageSummary", errors)
    if summary.get("fixtureCount") != len(fixtures):
        errors.append(f"{CATALOG_PATH}: coverageSummary.fixtureCount stale")
    if summary.get("operationCount") != len(operations):
        errors.append(f"{CATALOG_PATH}: coverageSummary.operationCount stale")
    compare_fields(
        string_list(summary.get("fixtures")),
        fixture_paths,
        "coverageSummary.fixtures",
        errors,
    )
    naming = require_object(
        summary.get("operationNamingBoundary"),
        "coverageSummary.operationNamingBoundary",
        errors,
    )
    if tuple(naming) != OPERATION_NAMING_BOUNDARY_KEYS:
        errors.append(
            f"{CATALOG_PATH}: coverageSummary.operationNamingBoundary schema changed"
        )
    if naming.get("operationPrefix") != "hir.":
        errors.append(
            f"{CATALOG_PATH}: coverageSummary.operationNamingBoundary.operationPrefix "
            "must be 'hir.'"
        )
    if naming.get("blockedNamespace") != "crossgl.":
        errors.append(
            f"{CATALOG_PATH}: coverageSummary.operationNamingBoundary.blockedNamespace "
            "must be 'crossgl.'"
        )
    if string_list(naming.get("boundaryInventoryOperations")) != operation_names:
        errors.append(
            f"{CATALOG_PATH}: coverageSummary.operationNamingBoundary."
            "boundaryInventoryOperations must match projected operation order"
        )
    if string_list(naming.get("projectedOperations")) != operation_names:
        errors.append(
            f"{CATALOG_PATH}: coverageSummary.operationNamingBoundary.projectedOperations "
            "must match operations"
        )
    if naming.get("allProjectedOperationsFromBoundaryInventory") is not True:
        errors.append(
            f"{CATALOG_PATH}: coverageSummary.operationNamingBoundary."
            "allProjectedOperationsFromBoundaryInventory must be true"
        )
    if naming.get("allProjectedOperationsUseCanonicalPrefix") is not True:
        errors.append(
            f"{CATALOG_PATH}: coverageSummary.operationNamingBoundary."
            "allProjectedOperationsUseCanonicalPrefix must be true"
        )
    if naming.get("blockedNamespaceOperationCount") != 0:
        errors.append(
            f"{CATALOG_PATH}: coverageSummary.operationNamingBoundary."
            "blockedNamespaceOperationCount must be 0"
        )


def check_repo(root: Path, *, update: bool = False) -> tuple[list[str], dict[str, int]]:
    errors: list[str] = []
    try:
        derived = derive_catalog(root)
    except (OSError, ValueError) as error:
        return [str(error)], {"fixtures": 0, "operations": 0}

    if update:
        write_json(root / CATALOG_PATH, derived)
    else:
        try:
            actual = load_json(root / CATALOG_PATH)
        except (OSError, ValueError) as error:
            return [f"{CATALOG_PATH}: {error}"], {"fixtures": 0, "operations": 0}
        if actual != derived:
            errors.append(
                f"{CATALOG_PATH}: stale; regenerate with "
                "tools/check_mlir_textual_dialect_projection.py --update"
            )
        if isinstance(actual, dict):
            check_catalog_shape(actual, errors)
        else:
            errors.append(f"{CATALOG_PATH}: catalog must be an object")

    return errors, {
        "fixtures": len(derived["fixtures"]),
        "operations": len(derived["operations"]),
    }


def run_self_test() -> list[str]:
    errors: list[str] = []
    with tempfile.TemporaryDirectory() as temp_dir:
        root = Path(temp_dir)
        (root / "experimental/mlir").mkdir(parents=True)
        boundary = {
            "kind": BOUNDARY_KIND,
            "sourceAuthority": {
                "hirNamespace": "hir",
                "operationPrefix": "hir.",
                "blockedNamespace": "crossgl.",
                "authorityAnchors": ["include/crossgl/HIR/HIR.h"],
            },
            "operations": [
                {
                    "operation": "hir.module",
                    "role": "test module",
                    "allowedHirFamilies": ["module_stages_and_entry_points"],
                    "fixtures": ["tests/fixtures/Test.cgl"],
                    "requiredFixtureFacts": ["source_file", "shader_module"],
                }
            ],
            "fixtureBoundary": [
                {
                    "path": "tests/fixtures/Test.cgl",
                    "expectedOperations": ["hir.module"],
                    "resourceFactMode": "empty-resource-facts",
                }
            ],
        }
        fixture = {
            "kind": FIXTURE_KIND,
            "fixtures": [
                {
                    "path": "tests/fixtures/Test.cgl",
                    "stage": "compute",
                    "entryPoint": "main",
                    "resourceFacts": {"localSize": [1, 1, 1]},
                }
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
                        "sourceLocationFacts": [
                            "source_file",
                            "shader_module",
                            "compute_stage",
                            "entry_point",
                            "layout_local_size",
                            "return_statement",
                        ],
                        "entryPointFacts": [
                            "stage",
                            "entryPoint",
                            "sourceLocationFacts.shader_module",
                            "sourceLocationFacts.compute_stage",
                            "sourceLocationFacts.entry_point",
                            "typeFacts.void_entry_point",
                            "resourceFacts.localSize",
                        ],
                        "targetIndependentTypeFacts": ["void_entry_point"],
                        "resourceFactFields": [
                            "resourceFacts.localSize",
                            "resourceFacts.descriptors",
                            "resourceFacts.storageBuffers",
                            "resourceFacts.storageImages",
                            "resourceFacts.textures",
                            "resourceFacts.samplers",
                        ],
                        "targetIndependentResourceMetadataFields": [
                            "resourceFacts.targetIndependentResourceMetadata"
                        ],
                        "sourceMapDebugFacts": [
                            "ir/debug-metadata.json",
                            "ir/hir-source-map.json",
                        ],
                    },
                }
            ],
        }
        write_json(root / BOUNDARY_PATH, boundary)
        write_json(root / FIXTURE_PATH, fixture)
        write_json(root / MANIFEST_PATH, manifest)
        generated = derive_catalog(root)
        check_catalog_shape(generated, errors)

        stale = copy.deepcopy(generated)
        stale["operations"][0]["operation"] = "crossgl.module"
        stale_errors: list[str] = []
        check_catalog_shape(stale, stale_errors)
        if not any("operation invalid" in error for error in stale_errors):
            errors.append("self-test failed to catch blocked operation namespace")

        missing_fact = copy.deepcopy(generated)
        missing_fact["operations"][0]["fixtureCoverage"][0]["missingRequiredFacts"] = [
            "shader_module"
        ]
        missing_errors: list[str] = []
        check_catalog_shape(missing_fact, missing_errors)
        if not any(
            "missingRequiredFacts must be empty" in error for error in missing_errors
        ):
            errors.append("self-test failed to catch missing fixture facts")

        stale_naming = copy.deepcopy(generated)
        stale_naming["coverageSummary"]["operationNamingBoundary"][
            "allProjectedOperationsUseCanonicalPrefix"
        ] = False
        stale_naming_errors: list[str] = []
        check_catalog_shape(stale_naming, stale_naming_errors)
        if not any(
            "allProjectedOperationsUseCanonicalPrefix" in error
            for error in stale_naming_errors
        ):
            errors.append("self-test failed to catch stale operation naming evidence")
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
        counts = {"fixtures": 0, "operations": 0}
    else:
        errors, counts = check_repo(args.root.resolve(), update=args.update)
    if errors:
        for error in errors:
            print(f"error: {error}", file=sys.stderr)
        return 1
    if args.self_test:
        print("MLIR textual dialect projection self-test passed")
    elif args.update:
        print(
            f"Updated {CATALOG_PATH} "
            f"({counts['fixtures']} fixtures, {counts['operations']} ops)"
        )
    else:
        print(
            "MLIR textual dialect projection audit passed "
            f"({counts['fixtures']} fixtures, {counts['operations']} ops)"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
