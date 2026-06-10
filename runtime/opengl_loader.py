#!/usr/bin/env python3
"""Source-free OpenGL package loader planning prototype."""

from __future__ import annotations

from dataclasses import dataclass, replace
from pathlib import Path, PurePosixPath
from typing import Any

from .backend_loader import SourceFreeNativeBackendLoaderPlan
from .backend_loader import _graphics_abi_reflection_parity_summary
from .loader import LoaderArtifactPlan, RuntimeLoaderPlan, read_loader_plan
from .package_reader import CompatibilityDiagnostic, PackageReadError


OPENGL_LOADER_TARGET = "opengl"
OPENGL_SOURCE_ARTIFACT = "backendSource"
OPENGL_NATIVE_ARTIFACT = "nativeBinary"
OPENGL_NATIVE_ARTIFACT_DESCRIPTOR = "nativeArtifactDescriptor"
OPENGL_SOURCE_PACKAGE_MODE = "source-package"
OPENGL_BACKEND_SOURCE_SUFFIX = ".glsl"


@dataclass(frozen=True)
class OpenGLLoaderPlan(RuntimeLoaderPlan):
    """OpenGL-specific metadata-only runtime-loader plan."""

    @property
    def opengl_source_package_admission_detail(self) -> dict[str, Any]:
        return _opengl_source_package_admission_detail(self)

    def to_summary(self) -> dict[str, Any]:
        summary = super().to_summary()
        summary["openglSourcePackageAdmission"] = (
            self.opengl_source_package_admission_detail
        )
        return summary


def plan_opengl_loader(
    package_path: Path | str,
    *,
    package_mode: str = "auto",
) -> OpenGLLoaderPlan:
    """Return a metadata-only OpenGL runtime-loader validation plan.

    OpenGL packages remain source-package targets in the v0 runtime boundary.
    ``auto`` therefore selects the generated backend source artifact instead of
    treating validator-backed GLSL evidence as an executable native binary.
    """
    requested_mode = _normalize_opengl_package_mode(package_mode)
    if requested_mode == "native":
        plan = read_loader_plan(
            package_path,
            OPENGL_LOADER_TARGET,
            package_mode=OPENGL_SOURCE_PACKAGE_MODE,
        )
        return _as_opengl_loader_plan(_reject_opengl_native_mode(plan))

    plan = _as_opengl_loader_plan(
        _apply_opengl_loader_diagnostics(
            read_loader_plan(
                package_path,
                OPENGL_LOADER_TARGET,
                package_mode=OPENGL_SOURCE_PACKAGE_MODE,
            )
        )
    )
    if requested_mode == "auto":
        selection = replace(
            plan.runtime_artifact_selection,
            requested_package_mode="auto",
        )
        return replace(plan, runtime_artifact_selection=selection)
    return plan


def plan_opengl_native_loader(
    package_path: Path | str,
) -> SourceFreeNativeBackendLoaderPlan:
    """Return a metadata-only OpenGL native-loader validation plan."""
    runtime_plan = plan_opengl_loader(
        package_path,
        package_mode="native",
    )
    return SourceFreeNativeBackendLoaderPlan(
        package_path=Path(package_path),
        loader_name="opengl-native",
        target=OPENGL_LOADER_TARGET,
        runtime_plan=runtime_plan,
        native_artifact=None,
        native_artifact_descriptor=None,
        entry_points=_reflection_records(runtime_plan, "entryPoints"),
        resources=_reflection_records(runtime_plan, "resources"),
        target_resource_bindings=_target_resource_bindings(
            runtime_plan,
            OPENGL_LOADER_TARGET,
        ),
        workgroup_sizes=runtime_plan.workgroup_sizes,
        diagnostics=runtime_plan.diagnostics,
    )


def plan_opengl_source_package_loader(package_path: Path | str) -> OpenGLLoaderPlan:
    """Return a metadata-only OpenGL source-package loader validation plan."""
    return plan_opengl_loader(
        package_path,
        package_mode="source-package",
    )


def _normalize_opengl_package_mode(package_mode: str) -> str:
    if package_mode == "source":
        return OPENGL_SOURCE_PACKAGE_MODE
    if package_mode in {"auto", "native", OPENGL_SOURCE_PACKAGE_MODE}:
        return package_mode
    raise PackageReadError(
        "OpenGL runtime package_mode must be one of auto, native, source, "
        f"source-package: {package_mode}"
    )


