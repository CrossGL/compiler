#!/usr/bin/env python3
"""Generate and validate the report-only MLIR dialect op/type catalog.

The catalog is derived from committed HIR fixture facts and the MLIR boundary
inventory. It intentionally does not import compiler modules, lower HIR, or
probe an installed MLIR toolchain.
"""

from __future__ import annotations

import argparse
import copy
import json
import sys
import tempfile
from pathlib import Path
from typing import Any


CATALOG_PATH = Path("experimental/mlir/op_type_catalog.v0.json")
BOUNDARY_PATH = Path("experimental/mlir/boundary_inventory.v0.json")
FIXTURE_PATH = Path("experimental/mlir/fixture_inventory.json")
MANIFEST_PATH = Path("experimental/mlir/experiment_manifest.json")

CATALOG_KIND = "crossgl-mlir-op-type-catalog-v0"
BOUNDARY_KIND = "crossgl-mlir-boundary-inventory-v0"
FIXTURE_KIND = "crossgl-mlir-experiment-fixture-inventory"
MANIFEST_KIND = "crossgl-mlir-experiment-manifest"
CATALOG_STATUS = "report-only-derived-from-hir-facts"
OP_STATUS = "boundary-inventory-only"
TYPE_STATUS = "hir-type-fact-only"
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
    "coverageSummary",
    "fixtureUniverse",
    "operations",
    "types",
    "blockedCoverage",
)
GENERATION_KEYS = (
    "deterministic",
    "derivedFrom",
    "optionalMlirToolingRequired",
    "productionLinked",
    "normalBuildRequired",
    "separatesPseudoMlir",
)
FIXTURE_UNIVERSE_KEYS = (
    "admittedFixtures",
    "operationFixtures",
    "fixturesMissingOperationCoverage",
    "operationFixturesOutsideInventory",
    "matches",
)
OPERATION_KEYS = (
    "operation",
    "coverageStatus",
    "emissionStatus",
    "role",
    "authorityAnchors",
    "allowedHirFamilies",
    "preserves",
    "requiredFixtureFacts",
    "fixtures",
    "fixtureCoverage",
)
TYPE_KEYS = (
    "typeFact",
    "coverageStatus",
    "sourceField",
    "fixtures",
)
FIXTURE_COVERAGE_KEYS = (
    "path",
    "experimentSlice",
    "loweringStatus",
    "matchedRequiredFacts",
    "missingRequiredFacts",
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


def fact_universe(coverage: dict[str, Any]) -> set[str]:
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


def load_inputs(root: Path) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    boundary = require_loaded_object(root / BOUNDARY_PATH, BOUNDARY_KIND)
    fixture = require_loaded_object(root / FIXTURE_PATH, FIXTURE_KIND)
    manifest = require_loaded_object(root / MANIFEST_PATH, MANIFEST_KIND)
    return boundary, fixture, manifest


def require_loaded_object(path: Path, kind: str) -> dict[str, Any]:
    value = load_json(path)
    if not isinstance(value, dict):
        raise ValueError(f"{path}: must be a JSON object")
    if value.get("kind") != kind:
        raise ValueError(f"{path}: kind must be {kind!r}")
    return value


def manifest_fixture_records(manifest: dict[str, Any]) -> dict[str, dict[str, Any]]:
    records: dict[str, dict[str, Any]] = {}
    for item in manifest.get("eligibleFixtures", []):
        if not isinstance(item, dict):
            continue
        path = item.get("path")
        coverage = item.get("boundaryFactCoverage")
        if isinstance(path, str) and isinstance(coverage, dict):
            records[path] = item
    return records


def fixture_inventory_paths(fixture_inventory: dict[str, Any]) -> list[str]:
    paths: list[str] = []
    for item in fixture_inventory.get("fixtures", []):
        if isinstance(item, dict) and isinstance(item.get("path"), str):
            paths.append(item["path"])
    return paths


def operation_fixture_paths(operations: list[dict[str, Any]]) -> list[str]:
    paths: list[str] = []
    for operation in operations:
        paths.extend(string_list(operation.get("fixtures")))
    return sorted_unique(paths)


def sorted_difference(left: list[str], right: list[str]) -> list[str]:
    return sorted(set(left) - set(right))


def derive_fixture_universe(
    fixture_paths: list[str], operations: list[dict[str, Any]]
) -> dict[str, Any]:
    admitted_fixtures = sorted_unique(fixture_paths)
    operation_fixtures = operation_fixture_paths(operations)
    missing_coverage = sorted_difference(admitted_fixtures, operation_fixtures)
    outside_inventory = sorted_difference(operation_fixtures, admitted_fixtures)
    return {
        "admittedFixtures": admitted_fixtures,
        "operationFixtures": operation_fixtures,
        "fixturesMissingOperationCoverage": missing_coverage,
        "operationFixturesOutsideInventory": outside_inventory,
        "matches": not missing_coverage and not outside_inventory,
    }


def derive_operation_catalog(
    boundary: dict[str, Any], manifest_records: dict[str, dict[str, Any]]
) -> list[dict[str, Any]]:
    operations: list[dict[str, Any]] = []
    for item in boundary.get("operations", []):
        if not isinstance(item, dict):
            continue
        required_facts = string_list(item.get("requiredFixtureFacts"))
        fixture_paths = string_list(item.get("fixtures"))
        fixture_coverage = []
        for fixture_path in fixture_paths:
            record = manifest_records.get(fixture_path, {})
            coverage = record.get("boundaryFactCoverage")
            universe = fact_universe(coverage if isinstance(coverage, dict) else {})
            matched = [fact for fact in required_facts if fact in universe]
            missing = [fact for fact in required_facts if fact not in universe]
            fixture_coverage.append(
                {
                    "path": fixture_path,
                    "experimentSlice": record.get("experimentSlice"),
                    "loweringStatus": record.get("loweringStatus"),
                    "matchedRequiredFacts": matched,
                    "missingRequiredFacts": missing,
                }
            )
        operations.append(
            {
                "operation": item.get("operation"),
                "coverageStatus": OP_STATUS,
                "emissionStatus": item.get("emissionStatus"),
                "role": item.get("role"),
                "authorityAnchors": string_list(item.get("authorityAnchors")),
                "allowedHirFamilies": string_list(item.get("allowedHirFamilies")),
                "preserves": string_list(item.get("preserves")),
                "requiredFixtureFacts": required_facts,
                "fixtures": fixture_paths,
                "fixtureCoverage": fixture_coverage,
            }
        )
    return operations


def derive_type_catalog(
    manifest_records: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    fixture_by_type: dict[str, list[str]] = {}
    for fixture_path, record in manifest_records.items():
        coverage = record.get("boundaryFactCoverage")
        if not isinstance(coverage, dict):
            continue
        for type_fact in string_list(coverage.get("targetIndependentTypeFacts")):
            fixture_by_type.setdefault(type_fact, []).append(fixture_path)
    return [
        {
            "typeFact": type_fact,
            "coverageStatus": TYPE_STATUS,
            "sourceField": "eligibleFixtures[].boundaryFactCoverage.targetIndependentTypeFacts",
            "fixtures": sorted_unique(paths),
        }
        for type_fact, paths in sorted(fixture_by_type.items())
    ]


def derive_catalog(root: Path) -> dict[str, Any]:
    boundary, fixture_inventory, manifest = load_inputs(root)
    source_authority = boundary.get("sourceAuthority")
    if not isinstance(source_authority, dict):
        source_authority = {}
    manifest_records = manifest_fixture_records(manifest)
    fixture_paths = sorted_unique(fixture_inventory_paths(fixture_inventory))
    operations = derive_operation_catalog(boundary, manifest_records)
    types = derive_type_catalog(manifest_records)
    fixture_universe = derive_fixture_universe(fixture_paths, operations)
    blocked = manifest.get("ineligibleFixtureFamilies")
    if not isinstance(blocked, list):
        blocked = []
    return {
        "schemaVersion": 1,
        "kind": CATALOG_KIND,
        "status": CATALOG_STATUS,
        "scope": "experimental CrossGL MLIR HIR dialect operation and type fact coverage",
        "generation": {
            "deterministic": True,
            "derivedFrom": list(DERIVED_FROM),
            "optionalMlirToolingRequired": False,
            "productionLinked": False,
            "normalBuildRequired": False,
            "separatesPseudoMlir": True,
        },
        "dialect": {
            "canonicalNamespace": source_authority.get("hirNamespace", "hir"),
            "operationPrefix": source_authority.get("operationPrefix", "hir."),
            "authorityAnchors": string_list(source_authority.get("authorityAnchors")),
        },
        "coverageSummary": {
            "operationCount": len(operations),
            "typeFactCount": len(types),
            "fixtureCount": len(fixture_paths),
            "fixtures": fixture_paths,
        },
        "fixtureUniverse": fixture_universe,
        "operations": operations,
        "types": types,
        "blockedCoverage": blocked,
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
    expected_generation_flags = {
        "deterministic": True,
        "optionalMlirToolingRequired": False,
        "productionLinked": False,
        "normalBuildRequired": False,
        "separatesPseudoMlir": True,
    }
    for flag, expected in expected_generation_flags.items():
        if generation.get(flag) is not expected:
            errors.append(f"{CATALOG_PATH}: generation.{flag} must be {expected}")
    if generation.get("derivedFrom") != list(DERIVED_FROM):
        errors.append(f"{CATALOG_PATH}: generation.derivedFrom is stale")

    summary = require_object(catalog.get("coverageSummary"), "coverageSummary", errors)
    summary_fixtures = string_list(summary.get("fixtures"))

    fixture_universe = require_object(
        catalog.get("fixtureUniverse"), "fixtureUniverse", errors
    )
    if tuple(fixture_universe) != FIXTURE_UNIVERSE_KEYS:
        errors.append(f"{CATALOG_PATH}: fixtureUniverse schema changed")
    for field in (
        "admittedFixtures",
        "operationFixtures",
        "fixturesMissingOperationCoverage",
        "operationFixturesOutsideInventory",
    ):
        values = string_list(fixture_universe.get(field))
        if values != sorted_unique(values):
            errors.append(
                f"{CATALOG_PATH}: fixtureUniverse.{field} must be sorted unique"
            )
    if fixture_universe.get("admittedFixtures") != summary_fixtures:
        errors.append(
            f"{CATALOG_PATH}: fixtureUniverse.admittedFixtures must match "
            "coverageSummary.fixtures"
        )
    if fixture_universe.get("fixturesMissingOperationCoverage") != []:
        errors.append(
            f"{CATALOG_PATH}: every admitted fixture must have at least one "
            "operation coverage row"
        )
    if fixture_universe.get("operationFixturesOutsideInventory") != []:
        errors.append(
            f"{CATALOG_PATH}: operation fixture coverage must not reference "
            "fixtures outside fixture_inventory.json"
        )
    expected_matches = (
        fixture_universe.get("fixturesMissingOperationCoverage") == []
        and fixture_universe.get("operationFixturesOutsideInventory") == []
    )
    if fixture_universe.get("matches") is not expected_matches:
        errors.append(f"{CATALOG_PATH}: fixtureUniverse.matches is inconsistent")

    operations = require_list(catalog.get("operations"), "operations", errors)
    operation_names: list[str] = []
    referenced_fixtures: list[str] = []
    for index, item in enumerate(operations):
        record = require_object(item, f"operations[{index}]", errors)
        if tuple(record) != OPERATION_KEYS:
            errors.append(f"{CATALOG_PATH}: operations[{index}] schema changed")
        operation = record.get("operation")
        if not isinstance(operation, str) or not operation.startswith("hir."):
            errors.append(f"{CATALOG_PATH}: operations[{index}].operation invalid")
        else:
            operation_names.append(operation)
        referenced_fixtures.extend(string_list(record.get("fixtures")))
        fixtures = string_list(record.get("fixtures"))
        if len(fixtures) != len(set(fixtures)):
            errors.append(f"{CATALOG_PATH}: operations[{index}].fixtures duplicate")
        required_facts = string_list(record.get("requiredFixtureFacts"))
        coverage_paths: list[str] = []
        if record.get("coverageStatus") != OP_STATUS:
            errors.append(f"{CATALOG_PATH}: operations[{index}].coverageStatus invalid")
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
                    f"{CATALOG_PATH}: operations[{index}].fixtureCoverage"
                    f"[{coverage_index}] schema changed"
                )
            coverage_path = coverage_record.get("path")
            if isinstance(coverage_path, str):
                coverage_paths.append(coverage_path)
            else:
                errors.append(
                    f"{CATALOG_PATH}: operations[{index}].fixtureCoverage"
                    f"[{coverage_index}].path invalid"
                )
            matched = string_list(coverage_record.get("matchedRequiredFacts"))
            missing = string_list(coverage_record.get("missingRequiredFacts"))
            if missing != []:
                errors.append(
                    f"{CATALOG_PATH}: operations[{index}].fixtureCoverage"
                    f"[{coverage_index}].missingRequiredFacts must be empty"
                )
            if matched != required_facts:
                errors.append(
                    f"{CATALOG_PATH}: operations[{index}].fixtureCoverage"
                    f"[{coverage_index}].matchedRequiredFacts must match "
                    "requiredFixtureFacts"
                )
        if coverage_paths != fixtures:
            errors.append(
                f"{CATALOG_PATH}: operations[{index}].fixtureCoverage paths must "
                "match operations[].fixtures"
            )
    if len(operation_names) != len(set(operation_names)):
        errors.append(f"{CATALOG_PATH}: operations must be unique")
    if fixture_universe and fixture_universe.get("operationFixtures") != sorted_unique(
        referenced_fixtures
    ):
        errors.append(
            f"{CATALOG_PATH}: fixtureUniverse.operationFixtures must match "
            "operations[].fixtures"
        )

    types = require_list(catalog.get("types"), "types", errors)
    type_names: list[str] = []
    for index, item in enumerate(types):
        record = require_object(item, f"types[{index}]", errors)
        if tuple(record) != TYPE_KEYS:
            errors.append(f"{CATALOG_PATH}: types[{index}] schema changed")
        type_fact = record.get("typeFact")
        if not isinstance(type_fact, str) or not type_fact:
            errors.append(f"{CATALOG_PATH}: types[{index}].typeFact invalid")
        else:
            type_names.append(type_fact)
        if record.get("coverageStatus") != TYPE_STATUS:
            errors.append(f"{CATALOG_PATH}: types[{index}].coverageStatus invalid")
        fixtures = string_list(record.get("fixtures"))
        if fixtures != sorted_unique(fixtures):
            errors.append(
                f"{CATALOG_PATH}: types[{index}].fixtures must be sorted unique"
            )
    if type_names != sorted_unique(type_names):
        errors.append(f"{CATALOG_PATH}: types must be sorted unique by typeFact")


def check_repo(root: Path, *, update: bool = False) -> tuple[list[str], dict[str, int]]:
    errors: list[str] = []
    try:
        derived = derive_catalog(root)
    except (OSError, ValueError) as error:
        return [str(error)], {"operations": 0, "types": 0}

    if update:
        write_json(root / CATALOG_PATH, derived)
    else:
        try:
            actual = load_json(root / CATALOG_PATH)
        except (OSError, ValueError) as error:
            return [f"{CATALOG_PATH}: {error}"], {"operations": 0, "types": 0}
        if actual != derived:
            errors.append(
                f"{CATALOG_PATH}: stale; regenerate with "
                "tools/check_mlir_op_type_catalog.py --update"
            )
        if isinstance(actual, dict):
            check_catalog_shape(actual, errors)
        else:
            errors.append(f"{CATALOG_PATH}: catalog must be an object")

    return errors, {
        "operations": len(derived["operations"]),
        "types": len(derived["types"]),
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
                "authorityAnchors": ["include/crossgl/HIR/HIR.h"],
            },
            "operations": [
                {
                    "operation": "hir.entry_point",
                    "emissionStatus": "boundary-inventory-only",
                    "role": "test op",
                    "authorityAnchors": ["include/crossgl/HIR/HIR.h"],
                    "allowedHirFamilies": ["module_stages_and_entry_points"],
                    "fixtures": ["tests/fixtures/Test.cgl"],
                    "preserves": ["typed_hir_facts"],
                    "requiredFixtureFacts": [
                        "entry_point",
                        "typeFacts.void_entry_point",
                    ],
                }
            ],
        }
        fixture = {
            "kind": FIXTURE_KIND,
            "fixtures": [{"path": "tests/fixtures/Test.cgl"}],
        }
        manifest = {
            "kind": MANIFEST_KIND,
            "eligibleFixtures": [
                {
                    "path": "tests/fixtures/Test.cgl",
                    "experimentSlice": "test",
                    "loweringStatus": "eligible-report-only",
                    "boundaryFactCoverage": {
                        "sourceLocationFacts": ["entry_point"],
                        "targetIndependentTypeFacts": ["void_entry_point"],
                    },
                }
            ],
            "ineligibleFixtureFamilies": [],
        }
        write_json(root / BOUNDARY_PATH, boundary)
        write_json(root / FIXTURE_PATH, fixture)
        write_json(root / MANIFEST_PATH, manifest)
        generated = derive_catalog(root)
        check_catalog_shape(generated, errors)
        missing_pseudo_mlir_boundary = copy.deepcopy(generated)
        del missing_pseudo_mlir_boundary["generation"]["separatesPseudoMlir"]
        missing_pseudo_mlir_boundary_errors: list[str] = []
        check_catalog_shape(
            missing_pseudo_mlir_boundary, missing_pseudo_mlir_boundary_errors
        )
        if not any(
            "generation schema changed" in error
            for error in missing_pseudo_mlir_boundary_errors
        ):
            errors.append(
                "self-test failed to catch missing pseudo-MLIR separation flag"
            )
        wrong_pseudo_mlir_boundary = copy.deepcopy(generated)
        wrong_pseudo_mlir_boundary["generation"]["separatesPseudoMlir"] = False
        wrong_pseudo_mlir_boundary_errors: list[str] = []
        check_catalog_shape(
            wrong_pseudo_mlir_boundary, wrong_pseudo_mlir_boundary_errors
        )
        if not any(
            "generation.separatesPseudoMlir must be True" in error
            for error in wrong_pseudo_mlir_boundary_errors
        ):
            errors.append(
                "self-test failed to catch disabled pseudo-MLIR separation flag"
            )
        missing_coverage = copy.deepcopy(generated)
        missing_coverage["fixtureUniverse"]["fixturesMissingOperationCoverage"] = [
            "tests/fixtures/Test.cgl"
        ]
        missing_coverage["fixtureUniverse"]["matches"] = False
        missing_coverage_errors: list[str] = []
        check_catalog_shape(missing_coverage, missing_coverage_errors)
        if not any(
            "every admitted fixture must have at least one operation coverage row"
            in error
            for error in missing_coverage_errors
        ):
            errors.append(
                "self-test failed to catch missing operation fixture coverage"
            )
        outside_inventory = copy.deepcopy(generated)
        outside_inventory["fixtureUniverse"]["operationFixturesOutsideInventory"] = [
            "tests/fixtures/Unexpected.cgl"
        ]
        outside_inventory["fixtureUniverse"]["matches"] = False
        outside_inventory_errors: list[str] = []
        check_catalog_shape(outside_inventory, outside_inventory_errors)
        if not any(
            "operation fixture coverage must not reference fixtures outside" in error
            for error in outside_inventory_errors
        ):
            errors.append(
                "self-test failed to catch outside-inventory fixture coverage"
            )
        stale = copy.deepcopy(generated)
        stale["types"][0]["fixtures"] = ["z", "a"]
        stale_errors: list[str] = []
        check_catalog_shape(stale, stale_errors)
        if not any("fixtures must be sorted unique" in error for error in stale_errors):
            errors.append("self-test failed to catch unsorted type fixture coverage")

        stale_matched_facts = copy.deepcopy(generated)
        stale_matched_facts["operations"][0]["fixtureCoverage"][0][
            "matchedRequiredFacts"
        ] = ["entry_point"]
        stale_matched_facts_errors: list[str] = []
        check_catalog_shape(stale_matched_facts, stale_matched_facts_errors)
        if not any(
            "matchedRequiredFacts must match requiredFixtureFacts" in error
            for error in stale_matched_facts_errors
        ):
            errors.append(
                "self-test failed to catch stale operation matched fact coverage"
            )

        stale_coverage_path = copy.deepcopy(generated)
        stale_coverage_path["operations"][0]["fixtureCoverage"][0]["path"] = (
            "tests/fixtures/Unexpected.cgl"
        )
        stale_coverage_path_errors: list[str] = []
        check_catalog_shape(stale_coverage_path, stale_coverage_path_errors)
        if not any(
            "fixtureCoverage paths must match operations[].fixtures" in error
            for error in stale_coverage_path_errors
        ):
            errors.append(
                "self-test failed to catch operation fixture coverage path drift"
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
        counts = {"operations": 0, "types": 0}
    else:
        errors, counts = check_repo(args.root.resolve(), update=args.update)
    if errors:
        for error in errors:
            print(f"error: {error}", file=sys.stderr)
        return 1
    if args.self_test:
        print("MLIR op/type catalog self-test passed")
    elif args.update:
        print(
            f"Updated {CATALOG_PATH} "
            f"({counts['operations']} ops, {counts['types']} type facts)"
        )
    else:
        print(
            "MLIR op/type catalog audit passed "
            f"({counts['operations']} ops, {counts['types']} type facts)"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
