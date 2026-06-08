#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock
import zipfile


REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))


DIRECTX_FIXTURE_HLSL_BYTES = b"// generated HLSL\n"


from runtime.directx_loader import (  # noqa: E402
    plan_directx_loader,
    plan_directx_native_loader,
    plan_directx_source_package_loader,
)
from runtime.package_reader import PackageReadError  # noqa: E402


class DirectXNativeLoaderPlanTests(unittest.TestCase):
    def test_ready_plan_uses_native_artifact_without_source_parse(self) -> None:
        with tempfile.TemporaryDirectory(suffix=".cglb") as temp_dir:
            package_dir = Path(temp_dir)
            self._write_valid_directx_package(package_dir)
            source_path = package_dir / "source" / "invalid.cgl"
            source_path.parent.mkdir()
            source_path.write_text("must not parse source\n", encoding="utf-8")

            with self._guard_source_reads():
                plan = plan_directx_native_loader(package_dir)
                summary = plan.to_summary()

            self.assertTrue(plan.ready, summary["diagnostics"])
            self.assertIs(plan.require_ready(), plan)
            self.assertEqual(plan.status, "ready")
            self.assertFalse(plan.source_parsing_required)
            self.assertFalse(plan.device_execution_required)
            self.assertEqual(summary["loader"], "directx-native")
            self.assertEqual(summary["target"], "directx")
            self.assertEqual(summary["sourceInputs"], [])
            self.assertEqual(summary["compilerInvocationRequired"], False)
            self.assertEqual(summary["deviceExecutionRequired"], False)
            self.assertEqual(plan.native_artifact.name, "nativeBinary")
            self.assertEqual(
                plan.native_artifact.package_path,
                "backend/directx/RuntimeDirectXLoaderFixture.dxil",
            )
            self.assertEqual(
                summary["runtimePlan"]["runtimeArtifactSelection"][
                    "selectedPackageMode"
                ],
                "native",
            )
            self.assertEqual(
                summary["targetLegalizationEvidence"],
                summary["runtimePlan"]["targetLegalizationEvidence"],
            )
            self.assertEqual(
                summary["targetLegalizationToolRequirements"],
                summary["runtimePlan"]["targetLegalizationToolRequirements"],
            )
            self.assertEqual(
                summary["nativeAdmission"]["targetLegalizationEvidence"],
                summary["targetLegalizationEvidence"],
            )
            self.assertEqual(
                summary["nativeAdmission"]["targetLegalizationToolRequirements"],
                summary["targetLegalizationToolRequirements"],
            )
            self.assertEqual(summary["reflection"]["entryPointCount"], 1)
            self.assertEqual(summary["reflection"]["resourceCount"], 1)
            self.assertEqual(summary["reflection"]["targetResourceBindingCount"], 1)
            self.assertEqual(
                summary["reflection"]["targetResourceBindings"][0]["abi"],
                {"space": 0, "register": "u0"},
            )
            api_boundary = summary["directxNativeApiBoundary"]
            self.assertEqual(
                api_boundary["boundary"],
                "directx.native-api.metadata-v0",
            )
            self.assertEqual(api_boundary["decision"], "accepted")
            self.assertEqual(
                api_boundary["targetLegalizationEvidence"],
                summary["targetLegalizationEvidence"],
            )
            self.assertEqual(
                api_boundary["targetLegalizationToolRequirements"],
                summary["targetLegalizationToolRequirements"],
            )
            self.assertEqual(
                api_boundary["packageArtifactRequirementsSource"],
                summary["packageArtifactRequirementsSource"],
            )
            self.assertEqual(
                api_boundary["packageArtifactRequirements"],
                summary["packageArtifactRequirements"],
            )
            self.assertFalse(api_boundary["d3dRuntimeCallsPerformed"])
            self.assertFalse(api_boundary["d3dDeviceCreationPerformed"])
            self.assertFalse(api_boundary["d3dShaderModuleCreationPerformed"])
            self.assertFalse(api_boundary["d3dPipelineCreationPerformed"])
            self.assertFalse(api_boundary["d3dCommandExecutionPerformed"])
            self.assertEqual(
                api_boundary["runtimeInputs"]["nativeBinaryArtifact"][
                    "nativeBinaryStatus"
                ],
                "emitted",
            )
            self.assertEqual(
                api_boundary["runtimeInputs"]["dxilArtifact"]["path"],
                "backend/directx/RuntimeDirectXLoaderFixture.dxil",
            )
            self.assertFalse(
                api_boundary["runtimeInputs"]["dxbcArtifact"]["actualBinaryKindMatches"]
            )
            self.assertTrue(
                api_boundary["runtimeInputs"]["versionCompatibility"]["compatible"]
            )
            self.assertEqual(
                api_boundary["runtimeInputs"]["reflection"][
                    "hlslRegisterSpaceBindings"
                ][0],
                {
                    "stage": "compute",
                    "entryPoint": "runtime_directx_loader_main",
                    "name": "OutputBuffer",
                    "kind": "storageBuffer",
                    "register": "u0",
                    "space": 0,
                    "bindingClass": "uav",
                    "descriptorType": "UAV",
                    "hlslType": "RWStructuredBuffer<float4>",
                },
            )
            self.assertEqual(summary["rejectReasons"], [])
            self.assertEqual(list(package_dir.rglob("*.cgl")), [source_path])

    def test_native_api_boundary_preserves_storage_image_metadata_without_source_parse(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory(suffix=".cglb") as temp_dir:
            package_dir = Path(temp_dir)
            self._write_valid_directx_package(package_dir)
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
                    "set": 1,
                    "binding": 4,
                    **storage_metadata,
                }
            )
            reflection["targetResourceBindings"][0].update(
                {
                    "name": "OutputImage",
                    "kind": "storageImage",
                    "sourceType": "RWTexture2D<float4>",
                    "addressSpace": "uav",
                    "abi": {"space": 1, "register": "u4"},
                    "set": 1,
                    "binding": 4,
                    "bindingClass": "uav",
                    "descriptorType": "UAV",
                    "hlslType": "RWTexture2D<float4>",
                    **storage_metadata,
                }
            )
            self._write_json(reflection_path, reflection)
            source_path = package_dir / "source" / "invalid.cgl"
            source_path.parent.mkdir()
            source_path.write_text(
                "native loader must not parse source for storage image metadata\n",
                encoding="utf-8",
            )

            with self._guard_source_reads():
                plan = plan_directx_native_loader(package_dir)
                summary = plan.to_summary()

            api_reflection = summary["directxNativeApiBoundary"]["runtimeInputs"][
                "reflection"
            ]
            resource = api_reflection["resources"][0]
            target_binding = api_reflection["targetResourceBindings"][0]
            register_binding = api_reflection["hlslRegisterSpaceBindings"][0]

            self.assertTrue(plan.ready, summary["diagnostics"])
            self.assertEqual(resource["storageImageFormat"], "rgba8")
            self.assertEqual(resource["storageImageAccess"], "read_write")
            self.assertEqual(target_binding["storageImageFormat"], "rgba8")
            self.assertEqual(target_binding["storageImageAccess"], "read_write")
            self.assertEqual(register_binding["storageImageFormat"], "rgba8")
            self.assertEqual(register_binding["storageImageAccess"], "read_write")
            self.assertEqual(list(package_dir.rglob("*.cgl")), [source_path])

    def test_source_free_plan_uses_manifest_dxil_descriptor_and_ignores_legacy_path(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory(suffix=".cglb") as temp_dir:
            package_dir = Path(temp_dir)
            descriptor_path = (
                "backend/directx/RuntimeDirectXLoaderFixture.native-artifact.json"
            )
            native_path = "backend/directx/RuntimeDirectXLoaderFixture.dxil"
            self._write_source_free_directx_package(
                package_dir,
                descriptor_path=descriptor_path,
            )
            source_path = package_dir / "source" / "RuntimeDirectXLoaderFixture.cgl"
            source_path.parent.mkdir()
            source_path.write_text(
                "DirectX source-free native packages must not parse source\n",
                encoding="utf-8",
            )
            legacy_descriptor_path = package_dir / "metadata" / "native-artifact.json"
            legacy_descriptor_path.parent.mkdir()
            legacy_descriptor_path.write_text(
                '{"target": "vulkan", "binaryKind": "vulkan.spirv-module"}\n',
                encoding="utf-8",
            )

            with self._guard_crossgl_source_reads(
                forbidden_paths={legacy_descriptor_path},
            ):
                plan = plan_directx_native_loader(package_dir)
                summary = plan.to_summary()

            descriptor_summary = summary["nativeArtifactDescriptor"]
            self.assertTrue(plan.ready, summary["diagnostics"])
            self.assertEqual(summary["sourceInputs"], [])
            self.assertEqual(
                summary["runtimePlan"]["metadataContract"]["sourceInputs"],
                [],
            )
            self.assertEqual(
                summary["runtimePlan"]["requiredArtifacts"],
                ["nativeBinary"],
            )
            self.assertEqual(
                [
                    (artifact["name"], artifact["path"])
                    for artifact in summary["artifactInputs"]
                ],
                [("nativeBinary", native_path)],
            )
            self.assertEqual(summary["nativeArtifact"]["path"], native_path)
            api_boundary = summary["directxNativeApiBoundary"]
            descriptor_input = api_boundary["runtimeInputs"]["nativeArtifactDescriptor"]
            self.assertEqual(
                api_boundary["runtimeInputs"]["nativeBinaryArtifact"]["binaryKind"],
                "directx.dxil",
            )
            self.assertIsNone(
                api_boundary["runtimeInputs"]["nativeBinaryArtifact"][
                    "nativeBinaryStatus"
                ]
            )
            self.assertEqual(descriptor_input["fields"]["binaryKind"], "directx.dxil")
            self.assertEqual(descriptor_input["fields"]["artifactPath"], native_path)
            self.assertTrue(descriptor_input["schemaVersionCompatible"])
            self.assertTrue(descriptor_input["contractVersionCompatible"])
            self.assertTrue(descriptor_input["targetMatchesLoader"])
            self.assertTrue(descriptor_input["artifactPathMatchesNativeBinary"])
            self.assertTrue(descriptor_input["artifactHashMatchesNativeBinary"])
            self.assertTrue(descriptor_input["sizeBytesMatchesNativeBinary"])
            self.assertTrue(descriptor_input["nativeBinaryStatusMatchesManifest"])
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
            self._assert_source_free_directx_descriptor_summary(
                descriptor_summary,
                descriptor_path=descriptor_path,
                native_path=native_path,
            )
            self.assertEqual(summary["rejectReasons"], [])
            self.assertEqual(list(package_dir.rglob("*.cgl")), [source_path])

    def test_source_free_plan_accepts_dxbc_descriptor_and_suffix_without_source_parse(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory(suffix=".cglb") as temp_dir:
            package_dir = Path(temp_dir)
            descriptor_path = (
                "backend/directx/RuntimeDirectXLoaderFixture.native-artifact.json"
            )
            native_path = "backend/directx/RuntimeDirectXLoaderFixture.dxbc"
            self._write_source_free_directx_package(
                package_dir,
                descriptor_path=descriptor_path,
                descriptor_binary_kind="directx.dxbc",
                native_path=native_path,
                native_bytes=b"DXBC",
            )
            source_path = package_dir / "source" / "RuntimeDirectXLoaderFixture.cgl"
            source_path.parent.mkdir()
            source_path.write_text(
                "DirectX DXBC source-free native packages must not parse source\n",
                encoding="utf-8",
            )

            with self._guard_crossgl_source_reads():
                plan = plan_directx_native_loader(package_dir)
                summary = plan.to_summary()

            descriptor_summary = summary["nativeArtifactDescriptor"]
            descriptor_admission = summary["nativeAdmission"][
                "nativeArtifactDescriptor"
            ]
            self.assertTrue(plan.ready, summary["diagnostics"])
            self.assertEqual(summary["sourceInputs"], [])
            self.assertEqual(summary["nativeArtifact"]["path"], native_path)
            self.assertEqual(
                summary["runtimePlan"]["runtimeArtifactSelection"]["artifact"]["path"],
                native_path,
            )
            self.assertEqual(
                descriptor_summary["fields"]["binaryKind"],
                "directx.dxbc",
            )
            self.assertEqual(
                descriptor_summary["fields"]["artifactPath"],
                native_path,
            )
            api_boundary = summary["directxNativeApiBoundary"]
            self.assertEqual(
                api_boundary["runtimeInputs"]["nativeBinaryArtifact"]["binaryKind"],
                "directx.dxbc",
            )
            self.assertEqual(
                api_boundary["runtimeInputs"]["dxbcArtifact"]["path"],
                native_path,
            )
            self.assertTrue(
                api_boundary["runtimeInputs"]["dxbcArtifact"]["actualBinaryKindMatches"]
            )
            self.assertFalse(
                api_boundary["runtimeInputs"]["dxilArtifact"]["actualBinaryKindMatches"]
            )
            self.assertTrue(
                api_boundary["descriptorFreshness"]["artifactPathMatchesDxbc"]
            )
            self.assertFalse(
                api_boundary["descriptorFreshness"]["artifactPathMatchesDxil"]
            )
            self.assertEqual(
                descriptor_summary["expectedBinaryKinds"],
                ["directx.dxil", "directx.dxbc"],
            )
            self.assertTrue(descriptor_summary["binaryKindMatchesLoader"])
            self.assertEqual(descriptor_admission["decision"], "accepted")
            self.assertEqual(descriptor_admission["binaryKind"], "directx.dxbc")
            self.assertTrue(descriptor_admission["binaryKindMatchesLoader"])
            self.assertEqual(summary["rejectReasons"], [])
            self.assertEqual(list(package_dir.rglob("*.cgl")), [source_path])

    def test_native_loader_rejects_dxil_descriptor_with_non_dxil_artifact_path(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory(suffix=".cglb") as temp_dir:
            package_dir = Path(temp_dir)
            descriptor_path = (
                "backend/directx/RuntimeDirectXLoaderFixture.native-artifact.json"
            )
            native_path = "backend/directx/RuntimeDirectXLoaderFixture.bin"
            self._write_source_free_directx_package(
                package_dir,
                descriptor_path=descriptor_path,
                native_path=native_path,
                native_bytes=b"DXIL",
            )
            source_path = package_dir / "source" / "RuntimeDirectXLoaderFixture.cgl"
            source_path.parent.mkdir()
            source_path.write_text(
                "DirectX native suffix rejection must not parse source\n",
                encoding="utf-8",
            )

            with self._guard_crossgl_source_reads():
                plan = plan_directx_native_loader(package_dir)
                summary = plan.to_summary()

            reject_codes = [
                diagnostic["code"] for diagnostic in summary["rejectReasons"]
            ]
            self.assertFalse(plan.ready)
            self.assertFalse(plan.loadable)
            self.assertIsNone(plan.native_artifact)
            self.assertIsNone(summary["nativeArtifact"])
            self.assertEqual(summary["sourceInputs"], [])
            self.assertEqual(
                summary["runtimePlan"]["metadataContract"]["sourceInputs"],
                [],
            )
            self.assertIn(
                "directx_loader.native_artifact_path_suffix_mismatch",
                reject_codes,
            )
            self.assertIn(
                "directx_loader."
                "native_artifact_descriptor_artifact_path_suffix_mismatch",
                reject_codes,
            )
            with self.assertRaisesRegex(PackageReadError, r"\.dxil"):
                plan.require_ready()
            self.assertEqual(list(package_dir.rglob("*.cgl")), [source_path])

    def test_descriptor_binary_kind_mismatch_rejects_source_free_plan(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory(suffix=".cglb") as temp_dir:
            package_dir = Path(temp_dir)
            descriptor_path = (
                "backend/directx/RuntimeDirectXLoaderFixture.native-artifact.json"
            )
            self._write_source_free_directx_package(
                package_dir,
                descriptor_path=descriptor_path,
                descriptor_binary_kind="metal.metallib",
            )
            source_path = package_dir / "source" / "RuntimeDirectXLoaderFixture.cgl"
            source_path.parent.mkdir()
            source_path.write_text(
                "DirectX descriptor kind rejection must not parse source\n",
                encoding="utf-8",
            )

            with self._guard_crossgl_source_reads():
                plan = plan_directx_native_loader(package_dir)
                summary = plan.to_summary()

            descriptor_summary = summary["nativeArtifactDescriptor"]
            reject_codes = [
                diagnostic["code"] for diagnostic in summary["rejectReasons"]
            ]
            self.assertFalse(plan.ready)
            self.assertFalse(plan.loadable)
            self.assertIsNone(plan.native_artifact)
            self.assertIsNone(summary["nativeArtifact"])
            self.assertEqual(summary["sourceInputs"], [])
            self.assertIsNotNone(descriptor_summary)
            self.assertTrue(descriptor_summary["readable"])
            self.assertEqual(
                descriptor_summary["fields"]["binaryKind"],
                "metal.metallib",
            )
            self.assertEqual(
                descriptor_summary["expectedBinaryKinds"],
                ["directx.dxil", "directx.dxbc"],
            )
            self.assertFalse(descriptor_summary["binaryKindMatchesLoader"])
            self.assertIn(
                "package.native_artifact_descriptor.binary_kind_mismatch",
                reject_codes,
            )
            descriptor_reject = next(
                diagnostic
                for diagnostic in summary["rejectReasons"]
                if diagnostic["code"]
                == "package.native_artifact_descriptor.binary_kind_mismatch"
            )
            self.assertEqual(descriptor_reject["document"], "nativeArtifactDescriptor")
            self.assertEqual(descriptor_reject["artifact"], "nativeArtifactDescriptor")
            self.assertEqual(descriptor_reject["path"], "binaryKind")
            self.assertEqual(
                descriptor_reject["expected"],
                ["directx.dxil", "directx.dxbc"],
            )
            self.assertEqual(descriptor_reject["actual"], "metal.metallib")
            with self.assertRaisesRegex(PackageReadError, "binaryKind"):
                plan.require_ready()
            self.assertEqual(list(package_dir.rglob("*.cgl")), [source_path])

    def test_ready_zip_plan_uses_native_artifact_and_descriptor_without_source_parse(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir)
            package_dir = temp_root / "package-dir"
            package_dir.mkdir()
            descriptor_path = (
                "backend/directx/RuntimeDirectXLoaderFixture.native-artifact.json"
            )
            native_path = "backend/directx/RuntimeDirectXLoaderFixture.dxil"
            self._write_source_free_directx_package(
                package_dir,
                descriptor_path=descriptor_path,
            )
            source_path = package_dir / "source" / "RuntimeDirectXLoaderFixture.cgl"
            source_path.parent.mkdir()
            source_path.write_text(
                "zip loader must not parse source\n", encoding="utf-8"
            )
            zip_path = temp_root / "RuntimeDirectXLoaderFixture.cglb"
            self._write_zip_package(
                package_dir,
                zip_path,
                prefix=zip_path.name,
            )

            with (
                self._guard_crossgl_source_reads(),
                self._guard_crossgl_source_archive_reads(),
            ):
                plan = plan_directx_native_loader(zip_path)
                summary = plan.to_summary()

            descriptor_summary = summary["nativeArtifactDescriptor"]
            self.assertTrue(plan.ready, summary["diagnostics"])
            self.assertIs(plan.require_ready(), plan)
            self.assertFalse(plan.source_parsing_required)
            self.assertFalse(plan.device_execution_required)
            self.assertEqual(summary["runtimePlan"]["packageFormat"], "zip")
            self.assertEqual(summary["sourceInputs"], [])
            self.assertEqual(summary["compilerInvocationRequired"], False)
            self.assertEqual(summary["deviceExecutionRequired"], False)
            self.assertEqual(summary["rejectReasons"], [])
            self.assertEqual(
                summary["nativeAdmission"]["packageArtifactRequirementsSource"],
                summary["packageArtifactRequirementsSource"],
            )
            self.assertEqual(
                summary["nativeAdmission"]["packageArtifactRequirements"],
                summary["packageArtifactRequirements"],
            )
            self.assertIsNotNone(plan.native_artifact)
            self.assertEqual(plan.native_artifact.archive_path, zip_path)
            self.assertEqual(
                plan.native_artifact.archive_member,
                f"{zip_path.name}/{native_path}",
            )
            self.assertTrue(
                summary["nativeArtifact"]["absolutePath"].startswith(f"{zip_path}!/")
            )
            self.assertEqual(summary["nativeArtifact"]["path"], native_path)
            self._assert_source_free_directx_descriptor_summary(
                descriptor_summary,
                descriptor_path=descriptor_path,
                native_path=native_path,
                absolute_path_prefix=f"{zip_path}!/",
            )

    def test_ready_zip_dxil_plan_reports_native_api_boundary_admission(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir)
            package_dir = temp_root / "package-dir"
            package_dir.mkdir()
            descriptor_path = (
                "backend/directx/RuntimeDirectXLoaderFixture.native-artifact.json"
            )
            native_path = "backend/directx/RuntimeDirectXLoaderFixture.dxil"
            native_bytes = b"DXIL"
            self._write_source_free_directx_package(
                package_dir,
                descriptor_path=descriptor_path,
                native_path=native_path,
                native_bytes=native_bytes,
            )
            source_path = package_dir / "source" / "RuntimeDirectXLoaderFixture.cgl"
            source_path.parent.mkdir()
            source_path.write_text(
                "zip DXIL native admission must not parse source\n",
                encoding="utf-8",
            )
            zip_path = temp_root / "RuntimeDirectXLoaderFixture.cglb"
            self._write_zip_package(
                package_dir,
                zip_path,
                prefix=zip_path.name,
            )

            with (
                self._guard_crossgl_source_reads(),
                self._guard_crossgl_source_archive_reads(),
            ):
                plan = plan_directx_native_loader(zip_path)
                summary = plan.to_summary()

            self.assertTrue(plan.ready, summary["diagnostics"])
            self.assertEqual(summary["runtimePlan"]["packageFormat"], "zip")
            self.assertEqual(summary["sourceInputs"], [])
            self.assertEqual(summary["compilerInvocationRequired"], False)
            self.assertEqual(summary["deviceExecutionRequired"], False)
            self.assertEqual(summary["rejectReasons"], [])
            self.assertIsNotNone(plan.native_artifact)
            self.assertEqual(plan.native_artifact.archive_path, zip_path)
            self.assertEqual(
                plan.native_artifact.archive_member,
                f"{zip_path.name}/{native_path}",
            )

            api_boundary = summary["directxNativeApiBoundary"]
            runtime_inputs = api_boundary["runtimeInputs"]
            native_binary = runtime_inputs["nativeBinaryArtifact"]
            dxil_artifact = runtime_inputs["dxilArtifact"]
            dxbc_artifact = runtime_inputs["dxbcArtifact"]
            descriptor_input = runtime_inputs["nativeArtifactDescriptor"]
            freshness = api_boundary["descriptorFreshness"]
            expected_hash = self._sha256(native_bytes)

            self.assertEqual(api_boundary["boundary"], "directx.native-api.metadata-v0")
            self.assertEqual(api_boundary["decision"], "accepted")
            self.assertEqual(api_boundary["status"], "ready")
            self.assertEqual(
                api_boundary["reason"],
                "directx_loader.native_api_boundary.accepted",
            )
            self.assertEqual(api_boundary["loaderTarget"], "directx")
            self.assertEqual(api_boundary["packageTarget"], "directx")
            self.assertFalse(api_boundary["sourceParsingRequired"])
            self.assertEqual(api_boundary["sourceInputs"], [])
            self.assertFalse(api_boundary["compilerInvocationRequired"])
            self.assertFalse(api_boundary["deviceExecutionRequired"])
            self.assertFalse(api_boundary["d3dRuntimeCallsPerformed"])
            self.assertFalse(api_boundary["d3dDeviceCreationPerformed"])
            self.assertFalse(api_boundary["d3dShaderModuleCreationPerformed"])
            self.assertFalse(api_boundary["d3dPipelineCreationPerformed"])
            self.assertFalse(api_boundary["d3dCommandExecutionPerformed"])
            self.assertEqual(api_boundary["blockedByDiagnostics"], [])
            self.assertEqual(
                api_boundary["targetLegalizationEvidence"],
                summary["targetLegalizationEvidence"],
            )
            self.assertEqual(
                api_boundary["targetLegalizationToolRequirements"],
                summary["targetLegalizationToolRequirements"],
            )
            self.assertEqual(
                api_boundary["packageArtifactRequirementsSource"],
                summary["packageArtifactRequirementsSource"],
            )
            self.assertEqual(
                api_boundary["packageArtifactRequirements"],
                summary["packageArtifactRequirements"],
            )

            self.assertEqual(native_binary["path"], native_path)
            self.assertTrue(native_binary["exists"])
            self.assertTrue(native_binary["acceptedForLoad"])
            self.assertEqual(native_binary["sizeBytes"], len(native_bytes))
            self.assertEqual(native_binary["binaryKind"], "directx.dxil")
            self.assertEqual(
                native_binary["binaryKindSource"],
                "nativeArtifactDescriptor.binaryKind",
            )
            self.assertEqual(native_binary["expectedBinaryKind"], "directx.dxil")
            self.assertEqual(
                native_binary["expectedBinaryKinds"],
                ["directx.dxil", "directx.dxbc"],
            )
            self.assertEqual(native_binary["pathSuffix"], ".dxil")
            self.assertTrue(native_binary["pathSuffixMatchesExpected"])
            self.assertEqual(native_binary["descriptorArtifactPath"], native_path)
            self.assertEqual(native_binary["descriptorArtifactHash"], expected_hash)
            self.assertTrue(native_binary["descriptorArtifactHashMatchesNativeBinary"])
            self.assertTrue(native_binary["absolutePath"].startswith(f"{zip_path}!/"))

            self.assertEqual(dxil_artifact["path"], native_path)
            self.assertTrue(dxil_artifact["declared"])
            self.assertTrue(dxil_artifact["exists"])
            self.assertTrue(dxil_artifact["acceptedForLoad"])
            self.assertEqual(dxil_artifact["actualBinaryKind"], "directx.dxil")
            self.assertTrue(dxil_artifact["actualBinaryKindMatches"])
            self.assertEqual(dxil_artifact["sizeBytes"], len(native_bytes))
            self.assertEqual(dxil_artifact["pathSuffix"], ".dxil")
            self.assertTrue(dxil_artifact["pathSuffixMatchesExpected"])
            self.assertIsNone(dxbc_artifact["path"])
            self.assertFalse(dxbc_artifact["declared"])
            self.assertFalse(dxbc_artifact["exists"])
            self.assertFalse(dxbc_artifact["acceptedForLoad"])
            self.assertEqual(dxbc_artifact["actualBinaryKind"], "directx.dxil")
            self.assertFalse(dxbc_artifact["actualBinaryKindMatches"])

            self.assertTrue(descriptor_input["declared"])
            self.assertTrue(descriptor_input["readable"])
            self.assertEqual(descriptor_input["artifact"]["path"], descriptor_path)
            self.assertEqual(descriptor_input["target"], "directx")
            self.assertTrue(descriptor_input["targetMatchesLoader"])
            self.assertEqual(descriptor_input["binaryKind"], "directx.dxil")
            self.assertTrue(descriptor_input["binaryKindMatchesLoader"])
            self.assertEqual(descriptor_input["artifactPath"], native_path)
            self.assertTrue(descriptor_input["artifactPathMatchesNativeBinary"])
            self.assertTrue(descriptor_input["artifactPathMatchesDxilOrDxbc"])
            self.assertEqual(descriptor_input["artifactHash"], expected_hash)
            self.assertTrue(descriptor_input["artifactHashMatchesNativeBinary"])
            self.assertEqual(descriptor_input["sizeBytes"], len(native_bytes))
            self.assertTrue(descriptor_input["sizeBytesMatchesNativeBinary"])
            self.assertIsNone(descriptor_input["nativeBinaryStatus"])
            self.assertTrue(descriptor_input["nativeBinaryStatusMatchesManifest"])
            self.assertTrue(descriptor_input["sourcePathDeclared"])
            self.assertFalse(descriptor_input["sourcePathExposed"])
            self.assertEqual(descriptor_input["diagnostics"], [])

            self.assertTrue(freshness["artifactPathMatchesNativeBinary"])
            self.assertTrue(freshness["artifactPathMatchesDxil"])
            self.assertFalse(freshness["artifactPathMatchesDxbc"])
            self.assertTrue(freshness["artifactPathMatchesDxilOrDxbc"])
            self.assertTrue(freshness["artifactHashDeclared"])
            self.assertTrue(freshness["artifactHashMatchesNativeBinary"])
            self.assertTrue(freshness["sizeBytesMatchesNativeBinary"])
            self.assertTrue(freshness["nativeBinaryStatusMatchesManifest"])
            self.assertEqual(freshness["failClosedDiagnosticCodes"], [])
            self.assertEqual(list(package_dir.rglob("*.cgl")), [source_path])

    def test_rejects_zip_missing_native_artifact_without_source_parse(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir)
            package_dir = temp_root / "package-dir"
            package_dir.mkdir()
            descriptor_path = (
                "backend/directx/RuntimeDirectXLoaderFixture.native-artifact.json"
            )
            native_path = "backend/directx/RuntimeDirectXLoaderFixture.dxil"
            self._write_source_free_directx_package(
                package_dir,
                descriptor_path=descriptor_path,
            )
            source_path = package_dir / "source" / "RuntimeDirectXLoaderFixture.cgl"
            source_path.parent.mkdir()
            source_path.write_text(
                "missing zip artifact must not parse source\n",
                encoding="utf-8",
            )
            zip_path = temp_root / "RuntimeDirectXLoaderFixture.cglb"
            self._write_zip_package(
                package_dir,
                zip_path,
                prefix=zip_path.name,
                exclude={native_path},
            )

            with (
                self._guard_crossgl_source_reads(),
                self._guard_crossgl_source_archive_reads(),
            ):
                plan = plan_directx_native_loader(zip_path)
                summary = plan.to_summary()

            descriptor_summary = summary["nativeArtifactDescriptor"]
            self.assertFalse(plan.ready)
            self.assertFalse(plan.source_parsing_required)
            self.assertFalse(plan.device_execution_required)
            self.assertIsNone(plan.native_artifact)
            self.assertEqual(summary["runtimePlan"]["packageFormat"], "zip")
            self.assertEqual(summary["sourceInputs"], [])
            self.assertEqual(summary["compilerInvocationRequired"], False)
            self.assertEqual(summary["deviceExecutionRequired"], False)
            self.assertIsNone(summary["nativeArtifact"])
            self.assertEqual(
                summary["runtimePlan"]["requiredArtifactPaths"],
                {"nativeBinary": native_path},
            )
            self._assert_source_free_directx_descriptor_summary(
                descriptor_summary,
                descriptor_path=descriptor_path,
                native_path=native_path,
            )
            self.assertIn(
                "package.artifact.required_file_missing",
                [diagnostic["code"] for diagnostic in summary["rejectReasons"]],
            )
            with self.assertRaisesRegex(PackageReadError, "nativeBinary"):
                plan.require_ready()

    def test_rejects_stale_or_malformed_dxil_descriptor_without_source_or_work(
        self,
    ) -> None:
        cases = (
            (
                "stale artifact bytes",
                "stale",
                [
                    "package.native_artifact_descriptor.artifact_hash_mismatch",
                    "package.native_artifact_descriptor.size_bytes_mismatch",
                ],
                "artifact",
            ),
            (
                "missing artifact hash",
                "missing_hash",
                ["package.native_artifact_descriptor.artifact_hash_invalid"],
                "artifactHash",
            ),
        )
        for name, mutation, expected_codes, ready_error in cases:
            with self.subTest(name=name):
                with tempfile.TemporaryDirectory(suffix=".cglb") as temp_dir:
                    package_dir = Path(temp_dir)
                    descriptor_path = (
                        "backend/directx/"
                        "RuntimeDirectXLoaderFixture.native-artifact.json"
                    )
                    native_path = "backend/directx/RuntimeDirectXLoaderFixture.dxil"
                    self._write_source_free_directx_package(
                        package_dir,
                        descriptor_path=descriptor_path,
                    )
                    if mutation == "stale":
                        (package_dir / native_path).write_bytes(b"stale-dxil")
                    else:
                        descriptor_file = package_dir / descriptor_path
                        descriptor = json.loads(
                            descriptor_file.read_text(encoding="utf-8")
                        )
                        descriptor.pop("artifactHash")
                        self._write_json(descriptor_file, descriptor)
                    source_path = (
                        package_dir / "source" / "RuntimeDirectXLoaderFixture.cgl"
                    )
                    source_path.parent.mkdir()
                    source_path.write_text(
                        "descriptor recovery must not parse CrossGL source\n",
                        encoding="utf-8",
                    )

                    with self._guard_crossgl_source_reads():
                        plan = plan_directx_native_loader(package_dir)
                        summary = plan.to_summary()

                    descriptor_summary = summary["nativeArtifactDescriptor"]
                    self.assertFalse(plan.ready)
                    self.assertFalse(plan.source_parsing_required)
                    self.assertFalse(plan.device_execution_required)
                    self.assertIsNone(plan.native_artifact)
                    self.assertEqual(
                        summary["runtimePlan"]["packageFormat"], "directory"
                    )
                    self.assertEqual(summary["sourceInputs"], [])
                    self.assertEqual(summary["compilerInvocationRequired"], False)
                    self.assertEqual(summary["deviceExecutionRequired"], False)
                    self.assertIsNone(summary["nativeArtifact"])
                    self.assertEqual(
                        summary["runtimePlan"]["metadataContract"]["sourceInputs"],
                        [],
                    )
                    self._assert_source_free_directx_descriptor_summary(
                        descriptor_summary,
                        descriptor_path=descriptor_path,
                        native_path=native_path,
                    )
                    reject_codes = [
                        diagnostic["code"] for diagnostic in summary["rejectReasons"]
                    ]
                    for expected_code in expected_codes:
                        self.assertIn(expected_code, reject_codes)
                    api_boundary = summary["directxNativeApiBoundary"]
                    self.assertEqual(api_boundary["decision"], "rejected")
                    self.assertFalse(api_boundary["d3dRuntimeCallsPerformed"])
                    self.assertFalse(api_boundary["d3dDeviceCreationPerformed"])
                    self.assertFalse(api_boundary["d3dCommandExecutionPerformed"])
                    freshness = api_boundary["descriptorFreshness"]
                    for expected_code in expected_codes:
                        self.assertIn(
                            expected_code,
                            freshness["failClosedDiagnosticCodes"],
                        )
                    self.assertFalse(freshness["artifactHashMatchesNativeBinary"])
                    if mutation == "stale":
                        self.assertTrue(freshness["artifactHashDeclared"])
                        self.assertFalse(freshness["sizeBytesMatchesNativeBinary"])
                    else:
                        self.assertFalse(freshness["artifactHashDeclared"])
                        self.assertTrue(freshness["sizeBytesMatchesNativeBinary"])
                    with self.assertRaisesRegex(PackageReadError, ready_error):
                        plan.require_ready()

    def test_rejects_zip_stale_or_malformed_dxil_descriptor_without_source_or_work(
        self,
    ) -> None:
        cases = (
            (
                "stale artifact bytes",
                "stale",
                [
                    "package.native_artifact_descriptor.artifact_hash_mismatch",
                    "package.native_artifact_descriptor.size_bytes_mismatch",
                ],
                "artifact",
            ),
            (
                "missing artifact hash",
                "missing_hash",
                ["package.native_artifact_descriptor.artifact_hash_invalid"],
                "artifactHash",
            ),
        )
        for name, mutation, expected_codes, ready_error in cases:
            with self.subTest(name=name):
                with tempfile.TemporaryDirectory() as temp_dir:
                    temp_root = Path(temp_dir)
                    package_dir = temp_root / "package-dir"
                    package_dir.mkdir()
                    descriptor_path = (
                        "backend/directx/"
                        "RuntimeDirectXLoaderFixture.native-artifact.json"
                    )
                    native_path = "backend/directx/RuntimeDirectXLoaderFixture.dxil"
                    self._write_source_free_directx_package(
                        package_dir,
                        descriptor_path=descriptor_path,
                    )
                    if mutation == "stale":
                        (package_dir / native_path).write_bytes(b"stale-dxil")
                    else:
                        descriptor_file = package_dir / descriptor_path
                        descriptor = json.loads(
                            descriptor_file.read_text(encoding="utf-8")
                        )
                        descriptor.pop("artifactHash")
                        self._write_json(descriptor_file, descriptor)
                    source_path = (
                        package_dir / "source" / "RuntimeDirectXLoaderFixture.cgl"
                    )
                    source_path.parent.mkdir()
                    source_path.write_text(
                        "zip descriptor recovery must not parse CrossGL source\n",
                        encoding="utf-8",
                    )
                    zip_path = temp_root / "RuntimeDirectXLoaderFixture.cglb"
                    self._write_zip_package(
                        package_dir,
                        zip_path,
                        prefix=zip_path.name,
                    )

                    with (
                        self._guard_crossgl_source_reads(),
                        self._guard_crossgl_source_archive_reads(),
                    ):
                        plan = plan_directx_native_loader(zip_path)
                        summary = plan.to_summary()

                    descriptor_summary = summary["nativeArtifactDescriptor"]
                    self.assertFalse(plan.ready)
                    self.assertFalse(plan.source_parsing_required)
                    self.assertFalse(plan.device_execution_required)
                    self.assertIsNone(plan.native_artifact)
                    self.assertEqual(summary["runtimePlan"]["packageFormat"], "zip")
                    self.assertEqual(summary["sourceInputs"], [])
                    self.assertEqual(summary["compilerInvocationRequired"], False)
                    self.assertEqual(summary["deviceExecutionRequired"], False)
                    self.assertIsNone(summary["nativeArtifact"])
                    self._assert_source_free_directx_descriptor_summary(
                        descriptor_summary,
                        descriptor_path=descriptor_path,
                        native_path=native_path,
                    )
                    reject_codes = [
                        diagnostic["code"] for diagnostic in summary["rejectReasons"]
                    ]
                    for expected_code in expected_codes:
                        self.assertIn(expected_code, reject_codes)
                    api_boundary = summary["directxNativeApiBoundary"]
                    self.assertEqual(api_boundary["decision"], "rejected")
                    self.assertFalse(api_boundary["d3dRuntimeCallsPerformed"])
                    self.assertFalse(api_boundary["d3dDeviceCreationPerformed"])
                    self.assertFalse(api_boundary["d3dCommandExecutionPerformed"])
                    freshness = api_boundary["descriptorFreshness"]
                    for expected_code in expected_codes:
                        self.assertIn(
                            expected_code,
                            freshness["failClosedDiagnosticCodes"],
                        )
                    self.assertFalse(freshness["artifactHashMatchesNativeBinary"])
                    if mutation == "stale":
                        self.assertTrue(freshness["artifactHashDeclared"])
                        self.assertFalse(freshness["sizeBytesMatchesNativeBinary"])
                    else:
                        self.assertFalse(freshness["artifactHashDeclared"])
                        self.assertTrue(freshness["sizeBytesMatchesNativeBinary"])
                    with self.assertRaisesRegex(PackageReadError, ready_error):
                        plan.require_ready()

    def test_rejects_incompatible_target_without_source_parse(self) -> None:
        with tempfile.TemporaryDirectory(suffix=".cglb") as temp_dir:
            package_dir = Path(temp_dir)
            self._write_valid_vulkan_package(package_dir)
            source_path = package_dir / "source" / "invalid.cgl"
            source_path.parent.mkdir()
            source_path.write_text("target mismatch source\n", encoding="utf-8")

            with self._guard_source_reads():
                plan = plan_directx_native_loader(package_dir)
                summary = plan.to_summary()

            self.assertFalse(plan.ready)
            self.assertIsNone(plan.native_artifact)
            self.assertEqual(summary["sourceInputs"], [])
            self.assertIn(
                "package.target.loader_mismatch",
                [diagnostic["code"] for diagnostic in summary["rejectReasons"]],
            )
            self.assertEqual(list(package_dir.rglob("*.cgl")), [source_path])

    def test_rejects_missing_native_artifact_metadata(self) -> None:
        with tempfile.TemporaryDirectory(suffix=".cglb") as temp_dir:
            package_dir = Path(temp_dir)
            self._write_valid_directx_package(package_dir, include_native_binary=False)
            source_path = package_dir / "source" / "invalid.cgl"
            source_path.parent.mkdir()
            source_path.write_text("missing artifact source\n", encoding="utf-8")

            with self._guard_source_reads():
                plan = plan_directx_native_loader(package_dir)
                summary = plan.to_summary()

            self.assertFalse(plan.ready)
            self.assertIsNone(plan.native_artifact)
            self.assertEqual(summary["sourceInputs"], [])
            self.assertIn(
                "package.artifact.required_missing",
                [diagnostic["code"] for diagnostic in summary["rejectReasons"]],
            )
            with self.assertRaisesRegex(PackageReadError, "nativeBinary"):
                plan.require_ready()
            self.assertEqual(list(package_dir.rglob("*.cgl")), [source_path])

    def test_rejects_native_artifact_tampered_to_crossgl_source(self) -> None:
        with tempfile.TemporaryDirectory(suffix=".cglb") as temp_dir:
            package_dir = Path(temp_dir)
            self._write_valid_directx_package(
                package_dir,
                native_binary_path="source/forged.cgl",
            )

            with self._guard_source_reads():
                plan = plan_directx_native_loader(package_dir)
                summary = plan.to_summary()

            self.assertFalse(plan.ready)
            self.assertIsNone(plan.native_artifact)
            self.assertEqual(summary["sourceInputs"], [])
            self.assertIn(
                "package.artifact.source_input_leakage",
                [diagnostic["code"] for diagnostic in summary["rejectReasons"]],
            )

    def test_manifest_declared_descriptor_status_mismatch_rejects_native_plan(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory(suffix=".cglb") as temp_dir:
            package_dir = Path(temp_dir)
            descriptor_path = "metadata/native-artifact.json"
            self._write_valid_directx_package(package_dir)
            self._write_native_artifact_descriptor(
                package_dir,
                descriptor_path=descriptor_path,
                native_binary_status="validated",
                validation_status="validated",
            )
            manifest_path = package_dir / "manifest.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["artifacts"]["nativeArtifactDescriptor"] = descriptor_path
            self._write_json(manifest_path, manifest)
            source_path = package_dir / "source" / "invalid.cgl"
            source_path.parent.mkdir()
            source_path.write_text(
                "status mismatch rejection must not parse CrossGL source\n",
                encoding="utf-8",
            )

            with self._guard_crossgl_source_reads():
                plan = plan_directx_native_loader(package_dir)
                summary = plan.to_summary()

            self.assertFalse(plan.ready)
            self.assertIsNone(plan.native_artifact)
            self.assertEqual(summary["sourceInputs"], [])
            reject_codes = [
                diagnostic["code"] for diagnostic in summary["rejectReasons"]
            ]
            self.assertIn(
                (
                    "directx_loader."
                    "native_artifact_descriptor_native_binary_status_mismatch"
                ),
                reject_codes,
            )
            self.assertIn(
                "package.native_artifact_descriptor.native_binary_status_mismatch",
                reject_codes,
            )
            descriptor_reject = next(
                diagnostic
                for diagnostic in summary["rejectReasons"]
                if diagnostic["code"]
                == (
                    "directx_loader."
                    "native_artifact_descriptor_native_binary_status_mismatch"
                )
            )
            self.assertEqual(descriptor_reject["document"], "nativeArtifactDescriptor")
            self.assertEqual(descriptor_reject["path"], "nativeBinaryStatus")
            self.assertEqual(descriptor_reject["expected"], "emitted")
            self.assertEqual(descriptor_reject["actual"], "validated")
            with self.assertRaisesRegex(PackageReadError, "nativeBinaryStatus"):
                plan.require_ready()
            self.assertEqual(list(package_dir.rglob("*.cgl")), [source_path])

    def test_source_package_plan_uses_recorded_manifest_boundary(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory(suffix=".cglb") as temp_dir:
            package_dir = Path(temp_dir)
            requirements = self._source_package_requirements()
            requirements["requiredPathArtifacts"] = [
                "nativeBinary",
                "backendSource",
            ]
            self._write_valid_directx_package(
                package_dir,
                native_binary_status="planned",
                package_artifact_requirements=requirements,
            )
            native_path = (
                package_dir / "backend" / "directx" / "RuntimeDirectXLoaderFixture.dxil"
            )
            native_path.unlink()
            source_path = package_dir / "source" / "RuntimeDirectXLoaderFixture.cgl"
            source_path.parent.mkdir()
            source_path.write_text(
                "source-package loader must not parse CrossGL source\n",
                encoding="utf-8",
            )

            with self._guard_source_reads():
                plan = plan_directx_source_package_loader(package_dir)
                summary = plan.to_summary()

            self.assertTrue(plan.loadable, summary["diagnostics"])
            self.assertFalse(plan.source_parsing_required)
            self.assertEqual(summary["sourceInputs"], [])
            self.assertEqual(summary["compilerInvocationRequired"], False)
            self.assertEqual(summary["deviceExecutionRequired"], False)
            self.assertEqual(
                plan.required_artifacts,
                ("nativeBinary", "backendSource"),
            )
            self.assertEqual(
                [artifact.name for artifact in plan.selected_artifacts],
                ["nativeBinary", "backendSource"],
            )
            self.assertEqual(plan.require_runtime_artifact().name, "backendSource")
            self.assertEqual(
                summary["runtimeArtifactSelection"]["selectedPackageMode"],
                "source-package",
            )
            self.assertEqual(
                summary["runtimeArtifactSelection"]["artifact"]["name"],
                "backendSource",
            )
            self.assertFalse(
                summary["runtimeArtifactSelection"]["sourceParsingRequired"]
            )
            self.assertEqual(
                summary["metadataContract"]["contractSource"],
                "manifest.packageArtifactRequirements",
            )
            self.assertEqual(summary["metadataContract"]["sourceInputs"], [])
            self.assertEqual(
                [
                    (artifact["name"], artifact["path"], artifact["exists"])
                    for artifact in summary["selectedArtifacts"]
                ],
                [
                    (
                        "nativeBinary",
                        "backend/directx/RuntimeDirectXLoaderFixture.dxil",
                        False,
                    ),
                    (
                        "backendSource",
                        "backend/directx/RuntimeDirectXLoaderFixture.hlsl",
                        True,
                    ),
                ],
            )
            self.assertEqual(
                summary["metadataContract"]["runtimeArtifact"],
                {
                    "name": "backendSource",
                    "path": "backend/directx/RuntimeDirectXLoaderFixture.hlsl",
                    "declaredBy": "manifest.artifacts.backendSource",
                },
            )
            self.assertEqual(
                summary["compatibilityReport"]["nativeBinaryStatus"],
                "planned",
            )
            self.assertEqual(
                summary["compatibilityReport"]["packageArtifactRequirements"][
                    "requirementsSource"
                ],
                "manifest",
            )
            self.assertEqual(
                summary["compatibilityReport"]["packageArtifactRequirements"][
                    "requiredPathArtifacts"
                ],
                ["nativeBinary", "backendSource"],
            )
            roles_by_name = {
                role["role"]: role
                for role in summary["artifactRoleCompatibility"]["roles"]
            }
            self.assertEqual(
                roles_by_name["nativeBinary"]["status"],
                "planned-evidence",
            )
            self.assertTrue(roles_by_name["nativeBinary"]["compatible"])
            self.assertFalse(roles_by_name["nativeBinary"]["exists"])
            directx_admission = summary["directxSourcePackageAdmission"]
            self.assertEqual(directx_admission["decision"], "accepted")
            self.assertEqual(
                directx_admission["targetLegalizationEvidence"],
                summary["targetLegalizationEvidence"],
            )
            self.assertEqual(
                directx_admission["targetLegalizationToolRequirements"],
                summary["targetLegalizationToolRequirements"],
            )
            self.assertEqual(
                directx_admission["packageArtifactRequirementsSource"],
                summary["packageArtifactRequirementsSource"],
            )
            self.assertEqual(
                directx_admission["packageArtifactRequirements"],
                summary["packageArtifactRequirements"],
            )
            self.assertEqual(
                directx_admission["reason"],
                "directx_loader.source_package_admission.accepted",
            )
            self.assertEqual(
                directx_admission["compilerInvocationRequired"],
                False,
            )
            self.assertEqual(directx_admission["deviceExecutionRequired"], False)
            self.assertEqual(directx_admission["sourceInputs"], [])
            self.assertEqual(
                directx_admission["dxilArtifact"]["status"],
                "planned-metadata-only",
            )
            self.assertTrue(directx_admission["dxilArtifact"]["plannedMetadataOnly"])
            self.assertFalse(directx_admission["dxilArtifact"]["selectedForRuntime"])
            self.assertFalse(directx_admission["dxilArtifact"]["bytesRequired"])
            self.assertTrue(
                directx_admission["dxilArtifact"]["acceptedAsSourcePackageEvidence"]
            )
            self.assertEqual(
                directx_admission["sourcePackageRuntime"]["path"],
                "backend/directx/RuntimeDirectXLoaderFixture.hlsl",
            )
            self.assertEqual(
                directx_admission["packageMode"],
                {
                    "kind": "source-package",
                    "requested": "source-package",
                    "selected": "source-package",
                    "selectedForRuntime": True,
                },
            )
            self.assertEqual(
                directx_admission["declaredSourceArtifact"],
                directx_admission["sourcePackageRuntime"],
            )
            self.assertEqual(
                directx_admission["declaredSourceArtifact"]["declaredBy"],
                "manifest.artifacts.backendSource",
            )
            self.assertEqual(
                directx_admission["declaredSourceArtifact"]["expectedPathSuffix"],
                ".hlsl",
            )
            self.assertTrue(
                directx_admission["declaredSourceArtifact"]["pathSuffixMatchesExpected"]
            )
            self.assertIsNone(directx_admission["validatedSourceArtifact"])
            self.assertIsNone(directx_admission["compiledArtifact"])
            self.assertEqual(
                directx_admission["compatibilityEvidence"][
                    "manifestNativeBinaryStatus"
                ],
                "planned",
            )
            self.assertEqual(
                directx_admission["compatibilityEvidence"][
                    "packageArtifactRequirementsSource"
                ],
                summary["packageArtifactRequirementsSource"],
            )
            self.assertEqual(
                directx_admission["compatibilityEvidence"][
                    "packageArtifactRequirements"
                ],
                summary["packageArtifactRequirements"],
            )
            self.assertEqual(
                directx_admission["compatibilityEvidence"]["declaredSourcePath"],
                "backend/directx/RuntimeDirectXLoaderFixture.hlsl",
            )
            self.assertFalse(
                directx_admission["compatibilityEvidence"]["compiledArtifactExists"]
            )
            self.assertEqual(
                directx_admission["compatibilityEvidence"][
                    "targetLegalizationEvidence"
                ],
                summary["targetLegalizationEvidence"],
            )
            self.assertEqual(
                directx_admission["compatibilityEvidence"][
                    "targetLegalizationToolRequirements"
                ],
                summary["targetLegalizationToolRequirements"],
            )
            self.assertTrue(
                directx_admission["sourcePackageRuntime"]["sourcePackageSelected"]
            )
            self.assertEqual(
                summary["reflectionResources"]["targetResourceBindings"][0]["abi"],
                {"space": 0, "register": "u0"},
            )
            self.assertEqual(summary["reflectionResources"]["targetFeatureCount"], 1)
            self.assertEqual(summary["rejectReasons"], [])
            self.assertEqual(list(package_dir.rglob("*.cgl")), [source_path])

    def test_source_package_plan_uses_zip_recorded_manifest_boundary(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir)
            package_dir = temp_root / "package-dir"
            package_dir.mkdir()
            requirements = self._source_package_requirements()
            requirements["requiredPathArtifacts"] = [
                "nativeBinary",
                "backendSource",
            ]
            self._write_valid_directx_package(
                package_dir,
                native_binary_status="planned",
                package_artifact_requirements=requirements,
            )
            native_rel = "backend/directx/RuntimeDirectXLoaderFixture.dxil"
            source_rel = "backend/directx/RuntimeDirectXLoaderFixture.hlsl"
            source_path = package_dir / "source" / "RuntimeDirectXLoaderFixture.cgl"
            source_path.parent.mkdir()
            source_path.write_text(
                "zip source-package loader must not parse CrossGL source\n",
                encoding="utf-8",
            )
            zip_path = temp_root / "RuntimeDirectXLoaderFixture.cglb"
            self._write_zip_package(
                package_dir,
                zip_path,
                prefix=zip_path.name,
            )

            with (
                self._guard_crossgl_source_reads(),
                self._guard_crossgl_source_archive_reads(),
            ):
                plan = plan_directx_source_package_loader(zip_path)
                summary = plan.to_summary()

            selection = summary["runtimeArtifactSelection"]
            directx_admission = summary["directxSourcePackageAdmission"]

            self.assertTrue(plan.loadable, summary["diagnostics"])
            self.assertFalse(plan.source_parsing_required)
            self.assertEqual(summary["packageFormat"], "zip")
            self.assertEqual(summary["sourceInputs"], [])
            self.assertEqual(summary["compilerInvocationRequired"], False)
            self.assertEqual(summary["deviceExecutionRequired"], False)
            self.assertEqual(plan.required_artifacts, ("nativeBinary", "backendSource"))
            self.assertEqual(
                [artifact.name for artifact in plan.selected_artifacts],
                ["nativeBinary", "backendSource"],
            )
            self.assertEqual(plan.require_runtime_artifact().name, "backendSource")
            self.assertEqual(plan.require_runtime_artifact().archive_path, zip_path)
            self.assertEqual(
                plan.require_runtime_artifact().archive_member,
                f"{zip_path.name}/{source_rel}",
            )
            self.assertEqual(selection["requestedPackageMode"], "source-package")
            self.assertEqual(selection["selectedPackageMode"], "source-package")
            self.assertEqual(selection["artifact"]["name"], "backendSource")
            self.assertEqual(selection["artifact"]["path"], source_rel)
            self.assertFalse(selection["sourceParsingRequired"])
            self.assertEqual(
                summary["metadataContract"]["contractSource"],
                "manifest.packageArtifactRequirements",
            )
            self.assertEqual(summary["metadataContract"]["sourceInputs"], [])
            self.assertEqual(
                summary["metadataContract"]["runtimeArtifact"],
                {
                    "name": "backendSource",
                    "path": source_rel,
                    "declaredBy": "manifest.artifacts.backendSource",
                },
            )
            self.assertEqual(
                summary["compatibilityReport"]["packageArtifactRequirements"][
                    "requirementsSource"
                ],
                "manifest",
            )
            self.assertEqual(
                summary["compatibilityReport"]["packageArtifactRequirements"][
                    "requiredPathArtifacts"
                ],
                ["nativeBinary", "backendSource"],
            )
            self.assertEqual(
                [
                    (artifact["name"], artifact["path"], artifact["exists"])
                    for artifact in summary["selectedArtifacts"]
                ],
                [
                    ("nativeBinary", native_rel, True),
                    ("backendSource", source_rel, True),
                ],
            )
            self.assertEqual(directx_admission["decision"], "accepted")
            self.assertEqual(
                directx_admission["reason"],
                "directx_loader.source_package_admission.accepted",
            )
            self.assertEqual(directx_admission["compilerInvocationRequired"], False)
            self.assertEqual(directx_admission["deviceExecutionRequired"], False)
            self.assertEqual(directx_admission["sourceInputs"], [])
            self.assertEqual(
                directx_admission["packageArtifactRequirementsSource"],
                summary["packageArtifactRequirementsSource"],
            )
            self.assertEqual(
                directx_admission["packageArtifactRequirements"],
                summary["packageArtifactRequirements"],
            )
            self.assertEqual(
                directx_admission["dxilArtifact"]["status"],
                "planned-metadata-only",
            )
            self.assertTrue(directx_admission["dxilArtifact"]["plannedMetadataOnly"])
            self.assertFalse(directx_admission["dxilArtifact"]["selectedForRuntime"])
            self.assertFalse(directx_admission["dxilArtifact"]["bytesRequired"])
            self.assertEqual(
                directx_admission["sourcePackageRuntime"]["path"],
                source_rel,
            )
            self.assertEqual(
                directx_admission["packageMode"],
                {
                    "kind": "source-package",
                    "requested": "source-package",
                    "selected": "source-package",
                    "selectedForRuntime": True,
                },
            )
            self.assertEqual(
                directx_admission["compatibilityEvidence"][
                    "packageArtifactRequirementsSource"
                ],
                summary["packageArtifactRequirementsSource"],
            )
            self.assertEqual(
                directx_admission["compatibilityEvidence"][
                    "packageArtifactRequirements"
                ],
                summary["packageArtifactRequirements"],
            )
            self.assertEqual(summary["rejectReasons"], [])
            self.assertEqual(list(package_dir.rglob("*.cgl")), [source_path])

    def test_source_package_rejects_missing_declared_hlsl_source_artifact(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory(suffix=".cglb") as temp_dir:
            package_dir = Path(temp_dir)
            self._write_valid_directx_package(
                package_dir,
                native_binary_status="planned",
                package_artifact_requirements=self._source_package_requirements(),
            )
            source_artifact_path = (
                package_dir / "backend" / "directx" / "RuntimeDirectXLoaderFixture.hlsl"
            )
            source_artifact_path.unlink()
            crossgl_source = package_dir / "source" / "RuntimeDirectXLoaderFixture.cgl"
            crossgl_source.parent.mkdir()
            crossgl_source.write_text(
                "missing HLSL source artifact must not be parsed\n",
                encoding="utf-8",
            )

            with self._guard_source_reads():
                plan = plan_directx_source_package_loader(package_dir)
                summary = plan.to_summary()

            admission = summary["directxSourcePackageAdmission"]
            declared_source = admission["declaredSourceArtifact"]
            evidence = admission["compatibilityEvidence"]

            self.assertFalse(plan.loadable)
            self.assertEqual(admission["decision"], "rejected")
            self.assertEqual(
                admission["reason"],
                "package.artifact.required_file_missing",
            )
            self.assertTrue(declared_source["declared"])
            self.assertFalse(declared_source["exists"])
            self.assertEqual(
                declared_source["path"],
                "backend/directx/RuntimeDirectXLoaderFixture.hlsl",
            )
            self.assertEqual(declared_source["expectedPathSuffix"], ".hlsl")
            self.assertTrue(declared_source["pathSuffixMatchesExpected"])
            self.assertEqual(
                evidence["declaredSourcePath"],
                "backend/directx/RuntimeDirectXLoaderFixture.hlsl",
            )
            self.assertFalse(evidence["sourceArtifactExists"])
            self.assertIn(
                "package.artifact.required_file_missing",
                [diagnostic["code"] for diagnostic in summary["rejectReasons"]],
            )
            with self.assertRaisesRegex(PackageReadError, "backendSource"):
                plan.require_loadable()
            self.assertEqual(list(package_dir.rglob("*.cgl")), [crossgl_source])

    def test_planned_source_package_treats_present_native_binary_as_evidence(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory(suffix=".cglb") as temp_dir:
            package_dir = Path(temp_dir)
            requirements = self._source_package_requirements()
            self._write_valid_directx_package(
                package_dir,
                native_binary_status="planned",
                package_artifact_requirements=requirements,
            )
            source_path = package_dir / "source" / "RuntimeDirectXLoaderFixture.cgl"
            source_path.parent.mkdir()
            source_path.write_text(
                "present planned native evidence must not parse CrossGL source\n",
                encoding="utf-8",
            )

            with self._guard_source_reads():
                plan = plan_directx_source_package_loader(package_dir)
                summary = plan.to_summary()

            artifacts_by_name = {
                artifact["name"]: artifact
                for artifact in summary["artifactCompatibility"]["artifacts"]
            }
            roles_by_name = {
                role["role"]: role
                for role in summary["artifactRoleCompatibility"]["roles"]
            }
            native_admission = summary["runtimeArtifactAdmission"]["nativeArtifact"]

            self.assertTrue(plan.loadable, summary["diagnostics"])
            self.assertEqual(plan.require_runtime_artifact().name, "backendSource")
            self.assertEqual(
                summary["runtimeArtifactSelection"]["selectedPackageMode"],
                "source-package",
            )
            self.assertEqual(
                [
                    (artifact["name"], artifact["exists"])
                    for artifact in summary["selectedArtifacts"]
                ],
                [("backendSource", True), ("nativeBinary", True)],
            )
            self.assertEqual(
                artifacts_by_name["nativeBinary"]["decision"],
                "skipped",
            )
            self.assertEqual(
                artifacts_by_name["nativeBinary"]["reason"],
                "package.artifact.planned_native_binary",
            )
            self.assertEqual(
                roles_by_name["nativeBinary"]["status"],
                "planned-evidence",
            )
            self.assertFalse(roles_by_name["nativeBinary"]["selectedForRuntime"])
            self.assertFalse(roles_by_name["nativeBinary"]["bytesRequired"])
            self.assertEqual(native_admission["decision"], "skipped")
            self.assertEqual(native_admission["category"], "native-not-requested")
            self.assertEqual(
                native_admission["reason"],
                "runtime.native_artifact.not_requested",
            )
            self.assertEqual(native_admission["artifact"]["name"], "nativeBinary")
            directx_admission = summary["directxSourcePackageAdmission"]
            self.assertEqual(
                directx_admission["dxilArtifact"]["status"],
                "planned-metadata-only",
            )
            self.assertTrue(directx_admission["dxilArtifact"]["exists"])
            self.assertTrue(
                directx_admission["dxilArtifact"]["acceptedAsSourcePackageEvidence"]
            )
            self.assertFalse(
                directx_admission["dxilArtifact"]["acceptedForNativeSelection"]
            )
            self.assertEqual(summary["sourceInputs"], [])
            self.assertEqual(summary["metadataContract"]["sourceInputs"], [])
            self.assertEqual(list(package_dir.rglob("*.cgl")), [source_path])

    def test_emitted_source_package_selects_native_unless_source_package_requested(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory(suffix=".cglb") as temp_dir:
            package_dir = Path(temp_dir)
            requirements = self._source_package_requirements()
            requirements["requiredPathArtifacts"] = [
                "nativeBinary",
                "backendSource",
            ]
            self._write_valid_directx_package(
                package_dir,
                native_binary_status="emitted",
                package_artifact_requirements=requirements,
            )
            native_rel = "backend/directx/RuntimeDirectXLoaderFixture.dxil"
            source_rel = "backend/directx/RuntimeDirectXLoaderFixture.hlsl"
            source_path = package_dir / "source" / "RuntimeDirectXLoaderFixture.cgl"
            source_path.parent.mkdir()
            source_path.write_text(
                "emitted source-package selection must stay metadata-only\n",
                encoding="utf-8",
            )

            with self._guard_source_reads():
                auto_plan = plan_directx_loader(package_dir)
                native_plan = plan_directx_loader(
                    package_dir,
                    package_mode="native",
                )
                source_package_plan = plan_directx_source_package_loader(package_dir)

            for plan, requested_mode in (
                (auto_plan, "auto"),
                (native_plan, "native"),
            ):
                with self.subTest(requested_mode=requested_mode):
                    summary = plan.to_summary()
                    selection = summary["runtimeArtifactSelection"]

                    self.assertTrue(plan.loadable, summary["diagnostics"])
                    self.assertEqual(summary["loaderTarget"], "directx")
                    self.assertEqual(summary["selectedTarget"], "directx")
                    self.assertEqual(selection["requestedPackageMode"], requested_mode)
                    self.assertEqual(selection["selectedPackageMode"], "native")
                    self.assertEqual(selection["artifact"]["name"], "nativeBinary")
                    self.assertEqual(selection["artifact"]["path"], native_rel)
                    self.assertEqual(
                        plan.require_runtime_artifact().name, "nativeBinary"
                    )
                    self.assertEqual(summary["runtimeArtifactPath"], native_rel)
                    self.assertEqual(
                        summary["compatibilityReport"]["nativeBinaryStatus"],
                        "emitted",
                    )
                    self.assertEqual(
                        summary["compatibilityReport"]["packageArtifactRequirements"][
                            "packageMode"
                        ],
                        "source-package",
                    )
                    self.assertEqual(summary["sourceInputs"], [])
                    self.assertEqual(
                        summary["compilerInvocationRequired"],
                        False,
                    )
                    self.assertEqual(summary["deviceExecutionRequired"], False)
                    self.assertEqual(
                        summary["metadataContract"]["runtimeArtifact"],
                        {
                            "name": "nativeBinary",
                            "path": native_rel,
                            "declaredBy": "manifest.artifacts.nativeBinary",
                        },
                    )
                    self.assertEqual(
                        summary["metadataContract"]["compilerInvocationRequired"],
                        False,
                    )
                    self.assertEqual(
                        summary["metadataContract"]["deviceExecutionRequired"],
                        False,
                    )
                    self.assertEqual(summary["metadataContract"]["sourceInputs"], [])
                    directx_admission = summary["directxSourcePackageAdmission"]
                    self.assertEqual(directx_admission["decision"], "accepted")
                    self.assertEqual(
                        directx_admission["dxilArtifact"]["status"],
                        "emitted-selected",
                    )
                    self.assertTrue(
                        directx_admission["dxilArtifact"]["acceptedForNativeSelection"]
                    )
                    self.assertFalse(
                        directx_admission["dxilArtifact"]["plannedMetadataOnly"]
                    )
                    self.assertEqual(
                        directx_admission["compilerInvocationRequired"],
                        False,
                    )
                    self.assertEqual(
                        directx_admission["deviceExecutionRequired"],
                        False,
                    )
                    self.assertEqual(
                        directx_admission["packageArtifactRequirementsSource"],
                        summary["packageArtifactRequirementsSource"],
                    )
                    self.assertEqual(
                        directx_admission["packageArtifactRequirements"],
                        summary["packageArtifactRequirements"],
                    )
                    self.assertEqual(
                        directx_admission["compatibilityEvidence"][
                            "packageArtifactRequirementsSource"
                        ],
                        summary["packageArtifactRequirementsSource"],
                    )
                    self.assertEqual(
                        directx_admission["compatibilityEvidence"][
                            "packageArtifactRequirements"
                        ],
                        summary["packageArtifactRequirements"],
                    )

            summary = source_package_plan.to_summary()
            selection = summary["runtimeArtifactSelection"]
            self.assertTrue(source_package_plan.loadable, summary["diagnostics"])
            self.assertEqual(selection["requestedPackageMode"], "source-package")
            self.assertEqual(selection["selectedPackageMode"], "source-package")
            self.assertEqual(selection["artifact"]["name"], "backendSource")
            self.assertEqual(selection["artifact"]["path"], source_rel)
            self.assertEqual(
                source_package_plan.require_runtime_artifact().name,
                "backendSource",
            )
            self.assertEqual(summary["runtimeArtifactPath"], source_rel)
            self.assertEqual(
                summary["compatibilityReport"]["nativeBinaryStatus"],
                "emitted",
            )
            self.assertEqual(summary["compilerInvocationRequired"], False)
            self.assertEqual(summary["deviceExecutionRequired"], False)
            self.assertEqual(
                summary["metadataContract"]["runtimeArtifact"],
                {
                    "name": "backendSource",
                    "path": source_rel,
                    "declaredBy": "manifest.artifacts.backendSource",
                },
            )
            self.assertEqual(
                [
                    (artifact["name"], artifact["path"], artifact["exists"])
                    for artifact in summary["selectedArtifacts"]
                ],
                [
                    ("nativeBinary", native_rel, True),
                    ("backendSource", source_rel, True),
                ],
            )
            roles_by_name = {
                role["role"]: role
                for role in summary["artifactRoleCompatibility"]["roles"]
            }
            self.assertEqual(
                roles_by_name["nativeBinary"]["status"],
                "required-sidecar-artifact",
            )
            self.assertTrue(roles_by_name["nativeBinary"]["compatible"])
            self.assertFalse(roles_by_name["nativeBinary"]["selectedForRuntime"])
            self.assertEqual(
                roles_by_name["backendSource"]["status"],
                "selected-runtime-artifact",
            )
            directx_admission = summary["directxSourcePackageAdmission"]
            self.assertEqual(directx_admission["decision"], "accepted")
            self.assertEqual(
                directx_admission["selectedPackageMode"],
                "source-package",
            )
            self.assertEqual(
                directx_admission["dxilArtifact"]["status"],
                "emitted-sidecar",
            )
            self.assertFalse(directx_admission["dxilArtifact"]["selectedForRuntime"])
            self.assertFalse(
                directx_admission["dxilArtifact"]["acceptedForNativeSelection"]
            )
            self.assertTrue(
                directx_admission["sourcePackageRuntime"]["sourcePackageSelected"]
            )
            self.assertEqual(
                directx_admission["packageArtifactRequirementsSource"],
                summary["packageArtifactRequirementsSource"],
            )
            self.assertEqual(
                directx_admission["packageArtifactRequirements"],
                summary["packageArtifactRequirements"],
            )
            self.assertEqual(
                directx_admission["compatibilityEvidence"][
                    "packageArtifactRequirementsSource"
                ],
                summary["packageArtifactRequirementsSource"],
            )
            self.assertEqual(
                directx_admission["compatibilityEvidence"][
                    "packageArtifactRequirements"
                ],
                summary["packageArtifactRequirements"],
            )
            self.assertEqual(summary["sourceInputs"], [])
            self.assertEqual(summary["metadataContract"]["sourceInputs"], [])
            self.assertEqual(list(package_dir.rglob("*.cgl")), [source_path])

    def test_emitted_source_package_reports_descriptor_consistency_detail(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory(suffix=".cglb") as temp_dir:
            package_dir = Path(temp_dir)
            requirements = self._source_package_requirements()
            requirements["requiredPathArtifacts"] = [
                "nativeBinary",
                "backendSource",
            ]
            descriptor_path = "metadata/native-artifact.json"
            self._write_valid_directx_package(
                package_dir,
                native_binary_status="emitted",
                package_artifact_requirements=requirements,
            )
            self._write_native_artifact_descriptor(
                package_dir,
                descriptor_path=descriptor_path,
                native_binary_status="emitted",
                validation_status="not-run",
            )
            manifest_path = package_dir / "manifest.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["artifacts"]["nativeArtifactDescriptor"] = descriptor_path
            self._write_json(manifest_path, manifest)
            source_path = package_dir / "source" / "RuntimeDirectXLoaderFixture.cgl"
            source_path.parent.mkdir()
            source_path.write_text(
                "descriptor consistency must not parse CrossGL source\n",
                encoding="utf-8",
            )

            with self._guard_crossgl_source_reads():
                plan = plan_directx_source_package_loader(package_dir)
                summary = plan.to_summary()

            directx_admission = summary["directxSourcePackageAdmission"]
            native_admission = directx_admission["nativeBinaryArtifact"]
            descriptor_admission = directx_admission["nativeArtifactDescriptor"]

            self.assertTrue(plan.loadable, summary["diagnostics"])
            self.assertEqual(directx_admission["decision"], "accepted")
            self.assertEqual(directx_admission["compilerInvocationRequired"], False)
            self.assertEqual(directx_admission["deviceExecutionRequired"], False)
            self.assertEqual(directx_admission["sourceInputs"], [])
            self.assertEqual(
                directx_admission["dxilArtifact"]["status"],
                "emitted-sidecar",
            )
            self.assertEqual(directx_admission["dxilArtifact"], native_admission)
            self.assertNotIn("dxbcArtifact", directx_admission)
            self.assertEqual(native_admission["binaryKind"], "directx.dxil")
            self.assertEqual(native_admission["expectedPathSuffix"], ".dxil")
            self.assertEqual(native_admission["pathSuffix"], ".dxil")
            self.assertTrue(native_admission["pathSuffixMatchesExpected"])
            self.assertTrue(native_admission["pathSuffixMatchesDxil"])
            self.assertNotIn("pathSuffixMatchesDxbc", native_admission)
            self.assertTrue(descriptor_admission["declared"])
            self.assertTrue(descriptor_admission["readable"])
            self.assertTrue(descriptor_admission["manifestConsistent"])
            self.assertEqual(
                descriptor_admission["consistencyStatus"],
                "consistent",
            )
            self.assertTrue(descriptor_admission["binaryKindMatchesLoader"])
            self.assertTrue(descriptor_admission["artifactPathMatchesManifest"])
            self.assertTrue(descriptor_admission["nativeBinaryStatusMatchesManifest"])
            self.assertTrue(descriptor_admission["sizeBytesMatchesArtifact"])
            self.assertTrue(
                directx_admission["dxilArtifact"]["emittedDescriptorManifestConsistent"]
            )
            self.assertEqual(list(package_dir.rglob("*.cgl")), [source_path])

    def test_emitted_source_package_reports_dxbc_native_binary_detail(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory(suffix=".cglb") as temp_dir:
            package_dir = Path(temp_dir)
            requirements = self._source_package_requirements()
            requirements["requiredPathArtifacts"] = [
                "nativeBinary",
                "backendSource",
            ]
            descriptor_path = "metadata/native-artifact.json"
            native_rel = "backend/directx/RuntimeDirectXLoaderFixture.dxbc"
            native_bytes = b"DXBC"
            self._write_valid_directx_package(
                package_dir,
                native_binary_path=native_rel,
                native_binary_status="emitted",
                native_binary_bytes=native_bytes,
                package_artifact_requirements=requirements,
            )
            self._write_native_artifact_descriptor(
                package_dir,
                descriptor_path=descriptor_path,
                native_binary_status="emitted",
                validation_status="not-run",
                binary_kind="directx.dxbc",
                artifact_path=native_rel,
                artifact_bytes=native_bytes,
            )
            manifest_path = package_dir / "manifest.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["artifacts"]["nativeArtifactDescriptor"] = descriptor_path
            self._write_json(manifest_path, manifest)
            source_path = package_dir / "source" / "RuntimeDirectXLoaderFixture.cgl"
            source_path.parent.mkdir()
            source_path.write_text(
                "DXBC descriptor source package must not parse CrossGL source\n",
                encoding="utf-8",
            )

            with self._guard_crossgl_source_reads():
                plan = plan_directx_source_package_loader(package_dir)
                summary = plan.to_summary()

            directx_admission = summary["directxSourcePackageAdmission"]
            native_admission = directx_admission["nativeBinaryArtifact"]
            descriptor_admission = directx_admission["nativeArtifactDescriptor"]

            self.assertTrue(plan.loadable, summary["diagnostics"])
            self.assertEqual(directx_admission["decision"], "accepted")
            self.assertEqual(directx_admission["blockedByDiagnostics"], [])
            self.assertNotIn("dxilArtifact", directx_admission)
            self.assertEqual(directx_admission["dxbcArtifact"], native_admission)
            self.assertEqual(native_admission["status"], "emitted-sidecar")
            self.assertEqual(native_admission["binaryKind"], "directx.dxbc")
            self.assertEqual(
                native_admission["binaryKindSource"],
                "nativeArtifactDescriptor.binaryKind",
            )
            self.assertEqual(native_admission["descriptorBinaryKind"], "directx.dxbc")
            self.assertEqual(native_admission["expectedBinaryKind"], "directx.dxbc")
            self.assertEqual(
                native_admission["expectedBinaryKinds"],
                ["directx.dxil", "directx.dxbc"],
            )
            self.assertEqual(native_admission["expectedPathSuffix"], ".dxbc")
            self.assertEqual(
                native_admission["expectedPathSuffixes"],
                [".dxil", ".dxbc"],
            )
            self.assertEqual(native_admission["pathSuffix"], ".dxbc")
            self.assertTrue(native_admission["pathSuffixMatchesExpected"])
            self.assertTrue(native_admission["pathSuffixMatchesDxbc"])
            self.assertNotIn("pathSuffixMatchesDxil", native_admission)
            self.assertFalse(native_admission["selectedForRuntime"])
            self.assertFalse(native_admission["acceptedForNativeSelection"])
            self.assertTrue(descriptor_admission["manifestConsistent"])
            self.assertTrue(descriptor_admission["binaryKindMatchesLoader"])
            self.assertTrue(descriptor_admission["artifactPathMatchesManifest"])
            self.assertEqual(summary["rejectReasons"], [])
            self.assertEqual(list(package_dir.rglob("*.cgl")), [source_path])

    def test_emitted_source_package_rejects_dxbc_descriptor_with_dxil_suffix(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory(suffix=".cglb") as temp_dir:
            package_dir = Path(temp_dir)
            requirements = self._source_package_requirements()
            requirements["requiredPathArtifacts"] = [
                "nativeBinary",
                "backendSource",
            ]
            descriptor_path = "metadata/native-artifact.json"
            native_rel = "backend/directx/RuntimeDirectXLoaderFixture.dxil"
            native_bytes = b"DXBC"
            self._write_valid_directx_package(
                package_dir,
                native_binary_path=native_rel,
                native_binary_status="emitted",
                native_binary_bytes=native_bytes,
                package_artifact_requirements=requirements,
            )
            self._write_native_artifact_descriptor(
                package_dir,
                descriptor_path=descriptor_path,
                native_binary_status="emitted",
                validation_status="not-run",
                binary_kind="directx.dxbc",
                artifact_path=native_rel,
                artifact_bytes=native_bytes,
            )
            manifest_path = package_dir / "manifest.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["artifacts"]["nativeArtifactDescriptor"] = descriptor_path
            self._write_json(manifest_path, manifest)
            source_path = package_dir / "source" / "RuntimeDirectXLoaderFixture.cgl"
            source_path.parent.mkdir()
            source_path.write_text(
                "DXBC suffix mismatch must not parse CrossGL source\n",
                encoding="utf-8",
            )

            with self._guard_crossgl_source_reads():
                plan = plan_directx_source_package_loader(package_dir)
                summary = plan.to_summary()

            directx_admission = summary["directxSourcePackageAdmission"]
            native_admission = directx_admission["nativeBinaryArtifact"]
            reject_reasons = summary["rejectReasons"]
            reject_codes = [diagnostic["code"] for diagnostic in reject_reasons]
            native_suffix_reject = next(
                diagnostic
                for diagnostic in reject_reasons
                if diagnostic["code"]
                == "directx_loader.native_artifact_path_suffix_mismatch"
            )
            descriptor_suffix_reject = next(
                diagnostic
                for diagnostic in reject_reasons
                if diagnostic["code"]
                == (
                    "directx_loader."
                    "native_artifact_descriptor_artifact_path_suffix_mismatch"
                )
            )

            self.assertFalse(plan.loadable)
            self.assertEqual(directx_admission["decision"], "rejected")
            self.assertEqual(
                directx_admission["reason"],
                "directx_loader.native_artifact_path_suffix_mismatch",
            )
            self.assertNotIn("dxilArtifact", directx_admission)
            self.assertEqual(directx_admission["dxbcArtifact"], native_admission)
            self.assertIn(
                "directx_loader.native_artifact_path_suffix_mismatch",
                reject_codes,
            )
            self.assertIn(
                (
                    "directx_loader."
                    "native_artifact_descriptor_artifact_path_suffix_mismatch"
                ),
                reject_codes,
            )
            self.assertEqual(native_suffix_reject["expected"], "*.dxbc")
            self.assertEqual(native_suffix_reject["actual"], native_rel)
            self.assertEqual(descriptor_suffix_reject["expected"], "*.dxbc")
            self.assertEqual(descriptor_suffix_reject["actual"], native_rel)
            self.assertEqual(native_admission["binaryKind"], "directx.dxbc")
            self.assertEqual(native_admission["expectedPathSuffix"], ".dxbc")
            self.assertEqual(native_admission["pathSuffix"], ".dxil")
            self.assertFalse(native_admission["pathSuffixMatchesExpected"])
            self.assertFalse(native_admission["pathSuffixMatchesDxbc"])
            self.assertNotIn("pathSuffixMatchesDxil", native_admission)
            with self.assertRaisesRegex(PackageReadError, r"\.dxbc"):
                plan.require_loadable()
            self.assertEqual(list(package_dir.rglob("*.cgl")), [source_path])

    def test_emitted_source_package_reports_descriptor_manifest_mismatch_detail(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory(suffix=".cglb") as temp_dir:
            package_dir = Path(temp_dir)
            requirements = self._source_package_requirements()
            requirements["requiredPathArtifacts"] = [
                "nativeBinary",
                "backendSource",
            ]
            descriptor_path = "metadata/native-artifact.json"
            native_rel = "backend/directx/RuntimeDirectXLoaderFixture.dxil"
            self._write_valid_directx_package(
                package_dir,
                native_binary_status="emitted",
                package_artifact_requirements=requirements,
            )
            self._write_native_artifact_descriptor(
                package_dir,
                descriptor_path=descriptor_path,
                native_binary_status="emitted",
                validation_status="not-run",
                artifact_path="backend/directx/Other.dxil",
            )
            manifest_path = package_dir / "manifest.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["artifacts"]["nativeArtifactDescriptor"] = descriptor_path
            self._write_json(manifest_path, manifest)
            source_path = package_dir / "source" / "RuntimeDirectXLoaderFixture.cgl"
            source_path.parent.mkdir()
            source_path.write_text(
                "descriptor mismatch must not parse CrossGL source\n",
                encoding="utf-8",
            )

            with self._guard_crossgl_source_reads():
                plan = plan_directx_source_package_loader(package_dir)
                summary = plan.to_summary()

            directx_admission = summary["directxSourcePackageAdmission"]
            descriptor_admission = directx_admission["nativeArtifactDescriptor"]
            diagnostic_codes = [
                diagnostic["code"] for diagnostic in descriptor_admission["diagnostics"]
            ]

            self.assertFalse(plan.loadable)
            self.assertEqual(directx_admission["decision"], "rejected")
            self.assertEqual(
                directx_admission["reason"],
                "package.native_artifact_descriptor.artifact_path_mismatch",
            )
            self.assertFalse(descriptor_admission["manifestConsistent"])
            self.assertEqual(
                descriptor_admission["consistencyStatus"],
                "inconsistent",
            )
            self.assertEqual(
                descriptor_admission["artifactPath"],
                "backend/directx/Other.dxil",
            )
            self.assertEqual(
                descriptor_admission["manifestNativeBinaryPath"],
                native_rel,
            )
            self.assertFalse(descriptor_admission["artifactPathMatchesManifest"])
            self.assertFalse(
                directx_admission["dxilArtifact"]["emittedDescriptorManifestConsistent"]
            )
            self.assertIn(
                "package.native_artifact_descriptor.artifact_path_mismatch",
                diagnostic_codes,
            )
            self.assertEqual(summary["compilerInvocationRequired"], False)
            self.assertEqual(summary["deviceExecutionRequired"], False)
            self.assertEqual(list(package_dir.rglob("*.cgl")), [source_path])

    def test_native_selection_rejects_missing_emitted_native_binary_without_source_fallback(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory(suffix=".cglb") as temp_dir:
            package_dir = Path(temp_dir)
            requirements = self._source_package_requirements()
            requirements["requiredPathArtifacts"] = [
                "nativeBinary",
                "backendSource",
            ]
            self._write_valid_directx_package(
                package_dir,
                native_binary_status="emitted",
                package_artifact_requirements=requirements,
            )
            native_path = (
                package_dir / "backend" / "directx" / "RuntimeDirectXLoaderFixture.dxil"
            )
            native_path.unlink()
            source_path = package_dir / "source" / "RuntimeDirectXLoaderFixture.cgl"
            source_path.parent.mkdir()
            source_path.write_text(
                "missing nativeBinary must not trigger source fallback\n",
                encoding="utf-8",
            )

            with self._guard_source_reads():
                plan = plan_directx_loader(
                    package_dir,
                    package_mode="native",
                )
                native_loader_plan = plan_directx_native_loader(package_dir)

            summary = plan.to_summary()
            selection = summary["runtimeArtifactSelection"]
            self.assertFalse(plan.loadable)
            self.assertIsNone(plan.runtime_artifact)
            self.assertEqual(plan.selected_artifacts, ())
            self.assertEqual(selection["requestedPackageMode"], "native")
            self.assertIsNone(selection["selectedPackageMode"])
            self.assertIsNone(selection["artifact"])
            self.assertIsNone(summary["runtimeArtifactPath"])
            self.assertEqual(summary["selectedArtifacts"], [])
            self.assertEqual(summary["sourceInputs"], [])
            self.assertEqual(summary["metadataContract"]["sourceInputs"], [])
            self.assertEqual(
                summary["compatibilityReport"]["nativeBinaryStatus"],
                "emitted",
            )
            self.assertIn(
                "package.artifact.required_file_missing",
                [diagnostic["code"] for diagnostic in summary["rejectReasons"]],
            )
            with self.assertRaisesRegex(PackageReadError, "nativeBinary"):
                plan.require_loadable()

            native_summary = native_loader_plan.to_summary()
            self.assertFalse(native_loader_plan.ready)
            self.assertIsNone(native_loader_plan.native_artifact)
            self.assertIsNone(native_summary["nativeArtifact"])
            self.assertEqual(native_summary["sourceInputs"], [])
            self.assertIsNone(
                native_summary["runtimePlan"]["runtimeArtifactSelection"]["artifact"]
            )
            self.assertEqual(native_summary["runtimePlan"]["selectedArtifacts"], [])
            self.assertIn(
                "package.artifact.required_file_missing",
                [diagnostic["code"] for diagnostic in native_summary["rejectReasons"]],
            )
            with self.assertRaisesRegex(PackageReadError, "nativeBinary"):
                native_loader_plan.require_ready()
            self.assertEqual(list(package_dir.rglob("*.cgl")), [source_path])

    def test_source_package_rejects_invalid_recorded_requirements_without_source_parse(
        self,
    ) -> None:
        valid_requirements = self._source_package_requirements()
        cases: tuple[tuple[str, dict[str, object], str, str], ...] = (
            (
                "unknown field",
                {**valid_requirements, "artifactFlavor": "compressed"},
                "package.artifact_requirements.unexpected_field",
                "packageArtifactRequirements.artifactFlavor",
            ),
            (
                "malformed source package",
                {
                    **valid_requirements,
                    "requiredPathArtifacts": ["nativeBinary"],
                    "requiresNativeBinaryStatus": False,
                },
                "package.artifact_requirements.source_package_artifact_missing",
                "packageArtifactRequirements.requiredPathArtifacts",
            ),
        )

        for name, requirements, expected_code, expected_path in cases:
            with self.subTest(name=name):
                with tempfile.TemporaryDirectory(suffix=".cglb") as temp_dir:
                    package_dir = Path(temp_dir)
                    self._write_valid_directx_package(
                        package_dir,
                        native_binary_status="planned",
                        package_artifact_requirements=requirements,
                    )
                    source_path = (
                        package_dir / "source" / "RuntimeDirectXLoaderFixture.cgl"
                    )
                    source_path.parent.mkdir()
                    source_path.write_text(
                        "invalid requirements must reject structurally\n",
                        encoding="utf-8",
                    )

                    with self._guard_source_reads():
                        plan = plan_directx_source_package_loader(package_dir)
                        summary = plan.to_summary()

                    reject_codes = [
                        diagnostic["code"] for diagnostic in summary["rejectReasons"]
                    ]
                    self.assertFalse(plan.loadable)
                    self.assertEqual(plan.selected_artifacts, ())
                    self.assertIsNone(plan.runtime_artifact)
                    self.assertFalse(plan.source_parsing_required)
                    self.assertEqual(summary["sourceInputs"], [])
                    self.assertEqual(summary["metadataContract"]["sourceInputs"], [])
                    self.assertIsNone(summary["runtimeArtifactSelection"]["artifact"])
                    self.assertIsNone(
                        summary["compatibilityReport"]["packageArtifactRequirements"]
                    )
                    self.assertIn(expected_code, reject_codes)
                    diagnostic = next(
                        diagnostic
                        for diagnostic in summary["rejectReasons"]
                        if diagnostic["code"] == expected_code
                    )
                    self.assertEqual(diagnostic["document"], "manifest")
                    self.assertEqual(diagnostic["path"], expected_path)
                    self.assertEqual(list(package_dir.rglob("*.cgl")), [source_path])

    def test_source_package_rejects_non_hlsl_backend_source_without_source_parse(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory(suffix=".cglb") as temp_dir:
            package_dir = Path(temp_dir)
            bad_source_rel = "backend/directx/RuntimeDirectXLoaderFixture.txt"
            self._write_valid_directx_package(
                package_dir,
                native_binary_status="planned",
                package_artifact_requirements=self._source_package_requirements(),
            )
            (package_dir / bad_source_rel).write_text(
                "not HLSL by manifest path\n",
                encoding="utf-8",
            )
            manifest_path = package_dir / "manifest.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["artifacts"]["backendSource"] = bad_source_rel
            self._write_json(manifest_path, manifest)
            source_path = package_dir / "source" / "RuntimeDirectXLoaderFixture.cgl"
            source_path.parent.mkdir()
            source_path.write_text(
                "backendSource suffix rejection must stay metadata-only\n",
                encoding="utf-8",
            )

            with self._guard_source_reads():
                plan = plan_directx_source_package_loader(package_dir)
                summary = plan.to_summary()

            diagnostic_code = (
                "directx_loader.source_package_backend_source_suffix_mismatch"
            )
            reject_codes = [
                diagnostic["code"] for diagnostic in summary["rejectReasons"]
            ]
            directx_admission = summary["directxSourcePackageAdmission"]
            diagnostic = next(
                diagnostic
                for diagnostic in summary["rejectReasons"]
                if diagnostic["code"] == diagnostic_code
            )

            self.assertFalse(plan.loadable)
            self.assertEqual(plan.selected_artifacts, ())
            self.assertIsNone(plan.runtime_artifact)
            self.assertFalse(plan.source_parsing_required)
            self.assertEqual(summary["sourceInputs"], [])
            self.assertEqual(summary["metadataContract"]["sourceInputs"], [])
            self.assertIn(diagnostic_code, reject_codes)
            self.assertEqual(diagnostic["document"], "manifest")
            self.assertEqual(diagnostic["artifact"], "backendSource")
            self.assertEqual(diagnostic["path"], bad_source_rel)
            self.assertEqual(diagnostic["expected"], "*.hlsl")
            self.assertEqual(directx_admission["decision"], "rejected")
            self.assertEqual(directx_admission["reason"], diagnostic_code)
            self.assertEqual(
                directx_admission["sourcePackageRuntime"]["path"],
                bad_source_rel,
            )
            self.assertFalse(
                directx_admission["sourcePackageRuntime"]["sourcePackageSelected"]
            )
            with self.assertRaisesRegex(PackageReadError, r"\.hlsl"):
                plan.require_loadable()
            self.assertEqual(list(package_dir.rglob("*.cgl")), [source_path])

    def _write_valid_directx_package(
        self,
        package_dir: Path,
        *,
        include_native_binary: bool = True,
        native_binary_path: str = "backend/directx/RuntimeDirectXLoaderFixture.dxil",
        native_binary_bytes: bytes = b"DXIL",
        native_binary_status: object | None = "emitted",
        package_artifact_requirements: dict[str, object] | None = None,
    ) -> None:
        backend_dir = package_dir / "backend" / "directx"
        backend_dir.mkdir(parents=True)
        source_path = "backend/directx/RuntimeDirectXLoaderFixture.hlsl"
        (package_dir / source_path).write_bytes(DIRECTX_FIXTURE_HLSL_BYTES)
        if include_native_binary:
            native_path = package_dir / native_binary_path
            native_path.parent.mkdir(parents=True, exist_ok=True)
            native_path.write_bytes(native_binary_bytes)

        artifacts: dict[str, object] = {
            "backendSource": source_path,
        }
        if native_binary_status is not None:
            artifacts["nativeBinaryStatus"] = native_binary_status
        if include_native_binary:
            artifacts["nativeBinary"] = native_binary_path

        self._write_package_json(
            package_dir,
            target="directx",
            native_binary_path=native_binary_path,
            artifacts=artifacts,
            package_artifact_requirements=package_artifact_requirements,
            binding={
                "target": "directx",
                "stage": "compute",
                "entryPoint": "runtime_directx_loader_main",
                "name": "OutputBuffer",
                "kind": "storageBuffer",
                "sourceType": "float4",
                "addressSpace": "uav",
                "abi": {"space": 0, "register": "u0"},
                "bindingClass": "uav",
                "descriptorType": "UAV",
                "hlslType": "RWStructuredBuffer<float4>",
            },
        )

    def _write_source_free_directx_package(
        self,
        package_dir: Path,
        *,
        descriptor_path: str,
        descriptor_binary_kind: str = "directx.dxil",
        native_path: str = "backend/directx/RuntimeDirectXLoaderFixture.dxil",
        native_bytes: bytes = b"DXIL",
    ) -> None:
        backend_dir = package_dir / "backend" / "directx"
        backend_dir.mkdir(parents=True)
        (package_dir / native_path).write_bytes(native_bytes)

        self._write_package_json(
            package_dir,
            target="directx",
            native_binary_path=native_path,
            artifacts={
                "nativeBinary": native_path,
                "nativeArtifactDescriptor": descriptor_path,
            },
            package_artifact_requirements={
                "target": "directx",
                "packageMode": "native",
                "requiredPathArtifacts": ["nativeBinary"],
                "requiresNativeBinaryStatus": False,
                "allowsPlannedNativeBinary": False,
                "allowsPlannedNativeSourceEvidence": False,
            },
            binding={
                "target": "directx",
                "stage": "compute",
                "entryPoint": "runtime_directx_loader_main",
                "name": "OutputBuffer",
                "kind": "storageBuffer",
                "sourceType": "float4",
                "addressSpace": "uav",
                "abi": {"space": 0, "register": "u0"},
                "bindingClass": "uav",
                "descriptorType": "UAV",
                "hlslType": "RWStructuredBuffer<float4>",
            },
        )
        self._write_native_artifact_descriptor(
            package_dir,
            descriptor_path=descriptor_path,
            binary_kind=descriptor_binary_kind,
            source_path="source/RuntimeDirectXLoaderFixture.cgl",
            source_bytes=b"CrossGL source bytes intentionally not read by loader",
            artifact_path=native_path,
            artifact_bytes=native_bytes,
            native_binary_status=None,
            validation_status="not-run",
        )

    def _write_valid_vulkan_package(self, package_dir: Path) -> None:
        backend_dir = package_dir / "backend" / "vulkan"
        backend_dir.mkdir(parents=True)
        assembly_path = "backend/vulkan/RuntimeDirectXLoaderFixture.spvasm"
        native_path = "backend/vulkan/RuntimeDirectXLoaderFixture.spv"
        (package_dir / assembly_path).write_text("; SPIR-V\n", encoding="utf-8")
        (package_dir / native_path).write_bytes(b"SPIR-V")
        self._write_package_json(
            package_dir,
            target="vulkan",
            native_binary_path=native_path,
            artifacts={"backendAssembly": assembly_path, "nativeBinary": native_path},
            binding={
                "target": "vulkan",
                "stage": "compute",
                "entryPoint": "runtime_directx_loader_main",
                "name": "OutputBuffer",
                "kind": "storageBuffer",
                "sourceType": "float4",
                "addressSpace": "storage",
                "abi": {"set": 0, "binding": 0},
                "bindingClass": "storage-buffer",
                "descriptorType": "VK_DESCRIPTOR_TYPE_STORAGE_BUFFER",
            },
        )

    def _write_package_json(
        self,
        package_dir: Path,
        *,
        target: str,
        native_binary_path: str,
        artifacts: dict[str, object],
        binding: dict[str, object],
        package_artifact_requirements: dict[str, object] | None = None,
    ) -> None:
        manifest: dict[str, object] = {
            "schemaVersion": 1,
            "compiler": {
                "name": "CrossGL-Compiler",
                "version": "test",
                "llvmVersion": "not-found",
            },
            "module": "RuntimeDirectXLoaderFixture",
            "target": target,
            "sourceHash": {"algorithm": "sha256", "value": "0" * 64},
            "artifacts": artifacts,
        }
        if package_artifact_requirements is not None:
            manifest["packageArtifactRequirements"] = package_artifact_requirements
        self._write_json(package_dir / "manifest.json", manifest)
        self._write_json(
            package_dir / "reflection.json",
            {
                "schemaVersion": 1,
                "module": "RuntimeDirectXLoaderFixture",
                "target": target,
                "nativeBinary": native_binary_path,
                "entryPoints": [
                    {
                        "stage": "compute",
                        "sourceName": "main",
                        "backendName": "runtime_directx_loader_main",
                    }
                ],
                "resources": [
                    {
                        "stage": "compute",
                        "name": "OutputBuffer",
                        "kind": "storageBuffer",
                        "type": "float4",
                        "set": 0,
                        "binding": 0,
                    }
                ],
                "targetResourceBindings": [binding],
                "targetFeatures": [
                    {"target": target, "kind": "package", "name": "fixture"}
                ],
            },
        )
        self._write_json(
            package_dir / "diagnostics.json",
            {"schemaVersion": 1, "diagnostics": []},
        )

    def _write_native_artifact_descriptor(
        self,
        package_dir: Path,
        *,
        descriptor_path: str,
        native_binary_status: str | None = "emitted",
        validation_status: str = "not-run",
        binary_kind: str = "directx.dxil",
        source_path: str = "backend/directx/RuntimeDirectXLoaderFixture.hlsl",
        source_bytes: bytes = DIRECTX_FIXTURE_HLSL_BYTES,
        artifact_path: str = "backend/directx/RuntimeDirectXLoaderFixture.dxil",
        artifact_bytes: bytes = b"DXIL",
    ) -> None:
        descriptor: dict[str, object] = {
            "schemaVersion": 1,
            "kind": "crossgl.nativeArtifact",
            "contractVersion": "native-artifact-v0",
            "target": "directx",
            "binaryKind": binary_kind,
            "sourcePath": source_path,
            "sourceHash": self._sha256(source_bytes),
            "artifactPath": artifact_path,
            "artifactHash": self._sha256(artifact_bytes),
            "sizeBytes": len(artifact_bytes),
            "toolchainProvenance": {
                "producer": "tests.runtime.test_directx_loader",
                "tools": [],
            },
            "optimizationLevel": "unknown",
            "optimizationEvidence": {
                "requestedLevel": "unknown",
                "effectiveLevel": "unknown",
                "policy": "metadata-only",
                "status": "metadata-only",
                "evidenceSource": {"kind": "descriptor"},
            },
            "validationStatus": validation_status,
            "validationDiagnostics": [],
        }
        if native_binary_status is not None:
            descriptor["nativeBinaryStatus"] = native_binary_status
        self._write_json(package_dir / descriptor_path, descriptor)

    def _assert_source_free_directx_descriptor_summary(
        self,
        descriptor_summary: dict[str, object],
        *,
        descriptor_path: str,
        native_path: str,
        absolute_path_prefix: str | None = None,
    ) -> None:
        self.assertIsNotNone(descriptor_summary)
        self.assertTrue(descriptor_summary["readable"])
        self.assertTrue(descriptor_summary["sourcePathDeclared"])
        self.assertEqual(descriptor_summary["artifact"]["path"], descriptor_path)
        if absolute_path_prefix is not None:
            self.assertTrue(
                descriptor_summary["artifact"]["absolutePath"].startswith(
                    absolute_path_prefix
                )
            )
        self.assertEqual(
            descriptor_summary["fields"]["binaryKind"],
            "directx.dxil",
        )
        self.assertEqual(
            descriptor_summary["fields"]["artifactPath"],
            native_path,
        )
        self.assertEqual(
            descriptor_summary["optimizationEvidence"],
            {
                "present": True,
                "wellFormed": True,
                "requestedLevel": "unknown",
                "effectiveLevel": "unknown",
                "policy": "metadata-only",
                "status": "metadata-only",
                "evidenceSource": {"kind": "descriptor"},
            },
        )
        self.assertEqual(
            descriptor_summary["fields"]["optimizationEvidence"]["status"],
            "metadata-only",
        )
        self.assertNotIn("nativeBinaryStatus", descriptor_summary["fields"])
        self.assertEqual(
            descriptor_summary["expectedBinaryKinds"],
            ["directx.dxil", "directx.dxbc"],
        )
        self.assertTrue(descriptor_summary["binaryKindMatchesLoader"])

    def _sha256(self, payload: bytes) -> dict[str, str]:
        return {
            "algorithm": "sha256",
            "value": hashlib.sha256(payload).hexdigest(),
        }

    def _write_json(self, path: Path, document: object) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(document, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )

    def _source_package_requirements(self) -> dict[str, object]:
        return {
            "target": "directx",
            "packageMode": "source-package",
            "requiredPathArtifacts": ["backendSource", "nativeBinary"],
            "requiresNativeBinaryStatus": True,
            "allowsPlannedNativeBinary": True,
            "allowsPlannedNativeSourceEvidence": True,
        }

    def _write_zip_package(
        self,
        package_dir: Path,
        zip_path: Path,
        *,
        prefix: str | None = None,
        exclude: set[str] | None = None,
    ) -> None:
        excluded = set() if exclude is None else set(exclude)
        with zipfile.ZipFile(zip_path, "w") as archive:
            for path in sorted(package_dir.rglob("*")):
                if not path.is_file():
                    continue
                archive_name = path.relative_to(package_dir).as_posix()
                if archive_name in excluded:
                    continue
                if prefix is not None:
                    archive_name = f"{prefix}/{archive_name}"
                archive.write(path, archive_name)

    def _guard_source_reads(self) -> object:
        original_read_text = Path.read_text
        original_read_bytes = Path.read_bytes
        original_open = Path.open
        guarded_suffixes = {".cgl", ".hlsl", ".glsl", ".metal", ".spvasm"}

        def assert_allowed_path(path: Path, action: str) -> None:
            if path.suffix in guarded_suffixes:
                raise AssertionError(f"loader {action} source artifact: {path}")

        def guarded_read_text(path: Path, *args: object, **kwargs: object) -> str:
            assert_allowed_path(path, "parsed")
            return original_read_text(path, *args, **kwargs)

        def guarded_read_bytes(path: Path, *args: object, **kwargs: object) -> bytes:
            assert_allowed_path(path, "parsed")
            return original_read_bytes(path, *args, **kwargs)

        def guarded_open(path: Path, *args: object, **kwargs: object) -> object:
            assert_allowed_path(path, "opened")
            return original_open(path, *args, **kwargs)

        return mock.patch.multiple(
            Path,
            read_text=guarded_read_text,
            read_bytes=guarded_read_bytes,
            open=guarded_open,
        )

    def _guard_crossgl_source_reads(
        self,
        *,
        forbidden_paths: set[Path] | None = None,
    ) -> object:
        original_read_text = Path.read_text
        original_read_bytes = Path.read_bytes
        original_open = Path.open
        forbidden_resolved_paths = frozenset(
            path.resolve() for path in (forbidden_paths or set())
        )

        def assert_allowed_path(path: Path, action: str) -> None:
            if path.resolve() in forbidden_resolved_paths:
                raise AssertionError(f"loader read stale descriptor path: {path}")
            if path.suffix == ".cgl":
                raise AssertionError(f"loader {action} CrossGL source artifact: {path}")

        def guarded_read_text(path: Path, *args: object, **kwargs: object) -> str:
            assert_allowed_path(path, "parsed")
            return original_read_text(path, *args, **kwargs)

        def guarded_read_bytes(path: Path, *args: object, **kwargs: object) -> bytes:
            assert_allowed_path(path, "parsed")
            return original_read_bytes(path, *args, **kwargs)

        def guarded_open(path: Path, *args: object, **kwargs: object) -> object:
            assert_allowed_path(path, "opened")
            return original_open(path, *args, **kwargs)

        return mock.patch.multiple(
            Path,
            read_text=guarded_read_text,
            read_bytes=guarded_read_bytes,
            open=guarded_open,
        )

    def _guard_crossgl_source_archive_reads(self) -> object:
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
                raise AssertionError(f"loader opened CrossGL archive member: {member}")
            return original_open(archive, name, *args, **kwargs)

        def guarded_read(
            archive: zipfile.ZipFile,
            name: object,
            *args: object,
            **kwargs: object,
        ) -> object:
            member = member_name(name)
            if Path(member).suffix == ".cgl":
                raise AssertionError(f"loader read CrossGL archive member: {member}")
            return original_read(archive, name, *args, **kwargs)

        return mock.patch.multiple(
            zipfile.ZipFile,
            open=guarded_open,
            read=guarded_read,
        )

    def _guard_source_archive_reads(self) -> object:
        original_open = zipfile.ZipFile.open
        original_read = zipfile.ZipFile.read
        guarded_suffixes = {".cgl", ".hlsl", ".glsl", ".metal", ".spvasm"}

        def member_name(name: object) -> str:
            return str(getattr(name, "filename", name))

        def guarded_open(
            archive: zipfile.ZipFile,
            name: object,
            *args: object,
            **kwargs: object,
        ) -> object:
            member = member_name(name)
            if Path(member).suffix in guarded_suffixes:
                raise AssertionError(f"loader parsed source archive member: {member}")
            return original_open(archive, name, *args, **kwargs)

        def guarded_read(
            archive: zipfile.ZipFile,
            name: object,
            *args: object,
            **kwargs: object,
        ) -> object:
            member = member_name(name)
            if Path(member).suffix in guarded_suffixes:
                raise AssertionError(f"loader parsed source archive member: {member}")
            return original_read(archive, name, *args, **kwargs)

        return mock.patch.multiple(
            zipfile.ZipFile,
            open=guarded_open,
            read=guarded_read,
        )


if __name__ == "__main__":
    unittest.main()