def _reject_opengl_native_mode(plan: RuntimeLoaderPlan) -> RuntimeLoaderPlan:
    diagnostic = CompatibilityDiagnostic(
        code="opengl_loader.native_mode_unsupported",
        message=(
            "OpenGL native mode is not supported by the v0 runtime loader; "
            "validated OpenGL packages load through source-package backendSource"
        ),
        document="manifest",
        artifact=OPENGL_NATIVE_ARTIFACT,
        expected=OPENGL_SOURCE_PACKAGE_MODE,
        actual="native",
    )
    selection = replace(
        plan.runtime_artifact_selection,
        requested_package_mode="native",
        selected_package_mode=None,
        artifact=None,
        diagnostics=(*plan.runtime_artifact_selection.diagnostics, diagnostic),
    )
    return replace(
        plan,
        runtime_artifact_selection=selection,
        selected_artifacts=(),
    )


def _as_opengl_loader_plan(plan: RuntimeLoaderPlan) -> OpenGLLoaderPlan:
    if isinstance(plan, OpenGLLoaderPlan):
        return plan
    return OpenGLLoaderPlan(
        root=plan.root,
        loader_target=plan.loader_target,
        module=plan.module,
        package_target=plan.package_target,
        compatibility_report=plan.compatibility_report,
        runtime_artifact_selection=plan.runtime_artifact_selection,
        selected_artifacts=plan.selected_artifacts,
    )


def _apply_opengl_loader_diagnostics(plan: RuntimeLoaderPlan) -> RuntimeLoaderPlan:
    diagnostics = _opengl_loader_diagnostics(plan)
    if not diagnostics:
        return plan
    runtime_artifact_selection = replace(
        plan.runtime_artifact_selection,
        diagnostics=(*plan.runtime_artifact_selection.diagnostics, *diagnostics),
        admission=None,
    )
    selected_artifacts = plan.selected_artifacts
    if _first_blocking_diagnostic(diagnostics) is not None:
        selected_artifacts = ()
    return replace(
        plan,
        runtime_artifact_selection=runtime_artifact_selection,
        selected_artifacts=selected_artifacts,
    )


def _opengl_loader_diagnostics(
    plan: RuntimeLoaderPlan,
) -> tuple[CompatibilityDiagnostic, ...]:
    if plan.package_target != OPENGL_LOADER_TARGET:
        return ()
    return (
        *_opengl_source_package_artifact_suffix_diagnostics(plan),
        *_opengl_validated_source_package_metadata_diagnostics(plan),
    )


def _opengl_source_package_artifact_suffix_diagnostics(
    plan: RuntimeLoaderPlan,
) -> tuple[CompatibilityDiagnostic, ...]:
    if (
        plan.runtime_artifact_selection.selected_package_mode
        != OPENGL_SOURCE_PACKAGE_MODE
    ):
        return ()
    source_artifact = _available_artifact(plan, OPENGL_SOURCE_ARTIFACT)
    if source_artifact is None or _path_has_suffix(
        source_artifact.package_path,
        OPENGL_BACKEND_SOURCE_SUFFIX,
    ):
        return ()
    return (
        CompatibilityDiagnostic(
            code="opengl_loader.source_package_backend_source_suffix_mismatch",
            message=(
                "OpenGL source-package loader requires "
                "manifest.artifacts.backendSource to reference a .glsl artifact"
            ),
            document="manifest",
            artifact=OPENGL_SOURCE_ARTIFACT,
            path=source_artifact.package_path,
            expected=f"*{OPENGL_BACKEND_SOURCE_SUFFIX}",
            actual=source_artifact.package_path,
        ),
    )


