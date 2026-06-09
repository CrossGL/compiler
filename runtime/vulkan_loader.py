#!/usr/bin/env python3
"""Source-free Vulkan package loader planning prototype."""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from pathlib import PurePosixPath
from typing import Any

from .backend_loader import NATIVE_ARTIFACT_DESCRIPTOR
from .backend_loader import NativeArtifactDescriptorPlan
from .backend_loader import SourceFreeNativeBackendLoaderPlan
from .backend_loader import plan_source_free_native_backend_loader
from .loader import LoaderArtifactPlan
from .package_reader import CompatibilityDiagnostic, PackageReadError
from .package_reader import RUNTIME_METADATA_JSON_BYTE_LIMIT
from .package_reader import NATIVE_ARTIFACT_DESCRIPTOR_CONTRACT_VERSION
from .package_reader import SUPPORTED_NATIVE_ARTIFACT_DESCRIPTOR_SCHEMA_VERSION


VULKAN_LOADER_TARGET = "vulkan"
VULKAN_NATIVE_ARTIFACT = "nativeBinary"
VULKAN_BACKEND_ASSEMBLY_ARTIFACT = "backendAssembly"
VULKAN_NATIVE_PROFILE_ARTIFACT = "nativeProfile"
VULKAN_NATIVE_BINARY_KIND = "vulkan.spirv-module"
VULKAN_NATIVE_BINARY_SUFFIX = ".spv"
_VULKAN_NATIVE_PROFILE_SUMMARY_FIELDS = (
    "schemaVersion",
    "module",
    "target",
    "artifacts",
    "backendAssembly",
    "nativeBinary",
    "debug",
)
_VULKAN_GRAPHICS_STAGES = ("vertex", "fragment")


@dataclass(frozen=True)
class VulkanNativeProfilePlan:
    """Runtime-facing summary of Vulkan native profile metadata."""

    artifact: LoaderArtifactPlan
    readable: bool
    fields: dict[str, Any]

    def to_summary(self) -> dict[str, Any]:
        return {
            "artifact": self.artifact.to_summary(),
            "readable": self.readable,
            "fields": dict(self.fields),
        }


@dataclass(frozen=True)
class VulkanNativeLoaderPlan(SourceFreeNativeBackendLoaderPlan):
    """Vulkan-specific metadata-only native-loader admission plan."""

    native_profile: VulkanNativeProfilePlan | None = None

    @property
    def vulkan_native_admission_detail(self) -> dict[str, Any]:
        return _vulkan_native_admission_detail(self)

    @property
    def vulkan_native_api_boundary(self) -> dict[str, Any]:
        return _vulkan_native_api_boundary(self)

    def to_summary(self) -> dict[str, Any]:
        summary = super().to_summary()
        summary["vulkanNativeProfile"] = (
            self.native_profile.to_summary()
            if self.native_profile is not None
            else None
        )
        summary["vulkanNativeAdmission"] = self.vulkan_native_admission_detail
        summary["vulkanNativeApiBoundary"] = self.vulkan_native_api_boundary
        return summary


def plan_vulkan_native_loader(
    package_path: Path | str,
) -> VulkanNativeLoaderPlan:
    """Return a metadata-only Vulkan native-loader validation plan."""
    base_plan = plan_source_free_native_backend_loader(
        package_path,
        VULKAN_LOADER_TARGET,
        loader_name="vulkan-native",
    )
    native_profile = _vulkan_native_profile_plan(base_plan)
    base_diagnostics = _vulkan_filtered_base_diagnostics(base_plan, native_profile)
    diagnostics = (
        *base_diagnostics,
        *_vulkan_native_loader_diagnostics(base_plan, native_profile),
    )
    native_artifact = base_plan.native_artifact
    if native_artifact is None and not _has_blocking_diagnostics(diagnostics):
        native_artifact = _available_artifact(base_plan, VULKAN_NATIVE_ARTIFACT)
    if _has_blocking_diagnostics(diagnostics):
        native_artifact = None

    return VulkanNativeLoaderPlan(
        package_path=base_plan.package_path,
        loader_name=base_plan.loader_name,
        target=base_plan.target,
        runtime_plan=base_plan.runtime_plan,
        native_artifact=native_artifact,
        native_artifact_descriptor=base_plan.native_artifact_descriptor,
        native_profile=native_profile,
        entry_points=base_plan.entry_points,
        resources=base_plan.resources,
        target_resource_bindings=base_plan.target_resource_bindings,
        workgroup_sizes=base_plan.workgroup_sizes,
        diagnostics=diagnostics,
    )


def _vulkan_native_loader_diagnostics(
    plan: SourceFreeNativeBackendLoaderPlan,
    native_profile: VulkanNativeProfilePlan | None,
) -> tuple[CompatibilityDiagnostic, ...]:
    diagnostics: list[CompatibilityDiagnostic] = []
    native_artifact = _available_artifact(plan, VULKAN_NATIVE_ARTIFACT)
    backend_assembly = _available_artifact(plan, VULKAN_BACKEND_ASSEMBLY_ARTIFACT)

    if native_artifact is not None and not _path_has_suffix(
        native_artifact.package_path,
        VULKAN_NATIVE_BINARY_SUFFIX,
    ):
        diagnostics.append(
            CompatibilityDiagnostic(
                code="vulkan_loader.native_artifact_spv_path_mismatch",
                message=(
                    "Vulkan native loader requires manifest.artifacts.nativeBinary "
                    "to reference a .spv artifact"
                ),
                document="manifest",
                artifact=VULKAN_NATIVE_ARTIFACT,
                path=native_artifact.package_path,
                expected=f"*{VULKAN_NATIVE_BINARY_SUFFIX}",
                actual=native_artifact.package_path,
            )
        )

    diagnostics.extend(
        _vulkan_native_artifact_descriptor_diagnostics(plan, native_artifact)
    )
    diagnostics.extend(
        _vulkan_native_profile_diagnostics(
            plan,
            native_profile=native_profile,
            native_artifact=native_artifact,
            backend_assembly=backend_assembly,
            descriptor=plan.native_artifact_descriptor,
        )
    )
    diagnostics.extend(_vulkan_graphics_stage_diagnostics(plan))
    return tuple(diagnostics)


