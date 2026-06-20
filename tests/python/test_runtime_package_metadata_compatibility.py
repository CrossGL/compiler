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


from runtime.loader import read_loader_plan  # noqa: E402
from runtime.package_reader import read_compatibility_report  # noqa: E402


class RuntimePackageMetadataCompatibilityTests(unittest.TestCase):
    def test_source_package_report_accepts_source_and_skips_planned_native(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory(suffix=".cglb") as temp_dir:
            package_dir = Path(temp_dir)
            self._write_package(package_dir, target="directx", native_status="planned")
            (package_dir / "backend" / "directx" / "MetadataFixture.dxil").unlink()
            (package_dir / "source").mkdir()
            (package_dir / "source" / "invalid.cgl").write_text(
                "runtime compatibility must not parse package source\n",
                encoding="utf-8",
            )

            report = read_compatibility_report(package_dir, loader_target="directx")
            summary = report.to_summary()["artifactCompatibility"]

            self.assertTrue(report.compatible, report.to_summary()["diagnostics"])
            self.assertFalse(report.source_parsing_required)
            self.assertEqual(summary["selectedArtifact"], "backendSource")
            self.assertEqual(
                [record["name"] for record in summary["accepted"]],
                ["backendSource"],
            )
            self.assertEqual(
                [record["name"] for record in summary["skipped"]],
                ["nativeBinary"],
            )
            self.assertEqual(summary["rejected"], [])
            self.assertEqual(
                summary["skipped"][0]["reason"],
                "package.artifact.planned_native_binary",
            )
            self.assertFalse(summary["skipped"][0]["exists"])

    def test_loader_target_mismatch_skips_declared_artifacts(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory(suffix=".cglb") as temp_dir:
            package_dir = Path(temp_dir)
            self._write_package(package_dir, target="metal")

            report = read_compatibility_report(package_dir, loader_target="vulkan")
            summary = report.to_summary()["artifactCompatibility"]

            self.assertFalse(report.compatible)
            self.assertEqual(summary["selectedArtifact"], None)
            self.assertEqual(summary["accepted"], [])
            self.assertEqual(summary["rejected"], [])
            self.assertEqual(
                [record["name"] for record in summary["skipped"]],
                ["backendSource", "intermediate", "nativeBinary"],
            )
            self.assertEqual(
                {record["reason"] for record in summary["skipped"]},
                {"package.target.loader_mismatch"},
            )

    def test_target_incompatible_manifest_sidecar_is_rejected_without_source_parse(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory(suffix=".cglb") as temp_dir:
            package_dir = Path(temp_dir)
            self._write_package(package_dir, target="directx", native_status="planned")
            manifest_path = package_dir / "manifest.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["artifacts"]["nativeProfile"] = "backend/directx/profile.json"
            self._write_json(manifest_path, manifest)
            self._write_json(
                package_dir / "backend" / "directx" / "profile.json",
                {
                    "schemaVersion": 1,
                    "target": "directx",
                    "nativeBinary": "backend/directx/MetadataFixture.dxil",
                },
            )
            source_path = package_dir / "source" / "invalid.cgl"
            source_path.parent.mkdir()
            source_path.write_text(
                "runtime compatibility must not parse CrossGL source\n",
                encoding="utf-8",
            )

            with self._guard_crossgl_source_reads():
                report = read_compatibility_report(
                    package_dir,
                    loader_target="directx",
                )
                plan = read_loader_plan(package_dir, "directx")

            summary = report.to_summary()["artifactCompatibility"]
            reject_codes = [diagnostic.code for diagnostic in report.reject_reasons]

            self.assertFalse(report.compatible)
            self.assertFalse(report.source_parsing_required)
            self.assertFalse(plan.loadable)
            self.assertFalse(plan.source_parsing_required)
            self.assertIn("package.artifact.target_incompatible", reject_codes)
            self.assertEqual(
                [record["name"] for record in summary["rejected"]],
                ["nativeProfile"],
            )
            self.assertEqual(
                summary["rejected"][0]["reason"],
                "package.artifact.target_incompatible",
            )
            self.assertEqual(list(package_dir.rglob("*.cgl")), [source_path])

    def test_missing_required_artifact_is_rejected_without_rejecting_usable_peers(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory(suffix=".cglb") as temp_dir:
            package_dir = Path(temp_dir)
            self._write_package(package_dir, target="metal")
            (package_dir / "backend" / "metal" / "MetadataFixture.metal").unlink()

            report = read_compatibility_report(package_dir, loader_target="metal")
            summary = report.to_summary()["artifactCompatibility"]

            self.assertFalse(report.compatible)
            self.assertEqual(summary["selectedArtifact"], None)
            self.assertEqual(
                [record["name"] for record in summary["accepted"]],
                ["intermediate", "nativeBinary"],
            )
            self.assertEqual(
                [record["name"] for record in summary["rejected"]],
                ["backendSource"],
            )
            self.assertEqual(
                summary["rejected"][0]["reason"],
                "package.artifact.required_file_missing",
            )
            self.assertEqual(summary["skipped"], [])

    def test_loader_summary_uses_requested_package_mode_for_selected_artifact(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory(suffix=".cglb") as temp_dir:
            package_dir = Path(temp_dir)
            self._write_package(package_dir, target="directx", native_status="emitted")

            plan = read_loader_plan(
                package_dir,
                "directx",
                package_mode="source-package",
            )
            summary = plan.to_summary()
            artifact_summary = summary["artifactCompatibility"]

            self.assertTrue(plan.loadable, summary["diagnostics"])
            self.assertEqual(
                summary["compatibilityReport"]["artifactCompatibility"][
                    "selectedArtifact"
                ],
                "nativeBinary",
            )
            self.assertEqual(artifact_summary["selectedArtifact"], "backendSource")
            accepted_by_name = {
                record["name"]: record for record in artifact_summary["accepted"]
            }
            self.assertTrue(accepted_by_name["backendSource"]["selected"])
            self.assertFalse(accepted_by_name["nativeBinary"]["selected"])
            self.assertEqual(artifact_summary["rejected"], [])
            self.assertEqual(artifact_summary["skipped"], [])

    def test_native_contract_rejects_planned_descriptor_source_evidence(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory(suffix=".cglb") as temp_dir:
            package_dir = Path(temp_dir)
            self._write_package(package_dir, target="metal", native_status="planned")
            self._write_native_artifact_descriptor(
                package_dir,
                target="metal",
                binary_kind="metal.metallib",
                native_status="planned",
            )

            with self._guard_crossgl_source_reads():
                report = read_compatibility_report(package_dir, loader_target="metal")

            summary = report.to_summary()["artifactCompatibility"]
            reject_codes = [diagnostic.code for diagnostic in report.reject_reasons]
            rejected_by_name = {
                record["name"]: record for record in summary["rejected"]
            }

            self.assertFalse(report.compatible)
            self.assertFalse(report.source_parsing_required)
            self.assertIn("package.native_binary_status.forbidden", reject_codes)
            self.assertIn(
                (
                    "package.native_artifact_descriptor."
                    "planned_source_evidence_forbidden"
                ),
                reject_codes,
            )
            self.assertEqual(
                rejected_by_name["nativeArtifactDescriptor"]["reason"],
                (
                    "package.native_artifact_descriptor."
                    "planned_source_evidence_forbidden"
                ),
            )
            self.assertEqual(
                report.admission_summary["decision"],
                "rejected",
            )

    def _write_package(
        self,
        package_dir: Path,
        *,
        target: str,
        native_status: str | None = None,
    ) -> None:
        backend_dir = package_dir / "backend" / target
        backend_dir.mkdir(parents=True)
        source_extension = {
            "directx": "hlsl",
            "metal": "metal",
        }.get(target, "src")
        binary_extension = {
            "directx": "dxil",
            "metal": "metallib",
        }.get(target, "bin")
        source_path = f"backend/{target}/MetadataFixture.{source_extension}"
        binary_path = f"backend/{target}/MetadataFixture.{binary_extension}"

        (backend_dir / f"MetadataFixture.{source_extension}").write_text(
            f"// generated {target} source\n",
            encoding="utf-8",
        )
        (backend_dir / f"MetadataFixture.{binary_extension}").write_bytes(b"bin")

        artifacts = {
            "backendSource": source_path,
        }
        if target == "metal":
            (backend_dir / "MetadataFixture.air").write_bytes(b"air")
            artifacts["intermediate"] = "backend/metal/MetadataFixture.air"
        artifacts["nativeBinary"] = binary_path
        if native_status is not None:
            artifacts["nativeBinaryStatus"] = native_status

        self._write_json(
            package_dir / "manifest.json",
            {
                "schemaVersion": 1,
                "compiler": {
                    "name": "CrossGL-Compiler",
                    "version": "test",
                },
                "module": "MetadataFixture",
                "target": target,
                "artifacts": artifacts,
            },
        )
        self._write_json(
            package_dir / "reflection.json",
            {
                "schemaVersion": 1,
                "module": "MetadataFixture",
                "target": target,
                "nativeBinary": binary_path,
                "entryPoints": [
                    {
                        "stage": "compute",
                        "sourceName": "main",
                        "backendName": "metadata_fixture_main",
                    }
                ],
                "resources": [
                    {
                        "stage": "compute",
                        "name": "OutputBuffer",
                        "kind": "storageBuffer",
                    }
                ],
                "targetResourceBindings": [
                    {
                        "target": target,
                        "stage": "compute",
                        "entryPoint": "metadata_fixture_main",
                        "name": "OutputBuffer",
                        "kind": "storageBuffer",
                    }
                ],
                "targetFeatures": [
                    {
                        "target": target,
                        "kind": "backend",
                        "name": target,
                    }
                ],
            },
        )
        self._write_json(
            package_dir / "diagnostics.json",
            {
                "schemaVersion": 1,
                "module": "MetadataFixture",
                "diagnostics": [],
            },
        )

    def _write_native_artifact_descriptor(
        self,
        package_dir: Path,
        *,
        target: str,
        binary_kind: str,
        native_status: str,
    ) -> None:
        manifest_path = package_dir / "manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        descriptor_path = f"backend/{target}/MetadataFixture.native-artifact.json"
        manifest["artifacts"]["nativeArtifactDescriptor"] = descriptor_path
        self._write_json(manifest_path, manifest)

        source_path = manifest["artifacts"]["backendSource"]
        source_bytes = (package_dir / source_path).read_bytes()
        self._write_json(
            package_dir / descriptor_path,
            {
                "schemaVersion": 1,
                "kind": "crossgl.nativeArtifact",
                "contractVersion": "native-artifact-v0",
                "target": target,
                "binaryKind": binary_kind,
                "sourcePath": source_path,
                "sourceHash": {
                    "algorithm": "sha256",
                    "value": hashlib.sha256(source_bytes).hexdigest(),
                },
                "nativeBinaryStatus": native_status,
                "validationStatus": "unavailable",
                "optimizationLevel": "unknown",
                "toolchainProvenance": {"tools": []},
            },
        )

    def _write_json(self, path: Path, data: dict[str, object]) -> None:
        path.write_text(
            json.dumps(data, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )

    def _guard_crossgl_source_reads(self):
        original_read_text = Path.read_text
        original_read_bytes = Path.read_bytes

        def guarded_read_text(path: Path, *args: object, **kwargs: object) -> str:
            if path.suffix == ".cgl":
                raise AssertionError(f"runtime parsed source file: {path}")
            return original_read_text(path, *args, **kwargs)

        def guarded_read_bytes(path: Path, *args: object, **kwargs: object) -> bytes:
            if path.suffix == ".cgl":
                raise AssertionError(f"runtime parsed source file: {path}")
            return original_read_bytes(path, *args, **kwargs)

        return mock.patch.multiple(
            Path,
            read_text=guarded_read_text,
            read_bytes=guarded_read_bytes,
        )


if __name__ == "__main__":
    unittest.main()
