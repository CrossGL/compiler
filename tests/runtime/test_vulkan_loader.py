#!/usr/bin/env python3
from __future__ import annotations

import builtins
from collections.abc import Iterator
import contextlib
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


from runtime.package_reader import PackageReadError  # noqa: E402
from runtime.package_reader import read_compatibility_report  # noqa: E402
from runtime.package_reader import select_runtime_artifact  # noqa: E402
from runtime.loader import read_loader_plan  # noqa: E402
from runtime.vulkan_loader import plan_vulkan_native_loader  # noqa: E402


class VulkanNativeLoaderPlanTests(unittest.TestCase):
    def test_ready_plan_uses_native_artifact_without_source_parse(self) -> None:
        with tempfile.TemporaryDirectory(suffix=".cglb") as temp_dir:
            package_dir = Path(temp_dir)
            self._write_valid_vulkan_package(
                package_dir,
                include_backend_source=True,
                include_native_profile=True,
            )
            source_path = package_dir / "source" / "invalid.cgl"
            source_path.parent.mkdir()
            source_path.write_text("must not parse source\n", encoding="utf-8")

            with self._guard_source_reads(), self._guard_compiler_and_device_work():
                plan = plan_vulkan_native_loader(package_dir)
                summary = plan.to_summary()

            self.assertTrue(plan.ready, summary["diagnostics"])
            self.assertIs(plan.require_ready(), plan)
            self.assertEqual(plan.status, "ready")
            self.assertFalse(plan.source_parsing_required)
            self.assertFalse(plan.device_execution_required)
            self.assertEqual(summary["loader"], "vulkan-native")
            self.assertEqual(summary["target"], "vulkan")
            self.assertEqual(summary["sourceInputs"], [])
            self.assertEqual(summary["compilerInvocationRequired"], False)
            self.assertEqual(summary["deviceExecutionRequired"], False)
            self.assertEqual(plan.native_artifact.name, "nativeBinary")
            self.assertEqual(
                plan.native_artifact.package_path,
                "backend/vulkan/RuntimeVulkanLoaderFixture.spv",
            )
            self.assertEqual(summary["nativeArtifact"]["name"], "nativeBinary")
            self.assertEqual(
                summary["nativeArtifact"]["path"],
                "backend/vulkan/RuntimeVulkanLoaderFixture.spv",
            )
            self.assertEqual(
                [
                    (artifact["name"], artifact["exists"])
                    for artifact in summary["artifactInputs"]
                ],
                [("backendAssembly", True), ("nativeBinary", True)],
            )
            runtime_summary = summary["runtimePlan"]
            metadata_contract = runtime_summary["metadataContract"]
            runtime_selection = runtime_summary["runtimeArtifactSelection"]
            self.assertEqual(
                summary["targetLegalizationEvidence"],
                runtime_summary["targetLegalizationEvidence"],
            )
            self.assertEqual(
                summary["targetLegalizationToolRequirements"],
                runtime_summary["targetLegalizationToolRequirements"],
            )
            self.assertEqual(
                summary["nativeAdmission"]["targetLegalizationEvidence"],
                summary["targetLegalizationEvidence"],
            )
            self.assertEqual(
                summary["nativeAdmission"]["targetLegalizationToolRequirements"],
                summary["targetLegalizationToolRequirements"],
            )
            self.assertEqual(runtime_summary["loaderTarget"], "vulkan")
            self.assertEqual(runtime_summary["packageTarget"], "vulkan")
            self.assertEqual(runtime_summary["selectedTarget"], "vulkan")
            self.assertEqual(runtime_summary["sourceInputs"], [])
            self.assertEqual(runtime_summary["compilerInvocationRequired"], False)
            self.assertEqual(runtime_summary["deviceExecutionRequired"], False)
            self.assertEqual(
                runtime_summary["requiredArtifactPaths"],
                {
                    "backendAssembly": (
                        "backend/vulkan/RuntimeVulkanLoaderFixture.spvasm"
                    ),
                    "nativeBinary": ("backend/vulkan/RuntimeVulkanLoaderFixture.spv"),
                },
            )
            self.assertEqual(
                runtime_summary["artifactCompatibility"]["selectedArtifact"],
                "nativeBinary",
            )
            self.assertEqual(
                runtime_selection["requestedPackageMode"],
                "native",
            )
            self.assertEqual(runtime_selection["selectedPackageMode"], "native")
            self.assertEqual(runtime_selection["artifact"]["name"], "nativeBinary")
            self.assertEqual(
                runtime_selection["artifact"]["path"],
                "backend/vulkan/RuntimeVulkanLoaderFixture.spv",
            )
            self.assertEqual(metadata_contract["loaderTarget"], "vulkan")
            self.assertEqual(metadata_contract["packageTarget"], "vulkan")
            self.assertEqual(metadata_contract["sourceInputs"], [])
            self.assertEqual(
                metadata_contract["compilerInvocationRequired"],
                False,
            )
            self.assertEqual(metadata_contract["deviceExecutionRequired"], False)
            self.assertEqual(
                metadata_contract["runtimeArtifact"],
                {
                    "name": "nativeBinary",
                    "path": "backend/vulkan/RuntimeVulkanLoaderFixture.spv",
                    "declaredBy": "manifest.artifacts.nativeBinary",
                },
            )
            self.assertEqual(
                [
                    artifact["name"]
                    for artifact in metadata_contract["requiredArtifactInputs"]
                ],
                ["backendAssembly", "nativeBinary"],
            )
            self.assertEqual(
                [
                    artifact["name"]
                    for artifact in metadata_contract["selectedArtifactInputs"]
                ],
                ["backendAssembly", "nativeBinary"],
            )
            self.assertNotIn(
                "backendSource",
                [
                    artifact["name"]
                    for artifact in metadata_contract["selectedArtifactInputs"]
                ],
            )
            self.assertEqual(summary["reflection"]["entryPointCount"], 1)
            self.assertEqual(summary["reflection"]["resourceCount"], 1)
            self.assertEqual(summary["reflection"]["targetResourceBindingCount"], 1)
            self.assertEqual(
                summary["reflection"]["targetResourceBindings"][0]["abi"],
                {"set": 0, "binding": 0},
            )
            self.assertEqual(
                summary["reflection"]["targetResourceBindings"][0]["evidenceId"],
                (
                    "target-legalization.v1.vulkan.resource-binding.compute."
                    "runtime_vulkan_loader_main.OutputBuffer"
                ),
            )
            self.assertEqual(
                summary["reflection"]["targetResourceBindings"][0]["descriptorType"],
                "VK_DESCRIPTOR_TYPE_STORAGE_BUFFER",
            )
            compatibility_artifacts = {
                artifact["name"]: artifact
                for artifact in runtime_summary["compatibilityReport"][
                    "availableArtifacts"
                ]
            }
            self.assertIn("backendSource", compatibility_artifacts)
            self.assertTrue(compatibility_artifacts["backendSource"]["exists"])
            self.assertIn("nativeProfile", compatibility_artifacts)
            native_profile = self._artifact_compatibility_record(
                runtime_summary["artifactCompatibility"],
                "nativeProfile",
            )
            self.assertEqual(native_profile["decision"], "skipped")
            self.assertEqual(native_profile["reason"], "package.artifact.not_required")
            self.assertFalse(native_profile["selected"])
            vulkan_admission = summary["vulkanNativeAdmission"]
            self.assertEqual(vulkan_admission["decision"], "accepted")
            self.assertEqual(
                vulkan_admission["reason"],
                "vulkan_loader.native_spv_admission.accepted",
            )
            self.assertFalse(vulkan_admission["sourceParsingRequired"])
            self.assertFalse(vulkan_admission["compilerInvocationRequired"])
            self.assertFalse(vulkan_admission["deviceExecutionRequired"])
            self.assertEqual(
                vulkan_admission["targetLegalizationEvidence"],
                summary["targetLegalizationEvidence"],
            )
            self.assertEqual(
                vulkan_admission["targetLegalizationToolRequirements"],
                summary["targetLegalizationToolRequirements"],
            )
            self.assertEqual(
                vulkan_admission["packageArtifactRequirementsSource"],
                summary["packageArtifactRequirementsSource"],
            )
            self.assertEqual(
                vulkan_admission["packageArtifactRequirements"],
                summary["packageArtifactRequirements"],
            )
            self.assertEqual(
                summary["vulkanNativeApiBoundary"]["targetLegalizationEvidence"],
                summary["targetLegalizationEvidence"],
            )
            self.assertEqual(
                summary["vulkanNativeApiBoundary"][
                    "targetLegalizationToolRequirements"
                ],
                summary["targetLegalizationToolRequirements"],
            )
            self.assertEqual(
                summary["vulkanNativeApiBoundary"]["packageArtifactRequirementsSource"],
                summary["packageArtifactRequirementsSource"],
            )
            self.assertEqual(
                summary["vulkanNativeApiBoundary"]["packageArtifactRequirements"],
                summary["packageArtifactRequirements"],
            )
            self.assertTrue(vulkan_admission["requiredChecksPassed"])
            self.assertEqual(vulkan_admission["blockedByDiagnostics"], [])
            spirv_admission = vulkan_admission["spirvArtifact"]
            self.assertTrue(spirv_admission["declared"])
            self.assertTrue(spirv_admission["exists"])
            self.assertTrue(spirv_admission["selectedForRuntime"])
            self.assertTrue(spirv_admission["acceptedForLoad"])
            self.assertEqual(
                spirv_admission["path"],
                "backend/vulkan/RuntimeVulkanLoaderFixture.spv",
            )
            self.assertEqual(spirv_admission["expectedPathSuffix"], ".spv")
            self.assertEqual(spirv_admission["pathSuffix"], ".spv")
            self.assertTrue(spirv_admission["pathSuffixMatchesSpv"])
            self.assertEqual(
                spirv_admission["expectedBinaryKind"],
                "vulkan.spirv-module",
            )
            expected_spv_hash = self._sha256(b"SPIR-V")
            self.assertEqual(
                spirv_admission["descriptorArtifactHash"],
                expected_spv_hash,
            )
            self.assertTrue(spirv_admission["descriptorArtifactHashMatchesSpirv"])
            descriptor_admission = vulkan_admission["nativeArtifactDescriptor"]
            self.assertTrue(descriptor_admission["declared"])
            self.assertTrue(descriptor_admission["readable"])
            self.assertEqual(descriptor_admission["artifactHash"], expected_spv_hash)
            self.assertTrue(descriptor_admission["artifactHashMatchesArtifact"])
            profile_admission = vulkan_admission["nativeProfile"]
            self.assertTrue(profile_admission["declared"])
            self.assertTrue(profile_admission["readable"])
            self.assertEqual(profile_admission["target"], "vulkan")
            self.assertTrue(profile_admission["targetMatchesLoader"])
            self.assertEqual(
                profile_admission["nativeBinary"],
                "backend/vulkan/RuntimeVulkanLoaderFixture.spv",
            )
            self.assertTrue(profile_admission["nativeBinaryMatchesNativeArtifact"])
            self.assertEqual(
                profile_admission["backendAssembly"],
                "backend/vulkan/RuntimeVulkanLoaderFixture.spvasm",
            )
            self.assertTrue(profile_admission["backendAssemblyMatchesManifest"])
            self.assertEqual(
                profile_admission["disassembly"]["status"],
                "skipped-tool-missing",
            )
            checks = {check["name"]: check for check in vulkan_admission["checks"]}
            self.assertTrue(checks["nativeBinaryPathSuffixMatchesSpv"]["passed"])
            self.assertTrue(checks["nativeProfileTargetMatchesLoader"]["passed"])
            self.assertTrue(
                checks["nativeProfileNativeBinaryMatchesNativeArtifact"]["passed"]
            )
            self.assertTrue(
                checks["nativeArtifactDescriptorArtifactHashDeclared"]["passed"]
            )
            self.assertTrue(
                checks["nativeArtifactDescriptorArtifactHashMatchesSpirv"]["passed"]
            )
            api_boundary = summary["vulkanNativeApiBoundary"]
            self.assertEqual(api_boundary["boundary"], "vulkan.native-api.metadata-v0")
            self.assertEqual(api_boundary["decision"], "accepted")
            self.assertFalse(api_boundary["vulkanRuntimeCallsPerformed"])
            self.assertFalse(api_boundary["vulkanShaderModuleCreationPerformed"])
            self.assertEqual(
                api_boundary["runtimeInputs"]["spirvArtifact"]["path"],
                "backend/vulkan/RuntimeVulkanLoaderFixture.spv",
            )
            self.assertEqual(
                api_boundary["runtimeInputs"]["spirvArtifact"][
                    "descriptorArtifactHash"
                ],
                expected_spv_hash,
            )
            self.assertTrue(
                api_boundary["runtimeInputs"]["spirvArtifact"][
                    "descriptorArtifactHashMatchesSpirv"
                ]
            )
            self.assertEqual(
                api_boundary["runtimeInputs"]["versionCompatibility"],
                summary["runtimePlan"]["versionCompatibility"],
            )
            self.assertTrue(api_boundary["descriptorFreshness"]["artifactHashDeclared"])
            self.assertTrue(
                api_boundary["descriptorFreshness"]["artifactHashMatchesSpirv"]
            )
            self.assertTrue(
                api_boundary["nativeProfileCompatibility"]["targetMatchesLoader"]
            )
            self.assertEqual(summary["rejectReasons"], [])
            self.assertEqual(list(package_dir.rglob("*.cgl")), [source_path])

    def test_ready_plan_summarizes_flat_vulkan_binding_evidence_without_source_parse(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory(suffix=".cglb") as temp_dir:
            package_dir = Path(temp_dir)
            self._write_valid_vulkan_package(package_dir)
            reflection_path = package_dir / "reflection.json"
            reflection = json.loads(reflection_path.read_text(encoding="utf-8"))
            evidence_id = (
                "target-legalization.v1.vulkan.resource-binding.compute."
                "runtime_vulkan_loader_main.OutputBuffer"
            )
            binding = reflection["targetResourceBindings"][0]
            binding.update(
                {
                    "abi": "descriptor",
                    "set": 0,
                    "binding": 0,
                    "evidenceId": evidence_id,
                }
            )
            self._write_json(reflection_path, reflection)
            source_path = package_dir / "source" / "invalid.cgl"
            source_path.parent.mkdir()
            source_path.write_text(
                "runtime must not parse CrossGL source for flat ABI evidence\n",
                encoding="utf-8",
            )

            with self._guard_source_reads(), self._guard_compiler_and_device_work():
                plan = plan_vulkan_native_loader(package_dir)
                summary = plan.to_summary()

            binding_summary = summary["reflection"]["targetResourceBindings"][0]
            api_binding_summary = summary["vulkanNativeApiBoundary"]["runtimeInputs"][
                "reflection"
            ]["targetResourceBindings"][0]

            self.assertTrue(plan.ready, summary["diagnostics"])
            self.assertFalse(plan.source_parsing_required)
            self.assertEqual(binding_summary["abi"], "descriptor")
            self.assertEqual(binding_summary["set"], 0)
            self.assertEqual(binding_summary["binding"], 0)
            self.assertEqual(binding_summary["evidenceId"], evidence_id)
            self.assertEqual(api_binding_summary["abiKind"], "descriptor")
            self.assertEqual(api_binding_summary["evidenceId"], evidence_id)
            self.assertEqual(list(package_dir.rglob("*.cgl")), [source_path])

    def test_ready_plan_accepts_generated_native_profile_artifact_map(self) -> None:
        with tempfile.TemporaryDirectory(suffix=".cglb") as temp_dir:
            package_dir = Path(temp_dir)
            self._write_valid_vulkan_package(
                package_dir,
                include_backend_source=True,
                include_native_profile=True,
            )
            profile_path = (
                package_dir
                / "backend"
                / "vulkan"
                / "RuntimeVulkanLoaderFixture.profile.json"
            )
            profile = json.loads(profile_path.read_text(encoding="utf-8"))
            backend_assembly = profile.pop("backendAssembly")
            native_binary = profile.pop("nativeBinary")
            profile["artifacts"] = {
                "backendAssembly": backend_assembly,
                "nativeBinary": native_binary,
            }
            self._write_json(profile_path, profile)
            source_path = package_dir / "source" / "generated-profile.cgl"
            source_path.parent.mkdir(exist_ok=True)
            source_path.write_text(
                "generated profile admission must stay metadata-only\n",
                encoding="utf-8",
            )

            with self._guard_source_reads(), self._guard_compiler_and_device_work():
                plan = plan_vulkan_native_loader(package_dir)
                summary = plan.to_summary()

            self.assertTrue(plan.ready, summary["diagnostics"])
            self.assertEqual(summary["rejectReasons"], [])
            self.assertEqual(
                summary["vulkanNativeProfile"]["fields"]["artifacts"],
                {
                    "backendAssembly": (
                        "backend/vulkan/RuntimeVulkanLoaderFixture.spvasm"
                    ),
                    "nativeBinary": ("backend/vulkan/RuntimeVulkanLoaderFixture.spv"),
                },
            )
            profile_admission = summary["vulkanNativeAdmission"]["nativeProfile"]
            self.assertEqual(
                profile_admission["backendAssembly"],
                "backend/vulkan/RuntimeVulkanLoaderFixture.spvasm",
            )
            self.assertEqual(
                profile_admission["nativeBinary"],
                "backend/vulkan/RuntimeVulkanLoaderFixture.spv",
            )
            self.assertTrue(profile_admission["backendAssemblyMatchesManifest"])
            self.assertTrue(profile_admission["nativeBinaryMatchesNativeArtifact"])
            self.assertTrue(
                summary["vulkanNativeApiBoundary"]["nativeProfileCompatibility"][
                    "nativeBinaryMatchesSpirv"
                ]
            )
            self.assertEqual(list(package_dir.rglob("*.cgl")), [source_path])

    def test_graphics_stage_closure_reports_vertex_fragment_pair(self) -> None:
        with tempfile.TemporaryDirectory(suffix=".cglb") as temp_dir:
            package_dir = Path(temp_dir)
            self._write_valid_vulkan_package(package_dir)
            reflection_path = package_dir / "reflection.json"
            reflection = json.loads(reflection_path.read_text(encoding="utf-8"))
            reflection["entryPoints"] = [
                {
                    "stage": "vertex",
                    "sourceName": "main",
                    "backendName": "vertex_main",
                },
                {
                    "stage": "fragment",
                    "sourceName": "main",
                    "backendName": "fragment_main",
                },
            ]
            reflection["resources"] = [
                {
                    "stage": "fragment",
                    "name": "shadowMap",
                    "kind": "texture",
                    "type": "sampler2DShadow",
                    "set": 0,
                    "binding": 2,
                },
                {
                    "stage": "fragment",
                    "name": "shadowSampler",
                    "kind": "sampler",
                    "type": "comparison_sampler",
                    "set": 0,
                    "binding": 3,
                },
            ]
            reflection["targetResourceBindings"] = [
                {
                    "target": "vulkan",
                    "stage": "fragment",
                    "entryPoint": "fragment_main",
                    "name": "shadowMap",
                    "kind": "texture",
                    "sourceType": "sampler2DShadow",
                    "addressSpace": "UniformConstant",
                    "abi": {"set": 0, "binding": 2},
                    "bindingClass": "sampledImage",
                    "descriptorType": "VK_DESCRIPTOR_TYPE_SAMPLED_IMAGE",
                    "storageClass": "UniformConstant",
                    "spirvType": "OpTypeImage<depth_compare, 2D, sampled=1>",
                },
                {
                    "target": "vulkan",
                    "stage": "fragment",
                    "entryPoint": "fragment_main",
                    "name": "shadowSampler",
                    "kind": "sampler",
                    "sourceType": "comparison_sampler",
                    "addressSpace": "UniformConstant",
                    "abi": {"set": 0, "binding": 3},
                    "bindingClass": "sampler",
                    "descriptorType": "VK_DESCRIPTOR_TYPE_SAMPLER",
                    "storageClass": "UniformConstant",
                    "spirvType": "OpTypeSampler",
                },
            ]
            self._write_json(reflection_path, reflection)
            source_path = package_dir / "source" / "invalid.cgl"
            source_path.parent.mkdir()
            source_path.write_text(
                "graphics closure must not trigger source parsing\n",
                encoding="utf-8",
            )

            with self._guard_source_reads(), self._guard_compiler_and_device_work():
                plan = plan_vulkan_native_loader(package_dir)
                summary = plan.to_summary()

            self.assertTrue(plan.ready, summary["diagnostics"])
            closure = summary["vulkanNativeAdmission"]["reflection"][
                "graphicsStageClosure"
            ]
            self.assertTrue(closure["graphicsPackage"])
            self.assertEqual(closure["stageCounts"], {"vertex": 1, "fragment": 1})
            self.assertTrue(closure["hasVertexFragmentPair"])
            self.assertTrue(closure["hasOnlyGraphicsStages"])
            self.assertEqual(closure["vertexEntryPoint"]["backendName"], "vertex_main")
            self.assertEqual(
                closure["fragmentEntryPoint"]["backendName"],
                "fragment_main",
            )
            checks = {
                check["name"]: check
                for check in summary["vulkanNativeAdmission"]["checks"]
            }
            self.assertTrue(
                checks["reflectionGraphicsVertexFragmentPairPresent"]["passed"]
            )
            self.assertTrue(
                checks["reflectionGraphicsStagesOnlyVertexFragment"]["passed"]
            )
            api_reflection = summary["vulkanNativeApiBoundary"]["runtimeInputs"][
                "reflection"
            ]
            self.assertTrue(
                api_reflection["graphicsStageClosure"]["hasVertexFragmentPair"]
            )
            self.assertEqual(list(package_dir.rglob("*.cgl")), [source_path])

    def test_source_free_native_artifact_with_spirv_dependencies_remains_loadable(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory(suffix=".cglb") as temp_dir:
            package_dir = Path(temp_dir)
            descriptor_path = "metadata/native-artifact.json"
            self._write_source_free_vulkan_package(
                package_dir,
                descriptor_path=descriptor_path,
            )
            descriptor_file = package_dir / descriptor_path
            descriptor = json.loads(descriptor_file.read_text(encoding="utf-8"))
            spirv_dependencies = {
                "extendedInstructionSets": [
                    {
                        "resultId": "%glsl_std_450",
                        "instructionSet": "GLSL.std.450",
                    }
                ]
            }
            descriptor["spirvDependencies"] = spirv_dependencies
            self._write_json(descriptor_file, descriptor)
            source_path = package_dir / "source" / "RuntimeVulkanLoaderFixture.cgl"
            source_path.parent.mkdir()
            source_path.write_text(
                "SPIR-V dependency metadata must not trigger source parsing\n",
                encoding="utf-8",
            )

            with self._guard_source_reads(), self._guard_compiler_and_device_work():
                plan = plan_vulkan_native_loader(package_dir)
                summary = plan.to_summary()

            descriptor_summary = summary["nativeArtifactDescriptor"]
            descriptor_admission = summary["nativeAdmission"][
                "nativeArtifactDescriptor"
            ]

            self.assertTrue(plan.ready, summary["diagnostics"])
            self.assertIs(plan.require_ready(), plan)
            self.assertEqual(summary["rejectReasons"], [])
            self.assertEqual(summary["sourceInputs"], [])
            self.assertEqual(summary["compilerInvocationRequired"], False)
            self.assertEqual(summary["deviceExecutionRequired"], False)
            self.assertEqual(
                summary["runtimePlan"]["runtimeArtifactSelection"][
                    "selectedPackageMode"
                ],
                "native",
            )
            self.assertEqual(plan.native_artifact.name, "nativeBinary")
            self.assertEqual(
                descriptor_summary["fields"]["spirvDependencies"],
                spirv_dependencies,
            )
            self.assertEqual(
                descriptor_admission["fields"]["spirvDependencies"],
                spirv_dependencies,
            )
            self.assertEqual(descriptor_admission["decision"], "accepted")
            self.assertEqual(
                summary["vulkanNativeAdmission"]["decision"],
                "accepted",
            )
            self.assertEqual(list(package_dir.rglob("*.cgl")), [source_path])

    def test_runtime_selection_native_and_auto_select_spv_but_source_package_rejects(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory(suffix=".cglb") as temp_dir:
            package_dir = Path(temp_dir)
            self._write_valid_vulkan_package(
                package_dir,
                include_backend_source=True,
            )
            source_path = package_dir / "source" / "invalid.cgl"
            source_path.parent.mkdir()
            source_path.write_text(
                "source-package rejection must not parse source\n",
                encoding="utf-8",
            )

            with self._guard_source_reads(), self._guard_compiler_and_device_work():
                report = read_compatibility_report(
                    package_dir,
                    loader_target="vulkan",
                )
                native_selection = select_runtime_artifact(
                    report,
                    target="vulkan",
                    package_mode="native",
                )
                auto_selection = select_runtime_artifact(report, target="vulkan")
                source_plan = read_loader_plan(
                    package_dir,
                    "vulkan",
                    package_mode="source-package",
                )
                source_summary = source_plan.to_summary()

            self.assertTrue(native_selection.selected)
            self.assertEqual(native_selection.selected_package_mode, "native")
            self.assertEqual(native_selection.require_selected().name, "nativeBinary")
            self.assertEqual(
                native_selection.require_selected().package_path,
                "backend/vulkan/RuntimeVulkanLoaderFixture.spv",
            )
            self.assertTrue(auto_selection.selected)
            self.assertEqual(auto_selection.requested_package_mode, "auto")
            self.assertEqual(auto_selection.selected_package_mode, "native")
            self.assertEqual(auto_selection.require_selected().name, "nativeBinary")
            self.assertFalse(source_plan.loadable)
            self.assertEqual(source_summary["selectedTarget"], None)
            self.assertEqual(source_summary["sourceInputs"], [])
            self.assertEqual(source_summary["compilerInvocationRequired"], False)
            self.assertEqual(source_summary["deviceExecutionRequired"], False)
            self.assertEqual(
                source_summary["runtimeArtifactSelection"]["requestedPackageMode"],
                "source-package",
            )
            self.assertIsNone(
                source_summary["runtimeArtifactSelection"]["selectedPackageMode"]
            )
            self.assertIsNone(source_summary["runtimeArtifactSelection"]["artifact"])
            self.assertEqual(source_summary["runtimeArtifactPath"], None)
            self.assertEqual(source_summary["selectedArtifacts"], [])
            self.assertEqual(
                source_summary["requiredArtifactPaths"],
                {
                    "backendAssembly": (
                        "backend/vulkan/RuntimeVulkanLoaderFixture.spvasm"
                    ),
                    "nativeBinary": ("backend/vulkan/RuntimeVulkanLoaderFixture.spv"),
                },
            )
            self.assertIn(
                "package.mode.unsupported",
                [diagnostic["code"] for diagnostic in source_summary["rejectReasons"]],
            )
            self.assertNotEqual(
                source_summary["runtimeArtifactPath"],
                "backend/vulkan/RuntimeVulkanLoaderFixture.glsl",
            )
            self.assertEqual(list(package_dir.rglob("*.cgl")), [source_path])

    def test_ready_zip_plan_uses_native_artifact_and_descriptor_without_source_parse(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir)
            package_dir = temp_root / "package-dir"
            package_dir.mkdir()
            descriptor_path = (
                "backend/vulkan/RuntimeVulkanLoaderFixture.native-artifact.json"
            )
            self._write_source_free_vulkan_package(
                package_dir,
                descriptor_path=descriptor_path,
            )
            source_path = package_dir / "source" / "RuntimeVulkanLoaderFixture.cgl"
            source_path.parent.mkdir()
            source_path.write_text(
                "zip loader must not parse CrossGL source\n",
                encoding="utf-8",
            )
            zip_path = temp_root / "RuntimeVulkanLoaderFixture.cglb"
            self._write_zip_package(
                package_dir,
                zip_path,
                prefix=zip_path.name,
            )

            with (
                self._guard_crossgl_source_reads(),
                self._guard_source_archive_reads(),
                self._guard_compiler_and_device_work(),
            ):
                plan = plan_vulkan_native_loader(zip_path)
                summary = plan.to_summary()

            descriptor_summary = summary["nativeArtifactDescriptor"]
            runtime_summary = summary["runtimePlan"]
            metadata_contract = runtime_summary["metadataContract"]
            runtime_selection = runtime_summary["runtimeArtifactSelection"]
            self.assertTrue(plan.ready, summary["diagnostics"])
            self.assertIs(plan.require_ready(), plan)
            self.assertFalse(plan.source_parsing_required)
            self.assertFalse(plan.device_execution_required)
            self.assertEqual(plan.status, "ready")
            self.assertEqual(summary["loader"], "vulkan-native")
            self.assertEqual(summary["target"], "vulkan")
            self.assertEqual(runtime_summary["packageFormat"], "zip")
            self.assertEqual(summary["sourceInputs"], [])
            self.assertEqual(summary["compilerInvocationRequired"], False)
            self.assertEqual(summary["deviceExecutionRequired"], False)
            self.assertEqual(summary["rejectReasons"], [])
            self.assertIsNotNone(plan.native_artifact)
            self.assertEqual(plan.native_artifact.archive_path, zip_path)
            self.assertEqual(
                plan.native_artifact.archive_member,
                f"{zip_path.name}/backend/vulkan/RuntimeVulkanLoaderFixture.spv",
            )
            self.assertTrue(
                summary["nativeArtifact"]["absolutePath"].startswith(f"{zip_path}!/")
            )
            self.assertEqual(summary["nativeArtifact"]["name"], "nativeBinary")
            self.assertEqual(
                summary["nativeArtifact"]["path"],
                "backend/vulkan/RuntimeVulkanLoaderFixture.spv",
            )
            self.assertEqual(
                summary["nativeAdmission"]["packageArtifactRequirementsSource"],
                summary["packageArtifactRequirementsSource"],
            )
            self.assertEqual(
                summary["nativeAdmission"]["packageArtifactRequirements"],
                summary["packageArtifactRequirements"],
            )
            self.assertEqual(
                summary["vulkanNativeAdmission"]["packageArtifactRequirementsSource"],
                summary["packageArtifactRequirementsSource"],
            )
            self.assertEqual(
                summary["vulkanNativeAdmission"]["packageArtifactRequirements"],
                summary["packageArtifactRequirements"],
            )
            self.assertEqual(
                summary["vulkanNativeApiBoundary"]["packageArtifactRequirementsSource"],
                summary["packageArtifactRequirementsSource"],
            )
            self.assertEqual(
                summary["vulkanNativeApiBoundary"]["packageArtifactRequirements"],
                summary["packageArtifactRequirements"],
            )
            self.assertEqual(
                [
                    (artifact["name"], artifact["path"], artifact["exists"])
                    for artifact in summary["artifactInputs"]
                ],
                [
                    (
                        "nativeBinary",
                        "backend/vulkan/RuntimeVulkanLoaderFixture.spv",
                        True,
                    )
                ],
            )
            self.assertEqual(runtime_summary["sourceInputs"], [])
            self.assertEqual(runtime_summary["compilerInvocationRequired"], False)
            self.assertEqual(runtime_summary["deviceExecutionRequired"], False)
            self.assertEqual(runtime_summary["sourceParsingRequired"], False)
            self.assertEqual(runtime_summary["requiredArtifacts"], ["nativeBinary"])
            self.assertEqual(
                runtime_summary["requiredArtifactPaths"],
                {"nativeBinary": "backend/vulkan/RuntimeVulkanLoaderFixture.spv"},
            )
            self.assertEqual(runtime_selection["requestedPackageMode"], "native")
            self.assertEqual(runtime_selection["selectedPackageMode"], "native")
            self.assertEqual(runtime_selection["artifact"]["name"], "nativeBinary")
            self.assertEqual(
                runtime_selection["artifact"]["path"],
                "backend/vulkan/RuntimeVulkanLoaderFixture.spv",
            )
            self.assertEqual(metadata_contract["sourceInputs"], [])
            self.assertEqual(metadata_contract["compilerInvocationRequired"], False)
            self.assertEqual(metadata_contract["deviceExecutionRequired"], False)
            self.assertEqual(
                metadata_contract["requiredArtifactInputs"],
                [
                    {
                        "name": "nativeBinary",
                        "path": "backend/vulkan/RuntimeVulkanLoaderFixture.spv",
                        "declaredBy": "manifest.artifacts.nativeBinary",
                    }
                ],
            )
            self.assertEqual(
                [
                    (artifact["name"], artifact["selectedForLoad"])
                    for artifact in metadata_contract["selectedArtifactInputs"]
                ],
                [("nativeBinary", True)],
            )
            self.assertEqual(
                metadata_contract["runtimeArtifact"],
                {
                    "name": "nativeBinary",
                    "path": "backend/vulkan/RuntimeVulkanLoaderFixture.spv",
                    "declaredBy": "manifest.artifacts.nativeBinary",
                },
            )
            self.assertIsNotNone(descriptor_summary)
            self.assertTrue(descriptor_summary["readable"])
            self.assertTrue(descriptor_summary["sourcePathDeclared"])
            self.assertEqual(descriptor_summary["artifact"]["path"], descriptor_path)
            self.assertTrue(
                descriptor_summary["artifact"]["absolutePath"].startswith(
                    f"{zip_path}!/"
                )
            )
            self.assertEqual(
                descriptor_summary["fields"]["binaryKind"],
                "vulkan.spirv-module",
            )
            self.assertEqual(
                descriptor_summary["fields"]["artifactPath"],
                "backend/vulkan/RuntimeVulkanLoaderFixture.spv",
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
                summary["nativeAdmission"]["nativeArtifactDescriptor"][
                    "optimizationEvidence"
                ]["status"],
                "metadata-only",
            )
            self.assertEqual(
                descriptor_summary["expectedBinaryKinds"],
                ["vulkan.spirv-module"],
            )
            self.assertTrue(descriptor_summary["binaryKindMatchesLoader"])

    def test_source_free_plan_uses_manifest_spirv_descriptor_and_ignores_legacy_path(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory(suffix=".cglb") as temp_dir:
            package_dir = Path(temp_dir)
            descriptor_path = (
                "backend/vulkan/RuntimeVulkanLoaderFixture.native-artifact.json"
            )
            self._write_source_free_vulkan_package(
                package_dir,
                descriptor_path=descriptor_path,
            )
            source_path = package_dir / "source" / "RuntimeVulkanLoaderFixture.cgl"
            source_path.parent.mkdir()
            source_path.write_text(
                "Vulkan source-free native packages must not parse source\n",
                encoding="utf-8",
            )
            legacy_descriptor_path = package_dir / "metadata" / "native-artifact.json"
            legacy_descriptor_path.parent.mkdir()
            legacy_descriptor_path.write_text(
                '{"target": "metal", "binaryKind": "metal.metallib"}\n',
                encoding="utf-8",
            )

            with self._guard_crossgl_source_reads(
                forbidden_paths={legacy_descriptor_path},
            ):
                plan = plan_vulkan_native_loader(package_dir)
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
                [
                    (
                        "nativeBinary",
                        "backend/vulkan/RuntimeVulkanLoaderFixture.spv",
                    )
                ],
            )
            self.assertEqual(
                summary["nativeArtifact"]["path"],
                "backend/vulkan/RuntimeVulkanLoaderFixture.spv",
            )
            self.assertIsNotNone(descriptor_summary)
            self.assertTrue(descriptor_summary["readable"])
            self.assertEqual(descriptor_summary["artifact"]["path"], descriptor_path)
            self.assertEqual(
                descriptor_summary["fields"]["binaryKind"],
                "vulkan.spirv-module",
            )
            self.assertEqual(
                descriptor_summary["fields"]["artifactPath"],
                "backend/vulkan/RuntimeVulkanLoaderFixture.spv",
            )
            self.assertEqual(
                descriptor_summary["expectedBinaryKinds"],
                ["vulkan.spirv-module"],
            )
            self.assertTrue(descriptor_summary["binaryKindMatchesLoader"])
            vulkan_admission = summary["vulkanNativeAdmission"]
            self.assertEqual(vulkan_admission["decision"], "accepted")
            descriptor_admission = vulkan_admission["nativeArtifactDescriptor"]
            self.assertTrue(descriptor_admission["declared"])
            self.assertTrue(descriptor_admission["readable"])
            self.assertEqual(descriptor_admission["target"], "vulkan")
            self.assertTrue(descriptor_admission["targetMatchesLoader"])
            self.assertEqual(
                descriptor_admission["binaryKind"],
                "vulkan.spirv-module",
            )
            self.assertTrue(descriptor_admission["binaryKindMatchesLoader"])
            self.assertEqual(
                descriptor_admission["artifactPath"],
                "backend/vulkan/RuntimeVulkanLoaderFixture.spv",
            )
            self.assertTrue(descriptor_admission["artifactPathMatchesNativeArtifact"])
            self.assertTrue(descriptor_admission["artifactPathSuffixMatchesSpv"])
            self.assertEqual(
                descriptor_admission["artifactHash"],
                self._sha256(b"SPIR-V"),
            )
            self.assertTrue(descriptor_admission["artifactHashMatchesArtifact"])
            self.assertTrue(descriptor_admission["sizeBytesMatchesArtifact"])
            checks = {check["name"]: check for check in vulkan_admission["checks"]}
            self.assertTrue(
                checks["nativeArtifactDescriptorBinaryKindMatchesLoader"]["passed"]
            )
            self.assertTrue(
                checks["nativeArtifactDescriptorArtifactPathMatchesNativeBinary"][
                    "passed"
                ]
            )
            self.assertTrue(
                checks["nativeArtifactDescriptorArtifactPathSuffixMatchesSpv"]["passed"]
            )
            self.assertTrue(
                checks["nativeArtifactDescriptorArtifactHashMatchesSpirv"]["passed"]
            )
            self.assertEqual(summary["rejectReasons"], [])
            self.assertEqual(list(package_dir.rglob("*.cgl")), [source_path])

    def test_descriptor_binary_kind_mismatch_rejects_source_free_plan_structurally(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory(suffix=".cglb") as temp_dir:
            package_dir = Path(temp_dir)
            self._write_source_free_vulkan_package(
                package_dir,
                descriptor_path=(
                    "backend/vulkan/RuntimeVulkanLoaderFixture.native-artifact.json"
                ),
                descriptor_binary_kind="metal.metallib",
            )
            source_path = package_dir / "source" / "RuntimeVulkanLoaderFixture.cgl"
            source_path.parent.mkdir()
            source_path.write_text(
                "descriptor rejection must not parse CrossGL source\n",
                encoding="utf-8",
            )

            with self._guard_crossgl_source_reads():
                plan = plan_vulkan_native_loader(package_dir)
                summary = plan.to_summary()

            descriptor_summary = summary["nativeArtifactDescriptor"]
            self.assertFalse(plan.ready)
            self.assertIsNone(plan.native_artifact)
            self.assertEqual(summary["sourceInputs"], [])
            self.assertIsNotNone(descriptor_summary)
            self.assertTrue(descriptor_summary["readable"])
            self.assertEqual(
                descriptor_summary["fields"]["binaryKind"],
                "metal.metallib",
            )
            self.assertEqual(
                descriptor_summary["expectedBinaryKinds"],
                ["vulkan.spirv-module"],
            )
            self.assertFalse(descriptor_summary["binaryKindMatchesLoader"])
            reject_codes = [
                diagnostic["code"] for diagnostic in summary["rejectReasons"]
            ]
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
            self.assertEqual(descriptor_reject["path"], "binaryKind")
            self.assertEqual(descriptor_reject["expected"], ["vulkan.spirv-module"])
            self.assertEqual(descriptor_reject["actual"], "metal.metallib")
            vulkan_admission = summary["vulkanNativeAdmission"]
            self.assertEqual(vulkan_admission["decision"], "rejected")
            descriptor_admission = vulkan_admission["nativeArtifactDescriptor"]
            self.assertEqual(descriptor_admission["binaryKind"], "metal.metallib")
            self.assertFalse(descriptor_admission["binaryKindMatchesLoader"])
            mismatch_checks = {
                check["name"]: check for check in vulkan_admission["checks"]
            }
            self.assertFalse(
                mismatch_checks["nativeArtifactDescriptorBinaryKindMatchesLoader"][
                    "passed"
                ]
            )
            self.assertFalse(vulkan_admission["requiredChecksPassed"])
            with self.assertRaisesRegex(PackageReadError, "binaryKind"):
                plan.require_ready()
            self.assertEqual(list(package_dir.rglob("*.cgl")), [source_path])

    def test_rejects_zip_missing_native_artifact_without_source_parse(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir)
            package_dir = temp_root / "package-dir"
            package_dir.mkdir()
            descriptor_path = (
                "backend/vulkan/RuntimeVulkanLoaderFixture.native-artifact.json"
            )
            self._write_source_free_vulkan_package(
                package_dir,
                descriptor_path=descriptor_path,
            )
            source_path = package_dir / "source" / "RuntimeVulkanLoaderFixture.cgl"
            source_path.parent.mkdir()
            source_path.write_text(
                "missing zip artifact must not parse CrossGL source\n",
                encoding="utf-8",
            )
            zip_path = temp_root / "RuntimeVulkanLoaderFixture.cglb"
            self._write_zip_package(
                package_dir,
                zip_path,
                prefix=zip_path.name,
                exclude={"backend/vulkan/RuntimeVulkanLoaderFixture.spv"},
            )

            with (
                self._guard_crossgl_source_reads(),
                self._guard_source_archive_reads(),
                self._guard_compiler_and_device_work(),
            ):
                plan = plan_vulkan_native_loader(zip_path)
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
                summary["runtimePlan"]["runtimeArtifactSelection"]["artifact"],
                None,
            )
            self.assertEqual(
                summary["runtimePlan"]["runtimeArtifactSelection"][
                    "selectedPackageMode"
                ],
                None,
            )
            self.assertEqual(
                summary["runtimePlan"]["requiredArtifactPaths"],
                {"nativeBinary": "backend/vulkan/RuntimeVulkanLoaderFixture.spv"},
            )
            self.assertIsNotNone(descriptor_summary)
            self.assertTrue(descriptor_summary["readable"])
            self.assertTrue(descriptor_summary["sourcePathDeclared"])
            self.assertEqual(descriptor_summary["artifact"]["path"], descriptor_path)
            self.assertEqual(
                descriptor_summary["fields"]["artifactPath"],
                "backend/vulkan/RuntimeVulkanLoaderFixture.spv",
            )
            self.assertIn(
                "package.artifact.required_file_missing",
                [diagnostic["code"] for diagnostic in summary["rejectReasons"]],
            )
            with self.assertRaisesRegex(PackageReadError, "nativeBinary"):
                plan.require_ready()

    def test_rejects_zip_stale_spv_descriptor_without_source_or_work(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir)
            package_dir = temp_root / "package-dir"
            package_dir.mkdir()
            descriptor_path = (
                "backend/vulkan/RuntimeVulkanLoaderFixture.native-artifact.json"
            )
            self._write_source_free_vulkan_package(
                package_dir,
                descriptor_path=descriptor_path,
            )
            (
                package_dir / "backend" / "vulkan" / "RuntimeVulkanLoaderFixture.spv"
            ).write_bytes(b"stale-spv")
            source_path = package_dir / "source" / "RuntimeVulkanLoaderFixture.cgl"
            source_path.parent.mkdir()
            source_path.write_text(
                "zip stale descriptor recovery must not parse CrossGL source\n",
                encoding="utf-8",
            )
            zip_path = temp_root / "RuntimeVulkanLoaderFixture.cglb"
            self._write_zip_package(
                package_dir,
                zip_path,
                prefix=zip_path.name,
            )

            with (
                self._guard_crossgl_source_reads(),
                self._guard_source_archive_reads(),
                self._guard_compiler_and_device_work(),
            ):
                plan = plan_vulkan_native_loader(zip_path)
                summary = plan.to_summary()

            self.assertFalse(plan.ready)
            self.assertFalse(plan.source_parsing_required)
            self.assertFalse(plan.device_execution_required)
            self.assertIsNone(plan.native_artifact)
            self.assertEqual(summary["runtimePlan"]["packageFormat"], "zip")
            self.assertEqual(summary["sourceInputs"], [])
            self.assertEqual(summary["compilerInvocationRequired"], False)
            self.assertEqual(summary["deviceExecutionRequired"], False)
            self.assertIsNone(summary["nativeArtifact"])
            reject_codes = [
                diagnostic["code"] for diagnostic in summary["rejectReasons"]
            ]
            self.assertIn(
                "package.native_artifact_descriptor.artifact_hash_mismatch",
                reject_codes,
            )
            self.assertIn(
                "package.native_artifact_descriptor.size_bytes_mismatch",
                reject_codes,
            )
            descriptor_summary = summary["nativeArtifactDescriptor"]
            self.assertIsNotNone(descriptor_summary)
            self.assertTrue(descriptor_summary["readable"])
            self.assertEqual(
                descriptor_summary["artifact"]["path"],
                descriptor_path,
            )
            api_boundary = summary["vulkanNativeApiBoundary"]
            self.assertEqual(api_boundary["decision"], "rejected")
            self.assertFalse(api_boundary["vulkanRuntimeCallsPerformed"])
            self.assertFalse(api_boundary["vulkanShaderModuleCreationPerformed"])
            self.assertIn(
                "package.native_artifact_descriptor.artifact_hash_mismatch",
                api_boundary["descriptorFreshness"]["failClosedDiagnosticCodes"],
            )
            self.assertFalse(
                api_boundary["descriptorFreshness"]["artifactHashMatchesSpirv"]
            )
            self.assertFalse(
                api_boundary["descriptorFreshness"]["sizeBytesMatchesSpirv"]
            )
            with self.assertRaisesRegex(PackageReadError, "artifact"):
                plan.require_ready()

    def test_rejects_zip_missing_spv_descriptor_hash_without_source_or_work(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir)
            package_dir = temp_root / "package-dir"
            package_dir.mkdir()
            descriptor_path = (
                "backend/vulkan/RuntimeVulkanLoaderFixture.native-artifact.json"
            )
            self._write_source_free_vulkan_package(
                package_dir,
                descriptor_path=descriptor_path,
            )
            descriptor_file = package_dir / descriptor_path
            descriptor = json.loads(descriptor_file.read_text(encoding="utf-8"))
            descriptor.pop("artifactHash")
            self._write_json(descriptor_file, descriptor)
            source_path = package_dir / "source" / "RuntimeVulkanLoaderFixture.cgl"
            source_path.parent.mkdir()
            source_path.write_text(
                "zip malformed descriptor recovery must not parse CrossGL source\n",
                encoding="utf-8",
            )
            zip_path = temp_root / "RuntimeVulkanLoaderFixture.cglb"
            self._write_zip_package(
                package_dir,
                zip_path,
                prefix=zip_path.name,
            )

            with (
                self._guard_crossgl_source_reads(),
                self._guard_source_archive_reads(),
                self._guard_compiler_and_device_work(),
            ):
                plan = plan_vulkan_native_loader(zip_path)
                summary = plan.to_summary()

            self.assertFalse(plan.ready)
            self.assertFalse(plan.source_parsing_required)
            self.assertFalse(plan.device_execution_required)
            self.assertIsNone(plan.native_artifact)
            self.assertEqual(summary["runtimePlan"]["packageFormat"], "zip")
            self.assertEqual(summary["sourceInputs"], [])
            self.assertEqual(summary["compilerInvocationRequired"], False)
            self.assertEqual(summary["deviceExecutionRequired"], False)
            self.assertIsNone(summary["nativeArtifact"])
            reject_codes = [
                diagnostic["code"] for diagnostic in summary["rejectReasons"]
            ]
            self.assertIn(
                "package.native_artifact_descriptor.artifact_hash_invalid",
                reject_codes,
            )
            descriptor_summary = summary["nativeArtifactDescriptor"]
            self.assertIsNotNone(descriptor_summary)
            self.assertTrue(descriptor_summary["readable"])
            self.assertEqual(
                descriptor_summary["artifact"]["path"],
                descriptor_path,
            )
            api_boundary = summary["vulkanNativeApiBoundary"]
            self.assertEqual(api_boundary["decision"], "rejected")
            self.assertFalse(api_boundary["vulkanRuntimeCallsPerformed"])
            self.assertFalse(api_boundary["vulkanShaderModuleCreationPerformed"])
            self.assertIn(
                "package.native_artifact_descriptor.artifact_hash_invalid",
                api_boundary["descriptorFreshness"]["failClosedDiagnosticCodes"],
            )
            self.assertFalse(
                api_boundary["descriptorFreshness"]["artifactHashDeclared"]
            )
            self.assertFalse(
                api_boundary["descriptorFreshness"]["artifactHashMatchesSpirv"]
            )
            with self.assertRaisesRegex(PackageReadError, "artifactHash"):
                plan.require_ready()

    def test_rejects_zip_native_profile_target_mismatch_without_source_or_work(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir)
            package_dir = temp_root / "package-dir"
            package_dir.mkdir()
            descriptor_path = (
                "backend/vulkan/RuntimeVulkanLoaderFixture.native-artifact.json"
            )
            self._write_source_free_vulkan_package(
                package_dir,
                descriptor_path=descriptor_path,
            )
            profile_path = (
                package_dir
                / "backend"
                / "vulkan"
                / "RuntimeVulkanLoaderFixture.profile.json"
            )
            profile = json.loads(profile_path.read_text(encoding="utf-8"))
            profile["target"] = "metal"
            self._write_json(profile_path, profile)
            source_path = package_dir / "source" / "RuntimeVulkanLoaderFixture.cgl"
            source_path.parent.mkdir()
            source_path.write_text(
                "zip profile mismatch recovery must not parse CrossGL source\n",
                encoding="utf-8",
            )
            zip_path = temp_root / "RuntimeVulkanLoaderFixture.cglb"
            self._write_zip_package(
                package_dir,
                zip_path,
                prefix=zip_path.name,
            )

            with (
                self._guard_crossgl_source_reads(),
                self._guard_source_archive_reads(),
                self._guard_compiler_and_device_work(),
            ):
                plan = plan_vulkan_native_loader(zip_path)
                summary = plan.to_summary()

            self.assertFalse(plan.ready)
            self.assertFalse(plan.source_parsing_required)
            self.assertFalse(plan.device_execution_required)
            self.assertIsNone(plan.native_artifact)
            self.assertEqual(summary["runtimePlan"]["packageFormat"], "zip")
            self.assertEqual(summary["sourceInputs"], [])
            self.assertEqual(summary["compilerInvocationRequired"], False)
            self.assertEqual(summary["deviceExecutionRequired"], False)
            self.assertIsNone(summary["nativeArtifact"])
            reject_codes = [
                diagnostic["code"] for diagnostic in summary["rejectReasons"]
            ]
            self.assertIn("package.native_profile.target_mismatch", reject_codes)
            self.assertIn(
                "vulkan_loader.native_profile_target_mismatch",
                reject_codes,
            )
            profile_admission = summary["vulkanNativeAdmission"]["nativeProfile"]
            self.assertTrue(profile_admission["declared"])
            self.assertTrue(profile_admission["readable"])
            self.assertEqual(profile_admission["target"], "metal")
            self.assertFalse(profile_admission["targetMatchesLoader"])
            api_boundary = summary["vulkanNativeApiBoundary"]
            self.assertEqual(api_boundary["decision"], "rejected")
            self.assertFalse(api_boundary["vulkanRuntimeCallsPerformed"])
            self.assertFalse(api_boundary["vulkanShaderModuleCreationPerformed"])
            self.assertIn(
                "package.native_profile.target_mismatch",
                api_boundary["nativeProfileCompatibility"]["failClosedDiagnosticCodes"],
            )
            self.assertFalse(
                api_boundary["nativeProfileCompatibility"]["targetMatchesLoader"]
            )
            with self.assertRaisesRegex(PackageReadError, "nativeProfile.target"):
                plan.require_ready()

    def test_rejects_zip_descriptor_target_mismatch_without_source_or_work(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir)
            package_dir = temp_root / "package-dir"
            package_dir.mkdir()
            descriptor_path = (
                "backend/vulkan/RuntimeVulkanLoaderFixture.native-artifact.json"
            )
            self._write_source_free_vulkan_package(
                package_dir,
                descriptor_path=descriptor_path,
            )
            descriptor_file = package_dir / descriptor_path
            descriptor = json.loads(descriptor_file.read_text(encoding="utf-8"))
            descriptor["target"] = "metal"
            self._write_json(descriptor_file, descriptor)
            source_path = package_dir / "source" / "RuntimeVulkanLoaderFixture.cgl"
            source_path.parent.mkdir()
            source_path.write_text(
                "zip descriptor target mismatch recovery must not parse source\n",
                encoding="utf-8",
            )
            zip_path = temp_root / "RuntimeVulkanLoaderFixture.cglb"
            self._write_zip_package(
                package_dir,
                zip_path,
                prefix=zip_path.name,
            )

            with (
                self._guard_crossgl_source_reads(),
                self._guard_source_archive_reads(),
                self._guard_compiler_and_device_work(),
            ):
                plan = plan_vulkan_native_loader(zip_path)
                summary = plan.to_summary()

            expected_shared_code = "package.native_artifact_descriptor.target_mismatch"
            expected_loader_code = (
                "vulkan_loader.native_artifact_descriptor_target_mismatch"
            )
            self.assertFalse(plan.ready)
            self.assertFalse(plan.source_parsing_required)
            self.assertFalse(plan.device_execution_required)
            self.assertIsNone(plan.native_artifact)
            self.assertEqual(summary["runtimePlan"]["packageFormat"], "zip")
            self.assertEqual(summary["sourceInputs"], [])
            self.assertEqual(summary["compilerInvocationRequired"], False)
            self.assertEqual(summary["deviceExecutionRequired"], False)
            self.assertIsNone(summary["nativeArtifact"])
            reject_codes = [
                diagnostic["code"] for diagnostic in summary["rejectReasons"]
            ]
            self.assertIn(expected_shared_code, reject_codes)
            self.assertIn(expected_loader_code, reject_codes)

            native_admission = summary["nativeAdmission"]
            self.assertEqual(native_admission["decision"], "rejected")
            self.assertEqual(native_admission["reason"], expected_shared_code)
            descriptor_admission = native_admission["nativeArtifactDescriptor"]
            self.assertEqual(descriptor_admission["decision"], "rejected")
            self.assertEqual(descriptor_admission["reason"], expected_shared_code)
            self.assertEqual(descriptor_admission["fields"]["target"], "metal")
            self.assertIn(
                expected_shared_code,
                [
                    diagnostic["code"]
                    for diagnostic in descriptor_admission["diagnostics"]
                ],
            )

            vulkan_admission = summary["vulkanNativeAdmission"]
            self.assertEqual(vulkan_admission["decision"], "rejected")
            self.assertEqual(vulkan_admission["reason"], expected_shared_code)
            self.assertFalse(vulkan_admission["requiredChecksPassed"])
            self.assertIn(
                expected_loader_code,
                [
                    diagnostic["code"]
                    for diagnostic in vulkan_admission["blockedByDiagnostics"]
                ],
            )
            descriptor_detail = vulkan_admission["nativeArtifactDescriptor"]
            self.assertTrue(descriptor_detail["declared"])
            self.assertTrue(descriptor_detail["readable"])
            self.assertEqual(descriptor_detail["target"], "metal")
            self.assertFalse(descriptor_detail["targetMatchesLoader"])
            checks = {check["name"]: check for check in vulkan_admission["checks"]}
            self.assertFalse(
                checks["nativeArtifactDescriptorTargetMatchesLoader"]["passed"]
            )

            api_boundary = summary["vulkanNativeApiBoundary"]
            self.assertEqual(api_boundary["decision"], "rejected")
            self.assertFalse(api_boundary["vulkanRuntimeCallsPerformed"])
            self.assertFalse(api_boundary["vulkanShaderModuleCreationPerformed"])
            self.assertIn(
                expected_shared_code,
                api_boundary["descriptorFreshness"]["failClosedDiagnosticCodes"],
            )
            self.assertIn(
                expected_loader_code,
                api_boundary["descriptorFreshness"]["failClosedDiagnosticCodes"],
            )
            with self.assertRaisesRegex(
                PackageReadError,
                "nativeArtifactDescriptor.target",
            ):
                plan.require_ready()

    def test_rejects_missing_spv_native_binary_without_source_or_work(self) -> None:
        with tempfile.TemporaryDirectory(suffix=".cglb") as temp_dir:
            package_dir = Path(temp_dir)
            self._write_valid_vulkan_package(package_dir)
            (
                package_dir / "backend" / "vulkan" / "RuntimeVulkanLoaderFixture.spv"
            ).unlink()
            source_path = package_dir / "source" / "invalid.cgl"
            source_path.parent.mkdir()
            source_path.write_text(
                "missing native binary must not trigger source fallback\n",
                encoding="utf-8",
            )

            with self._guard_source_reads(), self._guard_compiler_and_device_work():
                plan = plan_vulkan_native_loader(package_dir)
                summary = plan.to_summary()

            self.assertFalse(plan.ready)
            self.assertFalse(plan.planned)
            self.assertFalse(plan.loadable)
            self.assertEqual(plan.status, "rejected")
            self.assertIsNone(plan.native_artifact)
            self.assertEqual(summary["sourceInputs"], [])
            self.assertEqual(summary["compilerInvocationRequired"], False)
            self.assertEqual(summary["deviceExecutionRequired"], False)
            self.assertIsNone(summary["nativeArtifact"])
            self.assertEqual(summary["runtimePlan"]["sourceInputs"], [])
            self.assertEqual(
                summary["runtimePlan"]["compilerInvocationRequired"],
                False,
            )
            self.assertEqual(summary["runtimePlan"]["deviceExecutionRequired"], False)
            self.assertIn(
                "package.artifact.required_file_missing",
                [diagnostic["code"] for diagnostic in summary["rejectReasons"]],
            )
            with self.assertRaisesRegex(PackageReadError, "nativeBinary"):
                plan.require_ready()
            self.assertEqual(list(package_dir.rglob("*.cgl")), [source_path])

    def test_rejects_missing_native_artifact_descriptor_metadata(self) -> None:
        with tempfile.TemporaryDirectory(suffix=".cglb") as temp_dir:
            package_dir = Path(temp_dir)
            self._write_valid_vulkan_package(
                package_dir,
                include_native_artifact_descriptor=False,
                include_native_profile=True,
            )
            source_path = package_dir / "source" / "invalid.cgl"
            source_path.parent.mkdir()
            source_path.write_text(
                "missing descriptor must not trigger source parsing\n",
                encoding="utf-8",
            )

            with self._guard_source_reads(), self._guard_compiler_and_device_work():
                plan = plan_vulkan_native_loader(package_dir)
                summary = plan.to_summary()

            self.assertFalse(plan.ready)
            self.assertIsNone(plan.native_artifact)
            self.assertEqual(summary["sourceInputs"], [])
            reject_codes = [
                diagnostic["code"] for diagnostic in summary["rejectReasons"]
            ]
            self.assertIn(
                "vulkan_loader.native_artifact_descriptor_missing",
                reject_codes,
            )
            vulkan_admission = summary["vulkanNativeAdmission"]
            self.assertFalse(
                {check["name"]: check for check in vulkan_admission["checks"]}[
                    "nativeArtifactDescriptorDeclared"
                ]["passed"]
            )
            api_boundary = summary["vulkanNativeApiBoundary"]
            self.assertEqual(api_boundary["decision"], "rejected")
            self.assertIn(
                "vulkan_loader.native_artifact_descriptor_missing",
                api_boundary["descriptorFreshness"]["failClosedDiagnosticCodes"],
            )
            with self.assertRaisesRegex(PackageReadError, "nativeArtifactDescriptor"):
                plan.require_ready()
            self.assertEqual(list(package_dir.rglob("*.cgl")), [source_path])

    def test_rejects_missing_native_profile_metadata(self) -> None:
        with tempfile.TemporaryDirectory(suffix=".cglb") as temp_dir:
            package_dir = Path(temp_dir)
            self._write_valid_vulkan_package(
                package_dir,
                include_native_artifact_descriptor=True,
                include_native_profile=False,
            )
            source_path = package_dir / "source" / "invalid.cgl"
            source_path.parent.mkdir()
            source_path.write_text(
                "missing profile must not trigger source parsing\n",
                encoding="utf-8",
            )

            with self._guard_source_reads(), self._guard_compiler_and_device_work():
                plan = plan_vulkan_native_loader(package_dir)
                summary = plan.to_summary()

            self.assertFalse(plan.ready)
            self.assertIsNone(plan.native_artifact)
            self.assertEqual(summary["sourceInputs"], [])
            reject_codes = [
                diagnostic["code"] for diagnostic in summary["rejectReasons"]
            ]
            self.assertIn("vulkan_loader.native_profile_missing", reject_codes)
            vulkan_admission = summary["vulkanNativeAdmission"]
            self.assertFalse(
                {check["name"]: check for check in vulkan_admission["checks"]}[
                    "nativeProfileDeclared"
                ]["passed"]
            )
            self.assertEqual(
                summary["vulkanNativeApiBoundary"]["nativeProfileCompatibility"][
                    "declared"
                ],
                False,
            )
            with self.assertRaisesRegex(PackageReadError, "nativeProfile"):
                plan.require_ready()
            self.assertEqual(list(package_dir.rglob("*.cgl")), [source_path])

    def test_rejects_missing_descriptor_artifact_hash_without_source_or_work(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory(suffix=".cglb") as temp_dir:
            package_dir = Path(temp_dir)
            self._write_valid_vulkan_package(package_dir)
            descriptor_path = package_dir / "metadata" / "native-artifact.json"
            descriptor = json.loads(descriptor_path.read_text(encoding="utf-8"))
            descriptor.pop("artifactHash")
            self._write_json(descriptor_path, descriptor)
            source_path = package_dir / "source" / "invalid.cgl"
            source_path.parent.mkdir()
            source_path.write_text(
                "missing descriptor hash must not trigger source parsing\n",
                encoding="utf-8",
            )

            with (
                self._guard_crossgl_source_reads(),
                self._guard_compiler_and_device_work(),
            ):
                plan = plan_vulkan_native_loader(package_dir)
                summary = plan.to_summary()

            self.assertFalse(plan.ready)
            self.assertIsNone(plan.native_artifact)
            self.assertEqual(summary["sourceInputs"], [])
            reject_codes = [
                diagnostic["code"] for diagnostic in summary["rejectReasons"]
            ]
            self.assertIn(
                "package.native_artifact_descriptor.artifact_hash_invalid",
                reject_codes,
            )
            vulkan_admission = summary["vulkanNativeAdmission"]
            checks = {check["name"]: check for check in vulkan_admission["checks"]}
            self.assertFalse(
                checks["nativeArtifactDescriptorArtifactHashDeclared"]["passed"]
            )
            self.assertFalse(
                checks["nativeArtifactDescriptorArtifactHashMatchesSpirv"]["passed"]
            )
            self.assertFalse(
                summary["vulkanNativeApiBoundary"]["descriptorFreshness"][
                    "artifactHashDeclared"
                ]
            )
            with self.assertRaisesRegex(PackageReadError, "artifactHash"):
                plan.require_ready()
            self.assertEqual(list(package_dir.rglob("*.cgl")), [source_path])

    def test_rejects_stale_spv_native_binary_without_source_or_work(self) -> None:
        with tempfile.TemporaryDirectory(suffix=".cglb") as temp_dir:
            package_dir = Path(temp_dir)
            self._write_valid_vulkan_package(
                package_dir,
                include_native_artifact_descriptor=True,
                include_native_profile=True,
            )
            native_path = (
                package_dir / "backend" / "vulkan" / "RuntimeVulkanLoaderFixture.spv"
            )
            native_path.write_bytes(b"SPIR-X")
            source_path = package_dir / "source" / "invalid.cgl"
            source_path.parent.mkdir()
            source_path.write_text(
                "stale native binary must not trigger source fallback\n",
                encoding="utf-8",
            )

            with (
                self._guard_crossgl_source_reads(),
                self._guard_compiler_and_device_work(),
            ):
                plan = plan_vulkan_native_loader(package_dir)
                summary = plan.to_summary()

            descriptor_summary = summary["nativeArtifactDescriptor"]
            self.assertFalse(plan.ready)
            self.assertIsNone(plan.native_artifact)
            self.assertEqual(summary["sourceInputs"], [])
            self.assertEqual(summary["compilerInvocationRequired"], False)
            self.assertEqual(summary["deviceExecutionRequired"], False)
            self.assertIsNone(summary["nativeArtifact"])
            self.assertIsNotNone(descriptor_summary)
            self.assertTrue(descriptor_summary["readable"])
            self.assertEqual(
                descriptor_summary["fields"]["artifactPath"],
                "backend/vulkan/RuntimeVulkanLoaderFixture.spv",
            )
            self.assertIn(
                "package.native_artifact_descriptor.artifact_hash_mismatch",
                [diagnostic["code"] for diagnostic in summary["rejectReasons"]],
            )
            with self.assertRaisesRegex(PackageReadError, "artifactHash"):
                plan.require_ready()
            self.assertEqual(list(package_dir.rglob("*.cgl")), [source_path])

    def test_rejects_stale_native_artifact_descriptor_without_source_or_work(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory(suffix=".cglb") as temp_dir:
            package_dir = Path(temp_dir)
            self._write_valid_vulkan_package(
                package_dir,
                include_native_artifact_descriptor=True,
                include_native_profile=True,
            )
            descriptor_path = package_dir / "metadata" / "native-artifact.json"
            descriptor = json.loads(descriptor_path.read_text(encoding="utf-8"))
            descriptor["artifactPath"] = "backend/vulkan/StaleFixture.spv"
            self._write_json(descriptor_path, descriptor)
            source_path = package_dir / "source" / "invalid.cgl"
            source_path.parent.mkdir()
            source_path.write_text(
                "stale descriptor must not trigger source fallback\n",
                encoding="utf-8",
            )

            with (
                self._guard_crossgl_source_reads(),
                self._guard_compiler_and_device_work(),
            ):
                plan = plan_vulkan_native_loader(package_dir)
                summary = plan.to_summary()

            descriptor_summary = summary["nativeArtifactDescriptor"]
            self.assertFalse(plan.ready)
            self.assertFalse(plan.loadable)
            self.assertIsNone(plan.native_artifact)
            self.assertIsNone(summary["nativeArtifact"])
            self.assertEqual(summary["sourceInputs"], [])
            self.assertEqual(summary["compilerInvocationRequired"], False)
            self.assertEqual(summary["deviceExecutionRequired"], False)
            self.assertIsNotNone(descriptor_summary)
            self.assertEqual(
                descriptor_summary["fields"]["artifactPath"],
                "backend/vulkan/StaleFixture.spv",
            )
            self.assertIn(
                "package.native_artifact_descriptor.artifact_path_mismatch",
                [diagnostic["code"] for diagnostic in summary["rejectReasons"]],
            )
            with self.assertRaisesRegex(PackageReadError, "artifactPath"):
                plan.require_ready()
            self.assertEqual(list(package_dir.rglob("*.cgl")), [source_path])

    def test_summary_surfaces_native_artifact_descriptor_metadata(self) -> None:
        with tempfile.TemporaryDirectory(suffix=".cglb") as temp_dir:
            package_dir = Path(temp_dir)
            self._write_valid_vulkan_package(
                package_dir,
                include_native_artifact_descriptor=True,
                include_native_profile=True,
            )
            source_path = package_dir / "source" / "invalid.cgl"
            source_path.parent.mkdir()
            source_path.write_text("must not parse CrossGL source\n", encoding="utf-8")

            with self._guard_crossgl_source_reads():
                plan = plan_vulkan_native_loader(package_dir)
                summary = plan.to_summary()

            descriptor_summary = summary["nativeArtifactDescriptor"]
            self.assertTrue(plan.ready, summary["diagnostics"])
            self.assertIsNotNone(descriptor_summary)
            self.assertTrue(descriptor_summary["readable"])
            self.assertEqual(
                descriptor_summary["artifact"]["path"],
                "metadata/native-artifact.json",
            )
            self.assertEqual(
                descriptor_summary["fields"]["binaryKind"],
                "vulkan.spirv-module",
            )
            self.assertEqual(
                descriptor_summary["fields"]["artifactPath"],
                "backend/vulkan/RuntimeVulkanLoaderFixture.spv",
            )
            self.assertEqual(
                descriptor_summary["expectedBinaryKinds"],
                ["vulkan.spirv-module"],
            )
            self.assertTrue(descriptor_summary["binaryKindMatchesLoader"])
            self.assertEqual(summary["rejectReasons"], [])
            self.assertEqual(list(package_dir.rglob("*.cgl")), [source_path])

    def test_descriptor_binary_kind_mismatch_rejects_plan(self) -> None:
        with tempfile.TemporaryDirectory(suffix=".cglb") as temp_dir:
            package_dir = Path(temp_dir)
            self._write_valid_vulkan_package(
                package_dir,
                include_native_artifact_descriptor=True,
                descriptor_binary_kind="directx.dxil",
                include_native_profile=True,
            )

            plan = plan_vulkan_native_loader(package_dir)
            summary = plan.to_summary()

            descriptor_summary = summary["nativeArtifactDescriptor"]
            self.assertFalse(plan.ready)
            self.assertIsNone(plan.native_artifact)
            self.assertIsNotNone(descriptor_summary)
            self.assertTrue(descriptor_summary["readable"])
            self.assertEqual(
                descriptor_summary["fields"]["binaryKind"],
                "directx.dxil",
            )
            self.assertFalse(descriptor_summary["binaryKindMatchesLoader"])
            self.assertIn(
                "package.native_artifact_descriptor.binary_kind_mismatch",
                [diagnostic["code"] for diagnostic in summary["rejectReasons"]],
            )
            with self.assertRaisesRegex(PackageReadError, "binaryKind"):
                plan.require_ready()

    def test_manifest_declared_unreadable_descriptor_rejects_native_plan(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory(suffix=".cglb") as temp_dir:
            package_dir = Path(temp_dir)
            descriptor_path = "metadata/native-artifact.json"
            self._write_valid_vulkan_package(package_dir)
            manifest_path = package_dir / "manifest.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["artifacts"]["nativeArtifactDescriptor"] = descriptor_path
            self._write_json(manifest_path, manifest)
            (package_dir / descriptor_path).parent.mkdir(parents=True, exist_ok=True)
            (package_dir / descriptor_path).write_text("{", encoding="utf-8")
            source_path = package_dir / "source" / "invalid.cgl"
            source_path.parent.mkdir()
            source_path.write_text(
                "unreadable descriptor rejection must not parse source\n",
                encoding="utf-8",
            )

            with self._guard_source_reads(), self._guard_compiler_and_device_work():
                plan = plan_vulkan_native_loader(package_dir)
                summary = plan.to_summary()

            self.assertFalse(plan.ready)
            self.assertIsNone(plan.native_artifact)
            self.assertEqual(summary["sourceInputs"], [])
            reject_codes = [
                diagnostic["code"] for diagnostic in summary["rejectReasons"]
            ]
            self.assertIn(
                "vulkan_loader.native_artifact_descriptor_unreadable",
                reject_codes,
            )
            self.assertIn("package.native_artifact_descriptor.invalid", reject_codes)
            descriptor_summary = summary["nativeArtifactDescriptor"]
            self.assertIsNotNone(descriptor_summary)
            self.assertFalse(descriptor_summary["readable"])
            with self.assertRaisesRegex(PackageReadError, "nativeArtifactDescriptor"):
                plan.require_ready()
            self.assertEqual(list(package_dir.rglob("*.cgl")), [source_path])

    def test_rejects_incompatible_target_without_source_parse(self) -> None:
        with tempfile.TemporaryDirectory(suffix=".cglb") as temp_dir:
            package_dir = Path(temp_dir)
            self._write_valid_directx_package(package_dir)
            source_path = package_dir / "source" / "invalid.cgl"
            source_path.parent.mkdir()
            source_path.write_text("target mismatch source\n", encoding="utf-8")

            with self._guard_source_reads():
                plan = plan_vulkan_native_loader(package_dir)
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
            self._write_valid_vulkan_package(package_dir, include_native_binary=False)
            source_path = package_dir / "source" / "invalid.cgl"
            source_path.parent.mkdir()
            source_path.write_text("missing artifact source\n", encoding="utf-8")

            with self._guard_source_reads():
                plan = plan_vulkan_native_loader(package_dir)
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
            self._write_valid_vulkan_package(
                package_dir,
                native_binary_path="source/forged.cgl",
                include_native_artifact_descriptor=False,
            )

            with self._guard_source_reads():
                plan = plan_vulkan_native_loader(package_dir)
                summary = plan.to_summary()

            self.assertFalse(plan.ready)
            self.assertIsNone(plan.native_artifact)
            self.assertEqual(summary["sourceInputs"], [])
            self.assertIn(
                "package.artifact.source_input_leakage",
                [diagnostic["code"] for diagnostic in summary["rejectReasons"]],
            )

    def test_rejects_native_profile_native_binary_mismatch_detail(self) -> None:
        with tempfile.TemporaryDirectory(suffix=".cglb") as temp_dir:
            package_dir = Path(temp_dir)
            self._write_valid_vulkan_package(
                package_dir,
                include_native_artifact_descriptor=True,
                include_native_profile=True,
            )
            profile_path = (
                package_dir
                / "backend"
                / "vulkan"
                / "RuntimeVulkanLoaderFixture.profile.json"
            )
            profile = json.loads(profile_path.read_text(encoding="utf-8"))
            profile["nativeBinary"] = "backend/vulkan/OtherFixture.spv"
            self._write_json(profile_path, profile)
            source_path = package_dir / "source" / "invalid.cgl"
            source_path.parent.mkdir()
            source_path.write_text(
                "profile mismatch must not trigger source parsing\n",
                encoding="utf-8",
            )

            with (
                self._guard_crossgl_source_reads(),
                self._guard_compiler_and_device_work(),
            ):
                plan = plan_vulkan_native_loader(package_dir)
                summary = plan.to_summary()

            self.assertFalse(plan.ready)
            self.assertFalse(plan.source_parsing_required)
            self.assertFalse(plan.device_execution_required)
            self.assertIsNone(plan.native_artifact)
            self.assertEqual(summary["sourceInputs"], [])
            reject_codes = [
                diagnostic["code"] for diagnostic in summary["rejectReasons"]
            ]
            self.assertIn(
                "vulkan_loader.native_profile_native_binary_mismatch",
                reject_codes,
            )
            vulkan_admission = summary["vulkanNativeAdmission"]
            self.assertEqual(vulkan_admission["decision"], "rejected")
            profile_admission = vulkan_admission["nativeProfile"]
            self.assertTrue(profile_admission["declared"])
            self.assertTrue(profile_admission["readable"])
            self.assertEqual(
                profile_admission["nativeBinary"],
                "backend/vulkan/OtherFixture.spv",
            )
            self.assertFalse(profile_admission["nativeBinaryMatchesNativeArtifact"])
            mismatch_checks = {
                check["name"]: check for check in vulkan_admission["checks"]
            }
            self.assertFalse(
                mismatch_checks["nativeProfileNativeBinaryMatchesNativeArtifact"][
                    "passed"
                ]
            )
            self.assertFalse(vulkan_admission["requiredChecksPassed"])
            with self.assertRaisesRegex(PackageReadError, "nativeProfile.nativeBinary"):
                plan.require_ready()
            self.assertEqual(list(package_dir.rglob("*.cgl")), [source_path])

    def test_rejects_descriptor_native_profile_evidence_path_mismatch(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory(suffix=".cglb") as temp_dir:
            package_dir = Path(temp_dir)
            self._write_valid_vulkan_package(
                package_dir,
                include_native_artifact_descriptor=True,
                include_native_profile=True,
            )
            descriptor_path = package_dir / "metadata" / "native-artifact.json"
            descriptor = json.loads(descriptor_path.read_text(encoding="utf-8"))
            descriptor["optimizationEvidence"]["evidenceSource"] = {
                "kind": "native-profile",
                "path": "backend/vulkan/StaleRuntimeVulkanLoaderFixture.profile.json",
            }
            self._write_json(descriptor_path, descriptor)
            source_path = package_dir / "source" / "invalid.cgl"
            source_path.parent.mkdir()
            source_path.write_text(
                "descriptor/profile mismatch must not trigger source parsing\n",
                encoding="utf-8",
            )

            with (
                self._guard_crossgl_source_reads(),
                self._guard_compiler_and_device_work(),
            ):
                plan = plan_vulkan_native_loader(package_dir)
                summary = plan.to_summary()

            expected_code = (
                "vulkan_loader.native_profile_descriptor_evidence_path_mismatch"
            )
            self.assertFalse(plan.ready)
            self.assertFalse(plan.source_parsing_required)
            self.assertFalse(plan.device_execution_required)
            self.assertIsNone(plan.native_artifact)
            self.assertEqual(summary["sourceInputs"], [])
            self.assertIn(
                expected_code,
                [diagnostic["code"] for diagnostic in summary["rejectReasons"]],
            )

            vulkan_admission = summary["vulkanNativeAdmission"]
            self.assertEqual(vulkan_admission["decision"], "rejected")
            self.assertEqual(vulkan_admission["reason"], expected_code)
            profile_admission = vulkan_admission["nativeProfile"]
            self.assertEqual(
                profile_admission["descriptorEvidenceSourcePath"],
                "backend/vulkan/StaleRuntimeVulkanLoaderFixture.profile.json",
            )
            self.assertFalse(
                profile_admission["descriptorEvidenceSourcePathMatchesNativeProfile"]
            )
            profile_api_input = summary["vulkanNativeApiBoundary"]["runtimeInputs"][
                "nativeProfile"
            ]
            self.assertEqual(
                profile_api_input["descriptorEvidenceSourcePath"],
                "backend/vulkan/StaleRuntimeVulkanLoaderFixture.profile.json",
            )
            self.assertFalse(
                profile_api_input["descriptorEvidenceSourcePathMatchesNativeProfile"]
            )
            mismatch_checks = {
                check["name"]: check for check in vulkan_admission["checks"]
            }
            self.assertFalse(
                mismatch_checks[
                    "nativeArtifactDescriptorEvidenceSourcePathMatchesNativeProfile"
                ]["passed"]
            )
            self.assertFalse(vulkan_admission["requiredChecksPassed"])
            with self.assertRaisesRegex(PackageReadError, "optimizationEvidence"):
                plan.require_ready()
            self.assertEqual(list(package_dir.rglob("*.cgl")), [source_path])

    def test_rejects_native_profile_target_mismatch_detail(self) -> None:
        with tempfile.TemporaryDirectory(suffix=".cglb") as temp_dir:
            package_dir = Path(temp_dir)
            self._write_valid_vulkan_package(
                package_dir,
                include_native_artifact_descriptor=True,
                include_native_profile=True,
            )
            profile_path = (
                package_dir
                / "backend"
                / "vulkan"
                / "RuntimeVulkanLoaderFixture.profile.json"
            )
            profile = json.loads(profile_path.read_text(encoding="utf-8"))
            profile["target"] = "metal"
            self._write_json(profile_path, profile)
            source_path = package_dir / "source" / "invalid.cgl"
            source_path.parent.mkdir()
            source_path.write_text(
                "profile target mismatch must not trigger source parsing\n",
                encoding="utf-8",
            )

            with (
                self._guard_crossgl_source_reads(),
                self._guard_compiler_and_device_work(),
            ):
                plan = plan_vulkan_native_loader(package_dir)
                summary = plan.to_summary()

            shared_code = "package.native_profile.target_mismatch"
            expected_code = "vulkan_loader.native_profile_target_mismatch"
            self.assertFalse(plan.ready)
            self.assertFalse(plan.source_parsing_required)
            self.assertFalse(plan.device_execution_required)
            self.assertIsNone(plan.native_artifact)
            self.assertEqual(summary["sourceInputs"], [])
            self.assertIn(
                shared_code,
                [diagnostic["code"] for diagnostic in summary["rejectReasons"]],
            )
            self.assertIn(
                expected_code,
                [diagnostic["code"] for diagnostic in summary["rejectReasons"]],
            )

            native_admission = summary["nativeAdmission"]
            self.assertEqual(native_admission["reason"], shared_code)
            self.assertIn(
                shared_code,
                [
                    diagnostic["code"]
                    for diagnostic in native_admission["blockedByDiagnostics"]
                ],
            )
            self.assertIn(
                expected_code,
                [
                    diagnostic["code"]
                    for diagnostic in native_admission["blockedByDiagnostics"]
                ],
            )

            vulkan_admission = summary["vulkanNativeAdmission"]
            self.assertEqual(vulkan_admission["decision"], "rejected")
            self.assertEqual(vulkan_admission["reason"], shared_code)
            self.assertIn(
                shared_code,
                [
                    diagnostic["code"]
                    for diagnostic in vulkan_admission["blockedByDiagnostics"]
                ],
            )
            self.assertIn(
                expected_code,
                [
                    diagnostic["code"]
                    for diagnostic in vulkan_admission["blockedByDiagnostics"]
                ],
            )

            profile_admission = vulkan_admission["nativeProfile"]
            self.assertEqual(profile_admission["target"], "metal")
            self.assertFalse(profile_admission["targetMatchesLoader"])

            mismatch_checks = {
                check["name"]: check for check in vulkan_admission["checks"]
            }
            self.assertFalse(
                mismatch_checks["nativeProfileTargetMatchesLoader"]["passed"]
            )
            self.assertFalse(vulkan_admission["requiredChecksPassed"])
            with self.assertRaisesRegex(PackageReadError, "nativeProfile.target"):
                plan.require_ready()
            self.assertEqual(list(package_dir.rglob("*.cgl")), [source_path])

    def test_rejects_non_spv_native_binary_descriptor_detail(self) -> None:
        with tempfile.TemporaryDirectory(suffix=".cglb") as temp_dir:
            package_dir = Path(temp_dir)
            self._write_valid_vulkan_package(
                package_dir,
                native_binary_path="backend/vulkan/RuntimeVulkanLoaderFixture.bin",
                include_native_artifact_descriptor=True,
            )
            source_path = package_dir / "source" / "invalid.cgl"
            source_path.parent.mkdir()
            source_path.write_text(
                "non-spv rejection must stay metadata-only\n",
                encoding="utf-8",
            )

            with (
                self._guard_crossgl_source_reads(),
                self._guard_compiler_and_device_work(),
            ):
                plan = plan_vulkan_native_loader(package_dir)
                summary = plan.to_summary()

            self.assertFalse(plan.ready)
            self.assertFalse(plan.source_parsing_required)
            self.assertFalse(plan.device_execution_required)
            self.assertIsNone(plan.native_artifact)
            self.assertEqual(summary["sourceInputs"], [])
            reject_codes = [
                diagnostic["code"] for diagnostic in summary["rejectReasons"]
            ]
            self.assertIn(
                "vulkan_loader.native_artifact_spv_path_mismatch",
                reject_codes,
            )
            self.assertIn(
                "vulkan_loader.native_artifact_descriptor_spv_path_mismatch",
                reject_codes,
            )
            vulkan_admission = summary["vulkanNativeAdmission"]
            self.assertEqual(vulkan_admission["decision"], "rejected")
            spirv_admission = vulkan_admission["spirvArtifact"]
            self.assertEqual(
                spirv_admission["path"],
                "backend/vulkan/RuntimeVulkanLoaderFixture.bin",
            )
            self.assertEqual(spirv_admission["pathSuffix"], ".bin")
            self.assertFalse(spirv_admission["pathSuffixMatchesSpv"])
            descriptor_admission = vulkan_admission["nativeArtifactDescriptor"]
            self.assertEqual(
                descriptor_admission["artifactPath"],
                "backend/vulkan/RuntimeVulkanLoaderFixture.bin",
            )
            self.assertFalse(descriptor_admission["artifactPathSuffixMatchesSpv"])
            mismatch_checks = {
                check["name"]: check for check in vulkan_admission["checks"]
            }
            self.assertFalse(
                mismatch_checks["nativeBinaryPathSuffixMatchesSpv"]["passed"]
            )
            self.assertFalse(
                mismatch_checks["nativeArtifactDescriptorArtifactPathSuffixMatchesSpv"][
                    "passed"
                ]
            )
            self.assertFalse(vulkan_admission["requiredChecksPassed"])
            with self.assertRaisesRegex(PackageReadError, ".spv"):
                plan.require_ready()
            self.assertEqual(list(package_dir.rglob("*.cgl")), [source_path])

    def _write_valid_vulkan_package(
        self,
        package_dir: Path,
        *,
        include_native_binary: bool = True,
        native_binary_path: str = "backend/vulkan/RuntimeVulkanLoaderFixture.spv",
        include_native_artifact_descriptor: bool = True,
        descriptor_binary_kind: str = "vulkan.spirv-module",
        include_backend_source: bool = False,
        include_native_profile: bool = True,
    ) -> None:
        backend_dir = package_dir / "backend" / "vulkan"
        backend_dir.mkdir(parents=True)
        assembly_path = "backend/vulkan/RuntimeVulkanLoaderFixture.spvasm"
        assembly_bytes = b"; generated SPIR-V assembly\n"
        (package_dir / assembly_path).write_bytes(assembly_bytes)
        backend_source_path = "backend/vulkan/RuntimeVulkanLoaderFixture.glsl"
        if include_backend_source:
            (package_dir / backend_source_path).write_text(
                "// generated Vulkan source-package fallback\n",
                encoding="utf-8",
            )
        native_bytes = b"SPIR-V"
        if include_native_binary:
            native_path = package_dir / native_binary_path
            native_path.parent.mkdir(parents=True, exist_ok=True)
            native_path.write_bytes(native_bytes)

        artifacts: dict[str, object] = {
            "backendAssembly": assembly_path,
        }
        if include_backend_source:
            artifacts["backendSource"] = backend_source_path
        if include_native_binary:
            artifacts["nativeBinary"] = native_binary_path
        if include_native_profile:
            profile_path = "backend/vulkan/RuntimeVulkanLoaderFixture.profile.json"
            artifacts["nativeProfile"] = profile_path
            self._write_json(
                package_dir / profile_path,
                {
                    "schemaVersion": 1,
                    "module": "RuntimeVulkanLoaderFixture",
                    "target": "vulkan",
                    "backendAssembly": assembly_path,
                    "nativeBinary": native_binary_path,
                    "debug": {
                        "disassembly": {
                            "status": "skipped-tool-missing",
                            "path": None,
                        },
                    },
                },
            )
        if include_native_artifact_descriptor:
            descriptor_path = "metadata/native-artifact.json"
            artifacts["nativeArtifactDescriptor"] = descriptor_path
            self._write_native_artifact_descriptor(
                package_dir,
                descriptor_path=descriptor_path,
                target="vulkan",
                binary_kind=descriptor_binary_kind,
                source_path=assembly_path,
                source_bytes=assembly_bytes,
                artifact_path=native_binary_path,
                artifact_bytes=native_bytes,
            )

        self._write_package_json(
            package_dir,
            target="vulkan",
            native_binary_path=native_binary_path,
            artifacts=artifacts,
            binding={
                "target": "vulkan",
                "stage": "compute",
                "entryPoint": "runtime_vulkan_loader_main",
                "name": "OutputBuffer",
                "kind": "storageBuffer",
                "sourceType": "float4",
                "addressSpace": "storage",
                "abi": {"set": 0, "binding": 0},
                "bindingClass": "storage-buffer",
                "descriptorType": "VK_DESCRIPTOR_TYPE_STORAGE_BUFFER",
                "storageClass": "StorageBuffer",
                "spirvType": "%_runtimearr_v4float",
                "evidenceId": (
                    "target-legalization.v1.vulkan.resource-binding.compute."
                    "runtime_vulkan_loader_main.OutputBuffer"
                ),
            },
        )

    def _write_valid_directx_package(self, package_dir: Path) -> None:
        backend_dir = package_dir / "backend" / "directx"
        backend_dir.mkdir(parents=True)
        source_path = "backend/directx/RuntimeVulkanLoaderFixture.hlsl"
        native_path = "backend/directx/RuntimeVulkanLoaderFixture.dxil"
        (package_dir / source_path).write_text("// generated HLSL\n", encoding="utf-8")
        (package_dir / native_path).write_bytes(b"DXIL")
        self._write_package_json(
            package_dir,
            target="directx",
            native_binary_path=native_path,
            artifacts={
                "backendSource": source_path,
                "nativeBinary": native_path,
                "nativeBinaryStatus": "emitted",
            },
            binding={
                "target": "directx",
                "stage": "compute",
                "entryPoint": "runtime_vulkan_loader_main",
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

    def _write_source_free_vulkan_package(
        self,
        package_dir: Path,
        *,
        descriptor_path: str,
        descriptor_binary_kind: str = "vulkan.spirv-module",
    ) -> None:
        backend_dir = package_dir / "backend" / "vulkan"
        backend_dir.mkdir(parents=True)
        native_path = "backend/vulkan/RuntimeVulkanLoaderFixture.spv"
        profile_path = "backend/vulkan/RuntimeVulkanLoaderFixture.profile.json"
        native_bytes = b"SPIR-V"
        (package_dir / native_path).write_bytes(native_bytes)

        self._write_json(
            package_dir / "manifest.json",
            {
                "schemaVersion": 1,
                "compiler": {
                    "name": "CrossGL-Compiler",
                    "version": "test",
                    "llvmVersion": "not-found",
                },
                "module": "RuntimeVulkanLoaderFixture",
                "target": "vulkan",
                "sourceHash": {"algorithm": "sha256", "value": "0" * 64},
                "packageArtifactRequirements": {
                    "target": "vulkan",
                    "packageMode": "native",
                    "requiredPathArtifacts": ["nativeBinary"],
                    "requiresNativeBinaryStatus": False,
                    "allowsPlannedNativeBinary": False,
                    "allowsPlannedNativeSourceEvidence": False,
                },
                "artifacts": {
                    "nativeBinary": native_path,
                    "nativeArtifactDescriptor": descriptor_path,
                    "nativeProfile": profile_path,
                },
            },
        )
        self._write_json(
            package_dir / profile_path,
            {
                "schemaVersion": 1,
                "module": "RuntimeVulkanLoaderFixture",
                "target": "vulkan",
                "nativeBinary": native_path,
                "debug": {
                    "disassembly": {
                        "status": "skipped-tool-missing",
                        "path": None,
                    },
                },
            },
        )
        self._write_json(
            package_dir / "reflection.json",
            {
                "schemaVersion": 1,
                "module": "RuntimeVulkanLoaderFixture",
                "target": "vulkan",
                "nativeBinary": native_path,
                "entryPoints": [
                    {
                        "stage": "compute",
                        "sourceName": "main",
                        "backendName": "runtime_vulkan_loader_main",
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
                "targetResourceBindings": [
                    {
                        "target": "vulkan",
                        "stage": "compute",
                        "entryPoint": "runtime_vulkan_loader_main",
                        "name": "OutputBuffer",
                        "kind": "storageBuffer",
                        "sourceType": "float4",
                        "addressSpace": "storage",
                        "abi": {"set": 0, "binding": 0},
                        "bindingClass": "storage-buffer",
                        "descriptorType": "VK_DESCRIPTOR_TYPE_STORAGE_BUFFER",
                        "storageClass": "StorageBuffer",
                        "spirvType": "%_runtimearr_v4float",
                        "evidenceId": (
                            "target-legalization.v1.vulkan.resource-binding.compute."
                            "runtime_vulkan_loader_main.OutputBuffer"
                        ),
                    }
                ],
                "targetFeatures": [
                    {"target": "vulkan", "kind": "package", "name": "fixture"}
                ],
            },
        )
        self._write_json(
            package_dir / "diagnostics.json",
            {"schemaVersion": 1, "diagnostics": []},
        )
        self._write_native_artifact_descriptor(
            package_dir,
            descriptor_path=descriptor_path,
            target="vulkan",
            binary_kind=descriptor_binary_kind,
            source_path="source/RuntimeVulkanLoaderFixture.cgl",
            source_bytes=b"CrossGL source bytes intentionally not read by loader",
            artifact_path=native_path,
            artifact_bytes=native_bytes,
        )

    def _write_package_json(
        self,
        package_dir: Path,
        *,
        target: str,
        native_binary_path: str,
        artifacts: dict[str, object],
        binding: dict[str, object],
    ) -> None:
        self._write_json(
            package_dir / "manifest.json",
            {
                "schemaVersion": 1,
                "compiler": {
                    "name": "CrossGL-Compiler",
                    "version": "test",
                    "llvmVersion": "not-found",
                },
                "module": "RuntimeVulkanLoaderFixture",
                "target": target,
                "sourceHash": {"algorithm": "sha256", "value": "0" * 64},
                "artifacts": artifacts,
            },
        )
        self._write_json(
            package_dir / "reflection.json",
            {
                "schemaVersion": 1,
                "module": "RuntimeVulkanLoaderFixture",
                "target": target,
                "nativeBinary": native_binary_path,
                "entryPoints": [
                    {
                        "stage": "compute",
                        "sourceName": "main",
                        "backendName": "runtime_vulkan_loader_main",
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

    def _write_json(self, path: Path, document: object) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(document, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )

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

    def _write_native_artifact_descriptor(
        self,
        package_dir: Path,
        *,
        descriptor_path: str,
        target: str,
        binary_kind: str,
        source_path: str,
        source_bytes: bytes,
        artifact_path: str,
        artifact_bytes: bytes,
    ) -> None:
        self._write_json(
            package_dir / descriptor_path,
            {
                "schemaVersion": 1,
                "kind": "crossgl.nativeArtifact",
                "contractVersion": "native-artifact-v0",
                "target": target,
                "binaryKind": binary_kind,
                "sourcePath": source_path,
                "sourceHash": self._sha256(source_bytes),
                "artifactPath": artifact_path,
                "artifactHash": self._sha256(artifact_bytes),
                "sizeBytes": len(artifact_bytes),
                "toolchainProvenance": {
                    "producer": "tests.runtime.test_vulkan_loader",
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
                "validationStatus": "not-run",
                "validationDiagnostics": [],
            },
        )

    def _sha256(self, payload: bytes) -> dict[str, str]:
        return {
            "algorithm": "sha256",
            "value": hashlib.sha256(payload).hexdigest(),
        }

    def _artifact_compatibility_record(
        self,
        artifact_compatibility: dict[str, object],
        name: str,
    ) -> dict[str, object]:
        records = artifact_compatibility.get("artifacts", [])
        self.assertIsInstance(records, list)
        for record in records:
            if isinstance(record, dict) and record.get("name") == name:
                return record
        self.fail(f"missing artifact compatibility record: {name}")

    @contextlib.contextmanager
    def _guard_compiler_and_device_work(self) -> Iterator[None]:
        original_import = builtins.__import__
        forbidden_import_roots = {"compiler", "spirv_tools", "vulkan"}

        def guarded_import(
            name: str,
            globals: object | None = None,
            locals: object | None = None,
            fromlist: tuple[object, ...] = (),
            level: int = 0,
        ) -> object:
            root = name.partition(".")[0].lower()
            if level == 0 and root in forbidden_import_roots:
                raise AssertionError(f"loader imported compiler/device module: {name}")
            return original_import(name, globals, locals, fromlist, level)

        with (
            mock.patch(
                "subprocess.run",
                side_effect=AssertionError("loader invoked compiler subprocess"),
            ),
            mock.patch(
                "ctypes.CDLL",
                side_effect=AssertionError("loader opened graphics device library"),
            ),
            mock.patch("builtins.__import__", side_effect=guarded_import),
        ):
            yield

    def _guard_source_reads(self) -> object:
        original_read_text = Path.read_text
        original_read_bytes = Path.read_bytes
        original_open = Path.open
        guarded_suffixes = {".cgl", ".hlsl", ".glsl", ".metal"}

        def _assert_allowed_path(path: Path) -> None:
            if path.suffix in guarded_suffixes:
                raise AssertionError(f"loader parsed source artifact: {path}")

        def guarded_read_text(path: Path, *args: object, **kwargs: object) -> str:
            _assert_allowed_path(path)
            return original_read_text(path, *args, **kwargs)

        def guarded_read_bytes(path: Path, *args: object, **kwargs: object) -> bytes:
            _assert_allowed_path(path)
            return original_read_bytes(path, *args, **kwargs)

        def guarded_open(path: Path, *args: object, **kwargs: object) -> object:
            _assert_allowed_path(path)
            return original_open(path, *args, **kwargs)

        return mock.patch.multiple(
            Path,
            read_text=guarded_read_text,
            read_bytes=guarded_read_bytes,
            open=guarded_open,
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

        def _assert_allowed_path(path: Path) -> None:
            if path.resolve() in forbidden_resolved_paths:
                raise AssertionError(f"loader read stale descriptor path: {path}")
            if path.suffix == ".cgl":
                raise AssertionError(f"loader parsed CrossGL source: {path}")

        def guarded_read_text(path: Path, *args: object, **kwargs: object) -> str:
            _assert_allowed_path(path)
            return original_read_text(path, *args, **kwargs)

        def guarded_read_bytes(path: Path, *args: object, **kwargs: object) -> bytes:
            _assert_allowed_path(path)
            return original_read_bytes(path, *args, **kwargs)

        def guarded_open(path: Path, *args: object, **kwargs: object) -> object:
            _assert_allowed_path(path)
            return original_open(path, *args, **kwargs)

        return mock.patch.multiple(
            Path,
            read_text=guarded_read_text,
            read_bytes=guarded_read_bytes,
            open=guarded_open,
        )


if __name__ == "__main__":
    unittest.main()
