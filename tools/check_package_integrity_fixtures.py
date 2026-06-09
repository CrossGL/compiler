#!/usr/bin/env python3
"""Check package integrity validator behavior with synthetic packages."""

import argparse
import copy
import hashlib
import json
import subprocess
import sys
import tempfile
from pathlib import Path

from fixture_parallelism import extend_errors_from_fixture_tasks
from json_schema_semantics.target_explanation_v1 import (
    expected_legalization_core_evidence_ids,
)
from package_target_contracts import (
    PACKAGE_TARGETS_REQUIRING_NATIVE_STATUS,
    SOURCE_PACKAGE_TARGETS,
    TARGET_REQUIRED_ARTIFACTS,
    TARGET_REQUIRED_PATH_ARTIFACTS,
)


MODULE_NAME = "StorageBufferComputeShader"
DEBUG_TARGET_SUMMARY_TARGETS = ("metal", "vulkan", "directx", "opengl")
TARGET_EXPLANATION_SCHEMA_PATH = (
    Path(__file__).resolve().parents[1]
    / "docs"
    / "schemas"
    / "target-explanation-v1.schema.json"
)
_TARGET_EXPLANATION_TARGET_RECORD_PROPERTIES = None
TARGET_ARTIFACT_PATHS = {
    "metal": {
        "backendSource": "backend/metal/StorageBufferComputeShader.metal",
        "intermediate": "backend/metal/StorageBufferComputeShader.air",
        "nativeBinary": "backend/metal/StorageBufferComputeShader.metallib",
    },
    "vulkan": {
        "backendAssembly": "backend/vulkan/StorageBufferComputeShader.spvasm",
        "nativeBinary": "backend/vulkan/StorageBufferComputeShader.spv",
        "nativeProfile": "backend/vulkan/StorageBufferComputeShader.profile.json",
    },
    "directx": {
        "backendSource": "backend/directx/StorageBufferComputeShader.hlsl",
        "nativeBinary": "backend/directx/StorageBufferComputeShader.dxil",
    },
    "opengl": {
        "backendSource": "backend/opengl/StorageBufferComputeShader.comp.glsl",
        "nativeBinary": "backend/opengl/StorageBufferComputeShader.glsl",
    },
}

SOURCE_PACKAGE_GENERATOR_NAMES = {
    "directx": "CrossGL DirectX backend",
    "opengl": "CrossGL OpenGL backend",
}
VULKAN_DISASSEMBLY_PATH = "backend/vulkan/StorageBufferComputeShader.disassembly.spvasm"
NATIVE_ARTIFACT_DESCRIPTOR_PATH = "metadata/native-artifact.json"
NONUNIFORM_TARGET_FEATURES = {
    "directx": [
        {
            "target": "directx",
            "kind": "operation",
            "name": "nonuniform-descriptor-index",
        },
        {
            "target": "directx",
            "kind": "intrinsic",
            "name": "NonUniformResourceIndex",
        },
    ],
    "opengl": [
        {
            "target": "opengl",
            "kind": "operation",
            "name": "nonuniform-descriptor-index",
        },
        {
            "target": "opengl",
            "kind": "extension",
            "name": "GL_EXT_nonuniform_qualifier",
        },
    ],
    "vulkan": [
        {
            "target": "vulkan",
            "kind": "operation",
            "name": "nonuniform-descriptor-index",
        },
        {
            "target": "vulkan",
            "kind": "extension",
            "name": "SPV_EXT_descriptor_indexing",
        },
        {
            "target": "vulkan",
            "kind": "capability",
            "name": "ShaderNonUniformEXT",
        },
        {
            "target": "vulkan",
            "kind": "capability",
            "name": "SampledImageArrayNonUniformIndexingEXT",
        },
        {
            "target": "vulkan",
            "kind": "capability",
            "name": "StorageBufferArrayNonUniformIndexingEXT",
        },
    ],
    "metal": [
        {
            "target": "metal",
            "kind": "operation",
            "name": "nonuniform-descriptor-index",
        },
        {
            "target": "metal",
            "kind": "operation",
            "name": "nonuniform-texture-descriptor-index",
        },
        {
            "target": "metal",
            "kind": "operation",
            "name": "nonuniform-sampler-descriptor-index",
        },
    ],
}
STORAGE_IMAGE_ARRAY_DIMENSION = {
    "source": "IMAGE_COUNT",
    "kind": "fixed",
    "elementCount": 2,
}
STORAGE_IMAGE_ARRAY_SIZE = "IMAGE_COUNT"
STORAGE_IMAGE_ARRAY_ELEMENT_COUNT = 2
STORAGE_IMAGE_READ_WRITE_FEATURES = (
    ("resource", "storage-image"),
    ("resource", "descriptor-array"),
    ("layout", "fixed-array"),
    ("storageImage", "read-write"),
    ("storageImage", "2d-dimension"),
    ("storageImage", "2d_array-dimension"),
    ("storageImage", "array-dimension"),
    ("storageImage", "rgba32f-format"),
    ("storageImage", "rgba32ui-format"),
    ("operation", "storage-image-read"),
    ("operation", "storage-image-write"),
)
STORAGE_IMAGE_ATOMIC_FEATURES = (
    ("resource", "storage-image"),
    ("resource", "descriptor-array"),
    ("layout", "fixed-array"),
    ("storageImage", "read-write"),
    ("storageImage", "2d-dimension"),
    ("storageImage", "2d_array-dimension"),
    ("storageImage", "array-dimension"),
    ("storageImage", "r32i-format"),
    ("storageImage", "r32ui-format"),
    ("operation", "storage-image-read"),
    ("operation", "storage-image-write"),
    ("operation", "storage-image-atomic-add"),
    ("operation", "storage-image-atomic-exchange"),
    ("operation", "storage-image-atomic-min"),
    ("operation", "storage-image-atomic-max"),
    ("operation", "storage-image-atomic-and"),
    ("operation", "storage-image-atomic-or"),
    ("operation", "storage-image-atomic-xor"),
)


