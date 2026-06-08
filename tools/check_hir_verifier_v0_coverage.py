#!/usr/bin/env python3
"""Validate the native-v0 HIR verifier coverage manifest."""

from __future__ import annotations

import argparse
import copy
import json
import re
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from check_support_matrix_evidence import (
    SUPPORT_MATRIX_PATH,
    UNIT_TEST_FUNCTION_ALIASES,
    declared_optional_native_evidence_names,
    format_locations,
    line_locations,
    load_ctest_inventory,
    parse_evidence_references,
    split_missing_ctest_references,
    validate_unit_test_aliases,
)


SCHEMA_VERSION = "crossgl-hir-verifier-v0-coverage-v2"
REPORT_SCHEMA_VERSION = "crossgl-hir-verifier-v0-coverage-report-v2"
DEFAULT_MANIFEST = Path("tests/conformance/hir-verifier-v0-coverage.json")
DEFAULT_CONFORMANCE_MANIFEST = Path("tests/conformance/manifest.v0.json")
HIR_HEADER_PATH = Path("include/crossgl/HIR/HIR.h")
REQUIRED_FAMILIES = (
    "arrays",
    "atomics",
    "compute-basics",
    "constants",
    "control-flow",
    "invalid-shape-diagnostics",
    "resources",
    "stage-coverage",
    "storage-buffers",
    "storage-images",
    "textures-samplers",
    "type-semantics",
)
COVERAGE_CATEGORY_FIELD = "coverage_categories"
DIAGNOSTIC_COVERAGE_CATEGORY_PREFIX = "diagnostic:"
HIR_COVERAGE_ENUMS = (
    "HIRExpressionKind",
    "HIRResourceKind",
    "HIRStatementKind",
)
REQUIRED_COVERAGE_CATEGORIES = (
    "HIRExpressionKind::Binary",
    "HIRExpressionKind::Call",
    "HIRExpressionKind::Constructor",
    "HIRExpressionKind::IndexAccess",
    "HIRExpressionKind::MemberAccess",
    "HIRExpressionKind::NonUniform",
    "HIRExpressionKind::TextureCompare",
    "HIRExpressionKind::TextureCompareLodManual",
    "HIRExpressionKind::TextureSample",
    "HIRResourceKind::Buffer",
    "HIRResourceKind::Sampler",
    "HIRResourceKind::Shared",
    "HIRResourceKind::StorageImage",
    "HIRResourceKind::Texture",
    "HIRResourceKind::Uniform",
    "HIRStatementKind::Assignment",
    "HIRStatementKind::Block",
    "HIRStatementKind::Break",
    "HIRStatementKind::Continue",
    "HIRStatementKind::Declaration",
    "HIRStatementKind::Discard",
    "HIRStatementKind::Expression",
    "HIRStatementKind::For",
    "HIRStatementKind::If",
    "HIRStatementKind::Return",
    "diagnostic:opengl.unsupported-function-parameter-array-write",
    "diagnostic:opt.hir-duplicate-resource",
    "diagnostic:opt.hir-duplicate-resource-binding",
    "diagnostic:opt.hir-expression-shape",
    "diagnostic:opt.hir-matrix-constructor",
    "diagnostic:opt.hir-missing-entry-point",
    "diagnostic:opt.hir-resource-shape",
    "diagnostic:opt.hir-runtime-resource-array-shape",
    "diagnostic:opt.hir-scalar-constructor",
    "diagnostic:opt.hir-statement-shape",
    "diagnostic:opt.hir-storage-image-runtime-descriptor-array",
    "diagnostic:opt.hir-vector-constructor",
    "diagnostic:sema.storage-image-atomic",
)
ALLOWED_NON_HIR_COVERAGE_CATEGORIES = frozenset(
    category for category in REQUIRED_COVERAGE_CATEGORIES if "::" not in category
)
ALLOWED_STATUSES = {"planned", "supported"}
ALLOWED_KINDS = {"diagnostic", "planned-failure", "support-matrix"}
DIAGNOSTIC_KINDS = {"diagnostic", "planned-failure"}
DIAGNOSTIC_ONLY_SUPPORTED_FAMILIES = {"invalid-shape-diagnostics"}
EVIDENCE_NAME_RE = re.compile(r"^(?:cglc_[A-Za-z0-9_-]+|test[A-Z][A-Za-z0-9_]*)$")
REJECTION_EVIDENCE_MARKERS = ("_failure", "_planned_failure", "_unavailable")
SUPPORTED_CONFORMANCE_STATUS = "accepted"
GRAPHICS_STAGES_FEATURE_GROUP = "graphics-stages"
PACKAGE_BACKED_COMMAND_PROFILES = frozenset(
    {
        "native-package-build",
        "source-package-build",
    }
)


@dataclass(frozen=True)
class ManifestCoverageReport:
    evidence_names: set[str]
    evidence_names_by_kind: dict[str, set[str]]
    coverage_categories: set[str]
    coverage_categories_by_evidence_name: dict[str, set[str]]
    families: list[dict[str, Any]]
    coverage_counts: dict[str, int]
    conformance_feature_groups: set[str]


@dataclass(frozen=True)
class ConformanceEntry:
    entry_id: str
    feature_group: str
    status: str
    command_profile: str | None
    fixture: str


@dataclass(frozen=True)
class ConformanceCoverageReport:
    manifest_path: Path
    required_statuses_by_group: dict[str, set[str]]
    accepted_feature_groups: set[str]
    entries_by_id: dict[str, ConformanceEntry]


def load_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"{path}: invalid JSON: {exc}") from exc
    if not isinstance(payload, dict):
        raise ValueError(f"{path}: manifest must be a JSON object")
    return payload


def require_string(obj: dict[str, Any], field: str, context: str) -> str:
    value = obj.get(field)
    if not isinstance(value, str) or not value:
        raise ValueError(f"{context}: {field!r} must be a non-empty string")
    return value


def require_sorted_string_list(
    obj: dict[str, Any], field: str, context: str
) -> list[str]:
    value = obj.get(field)
    if not isinstance(value, list) or not value:
        raise ValueError(f"{context}: {field!r} must be a non-empty array")

    result: list[str] = []
    for index, item in enumerate(value):
        if not isinstance(item, str) or not item:
            raise ValueError(f"{context}: {field}[{index}] must be a non-empty string")
        result.append(item)

    if len(result) != len(set(result)):
        raise ValueError(f"{context}: {field!r} contains duplicate values")
    if result != sorted(result):
        raise ValueError(f"{context}: {field!r} must be sorted")
    return result


def validate_repo_fixture(root: Path, fixture: str, context: str) -> None:
    fixture_path = Path(fixture)
    if fixture_path.is_absolute() or ".." in fixture_path.parts:
        raise ValueError(f"{context}: fixture must be a repository-relative path")
    if fixture_path.suffix != ".cgl":
        raise ValueError(f"{context}: fixture must use the .cgl extension")
    if not (root / fixture_path).is_file():
        raise ValueError(f"{context}: fixture does not exist: {fixture}")


def strip_cpp_comments(text: str) -> str:
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.DOTALL)
    return re.sub(r"//.*", "", text)


