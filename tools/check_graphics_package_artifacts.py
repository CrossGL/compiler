#!/usr/bin/env python3
"""Probe graphics package artifact shape with a real package build."""

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


MODULE = "SimpleShader"
FIXTURE = Path("tests/fixtures/SimpleShader.cgl")
DIRECTX_GRAPHICS_RESOURCE_MODULE = "DirectXGraphicsResourceShader"
DIRECTX_GRAPHICS_RESOURCE_FIXTURE = Path(
    "tests/directx/fixtures/DirectXGraphicsResourceShader.cgl"
)
DEBUG_ARTIFACTS = ("debugMetadata", "hirSourceMap", "targetExplanation")
GRAPHICS_ABI_ARTIFACT = "graphicsAbi"
GRAPHICS_ABI_ARRAYS = (
    ("entryPoints", "entryPointCount"),
    ("vertexInputs", "vertexInputCount"),
    ("varyings", "varyingCount"),
    ("fragmentOutputs", "fragmentOutputCount"),
    ("builtins", "builtinCount"),
    ("resources", "resourceCount"),
    ("abiRecords", "abiRecordCount"),
)
STAGES = ("vertex", "fragment")

TARGETS = {
    "directx": {
        "always": True,
        "artifacts": {
            "backendSource": f"backend/directx/{MODULE}.graphics.hlsl",
            "nativeBinary": f"backend/directx/{MODULE}.dxil",
        },
        "source_artifact": "backendSource",
    },
    "opengl": {
        "always": True,
        "artifacts": {
            "backendSource": f"backend/opengl/{MODULE}.graphics.glsl",
            "nativeBinary": f"backend/opengl/{MODULE}.glsl",
        },
        "source_artifact": "backendSource",
    },
    "vulkan": {
        "tools": ("spirv-as", "spirv-val"),
        "artifacts": {
            "backendAssembly": f"backend/vulkan/{MODULE}.spvasm",
            "nativeBinary": f"backend/vulkan/{MODULE}.spv",
            "nativeProfile": f"backend/vulkan/{MODULE}.profile.json",
        },
        "source_artifact": "backendAssembly",
    },
    "metal": {
        "xcrun_tools": ("metal", "metallib"),
        "artifacts": {
            "backendSource": f"backend/metal/{MODULE}.metal",
            "intermediate": f"backend/metal/{MODULE}.air",
            "nativeBinary": f"backend/metal/{MODULE}.metallib",
        },
        "source_artifact": "backendSource",
    },
}


def run(command, *, cwd=None, env=None):
    return subprocess.run(
        [str(arg) for arg in command],
        cwd=cwd,
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )


def fail(errors, case_name, message):
    errors.append(f"{case_name}: {message}")


def load_json(path, errors, case_name):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except OSError as exc:
        fail(errors, case_name, f"failed to read {path}: {exc}")
    except json.JSONDecodeError as exc:
        fail(errors, case_name, f"{path} is not JSON: {exc}")
    return {}


def validate_schema(root, tmp_dir, schema_name, instance_text, case_name):
    instance = tmp_dir / f"{case_name}.{schema_name}.json"
    instance.write_text(instance_text, encoding="utf-8")
    result = run(
        [
            sys.executable,
            root / "tools" / "validate_json_schema.py",
            "--schema",
            root / "docs" / "schemas" / f"{schema_name}.schema.json",
            "--instance",
            instance,
        ]
    )
    if result.returncode != 0:
        return [
            f"{case_name}: {schema_name} schema validation failed: "
            f"{result.stderr}{result.stdout}".strip()
        ]
    return []


def has_xcrun_tool(tool):
    xcrun = shutil.which("xcrun")
    if not xcrun:
        return False
    result = run([xcrun, "-find", tool])
    return result.returncode == 0 and bool(result.stdout.strip())


def target_available(target, spec):
    if spec.get("always"):
        return True
    if "tools" in spec:
        return all(shutil.which(tool) for tool in spec["tools"])
    if "xcrun_tools" in spec:
        return sys.platform == "darwin" and all(
            has_xcrun_tool(tool) for tool in spec["xcrun_tools"]
        )
    return False


