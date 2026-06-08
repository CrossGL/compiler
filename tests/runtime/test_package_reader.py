#!/usr/bin/env python3
from __future__ import annotations

from contextlib import contextmanager
from contextlib import nullcontext
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock
import warnings
import zipfile


REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURE_ROOT = REPO_ROOT / "runtime" / "examples" / "fixtures"
sys.path.insert(0, str(REPO_ROOT))


def _discard_legacy_cglc_arg() -> None:
    # CTest still passes this compiler path; runtime tests remain fixture-only.
    index = 1
    while index < len(sys.argv):
        if sys.argv[index] == "--cglc":
            if index + 1 >= len(sys.argv):
                raise RuntimeError("--cglc requires a path")
            del sys.argv[index : index + 2]
            continue
        if sys.argv[index].startswith("--cglc="):
            del sys.argv[index]
            continue
        index += 1


_discard_legacy_cglc_arg()


import runtime.package_reader as package_reader_module  # noqa: E402
import runtime.package_target_contracts as runtime_target_contracts  # noqa: E402
from runtime.package_reader import (  # noqa: E402
    PackageReadError,
    read_compatibility_report,
    read_package,
    select_runtime_artifact,
)
from tools import package_target_contracts as tool_target_contracts  # noqa: E402


@contextmanager
def _runtime_metadata_byte_limit(limit: int):
    original_limit = package_reader_module.RUNTIME_METADATA_JSON_BYTE_LIMIT
    package_reader_module.RUNTIME_METADATA_JSON_BYTE_LIMIT = limit
    try:
        yield
    finally:
        package_reader_module.RUNTIME_METADATA_JSON_BYTE_LIMIT = original_limit


