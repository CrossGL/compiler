#!/usr/bin/env python3
from __future__ import annotations

from contextlib import contextmanager
import json
import os
from pathlib import Path
import shutil
import stat
import subprocess
import sys
import tempfile
import unittest
from unittest import mock


REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))


def _extract_cglc_arg() -> str | None:
    cglc = os.environ.get("CGLC")
    rewritten_argv = [sys.argv[0]]
    index = 1
    while index < len(sys.argv):
        argument = sys.argv[index]
        if argument == "--cglc":
            if index + 1 >= len(sys.argv):
                raise RuntimeError("--cglc requires a path")
            cglc = sys.argv[index + 1]
            index += 2
            continue
        if argument.startswith("--cglc="):
            cglc = argument.split("=", 1)[1]
            index += 1
            continue
        rewritten_argv.append(argument)
        index += 1
    sys.argv[:] = rewritten_argv
    return cglc


CGLC_ARG = _extract_cglc_arg()


from runtime.opengl_loader import (  # noqa: E402
    plan_opengl_loader,
    plan_opengl_native_loader,
)
from runtime.package_reader import (  # noqa: E402
    read_compatibility_report,
    read_package,
)


class CompilerProducedPackageRuntimeSmokeTests(unittest.TestCase):
    def test_reads_compiler_native_artifact_descriptor_without_crossgl_source(
        self,
    ) -> None:
        cglc = self._require_cglc()
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir)
            input_path = temp_root / "StorageBufferComputeShader.cgl"
            input_path.write_text(
                (
                    REPO_ROOT / "tests" / "fixtures" / "StorageBufferComputeShader.cgl"
                ).read_text(encoding="utf-8"),
                encoding="utf-8",
            )
            package_dir = temp_root / "StorageBufferComputeShader.cglb"
            fake_tool_dir = temp_root / "fake-toolchain"
            fake_tool_log = temp_root / "glslangValidator.log"
            self._write_fake_glslang_validator(fake_tool_dir)

            self._run_cglc_build(
                cglc,
                input_path=input_path,
                package_dir=package_dir,
                fake_tool_dir=fake_tool_dir,
                fake_tool_log=fake_tool_log,
            )
            input_path.unlink()

            manifest_path = package_dir / "manifest.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            reflection = json.loads(
                (package_dir / "reflection.json").read_text(encoding="utf-8")
            )
            artifacts = manifest["artifacts"]
            package_artifact_requirements = manifest["packageArtifactRequirements"]
            descriptor_path = artifacts["nativeArtifactDescriptor"]
            native_binary_path = artifacts["nativeBinary"]
            backend_source_path = artifacts["backendSource"]
            target_explanation_path = artifacts["targetExplanation"]
            self.assertEqual(manifest["target"], "opengl")
            self.assertNotIn("graphicsAbi", artifacts)
            self.assertEqual(list(package_dir.rglob("*.graphics-abi.json")), [])
            self.assertEqual(
                set(package_artifact_requirements),
                {
                    "target",
                    "packageMode",
                    "requiredPathArtifacts",
                    "requiresNativeBinaryStatus",
                    "allowsPlannedNativeBinary",
                    "allowsPlannedNativeSourceEvidence",
                    "evidenceIds",
                },
            )
            self.assertEqual(package_artifact_requirements["target"], "opengl")
            self.assertEqual(
                package_artifact_requirements["packageMode"],
                "source-package",
            )
            self.assertEqual(
                package_artifact_requirements["requiredPathArtifacts"],
                ["backendSource", "nativeBinary"],
            )
            self.assertEqual(
                package_artifact_requirements["requiresNativeBinaryStatus"],
                True,
            )
            self.assertEqual(
                package_artifact_requirements["allowsPlannedNativeBinary"],
                True,
            )
            self.assertEqual(
                package_artifact_requirements["allowsPlannedNativeSourceEvidence"],
                True,
            )
            self.assertIsInstance(package_artifact_requirements["evidenceIds"], list)
            self.assertIn(
                "target-legalization.v1.opengl.package-artifact.required.backendSource",
                package_artifact_requirements["evidenceIds"],
            )
            self.assertEqual(artifacts["nativeBinaryStatus"], "validated")
            self.assertNotEqual(descriptor_path, "metadata/native-artifact.json")
            self.assertTrue((package_dir / descriptor_path).is_file())
            self.assertTrue((package_dir / native_binary_path).is_file())
            self.assertEqual(target_explanation_path, "ir/target-explanation.json")
            self.assertTrue((package_dir / target_explanation_path).is_file())
            target_binding = reflection["targetResourceBindings"][0]
            self.assertEqual(target_binding["target"], "opengl")
            self.assertEqual(target_binding["abi"], "programResourceBinding")
            self.assertEqual(target_binding["bindingClass"], "storage-buffer")
            self.assertEqual(target_binding["argumentIndex"], 0)
            self.assertEqual(target_binding["set"], 0)
            self.assertEqual(target_binding["binding"], 0)

            legacy_descriptor_path = package_dir / "metadata" / "native-artifact.json"
            legacy_descriptor_path.parent.mkdir()
            legacy_descriptor_path.write_text(
                '{"not": "the manifest-declared descriptor"}\n',
                encoding="utf-8",
            )
            source_probe = package_dir / "source" / "must_not_parse.cgl"
            source_probe.parent.mkdir()
            source_probe.write_text(
                "runtime must not parse CrossGL source\n",
                encoding="utf-8",
            )

            with self._guard_crossgl_source_reads():
                package = read_package(package_dir)
                report = package.compatibility_report(loader_target="opengl")
                report_from_path = read_compatibility_report(
                    package_dir,
                    loader_target="opengl",
                )
                loader_plan = plan_opengl_loader(package_dir)
                native_loader_plan = plan_opengl_native_loader(package_dir)

            report_summary = report.to_summary()
            loader_summary = loader_plan.to_summary()
            native_loader_summary = native_loader_plan.to_summary()
            descriptor_artifact = package.require_existing_artifact(
                "nativeArtifactDescriptor"
            )
            target_explanation_artifact = package.require_existing_artifact(
                "targetExplanation"
            )
            descriptor_summary = json.loads(descriptor_artifact.read_text())

            self.assertEqual(package.module, "StorageBufferComputeShader")
            self.assertEqual(package.target, "opengl")
            self.assertEqual(package.native_binary_status, "validated")
            self.assertTrue(report.compatible, report_summary["diagnostics"])
            self.assertTrue(report_from_path.compatible)
            self.assertFalse(report.source_parsing_required)
            self.assertEqual(report.target_contract.requirements_source, "manifest")
            self.assertEqual(
                report.required_artifacts, ("backendSource", "nativeBinary")
            )
            self.assertEqual(descriptor_artifact.package_path, descriptor_path)
            self.assertEqual(
                descriptor_artifact.path.resolve(),
                (package_dir / descriptor_path).resolve(),
            )
            self.assertNotEqual(
                descriptor_artifact.path.resolve(),
                legacy_descriptor_path.resolve(),
            )
            self.assertEqual(
                target_explanation_artifact.package_path,
                target_explanation_path,
            )
            target_explanation = json.loads(target_explanation_artifact.read_text())
            self.assertEqual(target_explanation["schemaVersion"], 1)
            self.assertEqual(target_explanation["module"], "StorageBufferComputeShader")
            self.assertTrue(loader_plan.loadable, loader_summary["diagnostics"])
            self.assertEqual(
                loader_summary["runtimeArtifactSelection"]["requestedPackageMode"],
                "auto",
            )
            self.assertEqual(
                loader_summary["runtimeArtifactSelection"]["selectedPackageMode"],
                "source-package",
            )
            self.assertEqual(
                loader_summary["runtimeArtifactSelection"]["artifact"]["name"],
                "backendSource",
            )
            self.assertEqual(
                loader_plan.require_runtime_artifact().package_path,
                backend_source_path,
            )
            self.assertEqual(
                loader_plan.require_artifact("nativeBinary").package_path,
                native_binary_path,
            )
            self.assertEqual(
                loader_summary["compatibilityReport"]["nativeBinaryStatus"],
                "validated",
            )
            self.assertEqual(loader_summary["sourceInputs"], [])
            self.assertEqual(
                loader_summary["compilerInvocationRequired"],
                False,
            )
            self.assertEqual(
                loader_summary["deviceExecutionRequired"],
                False,
            )
            self.assertFalse(native_loader_plan.ready)
            self.assertIsNone(native_loader_plan.native_artifact)
            self.assertTrue(
                any(
                    diagnostic["code"] == "opengl_loader.native_mode_unsupported"
                    for diagnostic in native_loader_summary["rejectReasons"]
                )
            )
            self.assertEqual(descriptor_summary["sourcePath"], backend_source_path)
            self.assertEqual(descriptor_summary["artifactPath"], native_binary_path)
            self.assertEqual(descriptor_summary["nativeBinaryStatus"], "validated")
            self.assertEqual(descriptor_summary["validationStatus"], "validated")

            mutated_manifest = dict(manifest)
            mutated_requirements = dict(package_artifact_requirements)
            mutated_requirements["artifactFlavor"] = "compressed"
            mutated_manifest["packageArtifactRequirements"] = mutated_requirements
            manifest_path.write_text(
                json.dumps(mutated_manifest, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )

            with self._guard_crossgl_source_reads():
                evolved_report = read_compatibility_report(
                    package_dir,
                    loader_target="opengl",
                )
                evolved_loader_plan = plan_opengl_loader(package_dir)

            evolved_loader_summary = evolved_loader_plan.to_summary()
            evolved_reject_codes = [
                diagnostic.code for diagnostic in evolved_report.reject_reasons
            ]

            self.assertFalse(evolved_report.compatible)
            self.assertFalse(evolved_loader_plan.loadable)
            self.assertFalse(evolved_loader_plan.source_parsing_required)
            self.assertIn(
                "package.artifact_requirements.unexpected_field",
                evolved_reject_codes,
            )
            self.assertIsNone(evolved_report.target_contract)
            self.assertEqual(evolved_report.required_artifacts, ())
            self.assertEqual(evolved_loader_summary["sourceInputs"], [])
            self.assertEqual(evolved_loader_summary["selectedArtifacts"], [])
            self.assertEqual(
                evolved_loader_summary["metadataContract"]["sourceInputs"],
                [],
            )
            self.assertEqual(
                next(
                    diagnostic
                    for diagnostic in evolved_loader_summary["rejectReasons"]
                    if diagnostic["code"]
                    == "package.artifact_requirements.unexpected_field"
                )["path"],
                "packageArtifactRequirements.artifactFlavor",
            )
            self.assertEqual(list(package_dir.rglob("*.cgl")), [source_probe])
            self.assertIn(".comp.glsl", fake_tool_log.read_text(encoding="utf-8"))

    def test_emits_optional_graphics_abi_sidecar_for_graphics_package(
        self,
    ) -> None:
        cglc = self._require_cglc()
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir)
            fixture = (
                REPO_ROOT
                / "tests"
                / "opengl"
                / "fixtures"
                / "OpenGLGraphicsTextureSamplerResourcesShader.cgl"
            )
            input_path = temp_root / fixture.name
            input_path.write_text(fixture.read_text(encoding="utf-8"), encoding="utf-8")
            package_dir = temp_root / "OpenGLGraphicsTextureSamplerResourcesShader.cglb"
            fake_tool_dir = temp_root / "fake-toolchain"
            fake_tool_log = temp_root / "glslangValidator.log"
            self._write_fake_glslang_validator(fake_tool_dir)

            self._run_cglc_build(
                cglc,
                input_path=input_path,
                package_dir=package_dir,
                fake_tool_dir=fake_tool_dir,
                fake_tool_log=fake_tool_log,
            )
            input_path.unlink()

            manifest = json.loads(
                (package_dir / "manifest.json").read_text(encoding="utf-8")
            )
            artifacts = manifest["artifacts"]
            graphics_abi_path = (
                "backend/opengl/"
                "OpenGLGraphicsTextureSamplerResourcesShader.graphics-abi.json"
            )
            backend_source_path = artifacts["backendSource"]
            native_binary_path = artifacts["nativeBinary"]
            vertex_source_path = (
                "backend/opengl/OpenGLGraphicsTextureSamplerResourcesShader.vert.glsl"
            )
            fragment_source_path = (
                "backend/opengl/OpenGLGraphicsTextureSamplerResourcesShader.frag.glsl"
            )
            validated_vertex_path = (
                "backend/opengl/"
                "OpenGLGraphicsTextureSamplerResourcesShader.validated.vert.glsl"
            )
            validated_fragment_path = (
                "backend/opengl/"
                "OpenGLGraphicsTextureSamplerResourcesShader.validated.frag.glsl"
            )
            self.assertEqual(artifacts["graphicsAbi"], graphics_abi_path)
            self.assertNotIn(
                "graphicsAbi",
                manifest["packageArtifactRequirements"]["requiredPathArtifacts"],
            )
            self.assertTrue((package_dir / graphics_abi_path).is_file())
            self.assertTrue((package_dir / vertex_source_path).is_file())
            self.assertTrue((package_dir / fragment_source_path).is_file())
            self.assertTrue((package_dir / validated_vertex_path).is_file())
            self.assertTrue((package_dir / validated_fragment_path).is_file())
            source_inventory = (package_dir / backend_source_path).read_text(
                encoding="utf-8"
            )
            native_inventory = (package_dir / native_binary_path).read_text(
                encoding="utf-8"
            )
            self.assertIn(f"stage vertex: {vertex_source_path}", source_inventory)
            self.assertIn(f"stage fragment: {fragment_source_path}", source_inventory)
            self.assertIn(f"stage vertex: {validated_vertex_path}", native_inventory)
            self.assertIn(
                f"stage fragment: {validated_fragment_path}", native_inventory
            )
            vertex_source = (package_dir / vertex_source_path).read_text(
                encoding="utf-8"
            )
            fragment_source = (package_dir / fragment_source_path).read_text(
                encoding="utf-8"
            )
            self.assertIn("void main()", vertex_source)
            self.assertIn("gl_Position", vertex_source)
            self.assertIn("void main()", fragment_source)
            self.assertIn("crossgl_out_color", fragment_source)
            fake_log = fake_tool_log.read_text(encoding="utf-8")
            self.assertIn("-S vert", fake_log)
            self.assertIn(vertex_source_path, fake_log)
            self.assertIn("-S frag", fake_log)
            self.assertIn(fragment_source_path, fake_log)
            self.assertNotIn("-DCROSSGL_STAGE_VERTEX", fake_log)
            self.assertNotIn("-DCROSSGL_STAGE_FRAGMENT", fake_log)

            verifier = subprocess.run(
                [
                    sys.executable,
                    str(REPO_ROOT / "tools" / "verify_graphics_abi.py"),
                    "--input",
                    str(package_dir / graphics_abi_path),
                    "--json",
                ],
                cwd=REPO_ROOT,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
            )
            if verifier.returncode != 0:
                self.fail(
                    "graphics ABI verifier failed\n"
                    f"stdout:\n{verifier.stdout}\n"
                    f"stderr:\n{verifier.stderr}"
                )
            graphics_abi = json.loads(
                (package_dir / graphics_abi_path).read_text(encoding="utf-8")
            )
            verifier_report = json.loads(verifier.stdout)
            self.assertTrue(verifier_report["success"], verifier_report)
            self.assertEqual(verifier_report["summary"]["entryPointCount"], 2)
            self.assertEqual(verifier_report["summary"]["resourceCount"], 4)
            self.assertEqual(verifier_report["summary"]["abiRecordCount"], 4)
            self.assertEqual(verifier_report["summary"]["vertexInputCount"], 2)
            self.assertEqual(verifier_report["summary"]["varyingCount"], 2)
            self.assertEqual(verifier_report["summary"]["fragmentOutputCount"], 1)
            self.assertEqual(verifier_report["summary"]["builtinCount"], 1)
            self.assertEqual(
                graphics_abi["vertexInputs"],
                [
                    {
                        "stage": "vertex",
                        "entryPoint": "vertex_main",
                        "name": "position",
                        "type": "vec3",
                        "location": 0,
                        "format": "float32x3",
                    },
                    {
                        "stage": "vertex",
                        "entryPoint": "vertex_main",
                        "name": "texCoord",
                        "type": "vec2",
                        "location": 1,
                        "format": "float32x2",
                    },
                ],
            )
            self.assertEqual(
                graphics_abi["varyings"],
                [
                    {
                        "interpolation": "smooth",
                        "producer": {
                            "stage": "vertex",
                            "entryPoint": "vertex_main",
                            "name": "uv",
                            "type": "vec2",
                            "location": 0,
                            "direction": "output",
                        },
                        "consumer": {
                            "stage": "fragment",
                            "entryPoint": "fragment_main",
                            "name": "uv",
                            "type": "vec2",
                            "location": 0,
                            "direction": "input",
                        },
                    },
                    {
                        "interpolation": "smooth",
                        "producer": {
                            "stage": "vertex",
                            "entryPoint": "vertex_main",
                            "name": "tint",
                            "type": "vec4",
                            "location": 1,
                            "direction": "output",
                        },
                        "consumer": {
                            "stage": "fragment",
                            "entryPoint": "fragment_main",
                            "name": "tint",
                            "type": "vec4",
                            "location": 1,
                            "direction": "input",
                        },
                    },
                ],
            )
            self.assertEqual(
                graphics_abi["fragmentOutputs"],
                [
                    {
                        "stage": "fragment",
                        "entryPoint": "fragment_main",
                        "name": "color",
                        "type": "vec4",
                        "location": 0,
                        "format": "rgba32f",
                    }
                ],
            )
            self.assertEqual(
                graphics_abi["builtins"],
                [
                    {
                        "stage": "vertex",
                        "entryPoint": "vertex_main",
                        "name": "position",
                        "builtin": "position",
                        "type": "vec4",
                        "direction": "output",
                    }
                ],
            )

            with self._guard_crossgl_source_reads():
                package = read_package(package_dir)
                report = package.compatibility_report(loader_target="opengl")

            self.assertTrue(report.compatible, report.to_summary()["diagnostics"])
            self.assertIn(
                "graphicsAbi", [artifact.name for artifact in package.artifacts]
            )
            self.assertEqual(
                report.required_artifacts, ("backendSource", "nativeBinary")
            )

    def _require_cglc(self) -> Path:
        candidates = []
        if CGLC_ARG:
            candidates.append(CGLC_ARG)
        candidates.append("cglc")
        for candidate in candidates:
            path = Path(candidate)
            if path.is_file():
                return path.resolve()
            found = shutil.which(candidate)
            if found is not None:
                return Path(found).resolve()
        self.skipTest("cglc executable not supplied via --cglc, CGLC, or PATH")

    def _run_cglc_build(
        self,
        cglc: Path,
        *,
        input_path: Path,
        package_dir: Path,
        fake_tool_dir: Path,
        fake_tool_log: Path,
    ) -> None:
        env = os.environ.copy()
        env["PATH"] = str(fake_tool_dir) + os.pathsep + env.get("PATH", "")
        env["CROSSGL_DISABLE_TOOLCHAIN_FALLBACKS"] = "1"
        env["CROSSGL_FAKE_GLSLANG_LOG"] = str(fake_tool_log)
        result = subprocess.run(
            [
                str(cglc),
                "build",
                str(input_path),
                "--target",
                "opengl",
                "--output",
                str(package_dir),
                "--debug-ir",
            ],
            cwd=REPO_ROOT,
            env=env,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        if result.returncode != 0:
            self.fail(
                "cglc OpenGL package build failed\n"
                f"command: {cglc} build {input_path} --target opengl "
                f"--output {package_dir} --debug-ir\n"
                f"stdout:\n{result.stdout}\n"
                f"stderr:\n{result.stderr}"
            )

    def _write_fake_glslang_validator(self, tool_dir: Path) -> None:
        tool_dir.mkdir()
        if os.name == "nt":
            script = tool_dir / "glslangValidator.cmd"
            script.write_text(
                '@echo off\r\necho %*>>"%CROSSGL_FAKE_GLSLANG_LOG%"\r\nexit /b 0\r\n',
                encoding="utf-8",
            )
            return

        script = tool_dir / "glslangValidator"
        script.write_text(
            '#!/bin/sh\nprintf \'%s\\n\' "$*" >> "$CROSSGL_FAKE_GLSLANG_LOG"\nexit 0\n',
            encoding="utf-8",
        )
        script.chmod(script.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)

    @contextmanager
    def _guard_crossgl_source_reads(self) -> object:
        original_read_text = Path.read_text
        original_read_bytes = Path.read_bytes

        def guarded_read_text(path: Path, *args: object, **kwargs: object) -> str:
            if path.suffix == ".cgl":
                raise AssertionError(f"runtime parsed CrossGL source: {path}")
            return original_read_text(path, *args, **kwargs)

        def guarded_read_bytes(path: Path, *args: object, **kwargs: object) -> bytes:
            if path.suffix == ".cgl":
                raise AssertionError(f"runtime parsed CrossGL source: {path}")
            return original_read_bytes(path, *args, **kwargs)

        with mock.patch.object(Path, "read_text", guarded_read_text):
            with mock.patch.object(Path, "read_bytes", guarded_read_bytes):
                yield


if __name__ == "__main__":
    unittest.main()