def artifact_record(records, name):
    for record in records:
        if isinstance(record, dict) and record.get("name") == name:
            return record
    return None


def expect_equal(errors, case_name, path, actual, expected):
    if actual != expected:
        fail(errors, case_name, f"expected {path}={expected!r}, got {actual!r}")


def expected_summary_native_binary_status(manifest, package):
    artifacts = manifest.get("artifacts", {})
    if not isinstance(artifacts, dict):
        return None

    manifest_status = artifacts.get("nativeBinaryStatus")
    if manifest_status is not None:
        return manifest_status

    if isinstance(manifest.get("packageArtifactRequirements"), dict):
        return None

    if manifest.get("target") == "metal":
        intermediate = artifacts.get("intermediate")
        native_binary = artifacts.get("nativeBinary")
        if (
            isinstance(intermediate, str)
            and isinstance(native_binary, str)
            and (package / intermediate).is_file()
            and (package / native_binary).is_file()
        ):
            return "emitted"
    return None


def expect_file(path, errors, case_name):
    if not path.is_file():
        fail(errors, case_name, f"expected file {path}")


def expect_artifact_paths(errors, case_name, package, manifest, reflection, spec):
    artifacts = manifest.get("artifacts")
    if not isinstance(artifacts, dict):
        fail(errors, case_name, "manifest.artifacts must be an object")
        return

    expected_artifacts = dict(spec["artifacts"])
    expected_artifacts.update(
        {
            "debugMetadata": "ir/debug-metadata.json",
            "hirSourceMap": "ir/hir-source-map.json",
            "targetExplanation": "ir/target-explanation.json",
            GRAPHICS_ABI_ARTIFACT: (
                f"backend/{manifest.get('target')}/"
                f"{manifest.get('module')}.graphics-abi.json"
            ),
        }
    )
    for name, expected_path in expected_artifacts.items():
        expect_equal(
            errors,
            case_name,
            f"manifest.artifacts.{name}",
            artifacts.get(name),
            expected_path,
        )
        if name != "nativeBinary" or artifacts.get("nativeBinaryStatus") != "planned":
            expect_file(package / expected_path, errors, case_name)

    native_binary = artifacts.get("nativeBinary")
    expect_equal(
        errors,
        case_name,
        "reflection.nativeBinary",
        reflection.get("nativeBinary"),
        native_binary,
    )
    if artifacts.get("nativeBinaryStatus") in ("planned", None):
        native_path = package / native_binary
        if artifacts.get("nativeBinaryStatus") == "planned" and native_path.exists():
            fail(
                errors,
                case_name,
                "planned nativeBinaryStatus should not leave a native binary file",
            )
    elif artifacts.get("nativeBinaryStatus") in ("emitted", "validated"):
        expect_file(package / native_binary, errors, case_name)
    elif "nativeBinaryStatus" in artifacts:
        fail(
            errors,
            case_name,
            f"unexpected nativeBinaryStatus {artifacts.get('nativeBinaryStatus')!r}",
        )
    if manifest.get("target") == "vulkan":
        profile_path = artifacts.get("nativeProfile")
        profile = load_json(package / profile_path, errors, case_name)
        if isinstance(profile, dict):
            expect_equal(
                errors,
                case_name,
                "nativeProfile.target",
                profile.get("target"),
                "vulkan",
            )
            expect_equal(
                errors,
                case_name,
                "nativeProfile.api",
                profile.get("api"),
                "vulkan",
            )
            expect_equal(
                errors,
                case_name,
                "nativeProfile.artifacts.nativeBinary",
                profile.get("artifacts", {}).get("nativeBinary"),
                native_binary,
            )


