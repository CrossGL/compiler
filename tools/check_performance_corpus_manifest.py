#!/usr/bin/env python3
"""Validate the static Milestone 6 performance corpus manifest.

This checker is intentionally local and static: it parses the checked-in JSON
manifest and verifies fixture metadata only. It does not invoke cglc, import the
benchmark runner, or run performance benchmarks.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import sys
import tempfile
from pathlib import Path
from typing import Any


SCHEMA_VERSION = 1
DEFAULT_CORPUS = "milestone6-smoke"
MANIFEST_PATH = Path("tests/performance/performance_corpus_manifest.json")
DEFAULT_TARGETS = ("directx", "opengl")
KNOWN_TARGETS = ("directx", "metal", "opengl", "vulkan")
REQUIRED_MILESTONE6_CATEGORIES = (
    "storage-buffers",
    "texture-sampling",
    "descriptor-arrays",
    "storage-images",
    "atomics",
    "control-flow",
)
KNOWN_COVERAGE_POLICIES = ("aggregate", "matrix")
KNOWN_COVERAGE_PACKAGE_MODES = ("native", "source-package")
KNOWN_COVERAGE_REPORT_POLICIES = ("report-only",)
KNOWN_COVERAGE_ARTIFACT_KINDS = (
    "manifestArtifacts",
    "nativeArtifactDescriptor",
    "nativeBinaryStatus",
    "nativeProfile",
)
KNOWN_COVERAGE_SUMMARY_FIELDS = (
    "manifestArtifactKinds",
    "nativeArtifactDescriptorOptimizationEvidence",
    "nativeOptimizationEvidence",
)
REQUIRED_MILESTONE6_COVERAGE_RULES: tuple[dict[str, Any], ...] = (
    {
        "name": "source-package-artifacts",
        "reportPolicy": "report-only",
        "packageMode": "source-package",
        "coverage": "matrix",
        "targets": ("directx", "opengl"),
        "categories": REQUIRED_MILESTONE6_CATEGORIES,
        "artifactKinds": ("nativeArtifactDescriptor", "nativeBinaryStatus"),
        "summaryFields": ("manifestArtifactKinds",),
    },
    {
        "name": "native-optimization-evidence",
        "reportPolicy": "report-only",
        "packageMode": "native",
        "coverage": "aggregate",
        "targets": ("metal", "vulkan"),
        "categories": (
            "storage-buffers",
            "descriptor-arrays",
            "storage-images",
            "atomics",
            "control-flow",
        ),
        "artifactKinds": ("nativeArtifactDescriptor", "nativeProfile"),
        "summaryFields": (
            "nativeArtifactDescriptorOptimizationEvidence",
            "nativeOptimizationEvidence",
        ),
    },
)
EXPECTED_MILESTONE6_FIXTURES = (
    (
        "storage-buffer-compute",
        "tests/fixtures/StorageBufferComputeShader.cgl",
        "storage-buffers",
        ("directx", "opengl", "vulkan"),
    ),
    (
        "texture-sampling-descriptor-array",
        "tests/fixtures/TextureOnlyDescriptorArraySampleShader.cgl",
        "texture-sampling",
        DEFAULT_TARGETS,
    ),
    (
        "texture-descriptor-array",
        "tests/fixtures/TextureDescriptorArrayShader.cgl",
        "descriptor-arrays",
        DEFAULT_TARGETS,
    ),
    (
        "mixed-resource-descriptor-array",
        "tests/fixtures/MixedResourceDescriptorArrayShader.cgl",
        "descriptor-arrays",
        ("directx", "metal", "opengl", "vulkan"),
    ),
    (
        "storage-image-explicit-format",
        "tests/fixtures/StorageImageExplicitFormatShader.cgl",
        "storage-images",
        DEFAULT_TARGETS,
    ),
    (
        "storage-image-descriptor-array",
        "tests/fixtures/StorageImageExplicitFormatDescriptorArrayShader.cgl",
        "storage-images",
        ("directx", "metal", "opengl", "vulkan"),
    ),
    (
        "storage-image-atomics",
        "tests/fixtures/StorageImageAtomicShader.cgl",
        "atomics",
        DEFAULT_TARGETS,
    ),
    (
        "storage-image-atomic-descriptor-array",
        "tests/fixtures/StorageImageAtomicDescriptorArrayShader.cgl",
        "atomics",
        ("directx", "opengl", "vulkan"),
    ),
    (
        "nested-control-flow",
        "tests/fixtures/NestedForComputeShader.cgl",
        "control-flow",
        DEFAULT_TARGETS,
    ),
    (
        "while-control-flow",
        "tests/fixtures/WhileComputeShader.cgl",
        "control-flow",
        ("directx", "metal", "opengl", "vulkan"),
    ),
    (
        "metal-storage-buffer-folded-descriptor-array",
        "tests/fixtures/MetalStorageBufferFoldedDescriptorArrayShader.cgl",
        "storage-buffers",
        ("metal",),
    ),
)
EXPECTED_MILESTONE6_CASES = tuple(
    f"{fixture_name}::{target}"
    for fixture_name, _, _, targets in EXPECTED_MILESTONE6_FIXTURES
    for target in targets
)
REQUIRED_FIXTURE_FIELDS = (
    "name",
    "path",
    "category",
    "description",
    "sourceSha256",
)


class CheckError(RuntimeError):
    """Raised when a checker self-test fails."""


def load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def rel(path: Path) -> str:
    return path.as_posix()


def normalize_source_text(text: str) -> str:
    return text.replace("\r\n", "\n").replace("\r", "\n")


def sha256_source_text(text: str) -> str:
    return hashlib.sha256(normalize_source_text(text).encode("utf-8")).hexdigest()


def expect_object(value: Any, path: str, errors: list[str]) -> dict[str, Any] | None:
    if not isinstance(value, dict):
        errors.append(f"{path}: expected JSON object")
        return None
    return value


def string_field(
    value: dict[str, Any], key: str, path: str, errors: list[str]
) -> str | None:
    field_path = f"{path}.{key}"
    if key not in value:
        errors.append(f"{field_path}: required string field is missing")
        return None
    field = value[key]
    if not isinstance(field, str) or field == "":
        errors.append(f"{field_path}: expected non-empty string")
        return None
    if field != field.strip():
        errors.append(f"{field_path}: must not have leading or trailing whitespace")
        return None
    return field


def list_field(
    value: dict[str, Any], key: str, path: str, errors: list[str]
) -> list[Any] | None:
    field_path = f"{path}.{key}"
    if key not in value:
        errors.append(f"{field_path}: required list field is missing")
        return None
    field = value[key]
    if not isinstance(field, list):
        errors.append(f"{field_path}: expected list")
        return None
    return field


def string_list_field(
    value: dict[str, Any],
    key: str,
    path: str,
    errors: list[str],
    *,
    known_values: tuple[str, ...] | None = None,
) -> tuple[str, ...]:
    items = list_field(value, key, path, errors)
    if items is None:
        return ()

    field_path = f"{path}.{key}"
    if not items:
        errors.append(f"{field_path}: expected non-empty list")
        return ()

    parsed: list[str] = []
    seen: set[str] = set()
    for index, item in enumerate(items):
        item_path = f"{field_path}[{index}]"
        if not isinstance(item, str) or item == "":
            errors.append(f"{item_path}: expected non-empty string")
            continue
        if item != item.strip():
            errors.append(f"{item_path}: must not have leading or trailing whitespace")
            continue
        if known_values is not None and item not in known_values:
            choices = ", ".join(known_values)
            errors.append(f"{item_path}: unknown value {item!r}; choose {choices}")
        if item in seen:
            errors.append(f"{item_path}: duplicate value {item!r}")
        seen.add(item)
        parsed.append(item)
    return tuple(parsed)


def validate_fixture_path(
    root: Path, value: str, path: str, errors: list[str]
) -> Path | None:
    if "\\" in value:
        errors.append(f"{path}: fixture path must use POSIX separators")
        return None
    if "://" in value:
        errors.append(f"{path}: fixture path must be repository-relative")
        return None

    fixture_path = Path(value)
    if fixture_path.is_absolute():
        errors.append(f"{path}: fixture path must be repository-relative")
        return None
    if ".." in fixture_path.parts:
        errors.append(f"{path}: fixture path must not escape the repository root")
        return None

    root_resolved = root.resolve()
    resolved = (root_resolved / fixture_path).resolve()
    if not resolved.is_relative_to(root_resolved):
        errors.append(f"{path}: fixture path must remain under the repository root")
        return None
    if not resolved.is_file():
        errors.append(f"{path}: fixture path does not exist: {value!r}")
        return None
    return resolved


def fixture_source_sha256(path: Path) -> str:
    return sha256_source_text(path.read_bytes().decode("utf-8"))


def validate_source_sha256(
    resolved_fixture_path: Path | None,
    value: Any,
    path: str,
    errors: list[str],
) -> str | None:
    if not isinstance(value, str) or value == "":
        errors.append(f"{path}: expected non-empty string")
        return None
    if value != value.strip():
        errors.append(f"{path}: must not have leading or trailing whitespace")
        return None
    if len(value) != 64 or any(char not in "0123456789abcdef" for char in value):
        errors.append(f"{path}: expected lowercase SHA-256 hex digest")
        return None
    if resolved_fixture_path is None:
        return value

    actual = fixture_source_sha256(resolved_fixture_path)
    if value != actual:
        errors.append(f"{path}: expected fixture source SHA-256 {actual}, got {value}")
        return None
    return value


def validate_targets(
    fixture: dict[str, Any],
    path: str,
    errors: list[str],
    *,
    require_explicit: bool = False,
) -> tuple[str, ...]:
    if "targets" not in fixture:
        if require_explicit:
            errors.append(
                f"{path}.targets: default corpus fixtures must declare "
                "target coverage explicitly"
            )
        return DEFAULT_TARGETS

    target_path = f"{path}.targets"
    targets = fixture["targets"]
    if not isinstance(targets, list) or not targets:
        errors.append(f"{target_path}: expected non-empty list")
        return ()

    parsed: list[str] = []
    seen: set[str] = set()
    for index, target in enumerate(targets):
        item_path = f"{target_path}[{index}]"
        if not isinstance(target, str) or target == "":
            errors.append(f"{item_path}: expected non-empty string")
            continue
        if target not in KNOWN_TARGETS:
            choices = ", ".join(KNOWN_TARGETS)
            errors.append(f"{item_path}: unknown target {target!r}; choose {choices}")
        if target in seen:
            errors.append(f"{item_path}: duplicate target {target!r}")
        seen.add(target)
        parsed.append(target)
    return tuple(parsed)


def validate_required_categories(
    manifest: dict[str, Any], errors: list[str]
) -> tuple[str, ...]:
    categories = list_field(manifest, "requiredCategories", "$", errors)
    if categories is None:
        return ()

    parsed: list[str] = []
    seen: set[str] = set()
    for index, category in enumerate(categories):
        item_path = f"$.requiredCategories[{index}]"
        if not isinstance(category, str) or not category:
            errors.append(f"{item_path}: expected non-empty string")
            continue
        if category != category.strip():
            errors.append(f"{item_path}: must not have leading or trailing whitespace")
            continue
        if category in seen:
            errors.append(f"{item_path}: duplicate category {category!r}")
        seen.add(category)
        parsed.append(category)

    expected = set(REQUIRED_MILESTONE6_CATEGORIES)
    observed = set(parsed)
    missing = sorted(expected - observed)
    extra = sorted(observed - expected)
    for category in missing:
        errors.append(f"$.requiredCategories: missing category {category!r}")
    for category in extra:
        errors.append(f"$.requiredCategories: unexpected category {category!r}")
    if not missing and not extra and tuple(parsed) != REQUIRED_MILESTONE6_CATEGORIES:
        errors.append(
            "$.requiredCategories: expected canonical category order "
            f"{list(REQUIRED_MILESTONE6_CATEGORIES)!r}"
        )
    return tuple(parsed)


def validate_required_coverage(
    manifest: dict[str, Any], errors: list[str]
) -> dict[str, dict[str, Any]]:
    coverage = list_field(manifest, "requiredCoverage", "$", errors)
    if coverage is None:
        return {}
    if not coverage:
        errors.append("$.requiredCoverage: expected at least one coverage rule")
        return {}

    parsed: dict[str, dict[str, Any]] = {}
    for index, rule_value in enumerate(coverage):
        rule_path = f"$.requiredCoverage[{index}]"
        rule = expect_object(rule_value, rule_path, errors)
        if rule is None:
            continue

        name = string_field(rule, "name", rule_path, errors)
        string_field(rule, "description", rule_path, errors)
        report_policy = string_field(rule, "reportPolicy", rule_path, errors)
        package_mode = string_field(rule, "packageMode", rule_path, errors)
        coverage_policy = string_field(rule, "coverage", rule_path, errors)
        targets = string_list_field(
            rule,
            "targets",
            rule_path,
            errors,
            known_values=KNOWN_TARGETS,
        )
        categories = string_list_field(
            rule,
            "categories",
            rule_path,
            errors,
            known_values=REQUIRED_MILESTONE6_CATEGORIES,
        )
        artifact_kinds = string_list_field(
            rule,
            "artifactKinds",
            rule_path,
            errors,
            known_values=KNOWN_COVERAGE_ARTIFACT_KINDS,
        )
        summary_fields = string_list_field(
            rule,
            "summaryFields",
            rule_path,
            errors,
            known_values=KNOWN_COVERAGE_SUMMARY_FIELDS,
        )

        if report_policy is not None and report_policy not in (
            KNOWN_COVERAGE_REPORT_POLICIES
        ):
            choices = ", ".join(KNOWN_COVERAGE_REPORT_POLICIES)
            errors.append(
                f"{rule_path}.reportPolicy: unknown value {report_policy!r}; "
                f"choose {choices}"
            )
        if package_mode is not None and package_mode not in (
            KNOWN_COVERAGE_PACKAGE_MODES
        ):
            choices = ", ".join(KNOWN_COVERAGE_PACKAGE_MODES)
            errors.append(
                f"{rule_path}.packageMode: unknown value {package_mode!r}; "
                f"choose {choices}"
            )
        if coverage_policy is not None and coverage_policy not in (
            KNOWN_COVERAGE_POLICIES
        ):
            choices = ", ".join(KNOWN_COVERAGE_POLICIES)
            errors.append(
                f"{rule_path}.coverage: unknown value {coverage_policy!r}; "
                f"choose {choices}"
            )

        if name is None:
            continue
        if name in parsed:
            errors.append(f"{rule_path}.name: duplicate coverage rule {name!r}")
            continue
        parsed[name] = {
            "path": rule_path,
            "name": name,
            "reportPolicy": report_policy,
            "packageMode": package_mode,
            "coverage": coverage_policy,
            "targets": targets,
            "categories": categories,
            "artifactKinds": artifact_kinds,
            "summaryFields": summary_fields,
        }

    expected_by_name = {
        str(rule["name"]): rule for rule in REQUIRED_MILESTONE6_COVERAGE_RULES
    }
    observed_names = set(parsed)
    expected_names = set(expected_by_name)
    for name in sorted(expected_names - observed_names):
        errors.append(f"$.requiredCoverage: missing required coverage rule {name!r}")
    for name in sorted(observed_names - expected_names):
        errors.append(f"$.requiredCoverage: unexpected coverage rule {name!r}")

    for name, expected in expected_by_name.items():
        observed = parsed.get(name)
        if observed is None:
            continue
        rule_path = str(observed["path"])
        for key in ("reportPolicy", "packageMode", "coverage"):
            if observed[key] != expected[key]:
                errors.append(
                    f"{rule_path}.{key}: expected {expected[key]!r}, "
                    f"got {observed[key]!r}"
                )
        for key in ("targets", "categories", "artifactKinds", "summaryFields"):
            if tuple(observed[key]) != expected[key]:
                errors.append(
                    f"{rule_path}.{key}: expected canonical coverage values "
                    f"{list(expected[key])!r}, got {list(observed[key])!r}"
                )

    return parsed


def validate_required_coverage_cases(
    coverage_rules: dict[str, dict[str, Any]],
    targets_by_category: dict[str, set[str]],
    categories_by_target: dict[str, set[str]],
    errors: list[str],
) -> None:
    for name in sorted(coverage_rules):
        rule = coverage_rules[name]
        rule_path = str(rule["path"])
        package_mode = str(rule["packageMode"])
        targets = tuple(rule["targets"])
        categories = tuple(rule["categories"])
        coverage_policy = rule["coverage"]

        if coverage_policy == "matrix":
            for category in categories:
                observed_targets = targets_by_category.get(category, set())
                for target in targets:
                    if target in observed_targets:
                        continue
                    errors.append(
                        f"{rule_path}: coverage rule {name!r} missing "
                        f"{package_mode} coverage for category {category!r} "
                        f"on target {target!r}"
                    )
            continue

        if coverage_policy == "aggregate":
            required_target_set = set(targets)
            required_category_set = set(categories)
            for category in categories:
                observed = sorted(
                    required_target_set & targets_by_category.get(category, set())
                )
                if observed:
                    continue
                errors.append(
                    f"{rule_path}: coverage rule {name!r} missing {package_mode} "
                    f"coverage for category {category!r}; expected at least one "
                    f"of targets {list(targets)!r}"
                )
            for target in targets:
                observed = sorted(
                    required_category_set & categories_by_target.get(target, set())
                )
                if observed:
                    continue
                errors.append(
                    f"{rule_path}: coverage rule {name!r} missing {package_mode} "
                    f"coverage for target {target!r}; expected at least one "
                    f"of categories {list(categories)!r}"
                )


def validate_manifest(root: Path, payload: Any) -> list[str]:
    errors: list[str] = []
    manifest = expect_object(payload, "$", errors)
    if manifest is None:
        return errors

    if manifest.get("schemaVersion") != SCHEMA_VERSION:
        errors.append(
            "$.schemaVersion: expected "
            f"{SCHEMA_VERSION!r}, got {manifest.get('schemaVersion')!r}"
        )

    default_corpus = string_field(manifest, "defaultCorpus", "$", errors)
    validate_required_categories(manifest, errors)
    coverage_rules = validate_required_coverage(manifest, errors)
    corpora = list_field(manifest, "corpora", "$", errors)
    if corpora is None:
        return errors
    if not corpora:
        errors.append("$.corpora: expected at least one corpus")

    corpus_names: set[str] = set()
    default_categories: set[str] = set()
    default_cases: set[str] = set()
    default_source_hashes: dict[str, str] = {}
    default_targets_by_category: dict[str, set[str]] = {}
    default_categories_by_target: dict[str, set[str]] = {}

    for corpus_index, corpus_value in enumerate(corpora):
        corpus_path = f"$.corpora[{corpus_index}]"
        corpus = expect_object(corpus_value, corpus_path, errors)
        if corpus is None:
            continue

        corpus_name = string_field(corpus, "name", corpus_path, errors)
        fixtures = list_field(corpus, "fixtures", corpus_path, errors)
        if corpus_name is not None:
            if corpus_name in corpus_names:
                errors.append(
                    f"{corpus_path}.name: duplicate corpus name {corpus_name!r}"
                )
            corpus_names.add(corpus_name)
        if fixtures is None:
            continue
        if not fixtures:
            errors.append(f"{corpus_path}.fixtures: expected at least one fixture")

        fixture_names: set[str] = set()
        case_ids: set[str] = set()

        for fixture_index, fixture_value in enumerate(fixtures):
            fixture_path = f"{corpus_path}.fixtures[{fixture_index}]"
            fixture = expect_object(fixture_value, fixture_path, errors)
            if fixture is None:
                continue

            for required_field in REQUIRED_FIXTURE_FIELDS:
                string_field(fixture, required_field, fixture_path, errors)

            fixture_name = fixture.get("name")
            category = fixture.get("category")
            manifest_fixture_path = fixture.get("path")
            source_sha256 = fixture.get("sourceSha256")
            targets = validate_targets(
                fixture,
                fixture_path,
                errors,
                require_explicit=(
                    default_corpus is not None and corpus_name == default_corpus
                ),
            )
            resolved_fixture_path: Path | None = None

            if isinstance(fixture_name, str) and fixture_name:
                if "::" in fixture_name:
                    errors.append(
                        f"{fixture_path}.name: fixture name must not contain '::'"
                    )
                if fixture_name in fixture_names:
                    errors.append(
                        f"{fixture_path}.name: duplicate fixture name {fixture_name!r}"
                    )
                fixture_names.add(fixture_name)

                for target in targets:
                    case_id = f"{fixture_name}::{target}"
                    if case_id in case_ids:
                        errors.append(
                            f"{fixture_path}.targets: duplicate expanded case "
                            f"{case_id!r}"
                        )
                    case_ids.add(case_id)
                    if corpus_name == default_corpus:
                        default_cases.add(case_id)
                        if isinstance(category, str) and category:
                            default_targets_by_category.setdefault(category, set()).add(
                                target
                            )
                            default_categories_by_target.setdefault(target, set()).add(
                                category
                            )

            if isinstance(manifest_fixture_path, str) and manifest_fixture_path:
                resolved_fixture_path = validate_fixture_path(
                    root, manifest_fixture_path, f"{fixture_path}.path", errors
                )

            parsed_source_sha256: str | None = None
            if "sourceSha256" in fixture:
                parsed_source_sha256 = validate_source_sha256(
                    resolved_fixture_path,
                    source_sha256,
                    f"{fixture_path}.sourceSha256",
                    errors,
                )

            if (
                corpus_name == default_corpus
                and isinstance(fixture_name, str)
                and fixture_name
                and parsed_source_sha256 is not None
            ):
                previous_fixture = default_source_hashes.get(parsed_source_sha256)
                if previous_fixture is not None:
                    errors.append(
                        f"{fixture_path}.sourceSha256: duplicate fixture source "
                        f"hash {parsed_source_sha256!r}; already used by "
                        f"{previous_fixture!r}"
                    )
                else:
                    default_source_hashes[parsed_source_sha256] = fixture_name

            if corpus_name == default_corpus and isinstance(category, str) and category:
                default_categories.add(category)

    if default_corpus is not None and default_corpus not in corpus_names:
        errors.append(
            "$.defaultCorpus: default corpus "
            f"{default_corpus!r} is not defined in corpora"
        )

    if default_corpus == DEFAULT_CORPUS and default_corpus in corpus_names:
        expected = set(REQUIRED_MILESTONE6_CATEGORIES)
        missing = sorted(expected - default_categories)
        extra = sorted(default_categories - expected)
        for category in missing:
            errors.append(
                f"$.corpora[{default_corpus}].fixtures: missing Milestone 6 "
                f"category {category!r}"
            )
        for category in extra:
            errors.append(
                f"$.corpora[{default_corpus}].fixtures: unexpected Milestone 6 "
                f"category {category!r}"
            )

        expected_cases = set(EXPECTED_MILESTONE6_CASES)
        missing_cases = sorted(expected_cases - default_cases)
        extra_cases = sorted(default_cases - expected_cases)
        for case_id in missing_cases:
            errors.append(
                f"$.corpora[{default_corpus}].fixtures: missing Milestone 6 "
                f"expanded case {case_id!r}"
            )
        for case_id in extra_cases:
            errors.append(
                f"$.corpora[{default_corpus}].fixtures: unexpected Milestone 6 "
                f"expanded case {case_id!r}"
            )

        validate_required_coverage_cases(
            coverage_rules,
            default_targets_by_category,
            default_categories_by_target,
            errors,
        )

    return errors


def valid_self_test_manifest() -> dict[str, Any]:
    fixtures = []
    for name, path, category, targets in EXPECTED_MILESTONE6_FIXTURES:
        fixture: dict[str, Any] = {
            "name": name,
            "path": path,
            "category": category,
            "description": f"Self-test fixture for {category}.",
            "targets": list(targets),
        }
        fixtures.append(fixture)
    return {
        "schemaVersion": SCHEMA_VERSION,
        "defaultCorpus": DEFAULT_CORPUS,
        "requiredCategories": list(REQUIRED_MILESTONE6_CATEGORIES),
        "requiredCoverage": [
            {
                "name": rule["name"],
                "description": f"Self-test coverage rule for {rule['name']}.",
                "reportPolicy": rule["reportPolicy"],
                "packageMode": rule["packageMode"],
                "coverage": rule["coverage"],
                "targets": list(rule["targets"]),
                "categories": list(rule["categories"]),
                "artifactKinds": list(rule["artifactKinds"]),
                "summaryFields": list(rule["summaryFields"]),
            }
            for rule in REQUIRED_MILESTONE6_COVERAGE_RULES
        ],
        "corpora": [
            {
                "name": DEFAULT_CORPUS,
                "fixtures": fixtures,
            }
        ],
    }


def write_self_test_fixtures(root: Path, manifest: dict[str, Any]) -> None:
    for corpus in manifest["corpora"]:
        for fixture in corpus["fixtures"]:
            fixture_path = root / fixture["path"]
            fixture_path.parent.mkdir(parents=True, exist_ok=True)
            fixture_path.write_text(
                f"// performance manifest self-test: {fixture['name']}\n",
                encoding="utf-8",
            )


def populate_self_test_source_hashes(root: Path, manifest: dict[str, Any]) -> None:
    for corpus in manifest["corpora"]:
        for fixture in corpus["fixtures"]:
            fixture["sourceSha256"] = fixture_source_sha256(root / fixture["path"])


def clone_manifest(manifest: dict[str, Any]) -> dict[str, Any]:
    return copy.deepcopy(manifest)


def expect_valid(root: Path, manifest: dict[str, Any], label: str) -> None:
    errors = validate_manifest(root, manifest)
    if errors:
        raise CheckError(f"self-test {label}: expected valid manifest, got {errors!r}")


def expect_invalid(
    root: Path, manifest: dict[str, Any], label: str, expected_error: str
) -> None:
    errors = validate_manifest(root, manifest)
    if not errors:
        raise CheckError(f"self-test {label}: expected validation failure")
    joined = "\n".join(errors)
    if expected_error not in joined:
        raise CheckError(
            f"self-test {label}: expected {expected_error!r} in errors, got {errors!r}"
        )


def run_self_test() -> None:
    with tempfile.TemporaryDirectory(
        prefix="crossgl-performance-corpus-manifest-self-test-"
    ) as temp:
        root = Path(temp)
        manifest = valid_self_test_manifest()
        write_self_test_fixtures(root, manifest)
        populate_self_test_source_hashes(root, manifest)
        expect_valid(root, manifest, "valid")

        normalized_newlines = clone_manifest(manifest)
        normalized_fixture = (
            root / normalized_newlines["corpora"][0]["fixtures"][0]["path"]
        )
        lf_hash = normalized_newlines["corpora"][0]["fixtures"][0]["sourceSha256"]
        lf_source = normalized_fixture.read_text(encoding="utf-8")
        crlf_source = lf_source.replace("\n", "\r\n").encode("utf-8")
        normalized_fixture.write_bytes(crlf_source)
        if fixture_source_sha256(normalized_fixture) != lf_hash:
            raise CheckError(
                "self-test normalized-newlines: CRLF fixture hash did not match LF hash"
            )
        expect_valid(root, normalized_newlines, "normalized-newlines")

        missing_field = clone_manifest(manifest)
        del missing_field["corpora"][0]["fixtures"][0]["path"]
        expect_invalid(root, missing_field, "missing-field", ".path")

        missing_hash = clone_manifest(manifest)
        del missing_hash["corpora"][0]["fixtures"][0]["sourceSha256"]
        expect_invalid(root, missing_hash, "missing-source-hash", ".sourceSha256")

        missing_targets = clone_manifest(manifest)
        del missing_targets["corpora"][0]["fixtures"][1]["targets"]
        expect_invalid(
            root,
            missing_targets,
            "missing-targets",
            "default corpus fixtures must declare target coverage explicitly",
        )

        missing_required_categories = clone_manifest(manifest)
        del missing_required_categories["requiredCategories"]
        expect_invalid(
            root,
            missing_required_categories,
            "missing-required-categories",
            "$.requiredCategories",
        )

        missing_required_category = clone_manifest(manifest)
        missing_required_category["requiredCategories"].remove("atomics")
        expect_invalid(
            root,
            missing_required_category,
            "missing-required-category",
            "$.requiredCategories: missing category 'atomics'",
        )

        extra_required_category = clone_manifest(manifest)
        extra_required_category["requiredCategories"].append("ray-tracing")
        expect_invalid(
            root,
            extra_required_category,
            "unexpected-required-category",
            "$.requiredCategories: unexpected category 'ray-tracing'",
        )

        unordered_required_categories = clone_manifest(manifest)
        unordered_required_categories["requiredCategories"] = list(
            reversed(unordered_required_categories["requiredCategories"])
        )
        expect_invalid(
            root,
            unordered_required_categories,
            "unordered-required-categories",
            "$.requiredCategories: expected canonical category order",
        )

        missing_required_coverage = clone_manifest(manifest)
        del missing_required_coverage["requiredCoverage"]
        expect_invalid(
            root,
            missing_required_coverage,
            "missing-required-coverage",
            "$.requiredCoverage",
        )

        missing_native_coverage_rule = clone_manifest(manifest)
        missing_native_coverage_rule["requiredCoverage"] = [
            rule
            for rule in missing_native_coverage_rule["requiredCoverage"]
            if rule["name"] != "native-optimization-evidence"
        ]
        expect_invalid(
            root,
            missing_native_coverage_rule,
            "missing-native-coverage-rule",
            "missing required coverage rule 'native-optimization-evidence'",
        )

        missing_source_coverage_rule = clone_manifest(manifest)
        missing_source_coverage_rule["requiredCoverage"] = [
            rule
            for rule in missing_source_coverage_rule["requiredCoverage"]
            if rule["name"] != "source-package-artifacts"
        ]
        expect_invalid(
            root,
            missing_source_coverage_rule,
            "missing-source-coverage-rule",
            "missing required coverage rule 'source-package-artifacts'",
        )

        stale_native_summary_fields = clone_manifest(manifest)
        stale_native_summary_fields["requiredCoverage"][1]["summaryFields"] = [
            "nativeOptimizationEvidence"
        ]
        expect_invalid(
            root,
            stale_native_summary_fields,
            "stale-native-summary-fields",
            "expected canonical coverage values",
        )

        stale_hash = clone_manifest(manifest)
        stale_hash["corpora"][0]["fixtures"][0]["sourceSha256"] = "0" * 64
        expect_invalid(
            root,
            stale_hash,
            "stale-source-hash",
            "expected fixture source SHA-256",
        )

        duplicate_source_hash = clone_manifest(manifest)
        duplicate_source_hash["corpora"][0]["fixtures"][1]["path"] = (
            duplicate_source_hash["corpora"][0]["fixtures"][0]["path"]
        )
        duplicate_source_hash["corpora"][0]["fixtures"][1]["sourceSha256"] = (
            duplicate_source_hash["corpora"][0]["fixtures"][0]["sourceSha256"]
        )
        expect_invalid(
            root,
            duplicate_source_hash,
            "duplicate-source-hash",
            "duplicate fixture source hash",
        )

        duplicate_fixture = clone_manifest(manifest)
        duplicate_fixture["corpora"][0]["fixtures"][1]["name"] = duplicate_fixture[
            "corpora"
        ][0]["fixtures"][0]["name"]
        expect_invalid(
            root,
            duplicate_fixture,
            "duplicate-fixture-name",
            "duplicate fixture name",
        )

        unknown_target = clone_manifest(manifest)
        unknown_target["corpora"][0]["fixtures"][0]["targets"] = ["directx", "webgpu"]
        expect_invalid(
            root, unknown_target, "unknown-target", "unknown target 'webgpu'"
        )

        duplicate_target = clone_manifest(manifest)
        duplicate_target["corpora"][0]["fixtures"][0]["targets"] = [
            "directx",
            "directx",
        ]
        expect_invalid(
            root,
            duplicate_target,
            "duplicate-expanded-case",
            "duplicate expanded case",
        )

        missing_fixture_path = clone_manifest(manifest)
        missing_fixture_path["corpora"][0]["fixtures"][0]["path"] = (
            "tests/fixtures/does-not-exist.cgl"
        )
        expect_invalid(
            root,
            missing_fixture_path,
            "missing-fixture-path",
            "fixture path does not exist",
        )

        missing_category = clone_manifest(manifest)
        missing_category["corpora"][0]["fixtures"][1]["category"] = "new-category"
        expect_invalid(
            root,
            missing_category,
            "missing-category",
            "missing Milestone 6 category",
        )

        for category in REQUIRED_MILESTONE6_CATEGORIES:
            category_omission = clone_manifest(manifest)
            category_omission["corpora"][0]["fixtures"] = [
                fixture
                for fixture in category_omission["corpora"][0]["fixtures"]
                if fixture["category"] != category
            ]
            expect_invalid(
                root,
                category_omission,
                f"missing-category-{category}",
                f"missing Milestone 6 category {category!r}",
            )

        missing_case = clone_manifest(manifest)
        missing_case["corpora"][0]["fixtures"][0]["targets"] = ["directx", "opengl"]
        expect_invalid(
            root,
            missing_case,
            "missing-expanded-case",
            "missing Milestone 6 expanded case",
        )

        missing_native_coverage = clone_manifest(manifest)
        missing_native_coverage["corpora"][0]["fixtures"][0]["targets"] = [
            "directx",
            "opengl",
        ]
        missing_native_coverage["corpora"][0]["fixtures"] = [
            fixture
            for fixture in missing_native_coverage["corpora"][0]["fixtures"]
            if fixture["name"] != "metal-storage-buffer-folded-descriptor-array"
        ]
        expect_invalid(
            root,
            missing_native_coverage,
            "missing-native-coverage",
            "coverage rule 'native-optimization-evidence' missing native "
            "coverage for category 'storage-buffers'",
        )

        missing_source_package_coverage = clone_manifest(manifest)
        missing_source_package_coverage["corpora"][0]["fixtures"][0]["targets"] = [
            "directx",
            "vulkan",
        ]
        expect_invalid(
            root,
            missing_source_package_coverage,
            "missing-source-package-coverage",
            "coverage rule 'source-package-artifacts' missing source-package "
            "coverage for category 'storage-buffers' on target 'opengl'",
        )

        extra_case = clone_manifest(manifest)
        extra_case["corpora"][0]["fixtures"][1]["targets"] = [
            "directx",
            "opengl",
            "metal",
        ]
        expect_invalid(
            root,
            extra_case,
            "unexpected-expanded-case",
            "unexpected Milestone 6 expanded case",
        )

        duplicate_corpus = clone_manifest(manifest)
        duplicate_corpus["corpora"].append(clone_manifest(manifest)["corpora"][0])
        expect_invalid(
            root,
            duplicate_corpus,
            "duplicate-corpus",
            "duplicate corpus name",
        )

        bad_default = clone_manifest(manifest)
        bad_default["defaultCorpus"] = "not-defined"
        expect_invalid(
            root,
            bad_default,
            "bad-default-corpus",
            "is not defined in corpora",
        )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--root",
        default=Path(__file__).resolve().parents[1],
        type=Path,
        help="CrossGL-Compiler repository root",
    )
    parser.add_argument(
        "--manifest",
        type=Path,
        help=f"Manifest path to validate; defaults to {rel(MANIFEST_PATH)}",
    )
    parser.add_argument(
        "--self-test",
        action="store_true",
        help="Run in-memory checker self-tests instead of validating the repository",
    )
    args = parser.parse_args()

    if args.self_test:
        try:
            run_self_test()
        except CheckError as exc:
            print(
                f"performance corpus manifest self-test failed: {exc}", file=sys.stderr
            )
            return 1
        print("validated performance corpus manifest checker self-test")
        return 0

    root = args.root.resolve()
    manifest_path = args.manifest or (root / MANIFEST_PATH)
    if not manifest_path.is_absolute():
        manifest_path = root / manifest_path

    try:
        payload = load_json(manifest_path)
    except OSError as exc:
        print(
            f"performance corpus manifest check failed: could not read {manifest_path}: "
            f"{exc}",
            file=sys.stderr,
        )
        return 1
    except json.JSONDecodeError as exc:
        print(
            "performance corpus manifest check failed: "
            f"invalid JSON at line {exc.lineno} column {exc.colno}",
            file=sys.stderr,
        )
        return 1

    errors = validate_manifest(root, payload)
    if errors:
        print("performance corpus manifest check failed:", file=sys.stderr)
        for error in errors:
            print(f"  - {error}", file=sys.stderr)
        return 1

    print(f"validated performance corpus manifest: {rel(manifest_path)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
