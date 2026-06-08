#!/usr/bin/env python3
"""Check cglc language feature report CLI output."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any


SOURCE_LOCATION_FIELDS = (
    "file",
    "line",
    "column",
    "offset",
    "length",
    "endLine",
    "endColumn",
    "endOffset",
)

SNAPSHOT_AGGREGATE_FEATURES = {
    "resources": {
        "resource.storage-image-types",
        "resource.buffer-types",
        "resource.uav-buffer-types",
        "resource.sampler-state-types",
        "resource.access-metadata",
        "resource.descriptor-index-metadata",
        "resource.image-format-metadata",
    },
    "memory": {
        "memory.address-spaces",
        "memory.layout-metadata",
    },
    "layout": {
        "layout.builtin-semantics",
        "layout.metadata-single-values",
        "layout.metadata-aliases",
        "layout.metadata-multi-values",
        "layout.interpolation-metadata",
        "layout.stage-layout-entries",
    },
}


def normalize_text(text: str) -> str:
    return text.replace("\r\n", "\n").replace("\r", "\n")


def sha256_text(text: str) -> str:
    return hashlib.sha256(normalize_text(text).encode("utf-8")).hexdigest()


def load_schema(root: Path) -> dict[str, Any]:
    return json.loads(
        (root / "docs/schemas/language-feature-report-v1.schema.json").read_text(
            encoding="utf-8"
        )
    )


def validate_report(root: Path, report: dict[str, Any]) -> None:
    sys.path.insert(0, str(root / "tools"))
    from json_schema_semantics import validate_semantics
    from validate_json_schema import SchemaError
    from validate_json_schema import validate as validate_json_schema

    schema = load_schema(root)
    try:
        validate_json_schema(report, schema, schema)
    except SchemaError as exc:
        raise AssertionError(f"schema validation failed: {exc}") from exc

    semantic_errors = validate_semantics(report, schema)
    if semantic_errors:
        raise AssertionError(
            "semantic validation failed:\n" + "\n".join(semantic_errors)
        )

    pointer_errors = validate_evidence_paths(root, report)
    if pointer_errors:
        raise AssertionError(
            "evidence pointer validation failed:\n" + "\n".join(pointer_errors)
        )


def validate_evidence_paths(root: Path, report: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    for index, record in enumerate(report.get("evidence", [])):
        if not isinstance(record, dict):
            continue
        path = record.get("path")
        if not isinstance(path, str) or not path:
            continue
        if "\\" in path or path.startswith("/") or ".." in Path(path).parts:
            errors.append(
                f"$.evidence[{index}].path is not repo-relative POSIX: {path}"
            )
            continue
        if not (root / path).exists():
            errors.append(f"$.evidence[{index}].path does not exist: {path}")
    return errors


def run_report(cglc: Path, root: Path, source: Path) -> dict[str, Any]:
    result = subprocess.run(
        [
            str(cglc),
            "language-feature-report",
            str(source),
            "--root",
            str(root),
        ],
        cwd=root,
        text=True,
        capture_output=True,
        check=False,
    )
    if result.returncode != 0:
        raise AssertionError(
            f"cglc language-feature-report failed with {result.returncode}\n"
            f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
        )
    try:
        report = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise AssertionError(f"report stdout was not JSON: {exc}") from exc
    if not isinstance(report, dict):
        raise AssertionError("report must be a JSON object")
    validate_report(root, report)
    validate_source_locations(report)
    return report


def features(report: dict[str, Any], group: str) -> list[dict[str, Any]]:
    return report["resourceMemoryLayoutFeatures"][group]


def feature_ids(report: dict[str, Any], group: str) -> set[str]:
    return {feature["featureId"] for feature in features(report, group)}


def feature_by_id(
    report: dict[str, Any], group: str, feature_id: str
) -> dict[str, Any]:
    features = report["resourceMemoryLayoutFeatures"][group]
    for feature in features:
        if feature["featureId"] == feature_id:
            return feature
    raise AssertionError(f"missing {group} feature {feature_id!r}")


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def fixture_evidence(report: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        record
        for record in report["evidence"]
        if isinstance(record, dict) and record.get("kind") == "fixture"
    ]


def location_key(location: dict[str, Any]) -> tuple[Any, ...]:
    return (
        location["file"],
        location["offset"],
        location["endOffset"],
        location["line"],
        location["column"],
        location["endLine"],
        location["endColumn"],
        location["length"],
    )


def validate_source_locations(report: dict[str, Any]) -> None:
    source_path = report["module"]["sourcePath"]
    for group in ("resources", "memory", "layout"):
        for feature in features(report, group):
            path = f"{group}.{feature['featureId']}.sourceLocations"
            locations = feature["sourceLocations"]
            keys = []
            for location in locations:
                require(
                    all(field in location for field in SOURCE_LOCATION_FIELDS),
                    f"{path} entry missing required source location fields",
                )
                require(
                    location["file"] == source_path,
                    f"{path} should use the module repo-relative source path",
                )
                require(
                    not location["file"].startswith("/")
                    and "\\" not in location["file"],
                    f"{path} file should be repo-relative POSIX",
                )
                require(location["line"] >= 1, f"{path} line should be positive")
                require(location["column"] >= 1, f"{path} column should be positive")
                require(location["endLine"] >= 1, f"{path} endLine should be positive")
                require(
                    location["endColumn"] >= 1,
                    f"{path} endColumn should be positive",
                )
                keys.append(location_key(location))
            require(
                keys == sorted(set(keys)),
                f"{path} should be sorted and deduplicated",
            )


def require_feature_source_location(
    report: dict[str, Any], group: str, feature_id: str
) -> None:
    feature = feature_by_id(report, group, feature_id)
    require(
        bool(feature["sourceLocations"]),
        f"{group} feature {feature_id!r} should have a source location",
    )


def source_lines_for_feature(
    report: dict[str, Any], group: str, feature_id: str, source_text: str
) -> list[str]:
    source_lines = normalize_text(source_text).splitlines()
    feature = feature_by_id(report, group, feature_id)
    lines: list[str] = []
    for location in feature["sourceLocations"]:
        line_index = location["line"] - 1
        require(
            0 <= line_index < len(source_lines),
            f"{group} feature {feature_id!r} source line should be in range",
        )
        lines.append(source_lines[line_index])
    return lines


def require_feature_lines_include(
    report: dict[str, Any],
    group: str,
    feature_id: str,
    source_text: str,
    expected_fragments: set[str],
) -> None:
    lines = source_lines_for_feature(report, group, feature_id, source_text)
    require(lines, f"{group} feature {feature_id!r} should have source lines")
    for fragment in expected_fragments:
        require(
            any(fragment in line for line in lines),
            f"{group} feature {feature_id!r} should cite source containing "
            f"{fragment!r}",
        )


def require_feature_status(
    report: dict[str, Any], group: str, feature_id: str, status: str
) -> None:
    feature = feature_by_id(report, group, feature_id)
    require(
        feature["status"] == status,
        f"{group} feature {feature_id!r} should have status {status!r}",
    )


def require_snapshot_aggregate_features(report: dict[str, Any]) -> None:
    for group, expected in SNAPSHOT_AGGREGATE_FEATURES.items():
        missing = sorted(expected.difference(feature_ids(report, group)))
        require(
            not missing,
            f"missing snapshot-backed aggregate {group} features: {missing}",
        )
        for feature_id in expected:
            feature = feature_by_id(report, group, feature_id)
            require(
                feature["status"] == "cross-tl-inventory-only",
                f"{group} snapshot aggregate {feature_id!r} should be "
                "CrossTL inventory only, not native accepted source",
            )


def check_resource_shader(cglc: Path, root: Path) -> None:
    source = root / "tests/fixtures/ResourceShader.cgl"
    report = run_report(cglc, root, source)

    require(report["kind"] == "crossgl.languageFeatureReport", "unexpected kind")
    require(report["module"]["moduleId"] == "ResourceShader", "module id mismatch")
    require(
        report["module"]["sourcePath"] == "tests/fixtures/ResourceShader.cgl",
        "source path should be root-relative",
    )
    require(
        report["module"]["sourceSha256"]
        == sha256_text(source.read_text(encoding="utf-8")),
        "source hash mismatch",
    )
    require(
        report["module"]["stageEntryPoints"]
        == [{"stage": "compute", "entryPoint": "main"}],
        "stage entry points mismatch",
    )

    resource_features = feature_ids(report, "resources")
    memory_features = feature_ids(report, "memory")
    layout_features = feature_ids(report, "layout")
    require("resource.uniform-buffer" in resource_features, "missing uniform fact")
    require("resource.storage-buffer" in resource_features, "missing buffer fact")
    require("resource.texture" in resource_features, "missing texture fact")
    require("resource.sampler" in resource_features, "missing sampler fact")
    require(
        "memory.workgroup-shared" in memory_features,
        "missing workgroup shared fact",
    )
    require("layout.local-size" in layout_features, "missing local size fact")
    require("layout.set-binding" in layout_features, "missing set/binding fact")
    require_feature_source_location(report, "resources", "resource.storage-buffer")
    require_feature_source_location(report, "memory", "memory.workgroup-shared")
    require_feature_source_location(report, "layout", "layout.set-binding")
    require_feature_source_location(report, "layout", "layout.local-size")
    require_snapshot_aggregate_features(report)
    require(
        report["compatibilityBucketSummary"]["cross-tl-inventory-only"]
        == sum(len(features) for features in SNAPSHOT_AGGREGATE_FEATURES.values()),
        "snapshot inventory bucket count mismatch",
    )
    require(report["generation"]["tool"] == "cglc", "generation tool mismatch")
    require(
        report["generation"]["command"][1] == "language-feature-report",
        "generation command mismatch",
    )
    require(
        any(
            record["id"] == "fixture:tests/fixtures/ResourceShader.cgl"
            and record["path"] == "tests/fixtures/ResourceShader.cgl"
            for record in fixture_evidence(report)
        ),
        "ordinary fixture evidence id should preserve the source path",
    )


def check_storage_image_descriptor_array_shader(
    cglc: Path,
    root: Path,
    fixture_name: str,
    expected_storage_image_declarations: set[str],
    expected_format_declarations: set[str],
    expected_nonuniform_uses: set[str],
    expected_memory_features: set[str] | None = None,
    expected_atomic_uses: set[str] | None = None,
) -> None:
    source = root / "tests/fixtures" / fixture_name
    source_text = source.read_text(encoding="utf-8")
    report = run_report(cglc, root, source)

    require(
        report["module"]["sourcePath"] == f"tests/fixtures/{fixture_name}",
        "storage image fixture source path should be root-relative",
    )
    require(
        report["module"]["sourceSha256"] == sha256_text(source_text),
        "storage image fixture source hash mismatch",
    )

    expected_resource_features = {
        "resource.storage-image": "package-supported",
        "resource.descriptor-array": "package-supported",
        "resource.nonuniform-descriptor-index": "package-supported",
        "resource.storage-image-access-qualifier": "accepted-source",
    }
    expected_layout_features = {
        "layout.storage-image-format",
        "layout.set-binding",
        "layout.fixed-array",
    }
    expected_memory_features = expected_memory_features or set()

    for feature_id, status in expected_resource_features.items():
        require_feature_status(report, "resources", feature_id, status)
        require_feature_source_location(report, "resources", feature_id)
    for feature_id in expected_memory_features:
        require_feature_status(report, "memory", feature_id, "package-supported")
        require_feature_source_location(report, "memory", feature_id)
    for feature_id in expected_layout_features:
        require_feature_status(report, "layout", feature_id, "accepted-source")
        require_feature_source_location(report, "layout", feature_id)

    for feature_id in {
        "resource.storage-image",
        "resource.descriptor-array",
        "resource.storage-image-access-qualifier",
    }:
        require_feature_lines_include(
            report,
            "resources",
            feature_id,
            source_text,
            expected_storage_image_declarations,
        )
    require_feature_lines_include(
        report,
        "layout",
        "layout.storage-image-format",
        source_text,
        expected_format_declarations,
    )
    require_feature_lines_include(
        report,
        "resources",
        "resource.nonuniform-descriptor-index",
        source_text,
        expected_nonuniform_uses,
    )
    if expected_atomic_uses is not None:
        require_feature_lines_include(
            report,
            "memory",
            "memory.storage-image-atomic",
            source_text,
            expected_atomic_uses,
        )

    require(
        any(
            record["id"] == f"fixture:tests/fixtures/{fixture_name}"
            and record["path"] == f"tests/fixtures/{fixture_name}"
            for record in fixture_evidence(report)
        ),
        "storage image fixture evidence id should preserve the source path",
    )


def check_spaced_source_path_schema(cglc: Path, root: Path) -> None:
    fixture_text = (root / "tests/fixtures/ResourceShader.cgl").read_text(
        encoding="utf-8"
    )
    with tempfile.TemporaryDirectory(
        dir=root / "tests/language-feature-report",
        prefix="path with spaces ",
    ) as temp_dir:
        source = Path(temp_dir) / "Resource Shader.cgl"
        source.write_text(fixture_text, encoding="utf-8")
        report = run_report(cglc, root, source)

        source_path = source.relative_to(root).as_posix()
        require(
            report["module"]["sourcePath"] == source_path,
            "spaced source path should stay unchanged as display path",
        )
        fixtures = fixture_evidence(report)
        require(len(fixtures) == 1, "expected one fixture evidence record")
        fixture = fixtures[0]
        require(fixture["path"] == source_path, "fixture path should be display path")
        require(
            fixture["id"] != f"fixture:{source_path}",
            "spaced source path must not be used raw as an evidence id",
        )
        require(
            re.match(
                r"^fixture:[A-Za-z0-9][A-Za-z0-9_.:/-]*-[0-9a-f]{12}$",
                fixture["id"],
            )
            is not None,
            f"spaced source evidence id was not schema-safe: {fixture['id']!r}",
        )


def check_target_limited_shader(cglc: Path, root: Path) -> None:
    source = root / "tests/fixtures/RuntimeResourceArrayUnsupportedShader.cgl"
    report = run_report(cglc, root, source)

    gate_ids = {gate["gateId"] for gate in report["targetFeatureGates"]}
    require("target.resource-arrays" in gate_ids, "missing resource-array gate")
    resource_array_gate = next(
        gate
        for gate in report["targetFeatureGates"]
        if gate["gateId"] == "target.resource-arrays"
    )
    target = resource_array_gate["target"]
    evidence_ids = set(resource_array_gate["evidenceIds"])
    require(
        any(
            evidence_id.startswith(f"target-contract:{target}.package-mode.")
            for evidence_id in evidence_ids
        ),
        "target gate should cite projection package-mode evidence",
    )
    require(
        f"target-contract:{target}.support.unsupported" in evidence_ids,
        "target gate should cite unsupported projection support evidence",
    )
    unsupported_facts = report["facts"]["unsupported"]
    require(unsupported_facts, "expected target unsupported fact")
    require(
        any(
            fact["classification"] == "target.unsupported" for fact in unsupported_facts
        ),
        "missing target.unsupported classification",
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", required=True, type=Path)
    parser.add_argument("--cglc", required=True, type=Path)
    args = parser.parse_args()

    root = args.root.resolve()
    check_resource_shader(args.cglc.resolve(), root)
    check_storage_image_descriptor_array_shader(
        args.cglc.resolve(),
        root,
        "StorageImageExplicitFormatDescriptorArrayShader.cgl",
        expected_storage_image_declarations={
            "readonly uniform image2D colorImages[IMAGE_COUNT]",
            "readonly uniform iimage2D labelImages[IMAGE_COUNT]",
            "readonly uniform uimage2DArray maskAtlases[ATLAS_COUNT]",
            "writeonly uniform uimage2DArray outputAtlases[ATLAS_COUNT]",
        },
        expected_format_declarations={
            "binding = 0, format = r32f",
            "binding = 1, format = r32i",
            "binding = 2, format = r32ui",
            "binding = 3, format = r32ui",
        },
        expected_nonuniform_uses={
            "colorImages[nonuniform(imageSlot)]",
            "labelImages[nonuniform(imageSlot)]",
            "maskAtlases[nonuniform(atlasSlot)]",
            "outputAtlases[nonuniform(atlasSlot)]",
        },
    )
    check_storage_image_descriptor_array_shader(
        args.cglc.resolve(),
        root,
        "StorageImageAtomicDescriptorArrayShader.cgl",
        expected_storage_image_declarations={
            "readwrite uniform iimage2D signedCounters[IMAGE_COUNT]",
            "readwrite uniform uimage2D unsignedCounters[IMAGE_COUNT]",
            "readwrite uniform iimage2DArray signedAtlases[IMAGE_COUNT]",
            "readwrite uniform uimage2DArray unsignedAtlases[IMAGE_COUNT]",
        },
        expected_format_declarations={
            "binding = 1, format = r32i",
            "binding = 2, format = r32ui",
            "binding = 3, format = r32i",
            "binding = 4, format = r32ui",
        },
        expected_nonuniform_uses={
            "signedCounters[nonuniform(slot)]",
            "unsignedCounters[nonuniform(slot)]",
            "signedAtlases[nonuniform(slot)]",
            "unsignedAtlases[nonuniform(slot)]",
        },
        expected_memory_features={"memory.storage-image-atomic"},
        expected_atomic_uses={
            "imageAtomicAdd",
            "imageAtomicMin",
            "imageAtomicMax",
            "imageAtomicAnd",
            "imageAtomicOr",
            "imageAtomicExchange",
            "imageAtomicXor",
        },
    )
    check_spaced_source_path_schema(args.cglc.resolve(), root)
    check_target_limited_shader(args.cglc.resolve(), root)
    print("cglc language feature report CLI OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