def expect_graphics_reflection(errors, case_name, reflection, target, module=MODULE):
    expect_equal(
        errors,
        case_name,
        "reflection.schemaVersion",
        reflection.get("schemaVersion"),
        1,
    )
    expect_equal(
        errors, case_name, "reflection.target", reflection.get("target"), target
    )
    expect_equal(
        errors, case_name, "reflection.module", reflection.get("module"), module
    )

    entry_points = reflection.get("entryPoints")
    if not isinstance(entry_points, list):
        fail(errors, case_name, "reflection.entryPoints must be an array")
        return
    actual_stages = [
        entry.get("stage") for entry in entry_points if isinstance(entry, dict)
    ]
    expect_equal(
        errors, case_name, "reflection.entryPoints stages", actual_stages, list(STAGES)
    )
    for stage, entry in zip(STAGES, entry_points):
        if not isinstance(entry, dict):
            fail(errors, case_name, f"entry point for {stage} must be an object")
            continue
        expect_equal(
            errors,
            case_name,
            f"{stage}.backendName",
            entry.get("backendName"),
            f"{stage}_main",
        )

    vertex_layouts = reflection.get("vertexLayouts")
    if not isinstance(vertex_layouts, list) or not vertex_layouts:
        fail(errors, case_name, "expected at least one vertex layout")
    else:
        expect_equal(
            errors,
            case_name,
            "vertexLayouts[0].entryPoint",
            vertex_layouts[0].get("entryPoint"),
            "vertex_main",
        )

    if reflection.get("workgroupSizes") not in ([], None):
        fail(errors, case_name, "graphics package should not declare workgroupSizes")


def expect_directx_graphics_resource_alignment(errors, case_name, reflection):
    expected = [
        (
            "transform",
            "vertex",
            "uniform",
            "Transform",
            "ConstantBuffer<Transform>",
            "constant-buffer",
            "CBV",
            "constant-buffer",
            0,
        ),
        (
            "material",
            "fragment",
            "uniform",
            "Material",
            "ConstantBuffer<Material>",
            "constant-buffer",
            "CBV",
            "constant-buffer",
            1,
        ),
        (
            "colorMap",
            "fragment",
            "texture",
            "sampler2D",
            "Texture2D<float4>",
            "srv",
            "SRV",
            "shader-resource",
            2,
        ),
        (
            "linearSampler",
            "fragment",
            "sampler",
            "sampler",
            "SamplerState",
            "sampler",
            "Sampler",
            "sampler",
            3,
        ),
    ]
    resources = reflection.get("resources")
    target_bindings = reflection.get("targetResourceBindings")
    if not isinstance(resources, list):
        fail(errors, case_name, "reflection.resources must be an array")
        return
    if not isinstance(target_bindings, list):
        fail(errors, case_name, "reflection.targetResourceBindings must be an array")
        return
    expect_equal(
        errors,
        case_name,
        "reflection.resources count",
        len(resources),
        len(expected),
    )
    expect_equal(
        errors,
        case_name,
        "reflection.targetResourceBindings count",
        len(target_bindings),
        len(expected),
    )

    resources_by_name = {
        record.get("name"): record for record in resources if isinstance(record, dict)
    }
    bindings_by_name = {
        record.get("name"): record
        for record in target_bindings
        if isinstance(record, dict)
    }
    for (
        name,
        stage,
        kind,
        source_type,
        hlsl_type,
        binding_class,
        descriptor_type,
        address_space,
        binding,
    ) in expected:
        resource = resources_by_name.get(name)
        target_binding = bindings_by_name.get(name)
        if resource is None:
            fail(errors, case_name, f"reflection.resources missing {name}")
            continue
        if target_binding is None:
            fail(
                errors,
                case_name,
                f"reflection.targetResourceBindings missing {name}",
            )
            continue
        for field, value in (
            ("stage", stage),
            ("kind", kind),
            ("type", source_type),
            ("set", 0),
            ("binding", binding),
        ):
            expect_equal(
                errors,
                case_name,
                f"reflection.resources[{name}].{field}",
                resource.get(field),
                value,
            )
        for field, value in (
            ("target", "directx"),
            ("stage", stage),
            ("entryPoint", f"{stage}_main"),
            ("kind", kind),
            ("sourceType", source_type),
            ("hlslType", hlsl_type),
            ("addressSpace", address_space),
            ("abi", "registerBinding"),
            ("bindingClass", binding_class),
            ("descriptorType", descriptor_type),
            ("argumentIndex", binding),
            ("set", resource.get("set")),
            ("binding", resource.get("binding")),
        ):
            expect_equal(
                errors,
                case_name,
                f"reflection.targetResourceBindings[{name}].{field}",
                target_binding.get(field),
                value,
            )


