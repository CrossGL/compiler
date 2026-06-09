#!/usr/bin/env python3
"""Minimal CrossGL .cglb directory/zip package reader.

This prototype reads package root JSON and exposes loader-oriented artifact
access without parsing CrossGL source or loading any graphics API.
"""

from __future__ import annotations

import argparse
from collections.abc import Iterator
from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
from pathlib import PurePosixPath
import re
import sys
from typing import Any
import zipfile

try:
    from . import package_target_contracts as _generated_package_target_contracts
except ImportError:  # pragma: no cover - supports direct script execution.
    import package_target_contracts as _generated_package_target_contracts


ROOT_METADATA_FILES = ("manifest.json", "reflection.json", "diagnostics.json")
RUNTIME_METADATA_JSON_BYTE_LIMIT = 16 * 1024 * 1024
RUNTIME_ARTIFACT_BYTE_LIMIT = 512 * 1024 * 1024
RUNTIME_ARTIFACT_STREAM_CHUNK_SIZE = 1024 * 1024
_DEFAULT_ARTIFACT_BYTE_LIMIT = object()
NATIVE_BINARY_READY_STATUSES = frozenset(("emitted", "validated"))
SOURCE_FREE_NATIVE_RUNTIME_TARGETS = frozenset(("directx", "metal", "vulkan"))
RUNTIME_ARTIFACT_MODES = frozenset(("auto", "native", "source"))
RUNTIME_ARTIFACT_SELECTION_MODES = frozenset(
    ("auto", "native", "source", "source-package")
)
PACKAGE_ARTIFACT_REQUIREMENT_KEYS = frozenset(
    (
        "target",
        "packageMode",
        "requiredPathArtifacts",
        "requiresNativeBinaryStatus",
        "allowsPlannedNativeBinary",
        "allowsPlannedNativeSourceEvidence",
        "evidenceIds",
    )
)
TARGET_LEGALIZATION_TOOL_REQUIREMENT_KEYS = frozenset(
    (
        "target",
        "packageMode",
        "requiredToolCount",
        "missingToolCount",
        "requiredToolIds",
        "missingToolIds",
        "optionalNativeToolMissing",
        "optionalNativeToolStatus",
        "toolRequirementEvidenceIds",
    )
)
TARGET_LEGALIZATION_OPTIONAL_NATIVE_TOOL_STATUSES = frozenset(
    ("available", "missing", "not-required")
)
PACKAGE_ARTIFACT_REQUIREMENT_SOURCE_FIELDS = frozenset(
    ("requirementsSource", "requirements_source", "contractSource")
)
GENERATED_PACKAGE_TARGET_CONTRACT_KEYS = frozenset(
    (
        "target",
        "requiredPathArtifacts",
        "requiresNativeBinaryStatus",
        "allowsPlannedNativeBinary",
        "allowsPlannedNativeSourceEvidence",
    )
)
PACKAGE_PATH_ARTIFACTS = frozenset(
    ("backendSource", "backendAssembly", "intermediate", "nativeBinary")
)
MANIFEST_ARTIFACT_KEYS = frozenset(
    (
        "backendSource",
        "backendAssembly",
        "intermediate",
        "nativeBinary",
        "nativeProfile",
        "nativeArtifactDescriptor",
        "nativeBinaryStatus",
        "debugMetadata",
        "graphicsAbi",
        "hirSourceMap",
        "targetExplanation",
    )
)
SUPPORTED_COMPILER_NAME = "CrossGL-Compiler"
SUPPORTED_DEBUG_METADATA_SCHEMA_VERSION = 11
SUPPORTED_NATIVE_ARTIFACT_DESCRIPTOR_SCHEMA_VERSION = 1
SUPPORTED_NATIVE_PROFILE_SCHEMA_VERSION = 1
SUPPORTED_PACKAGE_SCHEMA_VERSION = 1
SUPPORTED_PACKAGE_TARGET_CONTRACT_SCHEMA_VERSION = 1
SOURCE_ARTIFACT_NAMES = ("backendSource",)
SOURCE_PACKAGE_MODE = "source-package"
NATIVE_ARTIFACT_DESCRIPTOR_KIND = "crossgl.nativeArtifact"
NATIVE_ARTIFACT_DESCRIPTOR_CONTRACT_VERSION = "native-artifact-v0"
NATIVE_ARTIFACT_DESCRIPTOR_FIELDS = frozenset(
    (
        "schemaVersion",
        "kind",
        "contractVersion",
        "target",
        "binaryKind",
        "artifactPath",
        "artifactHash",
        "sizeBytes",
        "spirvDependencies",
        "sourcePath",
        "sourceHash",
        "toolchainProvenance",
        "optimizationLevel",
        "optimizationEvidence",
        "validationStatus",
        "nativeBinaryStatus",
        "validationDiagnostics",
    )
)
NATIVE_OPTIMIZATION_EVIDENCE_APPLIED_VALUES = frozenset(
    ("applied", "optimization-applied", "optimized")
)
NATIVE_OPTIMIZATION_LEVELS = frozenset(
    ("none", "debug", "O0", "O1", "O2", "O3", "Os", "Oz", "unknown")
)
NATIVE_CONCRETE_OPTIMIZATION_LEVELS = frozenset(
    level for level in NATIVE_OPTIMIZATION_LEVELS if level != "unknown"
)
NATIVE_OPTIMIZATION_PRODUCED_ARTIFACT_FACTS = (
    "artifactPath",
    "artifactHash",
    "sizeBytes",
)
NATIVE_TOOLCHAIN_EXECUTABLE_SOURCES = frozenset(
    ("PATH", "direct", "fallback", "xcrun", "not-found")
)
NATIVE_TOOLCHAIN_VERSION_PROBE_STATUSES = frozenset(
    ("succeeded", "failed", "not-started", "version-unknown", "unavailable")
)
NATIVE_TOOLCHAIN_TOOL_IDENTITY_STRING_FIELDS = (
    "name",
    "role",
    "version",
    "executable",
)
NATIVE_ARTIFACT_DESCRIPTOR_VALIDATION_STATUSES = frozenset(
    ("not-run", "unavailable", "validated", "failed")
)
NATIVE_ADMISSION_DIAGNOSTIC_ARTIFACTS = frozenset(
    (
        "nativeBinary",
        "nativeBinaryStatus",
        "nativeArtifactDescriptor",
        "nativeProfile",
    )
)
NATIVE_BINARY_DESCRIPTOR_CONTRACT_DIAGNOSTIC_CODES = frozenset(
    (
        "package.native_artifact_descriptor.artifact_path_mismatch",
        "package.native_artifact_descriptor.artifact_hash_invalid",
        "package.native_artifact_descriptor.artifact_hash_mismatch",
        "package.native_artifact_descriptor.artifact_hash_too_large",
        "package.native_artifact_descriptor.size_bytes_invalid",
        "package.native_artifact_descriptor.size_bytes_mismatch",
    )
)
NATIVE_BINARY_STATUS_CONTRACT_DIAGNOSTIC_CODES = frozenset(
    ("package.native_binary_status.invalid",)
)
MANIFEST_ARTIFACT_CONTRACT_DIAGNOSTIC_CODES = frozenset(
    (
        "package.artifact.name_invalid",
        "package.artifact.unexpected",
        "package.artifact.path_invalid",
        "package.artifact.path_duplicate",
    )
)
NATIVE_ARTIFACT_BINARY_KINDS_BY_TARGET = {
    "directx": ("directx.dxil", "directx.dxbc"),
    "metal": ("metal.metallib",),
    "opengl": ("opengl.source", "opengl.package"),
    "vulkan": ("vulkan.spirv-module",),
}
NATIVE_ARTIFACT_SOURCE_BY_BINARY_KIND = {
    "directx.dxbc": "backendSource",
    "directx.dxil": "backendSource",
    "metal.metallib": "backendSource",
    "opengl.package": "backendSource",
    "opengl.source": "backendSource",
    "vulkan.spirv-module": "backendAssembly",
}
REFLECTION_RUNTIME_COLLECTIONS = {
    "entryPoints": "entry_points",
    "resources": "resources",
    "targetResourceBindings": "target_resource_bindings",
    "targetFeatures": "target_features",
}
REFLECTION_WORKGROUP_SIZE_FIELDS = (
    "stage",
    "entryPoint",
    "x",
    "y",
    "z",
    "sourceX",
    "sourceY",
    "sourceZ",
)
REFLECTION_REQUIRED_STRING_FIELDS = {
    "entryPoints": ("stage", "sourceName", "backendName"),
    "resources": ("stage", "name", "kind"),
    "targetResourceBindings": ("stage", "entryPoint", "name", "kind"),
    "targetFeatures": ("kind", "name"),
}
TARGET_LEGALIZATION_EVIDENCE_PREFIX = "target-legalization.v1"
TARGET_FEATURE_EVIDENCE_TARGETS = frozenset(("metal", "vulkan", "directx", "opengl"))
TARGET_LEGALIZATION_TARGET_FEATURE_EVIDENCE_RE = re.compile(
    r"^target-legalization\.v1\."
    r"(?P<target>metal|vulkan|directx|opengl)\."
    r"(?:(?:capability\.(?:required|missing)\."
    r"(?P<capability_target>metal|vulkan|directx|opengl)\.[A-Za-z0-9_.-]+)"
    r"|(?:abi\.(?:required|missing)\.[A-Za-z0-9_.-]+))$"
)
TARGET_RESOURCE_BINDING_ABI_EXPECTATIONS = {
    "directx": (
        "DirectX register ABI object with integer space and register string, "
        "or flat registerBinding/groupsharedLocal reflection ABI"
    ),
    "metal": (
        "Metal argument ABI object with integer buffer, texture, or sampler, "
        "or flat kernelArgument/threadgroupLocal reflection ABI"
    ),
    "opengl": (
        "OpenGL resource ABI object with integer program and binding, "
        "or flat programResourceBinding/workgroupLocal reflection ABI"
    ),
    "vulkan": (
        "Vulkan descriptor ABI object with integer set and binding, "
        "or flat descriptor/workgroupLocal reflection ABI"
    ),
}
GENERATED_CONTRACT_REQUIREMENTS_SOURCE = "legacy-v0-target-contract"
# The generated v0 artifact contract does not encode backend-specific native
# status lifecycles, so keep those compatibility decisions separate.
_LEGACY_NATIVE_BINARY_STATUSES_BY_TARGET = {
    "directx": ("planned", "emitted"),
    "opengl": ("planned", "validated"),
}
_UNSUPPORTED_VERSION_DIAGNOSTIC_CODES = frozenset(
    (
        "package.schema.incompatible",
        "package.schema.version_missing",
        "package.schema.version_invalid",
        "package.debug_metadata.schema_incompatible",
        "package.debug_metadata.schema_version_missing",
        "package.debug_metadata.schema_version_invalid",
        "package.native_artifact_descriptor.schema_incompatible",
        "package.native_artifact_descriptor.schema_version_missing",
        "package.native_artifact_descriptor.schema_version_invalid",
        "package.native_profile.schema_incompatible",
        "package.native_profile.schema_version_missing",
        "package.native_profile.schema_version_invalid",
        "package.artifact_requirements.schema_incompatible",
        "package.target_contract.schema_incompatible",
    )
)


@dataclass(frozen=True)
class _PackageSource:
    root: Path
    package_format: str
    zip_members: dict[str, zipfile.ZipInfo] | None = None

    @property
    def is_zip(self) -> bool:
        return self.package_format == "zip"

    def zip_info(self, package_path: str) -> zipfile.ZipInfo | None:
        if self.zip_members is None:
            return None
        return self.zip_members.get(package_path)


class PackageReadError(ValueError):
    """Raised when a .cglb package cannot be read."""


class _MetadataTooLargeError(PackageReadError):
    def __init__(self, root_file_name: str, size: int, limit: int) -> None:
        self.root_file_name = root_file_name
        self.size = size
        self.limit = limit
        super().__init__(
            "package metadata exceeds runtime byte limit: "
            f"{root_file_name} is {size} bytes; limit is {limit} bytes"
        )


class _ArtifactTooLargeError(PackageReadError):
    def __init__(self, artifact: "Artifact", size: int, limit: int) -> None:
        self.artifact_name = artifact.name
        self.package_path = artifact.package_path
        self.size = size
        self.limit = limit
        super().__init__(
            "package artifact exceeds runtime byte limit: "
            f"{artifact.name} ({artifact.package_path}) is {size} bytes; "
            f"limit is {limit} bytes"
        )


@dataclass(frozen=True)
class DebugMetadataRecord:
    """Lightweight runtime-facing summary of optional debug metadata."""

    schema_version: Any
    requested_target: str | None
    selected_target: str | None
    selected_package_mode: str | None
    expression_source_location_count: int | None
    type_source_location_count: int | None
    statement_source_location_count: int | None
    manual_texture_compare_kernel_count: int | None

    @property
    def compatible(self) -> bool:
        return self.schema_version == SUPPORTED_DEBUG_METADATA_SCHEMA_VERSION

    def to_summary(self) -> dict[str, Any]:
        return {
            "schemaVersion": self.schema_version,
            "compatible": self.compatible,
            "requestedTarget": self.requested_target,
            "selectedTarget": self.selected_target,
            "selectedPackageMode": self.selected_package_mode,
            "sourceLocationCounts": {
                "expressions": self.expression_source_location_count,
                "types": self.type_source_location_count,
                "statements": self.statement_source_location_count,
            },
            "manualTextureCompareKernelCount": (
                self.manual_texture_compare_kernel_count
            ),
        }


@dataclass(frozen=True)
class GraphicsAbiRecord:
    """Lightweight runtime-facing summary of optional graphics ABI metadata."""

    module: str | None
    target: str | None
    schema_version: Any
    abi_version: Any
    entry_points: tuple[dict[str, Any], ...]
    resources: tuple[dict[str, Any], ...]
    abi_records: tuple[dict[str, Any], ...]
    descriptor_bindings: tuple[dict[str, Any], ...]
    stage_count: int
    stage_record_counts: dict[str, int]
    resource_count: int
    resource_record_counts: dict[str, int]

    def to_summary(self) -> dict[str, Any]:
        return {
            "module": self.module,
            "target": self.target,
            "schemaVersion": self.schema_version,
            "abiVersion": self.abi_version,
            "entryPointCount": len(self.entry_points),
            "resourceDeclarationCount": len(self.resources),
            "abiRecordCount": len(self.abi_records),
            "descriptorBindingCount": len(self.descriptor_bindings),
            "stageCount": self.stage_count,
            "stageRecordCounts": dict(self.stage_record_counts),
            "resourceCount": self.resource_count,
            "resourceRecordCounts": dict(self.resource_record_counts),
            "descriptorBindings": list(self.descriptor_bindings),
        }


@dataclass(frozen=True)
class TargetArtifactContract:
    """Runtime-visible target artifact requirements for package schema v1."""

    target: str
    package_mode: str
    required_artifacts: tuple[str, ...]
    native_binary_status_required: bool
    allowed_native_binary_statuses: tuple[str, ...]
    planned_native_binary_may_be_absent: bool
    allows_planned_native_source_evidence: bool = False
    requirements_source: str = GENERATED_CONTRACT_REQUIREMENTS_SOURCE

    def to_summary(self) -> dict[str, Any]:
        legacy_report_only = (
            self.requirements_source == GENERATED_CONTRACT_REQUIREMENTS_SOURCE
        )
        return {
            "target": self.target,
            "packageMode": self.package_mode,
            "requiredArtifacts": list(self.required_artifacts),
            "requiredPathArtifacts": list(self.required_artifacts),
            "nativeBinaryStatusRequired": self.native_binary_status_required,
            "requiresNativeBinaryStatus": self.native_binary_status_required,
            "allowedNativeBinaryStatuses": list(self.allowed_native_binary_statuses),
            "plannedNativeBinaryMayBeAbsent": (
                self.planned_native_binary_may_be_absent
            ),
            "allowsPlannedNativeBinary": (self.planned_native_binary_may_be_absent),
            "allowsPlannedNativeSourceEvidence": (
                self.allows_planned_native_source_evidence
            ),
            "requirementsSource": self.requirements_source,
            "reportOnly": legacy_report_only,
            "compatibilityScope": (
                "legacy/report-only"
                if legacy_report_only
                else "recorded-package-metadata"
            ),
        }


def _target_artifact_contracts(
    diagnostics: list[CompatibilityDiagnostic] | None = None,
) -> dict[str, TargetArtifactContract]:
    parsed_diagnostics: list[CompatibilityDiagnostic] = []
    contract_schema_version = getattr(
        _generated_package_target_contracts,
        "SCHEMA_VERSION",
        None,
    )
    if contract_schema_version != SUPPORTED_PACKAGE_TARGET_CONTRACT_SCHEMA_VERSION:
        parsed_diagnostics.append(
            CompatibilityDiagnostic(
                code="package.target_contract.schema_incompatible",
                message=(
                    "runtime generated package target contract schemaVersion "
                    "is not supported by this runtime"
                ),
                document="runtime.package_target_contracts",
                path="SCHEMA_VERSION",
                expected=SUPPORTED_PACKAGE_TARGET_CONTRACT_SCHEMA_VERSION,
                actual=contract_schema_version,
            )
        )
        if diagnostics is None:
            raise PackageReadError(parsed_diagnostics[0].message)
        diagnostics.extend(parsed_diagnostics)
        return {}

    contracts: dict[str, TargetArtifactContract] = {}
    for index, entry in enumerate(
        _generated_package_target_contracts.PACKAGE_TARGET_CONTRACTS
    ):
        contract = _target_artifact_contract_from_generated_entry(
            entry,
            index=index,
            diagnostics=parsed_diagnostics,
        )
        if contract is None:
            continue
        if contract.target in contracts:
            parsed_diagnostics.append(
                CompatibilityDiagnostic(
                    code="package.target_contract.target_duplicate",
                    message=(
                        "runtime generated package target contracts contain a "
                        f"duplicate target: {contract.target}"
                    ),
                    document="runtime.package_target_contracts",
                    path=f"PACKAGE_TARGET_CONTRACTS[{index}].target",
                    expected="unique target",
                    actual=contract.target,
                )
            )
            continue
        contracts[contract.target] = contract

    if parsed_diagnostics:
        if diagnostics is None:
            messages = "; ".join(
                diagnostic.message for diagnostic in parsed_diagnostics
            )
            raise PackageReadError(messages)
        diagnostics.extend(parsed_diagnostics)
    return contracts


def _target_artifact_contract_from_generated_entry(
    entry: Any,
    *,
    index: int,
    diagnostics: list[CompatibilityDiagnostic],
) -> TargetArtifactContract | None:
    start_diagnostic_count = len(diagnostics)
    entry_path = f"PACKAGE_TARGET_CONTRACTS[{index}]"
    if not isinstance(entry, dict):
        diagnostics.append(
            CompatibilityDiagnostic(
                code="package.target_contract.invalid",
                message="runtime generated package target contract must be an object",
                document="runtime.package_target_contracts",
                path=entry_path,
                expected="object",
                actual=_json_type_name(entry),
            )
        )
        return None

    for field in sorted(set(entry) - GENERATED_PACKAGE_TARGET_CONTRACT_KEYS):
        diagnostics.append(
            CompatibilityDiagnostic(
                code="package.target_contract.unexpected_field",
                message=(
                    "runtime generated package target contract contains an "
                    f"unexpected field: {field}"
                ),
                document="runtime.package_target_contracts",
                path=f"{entry_path}.{field}",
                expected=sorted(GENERATED_PACKAGE_TARGET_CONTRACT_KEYS),
                actual=field,
            )
        )

    target = _generated_contract_string_field(
        entry,
        "target",
        index=index,
        diagnostics=diagnostics,
    )
    required_artifacts = _generated_contract_required_path_artifacts(
        entry.get("requiredPathArtifacts"),
        present="requiredPathArtifacts" in entry,
        index=index,
        diagnostics=diagnostics,
    )
    requires_native_status = _generated_contract_bool_field(
        entry,
        "requiresNativeBinaryStatus",
        index=index,
        diagnostics=diagnostics,
    )
    allows_planned_native = _generated_contract_bool_field(
        entry,
        "allowsPlannedNativeBinary",
        index=index,
        diagnostics=diagnostics,
    )
    allows_planned_source_evidence = _generated_contract_bool_field(
        entry,
        "allowsPlannedNativeSourceEvidence",
        index=index,
        diagnostics=diagnostics,
    )

    if (
        requires_native_status is not None
        and allows_planned_native is not None
        and allows_planned_source_evidence is not None
        and (
            requires_native_status != allows_planned_native
            or allows_planned_source_evidence != allows_planned_native
        )
    ):
        diagnostics.append(
            CompatibilityDiagnostic(
                code="package.target_contract.native_binary_policy_mismatch",
                message=(
                    "runtime generated package target contract native binary "
                    "policy fields must match for schemaVersion 1"
                ),
                document="runtime.package_target_contracts",
                path=entry_path,
                expected=(
                    "requiresNativeBinaryStatus, allowsPlannedNativeBinary, "
                    "and allowsPlannedNativeSourceEvidence match"
                ),
                actual={
                    "requiresNativeBinaryStatus": requires_native_status,
                    "allowsPlannedNativeBinary": allows_planned_native,
                    "allowsPlannedNativeSourceEvidence": (
                        allows_planned_source_evidence
                    ),
                },
            )
        )

    if required_artifacts is not None and "nativeBinary" not in required_artifacts:
        diagnostics.append(
            CompatibilityDiagnostic(
                code="package.target_contract.native_binary_missing",
                message=(
                    "runtime generated package target contract "
                    "requiredPathArtifacts must include nativeBinary"
                ),
                document="runtime.package_target_contracts",
                path=f"{entry_path}.requiredPathArtifacts",
                expected="requiredPathArtifacts includes nativeBinary",
                actual=list(required_artifacts),
            )
        )

    if (
        requires_native_status is True
        and allows_planned_native is True
        and required_artifacts is not None
        and "backendSource" not in required_artifacts
    ):
        diagnostics.append(
            CompatibilityDiagnostic(
                code="package.target_contract.source_package_artifact_missing",
                message=(
                    "runtime generated source-package target contract "
                    "requiredPathArtifacts must include backendSource"
                ),
                document="runtime.package_target_contracts",
                path=f"{entry_path}.requiredPathArtifacts",
                expected="requiredPathArtifacts includes backendSource",
                actual=list(required_artifacts),
            )
        )

    if len(diagnostics) != start_diagnostic_count:
        return None

    assert target is not None
    assert required_artifacts is not None
    assert requires_native_status is not None
    assert allows_planned_native is not None
    assert allows_planned_source_evidence is not None
    source_package = requires_native_status and allows_planned_native
    return TargetArtifactContract(
        target=target,
        package_mode=SOURCE_PACKAGE_MODE if source_package else "native",
        required_artifacts=required_artifacts,
        native_binary_status_required=requires_native_status,
        allowed_native_binary_statuses=_generated_allowed_native_binary_statuses(
            target,
            requires_native_status=requires_native_status,
            allows_planned_native=allows_planned_native,
        ),
        planned_native_binary_may_be_absent=allows_planned_native,
        allows_planned_native_source_evidence=allows_planned_source_evidence,
        requirements_source=GENERATED_CONTRACT_REQUIREMENTS_SOURCE,
    )


def _generated_contract_string_field(
    entry: dict[str, Any],
    field: str,
    *,
    index: int,
    diagnostics: list[CompatibilityDiagnostic],
) -> str | None:
    path = f"PACKAGE_TARGET_CONTRACTS[{index}].{field}"
    if field not in entry:
        diagnostics.append(
            CompatibilityDiagnostic(
                code=f"package.target_contract.{_snake_case(field)}_missing",
                message=(
                    f"runtime generated package target contract {field} is required"
                ),
                document="runtime.package_target_contracts",
                path=path,
                expected="non-empty string",
                actual=None,
            )
        )
        return None
    value = entry.get(field)
    if not isinstance(value, str) or not value:
        diagnostics.append(
            CompatibilityDiagnostic(
                code=f"package.target_contract.{_snake_case(field)}_invalid",
                message=(
                    f"runtime generated package target contract {field} is invalid"
                ),
                document="runtime.package_target_contracts",
                path=path,
                expected="non-empty string",
                actual=_contract_actual_value(value),
            )
        )
        return None
    return value


def _generated_contract_bool_field(
    entry: dict[str, Any],
    field: str,
    *,
    index: int,
    diagnostics: list[CompatibilityDiagnostic],
) -> bool | None:
    path = f"PACKAGE_TARGET_CONTRACTS[{index}].{field}"
    if field not in entry:
        diagnostics.append(
            CompatibilityDiagnostic(
                code=f"package.target_contract.{_snake_case(field)}_missing",
                message=(
                    f"runtime generated package target contract {field} is required"
                ),
                document="runtime.package_target_contracts",
                path=path,
                expected="boolean",
                actual=None,
            )
        )
        return None
    value = entry.get(field)
    if not isinstance(value, bool):
        diagnostics.append(
            CompatibilityDiagnostic(
                code=f"package.target_contract.{_snake_case(field)}_invalid",
                message=(
                    f"runtime generated package target contract {field} "
                    "must be a boolean"
                ),
                document="runtime.package_target_contracts",
                path=path,
                expected="boolean",
                actual=_json_type_name(value),
            )
        )
        return None
    return value


def _generated_contract_required_path_artifacts(
    value: Any,
    *,
    present: bool,
    index: int,
    diagnostics: list[CompatibilityDiagnostic],
) -> tuple[str, ...] | None:
    path = f"PACKAGE_TARGET_CONTRACTS[{index}].requiredPathArtifacts"
    if not present:
        diagnostics.append(
            CompatibilityDiagnostic(
                code="package.target_contract.required_path_artifacts_missing",
                message=(
                    "runtime generated package target contract "
                    "requiredPathArtifacts is required"
                ),
                document="runtime.package_target_contracts",
                path=path,
                expected="non-empty string sequence",
                actual=None,
            )
        )
        return None
    if not isinstance(value, (list, tuple)) or not value:
        diagnostics.append(
            CompatibilityDiagnostic(
                code="package.target_contract.required_path_artifacts_invalid",
                message=(
                    "runtime generated package target contract "
                    "requiredPathArtifacts must be a non-empty sequence"
                ),
                document="runtime.package_target_contracts",
                path=path,
                expected="non-empty string sequence",
                actual=_json_type_name(value),
            )
        )
        return None
    artifacts: list[str] = []
    for artifact_index, artifact_name in enumerate(value):
        if not isinstance(artifact_name, str) or not artifact_name:
            diagnostics.append(
                CompatibilityDiagnostic(
                    code="package.target_contract.required_path_artifact_invalid",
                    message=(
                        "runtime generated package target contract "
                        "requiredPathArtifacts entries must be non-empty strings"
                    ),
                    document="runtime.package_target_contracts",
                    path=f"{path}[{artifact_index}]",
                    expected="non-empty string",
                    actual=_contract_actual_value(artifact_name),
                )
            )
            continue
        if artifact_name not in PACKAGE_PATH_ARTIFACTS:
            diagnostics.append(
                CompatibilityDiagnostic(
                    code="package.target_contract.required_path_artifact_unknown",
                    message=(
                        "runtime generated package target contract "
                        "requiredPathArtifacts entries must be known path "
                        "artifact names"
                    ),
                    document="runtime.package_target_contracts",
                    path=f"{path}[{artifact_index}]",
                    expected=sorted(PACKAGE_PATH_ARTIFACTS),
                    actual=artifact_name,
                )
            )
            continue
        if artifact_name in artifacts:
            diagnostics.append(
                CompatibilityDiagnostic(
                    code="package.target_contract.required_path_artifact_duplicate",
                    message=(
                        "runtime generated package target contract "
                        "requiredPathArtifacts must not contain duplicates"
                    ),
                    document="runtime.package_target_contracts",
                    path=f"{path}[{artifact_index}]",
                    expected="unique artifact name",
                    actual=artifact_name,
                )
            )
            continue
        artifacts.append(artifact_name)
    if len(artifacts) != len(value):
        return None
    return tuple(artifacts)


def _generated_allowed_native_binary_statuses(
    target: str,
    *,
    requires_native_status: bool,
    allows_planned_native: bool,
) -> tuple[str, ...]:
    if not requires_native_status:
        return ()
    legacy_statuses = _LEGACY_NATIVE_BINARY_STATUSES_BY_TARGET.get(target)
    if legacy_statuses is not None:
        return legacy_statuses
    if allows_planned_native:
        return ("planned", "emitted", "validated")
    return ("emitted", "validated")


@dataclass(frozen=True)
class CompatibilityDiagnostic:
    """Structured runtime package compatibility diagnostic."""

    code: str
    message: str
    severity: str = "error"
    document: str | None = None
    artifact: str | None = None
    path: str | None = None
    expected: Any | None = None
    actual: Any | None = None

    def to_summary(self) -> dict[str, Any]:
        summary: dict[str, Any] = {
            "severity": self.severity,
            "code": self.code,
            "message": self.message,
        }
        if self.document is not None:
            summary["document"] = self.document
        if self.artifact is not None:
            summary["artifact"] = self.artifact
        if self.path is not None:
            summary["path"] = self.path
        if self.expected is not None:
            summary["expected"] = self.expected
        if self.actual is not None:
            summary["actual"] = self.actual
        return summary


@dataclass(frozen=True)
class PackageArtifactCompatibility:
    """Runtime compatibility decision for one manifest artifact."""

    name: str
    decision: str
    reason: str
    message: str
    required: bool
    selected: bool
    artifact: Artifact | None
    diagnostics: tuple[CompatibilityDiagnostic, ...] = ()

    def to_summary(self) -> dict[str, Any]:
        artifact_summary = (
            self.artifact.to_summary() if self.artifact is not None else None
        )
        summary: dict[str, Any] = {
            "name": self.name,
            "decision": self.decision,
            "reason": self.reason,
            "message": self.message,
            "required": self.required,
            "selected": self.selected,
            "artifact": artifact_summary,
            "diagnostics": [diagnostic.to_summary() for diagnostic in self.diagnostics],
        }
        if artifact_summary is not None:
            summary["path"] = artifact_summary["path"]
            summary["exists"] = artifact_summary["exists"]
        return summary


@dataclass(frozen=True)
class PackageCompatibilityReport:
    """Runtime package compatibility facts and diagnostics."""

    root: Path
    package_format: str
    module: str | None
    target: str | None
    loader_target: str | None
    compiler_name: str | None
    compiler_version: str | None
    manifest_schema_version: Any
    reflection_schema_version: Any
    diagnostics_schema_version: Any
    runtime_package_mode: str
    native_binary_status: Any
    target_contract: TargetArtifactContract | None
    available_artifacts: tuple[Artifact, ...]
    reflection: dict[str, Any]
    reflection_availability: dict[str, Any]
    diagnostics_availability: dict[str, Any]
    debug_metadata_availability: dict[str, Any]
    graphics_abi_availability: dict[str, Any]
    graphics_descriptor_bindings: dict[str, Any]
    target_legalization_evidence: dict[str, Any]
    diagnostics: tuple[CompatibilityDiagnostic, ...]
    package_artifact_requirements_declared: bool = False
    source_parsing_required: bool = False
    compiler_invocation_required: bool = False
    device_execution_required: bool = False
    source_inputs: tuple[str, ...] = ()

    @property
    def compatible(self) -> bool:
        return not self.reject_reasons and not self.skip_reasons

    @property
    def status(self) -> str:
        if any(
            diagnostic.code in _UNSUPPORTED_VERSION_DIAGNOSTIC_CODES
            for diagnostic in self.reject_reasons
        ):
            return "unsupported-version"
        if self.missing_artifacts:
            return "missing-artifact"
        if any(
            diagnostic.code == "package.target.loader_mismatch"
            for diagnostic in self.skip_reasons
        ):
            return "target-mismatch"
        if any(
            diagnostic.code == "package.target.unsupported"
            for diagnostic in self.reject_reasons
        ):
            return "unsupported-target"
        if self.reject_reasons:
            return "incompatible"
        if self.skip_reasons:
            return "skipped"
        artifact_availability = self.artifact_availability
        if (
            artifact_availability["source"]["available"]
            and not artifact_availability["native"]["usable"]
        ):
            return "source-only"
        return "compatible"

    @property
    def reject_reasons(self) -> tuple[CompatibilityDiagnostic, ...]:
        return tuple(
            diagnostic
            for diagnostic in self.diagnostics
            if diagnostic.severity == "error"
        )

    @property
    def skip_reasons(self) -> tuple[CompatibilityDiagnostic, ...]:
        return tuple(
            diagnostic
            for diagnostic in self.diagnostics
            if diagnostic.severity == "skip"
        )

    @property
    def required_artifacts(self) -> tuple[str, ...]:
        if self.target_contract is None:
            return ()
        return self.target_contract.required_artifacts

    @property
    def missing_artifacts(self) -> tuple[CompatibilityDiagnostic, ...]:
        return tuple(
            diagnostic
            for diagnostic in self.diagnostics
            if diagnostic.code.startswith("package.artifact.required")
        )

    @property
    def artifact_availability(self) -> dict[str, Any]:
        return _artifact_availability_summary(
            self.available_artifacts,
            native_binary_status=self.native_binary_status,
            target_contract=self.target_contract,
        )

    @property
    def available_targets(self) -> tuple[str, ...]:
        return _available_targets(self.target, self.reflection)

    @property
    def target_availability(self) -> dict[str, Any]:
        return _target_availability_summary(self.target, self.reflection)

    @property
    def workgroup_sizes(self) -> tuple[dict[str, Any], ...]:
        """Return reflected compute workgroup sizes from metadata only."""
        return _workgroup_size_records(self.reflection)

    def workgroup_size(self, stage: str, entry_point: str) -> dict[str, Any] | None:
        """Find reflected workgroup size by stage and source/backend entry name."""
        return _find_workgroup_size(self.reflection, stage, entry_point)

    def require_workgroup_size(self, stage: str, entry_point: str) -> dict[str, Any]:
        workgroup_size = self.workgroup_size(stage, entry_point)
        if workgroup_size is None:
            raise PackageReadError(
                "missing reflection workgroup size: "
                f"stage={stage} entryPoint={entry_point}"
            )
        return workgroup_size

    @property
    def workgroup_size_summary(self) -> dict[str, Any]:
        return _workgroup_size_summary(self.reflection)

    @property
    def availability_summary(self) -> dict[str, Any]:
        return {
            "schemaVersion": 1,
            "targets": self.target_availability,
            "sidecars": {
                "manifest": _manifest_availability_summary(
                    self.manifest_schema_version
                ),
                "reflection": self.reflection_availability,
                "diagnostics": self.diagnostics_availability,
                "debugMetadata": self.debug_metadata_availability,
                "graphicsAbi": self.graphics_abi_availability,
            },
            "artifacts": {
                "required": list(self.required_artifacts),
                "declared": [
                    artifact.to_summary()
                    for artifact in sorted(
                        self.available_artifacts, key=lambda artifact: artifact.name
                    )
                ],
                "runtime": self.artifact_availability,
                "missing": [
                    diagnostic.to_summary() for diagnostic in self.missing_artifacts
                ],
            },
        }

    @property
    def requirement_diagnostics(self) -> tuple[CompatibilityDiagnostic, ...]:
        return tuple(
            diagnostic
            for diagnostic in self.diagnostics
            if diagnostic.code.startswith("package.artifact_requirements.")
            or diagnostic.code.startswith("package.target_contract.")
        )

    @property
    def admission_summary(self) -> dict[str, Any]:
        return _admission_summary(self)

    @property
    def target_legalization_tool_requirements(self) -> dict[str, Any]:
        return _target_legalization_tool_requirements_summary(
            self.target_legalization_evidence,
        )

    @property
    def artifact_decisions(self) -> tuple[PackageArtifactCompatibility, ...]:
        return _artifact_compatibility_records(
            self,
            selected_artifact_name=None,
            infer_runtime_selection=True,
        )

    @property
    def accepted_artifacts(self) -> tuple[PackageArtifactCompatibility, ...]:
        return tuple(
            record
            for record in self.artifact_decisions
            if record.decision == "accepted"
        )

    @property
    def rejected_artifacts(self) -> tuple[PackageArtifactCompatibility, ...]:
        return tuple(
            record
            for record in self.artifact_decisions
            if record.decision == "rejected"
        )

    @property
    def skipped_artifacts(self) -> tuple[PackageArtifactCompatibility, ...]:
        return tuple(
            record for record in self.artifact_decisions if record.decision == "skipped"
        )

    def artifact_compatibility_summary(
        self,
        *,
        selected_artifact_name: str | None = None,
        infer_runtime_selection: bool = True,
    ) -> dict[str, Any]:
        return _artifact_compatibility_summary(
            self,
            selected_artifact_name=selected_artifact_name,
            infer_runtime_selection=infer_runtime_selection,
        )

    @property
    def diagnostic_summary(self) -> dict[str, Any]:
        by_severity: dict[str, int] = {}
        for diagnostic in self.diagnostics:
            by_severity[diagnostic.severity] = (
                by_severity.get(diagnostic.severity, 0) + 1
            )
        return {
            "status": self.status,
            "compatibilityDiagnosticCount": len(self.diagnostics),
            "rejectCount": len(self.reject_reasons),
            "skipCount": len(self.skip_reasons),
            "bySeverity": dict(sorted(by_severity.items())),
            "packageDiagnosticCount": self.diagnostics_availability["diagnosticCount"],
            "packageMaxSeverity": self.diagnostics_availability["maxSeverity"],
        }

    def require_compatible(self) -> "PackageCompatibilityReport":
        if not self.compatible:
            messages = "; ".join(
                diagnostic.message
                for diagnostic in self.diagnostics
                if diagnostic.severity in {"error", "skip"}
            )
            raise PackageReadError(f"runtime package is not compatible: {messages}")
        return self

    def to_summary(self) -> dict[str, Any]:
        requirements_summary = self.requirements_summary
        return {
            "schemaVersion": 1,
            "packageFormat": self.package_format,
            "packageVersion": self.manifest_schema_version,
            "root": str(self.root),
            "module": self.module,
            "target": self.target,
            "loaderTarget": self.loader_target,
            "availableTargets": list(self.available_targets),
            "targetAvailability": self.target_availability,
            "compatible": self.compatible,
            "status": self.status,
            "sourceParsingRequired": self.source_parsing_required,
            "compilerInvocationRequired": self.compiler_invocation_required,
            "deviceExecutionRequired": self.device_execution_required,
            "sourceInputs": list(self.source_inputs),
            "runtime": {
                "reader": "runtime.package_reader",
                "supportedPackageSchemaVersion": SUPPORTED_PACKAGE_SCHEMA_VERSION,
                "supportedDebugMetadataSchemaVersion": (
                    SUPPORTED_DEBUG_METADATA_SCHEMA_VERSION
                ),
                "metadataJsonByteLimit": RUNTIME_METADATA_JSON_BYTE_LIMIT,
                "artifactByteLimit": RUNTIME_ARTIFACT_BYTE_LIMIT,
                "artifactStreamChunkSize": RUNTIME_ARTIFACT_STREAM_CHUNK_SIZE,
            },
            "compiler": {
                "name": self.compiler_name,
                "version": self.compiler_version,
                "compatible": self._compiler_compatible(),
            },
            "schemas": {
                "manifest": {
                    "version": self.manifest_schema_version,
                    "compatible": (
                        self.manifest_schema_version == SUPPORTED_PACKAGE_SCHEMA_VERSION
                    ),
                },
                "reflection": {
                    "version": self.reflection_schema_version,
                    "compatible": (
                        self.reflection_schema_version
                        == SUPPORTED_PACKAGE_SCHEMA_VERSION
                    ),
                },
                "diagnostics": {
                    "version": self.diagnostics_schema_version,
                    "compatible": (
                        self.diagnostics_schema_version
                        == SUPPORTED_PACKAGE_SCHEMA_VERSION
                    ),
                },
            },
            "runtimePackageMode": self.runtime_package_mode,
            "nativeBinaryStatus": self.native_binary_status,
            "targetContract": (
                self.target_contract.to_summary()
                if self.target_contract is not None
                else None
            ),
            "packageArtifactRequirements": (
                self.target_contract.to_summary()
                if self.target_contract is not None
                else None
            ),
            "packageArtifactRequirementsStatus": requirements_summary,
            "requiredArtifacts": list(self.required_artifacts),
            "availableArtifacts": [
                artifact.to_summary() for artifact in self.available_artifacts
            ],
            "artifactAvailability": self.artifact_availability,
            "artifactCompatibility": self.artifact_compatibility_summary(),
            "availability": self.availability_summary,
            "admission": self.admission_summary,
            "missingArtifacts": [
                diagnostic.to_summary() for diagnostic in self.missing_artifacts
            ],
            "reflection": self.reflection_availability,
            "workgroupSizes": self.workgroup_size_summary,
            "diagnosticsMetadata": self.diagnostics_availability,
            "debugMetadata": self.debug_metadata_availability,
            "graphicsAbi": self.graphics_abi_availability,
            "graphicsDescriptorBindings": self.graphics_descriptor_bindings,
            "targetLegalizationEvidence": self.target_legalization_evidence,
            "targetLegalizationToolRequirements": (
                self.target_legalization_tool_requirements
            ),
            "diagnosticSummary": self.diagnostic_summary,
            "rejectReasons": [
                diagnostic.to_summary() for diagnostic in self.reject_reasons
            ],
            "skipReasons": [
                diagnostic.to_summary() for diagnostic in self.skip_reasons
            ],
            "diagnostics": [diagnostic.to_summary() for diagnostic in self.diagnostics],
        }

    def _compiler_compatible(self) -> bool:
        return (
            self.compiler_name == SUPPORTED_COMPILER_NAME
            and isinstance(self.compiler_version, str)
            and bool(self.compiler_version)
        )

    @property
    def requirements_summary(self) -> dict[str, Any]:
        return _requirements_admission_summary(self)


