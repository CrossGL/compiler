#!/usr/bin/env python3
"""Shared source-free native backend loader planning helpers.

This module validates the metadata boundary used by backend-specific native
runtime loader sketches. It never parses CrossGL source, invokes the compiler,
or touches a graphics API/device.
"""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path, PurePosixPath
from typing import Any

from .loader import (
    LoaderArtifactPlan,
    RuntimeLoaderPlan,
    SourceFreeRuntimeArtifactHandoff,
    read_loader_plan,
)
from .package_reader import (
    CompatibilityDiagnostic,
    NATIVE_ARTIFACT_BINARY_KINDS_BY_TARGET,
    PackageReadError,
    RUNTIME_METADATA_JSON_BYTE_LIMIT,
)


NATIVE_BACKEND_ARTIFACT = "nativeBinary"
NATIVE_ARTIFACT_DESCRIPTOR = "nativeArtifactDescriptor"
_CROSSGL_SOURCE_INPUT_SUFFIXES = frozenset((".cgl",))
_NATIVE_DESCRIPTOR_SUMMARY_FIELDS = (
    "schemaVersion",
    "contractVersion",
    "target",
    "binaryKind",
    "artifactPath",
    "artifactHash",
    "nativeBinaryStatus",
    "validationStatus",
    "optimizationLevel",
    "optimizationEvidence",
    "spirvDependencies",
    "sizeBytes",
)
_NATIVE_OPTIMIZATION_EVIDENCE_FIELDS = (
    "requestedLevel",
    "effectiveLevel",
    "policy",
    "status",
    "tool",
    "toolFlag",
    "evidenceSource",
    "debugInfo",
    "profile",
    "flags",
)


@dataclass(frozen=True)
class NativeArtifactDescriptorPlan:
    """Runtime-facing summary of a validated native artifact descriptor."""

    artifact: LoaderArtifactPlan
    readable: bool
    fields: dict[str, Any]
    source_path_declared: bool
    expected_binary_kinds: tuple[str, ...]

    @property
    def binary_kind(self) -> str | None:
        value = self.fields.get("binaryKind")
        return value if isinstance(value, str) else None

    @property
    def binary_kind_matches_loader(self) -> bool | None:
        if not self.readable or self.binary_kind is None:
            return None
        return self.binary_kind in self.expected_binary_kinds

    def to_summary(self) -> dict[str, Any]:
        return {
            "artifact": self.artifact.to_summary(),
            "readable": self.readable,
            "fields": dict(self.fields),
            "optimizationEvidence": _native_optimization_evidence_summary(
                self.fields,
            ),
            "sourcePathDeclared": self.source_path_declared,
            "expectedBinaryKinds": list(self.expected_binary_kinds),
            "binaryKindMatchesLoader": self.binary_kind_matches_loader,
        }


@dataclass(frozen=True)
class SourceFreeNativeBackendLoaderPlan:
    """Validated metadata-only handoff for a native backend runtime loader."""

    package_path: Path
    loader_name: str
    target: str
    runtime_plan: RuntimeLoaderPlan
    native_artifact: LoaderArtifactPlan | None
    native_artifact_descriptor: NativeArtifactDescriptorPlan | None
    entry_points: tuple[dict[str, Any], ...]
    resources: tuple[dict[str, Any], ...]
    target_resource_bindings: tuple[dict[str, Any], ...]
    target_resource_binding_metadata: tuple[dict[str, Any], ...]
    workgroup_sizes: tuple[dict[str, Any], ...]
    diagnostics: tuple[CompatibilityDiagnostic, ...]

    @property
    def ready(self) -> bool:
        return not self.reject_reasons and self.native_artifact is not None

    @property
    def planned(self) -> bool:
        return self.ready

    @property
    def loadable(self) -> bool:
        return self.ready

    @property
    def status(self) -> str:
        return "ready" if self.ready else "rejected"

    @property
    def source_parsing_required(self) -> bool:
        return False

    @property
    def device_execution_required(self) -> bool:
        return False

    @property
    def reject_reasons(self) -> tuple[CompatibilityDiagnostic, ...]:
        return tuple(
            diagnostic
            for diagnostic in self.diagnostics
            if diagnostic.severity in {"error", "skip"}
        )

    def require_ready(self) -> "SourceFreeNativeBackendLoaderPlan":
        if self.ready:
            return self
        messages = "; ".join(diagnostic.message for diagnostic in self.reject_reasons)
        if not messages:
            messages = f"{self.loader_name} loader plan is not ready"
        raise PackageReadError(f"{self.loader_name} loader plan rejected: {messages}")

    def require_runtime_artifact_handoff(
        self,
        *,
        byte_limit: int | None = None,
    ) -> SourceFreeRuntimeArtifactHandoff:
        self.require_ready()
        handoff = self.runtime_plan.require_runtime_artifact_handoff(
            byte_limit=byte_limit,
        )
        if (
            self.native_artifact is not None
            and handoff.artifact_name != self.native_artifact.name
        ):
            raise PackageReadError(
                f"{self.loader_name} loader selected artifact mismatch: "
                f"{handoff.artifact_name} != {self.native_artifact.name}"
            )
        return handoff

    @property
    def native_admission_summary(self) -> dict[str, Any]:
        return _native_admission_summary(self)

    def to_summary(self) -> dict[str, Any]:
        return {
            "schemaVersion": 1,
            "loader": self.loader_name,
            "target": self.target,
            "status": self.status,
            "ready": self.ready,
            "planned": self.planned,
            "loadable": self.loadable,
            "sourceParsingRequired": self.source_parsing_required,
            "compilerInvocationRequired": False,
            "deviceExecutionRequired": self.device_execution_required,
            "packagePath": str(self.package_path),
            "packageTarget": self.runtime_plan.package_target,
            "packageArtifactRequirementsSource": (
                self.runtime_plan.package_artifact_requirements_source
            ),
            "packageArtifactRequirements": (
                self.runtime_plan.package_artifact_requirements
            ),
            "targetLegalizationEvidence": (
                self.runtime_plan.compatibility_report.target_legalization_evidence
            ),
            "targetLegalizationToolRequirements": (
                self.runtime_plan.compatibility_report.target_legalization_tool_requirements
            ),
            "nativeArtifact": (
                self.native_artifact.to_summary()
                if self.native_artifact is not None
                else None
            ),
            "nativeArtifactDescriptor": (
                self.native_artifact_descriptor.to_summary()
                if self.native_artifact_descriptor is not None
                else None
            ),
            "nativeAdmission": self.native_admission_summary,
            "artifactInputs": [
                artifact.to_summary()
                for artifact in self.runtime_plan.selected_artifacts
            ],
            "reflection": {
                "entryPointCount": len(self.entry_points),
                "resourceCount": len(self.resources),
                "targetResourceBindingCount": len(self.target_resource_bindings),
                "targetResourceBindingMetadataCount": len(
                    self.target_resource_binding_metadata
                ),
                "workgroupSizeCount": len(self.workgroup_sizes),
                "entryPoints": list(self.entry_points),
                "resources": list(self.resources),
                "targetResourceBindings": list(self.target_resource_bindings),
                "targetResourceBindingMetadata": list(
                    self.target_resource_binding_metadata
                ),
                "workgroupSizes": list(self.workgroup_sizes),
            },
            "targetResourceBindingMetadata": (
                self.runtime_plan.target_resource_binding_metadata_summary
            ),
            "graphicsDescriptorBindings": (
                self.runtime_plan.compatibility_report.graphics_descriptor_bindings
            ),
            "graphicsAbiReflectionParity": _graphics_abi_reflection_parity_summary(
                self.runtime_plan,
                target=self.target,
                target_resource_bindings=self.target_resource_bindings,
            ),
            "sourceInputs": [],
            "runtimePlan": self.runtime_plan.to_summary(),
            "rejectReasons": [
                diagnostic.to_summary() for diagnostic in self.reject_reasons
            ],
            "diagnostics": [diagnostic.to_summary() for diagnostic in self.diagnostics],
        }