def expect_directx_graphics_dxil_bundle(errors, case_name, package, native_path):
    if not isinstance(native_path, str):
        fail(errors, case_name, "manifest.artifacts.nativeBinary must be a string")
        return
    bundle_path = package / native_path
    try:
        bundle = bundle_path.read_text(encoding="utf-8")
    except OSError as exc:
        fail(errors, case_name, f"failed to read DXIL bundle {bundle_path}: {exc}")
        return
    for fragment in (
        "CrossGL DirectX graphics DXIL bundle v1\n",
        f"stage vertex file {DIRECTX_GRAPHICS_RESOURCE_MODULE}.vertex.dxil",
        f"stage fragment file {DIRECTX_GRAPHICS_RESOURCE_MODULE}.fragment.dxil",
        "fake dxil",
    ):
        if fragment not in bundle:
            fail(
                errors,
                case_name,
                f"expected DXIL bundle to contain {fragment!r}",
            )


def expected_graphics_abi_summary(sidecar):
    summary = {
        "module": sidecar.get("module"),
        "target": sidecar.get("target"),
    }
    for array_name, summary_name in GRAPHICS_ABI_ARRAYS:
        value = sidecar.get(array_name)
        summary[summary_name] = len(value) if isinstance(value, list) else None
    return summary


def expect_graphics_abi_report(
    errors, case_name, package, manifest, report, report_name
):
    artifacts = manifest.get("artifacts", {})
    path = artifacts.get(GRAPHICS_ABI_ARTIFACT)
    if not isinstance(path, str):
        fail(errors, case_name, f"manifest.artifacts.{GRAPHICS_ABI_ARTIFACT} missing")
        return

    sidecar = load_json(package / path, errors, case_name)
    graphics_abi = report.get("graphicsAbi")
    if not isinstance(graphics_abi, dict):
        fail(errors, case_name, f"{report_name}.graphicsAbi must be an object")
        return

    expect_equal(
        errors,
        case_name,
        f"{report_name}.graphicsAbi.artifactPresent",
        graphics_abi.get("artifactPresent"),
        True,
    )
    expect_equal(
        errors,
        case_name,
        f"{report_name}.graphicsAbi.path",
        graphics_abi.get("path"),
        path,
    )
    expect_equal(
        errors,
        case_name,
        f"{report_name}.graphicsAbi.exists",
        graphics_abi.get("exists"),
        True,
    )
    expect_equal(
        errors,
        case_name,
        f"{report_name}.graphicsAbi.health",
        graphics_abi.get("health"),
        "ok",
    )
    expect_equal(
        errors,
        case_name,
        f"{report_name}.graphicsAbi.validation",
        graphics_abi.get("validation"),
        "lightweight-structural",
    )
    expect_equal(
        errors,
        case_name,
        f"{report_name}.graphicsAbi.schemaVersion",
        graphics_abi.get("schemaVersion"),
        1,
    )
    expect_equal(
        errors,
        case_name,
        f"{report_name}.graphicsAbi.summary",
        graphics_abi.get("summary"),
        expected_graphics_abi_summary(sidecar),
    )
    expect_equal(
        errors,
        case_name,
        f"{report_name}.graphicsAbi.diagnosticCounts",
        graphics_abi.get("diagnosticCounts"),
        {"note": 0, "warning": 0, "error": 0},
    )
    expect_equal(
        errors,
        case_name,
        f"{report_name}.graphicsAbi.diagnostics",
        graphics_abi.get("diagnostics"),
        [],
    )


