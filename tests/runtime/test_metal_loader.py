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


from runtime.metal_loader import plan_metal_native_loader  # noqa: E402
from runtime.loader import read_loader_plan  # noqa: E402
from runtime.package_reader import PackageReadError  # noqa: E402


class MetalNativeLoaderPlanTests(unittest.TestCase):
    def test_ready_plan_uses_native_artifact_and_reflection_without_source_parse(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory(suffix=".cglb") as temp_dir:
            package_dir = Path(temp_dir)
            self._write_valid_metal_package(package_dir)
            source_path = package_dir / "source" / "invalid.cgl"
            source_path.parent.mkdir()
            source_path.write_text(
                "Metal native loader must not parse source\n",
                encoding="utf-8",
            )

            with self._guard_crossgl_source_reads():
                plan = plan_metal_native_loader(package_dir)
                summary = plan.to_summary()

            self.assertTrue(plan.ready, summary["diagnostics"])
            self.assertTrue(plan.planned)
            self.assertTrue(plan.loadable)
            self.assertIs(plan.require_ready(), plan)
            self.assertEqual(plan.status, "ready")
            self.assertFalse(plan.source_parsing_required)
            self.assertFalse(plan.device_execution_required)
            self.assertEqual(plan.native_artifact.name, "nativeBinary")
            self.assertEqual(
                plan.native_artifact.package_path,
                "backend/metal/RuntimeMetalLoaderFixture.metallib",
            )
            self.assertEqual(summary["loader"], "metal-native")
            self.assertEqual(summary["target"], "metal")
            self.assertEqual(summary["sourceInputs"], [])
            self.assertEqual(summary["compilerInvocationRequired"], False)
            self.assertEqual(summary["deviceExecutionRequired"], False)
            self.assertEqual(
                [
                    (artifact["name"], artifact["path"])
                    for artifact in summary["artifactInputs"]
                ],
                [
                    (
                        "backendSource",
                        "backend/metal/RuntimeMetalLoaderFixture.metal",
                    ),
                    (
                        "intermediate",
                        "backend/metal/RuntimeMetalLoaderFixture.air",
                    ),
                    (
                        "nativeBinary",
                        "backend/metal/RuntimeMetalLoaderFixture.metallib",
                    ),
                ],
            )
            self.assertEqual(summary["nativeArtifact"]["exists"], True)
            self.assertEqual(summary["nativeArtifact"]["name"], "nativeBinary")
            self.assertEqual(
                summary["nativeArtifact"]["path"],
                "backend/metal/RuntimeMetalLoaderFixture.metallib",
            )
            self.assertEqual(summary["reflection"]["entryPointCount"], 1)
            self.assertEqual(summary["reflection"]["resourceCount"], 1)
            self.assertEqual(summary["reflection"]["targetResourceBindingCount"], 1)
            self.assertEqual(
                summary["reflection"]["targetResourceBindings"][0]["abi"],
                {"buffer": 0},
            )
            runtime_summary = summary["runtimePlan"]
            self.assertEqual(runtime_summary["loaderTarget"], "metal")
            self.assertEqual(runtime_summary["sourceInputs"], [])
            self.assertEqual(runtime_summary["compilerInvocationRequired"], False)
            self.assertEqual(runtime_summary["deviceExecutionRequired"], False)
            self.assertEqual(
                runtime_summary["requiredArtifactPaths"],
                {
                    "backendSource": ("backend/metal/RuntimeMetalLoaderFixture.metal"),
                    "intermediate": "backend/metal/RuntimeMetalLoaderFixture.air",
                    "nativeBinary": (
                        "backend/metal/RuntimeMetalLoaderFixture.metallib"
                    ),
                },
            )
            self.assertEqual(
                runtime_summary["runtimeArtifactSelection"]["selectedPackageMode"],
                "native",
            )
            self.assertEqual(
                runtime_summary["runtimeArtifactSelection"]["artifact"]["name"],
                "nativeBinary",
            )
            metadata_contract = runtime_summary["metadataContract"]
            self.assertEqual(metadata_contract["loaderTarget"], "metal")
            self.assertEqual(metadata_contract["sourceInputs"], [])
            self.assertEqual(
                metadata_contract["compilerInvocationRequired"],
                False,
            )
            self.assertEqual(metadata_contract["deviceExecutionRequired"], False)
            self.assertEqual(
                metadata_contract["requiredArtifactInputs"],
                [
                    {
                        "name": "backendSource",
                        "path": "backend/metal/RuntimeMetalLoaderFixture.metal",
                        "declaredBy": "manifest.artifacts.backendSource",
                    },
                    {
                        "name": "intermediate",
                        "path": "backend/metal/RuntimeMetalLoaderFixture.air",
                        "declaredBy": "manifest.artifacts.intermediate",
                    },
                    {
                        "name": "nativeBinary",
                        "path": ("backend/metal/RuntimeMetalLoaderFixture.metallib"),
                        "declaredBy": "manifest.artifacts.nativeBinary",
                    },
                ],
            )
            self.assertEqual(
                [
                    (artifact["name"], artifact["selectedForLoad"])
                    for artifact in metadata_contract["selectedArtifactInputs"]
                ],
                [
                    ("backendSource", False),
                    ("intermediate", False),
                    ("nativeBinary", True),
                ],
            )
            self.assertEqual(
                metadata_contract["runtimeArtifact"],
                {
                    "name": "nativeBinary",
                    "path": "backend/metal/RuntimeMetalLoaderFixture.metallib",
                    "declaredBy": "manifest.artifacts.nativeBinary",
                },
            )
            self.assertEqual(summary["rejectReasons"], [])
            self.assertEqual(list(package_dir.rglob("*.cgl")), [source_path])

    def test_native_and_auto_package_modes_select_metal_native_binary(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory(suffix=".cglb") as temp_dir:
            package_dir = Path(temp_dir)
            self._write_valid_metal_package(package_dir)
            source_path = package_dir / "source" / "invalid.cgl"
            source_path.parent.mkdir()
            source_path.write_text(
                "package mode selection must stay source-free\n",
                encoding="utf-8",
            )

            with self._guard_crossgl_source_reads():
                auto_plan = read_loader_plan(package_dir, "metal")
                native_plan = read_loader_plan(
                    package_dir,
                    "metal",
                    package_mode="native",
                )
                source_package_plan = read_loader_plan(
                    package_dir,
                    "metal",
                    package_mode="source-package",
                )

            auto_summary = auto_plan.to_summary()
            native_summary = native_plan.to_summary()
            source_package_summary = source_package_plan.to_summary()

            self.assertTrue(auto_plan.loadable, auto_summary["diagnostics"])
            self.assertEqual(auto_plan.require_runtime_artifact().name, "nativeBinary")
            self.assertEqual(
                auto_summary["runtimeArtifactSelection"]["requestedPackageMode"],
                "auto",
            )
            self.assertEqual(
                auto_summary["runtimeArtifactSelection"]["selectedPackageMode"],
                "native",
            )
            self.assertEqual(
                auto_summary["runtimeArtifactSelection"]["artifact"]["path"],
                "backend/metal/RuntimeMetalLoaderFixture.metallib",
            )

            self.assertTrue(native_plan.loadable, native_summary["diagnostics"])
            self.assertEqual(
                native_plan.require_runtime_artifact().package_path,
                "backend/metal/RuntimeMetalLoaderFixture.metallib",
            )
            self.assertEqual(
                native_summary["runtimeArtifactSelection"]["requestedPackageMode"],
                "native",
            )
            self.assertEqual(
                native_summary["runtimeArtifactSelection"]["selectedPackageMode"],
                "native",
            )

            self.assertFalse(source_package_plan.loadable)
            self.assertFalse(source_package_plan.source_parsing_required)
            self.assertIsNone(source_package_plan.runtime_artifact)
            self.assertEqual(source_package_summary["sourceInputs"], [])
            self.assertEqual(
                source_package_summary["runtimeArtifactSelection"][
                    "requestedPackageMode"
                ],
                "source-package",
            )
            self.assertIsNone(
                source_package_summary["runtimeArtifactSelection"]["artifact"]
            )
            self.assertIn(
                "package.mode.unsupported",
                [
                    diagnostic["code"]
                    for diagnostic in source_package_summary["rejectReasons"]
                ],
            )
            self.assertEqual(list(package_dir.rglob("*.cgl")), [source_path])

    def test_source_free_plan_uses_manifest_descriptor_and_ignores_legacy_path(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory(suffix=".cglb") as temp_dir:
            package_dir = Path(temp_dir)
            descriptor_path = (
                "backend/metal/RuntimeMetalLoaderFixture.native-artifact.json"
            )
            self._write_source_free_metal_package(
                package_dir,
                descriptor_path=descriptor_path,
            )
            source_path = package_dir / "source" / "RuntimeMetalLoaderFixture.cgl"
            source_path.parent.mkdir()
            source_path.write_text(
                "native descriptor packages must not parse CrossGL source\n",
                encoding="utf-8",
            )
            legacy_descriptor_path = package_dir / "metadata" / "native-artifact.json"
            legacy_descriptor_path.parent.mkdir()
            legacy_descriptor_path.write_text(
                '{"target": "directx", "binaryKind": "directx.dxil"}\n',
                encoding="utf-8",
            )

            with self._guard_crossgl_source_reads(
                forbidden_paths={legacy_descriptor_path},
            ):
                plan = plan_metal_native_loader(package_dir)
                summary = plan.to_summary()

            descriptor_summary = summary["nativeArtifactDescriptor"]
            expected_metallib_hash = self._sha256(b"metallib")
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
            self.assertEqual(
                [
                    (artifact["name"], artifact["path"])
                    for artifact in summary["artifactInputs"]
                ],
                [
                    (
                        "nativeBinary",
                        "backend/metal/RuntimeMetalLoaderFixture.metallib",
                    )
                ],
            )
            self.assertEqual(
                summary["nativeArtifact"]["path"],
                "backend/metal/RuntimeMetalLoaderFixture.metallib",
            )
            self.assertIsNotNone(descriptor_summary)
            self.assertTrue(descriptor_summary["readable"])
            self.assertEqual(descriptor_summary["artifact"]["path"], descriptor_path)
            self.assertEqual(
                descriptor_summary["fields"]["binaryKind"],
                "metal.metallib",
            )
            self.assertEqual(
                descriptor_summary["fields"]["artifactPath"],
                "backend/metal/RuntimeMetalLoaderFixture.metallib",
            )
            self.assertEqual(
                descriptor_summary["fields"]["artifactHash"],
                expected_metallib_hash,
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
                descriptor_summary["expectedBinaryKinds"],
                ["metal.metallib"],
            )
            self.assertTrue(descriptor_summary["binaryKindMatchesLoader"])
            metal_admission = summary["metalNativeAdmission"]
            self.assertEqual(metal_admission["decision"], "accepted")
            self.assertEqual(
                metal_admission["reason"],
                ("metal_loader.native_metallib_admission.accepted"),
            )
            self.assertEqual(metal_admission["loaderTarget"], "metal")
            self.assertEqual(metal_admission["packageTarget"], "metal")
            self.assertEqual(metal_admission["sourceParsingRequired"], False)
            self.assertEqual(metal_admission["compilerInvocationRequired"], False)
            self.assertEqual(metal_admission["deviceExecutionRequired"], False)
            self.assertEqual(
                metal_admission["targetLegalizationEvidence"],
                summary["targetLegalizationEvidence"],
            )
            self.assertEqual(
                metal_admission["targetLegalizationToolRequirements"],
                summary["targetLegalizationToolRequirements"],
            )
            self.assertEqual(
                metal_admission["packageArtifactRequirementsSource"],
                summary["packageArtifactRequirementsSource"],
            )
            self.assertEqual(
                metal_admission["packageArtifactRequirements"],
                summary["packageArtifactRequirements"],
            )
            self.assertEqual(
                summary["metalNativeApiBoundary"]["targetLegalizationEvidence"],
                summary["targetLegalizationEvidence"],
            )
            self.assertEqual(
                summary["metalNativeApiBoundary"]["targetLegalizationToolRequirements"],
                summary["targetLegalizationToolRequirements"],
            )
            self.assertEqual(
                summary["metalNativeApiBoundary"]["packageArtifactRequirementsSource"],
                summary["packageArtifactRequirementsSource"],
            )
            self.assertEqual(
                summary["metalNativeApiBoundary"]["packageArtifactRequirements"],
                summary["packageArtifactRequirements"],
            )
            self.assertTrue(metal_admission["requiredChecksPassed"])
            self.assertEqual(metal_admission["blockedByDiagnostics"], [])
            metallib_admission = metal_admission["metallibArtifact"]
            self.assertTrue(metallib_admission["declared"])
            self.assertTrue(metallib_admission["exists"])
            self.assertTrue(metallib_admission["selectedForRuntime"])
            self.assertTrue(metallib_admission["acceptedForLoad"])
            self.assertEqual(
                metallib_admission["path"],
                "backend/metal/RuntimeMetalLoaderFixture.metallib",
            )
            self.assertEqual(metallib_admission["expectedPathSuffix"], ".metallib")
            self.assertEqual(metallib_admission["pathSuffix"], ".metallib")
            self.assertTrue(metallib_admission["pathSuffixMatchesMetallib"])
            self.assertEqual(metallib_admission["expectedBinaryKind"], "metal.metallib")
            self.assertEqual(
                metallib_admission["descriptorBinaryKind"], "metal.metallib"
            )
            self.assertEqual(
                metallib_admission["descriptorArtifactHash"],
                expected_metallib_hash,
            )
            self.assertTrue(metallib_admission["descriptorArtifactHashMatchesMetallib"])
            descriptor_admission = metal_admission["nativeArtifactDescriptor"]
            self.assertTrue(descriptor_admission["declared"])
            self.assertTrue(descriptor_admission["readable"])
            self.assertEqual(descriptor_admission["target"], "metal")
            self.assertTrue(descriptor_admission["targetMatchesLoader"])
            self.assertEqual(descriptor_admission["binaryKind"], "metal.metallib")
            self.assertTrue(descriptor_admission["binaryKindMatchesLoader"])
            self.assertEqual(
                descriptor_admission["artifactPath"],
                "backend/metal/RuntimeMetalLoaderFixture.metallib",
            )
            self.assertTrue(descriptor_admission["artifactPathMatchesNativeArtifact"])
            self.assertTrue(descriptor_admission["artifactPathSuffixMatchesMetallib"])
            self.assertEqual(
                descriptor_admission["artifactHash"],
                expected_metallib_hash,
            )
            self.assertTrue(descriptor_admission["artifactHashMatchesArtifact"])
            self.assertTrue(descriptor_admission["sizeBytesMatchesArtifact"])
            self.assertEqual(
                metal_admission["reflection"]["entryPoints"][0]["backendName"],
                "runtime_metal_loader_main",
            )
            self.assertEqual(
                metal_admission["reflection"]["targetResourceBindings"][0][
                    "bufferIndex"
                ],
                0,
            )
            checks = {check["name"]: check for check in metal_admission["checks"]}
            self.assertTrue(checks["manifestTargetMatchesLoader"]["passed"])
            self.assertTrue(checks["nativeBinaryPathSuffixMatchesMetallib"]["passed"])
            self.assertTrue(
                checks["nativeArtifactDescriptorBinaryKindMatchesLoader"]["passed"]
            )
            self.assertTrue(
                checks["nativeArtifactDescriptorArtifactPathMatchesNativeBinary"][
                    "passed"
                ]
            )
            self.assertTrue(
                checks["nativeArtifactDescriptorArtifactPathSuffixMatchesMetallib"][
                    "passed"
                ]
            )
            self.assertTrue(
                checks["nativeArtifactDescriptorArtifactHashDeclared"]["passed"]
            )
            self.assertTrue(
                checks["nativeArtifactDescriptorArtifactHashMatchesMetallib"]["passed"]
            )
            api_boundary = summary["metalNativeApiBoundary"]
            self.assertEqual(api_boundary["boundary"], "metal.native-api.metadata-v0")
            self.assertEqual(api_boundary["decision"], "accepted")
            self.assertTrue(api_boundary["metadataOnly"])
            self.assertEqual(api_boundary["sourceInputs"], [])
            self.assertFalse(api_boundary["sourceParsingRequired"])
            self.assertFalse(api_boundary["compilerInvocationRequired"])
            self.assertFalse(api_boundary["deviceExecutionRequired"])
            self.assertFalse(api_boundary["metalFrameworkCallsPerformed"])
            self.assertFalse(api_boundary["metalDeviceCreationPerformed"])
            self.assertFalse(api_boundary["metalLibraryCreationPerformed"])
            self.assertFalse(api_boundary["metalPipelineCreationPerformed"])
            self.assertFalse(api_boundary["metalCommandExecutionPerformed"])
            api_inputs = api_boundary["runtimeInputs"]
            self.assertEqual(
                api_inputs["metallibArtifact"]["path"],
                "backend/metal/RuntimeMetalLoaderFixture.metallib",
            )
            self.assertEqual(
                api_inputs["metallibArtifact"]["descriptorArtifactHash"],
                expected_metallib_hash,
            )
            self.assertTrue(
                api_inputs["metallibArtifact"]["descriptorArtifactHashMatchesMetallib"]
            )
            self.assertEqual(
                api_inputs["nativeArtifactDescriptor"]["artifactHash"],
                expected_metallib_hash,
            )
            self.assertTrue(
                api_inputs["nativeArtifactDescriptor"]["artifactHashMatchesMetallib"]
            )
            self.assertFalse(
                api_inputs["nativeArtifactDescriptor"]["sourcePathExposed"]
            )
            self.assertEqual(api_inputs["reflection"]["resourceCount"], 1)
            self.assertEqual(
                api_inputs["reflection"]["targetResourceBindings"][0]["bufferIndex"],
                0,
            )
            self.assertEqual(
                api_inputs["versionCompatibility"],
                summary["runtimePlan"]["versionCompatibility"],
            )
            self.assertTrue(api_boundary["descriptorFreshness"]["artifactHashDeclared"])
            self.assertTrue(
                api_boundary["descriptorFreshness"]["artifactHashMatchesMetallib"]
            )
            self.assertEqual(summary["rejectReasons"], [])
            self.assertEqual(list(package_dir.rglob("*.cgl")), [source_path])

    def test_ready_zip_plan_uses_native_artifact_and_descriptor_without_source_parse(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir)
            package_dir = temp_root / "package-dir"
            package_dir.mkdir()
            descriptor_path = (
                "backend/metal/RuntimeMetalLoaderFixture.native-artifact.json"
            )
            self._write_source_free_metal_package(
                package_dir,
                descriptor_path=descriptor_path,
            )
            source_path = package_dir / "source" / "RuntimeMetalLoaderFixture.cgl"
            source_path.parent.mkdir()
            source_path.write_text(
                "zip native loader must not parse CrossGL source\n",
                encoding="utf-8",
            )
            zip_path = temp_root / "RuntimeMetalLoaderFixture.cglb"
            self._write_zip_package(
                package_dir,
                zip_path,
                prefix=zip_path.name,
            )

            with (
                self._guard_crossgl_source_reads(),
                self._guard_crossgl_source_archive_reads(),
                self._guard_compiler_processes(),
            ):
                plan = plan_metal_native_loader(zip_path)
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
            self.assertIsNotNone(plan.native_artifact)
            self.assertEqual(plan.native_artifact.archive_path, zip_path)
            self.assertEqual(
                plan.native_artifact.archive_member,
                f"{zip_path.name}/backend/metal/RuntimeMetalLoaderFixture.metallib",
            )
            self.assertTrue(
                summary["nativeArtifact"]["absolutePath"].startswith(f"{zip_path}!/")
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
                "metal.metallib",
            )
            self.assertEqual(
                descriptor_summary["fields"]["artifactPath"],
                "backend/metal/RuntimeMetalLoaderFixture.metallib",
            )
            self.assertEqual(
                descriptor_summary["expectedBinaryKinds"],
                ["metal.metallib"],
            )
            self.assertTrue(descriptor_summary["binaryKindMatchesLoader"])

    def test_ready_zip_native_package_reports_metal_admission_without_source_or_work(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir)
            package_dir = temp_root / "package-dir"
            package_dir.mkdir()
            descriptor_path = (
                "backend/metal/RuntimeMetalLoaderFixture.native-artifact.json"
            )
            native_path = "backend/metal/RuntimeMetalLoaderFixture.metallib"
            native_bytes = b"metallib"
            self._write_source_free_metal_package(
                package_dir,
                descriptor_path=descriptor_path,
                native_path=native_path,
                native_bytes=native_bytes,
            )
            source_path = package_dir / "source" / "RuntimeMetalLoaderFixture.cgl"
            source_path.parent.mkdir()
            source_path.write_text(
                "zip native admission must not parse CrossGL source\n",
                encoding="utf-8",
            )
            zip_path = temp_root / "RuntimeMetalLoaderFixture.cglb"
            self._write_zip_package(
                package_dir,
                zip_path,
                prefix=zip_path.name,
            )

            with (
                self._guard_crossgl_source_reads(),
                self._guard_crossgl_source_archive_reads(),
                self._guard_compiler_processes(),
            ):
                plan = plan_metal_native_loader(zip_path)
                summary = plan.to_summary()

            expected_hash = self._sha256(native_bytes)
            descriptor_summary = summary["nativeArtifactDescriptor"]
            native_admission = summary["nativeAdmission"]
            metal_admission = summary["metalNativeAdmission"]
            api_boundary = summary["metalNativeApiBoundary"]
            api_inputs = api_boundary["runtimeInputs"]

            self.assertTrue(plan.ready, summary["diagnostics"])
            self.assertIs(plan.require_ready(), plan)
            self.assertEqual(summary["runtimePlan"]["packageFormat"], "zip")
            self.assertEqual(summary["sourceInputs"], [])
            self.assertFalse(summary["compilerInvocationRequired"])
            self.assertFalse(summary["deviceExecutionRequired"])
            self.assertEqual(summary["rejectReasons"], [])
            self.assertIsNotNone(plan.native_artifact)
            self.assertEqual(plan.native_artifact.archive_path, zip_path)
            self.assertEqual(
                plan.native_artifact.archive_member,
                f"{zip_path.name}/{native_path}",
            )
            self.assertEqual(summary["nativeArtifact"]["path"], native_path)
            self.assertEqual(summary["nativeArtifact"]["size"], len(native_bytes))
            self.assertTrue(
                summary["nativeArtifact"]["absolutePath"].startswith(f"{zip_path}!/")
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
            self.assertEqual(descriptor_summary["fields"]["target"], "metal")
            self.assertEqual(
                descriptor_summary["fields"]["binaryKind"],
                "metal.metallib",
            )
            self.assertEqual(
                descriptor_summary["fields"]["artifactPath"],
                native_path,
            )
            self.assertEqual(
                descriptor_summary["fields"]["artifactHash"],
                expected_hash,
            )
            self.assertEqual(
                descriptor_summary["fields"]["sizeBytes"],
                len(native_bytes),
            )
            self.assertEqual(
                descriptor_summary["expectedBinaryKinds"],
                ["metal.metallib"],
            )
            self.assertTrue(descriptor_summary["binaryKindMatchesLoader"])

            self.assertEqual(native_admission["decision"], "accepted")
            self.assertEqual(native_admission["status"], "ready")
            self.assertEqual(native_admission["target"], "metal")
            self.assertEqual(native_admission["packageTarget"], "metal")
            self.assertFalse(native_admission["sourceParsingRequired"])
            self.assertFalse(native_admission["compilerInvocationRequired"])
            self.assertFalse(native_admission["deviceExecutionRequired"])
            self.assertEqual(
                native_admission["targetLegalizationEvidence"],
                summary["targetLegalizationEvidence"],
            )
            self.assertEqual(
                native_admission["targetLegalizationToolRequirements"],
                summary["targetLegalizationToolRequirements"],
            )
            self.assertEqual(
                native_admission["packageArtifactRequirementsSource"],
                summary["packageArtifactRequirementsSource"],
            )
            self.assertEqual(
                native_admission["packageArtifactRequirements"],
                summary["packageArtifactRequirements"],
            )
            self.assertEqual(native_admission["blockedByDiagnostics"], [])
            self.assertEqual(native_admission["nativeArtifact"]["path"], native_path)
            self.assertEqual(
                native_admission["nativeArtifact"]["artifact"]["size"],
                len(native_bytes),
            )
            descriptor_admission = native_admission["nativeArtifactDescriptor"]
            self.assertEqual(descriptor_admission["decision"], "accepted")
            self.assertEqual(descriptor_admission["fields"]["target"], "metal")
            self.assertEqual(
                descriptor_admission["fields"]["binaryKind"],
                "metal.metallib",
            )
            self.assertEqual(
                descriptor_admission["fields"]["artifactPath"],
                native_path,
            )
            self.assertEqual(
                descriptor_admission["fields"]["artifactHash"],
                expected_hash,
            )
            self.assertEqual(
                descriptor_admission["fields"]["sizeBytes"],
                len(native_bytes),
            )

            self.assertEqual(metal_admission["decision"], "accepted")
            self.assertEqual(metal_admission["status"], "ready")
            self.assertEqual(
                metal_admission["reason"],
                "metal_loader.native_metallib_admission.accepted",
            )
            self.assertEqual(metal_admission["loaderTarget"], "metal")
            self.assertEqual(metal_admission["packageTarget"], "metal")
            self.assertFalse(metal_admission["sourceParsingRequired"])
            self.assertFalse(metal_admission["compilerInvocationRequired"])
            self.assertFalse(metal_admission["deviceExecutionRequired"])
            self.assertTrue(metal_admission["requiredChecksPassed"])
            self.assertEqual(metal_admission["blockedByDiagnostics"], [])
            self.assertEqual(
                metal_admission["targetLegalizationEvidence"],
                summary["targetLegalizationEvidence"],
            )
            self.assertEqual(
                metal_admission["targetLegalizationToolRequirements"],
                summary["targetLegalizationToolRequirements"],
            )
            self.assertEqual(
                metal_admission["packageArtifactRequirementsSource"],
                summary["packageArtifactRequirementsSource"],
            )
            self.assertEqual(
                metal_admission["packageArtifactRequirements"],
                summary["packageArtifactRequirements"],
            )
            metallib_admission = metal_admission["metallibArtifact"]
            self.assertEqual(metallib_admission["path"], native_path)
            self.assertTrue(metallib_admission["exists"])
            self.assertTrue(metallib_admission["acceptedForLoad"])
            self.assertEqual(metallib_admission["size"], len(native_bytes))
            self.assertEqual(
                metallib_admission["descriptorArtifactHash"],
                expected_hash,
            )
            self.assertTrue(metallib_admission["descriptorArtifactHashMatchesMetallib"])
            descriptor_detail = metal_admission["nativeArtifactDescriptor"]
            self.assertEqual(descriptor_detail["target"], "metal")
            self.assertTrue(descriptor_detail["targetMatchesLoader"])
            self.assertEqual(descriptor_detail["binaryKind"], "metal.metallib")
            self.assertTrue(descriptor_detail["binaryKindMatchesLoader"])
            self.assertEqual(descriptor_detail["artifactPath"], native_path)
            self.assertTrue(descriptor_detail["artifactPathMatchesNativeArtifact"])
            self.assertEqual(descriptor_detail["artifactHash"], expected_hash)
            self.assertTrue(descriptor_detail["artifactHashMatchesArtifact"])
            self.assertEqual(descriptor_detail["sizeBytes"], len(native_bytes))
            self.assertTrue(descriptor_detail["sizeBytesMatchesArtifact"])

            checks = {check["name"]: check for check in metal_admission["checks"]}
            for check_name in [
                "manifestTargetMatchesLoader",
                "nativeBinaryDeclared",
                "nativeBinaryExists",
                "nativeBinaryPathSuffixMatchesMetallib",
                "nativeBinarySelectedForRuntime",
                "nativeArtifactDescriptorTargetMatchesLoader",
                "nativeArtifactDescriptorBinaryKindMatchesLoader",
                "nativeArtifactDescriptorArtifactPathMatchesNativeBinary",
                "nativeArtifactDescriptorSizeBytesMatchesArtifact",
                "nativeArtifactDescriptorArtifactHashDeclared",
                "nativeArtifactDescriptorArtifactHashMatchesMetallib",
            ]:
                self.assertTrue(checks[check_name]["passed"], check_name)

            self.assertEqual(api_boundary["boundary"], "metal.native-api.metadata-v0")
            self.assertEqual(api_boundary["decision"], "accepted")
            self.assertEqual(api_boundary["status"], "ready")
            self.assertEqual(
                api_boundary["reason"],
                "metal_loader.native_api_boundary.accepted",
            )
            self.assertEqual(api_boundary["loaderTarget"], "metal")
            self.assertEqual(api_boundary["packageTarget"], "metal")
            self.assertEqual(api_boundary["sourceInputs"], [])
            self.assertFalse(api_boundary["sourceParsingRequired"])
            self.assertFalse(api_boundary["compilerInvocationRequired"])
            self.assertFalse(api_boundary["deviceExecutionRequired"])
            self.assertFalse(api_boundary["metalFrameworkCallsPerformed"])
            self.assertFalse(api_boundary["metalDeviceCreationPerformed"])
            self.assertFalse(api_boundary["metalLibraryCreationPerformed"])
            self.assertFalse(api_boundary["metalPipelineCreationPerformed"])
            self.assertFalse(api_boundary["metalCommandExecutionPerformed"])
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
            self.assertEqual(api_inputs["metallibArtifact"]["path"], native_path)
            self.assertTrue(api_inputs["metallibArtifact"]["exists"])
            self.assertTrue(api_inputs["metallibArtifact"]["acceptedForLoad"])
            self.assertEqual(
                api_inputs["metallibArtifact"]["sizeBytes"],
                len(native_bytes),
            )
            self.assertEqual(
                api_inputs["metallibArtifact"]["descriptorArtifactHash"],
                expected_hash,
            )
            self.assertTrue(
                api_inputs["metallibArtifact"]["descriptorArtifactHashMatchesMetallib"]
            )
            descriptor_input = api_inputs["nativeArtifactDescriptor"]
            self.assertEqual(descriptor_input["target"], "metal")
            self.assertTrue(descriptor_input["targetMatchesLoader"])
            self.assertEqual(descriptor_input["binaryKind"], "metal.metallib")
            self.assertTrue(descriptor_input["binaryKindMatchesLoader"])
            self.assertEqual(descriptor_input["artifactPath"], native_path)
            self.assertTrue(descriptor_input["artifactPathMatchesMetallib"])
            self.assertEqual(descriptor_input["artifactHash"], expected_hash)
            self.assertTrue(descriptor_input["artifactHashMatchesMetallib"])
            self.assertEqual(descriptor_input["sizeBytes"], len(native_bytes))
            self.assertTrue(descriptor_input["sizeBytesMatchesMetallib"])
            self.assertFalse(descriptor_input["sourcePathExposed"])
            freshness = api_boundary["descriptorFreshness"]
            self.assertTrue(freshness["artifactPathMatchesMetallib"])
            self.assertTrue(freshness["artifactHashDeclared"])
            self.assertTrue(freshness["artifactHashMatchesMetallib"])
            self.assertTrue(freshness["sizeBytesMatchesMetallib"])
            self.assertEqual(freshness["failClosedDiagnosticCodes"], [])
            self.assertEqual(list(package_dir.rglob("*.cgl")), [source_path])

    def test_rejects_zip_missing_native_artifact_without_source_parse(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir)
            package_dir = temp_root / "package-dir"
            package_dir.mkdir()
            self._write_source_free_metal_package(
                package_dir,
                descriptor_path=(
                    "backend/metal/RuntimeMetalLoaderFixture.native-artifact.json"
                ),
            )
            source_path = package_dir / "source" / "RuntimeMetalLoaderFixture.cgl"
            source_path.parent.mkdir()
            source_path.write_text(
                "missing zip artifact must not parse CrossGL source\n",
                encoding="utf-8",
            )
            zip_path = temp_root / "RuntimeMetalLoaderFixture.cglb"
            self._write_zip_package(
                package_dir,
                zip_path,
                prefix=zip_path.name,
                exclude={"backend/metal/RuntimeMetalLoaderFixture.metallib"},
            )

            with (
                self._guard_crossgl_source_reads(),
                self._guard_crossgl_source_archive_reads(),
                self._guard_compiler_processes(),
            ):
                plan = plan_metal_native_loader(zip_path)
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
            self.assertIn(
                "package.artifact.required_file_missing",
                [diagnostic["code"] for diagnostic in summary["rejectReasons"]],
            )
            with self.assertRaisesRegex(PackageReadError, "nativeBinary"):
                plan.require_ready()

    def test_rejects_zip_stale_metallib_descriptor_without_source_or_work(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir)
            package_dir = temp_root / "package-dir"
            package_dir.mkdir()
            descriptor_path = (
                "backend/metal/RuntimeMetalLoaderFixture.native-artifact.json"
            )
            self._write_source_free_metal_package(
                package_dir,
                descriptor_path=descriptor_path,
            )
            (
                package_dir / "backend" / "metal" / "RuntimeMetalLoaderFixture.metallib"
            ).write_bytes(b"stale-metallib")
            source_path = package_dir / "source" / "RuntimeMetalLoaderFixture.cgl"
            source_path.parent.mkdir()
            source_path.write_text(
                "zip stale descriptor recovery must not parse CrossGL source\n",
                encoding="utf-8",
            )
            zip_path = temp_root / "RuntimeMetalLoaderFixture.cglb"
            self._write_zip_package(
                package_dir,
                zip_path,
                prefix=zip_path.name,
            )

            with (
                self._guard_crossgl_source_reads(),
                self._guard_crossgl_source_archive_reads(),
                self._guard_compiler_processes(),
            ):
                plan = plan_metal_native_loader(zip_path)
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
            self.assertEqual(
                summary["runtimePlan"]["metadataContract"]["sourceInputs"],
                [],
            )
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
            api_boundary = summary["metalNativeApiBoundary"]
            self.assertEqual(api_boundary["decision"], "rejected")
            self.assertFalse(api_boundary["metalFrameworkCallsPerformed"])
            self.assertFalse(api_boundary["metalDeviceCreationPerformed"])
            self.assertFalse(api_boundary["metalCommandExecutionPerformed"])
            self.assertIn(
                "package.native_artifact_descriptor.artifact_hash_mismatch",
                api_boundary["descriptorFreshness"]["failClosedDiagnosticCodes"],
            )
            self.assertFalse(
                api_boundary["descriptorFreshness"]["artifactHashMatchesMetallib"]
            )
            self.assertFalse(
                api_boundary["descriptorFreshness"]["sizeBytesMatchesMetallib"]
            )
            with self.assertRaisesRegex(PackageReadError, "artifact"):
                plan.require_ready()

    def test_rejects_zip_missing_metallib_descriptor_hash_without_source_or_work(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir)
            package_dir = temp_root / "package-dir"
            package_dir.mkdir()
            descriptor_path = (
                "backend/metal/RuntimeMetalLoaderFixture.native-artifact.json"
            )
            self._write_source_free_metal_package(
                package_dir,
                descriptor_path=descriptor_path,
            )
            descriptor_file = package_dir / descriptor_path
            descriptor = json.loads(descriptor_file.read_text(encoding="utf-8"))
            descriptor.pop("artifactHash")
            self._write_json(descriptor_file, descriptor)
            source_path = package_dir / "source" / "RuntimeMetalLoaderFixture.cgl"
            source_path.parent.mkdir()
            source_path.write_text(
                "zip malformed descriptor recovery must not parse CrossGL source\n",
                encoding="utf-8",
            )
            zip_path = temp_root / "RuntimeMetalLoaderFixture.cglb"
            self._write_zip_package(
                package_dir,
                zip_path,
                prefix=zip_path.name,
            )

            with (
                self._guard_crossgl_source_reads(),
                self._guard_crossgl_source_archive_reads(),
                self._guard_compiler_processes(),
            ):
                plan = plan_metal_native_loader(zip_path)
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
            api_boundary = summary["metalNativeApiBoundary"]
            self.assertEqual(api_boundary["decision"], "rejected")
            self.assertFalse(api_boundary["metalFrameworkCallsPerformed"])
            self.assertFalse(api_boundary["metalDeviceCreationPerformed"])
            self.assertFalse(api_boundary["metalCommandExecutionPerformed"])
            self.assertIn(
                "package.native_artifact_descriptor.artifact_hash_invalid",
                api_boundary["descriptorFreshness"]["failClosedDiagnosticCodes"],
            )
            self.assertFalse(
                api_boundary["descriptorFreshness"]["artifactHashDeclared"]
            )
            self.assertFalse(
                api_boundary["descriptorFreshness"]["artifactHashMatchesMetallib"]
            )
            with self.assertRaisesRegex(PackageReadError, "artifactHash"):
                plan.require_ready()

    def test_descriptor_binary_kind_mismatch_rejects_source_free_plan(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory(suffix=".cglb") as temp_dir:
            package_dir = Path(temp_dir)
            self._write_source_free_metal_package(
                package_dir,
                descriptor_path=(
                    "backend/metal/RuntimeMetalLoaderFixture.native-artifact.json"
                ),
                descriptor_binary_kind="vulkan.spirv-module",
            )
            source_path = package_dir / "source" / "RuntimeMetalLoaderFixture.cgl"
            source_path.parent.mkdir()
            source_path.write_text(
                "descriptor rejection must stay source-free\n",
                encoding="utf-8",
            )

            with self._guard_crossgl_source_reads():
                plan = plan_metal_native_loader(package_dir)
                summary = plan.to_summary()

            descriptor_summary = summary["nativeArtifactDescriptor"]
            metal_admission = summary["metalNativeAdmission"]
            self.assertFalse(plan.ready)
            self.assertIsNone(plan.native_artifact)
            self.assertEqual(summary["sourceInputs"], [])
            self.assertIsNotNone(descriptor_summary)
            self.assertTrue(descriptor_summary["readable"])
            self.assertEqual(
                descriptor_summary["fields"]["binaryKind"],
                "vulkan.spirv-module",
            )
            self.assertEqual(
                descriptor_summary["expectedBinaryKinds"],
                ["metal.metallib"],
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
            self.assertEqual(descriptor_reject["expected"], ["metal.metallib"])
            self.assertEqual(descriptor_reject["actual"], "vulkan.spirv-module")
            self.assertEqual(metal_admission["decision"], "rejected")
            self.assertEqual(
                metal_admission["nativeArtifactDescriptor"]["binaryKind"],
                "vulkan.spirv-module",
            )
            self.assertFalse(
                metal_admission["nativeArtifactDescriptor"]["binaryKindMatchesLoader"]
            )
            mismatch_checks = {
                check["name"]: check for check in metal_admission["checks"]
            }
            self.assertFalse(
                mismatch_checks["nativeArtifactDescriptorBinaryKindMatchesLoader"][
                    "passed"
                ]
            )
            self.assertFalse(metal_admission["requiredChecksPassed"])
            with self.assertRaisesRegex(PackageReadError, "binaryKind"):
                plan.require_ready()
            self.assertEqual(list(package_dir.rglob("*.cgl")), [source_path])

    def test_rejects_zip_descriptor_binary_kind_mismatch_without_source_or_work(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir)
            package_dir = temp_root / "package-dir"
            package_dir.mkdir()
            descriptor_path = (
                "backend/metal/RuntimeMetalLoaderFixture.native-artifact.json"
            )
            self._write_source_free_metal_package(
                package_dir,
                descriptor_path=descriptor_path,
            )
            descriptor_file = package_dir / descriptor_path
            descriptor = json.loads(descriptor_file.read_text(encoding="utf-8"))
            descriptor["binaryKind"] = "vulkan.spirv-module"
            self._write_json(descriptor_file, descriptor)
            source_path = package_dir / "source" / "RuntimeMetalLoaderFixture.cgl"
            source_path.parent.mkdir()
            source_path.write_text(
                "zip descriptor compatibility must not parse CrossGL source\n",
                encoding="utf-8",
            )
            zip_path = temp_root / "RuntimeMetalLoaderFixture.cglb"
            self._write_zip_package(
                package_dir,
                zip_path,
                prefix=zip_path.name,
            )

            with (
                self._guard_crossgl_source_reads(),
                self._guard_crossgl_source_archive_reads(),
                self._guard_compiler_processes(),
            ):
                plan = plan_metal_native_loader(zip_path)
                summary = plan.to_summary()

            descriptor_summary = summary["nativeArtifactDescriptor"]
            metal_admission = summary["metalNativeAdmission"]
            self.assertFalse(plan.ready)
            self.assertFalse(plan.source_parsing_required)
            self.assertFalse(plan.device_execution_required)
            self.assertIsNone(plan.native_artifact)
            self.assertEqual(summary["runtimePlan"]["packageFormat"], "zip")
            self.assertEqual(summary["sourceInputs"], [])
            self.assertEqual(summary["compilerInvocationRequired"], False)
            self.assertEqual(summary["deviceExecutionRequired"], False)
            self.assertIsNone(summary["nativeArtifact"])
            self.assertIsNotNone(descriptor_summary)
            self.assertTrue(descriptor_summary["readable"])
            self.assertEqual(
                descriptor_summary["fields"]["binaryKind"],
                "vulkan.spirv-module",
            )
            self.assertEqual(
                descriptor_summary["expectedBinaryKinds"],
                ["metal.metallib"],
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
            self.assertEqual(descriptor_reject["artifact"], "nativeArtifactDescriptor")
            self.assertEqual(descriptor_reject["path"], "binaryKind")
            self.assertEqual(descriptor_reject["expected"], ["metal.metallib"])
            self.assertEqual(descriptor_reject["actual"], "vulkan.spirv-module")
            self.assertEqual(metal_admission["decision"], "rejected")
            descriptor_admission = metal_admission["nativeArtifactDescriptor"]
            self.assertTrue(descriptor_admission["declared"])
            self.assertTrue(descriptor_admission["readable"])
            self.assertEqual(
                descriptor_admission["binaryKind"],
                "vulkan.spirv-module",
            )
            self.assertFalse(descriptor_admission["binaryKindMatchesLoader"])
            checks = {check["name"]: check for check in metal_admission["checks"]}
            self.assertFalse(
                checks["nativeArtifactDescriptorBinaryKindMatchesLoader"]["passed"]
            )
            self.assertFalse(metal_admission["requiredChecksPassed"])
            api_boundary = summary["metalNativeApiBoundary"]
            self.assertEqual(api_boundary["decision"], "rejected")
            self.assertFalse(api_boundary["metalFrameworkCallsPerformed"])
            self.assertFalse(api_boundary["metalDeviceCreationPerformed"])
            self.assertFalse(api_boundary["metalLibraryCreationPerformed"])
            self.assertFalse(api_boundary["metalPipelineCreationPerformed"])
            self.assertFalse(api_boundary["metalCommandExecutionPerformed"])
            with self.assertRaisesRegex(PackageReadError, "binaryKind"):
                plan.require_ready()

    def test_rejects_native_artifact_tampered_to_crossgl_source(self) -> None:
        with tempfile.TemporaryDirectory(suffix=".cglb") as temp_dir:
            package_dir = Path(temp_dir)
            self._write_valid_metal_package(package_dir)
            forged_path = "source/forged.cgl"
            (package_dir / forged_path).parent.mkdir(parents=True)
            (package_dir / forged_path).write_bytes(b"forged native bytes")

            manifest_path = package_dir / "manifest.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["artifacts"]["nativeBinary"] = forged_path
            self._write_json(manifest_path, manifest)

            reflection_path = package_dir / "reflection.json"
            reflection = json.loads(reflection_path.read_text(encoding="utf-8"))
            reflection["nativeBinary"] = forged_path
            self._write_json(reflection_path, reflection)

            with self._guard_crossgl_source_reads():
                plan = plan_metal_native_loader(package_dir)
                summary = plan.to_summary()

            self.assertFalse(plan.ready)
            self.assertIsNone(plan.native_artifact)
            self.assertEqual(summary["sourceInputs"], [])
            self.assertIsNone(summary["nativeArtifact"])
            reject = next(
                diagnostic
                for diagnostic in summary["rejectReasons"]
                if diagnostic["code"] == "package.artifact.source_input_leakage"
            )
            self.assertEqual(reject["document"], "manifest")
            self.assertEqual(reject["artifact"], "nativeBinary")
            self.assertEqual(reject["path"], forged_path)
            self.assertEqual(reject["expected"], "generated package artifact")
            self.assertEqual(reject["actual"], forged_path)
            self.assertEqual(
                list(package_dir.rglob("*.cgl")),
                [package_dir / forged_path],
            )

    def test_rejects_non_metallib_native_binary_descriptor_detail(self) -> None:
        with tempfile.TemporaryDirectory(suffix=".cglb") as temp_dir:
            package_dir = Path(temp_dir)
            native_path = "backend/metal/RuntimeMetalLoaderFixture.bin"
            self._write_source_free_metal_package(
                package_dir,
                descriptor_path=(
                    "backend/metal/RuntimeMetalLoaderFixture.native-artifact.json"
                ),
                native_path=native_path,
            )
            source_path = package_dir / "source" / "RuntimeMetalLoaderFixture.cgl"
            source_path.parent.mkdir()
            source_path.write_text(
                "non-metallib rejection must stay source-free\n",
                encoding="utf-8",
            )

            with self._guard_crossgl_source_reads():
                plan = plan_metal_native_loader(package_dir)
                summary = plan.to_summary()

            self.assertFalse(plan.ready)
            self.assertFalse(plan.source_parsing_required)
            self.assertFalse(plan.device_execution_required)
            self.assertIsNone(plan.native_artifact)
            self.assertEqual(summary["sourceInputs"], [])
            self.assertEqual(summary["compilerInvocationRequired"], False)
            self.assertEqual(summary["deviceExecutionRequired"], False)
            self.assertIsNone(summary["nativeArtifact"])
            reject_codes = [
                diagnostic["code"] for diagnostic in summary["rejectReasons"]
            ]
            self.assertIn(
                "metal_loader.native_artifact_metallib_path_mismatch",
                reject_codes,
            )
            self.assertIn(
                "metal_loader.native_artifact_descriptor_metallib_path_mismatch",
                reject_codes,
            )
            artifact_reject = next(
                diagnostic
                for diagnostic in summary["rejectReasons"]
                if diagnostic["code"]
                == "metal_loader.native_artifact_metallib_path_mismatch"
            )
            descriptor_reject = next(
                diagnostic
                for diagnostic in summary["rejectReasons"]
                if diagnostic["code"]
                == "metal_loader.native_artifact_descriptor_metallib_path_mismatch"
            )
            self.assertEqual(artifact_reject["document"], "manifest")
            self.assertEqual(artifact_reject["artifact"], "nativeBinary")
            self.assertEqual(artifact_reject["expected"], "*.metallib")
            self.assertEqual(artifact_reject["actual"], native_path)
            self.assertEqual(descriptor_reject["document"], "nativeArtifactDescriptor")
            self.assertEqual(descriptor_reject["path"], "artifactPath")
            self.assertEqual(descriptor_reject["expected"], "*.metallib")
            self.assertEqual(descriptor_reject["actual"], native_path)

            metal_admission = summary["metalNativeAdmission"]
            self.assertEqual(metal_admission["decision"], "rejected")
            metallib_admission = metal_admission["metallibArtifact"]
            self.assertEqual(metallib_admission["path"], native_path)
            self.assertEqual(metallib_admission["pathSuffix"], ".bin")
            self.assertFalse(metallib_admission["pathSuffixMatchesMetallib"])
            descriptor_admission = metal_admission["nativeArtifactDescriptor"]
            self.assertEqual(descriptor_admission["artifactPath"], native_path)
            self.assertTrue(descriptor_admission["artifactPathMatchesNativeArtifact"])
            self.assertFalse(descriptor_admission["artifactPathSuffixMatchesMetallib"])
            checks = {check["name"]: check for check in metal_admission["checks"]}
            self.assertFalse(checks["nativeBinaryPathSuffixMatchesMetallib"]["passed"])
            self.assertFalse(
                checks["nativeArtifactDescriptorArtifactPathSuffixMatchesMetallib"][
                    "passed"
                ]
            )
            self.assertFalse(metal_admission["requiredChecksPassed"])
            with self.assertRaisesRegex(PackageReadError, "metallib"):
                plan.require_ready()
            self.assertEqual(list(package_dir.rglob("*.cgl")), [source_path])

    def test_descriptor_artifact_path_mismatch_reports_metal_admission_detail(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory(suffix=".cglb") as temp_dir:
            package_dir = Path(temp_dir)
            descriptor_path = (
                "backend/metal/RuntimeMetalLoaderFixture.native-artifact.json"
            )
            self._write_source_free_metal_package(
                package_dir,
                descriptor_path=descriptor_path,
            )
            descriptor_file = package_dir / descriptor_path
            descriptor = json.loads(descriptor_file.read_text(encoding="utf-8"))
            descriptor["artifactPath"] = "backend/metal/Other.metallib"
            self._write_json(descriptor_file, descriptor)
            source_path = package_dir / "source" / "RuntimeMetalLoaderFixture.cgl"
            source_path.parent.mkdir()
            source_path.write_text(
                "descriptor path mismatch must stay source-free\n",
                encoding="utf-8",
            )

            with self._guard_crossgl_source_reads():
                plan = plan_metal_native_loader(package_dir)
                summary = plan.to_summary()

            self.assertFalse(plan.ready)
            self.assertFalse(plan.source_parsing_required)
            self.assertFalse(plan.device_execution_required)
            self.assertIsNone(plan.native_artifact)
            self.assertEqual(summary["sourceInputs"], [])
            self.assertEqual(summary["compilerInvocationRequired"], False)
            self.assertEqual(summary["deviceExecutionRequired"], False)
            reject_codes = [
                diagnostic["code"] for diagnostic in summary["rejectReasons"]
            ]
            self.assertIn(
                "package.native_artifact_descriptor.artifact_path_mismatch",
                reject_codes,
            )
            self.assertIn(
                "metal_loader.native_artifact_descriptor_artifact_path_mismatch",
                reject_codes,
            )
            metal_admission = summary["metalNativeAdmission"]
            self.assertEqual(metal_admission["decision"], "rejected")
            descriptor_admission = metal_admission["nativeArtifactDescriptor"]
            self.assertEqual(
                descriptor_admission["artifactPath"],
                "backend/metal/Other.metallib",
            )
            self.assertFalse(descriptor_admission["artifactPathMatchesNativeArtifact"])
            self.assertTrue(descriptor_admission["artifactPathSuffixMatchesMetallib"])
            mismatch_checks = {
                check["name"]: check for check in metal_admission["checks"]
            }
            self.assertFalse(
                mismatch_checks[
                    "nativeArtifactDescriptorArtifactPathMatchesNativeBinary"
                ]["passed"]
            )
            self.assertTrue(
                mismatch_checks[
                    "nativeArtifactDescriptorArtifactPathSuffixMatchesMetallib"
                ]["passed"]
            )
            self.assertFalse(metal_admission["requiredChecksPassed"])
            with self.assertRaisesRegex(PackageReadError, "artifactPath"):
                plan.require_ready()
            self.assertEqual(list(package_dir.rglob("*.cgl")), [source_path])

    def test_manifest_declared_missing_descriptor_rejects_native_plan(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory(suffix=".cglb") as temp_dir:
            package_dir = Path(temp_dir)
            self._write_valid_metal_package(package_dir)
            manifest_path = package_dir / "manifest.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["artifacts"]["nativeArtifactDescriptor"] = (
                "metadata/missing-native-artifact.json"
            )
            self._write_json(manifest_path, manifest)
            source_path = package_dir / "source" / "invalid.cgl"
            source_path.parent.mkdir()
            source_path.write_text(
                "missing descriptor rejection must not parse CrossGL source\n",
                encoding="utf-8",
            )

            with self._guard_crossgl_source_reads():
                plan = plan_metal_native_loader(package_dir)
                summary = plan.to_summary()

            self.assertFalse(plan.ready)
            self.assertIsNone(plan.native_artifact)
            self.assertEqual(summary["sourceInputs"], [])
            self.assertIn(
                "metal_loader.native_artifact_descriptor_missing",
                [diagnostic["code"] for diagnostic in summary["rejectReasons"]],
            )
            descriptor_summary = summary["nativeArtifactDescriptor"]
            self.assertIsNotNone(descriptor_summary)
            self.assertFalse(descriptor_summary["readable"])
            self.assertEqual(
                descriptor_summary["artifact"]["path"],
                "metadata/missing-native-artifact.json",
            )
            with self.assertRaisesRegex(PackageReadError, "nativeArtifactDescriptor"):
                plan.require_ready()
            self.assertEqual(list(package_dir.rglob("*.cgl")), [source_path])

    def test_rejects_stale_metallib_descriptor_without_source_or_work(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory(suffix=".cglb") as temp_dir:
            package_dir = Path(temp_dir)
            self._write_source_free_metal_package(
                package_dir,
                descriptor_path=(
                    "backend/metal/RuntimeMetalLoaderFixture.native-artifact.json"
                ),
            )
            (
                package_dir / "backend" / "metal" / "RuntimeMetalLoaderFixture.metallib"
            ).write_bytes(b"stale-metallib")
            source_path = package_dir / "source" / "RuntimeMetalLoaderFixture.cgl"
            source_path.parent.mkdir()
            source_path.write_text(
                "stale native binary recovery must not parse CrossGL source\n",
                encoding="utf-8",
            )

            with self._guard_crossgl_source_reads():
                with self._guard_compiler_processes():
                    plan = plan_metal_native_loader(package_dir)
                    summary = plan.to_summary()

            self.assertFalse(plan.ready)
            self.assertFalse(plan.source_parsing_required)
            self.assertFalse(plan.device_execution_required)
            self.assertIsNone(plan.native_artifact)
            self.assertEqual(summary["sourceInputs"], [])
            self.assertEqual(summary["compilerInvocationRequired"], False)
            self.assertEqual(summary["deviceExecutionRequired"], False)
            self.assertIsNone(summary["nativeArtifact"])
            self.assertEqual(
                summary["runtimePlan"]["metadataContract"]["sourceInputs"],
                [],
            )
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
            api_boundary = summary["metalNativeApiBoundary"]
            self.assertEqual(api_boundary["decision"], "rejected")
            self.assertFalse(api_boundary["metalFrameworkCallsPerformed"])
            self.assertFalse(api_boundary["metalDeviceCreationPerformed"])
            self.assertFalse(api_boundary["metalCommandExecutionPerformed"])
            self.assertTrue(api_boundary["descriptorFreshness"]["artifactHashDeclared"])
            self.assertFalse(
                api_boundary["descriptorFreshness"]["artifactHashMatchesMetallib"]
            )
            self.assertIn(
                "package.native_artifact_descriptor.artifact_hash_mismatch",
                api_boundary["descriptorFreshness"]["failClosedDiagnosticCodes"],
            )
            with self.assertRaisesRegex(PackageReadError, "artifact"):
                plan.require_ready()
            self.assertEqual(list(package_dir.rglob("*.cgl")), [source_path])

    def test_rejects_missing_metallib_descriptor_hash_without_source_or_work(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory(suffix=".cglb") as temp_dir:
            package_dir = Path(temp_dir)
            descriptor_path = (
                "backend/metal/RuntimeMetalLoaderFixture.native-artifact.json"
            )
            self._write_source_free_metal_package(
                package_dir,
                descriptor_path=descriptor_path,
            )
            descriptor_file = package_dir / descriptor_path
            descriptor = json.loads(descriptor_file.read_text(encoding="utf-8"))
            descriptor.pop("artifactHash")
            self._write_json(descriptor_file, descriptor)
            source_path = package_dir / "source" / "RuntimeMetalLoaderFixture.cgl"
            source_path.parent.mkdir()
            source_path.write_text(
                "missing native descriptor hash must not parse CrossGL source\n",
                encoding="utf-8",
            )

            with self._guard_crossgl_source_reads():
                with self._guard_compiler_processes():
                    plan = plan_metal_native_loader(package_dir)
                    summary = plan.to_summary()

            self.assertFalse(plan.ready)
            self.assertFalse(plan.source_parsing_required)
            self.assertFalse(plan.device_execution_required)
            self.assertIsNone(plan.native_artifact)
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

            api_boundary = summary["metalNativeApiBoundary"]
            self.assertEqual(api_boundary["decision"], "rejected")
            self.assertFalse(api_boundary["metalFrameworkCallsPerformed"])
            self.assertFalse(api_boundary["metalDeviceCreationPerformed"])
            self.assertFalse(api_boundary["metalCommandExecutionPerformed"])
            self.assertFalse(
                api_boundary["descriptorFreshness"]["artifactHashDeclared"]
            )
            self.assertFalse(
                api_boundary["descriptorFreshness"]["artifactHashMatchesMetallib"]
            )
            self.assertIn(
                "package.native_artifact_descriptor.artifact_hash_invalid",
                api_boundary["descriptorFreshness"]["failClosedDiagnosticCodes"],
            )
            descriptor_input = api_boundary["runtimeInputs"]["nativeArtifactDescriptor"]
            self.assertIsNone(descriptor_input["artifactHash"])
            self.assertFalse(descriptor_input["artifactHashMatchesMetallib"])
            checks = {
                check["name"]: check
                for check in summary["metalNativeAdmission"]["checks"]
            }
            self.assertFalse(
                checks["nativeArtifactDescriptorArtifactHashDeclared"]["passed"]
            )
            self.assertFalse(
                checks["nativeArtifactDescriptorArtifactHashMatchesMetallib"]["passed"]
            )
            self.assertFalse(summary["metalNativeAdmission"]["requiredChecksPassed"])
            with self.assertRaisesRegex(PackageReadError, "artifactHash"):
                plan.require_ready()
            self.assertEqual(list(package_dir.rglob("*.cgl")), [source_path])

    def test_rejects_missing_native_artifact_as_structured_source_free_result(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory(suffix=".cglb") as temp_dir:
            package_dir = Path(temp_dir)
            self._write_valid_metal_package(package_dir)
            (
                package_dir / "backend" / "metal" / "RuntimeMetalLoaderFixture.metallib"
            ).unlink()
            source_path = package_dir / "source" / "invalid.cgl"
            source_path.parent.mkdir()
            source_path.write_text(
                "fallback source parsing is not allowed\n",
                encoding="utf-8",
            )

            with self._guard_crossgl_source_reads():
                with self._guard_compiler_processes():
                    plan = plan_metal_native_loader(package_dir)
                    summary = plan.to_summary()

            self.assertFalse(plan.ready)
            self.assertFalse(plan.planned)
            self.assertFalse(plan.loadable)
            self.assertEqual(plan.status, "rejected")
            self.assertIsNone(plan.native_artifact)
            self.assertFalse(plan.source_parsing_required)
            self.assertEqual(summary["sourceInputs"], [])
            self.assertIsNone(summary["nativeArtifact"])
            self.assertEqual(
                [diagnostic["code"] for diagnostic in summary["rejectReasons"]],
                ["package.artifact.required_file_missing"],
            )
            self.assertEqual(
                summary["runtimePlan"]["sourceParsingRequired"],
                False,
            )
            with self.assertRaisesRegex(
                PackageReadError,
                "required artifact nativeBinary is declared but missing",
            ):
                plan.require_ready()
            self.assertEqual(list(package_dir.rglob("*.cgl")), [source_path])

    def test_rejects_source_package_without_selecting_backend_source(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory(suffix=".cglb") as temp_dir:
            package_dir = Path(temp_dir)
            self._write_valid_metal_package(package_dir, native_status="planned")
            (
                package_dir / "backend" / "metal" / "RuntimeMetalLoaderFixture.metallib"
            ).unlink()
            source_path = package_dir / "source" / "invalid.cgl"
            source_path.parent.mkdir()
            source_path.write_text(
                "native loader must not parse source-package fallback\n",
                encoding="utf-8",
            )

            with self._guard_crossgl_source_reads():
                plan = plan_metal_native_loader(package_dir)
                summary = plan.to_summary()

            self.assertFalse(plan.ready)
            self.assertFalse(plan.source_parsing_required)
            self.assertEqual(summary["sourceInputs"], [])
            self.assertIsNone(summary["nativeArtifact"])
            self.assertIsNone(
                summary["runtimePlan"]["runtimeArtifactSelection"]["artifact"]
            )
            self.assertIn(
                "package.native_binary_status.forbidden",
                [diagnostic["code"] for diagnostic in summary["rejectReasons"]],
            )
            self.assertNotEqual(
                summary["runtimePlan"]["runtimeArtifactPath"],
                "backend/metal/RuntimeMetalLoaderFixture.metal",
            )
            self.assertEqual(list(package_dir.rglob("*.cgl")), [source_path])

    def test_rejects_missing_metal_reflection_resources_structurally(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory(suffix=".cglb") as temp_dir:
            package_dir = Path(temp_dir)
            self._write_valid_metal_package(package_dir)
            reflection_path = package_dir / "reflection.json"
            reflection = json.loads(reflection_path.read_text(encoding="utf-8"))
            reflection["resources"] = []
            reflection["targetResourceBindings"] = []
            self._write_json(reflection_path, reflection)
            source_path = package_dir / "source" / "invalid.cgl"
            source_path.parent.mkdir()
            source_path.write_text(
                "reflection gaps must not trigger source parsing\n",
                encoding="utf-8",
            )

            with self._guard_crossgl_source_reads():
                plan = plan_metal_native_loader(package_dir)
                summary = plan.to_summary()

            self.assertFalse(plan.ready)
            self.assertIsNone(plan.native_artifact)
            self.assertEqual(summary["sourceInputs"], [])
            self.assertEqual(summary["reflection"]["entryPointCount"], 1)
            self.assertEqual(summary["reflection"]["resourceCount"], 0)
            self.assertEqual(summary["reflection"]["targetResourceBindingCount"], 0)
            self.assertEqual(
                [diagnostic["code"] for diagnostic in summary["rejectReasons"]],
                [
                    "metal_loader.reflection.resources_missing",
                    "metal_loader.reflection.target_bindings_missing",
                ],
            )
            self.assertEqual(list(package_dir.rglob("*.cgl")), [source_path])

    def test_rejects_incompatible_target_without_source_parse(self) -> None:
        with tempfile.TemporaryDirectory(suffix=".cglb") as temp_dir:
            package_dir = Path(temp_dir)
            self._write_valid_metal_package(package_dir, target="directx")
            source_path = package_dir / "source" / "invalid.cgl"
            source_path.parent.mkdir()
            source_path.write_text(
                "target mismatch must stay metadata-only\n",
                encoding="utf-8",
            )

            with self._guard_crossgl_source_reads():
                plan = plan_metal_native_loader(package_dir)
                summary = plan.to_summary()

            self.assertFalse(plan.ready)
            self.assertFalse(plan.source_parsing_required)
            self.assertEqual(summary["sourceInputs"], [])
            self.assertIsNone(summary["nativeArtifact"])
            self.assertIn(
                "package.target.loader_mismatch",
                [diagnostic["code"] for diagnostic in summary["rejectReasons"]],
            )
            self.assertEqual(list(package_dir.rglob("*.cgl")), [source_path])

    def _write_valid_metal_package(
        self,
        package_dir: Path,
        *,
        target: str = "metal",
        native_status: str | None = None,
    ) -> None:
        backend_dir = package_dir / "backend" / target
        backend_dir.mkdir(parents=True)
        source_extension = "metal" if target == "metal" else "hlsl"
        binary_extension = "metallib" if target == "metal" else "dxil"
        source_path = f"backend/{target}/RuntimeMetalLoaderFixture.{source_extension}"
        binary_path = f"backend/{target}/RuntimeMetalLoaderFixture.{binary_extension}"

        (backend_dir / f"RuntimeMetalLoaderFixture.{source_extension}").write_text(
            f"// generated {target} source\n",
            encoding="utf-8",
        )
        (backend_dir / f"RuntimeMetalLoaderFixture.{binary_extension}").write_bytes(
            b"native"
        )
        artifacts: dict[str, object] = {
            "backendSource": source_path,
            "nativeBinary": binary_path,
        }
        if target == "metal":
            (backend_dir / "RuntimeMetalLoaderFixture.air").write_bytes(b"air")
            artifacts["intermediate"] = "backend/metal/RuntimeMetalLoaderFixture.air"
        if native_status is not None:
            artifacts["nativeBinaryStatus"] = native_status

        self._write_json(
            package_dir / "manifest.json",
            {
                "schemaVersion": 1,
                "compiler": {
                    "name": "CrossGL-Compiler",
                    "version": "test",
                    "llvmVersion": "not-found",
                },
                "module": "RuntimeMetalLoaderFixture",
                "target": target,
                "sourceHash": {
                    "algorithm": "sha256",
                    "value": "0" * 64,
                },
                "artifacts": artifacts,
            },
        )
        self._write_json(
            package_dir / "reflection.json",
            {
                "schemaVersion": 1,
                "module": "RuntimeMetalLoaderFixture",
                "target": target,
                "nativeBinary": binary_path,
                "entryPoints": [
                    {
                        "stage": "compute",
                        "sourceName": "main",
                        "backendName": "runtime_metal_loader_main",
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
                        "target": target,
                        "stage": "compute",
                        "entryPoint": "runtime_metal_loader_main",
                        "name": "OutputBuffer",
                        "kind": "storageBuffer",
                        "sourceType": "float4",
                        "addressSpace": "device",
                        "abi": {"buffer": 0},
                        "bindingClass": "buffer",
                        "descriptorType": "buffer",
                    }
                ],
                "targetFeatures": [
                    {
                        "target": target,
                        "kind": "package",
                        "name": "fixture",
                    }
                ],
            },
        )
        self._write_json(
            package_dir / "diagnostics.json",
            {
                "schemaVersion": 1,
                "diagnostics": [],
            },
        )

    def _write_source_free_metal_package(
        self,
        package_dir: Path,
        *,
        descriptor_path: str,
        descriptor_binary_kind: str = "metal.metallib",
        native_path: str = "backend/metal/RuntimeMetalLoaderFixture.metallib",
        native_bytes: bytes = b"metallib",
    ) -> None:
        backend_dir = package_dir / "backend" / "metal"
        backend_dir.mkdir(parents=True)
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
                "module": "RuntimeMetalLoaderFixture",
                "target": "metal",
                "sourceHash": {
                    "algorithm": "sha256",
                    "value": "0" * 64,
                },
                "packageArtifactRequirements": {
                    "target": "metal",
                    "packageMode": "native",
                    "requiredPathArtifacts": ["nativeBinary"],
                    "requiresNativeBinaryStatus": False,
                    "allowsPlannedNativeBinary": False,
                    "allowsPlannedNativeSourceEvidence": False,
                },
                "artifacts": {
                    "nativeBinary": native_path,
                    "nativeArtifactDescriptor": descriptor_path,
                },
            },
        )
        self._write_json(
            package_dir / "reflection.json",
            {
                "schemaVersion": 1,
                "module": "RuntimeMetalLoaderFixture",
                "target": "metal",
                "nativeBinary": native_path,
                "entryPoints": [
                    {
                        "stage": "compute",
                        "sourceName": "main",
                        "backendName": "runtime_metal_loader_main",
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
                        "target": "metal",
                        "stage": "compute",
                        "entryPoint": "runtime_metal_loader_main",
                        "name": "OutputBuffer",
                        "kind": "storageBuffer",
                        "sourceType": "float4",
                        "addressSpace": "device",
                        "abi": {"buffer": 0},
                        "bindingClass": "buffer",
                        "descriptorType": "buffer",
                    }
                ],
                "targetFeatures": [
                    {
                        "target": "metal",
                        "kind": "package",
                        "name": "fixture",
                    }
                ],
            },
        )
        self._write_json(
            package_dir / "diagnostics.json",
            {
                "schemaVersion": 1,
                "diagnostics": [],
            },
        )
        self._write_native_artifact_descriptor(
            package_dir,
            descriptor_path=descriptor_path,
            binary_kind=descriptor_binary_kind,
            source_path="source/RuntimeMetalLoaderFixture.cgl",
            source_bytes=b"CrossGL source bytes intentionally not read by loader",
            artifact_path=native_path,
            artifact_bytes=native_bytes,
        )

    def _write_native_artifact_descriptor(
        self,
        package_dir: Path,
        *,
        descriptor_path: str,
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
                "target": "metal",
                "binaryKind": binary_kind,
                "sourcePath": source_path,
                "sourceHash": self._sha256(source_bytes),
                "artifactPath": artifact_path,
                "artifactHash": self._sha256(artifact_bytes),
                "sizeBytes": len(artifact_bytes),
                "toolchainProvenance": {
                    "producer": "tests.runtime.test_metal_loader",
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

        def _assert_allowed_path(path: Path, action: str) -> None:
            if path.resolve() in forbidden_resolved_paths:
                raise AssertionError(f"loader read stale descriptor path: {path}")
            if path.suffix == ".cgl":
                raise AssertionError(f"loader {action} source file: {path}")

        def guarded_read_text(path: Path, *args: object, **kwargs: object) -> str:
            _assert_allowed_path(path, "read")
            return original_read_text(path, *args, **kwargs)

        def guarded_read_bytes(path: Path, *args: object, **kwargs: object) -> bytes:
            _assert_allowed_path(path, "read")
            return original_read_bytes(path, *args, **kwargs)

        def guarded_open(path: Path, *args: object, **kwargs: object) -> object:
            _assert_allowed_path(path, "opened")
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

    def _guard_compiler_processes(self) -> object:
        def forbidden_process_call(*args: object, **kwargs: object) -> object:
            raise AssertionError(
                "Metal native loader invoked compiler/device process work"
            )

        return mock.patch.multiple(
            "subprocess",
            Popen=forbidden_process_call,
            check_call=forbidden_process_call,
            check_output=forbidden_process_call,
            run=forbidden_process_call,
        )


if __name__ == "__main__":
    unittest.main()
