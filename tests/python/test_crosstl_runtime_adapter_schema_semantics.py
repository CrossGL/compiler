#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
import sys
import unittest


REPO_ROOT = Path(__file__).resolve().parents[2]
TOOLS_ROOT = REPO_ROOT / "tools"
sys.path.insert(0, str(TOOLS_ROOT))


from json_schema_semantics import validate_semantics  # noqa: E402
from validate_json_schema import SchemaError, load_json, validate  # noqa: E402


BLOCKED_STATUSES = {"blocked", "unavailable", "not-inspected", "failed"}


class CrossTLRuntimeAdapterSchemaSemanticsTests(unittest.TestCase):
    def test_descriptor_accepts_string_binding_and_artifact_for_new_statuses(
        self,
    ) -> None:
        for status in ("not-inspected", "failed"):
            with self.subTest(status=status):
                self.assert_valid(
                    "crosstl-runtime-adapter-descriptor-v1",
                    descriptor_instance(
                        status=status,
                        load_ready=False,
                        binding="metal-main-binding",
                        artifact="metal-main-artifact",
                    ),
                )

    def test_descriptor_preserves_object_binding_and_artifact(self) -> None:
        self.assert_valid(
            "crosstl-runtime-adapter-descriptor-v1",
            descriptor_instance(
                status="ready",
                load_ready=True,
                binding={"id": "metal-main-binding"},
                artifact={"id": "metal-main-artifact"},
            ),
        )

    def test_package_accepts_strings_new_statuses_and_copied_runtime_count(
        self,
    ) -> None:
        self.assert_valid(
            "crosstl-runtime-adapter-package-v1",
            package_instance(
                statuses=("not-inspected", "failed"),
                copied_global_runtime_count=True,
            ),
        )

    def test_package_runtime_reference_count_still_flags_mismatch(self) -> None:
        instance = package_instance(
            statuses=("not-inspected", "failed"),
            copied_global_runtime_count=True,
        )
        instance["targets"][1]["runtimeReferenceCount"] = 3

        schema = self.load_schema("crosstl-runtime-adapter-package-v1")
        validate(instance, schema, schema)
        semantic_errors = validate_semantics(instance, schema)

        self.assertTrue(
            any(
                error.startswith("$.summary.runtimeReferenceCount:")
                for error in semantic_errors
            ),
            semantic_errors,
        )

    def assert_valid(self, schema_name: str, instance: dict) -> None:
        schema = self.load_schema(schema_name)
        try:
            validate(instance, schema, schema)
        except SchemaError as exc:
            self.fail(f"{schema_name} schema validation failed: {exc}")

        semantic_errors = validate_semantics(instance, schema)
        self.assertEqual(semantic_errors, [])

    def load_schema(self, schema_name: str) -> dict:
        return load_json(REPO_ROOT / "docs" / "schemas" / f"{schema_name}.schema.json")


def descriptor_instance(*, status, load_ready, binding, artifact):
    return {
        "schemaVersion": 1,
        "kind": "crosstl-runtime-adapter-descriptor",
        "sourcePackage": "fixtures/package.crosstl",
        "sourcePackageHash": {
            "algorithm": "sha256",
            "value": "a" * 64,
        },
        "packageRoot": "/tmp/package",
        "adapterPlan": {
            "kind": "crosstl-runtime-adapter-plan",
            "success": True,
            "scope": "runtime-adapter-integration-planning",
        },
        "id": "metal-main",
        "target": "metal",
        "adapterKind": "host-loader",
        "artifactFormat": "backend-source",
        "binding": binding,
        "artifact": artifact,
        "packagePath": "adapters/metal/main.metal",
        "sourcePath": "src/main.cgl",
        "sourceBackend": "msl",
        "stage": "fragment",
        "variant": "default",
        "defines": {},
        "sourceRemap": None,
        "hostInterface": {
            "status": status,
        },
        "requiredTools": [
            "metal",
        ],
        "hostResponsibilities": [],
        "validation": {
            "loadReady": load_ready,
        },
    }


def package_instance(*, statuses, copied_global_runtime_count):
    descriptors = []
    targets = []
    runtime_reference_count = len(statuses)

    for index, status in enumerate(statuses):
        target = ("metal", "directx", "opengl")[index]
        descriptor_id = f"{target}-main"
        package_path = f"adapters/{target}/main.{target}"
        descriptor_path = f"adapters/{target}/main.adapter.json"
        target_runtime_reference_count = (
            runtime_reference_count if copied_global_runtime_count else 1
        )

        descriptors.append(
            {
                "id": descriptor_id,
                "target": target,
                "adapterKind": "host-loader",
                "artifactFormat": "backend-source",
                "binding": f"{descriptor_id}-binding",
                "artifact": f"{descriptor_id}-artifact",
                "packagePath": package_path,
                "descriptorPath": descriptor_path,
                "descriptorHash": {
                    "algorithm": "sha256",
                    "value": chr(ord("b") + index) * 64,
                },
                "descriptorSizeBytes": 12 + index,
                "hostInterfaceStatus": status,
                "requiredTools": [
                    target,
                ],
            }
        )
        targets.append(
            {
                "target": target,
                "adapterKind": "host-loader",
                "adapterCount": 1,
                "descriptorCount": 1,
                "readyDescriptorCount": 1 if status == "ready" else 0,
                "blockedDescriptorCount": 1 if status in BLOCKED_STATUSES else 0,
                "runtimeReferenceCount": target_runtime_reference_count,
                "requiredTools": [
                    target,
                ],
                "descriptors": [
                    descriptor_id,
                ],
                "packagePaths": [
                    package_path,
                ],
            }
        )

    return {
        "schemaVersion": 1,
        "kind": "crosstl-runtime-adapter-package",
        "sourcePackage": "fixtures/package.crosstl",
        "sourcePackageHash": {
            "algorithm": "sha256",
            "value": "a" * 64,
        },
        "generatedAt": 1,
        "success": True,
        "scope": "runtime-adapter-descriptor-package",
        "nonGoals": [],
        "packageRoot": "/tmp/package",
        "adapterRoot": "runtime-adapters",
        "adapterManifest": "runtime-adapters.json",
        "project": {},
        "summary": {
            "targetCount": len(targets),
            "adapterCount": len(targets),
            "descriptorCount": len(descriptors),
            "readyDescriptorCount": sum(
                1
                for descriptor in descriptors
                if descriptor["hostInterfaceStatus"] == "ready"
            ),
            "blockedDescriptorCount": sum(
                1
                for descriptor in descriptors
                if descriptor["hostInterfaceStatus"] in BLOCKED_STATUSES
            ),
            "actionCount": 0,
            "runtimeReferenceCount": runtime_reference_count,
        },
        "targets": targets,
        "descriptors": descriptors,
        "actions": [],
        "runtimePlan": {},
        "adapterPlan": {
            "kind": "crosstl-runtime-adapter-plan",
            "success": True,
            "scope": "runtime-adapter-integration-planning",
            "adapterCount": len(targets),
        },
        "packageInspection": {},
        "diagnosticCounts": {
            "note": 0,
            "warning": 0,
            "error": 0,
        },
        "diagnostics": [],
    }


if __name__ == "__main__":
    unittest.main()