def expect_inspect(
    errors, root, tmp_dir, cglc, case_name, package, manifest, reflection, spec
):
    result = run([cglc, "package", "inspect", package, "--json"])
    if result.returncode != 0:
        fail(
            errors,
            case_name,
            f"package inspect failed: {result.stderr}{result.stdout}".strip(),
        )
        return
    errors.extend(
        validate_schema(root, tmp_dir, "package-inspect-v1", result.stdout, case_name)
    )
    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        fail(errors, case_name, f"inspect output is not JSON: {exc}")
        return

    expect_equal(
        errors, case_name, "inspect.manifest", payload.get("manifest"), manifest
    )
    expect_equal(
        errors, case_name, "inspect.reflection", payload.get("reflection"), reflection
    )

    summary = payload.get("summary", {})
    expect_equal(
        errors,
        case_name,
        "inspect.summary.module",
        summary.get("module"),
        manifest.get("module"),
    )
    expect_equal(
        errors,
        case_name,
        "inspect.summary.target",
        summary.get("target"),
        manifest.get("target"),
    )
    expect_equal(
        errors,
        case_name,
        "inspect.summary.nativeBinaryStatus",
        summary.get("nativeBinaryStatus"),
        expected_summary_native_binary_status(manifest, package),
    )
    expect_graphics_abi_report(errors, case_name, package, manifest, payload, "inspect")

    records = payload.get("artifacts")
    if not isinstance(records, list):
        fail(errors, case_name, "inspect.artifacts must be an array")
        return

    for name, expected_path in spec["artifacts"].items():
        record = artifact_record(records, name)
        if record is None:
            fail(errors, case_name, f"inspect.artifacts missing {name}")
            continue
        expect_equal(
            errors,
            case_name,
            f"inspect.artifacts.{name}.path",
            record.get("path"),
            expected_path,
        )
        expected_exists = name != "nativeBinary" or (
            manifest.get("artifacts", {}).get("nativeBinaryStatus") != "planned"
        )
        expect_equal(
            errors,
            case_name,
            f"inspect.artifacts.{name}.exists",
            record.get("exists"),
            expected_exists,
        )

    for name in DEBUG_ARTIFACTS:
        record = artifact_record(records, name)
        if record is None:
            fail(errors, case_name, f"inspect.artifacts missing {name}")
        else:
            expect_equal(
                errors,
                case_name,
                f"inspect.artifacts.{name}.exists",
                record.get("exists"),
                True,
            )
    if manifest.get("target") == "vulkan":
        profile = payload.get("vulkanNativeProfile", {})
        expect_equal(
            errors,
            case_name,
            "inspect.vulkanNativeProfile.health",
            profile.get("health"),
            "ok",
        )
        expect_equal(
            errors,
            case_name,
            "inspect.vulkanNativeProfile.spirvVersion",
            profile.get("spirvVersion"),
            "1.0",
        )


def expect_verify(errors, root, tmp_dir, cglc, case_name, package, source, manifest):
    result = run([cglc, "package", "verify", package, "--source", source, "--json"])
    if result.returncode != 0:
        fail(
            errors,
            case_name,
            f"package verify failed: {result.stderr}{result.stdout}".strip(),
        )
        return
    errors.extend(
        validate_schema(root, tmp_dir, "package-verify-v1", result.stdout, case_name)
    )
    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        fail(errors, case_name, f"verify output is not JSON: {exc}")
        return
    expect_equal(errors, case_name, "verify.success", payload.get("success"), True)
    expect_graphics_abi_report(errors, case_name, package, manifest, payload, "verify")
    summary = payload.get("summary", {})
    expect_equal(
        errors,
        case_name,
        "verify.summary.module",
        summary.get("module"),
        manifest.get("module"),
    )
    expect_equal(
        errors,
        case_name,
        "verify.summary.target",
        summary.get("target"),
        manifest.get("target"),
    )
    expect_equal(
        errors,
        case_name,
        "verify.summary.nativeBinaryStatus",
        summary.get("nativeBinaryStatus"),
        expected_summary_native_binary_status(manifest, package),
    )
    expected_artifact_count = len(
        [name for name in manifest.get("artifacts", {}) if name != "nativeBinaryStatus"]
    )
    expect_equal(
        errors,
        case_name,
        "verify.summary.artifactCount",
        summary.get("artifactCount"),
        expected_artifact_count,
    )
    expect_equal(
        errors,
        case_name,
        "verify.diagnosticCounts.error",
        payload.get("diagnosticCounts", {}).get("error"),
        0,
    )