def _opengl_validated_source_package_metadata_diagnostics(
    plan: RuntimeLoaderPlan,
) -> tuple[CompatibilityDiagnostic, ...]:
    if (
        plan.runtime_artifact_selection.selected_package_mode
        != OPENGL_SOURCE_PACKAGE_MODE
    ):
        return ()
    if plan.compatibility_report.native_binary_status != "validated":
        return ()
    descriptor = _available_artifact(plan, OPENGL_NATIVE_ARTIFACT_DESCRIPTOR)
    if descriptor is not None:
        return ()
    return (
        CompatibilityDiagnostic(
            code="opengl_loader.validated_source_descriptor_missing",
            message=(
                "OpenGL source-package loader requires "
                "manifest.artifacts.nativeArtifactDescriptor when "
                "nativeBinaryStatus is validated"
            ),
            document="manifest",
            artifact=OPENGL_NATIVE_ARTIFACT_DESCRIPTOR,
            expected="manifest.artifacts.nativeArtifactDescriptor",
            actual=None,
        ),
    )


def _opengl_source_package_admission_detail(
    plan: OpenGLLoaderPlan,
) -> dict[str, Any]:
    backend_source = _available_artifact(plan, OPENGL_SOURCE_ARTIFACT)
    native_binary = _available_artifact(plan, OPENGL_NATIVE_ARTIFACT)
    descriptor = _available_artifact(plan, OPENGL_NATIVE_ARTIFACT_DESCRIPTOR)
    descriptor_diagnostics = _descriptor_diagnostics(plan)
    blocking_reason = _first_blocking_diagnostic(plan.diagnostics)
    native_status = plan.compatibility_report.native_binary_status
    backend_source_detail = _artifact_detail(
        backend_source,
        selected_for_runtime=_artifact_is_runtime_selection(
            plan,
            OPENGL_SOURCE_ARTIFACT,
        ),
        bytes_required=_artifact_is_runtime_selection(
            plan,
            OPENGL_SOURCE_ARTIFACT,
        ),
        expected_path_suffix=OPENGL_BACKEND_SOURCE_SUFFIX,
    )
    native_glsl_detail = _native_glsl_source_package_detail(
        plan,
        native_binary,
    )
    descriptor_detail = _opengl_descriptor_detail(
        descriptor,
        descriptor_diagnostics=descriptor_diagnostics,
    )

    return {
        "schemaVersion": 1,
        "metadataOnly": True,
        "decision": _opengl_admission_decision(plan, blocking_reason),
        "reason": _opengl_admission_reason(plan, blocking_reason, native_status),
        "loaderTarget": OPENGL_LOADER_TARGET,
        "packageTarget": plan.package_target,
        "packageMode": {
            "kind": OPENGL_SOURCE_PACKAGE_MODE,
            "requested": plan.runtime_artifact_selection.requested_package_mode,
            "selected": plan.runtime_artifact_selection.selected_package_mode,
            "selectedForRuntime": (
                plan.runtime_artifact_selection.selected_package_mode
                == OPENGL_SOURCE_PACKAGE_MODE
            ),
        },
        "requestedPackageMode": plan.runtime_artifact_selection.requested_package_mode,
        "selectedPackageMode": plan.runtime_artifact_selection.selected_package_mode,
        "sourceParsingRequired": plan.source_parsing_required,
        "compilerInvocationRequired": False,
        "deviceExecutionRequired": False,
        "packageArtifactRequirementsSource": (
            plan.package_artifact_requirements_source
        ),
        "packageArtifactRequirements": plan.package_artifact_requirements,
        "runtimeArtifact": _artifact_detail(
            plan.runtime_artifact,
            selected_for_runtime=True,
            bytes_required=plan.runtime_artifact is not None,
        ),
        "backendSource": backend_source_detail,
        "sourcePackageRuntime": backend_source_detail,
        "declaredSourceArtifact": backend_source_detail,
        "nativeGlslSourcePackageArtifact": native_glsl_detail,
        "validatedSourceArtifact": (
            native_glsl_detail if native_status == "validated" else None
        ),
        "compiledArtifact": None,
        "nativeArtifactDescriptor": descriptor_detail,
        "validatedSourceStatus": {
            "manifestNativeBinaryStatus": native_status,
            "descriptorPresent": descriptor is not None,
            "descriptorManifestConsistent": (
                not descriptor_diagnostics if descriptor is not None else None
            ),
            "diagnostics": descriptor_diagnostics,
        },
        "compatibilityEvidence": _opengl_compatibility_evidence(
            plan,
            backend_source=backend_source,
            native_glsl_detail=native_glsl_detail,
            descriptor_detail=descriptor_detail,
        ),
        "targetLegalizationEvidence": (
            plan.compatibility_report.target_legalization_evidence
        ),
        "targetLegalizationToolRequirements": (
            plan.compatibility_report.target_legalization_tool_requirements
        ),
        "reflection": {
            "entryPointCount": len(_reflection_records(plan, "entryPoints")),
            "resourceCount": len(_reflection_records(plan, "resources")),
            "targetResourceBindingCount": len(
                _target_resource_bindings(plan, OPENGL_LOADER_TARGET)
            ),
            "entryPoints": [
                _summarize_opengl_entry_point(record)
                for record in _reflection_records(plan, "entryPoints")
            ],
            "resources": [
                _summarize_opengl_resource(record)
                for record in _reflection_records(plan, "resources")
            ],
            "targetResourceBindings": [
                _summarize_opengl_resource_binding(record)
                for record in _target_resource_bindings(plan, OPENGL_LOADER_TARGET)
            ],
        },
        "graphicsAbiReflectionParity": _graphics_abi_reflection_parity_summary(
            plan,
            target=OPENGL_LOADER_TARGET,
            target_resource_bindings=_target_resource_bindings(
                plan,
                OPENGL_LOADER_TARGET,
            ),
        ),
        "blockedByDiagnostics": [
            diagnostic.to_summary()
            for diagnostic in plan.diagnostics
            if diagnostic.severity in {"error", "skip"}
        ],
    }


