#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock
import warnings
import zipfile


REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURE_ROOT = REPO_ROOT / "runtime" / "examples" / "fixtures"
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "tools"))


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


from json_schema_semantics import validate_semantics  # noqa: E402
from runtime.loader import (  # noqa: E402
    read_loader_plan,
    read_runtime_loader_plan_contract,
)
from runtime.opengl_loader import plan_opengl_loader  # noqa: E402
from runtime.package_reader import (  # noqa: E402
    PackageReadError,
    read_compatibility_report,
    select_runtime_artifact,
)
import runtime.package_target_contracts as runtime_target_contracts  # noqa: E402
from validate_json_schema import load_json as load_schema_json  # noqa: E402
from validate_json_schema import validate as validate_json_schema  # noqa: E402


RUNTIME_LOADER_PLAN_SCHEMA = load_schema_json(
    REPO_ROOT / "docs" / "schemas" / "runtime-loader-plan-v1.schema.json"
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


class RuntimeLoaderFacadeTests(unittest.TestCase):
    def assertRuntimeLoaderPlanContractValid(self, contract: dict[str, object]) -> None:
        validate_json_schema(
            contract,
            RUNTIME_LOADER_PLAN_SCHEMA,
            RUNTIME_LOADER_PLAN_SCHEMA,
        )
        self.assertEqual(
            validate_semantics(contract, RUNTIME_LOADER_PLAN_SCHEMA),
            [],
        )

    def assertLegacyRequirementsFallbackOnly(
        self, diagnostics: list[dict[str, object]]
    ) -> None:
        self.assertEqual(diagnostics, [LEGACY_REQUIREMENTS_FALLBACK_DIAGNOSTIC])

    def assertCompatibilityCodesWithLegacyFallback(
        self,
        summary: dict[str, object],
        expected_codes: list[str],
    ) -> None:
        compatibility = summary["loaderDiagnostics"]["compatibility"]
        self.assertIn(LEGACY_REQUIREMENTS_FALLBACK_CODE, compatibility["codes"])
        self.assertEqual(
            [
                code
                for code in compatibility["codes"]
                if code != LEGACY_REQUIREMENTS_FALLBACK_CODE
            ],
            expected_codes,
        )
        self.assertEqual(
            [
                diagnostic
                for diagnostic in compatibility["diagnostics"]
                if diagnostic["code"] == LEGACY_REQUIREMENTS_FALLBACK_CODE
            ],
            [LEGACY_REQUIREMENTS_FALLBACK_DIAGNOSTIC],
        )

    def assertRuntimeArtifactHandoff(
        self,
        handoff: object,
        *,
        expected_bytes: bytes,
        expected_metadata: dict[str, object],
        expected_package_format: str,
        expected_artifact_name: str,
        expected_package_path: str,
        expected_absolute_path: str,
        expected_selected_package_mode: str,
        expected_size: int,
    ) -> None:
        self.assertEqual(handoff.bytes, expected_bytes)
        self.assertEqual(handoff.metadata, expected_metadata)
        self.assertEqual(handoff.package_format, expected_package_format)
        self.assertEqual(handoff.artifact_name, expected_artifact_name)
        self.assertEqual(handoff.package_path, expected_package_path)
        self.assertEqual(handoff.absolute_path, expected_absolute_path)
        self.assertEqual(
            handoff.selected_package_mode,
            expected_selected_package_mode,
        )
        self.assertEqual(handoff.size, expected_size)

    def test_directx_source_package_plan_selects_contract_and_reflection(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory(suffix=".cglb") as temp_dir:
            package_dir = Path(temp_dir)
            self._write_valid_package(package_dir, target="directx")
            (package_dir / "source").mkdir()
            (package_dir / "source" / "invalid.cgl").write_text(
                "runtime loader must not parse package source\n",
                encoding="utf-8",
            )

            plan = read_loader_plan(package_dir, "directx")
            summary = plan.to_summary()
            contract = plan.to_runtime_loader_plan_contract()

            self.assertTrue(plan.loadable, summary["diagnostics"])
            self.assertRuntimeLoaderPlanContractValid(contract)
            self.assertEqual(contract["kind"], "crossgl-runtime-loader-plan")
            self.assertEqual(contract["success"], True)
            self.assertEqual(contract["packageFormat"], "directory")
            self.assertEqual(contract["packageTarget"], "directx")
            self.assertEqual(contract["requestedLoaderTarget"], "directx")
            self.assertEqual(contract["selectedPackageMode"], "source-package")
            self.assertEqual(contract["selectedArtifact"]["name"], "backendSource")
            self.assertFalse(contract["sourceParsingRequired"])
            self.assertEqual(contract["packageVersion"], 1)
            self.assertEqual(contract["selectedTarget"], "directx")
            self.assertTrue(contract["loadable"])
            self.assertEqual(
                contract["requiredArtifacts"],
                ["backendSource", "nativeBinary"],
            )
            self.assertEqual(
                contract["requiredArtifactPaths"],
                {
                    "backendSource": "backend/directx/RuntimeLoaderFixture.hlsl",
                    "nativeBinary": "backend/directx/RuntimeLoaderFixture.dxil",
                },
            )
            self.assertEqual(
                contract["runtimeArtifactPath"],
                "backend/directx/RuntimeLoaderFixture.hlsl",
            )
            self.assertEqual(contract["reflectionInputs"]["schemaVersion"], 1)
            self.assertEqual(contract["reflectionInputs"]["selectedTarget"], "directx")
            self.assertEqual(contract["reflectionInputs"]["resourceCount"], 1)
            self.assertEqual(
                contract["reflectionInputs"]["targetResourceBindingCount"],
                1,
            )
            self.assertEqual(
                contract["reflectionInputs"]["targetResourceBindings"][0]["target"],
                "directx",
            )
            self.assertEqual(
                contract["reflectionInputs"]["targetResourceBindings"][0][
                    "descriptorType"
                ],
                "UAV",
            )
            binding_metadata = contract["targetResourceBindingMetadata"]
            self.assertEqual(binding_metadata["schemaVersion"], 1)
            self.assertEqual(binding_metadata["selectedTarget"], "directx")
            self.assertEqual(binding_metadata["loaderTarget"], "directx")
            self.assertEqual(binding_metadata["packageTarget"], "directx")
            self.assertEqual(binding_metadata["bindingCount"], 1)
            self.assertEqual(binding_metadata["skippedBindingCount"], 0)
            self.assertEqual(
                binding_metadata["bindings"][0]["identity"],
                {
                    "target": "directx",
                    "stage": "compute",
                    "entryPoint": "runtime_loader_main",
                    "name": "OutputBuffer",
                    "kind": "storageBuffer",
                },
            )
            self.assertEqual(binding_metadata["bindings"][0]["descriptorType"], "UAV")
            host_loader_integration = contract["hostLoaderIntegration"]
            self.assertEqual(
                host_loader_integration["kind"],
                "crossgl-runtime-host-loader-integration",
            )
            self.assertEqual(host_loader_integration["status"], "ready")
            self.assertEqual(
                host_loader_integration["scope"],
                "host-loader-scaffold-generation",
            )
            self.assertEqual(
                host_loader_integration["summary"],
                {
                    "targetCount": 1,
                    "loadUnitCount": 1,
                    "readyLoadUnitCount": 1,
                    "blockedLoadUnitCount": 0,
                    "entryPointCount": 1,
                    "resourceBindingCount": 1,
                    "workgroupSizeCount": 0,
                    "functionConstantCount": 0,
                    "specializationConstantCount": 0,
                },
            )
            load_unit = host_loader_integration["loadUnits"][0]
            self.assertEqual(load_unit["id"], "runtime-loader.directx.backendSource")
            self.assertEqual(load_unit["target"], "directx")
            self.assertEqual(
                load_unit["packagePath"], contract["selectedArtifact"]["path"]
            )
            self.assertEqual(load_unit["artifact"], contract["selectedArtifact"])
            self.assertEqual(load_unit["artifactFormat"], "backend-source")
            self.assertEqual(load_unit["adapterKind"], "backend-source-loader")
            self.assertIsNone(load_unit["sourceRemap"])
            self.assertIsNone(load_unit["backendSourceMap"])
            self.assertEqual(load_unit["requiredTools"], [])
            self.assertEqual(
                load_unit["hostResponsibilities"],
                [
                    "load-package-artifact",
                    "bind-reflected-entry-points",
                    "bind-reflected-resources",
                ],
            )
            self.assertEqual(load_unit["hostInterface"]["status"], "ready")
            self.assertEqual(load_unit["validation"]["loadReady"], True)
            self.assertEqual(
                [step["kind"] for step in load_unit["loadSteps"]],
                ["load-package-artifact", "bind-host-interface"],
            )
            self.assertEqual(
                load_unit["loadSteps"][0]["message"],
                "Load the selected runtime package artifact.",
            )
            self.assertEqual(load_unit["loadSteps"][0]["target"], "directx")
            self.assertEqual(
                load_unit["loadSteps"][0]["packagePath"],
                "backend/directx/RuntimeLoaderFixture.hlsl",
            )
            self.assertEqual(
                load_unit["loadSteps"][0]["hostInterfaceStatus"],
                "ready",
            )
            self.assertEqual(
                load_unit["loadSteps"][0]["metadata"],
                {
                    "source": {
                        "field": "selectedArtifact.path",
                        "path": "backend/directx/RuntimeLoaderFixture.hlsl",
                    },
                    "artifact": {
                        "name": "backendSource",
                        "packageMode": "source-package",
                        "artifactFormat": "backend-source",
                    },
                },
            )
            self.assertEqual(
                load_unit["loadSteps"][1]["message"],
                "Bind reflected host interface metadata.",
            )
            self.assertEqual(load_unit["loadSteps"][1]["target"], "directx")
            self.assertEqual(
                load_unit["loadSteps"][1]["packagePath"],
                "backend/directx/RuntimeLoaderFixture.hlsl",
            )
            self.assertEqual(
                load_unit["loadSteps"][1]["hostInterfaceStatus"],
                "ready",
            )
            self.assertEqual(load_unit["blockers"], [])
            self.assertEqual(
                contract["runtimeArtifactSelection"],
                {
                    "schemaVersion": 1,
                    "requestedTarget": "directx",
                    "requestedPackageMode": "auto",
                    "packageTarget": "directx",
                    "selectedTarget": "directx",
                    "selected": True,
                    "selectedPackageMode": "source-package",
                    "sourceParsingRequired": False,
                    "compilerInvocationRequired": False,
                    "deviceExecutionRequired": False,
                    "sourceInputs": [],
                    "artifact": contract["selectedArtifact"],
                },
            )
            self.assertEqual(
                read_runtime_loader_plan_contract(package_dir, "directx"),
                contract,
            )
            self.assertEqual(
                contract["packageArtifactRequirementsSource"],
                "generated-package-target-contract",
            )
            self.assertEqual(
                contract["targetLegalizationEvidenceSummary"],
                {
                    "toolRequirementsPresent": False,
                    "target": None,
                    "packageMode": None,
                    "requiredToolCount": 0,
                    "missingToolCount": 0,
                    "requiredToolIds": [],
                    "missingToolIds": [],
                    "toolRequirementEvidenceIds": [],
                },
            )
            self.assertFalse(plan.source_parsing_required)
            self.assertEqual(plan.module, "RuntimeLoaderFixture")
            self.assertEqual(plan.package_target, "directx")
            self.assertEqual(
                plan.required_artifacts,
                ("backendSource", "nativeBinary"),
            )
            self.assertEqual(
                [artifact.name for artifact in plan.selected_artifacts],
                ["backendSource", "nativeBinary"],
            )
            backend_source = plan.require_artifact("backendSource")
            native_binary = plan.require_artifact("nativeBinary")
            self.assertEqual(
                backend_source.package_path,
                "backend/directx/RuntimeLoaderFixture.hlsl",
            )
            self.assertEqual(
                native_binary.package_path,
                "backend/directx/RuntimeLoaderFixture.dxil",
            )
            self.assertIn("generated directx source", backend_source.read_text())
            self.assertEqual(plan.compatibility_report.native_binary_status, "planned")
            self.assertEqual(plan.runtime_artifact, backend_source)
            self.assertEqual(
                summary["runtimeArtifactSelection"]["artifact"]["name"],
                "backendSource",
            )
            self.assertEqual(
                summary["runtimeArtifactSelection"]["selectedPackageMode"],
                "source-package",
            )
            self.assertTrue(native_binary.exists)
            self.assertIsNotNone(native_binary.size)

            entry_point = plan.require_entry_point("compute", "main")
            self.assertEqual(entry_point["backendName"], "runtime_loader_main")
            resource = plan.require_resource_binding("compute", "OutputBuffer")
            self.assertEqual(resource["binding"], 0)
            target_resource = plan.require_target_resource_binding(
                "compute",
                "OutputBuffer",
                entry_point="runtime_loader_main",
            )
            self.assertEqual(target_resource["hlslType"], "RWStructuredBuffer<float4>")
            self.assertEqual(target_resource["descriptorType"], "UAV")
            metadata_record = plan.require_target_resource_binding_metadata(
                "compute",
                "OutputBuffer",
                entry_point="runtime_loader_main",
            )
            self.assertEqual(metadata_record, binding_metadata["bindings"][0])
            self.assertEqual(
                plan.target_resource_binding_metadata_records(),
                (metadata_record,),
            )
            self.assertIsNone(
                plan.target_resource_binding_metadata("compute", "MissingBuffer")
            )
            with self.assertRaisesRegex(
                PackageReadError,
                "target resource binding metadata",
            ):
                plan.require_target_resource_binding_metadata(
                    "compute",
                    "MissingBuffer",
                )
            self.assertEqual(
                summary["compatibilityReport"]["sourceParsingRequired"],
                False,
            )

    def test_source_remap_artifact_is_exposed_as_host_loader_load_step(self) -> None:
        with tempfile.TemporaryDirectory(suffix=".cglb") as temp_dir:
            package_dir = Path(temp_dir)
            self._write_valid_package(package_dir, target="directx")
            source_remap_path = "ir/source-remap-provenance.json"
            manifest_path = package_dir / "manifest.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["artifacts"]["sourceRemap"] = source_remap_path
            self._write_json(manifest_path, manifest)
            (package_dir / "ir").mkdir()
            self._write_json(
                package_dir / source_remap_path,
                {
                    "schemaVersion": 1,
                    "kind": "crossgl.sourceRemapProvenance",
                    "contractVersion": "source-remap-provenance-v1",
                    "target": "directx",
                    "generatedFile": "generated/from-translator.cgl",
                    "mappingGranularity": "source-span",
                    "mappingCount": 1,
                    "sourceRemap": {
                        "path": "source/original.crossgl",
                        "sha256": {
                            "algorithm": "sha256",
                            "value": "0" * 64,
                        },
                        "sizeBytes": 0,
                    },
                },
            )

            contract = read_runtime_loader_plan_contract(package_dir, "directx")

            self.assertRuntimeLoaderPlanContractValid(contract)
            load_unit = contract["hostLoaderIntegration"]["loadUnits"][0]
            expected_source_remap_provenance = {
                "available": True,
                "health": "ok",
                "schemaVersion": 1,
                "kind": "crossgl.sourceRemapProvenance",
                "contractVersion": "source-remap-provenance-v1",
                "target": "directx",
                "generatedFile": "generated/from-translator.cgl",
                "mappingGranularity": "source-span",
                "mappingCount": 1,
                "sourcePath": "source/original.crossgl",
                "sourceSha256": "0" * 64,
                "sourceSizeBytes": 0,
                "sourceRemapTarget": None,
                "sourceRemapMappingGranularity": None,
                "sourceRemapSourceBackend": None,
                "sourceRemapVariant": None,
            }
            self.assertEqual(
                load_unit["sourceRemap"],
                {
                    "source": "manifest.artifacts.sourceRemap",
                    "packagePath": source_remap_path,
                    "exists": True,
                    "provenance": expected_source_remap_provenance,
                },
            )
            self.assertEqual(
                load_unit["hostResponsibilities"],
                [
                    "load-package-artifact",
                    "load-source-remap",
                    "bind-reflected-entry-points",
                    "bind-reflected-resources",
                ],
            )
            self.assertEqual(
                [step["kind"] for step in load_unit["loadSteps"]],
                [
                    "load-package-artifact",
                    "load-source-remap",
                    "bind-host-interface",
                ],
            )
            self.assertEqual(
                load_unit["loadSteps"][1],
                {
                    "kind": "load-source-remap",
                    "message": "Load source remap provenance for diagnostics.",
                    "target": "directx",
                    "packagePath": source_remap_path,
                    "hostInterfaceStatus": "ready",
                    "command": None,
                    "tools": [],
                    "metadata": {
                        "source": {
                            "field": "manifest.artifacts.sourceRemap",
                            "path": source_remap_path,
                        },
                        "provenance": {
                            "source": "loadUnit.sourceRemap.provenance",
                            "available": True,
                            "health": "ok",
                        },
                    },
                },
            )

    def test_crosstl_adapter_load_units_are_selected_for_runtime_artifact(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory(suffix=".cglb") as temp_dir:
            package_dir = Path(temp_dir)
            self._write_valid_package(package_dir, target="directx")
            package_path = "backend/directx/RuntimeLoaderFixture.hlsl"
            self._write_crosstl_runtime_adapter_package(
                package_dir,
                target="directx",
                artifact_format="HLSL source",
                package_path=package_path,
            )

            plan = read_loader_plan(package_dir, "directx")
            contract = plan.to_runtime_loader_plan_contract()
            load_units = plan.crosstl_adapter_load_unit_records()

            self.assertTrue(plan.loadable, plan.to_summary()["diagnostics"])
            self.assertRuntimeLoaderPlanContractValid(contract)
            self.assertEqual(len(load_units), 1)
            load_unit = load_units[0]
            self.assertEqual(
                load_unit.id,
                "runtime-loader.directx.DirectxRuntimeLoaderFixture",
            )
            self.assertEqual(load_unit.target, "directx")
            self.assertEqual(load_unit.artifact_format, "backend-source")
            self.assertEqual(load_unit.package_path, plan.runtime_artifact_path)
            self.assertEqual(load_unit.source_path, "source/RuntimeLoaderFixture.cgl")
            self.assertEqual(load_unit.source_backend, "crossgl")
            self.assertEqual(load_unit.stage, "compute")
            self.assertEqual(load_unit.variant, "debug")
            self.assertEqual(
                load_unit.required_tools,
                ("directx.toolchain.compiler",),
            )
            self.assertEqual(load_unit.validation["loadReady"], True)
            self.assertEqual(
                [step["kind"] for step in load_unit.load_steps],
                [
                    "load-package-artifact",
                    "load-source-remap",
                    "bind-host-interface",
                    "validate-target-toolchain",
                ],
            )
            self.assertEqual(
                plan.crosstl_adapter_load_unit(package_path),
                load_unit,
            )
            self.assertEqual(
                plan.require_crosstl_adapter_load_unit(package_path),
                load_unit,
            )
            self.assertEqual(
                plan.crosstl_adapter_load_unit_records(target="metal"),
                (),
            )
            with self.assertRaisesRegex(
                PackageReadError,
                "missing CrossTL runtime adapter load unit",
            ):
                plan.require_crosstl_adapter_load_unit(
                    "backend/directx/Missing.hlsl",
                )
            self.assertEqual(
                contract["hostLoaderIntegration"]["loadUnits"][0]["id"],
                "runtime-loader.directx.backendSource",
            )

    def test_crosstl_adapter_load_units_filter_to_selected_artifact_path(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory(suffix=".cglb") as temp_dir:
            package_dir = Path(temp_dir)
            self._write_valid_package(package_dir, target="directx")
            self._write_crosstl_runtime_adapter_package(
                package_dir,
                target="directx",
                artifact_format="HLSL source",
                package_path="backend/directx/UnselectedFixture.hlsl",
            )

            plan = read_loader_plan(package_dir, "directx")

            self.assertTrue(plan.loadable, plan.to_summary()["diagnostics"])
            self.assertEqual(
                plan.runtime_artifact_path,
                "backend/directx/RuntimeLoaderFixture.hlsl",
            )
            self.assertEqual(plan.crosstl_adapter_load_unit_records(), ())
            self.assertRuntimeLoaderPlanContractValid(
                plan.to_runtime_loader_plan_contract()
            )

    def test_invalid_crosstl_adapter_manifest_does_not_block_runtime_plan(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory(suffix=".cglb") as temp_dir:
            package_dir = Path(temp_dir)
            self._write_valid_package(package_dir, target="directx")
            (package_dir / "runtime-adapters.json").write_text(
                "{not json",
                encoding="utf-8",
            )

            plan = read_loader_plan(package_dir, "directx")

            self.assertTrue(plan.loadable, plan.to_summary()["diagnostics"])
            self.assertEqual(plan.crosstl_adapter_load_unit_records(), ())
            self.assertRuntimeLoaderPlanContractValid(
                plan.to_runtime_loader_plan_contract()
            )

    def test_zip_loader_plan_discovers_crosstl_adapter_sidecar(self) -> None:
        with tempfile.TemporaryDirectory(suffix=".cglb") as temp_dir:
            package_dir = Path(temp_dir)
            self._write_valid_package(package_dir, target="directx")
            package_path = "backend/directx/RuntimeLoaderFixture.hlsl"
            self._write_crosstl_runtime_adapter_package(
                package_dir,
                target="directx",
                artifact_format="HLSL source",
                package_path=package_path,
            )
            zip_path = package_dir.with_suffix(".zip")
            self._write_zip_package(package_dir, zip_path)

            with self._guard_crossgl_source_archive_reads():
                plan = read_loader_plan(zip_path, "directx")
            contract = plan.to_runtime_loader_plan_contract()
            load_units = plan.crosstl_adapter_load_unit_records()

            self.assertTrue(plan.loadable, plan.to_summary()["diagnostics"])
            self.assertRuntimeLoaderPlanContractValid(contract)
            self.assertEqual(len(load_units), 1)
            load_unit = load_units[0]
            self.assertEqual(
                load_unit.id,
                "runtime-loader.directx.DirectxRuntimeLoaderFixture",
            )
            self.assertEqual(load_unit.target, "directx")
            self.assertEqual(load_unit.artifact_format, "backend-source")
            self.assertEqual(load_unit.package_path, package_path)
            self.assertEqual(load_unit.source_path, "source/RuntimeLoaderFixture.cgl")
            self.assertEqual(
                load_unit.required_tools,
                ("directx.toolchain.compiler",),
            )
            self.assertEqual(plan.crosstl_adapter_load_unit(package_path), load_unit)
            self.assertEqual(
                contract["hostLoaderIntegration"]["loadUnits"][0]["id"],
                "runtime-loader.directx.backendSource",
            )

    def test_prefixed_zip_loader_plan_discovers_crosstl_adapter_sidecar(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory(suffix=".cglb") as temp_dir:
            package_dir = Path(temp_dir)
            self._write_valid_package(package_dir, target="directx")
            package_path = "backend/directx/RuntimeLoaderFixture.hlsl"
            self._write_crosstl_runtime_adapter_package(
                package_dir,
                target="directx",
                artifact_format="HLSL source",
                package_path=package_path,
            )
            zip_path = package_dir.with_suffix(".zip")
            self._write_zip_package(package_dir, zip_path, prefix=zip_path.name)

            with self._guard_crossgl_source_archive_reads():
                plan = read_loader_plan(zip_path, "directx")
            load_units = plan.crosstl_adapter_load_unit_records()

            self.assertTrue(plan.loadable, plan.to_summary()["diagnostics"])
            self.assertEqual(len(load_units), 1)
            self.assertEqual(load_units[0].package_path, package_path)
            self.assertRuntimeLoaderPlanContractValid(
                plan.to_runtime_loader_plan_contract()
            )

    def test_invalid_zip_crosstl_adapter_manifest_does_not_block_runtime_plan(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory(suffix=".cglb") as temp_dir:
            package_dir = Path(temp_dir)
            self._write_valid_package(package_dir, target="directx")
            (package_dir / "runtime-adapters.json").write_text(
                "{not json",
                encoding="utf-8",
            )
            zip_path = package_dir.with_suffix(".zip")
            self._write_zip_package(package_dir, zip_path)

            with self._guard_crossgl_source_archive_reads():
                plan = read_loader_plan(zip_path, "directx")

            self.assertTrue(plan.loadable, plan.to_summary()["diagnostics"])
            self.assertEqual(plan.crosstl_adapter_load_unit_records(), ())
            self.assertRuntimeLoaderPlanContractValid(
                plan.to_runtime_loader_plan_contract()
            )

    def test_backend_source_map_artifact_is_exposed_as_host_loader_load_step(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory(suffix=".cglb") as temp_dir:
            package_dir = Path(temp_dir)
            self._write_valid_package(package_dir, target="directx")
            backend_source_map_path = (
                "backend/directx/RuntimeLoaderFixture.backend-source-map.json"
            )
            manifest_path = package_dir / "manifest.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["artifacts"]["backendSourceMap"] = backend_source_map_path
            self._write_json(manifest_path, manifest)
            self._write_json(
                package_dir / backend_source_map_path,
                {
                    "schemaVersion": 1,
                    "kind": "crossgl.backendSourceMap",
                    "target": "directx",
                    "module": "RuntimeLoaderFixture",
                    "mappingGranularity": "statement",
                    "sourceBackend": "crossgl-hir",
                    "targetBackend": "hlsl",
                    "backend": {
                        "language": "hlsl",
                        "lineCount": 1,
                    },
                    "mappingCount": 0,
                    "mappings": [],
                },
            )

            contract = read_runtime_loader_plan_contract(package_dir, "directx")

            self.assertRuntimeLoaderPlanContractValid(contract)
            load_unit = contract["hostLoaderIntegration"]["loadUnits"][0]
            self.assertIsNone(load_unit["sourceRemap"])
            expected_backend_source_map_provenance = {
                "available": True,
                "health": "ok",
                "schemaVersion": 1,
                "kind": "crossgl.backendSourceMap",
                "target": "directx",
                "module": "RuntimeLoaderFixture",
                "mappingGranularity": "statement",
                "sourceBackend": "crossgl-hir",
                "targetBackend": "hlsl",
                "backendLanguage": "hlsl",
                "backendLineCount": 1,
                "mappingCount": 0,
                "mappingRecordCount": 0,
                "sourceRemapPresent": False,
                "sourceRemapPath": None,
                "sourceRemapGeneratedFile": None,
                "sourceRemapTarget": None,
                "sourceRemapMappingGranularity": None,
                "sourceRemapMappingCount": None,
                "sourceRemapSourceBackend": None,
                "sourceRemapVariant": None,
                "sourceRemapSha256": None,
                "sourceRemapSizeBytes": None,
            }
            self.assertEqual(
                load_unit["backendSourceMap"],
                {
                    "source": "manifest.artifacts.backendSourceMap",
                    "packagePath": backend_source_map_path,
                    "exists": True,
                    "provenance": expected_backend_source_map_provenance,
                },
            )
            self.assertEqual(
                load_unit["hostResponsibilities"],
                [
                    "load-package-artifact",
                    "load-backend-source-map",
                    "bind-reflected-entry-points",
                    "bind-reflected-resources",
                ],
            )
            self.assertEqual(
                [step["kind"] for step in load_unit["loadSteps"]],
                [
                    "load-package-artifact",
                    "load-backend-source-map",
                    "bind-host-interface",
                ],
            )
            self.assertEqual(
                load_unit["loadSteps"][1],
                {
                    "kind": "load-backend-source-map",
                    "message": "Load backend source map metadata for diagnostics.",
                    "target": "directx",
                    "packagePath": backend_source_map_path,
                    "hostInterfaceStatus": "ready",
                    "command": None,
                    "tools": [],
                    "metadata": {
                        "source": {
                            "field": "manifest.artifacts.backendSourceMap",
                            "path": backend_source_map_path,
                        },
                        "provenance": {
                            "source": "loadUnit.backendSourceMap.provenance",
                            "available": True,
                            "health": "ok",
                        },
                    },
                },
            )

    def test_backend_source_map_embedded_source_remap_matches_host_loader_provenance(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory(suffix=".cglb") as temp_dir:
            package_dir = Path(temp_dir)
            self._write_valid_package(package_dir, target="directx")
            source_remap_path = "ir/source-remap-provenance.json"
            backend_source_map_path = (
                "backend/directx/RuntimeLoaderFixture.backend-source-map.json"
            )
            manifest_path = package_dir / "manifest.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["artifacts"]["sourceRemap"] = source_remap_path
            manifest["artifacts"]["backendSourceMap"] = backend_source_map_path
            self._write_json(manifest_path, manifest)
            (package_dir / "ir").mkdir()
            source_hash = {
                "algorithm": "sha256",
                "value": "0" * 64,
            }
            source_remap_metadata = {
                "target": "cgl",
                "mappingGranularity": "file",
                "sourceBackend": "cgl",
                "variant": "debug",
            }
            self._write_json(
                package_dir / source_remap_path,
                {
                    "schemaVersion": 1,
                    "kind": "crossgl.sourceRemapProvenance",
                    "contractVersion": "source-remap-provenance-v1",
                    "target": "directx",
                    "generatedFile": "generated/from-translator.cgl",
                    "mappingGranularity": "source-span",
                    "mappingCount": 1,
                    "sourceRemap": {
                        "path": "source/original.crossgl",
                        "sha256": dict(source_hash),
                        "sizeBytes": 0,
                        **source_remap_metadata,
                    },
                },
            )
            self._write_json(
                package_dir / backend_source_map_path,
                {
                    "schemaVersion": 1,
                    "kind": "crossgl.backendSourceMap",
                    "target": "directx",
                    "module": "RuntimeLoaderFixture",
                    "mappingGranularity": "statement",
                    "sourceBackend": "crossgl-hir",
                    "targetBackend": "hlsl",
                    "backend": {
                        "language": "hlsl",
                        "lineCount": 1,
                    },
                    "sourceRemap": {
                        "path": source_remap_path,
                        "sha256": dict(source_hash),
                        "sizeBytes": 0,
                        "generatedFile": "generated/from-translator.cgl",
                        "mappingCount": 1,
                        **source_remap_metadata,
                    },
                    "mappingCount": 1,
                    "mappings": [
                        {
                            "index": 0,
                            "stage": "compute",
                            "entryPoint": "main",
                            "function": "main",
                            "statementKind": "assignment",
                            "backend": {
                                "startLine": 1,
                                "endLine": 1,
                            },
                            "location": {
                                "file": "generated/from-translator.cgl",
                                "line": 1,
                                "column": 1,
                                "offset": 0,
                                "length": 1,
                                "endLine": 1,
                                "endColumn": 2,
                                "endOffset": 1,
                            },
                            "originalLocation": {
                                "file": "source/original.crossgl",
                                "line": 1,
                                "column": 1,
                                "offset": 0,
                                "length": 1,
                                "endLine": 1,
                                "endColumn": 2,
                                "endOffset": 1,
                            },
                        }
                    ],
                },
            )

            contract = read_runtime_loader_plan_contract(package_dir, "directx")

            self.assertRuntimeLoaderPlanContractValid(contract)
            load_unit = contract["hostLoaderIntegration"]["loadUnits"][0]
            self.assertEqual(
                load_unit["sourceRemap"]["provenance"],
                {
                    "available": True,
                    "health": "ok",
                    "schemaVersion": 1,
                    "kind": "crossgl.sourceRemapProvenance",
                    "contractVersion": "source-remap-provenance-v1",
                    "target": "directx",
                    "generatedFile": "generated/from-translator.cgl",
                    "mappingGranularity": "source-span",
                    "mappingCount": 1,
                    "sourcePath": "source/original.crossgl",
                    "sourceSha256": "0" * 64,
                    "sourceSizeBytes": 0,
                    "sourceRemapTarget": "cgl",
                    "sourceRemapMappingGranularity": "file",
                    "sourceRemapSourceBackend": "cgl",
                    "sourceRemapVariant": "debug",
                },
            )
            self.assertEqual(
                load_unit["backendSourceMap"]["provenance"],
                {
                    "available": True,
                    "health": "ok",
                    "schemaVersion": 1,
                    "kind": "crossgl.backendSourceMap",
                    "target": "directx",
                    "module": "RuntimeLoaderFixture",
                    "mappingGranularity": "statement",
                    "sourceBackend": "crossgl-hir",
                    "targetBackend": "hlsl",
                    "backendLanguage": "hlsl",
                    "backendLineCount": 1,
                    "mappingCount": 1,
                    "mappingRecordCount": 1,
                    "sourceRemapPresent": True,
                    "sourceRemapPath": source_remap_path,
                    "sourceRemapGeneratedFile": "generated/from-translator.cgl",
                    "sourceRemapTarget": "cgl",
                    "sourceRemapMappingGranularity": "file",
                    "sourceRemapMappingCount": 1,
                    "sourceRemapSourceBackend": "cgl",
                    "sourceRemapVariant": "debug",
                    "sourceRemapSha256": "0" * 64,
                    "sourceRemapSizeBytes": 0,
                },
            )
            self.assertEqual(
                [step["kind"] for step in load_unit["loadSteps"]],
                [
                    "load-package-artifact",
                    "load-source-remap",
                    "load-backend-source-map",
                    "bind-host-interface",
                ],
            )

    def test_workgroup_size_metadata_handoff_uses_reflection_only(self) -> None:
        with tempfile.TemporaryDirectory(suffix=".cglb") as temp_dir:
            package_dir = Path(temp_dir)
            self._write_valid_package(package_dir, target="directx")
            reflection_path = package_dir / "reflection.json"
            reflection = json.loads(reflection_path.read_text(encoding="utf-8"))
            workgroup_size = {
                "stage": "compute",
                "entryPoint": "runtime_loader_main",
                "x": "16",
                "y": "4",
                "z": "1",
                "sourceX": "WORKGROUP_X",
                "sourceY": "4",
                "sourceZ": "1",
            }
            reflection["workgroupSizes"] = [workgroup_size]
            self._write_json(reflection_path, reflection)
            source_path = package_dir / "source" / "invalid.cgl"
            source_path.parent.mkdir()
            source_path.write_text(
                "loader workgroup handoff must not parse CrossGL source\n",
                encoding="utf-8",
            )

            with self._guard_crossgl_source_path_reads():
                plan = read_loader_plan(package_dir, "directx")

            summary = plan.to_summary()
            reflection_summary = summary["reflectionResources"]
            contract_reflection = summary["metadataContract"]["reflectionInputs"]

            self.assertTrue(plan.loadable, summary["diagnostics"])
            self.assertEqual(plan.workgroup_sizes, (workgroup_size,))
            self.assertEqual(plan.workgroup_size("compute", "main"), workgroup_size)
            self.assertEqual(
                plan.workgroup_size("compute", "runtime_loader_main"),
                workgroup_size,
            )
            self.assertEqual(
                plan.require_workgroup_size("compute", "main"),
                workgroup_size,
            )
            self.assertEqual(reflection_summary["workgroupSizeCount"], 1)
            self.assertTrue(reflection_summary["workgroupSizesAvailable"])
            self.assertEqual(reflection_summary["workgroupSizes"], [workgroup_size])
            self.assertEqual(contract_reflection["workgroupSizes"], [workgroup_size])
            self.assertEqual(
                summary["compatibilityReport"]["workgroupSizes"]["records"],
                [workgroup_size],
            )
            self.assertEqual(list(package_dir.rglob("*.cgl")), [source_path])

    def test_workgroup_size_metadata_handoff_falls_back_when_absent(self) -> None:
        with tempfile.TemporaryDirectory(suffix=".cglb") as temp_dir:
            package_dir = Path(temp_dir)
            self._write_valid_package(package_dir)

            plan = read_loader_plan(package_dir, "metal")
            summary = plan.to_summary()

            self.assertTrue(plan.loadable, summary["diagnostics"])
            self.assertEqual(plan.workgroup_sizes, ())
            self.assertIsNone(plan.workgroup_size("compute", "main"))
            self.assertEqual(summary["reflectionResources"]["workgroupSizeCount"], 0)
            self.assertFalse(summary["reflectionResources"]["workgroupSizesAvailable"])
            self.assertEqual(
                summary["metadataContract"]["reflectionInputs"]["workgroupSizes"],
                [],
            )
            self.assertFalse(
                summary["compatibilityReport"]["workgroupSizes"]["available"]
            )
            with self.assertRaisesRegex(
                PackageReadError,
                "missing reflection workgroup size",
            ):
                plan.require_workgroup_size("compute", "main")

    def test_function_constant_metadata_handoff_uses_reflection_only(self) -> None:
        with tempfile.TemporaryDirectory(suffix=".cglb") as temp_dir:
            package_dir = Path(temp_dir)
            self._write_valid_package(package_dir, target="directx")
            reflection_path = package_dir / "reflection.json"
            reflection = json.loads(reflection_path.read_text(encoding="utf-8"))
            function_constants = [
                {
                    "name": "TILE_SIZE",
                    "type": "int",
                    "value": "16",
                    "specializationId": 7,
                },
                {
                    "name": "USE_FAST_PATH",
                    "type": "bool",
                    "value": "true",
                },
            ]
            reflection["functionConstants"] = function_constants
            self._write_json(reflection_path, reflection)
            source_path = package_dir / "source" / "invalid.cgl"
            source_path.parent.mkdir()
            source_path.write_text(
                "loader function constant handoff must not parse CrossGL source\n",
                encoding="utf-8",
            )

            with self._guard_crossgl_source_path_reads():
                plan = read_loader_plan(package_dir, "directx")

            summary = plan.to_summary()
            contract = plan.to_runtime_loader_plan_contract()
            reflection_summary = summary["reflectionResources"]
            contract_reflection = summary["metadataContract"]["reflectionInputs"]
            host_loader_integration = contract["hostLoaderIntegration"]
            load_unit = host_loader_integration["loadUnits"][0]
            bind_step = load_unit["loadSteps"][1]

            self.assertTrue(plan.loadable, summary["diagnostics"])
            self.assertEqual(plan.function_constants, tuple(function_constants))
            self.assertEqual(plan.function_constant("TILE_SIZE"), function_constants[0])
            self.assertEqual(
                plan.require_function_constant("USE_FAST_PATH"),
                function_constants[1],
            )
            self.assertEqual(reflection_summary["functionConstantCount"], 2)
            self.assertEqual(reflection_summary["specializationConstantCount"], 1)
            self.assertTrue(reflection_summary["functionConstantsAvailable"])
            self.assertEqual(
                reflection_summary["functionConstants"], function_constants
            )
            self.assertEqual(contract_reflection["functionConstantCount"], 2)
            self.assertEqual(contract_reflection["specializationConstantCount"], 1)
            self.assertTrue(contract_reflection["functionConstantsAvailable"])
            self.assertEqual(
                contract_reflection["functionConstants"], function_constants
            )
            self.assertEqual(
                summary["compatibilityReport"]["functionConstants"]["records"],
                function_constants,
            )
            self.assertEqual(
                host_loader_integration["summary"]["functionConstantCount"],
                2,
            )
            self.assertEqual(
                host_loader_integration["summary"]["specializationConstantCount"],
                1,
            )
            self.assertEqual(load_unit["hostInterface"]["functionConstantCount"], 2)
            self.assertEqual(
                load_unit["hostInterface"]["specializationConstantCount"],
                1,
            )
            self.assertEqual(bind_step["metadata"]["functionConstantCount"], 2)
            self.assertEqual(
                bind_step["metadata"]["specializationConstantCount"],
                1,
            )
            self.assertEqual(list(package_dir.rglob("*.cgl")), [source_path])

    def test_metadata_contract_consumes_declared_package_inputs_only(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory(suffix=".cglb") as temp_dir:
            package_dir = Path(temp_dir)
            self._write_valid_package(
                package_dir,
                target="directx",
                package_artifact_requirements={
                    "target": "directx",
                    "packageMode": "source-package",
                    "requiredPathArtifacts": ["backendSource", "nativeBinary"],
                    "requiresNativeBinaryStatus": True,
                    "allowsPlannedNativeBinary": True,
                    "allowsPlannedNativeSourceEvidence": True,
                    "evidenceIds": [
                        "target-legalization.v1.directx.package-artifact.required.backendSource",
                        "target-legalization.v1.directx.package-artifact.required.nativeBinary",
                    ],
                },
            )
            target_tool_requirements = {
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
            manifest["targetLegalizationToolRequirements"] = target_tool_requirements
            self._write_json(manifest_path, manifest)
            source_path = package_dir / "source" / "invalid.cgl"
            source_path.parent.mkdir()
            source_path.write_text(
                "metadata contract must not parse CrossGL source\n",
                encoding="utf-8",
            )

            original_read_text = Path.read_text
            original_read_bytes = Path.read_bytes

            def guarded_read_text(path: Path, *args: object, **kwargs: object) -> str:
                if path.suffix == ".cgl":
                    raise AssertionError(f"loader parsed source file: {path}")
                return original_read_text(path, *args, **kwargs)

            def guarded_read_bytes(
                path: Path, *args: object, **kwargs: object
            ) -> bytes:
                if path.suffix == ".cgl":
                    raise AssertionError(f"loader parsed source file: {path}")
                return original_read_bytes(path, *args, **kwargs)

            with mock.patch.object(Path, "read_text", guarded_read_text):
                with mock.patch.object(Path, "read_bytes", guarded_read_bytes):
                    plan = read_loader_plan(package_dir, "directx")
                    summary = plan.to_summary()

            contract = summary["metadataContract"]

            self.assertTrue(plan.loadable, summary["diagnostics"])
            self.assertEqual(
                summary["metadataContract"],
                plan.metadata_contract_summary,
            )
            self.assertEqual(contract["schemaVersion"], 1)
            self.assertEqual(contract["metadataOnly"], True)
            self.assertEqual(contract["sourceParsingRequired"], False)
            self.assertEqual(contract["compilerInvocationRequired"], False)
            self.assertEqual(contract["deviceExecutionRequired"], False)
            self.assertEqual(contract["packageTarget"], "directx")
            self.assertEqual(contract["loaderTarget"], "directx")
            self.assertEqual(contract["status"], "source-only")
            self.assertEqual(
                contract["contractSource"],
                "manifest.packageArtifactRequirements",
            )
            self.assertFalse(contract["requirements"]["reportOnly"])
            self.assertEqual(
                contract["requirements"]["compatibilityScope"],
                "recorded-package-metadata",
            )
            self.assertEqual(
                contract["targetLegalizationEvidence"],
                summary["targetLegalizationEvidence"],
            )
            self.assertEqual(
                contract["targetLegalizationEvidence"],
                summary["compatibilityReport"]["targetLegalizationEvidence"],
            )
            expected_tool_requirements = {
                "present": True,
                **target_tool_requirements,
            }
            self.assertEqual(
                summary["targetLegalizationToolRequirements"],
                expected_tool_requirements,
            )
            self.assertEqual(
                contract["targetLegalizationToolRequirements"],
                expected_tool_requirements,
            )
            self.assertEqual(
                summary["compatibilityReport"]["targetLegalizationToolRequirements"],
                expected_tool_requirements,
            )
            self.assertEqual(
                contract["targetLegalizationEvidence"]["manifestToolRequirements"],
                expected_tool_requirements,
            )
            self.assertEqual(
                contract["targetLegalizationEvidence"]["checks"][
                    "manifestToolRequirementsTargetMatchesPackage"
                ],
                True,
            )
            self.assertEqual(
                contract["targetLegalizationEvidence"]["checks"][
                    "manifestToolRequirementsPackageModeMatchesRequirements"
                ],
                True,
            )
            self.assertEqual(
                contract["targetLegalizationEvidence"]["checks"][
                    "manifestToolRequirementEvidenceIdsPresent"
                ],
                True,
            )
            self.assertFalse(
                contract["requirements"]["legacyGeneratedRequirements"]["reportOnly"]
            )
            self.assertIsNone(
                contract["requirements"]["legacyGeneratedRequirements"][
                    "compatibilityScope"
                ]
            )
            self.assertEqual(
                summary["requiredMetadataInputs"],
                [
                    {
                        "name": "manifest",
                        "path": "manifest.json",
                        "required": True,
                        "declaredBy": "package-root",
                        "schemaVersion": 1,
                        "supportedSchemaVersion": 1,
                        "compatible": True,
                    },
                    {
                        "name": "reflection",
                        "path": "reflection.json",
                        "required": True,
                        "declaredBy": "package-root",
                        "schemaVersion": 1,
                        "supportedSchemaVersion": 1,
                        "compatible": True,
                    },
                    {
                        "name": "diagnostics",
                        "path": "diagnostics.json",
                        "required": True,
                        "declaredBy": "package-root",
                        "schemaVersion": 1,
                        "supportedSchemaVersion": 1,
                        "compatible": True,
                    },
                ],
            )
            self.assertEqual(
                contract["requiredMetadataInputs"],
                summary["requiredMetadataInputs"],
            )
            self.assertEqual(
                summary["artifactSelection"]["supportedModes"],
                ["auto", "native", "source-package"],
            )
            self.assertEqual(summary["artifactSelection"]["requestedMode"], "auto")
            self.assertEqual(
                summary["artifactSelection"]["selectedMode"],
                "source-package",
            )
            self.assertEqual(
                summary["artifactSelection"]["runtimeArtifact"]["name"],
                "backendSource",
            )
            self.assertEqual(summary["artifactSelection"]["sourceInputs"], [])
            self.assertFalse(summary["artifactSelection"]["sourceParsingRequired"])
            self.assertFalse(summary["artifactSelection"]["compilerInvocationRequired"])
            self.assertFalse(summary["artifactSelection"]["deviceExecutionRequired"])
            self.assertEqual(
                contract["artifactSelection"],
                summary["artifactSelection"],
            )
            self.assertEqual(summary["targetCompatibility"]["decision"], "accepted")
            self.assertEqual(
                summary["targetCompatibility"]["category"],
                "target-accepted",
            )
            self.assertEqual(summary["targetCompatibility"]["diagnostics"], [])
            self.assertEqual(summary["targetCompatibility"]["diagnosticCodes"], [])
            self.assertEqual(
                contract["targetCompatibility"],
                summary["targetCompatibility"],
            )
            self.assertEqual(
                contract["metadataDocuments"],
                [
                    {
                        "name": "manifest",
                        "path": "manifest.json",
                        "schemaVersion": 1,
                        "compatible": True,
                    },
                    {
                        "name": "reflection",
                        "path": "reflection.json",
                        "schemaVersion": 1,
                        "compatible": True,
                    },
                    {
                        "name": "diagnostics",
                        "path": "diagnostics.json",
                        "schemaVersion": 1,
                        "compatible": True,
                    },
                ],
            )
            self.assertEqual(
                contract["requiredArtifactInputs"],
                [
                    {
                        "name": "backendSource",
                        "path": "backend/directx/RuntimeLoaderFixture.hlsl",
                        "declaredBy": "manifest.artifacts.backendSource",
                    },
                    {
                        "name": "nativeBinary",
                        "path": "backend/directx/RuntimeLoaderFixture.dxil",
                        "declaredBy": "manifest.artifacts.nativeBinary",
                    },
                ],
            )
            self.assertEqual(
                [
                    (artifact["name"], artifact["path"], artifact["selectedForLoad"])
                    for artifact in contract["selectedArtifactInputs"]
                ],
                [
                    (
                        "backendSource",
                        "backend/directx/RuntimeLoaderFixture.hlsl",
                        True,
                    ),
                    (
                        "nativeBinary",
                        "backend/directx/RuntimeLoaderFixture.dxil",
                        False,
                    ),
                ],
            )
            self.assertEqual(
                contract["runtimeArtifact"],
                {
                    "name": "backendSource",
                    "path": "backend/directx/RuntimeLoaderFixture.hlsl",
                    "declaredBy": "manifest.artifacts.backendSource",
                },
            )
            self.assertEqual(contract["reflectionInputs"]["entryPointCount"], 1)
            self.assertEqual(contract["reflectionInputs"]["resourceCount"], 1)
            self.assertEqual(
                contract["reflectionInputs"]["targetResourceBindingCount"],
                1,
            )
            self.assertEqual(contract["sourceInputs"], [])
            self.assertEqual(
                summary["artifactRoleCompatibility"],
                plan.artifact_role_compatibility,
            )
            self.assertEqual(
                summary["artifactRoleCompatibility"]["selectedRuntimeArtifact"],
                "backendSource",
            )
            self.assertEqual(
                [
                    (
                        role["role"],
                        role["status"],
                        role["selectedForRuntime"],
                        role["bytesRequired"],
                    )
                    for role in summary["artifactRoleCompatibility"]["roles"]
                ],
                [
                    (
                        "backendSource",
                        "selected-runtime-artifact",
                        True,
                        True,
                    ),
                    (
                        "nativeBinary",
                        "planned-evidence",
                        False,
                        False,
                    ),
                ],
            )
            self.assertEqual(list(package_dir.rglob("*.cgl")), [source_path])

    def test_recorded_source_free_native_plan_is_not_downgraded_by_legacy_defaults(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory(suffix=".cglb") as temp_dir:
            package_dir = Path(temp_dir)
            self._write_valid_package(package_dir, target="metal")
            manifest_path = package_dir / "manifest.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            artifacts = manifest["artifacts"]
            native_path = artifacts["nativeBinary"]
            artifacts.pop("backendSource")
            artifacts.pop("intermediate")
            artifacts["nativeArtifactDescriptor"] = "metadata/native-artifact.json"
            manifest["packageArtifactRequirements"] = {
                "target": "metal",
                "packageMode": "native",
                "requiredPathArtifacts": ["nativeBinary"],
                "requiresNativeBinaryStatus": False,
                "allowsPlannedNativeBinary": False,
                "allowsPlannedNativeSourceEvidence": False,
            }
            self._write_json(manifest_path, manifest)
            native_file = package_dir / native_path
            descriptor_path = package_dir / "metadata" / "native-artifact.json"
            descriptor_path.parent.mkdir()
            source_payload = (
                "recorded source-free native plans must not parse source\n"
            ).encode("utf-8")
            self._write_json(
                descriptor_path,
                {
                    "schemaVersion": 1,
                    "kind": "crossgl.nativeArtifact",
                    "contractVersion": "native-artifact-v0",
                    "target": "metal",
                    "binaryKind": "metal.metallib",
                    "sourcePath": "source/RuntimeLoaderFixture.cgl",
                    "sourceHash": {
                        "algorithm": "sha256",
                        "value": hashlib.sha256(source_payload).hexdigest(),
                    },
                    "artifactPath": native_path,
                    "artifactHash": {
                        "algorithm": "sha256",
                        "value": hashlib.sha256(native_file.read_bytes()).hexdigest(),
                    },
                    "sizeBytes": native_file.stat().st_size,
                    "toolchainProvenance": {
                        "producer": "runtime loader fixture",
                        "tools": [],
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
                },
            )
            source_path = package_dir / "source" / "RuntimeLoaderFixture.cgl"
            source_path.parent.mkdir()
            source_path.write_bytes(source_payload)

            with self._guard_crossgl_source_path_reads():
                plan = read_loader_plan(package_dir, "metal")

            summary = plan.to_summary()
            admission = summary["runtimeArtifactAdmission"]
            requirement_codes = [
                diagnostic.code
                for diagnostic in plan.compatibility_report.requirement_diagnostics
            ]

            self.assertTrue(plan.loadable, summary["diagnostics"])
            self.assertFalse(plan.source_parsing_required)
            self.assertEqual(plan.required_artifacts, ("nativeBinary",))
            self.assertEqual(plan.runtime_artifact.name, "nativeBinary")
            self.assertEqual(
                summary["runtimeArtifactSelection"]["selectedPackageMode"],
                "native",
            )
            self.assertEqual(
                summary["metadataContract"]["contractSource"],
                "manifest.packageArtifactRequirements",
            )
            self.assertFalse(summary["metadataContract"]["requirements"]["reportOnly"])
            self.assertEqual(
                summary["metadataContract"]["requirements"]["compatibilityScope"],
                "recorded-package-metadata",
            )
            self.assertEqual(admission["nativeArtifact"]["decision"], "accepted")
            self.assertEqual(
                admission["sourcePackageFallback"]["decision"],
                "skipped",
            )
            self.assertEqual(
                admission["sourcePackageFallback"]["reason"],
                "runtime.source_package_fallback.not_allowed",
            )
            self.assertNotIn(
                "package.artifact_requirements.package_mode_mismatch",
                requirement_codes,
            )
            self.assertEqual(list(package_dir.rglob("*.cgl")), [source_path])

    def test_selects_required_target_artifacts_without_source_parse(self) -> None:
        with tempfile.TemporaryDirectory(suffix=".cglb") as temp_dir:
            package_dir = Path(temp_dir)
            self._write_valid_package(package_dir)
            (package_dir / "source").mkdir()
            (package_dir / "source" / "invalid.cgl").write_text(
                "this is not CrossGL source\n",
                encoding="utf-8",
            )

            plan = read_loader_plan(package_dir, "metal")
            summary = plan.to_summary()

            self.assertTrue(plan.loadable, summary["diagnostics"])
            self.assertIs(plan.require_loadable(), plan)
            self.assertFalse(plan.source_parsing_required)
            self.assertEqual(plan.module, "RuntimeLoaderFixture")
            self.assertEqual(plan.package_target, "metal")
            self.assertEqual(plan.loader_target, "metal")
            self.assertEqual(
                [artifact.name for artifact in plan.selected_artifacts],
                ["backendSource", "intermediate", "nativeBinary"],
            )
            self.assertEqual(
                plan.require_artifact("backendSource").package_path,
                "backend/metal/RuntimeLoaderFixture.metal",
            )
            self.assertIn(
                "generated Metal source",
                plan.require_artifact("backendSource").read_text(),
            )
            self.assertEqual(plan.require_artifact("nativeBinary").read_bytes(), b"bin")
            self.assertEqual(summary["loadable"], True)
            self.assertEqual(summary["selectedTarget"], "metal")
            self.assertEqual(summary["sourceParsingRequired"], False)
            self.assertEqual(
                summary["requiredArtifactPaths"],
                {
                    "backendSource": "backend/metal/RuntimeLoaderFixture.metal",
                    "intermediate": "backend/metal/RuntimeLoaderFixture.air",
                    "nativeBinary": "backend/metal/RuntimeLoaderFixture.metallib",
                },
            )
            self.assertEqual(
                summary["runtimeArtifactPath"],
                "backend/metal/RuntimeLoaderFixture.metallib",
            )
            self.assertEqual(summary["reflectionResources"]["selectedTarget"], "metal")
            self.assertEqual(summary["reflectionResources"]["entryPointCount"], 1)
            self.assertEqual(summary["reflectionResources"]["resourceCount"], 1)
            self.assertEqual(
                summary["reflectionResources"]["targetResourceBindingCount"],
                1,
            )
            self.assertEqual(
                summary["reflectionResources"]["targetResourceBindings"][0]["abi"],
                {"buffer": 0},
            )
            self.assertEqual(
                summary["reflectionResources"]["targetResourceBindings"][0][
                    "evidenceId"
                ],
                (
                    "target-legalization.v1.metal.resource-binding.compute."
                    "runtime_loader_main.OutputBuffer"
                ),
            )
            self.assertEqual(
                summary["reflectionResources"]["targetFeatures"],
                [
                    {
                        "target": "metal",
                        "kind": "package",
                        "name": "fixture",
                        "evidenceIds": [
                            "target-legalization.v1.metal.capability.required."
                            "metal.package.fixture"
                        ],
                    }
                ],
            )
            self.assertEqual(
                summary["metadataContract"]["reflectionInputs"]["targetFeatures"],
                summary["reflectionResources"]["targetFeatures"],
            )
            binding_metadata = summary["targetResourceBindingMetadata"]
            self.assertEqual(
                binding_metadata,
                summary["metadataContract"]["targetResourceBindingMetadata"],
            )
            self.assertEqual(binding_metadata["schemaVersion"], 1)
            self.assertEqual(binding_metadata["selectedTarget"], "metal")
            self.assertEqual(binding_metadata["loaderTarget"], "metal")
            self.assertEqual(binding_metadata["packageTarget"], "metal")
            self.assertEqual(binding_metadata["bindingCount"], 1)
            self.assertEqual(binding_metadata["skippedBindingCount"], 0)
            self.assertEqual(
                binding_metadata["bindings"][0],
                {
                    "target": "metal",
                    "stage": "compute",
                    "entryPoint": "runtime_loader_main",
                    "name": "OutputBuffer",
                    "kind": "storageBuffer",
                    "bindingClass": "uav",
                    "descriptorType": "UAV",
                    "set": None,
                    "binding": None,
                    "argumentIndex": None,
                    "abi": {"buffer": 0},
                    "evidenceId": (
                        "target-legalization.v1.metal.resource-binding.compute."
                        "runtime_loader_main.OutputBuffer"
                    ),
                    "identity": {
                        "target": "metal",
                        "stage": "compute",
                        "entryPoint": "runtime_loader_main",
                        "name": "OutputBuffer",
                        "kind": "storageBuffer",
                    },
                },
            )
            self.assertEqual(summary["availableTargets"], ["metal"])
            self.assertEqual(
                summary["targetAvailability"],
                summary["compatibilityReport"]["targetAvailability"],
            )
            self.assertEqual(
                summary["artifactAvailability"],
                summary["compatibilityReport"]["artifactAvailability"],
            )
            self.assertEqual(summary["availability"], plan.availability_summary)
            self.assertEqual(
                summary["availability"],
                summary["compatibilityReport"]["availability"],
            )
            self.assertEqual(
                summary["availability"]["artifacts"]["runtime"],
                summary["artifactAvailability"],
            )
            self.assertTrue(
                summary["availability"]["sidecars"]["manifest"]["compatible"]
            )
            self.assertEqual(
                summary["diagnosticSummary"],
                summary["compatibilityReport"]["diagnosticSummary"],
            )
            self.assertEqual(
                summary["compatibilityReport"]["sourceParsingRequired"], False
            )
            self.assertLegacyRequirementsFallbackOnly(summary["diagnostics"])
            self.assertEqual(summary["selectedArtifacts"][0]["name"], "backendSource")
            self.assertEqual(plan.require_runtime_artifact().name, "nativeBinary")
            self.assertEqual(
                [
                    (
                        role["role"],
                        role["status"],
                        role["selectedForRuntime"],
                        role["compatible"],
                    )
                    for role in summary["artifactRoleCompatibility"]["roles"]
                ],
                [
                    ("backendSource", "required-sidecar-artifact", False, True),
                    ("intermediate", "required-sidecar-artifact", False, True),
                    ("nativeBinary", "selected-runtime-artifact", True, True),
                ],
            )
            self.assertEqual(
                summary["runtimeArtifactSelection"]["artifact"]["name"],
                "nativeBinary",
            )
            self.assertEqual(
                summary["runtimeArtifactSelection"]["selectedPackageMode"],
                "native",
            )
            self.assertEqual(
                summary["metadataContract"]["contractSource"],
                "legacy-v0-target-contract",
            )
            self.assertTrue(summary["metadataContract"]["requirements"]["reportOnly"])
            self.assertEqual(
                summary["metadataContract"]["requirements"]["compatibilityScope"],
                "legacy/report-only",
            )
            self.assertTrue(
                summary["metadataContract"]["requirements"][
                    "legacyGeneratedRequirements"
                ]["reportOnly"]
            )
            self.assertEqual(
                summary["metadataContract"]["requirements"][
                    "legacyGeneratedRequirements"
                ]["compatibilityScope"],
                "legacy/report-only",
            )

    def test_loader_summary_exposes_descriptor_array_binding_metadata_without_source_parse(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory(suffix=".cglb") as temp_dir:
            package_dir = Path(temp_dir)
            self._write_valid_package(package_dir, target="directx")
            reflection_path = package_dir / "reflection.json"
            reflection = json.loads(reflection_path.read_text(encoding="utf-8"))
            array_dimensions = [
                {"kind": "fixed", "source": "4", "elementCount": 4},
            ]
            reflection["resources"][0].update(
                {
                    "type": "StructuredBuffer<float4>[4]",
                    "arrayDimensions": array_dimensions,
                    "arrayElementCount": 4,
                    "set": 2,
                    "binding": 3,
                }
            )
            reflection["targetResourceBindings"][0].update(
                {
                    "sourceType": "StructuredBuffer<float4>[4]",
                    "arrayDimensions": array_dimensions,
                    "arrayElementCount": 4,
                    "abi": {"space": 1, "register": "u3"},
                    "set": 2,
                    "binding": 3,
                    "bindingClass": "uav",
                    "descriptorType": "UAV",
                    "hlslType": "RWStructuredBuffer<float4>",
                }
            )
            self._write_json(reflection_path, reflection)
            source_path = package_dir / "source" / "RuntimeLoaderFixture.cgl"
            source_path.parent.mkdir()
            source_path.write_text(
                "loader must not parse source for descriptor array metadata\n",
                encoding="utf-8",
            )

            with self._guard_crossgl_source_path_reads():
                plan = read_loader_plan(package_dir, "directx")

            summary = plan.to_summary()
            resource = summary["reflectionResources"]["resources"][0]
            target_binding = summary["reflectionResources"]["targetResourceBindings"][0]
            binding_metadata = summary["targetResourceBindingMetadata"]["bindings"][0]

            self.assertTrue(plan.loadable, summary["diagnostics"])
            self.assertFalse(plan.source_parsing_required)
            self.assertEqual(resource["arrayDimensions"], array_dimensions)
            self.assertEqual(resource["arrayElementCount"], 4)
            self.assertEqual(resource["set"], 2)
            self.assertEqual(resource["binding"], 3)
            self.assertEqual(target_binding["arrayDimensions"], array_dimensions)
            self.assertEqual(target_binding["arrayElementCount"], 4)
            self.assertEqual(target_binding["abi"], {"space": 1, "register": "u3"})
            self.assertEqual(binding_metadata["arrayDimensions"], array_dimensions)
            self.assertEqual(binding_metadata["arrayElementCount"], 4)
            self.assertEqual(binding_metadata["set"], 2)
            self.assertEqual(binding_metadata["binding"], 3)
            self.assertEqual(binding_metadata["bindingClass"], "uav")
            self.assertEqual(binding_metadata["descriptorType"], "UAV")
            self.assertEqual(list(package_dir.rglob("*.cgl")), [source_path])

    def test_loader_summary_exposes_storage_image_metadata_without_source_parse(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory(suffix=".cglb") as temp_dir:
            package_dir = Path(temp_dir)
            self._write_valid_package(package_dir, target="directx")
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
                    "set": 2,
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
                    "abi": {"space": 2, "register": "u4"},
                    "set": 2,
                    "binding": 4,
                    "bindingClass": "uav",
                    "descriptorType": "UAV",
                    "hlslType": "RWTexture2D<float4>",
                    **storage_metadata,
                }
            )
            self._write_json(reflection_path, reflection)
            source_path = package_dir / "source" / "RuntimeLoaderFixture.cgl"
            source_path.parent.mkdir()
            source_path.write_text(
                "loader must not parse source for storage image metadata\n",
                encoding="utf-8",
            )

            with self._guard_crossgl_source_path_reads():
                plan = read_loader_plan(package_dir, "directx")

            summary = plan.to_summary()
            reflection_summary = summary["reflectionResources"]
            contract_reflection = summary["metadataContract"]["reflectionInputs"]
            resource = reflection_summary["resources"][0]
            target_binding = reflection_summary["targetResourceBindings"][0]
            binding_metadata = summary["targetResourceBindingMetadata"]["bindings"][0]

            self.assertTrue(plan.loadable, summary["diagnostics"])
            self.assertFalse(plan.source_parsing_required)
            self.assertEqual(resource["storageImageFormat"], "rgba8")
            self.assertEqual(resource["storageImageAccess"], "read_write")
            self.assertEqual(target_binding["storageImageFormat"], "rgba8")
            self.assertEqual(target_binding["storageImageAccess"], "read_write")
            self.assertEqual(binding_metadata["storageImageFormat"], "rgba8")
            self.assertEqual(binding_metadata["storageImageAccess"], "read_write")
            self.assertEqual(
                contract_reflection["resources"][0]["storageImageFormat"],
                "rgba8",
            )
            self.assertEqual(
                contract_reflection["targetResourceBindings"][0]["storageImageAccess"],
                "read_write",
            )
            self.assertEqual(list(package_dir.rglob("*.cgl")), [source_path])

    def test_opengl_summary_exposes_descriptor_array_binding_metadata_without_source_parse(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory(suffix=".cglb") as temp_dir:
            package_dir = Path(temp_dir)
            self._write_valid_package(package_dir, target="opengl")
            manifest_path = package_dir / "manifest.json"
            reflection_path = package_dir / "reflection.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            reflection = json.loads(reflection_path.read_text(encoding="utf-8"))
            native_binary_path = "backend/opengl/RuntimeLoaderFixture.native.glsl"
            (package_dir / native_binary_path).write_bytes(b"native")
            manifest["artifacts"]["nativeBinary"] = native_binary_path
            reflection["nativeBinary"] = native_binary_path
            array_dimensions = [
                {"kind": "fixed", "source": "2", "elementCount": 2},
                {"kind": "fixed", "source": "3", "elementCount": 3},
            ]
            reflection["resources"][0].update(
                {
                    "type": "float4[2][3]",
                    "arrayDimensions": array_dimensions,
                    "arrayElementCount": 6,
                    "set": 0,
                    "binding": 7,
                }
            )
            reflection["targetResourceBindings"][0].update(
                {
                    "sourceType": "float4[2][3]",
                    "arrayDimensions": array_dimensions,
                    "arrayElementCount": 6,
                    "abi": {"program": 0, "binding": 7},
                    "bindingClass": "storage-buffer",
                    "descriptorType": "shader-storage-buffer",
                }
            )
            self._write_json(manifest_path, manifest)
            self._write_json(reflection_path, reflection)
            source_path = package_dir / "source" / "RuntimeLoaderFixture.cgl"
            source_path.parent.mkdir()
            source_path.write_text(
                "opengl loader must not parse source for descriptor arrays\n",
                encoding="utf-8",
            )

            with self._guard_crossgl_source_path_reads():
                plan = plan_opengl_loader(package_dir)

            summary = plan.to_summary()
            admission_reflection = summary["openglSourcePackageAdmission"]["reflection"]
            resource = admission_reflection["resources"][0]
            target_binding = admission_reflection["targetResourceBindings"][0]
            generic_binding = summary["targetResourceBindingMetadata"]["bindings"][0]

            self.assertTrue(plan.loadable, summary["diagnostics"])
            self.assertFalse(plan.source_parsing_required)
            self.assertEqual(resource["arrayDimensions"], array_dimensions)
            self.assertEqual(resource["arrayElementCount"], 6)
            self.assertEqual(resource["binding"], 7)
            self.assertEqual(target_binding["arrayDimensions"], array_dimensions)
            self.assertEqual(target_binding["arrayElementCount"], 6)
            self.assertEqual(target_binding["binding"], 7)
            self.assertEqual(target_binding["descriptorType"], "shader-storage-buffer")
            self.assertEqual(generic_binding["arrayDimensions"], array_dimensions)
            self.assertEqual(generic_binding["arrayElementCount"], 6)
            self.assertEqual(list(package_dir.rglob("*.cgl")), [source_path])

    def test_loader_plan_reports_version_metadata_rejections_without_source_parse(
        self,
    ) -> None:
        cases = (
            (
                "missing compiler version",
                lambda manifest: manifest["compiler"].pop("version"),
                "incompatible",
                "package.compiler.version_missing",
                "non-empty string",
                None,
                False,
                True,
            ),
            (
                "malformed compiler version",
                lambda manifest: manifest["compiler"].__setitem__("version", 42),
                "incompatible",
                "package.compiler.version_invalid",
                "non-empty string",
                "number",
                False,
                True,
            ),
            (
                "future manifest schema",
                lambda manifest: manifest.__setitem__("schemaVersion", 2),
                "unsupported-version",
                "package.schema.incompatible",
                1,
                2,
                True,
                False,
            ),
            (
                "malformed manifest schema",
                lambda manifest: manifest.__setitem__("schemaVersion", "1"),
                "unsupported-version",
                "package.schema.version_invalid",
                1,
                "1",
                True,
                False,
            ),
        )

        original_read_text = Path.read_text
        original_read_bytes = Path.read_bytes

        def guarded_read_text(path: Path, *args: object, **kwargs: object) -> str:
            if path.suffix == ".cgl":
                raise AssertionError(f"loader parsed source file: {path}")
            return original_read_text(path, *args, **kwargs)

        def guarded_read_bytes(path: Path, *args: object, **kwargs: object) -> bytes:
            if path.suffix == ".cgl":
                raise AssertionError(f"loader parsed source file: {path}")
            return original_read_bytes(path, *args, **kwargs)

        for (
            name,
            mutate_manifest,
            expected_status,
            expected_code,
            expected_value,
            actual_value,
            expected_compiler_compatible,
            expected_manifest_compatible,
        ) in cases:
            with self.subTest(name=name):
                with tempfile.TemporaryDirectory(suffix=".cglb") as temp_dir:
                    package_dir = Path(temp_dir)
                    self._write_valid_package(package_dir)
                    manifest_path = package_dir / "manifest.json"
                    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
                    mutate_manifest(manifest)
                    self._write_json(manifest_path, manifest)
                    source_path = package_dir / "source" / "invalid.cgl"
                    source_path.parent.mkdir()
                    source_path.write_text(
                        "loader must report metadata versions without source parse\n",
                        encoding="utf-8",
                    )

                    with mock.patch.object(Path, "read_text", guarded_read_text):
                        with mock.patch.object(Path, "read_bytes", guarded_read_bytes):
                            plan = read_loader_plan(package_dir, "metal")
                    summary = plan.to_summary()

                    self.assertFalse(plan.loadable)
                    self.assertEqual(plan.selected_artifacts, ())
                    self.assertFalse(plan.source_parsing_required)
                    self.assertEqual(summary["status"], expected_status)
                    self.assertEqual(
                        [diagnostic.code for diagnostic in plan.reject_reasons],
                        [expected_code],
                    )
                    self.assertCompatibilityCodesWithLegacyFallback(
                        summary,
                        [expected_code],
                    )
                    self.assertEqual(
                        summary["loaderDiagnostics"]["selection"]["codes"],
                        [],
                    )
                    diagnostic = summary["diagnostics"][0]
                    self.assertEqual(diagnostic["document"], "manifest")
                    self.assertEqual(diagnostic.get("expected"), expected_value)
                    self.assertEqual(diagnostic.get("actual"), actual_value)
                    version_compatibility = summary["versionCompatibility"]
                    self.assertEqual(
                        summary["metadataContract"]["versionCompatibility"],
                        version_compatibility,
                    )
                    self.assertEqual(
                        summary["loaderDiagnostics"]["versionCompatibility"],
                        version_compatibility,
                    )
                    self.assertEqual(version_compatibility["schemaVersion"], 1)
                    self.assertEqual(version_compatibility["metadataOnly"], True)
                    self.assertEqual(
                        version_compatibility["sourceParsingRequired"],
                        False,
                    )
                    self.assertEqual(
                        version_compatibility["planStatus"],
                        expected_status,
                    )
                    self.assertEqual(version_compatibility["status"], expected_status)
                    self.assertEqual(
                        version_compatibility["compatible"],
                        plan.compatibility_report.compatible,
                    )
                    self.assertEqual(
                        version_compatibility["compiler"]["expectedName"],
                        "CrossGL-Compiler",
                    )
                    self.assertEqual(
                        version_compatibility["compiler"]["compatible"],
                        expected_compiler_compatible,
                    )
                    self.assertEqual(
                        version_compatibility["schemas"]["manifest"][
                            "supportedVersion"
                        ],
                        1,
                    )
                    self.assertEqual(
                        version_compatibility["schemas"]["manifest"]["compatible"],
                        expected_manifest_compatible,
                    )
                    self.assertEqual(
                        [
                            diagnostic["code"]
                            for diagnostic in version_compatibility["diagnostics"]
                        ],
                        [expected_code],
                    )
                    self.assertEqual(
                        version_compatibility["diagnosticCodes"],
                        [expected_code],
                    )
                    self.assertEqual(list(package_dir.rglob("*.cgl")), [source_path])

    def test_loader_plan_selects_recorded_package_artifact_requirements(
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
                native_artifact_descriptor=True,
            )

            plan = read_loader_plan(package_dir, "metal")
            summary = plan.to_summary()
            contract = plan.to_runtime_loader_plan_contract()

            self.assertTrue(plan.loadable, summary["diagnostics"])
            self.assertRuntimeLoaderPlanContractValid(contract)
            self.assertEqual(
                plan.required_artifacts,
                ("backendSource", "intermediate", "nativeBinary"),
            )
            self.assertEqual(
                [artifact.name for artifact in plan.selected_artifacts],
                ["backendSource", "intermediate", "nativeBinary"],
            )
            self.assertEqual(plan.require_runtime_artifact().name, "nativeBinary")
            self.assertEqual(contract["selectedArtifact"]["name"], "nativeBinary")
            load_unit = contract["hostLoaderIntegration"]["loadUnits"][0]
            self.assertEqual(load_unit["artifact"], contract["selectedArtifact"])
            self.assertEqual(load_unit["artifactFormat"], "native-binary")
            self.assertEqual(load_unit["adapterKind"], "native-binary-loader")
            self.assertEqual(
                load_unit["loadSteps"][0]["metadata"]["artifact"],
                {
                    "name": "nativeBinary",
                    "packageMode": "native",
                    "artifactFormat": "native-binary",
                },
            )
            self.assertEqual(
                summary["compatibilityReport"]["packageArtifactRequirements"][
                    "requirementsSource"
                ],
                "manifest",
            )
            self.assertFalse(summary["metadataContract"]["requirements"]["reportOnly"])
            self.assertEqual(
                summary["metadataContract"]["requirements"]["compatibilityScope"],
                "recorded-package-metadata",
            )
            self.assertEqual(
                summary["requiredArtifactPaths"],
                {
                    "backendSource": "backend/metal/RuntimeLoaderFixture.metal",
                    "intermediate": "backend/metal/RuntimeLoaderFixture.air",
                    "nativeBinary": "backend/metal/RuntimeLoaderFixture.metallib",
                },
            )
            self.assertEqual(summary["missingArtifacts"], [])

    def test_runtime_artifact_handoff_directory_returns_selected_artifact_bytes(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory(suffix=".cglb") as temp_dir:
            package_dir = Path(temp_dir)
            self._write_valid_package(package_dir)
            source_path = package_dir / "source" / "invalid.cgl"
            source_path.parent.mkdir()
            source_path.write_text(
                "runtime artifact handoff must not parse source\n",
                encoding="utf-8",
            )

            with self._guard_crossgl_source_path_reads():
                plan = read_loader_plan(package_dir, "metal")
                handoff = plan.require_runtime_artifact_handoff()

            artifact = plan.require_runtime_artifact()
            self.assertTrue(plan.loadable, plan.to_summary()["diagnostics"])
            self.assertRuntimeArtifactHandoff(
                handoff,
                expected_bytes=b"bin",
                expected_metadata=plan.metadata_contract_summary,
                expected_package_format="directory",
                expected_artifact_name="nativeBinary",
                expected_package_path="backend/metal/RuntimeLoaderFixture.metallib",
                expected_absolute_path=artifact.absolute_path or str(artifact.path),
                expected_selected_package_mode="native",
                expected_size=artifact.size,
            )
            self.assertEqual(list(package_dir.rglob("*.cgl")), [source_path])

    def test_runtime_artifact_handoff_zip_returns_selected_artifact_bytes(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir)
            package_dir = temp_root / "package-dir"
            package_dir.mkdir()
            self._write_valid_package(package_dir)
            source_path = package_dir / "source" / "invalid.cgl"
            source_path.parent.mkdir()
            source_path.write_text(
                "zip runtime artifact handoff must not parse source\n",
                encoding="utf-8",
            )
            zip_path = temp_root / "RuntimeLoaderFixture.cglb"
            self._write_zip_package(package_dir, zip_path)

            with self._guard_crossgl_source_path_reads():
                with self._guard_crossgl_source_archive_reads():
                    plan = read_loader_plan(zip_path, "metal")
                    handoff = plan.require_runtime_artifact_handoff()

            artifact = plan.require_runtime_artifact()
            self.assertTrue(plan.loadable, plan.to_summary()["diagnostics"])
            self.assertRuntimeArtifactHandoff(
                handoff,
                expected_bytes=b"bin",
                expected_metadata=plan.metadata_contract_summary,
                expected_package_format="zip",
                expected_artifact_name="nativeBinary",
                expected_package_path="backend/metal/RuntimeLoaderFixture.metallib",
                expected_absolute_path=(
                    f"{zip_path}!/backend/metal/RuntimeLoaderFixture.metallib"
                ),
                expected_selected_package_mode="native",
                expected_size=artifact.size,
            )

    def test_runtime_artifact_handoff_rejects_not_loadable_plan(self) -> None:
        with tempfile.TemporaryDirectory(suffix=".cglb") as temp_dir:
            package_dir = Path(temp_dir)
            self._write_valid_package(package_dir)
            source_path = package_dir / "source" / "invalid.cgl"
            source_path.parent.mkdir()
            source_path.write_text(
                "runtime artifact handoff must not parse source for rejects\n",
                encoding="utf-8",
            )

            with self._guard_crossgl_source_path_reads():
                plan = read_loader_plan(package_dir, "vulkan")
                self.assertFalse(plan.loadable)
                with self.assertRaisesRegex(
                    PackageReadError,
                    "runtime loader cannot load package",
                ):
                    plan.require_runtime_artifact_handoff()

            self.assertIsNone(plan.runtime_artifact)
            self.assertEqual(list(package_dir.rglob("*.cgl")), [source_path])

    def test_runtime_artifact_handoff_enforces_byte_limit_for_directory_and_zip(
        self,
    ) -> None:
        payload = b"0123456789abcdef"

        for package_format in ("directory", "zip"):
            with self.subTest(package_format=package_format):
                with tempfile.TemporaryDirectory() as temp_dir:
                    temp_root = Path(temp_dir)
                    package_dir = temp_root / "package-dir"
                    package_dir.mkdir()
                    self._write_valid_package(package_dir, target="directx")
                    source_path = package_dir / "source" / "invalid.cgl"
                    source_path.parent.mkdir()
                    source_path.write_text(
                        "runtime artifact byte limit must not parse source\n",
                        encoding="utf-8",
                    )
                    artifact_path = (
                        package_dir / "backend/directx/RuntimeLoaderFixture.hlsl"
                    )
                    artifact_path.write_bytes(payload)

                    if package_format == "zip":
                        package_root = temp_root / "RuntimeLoaderFixture.cglb"
                        self._write_zip_package(package_dir, package_root)
                    else:
                        package_root = package_dir

                    with self._guard_crossgl_source_path_reads():
                        with self._guard_crossgl_source_archive_reads():
                            plan = read_loader_plan(package_root, "directx")
                            handoff = plan.require_runtime_artifact_handoff(
                                byte_limit=len(payload)
                            )
                            with self.assertRaisesRegex(
                                PackageReadError,
                                "package artifact exceeds runtime byte limit",
                            ):
                                plan.require_runtime_artifact_handoff(
                                    byte_limit=len(payload) - 1
                                )

                    artifact = plan.require_runtime_artifact()
                    self.assertRuntimeArtifactHandoff(
                        handoff,
                        expected_bytes=payload,
                        expected_metadata=plan.metadata_contract_summary,
                        expected_package_format=package_format,
                        expected_artifact_name="backendSource",
                        expected_package_path=(
                            "backend/directx/RuntimeLoaderFixture.hlsl"
                        ),
                        expected_absolute_path=(
                            artifact.absolute_path or str(artifact.path)
                        ),
                        expected_selected_package_mode="source-package",
                        expected_size=len(payload),
                    )
                    self.assertEqual(list(package_dir.rglob("*.cgl")), [source_path])

    def test_runtime_artifact_handoff_preserves_archive_identity(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir)
            package_dir = temp_root / "package-dir"
            package_dir.mkdir()
            self._write_valid_package(package_dir)
            zip_path = temp_root / "RuntimeLoaderFixture.cglb"
            self._write_zip_package(package_dir, zip_path, prefix=zip_path.name)

            plan = read_loader_plan(zip_path, "metal")
            handoff = plan.require_runtime_artifact_handoff()

            self.assertRuntimeArtifactHandoff(
                handoff,
                expected_bytes=b"bin",
                expected_metadata=plan.metadata_contract_summary,
                expected_package_format="zip",
                expected_artifact_name="nativeBinary",
                expected_package_path="backend/metal/RuntimeLoaderFixture.metallib",
                expected_absolute_path=(
                    f"{zip_path}!/{zip_path.name}/backend/metal/"
                    "RuntimeLoaderFixture.metallib"
                ),
                expected_selected_package_mode="native",
                expected_size=3,
            )

    def test_loader_plan_rejects_recorded_required_artifact_contract_drift(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory(suffix=".cglb") as temp_dir:
            package_dir = Path(temp_dir)
            self._write_valid_package(
                package_dir,
                package_artifact_requirements={
                    "target": "metal",
                    "packageMode": "native",
                    "requiredPathArtifacts": ["backendSource", "nativeBinary"],
                    "requiresNativeBinaryStatus": False,
                    "allowsPlannedNativeBinary": False,
                    "allowsPlannedNativeSourceEvidence": False,
                },
            )
            source_path = package_dir / "source" / "invalid.cgl"
            source_path.parent.mkdir()
            source_path.write_text(
                "loader must not parse source to repair contract drift\n",
                encoding="utf-8",
            )

            with self._guard_crossgl_source_path_reads():
                plan = read_loader_plan(package_dir, "metal")

            summary = plan.to_summary()
            reject_codes = [diagnostic.code for diagnostic in plan.reject_reasons]
            expected_code = (
                "package.artifact_requirements.required_path_artifacts_mismatch"
            )

            self.assertFalse(plan.loadable)
            self.assertEqual(plan.required_artifacts, ())
            self.assertEqual(plan.selected_artifacts, ())
            self.assertIsNone(plan.runtime_artifact)
            self.assertFalse(plan.source_parsing_required)
            self.assertIn(expected_code, reject_codes)
            self.assertIsNone(
                summary["compatibilityReport"]["packageArtifactRequirements"]
            )
            self.assertEqual(
                summary["compatibilityReport"]["packageArtifactRequirementsStatus"][
                    "reason"
                ],
                expected_code,
            )
            self.assertEqual(summary["runtimeArtifactSelection"]["artifact"], None)
            self.assertEqual(list(package_dir.rglob("*.cgl")), [source_path])

    def test_loader_plan_rejects_malformed_recorded_package_artifact_requirements(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory(suffix=".cglb") as temp_dir:
            package_dir = Path(temp_dir)
            self._write_valid_package(
                package_dir,
                package_artifact_requirements={
                    "target": "metal",
                    "packageMode": "source-package",
                    "requiredPathArtifacts": ["nativeBinary"],
                    "requiresNativeBinaryStatus": False,
                    "allowsPlannedNativeBinary": False,
                    "allowsPlannedNativeSourceEvidence": False,
                },
            )
            (package_dir / "source").mkdir()
            (package_dir / "source" / "invalid.cgl").write_text(
                "loader must not parse source for malformed requirements\n",
                encoding="utf-8",
            )

            plan = read_loader_plan(package_dir, "metal")
            summary = plan.to_summary()
            reject_codes = [diagnostic.code for diagnostic in plan.reject_reasons]

            self.assertFalse(plan.loadable)
            self.assertEqual(plan.required_artifacts, ())
            self.assertEqual(plan.selected_artifacts, ())
            self.assertIsNone(plan.runtime_artifact)
            self.assertFalse(plan.source_parsing_required)
            self.assertIn(
                "package.artifact_requirements.source_package_artifact_missing",
                reject_codes,
            )
            self.assertIn(
                "package.artifact_requirements.source_package_status_invalid",
                reject_codes,
            )
            self.assertIsNone(
                summary["compatibilityReport"]["packageArtifactRequirements"]
            )
            self.assertIsNone(summary["runtimeArtifactSelection"]["artifact"])
            self.assertEqual(
                list(package_dir.rglob("*.cgl")),
                [package_dir / "source" / "invalid.cgl"],
            )

    def test_loader_plan_rejects_null_recorded_package_artifact_requirements_without_legacy_fallback(
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
                "loader must not parse source for null requirements\n",
                encoding="utf-8",
            )

            with self._guard_crossgl_source_path_reads():
                plan = read_loader_plan(package_dir, "metal")

            summary = plan.to_summary()
            reject_codes = [diagnostic.code for diagnostic in plan.reject_reasons]
            requirement_summary = summary["compatibilityReport"]["admission"][
                "requirements"
            ]

            self.assertFalse(plan.loadable)
            self.assertEqual(plan.required_artifacts, ())
            self.assertEqual(plan.selected_artifacts, ())
            self.assertIsNone(plan.runtime_artifact)
            self.assertFalse(plan.source_parsing_required)
            self.assertIn("package.artifact_requirements.invalid", reject_codes)
            self.assertIsNone(summary["metadataContract"]["contractSource"])
            self.assertEqual(summary["metadataContract"]["sourceInputs"], [])
            self.assertIsNone(
                summary["compatibilityReport"]["packageArtifactRequirements"]
            )
            self.assertIsNone(summary["runtimeArtifactSelection"]["artifact"])
            self.assertTrue(requirement_summary["declared"])
            self.assertFalse(requirement_summary["legacyInferred"])
            self.assertEqual(requirement_summary["requirementsSource"], "manifest")
            self.assertFalse(requirement_summary["resolved"])
            self.assertFalse(requirement_summary["valid"])
            self.assertEqual(list(package_dir.rglob("*.cgl")), [source_path])

    def test_loader_plan_rejects_unknown_recorded_package_artifact_requirement_fields_without_source_parse(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory(suffix=".cglb") as temp_dir:
            package_dir = Path(temp_dir)
            self._write_valid_package(
                package_dir,
                package_artifact_requirements={
                    "target": "metal",
                    "packageMode": "native",
                    "requiredPathArtifacts": ["backendSource", "nativeBinary"],
                    "requiresNativeBinaryStatus": False,
                    "allowsPlannedNativeBinary": False,
                    "allowsPlannedNativeSourceEvidence": False,
                    "artifactFlavor": "compressed",
                },
            )
            source_path = package_dir / "source" / "invalid.cgl"
            source_path.parent.mkdir()
            source_path.write_text(
                "loader must not infer unknown package requirement fields "
                "from CrossGL source\n",
                encoding="utf-8",
            )

            original_read_text = Path.read_text
            original_read_bytes = Path.read_bytes

            def guarded_read_text(path: Path, *args: object, **kwargs: object) -> str:
                if path.suffix == ".cgl":
                    raise AssertionError(f"loader parsed source file: {path}")
                return original_read_text(path, *args, **kwargs)

            def guarded_read_bytes(
                path: Path, *args: object, **kwargs: object
            ) -> bytes:
                if path.suffix == ".cgl":
                    raise AssertionError(f"loader parsed source file: {path}")
                return original_read_bytes(path, *args, **kwargs)

            with mock.patch.object(Path, "read_text", guarded_read_text):
                with mock.patch.object(Path, "read_bytes", guarded_read_bytes):
                    plan = read_loader_plan(package_dir, "metal")

            summary = plan.to_summary()
            reject_codes = [diagnostic.code for diagnostic in plan.reject_reasons]

            self.assertFalse(plan.loadable)
            self.assertEqual(plan.required_artifacts, ())
            self.assertEqual(plan.selected_artifacts, ())
            self.assertIsNone(plan.runtime_artifact)
            self.assertFalse(plan.source_parsing_required)
            self.assertIn(
                "package.artifact_requirements.unexpected_field",
                reject_codes,
            )
            self.assertIsNone(
                summary["compatibilityReport"]["packageArtifactRequirements"]
            )
            self.assertIsNone(summary["runtimeArtifactSelection"]["artifact"])
            self.assertEqual(summary["metadataContract"]["sourceInputs"], [])
            self.assertEqual(summary["selectedArtifacts"], [])
            self.assertEqual(
                next(
                    diagnostic
                    for diagnostic in summary["rejectReasons"]
                    if diagnostic["code"]
                    == "package.artifact_requirements.unexpected_field"
                )["path"],
                "packageArtifactRequirements.artifactFlavor",
            )
            self.assertEqual(list(package_dir.rglob("*.cgl")), [source_path])

    def test_loader_plan_reports_future_requirement_schema_as_version_incompatible_without_source_parse(
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
                    "schemaVersion": 2,
                },
            )
            source_path = package_dir / "source" / "invalid.cgl"
            source_path.parent.mkdir()
            source_path.write_text(
                "loader must not inspect source for future requirements schema\n",
                encoding="utf-8",
            )

            with self._guard_crossgl_source_path_reads():
                plan = read_loader_plan(package_dir, "metal")

            summary = plan.to_summary()
            version_compatibility = summary["versionCompatibility"]

            self.assertFalse(plan.loadable)
            self.assertEqual(summary["status"], "unsupported-version")
            self.assertEqual(plan.selected_artifacts, ())
            self.assertIsNone(plan.runtime_artifact)
            self.assertFalse(plan.source_parsing_required)
            self.assertEqual(
                [diagnostic.code for diagnostic in plan.reject_reasons],
                ["package.artifact_requirements.schema_incompatible"],
            )
            self.assertEqual(
                version_compatibility["status"],
                "unsupported-version",
            )
            self.assertEqual(
                version_compatibility["planStatus"],
                "unsupported-version",
            )
            self.assertEqual(
                version_compatibility["diagnosticCodes"],
                ["package.artifact_requirements.schema_incompatible"],
            )
            self.assertEqual(
                summary["metadataContract"]["versionCompatibility"],
                version_compatibility,
            )
            self.assertEqual(
                summary["loaderDiagnostics"]["versionCompatibility"],
                version_compatibility,
            )
            self.assertIsNone(summary["metadataContract"]["contractSource"])
            self.assertEqual(summary["metadataContract"]["sourceInputs"], [])
            self.assertEqual(summary["metadataContract"]["requiredArtifactInputs"], [])
            self.assertEqual(summary["metadataContract"]["selectedArtifactInputs"], [])
            self.assertIsNone(summary["metadataContract"]["runtimeArtifact"])
            self.assertEqual(list(package_dir.rglob("*.cgl")), [source_path])

    def test_zip_loader_plan_rejects_recorded_requirement_contract_edges_without_legacy_fallback(
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
                        "loader must not parse zip CrossGL source or reconcile "
                        "rejected recorded requirements with v0 policy\n",
                        encoding="utf-8",
                    )
                    zip_path = temp_root / "RuntimeLoaderFixture.cglb"
                    self._write_zip_package(
                        package_dir,
                        zip_path,
                        prefix=zip_path.name,
                    )

                    with self._guard_crossgl_source_archive_reads():
                        plan = read_loader_plan(zip_path, "directx")

                    summary = plan.to_summary()
                    report_summary = summary["compatibilityReport"]
                    requirement_summary = report_summary[
                        "packageArtifactRequirementsStatus"
                    ]
                    requirement_codes = [
                        diagnostic["code"]
                        for diagnostic in requirement_summary["diagnostics"]
                    ]

                    self.assertFalse(plan.loadable)
                    self.assertEqual(summary["status"], expected_status)
                    self.assertEqual(summary["packageFormat"], "zip")
                    self.assertEqual(plan.required_artifacts, ())
                    self.assertEqual(plan.selected_artifacts, ())
                    self.assertIsNone(plan.runtime_artifact)
                    self.assertEqual(
                        [diagnostic.code for diagnostic in plan.reject_reasons],
                        [expected_code],
                    )
                    self.assertEqual(requirement_codes, [expected_code])
                    self.assertFalse(requirement_summary["legacyInferred"])
                    self.assertEqual(
                        requirement_summary["requirementsSource"],
                        "manifest",
                    )
                    self.assertEqual(requirement_summary["sourceKind"], "recorded")
                    self.assertEqual(requirement_summary["reason"], expected_code)
                    self.assertFalse(requirement_summary["resolved"])
                    self.assertFalse(requirement_summary["valid"])
                    self.assertIsNone(summary["metadataContract"]["contractSource"])
                    self.assertEqual(summary["metadataContract"]["sourceInputs"], [])
                    self.assertEqual(
                        summary["metadataContract"]["requiredArtifactInputs"],
                        [],
                    )
                    self.assertEqual(
                        summary["metadataContract"]["selectedArtifactInputs"],
                        [],
                    )
                    self.assertIsNone(summary["metadataContract"]["runtimeArtifact"])
                    self.assertIsNone(report_summary["packageArtifactRequirements"])
                    self.assertIsNone(summary["runtimeArtifactSelection"]["artifact"])
                    self.assertFalse(summary["sourceParsingRequired"])
                    self.assertFalse(
                        summary["runtimeArtifactSelection"]["sourceParsingRequired"]
                    )
                    with zipfile.ZipFile(zip_path) as archive:
                        self.assertIn(
                            f"{zip_path.name}/source/invalid.cgl",
                            archive.namelist(),
                        )

    def test_loader_plan_reports_future_native_descriptor_schema_as_version_incompatible_without_source_parse(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory(suffix=".cglb") as temp_dir:
            package_dir = Path(temp_dir)
            self._write_valid_package(package_dir)
            manifest_path = package_dir / "manifest.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            artifacts = manifest["artifacts"]
            descriptor_path = "metadata/native-artifact.json"
            source_artifact_path = artifacts["backendSource"]
            native_artifact_path = artifacts["nativeBinary"]
            artifacts["nativeArtifactDescriptor"] = descriptor_path
            self._write_json(manifest_path, manifest)
            (package_dir / "metadata").mkdir()
            self._write_json(
                package_dir / descriptor_path,
                {
                    "schemaVersion": 2,
                    "kind": "crossgl.nativeArtifact",
                    "contractVersion": "native-artifact-v0",
                    "target": "metal",
                    "binaryKind": "metal.metallib",
                    "artifactPath": native_artifact_path,
                    "artifactHash": {
                        "algorithm": "sha256",
                        "value": hashlib.sha256(
                            (package_dir / native_artifact_path).read_bytes()
                        ).hexdigest(),
                    },
                    "sizeBytes": (package_dir / native_artifact_path).stat().st_size,
                    "sourcePath": source_artifact_path,
                    "sourceHash": {
                        "algorithm": "sha256",
                        "value": hashlib.sha256(
                            (package_dir / source_artifact_path).read_bytes()
                        ).hexdigest(),
                    },
                    "toolchainProvenance": {
                        "producer": "runtime loader fixture",
                        "tools": [],
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
                },
            )
            source_path = package_dir / "source" / "invalid.cgl"
            source_path.parent.mkdir()
            source_path.write_text(
                "loader must not inspect source for future native descriptor schema\n",
                encoding="utf-8",
            )

            with self._guard_crossgl_source_path_reads():
                plan = read_loader_plan(package_dir, "metal")

            summary = plan.to_summary()
            version_compatibility = summary["versionCompatibility"]
            admission = summary["runtimeArtifactAdmission"]
            code = "package.native_artifact_descriptor.schema_incompatible"

            self.assertFalse(plan.loadable)
            self.assertEqual(summary["status"], "unsupported-version")
            self.assertEqual(plan.selected_artifacts, ())
            self.assertIsNone(plan.runtime_artifact)
            self.assertFalse(plan.source_parsing_required)
            self.assertIn(code, [diagnostic.code for diagnostic in plan.reject_reasons])
            self.assertEqual(
                version_compatibility["status"],
                "unsupported-version",
            )
            self.assertEqual(
                version_compatibility["planStatus"],
                "unsupported-version",
            )
            self.assertEqual(version_compatibility["diagnosticCodes"], [code])
            self.assertEqual(
                summary["metadataContract"]["versionCompatibility"],
                version_compatibility,
            )
            self.assertEqual(
                summary["loaderDiagnostics"]["versionCompatibility"],
                version_compatibility,
            )
            self.assertEqual(admission["decision"], "rejected")
            self.assertEqual(admission["nativeArtifact"]["reason"], code)
            self.assertIn(
                code,
                [
                    diagnostic["code"]
                    for diagnostic in admission["nativeArtifact"]["diagnostics"]
                ],
            )
            self.assertEqual(summary["metadataContract"]["sourceInputs"], [])
            self.assertEqual(summary["metadataContract"]["selectedArtifactInputs"], [])
            self.assertIsNone(summary["metadataContract"]["runtimeArtifact"])
            self.assertEqual(list(package_dir.rglob("*.cgl")), [source_path])

    def test_loader_plan_accepts_native_descriptor_host_tool_evidence_without_probe(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory(suffix=".cglb") as temp_dir:
            package_dir = Path(temp_dir)
            self._write_valid_package(package_dir)
            manifest_path = package_dir / "manifest.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            artifacts = manifest["artifacts"]
            descriptor_path = "metadata/native-artifact.json"
            source_artifact_path = artifacts["backendSource"]
            native_artifact_path = artifacts["nativeBinary"]
            artifacts["nativeArtifactDescriptor"] = descriptor_path
            self._write_json(manifest_path, manifest)
            (package_dir / "metadata").mkdir()
            self._write_json(
                package_dir / descriptor_path,
                {
                    "schemaVersion": 1,
                    "kind": "crossgl.nativeArtifact",
                    "contractVersion": "native-artifact-v0",
                    "target": "metal",
                    "binaryKind": "metal.metallib",
                    "artifactPath": native_artifact_path,
                    "artifactHash": {
                        "algorithm": "sha256",
                        "value": hashlib.sha256(
                            (package_dir / native_artifact_path).read_bytes()
                        ).hexdigest(),
                    },
                    "sizeBytes": (package_dir / native_artifact_path).stat().st_size,
                    "sourcePath": source_artifact_path,
                    "sourceHash": {
                        "algorithm": "sha256",
                        "value": hashlib.sha256(
                            (package_dir / source_artifact_path).read_bytes()
                        ).hexdigest(),
                    },
                    "toolchainProvenance": {
                        "producer": "runtime loader fixture",
                        "tools": [
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
                },
            )
            source_path = package_dir / "source" / "invalid.cgl"
            source_path.parent.mkdir()
            source_path.write_text(
                "loader must not parse source or probe host tools\n",
                encoding="utf-8",
            )

            with self._guard_crossgl_source_path_reads():
                with mock.patch(
                    "subprocess.run",
                    side_effect=AssertionError("loader probed host tools"),
                ):
                    plan = read_loader_plan(package_dir, "metal")

            summary = plan.to_summary()
            descriptor_artifact = next(
                artifact
                for artifact in plan.compatibility_report.available_artifacts
                if artifact.name == "nativeArtifactDescriptor"
            )
            descriptor = json.loads(descriptor_artifact.read_text(encoding="utf-8"))
            tool_records = descriptor["toolchainProvenance"]["tools"]

            self.assertTrue(plan.loadable, summary["diagnostics"])
            self.assertFalse(plan.source_parsing_required)
            self.assertEqual(summary["sourceInputs"], [])
            self.assertFalse(summary["compilerInvocationRequired"])
            self.assertFalse(summary["deviceExecutionRequired"])
            self.assertEqual(plan.runtime_artifact.name, "nativeBinary")
            self.assertEqual(summary["runtimeArtifactPath"], native_artifact_path)
            self.assertEqual(summary["rejectReasons"], [])
            self.assertEqual(summary["metadataContract"]["sourceInputs"], [])
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

    def test_loader_plan_reports_generated_contract_schema_evolution_without_source_parse(
        self,
    ) -> None:
        original_schema_version = runtime_target_contracts.SCHEMA_VERSION
        try:
            runtime_target_contracts.SCHEMA_VERSION = 2
            with tempfile.TemporaryDirectory(suffix=".cglb") as temp_dir:
                package_dir = Path(temp_dir)
                self._write_valid_package(package_dir)
                source_path = package_dir / "source" / "invalid.cgl"
                source_path.parent.mkdir()
                source_path.write_text(
                    "loader must not inspect source for evolved generated "
                    "target contracts\n",
                    encoding="utf-8",
                )

                with self._guard_crossgl_source_path_reads():
                    plan = read_loader_plan(package_dir, "metal")

                summary = plan.to_summary()
                requirements = summary["metadataContract"]["requirements"]

                self.assertFalse(plan.loadable)
                self.assertEqual(summary["status"], "unsupported-version")
                self.assertEqual(plan.selected_artifacts, ())
                self.assertIsNone(plan.runtime_artifact)
                self.assertFalse(plan.source_parsing_required)
                self.assertEqual(summary["metadataContract"]["sourceInputs"], [])
                self.assertIsNone(summary["metadataContract"]["contractSource"])
                self.assertFalse(requirements["declared"])
                self.assertTrue(requirements["legacyInferred"])
                self.assertEqual(
                    requirements["requirementsSource"],
                    "legacy-v0-target-contract",
                )
                self.assertFalse(requirements["resolved"])
                self.assertFalse(requirements["valid"])
                self.assertEqual(
                    [diagnostic["code"] for diagnostic in requirements["diagnostics"]],
                    ["package.target_contract.schema_incompatible"],
                )
                self.assertEqual(
                    [diagnostic.code for diagnostic in plan.reject_reasons],
                    ["package.target_contract.schema_incompatible"],
                )
                self.assertEqual(
                    summary["versionCompatibility"]["diagnosticCodes"],
                    ["package.target_contract.schema_incompatible"],
                )
                self.assertEqual(list(package_dir.rglob("*.cgl")), [source_path])
        finally:
            runtime_target_contracts.SCHEMA_VERSION = original_schema_version

    def test_existing_package_fixture_produces_source_free_plan(self) -> None:
        package_dir = FIXTURE_ROOT / "source-free-metal-native.cglb"

        plan = read_loader_plan(package_dir, "metal")
        summary = plan.to_summary()

        self.assertTrue(plan.loadable, summary["diagnostics"])
        self.assertEqual(summary["selectedTarget"], "metal")
        self.assertEqual(
            summary["runtimeArtifactPath"],
            ("backend/metal/SourceFreeMetalRuntimeExample.metallib"),
        )
        self.assertEqual(
            summary["requiredArtifactPaths"],
            {
                "backendSource": ("backend/metal/SourceFreeMetalRuntimeExample.metal"),
                "intermediate": ("backend/metal/SourceFreeMetalRuntimeExample.air"),
                "nativeBinary": (
                    "backend/metal/SourceFreeMetalRuntimeExample.metallib"
                ),
            },
        )
        self.assertEqual(
            summary["reflectionResources"]["entryPoints"],
            [
                {
                    "stage": "compute",
                    "sourceName": "main",
                    "backendName": "source_free_metal_main",
                }
            ],
        )
        self.assertEqual(
            summary["reflectionResources"]["resources"],
            [
                {
                    "stage": "compute",
                    "name": "OutputBuffer",
                    "kind": "storageBuffer",
                    "type": "float4",
                    "set": 0,
                    "binding": 0,
                }
            ],
        )
        self.assertEqual(
            summary["reflectionResources"]["targetResourceBindings"][0],
            {
                "target": "metal",
                "stage": "compute",
                "entryPoint": "source_free_metal_main",
                "name": "OutputBuffer",
                "kind": "storageBuffer",
                "bindingClass": "buffer",
                "descriptorType": "buffer",
                "abi": {"buffer": 0},
            },
        )

    def test_runtime_artifact_selection_supported_target_from_metadata(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory(suffix=".cglb") as temp_dir:
            package_dir = Path(temp_dir)
            self._write_valid_package(package_dir)
            (package_dir / "source").mkdir()
            (package_dir / "source" / "invalid.cgl").write_text(
                "selection must not parse CrossGL source\n",
                encoding="utf-8",
            )

            report = read_compatibility_report(package_dir, loader_target="metal")
            selection = select_runtime_artifact(report, target="metal")
            summary = selection.to_summary()

            self.assertTrue(selection.selected, summary["diagnostics"])
            self.assertFalse(selection.source_parsing_required)
            self.assertEqual(selection.selected_package_mode, "native")
            self.assertEqual(selection.require_selected().name, "nativeBinary")
            self.assertEqual(selection.require_selected().read_bytes(), b"bin")
            self.assertEqual(summary["requestedTarget"], "metal")
            self.assertEqual(summary["requestedPackageMode"], "auto")
            self.assertEqual(summary["artifact"]["name"], "nativeBinary")
            self.assertLegacyRequirementsFallbackOnly(summary["diagnostics"])

    def test_selects_zip_package_artifacts_without_source_parse(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir)
            package_dir = temp_root / "package-dir"
            package_dir.mkdir()
            self._write_valid_package(package_dir)
            (package_dir / "source").mkdir()
            (package_dir / "source" / "invalid.cgl").write_text(
                "loader zip plan must not parse this source\n",
                encoding="utf-8",
            )
            zip_path = temp_root / "RuntimeLoaderFixture.cglb"
            self._write_zip_package(package_dir, zip_path)

            with self._guard_crossgl_source_path_reads():
                with self._guard_crossgl_source_archive_reads():
                    plan = read_loader_plan(zip_path, "metal")
                    summary = plan.to_summary()
                    contract = plan.to_runtime_loader_plan_contract()

            self.assertTrue(plan.loadable, summary["diagnostics"])
            self.assertRuntimeLoaderPlanContractValid(contract)
            self.assertEqual(summary["packageFormat"], "zip")
            self.assertEqual(contract["packageFormat"], "zip")
            self.assertEqual(contract["success"], True)
            self.assertEqual(contract["selectedPackageMode"], "native")
            self.assertEqual(contract["selectedArtifact"]["name"], "nativeBinary")
            self.assertEqual(summary["packageVersion"], 1)
            self.assertEqual(summary["status"], "compatible")
            self.assertEqual(
                [artifact.name for artifact in plan.selected_artifacts],
                ["backendSource", "intermediate", "nativeBinary"],
            )
            self.assertIn(
                "generated Metal source",
                plan.require_artifact("backendSource").read_text(),
            )
            self.assertEqual(plan.require_artifact("nativeBinary").read_bytes(), b"bin")
            self.assertTrue(
                summary["selectedArtifacts"][0]["absolutePath"].startswith(
                    f"{zip_path}!/"
                )
            )
            self.assertEqual(summary["metadataContract"]["sourceInputs"], [])
            self.assertEqual(
                summary["metadataContract"]["metadataDocuments"],
                [
                    {
                        "name": "manifest",
                        "path": "manifest.json",
                        "schemaVersion": 1,
                        "compatible": True,
                    },
                    {
                        "name": "reflection",
                        "path": "reflection.json",
                        "schemaVersion": 1,
                        "compatible": True,
                    },
                    {
                        "name": "diagnostics",
                        "path": "diagnostics.json",
                        "schemaVersion": 1,
                        "compatible": True,
                    },
                ],
            )
            self.assertTrue(
                all(
                    artifact["absolutePath"].startswith(f"{zip_path}!/")
                    for artifact in summary["selectedArtifacts"]
                )
            )

    def test_zip_loader_plan_ignores_source_looking_members_without_source_parse(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir)
            package_dir = temp_root / "package-dir"
            package_dir.mkdir()
            self._write_valid_package(package_dir, target="directx")
            zip_path = temp_root / "RuntimeLoaderFixture.cglb"
            prefix = zip_path.name
            inside_source_member = f"{prefix}/source/not-declared.cgl"
            near_source_member = "near-zip-source.cgl"
            unsafe_members = {
                f"{prefix}/../source/escape.cgl": "shader unsafe_prefix_escape {}\n",
                f"{prefix}/source/../escape.cgl": "shader unsafe_inner_escape {}\n",
                "/absolute-source.cgl": "shader unsafe_absolute {}\n",
                f"{prefix}/backslash\\source.cgl": "shader unsafe_backslash {}\n",
            }
            self._write_zip_package(
                package_dir,
                zip_path,
                prefix=prefix,
                extra_members={
                    inside_source_member: (
                        "shader inside_archive_must_not_be_parsed {}\n"
                    ),
                    near_source_member: "shader near_archive_must_not_be_parsed {}\n",
                    **unsafe_members,
                },
            )
            near_source_path = temp_root / "near-filesystem-source.cgl"
            near_source_path.write_text(
                "shader near_filesystem_must_not_be_parsed {}\n",
                encoding="utf-8",
            )

            with zipfile.ZipFile(zip_path) as archive:
                archive_members = set(archive.namelist())
            expected_unsafe_members = {
                self._zip_writestr_member_name(member) for member in unsafe_members
            }
            self.assertIn(inside_source_member, archive_members)
            self.assertIn(near_source_member, archive_members)
            self.assertTrue(
                expected_unsafe_members.issubset(archive_members),
                {
                    "expected": sorted(expected_unsafe_members),
                    "actual": sorted(archive_members),
                },
            )
            self.assertTrue(near_source_path.is_file())

            with self._guard_crossgl_source_path_reads():
                with self._guard_crossgl_source_archive_reads():
                    plan = read_loader_plan(zip_path, "directx")
                    summary = plan.to_summary()

            self.assertTrue(plan.loadable, summary["diagnostics"])
            self.assertEqual(summary["packageFormat"], "zip")
            self.assertEqual(summary["status"], "source-only")
            self.assertFalse(plan.source_parsing_required)
            self.assertEqual(summary["sourceInputs"], [])
            self.assertEqual(summary["metadataContract"]["sourceInputs"], [])
            self._assert_loader_runtime_artifact_admission_is_shared(summary)
            self.assertEqual(
                summary["runtimeArtifactAdmission"]["decision"],
                "accepted",
            )
            self.assertEqual(
                summary["runtimeArtifactAdmission"]["reason"],
                "runtime.source_package_fallback.accepted",
            )
            self.assertEqual(
                summary["runtimeArtifactPath"],
                "backend/directx/RuntimeLoaderFixture.hlsl",
            )
            self.assertEqual(
                summary["runtimeArtifactSelection"]["artifact"]["path"],
                "backend/directx/RuntimeLoaderFixture.hlsl",
            )
            self.assertEqual(
                [artifact.package_path for artifact in plan.selected_artifacts],
                [
                    "backend/directx/RuntimeLoaderFixture.hlsl",
                    "backend/directx/RuntimeLoaderFixture.dxil",
                ],
            )
            self.assertFalse(
                any(
                    Path(artifact["path"]).suffix == ".cgl"
                    for artifact in summary["compatibilityReport"]["availableArtifacts"]
                )
            )
            self.assertIn(
                "generated directx source",
                plan.require_runtime_artifact().read_text(),
            )

    def test_select_runtime_artifact_zip_requires_declared_backend_source(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir)
            package_dir = temp_root / "package-dir"
            package_dir.mkdir()
            self._write_valid_package(package_dir, target="directx")
            manifest_path = package_dir / "manifest.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            del manifest["artifacts"]["backendSource"]
            self._write_json(manifest_path, manifest)

            zip_path = temp_root / "RuntimeLoaderFixture.cglb"
            prefix = zip_path.name
            undeclared_backend_source = (
                f"{prefix}/backend/directx/RuntimeLoaderFixture.hlsl"
            )
            source_member = f"{prefix}/source/not-declared.cgl"
            self._write_zip_package(
                package_dir,
                zip_path,
                prefix=prefix,
                extra_members={
                    source_member: "shader source_must_not_be_parsed {}\n",
                    f"{prefix}/backend/directx/LooksLikeArtifact.hlsl": (
                        "// filename-only candidate must not be inferred\n"
                    ),
                },
            )

            with zipfile.ZipFile(zip_path) as archive:
                archive_members = set(archive.namelist())
            self.assertIn(undeclared_backend_source, archive_members)
            self.assertIn(source_member, archive_members)

            with self._guard_crossgl_source_archive_reads():
                report = read_compatibility_report(
                    zip_path,
                    loader_target="directx",
                )
                selection = select_runtime_artifact(
                    report,
                    target="directx",
                    package_mode="source-package",
                )
                summary = selection.to_summary()

            self.assertFalse(selection.selected)
            self.assertIsNone(selection.artifact)
            self.assertEqual(summary["artifact"], None)
            self.assertFalse(summary["sourceParsingRequired"])
            self.assertEqual(summary["sourceInputs"], [])
            self.assertNotIn(
                "backendSource",
                [artifact.name for artifact in report.available_artifacts],
            )
            self.assertIn(
                "package.artifact.required_missing",
                [diagnostic.code for diagnostic in selection.reject_reasons],
            )
            admission = summary["admission"]
            self.assertEqual(admission["decision"], "rejected")
            self.assertEqual(admission["target"]["decision"], "accepted")
            self.assertEqual(
                admission["sourcePackageFallback"]["decision"],
                "rejected",
            )
            self.assertTrue(admission["sourcePackageFallback"]["fallbackAttempted"])
            self.assertFalse(admission["sourcePackageFallback"]["artifactDeclared"])
            self.assertFalse(admission["sourcePackageFallback"]["artifactAvailable"])

    def test_rejects_duplicate_zip_members_before_loader_plan(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir)
            package_dir = temp_root / "package-dir"
            package_dir.mkdir()
            self._write_valid_package(package_dir)
            zip_path = temp_root / "RuntimeLoaderFixture.cglb"
            self._write_zip_package(package_dir, zip_path)

            with warnings.catch_warnings():
                warnings.simplefilter("ignore", UserWarning)
                with zipfile.ZipFile(zip_path, "a") as archive:
                    archive.writestr("manifest.json", "{}\n")

            with self.assertRaisesRegex(
                PackageReadError,
                "ambiguous duplicate package archive member: manifest\\.json",
            ):
                read_loader_plan(zip_path, "metal")

    def test_rejects_duplicate_normalized_zip_members_before_loader_plan(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir)
            package_dir = temp_root / "package-dir"
            package_dir.mkdir()
            self._write_valid_package(package_dir)
            zip_path = temp_root / "RuntimeLoaderFixture.cglb"
            prefix = zip_path.name
            self._write_zip_package(package_dir, zip_path, prefix=prefix)

            alias_member = f"{prefix}/backend/metal/./RuntimeLoaderFixture.metallib"
            with zipfile.ZipFile(zip_path, "a") as archive:
                archive.writestr(alias_member, b"ambiguous metallib alias")

            with self.assertRaisesRegex(
                PackageReadError,
                (
                    "ambiguous duplicate package archive member: "
                    "backend/metal/RuntimeLoaderFixture\\.metallib.*"
                    "backend/metal/\\./RuntimeLoaderFixture\\.metallib"
                ),
            ):
                read_loader_plan(zip_path, "metal")

    def test_rejects_duplicate_zip_source_members_before_loader_plan(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir)
            package_dir = temp_root / "package-dir"
            package_dir.mkdir()
            self._write_valid_package(package_dir)
            zip_path = temp_root / "RuntimeLoaderFixture.cglb"
            prefix = zip_path.name
            self._write_zip_package(
                package_dir,
                zip_path,
                prefix=prefix,
                extra_members={
                    f"{prefix}/source/not-declared.cgl": (
                        "shader first_source_member {}\n"
                    ),
                },
            )

            with warnings.catch_warnings():
                warnings.simplefilter("ignore", UserWarning)
                with zipfile.ZipFile(zip_path, "a") as archive:
                    archive.writestr(
                        f"{prefix}/source/not-declared.cgl",
                        "shader duplicate_source_member {}\n",
                    )

            with self._guard_crossgl_source_archive_reads():
                with self.assertRaisesRegex(
                    PackageReadError,
                    "ambiguous duplicate package archive member: "
                    "source/not-declared\\.cgl",
                ):
                    read_loader_plan(zip_path, "metal")

    def test_target_mismatch_is_reported_as_runtime_skip(self) -> None:
        with tempfile.TemporaryDirectory(suffix=".cglb") as temp_dir:
            package_dir = Path(temp_dir)
            self._write_valid_package(package_dir)

            plan = read_loader_plan(package_dir, "vulkan")
            summary = plan.to_summary()

            self.assertFalse(plan.loadable)
            self.assertEqual(summary["selectedTarget"], None)
            self.assertEqual(plan.selected_artifacts, ())
            self.assertEqual(
                [diagnostic.code for diagnostic in plan.skip_reasons],
                ["package.target.loader_mismatch"],
            )
            self.assertEqual(summary["selectedArtifacts"], [])
            self.assertFalse(summary["runtimeArtifactSelection"]["selected"])
            self.assertEqual(
                summary["runtimeArtifactSelection"]["skipReasons"][0]["code"],
                "package.target.loader_mismatch",
            )
            self.assertEqual(
                summary["skipReasons"][0]["message"],
                "package target metal does not match loader target vulkan",
            )
            with self.assertRaisesRegex(
                PackageReadError,
                "runtime loader cannot load package: package target metal",
            ):
                plan.require_loadable()

    def test_native_profile_target_mismatch_rejects_before_dispatch(self) -> None:
        with tempfile.TemporaryDirectory(suffix=".cglb") as temp_dir:
            package_dir = Path(temp_dir)
            self._write_valid_package(package_dir, target="metal")
            profile_path = package_dir / "backend" / "metal" / "native-profile.json"
            self._write_json(profile_path, {"schemaVersion": 1, "target": "metal"})
            manifest_path = package_dir / "manifest.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["artifacts"]["nativeProfile"] = "backend/metal/native-profile.json"
            self._write_json(manifest_path, manifest)

            plan = read_loader_plan(package_dir, "metal")
            summary = plan.to_summary()

            self.assertFalse(plan.loadable)
            self.assertEqual(plan.selected_artifacts, ())
            self.assertIsNone(plan.runtime_artifact)
            self.assertEqual(summary["selectedTarget"], None)
            self.assertEqual(summary["selectedArtifacts"], [])
            self.assertEqual(
                [diagnostic.code for diagnostic in plan.reject_reasons],
                ["package.artifact.target_incompatible"],
            )
            self.assertCompatibilityCodesWithLegacyFallback(
                summary,
                ["package.artifact.target_incompatible"],
            )
            self.assertEqual(
                summary["loaderDiagnostics"]["selection"]["codes"],
                [],
            )
            self.assertEqual(
                summary["compatibilityReport"]["artifactCompatibility"]["rejected"][0][
                    "name"
                ],
                "nativeProfile",
            )
            self.assertEqual(
                summary["compatibilityReport"]["artifactCompatibility"]["rejected"][0][
                    "reason"
                ],
                "package.artifact.target_incompatible",
            )
            self.assertEqual(
                summary["runtimeArtifactSelection"]["artifact"],
                None,
            )

    def test_vulkan_native_profile_artifact_mismatch_rejects_before_dispatch(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory(suffix=".cglb") as temp_dir:
            package_dir = Path(temp_dir)
            self._write_valid_package(package_dir, target="vulkan")
            manifest_path = package_dir / "manifest.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            artifacts = manifest["artifacts"]
            assembly_path = "backend/vulkan/RuntimeLoaderFixture.spvasm"
            profile_path = "backend/vulkan/native-profile.json"
            (package_dir / assembly_path).write_bytes(b"spvasm")
            artifacts["backendAssembly"] = assembly_path
            artifacts["nativeProfile"] = profile_path
            self._write_json(manifest_path, manifest)
            self._write_json(
                package_dir / profile_path,
                {
                    "schemaVersion": 1,
                    "target": "vulkan",
                    "backendAssembly": assembly_path,
                    "nativeBinary": "backend/vulkan/stale.spv",
                },
            )
            source_path = package_dir / "source" / "invalid.cgl"
            source_path.parent.mkdir()
            source_path.write_text(
                "runtime loader must not parse source to repair stale "
                "native profile metadata\n",
                encoding="utf-8",
            )

            with self._guard_crossgl_source_path_reads():
                plan = read_loader_plan(package_dir, "vulkan")

            summary = plan.to_summary()
            expected_code = "package.native_profile.native_binary_mismatch"

            self.assertFalse(plan.loadable)
            self.assertEqual(plan.selected_artifacts, ())
            self.assertIsNone(plan.runtime_artifact)
            self.assertFalse(plan.source_parsing_required)
            self.assertEqual(summary["metadataContract"]["sourceInputs"], [])
            self.assertEqual(summary["selectedTarget"], None)
            self.assertEqual(summary["selectedArtifacts"], [])
            self.assertEqual(
                [diagnostic.code for diagnostic in plan.reject_reasons],
                [expected_code],
            )
            self.assertCompatibilityCodesWithLegacyFallback(
                summary,
                [expected_code],
            )
            self.assertEqual(
                summary["loaderDiagnostics"]["selection"]["codes"],
                [],
            )
            self.assertEqual(
                summary["runtimeArtifactAdmission"]["nativeArtifact"]["reason"],
                expected_code,
            )
            profile_record = next(
                artifact
                for artifact in summary["artifactCompatibility"]["artifacts"]
                if artifact["name"] == "nativeProfile"
            )
            self.assertEqual(profile_record["decision"], "rejected")
            self.assertEqual(profile_record["reason"], expected_code)
            self.assertEqual(
                profile_record["diagnostics"][0]["expected"],
                artifacts["nativeBinary"],
            )
            self.assertEqual(
                profile_record["diagnostics"][0]["actual"],
                "backend/vulkan/stale.spv",
            )
            self.assertEqual(list(package_dir.rglob("*.cgl")), [source_path])

    def test_crossgl_source_artifact_leakage_rejects_before_dispatch(self) -> None:
        with tempfile.TemporaryDirectory(suffix=".cglb") as temp_dir:
            package_dir = Path(temp_dir)
            self._write_valid_package(package_dir, target="directx")
            source_path = package_dir / "source" / "RuntimeLoaderFixture.cgl"
            source_path.parent.mkdir()
            source_path.write_text(
                "loader plans must not dispatch CrossGL source inputs\n",
                encoding="utf-8",
            )
            manifest_path = package_dir / "manifest.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["artifacts"]["backendSource"] = "source/RuntimeLoaderFixture.cgl"
            self._write_json(manifest_path, manifest)

            plan = read_loader_plan(package_dir, "directx")
            summary = plan.to_summary()

            self.assertFalse(plan.loadable)
            self.assertFalse(plan.source_parsing_required)
            self.assertEqual(plan.selected_artifacts, ())
            self.assertIsNone(plan.runtime_artifact)
            self.assertEqual(summary["selectedTarget"], None)
            self.assertEqual(summary["selectedArtifacts"], [])
            self.assertEqual(summary["metadataContract"]["sourceInputs"], [])
            self.assertEqual(
                [diagnostic.code for diagnostic in plan.reject_reasons],
                ["package.artifact.source_input_leakage"],
            )
            self.assertCompatibilityCodesWithLegacyFallback(
                summary,
                ["package.artifact.source_input_leakage"],
            )
            self.assertEqual(
                summary["loaderDiagnostics"]["selection"]["codes"],
                [],
            )
            self.assertEqual(
                summary["compatibilityReport"]["artifactCompatibility"]["rejected"][0][
                    "name"
                ],
                "backendSource",
            )
            self.assertEqual(
                summary["compatibilityReport"]["artifactCompatibility"]["rejected"][0][
                    "reason"
                ],
                "package.artifact.source_input_leakage",
            )
            self.assertEqual(
                summary["runtimeArtifactSelection"]["artifact"],
                None,
            )
            self.assertEqual(
                list(package_dir.rglob("*.cgl")),
                [source_path],
            )

    def test_stale_reflection_target_binding_rejects_loader_plan(self) -> None:
        with tempfile.TemporaryDirectory(suffix=".cglb") as temp_dir:
            package_dir = Path(temp_dir)
            self._write_valid_package(package_dir, target="directx")
            (package_dir / "source").mkdir()
            (package_dir / "source" / "invalid.cgl").write_text(
                "runtime loader must not parse stale package source\n",
                encoding="utf-8",
            )
            reflection_path = package_dir / "reflection.json"
            reflection = json.loads(reflection_path.read_text(encoding="utf-8"))
            reflection["targetResourceBindings"][0]["target"] = "metal"
            self._write_json(reflection_path, reflection)

            plan = read_loader_plan(package_dir, "directx")
            summary = plan.to_summary()

            self.assertFalse(plan.loadable)
            self.assertEqual(plan.selected_artifacts, ())
            self.assertEqual(summary["selectedTarget"], None)
            self.assertFalse(plan.source_parsing_required)
            self.assertEqual(
                [diagnostic.code for diagnostic in plan.reject_reasons],
                ["package.reflection.target_resource_binding_target_mismatch"],
            )
            self.assertEqual(summary["selectedArtifacts"], [])
            self.assertEqual(summary["availableTargets"], ["directx"])
            self.assertEqual(
                summary["targetAvailability"]["targetResourceBindingTargets"],
                [],
            )
            self.assertEqual(
                summary["targetAvailability"]["targetFeatureTargets"],
                ["directx"],
            )
            self.assertEqual(
                summary["runtimeArtifactAdmission"]["targetCompatibility"]["category"],
                "target-unavailable",
            )
            self.assertEqual(
                summary["rejectReasons"][0],
                {
                    "severity": "error",
                    "code": (
                        "package.reflection.target_resource_binding_target_mismatch"
                    ),
                    "message": (
                        "reflection.targetResourceBindings target does not match "
                        "manifest.target"
                    ),
                    "document": "reflection",
                    "path": "targetResourceBindings[0].target",
                    "expected": "directx",
                    "actual": "metal",
                },
            )
            with self.assertRaisesRegex(
                PackageReadError,
                "reflection.targetResourceBindings target does not match",
            ):
                plan.require_loadable()

    def test_loader_plan_rejects_native_binary_metadata_disagreement_without_source_parse(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory(suffix=".cglb") as temp_dir:
            package_dir = Path(temp_dir)
            self._write_valid_package(package_dir, target="metal")
            source_path = package_dir / "source" / "invalid.cgl"
            source_path.parent.mkdir()
            source_path.write_text(
                "runtime loader must not parse source to reconcile stale "
                "native binary metadata\n",
                encoding="utf-8",
            )

            manifest_path = package_dir / "manifest.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            artifacts = manifest["artifacts"]
            native_binary_path = artifacts["nativeBinary"]
            backend_source_path = artifacts["backendSource"]
            descriptor_path = "metadata/native-artifact.json"
            artifacts["nativeArtifactDescriptor"] = descriptor_path
            self._write_json(manifest_path, manifest)

            native_binary_file = package_dir / native_binary_path
            backend_source_file = package_dir / backend_source_path
            descriptor_file = package_dir / descriptor_path
            descriptor_file.parent.mkdir()
            self._write_json(
                descriptor_file,
                {
                    "schemaVersion": 1,
                    "kind": "crossgl.nativeArtifact",
                    "contractVersion": "native-artifact-v0",
                    "target": "metal",
                    "binaryKind": "metal.metallib",
                    "artifactPath": "backend/metal/stale.metallib",
                    "artifactHash": {
                        "algorithm": "sha256",
                        "value": hashlib.sha256(
                            native_binary_file.read_bytes()
                        ).hexdigest(),
                    },
                    "sizeBytes": native_binary_file.stat().st_size,
                    "sourcePath": backend_source_path,
                    "sourceHash": {
                        "algorithm": "sha256",
                        "value": hashlib.sha256(
                            backend_source_file.read_bytes()
                        ).hexdigest(),
                    },
                    "toolchainProvenance": {
                        "producer": "runtime loader fixture",
                        "tools": [],
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
                },
            )

            reflection_path = package_dir / "reflection.json"
            reflection = json.loads(reflection_path.read_text(encoding="utf-8"))
            reflection["nativeBinary"] = "backend/metal/stale.metallib"
            self._write_json(reflection_path, reflection)

            with self._guard_crossgl_source_path_reads():
                plan = read_loader_plan(package_dir, "metal")

            summary = plan.to_summary()
            reject_codes = [diagnostic.code for diagnostic in plan.reject_reasons]

            self.assertFalse(plan.loadable)
            self.assertEqual(plan.selected_artifacts, ())
            self.assertIsNone(plan.runtime_artifact)
            self.assertFalse(plan.source_parsing_required)
            self.assertEqual(summary["metadataContract"]["sourceInputs"], [])
            self.assertIn("package.reflection.native_binary_mismatch", reject_codes)
            self.assertIn(
                "package.native_artifact_descriptor.artifact_path_mismatch",
                reject_codes,
            )
            self.assertNotIn("package.target.unsupported", reject_codes)
            self.assertEqual(summary["selectedArtifacts"], [])
            self.assertEqual(summary["runtimeArtifactSelection"]["artifact"], None)
            self.assertEqual(list(package_dir.rglob("*.cgl")), [source_path])

    def test_malformed_reflection_target_binding_shape_rejects_loader_plan(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory(suffix=".cglb") as temp_dir:
            package_dir = Path(temp_dir)
            self._write_valid_package(package_dir, target="directx")
            (package_dir / "source").mkdir()
            (package_dir / "source" / "invalid.cgl").write_text(
                "runtime loader must not infer bindings from source\n",
                encoding="utf-8",
            )
            reflection_path = package_dir / "reflection.json"
            reflection = json.loads(reflection_path.read_text(encoding="utf-8"))
            reflection["targetResourceBindings"] = {"target": "directx"}
            self._write_json(reflection_path, reflection)

            plan = read_loader_plan(package_dir, "directx")
            summary = plan.to_summary()

            self.assertFalse(plan.loadable)
            self.assertEqual(plan.selected_artifacts, ())
            self.assertEqual(summary["selectedTarget"], None)
            self.assertFalse(plan.source_parsing_required)
            self.assertEqual(
                [diagnostic.code for diagnostic in plan.reject_reasons],
                ["package.reflection.target_resource_bindings_invalid"],
            )
            self.assertEqual(summary["selectedArtifacts"], [])
            self.assertEqual(
                summary["rejectReasons"][0],
                {
                    "severity": "error",
                    "code": "package.reflection.target_resource_bindings_invalid",
                    "message": ("reflection.targetResourceBindings must be an array"),
                    "document": "reflection",
                    "path": "targetResourceBindings",
                    "expected": "array",
                    "actual": "object",
                },
            )
            self.assertEqual(
                list(package_dir.rglob("*.cgl")),
                [package_dir / "source" / "invalid.cgl"],
            )
            with self.assertRaisesRegex(
                PackageReadError,
                "reflection.targetResourceBindings must be an array",
            ):
                plan.require_loadable()

    def test_missing_required_artifact_rejects_plan_with_diagnostics(self) -> None:
        with tempfile.TemporaryDirectory(suffix=".cglb") as temp_dir:
            package_dir = Path(temp_dir)
            self._write_valid_package(package_dir)
            (package_dir / "backend" / "metal" / "RuntimeLoaderFixture.metal").unlink()

            plan = read_loader_plan(package_dir, "metal")
            summary = plan.to_summary()

            self.assertFalse(plan.loadable)
            self.assertEqual(plan.selected_artifacts, ())
            self.assertEqual(summary["selectedTarget"], None)
            self.assertEqual(
                summary["requiredArtifactPaths"]["backendSource"],
                "backend/metal/RuntimeLoaderFixture.metal",
            )
            self.assertEqual(
                summary["requiredArtifactPaths"]["nativeBinary"],
                "backend/metal/RuntimeLoaderFixture.metallib",
            )
            self.assertEqual(summary["runtimeArtifactPath"], None)
            self.assertEqual(
                [diagnostic.code for diagnostic in plan.reject_reasons],
                ["package.artifact.required_file_missing"],
            )
            self.assertEqual(
                summary["artifactRoleCompatibility"]["blockedByDiagnostics"][0]["code"],
                "package.artifact.required_file_missing",
            )
            self.assertEqual(
                [
                    (role["role"], role["status"], role["compatible"])
                    for role in summary["artifactRoleCompatibility"]["roles"]
                ],
                [
                    ("backendSource", "blocked", False),
                    ("intermediate", "blocked", False),
                    ("nativeBinary", "blocked", False),
                ],
            )
            self.assertEqual(
                summary["missingArtifacts"][0]["path"],
                "backend/metal/RuntimeLoaderFixture.metal",
            )
            with self.assertRaisesRegex(
                PackageReadError,
                "required artifact backendSource is declared but missing on disk",
            ):
                plan.require_loadable()

    def test_missing_required_artifact_metadata_rejects_plan_with_path_gap(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory(suffix=".cglb") as temp_dir:
            package_dir = Path(temp_dir)
            self._write_valid_package(package_dir, target="directx")
            manifest_path = package_dir / "manifest.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            del manifest["artifacts"]["nativeBinary"]
            self._write_json(manifest_path, manifest)

            plan = read_loader_plan(package_dir, "directx")
            summary = plan.to_summary()

            self.assertFalse(plan.loadable)
            self.assertEqual(summary["selectedTarget"], None)
            self.assertEqual(summary["runtimeArtifactPath"], None)
            self.assertEqual(
                summary["requiredArtifactPaths"],
                {
                    "backendSource": "backend/directx/RuntimeLoaderFixture.hlsl",
                    "nativeBinary": None,
                },
            )
            self.assertEqual(summary["selectedArtifacts"], [])
            self.assertIn(
                "package.artifact.required_missing",
                [diagnostic.code for diagnostic in plan.reject_reasons],
            )
            self.assertEqual(
                summary["missingArtifacts"][0]["artifact"],
                "nativeBinary",
            )

    def test_loader_plan_reports_malformed_metadata_without_source_parse(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory(suffix=".cglb") as temp_dir:
            package_dir = Path(temp_dir)
            self._write_valid_package(package_dir)
            (package_dir / "diagnostics.json").write_text(
                "{not-json}\n",
                encoding="utf-8",
            )
            (package_dir / "source").mkdir()
            (package_dir / "source" / "invalid.cgl").write_text(
                "runtime loader must not parse package source\n",
                encoding="utf-8",
            )

            plan = read_loader_plan(package_dir, "metal")
            summary = plan.to_summary()

            self.assertFalse(plan.loadable)
            self.assertEqual(plan.selected_artifacts, ())
            self.assertFalse(plan.source_parsing_required)
            self.assertIn(
                "package.metadata.invalid",
                [diagnostic.code for diagnostic in plan.reject_reasons],
            )
            self.assertEqual(
                summary["rejectReasons"][0],
                {
                    "severity": "error",
                    "code": "package.metadata.invalid",
                    "message": "invalid JSON in diagnostics.json: "
                    "Expecting property name enclosed in double quotes",
                    "document": "diagnostics",
                    "expected": "JSON object metadata file",
                    "actual": "invalid",
                },
            )
            self.assertEqual(
                summary["compatibilityReport"]["sourceParsingRequired"],
                False,
            )
            with self.assertRaisesRegex(
                PackageReadError,
                "invalid JSON in diagnostics.json",
            ):
                plan.require_loadable()

    def test_loader_plan_reports_missing_manifest_target_as_target_unavailable(
        self,
    ) -> None:
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
                "runtime loader must not infer missing target metadata from source\n",
                encoding="utf-8",
            )

            with self._guard_crossgl_source_path_reads():
                plan = read_loader_plan(package_dir, "metal")

            summary = plan.to_summary()
            target_admission = summary["runtimeArtifactAdmission"][
                "targetCompatibility"
            ]

            self.assertFalse(plan.loadable)
            self.assertEqual(plan.selected_artifacts, ())
            self.assertIsNone(plan.runtime_artifact)
            self.assertFalse(plan.source_parsing_required)
            self.assertEqual(
                [diagnostic.code for diagnostic in plan.reject_reasons],
                ["package.identity.target_missing"],
            )
            self.assertEqual(target_admission["decision"], "rejected")
            self.assertEqual(target_admission["category"], "target-unavailable")
            self.assertEqual(
                target_admission["diagnostics"],
                [
                    {
                        "severity": "error",
                        "code": "package.identity.target_missing",
                        "message": "manifest.target must be a non-empty string",
                        "document": "manifest",
                        "expected": "non-empty string",
                        "actual": "missing",
                    }
                ],
            )
            self.assertEqual(
                summary["targetCompatibility"]["category"],
                "target-unavailable",
            )
            self.assertEqual(
                summary["artifactSelection"]["reason"],
                "package.identity.target_missing",
            )
            self.assertEqual(summary["metadataContract"]["sourceInputs"], [])
            self.assertEqual(list(package_dir.rglob("*.cgl")), [source_path])

    def test_loader_plan_rejects_malformed_diagnostics_records_without_source_parse(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory(suffix=".cglb") as temp_dir:
            package_dir = Path(temp_dir)
            self._write_valid_package(package_dir)
            diagnostics_path = package_dir / "diagnostics.json"
            diagnostics = json.loads(diagnostics_path.read_text(encoding="utf-8"))
            diagnostics["diagnostics"] = {"severity": "error"}
            self._write_json(diagnostics_path, diagnostics)
            source_path = package_dir / "source" / "invalid.cgl"
            source_path.parent.mkdir()
            source_path.write_text(
                "runtime loader must not infer diagnostics metadata from source\n",
                encoding="utf-8",
            )

            with self._guard_crossgl_source_path_reads():
                plan = read_loader_plan(package_dir, "metal")

            summary = plan.to_summary()

            self.assertFalse(plan.loadable)
            self.assertEqual(plan.selected_artifacts, ())
            self.assertIsNone(plan.runtime_artifact)
            self.assertFalse(plan.source_parsing_required)
            self.assertIn(
                "package.diagnostics.records_invalid",
                [diagnostic.code for diagnostic in plan.reject_reasons],
            )
            self.assertEqual(
                summary["compatibilityReport"]["diagnosticsMetadata"][
                    "recordShapeValid"
                ],
                False,
            )
            self.assertEqual(
                summary["compatibilityReport"]["diagnosticsMetadata"]["valid"],
                False,
            )
            self.assertCompatibilityCodesWithLegacyFallback(
                summary,
                ["package.diagnostics.records_invalid"],
            )
            self.assertFalse(summary["metadataContract"]["sourceParsingRequired"])
            self.assertFalse(summary["metadataContract"]["compilerInvocationRequired"])
            self.assertFalse(summary["metadataContract"]["deviceExecutionRequired"])
            self.assertEqual(summary["metadataContract"]["sourceInputs"], [])
            self.assertEqual(list(package_dir.rglob("*.cgl")), [source_path])

    def test_loader_plan_rejects_future_debug_metadata_schema(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory(suffix=".cglb") as temp_dir:
            package_dir = Path(temp_dir)
            self._write_valid_package(package_dir)
            manifest_path = package_dir / "manifest.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            (package_dir / "ir").mkdir()
            debug_path = package_dir / "ir" / "debug-metadata.json"
            self._write_json(
                debug_path,
                {
                    "schemaVersion": 12,
                    "targetDecision": {
                        "requestedTarget": "metal",
                        "selectedTarget": "metal",
                        "selectedTargetPackageMode": "native",
                    },
                },
            )
            manifest["artifacts"]["debugMetadata"] = "ir/debug-metadata.json"
            self._write_json(manifest_path, manifest)
            (package_dir / "source").mkdir()
            (package_dir / "source" / "invalid.cgl").write_text(
                "loader must not parse source for debug metadata fallback\n",
                encoding="utf-8",
            )

            plan = read_loader_plan(package_dir, "metal")
            summary = plan.to_summary()

            self.assertFalse(plan.loadable)
            self.assertEqual(summary["status"], "unsupported-version")
            self.assertFalse(plan.source_parsing_required)
            self.assertEqual(plan.selected_artifacts, ())
            self.assertEqual(
                [diagnostic.code for diagnostic in plan.reject_reasons],
                ["package.debug_metadata.schema_incompatible"],
            )
            self.assertCompatibilityCodesWithLegacyFallback(
                summary,
                ["package.debug_metadata.schema_incompatible"],
            )
            self.assertEqual(
                summary["loaderDiagnostics"]["selection"]["codes"],
                [],
            )
            self.assertEqual(
                summary["compatibilityReport"]["debugMetadata"]["record"][
                    "schemaVersion"
                ],
                12,
            )
            self.assertEqual(
                list(package_dir.rglob("*.cgl")),
                [package_dir / "source" / "invalid.cgl"],
            )

    def test_source_package_plan_allows_planned_native_absence(self) -> None:
        with tempfile.TemporaryDirectory(suffix=".cglb") as temp_dir:
            package_dir = Path(temp_dir)
            self._write_valid_package(package_dir, target="directx")
            (package_dir / "backend" / "directx" / "RuntimeLoaderFixture.dxil").unlink()
            (package_dir / "source").mkdir()
            (package_dir / "source" / "invalid.cgl").write_text(
                "planned native classification must not parse source\n",
                encoding="utf-8",
            )

            plan = read_loader_plan(package_dir, "directx")
            summary = plan.to_summary()

            self.assertTrue(plan.loadable, summary["diagnostics"])
            self.assertIs(plan.require_loadable(), plan)
            self.assertFalse(plan.source_parsing_required)
            self.assertEqual(
                [artifact.name for artifact in plan.selected_artifacts],
                ["backendSource", "nativeBinary"],
            )
            self.assertTrue(plan.require_artifact("backendSource").exists)
            self.assertFalse(plan.require_artifact("nativeBinary").exists)
            self.assertIsNone(plan.require_artifact("nativeBinary").size)
            self.assertEqual(summary["status"], "source-only")
            self.assertEqual(summary["missingArtifacts"], [])
            self.assertEqual(
                summary["artifactAvailability"]["native"]["nativeBinaryStatus"],
                "planned",
            )
            self.assertEqual(
                summary["artifactAvailability"]["native"]["artifact"]["path"],
                "backend/directx/RuntimeLoaderFixture.dxil",
            )
            self.assertFalse(summary["artifactAvailability"]["native"]["exists"])
            self.assertFalse(summary["artifactAvailability"]["native"]["usable"])
            self.assertTrue(summary["artifactAvailability"]["source"]["available"])
            self.assertEqual(summary["diagnosticSummary"]["status"], "source-only")
            self.assertEqual(summary["diagnosticSummary"]["rejectCount"], 0)
            self.assertEqual(summary["selectedArtifacts"][1]["exists"], False)
            self.assertEqual(plan.require_runtime_artifact().name, "backendSource")
            self.assertEqual(
                [
                    (
                        role["role"],
                        role["status"],
                        role["exists"],
                        role["compatible"],
                        role["bytesRequired"],
                    )
                    for role in summary["artifactRoleCompatibility"]["roles"]
                ],
                [
                    (
                        "backendSource",
                        "selected-runtime-artifact",
                        True,
                        True,
                        True,
                    ),
                    ("nativeBinary", "planned-evidence", False, True, False),
                ],
            )

    def test_runtime_artifact_selection_reports_malformed_artifact_metadata(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory(suffix=".cglb") as temp_dir:
            package_dir = Path(temp_dir)
            self._write_valid_package(package_dir, target="directx")
            manifest_path = package_dir / "manifest.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["artifacts"]["backendSource"] = {
                "path": "backend/directx/RuntimeLoaderFixture.hlsl"
            }
            self._write_json(manifest_path, manifest)

            report = read_compatibility_report(package_dir, loader_target="directx")
            selection = select_runtime_artifact(
                report,
                target="directx",
                package_mode="source-package",
            )
            summary = selection.to_summary()

            self.assertFalse(selection.selected)
            self.assertEqual(selection.artifact, None)
            self.assertIn(
                "package.artifact.path_invalid",
                [diagnostic.code for diagnostic in selection.reject_reasons],
            )
            self.assertIn(
                "package.artifact.required_missing",
                [diagnostic.code for diagnostic in selection.reject_reasons],
            )
            self.assertEqual(summary["artifact"], None)
            self.assertFalse(summary["sourceParsingRequired"])

    def test_loader_plan_rejects_malformed_native_binary_status_as_contract_invalid(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory(suffix=".cglb") as temp_dir:
            package_dir = Path(temp_dir)
            self._write_valid_package(package_dir, target="directx")
            manifest_path = package_dir / "manifest.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["artifacts"]["nativeBinaryStatus"] = {"status": "planned"}
            self._write_json(manifest_path, manifest)
            source_path = package_dir / "source" / "invalid.cgl"
            source_path.parent.mkdir()
            source_path.write_text(
                "loader must not infer malformed native status from source\n",
                encoding="utf-8",
            )

            with self._guard_crossgl_source_path_reads():
                plan = read_loader_plan(package_dir, "directx")

            summary = plan.to_summary()
            reject_codes = [diagnostic.code for diagnostic in plan.reject_reasons]

            self.assertFalse(plan.loadable)
            self.assertEqual(plan.selected_artifacts, ())
            self.assertIsNone(plan.runtime_artifact)
            self.assertFalse(plan.source_parsing_required)
            self.assertEqual(summary["sourceInputs"], [])
            self.assertFalse(summary["compilerInvocationRequired"])
            self.assertFalse(summary["deviceExecutionRequired"])
            self.assertEqual(summary["metadataContract"]["sourceInputs"], [])
            self.assertFalse(summary["metadataContract"]["compilerInvocationRequired"])
            self.assertFalse(summary["metadataContract"]["deviceExecutionRequired"])
            self.assertIn("package.native_binary_status.invalid", reject_codes)
            self.assertIn("package.artifacts.contract_invalid", reject_codes)
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
            self.assertIsNone(summary["runtimeArtifactSelection"]["artifact"])
            self.assertEqual(
                summary["runtimeArtifactSelection"]["sourceInputs"],
                [],
            )
            self.assertFalse(
                summary["runtimeArtifactSelection"]["compilerInvocationRequired"]
            )
            self.assertFalse(
                summary["runtimeArtifactSelection"]["deviceExecutionRequired"]
            )
            self.assertEqual(list(package_dir.rglob("*.cgl")), [source_path])

    def test_loader_plan_rejects_unexpected_artifact_metadata(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory(suffix=".cglb") as temp_dir:
            package_dir = Path(temp_dir)
            self._write_valid_package(package_dir)
            manifest_path = package_dir / "manifest.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["artifacts"]["shaderBlob"] = (
                "backend/metal/RuntimeLoaderFixture.metallib"
            )
            self._write_json(manifest_path, manifest)
            (package_dir / "source").mkdir()
            (package_dir / "source" / "invalid.cgl").write_text(
                "loader must not inspect source for future artifact metadata\n",
                encoding="utf-8",
            )

            plan = read_loader_plan(package_dir, "metal")
            summary = plan.to_summary()

            self.assertFalse(plan.loadable)
            self.assertEqual(plan.selected_artifacts, ())
            self.assertIsNone(plan.runtime_artifact)
            self.assertFalse(plan.source_parsing_required)
            self.assertIn(
                "package.artifact.unexpected",
                [diagnostic.code for diagnostic in plan.reject_reasons],
            )
            self.assertCompatibilityCodesWithLegacyFallback(
                summary,
                [
                    "package.artifact.unexpected",
                    "package.artifacts.contract_invalid",
                ],
            )
            contract_reject = next(
                diagnostic
                for diagnostic in summary["rejectReasons"]
                if diagnostic["code"] == "package.artifacts.contract_invalid"
            )
            self.assertEqual(
                [diagnostic["code"] for diagnostic in contract_reject["actual"]],
                ["package.artifact.unexpected"],
            )
            self.assertEqual(
                summary["compatibilityReport"]["rejectReasons"][0]["artifact"],
                "shaderBlob",
            )
            self.assertEqual(
                list(package_dir.rglob("*.cgl")),
                [package_dir / "source" / "invalid.cgl"],
            )

    def test_loader_plan_rejects_duplicate_artifact_path_aliases(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory(suffix=".cglb") as temp_dir:
            package_dir = Path(temp_dir)
            self._write_valid_package(package_dir)
            manifest_path = package_dir / "manifest.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["artifacts"]["intermediate"] = manifest["artifacts"][
                "backendSource"
            ]
            self._write_json(manifest_path, manifest)
            (package_dir / "source").mkdir()
            (package_dir / "source" / "invalid.cgl").write_text(
                "loader must not infer artifact roles from package source\n",
                encoding="utf-8",
            )

            plan = read_loader_plan(package_dir, "metal")
            summary = plan.to_summary()

            self.assertFalse(plan.loadable)
            self.assertEqual(plan.selected_artifacts, ())
            self.assertIsNone(plan.runtime_artifact)
            self.assertFalse(plan.source_parsing_required)
            self.assertEqual(
                [diagnostic.code for diagnostic in plan.reject_reasons],
                [
                    "package.artifact.path_duplicate",
                    "package.artifacts.contract_invalid",
                ],
            )
            self.assertCompatibilityCodesWithLegacyFallback(
                summary,
                [
                    "package.artifact.path_duplicate",
                    "package.artifacts.contract_invalid",
                ],
            )
            self.assertEqual(summary["loaderDiagnostics"]["selection"]["codes"], [])
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
                summary["compatibilityReport"]["rejectReasons"][0],
                {
                    "severity": "error",
                    "code": "package.artifact.path_duplicate",
                    "message": (
                        "manifest.artifacts.intermediate reuses path declared by "
                        "backendSource: backend/metal/RuntimeLoaderFixture.metal"
                    ),
                    "document": "manifest",
                    "artifact": "intermediate",
                    "path": "artifacts.intermediate",
                    "expected": "unique package-relative path",
                    "actual": "backend/metal/RuntimeLoaderFixture.metal",
                },
            )
            self.assertEqual(
                list(package_dir.rglob("*.cgl")),
                [package_dir / "source" / "invalid.cgl"],
            )

    def test_loader_plan_rejects_non_normalized_artifact_paths(
        self,
    ) -> None:
        cases = (
            ("directory", "backend/metal/./RuntimeLoaderFixture.metal"),
            ("zip", "backend/metal//RuntimeLoaderFixture.metal"),
        )
        for package_format, artifact_path in cases:
            with self.subTest(
                package_format=package_format, artifact_path=artifact_path
            ):
                with tempfile.TemporaryDirectory(suffix=".cglb") as temp_dir:
                    package_dir = Path(temp_dir) / "package"
                    package_dir.mkdir()
                    self._write_valid_package(package_dir)
                    manifest_path = package_dir / "manifest.json"
                    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
                    manifest["artifacts"]["backendSource"] = artifact_path
                    self._write_json(manifest_path, manifest)
                    source_path = package_dir / "source" / "invalid.cgl"
                    source_path.parent.mkdir()
                    source_path.write_text(
                        "loader must reject malformed artifact paths from metadata\n",
                        encoding="utf-8",
                    )

                    if package_format == "zip":
                        zip_path = Path(temp_dir) / "package.cglb"
                        self._write_zip_package(
                            package_dir,
                            zip_path,
                            prefix=zip_path.name,
                        )
                        with self._guard_crossgl_source_archive_reads():
                            plan = read_loader_plan(zip_path, "metal")
                    else:
                        with self._guard_crossgl_source_path_reads():
                            plan = read_loader_plan(package_dir, "metal")

                    summary = plan.to_summary()
                    reject_codes = [
                        diagnostic.code for diagnostic in plan.reject_reasons
                    ]

                    self.assertFalse(plan.loadable)
                    self.assertEqual(plan.selected_artifacts, ())
                    self.assertIsNone(plan.runtime_artifact)
                    self.assertFalse(plan.source_parsing_required)
                    self.assertIn("package.artifact.path_invalid", reject_codes)
                    self.assertIn("package.artifacts.contract_invalid", reject_codes)
                    self.assertIsNone(summary["runtimeArtifactSelection"]["artifact"])
                    path_reject = next(
                        diagnostic
                        for diagnostic in summary["compatibilityReport"][
                            "rejectReasons"
                        ]
                        if diagnostic["code"] == "package.artifact.path_invalid"
                    )
                    self.assertEqual(path_reject["path"], "artifacts.backendSource")
                    self.assertEqual(path_reject["actual"], artifact_path)
                    self.assertIn(
                        "must be a normalized package-relative path",
                        path_reject["message"],
                    )
                    contract_reject = next(
                        diagnostic
                        for diagnostic in summary["rejectReasons"]
                        if diagnostic["code"] == "package.artifacts.contract_invalid"
                    )
                    self.assertEqual(
                        [
                            diagnostic["code"]
                            for diagnostic in contract_reject["actual"]
                        ],
                        ["package.artifact.path_invalid"],
                    )
                    self.assertEqual(list(package_dir.rglob("*.cgl")), [source_path])

    def test_runtime_artifact_selection_respects_source_package_and_native_modes(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory(suffix=".cglb") as temp_dir:
            package_dir = Path(temp_dir)
            self._write_valid_package(
                package_dir,
                target="directx",
                native_status="emitted",
                native_artifact_descriptor=True,
            )

            report = read_compatibility_report(package_dir, loader_target="directx")
            auto_selection = select_runtime_artifact(report, target="directx")
            source_selection = select_runtime_artifact(
                report,
                target="directx",
                package_mode="source-package",
            )
            native_selection = select_runtime_artifact(
                report,
                target="directx",
                package_mode="native",
            )

            self.assertTrue(auto_selection.selected)
            self.assertTrue(source_selection.selected)
            self.assertTrue(native_selection.selected)
            self.assertEqual(auto_selection.selected_package_mode, "native")
            self.assertEqual(auto_selection.require_selected().name, "nativeBinary")
            self.assertEqual(
                source_selection.selected_package_mode,
                "source-package",
            )
            self.assertEqual(source_selection.require_selected().name, "backendSource")
            self.assertEqual(native_selection.selected_package_mode, "native")
            self.assertEqual(native_selection.require_selected().name, "nativeBinary")

            auto_plan_summary = read_loader_plan(package_dir, "directx").to_summary()
            source_plan_summary = read_loader_plan(
                package_dir,
                "directx",
                package_mode="source-package",
            ).to_summary()
            native_plan_summary = read_loader_plan(
                package_dir,
                "directx",
                package_mode="native",
            ).to_summary()
            source_alias_summary = read_loader_plan(
                package_dir,
                "directx",
                package_mode="source",
            ).to_summary()

            self.assertEqual(
                auto_plan_summary["artifactSelection"]["supportedModes"],
                ["auto", "native", "source-package"],
            )
            self.assertEqual(
                auto_plan_summary["artifactSelection"]["requestedMode"],
                "auto",
            )
            self.assertEqual(
                auto_plan_summary["artifactSelection"]["selectedMode"],
                "native",
            )
            self.assertEqual(
                source_plan_summary["artifactSelection"]["requestedMode"],
                "source-package",
            )
            self.assertEqual(
                source_plan_summary["artifactSelection"]["selectedMode"],
                "source-package",
            )
            self.assertEqual(
                native_plan_summary["artifactSelection"]["requestedMode"],
                "native",
            )
            self.assertEqual(
                native_plan_summary["artifactSelection"]["selectedMode"],
                "native",
            )
            self.assertEqual(
                source_alias_summary["artifactSelection"]["requestedMode"],
                "source-package",
            )
            self.assertEqual(
                source_alias_summary["artifactSelection"]["selectedMode"],
                "source-package",
            )

    def test_loader_summaries_expose_runtime_artifact_admission(self) -> None:
        metal_path = "backend/metal/RuntimeLoaderFixture.metallib"
        directx_source = "backend/directx/RuntimeLoaderFixture.hlsl"
        directx_native = "backend/directx/RuntimeLoaderFixture.dxil"

        with self.subTest("native accepted"):
            with tempfile.TemporaryDirectory(suffix=".cglb") as temp_dir:
                package_dir = Path(temp_dir)
                self._write_valid_package(package_dir)

                summary = read_loader_plan(package_dir, "metal").to_summary()
                admission = summary["runtimeArtifactAdmission"]

                self._assert_loader_runtime_artifact_admission_is_shared(summary)
                self.assertEqual(admission["decision"], "accepted")
                self.assertEqual(
                    admission["reason"],
                    "runtime.native_artifact.accepted",
                )
                self.assertEqual(admission["runtimeArtifact"]["name"], "nativeBinary")
                self.assertEqual(admission["runtimeArtifact"]["path"], metal_path)
                self.assertEqual(admission["nativeArtifact"]["decision"], "accepted")
                self.assertEqual(admission["nativeArtifact"]["selected"], True)
                self.assertEqual(
                    admission["nativeArtifact"]["artifact"]["name"],
                    "nativeBinary",
                )
                self.assertEqual(
                    admission["nativeArtifact"]["artifact"]["path"],
                    metal_path,
                )
                self.assertEqual(
                    admission["sourcePackageFallback"]["decision"],
                    "skipped",
                )
                self.assertEqual(
                    admission["sourcePackageFallback"]["reason"],
                    "runtime.source_package_fallback.not_allowed",
                )

        with self.subTest("source package fallback accepted"):
            with tempfile.TemporaryDirectory(suffix=".cglb") as temp_dir:
                package_dir = Path(temp_dir)
                self._write_valid_package(package_dir, target="directx")

                summary = read_loader_plan(package_dir, "directx").to_summary()
                admission = summary["runtimeArtifactAdmission"]

                self._assert_loader_runtime_artifact_admission_is_shared(summary)
                self.assertEqual(admission["decision"], "accepted")
                self.assertEqual(
                    admission["reason"],
                    "runtime.source_package_fallback.accepted",
                )
                self.assertEqual(admission["runtimeArtifact"]["name"], "backendSource")
                self.assertEqual(admission["runtimeArtifact"]["path"], directx_source)
                self.assertEqual(admission["nativeArtifact"]["decision"], "skipped")
                self.assertEqual(
                    admission["nativeArtifact"]["reason"],
                    "runtime.native_artifact.source_package_fallback",
                )
                self.assertEqual(admission["nativeArtifact"]["selected"], False)
                self.assertEqual(
                    admission["nativeArtifact"]["artifact"]["path"],
                    directx_native,
                )
                self.assertEqual(
                    admission["sourcePackageFallback"]["decision"],
                    "accepted",
                )
                self.assertEqual(
                    admission["sourcePackageFallback"]["artifact"]["path"],
                    directx_source,
                )
                self.assertFalse(
                    admission["sourcePackageFallback"]["sourceParsingRequired"]
                )

        with self.subTest("source package fallback not requested when native required"):
            with tempfile.TemporaryDirectory(suffix=".cglb") as temp_dir:
                package_dir = Path(temp_dir)
                self._write_valid_package(package_dir, target="directx")

                summary = read_loader_plan(
                    package_dir,
                    "directx",
                    package_mode="native",
                ).to_summary()
                admission = summary["runtimeArtifactAdmission"]

                self._assert_loader_runtime_artifact_admission_is_shared(summary)
                self.assertFalse(summary["loadable"])
                self.assertEqual(admission["decision"], "rejected")
                self.assertEqual(
                    admission["reason"],
                    "package.native_binary_status.not_ready",
                )
                self.assertIsNone(admission["runtimeArtifact"])
                self.assertEqual(admission["nativeArtifact"]["decision"], "skipped")
                self.assertEqual(
                    admission["nativeArtifact"]["artifact"]["path"],
                    directx_native,
                )
                self.assertEqual(
                    admission["sourcePackageFallback"]["decision"],
                    "skipped",
                )
                self.assertEqual(
                    admission["sourcePackageFallback"]["reason"],
                    "runtime.source_package_fallback.not_requested",
                )

        with self.subTest("source package fallback rejected"):
            with tempfile.TemporaryDirectory(suffix=".cglb") as temp_dir:
                package_dir = Path(temp_dir)
                self._write_valid_package(package_dir, target="directx")
                (
                    package_dir / "backend" / "directx" / "RuntimeLoaderFixture.hlsl"
                ).unlink()

                summary = read_loader_plan(package_dir, "directx").to_summary()
                admission = summary["runtimeArtifactAdmission"]

                self._assert_loader_runtime_artifact_admission_is_shared(summary)
                self.assertFalse(summary["loadable"])
                self.assertEqual(admission["decision"], "rejected")
                self.assertEqual(
                    admission["reason"],
                    "package.artifact.required_file_missing",
                )
                self.assertIsNone(admission["runtimeArtifact"])
                self.assertEqual(admission["status"], "missing-artifact")
                self.assertEqual(
                    admission["sourcePackageFallback"]["decision"],
                    "rejected",
                )
                self.assertEqual(
                    admission["sourcePackageFallback"]["reason"],
                    "runtime.source_package_fallback.unavailable",
                )
                self.assertEqual(
                    admission["sourcePackageFallback"]["artifact"]["path"],
                    directx_source,
                )
                self.assertFalse(
                    admission["sourcePackageFallback"]["artifact"]["exists"]
                )

    def test_loader_plan_separates_selection_diagnostics_from_compatibility(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory(suffix=".cglb") as temp_dir:
            package_dir = Path(temp_dir)
            self._write_valid_package(package_dir, target="directx")

            plan = read_loader_plan(
                package_dir,
                "directx",
                package_mode="native",
            )
            summary = plan.to_summary()
            contract = plan.to_runtime_loader_plan_contract()

            self.assertFalse(plan.loadable)
            self.assertRuntimeLoaderPlanContractValid(contract)
            self.assertEqual(contract["success"], False)
            self.assertEqual(contract["requestedPackageMode"], "native")
            self.assertIsNone(contract["selectedPackageMode"])
            self.assertIsNone(contract["selectedArtifact"])
            self.assertNotIn(
                "skip",
                [diagnostic["severity"] for diagnostic in contract["diagnostics"]],
            )
            self.assertIn(
                "package.runtime-plan.native-artifact-unavailable",
                [diagnostic["code"] for diagnostic in contract["diagnostics"]],
            )
            self.assertNotIn(
                "package.native_binary_status.not_ready",
                [diagnostic["code"] for diagnostic in contract["diagnostics"]],
            )
            self.assertTrue(plan.compatibility_report.compatible)
            self.assertEqual(summary["status"], "source-only")
            self.assertCompatibilityCodesWithLegacyFallback(summary, [])
            self.assertEqual(
                summary["loaderDiagnostics"]["selection"]["codes"],
                ["package.native_binary_status.not_ready"],
            )
            self.assertEqual(
                summary["loaderDiagnostics"]["selection"]["bySeverity"],
                {"error": 1},
            )
            self.assertEqual(
                [diagnostic["code"] for diagnostic in summary["diagnostics"]],
                [
                    LEGACY_REQUIREMENTS_FALLBACK_CODE,
                    "package.native_binary_status.not_ready",
                ],
            )

    def test_runtime_loader_plan_contract_normalizes_target_mismatch(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory(suffix=".cglb") as temp_dir:
            package_dir = Path(temp_dir)
            self._write_valid_package(package_dir, target="directx")

            plan = read_loader_plan(package_dir, "vulkan")
            contract = plan.to_runtime_loader_plan_contract()

            self.assertFalse(plan.loadable)
            self.assertRuntimeLoaderPlanContractValid(contract)
            self.assertEqual(contract["success"], False)
            self.assertEqual(contract["packageTarget"], "directx")
            self.assertEqual(contract["requestedLoaderTarget"], "vulkan")
            self.assertEqual(contract["targetMatchesPackage"], False)
            self.assertEqual(contract["selectedArtifact"], None)
            self.assertEqual(contract["diagnosticCounts"]["error"], 1)
            mismatch_diagnostic = next(
                diagnostic
                for diagnostic in contract["diagnostics"]
                if diagnostic["code"] == "package.runtime-plan.target-mismatch"
            )
            self.assertEqual(
                mismatch_diagnostic["severity"],
                "error",
            )
            self.assertNotIn(
                "package.target.loader_mismatch",
                [diagnostic["code"] for diagnostic in contract["diagnostics"]],
            )

    def test_runtime_loader_plan_contract_normalizes_source_artifact_unavailable(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory(suffix=".cglb") as temp_dir:
            package_dir = Path(temp_dir)
            self._write_valid_package(package_dir, target="directx")
            (package_dir / "backend/directx/RuntimeLoaderFixture.hlsl").unlink()

            plan = read_loader_plan(
                package_dir,
                "directx",
                package_mode="source-package",
            )
            contract = plan.to_runtime_loader_plan_contract()

            self.assertFalse(plan.loadable)
            self.assertRuntimeLoaderPlanContractValid(contract)
            self.assertEqual(contract["success"], False)
            self.assertEqual(contract["requestedPackageMode"], "source-package")
            self.assertIsNone(contract["selectedArtifact"])
            self.assertIn(
                "package.runtime-plan.source-artifact-unavailable",
                [diagnostic["code"] for diagnostic in contract["diagnostics"]],
            )
            self.assertNotIn(
                "package.artifact.required_file_missing",
                [diagnostic["code"] for diagnostic in contract["diagnostics"]],
            )

    def test_unsupported_package_target_rejects_without_loader_policy(self) -> None:
        with tempfile.TemporaryDirectory(suffix=".cglb") as temp_dir:
            package_dir = Path(temp_dir)
            self._write_valid_package(package_dir, target="webgpu")

            plan = read_loader_plan(package_dir, "webgpu")

            self.assertFalse(plan.loadable)
            self.assertEqual(plan.required_artifacts, ())
            self.assertEqual(plan.selected_artifacts, ())
            self.assertEqual(
                [diagnostic.code for diagnostic in plan.reject_reasons],
                ["package.target.unsupported"],
            )

    def test_runtime_admission_summary_fields_are_stable(self) -> None:
        metal_paths = {
            "backendSource": "backend/metal/RuntimeLoaderFixture.metal",
            "intermediate": "backend/metal/RuntimeLoaderFixture.air",
            "nativeBinary": "backend/metal/RuntimeLoaderFixture.metallib",
        }
        directx_paths = {
            "backendSource": "backend/directx/RuntimeLoaderFixture.hlsl",
            "nativeBinary": "backend/directx/RuntimeLoaderFixture.dxil",
        }

        with self.subTest("compatible native"):
            with tempfile.TemporaryDirectory(suffix=".cglb") as temp_dir:
                package_dir = Path(temp_dir)
                self._write_valid_package(package_dir)

                summary = read_loader_plan(package_dir, "metal").to_summary()

                self._assert_runtime_admission_summary(
                    summary,
                    expected_status="compatible",
                    expected_selected_artifacts=[
                        (
                            "backendSource",
                            "backend/metal/RuntimeLoaderFixture.metal",
                            True,
                        ),
                        (
                            "intermediate",
                            "backend/metal/RuntimeLoaderFixture.air",
                            True,
                        ),
                        (
                            "nativeBinary",
                            "backend/metal/RuntimeLoaderFixture.metallib",
                            True,
                        ),
                    ],
                    expected_required_artifact_paths=metal_paths,
                    expected_runtime_artifact="nativeBinary",
                    expected_artifact_decisions=[
                        (
                            "backendSource",
                            "accepted",
                            "package.artifact.accepted",
                            False,
                        ),
                        (
                            "intermediate",
                            "accepted",
                            "package.artifact.accepted",
                            False,
                        ),
                        (
                            "nativeBinary",
                            "accepted",
                            "package.artifact.selected",
                            True,
                        ),
                    ],
                )

        with self.subTest("compatible source-package"):
            with tempfile.TemporaryDirectory(suffix=".cglb") as temp_dir:
                package_dir = Path(temp_dir)
                self._write_valid_package(package_dir, target="directx")

                summary = read_loader_plan(package_dir, "directx").to_summary()

                self._assert_runtime_admission_summary(
                    summary,
                    expected_status="source-only",
                    expected_selected_artifacts=[
                        (
                            "backendSource",
                            "backend/directx/RuntimeLoaderFixture.hlsl",
                            True,
                        ),
                        (
                            "nativeBinary",
                            "backend/directx/RuntimeLoaderFixture.dxil",
                            True,
                        ),
                    ],
                    expected_required_artifact_paths=directx_paths,
                    expected_runtime_artifact="backendSource",
                    expected_artifact_decisions=[
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

        with self.subTest("target mismatch"):
            with tempfile.TemporaryDirectory(suffix=".cglb") as temp_dir:
                package_dir = Path(temp_dir)
                self._write_valid_package(package_dir)

                summary = read_loader_plan(package_dir, "vulkan").to_summary()

                self._assert_runtime_admission_summary(
                    summary,
                    expected_status="target-mismatch",
                    expected_selected_artifacts=[],
                    expected_required_artifact_paths=metal_paths,
                    expected_runtime_artifact=None,
                    expected_artifact_decisions=[
                        (
                            "backendSource",
                            "skipped",
                            "package.target.loader_mismatch",
                            False,
                        ),
                        (
                            "intermediate",
                            "skipped",
                            "package.target.loader_mismatch",
                            False,
                        ),
                        (
                            "nativeBinary",
                            "skipped",
                            "package.target.loader_mismatch",
                            False,
                        ),
                    ],
                )

        with self.subTest("missing artifact"):
            with tempfile.TemporaryDirectory(suffix=".cglb") as temp_dir:
                package_dir = Path(temp_dir)
                self._write_valid_package(package_dir)
                (
                    package_dir / "backend" / "metal" / "RuntimeLoaderFixture.metal"
                ).unlink()

                summary = read_loader_plan(package_dir, "metal").to_summary()

                self._assert_runtime_admission_summary(
                    summary,
                    expected_status="missing-artifact",
                    expected_selected_artifacts=[],
                    expected_required_artifact_paths=metal_paths,
                    expected_runtime_artifact=None,
                    expected_artifact_decisions=[
                        (
                            "backendSource",
                            "rejected",
                            "package.artifact.required_file_missing",
                            False,
                        ),
                        (
                            "intermediate",
                            "accepted",
                            "package.artifact.accepted",
                            False,
                        ),
                        (
                            "nativeBinary",
                            "accepted",
                            "package.artifact.accepted",
                            False,
                        ),
                    ],
                )

        with self.subTest("unsupported schema"):
            with tempfile.TemporaryDirectory(suffix=".cglb") as temp_dir:
                package_dir = Path(temp_dir)
                self._write_valid_package(package_dir)
                manifest_path = package_dir / "manifest.json"
                manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
                manifest["schemaVersion"] = 2
                self._write_json(manifest_path, manifest)

                summary = read_loader_plan(package_dir, "metal").to_summary()

                self._assert_runtime_admission_summary(
                    summary,
                    expected_status="unsupported-version",
                    expected_selected_artifacts=[],
                    expected_required_artifact_paths=metal_paths,
                    expected_runtime_artifact=None,
                    expected_artifact_decisions=[
                        (
                            "backendSource",
                            "rejected",
                            "package.schema.incompatible",
                            False,
                        ),
                        (
                            "intermediate",
                            "rejected",
                            "package.schema.incompatible",
                            False,
                        ),
                        (
                            "nativeBinary",
                            "rejected",
                            "package.schema.incompatible",
                            False,
                        ),
                    ],
                )

        with self.subTest("malformed artifact requirements"):
            with tempfile.TemporaryDirectory(suffix=".cglb") as temp_dir:
                package_dir = Path(temp_dir)
                self._write_valid_package(
                    package_dir,
                    package_artifact_requirements={
                        "target": "metal",
                        "packageMode": "source-package",
                        "requiredPathArtifacts": ["nativeBinary"],
                        "requiresNativeBinaryStatus": False,
                        "allowsPlannedNativeBinary": False,
                        "allowsPlannedNativeSourceEvidence": False,
                    },
                )

                summary = read_loader_plan(package_dir, "metal").to_summary()

                self._assert_runtime_admission_summary(
                    summary,
                    expected_status="incompatible",
                    expected_selected_artifacts=[],
                    expected_required_artifact_paths={},
                    expected_runtime_artifact=None,
                    expected_artifact_decisions=[
                        (
                            "backendSource",
                            "rejected",
                            (
                                "package.artifact_requirements."
                                "source_package_artifact_missing"
                            ),
                            False,
                        ),
                        (
                            "intermediate",
                            "rejected",
                            (
                                "package.artifact_requirements."
                                "source_package_artifact_missing"
                            ),
                            False,
                        ),
                        (
                            "nativeBinary",
                            "rejected",
                            (
                                "package.artifact_requirements."
                                "source_package_artifact_missing"
                            ),
                            False,
                        ),
                    ],
                )

    def test_loader_target_must_be_explicit(self) -> None:
        with tempfile.TemporaryDirectory(suffix=".cglb") as temp_dir:
            with self.assertRaisesRegex(
                PackageReadError, "loader_target must be a non-empty string"
            ):
                read_loader_plan(Path(temp_dir), "")

    def _assert_runtime_admission_summary(
        self,
        summary: dict[str, object],
        *,
        expected_status: str,
        expected_selected_artifacts: list[tuple[str, str, bool]],
        expected_required_artifact_paths: dict[str, str | None],
        expected_runtime_artifact: str | None,
        expected_artifact_decisions: list[tuple[str, str, str, bool]],
    ) -> None:
        for field in (
            "sourceParsingRequired",
            "compilerInvocationRequired",
            "deviceExecutionRequired",
            "sourceInputs",
            "metadataContract",
            "selectedArtifacts",
            "requiredArtifactPaths",
            "artifactCompatibility",
            "runtimeArtifactAdmission",
            "packageArtifactRequirementsSource",
            "packageArtifactRequirements",
            "targetLegalizationEvidence",
            "versionCompatibility",
            "requiredMetadataInputs",
            "targetCompatibility",
            "artifactSelection",
            "targetLegalizationToolRequirements",
        ):
            self.assertIn(field, summary)

        self.assertEqual(summary["status"], expected_status)
        self.assertEqual(summary["sourceParsingRequired"], False)
        self.assertEqual(summary["compilerInvocationRequired"], False)
        self.assertEqual(summary["deviceExecutionRequired"], False)
        self.assertEqual(summary["sourceInputs"], [])
        self.assertEqual(
            summary["requiredArtifactPaths"],
            expected_required_artifact_paths,
        )
        self.assertEqual(
            [
                (artifact["name"], artifact["path"], artifact["exists"])
                for artifact in summary["selectedArtifacts"]
            ],
            expected_selected_artifacts,
        )

        metadata_contract = summary["metadataContract"]
        version_compatibility = summary["versionCompatibility"]
        required_metadata_inputs = summary["requiredMetadataInputs"]
        target_compatibility = summary["targetCompatibility"]
        artifact_selection = summary["artifactSelection"]
        self.assertEqual(metadata_contract["schemaVersion"], 1)
        self.assertEqual(metadata_contract["metadataOnly"], True)
        self.assertEqual(metadata_contract["sourceParsingRequired"], False)
        self.assertEqual(metadata_contract["compilerInvocationRequired"], False)
        self.assertEqual(metadata_contract["deviceExecutionRequired"], False)
        self.assertEqual(metadata_contract["sourceInputs"], [])
        self.assertEqual(metadata_contract["loadable"], summary["loadable"])
        self.assertEqual(metadata_contract["status"], summary["status"])
        self.assertEqual(metadata_contract["packageTarget"], summary["packageTarget"])
        self.assertEqual(metadata_contract["loaderTarget"], summary["loaderTarget"])
        self.assertEqual(
            summary["packageArtifactRequirements"],
            summary["compatibilityReport"]["admission"]["requirements"],
        )
        self.assertEqual(
            metadata_contract["packageArtifactRequirementsSource"],
            summary["packageArtifactRequirementsSource"],
        )
        self.assertEqual(
            metadata_contract["packageArtifactRequirements"],
            summary["packageArtifactRequirements"],
        )
        self.assertEqual(
            metadata_contract["contractSource"],
            summary["packageArtifactRequirementsSource"],
        )
        self.assertEqual(
            metadata_contract["requirements"],
            summary["packageArtifactRequirements"],
        )
        self.assertEqual(
            summary["targetLegalizationEvidence"],
            summary["compatibilityReport"]["targetLegalizationEvidence"],
        )
        self.assertEqual(
            metadata_contract["targetLegalizationEvidence"],
            summary["targetLegalizationEvidence"],
        )
        self.assertEqual(
            summary["targetLegalizationToolRequirements"],
            summary["targetLegalizationEvidence"]["manifestToolRequirements"],
        )
        self.assertEqual(
            summary["targetLegalizationToolRequirements"],
            summary["compatibilityReport"]["targetLegalizationToolRequirements"],
        )
        self.assertEqual(
            metadata_contract["targetLegalizationToolRequirements"],
            summary["targetLegalizationToolRequirements"],
        )
        self.assertEqual(
            metadata_contract["versionCompatibility"],
            version_compatibility,
        )
        self.assertEqual(
            metadata_contract["requiredMetadataInputs"],
            required_metadata_inputs,
        )
        self.assertEqual(
            metadata_contract["targetCompatibility"],
            target_compatibility,
        )
        self.assertEqual(
            metadata_contract["artifactSelection"],
            artifact_selection,
        )
        self.assertEqual(
            summary["loaderDiagnostics"]["versionCompatibility"],
            version_compatibility,
        )
        self.assertEqual(
            summary["loaderDiagnostics"]["targetCompatibility"],
            target_compatibility,
        )
        self.assertEqual(
            summary["loaderDiagnostics"]["artifactSelection"],
            artifact_selection,
        )
        self.assertEqual(
            [
                (
                    metadata_input["name"],
                    metadata_input["path"],
                    metadata_input["required"],
                    metadata_input["declaredBy"],
                )
                for metadata_input in required_metadata_inputs
            ],
            [
                ("manifest", "manifest.json", True, "package-root"),
                ("reflection", "reflection.json", True, "package-root"),
                ("diagnostics", "diagnostics.json", True, "package-root"),
            ],
        )
        self.assertEqual(
            [
                metadata_input["supportedSchemaVersion"]
                for metadata_input in required_metadata_inputs
            ],
            [1, 1, 1],
        )
        self.assertEqual(version_compatibility["schemaVersion"], 1)
        self.assertEqual(version_compatibility["metadataOnly"], True)
        self.assertEqual(version_compatibility["sourceParsingRequired"], False)
        self.assertEqual(version_compatibility["planStatus"], summary["status"])
        self.assertEqual(
            version_compatibility["compatible"],
            version_compatibility["diagnosticCount"] == 0,
        )
        self.assertEqual(
            version_compatibility["diagnosticCodes"],
            [diagnostic["code"] for diagnostic in version_compatibility["diagnostics"]],
        )
        self.assertEqual(
            version_compatibility["compiler"]["name"],
            summary["compatibilityReport"]["compiler"]["name"],
        )
        self.assertEqual(
            version_compatibility["compiler"]["version"],
            summary["compatibilityReport"]["compiler"]["version"],
        )
        self.assertEqual(
            version_compatibility["compiler"]["expectedName"],
            "CrossGL-Compiler",
        )
        self.assertEqual(
            version_compatibility["schemas"]["manifest"]["version"],
            summary["packageVersion"],
        )
        self.assertEqual(
            version_compatibility["schemas"]["manifest"]["supportedVersion"],
            1,
        )
        self.assertEqual(target_compatibility["schemaVersion"], 1)
        self.assertEqual(target_compatibility["metadataOnly"], True)
        self.assertEqual(target_compatibility["sourceParsingRequired"], False)
        self.assertEqual(target_compatibility["compilerInvocationRequired"], False)
        self.assertEqual(target_compatibility["deviceExecutionRequired"], False)
        self.assertEqual(target_compatibility["loaderTarget"], summary["loaderTarget"])
        self.assertEqual(
            target_compatibility["requestedTarget"],
            summary["loaderTarget"],
        )
        self.assertEqual(
            target_compatibility["packageTarget"],
            summary["packageTarget"],
        )
        self.assertEqual(
            target_compatibility["diagnosticCodes"],
            [diagnostic["code"] for diagnostic in target_compatibility["diagnostics"]],
        )
        self.assertEqual(artifact_selection["schemaVersion"], 1)
        self.assertEqual(artifact_selection["metadataOnly"], True)
        self.assertEqual(artifact_selection["sourceParsingRequired"], False)
        self.assertEqual(artifact_selection["compilerInvocationRequired"], False)
        self.assertEqual(artifact_selection["deviceExecutionRequired"], False)
        self.assertEqual(artifact_selection["sourceInputs"], [])
        self.assertEqual(
            artifact_selection["supportedModes"],
            ["auto", "native", "source-package"],
        )
        self.assertEqual(
            artifact_selection["requestedMode"],
            artifact_selection["requestedPackageMode"],
        )
        self.assertEqual(
            artifact_selection["selectedMode"],
            artifact_selection["selectedPackageMode"],
        )
        self.assertEqual(
            artifact_selection["selected"],
            summary["runtimeArtifactSelection"]["selected"],
        )
        self.assertEqual(
            artifact_selection["diagnosticCodes"],
            [diagnostic["code"] for diagnostic in artifact_selection["diagnostics"]],
        )
        self.assertEqual(
            [
                (artifact["name"], artifact["path"], artifact["exists"])
                for artifact in artifact_selection["selectedArtifacts"]
            ],
            expected_selected_artifacts,
        )
        if expected_runtime_artifact is None:
            self.assertIsNone(artifact_selection["runtimeArtifact"])
        else:
            self.assertEqual(
                artifact_selection["runtimeArtifact"]["name"],
                expected_runtime_artifact,
            )
        self._assert_loader_runtime_artifact_admission_is_shared(summary)
        self.assertEqual(
            [
                (artifact["name"], artifact["path"], artifact["declaredBy"])
                for artifact in metadata_contract["requiredArtifactInputs"]
            ],
            [
                (
                    name,
                    path,
                    f"manifest.artifacts.{name}" if path is not None else None,
                )
                for name, path in expected_required_artifact_paths.items()
            ],
        )
        self.assertEqual(
            [
                (
                    artifact["name"],
                    artifact["path"],
                    artifact["exists"],
                    artifact["selectedForLoad"],
                )
                for artifact in metadata_contract["selectedArtifactInputs"]
            ],
            [
                (name, path, exists, name == expected_runtime_artifact)
                for name, path, exists in expected_selected_artifacts
            ],
        )
        if expected_runtime_artifact is None:
            self.assertIsNone(metadata_contract["runtimeArtifact"])
        else:
            self.assertEqual(
                metadata_contract["runtimeArtifact"]["name"],
                expected_runtime_artifact,
            )

        artifact_compatibility = summary["artifactCompatibility"]
        self.assertEqual(artifact_compatibility["schemaVersion"], 1)
        self.assertEqual(
            artifact_compatibility["loaderTarget"],
            summary["loaderTarget"],
        )
        self.assertEqual(
            artifact_compatibility["packageTarget"],
            summary["packageTarget"],
        )
        self.assertEqual(
            artifact_compatibility["selectedArtifact"],
            expected_runtime_artifact,
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
            expected_artifact_decisions,
        )
        self.assertEqual(
            summary["compatibilityReport"]["sourceParsingRequired"],
            False,
        )
        self.assertEqual(
            summary["compatibilityReport"]["artifactCompatibility"]["schemaVersion"],
            1,
        )
        self.assertEqual(
            summary["compatibilityReport"]["artifactCompatibility"]["selectedArtifact"],
            expected_runtime_artifact,
        )

    def _assert_loader_runtime_artifact_admission_is_shared(
        self,
        summary: dict[str, object],
    ) -> None:
        admission = summary["runtimeArtifactAdmission"]
        metadata_contract = summary["metadataContract"]
        loader_diagnostics = summary["loaderDiagnostics"]
        self.assertEqual(
            metadata_contract["runtimeArtifactAdmission"],
            admission,
        )
        self.assertEqual(
            loader_diagnostics["runtimeArtifactAdmission"],
            admission,
        )
        self.assertEqual(admission["schemaVersion"], 1)
        self.assertEqual(admission["metadataOnly"], True)
        self.assertEqual(admission["sourceParsingRequired"], False)
        self.assertEqual(admission["compilerInvocationRequired"], False)
        self.assertEqual(admission["deviceExecutionRequired"], False)
        self.assertEqual(admission["loaderTarget"], summary["loaderTarget"])
        self.assertEqual(admission["packageTarget"], summary["packageTarget"])
        self.assertEqual(admission["loadable"], summary["loadable"])
        self.assertEqual(admission["status"], summary["status"])
        self.assertEqual(
            admission["packageArtifactRequirementsSource"],
            summary["packageArtifactRequirementsSource"],
        )
        self.assertEqual(
            admission["packageArtifactRequirements"],
            summary["packageArtifactRequirements"],
        )
        self.assertIn(
            admission["decision"],
            {"accepted", "rejected", "skipped", "unavailable"},
        )
        self.assertIsInstance(admission["reason"], str)
        self.assertEqual(
            admission["targetCompatibility"]["requestedTarget"],
            summary["loaderTarget"],
        )
        self.assertEqual(
            summary["targetCompatibility"]["decision"],
            admission["targetCompatibility"]["decision"],
        )
        self.assertEqual(
            summary["targetCompatibility"]["category"],
            admission["targetCompatibility"]["category"],
        )
        self.assertEqual(
            summary["targetCompatibility"]["diagnostics"],
            admission["targetCompatibility"]["diagnostics"],
        )
        self.assertEqual(
            admission["targetCompatibility"]["packageTarget"],
            summary["packageTarget"],
        )
        self.assertIn("decision", admission["nativeArtifact"])
        self.assertIn("reason", admission["nativeArtifact"])
        self.assertIn("artifact", admission["nativeArtifact"])
        self.assertIn("decision", admission["sourcePackageFallback"])
        self.assertIn("reason", admission["sourcePackageFallback"])
        self.assertIn("artifact", admission["sourcePackageFallback"])

    def _write_valid_package(
        self,
        package_dir: Path,
        *,
        target: str = "metal",
        native_status: str | None = None,
        package_artifact_requirements: dict[str, object] | None = None,
        native_artifact_descriptor: bool = False,
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
        source_path = f"backend/{target}/RuntimeLoaderFixture.{source_extension}"
        binary_path = f"backend/{target}/RuntimeLoaderFixture.{binary_extension}"

        (backend_dir / f"RuntimeLoaderFixture.{source_extension}").write_text(
            f"// generated {source_label} source\n",
            encoding="utf-8",
        )
        (backend_dir / f"RuntimeLoaderFixture.{binary_extension}").write_bytes(b"bin")

        artifacts = {
            "backendSource": source_path,
            "nativeBinary": binary_path,
        }
        if target == "metal":
            (backend_dir / "RuntimeLoaderFixture.air").write_bytes(b"air")
            artifacts["intermediate"] = "backend/metal/RuntimeLoaderFixture.air"
        if target in {"directx", "opengl"} and native_status is None:
            native_status = "planned"
        if native_status is not None:
            artifacts["nativeBinaryStatus"] = native_status
        descriptor_path = "metadata/native-artifact.json"
        if native_artifact_descriptor:
            artifacts["nativeArtifactDescriptor"] = descriptor_path

        manifest: dict[str, object] = {
            "schemaVersion": 1,
            "compiler": {
                "name": "CrossGL-Compiler",
                "version": "test",
                "llvmVersion": "not-found",
            },
            "module": "RuntimeLoaderFixture",
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
        if native_artifact_descriptor:
            self._write_native_artifact_descriptor(
                package_dir,
                descriptor_path=descriptor_path,
                target=target,
                source_path=source_path,
                binary_path=binary_path,
                native_status=native_status,
            )
        self._write_json(
            package_dir / "reflection.json",
            {
                "schemaVersion": 1,
                "module": "RuntimeLoaderFixture",
                "target": target,
                "nativeBinary": binary_path,
                "entryPoints": [
                    {
                        "stage": "compute",
                        "sourceName": "main",
                        "backendName": "runtime_loader_main",
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
                        "entryPoint": "runtime_loader_main",
                        "name": "OutputBuffer",
                        "kind": "storageBuffer",
                        "sourceType": "float4",
                        "addressSpace": "storage",
                        "abi": self._target_resource_binding_abi(target),
                        "bindingClass": "uav",
                        "descriptorType": "UAV",
                        "hlslType": "RWStructuredBuffer<float4>",
                        "evidenceId": (
                            f"target-legalization.v1.{target}.resource-binding."
                            "compute.runtime_loader_main.OutputBuffer"
                        ),
                    }
                ],
                "targetFeatures": [
                    {
                        "target": target,
                        "kind": "package",
                        "name": "fixture",
                        "evidenceIds": [
                            f"target-legalization.v1.{target}.capability.required."
                            f"{target}.package.fixture"
                        ],
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
        descriptor_path: str,
        target: str,
        source_path: str,
        binary_path: str,
        native_status: str | None,
    ) -> None:
        source_file = package_dir / source_path
        binary_file = package_dir / binary_path
        binary_kind = {
            "directx": "directx.dxil",
            "metal": "metal.metallib",
            "opengl": "opengl.source",
        }.get(target, f"{target}.native")
        descriptor_file = package_dir / descriptor_path
        descriptor_file.parent.mkdir(parents=True, exist_ok=True)
        descriptor = {
            "schemaVersion": 1,
            "kind": "crossgl.nativeArtifact",
            "contractVersion": "native-artifact-v0",
            "target": target,
            "binaryKind": binary_kind,
            "sourcePath": source_path,
            "sourceHash": {
                "algorithm": "sha256",
                "value": hashlib.sha256(source_file.read_bytes()).hexdigest(),
            },
            "artifactPath": binary_path,
            "artifactHash": {
                "algorithm": "sha256",
                "value": hashlib.sha256(binary_file.read_bytes()).hexdigest(),
            },
            "sizeBytes": binary_file.stat().st_size,
            "toolchainProvenance": {
                "producer": "runtime loader fixture",
                "tools": [],
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
        self._write_json(descriptor_file, descriptor)

    def _write_crosstl_runtime_adapter_package(
        self,
        package_dir: Path,
        *,
        target: str,
        artifact_format: str,
        package_path: str,
    ) -> None:
        descriptor_path = f"adapters/{target}/runtime-loader-fixture.adapter.json"
        descriptor_file = package_dir / descriptor_path
        descriptor_file.parent.mkdir(parents=True, exist_ok=True)
        adapter_id = f"{target}.runtime-loader-fixture"
        adapter_kind = f"{target}-runtime-loader-adapter"
        descriptor = {
            "schemaVersion": 1,
            "kind": "crosstl-runtime-adapter-descriptor",
            "sourcePackage": str(package_dir / "runtime-package.json"),
            "sourcePackageHash": {"algorithm": "sha256", "value": "1" * 64},
            "packageRoot": str(package_dir),
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
            "sourcePath": "source/RuntimeLoaderFixture.cgl",
            "sourceBackend": "crossgl",
            "stage": "compute",
            "variant": "debug",
            "defines": {"TEST_FIXTURE": "1"},
            "sourceRemap": {
                "packagePath": "source-remaps/RuntimeLoaderFixture.source-remap.json"
            },
            "hostInterface": {
                "status": "ready",
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
                        "name": "OutputBuffer",
                        "kind": "storageBuffer",
                        "type": "RWStructuredBuffer<float4>",
                        "set": 0,
                        "binding": 0,
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
            "validation": {"loadReady": True},
        }
        self._write_json(descriptor_file, descriptor)
        descriptor_bytes = descriptor_file.read_bytes()
        descriptor_record = {
            "id": adapter_id,
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
            "hostInterfaceStatus": "ready",
            "requiredTools": descriptor["requiredTools"],
        }
        self._write_json(
            package_dir / "runtime-adapters.json",
            {
                "schemaVersion": 1,
                "kind": "crosstl-runtime-adapter-package",
                "sourcePackage": str(package_dir / "runtime-package.json"),
                "sourcePackageHash": {"algorithm": "sha256", "value": "1" * 64},
                "generatedAt": 1,
                "success": True,
                "scope": "runtime-adapter-descriptor-package",
                "nonGoals": ["host-code-rewriting"],
                "packageRoot": str(package_dir),
                "adapterRoot": str(package_dir),
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
                        "descriptors": [adapter_id],
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
            },
        )

    @staticmethod
    def _target_resource_binding_abi(target: str) -> dict[str, object]:
        if target == "directx":
            return {"space": 0, "register": "u0"}
        if target == "metal":
            return {"buffer": 0}
        if target == "opengl":
            return {"program": 0, "binding": 0}
        return {"set": 0, "binding": 0}

    def _write_json(self, path: Path, document: object) -> None:
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

    @staticmethod
    def _zip_writestr_member_name(member: str) -> str:
        return zipfile.ZipInfo(member).filename

    def _guard_crossgl_source_path_reads(self) -> object:
        original_open = Path.open
        original_read_text = Path.read_text
        original_read_bytes = Path.read_bytes

        def is_crossgl_source_path(path: Path) -> bool:
            return path.suffix.lower() == ".cgl"

        def guarded_open(path: Path, *args: object, **kwargs: object) -> object:
            if is_crossgl_source_path(path):
                raise AssertionError(f"loader opened CrossGL source path: {path}")
            return original_open(path, *args, **kwargs)

        def guarded_read_text(
            path: Path,
            *args: object,
            **kwargs: object,
        ) -> str:
            if is_crossgl_source_path(path):
                raise AssertionError(f"loader read CrossGL source path: {path}")
            return original_read_text(path, *args, **kwargs)

        def guarded_read_bytes(
            path: Path,
            *args: object,
            **kwargs: object,
        ) -> bytes:
            if is_crossgl_source_path(path):
                raise AssertionError(f"loader read CrossGL source path: {path}")
            return original_read_bytes(path, *args, **kwargs)

        return mock.patch.multiple(
            Path,
            open=guarded_open,
            read_text=guarded_read_text,
            read_bytes=guarded_read_bytes,
        )

    def _guard_crossgl_source_archive_reads(self) -> object:
        original_open = zipfile.ZipFile.open
        original_read = zipfile.ZipFile.read

        def member_name(name: object) -> str:
            return str(getattr(name, "filename", name))

        def is_crossgl_source_member(name: object) -> bool:
            return Path(member_name(name)).suffix.lower() == ".cgl"

        def guarded_open(
            archive: zipfile.ZipFile,
            name: object,
            *args: object,
            **kwargs: object,
        ) -> object:
            if is_crossgl_source_member(name):
                raise AssertionError(
                    f"loader opened CrossGL source archive member: {member_name(name)}"
                )
            return original_open(archive, name, *args, **kwargs)

        def guarded_read(
            archive: zipfile.ZipFile,
            name: object,
            *args: object,
            **kwargs: object,
        ) -> bytes:
            if is_crossgl_source_member(name):
                raise AssertionError(
                    f"loader read CrossGL source archive member: {member_name(name)}"
                )
            return original_read(archive, name, *args, **kwargs)

        return mock.patch.multiple(
            zipfile.ZipFile,
            open=guarded_open,
            read=guarded_read,
        )


if __name__ == "__main__":
    unittest.main()
