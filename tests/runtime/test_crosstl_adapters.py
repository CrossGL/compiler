#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re
import sys
import tempfile
import unittest


REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))


from runtime.crosstl_adapters import (  # noqa: E402
    build_crosstl_runtime_adapter_normalization_report,
    normalize_crosstl_runtime_adapter_candidates,
    read_crosstl_runtime_adapter_package,
)


class CrossTLRuntimeAdapterPackageReaderTests(unittest.TestCase):
    def test_reads_supported_runtime_adapter_descriptor_bundle(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            manifest = self._write_adapter_bundle(root, target="opengl")

            report = read_crosstl_runtime_adapter_package(manifest)

            self.assertTrue(report.valid, report.diagnostics)
            self.assertTrue(report.compiler_supported, report.diagnostics)
            self.assertEqual(report.package_kind, "crosstl-runtime-adapter-package")
            self.assertEqual(report.adapter_manifest, "runtime-adapters.json")
            self.assertEqual(report.descriptor_count, 1)
            self.assertEqual(report.supported_targets, ("opengl",))
            self.assertEqual(report.unsupported_targets, ())
            self.assertEqual(report.diagnostics, ())
            descriptor = report.descriptors[0]
            self.assertEqual(descriptor.id, "opengl.main")
            self.assertEqual(descriptor.target, "opengl")
            self.assertEqual(descriptor.adapter_kind, "opengl-glsl-adapter")
            self.assertEqual(descriptor.artifact_format, "GLSL source")
            self.assertEqual(descriptor.package_path, "backend/opengl/main.glsl")
            self.assertEqual(
                descriptor.descriptor_path,
                "adapters/opengl/opengl-main.adapter.json",
            )
            self.assertEqual(descriptor.host_interface_status, "ready")
            candidates = normalize_crosstl_runtime_adapter_candidates(report)
            self.assertEqual(len(candidates), 1)
            candidate = candidates[0]
            self.assertEqual(candidate.id, "runtime-loader.opengl.OpenglMain")
            self.assertEqual(candidate.target, "opengl")
            self.assertEqual(candidate.artifact_name, "backendSource")
            self.assertEqual(candidate.adapter_kind, "backend-source-loader")
            self.assertEqual(candidate.artifact_format, "backend-source")
            self.assertEqual(candidate.producer_adapter_kind, "opengl-glsl-adapter")
            self.assertEqual(candidate.producer_artifact_format, "GLSL source")
            self.assertEqual(candidate.package_path, "backend/opengl/main.glsl")
            self.assertTrue(candidate.load_ready)
            self.assertEqual(candidate.host_interface_status, "ready")
            self.assertEqual(candidate.required_tools, ("opengl.toolchain.compiler",))
            self.assertEqual(
                candidate.host_responsibilities, ("load-package-artifact",)
            )
            self.assertEqual(candidate.source_path, "src/opengl/main.crossgl")
            self.assertEqual(candidate.source_backend, "crossgl")
            self.assertEqual(candidate.stage, "compute")
            self.assertEqual(candidate.variant, "debug")
            self.assertEqual(candidate.defines, {})
            self.assertEqual(
                candidate.source_remap,
                {"packagePath": "source-remaps/opengl/main.source-remap.json"},
            )
            self.assertEqual(candidate.validation["loadReady"], True)
            self.assertEqual(candidate.host_interface["status"], "ready")
            self.assertEqual(
                candidate.entry_points,
                (
                    {
                        "name": "main",
                        "stage": "compute",
                        "executionConfig": {"workgroupSize": [8, 1, 1]},
                    },
                ),
            )
            self.assertEqual(
                candidate.resources,
                (
                    {
                        "name": "Particles",
                        "kind": "buffer",
                        "type": "RWStructuredBuffer<float4>",
                        "set": 0,
                        "binding": 1,
                        "access": "read-write",
                    },
                ),
            )
            self.assertEqual(
                candidate.constants,
                (
                    {
                        "name": "ParticleCount",
                        "kind": "specialization-constant",
                        "dtype": "uint",
                        "id": 0,
                        "required": False,
                    },
                ),
            )
            self.assertEqual(
                candidate.target_resource_binding_metadata,
                (
                    {
                        "target": "opengl",
                        "stage": "compute",
                        "entryPoint": "main",
                        "name": "Particles",
                        "kind": "buffer",
                        "bindingClass": None,
                        "descriptorType": None,
                        "set": 0,
                        "binding": 1,
                        "argumentIndex": None,
                        "abi": {
                            "source": "hostInterface.resources",
                            "status": "bound",
                        },
                        "evidenceId": "hostInterface.resources[0]",
                    },
                ),
            )
            normalization_report = build_crosstl_runtime_adapter_normalization_report(
                report
            )
            self.assertEqual(normalization_report.candidates, candidates)
            self.assertEqual(normalization_report.candidate_count, 1)
            self.assertEqual(normalization_report.ready_candidate_count, 1)
            self.assertEqual(normalization_report.blocked_candidate_count, 0)
            self.assertEqual(normalization_report.skipped_descriptor_count, 0)
            self.assertEqual(normalization_report.unsupported_target_count, 0)
            self.assertEqual(normalization_report.targets, ("opengl",))

    def test_reports_unsupported_descriptor_targets_without_invalidating_package(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            manifest = self._write_adapter_bundle(
                root,
                target="cuda",
                adapter_kind="cuda-source-adapter",
                package_path="backend/cuda/main.cu",
            )

            report = read_crosstl_runtime_adapter_package(manifest)

            self.assertTrue(report.valid, report.diagnostics)
            self.assertFalse(report.compiler_supported)
            self.assertEqual(report.supported_targets, ())
            self.assertEqual(report.unsupported_targets, ("cuda",))
            self.assertEqual(
                [
                    (diagnostic.severity, diagnostic.code)
                    for diagnostic in report.diagnostics
                ],
                [("warning", "crosstl.adapter.unsupported_target")],
            )
            self.assertEqual(normalize_crosstl_runtime_adapter_candidates(report), ())
            normalization_report = build_crosstl_runtime_adapter_normalization_report(
                report
            )
            self.assertEqual(normalization_report.candidate_count, 0)
            self.assertEqual(normalization_report.skipped_descriptor_count, 1)
            self.assertEqual(normalization_report.unsupported_target_count, 1)
            self.assertEqual(
                normalization_report.skipped_descriptors[0].reason,
                "unsupported-target",
            )

    def test_normalizes_native_binary_adapter_candidate(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            manifest = self._write_adapter_bundle(
                root,
                target="directx",
                adapter_kind="directx-dxil-adapter",
                artifact_format="DXIL binary",
                package_path="backend/directx/main.dxil",
            )

            report = read_crosstl_runtime_adapter_package(manifest)
            candidates = normalize_crosstl_runtime_adapter_candidates(report)

            self.assertTrue(report.valid, report.diagnostics)
            self.assertEqual(len(candidates), 1)
            self.assertEqual(candidates[0].artifact_format, "native-binary")
            self.assertEqual(candidates[0].artifact_name, "nativeBinary")
            self.assertEqual(candidates[0].adapter_kind, "native-binary-loader")
            self.assertEqual(candidates[0].producer_artifact_format, "DXIL binary")

    def test_normalizes_known_artifact_format_aliases(self) -> None:
        cases = {
            "GLSL source": "backend-source",
            "glsl-source": "backend-source",
            "HLSL source": "backend-source",
            "MSL source": "backend-source",
            "Metal source": "backend-source",
            "WGSL source": "backend-source",
            "backend-source": "backend-source",
            "DXIL": "native-binary",
            "DXIL binary": "native-binary",
            "DXBC": "native-binary",
            "metallib": "native-binary",
            "SPIR-V": "native-binary",
            "SPIR-V module": "native-binary",
            "spirv": "native-binary",
            "native-binary": "native-binary",
        }
        for artifact_format, expected_format in cases.items():
            with self.subTest(artifact_format=artifact_format):
                with tempfile.TemporaryDirectory() as temp_dir:
                    root = Path(temp_dir)
                    manifest = self._write_adapter_bundle(
                        root,
                        target="opengl",
                        artifact_format=artifact_format,
                    )

                    report = read_crosstl_runtime_adapter_package(manifest)
                    candidates = normalize_crosstl_runtime_adapter_candidates(report)

                    self.assertTrue(report.valid, report.diagnostics)
                    self.assertEqual(len(candidates), 1)
                    self.assertEqual(candidates[0].artifact_format, expected_format)

    def test_unknown_artifact_format_does_not_create_candidate(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            manifest = self._write_adapter_bundle(
                root,
                target="opengl",
                artifact_format="mystery intermediate",
            )

            report = read_crosstl_runtime_adapter_package(manifest)

            self.assertTrue(report.valid, report.diagnostics)
            self.assertIn(
                "crosstl.adapter.unsupported_artifact_format",
                {diagnostic.code for diagnostic in report.diagnostics},
            )
            self.assertEqual(normalize_crosstl_runtime_adapter_candidates(report), ())
            normalization_report = build_crosstl_runtime_adapter_normalization_report(
                report
            )
            self.assertEqual(normalization_report.candidate_count, 0)
            self.assertEqual(normalization_report.skipped_descriptor_count, 1)
            self.assertEqual(normalization_report.unsupported_artifact_format_count, 1)
            self.assertEqual(
                normalization_report.skipped_descriptors[0].reason,
                "unsupported-artifact-format",
            )

    def test_blocked_host_interface_keeps_candidate_unready(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            manifest = self._write_adapter_bundle(
                root,
                target="vulkan",
                adapter_kind="vulkan-shader-adapter",
                artifact_format="Vulkan-targeted shader source",
                package_path="backend/vulkan/main.spvasm",
                host_interface_status="blocked",
                load_ready=False,
            )

            report = read_crosstl_runtime_adapter_package(manifest)
            candidates = normalize_crosstl_runtime_adapter_candidates(report)

            self.assertTrue(report.valid, report.diagnostics)
            self.assertEqual(len(candidates), 1)
            self.assertEqual(candidates[0].adapter_kind, "backend-source-loader")
            self.assertEqual(candidates[0].artifact_format, "backend-source")
            self.assertEqual(candidates[0].host_interface_status, "blocked")
            self.assertFalse(candidates[0].load_ready)
            normalization_report = build_crosstl_runtime_adapter_normalization_report(
                report
            )
            self.assertEqual(normalization_report.candidate_count, 1)
            self.assertEqual(normalization_report.ready_candidate_count, 0)
            self.assertEqual(normalization_report.blocked_candidate_count, 1)

    def test_invalid_report_does_not_create_candidates(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            manifest = self._write_adapter_bundle(root, target="opengl")
            payload = json.loads(manifest.read_text(encoding="utf-8"))
            payload["descriptors"][0]["descriptorHash"]["value"] = "0" * 64
            self._write_json(manifest, payload)

            report = read_crosstl_runtime_adapter_package(manifest)

            self.assertFalse(report.valid)
            self.assertEqual(normalize_crosstl_runtime_adapter_candidates(report), ())
            normalization_report = build_crosstl_runtime_adapter_normalization_report(
                report
            )
            self.assertEqual(normalization_report.candidate_count, 0)
            self.assertEqual(normalization_report.skipped_descriptor_count, 1)
            self.assertEqual(
                normalization_report.skipped_descriptors[0].reason,
                "invalid-package",
            )

    def test_native_unsupported_target_is_not_normalized(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            manifest = self._write_adapter_bundle(
                root,
                target="cuda",
                adapter_kind="cuda-native-adapter",
                artifact_format="native-binary",
                package_path="backend/cuda/main.cubin",
            )

            report = read_crosstl_runtime_adapter_package(manifest)

            self.assertTrue(report.valid, report.diagnostics)
            self.assertFalse(report.compiler_supported)
            self.assertEqual(normalize_crosstl_runtime_adapter_candidates(report), ())

    def test_candidate_id_is_runtime_loader_safe_for_punctuation(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            manifest = self._write_adapter_bundle(
                root,
                target="metal",
                adapter_id="123.main/kernel:debug",
                package_path="backend/metal/main.metal",
            )

            report = read_crosstl_runtime_adapter_package(manifest)
            candidates = normalize_crosstl_runtime_adapter_candidates(report)

            self.assertEqual(len(candidates), 1)
            self.assertRegex(
                candidates[0].id,
                re.compile(r"^runtime-loader\.metal\.[A-Za-z][A-Za-z0-9]*$"),
            )

    def test_detects_descriptor_hash_and_size_drift(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            manifest = self._write_adapter_bundle(root, target="opengl")
            payload = json.loads(manifest.read_text(encoding="utf-8"))
            payload["descriptors"][0]["descriptorHash"]["value"] = "0" * 64
            payload["descriptors"][0]["descriptorSizeBytes"] += 1
            self._write_json(manifest, payload)

            report = read_crosstl_runtime_adapter_package(manifest)

            self.assertFalse(report.valid)
            self.assertFalse(report.compiler_supported)
            self.assertIn(
                "crosstl.adapter.descriptor_hash_drift",
                {diagnostic.code for diagnostic in report.diagnostics},
            )
            self.assertIn(
                "crosstl.adapter.descriptor_size_drift",
                {diagnostic.code for diagnostic in report.diagnostics},
            )

    def test_rejects_descriptor_paths_outside_adapter_root(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            manifest = self._write_adapter_bundle(root, target="opengl")
            payload = json.loads(manifest.read_text(encoding="utf-8"))
            payload["descriptors"][0]["descriptorPath"] = "../opengl.adapter.json"
            self._write_json(manifest, payload)

            report = read_crosstl_runtime_adapter_package(manifest)

            self.assertFalse(report.valid)
            self.assertIn(
                "crosstl.adapter.invalid_descriptor_path",
                {diagnostic.code for diagnostic in report.diagnostics},
            )

    def test_detects_manifest_host_interface_status_drift(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            manifest = self._write_adapter_bundle(root, target="opengl")
            payload = json.loads(manifest.read_text(encoding="utf-8"))
            descriptor_path = root / payload["descriptors"][0]["descriptorPath"]
            descriptor = json.loads(descriptor_path.read_text(encoding="utf-8"))
            descriptor["hostInterface"]["status"] = "blocked"
            self._write_json(descriptor_path, descriptor)
            descriptor_bytes = descriptor_path.read_bytes()
            payload["descriptors"][0]["descriptorHash"]["value"] = hashlib.sha256(
                descriptor_bytes
            ).hexdigest()
            payload["descriptors"][0]["descriptorSizeBytes"] = len(descriptor_bytes)
            self._write_json(manifest, payload)

            report = read_crosstl_runtime_adapter_package(manifest)

            self.assertFalse(report.valid)
            self.assertIn(
                "crosstl.adapter.host_interface_record_drift",
                {diagnostic.code for diagnostic in report.diagnostics},
            )

    def _write_adapter_bundle(
        self,
        root: Path,
        *,
        target: str,
        adapter_id: str | None = None,
        adapter_kind: str | None = None,
        artifact_format: str = "GLSL source",
        package_path: str | None = None,
        host_interface_status: str = "ready",
        load_ready: bool = True,
    ) -> Path:
        adapter_kind = adapter_kind or f"{target}-glsl-adapter"
        adapter_id = adapter_id or f"{target}.main"
        package_path = package_path or f"backend/{target}/main.glsl"
        descriptor_path = f"adapters/{target}/{target}-main.adapter.json"
        descriptor_file = root / descriptor_path
        descriptor_file.parent.mkdir(parents=True)
        descriptor = {
            "schemaVersion": 1,
            "kind": "crosstl-runtime-adapter-descriptor",
            "sourcePackage": str(root / "runtime-package.json"),
            "sourcePackageHash": {"algorithm": "sha256", "value": "1" * 64},
            "packageRoot": str(root),
            "adapterPlan": {
                "kind": "crosstl-runtime-adapter-plan",
                "success": True,
                "scope": "runtime-adapter-integration-planning",
            },
            "id": adapter_id,
            "target": target,
            "adapterKind": adapter_kind,
            "artifactFormat": artifact_format,
            "binding": {"kind": "runtime-adapter"},
            "artifact": {"name": "backendSource"},
            "packagePath": package_path,
            "sourcePath": f"src/{target}/main.crossgl",
            "sourceBackend": "crossgl",
            "stage": "compute",
            "variant": "debug",
            "defines": {},
            "sourceRemap": {
                "packagePath": f"source-remaps/{target}/main.source-remap.json"
            },
            "hostInterface": {
                "status": host_interface_status,
                "source": "package-artifact",
                "parser": target,
                "artifactFormat": artifact_format,
                "entryPointCount": 1,
                "resourceCount": 1,
                "constantCount": 1,
                "entryPoints": [
                    {
                        "name": "main",
                        "stage": "compute",
                        "executionConfig": {"workgroupSize": [8, 1, 1]},
                    }
                ],
                "resources": [
                    {
                        "name": "Particles",
                        "kind": "buffer",
                        "type": "RWStructuredBuffer<float4>",
                        "set": 0,
                        "binding": 1,
                        "access": "read-write",
                    }
                ],
                "constants": [
                    {
                        "name": "ParticleCount",
                        "kind": "specialization-constant",
                        "dtype": "uint",
                        "id": 0,
                        "required": False,
                    }
                ],
                "diagnostics": [],
            },
            "requiredTools": [f"{target}.toolchain.compiler"],
            "hostResponsibilities": ["load-package-artifact"],
            "validation": {"loadReady": load_ready},
        }
        self._write_json(descriptor_file, descriptor)
        descriptor_bytes = descriptor_file.read_bytes()
        descriptor_record = {
            "id": descriptor["id"],
            "target": target,
            "adapterKind": adapter_kind,
            "artifactFormat": artifact_format,
            "binding": descriptor["binding"],
            "artifact": descriptor["artifact"],
            "packagePath": package_path,
            "descriptorPath": descriptor_path,
            "descriptorHash": {
                "algorithm": "sha256",
                "value": hashlib.sha256(descriptor_bytes).hexdigest(),
            },
            "descriptorSizeBytes": len(descriptor_bytes),
            "hostInterfaceStatus": host_interface_status,
            "requiredTools": descriptor["requiredTools"],
        }
        manifest = {
            "schemaVersion": 1,
            "kind": "crosstl-runtime-adapter-package",
            "sourcePackage": str(root / "runtime-package.json"),
            "sourcePackageHash": {"algorithm": "sha256", "value": "1" * 64},
            "generatedAt": 1,
            "success": True,
            "scope": "runtime-adapter-descriptor-package",
            "nonGoals": ["host-code-rewriting"],
            "packageRoot": str(root),
            "adapterRoot": str(root),
            "adapterManifest": "runtime-adapters.json",
            "project": {"targets": [target]},
            "summary": {
                "targetCount": 1,
                "adapterCount": 1,
                "descriptorCount": 1,
                "readyDescriptorCount": 1 if host_interface_status == "ready" else 0,
                "blockedDescriptorCount": 0 if host_interface_status == "ready" else 1,
                "actionCount": 0,
                "runtimeReferenceCount": 1,
            },
            "targets": [
                {
                    "target": target,
                    "adapterKind": adapter_kind,
                    "adapterCount": 1,
                    "descriptorCount": 1,
                    "readyDescriptorCount": 1
                    if host_interface_status == "ready"
                    else 0,
                    "blockedDescriptorCount": 0
                    if host_interface_status == "ready"
                    else 1,
                    "runtimeReferenceCount": 1,
                    "requiredTools": descriptor["requiredTools"],
                    "descriptors": [descriptor["id"]],
                    "packagePaths": [package_path],
                }
            ],
            "descriptors": [descriptor_record],
            "actions": [],
            "runtimePlan": {"kind": "crosstl-runtime-plan"},
            "adapterPlan": {
                "kind": "crosstl-runtime-adapter-plan",
                "success": True,
                "adapterCount": 1,
                "actionCount": 0,
            },
            "packageInspection": {"success": True},
            "diagnosticCounts": {"note": 0, "warning": 0, "error": 0},
            "diagnostics": [],
        }
        manifest_path = root / "runtime-adapters.json"
        self._write_json(manifest_path, manifest)
        return manifest_path

    def _write_json(self, path: Path, document: dict[str, object]) -> None:
        path.write_text(
            json.dumps(document, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )


if __name__ == "__main__":
    unittest.main()