def _native_glsl_source_package_detail(
    plan: OpenGLLoaderPlan,
    artifact: LoaderArtifactPlan | None,
) -> dict[str, Any]:
    native_status = plan.compatibility_report.native_binary_status
    selected_for_runtime = _artifact_is_runtime_selection(plan, OPENGL_NATIVE_ARTIFACT)
    artifact_detail = _artifact_detail(
        artifact,
        selected_for_runtime=selected_for_runtime,
        bytes_required=selected_for_runtime,
        expected_path_suffix=OPENGL_BACKEND_SOURCE_SUFFIX,
    )
    if artifact_detail is None:
        artifact_detail = {
            "name": OPENGL_NATIVE_ARTIFACT,
            "path": None,
            "absolutePath": None,
            "exists": False,
            "size": None,
            "declaredBy": None,
            "selectedForRuntime": selected_for_runtime,
            "bytesRequired": selected_for_runtime,
        }
    return {
        **artifact_detail,
        "nativeBinaryStatus": native_status,
        "plannedNativeMetadataOnly": native_status == "planned",
        "validatedSourceEvidence": native_status == "validated",
        "acceptedAsSourcePackageEvidence": plan.loadable
        and artifact is not None
        and native_status in {"planned", "validated"},
    }


def _opengl_descriptor_detail(
    descriptor: LoaderArtifactPlan | None,
    *,
    descriptor_diagnostics: list[dict[str, Any]],
) -> dict[str, Any]:
    return {
        "declared": descriptor is not None,
        "exists": descriptor.exists if descriptor is not None else False,
        "artifact": _artifact_detail(
            descriptor,
            selected_for_runtime=False,
            bytes_required=False,
        ),
        "descriptorManifestConsistent": (
            not descriptor_diagnostics if descriptor is not None else None
        ),
        "diagnostics": descriptor_diagnostics,
    }


def _opengl_compatibility_evidence(
    plan: OpenGLLoaderPlan,
    *,
    backend_source: LoaderArtifactPlan | None,
    native_glsl_detail: dict[str, Any],
    descriptor_detail: dict[str, Any],
) -> dict[str, Any]:
    return {
        "manifestNativeBinaryStatus": plan.compatibility_report.native_binary_status,
        "packageArtifactRequirementsSource": plan.package_artifact_requirements_source,
        "packageArtifactRequirements": plan.package_artifact_requirements,
        "requiredArtifacts": list(plan.required_artifacts),
        "requiredArtifactPaths": plan.required_artifact_paths,
        "declaredSourcePath": (
            backend_source.package_path if backend_source is not None else None
        ),
        "sourceArtifactExists": (
            backend_source.exists if backend_source is not None else False
        ),
        "validatedArtifactPath": native_glsl_detail["path"],
        "validatedArtifactExists": native_glsl_detail["exists"],
        "validatedSourceEvidence": native_glsl_detail["validatedSourceEvidence"],
        "descriptorDeclared": descriptor_detail["declared"],
        "descriptorExists": descriptor_detail["exists"],
        "descriptorManifestConsistent": descriptor_detail[
            "descriptorManifestConsistent"
        ],
        "descriptorDiagnostics": descriptor_detail["diagnostics"],
        "targetLegalizationEvidence": (
            plan.compatibility_report.target_legalization_evidence
        ),
        "targetLegalizationToolRequirements": (
            plan.compatibility_report.target_legalization_tool_requirements
        ),
    }