def fake_dxc_environment(tool_dir):
    tool_dir.mkdir(parents=True, exist_ok=True)
    env = os.environ.copy()
    env["PATH"] = f"{tool_dir}{os.pathsep}{env.get('PATH', '')}"
    env["CROSSGL_DISABLE_TOOLCHAIN_FALLBACKS"] = "1"

    if os.name == "nt":
        dxc = tool_dir / "dxc.cmd"
        dxc.write_text(
            "@echo off\r\n"
            "set output=\r\n"
            ":loop\r\n"
            'if "%~1"=="" goto done\r\n'
            'if "%~1"=="-Fo" (\r\n'
            "  set output=%~2\r\n"
            "  shift\r\n"
            "  shift\r\n"
            "  goto loop\r\n"
            ")\r\n"
            "shift\r\n"
            "goto loop\r\n"
            ":done\r\n"
            'if "%output%"=="" exit /b 2\r\n'
            '> "%output%" echo fake dxil\r\n'
            "exit /b 0\r\n",
            encoding="utf-8",
        )
    else:
        dxc = tool_dir / "dxc"
        dxc.write_text(
            "#!/bin/sh\n"
            "output=\n"
            'while [ "$#" -gt 0 ]; do\n'
            '  if [ "$1" = "-Fo" ]; then\n'
            '    output="$2"\n'
            "    shift 2\n"
            "    continue\n"
            "  fi\n"
            "  shift\n"
            "done\n"
            'if [ -z "$output" ]; then\n'
            "  exit 2\n"
            "fi\n"
            "printf 'fake dxil\\n' > \"$output\"\n",
            encoding="utf-8",
        )
        dxc.chmod(0o755)

    return env


def probe_target(root, tmp_dir, cglc, target, spec):
    case_name = f"{target}-graphics-package-artifacts"
    package = tmp_dir / f"{target}-SimpleShader.cglb"
    source = root / FIXTURE
    result = run(
        [
            cglc,
            "build",
            source,
            "--target",
            target,
            "--output",
            package,
            "--debug-ir",
        ]
    )
    if result.returncode != 0:
        return [f"{case_name}: build failed: {result.stderr}{result.stdout}".strip()]

    errors = []
    manifest = load_json(package / "manifest.json", errors, case_name)
    reflection = load_json(package / "reflection.json", errors, case_name)
    diagnostics = load_json(package / "diagnostics.json", errors, case_name)

    expect_equal(
        errors, case_name, "manifest.schemaVersion", manifest.get("schemaVersion"), 1
    )
    expect_equal(errors, case_name, "manifest.target", manifest.get("target"), target)
    expect_equal(errors, case_name, "manifest.module", manifest.get("module"), MODULE)
    if diagnostics.get("diagnostics") is None:
        fail(errors, case_name, "diagnostics.diagnostics must be present")

    expect_artifact_paths(errors, case_name, package, manifest, reflection, spec)
    expect_graphics_reflection(errors, case_name, reflection, target)
    expect_inspect(
        errors, root, tmp_dir, cglc, case_name, package, manifest, reflection, spec
    )
    expect_verify(errors, root, tmp_dir, cglc, case_name, package, source, manifest)
    return errors


