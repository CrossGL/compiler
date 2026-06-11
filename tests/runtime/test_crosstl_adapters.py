#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest


REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))


from runtime.crosstl_adapters import (  # noqa: E402
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
                [(diagnostic.severity, diagnostic.code) for diagnostic in report.diagnostics],
                [("warning", "crosstl.adapter.unsupported_target")],
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

    def _write_adapter_bundle(
        self,
        root: Path,
        *,
        target: str,
        adapter_kind: str | None = None,
        package_path: str | None = None,
    ) -> Path:
        adapter_kind = adapter_kind or f"{target}-glsl-adapter"
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
            "id": f"{target}.main",
            "target": target,
            "adapterKind": adapter_kind,
            "artifactFormat": "GLSL source",
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
            "hostInterface": {"status": "ready"},
            "requiredTools": [f"{target}.toolchain.compiler"],
            "hostResponsibilities": ["load-package-artifact"],
            "validation": {"loadReady": True},
        }
        self._write_json(descriptor_file, descriptor)
        descriptor_bytes = descriptor_file.read_bytes()
        descriptor_record = {
            "id": descriptor["id"],
            "target": target,
            "adapterKind": adapter_kind,
            "artifactFormat": "GLSL source",
            "binding": descriptor["binding"],
            "artifact": descriptor["artifact"],
            "packagePath": package_path,
            "descriptorPath": descriptor_path,
            "descriptorHash": {
                "algorithm": "sha256",
                "value": hashlib.sha256(descriptor_bytes).hexdigest(),
            },
            "descriptorSizeBytes": len(descriptor_bytes),
            "hostInterfaceStatus": "ready",
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
                "readyDescriptorCount": 1,
                "blockedDescriptorCount": 0,
                "actionCount": 0,
                "runtimeReferenceCount": 1,
            },
            "targets": [
                {
                    "target": target,
                    "adapterKind": adapter_kind,
                    "adapterCount": 1,
                    "descriptorCount": 1,
                    "readyDescriptorCount": 1,
                    "blockedDescriptorCount": 0,
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
