#!/usr/bin/env python3
"""Source-free runtime loader boundary example.

This example consumes only `.cglb` package metadata and declared artifact
paths. It does not parse CrossGL source, import compiler-private APIs, invoke
`cglc`, or execute any graphics API.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any, Callable

from runtime.directx_loader import plan_directx_native_loader
from runtime.loader import (
    RuntimeLoaderPlan,
    SourceFreeRuntimeArtifactHandoff,
    read_loader_plan,
)
from runtime.metal_loader import plan_metal_native_loader
from runtime.opengl_loader import plan_opengl_loader
from runtime.opengl_loader import plan_opengl_native_loader
from runtime.package_reader import PackageReadError
from runtime.vulkan_loader import plan_vulkan_native_loader


DEVICE_EXECUTION_MODE = "not-executed"
NativeAdmissionPlanner = Callable[[Path | str], Any]
NATIVE_ADMISSION_PLANNERS: dict[str, NativeAdmissionPlanner] = {
    "directx": plan_directx_native_loader,
    "metal": plan_metal_native_loader,
    "opengl": plan_opengl_native_loader,
    "vulkan": plan_vulkan_native_loader,
}


def inspect_source_free_package(
    package_path: Path | str,
    loader_target: str,
    *,
    native_admission: bool = False,
) -> dict[str, Any]:
    """Return the metadata-only loader handoff for a package directory.

    The returned dictionary is deliberately small and deterministic so runtime
    consumers can see the boundary: admission comes from manifest/reflection
    metadata, the selected artifact is a declared package artifact, and
    incompatible packages carry structured diagnostics instead of falling back
    to source parsing.
    """
    plan = read_loader_plan(package_path, loader_target)
    if (
        loader_target == "opengl"
        and plan.compatibility_report.native_binary_status == "validated"
    ):
        plan = plan_opengl_loader(package_path)
    runtime_artifact_handoff = plan.runtime_artifact_handoff()
    summary = _plan_summary(
        plan,
        runtime_artifact_handoff=runtime_artifact_handoff,
    )
    if native_admission:
        summary["nativeBackendAdmission"] = _native_backend_admission_summary(
            package_path,
            loader_target,
            package_artifact_requirements_source=summary[
                "packageArtifactRequirementsSource"
            ],
            package_artifact_requirements=summary["packageArtifactRequirements"],
            target_legalization_evidence=summary["targetLegalizationEvidence"],
            target_legalization_tool_requirements=summary[
                "targetLegalizationToolRequirements"
            ],
        )
    if not plan.loadable:
        return summary

    if runtime_artifact_handoff is None:
        runtime_artifact_handoff = plan.require_runtime_artifact_handoff()
    runtime_artifact = runtime_artifact_handoff.artifact
    reflection = plan.compatibility_report.reflection
    summary.update(
        {
            "runtimeArtifactHandoff": runtime_artifact_handoff.to_summary(),
            "selectedArtifact": runtime_artifact.to_summary(),
            "selectedArtifacts": [
                artifact.to_summary() for artifact in plan.selected_artifacts
            ],
            "reflectionHandoff": {
                "entryPoint": _entry_point_summary(
                    _first_record(reflection.get("entryPoints"))
                ),
                "targetResourceBinding": _target_binding_summary(
                    _first_target_binding(reflection, loader_target)
                ),
            },
        }
    )
    return summary


def _plan_summary(
    plan: RuntimeLoaderPlan,
    *,
    runtime_artifact_handoff: SourceFreeRuntimeArtifactHandoff | None = None,
) -> dict[str, Any]:
    metadata_contract = plan.metadata_contract_summary
    return {
        "schemaVersion": 1,
        "package": str(plan.root),
        "module": plan.module,
        "packageTarget": plan.package_target,
        "loaderTarget": plan.loader_target,
        "availableTargets": list(plan.compatibility_report.available_targets),
        "status": plan.compatibility_report.status,
        "loadable": plan.loadable,
        "metadataOnly": metadata_contract["metadataOnly"],
        "metadataInputs": metadata_contract["metadataDocuments"],
        "sourceInputs": metadata_contract["sourceInputs"],
        "packageArtifactRequirementsSource": metadata_contract["contractSource"],
        "packageArtifactRequirements": metadata_contract["requirements"],
        "targetLegalizationEvidence": metadata_contract["targetLegalizationEvidence"],
        "targetLegalizationToolRequirements": (
            metadata_contract["targetLegalizationToolRequirements"]
        ),
        "sourceParsingRequired": plan.source_parsing_required,
        "compilerInvocationRequired": metadata_contract["compilerInvocationRequired"],
        "deviceExecutionRequired": metadata_contract["deviceExecutionRequired"],
        "deviceExecution": DEVICE_EXECUTION_MODE,
        "runtimeArtifactAdmission": _runtime_artifact_admission_summary(
            plan,
            metadata_contract,
            runtime_artifact_handoff=runtime_artifact_handoff,
        ),
        "runtimeArtifactHandoff": (
            runtime_artifact_handoff.to_summary()
            if runtime_artifact_handoff is not None
            else None
        ),
        "selectedArtifact": None,
        "selectedArtifacts": [],
        "reflectionHandoff": {
            "entryPoint": None,
            "targetResourceBinding": None,
        },
        "diagnostics": [diagnostic.to_summary() for diagnostic in plan.diagnostics],
    }


def _runtime_artifact_admission_summary(
    plan: RuntimeLoaderPlan,
    metadata_contract: dict[str, Any],
    *,
    runtime_artifact_handoff: SourceFreeRuntimeArtifactHandoff | None = None,
) -> dict[str, Any]:
    selection = plan.runtime_artifact_selection
    admission = selection.admission or {}
    return {
        "schemaVersion": 1,
        "decision": admission.get("decision"),
        "requestedPackageMode": selection.requested_package_mode,
        "selectedPackageMode": selection.selected_package_mode,
        "target": admission.get("target"),
        "native": admission.get("native"),
        "sourcePackageFallback": admission.get("sourcePackageFallback"),
        "selectedArtifact": _selected_artifact_identity(
            plan,
            runtime_artifact_handoff=runtime_artifact_handoff,
        ),
        "packageArtifactRequirementsSource": metadata_contract["contractSource"],
        "packageArtifactRequirements": metadata_contract["requirements"],
        "targetLegalizationEvidence": metadata_contract["targetLegalizationEvidence"],
        "targetLegalizationToolRequirements": (
            metadata_contract["targetLegalizationToolRequirements"]
        ),
        "sourceFreeInvariants": {
            "metadataOnly": metadata_contract["metadataOnly"],
            "sourceInputs": metadata_contract["sourceInputs"],
            "sourceParsingRequired": plan.source_parsing_required,
            "compilerInvocationRequired": metadata_contract[
                "compilerInvocationRequired"
            ],
            "deviceExecutionRequired": metadata_contract["deviceExecutionRequired"],
            "deviceExecution": DEVICE_EXECUTION_MODE,
        },
    }


def _selected_artifact_identity(
    plan: RuntimeLoaderPlan,
    *,
    runtime_artifact_handoff: SourceFreeRuntimeArtifactHandoff | None = None,
) -> dict[str, Any] | None:
    if runtime_artifact_handoff is not None:
        return {
            "name": runtime_artifact_handoff.artifact_name,
            "path": runtime_artifact_handoff.package_path,
            "declaredBy": (
                f"manifest.artifacts.{runtime_artifact_handoff.artifact_name}"
            ),
            "exists": runtime_artifact_handoff.artifact.exists,
            "selectedPackageMode": runtime_artifact_handoff.selected_package_mode,
        }
    artifact = plan.runtime_artifact
    if artifact is None:
        return None
    return {
        "name": artifact.name,
        "path": artifact.package_path,
        "declaredBy": f"manifest.artifacts.{artifact.name}",
        "exists": artifact.exists,
        "selectedPackageMode": plan.runtime_artifact_selection.selected_package_mode,
    }


def _native_backend_admission_summary(
    package_path: Path | str,
    loader_target: str,
    *,
    package_artifact_requirements_source: str | None,
    package_artifact_requirements: dict[str, Any],
    target_legalization_evidence: dict[str, Any],
    target_legalization_tool_requirements: dict[str, Any],
) -> dict[str, Any]:
    planner = NATIVE_ADMISSION_PLANNERS.get(loader_target)
    if planner is None:
        return {
            "schemaVersion": 1,
            "requested": True,
            "available": False,
            "target": loader_target,
            "decision": "unavailable",
            "status": "planner-unavailable",
            "reason": "runtime.native_backend_loader.planner_unavailable",
            "sourceParsingRequired": False,
            "compilerInvocationRequired": False,
            "deviceExecutionRequired": False,
            "deviceExecution": DEVICE_EXECUTION_MODE,
            "nativeAdmission": None,
            "nativeArtifact": None,
            "nativeArtifactDescriptor": None,
            "artifactInputs": [],
            "packageArtifactRequirementsSource": (package_artifact_requirements_source),
            "packageArtifactRequirements": package_artifact_requirements,
            "targetLegalizationEvidence": target_legalization_evidence,
            "targetLegalizationToolRequirements": (
                target_legalization_tool_requirements
            ),
            "reflection": {
                "entryPointCount": 0,
                "resourceCount": 0,
                "targetResourceBindingCount": 0,
            },
            "sourceInputs": [],
            "rejectReasons": [],
        }

    planner_summary = planner(package_path).to_summary()
    reflection = planner_summary.get("reflection")
    if not isinstance(reflection, dict):
        reflection = {}
    native_admission = planner_summary.get("nativeAdmission")
    decision = (
        native_admission.get("decision") if isinstance(native_admission, dict) else None
    )
    if not isinstance(decision, str):
        decision = "accepted" if planner_summary.get("ready") else "rejected"

    return {
        "schemaVersion": 1,
        "requested": True,
        "available": True,
        "loader": planner_summary.get("loader"),
        "target": planner_summary.get("target"),
        "packageTarget": planner_summary.get("packageTarget"),
        "decision": decision,
        "status": planner_summary.get("status"),
        "ready": planner_summary.get("ready"),
        "loadable": planner_summary.get("loadable"),
        "sourceParsingRequired": planner_summary.get("sourceParsingRequired"),
        "compilerInvocationRequired": planner_summary.get("compilerInvocationRequired"),
        "deviceExecutionRequired": planner_summary.get("deviceExecutionRequired"),
        "deviceExecution": DEVICE_EXECUTION_MODE,
        "nativeAdmission": native_admission,
        "targetNativeAdmission": planner_summary.get(
            f"{loader_target}NativeAdmission",
        ),
        "nativeApiBoundary": planner_summary.get(
            f"{loader_target}NativeApiBoundary",
        ),
        "nativeArtifact": planner_summary.get("nativeArtifact"),
        "nativeArtifactDescriptor": planner_summary.get("nativeArtifactDescriptor"),
        "nativeProfile": planner_summary.get("vulkanNativeProfile"),
        "artifactInputs": planner_summary.get("artifactInputs", []),
        "packageArtifactRequirementsSource": package_artifact_requirements_source,
        "packageArtifactRequirements": package_artifact_requirements,
        "targetLegalizationEvidence": target_legalization_evidence,
        "targetLegalizationToolRequirements": target_legalization_tool_requirements,
        "reflection": {
            "entryPointCount": reflection.get("entryPointCount", 0),
            "resourceCount": reflection.get("resourceCount", 0),
            "targetResourceBindingCount": reflection.get(
                "targetResourceBindingCount",
                0,
            ),
        },
        "sourceInputs": planner_summary.get("sourceInputs", []),
        "rejectReasons": planner_summary.get("rejectReasons", []),
    }


def _first_record(value: Any) -> dict[str, Any] | None:
    if not isinstance(value, list):
        return None
    for record in value:
        if isinstance(record, dict):
            return record
    return None


def _first_target_binding(
    reflection: dict[str, Any],
    loader_target: str,
) -> dict[str, Any] | None:
    bindings = reflection.get("targetResourceBindings")
    if not isinstance(bindings, list):
        return None
    for binding in bindings:
        if isinstance(binding, dict) and binding.get("target") == loader_target:
            return binding
    return None


def _entry_point_summary(record: dict[str, Any] | None) -> dict[str, Any] | None:
    if record is None:
        return None
    return {
        "stage": record.get("stage"),
        "sourceName": record.get("sourceName"),
        "backendName": record.get("backendName"),
    }


def _target_binding_summary(record: dict[str, Any] | None) -> dict[str, Any] | None:
    if record is None:
        return None
    summary = {
        "stage": record.get("stage"),
        "entryPoint": record.get("entryPoint"),
        "name": record.get("name"),
        "kind": record.get("kind"),
        "bindingClass": record.get("bindingClass"),
        "descriptorType": record.get("descriptorType"),
        "abi": record.get("abi"),
    }
    for field_name in (
        "arrayDimensions",
        "arrayElementCount",
        "storageImageFormat",
        "storageImageAccess",
    ):
        if field_name in record:
            summary[field_name] = record.get(field_name)
    return summary


def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Inspect a CrossGL .cglb package directory at the runtime loader "
            "boundary without parsing CrossGL source."
        )
    )
    parser.add_argument("package", type=Path, help="Path to a .cglb directory")
    parser.add_argument("loader_target", help="Runtime loader target to admit")
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print the metadata-only loader handoff as JSON",
    )
    parser.add_argument(
        "--native-admission",
        action="store_true",
        help=(
            "Include backend-native admission metadata from the target native "
            "loader planner without executing graphics APIs"
        ),
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(sys.argv[1:] if argv is None else argv)
    try:
        summary = inspect_source_free_package(
            args.package,
            args.loader_target,
            native_admission=args.native_admission,
        )
    except PackageReadError as error:
        print(f"crossgl-runtime-source-free-loader: {error}", file=sys.stderr)
        return 1

    if args.json:
        print(json.dumps(summary, indent=2, sort_keys=True))
    else:
        artifact = summary["selectedArtifact"]
        artifact_text = artifact["path"] if artifact is not None else "none"
        print(
            f"{summary['module']} [{summary['status']}]: "
            f"loader={summary['loaderTarget']} artifact={artifact_text}"
        )
    return 0 if summary["loadable"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