def parse_hir_enum_entries(header_path: Path) -> dict[str, set[str]]:
    if not header_path.is_file():
        raise ValueError(f"HIR header is missing: {header_path}")

    text = strip_cpp_comments(header_path.read_text(encoding="utf-8"))
    entries_by_enum: dict[str, set[str]] = {}
    for enum_name in HIR_COVERAGE_ENUMS:
        match = re.search(
            rf"\benum\s+class\s+{enum_name}\s*\{{(?P<body>.*?)\}}",
            text,
            re.DOTALL,
        )
        if match is None:
            raise ValueError(f"{header_path}: missing enum class {enum_name}")

        entries: set[str] = set()
        for raw_entry in match.group("body").split(","):
            entry = raw_entry.split("=", 1)[0].strip()
            if not entry:
                continue
            if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", entry):
                raise ValueError(
                    f"{header_path}: could not parse {enum_name} entry {raw_entry!r}"
                )
            entries.add(entry)

        if not entries:
            raise ValueError(f"{header_path}: enum class {enum_name} has no entries")
        entries_by_enum[enum_name] = entries

    return entries_by_enum


def hir_coverage_categories(root: Path) -> set[str]:
    enum_entries = parse_hir_enum_entries(root / HIR_HEADER_PATH)
    return {
        f"{enum_name}::{entry}"
        for enum_name, entries in enum_entries.items()
        for entry in entries
    }


def allowed_coverage_categories(root: Path) -> set[str]:
    return hir_coverage_categories(root) | set(ALLOWED_NON_HIR_COVERAGE_CATEGORIES)


def describe_unknown_coverage_category(
    category: str, allowed_categories: set[str]
) -> str:
    family, separator, name = category.partition("::")
    if separator and family in HIR_COVERAGE_ENUMS:
        allowed_for_family = sorted(
            candidate.removeprefix(f"{family}::")
            for candidate in allowed_categories
            if candidate.startswith(f"{family}::")
        )
        return (
            f"unknown HIR coverage category {category!r}: {family} has no enum "
            f"entry {name!r} in {HIR_HEADER_PATH}; expected one of "
            f"{allowed_for_family}"
        )
    if separator and family.startswith("HIR"):
        return (
            f"unknown HIR coverage category family {family!r} in {category!r}; "
            f"expected one of {sorted(HIR_COVERAGE_ENUMS)}"
        )
    return (
        f"unknown coverage category {category!r}; expected one of "
        f"{sorted(allowed_categories)}"
    )


def optional_sorted_coverage_categories(
    obj: dict[str, Any], context: str, allowed_categories: set[str]
) -> list[str]:
    value = obj.get(COVERAGE_CATEGORY_FIELD)
    if value is None:
        return []
    if not isinstance(value, list) or not value:
        raise ValueError(
            f"{context}: {COVERAGE_CATEGORY_FIELD!r} must be a non-empty array "
            "when present"
        )

    categories: list[str] = []
    for index, item in enumerate(value):
        if not isinstance(item, str) or not item:
            raise ValueError(
                f"{context}: {COVERAGE_CATEGORY_FIELD}[{index}] must be a "
                "non-empty string"
            )
        if item not in allowed_categories:
            raise ValueError(
                f"{context}: "
                f"{describe_unknown_coverage_category(item, allowed_categories)}"
            )
        categories.append(item)

    if len(categories) != len(set(categories)):
        raise ValueError(
            f"{context}: {COVERAGE_CATEGORY_FIELD!r} contains duplicate values"
        )
    if categories != sorted(categories):
        raise ValueError(f"{context}: {COVERAGE_CATEGORY_FIELD!r} must be sorted")
    return categories


def load_conformance_coverage(
    root: Path, conformance_path: Path
) -> ConformanceCoverageReport:
    if not conformance_path.exists():
        raise ValueError(f"conformance manifest is missing: {conformance_path}")

    payload = load_json(conformance_path)
    contract = payload.get("coverage_contract")
    if not isinstance(contract, dict):
        raise ValueError(f"{conformance_path}: coverage_contract must be a JSON object")

    required_statuses = contract.get("required_feature_statuses")
    if not isinstance(required_statuses, list) or not required_statuses:
        raise ValueError(
            f"{conformance_path}: coverage_contract.required_feature_statuses "
            "must be a non-empty array"
        )

    required_statuses_by_group: dict[str, set[str]] = {}
    for index, requirement in enumerate(required_statuses):
        context = (
            f"{conformance_path}: coverage_contract.required_feature_statuses[{index}]"
        )
        if not isinstance(requirement, dict):
            raise ValueError(f"{context}: requirement must be a JSON object")
        feature_group = require_string(requirement, "feature_group", context)
        status = require_string(requirement, "status", context)
        required_statuses_by_group.setdefault(feature_group, set()).add(status)

    accepted_feature_groups = {
        feature_group
        for feature_group, statuses in required_statuses_by_group.items()
        if SUPPORTED_CONFORMANCE_STATUS in statuses
    }

    entries = payload.get("entries")
    if not isinstance(entries, list) or not entries:
        raise ValueError(f"{conformance_path}: entries must be a non-empty array")

    entries_by_id: dict[str, ConformanceEntry] = {}
    for index, entry in enumerate(entries):
        context = f"{conformance_path}: entries[{index}]"
        if not isinstance(entry, dict):
            raise ValueError(f"{context}: entry must be a JSON object")
        entry_id = require_string(entry, "id", context)
        if entry_id in entries_by_id:
            raise ValueError(f"{context}: duplicate conformance entry id {entry_id!r}")
        feature_group = require_string(entry, "feature_group", context)
        status = require_string(entry, "status", context)
        command_profile_value = entry.get("command_profile")
        if command_profile_value is not None and (
            not isinstance(command_profile_value, str) or not command_profile_value
        ):
            raise ValueError(
                f"{context}: 'command_profile' must be a non-empty string when present"
            )
        fixture = require_string(entry, "fixture", context)
        validate_repo_fixture(root, fixture, context)
        entries_by_id[entry_id] = ConformanceEntry(
            entry_id=entry_id,
            feature_group=feature_group,
            status=status,
            command_profile=command_profile_value,
            fixture=fixture,
        )

    return ConformanceCoverageReport(
        manifest_path=conformance_path,
        required_statuses_by_group=dict(sorted(required_statuses_by_group.items())),
        accepted_feature_groups=accepted_feature_groups,
        entries_by_id=dict(sorted(entries_by_id.items())),
    )