def plan_source_free_native_backend_loader(
    package_path: Path | str,
    target: str,
    *,
    loader_name: str | None = None,
) -> SourceFreeNativeBackendLoaderPlan:
    """Return a source-free native backend loader validation plan."""
    if not isinstance(target, str) or not target:
        raise PackageReadError("target must be a non-empty string")

    package_root = Path(package_path)
    resolved_loader_name = loader_name or f"{target}-native"
    runtime_plan = read_loader_plan(
        package_root,
        target,
        package_mode="native",
    )
    diagnostics = list(runtime_plan.diagnostics)
    native_artifact = runtime_plan.artifact(NATIVE_BACKEND_ARTIFACT)
    native_artifact_descriptor = _native_artifact_descriptor_plan(
        runtime_plan,
        target,
    )
    entry_points = _reflection_records(runtime_plan, "entryPoints")
    resources = _reflection_records(runtime_plan, "resources")
    target_resource_bindings = _target_resource_bindings(runtime_plan, target)
    target_resource_binding_metadata = (
        runtime_plan.target_resource_binding_metadata_records(target=target)
    )
    workgroup_sizes = runtime_plan.workgroup_sizes

    diagnostics.extend(
        _native_backend_loader_boundary_diagnostics(
            runtime_plan,
            target=target,
            native_artifact=native_artifact,
            native_artifact_descriptor=native_artifact_descriptor,
            entry_points=entry_points,
            resources=resources,
            target_resource_bindings=target_resource_bindings,
            target_resource_binding_metadata=target_resource_binding_metadata,
        )
    )

    if _has_blocking_diagnostics(diagnostics):
        native_artifact = None

    return SourceFreeNativeBackendLoaderPlan(
        package_path=package_root,
        loader_name=resolved_loader_name,
        target=target,
        runtime_plan=runtime_plan,
        native_artifact=native_artifact,
        native_artifact_descriptor=native_artifact_descriptor,
        entry_points=entry_points,
        resources=resources,
        target_resource_bindings=target_resource_bindings,
        target_resource_binding_metadata=target_resource_binding_metadata,
        workgroup_sizes=workgroup_sizes,
        diagnostics=tuple(diagnostics),
    )