@dataclass(frozen=True)
class Artifact:
    """A package artifact declared by manifest.artifacts."""

    name: str
    package_path: str
    path: Path
    exists: bool
    size: int | None = None
    archive_path: Path | None = None
    archive_member: str | None = None

    @property
    def absolute_path(self) -> str:
        if self.archive_path is not None:
            member = self.archive_member or self.package_path
            return f"{self.archive_path}!/{member}"
        return str(self.path)

    def to_summary(self) -> dict[str, Any]:
        size = self.size
        if size is None and self.exists and self.archive_path is None:
            size = self.path.stat().st_size
        return {
            "name": self.name,
            "path": self.package_path,
            "absolutePath": self.absolute_path,
            "exists": self.exists,
            "size": size if self.exists else None,
        }

    def require_exists(self) -> "Artifact":
        if self.archive_path is not None:
            if not self.exists:
                raise PackageReadError(
                    f"manifest artifact is missing in archive: {self.name} "
                    f"({self.package_path})"
                )
            return self
        if not self.path.is_file():
            raise PackageReadError(
                f"manifest artifact is missing on disk: {self.name} "
                f"({self.package_path})"
            )
        return self

    def iter_bytes(
        self,
        *,
        chunk_size: int = RUNTIME_ARTIFACT_STREAM_CHUNK_SIZE,
        byte_limit: Any = _DEFAULT_ARTIFACT_BYTE_LIMIT,
    ) -> Iterator[bytes]:
        artifact = self.require_exists()
        yield from _iter_artifact_bytes(
            artifact,
            chunk_size=chunk_size,
            byte_limit=_resolve_artifact_byte_limit(byte_limit),
        )

    def read_bytes(self, *, byte_limit: int | None = None) -> bytes:
        return b"".join(self.iter_bytes(byte_limit=byte_limit))

    def read_text(
        self,
        *,
        encoding: str = "utf-8",
        byte_limit: int | None = None,
    ) -> str:
        if self.archive_path is not None or byte_limit is not None:
            return self.read_bytes(byte_limit=byte_limit).decode(encoding)
        return self.require_exists().path.read_text(encoding=encoding)

    def sha256(
        self,
        *,
        chunk_size: int = RUNTIME_ARTIFACT_STREAM_CHUNK_SIZE,
        byte_limit: Any = _DEFAULT_ARTIFACT_BYTE_LIMIT,
    ) -> str:
        digest = hashlib.sha256()
        for chunk in self.iter_bytes(
            chunk_size=chunk_size,
            byte_limit=_resolve_artifact_byte_limit(byte_limit),
        ):
            digest.update(chunk)
        return digest.hexdigest()


@dataclass(frozen=True)
class RuntimeArtifactSelection:
    """Deterministic loader artifact choice plus structured rejection reasons."""

    requested_target: str
    requested_package_mode: str
    package_target: str | None
    selected_package_mode: str | None
    artifact: Artifact | None
    diagnostics: tuple[CompatibilityDiagnostic, ...]
    source_parsing_required: bool = False
    compiler_invocation_required: bool = False
    device_execution_required: bool = False
    source_inputs: tuple[str, ...] = ()
    admission: dict[str, Any] | None = None

    @property
    def selected(self) -> bool:
        return (
            self.artifact is not None
            and not self.reject_reasons
            and not self.skip_reasons
        )

    @property
    def reject_reasons(self) -> tuple[CompatibilityDiagnostic, ...]:
        return tuple(
            diagnostic
            for diagnostic in self.diagnostics
            if diagnostic.severity == "error"
        )

    @property
    def skip_reasons(self) -> tuple[CompatibilityDiagnostic, ...]:
        return tuple(
            diagnostic
            for diagnostic in self.diagnostics
            if diagnostic.severity == "skip"
        )

    @property
    def missing_artifacts(self) -> tuple[CompatibilityDiagnostic, ...]:
        return tuple(
            diagnostic
            for diagnostic in self.diagnostics
            if diagnostic.code.startswith("package.artifact.")
            and diagnostic.actual == "missing"
        )

    def require_selected(self) -> Artifact:
        if self.selected and self.artifact is not None:
            return self.artifact
        messages = "; ".join(
            diagnostic.message
            for diagnostic in self.diagnostics
            if diagnostic.severity in {"error", "skip"}
        )
        if not messages:
            messages = "no runtime artifact was selected"
        raise PackageReadError(f"runtime artifact selection failed: {messages}")

    def to_summary(self) -> dict[str, Any]:
        return {
            "schemaVersion": 1,
            "requestedTarget": self.requested_target,
            "requestedPackageMode": self.requested_package_mode,
            "packageTarget": self.package_target,
            "selected": self.selected,
            "selectedPackageMode": self.selected_package_mode,
            "sourceParsingRequired": self.source_parsing_required,
            "compilerInvocationRequired": self.compiler_invocation_required,
            "deviceExecutionRequired": self.device_execution_required,
            "sourceInputs": list(self.source_inputs),
            "admission": self.admission,
            "artifact": self.artifact.to_summary()
            if self.artifact is not None
            else None,
            "missingArtifacts": [
                diagnostic.to_summary() for diagnostic in self.missing_artifacts
            ],
            "rejectReasons": [
                diagnostic.to_summary() for diagnostic in self.reject_reasons
            ],
            "skipReasons": [
                diagnostic.to_summary() for diagnostic in self.skip_reasons
            ],
            "diagnostics": [diagnostic.to_summary() for diagnostic in self.diagnostics],
        }


@dataclass(frozen=True)
class RuntimePackage:
    """Metadata a future graphics runtime can use to select package artifacts."""

    root: Path
    package_format: str
    module: str
    target: str
    manifest: dict[str, Any]
    reflection: dict[str, Any]
    diagnostics: dict[str, Any]
    debug_metadata: dict[str, Any] | None
    graphics_abi: GraphicsAbiRecord | None
    artifacts: tuple[Artifact, ...]
    native_binary_status: Any
    target_explanation: dict[str, Any] | None = None

    @property
    def package_mode(self) -> str:
        """Return the loader-visible package mode: ``native`` or ``source``."""
        return _runtime_package_mode(self.native_binary_status)

    def target_package_mode(self) -> tuple[str, str]:
        """Return ``(target, package_mode)`` for runtime target selection."""
        return (self.target, self.package_mode)

    def artifact(self, name: str) -> Artifact | None:
        for artifact in self.artifacts:
            if artifact.name == name:
                return artifact
        return None

    def require_artifact(self, name: str) -> Artifact:
        artifact = self.artifact(name)
        if artifact is None:
            raise PackageReadError(f"missing manifest artifact: {name}")
        return artifact

    def require_existing_artifact(self, name: str) -> Artifact:
        return self.require_artifact(name).require_exists()

    def native_binary_artifact(self) -> Artifact | None:
        return self.artifact("nativeBinary")

    def backend_source_artifact(self) -> Artifact | None:
        return self.artifact("backendSource")

    def debug_metadata_artifact(self) -> Artifact | None:
        return self.artifact("debugMetadata")

    def graphics_abi_artifact(self) -> Artifact | None:
        return self.artifact("graphicsAbi")

    def require_debug_metadata(self) -> dict[str, Any]:
        if self.debug_metadata is None:
            raise PackageReadError("debug metadata artifact is not available")
        return self.debug_metadata

    def debug_metadata_record(self) -> DebugMetadataRecord | None:
        if self.debug_metadata is None:
            return None
        return _debug_metadata_record(self.debug_metadata)

    def graphics_abi_record(self) -> GraphicsAbiRecord | None:
        return self.graphics_abi

    @property
    def graphics_descriptor_bindings(self) -> dict[str, Any]:
        return _graphics_descriptor_binding_summary(
            target=self.target,
            reflection=self.reflection,
            graphics_abi=self.graphics_abi,
        )

    def require_graphics_abi(self) -> GraphicsAbiRecord:
        artifact = self.graphics_abi_artifact()
        if artifact is None:
            raise PackageReadError("graphics ABI artifact is not declared")
        artifact.require_exists()
        if self.graphics_abi is None:
            raise PackageReadError("graphics ABI artifact is not available")
        return self.graphics_abi

    def runtime_artifact(self, mode: str = "auto") -> Artifact:
        """Return the artifact a loader should consume for ``mode``.

        ``auto`` selects a native binary only when ``nativeBinaryStatus`` says
        it was emitted or validated. ``native`` requires a usable native binary
        and reports planned/missing native artifacts explicitly. ``source``
        returns the generated backend source artifact.
        """
        if mode not in RUNTIME_ARTIFACT_MODES:
            raise PackageReadError(
                f"runtime artifact mode must be one of auto, native, source: {mode}"
            )
        contract = self._require_runtime_artifact_contract()
        if mode == "source":
            return self.require_existing_artifact("backendSource")
        if mode == "native":
            return self._require_native_runtime_artifact(contract)
        if self.package_mode == "native":
            return self._require_native_runtime_artifact(contract)
        return self.require_existing_artifact("backendSource")

    def entry_point(self, stage: str, name: str) -> dict[str, Any] | None:
        """Find a reflected entry point by stage and source/backend name."""
        for entry_point in self._reflection_records("entryPoints"):
            if entry_point.get("stage") != stage:
                continue
            if name in (entry_point.get("sourceName"), entry_point.get("backendName")):
                return entry_point
        return None

    def require_entry_point(self, stage: str, name: str) -> dict[str, Any]:
        entry_point = self.entry_point(stage, name)
        if entry_point is None:
            raise PackageReadError(
                f"missing reflection entry point: stage={stage} name={name}"
            )
        return entry_point

    def resource_binding(self, stage: str, name: str) -> dict[str, Any] | None:
        """Find a reflected resource binding by stage and resource name."""
        for resource in self._reflection_records("resources"):
            if resource.get("stage") == stage and resource.get("name") == name:
                return resource
        return None

    def require_resource_binding(self, stage: str, name: str) -> dict[str, Any]:
        resource = self.resource_binding(stage, name)
        if resource is None:
            raise PackageReadError(
                f"missing reflection resource binding: stage={stage} name={name}"
            )
        return resource

    def target_resource_binding(
        self,
        stage: str,
        name: str,
        *,
        target: str | None = None,
        entry_point: str | None = None,
    ) -> dict[str, Any] | None:
        """Find a target-specific reflected resource binding by stage and name."""
        expected_target = self.target if target is None else target
        for resource in self._reflection_records("targetResourceBindings"):
            if resource.get("target") != expected_target:
                continue
            if resource.get("stage") != stage or resource.get("name") != name:
                continue
            if entry_point is not None and resource.get("entryPoint") != entry_point:
                continue
            return resource
        return None

    def require_target_resource_binding(
        self,
        stage: str,
        name: str,
        *,
        target: str | None = None,
        entry_point: str | None = None,
    ) -> dict[str, Any]:
        resource = self.target_resource_binding(
            stage,
            name,
            target=target,
            entry_point=entry_point,
        )
        if resource is None:
            expected_target = self.target if target is None else target
            raise PackageReadError(
                "missing reflection target resource binding: "
                f"target={expected_target} stage={stage} name={name}"
            )
        return resource

    @property
    def workgroup_sizes(self) -> tuple[dict[str, Any], ...]:
        """Return reflected compute workgroup sizes without artifact decoding."""
        return _workgroup_size_records(self.reflection)

    def workgroup_size(self, stage: str, entry_point: str) -> dict[str, Any] | None:
        """Find reflected workgroup size by stage and source/backend entry name."""
        return _find_workgroup_size(self.reflection, stage, entry_point)

    def require_workgroup_size(self, stage: str, entry_point: str) -> dict[str, Any]:
        workgroup_size = self.workgroup_size(stage, entry_point)
        if workgroup_size is None:
            raise PackageReadError(
                "missing reflection workgroup size: "
                f"stage={stage} entryPoint={entry_point}"
            )
        return workgroup_size

    def read_artifact_bytes(self, name: str) -> bytes:
        return self.require_existing_artifact(name).read_bytes()

    def read_artifact_text(self, name: str, *, encoding: str = "utf-8") -> str:
        return self.require_existing_artifact(name).read_text(encoding=encoding)

    def target_artifact_contract(self) -> TargetArtifactContract | None:
        """Return recorded package artifact requirements or the legacy contract."""
        diagnostics: list[CompatibilityDiagnostic] = []
        contract, _diagnostics, _declared = _target_artifact_contract_from_manifest(
            target=self.target,
            manifest=self.manifest,
            diagnostics=diagnostics,
        )
        return contract

    def required_target_artifacts(self) -> tuple[str, ...]:
        contract = self.target_artifact_contract()
        if contract is None:
            return ()
        return contract.required_artifacts

    def compatibility_report(
        self, *, loader_target: str | None = None
    ) -> PackageCompatibilityReport:
        """Return runtime compatibility facts without parsing CrossGL source."""
        return _build_compatibility_report(
            root=self.root,
            module=self.module,
            target=self.target,
            manifest=self.manifest,
            reflection=self.reflection,
            diagnostics_document=self.diagnostics,
            debug_metadata=self.debug_metadata,
            graphics_abi=self.graphics_abi,
            target_explanation=self.target_explanation,
            artifacts=self.artifacts,
            native_binary_status=self.native_binary_status,
            runtime_package_mode=self.package_mode,
            package_format=self.package_format,
            loader_target=loader_target,
        )

    def select_runtime_artifact(
        self,
        *,
        target: str | None = None,
        package_mode: str = "auto",
    ) -> RuntimeArtifactSelection:
        """Select the best declared artifact for a target/package mode."""
        requested_target = self.target if target is None else target
        report = self.compatibility_report(loader_target=requested_target)
        return select_runtime_artifact(
            report,
            target=requested_target,
            package_mode=package_mode,
        )

    def require_runtime_compatible(self) -> "RuntimePackage":
        self.compatibility_report().require_compatible()
        return self

    def to_summary(self) -> dict[str, Any]:
        diagnostics = self.diagnostics.get("diagnostics", [])
        debug_metadata_record = self.debug_metadata_record()
        compatibility_report = self.compatibility_report()
        target_contract = compatibility_report.target_contract
        return {
            "schemaVersion": 1,
            "packageFormat": self.package_format,
            "root": str(self.root),
            "module": self.module,
            "target": self.target,
            "packageMode": self.package_mode,
            "nativeBinaryStatus": self.native_binary_status,
            "targetContract": (
                target_contract.to_summary() if target_contract is not None else None
            ),
            "packageArtifactRequirements": (
                target_contract.to_summary() if target_contract is not None else None
            ),
            "artifactCount": len(self.artifacts),
            "artifacts": [artifact.to_summary() for artifact in self.artifacts],
            "entryPoints": self.reflection.get("entryPoints", []),
            "workgroupSizes": list(self.workgroup_sizes),
            "diagnosticCount": len(diagnostics) if isinstance(diagnostics, list) else 0,
            "debugMetadata": _debug_metadata_availability_summary(
                self.debug_metadata_artifact(), debug_metadata_record
            ),
            "graphicsAbi": _graphics_abi_availability_summary(
                self.graphics_abi_artifact(), self.graphics_abi
            ),
            "graphicsDescriptorBindings": self.graphics_descriptor_bindings,
            "targetLegalizationEvidence": (
                compatibility_report.target_legalization_evidence
            ),
            "targetLegalizationToolRequirements": (
                compatibility_report.target_legalization_tool_requirements
            ),
        }

    def _require_runtime_artifact_contract(self) -> TargetArtifactContract:
        diagnostics: list[CompatibilityDiagnostic] = []
        contract, requirement_diagnostics, _declared = (
            _target_artifact_contract_from_manifest(
                target=self.target,
                manifest=self.manifest,
                diagnostics=diagnostics,
            )
        )
        blocking_diagnostics = tuple(
            diagnostic
            for diagnostic in requirement_diagnostics
            if diagnostic.severity == "error"
        )
        if blocking_diagnostics:
            messages = "; ".join(
                diagnostic.message for diagnostic in blocking_diagnostics
            )
            raise PackageReadError(
                f"package artifact requirements are not compatible: {messages}"
            )
        if contract is None:
            raise PackageReadError(
                f"runtime target contract is not available for target {self.target}"
            )
        return contract

    def _require_native_runtime_artifact(
        self,
        contract: TargetArtifactContract,
    ) -> Artifact:
        if self.native_binary_status == "planned":
            raise PackageReadError(
                f"native runtime artifact is only planned for target {self.target}: "
                "nativeBinaryStatus=planned"
            )
        if not _native_binary_status_is_ready(self.native_binary_status):
            raise PackageReadError(
                f"native runtime artifact is not available for target {self.target}: "
                f"nativeBinaryStatus={self.native_binary_status!r}"
            )
        if (
            _native_artifact_descriptor_required_for_runtime_artifact(
                target=self.target,
                artifacts=self.artifacts,
                native_binary_status=self.native_binary_status,
                contract=contract,
            )
            and self.artifact("nativeArtifactDescriptor") is None
        ):
            raise PackageReadError(
                "native-ready runtime artifact requires "
                "manifest.artifacts.nativeArtifactDescriptor"
            )
        if (
            _native_profile_required_for_runtime_artifact(
                target=self.target,
                artifacts=self.artifacts,
                native_binary_status=self.native_binary_status,
                contract=contract,
            )
            and self.artifact("nativeProfile") is None
        ):
            raise PackageReadError(
                "vulkan native runtime artifact requires "
                "manifest.artifacts.nativeProfile"
            )
        return self.require_existing_artifact("nativeBinary")

    def _reflection_records(self, key: str) -> tuple[dict[str, Any], ...]:
        records = self.reflection.get(key, [])
        if not isinstance(records, list):
            return ()
        return tuple(record for record in records if isinstance(record, dict))


def read_package(package_path: Path | str) -> RuntimePackage:
    source = _open_package_source(package_path)

    documents = {
        name: _read_source_json_object(source, name, root_file_name=name)
        for name in ROOT_METADATA_FILES
    }
    manifest = documents["manifest.json"]
    reflection = documents["reflection.json"]
    diagnostics = documents["diagnostics.json"]

    _require_schema_version(manifest, "manifest")
    _require_schema_version(reflection, "reflection")
    _require_schema_version(diagnostics, "diagnostics")

    module = _require_string(manifest, "module", "manifest")
    target = _require_string(manifest, "target", "manifest")
    artifacts, native_binary_status = _read_manifest_artifacts(source, manifest)

    reflection_module = reflection.get("module")
    reflection_target = reflection.get("target")
    if reflection_module != module:
        raise PackageReadError("reflection.module does not match manifest.module")
    if reflection_target != target:
        raise PackageReadError("reflection.target does not match manifest.target")

    reflection_diagnostics: list[CompatibilityDiagnostic] = []
    _append_reflection_target_binding_duplicate_diagnostics(
        reflection_diagnostics,
        target=target,
        reflection=reflection,
    )
    _append_reflection_target_abi_diagnostics(
        reflection_diagnostics,
        target=target,
        reflection=reflection,
    )
    if reflection_diagnostics:
        messages = "; ".join(
            diagnostic.message for diagnostic in reflection_diagnostics
        )
        raise PackageReadError(f"reflection target ABI is not compatible: {messages}")

    debug_metadata = _read_optional_artifact_json_object(
        source, "debugMetadata", artifacts, root_file_name="debug metadata"
    )
    graphics_abi_document = _read_optional_artifact_json_object(
        source, "graphicsAbi", artifacts, root_file_name="graphics ABI"
    )
    graphics_abi = _graphics_abi_record(graphics_abi_document, target=target)
    graphics_abi_diagnostics: list[CompatibilityDiagnostic] = []
    _append_graphics_abi_diagnostics(
        graphics_abi_diagnostics,
        module=module,
        target=target,
        reflection=reflection,
        graphics_abi=graphics_abi,
    )
    if graphics_abi_diagnostics:
        messages = "; ".join(
            diagnostic.message for diagnostic in graphics_abi_diagnostics
        )
        raise PackageReadError(f"graphics ABI is not compatible: {messages}")
    target_explanation = _read_optional_artifact_json_object(
        source,
        "targetExplanation",
        artifacts,
        root_file_name="target explanation",
    )
    descriptor_diagnostics: list[CompatibilityDiagnostic] = []
    _append_native_artifact_descriptor_diagnostics(
        descriptor_diagnostics,
        target=target,
        artifacts=tuple(artifacts),
        native_binary_status=native_binary_status,
        unreadable_documents=frozenset(),
    )
    if descriptor_diagnostics:
        messages = "; ".join(
            diagnostic.message for diagnostic in descriptor_diagnostics
        )
        raise PackageReadError(
            f"native artifact descriptor is not compatible: {messages}"
        )

    return RuntimePackage(
        root=source.root,
        package_format=source.package_format,
        module=module,
        target=target,
        manifest=manifest,
        reflection=reflection,
        diagnostics=diagnostics,
        debug_metadata=debug_metadata,
        graphics_abi=graphics_abi,
        target_explanation=target_explanation,
        artifacts=tuple(artifacts),
        native_binary_status=native_binary_status,
    )


def read_compatibility_report(
    package_path: Path | str, *, loader_target: str | None = None
) -> PackageCompatibilityReport:
    """Read a runtime compatibility report without requiring schema compatibility."""
    source = _open_package_source(package_path)
    metadata_diagnostics: list[CompatibilityDiagnostic] = []

    documents = {
        name: _read_source_json_object_for_report(
            source,
            name,
            root_file_name=name,
            diagnostics=metadata_diagnostics,
        )
        for name in ROOT_METADATA_FILES
    }
    manifest = documents["manifest.json"]
    reflection = documents["reflection.json"]
    diagnostics_document = documents["diagnostics.json"]
    unreadable_documents = _unreadable_metadata_documents(metadata_diagnostics)
    module = _optional_non_empty_string(manifest.get("module"))
    target = _optional_non_empty_string(manifest.get("target"))
    if "manifest" in unreadable_documents:
        artifacts = []
        native_binary_status = None
    else:
        artifacts, native_binary_status = _read_manifest_artifacts(
            source,
            manifest,
            diagnostics=metadata_diagnostics,
        )
    debug_metadata = _read_optional_artifact_json_object_for_report(
        source,
        "debugMetadata",
        artifacts,
        root_file_name="debug metadata",
        diagnostics=metadata_diagnostics,
    )
    target_explanation = _read_optional_artifact_json_object_for_report(
        source,
        "targetExplanation",
        artifacts,
        root_file_name="target explanation",
        diagnostics=metadata_diagnostics,
        document="targetExplanation",
        diagnostic_prefix="package.target_explanation",
        expected="JSON object target explanation metadata",
    )
    graphics_abi_document = _read_optional_artifact_json_object_for_report(
        source,
        "graphicsAbi",
        artifacts,
        root_file_name="graphics ABI",
        diagnostics=metadata_diagnostics,
        document="graphicsAbi",
        diagnostic_prefix="package.graphicsAbi",
        expected="JSON object graphics ABI metadata",
    )
    graphics_abi = _graphics_abi_record(graphics_abi_document, target=target)

    return _build_compatibility_report(
        root=source.root,
        package_format=source.package_format,
        module=module,
        target=target,
        manifest=manifest,
        reflection=reflection,
        diagnostics_document=diagnostics_document,
        debug_metadata=debug_metadata,
        graphics_abi=graphics_abi,
        target_explanation=target_explanation,
        artifacts=tuple(artifacts),
        native_binary_status=native_binary_status,
        runtime_package_mode=_runtime_package_mode(native_binary_status),
        loader_target=loader_target,
        metadata_diagnostics=tuple(metadata_diagnostics),
        unreadable_documents=unreadable_documents,
    )


def _read_manifest_artifacts(
    source: _PackageSource,
    manifest: dict[str, Any],
    *,
    diagnostics: list[CompatibilityDiagnostic] | None = None,
) -> tuple[list[Artifact], Any]:
    strict = diagnostics is None
    artifacts_value = manifest.get("artifacts")
    if not isinstance(artifacts_value, dict) or not artifacts_value:
        if strict:
            raise PackageReadError("manifest.artifacts must be a non-empty object")
        assert diagnostics is not None
        diagnostics.append(
            CompatibilityDiagnostic(
                code=(
                    "package.artifacts.missing"
                    if artifacts_value is None
                    else "package.artifacts.invalid"
                ),
                message="manifest.artifacts must be a non-empty object",
                document="manifest",
                path="artifacts",
                expected="non-empty object",
                actual=_json_type_name(artifacts_value),
            )
        )
        return [], None

    artifacts: list[Artifact] = []
    native_binary_status: Any = None
    artifact_diagnostic_start = len(diagnostics) if diagnostics is not None else 0
    for name, artifact_path in artifacts_value.items():
        if not isinstance(name, str) or not name:
            if strict:
                raise PackageReadError(
                    "manifest.artifacts keys must be non-empty artifact names"
                )
            assert diagnostics is not None
            diagnostics.append(
                CompatibilityDiagnostic(
                    code="package.artifact.name_invalid",
                    message=(
                        "manifest.artifacts keys must be non-empty artifact names"
                    ),
                    document="manifest",
                    expected="non-empty artifact name",
                    actual=_contract_actual_value(name),
                )
            )
            continue
        if name not in MANIFEST_ARTIFACT_KEYS:
            if strict:
                raise PackageReadError(
                    f"manifest.artifacts.{name} is not a recognized artifact field"
                )
            assert diagnostics is not None
            diagnostics.append(
                CompatibilityDiagnostic(
                    code="package.artifact.unexpected",
                    message=(
                        "manifest.artifacts contains an unexpected artifact field: "
                        f"{name}"
                    ),
                    document="manifest",
                    artifact=name,
                    path=f"artifacts.{name}",
                    expected=sorted(MANIFEST_ARTIFACT_KEYS),
                    actual=name,
                )
            )
            continue
        if name == "nativeBinaryStatus":
            if not isinstance(artifact_path, str):
                if strict:
                    raise PackageReadError(
                        "manifest.artifacts.nativeBinaryStatus must be a string"
                    )
                native_binary_status = artifact_path
                continue
            native_binary_status = artifact_path
            continue
        if not isinstance(artifact_path, str):
            if strict:
                raise PackageReadError("manifest.artifacts must map strings to strings")
            assert diagnostics is not None
            diagnostics.append(
                CompatibilityDiagnostic(
                    code="package.artifact.path_invalid",
                    message="manifest.artifacts must map artifact names to strings",
                    document="manifest",
                    artifact=name if isinstance(name, str) else None,
                    path=f"artifacts.{name}" if isinstance(name, str) else None,
                    expected="package-relative path string",
                    actual=_json_type_name(artifact_path),
                )
            )
            continue
        try:
            if source.is_zip:
                member = _resolve_package_relative_member(
                    artifact_path, f"manifest.artifacts.{name}"
                )
                info = source.zip_info(member)
                artifacts.append(
                    Artifact(
                        name=name,
                        package_path=artifact_path,
                        path=source.root,
                        exists=info is not None,
                        size=info.file_size if info is not None else None,
                        archive_path=source.root,
                        archive_member=info.filename if info is not None else member,
                    )
                )
            else:
                resolved_path = _resolve_package_relative_path(
                    source.root, artifact_path, f"manifest.artifacts.{name}"
                )
                exists = resolved_path.is_file()
                artifacts.append(
                    Artifact(
                        name=name,
                        package_path=artifact_path,
                        path=resolved_path,
                        exists=exists,
                        size=resolved_path.stat().st_size if exists else None,
                    )
                )
        except PackageReadError as error:
            if strict:
                raise
            assert diagnostics is not None
            diagnostics.append(
                CompatibilityDiagnostic(
                    code="package.artifact.path_invalid",
                    message=str(error),
                    document="manifest",
                    artifact=name,
                    path=f"artifacts.{name}",
                    expected="package-relative path",
                    actual=artifact_path,
                )
            )

    duplicate_path_diagnostics = _duplicate_artifact_path_diagnostics(artifacts)
    if duplicate_path_diagnostics:
        if strict:
            first = duplicate_path_diagnostics[0]
            raise PackageReadError(first.message)
        assert diagnostics is not None
        diagnostics.extend(duplicate_path_diagnostics)

    if not strict:
        assert diagnostics is not None
        _append_manifest_artifact_contract_invalid_diagnostic(
            diagnostics,
            start_index=artifact_diagnostic_start,
        )

    if not artifacts:
        if strict:
            raise PackageReadError("manifest.artifacts contains no runtime artifacts")
        assert diagnostics is not None
        diagnostics.append(
            CompatibilityDiagnostic(
                code="package.artifacts.empty",
                message="manifest.artifacts contains no runtime artifacts",
                document="manifest",
                expected="at least one runtime artifact path",
                actual=sorted(artifacts_value),
            )
        )
    return artifacts, native_binary_status


def _append_manifest_artifact_contract_invalid_diagnostic(
    diagnostics: list[CompatibilityDiagnostic],
    *,
    start_index: int,
) -> None:
    contract_diagnostics = tuple(
        diagnostic
        for diagnostic in diagnostics[start_index:]
        if diagnostic.code in MANIFEST_ARTIFACT_CONTRACT_DIAGNOSTIC_CODES
    )
    if not contract_diagnostics:
        return

    diagnostics.append(
        CompatibilityDiagnostic(
            code="package.artifacts.contract_invalid",
            message=(
                "manifest.artifacts contains malformed or unsupported artifact "
                "records; runtime loaders must reject the artifact contract "
                "instead of inferring artifact roles from remaining entries"
            ),
            document="manifest",
            path="artifacts",
            expected="all artifact records use known names and package-relative paths",
            actual=[diagnostic.to_summary() for diagnostic in contract_diagnostics],
        )
    )


def _append_native_binary_status_contract_invalid_diagnostic(
    diagnostics: list[CompatibilityDiagnostic],
    *,
    start_index: int,
) -> None:
    contract_diagnostics = tuple(
        diagnostic
        for diagnostic in diagnostics[start_index:]
        if diagnostic.code in NATIVE_BINARY_STATUS_CONTRACT_DIAGNOSTIC_CODES
    )
    if not contract_diagnostics:
        return

    diagnostics.append(
        CompatibilityDiagnostic(
            code="package.artifacts.contract_invalid",
            message=(
                "manifest.artifacts.nativeBinaryStatus is malformed; runtime "
                "loaders must reject the artifact contract instead of inferring "
                "native binary readiness"
            ),
            document="manifest",
            path="artifacts.nativeBinaryStatus",
            expected="supported native binary status string",
            actual=[diagnostic.to_summary() for diagnostic in contract_diagnostics],
        )
    )


def _duplicate_artifact_path_diagnostics(
    artifacts: list[Artifact],
) -> tuple[CompatibilityDiagnostic, ...]:
    seen_paths: dict[str, str] = {}
    diagnostics: list[CompatibilityDiagnostic] = []
    for artifact in artifacts:
        path_identity = _artifact_path_identity(artifact)
        previous_name = seen_paths.get(path_identity)
        if previous_name is None:
            seen_paths[path_identity] = artifact.name
            continue
        diagnostics.append(
            CompatibilityDiagnostic(
                code="package.artifact.path_duplicate",
                message=(
                    f"manifest.artifacts.{artifact.name} reuses path declared by "
                    f"{previous_name}: {artifact.package_path}"
                ),
                document="manifest",
                artifact=artifact.name,
                path=f"artifacts.{artifact.name}",
                expected="unique package-relative path",
                actual=artifact.package_path,
            )
        )
    return tuple(diagnostics)


def _artifact_path_identity(artifact: Artifact) -> str:
    if artifact.archive_path is not None:
        return _resolve_package_relative_member(
            artifact.package_path, f"manifest.artifacts.{artifact.name}"
        )
    return str(artifact.path)


def _runtime_package_mode(native_binary_status: Any) -> str:
    if _native_binary_status_is_ready(native_binary_status):
        return "native"
    return "source"