def validate_coverage_entry(
    entry: dict[str, Any],
    context: str,
    support_matrix_names: set[str],
    allowed_categories: set[str],
) -> tuple[str, list[str]]:
    kind = require_string(entry, "kind", context)
    if kind not in ALLOWED_KINDS:
        raise ValueError(
            f"{context}: unsupported coverage kind {kind!r}; "
            f"expected one of {sorted(ALLOWED_KINDS)}"
        )

    name = require_string(entry, "name", context)
    if not EVIDENCE_NAME_RE.match(name):
        raise ValueError(f"{context}: invalid evidence name {name!r}")
    if name not in support_matrix_names:
        raise ValueError(
            f"{context}: evidence {name!r} is not cited in {SUPPORT_MATRIX_PATH}"
        )
    if kind == "support-matrix" and any(
        marker in name for marker in REJECTION_EVIDENCE_MARKERS
    ):
        raise ValueError(
            f"{context}: support-matrix entries must cite passing evidence; "
            f"{name!r} looks like rejection or unavailable evidence"
        )

    require_string(entry, "requirement", context)

    diagnostic_code = entry.get("diagnostic_code")
    if kind in DIAGNOSTIC_KINDS:
        if not isinstance(diagnostic_code, str) or not diagnostic_code:
            raise ValueError(
                f"{context}: {kind!r} entries require a non-empty diagnostic_code"
            )
    elif diagnostic_code is not None:
        raise ValueError(
            f"{context}: diagnostic_code is only allowed on diagnostic entries"
        )

    if kind == "planned-failure" and "planned_failure" not in name:
        raise ValueError(
            f"{context}: planned-failure evidence must name a planned_failure CTest"
        )

    coverage_categories = optional_sorted_coverage_categories(
        entry, context, allowed_categories
    )
    diagnostic_categories = [
        category
        for category in coverage_categories
        if category.startswith(DIAGNOSTIC_COVERAGE_CATEGORY_PREFIX)
    ]
    if kind in DIAGNOSTIC_KINDS:
        expected_diagnostic_category = (
            f"{DIAGNOSTIC_COVERAGE_CATEGORY_PREFIX}{diagnostic_code}"
        )
        stale_diagnostic_categories = [
            category
            for category in diagnostic_categories
            if category != expected_diagnostic_category
        ]
        if stale_diagnostic_categories:
            raise ValueError(
                f"{context}: diagnostic coverage category must match "
                f"diagnostic_code {diagnostic_code!r}; got "
                f"{stale_diagnostic_categories}"
            )
    elif diagnostic_categories:
        raise ValueError(
            f"{context}: diagnostic coverage categories are only allowed on "
            "diagnostic or planned-failure entries"
        )

    return name, coverage_categories


def empty_coverage_counts() -> dict[str, int]:
    return {kind: 0 for kind in sorted(ALLOWED_KINDS)}


def coverage_counts_report(counts: dict[str, int]) -> dict[str, int]:
    report = {kind: counts.get(kind, 0) for kind in sorted(ALLOWED_KINDS)}
    report["diagnostic-or-planned-failure"] = sum(
        counts.get(kind, 0) for kind in DIAGNOSTIC_KINDS
    )
    return report


def family_evidence_counts_report(
    family_reports: list[dict[str, Any]],
) -> dict[str, dict[str, int]]:
    return {
        family["id"]: {
            "coverage_entry_count": len(family["evidence_names"]),
            "unique_evidence_name_count": len(set(family["evidence_names"])),
            **family["coverage_counts"],
        }
        for family in family_reports
    }


def validate_family_conformance_linkage(
    family_context: str,
    family_id: str,
    family_status: str,
    conformance_feature_groups: list[str],
    conformance_entries: list[str],
    conformance_report: ConformanceCoverageReport,
) -> list[ConformanceEntry]:
    linked_entries: list[ConformanceEntry] = []
    known_feature_groups = set(conformance_report.required_statuses_by_group)
    for group_index, feature_group in enumerate(conformance_feature_groups):
        if feature_group not in known_feature_groups:
            raise ValueError(
                f"{family_context}: conformance_feature_groups[{group_index}] "
                f"unknown feature_group {feature_group!r}; expected one of "
                f"{sorted(known_feature_groups)} from "
                f"{conformance_report.manifest_path}"
            )
        if (
            feature_group in conformance_report.accepted_feature_groups
            and family_status != "supported"
        ):
            raise ValueError(
                f"{family_context}: v0-supported conformance feature_group "
                f"{feature_group!r} must link to a supported HIR family, got "
                f"status {family_status!r}"
            )

    for entry_index, entry_id in enumerate(conformance_entries):
        entry = conformance_report.entries_by_id.get(entry_id)
        if entry is None:
            raise ValueError(
                f"{family_context}: conformance_entries[{entry_index}] unknown "
                f"conformance entry id {entry_id!r} in "
                f"{conformance_report.manifest_path}"
            )
        if entry.feature_group not in conformance_feature_groups:
            raise ValueError(
                f"{family_context}: conformance entry {entry_id!r} belongs to "
                f"feature_group {entry.feature_group!r}, which is not listed in "
                "conformance_feature_groups"
            )
        linked_entries.append(entry)

    linked_required_pairs = {
        (entry.feature_group, entry.status) for entry in linked_entries
    }
    for feature_group in conformance_feature_groups:
        required_statuses = conformance_report.required_statuses_by_group[feature_group]
        if not any(
            (feature_group, status) in linked_required_pairs
            for status in required_statuses
        ):
            raise ValueError(
                f"{family_context}: feature_group {feature_group!r} needs at "
                f"least one linked conformance entry with required status "
                f"{sorted(required_statuses)}"
            )

    if (
        family_status == "supported"
        and family_id not in DIAGNOSTIC_ONLY_SUPPORTED_FAMILIES
        and not any(
            entry.status == SUPPORTED_CONFORMANCE_STATUS for entry in linked_entries
        )
    ):
        raise ValueError(
            f"{family_context}: supported HIR family must link to at least one "
            f"{SUPPORTED_CONFORMANCE_STATUS!r} conformance entry"
        )

    return linked_entries


def required_graphics_stage_package_entry_ids(
    conformance_report: ConformanceCoverageReport,
) -> list[str]:
    return sorted(
        entry.entry_id
        for entry in conformance_report.entries_by_id.values()
        if entry.feature_group == GRAPHICS_STAGES_FEATURE_GROUP
        and entry.status == SUPPORTED_CONFORMANCE_STATUS
        and entry.command_profile in PACKAGE_BACKED_COMMAND_PROFILES
    )


def conformance_feature_group_summary_report(
    family_reports: list[dict[str, Any]],
    conformance_report: ConformanceCoverageReport,
) -> dict[str, Any]:
    accepted = conformance_report.accepted_feature_groups
    groups_by_family = {
        family["id"]: family["conformance_feature_groups"] for family in family_reports
    }
    families_by_group: dict[str, list[str]] = {}
    for family in family_reports:
        for feature_group in family["conformance_feature_groups"]:
            families_by_group.setdefault(feature_group, []).append(family["id"])

    covered_supported_groups = {
        feature_group
        for feature_group in accepted
        if feature_group in families_by_group
    }
    return {
        "complete": accepted == covered_supported_groups,
        "required_supported_feature_groups": sorted(accepted),
        "covered_supported_feature_groups": sorted(covered_supported_groups),
        "missing_supported_feature_groups": sorted(accepted - covered_supported_groups),
        "feature_groups_by_hir_family": groups_by_family,
        "hir_families_by_feature_group": {
            feature_group: sorted(families)
            for feature_group, families in sorted(families_by_group.items())
        },
    }


