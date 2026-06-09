#!/usr/bin/env python3
"""Source-free Metal package loader planning prototype."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any

from .backend_loader import NATIVE_ARTIFACT_DESCRIPTOR
from .backend_loader import NativeArtifactDescriptorPlan
from .backend_loader import SourceFreeNativeBackendLoaderPlan
from .backend_loader import plan_source_free_native_backend_loader
from .loader import LoaderArtifactPlan, RuntimeLoaderPlan
from .package_reader import (
    CompatibilityDiagnostic,
    NATIVE_ARTIFACT_DESCRIPTOR_CONTRACT_VERSION,
    SUPPORTED_NATIVE_ARTIFACT_DESCRIPTOR_SCHEMA_VERSION,
)


METAL_LOADER_TARGET = "metal"
METAL_NATIVE_ARTIFACT = "nativeBinary"
METAL_NATIVE_BINARY_KIND = "metal.metallib"
METAL_NATIVE_BINARY_SUFFIX = ".metallib"


@dataclass(frozen=True)
class MetalNativeLoaderPlan(SourceFreeNativeBackendLoaderPlan):
    """Metal-specific metadata-only native-loader admission plan."""

    @property
    def metal_native_admission_detail(self) -> dict[str, Any]:
        return _metal_native_admission_detail(self)

    @property
    def metal_native_api_boundary(self) -> dict[str, Any]:
        return _metal_native_api_boundary(self)

    def to_summary(self) -> dict[str, Any]:
        summary = super().to_summary()
        summary["metalNativeAdmission"] = self.metal_native_admission_detail
        summary["metalNativeApiBoundary"] = self.metal_native_api_boundary
        return summary


def plan_metal_native_loader(
    package_path: Path | str,
) -> MetalNativeLoaderPlan:
    """Return a metadata-only Metal native-loader validation plan."""
    base_plan = plan_source_free_native_backend_loader(
        package_path,
        METAL_LOADER_TARGET,
        loader_name="metal-native",
    )
    diagnostics = (
        *base_plan.diagnostics,
        *_metal_native_loader_diagnostics(base_plan),
    )
    native_artifact = base_plan.native_artifact
    if _has_blocking_diagnostics(diagnostics):
        native_artifact = None

    return MetalNativeLoaderPlan(
        package_path=base_plan.package_path,
        loader_name=base_plan.loader_name,
        target=base_plan.target,
        runtime_plan=base_plan.runtime_plan,
        native_artifact=native_artifact,
        native_artifact_descriptor=base_plan.native_artifact_descriptor,
        entry_points=base_plan.entry_points,
        resources=base_plan.resources,
        target_resource_bindings=base_plan.target_resource_bindings,
        workgroup_sizes=base_plan.workgroup_sizes,
        diagnostics=diagnostics,
    )


def _metal_loader_boundary_diagnostics(
    runtime_plan: RuntimeLoaderPlan,
    *,
    native_artifact: LoaderArtifactPlan | None,
    native_artifact_descriptor: NativeArtifactDescriptorPlan | None = None,
    entry_points: tuple[dict[str, Any], ...],
    resources: tuple[dict[str, Any], ...],
    target_resource_bindings: tuple[dict[str, Any], ...],
) -> tuple[CompatibilityDiagnostic, ...]:
    """Compatibility shim for audit docs; shared backend loader owns policy."""
    from .backend_loader import _native_backend_loader_boundary_diagnostics

    return _native_backend_loader_boundary_diagnostics(
        runtime_plan,
        target=METAL_LOADER_TARGET,
        native_artifact=native_artifact,
        native_artifact_descriptor=native_artifact_descriptor,
        entry_points=entry_points,
        resources=resources,
        target_resource_bindings=target_resource_bindings,
    )


def _metal_native_loader_diagnostics(
    plan: SourceFreeNativeBackendLoaderPlan,
) -> tuple[CompatibilityDiagnostic, ...]:
    diagnostics: list[CompatibilityDiagnostic] = []
    native_artifact = _available_artifact(plan.runtime_plan, METAL_NATIVE_ARTIFACT)

    if native_artifact is not None and not _path_has_suffix(
        native_artifact.package_path,
        METAL_NATIVE_BINARY_SUFFIX,
    ):
        diagnostics.append(
            CompatibilityDiagnostic(
                code="metal_loader.native_artifact_metallib_path_mismatch",
                message=(
                    "metal native loader requires manifest.artifacts.nativeBinary "
                    "to reference a .metallib artifact"
                ),
                document="manifest",
                artifact=METAL_NATIVE_ARTIFACT,
                path=native_artifact.package_path,
                expected=f"*{METAL_NATIVE_BINARY_SUFFIX}",
                actual=native_artifact.package_path,
            )
        )

    descriptor = plan.native_artifact_descriptor
    if descriptor is None or not descriptor.readable:
        return tuple(diagnostics)

    descriptor_artifact_path = descriptor.fields.get("artifactPath")
    if (
        native_artifact is not None
        and isinstance(descriptor_artifact_path, str)
        and descriptor_artifact_path != native_artifact.package_path
    ):
        diagnostics.append(
            CompatibilityDiagnostic(
                code=("metal_loader.native_artifact_descriptor_artifact_path_mismatch"),
                message=(
                    "metal native loader requires "
                    "nativeArtifactDescriptor.artifactPath to match "
                    "manifest.artifacts.nativeBinary"
                ),
                document="nativeArtifactDescriptor",
                artifact=NATIVE_ARTIFACT_DESCRIPTOR,
                path="artifactPath",
                expected=native_artifact.package_path,
                actual=descriptor_artifact_path,
            )
        )
    if isinstance(descriptor_artifact_path, str) and not _path_has_suffix(
        descriptor_artifact_path,
        METAL_NATIVE_BINARY_SUFFIX,
    ):
        diagnostics.append(
            CompatibilityDiagnostic(
                code=("metal_loader.native_artifact_descriptor_metallib_path_mismatch"),
                message=(
                    "metal native loader requires "
                    "nativeArtifactDescriptor.artifactPath to reference a "
                    ".metallib artifact"
                ),
                document="nativeArtifactDescriptor",
                artifact=NATIVE_ARTIFACT_DESCRIPTOR,
                path="artifactPath",
                expected=f"*{METAL_NATIVE_BINARY_SUFFIX}",
                actual=descriptor_artifact_path,
            )
        )

    return tuple(diagnostics)


def _metal_native_admission_detail(plan: MetalNativeLoaderPlan) -> dict[str, Any]:
    native_artifact = _available_artifact(plan.runtime_plan, METAL_NATIVE_ARTIFACT)
    descriptor = plan.native_artifact_descriptor
    blocking_reason = _first_blocking_diagnostic(plan.diagnostics)
    checks = _metal_native_admission_checks(
        plan,
        native_artifact=native_artifact,
        descriptor=descriptor,
    )
    target_contract = plan.runtime_plan.compatibility_report.target_contract

    return {
        "schemaVersion": 1,
        "metadataOnly": True,
        "decision": "accepted" if plan.ready else "rejected",
        "status": "ready" if plan.ready else "rejected",
        "reason": (
            "metal_loader.native_metallib_admission.accepted"
            if plan.ready
            else blocking_reason.code
            if blocking_reason is not None
            else None
        ),
        "loaderTarget": METAL_LOADER_TARGET,
        "packageTarget": plan.runtime_plan.package_target,
        "sourceParsingRequired": plan.source_parsing_required,
        "compilerInvocationRequired": False,
        "deviceExecutionRequired": plan.device_execution_required,
        "packageArtifactRequirementsSource": (
            plan.runtime_plan.package_artifact_requirements_source
        ),
        "packageArtifactRequirements": plan.runtime_plan.package_artifact_requirements,
        "targetLegalizationEvidence": (
            plan.runtime_plan.compatibility_report.target_legalization_evidence
        ),
        "targetLegalizationToolRequirements": (
            plan.runtime_plan.compatibility_report.target_legalization_tool_requirements
        ),
        "manifest": {
            "target": plan.runtime_plan.package_target,
            "targetMatchesLoader": plan.runtime_plan.package_target
            == METAL_LOADER_TARGET,
            "requiredArtifacts": list(plan.runtime_plan.required_artifacts),
            "requiredArtifactPaths": plan.runtime_plan.required_artifact_paths,
            "targetContract": (
                target_contract.to_summary() if target_contract is not None else None
            ),
        },
        "metallibArtifact": _metal_native_artifact_detail(
            plan,
            native_artifact,
        ),
        "nativeArtifactDescriptor": _metal_descriptor_detail(
            plan,
            native_artifact=native_artifact,
            descriptor=descriptor,
        ),
        "reflection": {
            "entryPointCount": len(plan.entry_points),
            "resourceCount": len(plan.resources),
            "targetResourceBindingCount": len(plan.target_resource_bindings),
            "entryPoints": [
                _summarize_metal_entry_point(record) for record in plan.entry_points
            ],
            "resources": [
                _summarize_metal_resource(record) for record in plan.resources
            ],
            "targetResourceBindings": [
                _summarize_metal_resource_binding(record)
                for record in plan.target_resource_bindings
            ],
        },
        "checks": checks,
        "requiredChecksPassed": all(
            check["passed"] is True for check in checks if check["required"]
        ),
        "blockedByDiagnostics": [
            diagnostic.to_summary()
            for diagnostic in plan.diagnostics
            if diagnostic.severity in {"error", "skip"}
        ],
    }


def _metal_native_api_boundary(plan: MetalNativeLoaderPlan) -> dict[str, Any]:
    """Return the metadata handoff a future Metal API loader would consume."""
    native_artifact = _available_artifact(plan.runtime_plan, METAL_NATIVE_ARTIFACT)
    descriptor = plan.native_artifact_descriptor
    fields = descriptor.fields if descriptor is not None else {}
    blocking_reason = _first_blocking_diagnostic(plan.diagnostics)

    return {
        "schemaVersion": 1,
        "metadataOnly": True,
        "boundary": "metal.native-api.metadata-v0",
        "decision": "accepted" if plan.ready else "rejected",
        "status": "ready" if plan.ready else "rejected",
        "reason": (
            "metal_loader.native_api_boundary.accepted"
            if plan.ready
            else blocking_reason.code
            if blocking_reason is not None
            else None
        ),
        "loaderTarget": METAL_LOADER_TARGET,
        "packageTarget": plan.runtime_plan.package_target,
        "sourceParsingRequired": plan.source_parsing_required,
        "sourceInputs": [],
        "compilerInvocationRequired": False,
        "deviceExecutionRequired": plan.device_execution_required,
        "packageArtifactRequirementsSource": (
            plan.runtime_plan.package_artifact_requirements_source
        ),
        "packageArtifactRequirements": plan.runtime_plan.package_artifact_requirements,
        "targetLegalizationEvidence": (
            plan.runtime_plan.compatibility_report.target_legalization_evidence
        ),
        "targetLegalizationToolRequirements": (
            plan.runtime_plan.compatibility_report.target_legalization_tool_requirements
        ),
        "metalFrameworkCallsPerformed": False,
        "metalDeviceCreationPerformed": False,
        "metalLibraryCreationPerformed": False,
        "metalPipelineCreationPerformed": False,
        "metalCommandExecutionPerformed": False,
        "runtimeInputs": {
            "manifest": {
                "target": plan.runtime_plan.package_target,
                "nativeBinaryArtifact": METAL_NATIVE_ARTIFACT,
                "nativeArtifactDescriptor": NATIVE_ARTIFACT_DESCRIPTOR,
            },
            "metallibArtifact": _metal_api_metallib_input(
                plan,
                native_artifact=native_artifact,
                descriptor=descriptor,
            ),
            "nativeArtifactDescriptor": _metal_api_descriptor_input(
                plan,
                native_artifact=native_artifact,
                descriptor=descriptor,
            ),
            "reflection": _metal_api_reflection_input(plan),
            "versionCompatibility": plan.runtime_plan.version_compatibility_summary,
        },
        "descriptorFreshness": {
            "artifactPathMatchesMetallib": _descriptor_artifact_path_matches(
                descriptor,
                native_artifact,
            ),
            "artifactHashDeclared": "artifactHash" in fields,
            "artifactHashMatchesMetallib": _descriptor_artifact_hash_matches(
                plan,
                descriptor,
                native_artifact,
            ),
            "sizeBytesMatchesMetallib": _descriptor_size_bytes_matches(
                descriptor,
                native_artifact,
            ),
            "failClosedDiagnosticCodes": [
                diagnostic.code
                for diagnostic in plan.diagnostics
                if diagnostic.document == "nativeArtifactDescriptor"
                or diagnostic.artifact == NATIVE_ARTIFACT_DESCRIPTOR
            ],
        },
        "blockedByDiagnostics": [
            diagnostic.to_summary()
            for diagnostic in plan.diagnostics
            if diagnostic.severity in {"error", "skip"}
        ],
    }


def _metal_native_artifact_detail(
    plan: MetalNativeLoaderPlan,
    native_artifact: LoaderArtifactPlan | None,
) -> dict[str, Any]:
    runtime_artifact = plan.runtime_plan.runtime_artifact
    selected_for_runtime = (
        runtime_artifact is not None and runtime_artifact.name == METAL_NATIVE_ARTIFACT
    )

    return {
        "name": METAL_NATIVE_ARTIFACT,
        "declared": native_artifact is not None,
        "exists": native_artifact.exists if native_artifact is not None else False,
        "selectedForRuntime": selected_for_runtime,
        "acceptedForLoad": plan.ready and plan.native_artifact is not None,
        "path": (native_artifact.package_path if native_artifact is not None else None),
        "absolutePath": (
            native_artifact.absolute_path or str(native_artifact.path)
            if native_artifact is not None
            else None
        ),
        "size": native_artifact.size if native_artifact is not None else None,
        "expectedPathSuffix": METAL_NATIVE_BINARY_SUFFIX,
        "pathSuffix": (
            _path_suffix(native_artifact.package_path)
            if native_artifact is not None
            else None
        ),
        "pathSuffixMatchesMetallib": (
            _path_has_suffix(
                native_artifact.package_path,
                METAL_NATIVE_BINARY_SUFFIX,
            )
            if native_artifact is not None
            else None
        ),
        "expectedBinaryKind": METAL_NATIVE_BINARY_KIND,
        "descriptorBinaryKind": (
            plan.native_artifact_descriptor.binary_kind
            if plan.native_artifact_descriptor is not None
            else None
        ),
        "descriptorArtifactHash": _descriptor_artifact_hash(
            plan.native_artifact_descriptor,
        ),
        "descriptorArtifactHashMatchesMetallib": (
            _descriptor_artifact_hash_matches(
                plan,
                plan.native_artifact_descriptor,
                native_artifact,
            )
        ),
    }


def _metal_descriptor_detail(
    plan: MetalNativeLoaderPlan,
    *,
    native_artifact: LoaderArtifactPlan | None,
    descriptor: NativeArtifactDescriptorPlan | None,
) -> dict[str, Any]:
    diagnostics = [
        diagnostic.to_summary()
        for diagnostic in plan.diagnostics
        if diagnostic.document == "nativeArtifactDescriptor"
        or diagnostic.artifact == NATIVE_ARTIFACT_DESCRIPTOR
    ]
    if descriptor is None:
        return {
            "declared": False,
            "readable": False,
            "artifact": None,
            "fields": {},
            "sourcePathDeclared": False,
            "targetMatchesLoader": None,
            "binaryKindMatchesLoader": None,
            "artifactPathMatchesNativeArtifact": None,
            "artifactPathSuffixMatchesMetallib": None,
            "artifactHash": None,
            "artifactHashMatchesArtifact": None,
            "sizeBytesMatchesArtifact": None,
            "diagnostics": diagnostics,
        }

    fields = dict(descriptor.fields)
    descriptor_target = fields.get("target")
    artifact_path = fields.get("artifactPath")
    size_bytes = fields.get("sizeBytes")
    artifact_path_matches = None
    if native_artifact is not None and isinstance(artifact_path, str):
        artifact_path_matches = artifact_path == native_artifact.package_path

    size_matches = None
    if (
        native_artifact is not None
        and native_artifact.size is not None
        and isinstance(size_bytes, int)
        and not isinstance(size_bytes, bool)
    ):
        size_matches = size_bytes == native_artifact.size

    return {
        "declared": True,
        "readable": descriptor.readable,
        "artifact": descriptor.artifact.to_summary(),
        "fields": fields,
        "sourcePathDeclared": descriptor.source_path_declared,
        "target": descriptor_target,
        "targetMatchesLoader": (
            descriptor_target == METAL_LOADER_TARGET if descriptor.readable else None
        ),
        "binaryKind": descriptor.binary_kind,
        "expectedBinaryKinds": list(descriptor.expected_binary_kinds),
        "binaryKindMatchesLoader": descriptor.binary_kind_matches_loader,
        "artifactPath": artifact_path if isinstance(artifact_path, str) else None,
        "artifactPathMatchesNativeArtifact": artifact_path_matches,
        "artifactPathSuffixMatchesMetallib": (
            _path_has_suffix(artifact_path, METAL_NATIVE_BINARY_SUFFIX)
            if isinstance(artifact_path, str)
            else None
        ),
        "validationStatus": fields.get("validationStatus"),
        "nativeBinaryStatus": fields.get("nativeBinaryStatus"),
        "artifactHash": _descriptor_artifact_hash(descriptor),
        "artifactHashMatchesArtifact": _descriptor_artifact_hash_matches(
            plan,
            descriptor,
            native_artifact,
        ),
        "sizeBytes": size_bytes,
        "sizeBytesMatchesArtifact": size_matches,
        "diagnostics": diagnostics,
    }


def _metal_native_admission_checks(
    plan: MetalNativeLoaderPlan,
    *,
    native_artifact: LoaderArtifactPlan | None,
    descriptor: NativeArtifactDescriptorPlan | None,
) -> list[dict[str, Any]]:
    descriptor_declared = descriptor is not None
    descriptor_readable = descriptor is not None and descriptor.readable
    descriptor_fields = descriptor.fields if descriptor is not None else {}
    descriptor_artifact_path = descriptor_fields.get("artifactPath")
    descriptor_artifact_hash = descriptor_fields.get("artifactHash")
    descriptor_size = descriptor_fields.get("sizeBytes")
    descriptor_size_matches = None
    if (
        native_artifact is not None
        and native_artifact.size is not None
        and isinstance(descriptor_size, int)
        and not isinstance(descriptor_size, bool)
    ):
        descriptor_size_matches = descriptor_size == native_artifact.size

    return [
        _admission_check(
            "manifestTargetMatchesLoader",
            plan.runtime_plan.package_target == METAL_LOADER_TARGET,
            document="manifest",
            path="target",
            expected=METAL_LOADER_TARGET,
            actual=plan.runtime_plan.package_target,
        ),
        _admission_check(
            "nativeBinaryDeclared",
            native_artifact is not None,
            document="manifest",
            artifact=METAL_NATIVE_ARTIFACT,
            path=f"artifacts.{METAL_NATIVE_ARTIFACT}",
            expected="declared .metallib artifact",
            actual=(
                native_artifact.package_path if native_artifact is not None else None
            ),
        ),
        _admission_check(
            "nativeBinaryExists",
            native_artifact.exists if native_artifact is not None else False,
            document="manifest",
            artifact=METAL_NATIVE_ARTIFACT,
            path=(
                native_artifact.package_path if native_artifact is not None else None
            ),
            expected="existing .metallib artifact",
            actual=(
                "exists"
                if native_artifact is not None and native_artifact.exists
                else "missing"
            ),
        ),
        _admission_check(
            "nativeBinaryPathSuffixMatchesMetallib",
            (
                _path_has_suffix(
                    native_artifact.package_path,
                    METAL_NATIVE_BINARY_SUFFIX,
                )
                if native_artifact is not None
                else False
            ),
            document="manifest",
            artifact=METAL_NATIVE_ARTIFACT,
            path=(
                native_artifact.package_path if native_artifact is not None else None
            ),
            expected=f"*{METAL_NATIVE_BINARY_SUFFIX}",
            actual=(
                native_artifact.package_path if native_artifact is not None else None
            ),
        ),
        _admission_check(
            "nativeBinarySelectedForRuntime",
            plan.runtime_plan.runtime_artifact is not None
            and plan.runtime_plan.runtime_artifact.name == METAL_NATIVE_ARTIFACT,
            document="manifest",
            artifact=METAL_NATIVE_ARTIFACT,
            path=(
                plan.runtime_plan.runtime_artifact.package_path
                if plan.runtime_plan.runtime_artifact is not None
                else None
            ),
            expected=METAL_NATIVE_ARTIFACT,
            actual=(
                plan.runtime_plan.runtime_artifact.name
                if plan.runtime_plan.runtime_artifact is not None
                else None
            ),
        ),
        _admission_check(
            "nativeArtifactDescriptorDeclared",
            descriptor_declared,
            document="manifest",
            artifact=NATIVE_ARTIFACT_DESCRIPTOR,
            path=f"artifacts.{NATIVE_ARTIFACT_DESCRIPTOR}",
            expected="optional descriptor metadata",
            actual=(
                descriptor.artifact.package_path if descriptor is not None else None
            ),
            required=False,
        ),
        _admission_check(
            "nativeArtifactDescriptorReadable",
            descriptor_readable if descriptor_declared else None,
            document="nativeArtifactDescriptor",
            artifact=NATIVE_ARTIFACT_DESCRIPTOR,
            path=(descriptor.artifact.package_path if descriptor is not None else None),
            expected="readable JSON object",
            actual=(
                "readable"
                if descriptor_readable
                else "missing or unreadable"
                if descriptor_declared
                else None
            ),
            required=descriptor_declared,
        ),
        _admission_check(
            "nativeArtifactDescriptorSchemaVersionCompatible",
            (
                descriptor_fields.get("schemaVersion")
                == SUPPORTED_NATIVE_ARTIFACT_DESCRIPTOR_SCHEMA_VERSION
                if descriptor_readable
                else None
            ),
            document="nativeArtifactDescriptor",
            artifact=NATIVE_ARTIFACT_DESCRIPTOR,
            path="schemaVersion",
            expected=SUPPORTED_NATIVE_ARTIFACT_DESCRIPTOR_SCHEMA_VERSION,
            actual=descriptor_fields.get("schemaVersion"),
            required=descriptor_readable,
        ),
        _admission_check(
            "nativeArtifactDescriptorContractVersionCompatible",
            (
                descriptor_fields.get("contractVersion")
                == NATIVE_ARTIFACT_DESCRIPTOR_CONTRACT_VERSION
                if descriptor_readable
                else None
            ),
            document="nativeArtifactDescriptor",
            artifact=NATIVE_ARTIFACT_DESCRIPTOR,
            path="contractVersion",
            expected=NATIVE_ARTIFACT_DESCRIPTOR_CONTRACT_VERSION,
            actual=descriptor_fields.get("contractVersion"),
            required=descriptor_readable,
        ),
        _admission_check(
            "nativeArtifactDescriptorTargetMatchesLoader",
            (
                descriptor_fields.get("target") == METAL_LOADER_TARGET
                if descriptor_readable
                else None
            ),
            document="nativeArtifactDescriptor",
            artifact=NATIVE_ARTIFACT_DESCRIPTOR,
            path="target",
            expected=METAL_LOADER_TARGET,
            actual=descriptor_fields.get("target"),
            required=descriptor_readable,
        ),
        _admission_check(
            "nativeArtifactDescriptorBinaryKindMatchesLoader",
            (
                descriptor.binary_kind_matches_loader
                if descriptor is not None and descriptor_readable
                else None
            ),
            document="nativeArtifactDescriptor",
            artifact=NATIVE_ARTIFACT_DESCRIPTOR,
            path="binaryKind",
            expected=[METAL_NATIVE_BINARY_KIND],
            actual=(
                descriptor.binary_kind
                if descriptor is not None and descriptor_readable
                else None
            ),
            required=descriptor_readable,
        ),
        _admission_check(
            "nativeArtifactDescriptorArtifactPathMatchesNativeBinary",
            (
                descriptor_artifact_path == native_artifact.package_path
                if descriptor_readable
                and native_artifact is not None
                and isinstance(descriptor_artifact_path, str)
                else None
            ),
            document="nativeArtifactDescriptor",
            artifact=NATIVE_ARTIFACT_DESCRIPTOR,
            path="artifactPath",
            expected=(
                native_artifact.package_path if native_artifact is not None else None
            ),
            actual=descriptor_artifact_path,
            required=descriptor_readable,
        ),
        _admission_check(
            "nativeArtifactDescriptorArtifactPathSuffixMatchesMetallib",
            (
                _path_has_suffix(
                    descriptor_artifact_path,
                    METAL_NATIVE_BINARY_SUFFIX,
                )
                if descriptor_readable and isinstance(descriptor_artifact_path, str)
                else None
            ),
            document="nativeArtifactDescriptor",
            artifact=NATIVE_ARTIFACT_DESCRIPTOR,
            path="artifactPath",
            expected=f"*{METAL_NATIVE_BINARY_SUFFIX}",
            actual=descriptor_artifact_path,
            required=descriptor_readable,
        ),
        _admission_check(
            "nativeArtifactDescriptorSizeBytesMatchesArtifact",
            descriptor_size_matches,
            document="nativeArtifactDescriptor",
            artifact=NATIVE_ARTIFACT_DESCRIPTOR,
            path="sizeBytes",
            expected=native_artifact.size if native_artifact is not None else None,
            actual=descriptor_size,
            required=descriptor_readable
            and native_artifact is not None
            and native_artifact.size is not None,
        ),
        _admission_check(
            "nativeArtifactDescriptorArtifactHashDeclared",
            "artifactHash" in descriptor_fields if descriptor_readable else None,
            document="nativeArtifactDescriptor",
            artifact=NATIVE_ARTIFACT_DESCRIPTOR,
            path="artifactHash",
            expected={"algorithm": "sha256", "value": "lowercase sha256"},
            actual=descriptor_artifact_hash,
            required=descriptor_readable,
        ),
        _admission_check(
            "nativeArtifactDescriptorArtifactHashMatchesMetallib",
            _descriptor_artifact_hash_matches(plan, descriptor, native_artifact),
            document="nativeArtifactDescriptor",
            artifact=NATIVE_ARTIFACT_DESCRIPTOR,
            path="artifactHash.value",
            expected="sha256 of selected .metallib artifact",
            actual=_descriptor_artifact_hash(descriptor),
            required=descriptor_readable
            and native_artifact is not None
            and native_artifact.exists,
        ),
        _admission_check(
            "reflectionEntryPointsPresent",
            bool(plan.entry_points),
            document="reflection",
            path="entryPoints",
            expected="non-empty array",
            actual=len(plan.entry_points),
        ),
        _admission_check(
            "reflectionResourcesPresent",
            bool(plan.resources),
            document="reflection",
            path="resources",
            expected="non-empty array",
            actual=len(plan.resources),
        ),
        _admission_check(
            "reflectionTargetResourceBindingsPresent",
            bool(plan.target_resource_bindings),
            document="reflection",
            path="targetResourceBindings",
            expected="non-empty metal binding array",
            actual=len(plan.target_resource_bindings),
        ),
    ]


def _metal_api_metallib_input(
    plan: MetalNativeLoaderPlan,
    *,
    native_artifact: LoaderArtifactPlan | None,
    descriptor: NativeArtifactDescriptorPlan | None,
) -> dict[str, Any]:
    return {
        "artifactName": METAL_NATIVE_ARTIFACT,
        "path": native_artifact.package_path if native_artifact is not None else None,
        "absolutePath": (
            native_artifact.absolute_path or str(native_artifact.path)
            if native_artifact is not None
            else None
        ),
        "exists": native_artifact.exists if native_artifact is not None else False,
        "sizeBytes": native_artifact.size if native_artifact is not None else None,
        "selectedForRuntime": (
            plan.runtime_plan.runtime_artifact is not None
            and plan.runtime_plan.runtime_artifact.name == METAL_NATIVE_ARTIFACT
        ),
        "acceptedForLoad": plan.ready and plan.native_artifact is not None,
        "expectedBinaryKind": METAL_NATIVE_BINARY_KIND,
        "expectedPathSuffix": METAL_NATIVE_BINARY_SUFFIX,
        "descriptorArtifactPath": (
            descriptor.fields.get("artifactPath")
            if descriptor is not None and descriptor.readable
            else None
        ),
        "descriptorArtifactHash": _descriptor_artifact_hash(descriptor),
        "descriptorArtifactHashMatchesMetallib": _descriptor_artifact_hash_matches(
            plan,
            descriptor,
            native_artifact,
        ),
    }


def _metal_api_descriptor_input(
    plan: MetalNativeLoaderPlan,
    *,
    native_artifact: LoaderArtifactPlan | None,
    descriptor: NativeArtifactDescriptorPlan | None,
) -> dict[str, Any]:
    if descriptor is None:
        return {
            "declared": False,
            "readable": False,
            "artifact": None,
            "schemaVersion": None,
            "schemaVersionCompatible": None,
            "contractVersion": None,
            "contractVersionCompatible": None,
            "target": None,
            "targetMatchesLoader": None,
            "binaryKind": None,
            "binaryKindMatchesLoader": None,
            "artifactPath": None,
            "artifactHash": None,
            "sizeBytes": None,
            "validationStatus": None,
            "sourcePathDeclared": False,
            "sourcePathExposed": False,
            "diagnostics": _metal_descriptor_diagnostics(plan),
        }

    fields = descriptor.fields
    schema_version = fields.get("schemaVersion")
    contract_version = fields.get("contractVersion")
    target = fields.get("target")

    return {
        "declared": True,
        "readable": descriptor.readable,
        "artifact": descriptor.artifact.to_summary(),
        "schemaVersion": schema_version,
        "schemaVersionCompatible": (
            schema_version == SUPPORTED_NATIVE_ARTIFACT_DESCRIPTOR_SCHEMA_VERSION
            if descriptor.readable
            else None
        ),
        "contractVersion": contract_version,
        "contractVersionCompatible": (
            contract_version == NATIVE_ARTIFACT_DESCRIPTOR_CONTRACT_VERSION
            if descriptor.readable
            else None
        ),
        "target": target,
        "targetMatchesLoader": (
            target == METAL_LOADER_TARGET if descriptor.readable else None
        ),
        "binaryKind": descriptor.binary_kind,
        "binaryKindMatchesLoader": descriptor.binary_kind_matches_loader,
        "artifactPath": fields.get("artifactPath"),
        "artifactPathMatchesMetallib": _descriptor_artifact_path_matches(
            descriptor,
            native_artifact,
        ),
        "artifactHash": _descriptor_artifact_hash(descriptor),
        "artifactHashMatchesMetallib": _descriptor_artifact_hash_matches(
            plan,
            descriptor,
            native_artifact,
        ),
        "sizeBytes": fields.get("sizeBytes"),
        "sizeBytesMatchesMetallib": _descriptor_size_bytes_matches(
            descriptor,
            native_artifact,
        ),
        "validationStatus": fields.get("validationStatus"),
        "sourcePathDeclared": descriptor.source_path_declared,
        "sourcePathExposed": False,
        "diagnostics": _metal_descriptor_diagnostics(plan),
    }


def _metal_api_reflection_input(plan: MetalNativeLoaderPlan) -> dict[str, Any]:
    return {
        "entryPointCount": len(plan.entry_points),
        "resourceCount": len(plan.resources),
        "targetResourceBindingCount": len(plan.target_resource_bindings),
        "entryPoints": [
            _summarize_metal_entry_point(record) for record in plan.entry_points
        ],
        "resources": [_summarize_metal_resource(record) for record in plan.resources],
        "targetResourceBindings": [
            _summarize_metal_resource_binding(record)
            for record in plan.target_resource_bindings
        ],
    }


def _metal_descriptor_diagnostics(
    plan: MetalNativeLoaderPlan,
) -> list[dict[str, Any]]:
    return [
        diagnostic.to_summary()
        for diagnostic in plan.diagnostics
        if diagnostic.document == "nativeArtifactDescriptor"
        or diagnostic.artifact == NATIVE_ARTIFACT_DESCRIPTOR
    ]


def _descriptor_artifact_path_matches(
    descriptor: NativeArtifactDescriptorPlan | None,
    native_artifact: LoaderArtifactPlan | None,
) -> bool | None:
    if descriptor is None or not descriptor.readable or native_artifact is None:
        return None
    return descriptor.fields.get("artifactPath") == native_artifact.package_path


def _descriptor_artifact_hash(
    descriptor: NativeArtifactDescriptorPlan | None,
) -> Any:
    if descriptor is None or not descriptor.readable:
        return None
    return descriptor.fields.get("artifactHash")


def _descriptor_artifact_hash_matches(
    plan: MetalNativeLoaderPlan,
    descriptor: NativeArtifactDescriptorPlan | None,
    native_artifact: LoaderArtifactPlan | None,
) -> bool | None:
    if descriptor is None or not descriptor.readable:
        return None
    if native_artifact is None or not native_artifact.exists:
        return None
    if "artifactHash" not in descriptor.fields:
        return False
    if _has_diagnostic_code(
        plan,
        "package.native_artifact_descriptor.artifact_hash_invalid",
    ):
        return False
    if _has_diagnostic_code(
        plan,
        "package.native_artifact_descriptor.artifact_hash_mismatch",
    ):
        return False
    if _has_diagnostic_code(
        plan,
        "package.native_artifact_descriptor.artifact_hash_too_large",
    ):
        return False
    return True


def _descriptor_size_bytes_matches(
    descriptor: NativeArtifactDescriptorPlan | None,
    native_artifact: LoaderArtifactPlan | None,
) -> bool | None:
    if descriptor is None or not descriptor.readable or native_artifact is None:
        return None
    if native_artifact.size is None:
        return None
    return descriptor.fields.get("sizeBytes") == native_artifact.size


def _has_diagnostic_code(plan: MetalNativeLoaderPlan, code: str) -> bool:
    return any(diagnostic.code == code for diagnostic in plan.diagnostics)


def _admission_check(
    name: str,
    passed: bool | None,
    *,
    document: str,
    expected: Any,
    actual: Any,
    path: str | None = None,
    artifact: str | None = None,
    required: bool = True,
) -> dict[str, Any]:
    return {
        "name": name,
        "passed": passed,
        "required": required,
        "document": document,
        "artifact": artifact,
        "path": path,
        "expected": expected,
        "actual": actual,
    }


def _summarize_metal_entry_point(record: dict[str, Any]) -> dict[str, Any]:
    return {
        "stage": record.get("stage"),
        "sourceName": record.get("sourceName"),
        "backendName": record.get("backendName"),
    }


def _summarize_metal_resource(record: dict[str, Any]) -> dict[str, Any]:
    summary = {
        "stage": record.get("stage"),
        "name": record.get("name"),
        "kind": record.get("kind"),
        "type": record.get("type"),
        "set": record.get("set"),
        "binding": record.get("binding"),
    }
    _copy_descriptor_array_metadata(summary, record)
    return summary


def _summarize_metal_resource_binding(record: dict[str, Any]) -> dict[str, Any]:
    abi = record.get("abi")
    abi_summary = dict(abi) if isinstance(abi, dict) else {}
    summary = {
        "target": record.get("target"),
        "stage": record.get("stage"),
        "entryPoint": record.get("entryPoint"),
        "name": record.get("name"),
        "kind": record.get("kind"),
        "sourceType": record.get("sourceType"),
        "addressSpace": record.get("addressSpace"),
        "bindingClass": record.get("bindingClass"),
        "descriptorType": record.get("descriptorType"),
        "abi": abi_summary,
        "bufferIndex": abi_summary.get("buffer"),
    }
    _copy_descriptor_array_metadata(summary, record)
    return summary


def _copy_descriptor_array_metadata(
    summary: dict[str, Any],
    record: dict[str, Any],
) -> None:
    for field_name in (
        "arrayDimensions",
        "arrayElementCount",
        "storageImageFormat",
        "storageImageAccess",
    ):
        if field_name in record:
            summary[field_name] = record.get(field_name)


def _available_artifact(
    runtime_plan: RuntimeLoaderPlan,
    name: str,
) -> LoaderArtifactPlan | None:
    for artifact in runtime_plan.compatibility_report.available_artifacts:
        if artifact.name == name:
            return LoaderArtifactPlan.from_artifact(artifact)
    return None


def _has_blocking_diagnostics(
    diagnostics: tuple[CompatibilityDiagnostic, ...] | list[CompatibilityDiagnostic],
) -> bool:
    return _first_blocking_diagnostic(diagnostics) is not None


def _first_blocking_diagnostic(
    diagnostics: tuple[CompatibilityDiagnostic, ...] | list[CompatibilityDiagnostic],
) -> CompatibilityDiagnostic | None:
    return next(
        (
            diagnostic
            for diagnostic in diagnostics
            if diagnostic.severity in {"error", "skip"}
        ),
        None,
    )


def _path_suffix(package_path: str) -> str:
    return PurePosixPath(package_path).suffix.lower()


def _path_has_suffix(package_path: str, suffix: str) -> bool:
    return _path_suffix(package_path) == suffix
