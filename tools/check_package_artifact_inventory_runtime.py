#!/usr/bin/env python3
"""Check package inspect exposes a runtime-loadable artifact inventory."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import tempfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path, PurePosixPath
from typing import Any

from check_package_integrity_fixtures import (
    TARGET_ARTIFACT_PATHS,
    VULKAN_DISASSEMBLY_PATH,
    add_native_artifact_descriptor,
    make_package,
    mark_native_artifact_validated,
    rewrite_manifest,
)
from package_fixture_json_contracts import (
    expected_manifest_artifact_names,
    expected_summary_native_binary_status,
    manifest_artifacts,
)


ROOT_FILE_PATHS = {
    "manifest": "manifest.json",
    "reflection": "reflection.json",
    "diagnostics": "diagnostics.json",
}
CROSSGL_PACKAGE_ARTIFACT_INVENTORY_RUNTIME_JOBS = (
    "CROSSGL_PACKAGE_ARTIFACT_INVENTORY_RUNTIME_JOBS"
)

CASE_SPECS = (
    {
        "name": "runtime-directx-source-planned",
        "target": "directx",
        "status": "planned",
    },
    {
        "name": "runtime-directx-source-emitted",
        "target": "directx",
        "status": "emitted",
    },
    {"name": "runtime-opengl-source-planned", "target": "opengl", "status": "planned"},
    {
        "name": "runtime-opengl-source-validated",
        "target": "opengl",
        "status": "validated",
    },
    {"name": "runtime-metal-native", "target": "metal", "status": "planned"},
    {"name": "runtime-vulkan-native", "target": "vulkan", "status": "planned"},
    {
        "name": "runtime-directx-descriptor-planned",
        "target": "directx",
        "status": "planned",
        "descriptor": "default",
    },
    {
        "name": "runtime-directx-descriptor-emitted",
        "target": "directx",
        "status": "emitted",
        "descriptor": "optimized",
    },
    {
        "name": "runtime-opengl-descriptor-validated",
        "target": "opengl",
        "status": "validated",
        "descriptor": "validated",
    },
    {
        "name": "runtime-metal-descriptor",
        "target": "metal",
        "status": "planned",
        "descriptor": "validated",
    },
    {
        "name": "runtime-vulkan-descriptor",
        "target": "vulkan",
        "status": "planned",
        "descriptor": "validated",
    },
)

HEX_DIGITS = set("0123456789abcdef")
SOURCE_PACKAGE_TARGETS = {"directx", "opengl"}
NATIVE_ARTIFACT_BINARY_KINDS = {
    "metal": "metal.metallib",
    "vulkan": "vulkan.spirv-module",
    "directx": "directx.dxil",
    "opengl": "opengl.source",
}
NATIVE_ARTIFACT_DESCRIPTOR_CHECKS = (
    "descriptorIdentityMatchesContract",
    "targetMatchesPackage",
    "nativeBinaryStatusMatchesPackage",
    "sourcePathMatchesManifest",
    "sourceHashMatchesFile",
    "artifactPathMatchesManifest",
    "artifactHashMatchesFile",
    "sizeBytesMatchesFile",
    "validationStatusMatchesNativeStatus",
)
VULKAN_NATIVE_PROFILE_CHECKS = (
    "targetMatchesPackage",
    "moduleMatchesPackage",
    "nativeBinaryMatchesManifest",
    "backendAssemblyMatchesManifest",
    "emittedDisassemblyExists",
    "spirvProfilePresent",
)
DIRECTX_OPTIMIZATION_EVIDENCE = {
    "requestedLevel": "O2",
    "effectiveLevel": "O2",
    "policy": "crossgl-to-dxc-optimization-map",
    "status": "metadata-only",
    "tool": "dxc",
    "toolFlag": "-O3",
    "debugInfo": False,
    "profile": "cs_6_0",
    "flags": ["-O3"],
    "evidenceSource": {
        "kind": "compiler-policy",
    },
}


def parse_jobs(value: str | None, label: str) -> int:
    if value is None or value == "":
        return 1
    try:
        jobs = int(value)
    except ValueError as exc:
        raise ValueError(f"{label} must be a positive integer") from exc
    if jobs < 1:
        raise ValueError(f"{label} must be a positive integer")
    return jobs


def run_inspect(cglc: Path, package: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [str(cglc), "package", "inspect", str(package), "--json"],
        check=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )


def fail(errors: list[str], case_name: str, path: str, message: str) -> None:
    errors.append(f"{case_name}: {path}: {message}")


def expect_equal(
    errors: list[str], case_name: str, path: str, actual: Any, expected: Any
) -> None:
    if actual != expected:
        fail(errors, case_name, path, f"expected {expected!r}, got {actual!r}")


def expect_type(
    errors: list[str],
    case_name: str,
    path: str,
    value: Any,
    expected_type: type,
) -> bool:
    if not isinstance(value, expected_type):
        fail(
            errors,
            case_name,
            path,
            f"expected {expected_type.__name__}, got {type(value).__name__}",
        )
        return False
    return True


def records_by_name(
    errors: list[str], case_name: str, path: str, records: Any
) -> dict[str, dict[str, Any]]:
    if not expect_type(errors, case_name, path, records, list):
        return {}

    result: dict[str, dict[str, Any]] = {}
    for index, record in enumerate(records):
        record_path = f"{path}[{index}]"
        if not expect_type(errors, case_name, record_path, record, dict):
            continue
        name = record.get("name")
        if not isinstance(name, str) or not name:
            fail(errors, case_name, f"{record_path}.name", "expected non-empty string")
            continue
        if name in result:
            fail(errors, case_name, record_path, f"duplicate record {name!r}")
            continue
        result[name] = record
    return result


def is_package_relative_path(value: Any) -> bool:
    if not isinstance(value, str) or not value:
        return False
    if "\\" in value or value.startswith("/"):
        return False
    if len(value) >= 2 and value[0].isalpha() and value[1] == ":":
        return False
    parts = PurePosixPath(value).parts
    return all(part not in {"", ".", ".."} for part in parts)


def expect_package_relative_path(
    errors: list[str], case_name: str, path: str, value: Any
) -> None:
    if not is_package_relative_path(value):
        fail(errors, case_name, path, f"expected package-relative path, got {value!r}")


def expect_sha_contract(
    errors: list[str],
    case_name: str,
    path: str,
    record: dict[str, Any],
    exists: bool,
) -> None:
    sha256 = record.get("sha256")
    size_bytes = record.get("sizeBytes")
    if exists:
        if (
            not isinstance(sha256, str)
            or len(sha256) != 64
            or any(character not in HEX_DIGITS for character in sha256)
        ):
            fail(errors, case_name, f"{path}.sha256", "expected lowercase SHA-256")
        if not isinstance(size_bytes, int) or size_bytes <= 0:
            fail(errors, case_name, f"{path}.sizeBytes", "expected positive integer")
    else:
        expect_equal(errors, case_name, f"{path}.sha256", sha256, None)
        expect_equal(errors, case_name, f"{path}.sizeBytes", size_bytes, None)


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_json_file(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, dict):
        return {}
    return payload


def package_relative_file(package: Path, value: Any) -> Path | None:
    if not is_package_relative_path(value):
        return None
    return package / Path(value)


def file_facts(package: Path, value: Any) -> tuple[bool, int | None, str | None]:
    file_path = package_relative_file(package, value)
    if file_path is None or not file_path.is_file():
        return False, None, None
    return True, file_path.stat().st_size, sha256_file(file_path)


def expect_file_fact_contract(
    errors: list[str],
    case_name: str,
    path: str,
    record: dict[str, Any],
    package: Path,
    expected_path: Any,
) -> None:
    exists, size_bytes, sha256 = file_facts(package, expected_path)
    expect_equal(errors, case_name, f"{path}.exists", record.get("exists"), exists)
    expect_equal(
        errors, case_name, f"{path}.sizeBytes", record.get("sizeBytes"), size_bytes
    )
    expect_equal(errors, case_name, f"{path}.sha256", record.get("sha256"), sha256)


def add_directx_optimization_evidence(descriptor: dict[str, Any]) -> None:
    descriptor["optimizationLevel"] = "O2"
    descriptor["optimizationEvidence"] = DIRECTX_OPTIMIZATION_EVIDENCE


def expected_native_artifact_source_name(manifest: dict[str, Any]) -> str:
    if manifest["target"] == "vulkan":
        return "backendAssembly"
    return "backendSource"


def runtime_artifact_role(name: str) -> str:
    if name == "nativeBinary":
        return "native-binary"
    if name == "backendSource":
        return "backend-source"
    if name == "backendAssembly":
        return "backend-assembly"
    if name == "intermediate":
        return "native-intermediate"
    if name == "nativeProfile":
        return "native-profile"
    if name == "nativeArtifactDescriptor":
        return "native-artifact-descriptor"
    if name in {"debugMetadata", "hirSourceMap", "targetExplanation"}:
        return "debug"
    return "declared-artifact"


def check_root_file_inventory(
    errors: list[str],
    case_name: str,
    package: Path,
    payload: dict[str, Any],
) -> dict[str, dict[str, Any]]:
    root_files = records_by_name(
        errors, case_name, "rootFiles", payload.get("rootFiles")
    )
    expect_equal(
        errors,
        case_name,
        "rootFiles.names",
        sorted(root_files),
        sorted(ROOT_FILE_PATHS),
    )

    for name, expected_path in ROOT_FILE_PATHS.items():
        record = root_files.get(name)
        if record is None:
            continue
        record_path = f"rootFiles.{name}"
        expect_equal(
            errors, case_name, f"{record_path}.path", record.get("path"), expected_path
        )
        expect_package_relative_path(
            errors, case_name, f"{record_path}.path", record.get("path")
        )
        expect_equal(
            errors, case_name, f"{record_path}.exists", record.get("exists"), True
        )
        expect_sha_contract(errors, case_name, record_path, record, True)
        expect_file_fact_contract(
            errors, case_name, record_path, record, package, expected_path
        )
        provenance = record.get("provenance")
        if expect_type(
            errors, case_name, f"{record_path}.provenance", provenance, dict
        ):
            expect_equal(
                errors,
                case_name,
                f"{record_path}.provenance.kind",
                provenance.get("kind"),
                "packageRootFile",
            )
            expect_equal(
                errors,
                case_name,
                f"{record_path}.provenance.source",
                provenance.get("source"),
                "packageRoot",
            )
    return root_files


def check_artifact_inventory(
    errors: list[str],
    case_name: str,
    package: Path,
    manifest: dict[str, Any],
    payload: dict[str, Any],
) -> dict[str, dict[str, Any]]:
    artifact_records = records_by_name(
        errors, case_name, "artifacts", payload.get("artifacts")
    )
    expected_names = sorted(expected_manifest_artifact_names(manifest))
    expect_equal(
        errors,
        case_name,
        "artifacts.names",
        sorted(artifact_records),
        expected_names,
    )
    if "nativeBinaryStatus" in artifact_records:
        fail(
            errors,
            case_name,
            "artifacts.nativeBinaryStatus",
            "metadata is not a file artifact",
        )

    for name, expected_path in manifest_artifacts(manifest).items():
        if name == "nativeBinaryStatus":
            continue
        record = artifact_records.get(name)
        if record is None:
            continue
        record_path = f"artifacts.{name}"
        expect_equal(
            errors, case_name, f"{record_path}.path", record.get("path"), expected_path
        )
        expect_package_relative_path(
            errors, case_name, f"{record_path}.path", record.get("path")
        )
        expect_equal(
            errors,
            case_name,
            f"{record_path}.packageRelative",
            record.get("packageRelative"),
            True,
        )
        artifact_exists, _, _ = file_facts(package, expected_path)
        expect_equal(
            errors,
            case_name,
            f"{record_path}.exists",
            record.get("exists"),
            artifact_exists,
        )
        expect_sha_contract(errors, case_name, record_path, record, artifact_exists)
        expect_file_fact_contract(
            errors, case_name, record_path, record, package, expected_path
        )
        provenance = record.get("provenance")
        if expect_type(
            errors, case_name, f"{record_path}.provenance", provenance, dict
        ):
            expect_equal(
                errors,
                case_name,
                f"{record_path}.provenance.kind",
                provenance.get("kind"),
                "manifestArtifact",
            )
            expect_equal(
                errors,
                case_name,
                f"{record_path}.provenance.source",
                provenance.get("source"),
                "manifest.artifacts",
            )
            expect_equal(
                errors,
                case_name,
                f"{record_path}.provenance.manifestKey",
                provenance.get("manifestKey"),
                name,
            )
    return artifact_records


def check_summary_inventory(
    errors: list[str],
    case_name: str,
    manifest: dict[str, Any],
    payload: dict[str, Any],
    artifacts: dict[str, dict[str, Any]],
) -> None:
    summary = payload.get("summary")
    if not expect_type(errors, case_name, "summary", summary, dict):
        return
    expect_equal(
        errors,
        case_name,
        "summary.artifactCount",
        summary.get("artifactCount"),
        len(artifacts),
    )
    expect_equal(
        errors,
        case_name,
        "summary.debugArtifactsPresent",
        summary.get("debugArtifactsPresent"),
        {"debugMetadata", "hirSourceMap"}.issubset(artifacts),
    )
    expect_equal(
        errors,
        case_name,
        "summary.nativeBinaryStatus",
        summary.get("nativeBinaryStatus"),
        expected_summary_native_binary_status(manifest),
    )


def check_native_binary_inventory(
    errors: list[str],
    case_name: str,
    manifest: dict[str, Any],
    payload: dict[str, Any],
    artifacts: dict[str, dict[str, Any]],
) -> None:
    target = manifest["target"]
    manifest_artifact_map = manifest["artifacts"]
    summary = payload.get("summary", {})
    reflection = payload.get("reflection", {})
    native_binary = artifacts.get("nativeBinary")
    if native_binary is None:
        fail(errors, case_name, "artifacts.nativeBinary", "missing runtime artifact")
        return

    expected_path = manifest_artifact_map["nativeBinary"]
    record_path = "artifacts.nativeBinary"
    expect_equal(
        errors,
        case_name,
        f"{record_path}.path",
        native_binary.get("path"),
        expected_path,
    )
    expect_equal(
        errors,
        case_name,
        "reflection.nativeBinary",
        reflection.get("nativeBinary"),
        expected_path,
    )

    summary_status = summary.get("nativeBinaryStatus")
    if target in SOURCE_PACKAGE_TARGETS:
        manifest_status = manifest_artifact_map.get("nativeBinaryStatus")
        expect_equal(
            errors,
            case_name,
            "manifest.artifacts.nativeBinaryStatus",
            manifest_status,
            summary_status,
        )
        expected_exists = manifest_status != "planned"
    else:
        if "nativeBinaryStatus" in manifest_artifact_map:
            fail(
                errors,
                case_name,
                "manifest.artifacts.nativeBinaryStatus",
                "native-only package must not declare source-package status",
            )
        expected_exists = True

    expect_equal(
        errors,
        case_name,
        f"{record_path}.exists",
        native_binary.get("exists"),
        expected_exists,
    )
    expect_sha_contract(
        errors,
        case_name,
        record_path,
        native_binary,
        expected_exists,
    )


def check_vulkan_profile_inventory(
    errors: list[str],
    case_name: str,
    payload: dict[str, Any],
    manifest: dict[str, Any],
    artifacts: dict[str, dict[str, Any]],
) -> None:
    target = manifest["target"]
    profile = payload.get("vulkanNativeProfile")
    if not expect_type(errors, case_name, "vulkanNativeProfile", profile, dict):
        return
    checks = profile.get("checks")
    if not expect_type(errors, case_name, "vulkanNativeProfile.checks", checks, dict):
        checks = {}

    profile_record = artifacts.get("nativeProfile")
    profile_declared = profile_record is not None
    profile_exists = profile_declared and profile_record.get("exists") is True
    is_vulkan = target == "vulkan"

    expect_equal(
        errors,
        case_name,
        "vulkanNativeProfile.applicable",
        profile.get("applicable"),
        is_vulkan,
    )
    expect_equal(
        errors,
        case_name,
        "vulkanNativeProfile.nativeProfileArtifactPresent",
        profile.get("nativeProfileArtifactPresent"),
        profile_declared,
    )
    expect_equal(
        errors,
        case_name,
        "vulkanNativeProfile.nativeProfileExists",
        profile.get("nativeProfileExists"),
        profile_exists,
    )

    if not is_vulkan:
        expect_equal(
            errors,
            case_name,
            "vulkanNativeProfile.health",
            profile.get("health"),
            "not-applicable",
        )
        for check_name in VULKAN_NATIVE_PROFILE_CHECKS:
            expect_equal(
                errors,
                case_name,
                f"vulkanNativeProfile.checks.{check_name}",
                checks.get(check_name),
                None,
            )
        return

    if profile_record is None:
        fail(
            errors,
            case_name,
            "artifacts.nativeProfile",
            "missing Vulkan native profile artifact record",
        )
        return

    expect_equal(
        errors,
        case_name,
        "artifacts.nativeProfile.path",
        profile_record.get("path"),
        manifest["artifacts"]["nativeProfile"],
    )
    expect_equal(
        errors,
        case_name,
        "vulkanNativeProfile.health",
        profile.get("health"),
        "ok",
    )
    expect_equal(
        errors,
        case_name,
        "vulkanNativeProfile.nativeBinary",
        profile.get("nativeBinary"),
        manifest["artifacts"]["nativeBinary"],
    )
    expect_equal(
        errors,
        case_name,
        "vulkanNativeProfile.backendAssembly",
        profile.get("backendAssembly"),
        manifest["artifacts"]["backendAssembly"],
    )
    expect_equal(
        errors,
        case_name,
        "vulkanNativeProfile.disassemblyPath",
        profile.get("disassemblyPath"),
        VULKAN_DISASSEMBLY_PATH,
    )
    expect_package_relative_path(
        errors,
        case_name,
        "vulkanNativeProfile.disassemblyPath",
        profile.get("disassemblyPath"),
    )
    expect_equal(
        errors,
        case_name,
        "vulkanNativeProfile.disassemblyExists",
        profile.get("disassemblyExists"),
        True,
    )
    for check_name in VULKAN_NATIVE_PROFILE_CHECKS:
        expect_equal(
            errors,
            case_name,
            f"vulkanNativeProfile.checks.{check_name}",
            checks.get(check_name),
            True,
        )


def check_native_artifact_descriptor_inventory(
    errors: list[str],
    case_name: str,
    package: Path,
    manifest: dict[str, Any],
    payload: dict[str, Any],
    artifacts: dict[str, dict[str, Any]],
) -> None:
    descriptor = payload.get("nativeArtifactDescriptor")
    if not expect_type(errors, case_name, "nativeArtifactDescriptor", descriptor, dict):
        return
    checks = descriptor.get("checks")
    if not expect_type(
        errors, case_name, "nativeArtifactDescriptor.checks", checks, dict
    ):
        checks = {}

    manifest_artifact_map = manifest["artifacts"]
    descriptor_record = artifacts.get("nativeArtifactDescriptor")
    descriptor_declared = descriptor_record is not None
    descriptor_exists = (
        descriptor_record is not None and descriptor_record.get("exists") is True
    )
    expected_descriptor_path = manifest_artifact_map.get("nativeArtifactDescriptor")

    expect_equal(
        errors,
        case_name,
        "nativeArtifactDescriptor.artifactPresent",
        descriptor.get("artifactPresent"),
        descriptor_declared,
    )
    expect_equal(
        errors,
        case_name,
        "nativeArtifactDescriptor.descriptorExists",
        descriptor.get("descriptorExists"),
        descriptor_exists,
    )
    expect_equal(
        errors,
        case_name,
        "nativeArtifactDescriptor.path",
        descriptor.get("path"),
        expected_descriptor_path,
    )

    if descriptor_record is None:
        expect_equal(
            errors,
            case_name,
            "nativeArtifactDescriptor.health",
            descriptor.get("health"),
            "not-present",
        )
        for check_name in NATIVE_ARTIFACT_DESCRIPTOR_CHECKS:
            expect_equal(
                errors,
                case_name,
                f"nativeArtifactDescriptor.checks.{check_name}",
                checks.get(check_name),
                None,
            )
        return

    target = manifest["target"]
    source_artifact_name = expected_native_artifact_source_name(manifest)
    source_record = artifacts.get(source_artifact_name)
    native_binary = artifacts.get("nativeBinary")
    if source_record is None:
        fail(
            errors,
            case_name,
            f"artifacts.{source_artifact_name}",
            "required descriptor source artifact record is missing",
        )
        return
    if native_binary is None:
        fail(
            errors,
            case_name,
            "artifacts.nativeBinary",
            "required descriptor native binary record is missing",
        )
        return

    source_exists, _source_size, source_sha256 = file_facts(
        package, source_record.get("path")
    )
    native_binary_exists, native_binary_size, native_binary_sha256 = file_facts(
        package, native_binary.get("path")
    )
    if not source_exists:
        fail(
            errors,
            case_name,
            f"artifacts.{source_artifact_name}.path",
            "descriptor source artifact must exist on disk",
        )
        return

    expect_equal(
        errors,
        case_name,
        "nativeArtifactDescriptor.health",
        descriptor.get("health"),
        "ok",
    )
    expect_equal(
        errors,
        case_name,
        "nativeArtifactDescriptor.schemaVersion",
        descriptor.get("schemaVersion"),
        1,
    )
    expect_equal(
        errors,
        case_name,
        "nativeArtifactDescriptor.kind",
        descriptor.get("kind"),
        "crossgl.nativeArtifact",
    )
    expect_equal(
        errors,
        case_name,
        "nativeArtifactDescriptor.contractVersion",
        descriptor.get("contractVersion"),
        "native-artifact-v0",
    )
    expect_equal(
        errors,
        case_name,
        "nativeArtifactDescriptor.target",
        descriptor.get("target"),
        target,
    )
    expect_equal(
        errors,
        case_name,
        "nativeArtifactDescriptor.binaryKind",
        descriptor.get("binaryKind"),
        NATIVE_ARTIFACT_BINARY_KINDS[target],
    )
    expect_equal(
        errors,
        case_name,
        "nativeArtifactDescriptor.sourcePath",
        descriptor.get("sourcePath"),
        source_record.get("path"),
    )
    expect_equal(
        errors,
        case_name,
        "nativeArtifactDescriptor.sourceHash",
        descriptor.get("sourceHash"),
        source_sha256,
    )
    descriptor_file = package_relative_file(package, expected_descriptor_path)
    descriptor_payload = (
        load_json_file(descriptor_file)
        if descriptor_file is not None and descriptor_file.is_file()
        else {}
    )
    expected_optimization_level = descriptor_payload.get("optimizationLevel")
    expected_optimization_evidence = descriptor_payload.get("optimizationEvidence")
    expect_equal(
        errors,
        case_name,
        "nativeArtifactDescriptor.optimizationLevel",
        descriptor.get("optimizationLevel"),
        expected_optimization_level,
    )
    expect_equal(
        errors,
        case_name,
        "nativeArtifactDescriptor.optimizationEvidence",
        descriptor.get("optimizationEvidence"),
        expected_optimization_evidence,
    )

    summary_status = payload.get("summary", {}).get("nativeBinaryStatus")
    if target in SOURCE_PACKAGE_TARGETS:
        expect_equal(
            errors,
            case_name,
            "nativeArtifactDescriptor.nativeBinaryStatus",
            descriptor.get("nativeBinaryStatus"),
            summary_status,
        )
    else:
        expect_equal(
            errors,
            case_name,
            "nativeArtifactDescriptor.nativeBinaryStatus",
            descriptor.get("nativeBinaryStatus"),
            None,
        )

    planned_native_binary = summary_status == "planned"
    if planned_native_binary:
        expected_artifact_path = None
        expected_artifact_hash = None
        expected_size_bytes = None
    else:
        if not native_binary_exists:
            fail(
                errors,
                case_name,
                "artifacts.nativeBinary.path",
                "descriptor native binary artifact must exist on disk",
            )
            return
        expected_artifact_path = native_binary.get("path")
        expected_artifact_hash = native_binary_sha256
        expected_size_bytes = native_binary_size
    expect_equal(
        errors,
        case_name,
        "nativeArtifactDescriptor.artifactPath",
        descriptor.get("artifactPath"),
        expected_artifact_path,
    )
    expect_equal(
        errors,
        case_name,
        "nativeArtifactDescriptor.artifactHash",
        descriptor.get("artifactHash"),
        expected_artifact_hash,
    )
    expect_equal(
        errors,
        case_name,
        "nativeArtifactDescriptor.sizeBytes",
        descriptor.get("sizeBytes"),
        expected_size_bytes,
    )

    expected_checks = dict.fromkeys(NATIVE_ARTIFACT_DESCRIPTOR_CHECKS, True)
    if planned_native_binary:
        expected_checks["artifactHashMatchesFile"] = None
        expected_checks["sizeBytesMatchesFile"] = None
    for check_name, expected_value in expected_checks.items():
        expect_equal(
            errors,
            case_name,
            f"nativeArtifactDescriptor.checks.{check_name}",
            checks.get(check_name),
            expected_value,
        )


def check_runtime_roles(
    errors: list[str],
    case_name: str,
    package: Path,
    manifest: dict[str, Any],
    payload: dict[str, Any],
    artifacts: dict[str, dict[str, Any]],
) -> None:
    target = manifest["target"]
    summary = payload.get("summary", {})
    reflection = payload.get("reflection", {})
    embedded_manifest = payload.get("manifest", {})

    expect_equal(errors, case_name, "summary.target", summary.get("target"), target)
    expect_equal(
        errors,
        case_name,
        "summary.nativeBinaryStatus",
        summary.get("nativeBinaryStatus"),
        expected_summary_native_binary_status(manifest),
    )
    expect_equal(
        errors,
        case_name,
        "manifest.artifacts",
        embedded_manifest.get("artifacts"),
        manifest.get("artifacts"),
    )
    expect_equal(
        errors,
        case_name,
        "reflection.nativeBinary",
        reflection.get("nativeBinary"),
        manifest["artifacts"].get("nativeBinary"),
    )
    check_summary_inventory(errors, case_name, manifest, payload, artifacts)
    check_native_binary_inventory(errors, case_name, manifest, payload, artifacts)
    check_vulkan_profile_inventory(errors, case_name, payload, manifest, artifacts)
    check_native_artifact_descriptor_inventory(
        errors, case_name, package, manifest, payload, artifacts
    )

    for name in ("debugMetadata", "hirSourceMap", "targetExplanation"):
        if name not in artifacts:
            fail(
                errors,
                case_name,
                f"artifacts.{name}",
                "required for runtime debug lookup",
            )
        else:
            expect_equal(
                errors,
                case_name,
                f"artifacts.{name}.exists",
                artifacts[name].get("exists"),
                True,
            )

    for name in TARGET_ARTIFACT_PATHS[target]:
        if name not in artifacts:
            fail(
                errors,
                case_name,
                f"artifacts.{name}",
                "missing target runtime artifact",
            )

    if target in {"directx", "opengl"}:
        expect_equal(
            errors,
            case_name,
            "manifest.artifacts.nativeBinaryStatus",
            manifest["artifacts"].get("nativeBinaryStatus"),
            summary.get("nativeBinaryStatus"),
        )
        expect_equal(
            errors,
            case_name,
            "artifacts.backendSource.exists",
            artifacts["backendSource"].get("exists"),
            True,
        )
        expected_native_exists = summary.get("nativeBinaryStatus") != "planned"
        expect_equal(
            errors,
            case_name,
            "artifacts.nativeBinary.exists",
            artifacts["nativeBinary"].get("exists"),
            expected_native_exists,
        )
    elif target == "metal":
        if "nativeBinaryStatus" in manifest["artifacts"]:
            fail(
                errors,
                case_name,
                "manifest.artifacts.nativeBinaryStatus",
                "unexpected native metadata",
            )
        for name in ("backendSource", "intermediate", "nativeBinary"):
            expect_equal(
                errors,
                case_name,
                f"artifacts.{name}.exists",
                artifacts[name].get("exists"),
                True,
            )
    elif target == "vulkan":
        if "backendSource" in artifacts:
            fail(
                errors,
                case_name,
                "artifacts.backendSource",
                "Vulkan runtime uses SPIR-V assembly",
            )
        for name in ("backendAssembly", "nativeBinary", "nativeProfile"):
            expect_equal(
                errors,
                case_name,
                f"artifacts.{name}.exists",
                artifacts[name].get("exists"),
                True,
            )


def case_runtime_report(
    case_name: str,
    payload: dict[str, Any],
    artifacts: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    summary = payload.get("summary", {})
    descriptor = payload.get("nativeArtifactDescriptor", {})
    profile = payload.get("vulkanNativeProfile", {})
    root_file_reports = [
        {
            "name": record.get("name"),
            "role": "root-file",
            "path": record.get("path"),
            "exists": record.get("exists"),
            "sizeBytes": record.get("sizeBytes"),
            "sha256": record.get("sha256"),
        }
        for record in payload.get("rootFiles", [])
        if isinstance(record, dict)
    ]
    artifact_reports = [
        {
            "name": name,
            "role": runtime_artifact_role(name),
            "path": record.get("path"),
            "exists": record.get("exists"),
            "packageRelative": record.get("packageRelative"),
            "sizeBytes": record.get("sizeBytes"),
            "sha256": record.get("sha256"),
        }
        for name, record in sorted(artifacts.items())
    ]
    return {
        "name": case_name,
        "target": summary.get("target"),
        "nativeBinaryStatus": summary.get("nativeBinaryStatus"),
        "artifactCount": summary.get("artifactCount"),
        "declaredArtifactNames": [record["name"] for record in artifact_reports],
        "existingArtifactNames": [
            record["name"] for record in artifact_reports if record["exists"] is True
        ],
        "missingArtifactNames": [
            record["name"] for record in artifact_reports if record["exists"] is False
        ],
        "rootFiles": root_file_reports,
        "artifacts": artifact_reports,
        "nativeBinary": artifacts.get("nativeBinary"),
        "vulkanNativeProfile": {
            "health": profile.get("health"),
            "nativeProfileArtifactPresent": profile.get("nativeProfileArtifactPresent"),
            "nativeProfileExists": profile.get("nativeProfileExists"),
            "nativeBinary": profile.get("nativeBinary"),
            "backendAssembly": profile.get("backendAssembly"),
            "disassemblyPath": profile.get("disassemblyPath"),
            "disassemblyExists": profile.get("disassemblyExists"),
        },
        "nativeArtifactDescriptor": {
            "health": descriptor.get("health"),
            "artifactPresent": descriptor.get("artifactPresent"),
            "descriptorExists": descriptor.get("descriptorExists"),
            "path": descriptor.get("path"),
            "target": descriptor.get("target"),
            "binaryKind": descriptor.get("binaryKind"),
            "sourcePath": descriptor.get("sourcePath"),
            "sourceHash": descriptor.get("sourceHash"),
            "artifactPath": descriptor.get("artifactPath"),
            "artifactHash": descriptor.get("artifactHash"),
            "sizeBytes": descriptor.get("sizeBytes"),
            "optimizationLevel": descriptor.get("optimizationLevel"),
            "optimizationEvidence": descriptor.get("optimizationEvidence"),
            "nativeBinaryStatus": descriptor.get("nativeBinaryStatus"),
            "checks": descriptor.get("checks"),
        },
    }


def check_case(
    root: Path, cglc: Path, tmp_dir: Path, case_spec: dict[str, str]
) -> tuple[list[str], dict[str, Any] | None]:
    del root
    case_name = case_spec["name"]
    target = case_spec["target"]
    status = case_spec["status"]
    package, _source, manifest = make_package(
        tmp_dir,
        case_name,
        target=target,
        status=status,
    )
    descriptor_mode = case_spec.get("descriptor")
    if descriptor_mode == "validated":
        add_native_artifact_descriptor(
            package, manifest, mutate=mark_native_artifact_validated
        )
    elif descriptor_mode == "optimized":
        add_native_artifact_descriptor(
            package, manifest, mutate=add_directx_optimization_evidence
        )
    elif descriptor_mode == "default":
        add_native_artifact_descriptor(package, manifest)

    result = run_inspect(cglc, package)
    if result.returncode != 0:
        return (
            [
                f"{case_name}: package inspect failed: "
                f"{result.stderr}{result.stdout}".strip()
            ],
            None,
        )

    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        return [f"{case_name}: package inspect did not emit JSON: {exc}"], None

    errors: list[str] = []
    expect_equal(errors, case_name, "schemaVersion", payload.get("schemaVersion"), 1)
    expect_equal(
        errors, case_name, "packageFormat", payload.get("packageFormat"), "directory"
    )
    check_root_file_inventory(errors, case_name, package, payload)
    artifacts = check_artifact_inventory(errors, case_name, package, manifest, payload)
    check_runtime_roles(errors, case_name, package, manifest, payload, artifacts)
    return errors, case_runtime_report(case_name, payload, artifacts)


def case_tmp_dir(tmp_dir: Path, case_spec: dict[str, str]) -> Path:
    return tmp_dir / case_spec["name"]


def collect_case_results(
    root: Path, cglc: Path, tmp_dir: Path, jobs: int
) -> list[tuple[list[str], dict[str, Any] | None]]:
    cases = list(CASE_SPECS)
    if jobs <= 1 or len(cases) <= 1:
        return [
            check_case(root, cglc, case_tmp_dir(tmp_dir, case_spec), case_spec)
            for case_spec in cases
        ]

    with ThreadPoolExecutor(max_workers=min(jobs, len(cases))) as executor:
        return list(
            executor.map(
                lambda case_spec: check_case(
                    root, cglc, case_tmp_dir(tmp_dir, case_spec), case_spec
                ),
                cases,
            )
        )


def run_cases(
    root: Path, cglc: Path, *, jobs: int = 1
) -> tuple[list[str], list[dict[str, Any]]]:
    errors: list[str] = []
    reports: list[dict[str, Any]] = []
    with tempfile.TemporaryDirectory() as tmp:
        tmp_dir = Path(tmp)
        for case_errors, case_report in collect_case_results(root, cglc, tmp_dir, jobs):
            errors.extend(case_errors)
            if case_report is not None:
                reports.append(case_report)
    return errors, reports


def self_test_artifact_record_facts() -> list[str]:
    errors: list[str] = []
    with tempfile.TemporaryDirectory() as tmp:
        package = Path(tmp) / "package.cglb"
        artifact_path = "backend/test.bin"
        file_path = package / artifact_path
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_bytes(b"runtime artifact bytes\n")

        record = {
            "name": "nativeBinary",
            "path": artifact_path,
            "exists": True,
            "sizeBytes": 1,
            "sha256": "0" * 64,
        }
        record_errors: list[str] = []
        expect_file_fact_contract(
            record_errors,
            "self-test",
            "artifacts.nativeBinary",
            record,
            package,
            artifact_path,
        )
        for expected_path in (
            "artifacts.nativeBinary.sizeBytes",
            "artifacts.nativeBinary.sha256",
        ):
            if not any(expected_path in error for error in record_errors):
                errors.append(
                    f"self-test: expected tampered {expected_path} to be rejected"
                )
    return errors


def artifact_record(
    package: Path,
    name: str,
    artifact_path: str,
    *,
    sha256: str | None = None,
    size_bytes: int | None = None,
) -> dict[str, Any]:
    exists, actual_size, actual_sha256 = file_facts(package, artifact_path)
    return {
        "name": name,
        "path": artifact_path,
        "exists": exists,
        "packageRelative": is_package_relative_path(artifact_path),
        "sizeBytes": actual_size if size_bytes is None else size_bytes,
        "sha256": actual_sha256 if sha256 is None else sha256,
    }


def descriptor_payload(
    manifest: dict[str, Any],
    *,
    source_hash: str,
    artifact_hash: str,
    size_bytes: int,
    optimization_level: str = "O0",
    optimization_evidence: dict[str, Any] | None = None,
) -> dict[str, Any]:
    target = manifest["target"]
    source_name = expected_native_artifact_source_name(manifest)
    return {
        "artifactPresent": True,
        "descriptorExists": True,
        "path": manifest["artifacts"]["nativeArtifactDescriptor"],
        "health": "ok",
        "schemaVersion": 1,
        "kind": "crossgl.nativeArtifact",
        "contractVersion": "native-artifact-v0",
        "target": target,
        "binaryKind": NATIVE_ARTIFACT_BINARY_KINDS[target],
        "sourcePath": manifest["artifacts"][source_name],
        "sourceHash": source_hash,
        "nativeBinaryStatus": manifest["artifacts"].get("nativeBinaryStatus"),
        "artifactPath": manifest["artifacts"]["nativeBinary"],
        "artifactHash": artifact_hash,
        "sizeBytes": size_bytes,
        "optimizationLevel": optimization_level,
        "optimizationEvidence": optimization_evidence,
        "checks": dict.fromkeys(NATIVE_ARTIFACT_DESCRIPTOR_CHECKS, True),
    }


def self_test_native_artifact_descriptor_file_facts() -> list[str]:
    errors: list[str] = []
    with tempfile.TemporaryDirectory() as tmp:
        package, _source, manifest = make_package(
            Path(tmp),
            "descriptor-tamper",
            target="directx",
            status="emitted",
        )
        add_native_artifact_descriptor(package, manifest)

        source_name = expected_native_artifact_source_name(manifest)
        source_path = manifest["artifacts"][source_name]
        native_path = manifest["artifacts"]["nativeBinary"]
        _source_exists, _source_size, source_sha256 = file_facts(package, source_path)
        _native_exists, native_size, native_sha256 = file_facts(package, native_path)
        tampered_source_sha256 = "f" * 64 if source_sha256 != "f" * 64 else "e" * 64
        tampered_native_sha256 = "e" * 64 if native_sha256 != "e" * 64 else "d" * 64
        tampered_native_size = 1 if native_size != 1 else 2

        artifacts = {
            source_name: artifact_record(
                package, source_name, source_path, sha256=tampered_source_sha256
            ),
            "nativeBinary": artifact_record(
                package,
                "nativeBinary",
                native_path,
                sha256=tampered_native_sha256,
                size_bytes=tampered_native_size,
            ),
            "nativeArtifactDescriptor": artifact_record(
                package,
                "nativeArtifactDescriptor",
                manifest["artifacts"]["nativeArtifactDescriptor"],
            ),
        }
        payload = {
            "summary": {"nativeBinaryStatus": "emitted"},
            "nativeArtifactDescriptor": descriptor_payload(
                manifest,
                source_hash=tampered_source_sha256,
                artifact_hash=tampered_native_sha256,
                size_bytes=tampered_native_size,
            ),
        }

        descriptor_errors: list[str] = []
        check_native_artifact_descriptor_inventory(
            descriptor_errors,
            "self-test",
            package,
            manifest,
            payload,
            artifacts,
        )
        for expected_path in (
            "nativeArtifactDescriptor.sourceHash",
            "nativeArtifactDescriptor.artifactHash",
            "nativeArtifactDescriptor.sizeBytes",
        ):
            if not any(expected_path in error for error in descriptor_errors):
                errors.append(
                    f"self-test: expected tampered {expected_path} to be rejected"
                )
    return errors


def runtime_reader_imports() -> tuple[Any, Any]:
    repo_root = Path(__file__).resolve().parents[1]
    repo_root_text = str(repo_root)
    if repo_root_text not in sys.path:
        sys.path.insert(0, repo_root_text)

    from runtime.package_reader import (  # pylint: disable=import-outside-toplevel
        read_compatibility_report,
        select_runtime_artifact,
    )

    return read_compatibility_report, select_runtime_artifact


def self_test_native_profile_target_mismatch_blocks_selection() -> list[str]:
    errors: list[str] = []
    with tempfile.TemporaryDirectory() as tmp:
        package, _source, manifest = make_package(
            Path(tmp),
            "vulkan-native-profile-target-mismatch",
            target="vulkan",
            status="planned",
        )
        profile_path = package_relative_file(
            package, manifest["artifacts"]["nativeProfile"]
        )
        if profile_path is None or not profile_path.is_file():
            return ["self-test: expected Vulkan nativeProfile fixture to exist"]

        profile = load_json_file(profile_path)
        profile["target"] = "metal"
        profile_path.write_text(
            json.dumps(profile, indent=2) + "\n",
            encoding="utf-8",
        )

        read_compatibility_report, select_runtime_artifact = runtime_reader_imports()
        report = read_compatibility_report(package, loader_target="vulkan")
        selection = select_runtime_artifact(
            report,
            target="vulkan",
            package_mode="native",
        )
        report_summary = report.to_summary()
        selection_summary = selection.to_summary()
        expected_code = "package.native_profile.target_mismatch"
        reject_codes = [
            diagnostic["code"] for diagnostic in report_summary["rejectReasons"]
        ]
        selection_reject_codes = [
            diagnostic["code"] for diagnostic in selection_summary["rejectReasons"]
        ]

        if report.compatible:
            errors.append("self-test: target-incompatible nativeProfile was compatible")
        if selection.selected or selection_summary["artifact"] is not None:
            errors.append(
                "self-test: target-incompatible nativeProfile selected a native artifact"
            )
        if expected_code not in reject_codes:
            errors.append(
                "self-test: target-incompatible nativeProfile was not rejected "
                f"with {expected_code}"
            )
        if expected_code not in selection_reject_codes:
            errors.append(
                "self-test: target-incompatible nativeProfile did not block "
                f"runtime selection with {expected_code}"
            )
        admission = selection_summary["admission"]
        if admission["decision"] != "rejected":
            errors.append(
                "self-test: target-incompatible nativeProfile admission was not rejected"
            )
        if admission["native"]["reason"] != expected_code:
            errors.append(
                "self-test: target-incompatible nativeProfile did not surface "
                "as native admission reason"
            )
        for key in (
            "sourceParsingRequired",
            "compilerInvocationRequired",
            "deviceExecutionRequired",
        ):
            if selection_summary[key]:
                errors.append(
                    "self-test: target-incompatible nativeProfile selection "
                    f"unexpectedly set {key}"
                )
        if selection_summary["sourceInputs"] != []:
            errors.append(
                "self-test: target-incompatible nativeProfile selection "
                "reported source inputs"
            )
    return errors


def self_test_legacy_requirements_are_report_only() -> list[str]:
    errors: list[str] = []
    with tempfile.TemporaryDirectory() as tmp:
        package, _source, manifest = make_package(
            Path(tmp),
            "legacy-requirements-report-only",
            target="metal",
            status="planned",
        )
        manifest.pop("packageArtifactRequirements", None)
        rewrite_manifest(package, manifest)

        read_compatibility_report, _select_runtime_artifact = runtime_reader_imports()
        report = read_compatibility_report(package, loader_target="metal")
        summary = report.to_summary()
        requirements = summary["admission"]["requirements"]
        legacy_requirements = requirements["legacyGeneratedRequirements"]

        expected_pairs = {
            "declared": False,
            "recorded": False,
            "legacyInferred": True,
            "requirementsSource": "legacy-v0-target-contract",
            "sourceKind": "legacy-generated",
            "compatibilityKind": "legacy-generated-compatible",
            "reportOnly": True,
            "compatibilityScope": "legacy/report-only",
        }
        for field, expected in expected_pairs.items():
            actual = requirements.get(field)
            if actual != expected:
                errors.append(
                    "self-test: legacy generated requirements field "
                    f"{field} expected {expected!r}, got {actual!r}"
                )

        legacy_expected_pairs = {
            "compatibilityOnly": True,
            "reportOnly": True,
            "compatibilityScope": "legacy/report-only",
            "inferred": True,
            "requirementsSource": "legacy-v0-target-contract",
        }
        for field, expected in legacy_expected_pairs.items():
            actual = legacy_requirements.get(field)
            if actual != expected:
                errors.append(
                    "self-test: legacy generated requirements label "
                    f"{field} expected {expected!r}, got {actual!r}"
                )

        if summary["packageArtifactRequirementsStatus"] != requirements:
            errors.append(
                "self-test: packageArtifactRequirementsStatus did not mirror "
                "admission requirements"
            )
        expected_diagnostic = {
            "severity": "note",
            "code": "package.artifact_requirements.legacy_v0_fallback",
            "message": (
                "manifest.packageArtifactRequirements is missing; using generated "
                "legacy v0 target contract as report-only compatibility metadata"
            ),
            "document": "manifest",
            "path": "packageArtifactRequirements",
            "expected": "recorded package artifact requirements",
            "actual": "legacy-v0-target-contract",
        }
        if requirements.get("diagnostics") != [expected_diagnostic]:
            errors.append(
                "self-test: legacy requirements fallback did not expose the "
                "runtime diagnostic note"
            )
        if summary["diagnostics"] != [expected_diagnostic]:
            errors.append(
                "self-test: legacy requirements fallback note was not included "
                "in compatibility diagnostics"
            )
        if summary["packageArtifactRequirements"]["requirementsSource"] != (
            "legacy-v0-target-contract"
        ):
            errors.append(
                "self-test: legacy packageArtifactRequirements did not expose "
                "the legacy source label"
            )
        if summary["packageArtifactRequirements"]["reportOnly"] is not True:
            errors.append(
                "self-test: legacy packageArtifactRequirements were not report-only"
            )
        if summary["packageArtifactRequirements"]["compatibilityScope"] != (
            "legacy/report-only"
        ):
            errors.append(
                "self-test: legacy packageArtifactRequirements did not expose "
                "the report-only scope"
            )
        if not summary["admission"]["metadataOnly"]:
            errors.append(
                "self-test: legacy requirements admission was not metadata-only"
            )
        for key in (
            "sourceParsingRequired",
            "compilerInvocationRequired",
            "deviceExecutionRequired",
        ):
            if summary[key]:
                errors.append(
                    "self-test: legacy requirements compatibility report "
                    f"unexpectedly set {key}"
                )
            if summary["admission"][key]:
                errors.append(
                    f"self-test: legacy requirements admission unexpectedly set {key}"
                )
        if summary["sourceInputs"] != [] or summary["admission"]["sourceInputs"] != []:
            errors.append(
                "self-test: legacy requirements compatibility report exposed "
                "source inputs"
            )
    return errors


def run_self_test() -> list[str]:
    errors: list[str] = []
    path_cases = {
        "backend/test.bin": True,
        "backend/nested/test.bin": True,
        "/backend/test.bin": False,
        "backend\\test.bin": False,
        "../backend/test.bin": False,
        "backend/../test.bin": False,
        "C:/backend/test.bin": False,
    }
    for value, expected in path_cases.items():
        actual = is_package_relative_path(value)
        if actual != expected:
            errors.append(
                f"self-test: expected package-relative check for {value!r} "
                f"to be {expected}, got {actual}"
            )
    errors.extend(self_test_artifact_record_facts())
    errors.extend(self_test_native_artifact_descriptor_file_facts())
    errors.extend(self_test_native_profile_target_mismatch_blocks_selection())
    errors.extend(self_test_legacy_requirements_are_report_only())
    return errors


def inventory_report(reports: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "schemaVersion": 1,
        "kind": "crossgl.packageArtifactInventoryRuntimeCheck",
        "caseCount": len(reports),
        "cases": reports,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--root",
        default=".",
        help="CrossGL-Compiler repository root",
    )
    parser.add_argument("--cglc", help="path to cglc executable")
    parser.add_argument(
        "--self-test",
        action="store_true",
        help="run checker-local tamper guard tests without invoking cglc",
    )
    parser.add_argument(
        "--jobs",
        default=None,
        help=(
            "Opt-in worker count for independent runtime inventory cases. Defaults "
            f"to ${CROSSGL_PACKAGE_ARTIFACT_INVENTORY_RUNTIME_JOBS} or 1."
        ),
    )
    parser.add_argument(
        "--report-json",
        help="optional path for a JSON inventory report derived from package inspect",
    )
    args = parser.parse_args()

    if args.self_test:
        errors = run_self_test()
        if errors:
            for error in errors:
                print(
                    f"package artifact inventory self-test failed: {error}",
                    file=sys.stderr,
                )
            return 1
        print("validated package artifact inventory runtime checker self-test")
        return 0

    if args.cglc is None:
        parser.error("--cglc is required unless --self-test is used")

    try:
        jobs = parse_jobs(
            args.jobs
            if args.jobs is not None
            else os.environ.get(CROSSGL_PACKAGE_ARTIFACT_INVENTORY_RUNTIME_JOBS),
            "--jobs"
            if args.jobs is not None
            else CROSSGL_PACKAGE_ARTIFACT_INVENTORY_RUNTIME_JOBS,
        )
    except ValueError as exc:
        parser.error(str(exc))

    errors, reports = run_cases(
        Path(args.root).resolve(), Path(args.cglc).resolve(), jobs=jobs
    )
    if errors:
        for error in errors:
            print(f"package artifact inventory check failed: {error}", file=sys.stderr)
        return 1

    if args.report_json:
        Path(args.report_json).write_text(
            json.dumps(inventory_report(reports), indent=2) + "\n",
            encoding="utf-8",
        )

    print("validated package artifact inventory for runtime consumers")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