def required_family_summary_report(
    family_reports: list[dict[str, Any]],
) -> dict[str, Any]:
    family_ids = [family["id"] for family in family_reports]
    required = set(REQUIRED_FAMILIES)
    actual = set(family_ids)
    family_counts = family_evidence_counts_report(family_reports)
    families_with_diagnostic_evidence = sorted(
        family_id
        for family_id, counts in family_counts.items()
        if counts["diagnostic-or-planned-failure"] > 0
    )
    return {
        "complete": required == actual,
        "required_family_ids": sorted(REQUIRED_FAMILIES),
        "covered_family_ids": sorted(actual & required),
        "missing_family_ids": sorted(required - actual),
        "unknown_family_ids": sorted(actual - required),
        "covered_required_family_count": len(actual & required),
        "required_family_count": len(REQUIRED_FAMILIES),
        "families_with_diagnostic_or_planned_failure": (
            families_with_diagnostic_evidence
        ),
        "family_evidence_counts": family_counts,
    }


def required_coverage_category_summary_report(
    coverage_categories: set[str],
) -> dict[str, Any]:
    required = set(REQUIRED_COVERAGE_CATEGORIES)
    actual = set(coverage_categories)
    return {
        "complete": required <= actual,
        "required_category_ids": sorted(REQUIRED_COVERAGE_CATEGORIES),
        "covered_required_category_ids": sorted(actual & required),
        "missing_category_ids": sorted(required - actual),
        "covered_required_category_count": len(actual & required),
        "required_category_count": len(REQUIRED_COVERAGE_CATEGORIES),
    }


def validate_manifest_shape(
    root: Path,
    manifest_path: Path,
    support_matrix_names: set[str],
    conformance_report: ConformanceCoverageReport,
) -> ManifestCoverageReport:
    payload = load_json(manifest_path)
    allowed_categories = allowed_coverage_categories(root)

    schema_version = payload.get("schema_version")
    if schema_version != SCHEMA_VERSION:
        raise ValueError(
            f"{manifest_path}: schema_version must be {SCHEMA_VERSION!r}, "
            f"got {schema_version!r}"
        )

    description = payload.get("description")
    if not isinstance(description, str) or not description:
        raise ValueError(f"{manifest_path}: description must be a non-empty string")

    families = payload.get("families")
    if not isinstance(families, list) or not families:
        raise ValueError(f"{manifest_path}: families must be a non-empty array")

    seen_family_ids: set[str] = set()
    family_ids: list[str] = []
    evidence_names: set[str] = set()
    evidence_metadata_by_name: dict[str, tuple[str, str | None]] = {}
    evidence_names_by_kind = {kind: set() for kind in sorted(ALLOWED_KINDS)}
    coverage_categories: set[str] = set()
    coverage_categories_by_evidence_name: dict[str, set[str]] = {}
    family_reports: list[dict[str, Any]] = []
    coverage_counts = empty_coverage_counts()
    diagnostic_family_count = 0
    linked_conformance_feature_groups: set[str] = set()
    linked_conformance_entry_ids: set[str] = set()

    for family_index, family in enumerate(families):
        family_context = f"{manifest_path}: families[{family_index}]"
        if not isinstance(family, dict):
            raise ValueError(f"{family_context}: family must be a JSON object")

        family_id = require_string(family, "id", family_context)
        if family_id in seen_family_ids:
            raise ValueError(f"{family_context}: duplicate family id {family_id!r}")
        seen_family_ids.add(family_id)
        family_ids.append(family_id)

        require_string(family, "title", family_context)
        status = require_string(family, "status", family_context)
        if status not in ALLOWED_STATUSES:
            raise ValueError(
                f"{family_context}: unsupported status {status!r}; "
                f"expected one of {sorted(ALLOWED_STATUSES)}"
            )

        conformance_feature_groups = require_sorted_string_list(
            family, "conformance_feature_groups", family_context
        )
        conformance_entries = require_sorted_string_list(
            family, "conformance_entries", family_context
        )
        linked_conformance_entries = validate_family_conformance_linkage(
            family_context,
            family_id,
            status,
            conformance_feature_groups,
            conformance_entries,
            conformance_report,
        )
        linked_conformance_feature_groups.update(conformance_feature_groups)
        linked_conformance_entry_ids.update(
            entry.entry_id for entry in linked_conformance_entries
        )

        coverage = family.get("coverage")
        if not isinstance(coverage, list) or not coverage:
            raise ValueError(f"{family_context}: coverage must be a non-empty array")

        family_evidence_names: list[str] = []
        family_coverage_categories: set[str] = set()
        family_counts = empty_coverage_counts()
        family_has_support_matrix_evidence = False
        family_has_diagnostic_evidence = False
        for coverage_index, coverage_entry in enumerate(coverage):
            coverage_context = f"{family_context}: coverage[{coverage_index}]"
            if not isinstance(coverage_entry, dict):
                raise ValueError(
                    f"{coverage_context}: coverage entry must be a JSON object"
                )
            name, entry_coverage_categories = validate_coverage_entry(
                coverage_entry,
                coverage_context,
                support_matrix_names,
                allowed_categories,
            )
            kind = coverage_entry["kind"]
            evidence_metadata = (kind, coverage_entry.get("diagnostic_code"))
            previous_metadata = evidence_metadata_by_name.get(name)
            if previous_metadata is not None and previous_metadata != evidence_metadata:
                previous_kind, previous_diagnostic_code = previous_metadata
                kind_label = (
                    f"{previous_kind!r}"
                    if previous_diagnostic_code is None
                    else f"{previous_kind!r}/{previous_diagnostic_code!r}"
                )
                current_label = (
                    f"{kind!r}"
                    if evidence_metadata[1] is None
                    else f"{kind!r}/{evidence_metadata[1]!r}"
                )
                raise ValueError(
                    f"{coverage_context}: evidence {name!r} reuses conflicting "
                    f"coverage metadata: {kind_label} vs {current_label}"
                )
            evidence_metadata_by_name[name] = evidence_metadata
            family_evidence_names.append(name)
            evidence_names.add(name)
            family_coverage_categories.update(entry_coverage_categories)
            coverage_categories.update(entry_coverage_categories)
            coverage_categories_by_evidence_name.setdefault(name, set()).update(
                entry_coverage_categories
            )

            family_counts[kind] += 1
            coverage_counts[kind] += 1
            evidence_names_by_kind[kind].add(name)
            if kind == "support-matrix":
                family_has_support_matrix_evidence = True
            if kind in DIAGNOSTIC_KINDS:
                family_has_diagnostic_evidence = True

        if family_evidence_names != sorted(family_evidence_names):
            raise ValueError(
                f"{family_context}: coverage entries must be sorted by evidence name"
            )
        if len(family_evidence_names) != len(set(family_evidence_names)):
            raise ValueError(f"{family_context}: duplicate coverage evidence name")
        if (
            status == "supported"
            and family_id not in DIAGNOSTIC_ONLY_SUPPORTED_FAMILIES
            and not family_has_support_matrix_evidence
        ):
            raise ValueError(
                f"{family_context}: supported family needs support-matrix evidence"
            )
        if (
            family_id in DIAGNOSTIC_ONLY_SUPPORTED_FAMILIES
            and not family_has_diagnostic_evidence
        ):
            raise ValueError(
                f"{family_context}: diagnostic family needs diagnostic or "
                "planned-failure evidence"
            )
        if family_has_diagnostic_evidence:
            diagnostic_family_count += 1

        family_reports.append(
            {
                "id": family_id,
                "title": family["title"],
                "status": status,
                "conformance_feature_groups": conformance_feature_groups,
                "conformance_entries": conformance_entries,
                "conformance_fixtures": sorted(
                    {entry.fixture for entry in linked_conformance_entries}
                ),
                "evidence_names": family_evidence_names,
                "coverage_categories": sorted(family_coverage_categories),
                "coverage_counts": coverage_counts_report(family_counts),
            }
        )

    if family_ids != sorted(family_ids):
        raise ValueError(f"{manifest_path}: families must be sorted by id")

    required = set(REQUIRED_FAMILIES)
    actual = set(family_ids)
    missing = sorted(required - actual)
    unknown = sorted(actual - required)
    if missing:
        raise ValueError(
            f"{manifest_path}: missing required HIR family id(s): " + ", ".join(missing)
        )
    if unknown:
        raise ValueError(
            f"{manifest_path}: unknown HIR family id(s): " + ", ".join(unknown)
        )
    if diagnostic_family_count == 0:
        raise ValueError(
            f"{manifest_path}: at least one family must map invalid shapes to "
            "diagnostic or planned-failure evidence"
        )
    missing_supported_groups = sorted(
        conformance_report.accepted_feature_groups - linked_conformance_feature_groups
    )
    if missing_supported_groups:
        raise ValueError(
            f"{manifest_path}: missing HIR coverage linkage for v0-supported "
            "conformance feature_group(s): "
            + ", ".join(missing_supported_groups)
            + "; add conformance_feature_groups and conformance_entries to a "
            "supported HIR family"
        )
    missing_graphics_package_entries = sorted(
        set(required_graphics_stage_package_entry_ids(conformance_report))
        - linked_conformance_entry_ids
    )
    if missing_graphics_package_entries:
        raise ValueError(
            f"{manifest_path}: missing HIR coverage linkage for accepted "
            f"{GRAPHICS_STAGES_FEATURE_GROUP} package conformance entry id(s): "
            + ", ".join(missing_graphics_package_entries)
            + "; add each fixture-scoped package row to conformance_entries for "
            "an appropriate supported HIR family"
        )
    missing_coverage_categories = sorted(
        set(REQUIRED_COVERAGE_CATEGORIES) - coverage_categories
    )
    if missing_coverage_categories:
        raise ValueError(
            f"{manifest_path}: missing required HIR coverage category id(s): "
            + ", ".join(missing_coverage_categories)
        )

    return ManifestCoverageReport(
        evidence_names=evidence_names,
        evidence_names_by_kind=evidence_names_by_kind,
        coverage_categories=coverage_categories,
        coverage_categories_by_evidence_name=coverage_categories_by_evidence_name,
        families=family_reports,
        coverage_counts=coverage_counts,
        conformance_feature_groups=linked_conformance_feature_groups,
    )