def _target_artifact_contract_from_manifest(
    *,
    target: str | None,
    manifest: dict[str, Any],
    diagnostics: list[CompatibilityDiagnostic] | None = None,
) -> tuple[TargetArtifactContract | None, tuple[CompatibilityDiagnostic, ...], bool]:
    """Return manifest-recorded artifact requirements, falling back to v0 policy."""
    if target is None:
        return None, (), False

    if "packageArtifactRequirements" not in manifest:
        if _manifest_requires_recorded_source_free_native_requirements(manifest):
            diagnostic = CompatibilityDiagnostic(
                code="package.artifact_requirements.source_free_native_missing",
                message=(
                    "manifest.packageArtifactRequirements is required for "
                    "source-free native descriptor packages"
                ),
                document="manifest",
                path="packageArtifactRequirements",
                expected="recorded source-free native artifact requirements",
                actual="missing",
            )
            if diagnostics is None:
                raise PackageReadError(diagnostic.message)
            diagnostics.append(diagnostic)
            return None, (diagnostic,), False

        contract_diagnostics: list[CompatibilityDiagnostic] = []
        contracts = _target_artifact_contracts(diagnostics=contract_diagnostics)
        if contract_diagnostics and diagnostics is None:
            messages = "; ".join(
                diagnostic.message for diagnostic in contract_diagnostics
            )
            raise PackageReadError(messages)
        contract = contracts.get(target)
        if contract is not None:
            contract_diagnostics.append(
                CompatibilityDiagnostic(
                    code="package.artifact_requirements.legacy_v0_fallback",
                    message=(
                        "manifest.packageArtifactRequirements is missing; "
                        "using generated legacy v0 target contract as "
                        "report-only compatibility metadata"
                    ),
                    severity="note",
                    document="manifest",
                    path="packageArtifactRequirements",
                    expected="recorded package artifact requirements",
                    actual=GENERATED_CONTRACT_REQUIREMENTS_SOURCE,
                )
            )
        if diagnostics is not None:
            diagnostics.extend(contract_diagnostics)
        return contract, tuple(contract_diagnostics), False

    requirements = manifest.get("packageArtifactRequirements")
    parsed_diagnostics: list[CompatibilityDiagnostic] = []
    contract = _recorded_package_artifact_requirements_contract(
        target=target,
        manifest=manifest,
        requirements=requirements,
        diagnostics=parsed_diagnostics,
    )
    if parsed_diagnostics and diagnostics is None:
        messages = "; ".join(diagnostic.message for diagnostic in parsed_diagnostics)
        raise PackageReadError(messages)
    if diagnostics is not None:
        diagnostics.extend(parsed_diagnostics)
    return contract, tuple(parsed_diagnostics), True


def _manifest_requires_recorded_source_free_native_requirements(
    manifest: dict[str, Any],
) -> bool:
    artifacts = manifest.get("artifacts")
    if not isinstance(artifacts, dict):
        return False
    source_sidecar_artifacts = ("backendSource", "backendAssembly", "intermediate")
    return (
        "nativeBinary" in artifacts
        and "nativeArtifactDescriptor" in artifacts
        and "nativeBinaryStatus" not in artifacts
        and all(artifact not in artifacts for artifact in source_sidecar_artifacts)
    )


def _recorded_package_artifact_requirements_contract(
    *,
    target: str,
    manifest: dict[str, Any],
    requirements: Any,
    diagnostics: list[CompatibilityDiagnostic],
) -> TargetArtifactContract | None:
    start_diagnostic_count = len(diagnostics)
    if not isinstance(requirements, dict):
        diagnostics.append(
            CompatibilityDiagnostic(
                code="package.artifact_requirements.invalid",
                message="manifest.packageArtifactRequirements must be an object",
                document="manifest",
                path="packageArtifactRequirements",
                expected="object",
                actual=_json_type_name(requirements),
            )
        )
        return None

    target_contract_diagnostic_count = len(diagnostics)
    runtime_contracts = _target_artifact_contracts(diagnostics=diagnostics)
    target_contract_metadata_valid = (
        len(diagnostics) == target_contract_diagnostic_count
    )

    key_diagnostic_count = len(diagnostics)
    _append_recorded_requirement_key_diagnostics(requirements, diagnostics)
    requirement_keys_valid = len(diagnostics) == key_diagnostic_count
    required_artifacts_value = requirements.get("requiredPathArtifacts")
    required_artifacts = _recorded_required_path_artifacts(
        required_artifacts_value,
        present="requiredPathArtifacts" in requirements,
        diagnostics=diagnostics,
    )
    package_mode = _recorded_string_field(
        requirements,
        "packageMode",
        expected=("native", SOURCE_PACKAGE_MODE),
        diagnostics=diagnostics,
    )
    requirements_target = _recorded_string_field(
        requirements,
        "target",
        diagnostics=diagnostics,
    )
    requires_native_status = _recorded_bool_field(
        requirements,
        "requiresNativeBinaryStatus",
        diagnostics=diagnostics,
    )
    allows_planned_native = _recorded_bool_field(
        requirements,
        "allowsPlannedNativeBinary",
        diagnostics=diagnostics,
    )
    allows_planned_source_evidence = _recorded_bool_field(
        requirements,
        "allowsPlannedNativeSourceEvidence",
        diagnostics=diagnostics,
    )
    evidence_ids = _recorded_optional_string_array_field(
        requirements,
        "evidenceIds",
        diagnostics=diagnostics,
    )

    if requirements_target is not None and requirements_target != target:
        diagnostics.append(
            CompatibilityDiagnostic(
                code="package.artifact_requirements.target_mismatch",
                message="manifest.packageArtifactRequirements.target must match manifest.target",
                document="manifest",
                path="packageArtifactRequirements.target",
                expected=target,
                actual=requirements_target,
            )
        )

    if (
        requirements_target is not None
        and requirement_keys_valid
        and target_contract_metadata_valid
        and requirements_target not in runtime_contracts
    ):
        diagnostics.append(
            CompatibilityDiagnostic(
                code="package.artifact_requirements.target_unsupported",
                message=(
                    "manifest.packageArtifactRequirements.target is not "
                    "supported by this runtime"
                ),
                document="manifest",
                path="packageArtifactRequirements.target",
                expected=sorted(runtime_contracts),
                actual=requirements_target,
            )
        )

    if allows_planned_source_evidence is True and allows_planned_native is False:
        diagnostics.append(
            CompatibilityDiagnostic(
                code="package.artifact_requirements.planned_source_evidence_invalid",
                message=(
                    "manifest.packageArtifactRequirements."
                    "allowsPlannedNativeSourceEvidence requires "
                    "allowsPlannedNativeBinary"
                ),
                document="manifest",
                path="packageArtifactRequirements.allowsPlannedNativeSourceEvidence",
                expected="allowsPlannedNativeBinary true",
                actual=True,
            )
        )

    if required_artifacts is not None and "nativeBinary" not in required_artifacts:
        diagnostics.append(
            CompatibilityDiagnostic(
                code="package.artifact_requirements.native_binary_missing",
                message=(
                    "manifest.packageArtifactRequirements.requiredPathArtifacts "
                    "must include nativeBinary"
                ),
                document="manifest",
                path="packageArtifactRequirements.requiredPathArtifacts",
                expected="requiredPathArtifacts includes nativeBinary",
                actual=list(required_artifacts),
            )
        )

    if (
        package_mode == SOURCE_PACKAGE_MODE
        and required_artifacts is not None
        and "backendSource" not in required_artifacts
    ):
        diagnostics.append(
            CompatibilityDiagnostic(
                code="package.artifact_requirements.source_package_artifact_missing",
                message=(
                    "manifest.packageArtifactRequirements.requiredPathArtifacts "
                    "must include backendSource for source-package mode"
                ),
                document="manifest",
                path="packageArtifactRequirements.requiredPathArtifacts",
                expected="requiredPathArtifacts includes backendSource",
                actual=list(required_artifacts),
            )
        )

    if package_mode == SOURCE_PACKAGE_MODE and requires_native_status is False:
        diagnostics.append(
            CompatibilityDiagnostic(
                code="package.artifact_requirements.source_package_status_invalid",
                message=(
                    "manifest.packageArtifactRequirements.source-package mode "
                    "requires requiresNativeBinaryStatus"
                ),
                document="manifest",
                path="packageArtifactRequirements.requiresNativeBinaryStatus",
                expected=True,
                actual=False,
            )
        )

    if package_mode == "native" and requires_native_status is True:
        diagnostics.append(
            CompatibilityDiagnostic(
                code="package.artifact_requirements.native_status_invalid",
                message=(
                    "manifest.packageArtifactRequirements.native mode must not "
                    "require nativeBinaryStatus"
                ),
                document="manifest",
                path="packageArtifactRequirements.requiresNativeBinaryStatus",
                expected=False,
                actual=True,
            )
        )

    if allows_planned_native is True and requires_native_status is False:
        diagnostics.append(
            CompatibilityDiagnostic(
                code="package.artifact_requirements.planned_native_status_invalid",
                message=(
                    "manifest.packageArtifactRequirements."
                    "allowsPlannedNativeBinary requires "
                    "requiresNativeBinaryStatus"
                ),
                document="manifest",
                path="packageArtifactRequirements.allowsPlannedNativeBinary",
                expected="requiresNativeBinaryStatus true",
                actual=True,
            )
        )

    if package_mode == "native" and allows_planned_native is True:
        diagnostics.append(
            CompatibilityDiagnostic(
                code="package.artifact_requirements.planned_native_mode_invalid",
                message=(
                    "manifest.packageArtifactRequirements.native mode must not "
                    "allow planned native binaries"
                ),
                document="manifest",
                path="packageArtifactRequirements.allowsPlannedNativeBinary",
                expected=False,
                actual=True,
            )
        )

    if package_mode == "native" and allows_planned_source_evidence is True:
        diagnostics.append(
            CompatibilityDiagnostic(
                code="package.artifact_requirements.planned_source_mode_invalid",
                message=(
                    "manifest.packageArtifactRequirements.native mode must not "
                    "allow planned native source evidence"
                ),
                document="manifest",
                path=("packageArtifactRequirements.allowsPlannedNativeSourceEvidence"),
                expected=False,
                actual=True,
            )
        )

    source_free_native_descriptor = (
        target_contract_metadata_valid
        and requirement_keys_valid
        and requirements_target == target
        and requirements_target in runtime_contracts
        and _recorded_requirements_are_source_free_native_descriptor(
            target_contract=runtime_contracts[requirements_target],
            manifest=manifest,
            required_artifacts=required_artifacts,
            package_mode=package_mode,
            requires_native_status=requires_native_status,
            allows_planned_native=allows_planned_native,
            allows_planned_source_evidence=allows_planned_source_evidence,
        )
    )

    if (
        target_contract_metadata_valid
        and requirement_keys_valid
        and requirements_target == target
        and requirements_target in runtime_contracts
        and not source_free_native_descriptor
    ):
        _append_recorded_requirement_target_contract_diagnostics(
            target_contract=runtime_contracts[requirements_target],
            required_artifacts=required_artifacts,
            package_mode=package_mode,
            requires_native_status=requires_native_status,
            allows_planned_native=allows_planned_native,
            allows_planned_source_evidence=allows_planned_source_evidence,
            diagnostics=diagnostics,
        )

    if any(
        value is None
        for value in (
            required_artifacts,
            package_mode,
            requirements_target,
            requires_native_status,
            allows_planned_native,
            allows_planned_source_evidence,
            evidence_ids,
        )
    ):
        return None

    if len(diagnostics) != start_diagnostic_count:
        return None

    allowed_statuses: tuple[str, ...]
    if requires_native_status:
        allowed_statuses = (
            ("planned", "emitted", "validated")
            if allows_planned_native
            else ("emitted", "validated")
        )
    else:
        allowed_statuses = ()

    return TargetArtifactContract(
        target=target,
        package_mode=package_mode,
        required_artifacts=required_artifacts,
        native_binary_status_required=requires_native_status,
        allowed_native_binary_statuses=allowed_statuses,
        planned_native_binary_may_be_absent=allows_planned_native,
        allows_planned_native_source_evidence=allows_planned_source_evidence,
        requirements_source="manifest",
    )


def _recorded_requirements_are_source_free_native_descriptor(
    *,
    target_contract: TargetArtifactContract,
    manifest: dict[str, Any],
    required_artifacts: tuple[str, ...] | None,
    package_mode: str | None,
    requires_native_status: bool | None,
    allows_planned_native: bool | None,
    allows_planned_source_evidence: bool | None,
) -> bool:
    artifacts = manifest.get("artifacts")
    if not isinstance(artifacts, dict):
        return False

    return (
        target_contract.target in SOURCE_FREE_NATIVE_RUNTIME_TARGETS
        and target_contract.package_mode in (SOURCE_PACKAGE_MODE, "native")
        and package_mode == "native"
        and required_artifacts == ("nativeBinary",)
        and requires_native_status is False
        and allows_planned_native is False
        and allows_planned_source_evidence is False
        and "nativeBinary" in artifacts
        and "nativeArtifactDescriptor" in artifacts
        and "nativeBinaryStatus" not in artifacts
        and "backendSource" not in artifacts
        and "backendAssembly" not in artifacts
        and "intermediate" not in artifacts
    )


def _append_recorded_requirement_target_contract_diagnostics(
    *,
    target_contract: TargetArtifactContract,
    required_artifacts: tuple[str, ...] | None,
    package_mode: str | None,
    requires_native_status: bool | None,
    allows_planned_native: bool | None,
    allows_planned_source_evidence: bool | None,
    diagnostics: list[CompatibilityDiagnostic],
) -> None:
    target = target_contract.target
    comparisons: tuple[tuple[str, str, Any, Any, str], ...] = (
        (
            "packageMode",
            "package_mode",
            target_contract.package_mode,
            package_mode,
            (
                "manifest.packageArtifactRequirements.packageMode must match "
                "the runtime v0 target contract for manifest.target"
            ),
        ),
        (
            "requiresNativeBinaryStatus",
            "requires_native_binary_status",
            target_contract.native_binary_status_required,
            requires_native_status,
            (
                "manifest.packageArtifactRequirements."
                "requiresNativeBinaryStatus must match the runtime v0 target "
                "contract for manifest.target"
            ),
        ),
        (
            "allowsPlannedNativeBinary",
            "allows_planned_native_binary",
            target_contract.planned_native_binary_may_be_absent,
            allows_planned_native,
            (
                "manifest.packageArtifactRequirements."
                "allowsPlannedNativeBinary must match the runtime v0 target "
                "contract for manifest.target"
            ),
        ),
        (
            "allowsPlannedNativeSourceEvidence",
            "allows_planned_native_source_evidence",
            target_contract.allows_planned_native_source_evidence,
            allows_planned_source_evidence,
            (
                "manifest.packageArtifactRequirements."
                "allowsPlannedNativeSourceEvidence must match the runtime v0 "
                "target contract for manifest.target"
            ),
        ),
    )
    for manifest_field, code_field, expected, actual, message in comparisons:
        if actual is None or actual == expected:
            continue
        diagnostics.append(
            CompatibilityDiagnostic(
                code=f"package.artifact_requirements.{code_field}_mismatch",
                message=message,
                document="manifest",
                path=f"packageArtifactRequirements.{manifest_field}",
                expected={
                    "target": target,
                    "requirementsSource": GENERATED_CONTRACT_REQUIREMENTS_SOURCE,
                    "value": expected,
                },
                actual=actual,
            )
        )
    if required_artifacts is not None and frozenset(required_artifacts) != frozenset(
        target_contract.required_artifacts
    ):
        diagnostics.append(
            CompatibilityDiagnostic(
                code="package.artifact_requirements.required_path_artifacts_mismatch",
                message=(
                    "manifest.packageArtifactRequirements.requiredPathArtifacts "
                    "must match the runtime v0 target contract for manifest.target"
                ),
                document="manifest",
                path="packageArtifactRequirements.requiredPathArtifacts",
                expected={
                    "target": target,
                    "requirementsSource": GENERATED_CONTRACT_REQUIREMENTS_SOURCE,
                    "value": list(target_contract.required_artifacts),
                },
                actual=list(required_artifacts),
            )
        )


def _append_recorded_requirement_key_diagnostics(
    requirements: dict[str, Any],
    diagnostics: list[CompatibilityDiagnostic],
) -> None:
    for field in sorted(set(requirements) - PACKAGE_ARTIFACT_REQUIREMENT_KEYS):
        if field in PACKAGE_ARTIFACT_REQUIREMENT_SOURCE_FIELDS:
            diagnostics.append(
                CompatibilityDiagnostic(
                    code=(
                        f"package.artifact_requirements.{_snake_case(field)}_invalid"
                    ),
                    message=(
                        "manifest.packageArtifactRequirements must not declare "
                        f"{field}; the runtime derives the contract source"
                    ),
                    document="manifest",
                    path=f"packageArtifactRequirements.{field}",
                    expected="absent; runtime-derived contract source",
                    actual=_contract_actual_value(requirements.get(field)),
                )
            )
            continue
        if field == "schemaVersion":
            diagnostics.append(
                CompatibilityDiagnostic(
                    code="package.artifact_requirements.schema_incompatible",
                    message=(
                        "manifest.packageArtifactRequirements.schemaVersion "
                        "is not supported by this runtime"
                    ),
                    document="manifest",
                    path="packageArtifactRequirements.schemaVersion",
                    expected="absent in manifest schema v1",
                    actual=requirements.get(field),
                )
            )
            continue
        diagnostics.append(
            CompatibilityDiagnostic(
                code="package.artifact_requirements.unexpected_field",
                message=(
                    "manifest.packageArtifactRequirements contains an "
                    f"unexpected field: {field}"
                ),
                document="manifest",
                path=f"packageArtifactRequirements.{field}",
                expected=sorted(PACKAGE_ARTIFACT_REQUIREMENT_KEYS),
                actual=field,
            )
        )


def _recorded_required_path_artifacts(
    value: Any,
    *,
    present: bool,
    diagnostics: list[CompatibilityDiagnostic],
) -> tuple[str, ...] | None:
    path = "packageArtifactRequirements.requiredPathArtifacts"
    if not present:
        diagnostics.append(
            CompatibilityDiagnostic(
                code="package.artifact_requirements.required_path_artifacts_missing",
                message=(
                    "manifest.packageArtifactRequirements.requiredPathArtifacts "
                    "is required"
                ),
                document="manifest",
                path=path,
                expected="non-empty string array",
                actual=None,
            )
        )
        return None
    if not isinstance(value, list) or not value:
        diagnostics.append(
            CompatibilityDiagnostic(
                code="package.artifact_requirements.required_path_artifacts_invalid",
                message=(
                    "manifest.packageArtifactRequirements.requiredPathArtifacts "
                    "must be a non-empty array"
                ),
                document="manifest",
                path=path,
                expected="non-empty string array",
                actual=_json_type_name(value),
            )
        )
        return None
    artifacts: list[str] = []
    for index, artifact_name in enumerate(value):
        if not isinstance(artifact_name, str) or not artifact_name:
            diagnostics.append(
                CompatibilityDiagnostic(
                    code=(
                        "package.artifact_requirements.required_path_artifact_invalid"
                    ),
                    message=(
                        "manifest.packageArtifactRequirements."
                        "requiredPathArtifacts entries must be non-empty strings"
                    ),
                    document="manifest",
                    path=f"{path}[{index}]",
                    expected="non-empty string",
                    actual=_contract_actual_value(artifact_name),
                )
            )
            continue
        if artifact_name not in PACKAGE_PATH_ARTIFACTS:
            diagnostics.append(
                CompatibilityDiagnostic(
                    code=(
                        "package.artifact_requirements.required_path_artifact_unknown"
                    ),
                    message=(
                        "manifest.packageArtifactRequirements."
                        "requiredPathArtifacts entries must be known path "
                        "artifact names"
                    ),
                    document="manifest",
                    path=f"{path}[{index}]",
                    expected=sorted(PACKAGE_PATH_ARTIFACTS),
                    actual=artifact_name,
                )
            )
            continue
        if artifact_name in artifacts:
            diagnostics.append(
                CompatibilityDiagnostic(
                    code=(
                        "package.artifact_requirements.required_path_artifact_duplicate"
                    ),
                    message=(
                        "manifest.packageArtifactRequirements."
                        "requiredPathArtifacts must not contain duplicates"
                    ),
                    document="manifest",
                    path=f"{path}[{index}]",
                    expected="unique artifact name",
                    actual=artifact_name,
                )
            )
            continue
        artifacts.append(artifact_name)
    if len(artifacts) != len(value):
        return None
    return tuple(artifacts)


def _recorded_optional_string_array_field(
    requirements: dict[str, Any],
    field: str,
    *,
    diagnostics: list[CompatibilityDiagnostic],
) -> tuple[str, ...] | None:
    if field not in requirements:
        return ()
    path = f"packageArtifactRequirements.{field}"
    value = requirements.get(field)
    if not isinstance(value, list) or not value:
        diagnostics.append(
            CompatibilityDiagnostic(
                code=f"package.artifact_requirements.{_snake_case(field)}_invalid",
                message=(
                    f"manifest.packageArtifactRequirements.{field} must be "
                    "a non-empty array"
                ),
                document="manifest",
                path=path,
                expected="non-empty string array",
                actual=_json_type_name(value),
            )
        )
        return None
    entries: list[str] = []
    for index, entry in enumerate(value):
        if not isinstance(entry, str) or not entry:
            code = f"package.artifact_requirements.{_snake_case(field)}_entry_invalid"
            diagnostics.append(
                CompatibilityDiagnostic(
                    code=code,
                    message=(
                        f"manifest.packageArtifactRequirements.{field} entries "
                        "must be non-empty strings"
                    ),
                    document="manifest",
                    path=f"{path}[{index}]",
                    expected="non-empty string",
                    actual=_contract_actual_value(entry),
                )
            )
            continue
        if entry in entries:
            code = f"package.artifact_requirements.{_snake_case(field)}_duplicate"
            diagnostics.append(
                CompatibilityDiagnostic(
                    code=code,
                    message=(
                        f"manifest.packageArtifactRequirements.{field} must not "
                        "contain duplicates"
                    ),
                    document="manifest",
                    path=f"{path}[{index}]",
                    expected="unique string",
                    actual=entry,
                )
            )
            continue
        entries.append(entry)
    if len(entries) != len(value):
        return None
    return tuple(entries)


def _recorded_string_field(
    requirements: dict[str, Any],
    field: str,
    *,
    expected: tuple[str, ...] | None = None,
    diagnostics: list[CompatibilityDiagnostic],
) -> str | None:
    path = f"packageArtifactRequirements.{field}"
    if field not in requirements:
        diagnostics.append(
            CompatibilityDiagnostic(
                code=f"package.artifact_requirements.{_snake_case(field)}_missing",
                message=f"manifest.packageArtifactRequirements.{field} is required",
                document="manifest",
                path=path,
                expected=list(expected) if expected is not None else "non-empty string",
                actual=None,
            )
        )
        return None
    value = requirements.get(field)
    if (
        not isinstance(value, str)
        or not value
        or (expected is not None and value not in expected)
    ):
        diagnostics.append(
            CompatibilityDiagnostic(
                code=f"package.artifact_requirements.{_snake_case(field)}_invalid",
                message=f"manifest.packageArtifactRequirements.{field} is invalid",
                document="manifest",
                path=path,
                expected=list(expected) if expected is not None else "non-empty string",
                actual=_contract_actual_value(value),
            )
        )
        return None
    return value


def _recorded_bool_field(
    requirements: dict[str, Any],
    field: str,
    *,
    diagnostics: list[CompatibilityDiagnostic],
) -> bool | None:
    if field not in requirements:
        diagnostics.append(
            CompatibilityDiagnostic(
                code=f"package.artifact_requirements.{_snake_case(field)}_missing",
                message=f"manifest.packageArtifactRequirements.{field} is required",
                document="manifest",
                path=f"packageArtifactRequirements.{field}",
                expected="boolean",
                actual=None,
            )
        )
        return None
    value = requirements.get(field)
    if not isinstance(value, bool):
        diagnostics.append(
            CompatibilityDiagnostic(
                code=f"package.artifact_requirements.{_snake_case(field)}_invalid",
                message=f"manifest.packageArtifactRequirements.{field} must be a boolean",
                document="manifest",
                path=f"packageArtifactRequirements.{field}",
                expected="boolean",
                actual=_json_type_name(value),
            )
        )
        return None
    return value


def _snake_case(value: str) -> str:
    result: list[str] = []
    for character in value:
        if character.isupper():
            result.append("_")
            result.append(character.lower())
        else:
            result.append(character)
    return "".join(result).lstrip("_")


def select_runtime_artifact(
    report: PackageCompatibilityReport,
    *,
    target: str,
    package_mode: str = "auto",
) -> RuntimeArtifactSelection:
    """Select one loadable artifact from package metadata only.

    ``auto`` prefers a usable native binary when package metadata proves one is
    ready; otherwise it falls back to the target's source-package artifact only
    for source-package targets. ``native`` requires a ready ``nativeBinary``.
    ``source-package`` requires a generated backend source artifact and does not
    select optional native binaries.
    """
    if not isinstance(target, str) or not target:
        raise PackageReadError("target must be a non-empty string")

    requested_mode = _normalize_runtime_artifact_selection_mode(package_mode)
    diagnostics = list(report.diagnostics)
    diagnostics.extend(
        _runtime_artifact_selection_context_diagnostics(
            report=report,
            requested_target=target,
        )
    )
    selected_mode: str | None = None
    artifact: Artifact | None = None

    if not _has_blocking_diagnostics(diagnostics):
        if report.target != target:
            diagnostics.append(
                CompatibilityDiagnostic(
                    code="package.target.loader_mismatch",
                    message=(
                        f"package target {report.target} does not match loader "
                        f"target {target}"
                    ),
                    severity="skip",
                    document="manifest",
                    expected=target,
                    actual=report.target,
                )
            )
        elif report.target_contract is None:
            diagnostics.append(
                CompatibilityDiagnostic(
                    code="package.target.unsupported",
                    message=f"runtime does not have a target contract for {target}",
                    document="manifest",
                    expected=sorted(_target_artifact_contracts()),
                    actual=target,
                )
            )
        else:
            selected_mode, artifact, selection_diagnostics = (
                _select_runtime_artifact_candidate(report, requested_mode)
            )
            diagnostics.extend(selection_diagnostics)
            if selection_diagnostics:
                artifact = None

    admission = _runtime_artifact_selection_admission_summary(
        report=report,
        requested_target=target,
        requested_mode=requested_mode,
        selected_mode=selected_mode if artifact is not None else None,
        artifact=artifact,
        diagnostics=tuple(diagnostics),
    )
    return RuntimeArtifactSelection(
        requested_target=target,
        requested_package_mode=requested_mode,
        package_target=report.target,
        selected_package_mode=selected_mode if artifact is not None else None,
        artifact=artifact,
        diagnostics=tuple(diagnostics),
        admission=admission,
    )


def _build_compatibility_report(
    *,
    root: Path,
    package_format: str,
    module: str | None,
    target: str | None,
    manifest: dict[str, Any],
    reflection: dict[str, Any],
    diagnostics_document: dict[str, Any],
    debug_metadata: dict[str, Any] | None,
    graphics_abi: GraphicsAbiRecord | None,
    target_explanation: dict[str, Any] | None,
    artifacts: tuple[Artifact, ...],
    native_binary_status: Any,
    runtime_package_mode: str,
    loader_target: str | None,
    metadata_diagnostics: tuple[CompatibilityDiagnostic, ...] = (),
    unreadable_documents: frozenset[str] = frozenset(),
) -> PackageCompatibilityReport:
    diagnostics: list[CompatibilityDiagnostic] = list(metadata_diagnostics)
    compiler_name, compiler_version = (
        (None, None)
        if "manifest" in unreadable_documents
        else _read_compiler_metadata(manifest, diagnostics)
    )
    _append_schema_diagnostics(
        diagnostics,
        manifest=manifest,
        reflection=reflection,
        diagnostics_document=diagnostics_document,
        unreadable_documents=unreadable_documents,
    )
    _append_diagnostics_document_diagnostics(
        diagnostics,
        diagnostics_document=diagnostics_document,
        unreadable_documents=unreadable_documents,
    )
    _append_identity_diagnostics(
        diagnostics,
        manifest=manifest,
        module=module,
        target=target,
        reflection=reflection,
        loader_target=loader_target,
        unreadable_documents=unreadable_documents,
    )
    _append_reflection_consistency_diagnostics(
        diagnostics,
        target=target,
        reflection=reflection,
        artifacts=artifacts,
        unreadable_documents=unreadable_documents,
    )
    _append_native_profile_metadata_diagnostics(
        diagnostics,
        target=target,
        artifacts=artifacts,
        unreadable_documents=unreadable_documents,
    )
    _append_graphics_abi_diagnostics(
        diagnostics,
        module=module,
        target=target,
        reflection=reflection,
        graphics_abi=graphics_abi,
        unreadable_documents=unreadable_documents,
    )

    contract: TargetArtifactContract | None = None
    requirements_declared = False
    if "manifest" in unreadable_documents:
        contract = None
    else:
        contract, _requirement_diagnostics, requirements_declared = (
            _target_artifact_contract_from_manifest(
                target=target,
                manifest=manifest,
                diagnostics=diagnostics,
            )
        )
        target_contract_metadata_invalid = any(
            diagnostic.code.startswith("package.target_contract.")
            for diagnostic in _requirement_diagnostics
        )
        native_status_diagnostic_start = len(diagnostics)
        diagnostics.extend(
            _native_binary_status_diagnostics(
                native_binary_status,
                contract=contract,
            )
        )
        _append_native_binary_status_contract_invalid_diagnostic(
            diagnostics,
            start_index=native_status_diagnostic_start,
        )
        if (
            target
            and contract is None
            and not requirements_declared
            and not target_contract_metadata_invalid
            and not _requirement_diagnostics
        ):
            diagnostics.append(
                CompatibilityDiagnostic(
                    code="package.target.unsupported",
                    message=f"runtime does not have a target contract for {target}",
                    document="manifest",
                    expected=sorted(_target_artifact_contracts()),
                    actual=target,
                )
            )
        elif contract is not None:
            diagnostics.extend(
                _target_contract_diagnostics(
                    target=target,
                    artifacts=artifacts,
                    native_binary_status=native_binary_status,
                    contract=contract,
                )
            )

    _append_native_artifact_descriptor_diagnostics(
        diagnostics,
        target=target,
        artifacts=artifacts,
        native_binary_status=native_binary_status,
        target_contract=contract,
        unreadable_documents=unreadable_documents,
    )

    debug_metadata_record = (
        _debug_metadata_record(debug_metadata) if debug_metadata is not None else None
    )
    debug_metadata_artifact = _artifact_by_name(artifacts, "debugMetadata")
    graphics_abi_artifact = _artifact_by_name(artifacts, "graphicsAbi")
    if debug_metadata_record is not None and not debug_metadata_record.compatible:
        debug_schema_version = debug_metadata_record.schema_version
        debug_schema_artifact_path = (
            debug_metadata_artifact.package_path
            if debug_metadata_artifact is not None
            else None
        )
        if debug_schema_version is None:
            diagnostics.append(
                CompatibilityDiagnostic(
                    code="package.debug_metadata.schema_version_missing",
                    message="debug metadata schemaVersion is required",
                    document="debugMetadata",
                    artifact="debugMetadata",
                    path=debug_schema_artifact_path,
                    expected=SUPPORTED_DEBUG_METADATA_SCHEMA_VERSION,
                    actual="missing",
                )
            )
        elif _schema_version_is_malformed(debug_schema_version):
            diagnostics.append(
                CompatibilityDiagnostic(
                    code="package.debug_metadata.schema_version_invalid",
                    message="debug metadata schemaVersion must be an integer",
                    document="debugMetadata",
                    artifact="debugMetadata",
                    path=debug_schema_artifact_path,
                    expected=SUPPORTED_DEBUG_METADATA_SCHEMA_VERSION,
                    actual=_contract_actual_value(debug_schema_version),
                )
            )
        else:
            diagnostics.append(
                CompatibilityDiagnostic(
                    code="package.debug_metadata.schema_incompatible",
                    message=(
                        "debug metadata schemaVersion is not supported by this runtime"
                    ),
                    document="debugMetadata",
                    artifact="debugMetadata",
                    path=debug_schema_artifact_path,
                    expected=SUPPORTED_DEBUG_METADATA_SCHEMA_VERSION,
                    actual=debug_schema_version,
                )
            )

    target_legalization_evidence = _target_legalization_evidence_summary(
        diagnostics,
        target=target,
        target_contract=contract,
        manifest=manifest,
        artifacts=artifacts,
        debug_metadata=debug_metadata,
        target_explanation=target_explanation,
        unreadable_documents=unreadable_documents,
    )

    return PackageCompatibilityReport(
        root=root,
        package_format=package_format,
        module=module,
        target=target,
        loader_target=loader_target,
        compiler_name=compiler_name,
        compiler_version=compiler_version,
        manifest_schema_version=manifest.get("schemaVersion"),
        reflection_schema_version=reflection.get("schemaVersion"),
        diagnostics_schema_version=diagnostics_document.get("schemaVersion"),
        runtime_package_mode=runtime_package_mode,
        native_binary_status=native_binary_status,
        target_contract=contract,
        available_artifacts=artifacts,
        reflection=reflection,
        reflection_availability=_reflection_availability_summary(reflection),
        diagnostics_availability=_diagnostics_availability_summary(
            diagnostics_document
        ),
        debug_metadata_availability=_debug_metadata_availability_summary(
            debug_metadata_artifact, debug_metadata_record
        ),
        graphics_abi_availability=_graphics_abi_availability_summary(
            graphics_abi_artifact,
            graphics_abi,
        ),
        graphics_descriptor_bindings=_graphics_descriptor_binding_summary(
            target=target,
            reflection=reflection,
            graphics_abi=graphics_abi,
        ),
        target_legalization_evidence=target_legalization_evidence,
        diagnostics=tuple(diagnostics),
        package_artifact_requirements_declared=requirements_declared,
    )


def _append_identity_diagnostics(
    diagnostics: list[CompatibilityDiagnostic],
    *,
    manifest: dict[str, Any],
    module: str | None,
    target: str | None,
    reflection: dict[str, Any],
    loader_target: str | None,
    unreadable_documents: frozenset[str] = frozenset(),
) -> None:
    manifest_readable = "manifest" not in unreadable_documents
    reflection_readable = "reflection" not in unreadable_documents

    module_value = manifest.get("module")
    if manifest_readable and (not isinstance(module_value, str) or not module_value):
        diagnostics.append(
            CompatibilityDiagnostic(
                code="package.identity.module_missing",
                message="manifest.module must be a non-empty string",
                document="manifest",
                expected="non-empty string",
                actual=_contract_actual_value(module_value),
            )
        )
    target_value = manifest.get("target")
    if manifest_readable and (not isinstance(target_value, str) or not target_value):
        diagnostics.append(
            CompatibilityDiagnostic(
                code="package.identity.target_missing",
                message="manifest.target must be a non-empty string",
                document="manifest",
                expected="non-empty string",
                actual=_contract_actual_value(target_value),
            )
        )

    reflection_module = reflection.get("module")
    if reflection_readable and module is not None and reflection_module != module:
        diagnostics.append(
            CompatibilityDiagnostic(
                code="package.identity.reflection_module_mismatch",
                message="reflection.module does not match manifest.module",
                document="reflection",
                expected=module,
                actual=reflection_module,
            )
        )

    reflection_target = reflection.get("target")
    if reflection_readable and target is not None and reflection_target != target:
        diagnostics.append(
            CompatibilityDiagnostic(
                code="package.identity.reflection_target_mismatch",
                message="reflection.target does not match manifest.target",
                document="reflection",
                expected=target,
                actual=reflection_target,
            )
        )

    if (
        manifest_readable
        and loader_target is not None
        and target
        and target != loader_target
    ):
        diagnostics.append(
            CompatibilityDiagnostic(
                code="package.target.loader_mismatch",
                message=(
                    f"package target {target} does not match loader target "
                    f"{loader_target}"
                ),
                severity="skip",
                document="manifest",
                expected=loader_target,
                actual=target,
            )
        )


def _append_reflection_consistency_diagnostics(
    diagnostics: list[CompatibilityDiagnostic],
    *,
    target: str | None,
    reflection: dict[str, Any],
    artifacts: tuple[Artifact, ...],
    unreadable_documents: frozenset[str],
) -> None:
    if (
        "manifest" in unreadable_documents
        or "reflection" in unreadable_documents
        or not target
    ):
        return

    _append_reflection_native_binary_diagnostics(
        diagnostics,
        reflection=reflection,
        artifacts=artifacts,
    )
    _append_reflection_runtime_collection_diagnostics(
        diagnostics,
        reflection=reflection,
    )
    _append_reflection_required_field_diagnostics(
        diagnostics,
        reflection=reflection,
    )
    _append_reflection_target_record_diagnostics(
        diagnostics,
        target=target,
        reflection=reflection,
    )
    _append_reflection_target_feature_evidence_diagnostics(
        diagnostics,
        reflection=reflection,
    )
    _append_reflection_target_binding_duplicate_diagnostics(
        diagnostics,
        target=target,
        reflection=reflection,
    )
    _append_reflection_target_abi_diagnostics(
        diagnostics,
        target=target,
        reflection=reflection,
    )


def _append_reflection_native_binary_diagnostics(
    diagnostics: list[CompatibilityDiagnostic],
    *,
    reflection: dict[str, Any],
    artifacts: tuple[Artifact, ...],
) -> None:
    reflection_native_binary = reflection.get("nativeBinary")
    if reflection_native_binary is None:
        diagnostics.append(
            CompatibilityDiagnostic(
                code="package.reflection.native_binary_missing",
                message="reflection.nativeBinary must be a package-relative path",
                document="reflection",
                artifact="nativeBinary",
                path="nativeBinary",
                expected="package-relative path",
                actual="missing",
            )
        )
        return
    if not isinstance(reflection_native_binary, str) or not reflection_native_binary:
        diagnostics.append(
            CompatibilityDiagnostic(
                code="package.reflection.native_binary_invalid",
                message="reflection.nativeBinary must be a package-relative path",
                document="reflection",
                artifact="nativeBinary",
                path="nativeBinary",
                expected="package-relative path",
                actual=_contract_actual_value(reflection_native_binary),
            )
        )
        return
    try:
        _resolve_package_relative_member(
            reflection_native_binary,
            "reflection.nativeBinary",
        )
    except PackageReadError as error:
        diagnostics.append(
            CompatibilityDiagnostic(
                code="package.reflection.native_binary_invalid",
                message=str(error),
                document="reflection",
                artifact="nativeBinary",
                path="nativeBinary",
                expected="package-relative path",
                actual=reflection_native_binary,
            )
        )
        return

    manifest_native_binary = _artifact_by_name(artifacts, "nativeBinary")
    if (
        manifest_native_binary is not None
        and reflection_native_binary != manifest_native_binary.package_path
    ):
        diagnostics.append(
            CompatibilityDiagnostic(
                code="package.reflection.native_binary_mismatch",
                message=(
                    "reflection.nativeBinary does not match "
                    "manifest.artifacts.nativeBinary"
                ),
                document="reflection",
                artifact="nativeBinary",
                path="nativeBinary",
                expected=manifest_native_binary.package_path,
                actual=reflection_native_binary,
            )
        )


