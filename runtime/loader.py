#!/usr/bin/env python3
"""Target-neutral runtime loader facade for CrossGL .cglb packages.

The facade is intentionally a planner, not a graphics API loader. It consumes
the package reader's compatibility report and selects the artifact records that
the package contract makes available to a target-specific loader.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from pathlib import Path, PurePosixPath
from typing import Any

from .package_reader import (
    Artifact,
    CompatibilityDiagnostic,
    PackageCompatibilityReport,
    PackageReadError,
    RUNTIME_ARTIFACT_STREAM_CHUNK_SIZE,
    RuntimeArtifactSelection,
    SUPPORTED_COMPILER_NAME,
    SUPPORTED_DEBUG_METADATA_SCHEMA_VERSION,
    SUPPORTED_PACKAGE_SCHEMA_VERSION,
    read_compatibility_report,
    select_runtime_artifact,
    _DEFAULT_ARTIFACT_BYTE_LIMIT,
)


_CROSSGL_SOURCE_INPUT_SUFFIXES = frozenset((".cgl",))
_ARTIFACT_SELECTION_MODES = ("auto", "native", "source-package")
_RUNTIME_LOADER_PLAN_KIND = "crossgl-runtime-loader-plan"
_RUNTIME_LOADER_PLAN_REQUIRED_METADATA_INPUTS = [
    "manifest.json",
    "reflection.json",
    "diagnostics.json",
]
_RUNTIME_LOADER_PLAN_KNOWN_TARGETS = frozenset(("metal", "vulkan", "directx", "opengl"))
_RUNTIME_LOADER_PLAN_SCHEMA_REQUIREMENT_SOURCES = {
    "manifest.packageArtifactRequirements": "manifest.packageArtifactRequirements",
    "generated-package-target-contract": "generated-package-target-contract",
    "legacy-v0-target-contract": "generated-package-target-contract",
}
_VERSION_COMPATIBILITY_DIAGNOSTIC_CODES = frozenset(
    (
        "package.compiler.missing",
        "package.compiler.name_incompatible",
        "package.compiler.version_missing",
        "package.compiler.version_invalid",
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
_UNSUPPORTED_VERSION_COMPATIBILITY_DIAGNOSTIC_CODES = frozenset(
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
class LoaderArtifactPlan:
    """A required package artifact selected for a runtime loader target."""

    name: str
    package_path: str
    path: Path
    exists: bool
    size: int | None
    archive_path: Path | None = None
    archive_member: str | None = None
    absolute_path: str | None = None

    @classmethod
    def from_artifact(cls, artifact: Artifact) -> "LoaderArtifactPlan":
        return cls(
            name=artifact.name,
            package_path=artifact.package_path,
            path=artifact.path,
            exists=artifact.exists,
            size=artifact.size,
            archive_path=artifact.archive_path,
            archive_member=artifact.archive_member,
            absolute_path=artifact.absolute_path,
        )

    def require_exists(self) -> "LoaderArtifactPlan":
        if self.archive_path is not None:
            if not self.exists:
                raise PackageReadError(
                    f"loader artifact is missing in archive: {self.name} "
                    f"({self.package_path})"
                )
            return self
        if not self.path.is_file():
            raise PackageReadError(
                f"loader artifact is missing on disk: {self.name} ({self.package_path})"
            )
        return self

    def _as_manifest_artifact(self) -> Artifact:
        return Artifact(
            name=self.name,
            package_path=self.package_path,
            path=self.path,
            exists=self.exists,
            size=self.size,
            archive_path=self.archive_path,
            archive_member=self.archive_member,
        )

    def iter_bytes(
        self,
        *,
        chunk_size: int = RUNTIME_ARTIFACT_STREAM_CHUNK_SIZE,
        byte_limit: Any = _DEFAULT_ARTIFACT_BYTE_LIMIT,
    ):
        self.require_exists()
        yield from self._as_manifest_artifact().iter_bytes(
            chunk_size=chunk_size,
            byte_limit=byte_limit,
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
        self.require_exists()
        digest = self._as_manifest_artifact().sha256(
            chunk_size=chunk_size,
            byte_limit=byte_limit,
        )
        return digest

    def to_summary(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "path": self.package_path,
            "absolutePath": self.absolute_path or str(self.path),
            "exists": self.exists,
            "size": self.size,
        }


@dataclass(frozen=True)
class SourceFreeRuntimeArtifactHandoff:
    """Bytes and identity metadata for a selected source-free runtime artifact."""

    plan: "RuntimeLoaderPlan"
    artifact: LoaderArtifactPlan
    metadata: dict[str, Any]
    package_format: str
    artifact_name: str
    package_path: str
    absolute_path: str
    selected_package_mode: str | None
    size: int | None
    bytes: bytes
    archive_path: Path | None = None
    archive_member: str | None = None

    @property
    def byte_length(self) -> int:
        return len(self.bytes)

    def to_summary(self) -> dict[str, Any]:
        return {
            "schemaVersion": 1,
            "packageFormat": self.package_format,
            "selectedPackageMode": self.selected_package_mode,
            "sourceParsingRequired": False,
            "compilerInvocationRequired": False,
            "deviceExecutionRequired": False,
            "byteLength": self.byte_length,
            "metadata": self.metadata,
            "artifact": {
                "name": self.artifact_name,
                "path": self.package_path,
                "absolutePath": self.absolute_path,
                "size": self.size,
                "archivePath": (
                    str(self.archive_path) if self.archive_path is not None else None
                ),
                "archiveMember": self.archive_member,
            },
        }


@dataclass(frozen=True)
class RuntimeLoaderPlan:
    """Structured runtime handoff for a target-specific loader implementation."""

    root: Path
    loader_target: str
    module: str | None
    package_target: str | None
    compatibility_report: PackageCompatibilityReport
    runtime_artifact_selection: RuntimeArtifactSelection
    selected_artifacts: tuple[LoaderArtifactPlan, ...]

    @property
    def loadable(self) -> bool:
        return self.runtime_artifact_selection.selected

    @property
    def selected_target(self) -> str | None:
        if not self.loadable:
            return None
        return self.loader_target

    @property
    def source_parsing_required(self) -> bool:
        return False

    @property
    def loader_diagnostic_summary(self) -> dict[str, Any]:
        compatibility_diagnostics = self.compatibility_report.diagnostics
        selection_diagnostics = tuple(
            diagnostic
            for diagnostic in self.runtime_artifact_selection.diagnostics
            if diagnostic not in compatibility_diagnostics
        )
        return {
            "schemaVersion": 1,
            "loadable": self.loadable,
            "status": self.compatibility_report.status,
            "sourceParsingRequired": self.source_parsing_required,
            "versionCompatibility": self.version_compatibility_summary,
            "targetCompatibility": self.target_compatibility_summary,
            "artifactSelection": self.artifact_selection_summary,
            "compatibility": _diagnostic_phase_summary(compatibility_diagnostics),
            "selection": _diagnostic_phase_summary(selection_diagnostics),
            "runtimeArtifactAdmission": self.runtime_artifact_admission_summary,
        }

    @property
    def metadata_contract_summary(self) -> dict[str, Any]:
        """Return the bounded metadata-only contract exposed to loaders."""
        runtime_artifact = self.runtime_artifact
        contract_source = self.package_artifact_requirements_source

        return {
            "schemaVersion": 1,
            "metadataOnly": True,
            "sourceParsingRequired": self.source_parsing_required,
            "compilerInvocationRequired": False,
            "deviceExecutionRequired": False,
            "packageTarget": self.package_target,
            "loaderTarget": self.loader_target,
            "loadable": self.loadable,
            "status": self.compatibility_report.status,
            "contractSource": contract_source,
            "packageArtifactRequirementsSource": contract_source,
            "requiredMetadataInputs": self.required_metadata_inputs,
            "requirements": self.package_artifact_requirements,
            "packageArtifactRequirements": self.package_artifact_requirements,
            "targetLegalizationEvidence": (
                self.compatibility_report.target_legalization_evidence
            ),
            "targetLegalizationToolRequirements": (
                self.compatibility_report.target_legalization_tool_requirements
            ),
            "versionCompatibility": self.version_compatibility_summary,
            "targetCompatibility": self.target_compatibility_summary,
            "artifactSelection": self.artifact_selection_summary,
            "runtimeArtifactAdmission": self.runtime_artifact_admission_summary,
            "metadataDocuments": _loader_metadata_documents(self.compatibility_report),
            "requiredArtifactInputs": [
                {
                    "name": name,
                    "path": self.required_artifact_paths[name],
                    "declaredBy": (
                        f"manifest.artifacts.{name}"
                        if self.required_artifact_paths[name] is not None
                        else None
                    ),
                }
                for name in self.required_artifacts
            ],
            "selectedArtifactInputs": [
                {
                    "name": artifact.name,
                    "path": artifact.package_path,
                    "declaredBy": f"manifest.artifacts.{artifact.name}",
                    "selectedForLoad": (
                        runtime_artifact is not None
                        and artifact.name == runtime_artifact.name
                    ),
                    "exists": artifact.exists,
                }
                for artifact in self.selected_artifacts
            ],
            "runtimeArtifact": (
                {
                    "name": runtime_artifact.name,
                    "path": runtime_artifact.package_path,
                    "declaredBy": f"manifest.artifacts.{runtime_artifact.name}",
                }
                if runtime_artifact is not None
                else None
            ),
            "reflectionInputs": self.reflection_resource_summary,
            "targetResourceBindingMetadata": (
                self.target_resource_binding_metadata_summary
            ),
            "sourceInputs": [],
        }

    def to_runtime_loader_plan_contract(self) -> dict[str, Any]:
        """Return the published metadata-only runtime loader plan contract."""
        diagnostics = _runtime_loader_plan_contract_diagnostics(self)
        selected_artifact = _runtime_loader_plan_contract_selected_artifact(self)
        diagnostic_counts = _runtime_loader_plan_contract_diagnostic_counts(diagnostics)
        package_target = _runtime_loader_plan_target_or_null(self.package_target)
        requested_target = _runtime_loader_plan_target_or_null(self.loader_target)
        target_matches_package = (
            package_target is not None
            and requested_target is not None
            and package_target == requested_target
        )

        return {
            "schemaVersion": 1,
            "kind": _RUNTIME_LOADER_PLAN_KIND,
            "success": selected_artifact is not None
            and diagnostic_counts["error"] == 0
            and target_matches_package,
            "metadataOnly": True,
            "sourceParsingRequired": self.source_parsing_required,
            "compilerInvocationRequired": False,
            "deviceExecutionRequired": False,
            "packageFormat": _runtime_loader_plan_package_format(
                self.compatibility_report.package_format
            ),
            "packageVersion": self.compatibility_report.manifest_schema_version,
            "packageTarget": package_target,
            "requestedLoaderTarget": requested_target,
            "selectedTarget": self.selected_target,
            "targetMatchesPackage": target_matches_package,
            "loadable": self.loadable,
            "requestedPackageMode": (
                self.runtime_artifact_selection.requested_package_mode
            ),
            "selectedPackageMode": (
                selected_artifact["packageMode"] if selected_artifact else None
            ),
            "selectedArtifact": selected_artifact,
            "requiredArtifacts": list(self.required_artifacts),
            "requiredArtifactPaths": self.required_artifact_paths,
            "runtimeArtifactPath": self.runtime_artifact_path,
            "runtimeArtifactSelection": (
                _runtime_loader_plan_contract_runtime_artifact_selection(
                    self,
                    selected_artifact=selected_artifact,
                    success=(
                        selected_artifact is not None
                        and diagnostic_counts["error"] == 0
                        and target_matches_package
                    ),
                )
            ),
            "requiredMetadataInputs": list(
                _RUNTIME_LOADER_PLAN_REQUIRED_METADATA_INPUTS
            ),
            "packageArtifactRequirementsSource": (
                _runtime_loader_plan_requirements_source(
                    self.package_artifact_requirements_source
                )
            ),
            "packageArtifactRequirements": (
                _runtime_loader_plan_package_artifact_requirements(
                    self.compatibility_report
                )
            ),
            "targetLegalizationEvidenceSummary": (
                _runtime_loader_plan_target_legalization_summary(
                    self.compatibility_report
                )
            ),
            "reflectionSummary": _runtime_loader_plan_reflection_summary(self),
            "reflectionInputs": self.reflection_resource_summary,
            "targetResourceBindingMetadata": (
                self.target_resource_binding_metadata_summary
            ),
            "diagnosticCounts": diagnostic_counts,
            "diagnostics": diagnostics,
        }

    @property
    def required_metadata_inputs(self) -> list[dict[str, Any]]:
        """Return package metadata documents required before loader dispatch."""
        return _loader_required_metadata_inputs(self.compatibility_report)

    @property
    def version_compatibility_summary(self) -> dict[str, Any]:
        """Return loader-facing compiler/runtime version compatibility facts."""
        report = self.compatibility_report
        diagnostics = tuple(
            diagnostic
            for diagnostic in report.diagnostics
            if _is_version_compatibility_diagnostic(diagnostic)
        )
        return {
            "schemaVersion": 1,
            "metadataOnly": True,
            "sourceParsingRequired": self.source_parsing_required,
            "planStatus": report.status,
            "status": _version_compatibility_status(diagnostics),
            "compatible": not diagnostics,
            "compiler": {
                "name": report.compiler_name,
                "version": report.compiler_version,
                "expectedName": SUPPORTED_COMPILER_NAME,
                "compatible": _compiler_metadata_compatible(report),
            },
            "runtime": {
                "loader": "runtime.loader",
                "packageReader": "runtime.package_reader",
                "supportedPackageSchemaVersion": SUPPORTED_PACKAGE_SCHEMA_VERSION,
                "supportedDebugMetadataSchemaVersion": (
                    SUPPORTED_DEBUG_METADATA_SCHEMA_VERSION
                ),
            },
            "schemas": {
                "manifest": _schema_version_compatibility(
                    report.manifest_schema_version,
                    supported_version=SUPPORTED_PACKAGE_SCHEMA_VERSION,
                    required=True,
                ),
                "reflection": _schema_version_compatibility(
                    report.reflection_schema_version,
                    supported_version=SUPPORTED_PACKAGE_SCHEMA_VERSION,
                    required=True,
                ),
                "diagnostics": _schema_version_compatibility(
                    report.diagnostics_schema_version,
                    supported_version=SUPPORTED_PACKAGE_SCHEMA_VERSION,
                    required=True,
                ),
                "debugMetadata": _debug_metadata_version_compatibility(report),
            },
            "diagnosticCount": len(diagnostics),
            "diagnosticCodes": [diagnostic.code for diagnostic in diagnostics],
            "diagnostics": [diagnostic.to_summary() for diagnostic in diagnostics],
        }

    @property
    def target_compatibility_summary(self) -> dict[str, Any]:
        """Return loader-facing target compatibility facts and diagnostics."""
        target_admission = _admission_section(
            self.runtime_artifact_admission_summary.get("targetCompatibility")
        )
        diagnostics = [
            diagnostic
            for diagnostic in target_admission.get("diagnostics", [])
            if isinstance(diagnostic, dict)
        ]
        return {
            "schemaVersion": 1,
            "metadataOnly": True,
            "sourceParsingRequired": self.source_parsing_required,
            "compilerInvocationRequired": False,
            "deviceExecutionRequired": False,
            "loaderTarget": self.loader_target,
            "packageTarget": self.package_target,
            "decision": target_admission.get("decision"),
            "category": target_admission.get("category"),
            "requestedTarget": target_admission.get(
                "requestedTarget",
                self.loader_target,
            ),
            "matched": target_admission.get(
                "matched",
                self.package_target == self.loader_target,
            ),
            "diagnosticCount": len(diagnostics),
            "diagnosticCodes": [
                diagnostic["code"]
                for diagnostic in diagnostics
                if isinstance(diagnostic.get("code"), str)
            ],
            "diagnostics": diagnostics,
        }

    @property
    def artifact_selection_summary(self) -> dict[str, Any]:
        """Return the normalized runtime artifact selection contract."""
        selection = self.runtime_artifact_selection
        admission = _admission_section(selection.admission)
        diagnostics = [diagnostic.to_summary() for diagnostic in selection.diagnostics]
        runtime_admission = self.runtime_artifact_admission_summary
        return {
            "schemaVersion": 1,
            "metadataOnly": True,
            "sourceParsingRequired": self.source_parsing_required,
            "compilerInvocationRequired": False,
            "deviceExecutionRequired": False,
            "sourceInputs": [],
            "supportedModes": list(_ARTIFACT_SELECTION_MODES),
            "requestedMode": selection.requested_package_mode,
            "requestedPackageMode": selection.requested_package_mode,
            "selectedMode": selection.selected_package_mode,
            "selectedPackageMode": selection.selected_package_mode,
            "selected": selection.selected,
            "decision": admission.get(
                "decision",
                "accepted" if selection.selected else "unavailable",
            ),
            "reason": runtime_admission["reason"],
            "runtimeArtifact": _artifact_identity(self.runtime_artifact),
            "selectedArtifacts": [
                artifact.to_summary() for artifact in self.selected_artifacts
            ],
            "diagnosticCount": len(diagnostics),
            "diagnosticCodes": [
                diagnostic["code"]
                for diagnostic in diagnostics
                if isinstance(diagnostic.get("code"), str)
            ],
            "diagnostics": diagnostics,
            "nativeArtifact": runtime_admission["nativeArtifact"],
            "sourcePackageFallback": runtime_admission["sourcePackageFallback"],
        }

    @property
    def diagnostics(self) -> tuple[CompatibilityDiagnostic, ...]:
        return self.runtime_artifact_selection.diagnostics

    @property
    def reject_reasons(self) -> tuple[CompatibilityDiagnostic, ...]:
        return self.runtime_artifact_selection.reject_reasons

    @property
    def skip_reasons(self) -> tuple[CompatibilityDiagnostic, ...]:
        return self.runtime_artifact_selection.skip_reasons

    @property
    def required_artifacts(self) -> tuple[str, ...]:
        return self.compatibility_report.required_artifacts

    @property
    def required_artifact_paths(self) -> dict[str, str | None]:
        artifacts_by_name = {
            artifact.name: artifact
            for artifact in self.compatibility_report.available_artifacts
        }
        return {
            name: (
                artifacts_by_name[name].package_path
                if name in artifacts_by_name
                else None
            )
            for name in self.required_artifacts
        }

    @property
    def runtime_artifact_path(self) -> str | None:
        artifact = self.runtime_artifact
        if artifact is None:
            return None
        return artifact.package_path

    @property
    def availability_summary(self) -> dict[str, Any]:
        return self.compatibility_report.availability_summary

    @property
    def artifact_compatibility_summary(self) -> dict[str, Any]:
        selected_artifact = self.runtime_artifact_selection.artifact
        return self.compatibility_report.artifact_compatibility_summary(
            selected_artifact_name=(
                selected_artifact.name if selected_artifact is not None else None
            ),
            infer_runtime_selection=False,
        )

    @property
    def runtime_artifact_admission_summary(self) -> dict[str, Any]:
        """Return loader-facing runtime artifact admission facts."""
        selection_summary = self.runtime_artifact_selection.to_summary()
        admission = selection_summary.get("admission")
        if not isinstance(admission, dict):
            admission = {}

        target_admission = _admission_section(admission.get("target"))
        native_admission = _admission_section(admission.get("native"))
        source_package_fallback = _admission_section(
            admission.get("sourcePackageFallback")
        )
        artifacts_by_name = {
            artifact.name: artifact
            for artifact in self.compatibility_report.available_artifacts
        }

        native_admission["artifact"] = _artifact_identity(
            artifacts_by_name.get("nativeBinary")
        )
        source_package_fallback["artifact"] = _artifact_identity(
            artifacts_by_name.get("backendSource")
        )

        return {
            "schemaVersion": 1,
            "metadataOnly": True,
            "sourceParsingRequired": self.source_parsing_required,
            "compilerInvocationRequired": False,
            "deviceExecutionRequired": False,
            "loaderTarget": self.loader_target,
            "packageTarget": self.package_target,
            "requestedPackageMode": self.runtime_artifact_selection.requested_package_mode,
            "selectedPackageMode": self.runtime_artifact_selection.selected_package_mode,
            "loadable": self.loadable,
            "status": self.compatibility_report.status,
            "decision": admission.get(
                "decision",
                "accepted" if self.loadable else "rejected",
            ),
            "reason": _runtime_artifact_admission_reason(
                selection=self.runtime_artifact_selection,
                native_admission=native_admission,
                source_package_fallback=source_package_fallback,
            ),
            "runtimeArtifact": _artifact_identity(self.runtime_artifact),
            "packageArtifactRequirementsSource": (
                self.package_artifact_requirements_source
            ),
            "packageArtifactRequirements": self.package_artifact_requirements,
            "targetCompatibility": target_admission,
            "nativeArtifact": native_admission,
            "sourcePackageFallback": source_package_fallback,
        }

    @property
    def package_artifact_requirements_source(self) -> str | None:
        """Return the loader-facing source for package artifact requirements."""
        contract = self.compatibility_report.target_contract
        if contract is None:
            return None
        if contract.requirements_source == "manifest":
            return "manifest.packageArtifactRequirements"
        return "legacy-v0-target-contract"

    @property
    def package_artifact_requirements(self) -> dict[str, Any]:
        """Return normalized package artifact requirement admission facts."""
        return self.compatibility_report.requirements_summary

    @property
    def artifact_role_compatibility(self) -> dict[str, Any]:
        """Return loader-facing compatibility for each required artifact role."""
        roles = [
            self._artifact_role_compatibility(name) for name in self.required_artifacts
        ]
        return {
            "schemaVersion": 1,
            "loaderTarget": self.loader_target,
            "packageTarget": self.package_target,
            "loadable": self.loadable,
            "selectedRuntimeArtifact": (
                self.runtime_artifact.name
                if self.runtime_artifact is not None
                else None
            ),
            "roleCount": len(roles),
            "compatibleRoleCount": sum(1 for role in roles if role["compatible"]),
            "blockedByDiagnostics": [
                diagnostic.to_summary()
                for diagnostic in self.diagnostics
                if diagnostic.severity in {"error", "skip"}
            ],
            "roles": roles,
        }

    @property
    def reflection_resource_summary(self) -> dict[str, Any]:
        target_bindings = self._reflection_records("targetResourceBindings")
        target_features = self._reflection_records("targetFeatures")
        workgroup_sizes = self.workgroup_sizes
        selected_target = self.selected_target
        if selected_target is None:
            selected_target = self.loader_target

        selected_bindings = tuple(
            record
            for record in target_bindings
            if record.get("target") == selected_target
        )
        selected_features = tuple(
            record
            for record in target_features
            if record.get("target") == selected_target
        )

        return {
            "schemaVersion": 1,
            "selectedTarget": self.selected_target,
            "entryPointCount": len(self._reflection_records("entryPoints")),
            "resourceCount": len(self._reflection_records("resources")),
            "targetResourceBindingCount": len(selected_bindings),
            "targetFeatureCount": len(selected_features),
            "workgroupSizeCount": len(workgroup_sizes),
            "workgroupSizesAvailable": bool(workgroup_sizes),
            "skippedTargetResourceBindingCount": (
                len(target_bindings) - len(selected_bindings)
            ),
            "skippedTargetFeatureCount": len(target_features) - len(selected_features),
            "entryPoints": [
                _summarize_reflection_record(
                    record,
                    ("stage", "sourceName", "backendName"),
                )
                for record in self._reflection_records("entryPoints")
            ],
            "resources": [
                _summarize_reflection_record(
                    record,
                    (
                        "stage",
                        "name",
                        "kind",
                        "type",
                        "storageImageFormat",
                        "storageImageAccess",
                        "arrayDimensions",
                        "arrayElementCount",
                        "set",
                        "binding",
                    ),
                )
                for record in self._reflection_records("resources")
            ],
            "targetResourceBindings": [
                _summarize_reflection_record(
                    record,
                    (
                        "target",
                        "stage",
                        "entryPoint",
                        "name",
                        "kind",
                        "bindingClass",
                        "descriptorType",
                        "storageImageFormat",
                        "storageImageAccess",
                        "arrayDimensions",
                        "arrayElementCount",
                        "abi",
                        "evidenceId",
                    ),
                )
                for record in selected_bindings
            ],
            "targetFeatures": [
                _summarize_reflection_record(
                    record,
                    ("target", "kind", "name", "evidenceIds"),
                )
                for record in selected_features
            ],
            "workgroupSizes": list(workgroup_sizes),
        }

    @property
    def target_resource_binding_metadata_summary(self) -> dict[str, Any]:
        target_bindings = self._reflection_records("targetResourceBindings")
        selected_target = self.selected_target
        if selected_target is None:
            selected_target = self.loader_target
        selected_bindings = tuple(
            record
            for record in target_bindings
            if record.get("target") == selected_target
        )
        return {
            "schemaVersion": 1,
            "selectedTarget": self.selected_target,
            "loaderTarget": self.loader_target,
            "packageTarget": self.package_target,
            "bindingCount": len(selected_bindings),
            "skippedBindingCount": len(target_bindings) - len(selected_bindings),
            "bindings": [
                _target_resource_binding_metadata_record(record)
                for record in selected_bindings
            ],
        }

    @property
    def runtime_artifact(self) -> LoaderArtifactPlan | None:
        artifact = self.runtime_artifact_selection.artifact
        if artifact is None:
            return None
        return self.artifact(artifact.name)

    def require_runtime_artifact(self) -> LoaderArtifactPlan:
        artifact = self.runtime_artifact
        if artifact is None:
            self.runtime_artifact_selection.require_selected()
            raise PackageReadError("loader plan did not select a runtime artifact")
        return artifact

    def runtime_artifact_handoff(
        self,
        *,
        byte_limit: int | None = None,
    ) -> SourceFreeRuntimeArtifactHandoff | None:
        if not self.loadable:
            return None
        artifact = self.runtime_artifact
        if artifact is None:
            return None
        return self._runtime_artifact_handoff(artifact, byte_limit=byte_limit)

    def require_runtime_artifact_handoff(
        self,
        *,
        byte_limit: int | None = None,
    ) -> SourceFreeRuntimeArtifactHandoff:
        self.require_loadable()
        return self._runtime_artifact_handoff(
            self.require_runtime_artifact(),
            byte_limit=byte_limit,
        )

    def _runtime_artifact_handoff(
        self,
        artifact: LoaderArtifactPlan,
        *,
        byte_limit: int | None,
    ) -> SourceFreeRuntimeArtifactHandoff:
        payload = artifact.read_bytes(byte_limit=byte_limit)
        return SourceFreeRuntimeArtifactHandoff(
            plan=self,
            artifact=artifact,
            metadata=self.metadata_contract_summary,
            package_format=self.compatibility_report.package_format,
            artifact_name=artifact.name,
            package_path=artifact.package_path,
            absolute_path=artifact.absolute_path or str(artifact.path),
            selected_package_mode=(
                self.runtime_artifact_selection.selected_package_mode
            ),
            size=artifact.size if artifact.size is not None else len(payload),
            bytes=payload,
            archive_path=artifact.archive_path,
            archive_member=artifact.archive_member,
        )

    def artifact(self, name: str) -> LoaderArtifactPlan | None:
        for artifact in self.selected_artifacts:
            if artifact.name == name:
                return artifact
        return None

    def require_artifact(self, name: str) -> LoaderArtifactPlan:
        artifact = self.artifact(name)
        if artifact is None:
            raise PackageReadError(f"loader plan did not select artifact: {name}")
        return artifact

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
        expected_target = self.loader_target if target is None else target
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
            expected_target = self.loader_target if target is None else target
            raise PackageReadError(
                "missing reflection target resource binding: "
                f"target={expected_target} stage={stage} name={name}"
            )
        return resource

    @property
    def workgroup_sizes(self) -> tuple[dict[str, Any], ...]:
        """Return reflected compute workgroup sizes from package metadata."""
        return self.compatibility_report.workgroup_sizes

    def workgroup_size(self, stage: str, entry_point: str) -> dict[str, Any] | None:
        """Find reflected workgroup size by stage and source/backend entry name."""
        return self.compatibility_report.workgroup_size(stage, entry_point)

    def require_workgroup_size(self, stage: str, entry_point: str) -> dict[str, Any]:
        workgroup_size = self.workgroup_size(stage, entry_point)
        if workgroup_size is None:
            raise PackageReadError(
                "missing reflection workgroup size: "
                f"stage={stage} entryPoint={entry_point}"
            )
        return workgroup_size

    def require_loadable(self) -> "RuntimeLoaderPlan":
        if not self.loadable:
            messages = "; ".join(
                diagnostic.message
                for diagnostic in self.diagnostics
                if diagnostic.severity in {"error", "skip"}
            )
            raise PackageReadError(f"runtime loader cannot load package: {messages}")
        return self

    def to_summary(self) -> dict[str, Any]:
        return {
            "schemaVersion": 1,
            "packageFormat": self.compatibility_report.package_format,
            "packageVersion": self.compatibility_report.manifest_schema_version,
            "root": str(self.root),
            "module": self.module,
            "packageTarget": self.package_target,
            "loaderTarget": self.loader_target,
            "selectedTarget": self.selected_target,
            "availableTargets": list(self.compatibility_report.available_targets),
            "targetAvailability": self.compatibility_report.target_availability,
            "loadable": self.loadable,
            "status": self.compatibility_report.status,
            "versionCompatibility": self.version_compatibility_summary,
            "sourceParsingRequired": self.source_parsing_required,
            "sourceInputs": [],
            "compilerInvocationRequired": False,
            "deviceExecutionRequired": False,
            "requiredMetadataInputs": self.required_metadata_inputs,
            "requiredArtifacts": list(self.required_artifacts),
            "requiredArtifactPaths": self.required_artifact_paths,
            "runtimeArtifactPath": self.runtime_artifact_path,
            "packageArtifactRequirementsSource": (
                self.package_artifact_requirements_source
            ),
            "packageArtifactRequirements": self.package_artifact_requirements,
            "targetCompatibility": self.target_compatibility_summary,
            "artifactSelection": self.artifact_selection_summary,
            "runtimeArtifactAdmission": self.runtime_artifact_admission_summary,
            "runtimeArtifactSelection": self.runtime_artifact_selection.to_summary(),
            "targetLegalizationEvidence": (
                self.compatibility_report.target_legalization_evidence
            ),
            "targetLegalizationToolRequirements": (
                self.compatibility_report.target_legalization_tool_requirements
            ),
            "selectedArtifacts": [
                artifact.to_summary() for artifact in self.selected_artifacts
            ],
            "artifactRoleCompatibility": self.artifact_role_compatibility,
            "artifactCompatibility": self.artifact_compatibility_summary,
            "reflectionResources": self.reflection_resource_summary,
            "targetResourceBindingMetadata": (
                self.target_resource_binding_metadata_summary
            ),
            "artifactAvailability": self.compatibility_report.artifact_availability,
            "availability": self.availability_summary,
            "metadataContract": self.metadata_contract_summary,
            "missingArtifacts": [
                diagnostic.to_summary()
                for diagnostic in self.compatibility_report.missing_artifacts
            ],
            "rejectReasons": [
                diagnostic.to_summary() for diagnostic in self.reject_reasons
            ],
            "skipReasons": [
                diagnostic.to_summary() for diagnostic in self.skip_reasons
            ],
            "diagnosticSummary": self.compatibility_report.diagnostic_summary,
            "loaderDiagnostics": self.loader_diagnostic_summary,
            "diagnostics": [diagnostic.to_summary() for diagnostic in self.diagnostics],
            "compatibilityReport": self.compatibility_report.to_summary(),
        }

    def _reflection_records(self, key: str) -> tuple[dict[str, Any], ...]:
        records = self.compatibility_report.reflection.get(key, [])
        if not isinstance(records, list):
            return ()
        return tuple(record for record in records if isinstance(record, dict))

    def _artifact_role_compatibility(self, name: str) -> dict[str, Any]:
        artifacts_by_name = {
            artifact.name: artifact
            for artifact in self.compatibility_report.available_artifacts
        }
        artifact = artifacts_by_name.get(name)
        selected_for_runtime = (
            self.runtime_artifact_selection.artifact is not None
            and self.runtime_artifact_selection.artifact.name == name
        )
        planned_native_evidence = (
            self.loadable
            and name == "nativeBinary"
            and self.runtime_artifact_selection.selected_package_mode
            == "source-package"
            and self.compatibility_report.native_binary_status == "planned"
            and artifact is not None
        )

        if not self.loadable:
            status = "blocked"
        elif artifact is None:
            status = "missing-metadata"
        elif selected_for_runtime:
            status = "selected-runtime-artifact"
        elif planned_native_evidence:
            status = "planned-evidence"
        elif artifact.exists:
            status = "required-sidecar-artifact"
        else:
            status = "missing-file"

        compatible = (
            self.loadable
            and artifact is not None
            and (artifact.exists or planned_native_evidence)
        )
        return {
            "role": name,
            "required": True,
            "declared": artifact is not None,
            "declaredBy": (
                f"manifest.artifacts.{name}" if artifact is not None else None
            ),
            "path": artifact.package_path if artifact is not None else None,
            "exists": artifact.exists if artifact is not None else False,
            "size": artifact.size if artifact is not None else None,
            "selectedForRuntime": selected_for_runtime,
            "bytesRequired": selected_for_runtime,
            "status": status,
            "compatible": compatible,
            "diagnostics": [
                diagnostic.to_summary()
                for diagnostic in self.diagnostics
                if _diagnostic_matches_artifact_role(diagnostic, name)
            ],
        }


def read_loader_plan(
    package_path: Path | str,
    loader_target: str,
    *,
    package_mode: str = "auto",
) -> RuntimeLoaderPlan:
    """Build a target-neutral runtime loader plan for a `.cglb` package.

    The package is read through :func:`read_compatibility_report`; this function
    does not parse CrossGL source, infer target support, or inspect compiler
    private IR. Required artifact selection follows the target contract reported
    by the package reader; primary runtime artifact selection follows package
    metadata and the requested package mode.
    """
    if not isinstance(loader_target, str) or not loader_target:
        raise PackageReadError("loader_target must be a non-empty string")

    report = _loader_compatibility_report(
        read_compatibility_report(package_path, loader_target=loader_target)
    )
    runtime_artifact_selection = select_runtime_artifact(
        report,
        target=loader_target,
        package_mode=package_mode,
    )
    selected_artifacts = _select_loader_artifacts(report)
    if not runtime_artifact_selection.selected:
        selected_artifacts = ()

    return RuntimeLoaderPlan(
        root=report.root,
        loader_target=loader_target,
        module=report.module,
        package_target=report.target,
        compatibility_report=report,
        runtime_artifact_selection=runtime_artifact_selection,
        selected_artifacts=selected_artifacts,
    )


def read_runtime_loader_plan_contract(
    package_path: Path | str,
    loader_target: str,
    *,
    package_mode: str = "auto",
) -> dict[str, Any]:
    """Read a `.cglb` package and return the published loader-plan contract."""
    return read_loader_plan(
        package_path,
        loader_target,
        package_mode=package_mode,
    ).to_runtime_loader_plan_contract()


def _runtime_loader_plan_target_or_null(target: str | None) -> str | None:
    if target in _RUNTIME_LOADER_PLAN_KNOWN_TARGETS:
        return target
    return None


def _runtime_loader_plan_package_format(package_format: str) -> str | None:
    if package_format in {"directory", "zip"}:
        return package_format
    return None


def _runtime_loader_plan_requirements_source(source: str | None) -> str | None:
    if source is None:
        return None
    return _RUNTIME_LOADER_PLAN_SCHEMA_REQUIREMENT_SOURCES.get(source)


def _runtime_loader_plan_package_artifact_requirements(
    report: PackageCompatibilityReport,
) -> dict[str, Any] | None:
    contract = report.target_contract
    if contract is None:
        return None

    evidence_ids = report.target_legalization_evidence.get(
        "packageArtifactRequirementEvidenceIds"
    )
    if not isinstance(evidence_ids, list):
        evidence_ids = []

    return {
        "target": contract.target,
        "packageMode": contract.package_mode,
        "requiredPathArtifacts": list(contract.required_artifacts),
        "requiresNativeBinaryStatus": contract.native_binary_status_required,
        "allowsPlannedNativeBinary": contract.planned_native_binary_may_be_absent,
        "allowsPlannedNativeSourceEvidence": (
            contract.allows_planned_native_source_evidence
        ),
        "evidenceIds": [item for item in evidence_ids if isinstance(item, str)],
    }


def _runtime_loader_plan_target_legalization_summary(
    report: PackageCompatibilityReport,
) -> dict[str, Any]:
    requirements = report.target_legalization_tool_requirements
    present = bool(requirements.get("present"))
    required_tool_ids = _runtime_loader_plan_string_list(
        requirements.get("requiredToolIds")
    )
    missing_tool_ids = _runtime_loader_plan_string_list(
        requirements.get("missingToolIds")
    )
    evidence_ids = _runtime_loader_plan_string_list(
        requirements.get("toolRequirementEvidenceIds")
    )
    package_mode = requirements.get("packageMode")

    return {
        "toolRequirementsPresent": present,
        "target": (
            _runtime_loader_plan_target_or_null(requirements.get("target"))
            if present
            else None
        ),
        "packageMode": (
            package_mode if package_mode in {"native", "source-package"} else None
        ),
        "requiredToolCount": len(required_tool_ids),
        "missingToolCount": len(missing_tool_ids),
        "requiredToolIds": required_tool_ids,
        "missingToolIds": missing_tool_ids,
        "toolRequirementEvidenceIds": evidence_ids,
    }


def _runtime_loader_plan_reflection_summary(
    plan: RuntimeLoaderPlan,
) -> dict[str, Any]:
    reflection = plan.reflection_resource_summary
    return {
        "resourceCount": reflection["resourceCount"],
        "targetResourceBindingCount": reflection["targetResourceBindingCount"],
        "targetFeatureCount": reflection["targetFeatureCount"],
        "entryPointCount": reflection["entryPointCount"],
        "workgroupSizeCount": reflection["workgroupSizeCount"],
        "threadgroupShapeSource": "reflection.workgroupSizes",
    }


def _runtime_loader_plan_contract_selected_artifact(
    plan: RuntimeLoaderPlan,
) -> dict[str, Any] | None:
    artifact = plan.runtime_artifact
    package_mode = plan.runtime_artifact_selection.selected_package_mode
    if artifact is None or package_mode is None:
        return None
    package_path = artifact.package_path
    return {
        "name": artifact.name,
        "path": package_path,
        "packageMode": package_mode,
        "packageRelative": (
            not PurePosixPath(package_path).is_absolute() and "\\" not in package_path
        ),
        "exists": artifact.exists,
    }


def _runtime_loader_plan_contract_runtime_artifact_selection(
    plan: RuntimeLoaderPlan,
    *,
    selected_artifact: dict[str, Any] | None,
    success: bool,
) -> dict[str, Any]:
    return {
        "schemaVersion": 1,
        "requestedTarget": _runtime_loader_plan_target_or_null(plan.loader_target),
        "requestedPackageMode": (
            plan.runtime_artifact_selection.requested_package_mode
        ),
        "packageTarget": _runtime_loader_plan_target_or_null(plan.package_target),
        "selectedTarget": plan.selected_target if success else None,
        "selected": success,
        "selectedPackageMode": (
            selected_artifact["packageMode"] if selected_artifact else None
        ),
        "sourceParsingRequired": plan.source_parsing_required,
        "compilerInvocationRequired": False,
        "deviceExecutionRequired": False,
        "sourceInputs": [],
        "artifact": selected_artifact,
    }


def _runtime_loader_plan_contract_diagnostics(
    plan: RuntimeLoaderPlan,
) -> list[dict[str, Any]]:
    return [
        _runtime_loader_plan_contract_diagnostic(
            diagnostic,
            requested_package_mode=plan.runtime_artifact_selection.requested_package_mode,
        )
        for diagnostic in plan.runtime_artifact_selection.diagnostics
    ]


def _runtime_loader_plan_contract_diagnostic(
    diagnostic: CompatibilityDiagnostic,
    *,
    requested_package_mode: str,
) -> dict[str, Any]:
    severity = diagnostic.severity
    if severity == "skip":
        severity = "error"
    if severity not in {"note", "warning", "error"}:
        severity = "error"

    summary: dict[str, Any] = {
        "severity": severity,
        "code": _runtime_loader_plan_contract_diagnostic_code(
            diagnostic,
            requested_package_mode=requested_package_mode,
        ),
        "message": diagnostic.message,
        "location": _runtime_loader_plan_diagnostic_location(diagnostic),
    }
    target = _runtime_loader_plan_diagnostic_target(diagnostic)
    if target is not None:
        summary["target"] = target
    return summary


def _runtime_loader_plan_contract_diagnostic_code(
    diagnostic: CompatibilityDiagnostic,
    *,
    requested_package_mode: str,
) -> str:
    if diagnostic.code == "package.target.loader_mismatch":
        return "package.runtime-plan.target-mismatch"
    if diagnostic.code == "package.target.unsupported":
        return "package.runtime-plan.unsupported-target"
    native_artifact_failure = (
        diagnostic.artifact
        in {
            "nativeArtifactDescriptor",
            "nativeBinary",
            "nativeBinaryStatus",
            "nativeProfile",
        }
        or diagnostic.code == "package.mode.unsupported"
    )
    source_artifact_failure = (
        diagnostic.artifact == "backendSource"
        or diagnostic.code == "package.mode.unsupported"
    )
    if requested_package_mode == "native" and (
        diagnostic.code
        in {
            "package.artifact.required_file_missing",
            "package.artifact.required_missing",
            "package.artifact.selection_missing",
            "package.artifact.selection_file_missing",
            "package.native_artifact_descriptor.required_missing",
            "package.native_binary_status.not_ready",
            "package.native_profile.required_missing",
        }
        and native_artifact_failure
    ):
        return "package.runtime-plan.native-artifact-unavailable"
    if requested_package_mode == "source-package" and (
        diagnostic.code
        in {
            "package.artifact.required_file_missing",
            "package.artifact.required_missing",
            "package.artifact.selection_missing",
            "package.artifact.selection_file_missing",
            "package.mode.unsupported",
        }
        and source_artifact_failure
    ):
        return "package.runtime-plan.source-artifact-unavailable"
    if requested_package_mode == "auto" and (
        diagnostic.code
        in {
            "package.artifact.required_file_missing",
            "package.artifact.required_missing",
            "package.artifact.selection_missing",
            "package.artifact.selection_file_missing",
            "package.mode.unsupported",
            "package.native_artifact_descriptor.required_missing",
            "package.native_binary_status.not_ready",
            "package.native_profile.required_missing",
        }
        and (native_artifact_failure or source_artifact_failure)
    ):
        return "package.runtime-plan.artifact-unavailable"
    return diagnostic.code


def _runtime_loader_plan_diagnostic_location(
    diagnostic: CompatibilityDiagnostic,
) -> dict[str, int | str]:
    return {
        "file": diagnostic.document or "package",
        "line": 0,
        "column": 0,
        "offset": 0,
        "length": 0,
        "endLine": 0,
        "endColumn": 0,
        "endOffset": 0,
    }


def _runtime_loader_plan_diagnostic_target(
    diagnostic: CompatibilityDiagnostic,
) -> str | None:
    for value in (diagnostic.actual, diagnostic.expected):
        if isinstance(value, str) and value in _RUNTIME_LOADER_PLAN_KNOWN_TARGETS:
            return value
    return None


def _runtime_loader_plan_contract_diagnostic_counts(
    diagnostics: list[dict[str, Any]],
) -> dict[str, int]:
    counts = {"note": 0, "warning": 0, "error": 0}
    for diagnostic in diagnostics:
        severity = diagnostic["severity"]
        if severity in counts:
            counts[severity] += 1
    return counts


def _runtime_loader_plan_string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, str)]


def _select_loader_artifacts(
    report: PackageCompatibilityReport,
) -> tuple[LoaderArtifactPlan, ...]:
    artifacts_by_name = {
        artifact.name: artifact for artifact in report.available_artifacts
    }
    selected: list[LoaderArtifactPlan] = []
    for artifact_name in report.required_artifacts:
        artifact = artifacts_by_name.get(artifact_name)
        if artifact is not None:
            selected.append(LoaderArtifactPlan.from_artifact(artifact))
    return tuple(selected)


def _loader_compatibility_report(
    report: PackageCompatibilityReport,
) -> PackageCompatibilityReport:
    """Return the package report with loader-boundary admission diagnostics."""
    diagnostics = _loader_boundary_diagnostics(report)
    if not diagnostics:
        return report

    existing = {
        (diagnostic.code, diagnostic.artifact, diagnostic.path)
        for diagnostic in report.diagnostics
    }
    new_diagnostics = tuple(
        diagnostic
        for diagnostic in diagnostics
        if (diagnostic.code, diagnostic.artifact, diagnostic.path) not in existing
    )
    if not new_diagnostics:
        return report

    return replace(report, diagnostics=(*report.diagnostics, *new_diagnostics))


def _loader_boundary_diagnostics(
    report: PackageCompatibilityReport,
) -> tuple[CompatibilityDiagnostic, ...]:
    if report.target_contract is None:
        return ()

    required_artifact_names = set(report.required_artifacts)
    diagnostics: list[CompatibilityDiagnostic] = []
    for artifact in report.available_artifacts:
        if artifact.name not in required_artifact_names:
            continue
        if not _is_crossgl_source_input_path(artifact.package_path):
            continue
        diagnostics.append(
            CompatibilityDiagnostic(
                code="package.artifact.source_input_leakage",
                message=(
                    f"manifest.artifacts.{artifact.name} points at a CrossGL "
                    "source input; runtime loader plans only consume generated "
                    "package artifacts"
                ),
                document="manifest",
                artifact=artifact.name,
                path=artifact.package_path,
                expected="generated package artifact",
                actual=artifact.package_path,
            )
        )
    return tuple(diagnostics)


def _is_crossgl_source_input_path(package_path: str) -> bool:
    return PurePosixPath(package_path).suffix.lower() in _CROSSGL_SOURCE_INPUT_SUFFIXES


def _diagnostic_phase_summary(
    diagnostics: tuple[CompatibilityDiagnostic, ...],
) -> dict[str, Any]:
    by_severity: dict[str, int] = {}
    for diagnostic in diagnostics:
        by_severity[diagnostic.severity] = by_severity.get(diagnostic.severity, 0) + 1
    return {
        "count": len(diagnostics),
        "bySeverity": dict(sorted(by_severity.items())),
        "codes": [diagnostic.code for diagnostic in diagnostics],
        "diagnostics": [diagnostic.to_summary() for diagnostic in diagnostics],
    }


def _compiler_metadata_compatible(report: PackageCompatibilityReport) -> bool:
    return (
        report.compiler_name == SUPPORTED_COMPILER_NAME
        and isinstance(report.compiler_version, str)
        and bool(report.compiler_version)
    )


def _schema_version_compatibility(
    version: Any,
    *,
    supported_version: int,
    required: bool,
) -> dict[str, Any]:
    return {
        "version": version,
        "supportedVersion": supported_version,
        "required": required,
        "compatible": version == supported_version,
    }


def _debug_metadata_version_compatibility(
    report: PackageCompatibilityReport,
) -> dict[str, Any]:
    availability = report.debug_metadata_availability
    declared = bool(availability.get("declared"))
    schema_summary = _schema_version_compatibility(
        availability.get("schemaVersion"),
        supported_version=SUPPORTED_DEBUG_METADATA_SCHEMA_VERSION,
        required=False,
    )
    if not declared:
        schema_summary["compatible"] = True
    return {
        "declared": declared,
        "path": availability.get("path"),
        **schema_summary,
        "compatible": availability.get("compatible") if declared else True,
    }


def _is_version_compatibility_diagnostic(
    diagnostic: CompatibilityDiagnostic,
) -> bool:
    return diagnostic.code in _VERSION_COMPATIBILITY_DIAGNOSTIC_CODES


def _version_compatibility_status(
    diagnostics: tuple[CompatibilityDiagnostic, ...],
) -> str:
    if any(
        diagnostic.code in _UNSUPPORTED_VERSION_COMPATIBILITY_DIAGNOSTIC_CODES
        for diagnostic in diagnostics
    ):
        return "unsupported-version"
    if diagnostics:
        return "incompatible"
    return "compatible"


def _diagnostic_matches_artifact_role(
    diagnostic: CompatibilityDiagnostic,
    role: str,
) -> bool:
    if diagnostic.artifact == role:
        return True
    return role == "nativeBinary" and diagnostic.artifact == "nativeBinaryStatus"


def _admission_section(section: Any) -> dict[str, Any]:
    if isinstance(section, dict):
        return dict(section)
    return {}


def _artifact_identity(
    artifact: Artifact | LoaderArtifactPlan | None,
) -> dict[str, Any] | None:
    if artifact is None:
        return None
    summary = artifact.to_summary()
    summary["declaredBy"] = f"manifest.artifacts.{artifact.name}"
    return summary


def _runtime_artifact_admission_reason(
    *,
    selection: RuntimeArtifactSelection,
    native_admission: dict[str, Any],
    source_package_fallback: dict[str, Any],
) -> str:
    blocking_reason = next(
        (
            diagnostic.code
            for diagnostic in (*selection.reject_reasons, *selection.skip_reasons)
        ),
        None,
    )
    if blocking_reason is not None:
        return blocking_reason
    if selection.selected_package_mode == "native":
        reason = native_admission.get("reason")
        if isinstance(reason, str):
            return reason
    if selection.selected_package_mode == "source-package":
        reason = source_package_fallback.get("reason")
        if isinstance(reason, str):
            return reason
    native_reason = native_admission.get("reason")
    if isinstance(native_reason, str):
        return native_reason
    fallback_reason = source_package_fallback.get("reason")
    if isinstance(fallback_reason, str):
        return fallback_reason
    return "runtime.artifact_admission.unavailable"


def _loader_metadata_documents(
    report: PackageCompatibilityReport,
) -> list[dict[str, Any]]:
    documents = [
        {
            "name": "manifest",
            "path": "manifest.json",
            "schemaVersion": report.manifest_schema_version,
            "compatible": (
                report.manifest_schema_version == SUPPORTED_PACKAGE_SCHEMA_VERSION
            ),
        },
        {
            "name": "reflection",
            "path": "reflection.json",
            "schemaVersion": report.reflection_schema_version,
            "compatible": (
                report.reflection_schema_version == SUPPORTED_PACKAGE_SCHEMA_VERSION
            ),
        },
        {
            "name": "diagnostics",
            "path": "diagnostics.json",
            "schemaVersion": report.diagnostics_schema_version,
            "compatible": (
                report.diagnostics_schema_version == SUPPORTED_PACKAGE_SCHEMA_VERSION
            ),
        },
    ]
    debug_metadata = report.debug_metadata_availability
    if debug_metadata.get("declared"):
        documents.append(
            {
                "name": "debugMetadata",
                "path": debug_metadata.get("path"),
                "schemaVersion": debug_metadata.get("schemaVersion"),
                "compatible": debug_metadata.get("compatible"),
            }
        )
    return documents


def _loader_required_metadata_inputs(
    report: PackageCompatibilityReport,
) -> list[dict[str, Any]]:
    return [
        _loader_required_metadata_input(
            name="manifest",
            path="manifest.json",
            schema_version=report.manifest_schema_version,
        ),
        _loader_required_metadata_input(
            name="reflection",
            path="reflection.json",
            schema_version=report.reflection_schema_version,
        ),
        _loader_required_metadata_input(
            name="diagnostics",
            path="diagnostics.json",
            schema_version=report.diagnostics_schema_version,
        ),
    ]


def _loader_required_metadata_input(
    *,
    name: str,
    path: str,
    schema_version: Any,
) -> dict[str, Any]:
    return {
        "name": name,
        "path": path,
        "required": True,
        "declaredBy": "package-root",
        "schemaVersion": schema_version,
        "supportedSchemaVersion": SUPPORTED_PACKAGE_SCHEMA_VERSION,
        "compatible": schema_version == SUPPORTED_PACKAGE_SCHEMA_VERSION,
    }


def _summarize_reflection_record(
    record: dict[str, Any],
    keys: tuple[str, ...],
) -> dict[str, Any]:
    return {key: record[key] for key in keys if key in record}


def _target_resource_binding_metadata_record(
    record: dict[str, Any],
) -> dict[str, Any]:
    abi = record.get("abi")
    abi_summary = dict(abi) if isinstance(abi, dict) else abi
    summary = {
        "target": record.get("target"),
        "stage": record.get("stage"),
        "entryPoint": record.get("entryPoint"),
        "name": record.get("name"),
        "kind": record.get("kind"),
        "bindingClass": record.get("bindingClass"),
        "descriptorType": record.get("descriptorType"),
        "set": record.get("set"),
        "binding": record.get("binding"),
        "argumentIndex": record.get("argumentIndex"),
        "abi": abi_summary,
        "identity": {
            "target": record.get("target"),
            "stage": record.get("stage"),
            "entryPoint": record.get("entryPoint"),
            "name": record.get("name"),
            "kind": record.get("kind"),
        },
    }
    evidence_id = record.get("evidenceId")
    if isinstance(evidence_id, str) and evidence_id:
        summary["evidenceId"] = evidence_id
    for field_name in (
        "arrayDimensions",
        "arrayElementCount",
        "storageImageFormat",
        "storageImageAccess",
    ):
        if field_name in record:
            summary[field_name] = record.get(field_name)
    return summary