def _native_backend_loader_boundary_diagnostics(
    runtime_plan: RuntimeLoaderPlan,
    *,
    target: str,
    native_artifact: LoaderArtifactPlan | None,
    native_artifact_descriptor: NativeArtifactDescriptorPlan | None,
    entry_points: tuple[dict[str, Any], ...],
    resources: tuple[dict[str, Any], ...],
    target_resource_bindings: tuple[dict[str, Any], ...],
    target_resource_binding_metadata: tuple[dict[str, Any], ...],
) -> tuple[CompatibilityDiagnostic, ...]:
    diagnostics: list[CompatibilityDiagnostic] = list(
        _native_artifact_descriptor_admission_diagnostics(
            runtime_plan,
            target=target,
            native_artifact=native_artifact,
            native_artifact_descriptor=native_artifact_descriptor,
        )
    )
    if _has_blocking_diagnostics(runtime_plan.diagnostics):
        return tuple(diagnostics)

    if runtime_plan.package_target != target:
        diagnostics.append(
            CompatibilityDiagnostic(
                code=f"{target}_loader.package_target_mismatch",
                message=f"{target} native loader requires a package targeted at {target}",
                severity="skip",
                document="manifest",
                expected=target,
                actual=runtime_plan.package_target,
            )
        )

    if native_artifact is None:
        diagnostics.append(
            CompatibilityDiagnostic(
                code=f"{target}_loader.native_artifact_missing",
                message=(
                    f"{target} native loader requires manifest.artifacts.nativeBinary"
                ),
                document="manifest",
                artifact=NATIVE_BACKEND_ARTIFACT,
                expected="declared nativeBinary artifact",
                actual="missing",
            )
        )
    elif not native_artifact.exists:
        diagnostics.append(
            CompatibilityDiagnostic(
                code=f"{target}_loader.native_artifact_file_missing",
                message=(
                    f"{target} native loader requires an existing nativeBinary "
                    "artifact file"
                ),
                document="manifest",
                artifact=NATIVE_BACKEND_ARTIFACT,
                path=native_artifact.package_path,
                expected=f"existing {target} native artifact",
                actual="missing",
            )
        )
    elif _is_crossgl_source_input_path(native_artifact.package_path):
        diagnostics.append(
            CompatibilityDiagnostic(
                code=f"{target}_loader.native_artifact_source_input",
                message=(
                    f"{target} native loader nativeBinary must not point at a "
                    "CrossGL source input"
                ),
                document="manifest",
                artifact=NATIVE_BACKEND_ARTIFACT,
                path=native_artifact.package_path,
                expected=f"native {target} package artifact",
                actual=native_artifact.package_path,
            )
        )

    if (
        native_artifact_descriptor is not None
        and native_artifact_descriptor.binary_kind_matches_loader is False
    ):
        diagnostics.append(
            CompatibilityDiagnostic(
                code=f"{target}_loader.native_artifact_descriptor_binary_kind_mismatch",
                message=(
                    f"{target} native loader requires a native artifact "
                    "descriptor binaryKind owned by the loader target"
                ),
                document="nativeArtifactDescriptor",
                artifact=NATIVE_ARTIFACT_DESCRIPTOR,
                path="binaryKind",
                expected=list(native_artifact_descriptor.expected_binary_kinds),
                actual=native_artifact_descriptor.binary_kind,
            )
        )

    for artifact in runtime_plan.selected_artifacts:
        if not _is_crossgl_source_input_path(artifact.package_path):
            continue
        diagnostics.append(
            CompatibilityDiagnostic(
                code=f"{target}_loader.source_input_rejected",
                message=(
                    f"{target} native loader plans must not consume CrossGL "
                    "source inputs"
                ),
                document="manifest",
                artifact=artifact.name,
                path=artifact.package_path,
                expected="generated package artifact",
                actual=artifact.package_path,
            )
        )

    if not entry_points:
        diagnostics.append(
            CompatibilityDiagnostic(
                code=f"{target}_loader.reflection.entry_points_missing",
                message=f"{target} native loader requires reflected entry points",
                document="reflection",
                path="entryPoints",
                expected="non-empty array",
                actual="empty",
            )
        )
    if not resources:
        diagnostics.append(
            CompatibilityDiagnostic(
                code=f"{target}_loader.reflection.resources_missing",
                message=f"{target} native loader requires reflected resources",
                document="reflection",
                path="resources",
                expected="non-empty array",
                actual="empty",
            )
        )
    if not target_resource_bindings:
        diagnostics.append(
            CompatibilityDiagnostic(
                code=f"{target}_loader.reflection.target_bindings_missing",
                message=(
                    f"{target} native loader requires reflected target resource "
                    f"bindings for {target}"
                ),
                document="reflection",
                path="targetResourceBindings",
                expected=f"non-empty {target} binding array",
                actual="empty",
            )
        )
    else:
        diagnostics.extend(
            _target_resource_binding_drift_diagnostics(
                target=target,
                resources=resources,
                target_resource_bindings=target_resource_bindings,
            )
        )

    diagnostics.extend(
        _target_resource_binding_metadata_drift_diagnostics(
            target=target,
            target_resource_bindings=target_resource_bindings,
            target_resource_binding_metadata=target_resource_binding_metadata,
        )
    )

    return tuple(diagnostics)


def _native_artifact_descriptor_admission_diagnostics(
    runtime_plan: RuntimeLoaderPlan,
    *,
    target: str,
    native_artifact: LoaderArtifactPlan | None,
    native_artifact_descriptor: NativeArtifactDescriptorPlan | None,
) -> tuple[CompatibilityDiagnostic, ...]:
    if native_artifact_descriptor is None:
        if _native_runtime_plan_requires_descriptor(runtime_plan):
            return (
                CompatibilityDiagnostic(
                    code=f"{target}_loader.native_artifact_descriptor_not_declared",
                    message=(
                        f"{target} native loader requires "
                        "manifest.artifacts.nativeArtifactDescriptor for native "
                        "binary admission"
                    ),
                    document="manifest",
                    artifact=NATIVE_ARTIFACT_DESCRIPTOR,
                    path=f"artifacts.{NATIVE_ARTIFACT_DESCRIPTOR}",
                    expected="declared nativeArtifactDescriptor metadata",
                    actual="missing",
                ),
            )
        return ()

    diagnostics: list[CompatibilityDiagnostic] = []
    descriptor_artifact = native_artifact_descriptor.artifact
    if not descriptor_artifact.exists:
        diagnostics.append(
            CompatibilityDiagnostic(
                code=f"{target}_loader.native_artifact_descriptor_missing",
                message=(
                    f"{target} native loader requires the manifest-declared "
                    "nativeArtifactDescriptor file to exist"
                ),
                document="manifest",
                artifact=NATIVE_ARTIFACT_DESCRIPTOR,
                path=descriptor_artifact.package_path,
                expected="existing nativeArtifactDescriptor JSON object",
                actual="missing",
            )
        )
        return tuple(diagnostics)

    if not native_artifact_descriptor.readable:
        diagnostics.append(
            CompatibilityDiagnostic(
                code=f"{target}_loader.native_artifact_descriptor_unreadable",
                message=(
                    f"{target} native loader requires the manifest-declared "
                    "nativeArtifactDescriptor to be readable JSON object metadata"
                ),
                document="nativeArtifactDescriptor",
                artifact=NATIVE_ARTIFACT_DESCRIPTOR,
                path=descriptor_artifact.package_path,
                expected="readable JSON object",
                actual="unreadable",
            )
        )
        return tuple(diagnostics)

    fields = native_artifact_descriptor.fields
    descriptor_target = fields.get("target")
    if descriptor_target != target:
        diagnostics.append(
            CompatibilityDiagnostic(
                code=f"{target}_loader.native_artifact_descriptor_target_mismatch",
                message=(
                    f"{target} native loader requires nativeArtifactDescriptor.target "
                    "to match the loader target"
                ),
                document="nativeArtifactDescriptor",
                artifact=NATIVE_ARTIFACT_DESCRIPTOR,
                path="target",
                expected=target,
                actual=descriptor_target,
            )
        )

    descriptor_artifact_path = fields.get("artifactPath")
    if (
        native_artifact is not None
        and descriptor_artifact_path != native_artifact.package_path
    ):
        diagnostics.append(
            CompatibilityDiagnostic(
                code=(
                    f"{target}_loader.native_artifact_descriptor_artifact_path_mismatch"
                ),
                message=(
                    f"{target} native loader requires "
                    "nativeArtifactDescriptor.artifactPath to match the selected "
                    "nativeBinary artifact"
                ),
                document="nativeArtifactDescriptor",
                artifact=NATIVE_ARTIFACT_DESCRIPTOR,
                path="artifactPath",
                expected=native_artifact.package_path,
                actual=descriptor_artifact_path,
            )
        )

    native_binary_status = runtime_plan.compatibility_report.native_binary_status
    descriptor_native_status = fields.get("nativeBinaryStatus")
    if native_binary_status is None:
        if descriptor_native_status is not None:
            diagnostics.append(
                CompatibilityDiagnostic(
                    code=(
                        f"{target}_loader."
                        "native_artifact_descriptor_native_binary_status_mismatch"
                    ),
                    message=(
                        f"{target} native loader requires "
                        "nativeArtifactDescriptor.nativeBinaryStatus to be absent "
                        "when manifest.artifacts.nativeBinaryStatus is absent"
                    ),
                    document="nativeArtifactDescriptor",
                    artifact=NATIVE_ARTIFACT_DESCRIPTOR,
                    path="nativeBinaryStatus",
                    expected=None,
                    actual=descriptor_native_status,
                )
            )
    elif descriptor_native_status != native_binary_status:
        diagnostics.append(
            CompatibilityDiagnostic(
                code=(
                    f"{target}_loader."
                    "native_artifact_descriptor_native_binary_status_mismatch"
                ),
                message=(
                    f"{target} native loader requires "
                    "nativeArtifactDescriptor.nativeBinaryStatus to match "
                    "manifest.artifacts.nativeBinaryStatus"
                ),
                document="nativeArtifactDescriptor",
                artifact=NATIVE_ARTIFACT_DESCRIPTOR,
                path="nativeBinaryStatus",
                expected=native_binary_status,
                actual=descriptor_native_status,
            )
        )

    validation_status = fields.get("validationStatus")
    target_contract = runtime_plan.compatibility_report.target_contract
    if (
        target_contract is not None
        and target_contract.native_binary_status_required
        and native_binary_status == "validated"
        and validation_status != "validated"
    ):
        diagnostics.append(
            CompatibilityDiagnostic(
                code=(
                    f"{target}_loader."
                    "native_artifact_descriptor_validation_status_mismatch"
                ),
                message=(
                    f"{target} native loader requires "
                    "nativeArtifactDescriptor.validationStatus=validated when "
                    "target policy requires validated nativeBinaryStatus metadata"
                ),
                document="nativeArtifactDescriptor",
                artifact=NATIVE_ARTIFACT_DESCRIPTOR,
                path="validationStatus",
                expected="validated",
                actual=validation_status,
            )
        )

    descriptor_size = fields.get("sizeBytes")
    if (
        native_artifact is not None
        and native_artifact.size is not None
        and "sizeBytes" in fields
        and descriptor_size != native_artifact.size
    ):
        diagnostics.append(
            CompatibilityDiagnostic(
                code=f"{target}_loader.native_artifact_descriptor_size_bytes_mismatch",
                message=(
                    f"{target} native loader requires "
                    "nativeArtifactDescriptor.sizeBytes to match the selected "
                    "nativeBinary artifact size"
                ),
                document="nativeArtifactDescriptor",
                artifact=NATIVE_ARTIFACT_DESCRIPTOR,
                path="sizeBytes",
                expected=native_artifact.size,
                actual=descriptor_size,
            )
        )

    return tuple(diagnostics)