def probe_directx_graphics_fake_dxc(root, tmp_dir, cglc):
    case_name = "directx-graphics-package-artifacts-fake-dxc-emitted"
    package = tmp_dir / "directx-graphics-resource-fake-dxc.cglb"
    source = root / DIRECTX_GRAPHICS_RESOURCE_FIXTURE
    spec = {
        "artifacts": {
            "backendSource": (
                f"backend/directx/{DIRECTX_GRAPHICS_RESOURCE_MODULE}.graphics.hlsl"
            ),
            "nativeBinary": f"backend/directx/{DIRECTX_GRAPHICS_RESOURCE_MODULE}.dxil",
        },
        "source_artifact": "backendSource",
    }
    result = run(
        [
            cglc,
            "build",
            source,
            "--target",
            "directx",
            "--output",
            package,
            "--debug-ir",
        ],
        env=fake_dxc_environment(tmp_dir / "fake-dxc"),
    )
    if result.returncode != 0:
        return [f"{case_name}: build failed: {result.stderr}{result.stdout}".strip()]

    errors = []
    manifest = load_json(package / "manifest.json", errors, case_name)
    reflection = load_json(package / "reflection.json", errors, case_name)
    diagnostics = load_json(package / "diagnostics.json", errors, case_name)
    artifacts = manifest.get("artifacts", {})

    expect_equal(
        errors, case_name, "manifest.schemaVersion", manifest.get("schemaVersion"), 1
    )
    expect_equal(
        errors, case_name, "manifest.target", manifest.get("target"), "directx"
    )
    expect_equal(
        errors,
        case_name,
        "manifest.module",
        manifest.get("module"),
        DIRECTX_GRAPHICS_RESOURCE_MODULE,
    )
    expect_equal(
        errors,
        case_name,
        "manifest.artifacts.nativeBinaryStatus",
        artifacts.get("nativeBinaryStatus"),
        "emitted",
    )
    expect_equal(
        errors,
        case_name,
        "diagnostics.diagnostics severities/codes",
        [
            (record.get("severity"), record.get("code"))
            for record in diagnostics.get("diagnostics", [])
            if isinstance(record, dict)
        ],
        [
            ("note", "directx.source-package-emitted"),
            ("note", "directx.dxil-emitted"),
        ],
    )

    expect_artifact_paths(errors, case_name, package, manifest, reflection, spec)
    expect_graphics_reflection(
        errors,
        case_name,
        reflection,
        "directx",
        module=DIRECTX_GRAPHICS_RESOURCE_MODULE,
    )
    expect_directx_graphics_resource_alignment(errors, case_name, reflection)
    expect_directx_graphics_dxil_bundle(
        errors, case_name, package, artifacts.get("nativeBinary")
    )
    expect_inspect(
        errors, root, tmp_dir, cglc, case_name, package, manifest, reflection, spec
    )
    expect_verify(errors, root, tmp_dir, cglc, case_name, package, source, manifest)
    return errors


def parse_args():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", required=True, type=Path)
    parser.add_argument("--cglc", required=True, type=Path)
    parser.add_argument(
        "--targets",
        nargs="*",
        choices=sorted(TARGETS),
        default=sorted(TARGETS),
        help="targets to consider; native-only targets are skipped without tools",
    )
    return parser.parse_args()


def main():
    args = parse_args()
    root = args.root.resolve()
    cglc = args.cglc.resolve()
    errors = []
    probed = []
    skipped = []

    with tempfile.TemporaryDirectory(prefix="crossgl-graphics-package-") as tmp:
        tmp_dir = Path(tmp)
        for target in args.targets:
            spec = TARGETS[target]
            if not target_available(target, spec):
                skipped.append(target)
                continue
            target_errors = probe_target(root, tmp_dir, cglc, target, spec)
            if target_errors:
                errors.extend(target_errors)
            else:
                probed.append(target)
        if "directx" in args.targets:
            target_errors = probe_directx_graphics_fake_dxc(root, tmp_dir, cglc)
            if target_errors:
                errors.extend(target_errors)
            else:
                probed.append("directx-fake-dxc-emitted")

    for required_target in ("directx", "opengl"):
        if required_target in args.targets and required_target not in probed:
            fail(
                errors, "graphics-package-artifacts", f"did not probe {required_target}"
            )

    if errors:
        for error in errors:
            print(f"graphics package artifact probe failed: {error}", file=sys.stderr)
        if skipped:
            print(
                f"skipped optional native targets: {', '.join(skipped)}",
                file=sys.stderr,
            )
        return 1

    message = f"validated graphics package artifacts for: {', '.join(probed)}"
    if skipped:
        message += f" (skipped optional native targets: {', '.join(skipped)})"
    print(message)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
