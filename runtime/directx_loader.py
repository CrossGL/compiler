#!/usr/bin/env python3
"""Source-free DirectX package loader planning prototype."""

from __future__ import annotations

from dataclasses import dataclass, replace
from pathlib import Path, PurePosixPath
from typing import Any

from .backend_loader import NATIVE_ARTIFACT_DESCRIPTOR
from .backend_loader import NativeArtifactDescriptorPlan
from .backend_loader import SourceFreeNativeBackendLoaderPlan
from .backend_loader import _native_artifact_descriptor_plan
from .backend_loader import plan_source_free_native_backend_loader
from .loader import LoaderArtifactPlan, RuntimeLoaderPlan, read_loader_plan
from .package_reader import (
    CompatibilityDiagnostic,
    NATIVE_ARTIFACT_DESCRIPTOR_CONTRACT_VERSION,
    SUPPORTED_NATIVE_ARTIFACT_DESCRIPTOR_SCHEMA_VERSION,
)


DIRECTX_LOADER_TARGET = "directx"
DIRECTX_SOURCE_ARTIFACT = "backendSource"
DIRECTX_NATIVE_ARTIFACT = "nativeBinary"
DIRECTX_DXIL_BINARY_KIND = "directx.dxil"
DIRECTX_DXBC_BINARY_KIND = "directx.dxbc"
DIRECTX_NATIVE_BINARY_KINDS = (DIRECTX_DXIL_BINARY_KIND, DIRECTX_DXBC_BINARY_KIND)
DIRECTX_BACKEND_SOURCE_SUFFIX = ".hlsl"
DIRECTX_DXIL_SUFFIX = ".dxil"
DIRECTX_DXBC_SUFFIX = ".dxbc"
DIRECTX_NATIVE_BINARY_SUFFIXES_BY_KIND = {
    DIRECTX_DXIL_BINARY_KIND: DIRECTX_DXIL_SUFFIX,
    DIRECTX_DXBC_BINARY_KIND: DIRECTX_DXBC_SUFFIX,
}
DIRECTX_NATIVE_BINARY_SUFFIXES = tuple(DIRECTX_NATIVE_BINARY_SUFFIXES_BY_KIND.values())


@dataclass(frozen=True)
class DirectXLoaderPlan(RuntimeLoaderPlan):
    """DirectX-specific metadata-only runtime loader plan."""

    @property
    def directx_source_package_admission_detail(self) -> dict[str, Any]:
        return _directx_source_package_admission_detail(self)

    def to_summary(self) -> dict[str, Any]:
        summary = super().to_summary()
        summary["directxSourcePackageAdmission"] = (
            self.directx_source_package_admission_detail
        )
        return summary


@dataclass(frozen=True)
class DirectXNativeLoaderPlan(SourceFreeNativeBackendLoaderPlan):
    """DirectX-specific metadata-only native-loader admission plan."""

    @property
    def directx_native_api_boundary(self) -> dict[str, Any]:
        return _directx_native_api_boundary(self)

    def to_summary(self) -> dict[str, Any]:
        summary = super().to_summary()
        summary["directxNativeApiBoundary"] = self.directx_native_api_boundary
        return summary