def _native_runtime_plan_requires_descriptor(
    runtime_plan: RuntimeLoaderPlan,
) -> bool:
    contract = runtime_plan.compatibility_report.target_contract
    if contract is None:
        return False
    native_availability = runtime_plan.compatibility_report.artifact_availability[
        "native"
    ]
    return bool(native_availability["usable"])


def _native_artifact_descriptor_plan(
    runtime_plan: RuntimeLoaderPlan,
    target: str,
) -> NativeArtifactDescriptorPlan | None:
    artifact = _available_artifact(runtime_plan, NATIVE_ARTIFACT_DESCRIPTOR)
    if artifact is None:
        return None

    descriptor: object | None = None
    readable = False
    if artifact.exists:
        try:
            descriptor = json.loads(
                artifact.read_text(byte_limit=RUNTIME_METADATA_JSON_BYTE_LIMIT)
            )
            readable = isinstance(descriptor, dict)
        except (OSError, PackageReadError, UnicodeDecodeError, json.JSONDecodeError):
            descriptor = None

    fields: dict[str, Any] = {}
    if isinstance(descriptor, dict):
        fields = {
            name: descriptor[name]
            for name in _NATIVE_DESCRIPTOR_SUMMARY_FIELDS
            if name in descriptor
        }

    return NativeArtifactDescriptorPlan(
        artifact=artifact,
        readable=readable,
        fields=fields,
        source_path_declared=isinstance(descriptor, dict)
        and "sourcePath" in descriptor,
        expected_binary_kinds=NATIVE_ARTIFACT_BINARY_KINDS_BY_TARGET.get(
            target,
            (),
        ),
    )


def _native_admission_summary(
    plan: SourceFreeNativeBackendLoaderPlan,
) -> dict[str, Any]:
    blocking_reason = _first_blocking_diagnostic(plan.diagnostics)
    artifact_admission = _native_artifact_admission_summary(plan, blocking_reason)
    descriptor_admission = _native_descriptor_admission_summary(plan)
    runtime_selection_admission = _runtime_selection_admission(plan.runtime_plan)

    return {
        "schemaVersion": 1,
        "decision": "accepted" if plan.ready else "rejected",
        "status": "ready" if plan.ready else "rejected",
        "reason": (
            "runtime.native_backend_loader.accepted"
            if plan.ready
            else blocking_reason.code
            if blocking_reason is not None
            else None
        ),
        "target": plan.target,
        "packageTarget": plan.runtime_plan.package_target,
        "sourceParsingRequired": plan.source_parsing_required,
        "compilerInvocationRequired": False,
        "deviceExecutionRequired": plan.device_execution_required,
        "packageArtifactRequirementsSource": (
            plan.runtime_plan.package_artifact_requirements_source
        ),
        "packageArtifactRequirements": (
            plan.runtime_plan.package_artifact_requirements
        ),
        "targetLegalizationEvidence": (
            plan.runtime_plan.compatibility_report.target_legalization_evidence
        ),
        "targetLegalizationToolRequirements": (
            plan.runtime_plan.compatibility_report.target_legalization_tool_requirements
        ),
        "nativeArtifact": artifact_admission,
        "nativeArtifactDescriptor": descriptor_admission,
        "targetResourceBindingMetadata": (
            _target_resource_binding_metadata_admission_summary(plan)
        ),
        "graphicsAbiReflectionParity": _graphics_abi_reflection_parity_summary(
            plan.runtime_plan,
            target=plan.target,
            target_resource_bindings=plan.target_resource_bindings,
        ),
        "runtimeSelection": {
            "requestedPackageMode": (
                plan.runtime_plan.runtime_artifact_selection.requested_package_mode
            ),
            "selectedPackageMode": (
                plan.runtime_plan.runtime_artifact_selection.selected_package_mode
            ),
            "selected": plan.runtime_plan.runtime_artifact_selection.selected,
            "native": runtime_selection_admission.get("native"),
            "sourcePackageFallback": runtime_selection_admission.get(
                "sourcePackageFallback",
            ),
        },
        "blockedByDiagnostics": [
            diagnostic.to_summary()
            for diagnostic in plan.diagnostics
            if diagnostic.severity in {"error", "skip"}
        ],
    }


