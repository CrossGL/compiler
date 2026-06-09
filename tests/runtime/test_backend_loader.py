#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock


REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))


from runtime.backend_loader import plan_source_free_native_backend_loader  # noqa: E402
from runtime.package_reader import PackageReadError  # noqa: E402


class SourceFreeNativeBackendLoaderAdmissionTests(unittest.TestCase):
    def test_summary_accepts_native_artifact_descriptor_at_top_level(self) -> None:
        with tempfile.TemporaryDirectory(suffix=".cglb") as temp_dir:
            package_dir = Path(temp_dir)
            self._write_source_free_metal_package(package_dir)
            source_path = package_dir / "source" / "RuntimeBackendLoaderFixture.cgl"
            source_path.parent.mkdir()
            source_path.write_text(
                "backend native loader admission must not parse source\n",
                encoding="utf-8",
            )

            with self._guard_source_reads():
                plan = plan_source_free_native_backend_loader(
                    package_dir,
                    "metal",
                    loader_name="metal-native",
                )
                summary = plan.to_summary()

            admission = summary["nativeAdmission"]
            artifact = admission["nativeArtifact"]
            descriptor = admission["nativeArtifactDescriptor"]

            self.assertTrue(plan.ready, summary["diagnostics"])
            self.assertEqual(summary["deviceExecutionRequired"], False)
            self.assertEqual(
                summary["targetLegalizationEvidence"],
                summary["runtimePlan"]["targetLegalizationEvidence"],
            )
            self.assertEqual(
                summary["targetLegalizationToolRequirements"],
                summary["runtimePlan"]["targetLegalizationToolRequirements"],
            )
            self.assertEqual(
                summary["packageArtifactRequirementsSource"],
                summary["runtimePlan"]["packageArtifactRequirementsSource"],
            )
            self.assertEqual(
                summary["packageArtifactRequirements"],
                summary["runtimePlan"]["packageArtifactRequirements"],
            )
            self.assertEqual(admission["decision"], "accepted")
            self.assertEqual(
                admission["reason"], "runtime.native_backend_loader.accepted"
            )
            self.assertEqual(admission["deviceExecutionRequired"], False)
            self.assertEqual(
                admission["packageArtifactRequirementsSource"],
                summary["packageArtifactRequirementsSource"],
            )
            self.assertEqual(
                admission["packageArtifactRequirements"],
                summary["packageArtifactRequirements"],
            )
            self.assertEqual(
                admission["targetLegalizationEvidence"],
                summary["targetLegalizationEvidence"],
            )
            self.assertEqual(
                admission["targetLegalizationToolRequirements"],
                summary["targetLegalizationToolRequirements"],
            )
            self.assertEqual(artifact["decision"], "accepted")
            self.assertEqual(artifact["status"], "accepted-native-artifact")
            self.assertEqual(artifact["reason"], "runtime.native_artifact.accepted")
            self.assertTrue(artifact["available"])
            self.assertNotIn(
                "metal_loader.reflection.resource_target_binding_missing",
                [diagnostic["code"] for diagnostic in summary["diagnostics"]],
            )
            self.assertNotIn(
                "metal_loader.reflection.target_binding_source_missing",
                [diagnostic["code"] for diagnostic in summary["diagnostics"]],
            )
            self.assertEqual(
                artifact["path"],
                "backend/metal/RuntimeBackendLoaderFixture.metallib",
            )
            self.assertEqual(descriptor["decision"], "accepted")
            self.assertEqual(
                descriptor["status"],
                "accepted-native-artifact-descriptor",
            )
            self.assertTrue(descriptor["compatible"])
            self.assertEqual(descriptor["binaryKind"], "metal.metallib")
            self.assertEqual(descriptor["expectedBinaryKinds"], ["metal.metallib"])
            self.assertTrue(descriptor["binaryKindMatchesLoader"])
            self.assertTrue(descriptor["sourcePathDeclared"])
            self.assertNotIn("sourcePath", descriptor["fields"])
            self.assertTrue(summary["nativeArtifactDescriptor"]["sourcePathDeclared"])
            self.assertNotIn(
                "sourcePath",
                summary["nativeArtifactDescriptor"]["fields"],
            )
            self.assertEqual(list(package_dir.rglob("*.cgl")), [source_path])

    def test_summary_exposes_graphics_abi_descriptor_bindings(self) -> None:
        with tempfile.TemporaryDirectory(suffix=".cglb") as temp_dir:
            package_dir = Path(temp_dir)
            self._write_source_free_metal_package(package_dir)
            self._write_graphics_abi_sidecar(package_dir)
            source_path = package_dir / "source" / "RuntimeBackendLoaderFixture.cgl"
            source_path.parent.mkdir()
            source_path.write_text(
                "backend loader must not parse source for graphics ABI bindings\n",
                encoding="utf-8",
            )

            with self._guard_source_reads():
                plan = plan_source_free_native_backend_loader(
                    package_dir,
                    "metal",
                    loader_name="metal-native",
                )
                summary = plan.to_summary()

            bindings = summary["graphicsDescriptorBindings"]
            binding = bindings["bindings"][0]

            self.assertTrue(plan.ready, summary["diagnostics"])
            self.assertEqual(bindings["source"], "graphicsAbi.abiRecords")
            self.assertEqual(bindings["bindingCount"], 1)
            self.assertEqual(binding["target"], "metal")
            self.assertEqual(binding["entryPoint"], "runtime_backend_loader_main")
            self.assertEqual(binding["name"], "OutputBuffer")
            self.assertEqual(binding["abi"], "kernelArgument")
            self.assertEqual(binding["bindingClass"], "buffer")
            self.assertEqual(binding["argumentIndex"], 0)
            self.assertEqual(binding["set"], 0)
            self.assertEqual(binding["binding"], 0)
            self.assertEqual(list(package_dir.rglob("*.cgl")), [source_path])

    def test_summary_rejects_resource_without_selected_target_binding(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory(suffix=".cglb") as temp_dir:
            package_dir = Path(temp_dir)
            self._write_source_free_metal_package(package_dir)
            reflection_path = package_dir / "reflection.json"
            reflection = json.loads(reflection_path.read_text(encoding="utf-8"))
            reflection["resources"].append(
                {
                    "stage": "compute",
                    "name": "InputBuffer",
                    "kind": "storageBuffer",
                    "type": "float4",
                    "set": 0,
                    "binding": 1,
                }
            )
            self._write_json(reflection_path, reflection)
            source_path = package_dir / "source" / "RuntimeBackendLoaderFixture.cgl"
            source_path.parent.mkdir()
            source_path.write_text(
                "reflection drift must not trigger source parsing\n",
                encoding="utf-8",
            )

            with self._guard_source_reads():
                plan = plan_source_free_native_backend_loader(
                    package_dir,
                    "metal",
                    loader_name="metal-native",
                )
                summary = plan.to_summary()

            reject_diagnostics = {
                diagnostic["code"]: diagnostic
                for diagnostic in summary["rejectReasons"]
            }
            diagnostic = reject_diagnostics[
                "metal_loader.reflection.resource_target_binding_missing"
            ]

            self.assertFalse(plan.ready)
            self.assertIsNone(plan.native_artifact)
            self.assertEqual(summary["sourceInputs"], [])
            self.assertEqual(summary["nativeAdmission"]["decision"], "rejected")
            self.assertEqual(
                summary["nativeAdmission"]["reason"],
                "metal_loader.reflection.resource_target_binding_missing",
            )
            self.assertEqual(summary["reflection"]["resourceCount"], 2)
            self.assertEqual(summary["reflection"]["targetResourceBindingCount"], 1)
            self.assertEqual(diagnostic["document"], "reflection")
            self.assertEqual(diagnostic["path"], "targetResourceBindings")
            self.assertEqual(
                diagnostic["expected"],
                {
                    "target": "metal",
                    "stage": "compute",
                    "name": "InputBuffer",
                    "kind": "storageBuffer",
                },
            )
            self.assertEqual(diagnostic["actual"], "missing")
            with self.assertRaisesRegex(PackageReadError, "selected-target"):
                plan.require_ready()
            self.assertEqual(list(package_dir.rglob("*.cgl")), [source_path])

    def test_summary_rejects_selected_target_binding_without_resource(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory(suffix=".cglb") as temp_dir:
            package_dir = Path(temp_dir)
            self._write_source_free_metal_package(package_dir)
            reflection_path = package_dir / "reflection.json"
            reflection = json.loads(reflection_path.read_text(encoding="utf-8"))
            stale_binding = dict(reflection["targetResourceBindings"][0])
            stale_binding["name"] = "StaleBuffer"
            stale_binding["abi"] = {"buffer": 1}
            reflection["targetResourceBindings"].append(stale_binding)
            self._write_json(reflection_path, reflection)
            source_path = package_dir / "source" / "RuntimeBackendLoaderFixture.cgl"
            source_path.parent.mkdir()
            source_path.write_text(
                "stale target binding must not trigger source parsing\n",
                encoding="utf-8",
            )

            with self._guard_source_reads():
                plan = plan_source_free_native_backend_loader(
                    package_dir,
                    "metal",
                    loader_name="metal-native",
                )
                summary = plan.to_summary()

            reject_diagnostics = {
                diagnostic["code"]: diagnostic
                for diagnostic in summary["rejectReasons"]
            }
            diagnostic = reject_diagnostics[
                "metal_loader.reflection.target_binding_source_missing"
            ]

            self.assertFalse(plan.ready)
            self.assertIsNone(plan.native_artifact)
            self.assertEqual(summary["sourceInputs"], [])
            self.assertEqual(summary["nativeAdmission"]["decision"], "rejected")
            self.assertEqual(
                summary["nativeAdmission"]["reason"],
                "metal_loader.reflection.target_binding_source_missing",
            )
            self.assertEqual(summary["reflection"]["resourceCount"], 1)
            self.assertEqual(summary["reflection"]["targetResourceBindingCount"], 2)
            self.assertEqual(diagnostic["document"], "reflection")
            self.assertEqual(diagnostic["path"], "resources")
            self.assertEqual(
                diagnostic["expected"],
                {
                    "stage": "compute",
                    "name": "StaleBuffer",
                    "kind": "storageBuffer",
                },
            )
            self.assertEqual(diagnostic["actual"], "missing")
            with self.assertRaisesRegex(PackageReadError, "source resource"):
                plan.require_ready()
            self.assertEqual(list(package_dir.rglob("*.cgl")), [source_path])

    def test_summary_distinguishes_missing_native_artifact(self) -> None:
        with tempfile.TemporaryDirectory(suffix=".cglb") as temp_dir:
            package_dir = Path(temp_dir)
            self._write_source_free_metal_package(
                package_dir,
                write_native_binary=False,
            )
            source_path = package_dir / "source" / "RuntimeBackendLoaderFixture.cgl"
            source_path.parent.mkdir()
            source_path.write_text(
                "missing native artifact must not trigger source fallback\n",
                encoding="utf-8",
            )

            with self._guard_source_reads():
                plan = plan_source_free_native_backend_loader(
                    package_dir,
                    "metal",
                    loader_name="metal-native",
                )
                summary = plan.to_summary()

            admission = summary["nativeAdmission"]
            artifact = admission["nativeArtifact"]

            self.assertFalse(plan.ready)
            self.assertEqual(summary["sourceParsingRequired"], False)
            self.assertEqual(summary["deviceExecutionRequired"], False)
            self.assertEqual(admission["decision"], "rejected")
            self.assertEqual(artifact["decision"], "rejected")
            self.assertEqual(artifact["status"], "missing-native-artifact")
            self.assertEqual(
                artifact["reason"], "package.artifact.required_file_missing"
            )
            self.assertFalse(artifact["available"])
            self.assertIsNone(summary["nativeArtifact"])
            self.assertEqual(list(package_dir.rglob("*.cgl")), [source_path])

    def test_summary_rejects_native_artifact_declared_under_other_backend(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory(suffix=".cglb") as temp_dir:
            package_dir = Path(temp_dir)
            self._write_source_free_metal_package(package_dir)

            manifest_path = package_dir / "manifest.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            native_path = manifest["artifacts"]["nativeBinary"]
            moved_native_path = native_path.replace(
                "backend/metal/", "backend/directx/"
            )
            moved_native_file = package_dir / moved_native_path
            moved_native_file.parent.mkdir(parents=True, exist_ok=True)
            (package_dir / native_path).rename(moved_native_file)
            manifest["artifacts"]["nativeBinary"] = moved_native_path
            self._write_json(manifest_path, manifest)

            reflection_path = package_dir / "reflection.json"
            reflection = json.loads(reflection_path.read_text(encoding="utf-8"))
            reflection["nativeBinary"] = moved_native_path
            self._write_json(reflection_path, reflection)

            descriptor_path = package_dir / "metadata" / "native-artifact.json"
            descriptor = json.loads(descriptor_path.read_text(encoding="utf-8"))
            descriptor["artifactPath"] = moved_native_path
            self._write_json(descriptor_path, descriptor)

            source_path = package_dir / "source" / "RuntimeBackendLoaderFixture.cgl"
            source_path.parent.mkdir()
            source_path.write_text(
                "backend mismatch must not trigger source fallback\n",
                encoding="utf-8",
            )

            with self._guard_source_reads():
                plan = plan_source_free_native_backend_loader(
                    package_dir,
                    "metal",
                    loader_name="metal-native",
                )
                summary = plan.to_summary()

            mismatch_code = "package.artifact.backend_target_mismatch"
            diagnostic = next(
                diagnostic
                for diagnostic in summary["rejectReasons"]
                if diagnostic["code"] == mismatch_code
            )

            self.assertFalse(plan.ready)
            self.assertFalse(summary["sourceParsingRequired"])
            self.assertFalse(summary["deviceExecutionRequired"])
            self.assertIsNone(plan.native_artifact)
            self.assertIsNone(summary["nativeArtifact"])
            self.assertEqual(summary["nativeAdmission"]["reason"], mismatch_code)
            self.assertEqual(
                summary["nativeAdmission"]["nativeArtifact"]["reason"],
                mismatch_code,
            )
            self.assertEqual(
                summary["runtimePlan"]["runtimeArtifactSelection"]["admission"][
                    "native"
                ]["reason"],
                mismatch_code,
            )
            self.assertEqual(diagnostic["artifact"], "nativeBinary")
            self.assertEqual(diagnostic["path"], moved_native_path)
            self.assertEqual(diagnostic["expected"], "backend/metal/")
            self.assertEqual(diagnostic["actual"], "backend/directx/")
            with self.assertRaisesRegex(PackageReadError, "backend/directx"):
                plan.require_ready()
            self.assertEqual(list(package_dir.rglob("*.cgl")), [source_path])

    def test_summary_rejects_malformed_recorded_requirements_without_source_parse(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory(suffix=".cglb") as temp_dir:
            package_dir = Path(temp_dir)
            self._write_source_free_metal_package(package_dir)
            manifest_path = package_dir / "manifest.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["packageArtifactRequirements"] = "native"
            self._write_json(manifest_path, manifest)
            source_path = package_dir / "source" / "RuntimeBackendLoaderFixture.cgl"
            source_path.parent.mkdir()
            source_path.write_text(
                "malformed requirements must not trigger source parsing\n",
                encoding="utf-8",
            )

            with self._guard_source_reads():
                plan = plan_source_free_native_backend_loader(
                    package_dir,
                    "metal",
                    loader_name="metal-native",
                )
                summary = plan.to_summary()

            reject_codes = [diagnostic.code for diagnostic in plan.reject_reasons]

            self.assertFalse(plan.ready)
            self.assertIsNone(plan.native_artifact)
            self.assertFalse(summary["sourceParsingRequired"])
            self.assertIn("package.artifact_requirements.invalid", reject_codes)
            self.assertIsNone(
                summary["runtimePlan"]["compatibilityReport"][
                    "packageArtifactRequirements"
                ]
            )
            self.assertEqual(
                summary["runtimePlan"]["compatibilityReport"]["admission"][
                    "requirements"
                ]["requirementsSource"],
                "manifest",
            )
            self.assertEqual(list(package_dir.rglob("*.cgl")), [source_path])

    def test_summary_rejects_null_recorded_requirements_without_legacy_fallback(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory(suffix=".cglb") as temp_dir:
            package_dir = Path(temp_dir)
            self._write_source_free_metal_package(package_dir)
            manifest_path = package_dir / "manifest.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["packageArtifactRequirements"] = None
            self._write_json(manifest_path, manifest)
            source_path = package_dir / "source" / "RuntimeBackendLoaderFixture.cgl"
            source_path.parent.mkdir()
            source_path.write_text(
                "null requirements must not trigger source parsing\n",
                encoding="utf-8",
            )

            with self._guard_source_reads():
                plan = plan_source_free_native_backend_loader(
                    package_dir,
                    "metal",
                    loader_name="metal-native",
                )
                summary = plan.to_summary()

            reject_codes = [diagnostic.code for diagnostic in plan.reject_reasons]
            compatibility_report = summary["runtimePlan"]["compatibilityReport"]
            requirement_summary = compatibility_report["admission"]["requirements"]

            self.assertFalse(plan.ready)
            self.assertIsNone(plan.native_artifact)
            self.assertFalse(summary["sourceParsingRequired"])
            self.assertIn("package.artifact_requirements.invalid", reject_codes)
            self.assertIsNone(
                summary["runtimePlan"]["metadataContract"]["contractSource"]
            )
            self.assertIsNone(summary["packageArtifactRequirementsSource"])
            self.assertEqual(
                summary["packageArtifactRequirements"],
                summary["runtimePlan"]["packageArtifactRequirements"],
            )
            self.assertIsNone(
                summary["nativeAdmission"]["packageArtifactRequirementsSource"]
            )
            self.assertEqual(
                summary["nativeAdmission"]["packageArtifactRequirements"],
                summary["packageArtifactRequirements"],
            )
            self.assertEqual(
                summary["runtimePlan"]["metadataContract"]["sourceInputs"], []
            )
            self.assertIsNone(compatibility_report["packageArtifactRequirements"])
            self.assertTrue(requirement_summary["declared"])
            self.assertFalse(requirement_summary["legacyInferred"])
            self.assertEqual(requirement_summary["requirementsSource"], "manifest")
            self.assertFalse(requirement_summary["resolved"])
            self.assertFalse(requirement_summary["valid"])
            self.assertEqual(list(package_dir.rglob("*.cgl")), [source_path])

    def test_summary_rejects_recorded_native_contract_without_descriptor_metadata(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory(suffix=".cglb") as temp_dir:
            package_dir = Path(temp_dir)
            self._write_source_free_metal_package(
                package_dir,
                include_descriptor=False,
            )
            backend_source = "backend/metal/RuntimeBackendLoaderFixture.metal"
            intermediate = "backend/metal/RuntimeBackendLoaderFixture.air"
            (package_dir / backend_source).write_text(
                "// generated Metal source\n",
                encoding="utf-8",
            )
            (package_dir / intermediate).write_bytes(b"air")
            manifest_path = package_dir / "manifest.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["artifacts"]["backendSource"] = backend_source
            manifest["artifacts"]["intermediate"] = intermediate
            manifest["packageArtifactRequirements"]["requiredPathArtifacts"] = [
                "backendSource",
                "intermediate",
                "nativeBinary",
            ]
            self._write_json(manifest_path, manifest)
            source_path = package_dir / "source" / "RuntimeBackendLoaderFixture.cgl"
            source_path.parent.mkdir()
            source_path.write_text(
                "descriptor admission must not trigger source parsing\n",
                encoding="utf-8",
            )

            with self._guard_source_reads():
                plan = plan_source_free_native_backend_loader(
                    package_dir,
                    "metal",
                    loader_name="metal-native",
                )
                summary = plan.to_summary()

            diagnostic_code = "metal_loader.native_artifact_descriptor_not_declared"
            reject_codes = [diagnostic.code for diagnostic in plan.reject_reasons]
            descriptor_admission = summary["nativeAdmission"][
                "nativeArtifactDescriptor"
            ]
            descriptor_diagnostic = next(
                diagnostic
                for diagnostic in summary["rejectReasons"]
                if diagnostic["code"] == diagnostic_code
            )

            self.assertFalse(plan.ready)
            self.assertIsNone(plan.native_artifact)
            self.assertEqual(summary["sourceInputs"], [])
            self.assertEqual(summary["nativeAdmission"]["decision"], "rejected")
            self.assertEqual(summary["nativeAdmission"]["reason"], diagnostic_code)
            self.assertIn(diagnostic_code, reject_codes)
            self.assertEqual(
                descriptor_admission["decision"],
                "missing",
            )
            self.assertEqual(
                descriptor_admission["status"],
                "descriptor-not-declared",
            )
            self.assertEqual(
                descriptor_admission["reason"],
                "runtime.native_artifact_descriptor.not_declared",
            )
            self.assertEqual(
                descriptor_admission["diagnostics"][0]["code"],
                diagnostic_code,
            )
            self.assertEqual(descriptor_diagnostic["document"], "manifest")
            self.assertEqual(
                descriptor_diagnostic["artifact"],
                "nativeArtifactDescriptor",
            )
            self.assertEqual(
                descriptor_diagnostic["path"],
                "artifacts.nativeArtifactDescriptor",
            )
            with self.assertRaisesRegex(PackageReadError, "nativeArtifactDescriptor"):
                plan.require_ready()
            self.assertEqual(list(package_dir.rglob("*.cgl")), [source_path])

    def test_summary_rejects_planned_source_package_native_metadata(self) -> None:
        with tempfile.TemporaryDirectory(suffix=".cglb") as temp_dir:
            package_dir = Path(temp_dir)
            self._write_planned_directx_source_package(package_dir)
            source_path = package_dir / "source" / "RuntimeBackendLoaderFixture.cgl"
            source_path.parent.mkdir()
            source_path.write_text(
                "planned native metadata must not trigger source parsing\n",
                encoding="utf-8",
            )

            with self._guard_source_reads():
                plan = plan_source_free_native_backend_loader(
                    package_dir,
                    "directx",
                    loader_name="directx-native",
                )
                summary = plan.to_summary()

            admission = summary["nativeAdmission"]
            artifact = admission["nativeArtifact"]
            runtime_native = admission["runtimeSelection"]["native"]
            source_fallback = admission["runtimeSelection"]["sourcePackageFallback"]

            self.assertFalse(plan.ready)
            self.assertEqual(summary["sourceParsingRequired"], False)
            self.assertEqual(summary["deviceExecutionRequired"], False)
            self.assertEqual(admission["decision"], "rejected")
            self.assertEqual(artifact["decision"], "rejected")
            self.assertEqual(artifact["status"], "planned-native-metadata")
            self.assertEqual(artifact["nativeBinaryStatus"], "planned")
            self.assertEqual(
                artifact["reason"], "package.native_binary_status.not_ready"
            )
            self.assertFalse(artifact["available"])
            self.assertEqual(runtime_native["category"], "native-planned-only")
            self.assertEqual(
                runtime_native["reason"],
                "runtime.native_artifact.source_package_fallback",
            )
            self.assertTrue(source_fallback["fallbackAllowed"])
            self.assertFalse(source_fallback["fallbackAttempted"])
            self.assertIsNone(summary["nativeArtifact"])
            self.assertEqual(list(package_dir.rglob("*.cgl")), [source_path])

    def _write_source_free_metal_package(
        self,
        package_dir: Path,
        *,
        write_native_binary: bool = True,
        include_descriptor: bool = True,
    ) -> None:
        native_path = "backend/metal/RuntimeBackendLoaderFixture.metallib"
        native_bytes = b"metallib"
        if write_native_binary:
            native_file = package_dir / native_path
            native_file.parent.mkdir(parents=True)
            native_file.write_bytes(native_bytes)

        artifacts: dict[str, object] = {"nativeBinary": native_path}
        if include_descriptor:
            artifacts["nativeArtifactDescriptor"] = "metadata/native-artifact.json"

        self._write_json(
            package_dir / "manifest.json",
            {
                "schemaVersion": 1,
                "compiler": {
                    "name": "CrossGL-Compiler",
                    "version": "test",
                    "llvmVersion": "not-found",
                },
                "module": "RuntimeBackendLoaderFixture",
                "target": "metal",
                "sourceHash": {"algorithm": "sha256", "value": "0" * 64},
                "packageArtifactRequirements": {
                    "target": "metal",
                    "packageMode": "native",
                    "requiredPathArtifacts": ["nativeBinary"],
                    "requiresNativeBinaryStatus": False,
                    "allowsPlannedNativeBinary": False,
                    "allowsPlannedNativeSourceEvidence": False,
                },
                "artifacts": artifacts,
            },
        )
        self._write_reflection(
            package_dir,
            target="metal",
            native_path=native_path,
            descriptor_type="buffer",
            abi={"buffer": 0},
        )
        self._write_json(
            package_dir / "diagnostics.json",
            {"schemaVersion": 1, "diagnostics": []},
        )
        if include_descriptor:
            self._write_native_artifact_descriptor(
                package_dir,
                descriptor_path="metadata/native-artifact.json",
                target="metal",
                binary_kind="metal.metallib",
                artifact_path=native_path,
                artifact_bytes=native_bytes,
            )

    def _write_graphics_abi_sidecar(self, package_dir: Path) -> None:
        manifest_path = package_dir / "manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        graphics_abi_path = (
            "backend/metal/RuntimeBackendLoaderFixture.graphics-abi.json"
        )
        self._write_json(
            package_dir / graphics_abi_path,
            {
                "schemaVersion": 1,
                "module": "RuntimeBackendLoaderFixture",
                "target": "metal",
                "entryPoints": [
                    {
                        "stage": "compute",
                        "sourceName": "main",
                        "backendName": "runtime_backend_loader_main",
                    }
                ],
                "vertexInputs": [],
                "varyings": [],
                "fragmentOutputs": [],
                "builtins": [],
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
                "abiRecords": [
                    {
                        "target": "metal",
                        "stage": "compute",
                        "entryPoint": "runtime_backend_loader_main",
                        "name": "OutputBuffer",
                        "kind": "storageBuffer",
                        "sourceType": "float4",
                        "addressSpace": "device",
                        "abi": "kernelArgument",
                        "bindingClass": "buffer",
                        "metalType": "device float4*",
                        "argumentIndex": 0,
                        "set": 0,
                        "binding": 0,
                    }
                ],
            },
        )
        manifest["artifacts"]["graphicsAbi"] = graphics_abi_path
        self._write_json(manifest_path, manifest)

    def _write_planned_directx_source_package(self, package_dir: Path) -> None:
        backend_source = "backend/directx/RuntimeBackendLoaderFixture.hlsl"
        native_path = "backend/directx/RuntimeBackendLoaderFixture.dxil"
        source_file = package_dir / backend_source
        source_file.parent.mkdir(parents=True)
        source_file.write_text("// generated DirectX source\n", encoding="utf-8")

        self._write_json(
            package_dir / "manifest.json",
            {
                "schemaVersion": 1,
                "compiler": {
                    "name": "CrossGL-Compiler",
                    "version": "test",
                    "llvmVersion": "not-found",
                },
                "module": "RuntimeBackendLoaderFixture",
                "target": "directx",
                "sourceHash": {"algorithm": "sha256", "value": "0" * 64},
                "artifacts": {
                    "backendSource": backend_source,
                    "nativeBinary": native_path,
                    "nativeBinaryStatus": "planned",
                },
            },
        )
        self._write_reflection(
            package_dir,
            target="directx",
            native_path=native_path,
            descriptor_type="UAV",
            abi={"space": 0, "register": "u0"},
        )
        self._write_json(
            package_dir / "diagnostics.json",
            {"schemaVersion": 1, "diagnostics": []},
        )

    def _write_reflection(
        self,
        package_dir: Path,
        *,
        target: str,
        native_path: str,
        descriptor_type: str,
        abi: dict[str, object],
    ) -> None:
        self._write_json(
            package_dir / "reflection.json",
            {
                "schemaVersion": 1,
                "module": "RuntimeBackendLoaderFixture",
                "target": target,
                "nativeBinary": native_path,
                "entryPoints": [
                    {
                        "stage": "compute",
                        "sourceName": "main",
                        "backendName": "runtime_backend_loader_main",
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
                        "entryPoint": "runtime_backend_loader_main",
                        "name": "OutputBuffer",
                        "kind": "storageBuffer",
                        "sourceType": "float4",
                        "addressSpace": "device",
                        "abi": abi,
                        "bindingClass": "buffer",
                        "descriptorType": descriptor_type,
                    }
                ],
            },
        )

    def _write_native_artifact_descriptor(
        self,
        package_dir: Path,
        *,
        descriptor_path: str,
        target: str,
        binary_kind: str,
        artifact_path: str,
        artifact_bytes: bytes,
    ) -> None:
        source_bytes = b"CrossGL source bytes intentionally not read by loader"
        self._write_json(
            package_dir / descriptor_path,
            {
                "schemaVersion": 1,
                "kind": "crossgl.nativeArtifact",
                "contractVersion": "native-artifact-v0",
                "target": target,
                "binaryKind": binary_kind,
                "sourcePath": "source/RuntimeBackendLoaderFixture.cgl",
                "sourceHash": self._sha256(source_bytes),
                "artifactPath": artifact_path,
                "artifactHash": self._sha256(artifact_bytes),
                "sizeBytes": len(artifact_bytes),
                "toolchainProvenance": {
                    "producer": "tests.runtime.test_backend_loader",
                    "tools": [],
                },
                "optimizationLevel": "unknown",
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

    def _guard_source_reads(self) -> object:
        original_read_text = Path.read_text
        original_read_bytes = Path.read_bytes
        original_open = Path.open

        def _assert_not_source(path: Path, action: str) -> None:
            if path.suffix == ".cgl":
                raise AssertionError(f"backend loader {action} source file: {path}")

        def guarded_read_text(path: Path, *args: object, **kwargs: object) -> str:
            _assert_not_source(path, "read")
            return original_read_text(path, *args, **kwargs)

        def guarded_read_bytes(path: Path, *args: object, **kwargs: object) -> bytes:
            _assert_not_source(path, "read")
            return original_read_bytes(path, *args, **kwargs)

        def guarded_open(path: Path, *args: object, **kwargs: object) -> object:
            _assert_not_source(path, "opened")
            return original_open(path, *args, **kwargs)

        return mock.patch.multiple(
            Path,
            read_text=guarded_read_text,
            read_bytes=guarded_read_bytes,
            open=guarded_open,
        )


if __name__ == "__main__":
    unittest.main()
