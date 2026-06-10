#!/usr/bin/env python3
from __future__ import annotations

from collections.abc import Callable
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock
import zipfile


REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURE_ROOT = REPO_ROOT / "runtime" / "examples" / "fixtures"
sys.path.insert(0, str(REPO_ROOT))


from runtime.opengl_loader import (  # noqa: E402
    plan_opengl_loader,
    plan_opengl_native_loader,
    plan_opengl_source_package_loader,
)
from runtime.package_reader import PackageReadError  # noqa: E402


class OpenGLNativeLoaderPlanTests(unittest.TestCase):
    def test_committed_validated_source_fixture_selects_backend_source_without_native_binary_promotion(
        self,
    ) -> None:
        package_dir = FIXTURE_ROOT / "source-free-opengl-validated-source.cglb"

        for package_mode in ("auto", "source-package"):
            with self.subTest(package_mode=package_mode):
                with self._guard_crossgl_source_reads():
                    plan = plan_opengl_loader(
                        package_dir,
                        package_mode=package_mode,
                    )
                    summary = plan.to_summary()

                selection = summary["runtimeArtifactSelection"]
                admission = summary["openglSourcePackageAdmission"]
                descriptor = admission["nativeArtifactDescriptor"]

                self.assertTrue(plan.loadable, summary["diagnostics"])
                self.assertFalse(plan.source_parsing_required)
                self.assertEqual(summary["sourceInputs"], [])
                self.assertFalse(summary["compilerInvocationRequired"])
                self.assertFalse(summary["deviceExecutionRequired"])
                self.assertEqual(selection["requestedPackageMode"], package_mode)
                self.assertEqual(selection["selectedPackageMode"], "source-package")
                self.assertEqual(selection["artifact"]["name"], "backendSource")
                self.assertEqual(
                    selection["artifact"]["path"],
                    (
                        "backend/opengl/"
                        "SourceFreeOpenGLValidatedSourceRuntimeExample.comp.glsl"
                    ),
                )
                self.assertEqual(
                    [artifact.name for artifact in plan.selected_artifacts],
                    ["backendSource", "nativeBinary"],
                )
                self.assertEqual(
                    admission["reason"],
                    "opengl_loader.source_package_admission.validated_glsl_accepted",
                )
                self.assertEqual(
                    admission["validatedSourceArtifact"]["path"],
                    (
                        "backend/opengl/"
                        "SourceFreeOpenGLValidatedSourceRuntimeExample.glsl"
                    ),
                )
                self.assertTrue(
                    admission["validatedSourceArtifact"]["validatedSourceEvidence"]
                )
                self.assertTrue(descriptor["declared"])
                self.assertTrue(descriptor["exists"])
                self.assertTrue(descriptor["descriptorManifestConsistent"])
                self.assertEqual(descriptor["diagnostics"], [])
                self.assertEqual(summary["rejectReasons"], [])
                self.assertEqual(list(package_dir.rglob("*.cgl")), [])

    def test_committed_validated_source_fixture_rejects_opengl_native_mode(
        self,
    ) -> None:
        package_dir = FIXTURE_ROOT / "source-free-opengl-validated-source.cglb"

        with self._guard_crossgl_source_reads():
            plan = plan_opengl_native_loader(package_dir)
            summary = plan.to_summary()

        native_admission = summary["nativeAdmission"]
        native_artifact = native_admission["nativeArtifact"]

        self.assertFalse(plan.ready)
        self.assertFalse(plan.loadable)
        self.assertFalse(plan.source_parsing_required)
        self.assertFalse(summary["compilerInvocationRequired"])
        self.assertFalse(summary["deviceExecutionRequired"])
        self.assertEqual(summary["sourceInputs"], [])
        self.assertEqual(
            native_admission["reason"],
            "opengl_loader.native_mode_unsupported",
        )
        self.assertEqual(native_artifact["decision"], "rejected")
        self.assertEqual(native_artifact["nativeBinaryStatus"], "validated")
        self.assertFalse(native_artifact["bytesRequired"])
        self.assertEqual(summary["nativeArtifact"], None)
        self.assertEqual(
            [diagnostic["code"] for diagnostic in summary["rejectReasons"]],
            ["opengl_loader.native_mode_unsupported"],
        )

    def test_validated_source_package_modes_select_backend_source_without_crossgl_parse(
        self,
    ) -> None:
        cases = (("auto", "auto"), ("source-package", "source-package"))
        for package_mode, requested_mode in cases:
            with self.subTest(package_mode=package_mode):
                with tempfile.TemporaryDirectory(suffix=".cglb") as temp_dir:
                    package_dir = Path(temp_dir)
                    self._write_valid_opengl_package(
                        package_dir,
                        native_binary_status="validated",
                        emit_native_artifact_descriptor=True,
                    )
                    source_path = package_dir / "source" / "invalid.cgl"
                    source_path.parent.mkdir()
                    source_path.write_text(
                        "must not parse CrossGL source\n", encoding="utf-8"
                    )

                    with self._guard_crossgl_source_reads():
                        plan = plan_opengl_loader(
                            package_dir,
                            package_mode=package_mode,
                        )
                        summary = plan.to_summary()

                    selection = summary["runtimeArtifactSelection"]
                    self.assertTrue(plan.loadable, summary["diagnostics"])
                    self.assertIs(plan.require_loadable(), plan)
                    self.assertFalse(plan.source_parsing_required)
                    self.assertEqual(summary["sourceInputs"], [])
                    self.assertEqual(summary["compilerInvocationRequired"], False)
                    self.assertEqual(summary["deviceExecutionRequired"], False)
                    self.assertEqual(summary["packageTarget"], "opengl")
                    self.assertEqual(summary["loaderTarget"], "opengl")
                    self.assertEqual(summary["selectedTarget"], "opengl")
                    self.assertEqual(selection["requestedPackageMode"], requested_mode)
                    self.assertEqual(
                        selection["selectedPackageMode"],
                        "source-package",
                    )
                    self.assertEqual(selection["artifact"]["name"], "backendSource")
                    self.assertEqual(
                        selection["artifact"]["path"],
                        "backend/opengl/RuntimeOpenGLLoaderFixture.comp.glsl",
                    )
                    self.assertEqual(
                        [artifact.name for artifact in plan.selected_artifacts],
                        ["backendSource", "nativeBinary"],
                    )
                    self.assertEqual(
                        plan.require_runtime_artifact().name,
                        "backendSource",
                    )
                    self.assertEqual(
                        summary["compatibilityReport"]["nativeBinaryStatus"],
                        "validated",
                    )
                    self._assert_validated_opengl_source_package_admission_detail(
                        summary,
                        requested_mode=requested_mode,
                    )
                    self.assertEqual(
                        summary["metadataContract"]["runtimeArtifact"],
                        {
                            "name": "backendSource",
                            "path": (
                                "backend/opengl/RuntimeOpenGLLoaderFixture.comp.glsl"
                            ),
                            "declaredBy": "manifest.artifacts.backendSource",
                        },
                    )
                    self.assertEqual(summary["rejectReasons"], [])
                    self.assertEqual(list(package_dir.rglob("*.cgl")), [source_path])

    def test_source_package_plan_returns_explicit_glsl_handoff_without_crossgl_parse(
        self,
    ) -> None:
        expected_bytes = b"// generated GLSL\n"
        with tempfile.TemporaryDirectory(suffix=".cglb") as temp_dir:
            package_dir = Path(temp_dir)
            self._write_valid_opengl_package(
                package_dir,
                native_binary_status="validated",
                emit_native_artifact_descriptor=True,
            )
            source_path = package_dir / "source" / "invalid.cgl"
            source_path.parent.mkdir()
            source_path.write_text(
                "GLSL handoff must not parse CrossGL source\n",
                encoding="utf-8",
            )

            with self._guard_crossgl_source_reads():
                plan = plan_opengl_source_package_loader(package_dir)
                summary = plan.to_summary()
                handoff = plan.require_glsl_handoff()
                with self.assertRaisesRegex(
                    PackageReadError,
                    "package artifact exceeds runtime byte limit",
                ):
                    plan.require_glsl_handoff(byte_limit=len(expected_bytes) - 1)

            self.assertTrue(plan.loadable, summary["diagnostics"])
            self.assertNotIn("runtimeArtifactHandoff", summary)
            self.assertNotIn("glslHandoff", summary)
            self.assertEqual(handoff.artifact_name, "backendSource")
            self.assertEqual(
                handoff.package_path,
                "backend/opengl/RuntimeOpenGLLoaderFixture.comp.glsl",
            )
            self.assertEqual(handoff.package_format, "directory")
            self.assertEqual(handoff.selected_package_mode, "source-package")
            self.assertEqual(handoff.bytes, expected_bytes)
            self.assertEqual(handoff.byte_length, len(expected_bytes))
            self.assertIsNone(handoff.archive_path)
            self.assertIsNone(handoff.archive_member)
            self.assertEqual(handoff.metadata["sourceInputs"], [])
            self.assertFalse(handoff.metadata["sourceParsingRequired"])
            self.assertFalse(handoff.metadata["compilerInvocationRequired"])
            self.assertFalse(handoff.metadata["deviceExecutionRequired"])
            self.assertEqual(
                handoff.metadata["runtimeArtifact"],
                {
                    "name": "backendSource",
                    "path": "backend/opengl/RuntimeOpenGLLoaderFixture.comp.glsl",
                    "declaredBy": "manifest.artifacts.backendSource",
                },
            )
            self.assertEqual(list(package_dir.rglob("*.cgl")), [source_path])

    def test_validated_source_package_requires_descriptor_evidence_without_crossgl_parse(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory(suffix=".cglb") as temp_dir:
            package_dir = Path(temp_dir)
            self._write_valid_opengl_package(
                package_dir,
                native_binary_status="validated",
                emit_native_artifact_descriptor=False,
            )
            source_path = package_dir / "source" / "invalid.cgl"
            source_path.parent.mkdir()
            source_path.write_text(
                "missing validated descriptor must not parse CrossGL source\n",
                encoding="utf-8",
            )

            with self._guard_crossgl_source_reads():
                plan = plan_opengl_source_package_loader(package_dir)
                summary = plan.to_summary()

            admission = summary["openglSourcePackageAdmission"]
            descriptor = admission["nativeArtifactDescriptor"]
            validated_artifact = admission["validatedSourceArtifact"]
            evidence = admission["compatibilityEvidence"]
            diagnostic_code = "opengl_loader.validated_source_descriptor_missing"

            self.assertFalse(plan.loadable)
            self.assertEqual(admission["decision"], "rejected")
            self.assertEqual(admission["reason"], diagnostic_code)
            self.assertEqual(
                admission["packageMode"],
                {
                    "kind": "source-package",
                    "requested": "source-package",
                    "selected": "source-package",
                    "selectedForRuntime": True,
                },
            )
            self.assertEqual(
                admission["declaredSourceArtifact"],
                admission["sourcePackageRuntime"],
            )
            self.assertEqual(
                admission["declaredSourceArtifact"]["path"],
                "backend/opengl/RuntimeOpenGLLoaderFixture.comp.glsl",
            )
            self.assertEqual(
                admission["declaredSourceArtifact"]["expectedPathSuffix"],
                ".glsl",
            )
            self.assertTrue(
                admission["declaredSourceArtifact"]["pathSuffixMatchesExpected"]
            )
            self.assertIsNotNone(validated_artifact)
            self.assertEqual(
                validated_artifact["path"],
                "backend/opengl/RuntimeOpenGLLoaderFixture.glsl",
            )
            self.assertTrue(validated_artifact["validatedSourceEvidence"])
            self.assertFalse(descriptor["declared"])
            self.assertFalse(descriptor["exists"])
            self.assertEqual(evidence["manifestNativeBinaryStatus"], "validated")
            self.assertTrue(evidence["validatedSourceEvidence"])
            self.assertFalse(evidence["descriptorDeclared"])
            self.assertIn(
                diagnostic_code,
                [diagnostic["code"] for diagnostic in summary["rejectReasons"]],
            )
            with self.assertRaisesRegex(PackageReadError, "nativeArtifactDescriptor"):
                plan.require_loadable()
            self.assertEqual(list(package_dir.rglob("*.cgl")), [source_path])

    def test_accepts_opengl_package_descriptor_as_source_package_evidence_without_crossgl_parse(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory(suffix=".cglb") as temp_dir:
            package_dir = Path(temp_dir)
            self._write_valid_opengl_package(
                package_dir,
                native_binary_status="validated",
                emit_native_artifact_descriptor=True,
                descriptor_binary_kind="opengl.package",
            )
            source_path = package_dir / "source" / "invalid.cgl"
            source_path.parent.mkdir()
            source_path.write_text(
                "opengl.package descriptor admission must not parse CrossGL source\n",
                encoding="utf-8",
            )

            with self._guard_crossgl_source_reads():
                plan = plan_opengl_loader(package_dir)
                summary = plan.to_summary()

            admission = summary["openglSourcePackageAdmission"]
            descriptor_admission = self._summary_section(
                admission["nativeArtifactDescriptor"],
                "OpenGL nativeArtifactDescriptor admission",
            )

            self.assertTrue(plan.loadable, summary["diagnostics"])
            self.assertFalse(plan.source_parsing_required)
            self.assertEqual(summary["sourceInputs"], [])
            self.assertEqual(summary["compilerInvocationRequired"], False)
            self.assertEqual(summary["deviceExecutionRequired"], False)
            self.assertEqual(
                summary["runtimeArtifactSelection"]["selectedPackageMode"],
                "source-package",
            )
            self.assertEqual(
                summary["runtimeArtifactSelection"]["artifact"]["name"],
                "backendSource",
            )
            self.assertEqual(admission["decision"], "accepted")
            self.assertTrue(descriptor_admission["declared"])
            self.assertTrue(descriptor_admission["exists"])
            self.assertTrue(descriptor_admission["descriptorManifestConsistent"])
            self.assertEqual(descriptor_admission["diagnostics"], [])
            self.assertEqual(summary["rejectReasons"], [])
            self.assertEqual(list(package_dir.rglob("*.cgl")), [source_path])

    def test_source_package_admission_reports_graphics_abi_reflection_parity_without_crossgl_parse(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory(suffix=".cglb") as temp_dir:
            package_dir = Path(temp_dir)
            self._write_valid_opengl_package(
                package_dir,
                native_binary_status="validated",
                emit_native_artifact_descriptor=True,
            )
            self._write_graphics_abi_sidecar(package_dir)
            source_path = package_dir / "source" / "invalid.cgl"
            source_path.parent.mkdir()
            source_path.write_text(
                "OpenGL graphics ABI parity must not parse CrossGL source\n",
                encoding="utf-8",
            )

            with self._guard_crossgl_source_reads():
                plan = plan_opengl_source_package_loader(package_dir)
                summary = plan.to_summary()

            admission = summary["openglSourcePackageAdmission"]
            parity = admission["graphicsAbiReflectionParity"]

            self.assertTrue(plan.loadable, summary["diagnostics"])
            self.assertTrue(parity["graphicsAbiDeclared"])
            self.assertTrue(parity["parityChecked"])
            self.assertTrue(parity["identityMatches"])
            self.assertEqual(parity["status"], "matched")
            self.assertEqual(parity["reflectionBindingCount"], 1)
            self.assertEqual(parity["graphicsAbiBindingCount"], 1)
            self.assertEqual(parity["missingGraphicsAbiBindings"], [])
            self.assertEqual(parity["staleGraphicsAbiBindings"], [])
            self.assertEqual(parity["diagnostics"], [])
            self.assertEqual(list(package_dir.rglob("*.cgl")), [source_path])

    def test_rejects_non_opengl_descriptor_kind_without_crossgl_parse(self) -> None:
        with tempfile.TemporaryDirectory(suffix=".cglb") as temp_dir:
            package_dir = Path(temp_dir)
            self._write_valid_opengl_package(
                package_dir,
                native_binary_status="validated",
                emit_native_artifact_descriptor=True,
                descriptor_binary_kind="vulkan.spirv-module",
            )
            source_path = package_dir / "source" / "invalid.cgl"
            source_path.parent.mkdir()
            source_path.write_text(
                "descriptor target mismatch must not parse CrossGL source\n",
                encoding="utf-8",
            )

            with self._guard_crossgl_source_reads():
                plan = plan_opengl_loader(package_dir)
                summary = plan.to_summary()

            admission = summary["openglSourcePackageAdmission"]
            descriptor_admission = self._summary_section(
                admission["nativeArtifactDescriptor"],
                "OpenGL nativeArtifactDescriptor admission",
            )
            reject_codes = [
                diagnostic["code"] for diagnostic in summary["rejectReasons"]
            ]

            self.assertFalse(plan.loadable)
            self.assertFalse(plan.source_parsing_required)
            self.assertEqual(summary["sourceInputs"], [])
            self.assertEqual(admission["decision"], "rejected")
            self.assertEqual(
                admission["reason"],
                "package.native_artifact_descriptor.binary_kind_mismatch",
            )
            self.assertFalse(descriptor_admission["descriptorManifestConsistent"])
            self.assertIn(
                "package.native_artifact_descriptor.binary_kind_mismatch",
                reject_codes,
            )
            self._diagnostic_by_code(
                descriptor_admission["diagnostics"],
                "package.native_artifact_descriptor.binary_kind_mismatch",
            )
            with self.assertRaisesRegex(PackageReadError, "binaryKind"):
                plan.require_loadable()
            self.assertEqual(list(package_dir.rglob("*.cgl")), [source_path])

    def test_native_mode_rejects_validated_source_package_without_crossgl_parse(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory(suffix=".cglb") as temp_dir:
            package_dir = Path(temp_dir)
            self._write_valid_opengl_package(
                package_dir,
                native_binary_status="validated",
                emit_native_artifact_descriptor=True,
            )
            source_path = package_dir / "source" / "invalid.cgl"
            source_path.parent.mkdir()
            source_path.write_text(
                "native mode must not parse CrossGL source\n", encoding="utf-8"
            )

            with self._guard_crossgl_source_reads():
                plan = plan_opengl_loader(package_dir, package_mode="native")
                summary = plan.to_summary()

            selection = summary["runtimeArtifactSelection"]
            reject_codes = [
                diagnostic["code"] for diagnostic in summary["rejectReasons"]
            ]
            self.assertFalse(plan.loadable)
            self.assertFalse(plan.source_parsing_required)
            self.assertEqual(summary["sourceInputs"], [])
            self.assertEqual(summary["compilerInvocationRequired"], False)
            self.assertEqual(summary["deviceExecutionRequired"], False)
            self.assertEqual(summary["packageTarget"], "opengl")
            self.assertEqual(summary["loaderTarget"], "opengl")
            self.assertIsNone(summary["selectedTarget"])
            self.assertEqual(selection["requestedPackageMode"], "native")
            self.assertFalse(selection["selected"])
            self.assertIsNone(selection["selectedPackageMode"])
            self.assertIsNone(selection["artifact"])
            self.assertEqual(plan.selected_artifacts, ())
            self.assertEqual(
                summary["compatibilityReport"]["nativeBinaryStatus"],
                "validated",
            )
            self.assertIn("opengl_loader.native_mode_unsupported", reject_codes)
            with self.assertRaisesRegex(PackageReadError, "source-package"):
                plan.require_loadable()
            self.assertEqual(list(package_dir.rglob("*.cgl")), [source_path])

    def test_native_directory_plan_reports_validated_source_package_as_non_executable(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory(suffix=".cglb") as temp_dir:
            package_dir = Path(temp_dir)
            self._write_valid_opengl_package(package_dir)
            source_path = package_dir / "source" / "invalid.cgl"
            source_path.parent.mkdir()
            source_path.write_text(
                "native loader must not open CrossGL source\n", encoding="utf-8"
            )

            with self._guard_source_reads():
                plan = plan_opengl_native_loader(package_dir)
                summary = plan.to_summary()

            self.assertFalse(plan.ready)
            self.assertFalse(plan.loadable)
            self.assertIsNone(plan.native_artifact)
            self.assertIsNone(summary["nativeArtifact"])
            self.assertEqual(summary["runtimePlan"]["packageFormat"], "directory")
            self.assertFalse(summary["sourceParsingRequired"])
            self.assertEqual(summary["sourceInputs"], [])
            self.assertEqual(summary["artifactInputs"], [])
            self.assertEqual(summary["compilerInvocationRequired"], False)
            self.assertEqual(summary["deviceExecutionRequired"], False)
            self._assert_validated_opengl_native_admission_boundary(summary)
            with self.assertRaisesRegex(PackageReadError, "source-package"):
                plan.require_ready()
            self.assertEqual(list(package_dir.rglob("*.cgl")), [source_path])

    def test_malformed_or_stale_validated_metadata_fails_closed_without_crossgl_parse(
        self,
    ) -> None:
        cases = (
            (
                "malformed validation status",
                lambda descriptor: descriptor.__setitem__(
                    "validationStatus",
                    "complete",
                ),
                "package.native_artifact_descriptor.validation_status_invalid",
                "validationStatus",
            ),
            (
                "stale artifact hash",
                lambda descriptor: descriptor["artifactHash"].__setitem__(
                    "value",
                    "1" * 64,
                ),
                "package.native_artifact_descriptor.artifact_hash_mismatch",
                "artifactHash.value",
            ),
        )
        for name, mutate_descriptor, expected_code, expected_path in cases:
            with self.subTest(name=name):
                with tempfile.TemporaryDirectory(suffix=".cglb") as temp_dir:
                    package_dir = Path(temp_dir)
                    self._write_valid_opengl_package(
                        package_dir,
                        native_binary_status="validated",
                        emit_native_artifact_descriptor=True,
                        descriptor_mutator=mutate_descriptor,
                    )
                    source_path = package_dir / "source" / "invalid.cgl"
                    source_path.parent.mkdir()
                    source_path.write_text(
                        "metadata rejection must not parse CrossGL source\n",
                        encoding="utf-8",
                    )

                    with self._guard_crossgl_source_reads():
                        plan = plan_opengl_loader(package_dir)
                        summary = plan.to_summary()

                    reject_codes = [
                        diagnostic["code"] for diagnostic in summary["rejectReasons"]
                    ]
                    self.assertFalse(plan.loadable)
                    self.assertFalse(plan.source_parsing_required)
                    self.assertEqual(plan.selected_artifacts, ())
                    self.assertIsNone(plan.runtime_artifact)
                    self.assertEqual(summary["sourceInputs"], [])
                    self.assertEqual(summary["compilerInvocationRequired"], False)
                    self.assertEqual(summary["deviceExecutionRequired"], False)
                    self.assertEqual(
                        summary["metadataContract"]["sourceInputs"],
                        [],
                    )
                    self.assertEqual(
                        summary["runtimeArtifactSelection"]["requestedPackageMode"],
                        "auto",
                    )
                    self.assertFalse(summary["runtimeArtifactSelection"]["selected"])
                    self.assertIsNone(summary["runtimeArtifactSelection"]["artifact"])
                    self.assertEqual(
                        summary["compatibilityReport"]["nativeBinaryStatus"],
                        "validated",
                    )
                    source_admission = self._summary_section(
                        summary["openglSourcePackageAdmission"],
                        "openglSourcePackageAdmission",
                    )
                    descriptor_admission = self._summary_section(
                        source_admission["nativeArtifactDescriptor"],
                        "OpenGL nativeArtifactDescriptor admission",
                    )
                    self.assertEqual(source_admission["decision"], "rejected")
                    self.assertEqual(source_admission["reason"], expected_code)
                    self.assertFalse(
                        descriptor_admission["descriptorManifestConsistent"]
                    )
                    self._diagnostic_by_code(
                        descriptor_admission["diagnostics"],
                        expected_code,
                    )
                    self._diagnostic_by_code(
                        source_admission["blockedByDiagnostics"],
                        expected_code,
                    )
                    self.assertIn(expected_code, reject_codes)
                    diagnostic = next(
                        diagnostic
                        for diagnostic in summary["rejectReasons"]
                        if diagnostic["code"] == expected_code
                    )
                    self.assertEqual(diagnostic["document"], "nativeArtifactDescriptor")
                    self.assertEqual(diagnostic["path"], expected_path)
                    self.assertEqual(list(package_dir.rglob("*.cgl")), [source_path])

    def test_zip_malformed_or_stale_validated_metadata_fails_closed_without_crossgl_parse(
        self,
    ) -> None:
        cases = (
            (
                "malformed validation status",
                lambda descriptor: descriptor.__setitem__(
                    "validationStatus",
                    "complete",
                ),
                "package.native_artifact_descriptor.validation_status_invalid",
                "validationStatus",
            ),
            (
                "stale artifact hash",
                lambda descriptor: descriptor["artifactHash"].__setitem__(
                    "value",
                    "1" * 64,
                ),
                "package.native_artifact_descriptor.artifact_hash_mismatch",
                "artifactHash.value",
            ),
        )
        for name, mutate_descriptor, expected_code, expected_path in cases:
            with self.subTest(name=name):
                with tempfile.TemporaryDirectory() as temp_dir:
                    temp_root = Path(temp_dir)
                    package_dir = temp_root / "package-dir"
                    package_dir.mkdir()
                    self._write_valid_opengl_package(
                        package_dir,
                        native_binary_status="validated",
                        emit_native_artifact_descriptor=True,
                        descriptor_mutator=mutate_descriptor,
                    )
                    source_path = package_dir / "source" / "invalid.cgl"
                    source_path.parent.mkdir()
                    source_path.write_text(
                        "zip metadata rejection must not parse CrossGL source\n",
                        encoding="utf-8",
                    )
                    zip_path = temp_root / "RuntimeOpenGLLoaderFixture.cglb"
                    self._write_zip_package(
                        package_dir,
                        zip_path,
                        prefix=zip_path.name,
                    )

                    with (
                        self._guard_crossgl_source_reads(),
                        self._guard_crossgl_source_archive_reads(),
                    ):
                        plan = plan_opengl_loader(zip_path)
                        summary = plan.to_summary()

                    reject_codes = [
                        diagnostic["code"] for diagnostic in summary["rejectReasons"]
                    ]
                    self.assertFalse(plan.loadable)
                    self.assertFalse(plan.source_parsing_required)
                    self.assertEqual(plan.selected_artifacts, ())
                    self.assertIsNone(plan.runtime_artifact)
                    self.assertEqual(summary["packageFormat"], "zip")
                    self.assertEqual(summary["sourceInputs"], [])
                    self.assertEqual(summary["compilerInvocationRequired"], False)
                    self.assertEqual(summary["deviceExecutionRequired"], False)
                    self.assertEqual(
                        summary["metadataContract"]["sourceInputs"],
                        [],
                    )
                    self.assertEqual(
                        summary["runtimeArtifactSelection"]["requestedPackageMode"],
                        "auto",
                    )
                    self.assertFalse(summary["runtimeArtifactSelection"]["selected"])
                    self.assertIsNone(summary["runtimeArtifactSelection"]["artifact"])
                    self.assertEqual(
                        summary["compatibilityReport"]["nativeBinaryStatus"],
                        "validated",
                    )
                    source_admission = self._summary_section(
                        summary["openglSourcePackageAdmission"],
                        "openglSourcePackageAdmission",
                    )
                    descriptor_admission = self._summary_section(
                        source_admission["nativeArtifactDescriptor"],
                        "OpenGL nativeArtifactDescriptor admission",
                    )
                    self.assertEqual(source_admission["decision"], "rejected")
                    self.assertEqual(source_admission["reason"], expected_code)
                    self.assertFalse(source_admission["sourceParsingRequired"])
                    self.assertFalse(source_admission["compilerInvocationRequired"])
                    self.assertFalse(source_admission["deviceExecutionRequired"])
                    self.assertFalse(
                        descriptor_admission["descriptorManifestConsistent"]
                    )
                    self._diagnostic_by_code(
                        descriptor_admission["diagnostics"],
                        expected_code,
                    )
                    self._diagnostic_by_code(
                        source_admission["blockedByDiagnostics"],
                        expected_code,
                    )
                    self.assertIn(expected_code, reject_codes)
                    diagnostic = next(
                        diagnostic
                        for diagnostic in summary["rejectReasons"]
                        if diagnostic["code"] == expected_code
                    )
                    self.assertEqual(diagnostic["document"], "nativeArtifactDescriptor")
                    self.assertEqual(diagnostic["path"], expected_path)

    def test_zip_validated_source_package_admits_backend_source_without_source_reads(
        self,
    ) -> None:
        expected_bytes = b"// generated GLSL\n"
        for package_mode in ("auto", "source-package"):
            with self.subTest(package_mode=package_mode):
                with tempfile.TemporaryDirectory() as temp_dir:
                    temp_root = Path(temp_dir)
                    package_dir = temp_root / "package-dir"
                    package_dir.mkdir()
                    self._write_valid_opengl_package(
                        package_dir,
                        native_binary_status="validated",
                        emit_native_artifact_descriptor=True,
                    )
                    source_path = package_dir / "source" / "invalid.cgl"
                    source_path.parent.mkdir()
                    source_path.write_text(
                        "zip source-package admission must not parse CrossGL source\n",
                        encoding="utf-8",
                    )
                    zip_path = temp_root / "RuntimeOpenGLLoaderFixture.cglb"
                    self._write_zip_package(
                        package_dir,
                        zip_path,
                        prefix=zip_path.name,
                    )
                    near_source_member = "near-zip-source.cgl"
                    with zipfile.ZipFile(zip_path, "a") as archive:
                        archive.writestr(
                            near_source_member,
                            "near zip source must not be opened\n",
                        )

                    with (
                        self._guard_crossgl_source_reads(),
                        self._guard_crossgl_source_archive_reads(),
                    ):
                        plan = plan_opengl_loader(
                            zip_path,
                            package_mode=package_mode,
                        )
                        summary = plan.to_summary()
                        handoff = plan.require_glsl_handoff()

                    selection = summary["runtimeArtifactSelection"]
                    admission = summary["openglSourcePackageAdmission"]
                    descriptor = self._summary_section(
                        admission["nativeArtifactDescriptor"],
                        "OpenGL nativeArtifactDescriptor admission",
                    )
                    source_archive_member = f"{zip_path.name}/source/invalid.cgl"

                    self.assertTrue(plan.loadable, summary["diagnostics"])
                    self.assertIs(plan.require_loadable(), plan)
                    self.assertFalse(plan.source_parsing_required)
                    self.assertEqual(summary["packageFormat"], "zip")
                    self.assertEqual(summary["sourceInputs"], [])
                    self.assertEqual(summary["compilerInvocationRequired"], False)
                    self.assertEqual(summary["deviceExecutionRequired"], False)
                    self.assertEqual(summary["packageTarget"], "opengl")
                    self.assertEqual(summary["loaderTarget"], "opengl")
                    self.assertEqual(summary["selectedTarget"], "opengl")
                    self.assertEqual(
                        selection["requestedPackageMode"],
                        package_mode,
                    )
                    self.assertEqual(
                        selection["selectedPackageMode"],
                        "source-package",
                    )
                    self.assertEqual(selection["artifact"]["name"], "backendSource")
                    self.assertEqual(
                        selection["artifact"]["path"],
                        "backend/opengl/RuntimeOpenGLLoaderFixture.comp.glsl",
                    )
                    self.assertEqual(
                        [artifact.name for artifact in plan.selected_artifacts],
                        ["backendSource", "nativeBinary"],
                    )
                    for artifact in plan.selected_artifacts:
                        self.assertEqual(artifact.archive_path, zip_path)
                        self.assertTrue(
                            artifact.archive_member.startswith(f"{zip_path.name}/")
                        )
                    self.assertNotIn("runtimeArtifactHandoff", summary)
                    self.assertEqual(handoff.artifact_name, "backendSource")
                    self.assertEqual(
                        handoff.package_path,
                        "backend/opengl/RuntimeOpenGLLoaderFixture.comp.glsl",
                    )
                    self.assertEqual(handoff.package_format, "zip")
                    self.assertEqual(
                        handoff.selected_package_mode,
                        "source-package",
                    )
                    self.assertEqual(handoff.bytes, expected_bytes)
                    self.assertEqual(handoff.archive_path, zip_path)
                    self.assertEqual(
                        handoff.archive_member,
                        (
                            f"{zip_path.name}/backend/opengl/"
                            "RuntimeOpenGLLoaderFixture.comp.glsl"
                        ),
                    )
                    self.assertEqual(handoff.metadata["sourceInputs"], [])
                    self.assertFalse(handoff.metadata["sourceParsingRequired"])
                    self.assertEqual(
                        plan.require_runtime_artifact().name,
                        "backendSource",
                    )
                    self.assertEqual(admission["decision"], "accepted")
                    self.assertEqual(
                        admission["reason"],
                        (
                            "opengl_loader.source_package_admission."
                            "validated_glsl_accepted"
                        ),
                    )
                    self.assertEqual(
                        admission["validatedSourceArtifact"]["path"],
                        "backend/opengl/RuntimeOpenGLLoaderFixture.glsl",
                    )
                    self.assertTrue(
                        admission["validatedSourceArtifact"]["validatedSourceEvidence"]
                    )
                    self.assertTrue(descriptor["declared"])
                    self.assertTrue(descriptor["exists"])
                    self.assertTrue(descriptor["descriptorManifestConsistent"])
                    self.assertEqual(descriptor["diagnostics"], [])
                    self.assertEqual(
                        admission["compatibilityEvidence"][
                            "manifestNativeBinaryStatus"
                        ],
                        "validated",
                    )
                    self.assertTrue(
                        admission["compatibilityEvidence"]["validatedSourceEvidence"]
                    )
                    self.assertTrue(
                        admission["compatibilityEvidence"]["descriptorDeclared"]
                    )
                    self.assertEqual(
                        summary["metadataContract"]["runtimeArtifact"],
                        {
                            "name": "backendSource",
                            "path": (
                                "backend/opengl/RuntimeOpenGLLoaderFixture.comp.glsl"
                            ),
                            "declaredBy": "manifest.artifacts.backendSource",
                        },
                    )
                    self.assertEqual(summary["rejectReasons"], [])
                    self._assert_validated_opengl_source_package_admission_detail(
                        summary,
                        requested_mode=package_mode,
                    )
                    with zipfile.ZipFile(zip_path) as archive:
                        self.assertIn(source_archive_member, archive.namelist())
                        self.assertIn(near_source_member, archive.namelist())

    def test_native_zip_plan_rejects_validated_source_package_without_source_parse(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir)
            package_dir = temp_root / "package-dir"
            package_dir.mkdir()
            self._write_valid_opengl_package(package_dir)
            source_path = package_dir / "source" / "invalid.cgl"
            source_path.parent.mkdir()
            source_path.write_text(
                "zip loader must not parse source\n", encoding="utf-8"
            )
            zip_path = temp_root / "RuntimeOpenGLLoaderFixture.cglb"
            self._write_zip_package(
                package_dir,
                zip_path,
                prefix=zip_path.name,
            )

            with self._guard_source_reads(), self._guard_source_archive_reads():
                plan = plan_opengl_native_loader(zip_path)
                summary = plan.to_summary()

            reject_codes = [
                diagnostic["code"] for diagnostic in summary["rejectReasons"]
            ]
            self.assertFalse(plan.ready)
            self.assertFalse(plan.loadable)
            self.assertEqual(summary["runtimePlan"]["packageFormat"], "zip")
            self.assertEqual(summary["sourceInputs"], [])
            self.assertEqual(summary["artifactInputs"], [])
            self.assertEqual(summary["compilerInvocationRequired"], False)
            self.assertEqual(summary["deviceExecutionRequired"], False)
            self.assertIsNone(plan.native_artifact)
            self.assertIsNone(summary["nativeArtifact"])
            self.assertEqual(
                summary["runtimePlan"]["runtimeArtifactSelection"][
                    "requestedPackageMode"
                ],
                "native",
            )
            self.assertIsNone(
                summary["runtimePlan"]["runtimeArtifactSelection"]["artifact"]
            )
            self.assertIn("opengl_loader.native_mode_unsupported", reject_codes)
            self._assert_validated_opengl_native_admission_boundary(summary)
            with self.assertRaisesRegex(PackageReadError, "source-package"):
                plan.require_ready()

    def test_rejects_zip_missing_native_artifact_without_source_parse(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir)
            package_dir = temp_root / "package-dir"
            package_dir.mkdir()
            self._write_valid_opengl_package(package_dir)
            source_path = package_dir / "source" / "invalid.cgl"
            source_path.parent.mkdir()
            source_path.write_text(
                "missing zip artifact must not parse source\n",
                encoding="utf-8",
            )
            zip_path = temp_root / "RuntimeOpenGLLoaderFixture.cglb"
            self._write_zip_package(
                package_dir,
                zip_path,
                prefix=zip_path.name,
                exclude={"backend/opengl/RuntimeOpenGLLoaderFixture.glsl"},
            )

            with self._guard_source_reads(), self._guard_source_archive_reads():
                plan = plan_opengl_native_loader(zip_path)
                summary = plan.to_summary()

            self.assertFalse(plan.ready)
            self.assertIsNone(plan.native_artifact)
            self.assertEqual(summary["runtimePlan"]["packageFormat"], "zip")
            self.assertEqual(summary["sourceInputs"], [])
            self.assertEqual(summary["artifactInputs"], [])
            self.assertIn(
                "package.artifact.required_file_missing",
                [diagnostic["code"] for diagnostic in summary["rejectReasons"]],
            )
            self._assert_missing_native_artifact_admission_boundary(summary)
            with self.assertRaisesRegex(PackageReadError, "nativeBinary"):
                plan.require_ready()

    def test_rejects_incompatible_target_without_source_parse(self) -> None:
        with tempfile.TemporaryDirectory(suffix=".cglb") as temp_dir:
            package_dir = Path(temp_dir)
            self._write_valid_vulkan_package(package_dir)
            source_path = package_dir / "source" / "invalid.cgl"
            source_path.parent.mkdir()
            source_path.write_text("target mismatch source\n", encoding="utf-8")

            with self._guard_source_reads():
                plan = plan_opengl_native_loader(package_dir)
                summary = plan.to_summary()

            self.assertFalse(plan.ready)
            self.assertIsNone(plan.native_artifact)
            self.assertEqual(summary["sourceInputs"], [])
            self.assertIn(
                "package.target.loader_mismatch",
                [diagnostic["code"] for diagnostic in summary["rejectReasons"]],
            )
            self.assertEqual(list(package_dir.rglob("*.cgl")), [source_path])

    def test_source_package_target_mismatch_is_skipped_without_source_parse(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory(suffix=".cglb") as temp_dir:
            package_dir = Path(temp_dir)
            self._write_valid_vulkan_package(package_dir)
            source_path = package_dir / "source" / "invalid.cgl"
            source_path.parent.mkdir()
            source_path.write_text("source-package target mismatch\n", encoding="utf-8")

            with self._guard_source_reads():
                plan = plan_opengl_source_package_loader(package_dir)
                summary = plan.to_summary()

            admission = summary["openglSourcePackageAdmission"]
            runtime_admission = summary["runtimeArtifactAdmission"]

            self.assertFalse(plan.loadable)
            self.assertFalse(plan.source_parsing_required)
            self.assertIsNone(plan.runtime_artifact)
            self.assertEqual(summary["sourceInputs"], [])
            self.assertEqual(summary["metadataContract"]["sourceInputs"], [])
            self.assertEqual(runtime_admission["decision"], "skipped")
            self.assertEqual(admission["decision"], "skipped")
            self.assertEqual(
                admission["reason"],
                "opengl_loader.source_package_admission.target_mismatch",
            )
            self.assertIn(
                "package.target.loader_mismatch",
                [diagnostic["code"] for diagnostic in summary["diagnostics"]],
            )
            self.assertIsNone(summary["runtimeArtifactSelection"]["artifact"])
            self.assertIsNone(runtime_admission["runtimeArtifact"])
            self.assertEqual(list(package_dir.rglob("*.cgl")), [source_path])

    def test_rejects_missing_native_artifact_metadata(self) -> None:
        with tempfile.TemporaryDirectory(suffix=".cglb") as temp_dir:
            package_dir = Path(temp_dir)
            self._write_valid_opengl_package(package_dir, include_native_binary=False)
            source_path = package_dir / "source" / "invalid.cgl"
            source_path.parent.mkdir()
            source_path.write_text("missing artifact source\n", encoding="utf-8")

            with self._guard_source_reads():
                plan = plan_opengl_native_loader(package_dir)
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
            self._write_valid_opengl_package(
                package_dir,
                native_binary_path="source/forged.cgl",
            )

            with self._guard_source_reads():
                plan = plan_opengl_native_loader(package_dir)
                summary = plan.to_summary()

            self.assertFalse(plan.ready)
            self.assertIsNone(plan.native_artifact)
            self.assertEqual(summary["sourceInputs"], [])
            self.assertIn(
                "package.artifact.source_input_leakage",
                [diagnostic["code"] for diagnostic in summary["rejectReasons"]],
            )

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
            self._write_valid_opengl_package(
                package_dir,
                native_binary_status="planned",
                package_artifact_requirements=requirements,
            )
            native_path = (
                package_dir / "backend" / "opengl" / "RuntimeOpenGLLoaderFixture.glsl"
            )
            native_path.unlink()
            source_path = package_dir / "source" / "RuntimeOpenGLLoaderFixture.cgl"
            source_path.parent.mkdir()
            source_path.write_text(
                "source-package loader must not parse CrossGL source\n",
                encoding="utf-8",
            )

            with self._guard_source_reads():
                plan = plan_opengl_source_package_loader(package_dir)
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
                        "backend/opengl/RuntimeOpenGLLoaderFixture.glsl",
                        False,
                    ),
                    (
                        "backendSource",
                        "backend/opengl/RuntimeOpenGLLoaderFixture.comp.glsl",
                        True,
                    ),
                ],
            )
            self.assertEqual(
                summary["metadataContract"]["runtimeArtifact"],
                {
                    "name": "backendSource",
                    "path": "backend/opengl/RuntimeOpenGLLoaderFixture.comp.glsl",
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
            self._assert_planned_opengl_source_package_admission_detail(
                summary,
                native_exists=False,
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
            self.assertEqual(
                summary["reflectionResources"]["targetResourceBindings"][0]["abi"],
                {"program": 0, "binding": 0},
            )
            self.assertEqual(
                summary["reflectionResources"]["targetResourceBindings"][0][
                    "evidenceId"
                ],
                (
                    "target-legalization.v1.opengl.resource-binding.compute."
                    "runtime_opengl_loader_main.OutputBuffer"
                ),
            )
            self.assertEqual(summary["reflectionResources"]["targetFeatureCount"], 1)
            self.assertEqual(summary["rejectReasons"], [])
            self.assertEqual(list(package_dir.rglob("*.cgl")), [source_path])

    def test_planned_source_package_treats_present_native_binary_as_evidence(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory(suffix=".cglb") as temp_dir:
            package_dir = Path(temp_dir)
            requirements = self._source_package_requirements()
            self._write_valid_opengl_package(
                package_dir,
                native_binary_status="planned",
                package_artifact_requirements=requirements,
            )
            source_path = package_dir / "source" / "RuntimeOpenGLLoaderFixture.cgl"
            source_path.parent.mkdir()
            source_path.write_text(
                "present planned native evidence must not parse CrossGL source\n",
                encoding="utf-8",
            )

            with self._guard_source_reads():
                plan = plan_opengl_source_package_loader(package_dir)
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
            self._assert_planned_opengl_source_package_admission_detail(
                summary,
                native_exists=True,
            )
            self.assertEqual(summary["sourceInputs"], [])
            self.assertEqual(summary["metadataContract"]["sourceInputs"], [])
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
                    self._write_valid_opengl_package(
                        package_dir,
                        native_binary_status="planned",
                        package_artifact_requirements=requirements,
                    )
                    source_path = (
                        package_dir / "source" / "RuntimeOpenGLLoaderFixture.cgl"
                    )
                    source_path.parent.mkdir()
                    source_path.write_text(
                        "invalid requirements must reject structurally\n",
                        encoding="utf-8",
                    )

                    with self._guard_source_reads():
                        plan = plan_opengl_source_package_loader(package_dir)
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

    def test_source_package_rejects_non_glsl_backend_source_without_source_parse(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory(suffix=".cglb") as temp_dir:
            package_dir = Path(temp_dir)
            bad_source_rel = "backend/opengl/RuntimeOpenGLLoaderFixture.txt"
            self._write_valid_opengl_package(
                package_dir,
                native_binary_status="planned",
                package_artifact_requirements=self._source_package_requirements(),
            )
            (package_dir / bad_source_rel).write_text(
                "not GLSL by manifest path\n",
                encoding="utf-8",
            )
            manifest_path = package_dir / "manifest.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["artifacts"]["backendSource"] = bad_source_rel
            self._write_json(manifest_path, manifest)
            source_path = package_dir / "source" / "RuntimeOpenGLLoaderFixture.cgl"
            source_path.parent.mkdir()
            source_path.write_text(
                "backendSource suffix rejection must stay metadata-only\n",
                encoding="utf-8",
            )

            with self._guard_source_reads():
                plan = plan_opengl_source_package_loader(package_dir)
                summary = plan.to_summary()

            diagnostic_code = (
                "opengl_loader.source_package_backend_source_suffix_mismatch"
            )
            reject_codes = [
                diagnostic["code"] for diagnostic in summary["rejectReasons"]
            ]
            opengl_admission = summary["openglSourcePackageAdmission"]
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
            self.assertEqual(diagnostic["expected"], "*.glsl")
            self.assertEqual(opengl_admission["decision"], "rejected")
            self.assertEqual(opengl_admission["reason"], diagnostic_code)
            self.assertEqual(
                opengl_admission["backendSource"]["path"],
                bad_source_rel,
            )
            self.assertFalse(opengl_admission["backendSource"]["selectedForRuntime"])
            with self.assertRaisesRegex(PackageReadError, r"\.glsl"):
                plan.require_loadable()
            with self.assertRaisesRegex(PackageReadError, r"\.glsl"):
                plan.require_glsl_handoff()
            self.assertEqual(list(package_dir.rglob("*.cgl")), [source_path])

    def _write_valid_opengl_package(
        self,
        package_dir: Path,
        *,
        include_native_binary: bool = True,
        native_binary_path: str = "backend/opengl/RuntimeOpenGLLoaderFixture.glsl",
        native_binary_status: object | None = "validated",
        package_artifact_requirements: dict[str, object] | None = None,
        emit_native_artifact_descriptor: bool = False,
        descriptor_binary_kind: str = "opengl.source",
        descriptor_mutator: Callable[[dict[str, object]], None] | None = None,
    ) -> None:
        backend_dir = package_dir / "backend" / "opengl"
        backend_dir.mkdir(parents=True)
        source_path = "backend/opengl/RuntimeOpenGLLoaderFixture.comp.glsl"
        (package_dir / source_path).write_text("// generated GLSL\n", encoding="utf-8")
        if include_native_binary:
            native_path = package_dir / native_binary_path
            native_path.parent.mkdir(parents=True, exist_ok=True)
            native_path.write_text(
                "// validated GLSL package artifact\n", encoding="utf-8"
            )

        artifacts: dict[str, object] = {
            "backendSource": source_path,
        }
        if native_binary_status is not None:
            artifacts["nativeBinaryStatus"] = native_binary_status
        if include_native_binary:
            artifacts["nativeBinary"] = native_binary_path
        if emit_native_artifact_descriptor:
            descriptor_path = "metadata/native-artifact.json"
            artifacts["nativeArtifactDescriptor"] = descriptor_path
            self._write_native_artifact_descriptor(
                package_dir,
                descriptor_path=descriptor_path,
                source_path=source_path,
                native_binary_path=(
                    native_binary_path if include_native_binary else None
                ),
                native_binary_status=native_binary_status,
                binary_kind=descriptor_binary_kind,
                mutator=descriptor_mutator,
            )

        self._write_package_json(
            package_dir,
            target="opengl",
            native_binary_path=native_binary_path,
            artifacts=artifacts,
            package_artifact_requirements=package_artifact_requirements,
            binding={
                "target": "opengl",
                "stage": "compute",
                "entryPoint": "runtime_opengl_loader_main",
                "name": "OutputBuffer",
                "kind": "storageBuffer",
                "sourceType": "float4",
                "addressSpace": "buffer",
                "abi": {"program": 0, "binding": 0},
                "bindingClass": "storage-buffer",
                "descriptorType": "shader-storage-buffer",
                "evidenceId": (
                    "target-legalization.v1.opengl.resource-binding.compute."
                    "runtime_opengl_loader_main.OutputBuffer"
                ),
            },
        )

    def _write_native_artifact_descriptor(
        self,
        package_dir: Path,
        *,
        descriptor_path: str,
        source_path: str,
        native_binary_path: str | None,
        native_binary_status: object | None,
        binary_kind: str = "opengl.source",
        mutator: Callable[[dict[str, object]], None] | None = None,
    ) -> None:
        descriptor: dict[str, object] = {
            "schemaVersion": 1,
            "kind": "crossgl.nativeArtifact",
            "contractVersion": "native-artifact-v0",
            "target": "opengl",
            "binaryKind": binary_kind,
            "sourcePath": source_path,
            "sourceHash": self._sha256(package_dir / source_path),
            "toolchainProvenance": {
                "producer": "OpenGL runtime loader fixture",
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
            "validationStatus": "validated",
            "validationDiagnostics": [],
        }
        if native_binary_status is not None:
            descriptor["nativeBinaryStatus"] = native_binary_status
        if native_binary_status != "planned" and native_binary_path is not None:
            native_path = package_dir / native_binary_path
            descriptor["artifactPath"] = native_binary_path
            descriptor["artifactHash"] = self._sha256(native_path)
            descriptor["sizeBytes"] = native_path.stat().st_size
        if mutator is not None:
            mutator(descriptor)
        descriptor_file = package_dir / descriptor_path
        descriptor_file.parent.mkdir(parents=True, exist_ok=True)
        self._write_json(descriptor_file, descriptor)

    def _sha256(self, path: Path) -> dict[str, str]:
        return {
            "algorithm": "sha256",
            "value": hashlib.sha256(path.read_bytes()).hexdigest(),
        }

    def _write_valid_vulkan_package(self, package_dir: Path) -> None:
        backend_dir = package_dir / "backend" / "vulkan"
        backend_dir.mkdir(parents=True)
        assembly_path = "backend/vulkan/RuntimeOpenGLLoaderFixture.spvasm"
        native_path = "backend/vulkan/RuntimeOpenGLLoaderFixture.spv"
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
                "entryPoint": "runtime_opengl_loader_main",
                "name": "OutputBuffer",
                "kind": "storageBuffer",
                "sourceType": "float4",
                "addressSpace": "storage",
                "abi": {"set": 0, "binding": 0},
                "bindingClass": "storage-buffer",
                "descriptorType": "VK_DESCRIPTOR_TYPE_STORAGE_BUFFER",
            },
        )

    def _write_graphics_abi_sidecar(self, package_dir: Path) -> None:
        manifest_path = package_dir / "manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        graphics_abi_path = (
            "backend/opengl/RuntimeOpenGLLoaderFixture.graphics-abi.json"
        )
        self._write_json(
            package_dir / graphics_abi_path,
            {
                "schemaVersion": 1,
                "module": "RuntimeOpenGLLoaderFixture",
                "target": "opengl",
                "entryPoints": [
                    {
                        "stage": "compute",
                        "sourceName": "main",
                        "backendName": "runtime_opengl_loader_main",
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
                "abiRecords": [
                    {
                        "target": "opengl",
                        "stage": "compute",
                        "entryPoint": "runtime_opengl_loader_main",
                        "name": "OutputBuffer",
                        "kind": "storageBuffer",
                        "sourceType": "float4",
                        "addressSpace": "buffer",
                        "abi": {"program": 0, "binding": 0},
                        "bindingClass": "storage-buffer",
                        "descriptorType": "shader-storage-buffer",
                        "set": 0,
                        "binding": 0,
                    }
                ],
            },
        )
        manifest["artifacts"]["graphicsAbi"] = graphics_abi_path
        self._write_json(manifest_path, manifest)

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
            "module": "RuntimeOpenGLLoaderFixture",
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
                "module": "RuntimeOpenGLLoaderFixture",
                "target": target,
                "nativeBinary": native_binary_path,
                "entryPoints": [
                    {
                        "stage": "compute",
                        "sourceName": "main",
                        "backendName": "runtime_opengl_loader_main",
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
        path.write_text(
            json.dumps(document, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )

    def _source_package_requirements(self) -> dict[str, object]:
        return {
            "target": "opengl",
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

    def _assert_validated_opengl_native_admission_boundary(
        self,
        summary: dict[str, object],
    ) -> None:
        admission = self._summary_section(
            summary["nativeAdmission"],
            "nativeAdmission",
        )
        native_artifact = self._summary_section(
            admission["nativeArtifact"],
            "nativeArtifact admission",
        )
        runtime_selection = self._summary_section(
            admission["runtimeSelection"],
            "runtimeSelection admission",
        )

        self.assertEqual(admission["decision"], "rejected")
        self.assertEqual(admission["status"], "rejected")
        self.assertEqual(admission["reason"], "opengl_loader.native_mode_unsupported")
        self.assertFalse(admission["sourceParsingRequired"])
        self.assertFalse(admission["compilerInvocationRequired"])
        self.assertFalse(admission["deviceExecutionRequired"])
        self.assertEqual(
            admission["packageArtifactRequirementsSource"],
            summary["packageArtifactRequirementsSource"],
        )
        self.assertEqual(
            admission["packageArtifactRequirements"],
            summary["packageArtifactRequirements"],
        )
        unsupported = self._diagnostic_by_code(
            admission["blockedByDiagnostics"],
            "opengl_loader.native_mode_unsupported",
        )
        self.assertEqual(unsupported["document"], "manifest")
        self.assertEqual(unsupported["artifact"], "nativeBinary")
        self.assertEqual(unsupported["expected"], "source-package")
        self.assertEqual(unsupported["actual"], "native")

        self.assertEqual(native_artifact["decision"], "rejected")
        self.assertEqual(
            native_artifact["reason"],
            "opengl_loader.native_mode_unsupported",
        )
        self.assertEqual(native_artifact["nativeBinaryStatus"], "validated")
        self.assertTrue(native_artifact["declared"])
        self.assertTrue(native_artifact["available"])
        self.assertFalse(native_artifact["selectedForRuntime"])
        self.assertFalse(native_artifact["bytesRequired"])
        self.assertFalse(native_artifact["compatible"])
        self.assertIsNone(native_artifact["artifact"])
        native_compatibility = self._summary_section(
            native_artifact["compatibility"],
            "nativeArtifact compatibility",
        )
        self.assertEqual(native_compatibility["decision"], "accepted")
        self.assertEqual(native_compatibility["reason"], "package.artifact.accepted")
        self.assertFalse(native_compatibility["selected"])

        self.assertEqual(runtime_selection["requestedPackageMode"], "native")
        self.assertFalse(runtime_selection["selected"])
        self.assertIsNone(runtime_selection["selectedPackageMode"])
        source_fallback = self._summary_section(
            runtime_selection["sourcePackageFallback"],
            "sourcePackageFallback admission",
        )
        self.assertEqual(source_fallback["decision"], "accepted")
        self.assertEqual(
            source_fallback["reason"],
            "runtime.source_package_fallback.accepted",
        )
        self.assertTrue(source_fallback["fallbackAllowed"])
        self.assertTrue(source_fallback["fallbackAttempted"])
        self.assertTrue(source_fallback["fallbackAccepted"])
        self.assertFalse(source_fallback["sourceParsingRequired"])

    def _assert_missing_native_artifact_admission_boundary(
        self,
        summary: dict[str, object],
    ) -> None:
        admission = self._summary_section(
            summary["nativeAdmission"],
            "nativeAdmission",
        )
        native_artifact = self._summary_section(
            admission["nativeArtifact"],
            "nativeArtifact admission",
        )
        runtime_selection = self._summary_section(
            admission["runtimeSelection"],
            "runtimeSelection admission",
        )

        self.assertEqual(admission["decision"], "rejected")
        self.assertEqual(
            admission["reason"],
            "package.artifact.required_file_missing",
        )
        self.assertEqual(
            admission["packageArtifactRequirementsSource"],
            summary["packageArtifactRequirementsSource"],
        )
        self.assertEqual(
            admission["packageArtifactRequirements"],
            summary["packageArtifactRequirements"],
        )
        self._diagnostic_by_code(
            admission["blockedByDiagnostics"],
            "package.artifact.required_file_missing",
        )
        self._diagnostic_by_code(
            admission["blockedByDiagnostics"],
            "opengl_loader.native_mode_unsupported",
        )

        self.assertEqual(native_artifact["decision"], "rejected")
        self.assertEqual(native_artifact["status"], "missing-native-artifact")
        self.assertEqual(
            native_artifact["reason"],
            "package.artifact.required_file_missing",
        )
        self.assertTrue(native_artifact["declared"])
        self.assertFalse(native_artifact["available"])
        self.assertFalse(native_artifact["selectedForRuntime"])
        self.assertFalse(native_artifact["bytesRequired"])
        self.assertIsNone(native_artifact["artifact"])
        native_compatibility = self._summary_section(
            native_artifact["compatibility"],
            "nativeArtifact compatibility",
        )
        self.assertEqual(native_compatibility["decision"], "rejected")
        self.assertEqual(
            native_compatibility["reason"],
            "package.artifact.required_file_missing",
        )

        source_fallback = self._summary_section(
            runtime_selection["sourcePackageFallback"],
            "sourcePackageFallback admission",
        )
        self.assertEqual(source_fallback["decision"], "skipped")
        self.assertEqual(
            source_fallback["reason"],
            "runtime.source_package_fallback.unavailable",
        )
        self.assertTrue(source_fallback["fallbackAllowed"])
        self.assertTrue(source_fallback["fallbackAttempted"])
        self.assertFalse(source_fallback["fallbackAccepted"])
        self.assertFalse(source_fallback["sourceParsingRequired"])

    def _assert_validated_opengl_source_package_admission_detail(
        self,
        summary: dict[str, object],
        *,
        requested_mode: str,
    ) -> None:
        admission = self._summary_section(
            summary["openglSourcePackageAdmission"],
            "openglSourcePackageAdmission",
        )
        backend_source = self._summary_section(
            admission["backendSource"],
            "OpenGL backendSource admission",
        )
        native_glsl = self._summary_section(
            admission["nativeGlslSourcePackageArtifact"],
            "OpenGL native GLSL admission",
        )
        descriptor = self._summary_section(
            admission["nativeArtifactDescriptor"],
            "OpenGL nativeArtifactDescriptor admission",
        )
        reflection = self._summary_section(
            admission["reflection"],
            "OpenGL reflection admission",
        )

        self.assertEqual(admission["decision"], "accepted")
        self.assertEqual(
            admission["reason"],
            "opengl_loader.source_package_admission.validated_glsl_accepted",
        )
        self.assertEqual(admission["loaderTarget"], "opengl")
        self.assertEqual(admission["packageTarget"], "opengl")
        self.assertEqual(admission["requestedPackageMode"], requested_mode)
        self.assertEqual(admission["selectedPackageMode"], "source-package")
        self.assertEqual(
            admission["packageMode"],
            {
                "kind": "source-package",
                "requested": requested_mode,
                "selected": "source-package",
                "selectedForRuntime": True,
            },
        )
        self.assertFalse(admission["sourceParsingRequired"])
        self.assertFalse(admission["compilerInvocationRequired"])
        self.assertFalse(admission["deviceExecutionRequired"])
        self.assertEqual(
            admission["targetLegalizationEvidence"],
            summary["targetLegalizationEvidence"],
        )
        self.assertEqual(
            admission["targetLegalizationToolRequirements"],
            summary["targetLegalizationToolRequirements"],
        )
        self.assertEqual(
            admission["packageArtifactRequirementsSource"],
            summary["packageArtifactRequirementsSource"],
        )
        self.assertEqual(
            admission["packageArtifactRequirements"],
            summary["packageArtifactRequirements"],
        )
        self.assertEqual(admission["blockedByDiagnostics"], [])

        self.assertEqual(admission["declaredSourceArtifact"], backend_source)
        self.assertEqual(admission["sourcePackageRuntime"], backend_source)
        self.assertTrue(backend_source["exists"])
        self.assertTrue(backend_source["selectedForRuntime"])
        self.assertTrue(backend_source["bytesRequired"])
        self.assertEqual(backend_source["expectedPathSuffix"], ".glsl")
        self.assertEqual(backend_source["pathSuffix"], ".glsl")
        self.assertTrue(backend_source["pathSuffixMatchesExpected"])
        self.assertEqual(
            backend_source["path"],
            "backend/opengl/RuntimeOpenGLLoaderFixture.comp.glsl",
        )

        self.assertEqual(admission["validatedSourceArtifact"], native_glsl)
        self.assertIsNone(admission["compiledArtifact"])
        self.assertTrue(native_glsl["exists"])
        self.assertFalse(native_glsl["selectedForRuntime"])
        self.assertTrue(native_glsl["acceptedAsSourcePackageEvidence"])
        self.assertFalse(native_glsl["bytesRequired"])
        self.assertEqual(native_glsl["expectedPathSuffix"], ".glsl")
        self.assertEqual(native_glsl["pathSuffix"], ".glsl")
        self.assertTrue(native_glsl["pathSuffixMatchesExpected"])
        self.assertEqual(native_glsl["nativeBinaryStatus"], "validated")
        self.assertTrue(native_glsl["validatedSourceEvidence"])
        self.assertFalse(native_glsl["plannedNativeMetadataOnly"])
        self.assertEqual(
            native_glsl["path"],
            "backend/opengl/RuntimeOpenGLLoaderFixture.glsl",
        )

        self.assertTrue(descriptor["declared"])
        self.assertTrue(descriptor["exists"])
        self.assertTrue(descriptor["descriptorManifestConsistent"])
        self.assertEqual(descriptor["diagnostics"], [])
        self.assertEqual(
            admission["validatedSourceStatus"],
            {
                "manifestNativeBinaryStatus": "validated",
                "descriptorPresent": True,
                "descriptorManifestConsistent": True,
                "diagnostics": [],
            },
        )
        self.assertEqual(
            admission["compatibilityEvidence"]["manifestNativeBinaryStatus"],
            "validated",
        )
        self.assertEqual(
            admission["compatibilityEvidence"]["declaredSourcePath"],
            "backend/opengl/RuntimeOpenGLLoaderFixture.comp.glsl",
        )
        self.assertTrue(admission["compatibilityEvidence"]["validatedSourceEvidence"])
        self.assertTrue(admission["compatibilityEvidence"]["descriptorDeclared"])
        self.assertTrue(
            admission["compatibilityEvidence"]["descriptorManifestConsistent"]
        )
        self.assertEqual(
            admission["compatibilityEvidence"]["targetLegalizationEvidence"],
            summary["targetLegalizationEvidence"],
        )
        self.assertEqual(
            admission["compatibilityEvidence"]["targetLegalizationToolRequirements"],
            summary["targetLegalizationToolRequirements"],
        )
        self.assertEqual(
            admission["compatibilityEvidence"]["packageArtifactRequirementsSource"],
            summary["packageArtifactRequirementsSource"],
        )
        self.assertEqual(
            admission["compatibilityEvidence"]["packageArtifactRequirements"],
            summary["packageArtifactRequirements"],
        )

        self.assertEqual(reflection["entryPointCount"], 1)
        self.assertEqual(reflection["resourceCount"], 1)
        self.assertEqual(reflection["targetResourceBindingCount"], 1)

    def _assert_planned_opengl_source_package_admission_detail(
        self,
        summary: dict[str, object],
        *,
        native_exists: bool,
    ) -> None:
        admission = self._summary_section(
            summary["openglSourcePackageAdmission"],
            "openglSourcePackageAdmission",
        )
        native_glsl = self._summary_section(
            admission["nativeGlslSourcePackageArtifact"],
            "OpenGL native GLSL admission",
        )
        descriptor = self._summary_section(
            admission["nativeArtifactDescriptor"],
            "OpenGL nativeArtifactDescriptor admission",
        )

        self.assertEqual(admission["decision"], "accepted")
        self.assertEqual(
            admission["reason"],
            "opengl_loader.source_package_admission.planned_glsl_accepted",
        )
        self.assertEqual(admission["selectedPackageMode"], "source-package")
        self.assertFalse(admission["compilerInvocationRequired"])
        self.assertFalse(admission["deviceExecutionRequired"])
        self.assertEqual(
            admission["targetLegalizationEvidence"],
            summary["targetLegalizationEvidence"],
        )
        self.assertEqual(
            admission["targetLegalizationToolRequirements"],
            summary["targetLegalizationToolRequirements"],
        )
        self.assertEqual(
            admission["packageArtifactRequirementsSource"],
            summary["packageArtifactRequirementsSource"],
        )
        self.assertEqual(
            admission["packageArtifactRequirements"],
            summary["packageArtifactRequirements"],
        )
        self.assertEqual(admission["blockedByDiagnostics"], [])

        self.assertEqual(native_glsl["exists"], native_exists)
        self.assertFalse(native_glsl["selectedForRuntime"])
        self.assertTrue(native_glsl["acceptedAsSourcePackageEvidence"])
        self.assertFalse(native_glsl["bytesRequired"])
        self.assertEqual(native_glsl["nativeBinaryStatus"], "planned")
        self.assertTrue(native_glsl["plannedNativeMetadataOnly"])
        self.assertFalse(native_glsl["validatedSourceEvidence"])
        self.assertEqual(
            native_glsl["path"],
            "backend/opengl/RuntimeOpenGLLoaderFixture.glsl",
        )

        self.assertFalse(descriptor["declared"])
        self.assertFalse(descriptor["exists"])
        self.assertIsNone(descriptor["descriptorManifestConsistent"])
        self.assertEqual(descriptor["diagnostics"], [])
        self.assertEqual(
            admission["validatedSourceStatus"],
            {
                "manifestNativeBinaryStatus": "planned",
                "descriptorPresent": False,
                "descriptorManifestConsistent": None,
                "diagnostics": [],
            },
        )
        self.assertEqual(
            admission["compatibilityEvidence"]["targetLegalizationEvidence"],
            summary["targetLegalizationEvidence"],
        )
        self.assertEqual(
            admission["compatibilityEvidence"]["targetLegalizationToolRequirements"],
            summary["targetLegalizationToolRequirements"],
        )
        self.assertEqual(
            admission["compatibilityEvidence"]["packageArtifactRequirementsSource"],
            summary["packageArtifactRequirementsSource"],
        )
        self.assertEqual(
            admission["compatibilityEvidence"]["packageArtifactRequirements"],
            summary["packageArtifactRequirements"],
        )

    def _summary_section(
        self,
        section: object,
        name: str,
    ) -> dict[str, object]:
        self.assertIsInstance(section, dict)
        if not isinstance(section, dict):
            self.fail(f"{name} must be a dictionary")
        return section

    def _diagnostic_by_code(
        self,
        diagnostics: object,
        code: str,
    ) -> dict[str, object]:
        self.assertIsInstance(diagnostics, list)
        if not isinstance(diagnostics, list):
            self.fail("diagnostics must be a list")
        for diagnostic in diagnostics:
            self.assertIsInstance(diagnostic, dict)
            if isinstance(diagnostic, dict) and diagnostic.get("code") == code:
                return diagnostic
        self.fail(f"missing diagnostic code: {code}")

    def _guard_crossgl_source_reads(self) -> object:
        original_read_text = Path.read_text
        original_read_bytes = Path.read_bytes
        original_open = Path.open

        def guarded_read_text(path: Path, *args: object, **kwargs: object) -> str:
            if path.suffix == ".cgl":
                raise AssertionError(f"loader parsed CrossGL source input: {path}")
            return original_read_text(path, *args, **kwargs)

        def guarded_read_bytes(path: Path, *args: object, **kwargs: object) -> bytes:
            if path.suffix == ".cgl":
                raise AssertionError(f"loader parsed CrossGL source input: {path}")
            return original_read_bytes(path, *args, **kwargs)

        def guarded_open(path: Path, *args: object, **kwargs: object) -> object:
            if path.suffix == ".cgl":
                raise AssertionError(f"loader opened CrossGL source input: {path}")
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

    def _guard_source_reads(self) -> object:
        original_read_text = Path.read_text
        original_read_bytes = Path.read_bytes
        original_open = Path.open
        guarded_suffixes = {".cgl", ".hlsl", ".glsl", ".metal", ".spvasm"}

        def guarded_read_text(path: Path, *args: object, **kwargs: object) -> str:
            if path.suffix in guarded_suffixes:
                raise AssertionError(f"loader parsed source artifact: {path}")
            return original_read_text(path, *args, **kwargs)

        def guarded_read_bytes(path: Path, *args: object, **kwargs: object) -> bytes:
            if path.suffix in guarded_suffixes:
                raise AssertionError(f"loader parsed source artifact: {path}")
            return original_read_bytes(path, *args, **kwargs)

        def guarded_open(path: Path, *args: object, **kwargs: object) -> object:
            if path.suffix in guarded_suffixes:
                raise AssertionError(f"loader opened source artifact: {path}")
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


if __name__ == "__main__":
    unittest.main()