def _vulkan_native_artifact_descriptor_diagnostics(
    plan: SourceFreeNativeBackendLoaderPlan,
    native_artifact: LoaderArtifactPlan | None,
) -> tuple[CompatibilityDiagnostic, ...]:
    descriptor = plan.native_artifact_descriptor
    if descriptor is None:
        return (
            CompatibilityDiagnostic(
                code="vulkan_loader.native_artifact_descriptor_missing",
                message=(
                    "Vulkan native loader requires manifest.artifacts."
                    "nativeArtifactDescriptor metadata"
                ),
                document="manifest",
                artifact=NATIVE_ARTIFACT_DESCRIPTOR,
                path=f"artifacts.{NATIVE_ARTIFACT_DESCRIPTOR}",
                expected="declared nativeArtifactDescriptor metadata",
                actual="missing",
            ),
        )
    if not descriptor.readable:
        return ()

    diagnostics: list[CompatibilityDiagnostic] = []
    descriptor_artifact_path = descriptor.fields.get("artifactPath")
    if (
        native_artifact is not None
        and isinstance(descriptor_artifact_path, str)
        and descriptor_artifact_path != native_artifact.package_path
    ):
        diagnostics.append(
            CompatibilityDiagnostic(
                code=(
                    "vulkan_loader.native_artifact_descriptor_artifact_path_mismatch"
                ),
                message=(
                    "Vulkan native loader requires "
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
        VULKAN_NATIVE_BINARY_SUFFIX,
    ):
        diagnostics.append(
            CompatibilityDiagnostic(
                code=("vulkan_loader.native_artifact_descriptor_spv_path_mismatch"),
                message=(
                    "Vulkan native loader requires "
                    "nativeArtifactDescriptor.artifactPath to reference a .spv "
                    "artifact"
                ),
                document="nativeArtifactDescriptor",
                artifact=NATIVE_ARTIFACT_DESCRIPTOR,
                path="artifactPath",
                expected=f"*{VULKAN_NATIVE_BINARY_SUFFIX}",
                actual=descriptor_artifact_path,
            )
        )
    return tuple(diagnostics)


def _vulkan_native_profile_diagnostics(
    plan: SourceFreeNativeBackendLoaderPlan,
    *,
    native_profile: VulkanNativeProfilePlan | None,
    native_artifact: LoaderArtifactPlan | None,
    backend_assembly: LoaderArtifactPlan | None,
    descriptor: NativeArtifactDescriptorPlan | None,
) -> tuple[CompatibilityDiagnostic, ...]:
    descriptor_profile_path = _descriptor_native_profile_evidence_path(descriptor)
    if descriptor_profile_path is not None and native_profile is None:
        return (
            CompatibilityDiagnostic(
                code=(
                    "vulkan_loader.native_artifact_descriptor_native_profile_missing"
                ),
                message=(
                    "Vulkan native loader requires manifest.artifacts.nativeProfile "
                    "when nativeArtifactDescriptor optimization evidence cites a "
                    "native profile"
                ),
                document="nativeArtifactDescriptor",
                artifact=NATIVE_ARTIFACT_DESCRIPTOR,
                path="optimizationEvidence.evidenceSource.path",
                expected="manifest.artifacts.nativeProfile",
                actual=descriptor_profile_path,
            ),
        )

    if native_profile is None:
        return (
            CompatibilityDiagnostic(
                code="vulkan_loader.native_profile_missing",
                message=(
                    "Vulkan native loader requires manifest.artifacts.nativeProfile "
                    "metadata"
                ),
                document="manifest",
                artifact=VULKAN_NATIVE_PROFILE_ARTIFACT,
                path=f"artifacts.{VULKAN_NATIVE_PROFILE_ARTIFACT}",
                expected="declared Vulkan native profile metadata",
                actual="missing",
            ),
        )

    diagnostics: list[CompatibilityDiagnostic] = []
    profile_artifact = native_profile.artifact
    if not profile_artifact.exists:
        diagnostics.append(
            CompatibilityDiagnostic(
                code="vulkan_loader.native_profile_missing",
                message=(
                    "Vulkan native loader requires the manifest-declared "
                    "nativeProfile file to exist"
                ),
                document="nativeProfile",
                artifact=VULKAN_NATIVE_PROFILE_ARTIFACT,
                path=profile_artifact.package_path,
                expected="existing Vulkan native profile JSON object",
                actual="missing",
            )
        )
        return tuple(diagnostics)

    if not native_profile.readable:
        diagnostics.append(
            CompatibilityDiagnostic(
                code="vulkan_loader.native_profile_unreadable",
                message=(
                    "Vulkan native loader requires the manifest-declared "
                    "nativeProfile to be readable JSON object metadata"
                ),
                document="nativeProfile",
                artifact=VULKAN_NATIVE_PROFILE_ARTIFACT,
                path=profile_artifact.package_path,
                expected="readable JSON object",
                actual="unreadable",
            )
        )
        return tuple(diagnostics)

    if (
        descriptor_profile_path is not None
        and descriptor_profile_path != profile_artifact.package_path
    ):
        diagnostics.append(
            CompatibilityDiagnostic(
                code=("vulkan_loader.native_profile_descriptor_evidence_path_mismatch"),
                message=(
                    "Vulkan native loader requires "
                    "nativeArtifactDescriptor.optimizationEvidence.evidenceSource.path "
                    "to match manifest.artifacts.nativeProfile"
                ),
                document="nativeArtifactDescriptor",
                artifact=NATIVE_ARTIFACT_DESCRIPTOR,
                path="optimizationEvidence.evidenceSource.path",
                expected=profile_artifact.package_path,
                actual=descriptor_profile_path,
            )
        )

    fields = native_profile.fields
    schema_version = fields.get("schemaVersion")
    if schema_version != 1:
        diagnostics.append(
            CompatibilityDiagnostic(
                code="vulkan_loader.native_profile_schema_version_mismatch",
                message=("Vulkan native loader requires nativeProfile.schemaVersion=1"),
                document="nativeProfile",
                artifact=VULKAN_NATIVE_PROFILE_ARTIFACT,
                path="schemaVersion",
                expected=1,
                actual=schema_version,
            )
        )

    profile_target = fields.get("target")
    if profile_target != VULKAN_LOADER_TARGET:
        diagnostics.append(
            CompatibilityDiagnostic(
                code="vulkan_loader.native_profile_target_mismatch",
                message=(
                    "Vulkan native loader requires nativeProfile.target to match "
                    "the loader target"
                ),
                document="nativeProfile",
                artifact=VULKAN_NATIVE_PROFILE_ARTIFACT,
                path="target",
                expected=VULKAN_LOADER_TARGET,
                actual=profile_target,
            )
        )

    module = fields.get("module")
    if plan.runtime_plan.module is not None and not isinstance(module, str):
        diagnostics.append(
            CompatibilityDiagnostic(
                code="vulkan_loader.native_profile_module_missing",
                message=(
                    "Vulkan native loader requires nativeProfile.module to match "
                    "manifest.module"
                ),
                document="nativeProfile",
                artifact=VULKAN_NATIVE_PROFILE_ARTIFACT,
                path="module",
                expected=plan.runtime_plan.module,
                actual=module,
            )
        )
    if (
        isinstance(module, str)
        and plan.runtime_plan.module is not None
        and module != plan.runtime_plan.module
    ):
        diagnostics.append(
            CompatibilityDiagnostic(
                code="vulkan_loader.native_profile_module_mismatch",
                message=(
                    "Vulkan native loader requires nativeProfile.module to match "
                    "manifest.module"
                ),
                document="nativeProfile",
                artifact=VULKAN_NATIVE_PROFILE_ARTIFACT,
                path="module",
                expected=plan.runtime_plan.module,
                actual=module,
            )
        )

    backend_assembly_path = _vulkan_profile_artifact_path(
        fields,
        VULKAN_BACKEND_ASSEMBLY_ARTIFACT,
    )
    if backend_assembly is not None and not isinstance(backend_assembly_path, str):
        diagnostics.append(
            CompatibilityDiagnostic(
                code="vulkan_loader.native_profile_backend_assembly_missing",
                message=(
                    "Vulkan native loader requires nativeProfile.backendAssembly "
                    "to match manifest.artifacts.backendAssembly"
                ),
                document="nativeProfile",
                artifact=VULKAN_NATIVE_PROFILE_ARTIFACT,
                path="backendAssembly",
                expected=backend_assembly.package_path,
                actual=backend_assembly_path,
            )
        )
    if (
        isinstance(backend_assembly_path, str)
        and backend_assembly is not None
        and backend_assembly_path != backend_assembly.package_path
    ):
        diagnostics.append(
            CompatibilityDiagnostic(
                code="vulkan_loader.native_profile_backend_assembly_mismatch",
                message=(
                    "Vulkan native loader requires nativeProfile.backendAssembly "
                    "to match manifest.artifacts.backendAssembly"
                ),
                document="nativeProfile",
                artifact=VULKAN_NATIVE_PROFILE_ARTIFACT,
                path="backendAssembly",
                expected=backend_assembly.package_path,
                actual=backend_assembly_path,
            )
        )

    native_binary_path = _vulkan_profile_artifact_path(
        fields,
        VULKAN_NATIVE_ARTIFACT,
    )
    if native_artifact is not None and not isinstance(native_binary_path, str):
        diagnostics.append(
            CompatibilityDiagnostic(
                code="vulkan_loader.native_profile_native_binary_missing",
                message=(
                    "Vulkan native loader requires nativeProfile.nativeBinary "
                    "to match manifest.artifacts.nativeBinary"
                ),
                document="nativeProfile",
                artifact=VULKAN_NATIVE_PROFILE_ARTIFACT,
                path="nativeBinary",
                expected=native_artifact.package_path,
                actual=native_binary_path,
            )
        )
    if (
        isinstance(native_binary_path, str)
        and native_artifact is not None
        and native_binary_path != native_artifact.package_path
    ):
        diagnostics.append(
            CompatibilityDiagnostic(
                code="vulkan_loader.native_profile_native_binary_mismatch",
                message=(
                    "Vulkan native loader requires nativeProfile.nativeBinary "
                    "to match manifest.artifacts.nativeBinary"
                ),
                document="nativeProfile",
                artifact=VULKAN_NATIVE_PROFILE_ARTIFACT,
                path="nativeBinary",
                expected=native_artifact.package_path,
                actual=native_binary_path,
            )
        )

    return tuple(diagnostics)


def _vulkan_native_admission_detail(
    plan: VulkanNativeLoaderPlan,
) -> dict[str, Any]:
    native_artifact = _available_artifact(plan, VULKAN_NATIVE_ARTIFACT)
    backend_assembly = _available_artifact(plan, VULKAN_BACKEND_ASSEMBLY_ARTIFACT)
    descriptor = plan.native_artifact_descriptor
    native_profile = plan.native_profile
    blocking_reason = _first_blocking_diagnostic(plan.diagnostics)
    checks = _vulkan_native_admission_checks(
        plan,
        native_artifact=native_artifact,
        descriptor=descriptor,
        native_profile=native_profile,
        backend_assembly=backend_assembly,
    )
    target_contract = plan.runtime_plan.compatibility_report.target_contract

    return {
        "schemaVersion": 1,
        "metadataOnly": True,
        "decision": "accepted" if plan.ready else "rejected",
        "status": "ready" if plan.ready else "rejected",
        "reason": (
            "vulkan_loader.native_spv_admission.accepted"
            if plan.ready
            else blocking_reason.code
            if blocking_reason is not None
            else None
        ),
        "loaderTarget": VULKAN_LOADER_TARGET,
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
            == VULKAN_LOADER_TARGET,
            "requiredArtifacts": list(plan.runtime_plan.required_artifacts),
            "requiredArtifactPaths": plan.runtime_plan.required_artifact_paths,
            "targetContract": (
                target_contract.to_summary() if target_contract is not None else None
            ),
        },
        "spirvArtifact": _vulkan_spirv_artifact_detail(
            plan,
            native_artifact=native_artifact,
            native_profile=native_profile,
        ),
        "nativeArtifactDescriptor": _vulkan_descriptor_detail(
            plan,
            native_artifact=native_artifact,
            descriptor=descriptor,
        ),
        "nativeProfile": _vulkan_native_profile_detail(
            plan,
            native_artifact=native_artifact,
            native_profile=native_profile,
            backend_assembly=backend_assembly,
        ),
        "reflection": {
            "entryPointCount": len(plan.entry_points),
            "resourceCount": len(plan.resources),
            "targetResourceBindingCount": len(plan.target_resource_bindings),
            "stageCounts": _vulkan_entry_point_stage_counts(plan),
            "graphicsStageClosure": _vulkan_graphics_stage_closure(plan),
            "entryPoints": [
                _summarize_vulkan_entry_point(record) for record in plan.entry_points
            ],
            "resources": [
                _summarize_vulkan_resource(record) for record in plan.resources
            ],
            "targetResourceBindings": [
                _summarize_vulkan_resource_binding(record)
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


def _vulkan_native_api_boundary(plan: VulkanNativeLoaderPlan) -> dict[str, Any]:
    """Return the metadata handoff a future Vulkan API loader would consume."""
    native_artifact = _available_artifact(plan, VULKAN_NATIVE_ARTIFACT)
    descriptor = plan.native_artifact_descriptor
    native_profile = plan.native_profile
    fields = descriptor.fields if descriptor is not None else {}
    blocking_reason = _first_blocking_diagnostic(plan.diagnostics)

    return {
        "schemaVersion": 1,
        "metadataOnly": True,
        "boundary": "vulkan.native-api.metadata-v0",
        "decision": "accepted" if plan.ready else "rejected",
        "status": "ready" if plan.ready else "rejected",
        "reason": (
            "vulkan_loader.native_api_boundary.accepted"
            if plan.ready
            else blocking_reason.code
            if blocking_reason is not None
            else None
        ),
        "loaderTarget": VULKAN_LOADER_TARGET,
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
        "vulkanRuntimeCallsPerformed": False,
        "vulkanInstanceCreationPerformed": False,
        "vulkanDeviceCreationPerformed": False,
        "vulkanShaderModuleCreationPerformed": False,
        "vulkanPipelineCreationPerformed": False,
        "vulkanCommandExecutionPerformed": False,
        "runtimeInputs": {
            "manifest": {
                "target": plan.runtime_plan.package_target,
                "nativeBinaryArtifact": VULKAN_NATIVE_ARTIFACT,
                "nativeArtifactDescriptor": NATIVE_ARTIFACT_DESCRIPTOR,
                "nativeProfile": VULKAN_NATIVE_PROFILE_ARTIFACT,
            },
            "spirvArtifact": _vulkan_api_spirv_input(
                plan,
                native_artifact=native_artifact,
                descriptor=descriptor,
                native_profile=native_profile,
            ),
            "nativeArtifactDescriptor": _vulkan_api_descriptor_input(
                plan,
                native_artifact=native_artifact,
                descriptor=descriptor,
            ),
            "nativeProfile": _vulkan_api_profile_input(
                plan,
                native_artifact=native_artifact,
                native_profile=native_profile,
            ),
            "reflection": _vulkan_api_reflection_input(plan),
            "versionCompatibility": plan.runtime_plan.version_compatibility_summary,
        },
        "descriptorFreshness": {
            "artifactPathMatchesSpirv": _descriptor_artifact_path_matches(
                descriptor,
                native_artifact,
            ),
            "artifactHashDeclared": "artifactHash" in fields,
            "artifactHashMatchesSpirv": _descriptor_artifact_hash_matches(
                plan,
                descriptor,
                native_artifact,
            ),
            "sizeBytesMatchesSpirv": _descriptor_size_bytes_matches(
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
        "nativeProfileCompatibility": {
            "declared": native_profile is not None,
            "readable": native_profile is not None and native_profile.readable,
            "targetMatchesLoader": (
                native_profile.fields.get("target") == VULKAN_LOADER_TARGET
                if native_profile is not None and native_profile.readable
                else None
            ),
            "nativeBinaryMatchesSpirv": (
                _vulkan_profile_artifact_path(
                    native_profile.fields,
                    VULKAN_NATIVE_ARTIFACT,
                )
                == native_artifact.package_path
                if native_profile is not None
                and native_profile.readable
                and native_artifact is not None
                else None
            ),
            "failClosedDiagnosticCodes": [
                diagnostic.code
                for diagnostic in plan.diagnostics
                if diagnostic.document == "nativeProfile"
                or diagnostic.artifact == VULKAN_NATIVE_PROFILE_ARTIFACT
            ],
        },
        "blockedByDiagnostics": [
            diagnostic.to_summary()
            for diagnostic in plan.diagnostics
            if diagnostic.severity in {"error", "skip"}
        ],
    }


def _vulkan_spirv_artifact_detail(
    plan: VulkanNativeLoaderPlan,
    *,
    native_artifact: LoaderArtifactPlan | None,
    native_profile: VulkanNativeProfilePlan | None,
) -> dict[str, Any]:
    runtime_artifact = plan.runtime_plan.runtime_artifact
    selected_for_runtime = (
        runtime_artifact is not None and runtime_artifact.name == VULKAN_NATIVE_ARTIFACT
    )
    native_profile_binary = (
        native_profile.fields.get("nativeBinary")
        if native_profile is not None and native_profile.readable
        else None
    )

    return {
        "name": VULKAN_NATIVE_ARTIFACT,
        "declared": native_artifact is not None,
        "exists": native_artifact.exists if native_artifact is not None else False,
        "selectedForRuntime": selected_for_runtime,
        "acceptedForLoad": plan.ready and plan.native_artifact is not None,
        "path": native_artifact.package_path if native_artifact is not None else None,
        "absolutePath": (
            native_artifact.absolute_path or str(native_artifact.path)
            if native_artifact is not None
            else None
        ),
        "size": native_artifact.size if native_artifact is not None else None,
        "expectedPathSuffix": VULKAN_NATIVE_BINARY_SUFFIX,
        "pathSuffix": (
            _path_suffix(native_artifact.package_path)
            if native_artifact is not None
            else None
        ),
        "pathSuffixMatchesSpv": (
            _path_has_suffix(
                native_artifact.package_path,
                VULKAN_NATIVE_BINARY_SUFFIX,
            )
            if native_artifact is not None
            else None
        ),
        "expectedBinaryKind": VULKAN_NATIVE_BINARY_KIND,
        "descriptorBinaryKind": (
            plan.native_artifact_descriptor.binary_kind
            if plan.native_artifact_descriptor is not None
            else None
        ),
        "descriptorArtifactHash": _descriptor_artifact_hash(
            plan.native_artifact_descriptor,
        ),
        "descriptorArtifactHashMatchesSpirv": _descriptor_artifact_hash_matches(
            plan,
            plan.native_artifact_descriptor,
            native_artifact,
        ),
        "profileNativeBinary": (
            native_profile_binary if isinstance(native_profile_binary, str) else None
        ),
    }


def _vulkan_descriptor_detail(
    plan: VulkanNativeLoaderPlan,
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
            "target": None,
            "targetMatchesLoader": None,
            "binaryKind": None,
            "expectedBinaryKinds": [VULKAN_NATIVE_BINARY_KIND],
            "binaryKindMatchesLoader": None,
            "artifactPath": None,
            "artifactPathMatchesNativeArtifact": None,
            "artifactPathSuffixMatchesSpv": None,
            "artifactHash": None,
            "artifactHashMatchesArtifact": None,
            "validationStatus": None,
            "nativeBinaryStatus": None,
            "sizeBytes": None,
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
            descriptor_target == VULKAN_LOADER_TARGET if descriptor.readable else None
        ),
        "binaryKind": descriptor.binary_kind,
        "expectedBinaryKinds": list(descriptor.expected_binary_kinds),
        "binaryKindMatchesLoader": descriptor.binary_kind_matches_loader,
        "artifactPath": artifact_path if isinstance(artifact_path, str) else None,
        "artifactPathMatchesNativeArtifact": artifact_path_matches,
        "artifactPathSuffixMatchesSpv": (
            _path_has_suffix(artifact_path, VULKAN_NATIVE_BINARY_SUFFIX)
            if isinstance(artifact_path, str)
            else None
        ),
        "artifactHash": _descriptor_artifact_hash(descriptor),
        "artifactHashMatchesArtifact": _descriptor_artifact_hash_matches(
            plan,
            descriptor,
            native_artifact,
        ),
        "validationStatus": fields.get("validationStatus"),
        "nativeBinaryStatus": fields.get("nativeBinaryStatus"),
        "sizeBytes": size_bytes,
        "sizeBytesMatchesArtifact": size_matches,
        "diagnostics": diagnostics,
    }


def _vulkan_native_profile_detail(
    plan: VulkanNativeLoaderPlan,
    *,
    native_artifact: LoaderArtifactPlan | None,
    native_profile: VulkanNativeProfilePlan | None,
    backend_assembly: LoaderArtifactPlan | None,
) -> dict[str, Any]:
    diagnostics = [
        diagnostic.to_summary()
        for diagnostic in plan.diagnostics
        if diagnostic.document == "nativeProfile"
        or diagnostic.artifact == VULKAN_NATIVE_PROFILE_ARTIFACT
    ]
    if native_profile is None:
        return {
            "declared": False,
            "readable": False,
            "artifact": None,
            "fields": {},
            "target": None,
            "targetMatchesLoader": None,
            "module": None,
            "moduleMatchesManifest": None,
            "backendAssembly": None,
            "backendAssemblyMatchesManifest": None,
            "nativeBinary": None,
            "nativeBinaryMatchesNativeArtifact": None,
            "disassembly": None,
            "diagnostics": diagnostics,
        }

    fields = dict(native_profile.fields)
    profile_target = fields.get("target")
    module = fields.get("module")
    backend_assembly_path = _vulkan_profile_artifact_path(
        fields,
        VULKAN_BACKEND_ASSEMBLY_ARTIFACT,
    )
    native_binary_path = _vulkan_profile_artifact_path(
        fields,
        VULKAN_NATIVE_ARTIFACT,
    )
    descriptor_profile_path = _descriptor_native_profile_evidence_path(
        plan.native_artifact_descriptor,
    )

    return {
        "declared": True,
        "readable": native_profile.readable,
        "artifact": native_profile.artifact.to_summary(),
        "fields": fields,
        "target": profile_target if isinstance(profile_target, str) else None,
        "targetMatchesLoader": (
            profile_target == VULKAN_LOADER_TARGET if native_profile.readable else None
        ),
        "module": module if isinstance(module, str) else None,
        "moduleMatchesManifest": (
            module == plan.runtime_plan.module
            if isinstance(module, str) and plan.runtime_plan.module is not None
            else None
        ),
        "backendAssembly": (
            backend_assembly_path if isinstance(backend_assembly_path, str) else None
        ),
        "backendAssemblyMatchesManifest": (
            backend_assembly_path == backend_assembly.package_path
            if isinstance(backend_assembly_path, str) and backend_assembly is not None
            else None
        ),
        "nativeBinary": (
            native_binary_path if isinstance(native_binary_path, str) else None
        ),
        "nativeBinaryMatchesNativeArtifact": (
            native_binary_path == native_artifact.package_path
            if isinstance(native_binary_path, str) and native_artifact is not None
            else None
        ),
        "descriptorEvidenceSourcePath": descriptor_profile_path,
        "descriptorEvidenceSourcePathMatchesNativeProfile": (
            descriptor_profile_path == native_profile.artifact.package_path
            if isinstance(descriptor_profile_path, str)
            else None
        ),
        "disassembly": _vulkan_profile_disassembly(fields),
        "diagnostics": diagnostics,
    }


def _vulkan_native_admission_checks(
    plan: VulkanNativeLoaderPlan,
    *,
    native_artifact: LoaderArtifactPlan | None,
    descriptor: NativeArtifactDescriptorPlan | None,
    native_profile: VulkanNativeProfilePlan | None,
    backend_assembly: LoaderArtifactPlan | None,
) -> list[dict[str, Any]]:
    descriptor_declared = descriptor is not None
    descriptor_readable = descriptor is not None and descriptor.readable
    descriptor_fields = descriptor.fields if descriptor is not None else {}
    descriptor_artifact_path = descriptor_fields.get("artifactPath")
    descriptor_artifact_hash = descriptor_fields.get("artifactHash")
    descriptor_size = descriptor_fields.get("sizeBytes")
    descriptor_profile_path = _descriptor_native_profile_evidence_path(descriptor)
    descriptor_size_matches = None
    if (
        native_artifact is not None
        and native_artifact.size is not None
        and isinstance(descriptor_size, int)
        and not isinstance(descriptor_size, bool)
    ):
        descriptor_size_matches = descriptor_size == native_artifact.size

    profile_declared = native_profile is not None
    profile_readable = native_profile is not None and native_profile.readable
    profile_fields = native_profile.fields if native_profile is not None else {}
    profile_native_binary = _vulkan_profile_artifact_path(
        profile_fields,
        VULKAN_NATIVE_ARTIFACT,
    )
    profile_backend_assembly = _vulkan_profile_artifact_path(
        profile_fields,
        VULKAN_BACKEND_ASSEMBLY_ARTIFACT,
    )
    profile_module = profile_fields.get("module")
    graphics_closure = _vulkan_graphics_stage_closure(plan)

    return [
        _admission_check(
            "manifestTargetMatchesLoader",
            plan.runtime_plan.package_target == VULKAN_LOADER_TARGET,
            document="manifest",
            path="target",
            expected=VULKAN_LOADER_TARGET,
            actual=plan.runtime_plan.package_target,
        ),
        _admission_check(
            "nativeBinaryDeclared",
            native_artifact is not None,
            document="manifest",
            artifact=VULKAN_NATIVE_ARTIFACT,
            path=f"artifacts.{VULKAN_NATIVE_ARTIFACT}",
            expected="declared .spv artifact",
            actual=(
                native_artifact.package_path if native_artifact is not None else None
            ),
        ),
        _admission_check(
            "nativeBinaryExists",
            native_artifact.exists if native_artifact is not None else False,
            document="manifest",
            artifact=VULKAN_NATIVE_ARTIFACT,
            path=(
                native_artifact.package_path if native_artifact is not None else None
            ),
            expected="existing .spv artifact",
            actual=(
                "exists"
                if native_artifact is not None and native_artifact.exists
                else "missing"
            ),
        ),
        _admission_check(
            "nativeBinaryPathSuffixMatchesSpv",
            (
                _path_has_suffix(
                    native_artifact.package_path,
                    VULKAN_NATIVE_BINARY_SUFFIX,
                )
                if native_artifact is not None
                else False
            ),
            document="manifest",
            artifact=VULKAN_NATIVE_ARTIFACT,
            path=(
                native_artifact.package_path if native_artifact is not None else None
            ),
            expected=f"*{VULKAN_NATIVE_BINARY_SUFFIX}",
            actual=(
                native_artifact.package_path if native_artifact is not None else None
            ),
        ),
        _admission_check(
            "nativeBinarySelectedForRuntime",
            plan.runtime_plan.runtime_artifact is not None
            and plan.runtime_plan.runtime_artifact.name == VULKAN_NATIVE_ARTIFACT,
            document="manifest",
            artifact=VULKAN_NATIVE_ARTIFACT,
            path=(
                plan.runtime_plan.runtime_artifact.package_path
                if plan.runtime_plan.runtime_artifact is not None
                else None
            ),
            expected=VULKAN_NATIVE_ARTIFACT,
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
            expected="required Vulkan native artifact descriptor metadata",
            actual=(
                descriptor.artifact.package_path if descriptor is not None else None
            ),
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
            "nativeArtifactDescriptorTargetMatchesLoader",
            (
                descriptor_fields.get("target") == VULKAN_LOADER_TARGET
                if descriptor_readable
                else None
            ),
            document="nativeArtifactDescriptor",
            artifact=NATIVE_ARTIFACT_DESCRIPTOR,
            path="target",
            expected=VULKAN_LOADER_TARGET,
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
            expected=[VULKAN_NATIVE_BINARY_KIND],
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
            "nativeArtifactDescriptorArtifactPathSuffixMatchesSpv",
            (
                _path_has_suffix(
                    descriptor_artifact_path,
                    VULKAN_NATIVE_BINARY_SUFFIX,
                )
                if descriptor_readable and isinstance(descriptor_artifact_path, str)
                else None
            ),
            document="nativeArtifactDescriptor",
            artifact=NATIVE_ARTIFACT_DESCRIPTOR,
            path="artifactPath",
            expected=f"*{VULKAN_NATIVE_BINARY_SUFFIX}",
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
            and native_artifact.size is not None
            and "sizeBytes" in descriptor_fields,
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
            "nativeArtifactDescriptorArtifactHashMatchesSpirv",
            _descriptor_artifact_hash_matches(plan, descriptor, native_artifact),
            document="nativeArtifactDescriptor",
            artifact=NATIVE_ARTIFACT_DESCRIPTOR,
            path="artifactHash.value",
            expected="sha256 of selected .spv artifact",
            actual=_descriptor_artifact_hash(descriptor),
            required=descriptor_readable
            and native_artifact is not None
            and native_artifact.exists,
        ),
        _admission_check(
            "nativeArtifactDescriptorEvidenceSourcePathMatchesNativeProfile",
            (
                descriptor_profile_path == native_profile.artifact.package_path
                if profile_declared and isinstance(descriptor_profile_path, str)
                else False
                if isinstance(descriptor_profile_path, str)
                else None
            ),
            document="nativeArtifactDescriptor",
            artifact=NATIVE_ARTIFACT_DESCRIPTOR,
            path="optimizationEvidence.evidenceSource.path",
            expected=(
                native_profile.artifact.package_path
                if native_profile is not None
                else "manifest.artifacts.nativeProfile"
            ),
            actual=descriptor_profile_path,
            required=isinstance(descriptor_profile_path, str),
        ),
        _admission_check(
            "nativeProfileDeclared",
            profile_declared,
            document="manifest",
            artifact=VULKAN_NATIVE_PROFILE_ARTIFACT,
            path=f"artifacts.{VULKAN_NATIVE_PROFILE_ARTIFACT}",
            expected="required Vulkan native profile metadata",
            actual=(
                native_profile.artifact.package_path
                if native_profile is not None
                else None
            ),
        ),
        _admission_check(
            "nativeProfileReadable",
            profile_readable if profile_declared else None,
            document="nativeProfile",
            artifact=VULKAN_NATIVE_PROFILE_ARTIFACT,
            path=(
                native_profile.artifact.package_path
                if native_profile is not None
                else None
            ),
            expected="readable JSON object",
            actual=(
                "readable"
                if profile_readable
                else "missing or unreadable"
                if profile_declared
                else None
            ),
            required=profile_declared,
        ),
        _admission_check(
            "nativeProfileSchemaVersionCompatible",
            profile_fields.get("schemaVersion") == 1 if profile_readable else None,
            document="nativeProfile",
            artifact=VULKAN_NATIVE_PROFILE_ARTIFACT,
            path="schemaVersion",
            expected=1,
            actual=profile_fields.get("schemaVersion"),
            required=profile_readable,
        ),
        _admission_check(
            "nativeProfileTargetMatchesLoader",
            (
                profile_fields.get("target") == VULKAN_LOADER_TARGET
                if profile_readable
                else None
            ),
            document="nativeProfile",
            artifact=VULKAN_NATIVE_PROFILE_ARTIFACT,
            path="target",
            expected=VULKAN_LOADER_TARGET,
            actual=profile_fields.get("target"),
            required=profile_readable,
        ),
        _admission_check(
            "nativeProfileNativeBinaryMatchesNativeArtifact",
            (
                profile_native_binary == native_artifact.package_path
                if profile_readable
                and native_artifact is not None
                and isinstance(profile_native_binary, str)
                else None
            ),
            document="nativeProfile",
            artifact=VULKAN_NATIVE_PROFILE_ARTIFACT,
            path="nativeBinary",
            expected=(
                native_artifact.package_path if native_artifact is not None else None
            ),
            actual=profile_native_binary,
            required=profile_readable,
        ),
        _admission_check(
            "nativeProfileBackendAssemblyMatchesManifest",
            (
                profile_backend_assembly == backend_assembly.package_path
                if profile_readable
                and backend_assembly is not None
                and isinstance(profile_backend_assembly, str)
                else None
            ),
            document="nativeProfile",
            artifact=VULKAN_NATIVE_PROFILE_ARTIFACT,
            path="backendAssembly",
            expected=(
                backend_assembly.package_path if backend_assembly is not None else None
            ),
            actual=profile_backend_assembly,
            required=profile_readable and backend_assembly is not None,
        ),
        _admission_check(
            "nativeProfileModuleMatchesManifest",
            (
                profile_module == plan.runtime_plan.module
                if profile_readable
                and plan.runtime_plan.module is not None
                and isinstance(profile_module, str)
                else None
            ),
            document="nativeProfile",
            artifact=VULKAN_NATIVE_PROFILE_ARTIFACT,
            path="module",
            expected=plan.runtime_plan.module,
            actual=profile_module,
            required=profile_readable and plan.runtime_plan.module is not None,
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
            "reflectionGraphicsVertexFragmentPairPresent",
            (
                graphics_closure["hasVertexFragmentPair"]
                if graphics_closure["graphicsPackage"]
                else None
            ),
            document="reflection",
            path="entryPoints",
            expected="exactly one vertex entry point and one fragment entry point",
            actual=graphics_closure["stageCounts"],
            required=graphics_closure["graphicsPackage"],
        ),
        _admission_check(
            "reflectionGraphicsStagesOnlyVertexFragment",
            (
                graphics_closure["hasOnlyGraphicsStages"]
                if graphics_closure["graphicsPackage"]
                else None
            ),
            document="reflection",
            path="entryPoints",
            expected=list(_VULKAN_GRAPHICS_STAGES),
            actual=graphics_closure["nonGraphicsStages"],
            required=graphics_closure["graphicsPackage"],
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
            expected="non-empty vulkan binding array",
            actual=len(plan.target_resource_bindings),
        ),
    ]


def _vulkan_api_spirv_input(
    plan: VulkanNativeLoaderPlan,
    *,
    native_artifact: LoaderArtifactPlan | None,
    descriptor: NativeArtifactDescriptorPlan | None,
    native_profile: VulkanNativeProfilePlan | None,
) -> dict[str, Any]:
    return {
        "artifactName": VULKAN_NATIVE_ARTIFACT,
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
            and plan.runtime_plan.runtime_artifact.name == VULKAN_NATIVE_ARTIFACT
        ),
        "acceptedForLoad": plan.ready and plan.native_artifact is not None,
        "expectedBinaryKind": VULKAN_NATIVE_BINARY_KIND,
        "expectedPathSuffix": VULKAN_NATIVE_BINARY_SUFFIX,
        "descriptorArtifactPath": (
            descriptor.fields.get("artifactPath")
            if descriptor is not None and descriptor.readable
            else None
        ),
        "descriptorArtifactHash": _descriptor_artifact_hash(descriptor),
        "descriptorArtifactHashMatchesSpirv": _descriptor_artifact_hash_matches(
            plan,
            descriptor,
            native_artifact,
        ),
        "profileNativeBinary": (
            native_profile.fields.get("nativeBinary")
            if native_profile is not None and native_profile.readable
            else None
        ),
    }


def _vulkan_api_descriptor_input(
    plan: VulkanNativeLoaderPlan,
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
            "diagnostics": _vulkan_descriptor_diagnostics(plan),
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
            target == VULKAN_LOADER_TARGET if descriptor.readable else None
        ),
        "binaryKind": descriptor.binary_kind,
        "binaryKindMatchesLoader": descriptor.binary_kind_matches_loader,
        "artifactPath": fields.get("artifactPath"),
        "artifactPathMatchesSpirv": _descriptor_artifact_path_matches(
            descriptor,
            native_artifact,
        ),
        "artifactHash": _descriptor_artifact_hash(descriptor),
        "artifactHashMatchesSpirv": _descriptor_artifact_hash_matches(
            plan,
            descriptor,
            native_artifact,
        ),
        "sizeBytes": fields.get("sizeBytes"),
        "sizeBytesMatchesSpirv": _descriptor_size_bytes_matches(
            descriptor,
            native_artifact,
        ),
        "validationStatus": fields.get("validationStatus"),
        "sourcePathDeclared": descriptor.source_path_declared,
        "sourcePathExposed": False,
        "diagnostics": _vulkan_descriptor_diagnostics(plan),
    }


def _vulkan_api_profile_input(
    plan: VulkanNativeLoaderPlan,
    *,
    native_artifact: LoaderArtifactPlan | None,
    native_profile: VulkanNativeProfilePlan | None,
) -> dict[str, Any]:
    if native_profile is None:
        return {
            "declared": False,
            "readable": False,
            "artifact": None,
            "schemaVersion": None,
            "schemaVersionCompatible": None,
            "target": None,
            "targetMatchesLoader": None,
            "module": None,
            "moduleMatchesManifest": None,
            "backendAssembly": None,
            "nativeBinary": None,
            "nativeBinaryMatchesSpirv": None,
            "diagnostics": _vulkan_profile_diagnostics(plan),
        }

    fields = native_profile.fields
    schema_version = fields.get("schemaVersion")
    target = fields.get("target")
    native_binary = _vulkan_profile_artifact_path(fields, VULKAN_NATIVE_ARTIFACT)
    module = fields.get("module")

    return {
        "declared": True,
        "readable": native_profile.readable,
        "artifact": native_profile.artifact.to_summary(),
        "schemaVersion": schema_version,
        "schemaVersionCompatible": (
            schema_version == 1 if native_profile.readable else None
        ),
        "target": target,
        "targetMatchesLoader": (
            target == VULKAN_LOADER_TARGET if native_profile.readable else None
        ),
        "module": module,
        "moduleMatchesManifest": (
            module == plan.runtime_plan.module if native_profile.readable else None
        ),
        "backendAssembly": _vulkan_profile_artifact_path(
            fields,
            VULKAN_BACKEND_ASSEMBLY_ARTIFACT,
        ),
        "nativeBinary": native_binary,
        "nativeBinaryMatchesSpirv": (
            native_binary == native_artifact.package_path
            if native_profile.readable and native_artifact is not None
            else None
        ),
        "diagnostics": _vulkan_profile_diagnostics(plan),
    }


def _vulkan_api_reflection_input(plan: VulkanNativeLoaderPlan) -> dict[str, Any]:
    return {
        "entryPointCount": len(plan.entry_points),
        "resourceCount": len(plan.resources),
        "targetResourceBindingCount": len(plan.target_resource_bindings),
        "stageCounts": _vulkan_entry_point_stage_counts(plan),
        "graphicsStageClosure": _vulkan_graphics_stage_closure(plan),
        "entryPoints": [
            _summarize_vulkan_entry_point(record) for record in plan.entry_points
        ],
        "resources": [_summarize_vulkan_resource(record) for record in plan.resources],
        "targetResourceBindings": [
            _summarize_vulkan_resource_binding(record)
            for record in plan.target_resource_bindings
        ],
    }


def _vulkan_descriptor_diagnostics(
    plan: VulkanNativeLoaderPlan,
) -> list[dict[str, Any]]:
    return [
        diagnostic.to_summary()
        for diagnostic in plan.diagnostics
        if diagnostic.document == "nativeArtifactDescriptor"
        or diagnostic.artifact == NATIVE_ARTIFACT_DESCRIPTOR
    ]


def _vulkan_profile_diagnostics(
    plan: VulkanNativeLoaderPlan,
) -> list[dict[str, Any]]:
    return [
        diagnostic.to_summary()
        for diagnostic in plan.diagnostics
        if diagnostic.document == "nativeProfile"
        or diagnostic.artifact == VULKAN_NATIVE_PROFILE_ARTIFACT
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
    plan: VulkanNativeLoaderPlan,
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


def _has_diagnostic_code(plan: VulkanNativeLoaderPlan, code: str) -> bool:
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


def _summarize_vulkan_entry_point(record: dict[str, Any]) -> dict[str, Any]:
    return {
        "stage": record.get("stage"),
        "sourceName": record.get("sourceName"),
        "backendName": record.get("backendName"),
    }


def _vulkan_entry_point_stage_counts(
    plan: SourceFreeNativeBackendLoaderPlan,
) -> dict[str, int]:
    counts: dict[str, int] = {}
    for record in plan.entry_points:
        stage = record.get("stage")
        if isinstance(stage, str) and stage:
            counts[stage] = counts.get(stage, 0) + 1
    return counts


def _vulkan_graphics_stage_closure(
    plan: SourceFreeNativeBackendLoaderPlan,
) -> dict[str, Any]:
    stage_counts = _vulkan_entry_point_stage_counts(plan)
    vertex_entries = [
        _summarize_vulkan_entry_point(record)
        for record in plan.entry_points
        if record.get("stage") == "vertex"
    ]
    fragment_entries = [
        _summarize_vulkan_entry_point(record)
        for record in plan.entry_points
        if record.get("stage") == "fragment"
    ]
    graphics_package = bool(vertex_entries or fragment_entries)
    non_graphics_stages = sorted(
        stage
        for stage, count in stage_counts.items()
        if count > 0 and stage not in _VULKAN_GRAPHICS_STAGES
    )

    return {
        "graphicsPackage": graphics_package,
        "stageCounts": stage_counts,
        "vertexEntryPoint": vertex_entries[0] if len(vertex_entries) == 1 else None,
        "fragmentEntryPoint": (
            fragment_entries[0] if len(fragment_entries) == 1 else None
        ),
        "vertexEntryPointCount": len(vertex_entries),
        "fragmentEntryPointCount": len(fragment_entries),
        "hasVertexFragmentPair": len(vertex_entries) == 1
        and len(fragment_entries) == 1,
        "hasOnlyGraphicsStages": graphics_package and not non_graphics_stages,
        "nonGraphicsStages": non_graphics_stages,
    }


def _vulkan_graphics_stage_diagnostics(
    plan: SourceFreeNativeBackendLoaderPlan,
) -> tuple[CompatibilityDiagnostic, ...]:
    closure = _vulkan_graphics_stage_closure(plan)
    if not closure["graphicsPackage"]:
        return ()
    if closure["hasVertexFragmentPair"] and closure["hasOnlyGraphicsStages"]:
        return ()
    return (
        CompatibilityDiagnostic(
            code="vulkan_loader.graphics_entry_points_mismatch",
            message=(
                "Vulkan graphics native loader requires reflection.entryPoints "
                "to contain exactly one vertex entry point and one fragment "
                "entry point, with no compute entry points mixed into the "
                "graphics package"
            ),
            document="reflection",
            path="entryPoints",
            expected="exactly one vertex and one fragment entry point",
            actual=closure["stageCounts"],
        ),
    )


def _summarize_vulkan_resource(record: dict[str, Any]) -> dict[str, Any]:
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


def _summarize_vulkan_resource_binding(record: dict[str, Any]) -> dict[str, Any]:
    abi = record.get("abi")
    abi_summary = dict(abi) if isinstance(abi, dict) else {}
    set_value = record.get("set")
    if set_value is None:
        set_value = abi_summary.get("set")
    binding_value = record.get("binding")
    if binding_value is None:
        binding_value = abi_summary.get("binding")
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
        "abi": abi if isinstance(abi, str) else abi_summary,
        "set": set_value,
        "binding": binding_value,
        "storageClass": record.get("storageClass"),
        "spirvType": record.get("spirvType"),
    }
    if isinstance(abi, str):
        summary["abiKind"] = abi
    evidence_id = record.get("evidenceId")
    if isinstance(evidence_id, str) and evidence_id:
        summary["evidenceId"] = evidence_id
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


def _vulkan_profile_artifact_path(
    fields: dict[str, Any],
    artifact_name: str,
) -> str | None:
    value = fields.get(artifact_name)
    if isinstance(value, str):
        return value
    artifacts = fields.get("artifacts")
    if isinstance(artifacts, dict):
        value = artifacts.get(artifact_name)
        if isinstance(value, str):
            return value
    return None


def _vulkan_filtered_base_diagnostics(
    plan: SourceFreeNativeBackendLoaderPlan,
    native_profile: VulkanNativeProfilePlan | None,
) -> tuple[CompatibilityDiagnostic, ...]:
    return tuple(
        diagnostic
        for diagnostic in plan.diagnostics
        if not _vulkan_shared_profile_link_diagnostic_is_satisfied(
            plan,
            native_profile,
            diagnostic,
        )
    )


def _vulkan_shared_profile_link_diagnostic_is_satisfied(
    plan: SourceFreeNativeBackendLoaderPlan,
    native_profile: VulkanNativeProfilePlan | None,
    diagnostic: CompatibilityDiagnostic,
) -> bool:
    code_to_artifact = {
        "package.native_profile.backend_assembly_missing": (
            VULKAN_BACKEND_ASSEMBLY_ARTIFACT
        ),
        "package.native_profile.native_binary_missing": VULKAN_NATIVE_ARTIFACT,
    }
    artifact_name = code_to_artifact.get(diagnostic.code)
    if artifact_name is None or native_profile is None or not native_profile.readable:
        return False
    artifact = _available_artifact(plan, artifact_name)
    profile_path = _vulkan_profile_artifact_path(native_profile.fields, artifact_name)
    return artifact is not None and profile_path == artifact.package_path


def _vulkan_native_profile_plan(
    plan: SourceFreeNativeBackendLoaderPlan,
) -> VulkanNativeProfilePlan | None:
    artifact = _available_artifact(plan, VULKAN_NATIVE_PROFILE_ARTIFACT)
    if artifact is None:
        return None

    profile: object | None = None
    readable = False
    if artifact.exists:
        try:
            profile = json.loads(
                artifact.read_text(byte_limit=RUNTIME_METADATA_JSON_BYTE_LIMIT)
            )
            readable = isinstance(profile, dict)
        except (OSError, PackageReadError, UnicodeDecodeError, json.JSONDecodeError):
            profile = None

    fields: dict[str, Any] = {}
    if isinstance(profile, dict):
        fields = {
            name: profile[name]
            for name in _VULKAN_NATIVE_PROFILE_SUMMARY_FIELDS
            if name in profile
        }

    return VulkanNativeProfilePlan(
        artifact=artifact,
        readable=readable,
        fields=fields,
    )


def _vulkan_profile_disassembly(fields: dict[str, Any]) -> dict[str, Any] | None:
    debug = fields.get("debug")
    if not isinstance(debug, dict):
        return None
    disassembly = debug.get("disassembly")
    if not isinstance(disassembly, dict):
        return None
    return {
        "status": disassembly.get("status"),
        "path": disassembly.get("path"),
    }


def _descriptor_native_profile_evidence_path(
    descriptor: NativeArtifactDescriptorPlan | None,
) -> str | None:
    if descriptor is None or not descriptor.readable:
        return None
    evidence = descriptor.fields.get("optimizationEvidence")
    if not isinstance(evidence, dict):
        return None
    evidence_source = evidence.get("evidenceSource")
    if not isinstance(evidence_source, dict):
        return None
    if evidence_source.get("kind") != "native-profile":
        return None
    path = evidence_source.get("path")
    return path if isinstance(path, str) else None


def _available_artifact(
    plan: SourceFreeNativeBackendLoaderPlan,
    name: str,
) -> LoaderArtifactPlan | None:
    for artifact in plan.runtime_plan.compatibility_report.available_artifacts:
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