def _native_artifact_admission_summary(
    plan: SourceFreeNativeBackendLoaderPlan,
    blocking_reason: CompatibilityDiagnostic | None,
) -> dict[str, Any]:
    compatibility = _artifact_compatibility_record(
        plan.runtime_plan,
        NATIVE_BACKEND_ARTIFACT,
    )
    role = _artifact_role_record(plan.runtime_plan, NATIVE_BACKEND_ARTIFACT)
    selection_native = _runtime_selection_admission(plan.runtime_plan).get("native")
    source_fallback = _runtime_selection_admission(plan.runtime_plan).get(
        "sourcePackageFallback",
    )
    native_status = plan.runtime_plan.compatibility_report.artifact_availability[
        "native"
    ].get(
        "nativeBinaryStatus",
    )
    category = _native_artifact_admission_category(
        plan=plan,
        blocking_reason=blocking_reason,
        selection_native=selection_native,
        source_fallback=source_fallback,
    )

    reason = "runtime.native_artifact.accepted"
    message = "nativeBinary is accepted for native backend loading"
    if not plan.ready:
        reason = _native_artifact_rejection_reason(
            blocking_reason=blocking_reason,
            selection_native=selection_native,
            compatibility=compatibility,
        )
        message = (
            blocking_reason.message
            if blocking_reason is not None
            else "nativeBinary is not accepted for native backend loading"
        )

    return {
        "decision": "accepted" if plan.ready else "rejected",
        "status": category,
        "reason": reason,
        "message": message,
        "declared": bool(role.get("declared"))
        if role is not None
        else compatibility is not None,
        "available": bool(role.get("exists"))
        if role is not None
        else bool(compatibility.get("exists"))
        if compatibility is not None
        else False,
        "selectedForRuntime": bool(role.get("selectedForRuntime"))
        if role is not None
        else bool(compatibility.get("selected"))
        if compatibility is not None
        else False,
        "bytesRequired": bool(role.get("bytesRequired")) if role is not None else False,
        "compatible": bool(role.get("compatible")) if role is not None else plan.ready,
        "path": role.get("path")
        if role is not None
        else compatibility.get("path")
        if compatibility is not None
        else None,
        "nativeBinaryStatus": native_status,
        "artifact": (
            plan.native_artifact.to_summary()
            if plan.native_artifact is not None
            else None
        ),
        "compatibility": compatibility,
        "roleCompatibility": role,
        "diagnostics": [
            diagnostic.to_summary()
            for diagnostic in plan.diagnostics
            if _diagnostic_matches_native_artifact(diagnostic)
        ],
    }


def _native_descriptor_admission_summary(
    plan: SourceFreeNativeBackendLoaderPlan,
) -> dict[str, Any]:
    descriptor = plan.native_artifact_descriptor
    diagnostics = tuple(
        diagnostic
        for diagnostic in plan.diagnostics
        if diagnostic.document == "nativeArtifactDescriptor"
        or diagnostic.artifact == NATIVE_ARTIFACT_DESCRIPTOR
    )
    blocking_reason = _first_blocking_diagnostic(diagnostics)

    if descriptor is None:
        return {
            "decision": "missing",
            "status": "descriptor-not-declared",
            "reason": "runtime.native_artifact_descriptor.not_declared",
            "message": "nativeArtifactDescriptor is not declared by the package",
            "declared": False,
            "readable": False,
            "compatible": None,
            "binaryKind": None,
            "expectedBinaryKinds": list(
                NATIVE_ARTIFACT_BINARY_KINDS_BY_TARGET.get(plan.target, ()),
            ),
            "binaryKindMatchesLoader": None,
            "artifact": None,
            "fields": {},
            "optimizationEvidence": None,
            "sourcePathDeclared": False,
            "diagnostics": [diagnostic.to_summary() for diagnostic in diagnostics],
        }

    compatible = (
        descriptor.readable
        and descriptor.binary_kind_matches_loader is True
        and blocking_reason is None
    )
    if compatible:
        decision = "accepted"
        status = "accepted-native-artifact-descriptor"
        reason = "runtime.native_artifact_descriptor.accepted"
        message = "nativeArtifactDescriptor is compatible with the loader target"
    else:
        decision = "rejected"
        status = "descriptor-incompatible"
        reason = (
            blocking_reason.code
            if blocking_reason is not None
            else "runtime.native_artifact_descriptor.unreadable"
            if not descriptor.readable
            else "runtime.native_artifact_descriptor.binary_kind_mismatch"
        )
        message = (
            blocking_reason.message
            if blocking_reason is not None
            else "nativeArtifactDescriptor is not compatible with the loader target"
        )

    return {
        "decision": decision,
        "status": status,
        "reason": reason,
        "message": message,
        "declared": True,
        "readable": descriptor.readable,
        "compatible": compatible,
        "binaryKind": descriptor.binary_kind,
        "expectedBinaryKinds": list(descriptor.expected_binary_kinds),
        "binaryKindMatchesLoader": descriptor.binary_kind_matches_loader,
        "artifact": descriptor.artifact.to_summary(),
        "fields": dict(descriptor.fields),
        "optimizationEvidence": _native_optimization_evidence_summary(
            descriptor.fields,
        ),
        "sourcePathDeclared": descriptor.source_path_declared,
        "diagnostics": [diagnostic.to_summary() for diagnostic in diagnostics],
    }