def _append_reflection_runtime_collection_diagnostics(
    diagnostics: list[CompatibilityDiagnostic],
    *,
    reflection: dict[str, Any],
) -> None:
    for field_name, code_name in REFLECTION_RUNTIME_COLLECTIONS.items():
        value = reflection.get(field_name)
        if value is None:
            continue
        if not isinstance(value, list):
            diagnostics.append(
                CompatibilityDiagnostic(
                    code=f"package.reflection.{code_name}_invalid",
                    message=f"reflection.{field_name} must be an array",
                    document="reflection",
                    path=field_name,
                    expected="array",
                    actual=_json_type_name(value),
                )
            )
            continue

        for index, record in enumerate(value):
            if isinstance(record, dict):
                continue
            diagnostics.append(
                CompatibilityDiagnostic(
                    code=f"package.reflection.{code_name}_invalid",
                    message=f"reflection.{field_name} entries must be objects",
                    document="reflection",
                    path=f"{field_name}[{index}]",
                    expected="object",
                    actual=_json_type_name(record),
                )
            )


def _append_reflection_required_field_diagnostics(
    diagnostics: list[CompatibilityDiagnostic],
    *,
    reflection: dict[str, Any],
) -> None:
    for field_name, required_fields in REFLECTION_REQUIRED_STRING_FIELDS.items():
        code_name = REFLECTION_RUNTIME_COLLECTIONS[field_name]
        for index, record in enumerate(_json_object_list(reflection.get(field_name))):
            for required_field in required_fields:
                value = record.get(required_field)
                if isinstance(value, str) and value:
                    continue
                diagnostics.append(
                    CompatibilityDiagnostic(
                        code=(
                            f"package.reflection.{code_name}_"
                            f"{_snake_case(required_field)}_invalid"
                        ),
                        message=(
                            f"reflection.{field_name}.{required_field} must be "
                            "a non-empty string"
                        ),
                        document="reflection",
                        path=f"{field_name}[{index}].{required_field}",
                        expected="non-empty string",
                        actual=_contract_actual_value(value),
                    )
                )


def _append_reflection_target_record_diagnostics(
    diagnostics: list[CompatibilityDiagnostic],
    *,
    target: str,
    reflection: dict[str, Any],
) -> None:
    for index, record in enumerate(
        _json_object_list(reflection.get("targetResourceBindings"))
    ):
        record_target = record.get("target")
        if not isinstance(record_target, str) or not record_target:
            diagnostics.append(
                CompatibilityDiagnostic(
                    code="package.reflection.target_resource_binding_target_invalid",
                    message=(
                        "reflection.targetResourceBindings target must match "
                        "manifest.target"
                    ),
                    document="reflection",
                    path=f"targetResourceBindings[{index}].target",
                    expected=target,
                    actual=_contract_actual_value(record_target),
                )
            )
        elif record_target != target:
            diagnostics.append(
                CompatibilityDiagnostic(
                    code=("package.reflection.target_resource_binding_target_mismatch"),
                    message=(
                        "reflection.targetResourceBindings target does not match "
                        "manifest.target"
                    ),
                    document="reflection",
                    path=f"targetResourceBindings[{index}].target",
                    expected=target,
                    actual=record_target,
                )
            )

    for index, record in enumerate(_json_object_list(reflection.get("targetFeatures"))):
        record_target = record.get("target")
        if not isinstance(record_target, str) or not record_target:
            diagnostics.append(
                CompatibilityDiagnostic(
                    code="package.reflection.target_feature_target_invalid",
                    message=(
                        "reflection.targetFeatures target must match manifest.target"
                    ),
                    document="reflection",
                    path=f"targetFeatures[{index}].target",
                    expected=target,
                    actual=_contract_actual_value(record_target),
                )
            )
        elif record_target != target:
            diagnostics.append(
                CompatibilityDiagnostic(
                    code="package.reflection.target_feature_target_mismatch",
                    message=(
                        "reflection.targetFeatures target does not match "
                        "manifest.target"
                    ),
                    document="reflection",
                    path=f"targetFeatures[{index}].target",
                    expected=target,
                    actual=record_target,
                )
            )


def _append_reflection_target_feature_evidence_diagnostics(
    diagnostics: list[CompatibilityDiagnostic],
    *,
    reflection: dict[str, Any],
) -> None:
    seen: dict[str, str] = {}
    for feature_index, feature in enumerate(
        _json_object_list(reflection.get("targetFeatures"))
    ):
        feature_target = feature.get("target")
        if feature_target not in TARGET_FEATURE_EVIDENCE_TARGETS:
            continue
        evidence_ids = feature.get("evidenceIds", [])
        if evidence_ids is None:
            continue
        if not isinstance(evidence_ids, list):
            diagnostics.append(
                CompatibilityDiagnostic(
                    code="package.reflection.target_feature_evidence_ids_invalid",
                    message="reflection.targetFeatures evidenceIds must be an array",
                    document="reflection",
                    path=f"targetFeatures[{feature_index}].evidenceIds",
                    expected="array",
                    actual=_json_type_name(evidence_ids),
                )
            )
            continue
        for evidence_index, evidence_id in enumerate(evidence_ids):
            evidence_path = (
                f"targetFeatures[{feature_index}].evidenceIds[{evidence_index}]"
            )
            if not isinstance(evidence_id, str) or not evidence_id:
                diagnostics.append(
                    CompatibilityDiagnostic(
                        code=("package.reflection.target_feature_evidence_id_invalid"),
                        message=(
                            "reflection.targetFeatures evidenceIds entries must be "
                            "non-empty strings"
                        ),
                        document="reflection",
                        path=evidence_path,
                        expected="non-empty string",
                        actual=_contract_actual_value(evidence_id),
                    )
                )
                continue
            if evidence_id in seen:
                diagnostics.append(
                    CompatibilityDiagnostic(
                        code=(
                            "package.reflection.target_feature_evidence_id_duplicate"
                        ),
                        message=(
                            "reflection.targetFeatures evidenceIds must be unique "
                            "across targetFeatures"
                        ),
                        document="reflection",
                        path=evidence_path,
                        expected="unique target feature evidence id",
                        actual={
                            "duplicateOf": seen[evidence_id],
                            "evidenceId": evidence_id,
                        },
                    )
                )
            else:
                seen[evidence_id] = evidence_path

            match = TARGET_LEGALIZATION_TARGET_FEATURE_EVIDENCE_RE.fullmatch(
                evidence_id
            )
            if match is None:
                diagnostics.append(
                    CompatibilityDiagnostic(
                        code=("package.reflection.target_feature_evidence_id_invalid"),
                        message=(
                            "reflection.targetFeatures evidenceIds entries must be "
                            "target legalization target feature evidence ids"
                        ),
                        document="reflection",
                        path=evidence_path,
                        expected=(
                            "target-legalization.v1.<target>."
                            "{capability.required|capability.missing|"
                            "abi.required|abi.missing}.*"
                        ),
                        actual=evidence_id,
                    )
                )
                continue

            if not isinstance(feature_target, str) or not feature_target:
                continue
            expected_prefix = f"{TARGET_LEGALIZATION_EVIDENCE_PREFIX}.{feature_target}."
            if not evidence_id.startswith(expected_prefix):
                diagnostics.append(
                    CompatibilityDiagnostic(
                        code=(
                            "package.reflection."
                            "target_feature_evidence_id_target_mismatch"
                        ),
                        message=(
                            "reflection.targetFeatures evidenceIds must start with "
                            "the feature target legalization prefix"
                        ),
                        document="reflection",
                        path=evidence_path,
                        expected=expected_prefix,
                        actual=evidence_id,
                    )
                )
                continue

            capability_target = match.group("capability_target")
            if capability_target is not None and capability_target != feature_target:
                diagnostics.append(
                    CompatibilityDiagnostic(
                        code=(
                            "package.reflection."
                            "target_feature_evidence_id_capability_target_mismatch"
                        ),
                        message=(
                            "reflection.targetFeatures capability evidence target "
                            "must match the feature target"
                        ),
                        document="reflection",
                        path=evidence_path,
                        expected=feature_target,
                        actual=capability_target,
                    )
                )


def _append_reflection_target_binding_duplicate_diagnostics(
    diagnostics: list[CompatibilityDiagnostic],
    *,
    target: str,
    reflection: dict[str, Any],
) -> None:
    seen: dict[tuple[str, str, str, str | None], int] = {}
    for index, record in enumerate(
        _json_object_list(reflection.get("targetResourceBindings"))
    ):
        if record.get("target") != target:
            continue
        key = _target_resource_binding_identity(record)
        if key is None:
            continue
        if key not in seen:
            seen[key] = index
            continue
        diagnostics.append(
            CompatibilityDiagnostic(
                code="package.reflection.target_resource_binding_duplicate",
                message=(
                    "reflection.targetResourceBindings entries must be unique "
                    "for each target resource binding"
                ),
                document="reflection",
                path=f"targetResourceBindings[{index}]",
                expected={
                    "uniqueTargetResourceBinding": {
                        "target": target,
                        "stage": key[0],
                        "entryPoint": key[1],
                        "name": key[2],
                        "kind": key[3],
                    }
                },
                actual={
                    "duplicateOf": f"targetResourceBindings[{seen[key]}]",
                    "target": target,
                    "stage": key[0],
                    "entryPoint": key[1],
                    "name": key[2],
                    "kind": key[3],
                },
            )
        )


def _target_resource_binding_identity(
    record: dict[str, Any],
) -> tuple[str, str, str, str | None] | None:
    stage = record.get("stage")
    entry_point = record.get("entryPoint")
    name = record.get("name")
    kind = record.get("kind")
    if (
        not isinstance(stage, str)
        or not stage
        or not isinstance(entry_point, str)
        or not entry_point
        or not isinstance(name, str)
        or not name
    ):
        return None
    return stage, entry_point, name, kind if isinstance(kind, str) else None


def _append_reflection_target_abi_diagnostics(
    diagnostics: list[CompatibilityDiagnostic],
    *,
    target: str,
    reflection: dict[str, Any],
) -> None:
    expected = TARGET_RESOURCE_BINDING_ABI_EXPECTATIONS.get(target)
    if expected is None:
        return

    for index, record in enumerate(
        _json_object_list(reflection.get("targetResourceBindings"))
    ):
        if record.get("target") != target:
            continue
        if _target_resource_binding_abi_matches(
            target,
            record,
        ):
            continue
        diagnostics.append(
            CompatibilityDiagnostic(
                code="package.reflection.target_resource_binding_abi_invalid",
                message=(
                    "reflection.targetResourceBindings ABI metadata does not "
                    "match manifest.target"
                ),
                document="reflection",
                path=f"targetResourceBindings[{index}].abi",
                expected=expected,
                actual=_target_resource_binding_abi_actual(record),
            )
        )


def _append_graphics_abi_diagnostics(
    diagnostics: list[CompatibilityDiagnostic],
    *,
    module: str | None,
    target: str | None,
    reflection: dict[str, Any],
    graphics_abi: GraphicsAbiRecord | None,
    unreadable_documents: frozenset[str] = frozenset(),
) -> None:
    if graphics_abi is None or "graphicsAbi" in unreadable_documents:
        return

    if graphics_abi.schema_version is None:
        diagnostics.append(
            CompatibilityDiagnostic(
                code="package.graphicsAbi.schema_version_missing",
                message="graphics ABI sidecar schemaVersion is required",
                document="graphicsAbi",
                artifact="graphicsAbi",
                path="schemaVersion",
                expected=1,
                actual="missing",
            )
        )
    elif _schema_version_is_malformed(graphics_abi.schema_version):
        diagnostics.append(
            CompatibilityDiagnostic(
                code="package.graphicsAbi.schema_version_invalid",
                message="graphics ABI sidecar schemaVersion must be an integer",
                document="graphicsAbi",
                artifact="graphicsAbi",
                path="schemaVersion",
                expected=1,
                actual=_contract_actual_value(graphics_abi.schema_version),
            )
        )
    elif graphics_abi.schema_version != 1:
        diagnostics.append(
            CompatibilityDiagnostic(
                code="package.graphicsAbi.schema_incompatible",
                message="graphics ABI sidecar schemaVersion is not supported",
                document="graphicsAbi",
                artifact="graphicsAbi",
                path="schemaVersion",
                expected=1,
                actual=graphics_abi.schema_version,
            )
        )

    if not _is_non_empty_string(graphics_abi.module):
        diagnostics.append(
            CompatibilityDiagnostic(
                code="package.graphicsAbi.module_invalid",
                message="graphics ABI sidecar module must be a non-empty string",
                document="graphicsAbi",
                artifact="graphicsAbi",
                path="module",
                expected=module,
                actual=_contract_actual_value(graphics_abi.module),
            )
        )
    elif module is not None and graphics_abi.module != module:
        diagnostics.append(
            CompatibilityDiagnostic(
                code="package.graphicsAbi.module_mismatch",
                message="graphics ABI sidecar module must match manifest.module",
                document="graphicsAbi",
                artifact="graphicsAbi",
                path="module",
                expected=module,
                actual=graphics_abi.module,
            )
        )

    has_canonical_bindings = _graphics_abi_has_canonical_binding_records(graphics_abi)
    if not _is_non_empty_string(graphics_abi.target) and has_canonical_bindings:
        diagnostics.append(
            CompatibilityDiagnostic(
                code="package.graphicsAbi.target_invalid",
                message="graphics ABI sidecar target must be a non-empty string",
                document="graphicsAbi",
                artifact="graphicsAbi",
                path="target",
                expected=target,
                actual=_contract_actual_value(graphics_abi.target),
            )
        )
    elif (
        target is not None
        and _is_non_empty_string(graphics_abi.target)
        and graphics_abi.target != target
    ):
        diagnostics.append(
            CompatibilityDiagnostic(
                code="package.graphicsAbi.target_mismatch",
                message="graphics ABI sidecar target must match manifest.target",
                document="graphicsAbi",
                artifact="graphicsAbi",
                path="target",
                expected=target,
                actual=graphics_abi.target,
            )
        )

    if target is None:
        return
    _append_graphics_abi_binding_diagnostics(
        diagnostics,
        target=target,
        reflection=reflection,
        graphics_abi=graphics_abi,
    )


def _append_graphics_abi_binding_diagnostics(
    diagnostics: list[CompatibilityDiagnostic],
    *,
    target: str,
    reflection: dict[str, Any],
    graphics_abi: GraphicsAbiRecord,
) -> None:
    if not _graphics_abi_has_canonical_binding_records(graphics_abi):
        return

    seen: dict[tuple[str, str, str, str | None], int] = {}
    for index, record in enumerate(graphics_abi.abi_records):
        if record.get("target") != target:
            diagnostics.append(
                CompatibilityDiagnostic(
                    code="package.graphicsAbi.binding_target_mismatch",
                    message="graphics ABI resource binding target must match package target",
                    document="graphicsAbi",
                    artifact="graphicsAbi",
                    path=f"abiRecords[{index}].target",
                    expected=target,
                    actual=record.get("target"),
                )
            )
            continue

        if not _target_resource_binding_abi_matches(target, record):
            diagnostics.append(
                CompatibilityDiagnostic(
                    code="package.graphicsAbi.binding_abi_invalid",
                    message="graphics ABI resource binding ABI metadata does not match package target",
                    document="graphicsAbi",
                    artifact="graphicsAbi",
                    path=f"abiRecords[{index}].abi",
                    expected=TARGET_RESOURCE_BINDING_ABI_EXPECTATIONS.get(target),
                    actual=_target_resource_binding_abi_actual(record),
                )
            )

        key = _target_resource_binding_identity(record)
        if key is None:
            continue
        if key not in seen:
            seen[key] = index
            continue
        diagnostics.append(
            CompatibilityDiagnostic(
                code="package.graphicsAbi.binding_duplicate",
                message="graphics ABI resource binding records must be unique",
                document="graphicsAbi",
                artifact="graphicsAbi",
                path=f"abiRecords[{index}]",
                expected={
                    "uniqueGraphicsBinding": {
                        "target": target,
                        "stage": key[0],
                        "entryPoint": key[1],
                        "name": key[2],
                        "kind": key[3],
                    }
                },
                actual={"duplicateOf": f"abiRecords[{seen[key]}]"},
            )
        )

    reflection_keys = {
        key
        for record in _json_object_list(reflection.get("targetResourceBindings"))
        if record.get("target") == target
        if (key := _target_resource_binding_identity(record)) is not None
    }
    graphics_abi_keys = {
        key
        for record in graphics_abi.abi_records
        if record.get("target") == target
        if (key := _target_resource_binding_identity(record)) is not None
    }
    for stage, entry_point, name, kind in sorted(reflection_keys - graphics_abi_keys):
        diagnostics.append(
            CompatibilityDiagnostic(
                code="package.graphicsAbi.binding_missing",
                message="graphics ABI sidecar is missing a reflected target resource binding",
                document="graphicsAbi",
                artifact="graphicsAbi",
                path="abiRecords",
                expected={
                    "target": target,
                    "stage": stage,
                    "entryPoint": entry_point,
                    "name": name,
                    "kind": kind,
                },
                actual="missing",
            )
        )
    for stage, entry_point, name, kind in sorted(graphics_abi_keys - reflection_keys):
        diagnostics.append(
            CompatibilityDiagnostic(
                code="package.graphicsAbi.reflection_binding_missing",
                message="graphics ABI resource binding does not match reflection targetResourceBindings",
                document="graphicsAbi",
                artifact="graphicsAbi",
                path="abiRecords",
                expected={
                    "targetResourceBindings": {
                        "target": target,
                        "stage": stage,
                        "entryPoint": entry_point,
                        "name": name,
                        "kind": kind,
                    }
                },
                actual="missing",
            )
        )


def _graphics_abi_has_canonical_binding_records(
    graphics_abi: GraphicsAbiRecord,
) -> bool:
    return any(
        isinstance(record.get("target"), str) or isinstance(record.get("abi"), str)
        for record in graphics_abi.abi_records
    )


def _target_resource_binding_abi_matches(
    target: str,
    record: dict[str, Any],
) -> bool:
    abi = record.get("abi")
    if isinstance(abi, dict):
        return _target_resource_binding_legacy_abi_matches(target, abi)
    if not _is_non_empty_string(abi):
        return False
    return _target_resource_binding_flat_abi_matches(target, record, abi)


def _target_resource_binding_legacy_abi_matches(
    target: str,
    abi: dict[str, Any],
) -> bool:
    if target == "directx":
        return _is_non_negative_int(abi.get("space")) and _is_non_empty_string(
            abi.get("register")
        )
    if target == "metal":
        return any(
            _is_non_negative_int(abi.get(field_name))
            for field_name in ("buffer", "texture", "sampler")
        )
    if target == "opengl":
        return _is_non_negative_int(abi.get("program")) and _is_non_negative_int(
            abi.get("binding")
        )
    if target == "vulkan":
        return _is_non_negative_int(abi.get("set")) and _is_non_negative_int(
            abi.get("binding")
        )
    return True


def _target_resource_binding_flat_abi_matches(
    target: str,
    record: dict[str, Any],
    abi: str,
) -> bool:
    if target == "directx":
        if abi == "registerBinding":
            return (
                _is_non_empty_string(record.get("bindingClass"))
                and _is_non_empty_string(record.get("descriptorType"))
                and _is_non_negative_int(record.get("argumentIndex"))
                and _is_non_negative_int(record.get("set"))
                and _is_non_negative_int(record.get("binding"))
            )
        return abi == "groupsharedLocal" and _is_non_empty_string(
            record.get("bindingClass")
        )

    if target == "metal":
        if abi == "kernelArgument":
            return (
                _is_non_empty_string(record.get("bindingClass"))
                and _is_non_negative_int(record.get("argumentIndex"))
                and _is_non_negative_int(record.get("set"))
                and _is_non_negative_int(record.get("binding"))
            )
        return abi == "threadgroupLocal" and _is_non_empty_string(
            record.get("bindingClass")
        )

    if target == "opengl":
        if abi == "programResourceBinding":
            return (
                _is_non_empty_string(record.get("bindingClass"))
                and _is_non_negative_int(record.get("argumentIndex"))
                and _is_non_negative_int(record.get("set"))
                and _is_non_negative_int(record.get("binding"))
            )
        return abi == "workgroupLocal" and _is_non_empty_string(
            record.get("bindingClass")
        )

    if target == "vulkan":
        if abi == "descriptor":
            return (
                _is_non_empty_string(record.get("bindingClass"))
                and _is_non_empty_string(record.get("descriptorType"))
                and _is_non_negative_int(record.get("set"))
                and _is_non_negative_int(record.get("binding"))
            )
        return abi == "workgroupLocal" and _is_non_empty_string(
            record.get("bindingClass")
        )

    return True


def _target_resource_binding_abi_actual(record: dict[str, Any]) -> Any:
    abi = record.get("abi")
    if isinstance(abi, dict):
        return _target_resource_binding_abi_object_actual(abi)
    if not isinstance(abi, str):
        return _contract_actual_value(abi)
    return {
        field_name: _target_resource_binding_abi_field_actual(record[field_name])
        for field_name in (
            "abi",
            "bindingClass",
            "descriptorType",
            "argumentIndex",
            "set",
            "binding",
        )
        if field_name in record
    }


def _target_resource_binding_abi_object_actual(value: dict[str, Any]) -> Any:
    return {
        str(field_name): _target_resource_binding_abi_field_actual(field_value)
        for field_name, field_value in sorted(
            value.items(),
            key=lambda item: str(item[0]),
        )
    }


def _target_resource_binding_abi_field_actual(value: Any) -> Any:
    if isinstance(value, str):
        return value
    if isinstance(value, int) and not isinstance(value, bool):
        return value
    return _contract_actual_value(value)