def ctest_inventory_report(
    root: Path,
    build_dir: Path,
    ctest_config: str | None,
    evidence_names: set[str],
    support_locations: dict[str, list[int]],
) -> tuple[dict[str, Any], list[str]]:
    report: dict[str, Any] = {
        "checked": True,
        "build_dir": str(build_dir),
        "ctest_config": ctest_config,
        "inventory_test_count": 0,
        "missing_evidence_names": [],
        "unavailable_optional_evidence": [],
        "errors": [],
    }

    try:
        inventory = load_ctest_inventory(build_dir, ctest_config)
    except (RuntimeError, json.JSONDecodeError) as exc:
        errors = [str(exc)]
        report["errors"] = errors
        return report, errors

    report["inventory_test_count"] = len(inventory.names)
    errors = validate_unit_test_aliases(root, evidence_names, inventory.names)
    ctest_references = {
        name
        for name in evidence_names
        if not (name.startswith("test") and name in UNIT_TEST_FUNCTION_ALIASES)
    }
    missing, unavailable_optional = split_missing_ctest_references(
        ctest_references,
        inventory,
        declared_optional_native_evidence_names(root),
    )
    if missing:
        errors.append(
            "HIR verifier v0 coverage references CTest names that are not "
            f"registered in {build_dir}:\n"
            + "\n".join(
                "  - "
                + name
                + f" ({format_locations(SUPPORT_MATRIX_PATH, support_locations, name)})"
                for name in missing
            )
        )

    if unavailable_optional:
        unavailable_names = ", ".join(
            sorted(item.name for item in unavailable_optional)
        )
        errors.append(
            "HIR verifier v0 coverage must not depend on optional-native "
            f"unavailable evidence: {unavailable_names}"
        )

    report["missing_evidence_names"] = missing
    report["unavailable_optional_evidence"] = [
        {"name": item.name, "target": item.target, "category": item.category}
        for item in sorted(unavailable_optional, key=lambda item: item.name)
    ]
    report["errors"] = errors
    return report, errors


def validate_ctest_inventory(
    root: Path,
    build_dir: Path,
    ctest_config: str | None,
    evidence_names: set[str],
    support_locations: dict[str, list[int]],
) -> list[str]:
    _, errors = ctest_inventory_report(
        root,
        build_dir,
        ctest_config,
        evidence_names,
        support_locations,
    )
    return errors


def build_report(
    manifest_report: ManifestCoverageReport,
    conformance_report: ConformanceCoverageReport,
    support_names: set[str],
    ctest_report: dict[str, Any] | None,
) -> dict[str, Any]:
    evidence_names = sorted(manifest_report.evidence_names)
    report: dict[str, Any] = {
        "schema_version": REPORT_SCHEMA_VERSION,
        "manifest_schema_version": SCHEMA_VERSION,
        "required_family_count": len(REQUIRED_FAMILIES),
        "required_family_summary": required_family_summary_report(
            manifest_report.families
        ),
        "required_coverage_category_summary": (
            required_coverage_category_summary_report(
                manifest_report.coverage_categories
            )
        ),
        "conformance_feature_group_summary": (
            conformance_feature_group_summary_report(
                manifest_report.families, conformance_report
            )
        ),
        "family_statuses": {
            family["id"]: family["status"] for family in manifest_report.families
        },
        "families": manifest_report.families,
        "family_evidence_counts": family_evidence_counts_report(
            manifest_report.families
        ),
        "evidence_names": evidence_names,
        "evidence_names_by_kind": {
            kind: sorted(names)
            for kind, names in sorted(manifest_report.evidence_names_by_kind.items())
        },
        "coverage_counts": coverage_counts_report(manifest_report.coverage_counts),
        "coverage_categories": sorted(manifest_report.coverage_categories),
        "coverage_categories_by_evidence_name": {
            name: sorted(categories)
            for name, categories in sorted(
                manifest_report.coverage_categories_by_evidence_name.items()
            )
        },
        "support_matrix_evidence_counts": {
            "coverage_entry_count": manifest_report.coverage_counts["support-matrix"],
            "unique_coverage_evidence_name_count": len(
                manifest_report.evidence_names_by_kind["support-matrix"]
            ),
            "manifest_unique_evidence_name_count": len(evidence_names),
            "support_doc_unique_evidence_name_count": len(support_names),
        },
    }
    if ctest_report is None:
        report["ctest"] = {"checked": False}
    else:
        report["ctest"] = ctest_report
    return report