def _native_artifact_admission_category(
    *,
    plan: SourceFreeNativeBackendLoaderPlan,
    blocking_reason: CompatibilityDiagnostic | None,
    selection_native: object,
    source_fallback: object,
) -> str:
    if plan.ready:
        return "accepted-native-artifact"
    if blocking_reason is not None:
        if blocking_reason.code == "package.target.loader_mismatch":
            return "target-incompatible-sidecar"
        if blocking_reason.artifact == NATIVE_ARTIFACT_DESCRIPTOR:
            return "descriptor-incompatible"
        if blocking_reason.document == "nativeArtifactDescriptor":
            return "descriptor-incompatible"
        if blocking_reason.artifact == "nativeBinaryStatus":
            return "planned-native-metadata"
        if (
            blocking_reason.artifact == NATIVE_BACKEND_ARTIFACT
            and blocking_reason.actual == "missing"
        ):
            return "missing-native-artifact"
        if blocking_reason.code in {
            "package.artifact.required_missing",
            "package.artifact.required_file_missing",
            "package.artifact.selection_missing",
            "package.artifact.selection_file_missing",
        }:
            return "missing-native-artifact"
        if blocking_reason.code == "package.mode.unsupported":
            return "source-package-fallback-rejected"

    if isinstance(selection_native, dict):
        native_category = selection_native.get("category")
        if native_category == "native-planned-only":
            return "source-package-fallback-rejected"
        if native_category == "native-not-requested":
            return "native-not-requested"

    if isinstance(source_fallback, dict) and source_fallback.get("fallbackAllowed"):
        return "source-package-fallback-rejected"

    return "native-artifact-rejected"


def _native_artifact_rejection_reason(
    *,
    blocking_reason: CompatibilityDiagnostic | None,
    selection_native: object,
    compatibility: dict[str, Any] | None,
) -> str | None:
    if blocking_reason is not None:
        return blocking_reason.code
    if isinstance(selection_native, dict) and isinstance(
        selection_native.get("reason"),
        str,
    ):
        return selection_native["reason"]
    if compatibility is not None and isinstance(compatibility.get("reason"), str):
        return compatibility["reason"]
    return None


def _native_optimization_evidence_summary(
    fields: dict[str, Any],
) -> dict[str, Any] | None:
    if "optimizationEvidence" not in fields:
        return None

    evidence = fields.get("optimizationEvidence")
    if not isinstance(evidence, dict):
        return {
            "present": True,
            "wellFormed": False,
            "status": None,
        }

    summary: dict[str, Any] = {
        "present": True,
        "wellFormed": True,
    }
    for key in _NATIVE_OPTIMIZATION_EVIDENCE_FIELDS:
        if key not in evidence:
            continue
        value = evidence[key]
        if key == "evidenceSource":
            source = _optimizer_evidence_source_summary(value)
            if source is not None:
                summary[key] = source
            continue
        if key == "flags":
            flags = _string_list_summary(value)
            if flags is not None:
                summary[key] = flags
            continue
        if isinstance(value, str) or isinstance(value, bool):
            summary[key] = value
    return summary


def _optimizer_evidence_source_summary(value: Any) -> dict[str, str] | None:
    if not isinstance(value, dict):
        return None
    summary: dict[str, str] = {}
    for key in ("kind", "path"):
        field_value = value.get(key)
        if isinstance(field_value, str):
            summary[key] = field_value
    return summary or None


def _string_list_summary(value: Any) -> list[str] | None:
    if not isinstance(value, list):
        return None
    return [item for item in value if isinstance(item, str)]


def _runtime_selection_admission(
    runtime_plan: RuntimeLoaderPlan,
) -> dict[str, Any]:
    admission = runtime_plan.runtime_artifact_selection.admission
    return admission if isinstance(admission, dict) else {}


def _artifact_compatibility_record(
    runtime_plan: RuntimeLoaderPlan,
    artifact_name: str,
) -> dict[str, Any] | None:
    for record in runtime_plan.artifact_compatibility_summary["artifacts"]:
        if record.get("name") == artifact_name:
            return record
    return None


def _artifact_role_record(
    runtime_plan: RuntimeLoaderPlan,
    role_name: str,
) -> dict[str, Any] | None:
    for record in runtime_plan.artifact_role_compatibility["roles"]:
        if record.get("role") == role_name:
            return record
    return None


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


def _diagnostic_matches_native_artifact(
    diagnostic: CompatibilityDiagnostic,
) -> bool:
    return diagnostic.artifact in {
        NATIVE_BACKEND_ARTIFACT,
        "nativeBinaryStatus",
    }


def _available_artifact(
    runtime_plan: RuntimeLoaderPlan,
    name: str,
) -> LoaderArtifactPlan | None:
    for artifact in runtime_plan.compatibility_report.available_artifacts:
        if artifact.name == name:
            return LoaderArtifactPlan.from_artifact(artifact)
    return None


def _reflection_records(
    runtime_plan: RuntimeLoaderPlan,
    key: str,
) -> tuple[dict[str, Any], ...]:
    records = runtime_plan.compatibility_report.reflection.get(key, [])
    if not isinstance(records, list):
        return ()
    return tuple(record for record in records if isinstance(record, dict))


def _target_resource_bindings(
    runtime_plan: RuntimeLoaderPlan,
    target: str,
) -> tuple[dict[str, Any], ...]:
    return tuple(
        record
        for record in _reflection_records(runtime_plan, "targetResourceBindings")
        if record.get("target") == target
    )