def _is_non_negative_int(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value >= 0


def _is_non_empty_string(value: Any) -> bool:
    return isinstance(value, str) and bool(value)


def _append_native_artifact_descriptor_diagnostics(
    diagnostics: list[CompatibilityDiagnostic],
    *,
    target: str | None,
    artifacts: tuple[Artifact, ...],
    native_binary_status: Any,
    target_contract: TargetArtifactContract | None = None,
    unreadable_documents: frozenset[str],
) -> None:
    if "manifest" in unreadable_documents:
        return

    descriptor_artifact = _artifact_by_name(artifacts, "nativeArtifactDescriptor")
    if descriptor_artifact is None:
        return

    descriptor = _read_declared_artifact_json_object_for_report(
        descriptor_artifact,
        root_file_name="native artifact descriptor",
        document="nativeArtifactDescriptor",
        diagnostic_prefix="package.native_artifact_descriptor",
        diagnostics=diagnostics,
    )
    if descriptor is None:
        return

    _append_native_artifact_descriptor_key_diagnostics(
        diagnostics,
        descriptor=descriptor,
    )
    _append_native_artifact_descriptor_identity_diagnostics(
        diagnostics,
        descriptor=descriptor,
        target=target,
        native_binary_status=native_binary_status,
    )
    _append_native_artifact_descriptor_contract_diagnostics(
        diagnostics,
        descriptor=descriptor,
        target_contract=target_contract,
    )
    _append_native_artifact_descriptor_optimization_diagnostics(
        diagnostics,
        descriptor=descriptor,
        native_binary_status=native_binary_status,
    )
    _append_toolchain_provenance_diagnostics(
        diagnostics,
        descriptor=descriptor,
    )

    binary_kind = descriptor.get("binaryKind")
    if isinstance(target, str) and target:
        allowed_binary_kinds = NATIVE_ARTIFACT_BINARY_KINDS_BY_TARGET.get(target)
        if allowed_binary_kinds is not None and binary_kind not in allowed_binary_kinds:
            diagnostics.append(
                CompatibilityDiagnostic(
                    code="package.native_artifact_descriptor.binary_kind_mismatch",
                    message=(
                        "native artifact descriptor binaryKind does not match "
                        "manifest.target"
                    ),
                    document="nativeArtifactDescriptor",
                    artifact="nativeArtifactDescriptor",
                    path="binaryKind",
                    expected=list(allowed_binary_kinds),
                    actual=_contract_actual_value(binary_kind),
                )
            )

    source_artifact_name = (
        NATIVE_ARTIFACT_SOURCE_BY_BINARY_KIND.get(binary_kind)
        if isinstance(binary_kind, str)
        else None
    )
    if source_artifact_name is not None:
        _append_descriptor_source_fingerprint_diagnostics(
            diagnostics,
            descriptor=descriptor,
            source_artifact=_artifact_by_name(artifacts, source_artifact_name),
        )

    _append_descriptor_native_binary_fingerprint_diagnostics(
        diagnostics,
        descriptor=descriptor,
        native_binary_artifact=_artifact_by_name(artifacts, "nativeBinary"),
        native_binary_status=native_binary_status,
    )


def _append_native_artifact_descriptor_key_diagnostics(
    diagnostics: list[CompatibilityDiagnostic],
    *,
    descriptor: dict[str, Any],
) -> None:
    for field_name in sorted(set(descriptor) - NATIVE_ARTIFACT_DESCRIPTOR_FIELDS):
        diagnostics.append(
            CompatibilityDiagnostic(
                code="package.native_artifact_descriptor.unexpected_field",
                message=(
                    "native artifact descriptor contains an unexpected field: "
                    f"{field_name}"
                ),
                document="nativeArtifactDescriptor",
                artifact="nativeArtifactDescriptor",
                path=field_name,
                expected=sorted(NATIVE_ARTIFACT_DESCRIPTOR_FIELDS),
                actual=field_name,
            )
        )


def _append_toolchain_provenance_diagnostics(
    diagnostics: list[CompatibilityDiagnostic],
    *,
    descriptor: dict[str, Any],
) -> None:
    provenance = descriptor.get("toolchainProvenance")
    if provenance is None:
        return
    if not isinstance(provenance, dict):
        diagnostics.append(
            CompatibilityDiagnostic(
                code=(
                    "package.native_artifact_descriptor.toolchain_provenance_invalid"
                ),
                message=(
                    "native artifact descriptor toolchainProvenance must be an object"
                ),
                document="nativeArtifactDescriptor",
                artifact="nativeArtifactDescriptor",
                path="toolchainProvenance",
                expected="object",
                actual=_json_type_name(provenance),
            )
        )
        return

    tools = provenance.get("tools")
    if tools is None:
        return
    if not isinstance(tools, list):
        diagnostics.append(
            CompatibilityDiagnostic(
                code=(
                    "package.native_artifact_descriptor."
                    "toolchain_provenance_tools_invalid"
                ),
                message=(
                    "native artifact descriptor toolchainProvenance.tools "
                    "must be an array"
                ),
                document="nativeArtifactDescriptor",
                artifact="nativeArtifactDescriptor",
                path="toolchainProvenance.tools",
                expected="array",
                actual=_json_type_name(tools),
            )
        )
        return

    for index, tool in enumerate(tools):
        tool_path = f"toolchainProvenance.tools[{index}]"
        if not isinstance(tool, dict):
            diagnostics.append(
                CompatibilityDiagnostic(
                    code=(
                        "package.native_artifact_descriptor."
                        "toolchain_provenance_tool_invalid"
                    ),
                    message=(
                        "native artifact descriptor toolchainProvenance.tools "
                        "entries must be objects"
                    ),
                    document="nativeArtifactDescriptor",
                    artifact="nativeArtifactDescriptor",
                    path=tool_path,
                    expected="object",
                    actual=_json_type_name(tool),
                )
            )
            continue

        for field_name in NATIVE_TOOLCHAIN_TOOL_IDENTITY_STRING_FIELDS:
            _append_optional_tool_string_diagnostic(
                diagnostics,
                tool=tool,
                field_name=field_name,
                path_prefix=tool_path,
                code_suffix=_snake_case(field_name),
                expected="non-empty string",
            )
        _append_optional_tool_string_diagnostic(
            diagnostics,
            tool=tool,
            field_name="resolvedExecutable",
            path_prefix=tool_path,
            code_suffix="resolved_executable",
            expected="non-empty host tool path string",
        )
        _append_optional_tool_enum_diagnostic(
            diagnostics,
            tool=tool,
            field_name="executableSource",
            path_prefix=tool_path,
            code_suffix="executable_source",
            expected_values=NATIVE_TOOLCHAIN_EXECUTABLE_SOURCES,
        )
        _append_optional_tool_enum_diagnostic(
            diagnostics,
            tool=tool,
            field_name="versionProbeStatus",
            path_prefix=tool_path,
            code_suffix="version_probe_status",
            expected_values=NATIVE_TOOLCHAIN_VERSION_PROBE_STATUSES,
        )
        _append_optional_tool_string_diagnostic(
            diagnostics,
            tool=tool,
            field_name="versionDetail",
            path_prefix=tool_path,
            code_suffix="version_detail",
            expected="non-empty string",
        )


def _append_optional_tool_string_diagnostic(
    diagnostics: list[CompatibilityDiagnostic],
    *,
    tool: dict[str, Any],
    field_name: str,
    path_prefix: str,
    code_suffix: str,
    expected: str,
) -> None:
    if field_name not in tool:
        return
    value = tool.get(field_name)
    if isinstance(value, str) and value:
        return
    diagnostics.append(
        CompatibilityDiagnostic(
            code=(
                "package.native_artifact_descriptor."
                f"toolchain_provenance_tool_{code_suffix}_invalid"
            ),
            message=(
                "native artifact descriptor toolchainProvenance.tools "
                f"{field_name} is invalid"
            ),
            document="nativeArtifactDescriptor",
            artifact="nativeArtifactDescriptor",
            path=f"{path_prefix}.{field_name}",
            expected=expected,
            actual=_contract_actual_value(value),
        )
    )


def _append_optional_tool_enum_diagnostic(
    diagnostics: list[CompatibilityDiagnostic],
    *,
    tool: dict[str, Any],
    field_name: str,
    path_prefix: str,
    code_suffix: str,
    expected_values: frozenset[str],
) -> None:
    if field_name not in tool:
        return
    value = tool.get(field_name)
    if isinstance(value, str) and value in expected_values:
        return
    diagnostics.append(
        CompatibilityDiagnostic(
            code=(
                "package.native_artifact_descriptor."
                f"toolchain_provenance_tool_{code_suffix}_invalid"
            ),
            message=(
                "native artifact descriptor toolchainProvenance.tools "
                f"{field_name} is not supported"
            ),
            document="nativeArtifactDescriptor",
            artifact="nativeArtifactDescriptor",
            path=f"{path_prefix}.{field_name}",
            expected=sorted(expected_values),
            actual=_contract_actual_value(value),
        )
    )


def _append_native_profile_metadata_diagnostics(
    diagnostics: list[CompatibilityDiagnostic],
    *,
    target: str | None,
    artifacts: tuple[Artifact, ...],
    unreadable_documents: frozenset[str],
) -> None:
    if "manifest" in unreadable_documents:
        return

    native_profile = _artifact_by_name(artifacts, "nativeProfile")
    if native_profile is None:
        return

    profile = _read_declared_artifact_json_object_for_report(
        native_profile,
        root_file_name="native profile",
        document="nativeProfile",
        diagnostic_prefix="package.native_profile",
        diagnostics=diagnostics,
    )
    if profile is None or target != "vulkan":
        return

    profile_schema_version = profile.get("schemaVersion")
    if profile_schema_version is None:
        diagnostics.append(
            CompatibilityDiagnostic(
                code="package.native_profile.schema_version_missing",
                message="native profile schemaVersion is required",
                document="nativeProfile",
                artifact="nativeProfile",
                path="schemaVersion",
                expected=SUPPORTED_NATIVE_PROFILE_SCHEMA_VERSION,
                actual="missing",
            )
        )
    elif _schema_version_is_malformed(profile_schema_version):
        diagnostics.append(
            CompatibilityDiagnostic(
                code="package.native_profile.schema_version_invalid",
                message="native profile schemaVersion must be an integer",
                document="nativeProfile",
                artifact="nativeProfile",
                path="schemaVersion",
                expected=SUPPORTED_NATIVE_PROFILE_SCHEMA_VERSION,
                actual=_contract_actual_value(profile_schema_version),
            )
        )
    elif profile_schema_version != SUPPORTED_NATIVE_PROFILE_SCHEMA_VERSION:
        diagnostics.append(
            CompatibilityDiagnostic(
                code="package.native_profile.schema_incompatible",
                message=(
                    "native profile schemaVersion is not supported by this runtime"
                ),
                document="nativeProfile",
                artifact="nativeProfile",
                path="schemaVersion",
                expected=SUPPORTED_NATIVE_PROFILE_SCHEMA_VERSION,
                actual=_contract_actual_value(profile_schema_version),
            )
        )

    if (
        _schema_version_is_malformed(profile_schema_version)
        or profile_schema_version != SUPPORTED_NATIVE_PROFILE_SCHEMA_VERSION
    ):
        return

    profile_target = profile.get("target")
    if not isinstance(profile_target, str) or not profile_target:
        diagnostics.append(
            CompatibilityDiagnostic(
                code="package.native_profile.target_invalid",
                message="native profile target must match manifest.target",
                document="nativeProfile",
                artifact="nativeProfile",
                path="target",
                expected=target,
                actual=_contract_actual_value(profile_target),
            )
        )
        return
    if profile_target == target:
        _append_native_profile_artifact_link_diagnostics(
            diagnostics,
            profile=profile,
            artifacts=artifacts,
        )
        return
    diagnostics.append(
        CompatibilityDiagnostic(
            code="package.native_profile.target_mismatch",
            message="native profile target does not match manifest.target",
            document="nativeProfile",
            artifact="nativeProfile",
            path="target",
            expected=target,
            actual=_contract_actual_value(profile_target),
        )
    )


def _append_native_profile_artifact_link_diagnostics(
    diagnostics: list[CompatibilityDiagnostic],
    *,
    profile: dict[str, Any],
    artifacts: tuple[Artifact, ...],
) -> None:
    for field_name, artifact_name in (
        ("backendAssembly", "backendAssembly"),
        ("nativeBinary", "nativeBinary"),
    ):
        artifact = _artifact_by_name(artifacts, artifact_name)
        if artifact is None:
            continue
        profile_path = profile.get(field_name)
        if not isinstance(profile_path, str) or not profile_path:
            diagnostics.append(
                CompatibilityDiagnostic(
                    code=(f"package.native_profile.{_snake_case(field_name)}_missing"),
                    message=(
                        f"native profile {field_name} must match "
                        f"manifest.artifacts.{artifact_name}"
                    ),
                    document="nativeProfile",
                    artifact="nativeProfile",
                    path=field_name,
                    expected=artifact.package_path,
                    actual=_contract_actual_value(profile_path),
                )
            )
            continue
        if profile_path == artifact.package_path:
            continue
        diagnostics.append(
            CompatibilityDiagnostic(
                code=f"package.native_profile.{_snake_case(field_name)}_mismatch",
                message=(
                    f"native profile {field_name} does not match "
                    f"manifest.artifacts.{artifact_name}"
                ),
                document="nativeProfile",
                artifact="nativeProfile",
                path=field_name,
                expected=artifact.package_path,
                actual=profile_path,
            )
        )


def _append_native_artifact_descriptor_identity_diagnostics(
    diagnostics: list[CompatibilityDiagnostic],
    *,
    descriptor: dict[str, Any],
    target: str | None,
    native_binary_status: Any,
) -> None:
    expected_identity = {
        "schemaVersion": SUPPORTED_NATIVE_ARTIFACT_DESCRIPTOR_SCHEMA_VERSION,
        "kind": NATIVE_ARTIFACT_DESCRIPTOR_KIND,
        "contractVersion": NATIVE_ARTIFACT_DESCRIPTOR_CONTRACT_VERSION,
    }
    for field_name, expected in expected_identity.items():
        actual = descriptor.get(field_name)
        if actual == expected:
            continue
        if field_name == "schemaVersion":
            if actual is None:
                diagnostics.append(
                    CompatibilityDiagnostic(
                        code=(
                            "package.native_artifact_descriptor.schema_version_missing"
                        ),
                        message="native artifact descriptor schemaVersion is required",
                        document="nativeArtifactDescriptor",
                        artifact="nativeArtifactDescriptor",
                        path=field_name,
                        expected=expected,
                        actual="missing",
                    )
                )
                continue
            if _schema_version_is_malformed(actual):
                diagnostics.append(
                    CompatibilityDiagnostic(
                        code=(
                            "package.native_artifact_descriptor.schema_version_invalid"
                        ),
                        message=(
                            "native artifact descriptor schemaVersion must be "
                            "an integer"
                        ),
                        document="nativeArtifactDescriptor",
                        artifact="nativeArtifactDescriptor",
                        path=field_name,
                        expected=expected,
                        actual=_contract_actual_value(actual),
                    )
                )
                continue
            diagnostics.append(
                CompatibilityDiagnostic(
                    code="package.native_artifact_descriptor.schema_incompatible",
                    message=(
                        "native artifact descriptor schemaVersion is not "
                        "supported by this runtime"
                    ),
                    document="nativeArtifactDescriptor",
                    artifact="nativeArtifactDescriptor",
                    path=field_name,
                    expected=expected,
                    actual=_contract_actual_value(actual),
                )
            )
            continue
        diagnostics.append(
            CompatibilityDiagnostic(
                code=(
                    "package.native_artifact_descriptor."
                    f"{_snake_case(field_name)}_mismatch"
                ),
                message=(
                    f"native artifact descriptor {field_name} does not match "
                    "the runtime contract"
                ),
                document="nativeArtifactDescriptor",
                artifact="nativeArtifactDescriptor",
                path=field_name,
                expected=expected,
                actual=_contract_actual_value(actual),
            )
        )

    descriptor_target = descriptor.get("target")
    if descriptor_target != target:
        diagnostics.append(
            CompatibilityDiagnostic(
                code="package.native_artifact_descriptor.target_mismatch",
                message="native artifact descriptor target does not match manifest.target",
                document="nativeArtifactDescriptor",
                artifact="nativeArtifactDescriptor",
                path="target",
                expected=target,
                actual=_contract_actual_value(descriptor_target),
            )
        )

    descriptor_native_status = descriptor.get("nativeBinaryStatus")
    if native_binary_status is None:
        if descriptor_native_status is not None:
            diagnostics.append(
                CompatibilityDiagnostic(
                    code=(
                        "package.native_artifact_descriptor."
                        "native_binary_status_mismatch"
                    ),
                    message=(
                        "native artifact descriptor nativeBinaryStatus must be "
                        "absent when manifest.artifacts.nativeBinaryStatus is absent"
                    ),
                    document="nativeArtifactDescriptor",
                    artifact="nativeArtifactDescriptor",
                    path="nativeBinaryStatus",
                    expected=None,
                    actual=_contract_actual_value(descriptor_native_status),
                )
            )
    elif descriptor_native_status != native_binary_status:
        diagnostics.append(
            CompatibilityDiagnostic(
                code="package.native_artifact_descriptor.native_binary_status_mismatch",
                message=(
                    "native artifact descriptor nativeBinaryStatus does not match "
                    "manifest.artifacts.nativeBinaryStatus"
                ),
                document="nativeArtifactDescriptor",
                artifact="nativeArtifactDescriptor",
                path="nativeBinaryStatus",
                expected=native_binary_status,
                actual=_contract_actual_value(descriptor_native_status),
            )
        )

    validation_status = descriptor.get("validationStatus")
    if (
        not isinstance(validation_status, str)
        or validation_status not in NATIVE_ARTIFACT_DESCRIPTOR_VALIDATION_STATUSES
    ):
        diagnostics.append(
            CompatibilityDiagnostic(
                code="package.native_artifact_descriptor.validation_status_invalid",
                message=(
                    "native artifact descriptor validationStatus is not supported"
                ),
                document="nativeArtifactDescriptor",
                artifact="nativeArtifactDescriptor",
                path="validationStatus",
                expected=sorted(NATIVE_ARTIFACT_DESCRIPTOR_VALIDATION_STATUSES),
                actual=_contract_actual_value(validation_status),
            )
        )
        return

    if native_binary_status is None:
        return
    if validation_status == "validated" and native_binary_status != "validated":
        diagnostics.append(
            CompatibilityDiagnostic(
                code="package.native_artifact_descriptor.validation_status_mismatch",
                message=(
                    "native artifact descriptor validationStatus=validated requires "
                    "manifest.artifacts.nativeBinaryStatus=validated"
                ),
                document="nativeArtifactDescriptor",
                artifact="nativeArtifactDescriptor",
                path="validationStatus",
                expected=f"nativeBinaryStatus {native_binary_status!r} not validated",
                actual=validation_status,
            )
        )
    if native_binary_status == "validated" and validation_status != "validated":
        diagnostics.append(
            CompatibilityDiagnostic(
                code="package.native_artifact_descriptor.validation_status_mismatch",
                message=(
                    "manifest.artifacts.nativeBinaryStatus=validated requires "
                    "native artifact descriptor validationStatus=validated"
                ),
                document="nativeArtifactDescriptor",
                artifact="nativeArtifactDescriptor",
                path="validationStatus",
                expected="validated",
                actual=validation_status,
            )
        )


def _append_native_artifact_descriptor_contract_diagnostics(
    diagnostics: list[CompatibilityDiagnostic],
    *,
    descriptor: dict[str, Any],
    target_contract: TargetArtifactContract | None,
) -> None:
    if target_contract is None:
        return
    if descriptor.get("nativeBinaryStatus") != "planned":
        return
    if (
        target_contract.package_mode == SOURCE_PACKAGE_MODE
        and target_contract.allows_planned_native_source_evidence
    ):
        return

    diagnostics.append(
        CompatibilityDiagnostic(
            code=(
                "package.native_artifact_descriptor.planned_source_evidence_forbidden"
            ),
            message=(
                "native artifact descriptor nativeBinaryStatus=planned requires "
                "a source-package target contract that allows planned native "
                "source evidence"
            ),
            document="nativeArtifactDescriptor",
            artifact="nativeArtifactDescriptor",
            path="nativeBinaryStatus",
            expected={
                "packageMode": SOURCE_PACKAGE_MODE,
                "allowsPlannedNativeSourceEvidence": True,
            },
            actual={
                "target": target_contract.target,
                "packageMode": target_contract.package_mode,
                "allowsPlannedNativeSourceEvidence": (
                    target_contract.allows_planned_native_source_evidence
                ),
            },
        )
    )


def _append_native_artifact_descriptor_optimization_diagnostics(
    diagnostics: list[CompatibilityDiagnostic],
    *,
    descriptor: dict[str, Any],
    native_binary_status: Any,
) -> None:
    evidence = descriptor.get("optimizationEvidence")
    if evidence is None:
        return
    if not isinstance(evidence, dict):
        diagnostics.append(
            CompatibilityDiagnostic(
                code="package.native_artifact_descriptor.optimization_evidence_invalid",
                message=(
                    "native artifact descriptor optimizationEvidence must be an object"
                ),
                document="nativeArtifactDescriptor",
                artifact="nativeArtifactDescriptor",
                path="optimizationEvidence",
                expected="object",
                actual=_json_type_name(evidence),
            )
        )
        return

    applied_claim = _native_optimization_applied_claim(evidence)
    if applied_claim is None:
        return

    claim_field, claim_value = applied_claim
    claim_path = f"optimizationEvidence.{claim_field}"
    if native_binary_status == "planned":
        diagnostics.append(
            CompatibilityDiagnostic(
                code=(
                    "package.native_artifact_descriptor."
                    "optimization_evidence_applied_planned"
                ),
                message=(
                    "native artifact descriptor optimizationEvidence must not "
                    "claim applied optimization when nativeBinaryStatus is planned"
                ),
                document="nativeArtifactDescriptor",
                artifact="nativeArtifactDescriptor",
                path=claim_path,
                expected="metadata-only optimization evidence for planned native binary",
                actual=claim_value,
            )
        )

    optimization_level = descriptor.get("optimizationLevel")
    if not _is_concrete_optimization_level(optimization_level):
        diagnostics.append(
            CompatibilityDiagnostic(
                code="package.native_artifact_descriptor.optimization_level_required",
                message=(
                    "native artifact descriptor applied optimization evidence "
                    "requires a concrete optimizationLevel"
                ),
                document="nativeArtifactDescriptor",
                artifact="nativeArtifactDescriptor",
                path="optimizationLevel",
                expected="concrete optimizationLevel",
                actual=_contract_actual_value(optimization_level),
            )
        )

    missing_artifact_facts = [
        field_name
        for field_name in NATIVE_OPTIMIZATION_PRODUCED_ARTIFACT_FACTS
        if field_name not in descriptor
    ]
    if missing_artifact_facts:
        diagnostics.append(
            CompatibilityDiagnostic(
                code=(
                    "package.native_artifact_descriptor."
                    "optimization_artifact_facts_missing"
                ),
                message=(
                    "native artifact descriptor applied optimization evidence "
                    "requires produced artifact facts"
                ),
                document="nativeArtifactDescriptor",
                artifact="nativeArtifactDescriptor",
                path=claim_path,
                expected=list(NATIVE_OPTIMIZATION_PRODUCED_ARTIFACT_FACTS),
                actual={"missing": missing_artifact_facts},
            )
        )


def _native_optimization_applied_claim(
    evidence: dict[str, Any],
) -> tuple[str, str] | None:
    for field_name in ("status", "policy"):
        value = evidence.get(field_name)
        if (
            isinstance(value, str)
            and value in NATIVE_OPTIMIZATION_EVIDENCE_APPLIED_VALUES
        ):
            return field_name, value
    return None


def _is_concrete_optimization_level(value: Any) -> bool:
    return isinstance(value, str) and value in NATIVE_CONCRETE_OPTIMIZATION_LEVELS


def _append_descriptor_source_fingerprint_diagnostics(
    diagnostics: list[CompatibilityDiagnostic],
    *,
    descriptor: dict[str, Any],
    source_artifact: Artifact | None,
) -> None:
    _descriptor_sha256_value(
        diagnostics,
        descriptor.get("sourceHash"),
        descriptor_field="sourceHash",
    )
    if source_artifact is None:
        return

    source_path = descriptor.get("sourcePath")
    if source_path != source_artifact.package_path:
        diagnostics.append(
            CompatibilityDiagnostic(
                code="package.native_artifact_descriptor.source_path_mismatch",
                message=(
                    "native artifact descriptor sourcePath does not match the "
                    "manifest source artifact"
                ),
                document="nativeArtifactDescriptor",
                artifact="nativeArtifactDescriptor",
                path="sourcePath",
                expected=source_artifact.package_path,
                actual=_contract_actual_value(source_path),
            )
        )


def _append_descriptor_native_binary_fingerprint_diagnostics(
    diagnostics: list[CompatibilityDiagnostic],
    *,
    descriptor: dict[str, Any],
    native_binary_artifact: Artifact | None,
    native_binary_status: Any,
) -> None:
    planned_native_binary = native_binary_status == "planned"
    if planned_native_binary:
        for field_name in ("artifactPath", "artifactHash", "sizeBytes"):
            if field_name not in descriptor:
                continue
            diagnostics.append(
                CompatibilityDiagnostic(
                    code=(
                        "package.native_artifact_descriptor."
                        f"{_snake_case(field_name)}_unexpected"
                    ),
                    message=(
                        f"native artifact descriptor {field_name} must be absent "
                        "when nativeBinaryStatus is planned"
                    ),
                    document="nativeArtifactDescriptor",
                    artifact="nativeArtifactDescriptor",
                    path=field_name,
                    expected="absent for planned native binary",
                    actual=_contract_actual_value(descriptor.get(field_name)),
                )
            )
        return

    if native_binary_artifact is None:
        return

    artifact_path = descriptor.get("artifactPath")
    if artifact_path != native_binary_artifact.package_path:
        diagnostics.append(
            CompatibilityDiagnostic(
                code="package.native_artifact_descriptor.artifact_path_mismatch",
                message=(
                    "native artifact descriptor artifactPath does not match "
                    "manifest.artifacts.nativeBinary"
                ),
                document="nativeArtifactDescriptor",
                artifact="nativeArtifactDescriptor",
                path="artifactPath",
                expected=native_binary_artifact.package_path,
                actual=_contract_actual_value(artifact_path),
            )
        )

    if not native_binary_artifact.exists:
        return
    if _is_crossgl_source_input_path(native_binary_artifact.package_path):
        return

    _append_descriptor_hash_diagnostics(
        diagnostics,
        descriptor=descriptor,
        descriptor_field="artifactHash",
        artifact=native_binary_artifact,
        mismatch_code="package.native_artifact_descriptor.artifact_hash_mismatch",
        mismatch_message=(
            "native artifact descriptor artifactHash does not match artifactPath bytes"
        ),
    )

    size_bytes = descriptor.get("sizeBytes")
    if not isinstance(size_bytes, int) or isinstance(size_bytes, bool):
        diagnostics.append(
            CompatibilityDiagnostic(
                code="package.native_artifact_descriptor.size_bytes_invalid",
                message="native artifact descriptor sizeBytes must be an integer",
                document="nativeArtifactDescriptor",
                artifact="nativeArtifactDescriptor",
                path="sizeBytes",
                expected=native_binary_artifact.size,
                actual=_contract_actual_value(size_bytes),
            )
        )
    elif size_bytes != native_binary_artifact.size:
        diagnostics.append(
            CompatibilityDiagnostic(
                code="package.native_artifact_descriptor.size_bytes_mismatch",
                message=(
                    "native artifact descriptor sizeBytes does not match "
                    "artifactPath bytes"
                ),
                document="nativeArtifactDescriptor",
                artifact="nativeArtifactDescriptor",
                path="sizeBytes",
                expected=native_binary_artifact.size,
                actual=size_bytes,
            )
        )


def _append_descriptor_hash_diagnostics(
    diagnostics: list[CompatibilityDiagnostic],
    *,
    descriptor: dict[str, Any],
    descriptor_field: str,
    artifact: Artifact,
    mismatch_code: str,
    mismatch_message: str,
) -> None:
    hash_value = _descriptor_sha256_value(
        diagnostics,
        descriptor.get(descriptor_field),
        descriptor_field=descriptor_field,
    )
    if hash_value is None:
        return
    try:
        actual_hash = _artifact_sha256(artifact)
    except _ArtifactTooLargeError as error:
        diagnostics.append(
            CompatibilityDiagnostic(
                code=(
                    "package.native_artifact_descriptor."
                    f"{_snake_case(descriptor_field)}_too_large"
                ),
                message=(
                    f"native artifact descriptor {descriptor_field} cannot be "
                    f"validated: {error}"
                ),
                document="nativeArtifactDescriptor",
                artifact="nativeArtifactDescriptor",
                path=descriptor_field,
                expected=f"<= {error.limit} bytes",
                actual=error.size,
            )
        )
        return
    if hash_value == actual_hash:
        return
    diagnostics.append(
        CompatibilityDiagnostic(
            code=mismatch_code,
            message=mismatch_message,
            document="nativeArtifactDescriptor",
            artifact="nativeArtifactDescriptor",
            path=f"{descriptor_field}.value",
            expected=actual_hash,
            actual=hash_value,
        )
    )


def _descriptor_sha256_value(
    diagnostics: list[CompatibilityDiagnostic],
    value: Any,
    *,
    descriptor_field: str,
) -> str | None:
    if not isinstance(value, dict):
        diagnostics.append(
            CompatibilityDiagnostic(
                code=(
                    "package.native_artifact_descriptor."
                    f"{_snake_case(descriptor_field)}_invalid"
                ),
                message=(
                    f"native artifact descriptor {descriptor_field} must be a "
                    "sha256 hash object"
                ),
                document="nativeArtifactDescriptor",
                artifact="nativeArtifactDescriptor",
                path=descriptor_field,
                expected={"algorithm": "sha256", "value": "lowercase sha256"},
                actual=_json_type_name(value),
            )
        )
        return None

    algorithm = value.get("algorithm")
    digest = value.get("value")
    if algorithm != "sha256" or not _is_lowercase_sha256(digest):
        diagnostics.append(
            CompatibilityDiagnostic(
                code=(
                    "package.native_artifact_descriptor."
                    f"{_snake_case(descriptor_field)}_invalid"
                ),
                message=(
                    f"native artifact descriptor {descriptor_field} must contain "
                    "algorithm=sha256 and a lowercase SHA-256 value"
                ),
                document="nativeArtifactDescriptor",
                artifact="nativeArtifactDescriptor",
                path=descriptor_field,
                expected={"algorithm": "sha256", "value": "lowercase sha256"},
                actual={
                    "algorithm": _contract_actual_value(algorithm),
                    "value": _contract_actual_value(digest),
                },
            )
        )
        return None
    assert isinstance(digest, str)
    return digest


def _read_declared_artifact_json_object_for_report(
    artifact: Artifact,
    *,
    root_file_name: str,
    document: str,
    diagnostic_prefix: str,
    diagnostics: list[CompatibilityDiagnostic],
) -> dict[str, Any] | None:
    if not artifact.exists:
        diagnostics.append(
            CompatibilityDiagnostic(
                code=f"{diagnostic_prefix}.file_missing",
                message=(
                    f"declared {root_file_name} artifact is missing: "
                    f"{artifact.package_path}"
                ),
                document=document,
                artifact=artifact.name,
                path=artifact.package_path,
                expected="regular file",
                actual="missing",
            )
        )
        return None

    limit = RUNTIME_METADATA_JSON_BYTE_LIMIT
    if artifact.size is not None and artifact.size > limit:
        diagnostics.append(
            CompatibilityDiagnostic(
                code=f"{diagnostic_prefix}.too_large",
                message=(
                    f"package metadata exceeds runtime byte limit: "
                    f"{root_file_name} is {artifact.size} bytes; limit is {limit} bytes"
                ),
                document=document,
                artifact=artifact.name,
                path=artifact.package_path,
                expected=f"<= {limit} bytes",
                actual=artifact.size,
            )
        )
        return None

    try:
        payload = artifact.read_bytes()
        if len(payload) > limit:
            raise _MetadataTooLargeError(root_file_name, len(payload), limit)
        return _parse_json_object_payload(payload, root_file_name=root_file_name)
    except PackageReadError as error:
        if isinstance(error, _MetadataTooLargeError):
            diagnostics.append(
                CompatibilityDiagnostic(
                    code=f"{diagnostic_prefix}.too_large",
                    message=str(error),
                    document=document,
                    artifact=artifact.name,
                    path=artifact.package_path,
                    expected=f"<= {error.limit} bytes",
                    actual=error.size,
                )
            )
            return None
        diagnostics.append(
            CompatibilityDiagnostic(
                code=f"{diagnostic_prefix}.invalid",
                message=str(error),
                document=document,
                artifact=artifact.name,
                path=artifact.package_path,
                expected="JSON object metadata file",
                actual="invalid",
            )
        )
        return None
    except (KeyError, OSError, zipfile.BadZipFile) as error:
        diagnostics.append(
            CompatibilityDiagnostic(
                code=f"{diagnostic_prefix}.invalid",
                message=f"could not read {root_file_name}: {error}",
                document=document,
                artifact=artifact.name,
                path=artifact.package_path,
                expected="readable JSON object metadata file",
                actual="invalid",
            )
        )
        return None


def _iter_artifact_bytes(
    artifact: Artifact,
    *,
    chunk_size: int,
    byte_limit: int | None,
) -> Iterator[bytes]:
    chunk_size = _require_positive_int(
        chunk_size,
        label="artifact chunk_size",
    )
    byte_limit = _normalize_optional_byte_limit(
        byte_limit,
        label="artifact byte_limit",
    )
    if (
        byte_limit is not None
        and artifact.size is not None
        and artifact.size > byte_limit
    ):
        raise _ArtifactTooLargeError(artifact, artifact.size, byte_limit)

    if artifact.archive_path is not None:
        member = artifact.archive_member or artifact.package_path
        with zipfile.ZipFile(artifact.archive_path) as archive:
            with archive.open(member) as handle:
                yield from _iter_limited_binary_chunks(
                    handle,
                    artifact=artifact,
                    chunk_size=chunk_size,
                    byte_limit=byte_limit,
                )
        return

    with artifact.path.open("rb") as handle:
        yield from _iter_limited_binary_chunks(
            handle,
            artifact=artifact,
            chunk_size=chunk_size,
            byte_limit=byte_limit,
        )


def _iter_limited_binary_chunks(
    handle: Any,
    *,
    artifact: Artifact,
    chunk_size: int,
    byte_limit: int | None,
) -> Iterator[bytes]:
    total = 0
    while True:
        chunk = handle.read(chunk_size)
        if not chunk:
            return
        total += len(chunk)
        if byte_limit is not None and total > byte_limit:
            raise _ArtifactTooLargeError(artifact, total, byte_limit)
        yield chunk


def _require_positive_int(value: Any, *, label: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
        raise PackageReadError(f"{label} must be a positive integer")
    return value


def _normalize_optional_byte_limit(value: Any, *, label: str) -> int | None:
    if value is None:
        return None
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise PackageReadError(f"{label} must be a non-negative integer or None")
    return value


def _resolve_artifact_byte_limit(value: Any) -> int | None:
    if value is _DEFAULT_ARTIFACT_BYTE_LIMIT:
        return RUNTIME_ARTIFACT_BYTE_LIMIT
    return _normalize_optional_byte_limit(value, label="artifact byte_limit")


def _artifact_sha256(artifact: Artifact) -> str:
    return artifact.sha256()


def _is_lowercase_sha256(value: Any) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 64
        and all(character in "0123456789abcdef" for character in value)
    )


def _artifact_by_name(
    artifacts: tuple[Artifact, ...], artifact_name: str
) -> Artifact | None:
    for artifact in artifacts:
        if artifact.name == artifact_name:
            return artifact
    return None


def _artifact_availability_summary(
    artifacts: tuple[Artifact, ...],
    *,
    native_binary_status: Any,
    target_contract: TargetArtifactContract | None,
) -> dict[str, Any]:
    source_artifacts = tuple(
        artifact for artifact in artifacts if artifact.name in SOURCE_ARTIFACT_NAMES
    )
    native_artifact = _artifact_by_name(artifacts, "nativeBinary")
    native_exists = native_artifact.exists if native_artifact is not None else False
    status_says_ready = _native_binary_status_is_ready(native_binary_status)
    status_not_required = (
        target_contract is not None
        and not target_contract.native_binary_status_required
    )
    native_usable = (
        native_exists
        and target_contract is not None
        and (status_says_ready or status_not_required)
    )

    return {
        "source": {
            "declared": bool(source_artifacts),
            "available": any(artifact.exists for artifact in source_artifacts),
            "artifacts": [artifact.to_summary() for artifact in source_artifacts],
        },
        "native": {
            "declared": native_artifact is not None,
            "exists": native_exists,
            "usable": native_usable,
            "nativeBinaryStatus": native_binary_status,
            "artifact": (
                native_artifact.to_summary() if native_artifact is not None else None
            ),
        },
    }


def _admission_summary(report: PackageCompatibilityReport) -> dict[str, Any]:
    return {
        "schemaVersion": 1,
        "decision": _admission_decision(report),
        "status": report.status,
        "metadataOnly": True,
        "sourceParsingRequired": report.source_parsing_required,
        "compilerInvocationRequired": False,
        "deviceExecutionRequired": False,
        "sourceInputs": [],
        "target": _target_admission_summary(report),
        "requirements": _requirements_admission_summary(report),
        "fallbacks": _fallback_admission_summary(report),
    }


def _admission_decision(report: PackageCompatibilityReport) -> str:
    if report.reject_reasons:
        return "rejected"
    if report.skip_reasons:
        return "skipped"
    return "accepted"


def _requirements_admission_summary(
    report: PackageCompatibilityReport,
) -> dict[str, Any]:
    diagnostics = report.requirement_diagnostics
    contract = report.target_contract
    requirements_source = _requirements_source_for_report(report)
    source_kind = _requirements_source_kind(report, requirements_source)
    missing_diagnostics = tuple(
        diagnostic
        for diagnostic in diagnostics
        if diagnostic.code.startswith("package.artifact_requirements.")
        and diagnostic.code.endswith("_missing")
    )
    error_diagnostics = tuple(
        diagnostic for diagnostic in diagnostics if diagnostic.severity == "error"
    )
    reason_diagnostic = error_diagnostics[0] if error_diagnostics else None
    reason = reason_diagnostic.code if reason_diagnostic is not None else None
    complete = not missing_diagnostics
    valid = not error_diagnostics
    compatibility_kind = _requirements_compatibility_kind(
        report=report,
        source_kind=source_kind,
        complete=complete,
        valid=valid,
    )
    legacy_inferred = (
        requirements_source == GENERATED_CONTRACT_REQUIREMENTS_SOURCE
        and not report.package_artifact_requirements_declared
    )
    compatibility_scope = (
        "legacy/report-only"
        if legacy_inferred
        else "recorded-package-metadata"
        if report.package_artifact_requirements_declared
        else "unavailable"
    )
    return {
        "declared": report.package_artifact_requirements_declared,
        "recorded": report.package_artifact_requirements_declared,
        "legacyInferred": legacy_inferred,
        "requirementsSource": requirements_source,
        "sourceKind": source_kind,
        "compatibilityKind": compatibility_kind,
        "reportOnly": legacy_inferred,
        "compatibilityScope": compatibility_scope,
        "reason": reason,
        "complete": complete,
        "resolved": contract is not None,
        "valid": valid,
        "target": contract.target if contract is not None else report.target,
        "packageMode": contract.package_mode if contract is not None else None,
        "requiredPathArtifacts": list(report.required_artifacts),
        "nativeBinaryStatusRequired": (
            contract.native_binary_status_required if contract is not None else None
        ),
        "allowsPlannedNativeBinary": (
            contract.planned_native_binary_may_be_absent
            if contract is not None
            else None
        ),
        "allowsPlannedNativeSourceEvidence": (
            contract.allows_planned_native_source_evidence
            if contract is not None
            else None
        ),
        "recordedRequirements": {
            "declared": report.package_artifact_requirements_declared,
            "complete": (
                complete if report.package_artifact_requirements_declared else None
            ),
            "valid": valid if report.package_artifact_requirements_declared else None,
            "reason": (
                reason if report.package_artifact_requirements_declared else None
            ),
            "diagnosticCount": (
                len(diagnostics) if report.package_artifact_requirements_declared else 0
            ),
        },
        "legacyGeneratedRequirements": {
            "compatibilityOnly": legacy_inferred,
            "reportOnly": legacy_inferred,
            "compatibilityScope": ("legacy/report-only" if legacy_inferred else None),
            "inferred": legacy_inferred,
            "requirementsSource": GENERATED_CONTRACT_REQUIREMENTS_SOURCE,
        },
        "diagnosticCount": len(diagnostics),
        "diagnostics": [diagnostic.to_summary() for diagnostic in diagnostics],
    }


def _requirements_source_for_report(report: PackageCompatibilityReport) -> str:
    if report.target_contract is not None:
        return report.target_contract.requirements_source
    if report.package_artifact_requirements_declared:
        return "manifest"
    if report.target is not None:
        return GENERATED_CONTRACT_REQUIREMENTS_SOURCE
    return "unavailable"


def _requirements_source_kind(
    report: PackageCompatibilityReport,
    requirements_source: str,
) -> str:
    if report.package_artifact_requirements_declared:
        return "recorded"
    if requirements_source == GENERATED_CONTRACT_REQUIREMENTS_SOURCE:
        return "legacy-generated"
    return "unavailable"


def _requirements_compatibility_kind(
    *,
    report: PackageCompatibilityReport,
    source_kind: str,
    complete: bool,
    valid: bool,
) -> str:
    if source_kind == "recorded":
        if not complete:
            return "recorded-incomplete"
        if not valid or report.target_contract is None:
            return "recorded-invalid"
        return "recorded"
    if source_kind == "legacy-generated":
        if report.target_contract is None:
            return "legacy-generated-unresolved"
        return "legacy-generated-compatible"
    return "unavailable"


def _target_admission_summary(report: PackageCompatibilityReport) -> dict[str, Any]:
    diagnostics = _target_admission_diagnostics(report)
    supported_targets = _runtime_supported_targets()
    target_available = isinstance(report.target, str) and bool(report.target)
    target_supported = target_available and report.target in supported_targets
    loader_matched = (
        report.loader_target is None or report.loader_target == report.target
    )
    category = "target-accepted"
    decision = "accepted"
    reason: CompatibilityDiagnostic | None = None

    loader_mismatch = _first_diagnostic(
        diagnostics,
        "package.target.loader_mismatch",
    )
    target_unavailable = _first_diagnostic(
        diagnostics,
        "package.identity.target_missing",
        "package.metadata.missing",
        "package.metadata.invalid",
        "package.metadata.too_large",
    )
    target_contract_unavailable = next(
        (
            diagnostic
            for diagnostic in diagnostics
            if diagnostic.code.startswith("package.target_contract.")
        ),
        None,
    )
    target_sidecar_invalid = next(
        (
            diagnostic
            for diagnostic in diagnostics
            if diagnostic.code == "package.identity.reflection_target_mismatch"
            or diagnostic.code.startswith("package.reflection.target_")
        ),
        None,
    )
    target_unsupported = _first_diagnostic(
        diagnostics,
        "package.target.unsupported",
        "package.artifact_requirements.target_unsupported",
    )

    if loader_mismatch is not None:
        category = "target-mismatch"
        decision = "skipped"
        reason = loader_mismatch
    elif not target_available:
        category = "target-unavailable"
        decision = "rejected"
        reason = target_unavailable
    elif target_contract_unavailable is not None:
        category = "target-unavailable"
        decision = "rejected"
        reason = target_contract_unavailable
    elif target_sidecar_invalid is not None:
        category = "target-unavailable"
        decision = "rejected"
        reason = target_sidecar_invalid
    elif target_unsupported is not None or not target_supported:
        category = "target-unsupported"
        decision = "rejected"
        reason = target_unsupported

    return {
        "decision": decision,
        "category": category,
        "reason": reason.code if reason is not None else None,
        "loaderTarget": report.loader_target,
        "packageTarget": report.target,
        "matched": loader_matched,
        "available": target_available,
        "supported": target_supported,
        "supportedTargets": list(supported_targets),
        "availableTargets": list(report.available_targets),
        "diagnostics": [diagnostic.to_summary() for diagnostic in diagnostics],
    }


def _target_admission_diagnostics(
    report: PackageCompatibilityReport,
) -> tuple[CompatibilityDiagnostic, ...]:
    codes = {
        "package.identity.target_missing",
        "package.identity.reflection_target_mismatch",
        "package.target.loader_mismatch",
        "package.target.unsupported",
        "package.artifact_requirements.target_mismatch",
        "package.artifact_requirements.target_unsupported",
    }
    manifest_metadata_codes = {
        "package.metadata.missing",
        "package.metadata.invalid",
        "package.metadata.too_large",
    }
    return tuple(
        diagnostic
        for diagnostic in report.diagnostics
        if diagnostic.code in codes
        or (
            diagnostic.code in manifest_metadata_codes
            and diagnostic.document == "manifest"
        )
        or diagnostic.code.startswith("package.target_contract.")
        or diagnostic.code.startswith("package.reflection.target_")
    )


def _runtime_supported_targets() -> tuple[str, ...]:
    diagnostics: list[CompatibilityDiagnostic] = []
    contracts = _target_artifact_contracts(diagnostics=diagnostics)
    return tuple(sorted(contracts))


def _first_diagnostic(
    diagnostics: tuple[CompatibilityDiagnostic, ...],
    *codes: str,
) -> CompatibilityDiagnostic | None:
    code_set = set(codes)
    return next(
        (diagnostic for diagnostic in diagnostics if diagnostic.code in code_set),
        None,
    )


def _fallback_admission_summary(report: PackageCompatibilityReport) -> dict[str, Any]:
    source_availability = report.artifact_availability["source"]
    source_package_fallback = _source_package_fallback_admission_summary(report)
    return {
        "sourceFreePackage": not source_availability["declared"],
        "sourceParsingRequired": report.source_parsing_required,
        "sourcePackage": source_package_fallback,
        "source": {
            "artifactDeclared": source_availability["declared"],
            "artifactAvailable": source_availability["available"],
            "fallbackAllowed": False,
            "fallbackAttempted": False,
            "reason": "runtime.source_fallback_disabled",
            "message": (
                "runtime package reads do not parse CrossGL source as a fallback"
            ),
        },
        "compiler": {
            "fallbackAllowed": False,
            "fallbackAttempted": False,
            "reason": "runtime.compiler_fallback_disabled",
            "message": "runtime package reads do not invoke a compiler fallback",
        },
    }


def _source_package_fallback_admission_summary(
    report: PackageCompatibilityReport,
) -> dict[str, Any]:
    source_availability = report.artifact_availability["source"]
    native_availability = report.artifact_availability["native"]
    contract = report.target_contract
    allowed = contract is not None and contract.package_mode == SOURCE_PACKAGE_MODE
    native_usable = bool(native_availability["usable"])
    source_available = bool(source_availability["available"])
    attempted = allowed and not native_usable
    accepted = (
        attempted
        and source_available
        and not _has_blocking_diagnostics(list(report.diagnostics))
    )
    reason = "runtime.source_package_fallback.not_needed"
    message = "native runtime artifact is available"
    if accepted:
        reason = "runtime.source_package_fallback.accepted"
        message = (
            "generated backendSource is accepted because nativeBinary is not "
            "usable for this source-package target"
        )
    elif attempted:
        reason = "runtime.source_package_fallback.unavailable"
        message = (
            "source-package fallback is allowed but backendSource is not available"
        )
    elif not allowed:
        reason = "runtime.source_package_fallback.not_allowed"
        message = "target package contract does not allow source-package fallback"
    return {
        "fallbackAllowed": allowed,
        "fallbackAttempted": attempted,
        "fallbackAccepted": accepted,
        "reason": reason,
        "message": message,
        "artifactDeclared": source_availability["declared"],
        "artifactAvailable": source_available,
        "nativeUsable": native_usable,
        "nativeBinaryStatus": native_availability["nativeBinaryStatus"],
    }


def _normalize_runtime_artifact_selection_mode(package_mode: str) -> str:
    if package_mode == "source":
        return SOURCE_PACKAGE_MODE
    if package_mode not in RUNTIME_ARTIFACT_SELECTION_MODES:
        raise PackageReadError(
            "runtime artifact package_mode must be one of auto, native, "
            f"source, source-package: {package_mode}"
        )
    return package_mode


def _runtime_artifact_selection_context_diagnostics(
    *,
    report: PackageCompatibilityReport,
    requested_target: str,
) -> tuple[CompatibilityDiagnostic, ...]:
    if report.loader_target is None or report.loader_target == requested_target:
        return ()
    return (
        CompatibilityDiagnostic(
            code="package.target.selection_loader_mismatch",
            message=(
                "runtime artifact selection target "
                f"{requested_target} does not match compatibility report "
                f"loader target {report.loader_target}"
            ),
            document="compatibilityReport",
            path="loaderTarget",
            expected=requested_target,
            actual=report.loader_target,
        ),
    )


def _has_blocking_diagnostics(
    diagnostics: list[CompatibilityDiagnostic],
) -> bool:
    return any(diagnostic.severity in {"error", "skip"} for diagnostic in diagnostics)


def _runtime_artifact_selection_admission_summary(
    *,
    report: PackageCompatibilityReport,
    requested_target: str,
    requested_mode: str,
    selected_mode: str | None,
    artifact: Artifact | None,
    diagnostics: tuple[CompatibilityDiagnostic, ...],
) -> dict[str, Any]:
    reject_reasons = tuple(
        diagnostic for diagnostic in diagnostics if diagnostic.severity == "error"
    )
    skip_reasons = tuple(
        diagnostic for diagnostic in diagnostics if diagnostic.severity == "skip"
    )
    if reject_reasons:
        decision = "rejected"
    elif skip_reasons:
        decision = "skipped"
    elif artifact is not None:
        decision = "accepted"
    else:
        decision = "unavailable"
    return {
        "schemaVersion": 1,
        "decision": decision,
        "metadataOnly": True,
        "sourceParsingRequired": False,
        "compilerInvocationRequired": False,
        "deviceExecutionRequired": False,
        "sourceInputs": [],
        "target": _runtime_artifact_selection_target_admission(
            report=report,
            requested_target=requested_target,
            diagnostics=diagnostics,
        ),
        "native": _runtime_artifact_selection_native_admission(
            report=report,
            requested_mode=requested_mode,
            selected_mode=selected_mode,
            artifact=artifact,
            diagnostics=diagnostics,
        ),
        "sourcePackageFallback": (
            _runtime_artifact_selection_source_package_fallback_admission(
                report=report,
                requested_mode=requested_mode,
                selected_mode=selected_mode,
                artifact=artifact,
                diagnostics=diagnostics,
            )
        ),
    }


def _runtime_artifact_selection_target_admission(
    *,
    report: PackageCompatibilityReport,
    requested_target: str,
    diagnostics: tuple[CompatibilityDiagnostic, ...],
) -> dict[str, Any]:
    target_diagnostics = tuple(
        diagnostic
        for diagnostic in diagnostics
        if (
            diagnostic.code
            in {
                "package.identity.target_missing",
                "package.identity.reflection_target_mismatch",
                "package.metadata.missing",
                "package.metadata.invalid",
                "package.metadata.too_large",
                "package.target.loader_mismatch",
                "package.target.selection_loader_mismatch",
                "package.target.unsupported",
                "package.artifact_requirements.target_unsupported",
            }
            and (
                not diagnostic.code.startswith("package.metadata.")
                or diagnostic.document == "manifest"
            )
        )
        or diagnostic.code.startswith("package.target_contract.")
        or diagnostic.code.startswith("package.reflection.target_")
    )
    target_unavailable = _first_diagnostic(
        target_diagnostics,
        "package.identity.target_missing",
        "package.metadata.missing",
        "package.metadata.invalid",
        "package.metadata.too_large",
    )
    if _first_diagnostic(
        target_diagnostics,
        "package.target.selection_loader_mismatch",
    ):
        category = "selection-context-mismatch"
        decision = "rejected"
    elif _first_diagnostic(target_diagnostics, "package.target.loader_mismatch"):
        category = "target-mismatch"
        decision = "skipped"
    elif target_unavailable is not None:
        category = "target-unavailable"
        decision = "rejected"
    elif _first_diagnostic(
        target_diagnostics,
        "package.target.unsupported",
        "package.artifact_requirements.target_unsupported",
    ):
        category = "target-unsupported"
        decision = "rejected"
    elif any(
        diagnostic.code.startswith("package.target_contract.")
        for diagnostic in target_diagnostics
    ):
        category = "target-unavailable"
        decision = "rejected"
    elif any(
        diagnostic.code == "package.identity.reflection_target_mismatch"
        or diagnostic.code.startswith("package.reflection.target_")
        for diagnostic in target_diagnostics
    ):
        category = "target-unavailable"
        decision = "rejected"
    else:
        category = "target-accepted"
        decision = "accepted"
    return {
        "decision": decision,
        "category": category,
        "requestedTarget": requested_target,
        "reportLoaderTarget": report.loader_target,
        "packageTarget": report.target,
        "matched": report.target == requested_target,
        "diagnostics": [diagnostic.to_summary() for diagnostic in target_diagnostics],
    }


def _runtime_artifact_selection_native_admission(
    *,
    report: PackageCompatibilityReport,
    requested_mode: str,
    selected_mode: str | None,
    artifact: Artifact | None,
    diagnostics: tuple[CompatibilityDiagnostic, ...],
) -> dict[str, Any]:
    native_artifact = _artifact_by_name(report.available_artifacts, "nativeBinary")
    native_diagnostics = tuple(
        diagnostic
        for diagnostic in diagnostics
        if diagnostic.artifact in NATIVE_ADMISSION_DIAGNOSTIC_ARTIFACTS
    )
    native_availability = report.artifact_availability["native"]
    native_usable = bool(native_availability["usable"])
    decision = (
        "accepted" if selected_mode == "native" and artifact is not None else "skipped"
    )
    category = "native-accepted" if decision == "accepted" else "native-unavailable"
    reason = "runtime.native_artifact.accepted"
    blocking_reason = next(
        (
            diagnostic
            for diagnostic in diagnostics
            if diagnostic.severity in {"error", "skip"}
            and diagnostic.artifact not in {"nativeBinary", "nativeBinaryStatus"}
        ),
        None,
    )
    native_blocking_reason = next(
        (
            diagnostic
            for diagnostic in native_diagnostics
            if diagnostic.severity in {"error", "skip"}
        ),
        None,
    )

    if decision != "accepted":
        if blocking_reason is not None:
            reason = blocking_reason.code
        elif requested_mode == SOURCE_PACKAGE_MODE:
            category = "native-not-requested"
            reason = "runtime.native_artifact.not_requested"
        elif report.target_contract is None:
            category = "native-unavailable"
            reason = "runtime.native_artifact.contract_unavailable"
        elif report.target_contract.package_mode == SOURCE_PACKAGE_MODE:
            category = "native-planned-only"
            reason = "runtime.native_artifact.source_package_fallback"
        elif native_artifact is None:
            reason = "package.artifact.selection_missing"
        elif not native_artifact.exists:
            reason = "package.artifact.selection_file_missing"
        elif not native_usable:
            reason = "package.native_binary_status.not_ready"
        elif native_blocking_reason is not None:
            reason = native_blocking_reason.code

    return {
        "decision": decision,
        "category": category,
        "reason": reason,
        "requested": requested_mode in {"auto", "native"},
        "selected": decision == "accepted",
        "artifactDeclared": native_artifact is not None,
        "artifactAvailable": native_artifact.exists if native_artifact else False,
        "nativeBinaryStatus": native_availability["nativeBinaryStatus"],
        "usable": native_usable,
        "diagnostics": [diagnostic.to_summary() for diagnostic in native_diagnostics],
    }


def _runtime_artifact_selection_source_package_fallback_admission(
    *,
    report: PackageCompatibilityReport,
    requested_mode: str,
    selected_mode: str | None,
    artifact: Artifact | None,
    diagnostics: tuple[CompatibilityDiagnostic, ...],
) -> dict[str, Any]:
    source_artifact = _artifact_by_name(report.available_artifacts, "backendSource")
    source_diagnostics = tuple(
        diagnostic
        for diagnostic in diagnostics
        if diagnostic.artifact == "backendSource"
    )
    contract = report.target_contract
    allowed = contract is not None and contract.package_mode == SOURCE_PACKAGE_MODE
    attempted = requested_mode in {"auto", SOURCE_PACKAGE_MODE} and allowed
    accepted = (
        selected_mode == SOURCE_PACKAGE_MODE
        and artifact is not None
        and artifact.name == "backendSource"
        and not _has_blocking_diagnostics(list(diagnostics))
    )
    if accepted:
        reason = "runtime.source_package_fallback.accepted"
        decision = "accepted"
    elif attempted:
        reason = "runtime.source_package_fallback.unavailable"
        decision = "rejected" if source_diagnostics else "skipped"
    elif not allowed:
        reason = "runtime.source_package_fallback.not_allowed"
        decision = "skipped"
    else:
        reason = "runtime.source_package_fallback.not_requested"
        decision = "skipped"
    return {
        "decision": decision,
        "fallbackAllowed": allowed,
        "fallbackAttempted": attempted,
        "fallbackAccepted": accepted,
        "reason": reason,
        "artifactDeclared": source_artifact is not None,
        "artifactAvailable": source_artifact.exists if source_artifact else False,
        "sourceParsingRequired": False,
        "diagnostics": [diagnostic.to_summary() for diagnostic in source_diagnostics],
    }


def _select_runtime_artifact_candidate(
    report: PackageCompatibilityReport,
    requested_mode: str,
) -> tuple[str, Artifact | None, tuple[CompatibilityDiagnostic, ...]]:
    selected_mode = (
        _auto_runtime_artifact_selection_mode(report)
        if requested_mode == "auto"
        else requested_mode
    )
    if selected_mode == "native":
        artifact, diagnostics = _select_native_runtime_artifact(report)
    else:
        artifact, diagnostics = _select_source_package_runtime_artifact(report)
    return selected_mode, artifact, diagnostics


def _auto_runtime_artifact_selection_mode(
    report: PackageCompatibilityReport,
) -> str:
    native_artifact = _artifact_by_name(report.available_artifacts, "nativeBinary")
    if _native_runtime_artifact_is_usable(report, native_artifact):
        return "native"
    if (
        report.target_contract is not None
        and report.target_contract.package_mode == SOURCE_PACKAGE_MODE
    ):
        return SOURCE_PACKAGE_MODE
    return "native"


def _native_runtime_artifact_is_usable(
    report: PackageCompatibilityReport,
    artifact: Artifact | None,
) -> bool:
    if artifact is None or not artifact.exists:
        return False
    contract = report.target_contract
    if contract is not None and contract.native_binary_status_required:
        return _native_binary_status_is_ready(report.native_binary_status)
    return True


def _native_artifact_descriptor_required_for_runtime_artifact(
    *,
    target: str | None,
    artifacts: tuple[Artifact, ...],
    native_binary_status: Any,
    contract: TargetArtifactContract | None,
) -> bool:
    native_artifact = _artifact_by_name(artifacts, "nativeBinary")
    if contract is None or native_artifact is None:
        return False
    if native_binary_status == "planned":
        return False
    if _native_binary_status_is_ready(native_binary_status):
        return True
    return (
        contract.requirements_source == "manifest" and contract.package_mode == "native"
    )


def _native_profile_required_for_runtime_artifact(
    *,
    target: str | None,
    artifacts: tuple[Artifact, ...],
    native_binary_status: Any,
    contract: TargetArtifactContract | None,
) -> bool:
    return (
        target == "vulkan"
        and _native_artifact_descriptor_required_for_runtime_artifact(
            target=target,
            artifacts=artifacts,
            native_binary_status=native_binary_status,
            contract=contract,
        )
    )


def _native_artifact_descriptor_required_for_runtime_selection(
    report: PackageCompatibilityReport,
) -> bool:
    return _native_artifact_descriptor_required_for_runtime_artifact(
        target=report.target,
        artifacts=report.available_artifacts,
        native_binary_status=report.native_binary_status,
        contract=report.target_contract,
    )


def _native_profile_required_for_runtime_selection(
    report: PackageCompatibilityReport,
) -> bool:
    return _native_profile_required_for_runtime_artifact(
        target=report.target,
        artifacts=report.available_artifacts,
        native_binary_status=report.native_binary_status,
        contract=report.target_contract,
    )


def _select_native_runtime_artifact(
    report: PackageCompatibilityReport,
) -> tuple[Artifact | None, tuple[CompatibilityDiagnostic, ...]]:
    diagnostics: list[CompatibilityDiagnostic] = []
    artifact = _artifact_by_name(report.available_artifacts, "nativeBinary")
    if artifact is None:
        diagnostics.append(
            CompatibilityDiagnostic(
                code="package.artifact.selection_missing",
                message=(
                    f"manifest.artifacts.nativeBinary is required for native "
                    f"runtime selection on target {report.target}"
                ),
                document="manifest",
                artifact="nativeBinary",
                expected="package-relative path",
                actual=None,
            )
        )
        return None, tuple(diagnostics)

    contract = report.target_contract
    if (
        contract is not None
        and contract.native_binary_status_required
        and not _native_binary_status_is_ready(report.native_binary_status)
    ):
        diagnostics.append(
            CompatibilityDiagnostic(
                code="package.native_binary_status.not_ready",
                message=(
                    f"native runtime artifact is not ready for target "
                    f"{report.target}: nativeBinaryStatus="
                    f"{report.native_binary_status!r}"
                ),
                document="manifest",
                artifact="nativeBinaryStatus",
                expected=sorted(NATIVE_BINARY_READY_STATUSES),
                actual=report.native_binary_status,
            )
        )
    if not artifact.exists:
        diagnostics.append(
            CompatibilityDiagnostic(
                code="package.artifact.selection_file_missing",
                message=(
                    f"selected native runtime artifact is missing on disk: "
                    f"{artifact.package_path}"
                ),
                document="manifest",
                artifact="nativeBinary",
                path=artifact.package_path,
                expected="regular file",
                actual="missing",
            )
        )

    if (
        _native_artifact_descriptor_required_for_runtime_selection(report)
        and _artifact_by_name(report.available_artifacts, "nativeArtifactDescriptor")
        is None
    ):
        diagnostics.append(
            CompatibilityDiagnostic(
                code="package.native_artifact_descriptor.required_missing",
                message=(
                    f"{report.target} native-ready runtime selection requires "
                    "manifest.artifacts.nativeArtifactDescriptor for native "
                    "runtime selection"
                ),
                document="manifest",
                artifact="nativeArtifactDescriptor",
                path="artifacts.nativeArtifactDescriptor",
                expected="declared native artifact descriptor metadata",
                actual="missing",
            )
        )

    if (
        _native_profile_required_for_runtime_selection(report)
        and _artifact_by_name(report.available_artifacts, "nativeProfile") is None
    ):
        diagnostics.append(
            CompatibilityDiagnostic(
                code="package.native_profile.required_missing",
                message=(
                    "vulkan native-ready runtime selection requires "
                    "manifest.artifacts.nativeProfile metadata"
                ),
                document="manifest",
                artifact="nativeProfile",
                path="artifacts.nativeProfile",
                expected="declared Vulkan native profile metadata",
                actual="missing",
            )
        )

    if diagnostics:
        return None, tuple(diagnostics)
    return artifact, ()


def _select_source_package_runtime_artifact(
    report: PackageCompatibilityReport,
) -> tuple[Artifact | None, tuple[CompatibilityDiagnostic, ...]]:
    diagnostics: list[CompatibilityDiagnostic] = []
    contract = report.target_contract
    if contract is None or contract.package_mode != SOURCE_PACKAGE_MODE:
        diagnostics.append(
            CompatibilityDiagnostic(
                code="package.mode.unsupported",
                message=(
                    f"target {report.target} does not support source-package "
                    "runtime artifact selection"
                ),
                document="manifest",
                expected=SOURCE_PACKAGE_MODE,
                actual=contract.package_mode if contract is not None else None,
            )
        )
        return None, tuple(diagnostics)

    artifact = _artifact_by_name(report.available_artifacts, "backendSource")
    if artifact is None:
        diagnostics.append(
            CompatibilityDiagnostic(
                code="package.artifact.selection_missing",
                message=(
                    f"manifest.artifacts.backendSource is required for "
                    f"source-package runtime selection on target {report.target}"
                ),
                document="manifest",
                artifact="backendSource",
                expected="package-relative path",
                actual=None,
            )
        )
        return None, tuple(diagnostics)
    if not artifact.exists:
        diagnostics.append(
            CompatibilityDiagnostic(
                code="package.artifact.selection_file_missing",
                message=(
                    f"selected source-package runtime artifact is missing on disk: "
                    f"{artifact.package_path}"
                ),
                document="manifest",
                artifact="backendSource",
                path=artifact.package_path,
                expected="regular file",
                actual="missing",
            )
        )
        return None, tuple(diagnostics)
    return artifact, ()


def _artifact_compatibility_summary(
    report: PackageCompatibilityReport,
    *,
    selected_artifact_name: str | None,
    infer_runtime_selection: bool,
) -> dict[str, Any]:
    records = _artifact_compatibility_records(
        report,
        selected_artifact_name=selected_artifact_name,
        infer_runtime_selection=infer_runtime_selection,
    )
    selected = next((record.name for record in records if record.selected), None)
    return {
        "schemaVersion": 1,
        "loaderTarget": report.loader_target,
        "packageTarget": report.target,
        "selectedArtifact": selected,
        "accepted": [
            record.to_summary() for record in records if record.decision == "accepted"
        ],
        "rejected": [
            record.to_summary() for record in records if record.decision == "rejected"
        ],
        "skipped": [
            record.to_summary() for record in records if record.decision == "skipped"
        ],
        "artifacts": [record.to_summary() for record in records],
    }


def _artifact_compatibility_records(
    report: PackageCompatibilityReport,
    *,
    selected_artifact_name: str | None,
    infer_runtime_selection: bool,
) -> tuple[PackageArtifactCompatibility, ...]:
    if selected_artifact_name is None and infer_runtime_selection:
        selected_artifact_name = _selected_artifact_name_for_report(report)

    artifacts_by_name = {
        artifact.name: artifact for artifact in report.available_artifacts
    }
    required_names = set(report.required_artifacts)
    artifact_names = _ordered_unique_strings(
        (
            *(artifact.name for artifact in report.available_artifacts),
            *report.required_artifacts,
            *(
                diagnostic.artifact
                for diagnostic in report.diagnostics
                if diagnostic.artifact is not None
                and diagnostic.artifact != "nativeBinaryStatus"
            ),
        )
    )
    package_rejects = _package_level_artifact_reject_diagnostics(report)
    target_skips = tuple(
        diagnostic
        for diagnostic in report.skip_reasons
        if diagnostic.code == "package.target.loader_mismatch"
    )

    records: list[PackageArtifactCompatibility] = []
    for name in artifact_names:
        artifact = artifacts_by_name.get(name)
        artifact_diagnostics = _artifact_related_diagnostics(report, name)
        selected = name == selected_artifact_name
        required = name in required_names

        error_diagnostics = tuple(
            diagnostic
            for diagnostic in artifact_diagnostics
            if diagnostic.severity == "error"
        )
        if error_diagnostics:
            records.append(
                _artifact_compatibility_record(
                    name=name,
                    decision="rejected",
                    reason=error_diagnostics[0].code,
                    message=error_diagnostics[0].message,
                    required=required,
                    selected=selected,
                    artifact=artifact,
                    diagnostics=error_diagnostics,
                )
            )
            continue

        if package_rejects:
            records.append(
                _artifact_compatibility_record(
                    name=name,
                    decision="rejected",
                    reason=package_rejects[0].code,
                    message=package_rejects[0].message,
                    required=required,
                    selected=selected,
                    artifact=artifact,
                    diagnostics=package_rejects,
                )
            )
            continue

        if target_skips:
            records.append(
                _artifact_compatibility_record(
                    name=name,
                    decision="skipped",
                    reason=target_skips[0].code,
                    message=target_skips[0].message,
                    required=required,
                    selected=False,
                    artifact=artifact,
                    diagnostics=target_skips,
                )
            )
            continue

        if artifact is None:
            records.append(
                _artifact_compatibility_record(
                    name=name,
                    decision="rejected",
                    reason="package.artifact.required_missing",
                    message=(
                        f"manifest.artifacts.{name} is required for target "
                        f"{report.target}"
                    ),
                    required=required,
                    selected=selected,
                    artifact=None,
                    diagnostics=artifact_diagnostics,
                )
            )
            continue

        if _planned_native_binary_is_skipped(report, name):
            records.append(
                _artifact_compatibility_record(
                    name=name,
                    decision="skipped",
                    reason="package.artifact.planned_native_binary",
                    message=(
                        "planned nativeBinary is declared but source-package "
                        "runtime selection does not require native bytes"
                    ),
                    required=required,
                    selected=False,
                    artifact=artifact,
                    diagnostics=artifact_diagnostics,
                )
            )
            continue

        if not artifact.exists:
            records.append(
                _artifact_compatibility_record(
                    name=name,
                    decision="rejected",
                    reason="package.artifact.file_missing",
                    message=(
                        f"manifest artifact {name} is declared but missing on disk: "
                        f"{artifact.package_path}"
                    ),
                    required=required,
                    selected=selected,
                    artifact=artifact,
                    diagnostics=artifact_diagnostics,
                )
            )
            continue

        if not required and not selected:
            records.append(
                _artifact_compatibility_record(
                    name=name,
                    decision="skipped",
                    reason="package.artifact.not_required",
                    message=(
                        f"manifest artifact {name} is not required by runtime "
                        f"target {report.loader_target or report.target}"
                    ),
                    required=False,
                    selected=False,
                    artifact=artifact,
                    diagnostics=artifact_diagnostics,
                )
            )
            continue

        records.append(
            _artifact_compatibility_record(
                name=name,
                decision="accepted",
                reason=(
                    "package.artifact.selected"
                    if selected
                    else "package.artifact.accepted"
                ),
                message=(
                    f"manifest artifact {name} is accepted for runtime target "
                    f"{report.loader_target or report.target}"
                ),
                required=required,
                selected=selected,
                artifact=artifact,
                diagnostics=artifact_diagnostics,
            )
        )

    return tuple(records)


def _artifact_compatibility_record(
    *,
    name: str,
    decision: str,
    reason: str,
    message: str,
    required: bool,
    selected: bool,
    artifact: Artifact | None,
    diagnostics: tuple[CompatibilityDiagnostic, ...],
) -> PackageArtifactCompatibility:
    return PackageArtifactCompatibility(
        name=name,
        decision=decision,
        reason=reason,
        message=message,
        required=required,
        selected=selected,
        artifact=artifact,
        diagnostics=diagnostics,
    )


def _selected_artifact_name_for_report(
    report: PackageCompatibilityReport,
) -> str | None:
    target = report.loader_target or report.target
    if not isinstance(target, str) or not target:
        return None
    try:
        selection = select_runtime_artifact(report, target=target)
    except PackageReadError:
        return None
    if selection.selected and selection.artifact is not None:
        return selection.artifact.name
    return None


def _artifact_related_diagnostics(
    report: PackageCompatibilityReport,
    artifact_name: str,
) -> tuple[CompatibilityDiagnostic, ...]:
    related_artifact_names = {artifact_name}
    if artifact_name == "nativeBinary":
        related_artifact_names.add("nativeBinaryStatus")
    return tuple(
        diagnostic
        for diagnostic in report.diagnostics
        if diagnostic.artifact in related_artifact_names
        or (
            artifact_name == "nativeBinary"
            and diagnostic.code in NATIVE_BINARY_DESCRIPTOR_CONTRACT_DIAGNOSTIC_CODES
        )
    )


def _package_level_artifact_reject_diagnostics(
    report: PackageCompatibilityReport,
) -> tuple[CompatibilityDiagnostic, ...]:
    return tuple(
        diagnostic
        for diagnostic in report.reject_reasons
        if diagnostic.artifact is None
    )


def _planned_native_binary_is_skipped(
    report: PackageCompatibilityReport,
    artifact_name: str,
) -> bool:
    contract = report.target_contract
    return (
        artifact_name == "nativeBinary"
        and report.native_binary_status == "planned"
        and contract is not None
        and contract.planned_native_binary_may_be_absent
    )


def _manifest_availability_summary(schema_version: Any) -> dict[str, Any]:
    return {
        "declared": True,
        "schemaVersion": schema_version,
        "compatible": schema_version == SUPPORTED_PACKAGE_SCHEMA_VERSION,
    }


def _reflection_availability_summary(reflection: dict[str, Any]) -> dict[str, Any]:
    entry_points = _json_object_list(reflection.get("entryPoints"))
    resources = _json_object_list(reflection.get("resources"))
    target_resource_bindings = _json_object_list(
        reflection.get("targetResourceBindings")
    )
    target_resource_binding_evidence_ids = [
        evidence_id
        for record in target_resource_bindings
        if isinstance(evidence_id := record.get("evidenceId"), str) and evidence_id
    ]
    target_feature_evidence_ids = _target_feature_evidence_ids(
        reflection.get("targetFeatures")
    )
    workgroup_sizes = _workgroup_size_records(reflection)
    schema_version = reflection.get("schemaVersion")
    return {
        "declared": True,
        "schemaVersion": schema_version,
        "compatible": schema_version == SUPPORTED_PACKAGE_SCHEMA_VERSION,
        "entryPointCount": len(entry_points),
        "resourceBindingCount": len(resources),
        "targetResourceBindingCount": len(target_resource_bindings),
        "targetResourceBindingEvidenceIds": target_resource_binding_evidence_ids,
        "targetFeatureEvidenceIds": list(target_feature_evidence_ids),
        "workgroupSizeCount": len(workgroup_sizes),
        "entryPointsAvailable": bool(entry_points),
        "resourceBindingsAvailable": bool(resources or target_resource_bindings),
        "workgroupSizesAvailable": bool(workgroup_sizes),
    }


def _workgroup_size_summary(reflection: dict[str, Any]) -> dict[str, Any]:
    records_value = reflection.get("workgroupSizes")
    raw_records = _json_object_list(records_value)
    records = _workgroup_size_records(reflection)
    return {
        "schemaVersion": 1,
        "metadataOnly": True,
        "declared": "workgroupSizes" in reflection,
        "available": bool(records),
        "recordCount": len(records),
        "malformedRecordCount": len(raw_records) - len(records),
        "records": list(records),
    }


def _workgroup_size_records(reflection: dict[str, Any]) -> tuple[dict[str, Any], ...]:
    return tuple(
        _summarize_workgroup_size_record(record)
        for record in _json_object_list(reflection.get("workgroupSizes"))
        if _is_workgroup_size_record(record)
    )


def _find_workgroup_size(
    reflection: dict[str, Any],
    stage: str,
    entry_point: str,
) -> dict[str, Any] | None:
    if not isinstance(stage, str) or not isinstance(entry_point, str):
        return None
    candidate_entry_points = set(
        _entry_point_lookup_names(reflection, stage, entry_point)
    )
    for record in _workgroup_size_records(reflection):
        if record.get("stage") != stage:
            continue
        if record.get("entryPoint") in candidate_entry_points:
            return record
    return None


def _entry_point_lookup_names(
    reflection: dict[str, Any],
    stage: str,
    entry_point: str,
) -> tuple[str, ...]:
    names: list[str] = [entry_point]
    for record in _json_object_list(reflection.get("entryPoints")):
        if record.get("stage") != stage:
            continue
        source_name = record.get("sourceName")
        backend_name = record.get("backendName")
        if entry_point not in (source_name, backend_name):
            continue
        if isinstance(source_name, str):
            names.append(source_name)
        if isinstance(backend_name, str):
            names.append(backend_name)
    return _ordered_unique_strings(names)


def _is_workgroup_size_record(record: dict[str, Any]) -> bool:
    return all(
        isinstance(record.get(field), str) and bool(record.get(field))
        for field in REFLECTION_WORKGROUP_SIZE_FIELDS
    )


def _summarize_workgroup_size_record(record: dict[str, Any]) -> dict[str, Any]:
    return {field: record[field] for field in REFLECTION_WORKGROUP_SIZE_FIELDS}


def _diagnostics_availability_summary(
    diagnostics_document: dict[str, Any],
) -> dict[str, Any]:
    diagnostics_value = diagnostics_document.get("diagnostics")
    diagnostics = _json_object_list(diagnostics_value)
    severities = [
        diagnostic.get("severity")
        for diagnostic in diagnostics
        if isinstance(diagnostic.get("severity"), str)
    ]
    schema_version = diagnostics_document.get("schemaVersion")
    record_shape_valid = _diagnostics_record_shape_valid(diagnostics_value)
    return {
        "declared": True,
        "schemaVersion": schema_version,
        "compatible": schema_version == SUPPORTED_PACKAGE_SCHEMA_VERSION,
        "valid": (
            schema_version == SUPPORTED_PACKAGE_SCHEMA_VERSION and record_shape_valid
        ),
        "recordShapeValid": record_shape_valid,
        "diagnosticCount": len(diagnostics),
        "maxSeverity": _max_diagnostic_severity(severities),
    }


def _diagnostics_record_shape_valid(value: Any) -> bool:
    if value is None:
        return True
    if not isinstance(value, list):
        return False
    for record in value:
        if not isinstance(record, dict):
            return False
        severity = record.get("severity")
        if severity is not None and (not isinstance(severity, str) or not severity):
            return False
    return True


def _available_targets(
    manifest_target: str | None,
    reflection: dict[str, Any],
) -> tuple[str, ...]:
    if not isinstance(manifest_target, str) or not manifest_target:
        return ()
    return tuple(
        _ordered_unique_strings(
            (
                manifest_target,
                *_matching_record_string_values(
                    reflection.get("targetResourceBindings"),
                    "target",
                    expected=manifest_target,
                ),
                *_matching_record_string_values(
                    reflection.get("targetFeatures"),
                    "target",
                    expected=manifest_target,
                ),
            )
        )
    )


def _target_availability_summary(
    manifest_target: str | None,
    reflection: dict[str, Any],
) -> dict[str, Any]:
    reflection_target = _optional_string(reflection.get("target"))
    target_resource_binding_targets = _matching_record_string_values(
        reflection.get("targetResourceBindings"),
        "target",
        expected=manifest_target,
    )
    target_feature_targets = _matching_record_string_values(
        reflection.get("targetFeatures"),
        "target",
        expected=manifest_target,
    )
    target_feature_evidence_ids = _target_feature_evidence_ids(
        reflection.get("targetFeatures"),
        expected=manifest_target,
    )
    return {
        "manifestTarget": manifest_target,
        "reflectionTarget": reflection_target,
        "targetResourceBindingTargets": list(target_resource_binding_targets),
        "targetFeatureTargets": list(target_feature_targets),
        "targetFeatureEvidenceIds": list(target_feature_evidence_ids),
        "availableTargets": list(_available_targets(manifest_target, reflection)),
    }


def _matching_record_string_values(
    value: Any,
    key: str,
    *,
    expected: str | None,
) -> tuple[str, ...]:
    if not isinstance(expected, str) or not expected:
        return ()
    return tuple(
        _ordered_unique_strings(
            record.get(key)
            for record in _json_object_list(value)
            if record.get(key) == expected
        )
    )


def _target_feature_evidence_ids(
    value: Any,
    *,
    expected: str | None = None,
) -> tuple[str, ...]:
    if expected is not None and (not isinstance(expected, str) or not expected):
        return ()
    evidence_ids: list[str] = []
    for record in _json_object_list(value):
        if expected is not None and record.get("target") != expected:
            continue
        record_evidence_ids = record.get("evidenceIds")
        if not isinstance(record_evidence_ids, list):
            continue
        evidence_ids.extend(
            entry for entry in record_evidence_ids if isinstance(entry, str) and entry
        )
    return _ordered_unique_strings(evidence_ids)


def _ordered_unique_strings(values: Any) -> tuple[str, ...]:
    ordered: list[str] = []
    seen: set[str] = set()
    for value in values:
        if not isinstance(value, str) or not value or value in seen:
            continue
        seen.add(value)
        ordered.append(value)
    return tuple(ordered)


def _json_object_list(value: Any) -> tuple[dict[str, Any], ...]:
    if not isinstance(value, list):
        return ()
    return tuple(item for item in value if isinstance(item, dict))


def _max_diagnostic_severity(severities: list[str]) -> str | None:
    if not severities:
        return None
    order = {
        "note": 0,
        "info": 1,
        "warning": 2,
        "error": 3,
        "fatal": 4,
    }
    return max(severities, key=lambda severity: order.get(severity, -1))


def _open_package_source(package_path: Path | str) -> _PackageSource:
    root = Path(package_path)
    if not root.exists():
        raise PackageReadError(f"package path does not exist: {root}")
    if root.is_dir():
        return _PackageSource(root=root, package_format="directory")
    if root.is_file() and zipfile.is_zipfile(root):
        return _PackageSource(
            root=root,
            package_format="zip",
            zip_members=_index_zip_members(root),
        )
    raise PackageReadError(f"expected .cglb directory or zip package: {root}")


def _index_zip_members(root: Path) -> dict[str, zipfile.ZipInfo]:
    with zipfile.ZipFile(root) as archive:
        infos = tuple(info for info in archive.infolist() if not info.is_dir())
    normalized_infos = tuple(
        (normalized_name, info)
        for info in infos
        for normalized_name in [_normalize_zip_member_name(info.filename)]
        if normalized_name is not None
    )
    prefix = _detect_zip_package_prefix(tuple(name for name, _info in normalized_infos))
    members: dict[str, zipfile.ZipInfo] = {}
    for normalized_name, info in normalized_infos:
        name = normalized_name
        if prefix:
            if not name.startswith(prefix):
                continue
            name = name[len(prefix) :]
        if not name:
            continue
        if name in members:
            raw_names = (members[name].filename, info.filename)
            raw_detail = (
                ""
                if raw_names[0] == raw_names[1]
                else f" ({raw_names[0]!r}, {raw_names[1]!r})"
            )
            raise PackageReadError(
                f"ambiguous duplicate package archive member: {name}{raw_detail}"
            )
        members[name] = info
    return members


def _detect_zip_package_prefix(names: tuple[str, ...]) -> str:
    safe_names = tuple(name for name in names if _zip_member_name_is_safe(name))
    root_metadata_names = frozenset(ROOT_METADATA_FILES)
    metadata_by_root: dict[str, set[str]] = {}
    for name in safe_names:
        if name in root_metadata_names:
            metadata_by_root.setdefault("", set()).add(name)
            continue
        if "/" not in name:
            continue
        prefix, stripped_name = name.split("/", 1)
        if stripped_name in root_metadata_names:
            metadata_by_root.setdefault(f"{prefix}/", set()).add(stripped_name)

    complete_roots = sorted(
        root
        for root, metadata_names in metadata_by_root.items()
        if root_metadata_names.issubset(metadata_names)
    )
    if len(complete_roots) > 1:
        raise PackageReadError(
            "ambiguous package root metadata in archive: "
            + ", ".join(_zip_metadata_root_label(root) for root in complete_roots)
        )
    if not complete_roots:
        return ""

    prefix = complete_roots[0]
    if prefix:
        top_level_directories = {
            name.split("/", 1)[0] for name in safe_names if "/" in name
        }
        if top_level_directories != {prefix.rstrip("/")}:
            return ""
    if prefix and metadata_by_root.get(""):
        raise PackageReadError(
            "ambiguous package root metadata in archive: archive root, "
            f"{_zip_metadata_root_label(prefix)}"
        )
    return prefix


def _zip_metadata_root_label(root: str) -> str:
    return "archive root" if not root else root.rstrip("/")


def _zip_member_name_is_safe(name: str) -> bool:
    return _normalize_zip_member_name(name) is not None


def _normalize_zip_member_name(name: str) -> str | None:
    if not name or "\\" in name:
        return None
    path = PurePosixPath(name)
    if path.is_absolute():
        return None
    if not path.parts or any(part == ".." for part in path.parts):
        return None
    normalized = path.as_posix()
    if not normalized or normalized == ".":
        return None
    return normalized


def _resolve_package_relative_member(value: str, label: str) -> str:
    if not value:
        raise PackageReadError(f"{label} must be a non-empty package-relative path")
    if "\\" in value:
        raise PackageReadError(f"{label} must use '/' separators")

    path = PurePosixPath(value)
    if path.is_absolute():
        raise PackageReadError(f"{label} must be package-relative")
    if not path.parts:
        raise PackageReadError(f"{label} must be a non-empty package-relative path")
    _validate_package_relative_path_segments(
        value,
        label,
        escape_container="archive",
    )
    return path.as_posix()


def _validate_package_relative_path_segments(
    value: str,
    label: str,
    *,
    escape_container: str,
) -> None:
    parts = value.split("/")
    if any(part == ".." for part in parts):
        raise PackageReadError(f"{label} escapes the package {escape_container}")
    if any(part in ("", ".") for part in parts):
        raise PackageReadError(f"{label} must be a normalized package-relative path")


def _read_source_json_object(
    source: _PackageSource,
    package_path: str,
    *,
    root_file_name: str,
) -> dict[str, Any]:
    if not source.is_zip:
        return _read_json_object(
            source.root / package_path, root_file_name=root_file_name
        )

    info = source.zip_info(package_path)
    if info is None:
        raise PackageReadError(f"missing package metadata: {root_file_name}")
    with zipfile.ZipFile(source.root) as archive:
        payload = _read_zip_json_payload(archive, info, root_file_name=root_file_name)
    return _parse_json_object_payload(payload, root_file_name=root_file_name)


def _read_source_json_object_for_report(
    source: _PackageSource,
    package_path: str,
    *,
    root_file_name: str,
    diagnostics: list[CompatibilityDiagnostic],
) -> dict[str, Any]:
    try:
        return _read_source_json_object(
            source, package_path, root_file_name=root_file_name
        )
    except PackageReadError as error:
        diagnostics.append(
            _metadata_read_diagnostic(
                root_file_name=root_file_name,
                error=error,
            )
        )
        return {}


def _metadata_read_diagnostic(
    *,
    root_file_name: str,
    error: PackageReadError,
) -> CompatibilityDiagnostic:
    document = root_file_name.removesuffix(".json")
    message = str(error)
    if isinstance(error, _MetadataTooLargeError):
        return CompatibilityDiagnostic(
            code="package.metadata.too_large",
            message=message,
            document=document,
            expected=f"<= {error.limit} bytes",
            actual=error.size,
        )
    missing_prefixes = (
        "missing package metadata:",
        "package metadata is not a file:",
    )
    missing = any(message.startswith(prefix) for prefix in missing_prefixes)
    return CompatibilityDiagnostic(
        code="package.metadata.missing" if missing else "package.metadata.invalid",
        message=message,
        document=document,
        expected="JSON object metadata file",
        actual="missing" if missing else "invalid",
    )


def _unreadable_metadata_documents(
    diagnostics: list[CompatibilityDiagnostic],
) -> frozenset[str]:
    return frozenset(
        diagnostic.document
        for diagnostic in diagnostics
        if diagnostic.code
        in {
            "package.metadata.missing",
            "package.metadata.invalid",
            "package.metadata.too_large",
        }
        and diagnostic.document is not None
    )


def _read_file_json_payload(path: Path, *, root_file_name: str) -> bytes:
    limit = RUNTIME_METADATA_JSON_BYTE_LIMIT
    size = path.stat().st_size
    if size > limit:
        raise _MetadataTooLargeError(root_file_name, size, limit)
    with path.open("rb") as handle:
        payload = handle.read(limit + 1)
    if len(payload) > limit:
        raise _MetadataTooLargeError(root_file_name, len(payload), limit)
    return payload


def _read_zip_json_payload(
    archive: zipfile.ZipFile,
    info: zipfile.ZipInfo,
    *,
    root_file_name: str,
) -> bytes:
    limit = RUNTIME_METADATA_JSON_BYTE_LIMIT
    if info.file_size > limit:
        raise _MetadataTooLargeError(root_file_name, info.file_size, limit)
    with archive.open(info) as handle:
        payload = handle.read(limit + 1)
    if len(payload) > limit:
        raise _MetadataTooLargeError(root_file_name, len(payload), limit)
    return payload


def _parse_json_object_payload(
    payload: bytes,
    *,
    root_file_name: str,
) -> dict[str, Any]:
    try:
        text = payload.decode("utf-8")
    except UnicodeDecodeError as error:
        raise PackageReadError(
            f"invalid UTF-8 in {root_file_name}: {error.reason}"
        ) from error
    try:
        data = json.loads(text)
    except json.JSONDecodeError as error:
        raise PackageReadError(
            f"invalid JSON in {root_file_name}: {error.msg}"
        ) from error
    if not isinstance(data, dict):
        raise PackageReadError(f"{root_file_name} must contain a JSON object")
    return data


def _read_json_object(path: Path, *, root_file_name: str) -> dict[str, Any]:
    if not path.exists():
        raise PackageReadError(f"missing package metadata: {root_file_name}")
    if not path.is_file():
        raise PackageReadError(f"package metadata is not a file: {root_file_name}")
    payload = _read_file_json_payload(path, root_file_name=root_file_name)
    return _parse_json_object_payload(payload, root_file_name=root_file_name)


def _read_optional_artifact_json_object(
    source: _PackageSource,
    artifact_name: str,
    artifacts: list[Artifact],
    *,
    root_file_name: str,
) -> dict[str, Any] | None:
    artifact = next(
        (candidate for candidate in artifacts if candidate.name == artifact_name),
        None,
    )
    if artifact is None or not artifact.exists:
        return None
    if source.is_zip:
        member = artifact.archive_member or artifact.package_path
        try:
            with zipfile.ZipFile(source.root) as archive:
                info = archive.getinfo(member)
                payload = _read_zip_json_payload(
                    archive,
                    info,
                    root_file_name=root_file_name,
                )
        except KeyError as error:
            raise PackageReadError(
                f"missing package metadata: {root_file_name}"
            ) from error
        return _parse_json_object_payload(payload, root_file_name=root_file_name)
    return _read_json_object(artifact.path, root_file_name=root_file_name)


def _read_optional_artifact_json_object_for_report(
    source: _PackageSource,
    artifact_name: str,
    artifacts: list[Artifact],
    *,
    root_file_name: str,
    diagnostics: list[CompatibilityDiagnostic],
    document: str = "debugMetadata",
    diagnostic_prefix: str = "package.debug_metadata",
    expected: str = "JSON object debug metadata",
) -> dict[str, Any] | None:
    artifact = next(
        (candidate for candidate in artifacts if candidate.name == artifact_name),
        None,
    )
    try:
        return _read_optional_artifact_json_object(
            source,
            artifact_name,
            artifacts,
            root_file_name=root_file_name,
        )
    except PackageReadError as error:
        if isinstance(error, _MetadataTooLargeError):
            diagnostics.append(
                CompatibilityDiagnostic(
                    code=f"{diagnostic_prefix}.too_large",
                    message=str(error),
                    document=document,
                    artifact=artifact_name,
                    path=artifact.package_path if artifact is not None else None,
                    expected=f"<= {error.limit} bytes",
                    actual=error.size,
                )
            )
            return None
        diagnostics.append(
            CompatibilityDiagnostic(
                code=f"{diagnostic_prefix}.invalid",
                message=str(error),
                document=document,
                artifact=artifact_name,
                path=artifact.package_path if artifact is not None else None,
                expected=expected,
                actual="invalid",
            )
        )
        return None


def _empty_target_legalization_manifest_tool_requirements() -> dict[str, Any]:
    return {
        "present": False,
        "target": None,
        "packageMode": None,
        "requiredToolCount": None,
        "missingToolCount": None,
        "requiredToolIds": None,
        "missingToolIds": None,
        "optionalNativeToolMissing": None,
        "optionalNativeToolStatus": None,
        "toolRequirementEvidenceIds": None,
    }


def _manifest_target_legalization_tool_requirements(
    diagnostics: list[CompatibilityDiagnostic],
    *,
    manifest: dict[str, Any],
    target: str | None,
    target_contract: TargetArtifactContract | None,
) -> dict[str, Any]:
    if "targetLegalizationToolRequirements" not in manifest:
        return _empty_target_legalization_manifest_tool_requirements()

    requirements = manifest.get("targetLegalizationToolRequirements")
    if not isinstance(requirements, dict):
        diagnostics.append(
            CompatibilityDiagnostic(
                code="package.target_legalization_evidence.manifest_tool_requirements_invalid",
                message="manifest.targetLegalizationToolRequirements must be an object",
                document="manifest",
                path="targetLegalizationToolRequirements",
                expected="object",
                actual=_json_type_name(requirements),
            )
        )
        return _empty_target_legalization_manifest_tool_requirements()

    _append_target_legalization_tool_requirement_key_diagnostics(
        requirements,
        diagnostics,
    )
    parsed = _empty_target_legalization_manifest_tool_requirements()
    parsed["present"] = True
    parsed["target"] = _target_legalization_required_string_field(
        diagnostics,
        document="manifest",
        object_path="targetLegalizationToolRequirements",
        record=requirements,
        field="target",
        code_prefix="package.target_legalization_evidence.manifest_tool_requirements",
    )
    parsed["packageMode"] = _target_legalization_required_string_field(
        diagnostics,
        document="manifest",
        object_path="targetLegalizationToolRequirements",
        record=requirements,
        field="packageMode",
        expected=("native", SOURCE_PACKAGE_MODE),
        code_prefix="package.target_legalization_evidence.manifest_tool_requirements",
    )
    parsed["requiredToolCount"] = _target_legalization_unsigned_field(
        diagnostics,
        document="manifest",
        path="targetLegalizationToolRequirements.requiredToolCount",
        value=requirements.get("requiredToolCount"),
        present="requiredToolCount" in requirements,
        code_prefix="package.target_legalization_evidence.manifest_tool_requirements",
    )
    parsed["missingToolCount"] = _target_legalization_unsigned_field(
        diagnostics,
        document="manifest",
        path="targetLegalizationToolRequirements.missingToolCount",
        value=requirements.get("missingToolCount"),
        present="missingToolCount" in requirements,
        code_prefix="package.target_legalization_evidence.manifest_tool_requirements",
    )
    parsed["requiredToolIds"] = _target_legalization_string_array_field(
        diagnostics,
        document="manifest",
        path="targetLegalizationToolRequirements.requiredToolIds",
        value=requirements.get("requiredToolIds"),
        present="requiredToolIds" in requirements,
        code_prefix="package.target_legalization_evidence.manifest_tool_requirements",
        allow_empty=True,
    )
    parsed["missingToolIds"] = _target_legalization_string_array_field(
        diagnostics,
        document="manifest",
        path="targetLegalizationToolRequirements.missingToolIds",
        value=requirements.get("missingToolIds"),
        present="missingToolIds" in requirements,
        code_prefix="package.target_legalization_evidence.manifest_tool_requirements",
        allow_empty=True,
    )
    parsed["optionalNativeToolMissing"] = _optional_bool_field(
        diagnostics,
        document="manifest",
        path="targetLegalizationToolRequirements.optionalNativeToolMissing",
        value=requirements.get("optionalNativeToolMissing"),
        present="optionalNativeToolMissing" in requirements,
        code_prefix="package.target_legalization_evidence.manifest_tool_requirements",
    )
    parsed["optionalNativeToolStatus"] = _target_legalization_required_string_field(
        diagnostics,
        document="manifest",
        object_path="targetLegalizationToolRequirements",
        record=requirements,
        field="optionalNativeToolStatus",
        expected=tuple(sorted(TARGET_LEGALIZATION_OPTIONAL_NATIVE_TOOL_STATUSES)),
        code_prefix="package.target_legalization_evidence.manifest_tool_requirements",
    )
    parsed["toolRequirementEvidenceIds"] = _target_legalization_string_array_field(
        diagnostics,
        document="manifest",
        path="targetLegalizationToolRequirements.toolRequirementEvidenceIds",
        value=requirements.get("toolRequirementEvidenceIds"),
        present="toolRequirementEvidenceIds" in requirements,
        code_prefix="package.target_legalization_evidence.manifest_tool_requirements",
    )

    _append_manifest_target_legalization_tool_requirement_consistency_diagnostics(
        diagnostics,
        requirements=parsed,
        package_target=target,
        target_contract=target_contract,
    )
    return parsed


def _append_target_legalization_tool_requirement_key_diagnostics(
    requirements: dict[str, Any],
    diagnostics: list[CompatibilityDiagnostic],
) -> None:
    for field in sorted(set(requirements) - TARGET_LEGALIZATION_TOOL_REQUIREMENT_KEYS):
        diagnostics.append(
            CompatibilityDiagnostic(
                code="package.target_legalization_evidence.manifest_tool_requirements_unexpected_field",
                message=(
                    "manifest.targetLegalizationToolRequirements contains an "
                    f"unexpected field: {field}"
                ),
                document="manifest",
                path=f"targetLegalizationToolRequirements.{field}",
                expected=sorted(TARGET_LEGALIZATION_TOOL_REQUIREMENT_KEYS),
                actual=field,
            )
        )


def _target_legalization_required_string_field(
    diagnostics: list[CompatibilityDiagnostic],
    *,
    document: str,
    object_path: str,
    record: dict[str, Any],
    field: str,
    code_prefix: str,
    expected: tuple[str, ...] | None = None,
) -> str | None:
    path = f"{object_path}.{field}"
    if field not in record:
        diagnostics.append(
            CompatibilityDiagnostic(
                code=f"{code_prefix}_{_snake_case(field)}_missing",
                message=f"{document}.{path} is required",
                document=document,
                path=path,
                expected=list(expected) if expected is not None else "non-empty string",
                actual=None,
            )
        )
        return None
    value = record.get(field)
    if (
        not isinstance(value, str)
        or not value
        or (expected is not None and value not in expected)
    ):
        diagnostics.append(
            CompatibilityDiagnostic(
                code=f"{code_prefix}_{_snake_case(field)}_invalid",
                message=f"{document}.{path} is invalid",
                document=document,
                path=path,
                expected=list(expected) if expected is not None else "non-empty string",
                actual=_contract_actual_value(value),
            )
        )
        return None
    return value


def _append_manifest_target_legalization_tool_requirement_consistency_diagnostics(
    diagnostics: list[CompatibilityDiagnostic],
    *,
    requirements: dict[str, Any],
    package_target: str | None,
    target_contract: TargetArtifactContract | None,
) -> None:
    if not requirements["present"]:
        return

    target = requirements["target"]
    package_mode = requirements["packageMode"]
    required_tool_count = requirements["requiredToolCount"]
    missing_tool_count = requirements["missingToolCount"]
    required_tool_ids = requirements["requiredToolIds"]
    missing_tool_ids = requirements["missingToolIds"]
    optional_missing = requirements["optionalNativeToolMissing"]
    optional_status = requirements["optionalNativeToolStatus"]
    evidence_ids = requirements["toolRequirementEvidenceIds"]

    if target is not None and target != package_target:
        diagnostics.append(
            CompatibilityDiagnostic(
                code="package.target_legalization_evidence.manifest_tool_requirements_target_mismatch",
                message=(
                    "manifest.targetLegalizationToolRequirements.target must "
                    "match manifest.target"
                ),
                document="manifest",
                path="targetLegalizationToolRequirements.target",
                expected=package_target,
                actual=target,
            )
        )
    if (
        package_mode is not None
        and target_contract is not None
        and package_mode != target_contract.package_mode
    ):
        diagnostics.append(
            CompatibilityDiagnostic(
                code="package.target_legalization_evidence.manifest_tool_requirements_package_mode_mismatch",
                message=(
                    "manifest.targetLegalizationToolRequirements.packageMode "
                    "must match package artifact requirements"
                ),
                document="manifest",
                path="targetLegalizationToolRequirements.packageMode",
                expected=target_contract.package_mode,
                actual=package_mode,
            )
        )

    if (
        required_tool_count is not None
        and required_tool_ids is not None
        and required_tool_count != len(required_tool_ids)
    ) or (
        missing_tool_count is not None
        and missing_tool_ids is not None
        and missing_tool_count != len(missing_tool_ids)
    ):
        diagnostics.append(
            CompatibilityDiagnostic(
                code="package.target_legalization_evidence.manifest_tool_requirements_tool_counts_mismatch",
                message=(
                    "manifest.targetLegalizationToolRequirements tool counts "
                    "must match tool ID arrays"
                ),
                document="manifest",
                path="targetLegalizationToolRequirements",
                expected={
                    "requiredToolCount": (
                        len(required_tool_ids)
                        if required_tool_ids is not None
                        else None
                    ),
                    "missingToolCount": (
                        len(missing_tool_ids) if missing_tool_ids is not None else None
                    ),
                },
                actual={
                    "requiredToolCount": required_tool_count,
                    "missingToolCount": missing_tool_count,
                },
            )
        )

    if target is not None and required_tool_ids is not None:
        _append_tool_id_target_diagnostics(
            diagnostics,
            path="targetLegalizationToolRequirements.requiredToolIds",
            values=required_tool_ids,
            target=target,
        )
    if (
        target is not None
        and required_tool_ids is not None
        and missing_tool_ids is not None
    ):
        _append_missing_tool_id_diagnostics(
            diagnostics,
            path="targetLegalizationToolRequirements.missingToolIds",
            missing_tool_ids=missing_tool_ids,
            required_tool_ids=required_tool_ids,
            target=target,
        )

    if (
        package_mode is not None
        and required_tool_ids is not None
        and missing_tool_ids is not None
        and (
            optional_missing
            != _target_legalization_optional_native_tool_missing(
                package_mode,
                missing_tool_ids,
            )
            or optional_status
            != _target_legalization_optional_native_tool_status(
                package_mode,
                required_tool_ids,
                missing_tool_ids,
            )
        )
    ):
        diagnostics.append(
            CompatibilityDiagnostic(
                code="package.target_legalization_evidence.manifest_tool_requirements_optional_native_tool_status_inconsistent",
                message=(
                    "manifest.targetLegalizationToolRequirements optional "
                    "native tool status is inconsistent"
                ),
                document="manifest",
                path="targetLegalizationToolRequirements",
                expected={
                    "optionalNativeToolMissing": (
                        _target_legalization_optional_native_tool_missing(
                            package_mode,
                            missing_tool_ids,
                        )
                    ),
                    "optionalNativeToolStatus": (
                        _target_legalization_optional_native_tool_status(
                            package_mode,
                            required_tool_ids,
                            missing_tool_ids,
                        )
                    ),
                },
                actual={
                    "optionalNativeToolMissing": optional_missing,
                    "optionalNativeToolStatus": optional_status,
                },
            )
        )

    if target is not None and evidence_ids is not None:
        prefix = f"target-legalization.v1.{target}."
        for index, evidence_id in enumerate(evidence_ids):
            if not evidence_id.startswith(prefix):
                diagnostics.append(
                    CompatibilityDiagnostic(
                        code="package.target_legalization_evidence.manifest_tool_requirements_tool_requirement_evidence_ids_target_mismatch",
                        message=(
                            "manifest.targetLegalizationToolRequirements."
                            "toolRequirementEvidenceIds must match its target"
                        ),
                        document="manifest",
                        path=(
                            "targetLegalizationToolRequirements."
                            f"toolRequirementEvidenceIds[{index}]"
                        ),
                        expected=f"{prefix}*",
                        actual=evidence_id,
                    )
                )
        if (
            required_tool_ids is not None
            and missing_tool_ids is not None
            and all(
                _target_legalization_tool_id_matches_target(tool_id, target)
                for tool_id in (*required_tool_ids, *missing_tool_ids)
            )
        ):
            expected_ids = _target_legalization_tool_requirement_evidence_ids(
                target,
                required_tool_ids,
                missing_tool_ids,
            )
            if evidence_ids != expected_ids:
                diagnostics.append(
                    CompatibilityDiagnostic(
                        code="package.target_legalization_evidence.manifest_tool_requirements_tool_requirement_evidence_ids_mismatch",
                        message=(
                            "manifest.targetLegalizationToolRequirements."
                            "toolRequirementEvidenceIds must match recorded "
                            "tool IDs"
                        ),
                        document="manifest",
                        path=(
                            "targetLegalizationToolRequirements."
                            "toolRequirementEvidenceIds"
                        ),
                        expected=list(expected_ids),
                        actual=list(evidence_ids),
                    )
                )


def _append_tool_id_target_diagnostics(
    diagnostics: list[CompatibilityDiagnostic],
    *,
    path: str,
    values: tuple[str, ...],
    target: str,
) -> None:
    for index, tool_id in enumerate(values):
        if not _target_legalization_tool_id_matches_target(tool_id, target):
            diagnostics.append(
                CompatibilityDiagnostic(
                    code=(
                        "package.target_legalization_evidence."
                        f"manifest_tool_requirements_{_target_legalization_code_field(path)}_target_mismatch"
                    ),
                    message=(
                        f"manifest.{path} must contain tool IDs for "
                        "targetLegalizationToolRequirements.target"
                    ),
                    document="manifest",
                    path=f"{path}[{index}]",
                    expected=f"{target}.*.*",
                    actual=tool_id,
                )
            )


def _append_missing_tool_id_diagnostics(
    diagnostics: list[CompatibilityDiagnostic],
    *,
    path: str,
    missing_tool_ids: tuple[str, ...],
    required_tool_ids: tuple[str, ...],
    target: str,
) -> None:
    required = frozenset(required_tool_ids)
    for index, tool_id in enumerate(missing_tool_ids):
        if tool_id not in required or not _target_legalization_tool_id_matches_target(
            tool_id, target
        ):
            diagnostics.append(
                CompatibilityDiagnostic(
                    code="package.target_legalization_evidence.manifest_tool_requirements_missing_tool_ids_subset_mismatch",
                    message=(
                        "manifest.targetLegalizationToolRequirements."
                        "missingToolIds must be a subset of requiredToolIds "
                        "for its target"
                    ),
                    document="manifest",
                    path=f"{path}[{index}]",
                    expected="subset of requiredToolIds for target",
                    actual=tool_id,
                )
            )


def _target_legalization_tool_id_matches_target(tool_id: str, target: str) -> bool:
    parts = tool_id.split(".", 2)
    return len(parts) == 3 and parts[0] == target and bool(parts[1]) and bool(parts[2])


def _target_legalization_optional_native_tool_missing(
    package_mode: str,
    missing_tool_ids: tuple[str, ...],
) -> bool:
    return package_mode == SOURCE_PACKAGE_MODE and bool(missing_tool_ids)


def _target_legalization_optional_native_tool_status(
    package_mode: str,
    required_tool_ids: tuple[str, ...],
    missing_tool_ids: tuple[str, ...],
) -> str:
    if package_mode != SOURCE_PACKAGE_MODE:
        return "not-required"
    if missing_tool_ids:
        return "missing"
    if required_tool_ids:
        return "available"
    return "not-required"


def _target_legalization_tool_requirement_evidence_ids(
    target: str,
    required_tool_ids: tuple[str, ...],
    missing_tool_ids: tuple[str, ...],
) -> tuple[str, ...]:
    state = "present" if required_tool_ids or missing_tool_ids else "empty"
    evidence_ids = [f"target-legalization.v1.{target}.tool-requirements.{state}"]
    for tool_id in required_tool_ids:
        _tool_target, kind, name = tool_id.split(".", 2)
        evidence_ids.append(
            f"target-legalization.v1.{target}.tool-requirement.required.{kind}.{name}"
        )
    for tool_id in missing_tool_ids:
        _tool_target, kind, name = tool_id.split(".", 2)
        evidence_ids.append(
            f"target-legalization.v1.{target}.tool-requirement.missing.{kind}.{name}"
        )
    return tuple(evidence_ids)


def _target_legalization_evidence_summary(
    diagnostics: list[CompatibilityDiagnostic],
    *,
    target: str | None,
    target_contract: TargetArtifactContract | None,
    manifest: dict[str, Any],
    artifacts: tuple[Artifact, ...],
    debug_metadata: dict[str, Any] | None,
    target_explanation: dict[str, Any] | None,
    unreadable_documents: frozenset[str],
) -> dict[str, Any]:
    diagnostic_start = len(diagnostics)
    debug_artifact = _artifact_by_name(artifacts, "debugMetadata")
    target_explanation_artifact = _artifact_by_name(artifacts, "targetExplanation")
    manifest_requirements = manifest.get("packageArtifactRequirements")
    manifest_requirement_ids = (
        _valid_string_tuple(manifest_requirements.get("evidenceIds"))
        if isinstance(manifest_requirements, dict)
        else None
    )
    requirements_declared = "manifest" not in unreadable_documents and isinstance(
        manifest_requirements, dict
    )
    manifest_tool_requirements = _manifest_target_legalization_tool_requirements(
        diagnostics,
        manifest=manifest,
        target=target,
        target_contract=target_contract,
    )

    debug_sidecar = _debug_metadata_target_legalization_sidecar(
        diagnostics,
        artifact=debug_artifact,
        document=debug_metadata,
    )
    target_explanation_sidecar = _target_explanation_legalization_sidecar(
        diagnostics,
        artifact=target_explanation_artifact,
        document=target_explanation,
        package_target=target,
    )

    for label, sidecar in (
        ("debug_metadata", debug_sidecar),
        ("target_explanation", target_explanation_sidecar),
    ):
        _append_target_legalization_sidecar_consistency_diagnostics(
            diagnostics,
            label=label,
            sidecar=sidecar,
            package_target=target,
            target_contract=target_contract,
            manifest_requirement_ids=manifest_requirement_ids,
            manifest_tool_requirements=manifest_tool_requirements,
        )

    aggregate_requirement_ids = (
        manifest_requirement_ids
        or debug_sidecar["packageArtifactRequirementEvidenceIds"]
        or target_explanation_sidecar["packageArtifactRequirementEvidenceIds"]
    )
    package_mode, package_mode_source = _target_legalization_package_mode(
        requirements_declared=requirements_declared,
        target_contract=target_contract,
        debug_sidecar=debug_sidecar,
        target_explanation_sidecar=target_explanation_sidecar,
    )
    missing_evidence: list[str] = []
    if (
        debug_sidecar["legalizationEvidencePresent"]
        and debug_sidecar["artifactExists"]
        and not debug_sidecar["legalizationCoreEvidenceIds"]
    ):
        missing_evidence.append(
            "debugMetadata.targetDecision.selectedTargetLegalizationCoreEvidenceIds"
        )
    if (
        target_explanation_sidecar["artifactExists"]
        and not target_explanation_sidecar["legalizationCoreEvidenceIds"]
    ):
        missing_evidence.append(
            "targetExplanation.targets[].legalizationCoreEvidenceIds"
        )
    if requirements_declared and not aggregate_requirement_ids:
        missing_evidence.append("packageArtifactRequirementEvidenceIds")
    if (
        manifest_tool_requirements["present"]
        and not manifest_tool_requirements["toolRequirementEvidenceIds"]
    ):
        missing_evidence.append(
            "manifest.targetLegalizationToolRequirements.toolRequirementEvidenceIds"
        )

    applicable = (
        requirements_declared
        or manifest_tool_requirements["present"]
        or debug_sidecar["legalizationEvidencePresent"]
        or target_explanation_sidecar["artifactPresent"]
    )
    evidence_diagnostics = tuple(
        diagnostic
        for diagnostic in diagnostics[diagnostic_start:]
        if diagnostic.code.startswith("package.target_legalization_evidence.")
        or diagnostic.code.startswith("package.target_explanation.")
    )
    blocking = any(
        diagnostic.severity == "error" for diagnostic in evidence_diagnostics
    )
    if not applicable:
        health = "not-present"
    elif blocking:
        health = "drift"
    elif _target_legalization_evidence_incomplete(
        debug_sidecar,
        target_explanation_sidecar,
    ):
        health = "incomplete"
    elif missing_evidence:
        health = "partial"
    else:
        health = "ok"

    return {
        "health": health,
        "packageMode": package_mode,
        "packageModeSource": package_mode_source,
        "manifestToolRequirements": _target_legalization_manifest_tool_requirements_summary(
            manifest_tool_requirements
        ),
        "debugMetadata": _target_legalization_sidecar_summary(debug_sidecar),
        "targetExplanation": _target_legalization_sidecar_summary(
            target_explanation_sidecar
        ),
        "packageArtifactRequirementEvidenceIds": (
            list(aggregate_requirement_ids) if aggregate_requirement_ids else None
        ),
        "missingEvidence": missing_evidence,
        "checks": {
            "manifestToolRequirementsTargetMatchesPackage": _target_matches(
                manifest_tool_requirements["target"],
                target,
            ),
            "manifestToolRequirementsPackageModeMatchesRequirements": (
                _package_mode_matches(
                    manifest_tool_requirements["packageMode"],
                    target_contract,
                )
                if manifest_tool_requirements["present"]
                else None
            ),
            "manifestToolRequirementEvidenceIdsPresent": (
                bool(manifest_tool_requirements["toolRequirementEvidenceIds"])
                if manifest_tool_requirements["present"]
                else None
            ),
            "debugMetadataTargetMatchesPackage": _target_matches(
                debug_sidecar["target"], target
            ),
            "targetExplanationTargetMatchesPackage": _target_matches(
                target_explanation_sidecar["target"], target
            ),
            "debugMetadataPackageModeMatchesRequirements": _package_mode_matches(
                debug_sidecar["packageMode"], target_contract
            ),
            "targetExplanationPackageModeMatchesRequirements": _package_mode_matches(
                target_explanation_sidecar["packageMode"], target_contract
            ),
            "debugMetadataToolRequirementsMatchManifest": (
                _sidecar_tool_requirements_match_manifest(
                    manifest_tool_requirements,
                    debug_sidecar,
                )
            ),
            "targetExplanationToolRequirementsMatchManifest": (
                _sidecar_tool_requirements_match_manifest(
                    manifest_tool_requirements,
                    target_explanation_sidecar,
                )
            ),
            "packageArtifactRequirementEvidenceIdsPresent": (
                bool(aggregate_requirement_ids) if requirements_declared else None
            ),
        },
        "diagnosticCount": len(evidence_diagnostics),
        "diagnostics": [diagnostic.to_summary() for diagnostic in evidence_diagnostics],
    }


def _debug_metadata_target_legalization_sidecar(
    diagnostics: list[CompatibilityDiagnostic],
    *,
    artifact: Artifact | None,
    document: dict[str, Any] | None,
) -> dict[str, Any]:
    sidecar = _empty_target_legalization_sidecar(artifact)
    if document is None:
        return sidecar
    decision = document.get("targetDecision")
    if decision is None:
        return sidecar
    if not isinstance(decision, dict):
        diagnostics.append(
            CompatibilityDiagnostic(
                code="package.target_legalization_evidence.debug_metadata_decision_invalid",
                message="debugMetadata.targetDecision must be an object",
                document="debugMetadata",
                path="targetDecision",
                expected="object",
                actual=_json_type_name(decision),
            )
        )
        return sidecar

    sidecar["target"] = _optional_string(decision.get("selectedTarget"))
    sidecar["packageMode"] = _optional_string(decision.get("selectedTargetPackageMode"))
    sidecar["packageDecisionReason"] = _optional_string(
        decision.get("packageDecisionReason")
    )
    sidecar["packageBuildSupported"] = _optional_bool_field(
        diagnostics,
        document="debugMetadata",
        path="targetDecision.selectedTargetPackageBuildSupported",
        value=decision.get("selectedTargetPackageBuildSupported"),
        present="selectedTargetPackageBuildSupported" in decision,
        code_prefix="package.target_legalization_evidence.debug_metadata",
    )
    sidecar["legalizationCoreEvidenceIds"] = _target_legalization_string_array_field(
        diagnostics,
        document="debugMetadata",
        path="targetDecision.selectedTargetLegalizationCoreEvidenceIds",
        value=decision.get("selectedTargetLegalizationCoreEvidenceIds"),
        present="selectedTargetLegalizationCoreEvidenceIds" in decision,
        code_prefix="package.target_legalization_evidence.debug_metadata",
    )
    sidecar["packageArtifactRequirementEvidenceIds"] = (
        _target_legalization_string_array_field(
            diagnostics,
            document="debugMetadata",
            path="targetDecision.packageArtifactRequirementEvidenceIds",
            value=decision.get("packageArtifactRequirementEvidenceIds"),
            present="packageArtifactRequirementEvidenceIds" in decision,
            code_prefix="package.target_legalization_evidence.debug_metadata",
        )
    )
    sidecar["requiredToolCount"] = _target_legalization_unsigned_field(
        diagnostics,
        document="debugMetadata",
        path="targetDecision.selectedTargetRequiredToolCount",
        value=decision.get("selectedTargetRequiredToolCount"),
        present="selectedTargetRequiredToolCount" in decision,
        code_prefix="package.target_legalization_evidence.debug_metadata",
    )
    sidecar["missingToolCount"] = _target_legalization_unsigned_field(
        diagnostics,
        document="debugMetadata",
        path="targetDecision.selectedTargetMissingToolCount",
        value=decision.get("selectedTargetMissingToolCount"),
        present="selectedTargetMissingToolCount" in decision,
        code_prefix="package.target_legalization_evidence.debug_metadata",
    )
    sidecar["requiredToolIds"] = _target_legalization_string_array_field(
        diagnostics,
        document="debugMetadata",
        path="targetDecision.selectedTargetRequiredToolIds",
        value=decision.get("selectedTargetRequiredToolIds"),
        present="selectedTargetRequiredToolIds" in decision,
        code_prefix="package.target_legalization_evidence.debug_metadata",
        allow_empty=True,
    )
    sidecar["missingToolIds"] = _target_legalization_string_array_field(
        diagnostics,
        document="debugMetadata",
        path="targetDecision.selectedTargetMissingToolIds",
        value=decision.get("selectedTargetMissingToolIds"),
        present="selectedTargetMissingToolIds" in decision,
        code_prefix="package.target_legalization_evidence.debug_metadata",
        allow_empty=True,
    )
    sidecar["optionalNativeToolMissing"] = _optional_bool_field(
        diagnostics,
        document="debugMetadata",
        path="targetDecision.selectedTargetOptionalNativeToolMissing",
        value=decision.get("selectedTargetOptionalNativeToolMissing"),
        present="selectedTargetOptionalNativeToolMissing" in decision,
        code_prefix="package.target_legalization_evidence.debug_metadata",
    )
    sidecar["optionalNativeToolStatus"] = _target_legalization_optional_string_field(
        diagnostics,
        document="debugMetadata",
        path="targetDecision.selectedTargetOptionalNativeToolStatus",
        value=decision.get("selectedTargetOptionalNativeToolStatus"),
        present="selectedTargetOptionalNativeToolStatus" in decision,
        expected=tuple(sorted(TARGET_LEGALIZATION_OPTIONAL_NATIVE_TOOL_STATUSES)),
        code_prefix="package.target_legalization_evidence.debug_metadata",
    )
    sidecar["toolRequirementEvidenceIds"] = _target_legalization_string_array_field(
        diagnostics,
        document="debugMetadata",
        path="targetDecision.selectedTargetToolRequirementEvidenceIds",
        value=decision.get("selectedTargetToolRequirementEvidenceIds"),
        present="selectedTargetToolRequirementEvidenceIds" in decision,
        code_prefix="package.target_legalization_evidence.debug_metadata",
    )
    if sidecar["target"] is not None:
        summary = _debug_metadata_target_capability_summary(
            document,
            sidecar["target"],
        )
        if summary is not None:
            _fill_sidecar_tool_fields_from_record(
                diagnostics,
                sidecar=sidecar,
                record=summary,
                document="debugMetadata",
                path_prefix="targetCapabilities.summaries[]",
                code_prefix="package.target_legalization_evidence.debug_metadata",
            )
    sidecar["legalizationEvidencePresent"] = any(
        field in decision
        for field in (
            "selectedTargetLegalizationCoreEvidenceIds",
            "packageArtifactRequirementEvidenceIds",
            "selectedTargetPackageBuildSupported",
            "selectedTargetRequiredToolCount",
            "selectedTargetMissingToolCount",
            "selectedTargetRequiredToolIds",
            "selectedTargetMissingToolIds",
            "selectedTargetOptionalNativeToolMissing",
            "selectedTargetOptionalNativeToolStatus",
            "selectedTargetToolRequirementEvidenceIds",
        )
    ) or _sidecar_has_any_tool_requirements(sidecar)
    return sidecar


def _target_explanation_legalization_sidecar(
    diagnostics: list[CompatibilityDiagnostic],
    *,
    artifact: Artifact | None,
    document: dict[str, Any] | None,
    package_target: str | None,
) -> dict[str, Any]:
    sidecar = _empty_target_legalization_sidecar(artifact)
    if document is None:
        return sidecar
    targets = document.get("targets")
    if targets is None:
        return sidecar
    if not isinstance(targets, list):
        diagnostics.append(
            CompatibilityDiagnostic(
                code="package.target_legalization_evidence.target_explanation_targets_invalid",
                message="targetExplanation.targets must be an array",
                document="targetExplanation",
                path="targets",
                expected="array",
                actual=_json_type_name(targets),
            )
        )
        return sidecar

    selected_record: dict[str, Any] | None = None
    for index, record in enumerate(targets):
        if not isinstance(record, dict):
            diagnostics.append(
                CompatibilityDiagnostic(
                    code="package.target_legalization_evidence.target_explanation_target_invalid",
                    message="targetExplanation.targets entries must be objects",
                    document="targetExplanation",
                    path=f"targets[{index}]",
                    expected="object",
                    actual=_json_type_name(record),
                )
            )
            continue
        if record.get("target") == package_target:
            selected_record = record
            break
    if selected_record is None:
        return sidecar

    sidecar["legalizationEvidencePresent"] = True
    sidecar["target"] = _optional_string(selected_record.get("target"))
    sidecar["packageMode"] = _optional_string(selected_record.get("packageMode"))
    sidecar["packageDecisionReason"] = _optional_string(
        selected_record.get("packageDecisionReason")
    )
    sidecar["packageBuildSupported"] = _optional_bool_field(
        diagnostics,
        document="targetExplanation",
        path="targets[].packageBuildSupported",
        value=selected_record.get("packageBuildSupported"),
        present="packageBuildSupported" in selected_record,
        code_prefix="package.target_legalization_evidence.target_explanation",
    )
    sidecar["legalizationCoreEvidenceIds"] = _target_legalization_string_array_field(
        diagnostics,
        document="targetExplanation",
        path="targets[].legalizationCoreEvidenceIds",
        value=selected_record.get("legalizationCoreEvidenceIds"),
        present="legalizationCoreEvidenceIds" in selected_record,
        code_prefix="package.target_legalization_evidence.target_explanation",
    )
    sidecar["packageArtifactRequirementEvidenceIds"] = (
        _target_legalization_string_array_field(
            diagnostics,
            document="targetExplanation",
            path="targets[].packageArtifactRequirementEvidenceIds",
            value=selected_record.get("packageArtifactRequirementEvidenceIds"),
            present="packageArtifactRequirementEvidenceIds" in selected_record,
            code_prefix="package.target_legalization_evidence.target_explanation",
        )
    )
    _fill_sidecar_tool_fields_from_record(
        diagnostics,
        sidecar=sidecar,
        record=selected_record,
        document="targetExplanation",
        path_prefix="targets[]",
        code_prefix="package.target_legalization_evidence.target_explanation",
    )
    return sidecar


def _empty_target_legalization_sidecar(artifact: Artifact | None) -> dict[str, Any]:
    return {
        "artifactPresent": artifact is not None,
        "artifactExists": bool(artifact is not None and artifact.exists),
        "legalizationEvidencePresent": False,
        "target": None,
        "packageMode": None,
        "packageDecisionReason": None,
        "packageBuildSupported": None,
        "requiredToolCount": None,
        "missingToolCount": None,
        "requiredToolIds": None,
        "missingToolIds": None,
        "optionalNativeToolMissing": None,
        "optionalNativeToolStatus": None,
        "toolRequirementEvidenceIds": None,
        "legalizationCoreEvidenceIds": None,
        "packageArtifactRequirementEvidenceIds": None,
    }


def _target_legalization_manifest_tool_requirements_summary(
    requirements: dict[str, Any],
) -> dict[str, Any]:
    return {
        "present": requirements["present"],
        "target": requirements["target"],
        "packageMode": requirements["packageMode"],
        "requiredToolCount": requirements["requiredToolCount"],
        "missingToolCount": requirements["missingToolCount"],
        "requiredToolIds": (
            list(requirements["requiredToolIds"])
            if requirements["requiredToolIds"] is not None
            else None
        ),
        "missingToolIds": (
            list(requirements["missingToolIds"])
            if requirements["missingToolIds"] is not None
            else None
        ),
        "optionalNativeToolMissing": requirements["optionalNativeToolMissing"],
        "optionalNativeToolStatus": requirements["optionalNativeToolStatus"],
        "toolRequirementEvidenceIds": (
            list(requirements["toolRequirementEvidenceIds"])
            if requirements["toolRequirementEvidenceIds"] is not None
            else None
        ),
    }


def _target_legalization_tool_requirements_summary(
    evidence: dict[str, Any],
) -> dict[str, Any]:
    requirements = evidence.get("manifestToolRequirements")
    if not isinstance(requirements, dict):
        return _target_legalization_manifest_tool_requirements_summary(
            _empty_target_legalization_manifest_tool_requirements()
        )

    normalized = _empty_target_legalization_manifest_tool_requirements()
    for key in normalized:
        if key in requirements:
            value = requirements[key]
            normalized[key] = tuple(value) if isinstance(value, list) else value
    return _target_legalization_manifest_tool_requirements_summary(normalized)


def _target_legalization_sidecar_summary(sidecar: dict[str, Any]) -> dict[str, Any]:
    return {
        "artifactPresent": sidecar["artifactPresent"],
        "artifactExists": sidecar["artifactExists"],
        "legalizationEvidencePresent": sidecar["legalizationEvidencePresent"],
        "target": sidecar["target"],
        "packageMode": sidecar["packageMode"],
        "packageDecisionReason": sidecar["packageDecisionReason"],
        "packageBuildSupported": sidecar["packageBuildSupported"],
        "requiredToolCount": sidecar["requiredToolCount"],
        "missingToolCount": sidecar["missingToolCount"],
        "requiredToolIds": (
            list(sidecar["requiredToolIds"])
            if sidecar["requiredToolIds"] is not None
            else None
        ),
        "missingToolIds": (
            list(sidecar["missingToolIds"])
            if sidecar["missingToolIds"] is not None
            else None
        ),
        "optionalNativeToolMissing": sidecar["optionalNativeToolMissing"],
        "optionalNativeToolStatus": sidecar["optionalNativeToolStatus"],
        "toolRequirementEvidenceIds": (
            list(sidecar["toolRequirementEvidenceIds"])
            if sidecar["toolRequirementEvidenceIds"] is not None
            else None
        ),
        "legalizationCoreEvidenceIds": (
            list(sidecar["legalizationCoreEvidenceIds"])
            if sidecar["legalizationCoreEvidenceIds"]
            else None
        ),
        "packageArtifactRequirementEvidenceIds": (
            list(sidecar["packageArtifactRequirementEvidenceIds"])
            if sidecar["packageArtifactRequirementEvidenceIds"]
            else None
        ),
    }


def _target_legalization_package_mode(
    *,
    requirements_declared: bool,
    target_contract: TargetArtifactContract | None,
    debug_sidecar: dict[str, Any],
    target_explanation_sidecar: dict[str, Any],
) -> tuple[str | None, str | None]:
    if requirements_declared and target_contract is not None:
        return target_contract.package_mode, "manifest.packageArtifactRequirements"
    if (
        debug_sidecar["legalizationEvidencePresent"]
        and debug_sidecar["packageMode"] is not None
    ):
        return (
            debug_sidecar["packageMode"],
            "debugMetadata.targetDecision.selectedTargetPackageMode",
        )
    if target_explanation_sidecar["packageMode"] is not None:
        return (
            target_explanation_sidecar["packageMode"],
            "targetExplanation.targets[].packageMode",
        )
    return None, None


def _append_target_legalization_sidecar_consistency_diagnostics(
    diagnostics: list[CompatibilityDiagnostic],
    *,
    label: str,
    sidecar: dict[str, Any],
    package_target: str | None,
    target_contract: TargetArtifactContract | None,
    manifest_requirement_ids: tuple[str, ...] | None,
    manifest_tool_requirements: dict[str, Any],
) -> None:
    document = "debugMetadata" if label == "debug_metadata" else "targetExplanation"
    label_path = "debug_metadata" if label == "debug_metadata" else "target_explanation"
    if not sidecar["legalizationEvidencePresent"]:
        return
    if sidecar["target"] is not None and sidecar["target"] != package_target:
        diagnostics.append(
            CompatibilityDiagnostic(
                code=f"package.target_legalization_evidence.{label_path}_target_mismatch",
                message=(
                    f"{document} target legalization evidence target must match "
                    "manifest.target"
                ),
                document=document,
                expected=package_target,
                actual=sidecar["target"],
            )
        )

    if (
        sidecar["packageMode"] is not None
        and target_contract is not None
        and sidecar["packageMode"] != target_contract.package_mode
    ):
        diagnostics.append(
            CompatibilityDiagnostic(
                code=f"package.target_legalization_evidence.{label_path}_package_mode_mismatch",
                message=(
                    f"{document} target legalization packageMode must match "
                    "package artifact requirements"
                ),
                document=document,
                expected=target_contract.package_mode,
                actual=sidecar["packageMode"],
            )
        )

    if sidecar["packageBuildSupported"] is False:
        diagnostics.append(
            CompatibilityDiagnostic(
                code=f"package.target_legalization_evidence.{label_path}_unsupported",
                message=(
                    f"{document} target legalization projection rejects manifest.target"
                ),
                document=document,
                expected=True,
                actual=False,
            )
        )

    requirement_ids = sidecar["packageArtifactRequirementEvidenceIds"]
    if (
        manifest_requirement_ids is not None
        and requirement_ids is not None
        and requirement_ids != manifest_requirement_ids
    ):
        diagnostics.append(
            CompatibilityDiagnostic(
                code=(
                    "package.target_legalization_evidence."
                    f"{label_path}_requirement_evidence_mismatch"
                ),
                message=(
                    f"{document} target legalization "
                    "packageArtifactRequirementEvidenceIds must match "
                    "manifest.packageArtifactRequirements.evidenceIds"
                ),
                document=document,
                expected=list(manifest_requirement_ids),
                actual=list(requirement_ids),
            )
        )

    if (
        manifest_tool_requirements["present"]
        and sidecar["artifactExists"]
        and not _sidecar_tool_requirements_match_manifest(
            manifest_tool_requirements,
            sidecar,
        )
    ):
        diagnostics.append(
            CompatibilityDiagnostic(
                code=(
                    "package.target_legalization_evidence."
                    f"{label_path}_tool_requirements_mismatch"
                ),
                message=(
                    f"{document} target legalization tool requirements must "
                    "match manifest.targetLegalizationToolRequirements"
                ),
                document=document,
                expected=_target_legalization_manifest_tool_requirements_summary(
                    manifest_tool_requirements
                ),
                actual=_target_legalization_sidecar_tool_requirements_summary(sidecar),
            )
        )


def _target_legalization_sidecar_tool_requirements_summary(
    sidecar: dict[str, Any],
) -> dict[str, Any]:
    return {
        "requiredToolCount": sidecar["requiredToolCount"],
        "missingToolCount": sidecar["missingToolCount"],
        "requiredToolIds": (
            list(sidecar["requiredToolIds"])
            if sidecar["requiredToolIds"] is not None
            else None
        ),
        "missingToolIds": (
            list(sidecar["missingToolIds"])
            if sidecar["missingToolIds"] is not None
            else None
        ),
        "optionalNativeToolMissing": sidecar["optionalNativeToolMissing"],
        "optionalNativeToolStatus": sidecar["optionalNativeToolStatus"],
        "toolRequirementEvidenceIds": (
            list(sidecar["toolRequirementEvidenceIds"])
            if sidecar["toolRequirementEvidenceIds"] is not None
            else None
        ),
    }


def _target_legalization_evidence_incomplete(
    debug_sidecar: dict[str, Any],
    target_explanation_sidecar: dict[str, Any],
) -> bool:
    return _target_legalization_sidecar_incomplete(
        debug_sidecar
    ) or _target_legalization_sidecar_incomplete(target_explanation_sidecar)


def _target_legalization_sidecar_incomplete(sidecar: dict[str, Any]) -> bool:
    return bool(
        sidecar["artifactPresent"]
        and (
            not sidecar["artifactExists"]
            or sidecar["target"] is None
            or sidecar["packageMode"] is None
            or not sidecar["legalizationCoreEvidenceIds"]
        )
    )


def _sidecar_has_any_tool_requirements(sidecar: dict[str, Any]) -> bool:
    return any(
        sidecar[field] is not None
        for field in (
            "requiredToolCount",
            "missingToolCount",
            "requiredToolIds",
            "missingToolIds",
            "optionalNativeToolMissing",
            "optionalNativeToolStatus",
            "toolRequirementEvidenceIds",
        )
    )


def _sidecar_has_tool_requirements(sidecar: dict[str, Any]) -> bool:
    return all(
        sidecar[field] is not None
        for field in (
            "requiredToolCount",
            "missingToolCount",
            "requiredToolIds",
            "missingToolIds",
            "optionalNativeToolMissing",
            "optionalNativeToolStatus",
            "toolRequirementEvidenceIds",
        )
    )


def _sidecar_tool_requirements_match_manifest(
    manifest_tool_requirements: dict[str, Any],
    sidecar: dict[str, Any],
) -> bool | None:
    if not manifest_tool_requirements["present"] or not sidecar["artifactExists"]:
        return None
    if not _sidecar_has_tool_requirements(sidecar):
        return False
    for field in (
        "requiredToolCount",
        "missingToolCount",
        "requiredToolIds",
        "missingToolIds",
        "optionalNativeToolMissing",
        "optionalNativeToolStatus",
        "toolRequirementEvidenceIds",
    ):
        if manifest_tool_requirements[field] != sidecar[field]:
            return False
    return True


def _debug_metadata_target_capability_summary(
    document: dict[str, Any],
    target: str,
) -> dict[str, Any] | None:
    target_capabilities = document.get("targetCapabilities")
    if not isinstance(target_capabilities, dict):
        return None
    summaries = target_capabilities.get("summaries")
    if not isinstance(summaries, list):
        return None
    for summary in summaries:
        if isinstance(summary, dict) and summary.get("target") == target:
            return summary
    return None


def _fill_sidecar_tool_fields_from_record(
    diagnostics: list[CompatibilityDiagnostic],
    *,
    sidecar: dict[str, Any],
    record: dict[str, Any],
    document: str,
    path_prefix: str,
    code_prefix: str,
) -> None:
    fields: tuple[tuple[str, str, str], ...] = (
        ("requiredToolCount", "requiredToolCount", "unsigned"),
        ("missingToolCount", "missingToolCount", "unsigned"),
        ("requiredToolIds", "requiredToolIds", "string_array_allow_empty"),
        ("missingToolIds", "missingToolIds", "string_array_allow_empty"),
        ("optionalNativeToolMissing", "optionalNativeToolMissing", "bool"),
        ("optionalNativeToolStatus", "optionalNativeToolStatus", "status"),
        ("toolRequirementEvidenceIds", "toolRequirementEvidenceIds", "string_array"),
    )
    for sidecar_field, record_field, kind in fields:
        if sidecar[sidecar_field] is not None or record_field not in record:
            continue
        path = f"{path_prefix}.{record_field}"
        if kind == "unsigned":
            sidecar[sidecar_field] = _target_legalization_unsigned_field(
                diagnostics,
                document=document,
                path=path,
                value=record.get(record_field),
                present=True,
                code_prefix=code_prefix,
            )
        elif kind == "bool":
            sidecar[sidecar_field] = _optional_bool_field(
                diagnostics,
                document=document,
                path=path,
                value=record.get(record_field),
                present=True,
                code_prefix=code_prefix,
            )
        elif kind == "status":
            sidecar[sidecar_field] = _target_legalization_optional_string_field(
                diagnostics,
                document=document,
                path=path,
                value=record.get(record_field),
                present=True,
                expected=tuple(
                    sorted(TARGET_LEGALIZATION_OPTIONAL_NATIVE_TOOL_STATUSES)
                ),
                code_prefix=code_prefix,
            )
        else:
            sidecar[sidecar_field] = _target_legalization_string_array_field(
                diagnostics,
                document=document,
                path=path,
                value=record.get(record_field),
                present=True,
                code_prefix=code_prefix,
                allow_empty=(kind == "string_array_allow_empty"),
            )


def _target_legalization_unsigned_field(
    diagnostics: list[CompatibilityDiagnostic],
    *,
    document: str,
    path: str,
    value: Any,
    present: bool,
    code_prefix: str,
) -> int | None:
    if not present:
        return None
    if isinstance(value, int) and not isinstance(value, bool) and value >= 0:
        return value
    diagnostics.append(
        CompatibilityDiagnostic(
            code=f"{code_prefix}_{_target_legalization_code_field(path)}_invalid",
            message=f"{document}.{path} must be a non-negative integer",
            document=document,
            path=path,
            expected="non-negative integer",
            actual=_contract_actual_value(value),
        )
    )
    return None


def _target_legalization_optional_string_field(
    diagnostics: list[CompatibilityDiagnostic],
    *,
    document: str,
    path: str,
    value: Any,
    present: bool,
    expected: tuple[str, ...] | None,
    code_prefix: str,
) -> str | None:
    if not present:
        return None
    if isinstance(value, str) and value and (expected is None or value in expected):
        return value
    diagnostics.append(
        CompatibilityDiagnostic(
            code=f"{code_prefix}_{_target_legalization_code_field(path)}_invalid",
            message=f"{document}.{path} is invalid",
            document=document,
            path=path,
            expected=list(expected) if expected is not None else "non-empty string",
            actual=_contract_actual_value(value),
        )
    )
    return None


def _optional_bool_field(
    diagnostics: list[CompatibilityDiagnostic],
    *,
    document: str,
    path: str,
    value: Any,
    present: bool,
    code_prefix: str,
) -> bool | None:
    if not present:
        return None
    if isinstance(value, bool):
        return value
    diagnostics.append(
        CompatibilityDiagnostic(
            code=f"{code_prefix}_{_target_legalization_code_field(path)}_invalid",
            message=f"{document}.{path} must be a boolean",
            document=document,
            path=path,
            expected="boolean",
            actual=_json_type_name(value),
        )
    )
    return None


def _target_legalization_string_array_field(
    diagnostics: list[CompatibilityDiagnostic],
    *,
    document: str,
    path: str,
    value: Any,
    present: bool,
    code_prefix: str,
    allow_empty: bool = False,
) -> tuple[str, ...] | None:
    if not present:
        return None
    if not isinstance(value, list) or (not allow_empty and not value):
        diagnostics.append(
            CompatibilityDiagnostic(
                code=f"{code_prefix}_{_target_legalization_code_field(path)}_invalid",
                message=(
                    f"{document}.{path} must be a "
                    f"{'' if allow_empty else 'non-empty '}string array"
                ),
                document=document,
                path=path,
                expected=("string array" if allow_empty else "non-empty string array"),
                actual=_json_type_name(value),
            )
        )
        return None

    entries: list[str] = []
    for index, entry in enumerate(value):
        if not isinstance(entry, str) or not entry:
            diagnostics.append(
                CompatibilityDiagnostic(
                    code=(
                        f"{code_prefix}_"
                        f"{_target_legalization_code_field(path)}_entry_invalid"
                    ),
                    message=f"{document}.{path} entries must be non-empty strings",
                    document=document,
                    path=f"{path}[{index}]",
                    expected="non-empty string",
                    actual=_contract_actual_value(entry),
                )
            )
            continue
        if entry in entries:
            diagnostics.append(
                CompatibilityDiagnostic(
                    code=(
                        f"{code_prefix}_"
                        f"{_target_legalization_code_field(path)}_duplicate"
                    ),
                    message=f"{document}.{path} must not contain duplicates",
                    document=document,
                    path=f"{path}[{index}]",
                    expected="unique string",
                    actual=entry,
                )
            )
            continue
        entries.append(entry)
    if len(entries) != len(value):
        return None
    return tuple(entries)


def _target_legalization_code_field(path: str) -> str:
    return _snake_case(path.rsplit(".", 1)[-1].replace("[]", ""))


def _valid_string_tuple(value: Any) -> tuple[str, ...] | None:
    if not isinstance(value, list) or not value:
        return None
    entries: list[str] = []
    for entry in value:
        if not isinstance(entry, str) or not entry or entry in entries:
            return None
        entries.append(entry)
    return tuple(entries)


def _target_matches(
    recorded_target: str | None, package_target: str | None
) -> bool | None:
    if recorded_target is None:
        return None
    return recorded_target == package_target


def _package_mode_matches(
    package_mode: str | None,
    target_contract: TargetArtifactContract | None,
) -> bool | None:
    if package_mode is None or target_contract is None:
        return None
    return package_mode == target_contract.package_mode


def _debug_metadata_record(document: dict[str, Any]) -> DebugMetadataRecord:
    target_decision = document.get("targetDecision")
    if not isinstance(target_decision, dict):
        target_decision = {}
    hir_source_locations = document.get("hirSourceLocations")
    if not isinstance(hir_source_locations, dict):
        hir_source_locations = {}
    source_location_summary = hir_source_locations.get("summary")
    if not isinstance(source_location_summary, dict):
        source_location_summary = {}
    source_location_counts = hir_source_locations
    if not any(
        key in source_location_counts
        for key in ("expressionCount", "typeCount", "statementCount")
    ):
        source_location_counts = source_location_summary
    manual_texture_compare_kernels = document.get("manualTextureCompareKernels")
    return DebugMetadataRecord(
        schema_version=document.get("schemaVersion"),
        requested_target=_optional_string(target_decision.get("requestedTarget")),
        selected_target=_optional_string(target_decision.get("selectedTarget")),
        selected_package_mode=_optional_string(
            target_decision.get("selectedTargetPackageMode")
        ),
        expression_source_location_count=_optional_int(
            source_location_counts.get("expressionCount")
        ),
        type_source_location_count=_optional_int(
            source_location_counts.get("typeCount")
        ),
        statement_source_location_count=_optional_int(
            source_location_counts.get("statementCount")
        ),
        manual_texture_compare_kernel_count=(
            len(manual_texture_compare_kernels)
            if isinstance(manual_texture_compare_kernels, list)
            else None
        ),
    )


def _debug_metadata_availability_summary(
    artifact: Artifact | None,
    record: DebugMetadataRecord | None,
) -> dict[str, Any]:
    return {
        "declared": artifact is not None,
        "exists": artifact.exists if artifact is not None else False,
        "path": artifact.package_path if artifact is not None else None,
        "compatible": record.compatible if record is not None else None,
        "record": record.to_summary() if record is not None else None,
    }


_GRAPHICS_DESCRIPTOR_BINDING_SUMMARY_FIELDS = (
    "target",
    "stage",
    "entryPoint",
    "name",
    "kind",
    "sourceType",
    "addressSpace",
    "abi",
    "evidenceId",
    "bindingClass",
    "descriptorType",
    "argumentIndex",
    "set",
    "binding",
    "metalType",
    "hlslType",
    "storageClass",
    "spirvType",
    "arrayDimensions",
    "arrayElementCount",
    "storageImageFormat",
    "storageImageAccess",
)


def _graphics_descriptor_binding_summary(
    *,
    target: str | None,
    reflection: dict[str, Any],
    graphics_abi: GraphicsAbiRecord | None,
) -> dict[str, Any]:
    reflection_bindings = _graphics_descriptor_bindings_from_reflection(
        reflection,
        target=target,
    )
    graphics_abi_bindings = (
        graphics_abi.descriptor_bindings if graphics_abi is not None else ()
    )
    bindings = graphics_abi_bindings if graphics_abi_bindings else reflection_bindings
    source = (
        "graphicsAbi.abiRecords"
        if graphics_abi_bindings
        else "reflection.targetResourceBindings"
    )
    return {
        "schemaVersion": 1,
        "target": target,
        "source": source,
        "graphicsAbiDeclared": graphics_abi is not None,
        "bindingCount": len(bindings),
        "reflectionBindingCount": len(reflection_bindings),
        "graphicsAbiBindingCount": len(graphics_abi_bindings),
        "bindings": list(bindings),
    }


def _graphics_descriptor_bindings_from_graphics_abi(
    document: dict[str, Any],
    *,
    target: str | None,
) -> tuple[dict[str, Any], ...]:
    records = _json_object_records(document.get("abiRecords"))
    if not records:
        records = _json_object_records(document.get("targetResourceBindings"))
    return _graphics_descriptor_binding_records(records, target=target)


def _graphics_descriptor_bindings_from_reflection(
    reflection: dict[str, Any],
    *,
    target: str | None,
) -> tuple[dict[str, Any], ...]:
    return _graphics_descriptor_binding_records(
        _json_object_records(reflection.get("targetResourceBindings")),
        target=target,
    )


def _graphics_descriptor_binding_records(
    records: tuple[dict[str, Any], ...],
    *,
    target: str | None,
) -> tuple[dict[str, Any], ...]:
    normalized: list[dict[str, Any]] = []
    for record in records:
        record_target = record.get("target")
        if (
            target is not None
            and isinstance(record_target, str)
            and record_target != target
        ):
            continue
        normalized.append(_graphics_descriptor_binding_record(record, target=target))
    return tuple(
        sorted(
            normalized,
            key=lambda record: (
                str(record.get("stage") or ""),
                str(record.get("entryPoint") or ""),
                str(record.get("name") or ""),
                str(record.get("kind") or ""),
                str(record.get("target") or ""),
            ),
        )
    )


def _graphics_descriptor_binding_record(
    record: dict[str, Any],
    *,
    target: str | None,
) -> dict[str, Any]:
    summary = _summarize_reflection_like_record(
        record,
        _GRAPHICS_DESCRIPTOR_BINDING_SUMMARY_FIELDS,
    )
    if "target" not in summary and target is not None:
        summary["target"] = target
    abi = summary.get("abi")
    if isinstance(abi, dict):
        for field_name in (
            "space",
            "register",
            "buffer",
            "texture",
            "sampler",
            "program",
            "set",
            "binding",
        ):
            if field_name in abi and field_name not in summary:
                summary[field_name] = abi[field_name]
    elif isinstance(abi, str):
        summary["abiKind"] = abi
    return summary


def _summarize_reflection_like_record(
    record: dict[str, Any],
    fields: tuple[str, ...],
) -> dict[str, Any]:
    return {
        field_name: record[field_name] for field_name in fields if field_name in record
    }


def _graphics_abi_record(
    document: dict[str, Any] | None,
    *,
    target: str | None,
) -> GraphicsAbiRecord | None:
    if document is None:
        return None
    abi_records = _json_object_records(document.get("abiRecords"))
    descriptor_bindings = _graphics_descriptor_bindings_from_graphics_abi(
        document,
        target=target,
    )
    stage_record_counts = _graphics_abi_stage_record_counts(document)
    resource_record_counts = _graphics_abi_resource_record_counts(document)
    return GraphicsAbiRecord(
        module=_optional_string(document.get("module")),
        target=_optional_string(document.get("target")),
        schema_version=document.get("schemaVersion"),
        abi_version=document.get("abiVersion", document.get("version")),
        entry_points=tuple(
            _summarize_reflection_like_record(
                record,
                ("stage", "sourceName", "backendName"),
            )
            for record in _json_object_records(document.get("entryPoints"))
        ),
        resources=tuple(
            _summarize_reflection_like_record(
                record,
                (
                    "stage",
                    "name",
                    "kind",
                    "type",
                    "set",
                    "binding",
                    "arrayDimensions",
                    "arrayElementCount",
                    "storageImageFormat",
                    "storageImageAccess",
                ),
            )
            for record in _json_object_records(document.get("resources"))
        ),
        abi_records=tuple(
            _summarize_reflection_like_record(
                record,
                _GRAPHICS_DESCRIPTOR_BINDING_SUMMARY_FIELDS,
            )
            for record in abi_records
        ),
        descriptor_bindings=descriptor_bindings,
        stage_count=len(stage_record_counts),
        stage_record_counts=stage_record_counts,
        resource_count=sum(resource_record_counts.values()),
        resource_record_counts=resource_record_counts,
    )


def _graphics_abi_stage_record_counts(document: dict[str, Any]) -> dict[str, int]:
    counts: dict[str, int] = {}
    stages = document.get("stages")
    if isinstance(stages, dict):
        for stage in stages:
            if isinstance(stage, str) and stage:
                counts.setdefault(stage, 0)
    elif isinstance(stages, list):
        for stage_record in stages:
            if isinstance(stage_record, str) and stage_record:
                counts.setdefault(stage_record, 0)
            elif isinstance(stage_record, dict):
                stage = _optional_string(
                    stage_record.get("stage", stage_record.get("name"))
                )
                if stage:
                    counts.setdefault(stage, 0)

    for collection_name in (
        "entryPoints",
        "resources",
        "abiRecords",
        "resourceBindings",
        "targetResourceBindings",
    ):
        for record in _json_object_records(document.get(collection_name)):
            stage = _optional_string(record.get("stage"))
            if stage:
                counts[stage] = counts.get(stage, 0) + 1
    return counts


def _graphics_abi_resource_record_counts(document: dict[str, Any]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for collection_name in (
        "resources",
        "abiRecords",
        "resourceBindings",
        "targetResourceBindings",
    ):
        count = len(_json_object_records(document.get(collection_name)))
        if count:
            counts[collection_name] = count
    return counts


def _json_object_records(value: Any) -> tuple[dict[str, Any], ...]:
    if not isinstance(value, list):
        return ()
    return tuple(record for record in value if isinstance(record, dict))


def _graphics_abi_availability_summary(
    artifact: Artifact | None,
    record: GraphicsAbiRecord | None,
) -> dict[str, Any]:
    return {
        "declared": artifact is not None,
        "exists": artifact.exists if artifact is not None else False,
        "path": artifact.package_path if artifact is not None else None,
        "record": record.to_summary() if record is not None else None,
    }


def _optional_string(value: Any) -> str | None:
    return value if isinstance(value, str) else None


def _optional_non_empty_string(value: Any) -> str | None:
    return value if isinstance(value, str) and value else None


def _optional_int(value: Any) -> int | None:
    return value if isinstance(value, int) else None


def _contract_actual_value(value: Any) -> Any:
    if value is None:
        return "missing"
    if isinstance(value, str):
        return value
    return _json_type_name(value)


def _native_binary_status_is_ready(value: Any) -> bool:
    return isinstance(value, str) and value in NATIVE_BINARY_READY_STATUSES


def _is_crossgl_source_input_path(package_path: str) -> bool:
    return PurePosixPath(package_path).suffix.lower() == ".cgl"


def _json_type_name(value: Any) -> str:
    if value is None:
        return "missing"
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, dict):
        return "object"
    if isinstance(value, list):
        return "array"
    if isinstance(value, str):
        return "string"
    if isinstance(value, (int, float)):
        return "number"
    return type(value).__name__


def _snake_case(value: str) -> str:
    output: list[str] = []
    for index, char in enumerate(value):
        if char.isupper() and index > 0:
            output.append("_")
        output.append(char.lower())
    return "".join(output)


_TARGET_ARTIFACT_CONTRACT_IMPORT_DIAGNOSTICS: list[CompatibilityDiagnostic] = []
TARGET_ARTIFACT_CONTRACTS = _target_artifact_contracts(
    diagnostics=_TARGET_ARTIFACT_CONTRACT_IMPORT_DIAGNOSTICS
)


def _require_schema_version(document: dict[str, Any], label: str) -> None:
    if document.get("schemaVersion") != 1:
        raise PackageReadError(f"{label}.schemaVersion must be 1")


def _require_string(document: dict[str, Any], key: str, label: str) -> str:
    value = document.get(key)
    if not isinstance(value, str) or not value:
        raise PackageReadError(f"{label}.{key} must be a non-empty string")
    return value


def _read_compiler_metadata(
    manifest: dict[str, Any],
    diagnostics: list[CompatibilityDiagnostic],
) -> tuple[str | None, str | None]:
    compiler = manifest.get("compiler")
    if not isinstance(compiler, dict):
        diagnostics.append(
            CompatibilityDiagnostic(
                code="package.compiler.missing",
                message="manifest.compiler must be present for runtime compatibility",
                document="manifest",
                expected="object",
                actual=type(compiler).__name__,
            )
        )
        return None, None

    name = compiler.get("name")
    version = compiler.get("version")
    compiler_name = name if isinstance(name, str) else None
    compiler_version = version if isinstance(version, str) else None

    if compiler_name != SUPPORTED_COMPILER_NAME:
        diagnostics.append(
            CompatibilityDiagnostic(
                code="package.compiler.name_incompatible",
                message=("manifest.compiler.name is not a supported CrossGL compiler"),
                document="manifest",
                expected=SUPPORTED_COMPILER_NAME,
                actual=name,
            )
        )
    if "version" not in compiler or version == "":
        diagnostics.append(
            CompatibilityDiagnostic(
                code="package.compiler.version_missing",
                message="manifest.compiler.version must be a non-empty string",
                document="manifest",
                expected="non-empty string",
                actual=version,
            )
        )
    elif not isinstance(version, str):
        diagnostics.append(
            CompatibilityDiagnostic(
                code="package.compiler.version_invalid",
                message="manifest.compiler.version must be a string",
                document="manifest",
                expected="non-empty string",
                actual=_json_type_name(version),
            )
        )
    return compiler_name, compiler_version


def _schema_version_is_malformed(version: Any) -> bool:
    return isinstance(version, bool) or not isinstance(version, int)


def _append_schema_diagnostics(
    diagnostics: list[CompatibilityDiagnostic],
    *,
    manifest: dict[str, Any],
    reflection: dict[str, Any],
    diagnostics_document: dict[str, Any],
    unreadable_documents: frozenset[str] = frozenset(),
) -> None:
    for label, document in (
        ("manifest", manifest),
        ("reflection", reflection),
        ("diagnostics", diagnostics_document),
    ):
        if label in unreadable_documents:
            continue
        version = document.get("schemaVersion")
        if version is None:
            diagnostics.append(
                CompatibilityDiagnostic(
                    code="package.schema.version_missing",
                    message=f"{label}.schemaVersion is required",
                    document=label,
                    path="schemaVersion",
                    expected=SUPPORTED_PACKAGE_SCHEMA_VERSION,
                    actual="missing",
                )
            )
        elif _schema_version_is_malformed(version):
            diagnostics.append(
                CompatibilityDiagnostic(
                    code="package.schema.version_invalid",
                    message=f"{label}.schemaVersion must be an integer",
                    document=label,
                    path="schemaVersion",
                    expected=SUPPORTED_PACKAGE_SCHEMA_VERSION,
                    actual=_contract_actual_value(version),
                )
            )
        elif version != SUPPORTED_PACKAGE_SCHEMA_VERSION:
            diagnostics.append(
                CompatibilityDiagnostic(
                    code="package.schema.incompatible",
                    message=(f"{label}.schemaVersion is not supported by this runtime"),
                    document=label,
                    path="schemaVersion",
                    expected=SUPPORTED_PACKAGE_SCHEMA_VERSION,
                    actual=version,
                )
            )


def _append_diagnostics_document_diagnostics(
    diagnostics: list[CompatibilityDiagnostic],
    *,
    diagnostics_document: dict[str, Any],
    unreadable_documents: frozenset[str] = frozenset(),
) -> None:
    if "diagnostics" in unreadable_documents:
        return
    records = diagnostics_document.get("diagnostics")
    if records is None:
        return
    if not isinstance(records, list):
        diagnostics.append(
            CompatibilityDiagnostic(
                code="package.diagnostics.records_invalid",
                message="diagnostics.diagnostics must be an array",
                document="diagnostics",
                path="diagnostics",
                expected="array",
                actual=_json_type_name(records),
            )
        )
        return

    for index, record in enumerate(records):
        path = f"diagnostics[{index}]"
        if not isinstance(record, dict):
            diagnostics.append(
                CompatibilityDiagnostic(
                    code="package.diagnostics.record_invalid",
                    message="diagnostics.diagnostics entries must be objects",
                    document="diagnostics",
                    path=path,
                    expected="object",
                    actual=_json_type_name(record),
                )
            )
            continue
        severity = record.get("severity")
        if severity is not None and (not isinstance(severity, str) or not severity):
            diagnostics.append(
                CompatibilityDiagnostic(
                    code="package.diagnostics.severity_invalid",
                    message=(
                        "diagnostics.diagnostics severity fields must be "
                        "non-empty strings"
                    ),
                    document="diagnostics",
                    path=f"{path}.severity",
                    expected="non-empty string",
                    actual=_contract_actual_value(severity),
                )
            )


def _target_contract_diagnostics(
    *,
    target: str,
    artifacts: tuple[Artifact, ...],
    native_binary_status: Any,
    contract: TargetArtifactContract,
) -> tuple[CompatibilityDiagnostic, ...]:
    diagnostics: list[CompatibilityDiagnostic] = []
    native_status = native_binary_status

    if contract.native_binary_status_required:
        if native_status is None:
            diagnostics.append(
                CompatibilityDiagnostic(
                    code="package.native_binary_status.missing",
                    message=(
                        f"{target} packages must declare "
                        "manifest.artifacts.nativeBinaryStatus"
                    ),
                    document="manifest",
                    artifact="nativeBinaryStatus",
                    expected=list(contract.allowed_native_binary_statuses),
                    actual=None,
                )
            )
        elif (
            isinstance(native_status, str)
            and native_status not in contract.allowed_native_binary_statuses
        ):
            diagnostics.append(
                CompatibilityDiagnostic(
                    code="package.native_binary_status.unsupported",
                    message=(f"{target} nativeBinaryStatus is not supported"),
                    document="manifest",
                    artifact="nativeBinaryStatus",
                    expected=list(contract.allowed_native_binary_statuses),
                    actual=native_status,
                )
            )
    elif isinstance(native_status, str):
        diagnostics.append(
            CompatibilityDiagnostic(
                code="package.native_binary_status.forbidden",
                message=(
                    f"{target} packages must not declare "
                    "manifest.artifacts.nativeBinaryStatus"
                ),
                document="manifest",
                artifact="nativeBinaryStatus",
                expected=None,
                actual=native_status,
            )
        )

    native_profile = _artifact_by_name(artifacts, "nativeProfile")
    if native_profile is not None and target != "vulkan":
        diagnostics.append(
            CompatibilityDiagnostic(
                code="package.artifact.target_incompatible",
                message=(
                    "manifest.artifacts.nativeProfile is only valid for vulkan packages"
                ),
                document="manifest",
                artifact="nativeProfile",
                path=native_profile.package_path,
                expected="vulkan",
                actual=target,
            )
        )

    for artifact_name in contract.required_artifacts:
        artifact = _artifact_by_name(artifacts, artifact_name)
        if artifact is None:
            diagnostics.append(
                CompatibilityDiagnostic(
                    code="package.artifact.required_missing",
                    message=(
                        f"manifest.artifacts.{artifact_name} is required for "
                        f"target {target}"
                    ),
                    document="manifest",
                    artifact=artifact_name,
                    expected="package-relative path",
                    actual=None,
                )
            )
            continue

        backend_target_diagnostic = _required_artifact_backend_target_diagnostic(
            target=target,
            artifact_name=artifact_name,
            artifact=artifact,
        )
        if backend_target_diagnostic is not None:
            diagnostics.append(backend_target_diagnostic)

        if artifact.exists:
            continue
        if (
            artifact_name == "nativeBinary"
            and native_status == "planned"
            and contract.planned_native_binary_may_be_absent
        ):
            continue
        diagnostics.append(
            CompatibilityDiagnostic(
                code="package.artifact.required_file_missing",
                message=(
                    f"required artifact {artifact_name} is declared but missing "
                    f"on disk: {artifact.package_path}"
                ),
                document="manifest",
                artifact=artifact_name,
                path=artifact.package_path,
                expected="regular file",
                actual="missing",
            )
        )

    return tuple(diagnostics)


def _required_artifact_backend_target_diagnostic(
    *,
    target: str,
    artifact_name: str,
    artifact: Artifact,
) -> CompatibilityDiagnostic | None:
    backend_target = _backend_artifact_target(artifact.package_path)
    if backend_target is None or backend_target == target:
        return None
    return CompatibilityDiagnostic(
        code="package.artifact.backend_target_mismatch",
        message=(
            f"manifest.artifacts.{artifact_name} is declared under "
            f"backend/{backend_target}/ but target {target} requires "
            f"backend/{target}/ artifacts"
        ),
        document="manifest",
        artifact=artifact_name,
        path=artifact.package_path,
        expected=f"backend/{target}/",
        actual=f"backend/{backend_target}/",
    )


def _backend_artifact_target(package_path: str) -> str | None:
    parts = PurePosixPath(package_path).parts
    if len(parts) < 2 or parts[0] != "backend":
        return None
    backend_target = parts[1]
    return backend_target if backend_target else None


def _native_binary_status_diagnostics(
    native_binary_status: Any,
    *,
    contract: TargetArtifactContract | None,
) -> tuple[CompatibilityDiagnostic, ...]:
    if native_binary_status is None or isinstance(native_binary_status, str):
        return ()
    expected = (
        list(contract.allowed_native_binary_statuses) if contract is not None else None
    )
    return (
        CompatibilityDiagnostic(
            code="package.native_binary_status.invalid",
            message="manifest.artifacts.nativeBinaryStatus must be a string",
            document="manifest",
            artifact="nativeBinaryStatus",
            expected=expected,
            actual=_json_type_name(native_binary_status),
        ),
    )


def _resolve_package_relative_path(root: Path, value: str, label: str) -> Path:
    if not value:
        raise PackageReadError(f"{label} must be a non-empty package-relative path")
    if "\\" in value:
        raise PackageReadError(f"{label} must use '/' separators")

    artifact_path = Path(value)
    if artifact_path.is_absolute():
        raise PackageReadError(f"{label} must be package-relative")
    _validate_package_relative_path_segments(
        value,
        label,
        escape_container="directory",
    )

    root_resolved = root.resolve()
    resolved = (root / artifact_path).resolve()
    if resolved != root_resolved and root_resolved not in resolved.parents:
        raise PackageReadError(f"{label} escapes the package directory")
    return resolved


def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Read CrossGL .cglb directory or zip package metadata."
    )
    parser.add_argument("package", type=Path, help="Path to a .cglb directory or zip")
    parser.add_argument(
        "--compatibility-report",
        action="store_true",
        help="Print the loader-facing compatibility report as JSON",
    )
    parser.add_argument(
        "--loader-target",
        choices=sorted(_target_artifact_contracts()),
        help="Report whether the package matches a specific runtime loader target",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print a machine-readable package summary",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(sys.argv[1:] if argv is None else argv)
    if args.compatibility_report:
        try:
            report = read_compatibility_report(
                args.package, loader_target=args.loader_target
            )
        except PackageReadError as error:
            print(f"crossgl-runtime-package-reader: {error}", file=sys.stderr)
            return 1
        print(json.dumps(report.to_summary(), indent=2, sort_keys=True))
        return 0 if report.compatible else 2

    try:
        package = read_package(args.package)
    except PackageReadError as error:
        print(f"crossgl-runtime-package-reader: {error}", file=sys.stderr)
        return 1

    if args.json:
        print(json.dumps(package.to_summary(), indent=2, sort_keys=True))
    else:
        artifact_names = ", ".join(artifact.name for artifact in package.artifacts)
        print(f"{package.module} [{package.target}]: {artifact_names}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