class RuntimePackageReaderTests(unittest.TestCase):
    def test_generated_runtime_contract_data_matches_package_target_json(
        self,
    ) -> None:
        contract_path = REPO_ROOT / "tools" / "package_target_contracts.json"
        with contract_path.open("r", encoding="utf-8") as handle:
            document = json.load(handle)

        contracts, debug_artifacts = tool_target_contracts.load_contract_document(
            contract_path,
            label_root=REPO_ROOT,
        )
        json_contracts = tuple(
            {
                "target": entry["target"],
                "requiredPathArtifacts": tuple(entry["requiredPathArtifacts"]),
                "requiresNativeBinaryStatus": entry["requiresNativeBinaryStatus"],
                "allowsPlannedNativeBinary": entry["allowsPlannedNativeBinary"],
                "allowsPlannedNativeSourceEvidence": (
                    entry["allowsPlannedNativeSourceEvidence"]
                ),
            }
            for entry in document["targets"]
        )
        validated_contracts = tuple(
            {
                "target": contract.target,
                "requiredPathArtifacts": contract.required_path_artifacts,
                "requiresNativeBinaryStatus": (contract.requires_native_binary_status),
                "allowsPlannedNativeBinary": (contract.allows_planned_native_binary),
                "allowsPlannedNativeSourceEvidence": (
                    contract.allows_planned_native_source_evidence
                ),
            }
            for contract in contracts
        )

        self.assertEqual(runtime_target_contracts.SCHEMA_VERSION, 1)
        self.assertEqual(
            runtime_target_contracts.SCHEMA_VERSION,
            document["schemaVersion"],
        )
        self.assertEqual(
            runtime_target_contracts.PACKAGE_DEBUG_ARTIFACTS,
            debug_artifacts,
        )
        self.assertEqual(
            runtime_target_contracts.PACKAGE_TARGET_CONTRACTS,
            json_contracts,
        )
        self.assertEqual(
            runtime_target_contracts.PACKAGE_TARGET_CONTRACTS,
            validated_contracts,
        )

    def test_runtime_required_artifacts_follow_generated_contract_data(
        self,
    ) -> None:
        original_contracts = runtime_target_contracts.PACKAGE_TARGET_CONTRACTS
        runtime_target_contracts.PACKAGE_TARGET_CONTRACTS = tuple(
            {
                **entry,
                "requiredPathArtifacts": ("nativeBinary",),
            }
            if entry["target"] == "metal"
            else entry
            for entry in original_contracts
        )
        try:
            with tempfile.TemporaryDirectory(suffix=".cglb") as temp_dir:
                package_dir = Path(temp_dir)
                self._write_valid_package(package_dir)
                manifest_path = package_dir / "manifest.json"
                manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
                del manifest["artifacts"]["backendSource"]
                del manifest["artifacts"]["intermediate"]
                self._write_json(manifest_path, manifest)

                package = read_package(package_dir)
                report = package.compatibility_report(loader_target="metal")
                summary = report.to_summary()

                self.assertTrue(report.compatible, summary["diagnostics"])
                self.assertEqual(
                    package.required_target_artifacts(),
                    ("nativeBinary",),
                )
                self.assertEqual(report.required_artifacts, ("nativeBinary",))
                self.assertEqual(
                    summary["targetContract"]["requiredPathArtifacts"],
                    ["nativeBinary"],
                )
                self.assertEqual(summary["missingArtifacts"], [])
        finally:
            runtime_target_contracts.PACKAGE_TARGET_CONTRACTS = original_contracts

    def test_compatibility_report_reads_runtime_package_fixtures_without_source_parse(
        self,
    ) -> None:
        cases = (
            (
                "future-schema-directx.cglb",
                "directx",
                "unsupported-version",
                False,
                ("package.schema.incompatible",),
                ("backendSource", "nativeBinary"),
                "legacy-v0-target-contract",
            ),
            (
                "source-free-directx-emitted-dxil.cglb",
                "directx",
                "compatible",
                True,
                (),
                ("backendSource", "nativeBinary"),
                "manifest",
            ),
            (
                "source-free-directx.cglb",
                "directx",
                "source-only",
                True,
                (),
                ("backendSource", "nativeBinary"),
                "legacy-v0-target-contract",
            ),
            (
                "source-free-metal-native.cglb",
                "metal",
                "compatible",
                True,
                (),
                ("backendSource", "intermediate", "nativeBinary"),
                "legacy-v0-target-contract",
            ),
            (
                "source-free-opengl-validated-source.cglb",
                "opengl",
                "compatible",
                True,
                (),
                ("backendSource", "nativeBinary"),
                "manifest",
            ),
            (
                "source-free-opengl.cglb",
                "opengl",
                "source-only",
                True,
                (),
                ("backendSource", "nativeBinary"),
                "legacy-v0-target-contract",
            ),
            (
                "source-free-vulkan-native.cglb",
                "vulkan",
                "compatible",
                True,
                (),
                ("backendAssembly", "nativeBinary"),
                "legacy-v0-target-contract",
            ),
        )

        for (
            fixture_name,
            target,
            expected_status,
            expected_compatible,
            expected_reject_codes,
            expected_required_artifacts,
            expected_requirements_source,
        ) in cases:
            with self.subTest(fixture=fixture_name):
                with self._guard_crossgl_source_reads():
                    report = read_compatibility_report(
                        FIXTURE_ROOT / fixture_name,
                        loader_target=target,
                    )

                summary = report.to_summary()

                self.assertEqual(report.status, expected_status)
                self.assertEqual(report.compatible, expected_compatible)
                self.assertFalse(report.source_parsing_required)
                self.assertFalse(report.compiler_invocation_required)
                self.assertFalse(report.device_execution_required)
                self.assertEqual(report.source_inputs, ())
                self.assertEqual(report.required_artifacts, expected_required_artifacts)
                self.assertIsNotNone(report.target_contract)
                self.assertEqual(
                    report.target_contract.requirements_source,
                    expected_requirements_source,
                )
                self.assertEqual(
                    tuple(diagnostic.code for diagnostic in report.reject_reasons),
                    expected_reject_codes,
                )
                self.assertEqual(summary["sourceInputs"], [])

    def test_compatibility_report_rejects_malformed_generated_target_contract_fields_without_source_parse(
        self,
    ) -> None:
        valid_metal_contract: dict[str, object] = {
            "target": "metal",
            "requiredPathArtifacts": (
                "backendSource",
                "intermediate",
                "nativeBinary",
            ),
            "requiresNativeBinaryStatus": False,
            "allowsPlannedNativeBinary": False,
            "allowsPlannedNativeSourceEvidence": False,
        }
        cases: tuple[tuple[str, dict[str, object], str, str], ...] = (
            (
                "missing required field",
                {
                    key: value
                    for key, value in valid_metal_contract.items()
                    if key != "requiresNativeBinaryStatus"
                },
                "package.target_contract.requires_native_binary_status_missing",
                "PACKAGE_TARGET_CONTRACTS[0].requiresNativeBinaryStatus",
            ),
            (
                "missing planned source evidence field",
                {
                    key: value
                    for key, value in valid_metal_contract.items()
                    if key != "allowsPlannedNativeSourceEvidence"
                },
                (
                    "package.target_contract."
                    "allows_planned_native_source_evidence_missing"
                ),
                "PACKAGE_TARGET_CONTRACTS[0].allowsPlannedNativeSourceEvidence",
            ),
            (
                "future field",
                {**valid_metal_contract, "artifactFlavor": "compressed"},
                "package.target_contract.unexpected_field",
                "PACKAGE_TARGET_CONTRACTS[0].artifactFlavor",
            ),
            (
                "invalid target field",
                {**valid_metal_contract, "target": []},
                "package.target_contract.target_invalid",
                "PACKAGE_TARGET_CONTRACTS[0].target",
            ),
            (
                "invalid native status field",
                {
                    **valid_metal_contract,
                    "requiresNativeBinaryStatus": "false",
                },
                "package.target_contract.requires_native_binary_status_invalid",
                "PACKAGE_TARGET_CONTRACTS[0].requiresNativeBinaryStatus",
            ),
            (
                "invalid planned source evidence field",
                {
                    **valid_metal_contract,
                    "allowsPlannedNativeSourceEvidence": "false",
                },
                (
                    "package.target_contract."
                    "allows_planned_native_source_evidence_invalid"
                ),
                "PACKAGE_TARGET_CONTRACTS[0].allowsPlannedNativeSourceEvidence",
            ),
            (
                "mismatched planned source evidence field",
                {
                    **valid_metal_contract,
                    "allowsPlannedNativeSourceEvidence": True,
                },
                "package.target_contract.native_binary_policy_mismatch",
                "PACKAGE_TARGET_CONTRACTS[0]",
            ),
            (
                "unknown required path artifact",
                {
                    **valid_metal_contract,
                    "requiredPathArtifacts": (
                        "backendSource",
                        "shaderBlob",
                        "nativeBinary",
                    ),
                },
                "package.target_contract.required_path_artifact_unknown",
                "PACKAGE_TARGET_CONTRACTS[0].requiredPathArtifacts[1]",
            ),
            (
                "missing native binary required artifact",
                {
                    **valid_metal_contract,
                    "requiredPathArtifacts": (
                        "backendSource",
                        "intermediate",
                    ),
                },
                "package.target_contract.native_binary_missing",
                "PACKAGE_TARGET_CONTRACTS[0].requiredPathArtifacts",
            ),
        )
        original_contracts = runtime_target_contracts.PACKAGE_TARGET_CONTRACTS
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

        try:
            for name, generated_contract, expected_code, expected_path in cases:
                with self.subTest(name=name):
                    runtime_target_contracts.PACKAGE_TARGET_CONTRACTS = (
                        generated_contract,
                    )
                    with tempfile.TemporaryDirectory(suffix=".cglb") as temp_dir:
                        package_dir = Path(temp_dir)
                        self._write_valid_package(package_dir)
                        source_path = package_dir / "source" / "invalid.cgl"
                        source_path.parent.mkdir()
                        source_path.write_text(
                            "runtime must not parse CrossGL source for "
                            "malformed generated target contracts\n",
                            encoding="utf-8",
                        )

                        with mock.patch.object(Path, "read_text", guarded_read_text):
                            with mock.patch.object(
                                Path,
                                "read_bytes",
                                guarded_read_bytes,
                            ):
                                report = read_compatibility_report(
                                    package_dir,
                                    loader_target="metal",
                                )
                                selection = select_runtime_artifact(
                                    report,
                                    target="metal",
                                )

                        summary = report.to_summary()
                        reject_codes = [
                            diagnostic.code for diagnostic in report.reject_reasons
                        ]

                        self.assertFalse(report.compatible)
                        self.assertEqual(report.status, "incompatible")
                        self.assertIsNone(report.target_contract)
                        self.assertEqual(report.required_artifacts, ())
                        self.assertIn(expected_code, reject_codes)
                        self.assertNotIn("package.target.unsupported", reject_codes)
                        self.assertFalse(selection.selected)
                        self.assertIsNone(selection.artifact)
                        self.assertFalse(selection.source_parsing_required)
                        self.assertEqual(
                            next(
                                diagnostic
                                for diagnostic in summary["rejectReasons"]
                                if diagnostic["code"] == expected_code
                            )["path"],
                            expected_path,
                        )
                        self.assertEqual(
                            list(package_dir.rglob("*.cgl")), [source_path]
                        )
        finally:
            runtime_target_contracts.PACKAGE_TARGET_CONTRACTS = original_contracts

    def test_compatibility_report_rejects_generated_target_contract_schema_evolution_without_source_parse(
        self,
    ) -> None:
        original_schema_version = runtime_target_contracts.SCHEMA_VERSION
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

        try:
            runtime_target_contracts.SCHEMA_VERSION = 2
            with tempfile.TemporaryDirectory(suffix=".cglb") as temp_dir:
                package_dir = Path(temp_dir)
                self._write_valid_package(package_dir)
                source_path = package_dir / "source" / "invalid.cgl"
                source_path.parent.mkdir()
                source_path.write_text(
                    "runtime must not parse CrossGL source for evolved "
                    "generated target contracts\n",
                    encoding="utf-8",
                )

                with mock.patch.object(Path, "read_text", guarded_read_text):
                    with mock.patch.object(Path, "read_bytes", guarded_read_bytes):
                        report = read_compatibility_report(
                            package_dir,
                            loader_target="metal",
                        )
                        selection = select_runtime_artifact(report, target="metal")

                summary = report.to_summary()

                self.assertFalse(report.compatible)
                self.assertEqual(report.status, "unsupported-version")
                self.assertIsNone(report.target_contract)
                self.assertEqual(report.required_artifacts, ())
                self.assertFalse(selection.selected)
                self.assertIsNone(selection.artifact)
                self.assertFalse(selection.source_parsing_required)
                self.assertNotIn(
                    "package.target.unsupported",
                    [diagnostic.code for diagnostic in report.reject_reasons],
                )
                self.assertEqual(
                    summary["rejectReasons"],
                    [
                        {
                            "severity": "error",
                            "code": "package.target_contract.schema_incompatible",
                            "message": (
                                "runtime generated package target contract "
                                "schemaVersion is not supported by this runtime"
                            ),
                            "document": "runtime.package_target_contracts",
                            "path": "SCHEMA_VERSION",
                            "expected": 1,
                            "actual": 2,
                        }
                    ],
                )
                self.assertEqual(
                    summary["packageArtifactRequirementsStatus"]["reason"],
                    "package.target_contract.schema_incompatible",
                )
                self.assertEqual(list(package_dir.rglob("*.cgl")), [source_path])
        finally:
            runtime_target_contracts.SCHEMA_VERSION = original_schema_version

    def test_reads_directx_source_package_contract_without_source_parse(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory(suffix=".cglb") as temp_dir:
            package_dir = Path(temp_dir)
            self._write_valid_package(package_dir, target="directx")
            (package_dir / "source").mkdir()
            (package_dir / "source" / "invalid.cgl").write_text(
                "runtime must not parse CrossGL source from packages\n",
                encoding="utf-8",
            )

            package = read_package(package_dir)
            report = package.compatibility_report(loader_target="directx")
            summary = report.to_summary()

            self.assertEqual(package.module, "RuntimeReaderFixture")
            self.assertEqual(package.target, "directx")
            self.assertEqual(package.native_binary_status, "planned")
            self.assertEqual(package.target_package_mode(), ("directx", "source"))
            self.assertEqual(
                package.required_target_artifacts(),
                ("backendSource", "nativeBinary"),
            )
            self.assertEqual(
                report.required_artifacts,
                ("backendSource", "nativeBinary"),
            )
            self.assertTrue(report.compatible, summary["diagnostics"])
            self.assertFalse(report.source_parsing_required)
            self.assertEqual(summary["reflection"]["entryPointCount"], 1)
            self.assertEqual(summary["reflection"]["resourceBindingCount"], 1)
            self.assertEqual(summary["reflection"]["targetResourceBindingCount"], 1)

            backend_source = package.require_existing_artifact("backendSource")
            native_binary = package.require_artifact("nativeBinary")
            self.assertEqual(
                backend_source.package_path,
                "backend/directx/RuntimeReaderFixture.hlsl",
            )
            self.assertEqual(
                native_binary.package_path,
                "backend/directx/RuntimeReaderFixture.dxil",
            )
            self.assertIn("generated directx source", backend_source.read_text())
            self.assertTrue(native_binary.exists)
            self.assertEqual(package.runtime_artifact(), backend_source)
            with self.assertRaisesRegex(
                PackageReadError,
                "native runtime artifact is only planned for target directx",
            ):
                package.runtime_artifact("native")

            entry_point = package.require_entry_point("compute", "main")
            self.assertEqual(entry_point["backendName"], "runtime_reader_main")
            self.assertEqual(
                package.require_entry_point("compute", "runtime_reader_main")[
                    "sourceName"
                ],
                "main",
            )
            resource = package.require_resource_binding("compute", "OutputBuffer")
            self.assertEqual(resource["binding"], 0)
            self.assertEqual(resource["type"], "float4")
            target_resource = package.require_target_resource_binding(
                "compute",
                "OutputBuffer",
                entry_point="runtime_reader_main",
            )
            self.assertEqual(target_resource["hlslType"], "RWStructuredBuffer<float4>")
            self.assertEqual(target_resource["bindingClass"], "uav")

    def test_reads_descriptor_array_binding_metadata_without_source_parse(self) -> None:
        with tempfile.TemporaryDirectory(suffix=".cglb") as temp_dir:
            package_dir = Path(temp_dir)
            self._write_valid_package(package_dir, target="directx")
            reflection_path = package_dir / "reflection.json"
            reflection = json.loads(reflection_path.read_text(encoding="utf-8"))
            array_dimensions = [
                {"kind": "fixed", "source": "3", "elementCount": 3},
                {"kind": "fixed", "source": "2", "elementCount": 2},
            ]
            reflection["resources"][0].update(
                {
                    "type": "StructuredBuffer<float4>[3][2]",
                    "arrayDimensions": array_dimensions,
                    "arrayElementCount": 6,
                    "set": 4,
                    "binding": 5,
                }
            )
            reflection["targetResourceBindings"][0].update(
                {
                    "sourceType": "StructuredBuffer<float4>[3][2]",
                    "arrayDimensions": array_dimensions,
                    "arrayElementCount": 6,
                    "abi": {"space": 1, "register": "u5"},
                    "bindingClass": "uav",
                    "descriptorType": "UAV",
                    "hlslType": "RWStructuredBuffer<float4>",
                }
            )
            self._write_json(reflection_path, reflection)
            source_path = package_dir / "source" / "invalid.cgl"
            source_path.parent.mkdir()
            source_path.write_text(
                "descriptor array metadata must come from reflection\n",
                encoding="utf-8",
            )

            with self._guard_crossgl_source_reads():
                package = read_package(package_dir)
                report = package.compatibility_report(loader_target="directx")

            summary = report.to_summary()
            resource = package.require_resource_binding("compute", "OutputBuffer")
            target_resource = package.require_target_resource_binding(
                "compute",
                "OutputBuffer",
                entry_point="runtime_reader_main",
            )

            self.assertTrue(report.compatible, summary["diagnostics"])
            self.assertFalse(report.source_parsing_required)
            self.assertEqual(resource["arrayDimensions"], array_dimensions)
            self.assertEqual(resource["arrayElementCount"], 6)
            self.assertEqual(resource["set"], 4)
            self.assertEqual(resource["binding"], 5)
            self.assertEqual(target_resource["arrayDimensions"], array_dimensions)
            self.assertEqual(target_resource["arrayElementCount"], 6)
            self.assertEqual(target_resource["abi"], {"space": 1, "register": "u5"})
            self.assertEqual(target_resource["bindingClass"], "uav")
            self.assertEqual(target_resource["descriptorType"], "UAV")
            self.assertEqual(list(package_dir.rglob("*.cgl")), [source_path])

    def test_reads_workgroup_size_metadata_without_source_parse(self) -> None:
        with tempfile.TemporaryDirectory(suffix=".cglb") as temp_dir:
            package_dir = Path(temp_dir)
            self._write_valid_package(package_dir)
            reflection_path = package_dir / "reflection.json"
            reflection = json.loads(reflection_path.read_text(encoding="utf-8"))
            workgroup_size = {
                "stage": "compute",
                "entryPoint": "runtime_reader_main",
                "x": "8",
                "y": "2",
                "z": "1",
                "sourceX": "TILE_SIZE",
                "sourceY": "2",
                "sourceZ": "1",
            }
            reflection["workgroupSizes"] = [workgroup_size]
            self._write_json(reflection_path, reflection)
            source_path = package_dir / "source" / "invalid.cgl"
            source_path.parent.mkdir()
            source_path.write_text(
                "workgroup reflection lookup must not parse source\n",
                encoding="utf-8",
            )

            with self._guard_crossgl_source_reads():
                package = read_package(package_dir)
                report = package.compatibility_report(loader_target="metal")

            summary = report.to_summary()

            self.assertEqual(package.workgroup_sizes, (workgroup_size,))
            self.assertEqual(
                package.workgroup_size("compute", "main"),
                workgroup_size,
            )
            self.assertEqual(
                package.workgroup_size("compute", "runtime_reader_main"),
                workgroup_size,
            )
            self.assertEqual(
                report.require_workgroup_size("compute", "main"),
                workgroup_size,
            )
            self.assertEqual(
                summary["reflection"]["workgroupSizeCount"],
                1,
            )
            self.assertEqual(
                summary["workgroupSizes"],
                {
                    "schemaVersion": 1,
                    "metadataOnly": True,
                    "declared": True,
                    "available": True,
                    "recordCount": 1,
                    "malformedRecordCount": 0,
                    "records": [workgroup_size],
                },
            )
            self.assertEqual(list(package_dir.rglob("*.cgl")), [source_path])

    def test_workgroup_size_metadata_falls_back_for_legacy_reflection(self) -> None:
        with tempfile.TemporaryDirectory(suffix=".cglb") as temp_dir:
            package_dir = Path(temp_dir)
            self._write_valid_package(package_dir)

            package = read_package(package_dir)
            report = package.compatibility_report(loader_target="metal")
            summary = report.to_summary()

            self.assertEqual(package.workgroup_sizes, ())
            self.assertIsNone(package.workgroup_size("compute", "main"))
            self.assertEqual(report.workgroup_sizes, ())
            self.assertIsNone(report.workgroup_size("compute", "main"))
            self.assertEqual(summary["reflection"]["workgroupSizeCount"], 0)
            self.assertFalse(summary["reflection"]["workgroupSizesAvailable"])
            self.assertEqual(summary["workgroupSizes"]["declared"], False)
            self.assertFalse(summary["workgroupSizes"]["available"])
            with self.assertRaisesRegex(
                PackageReadError,
                "missing reflection workgroup size",
            ):
                package.require_workgroup_size("compute", "main")

    def test_reads_metadata_and_artifacts_without_source_parse(self) -> None:
        with tempfile.TemporaryDirectory(suffix=".cglb") as temp_dir:
            package_dir = Path(temp_dir)
            self._write_valid_package(package_dir)
            (package_dir / "source").mkdir()
            (package_dir / "source" / "invalid.cgl").write_text(
                "this is not CrossGL source\n",
                encoding="utf-8",
            )

            package = read_package(package_dir)

            self.assertEqual(package.module, "RuntimeReaderFixture")
            self.assertEqual(package.target, "metal")
            self.assertEqual(package.package_mode, "source")
            self.assertEqual(package.target_package_mode(), ("metal", "source"))
            self.assertEqual(
                [artifact.name for artifact in package.artifacts],
                ["backendSource", "intermediate", "nativeBinary"],
            )
            backend_source = package.artifact("backendSource")
            native_binary = package.artifact("nativeBinary")
            self.assertIsNotNone(backend_source)
            self.assertIsNotNone(native_binary)
            self.assertEqual(
                backend_source.package_path,
                "backend/metal/RuntimeReaderFixture.metal",
            )
            self.assertTrue(native_binary.exists)
            self.assertEqual(
                package.reflection["entryPoints"][0]["backendName"],
                "runtime_reader_main",
            )
            self.assertEqual(
                package.entry_point("compute", "main")["backendName"],
                "runtime_reader_main",
            )
            self.assertEqual(
                package.entry_point("compute", "runtime_reader_main")["sourceName"],
                "main",
            )
            self.assertEqual(
                package.resource_binding("compute", "OutputBuffer")["binding"],
                0,
            )
            self.assertEqual(package.to_summary()["diagnosticCount"], 1)

    def test_accepts_optional_graphics_abi_manifest_artifact_without_requiring_it(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory(suffix=".cglb") as temp_dir:
            package_dir = Path(temp_dir)
            self._write_valid_package(package_dir)
            manifest_path = package_dir / "manifest.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            graphics_abi_path = "backend/metal/RuntimeReaderFixture.graphics-abi.json"
            self._write_json(
                package_dir / graphics_abi_path,
                {
                    "schemaVersion": 1,
                    "abiVersion": "graphics-abi-v0",
                    "module": "RuntimeReaderFixture",
                    "entryPoints": [
                        {
                            "stage": "compute",
                            "name": "runtime_reader_main",
                        }
                    ],
                    "resources": [
                        {
                            "stage": "compute",
                            "name": "OutputBuffer",
                        }
                    ],
                    "abiRecords": [
                        {
                            "stage": "compute",
                            "name": "OutputBuffer",
                            "bindingClass": "uav",
                        }
                    ],
                    "targetResourceBindings": [
                        {
                            "stage": "compute",
                            "name": "OutputBuffer",
                        }
                    ],
                },
            )
            manifest["artifacts"]["graphicsAbi"] = graphics_abi_path
            self._write_json(manifest_path, manifest)

            package = read_package(package_dir)
            report = package.compatibility_report(loader_target="metal")
            graphics_abi = package.require_graphics_abi()

            self.assertTrue(report.compatible, report.to_summary()["diagnostics"])
            self.assertEqual(
                package.graphics_abi_artifact().package_path,
                graphics_abi_path,
            )
            self.assertEqual(package.graphics_abi_record(), graphics_abi)
            self.assertEqual(graphics_abi.module, "RuntimeReaderFixture")
            self.assertEqual(graphics_abi.schema_version, 1)
            self.assertEqual(graphics_abi.abi_version, "graphics-abi-v0")
            self.assertEqual(graphics_abi.stage_count, 1)
            self.assertEqual(graphics_abi.stage_record_counts, {"compute": 4})
            self.assertEqual(graphics_abi.resource_count, 3)
            self.assertEqual(
                graphics_abi.resource_record_counts,
                {"resources": 1, "abiRecords": 1, "targetResourceBindings": 1},
            )
            self.assertEqual(
                package.to_summary()["graphicsAbi"],
                {
                    "declared": True,
                    "exists": True,
                    "path": graphics_abi_path,
                    "record": graphics_abi.to_summary(),
                },
            )
            self.assertNotIn("graphicsAbi", package.required_target_artifacts())
            self.assertNotIn("graphicsAbi", report.required_artifacts)

    def test_reports_absent_optional_graphics_abi(self) -> None:
        with tempfile.TemporaryDirectory(suffix=".cglb") as temp_dir:
            package_dir = Path(temp_dir)
            self._write_valid_package(package_dir)

            package = read_package(package_dir)

            self.assertIsNone(package.graphics_abi_artifact())
            self.assertIsNone(package.graphics_abi_record())
            self.assertEqual(
                package.to_summary()["graphicsAbi"],
                {
                    "declared": False,
                    "exists": False,
                    "path": None,
                    "record": None,
                },
            )
            with self.assertRaisesRegex(
                PackageReadError,
                "graphics ABI artifact is not declared",
            ):
                package.require_graphics_abi()

    def test_declared_missing_graphics_abi_uses_artifact_missing_error(self) -> None:
        with tempfile.TemporaryDirectory(suffix=".cglb") as temp_dir:
            package_dir = Path(temp_dir)
            self._write_valid_package(package_dir)
            manifest_path = package_dir / "manifest.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["artifacts"]["graphicsAbi"] = (
                "backend/metal/missing.graphics-abi.json"
            )
            self._write_json(manifest_path, manifest)

            package = read_package(package_dir)

            self.assertIsNone(package.graphics_abi_record())
            self.assertEqual(
                package.to_summary()["graphicsAbi"],
                {
                    "declared": True,
                    "exists": False,
                    "path": "backend/metal/missing.graphics-abi.json",
                    "record": None,
                },
            )
            with self.assertRaisesRegex(
                PackageReadError,
                "manifest artifact is missing on disk: graphicsAbi "
                r"\(backend/metal/missing\.graphics-abi\.json\)",
            ):
                package.require_graphics_abi()

    def test_rejects_malformed_graphics_abi_json(self) -> None:
        with tempfile.TemporaryDirectory(suffix=".cglb") as temp_dir:
            package_dir = Path(temp_dir)
            self._write_valid_package(package_dir)
            manifest_path = package_dir / "manifest.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            graphics_abi_path = "backend/metal/RuntimeReaderFixture.graphics-abi.json"
            (package_dir / graphics_abi_path).write_text(
                "{not-json}\n",
                encoding="utf-8",
            )
            manifest["artifacts"]["graphicsAbi"] = graphics_abi_path
            self._write_json(manifest_path, manifest)

            with self.assertRaisesRegex(
                PackageReadError,
                "invalid JSON in graphics ABI",
            ):
                read_package(package_dir)

    def test_runtime_artifact_auto_uses_native_only_when_status_is_ready(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory(suffix=".cglb") as temp_dir:
            package_dir = Path(temp_dir)
            self._write_valid_package(package_dir, native_status="emitted")

            package = read_package(package_dir)

            self.assertEqual(package.package_mode, "native")
            self.assertEqual(package.target_package_mode(), ("metal", "native"))
            self.assertEqual(
                package.runtime_artifact(),
                package.require_existing_artifact("nativeBinary"),
            )
            self.assertEqual(
                package.runtime_artifact("native"),
                package.require_existing_artifact("nativeBinary"),
            )
            self.assertEqual(
                package.runtime_artifact("source"),
                package.require_existing_artifact("backendSource"),
            )

    def test_runtime_artifact_reports_planned_native_binary(self) -> None:
        with tempfile.TemporaryDirectory(suffix=".cglb") as temp_dir:
            package_dir = Path(temp_dir)
            self._write_valid_package(package_dir, native_status="planned")

            package = read_package(package_dir)

            self.assertEqual(package.package_mode, "source")
            self.assertEqual(
                package.runtime_artifact(),
                package.require_existing_artifact("backendSource"),
            )
            with self.assertRaisesRegex(
                PackageReadError,
                "native runtime artifact is only planned for target metal: "
                "nativeBinaryStatus=planned",
            ):
                package.runtime_artifact("native")

    def test_runtime_artifact_reports_missing_native_binary_file(self) -> None:
        with tempfile.TemporaryDirectory(suffix=".cglb") as temp_dir:
            package_dir = Path(temp_dir)
            self._write_valid_package(package_dir, native_status="validated")
            (
                package_dir / "backend" / "metal" / "RuntimeReaderFixture.metallib"
            ).unlink()

            package = read_package(package_dir)

            with self.assertRaisesRegex(
                PackageReadError,
                "manifest artifact is missing on disk: nativeBinary "
                r"\(backend/metal/RuntimeReaderFixture\.metallib\)",
            ):
                package.runtime_artifact()

    def test_compatibility_report_exposes_runtime_contract(self) -> None:
        with tempfile.TemporaryDirectory(suffix=".cglb") as temp_dir:
            package_dir = Path(temp_dir)
            self._write_valid_package(package_dir)
            (package_dir / "source").mkdir()
            (package_dir / "source" / "invalid.cgl").write_text(
                "runtime compatibility must not parse this source\n",
                encoding="utf-8",
            )

            package = read_package(package_dir)
            report = package.compatibility_report()
            summary = report.to_summary()
            legacy_requirements_note = {
                "severity": "note",
                "code": "package.artifact_requirements.legacy_v0_fallback",
                "message": (
                    "manifest.packageArtifactRequirements is missing; "
                    "using generated legacy v0 target contract as report-only "
                    "compatibility metadata"
                ),
                "document": "manifest",
                "path": "packageArtifactRequirements",
                "expected": "recorded package artifact requirements",
                "actual": "legacy-v0-target-contract",
            }

            self.assertTrue(report.compatible, summary["diagnostics"])
            self.assertEqual(report.status, "compatible")
            self.assertIs(package.require_runtime_compatible(), package)
            self.assertEqual(
                package.required_target_artifacts(),
                ("backendSource", "intermediate", "nativeBinary"),
            )
            self.assertEqual(
                report.required_artifacts, package.required_target_artifacts()
            )
            self.assertFalse(report.source_parsing_required)
            self.assertEqual(report.compiler_name, "CrossGL-Compiler")
            self.assertEqual(report.compiler_version, "test")
            self.assertEqual(report.manifest_schema_version, 1)
            self.assertEqual(report.reflection_schema_version, 1)
            self.assertEqual(report.diagnostics_schema_version, 1)
            self.assertEqual(summary["compiler"]["compatible"], True)
            self.assertEqual(summary["packageFormat"], "directory")
            self.assertEqual(summary["packageVersion"], 1)
            self.assertEqual(summary["status"], "compatible")
            self.assertEqual(report.available_targets, ("metal",))
            self.assertEqual(summary["availableTargets"], ["metal"])
            self.assertEqual(
                summary["targetAvailability"],
                {
                    "manifestTarget": "metal",
                    "reflectionTarget": "metal",
                    "targetResourceBindingTargets": ["metal"],
                    "targetFeatureTargets": ["metal"],
                    "availableTargets": ["metal"],
                },
            )
            self.assertEqual(summary["schemas"]["manifest"]["compatible"], True)
            self.assertEqual(summary["targetContract"]["target"], "metal")
            self.assertEqual(summary["targetContract"]["packageMode"], "native")
            self.assertEqual(
                summary["targetContract"]["requirementsSource"],
                "legacy-v0-target-contract",
            )
            self.assertTrue(summary["targetContract"]["reportOnly"])
            self.assertEqual(
                summary["targetContract"]["compatibilityScope"],
                "legacy/report-only",
            )
            self.assertEqual(summary["admission"]["decision"], "accepted")
            self.assertEqual(
                summary["admission"]["target"]["category"],
                "target-accepted",
            )
            self.assertFalse(summary["admission"]["requirements"]["declared"])
            self.assertFalse(summary["admission"]["requirements"]["recorded"])
            self.assertTrue(summary["admission"]["requirements"]["legacyInferred"])
            self.assertEqual(
                summary["admission"]["requirements"]["requirementsSource"],
                "legacy-v0-target-contract",
            )
            self.assertEqual(
                summary["admission"]["requirements"]["sourceKind"],
                "legacy-generated",
            )
            self.assertEqual(
                summary["admission"]["requirements"]["compatibilityKind"],
                "legacy-generated-compatible",
            )
            self.assertTrue(summary["admission"]["requirements"]["reportOnly"])
            self.assertEqual(
                summary["admission"]["requirements"]["compatibilityScope"],
                "legacy/report-only",
            )
            self.assertIsNone(summary["admission"]["requirements"]["reason"])
            self.assertTrue(
                summary["admission"]["requirements"]["legacyGeneratedRequirements"][
                    "compatibilityOnly"
                ]
            )
            self.assertTrue(
                summary["admission"]["requirements"]["legacyGeneratedRequirements"][
                    "reportOnly"
                ]
            )
            self.assertEqual(
                summary["admission"]["requirements"]["legacyGeneratedRequirements"][
                    "compatibilityScope"
                ],
                "legacy/report-only",
            )
            self.assertEqual(
                summary["packageArtifactRequirementsStatus"],
                summary["admission"]["requirements"],
            )
            self.assertEqual(
                summary["admission"]["requirements"]["diagnostics"],
                [legacy_requirements_note],
            )
            self.assertTrue(summary["admission"]["requirements"]["resolved"])
            self.assertEqual(
                summary["requiredArtifacts"],
                ["backendSource", "intermediate", "nativeBinary"],
            )
            self.assertEqual(
                [artifact["name"] for artifact in summary["availableArtifacts"]],
                ["backendSource", "intermediate", "nativeBinary"],
            )
            self.assertEqual(summary["reflection"]["entryPointCount"], 1)
            self.assertEqual(summary["reflection"]["resourceBindingCount"], 1)
            self.assertTrue(summary["reflection"]["resourceBindingsAvailable"])
            self.assertEqual(summary["diagnosticsMetadata"]["diagnosticCount"], 1)
            self.assertEqual(summary["diagnosticsMetadata"]["maxSeverity"], "note")
            self.assertEqual(
                summary["diagnosticSummary"],
                {
                    "status": "compatible",
                    "compatibilityDiagnosticCount": 1,
                    "rejectCount": 0,
                    "skipCount": 0,
                    "bySeverity": {"note": 1},
                    "packageDiagnosticCount": 1,
                    "packageMaxSeverity": "note",
                },
            )
            self.assertTrue(summary["artifactAvailability"]["source"]["available"])
            self.assertTrue(summary["artifactAvailability"]["native"]["usable"])
            self.assertEqual(summary["debugMetadata"]["declared"], False)
            self.assertEqual(summary["debugMetadata"]["compatible"], None)
            self.assertEqual(summary["missingArtifacts"], [])
            self.assertEqual(summary["rejectReasons"], [])
            self.assertEqual(summary["skipReasons"], [])
            self.assertEqual(summary["diagnostics"], [legacy_requirements_note])

    def test_compatibility_report_uses_recorded_package_artifact_requirements(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory(suffix=".cglb") as temp_dir:
            package_dir = Path(temp_dir)
            self._write_valid_package(
                package_dir,
                package_artifact_requirements={
                    "target": "metal",
                    "packageMode": "native",
                    "requiredPathArtifacts": [
                        "backendSource",
                        "intermediate",
                        "nativeBinary",
                    ],
                    "requiresNativeBinaryStatus": False,
                    "allowsPlannedNativeBinary": False,
                    "allowsPlannedNativeSourceEvidence": False,
                    "evidenceIds": [
                        "target-legalization.v1.metal.package-artifact.required.backendSource",
                        "target-legalization.v1.metal.package-artifact.required.intermediate",
                        "target-legalization.v1.metal.package-artifact.required.nativeBinary",
                    ],
                },
            )

            package = read_package(package_dir)
            report = package.compatibility_report(loader_target="metal")
            selection = select_runtime_artifact(report, target="metal")
            summary = report.to_summary()

            self.assertTrue(report.compatible, summary["diagnostics"])
            self.assertEqual(
                package.required_target_artifacts(),
                ("backendSource", "intermediate", "nativeBinary"),
            )
            self.assertEqual(
                report.required_artifacts,
                ("backendSource", "intermediate", "nativeBinary"),
            )
            self.assertEqual(selection.require_selected().name, "nativeBinary")
            self.assertEqual(report.target_contract.requirements_source, "manifest")
            self.assertNotEqual(
                report.target_contract.requirements_source,
                "legacy-v0-target-contract",
            )
            self.assertEqual(
                summary["packageArtifactRequirements"]["requiredPathArtifacts"],
                ["backendSource", "intermediate", "nativeBinary"],
            )
            self.assertEqual(
                summary["packageArtifactRequirements"]["requirementsSource"],
                "manifest",
            )
            self.assertFalse(summary["packageArtifactRequirements"]["reportOnly"])
            self.assertEqual(
                summary["packageArtifactRequirements"]["compatibilityScope"],
                "recorded-package-metadata",
            )
            self.assertNotEqual(
                summary["packageArtifactRequirements"]["requirementsSource"],
                "legacy-v0-target-contract",
            )
            self.assertTrue(summary["admission"]["requirements"]["declared"])
            self.assertTrue(summary["admission"]["requirements"]["recorded"])
            self.assertFalse(summary["admission"]["requirements"]["legacyInferred"])
            self.assertEqual(
                summary["admission"]["requirements"]["requirementsSource"],
                "manifest",
            )
            self.assertEqual(
                summary["admission"]["requirements"]["sourceKind"],
                "recorded",
            )
            self.assertEqual(
                summary["admission"]["requirements"]["compatibilityKind"],
                "recorded",
            )
            self.assertFalse(summary["admission"]["requirements"]["reportOnly"])
            self.assertEqual(
                summary["admission"]["requirements"]["compatibilityScope"],
                "recorded-package-metadata",
            )
            self.assertIsNone(summary["admission"]["requirements"]["reason"])
            self.assertFalse(
                summary["admission"]["requirements"]["legacyGeneratedRequirements"][
                    "compatibilityOnly"
                ]
            )
            self.assertFalse(
                summary["admission"]["requirements"]["legacyGeneratedRequirements"][
                    "reportOnly"
                ]
            )
            self.assertIsNone(
                summary["admission"]["requirements"]["legacyGeneratedRequirements"][
                    "compatibilityScope"
                ]
            )
            self.assertTrue(
                summary["admission"]["requirements"]["recordedRequirements"]["valid"]
            )
            self.assertIsNone(
                summary["admission"]["requirements"]["recordedRequirements"]["reason"]
            )
            self.assertEqual(
                summary["packageArtifactRequirementsStatus"],
                summary["admission"]["requirements"],
            )
            self.assertNotEqual(
                summary["admission"]["requirements"]["requirementsSource"],
                "legacy-v0-target-contract",
            )
            self.assertEqual(
                summary["admission"]["requirements"]["requiredPathArtifacts"],
                ["backendSource", "intermediate", "nativeBinary"],
            )
            self.assertEqual(summary["missingArtifacts"], [])

    def test_compatibility_report_rejects_target_legalization_package_mode_drift_for_directory_and_zip(
        self,
    ) -> None:
        for package_format in ("directory", "zip"):
            with self.subTest(package_format=package_format):
                with tempfile.TemporaryDirectory(suffix=".cglb") as temp_dir:
                    temp_root = Path(temp_dir)
                    package_dir = temp_root / "RuntimeReaderFixture.cglb"
                    package_dir.mkdir()
                    evidence_ids = [
                        "target-legalization.v1.metal.package-artifact.required.backendSource",
                        "target-legalization.v1.metal.package-artifact.required.intermediate",
                        "target-legalization.v1.metal.package-artifact.required.nativeBinary",
                    ]
                    self._write_valid_package(
                        package_dir,
                        emit_debug_metadata=True,
                        package_artifact_requirements={
                            "target": "metal",
                            "packageMode": "native",
                            "requiredPathArtifacts": [
                                "backendSource",
                                "intermediate",
                                "nativeBinary",
                            ],
                            "requiresNativeBinaryStatus": False,
                            "allowsPlannedNativeBinary": False,
                            "allowsPlannedNativeSourceEvidence": False,
                            "evidenceIds": evidence_ids,
                        },
                    )
                    source_path = package_dir / "source" / "invalid.cgl"
                    source_path.parent.mkdir()
                    source_path.write_text(
                        "target legalization drift must not parse source\n",
                        encoding="utf-8",
                    )
                    debug_path = package_dir / "ir" / "debug-metadata.json"
                    debug_metadata = json.loads(debug_path.read_text(encoding="utf-8"))
                    target_decision = debug_metadata["targetDecision"]
                    target_decision["selectedTargetPackageMode"] = "source-package"
                    target_decision["selectedTargetPackageBuildSupported"] = True
                    target_decision["selectedTargetLegalizationCoreEvidenceIds"] = [
                        "target-legalization.v1.metal.decision"
                    ]
                    target_decision["packageArtifactRequirementEvidenceIds"] = (
                        evidence_ids
                    )
                    self._write_json(debug_path, debug_metadata)

                    if package_format == "zip":
                        zip_path = temp_root / "RuntimeReaderFixture.zip.cglb"
                        self._write_zip_package(
                            package_dir,
                            zip_path,
                            prefix=zip_path.name,
                        )
                        package_path = zip_path
                        guard = self._guard_zip_crossgl_member_reads()
                    else:
                        package_path = package_dir
                        guard = self._guard_crossgl_source_reads()

                    with guard:
                        report = read_compatibility_report(
                            package_path,
                            loader_target="metal",
                        )

                    summary = report.to_summary()
                    reject_codes = [
                        diagnostic.code for diagnostic in report.reject_reasons
                    ]

                    self.assertFalse(report.compatible)
                    self.assertEqual(summary["packageFormat"], package_format)
                    self.assertIn(
                        (
                            "package.target_legalization_evidence."
                            "debug_metadata_package_mode_mismatch"
                        ),
                        reject_codes,
                    )
                    self.assertEqual(
                        summary["targetLegalizationEvidence"]["health"],
                        "drift",
                    )
                    self.assertFalse(
                        summary["targetLegalizationEvidence"]["checks"][
                            "debugMetadataPackageModeMatchesRequirements"
                        ]
                    )
                    self.assertFalse(summary["sourceParsingRequired"])

    def test_compatibility_report_records_manifest_tool_requirements_for_directory_and_zip(
        self,
    ) -> None:
        for package_format in ("directory", "zip"):
            with self.subTest(package_format=package_format):
                with tempfile.TemporaryDirectory(suffix=".cglb") as temp_dir:
                    temp_root = Path(temp_dir)
                    package_dir = temp_root / "RuntimeReaderFixture.cglb"
                    package_dir.mkdir()
                    evidence_ids = [
                        "target-legalization.v1.metal.package-artifact.required.backendSource",
                        "target-legalization.v1.metal.package-artifact.required.intermediate",
                        "target-legalization.v1.metal.package-artifact.required.nativeBinary",
                    ]
                    required_tool_ids = [
                        "metal.toolchain.xcrun-metal",
                        "metal.toolchain.xcrun-metallib",
                    ]
                    tool_evidence_ids = [
                        "target-legalization.v1.metal.tool-requirements.present",
                        "target-legalization.v1.metal.tool-requirement.required.toolchain.xcrun-metal",
                        "target-legalization.v1.metal.tool-requirement.required.toolchain.xcrun-metallib",
                    ]
                    tool_requirements = {
                        "target": "metal",
                        "packageMode": "native",
                        "requiredToolCount": 2,
                        "missingToolCount": 0,
                        "requiredToolIds": required_tool_ids,
                        "missingToolIds": [],
                        "optionalNativeToolMissing": False,
                        "optionalNativeToolStatus": "not-required",
                        "toolRequirementEvidenceIds": tool_evidence_ids,
                    }
                    self._write_valid_package(
                        package_dir,
                        emit_debug_metadata=True,
                        package_artifact_requirements={
                            "target": "metal",
                            "packageMode": "native",
                            "requiredPathArtifacts": [
                                "backendSource",
                                "intermediate",
                                "nativeBinary",
                            ],
                            "requiresNativeBinaryStatus": False,
                            "allowsPlannedNativeBinary": False,
                            "allowsPlannedNativeSourceEvidence": False,
                            "evidenceIds": evidence_ids,
                        },
                    )
                    manifest_path = package_dir / "manifest.json"
                    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
                    manifest["targetLegalizationToolRequirements"] = tool_requirements
                    manifest["artifacts"]["targetExplanation"] = (
                        "ir/target-explanation.json"
                    )
                    self._write_json(manifest_path, manifest)
                    source_path = package_dir / "source" / "invalid.cgl"
                    source_path.parent.mkdir()
                    source_path.write_text(
                        "manifest tool requirements must not parse source\n",
                        encoding="utf-8",
                    )

                    debug_path = package_dir / "ir" / "debug-metadata.json"
                    debug_metadata = json.loads(debug_path.read_text(encoding="utf-8"))
                    target_decision = debug_metadata["targetDecision"]
                    target_decision["selectedTargetPackageBuildSupported"] = True
                    target_decision["selectedTargetLegalizationCoreEvidenceIds"] = [
                        "target-legalization.v1.metal.decision"
                    ]
                    target_decision["packageArtifactRequirementEvidenceIds"] = (
                        evidence_ids
                    )
                    target_decision["selectedTargetRequiredToolCount"] = 2
                    target_decision["selectedTargetMissingToolCount"] = 0
                    target_decision["selectedTargetRequiredToolIds"] = required_tool_ids
                    target_decision["selectedTargetMissingToolIds"] = []
                    target_decision["selectedTargetOptionalNativeToolMissing"] = False
                    target_decision["selectedTargetOptionalNativeToolStatus"] = (
                        "not-required"
                    )
                    target_decision["selectedTargetToolRequirementEvidenceIds"] = (
                        tool_evidence_ids
                    )
                    self._write_json(debug_path, debug_metadata)
                    self._write_json(
                        package_dir / "ir" / "target-explanation.json",
                        {
                            "schemaVersion": 1,
                            "module": "RuntimeReaderFixture",
                            "defaultTarget": "metal",
                            "targets": [
                                {
                                    "target": "metal",
                                    "packageMode": "native",
                                    "packageBuildSupported": True,
                                    "legalizationCoreEvidenceIds": [
                                        "target-legalization.v1.metal.decision"
                                    ],
                                    "packageArtifactRequirementEvidenceIds": (
                                        evidence_ids
                                    ),
                                    **tool_requirements,
                                }
                            ],
                        },
                    )

                    if package_format == "zip":
                        zip_path = temp_root / "RuntimeReaderFixture.zip.cglb"
                        self._write_zip_package(
                            package_dir,
                            zip_path,
                            prefix=zip_path.name,
                        )
                        package_path = zip_path
                        guard = self._guard_zip_crossgl_member_reads()
                    else:
                        package_path = package_dir
                        guard = self._guard_crossgl_source_reads()

                    with guard:
                        package = read_package(package_path)
                        package_summary = package.to_summary()
                        report = read_compatibility_report(
                            package_path,
                            loader_target="metal",
                        )

                    summary = report.to_summary()
                    evidence = summary["targetLegalizationEvidence"]
                    checks = evidence["checks"]

                    self.assertEqual(
                        package_summary["targetLegalizationEvidence"],
                        evidence,
                    )
                    self.assertEqual(
                        package_summary["targetLegalizationToolRequirements"],
                        {"present": True, **tool_requirements},
                    )
                    self.assertEqual(
                        summary["targetLegalizationToolRequirements"],
                        {"present": True, **tool_requirements},
                    )
                    self.assertTrue(report.compatible, summary["diagnostics"])
                    self.assertEqual(summary["packageFormat"], package_format)
                    self.assertEqual(evidence["health"], "ok")
                    self.assertEqual(evidence["packageMode"], "native")
                    self.assertEqual(
                        evidence["manifestToolRequirements"],
                        {
                            "present": True,
                            **tool_requirements,
                        },
                    )
                    self.assertEqual(
                        evidence["debugMetadata"]["requiredToolIds"],
                        required_tool_ids,
                    )
                    self.assertEqual(
                        evidence["targetExplanation"]["toolRequirementEvidenceIds"],
                        tool_evidence_ids,
                    )
                    self.assertTrue(
                        checks["manifestToolRequirementsTargetMatchesPackage"]
                    )
                    self.assertTrue(
                        checks["manifestToolRequirementsPackageModeMatchesRequirements"]
                    )
                    self.assertTrue(checks["manifestToolRequirementEvidenceIdsPresent"])
                    self.assertTrue(
                        checks["debugMetadataToolRequirementsMatchManifest"]
                    )
                    self.assertTrue(
                        checks["targetExplanationToolRequirementsMatchManifest"]
                    )
                    self.assertTrue(
                        checks["packageArtifactRequirementEvidenceIdsPresent"]
                    )
                    self.assertEqual(evidence["missingEvidence"], [])
                    self.assertFalse(summary["sourceParsingRequired"])

    def test_compatibility_report_rejects_tool_requirement_sidecar_drift_for_directory_and_zip(
        self,
    ) -> None:
        for package_format in ("directory", "zip"):
            with self.subTest(package_format=package_format):
                with tempfile.TemporaryDirectory(suffix=".cglb") as temp_dir:
                    temp_root = Path(temp_dir)
                    package_dir = temp_root / "RuntimeReaderFixture.cglb"
                    package_dir.mkdir()
                    evidence_ids = [
                        "target-legalization.v1.metal.package-artifact.required.backendSource",
                        "target-legalization.v1.metal.package-artifact.required.intermediate",
                        "target-legalization.v1.metal.package-artifact.required.nativeBinary",
                    ]
                    tool_requirements = {
                        "target": "metal",
                        "packageMode": "native",
                        "requiredToolCount": 2,
                        "missingToolCount": 0,
                        "requiredToolIds": [
                            "metal.toolchain.xcrun-metal",
                            "metal.toolchain.xcrun-metallib",
                        ],
                        "missingToolIds": [],
                        "optionalNativeToolMissing": False,
                        "optionalNativeToolStatus": "not-required",
                        "toolRequirementEvidenceIds": [
                            "target-legalization.v1.metal.tool-requirements.present",
                            "target-legalization.v1.metal.tool-requirement.required.toolchain.xcrun-metal",
                            "target-legalization.v1.metal.tool-requirement.required.toolchain.xcrun-metallib",
                        ],
                    }
                    self._write_valid_package(
                        package_dir,
                        package_artifact_requirements={
                            "target": "metal",
                            "packageMode": "native",
                            "requiredPathArtifacts": [
                                "backendSource",
                                "intermediate",
                                "nativeBinary",
                            ],
                            "requiresNativeBinaryStatus": False,
                            "allowsPlannedNativeBinary": False,
                            "allowsPlannedNativeSourceEvidence": False,
                            "evidenceIds": evidence_ids,
                        },
                    )
                    manifest_path = package_dir / "manifest.json"
                    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
                    manifest["targetLegalizationToolRequirements"] = tool_requirements
                    manifest["artifacts"]["targetExplanation"] = (
                        "ir/target-explanation.json"
                    )
                    self._write_json(manifest_path, manifest)
                    source_path = package_dir / "source" / "invalid.cgl"
                    source_path.parent.mkdir()
                    source_path.write_text(
                        "tool requirement drift must not parse source\n",
                        encoding="utf-8",
                    )
                    (package_dir / "ir").mkdir(exist_ok=True)
                    self._write_json(
                        package_dir / "ir" / "target-explanation.json",
                        {
                            "schemaVersion": 1,
                            "module": "RuntimeReaderFixture",
                            "defaultTarget": "metal",
                            "targets": [
                                {
                                    "target": "metal",
                                    "packageMode": "native",
                                    "packageBuildSupported": True,
                                    "legalizationCoreEvidenceIds": [
                                        "target-legalization.v1.metal.decision"
                                    ],
                                    "packageArtifactRequirementEvidenceIds": (
                                        evidence_ids
                                    ),
                                    "requiredToolCount": 1,
                                    "missingToolCount": 0,
                                    "requiredToolIds": ["metal.toolchain.xcrun-metal"],
                                    "missingToolIds": [],
                                    "optionalNativeToolMissing": False,
                                    "optionalNativeToolStatus": "not-required",
                                    "toolRequirementEvidenceIds": [
                                        "target-legalization.v1.metal.tool-requirements.present",
                                        "target-legalization.v1.metal.tool-requirement.required.toolchain.xcrun-metal",
                                    ],
                                }
                            ],
                        },
                    )

                    if package_format == "zip":
                        zip_path = temp_root / "RuntimeReaderFixture.zip.cglb"
                        self._write_zip_package(
                            package_dir,
                            zip_path,
                            prefix=zip_path.name,
                        )
                        package_path = zip_path
                        guard = self._guard_zip_crossgl_member_reads()
                    else:
                        package_path = package_dir
                        guard = self._guard_crossgl_source_reads()

                    with guard:
                        report = read_compatibility_report(
                            package_path,
                            loader_target="metal",
                        )

                    summary = report.to_summary()
                    reject_codes = [
                        diagnostic.code for diagnostic in report.reject_reasons
                    ]
                    evidence = summary["targetLegalizationEvidence"]

                    self.assertFalse(report.compatible)
                    self.assertEqual(summary["packageFormat"], package_format)
                    self.assertIn(
                        (
                            "package.target_legalization_evidence."
                            "target_explanation_tool_requirements_mismatch"
                        ),
                        reject_codes,
                    )
                    self.assertEqual(evidence["health"], "drift")
                    self.assertFalse(
                        evidence["checks"][
                            "targetExplanationToolRequirementsMatchManifest"
                        ]
                    )
                    self.assertFalse(summary["sourceParsingRequired"])

    def test_compatibility_report_rejects_malformed_target_legalization_evidence_for_directory_and_zip(
        self,
    ) -> None:
        for package_format in ("directory", "zip"):
            with self.subTest(package_format=package_format):
                with tempfile.TemporaryDirectory(suffix=".cglb") as temp_dir:
                    temp_root = Path(temp_dir)
                    package_dir = temp_root / "RuntimeReaderFixture.cglb"
                    package_dir.mkdir()
                    evidence_ids = [
                        "target-legalization.v1.metal.package-artifact.required.backendSource",
                        "target-legalization.v1.metal.package-artifact.required.intermediate",
                        "target-legalization.v1.metal.package-artifact.required.nativeBinary",
                    ]
                    self._write_valid_package(
                        package_dir,
                        package_artifact_requirements={
                            "target": "metal",
                            "packageMode": "native",
                            "requiredPathArtifacts": [
                                "backendSource",
                                "intermediate",
                                "nativeBinary",
                            ],
                            "requiresNativeBinaryStatus": False,
                            "allowsPlannedNativeBinary": False,
                            "allowsPlannedNativeSourceEvidence": False,
                            "evidenceIds": evidence_ids,
                        },
                    )
                    source_path = package_dir / "source" / "invalid.cgl"
                    source_path.parent.mkdir()
                    source_path.write_text(
                        "malformed target legalization evidence must stay source-free\n",
                        encoding="utf-8",
                    )
                    manifest_path = package_dir / "manifest.json"
                    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
                    manifest["artifacts"]["targetExplanation"] = (
                        "ir/target-explanation.json"
                    )
                    self._write_json(manifest_path, manifest)
                    (package_dir / "ir").mkdir(exist_ok=True)
                    self._write_json(
                        package_dir / "ir" / "target-explanation.json",
                        {
                            "schemaVersion": 1,
                            "module": "RuntimeReaderFixture",
                            "defaultTarget": "metal",
                            "targets": [
                                {
                                    "target": "metal",
                                    "packageMode": "native",
                                    "packageBuildSupported": True,
                                    "legalizationCoreEvidenceIds": [
                                        "target-legalization.v1.metal.decision"
                                    ],
                                    "packageArtifactRequirementEvidenceIds": [
                                        evidence_ids[0],
                                        "",
                                    ],
                                }
                            ],
                        },
                    )

                    if package_format == "zip":
                        zip_path = temp_root / "RuntimeReaderFixture.zip.cglb"
                        self._write_zip_package(
                            package_dir,
                            zip_path,
                            prefix=zip_path.name,
                        )
                        package_path = zip_path
                        guard = self._guard_zip_crossgl_member_reads()
                    else:
                        package_path = package_dir
                        guard = self._guard_crossgl_source_reads()

                    with guard:
                        report = read_compatibility_report(
                            package_path,
                            loader_target="metal",
                        )

                    summary = report.to_summary()
                    reject_codes = [
                        diagnostic.code for diagnostic in report.reject_reasons
                    ]

                    self.assertFalse(report.compatible)
                    self.assertEqual(summary["packageFormat"], package_format)
                    self.assertIn(
                        (
                            "package.target_legalization_evidence."
                            "target_explanation_package_artifact_requirement_"
                            "evidence_ids_entry_invalid"
                        ),
                        reject_codes,
                    )
                    self.assertEqual(
                        summary["targetLegalizationEvidence"]["health"],
                        "drift",
                    )
                    self.assertFalse(summary["sourceParsingRequired"])

    def test_package_summary_does_not_crash_on_malformed_recorded_requirements(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory(suffix=".cglb") as temp_dir:
            package_dir = Path(temp_dir)
            self._write_valid_package(
                package_dir,
                package_artifact_requirements=["not", "an", "object"],
            )
            source_path = package_dir / "source" / "invalid.cgl"
            source_path.parent.mkdir()
            source_path.write_text(
                "runtime package summary must not parse source\n",
                encoding="utf-8",
            )

            with self._guard_crossgl_source_reads():
                package = read_package(package_dir)
                package_summary = package.to_summary()
                report = package.compatibility_report(loader_target="metal")

            summary = report.to_summary()
            reject_codes = [diagnostic.code for diagnostic in report.reject_reasons]

            self.assertIsNone(package.target_artifact_contract())
            self.assertEqual(package.required_target_artifacts(), ())
            self.assertIsNone(package_summary["packageArtifactRequirements"])
            self.assertIsNone(package_summary["targetContract"])
            self.assertFalse(report.compatible)
            self.assertEqual(report.required_artifacts, ())
            self.assertIn("package.artifact_requirements.invalid", reject_codes)
            self.assertIsNone(summary["packageArtifactRequirements"])
            self.assertEqual(
                summary["admission"]["requirements"]["requirementsSource"],
                "manifest",
            )
            self.assertFalse(summary["sourceParsingRequired"])
            self.assertEqual(list(package_dir.rglob("*.cgl")), [source_path])

    def test_runtime_artifact_rejects_source_fallback_with_malformed_recorded_requirements(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory(suffix=".cglb") as temp_dir:
            package_dir = Path(temp_dir)
            self._write_valid_package(
                package_dir,
                target="directx",
                package_artifact_requirements=["not", "an", "object"],
            )
            source_path = package_dir / "source" / "invalid.cgl"
            source_path.parent.mkdir()
            source_path.write_text(
                "runtime artifact fallback must not parse CrossGL source for "
                "malformed packageArtifactRequirements\n",
                encoding="utf-8",
            )

            with self._guard_crossgl_source_reads():
                package = read_package(package_dir)
                report = read_compatibility_report(
                    package_dir,
                    loader_target="directx",
                )
                selection = select_runtime_artifact(report, target="directx")

                with self.assertRaisesRegex(
                    PackageReadError,
                    "package artifact requirements are not compatible",
                ):
                    package.runtime_artifact()

            self.assertFalse(report.compatible)
            self.assertFalse(selection.selected)
            self.assertIn(
                "package.artifact_requirements.invalid",
                [diagnostic.code for diagnostic in report.reject_reasons],
            )
            self.assertEqual(list(package_dir.rglob("*.cgl")), [source_path])

    def test_recorded_requirements_resolve_despite_unrelated_manifest_diagnostic(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory(suffix=".cglb") as temp_dir:
            package_dir = Path(temp_dir)
            self._write_valid_package(
                package_dir,
                package_artifact_requirements={
                    "target": "metal",
                    "packageMode": "native",
                    "requiredPathArtifacts": [
                        "backendSource",
                        "intermediate",
                        "nativeBinary",
                    ],
                    "requiresNativeBinaryStatus": False,
                    "allowsPlannedNativeBinary": False,
                    "allowsPlannedNativeSourceEvidence": False,
                },
            )
            manifest_path = package_dir / "manifest.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["compiler"]["version"] = ""
            self._write_json(manifest_path, manifest)

            report = read_compatibility_report(package_dir, loader_target="metal")
            summary = report.to_summary()

            self.assertFalse(report.compatible)
            self.assertIsNotNone(report.target_contract)
            self.assertEqual(report.target_contract.requirements_source, "manifest")
            self.assertEqual(
                report.required_artifacts,
                ("backendSource", "intermediate", "nativeBinary"),
            )
            self.assertEqual(
                summary["packageArtifactRequirements"]["requiredPathArtifacts"],
                ["backendSource", "intermediate", "nativeBinary"],
            )
            self.assertIn(
                "package.compiler.version_missing",
                [diagnostic.code for diagnostic in report.reject_reasons],
            )

    def test_compatibility_report_accepts_native_artifact_descriptor_provenance(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory(suffix=".cglb") as temp_dir:
            package_dir = Path(temp_dir)
            self._write_valid_package(package_dir)
            descriptor = self._write_native_artifact_descriptor(package_dir)

            package = read_package(package_dir)
            report = package.compatibility_report(loader_target="metal")
            selection = select_runtime_artifact(report, target="metal")
            summary = report.to_summary()

            self.assertTrue(report.compatible, summary["diagnostics"])
            self.assertTrue(selection.selected, selection.to_summary()["diagnostics"])
            self.assertEqual(selection.require_selected().name, "nativeBinary")
            self.assertIn(
                "nativeArtifactDescriptor",
                [artifact.name for artifact in package.artifacts],
            )
            self.assertEqual(
                descriptor["optimizationEvidence"]["status"],
                "metadata-only",
            )
            self.assertEqual(summary["rejectReasons"], [])

    def test_compatibility_report_accepts_native_descriptor_host_tool_evidence_without_probe(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory(suffix=".cglb") as temp_dir:
            package_dir = Path(temp_dir)
            self._write_valid_package(package_dir)
            self._write_native_artifact_descriptor(
                package_dir,
                mutate=lambda descriptor: descriptor["toolchainProvenance"].__setitem__(
                    "tools",
                    [
                        {
                            "name": "xcrun metal",
                            "role": "compiler",
                            "version": "fixture",
                            "executable": "xcrun",
                            "resolvedExecutable": "/usr/bin/xcrun",
                            "executableSource": "direct",
                            "versionProbeStatus": "succeeded",
                            "versionDetail": "fixture version output",
                        },
                        {
                            "name": "metallib",
                            "role": "linker",
                            "version": "unknown",
                            "executable": "metallib",
                            "resolvedExecutable": "/opt/homebrew/bin/metallib",
                            "executableSource": "PATH",
                            "versionProbeStatus": "failed",
                            "versionDetail": "exit 1: fixture probe failure",
                        },
                    ],
                ),
            )
            source_path = package_dir / "source" / "invalid.cgl"
            source_path.parent.mkdir()
            source_path.write_text(
                "runtime must not parse source or probe host tools\n",
                encoding="utf-8",
            )

            with self._guard_crossgl_source_reads():
                with mock.patch(
                    "subprocess.run",
                    side_effect=AssertionError("runtime probed host tools"),
                ):
                    package = read_package(package_dir)
                    report = package.compatibility_report(loader_target="metal")
                    selection = select_runtime_artifact(report, target="metal")

            summary = report.to_summary()
            descriptor_artifact = package.require_existing_artifact(
                "nativeArtifactDescriptor"
            )
            descriptor = json.loads(descriptor_artifact.read_text(encoding="utf-8"))
            tool_records = descriptor["toolchainProvenance"]["tools"]

            self.assertTrue(report.compatible, summary["diagnostics"])
            self.assertTrue(selection.selected, selection.to_summary()["diagnostics"])
            self.assertFalse(report.source_parsing_required)
            self.assertEqual(selection.require_selected().name, "nativeBinary")
            self.assertEqual(summary["rejectReasons"], [])
            self.assertEqual(
                [
                    (
                        tool["resolvedExecutable"],
                        tool["executableSource"],
                        tool["versionProbeStatus"],
                        tool["versionDetail"],
                    )
                    for tool in tool_records
                ],
                [
                    (
                        "/usr/bin/xcrun",
                        "direct",
                        "succeeded",
                        "fixture version output",
                    ),
                    (
                        "/opt/homebrew/bin/metallib",
                        "PATH",
                        "failed",
                        "exit 1: fixture probe failure",
                    ),
                ],
            )
            self.assertEqual(list(package_dir.rglob("*.cgl")), [source_path])

    def test_compatibility_report_rejects_malformed_optional_native_tool_provenance_fields_without_source_parse(
        self,
    ) -> None:
        base_tool: dict[str, object] = {
            "name": "metallib",
            "role": "linker",
            "version": "unknown",
            "executable": "metallib",
            "resolvedExecutable": "/opt/homebrew/bin/metallib",
            "executableSource": "PATH",
            "versionProbeStatus": "failed",
            "versionDetail": "exit 1: fixture probe failure",
        }
        cases: tuple[tuple[str, dict[str, object], str, str], ...] = (
            (
                "empty resolved executable",
                {**base_tool, "resolvedExecutable": ""},
                (
                    "package.native_artifact_descriptor."
                    "toolchain_provenance_tool_resolved_executable_invalid"
                ),
                "toolchainProvenance.tools[0].resolvedExecutable",
            ),
            (
                "unknown executable source",
                {**base_tool, "executableSource": "ambient"},
                (
                    "package.native_artifact_descriptor."
                    "toolchain_provenance_tool_executable_source_invalid"
                ),
                "toolchainProvenance.tools[0].executableSource",
            ),
            (
                "unknown version probe status",
                {**base_tool, "versionProbeStatus": "maybe"},
                (
                    "package.native_artifact_descriptor."
                    "toolchain_provenance_tool_version_probe_status_invalid"
                ),
                "toolchainProvenance.tools[0].versionProbeStatus",
            ),
            (
                "empty version detail",
                {**base_tool, "versionDetail": ""},
                (
                    "package.native_artifact_descriptor."
                    "toolchain_provenance_tool_version_detail_invalid"
                ),
                "toolchainProvenance.tools[0].versionDetail",
            ),
        )

        for name, tool_record, expected_code, expected_path in cases:
            with self.subTest(name=name):
                with tempfile.TemporaryDirectory(suffix=".cglb") as temp_dir:
                    package_dir = Path(temp_dir)
                    self._write_valid_package(package_dir)
                    self._write_native_artifact_descriptor(
                        package_dir,
                        mutate=lambda descriptor: descriptor[
                            "toolchainProvenance"
                        ].__setitem__("tools", [tool_record]),
                    )
                    source_path = package_dir / "source" / "invalid.cgl"
                    source_path.parent.mkdir()
                    source_path.write_text(
                        "runtime must not parse source for malformed tool provenance\n",
                        encoding="utf-8",
                    )

                    with self._guard_crossgl_source_reads():
                        report = read_compatibility_report(
                            package_dir,
                            loader_target="metal",
                        )
                        selection = select_runtime_artifact(report, target="metal")

                    summary = report.to_summary()

                    self.assertFalse(report.compatible)
                    self.assertEqual(report.status, "incompatible")
                    self.assertFalse(report.source_parsing_required)
                    self.assertFalse(selection.selected)
                    self.assertIn(
                        expected_code,
                        [diagnostic.code for diagnostic in report.reject_reasons],
                    )
                    self.assertEqual(
                        next(
                            diagnostic
                            for diagnostic in summary["rejectReasons"]
                            if diagnostic["code"] == expected_code
                        )["path"],
                        expected_path,
                    )
                    with self._guard_crossgl_source_reads():
                        with self.assertRaisesRegex(
                            PackageReadError,
                            "native artifact descriptor is not compatible",
                        ):
                            read_package(package_dir)
                    self.assertEqual(list(package_dir.rglob("*.cgl")), [source_path])

    def test_compatibility_report_rejects_malformed_native_tool_identity_fields_without_source_parse(
        self,
    ) -> None:
        base_tool: dict[str, object] = {
            "name": "CrossGL fixture compiler",
            "role": "compiler",
            "version": "test",
            "executable": "cglc",
        }
        cases: tuple[tuple[str, dict[str, object], str, str, object], ...] = (
            (
                "name array",
                {**base_tool, "name": ["cglc"]},
                (
                    "package.native_artifact_descriptor."
                    "toolchain_provenance_tool_name_invalid"
                ),
                "toolchainProvenance.tools[0].name",
                "array",
            ),
            (
                "empty role",
                {**base_tool, "role": ""},
                (
                    "package.native_artifact_descriptor."
                    "toolchain_provenance_tool_role_invalid"
                ),
                "toolchainProvenance.tools[0].role",
                "",
            ),
            (
                "version object",
                {**base_tool, "version": {"string": "test"}},
                (
                    "package.native_artifact_descriptor."
                    "toolchain_provenance_tool_version_invalid"
                ),
                "toolchainProvenance.tools[0].version",
                "object",
            ),
            (
                "executable boolean",
                {**base_tool, "executable": False},
                (
                    "package.native_artifact_descriptor."
                    "toolchain_provenance_tool_executable_invalid"
                ),
                "toolchainProvenance.tools[0].executable",
                "boolean",
            ),
        )

        for name, tool_record, expected_code, expected_path, expected_actual in cases:
            with self.subTest(name=name):
                with tempfile.TemporaryDirectory(suffix=".cglb") as temp_dir:
                    package_dir = Path(temp_dir)
                    self._write_valid_package(package_dir)
                    self._write_native_artifact_descriptor(
                        package_dir,
                        mutate=lambda descriptor: descriptor[
                            "toolchainProvenance"
                        ].__setitem__("tools", [tool_record]),
                    )
                    source_path = package_dir / "source" / "invalid.cgl"
                    source_path.parent.mkdir()
                    source_path.write_text(
                        "runtime must not parse source for malformed tool identity\n",
                        encoding="utf-8",
                    )

                    with self._guard_crossgl_source_reads():
                        report = read_compatibility_report(
                            package_dir,
                            loader_target="metal",
                        )
                        selection = select_runtime_artifact(report, target="metal")

                    summary = report.to_summary()
                    diagnostic = next(
                        diagnostic
                        for diagnostic in summary["rejectReasons"]
                        if diagnostic["code"] == expected_code
                    )

                    self.assertFalse(report.compatible)
                    self.assertEqual(report.status, "incompatible")
                    self.assertFalse(report.source_parsing_required)
                    self.assertFalse(selection.selected)
                    self.assertFalse(selection.source_parsing_required)
                    self.assertEqual(diagnostic["document"], "nativeArtifactDescriptor")
                    self.assertEqual(diagnostic["artifact"], "nativeArtifactDescriptor")
                    self.assertEqual(diagnostic["path"], expected_path)
                    self.assertEqual(diagnostic["expected"], "non-empty string")
                    self.assertEqual(diagnostic["actual"], expected_actual)
                    with self._guard_crossgl_source_reads():
                        with self.assertRaisesRegex(
                            PackageReadError,
                            "native artifact descriptor is not compatible",
                        ):
                            read_package(package_dir)
                    self.assertEqual(list(package_dir.rglob("*.cgl")), [source_path])

    def test_compatibility_report_accepts_source_free_descriptor_zip_evidence(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir)
            package_dir = temp_root / "package-dir"
            package_dir.mkdir()
            self._write_valid_package(package_dir)
            self._write_native_artifact_descriptor(package_dir)
            self._make_source_free_native_package(package_dir)
            zip_path = temp_root / "RuntimeReaderFixture.cglb"
            self._write_zip_package(
                package_dir,
                zip_path,
                prefix="RuntimeReaderFixture.cglb",
            )

            package = read_package(zip_path)
            report = package.compatibility_report(loader_target="metal")
            selection = select_runtime_artifact(report, target="metal")
            summary = report.to_summary()
            descriptor_artifact = package.require_existing_artifact(
                "nativeArtifactDescriptor"
            )

            self.assertTrue(report.compatible, summary["diagnostics"])
            self.assertEqual(package.package_format, "zip")
            self.assertEqual(package.module, "RuntimeReaderFixture")
            self.assertEqual(package.target, "metal")
            self.assertEqual(report.required_artifacts, ("nativeBinary",))
            self.assertEqual(package.required_target_artifacts(), ("nativeBinary",))
            self.assertEqual(summary["packageFormat"], "zip")
            self.assertEqual(summary["module"], "RuntimeReaderFixture")
            self.assertEqual(summary["target"], "metal")
            self.assertEqual(summary["rejectReasons"], [])
            artifact_compatibility = summary["artifactCompatibility"]
            self.assertEqual(artifact_compatibility["selectedArtifact"], "nativeBinary")
            self.assertEqual(
                [
                    (artifact["name"], artifact["decision"], artifact["reason"])
                    for artifact in artifact_compatibility["accepted"]
                ],
                [("nativeBinary", "accepted", "package.artifact.selected")],
            )
            self.assertEqual(
                [
                    (artifact["name"], artifact["decision"], artifact["reason"])
                    for artifact in artifact_compatibility["skipped"]
                ],
                [
                    (
                        "nativeArtifactDescriptor",
                        "skipped",
                        "package.artifact.not_required",
                    )
                ],
            )
            self.assertEqual(artifact_compatibility["rejected"], [])
            self.assertTrue(summary["admission"]["fallbacks"]["sourceFreePackage"])
            self.assertFalse(
                summary["admission"]["fallbacks"]["source"]["fallbackAllowed"]
            )
            self.assertFalse(
                summary["admission"]["fallbacks"]["compiler"]["fallbackAllowed"]
            )
            self.assertNotIn(
                "backendSource",
                [artifact.name for artifact in package.artifacts],
            )
            self.assertEqual(
                selection.require_selected().package_path,
                "backend/metal/RuntimeReaderFixture.metallib",
            )
            self.assertEqual(package.read_artifact_bytes("nativeBinary"), b"metallib")
            self.assertEqual(
                descriptor_artifact.archive_member,
                "RuntimeReaderFixture.cglb/metadata/native-artifact.json",
            )
            with zipfile.ZipFile(zip_path) as archive:
                self.assertNotIn(
                    "RuntimeReaderFixture.cglb/backend/metal/"
                    "RuntimeReaderFixture.metal",
                    archive.namelist(),
                )

    def test_compatibility_report_prefers_recorded_source_free_requirements_for_directory_and_zip(
        self,
    ) -> None:
        for package_format in ("directory", "zip"):
            with self.subTest(package_format=package_format):
                with tempfile.TemporaryDirectory() as temp_dir:
                    temp_root = Path(temp_dir)
                    package_dir = temp_root / "package-dir"
                    package_dir.mkdir()
                    self._write_valid_package(package_dir)
                    self._write_native_artifact_descriptor(package_dir)
                    self._make_source_free_native_package(package_dir)
                    source_path = package_dir / "source" / "invalid.cgl"
                    source_path.parent.mkdir()
                    source_path.write_text(
                        "runtime must not parse source when manifest-recorded "
                        "source-free requirements are present\n",
                        encoding="utf-8",
                    )

                    if package_format == "zip":
                        package_path = temp_root / "RuntimeReaderFixture.cglb"
                        self._write_zip_package(
                            package_dir,
                            package_path,
                            prefix=package_path.name,
                        )
                        guard = self._guard_zip_crossgl_member_reads()
                    else:
                        package_path = package_dir
                        guard = self._guard_crossgl_source_reads()

                    with guard:
                        report = read_compatibility_report(
                            package_path,
                            loader_target="metal",
                        )
                        selection = select_runtime_artifact(
                            report,
                            target="metal",
                        )

                    summary = report.to_summary()
                    requirements = summary["admission"]["requirements"]

                    self.assertTrue(report.compatible, summary["diagnostics"])
                    self.assertEqual(summary["packageFormat"], package_format)
                    self.assertFalse(summary["sourceParsingRequired"])
                    self.assertFalse(summary["compilerInvocationRequired"])
                    self.assertFalse(summary["deviceExecutionRequired"])
                    self.assertEqual(report.required_artifacts, ("nativeBinary",))
                    self.assertEqual(summary["requiredArtifacts"], ["nativeBinary"])
                    self.assertEqual(
                        selection.require_selected().name,
                        "nativeBinary",
                    )
                    self.assertEqual(
                        summary["targetContract"]["requirementsSource"],
                        "manifest",
                    )
                    self.assertFalse(summary["targetContract"]["reportOnly"])
                    self.assertEqual(
                        summary["targetContract"]["compatibilityScope"],
                        "recorded-package-metadata",
                    )
                    self.assertTrue(requirements["declared"])
                    self.assertTrue(requirements["recorded"])
                    self.assertFalse(requirements["legacyInferred"])
                    self.assertEqual(requirements["requirementsSource"], "manifest")
                    self.assertEqual(
                        requirements["compatibilityScope"],
                        "recorded-package-metadata",
                    )
                    self.assertFalse(requirements["reportOnly"])
                    self.assertEqual(
                        requirements["requiredPathArtifacts"],
                        ["nativeBinary"],
                    )
                    self.assertFalse(
                        requirements["legacyGeneratedRequirements"]["reportOnly"]
                    )
                    self.assertEqual(
                        requirements["legacyGeneratedRequirements"][
                            "requirementsSource"
                        ],
                        "legacy-v0-target-contract",
                    )
                    self.assertEqual(summary["missingArtifacts"], [])
                    self.assertNotIn(
                        "backendSource",
                        [artifact.name for artifact in report.available_artifacts],
                    )
                    if package_format == "zip":
                        with zipfile.ZipFile(package_path) as archive:
                            self.assertIn(
                                f"{package_path.name}/source/invalid.cgl",
                                archive.namelist(),
                            )
                    else:
                        self.assertEqual(
                            list(package_dir.rglob("*.cgl")),
                            [source_path],
                        )

    def test_compatibility_report_rejects_source_free_descriptor_without_recorded_requirements_for_directory_and_zip(
        self,
    ) -> None:
        expected_code = "package.artifact_requirements.source_free_native_missing"
        for package_format in ("directory", "zip"):
            with self.subTest(package_format=package_format):
                with tempfile.TemporaryDirectory() as temp_dir:
                    temp_root = Path(temp_dir)
                    package_dir = temp_root / "package-dir"
                    package_dir.mkdir()
                    self._write_valid_package(package_dir)
                    self._write_native_artifact_descriptor(package_dir)
                    self._make_source_free_native_package(package_dir)
                    manifest_path = package_dir / "manifest.json"
                    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
                    manifest.pop("packageArtifactRequirements")
                    self._write_json(manifest_path, manifest)
                    source_path = package_dir / "source" / "invalid.cgl"
                    source_path.parent.mkdir()
                    source_path.write_text(
                        "runtime must not regenerate source-free requirements "
                        "from CrossGL source\n",
                        encoding="utf-8",
                    )

                    if package_format == "zip":
                        package_path = temp_root / "RuntimeReaderFixture.cglb"
                        self._write_zip_package(
                            package_dir,
                            package_path,
                            prefix=package_path.name,
                        )
                        guard = self._guard_zip_crossgl_member_reads()
                    else:
                        package_path = package_dir
                        guard = self._guard_crossgl_source_reads()

                    with guard:
                        report = read_compatibility_report(
                            package_path,
                            loader_target="metal",
                        )
                        selection = select_runtime_artifact(
                            report,
                            target="metal",
                        )

                    summary = report.to_summary()
                    requirements = summary["admission"]["requirements"]
                    reject_codes = [
                        diagnostic.code for diagnostic in report.reject_reasons
                    ]

                    self.assertFalse(report.compatible)
                    self.assertEqual(report.status, "incompatible")
                    self.assertIn(expected_code, reject_codes)
                    self.assertIsNone(report.target_contract)
                    self.assertEqual(report.required_artifacts, ())
                    self.assertEqual(summary["requiredArtifacts"], [])
                    self.assertIsNone(summary["targetContract"])
                    self.assertIsNone(summary["packageArtifactRequirements"])
                    self.assertFalse(
                        summary["artifactAvailability"]["native"]["usable"]
                    )
                    self.assertTrue(
                        summary["admission"]["fallbacks"]["sourceFreePackage"]
                    )
                    self.assertFalse(selection.selected)
                    self.assertIsNone(selection.artifact)
                    self.assertFalse(selection.source_parsing_required)
                    self.assertFalse(summary["sourceParsingRequired"])
                    self.assertFalse(summary["compilerInvocationRequired"])
                    self.assertFalse(summary["deviceExecutionRequired"])
                    self.assertFalse(requirements["declared"])
                    self.assertFalse(requirements["recorded"])
                    self.assertTrue(requirements["legacyInferred"])
                    self.assertEqual(
                        requirements["requirementsSource"],
                        "legacy-v0-target-contract",
                    )
                    self.assertEqual(
                        requirements["compatibilityKind"],
                        "legacy-generated-unresolved",
                    )
                    self.assertTrue(requirements["reportOnly"])
                    self.assertEqual(
                        requirements["compatibilityScope"],
                        "legacy/report-only",
                    )
                    self.assertEqual(requirements["reason"], expected_code)
                    self.assertFalse(requirements["complete"])
                    self.assertFalse(requirements["resolved"])
                    self.assertFalse(requirements["valid"])
                    self.assertTrue(
                        requirements["legacyGeneratedRequirements"]["compatibilityOnly"]
                    )
                    self.assertTrue(
                        requirements["legacyGeneratedRequirements"]["reportOnly"]
                    )
                    self.assertEqual(
                        requirements["legacyGeneratedRequirements"][
                            "compatibilityScope"
                        ],
                        "legacy/report-only",
                    )
                    self.assertIn(
                        expected_code,
                        [
                            diagnostic["code"]
                            for diagnostic in requirements["diagnostics"]
                        ],
                    )
                    if package_format == "zip":
                        with zipfile.ZipFile(package_path) as archive:
                            self.assertIn(
                                f"{package_path.name}/source/invalid.cgl",
                                archive.namelist(),
                            )
                    else:
                        self.assertEqual(
                            list(package_dir.rglob("*.cgl")),
                            [source_path],
                        )

    def test_compatibility_report_rejects_source_free_descriptor_zip_tampering(
        self,
    ) -> None:
        cases = (
            (
                "target mismatch",
                lambda descriptor: descriptor.__setitem__("target", "directx"),
                "package.native_artifact_descriptor.target_mismatch",
            ),
            (
                "artifact path mismatch",
                lambda descriptor: descriptor.__setitem__(
                    "artifactPath",
                    "backend/metal/Other.metallib",
                ),
                "package.native_artifact_descriptor.artifact_path_mismatch",
            ),
            (
                "artifact hash mismatch",
                lambda descriptor: descriptor["artifactHash"].__setitem__(
                    "value",
                    "1" * 64,
                ),
                "package.native_artifact_descriptor.artifact_hash_mismatch",
            ),
        )

        for name, mutate, expected_code in cases:
            with self.subTest(name=name):
                with tempfile.TemporaryDirectory() as temp_dir:
                    temp_root = Path(temp_dir)
                    package_dir = temp_root / "package-dir"
                    package_dir.mkdir()
                    self._write_valid_package(package_dir)
                    self._write_native_artifact_descriptor(
                        package_dir,
                        mutate=mutate,
                    )
                    self._make_source_free_native_package(package_dir)
                    zip_path = temp_root / "RuntimeReaderFixture.cglb"
                    self._write_zip_package(
                        package_dir,
                        zip_path,
                        prefix="RuntimeReaderFixture.cglb",
                    )

                    report = read_compatibility_report(
                        zip_path,
                        loader_target="metal",
                    )
                    selection = select_runtime_artifact(report, target="metal")
                    summary = report.to_summary()

                    self.assertFalse(report.compatible)
                    self.assertEqual(report.status, "incompatible")
                    self.assertEqual(summary["packageFormat"], "zip")
                    self.assertFalse(report.source_parsing_required)
                    self.assertFalse(selection.selected)
                    self.assertEqual(report.required_artifacts, ("nativeBinary",))
                    self.assertNotIn(
                        "backendSource",
                        [artifact.name for artifact in report.available_artifacts],
                    )
                    self.assertIn(
                        expected_code,
                        [diagnostic.code for diagnostic in report.reject_reasons],
                    )
                    with zipfile.ZipFile(zip_path) as archive:
                        self.assertNotIn(
                            "RuntimeReaderFixture.cglb/backend/metal/"
                            "RuntimeReaderFixture.metal",
                            archive.namelist(),
                        )
                    with self.assertRaisesRegex(
                        PackageReadError,
                        "native artifact descriptor is not compatible",
                    ):
                        read_package(zip_path)

    def test_compatibility_report_rejects_zip_native_artifact_descriptor_fingerprints(
        self,
    ) -> None:
        cases = (
            (
                "source path mismatch",
                lambda descriptor: descriptor.__setitem__(
                    "sourcePath",
                    "source/RuntimeReaderFixture.cgl",
                ),
                "package.native_artifact_descriptor.source_path_mismatch",
                "sourcePath",
            ),
            (
                "source hash mismatch",
                lambda descriptor: descriptor["sourceHash"].__setitem__(
                    "value",
                    "2" * 64,
                ),
                "package.native_artifact_descriptor.source_hash_mismatch",
                "sourceHash.value",
            ),
            (
                "artifact hash mismatch",
                lambda descriptor: descriptor["artifactHash"].__setitem__(
                    "value",
                    "3" * 64,
                ),
                "package.native_artifact_descriptor.artifact_hash_mismatch",
                "artifactHash.value",
            ),
            (
                "size mismatch",
                lambda descriptor: descriptor.__setitem__("sizeBytes", 999),
                "package.native_artifact_descriptor.size_bytes_mismatch",
                "sizeBytes",
            ),
        )

        for name, mutate, expected_code, expected_path in cases:
            with self.subTest(name=name):
                with tempfile.TemporaryDirectory() as temp_dir:
                    temp_root = Path(temp_dir)
                    package_dir = temp_root / "package-dir"
                    package_dir.mkdir()
                    self._write_valid_package(package_dir)
                    self._write_native_artifact_descriptor(
                        package_dir,
                        mutate=mutate,
                    )
                    cgl_source_path = (
                        package_dir / "source" / "RuntimeReaderFixture.cgl"
                    )
                    cgl_source_path.parent.mkdir()
                    cgl_source_path.write_text(
                        "runtime must not parse descriptor sourcePath members\n",
                        encoding="utf-8",
                    )
                    zip_path = temp_root / "RuntimeReaderFixture.cglb"
                    self._write_zip_package(
                        package_dir,
                        zip_path,
                        prefix="RuntimeReaderFixture.cglb",
                    )

                    with self._guard_zip_crossgl_member_reads():
                        report = read_compatibility_report(
                            zip_path,
                            loader_target="metal",
                        )
                        selection = select_runtime_artifact(report, target="metal")

                    summary = report.to_summary()

                    self.assertFalse(report.compatible)
                    self.assertEqual(report.status, "incompatible")
                    self.assertEqual(summary["packageFormat"], "zip")
                    self.assertFalse(report.source_parsing_required)
                    self.assertFalse(selection.selected)
                    self.assertIn(
                        expected_code,
                        [diagnostic.code for diagnostic in report.reject_reasons],
                    )
                    self.assertEqual(
                        next(
                            diagnostic
                            for diagnostic in summary["rejectReasons"]
                            if diagnostic["code"] == expected_code
                        )["path"],
                        expected_path,
                    )
                    with zipfile.ZipFile(zip_path) as archive:
                        self.assertIn(
                            "RuntimeReaderFixture.cglb/source/RuntimeReaderFixture.cgl",
                            archive.namelist(),
                        )
                    with self._guard_zip_crossgl_member_reads():
                        with self.assertRaisesRegex(
                            PackageReadError,
                            "native artifact descriptor is not compatible",
                        ):
                            read_package(zip_path)

    def test_compatibility_report_rejects_selected_native_binary_descriptor_size_drift(
        self,
    ) -> None:
        expected_code = "package.native_artifact_descriptor.size_bytes_mismatch"
        for package_format in ("directory", "zip"):
            with self.subTest(package_format=package_format):
                with tempfile.TemporaryDirectory() as temp_dir:
                    temp_root = Path(temp_dir)
                    package_dir = temp_root / "package-dir"
                    package_dir.mkdir()
                    self._write_valid_package(package_dir)
                    self._write_native_artifact_descriptor(
                        package_dir,
                        mutate=lambda descriptor: descriptor.__setitem__(
                            "sizeBytes",
                            999,
                        ),
                    )
                    source_path = package_dir / "source" / "invalid.cgl"
                    source_path.parent.mkdir()
                    source_path.write_text(
                        "runtime must not parse CrossGL source for native "
                        "artifact descriptor size drift\n",
                        encoding="utf-8",
                    )

                    package_path: Path
                    if package_format == "zip":
                        zip_path = temp_root / "RuntimeReaderFixture.cglb"
                        self._write_zip_package(
                            package_dir,
                            zip_path,
                            prefix="RuntimeReaderFixture.cglb",
                        )
                        package_path = zip_path
                        guard = self._guard_zip_crossgl_member_reads()
                    else:
                        package_path = package_dir
                        guard = self._guard_crossgl_source_reads()

                    with guard:
                        report = read_compatibility_report(
                            package_path,
                            loader_target="metal",
                        )
                        selection = select_runtime_artifact(report, target="metal")

                    summary = report.to_summary()
                    selection_summary = selection.to_summary()
                    artifact_records = {
                        artifact["name"]: artifact
                        for artifact in summary["artifactCompatibility"]["artifacts"]
                    }
                    native_binary_record = artifact_records["nativeBinary"]

                    self.assertFalse(report.compatible)
                    self.assertEqual(report.status, "incompatible")
                    self.assertFalse(report.source_parsing_required)
                    self.assertFalse(selection.selected)
                    self.assertFalse(selection.source_parsing_required)
                    self.assertEqual(summary["packageFormat"], package_format)
                    self.assertIn(
                        expected_code,
                        [diagnostic.code for diagnostic in report.reject_reasons],
                    )
                    self.assertEqual(
                        selection_summary["admission"]["native"]["reason"],
                        expected_code,
                    )
                    self.assertIsNone(
                        summary["artifactCompatibility"]["selectedArtifact"]
                    )
                    self.assertEqual(native_binary_record["decision"], "rejected")
                    self.assertEqual(native_binary_record["reason"], expected_code)
                    self.assertEqual(
                        [
                            diagnostic["code"]
                            for diagnostic in native_binary_record["diagnostics"]
                        ],
                        [expected_code],
                    )
                    self.assertEqual(
                        native_binary_record["diagnostics"][0]["artifact"],
                        "nativeArtifactDescriptor",
                    )

    def test_compatibility_report_rejects_source_free_descriptor_zip_size_tampering_without_source_member_reads(
        self,
    ) -> None:
        source_member = "source/RuntimeReaderFixture.cgl"
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir)
            package_dir = temp_root / "package-dir"
            package_dir.mkdir()
            self._write_valid_package(package_dir)
            self._write_native_artifact_descriptor(
                package_dir,
                mutate=lambda descriptor: descriptor.update(
                    {
                        "sourcePath": source_member,
                        "sizeBytes": 999,
                    }
                ),
            )
            cgl_source_path = package_dir / source_member
            cgl_source_path.parent.mkdir()
            cgl_source_path.write_text(
                "runtime must not parse source-free descriptor sourcePath members\n",
                encoding="utf-8",
            )
            self._make_source_free_native_package(package_dir)
            zip_path = temp_root / "RuntimeReaderFixture.cglb"
            self._write_zip_package(
                package_dir,
                zip_path,
                prefix="RuntimeReaderFixture.cglb",
            )

            with self._guard_zip_crossgl_member_reads():
                report = read_compatibility_report(zip_path, loader_target="metal")
                selection = select_runtime_artifact(report, target="metal")

            summary = report.to_summary()
            selection_summary = selection.to_summary()
            serialized_runtime_surfaces = json.dumps(
                {
                    "report": summary,
                    "selection": selection_summary,
                },
                sort_keys=True,
            )

            self.assertFalse(report.compatible)
            self.assertEqual(report.status, "incompatible")
            self.assertEqual(summary["packageFormat"], "zip")
            self.assertFalse(report.source_parsing_required)
            self.assertFalse(selection.selected)
            self.assertFalse(selection.source_parsing_required)
            self.assertTrue(summary["admission"]["fallbacks"]["sourceFreePackage"])
            self.assertEqual(report.required_artifacts, ("nativeBinary",))
            self.assertNotIn(
                "backendSource",
                [artifact.name for artifact in report.available_artifacts],
            )
            self.assertIn(
                "package.native_artifact_descriptor.size_bytes_mismatch",
                [diagnostic.code for diagnostic in report.reject_reasons],
            )
            self.assertNotIn(source_member, serialized_runtime_surfaces)
            with zipfile.ZipFile(zip_path) as archive:
                self.assertIn(
                    "RuntimeReaderFixture.cglb/source/RuntimeReaderFixture.cgl",
                    archive.namelist(),
                )
            with self._guard_zip_crossgl_member_reads():
                with self.assertRaisesRegex(
                    PackageReadError,
                    "native artifact descriptor is not compatible",
                ):
                    read_package(zip_path)

    def test_compatibility_report_rejects_native_artifact_descriptor_tampering(
        self,
    ) -> None:
        cases = (
            (
                "target mismatch",
                lambda descriptor: descriptor.__setitem__("target", "directx"),
                "package.native_artifact_descriptor.target_mismatch",
                "target",
            ),
            (
                "artifact path mismatch",
                lambda descriptor: descriptor.__setitem__(
                    "artifactPath",
                    "backend/metal/Other.metallib",
                ),
                "package.native_artifact_descriptor.artifact_path_mismatch",
                "artifactPath",
            ),
            (
                "artifact hash mismatch",
                lambda descriptor: descriptor["artifactHash"].__setitem__(
                    "value",
                    "1" * 64,
                ),
                "package.native_artifact_descriptor.artifact_hash_mismatch",
                "artifactHash.value",
            ),
            (
                "size mismatch",
                lambda descriptor: descriptor.__setitem__("sizeBytes", 999),
                "package.native_artifact_descriptor.size_bytes_mismatch",
                "sizeBytes",
            ),
        )

        for name, mutate, expected_code, expected_path in cases:
            with self.subTest(name=name):
                with tempfile.TemporaryDirectory(suffix=".cglb") as temp_dir:
                    package_dir = Path(temp_dir)
                    self._write_valid_package(package_dir)
                    self._write_native_artifact_descriptor(
                        package_dir,
                        mutate=mutate,
                    )

                    report = read_compatibility_report(
                        package_dir,
                        loader_target="metal",
                    )
                    selection = select_runtime_artifact(report, target="metal")
                    summary = report.to_summary()

                    self.assertFalse(report.compatible)
                    self.assertEqual(report.status, "incompatible")
                    self.assertFalse(selection.selected)
                    self.assertIn(
                        expected_code,
                        [diagnostic.code for diagnostic in report.reject_reasons],
                    )
                    self.assertEqual(
                        next(
                            diagnostic
                            for diagnostic in summary["rejectReasons"]
                            if diagnostic["code"] == expected_code
                        )["path"],
                        expected_path,
                    )
                    with self.assertRaisesRegex(
                        PackageReadError,
                        "native artifact descriptor is not compatible",
                    ):
                        read_package(package_dir)

    def test_compatibility_report_rejects_native_artifact_descriptor_status_tampering(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory(suffix=".cglb") as temp_dir:
            package_dir = Path(temp_dir)
            self._write_valid_package(
                package_dir,
                target="directx",
                native_status="planned",
            )
            self._write_native_artifact_descriptor(
                package_dir,
                mutate=lambda descriptor: descriptor.update(
                    {
                        "artifactPath": "backend/directx/RuntimeReaderFixture.dxil",
                        "nativeBinaryStatus": "emitted",
                    }
                ),
            )

            report = read_compatibility_report(package_dir, loader_target="directx")
            summary = report.to_summary()

            self.assertFalse(report.compatible)
            self.assertIn(
                "package.native_artifact_descriptor.native_binary_status_mismatch",
                [diagnostic.code for diagnostic in report.reject_reasons],
            )
            self.assertIn(
                "package.native_artifact_descriptor.artifact_path_unexpected",
                [diagnostic.code for diagnostic in report.reject_reasons],
            )
            self.assertEqual(summary["status"], "incompatible")

    def test_compatibility_report_rejects_applied_optimization_evidence_without_native_facts(
        self,
    ) -> None:
        def applied_level(level: str):
            def mutate(descriptor: dict[str, object]) -> None:
                evidence = descriptor["optimizationEvidence"]
                self.assertIsInstance(evidence, dict)
                descriptor["optimizationEvidence"] = {
                    **evidence,
                    "status": "applied",
                }
                descriptor["optimizationLevel"] = level

            return mutate

        cases = (
            (
                "missing concrete level",
                "metal",
                None,
                applied_level("unknown"),
                (
                    ("package.native_artifact_descriptor.optimization_level_required"),
                    "optimizationLevel",
                ),
            ),
            (
                "bogus level",
                "metal",
                None,
                applied_level("bogus"),
                (
                    ("package.native_artifact_descriptor.optimization_level_required"),
                    "optimizationLevel",
                ),
            ),
            (
                "future numeric level",
                "metal",
                None,
                applied_level("O99"),
                (
                    ("package.native_artifact_descriptor.optimization_level_required"),
                    "optimizationLevel",
                ),
            ),
            (
                "whitespace level",
                "metal",
                None,
                applied_level(" O2 "),
                (
                    ("package.native_artifact_descriptor.optimization_level_required"),
                    "optimizationLevel",
                ),
            ),
            (
                "case drift level",
                "metal",
                None,
                applied_level("o2"),
                (
                    ("package.native_artifact_descriptor.optimization_level_required"),
                    "optimizationLevel",
                ),
            ),
            (
                "missing produced artifact facts",
                "metal",
                None,
                lambda descriptor: (
                    descriptor.__setitem__(
                        "optimizationEvidence",
                        {
                            **descriptor["optimizationEvidence"],
                            "status": "applied",
                        },
                    ),
                    descriptor.pop("artifactHash"),
                ),
                (
                    (
                        "package.native_artifact_descriptor."
                        "optimization_artifact_facts_missing"
                    ),
                    "optimizationEvidence.status",
                ),
            ),
            (
                "planned source-package evidence",
                "directx",
                "planned",
                lambda descriptor: descriptor.__setitem__(
                    "optimizationEvidence",
                    {
                        **descriptor["optimizationEvidence"],
                        "status": "applied",
                    },
                ),
                (
                    (
                        "package.native_artifact_descriptor."
                        "optimization_evidence_applied_planned"
                    ),
                    "optimizationEvidence.status",
                ),
            ),
        )

        for name, target, native_status, mutate, expected in cases:
            with self.subTest(name=name):
                with tempfile.TemporaryDirectory(suffix=".cglb") as temp_dir:
                    package_dir = Path(temp_dir)
                    self._write_valid_package(
                        package_dir,
                        target=target,
                        native_status=native_status,
                    )
                    self._write_native_artifact_descriptor(
                        package_dir,
                        mutate=mutate,
                    )
                    source_path = package_dir / "source" / "invalid.cgl"
                    source_path.parent.mkdir()
                    source_path.write_text(
                        "runtime must not parse source for optimization evidence\n",
                        encoding="utf-8",
                    )

                    with self._guard_crossgl_source_reads():
                        report = read_compatibility_report(
                            package_dir,
                            loader_target=target,
                        )
                        selection = select_runtime_artifact(
                            report,
                            target=target,
                        )

                    summary = report.to_summary()
                    expected_code, expected_path = expected
                    diagnostic = next(
                        diagnostic
                        for diagnostic in summary["rejectReasons"]
                        if diagnostic["code"] == expected_code
                    )

                    self.assertFalse(report.compatible)
                    self.assertEqual(report.status, "incompatible")
                    self.assertFalse(report.source_parsing_required)
                    self.assertFalse(selection.selected)
                    self.assertFalse(selection.source_parsing_required)
                    self.assertEqual(diagnostic["document"], "nativeArtifactDescriptor")
                    self.assertEqual(diagnostic["artifact"], "nativeArtifactDescriptor")
                    self.assertEqual(diagnostic["path"], expected_path)
                    with self._guard_crossgl_source_reads():
                        with self.assertRaisesRegex(
                            PackageReadError,
                            "native artifact descriptor is not compatible",
                        ):
                            read_package(package_dir)
                    self.assertEqual(list(package_dir.rglob("*.cgl")), [source_path])

    def test_compatibility_report_accepts_applied_optimization_evidence_with_concrete_level_enum(
        self,
    ) -> None:
        concrete_levels = ("none", "debug", "O0", "O1", "O2", "O3", "Os", "Oz")

        for level in concrete_levels:
            with self.subTest(level=level):
                with tempfile.TemporaryDirectory(suffix=".cglb") as temp_dir:
                    package_dir = Path(temp_dir)
                    self._write_valid_package(package_dir, target="metal")

                    def mutate(descriptor: dict[str, object]) -> None:
                        evidence = descriptor["optimizationEvidence"]
                        self.assertIsInstance(evidence, dict)
                        descriptor["optimizationEvidence"] = {
                            **evidence,
                            "requestedLevel": level,
                            "effectiveLevel": level,
                            "status": "applied",
                        }
                        descriptor["optimizationLevel"] = level

                    self._write_native_artifact_descriptor(
                        package_dir,
                        mutate=mutate,
                    )
                    source_path = package_dir / "source" / "invalid.cgl"
                    source_path.parent.mkdir()
                    source_path.write_text(
                        "runtime must not parse source for valid optimization evidence\n",
                        encoding="utf-8",
                    )

                    with self._guard_crossgl_source_reads():
                        package = read_package(package_dir)
                        report = package.compatibility_report(loader_target="metal")
                        selection = select_runtime_artifact(report, target="metal")

                    summary = report.to_summary()
                    self.assertTrue(report.compatible, summary["diagnostics"])
                    self.assertTrue(selection.selected)
                    self.assertEqual(selection.require_selected().name, "nativeBinary")
                    self.assertEqual(summary["rejectReasons"], [])
                    self.assertEqual(list(package_dir.rglob("*.cgl")), [source_path])

    def test_compatibility_report_routes_malformed_native_artifact_metadata_to_native_admission_without_source_parse(
        self,
    ) -> None:
        cases = (
            (
                "descriptor not object",
                lambda package_dir: (
                    package_dir / "metadata" / "native-artifact.json"
                ).write_text("[]\n", encoding="utf-8"),
                "package.native_artifact_descriptor.invalid",
                "metadata/native-artifact.json",
                "incompatible",
            ),
            (
                "descriptor binary kind target mismatch",
                lambda package_dir: self._write_native_artifact_descriptor(
                    package_dir,
                    mutate=lambda descriptor: descriptor.__setitem__(
                        "binaryKind",
                        "vulkan.spirv-module",
                    ),
                ),
                "package.native_artifact_descriptor.binary_kind_mismatch",
                "binaryKind",
                "incompatible",
            ),
            (
                "future descriptor schema",
                lambda package_dir: self._write_native_artifact_descriptor(
                    package_dir,
                    mutate=lambda descriptor: descriptor.__setitem__(
                        "schemaVersion",
                        2,
                    ),
                ),
                "package.native_artifact_descriptor.schema_incompatible",
                "schemaVersion",
                "unsupported-version",
            ),
            (
                "missing descriptor schema",
                lambda package_dir: self._write_native_artifact_descriptor(
                    package_dir,
                    mutate=lambda descriptor: descriptor.pop("schemaVersion"),
                ),
                "package.native_artifact_descriptor.schema_version_missing",
                "schemaVersion",
                "unsupported-version",
            ),
            (
                "malformed descriptor schema",
                lambda package_dir: self._write_native_artifact_descriptor(
                    package_dir,
                    mutate=lambda descriptor: descriptor.__setitem__(
                        "schemaVersion",
                        "1",
                    ),
                ),
                "package.native_artifact_descriptor.schema_version_invalid",
                "schemaVersion",
                "unsupported-version",
            ),
            (
                "future descriptor field",
                lambda package_dir: self._write_native_artifact_descriptor(
                    package_dir,
                    mutate=lambda descriptor: descriptor.__setitem__(
                        "runtimeAdmissionHints",
                        {"preferredLoader": "metal"},
                    ),
                ),
                "package.native_artifact_descriptor.unexpected_field",
                "runtimeAdmissionHints",
                "incompatible",
            ),
        )

        for (
            name,
            mutate_descriptor,
            expected_code,
            expected_path,
            expected_status,
        ) in cases:
            with self.subTest(name=name):
                with tempfile.TemporaryDirectory(suffix=".cglb") as temp_dir:
                    package_dir = Path(temp_dir)
                    self._write_valid_package(package_dir)
                    self._write_native_artifact_descriptor(package_dir)
                    mutate_descriptor(package_dir)
                    source_path = package_dir / "source" / "invalid.cgl"
                    source_path.parent.mkdir()
                    source_path.write_text(
                        "runtime must not parse CrossGL source for malformed "
                        "native artifact metadata\n",
                        encoding="utf-8",
                    )

                    with self._guard_crossgl_source_reads():
                        report = read_compatibility_report(
                            package_dir,
                            loader_target="metal",
                        )
                        selection = select_runtime_artifact(
                            report,
                            target="metal",
                        )

                    summary = report.to_summary()
                    selection_summary = selection.to_summary()
                    native_admission = selection_summary["admission"]["native"]

                    self.assertFalse(report.compatible)
                    self.assertEqual(report.status, expected_status)
                    self.assertFalse(report.source_parsing_required)
                    self.assertFalse(selection.selected)
                    self.assertIsNone(selection.artifact)
                    self.assertFalse(selection.source_parsing_required)
                    self.assertIn(
                        expected_code,
                        [diagnostic.code for diagnostic in report.reject_reasons],
                    )
                    self.assertNotIn(
                        "package.target.unsupported",
                        [diagnostic.code for diagnostic in report.reject_reasons],
                    )
                    self.assertEqual(native_admission["reason"], expected_code)
                    self.assertEqual(
                        selection_summary["admission"]["decision"],
                        "rejected",
                    )
                    self.assertFalse(
                        selection_summary["admission"]["compilerInvocationRequired"]
                    )
                    self.assertFalse(
                        selection_summary["admission"]["deviceExecutionRequired"]
                    )
                    self.assertIn(
                        expected_code,
                        [
                            diagnostic["code"]
                            for diagnostic in native_admission["diagnostics"]
                        ],
                    )
                    self.assertEqual(
                        next(
                            diagnostic
                            for diagnostic in summary["rejectReasons"]
                            if diagnostic["code"] == expected_code
                        )["path"],
                        expected_path,
                    )
                    artifact_compatibility = summary["artifactCompatibility"]
                    artifact_records = {
                        artifact["name"]: artifact
                        for artifact in artifact_compatibility["artifacts"]
                    }
                    self.assertIsNone(artifact_compatibility["selectedArtifact"])
                    self.assertEqual(
                        artifact_records["nativeArtifactDescriptor"]["decision"],
                        "rejected",
                    )
                    self.assertEqual(
                        artifact_records["nativeArtifactDescriptor"]["reason"],
                        expected_code,
                    )
                    self.assertEqual(
                        [
                            diagnostic["code"]
                            for diagnostic in artifact_records[
                                "nativeArtifactDescriptor"
                            ]["diagnostics"]
                        ],
                        [expected_code],
                    )
                    self.assertEqual(
                        artifact_records["nativeBinary"]["decision"],
                        "accepted",
                    )
                    self.assertEqual(
                        artifact_records["nativeBinary"]["reason"],
                        "package.artifact.accepted",
                    )
                    self.assertEqual(list(package_dir.rglob("*.cgl")), [source_path])

    def test_compatibility_report_structures_native_descriptor_contract_field_drift_without_source_parse(
        self,
    ) -> None:
        cases: tuple[tuple[str, object, str, str, object], ...] = (
            (
                "kind array",
                lambda descriptor: descriptor.__setitem__("kind", []),
                "package.native_artifact_descriptor.kind_mismatch",
                "kind",
                "array",
            ),
            (
                "contract version number",
                lambda descriptor: descriptor.__setitem__("contractVersion", 7),
                "package.native_artifact_descriptor.contract_version_mismatch",
                "contractVersion",
                "number",
            ),
            (
                "target object",
                lambda descriptor: descriptor.__setitem__(
                    "target",
                    {"name": "metal"},
                ),
                "package.native_artifact_descriptor.target_mismatch",
                "target",
                "object",
            ),
            (
                "binary kind object",
                lambda descriptor: descriptor.__setitem__(
                    "binaryKind",
                    {"kind": "metal.metallib"},
                ),
                "package.native_artifact_descriptor.binary_kind_mismatch",
                "binaryKind",
                "object",
            ),
            (
                "validation status object",
                lambda descriptor: descriptor.__setitem__(
                    "validationStatus",
                    {"status": "unavailable"},
                ),
                "package.native_artifact_descriptor.validation_status_invalid",
                "validationStatus",
                "object",
            ),
            (
                "artifact hash scalar",
                lambda descriptor: descriptor.__setitem__(
                    "artifactHash",
                    "sha256:missing-structured-fields",
                ),
                "package.native_artifact_descriptor.artifact_hash_invalid",
                "artifactHash",
                "string",
            ),
            (
                "size bytes boolean",
                lambda descriptor: descriptor.__setitem__("sizeBytes", True),
                "package.native_artifact_descriptor.size_bytes_invalid",
                "sizeBytes",
                "boolean",
            ),
            (
                "optimization evidence scalar",
                lambda descriptor: descriptor.__setitem__(
                    "optimizationEvidence",
                    "applied",
                ),
                "package.native_artifact_descriptor.optimization_evidence_invalid",
                "optimizationEvidence",
                "string",
            ),
        )

        for name, mutate, expected_code, expected_path, expected_actual in cases:
            for package_format in ("directory", "zip"):
                with self.subTest(name=name, package_format=package_format):
                    with tempfile.TemporaryDirectory() as temp_dir:
                        temp_root = Path(temp_dir)
                        package_dir = temp_root / "package-dir"
                        package_dir.mkdir()
                        self._write_valid_package(package_dir)
                        self._write_native_artifact_descriptor(
                            package_dir,
                            mutate=mutate,
                        )
                        source_path = package_dir / "source" / "invalid.cgl"
                        source_path.parent.mkdir()
                        source_path.write_text(
                            "runtime must not parse CrossGL source for native "
                            "descriptor contract drift\n",
                            encoding="utf-8",
                        )

                        if package_format == "zip":
                            package_path = temp_root / "RuntimeReaderFixture.cglb"
                            self._write_zip_package(
                                package_dir,
                                package_path,
                                prefix=package_path.name,
                            )
                            guard = self._guard_zip_crossgl_member_reads()
                        else:
                            package_path = package_dir
                            guard = self._guard_crossgl_source_reads()

                        with guard:
                            report = read_compatibility_report(
                                package_path,
                                loader_target="metal",
                            )
                            selection = select_runtime_artifact(
                                report,
                                target="metal",
                            )

                        summary = report.to_summary()
                        diagnostic = next(
                            diagnostic
                            for diagnostic in summary["rejectReasons"]
                            if diagnostic["code"] == expected_code
                        )

                        self.assertFalse(report.compatible)
                        self.assertEqual(report.status, "incompatible")
                        self.assertFalse(report.source_parsing_required)
                        self.assertFalse(selection.selected)
                        self.assertFalse(selection.source_parsing_required)
                        self.assertEqual(
                            diagnostic["document"],
                            "nativeArtifactDescriptor",
                        )
                        self.assertEqual(
                            diagnostic["artifact"],
                            "nativeArtifactDescriptor",
                        )
                        self.assertEqual(diagnostic["path"], expected_path)
                        self.assertEqual(diagnostic["actual"], expected_actual)
                        self.assertIn(
                            expected_code,
                            [diagnostic.code for diagnostic in report.reject_reasons],
                        )
                        artifact_records = {
                            artifact["name"]: artifact
                            for artifact in summary["artifactCompatibility"][
                                "artifacts"
                            ]
                        }
                        self.assertEqual(
                            artifact_records["nativeArtifactDescriptor"]["decision"],
                            "rejected",
                        )
                        self.assertEqual(
                            artifact_records["nativeArtifactDescriptor"]["reason"],
                            expected_code,
                        )

    def test_compatibility_report_rejects_malformed_recorded_package_artifact_requirements(
        self,
    ) -> None:
        valid_requirements = self._valid_metal_package_artifact_requirements()
        cases: tuple[tuple[str, object, str], ...] = (
            (
                "record not object",
                ["target", "metal"],
                "package.artifact_requirements.invalid",
            ),
            (
                "unexpected field",
                {**valid_requirements, "extraRequirement": True},
                "package.artifact_requirements.unexpected_field",
            ),
            (
                "target mismatch",
                {**valid_requirements, "target": "vulkan"},
                "package.artifact_requirements.target_mismatch",
            ),
            (
                "missing package mode",
                {
                    key: value
                    for key, value in valid_requirements.items()
                    if key != "packageMode"
                },
                "package.artifact_requirements.package_mode_missing",
            ),
            (
                "invalid package mode",
                {**valid_requirements, "packageMode": "bytecode"},
                "package.artifact_requirements.package_mode_invalid",
            ),
            (
                "required artifacts not array",
                {**valid_requirements, "requiredPathArtifacts": "nativeBinary"},
                "package.artifact_requirements.required_path_artifacts_invalid",
            ),
            (
                "required artifact not string",
                {
                    **valid_requirements,
                    "requiredPathArtifacts": ["backendSource", 7, "nativeBinary"],
                },
                "package.artifact_requirements.required_path_artifact_invalid",
            ),
            (
                "unknown required artifact",
                {
                    **valid_requirements,
                    "requiredPathArtifacts": [
                        "backendSource",
                        "shaderBlob",
                        "nativeBinary",
                    ],
                },
                "package.artifact_requirements.required_path_artifact_unknown",
            ),
            (
                "duplicate required artifact",
                {
                    **valid_requirements,
                    "requiredPathArtifacts": [
                        "backendSource",
                        "nativeBinary",
                        "nativeBinary",
                    ],
                },
                "package.artifact_requirements.required_path_artifact_duplicate",
            ),
            (
                "required artifacts conflict with target contract",
                {
                    **valid_requirements,
                    "requiredPathArtifacts": ["backendSource", "nativeBinary"],
                },
                "package.artifact_requirements.required_path_artifacts_mismatch",
            ),
            (
                "missing native binary requirement",
                {
                    **valid_requirements,
                    "requiredPathArtifacts": ["backendSource"],
                },
                "package.artifact_requirements.native_binary_missing",
            ),
            (
                "source package missing backend source",
                {
                    **valid_requirements,
                    "packageMode": "source-package",
                    "requiredPathArtifacts": ["nativeBinary"],
                    "requiresNativeBinaryStatus": True,
                    "allowsPlannedNativeBinary": True,
                    "allowsPlannedNativeSourceEvidence": True,
                },
                "package.artifact_requirements.source_package_artifact_missing",
            ),
            (
                "source package without native status",
                {
                    **valid_requirements,
                    "packageMode": "source-package",
                },
                "package.artifact_requirements.source_package_status_invalid",
            ),
            (
                "native mode requires native status",
                {
                    **valid_requirements,
                    "requiresNativeBinaryStatus": True,
                },
                "package.artifact_requirements.native_status_invalid",
            ),
            (
                "native status flag not boolean",
                {
                    **valid_requirements,
                    "requiresNativeBinaryStatus": "false",
                },
                "package.artifact_requirements.requires_native_binary_status_invalid",
            ),
            (
                "planned native flag not boolean",
                {
                    **valid_requirements,
                    "allowsPlannedNativeBinary": "false",
                },
                "package.artifact_requirements.allows_planned_native_binary_invalid",
            ),
            (
                "planned source evidence flag not boolean",
                {
                    **valid_requirements,
                    "allowsPlannedNativeSourceEvidence": "false",
                },
                (
                    "package.artifact_requirements."
                    "allows_planned_native_source_evidence_invalid"
                ),
            ),
            (
                "planned native without status",
                {
                    **valid_requirements,
                    "allowsPlannedNativeBinary": True,
                },
                "package.artifact_requirements.planned_native_status_invalid",
            ),
            (
                "planned source evidence in native mode",
                {
                    **valid_requirements,
                    "allowsPlannedNativeBinary": True,
                    "allowsPlannedNativeSourceEvidence": True,
                },
                "package.artifact_requirements.planned_source_mode_invalid",
            ),
        )

        for name, requirements, expected_code in cases:
            with self.subTest(name=name):
                expected_reason = (
                    "package.artifact_requirements.planned_native_status_invalid"
                    if name == "planned source evidence in native mode"
                    else expected_code
                )
                with tempfile.TemporaryDirectory(suffix=".cglb") as temp_dir:
                    package_dir = Path(temp_dir)
                    self._write_valid_package(
                        package_dir,
                        package_artifact_requirements=requirements,
                    )

                    report = read_compatibility_report(
                        package_dir,
                        loader_target="metal",
                    )
                    selection = select_runtime_artifact(report, target="metal")
                    summary = report.to_summary()
                    reject_codes = [
                        diagnostic.code for diagnostic in report.reject_reasons
                    ]

                    self.assertFalse(report.compatible)
                    self.assertEqual(report.status, "incompatible")
                    self.assertIsNone(report.target_contract)
                    self.assertEqual(report.required_artifacts, ())
                    self.assertTrue(
                        summary["artifactAvailability"]["native"]["declared"]
                    )
                    self.assertTrue(summary["artifactAvailability"]["native"]["exists"])
                    self.assertFalse(
                        summary["artifactAvailability"]["native"]["usable"]
                    )
                    self.assertFalse(
                        summary["admission"]["fallbacks"]["sourcePackage"][
                            "nativeUsable"
                        ]
                    )
                    self.assertIn(expected_code, reject_codes)
                    self.assertIsNone(summary["packageArtifactRequirements"])
                    self.assertTrue(summary["admission"]["requirements"]["declared"])
                    self.assertEqual(
                        summary["admission"]["requirements"]["requirementsSource"],
                        "manifest",
                    )
                    self.assertEqual(
                        summary["admission"]["requirements"]["sourceKind"],
                        "recorded",
                    )
                    self.assertIn(
                        summary["admission"]["requirements"]["compatibilityKind"],
                        ("recorded-incomplete", "recorded-invalid"),
                    )
                    self.assertEqual(
                        summary["admission"]["requirements"]["reason"],
                        expected_reason,
                    )
                    self.assertEqual(
                        summary["admission"]["requirements"]["recordedRequirements"][
                            "reason"
                        ],
                        expected_reason,
                    )
                    self.assertFalse(summary["admission"]["requirements"]["resolved"])
                    self.assertFalse(summary["admission"]["requirements"]["valid"])
                    self.assertIn(
                        expected_code,
                        [
                            diagnostic["code"]
                            for diagnostic in summary["admission"]["requirements"][
                                "diagnostics"
                            ]
                        ],
                    )
                    self.assertFalse(selection.selected)
                    self.assertIsNone(selection.artifact)
                    self.assertFalse(selection.source_parsing_required)

    def test_compatibility_report_rejects_null_recorded_package_artifact_requirements_without_legacy_fallback(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory(suffix=".cglb") as temp_dir:
            package_dir = Path(temp_dir)
            self._write_valid_package(package_dir)
            manifest_path = package_dir / "manifest.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["packageArtifactRequirements"] = None
            self._write_json(manifest_path, manifest)
            source_path = package_dir / "source" / "invalid.cgl"
            source_path.parent.mkdir()
            source_path.write_text(
                "runtime must not parse CrossGL source for null "
                "packageArtifactRequirements\n",
                encoding="utf-8",
            )

            with self._guard_crossgl_source_reads():
                package = read_package(package_dir)
                package_summary = package.to_summary()
                report = read_compatibility_report(
                    package_dir,
                    loader_target="metal",
                )
                selection = select_runtime_artifact(report, target="metal")

            summary = report.to_summary()
            reject_codes = [diagnostic.code for diagnostic in report.reject_reasons]
            requirement_summary = summary["admission"]["requirements"]

            self.assertFalse(report.compatible)
            self.assertEqual(report.status, "incompatible")
            self.assertIsNone(report.target_contract)
            self.assertEqual(report.required_artifacts, ())
            self.assertIn("package.artifact_requirements.invalid", reject_codes)
            self.assertIsNone(package.target_artifact_contract())
            self.assertEqual(package.required_target_artifacts(), ())
            self.assertIsNone(package_summary["targetContract"])
            self.assertIsNone(package_summary["packageArtifactRequirements"])
            self.assertIsNone(summary["targetContract"])
            self.assertIsNone(summary["packageArtifactRequirements"])
            self.assertTrue(requirement_summary["declared"])
            self.assertTrue(requirement_summary["recorded"])
            self.assertFalse(requirement_summary["legacyInferred"])
            self.assertEqual(requirement_summary["requirementsSource"], "manifest")
            self.assertEqual(requirement_summary["sourceKind"], "recorded")
            self.assertEqual(
                requirement_summary["compatibilityKind"],
                "recorded-invalid",
            )
            self.assertEqual(
                requirement_summary["reason"],
                "package.artifact_requirements.invalid",
            )
            self.assertEqual(
                requirement_summary["recordedRequirements"]["reason"],
                "package.artifact_requirements.invalid",
            )
            self.assertFalse(requirement_summary["resolved"])
            self.assertFalse(requirement_summary["valid"])
            self.assertIn(
                "package.artifact_requirements.invalid",
                [
                    diagnostic["code"]
                    for diagnostic in requirement_summary["diagnostics"]
                ],
            )
            self.assertFalse(selection.selected)
            self.assertIsNone(selection.artifact)
            self.assertFalse(report.source_parsing_required)
            self.assertFalse(selection.source_parsing_required)
            self.assertEqual(list(package_dir.rglob("*.cgl")), [source_path])

    def test_compatibility_report_marks_incomplete_recorded_requirements_without_legacy_fallback(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory(suffix=".cglb") as temp_dir:
            package_dir = Path(temp_dir)
            requirements = self._valid_metal_package_artifact_requirements()
            del requirements["requiredPathArtifacts"]
            self._write_valid_package(
                package_dir,
                package_artifact_requirements=requirements,
            )
            source_path = package_dir / "source" / "invalid.cgl"
            source_path.parent.mkdir()
            source_path.write_text(
                "runtime must not infer legacy requirements for incomplete "
                "packageArtifactRequirements\n",
                encoding="utf-8",
            )

            with self._guard_crossgl_source_reads():
                report = read_compatibility_report(
                    package_dir,
                    loader_target="metal",
                )
                selection = select_runtime_artifact(report, target="metal")

            summary = report.to_summary()
            requirement_summary = summary["packageArtifactRequirementsStatus"]

            self.assertFalse(report.compatible)
            self.assertEqual(report.status, "incompatible")
            self.assertIsNone(report.target_contract)
            self.assertEqual(report.required_artifacts, ())
            self.assertIsNone(summary["packageArtifactRequirements"])
            self.assertTrue(requirement_summary["declared"])
            self.assertTrue(requirement_summary["recorded"])
            self.assertFalse(requirement_summary["legacyInferred"])
            self.assertEqual(requirement_summary["requirementsSource"], "manifest")
            self.assertEqual(requirement_summary["sourceKind"], "recorded")
            self.assertEqual(
                requirement_summary["compatibilityKind"],
                "recorded-incomplete",
            )
            self.assertEqual(
                requirement_summary["reason"],
                "package.artifact_requirements.required_path_artifacts_missing",
            )
            self.assertEqual(
                requirement_summary["recordedRequirements"]["reason"],
                "package.artifact_requirements.required_path_artifacts_missing",
            )
            self.assertFalse(requirement_summary["complete"])
            self.assertFalse(requirement_summary["resolved"])
            self.assertFalse(requirement_summary["valid"])
            self.assertFalse(
                requirement_summary["legacyGeneratedRequirements"]["compatibilityOnly"]
            )
            self.assertIn(
                "package.artifact_requirements.required_path_artifacts_missing",
                [diagnostic.code for diagnostic in report.reject_reasons],
            )
            self.assertFalse(selection.selected)
            self.assertIsNone(selection.artifact)
            self.assertFalse(report.source_parsing_required)
            self.assertFalse(selection.source_parsing_required)
            self.assertEqual(list(package_dir.rglob("*.cgl")), [source_path])

    def test_compatibility_report_does_not_mark_ready_native_usable_without_valid_contract(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory(suffix=".cglb") as temp_dir:
            package_dir = Path(temp_dir)
            self._write_valid_package(
                package_dir,
                target="directx",
                native_status="emitted",
                package_artifact_requirements={
                    "target": "directx",
                    "packageMode": "bytecode",
                    "requiredPathArtifacts": ["backendSource", "nativeBinary"],
                    "requiresNativeBinaryStatus": True,
                    "allowsPlannedNativeBinary": True,
                    "allowsPlannedNativeSourceEvidence": True,
                },
            )
            source_path = package_dir / "source" / "invalid.cgl"
            source_path.parent.mkdir()
            source_path.write_text(
                "runtime must not infer native usability from ready status "
                "when packageArtifactRequirements is malformed\n",
                encoding="utf-8",
            )

            with self._guard_crossgl_source_reads():
                report = read_compatibility_report(
                    package_dir,
                    loader_target="directx",
                )
                selection = select_runtime_artifact(report, target="directx")

            summary = report.to_summary()

            self.assertFalse(report.compatible)
            self.assertEqual(report.status, "incompatible")
            self.assertIsNone(report.target_contract)
            self.assertEqual(report.native_binary_status, "emitted")
            self.assertTrue(summary["artifactAvailability"]["native"]["declared"])
            self.assertTrue(summary["artifactAvailability"]["native"]["exists"])
            self.assertFalse(summary["artifactAvailability"]["native"]["usable"])
            self.assertFalse(
                summary["admission"]["fallbacks"]["sourcePackage"]["nativeUsable"]
            )
            self.assertIn(
                "package.artifact_requirements.package_mode_invalid",
                [diagnostic.code for diagnostic in report.reject_reasons],
            )
            self.assertFalse(selection.selected)
            self.assertIsNone(selection.artifact)
            self.assertFalse(selection.source_parsing_required)
            self.assertEqual(list(package_dir.rglob("*.cgl")), [source_path])

    def test_compatibility_report_rejects_evolved_recorded_package_artifact_requirements(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory(suffix=".cglb") as temp_dir:
            package_dir = Path(temp_dir)
            self._write_valid_package(
                package_dir,
                package_artifact_requirements={
                    **self._valid_metal_package_artifact_requirements(),
                    "schemaVersion": 2,
                },
            )
            source_path = package_dir / "source" / "invalid.cgl"
            source_path.parent.mkdir()
            source_path.write_text(
                "runtime must not parse CrossGL source for evolved "
                "packageArtifactRequirements\n",
                encoding="utf-8",
            )

            with self._guard_crossgl_source_reads():
                report = read_compatibility_report(
                    package_dir,
                    loader_target="metal",
                )
                selection = select_runtime_artifact(report, target="metal")

            summary = report.to_summary()

            self.assertFalse(report.compatible)
            self.assertEqual(report.status, "unsupported-version")
            self.assertIsNone(report.target_contract)
            self.assertEqual(report.required_artifacts, ())
            self.assertFalse(report.source_parsing_required)
            self.assertFalse(selection.selected)
            self.assertFalse(selection.source_parsing_required)
            self.assertEqual(
                summary["admission"]["requirements"]["diagnostics"],
                [
                    {
                        "severity": "error",
                        "code": ("package.artifact_requirements.schema_incompatible"),
                        "message": (
                            "manifest.packageArtifactRequirements.schemaVersion "
                            "is not supported by this runtime"
                        ),
                        "document": "manifest",
                        "path": "packageArtifactRequirements.schemaVersion",
                        "expected": "absent in manifest schema v1",
                        "actual": 2,
                    }
                ],
            )
            self.assertEqual(
                summary["admission"]["requirements"]["reason"],
                "package.artifact_requirements.schema_incompatible",
            )
            self.assertEqual(
                summary["admission"]["requirements"]["recordedRequirements"]["reason"],
                "package.artifact_requirements.schema_incompatible",
            )
            self.assertEqual(summary["packageArtifactRequirements"], None)
            self.assertNotIn(
                "package.artifact_requirements.unexpected_field",
                [diagnostic.code for diagnostic in report.requirement_diagnostics],
            )
            self.assertEqual(list(package_dir.rglob("*.cgl")), [source_path])

    def test_evolved_recorded_requirements_do_not_infer_v0_policy_without_source_parse(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory(suffix=".cglb") as temp_dir:
            package_dir = Path(temp_dir)
            self._write_valid_package(
                package_dir,
                target="directx",
                package_artifact_requirements={
                    "schemaVersion": 2,
                    "target": "directx",
                    "packageMode": "native",
                    "requiredPathArtifacts": ["nativeBinary"],
                    "requiresNativeBinaryStatus": False,
                    "allowsPlannedNativeBinary": False,
                    "allowsPlannedNativeSourceEvidence": False,
                },
            )
            source_path = package_dir / "source" / "invalid.cgl"
            source_path.parent.mkdir()
            source_path.write_text(
                "runtime must not parse CrossGL source or reinterpret evolved "
                "packageArtifactRequirements through v0 policy\n",
                encoding="utf-8",
            )

            with self._guard_crossgl_source_reads():
                report = read_compatibility_report(
                    package_dir,
                    loader_target="directx",
                )
                selection = select_runtime_artifact(report, target="directx")

            summary = report.to_summary()
            requirement_codes = [
                diagnostic.code for diagnostic in report.requirement_diagnostics
            ]

            self.assertFalse(report.compatible)
            self.assertEqual(report.status, "unsupported-version")
            self.assertIsNone(report.target_contract)
            self.assertEqual(report.required_artifacts, ())
            self.assertEqual(
                requirement_codes,
                ["package.artifact_requirements.schema_incompatible"],
            )
            self.assertNotIn(
                "package.artifact_requirements.package_mode_mismatch",
                requirement_codes,
            )
            self.assertNotIn(
                "package.artifact_requirements.requires_native_binary_status_mismatch",
                requirement_codes,
            )
            self.assertEqual(
                summary["packageArtifactRequirementsStatus"]["reason"],
                "package.artifact_requirements.schema_incompatible",
            )
            self.assertEqual(summary["packageArtifactRequirements"], None)
            self.assertFalse(selection.selected)
            self.assertIsNone(selection.artifact)
            self.assertFalse(report.source_parsing_required)
            self.assertFalse(selection.source_parsing_required)
            self.assertEqual(list(package_dir.rglob("*.cgl")), [source_path])

    def test_zip_recorded_requirement_contract_edges_do_not_infer_v0_policy(
        self,
    ) -> None:
        base_requirements: dict[str, object] = {
            "target": "directx",
            "packageMode": "native",
            "requiredPathArtifacts": ["nativeBinary"],
            "requiresNativeBinaryStatus": False,
            "allowsPlannedNativeBinary": False,
            "allowsPlannedNativeSourceEvidence": False,
        }
        cases: tuple[tuple[str, dict[str, object], str, str], ...] = (
            (
                "evolved schema",
                {**base_requirements, "schemaVersion": 2},
                "package.artifact_requirements.schema_incompatible",
                "unsupported-version",
            ),
            (
                "unknown contract key",
                {**base_requirements, "artifactFlavor": "compressed"},
                "package.artifact_requirements.unexpected_field",
                "incompatible",
            ),
        )

        for name, requirements, expected_code, expected_status in cases:
            with self.subTest(name=name):
                with tempfile.TemporaryDirectory() as temp_dir:
                    temp_root = Path(temp_dir)
                    package_dir = temp_root / "package-dir"
                    package_dir.mkdir()
                    self._write_valid_package(
                        package_dir,
                        target="directx",
                        package_artifact_requirements=requirements,
                    )
                    source_path = package_dir / "source" / "invalid.cgl"
                    source_path.parent.mkdir()
                    source_path.write_text(
                        "runtime must not parse zip CrossGL source or "
                        "reinterpret recorded requirements through v0 policy\n",
                        encoding="utf-8",
                    )
                    zip_path = temp_root / "RuntimeReaderFixture.cglb"
                    self._write_zip_package(
                        package_dir,
                        zip_path,
                        prefix=zip_path.name,
                    )

                    with self._guard_zip_crossgl_member_reads():
                        report = read_compatibility_report(
                            zip_path,
                            loader_target="directx",
                        )
                        selection = select_runtime_artifact(
                            report,
                            target="directx",
                        )

                    summary = report.to_summary()
                    requirement_codes = [
                        diagnostic.code for diagnostic in report.requirement_diagnostics
                    ]
                    requirement_summary = summary["packageArtifactRequirementsStatus"]

                    self.assertFalse(report.compatible)
                    self.assertEqual(report.status, expected_status)
                    self.assertEqual(summary["packageFormat"], "zip")
                    self.assertIsNone(report.target_contract)
                    self.assertEqual(report.required_artifacts, ())
                    self.assertEqual(requirement_codes, [expected_code])
                    self.assertNotIn(
                        "package.artifact_requirements.package_mode_mismatch",
                        requirement_codes,
                    )
                    self.assertNotIn(
                        (
                            "package.artifact_requirements."
                            "requires_native_binary_status_mismatch"
                        ),
                        requirement_codes,
                    )
                    self.assertFalse(requirement_summary["legacyInferred"])
                    self.assertEqual(
                        requirement_summary["requirementsSource"],
                        "manifest",
                    )
                    self.assertEqual(requirement_summary["sourceKind"], "recorded")
                    self.assertEqual(requirement_summary["reason"], expected_code)
                    self.assertFalse(requirement_summary["resolved"])
                    self.assertFalse(requirement_summary["valid"])
                    self.assertEqual(summary["packageArtifactRequirements"], None)
                    self.assertFalse(selection.selected)
                    self.assertIsNone(selection.artifact)
                    self.assertFalse(report.source_parsing_required)
                    self.assertFalse(selection.source_parsing_required)
                    with zipfile.ZipFile(zip_path) as archive:
                        self.assertIn(
                            f"{zip_path.name}/source/invalid.cgl",
                            archive.namelist(),
                        )

    def test_compatibility_report_structures_recorded_requirement_shape_errors(
        self,
    ) -> None:
        valid_requirements = self._valid_metal_package_artifact_requirements()
        cases: tuple[tuple[str, dict[str, object], dict[str, object]], ...] = (
            (
                "target object",
                {**valid_requirements, "target": {"name": "metal"}},
                {
                    "severity": "error",
                    "code": "package.artifact_requirements.target_invalid",
                    "message": (
                        "manifest.packageArtifactRequirements.target is invalid"
                    ),
                    "document": "manifest",
                    "path": "packageArtifactRequirements.target",
                    "expected": "non-empty string",
                    "actual": "object",
                },
            ),
            (
                "native status array",
                {
                    **valid_requirements,
                    "requiresNativeBinaryStatus": ["false"],
                },
                {
                    "severity": "error",
                    "code": (
                        "package.artifact_requirements."
                        "requires_native_binary_status_invalid"
                    ),
                    "message": (
                        "manifest.packageArtifactRequirements."
                        "requiresNativeBinaryStatus must be a boolean"
                    ),
                    "document": "manifest",
                    "path": ("packageArtifactRequirements.requiresNativeBinaryStatus"),
                    "expected": "boolean",
                    "actual": "array",
                },
            ),
            (
                "empty required paths",
                {**valid_requirements, "requiredPathArtifacts": []},
                {
                    "severity": "error",
                    "code": (
                        "package.artifact_requirements.required_path_artifacts_invalid"
                    ),
                    "message": (
                        "manifest.packageArtifactRequirements."
                        "requiredPathArtifacts must be a non-empty array"
                    ),
                    "document": "manifest",
                    "path": ("packageArtifactRequirements.requiredPathArtifacts"),
                    "expected": "non-empty string array",
                    "actual": "array",
                },
            ),
            (
                "invalid evidence ids",
                {**valid_requirements, "evidenceIds": ["valid", ""]},
                {
                    "severity": "error",
                    "code": (
                        "package.artifact_requirements.evidence_ids_entry_invalid"
                    ),
                    "message": (
                        "manifest.packageArtifactRequirements.evidenceIds entries "
                        "must be non-empty strings"
                    ),
                    "document": "manifest",
                    "path": "packageArtifactRequirements.evidenceIds[1]",
                    "expected": "non-empty string",
                    "actual": "",
                },
            ),
            (
                "future selection hints",
                {**valid_requirements, "selectionHints": {"prefer": "native"}},
                {
                    "severity": "error",
                    "code": "package.artifact_requirements.unexpected_field",
                    "message": (
                        "manifest.packageArtifactRequirements contains an "
                        "unexpected field: selectionHints"
                    ),
                    "document": "manifest",
                    "path": "packageArtifactRequirements.selectionHints",
                    "expected": sorted(
                        package_reader_module.PACKAGE_ARTIFACT_REQUIREMENT_KEYS
                    ),
                    "actual": "selectionHints",
                },
            ),
        )

        for name, requirements, expected_diagnostic in cases:
            with self.subTest(name=name):
                with tempfile.TemporaryDirectory(suffix=".cglb") as temp_dir:
                    package_dir = Path(temp_dir)
                    self._write_valid_package(
                        package_dir,
                        package_artifact_requirements=requirements,
                    )
                    source_path = package_dir / "source" / "invalid.cgl"
                    source_path.parent.mkdir()
                    source_path.write_text(
                        "runtime must not parse CrossGL source for malformed "
                        "packageArtifactRequirements\n",
                        encoding="utf-8",
                    )

                    with self._guard_crossgl_source_reads():
                        report = read_compatibility_report(
                            package_dir,
                            loader_target="metal",
                        )

                    summary = report.to_summary()

                    self.assertFalse(report.compatible)
                    self.assertEqual(report.status, "incompatible")
                    self.assertIsNone(report.target_contract)
                    self.assertEqual(report.required_artifacts, ())
                    self.assertFalse(report.source_parsing_required)
                    self.assertIn(
                        expected_diagnostic,
                        summary["admission"]["requirements"]["diagnostics"],
                    )
                    self.assertEqual(summary["packageArtifactRequirements"], None)
                    self.assertEqual(list(package_dir.rglob("*.cgl")), [source_path])

    def test_compatibility_report_rejects_recorded_requirement_source_fields_without_source_parse(
        self,
    ) -> None:
        valid_requirements = self._valid_metal_package_artifact_requirements()
        cases: tuple[tuple[str, object, str], ...] = (
            (
                "requirementsSource",
                "legacy-v0-target-contract",
                "package.artifact_requirements.requirements_source_invalid",
            ),
            (
                "requirements_source",
                "manifest",
                "package.artifact_requirements.requirements_source_invalid",
            ),
            (
                "contractSource",
                "legacy-v0-target-contract",
                "package.artifact_requirements.contract_source_invalid",
            ),
        )

        for field, value, expected_code in cases:
            with self.subTest(field=field):
                with tempfile.TemporaryDirectory(suffix=".cglb") as temp_dir:
                    package_dir = Path(temp_dir)
                    self._write_valid_package(
                        package_dir,
                        package_artifact_requirements={
                            **valid_requirements,
                            field: value,
                        },
                    )
                    source_path = package_dir / "source" / "invalid.cgl"
                    source_path.parent.mkdir()
                    source_path.write_text(
                        "runtime must not parse CrossGL source for forged "
                        "packageArtifactRequirements source fields\n",
                        encoding="utf-8",
                    )

                    with self._guard_crossgl_source_reads():
                        report = read_compatibility_report(
                            package_dir,
                            loader_target="metal",
                        )
                        selection = select_runtime_artifact(report, target="metal")

                    summary = report.to_summary()
                    requirement_summary = summary["packageArtifactRequirementsStatus"]
                    diagnostic = next(
                        diagnostic
                        for diagnostic in requirement_summary["diagnostics"]
                        if diagnostic["code"] == expected_code
                    )

                    self.assertFalse(report.compatible)
                    self.assertEqual(report.status, "incompatible")
                    self.assertIsNone(report.target_contract)
                    self.assertEqual(report.required_artifacts, ())
                    self.assertFalse(report.source_parsing_required)
                    self.assertFalse(selection.selected)
                    self.assertFalse(selection.source_parsing_required)
                    self.assertIsNone(summary["packageArtifactRequirements"])
                    self.assertTrue(requirement_summary["declared"])
                    self.assertFalse(requirement_summary["legacyInferred"])
                    self.assertEqual(
                        requirement_summary["requirementsSource"],
                        "manifest",
                    )
                    self.assertEqual(requirement_summary["sourceKind"], "recorded")
                    self.assertEqual(requirement_summary["reason"], expected_code)
                    self.assertEqual(
                        requirement_summary["recordedRequirements"]["reason"],
                        expected_code,
                    )
                    self.assertEqual(
                        [diagnostic.code for diagnostic in report.reject_reasons],
                        [expected_code],
                    )
                    self.assertEqual(
                        [
                            diagnostic.code
                            for diagnostic in report.requirement_diagnostics
                        ],
                        [expected_code],
                    )
                    self.assertEqual(
                        diagnostic,
                        {
                            "severity": "error",
                            "code": expected_code,
                            "message": (
                                "manifest.packageArtifactRequirements must not "
                                f"declare {field}; the runtime derives the "
                                "contract source"
                            ),
                            "document": "manifest",
                            "path": f"packageArtifactRequirements.{field}",
                            "expected": "absent; runtime-derived contract source",
                            "actual": value,
                        },
                    )
                    self.assertEqual(list(package_dir.rglob("*.cgl")), [source_path])

    def test_compatibility_report_rejects_recorded_requirements_conflicting_with_manifest_or_v0_contract_without_source_parse(
        self,
    ) -> None:
        cases: tuple[tuple[str, str, dict[str, object], str, str], ...] = (
            (
                "target mismatch",
                "metal",
                {
                    "target": "directx",
                    "packageMode": "source-package",
                    "requiredPathArtifacts": ["backendSource", "nativeBinary"],
                    "requiresNativeBinaryStatus": True,
                    "allowsPlannedNativeBinary": True,
                    "allowsPlannedNativeSourceEvidence": True,
                },
                "package.artifact_requirements.target_mismatch",
                "packageArtifactRequirements.target",
            ),
            (
                "metal recorded as source-package",
                "metal",
                {
                    "target": "metal",
                    "packageMode": "source-package",
                    "requiredPathArtifacts": ["backendSource", "nativeBinary"],
                    "requiresNativeBinaryStatus": True,
                    "allowsPlannedNativeBinary": True,
                    "allowsPlannedNativeSourceEvidence": True,
                },
                "package.artifact_requirements.package_mode_mismatch",
                "packageArtifactRequirements.packageMode",
            ),
            (
                "directx recorded as native",
                "directx",
                {
                    "target": "directx",
                    "packageMode": "native",
                    "requiredPathArtifacts": ["backendSource", "nativeBinary"],
                    "requiresNativeBinaryStatus": False,
                    "allowsPlannedNativeBinary": False,
                    "allowsPlannedNativeSourceEvidence": False,
                },
                "package.artifact_requirements.package_mode_mismatch",
                "packageArtifactRequirements.packageMode",
            ),
            (
                "directx native-only without descriptor",
                "directx",
                {
                    "target": "directx",
                    "packageMode": "native",
                    "requiredPathArtifacts": ["nativeBinary"],
                    "requiresNativeBinaryStatus": False,
                    "allowsPlannedNativeBinary": False,
                    "allowsPlannedNativeSourceEvidence": False,
                },
                "package.artifact_requirements.package_mode_mismatch",
                "packageArtifactRequirements.packageMode",
            ),
            (
                "directx planned status disallowed",
                "directx",
                {
                    "target": "directx",
                    "packageMode": "source-package",
                    "requiredPathArtifacts": ["backendSource", "nativeBinary"],
                    "requiresNativeBinaryStatus": True,
                    "allowsPlannedNativeBinary": False,
                    "allowsPlannedNativeSourceEvidence": False,
                },
                "package.artifact_requirements.allows_planned_native_binary_mismatch",
                "packageArtifactRequirements.allowsPlannedNativeBinary",
            ),
        )

        for name, target, requirements, expected_code, expected_path in cases:
            with self.subTest(name=name):
                with tempfile.TemporaryDirectory(suffix=".cglb") as temp_dir:
                    package_dir = Path(temp_dir)
                    self._write_valid_package(
                        package_dir,
                        target=target,
                        package_artifact_requirements=requirements,
                    )
                    source_path = package_dir / "source" / "invalid.cgl"
                    source_path.parent.mkdir()
                    source_path.write_text(
                        "runtime must not parse CrossGL source for recorded "
                        "requirement contract contradictions\n",
                        encoding="utf-8",
                    )

                    with self._guard_crossgl_source_reads():
                        report = read_compatibility_report(
                            package_dir,
                            loader_target=target,
                        )
                        selection = select_runtime_artifact(report, target=target)

                    summary = report.to_summary()
                    reject_codes = [
                        diagnostic.code for diagnostic in report.reject_reasons
                    ]
                    requirement_codes = [
                        diagnostic.code for diagnostic in report.requirement_diagnostics
                    ]

                    self.assertFalse(report.compatible)
                    self.assertEqual(report.status, "incompatible")
                    self.assertIsNone(report.target_contract)
                    self.assertEqual(report.required_artifacts, ())
                    self.assertIn(expected_code, reject_codes)
                    self.assertIn(expected_code, requirement_codes)
                    self.assertEqual(
                        next(
                            diagnostic
                            for diagnostic in summary["rejectReasons"]
                            if diagnostic["code"] == expected_code
                        )["path"],
                        expected_path,
                    )
                    self.assertIsNone(summary["packageArtifactRequirements"])
                    self.assertTrue(summary["admission"]["requirements"]["declared"])
                    self.assertFalse(
                        summary["admission"]["requirements"]["legacyInferred"]
                    )
                    self.assertEqual(
                        summary["admission"]["requirements"]["requirementsSource"],
                        "manifest",
                    )
                    self.assertEqual(
                        summary["admission"]["requirements"]["reason"],
                        expected_code,
                    )
                    self.assertEqual(
                        summary["admission"]["requirements"]["recordedRequirements"][
                            "reason"
                        ],
                        expected_code,
                    )
                    self.assertFalse(summary["admission"]["requirements"]["resolved"])
                    self.assertFalse(summary["sourceParsingRequired"])
                    self.assertFalse(selection.selected)
                    self.assertFalse(selection.source_parsing_required)
                    self.assertEqual(list(package_dir.rglob("*.cgl")), [source_path])

    def test_compatibility_report_rejects_zip_recorded_requirement_contract_conflict_without_source_member_reads(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir)
            package_dir = temp_root / "package-dir"
            package_dir.mkdir()
            self._write_valid_package(
                package_dir,
                package_artifact_requirements={
                    "target": "metal",
                    "packageMode": "source-package",
                    "requiredPathArtifacts": ["backendSource", "nativeBinary"],
                    "requiresNativeBinaryStatus": True,
                    "allowsPlannedNativeBinary": True,
                    "allowsPlannedNativeSourceEvidence": True,
                },
            )
            source_path = package_dir / "source" / "invalid.cgl"
            source_path.parent.mkdir()
            source_path.write_text(
                "runtime must not parse zipped CrossGL source for recorded "
                "requirement contract contradictions\n",
                encoding="utf-8",
            )
            zip_path = temp_root / "RuntimeReaderFixture.cglb"
            self._write_zip_package(
                package_dir,
                zip_path,
                prefix="RuntimeReaderFixture.cglb",
            )

            with self._guard_zip_crossgl_member_reads():
                report = read_compatibility_report(zip_path, loader_target="metal")
                selection = select_runtime_artifact(report, target="metal")

            summary = report.to_summary()

            self.assertFalse(report.compatible)
            self.assertEqual(report.status, "incompatible")
            self.assertEqual(summary["packageFormat"], "zip")
            self.assertFalse(report.source_parsing_required)
            self.assertFalse(selection.selected)
            self.assertFalse(selection.source_parsing_required)
            self.assertFalse(summary["compilerInvocationRequired"])
            self.assertFalse(summary["admission"]["compilerInvocationRequired"])
            self.assertIsNone(summary["packageArtifactRequirements"])
            self.assertEqual(
                summary["admission"]["requirements"]["reason"],
                "package.artifact_requirements.package_mode_mismatch",
            )
            self.assertEqual(
                summary["admission"]["requirements"]["recordedRequirements"]["reason"],
                "package.artifact_requirements.package_mode_mismatch",
            )
            self.assertIn(
                "package.artifact_requirements.package_mode_mismatch",
                [diagnostic.code for diagnostic in report.requirement_diagnostics],
            )
            with zipfile.ZipFile(zip_path) as archive:
                self.assertIn(
                    "RuntimeReaderFixture.cglb/source/invalid.cgl",
                    archive.namelist(),
                )

    def test_compatibility_report_accepts_directx_source_free_native_requirements_without_source_parse(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory(suffix=".cglb") as temp_dir:
            package_dir = Path(temp_dir)
            self._write_valid_package(
                package_dir,
                target="directx",
                native_status="emitted",
            )
            self._write_native_artifact_descriptor(
                package_dir,
                mutate=lambda descriptor: descriptor.pop(
                    "nativeBinaryStatus",
                    None,
                ),
            )
            self._make_source_free_native_package(package_dir)
            source_path = package_dir / "source" / "RuntimeReaderFixture.cgl"
            source_path.parent.mkdir()
            source_path.write_text(
                "runtime must not parse CrossGL source for source-free "
                "DirectX native requirements\n",
                encoding="utf-8",
            )

            with self._guard_crossgl_source_reads():
                report = read_compatibility_report(
                    package_dir,
                    loader_target="directx",
                )
                selection = select_runtime_artifact(report, target="directx")

            summary = report.to_summary()

            self.assertTrue(report.compatible, summary["diagnostics"])
            self.assertEqual(report.status, "compatible")
            self.assertEqual(report.required_artifacts, ("nativeBinary",))
            self.assertEqual(report.target_contract.requirements_source, "manifest")
            self.assertEqual(report.target_contract.package_mode, "native")
            self.assertFalse(report.target_contract.native_binary_status_required)
            self.assertEqual(
                summary["packageArtifactRequirements"]["requiredPathArtifacts"],
                ["nativeBinary"],
            )
            self.assertFalse(summary["sourceParsingRequired"])
            self.assertTrue(selection.selected, selection.to_summary()["diagnostics"])
            self.assertEqual(selection.require_selected().name, "nativeBinary")
            self.assertNotIn(
                "backendSource",
                [artifact.name for artifact in report.available_artifacts],
            )
            self.assertIn(
                "nativeArtifactDescriptor",
                [artifact.name for artifact in report.available_artifacts],
            )
            self.assertEqual(list(package_dir.rglob("*.cgl")), [source_path])

    def test_compatibility_report_rejects_source_free_requirements_for_unknown_target_without_source_parse(
        self,
    ) -> None:
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

        with tempfile.TemporaryDirectory(suffix=".cglb") as temp_dir:
            package_dir = Path(temp_dir)
            self._write_valid_package(package_dir, target="webgpu")
            self._make_source_free_native_package(package_dir)
            source_path = package_dir / "source" / "invalid.cgl"
            source_path.parent.mkdir()
            source_path.write_text(
                "runtime must not parse CrossGL source for unsupported target "
                "requirements\n",
                encoding="utf-8",
            )

            with mock.patch.object(Path, "read_text", guarded_read_text):
                with mock.patch.object(Path, "read_bytes", guarded_read_bytes):
                    report = read_compatibility_report(
                        package_dir,
                        loader_target="webgpu",
                    )
                    selection = select_runtime_artifact(report, target="webgpu")

            summary = report.to_summary()

            self.assertFalse(report.compatible)
            self.assertEqual(report.status, "incompatible")
            self.assertIsNone(report.target_contract)
            self.assertEqual(report.required_artifacts, ())
            self.assertFalse(report.source_parsing_required)
            self.assertFalse(selection.selected)
            self.assertIsNone(selection.artifact)
            self.assertFalse(selection.source_parsing_required)
            self.assertNotIn(
                "backendSource",
                [artifact.name for artifact in report.available_artifacts],
            )
            self.assertIn(
                "package.artifact_requirements.target_unsupported",
                [diagnostic.code for diagnostic in report.reject_reasons],
            )
            self.assertEqual(summary["admission"]["decision"], "rejected")
            self.assertEqual(
                summary["admission"]["target"]["category"],
                "target-unsupported",
            )
            self.assertTrue(summary["admission"]["fallbacks"]["sourceFreePackage"])
            self.assertFalse(
                summary["admission"]["fallbacks"]["source"]["fallbackAllowed"]
            )
            self.assertFalse(
                summary["admission"]["fallbacks"]["source"]["fallbackAttempted"]
            )
            self.assertFalse(
                summary["admission"]["fallbacks"]["compiler"]["fallbackAllowed"]
            )
            self.assertFalse(
                summary["admission"]["fallbacks"]["compiler"]["fallbackAttempted"]
            )
            self.assertEqual(
                next(
                    diagnostic
                    for diagnostic in summary["rejectReasons"]
                    if diagnostic["code"]
                    == "package.artifact_requirements.target_unsupported"
                ),
                {
                    "severity": "error",
                    "code": "package.artifact_requirements.target_unsupported",
                    "message": (
                        "manifest.packageArtifactRequirements.target is not "
                        "supported by this runtime"
                    ),
                    "document": "manifest",
                    "path": "packageArtifactRequirements.target",
                    "expected": ["directx", "metal", "opengl", "vulkan"],
                    "actual": "webgpu",
                },
            )
            self.assertIsNone(summary["packageArtifactRequirements"])
            self.assertEqual(list(package_dir.rglob("*.cgl")), [source_path])

    def test_compatibility_report_legacy_manifest_still_requires_legacy_artifacts(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory(suffix=".cglb") as temp_dir:
            package_dir = Path(temp_dir)
            self._write_valid_package(package_dir)
            (package_dir / "backend" / "metal" / "RuntimeReaderFixture.air").unlink()
            manifest_path = package_dir / "manifest.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            del manifest["artifacts"]["intermediate"]
            self._write_json(manifest_path, manifest)

            report = read_compatibility_report(package_dir, loader_target="metal")
            summary = report.to_summary()

            self.assertFalse(report.compatible)
            self.assertEqual(report.status, "missing-artifact")
            self.assertEqual(
                report.target_contract.requirements_source,
                "legacy-v0-target-contract",
            )
            self.assertEqual(
                summary["targetContract"]["requirementsSource"],
                "legacy-v0-target-contract",
            )
            self.assertEqual(
                summary["admission"]["requirements"]["requirementsSource"],
                "legacy-v0-target-contract",
            )
            self.assertTrue(summary["admission"]["requirements"]["legacyInferred"])
            self.assertEqual(
                report.required_artifacts,
                ("backendSource", "intermediate", "nativeBinary"),
            )
            self.assertEqual(
                [diagnostic["artifact"] for diagnostic in summary["missingArtifacts"]],
                ["intermediate"],
            )

    def test_compatibility_report_exposes_stable_availability_summary(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory(suffix=".cglb") as temp_dir:
            package_dir = Path(temp_dir)
            self._write_valid_package(
                package_dir,
                target="directx",
                emit_debug_metadata=True,
            )
            (package_dir / "backend" / "directx" / "RuntimeReaderFixture.dxil").unlink()

            report = read_compatibility_report(package_dir, loader_target="directx")
            summary = report.to_summary()
            availability = report.availability_summary

            self.assertTrue(report.compatible, summary["diagnostics"])
            self.assertEqual(summary["status"], "source-only")
            self.assertEqual(summary["availability"], availability)
            self.assertEqual(
                set(availability),
                {"schemaVersion", "targets", "sidecars", "artifacts"},
            )
            self.assertEqual(
                availability["targets"],
                {
                    "manifestTarget": "directx",
                    "reflectionTarget": "directx",
                    "targetResourceBindingTargets": ["directx"],
                    "targetFeatureTargets": ["directx"],
                    "availableTargets": ["directx"],
                },
            )
            self.assertEqual(
                set(availability["sidecars"]),
                {"manifest", "reflection", "diagnostics", "debugMetadata"},
            )
            self.assertEqual(
                set(availability["artifacts"]),
                {"required", "declared", "runtime", "missing"},
            )
            self.assertEqual(availability["schemaVersion"], 1)
            self.assertEqual(
                availability["sidecars"]["manifest"],
                {"declared": True, "schemaVersion": 1, "compatible": True},
            )
            self.assertEqual(
                availability["sidecars"]["reflection"]["entryPointCount"],
                1,
            )
            self.assertEqual(
                availability["sidecars"]["diagnostics"]["diagnosticCount"],
                1,
            )
            self.assertEqual(
                availability["sidecars"]["debugMetadata"]["path"],
                "ir/debug-metadata.json",
            )
            self.assertTrue(availability["sidecars"]["debugMetadata"]["exists"])
            self.assertTrue(availability["sidecars"]["debugMetadata"]["compatible"])
            self.assertEqual(
                availability["artifacts"]["required"],
                ["backendSource", "nativeBinary"],
            )
            self.assertEqual(
                [
                    artifact["name"]
                    for artifact in availability["artifacts"]["declared"]
                ],
                ["backendSource", "debugMetadata", "nativeBinary"],
            )
            self.assertTrue(availability["artifacts"]["runtime"]["source"]["available"])
            self.assertEqual(
                availability["artifacts"]["runtime"]["native"]["nativeBinaryStatus"],
                "planned",
            )
            self.assertFalse(availability["artifacts"]["runtime"]["native"]["exists"])
            self.assertFalse(availability["artifacts"]["runtime"]["native"]["usable"])
            self.assertEqual(availability["artifacts"]["missing"], [])

    def test_compatibility_report_structures_missing_artifacts(self) -> None:
        with tempfile.TemporaryDirectory(suffix=".cglb") as temp_dir:
            package_dir = Path(temp_dir)
            self._write_valid_package(package_dir)
            (package_dir / "backend" / "metal" / "RuntimeReaderFixture.metal").unlink()
            manifest_path = package_dir / "manifest.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            del manifest["artifacts"]["intermediate"]
            self._write_json(manifest_path, manifest)

            package = read_package(package_dir)
            report = package.compatibility_report()
            summary = report.to_summary()

            self.assertFalse(report.compatible)
            self.assertEqual(report.status, "missing-artifact")
            self.assertEqual(
                [diagnostic.code for diagnostic in report.missing_artifacts],
                [
                    "package.artifact.required_file_missing",
                    "package.artifact.required_missing",
                ],
            )
            self.assertEqual(
                [diagnostic["artifact"] for diagnostic in summary["missingArtifacts"]],
                ["backendSource", "intermediate"],
            )
            self.assertEqual(summary["status"], "missing-artifact")
            self.assertEqual(
                summary["missingArtifacts"][0]["path"],
                "backend/metal/RuntimeReaderFixture.metal",
            )
            with self.assertRaisesRegex(
                PackageReadError,
                "runtime package is not compatible: required artifact",
            ):
                report.require_compatible()

    def test_compatibility_report_allows_planned_native_file_absence(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory(suffix=".cglb") as temp_dir:
            package_dir = Path(temp_dir)
            self._write_valid_package(package_dir, target="directx")
            (package_dir / "backend" / "directx" / "RuntimeReaderFixture.dxil").unlink()
            (package_dir / "source").mkdir()
            (package_dir / "source" / "invalid.cgl").write_text(
                "planned native classification must not parse source\n",
                encoding="utf-8",
            )

            package = read_package(package_dir)
            report = package.compatibility_report()
            selection = select_runtime_artifact(report, target="directx")
            summary = report.to_summary()
            selection_summary = selection.to_summary()

            self.assertTrue(report.compatible, summary["diagnostics"])
            self.assertEqual(report.status, "source-only")
            self.assertFalse(report.source_parsing_required)
            self.assertTrue(selection.selected, selection_summary["diagnostics"])
            self.assertEqual(selection.require_selected().name, "backendSource")
            self.assertEqual(
                selection_summary["selectedPackageMode"],
                "source-package",
            )
            self.assertEqual(
                selection_summary["admission"]["native"]["category"],
                "native-planned-only",
            )
            self.assertEqual(
                selection_summary["admission"]["sourcePackageFallback"]["reason"],
                "runtime.source_package_fallback.accepted",
            )
            self.assertTrue(
                selection_summary["admission"]["sourcePackageFallback"][
                    "fallbackAccepted"
                ]
            )
            self.assertEqual(report.target_contract.package_mode, "source-package")
            self.assertEqual(report.native_binary_status, "planned")
            self.assertEqual(
                report.required_artifacts, ("backendSource", "nativeBinary")
            )
            self.assertEqual(report.missing_artifacts, ())
            self.assertFalse(report.artifact_availability["native"]["usable"])
            self.assertTrue(report.artifact_availability["source"]["available"])
            self.assertEqual(summary["status"], "source-only")
            self.assertEqual(summary["sourceParsingRequired"], False)
            self.assertEqual(summary["missingArtifacts"], [])
            self.assertEqual(
                summary["artifactAvailability"]["native"]["nativeBinaryStatus"],
                "planned",
            )
            self.assertEqual(
                summary["artifactAvailability"]["native"]["artifact"]["path"],
                "backend/directx/RuntimeReaderFixture.dxil",
            )
            self.assertFalse(summary["artifactAvailability"]["native"]["exists"])
            self.assertFalse(summary["artifactAvailability"]["native"]["usable"])
            self.assertTrue(summary["artifactAvailability"]["source"]["available"])
            self.assertEqual(summary["diagnosticSummary"]["status"], "source-only")
            self.assertEqual(summary["diagnosticSummary"]["rejectCount"], 0)
            artifact_compatibility = summary["artifactCompatibility"]
            self.assertEqual(
                artifact_compatibility["selectedArtifact"], "backendSource"
            )
            self.assertEqual(
                [
                    (
                        artifact["name"],
                        artifact["decision"],
                        artifact["reason"],
                        artifact["selected"],
                    )
                    for artifact in artifact_compatibility["artifacts"]
                ],
                [
                    (
                        "backendSource",
                        "accepted",
                        "package.artifact.selected",
                        True,
                    ),
                    (
                        "nativeBinary",
                        "skipped",
                        "package.artifact.planned_native_binary",
                        False,
                    ),
                ],
            )
            self.assertEqual(
                summary["admission"]["fallbacks"]["sourcePackage"]["reason"],
                "runtime.source_package_fallback.accepted",
            )
            self.assertTrue(
                summary["admission"]["fallbacks"]["sourcePackage"]["fallbackAccepted"]
            )

    def test_compatibility_report_skips_present_planned_native_evidence(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory(suffix=".cglb") as temp_dir:
            package_dir = Path(temp_dir)
            self._write_valid_package(package_dir, target="directx")
            source_path = package_dir / "source" / "invalid.cgl"
            source_path.parent.mkdir()
            source_path.write_text(
                "present planned native evidence must not trigger source parse\n",
                encoding="utf-8",
            )

            with self._guard_crossgl_source_reads():
                package = read_package(package_dir)
                report = package.compatibility_report(loader_target="directx")
                selection = select_runtime_artifact(report, target="directx")
                summary = report.to_summary()

            artifact_compatibility = summary["artifactCompatibility"]
            artifacts_by_name = {
                artifact["name"]: artifact
                for artifact in artifact_compatibility["artifacts"]
            }

            self.assertTrue(report.compatible, summary["diagnostics"])
            self.assertEqual(report.status, "source-only")
            self.assertTrue(selection.selected, selection.to_summary()["diagnostics"])
            self.assertEqual(selection.require_selected().name, "backendSource")
            self.assertEqual(
                summary["artifactAvailability"]["native"]["nativeBinaryStatus"],
                "planned",
            )
            self.assertTrue(summary["artifactAvailability"]["native"]["exists"])
            self.assertFalse(summary["artifactAvailability"]["native"]["usable"])
            self.assertEqual(
                artifacts_by_name["backendSource"]["decision"],
                "accepted",
            )
            self.assertEqual(
                artifacts_by_name["backendSource"]["reason"],
                "package.artifact.selected",
            )
            self.assertEqual(
                artifacts_by_name["nativeBinary"]["decision"],
                "skipped",
            )
            self.assertEqual(
                artifacts_by_name["nativeBinary"]["reason"],
                "package.artifact.planned_native_binary",
            )
            self.assertFalse(artifacts_by_name["nativeBinary"]["selected"])
            self.assertEqual(list(package_dir.rglob("*.cgl")), [source_path])

    def test_compatibility_report_rejects_emitted_native_file_absence(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory(suffix=".cglb") as temp_dir:
            package_dir = Path(temp_dir)
            self._write_valid_package(
                package_dir,
                target="directx",
                native_status="emitted",
            )
            (package_dir / "backend" / "directx" / "RuntimeReaderFixture.dxil").unlink()

            package = read_package(package_dir)
            report = package.compatibility_report()
            summary = report.to_summary()

            self.assertFalse(report.compatible)
            self.assertEqual(
                [diagnostic.to_summary() for diagnostic in report.missing_artifacts],
                [
                    {
                        "severity": "error",
                        "code": "package.artifact.required_file_missing",
                        "message": (
                            "required artifact nativeBinary is declared but "
                            "missing on disk: "
                            "backend/directx/RuntimeReaderFixture.dxil"
                        ),
                        "document": "manifest",
                        "artifact": "nativeBinary",
                        "path": "backend/directx/RuntimeReaderFixture.dxil",
                        "expected": "regular file",
                        "actual": "missing",
                    }
                ],
            )
            artifact_compatibility = summary["artifactCompatibility"]
            self.assertIsNone(artifact_compatibility["selectedArtifact"])
            self.assertEqual(
                [
                    (artifact["name"], artifact["decision"], artifact["reason"])
                    for artifact in artifact_compatibility["accepted"]
                ],
                [("backendSource", "accepted", "package.artifact.accepted")],
            )
            self.assertEqual(
                [
                    (artifact["name"], artifact["decision"], artifact["reason"])
                    for artifact in artifact_compatibility["rejected"]
                ],
                [
                    (
                        "nativeBinary",
                        "rejected",
                        "package.artifact.required_file_missing",
                    )
                ],
            )
            self.assertEqual(artifact_compatibility["skipped"], [])

    def test_compatibility_report_rejects_compiler_metadata_drift(self) -> None:
        with tempfile.TemporaryDirectory(suffix=".cglb") as temp_dir:
            package_dir = Path(temp_dir)
            self._write_valid_package(package_dir)
            manifest_path = package_dir / "manifest.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["compiler"]["name"] = "OtherCompiler"
            manifest["compiler"]["version"] = ""
            self._write_json(manifest_path, manifest)

            report = read_package(package_dir).compatibility_report()

            self.assertFalse(report.compatible)
            self.assertEqual(
                [diagnostic.code for diagnostic in report.diagnostics],
                [
                    "package.compiler.name_incompatible",
                    "package.compiler.version_missing",
                    "package.artifact_requirements.legacy_v0_fallback",
                ],
            )
            self.assertEqual(report.to_summary()["compiler"]["compatible"], False)

    def test_compatibility_report_handles_schema_version_mismatch(self) -> None:
        with tempfile.TemporaryDirectory(suffix=".cglb") as temp_dir:
            package_dir = Path(temp_dir)
            self._write_valid_package(package_dir)
            manifest_path = package_dir / "manifest.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["schemaVersion"] = 2
            self._write_json(manifest_path, manifest)

            with self.assertRaisesRegex(
                PackageReadError,
                "manifest.schemaVersion must be 1",
            ):
                read_package(package_dir)

            report = read_compatibility_report(package_dir)
            summary = report.to_summary()

            self.assertFalse(report.compatible)
            self.assertEqual(report.status, "unsupported-version")
            self.assertEqual(summary["schemas"]["manifest"]["version"], 2)
            self.assertEqual(summary["status"], "unsupported-version")
            self.assertEqual(summary["schemas"]["manifest"]["compatible"], False)
            self.assertEqual(
                [reason["code"] for reason in summary["rejectReasons"]],
                ["package.schema.incompatible"],
            )
            self.assertEqual(summary["rejectReasons"][0]["path"], "schemaVersion")

    def test_compatibility_report_rejects_malformed_root_schema_version_fields_without_source_parse(
        self,
    ) -> None:
        cases = (
            (
                "missing manifest schema",
                "manifest.json",
                lambda document: document.pop("schemaVersion"),
                "manifest",
                "package.schema.version_missing",
                "missing",
            ),
            (
                "string reflection schema",
                "reflection.json",
                lambda document: document.__setitem__("schemaVersion", "1"),
                "reflection",
                "package.schema.version_invalid",
                "1",
            ),
            (
                "boolean diagnostics schema",
                "diagnostics.json",
                lambda document: document.__setitem__("schemaVersion", True),
                "diagnostics",
                "package.schema.version_invalid",
                "boolean",
            ),
        )

        for (
            name,
            metadata_name,
            mutate_document,
            expected_document,
            expected_code,
            expected_actual,
        ) in cases:
            with self.subTest(name=name):
                with tempfile.TemporaryDirectory(suffix=".cglb") as temp_dir:
                    package_dir = Path(temp_dir)
                    self._write_valid_package(package_dir)
                    metadata_path = package_dir / metadata_name
                    document = json.loads(metadata_path.read_text(encoding="utf-8"))
                    mutate_document(document)
                    self._write_json(metadata_path, document)
                    source_path = package_dir / "source" / "invalid.cgl"
                    source_path.parent.mkdir()
                    source_path.write_text(
                        "runtime must not parse source for malformed schemaVersion\n",
                        encoding="utf-8",
                    )

                    with self._guard_crossgl_source_reads():
                        report = read_compatibility_report(
                            package_dir,
                            loader_target="metal",
                        )
                        selection = select_runtime_artifact(
                            report,
                            target="metal",
                        )

                    summary = report.to_summary()
                    diagnostic = next(
                        diagnostic
                        for diagnostic in summary["rejectReasons"]
                        if diagnostic["code"] == expected_code
                    )

                    self.assertFalse(report.compatible)
                    self.assertEqual(report.status, "unsupported-version")
                    self.assertFalse(report.source_parsing_required)
                    self.assertFalse(selection.selected)
                    self.assertFalse(selection.source_parsing_required)
                    self.assertEqual(diagnostic["document"], expected_document)
                    self.assertEqual(diagnostic["path"], "schemaVersion")
                    self.assertEqual(diagnostic["expected"], 1)
                    self.assertEqual(diagnostic.get("actual"), expected_actual)
                    self.assertNotIn(
                        "package.target.unsupported",
                        [reason["code"] for reason in summary["rejectReasons"]],
                    )
                    self.assertEqual(list(package_dir.rglob("*.cgl")), [source_path])

    def test_compatibility_report_marks_loader_target_mismatch_as_skip(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory(suffix=".cglb") as temp_dir:
            package_dir = Path(temp_dir)
            self._write_valid_package(package_dir)

            report = read_compatibility_report(package_dir, loader_target="vulkan")
            selection = select_runtime_artifact(report, target="vulkan")
            summary = report.to_summary()
            selection_summary = selection.to_summary()

            self.assertFalse(report.compatible)
            self.assertFalse(selection.selected)
            self.assertEqual(summary["loaderTarget"], "vulkan")
            self.assertEqual(summary["admission"]["decision"], "skipped")
            self.assertEqual(
                summary["admission"]["target"]["category"],
                "target-mismatch",
            )
            self.assertEqual(
                selection_summary["admission"]["decision"],
                "skipped",
            )
            self.assertEqual(
                selection_summary["admission"]["target"]["category"],
                "target-mismatch",
            )
            self.assertEqual(
                selection_summary["admission"]["native"]["category"],
                "native-unavailable",
            )
            self.assertTrue(summary["admission"]["target"]["available"])
            self.assertTrue(summary["admission"]["target"]["supported"])
            self.assertFalse(summary["admission"]["target"]["matched"])
            self.assertEqual(summary["rejectReasons"], [])
            self.assertEqual(
                summary["skipReasons"],
                [
                    {
                        "severity": "skip",
                        "code": "package.target.loader_mismatch",
                        "message": (
                            "package target metal does not match loader target vulkan"
                        ),
                        "document": "manifest",
                        "expected": "vulkan",
                        "actual": "metal",
                    }
                ],
            )

    def test_compatibility_report_admission_distinguishes_target_unsupported_and_unavailable(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory(suffix=".cglb") as temp_dir:
            package_dir = Path(temp_dir)
            self._write_valid_package(package_dir, target="spirv")

            report = read_compatibility_report(package_dir)
            selection = select_runtime_artifact(report, target="spirv")
            summary = report.to_summary()
            selection_summary = selection.to_summary()

            self.assertFalse(report.compatible)
            self.assertFalse(selection.selected)
            self.assertEqual(report.status, "unsupported-target")
            self.assertEqual(summary["admission"]["decision"], "rejected")
            self.assertEqual(
                summary["admission"]["target"]["category"],
                "target-unsupported",
            )
            self.assertEqual(
                selection_summary["admission"]["target"]["category"],
                "target-unsupported",
            )
            self.assertEqual(
                selection_summary["admission"]["native"]["reason"],
                "package.target.unsupported",
            )
            self.assertTrue(summary["admission"]["target"]["available"])
            self.assertFalse(summary["admission"]["target"]["supported"])
            self.assertIn(
                "package.target.unsupported",
                [
                    diagnostic["code"]
                    for diagnostic in summary["admission"]["target"]["diagnostics"]
                ],
            )

        with tempfile.TemporaryDirectory(suffix=".cglb") as temp_dir:
            package_dir = Path(temp_dir)
            self._write_valid_package(package_dir)
            manifest_path = package_dir / "manifest.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            del manifest["target"]
            self._write_json(manifest_path, manifest)
            source_path = package_dir / "source" / "invalid.cgl"
            source_path.parent.mkdir()
            source_path.write_text(
                "runtime admission must not recover target metadata from source\n",
                encoding="utf-8",
            )

            with self._guard_crossgl_source_reads():
                report = read_compatibility_report(package_dir, loader_target="metal")
                selection = select_runtime_artifact(report, target="metal")
            summary = report.to_summary()
            selection_summary = selection.to_summary()

            self.assertFalse(report.compatible)
            self.assertFalse(selection.selected)
            self.assertEqual(report.status, "incompatible")
            self.assertEqual(summary["admission"]["decision"], "rejected")
            self.assertEqual(
                summary["admission"]["target"]["category"],
                "target-unavailable",
            )
            self.assertEqual(
                selection_summary["admission"]["target"]["decision"],
                "rejected",
            )
            self.assertEqual(
                selection_summary["admission"]["target"]["category"],
                "target-unavailable",
            )
            self.assertEqual(
                [
                    diagnostic["code"]
                    for diagnostic in selection_summary["admission"]["target"][
                        "diagnostics"
                    ]
                ],
                ["package.identity.target_missing"],
            )
            self.assertFalse(summary["admission"]["target"]["available"])
            self.assertFalse(summary["admission"]["target"]["supported"])
            self.assertIn(
                "package.identity.target_missing",
                [
                    diagnostic["code"]
                    for diagnostic in summary["admission"]["target"]["diagnostics"]
                ],
            )
            self.assertEqual(list(package_dir.rglob("*.cgl")), [source_path])

    def test_compatibility_report_rejects_stale_reflection_native_binary(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory(suffix=".cglb") as temp_dir:
            package_dir = Path(temp_dir)
            self._write_valid_package(package_dir)
            (package_dir / "source").mkdir()
            (package_dir / "source" / "invalid.cgl").write_text(
                "runtime compatibility must not parse stale package source\n",
                encoding="utf-8",
            )
            reflection_path = package_dir / "reflection.json"
            reflection = json.loads(reflection_path.read_text(encoding="utf-8"))
            reflection["nativeBinary"] = "backend/metal/StaleFixture.metallib"
            self._write_json(reflection_path, reflection)

            report = read_compatibility_report(package_dir, loader_target="metal")
            selection = select_runtime_artifact(report, target="metal")
            summary = report.to_summary()

            self.assertFalse(report.compatible)
            self.assertEqual(report.status, "incompatible")
            self.assertFalse(report.source_parsing_required)
            self.assertFalse(selection.selected)
            self.assertEqual(selection.artifact, None)
            self.assertEqual(
                [diagnostic.code for diagnostic in report.reject_reasons],
                ["package.reflection.native_binary_mismatch"],
            )
            self.assertEqual(
                summary["rejectReasons"][0],
                {
                    "severity": "error",
                    "code": "package.reflection.native_binary_mismatch",
                    "message": (
                        "reflection.nativeBinary does not match "
                        "manifest.artifacts.nativeBinary"
                    ),
                    "document": "reflection",
                    "artifact": "nativeBinary",
                    "path": "nativeBinary",
                    "expected": "backend/metal/RuntimeReaderFixture.metallib",
                    "actual": "backend/metal/StaleFixture.metallib",
                },
            )
            self.assertEqual(
                list(package_dir.rglob("*.cgl")),
                [package_dir / "source" / "invalid.cgl"],
            )

    def test_compatibility_report_rejects_invalid_reflection_native_binary_path(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory(suffix=".cglb") as temp_dir:
            package_dir = Path(temp_dir)
            self._write_valid_package(package_dir)
            (package_dir / "source").mkdir()
            (package_dir / "source" / "invalid.cgl").write_text(
                "runtime compatibility must not parse invalid source fallback\n",
                encoding="utf-8",
            )
            reflection_path = package_dir / "reflection.json"
            reflection = json.loads(reflection_path.read_text(encoding="utf-8"))
            reflection["nativeBinary"] = "../outside.metallib"
            self._write_json(reflection_path, reflection)

            report = read_compatibility_report(package_dir, loader_target="metal")
            selection = select_runtime_artifact(report, target="metal")
            summary = report.to_summary()

            self.assertFalse(report.compatible)
            self.assertEqual(report.status, "incompatible")
            self.assertFalse(report.source_parsing_required)
            self.assertFalse(selection.selected)
            self.assertEqual(selection.artifact, None)
            self.assertEqual(
                [diagnostic.code for diagnostic in report.reject_reasons],
                ["package.reflection.native_binary_invalid"],
            )
            self.assertEqual(
                summary["rejectReasons"][0],
                {
                    "severity": "error",
                    "code": "package.reflection.native_binary_invalid",
                    "message": "reflection.nativeBinary escapes the package archive",
                    "document": "reflection",
                    "artifact": "nativeBinary",
                    "path": "nativeBinary",
                    "expected": "package-relative path",
                    "actual": "../outside.metallib",
                },
            )
            self.assertEqual(
                list(package_dir.rglob("*.cgl")),
                [package_dir / "source" / "invalid.cgl"],
            )

    def test_reflection_lookup_reports_missing_entry_point_and_resource(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory(suffix=".cglb") as temp_dir:
            package_dir = Path(temp_dir)
            self._write_valid_package(package_dir)
            package = read_package(package_dir)

            self.assertIsNone(package.entry_point("vertex", "main"))
            self.assertIsNone(package.resource_binding("compute", "MissingBuffer"))
            with self.assertRaisesRegex(
                PackageReadError,
                "missing reflection entry point: stage=vertex name=main",
            ):
                package.require_entry_point("vertex", "main")
            with self.assertRaisesRegex(
                PackageReadError,
                "missing reflection resource binding: stage=compute name=MissingBuffer",
            ):
                package.require_resource_binding("compute", "MissingBuffer")

    def test_required_artifacts_load_bytes_and_text(self) -> None:
        with tempfile.TemporaryDirectory(suffix=".cglb") as temp_dir:
            package_dir = Path(temp_dir)
            self._write_valid_package(package_dir)

            package = read_package(package_dir)

            self.assertEqual(
                package.backend_source_artifact(),
                package.require_artifact("backendSource"),
            )
            self.assertEqual(
                package.native_binary_artifact(),
                package.require_existing_artifact("nativeBinary"),
            )
            self.assertEqual(
                package.read_artifact_text("backendSource"),
                "// generated Metal source\n",
            )
            self.assertEqual(package.read_artifact_bytes("nativeBinary"), b"metallib")
            self.assertEqual(
                package.require_existing_artifact("intermediate").read_bytes(),
                b"air",
            )

    def test_required_artifact_reports_missing_manifest_key(self) -> None:
        with tempfile.TemporaryDirectory(suffix=".cglb") as temp_dir:
            package_dir = Path(temp_dir)
            self._write_valid_package(package_dir)
            package = read_package(package_dir)

            self.assertIsNone(package.artifact("backendAssembly"))
            with self.assertRaisesRegex(
                PackageReadError,
                "missing manifest artifact: backendAssembly",
            ):
                package.require_artifact("backendAssembly")

            with self.assertRaisesRegex(
                PackageReadError,
                "missing manifest artifact: backendAssembly",
            ):
                package.read_artifact_bytes("backendAssembly")

    def test_required_existing_artifact_reports_declared_file_missing_on_disk(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory(suffix=".cglb") as temp_dir:
            package_dir = Path(temp_dir)
            self._write_valid_package(package_dir)
            native_binary_path = (
                package_dir / "backend" / "metal" / "RuntimeReaderFixture.metallib"
            )
            native_binary_path.unlink()

            package = read_package(package_dir)
            native_binary = package.require_artifact("nativeBinary")

            self.assertFalse(native_binary.exists)
            self.assertEqual(
                native_binary.package_path,
                "backend/metal/RuntimeReaderFixture.metallib",
            )
            self.assertIsNone(
                next(
                    artifact
                    for artifact in package.to_summary()["artifacts"]
                    if artifact["name"] == "nativeBinary"
                )["size"]
            )
            with self.assertRaisesRegex(
                PackageReadError,
                "manifest artifact is missing on disk: nativeBinary "
                r"\(backend/metal/RuntimeReaderFixture\.metallib\)",
            ):
                package.require_existing_artifact("nativeBinary")

            with self.assertRaisesRegex(
                PackageReadError,
                "manifest artifact is missing on disk: nativeBinary",
            ):
                native_binary.read_bytes()

    def test_reads_optional_debug_metadata_as_raw_json_and_record(self) -> None:
        with tempfile.TemporaryDirectory(suffix=".cglb") as temp_dir:
            package_dir = Path(temp_dir)
            self._write_valid_package(package_dir, emit_debug_metadata=True)

            package = read_package(package_dir)
            debug_artifact = package.debug_metadata_artifact()
            debug_record = package.debug_metadata_record()
            summary = package.to_summary()["debugMetadata"]

            self.assertIsNotNone(debug_artifact)
            self.assertTrue(debug_artifact.exists)
            self.assertEqual(
                package.require_debug_metadata()["schemaVersion"],
                11,
            )
            self.assertIsNotNone(debug_record)
            self.assertTrue(debug_record.compatible)
            self.assertEqual(debug_record.selected_target, "metal")
            self.assertEqual(debug_record.selected_package_mode, "native")
            self.assertEqual(debug_record.expression_source_location_count, 1)
            self.assertEqual(debug_record.type_source_location_count, 2)
            self.assertEqual(debug_record.statement_source_location_count, 3)
            self.assertEqual(debug_record.manual_texture_compare_kernel_count, 0)
            self.assertEqual(
                summary,
                {
                    "declared": True,
                    "exists": True,
                    "path": "ir/debug-metadata.json",
                    "compatible": True,
                    "record": debug_record.to_summary(),
                },
            )

    def test_reports_declared_missing_debug_metadata_without_source_parse(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory(suffix=".cglb") as temp_dir:
            package_dir = Path(temp_dir)
            self._write_valid_package(package_dir, emit_debug_metadata=True)
            (package_dir / "ir" / "debug-metadata.json").unlink()
            (package_dir / "source").mkdir()
            (package_dir / "source" / "invalid.cgl").write_text(
                "runtime reader still must not parse source\n",
                encoding="utf-8",
            )

            package = read_package(package_dir)
            summary = package.to_summary()["debugMetadata"]

            self.assertIsNone(package.debug_metadata)
            self.assertIsNone(package.debug_metadata_record())
            self.assertEqual(
                summary,
                {
                    "declared": True,
                    "exists": False,
                    "path": "ir/debug-metadata.json",
                    "compatible": None,
                    "record": None,
                },
            )
            with self.assertRaisesRegex(
                PackageReadError,
                "debug metadata artifact is not available",
            ):
                package.require_debug_metadata()

    def test_reads_zip_package_compatibility_without_source_parse(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir)
            package_dir = temp_root / "package-dir"
            package_dir.mkdir()
            self._write_valid_package(package_dir, emit_debug_metadata=True)
            (package_dir / "source").mkdir()
            (package_dir / "source" / "invalid.cgl").write_text(
                "zip compatibility must not parse this source\n",
                encoding="utf-8",
            )
            zip_path = temp_root / "RuntimeReaderFixture.cglb"
            self._write_zip_package(
                package_dir, zip_path, prefix="RuntimeReaderFixture.cglb"
            )

            report = read_compatibility_report(zip_path, loader_target="metal")
            package = read_package(zip_path)
            summary = report.to_summary()

            self.assertTrue(report.compatible, summary["diagnostics"])
            self.assertEqual(report.status, "compatible")
            self.assertEqual(summary["packageFormat"], "zip")
            self.assertEqual(summary["packageVersion"], 1)
            self.assertEqual(summary["status"], "compatible")
            self.assertTrue(
                summary["availableArtifacts"][0]["absolutePath"].startswith(
                    f"{zip_path}!/"
                )
            )
            self.assertEqual(package.package_format, "zip")
            self.assertEqual(
                package.read_artifact_text("backendSource"),
                "// generated Metal source\n",
            )
            self.assertEqual(package.read_artifact_bytes("nativeBinary"), b"metallib")
            self.assertEqual(package.require_debug_metadata()["schemaVersion"], 11)

    def test_rejects_zip_package_duplicate_members(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir)
            package_dir = temp_root / "package-dir"
            package_dir.mkdir()
            self._write_valid_package(package_dir)
            zip_path = temp_root / "RuntimeReaderFixture.cglb"
            self._write_zip_package(
                package_dir, zip_path, prefix="RuntimeReaderFixture.cglb"
            )

            with warnings.catch_warnings():
                warnings.simplefilter("ignore", UserWarning)
                with zipfile.ZipFile(zip_path, "a") as archive:
                    archive.writestr(
                        "RuntimeReaderFixture.cglb/manifest.json",
                        "{}\n",
                    )

            with self.assertRaisesRegex(
                PackageReadError,
                "ambiguous duplicate package archive member: manifest\\.json",
            ):
                read_package(zip_path)
            with self.assertRaisesRegex(
                PackageReadError,
                "ambiguous duplicate package archive member: manifest\\.json",
            ):
                read_compatibility_report(zip_path, loader_target="metal")

    def test_rejects_zip_package_duplicate_normalized_members(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir)
            package_dir = temp_root / "package-dir"
            package_dir.mkdir()
            self._write_valid_package(package_dir)
            zip_path = temp_root / "RuntimeReaderFixture.cglb"
            prefix = "RuntimeReaderFixture.cglb"
            self._write_zip_package(package_dir, zip_path, prefix=prefix)

            alias_member = f"{prefix}/backend/metal/./RuntimeReaderFixture.metallib"
            with zipfile.ZipFile(zip_path, "a") as archive:
                archive.writestr(alias_member, b"ambiguous metallib alias")

            expected_message = (
                "ambiguous duplicate package archive member: "
                "backend/metal/RuntimeReaderFixture\\.metallib.*"
                "backend/metal/\\./RuntimeReaderFixture\\.metallib"
            )
            with self.assertRaisesRegex(PackageReadError, expected_message):
                read_package(zip_path)
            with self.assertRaisesRegex(PackageReadError, expected_message):
                read_compatibility_report(zip_path, loader_target="metal")

    def test_rejects_zip_package_multiple_metadata_roots(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir)
            package_dir = temp_root / "package-dir"
            package_dir.mkdir()
            self._write_valid_package(package_dir)
            zip_path = temp_root / "RuntimeReaderFixture.cglb"
            with zipfile.ZipFile(zip_path, "w") as archive:
                for path in sorted(package_dir.rglob("*")):
                    if not path.is_file():
                        continue
                    relative_path = path.relative_to(package_dir).as_posix()
                    archive.write(path, f"PackageA/{relative_path}")
                    archive.write(path, f"PackageB/{relative_path}")

            with self.assertRaisesRegex(
                PackageReadError,
                "ambiguous package root metadata in archive: PackageA, PackageB",
            ):
                read_package(zip_path)
            with self.assertRaisesRegex(
                PackageReadError,
                "ambiguous package root metadata in archive: PackageA, PackageB",
            ):
                read_compatibility_report(zip_path, loader_target="metal")

    def test_rejects_zip_package_mixed_root_and_prefixed_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir)
            package_dir = temp_root / "package-dir"
            package_dir.mkdir()
            self._write_valid_package(package_dir)
            zip_path = temp_root / "RuntimeReaderFixture.cglb"
            self._write_zip_package(
                package_dir, zip_path, prefix="RuntimeReaderFixture.cglb"
            )

            with zipfile.ZipFile(zip_path, "a") as archive:
                archive.writestr("manifest.json", "{}\n")

            with self.assertRaisesRegex(
                PackageReadError,
                (
                    "ambiguous package root metadata in archive: archive root, "
                    "RuntimeReaderFixture\\.cglb"
                ),
            ):
                read_package(zip_path)
            with self.assertRaisesRegex(
                PackageReadError,
                (
                    "ambiguous package root metadata in archive: archive root, "
                    "RuntimeReaderFixture\\.cglb"
                ),
            ):
                read_compatibility_report(zip_path, loader_target="metal")

    def test_compatibility_report_rejects_oversized_zip_root_metadata(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir)
            package_dir = temp_root / "package-dir"
            package_dir.mkdir()
            self._write_valid_package(package_dir)
            (package_dir / "source").mkdir()
            (package_dir / "source" / "invalid.cgl").write_text(
                "oversized zip metadata must not trigger source parsing\n",
                encoding="utf-8",
            )
            with _runtime_metadata_byte_limit(2048):
                oversized_size = self._write_oversized_json_object(
                    package_dir / "manifest.json"
                )
                zip_path = temp_root / "RuntimeReaderFixture.cglb"
                self._write_zip_package(
                    package_dir,
                    zip_path,
                    prefix="RuntimeReaderFixture.cglb",
                )

                report = read_compatibility_report(zip_path, loader_target="metal")
                summary = report.to_summary()

                self.assertFalse(report.compatible)
                self.assertEqual(summary["packageFormat"], "zip")
                self.assertEqual(summary["runtime"]["metadataJsonByteLimit"], 2048)
                self.assertFalse(summary["sourceParsingRequired"])
                self.assertEqual(
                    [diagnostic.code for diagnostic in report.reject_reasons],
                    ["package.metadata.too_large"],
                )
                self.assertEqual(
                    summary["rejectReasons"][0],
                    {
                        "severity": "error",
                        "code": "package.metadata.too_large",
                        "message": (
                            "package metadata exceeds runtime byte limit: "
                            f"manifest.json is {oversized_size} bytes; "
                            "limit is 2048 bytes"
                        ),
                        "document": "manifest",
                        "expected": "<= 2048 bytes",
                        "actual": oversized_size,
                    },
                )
                with self.assertRaisesRegex(
                    PackageReadError,
                    "package metadata exceeds runtime byte limit: manifest\\.json is ",
                ):
                    read_package(zip_path)

    def test_reports_missing_required_metadata(self) -> None:
        with tempfile.TemporaryDirectory(suffix=".cglb") as temp_dir:
            package_dir = Path(temp_dir)
            self._write_valid_package(package_dir)
            (package_dir / "reflection.json").unlink()

            with self.assertRaisesRegex(
                PackageReadError,
                "missing package metadata: reflection.json",
            ):
                read_package(package_dir)

    def test_compatibility_report_structures_missing_root_metadata(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory(suffix=".cglb") as temp_dir:
            package_dir = Path(temp_dir)
            self._write_valid_package(package_dir)
            (package_dir / "diagnostics.json").unlink()
            (package_dir / "source").mkdir()
            (package_dir / "source" / "invalid.cgl").write_text(
                "runtime compatibility must not parse package source\n",
                encoding="utf-8",
            )

            report = read_compatibility_report(package_dir, loader_target="metal")
            summary = report.to_summary()

            self.assertFalse(report.compatible)
            self.assertFalse(report.source_parsing_required)
            self.assertEqual(report.status, "incompatible")
            self.assertEqual(summary["availableTargets"], ["metal"])
            self.assertIn(
                "package.metadata.missing",
                [diagnostic.code for diagnostic in report.reject_reasons],
            )
            self.assertNotIn(
                "package.schema.incompatible",
                [diagnostic.code for diagnostic in report.reject_reasons],
            )
            self.assertEqual(
                summary["rejectReasons"][0],
                {
                    "severity": "error",
                    "code": "package.metadata.missing",
                    "message": "missing package metadata: diagnostics.json",
                    "document": "diagnostics",
                    "expected": "JSON object metadata file",
                    "actual": "missing",
                },
            )
            with self.assertRaisesRegex(
                PackageReadError,
                "missing package metadata: diagnostics.json",
            ):
                read_package(package_dir)

    def test_compatibility_report_structures_malformed_root_metadata(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory(suffix=".cglb") as temp_dir:
            package_dir = Path(temp_dir)
            self._write_valid_package(package_dir)
            (package_dir / "reflection.json").write_text(
                "[]\n",
                encoding="utf-8",
            )

            report = read_compatibility_report(package_dir, loader_target="metal")
            summary = report.to_summary()

            self.assertFalse(report.compatible)
            self.assertFalse(summary["sourceParsingRequired"])
            self.assertEqual(summary["targetAvailability"]["manifestTarget"], "metal")
            reject_codes = [diagnostic.code for diagnostic in report.reject_reasons]
            self.assertIn(
                "package.metadata.invalid",
                reject_codes,
            )
            self.assertNotIn("package.schema.incompatible", reject_codes)
            self.assertNotIn(
                "package.identity.reflection_module_mismatch",
                reject_codes,
            )
            self.assertNotIn(
                "package.identity.reflection_target_mismatch",
                reject_codes,
            )
            self.assertEqual(
                summary["rejectReasons"][0],
                {
                    "severity": "error",
                    "code": "package.metadata.invalid",
                    "message": "reflection.json must contain a JSON object",
                    "document": "reflection",
                    "expected": "JSON object metadata file",
                    "actual": "invalid",
                },
            )
            with self.assertRaisesRegex(
                PackageReadError,
                "reflection.json must contain a JSON object",
            ):
                read_package(package_dir)

    def test_compatibility_report_rejects_malformed_diagnostics_records_without_source_parse(
        self,
    ) -> None:
        cases: tuple[tuple[str, object, str, str, object], ...] = (
            (
                "records not array",
                {"severity": "error"},
                "package.diagnostics.records_invalid",
                "diagnostics",
                "object",
            ),
            (
                "record not object",
                ["not-object"],
                "package.diagnostics.record_invalid",
                "diagnostics[0]",
                "string",
            ),
            (
                "severity not string",
                [{"severity": []}],
                "package.diagnostics.severity_invalid",
                "diagnostics[0].severity",
                "array",
            ),
        )
        for name, records, expected_code, expected_path, expected_actual in cases:
            with self.subTest(name=name):
                with tempfile.TemporaryDirectory(suffix=".cglb") as temp_dir:
                    package_dir = Path(temp_dir)
                    self._write_valid_package(package_dir)
                    diagnostics_path = package_dir / "diagnostics.json"
                    diagnostics = json.loads(
                        diagnostics_path.read_text(encoding="utf-8")
                    )
                    diagnostics["diagnostics"] = records
                    self._write_json(diagnostics_path, diagnostics)
                    source_path = package_dir / "source" / "invalid.cgl"
                    source_path.parent.mkdir()
                    source_path.write_text(
                        "runtime compatibility must not infer diagnostics "
                        "metadata from source\n",
                        encoding="utf-8",
                    )

                    with self._guard_crossgl_source_reads():
                        report = read_compatibility_report(
                            package_dir,
                            loader_target="metal",
                        )
                        selection = select_runtime_artifact(report, target="metal")

                    summary = report.to_summary()
                    diagnostic = next(
                        diagnostic
                        for diagnostic in summary["rejectReasons"]
                        if diagnostic["code"] == expected_code
                    )

                    self.assertFalse(report.compatible)
                    self.assertEqual(report.status, "incompatible")
                    self.assertFalse(selection.selected)
                    self.assertFalse(report.source_parsing_required)
                    self.assertEqual(diagnostic["document"], "diagnostics")
                    self.assertEqual(diagnostic["path"], expected_path)
                    self.assertEqual(diagnostic["actual"], expected_actual)
                    self.assertFalse(summary["diagnosticsMetadata"]["valid"])
                    self.assertFalse(summary["diagnosticsMetadata"]["recordShapeValid"])
                    self.assertFalse(summary["admission"]["compilerInvocationRequired"])
                    self.assertFalse(summary["admission"]["deviceExecutionRequired"])
                    self.assertEqual(list(package_dir.rglob("*.cgl")), [source_path])

    def test_compatibility_report_rejects_oversized_root_metadata_without_source_parse(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory(suffix=".cglb") as temp_dir:
            package_dir = Path(temp_dir)
            self._write_valid_package(package_dir)
            (package_dir / "source").mkdir()
            (package_dir / "source" / "invalid.cgl").write_text(
                "oversized metadata must not trigger source parsing\n",
                encoding="utf-8",
            )

            with _runtime_metadata_byte_limit(2048):
                oversized_size = self._write_oversized_json_object(
                    package_dir / "manifest.json"
                )

                report = read_compatibility_report(
                    package_dir,
                    loader_target="metal",
                )
                summary = report.to_summary()

                self.assertFalse(report.compatible)
                self.assertEqual(report.status, "incompatible")
                self.assertFalse(summary["sourceParsingRequired"])
                self.assertEqual(summary["availableTargets"], [])
                self.assertEqual(summary["runtime"]["metadataJsonByteLimit"], 2048)
                self.assertEqual(
                    [diagnostic.code for diagnostic in report.reject_reasons],
                    ["package.metadata.too_large"],
                )
                self.assertNotIn(
                    "package.schema.incompatible",
                    [diagnostic.code for diagnostic in report.reject_reasons],
                )
                self.assertEqual(
                    summary["rejectReasons"][0],
                    {
                        "severity": "error",
                        "code": "package.metadata.too_large",
                        "message": (
                            "package metadata exceeds runtime byte limit: "
                            f"manifest.json is {oversized_size} bytes; "
                            "limit is 2048 bytes"
                        ),
                        "document": "manifest",
                        "expected": "<= 2048 bytes",
                        "actual": oversized_size,
                    },
                )
                self.assertEqual(
                    list(package_dir.rglob("*.cgl")),
                    [package_dir / "source" / "invalid.cgl"],
                )
                with self.assertRaisesRegex(
                    PackageReadError,
                    "package metadata exceeds runtime byte limit: manifest\\.json is ",
                ):
                    read_package(package_dir)

    def test_compatibility_report_rejects_missing_manifest_target_before_loader_mismatch(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory(suffix=".cglb") as temp_dir:
            package_dir = Path(temp_dir)
            self._write_valid_package(package_dir)
            manifest_path = package_dir / "manifest.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            del manifest["target"]
            self._write_json(manifest_path, manifest)

            report = read_compatibility_report(package_dir, loader_target="metal")
            reject_codes = [diagnostic.code for diagnostic in report.reject_reasons]
            skip_codes = [diagnostic.code for diagnostic in report.skip_reasons]

            self.assertFalse(report.compatible)
            self.assertEqual(report.status, "incompatible")
            self.assertIn("package.identity.target_missing", reject_codes)
            self.assertNotIn("package.target.unsupported", reject_codes)
            self.assertNotIn("package.target.loader_mismatch", skip_codes)
            with self.assertRaisesRegex(
                PackageReadError,
                "manifest.target must be a non-empty string",
            ):
                read_package(package_dir)

    def test_compatibility_report_rejects_empty_manifest_module(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory(suffix=".cglb") as temp_dir:
            package_dir = Path(temp_dir)
            self._write_valid_package(package_dir)
            manifest_path = package_dir / "manifest.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["module"] = ""
            self._write_json(manifest_path, manifest)

            report = read_compatibility_report(package_dir, loader_target="metal")
            summary = report.to_summary()

            self.assertFalse(report.compatible)
            self.assertEqual(report.status, "incompatible")
            self.assertIn(
                "package.identity.module_missing",
                [diagnostic.code for diagnostic in report.reject_reasons],
            )
            self.assertEqual(
                next(
                    diagnostic
                    for diagnostic in summary["rejectReasons"]
                    if diagnostic["code"] == "package.identity.module_missing"
                ),
                {
                    "severity": "error",
                    "code": "package.identity.module_missing",
                    "message": "manifest.module must be a non-empty string",
                    "document": "manifest",
                    "expected": "non-empty string",
                    "actual": "",
                },
            )
            with self.assertRaisesRegex(
                PackageReadError,
                "manifest.module must be a non-empty string",
            ):
                read_package(package_dir)

    def test_compatibility_report_rejects_invalid_manifest_target_before_loader_mismatch(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory(suffix=".cglb") as temp_dir:
            package_dir = Path(temp_dir)
            self._write_valid_package(package_dir)
            manifest_path = package_dir / "manifest.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["target"] = []
            self._write_json(manifest_path, manifest)

            report = read_compatibility_report(package_dir, loader_target="metal")
            reject_codes = [diagnostic.code for diagnostic in report.reject_reasons]
            skip_codes = [diagnostic.code for diagnostic in report.skip_reasons]

            self.assertFalse(report.compatible)
            self.assertEqual(report.status, "incompatible")
            self.assertIn("package.identity.target_missing", reject_codes)
            self.assertNotIn("package.target.unsupported", reject_codes)
            self.assertNotIn("package.target.loader_mismatch", skip_codes)
            with self.assertRaisesRegex(
                PackageReadError,
                "manifest.target must be a non-empty string",
            ):
                read_package(package_dir)

    def test_compatibility_report_structures_malformed_debug_metadata(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory(suffix=".cglb") as temp_dir:
            package_dir = Path(temp_dir)
            self._write_valid_package(package_dir, emit_debug_metadata=True)
            (package_dir / "ir" / "debug-metadata.json").write_text(
                "{not-json}\n",
                encoding="utf-8",
            )
            (package_dir / "source").mkdir()
            (package_dir / "source" / "invalid.cgl").write_text(
                "runtime compatibility must not parse this source\n",
                encoding="utf-8",
            )

            report = read_compatibility_report(package_dir, loader_target="metal")
            summary = report.to_summary()

            self.assertFalse(report.compatible)
            self.assertFalse(report.source_parsing_required)
            self.assertEqual(summary["status"], "incompatible")
            self.assertIn(
                "package.debug_metadata.invalid",
                [diagnostic.code for diagnostic in report.reject_reasons],
            )
            self.assertEqual(
                summary["debugMetadata"],
                {
                    "declared": True,
                    "exists": True,
                    "path": "ir/debug-metadata.json",
                    "compatible": None,
                    "record": None,
                },
            )
            self.assertEqual(
                summary["rejectReasons"][0]["path"],
                "ir/debug-metadata.json",
            )
            with self.assertRaisesRegex(
                PackageReadError,
                "invalid JSON in debug metadata",
            ):
                read_package(package_dir)

    def test_compatibility_report_rejects_oversized_debug_metadata(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory(suffix=".cglb") as temp_dir:
            package_dir = Path(temp_dir)
            self._write_valid_package(package_dir, emit_debug_metadata=True)
            (package_dir / "source").mkdir()
            (package_dir / "source" / "invalid.cgl").write_text(
                "oversized debug metadata must not trigger source parsing\n",
                encoding="utf-8",
            )

            with _runtime_metadata_byte_limit(2048):
                oversized_size = self._write_oversized_json_object(
                    package_dir / "ir" / "debug-metadata.json"
                )

                report = read_compatibility_report(
                    package_dir,
                    loader_target="metal",
                )
                summary = report.to_summary()

                self.assertFalse(report.compatible)
                self.assertEqual(report.status, "incompatible")
                self.assertFalse(summary["sourceParsingRequired"])
                self.assertEqual(
                    [diagnostic.code for diagnostic in report.reject_reasons],
                    ["package.debug_metadata.too_large"],
                )
                self.assertEqual(
                    summary["debugMetadata"],
                    {
                        "declared": True,
                        "exists": True,
                        "path": "ir/debug-metadata.json",
                        "compatible": None,
                        "record": None,
                    },
                )
                self.assertEqual(
                    summary["rejectReasons"][0],
                    {
                        "severity": "error",
                        "code": "package.debug_metadata.too_large",
                        "message": (
                            "package metadata exceeds runtime byte limit: "
                            f"debug metadata is {oversized_size} bytes; "
                            "limit is 2048 bytes"
                        ),
                        "document": "debugMetadata",
                        "artifact": "debugMetadata",
                        "path": "ir/debug-metadata.json",
                        "expected": "<= 2048 bytes",
                        "actual": oversized_size,
                    },
                )
                self.assertEqual(
                    list(package_dir.rglob("*.cgl")),
                    [package_dir / "source" / "invalid.cgl"],
                )
                with self.assertRaisesRegex(
                    PackageReadError,
                    "package metadata exceeds runtime byte limit: debug metadata is ",
                ):
                    read_package(package_dir)

    def test_compatibility_report_rejects_future_debug_metadata_schema(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory(suffix=".cglb") as temp_dir:
            package_dir = Path(temp_dir)
            self._write_valid_package(package_dir, emit_debug_metadata=True)
            debug_path = package_dir / "ir" / "debug-metadata.json"
            debug_metadata = json.loads(debug_path.read_text(encoding="utf-8"))
            debug_metadata["schemaVersion"] = 12
            self._write_json(debug_path, debug_metadata)
            (package_dir / "source").mkdir()
            (package_dir / "source" / "invalid.cgl").write_text(
                "runtime compatibility must not parse source for debug metadata\n",
                encoding="utf-8",
            )

            report = read_compatibility_report(package_dir, loader_target="metal")
            summary = report.to_summary()

            self.assertFalse(report.compatible)
            self.assertEqual(report.status, "unsupported-version")
            self.assertFalse(report.source_parsing_required)
            self.assertEqual(summary["debugMetadata"]["record"]["schemaVersion"], 12)
            self.assertFalse(summary["debugMetadata"]["compatible"])
            self.assertEqual(
                [diagnostic.code for diagnostic in report.reject_reasons],
                ["package.debug_metadata.schema_incompatible"],
            )
            self.assertEqual(
                summary["rejectReasons"][0],
                {
                    "severity": "error",
                    "code": "package.debug_metadata.schema_incompatible",
                    "message": (
                        "debug metadata schemaVersion is not supported by this runtime"
                    ),
                    "document": "debugMetadata",
                    "artifact": "debugMetadata",
                    "path": "ir/debug-metadata.json",
                    "expected": 11,
                    "actual": 12,
                },
            )
            self.assertEqual(
                list(package_dir.rglob("*.cgl")),
                [package_dir / "source" / "invalid.cgl"],
            )

    def test_compatibility_report_rejects_malformed_reflection_target_records(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory(suffix=".cglb") as temp_dir:
            package_dir = Path(temp_dir)
            self._write_valid_package(package_dir)
            (package_dir / "source").mkdir()
            (package_dir / "source" / "invalid.cgl").write_text(
                "runtime compatibility must not infer target records from source\n",
                encoding="utf-8",
            )
            reflection_path = package_dir / "reflection.json"
            reflection = json.loads(reflection_path.read_text(encoding="utf-8"))
            reflection["targetResourceBindings"][0]["target"] = []
            del reflection["targetFeatures"][0]["target"]
            self._write_json(reflection_path, reflection)

            report = read_compatibility_report(package_dir, loader_target="metal")
            summary = report.to_summary()

            self.assertFalse(report.compatible)
            self.assertFalse(report.source_parsing_required)
            self.assertEqual(report.status, "incompatible")
            self.assertEqual(summary["availableTargets"], ["metal"])
            self.assertEqual(
                summary["targetAvailability"]["targetResourceBindingTargets"],
                [],
            )
            self.assertEqual(
                summary["targetAvailability"]["targetFeatureTargets"],
                [],
            )
            self.assertEqual(
                summary["admission"]["target"]["category"],
                "target-unavailable",
            )
            self.assertFalse(summary["admission"]["compilerInvocationRequired"])
            self.assertFalse(summary["admission"]["deviceExecutionRequired"])
            self.assertEqual(
                [diagnostic.code for diagnostic in report.reject_reasons],
                [
                    "package.reflection.target_resource_binding_target_invalid",
                    "package.reflection.target_feature_target_invalid",
                ],
            )
            self.assertEqual(
                summary["rejectReasons"][0],
                {
                    "severity": "error",
                    "code": (
                        "package.reflection.target_resource_binding_target_invalid"
                    ),
                    "message": (
                        "reflection.targetResourceBindings target must match "
                        "manifest.target"
                    ),
                    "document": "reflection",
                    "path": "targetResourceBindings[0].target",
                    "expected": "metal",
                    "actual": "array",
                },
            )
            self.assertEqual(
                summary["rejectReasons"][1],
                {
                    "severity": "error",
                    "code": "package.reflection.target_feature_target_invalid",
                    "message": (
                        "reflection.targetFeatures target must match manifest.target"
                    ),
                    "document": "reflection",
                    "path": "targetFeatures[0].target",
                    "expected": "metal",
                    "actual": "missing",
                },
            )
            self.assertEqual(
                list(package_dir.rglob("*.cgl")),
                [package_dir / "source" / "invalid.cgl"],
            )

    def test_compatibility_report_does_not_advertise_target_incompatible_reflection_sidecars(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory(suffix=".cglb") as temp_dir:
            package_dir = Path(temp_dir)
            self._write_valid_package(package_dir, target="directx")
            source_path = package_dir / "source" / "invalid.cgl"
            source_path.parent.mkdir()
            source_path.write_text(
                "runtime compatibility must not infer target support from source\n",
                encoding="utf-8",
            )
            reflection_path = package_dir / "reflection.json"
            reflection = json.loads(reflection_path.read_text(encoding="utf-8"))
            reflection["targetResourceBindings"][0]["target"] = "metal"
            reflection["targetFeatures"][0]["target"] = "metal"
            self._write_json(reflection_path, reflection)

            with self._guard_crossgl_source_reads():
                report = read_compatibility_report(
                    package_dir,
                    loader_target="directx",
                )
                selection = select_runtime_artifact(report, target="directx")

            summary = report.to_summary()
            selection_summary = selection.to_summary()

            self.assertFalse(report.compatible)
            self.assertEqual(report.status, "incompatible")
            self.assertFalse(report.source_parsing_required)
            self.assertFalse(selection.selected)
            self.assertEqual(summary["availableTargets"], ["directx"])
            self.assertEqual(
                summary["targetAvailability"],
                {
                    "manifestTarget": "directx",
                    "reflectionTarget": "directx",
                    "targetResourceBindingTargets": [],
                    "targetFeatureTargets": [],
                    "availableTargets": ["directx"],
                },
            )
            self.assertEqual(
                summary["admission"]["target"]["category"],
                "target-unavailable",
            )
            self.assertEqual(
                selection_summary["admission"]["target"]["category"],
                "target-unavailable",
            )
            self.assertFalse(summary["admission"]["compilerInvocationRequired"])
            self.assertFalse(summary["admission"]["deviceExecutionRequired"])
            self.assertEqual(
                [diagnostic.code for diagnostic in report.reject_reasons],
                [
                    "package.reflection.target_resource_binding_target_mismatch",
                    "package.reflection.target_feature_target_mismatch",
                ],
            )
            self.assertEqual(list(package_dir.rglob("*.cgl")), [source_path])

    def test_compatibility_report_rejects_duplicate_target_resource_bindings(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory(suffix=".cglb") as temp_dir:
            package_dir = Path(temp_dir)
            self._write_valid_package(package_dir, target="directx")
            source_path = package_dir / "source" / "invalid.cgl"
            source_path.parent.mkdir()
            source_path.write_text(
                "runtime compatibility must not disambiguate duplicates from source\n",
                encoding="utf-8",
            )
            reflection_path = package_dir / "reflection.json"
            reflection = json.loads(reflection_path.read_text(encoding="utf-8"))
            duplicate = dict(reflection["targetResourceBindings"][0])
            duplicate["abi"] = {"space": 1, "register": "u1"}
            reflection["targetResourceBindings"].append(duplicate)
            self._write_json(reflection_path, reflection)

            with self._guard_crossgl_source_reads():
                report = read_compatibility_report(
                    package_dir,
                    loader_target="directx",
                )
                selection = select_runtime_artifact(report, target="directx")

            summary = report.to_summary()

            self.assertFalse(report.compatible)
            self.assertEqual(report.status, "incompatible")
            self.assertFalse(selection.selected)
            self.assertIn(
                "package.reflection.target_resource_binding_duplicate",
                [diagnostic.code for diagnostic in report.reject_reasons],
            )
            diagnostic = next(
                diagnostic
                for diagnostic in summary["rejectReasons"]
                if diagnostic["code"]
                == "package.reflection.target_resource_binding_duplicate"
            )
            self.assertEqual(diagnostic["document"], "reflection")
            self.assertEqual(diagnostic["path"], "targetResourceBindings[1]")
            self.assertEqual(
                diagnostic["expected"],
                {
                    "uniqueTargetResourceBinding": {
                        "target": "directx",
                        "stage": "compute",
                        "entryPoint": "runtime_reader_main",
                        "name": "OutputBuffer",
                        "kind": "storageBuffer",
                    }
                },
            )
            self.assertEqual(
                diagnostic["actual"],
                {
                    "duplicateOf": "targetResourceBindings[0]",
                    "target": "directx",
                    "stage": "compute",
                    "entryPoint": "runtime_reader_main",
                    "name": "OutputBuffer",
                    "kind": "storageBuffer",
                },
            )
            with self.assertRaisesRegex(PackageReadError, "unique"):
                read_package(package_dir)
            self.assertEqual(list(package_dir.rglob("*.cgl")), [source_path])

    def test_compatibility_report_rejects_malformed_reflection_handoff_records(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory(suffix=".cglb") as temp_dir:
            package_dir = Path(temp_dir)
            self._write_valid_package(package_dir)
            (package_dir / "source").mkdir()
            (package_dir / "source" / "invalid.cgl").write_text(
                "runtime compatibility must not infer reflection fields from source\n",
                encoding="utf-8",
            )
            reflection_path = package_dir / "reflection.json"
            reflection = json.loads(reflection_path.read_text(encoding="utf-8"))
            del reflection["entryPoints"][0]["backendName"]
            reflection["resources"][0]["stage"] = []
            reflection["targetResourceBindings"][0]["entryPoint"] = ""
            del reflection["targetFeatures"][0]["name"]
            self._write_json(reflection_path, reflection)

            report = read_compatibility_report(package_dir, loader_target="metal")
            selection = select_runtime_artifact(report, target="metal")
            summary = report.to_summary()

            self.assertFalse(report.compatible)
            self.assertEqual(report.status, "incompatible")
            self.assertFalse(report.source_parsing_required)
            self.assertFalse(selection.selected)
            self.assertEqual(
                [diagnostic.code for diagnostic in report.reject_reasons],
                [
                    "package.reflection.entry_points_backend_name_invalid",
                    "package.reflection.resources_stage_invalid",
                    ("package.reflection.target_resource_bindings_entry_point_invalid"),
                    "package.reflection.target_features_name_invalid",
                ],
            )
            self.assertEqual(
                summary["rejectReasons"][0],
                {
                    "severity": "error",
                    "code": "package.reflection.entry_points_backend_name_invalid",
                    "message": (
                        "reflection.entryPoints.backendName must be a non-empty string"
                    ),
                    "document": "reflection",
                    "path": "entryPoints[0].backendName",
                    "expected": "non-empty string",
                    "actual": "missing",
                },
            )
            self.assertEqual(
                summary["rejectReasons"][2],
                {
                    "severity": "error",
                    "code": (
                        "package.reflection."
                        "target_resource_bindings_entry_point_invalid"
                    ),
                    "message": (
                        "reflection.targetResourceBindings.entryPoint must be "
                        "a non-empty string"
                    ),
                    "document": "reflection",
                    "path": "targetResourceBindings[0].entryPoint",
                    "expected": "non-empty string",
                    "actual": "",
                },
            )
            self.assertEqual(
                list(package_dir.rglob("*.cgl")),
                [package_dir / "source" / "invalid.cgl"],
            )

    def test_compatibility_report_reports_missing_artifact_contract_fields(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory(suffix=".cglb") as temp_dir:
            package_dir = Path(temp_dir)
            self._write_valid_package(package_dir)
            manifest_path = package_dir / "manifest.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            del manifest["artifacts"]
            self._write_json(manifest_path, manifest)

            report = read_compatibility_report(package_dir, loader_target="metal")
            summary = report.to_summary()

            self.assertFalse(report.compatible)
            self.assertEqual(report.status, "missing-artifact")
            self.assertEqual(summary["availableArtifacts"], [])
            self.assertEqual(summary["availableTargets"], ["metal"])
            self.assertIn(
                "package.artifacts.missing",
                [diagnostic.code for diagnostic in report.reject_reasons],
            )
            self.assertEqual(
                [diagnostic.code for diagnostic in report.missing_artifacts],
                [
                    "package.artifact.required_missing",
                    "package.artifact.required_missing",
                    "package.artifact.required_missing",
                ],
            )
            with self.assertRaisesRegex(
                PackageReadError,
                "manifest.artifacts must be a non-empty object",
            ):
                read_package(package_dir)

    def test_compatibility_report_rejects_non_object_artifact_section_without_source_parse(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory(suffix=".cglb") as temp_dir:
            package_dir = Path(temp_dir)
            self._write_valid_package(package_dir)
            source_path = package_dir / "source" / "invalid.cgl"
            source_path.parent.mkdir()
            source_path.write_text(
                "runtime must not infer artifact records from source\n",
                encoding="utf-8",
            )
            manifest_path = package_dir / "manifest.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["artifacts"] = [
                {
                    "name": "backendSource",
                    "path": "backend/metal/RuntimeReaderFixture.metal",
                }
            ]
            self._write_json(manifest_path, manifest)

            with self._guard_crossgl_source_reads():
                report = read_compatibility_report(package_dir, loader_target="metal")
                selection = select_runtime_artifact(report, target="metal")

            summary = report.to_summary()

            self.assertFalse(report.compatible)
            self.assertEqual(report.status, "missing-artifact")
            self.assertFalse(report.source_parsing_required)
            self.assertFalse(selection.selected)
            self.assertIsNone(selection.artifact)
            self.assertFalse(selection.source_parsing_required)
            self.assertEqual(summary["availableArtifacts"], [])
            self.assertIn(
                "package.artifacts.invalid",
                [diagnostic.code for diagnostic in report.reject_reasons],
            )
            self.assertEqual(
                [diagnostic.code for diagnostic in report.missing_artifacts],
                [
                    "package.artifact.required_missing",
                    "package.artifact.required_missing",
                    "package.artifact.required_missing",
                ],
            )
            self.assertEqual(
                summary["rejectReasons"][0],
                {
                    "severity": "error",
                    "code": "package.artifacts.invalid",
                    "message": "manifest.artifacts must be a non-empty object",
                    "document": "manifest",
                    "path": "artifacts",
                    "expected": "non-empty object",
                    "actual": "array",
                },
            )
            self.assertEqual(list(package_dir.rglob("*.cgl")), [source_path])
            with self.assertRaisesRegex(
                PackageReadError,
                "manifest.artifacts must be a non-empty object",
            ):
                read_package(package_dir)

    def test_compatibility_report_rejects_empty_artifact_name(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory(suffix=".cglb") as temp_dir:
            package_dir = Path(temp_dir)
            self._write_valid_package(package_dir)
            manifest_path = package_dir / "manifest.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["artifacts"][""] = "backend/metal/unnamed.metal"
            self._write_json(manifest_path, manifest)

            report = read_compatibility_report(package_dir, loader_target="metal")
            summary = report.to_summary()

            self.assertFalse(report.compatible)
            self.assertEqual(report.status, "incompatible")
            self.assertIn(
                "package.artifact.name_invalid",
                [diagnostic.code for diagnostic in report.reject_reasons],
            )
            self.assertEqual(
                next(
                    diagnostic
                    for diagnostic in summary["rejectReasons"]
                    if diagnostic["code"] == "package.artifact.name_invalid"
                ),
                {
                    "severity": "error",
                    "code": "package.artifact.name_invalid",
                    "message": (
                        "manifest.artifacts keys must be non-empty artifact names"
                    ),
                    "document": "manifest",
                    "expected": "non-empty artifact name",
                    "actual": "",
                },
            )
            self.assertNotIn(
                "",
                [artifact["name"] for artifact in summary["availableArtifacts"]],
            )
            with self.assertRaisesRegex(
                PackageReadError,
                "manifest.artifacts keys must be non-empty artifact names",
            ):
                read_package(package_dir)

    def test_compatibility_report_rejects_unexpected_artifact_metadata(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory(suffix=".cglb") as temp_dir:
            package_dir = Path(temp_dir)
            self._write_valid_package(package_dir)
            manifest_path = package_dir / "manifest.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["artifacts"]["shaderBlob"] = (
                "backend/metal/RuntimeReaderFixture.metallib"
            )
            self._write_json(manifest_path, manifest)

            report = read_compatibility_report(package_dir, loader_target="metal")
            selection = select_runtime_artifact(report, target="metal")
            summary = report.to_summary()

            self.assertFalse(report.compatible)
            self.assertEqual(report.status, "incompatible")
            self.assertFalse(selection.selected)
            self.assertEqual(
                report.required_artifacts,
                ("backendSource", "intermediate", "nativeBinary"),
            )
            self.assertNotIn(
                "shaderBlob",
                [artifact.name for artifact in report.available_artifacts],
            )
            self.assertEqual(
                next(
                    diagnostic
                    for diagnostic in summary["rejectReasons"]
                    if diagnostic["code"] == "package.artifact.unexpected"
                ),
                {
                    "severity": "error",
                    "code": "package.artifact.unexpected",
                    "message": (
                        "manifest.artifacts contains an unexpected artifact field: "
                        "shaderBlob"
                    ),
                    "document": "manifest",
                    "artifact": "shaderBlob",
                    "path": "artifacts.shaderBlob",
                    "expected": [
                        "backendAssembly",
                        "backendSource",
                        "debugMetadata",
                        "graphicsAbi",
                        "hirSourceMap",
                        "intermediate",
                        "nativeArtifactDescriptor",
                        "nativeBinary",
                        "nativeBinaryStatus",
                        "nativeProfile",
                        "targetExplanation",
                    ],
                    "actual": "shaderBlob",
                },
            )
            with self.assertRaisesRegex(
                PackageReadError,
                "manifest.artifacts.shaderBlob is not a recognized artifact field",
            ):
                read_package(package_dir)

    def test_compatibility_report_rejects_object_shaped_artifact_metadata_without_inference(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory(suffix=".cglb") as temp_dir:
            package_dir = Path(temp_dir)
            self._write_valid_package(package_dir)
            (package_dir / "source").mkdir()
            (package_dir / "source" / "invalid.cgl").write_text(
                "runtime must not infer artifact paths from package source\n",
                encoding="utf-8",
            )
            manifest_path = package_dir / "manifest.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["artifacts"]["backendSource"] = {
                "path": "backend/metal/RuntimeReaderFixture.metal"
            }
            self._write_json(manifest_path, manifest)

            report = read_compatibility_report(package_dir, loader_target="metal")
            selection = select_runtime_artifact(report, target="metal")
            summary = report.to_summary()

            self.assertFalse(report.compatible)
            self.assertEqual(report.status, "missing-artifact")
            self.assertFalse(report.source_parsing_required)
            self.assertFalse(selection.selected)
            self.assertIsNone(selection.artifact)
            self.assertNotIn(
                "backendSource",
                [artifact.name for artifact in report.available_artifacts],
            )
            self.assertIn(
                "package.artifact.path_invalid",
                [diagnostic.code for diagnostic in report.reject_reasons],
            )
            self.assertIn(
                "package.artifact.required_missing",
                [diagnostic.code for diagnostic in report.reject_reasons],
            )
            self.assertEqual(
                next(
                    diagnostic
                    for diagnostic in summary["rejectReasons"]
                    if diagnostic["code"] == "package.artifact.path_invalid"
                ),
                {
                    "severity": "error",
                    "code": "package.artifact.path_invalid",
                    "message": (
                        "manifest.artifacts must map artifact names to strings"
                    ),
                    "document": "manifest",
                    "artifact": "backendSource",
                    "path": "artifacts.backendSource",
                    "expected": "package-relative path string",
                    "actual": "object",
                },
            )
            self.assertEqual(
                list(package_dir.rglob("*.cgl")),
                [package_dir / "source" / "invalid.cgl"],
            )
            with self.assertRaisesRegex(
                PackageReadError,
                "manifest.artifacts must map strings to strings",
            ):
                read_package(package_dir)

    def test_compatibility_report_rejects_duplicate_manifest_artifact_paths(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory(suffix=".cglb") as temp_dir:
            package_dir = Path(temp_dir)
            self._write_valid_package(package_dir)
            (package_dir / "source").mkdir()
            (package_dir / "source" / "invalid.cgl").write_text(
                "runtime must not infer artifact roles from duplicate paths\n",
                encoding="utf-8",
            )
            manifest_path = package_dir / "manifest.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["artifacts"]["intermediate"] = manifest["artifacts"][
                "backendSource"
            ]
            self._write_json(manifest_path, manifest)

            report = read_compatibility_report(package_dir, loader_target="metal")
            selection = select_runtime_artifact(report, target="metal")
            summary = report.to_summary()

            self.assertFalse(report.compatible)
            self.assertEqual(report.status, "incompatible")
            self.assertFalse(report.source_parsing_required)
            self.assertFalse(selection.selected)
            self.assertEqual(
                [diagnostic.code for diagnostic in report.reject_reasons],
                [
                    "package.artifact.path_duplicate",
                    "package.artifacts.contract_invalid",
                ],
            )
            self.assertEqual(
                summary["rejectReasons"][0],
                {
                    "severity": "error",
                    "code": "package.artifact.path_duplicate",
                    "message": (
                        "manifest.artifacts.intermediate reuses path declared by "
                        "backendSource: backend/metal/RuntimeReaderFixture.metal"
                    ),
                    "document": "manifest",
                    "artifact": "intermediate",
                    "path": "artifacts.intermediate",
                    "expected": "unique package-relative path",
                    "actual": "backend/metal/RuntimeReaderFixture.metal",
                },
            )
            contract_reject = next(
                diagnostic
                for diagnostic in summary["rejectReasons"]
                if diagnostic["code"] == "package.artifacts.contract_invalid"
            )
            self.assertEqual(
                [diagnostic["code"] for diagnostic in contract_reject["actual"]],
                ["package.artifact.path_duplicate"],
            )
            self.assertEqual(
                list(package_dir.rglob("*.cgl")),
                [package_dir / "source" / "invalid.cgl"],
            )
            with self.assertRaisesRegex(
                PackageReadError,
                "manifest.artifacts.intermediate reuses path declared by backendSource",
            ):
                read_package(package_dir)

    def test_compatibility_report_rejects_normalized_duplicate_manifest_artifact_paths(
        self,
    ) -> None:
        for package_format in ("directory", "zip"):
            with self.subTest(package_format=package_format):
                with tempfile.TemporaryDirectory() as temp_dir:
                    temp_root = Path(temp_dir)
                    package_dir = temp_root / "package-dir"
                    package_dir.mkdir()
                    self._write_valid_package(package_dir)
                    (package_dir / "source").mkdir()
                    (package_dir / "source" / "invalid.cgl").write_text(
                        "runtime must not infer artifact roles from aliases\n",
                        encoding="utf-8",
                    )
                    manifest_path = package_dir / "manifest.json"
                    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
                    manifest["artifacts"]["intermediate"] = (
                        "backend/metal/./RuntimeReaderFixture.metal"
                    )
                    self._write_json(manifest_path, manifest)

                    package_path = package_dir
                    guard = nullcontext()
                    if package_format == "zip":
                        zip_path = temp_root / "RuntimeReaderFixture.cglb"
                        self._write_zip_package(
                            package_dir,
                            zip_path,
                            prefix=zip_path.name,
                        )
                        package_path = zip_path
                        guard = self._guard_zip_crossgl_member_reads()

                    with guard:
                        report = read_compatibility_report(
                            package_path,
                            loader_target="metal",
                        )
                    summary = report.to_summary()

                    self.assertFalse(report.compatible)
                    self.assertEqual(report.status, "incompatible")
                    self.assertFalse(report.source_parsing_required)
                    self.assertEqual(
                        [diagnostic.code for diagnostic in report.reject_reasons],
                        [
                            "package.artifact.path_duplicate",
                            "package.artifacts.contract_invalid",
                        ],
                    )
                    self.assertEqual(
                        summary["rejectReasons"][0]["message"],
                        (
                            "manifest.artifacts.intermediate reuses path declared by "
                            "backendSource: "
                            "backend/metal/./RuntimeReaderFixture.metal"
                        ),
                    )
                    with self.assertRaisesRegex(
                        PackageReadError,
                        (
                            "manifest.artifacts.intermediate reuses path declared by "
                            "backendSource"
                        ),
                    ):
                        read_package(package_path)

    def test_compatibility_report_rejects_malformed_native_binary_status(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory(suffix=".cglb") as temp_dir:
            package_dir = Path(temp_dir)
            self._write_valid_package(package_dir, target="directx")
            manifest_path = package_dir / "manifest.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["artifacts"]["nativeBinaryStatus"] = {"status": "planned"}
            self._write_json(manifest_path, manifest)

            report = read_compatibility_report(package_dir, loader_target="directx")
            selection = select_runtime_artifact(report, target="directx")
            summary = report.to_summary()
            reject_codes = [diagnostic.code for diagnostic in report.reject_reasons]

            self.assertFalse(report.compatible)
            self.assertEqual(report.status, "incompatible")
            self.assertEqual(summary["sourceInputs"], [])
            self.assertFalse(summary["compilerInvocationRequired"])
            self.assertFalse(summary["deviceExecutionRequired"])
            self.assertEqual(summary["nativeBinaryStatus"], {"status": "planned"})
            self.assertIn("package.native_binary_status.invalid", reject_codes)
            self.assertIn("package.artifacts.contract_invalid", reject_codes)
            self.assertEqual(
                next(
                    diagnostic
                    for diagnostic in summary["rejectReasons"]
                    if diagnostic["code"] == "package.native_binary_status.invalid"
                ),
                {
                    "severity": "error",
                    "code": "package.native_binary_status.invalid",
                    "message": (
                        "manifest.artifacts.nativeBinaryStatus must be a string"
                    ),
                    "document": "manifest",
                    "artifact": "nativeBinaryStatus",
                    "expected": ["planned", "emitted"],
                    "actual": "object",
                },
            )
            contract_reject = next(
                diagnostic
                for diagnostic in summary["rejectReasons"]
                if diagnostic["code"] == "package.artifacts.contract_invalid"
            )
            self.assertEqual(contract_reject["path"], "artifacts.nativeBinaryStatus")
            self.assertEqual(
                [diagnostic["code"] for diagnostic in contract_reject["actual"]],
                ["package.native_binary_status.invalid"],
            )
            self.assertFalse(selection.selected)
            self.assertEqual(selection.to_summary()["sourceInputs"], [])
            self.assertFalse(selection.to_summary()["compilerInvocationRequired"])
            self.assertFalse(selection.to_summary()["deviceExecutionRequired"])
            with self.assertRaisesRegex(
                PackageReadError,
                "manifest.artifacts.nativeBinaryStatus must be a string",
            ):
                read_package(package_dir)

    def test_compatibility_report_rejects_malformed_native_binary_status_for_unsupported_target(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory(suffix=".cglb") as temp_dir:
            package_dir = Path(temp_dir)
            self._write_valid_package(package_dir, target="spirv")
            manifest_path = package_dir / "manifest.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["artifacts"]["nativeBinaryStatus"] = {"status": "planned"}
            self._write_json(manifest_path, manifest)

            report = read_compatibility_report(package_dir)
            summary = report.to_summary()
            reject_codes = [diagnostic.code for diagnostic in report.reject_reasons]

            self.assertFalse(report.compatible)
            self.assertEqual(report.status, "unsupported-target")
            self.assertEqual(summary["nativeBinaryStatus"], {"status": "planned"})
            self.assertIn("package.target.unsupported", reject_codes)
            self.assertIn("package.native_binary_status.invalid", reject_codes)
            self.assertIn("package.artifacts.contract_invalid", reject_codes)
            self.assertEqual(summary["sourceInputs"], [])
            self.assertFalse(summary["compilerInvocationRequired"])
            self.assertFalse(summary["deviceExecutionRequired"])
            self.assertEqual(
                next(
                    diagnostic
                    for diagnostic in summary["rejectReasons"]
                    if diagnostic["code"] == "package.native_binary_status.invalid"
                ),
                {
                    "severity": "error",
                    "code": "package.native_binary_status.invalid",
                    "message": (
                        "manifest.artifacts.nativeBinaryStatus must be a string"
                    ),
                    "document": "manifest",
                    "artifact": "nativeBinaryStatus",
                    "actual": "object",
                },
            )
            contract_reject = next(
                diagnostic
                for diagnostic in summary["rejectReasons"]
                if diagnostic["code"] == "package.artifacts.contract_invalid"
            )
            self.assertEqual(contract_reject["path"], "artifacts.nativeBinaryStatus")
            self.assertEqual(
                [diagnostic["code"] for diagnostic in contract_reject["actual"]],
                ["package.native_binary_status.invalid"],
            )
            with self.assertRaisesRegex(
                PackageReadError,
                "manifest.artifacts.nativeBinaryStatus must be a string",
            ):
                read_package(package_dir)

    def test_rejects_artifact_paths_outside_package(self) -> None:
        with tempfile.TemporaryDirectory(suffix=".cglb") as temp_dir:
            package_dir = Path(temp_dir)
            self._write_valid_package(package_dir)
            (package_dir / "source").mkdir()
            (package_dir / "source" / "invalid.cgl").write_text(
                "runtime report must not parse this source\n",
                encoding="utf-8",
            )
            manifest_path = package_dir / "manifest.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["artifacts"]["backendSource"] = "../escape.metal"
            self._write_json(manifest_path, manifest)

            report = read_compatibility_report(package_dir, loader_target="metal")

            self.assertFalse(report.compatible)
            self.assertEqual(report.status, "missing-artifact")
            reject_codes = [diagnostic.code for diagnostic in report.reject_reasons]
            self.assertLess(
                reject_codes.index("package.artifact.path_invalid"),
                reject_codes.index("package.artifacts.contract_invalid"),
            )
            self.assertIn("package.artifact.required_missing", reject_codes)
            contract_reject = next(
                diagnostic
                for diagnostic in report.to_summary()["rejectReasons"]
                if diagnostic["code"] == "package.artifacts.contract_invalid"
            )
            self.assertEqual(
                [diagnostic["code"] for diagnostic in contract_reject["actual"]],
                ["package.artifact.path_invalid"],
            )
            self.assertEqual(report.missing_artifacts[0].artifact, "backendSource")
            with self.assertRaisesRegex(
                PackageReadError,
                "manifest.artifacts.backendSource escapes the package directory",
            ):
                read_package(package_dir)

    def test_compatibility_report_rejects_target_incompatible_native_profile(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory(suffix=".cglb") as temp_dir:
            package_dir = Path(temp_dir)
            self._write_valid_package(
                package_dir,
                target="directx",
                native_status="emitted",
            )
            profile_path = package_dir / "backend" / "directx" / "profile.json"
            profile_path.write_text("{}\n", encoding="utf-8")
            manifest_path = package_dir / "manifest.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["artifacts"]["nativeProfile"] = "backend/directx/profile.json"
            self._write_json(manifest_path, manifest)

            report = read_compatibility_report(package_dir, loader_target="directx")
            selection = select_runtime_artifact(report, target="directx")
            summary = report.to_summary()
            selection_summary = selection.to_summary()

            self.assertFalse(report.compatible)
            self.assertEqual(report.status, "incompatible")
            self.assertFalse(report.source_parsing_required)
            self.assertFalse(report.compiler_invocation_required)
            self.assertFalse(report.device_execution_required)
            self.assertEqual(report.source_inputs, ())
            self.assertFalse(selection.selected)
            self.assertIsNone(selection.artifact)
            self.assertEqual(summary["sourceParsingRequired"], False)
            self.assertEqual(summary["compilerInvocationRequired"], False)
            self.assertEqual(summary["deviceExecutionRequired"], False)
            self.assertEqual(summary["sourceInputs"], [])
            self.assertEqual(selection_summary["sourceParsingRequired"], False)
            self.assertEqual(selection_summary["compilerInvocationRequired"], False)
            self.assertEqual(selection_summary["deviceExecutionRequired"], False)
            self.assertEqual(selection_summary["sourceInputs"], [])
            self.assertEqual(
                summary["rejectReasons"],
                [
                    {
                        "severity": "error",
                        "code": "package.artifact.target_incompatible",
                        "message": (
                            "manifest.artifacts.nativeProfile is only valid for "
                            "vulkan packages"
                        ),
                        "document": "manifest",
                        "artifact": "nativeProfile",
                        "path": "backend/directx/profile.json",
                        "expected": "vulkan",
                        "actual": "directx",
                    }
                ],
            )

    def test_read_package_accepts_flat_reflection_target_abi_records(
        self,
    ) -> None:
        cases = (
            (
                "directx",
                {
                    "abi": "registerBinding",
                    "bindingClass": "uav",
                    "descriptorType": "UAV",
                    "argumentIndex": 0,
                    "set": 0,
                    "binding": 0,
                },
            ),
            (
                "metal",
                {
                    "abi": "kernelArgument",
                    "bindingClass": "buffer",
                    "argumentIndex": 0,
                    "set": 0,
                    "binding": 0,
                },
            ),
            (
                "opengl",
                {
                    "abi": "programResourceBinding",
                    "bindingClass": "storage-buffer",
                    "argumentIndex": 0,
                    "set": 0,
                    "binding": 0,
                },
            ),
            (
                "vulkan",
                {
                    "abi": "descriptor",
                    "bindingClass": "storage-buffer",
                    "descriptorType": "VK_DESCRIPTOR_TYPE_STORAGE_BUFFER",
                    "set": 0,
                    "binding": 0,
                },
            ),
        )

        for target, flat_abi in cases:
            with self.subTest(target=target):
                with tempfile.TemporaryDirectory(suffix=".cglb") as temp_dir:
                    package_dir = Path(temp_dir)
                    self._write_valid_package(package_dir, target=target)
                    manifest_path = package_dir / "manifest.json"
                    reflection_path = package_dir / "reflection.json"
                    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
                    reflection = json.loads(reflection_path.read_text(encoding="utf-8"))
                    if target == "opengl":
                        native_binary_path = (
                            "backend/opengl/RuntimeReaderFixture.native.glsl"
                        )
                        (package_dir / native_binary_path).write_bytes(b"native")
                        manifest["artifacts"]["nativeBinary"] = native_binary_path
                        reflection["nativeBinary"] = native_binary_path
                    binding = reflection["targetResourceBindings"][0]
                    for field_name in (
                        "abi",
                        "bindingClass",
                        "descriptorType",
                        "hlslType",
                        "metalType",
                        "storageClass",
                        "spirvType",
                        "argumentIndex",
                        "set",
                        "binding",
                    ):
                        binding.pop(field_name, None)
                    binding.update(flat_abi)
                    self._write_json(manifest_path, manifest)
                    self._write_json(reflection_path, reflection)
                    source_path = package_dir / "source" / "invalid.cgl"
                    source_path.parent.mkdir()
                    source_path.write_text(
                        "runtime must not parse CrossGL source for flat ABI checks\n",
                        encoding="utf-8",
                    )

                    with self._guard_crossgl_source_reads():
                        package = read_package(package_dir)

                    self.assertEqual(package.target, target)
                    self.assertEqual(
                        package.reflection["targetResourceBindings"][0]["abi"],
                        flat_abi["abi"],
                    )
                    self.assertEqual(list(package_dir.rglob("*.cgl")), [source_path])

    def test_compatibility_report_rejects_target_abi_mismatch_without_source_parse(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory(suffix=".cglb") as temp_dir:
            package_dir = Path(temp_dir)
            self._write_valid_package(
                package_dir,
                target="directx",
                native_status="emitted",
            )
            reflection_path = package_dir / "reflection.json"
            reflection = json.loads(reflection_path.read_text(encoding="utf-8"))
            reflection["targetResourceBindings"][0]["abi"] = {
                "set": 0,
                "binding": 0,
            }
            self._write_json(reflection_path, reflection)
            source_path = package_dir / "source" / "invalid.cgl"
            source_path.parent.mkdir()
            source_path.write_text(
                "runtime must not parse CrossGL source for target ABI checks\n",
                encoding="utf-8",
            )

            with self._guard_crossgl_source_reads():
                report = read_compatibility_report(
                    package_dir,
                    loader_target="directx",
                )
                selection = select_runtime_artifact(report, target="directx")

            summary = report.to_summary()
            selection_summary = selection.to_summary()
            expected_code = "package.reflection.target_resource_binding_abi_invalid"
            diagnostic = next(
                diagnostic
                for diagnostic in summary["rejectReasons"]
                if diagnostic["code"] == expected_code
            )

            self.assertFalse(report.compatible)
            self.assertEqual(report.status, "incompatible")
            self.assertFalse(report.source_parsing_required)
            self.assertFalse(selection.selected)
            self.assertIsNone(selection.artifact)
            self.assertEqual(summary["admission"]["target"]["reason"], expected_code)
            self.assertEqual(diagnostic["document"], "reflection")
            self.assertEqual(diagnostic["path"], "targetResourceBindings[0].abi")
            self.assertIn("DirectX register ABI", diagnostic["expected"])
            self.assertEqual(diagnostic["actual"], {"set": 0, "binding": 0})
            self.assertIn(
                expected_code,
                [
                    diagnostic["code"]
                    for diagnostic in selection_summary["admission"]["target"][
                        "diagnostics"
                    ]
                ],
            )
            with self._guard_crossgl_source_reads():
                with self.assertRaisesRegex(
                    PackageReadError,
                    "reflection target ABI is not compatible",
                ):
                    read_package(package_dir)
            self.assertEqual(list(package_dir.rglob("*.cgl")), [source_path])

    def test_compatibility_report_rejects_flat_target_abi_mismatch_without_source_parse(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory(suffix=".cglb") as temp_dir:
            package_dir = Path(temp_dir)
            self._write_valid_package(
                package_dir,
                target="directx",
                native_status="emitted",
            )
            reflection_path = package_dir / "reflection.json"
            reflection = json.loads(reflection_path.read_text(encoding="utf-8"))
            binding = reflection["targetResourceBindings"][0]
            for field_name in (
                "abi",
                "bindingClass",
                "descriptorType",
                "hlslType",
                "argumentIndex",
                "set",
                "binding",
            ):
                binding.pop(field_name, None)
            binding.update(
                {
                    "abi": "programResourceBinding",
                    "bindingClass": "storage-buffer",
                    "argumentIndex": 0,
                    "set": 0,
                    "binding": 0,
                }
            )
            self._write_json(reflection_path, reflection)
            source_path = package_dir / "source" / "invalid.cgl"
            source_path.parent.mkdir()
            source_path.write_text(
                "runtime must not parse CrossGL source for flat ABI checks\n",
                encoding="utf-8",
            )

            with self._guard_crossgl_source_reads():
                report = read_compatibility_report(
                    package_dir,
                    loader_target="directx",
                )
                selection = select_runtime_artifact(report, target="directx")

            summary = report.to_summary()
            selection_summary = selection.to_summary()
            expected_code = "package.reflection.target_resource_binding_abi_invalid"
            diagnostic = next(
                diagnostic
                for diagnostic in summary["rejectReasons"]
                if diagnostic["code"] == expected_code
            )

            self.assertFalse(report.compatible)
            self.assertEqual(report.status, "incompatible")
            self.assertFalse(report.source_parsing_required)
            self.assertFalse(selection.selected)
            self.assertIsNone(selection.artifact)
            self.assertEqual(summary["admission"]["target"]["reason"], expected_code)
            self.assertEqual(diagnostic["document"], "reflection")
            self.assertEqual(diagnostic["path"], "targetResourceBindings[0].abi")
            self.assertIn("DirectX register ABI", diagnostic["expected"])
            self.assertEqual(
                diagnostic["actual"],
                {
                    "abi": "programResourceBinding",
                    "bindingClass": "storage-buffer",
                    "argumentIndex": 0,
                    "set": 0,
                    "binding": 0,
                },
            )
            self.assertIn(
                expected_code,
                [
                    diagnostic["code"]
                    for diagnostic in selection_summary["admission"]["target"][
                        "diagnostics"
                    ]
                ],
            )
            with self._guard_crossgl_source_reads():
                with self.assertRaisesRegex(
                    PackageReadError,
                    "reflection target ABI is not compatible",
                ):
                    read_package(package_dir)
            self.assertEqual(list(package_dir.rglob("*.cgl")), [source_path])

    def test_compatibility_report_rejects_malformed_native_profile_metadata_without_source_parse(
        self,
    ) -> None:
        cases = (
            (
                "declared profile missing",
                None,
                "package.native_profile.file_missing",
                "backend/vulkan/native-profile.json",
                "incompatible",
            ),
            (
                "profile not object",
                lambda path: path.write_text("[]\n", encoding="utf-8"),
                "package.native_profile.invalid",
                "backend/vulkan/native-profile.json",
                "incompatible",
            ),
            (
                "future profile schema",
                lambda path: self._write_json(
                    path,
                    {"schemaVersion": 2, "target": "vulkan"},
                ),
                "package.native_profile.schema_incompatible",
                "schemaVersion",
                "unsupported-version",
            ),
            (
                "missing profile schema",
                lambda path: self._write_json(
                    path,
                    {"target": "vulkan"},
                ),
                "package.native_profile.schema_version_missing",
                "schemaVersion",
                "unsupported-version",
            ),
            (
                "malformed profile schema",
                lambda path: self._write_json(
                    path,
                    {"schemaVersion": "1", "target": "vulkan"},
                ),
                "package.native_profile.schema_version_invalid",
                "schemaVersion",
                "unsupported-version",
            ),
            (
                "missing profile target",
                lambda path: self._write_json(
                    path,
                    {"schemaVersion": 1},
                ),
                "package.native_profile.target_invalid",
                "target",
                "incompatible",
            ),
            (
                "profile target mismatch",
                lambda path: self._write_json(
                    path,
                    {"schemaVersion": 1, "target": "metal"},
                ),
                "package.native_profile.target_mismatch",
                "target",
                "incompatible",
            ),
        )

        for (
            name,
            write_profile,
            expected_code,
            expected_path,
            expected_status,
        ) in cases:
            with self.subTest(name=name):
                with tempfile.TemporaryDirectory(suffix=".cglb") as temp_dir:
                    package_dir = Path(temp_dir)
                    self._write_valid_package(package_dir, target="vulkan")
                    backend_dir = package_dir / "backend" / "vulkan"
                    assembly_path = backend_dir / "RuntimeReaderFixture.spvasm"
                    assembly_path.write_bytes(b"spvasm")
                    profile_path = backend_dir / "native-profile.json"
                    manifest_path = package_dir / "manifest.json"
                    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
                    manifest["artifacts"]["backendAssembly"] = (
                        "backend/vulkan/RuntimeReaderFixture.spvasm"
                    )
                    manifest["artifacts"]["nativeProfile"] = (
                        "backend/vulkan/native-profile.json"
                    )
                    self._write_json(manifest_path, manifest)
                    if write_profile is not None:
                        write_profile(profile_path)
                    source_path = package_dir / "source" / "invalid.cgl"
                    source_path.parent.mkdir()
                    source_path.write_text(
                        "runtime must not parse CrossGL source for malformed "
                        "native profile metadata\n",
                        encoding="utf-8",
                    )

                    with self._guard_crossgl_source_reads():
                        report = read_compatibility_report(
                            package_dir,
                            loader_target="vulkan",
                        )
                        selection = select_runtime_artifact(
                            report,
                            target="vulkan",
                        )

                    summary = report.to_summary()
                    selection_summary = selection.to_summary()
                    native_admission = selection_summary["admission"]["native"]

                    self.assertFalse(report.compatible)
                    self.assertEqual(report.status, expected_status)
                    self.assertFalse(report.source_parsing_required)
                    self.assertFalse(selection.selected)
                    self.assertIsNone(selection.artifact)
                    self.assertFalse(selection.source_parsing_required)
                    self.assertIn(
                        expected_code,
                        [diagnostic.code for diagnostic in report.reject_reasons],
                    )
                    self.assertNotIn(
                        "package.target.unsupported",
                        [diagnostic.code for diagnostic in report.reject_reasons],
                    )
                    self.assertEqual(native_admission["reason"], expected_code)
                    self.assertIn(
                        expected_code,
                        [
                            diagnostic["code"]
                            for diagnostic in native_admission["diagnostics"]
                        ],
                    )
                    self.assertEqual(
                        next(
                            diagnostic
                            for diagnostic in summary["rejectReasons"]
                            if diagnostic["code"] == expected_code
                        )["path"],
                        expected_path,
                    )
                    artifact_compatibility = summary["artifactCompatibility"]
                    artifact_records = {
                        artifact["name"]: artifact
                        for artifact in artifact_compatibility["artifacts"]
                    }
                    self.assertIsNone(artifact_compatibility["selectedArtifact"])
                    self.assertEqual(
                        artifact_records["nativeProfile"]["decision"],
                        "rejected",
                    )
                    self.assertEqual(
                        artifact_records["nativeProfile"]["reason"],
                        expected_code,
                    )
                    self.assertEqual(
                        [
                            diagnostic["code"]
                            for diagnostic in artifact_records["nativeProfile"][
                                "diagnostics"
                            ]
                        ],
                        [expected_code],
                    )
                    self.assertEqual(
                        artifact_records["nativeBinary"]["decision"],
                        "accepted",
                    )
                    self.assertEqual(
                        artifact_records["nativeBinary"]["reason"],
                        "package.artifact.accepted",
                    )
                    self.assertEqual(list(package_dir.rglob("*.cgl")), [source_path])

    def test_compatibility_report_rejects_native_profile_artifact_link_drift_without_source_parse(
        self,
    ) -> None:
        cases = (
            (
                "missing backend assembly",
                {
                    "schemaVersion": 1,
                    "target": "vulkan",
                    "nativeBinary": "backend/vulkan/RuntimeReaderFixture.bin",
                },
                "package.native_profile.backend_assembly_missing",
                "backendAssembly",
                "backend/vulkan/RuntimeReaderFixture.spvasm",
                "missing",
            ),
            (
                "stale backend assembly",
                {
                    "schemaVersion": 1,
                    "target": "vulkan",
                    "backendAssembly": "backend/vulkan/stale.spvasm",
                    "nativeBinary": "backend/vulkan/RuntimeReaderFixture.bin",
                },
                "package.native_profile.backend_assembly_mismatch",
                "backendAssembly",
                "backend/vulkan/RuntimeReaderFixture.spvasm",
                "backend/vulkan/stale.spvasm",
            ),
            (
                "missing native binary",
                {
                    "schemaVersion": 1,
                    "target": "vulkan",
                    "backendAssembly": "backend/vulkan/RuntimeReaderFixture.spvasm",
                },
                "package.native_profile.native_binary_missing",
                "nativeBinary",
                "backend/vulkan/RuntimeReaderFixture.bin",
                "missing",
            ),
            (
                "stale native binary",
                {
                    "schemaVersion": 1,
                    "target": "vulkan",
                    "backendAssembly": "backend/vulkan/RuntimeReaderFixture.spvasm",
                    "nativeBinary": "backend/vulkan/stale.spv",
                },
                "package.native_profile.native_binary_mismatch",
                "nativeBinary",
                "backend/vulkan/RuntimeReaderFixture.bin",
                "backend/vulkan/stale.spv",
            ),
        )

        for (
            name,
            profile,
            expected_code,
            expected_path,
            expected_value,
            actual_value,
        ) in cases:
            with self.subTest(name=name):
                with tempfile.TemporaryDirectory(suffix=".cglb") as temp_dir:
                    package_dir = Path(temp_dir)
                    self._write_valid_package(package_dir, target="vulkan")
                    backend_dir = package_dir / "backend" / "vulkan"
                    assembly_path = backend_dir / "RuntimeReaderFixture.spvasm"
                    assembly_path.write_bytes(b"spvasm")
                    profile_path = backend_dir / "native-profile.json"
                    manifest_path = package_dir / "manifest.json"
                    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
                    manifest["artifacts"]["backendAssembly"] = (
                        "backend/vulkan/RuntimeReaderFixture.spvasm"
                    )
                    manifest["artifacts"]["nativeProfile"] = (
                        "backend/vulkan/native-profile.json"
                    )
                    self._write_json(manifest_path, manifest)
                    self._write_json(profile_path, profile)
                    source_path = package_dir / "source" / "invalid.cgl"
                    source_path.parent.mkdir()
                    source_path.write_text(
                        "runtime must not parse CrossGL source to repair "
                        "native profile artifact links\n",
                        encoding="utf-8",
                    )

                    with self._guard_crossgl_source_reads():
                        report = read_compatibility_report(
                            package_dir,
                            loader_target="vulkan",
                        )
                        selection = select_runtime_artifact(
                            report,
                            target="vulkan",
                        )

                    summary = report.to_summary()
                    selection_summary = selection.to_summary()
                    diagnostic = next(
                        diagnostic
                        for diagnostic in summary["rejectReasons"]
                        if diagnostic["code"] == expected_code
                    )
                    artifact_records = {
                        artifact["name"]: artifact
                        for artifact in summary["artifactCompatibility"]["artifacts"]
                    }

                    self.assertFalse(report.compatible)
                    self.assertEqual(report.status, "incompatible")
                    self.assertFalse(report.source_parsing_required)
                    self.assertFalse(selection.selected)
                    self.assertIsNone(selection.artifact)
                    self.assertFalse(selection.source_parsing_required)
                    self.assertEqual(diagnostic["document"], "nativeProfile")
                    self.assertEqual(diagnostic["artifact"], "nativeProfile")
                    self.assertEqual(diagnostic["path"], expected_path)
                    self.assertEqual(diagnostic["expected"], expected_value)
                    self.assertEqual(diagnostic["actual"], actual_value)
                    self.assertEqual(
                        selection_summary["admission"]["native"]["reason"],
                        expected_code,
                    )
                    self.assertIn(
                        expected_code,
                        [
                            diagnostic["code"]
                            for diagnostic in selection_summary["admission"]["native"][
                                "diagnostics"
                            ]
                        ],
                    )
                    self.assertEqual(
                        artifact_records["nativeProfile"]["decision"],
                        "rejected",
                    )
                    self.assertEqual(
                        artifact_records["nativeProfile"]["reason"],
                        expected_code,
                    )
                    self.assertEqual(
                        [
                            diagnostic["code"]
                            for diagnostic in artifact_records["nativeProfile"][
                                "diagnostics"
                            ]
                        ],
                        [expected_code],
                    )
                    self.assertEqual(list(package_dir.rglob("*.cgl")), [source_path])

    def test_cli_outputs_json_summary(self) -> None:
        with tempfile.TemporaryDirectory(suffix=".cglb") as temp_dir:
            package_dir = Path(temp_dir)
            self._write_valid_package(package_dir)

            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "runtime.package_reader",
                    str(package_dir),
                    "--json",
                ],
                cwd=REPO_ROOT,
                check=False,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            summary = json.loads(result.stdout)
            self.assertEqual(summary["module"], "RuntimeReaderFixture")
            self.assertEqual(summary["target"], "metal")
            self.assertEqual(summary["artifactCount"], 3)
            self.assertEqual(
                set(summary),
                {
                    "artifactCount",
                    "artifacts",
                    "debugMetadata",
                    "diagnosticCount",
                    "entryPoints",
                    "graphicsAbi",
                    "module",
                    "nativeBinaryStatus",
                    "packageArtifactRequirements",
                    "packageMode",
                    "packageFormat",
                    "root",
                    "schemaVersion",
                    "target",
                    "targetContract",
                    "targetLegalizationEvidence",
                    "targetLegalizationToolRequirements",
                    "workgroupSizes",
                },
            )
            self.assertEqual(
                summary["packageArtifactRequirements"]["requirementsSource"],
                "legacy-v0-target-contract",
            )
            self.assertEqual(
                set(summary["artifacts"][0]),
                {"absolutePath", "exists", "name", "path", "size"},
            )

    @contextmanager
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

        with mock.patch.object(Path, "read_text", guarded_read_text):
            with mock.patch.object(Path, "read_bytes", guarded_read_bytes):
                yield

    @contextmanager
    def _guard_zip_crossgl_member_reads(self):
        original_open = zipfile.ZipFile.open
        original_read = zipfile.ZipFile.read

        def member_name(name: object) -> str:
            if isinstance(name, zipfile.ZipInfo):
                return name.filename
            return str(name)

        def guarded_open(
            archive: zipfile.ZipFile,
            name: object,
            *args: object,
            **kwargs: object,
        ):
            if member_name(name).endswith(".cgl"):
                raise AssertionError(f"runtime parsed source archive member: {name}")
            return original_open(archive, name, *args, **kwargs)

        def guarded_read(
            archive: zipfile.ZipFile,
            name: object,
            *args: object,
            **kwargs: object,
        ) -> bytes:
            if member_name(name).endswith(".cgl"):
                raise AssertionError(f"runtime parsed source archive member: {name}")
            return original_read(archive, name, *args, **kwargs)

        with mock.patch.object(zipfile.ZipFile, "open", guarded_open):
            with mock.patch.object(zipfile.ZipFile, "read", guarded_read):
                yield

    @staticmethod
    def _valid_metal_package_artifact_requirements() -> dict[str, object]:
        return {
            "target": "metal",
            "packageMode": "native",
            "requiredPathArtifacts": [
                "backendSource",
                "intermediate",
                "nativeBinary",
            ],
            "requiresNativeBinaryStatus": False,
            "allowsPlannedNativeBinary": False,
            "allowsPlannedNativeSourceEvidence": False,
        }

    def test_cli_outputs_compatibility_report(self) -> None:
        with tempfile.TemporaryDirectory(suffix=".cglb") as temp_dir:
            package_dir = Path(temp_dir)
            self._write_valid_package(package_dir)

            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "runtime.package_reader",
                    str(package_dir),
                    "--compatibility-report",
                    "--loader-target",
                    "metal",
                ],
                cwd=REPO_ROOT,
                check=False,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            summary = json.loads(result.stdout)
            self.assertTrue(summary["compatible"])
            self.assertEqual(summary["loaderTarget"], "metal")
            self.assertEqual(summary["reflection"]["entryPointCount"], 1)
            self.assertEqual(summary["diagnosticsMetadata"]["diagnosticCount"], 1)

    def test_read_package_accepts_target_explanation_debug_sidecar(self) -> None:
        with tempfile.TemporaryDirectory(suffix=".cglb") as temp_dir:
            package_dir = Path(temp_dir)
            self._write_valid_package(package_dir, emit_debug_metadata=True)
            manifest_path = package_dir / "manifest.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["artifacts"]["targetExplanation"] = "ir/target-explanation.json"
            self._write_json(manifest_path, manifest)
            self._write_json(
                package_dir / "ir" / "target-explanation.json",
                {
                    "schemaVersion": 1,
                    "module": "RuntimeReaderFixture",
                    "defaultTarget": "metal",
                    "buildableTargetCount": 1,
                    "recommendedTarget": "metal",
                    "recommendedPackageMode": "native",
                    "targets": [],
                },
            )

            package = read_package(package_dir)
            artifact = package.require_existing_artifact("targetExplanation")
            summary = package.to_summary()

            self.assertEqual(artifact.package_path, "ir/target-explanation.json")
            self.assertEqual(
                json.loads(artifact.read_text())["module"],
                "RuntimeReaderFixture",
            )
            self.assertIn(
                "targetExplanation",
                [record["name"] for record in summary["artifacts"]],
            )

    def _write_valid_package(
        self,
        package_dir: Path,
        *,
        target: str = "metal",
        emit_debug_metadata: bool = False,
        native_status: str | None = None,
        package_artifact_requirements: dict[str, object] | None = None,
    ) -> None:
        backend_dir = package_dir / "backend" / target
        backend_dir.mkdir(parents=True)
        source_extension = {
            "directx": "hlsl",
            "metal": "metal",
            "opengl": "glsl",
        }.get(target, "src")
        binary_extension = {
            "directx": "dxil",
            "metal": "metallib",
            "opengl": "glsl",
        }.get(target, "bin")
        source_label = "Metal" if target == "metal" else target
        (backend_dir / f"RuntimeReaderFixture.{source_extension}").write_bytes(
            f"// generated {source_label} source\n".encode("utf-8")
        )

        artifacts = {
            "backendSource": (
                f"backend/{target}/RuntimeReaderFixture.{source_extension}"
            )
        }
        if target == "metal":
            (backend_dir / "RuntimeReaderFixture.air").write_bytes(b"air")
            artifacts["intermediate"] = "backend/metal/RuntimeReaderFixture.air"
        artifacts["nativeBinary"] = (
            f"backend/{target}/RuntimeReaderFixture.{binary_extension}"
        )
        (backend_dir / f"RuntimeReaderFixture.{binary_extension}").write_bytes(
            binary_extension.encode("utf-8")
        )
        if target in {"directx", "opengl"} and native_status is None:
            native_status = "planned"
        if native_status is not None:
            artifacts["nativeBinaryStatus"] = native_status
        if emit_debug_metadata:
            (package_dir / "ir").mkdir()
            artifacts["debugMetadata"] = "ir/debug-metadata.json"
            self._write_debug_metadata(package_dir / "ir" / "debug-metadata.json")
        manifest: dict[str, object] = {
            "schemaVersion": 1,
            "compiler": {
                "name": "CrossGL-Compiler",
                "version": "test",
                "llvmVersion": "not-found",
            },
            "module": "RuntimeReaderFixture",
            "target": target,
            "sourceHash": {
                "algorithm": "sha256",
                "value": "0" * 64,
            },
            "artifacts": artifacts,
        }
        if package_artifact_requirements is not None:
            manifest["packageArtifactRequirements"] = package_artifact_requirements
        self._write_json(package_dir / "manifest.json", manifest)
        self._write_json(
            package_dir / "reflection.json",
            {
                "schemaVersion": 1,
                "module": "RuntimeReaderFixture",
                "target": target,
                "nativeBinary": (
                    f"backend/{target}/RuntimeReaderFixture.{binary_extension}"
                ),
                "entryPoints": [
                    {
                        "stage": "compute",
                        "sourceName": "main",
                        "backendName": "runtime_reader_main",
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
                        "entryPoint": "runtime_reader_main",
                        "name": "OutputBuffer",
                        "kind": "storageBuffer",
                        "sourceType": "float4",
                        "addressSpace": "storage",
                        "abi": self._target_resource_binding_abi(target),
                        "bindingClass": "uav",
                        "descriptorType": "UAV",
                        "hlslType": "RWStructuredBuffer<float4>",
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
                "diagnostics": [
                    {
                        "severity": "note",
                        "code": "package.test",
                        "message": "fixture diagnostic",
                    }
                ],
            },
        )

    def _write_native_artifact_descriptor(
        self,
        package_dir: Path,
        *,
        mutate: object | None = None,
    ) -> dict[str, object]:
        manifest_path = package_dir / "manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        target = manifest["target"]
        artifacts = manifest["artifacts"]
        descriptor_path = "metadata/native-artifact.json"
        source_artifact_name = (
            "backendAssembly" if target == "vulkan" else "backendSource"
        )
        source_path = artifacts[source_artifact_name]
        native_status = artifacts.get("nativeBinaryStatus")
        binary_kind = {
            "directx": "directx.dxil",
            "metal": "metal.metallib",
            "opengl": "opengl.source",
            "vulkan": "vulkan.spirv-module",
        }[target]
        descriptor: dict[str, object] = {
            "schemaVersion": 1,
            "kind": "crossgl.nativeArtifact",
            "contractVersion": "native-artifact-v0",
            "target": target,
            "binaryKind": binary_kind,
            "sourcePath": source_path,
            "sourceHash": {
                "algorithm": "sha256",
                "value": self._sha256_file(package_dir / source_path),
            },
            "toolchainProvenance": {
                "producer": "runtime package reader fixture",
                "tools": [
                    {
                        "name": "CrossGL fixture compiler",
                        "role": "compiler",
                        "version": "test",
                        "executable": "cglc",
                    }
                ],
                "invocation": {
                    "commandLineSha256": "1" * 64,
                    "environmentSha256": "2" * 64,
                },
            },
            "optimizationLevel": "O0",
            "optimizationEvidence": {
                "requestedLevel": "O0",
                "effectiveLevel": "O0",
                "policy": "metadata-only",
                "status": "metadata-only",
                "evidenceSource": {"kind": "descriptor"},
            },
            "validationStatus": "unavailable",
            "validationDiagnostics": [],
        }
        if native_status is not None:
            descriptor["nativeBinaryStatus"] = native_status
        if native_status != "planned":
            native_binary_path = artifacts["nativeBinary"]
            native_binary_file = package_dir / native_binary_path
            descriptor["artifactPath"] = native_binary_path
            descriptor["artifactHash"] = {
                "algorithm": "sha256",
                "value": self._sha256_file(native_binary_file),
            }
            descriptor["sizeBytes"] = native_binary_file.stat().st_size
        if mutate is not None:
            mutate(descriptor)
        artifacts["nativeArtifactDescriptor"] = descriptor_path
        (package_dir / "metadata").mkdir(exist_ok=True)
        self._write_json(package_dir / descriptor_path, descriptor)
        self._write_json(manifest_path, manifest)
        return descriptor

    @staticmethod
    def _target_resource_binding_abi(target: str) -> dict[str, object]:
        if target == "directx":
            return {"space": 0, "register": "u0"}
        if target == "metal":
            return {"buffer": 0}
        if target == "opengl":
            return {"program": 0, "binding": 0}
        return {"set": 0, "binding": 0}

    @staticmethod
    def _sha256_file(path: Path) -> str:
        return hashlib.sha256(path.read_bytes()).hexdigest()

    def _make_source_free_native_package(self, package_dir: Path) -> None:
        manifest_path = package_dir / "manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        target = manifest["target"]
        artifacts = manifest["artifacts"]
        for artifact_name in ("backendSource", "backendAssembly", "intermediate"):
            artifact_path = artifacts.pop(artifact_name, None)
            if not isinstance(artifact_path, str):
                continue
            resolved_artifact = package_dir / artifact_path
            if resolved_artifact.exists():
                resolved_artifact.unlink()
        artifacts.pop("nativeBinaryStatus", None)
        manifest["packageArtifactRequirements"] = {
            "target": target,
            "packageMode": "native",
            "requiredPathArtifacts": ["nativeBinary"],
            "requiresNativeBinaryStatus": False,
            "allowsPlannedNativeBinary": False,
            "allowsPlannedNativeSourceEvidence": False,
        }
        self._write_json(manifest_path, manifest)

    def _write_debug_metadata(self, path: Path) -> None:
        self._write_json(
            path,
            {
                "schemaVersion": 11,
                "targetDecision": {
                    "requestedTarget": "metal",
                    "selectedTarget": "metal",
                    "selectedTargetPackageMode": "native",
                },
                "hirSourceLocations": {
                    "expressionCount": 1,
                    "expressionWithLocationCount": 1,
                    "typeCount": 2,
                    "typeWithLocationCount": 2,
                    "statementCount": 3,
                    "statementWithLocationCount": 3,
                    "expressions": [],
                    "types": [],
                    "statements": [],
                },
                "manualTextureCompareKernels": [],
            },
        )

    def _write_oversized_json_object(self, path: Path) -> int:
        self._write_json(
            path,
            {
                "schemaVersion": 1,
                "padding": (
                    "x" * (package_reader_module.RUNTIME_METADATA_JSON_BYTE_LIMIT + 1)
                ),
            },
        )
        return path.stat().st_size

    def _write_zip_package(
        self,
        package_dir: Path,
        zip_path: Path,
        *,
        prefix: str | None = None,
    ) -> None:
        with zipfile.ZipFile(zip_path, "w") as archive:
            for path in sorted(package_dir.rglob("*")):
                if not path.is_file():
                    continue
                archive_name = path.relative_to(package_dir).as_posix()
                if prefix is not None:
                    archive_name = f"{prefix}/{archive_name}"
                archive.write(path, archive_name)

    def _write_json(self, path: Path, document: object) -> None:
        path.write_text(
            json.dumps(document, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )


if __name__ == "__main__":
    unittest.main()