def _target_resource_binding_drift_diagnostics(
    *,
    target: str,
    resources: tuple[dict[str, Any], ...],
    target_resource_bindings: tuple[dict[str, Any], ...],
) -> tuple[CompatibilityDiagnostic, ...]:
    source_resource_keys = {
        key
        for resource in resources
        if (key := _reflection_resource_key(resource)) is not None
    }
    target_binding_keys = {
        key
        for binding in target_resource_bindings
        if (key := _reflection_resource_key(binding)) is not None
    }

    diagnostics: list[CompatibilityDiagnostic] = []
    missing_binding_keys = source_resource_keys - target_binding_keys
    for stage, name, kind in sorted(missing_binding_keys):
        diagnostics.append(
            CompatibilityDiagnostic(
                code=f"{target}_loader.reflection.resource_target_binding_missing",
                message=(
                    f"{target} native loader requires every reflected resource "
                    "to have a selected-target resource binding"
                ),
                document="reflection",
                path="targetResourceBindings",
                expected={
                    "target": target,
                    "stage": stage,
                    "name": name,
                    "kind": kind,
                },
                actual="missing",
            )
        )

    stale_binding_keys = target_binding_keys - source_resource_keys
    for stage, name, kind in sorted(stale_binding_keys):
        diagnostics.append(
            CompatibilityDiagnostic(
                code=f"{target}_loader.reflection.target_binding_source_missing",
                message=(
                    f"{target} native loader requires every selected-target "
                    "resource binding to match a reflected source resource"
                ),
                document="reflection",
                path="resources",
                expected={
                    "stage": stage,
                    "name": name,
                    "kind": kind,
                },
                actual="missing",
            )
        )

    return tuple(diagnostics)


def _target_resource_binding_metadata_admission_summary(
    plan: SourceFreeNativeBackendLoaderPlan,
) -> dict[str, Any]:
    parity = _target_resource_binding_metadata_parity(
        target=plan.target,
        target_resource_bindings=plan.target_resource_bindings,
        target_resource_binding_metadata=plan.target_resource_binding_metadata,
    )
    diagnostics = [
        diagnostic.to_summary()
        for diagnostic in plan.diagnostics
        if _diagnostic_matches_target_binding_metadata(diagnostic)
    ]
    blocking_diagnostics = [
        diagnostic
        for diagnostic in diagnostics
        if diagnostic.get("severity") in {"error", "skip"}
    ]
    identity_matches = parity["identityMatches"]
    if identity_matches is True and not blocking_diagnostics:
        decision = "accepted"
        status = "matched"
        reason = "runtime.target_resource_binding_metadata.accepted"
        message = "target resource binding metadata matches selected bindings"
    else:
        decision = "rejected"
        status = "mismatched" if identity_matches is False else "not-checkable"
        reason = (
            blocking_diagnostics[0]["code"]
            if blocking_diagnostics
            else "runtime.target_resource_binding_metadata.mismatched"
        )
        message = (
            blocking_diagnostics[0]["message"]
            if blocking_diagnostics
            else "target resource binding metadata does not match selected bindings"
        )

    return {
        "schemaVersion": 1,
        "decision": decision,
        "status": status,
        "reason": reason,
        "message": message,
        "target": plan.target,
        "targetResourceBindingCount": len(plan.target_resource_bindings),
        "metadataBindingCount": len(plan.target_resource_binding_metadata),
        "identityMatches": identity_matches,
        "missingMetadataBindingCount": len(parity["missingMetadataBindings"]),
        "staleMetadataBindingCount": len(parity["staleMetadataBindings"]),
        "missingMetadataBindings": parity["missingMetadataBindings"],
        "staleMetadataBindings": parity["staleMetadataBindings"],
        "diagnosticCodes": [
            diagnostic["code"]
            for diagnostic in diagnostics
            if isinstance(diagnostic.get("code"), str)
        ],
        "diagnostics": diagnostics,
    }


def _target_resource_binding_metadata_drift_diagnostics(
    *,
    target: str,
    target_resource_bindings: tuple[dict[str, Any], ...],
    target_resource_binding_metadata: tuple[dict[str, Any], ...],
) -> tuple[CompatibilityDiagnostic, ...]:
    parity = _target_resource_binding_metadata_parity(
        target=target,
        target_resource_bindings=target_resource_bindings,
        target_resource_binding_metadata=target_resource_binding_metadata,
    )
    diagnostics: list[CompatibilityDiagnostic] = []

    for identity in parity["missingMetadataBindings"]:
        diagnostics.append(
            CompatibilityDiagnostic(
                code=f"{target}_loader.reflection.target_binding_metadata_missing",
                message=(
                    f"{target} native loader requires every selected-target "
                    "resource binding to have loader-facing binding metadata"
                ),
                document="reflection",
                path="targetResourceBindingMetadata.bindings",
                expected=identity,
                actual="missing",
            )
        )

    for identity in parity["staleMetadataBindings"]:
        diagnostics.append(
            CompatibilityDiagnostic(
                code=f"{target}_loader.reflection.target_binding_metadata_stale",
                message=(
                    f"{target} native loader requires loader-facing binding "
                    "metadata to match a selected-target resource binding"
                ),
                document="reflection",
                path="targetResourceBindings",
                expected=identity,
                actual="missing",
            )
        )

    return tuple(diagnostics)


def _target_resource_binding_metadata_parity(
    *,
    target: str,
    target_resource_bindings: tuple[dict[str, Any], ...],
    target_resource_binding_metadata: tuple[dict[str, Any], ...],
) -> dict[str, Any]:
    binding_keys = {
        key
        for record in target_resource_bindings
        if (key := _target_resource_binding_metadata_identity(record)) is not None
        and key[0] == target
    }
    metadata_keys = {
        key
        for record in target_resource_binding_metadata
        if (key := _target_resource_binding_metadata_identity(record)) is not None
        and key[0] == target
    }
    missing_metadata_keys = tuple(sorted(binding_keys - metadata_keys))
    stale_metadata_keys = tuple(sorted(metadata_keys - binding_keys))
    identity_matches = not missing_metadata_keys and not stale_metadata_keys
    return {
        "identityMatches": identity_matches,
        "missingMetadataBindings": [
            _target_resource_binding_metadata_identity_summary(key)
            for key in missing_metadata_keys
        ],
        "staleMetadataBindings": [
            _target_resource_binding_metadata_identity_summary(key)
            for key in stale_metadata_keys
        ],
    }


def _diagnostic_matches_target_binding_metadata(
    diagnostic: CompatibilityDiagnostic,
) -> bool:
    return (
        diagnostic.path == "targetResourceBindingMetadata.bindings"
        or diagnostic.code.endswith(".target_binding_metadata_missing")
        or diagnostic.code.endswith(".target_binding_metadata_stale")
    )