def _opengl_admission_decision(
    plan: OpenGLLoaderPlan,
    blocking_reason: CompatibilityDiagnostic | None,
) -> str:
    if plan.package_target != OPENGL_LOADER_TARGET:
        return "skipped"
    return "accepted" if plan.loadable else "rejected"


def _opengl_admission_reason(
    plan: OpenGLLoaderPlan,
    blocking_reason: CompatibilityDiagnostic | None,
    native_status: str | None,
) -> str | None:
    if plan.package_target != OPENGL_LOADER_TARGET:
        return "opengl_loader.source_package_admission.target_mismatch"
    if plan.loadable:
        return _accepted_source_package_reason(native_status)
    return blocking_reason.code if blocking_reason is not None else None


def _artifact_detail(
    artifact: LoaderArtifactPlan | None,
    *,
    selected_for_runtime: bool,
    bytes_required: bool,
    expected_path_suffix: str | None = None,
) -> dict[str, Any] | None:
    if artifact is None:
        return None
    summary = artifact.to_summary()
    summary["declaredBy"] = f"manifest.artifacts.{artifact.name}"
    summary["selectedForRuntime"] = selected_for_runtime
    summary["bytesRequired"] = bytes_required
    if expected_path_suffix is not None:
        summary["expectedPathSuffix"] = expected_path_suffix
        summary["pathSuffix"] = _path_suffix(artifact.package_path)
        summary["pathSuffixMatchesExpected"] = _path_has_suffix(
            artifact.package_path,
            expected_path_suffix,
        )
    return summary


def _artifact_is_runtime_selection(plan: RuntimeLoaderPlan, artifact_name: str) -> bool:
    return (
        plan.runtime_artifact is not None
        and plan.runtime_artifact.name == artifact_name
    )


def _available_artifact(
    runtime_plan: RuntimeLoaderPlan,
    name: str,
) -> LoaderArtifactPlan | None:
    for artifact in runtime_plan.compatibility_report.available_artifacts:
        if artifact.name == name:
            return LoaderArtifactPlan.from_artifact(artifact)
    return None


def _descriptor_diagnostics(plan: RuntimeLoaderPlan) -> list[dict[str, Any]]:
    return [
        diagnostic.to_summary()
        for diagnostic in plan.diagnostics
        if diagnostic.document == "nativeArtifactDescriptor"
        or diagnostic.artifact == OPENGL_NATIVE_ARTIFACT_DESCRIPTOR
    ]


def _accepted_source_package_reason(native_status: str | None) -> str:
    if native_status == "planned":
        return "opengl_loader.source_package_admission.planned_glsl_accepted"
    if native_status == "validated":
        return "opengl_loader.source_package_admission.validated_glsl_accepted"
    return "opengl_loader.source_package_admission.accepted"


def _summarize_opengl_entry_point(record: dict[str, Any]) -> dict[str, Any]:
    return {
        "stage": record.get("stage"),
        "sourceName": record.get("sourceName"),
        "backendName": record.get("backendName"),
    }


def _summarize_opengl_resource(record: dict[str, Any]) -> dict[str, Any]:
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


def _summarize_opengl_resource_binding(record: dict[str, Any]) -> dict[str, Any]:
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
        "program": abi_summary.get("program"),
        "binding": abi_summary.get("binding"),
    }
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


def _path_suffix(package_path: str) -> str:
    return PurePosixPath(package_path).suffix.lower()


def _path_has_suffix(package_path: str, suffix: str) -> bool:
    return _path_suffix(package_path) == suffix