def write_report(path: Path, report: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


SELF_TEST_CONFORMANCE_STATUS_BY_GROUP = {
    "atomics": "accepted",
    "compute-basics": "accepted",
    "control-flow": "accepted",
    "graphics-stages": "accepted",
    "known-native-v0-unsupported": "unsupported",
    "resources": "accepted",
    "storage-images": "accepted",
    "texture-sampling": "accepted",
}
SELF_TEST_GRAPHICS_PACKAGE_ENTRY_ID = "graphics-stages.self-test-source-package"

SELF_TEST_FAMILY_CONFORMANCE_GROUPS = {
    "arrays": ["resources"],
    "atomics": ["atomics"],
    "compute-basics": ["compute-basics"],
    "constants": ["compute-basics"],
    "control-flow": ["control-flow"],
    "invalid-shape-diagnostics": ["known-native-v0-unsupported"],
    "resources": ["resources"],
    "stage-coverage": ["graphics-stages"],
    "storage-buffers": ["resources"],
    "storage-images": ["storage-images"],
    "textures-samplers": ["texture-sampling"],
    "type-semantics": ["compute-basics"],
}

SELF_TEST_COVERAGE_CATEGORIES_BY_FAMILY = {
    "arrays": [
        "HIRExpressionKind::IndexAccess",
    ],
    "atomics": [
        "HIRExpressionKind::Call",
        "HIRStatementKind::Expression",
    ],
    "compute-basics": [
        "HIRExpressionKind::Binary",
        "HIRExpressionKind::Constructor",
        "HIRResourceKind::Shared",
        "HIRStatementKind::Assignment",
        "HIRStatementKind::Declaration",
    ],
    "constants": [
        "HIRExpressionKind::MemberAccess",
    ],
    "control-flow": [
        "HIRStatementKind::Block",
        "HIRStatementKind::Break",
        "HIRStatementKind::Continue",
        "HIRStatementKind::Discard",
        "HIRStatementKind::For",
        "HIRStatementKind::If",
        "HIRStatementKind::Return",
    ],
    "invalid-shape-diagnostics": [],
    "resources": [
        "HIRResourceKind::Uniform",
    ],
    "stage-coverage": [],
    "storage-buffers": [
        "HIRResourceKind::Buffer",
    ],
    "storage-images": [
        "HIRResourceKind::StorageImage",
    ],
    "textures-samplers": [
        "HIRExpressionKind::NonUniform",
        "HIRExpressionKind::TextureCompare",
        "HIRExpressionKind::TextureCompareLodManual",
        "HIRExpressionKind::TextureSample",
        "HIRResourceKind::Sampler",
        "HIRResourceKind::Texture",
    ],
    "type-semantics": [],
}

SELF_TEST_DIAGNOSTIC_COVERAGE = (
    (
        "testSelfDiagnosticArrayWriteValidation",
        "opengl.unsupported-function-parameter-array-write",
    ),
    (
        "testSelfDiagnosticDuplicateResourceBindingValidation",
        "opt.hir-duplicate-resource-binding",
    ),
    ("testSelfDiagnosticDuplicateResourceValidation", "opt.hir-duplicate-resource"),
    ("testSelfDiagnosticExpressionShapeValidation", "opt.hir-expression-shape"),
    ("testSelfDiagnosticMatrixConstructorValidation", "opt.hir-matrix-constructor"),
    ("testSelfDiagnosticMissingEntryPointValidation", "opt.hir-missing-entry-point"),
    ("testSelfDiagnosticResourceShapeValidation", "opt.hir-resource-shape"),
    (
        "testSelfDiagnosticRuntimeResourceArrayShapeValidation",
        "opt.hir-runtime-resource-array-shape",
    ),
    ("testSelfDiagnosticScalarConstructorValidation", "opt.hir-scalar-constructor"),
    ("testSelfDiagnosticStatementShapeValidation", "opt.hir-statement-shape"),
    (
        "testSelfDiagnosticStorageImageRuntimeArrayValidation",
        "opt.hir-storage-image-runtime-descriptor-array",
    ),
    ("testSelfDiagnosticVectorConstructorValidation", "opt.hir-vector-constructor"),
    ("testSelfDiagnosticStorageImageAtomicValidation", "sema.storage-image-atomic"),
)


def self_test_conformance_entry_id(feature_group: str) -> str:
    return f"{feature_group}.self-test"


def self_test_conformance_fixture(feature_group: str, status: str) -> str:
    stem = "".join(part.title() for part in feature_group.split("-"))
    if status == "unsupported":
        return f"tests/check-failures/Bad{stem}SelfTest.cgl"
    return f"tests/frontend/fixtures/{stem}SelfTest.cgl"


def self_test_graphics_package_fixture() -> str:
    return "tests/frontend/fixtures/GraphicsStagesPackageSelfTest.cgl"


def self_test_conformance_payload() -> dict[str, Any]:
    required_statuses = [
        {
            "feature_group": feature_group,
            "status": status,
            "min_entries": 1,
        }
        for feature_group, status in sorted(
            SELF_TEST_CONFORMANCE_STATUS_BY_GROUP.items()
        )
    ]
    entries = []
    for feature_group, status in sorted(SELF_TEST_CONFORMANCE_STATUS_BY_GROUP.items()):
        entries.append(
            {
                "id": self_test_conformance_entry_id(feature_group),
                "feature_group": feature_group,
                "status": status,
                "fixture": self_test_conformance_fixture(feature_group, status),
            }
        )
        if feature_group == GRAPHICS_STAGES_FEATURE_GROUP:
            entries.append(
                {
                    "id": SELF_TEST_GRAPHICS_PACKAGE_ENTRY_ID,
                    "feature_group": feature_group,
                    "status": status,
                    "command_profile": "source-package-build",
                    "fixture": self_test_graphics_package_fixture(),
                }
            )
    return {
        "schema_version": "self-test-conformance",
        "coverage_contract": {
            "required_feature_statuses": required_statuses,
        },
        "entries": entries,
    }


def write_self_test_conformance_manifest(
    tmp_dir: Path,
    label: str,
    payload: dict[str, Any],
    *,
    create_fixtures: bool = True,
) -> Path:
    if create_fixtures:
        for entry in payload["entries"]:
            fixture = tmp_dir / entry["fixture"]
            fixture.parent.mkdir(parents=True, exist_ok=True)
            fixture.write_text(
                "shader SelfTest { compute { void main() {} } }\n",
                encoding="utf-8",
            )

    path = tmp_dir / f"{label}-conformance.json"
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return path


def write_self_test_hir_header(tmp_dir: Path) -> None:
    header_path = tmp_dir / HIR_HEADER_PATH
    header_path.parent.mkdir(parents=True, exist_ok=True)
    header_path.write_text(
        """\
enum class HIRResourceKind {
  Uniform,
  Buffer,
  Shared,
  Texture,
  StorageImage,
  Sampler,
  Value,
};

enum class HIRExpressionKind {
  Empty,
  Identifier,
  Literal,
  Group,
  MemberAccess,
  IndexAccess,
  NonUniform,
  Call,
  Constructor,
  Unary,
  Binary,
  Select,
  TextureSample,
  TextureCompare,
  TextureCompareLodManual,
};

enum class HIRStatementKind {
  Declaration,
  Assignment,
  Return,
  Expression,
  Block,
  If,
  For,
  Break,
  Continue,
  Discard,
  Raw,
};
""",
        encoding="utf-8",
    )


def self_test_evidence_name(family_id: str) -> str:
    return f"cglc_self_{family_id.replace('-', '_')}_coverage"


def self_test_manifest_payload() -> dict[str, Any]:
    families: list[dict[str, Any]] = []
    for family_id in sorted(REQUIRED_FAMILIES):
        coverage_categories = SELF_TEST_COVERAGE_CATEGORIES_BY_FAMILY[family_id]
        coverage = [
            {
                "kind": "support-matrix",
                "name": self_test_evidence_name(family_id),
                "requirement": f"Self-test support evidence for {family_id}.",
            }
        ]
        if coverage_categories:
            coverage[0][COVERAGE_CATEGORY_FIELD] = coverage_categories
        if family_id == "invalid-shape-diagnostics":
            for evidence_name, diagnostic_code in SELF_TEST_DIAGNOSTIC_COVERAGE:
                coverage.append(
                    {
                        "kind": "diagnostic",
                        "name": evidence_name,
                        "diagnostic_code": diagnostic_code,
                        COVERAGE_CATEGORY_FIELD: [
                            f"{DIAGNOSTIC_COVERAGE_CATEGORY_PREFIX}{diagnostic_code}"
                        ],
                        "requirement": (
                            "Self-test diagnostic evidence is counted separately."
                        ),
                    }
                )
        conformance_entries = [
            self_test_conformance_entry_id(feature_group)
            for feature_group in SELF_TEST_FAMILY_CONFORMANCE_GROUPS[family_id]
        ]
        if (
            GRAPHICS_STAGES_FEATURE_GROUP
            in SELF_TEST_FAMILY_CONFORMANCE_GROUPS[family_id]
        ):
            conformance_entries.append(SELF_TEST_GRAPHICS_PACKAGE_ENTRY_ID)
        families.append(
            {
                "id": family_id,
                "title": family_id.replace("-", " ").title(),
                "status": "supported",
                "conformance_feature_groups": SELF_TEST_FAMILY_CONFORMANCE_GROUPS[
                    family_id
                ],
                "conformance_entries": sorted(conformance_entries),
                "coverage": sorted(coverage, key=lambda entry: entry["name"]),
            }
        )
    return {
        "schema_version": SCHEMA_VERSION,
        "description": "Self-test HIR verifier coverage manifest.",
        "families": families,
    }


def write_self_test_manifest(
    tmp_dir: Path, label: str, payload: dict[str, Any]
) -> Path:
    path = tmp_dir / f"{label}.json"
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return path


def run_self_test_probe(
    tmp_dir: Path,
    label: str,
    payload: dict[str, Any],
    support_names: set[str],
    conformance_report: ConformanceCoverageReport,
    expected_error: str | None = None,
) -> list[str]:
    path = write_self_test_manifest(tmp_dir, label, payload)
    try:
        validate_manifest_shape(tmp_dir, path, support_names, conformance_report)
    except ValueError as exc:
        if expected_error is None:
            return [f"self-test {label}: valid manifest failed: {exc}"]
        if expected_error not in str(exc):
            return [
                f"self-test {label}: expected {expected_error!r} in error, got {exc}"
            ]
        return []

    if expected_error is not None:
        return [f"self-test {label}: expected validation failure"]
    return []


def run_self_test() -> int:
    payload = self_test_manifest_payload()
    supported_family_index = next(
        index
        for index, family in enumerate(payload["families"])
        if family["id"] not in DIAGNOSTIC_ONLY_SUPPORTED_FAMILIES
    )
    support_names = (
        {self_test_evidence_name(family_id) for family_id in REQUIRED_FAMILIES}
        | {
            "cglc_self_supported_family_planned_failure",
            "testSelfSupportedFamilyDiagnosticValidation",
        }
        | {evidence_name for evidence_name, _ in SELF_TEST_DIAGNOSTIC_COVERAGE}
    )
    errors: list[str] = []
    with tempfile.TemporaryDirectory(prefix="crossgl-hir-coverage-self-test-") as temp:
        tmp_dir = Path(temp)
        write_self_test_hir_header(tmp_dir)
        conformance_payload = self_test_conformance_payload()
        conformance_path = write_self_test_conformance_manifest(
            tmp_dir, "valid", conformance_payload
        )
        try:
            conformance_report = load_conformance_coverage(tmp_dir, conformance_path)
        except ValueError as exc:
            errors.append(f"self-test conformance manifest failed: {exc}")
            conformance_report = None

        missing_fixture_payload = copy.deepcopy(conformance_payload)
        missing_fixture_payload["entries"][0]["fixture"] = (
            "tests/frontend/fixtures/MissingSelfTest.cgl"
        )
        missing_fixture_path = write_self_test_conformance_manifest(
            tmp_dir,
            "missing-fixture",
            missing_fixture_payload,
            create_fixtures=False,
        )
        try:
            load_conformance_coverage(tmp_dir, missing_fixture_path)
        except ValueError as exc:
            if "fixture does not exist" not in str(exc):
                errors.append(
                    f"self-test missing fixture: expected fixture diagnostic, got {exc}"
                )
        else:
            errors.append("self-test missing fixture: expected validation failure")

        if conformance_report is None:
            print("HIR verifier v0 coverage self-test failed:", file=sys.stderr)
            for error in errors:
                print(f"- {error}", file=sys.stderr)
            return 1

        errors.extend(
            run_self_test_probe(
                tmp_dir,
                "valid-minimal",
                payload,
                support_names,
                conformance_report,
            )
        )

        diagnostic_only = copy.deepcopy(payload)
        diagnostic_only["families"][supported_family_index]["coverage"] = [
            {
                "kind": "diagnostic",
                "name": "testSelfSupportedFamilyDiagnosticValidation",
                "diagnostic_code": "self.supported-family-shape",
                "requirement": "Self-test diagnostic-only family must not count as supported.",
            }
        ]
        errors.extend(
            run_self_test_probe(
                tmp_dir,
                "supported-diagnostic-only-family",
                diagnostic_only,
                support_names,
                conformance_report,
                "supported family needs support-matrix evidence",
            )
        )

        rejection_as_support = copy.deepcopy(payload)
        rejection_as_support["families"][supported_family_index]["coverage"] = [
            {
                "kind": "support-matrix",
                "name": "cglc_self_supported_family_planned_failure",
                "requirement": "Self-test rejection evidence must not count as positive support.",
            }
        ]
        errors.extend(
            run_self_test_probe(
                tmp_dir,
                "rejection-evidence-as-support",
                rejection_as_support,
                support_names,
                conformance_report,
                "support-matrix entries must cite passing evidence",
            )
        )

        unknown_entry = copy.deepcopy(payload)
        unknown_entry["families"][supported_family_index]["conformance_entries"] = [
            "missing.self-test"
        ]
        errors.extend(
            run_self_test_probe(
                tmp_dir,
                "unknown-conformance-entry",
                unknown_entry,
                support_names,
                conformance_report,
                "unknown conformance entry id",
            )
        )

        missing_graphics_package_link = copy.deepcopy(payload)
        for family in missing_graphics_package_link["families"]:
            if SELF_TEST_GRAPHICS_PACKAGE_ENTRY_ID in family["conformance_entries"]:
                family["conformance_entries"].remove(
                    SELF_TEST_GRAPHICS_PACKAGE_ENTRY_ID
                )
        errors.extend(
            run_self_test_probe(
                tmp_dir,
                "missing-graphics-package-link",
                missing_graphics_package_link,
                support_names,
                conformance_report,
                "missing HIR coverage linkage for accepted graphics-stages "
                "package conformance entry id(s): "
                f"{SELF_TEST_GRAPHICS_PACKAGE_ENTRY_ID}",
            )
        )

        missing_feature_group_link = copy.deepcopy(payload)
        textures_family = next(
            family
            for family in missing_feature_group_link["families"]
            if family["id"] == "textures-samplers"
        )
        textures_family["conformance_feature_groups"] = ["resources"]
        textures_family["conformance_entries"] = [
            self_test_conformance_entry_id("resources")
        ]
        errors.extend(
            run_self_test_probe(
                tmp_dir,
                "missing-supported-feature-group-link",
                missing_feature_group_link,
                support_names,
                conformance_report,
                "missing HIR coverage linkage for v0-supported conformance "
                "feature_group(s): texture-sampling",
            )
        )

        missing_category = copy.deepcopy(payload)
        textures_family = next(
            family
            for family in missing_category["families"]
            if family["id"] == "textures-samplers"
        )
        texture_row = textures_family["coverage"][0]
        texture_row[COVERAGE_CATEGORY_FIELD].remove(
            "HIRExpressionKind::TextureCompareLodManual"
        )
        errors.extend(
            run_self_test_probe(
                tmp_dir,
                "missing-coverage-category",
                missing_category,
                support_names,
                conformance_report,
                "missing required HIR coverage category id(s): "
                "HIRExpressionKind::TextureCompareLodManual",
            )
        )

        stale_hir_enum_category = copy.deepcopy(payload)
        compute_family = next(
            family
            for family in stale_hir_enum_category["families"]
            if family["id"] == "compute-basics"
        )
        compute_row = compute_family["coverage"][0]
        compute_row[COVERAGE_CATEGORY_FIELD] = [
            "HIRExpressionKind::ImaginaryFutureNode"
        ]
        errors.extend(
            run_self_test_probe(
                tmp_dir,
                "stale-hir-enum-category",
                stale_hir_enum_category,
                support_names,
                conformance_report,
                "HIRExpressionKind has no enum entry 'ImaginaryFutureNode'",
            )
        )

        stale_diagnostic_category = copy.deepcopy(payload)
        invalid_shape_family = next(
            family
            for family in stale_diagnostic_category["families"]
            if family["id"] == "invalid-shape-diagnostics"
        )
        expression_shape_entry = next(
            entry
            for entry in invalid_shape_family["coverage"]
            if entry.get("diagnostic_code") == "opt.hir-expression-shape"
        )
        expression_shape_entry[COVERAGE_CATEGORY_FIELD] = [
            "diagnostic:opt.hir-statement-shape"
        ]
        errors.extend(
            run_self_test_probe(
                tmp_dir,
                "stale-diagnostic-category",
                stale_diagnostic_category,
                support_names,
                conformance_report,
                "diagnostic coverage category must match diagnostic_code",
            )
        )

    if errors:
        print("HIR verifier v0 coverage self-test failed:", file=sys.stderr)
        for error in errors:
            print(f"- {error}", file=sys.stderr)
        return 1

    print("HIR verifier v0 coverage self-test passed.")
    return 0


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument(
        "--conformance-manifest",
        type=Path,
        default=DEFAULT_CONFORMANCE_MANIFEST,
        help="v0 conformance manifest used for feature-group and fixture linkage.",
    )
    parser.add_argument("--build-dir", type=Path)
    parser.add_argument("--ctest-config", default=None)
    parser.add_argument(
        "--self-test",
        action="store_true",
        help="Run checker-internal manifest validation probes and exit.",
    )
    parser.add_argument(
        "--report-output",
        type=Path,
        help="Write a deterministic JSON coverage report to this path.",
    )
    args = parser.parse_args(argv)

    if args.self_test:
        return run_self_test()

    root = args.root.resolve()
    manifest_path = args.manifest
    if not manifest_path.is_absolute():
        manifest_path = root / manifest_path
    conformance_path = args.conformance_manifest
    if not conformance_path.is_absolute():
        conformance_path = root / conformance_path

    support_matrix_path = root / SUPPORT_MATRIX_PATH
    if not support_matrix_path.exists():
        print(
            f"support-matrix evidence doc is missing: {support_matrix_path}",
            file=sys.stderr,
        )
        return 2

    support_references = parse_evidence_references(support_matrix_path)
    support_names = {reference.name for reference in support_references}
    support_locations = line_locations(support_references)

    try:
        conformance_report = load_conformance_coverage(root, conformance_path)
        manifest_report = validate_manifest_shape(
            root, manifest_path, support_names, conformance_report
        )
    except ValueError as exc:
        print(exc, file=sys.stderr)
        return 1

    errors: list[str] = []
    ctest_report: dict[str, Any] | None = None
    if args.build_dir is not None:
        build_dir = args.build_dir
        if not build_dir.is_absolute():
            build_dir = root / build_dir
        if not build_dir.exists():
            errors.append(f"build directory does not exist: {build_dir}")
            ctest_report = {
                "checked": True,
                "build_dir": str(build_dir),
                "ctest_config": args.ctest_config or None,
                "inventory_test_count": 0,
                "missing_evidence_names": [],
                "unavailable_optional_evidence": [],
                "errors": [errors[-1]],
            }
        else:
            ctest_report, ctest_errors = ctest_inventory_report(
                root,
                build_dir,
                args.ctest_config or None,
                manifest_report.evidence_names,
                support_locations,
            )
            errors.extend(ctest_errors)

    if args.report_output is not None:
        try:
            write_report(
                args.report_output,
                build_report(
                    manifest_report,
                    conformance_report,
                    support_names,
                    ctest_report,
                ),
            )
        except OSError as exc:
            print(
                f"failed to write report output {args.report_output}: {exc}",
                file=sys.stderr,
            )
            return 2

    if errors:
        print("HIR verifier v0 coverage check failed:", file=sys.stderr)
        for error in errors:
            print(f"- {error}", file=sys.stderr)
        return 1

    ctest_note = " and configured CTest inventory" if args.build_dir else ""
    print(
        f"Validated {len(REQUIRED_FAMILIES)} required native-v0 HIR verifier "
        f"families and {len(conformance_report.accepted_feature_groups)} "
        "v0-supported conformance feature group link(s) with "
        f"{len(manifest_report.evidence_names)} support-matrix evidence "
        f"reference(s), and {len(REQUIRED_COVERAGE_CATEGORIES)} required HIR "
        f"category link(s){ctest_note}."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