def write_text(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")


def package_path(package, value):
    return package / Path(value)


def sha256_file(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def make_source(tmp_dir):
    source = tmp_dir / f"{MODULE_NAME}.cgl"
    write_text(
        source,
        f"shader {MODULE_NAME} {{\n  compute main() {{ }}\n}}\n",
    )
    return source


def expect_fixture_artifacts_cover_contract(target, artifacts):
    expected_path_artifacts = tuple(TARGET_REQUIRED_PATH_ARTIFACTS[target])
    actual_path_artifacts = tuple(
        artifact for artifact in artifacts if artifact in expected_path_artifacts
    )
    if actual_path_artifacts != expected_path_artifacts:
        raise AssertionError(
            f"{target} fixture artifact paths must cover package target "
            f"contract in order: expected {expected_path_artifacts!r}, "
            f"got {actual_path_artifacts!r}"
        )


def target_artifacts(target, status):
    artifacts = dict(TARGET_ARTIFACT_PATHS[target])
    expect_fixture_artifacts_cover_contract(target, artifacts)
    if target in PACKAGE_TARGETS_REQUIRING_NATIVE_STATUS:
        artifacts["nativeBinaryStatus"] = status
    expected_required_artifacts = tuple(TARGET_REQUIRED_ARTIFACTS[target])
    actual_required_artifacts = tuple(
        artifact for artifact in artifacts if artifact in expected_required_artifacts
    )
    if actual_required_artifacts != expected_required_artifacts:
        raise AssertionError(
            f"{target} fixture manifest artifacts must cover package target "
            f"contract in order: expected {expected_required_artifacts!r}, "
            f"got {actual_required_artifacts!r}"
        )
    artifacts["debugMetadata"] = "ir/debug-metadata.json"
    artifacts["hirSourceMap"] = "ir/hir-source-map.json"
    artifacts["targetExplanation"] = "ir/target-explanation.json"
    return artifacts


def package_artifact_requirements(target):
    source_package = target in SOURCE_PACKAGE_TARGETS
    requires_native_status = target in PACKAGE_TARGETS_REQUIRING_NATIVE_STATUS
    package_mode = "source-package" if source_package else "native"
    required_artifacts = list(TARGET_REQUIRED_PATH_ARTIFACTS[target])
    evidence_ids = [f"target-legalization.v1.{target}.package-artifacts.{package_mode}"]
    evidence_ids.extend(
        f"target-legalization.v1.{target}.package-artifact.required.{name}"
        for name in required_artifacts
    )
    if requires_native_status:
        evidence_ids.append(
            f"target-legalization.v1.{target}."
            "package-artifact.native-binary-status.required"
        )
    if source_package:
        evidence_ids.append(
            f"target-legalization.v1.{target}."
            "package-artifact.planned-native-binary.allowed"
        )
        evidence_ids.append(
            f"target-legalization.v1.{target}."
            "package-artifact.planned-native-source-evidence.allowed"
        )
    return {
        "target": target,
        "packageMode": package_mode,
        "requiredPathArtifacts": required_artifacts,
        "requiresNativeBinaryStatus": requires_native_status,
        "allowsPlannedNativeBinary": source_package,
        "allowsPlannedNativeSourceEvidence": source_package,
        "evidenceIds": evidence_ids,
    }


def package_artifact_requirement_evidence_ids(requirements):
    target = requirements.get("target")
    package_mode = requirements.get("packageMode")
    required_artifacts = requirements.get("requiredPathArtifacts", [])
    evidence_ids = [f"target-legalization.v1.{target}.package-artifacts.{package_mode}"]
    evidence_ids.extend(
        f"target-legalization.v1.{target}.package-artifact.required.{name}"
        for name in required_artifacts
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


def native_artifact_binary_kind(manifest):
    target = manifest["target"]
    if target == "metal":
        return "metal.metallib"
    if target == "vulkan":
        return "vulkan.spirv-module"
    if target == "directx":
        return "directx.dxil"
    if target == "opengl":
        return "opengl.source"
    raise ValueError(f"unsupported target {target!r}")


def native_artifact_source_path(manifest):
    binary_kind = native_artifact_binary_kind(manifest)
    if binary_kind == "vulkan.spirv-module":
        return manifest["artifacts"]["backendAssembly"]
    return manifest["artifacts"]["backendSource"]


def native_artifact_tools(manifest):
    target = manifest["target"]
    status = manifest["artifacts"].get("nativeBinaryStatus")
    if target in SOURCE_PACKAGE_TARGETS and status == "planned":
        return [
            {
                "name": SOURCE_PACKAGE_GENERATOR_NAMES[target],
                "role": "generator",
                "version": "fixture",
                "executable": "cglc",
            },
        ]
    if target == "metal":
        return [
            {
                "name": "xcrun metal",
                "role": "compiler",
                "version": "fixture",
                "executable": "xcrun",
            },
            {
                "name": "xcrun metallib",
                "role": "linker",
                "version": "fixture",
                "executable": "xcrun",
            },
        ]
    if target == "vulkan":
        return [
            {
                "name": "spirv-as",
                "role": "assembler",
                "version": "fixture",
                "executable": "spirv-as",
            },
        ]
    if target in {"directx", "opengl"}:
        return [
            {
                "name": f"CrossGL {target} backend",
                "role": "compiler" if target == "directx" else "generator",
                "version": "fixture",
                "executable": "cglc",
            },
        ]
    raise ValueError(f"unsupported target {target!r}")


def native_artifact_descriptor(package, manifest):
    source_path = native_artifact_source_path(manifest)
    source_file = package_path(package, source_path)
    native_status = manifest["artifacts"].get("nativeBinaryStatus")
    planned_source_package = (
        manifest["target"] in SOURCE_PACKAGE_TARGETS and native_status == "planned"
    )
    descriptor = {
        "schemaVersion": 1,
        "kind": "crossgl.nativeArtifact",
        "contractVersion": "native-artifact-v0",
        "target": manifest["target"],
        "binaryKind": native_artifact_binary_kind(manifest),
        "sourcePath": source_path,
        "sourceHash": {
            "algorithm": "sha256",
            "value": sha256_file(source_file),
        },
        "toolchainProvenance": {
            "producer": "cglc package fixture",
            "tools": native_artifact_tools(manifest),
            "invocation": {
                "commandLineSha256": "1" * 64,
                "environmentSha256": "2" * 64,
            },
        },
        "optimizationLevel": "unknown" if planned_source_package else "O0",
        "validationStatus": "unavailable",
        "validationDiagnostics": [],
    }
    if native_status is not None:
        descriptor["nativeBinaryStatus"] = native_status
    if native_status != "planned":
        artifact_path = manifest["artifacts"]["nativeBinary"]
        artifact_file = package_path(package, artifact_path)
        descriptor["artifactPath"] = artifact_path
        descriptor["artifactHash"] = {
            "algorithm": "sha256",
            "value": sha256_file(artifact_file),
        }
        descriptor["sizeBytes"] = artifact_file.stat().st_size
    return descriptor


def add_native_artifact_descriptor(package, manifest, mutate=None):
    manifest["artifacts"]["nativeArtifactDescriptor"] = NATIVE_ARTIFACT_DESCRIPTOR_PATH
    descriptor = native_artifact_descriptor(package, manifest)
    if mutate is not None:
        mutate(descriptor)
    write_json(package_path(package, NATIVE_ARTIFACT_DESCRIPTOR_PATH), descriptor)
    rewrite_manifest(package, manifest)
    return descriptor


def mark_native_artifact_validated(descriptor):
    descriptor["validationStatus"] = "validated"
    descriptor["toolchainProvenance"]["tools"].append(
        {
            "name": "native artifact fixture validator",
            "role": "validator",
            "version": "fixture",
            "executable": "native-artifact-validator",
        }
    )


def base_manifest(package, source, target="directx", status="planned"):
    source_hash = hashlib.sha256(source.read_bytes()).hexdigest()
    return {
        "schemaVersion": 1,
        "compiler": {
            "name": "CrossGL-Compiler",
            "version": "0.1.0",
            "llvmVersion": "fixture",
        },
        "module": MODULE_NAME,
        "target": target,
        "sourceHash": {
            "algorithm": "sha256",
            "value": source_hash,
        },
        "packageArtifactRequirements": package_artifact_requirements(target),
        "artifacts": target_artifacts(target, status),
    }


def base_reflection(manifest):
    return {
        "schemaVersion": 1,
        "module": manifest["module"],
        "target": manifest["target"],
        "nativeBinary": manifest["artifacts"]["nativeBinary"],
        "entryPoints": [
            {
                "stage": "compute",
                "sourceName": "main",
                "backendName": "compute_main",
                "returnType": "void",
                "parameters": [],
            },
        ],
        "structs": [],
        "resources": [],
        "targetResourceBindings": [],
        "pushConstants": [],
        "functionConstants": [],
        "vertexLayouts": [],
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


def nonuniform_target_features(target):
    return copy.deepcopy(NONUNIFORM_TARGET_FEATURES[target])


def storage_image_target_features(target, atomic=False):
    specs = (
        STORAGE_IMAGE_ATOMIC_FEATURES if atomic else STORAGE_IMAGE_READ_WRITE_FEATURES
    )
    return [
        {
            "target": target,
            "kind": kind,
            "name": name,
        }
        for kind, name in specs
    ]


def nonuniform_diagnostics(target):
    return {
        "schemaVersion": 1,
        "diagnostics": [
            {
                "severity": "note",
                "code": "package.fixture.nonuniform-target-feature",
                "message": (
                    f"{target} fixture carries nonuniform descriptor-index "
                    "target feature metadata"
                ),
                "location": source_location(0, 0),
                "target": target,
            },
        ],
    }


def write_nonuniform_reflection(package, manifest):
    reflection = base_reflection(manifest)
    reflection["targetFeatures"] = nonuniform_target_features(manifest["target"])
    write_json(package / "reflection.json", reflection)
    return reflection


def write_nonuniform_diagnostics(package, target):
    diagnostics = nonuniform_diagnostics(target)
    write_json(package / "diagnostics.json", diagnostics)
    return diagnostics


def storage_image_resource(name, source_type, binding, storage_format):
    resource = {
        "stage": "compute",
        "name": name,
        "kind": "storage_image",
        "type": source_type,
        "set": 0,
        "binding": binding,
        "storageImageFormat": storage_format,
    }
    if "[" in source_type:
        resource["arrayDimensions"] = [copy.deepcopy(STORAGE_IMAGE_ARRAY_DIMENSION)]
    return resource


def storage_image_base_type(source_type):
    return source_type.split("[", 1)[0]


def storage_image_scalar_type(source_type):
    base_type = storage_image_base_type(source_type)
    if base_type.startswith("uimage"):
        return "uint"
    if base_type.startswith("iimage"):
        return "int"
    return "float"


def storage_image_metal_type(resource):
    base_type = storage_image_base_type(resource["type"])
    scalar_type = storage_image_scalar_type(base_type)
    if base_type.endswith("Array"):
        metal_type = f"texture2d_array<{scalar_type}, access::read_write>"
    else:
        metal_type = f"texture2d<{scalar_type}, access::read_write>"
    if "arrayDimensions" in resource:
        return f"array<{metal_type}, {STORAGE_IMAGE_ARRAY_SIZE}>"
    return metal_type


def storage_image_spirv_format(storage_format):
    return {
        "rgba32f": "Rgba32f",
        "rgba32i": "Rgba32i",
        "rgba32ui": "Rgba32ui",
        "r32f": "R32f",
        "r32i": "R32i",
        "r32ui": "R32ui",
    }[storage_format]


def storage_image_spirv_type(resource):
    base_type = storage_image_base_type(resource["type"])
    scalar_type = storage_image_scalar_type(base_type)
    dimension = "2DArray" if base_type.endswith("Array") else "2D"
    image_type = (
        f"OpTypeImage<{scalar_type}, {dimension}, sampled=2, "
        f"format={storage_image_spirv_format(resource['storageImageFormat'])}>"
    )
    if "arrayDimensions" in resource:
        return f"OpTypeArray<{image_type}, {STORAGE_IMAGE_ARRAY_SIZE}>"
    return image_type


def storage_image_target_binding(target, resource):
    binding = {
        "target": target,
        "stage": "compute",
        "entryPoint": "compute_main",
        "name": resource["name"],
        "kind": "storage_image",
        "sourceType": resource["type"],
        "storageImageFormat": resource["storageImageFormat"],
    }
    if "arrayDimensions" in resource:
        binding["arraySize"] = STORAGE_IMAGE_ARRAY_SIZE
        binding["arrayElementCount"] = STORAGE_IMAGE_ARRAY_ELEMENT_COUNT
        binding["arrayDimensions"] = copy.deepcopy(resource["arrayDimensions"])

    if target == "directx":
        binding.update(
            {
                "addressSpace": "unordered-access",
                "abi": "registerBinding",
                "bindingClass": "uav",
                "descriptorType": "UAV",
                "set": resource["set"],
                "binding": resource["binding"],
                "argumentIndex": resource["binding"],
            }
        )
    elif target == "opengl":
        binding.update(
            {
                "addressSpace": "image",
                "abi": "programResourceBinding",
                "bindingClass": "image",
                "set": resource["set"],
                "binding": resource["binding"],
                "argumentIndex": resource["binding"],
            }
        )
    elif target == "vulkan":
        binding.update(
            {
                "addressSpace": "UniformConstant",
                "abi": "descriptor",
                "bindingClass": "storageImage",
                "descriptorType": "VK_DESCRIPTOR_TYPE_STORAGE_IMAGE",
                "storageClass": "UniformConstant",
                "spirvType": storage_image_spirv_type(resource),
                "set": resource["set"],
                "binding": resource["binding"],
            }
        )
    elif target == "metal":
        binding.update(
            {
                "addressSpace": "texture",
                "abi": "kernelArgument",
                "bindingClass": "texture",
                "metalType": storage_image_metal_type(resource),
                "set": resource["set"],
                "binding": resource["binding"],
                "argumentIndex": resource["binding"],
            }
        )
    else:
        raise ValueError(f"unsupported target {target!r}")

    return binding


def write_storage_image_reflection(package, manifest, atomic=False):
    target = manifest["target"]
    if atomic:
        resources = [
            storage_image_resource("signedCounters", "iimage2D", 0, "r32i"),
            storage_image_resource(
                "unsignedAtlases",
                f"uimage2DArray[{STORAGE_IMAGE_ARRAY_SIZE}]",
                1,
                "r32ui",
            ),
        ]
    else:
        resources = [
            storage_image_resource("colorImage", "image2D", 0, "rgba32f"),
            storage_image_resource(
                "maskAtlases",
                f"uimage2DArray[{STORAGE_IMAGE_ARRAY_SIZE}]",
                1,
                "rgba32ui",
            ),
        ]

    reflection = base_reflection(manifest)
    reflection["resources"] = resources
    reflection["targetResourceBindings"] = [
        storage_image_target_binding(target, resource) for resource in resources
    ]
    reflection["functionConstants"] = [
        {
            "name": STORAGE_IMAGE_ARRAY_SIZE,
            "type": "int",
            "value": str(STORAGE_IMAGE_ARRAY_ELEMENT_COUNT),
        }
    ]
    reflection["targetFeatures"] = storage_image_target_features(target, atomic=atomic)
    write_json(package / "reflection.json", reflection)
    return reflection


def base_manual_kernel_summary():
    return {
        "totalCount": 0,
        "staticNormalizedCount": 0,
        "staticNonNormalizedCount": 0,
        "staticZeroSumCount": 0,
        "dynamicCount": 0,
    }


def base_hir_source_locations():
    locations = empty_hir_source_locations()
    locations["expressionCount"] = 1
    locations["expressionWithLocationCount"] = 1
    locations["expressions"] = [expression_source_location()]
    return locations


def empty_hir_source_locations():
    return {
        "expressionCount": 0,
        "expressionWithLocationCount": 0,
        "typeCount": 0,
        "typeWithLocationCount": 0,
        "statementCount": 0,
        "statementWithLocationCount": 0,
        "expressions": [],
        "types": [],
        "statements": [],
    }


def base_vulkan_native_profile(manifest):
    return {
        "schemaVersion": 1,
        "module": manifest["module"],
        "target": "vulkan",
        "api": "vulkan",
        "profile": {
            "name": "vulkan-prototype",
            "vulkanVersion": "1.2",
            "spirvVersion": "1.0",
        },
        "generator": "CrossGL Vulkan prototype backend",
        "artifacts": {
            "backendAssembly": manifest["artifacts"]["backendAssembly"],
            "nativeBinary": manifest["artifacts"]["nativeBinary"],
        },
        "debug": {
            "binaryFormat": "SPIR-V",
            "assemblyFormat": "SPIR-V assembly",
            "validationTargetEnv": "vulkan1.2",
            "disassembly": {
                "tool": "spirv-dis",
                "policy": "use-when-available",
                "status": "emitted",
                "path": VULKAN_DISASSEMBLY_PATH,
            },
        },
    }


def debug_target_capability_summary(target):
    capability_summary = {
        "target": target,
        "nativeImplemented": target in {"metal", "vulkan"},
        "sourcePackageSupported": target in {"directx", "opengl"},
        "packageBuildSupported": True,
        "packageMode": "source-package"
        if target in {"directx", "opengl"}
        else "native",
        "packageDecisionReason": (
            "source-package-available"
            if target in {"directx", "opengl"}
            else "native-package-available"
        ),
        "packageRankScore": 1 if target in {"directx", "opengl"} else 0,
        "requiredCapabilityCount": 0,
        "missingCapabilityCount": 0,
        "requiredCapabilities": [],
        "missingCapabilities": [],
        "requiredCapabilityGroups": [],
        "missingCapabilityGroups": [],
    }
    evidence_ids = expected_legalization_core_evidence_ids(capability_summary)
    capability_summary["legalizationCoreEvidenceIds"] = evidence_ids
    return capability_summary


def debug_target_fallback_record(summary, rank):
    return {
        "rank": rank,
        "target": summary["target"],
        "packageMode": summary["packageMode"],
        "rankReason": summary["packageDecisionReason"],
        "nativeImplemented": summary["nativeImplemented"],
        "sourcePackageSupported": summary["sourcePackageSupported"],
        "packageBuildSupported": summary["packageBuildSupported"],
        "missingCapabilityCount": summary["missingCapabilityCount"],
        "missingCapabilities": copy.deepcopy(summary["missingCapabilities"]),
        "legalizationCoreEvidenceIds": copy.deepcopy(
            summary["legalizationCoreEvidenceIds"]
        ),
        "missingCapabilityGroups": copy.deepcopy(summary["missingCapabilityGroups"]),
    }


def base_debug_metadata(target="directx"):
    capability_summaries = [
        debug_target_capability_summary(summary_target)
        for summary_target in DEBUG_TARGET_SUMMARY_TARGETS
    ]
    summaries_by_target = {
        summary["target"]: summary for summary in capability_summaries
    }
    selected_summary = summaries_by_target[target]
    viable_targets = [
        summary["target"]
        for summary in capability_summaries
        if summary["packageBuildSupported"]
    ]
    non_viable_targets = [
        summary["target"]
        for summary in capability_summaries
        if not summary["packageBuildSupported"]
    ]
    fallback_summaries = [
        summary
        for summary in capability_summaries
        if summary["packageBuildSupported"] and summary["target"] != target
    ]
    fallback_summaries.sort(key=lambda summary: summary["packageRankScore"])
    fallback_targets = [summary["target"] for summary in fallback_summaries]
    fallback_records = [
        debug_target_fallback_record(summary, index + 1)
        for index, summary in enumerate(fallback_summaries)
    ]
    return {
        "schemaVersion": 11,
        "targetDecision": {
            "requestedTarget": target,
            "selectedTarget": target,
            "selectionReason": "explicit-target",
            "selectedTargetNativeImplemented": selected_summary["nativeImplemented"],
            "selectedTargetSourcePackageSupported": (
                selected_summary["sourcePackageSupported"]
            ),
            "selectedTargetPackageBuildSupported": (
                selected_summary["packageBuildSupported"]
            ),
            "selectedTargetPackageMode": selected_summary["packageMode"],
            "selectedTargetMissingCapabilityCount": selected_summary[
                "missingCapabilityCount"
            ],
            "selectedTargetMissingCapabilities": copy.deepcopy(
                selected_summary["missingCapabilities"]
            ),
            "selectedTargetLegalizationCoreEvidenceIds": copy.deepcopy(
                selected_summary["legalizationCoreEvidenceIds"]
            ),
            "selectedTargetMissingCapabilityGroups": copy.deepcopy(
                selected_summary["missingCapabilityGroups"]
            ),
            "selectedTargetDiagnosticCount": 0,
            "diagnostics": [],
            "viableTargets": viable_targets,
            "fallbackTargets": fallback_targets,
            "fallbackTargetRecordCount": len(fallback_records),
            "fallbackTargetRecords": fallback_records,
            "nonViableTargets": non_viable_targets,
        },
        "targetCapabilities": {
            "defaultTarget": target,
            "summaries": capability_summaries,
        },
        "hirSourceLocations": base_hir_source_locations(),
        "manualTextureCompareKernelSummary": base_manual_kernel_summary(),
        "manualTextureCompareKernelBuckets": {
            "staticNormalized": [],
            "staticNonNormalized": [],
            "staticZeroSum": [],
            "dynamic": [],
        },
        "manualTextureCompareKernels": [],
    }


def target_explanation_record(target):
    native = target in {"metal", "vulkan"}
    source_package = target in {"directx", "opengl"}
    package_mode = "native" if native else "source-package"
    required_capabilities = []
    missing_capabilities = []
    if target == "metal":
        required_capabilities.append("metal.backend.native-metal-package")
    elif target == "vulkan":
        required_capabilities.append("vulkan.backend.vulkan-prototype-package")
    elif target == "directx":
        required_capabilities.extend(
            [
                "directx.backend.hlsl-lowering",
                "directx.backend.native-dxil-package",
                "directx.toolchain.dxc",
                "directx.validation.dxil-validator",
            ]
        )
        missing_capabilities.extend(required_capabilities[1:])
    elif target == "opengl":
        required_capabilities.extend(
            [
                "opengl.backend.glsl-lowering",
                "opengl.backend.native-glsl-package",
                "opengl.toolchain.opengl-driver",
                "opengl.validation.glsl-program-validation",
            ]
        )
        missing_capabilities.extend(required_capabilities[1:])

    record = {
        "target": target,
        "nativeImplemented": native,
        "sourcePackageSupported": source_package,
        "packageBuildSupported": True,
        "packageMode": package_mode,
        "packageDecisionReason": (
            "native-package-available" if native else "source-package-available"
        ),
        "packageRankScore": 0 if native else 1,
        "requiredCapabilityCount": len(required_capabilities),
        "missingCapabilityCount": len(missing_capabilities),
        "requiredCapabilities": required_capabilities,
        "missingCapabilities": missing_capabilities,
    }
    add_target_explanation_consumer_context(record)
    record["legalizationCoreEvidenceIds"] = expected_legalization_core_evidence_ids(
        record
    )
    return record


def target_explanation_target_record_properties():
    global _TARGET_EXPLANATION_TARGET_RECORD_PROPERTIES
    if _TARGET_EXPLANATION_TARGET_RECORD_PROPERTIES is not None:
        return _TARGET_EXPLANATION_TARGET_RECORD_PROPERTIES
    try:
        schema = json.loads(TARGET_EXPLANATION_SCHEMA_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        _TARGET_EXPLANATION_TARGET_RECORD_PROPERTIES = {}
        return _TARGET_EXPLANATION_TARGET_RECORD_PROPERTIES
    target_record = schema.get("$defs", {}).get("targetRecord", {})
    _TARGET_EXPLANATION_TARGET_RECORD_PROPERTIES = target_record.get("properties", {})
    if not isinstance(_TARGET_EXPLANATION_TARGET_RECORD_PROPERTIES, dict):
        _TARGET_EXPLANATION_TARGET_RECORD_PROPERTIES = {}
    return _TARGET_EXPLANATION_TARGET_RECORD_PROPERTIES


def add_target_explanation_consumer_context(record):
    properties = target_explanation_target_record_properties()
    if "targetBackend" in properties:
        record["targetBackend"] = record["target"]
    if "decisionReasonCodes" in properties:
        record["decisionReasonCodes"] = target_explanation_decision_reason_codes(record)
    if "artifactLinks" in properties:
        record["artifactLinks"] = target_explanation_artifact_links(record)
    if "reportLinks" in properties:
        record["reportLinks"] = target_explanation_report_links(record)
    if "remediation" in properties:
        record["remediation"] = target_explanation_remediation(record)


def target_explanation_decision_reason_codes(record):
    codes = [
        f"package-mode:{record['packageMode']}",
        f"package-reason:{record['packageDecisionReason']}",
    ]
    if record["missingCapabilities"]:
        codes.append("optional-native-tool:missing")
    if not record["packageBuildSupported"]:
        codes.append("target:unsupported")
    return codes


def target_explanation_artifact_links(record):
    return [f"ir/target-explanation.json#targets/{record['target']}"]


def target_explanation_report_links(record):
    return [f"target-explanation-v1#targets/{record['target']}"]


def target_explanation_remediation(record):
    if record["missingCapabilities"]:
        missing = ", ".join(sorted(record["missingCapabilities"]))
        return (
            f"native artifact remediation: {record['target']} source-package "
            "fallback is available, but native artifact verification requires "
            f"missing capabilities: {missing}"
        )
    return "No remediation required; package build evidence is available."


def base_target_explanation(target="directx"):
    targets = [
        target_explanation_record(name)
        for name in ("metal", "vulkan", "directx", "opengl")
    ]
    recommended = targets[0]
    for record in targets[1:]:
        if record["packageRankScore"] < recommended["packageRankScore"] or (
            record["packageRankScore"] == recommended["packageRankScore"]
            and record["target"] == target
            and recommended["target"] != target
        ):
            recommended = record
    return {
        "schemaVersion": 1,
        "module": MODULE_NAME,
        "defaultTarget": target,
        "buildableTargetCount": len(targets),
        "recommendedTarget": recommended["target"],
        "recommendedPackageMode": recommended["packageMode"],
        "targets": targets,
    }


def base_hir_source_map():
    return {
        "schemaVersion": 7,
        "filters": {
            "activeCount": 0,
        },
        "pagination": {
            "activeCount": 0,
            "expressionOffset": 0,
            "typeOffset": 0,
            "statementOffset": 0,
            "expressionTotalCount": 1,
            "expressionEmittedCount": 1,
            "expressionHasMore": False,
            "expressionNextOffset": 1,
            "typeTotalCount": 0,
            "typeEmittedCount": 0,
            "typeHasMore": False,
            "typeNextOffset": 0,
            "statementTotalCount": 0,
            "statementEmittedCount": 0,
            "statementHasMore": False,
            "statementNextOffset": 0,
        },
        "categoryCounts": {
            "expressionTotalCount": 1,
            "typeTotalCount": 0,
            "statementTotalCount": 0,
            "recordTotalCount": 1,
            "expressionKinds": [
                {
                    "name": "literal",
                    "count": 1,
                },
            ],
            "statementKinds": [],
            "typeOwnerKinds": [],
        },
        "records": {
            "enabled": False,
            "activeCount": 0,
            "offset": 0,
            "totalCount": 1,
            "emittedCount": 0,
            "hasMore": False,
            "nextOffset": 0,
            "items": [],
        },
        "hirSourceLocations": base_hir_source_locations(),
    }


def source_location(offset, length=3):
    return {
        "file": "fixture.cgl",
        "line": 1,
        "column": offset + 1,
        "offset": offset,
        "length": length,
        "endLine": 1,
        "endColumn": offset + length + 1,
        "endOffset": offset + length,
    }


def expression_source_location():
    return {
        "index": 0,
        "stage": "compute",
        "entryPoint": "compute_main",
        "function": "main",
        "statementKind": "decl",
        "kind": "literal",
        "value": "1.0",
        "type": "float",
        "location": source_location(0),
    }


def type_source_location():
    return {
        "index": 0,
        "stage": "compute",
        "entryPoint": "compute_main",
        "function": "main",
        "ownerKind": "resource-type",
        "ownerName": "values",
        "type": "StructuredBuffer<float>",
        "location": source_location(4, 6),
    }


def statement_source_location():
    return {
        "index": 0,
        "stage": "compute",
        "entryPoint": "compute_main",
        "function": "main",
        "statementKind": "decl",
        "name": "value",
        "location": source_location(11, 5),
    }


def hir_source_map_with_expression():
    document = base_hir_source_map()
    expression = expression_source_location()
    document["pagination"]["expressionTotalCount"] = 1
    document["pagination"]["expressionEmittedCount"] = 1
    document["pagination"]["expressionNextOffset"] = 1
    document["categoryCounts"]["expressionTotalCount"] = 1
    document["categoryCounts"]["recordTotalCount"] = 1
    document["categoryCounts"]["expressionKinds"] = [
        {
            "name": "literal",
            "count": 1,
        },
    ]
    document["hirSourceLocations"]["expressionCount"] = 1
    document["hirSourceLocations"]["expressionWithLocationCount"] = 1
    document["hirSourceLocations"]["expressions"] = [expression]
    return document


def hir_source_map_with_all_record_kinds():
    document = hir_source_map_with_expression()
    source_type = type_source_location()
    statement = statement_source_location()

    document["pagination"]["typeTotalCount"] = 1
    document["pagination"]["typeEmittedCount"] = 1
    document["pagination"]["typeNextOffset"] = 1
    document["pagination"]["statementTotalCount"] = 1
    document["pagination"]["statementEmittedCount"] = 1
    document["pagination"]["statementNextOffset"] = 1
    document["categoryCounts"]["typeTotalCount"] = 1
    document["categoryCounts"]["statementTotalCount"] = 1
    document["categoryCounts"]["recordTotalCount"] = 3
    document["categoryCounts"]["typeOwnerKinds"] = [
        {
            "name": "resource-type",
            "count": 1,
        },
    ]
    document["categoryCounts"]["statementKinds"] = [
        {
            "name": "decl",
            "count": 1,
        },
    ]
    document["records"]["totalCount"] = 3
    document["hirSourceLocations"]["typeCount"] = 1
    document["hirSourceLocations"]["typeWithLocationCount"] = 1
    document["hirSourceLocations"]["statementCount"] = 1
    document["hirSourceLocations"]["statementWithLocationCount"] = 1
    document["hirSourceLocations"]["types"] = [source_type]
    document["hirSourceLocations"]["statements"] = [statement]
    return document


def rewrite_debug_metadata_locations(package, manifest, source_map):
    debug_metadata = base_debug_metadata(manifest["target"])
    debug_metadata["hirSourceLocations"] = copy.deepcopy(
        source_map["hirSourceLocations"]
    )
    write_json(
        package_path(package, manifest["artifacts"]["debugMetadata"]),
        debug_metadata,
    )


def should_emit_artifact(manifest, artifact_name):
    if artifact_name == "nativeBinaryStatus":
        return False
    artifacts = manifest["artifacts"]
    if (
        artifact_name == "nativeBinary"
        and manifest["target"] in SOURCE_PACKAGE_TARGETS
        and artifacts.get("nativeBinaryStatus") == "planned"
    ):
        return False
    return True


def make_package(tmp_dir, name, status="planned", target="directx"):
    package = tmp_dir / f"{name}.cglb"
    source = make_source(tmp_dir)
    manifest = base_manifest(package, source, target=target, status=status)

    write_json(package / "reflection.json", base_reflection(manifest))
    write_json(package / "diagnostics.json", {"schemaVersion": 1, "diagnostics": []})
    for artifact_name, artifact_value in manifest["artifacts"].items():
        if not should_emit_artifact(manifest, artifact_name):
            continue
        artifact_path = package_path(package, artifact_value)
        if artifact_name == "debugMetadata":
            write_json(artifact_path, base_debug_metadata(manifest["target"]))
        elif artifact_name == "hirSourceMap":
            write_json(artifact_path, base_hir_source_map())
        elif artifact_name == "targetExplanation":
            write_json(artifact_path, base_target_explanation(manifest["target"]))
        elif artifact_name == "nativeProfile":
            write_json(artifact_path, base_vulkan_native_profile(manifest))
        else:
            write_text(artifact_path, f"{artifact_name} fixture\n")
    if target == "vulkan":
        write_text(
            package_path(package, VULKAN_DISASSEMBLY_PATH),
            "disassembly fixture\n",
        )
    write_json(package / "manifest.json", manifest)
    return package, source, manifest


def run_validator(root, package, source, schema_root=True, package_verifier=None):
    validator = root / "tools" / "validate_package_integrity.py"
    schema_validator = root / "tools" / "validate_json_schema.py"
    command = [
        sys.executable,
        str(validator),
        "--package",
        str(package),
        "--source",
        str(source),
    ]
    if package_verifier is not None:
        command.extend(["--package-verifier", str(package_verifier)])
    if schema_root:
        command.extend(
            [
                "--schema-root",
                str(root / "docs" / "schemas"),
                "--json-schema-validator",
                str(schema_validator),
            ]
        )
    return subprocess.run(
        command,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )


def expect_success(root, package, source):
    result = run_validator(root, package, source)
    if result.returncode != 0:
        return [
            f"{package.name}: expected success, got "
            f"{result.stderr}{result.stdout}".strip()
        ]
    return []


def expect_base_target_explanation_schema_success(root, tmp_dir, target):
    instance_path = tmp_dir / f"base-target-explanation-{target}.json"
    write_json(instance_path, base_target_explanation(target))
    result = subprocess.run(
        [
            sys.executable,
            str(root / "tools" / "validate_json_schema.py"),
            "--schema",
            str(root / "docs" / "schemas" / "target-explanation-v1.schema.json"),
            "--instance",
            str(instance_path),
        ],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if result.returncode != 0:
        return [
            f"{instance_path.name}: expected base target explanation schema "
            f"success, got {result.stderr}{result.stdout}".strip()
        ]
    return []


def expect_failure(root, package, source, expected, schema_root=True):
    result = run_validator(root, package, source, schema_root=schema_root)
    output = result.stderr + result.stdout
    errors = []
    if result.returncode == 0:
        errors.append(f"{package.name}: expected validation failure")
    if expected not in output:
        errors.append(
            f"{package.name}: expected error substring {expected!r}; "
            f"got {output.strip()!r}"
        )
    return errors


def expect_native_failure(root, package, source, package_verifier, expected):
    result = run_validator(
        root,
        package,
        source,
        schema_root=False,
        package_verifier=package_verifier,
    )
    output = result.stderr + result.stdout
    errors = []
    if result.returncode == 0:
        errors.append(f"{package.name}: expected native validation failure")
    if expected not in output:
        errors.append(
            f"{package.name}: expected native error substring {expected!r}; "
            f"got {output.strip()!r}"
        )
    return errors


def rewrite_manifest(package, manifest):
    write_json(package / "manifest.json", manifest)


def duplicate_manifest_artifact(package, manifest, artifact_name):
    artifact_value = manifest["artifacts"][artifact_name]
    manifest_text = json.dumps(manifest, indent=2) + "\n"
    artifact_line = f'    "{artifact_name}": {json.dumps(artifact_value)},\n'
    duplicated = manifest_text.replace(artifact_line, artifact_line + artifact_line, 1)
    if duplicated == manifest_text:
        raise AssertionError(f"failed to duplicate manifest artifact {artifact_name!r}")
    write_text(package / "manifest.json", duplicated)


def delete_artifact_path(package, manifest, artifact_name):
    artifact_value = manifest["artifacts"].get(artifact_name)
    if isinstance(artifact_value, str):
        path = package_path(package, artifact_value)
        if path.exists() and path.is_file():
            path.unlink()


def run_native_delegation_cases(root, cglc, tmp_dir):
    errors = []

    package, source, _manifest = make_package(tmp_dir, "native-delegated-valid")
    result = run_validator(
        root,
        package,
        source,
        schema_root=False,
        package_verifier=cglc,
    )
    if result.returncode != 0:
        errors.append(
            f"{package.name}: expected native delegated success, got "
            f"{result.stderr}{result.stdout}".strip()
        )

    package, source, manifest = make_package(tmp_dir, "native-delegated-missing")
    package_path(package, manifest["artifacts"]["backendSource"]).unlink()
    errors.extend(
        expect_native_failure(
            root,
            package,
            source,
            cglc,
            "package artifact 'backendSource' does not exist",
        )
    )

    package, source, manifest = make_package(
        tmp_dir, "native-delegated-directory-artifact"
    )
    backend_source_path = package_path(package, manifest["artifacts"]["backendSource"])
    backend_source_path.unlink()
    backend_source_path.mkdir()
    errors.extend(
        expect_native_failure(
            root,
            package,
            source,
            cglc,
            "package artifact 'backendSource' is not a file",
        )
    )

    package, source, manifest = make_package(
        tmp_dir, "native-delegated-backslash-artifact"
    )
    backslash_manifest = copy.deepcopy(manifest)
    backslash_manifest["artifacts"]["backendSource"] = (
        "backend\\directx\\StorageBufferComputeShader.hlsl"
    )
    rewrite_manifest(package, backslash_manifest)
    errors.extend(
        expect_native_failure(
            root,
            package,
            source,
            cglc,
            "artifact paths must use '/' separators",
        )
    )

    package, source, manifest = make_package(
        tmp_dir, "native-delegated-reflection-backslash"
    )
    reflection_backslash = base_reflection(manifest)
    reflection_backslash["nativeBinary"] = (
        "backend\\directx\\StorageBufferComputeShader.dxil"
    )
    write_json(package / "reflection.json", reflection_backslash)
    errors.extend(
        expect_native_failure(
            root,
            package,
            source,
            cglc,
            "reflection nativeBinary path must use '/' separators",
        )
    )

    package, source, manifest = make_package(
        tmp_dir, "native-delegated-reflection-parent"
    )
    reflection_parent = base_reflection(manifest)
    reflection_parent["nativeBinary"] = "../StorageBufferComputeShader.dxil"
    write_json(package / "reflection.json", reflection_parent)
    errors.extend(
        expect_native_failure(
            root,
            package,
            source,
            cglc,
            "reflection nativeBinary path must stay inside package",
        )
    )

    package, source, manifest = make_package(
        tmp_dir, "native-delegated-reflection-absolute"
    )
    reflection_absolute = base_reflection(manifest)
    reflection_absolute["nativeBinary"] = (
        package_path(package, manifest["artifacts"]["nativeBinary"])
        .resolve(strict=False)
        .as_posix()
    )
    write_json(package / "reflection.json", reflection_absolute)
    errors.extend(
        expect_native_failure(
            root,
            package,
            source,
            cglc,
            "reflection nativeBinary path must be package-relative",
        )
    )

    package, source, manifest = make_package(
        tmp_dir, "native-delegated-artifact-contract-drift"
    )
    artifact_contract_drift = manifest_with_required_path_artifacts(
        manifest, ["backendSource"]
    )
    rewrite_manifest(package, artifact_contract_drift)
    errors.extend(
        expect_native_failure(
            root,
            package,
            source,
            cglc,
            "packageArtifactRequirements.requiredPathArtifacts must match "
            "manifest target contract",
        )
    )

    artifact_contract_drift_cases = (
        (
            "native-delegated-artifact-contract-reordered",
            ["nativeBinary", "backendSource"],
        ),
        (
            "native-delegated-artifact-contract-extra",
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
            expect_native_failure(
                root,
                package,
                source,
                cglc,
                "packageArtifactRequirements.requiredPathArtifacts must match "
                "manifest target contract",
            )
        )

    evidence_drift_cases = []
    for case_name, mutate in (
        (
            "native-delegated-requirement-evidence-missing-id",
            lambda evidence_ids: evidence_ids[:-1],
        ),
        (
            "native-delegated-requirement-evidence-extra-id",
            lambda evidence_ids: (
                evidence_ids
                + ["target-legalization.v1.directx.package-artifact.fixture.extra"]
            ),
        ),
    ):
        package, source, manifest = make_package(tmp_dir, case_name)
        expected_evidence_ids = package_artifact_requirement_evidence_ids(
            manifest["packageArtifactRequirements"]
        )
        evidence_drift = manifest_with_requirement_evidence_ids(
            manifest,
            mutate(expected_evidence_ids),
        )
        rewrite_manifest(package, evidence_drift)
        evidence_drift_cases.append((package, source))

    for package, source in evidence_drift_cases:
        errors.extend(
            expect_native_failure(
                root,
                package,
                source,
                cglc,
                "package manifest packageArtifactRequirements.evidenceIds must "
                "match recorded packageArtifactRequirements",
            )
        )

    package, source, manifest = make_package(
        tmp_dir, "native-delegated-planned-status-produced-native"
    )
    write_json(
        package_path(package, manifest["artifacts"]["nativeBinary"]),
        {"fixture": "planned native binary should not be produced"},
    )
    errors.extend(
        expect_native_failure(
            root,
            package,
            source,
            cglc,
            "nativeBinaryStatus planned requires the nativeBinary artifact path "
            "to be declared but not produced",
        )
    )

    package, source, _manifest = make_package(
        tmp_dir, "native-delegated-directory-root-file"
    )
    (package / "diagnostics.json").unlink()
    (package / "diagnostics.json").mkdir()
    errors.extend(
        expect_native_failure(
            root,
            package,
            source,
            cglc,
            "package diagnostics is not a regular file",
        )
    )

    package, source, manifest = make_package(tmp_dir, "native-delegated-bad-hash")
    bad_hash_manifest = copy.deepcopy(manifest)
    bad_hash_manifest["sourceHash"]["value"] = "0" * 64
    rewrite_manifest(package, bad_hash_manifest)
    errors.extend(
        expect_native_failure(
            root,
            package,
            source,
            cglc,
            "package.verify.source-hash-mismatch",
        )
    )

    package, source, manifest = make_package(
        tmp_dir, "native-delegated-bad-hash-format"
    )
    bad_hash_format_manifest = copy.deepcopy(manifest)
    bad_hash_format_manifest["sourceHash"]["value"] = "A" * 64
    rewrite_manifest(package, bad_hash_format_manifest)
    errors.extend(
        expect_native_failure(
            root,
            package,
            source,
            cglc,
            "package.verify.invalid-source-hash",
        )
    )

    return errors


def run_cases(root, cglc=None):
    errors = []
    with tempfile.TemporaryDirectory() as tmp:
        tmp_dir = Path(tmp)

        errors.extend(
            expect_base_target_explanation_schema_success(root, tmp_dir, "directx")
        )

        package, source, _manifest = make_package(tmp_dir, "valid-planned")
        errors.extend(expect_success(root, package, source))

        package, source, _manifest = make_package(
            tmp_dir, "valid-emitted", status="emitted"
        )
        add_native_artifact_descriptor(package, _manifest)
        errors.extend(expect_success(root, package, source))

        package, source, manifest = make_package(
            tmp_dir,
            "invalid-native-status-source-package",
            status="emitted",
        )
        invalid_native_status = copy.deepcopy(manifest)
        invalid_native_status["artifacts"]["nativeBinaryStatus"] = "cached"
        rewrite_manifest(package, invalid_native_status)
        errors.extend(
            expect_failure(
                root,
                package,
                source,
                "$.artifacts.nativeBinaryStatus: expected one of "
                "'planned', 'emitted', 'validated'",
                schema_root=False,
            )
        )

        valid_target_cases = []
        for target in ("metal", "vulkan", "opengl"):
            package, source, manifest = make_package(
                tmp_dir,
                f"valid-{target}",
                target=target,
            )
            if target in {"metal", "vulkan"}:
                add_native_artifact_descriptor(
                    package, manifest, mutate=mark_native_artifact_validated
                )
            valid_target_cases.append((package, source))

        def check_valid_target_case(case):
            package, source = case
            return expect_success(root, package, source)

        extend_errors_from_fixture_tasks(
            errors,
            valid_target_cases,
            check_valid_target_case,
        )

        unexpected_native_status_cases = []
        for target in ("metal", "vulkan"):
            case_name = f"unexpected-native-status-{target}"
            package, source, manifest = make_package(
                tmp_dir,
                case_name,
                target=target,
            )
            unexpected_native_status = copy.deepcopy(manifest)
            unexpected_native_status["artifacts"]["nativeBinaryStatus"] = "emitted"
            rewrite_manifest(package, unexpected_native_status)
            unexpected_native_status_cases.append((target, package, source))

        def check_unexpected_native_status_case(case):
            target, package, source = case
            return expect_failure(
                root,
                package,
                source,
                f"$.artifacts.nativeBinaryStatus: "
                f"{target} packages must not declare nativeBinaryStatus",
                schema_root=False,
            )

        extend_errors_from_fixture_tasks(
            errors,
            unexpected_native_status_cases,
            check_unexpected_native_status_case,
        )

        package, source, manifest = make_package(tmp_dir, "duplicate-artifact-key")
        duplicate_manifest_artifact(package, manifest, "backendSource")
        errors.extend(
            expect_failure(
                root,
                package,
                source,
                "manifest.json: duplicate JSON object key $.artifacts.backendSource",
                schema_root=False,
            )
        )

        missing_required_artifact_cases = []
        for target, required_artifacts in TARGET_REQUIRED_ARTIFACTS.items():
            for artifact_name in required_artifacts:
                case_name = f"missing-required-{target}-{artifact_name}"
                package, source, manifest = make_package(
                    tmp_dir,
                    case_name,
                    target=target,
                )
                missing_required_manifest = copy.deepcopy(manifest)
                del missing_required_manifest["artifacts"][artifact_name]
                delete_artifact_path(package, manifest, artifact_name)
                rewrite_manifest(package, missing_required_manifest)
                missing_required_artifact_cases.append(
                    (target, artifact_name, package, source)
                )

        def check_missing_required_artifact_case(case):
            target, artifact_name, package, source = case
            return expect_failure(
                root,
                package,
                source,
                f"$.artifacts.{artifact_name}: {target} packages require "
                f"{artifact_name}",
                schema_root=False,
            )

        extend_errors_from_fixture_tasks(
            errors,
            missing_required_artifact_cases,
            check_missing_required_artifact_case,
        )

        package, source, manifest = make_package(
            tmp_dir,
            "status-without-native-artifact",
        )
        status_without_native = copy.deepcopy(manifest)
        del status_without_native["artifacts"]["nativeBinary"]
        rewrite_manifest(package, status_without_native)
        errors.extend(
            expect_failure(
                root,
                package,
                source,
                "$.artifacts.nativeBinary: nativeBinaryStatus requires nativeBinary",
                schema_root=False,
            )
        )

        package, source, manifest = make_package(tmp_dir, "missing-source")
        package_path(package, manifest["artifacts"]["backendSource"]).unlink()
        errors.extend(
            expect_failure(
                root,
                package,
                source,
                "$.artifacts.backendSource: artifact does not exist",
            )
        )

        package, source, manifest = make_package(
            tmp_dir, "missing-native", status="emitted"
        )
        package_path(package, manifest["artifacts"]["nativeBinary"]).unlink()
        errors.extend(
            expect_failure(
                root,
                package,
                source,
                "$.artifacts.nativeBinary: artifact does not exist",
            )
        )

        package, source, manifest = make_package(tmp_dir, "escaping-artifact")
        escaping_manifest = copy.deepcopy(manifest)
        outside = tmp_dir / "outside.hlsl"
        write_text(outside, "// outside\n")
        escaping_manifest["artifacts"]["backendSource"] = "../outside.hlsl"
        rewrite_manifest(package, escaping_manifest)
        errors.extend(
            expect_failure(
                root,
                package,
                source,
                "$.artifacts.backendSource: artifact path escapes package",
            )
        )

        package, source, manifest = make_package(tmp_dir, "absolute-artifact")
        absolute_manifest = copy.deepcopy(manifest)
        absolute_manifest["artifacts"]["backendSource"] = (
            package_path(package, manifest["artifacts"]["backendSource"])
            .resolve(strict=False)
            .as_posix()
        )
        rewrite_manifest(package, absolute_manifest)
        errors.extend(
            expect_failure(
                root,
                package,
                source,
                "$.artifacts.backendSource: artifact path must be package-relative",
            )
        )

        package, source, manifest = make_package(tmp_dir, "reflection-mismatch")
        reflection_mismatch = base_reflection(manifest)
        reflection_mismatch["nativeBinary"] = "backend/directx/OtherShader.dxil"
        write_json(package / "reflection.json", reflection_mismatch)
        errors.extend(
            expect_failure(
                root,
                package,
                source,
                "$.nativeBinary: expected manifest artifacts.nativeBinary",
            )
        )

        package, source, manifest = make_package(
            tmp_dir, "reflection-target-feature-mismatch"
        )
        reflection_target_mismatch = base_reflection(manifest)
        reflection_target_mismatch["target"] = "opengl"
        reflection_target_mismatch["targetFeatures"] = [
            {
                "target": manifest["target"],
                "kind": "operation",
                "name": "fixture-target-mismatch",
            }
        ]
        write_json(package / "reflection.json", reflection_target_mismatch)
        errors.extend(
            expect_failure(
                root,
                package,
                source,
                "reflection.json: schema validation failed",
            )
        )

        package, source, manifest = make_package(tmp_dir, "absolute-reflection")
        absolute_reflection = base_reflection(manifest)
        absolute_reflection["nativeBinary"] = (
            package_path(package, manifest["artifacts"]["nativeBinary"])
            .resolve(strict=False)
            .as_posix()
        )
        write_json(package / "reflection.json", absolute_reflection)
        errors.extend(
            expect_failure(
                root,
                package,
                source,
                "$.nativeBinary: native binary path must be package-relative",
            )
        )

        package, source, _manifest = make_package(tmp_dir, "bad-reflection-schema")
        write_json(package / "reflection.json", {"schemaVersion": 1})
        errors.extend(
            expect_failure(
                root,
                package,
                source,
                "reflection.json: schema validation failed",
            )
        )

        package, source, _manifest = make_package(tmp_dir, "bad-diagnostics-schema")
        write_json(package / "diagnostics.json", {"schemaVersion": 1})
        errors.extend(
            expect_failure(
                root,
                package,
                source,
                "diagnostics.json: schema validation failed",
            )
        )

        package, source, manifest = make_package(tmp_dir, "bad-debug-schema")
        write_json(
            package_path(package, manifest["artifacts"]["debugMetadata"]),
            {"schemaVersion": 11},
        )
        errors.extend(
            expect_failure(
                root,
                package,
                source,
                "ir/debug-metadata.json: schema validation failed",
            )
        )

        package, source, manifest = make_package(tmp_dir, "bad-hir-source-map-schema")
        write_json(
            package_path(package, manifest["artifacts"]["hirSourceMap"]),
            {"schemaVersion": 7},
        )
        errors.extend(
            expect_failure(
                root,
                package,
                source,
                "ir/hir-source-map.json: schema validation failed",
            )
        )

        package, source, manifest = make_package(tmp_dir, "swapped-debug-artifacts")
        swapped_debug_manifest = copy.deepcopy(manifest)
        swapped_debug_manifest["artifacts"]["debugMetadata"] = manifest["artifacts"][
            "hirSourceMap"
        ]
        swapped_debug_manifest["artifacts"]["hirSourceMap"] = manifest["artifacts"][
            "debugMetadata"
        ]
        rewrite_manifest(package, swapped_debug_manifest)
        errors.extend(
            expect_failure(
                root,
                package,
                source,
                "ir/hir-source-map.json: schema validation failed",
            )
        )

        package, source, manifest = make_package(
            tmp_dir, "filtered-hir-source-map-artifact"
        )
        filtered_source_map = base_hir_source_map()
        filtered_source_map["filters"] = {
            "activeCount": 1,
            "expressionKind": "literal",
        }
        write_json(
            package_path(package, manifest["artifacts"]["hirSourceMap"]),
            filtered_source_map,
        )
        errors.extend(
            expect_failure(
                root,
                package,
                source,
                "ir/hir-source-map.json: package source map must be unfiltered",
            )
        )

        package, source, manifest = make_package(
            tmp_dir, "paged-hir-source-map-artifact"
        )
        paged_source_map = base_hir_source_map()
        paged_source_map["pagination"]["activeCount"] = 1
        paged_source_map["pagination"]["expressionLimit"] = 0
        write_json(
            package_path(package, manifest["artifacts"]["hirSourceMap"]),
            paged_source_map,
        )
        errors.extend(
            expect_failure(
                root,
                package,
                source,
                "ir/hir-source-map.json: package source map pagination must be inactive",
            )
        )

        package, source, manifest = make_package(
            tmp_dir, "combined-records-hir-source-map-artifact"
        )
        recorded_source_map = base_hir_source_map()
        recorded_source_map["records"]["enabled"] = True
        recorded_source_map["records"]["limit"] = 0
        write_json(
            package_path(package, manifest["artifacts"]["hirSourceMap"]),
            recorded_source_map,
        )
        errors.extend(
            expect_failure(
                root,
                package,
                source,
                "ir/hir-source-map.json: package source map records must be disabled",
            )
        )

        package, source, manifest = make_package(
            tmp_dir, "category-total-hir-source-map-artifact"
        )
        category_total_source_map = hir_source_map_with_all_record_kinds()
        rewrite_debug_metadata_locations(package, manifest, category_total_source_map)
        category_total_source_map["categoryCounts"]["recordTotalCount"] = 2
        write_json(
            package_path(package, manifest["artifacts"]["hirSourceMap"]),
            category_total_source_map,
        )
        errors.extend(
            expect_failure(
                root,
                package,
                source,
                "ir/hir-source-map.json: expected "
                "categoryCounts.recordTotalCount to match complete package source map",
                schema_root=False,
            )
        )

        package, source, manifest = make_package(
            tmp_dir, "category-expression-kind-hir-source-map-artifact"
        )
        expression_kind_source_map = hir_source_map_with_all_record_kinds()
        rewrite_debug_metadata_locations(package, manifest, expression_kind_source_map)
        expression_kind_source_map["categoryCounts"]["expressionKinds"] = [
            {
                "name": "binary",
                "count": 1,
            },
        ]
        write_json(
            package_path(package, manifest["artifacts"]["hirSourceMap"]),
            expression_kind_source_map,
        )
        errors.extend(
            expect_failure(
                root,
                package,
                source,
                "ir/hir-source-map.json: expected "
                "categoryCounts.expressionKinds to match package source map records",
                schema_root=False,
            )
        )

        package, source, manifest = make_package(
            tmp_dir, "category-statement-kind-hir-source-map-artifact"
        )
        statement_kind_source_map = hir_source_map_with_all_record_kinds()
        rewrite_debug_metadata_locations(package, manifest, statement_kind_source_map)
        statement_kind_source_map["categoryCounts"]["statementKinds"] = []
        write_json(
            package_path(package, manifest["artifacts"]["hirSourceMap"]),
            statement_kind_source_map,
        )
        errors.extend(
            expect_failure(
                root,
                package,
                source,
                "ir/hir-source-map.json: expected "
                "categoryCounts.statementKinds to match package source map records",
                schema_root=False,
            )
        )

        package, source, manifest = make_package(
            tmp_dir, "category-type-owner-hir-source-map-artifact"
        )
        type_owner_source_map = hir_source_map_with_all_record_kinds()
        rewrite_debug_metadata_locations(package, manifest, type_owner_source_map)
        type_owner_source_map["categoryCounts"]["typeOwnerKinds"] = []
        write_json(
            package_path(package, manifest["artifacts"]["hirSourceMap"]),
            type_owner_source_map,
        )
        errors.extend(
            expect_failure(
                root,
                package,
                source,
                "ir/hir-source-map.json: expected "
                "categoryCounts.typeOwnerKinds to match package source map records",
                schema_root=False,
            )
        )

        package, source, manifest = make_package(
            tmp_dir, "record-total-hir-source-map-artifact"
        )
        record_total_source_map = hir_source_map_with_all_record_kinds()
        rewrite_debug_metadata_locations(package, manifest, record_total_source_map)
        record_total_source_map["records"]["totalCount"] = 2
        write_json(
            package_path(package, manifest["artifacts"]["hirSourceMap"]),
            record_total_source_map,
        )
        errors.extend(
            expect_failure(
                root,
                package,
                source,
                "ir/hir-source-map.json: expected records.totalCount to match "
                "categoryCounts.recordTotalCount",
                schema_root=False,
            )
        )

        package, source, manifest = make_package(
            tmp_dir, "mismatched-debug-source-locations"
        )
        write_json(
            package_path(package, manifest["artifacts"]["hirSourceMap"]),
            hir_source_map_with_all_record_kinds(),
        )
        errors.extend(
            expect_failure(
                root,
                package,
                source,
                "ir/hir-source-map.json: hirSourceLocations must match "
                "ir/debug-metadata.json",
            )
        )

        package, source, manifest = make_package(
            tmp_dir, "debug-metadata-without-hir-source-map"
        )
        missing_hir_manifest = copy.deepcopy(manifest)
        del missing_hir_manifest["artifacts"]["hirSourceMap"]
        rewrite_manifest(package, missing_hir_manifest)
        errors.extend(
            expect_failure(
                root,
                package,
                source,
                "$.artifacts: debugMetadata and hirSourceMap must be emitted together",
                schema_root=False,
            )
        )

        package, source, manifest = make_package(
            tmp_dir, "hir-source-map-without-debug-metadata"
        )
        missing_debug_manifest = copy.deepcopy(manifest)
        del missing_debug_manifest["artifacts"]["debugMetadata"]
        rewrite_manifest(package, missing_debug_manifest)
        errors.extend(
            expect_failure(
                root,
                package,
                source,
                "$.artifacts: debugMetadata and hirSourceMap must be emitted together",
                schema_root=False,
            )
        )

        package, source, manifest = make_package(tmp_dir, "bad-source-hash")
        bad_hash_manifest = copy.deepcopy(manifest)
        bad_hash_manifest["sourceHash"]["value"] = "0" * 64
        rewrite_manifest(package, bad_hash_manifest)
        errors.extend(
            expect_failure(
                root,
                package,
                source,
                "$.sourceHash.value: expected source hash",
            )
        )

        package, source, _manifest = make_package(
            tmp_dir, "source-mutated-after-manifest"
        )
        write_text(source, source.read_text(encoding="utf-8") + "// tampered\n")
        errors.extend(
            expect_failure(
                root,
                package,
                source,
                "$.sourceHash.value: expected source hash",
            )
        )

        if cglc is not None:
            errors.extend(run_native_delegation_cases(root, cglc, tmp_dir))

    return errors


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--root",
        default=".",
        help="CrossGL-Compiler repository root",
    )
    parser.add_argument("--cglc", type=Path, help="Path to cglc executable")
    args = parser.parse_args()

    errors = run_cases(Path(args.root).resolve(), args.cglc)
    if errors:
        for error in errors:
            print(f"package integrity fixture check failed: {error}", file=sys.stderr)
        return 1

    print("validated package integrity fixtures")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
