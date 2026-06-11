#!/usr/bin/env python3
"""Check compiler-native package verification behavior with synthetic packages."""

import argparse
import copy
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

from check_package_integrity_fixtures import (
    add_native_artifact_descriptor,
    base_reflection,
    delete_artifact_path,
    duplicate_manifest_artifact,
    hir_source_map_with_all_record_kinds,
    hir_source_map_with_expression,
    mark_native_artifact_validated,
    make_package,
    package_path,
    rewrite_debug_metadata_locations,
    rewrite_manifest,
    STORAGE_IMAGE_ARRAY_ELEMENT_COUNT,
    write_nonuniform_diagnostics,
    write_nonuniform_reflection,
    write_storage_image_reflection,
    write_json,
)
from fixture_parallelism import extend_errors_from_fixture_tasks
from package_fixture_json_contracts import (
    expect_array,
    expect_equal,
    expect_object,
    expect_package_path_contract,
    expect_package_summary_manifest_contract,
)
from source_location_fixture_checks import (
    expect_location_overlaps_text,
    expect_location_span_coherent,
)
from package_target_contracts import TARGET_REQUIRED_ARTIFACTS


SEVERITIES = ("note", "warning", "error")
CROSSGL_PACKAGE_VERIFY_FIXTURE_JOBS = "CROSSGL_PACKAGE_VERIFY_FIXTURE_JOBS"
CROSSGL_CI_JOBS = "CROSSGL_CI_JOBS"
VERIFY_DIAGNOSTIC_CODE_PREFIX = "package.verify."
LEGACY_REQUIREMENTS_FALLBACK_CODE = (
    "package.verify.legacy-artifact-requirements-fallback"
)
SYNTHETIC_STORAGE_IMAGE_ARRAY_SOURCE_COORDINATES = {
    "maskAtlases": {"stage": "compute", "set": 0, "binding": 1},
    "unsignedAtlases": {"stage": "compute", "set": 0, "binding": 1},
}
GRAPHICS_ABI_FIXTURE_PATH = "metadata/graphics-abi.json"
GRAPHICS_ABI_FIXTURE_EVIDENCE_ID = (
    "target-legalization.v1.directx.resource-binding.fragment.fragment_fs_main.albedo"
)
GRAPHICS_ABI_FIXTURE_DRIFTED_EVIDENCE_ID = GRAPHICS_ABI_FIXTURE_EVIDENCE_ID + ".stale"


def positive_jobs(value):
    try:
        jobs = int(value)
    except (TypeError, ValueError) as exc:
        raise argparse.ArgumentTypeError("must be a positive integer") from exc
    if jobs < 1:
        raise argparse.ArgumentTypeError("must be a positive integer")
    return jobs


def jobs_from_environment(parser):
    for name in (CROSSGL_PACKAGE_VERIFY_FIXTURE_JOBS, CROSSGL_CI_JOBS):
        value = os.environ.get(name)
        if value is None or not value.strip():
            continue
        try:
            return positive_jobs(value)
        except argparse.ArgumentTypeError:
            parser.error(f"{name} must be a positive integer")
    return 1


def ordered_unique_strings(values):
    ordered = []
    seen = set()
    for value in values:
        if not isinstance(value, str) or not value or value in seen:
            continue
        ordered.append(value)
        seen.add(value)
    return ordered


def target_feature_evidence_ids(features):
    evidence_ids = []
    for feature in features:
        values = feature.get("evidenceIds", [])
        if isinstance(values, list):
            evidence_ids.extend(values)
    return ordered_unique_strings(evidence_ids)


def package_artifact_requirement_evidence_ids(requirements):
    target = requirements.get("target")
    package_mode = requirements.get("packageMode")
    required_artifacts = requirements.get("requiredPathArtifacts", [])
    evidence_ids = [f"target-legalization.v1.{target}.package-artifacts.{package_mode}"]
    evidence_ids.extend(
        f"target-legalization.v1.{target}.package-artifact.required.{artifact}"
        for artifact in required_artifacts
    )
    if requirements.get("requiresNativeBinaryStatus"):
        evidence_ids.append(
            f"target-legalization.v1.{target}."
            "package-artifact.native-binary-status.required"
        )
    if requirements.get("allowsPlannedNativeBinary"):
        evidence_ids.append(
            f"target-legalization.v1.{target}."
            "package-artifact.planned-native-binary.allowed"
        )
    if requirements.get("allowsPlannedNativeSourceEvidence"):
        evidence_ids.append(
            f"target-legalization.v1.{target}."
            "package-artifact.planned-native-source-evidence.allowed"
        )
    return evidence_ids


def manifest_with_required_path_artifacts(manifest, required_path_artifacts):
    updated = copy.deepcopy(manifest)
    requirements = updated["packageArtifactRequirements"]
    requirements["requiredPathArtifacts"] = list(required_path_artifacts)
    requirements["evidenceIds"] = package_artifact_requirement_evidence_ids(
        requirements
    )
    return updated


def manifest_with_requirement_evidence_ids(manifest, evidence_ids):
    updated = copy.deepcopy(manifest)
    updated["packageArtifactRequirements"]["evidenceIds"] = list(evidence_ids)
    return updated


def run_verify(cglc, package, json_output=False, source=None):
    command = [str(cglc), "package", "verify", str(package)]
    if source is not None:
        command.extend(["--source", str(source)])
    if json_output:
        command.append("--json")
    return subprocess.run(
        command,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )


def run_integrity_validator(root, cglc, package, source=None):
    command = [
        sys.executable,
        str(root / "tools" / "validate_package_integrity.py"),
        "--package",
        str(package),
        "--package-verifier",
        str(cglc),
    ]
    if source is not None:
        command.extend(["--source", str(source)])
    return subprocess.run(
        command,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )


def validate_schema(root, tmp_dir, case_name, verify_json):
    instance_path = tmp_dir / f"{case_name}.package-verify.json"
    instance_path.write_text(verify_json, encoding="utf-8")
    result = subprocess.run(
        [
            sys.executable,
            str(root / "tools" / "validate_json_schema.py"),
            "--schema",
            str(root / "docs" / "schemas" / "package-verify-v1.schema.json"),
            "--instance",
            str(instance_path),
        ],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if result.returncode != 0:
        return [
            f"{case_name}: package verify JSON failed schema validation: "
            f"{result.stderr}{result.stdout}".strip()
        ]
    return []


def read_artifact_json(package, manifest, artifact_name):
    artifact_path = manifest.get("artifacts", {}).get(artifact_name)
    if not isinstance(artifact_path, str):
        return None
    path = package_path(package, artifact_path)
    if not path.is_file():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def graphics_abi_source_map_ref(line=1):
    return {
        "file": "GraphicsAbiReleaseAuthority.cgl",
        "line": line,
        "column": 1,
        "offset": line - 1,
        "length": 1,
        "endLine": line,
        "endColumn": 2,
        "endOffset": line,
    }


def graphics_abi_release_reflection(manifest):
    return {
        "schemaVersion": 1,
        "module": manifest["module"],
        "target": manifest["target"],
        "nativeBinary": manifest["artifacts"]["nativeBinary"],
        "entryPoints": [
            {
                "stage": "vertex",
                "sourceName": "vs_main",
                "backendName": "vertex_vs_main",
                "returnType": "FragmentInput",
                "parameters": [],
            },
            {
                "stage": "fragment",
                "sourceName": "fs_main",
                "backendName": "fragment_fs_main",
                "returnType": "FragmentOutput",
                "parameters": [
                    {
                        "name": "input",
                        "type": "FragmentInput",
                    }
                ],
            },
        ],
        "structs": [
            {
                "name": "FragmentInput",
                "fields": [
                    {
                        "name": "uv",
                        "type": "float2",
                    }
                ],
            },
            {
                "name": "FragmentOutput",
                "fields": [
                    {
                        "name": "color",
                        "type": "float4",
                    }
                ],
            },
        ],
        "resources": [
            {
                "stage": "fragment",
                "name": "albedo",
                "kind": "texture",
                "type": "Texture2D",
                "set": 0,
                "binding": 0,
                "addressSpace": "shader-resource",
            }
        ],
        "targetResourceBindings": [
            {
                "target": manifest["target"],
                "stage": "fragment",
                "entryPoint": "fragment_fs_main",
                "name": "albedo",
                "kind": "texture",
                "sourceType": "Texture2D",
                "addressSpace": "shader-resource",
                "abi": "registerBinding",
                "bindingClass": "srv",
                "descriptorType": "SRV",
                "set": 0,
                "binding": 0,
                "argumentIndex": 0,
                "arrayDimensions": [],
                "evidenceId": GRAPHICS_ABI_FIXTURE_EVIDENCE_ID,
            }
        ],
        "pushConstants": [],
        "functionConstants": [],
        "vertexLayouts": [
            {
                "entryPoint": "vertex_vs_main",
                "attributes": [
                    {
                        "name": "position",
                        "type": "float3",
                        "location": 0,
                    },
                    {
                        "name": "uv",
                        "type": "float2",
                        "location": 1,
                    },
                ],
            }
        ],
        "workgroupSizes": [],
        "manualTextureCompareKernelSummary": {
            "totalCount": 0,
            "staticNormalizedCount": 0,
            "staticNonNormalizedCount": 0,
            "staticZeroSumCount": 0,
            "dynamicCount": 0,
        },
        "manualTextureCompareKernels": [],
        "targetFeatures": [],
    }


def graphics_abi_release_sidecar(manifest):
    return {
        "schemaVersion": 1,
        "module": manifest["module"],
        "target": manifest["target"],
        "entryPoints": [
            {
                "stage": "vertex",
                "sourceName": "vs_main",
                "backendName": "vertex_vs_main",
                "sourceMapRef": graphics_abi_source_map_ref(1),
            },
            {
                "stage": "fragment",
                "sourceName": "fs_main",
                "backendName": "fragment_fs_main",
                "sourceMapRef": graphics_abi_source_map_ref(2),
            },
        ],
        "vertexInputs": [
            {
                "stage": "vertex",
                "entryPoint": "vertex_vs_main",
                "name": "position",
                "type": "float3",
                "location": 0,
                "format": "float3",
                "semantic": "POSITION",
            },
            {
                "stage": "vertex",
                "entryPoint": "vertex_vs_main",
                "name": "uv",
                "type": "float2",
                "location": 1,
                "format": "float2",
                "semantic": "TEXCOORD0",
            },
        ],
        "varyings": [
            {
                "interpolation": "smooth",
                "producer": {
                    "stage": "vertex",
                    "entryPoint": "vertex_vs_main",
                    "name": "uv",
                    "type": "float2",
                    "location": 0,
                    "direction": "output",
                },
                "consumer": {
                    "stage": "fragment",
                    "entryPoint": "fragment_fs_main",
                    "name": "uv",
                    "type": "float2",
                    "location": 0,
                    "direction": "input",
                },
            }
        ],
        "fragmentOutputs": [
            {
                "stage": "fragment",
                "entryPoint": "fragment_fs_main",
                "name": "color",
                "type": "float4",
                "location": 0,
                "format": "rgba32f",
                "semantic": "SV_Target0",
            }
        ],
        "builtins": [],
        "resources": [
            {
                "stage": "fragment",
                "name": "albedo",
                "kind": "texture",
                "type": "Texture2D",
                "set": 0,
                "binding": 0,
                "addressSpace": "shader-resource",
                "sourceMapRef": graphics_abi_source_map_ref(3),
            }
        ],
        "abiRecords": [
            {
                "target": manifest["target"],
                "stage": "fragment",
                "entryPoint": "fragment_fs_main",
                "name": "albedo",
                "kind": "texture",
                "sourceType": "Texture2D",
                "addressSpace": "shader-resource",
                "abi": "registerBinding",
                "bindingClass": "srv",
                "descriptorType": "SRV",
                "set": 0,
                "binding": 0,
                "argumentIndex": 0,
                "arrayDimensions": [],
                "evidenceId": GRAPHICS_ABI_FIXTURE_EVIDENCE_ID,
                "sourceMapRef": graphics_abi_source_map_ref(4),
            }
        ],
    }


def make_graphics_abi_release_package(tmp_dir, case_name, *, include_graphics_abi=True):
    package, source, manifest = make_package(tmp_dir, case_name)
    write_json(package / "reflection.json", graphics_abi_release_reflection(manifest))
    if include_graphics_abi:
        manifest["artifacts"]["graphicsAbi"] = GRAPHICS_ABI_FIXTURE_PATH
        write_json(
            package_path(package, GRAPHICS_ABI_FIXTURE_PATH),
            graphics_abi_release_sidecar(manifest),
        )
        rewrite_manifest(package, manifest)
    return package, source, manifest


def drift_graphics_abi_evidence(package, manifest):
    sidecar = read_artifact_json(package, manifest, "graphicsAbi")
    if not isinstance(sidecar, dict):
        raise AssertionError("graphics ABI fixture sidecar must be present")
    records = sidecar.get("abiRecords")
    if not isinstance(records, list) or not records:
        raise AssertionError("graphics ABI fixture must contain abiRecords")
    records[0]["evidenceId"] = GRAPHICS_ABI_FIXTURE_DRIFTED_EVIDENCE_ID
    write_json(package_path(package, manifest["artifacts"]["graphicsAbi"]), sidecar)
    return sidecar


def source_remap_provenance(manifest, *, mapping_granularity="source-span"):
    return {
        "schemaVersion": 1,
        "kind": "crossgl.sourceRemapProvenance",
        "contractVersion": "source-remap-provenance-v1",
        "target": manifest["target"],
        "generatedFile": "generated/from-translator.cgl",
        "mappingGranularity": mapping_granularity,
        "mappingCount": 1,
        "sourceRemap": {
            "path": "tests/fixtures/source-remap-v1-full-file.json",
            "sha256": {
                "algorithm": "sha256",
                "value": (
                    "7ebc4d584f4b6f19b8eef3c47c1fe799361dd44e397d969df7899f9e05b6041b"
                ),
            },
            "sizeBytes": 592,
        },
    }


def backend_source_map(
    manifest,
    *,
    target=None,
    module=None,
    mapping_granularity="statement",
    source_backend="crossgl-hir",
    target_backend="hlsl",
    backend_language="hlsl",
    backend_line_count=1,
    mapping_count=1,
    mapping_end_line=1,
    source_remap=None,
):
    document = {
        "schemaVersion": 1,
        "kind": "crossgl.backendSourceMap",
        "target": target or manifest["target"],
        "module": module or manifest["module"],
        "mappingGranularity": mapping_granularity,
        "sourceBackend": source_backend,
        "targetBackend": target_backend,
        "backend": {
            "language": backend_language,
            "lineCount": backend_line_count,
        },
        "mappingCount": mapping_count,
        "mappings": [
            {
                "index": 0,
                "stage": "compute",
                "entryPoint": "main",
                "function": "main",
                "statementKind": "return",
                "backend": {
                    "startLine": 1,
                    "endLine": mapping_end_line,
                },
                "location": {
                    "file": "StorageBufferComputeShader.cgl",
                    "line": 1,
                    "column": 1,
                    "offset": 0,
                    "length": 1,
                    "endLine": 1,
                    "endColumn": 2,
                    "endOffset": 1,
                },
            }
        ],
    }
    if source_remap is not None:
        document["sourceRemap"] = source_remap
    return document


def source_remap_metadata_from_provenance(manifest):
    provenance = source_remap_provenance(manifest)
    source_remap = provenance["sourceRemap"]
    metadata = {
        "path": manifest["artifacts"]["sourceRemap"],
        "sha256": source_remap["sha256"],
        "sizeBytes": source_remap["sizeBytes"],
        "generatedFile": provenance["generatedFile"],
        "mappingCount": provenance["mappingCount"],
    }
    for field in ("target", "mappingGranularity", "sourceBackend", "variant"):
        if field in source_remap:
            metadata[field] = source_remap[field]
    return metadata


def add_backend_source_map(package, manifest, *, mutate=None, source_remap=None):
    path = f"backend/{manifest['target']}/{manifest['module']}.backend-source-map.json"
    manifest["artifacts"]["backendSourceMap"] = path
    document = backend_source_map(manifest, source_remap=source_remap)
    if mutate is not None:
        mutate(document)
    write_json(package_path(package, path), document)
    rewrite_manifest(package, manifest)
    return document


def target_record(records, target):
    for record in records or []:
        if isinstance(record, dict) and record.get("target") == target:
            return record
    return {}


def first_present(*values):
    for value in values:
        if value is not None:
            return value
    return None


TARGET_LEGALIZATION_TOOL_FIELD_PAIRS = (
    ("requiredToolCount", "selectedTargetRequiredToolCount", "requiredToolCount"),
    ("missingToolCount", "selectedTargetMissingToolCount", "missingToolCount"),
    ("requiredToolIds", "selectedTargetRequiredToolIds", "requiredToolIds"),
    ("missingToolIds", "selectedTargetMissingToolIds", "missingToolIds"),
    (
        "optionalNativeToolMissing",
        "selectedTargetOptionalNativeToolMissing",
        "optionalNativeToolMissing",
    ),
    (
        "optionalNativeToolStatus",
        "selectedTargetOptionalNativeToolStatus",
        "optionalNativeToolStatus",
    ),
    (
        "toolRequirementEvidenceIds",
        "selectedTargetToolRequirementEvidenceIds",
        "toolRequirementEvidenceIds",
    ),
)


def target_tool_sidecars_drift(left, right):
    for field, _, _ in TARGET_LEGALIZATION_TOOL_FIELD_PAIRS:
        left_value = left.get(field)
        right_value = right.get(field)
        if (
            left_value is not None
            and right_value is not None
            and left_value != right_value
        ):
            return True
    return False


def target_tool_sidecar_matches_manifest(manifest_tool_requirements, sidecar):
    if not manifest_tool_requirements.get("present") or not sidecar.get(
        "artifactExists"
    ):
        return None
    for field, _, _ in TARGET_LEGALIZATION_TOOL_FIELD_PAIRS:
        if sidecar.get(field) is None or sidecar.get(
            field
        ) != manifest_tool_requirements.get(field):
            return False
    return True


def record_by_name(records, name):
    for record in records or []:
        if isinstance(record, dict) and record.get("name") == name:
            return record
    return None


def reflection_source_coordinate(record):
    return {
        "stage": record.get("stage"),
        "set": record.get("set"),
        "binding": record.get("binding"),
    }


def reflection_target_binding_coordinate(target, record):
    if target == "directx":
        return {
            "target": record.get("target"),
            "stage": record.get("stage"),
            "entryPoint": record.get("entryPoint"),
            "abi": record.get("abi"),
            "addressSpace": record.get("addressSpace"),
            "registerClass": record.get("bindingClass"),
            "descriptorType": record.get("descriptorType"),
            "registerSpace": record.get("set"),
            "register": record.get("binding"),
            "argumentIndex": record.get("argumentIndex"),
        }
    if target == "opengl":
        return {
            "target": record.get("target"),
            "stage": record.get("stage"),
            "entryPoint": record.get("entryPoint"),
            "abi": record.get("abi"),
            "addressSpace": record.get("addressSpace"),
            "bindingClass": record.get("bindingClass"),
            "programResourceBinding": record.get("argumentIndex"),
            "sourceSet": record.get("set"),
            "sourceBinding": record.get("binding"),
        }
    if target == "metal":
        return {
            "target": record.get("target"),
            "stage": record.get("stage"),
            "entryPoint": record.get("entryPoint"),
            "abi": record.get("abi"),
            "addressSpace": record.get("addressSpace"),
            "bindingClass": record.get("bindingClass"),
            "argumentIndex": record.get("argumentIndex"),
            "sourceSet": record.get("set"),
            "sourceBinding": record.get("binding"),
        }
    if target == "vulkan":
        return {
            "target": record.get("target"),
            "stage": record.get("stage"),
            "entryPoint": record.get("entryPoint"),
            "abi": record.get("abi"),
            "addressSpace": record.get("addressSpace"),
            "bindingClass": record.get("bindingClass"),
            "descriptorType": record.get("descriptorType"),
            "storageClass": record.get("storageClass"),
            "descriptorSet": record.get("set"),
            "descriptorBinding": record.get("binding"),
        }
    raise ValueError(f"unsupported storage-image parity target {target!r}")


def expected_storage_image_array_target_coordinate(target, resource):
    source_set = resource.get("set")
    source_binding = resource.get("binding")
    if target == "directx":
        return {
            "target": "directx",
            "stage": "compute",
            "entryPoint": "compute_main",
            "abi": "registerBinding",
            "addressSpace": "unordered-access",
            "registerClass": "uav",
            "descriptorType": "UAV",
            "registerSpace": source_set,
            "register": source_binding,
            "argumentIndex": source_binding,
        }
    if target == "opengl":
        return {
            "target": "opengl",
            "stage": "compute",
            "entryPoint": "compute_main",
            "abi": "programResourceBinding",
            "addressSpace": "image",
            "bindingClass": "image",
            "programResourceBinding": source_binding,
            "sourceSet": source_set,
            "sourceBinding": source_binding,
        }
    if target == "metal":
        return {
            "target": "metal",
            "stage": "compute",
            "entryPoint": "compute_main",
            "abi": "kernelArgument",
            "addressSpace": "texture",
            "bindingClass": "texture",
            "argumentIndex": source_binding,
            "sourceSet": source_set,
            "sourceBinding": source_binding,
        }
    if target == "vulkan":
        return {
            "target": "vulkan",
            "stage": "compute",
            "entryPoint": "compute_main",
            "abi": "descriptor",
            "addressSpace": "UniformConstant",
            "bindingClass": "storageImage",
            "descriptorType": "VK_DESCRIPTOR_TYPE_STORAGE_IMAGE",
            "storageClass": "UniformConstant",
            "descriptorSet": source_set,
            "descriptorBinding": source_binding,
        }
    raise ValueError(f"unsupported storage-image parity target {target!r}")


def expected_synthetic_storage_image_array_source_coordinate(array_name):
    return dict(SYNTHETIC_STORAGE_IMAGE_ARRAY_SOURCE_COORDINATES[array_name])


def expected_array_element_count(resource):
    if resource.get("arrayElementCount") is not None:
        return resource.get("arrayElementCount")
    dimensions = resource.get("arrayDimensions")
    if not isinstance(dimensions, list) or not dimensions:
        return None
    element_count = 1
    for dimension in dimensions:
        if not isinstance(dimension, dict):
            return None
        dimension_count = dimension.get("elementCount")
        if dimension_count is None:
            return None
        element_count *= dimension_count
    return element_count


def expected_target_legalization_health(evidence):
    checks = evidence.get("checks", {})
    for name in (
        "manifestToolRequirementsTargetMatchesPackage",
        "manifestToolRequirementsPackageModeMatchesRequirements",
        "debugMetadataTargetMatchesPackage",
        "targetExplanationTargetMatchesPackage",
        "debugMetadataPackageModeMatchesRequirements",
        "targetExplanationPackageModeMatchesRequirements",
        "debugMetadataToolRequirementsMatchManifest",
        "targetExplanationToolRequirementsMatchManifest",
    ):
        if checks.get(name) is False:
            return "drift"
    if target_tool_sidecars_drift(
        evidence.get("debugMetadata", {}),
        evidence.get("targetExplanation", {}),
    ):
        return "drift"
    expected_requirement_ids = evidence.get("packageArtifactRequirementEvidenceIds")
    if expected_requirement_ids is not None:
        for sidecar_name in ("debugMetadata", "targetExplanation"):
            sidecar_ids = evidence.get(sidecar_name, {}).get(
                "packageArtifactRequirementEvidenceIds"
            )
            if sidecar_ids is not None and sidecar_ids != expected_requirement_ids:
                return "drift"
    for sidecar_name in ("debugMetadata", "targetExplanation"):
        sidecar = evidence.get(sidecar_name, {})
        if sidecar.get("artifactPresent") and (
            not sidecar.get("artifactExists")
            or sidecar.get("target") is None
            or sidecar.get("packageMode") is None
            or not sidecar.get("legalizationCoreEvidenceIds")
        ):
            return "incomplete"
    if (
        checks.get("packageArtifactRequirementEvidenceIdsPresent") is False
        or checks.get("manifestToolRequirementEvidenceIdsPresent") is False
    ):
        return "partial"
    return "ok"


def expect_target_legalization_sidecar(
    errors,
    case_name,
    path,
    actual,
    artifact_present,
    artifact_exists,
    expected_record,
):
    expect_equal(
        errors,
        case_name,
        f"{path}.artifactPresent",
        actual.get("artifactPresent"),
        artifact_present,
    )
    expect_equal(
        errors,
        case_name,
        f"{path}.artifactExists",
        actual.get("artifactExists"),
        artifact_exists,
    )
    if not artifact_exists:
        return
    expect_equal(
        errors,
        case_name,
        f"{path}.target",
        actual.get("target"),
        expected_record.get("target"),
    )
    expect_equal(
        errors,
        case_name,
        f"{path}.packageMode",
        actual.get("packageMode"),
        expected_record.get("packageMode"),
    )
    expect_equal(
        errors,
        case_name,
        f"{path}.packageDecisionReason",
        actual.get("packageDecisionReason"),
        expected_record.get("packageDecisionReason"),
    )
    for field, _, _ in TARGET_LEGALIZATION_TOOL_FIELD_PAIRS:
        expect_equal(
            errors,
            case_name,
            f"{path}.{field}",
            actual.get(field),
            expected_record.get(field),
        )
    expect_equal(
        errors,
        case_name,
        f"{path}.legalizationCoreEvidenceIds",
        actual.get("legalizationCoreEvidenceIds"),
        expected_record.get("legalizationCoreEvidenceIds"),
    )
    expect_equal(
        errors,
        case_name,
        f"{path}.packageArtifactRequirementEvidenceIds",
        actual.get("packageArtifactRequirementEvidenceIds"),
        expected_record.get("packageArtifactRequirementEvidenceIds"),
    )


def expect_target_legalization_evidence_summary(
    errors,
    case_name,
    payload,
    package,
    manifest,
):
    summary = expect_object(errors, case_name, "summary", payload.get("summary"))
    evidence = summary.get("targetLegalizationEvidence")
    if evidence is None:
        if isinstance(manifest.get("packageArtifactRequirements"), dict):
            errors.append(
                f"{case_name}: expected summary.targetLegalizationEvidence "
                "when manifest records packageArtifactRequirements"
            )
        return
    evidence = expect_object(
        errors,
        case_name,
        "summary.targetLegalizationEvidence",
        evidence,
    )
    artifacts = manifest.get("artifacts", {})
    if not isinstance(artifacts, dict):
        artifacts = {}
    target = summary.get("target")

    debug_doc = read_artifact_json(package, manifest, "debugMetadata")
    debug_decision = (debug_doc or {}).get("targetDecision", {})
    debug_summary = target_record(
        (debug_doc or {}).get("targetCapabilities", {}).get("summaries", []),
        debug_decision.get("selectedTarget"),
    )
    expected_debug = {
        "target": debug_decision.get("selectedTarget"),
        "packageMode": debug_decision.get("selectedTargetPackageMode"),
        "packageDecisionReason": debug_summary.get("packageDecisionReason"),
        "legalizationCoreEvidenceIds": debug_decision.get(
            "selectedTargetLegalizationCoreEvidenceIds"
        ),
        "packageArtifactRequirementEvidenceIds": debug_decision.get(
            "packageArtifactRequirementEvidenceIds"
        )
        or debug_summary.get("packageArtifactRequirementEvidenceIds"),
    }
    for field, decision_field, summary_field in TARGET_LEGALIZATION_TOOL_FIELD_PAIRS:
        expected_debug[field] = first_present(
            debug_decision.get(decision_field),
            debug_summary.get(summary_field),
        )
    expect_target_legalization_sidecar(
        errors,
        case_name,
        "summary.targetLegalizationEvidence.debugMetadata",
        evidence.get("debugMetadata", {}),
        "debugMetadata" in artifacts,
        debug_doc is not None,
        expected_debug,
    )

    explanation_doc = read_artifact_json(package, manifest, "targetExplanation")
    explanation_record = target_record(
        (explanation_doc or {}).get("targets", []), target
    )
    explanation_record = dict(explanation_record)
    expect_target_legalization_sidecar(
        errors,
        case_name,
        "summary.targetLegalizationEvidence.targetExplanation",
        evidence.get("targetExplanation", {}),
        "targetExplanation" in artifacts,
        explanation_doc is not None,
        explanation_record,
    )

    manifest_tool_requirements = manifest.get("targetLegalizationToolRequirements")
    actual_manifest_tool_requirements = expect_object(
        errors,
        case_name,
        "summary.targetLegalizationEvidence.manifestToolRequirements",
        evidence.get("manifestToolRequirements"),
    )
    if isinstance(manifest_tool_requirements, dict):
        expect_equal(
            errors,
            case_name,
            "summary.targetLegalizationEvidence.manifestToolRequirements.present",
            actual_manifest_tool_requirements.get("present"),
            True,
        )
        for field in ("target", "packageMode"):
            expect_equal(
                errors,
                case_name,
                f"summary.targetLegalizationEvidence.manifestToolRequirements.{field}",
                actual_manifest_tool_requirements.get(field),
                manifest_tool_requirements.get(field),
            )
        for field, _, _ in TARGET_LEGALIZATION_TOOL_FIELD_PAIRS:
            expect_equal(
                errors,
                case_name,
                f"summary.targetLegalizationEvidence.manifestToolRequirements.{field}",
                actual_manifest_tool_requirements.get(field),
                manifest_tool_requirements.get(field),
            )
    else:
        expect_equal(
            errors,
            case_name,
            "summary.targetLegalizationEvidence.manifestToolRequirements.present",
            actual_manifest_tool_requirements.get("present"),
            False,
        )

    requirements = manifest.get("packageArtifactRequirements")
    if isinstance(requirements, dict):
        expected_requirement_ids = (
            requirements.get("evidenceIds")
            or expected_debug.get("packageArtifactRequirementEvidenceIds")
            or explanation_record.get("packageArtifactRequirementEvidenceIds")
        )
        expect_equal(
            errors,
            case_name,
            "summary.targetLegalizationEvidence.packageMode",
            evidence.get("packageMode"),
            requirements.get("packageMode"),
        )
        expect_equal(
            errors,
            case_name,
            "summary.targetLegalizationEvidence.packageModeSource",
            evidence.get("packageModeSource"),
            "manifest.packageArtifactRequirements",
        )
        expect_equal(
            errors,
            case_name,
            "summary.targetLegalizationEvidence.packageArtifactRequirementEvidenceIds",
            evidence.get("packageArtifactRequirementEvidenceIds"),
            expected_requirement_ids,
        )
        expect_equal(
            errors,
            case_name,
            "summary.targetLegalizationEvidence.checks.packageArtifactRequirementEvidenceIdsPresent",
            evidence.get("checks", {}).get(
                "packageArtifactRequirementEvidenceIdsPresent"
            ),
            expected_requirement_ids is not None,
        )
        if (
            expected_requirement_ids is None
            and "packageArtifactRequirementEvidenceIds"
            not in evidence.get("missingEvidence", [])
        ):
            errors.append(
                f"{case_name}: expected summary.targetLegalizationEvidence."
                "missingEvidence to include 'packageArtifactRequirementEvidenceIds'"
            )

    checks = evidence.get("checks", {})
    if isinstance(manifest_tool_requirements, dict):
        expect_equal(
            errors,
            case_name,
            "summary.targetLegalizationEvidence.checks.manifestToolRequirementsTargetMatchesPackage",
            checks.get("manifestToolRequirementsTargetMatchesPackage"),
            manifest_tool_requirements.get("target") == target,
        )
        if isinstance(requirements, dict):
            expect_equal(
                errors,
                case_name,
                "summary.targetLegalizationEvidence.checks.manifestToolRequirementsPackageModeMatchesRequirements",
                checks.get("manifestToolRequirementsPackageModeMatchesRequirements"),
                manifest_tool_requirements.get("packageMode")
                == requirements.get("packageMode"),
            )
        expect_equal(
            errors,
            case_name,
            "summary.targetLegalizationEvidence.checks.manifestToolRequirementEvidenceIdsPresent",
            checks.get("manifestToolRequirementEvidenceIdsPresent"),
            bool(manifest_tool_requirements.get("toolRequirementEvidenceIds")),
        )
    for sidecar_name, expected_record in (
        ("debugMetadata", expected_debug),
        ("targetExplanation", explanation_record),
    ):
        target_value = expected_record.get("target")
        if target_value is not None:
            expect_equal(
                errors,
                case_name,
                f"summary.targetLegalizationEvidence.checks.{sidecar_name}TargetMatchesPackage",
                checks.get(f"{sidecar_name}TargetMatchesPackage"),
                target_value == target,
            )
        mode = expected_record.get("packageMode")
        if isinstance(requirements, dict) and mode is not None:
            expect_equal(
                errors,
                case_name,
                f"summary.targetLegalizationEvidence.checks.{sidecar_name}PackageModeMatchesRequirements",
                checks.get(f"{sidecar_name}PackageModeMatchesRequirements"),
                mode == requirements.get("packageMode"),
            )
        expect_equal(
            errors,
            case_name,
            f"summary.targetLegalizationEvidence.checks.{sidecar_name}ToolRequirementsMatchManifest",
            checks.get(f"{sidecar_name}ToolRequirementsMatchManifest"),
            target_tool_sidecar_matches_manifest(
                actual_manifest_tool_requirements,
                evidence.get(sidecar_name, {}),
            ),
        )

    expect_equal(
        errors,
        case_name,
        "summary.targetLegalizationEvidence.health",
        evidence.get("health"),
        expected_target_legalization_health(evidence),
    )


def expect_json_contract(errors, case_name, payload, package=None, manifest=None):
    if not isinstance(payload, dict):
        errors.append(f"{case_name}: expected verify JSON output to be an object")
        return

    expect_equal(errors, case_name, "schemaVersion", payload.get("schemaVersion"), 1)
    expect_package_path_contract(
        errors,
        case_name,
        payload.get("packagePath"),
        package,
    )

    diagnostic_counts = expect_object(
        errors,
        case_name,
        "diagnosticCounts",
        payload.get("diagnosticCounts"),
    )
    diagnostics = expect_array(
        errors,
        case_name,
        "diagnostics",
        payload.get("diagnostics"),
    )

    actual_counts = {severity: 0 for severity in SEVERITIES}
    for index, diagnostic in enumerate(diagnostics):
        diagnostic_path = f"diagnostics[{index}]"
        if not isinstance(diagnostic, dict):
            errors.append(f"{case_name}: expected {diagnostic_path} to be an object")
            continue

        severity = diagnostic.get("severity")
        if severity in actual_counts:
            actual_counts[severity] += 1
        else:
            errors.append(
                f"{case_name}: expected {diagnostic_path}.severity to be one of "
                f"{SEVERITIES!r}, got {severity!r}"
            )

        code = diagnostic.get("code")
        if not isinstance(code, str) or not code.startswith(
            VERIFY_DIAGNOSTIC_CODE_PREFIX
        ):
            errors.append(
                f"{case_name}: expected {diagnostic_path}.code to start with "
                f"{VERIFY_DIAGNOSTIC_CODE_PREFIX!r}, got {code!r}"
            )

        expect_location_span_coherent(
            errors,
            case_name,
            f"{diagnostic_path}.location",
            diagnostic.get("location"),
        )

    for severity, count in actual_counts.items():
        expect_equal(
            errors,
            case_name,
            f"diagnosticCounts.{severity}",
            diagnostic_counts.get(severity),
            count,
        )

    success = payload.get("success")
    expected_success = actual_counts["error"] == 0
    expect_equal(errors, case_name, "success", success, expected_success)
    if manifest is not None:
        expect_package_summary_manifest_contract(
            errors,
            case_name,
            payload.get("summary"),
            manifest,
        )
        if package is not None:
            expect_target_legalization_evidence_summary(
                errors,
                case_name,
                payload,
                package,
                manifest,
            )
    elif expected_success and payload.get("summary") is None:
        errors.append(
            f"{case_name}: expected summary object for successful JSON verify"
        )


def read_reflection_fixture(errors, case_name, package):
    path = package / "reflection.json"
    try:
        reflection = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        errors.append(f"{case_name}: failed to read reflection fixture: {exc}")
        return {}
    if not isinstance(reflection, dict):
        errors.append(f"{case_name}: expected reflection fixture to be an object")
        return {}
    return reflection


def expect_storage_image_binding_parity(
    case_name,
    target,
    package,
    manifest,
    payload,
    atomic=False,
    expected_source_coordinate=None,
):
    errors = []

    reflection = read_reflection_fixture(errors, case_name, package)
    resources = reflection.get("resources", [])
    bindings = reflection.get("targetResourceBindings", [])
    array_name = "unsignedAtlases" if atomic else "maskAtlases"
    resource = record_by_name(resources, array_name)
    binding = record_by_name(bindings, array_name)
    if resource is None:
        errors.append(f"{case_name}: expected reflection.resources {array_name!r}")
        return errors
    if binding is None:
        errors.append(
            f"{case_name}: expected reflection.targetResourceBindings {array_name!r}"
        )
        return errors

    source_coordinate = (
        expected_source_coordinate
        if expected_source_coordinate is not None
        else reflection_source_coordinate(resource)
    )
    expect_equal(
        errors,
        case_name,
        f"reflection.resources.{array_name}.sourceCoordinate",
        reflection_source_coordinate(resource),
        source_coordinate,
    )
    expect_equal(
        errors,
        case_name,
        f"reflection.targetResourceBindings.{array_name}.sourceCoordinate",
        reflection_source_coordinate(binding),
        source_coordinate,
    )
    expect_equal(
        errors,
        case_name,
        f"reflection.targetResourceBindings.{array_name}.targetCoordinate",
        reflection_target_binding_coordinate(target, binding),
        expected_storage_image_array_target_coordinate(target, resource),
    )
    expect_equal(
        errors,
        case_name,
        f"reflection.targetResourceBindings.{array_name}.arrayDimensions",
        binding.get("arrayDimensions"),
        resource.get("arrayDimensions"),
    )
    expect_equal(
        errors,
        case_name,
        f"reflection.targetResourceBindings.{array_name}.arrayElementCount",
        binding.get("arrayElementCount"),
        expected_array_element_count(resource),
    )

    if target not in {"directx", "opengl"}:
        return errors

    requirements = manifest.get("packageArtifactRequirements", {})
    debug_doc = read_artifact_json(package, manifest, "debugMetadata") or {}
    decision = debug_doc.get("targetDecision", {})
    summary = expect_object(errors, case_name, "summary", payload.get("summary"))
    evidence = expect_object(
        errors,
        case_name,
        "summary.targetLegalizationEvidence",
        summary.get("targetLegalizationEvidence"),
    )
    debug_sidecar = expect_object(
        errors,
        case_name,
        "summary.targetLegalizationEvidence.debugMetadata",
        evidence.get("debugMetadata"),
    )
    checks = evidence.get("checks", {})
    expected_evidence_ids = decision.get("selectedTargetLegalizationCoreEvidenceIds")

    expect_equal(
        errors,
        case_name,
        "manifest.packageArtifactRequirements.target",
        requirements.get("target"),
        target,
    )
    expect_equal(
        errors,
        case_name,
        "manifest.packageArtifactRequirements.packageMode",
        requirements.get("packageMode"),
        "source-package",
    )
    expect_equal(
        errors,
        case_name,
        "debugMetadata.targetDecision.selectedTarget",
        decision.get("selectedTarget"),
        target,
    )
    expect_equal(
        errors,
        case_name,
        "debugMetadata.targetDecision.selectedTargetPackageMode",
        decision.get("selectedTargetPackageMode"),
        "source-package",
    )
    expect_equal(
        errors,
        case_name,
        "debugMetadata.targetDecision.selectedTargetSourcePackageSupported",
        decision.get("selectedTargetSourcePackageSupported"),
        True,
    )
    expect_equal(
        errors,
        case_name,
        "summary.targetLegalizationEvidence.debugMetadata.target",
        debug_sidecar.get("target"),
        target,
    )
    expect_equal(
        errors,
        case_name,
        "summary.targetLegalizationEvidence.debugMetadata.packageMode",
        debug_sidecar.get("packageMode"),
        "source-package",
    )
    expect_equal(
        errors,
        case_name,
        "summary.targetLegalizationEvidence.debugMetadata.legalizationCoreEvidenceIds",
        debug_sidecar.get("legalizationCoreEvidenceIds"),
        expected_evidence_ids,
    )
    expect_equal(
        errors,
        case_name,
        "summary.targetLegalizationEvidence.packageMode",
        evidence.get("packageMode"),
        "source-package",
    )
    expect_equal(
        errors,
        case_name,
        "summary.targetLegalizationEvidence.checks.debugMetadataTargetMatchesPackage",
        checks.get("debugMetadataTargetMatchesPackage"),
        True,
    )
    expect_equal(
        errors,
        case_name,
        "summary.targetLegalizationEvidence.checks.debugMetadataPackageModeMatchesRequirements",
        checks.get("debugMetadataPackageModeMatchesRequirements"),
        True,
    )
    return errors


def expect_reflection_binding_failure(
    root,
    cglc,
    tmp_dir,
    case_name,
    package,
    source,
    manifest,
    expected,
    expected_code,
):
    errors = []
    errors.extend(
        expect_failure(
            cglc,
            case_name,
            package,
            expected,
            source=source,
        )
    )
    errors.extend(
        expect_json_failure(
            root,
            cglc,
            tmp_dir,
            f"{case_name}-json",
            package,
            expected,
            source=source,
            manifest=manifest,
            expected_code=expected_code,
        )
    )
    return errors


def expect_reflection_feature_failure(
    root,
    cglc,
    tmp_dir,
    case_name,
    package,
    source,
    manifest,
    expected,
    expected_code,
):
    errors = []
    errors.extend(
        expect_failure(
            cglc,
            case_name,
            package,
            expected,
            source=source,
        )
    )
    errors.extend(
        expect_json_failure(
            root,
            cglc,
            tmp_dir,
            f"{case_name}-json",
            package,
            expected,
            source=source,
            manifest=manifest,
            expected_code=expected_code,
        )
    )
    return errors


def shared_address_space_reflection(manifest, binding_address_space):
    target = manifest["target"]
    abi = {
        "directx": "groupsharedLocal",
        "metal": "threadgroupLocal",
        "opengl": "workgroupLocal",
        "vulkan": "workgroupLocal",
    }[target]
    binding_class = {
        "directx": "groupshared",
        "metal": "threadgroup",
        "opengl": "shared",
        "vulkan": "Workgroup",
    }[target]
    reflection = base_reflection(manifest)
    reflection["resources"] = [
        {
            "stage": "compute",
            "name": "tile",
            "kind": "shared",
            "type": "float",
            "addressSpace": "shared",
        }
    ]
    reflection["targetResourceBindings"] = [
        {
            "target": target,
            "stage": "compute",
            "entryPoint": "compute_main",
            "name": "tile",
            "kind": "shared",
            "sourceType": "float",
            "addressSpace": binding_address_space,
            "abi": abi,
            "bindingClass": binding_class,
            "evidenceId": (
                f"target-legalization.v1.{target}.resource-binding."
                "compute.compute_main.tile"
            ),
        }
    ]
    return reflection


def expect_reflection_summary(errors, case_name, summary, package, manifest):
    reflection_summary = expect_object(
        errors,
        case_name,
        "summary.reflection",
        summary.get("reflection"),
    )
    reflection = read_reflection_fixture(errors, case_name, package)
    selected_target = manifest.get("target")
    expected_bindings = []
    for binding in reflection.get("targetResourceBindings", []):
        if not isinstance(binding, dict) or binding.get("target") != selected_target:
            continue
        if not all(
            binding.get(field) for field in ("stage", "entryPoint", "name", "kind")
        ):
            continue
        expected_bindings.append(
            {
                "target": binding.get("target"),
                "stage": binding.get("stage"),
                "entryPoint": binding.get("entryPoint"),
                "name": binding.get("name"),
                "kind": binding.get("kind"),
                "evidenceId": binding.get("evidenceId"),
            }
        )
    expect_equal(
        errors,
        case_name,
        "summary.reflection.selectedTargetResourceBindingCount",
        reflection_summary.get("selectedTargetResourceBindingCount"),
        len(expected_bindings),
    )
    expect_equal(
        errors,
        case_name,
        "summary.reflection.selectedTargetResourceBindings",
        reflection_summary.get("selectedTargetResourceBindings"),
        expected_bindings,
    )
    expected_target_features = [
        feature
        for feature in reflection.get("targetFeatures", [])
        if isinstance(feature, dict) and feature.get("target") == selected_target
    ]
    if "targetFeatureCount" in reflection_summary:
        expect_equal(
            errors,
            case_name,
            "summary.reflection.targetFeatureCount",
            reflection_summary.get("targetFeatureCount"),
            len(expected_target_features),
        )
    if "targetFeatureEvidenceIds" in reflection_summary:
        expect_equal(
            errors,
            case_name,
            "summary.reflection.targetFeatureEvidenceIds",
            reflection_summary.get("targetFeatureEvidenceIds"),
            target_feature_evidence_ids(expected_target_features),
        )


def expect_native_artifact_descriptor_summary(
    errors,
    case_name,
    summary,
    package,
    manifest,
):
    summary = expect_object(errors, case_name, "summary", summary)
    descriptor_summary = expect_object(
        errors,
        case_name,
        "summary.nativeArtifactDescriptor",
        summary.get("nativeArtifactDescriptor"),
    )
    artifacts = manifest.get("artifacts", {})
    if not isinstance(artifacts, dict):
        artifacts = {}
    descriptor_path = artifacts.get("nativeArtifactDescriptor")
    if descriptor_path is None:
        expect_equal(
            errors,
            case_name,
            "summary.nativeArtifactDescriptor.artifactPresent",
            descriptor_summary.get("artifactPresent"),
            False,
        )
        expect_equal(
            errors,
            case_name,
            "summary.nativeArtifactDescriptor.descriptorExists",
            descriptor_summary.get("descriptorExists"),
            False,
        )
        expect_equal(
            errors,
            case_name,
            "summary.nativeArtifactDescriptor.health",
            descriptor_summary.get("health"),
            "not-present",
        )
        expect_equal(
            errors,
            case_name,
            "summary.nativeArtifactDescriptor.path",
            descriptor_summary.get("path"),
            None,
        )
        expect_equal(
            errors,
            case_name,
            "summary.nativeArtifactDescriptor.optimizationLevel",
            descriptor_summary.get("optimizationLevel"),
            None,
        )
        expect_equal(
            errors,
            case_name,
            "summary.nativeArtifactDescriptor.optimizationEvidence",
            descriptor_summary.get("optimizationEvidence"),
            None,
        )
        return

    expect_equal(
        errors,
        case_name,
        "summary.nativeArtifactDescriptor.artifactPresent",
        descriptor_summary.get("artifactPresent"),
        True,
    )
    expect_equal(
        errors,
        case_name,
        "summary.nativeArtifactDescriptor.path",
        descriptor_summary.get("path"),
        descriptor_path,
    )
    descriptor_file = package_path(package, descriptor_path)
    descriptor_exists = descriptor_file.is_file()
    expect_equal(
        errors,
        case_name,
        "summary.nativeArtifactDescriptor.descriptorExists",
        descriptor_summary.get("descriptorExists"),
        descriptor_exists,
    )
    if not descriptor_exists:
        return

    try:
        descriptor = json.loads(descriptor_file.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        errors.append(f"{case_name}: failed to read descriptor fixture: {exc}")
        return

    expect_equal(
        errors,
        case_name,
        "summary.nativeArtifactDescriptor.health",
        descriptor_summary.get("health"),
        "ok",
    )
    expect_equal(
        errors,
        case_name,
        "summary.nativeArtifactDescriptor.optimizationLevel",
        descriptor_summary.get("optimizationLevel"),
        descriptor.get("optimizationLevel"),
    )
    expected_evidence = descriptor.get("optimizationEvidence")
    if not isinstance(expected_evidence, dict):
        expected_evidence = None
    expect_equal(
        errors,
        case_name,
        "summary.nativeArtifactDescriptor.optimizationEvidence",
        descriptor_summary.get("optimizationEvidence"),
        expected_evidence,
    )


def expect_native_artifact_descriptor_report(errors, case_name, payload, expected):
    summary = expect_object(errors, case_name, "summary", payload.get("summary"))
    descriptor_summary = expect_object(
        errors,
        case_name,
        "summary.nativeArtifactDescriptor",
        summary.get("nativeArtifactDescriptor"),
    )
    for field, expected_value in expected.items():
        expect_equal(
            errors,
            case_name,
            f"summary.nativeArtifactDescriptor.{field}",
            descriptor_summary.get(field),
            expected_value,
        )


def expect_success(cglc, case_name, package, expected_stdout, source=None):
    result = run_verify(cglc, package, source=source)
    errors = []
    if result.returncode != 0:
        return [
            f"{case_name}: expected verify success, got "
            f"{result.stderr}{result.stdout}".strip()
        ]
    if result.stderr:
        errors.append(f"{case_name}: expected no diagnostics, got {result.stderr!r}")
    if expected_stdout not in result.stdout:
        errors.append(
            f"{case_name}: expected output substring {expected_stdout!r}; "
            f"got {result.stdout.strip()!r}"
        )
    return errors


def expect_json_success(
    root,
    cglc,
    tmp_dir,
    case_name,
    package,
    manifest,
    source=None,
    extra_check=None,
):
    result = run_verify(cglc, package, json_output=True, source=source)
    errors = []
    if result.returncode != 0:
        return [
            f"{case_name}: expected JSON verify success, got "
            f"{result.stderr}{result.stdout}".strip()
        ]
    if result.stderr:
        errors.append(f"{case_name}: expected no diagnostics, got {result.stderr!r}")
    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        return [f"{case_name}: verify output is not JSON: {exc}: {result.stdout!r}"]
    errors.extend(validate_schema(root, tmp_dir, case_name, result.stdout))
    expect_json_contract(errors, case_name, payload, package=package, manifest=manifest)
    expect_native_artifact_descriptor_summary(
        errors,
        case_name,
        payload.get("summary"),
        package,
        manifest,
    )
    expect_reflection_summary(
        errors,
        case_name,
        payload.get("summary"),
        package,
        manifest,
    )
    if "graphicsAbi" not in manifest.get("artifacts", {}) and "graphicsAbi" in payload:
        errors.append(
            f"{case_name}: verify report must omit graphicsAbi when "
            "manifest.artifacts.graphicsAbi is absent"
        )
    expect_equal(errors, case_name, "success", payload.get("success"), True)
    expect_equal(
        errors,
        case_name,
        "diagnosticCounts.error",
        payload.get("diagnosticCounts", {}).get("error"),
        0,
    )
    expect_equal(errors, case_name, "diagnostics", payload.get("diagnostics"), [])
    if extra_check is not None:
        errors.extend(extra_check(payload))
    return errors


def expect_json_legacy_fallback_success(
    root, cglc, tmp_dir, case_name, package, manifest, source=None
):
    result = run_verify(cglc, package, json_output=True, source=source)
    errors = []
    if result.returncode != 0:
        return [
            f"{case_name}: expected JSON verify success, got "
            f"{result.stderr}{result.stdout}".strip()
        ]
    if result.stderr:
        errors.append(f"{case_name}: expected no diagnostics on stderr")
    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        return [f"{case_name}: verify output is not JSON: {exc}: {result.stdout!r}"]

    errors.extend(validate_schema(root, tmp_dir, case_name, result.stdout))
    expect_json_contract(errors, case_name, payload, package=package, manifest=manifest)
    expect_native_artifact_descriptor_summary(
        errors,
        case_name,
        payload.get("summary"),
        package,
        manifest,
    )
    expect_reflection_summary(
        errors,
        case_name,
        payload.get("summary"),
        package,
        manifest,
    )
    expect_equal(errors, case_name, "success", payload.get("success"), True)
    expect_equal(
        errors,
        case_name,
        "diagnosticCounts.note",
        payload.get("diagnosticCounts", {}).get("note"),
        1,
    )
    expect_equal(
        errors,
        case_name,
        "diagnosticCounts.error",
        payload.get("diagnosticCounts", {}).get("error"),
        0,
    )

    diagnostics = payload.get("diagnostics", [])
    matching = [
        diagnostic
        for diagnostic in diagnostics
        if isinstance(diagnostic, dict)
        and diagnostic.get("code") == LEGACY_REQUIREMENTS_FALLBACK_CODE
    ]
    if len(matching) != 1:
        errors.append(
            f"{case_name}: expected one {LEGACY_REQUIREMENTS_FALLBACK_CODE} "
            f"diagnostic, got {len(matching)}"
        )
    elif matching[0].get("severity") != "note":
        errors.append(
            f"{case_name}: expected fallback diagnostic severity 'note', "
            f"got {matching[0].get('severity')!r}"
        )
    return errors


def expect_integrity_legacy_fallback_marker(root, cglc, case_name, package, source):
    result = run_integrity_validator(root, cglc, package, source=source)
    errors = []
    if result.returncode != 0:
        return [
            f"{case_name}: expected integrity validation success, got "
            f"{result.stderr}{result.stdout}".strip()
        ]
    if LEGACY_REQUIREMENTS_FALLBACK_CODE not in result.stdout:
        errors.append(
            f"{case_name}: expected integrity validation to report "
            f"{LEGACY_REQUIREMENTS_FALLBACK_CODE}, got {result.stdout!r}"
        )
    return errors


def expect_diagnostic_location_overlaps(
    errors,
    case_name,
    diagnostic,
    file_name,
    source_path,
    start_marker,
    end_marker,
):
    location = diagnostic.get("location")
    expect_location_overlaps_text(
        errors,
        case_name,
        "diagnostic location",
        location,
        source_path,
        start_marker,
        end_marker,
        expected_file_name=file_name,
    )


def expect_json_failure(
    root,
    cglc,
    tmp_dir,
    case_name,
    package,
    expected,
    source=None,
    expected_location=None,
    manifest=None,
    expected_code=None,
    expected_descriptor_summary=None,
):
    result = run_verify(cglc, package, json_output=True, source=source)
    errors = []
    if result.returncode == 0:
        errors.append(f"{case_name}: expected JSON verify failure")
    if result.stderr:
        errors.append(f"{case_name}: expected JSON diagnostics on stdout only")
    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        return [f"{case_name}: verify output is not JSON: {exc}: {result.stdout!r}"]
    errors.extend(validate_schema(root, tmp_dir, case_name, result.stdout))
    expect_json_contract(errors, case_name, payload, package=package, manifest=manifest)
    expect_equal(errors, case_name, "success", payload.get("success"), False)
    if payload.get("diagnosticCounts", {}).get("error", 0) < 1:
        errors.append(f"{case_name}: expected at least one JSON error diagnostic")
    diagnostics = payload.get("diagnostics", [])
    matching = next(
        (
            diagnostic
            for diagnostic in diagnostics
            if isinstance(diagnostic, dict)
            if expected in diagnostic.get("message", "")
            if expected_code is None or diagnostic.get("code") == expected_code
        ),
        None,
    )
    if matching is None:
        messages = "\n".join(
            f"{diagnostic.get('code', '')}: {diagnostic.get('message', '')}"
            for diagnostic in diagnostics
        )
        expected_detail = expected
        if expected_code is not None:
            expected_detail = f"{expected_code}: {expected}"
        errors.append(
            f"{case_name}: expected JSON diagnostic {expected_detail!r}; "
            f"got {messages!r}"
        )
    elif expected_location is not None:
        expect_diagnostic_location_overlaps(
            errors, case_name, matching, *expected_location
        )
    if expected_descriptor_summary is not None:
        expect_native_artifact_descriptor_report(
            errors,
            case_name,
            payload,
            expected_descriptor_summary,
        )
    return errors


def expect_failure(cglc, case_name, package, expected, source=None):
    result = run_verify(cglc, package, source=source)
    output = result.stderr + result.stdout
    errors = []
    if result.returncode == 0:
        errors.append(f"{case_name}: expected verify failure")
    if expected not in output:
        errors.append(
            f"{case_name}: expected error substring {expected!r}; "
            f"got {output.strip()!r}"
        )
    return errors


def expect_args_failure(cglc, case_name, args, expected):
    result = subprocess.run(
        [str(cglc), *args],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    output = result.stderr + result.stdout
    errors = []
    if result.returncode == 0:
        errors.append(f"{case_name}: expected command failure")
    if expected not in output:
        errors.append(
            f"{case_name}: expected output substring {expected!r}; "
            f"got {output.strip()!r}"
        )
    return errors


def run_cases(root, cglc, jobs=1):
    errors = []
    with tempfile.TemporaryDirectory() as tmp:
        tmp_dir = Path(tmp)

        package, source, manifest = make_package(tmp_dir, "valid-planned")
        errors.extend(
            expect_success(
                cglc,
                "valid-planned",
                package,
                "StorageBufferComputeShader for directx",
                source=source,
            )
        )
        errors.extend(
            expect_json_success(
                root,
                cglc,
                tmp_dir,
                "valid-planned-json",
                package,
                manifest,
                source=source,
            )
        )

        package, source, manifest = make_package(
            tmp_dir, "debug-metadata-package-mode-mismatch"
        )
        debug_metadata = read_artifact_json(package, manifest, "debugMetadata")
        debug_metadata["targetDecision"]["selectedTargetPackageMode"] = "native"
        write_json(
            package_path(package, manifest["artifacts"]["debugMetadata"]),
            debug_metadata,
        )
        expected = (
            "debugMetadata target legalization packageMode must match "
            "packageArtifactRequirements.packageMode"
        )
        errors.extend(
            expect_failure(
                cglc,
                "debug-metadata-package-mode-mismatch",
                package,
                expected,
                source=source,
            )
        )
        errors.extend(
            expect_json_failure(
                root,
                cglc,
                tmp_dir,
                "debug-metadata-package-mode-mismatch-json",
                package,
                expected,
                source=source,
                manifest=manifest,
                expected_code=(
                    "package.verify."
                    "target-legalization-debug-metadata-package-mode-mismatch"
                ),
            )
        )

        package, source, manifest = make_package(
            tmp_dir, "debug-metadata-requirement-evidence-drift"
        )
        debug_metadata = read_artifact_json(package, manifest, "debugMetadata")
        debug_metadata["targetDecision"]["packageArtifactRequirementEvidenceIds"] = [
            "legacy.generated.sidecar.evidence"
        ]
        write_json(
            package_path(package, manifest["artifacts"]["debugMetadata"]),
            debug_metadata,
        )
        expected = (
            "debugMetadata target legalization "
            "packageArtifactRequirementEvidenceIds must match recorded "
            "packageArtifactRequirements.evidenceIds"
        )
        errors.extend(
            expect_failure(
                cglc,
                "debug-metadata-requirement-evidence-drift",
                package,
                expected,
                source=source,
            )
        )
        errors.extend(
            expect_json_failure(
                root,
                cglc,
                tmp_dir,
                "debug-metadata-requirement-evidence-drift-json",
                package,
                expected,
                source=source,
                manifest=manifest,
                expected_code=(
                    "package.verify.target-legalization-debug-metadata-"
                    "requirement-evidence-mismatch"
                ),
            )
        )

        package, source, manifest = make_package(
            tmp_dir, "manifest-requirement-evidence-missing"
        )
        missing_requirement_evidence = copy.deepcopy(manifest)
        del missing_requirement_evidence["packageArtifactRequirements"]["evidenceIds"]
        rewrite_manifest(package, missing_requirement_evidence)
        expected = (
            "package manifest packageArtifactRequirements.evidenceIds must "
            "record target legalization package artifact requirement evidence"
        )
        errors.extend(
            expect_failure(
                cglc,
                "manifest-requirement-evidence-missing",
                package,
                expected,
                source=source,
            )
        )
        errors.extend(
            expect_json_failure(
                root,
                cglc,
                tmp_dir,
                "manifest-requirement-evidence-missing-json",
                package,
                expected,
                source=source,
                manifest=missing_requirement_evidence,
                expected_code=(
                    "package.verify.target-legalization-package-artifact-"
                    "requirement-evidence-missing"
                ),
            )
        )

        package, source, manifest = make_package(
            tmp_dir, "manifest-requirement-evidence-mismatch"
        )
        stale_requirement_evidence = copy.deepcopy(manifest)
        stale_requirement_evidence["packageArtifactRequirements"]["evidenceIds"] = [
            "target-legalization.v1.directx.stale-evidence"
        ]
        rewrite_manifest(package, stale_requirement_evidence)
        expected = (
            "package manifest packageArtifactRequirements.evidenceIds must "
            "match recorded packageArtifactRequirements"
        )
        errors.extend(
            expect_failure(
                cglc,
                "manifest-requirement-evidence-mismatch",
                package,
                expected,
                source=source,
            )
        )
        errors.extend(
            expect_json_failure(
                root,
                cglc,
                tmp_dir,
                "manifest-requirement-evidence-mismatch-json",
                package,
                expected,
                source=source,
                manifest=stale_requirement_evidence,
                expected_code=(
                    "package.verify.target-legalization-package-artifact-"
                    "requirement-evidence-mismatch"
                ),
            )
        )

        package, source, manifest = make_package(
            tmp_dir, "manifest-requirement-evidence-missing-id"
        )
        expected_evidence_ids = package_artifact_requirement_evidence_ids(
            manifest["packageArtifactRequirements"]
        )
        missing_requirement_evidence_id = manifest_with_requirement_evidence_ids(
            manifest,
            expected_evidence_ids[:-1],
        )
        rewrite_manifest(package, missing_requirement_evidence_id)
        expected = (
            "package manifest packageArtifactRequirements.evidenceIds must "
            "match recorded packageArtifactRequirements"
        )
        errors.extend(
            expect_failure(
                cglc,
                "manifest-requirement-evidence-missing-id",
                package,
                expected,
                source=source,
            )
        )
        errors.extend(
            expect_json_failure(
                root,
                cglc,
                tmp_dir,
                "manifest-requirement-evidence-missing-id-json",
                package,
                expected,
                source=source,
                manifest=missing_requirement_evidence_id,
                expected_code=(
                    "package.verify.target-legalization-package-artifact-"
                    "requirement-evidence-mismatch"
                ),
            )
        )

        package, source, manifest = make_package(
            tmp_dir, "manifest-requirement-evidence-extra-id"
        )
        expected_evidence_ids = package_artifact_requirement_evidence_ids(
            manifest["packageArtifactRequirements"]
        )
        extra_requirement_evidence_id = manifest_with_requirement_evidence_ids(
            manifest,
            expected_evidence_ids
            + ["target-legalization.v1.directx.package-artifact.fixture.extra"],
        )
        rewrite_manifest(package, extra_requirement_evidence_id)
        expected = (
            "package manifest packageArtifactRequirements.evidenceIds must "
            "match recorded packageArtifactRequirements"
        )
        errors.extend(
            expect_failure(
                cglc,
                "manifest-requirement-evidence-extra-id",
                package,
                expected,
                source=source,
            )
        )
        errors.extend(
            expect_json_failure(
                root,
                cglc,
                tmp_dir,
                "manifest-requirement-evidence-extra-id-json",
                package,
                expected,
                source=source,
                manifest=extra_requirement_evidence_id,
                expected_code=(
                    "package.verify.target-legalization-package-artifact-"
                    "requirement-evidence-mismatch"
                ),
            )
        )

        package, source, manifest = make_package(
            tmp_dir, "manifest-requirement-artifact-contract-drift"
        )
        artifact_contract_drift = manifest_with_required_path_artifacts(
            manifest, ["backendSource"]
        )
        rewrite_manifest(package, artifact_contract_drift)
        expected = (
            "package manifest "
            "packageArtifactRequirements.requiredPathArtifacts must match "
            "manifest target contract"
        )
        errors.extend(
            expect_failure(
                cglc,
                "manifest-requirement-artifact-contract-drift",
                package,
                expected,
                source=source,
            )
        )
        errors.extend(
            expect_json_failure(
                root,
                cglc,
                tmp_dir,
                "manifest-requirement-artifact-contract-drift-json",
                package,
                expected,
                source=source,
                manifest=artifact_contract_drift,
                expected_code="package.verify.invalid-manifest",
            )
        )

        artifact_contract_drift_cases = (
            (
                "manifest-requirement-artifact-contract-reordered",
                ["nativeBinary", "backendSource"],
            ),
            (
                "manifest-requirement-artifact-contract-extra",
                ["backendSource", "nativeBinary", "intermediate"],
            ),
        )
        for case_name, required_path_artifacts in artifact_contract_drift_cases:
            package, source, manifest = make_package(tmp_dir, case_name)
            artifact_contract_drift = manifest_with_required_path_artifacts(
                manifest,
                required_path_artifacts,
            )
            rewrite_manifest(package, artifact_contract_drift)
            errors.extend(
                expect_failure(
                    cglc,
                    case_name,
                    package,
                    expected,
                    source=source,
                )
            )
            errors.extend(
                expect_json_failure(
                    root,
                    cglc,
                    tmp_dir,
                    f"{case_name}-json",
                    package,
                    expected,
                    source=source,
                    manifest=artifact_contract_drift,
                    expected_code="package.verify.invalid-manifest",
                )
            )

        package, source, manifest = make_package(
            tmp_dir, "manifest-requirement-native-policy-contract-drift"
        )
        native_policy_drift = copy.deepcopy(manifest)
        native_policy_drift["packageArtifactRequirements"][
            "requiresNativeBinaryStatus"
        ] = False
        native_policy_drift["packageArtifactRequirements"][
            "allowsPlannedNativeBinary"
        ] = False
        native_policy_drift["packageArtifactRequirements"][
            "allowsPlannedNativeSourceEvidence"
        ] = False
        native_policy_drift["packageArtifactRequirements"]["evidenceIds"] = (
            package_artifact_requirement_evidence_ids(
                native_policy_drift["packageArtifactRequirements"]
            )
        )
        rewrite_manifest(package, native_policy_drift)
        expected = (
            "package manifest packageArtifactRequirements native binary policy "
            "must match manifest target contract"
        )
        errors.extend(
            expect_failure(
                cglc,
                "manifest-requirement-native-policy-contract-drift",
                package,
                expected,
                source=source,
            )
        )
        errors.extend(
            expect_json_failure(
                root,
                cglc,
                tmp_dir,
                "manifest-requirement-native-policy-contract-drift-json",
                package,
                expected,
                source=source,
                manifest=native_policy_drift,
                expected_code="package.verify.invalid-manifest",
            )
        )

        package, source, manifest = make_package(
            tmp_dir, "debug-metadata-incomplete-legalization-projection"
        )
        debug_metadata = read_artifact_json(package, manifest, "debugMetadata")
        debug_metadata["targetDecision"][
            "selectedTargetLegalizationCoreEvidenceIds"
        ] = []
        write_json(
            package_path(package, manifest["artifacts"]["debugMetadata"]),
            debug_metadata,
        )
        expected = (
            "debugMetadata target legalization projection evidence must include "
            "selected target, supported package state, packageMode, and "
            "legalizationCoreEvidenceIds"
        )
        errors.extend(
            expect_failure(
                cglc,
                "debug-metadata-incomplete-legalization-projection",
                package,
                expected,
                source=source,
            )
        )
        errors.extend(
            expect_json_failure(
                root,
                cglc,
                tmp_dir,
                "debug-metadata-incomplete-legalization-projection-json",
                package,
                expected,
                source=source,
                manifest=manifest,
                expected_code=(
                    "package.verify.target-legalization-debug-metadata-incomplete"
                ),
            )
        )

        package, source, manifest = make_package(
            tmp_dir, "target-explanation-unsupported-legalization-projection"
        )
        target_explanation = read_artifact_json(package, manifest, "targetExplanation")
        record = target_record(
            target_explanation.get("targets", []), manifest["target"]
        )
        record["packageBuildSupported"] = False
        write_json(
            package_path(package, manifest["artifacts"]["targetExplanation"]),
            target_explanation,
        )
        expected = (
            "targetExplanation target legalization projection rejects package target"
        )
        errors.extend(
            expect_failure(
                cglc,
                "target-explanation-unsupported-legalization-projection",
                package,
                expected,
                source=source,
            )
        )
        errors.extend(
            expect_json_failure(
                root,
                cglc,
                tmp_dir,
                "target-explanation-unsupported-legalization-projection-json",
                package,
                expected,
                source=source,
                manifest=manifest,
                expected_code=(
                    "package.verify.target-legalization-target-explanation-unsupported"
                ),
            )
        )

        package, source, manifest = make_package(tmp_dir, "legacy-requirements")
        legacy_manifest = copy.deepcopy(manifest)
        del legacy_manifest["packageArtifactRequirements"]
        rewrite_manifest(package, legacy_manifest)
        errors.extend(
            expect_json_legacy_fallback_success(
                root,
                cglc,
                tmp_dir,
                "legacy-requirements-json",
                package,
                legacy_manifest,
                source=source,
            )
        )
        errors.extend(
            expect_integrity_legacy_fallback_marker(
                root,
                cglc,
                "legacy-requirements-integrity",
                package,
                source,
            )
        )

        package, _source, manifest = make_package(tmp_dir, "null-artifact-requirements")
        null_requirements_manifest = copy.deepcopy(manifest)
        null_requirements_manifest["packageArtifactRequirements"] = None
        rewrite_manifest(package, null_requirements_manifest)
        errors.extend(
            expect_failure(
                cglc,
                "null-artifact-requirements",
                package,
                "package manifest packageArtifactRequirements is invalid",
            )
        )
        errors.extend(
            expect_json_failure(
                root,
                cglc,
                tmp_dir,
                "null-artifact-requirements-json",
                package,
                "package manifest packageArtifactRequirements is invalid",
                expected_code="package.verify.invalid-manifest",
            )
        )

        package, source, manifest = make_package(
            tmp_dir,
            "native-artifact-descriptor",
        )
        add_native_artifact_descriptor(package, manifest)
        errors.extend(
            expect_json_success(
                root,
                cglc,
                tmp_dir,
                "native-artifact-descriptor-json",
                package,
                manifest,
                source=source,
            )
        )

        package, source, manifest = make_package(
            tmp_dir,
            "native-artifact-descriptor-optimization-evidence",
        )

        def add_optimization_evidence(descriptor):
            descriptor["optimizationEvidence"] = {
                "requestedLevel": "O0",
                "effectiveLevel": "none",
                "policy": "source-package-planned",
                "status": "metadata-only",
            }

        add_native_artifact_descriptor(
            package, manifest, mutate=add_optimization_evidence
        )
        errors.extend(
            expect_json_success(
                root,
                cglc,
                tmp_dir,
                "native-artifact-descriptor-optimization-evidence-json",
                package,
                manifest,
                source=source,
            )
        )

        native_artifact_descriptor_cases = []
        for target in ("metal", "vulkan"):
            package, source, manifest = make_package(
                tmp_dir,
                f"native-artifact-descriptor-{target}",
                target=target,
            )
            add_native_artifact_descriptor(
                package, manifest, mutate=mark_native_artifact_validated
            )
            native_artifact_descriptor_cases.append((target, package, source, manifest))

        def check_native_artifact_descriptor_case(case):
            target, package, source, manifest = case
            return expect_json_success(
                root,
                cglc,
                tmp_dir,
                f"native-artifact-descriptor-{target}-json",
                package,
                manifest,
                source=source,
            )

        extend_errors_from_fixture_tasks(
            errors,
            native_artifact_descriptor_cases,
            check_native_artifact_descriptor_case,
            jobs=jobs,
        )

        package, source, manifest = make_package(
            tmp_dir,
            "native-artifact-descriptor-missing-file",
        )
        add_native_artifact_descriptor(package, manifest)
        package_path(
            package,
            manifest["artifacts"]["nativeArtifactDescriptor"],
        ).unlink()
        expected = (
            "native artifact descriptor does not exist: metadata/native-artifact.json"
        )
        errors.extend(
            expect_failure(
                cglc,
                "native-artifact-descriptor-missing-file",
                package,
                expected,
                source=source,
            )
        )
        errors.extend(
            expect_json_failure(
                root,
                cglc,
                tmp_dir,
                "native-artifact-descriptor-missing-file-json",
                package,
                expected,
                source=source,
                manifest=manifest,
                expected_code="package.verify.native-artifact-descriptor-missing",
                expected_descriptor_summary={
                    "artifactPresent": True,
                    "descriptorExists": False,
                    "health": "incomplete",
                    "path": manifest["artifacts"]["nativeArtifactDescriptor"],
                    "optimizationLevel": None,
                    "optimizationEvidence": None,
                },
            )
        )

        package, source, manifest = make_package(
            tmp_dir,
            "native-artifact-descriptor-missing-provenance",
        )

        def remove_toolchain_provenance(descriptor):
            del descriptor["toolchainProvenance"]

        add_native_artifact_descriptor(
            package, manifest, mutate=remove_toolchain_provenance
        )
        errors.extend(
            expect_json_failure(
                root,
                cglc,
                tmp_dir,
                "native-artifact-descriptor-missing-provenance-json",
                package,
                "native artifact descriptor must use the native-artifact-v0 contract",
                source=source,
                manifest=manifest,
                expected_code="package.verify.native-artifact-descriptor-invalid",
            )
        )

        package, source, manifest = make_package(
            tmp_dir,
            "native-artifact-descriptor-extra-property",
        )

        def add_extra_property(descriptor):
            descriptor["unexpected"] = True

        add_native_artifact_descriptor(package, manifest, mutate=add_extra_property)
        errors.extend(
            expect_json_failure(
                root,
                cglc,
                tmp_dir,
                "native-artifact-descriptor-extra-property-json",
                package,
                "native artifact descriptor must use the native-artifact-v0 contract",
                source=source,
                manifest=manifest,
                expected_code="package.verify.native-artifact-descriptor-invalid",
            )
        )

        package, source, manifest = make_package(
            tmp_dir,
            "native-artifact-descriptor-source-hash-extra-property",
        )

        def add_source_hash_extra_property(descriptor):
            descriptor["sourceHash"]["unexpected"] = True

        add_native_artifact_descriptor(
            package, manifest, mutate=add_source_hash_extra_property
        )
        errors.extend(
            expect_json_failure(
                root,
                cglc,
                tmp_dir,
                "native-artifact-descriptor-source-hash-extra-property-json",
                package,
                "native artifact descriptor must use the native-artifact-v0 contract",
                source=source,
                manifest=manifest,
                expected_code="package.verify.native-artifact-descriptor-invalid",
            )
        )

        package, source, manifest = make_package(
            tmp_dir,
            "native-artifact-descriptor-artifact-hash-extra-property",
            status="emitted",
        )

        def add_artifact_hash_extra_property(descriptor):
            descriptor["artifactHash"]["unexpected"] = True

        add_native_artifact_descriptor(
            package, manifest, mutate=add_artifact_hash_extra_property
        )
        errors.extend(
            expect_json_failure(
                root,
                cglc,
                tmp_dir,
                "native-artifact-descriptor-artifact-hash-extra-property-json",
                package,
                "native artifact descriptor must use the native-artifact-v0 contract",
                source=source,
                manifest=manifest,
                expected_code="package.verify.native-artifact-descriptor-invalid",
            )
        )

        package, source, manifest = make_package(
            tmp_dir,
            "native-artifact-descriptor-vulkan-binary-kind-mismatch",
            target="vulkan",
        )

        def use_metal_binary_kind(descriptor):
            descriptor["binaryKind"] = "metal.metallib"

        add_native_artifact_descriptor(package, manifest, mutate=use_metal_binary_kind)
        expected = "native artifact descriptor must use the native-artifact-v0 contract"
        errors.extend(
            expect_failure(
                cglc,
                "native-artifact-descriptor-vulkan-binary-kind-mismatch",
                package,
                expected,
                source=source,
            )
        )
        errors.extend(
            expect_json_failure(
                root,
                cglc,
                tmp_dir,
                "native-artifact-descriptor-vulkan-binary-kind-mismatch-json",
                package,
                expected,
                source=source,
                manifest=manifest,
                expected_code="package.verify.native-artifact-descriptor-invalid",
                expected_descriptor_summary={
                    "artifactPresent": True,
                    "descriptorExists": True,
                    "health": "invalid",
                    "path": manifest["artifacts"]["nativeArtifactDescriptor"],
                    "optimizationLevel": "O0",
                    "optimizationEvidence": None,
                },
            )
        )

        package, source, manifest = make_package(
            tmp_dir,
            "native-artifact-descriptor-source-hash-mismatch",
        )

        def corrupt_source_hash(descriptor):
            descriptor["sourceHash"]["value"] = "0" * 64

        add_native_artifact_descriptor(package, manifest, mutate=corrupt_source_hash)
        errors.extend(
            expect_json_failure(
                root,
                cglc,
                tmp_dir,
                "native-artifact-descriptor-source-hash-mismatch-json",
                package,
                "native artifact descriptor sourceHash must match sourcePath",
                source=source,
                manifest=manifest,
                expected_code="package.verify.native-artifact-source-hash-mismatch",
            )
        )

        package, source, manifest = make_package(
            tmp_dir,
            "native-artifact-descriptor-artifact-hash-mismatch",
            status="emitted",
        )

        def corrupt_artifact_hash(descriptor):
            descriptor["artifactHash"]["value"] = "0" * 64

        add_native_artifact_descriptor(package, manifest, mutate=corrupt_artifact_hash)
        errors.extend(
            expect_json_failure(
                root,
                cglc,
                tmp_dir,
                "native-artifact-descriptor-artifact-hash-mismatch-json",
                package,
                "native artifact descriptor artifactHash must match artifactPath",
                source=source,
                manifest=manifest,
                expected_code="package.verify.native-artifact-hash-mismatch",
            )
        )

        package, _source, manifest = make_package(tmp_dir, "planned-without-source")
        expected = (
            "directx packages with nativeBinaryStatus planned require --source "
            "to verify sourceHash"
        )
        errors.extend(
            expect_failure(
                cglc,
                "planned-without-source",
                package,
                expected,
            )
        )
        errors.extend(
            expect_json_failure(
                root,
                cglc,
                tmp_dir,
                "planned-without-source-json",
                package,
                expected,
                manifest=manifest,
                expected_code="package.verify.source-required-for-planned-native",
            )
        )

        package, _source, manifest = make_package(
            tmp_dir, "emitted-without-native-artifact-descriptor", status="emitted"
        )
        expected = (
            "directx native-ready package verification requires "
            "nativeArtifactDescriptor artifact evidence"
        )
        errors.extend(
            expect_failure(
                cglc,
                "emitted-without-native-artifact-descriptor",
                package,
                expected,
            )
        )
        errors.extend(
            expect_json_failure(
                root,
                cglc,
                tmp_dir,
                "emitted-without-native-artifact-descriptor-json",
                package,
                expected,
                manifest=manifest,
                expected_code=("package.verify.native-artifact-descriptor-required"),
            )
        )

        package, _source, manifest = make_package(
            tmp_dir, "native-without-native-artifact-descriptor", target="metal"
        )
        expected = (
            "metal native-ready package verification requires "
            "nativeArtifactDescriptor artifact evidence"
        )
        errors.extend(
            expect_failure(
                cglc,
                "native-without-native-artifact-descriptor",
                package,
                expected,
            )
        )
        errors.extend(
            expect_json_failure(
                root,
                cglc,
                tmp_dir,
                "native-without-native-artifact-descriptor-json",
                package,
                expected,
                manifest=manifest,
                expected_code=("package.verify.native-artifact-descriptor-required"),
            )
        )

        package, _source, manifest = make_package(
            tmp_dir, "valid-emitted", status="emitted"
        )
        add_native_artifact_descriptor(package, manifest)
        errors.extend(
            expect_success(
                cglc,
                "valid-emitted",
                package,
                "StorageBufferComputeShader for directx",
            )
        )
        errors.extend(
            expect_json_success(
                root,
                cglc,
                tmp_dir,
                "valid-emitted-json",
                package,
                manifest,
            )
        )

        package, source, manifest = make_package(
            tmp_dir, "valid-opengl-emitted", target="opengl", status="emitted"
        )
        add_native_artifact_descriptor(package, manifest)
        errors.extend(
            expect_success(
                cglc,
                "valid-opengl-emitted",
                package,
                "StorageBufferComputeShader for opengl",
                source=source,
            )
        )
        errors.extend(
            expect_json_success(
                root,
                cglc,
                tmp_dir,
                "valid-opengl-emitted-json",
                package,
                manifest,
                source=source,
            )
        )

        valid_target_cases = []
        for target in ("metal", "vulkan", "opengl"):
            case_name = f"valid-{target}"
            package, source, manifest = make_package(
                tmp_dir,
                case_name,
                target=target,
            )
            if target in {"metal", "vulkan"}:
                add_native_artifact_descriptor(
                    package, manifest, mutate=mark_native_artifact_validated
                )
            valid_target_cases.append((case_name, target, package, source, manifest))

        def check_valid_target_case(case):
            case_name, target, package, source, manifest = case
            case_errors = []
            case_errors.extend(
                expect_success(
                    cglc,
                    case_name,
                    package,
                    f"StorageBufferComputeShader for {target}",
                    source=source,
                )
            )
            case_errors.extend(
                expect_json_success(
                    root,
                    cglc,
                    tmp_dir,
                    f"{case_name}-json",
                    package,
                    manifest,
                    source=source,
                )
            )
            return case_errors

        extend_errors_from_fixture_tasks(
            errors,
            valid_target_cases,
            check_valid_target_case,
            jobs=jobs,
        )

        nonuniform_feature_cases = []
        for target in ("directx", "opengl", "vulkan", "metal"):
            case_name = f"nonuniform-feature-metadata-{target}"
            package, source, manifest = make_package(
                tmp_dir,
                case_name,
                target=target,
            )
            if target in {"metal", "vulkan"}:
                add_native_artifact_descriptor(
                    package, manifest, mutate=mark_native_artifact_validated
                )
            write_nonuniform_reflection(package, manifest)
            write_nonuniform_diagnostics(package, target)
            nonuniform_feature_cases.append((case_name, package, source, manifest))

        def check_nonuniform_feature_case(case):
            case_name, package, source, manifest = case
            return expect_json_success(
                root,
                cglc,
                tmp_dir,
                f"{case_name}-json",
                package,
                manifest,
                source=source,
            )

        extend_errors_from_fixture_tasks(
            errors,
            nonuniform_feature_cases,
            check_nonuniform_feature_case,
            jobs=jobs,
        )

        storage_image_cases = []
        for target in ("directx", "opengl", "vulkan", "metal"):
            for atomic in (False, True):
                family = (
                    "storage-image-atomic" if atomic else "storage-image-read-write"
                )
                case_name = f"{family}-metadata-{target}"
                package, source, manifest = make_package(
                    tmp_dir,
                    case_name,
                    target=target,
                )
                if target in {"metal", "vulkan"}:
                    add_native_artifact_descriptor(
                        package, manifest, mutate=mark_native_artifact_validated
                    )
                write_storage_image_reflection(package, manifest, atomic=atomic)
                storage_image_cases.append(
                    (case_name, target, package, source, manifest, atomic)
                )

        def check_storage_image_case(case):
            case_name, target, package, source, manifest, atomic = case
            case_errors = []
            case_errors.extend(
                expect_success(
                    cglc,
                    case_name,
                    package,
                    f"StorageBufferComputeShader for {target}",
                    source=source,
                )
            )
            case_errors.extend(
                expect_json_success(
                    root,
                    cglc,
                    tmp_dir,
                    f"{case_name}-json",
                    package,
                    manifest,
                    source=source,
                    extra_check=(
                        lambda payload: expect_storage_image_binding_parity(
                            case_name,
                            target,
                            package,
                            manifest,
                            payload,
                            atomic=atomic,
                            expected_source_coordinate=(
                                expected_synthetic_storage_image_array_source_coordinate(
                                    "unsignedAtlases" if atomic else "maskAtlases"
                                )
                            ),
                        )
                    ),
                )
            )
            return case_errors

        extend_errors_from_fixture_tasks(
            errors,
            storage_image_cases,
            check_storage_image_case,
            jobs=jobs,
        )

        unexpected_native_status_cases = []
        for target in ("metal", "vulkan"):
            case_name = f"{target}-unexpected-native-status"
            package, _source, manifest = make_package(
                tmp_dir,
                case_name,
                target=target,
            )
            unexpected_native_status = copy.deepcopy(manifest)
            unexpected_native_status["artifacts"]["nativeBinaryStatus"] = "emitted"
            rewrite_manifest(package, unexpected_native_status)
            expected = f"{target} packages must not declare nativeBinaryStatus"
            unexpected_native_status_cases.append(
                (case_name, package, unexpected_native_status, expected)
            )

        def check_unexpected_native_status_case(case):
            case_name, package, manifest, expected = case
            case_errors = []
            case_errors.extend(
                expect_failure(
                    cglc,
                    case_name,
                    package,
                    expected,
                )
            )
            case_errors.extend(
                expect_json_failure(
                    root,
                    cglc,
                    tmp_dir,
                    f"{case_name}-json",
                    package,
                    expected,
                    manifest=manifest,
                    expected_code="package.verify.unexpected-native-status",
                )
            )
            return case_errors

        extend_errors_from_fixture_tasks(
            errors,
            unexpected_native_status_cases,
            check_unexpected_native_status_case,
            jobs=jobs,
        )

        package, _source, manifest = make_package(tmp_dir, "duplicate-artifact-key")
        duplicate_manifest_artifact(package, manifest, "backendSource")
        expected = "duplicate JSON object key: $.artifacts.backendSource"
        errors.extend(
            expect_failure(
                cglc,
                "duplicate-artifact-key",
                package,
                expected,
            )
        )
        errors.extend(
            expect_json_failure(
                root,
                cglc,
                tmp_dir,
                "duplicate-artifact-key-json",
                package,
                expected,
                expected_code="package.verify.duplicate-key",
            )
        )

        missing_required_artifact_cases = []
        for target, required_artifacts in TARGET_REQUIRED_ARTIFACTS.items():
            for artifact_name in required_artifacts:
                case_name = f"{target}-missing-{artifact_name}"
                package, _source, manifest = make_package(
                    tmp_dir,
                    case_name,
                    target=target,
                )
                missing_required = copy.deepcopy(manifest)
                del missing_required["artifacts"][artifact_name]
                delete_artifact_path(package, manifest, artifact_name)
                rewrite_manifest(package, missing_required)
                expected = f"{target} packages require {artifact_name}"
                expected_code = (
                    "package.verify.missing-native-status"
                    if artifact_name == "nativeBinaryStatus"
                    else "package.verify.missing-required-artifact"
                )
                missing_required_artifact_cases.append(
                    (
                        case_name,
                        package,
                        missing_required,
                        expected,
                        expected_code,
                    )
                )

        def check_missing_required_artifact_case(case):
            case_name, package, manifest, expected, expected_code = case
            case_errors = []
            case_errors.extend(
                expect_failure(
                    cglc,
                    case_name,
                    package,
                    expected,
                )
            )
            case_errors.extend(
                expect_json_failure(
                    root,
                    cglc,
                    tmp_dir,
                    f"{case_name}-json",
                    package,
                    expected,
                    manifest=manifest,
                    expected_code=expected_code,
                )
            )
            return case_errors

        extend_errors_from_fixture_tasks(
            errors,
            missing_required_artifact_cases,
            check_missing_required_artifact_case,
            jobs=jobs,
        )

        package, source, manifest = make_package(
            tmp_dir, "recorded-requirements-no-native-status", status="emitted"
        )
        recorded_requirements = copy.deepcopy(manifest)
        del recorded_requirements["artifacts"]["nativeBinaryStatus"]
        recorded_requirements["packageArtifactRequirements"]["packageMode"] = "native"
        recorded_requirements["packageArtifactRequirements"][
            "requiresNativeBinaryStatus"
        ] = False
        recorded_requirements["packageArtifactRequirements"][
            "allowsPlannedNativeBinary"
        ] = False
        recorded_requirements["packageArtifactRequirements"][
            "allowsPlannedNativeSourceEvidence"
        ] = False
        recorded_requirements["packageArtifactRequirements"]["evidenceIds"] = (
            package_artifact_requirement_evidence_ids(
                recorded_requirements["packageArtifactRequirements"]
            )
        )
        rewrite_manifest(package, recorded_requirements)
        add_native_artifact_descriptor(package, recorded_requirements)

        debug_metadata_path = package_path(
            package, recorded_requirements["artifacts"]["debugMetadata"]
        )
        debug_metadata = json.loads(debug_metadata_path.read_text(encoding="utf-8"))
        debug_metadata["targetDecision"]["selectedTargetPackageMode"] = "native"
        for summary in debug_metadata["targetCapabilities"]["summaries"]:
            if summary.get("target") == "directx":
                summary["packageMode"] = "native"
                summary["packageDecisionReason"] = "native-package-available"
        write_json(debug_metadata_path, debug_metadata)

        target_explanation_path = package_path(
            package, recorded_requirements["artifacts"]["targetExplanation"]
        )
        target_explanation = json.loads(
            target_explanation_path.read_text(encoding="utf-8")
        )
        for record in target_explanation["targets"]:
            if record.get("target") == "directx":
                record["packageMode"] = "native"
                record["packageDecisionReason"] = "native-package-available"
                break
        write_json(target_explanation_path, target_explanation)

        def expect_recorded_native_requirements(payload):
            case_errors = []
            summary = payload.get("summary", {})
            expect_equal(
                case_errors,
                "recorded-requirements-no-native-status-json",
                "summary.nativeBinaryStatus",
                summary.get("nativeBinaryStatus"),
                None,
            )
            evidence = summary.get("targetLegalizationEvidence", {})
            expect_equal(
                case_errors,
                "recorded-requirements-no-native-status-json",
                "summary.targetLegalizationEvidence.packageMode",
                evidence.get("packageMode"),
                "native",
            )
            return case_errors

        errors.extend(
            expect_success(
                cglc,
                "recorded-requirements-no-native-status",
                package,
                "StorageBufferComputeShader for directx",
                source=source,
            )
        )
        errors.extend(
            expect_json_success(
                root,
                cglc,
                tmp_dir,
                "recorded-requirements-no-native-status-json",
                package,
                recorded_requirements,
                source=source,
                extra_check=expect_recorded_native_requirements,
            )
        )

        package, source, manifest = make_package(
            tmp_dir,
            "recorded-planned-status-policy-drift",
            status="emitted",
        )
        planned_status_disallowed = copy.deepcopy(manifest)
        planned_status_disallowed["artifacts"]["nativeBinaryStatus"] = "planned"
        planned_status_disallowed["packageArtifactRequirements"][
            "allowsPlannedNativeBinary"
        ] = False
        planned_status_disallowed["packageArtifactRequirements"][
            "allowsPlannedNativeSourceEvidence"
        ] = False
        planned_status_disallowed["packageArtifactRequirements"]["evidenceIds"] = (
            package_artifact_requirement_evidence_ids(
                planned_status_disallowed["packageArtifactRequirements"]
            )
        )
        rewrite_manifest(package, planned_status_disallowed)
        add_native_artifact_descriptor(package, planned_status_disallowed)
        expected = (
            "package manifest packageArtifactRequirements native binary policy "
            "must match manifest target contract"
        )
        errors.extend(
            expect_failure(
                cglc,
                "recorded-planned-status-policy-drift",
                package,
                expected,
                source=source,
            )
        )
        errors.extend(
            expect_json_failure(
                root,
                cglc,
                tmp_dir,
                "recorded-planned-status-policy-drift-json",
                package,
                expected,
                source=source,
                manifest=planned_status_disallowed,
                expected_code="package.verify.invalid-manifest",
            )
        )

        package, _source, manifest = make_package(
            tmp_dir, "legacy-requirements-missing-native-status", status="emitted"
        )
        legacy_requirements = copy.deepcopy(manifest)
        del legacy_requirements["packageArtifactRequirements"]
        del legacy_requirements["artifacts"]["nativeBinaryStatus"]
        rewrite_manifest(package, legacy_requirements)
        errors.extend(
            expect_failure(
                cglc,
                "legacy-requirements-missing-native-status",
                package,
                "directx packages require nativeBinaryStatus",
            )
        )
        errors.extend(
            expect_json_failure(
                root,
                cglc,
                tmp_dir,
                "legacy-requirements-missing-native-status-json",
                package,
                "directx packages require nativeBinaryStatus",
                manifest=legacy_requirements,
                expected_code="package.verify.missing-native-status",
            )
        )

        package, _source, manifest = make_package(tmp_dir, "missing-backend-source")
        package_path(package, manifest["artifacts"]["backendSource"]).unlink()
        errors.extend(
            expect_failure(
                cglc,
                "missing-backend-source",
                package,
                "package artifact 'backendSource' does not exist",
            )
        )
        errors.extend(
            expect_json_failure(
                root,
                cglc,
                tmp_dir,
                "missing-backend-source-json",
                package,
                "package artifact 'backendSource' does not exist",
                manifest=manifest,
                expected_location=(
                    "manifest.json",
                    package / "manifest.json",
                    json.dumps(manifest["artifacts"]["backendSource"]),
                    None,
                ),
            )
        )

        package, _source, manifest = make_package(tmp_dir, "directory-artifact")
        backend_source_path = package_path(
            package, manifest["artifacts"]["backendSource"]
        )
        backend_source_path.unlink()
        backend_source_path.mkdir()
        errors.extend(
            expect_failure(
                cglc,
                "directory-artifact",
                package,
                "package artifact 'backendSource' is not a file",
            )
        )
        errors.extend(
            expect_json_failure(
                root,
                cglc,
                tmp_dir,
                "directory-artifact-json",
                package,
                "package artifact 'backendSource' is not a file",
                manifest=manifest,
            )
        )

        package, _source, manifest = make_package(tmp_dir, "empty-artifact-path")
        empty_artifact_manifest = copy.deepcopy(manifest)
        empty_artifact_manifest["artifacts"]["backendSource"] = ""
        rewrite_manifest(package, empty_artifact_manifest)
        errors.extend(
            expect_failure(
                cglc,
                "empty-artifact-path",
                package,
                "path must not be empty",
            )
        )

        package, _source, manifest = make_package(tmp_dir, "backslash-artifact")
        backslash_artifact_manifest = copy.deepcopy(manifest)
        backslash_artifact_manifest["artifacts"]["backendSource"] = (
            "backend\\directx\\StorageBufferComputeShader.hlsl"
        )
        rewrite_manifest(package, backslash_artifact_manifest)
        errors.extend(
            expect_failure(
                cglc,
                "backslash-artifact",
                package,
                "artifact paths must use '/' separators",
            )
        )

        package, _source, manifest = make_package(tmp_dir, "escaping-artifact")
        escaping_manifest = copy.deepcopy(manifest)
        escaping_manifest["artifacts"]["backendSource"] = "../outside.hlsl"
        rewrite_manifest(package, escaping_manifest)
        errors.extend(
            expect_failure(
                cglc,
                "escaping-artifact",
                package,
                "package artifact 'backendSource' path must stay inside package",
            )
        )

        package, _source, manifest = make_package(tmp_dir, "missing-debug-pair")
        missing_debug_pair = copy.deepcopy(manifest)
        del missing_debug_pair["artifacts"]["hirSourceMap"]
        rewrite_manifest(package, missing_debug_pair)
        expected = (
            "debug artifact pair mismatch: "
            "debugMetadata 'ir/debug-metadata.json' requires hirSourceMap"
        )
        errors.extend(
            expect_failure(
                cglc,
                "missing-debug-pair",
                package,
                expected,
            )
        )
        errors.extend(
            expect_json_failure(
                root,
                cglc,
                tmp_dir,
                "missing-debug-pair-json",
                package,
                expected,
                manifest=missing_debug_pair,
                expected_code="package.verify.debug-artifact-pair",
            )
        )

        package, _source, manifest = make_package(tmp_dir, "missing-debug-metadata")
        missing_debug_metadata = copy.deepcopy(manifest)
        del missing_debug_metadata["artifacts"]["debugMetadata"]
        rewrite_manifest(package, missing_debug_metadata)
        expected = (
            "debug artifact pair mismatch: "
            "hirSourceMap 'ir/hir-source-map.json' requires debugMetadata"
        )
        errors.extend(
            expect_json_failure(
                root,
                cglc,
                tmp_dir,
                "missing-debug-metadata-json",
                package,
                expected,
                manifest=missing_debug_metadata,
                expected_code="package.verify.debug-artifact-pair",
            )
        )

        package, _source, manifest = make_package(
            tmp_dir, "missing-debug-metadata-file"
        )
        delete_artifact_path(package, manifest, "debugMetadata")
        errors.extend(
            expect_json_failure(
                root,
                cglc,
                tmp_dir,
                "missing-debug-metadata-file-json",
                package,
                "package artifact 'debugMetadata' does not exist: "
                "ir/debug-metadata.json",
                manifest=manifest,
                expected_code="package.verify.missing-artifact",
            )
        )

        package, _source, manifest = make_package(
            tmp_dir, "missing-hir-source-map-file"
        )
        delete_artifact_path(package, manifest, "hirSourceMap")
        errors.extend(
            expect_json_failure(
                root,
                cglc,
                tmp_dir,
                "missing-hir-source-map-file-json",
                package,
                "package artifact 'hirSourceMap' does not exist: "
                "ir/hir-source-map.json",
                manifest=manifest,
                expected_code="package.verify.missing-artifact",
            )
        )

        package, _source, manifest = make_package(
            tmp_dir, "source-remap-granularity-drift"
        )
        source_remap_manifest = copy.deepcopy(manifest)
        source_remap_manifest["artifacts"]["sourceRemap"] = (
            "ir/source-remap-provenance.json"
        )
        write_json(
            package_path(package, source_remap_manifest["artifacts"]["sourceRemap"]),
            source_remap_provenance(source_remap_manifest, mapping_granularity="line"),
        )
        rewrite_manifest(package, source_remap_manifest)
        expected = (
            "sourceRemap 'ir/source-remap-provenance.json' "
            "mappingGranularity must be source-span"
        )
        errors.extend(
            expect_failure(
                cglc,
                "source-remap-granularity-drift",
                package,
                expected,
            )
        )
        errors.extend(
            expect_json_failure(
                root,
                cglc,
                tmp_dir,
                "source-remap-granularity-drift-json",
                package,
                expected,
                manifest=source_remap_manifest,
                expected_code=(
                    "package.verify.source-remap-provenance-granularity-mismatch"
                ),
            )
        )

        package, source, manifest = make_package(
            tmp_dir, "source-remap-nested-target-normalized"
        )
        source_remap_manifest = copy.deepcopy(manifest)
        source_remap_manifest["artifacts"]["sourceRemap"] = (
            "ir/source-remap-provenance.json"
        )
        provenance = source_remap_provenance(source_remap_manifest)
        provenance["sourceRemap"]["target"] = "metal"
        write_json(
            package_path(package, source_remap_manifest["artifacts"]["sourceRemap"]),
            provenance,
        )
        rewrite_manifest(package, source_remap_manifest)
        errors.extend(
            expect_success(
                cglc,
                "source-remap-nested-target-normalized",
                package,
                "StorageBufferComputeShader for directx",
                source=source,
            )
        )
        errors.extend(
            expect_json_success(
                root,
                cglc,
                tmp_dir,
                "source-remap-nested-target-normalized-json",
                package,
                source_remap_manifest,
                source=source,
            )
        )

        package, _source, manifest = make_package(
            tmp_dir, "source-remap-nested-target-drift"
        )
        source_remap_manifest = copy.deepcopy(manifest)
        source_remap_manifest["artifacts"]["sourceRemap"] = (
            "ir/source-remap-provenance.json"
        )
        provenance = source_remap_provenance(source_remap_manifest)
        provenance["sourceRemap"]["target"] = "Metal"
        write_json(
            package_path(package, source_remap_manifest["artifacts"]["sourceRemap"]),
            provenance,
        )
        rewrite_manifest(package, source_remap_manifest)
        expected = (
            "sourceRemap 'ir/source-remap-provenance.json' "
            "sourceRemap.target must be a normalized target name when recorded"
        )
        errors.extend(
            expect_failure(
                cglc,
                "source-remap-nested-target-drift",
                package,
                expected,
            )
        )
        errors.extend(
            expect_json_failure(
                root,
                cglc,
                tmp_dir,
                "source-remap-nested-target-drift-json",
                package,
                expected,
                manifest=source_remap_manifest,
                expected_code=(
                    "package.verify.source-remap-provenance-source-remap-target-invalid"
                ),
            )
        )

        package, _source, manifest = make_package(
            tmp_dir, "backend-source-map-target-drift"
        )
        add_backend_source_map(
            package,
            manifest,
            mutate=lambda document: document.update({"target": "metal"}),
        )
        expected = (
            "backendSourceMap "
            "'backend/directx/StorageBufferComputeShader.backend-source-map.json' "
            "target must match package target 'directx'"
        )
        errors.extend(
            expect_failure(
                cglc,
                "backend-source-map-target-drift",
                package,
                expected,
            )
        )
        errors.extend(
            expect_json_failure(
                root,
                cglc,
                tmp_dir,
                "backend-source-map-target-drift-json",
                package,
                expected,
                manifest=manifest,
                expected_code="package.verify.backend-source-map-target-mismatch",
            )
        )

        package, _source, manifest = make_package(
            tmp_dir, "backend-source-map-language-drift"
        )
        add_backend_source_map(
            package,
            manifest,
            mutate=lambda document: (
                document.update({"targetBackend": "msl"}),
                document["backend"].update({"language": "msl"}),
            ),
        )
        expected = (
            "backendSourceMap "
            "'backend/directx/StorageBufferComputeShader.backend-source-map.json' "
            "targetBackend must match backend.language and the package target "
            "backend language"
        )
        errors.extend(
            expect_failure(
                cglc,
                "backend-source-map-language-drift",
                package,
                expected,
            )
        )
        errors.extend(
            expect_json_failure(
                root,
                cglc,
                tmp_dir,
                "backend-source-map-language-drift-json",
                package,
                expected,
                manifest=manifest,
                expected_code="package.verify.backend-source-map-language-mismatch",
            )
        )

        package, _source, manifest = make_package(
            tmp_dir, "backend-source-map-line-count-drift"
        )
        add_backend_source_map(
            package,
            manifest,
            mutate=lambda document: document["backend"].update({"lineCount": 2}),
        )
        expected = (
            "backendSourceMap "
            "'backend/directx/StorageBufferComputeShader.backend-source-map.json' "
            "backend.lineCount must match backend source line count"
        )
        errors.extend(
            expect_failure(
                cglc,
                "backend-source-map-line-count-drift",
                package,
                expected,
            )
        )
        errors.extend(
            expect_json_failure(
                root,
                cglc,
                tmp_dir,
                "backend-source-map-line-count-drift-json",
                package,
                expected,
                manifest=manifest,
                expected_code=("package.verify.backend-source-map-line-count-mismatch"),
            )
        )

        package, _source, manifest = make_package(
            tmp_dir, "backend-source-map-source-remap-target-drift"
        )
        manifest["artifacts"]["sourceRemap"] = "ir/source-remap-provenance.json"
        source_remap = source_remap_metadata_from_provenance(manifest)
        del manifest["artifacts"]["sourceRemap"]
        source_remap["target"] = "Metal"
        add_backend_source_map(package, manifest, source_remap=source_remap)
        expected = (
            "backendSourceMap "
            "'backend/directx/StorageBufferComputeShader.backend-source-map.json' "
            "sourceRemap.target must be a normalized target name when recorded"
        )
        errors.extend(
            expect_failure(
                cglc,
                "backend-source-map-source-remap-target-drift",
                package,
                expected,
            )
        )
        errors.extend(
            expect_json_failure(
                root,
                cglc,
                tmp_dir,
                "backend-source-map-source-remap-target-drift-json",
                package,
                expected,
                manifest=manifest,
                expected_code=(
                    "package.verify.backend-source-map-source-remap-target-invalid"
                ),
            )
        )

        package, source, manifest = make_package(
            tmp_dir, "backend-source-map-source-remap-target-normalized"
        )
        manifest["artifacts"]["sourceRemap"] = "ir/source-remap-provenance.json"
        source_remap = source_remap_metadata_from_provenance(manifest)
        del manifest["artifacts"]["sourceRemap"]
        source_remap["target"] = "metal"
        add_backend_source_map(package, manifest, source_remap=source_remap)
        errors.extend(
            expect_success(
                cglc,
                "backend-source-map-source-remap-target-normalized",
                package,
                "StorageBufferComputeShader for directx",
                source=source,
            )
        )
        errors.extend(
            expect_json_success(
                root,
                cglc,
                tmp_dir,
                "backend-source-map-source-remap-target-normalized-json",
                package,
                manifest,
                source=source,
            )
        )

        package, _source, manifest = make_package(
            tmp_dir, "backend-source-map-source-remap-drift"
        )
        manifest["artifacts"]["sourceRemap"] = "ir/source-remap-provenance.json"
        write_json(
            package_path(package, manifest["artifacts"]["sourceRemap"]),
            source_remap_provenance(manifest),
        )
        source_remap = source_remap_metadata_from_provenance(manifest)
        source_remap["generatedFile"] = "generated/stale.cgl"
        add_backend_source_map(package, manifest, source_remap=source_remap)
        expected = (
            "backendSourceMap "
            "'backend/directx/StorageBufferComputeShader.backend-source-map.json' "
            "sourceRemap metadata must match sourceRemap provenance"
        )
        errors.extend(
            expect_failure(
                cglc,
                "backend-source-map-source-remap-drift",
                package,
                expected,
            )
        )
        errors.extend(
            expect_json_failure(
                root,
                cglc,
                tmp_dir,
                "backend-source-map-source-remap-drift-json",
                package,
                expected,
                manifest=manifest,
                expected_code=(
                    "package.verify.backend-source-map-source-remap-provenance-mismatch"
                ),
            )
        )

        package, _source, manifest = make_package(
            tmp_dir, "verify-debug-source-location-drift"
        )
        source_location_drift_map = hir_source_map_with_all_record_kinds()
        write_json(
            package_path(package, manifest["artifacts"]["hirSourceMap"]),
            source_location_drift_map,
        )
        expected = (
            "hirSourceMap 'ir/hir-source-map.json' hirSourceLocations must match "
            "debugMetadata 'ir/debug-metadata.json'"
        )
        errors.extend(
            expect_failure(
                cglc,
                "verify-debug-source-location-drift",
                package,
                expected,
            )
        )
        errors.extend(
            expect_json_failure(
                root,
                cglc,
                tmp_dir,
                "verify-debug-source-location-drift-json",
                package,
                expected,
                manifest=manifest,
                expected_code="package.verify.debug-source-locations-mismatch",
            )
        )

        package, _source, manifest = make_package(
            tmp_dir, "verify-filtered-hir-source-map"
        )
        filtered_source_map = hir_source_map_with_all_record_kinds()
        rewrite_debug_metadata_locations(package, manifest, filtered_source_map)
        filtered_source_map["filters"] = {
            "activeCount": 1,
            "expressionKind": "literal",
        }
        write_json(
            package_path(package, manifest["artifacts"]["hirSourceMap"]),
            filtered_source_map,
        )
        expected = "hirSourceMap 'ir/hir-source-map.json' must be unfiltered"
        errors.extend(
            expect_failure(
                cglc,
                "verify-filtered-hir-source-map",
                package,
                expected,
            )
        )
        errors.extend(
            expect_json_failure(
                root,
                cglc,
                tmp_dir,
                "verify-filtered-hir-source-map-json",
                package,
                expected,
                manifest=manifest,
                expected_code="package.verify.debug-source-map-filtered",
            )
        )

        package, _source, manifest = make_package(
            tmp_dir, "verify-paged-hir-source-map"
        )
        paged_source_map = hir_source_map_with_all_record_kinds()
        rewrite_debug_metadata_locations(package, manifest, paged_source_map)
        paged_source_map["pagination"]["activeCount"] = 1
        paged_source_map["pagination"]["expressionLimit"] = 0
        write_json(
            package_path(package, manifest["artifacts"]["hirSourceMap"]),
            paged_source_map,
        )
        expected = "hirSourceMap 'ir/hir-source-map.json' pagination must be inactive"
        errors.extend(
            expect_failure(
                cglc,
                "verify-paged-hir-source-map",
                package,
                expected,
            )
        )
        errors.extend(
            expect_json_failure(
                root,
                cglc,
                tmp_dir,
                "verify-paged-hir-source-map-json",
                package,
                expected,
                manifest=manifest,
                expected_code="package.verify.debug-source-map-paged",
            )
        )

        package, _source, manifest = make_package(
            tmp_dir, "verify-recorded-hir-source-map"
        )
        recorded_source_map = hir_source_map_with_all_record_kinds()
        rewrite_debug_metadata_locations(package, manifest, recorded_source_map)
        recorded_source_map["records"]["enabled"] = True
        recorded_source_map["records"]["limit"] = 0
        write_json(
            package_path(package, manifest["artifacts"]["hirSourceMap"]),
            recorded_source_map,
        )
        expected = "hirSourceMap 'ir/hir-source-map.json' records must be disabled"
        errors.extend(
            expect_failure(
                cglc,
                "verify-recorded-hir-source-map",
                package,
                expected,
            )
        )
        errors.extend(
            expect_json_failure(
                root,
                cglc,
                tmp_dir,
                "verify-recorded-hir-source-map-json",
                package,
                expected,
                manifest=manifest,
                expected_code="package.verify.debug-source-map-records-enabled",
            )
        )

        package, _source, manifest = make_package(
            tmp_dir, "verify-category-drift-hir-source-map"
        )
        category_drift_map = hir_source_map_with_all_record_kinds()
        rewrite_debug_metadata_locations(package, manifest, category_drift_map)
        category_drift_map["categoryCounts"]["expressionKinds"] = [
            {
                "name": "binary",
                "count": 1,
            },
        ]
        write_json(
            package_path(package, manifest["artifacts"]["hirSourceMap"]),
            category_drift_map,
        )
        expected = (
            "hirSourceMap 'ir/hir-source-map.json' categoryCounts must match "
            "hirSourceLocations"
        )
        errors.extend(
            expect_failure(
                cglc,
                "verify-category-drift-hir-source-map",
                package,
                expected,
            )
        )
        errors.extend(
            expect_json_failure(
                root,
                cglc,
                tmp_dir,
                "verify-category-drift-hir-source-map-json",
                package,
                expected,
                manifest=manifest,
                expected_code="package.verify.debug-source-map-category-counts",
            )
        )

        package, _source, manifest = make_package(
            tmp_dir, "verify-record-total-drift-hir-source-map"
        )
        record_total_drift_map = hir_source_map_with_all_record_kinds()
        rewrite_debug_metadata_locations(package, manifest, record_total_drift_map)
        record_total_drift_map["records"]["totalCount"] = 2
        write_json(
            package_path(package, manifest["artifacts"]["hirSourceMap"]),
            record_total_drift_map,
        )
        expected = (
            "hirSourceMap 'ir/hir-source-map.json' records.totalCount must match "
            "categoryCounts.recordTotalCount"
        )
        errors.extend(
            expect_failure(
                cglc,
                "verify-record-total-drift-hir-source-map",
                package,
                expected,
            )
        )
        errors.extend(
            expect_json_failure(
                root,
                cglc,
                tmp_dir,
                "verify-record-total-drift-hir-source-map-json",
                package,
                expected,
                manifest=manifest,
                expected_code="package.verify.debug-source-map-record-total",
            )
        )

        package, _source, manifest = make_package(tmp_dir, "missing-native-status")
        missing_native_status = copy.deepcopy(manifest)
        del missing_native_status["artifacts"]["nativeBinaryStatus"]
        rewrite_manifest(package, missing_native_status)
        errors.extend(
            expect_failure(
                cglc,
                "missing-native-status",
                package,
                "directx packages require nativeBinaryStatus",
            )
        )

        package, _source, manifest = make_package(tmp_dir, "status-without-native")
        status_without_native = copy.deepcopy(manifest)
        del status_without_native["artifacts"]["nativeBinary"]
        rewrite_manifest(package, status_without_native)
        errors.extend(
            expect_failure(
                cglc,
                "status-without-native",
                package,
                "nativeBinaryStatus requires nativeBinary",
            )
        )

        package, source, manifest = make_package(
            tmp_dir, "planned-status-produced-native"
        )
        write_json(
            package_path(package, manifest["artifacts"]["nativeBinary"]),
            {"fixture": "planned native binary should not be produced"},
        )
        expected = (
            "nativeBinaryStatus planned requires the nativeBinary artifact path "
            "to be declared but not produced"
        )
        errors.extend(
            expect_failure(
                cglc,
                "planned-status-produced-native",
                package,
                expected,
                source=source,
            )
        )
        errors.extend(
            expect_json_failure(
                root,
                cglc,
                tmp_dir,
                "planned-status-produced-native-json",
                package,
                expected,
                source=source,
                manifest=manifest,
                expected_code=(
                    "package.verify.planned-native-status-with-produced-native"
                ),
            )
        )

        package, _source, manifest = make_package(tmp_dir, "reflection-mismatch")
        reflection_mismatch = base_reflection(manifest)
        reflection_mismatch["nativeBinary"] = "backend/directx/other.dxil"
        write_json(package / "reflection.json", reflection_mismatch)
        errors.extend(
            expect_failure(
                cglc,
                "reflection-mismatch",
                package,
                "reflection nativeBinary must match manifest artifacts.nativeBinary",
            )
        )

        package, _source, manifest = make_package(
            tmp_dir, "reflection-backslash-native-binary"
        )
        reflection_backslash = base_reflection(manifest)
        reflection_backslash["nativeBinary"] = (
            "backend\\directx\\StorageBufferComputeShader.dxil"
        )
        write_json(package / "reflection.json", reflection_backslash)
        errors.extend(
            expect_failure(
                cglc,
                "reflection-backslash-native-binary",
                package,
                "reflection nativeBinary path must use '/' separators",
            )
        )
        errors.extend(
            expect_json_failure(
                root,
                cglc,
                tmp_dir,
                "reflection-backslash-native-binary-json",
                package,
                "reflection nativeBinary path must use '/' separators",
                manifest=manifest,
                expected_location=(
                    "reflection.json",
                    package / "reflection.json",
                    '"nativeBinary"',
                    '"entryPoints"',
                ),
            )
        )

        package, _source, manifest = make_package(
            tmp_dir, "reflection-parent-native-binary"
        )
        reflection_parent = base_reflection(manifest)
        reflection_parent["nativeBinary"] = "../StorageBufferComputeShader.dxil"
        write_json(package / "reflection.json", reflection_parent)
        errors.extend(
            expect_failure(
                cglc,
                "reflection-parent-native-binary",
                package,
                "reflection nativeBinary path must stay inside package",
            )
        )

        package, _source, manifest = make_package(
            tmp_dir, "reflection-absolute-native-binary"
        )
        reflection_absolute = base_reflection(manifest)
        reflection_absolute["nativeBinary"] = (
            package_path(package, manifest["artifacts"]["nativeBinary"])
            .resolve(strict=False)
            .as_posix()
        )
        write_json(package / "reflection.json", reflection_absolute)
        errors.extend(
            expect_failure(
                cglc,
                "reflection-absolute-native-binary",
                package,
                "reflection nativeBinary path must be package-relative",
            )
        )

        package, source, manifest = make_package(
            tmp_dir, "reflection-resource-target-binding-missing"
        )
        reflection_missing_binding = write_storage_image_reflection(package, manifest)
        reflection_missing_binding["targetResourceBindings"] = (
            reflection_missing_binding["targetResourceBindings"][1:]
        )
        write_json(package / "reflection.json", reflection_missing_binding)
        errors.extend(
            expect_reflection_binding_failure(
                root,
                cglc,
                tmp_dir,
                "reflection-resource-target-binding-missing",
                package,
                source,
                manifest,
                "is missing selected-target resource binding",
                "package.verify.reflection-resource-target-binding-missing",
            )
        )

        package, source, manifest = make_package(
            tmp_dir, "reflection-target-binding-source-missing"
        )
        reflection_stale_binding = write_storage_image_reflection(package, manifest)
        stale_binding = copy.deepcopy(
            reflection_stale_binding["targetResourceBindings"][0]
        )
        stale_binding["name"] = "orphanImage"
        reflection_stale_binding["targetResourceBindings"].append(stale_binding)
        write_json(package / "reflection.json", reflection_stale_binding)
        errors.extend(
            expect_reflection_binding_failure(
                root,
                cglc,
                tmp_dir,
                "reflection-target-binding-source-missing",
                package,
                source,
                manifest,
                "has no reflected source resource",
                "package.verify.reflection-target-binding-source-missing",
            )
        )

        package, source, manifest = make_package(
            tmp_dir, "reflection-target-binding-source-type-mismatch"
        )
        reflection_source_type_mismatch = write_storage_image_reflection(
            package, manifest
        )
        reflection_source_type_mismatch["targetResourceBindings"][0]["sourceType"] = (
            "uimage2DArray[IMAGE_COUNT]"
        )
        write_json(package / "reflection.json", reflection_source_type_mismatch)
        errors.extend(
            expect_reflection_binding_failure(
                root,
                cglc,
                tmp_dir,
                "reflection-target-binding-source-type-mismatch",
                package,
                source,
                manifest,
                "sourceType must match reflected resource",
                "package.verify.reflection-target-resource-identity-mismatch",
            )
        )

        package, source, manifest = make_package(
            tmp_dir, "reflection-target-binding-array-dimensions-mismatch"
        )
        reflection_array_dimensions_mismatch = write_storage_image_reflection(
            package, manifest
        )
        reflection_array_dimensions_mismatch["targetResourceBindings"][1][
            "arrayDimensions"
        ][0]["elementCount"] = STORAGE_IMAGE_ARRAY_ELEMENT_COUNT + 1
        write_json(package / "reflection.json", reflection_array_dimensions_mismatch)
        errors.extend(
            expect_reflection_binding_failure(
                root,
                cglc,
                tmp_dir,
                "reflection-target-binding-array-dimensions-mismatch",
                package,
                source,
                manifest,
                "arrayDimensions must match reflected resource array metadata",
                "package.verify.reflection-target-resource-binding-array-mismatch",
            )
        )

        shared_address_space_cases = (
            ("directx", "groupshared"),
            ("vulkan", "Workgroup"),
            ("metal", "threadgroup"),
            ("opengl", "shared"),
        )
        for target, binding_address_space in shared_address_space_cases:
            case_name = f"reflection-shared-address-space-{target}"
            package, source, manifest = make_package(
                tmp_dir,
                case_name,
                target=target,
            )
            if target in {"metal", "vulkan"}:
                add_native_artifact_descriptor(
                    package, manifest, mutate=mark_native_artifact_validated
                )
            write_json(
                package / "reflection.json",
                shared_address_space_reflection(manifest, binding_address_space),
            )
            errors.extend(
                expect_success(
                    cglc,
                    case_name,
                    package,
                    f"StorageBufferComputeShader for {target}",
                    source=source,
                )
            )
            errors.extend(
                expect_json_success(
                    root,
                    cglc,
                    tmp_dir,
                    f"{case_name}-json",
                    package,
                    manifest,
                    source=source,
                )
            )

        package, source, manifest = make_package(
            tmp_dir, "reflection-target-binding-evidence-missing"
        )
        reflection_evidence_missing = shared_address_space_reflection(
            manifest, "groupshared"
        )
        del reflection_evidence_missing["targetResourceBindings"][0]["evidenceId"]
        write_json(package / "reflection.json", reflection_evidence_missing)
        errors.extend(
            expect_reflection_binding_failure(
                root,
                cglc,
                tmp_dir,
                "reflection-target-binding-evidence-missing",
                package,
                source,
                manifest,
                "must record target legalization resource binding evidenceId",
                ("package.verify.reflection-target-resource-binding-evidence-missing"),
            )
        )

        package, source, manifest = make_package(
            tmp_dir, "reflection-target-binding-evidence-invalid"
        )
        reflection_evidence_invalid = shared_address_space_reflection(
            manifest, "groupshared"
        )
        reflection_evidence_invalid["targetResourceBindings"][0]["evidenceId"] = (
            "target-legalization.v1.metal.resource-binding.compute.compute_main.tile"
        )
        write_json(package / "reflection.json", reflection_evidence_invalid)
        errors.extend(
            expect_reflection_binding_failure(
                root,
                cglc,
                tmp_dir,
                "reflection-target-binding-evidence-invalid",
                package,
                source,
                manifest,
                (
                    "evidenceId must use target legalization resource binding "
                    "prefix 'target-legalization.v1.directx.resource-binding.'"
                ),
                ("package.verify.reflection-target-resource-binding-evidence-invalid"),
            )
        )

        package, source, manifest = make_package(
            tmp_dir, "reflection-target-binding-evidence-duplicate"
        )
        reflection_evidence_duplicate = write_storage_image_reflection(
            package, manifest
        )
        reflection_evidence_duplicate["targetResourceBindings"][1]["evidenceId"] = (
            reflection_evidence_duplicate["targetResourceBindings"][0]["evidenceId"]
        )
        write_json(package / "reflection.json", reflection_evidence_duplicate)
        errors.extend(
            expect_reflection_binding_failure(
                root,
                cglc,
                tmp_dir,
                "reflection-target-binding-evidence-duplicate",
                package,
                source,
                manifest,
                "duplicates target legalization resource binding evidenceId",
                (
                    "package.verify.reflection-target-resource-binding-"
                    "evidence-duplicate"
                ),
            )
        )

        package, _source, manifest = make_graphics_abi_release_package(
            tmp_dir, "graphics-abi-target-evidence-mismatch"
        )
        drift_graphics_abi_evidence(package, manifest)
        errors.extend(
            expect_json_failure(
                root,
                cglc,
                tmp_dir,
                "graphics-abi-target-evidence-mismatch-json",
                package,
                "field 'evidenceId' must match reflection",
                manifest=manifest,
                expected_code="package.verify.graphics-abi-target-evidence-mismatch",
            )
        )

        package, _source, missing_graphics_abi_manifest = (
            make_graphics_abi_release_package(
                tmp_dir,
                "graphics-abi-missing-artifact",
                include_graphics_abi=False,
            )
        )
        errors.extend(
            expect_json_failure(
                root,
                cglc,
                tmp_dir,
                "graphics-abi-missing-artifact-json",
                package,
                "graphics package reflection requires manifest.artifacts.graphicsAbi",
                manifest=missing_graphics_abi_manifest,
                expected_code="package.verify.graphics-abi-missing-artifact",
            )
        )

        package, source, manifest = make_package(
            tmp_dir, "reflection-target-feature-evidence-invalid"
        )
        reflection_feature_invalid = write_storage_image_reflection(package, manifest)
        reflection_feature_invalid["targetFeatures"][0]["evidenceIds"] = [
            "target-legalization.v1.metal.capability.required."
            "metal.resource.storage-image"
        ]
        write_json(package / "reflection.json", reflection_feature_invalid)
        errors.extend(
            expect_reflection_feature_failure(
                root,
                cglc,
                tmp_dir,
                "reflection-target-feature-evidence-invalid",
                package,
                source,
                manifest,
                (
                    "evidenceId must use target legalization feature prefix "
                    "'target-legalization.v1.directx.'"
                ),
                "package.verify.reflection-target-feature-evidence-invalid",
            )
        )

        package, source, manifest = make_package(
            tmp_dir, "reflection-target-feature-evidence-capability-target"
        )
        reflection_feature_capability_target = write_storage_image_reflection(
            package, manifest
        )
        reflection_feature_capability_target["targetFeatures"][0]["evidenceIds"] = [
            "target-legalization.v1.directx.capability.required."
            "metal.resource.storage-image"
        ]
        write_json(package / "reflection.json", reflection_feature_capability_target)
        errors.extend(
            expect_reflection_feature_failure(
                root,
                cglc,
                tmp_dir,
                "reflection-target-feature-evidence-capability-target",
                package,
                source,
                manifest,
                "evidenceId capability target must be 'directx', got 'metal'",
                ("package.verify.reflection-target-feature-evidence-capability-target"),
            )
        )

        package, source, manifest = make_package(
            tmp_dir, "reflection-target-feature-evidence-malformed"
        )
        reflection_feature_malformed = write_storage_image_reflection(package, manifest)
        reflection_feature_malformed["targetFeatures"][0]["evidenceIds"] = [
            "target-legalization.v1.directx.capability.required.directx"
        ]
        write_json(package / "reflection.json", reflection_feature_malformed)
        errors.extend(
            expect_reflection_feature_failure(
                root,
                cglc,
                tmp_dir,
                "reflection-target-feature-evidence-malformed",
                package,
                source,
                manifest,
                "evidenceId must be target legalization capability or ABI evidence",
                "package.verify.reflection-target-feature-evidence-invalid",
            )
        )

        package, source, manifest = make_package(
            tmp_dir, "reflection-target-feature-evidence-duplicate"
        )
        reflection_feature_duplicate = write_storage_image_reflection(package, manifest)
        reflection_feature_duplicate["targetFeatures"][1]["evidenceIds"] = list(
            reflection_feature_duplicate["targetFeatures"][0]["evidenceIds"]
        )
        write_json(package / "reflection.json", reflection_feature_duplicate)
        errors.extend(
            expect_reflection_feature_failure(
                root,
                cglc,
                tmp_dir,
                "reflection-target-feature-evidence-duplicate",
                package,
                source,
                manifest,
                "duplicates target legalization feature evidenceId",
                "package.verify.reflection-target-feature-evidence-duplicate",
            )
        )

        package, source, manifest = make_package(
            tmp_dir, "reflection-target-binding-address-space-mismatch"
        )
        write_json(
            package / "reflection.json",
            shared_address_space_reflection(manifest, "constant"),
        )
        errors.extend(
            expect_reflection_binding_failure(
                root,
                cglc,
                tmp_dir,
                "reflection-target-binding-address-space-mismatch",
                package,
                source,
                manifest,
                "addressSpace must match reflected resource",
                "package.verify.reflection-target-resource-identity-mismatch",
            )
        )

        package, _source, _manifest = make_package(tmp_dir, "directory-root-file")
        (package / "diagnostics.json").unlink()
        (package / "diagnostics.json").mkdir()
        errors.extend(
            expect_failure(
                cglc,
                "directory-root-file",
                package,
                "package diagnostics is not a regular file",
            )
        )

        package, _source, manifest = make_package(tmp_dir, "missing-source-hash")
        missing_source_hash_manifest = copy.deepcopy(manifest)
        del missing_source_hash_manifest["sourceHash"]
        rewrite_manifest(package, missing_source_hash_manifest)
        errors.extend(
            expect_failure(
                cglc,
                "missing-source-hash",
                package,
                "sourceHash must contain string algorithm and value fields",
            )
        )
        errors.extend(
            expect_json_failure(
                root,
                cglc,
                tmp_dir,
                "missing-source-hash-json",
                package,
                "sourceHash must contain string algorithm and value fields",
                manifest=missing_source_hash_manifest,
            )
        )

        package, _source, manifest = make_package(tmp_dir, "bad-source-hash-format")
        bad_hash_format_manifest = copy.deepcopy(manifest)
        bad_hash_format_manifest["sourceHash"]["value"] = "A" * 64
        rewrite_manifest(package, bad_hash_format_manifest)
        errors.extend(
            expect_failure(
                cglc,
                "bad-source-hash-format",
                package,
                "64 lowercase hexadecimal sha256",
            )
        )
        errors.extend(
            expect_json_failure(
                root,
                cglc,
                tmp_dir,
                "bad-source-hash-format-json",
                package,
                "64 lowercase hexadecimal sha256",
                manifest=bad_hash_format_manifest,
                expected_location=(
                    "manifest.json",
                    package / "manifest.json",
                    '"value"',
                    '"artifacts"',
                ),
            )
        )

        package, source, manifest = make_package(tmp_dir, "bad-source-hash")
        bad_hash_manifest = copy.deepcopy(manifest)
        bad_hash_manifest["sourceHash"]["value"] = "0" * 64
        rewrite_manifest(package, bad_hash_manifest)
        errors.extend(
            expect_failure(
                cglc,
                "bad-source-hash",
                package,
                "expected source hash",
                source=source,
            )
        )
        errors.extend(
            expect_json_failure(
                root,
                cglc,
                tmp_dir,
                "bad-source-hash-json",
                package,
                "expected source hash",
                source=source,
                manifest=bad_hash_manifest,
                expected_location=(
                    "manifest.json",
                    package / "manifest.json",
                    '"value"',
                    '"artifacts"',
                ),
            )
        )

        package, source, manifest = make_package(tmp_dir, "missing-source-file")
        source.unlink()
        errors.extend(
            expect_failure(
                cglc,
                "missing-source-file",
                package,
                "failed to read source file",
                source=source,
            )
        )
        errors.extend(
            expect_json_failure(
                root,
                cglc,
                tmp_dir,
                "missing-source-file-json",
                package,
                "failed to read source file",
                source=source,
                manifest=manifest,
                expected_code="package.verify.source-read-failed",
            )
        )

        errors.extend(
            expect_args_failure(
                cglc,
                "verify-path-required",
                ["package", "verify"],
                "Usage:",
            )
        )

    return errors


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--root",
        default=".",
        help="CrossGL-Compiler repository root",
    )
    parser.add_argument("--cglc", required=True, help="Path to cglc executable")
    parser.add_argument(
        "--jobs",
        type=positive_jobs,
        help=(
            "Run independent fixture cases in parallel; defaults to "
            f"${CROSSGL_PACKAGE_VERIFY_FIXTURE_JOBS}, then ${CROSSGL_CI_JOBS}, "
            "then 1."
        ),
    )
    args = parser.parse_args()
    if args.jobs is None:
        args.jobs = jobs_from_environment(parser)

    root = Path(args.root).resolve()
    if str(root / "tools") not in sys.path:
        sys.path.insert(0, str(root / "tools"))

    errors = run_cases(root, Path(args.cglc), jobs=args.jobs)
    if errors:
        for error in errors:
            print(f"package verify fixture check failed: {error}", file=sys.stderr)
        return 1

    print("validated package verify fixtures")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