def plan_directx_native_loader(
    package_path: Path | str,
) -> DirectXNativeLoaderPlan:
    """Return a metadata-only DirectX native-loader validation plan."""
    base_plan = plan_source_free_native_backend_loader(
        package_path,
        DIRECTX_LOADER_TARGET,
        loader_name="directx-native",
    )
    diagnostics = (
        *base_plan.diagnostics,
        *_directx_native_loader_diagnostics(base_plan),
    )
    native_artifact = base_plan.native_artifact
    if _has_blocking_diagnostics(diagnostics):
        native_artifact = None

    return DirectXNativeLoaderPlan(
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


def _directx_native_loader_diagnostics(
    plan: SourceFreeNativeBackendLoaderPlan,
) -> tuple[CompatibilityDiagnostic, ...]:
    if plan.runtime_plan.package_target != DIRECTX_LOADER_TARGET:
        return ()
    native_artifact = _available_artifact(plan, DIRECTX_NATIVE_ARTIFACT)
    descriptor = plan.native_artifact_descriptor
    return _directx_native_binary_suffix_diagnostics(
        native_artifact=native_artifact,
        descriptor=descriptor,
    )


def _directx_native_api_boundary(plan: DirectXNativeLoaderPlan) -> dict[str, Any]:
    """Return the metadata handoff a future D3D/DXIL loader would consume."""
    native_artifact = _available_artifact(plan, DIRECTX_NATIVE_ARTIFACT)
    descriptor = plan.native_artifact_descriptor
    fields = descriptor.fields if descriptor is not None else {}
    blocking_reason = _first_blocking_diagnostic(plan.diagnostics)
    native_binary = _directx_api_native_binary_input(
        plan,
        native_artifact=native_artifact,
        descriptor=descriptor,
    )

    return {
        "schemaVersion": 1,
        "metadataOnly": True,
        "boundary": "directx.native-api.metadata-v0",
        "decision": "accepted" if plan.ready else "rejected",
        "status": "ready" if plan.ready else "rejected",
        "reason": (
            "directx_loader.native_api_boundary.accepted"
            if plan.ready
            else blocking_reason.code
            if blocking_reason is not None
            else None
        ),
        "loaderTarget": DIRECTX_LOADER_TARGET,
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
        "d3dRuntimeCallsPerformed": False,
        "d3dDeviceCreationPerformed": False,
        "d3dShaderModuleCreationPerformed": False,
        "d3dPipelineCreationPerformed": False,
        "d3dCommandExecutionPerformed": False,
        "runtimeInputs": {
            "manifest": {
                "target": plan.runtime_plan.package_target,
                "nativeBinaryArtifact": DIRECTX_NATIVE_ARTIFACT,
                "nativeArtifactDescriptor": NATIVE_ARTIFACT_DESCRIPTOR,
                "nativeBinaryStatus": (
                    plan.runtime_plan.compatibility_report.native_binary_status
                ),
            },
            "nativeBinaryArtifact": native_binary,
            "dxilArtifact": _directx_api_format_artifact(
                native_binary,
                expected_binary_kind=DIRECTX_DXIL_BINARY_KIND,
            ),
            "dxbcArtifact": _directx_api_format_artifact(
                native_binary,
                expected_binary_kind=DIRECTX_DXBC_BINARY_KIND,
            ),
            "nativeArtifactDescriptor": _directx_api_descriptor_input(
                plan,
                native_artifact=native_artifact,
                descriptor=descriptor,
            ),
            "reflection": _directx_api_reflection_input(plan),
            "versionCompatibility": plan.runtime_plan.version_compatibility_summary,
        },
        "descriptorFreshness": {
            "artifactPathMatchesNativeBinary": _descriptor_artifact_path_matches(
                descriptor,
                native_artifact,
            ),
            "artifactPathMatchesDxil": _descriptor_artifact_path_has_suffix(
                descriptor,
                DIRECTX_DXIL_SUFFIX,
            ),
            "artifactPathMatchesDxbc": _descriptor_artifact_path_has_suffix(
                descriptor,
                DIRECTX_DXBC_SUFFIX,
            ),
            "artifactPathMatchesDxilOrDxbc": (
                _descriptor_artifact_path_has_any_suffix(
                    descriptor,
                    DIRECTX_NATIVE_BINARY_SUFFIXES,
                )
            ),
            "artifactHashDeclared": "artifactHash" in fields,
            "artifactHashMatchesNativeBinary": _descriptor_artifact_hash_matches(
                plan,
                descriptor,
                native_artifact,
            ),
            "sizeBytesMatchesNativeBinary": _descriptor_size_bytes_matches(
                descriptor,
                native_artifact,
            ),
            "nativeBinaryStatusMatchesManifest": (
                _descriptor_native_binary_status_matches(plan, descriptor)
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


def _directx_api_native_binary_input(
    plan: DirectXNativeLoaderPlan,
    *,
    native_artifact: LoaderArtifactPlan | None,
    descriptor: NativeArtifactDescriptorPlan | None,
) -> dict[str, Any]:
    binary_kind, binary_kind_source = _directx_native_api_binary_kind(
        native_artifact=native_artifact,
        descriptor=descriptor,
    )
    expected_suffix = DIRECTX_NATIVE_BINARY_SUFFIXES_BY_KIND.get(binary_kind)
    path_suffix = (
        _path_suffix(native_artifact.package_path)
        if native_artifact is not None
        else None
    )
    native_admission = plan.native_admission_summary.get("nativeArtifact", {})

    return {
        "artifactName": DIRECTX_NATIVE_ARTIFACT,
        "declared": native_artifact is not None,
        "exists": native_artifact.exists if native_artifact is not None else False,
        "path": native_artifact.package_path if native_artifact is not None else None,
        "absolutePath": (
            native_artifact.absolute_path or str(native_artifact.path)
            if native_artifact is not None
            else None
        ),
        "sizeBytes": native_artifact.size if native_artifact is not None else None,
        "selectedForRuntime": (
            plan.runtime_plan.runtime_artifact is not None
            and plan.runtime_plan.runtime_artifact.name == DIRECTX_NATIVE_ARTIFACT
        ),
        "acceptedForLoad": plan.ready and plan.native_artifact is not None,
        "nativeBinaryStatus": (
            plan.runtime_plan.compatibility_report.native_binary_status
        ),
        "nativeAdmissionStatus": native_admission.get("status"),
        "binaryKind": binary_kind,
        "binaryKindSource": binary_kind_source,
        "expectedBinaryKind": binary_kind,
        "expectedBinaryKinds": list(DIRECTX_NATIVE_BINARY_KINDS),
        "expectedPathSuffix": expected_suffix,
        "expectedPathSuffixes": list(DIRECTX_NATIVE_BINARY_SUFFIXES),
        "pathSuffix": path_suffix,
        "pathSuffixMatchesExpected": (
            path_suffix == expected_suffix
            if path_suffix is not None and expected_suffix is not None
            else None
        ),
        "descriptorBinaryKind": (
            descriptor.binary_kind
            if descriptor is not None and descriptor.readable
            else None
        ),
        "descriptorArtifactPath": (
            descriptor.fields.get("artifactPath")
            if descriptor is not None and descriptor.readable
            else None
        ),
        "descriptorArtifactHash": _descriptor_artifact_hash(descriptor),
        "descriptorArtifactHashMatchesNativeBinary": (
            _descriptor_artifact_hash_matches(
                plan,
                descriptor,
                native_artifact,
            )
        ),
    }


def _directx_api_format_artifact(
    native_binary: dict[str, Any],
    *,
    expected_binary_kind: str,
) -> dict[str, Any]:
    expected_suffix = DIRECTX_NATIVE_BINARY_SUFFIXES_BY_KIND[expected_binary_kind]
    binary_kind = native_binary.get("binaryKind")
    matches_expected = binary_kind == expected_binary_kind
    path = native_binary.get("path")
    path_suffix = native_binary.get("pathSuffix")

    return {
        "artifactName": native_binary.get("artifactName"),
        "declared": bool(native_binary.get("declared")) and matches_expected,
        "exists": bool(native_binary.get("exists")) and matches_expected,
        "path": path if matches_expected else None,
        "absolutePath": (
            native_binary.get("absolutePath") if matches_expected else None
        ),
        "sizeBytes": native_binary.get("sizeBytes") if matches_expected else None,
        "selectedForRuntime": (
            bool(native_binary.get("selectedForRuntime")) and matches_expected
        ),
        "acceptedForLoad": bool(native_binary.get("acceptedForLoad"))
        and matches_expected,
        "nativeBinaryStatus": native_binary.get("nativeBinaryStatus"),
        "binaryKind": expected_binary_kind,
        "actualBinaryKind": binary_kind,
        "actualBinaryKindMatches": matches_expected,
        "expectedPathSuffix": expected_suffix,
        "pathSuffix": path_suffix if matches_expected else None,
        "pathSuffixMatchesExpected": (
            path_suffix == expected_suffix
            if matches_expected and path_suffix is not None
            else None
        ),
    }


def _directx_api_descriptor_input(
    plan: DirectXNativeLoaderPlan,
    *,
    native_artifact: LoaderArtifactPlan | None,
    descriptor: NativeArtifactDescriptorPlan | None,
) -> dict[str, Any]:
    if descriptor is None:
        return {
            "declared": False,
            "readable": False,
            "artifact": None,
            "fields": {},
            "schemaVersion": None,
            "schemaVersionCompatible": None,
            "contractVersion": None,
            "contractVersionCompatible": None,
            "target": None,
            "targetMatchesLoader": None,
            "binaryKind": None,
            "expectedBinaryKinds": list(DIRECTX_NATIVE_BINARY_KINDS),
            "binaryKindMatchesLoader": None,
            "artifactPath": None,
            "artifactPathMatchesNativeBinary": None,
            "artifactPathMatchesDxilOrDxbc": None,
            "artifactHash": None,
            "artifactHashMatchesNativeBinary": None,
            "sizeBytes": None,
            "sizeBytesMatchesNativeBinary": None,
            "nativeBinaryStatus": None,
            "manifestNativeBinaryStatus": (
                plan.runtime_plan.compatibility_report.native_binary_status
            ),
            "nativeBinaryStatusMatchesManifest": None,
            "validationStatus": None,
            "sourcePathDeclared": False,
            "sourcePathExposed": False,
            "diagnostics": _descriptor_diagnostics(plan),
        }

    fields = descriptor.fields
    schema_version = fields.get("schemaVersion")
    contract_version = fields.get("contractVersion")
    target = fields.get("target")

    return {
        "declared": True,
        "readable": descriptor.readable,
        "artifact": descriptor.artifact.to_summary(),
        "fields": dict(fields),
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
            target == DIRECTX_LOADER_TARGET if descriptor.readable else None
        ),
        "binaryKind": descriptor.binary_kind,
        "expectedBinaryKinds": list(descriptor.expected_binary_kinds),
        "binaryKindMatchesLoader": descriptor.binary_kind_matches_loader,
        "artifactPath": fields.get("artifactPath"),
        "artifactPathMatchesNativeBinary": _descriptor_artifact_path_matches(
            descriptor,
            native_artifact,
        ),
        "artifactPathMatchesDxilOrDxbc": _descriptor_artifact_path_has_any_suffix(
            descriptor,
            DIRECTX_NATIVE_BINARY_SUFFIXES,
        ),
        "artifactHash": _descriptor_artifact_hash(descriptor),
        "artifactHashMatchesNativeBinary": _descriptor_artifact_hash_matches(
            plan,
            descriptor,
            native_artifact,
        ),
        "sizeBytes": fields.get("sizeBytes"),
        "sizeBytesMatchesNativeBinary": _descriptor_size_bytes_matches(
            descriptor,
            native_artifact,
        ),
        "nativeBinaryStatus": fields.get("nativeBinaryStatus"),
        "manifestNativeBinaryStatus": (
            plan.runtime_plan.compatibility_report.native_binary_status
        ),
        "nativeBinaryStatusMatchesManifest": (
            _descriptor_native_binary_status_matches(plan, descriptor)
        ),
        "validationStatus": fields.get("validationStatus"),
        "sourcePathDeclared": descriptor.source_path_declared,
        "sourcePathExposed": False,
        "diagnostics": _descriptor_diagnostics(plan),
    }


def _directx_api_reflection_input(plan: DirectXNativeLoaderPlan) -> dict[str, Any]:
    target_resource_bindings = [
        _summarize_directx_resource_binding(record)
        for record in plan.target_resource_bindings
    ]
    return {
        "entryPointCount": len(plan.entry_points),
        "resourceCount": len(plan.resources),
        "targetResourceBindingCount": len(plan.target_resource_bindings),
        "entryPoints": [
            _summarize_directx_entry_point(record) for record in plan.entry_points
        ],
        "resources": [_summarize_directx_resource(record) for record in plan.resources],
        "targetResourceBindings": target_resource_bindings,
        "hlslRegisterSpaceBindings": [
            _summarize_directx_register_space_binding(record)
            for record in target_resource_bindings
        ],
    }


def _summarize_directx_entry_point(record: dict[str, Any]) -> dict[str, Any]:
    return {
        "stage": record.get("stage"),
        "sourceName": record.get("sourceName"),
        "backendName": record.get("backendName"),
    }


def _summarize_directx_resource(record: dict[str, Any]) -> dict[str, Any]:
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


def _summarize_directx_resource_binding(record: dict[str, Any]) -> dict[str, Any]:
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
        "hlslType": record.get("hlslType"),
        "abi": abi_summary,
        "register": abi_summary.get("register"),
        "space": abi_summary.get("space"),
    }
    _copy_descriptor_array_metadata(summary, record)
    return summary


def _summarize_directx_register_space_binding(
    record: dict[str, Any],
) -> dict[str, Any]:
    summary = {
        "stage": record.get("stage"),
        "entryPoint": record.get("entryPoint"),
        "name": record.get("name"),
        "kind": record.get("kind"),
        "register": record.get("register"),
        "space": record.get("space"),
        "bindingClass": record.get("bindingClass"),
        "descriptorType": record.get("descriptorType"),
        "hlslType": record.get("hlslType"),
    }
    _copy_descriptor_array_metadata(summary, record)
    return summary


def _copy_descriptor_array_metadata(
    summary: dict[str, Any],
    record: dict[str, Any],
) -> None:
    for field_name in ("arrayDimensions", "arrayElementCount"):
        if field_name in record:
            summary[field_name] = record.get(field_name)


def _directx_native_api_binary_kind(
    *,
    native_artifact: LoaderArtifactPlan | None,
    descriptor: NativeArtifactDescriptorPlan | None,
) -> tuple[str, str]:
    if (
        descriptor is not None
        and descriptor.readable
        and descriptor.binary_kind in DIRECTX_NATIVE_BINARY_KINDS
    ):
        return descriptor.binary_kind, "nativeArtifactDescriptor.binaryKind"

    if native_artifact is not None:
        path_binary_kind = _directx_native_binary_kind_for_path(
            native_artifact.package_path
        )
        if path_binary_kind is not None:
            return path_binary_kind, "manifest.artifacts.nativeBinary"

    return DIRECTX_DXIL_BINARY_KIND, "default"


def _directx_native_binary_suffix_diagnostics(
    *,
    native_artifact: LoaderArtifactPlan | None,
    descriptor: NativeArtifactDescriptorPlan | None,
) -> tuple[CompatibilityDiagnostic, ...]:
    diagnostics: list[CompatibilityDiagnostic] = []
    expected_suffix = _directx_expected_native_suffix(descriptor)

    if native_artifact is not None:
        if expected_suffix is not None:
            if not _path_has_suffix(native_artifact.package_path, expected_suffix):
                diagnostics.append(
                    CompatibilityDiagnostic(
                        code="directx_loader.native_artifact_path_suffix_mismatch",
                        message=(
                            "DirectX native loader requires "
                            "manifest.artifacts.nativeBinary to reference a "
                            f"{expected_suffix} artifact for "
                            f"{descriptor.binary_kind}"
                        ),
                        document="manifest",
                        artifact=DIRECTX_NATIVE_ARTIFACT,
                        path=native_artifact.package_path,
                        expected=f"*{expected_suffix}",
                        actual=native_artifact.package_path,
                    )
                )
        elif not _path_has_any_suffix(
            native_artifact.package_path,
            DIRECTX_NATIVE_BINARY_SUFFIXES,
        ):
            diagnostics.append(
                CompatibilityDiagnostic(
                    code="directx_loader.native_artifact_path_suffix_mismatch",
                    message=(
                        "DirectX native loader requires "
                        "manifest.artifacts.nativeBinary to reference a .dxil "
                        "or .dxbc artifact"
                    ),
                    document="manifest",
                    artifact=DIRECTX_NATIVE_ARTIFACT,
                    path=native_artifact.package_path,
                    expected=list(DIRECTX_NATIVE_BINARY_SUFFIXES),
                    actual=native_artifact.package_path,
                )
            )

    if descriptor is None or not descriptor.readable:
        return tuple(diagnostics)

    descriptor_artifact_path = descriptor.fields.get("artifactPath")
    if not isinstance(descriptor_artifact_path, str):
        return tuple(diagnostics)
    if expected_suffix is not None:
        if not _path_has_suffix(descriptor_artifact_path, expected_suffix):
            diagnostics.append(
                CompatibilityDiagnostic(
                    code=(
                        "directx_loader."
                        "native_artifact_descriptor_artifact_path_suffix_mismatch"
                    ),
                    message=(
                        "DirectX native loader requires "
                        "nativeArtifactDescriptor.artifactPath to reference a "
                        f"{expected_suffix} artifact for {descriptor.binary_kind}"
                    ),
                    document="nativeArtifactDescriptor",
                    artifact=NATIVE_ARTIFACT_DESCRIPTOR,
                    path="artifactPath",
                    expected=f"*{expected_suffix}",
                    actual=descriptor_artifact_path,
                )
            )
    elif not _path_has_any_suffix(
        descriptor_artifact_path,
        DIRECTX_NATIVE_BINARY_SUFFIXES,
    ):
        diagnostics.append(
            CompatibilityDiagnostic(
                code=(
                    "directx_loader."
                    "native_artifact_descriptor_artifact_path_suffix_mismatch"
                ),
                message=(
                    "DirectX native loader requires "
                    "nativeArtifactDescriptor.artifactPath to reference a "
                    ".dxil or .dxbc artifact"
                ),
                document="nativeArtifactDescriptor",
                artifact=NATIVE_ARTIFACT_DESCRIPTOR,
                path="artifactPath",
                expected=list(DIRECTX_NATIVE_BINARY_SUFFIXES),
                actual=descriptor_artifact_path,
            )
        )

    return tuple(diagnostics)


def plan_directx_loader(
    package_path: Path | str,
    *,
    package_mode: str = "auto",
) -> DirectXLoaderPlan:
    """Return a metadata-only DirectX loader plan for package-mode selection."""
    base_plan = read_loader_plan(
        package_path,
        DIRECTX_LOADER_TARGET,
        package_mode=package_mode,
    )
    diagnostics = _directx_loader_diagnostics(base_plan)
    runtime_artifact_selection = base_plan.runtime_artifact_selection
    selected_artifacts = base_plan.selected_artifacts
    if diagnostics:
        runtime_artifact_selection = replace(
            runtime_artifact_selection,
            diagnostics=(*runtime_artifact_selection.diagnostics, *diagnostics),
            admission=None,
        )
        if _has_blocking_diagnostics(diagnostics):
            selected_artifacts = ()
    return DirectXLoaderPlan(
        root=base_plan.root,
        loader_target=base_plan.loader_target,
        module=base_plan.module,
        package_target=base_plan.package_target,
        compatibility_report=base_plan.compatibility_report,
        runtime_artifact_selection=runtime_artifact_selection,
        selected_artifacts=selected_artifacts,
    )


def plan_directx_source_package_loader(
    package_path: Path | str,
) -> DirectXLoaderPlan:
    """Return a metadata-only DirectX source-package loader validation plan."""
    return plan_directx_loader(
        package_path,
        package_mode="source-package",
    )


def _directx_loader_diagnostics(
    plan: RuntimeLoaderPlan,
) -> tuple[CompatibilityDiagnostic, ...]:
    if plan.package_target != DIRECTX_LOADER_TARGET:
        return ()
    native_artifact = _artifact_plan(plan, DIRECTX_NATIVE_ARTIFACT)
    descriptor = _native_artifact_descriptor_plan(plan, DIRECTX_LOADER_TARGET)
    return (
        *_directx_native_binary_suffix_diagnostics(
            native_artifact=native_artifact,
            descriptor=descriptor,
        ),
        *_directx_source_package_artifact_suffix_diagnostics(plan),
    )


def _directx_source_package_artifact_suffix_diagnostics(
    plan: RuntimeLoaderPlan,
) -> tuple[CompatibilityDiagnostic, ...]:
    if plan.runtime_artifact_selection.selected_package_mode != "source-package":
        return ()
    source_artifact = _artifact_plan(plan, DIRECTX_SOURCE_ARTIFACT)
    if source_artifact is None or _path_has_suffix(
        source_artifact.package_path,
        DIRECTX_BACKEND_SOURCE_SUFFIX,
    ):
        return ()
    return (
        CompatibilityDiagnostic(
            code="directx_loader.source_package_backend_source_suffix_mismatch",
            message=(
                "DirectX source-package loader requires "
                "manifest.artifacts.backendSource to reference a .hlsl artifact"
            ),
            document="manifest",
            artifact=DIRECTX_SOURCE_ARTIFACT,
            path=source_artifact.package_path,
            expected=f"*{DIRECTX_BACKEND_SOURCE_SUFFIX}",
            actual=source_artifact.package_path,
        ),
    )


def _directx_source_package_admission_detail(
    plan: DirectXLoaderPlan,
) -> dict[str, Any]:
    native_artifact = _artifact_plan(plan, DIRECTX_NATIVE_ARTIFACT)
    source_artifact = _artifact_plan(plan, DIRECTX_SOURCE_ARTIFACT)
    descriptor = _native_artifact_descriptor_plan(plan, DIRECTX_LOADER_TARGET)
    descriptor_detail = _directx_descriptor_detail(
        plan,
        native_artifact=native_artifact,
        descriptor=descriptor,
    )
    native_artifact_detail = _directx_native_binary_artifact_detail(
        plan,
        native_artifact=native_artifact,
        descriptor_detail=descriptor_detail,
    )
    blocking_reason = _first_blocking_diagnostic(plan.diagnostics)
    admission = {
        "schemaVersion": 1,
        "metadataOnly": True,
        "decision": _directx_admission_decision(plan, blocking_reason),
        "reason": _directx_admission_reason(plan, blocking_reason),
        "loaderTarget": DIRECTX_LOADER_TARGET,
        "packageTarget": plan.package_target,
        "packageMode": {
            "kind": "source-package",
            "requested": plan.runtime_artifact_selection.requested_package_mode,
            "selected": plan.runtime_artifact_selection.selected_package_mode,
            "selectedForRuntime": (
                plan.runtime_artifact_selection.selected_package_mode
                == "source-package"
            ),
        },
        "requestedPackageMode": (
            plan.runtime_artifact_selection.requested_package_mode
        ),
        "selectedPackageMode": plan.runtime_artifact_selection.selected_package_mode,
        "sourceParsingRequired": plan.source_parsing_required,
        "compilerInvocationRequired": False,
        "deviceExecutionRequired": False,
        "sourceInputs": [],
        "packageArtifactRequirementsSource": (
            plan.package_artifact_requirements_source
        ),
        "packageArtifactRequirements": plan.package_artifact_requirements,
        "manifest": {
            "target": plan.package_target,
            "targetMatchesLoader": plan.package_target == DIRECTX_LOADER_TARGET,
            "nativeBinaryStatus": plan.compatibility_report.native_binary_status,
            "requiredArtifacts": list(plan.required_artifacts),
            "requiredArtifactPaths": plan.required_artifact_paths,
        },
        "sourcePackageRuntime": _source_artifact_detail(plan, source_artifact),
        "declaredSourceArtifact": _source_artifact_detail(plan, source_artifact),
        "validatedSourceArtifact": None,
        "compiledArtifact": (
            native_artifact_detail
            if plan.compatibility_report.native_binary_status == "emitted"
            else None
        ),
        "nativeBinaryArtifact": native_artifact_detail,
        "nativeArtifactDescriptor": descriptor_detail,
        "targetLegalizationEvidence": (
            plan.compatibility_report.target_legalization_evidence
        ),
        "targetLegalizationToolRequirements": (
            plan.compatibility_report.target_legalization_tool_requirements
        ),
        "compatibilityEvidence": _directx_compatibility_evidence(
            plan,
            source_artifact=source_artifact,
            native_artifact_detail=native_artifact_detail,
            descriptor_detail=descriptor_detail,
        ),
        "blockedByDiagnostics": [
            diagnostic.to_summary()
            for diagnostic in plan.diagnostics
            if diagnostic.severity in {"error", "skip"}
        ],
    }
    admission[_directx_native_binary_artifact_key(native_artifact_detail)] = (
        native_artifact_detail
    )
    return admission


def _directx_admission_decision(
    plan: DirectXLoaderPlan,
    blocking_reason: CompatibilityDiagnostic | None,
) -> str:
    if plan.package_target != DIRECTX_LOADER_TARGET:
        return "skipped"
    return "rejected" if blocking_reason is not None else "accepted"


def _directx_admission_reason(
    plan: DirectXLoaderPlan,
    blocking_reason: CompatibilityDiagnostic | None,
) -> str:
    if plan.package_target != DIRECTX_LOADER_TARGET:
        return "directx_loader.source_package_admission.target_mismatch"
    if blocking_reason is not None:
        return blocking_reason.code
    return "directx_loader.source_package_admission.accepted"


def _source_artifact_detail(
    plan: DirectXLoaderPlan,
    source_artifact: LoaderArtifactPlan | None,
) -> dict[str, Any]:
    selected = _runtime_artifact_is(plan, DIRECTX_SOURCE_ARTIFACT)
    role = _artifact_role_record(plan, DIRECTX_SOURCE_ARTIFACT)
    return {
        "name": DIRECTX_SOURCE_ARTIFACT,
        "declared": source_artifact is not None,
        "exists": source_artifact.exists if source_artifact is not None else False,
        "path": source_artifact.package_path if source_artifact is not None else None,
        "size": source_artifact.size if source_artifact is not None else None,
        "declaredBy": (
            f"manifest.artifacts.{DIRECTX_SOURCE_ARTIFACT}"
            if source_artifact is not None
            else None
        ),
        "selectedForRuntime": selected,
        "sourcePackageSelected": (
            plan.runtime_artifact_selection.selected_package_mode == "source-package"
            and selected
        ),
        "sourceParsingRequired": False,
        "compilerInvocationRequired": False,
        "expectedPathSuffix": DIRECTX_BACKEND_SOURCE_SUFFIX,
        "pathSuffix": (
            _path_suffix(source_artifact.package_path)
            if source_artifact is not None
            else None
        ),
        "pathSuffixMatchesExpected": (
            _path_has_suffix(
                source_artifact.package_path, DIRECTX_BACKEND_SOURCE_SUFFIX
            )
            if source_artifact is not None
            else None
        ),
        "roleCompatibility": role,
    }


def _directx_native_binary_artifact_detail(
    plan: DirectXLoaderPlan,
    *,
    native_artifact: LoaderArtifactPlan | None,
    descriptor_detail: dict[str, Any],
) -> dict[str, Any]:
    native_status = plan.compatibility_report.native_binary_status
    selected = _runtime_artifact_is(plan, DIRECTX_NATIVE_ARTIFACT)
    role = _artifact_role_record(plan, DIRECTX_NATIVE_ARTIFACT)
    bytes_required = bool(role.get("bytesRequired")) if role is not None else False
    planned_metadata_only = (
        native_status == "planned" and not selected and not bytes_required
    )
    binary_kind, binary_kind_source = _directx_native_binary_kind(
        native_artifact=native_artifact,
        descriptor_detail=descriptor_detail,
    )
    expected_suffix = DIRECTX_NATIVE_BINARY_SUFFIXES_BY_KIND.get(binary_kind)
    path_suffix = (
        _path_suffix(native_artifact.package_path)
        if native_artifact is not None
        else None
    )
    path_suffix_matches_expected = (
        path_suffix == expected_suffix
        if path_suffix is not None and expected_suffix is not None
        else None
    )

    detail = {
        "name": DIRECTX_NATIVE_ARTIFACT,
        "declared": native_artifact is not None,
        "exists": native_artifact.exists if native_artifact is not None else False,
        "path": native_artifact.package_path if native_artifact is not None else None,
        "size": native_artifact.size if native_artifact is not None else None,
        "nativeBinaryStatus": native_status,
        "status": _directx_native_binary_status(
            native_status=native_status,
            selected=selected,
            planned_metadata_only=planned_metadata_only,
            declared=native_artifact is not None,
        ),
        "selectedForRuntime": selected,
        "acceptedForNativeSelection": (
            plan.loadable
            and selected
            and plan.runtime_artifact_selection.selected_package_mode == "native"
        ),
        "acceptedAsSourcePackageEvidence": (
            plan.loadable
            and native_status == "planned"
            and native_artifact is not None
            and plan.runtime_artifact_selection.selected_package_mode
            == "source-package"
        ),
        "bytesRequired": bytes_required,
        "plannedMetadataOnly": planned_metadata_only,
        "binaryKind": binary_kind,
        "binaryKindSource": binary_kind_source,
        "descriptorBinaryKind": _directx_descriptor_binary_kind(descriptor_detail),
        "expectedBinaryKind": binary_kind,
        "expectedBinaryKinds": list(DIRECTX_NATIVE_BINARY_KINDS),
        "expectedPathSuffix": expected_suffix,
        "expectedPathSuffixes": list(DIRECTX_NATIVE_BINARY_SUFFIXES),
        "pathSuffix": path_suffix,
        "pathSuffixMatchesExpected": path_suffix_matches_expected,
        "emittedDescriptorManifestConsistent": (
            descriptor_detail["manifestConsistent"]
            if native_status == "emitted" and descriptor_detail["declared"]
            else None
        ),
        "roleCompatibility": role,
    }
    if binary_kind == DIRECTX_DXBC_BINARY_KIND:
        detail["pathSuffixMatchesDxbc"] = path_suffix_matches_expected
    else:
        detail["pathSuffixMatchesDxil"] = path_suffix_matches_expected
    return detail


def _directx_native_binary_status(
    *,
    native_status: Any,
    selected: bool,
    planned_metadata_only: bool,
    declared: bool,
) -> str:
    if native_status == "planned":
        return (
            "planned-metadata-only"
            if planned_metadata_only
            else "planned-native-requested"
        )
    if native_status == "emitted":
        if selected:
            return "emitted-selected"
        return "emitted-sidecar" if declared else "emitted-missing"
    if native_status is None:
        return "not-declared"
    return "unsupported-status"


def _directx_native_binary_artifact_key(detail: dict[str, Any]) -> str:
    if detail.get("binaryKind") == DIRECTX_DXBC_BINARY_KIND:
        return "dxbcArtifact"
    return "dxilArtifact"


def _directx_native_binary_kind(
    *,
    native_artifact: LoaderArtifactPlan | None,
    descriptor_detail: dict[str, Any],
) -> tuple[str, str]:
    descriptor_binary_kind = _directx_descriptor_binary_kind(descriptor_detail)
    if descriptor_binary_kind in DIRECTX_NATIVE_BINARY_SUFFIXES_BY_KIND:
        return descriptor_binary_kind, "nativeArtifactDescriptor.binaryKind"

    if native_artifact is not None:
        path_binary_kind = _directx_native_binary_kind_for_path(
            native_artifact.package_path
        )
        if path_binary_kind is not None:
            return path_binary_kind, "manifest.artifacts.nativeBinary"

    return DIRECTX_DXIL_BINARY_KIND, "default"


def _directx_descriptor_binary_kind(
    descriptor_detail: dict[str, Any],
) -> str | None:
    binary_kind = descriptor_detail.get("binaryKind")
    return binary_kind if isinstance(binary_kind, str) else None


def _directx_native_binary_kind_for_path(package_path: str) -> str | None:
    path_suffix = _path_suffix(package_path)
    for binary_kind, suffix in DIRECTX_NATIVE_BINARY_SUFFIXES_BY_KIND.items():
        if path_suffix == suffix:
            return binary_kind
    return None


def _directx_descriptor_detail(
    plan: DirectXLoaderPlan,
    *,
    native_artifact: LoaderArtifactPlan | None,
    descriptor: NativeArtifactDescriptorPlan | None,
) -> dict[str, Any]:
    diagnostics = _descriptor_diagnostics(plan)
    if descriptor is None:
        return {
            "declared": False,
            "readable": False,
            "artifact": None,
            "fields": {},
            "sourcePathDeclared": False,
            "binaryKindMatchesLoader": None,
            "artifactPathMatchesManifest": None,
            "nativeBinaryStatusMatchesManifest": None,
            "sizeBytesMatchesArtifact": None,
            "manifestConsistent": None,
            "consistencyStatus": "not-declared",
            "diagnostics": diagnostics,
        }

    fields = dict(descriptor.fields)
    artifact_path = fields.get("artifactPath")
    native_status = plan.compatibility_report.native_binary_status
    descriptor_native_status = fields.get("nativeBinaryStatus")
    size_bytes = fields.get("sizeBytes")
    artifact_path_matches = (
        artifact_path == native_artifact.package_path
        if native_artifact is not None and isinstance(artifact_path, str)
        else None
    )
    size_matches = (
        size_bytes == native_artifact.size
        if native_artifact is not None
        and native_artifact.size is not None
        and isinstance(size_bytes, int)
        and not isinstance(size_bytes, bool)
        else None
    )
    manifest_consistent = (
        descriptor.readable
        and descriptor.binary_kind_matches_loader is True
        and not diagnostics
    )

    return {
        "declared": True,
        "readable": descriptor.readable,
        "artifact": descriptor.artifact.to_summary(),
        "fields": fields,
        "sourcePathDeclared": descriptor.source_path_declared,
        "binaryKind": descriptor.binary_kind,
        "expectedBinaryKinds": list(descriptor.expected_binary_kinds),
        "binaryKindMatchesLoader": descriptor.binary_kind_matches_loader,
        "artifactPath": artifact_path if isinstance(artifact_path, str) else None,
        "manifestNativeBinaryPath": (
            native_artifact.package_path if native_artifact is not None else None
        ),
        "artifactPathMatchesManifest": artifact_path_matches,
        "nativeBinaryStatus": descriptor_native_status,
        "manifestNativeBinaryStatus": native_status,
        "nativeBinaryStatusMatchesManifest": descriptor_native_status == native_status,
        "sizeBytes": size_bytes,
        "manifestNativeBinarySize": (
            native_artifact.size if native_artifact is not None else None
        ),
        "sizeBytesMatchesArtifact": size_matches,
        "manifestConsistent": manifest_consistent,
        "consistencyStatus": _descriptor_consistency_status(
            plan,
            descriptor=descriptor,
            diagnostics=diagnostics,
        ),
        "diagnostics": diagnostics,
    }


def _directx_compatibility_evidence(
    plan: DirectXLoaderPlan,
    *,
    source_artifact: LoaderArtifactPlan | None,
    native_artifact_detail: dict[str, Any],
    descriptor_detail: dict[str, Any],
) -> dict[str, Any]:
    return {
        "manifestNativeBinaryStatus": plan.compatibility_report.native_binary_status,
        "packageArtifactRequirementsSource": plan.package_artifact_requirements_source,
        "packageArtifactRequirements": plan.package_artifact_requirements,
        "requiredArtifacts": list(plan.required_artifacts),
        "requiredArtifactPaths": plan.required_artifact_paths,
        "declaredSourcePath": (
            source_artifact.package_path if source_artifact is not None else None
        ),
        "sourceArtifactExists": (
            source_artifact.exists if source_artifact is not None else False
        ),
        "compiledArtifactStatus": native_artifact_detail["status"],
        "compiledArtifactPath": native_artifact_detail["path"],
        "compiledArtifactExists": native_artifact_detail["exists"],
        "descriptorDeclared": descriptor_detail["declared"],
        "descriptorReadable": descriptor_detail["readable"],
        "descriptorManifestConsistent": descriptor_detail["manifestConsistent"],
        "descriptorDiagnostics": descriptor_detail["diagnostics"],
        "targetLegalizationEvidence": (
            plan.compatibility_report.target_legalization_evidence
        ),
        "targetLegalizationToolRequirements": (
            plan.compatibility_report.target_legalization_tool_requirements
        ),
    }


def _descriptor_consistency_status(
    plan: DirectXLoaderPlan,
    *,
    descriptor: NativeArtifactDescriptorPlan,
    diagnostics: list[dict[str, Any]],
) -> str:
    if not descriptor.readable:
        return "unreadable"
    if diagnostics:
        return "inconsistent"
    if plan.compatibility_report.native_binary_status == "planned":
        return "planned-metadata-only"
    return "consistent"


def _artifact_plan(
    plan: DirectXLoaderPlan,
    name: str,
) -> LoaderArtifactPlan | None:
    for artifact in plan.compatibility_report.available_artifacts:
        if artifact.name == name:
            return LoaderArtifactPlan.from_artifact(artifact)
    return None


def _available_artifact(
    plan: SourceFreeNativeBackendLoaderPlan,
    name: str,
) -> LoaderArtifactPlan | None:
    for artifact in plan.runtime_plan.compatibility_report.available_artifacts:
        if artifact.name == name:
            return LoaderArtifactPlan.from_artifact(artifact)
    return None


def _directx_expected_native_suffix(
    descriptor: NativeArtifactDescriptorPlan | None,
) -> str | None:
    if descriptor is None or not descriptor.readable:
        return None
    return DIRECTX_NATIVE_BINARY_SUFFIXES_BY_KIND.get(descriptor.binary_kind)


def _artifact_role_record(
    plan: DirectXLoaderPlan,
    role_name: str,
) -> dict[str, Any] | None:
    for record in plan.artifact_role_compatibility["roles"]:
        if record.get("role") == role_name:
            return record
    return None


def _runtime_artifact_is(plan: DirectXLoaderPlan, name: str) -> bool:
    return plan.runtime_artifact is not None and plan.runtime_artifact.name == name


def _descriptor_diagnostics(
    plan: DirectXLoaderPlan | DirectXNativeLoaderPlan,
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


def _descriptor_artifact_path_has_suffix(
    descriptor: NativeArtifactDescriptorPlan | None,
    suffix: str,
) -> bool | None:
    if descriptor is None or not descriptor.readable:
        return None
    artifact_path = descriptor.fields.get("artifactPath")
    if not isinstance(artifact_path, str):
        return None
    return _path_has_suffix(artifact_path, suffix)


def _descriptor_artifact_path_has_any_suffix(
    descriptor: NativeArtifactDescriptorPlan | None,
    suffixes: tuple[str, ...],
) -> bool | None:
    if descriptor is None or not descriptor.readable:
        return None
    artifact_path = descriptor.fields.get("artifactPath")
    if not isinstance(artifact_path, str):
        return None
    return _path_has_any_suffix(artifact_path, suffixes)


def _descriptor_artifact_hash(
    descriptor: NativeArtifactDescriptorPlan | None,
) -> Any:
    if descriptor is None or not descriptor.readable:
        return None
    return descriptor.fields.get("artifactHash")


def _descriptor_artifact_hash_matches(
    plan: DirectXNativeLoaderPlan,
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


def _descriptor_native_binary_status_matches(
    plan: DirectXNativeLoaderPlan,
    descriptor: NativeArtifactDescriptorPlan | None,
) -> bool | None:
    if descriptor is None or not descriptor.readable:
        return None
    return (
        descriptor.fields.get("nativeBinaryStatus")
        == plan.runtime_plan.compatibility_report.native_binary_status
    )


def _has_diagnostic_code(plan: DirectXNativeLoaderPlan, code: str) -> bool:
    return any(diagnostic.code == code for diagnostic in plan.diagnostics)


def _first_blocking_diagnostic(
    diagnostics: tuple[CompatibilityDiagnostic, ...],
) -> CompatibilityDiagnostic | None:
    return next(
        (
            diagnostic
            for diagnostic in diagnostics
            if diagnostic.severity in {"error", "skip"}
        ),
        None,
    )


def _has_blocking_diagnostics(
    diagnostics: tuple[CompatibilityDiagnostic, ...] | list[CompatibilityDiagnostic],
) -> bool:
    return _first_blocking_diagnostic(tuple(diagnostics)) is not None


def _path_suffix(package_path: str) -> str:
    return PurePosixPath(package_path).suffix.lower()


def _path_has_suffix(package_path: str, suffix: str) -> bool:
    return _path_suffix(package_path) == suffix


def _path_has_any_suffix(package_path: str, suffixes: tuple[str, ...]) -> bool:
    return _path_suffix(package_path) in suffixes