def _graphics_abi_reflection_parity_summary(
    runtime_plan: RuntimeLoaderPlan,
    *,
    target: str,
    target_resource_bindings: tuple[dict[str, Any], ...] | None = None,
) -> dict[str, Any]:
    graphics_descriptor_bindings = (
        runtime_plan.compatibility_report.graphics_descriptor_bindings
    )
    if target_resource_bindings is None:
        target_resource_bindings = _target_resource_bindings(runtime_plan, target)

    reflection_bindings = tuple(
        _graphics_abi_boundary_binding(record, target=target)
        for record in target_resource_bindings
    )
    graphics_abi_declared = bool(
        graphics_descriptor_bindings.get("graphicsAbiDeclared")
    )
    source = graphics_descriptor_bindings.get("source")
    graphics_abi_bindings = (
        tuple(
            _graphics_abi_boundary_binding(record, target=target)
            for record in _object_records(graphics_descriptor_bindings.get("bindings"))
        )
        if graphics_abi_declared and source == "graphicsAbi.abiRecords"
        else ()
    )
    reflection_keys = _graphics_abi_binding_key_map(reflection_bindings)
    graphics_abi_keys = _graphics_abi_binding_key_map(graphics_abi_bindings)
    missing_graphics_abi_keys = tuple(
        sorted(reflection_keys.keys() - graphics_abi_keys.keys())
    )
    stale_graphics_abi_keys = tuple(
        sorted(graphics_abi_keys.keys() - reflection_keys.keys())
    )
    parity_checked = graphics_abi_declared and source == "graphicsAbi.abiRecords"
    identity_matches = (
        not missing_graphics_abi_keys and not stale_graphics_abi_keys
        if parity_checked
        else None
    )
    diagnostics = [
        diagnostic.to_summary()
        for diagnostic in runtime_plan.diagnostics
        if diagnostic.document == "graphicsAbi" or diagnostic.artifact == "graphicsAbi"
    ]

    return {
        "schemaVersion": 1,
        "target": target,
        "source": source,
        "graphicsAbiDeclared": graphics_abi_declared,
        "parityChecked": parity_checked,
        "identityMatches": identity_matches,
        "status": _graphics_abi_parity_status(
            graphics_abi_declared=graphics_abi_declared,
            parity_checked=parity_checked,
            identity_matches=identity_matches,
        ),
        "reflectionBindingCount": len(reflection_bindings),
        "graphicsAbiBindingCount": len(graphics_abi_bindings),
        "missingGraphicsAbiBindingCount": len(missing_graphics_abi_keys),
        "staleGraphicsAbiBindingCount": len(stale_graphics_abi_keys),
        "missingGraphicsAbiBindings": [
            _graphics_abi_binding_identity_summary(target, key)
            for key in missing_graphics_abi_keys
        ],
        "staleGraphicsAbiBindings": [
            _graphics_abi_binding_identity_summary(target, key)
            for key in stale_graphics_abi_keys
        ],
        "diagnosticCodes": [
            diagnostic["code"]
            for diagnostic in diagnostics
            if isinstance(diagnostic.get("code"), str)
        ],
        "diagnostics": diagnostics,
    }


def _graphics_abi_parity_status(
    *,
    graphics_abi_declared: bool,
    parity_checked: bool,
    identity_matches: bool | None,
) -> str:
    if not graphics_abi_declared:
        return "not-declared"
    if not parity_checked:
        return "not-checkable"
    if identity_matches:
        return "matched"
    return "mismatched"


def _graphics_abi_binding_key_map(
    records: tuple[dict[str, Any], ...],
) -> dict[tuple[str, str, str, str | None], dict[str, Any]]:
    mapping: dict[tuple[str, str, str, str | None], dict[str, Any]] = {}
    for record in records:
        key = _graphics_abi_binding_identity(record)
        if key is not None and key not in mapping:
            mapping[key] = record
    return mapping


def _graphics_abi_binding_identity(
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


def _graphics_abi_boundary_binding(
    record: dict[str, Any],
    *,
    target: str,
) -> dict[str, Any]:
    summary = {
        field_name: record[field_name]
        for field_name in (
            "target",
            "stage",
            "entryPoint",
            "name",
            "kind",
            "abi",
            "evidenceId",
            "bindingClass",
            "descriptorType",
            "set",
            "binding",
            "argumentIndex",
            "space",
            "register",
            "program",
        )
        if field_name in record
    }
    if "target" not in summary:
        summary["target"] = target
    return summary


def _graphics_abi_binding_identity_summary(
    target: str,
    key: tuple[str, str, str, str | None],
) -> dict[str, Any]:
    stage, entry_point, name, kind = key
    return {
        "target": target,
        "stage": stage,
        "entryPoint": entry_point,
        "name": name,
        "kind": kind,
    }


def _target_resource_binding_metadata_identity(
    record: dict[str, Any],
) -> tuple[str, str, str, str, str | None] | None:
    target = record.get("target")
    stage = record.get("stage")
    entry_point = record.get("entryPoint")
    name = record.get("name")
    kind = record.get("kind")
    if (
        not isinstance(target, str)
        or not target
        or not isinstance(stage, str)
        or not stage
        or not isinstance(entry_point, str)
        or not entry_point
        or not isinstance(name, str)
        or not name
    ):
        return None
    return target, stage, entry_point, name, kind if isinstance(kind, str) else None


def _target_resource_binding_metadata_identity_summary(
    key: tuple[str, str, str, str, str | None],
) -> dict[str, Any]:
    target, stage, entry_point, name, kind = key
    return {
        "target": target,
        "stage": stage,
        "entryPoint": entry_point,
        "name": name,
        "kind": kind,
    }


def _object_records(value: Any) -> tuple[dict[str, Any], ...]:
    if not isinstance(value, list):
        return ()
    return tuple(record for record in value if isinstance(record, dict))


def _reflection_resource_key(
    record: dict[str, Any],
) -> tuple[str, str, str] | None:
    stage = record.get("stage")
    name = record.get("name")
    kind = record.get("kind")
    if not isinstance(stage, str) or not isinstance(name, str):
        return None
    if not isinstance(kind, str):
        return None
    return stage, name, kind


def _has_blocking_diagnostics(
    diagnostics: tuple[CompatibilityDiagnostic, ...] | list[CompatibilityDiagnostic],
) -> bool:
    return any(diagnostic.severity in {"error", "skip"} for diagnostic in diagnostics)


def _is_crossgl_source_input_path(package_path: str) -> bool:
    return PurePosixPath(package_path).suffix.lower() in _CROSSGL_SOURCE_INPUT_SUFFIXES
