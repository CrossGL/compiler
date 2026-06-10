#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
from typing import Any
import unittest
from unittest.mock import patch
import zipfile


REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURE_ROOT = REPO_ROOT / "runtime" / "examples" / "fixtures"
sys.path.insert(0, str(REPO_ROOT))


from runtime.examples.source_free_loader import (  # noqa: E402
    inspect_source_free_package,
)

LEGACY_REQUIREMENTS_FALLBACK_CODE = "package.artifact_requirements.legacy_v0_fallback"
LEGACY_REQUIREMENTS_FALLBACK_DIAGNOSTIC = {
    "severity": "note",
    "code": LEGACY_REQUIREMENTS_FALLBACK_CODE,
    "message": (
        "manifest.packageArtifactRequirements is missing; using generated legacy "
        "v0 target contract as report-only compatibility metadata"
    ),
    "document": "manifest",
    "path": "packageArtifactRequirements",
    "expected": "recorded package artifact requirements",
    "actual": "legacy-v0-target-contract",
}


class SourceFreeRuntimeLoaderExampleTests(unittest.TestCase):
    def test_example_selects_native_metal_artifact_from_metadata(self) -> None:
        package_dir = FIXTURE_ROOT / "source-free-metal-native.cglb"

        summary = inspect_source_free_package(package_dir, "metal")

        self.assertTrue(summary["loadable"], summary["diagnostics"])
        self.assertEqual(summary["status"], "compatible")
        self.assertFalse(summary["sourceParsingRequired"])
        self.assertTrue(summary["metadataOnly"])
        self.assertEqual(summary["sourceInputs"], [])
        self.assertEqual(
            [source["name"] for source in summary["metadataInputs"]],
            ["manifest", "reflection", "diagnostics"],
        )
        self.assertEqual(summary["deviceExecution"], "not-executed")
        self.assertFalse(summary["deviceExecutionRequired"])
        self.assertNotIn("nativeBackendAdmission", summary)
        self.assertEqual(summary["module"], "SourceFreeMetalRuntimeExample")
        self.assertEqual(summary["availableTargets"], ["metal"])
        self.assertEqual(
            summary["packageArtifactRequirementsSource"],
            "legacy-v0-target-contract",
        )
        self.assertTrue(summary["packageArtifactRequirements"]["legacyInferred"])
        self.assertTrue(summary["packageArtifactRequirements"]["reportOnly"])
        self.assertEqual(summary["selectedArtifact"]["name"], "nativeBinary")
        self.assertEqual(
            summary["selectedArtifact"]["path"],
            "backend/metal/SourceFreeMetalRuntimeExample.metallib",
        )
        admission = summary["runtimeArtifactAdmission"]
        self._assert_source_free_admission_invariants(summary)
        self.assertEqual(admission["decision"], "accepted")
        self.assertEqual(admission["target"]["decision"], "accepted")
        self.assertEqual(admission["target"]["category"], "target-accepted")
        self.assertEqual(admission["native"]["decision"], "accepted")
        self.assertEqual(admission["native"]["category"], "native-accepted")
        self.assertEqual(admission["sourcePackageFallback"]["decision"], "skipped")
        self.assertFalse(admission["sourcePackageFallback"]["fallbackAllowed"])
        self.assertEqual(
            admission["selectedArtifact"],
            {
                "name": "nativeBinary",
                "path": "backend/metal/SourceFreeMetalRuntimeExample.metallib",
                "declaredBy": "manifest.artifacts.nativeBinary",
                "exists": True,
                "selectedPackageMode": "native",
            },
        )
        self.assertEqual(
            [artifact["name"] for artifact in summary["selectedArtifacts"]],
            ["backendSource", "intermediate", "nativeBinary"],
        )
        self.assertTrue(summary["selectedArtifacts"][2]["exists"])
        self.assertEqual(
            summary["reflectionHandoff"]["entryPoint"],
            {
                "stage": "compute",
                "sourceName": "main",
                "backendName": "source_free_metal_main",
            },
        )
        self.assertEqual(
            summary["reflectionHandoff"]["targetResourceBinding"],
            {
                "stage": "compute",
                "entryPoint": "source_free_metal_main",
                "name": "OutputBuffer",
                "kind": "storageBuffer",
                "bindingClass": "buffer",
                "descriptorType": "buffer",
                "abi": {
                    "buffer": 0,
                },
            },
        )
        self.assertEqual(list(package_dir.rglob("*.cgl")), [])

    def test_source_free_metal_descriptor_matches_checked_out_bytes(self) -> None:
        package_dir = FIXTURE_ROOT / "source-free-metal-native.cglb"
        descriptor_path = (
            package_dir
            / "backend"
            / "metal"
            / "SourceFreeMetalRuntimeExample.native-artifact.json"
        )

        descriptor = json.loads(descriptor_path.read_text(encoding="utf-8"))
        source_bytes = (package_dir / descriptor["sourcePath"]).read_bytes()
        artifact_bytes = (package_dir / descriptor["artifactPath"]).read_bytes()

        self.assertEqual(descriptor["sourceHash"]["algorithm"], "sha256")
        self.assertEqual(
            descriptor["sourceHash"]["value"],
            hashlib.sha256(source_bytes).hexdigest(),
        )
        self.assertEqual(descriptor["artifactHash"]["algorithm"], "sha256")
        self.assertEqual(
            descriptor["artifactHash"]["value"],
            hashlib.sha256(artifact_bytes).hexdigest(),
        )
        self.assertEqual(descriptor["sizeBytes"], len(artifact_bytes))

    def test_example_opt_in_reports_metal_native_backend_admission(self) -> None:
        package_dir = FIXTURE_ROOT / "source-free-metal-native.cglb"

        with self._guard_crossgl_source_path_opens():
            summary = inspect_source_free_package(
                package_dir,
                "metal",
                native_admission=True,
            )

        admission = summary["nativeBackendAdmission"]
        self.assertTrue(summary["loadable"], summary["diagnostics"])
        self.assertEqual(admission["schemaVersion"], 1)
        self.assertTrue(admission["requested"])
        self.assertTrue(admission["available"])
        self.assertEqual(admission["loader"], "metal-native")
        self.assertEqual(admission["target"], "metal")
        self.assertEqual(admission["packageTarget"], "metal")
        self.assertEqual(admission["decision"], "accepted")
        self.assertEqual(admission["status"], "ready")
        self.assertTrue(admission["ready"])
        self.assertFalse(admission["sourceParsingRequired"])
        self.assertFalse(admission["compilerInvocationRequired"])
        self.assertFalse(admission["deviceExecutionRequired"])
        self.assertEqual(admission["deviceExecution"], "not-executed")
        self.assertEqual(
            admission["nativeAdmission"]["reason"],
            "runtime.native_backend_loader.accepted",
        )
        self.assertEqual(
            admission["nativeAdmission"]["nativeArtifact"]["status"],
            "accepted-native-artifact",
        )
        self.assertEqual(admission["nativeArtifact"]["name"], "nativeBinary")
        self.assertEqual(
            admission["nativeArtifact"]["path"],
            "backend/metal/SourceFreeMetalRuntimeExample.metallib",
        )
        self.assertEqual(
            admission["reflection"],
            {
                "entryPointCount": 1,
                "resourceCount": 1,
                "targetResourceBindingCount": 1,
            },
        )
        self.assertEqual(admission["sourceInputs"], [])
        self.assertEqual(admission["rejectReasons"], [])

    def test_example_selects_native_metal_artifact_from_zip_metadata(self) -> None:
        self._assert_zip_package_matches_directory_fixture(
            fixture_name="source-free-metal-native.cglb",
            loader_target="metal",
        )

    def test_example_selects_native_vulkan_artifact_from_metadata(self) -> None:
        package_dir = FIXTURE_ROOT / "source-free-vulkan-native.cglb"

        summary = inspect_source_free_package(package_dir, "vulkan")

        self.assertTrue(summary["loadable"], summary["diagnostics"])
        self.assertEqual(summary["status"], "compatible")
        self.assertFalse(summary["sourceParsingRequired"])
        self.assertTrue(summary["metadataOnly"])
        self.assertEqual(summary["sourceInputs"], [])
        self.assertEqual(
            [source["name"] for source in summary["metadataInputs"]],
            ["manifest", "reflection", "diagnostics"],
        )
        self.assertEqual(summary["deviceExecution"], "not-executed")
        self.assertFalse(summary["deviceExecutionRequired"])
        self.assertNotIn("nativeBackendAdmission", summary)
        self.assertEqual(summary["module"], "SourceFreeVulkanRuntimeExample")
        self.assertEqual(summary["availableTargets"], ["vulkan"])
        self.assertEqual(summary["selectedArtifact"]["name"], "nativeBinary")
        self.assertEqual(
            summary["selectedArtifact"]["path"],
            "backend/vulkan/SourceFreeVulkanRuntimeExample.spv",
        )
        admission = summary["runtimeArtifactAdmission"]
        self._assert_source_free_admission_invariants(summary)
        self.assertEqual(admission["decision"], "accepted")
        self.assertEqual(admission["target"]["decision"], "accepted")
        self.assertEqual(admission["target"]["category"], "target-accepted")
        self.assertEqual(admission["native"]["decision"], "accepted")
        self.assertEqual(admission["native"]["category"], "native-accepted")
        self.assertEqual(admission["sourcePackageFallback"]["decision"], "skipped")
        self.assertFalse(admission["sourcePackageFallback"]["fallbackAllowed"])
        self.assertEqual(
            admission["selectedArtifact"],
            {
                "name": "nativeBinary",
                "path": "backend/vulkan/SourceFreeVulkanRuntimeExample.spv",
                "declaredBy": "manifest.artifacts.nativeBinary",
                "exists": True,
                "selectedPackageMode": "native",
            },
        )
        self.assertEqual(
            [artifact["name"] for artifact in summary["selectedArtifacts"]],
            ["backendAssembly", "nativeBinary"],
        )
        self.assertTrue(summary["selectedArtifacts"][1]["exists"])
        self.assertEqual(
            summary["reflectionHandoff"]["entryPoint"],
            {
                "stage": "compute",
                "sourceName": "main",
                "backendName": "source_free_vulkan_main",
            },
        )
        self.assertEqual(
            summary["reflectionHandoff"]["targetResourceBinding"],
            {
                "stage": "compute",
                "entryPoint": "source_free_vulkan_main",
                "name": "OutputBuffer",
                "kind": "storageBuffer",
                "bindingClass": "storage-buffer",
                "descriptorType": "VK_DESCRIPTOR_TYPE_STORAGE_BUFFER",
                "abi": {
                    "set": 0,
                    "binding": 0,
                },
            },
        )
        self.assertEqual(list(package_dir.rglob("*.cgl")), [])

    def test_example_opt_in_reports_vulkan_native_backend_admission(self) -> None:
        package_dir = FIXTURE_ROOT / "source-free-vulkan-native.cglb"

        with self._guard_crossgl_source_path_opens():
            summary = inspect_source_free_package(
                package_dir,
                "vulkan",
                native_admission=True,
            )

        admission = summary["nativeBackendAdmission"]
        self.assertTrue(summary["loadable"], summary["diagnostics"])
        self.assertEqual(summary["status"], "compatible")
        self.assertEqual(admission["schemaVersion"], 1)
        self.assertTrue(admission["requested"])
        self.assertTrue(admission["available"])
        self.assertEqual(admission["loader"], "vulkan-native")
        self.assertEqual(admission["target"], "vulkan")
        self.assertEqual(admission["packageTarget"], "vulkan")
        self.assertEqual(admission["decision"], "accepted")
        self.assertEqual(admission["status"], "ready")
        self.assertTrue(admission["ready"])
        self.assertFalse(admission["sourceParsingRequired"])
        self.assertFalse(admission["compilerInvocationRequired"])
        self.assertFalse(admission["deviceExecutionRequired"])
        self.assertEqual(admission["deviceExecution"], "not-executed")
        self.assertEqual(
            admission["nativeAdmission"]["reason"],
            "runtime.native_backend_loader.accepted",
        )
        self.assertEqual(
            admission["nativeAdmission"]["nativeArtifact"]["status"],
            "accepted-native-artifact",
        )
        self.assertEqual(admission["nativeArtifact"]["name"], "nativeBinary")
        self.assertEqual(
            admission["nativeArtifact"]["path"],
            "backend/vulkan/SourceFreeVulkanRuntimeExample.spv",
        )
        self.assertEqual(
            admission["nativeArtifactDescriptor"]["fields"]["artifactHash"],
            {
                "algorithm": "sha256",
                "value": (
                    "82734019300f84793405cef2e9c3f67a21236603d789ef54f7e656c0ad4fb48b"
                ),
            },
        )
        self.assertEqual(
            admission["nativeProfile"]["fields"]["nativeBinary"],
            "backend/vulkan/SourceFreeVulkanRuntimeExample.spv",
        )
        self.assertEqual(
            admission["targetNativeAdmission"]["decision"],
            "accepted",
        )
        self.assertTrue(
            admission["targetNativeAdmission"]["spirvArtifact"][
                "descriptorArtifactHashMatchesSpirv"
            ]
        )
        self.assertEqual(
            admission["nativeApiBoundary"]["boundary"],
            "vulkan.native-api.metadata-v0",
        )
        self.assertTrue(
            admission["nativeApiBoundary"]["descriptorFreshness"][
                "artifactHashMatchesSpirv"
            ]
        )
        self.assertTrue(
            admission["nativeApiBoundary"]["nativeProfileCompatibility"][
                "nativeBinaryMatchesSpirv"
            ]
        )
        self.assertEqual(
            admission["reflection"],
            {
                "entryPointCount": 1,
                "resourceCount": 1,
                "targetResourceBindingCount": 1,
            },
        )
        self.assertEqual(admission["sourceInputs"], [])
        self.assertEqual(admission["rejectReasons"], [])

    def test_example_selects_native_vulkan_artifact_from_zip_metadata(self) -> None:
        self._assert_zip_package_matches_directory_fixture(
            fixture_name="source-free-vulkan-native.cglb",
            loader_target="vulkan",
        )

    def test_vulkan_fixture_native_descriptor_matches_checkout_bytes(self) -> None:
        package_dir = FIXTURE_ROOT / "source-free-vulkan-native.cglb"
        descriptor = json.loads(
            (
                package_dir
                / "backend"
                / "vulkan"
                / "SourceFreeVulkanRuntimeExample.native-artifact.json"
            ).read_text(encoding="utf-8")
        )

        native_bytes = (package_dir / descriptor["artifactPath"]).read_bytes()
        source_bytes = (package_dir / descriptor["sourcePath"]).read_bytes()

        self.assertEqual(len(native_bytes), descriptor["sizeBytes"])
        self.assertEqual(
            hashlib.sha256(native_bytes).hexdigest(),
            descriptor["artifactHash"]["value"],
        )
        self.assertEqual(
            hashlib.sha256(source_bytes).hexdigest(),
            descriptor["sourceHash"]["value"],
        )

    def test_directx_emitted_dxil_fixture_native_descriptor_matches_checkout_bytes(
        self,
    ) -> None:
        package_dir = FIXTURE_ROOT / "source-free-directx-emitted-dxil.cglb"
        descriptor = json.loads(
            (
                package_dir
                / "backend"
                / "directx"
                / "SourceFreeDirectXEmittedDxilRuntimeExample.native-artifact.json"
            ).read_text(encoding="utf-8")
        )

        native_bytes = (package_dir / descriptor["artifactPath"]).read_bytes()
        source_bytes = (package_dir / descriptor["sourcePath"]).read_bytes()

        self.assertEqual(len(native_bytes), descriptor["sizeBytes"])
        self.assertEqual(
            hashlib.sha256(native_bytes).hexdigest(),
            descriptor["artifactHash"]["value"],
        )
        self.assertEqual(
            hashlib.sha256(source_bytes).hexdigest(),
            descriptor["sourceHash"]["value"],
        )

    def test_opengl_validated_source_fixture_descriptor_matches_checkout_bytes(
        self,
    ) -> None:
        package_dir = FIXTURE_ROOT / "source-free-opengl-validated-source.cglb"
        descriptor = json.loads(
            (
                package_dir
                / "backend"
                / "opengl"
                / "SourceFreeOpenGLValidatedSourceRuntimeExample.native-artifact.json"
            ).read_text(encoding="utf-8")
        )

        native_bytes = (package_dir / descriptor["artifactPath"]).read_bytes()
        source_bytes = (package_dir / descriptor["sourcePath"]).read_bytes()

        self.assertEqual(len(native_bytes), descriptor["sizeBytes"])
        self.assertEqual(
            hashlib.sha256(native_bytes).hexdigest(),
            descriptor["artifactHash"]["value"],
        )
        self.assertEqual(
            hashlib.sha256(source_bytes).hexdigest(),
            descriptor["sourceHash"]["value"],
        )

    def test_example_selects_validated_opengl_source_package_artifact_from_metadata(
        self,
    ) -> None:
        package_dir = FIXTURE_ROOT / "source-free-opengl-validated-source.cglb"

        with self._guard_crossgl_source_path_opens():
            summary = inspect_source_free_package(package_dir, "opengl")

        self.assertTrue(summary["loadable"], summary["diagnostics"])
        self.assertEqual(summary["status"], "compatible")
        self.assertFalse(summary["sourceParsingRequired"])
        self.assertTrue(summary["metadataOnly"])
        self.assertEqual(summary["sourceInputs"], [])
        self.assertFalse(summary["compilerInvocationRequired"])
        self.assertFalse(summary["deviceExecutionRequired"])
        self.assertEqual(
            summary["module"],
            "SourceFreeOpenGLValidatedSourceRuntimeExample",
        )
        self.assertEqual(summary["selectedArtifact"]["name"], "backendSource")
        self.assertEqual(
            summary["selectedArtifact"]["path"],
            ("backend/opengl/SourceFreeOpenGLValidatedSourceRuntimeExample.comp.glsl"),
        )
        admission = summary["runtimeArtifactAdmission"]
        self._assert_source_free_admission_invariants(summary)
        self.assertEqual(admission["decision"], "accepted")
        self.assertEqual(admission["selectedPackageMode"], "source-package")
        self.assertEqual(admission["native"]["decision"], "skipped")
        self.assertEqual(admission["native"]["category"], "native-not-requested")
        self.assertEqual(admission["native"]["nativeBinaryStatus"], "validated")
        self.assertEqual(admission["sourcePackageFallback"]["decision"], "accepted")
        self.assertEqual(
            admission["selectedArtifact"]["name"],
            "backendSource",
        )
        self.assertEqual(
            [artifact["name"] for artifact in summary["selectedArtifacts"]],
            ["backendSource", "nativeBinary"],
        )
        self.assertEqual(list(package_dir.rglob("*.cgl")), [])

    def test_example_selects_opengl_source_package_artifact_from_metadata(
        self,
    ) -> None:
        package_dir = FIXTURE_ROOT / "source-free-opengl.cglb"

        summary = inspect_source_free_package(package_dir, "opengl")

        self.assertTrue(summary["loadable"], summary["diagnostics"])
        self.assertEqual(summary["status"], "source-only")
        self.assertFalse(summary["sourceParsingRequired"])
        self.assertTrue(summary["metadataOnly"])
        self.assertEqual(summary["sourceInputs"], [])
        self.assertEqual(
            [source["name"] for source in summary["metadataInputs"]],
            ["manifest", "reflection", "diagnostics"],
        )
        self.assertEqual(summary["deviceExecution"], "not-executed")
        self.assertFalse(summary["compilerInvocationRequired"])
        self.assertFalse(summary["deviceExecutionRequired"])
        self.assertNotIn("nativeBackendAdmission", summary)
        self.assertEqual(summary["module"], "SourceFreeOpenGLRuntimeExample")
        self.assertEqual(summary["availableTargets"], ["opengl"])
        self.assertEqual(summary["selectedArtifact"]["name"], "backendSource")
        self.assertEqual(
            summary["selectedArtifact"]["path"],
            "backend/opengl/SourceFreeOpenGLRuntimeExample.comp.glsl",
        )
        admission = summary["runtimeArtifactAdmission"]
        self._assert_source_free_admission_invariants(summary)
        self.assertEqual(admission["decision"], "accepted")
        self.assertEqual(admission["target"]["decision"], "accepted")
        self.assertEqual(admission["target"]["category"], "target-accepted")
        self.assertEqual(admission["native"]["decision"], "skipped")
        self.assertEqual(admission["native"]["category"], "native-planned-only")
        self.assertEqual(admission["native"]["nativeBinaryStatus"], "planned")
        self.assertEqual(
            admission["native"]["reason"],
            "runtime.native_artifact.source_package_fallback",
        )
        self.assertEqual(admission["sourcePackageFallback"]["decision"], "accepted")
        self.assertTrue(admission["sourcePackageFallback"]["fallbackAccepted"])
        self.assertEqual(
            admission["selectedArtifact"],
            {
                "name": "backendSource",
                "path": "backend/opengl/SourceFreeOpenGLRuntimeExample.comp.glsl",
                "declaredBy": "manifest.artifacts.backendSource",
                "exists": True,
                "selectedPackageMode": "source-package",
            },
        )
        self.assertEqual(
            [artifact["name"] for artifact in summary["selectedArtifacts"]],
            ["backendSource", "nativeBinary"],
        )
        self.assertTrue(summary["selectedArtifacts"][1]["exists"])
        self.assertEqual(
            summary["reflectionHandoff"]["entryPoint"],
            {
                "stage": "compute",
                "sourceName": "main",
                "backendName": "source_free_opengl_main",
            },
        )
        self.assertEqual(
            summary["reflectionHandoff"]["targetResourceBinding"],
            {
                "stage": "compute",
                "entryPoint": "source_free_opengl_main",
                "name": "OutputBuffer",
                "kind": "storageBuffer",
                "bindingClass": "storage-buffer",
                "descriptorType": "shader-storage-buffer",
                "abi": {
                    "program": 0,
                    "binding": 0,
                },
            },
        )
        self.assertEqual(list(package_dir.rglob("*.cgl")), [])

    def test_example_opt_in_reports_opengl_native_backend_rejection(self) -> None:
        package_dir = FIXTURE_ROOT / "source-free-opengl.cglb"

        with self._guard_crossgl_source_path_opens():
            summary = inspect_source_free_package(
                package_dir,
                "opengl",
                native_admission=True,
            )

        admission = summary["nativeBackendAdmission"]
        native_admission = admission["nativeAdmission"]
        native_artifact = native_admission["nativeArtifact"]
        rejection = native_admission["blockedByDiagnostics"][0]
        self.assertTrue(summary["loadable"], summary["diagnostics"])
        self.assertEqual(summary["status"], "source-only")
        self.assertEqual(admission["schemaVersion"], 1)
        self.assertTrue(admission["requested"])
        self.assertTrue(admission["available"])
        self.assertEqual(admission["loader"], "opengl-native")
        self.assertEqual(admission["target"], "opengl")
        self.assertEqual(admission["packageTarget"], "opengl")
        self.assertEqual(admission["decision"], "rejected")
        self.assertEqual(admission["status"], "rejected")
        self.assertFalse(admission["ready"])
        self.assertFalse(admission["loadable"])
        self.assertFalse(admission["sourceParsingRequired"])
        self.assertFalse(admission["compilerInvocationRequired"])
        self.assertFalse(admission["deviceExecutionRequired"])
        self.assertEqual(admission["deviceExecution"], "not-executed")
        self.assertEqual(
            native_admission["reason"],
            "opengl_loader.native_mode_unsupported",
        )
        self.assertEqual(native_artifact["decision"], "rejected")
        self.assertEqual(
            native_artifact["reason"],
            "opengl_loader.native_mode_unsupported",
        )
        self.assertTrue(native_artifact["declared"])
        self.assertTrue(native_artifact["available"])
        self.assertFalse(native_artifact["selectedForRuntime"])
        self.assertFalse(native_artifact["bytesRequired"])
        self.assertEqual(native_artifact["nativeBinaryStatus"], "planned")
        self.assertIsNone(admission["nativeArtifact"])
        self.assertEqual(rejection["severity"], "error")
        self.assertEqual(rejection["code"], "opengl_loader.native_mode_unsupported")
        self.assertIn("OpenGL native mode is not supported", rejection["message"])
        self.assertEqual(rejection["document"], "manifest")
        self.assertEqual(rejection["artifact"], "nativeBinary")
        self.assertEqual(rejection["expected"], "source-package")
        self.assertEqual(rejection["actual"], "native")
        self.assertEqual(
            [diagnostic["code"] for diagnostic in admission["rejectReasons"]],
            ["opengl_loader.native_mode_unsupported"],
        )
        self.assertEqual(
            admission["reflection"],
            {
                "entryPointCount": 1,
                "resourceCount": 1,
                "targetResourceBindingCount": 1,
            },
        )
        self.assertEqual(admission["sourceInputs"], [])

    def test_example_selects_opengl_source_package_artifact_from_zip_metadata(
        self,
    ) -> None:
        self._assert_zip_package_matches_directory_fixture(
            fixture_name="source-free-opengl.cglb",
            loader_target="opengl",
        )

    def test_example_selects_artifact_and_reflection_metadata(self) -> None:
        package_dir = FIXTURE_ROOT / "source-free-directx.cglb"

        summary = inspect_source_free_package(package_dir, "directx")

        self.assertTrue(summary["loadable"], summary["diagnostics"])
        self.assertEqual(summary["status"], "source-only")
        self.assertFalse(summary["sourceParsingRequired"])
        self.assertTrue(summary["metadataOnly"])
        self.assertEqual(summary["sourceInputs"], [])
        self.assertEqual(
            [source["name"] for source in summary["metadataInputs"]],
            ["manifest", "reflection", "diagnostics"],
        )
        self.assertEqual(summary["deviceExecution"], "not-executed")
        self.assertFalse(summary["deviceExecutionRequired"])
        self.assertEqual(summary["module"], "SourceFreeRuntimeExample")
        self.assertEqual(summary["availableTargets"], ["directx"])
        self.assertEqual(
            summary["packageArtifactRequirementsSource"],
            "legacy-v0-target-contract",
        )
        self.assertFalse(summary["packageArtifactRequirements"]["declared"])
        self.assertTrue(summary["packageArtifactRequirements"]["legacyInferred"])
        self.assertEqual(
            summary["packageArtifactRequirements"]["requiredPathArtifacts"],
            ["backendSource", "nativeBinary"],
        )
        self.assertEqual(summary["selectedArtifact"]["name"], "backendSource")
        self.assertEqual(
            summary["selectedArtifact"]["path"],
            "backend/directx/SourceFreeRuntimeExample.hlsl",
        )
        admission = summary["runtimeArtifactAdmission"]
        self._assert_source_free_admission_invariants(summary)
        self.assertEqual(admission["decision"], "accepted")
        self.assertEqual(admission["target"]["decision"], "accepted")
        self.assertEqual(admission["native"]["decision"], "skipped")
        self.assertEqual(admission["native"]["category"], "native-planned-only")
        self.assertEqual(
            admission["native"]["reason"],
            "runtime.native_artifact.source_package_fallback",
        )
        self.assertEqual(admission["sourcePackageFallback"]["decision"], "accepted")
        self.assertTrue(admission["sourcePackageFallback"]["fallbackAccepted"])
        self.assertEqual(
            admission["selectedArtifact"],
            {
                "name": "backendSource",
                "path": "backend/directx/SourceFreeRuntimeExample.hlsl",
                "declaredBy": "manifest.artifacts.backendSource",
                "exists": True,
                "selectedPackageMode": "source-package",
            },
        )
        self.assertEqual(
            [artifact["name"] for artifact in summary["selectedArtifacts"]],
            ["backendSource", "nativeBinary"],
        )
        self.assertFalse(summary["selectedArtifacts"][1]["exists"])
        self.assertEqual(
            summary["reflectionHandoff"]["entryPoint"],
            {
                "stage": "compute",
                "sourceName": "main",
                "backendName": "source_free_main",
            },
        )
        self.assertEqual(
            summary["reflectionHandoff"]["targetResourceBinding"],
            {
                "stage": "compute",
                "entryPoint": "source_free_main",
                "name": "OutputBuffer",
                "kind": "storageBuffer",
                "bindingClass": "uav",
                "descriptorType": "UAV",
                "abi": {
                    "space": 0,
                    "register": "u0",
                },
            },
        )
        self.assertEqual(list(package_dir.rglob("*.cgl")), [])

    def test_example_opt_in_reports_directx_native_backend_rejection(self) -> None:
        package_dir = FIXTURE_ROOT / "source-free-directx.cglb"

        with self._guard_crossgl_source_path_opens():
            summary = inspect_source_free_package(
                package_dir,
                "directx",
                native_admission=True,
            )

        admission = summary["nativeBackendAdmission"]
        self.assertTrue(summary["loadable"], summary["diagnostics"])
        self.assertEqual(summary["status"], "source-only")
        self.assertEqual(admission["loader"], "directx-native")
        self.assertEqual(admission["decision"], "rejected")
        self.assertEqual(admission["status"], "rejected")
        self.assertFalse(admission["ready"])
        self.assertFalse(admission["loadable"])
        self.assertFalse(admission["sourceParsingRequired"])
        self.assertFalse(admission["compilerInvocationRequired"])
        self.assertFalse(admission["deviceExecutionRequired"])
        self.assertEqual(
            admission["nativeAdmission"]["nativeArtifact"]["status"],
            "planned-native-metadata",
        )
        self.assertEqual(
            admission["nativeAdmission"]["runtimeSelection"]["native"]["category"],
            "native-planned-only",
        )
        api_boundary = admission["nativeApiBoundary"]
        self.assertEqual(
            api_boundary["boundary"],
            "directx.native-api.metadata-v0",
        )
        self.assertEqual(api_boundary["decision"], "rejected")
        self.assertEqual(
            api_boundary["runtimeInputs"]["manifest"]["nativeBinaryStatus"],
            "planned",
        )
        self.assertEqual(
            api_boundary["runtimeInputs"]["nativeBinaryArtifact"]["path"],
            "backend/directx/SourceFreeRuntimeExample.dxil",
        )
        self.assertEqual(
            api_boundary["runtimeInputs"]["nativeBinaryArtifact"][
                "nativeAdmissionStatus"
            ],
            "planned-native-metadata",
        )
        self.assertEqual(
            api_boundary["runtimeInputs"]["dxilArtifact"]["path"],
            "backend/directx/SourceFreeRuntimeExample.dxil",
        )
        self.assertFalse(api_boundary["d3dRuntimeCallsPerformed"])
        self.assertFalse(api_boundary["d3dDeviceCreationPerformed"])
        self.assertFalse(api_boundary["d3dShaderModuleCreationPerformed"])
        self.assertFalse(api_boundary["d3dPipelineCreationPerformed"])
        self.assertFalse(api_boundary["d3dCommandExecutionPerformed"])
        self.assertEqual(
            api_boundary["runtimeInputs"]["reflection"]["hlslRegisterSpaceBindings"][0],
            {
                "stage": "compute",
                "entryPoint": "source_free_main",
                "name": "OutputBuffer",
                "kind": "storageBuffer",
                "register": "u0",
                "space": 0,
                "bindingClass": "uav",
                "descriptorType": "UAV",
                "hlslType": "RWStructuredBuffer<float4>",
            },
        )
        self.assertEqual(
            [diagnostic["code"] for diagnostic in admission["rejectReasons"]],
            [
                "package.native_binary_status.not_ready",
                "package.artifact.selection_file_missing",
            ],
        )
        self.assertEqual(admission["sourceInputs"], [])

    def test_example_preserves_target_legalization_evidence_in_handoffs(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            package_dir = Path(tmp_dir) / "source-free-directx.cglb"
            shutil.copytree(FIXTURE_ROOT / "source-free-directx.cglb", package_dir)
            source_path = package_dir / "source" / "not-declared.cgl"
            source_path.parent.mkdir()
            source_path.write_text(
                "shader source_free_loader_must_not_parse_this {}\n",
                encoding="utf-8",
            )
            artifact_evidence_ids = [
                "target-legalization.v1.directx.package-artifact.required.backendSource",
                "target-legalization.v1.directx.package-artifact.required.nativeBinary",
            ]
            tool_requirements = {
                "target": "directx",
                "packageMode": "source-package",
                "requiredToolCount": 2,
                "missingToolCount": 2,
                "requiredToolIds": [
                    "directx.toolchain.dxc",
                    "directx.validation.dxil-validator",
                ],
                "missingToolIds": [
                    "directx.toolchain.dxc",
                    "directx.validation.dxil-validator",
                ],
                "optionalNativeToolMissing": True,
                "optionalNativeToolStatus": "missing",
                "toolRequirementEvidenceIds": [
                    "target-legalization.v1.directx.tool-requirements.present",
                    "target-legalization.v1.directx.tool-requirement.required.toolchain.dxc",
                    "target-legalization.v1.directx.tool-requirement.required.validation.dxil-validator",
                    "target-legalization.v1.directx.tool-requirement.missing.toolchain.dxc",
                    "target-legalization.v1.directx.tool-requirement.missing.validation.dxil-validator",
                ],
            }
            manifest_path = package_dir / "manifest.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["packageArtifactRequirements"] = {
                "target": "directx",
                "packageMode": "source-package",
                "requiredPathArtifacts": ["backendSource", "nativeBinary"],
                "requiresNativeBinaryStatus": True,
                "allowsPlannedNativeBinary": True,
                "allowsPlannedNativeSourceEvidence": True,
                "evidenceIds": artifact_evidence_ids,
            }
            manifest["targetLegalizationToolRequirements"] = tool_requirements
            manifest_path.write_text(
                json.dumps(manifest, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )

            with self._guard_crossgl_source_path_opens():
                summary = inspect_source_free_package(
                    package_dir,
                    "directx",
                    native_admission=True,
                )

        evidence = summary["targetLegalizationEvidence"]
        self.assertTrue(summary["loadable"], summary["diagnostics"])
        self.assertEqual(summary["sourceInputs"], [])
        self.assertEqual(evidence["health"], "ok")
        self.assertEqual(evidence["diagnostics"], [])
        self.assertEqual(
            evidence["packageArtifactRequirementEvidenceIds"],
            artifact_evidence_ids,
        )
        self.assertEqual(
            evidence["manifestToolRequirements"],
            {"present": True, **tool_requirements},
        )
        expected_tool_requirements = {"present": True, **tool_requirements}
        self.assertEqual(
            summary["targetLegalizationToolRequirements"],
            expected_tool_requirements,
        )
        self.assertEqual(
            summary["packageArtifactRequirementsSource"],
            "manifest.packageArtifactRequirements",
        )
        self.assertTrue(summary["packageArtifactRequirements"]["declared"])
        self.assertFalse(summary["packageArtifactRequirements"]["legacyInferred"])
        self.assertEqual(
            summary["packageArtifactRequirements"]["requiredPathArtifacts"],
            ["backendSource", "nativeBinary"],
        )
        self.assertTrue(
            evidence["checks"]["manifestToolRequirementsTargetMatchesPackage"]
        )
        self.assertTrue(
            evidence["checks"]["manifestToolRequirementsPackageModeMatchesRequirements"]
        )
        self.assertTrue(evidence["checks"]["manifestToolRequirementEvidenceIdsPresent"])
        self.assertEqual(
            summary["runtimeArtifactAdmission"]["targetLegalizationEvidence"],
            evidence,
        )
        self.assertEqual(
            summary["runtimeArtifactAdmission"]["targetLegalizationToolRequirements"],
            expected_tool_requirements,
        )
        self.assertEqual(
            summary["nativeBackendAdmission"]["targetLegalizationEvidence"],
            evidence,
        )
        self.assertEqual(
            summary["nativeBackendAdmission"]["targetLegalizationToolRequirements"],
            expected_tool_requirements,
        )
        self.assertEqual(
            summary["nativeBackendAdmission"]["nativeAdmission"][
                "targetLegalizationToolRequirements"
            ],
            expected_tool_requirements,
        )
        self.assertEqual(
            summary["nativeBackendAdmission"]["nativeApiBoundary"][
                "targetLegalizationToolRequirements"
            ],
            expected_tool_requirements,
        )
        self.assertEqual(summary["nativeBackendAdmission"]["sourceInputs"], [])

    def test_example_selects_directx_artifact_from_zip_metadata(self) -> None:
        self._assert_zip_package_matches_directory_fixture(
            fixture_name="source-free-directx.cglb",
            loader_target="directx",
        )

    def test_example_selects_directx_emitted_dxil_native_artifact_from_metadata(
        self,
    ) -> None:
        package_dir = FIXTURE_ROOT / "source-free-directx-emitted-dxil.cglb"

        with self._guard_crossgl_source_path_opens():
            summary = inspect_source_free_package(package_dir, "directx")

        self.assertTrue(summary["loadable"], summary["diagnostics"])
        self.assertEqual(summary["status"], "compatible")
        self.assertFalse(summary["sourceParsingRequired"])
        self.assertTrue(summary["metadataOnly"])
        self.assertEqual(summary["sourceInputs"], [])
        self.assertEqual(summary["deviceExecution"], "not-executed")
        self.assertFalse(summary["compilerInvocationRequired"])
        self.assertFalse(summary["deviceExecutionRequired"])
        self.assertNotIn("nativeBackendAdmission", summary)
        self.assertEqual(
            summary["module"],
            "SourceFreeDirectXEmittedDxilRuntimeExample",
        )
        self.assertEqual(summary["availableTargets"], ["directx"])
        self.assertEqual(summary["selectedArtifact"]["name"], "nativeBinary")
        self.assertEqual(
            summary["selectedArtifact"]["path"],
            "backend/directx/SourceFreeDirectXEmittedDxilRuntimeExample.dxil",
        )
        admission = summary["runtimeArtifactAdmission"]
        self._assert_source_free_admission_invariants(summary)
        self.assertEqual(admission["decision"], "accepted")
        self.assertEqual(admission["selectedPackageMode"], "native")
        self.assertEqual(admission["target"]["decision"], "accepted")
        self.assertEqual(admission["target"]["category"], "target-accepted")
        self.assertEqual(admission["native"]["decision"], "accepted")
        self.assertEqual(admission["native"]["category"], "native-accepted")
        self.assertEqual(admission["native"]["nativeBinaryStatus"], "emitted")
        self.assertEqual(admission["sourcePackageFallback"]["decision"], "skipped")
        self.assertFalse(admission["sourcePackageFallback"]["fallbackAccepted"])
        self.assertTrue(admission["sourcePackageFallback"]["fallbackAllowed"])
        self.assertEqual(
            admission["selectedArtifact"],
            {
                "name": "nativeBinary",
                "path": (
                    "backend/directx/SourceFreeDirectXEmittedDxilRuntimeExample.dxil"
                ),
                "declaredBy": "manifest.artifacts.nativeBinary",
                "exists": True,
                "selectedPackageMode": "native",
            },
        )
        self.assertEqual(
            [artifact["name"] for artifact in summary["selectedArtifacts"]],
            ["backendSource", "nativeBinary"],
        )
        self.assertTrue(summary["selectedArtifacts"][0]["exists"])
        self.assertTrue(summary["selectedArtifacts"][1]["exists"])
        self.assertEqual(
            summary["reflectionHandoff"]["entryPoint"],
            {
                "stage": "compute",
                "sourceName": "main",
                "backendName": "source_free_directx_emitted_dxil_main",
            },
        )
        self.assertEqual(
            summary["reflectionHandoff"]["targetResourceBinding"],
            {
                "stage": "compute",
                "entryPoint": "source_free_directx_emitted_dxil_main",
                "name": "OutputBuffer",
                "kind": "storageBuffer",
                "bindingClass": "uav",
                "descriptorType": "UAV",
                "abi": {
                    "space": 0,
                    "register": "u0",
                },
            },
        )
        self.assertEqual(list(package_dir.rglob("*.cgl")), [])

    def test_example_handoff_preserves_storage_image_binding_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            package_dir = Path(tmp_dir) / "source-free-directx-emitted-dxil.cglb"
            shutil.copytree(
                FIXTURE_ROOT / "source-free-directx-emitted-dxil.cglb",
                package_dir,
            )
            reflection_path = package_dir / "reflection.json"
            reflection = json.loads(reflection_path.read_text(encoding="utf-8"))
            storage_metadata = {
                "storageImageFormat": "rgba8",
                "storageImageAccess": "read_write",
            }
            reflection["resources"][0].update(
                {
                    "name": "OutputImage",
                    "kind": "storageImage",
                    "type": "RWTexture2D<float4>",
                    **storage_metadata,
                }
            )
            reflection["targetResourceBindings"][0].update(
                {
                    "name": "OutputImage",
                    "kind": "storageImage",
                    "sourceType": "RWTexture2D<float4>",
                    "descriptorType": "UAV",
                    "hlslType": "RWTexture2D<float4>",
                    **storage_metadata,
                }
            )
            reflection_path.write_text(
                json.dumps(reflection, indent=2) + "\n",
                encoding="utf-8",
            )

            with self._guard_crossgl_source_path_opens():
                summary = inspect_source_free_package(package_dir, "directx")

        binding = summary["reflectionHandoff"]["targetResourceBinding"]
        self.assertTrue(summary["loadable"], summary["diagnostics"])
        self.assertEqual(binding["storageImageFormat"], "rgba8")
        self.assertEqual(binding["storageImageAccess"], "read_write")

    def test_example_opt_in_reports_directx_emitted_dxil_native_admission(
        self,
    ) -> None:
        package_dir = FIXTURE_ROOT / "source-free-directx-emitted-dxil.cglb"

        with self._guard_crossgl_source_path_opens():
            summary = inspect_source_free_package(
                package_dir,
                "directx",
                native_admission=True,
            )

        admission = summary["nativeBackendAdmission"]
        descriptor = admission["nativeArtifactDescriptor"]
        api_boundary = admission["nativeApiBoundary"]
        descriptor_input = api_boundary["runtimeInputs"]["nativeArtifactDescriptor"]
        native_input = api_boundary["runtimeInputs"]["nativeBinaryArtifact"]
        dxil_input = api_boundary["runtimeInputs"]["dxilArtifact"]
        dxbc_input = api_boundary["runtimeInputs"]["dxbcArtifact"]

        self.assertTrue(summary["loadable"], summary["diagnostics"])
        self.assertEqual(summary["status"], "compatible")
        self.assertEqual(admission["schemaVersion"], 1)
        self.assertTrue(admission["requested"])
        self.assertTrue(admission["available"])
        self.assertEqual(admission["loader"], "directx-native")
        self.assertEqual(admission["target"], "directx")
        self.assertEqual(admission["packageTarget"], "directx")
        self.assertEqual(admission["decision"], "accepted")
        self.assertEqual(admission["status"], "ready")
        self.assertTrue(admission["ready"])
        self.assertFalse(admission["sourceParsingRequired"])
        self.assertFalse(admission["compilerInvocationRequired"])
        self.assertFalse(admission["deviceExecutionRequired"])
        self.assertEqual(admission["deviceExecution"], "not-executed")
        self.assertEqual(
            admission["nativeAdmission"]["reason"],
            "runtime.native_backend_loader.accepted",
        )
        self.assertEqual(
            admission["nativeAdmission"]["nativeArtifact"]["status"],
            "accepted-native-artifact",
        )
        self.assertEqual(admission["nativeArtifact"]["name"], "nativeBinary")
        self.assertEqual(
            admission["nativeArtifact"]["path"],
            "backend/directx/SourceFreeDirectXEmittedDxilRuntimeExample.dxil",
        )
        self.assertTrue(descriptor["sourcePathDeclared"])
        self.assertNotIn("sourcePath", descriptor["fields"])
        self.assertEqual(descriptor["fields"]["nativeBinaryStatus"], "emitted")
        self.assertEqual(descriptor["fields"]["validationStatus"], "not-run")
        self.assertEqual(
            descriptor["fields"]["artifactHash"],
            {
                "algorithm": "sha256",
                "value": (
                    "dba3c188e179bfea1ccf34cfc9e024eb9d1b35d08d51c80c1a6e47b50d4c65ec"
                ),
            },
        )
        self.assertEqual(api_boundary["boundary"], "directx.native-api.metadata-v0")
        self.assertEqual(api_boundary["decision"], "accepted")
        self.assertEqual(api_boundary["status"], "ready")
        self.assertFalse(api_boundary["d3dRuntimeCallsPerformed"])
        self.assertFalse(api_boundary["d3dDeviceCreationPerformed"])
        self.assertFalse(api_boundary["d3dShaderModuleCreationPerformed"])
        self.assertFalse(api_boundary["d3dPipelineCreationPerformed"])
        self.assertFalse(api_boundary["d3dCommandExecutionPerformed"])
        self.assertEqual(
            api_boundary["runtimeInputs"]["manifest"]["nativeBinaryStatus"],
            "emitted",
        )
        self.assertEqual(native_input["nativeBinaryStatus"], "emitted")
        self.assertEqual(native_input["binaryKind"], "directx.dxil")
        self.assertEqual(
            native_input["binaryKindSource"],
            "nativeArtifactDescriptor.binaryKind",
        )
        self.assertTrue(native_input["acceptedForLoad"])
        self.assertTrue(native_input["descriptorArtifactHashMatchesNativeBinary"])
        self.assertEqual(
            dxil_input["path"],
            "backend/directx/SourceFreeDirectXEmittedDxilRuntimeExample.dxil",
        )
        self.assertTrue(dxil_input["actualBinaryKindMatches"])
        self.assertTrue(dxil_input["acceptedForLoad"])
        self.assertFalse(dxbc_input["actualBinaryKindMatches"])
        self.assertFalse(dxbc_input["acceptedForLoad"])
        self.assertTrue(descriptor_input["schemaVersionCompatible"])
        self.assertTrue(descriptor_input["contractVersionCompatible"])
        self.assertTrue(descriptor_input["targetMatchesLoader"])
        self.assertTrue(descriptor_input["binaryKindMatchesLoader"])
        self.assertTrue(descriptor_input["artifactPathMatchesNativeBinary"])
        self.assertTrue(descriptor_input["artifactHashMatchesNativeBinary"])
        self.assertTrue(descriptor_input["sizeBytesMatchesNativeBinary"])
        self.assertTrue(descriptor_input["nativeBinaryStatusMatchesManifest"])
        self.assertTrue(descriptor_input["sourcePathDeclared"])
        self.assertFalse(descriptor_input["sourcePathExposed"])
        self.assertTrue(
            api_boundary["descriptorFreshness"]["artifactPathMatchesNativeBinary"]
        )
        self.assertTrue(
            api_boundary["descriptorFreshness"]["artifactHashMatchesNativeBinary"]
        )
        self.assertTrue(
            api_boundary["descriptorFreshness"]["sizeBytesMatchesNativeBinary"]
        )
        self.assertTrue(
            api_boundary["descriptorFreshness"]["nativeBinaryStatusMatchesManifest"]
        )
        self.assertEqual(
            api_boundary["runtimeInputs"]["reflection"]["hlslRegisterSpaceBindings"][0],
            {
                "stage": "compute",
                "entryPoint": "source_free_directx_emitted_dxil_main",
                "name": "OutputBuffer",
                "kind": "storageBuffer",
                "register": "u0",
                "space": 0,
                "bindingClass": "uav",
                "descriptorType": "UAV",
                "hlslType": "RWStructuredBuffer<float4>",
            },
        )
        self.assertEqual(
            admission["reflection"],
            {
                "entryPointCount": 1,
                "resourceCount": 1,
                "targetResourceBindingCount": 1,
            },
        )
        self.assertEqual(admission["sourceInputs"], [])
        self.assertEqual(admission["rejectReasons"], [])

    def test_example_selects_directx_emitted_dxil_artifact_from_zip_metadata(
        self,
    ) -> None:
        self._assert_zip_package_matches_directory_fixture(
            fixture_name="source-free-directx-emitted-dxil.cglb",
            loader_target="directx",
        )

    def test_example_rejects_incompatible_package_without_source_parse(self) -> None:
        package_dir = FIXTURE_ROOT / "future-schema-directx.cglb"

        summary = inspect_source_free_package(package_dir, "directx")

        self.assertFalse(summary["loadable"])
        self.assertEqual(summary["status"], "unsupported-version")
        self.assertFalse(summary["sourceParsingRequired"])
        self.assertTrue(summary["metadataOnly"])
        self.assertEqual(summary["sourceInputs"], [])
        self.assertFalse(summary["deviceExecutionRequired"])
        self.assertIsNone(summary["selectedArtifact"])
        self.assertEqual(summary["selectedArtifacts"], [])
        self.assertEqual(summary["reflectionHandoff"]["entryPoint"], None)
        admission = summary["runtimeArtifactAdmission"]
        self._assert_source_free_admission_invariants(summary)
        self.assertEqual(admission["decision"], "rejected")
        self.assertEqual(admission["target"]["decision"], "accepted")
        self.assertEqual(admission["native"]["decision"], "skipped")
        self.assertEqual(admission["native"]["reason"], "package.schema.incompatible")
        self.assertEqual(admission["sourcePackageFallback"]["decision"], "skipped")
        self.assertIsNone(admission["selectedArtifact"])
        self.assertEqual(
            [diagnostic["code"] for diagnostic in summary["diagnostics"]],
            ["package.schema.incompatible", LEGACY_REQUIREMENTS_FALLBACK_CODE],
        )
        self.assertEqual(list(package_dir.rglob("*.cgl")), [])

    def test_example_rejects_future_schema_zip_before_artifact_or_source_fallback(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            temp_root = Path(tmp_dir)
            zip_path = temp_root / "future-schema-directx.cglb"
            prefix = zip_path.name
            self._write_zip_package(
                FIXTURE_ROOT / "future-schema-directx.cglb",
                zip_path,
                prefix=prefix,
                extra_members={
                    f"{prefix}/backend/directx/FutureSchemaRuntimeExample.dxil": (
                        b"future schema native artifact must not be selected"
                    ),
                    f"{prefix}/source/fallback.cgl": (
                        "shader fallback_must_not_be_parsed {}\n"
                    ),
                    "near-zip-fallback.cgl": (
                        "shader near_zip_must_not_be_parsed {}\n"
                    ),
                },
            )

            near_source_path = temp_root / "near-future-schema.cgl"
            near_source_path.write_text(
                "shader near_filesystem_must_not_be_parsed {}\n",
                encoding="utf-8",
            )

            with self._guard_crossgl_source_path_opens():
                with self._guard_crossgl_source_archive_opens():
                    summary = inspect_source_free_package(zip_path, "directx")

        self.assertFalse(summary["loadable"])
        self.assertEqual(summary["status"], "unsupported-version")
        self.assertFalse(summary["sourceParsingRequired"])
        self.assertTrue(summary["metadataOnly"])
        self.assertEqual(summary["sourceInputs"], [])
        self.assertFalse(summary["deviceExecutionRequired"])
        self.assertIsNone(summary["selectedArtifact"])
        self.assertEqual(summary["selectedArtifacts"], [])
        self.assertIsNone(summary["runtimeArtifactAdmission"]["selectedArtifact"])
        self.assertEqual(summary["reflectionHandoff"]["entryPoint"], None)
        self.assertEqual(
            [diagnostic["code"] for diagnostic in summary["diagnostics"]],
            ["package.schema.incompatible", LEGACY_REQUIREMENTS_FALLBACK_CODE],
        )

    def test_cli_prints_deterministic_metadata_handoff(self) -> None:
        summary = self._run_cli_json(
            fixture_name="source-free-directx.cglb",
            loader_target="directx",
        )

        self.assertEqual(summary["schemaVersion"], 1)
        self.assertEqual(summary["loaderTarget"], "directx")
        self._assert_cli_metadata_only_invariants(summary)
        self.assertEqual(
            summary["runtimeArtifactAdmission"]["sourcePackageFallback"]["decision"],
            "accepted",
        )
        self.assertEqual(summary["selectedArtifact"]["name"], "backendSource")
        self.assertEqual(
            summary["diagnostics"],
            [LEGACY_REQUIREMENTS_FALLBACK_DIAGNOSTIC],
        )

    def test_cli_prints_directx_emitted_dxil_native_metadata_handoff(self) -> None:
        summary = self._run_cli_json(
            fixture_name="source-free-directx-emitted-dxil.cglb",
            loader_target="directx",
            native_admission=True,
        )

        self.assertEqual(summary["schemaVersion"], 1)
        self.assertEqual(summary["loaderTarget"], "directx")
        self.assertEqual(summary["packageTarget"], "directx")
        self.assertEqual(summary["status"], "compatible")
        self._assert_cli_metadata_only_invariants(summary)
        self.assertEqual(summary["selectedArtifact"]["name"], "nativeBinary")
        self.assertEqual(
            summary["selectedArtifact"]["path"],
            "backend/directx/SourceFreeDirectXEmittedDxilRuntimeExample.dxil",
        )
        admission = summary["nativeBackendAdmission"]
        self.assertEqual(admission["loader"], "directx-native")
        self.assertEqual(admission["decision"], "accepted")
        self.assertEqual(admission["status"], "ready")
        self.assertTrue(admission["ready"])
        self.assertFalse(admission["sourceParsingRequired"])
        self.assertFalse(admission["deviceExecutionRequired"])
        self.assertEqual(
            admission["nativeApiBoundary"]["boundary"],
            "directx.native-api.metadata-v0",
        )
        self.assertEqual(admission["nativeApiBoundary"]["decision"], "accepted")
        self.assertFalse(admission["nativeApiBoundary"]["d3dDeviceCreationPerformed"])
        self.assertEqual(admission["sourceInputs"], [])

    def test_cli_prints_vulkan_native_metadata_handoff(self) -> None:
        summary = self._run_cli_json(
            fixture_name="source-free-vulkan-native.cglb",
            loader_target="vulkan",
        )

        self.assertEqual(summary["schemaVersion"], 1)
        self.assertEqual(summary["loaderTarget"], "vulkan")
        self.assertEqual(summary["packageTarget"], "vulkan")
        self.assertEqual(summary["status"], "compatible")
        self._assert_cli_metadata_only_invariants(summary)
        self.assertEqual(summary["selectedArtifact"]["name"], "nativeBinary")
        self.assertEqual(
            summary["selectedArtifact"]["path"],
            "backend/vulkan/SourceFreeVulkanRuntimeExample.spv",
        )
        admission = summary["runtimeArtifactAdmission"]
        self.assertEqual(admission["decision"], "accepted")
        self.assertEqual(admission["target"]["decision"], "accepted")
        self.assertEqual(admission["native"]["decision"], "accepted")
        self.assertEqual(
            admission["sourcePackageFallback"]["decision"],
            "skipped",
        )
        self.assertNotIn("nativeBackendAdmission", summary)

    def test_cli_prints_opengl_source_package_metadata_handoff(self) -> None:
        summary = self._run_cli_json(
            fixture_name="source-free-opengl.cglb",
            loader_target="opengl",
        )

        self.assertEqual(summary["schemaVersion"], 1)
        self.assertEqual(summary["loaderTarget"], "opengl")
        self.assertEqual(summary["packageTarget"], "opengl")
        self.assertEqual(summary["status"], "source-only")
        self._assert_cli_metadata_only_invariants(summary)
        self.assertEqual(summary["selectedArtifact"]["name"], "backendSource")
        self.assertEqual(
            summary["selectedArtifact"]["path"],
            "backend/opengl/SourceFreeOpenGLRuntimeExample.comp.glsl",
        )
        admission = summary["runtimeArtifactAdmission"]
        self.assertEqual(admission["decision"], "accepted")
        self.assertEqual(admission["target"]["decision"], "accepted")
        self.assertEqual(admission["native"]["decision"], "skipped")
        self.assertEqual(admission["native"]["category"], "native-planned-only")
        self.assertEqual(
            admission["sourcePackageFallback"]["decision"],
            "accepted",
        )
        self.assertNotIn("nativeBackendAdmission", summary)

    def test_cli_native_admission_flag_prints_backend_summary(self) -> None:
        summary = self._run_cli_json(
            fixture_name="source-free-metal-native.cglb",
            loader_target="metal",
            native_admission=True,
        )

        admission = summary["nativeBackendAdmission"]
        self.assertEqual(admission["loader"], "metal-native")
        self.assertEqual(admission["decision"], "accepted")
        self.assertFalse(admission["sourceParsingRequired"])
        self.assertFalse(admission["deviceExecutionRequired"])

    def test_cli_native_admission_flag_prints_vulkan_backend_summary(self) -> None:
        summary = self._run_cli_json(
            fixture_name="source-free-vulkan-native.cglb",
            loader_target="vulkan",
            native_admission=True,
        )

        self._assert_cli_metadata_only_invariants(summary)
        admission = summary["nativeBackendAdmission"]
        self.assertEqual(admission["loader"], "vulkan-native")
        self.assertEqual(admission["decision"], "accepted")
        self.assertEqual(admission["status"], "ready")
        self.assertTrue(admission["ready"])
        self.assertFalse(admission["sourceParsingRequired"])
        self.assertFalse(admission["deviceExecutionRequired"])
        self.assertEqual(admission["nativeArtifact"]["name"], "nativeBinary")
        self.assertEqual(
            admission["nativeProfile"]["fields"]["target"],
            "vulkan",
        )
        self.assertEqual(
            admission["nativeApiBoundary"]["runtimeInputs"]["nativeProfile"][
                "nativeBinary"
            ],
            "backend/vulkan/SourceFreeVulkanRuntimeExample.spv",
        )
        self.assertTrue(
            admission["nativeApiBoundary"]["descriptorFreshness"][
                "artifactHashMatchesSpirv"
            ]
        )
        self.assertEqual(admission["sourceInputs"], [])

    def test_cli_native_admission_flag_prints_opengl_backend_rejection(
        self,
    ) -> None:
        summary = self._run_cli_json(
            fixture_name="source-free-opengl.cglb",
            loader_target="opengl",
            native_admission=True,
        )

        self._assert_cli_metadata_only_invariants(summary)
        admission = summary["nativeBackendAdmission"]
        self.assertEqual(admission["loader"], "opengl-native")
        self.assertEqual(admission["decision"], "rejected")
        self.assertEqual(admission["status"], "rejected")
        self.assertFalse(admission["ready"])
        self.assertFalse(admission["sourceParsingRequired"])
        self.assertFalse(admission["deviceExecutionRequired"])
        self.assertIsNone(admission["nativeArtifact"])
        self.assertEqual(admission["sourceInputs"], [])

    def test_native_admission_without_target_planner_is_structured_absence(
        self,
    ) -> None:
        package_dir = FIXTURE_ROOT / "source-free-directx.cglb"

        summary = inspect_source_free_package(
            package_dir,
            "cuda",
            native_admission=True,
        )

        admission = summary["nativeBackendAdmission"]
        self.assertFalse(summary["loadable"])
        self.assertFalse(admission["available"])
        self.assertEqual(admission["target"], "cuda")
        self.assertEqual(admission["decision"], "unavailable")
        self.assertEqual(admission["status"], "planner-unavailable")
        self.assertEqual(
            admission["reason"],
            "runtime.native_backend_loader.planner_unavailable",
        )
        self.assertFalse(admission["sourceParsingRequired"])
        self.assertFalse(admission["compilerInvocationRequired"])
        self.assertFalse(admission["deviceExecutionRequired"])

    def test_example_does_not_open_crossgl_source_paths(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            package_dir = Path(tmp_dir) / "source-free-directx.cglb"
            shutil.copytree(FIXTURE_ROOT / "source-free-directx.cglb", package_dir)
            (package_dir / "not-declared.cgl").write_text(
                "shader main {}\n", encoding="utf-8"
            )

            original_open = Path.open

            def guarded_open(path: Path, *args: object, **kwargs: object) -> object:
                if path.suffix == ".cgl":
                    self.fail(f"example opened CrossGL source path: {path}")
                return original_open(path, *args, **kwargs)

            with patch.object(Path, "open", guarded_open):
                summary = inspect_source_free_package(package_dir, "directx")

        self.assertTrue(summary["loadable"], summary["diagnostics"])
        self.assertTrue(summary["metadataOnly"])
        self.assertEqual(summary["sourceInputs"], [])
        self.assertFalse(summary["sourceParsingRequired"])

    def test_example_zip_does_not_open_crossgl_source_paths(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            temp_root = Path(tmp_dir)
            zip_path = temp_root / "source-free-directx.cglb"
            prefix = zip_path.name
            inside_source_member = f"{prefix}/source/not-declared.cgl"
            near_source_member = "near-zip-source.cgl"
            self._write_zip_package(
                FIXTURE_ROOT / "source-free-directx.cglb",
                zip_path,
                prefix=prefix,
                extra_members={
                    inside_source_member: "shader inside_zip_must_not_be_parsed {}\n",
                    near_source_member: "shader near_zip_must_not_be_parsed {}\n",
                },
            )
            near_source_path = temp_root / "near-source-free-directx.cgl"
            near_source_path.write_text(
                "shader near_filesystem_must_not_be_parsed {}\n",
                encoding="utf-8",
            )

            with zipfile.ZipFile(zip_path) as archive:
                archive_members = set(archive.namelist())
            self.assertIn(inside_source_member, archive_members)
            self.assertIn(near_source_member, archive_members)
            self.assertTrue(near_source_path.is_file())

            with self._guard_crossgl_source_path_opens():
                with self._guard_crossgl_source_archive_opens():
                    summary = inspect_source_free_package(zip_path, "directx")

        self.assertTrue(summary["loadable"], summary["diagnostics"])
        self.assertEqual(summary["status"], "source-only")
        self.assertTrue(summary["metadataOnly"])
        self.assertEqual(summary["sourceInputs"], [])
        self.assertFalse(summary["sourceParsingRequired"])

    def test_native_admission_zip_does_not_open_crossgl_source_paths(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            temp_root = Path(tmp_dir)
            zip_path = temp_root / "source-free-directx.cglb"
            prefix = zip_path.name
            self._write_zip_package(
                FIXTURE_ROOT / "source-free-directx.cglb",
                zip_path,
                prefix=prefix,
                extra_members={
                    f"{prefix}/source/not-declared.cgl": (
                        "shader inside_zip_must_not_be_parsed {}\n"
                    ),
                    "near-zip-source.cgl": ("shader near_zip_must_not_be_parsed {}\n"),
                },
            )
            near_source_path = temp_root / "near-source-free-directx.cgl"
            near_source_path.write_text(
                "shader near_filesystem_must_not_be_parsed {}\n",
                encoding="utf-8",
            )

            with self._guard_crossgl_source_path_opens():
                with self._guard_crossgl_source_archive_opens():
                    summary = inspect_source_free_package(
                        zip_path,
                        "directx",
                        native_admission=True,
                    )

        self.assertTrue(summary["loadable"], summary["diagnostics"])
        self.assertEqual(summary["status"], "source-only")
        self.assertEqual(
            summary["nativeBackendAdmission"]["decision"],
            "rejected",
        )
        self.assertEqual(summary["nativeBackendAdmission"]["sourceInputs"], [])

    def _assert_zip_package_matches_directory_fixture(
        self,
        *,
        fixture_name: str,
        loader_target: str,
    ) -> None:
        package_dir = FIXTURE_ROOT / fixture_name
        directory_summary = inspect_source_free_package(package_dir, loader_target)

        with tempfile.TemporaryDirectory() as tmp_dir:
            zip_path = Path(tmp_dir) / fixture_name
            self._write_zip_package(package_dir, zip_path, prefix=zip_path.name)

            zip_summary = inspect_source_free_package(zip_path, loader_target)

        self._assert_source_free_admission_invariants(zip_summary)
        self.assertEqual(
            directory_summary["runtimeArtifactHandoff"]["packageFormat"],
            "directory",
        )
        self.assertIsNone(
            directory_summary["runtimeArtifactHandoff"]["artifact"]["archivePath"]
        )
        self.assertIsNone(
            directory_summary["runtimeArtifactHandoff"]["artifact"]["archiveMember"]
        )
        self.assertEqual(
            zip_summary["runtimeArtifactHandoff"]["packageFormat"],
            "zip",
        )
        self.assertEqual(
            zip_summary["runtimeArtifactHandoff"]["artifact"]["archivePath"],
            str(zip_path),
        )
        self.assertEqual(
            zip_summary["runtimeArtifactHandoff"]["artifact"]["archiveMember"],
            f"{zip_path.name}/{zip_summary['selectedArtifact']['path']}",
        )
        self.assertEqual(
            self._normalize_package_location(directory_summary),
            self._normalize_package_location(zip_summary),
        )
        self.assertTrue(zip_summary["loadable"], zip_summary["diagnostics"])
        self.assertTrue(zip_summary["metadataOnly"])
        self.assertEqual(zip_summary["sourceInputs"], [])
        self.assertFalse(zip_summary["sourceParsingRequired"])

    def _write_zip_package(
        self,
        package_dir: Path,
        zip_path: Path,
        *,
        prefix: str | None = None,
        extra_members: dict[str, str | bytes] | None = None,
    ) -> None:
        with zipfile.ZipFile(zip_path, "w") as archive:
            for path in sorted(package_dir.rglob("*")):
                if not path.is_file():
                    continue
                member = path.relative_to(package_dir).as_posix()
                if prefix is not None:
                    member = f"{prefix}/{member}"
                archive.write(path, member)
            for member, payload in sorted((extra_members or {}).items()):
                archive.writestr(member, payload)

    def _normalize_package_location(self, summary: dict[str, Any]) -> dict[str, Any]:
        normalized = json.loads(json.dumps(summary, sort_keys=True))
        normalized["package"] = "<package>"
        self._normalize_artifact_location(normalized["selectedArtifact"])
        for artifact in normalized["selectedArtifacts"]:
            self._normalize_artifact_location(artifact)
        self._normalize_handoff_location(normalized["runtimeArtifactHandoff"])
        return normalized

    def _normalize_artifact_location(self, artifact: dict[str, Any] | None) -> None:
        if artifact is not None:
            artifact["absolutePath"] = "<artifact>"

    def _normalize_handoff_location(self, handoff: dict[str, Any] | None) -> None:
        if handoff is None:
            return
        handoff["packageFormat"] = "<package-format>"
        artifact = handoff["artifact"]
        artifact["absolutePath"] = "<artifact>"
        artifact["archivePath"] = "<archive>"
        artifact["archiveMember"] = "<archive-member>"
        self._normalize_absolute_paths(handoff["metadata"])

    def _normalize_absolute_paths(self, value: Any) -> None:
        if isinstance(value, dict):
            if "absolutePath" in value:
                value["absolutePath"] = "<artifact>"
            for child in value.values():
                self._normalize_absolute_paths(child)
        elif isinstance(value, list):
            for child in value:
                self._normalize_absolute_paths(child)

    def _assert_source_free_admission_invariants(self, summary: dict[str, Any]) -> None:
        self._assert_runtime_artifact_handoff_invariants(summary)
        self.assertEqual(
            summary["runtimeArtifactAdmission"]["packageArtifactRequirementsSource"],
            summary["packageArtifactRequirementsSource"],
        )
        self.assertEqual(
            summary["runtimeArtifactAdmission"]["packageArtifactRequirements"],
            summary["packageArtifactRequirements"],
        )
        if "nativeBackendAdmission" in summary:
            self.assertEqual(
                summary["nativeBackendAdmission"]["packageArtifactRequirementsSource"],
                summary["packageArtifactRequirementsSource"],
            )
            self.assertEqual(
                summary["nativeBackendAdmission"]["packageArtifactRequirements"],
                summary["packageArtifactRequirements"],
            )
            for key in (
                "nativeAdmission",
                "targetNativeAdmission",
                "nativeApiBoundary",
            ):
                section = summary["nativeBackendAdmission"].get(key)
                if section is None:
                    continue
                self.assertEqual(
                    section["packageArtifactRequirementsSource"],
                    summary["packageArtifactRequirementsSource"],
                )
                self.assertEqual(
                    section["packageArtifactRequirements"],
                    summary["packageArtifactRequirements"],
                )
        self.assertEqual(
            summary["runtimeArtifactAdmission"]["targetLegalizationEvidence"],
            summary["targetLegalizationEvidence"],
        )
        self.assertEqual(
            summary["runtimeArtifactAdmission"]["sourceFreeInvariants"],
            {
                "metadataOnly": True,
                "sourceInputs": [],
                "sourceParsingRequired": False,
                "compilerInvocationRequired": False,
                "deviceExecutionRequired": False,
                "deviceExecution": "not-executed",
            },
        )

    def _assert_runtime_artifact_handoff_invariants(
        self,
        summary: dict[str, Any],
    ) -> None:
        handoff = summary["runtimeArtifactHandoff"]
        if not summary["loadable"]:
            self.assertIsNone(handoff)
            return

        self.assertIsNotNone(handoff)
        selected_artifact = summary["selectedArtifact"]
        admission_artifact = summary["runtimeArtifactAdmission"]["selectedArtifact"]
        self.assertIsNotNone(selected_artifact)
        self.assertIsNotNone(admission_artifact)

        artifact = handoff["artifact"]
        self.assertEqual(handoff["schemaVersion"], 1)
        self.assertIn(handoff["packageFormat"], {"directory", "zip"})
        self.assertFalse(handoff["sourceParsingRequired"])
        self.assertFalse(handoff["compilerInvocationRequired"])
        self.assertFalse(handoff["deviceExecutionRequired"])
        self.assertGreater(handoff["byteLength"], 0)
        if artifact["size"] is not None:
            self.assertEqual(handoff["byteLength"], artifact["size"])

        self.assertEqual(artifact["name"], selected_artifact["name"])
        self.assertEqual(artifact["path"], selected_artifact["path"])
        self.assertEqual(artifact["size"], selected_artifact["size"])
        self.assertEqual(artifact["name"], admission_artifact["name"])
        self.assertEqual(artifact["path"], admission_artifact["path"])
        self.assertEqual(
            handoff["selectedPackageMode"],
            admission_artifact["selectedPackageMode"],
        )

        metadata = handoff["metadata"]
        self.assertTrue(metadata["metadataOnly"])
        self.assertEqual(metadata["sourceInputs"], [])
        self.assertFalse(metadata["sourceParsingRequired"])
        self.assertFalse(metadata["compilerInvocationRequired"])
        self.assertFalse(metadata["deviceExecutionRequired"])
        self.assertEqual(metadata["runtimeArtifact"]["name"], artifact["name"])
        self.assertEqual(metadata["runtimeArtifact"]["path"], artifact["path"])

    def _run_cli_json(
        self,
        *,
        fixture_name: str,
        loader_target: str,
        native_admission: bool = False,
    ) -> dict[str, Any]:
        args = [
            sys.executable,
            "-m",
            "runtime.examples.source_free_loader",
            str(FIXTURE_ROOT / fixture_name),
            loader_target,
            "--json",
        ]
        if native_admission:
            args.append("--native-admission")

        result = subprocess.run(
            args,
            cwd=REPO_ROOT,
            check=False,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stderr, "")
        return json.loads(result.stdout)

    def _assert_cli_metadata_only_invariants(self, summary: dict[str, Any]) -> None:
        self.assertEqual(summary["deviceExecution"], "not-executed")
        self.assertTrue(summary["metadataOnly"])
        self.assertEqual(summary["sourceInputs"], [])
        self.assertFalse(summary["sourceParsingRequired"])
        self.assertFalse(summary["compilerInvocationRequired"])
        self.assertFalse(summary["deviceExecutionRequired"])
        self._assert_source_free_admission_invariants(summary)

    def _guard_crossgl_source_path_opens(self) -> object:
        original_open = Path.open

        def guarded_open(path: Path, *args: object, **kwargs: object) -> object:
            if path.suffix == ".cgl":
                raise AssertionError(f"example opened CrossGL source path: {path}")
            return original_open(path, *args, **kwargs)

        return patch.object(Path, "open", guarded_open)

    def _guard_crossgl_source_archive_opens(self) -> object:
        original_open = zipfile.ZipFile.open
        original_read = zipfile.ZipFile.read

        def member_name(name: object) -> str:
            return str(getattr(name, "filename", name))

        def guarded_open(
            archive: zipfile.ZipFile,
            name: object,
            *args: object,
            **kwargs: object,
        ) -> object:
            member = member_name(name)
            if Path(member).suffix == ".cgl":
                raise AssertionError(
                    f"example opened CrossGL source archive member: {member}"
                )
            return original_open(archive, name, *args, **kwargs)

        def guarded_read(
            archive: zipfile.ZipFile,
            name: object,
            *args: object,
            **kwargs: object,
        ) -> object:
            member = member_name(name)
            if Path(member).suffix == ".cgl":
                raise AssertionError(
                    f"example opened CrossGL source archive member: {member}"
                )
            return original_read(archive, name, *args, **kwargs)

        return patch.multiple(
            zipfile.ZipFile,
            open=guarded_open,
            read=guarded_read,
        )


if __name__ == "__main__":
    unittest.main()
