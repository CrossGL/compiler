#!/usr/bin/env python3
"""Exercise the local package release publish happy path."""

import argparse
import hashlib
import json
import os
import re
import shutil
import shlex
import subprocess
import sys
import tempfile
from pathlib import Path, PureWindowsPath


COMPUTE_PACKAGE_FIXTURES = (
    {
        "manifest_entry_id": None,
        "source": "tests/fixtures/MinimalComputeShader.cgl",
        "package_name": "MinimalComputeShader.cglb",
        "target": "vulkan",
        "command_profile": "native-package-build",
        "package_mode": "native",
        "allowed_native_binary_statuses": (None,),
    },
    {
        "manifest_entry_id": None,
        "source": "tests/fixtures/StorageBufferComputeShader.cgl",
        "package_name": "StorageBufferComputeShader.cglb",
        "target": "vulkan",
        "command_profile": "native-package-build",
        "package_mode": "native",
        "allowed_native_binary_statuses": (None,),
    },
)
GRAPHICS_PACKAGE_FIXTURES = (
    {
        "manifest_entry_id": "graphics-stages.directx-basic-source-package",
        "source": "tests/fixtures/SimpleShader.cgl",
        "package_name": "gfx-dx-basic.cglb",
        "target": "directx",
        "command_profile": "source-package-build",
        "package_mode": "source-package",
        "allowed_native_binary_statuses": ("planned", "emitted"),
        "evidence_tests": ("cglc_build_directx_graphics_source_package",),
        "target_feature_evidence_tests": (),
    },
    {
        "manifest_entry_id": (
            "graphics-stages.directx-storage-buffer-resources-source-package"
        ),
        "source": (
            "tests/directx/fixtures/DirectXGraphicsStorageBufferResourceShader.cgl"
        ),
        "package_name": "gfx-dx-storage.cglb",
        "module_alias": "DxStorageBufferShader",
        "target": "directx",
        "command_profile": "source-package-build",
        "package_mode": "source-package",
        "allowed_native_binary_statuses": ("planned", "emitted"),
        "evidence_tests": (
            "cglc_build_directx_graphics_storage_buffer_resources_source_package",
        ),
        "target_feature_evidence_tests": (
            "cglc_build_directx_graphics_resource_unsupported_planned_failure",
            "cglc_doctor_json_directx_graphics_storage_buffer_source_package_evidence",
            "cglc_explain_targets_directx_graphics_storage_buffer_source_package_evidence",
        ),
    },
    {
        "manifest_entry_id": "graphics-stages.metal-descriptor-array-native",
        "source": "tests/metal/fixtures/MetalGraphicsDescriptorArrayShader.cgl",
        "package_name": "gfx-metal-desc-array.cglb",
        "module_alias": "MetalDescArrayShader",
        "target": "metal",
        "command_profile": "native-package-build",
        "package_mode": "native",
        "allowed_native_binary_statuses": (None,),
        "evidence_tests": ("cglc_build_metal_graphics_descriptor_array_native",),
        "target_feature_evidence_tests": (
            "cglc_doctor_json_metal_graphics_descriptor_array_native_evidence",
            "cglc_explain_targets_metal_graphics_descriptor_array_native_evidence",
        ),
    },
    {
        "manifest_entry_id": "graphics-stages.opengl-basic-source-package",
        "source": "tests/fixtures/SimpleShader.cgl",
        "package_name": "gfx-gl-basic.cglb",
        "target": "opengl",
        "command_profile": "source-package-build",
        "package_mode": "source-package",
        "allowed_native_binary_statuses": ("planned", "validated"),
        "evidence_tests": ("cglc_build_opengl_graphics_source_package",),
        "target_feature_evidence_tests": (),
    },
    {
        "manifest_entry_id": (
            "graphics-stages.opengl-descriptor-array-resources-source-package"
        ),
        "source": (
            "tests/opengl/fixtures/OpenGLGraphicsDescriptorArrayResourcesShader.cgl"
        ),
        "package_name": "gfx-gl-desc-array.cglb",
        "module_alias": "GLDescArrayResourceShader",
        "target": "opengl",
        "command_profile": "source-package-build",
        "package_mode": "source-package",
        "allowed_native_binary_statuses": ("planned", "validated"),
        "evidence_tests": (
            "cglc_build_opengl_graphics_descriptor_array_resources_source_package",
        ),
        "target_feature_evidence_tests": (
            "cglc_doctor_json_opengl_graphics_descriptor_array_source_package_evidence",
            "cglc_explain_targets_opengl_graphics_descriptor_array_source_package_evidence",
        ),
    },
    {
        "manifest_entry_id": (
            "graphics-stages.vulkan-texture-sampler-descriptor-array-native"
        ),
        "source": (
            "tests/vulkan/fixtures/"
            "VulkanGraphicsTextureSamplerDescriptorArrayShader.cgl"
        ),
        "package_name": "gfx-vk-tex-sampler-array.cglb",
        "module_alias": "VkTextureSamplerArrayShader",
        "target": "vulkan",
        "command_profile": "native-package-build",
        "package_mode": "native",
        "allowed_native_binary_statuses": (None,),
        "evidence_tests": (
            "cglc_build_vulkan_graphics_texture_sampler_descriptor_array_native",
            "cglc_build_vulkan_graphics_texture_sampler_descriptor_array_spvasm_native",
        ),
        "target_feature_evidence_tests": (),
    },
)
PACKAGE_FIXTURES = COMPUTE_PACKAGE_FIXTURES + GRAPHICS_PACKAGE_FIXTURES
GCS_BUCKET = "crossgl-release-dry-run"
GCS_PREFIX = "compiler/packages"
WINDOWS_STAGE_PATH_LIMIT = 259
WINDOWS_CI_STAGE_ROOT = PureWindowsPath(
    "D:/a/compiler/compiler/build/package-release-publish-flow/package-release-stage"
)
RC_HANDOFF_EVIDENCE_KIND = "crossgl-release-publish-rc-handoff-evidence-v1"
LIVE_CLOUD_UPLOAD_ENV = "CROSSGL_ALLOW_LIVE_CLOUD_RELEASE_UPLOAD"
LOCAL_ONLY_GUARDRAIL_MODE = "local-only"
DRY_RUN_GUARDRAIL_MODE = "dry-run"
MOCK_GUARDRAIL_MODE = "mock"
LIVE_CLOUD_GUARDRAIL_MODE = "live-cloud"
SAFE_GUARDRAIL_MODES = (
    DRY_RUN_GUARDRAIL_MODE,
    LOCAL_ONLY_GUARDRAIL_MODE,
    MOCK_GUARDRAIL_MODE,
)
LIVE_CLOUD_APPROVAL_STRING_FIELDS = (
    "approvalRecord",
    "projectAllowlistEntry",
    "bucketAllowlistEntry",
    "budgetGuardrail",
    "lifecyclePolicy",
)
LIVE_CLOUD_APPROVAL_PLACEHOLDERS = {
    "",
    "tbd",
    "todo",
    "none",
    "n/a",
    "placeholder",
}
NATIVE_ARTIFACT_DESCRIPTOR = "nativeArtifactDescriptor"
NATIVE_BINARY = "nativeBinary"
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
SHADER_DECL_RE = re.compile(r"(?m)^shader\s+([A-Za-z_][A-Za-z0-9_]*)\s*\{")
URI_LIKE_EVIDENCE_RE = re.compile(r"^[A-Za-z][A-Za-z0-9+.-]*://")
RC_HANDOFF_SCALAR_PATH_FIELDS = (
    "provenanceManifestPath",
    "artifactInventoryPath",
    "guardrailRecordPath",
    "uploadManifestPath",
    "preflightReportPath",
)
RC_HANDOFF_LIST_PATH_FIELDS = (
    "dryRunReceiptPaths",
    "mockReceiptPaths",
    "fakeGcloudReceiptPaths",
)


class CheckError(RuntimeError):
    pass


def display_command(command):
    return " ".join(str(part) for part in command)


def display_local_path(root, path):
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return path.name


def local_evidence_path(path):
    return path.resolve().as_posix()


def excerpt(text, limit=4000):
    if len(text) <= limit:
        return text
    return text[:limit] + f"\n... truncated {len(text) - limit} chars ..."


def run_checked(label, command, *, cwd, env=None, stdout_path=None):
    command = [str(part) for part in command]
    print(f"[{label}] {display_command(command)}")
    result = subprocess.run(
        command,
        cwd=cwd,
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if stdout_path is not None:
        stdout_path.parent.mkdir(parents=True, exist_ok=True)
        stdout_path.write_text(result.stdout, encoding="utf-8")
    if result.returncode != 0:
        details = [
            f"{label}: command failed with exit code {result.returncode}",
            f"command: {display_command(command)}",
        ]
        if result.stdout:
            details.append("stdout:\n" + excerpt(result.stdout).rstrip())
        if result.stderr:
            details.append("stderr:\n" + excerpt(result.stderr).rstrip())
        raise CheckError("\n".join(details))
    if result.stderr:
        print(f"[{label}] stderr:\n{excerpt(result.stderr).rstrip()}")
    return result


def run_expect_failure(label, command, *, cwd, expected):
    command = [str(part) for part in command]
    print(f"[{label}] {display_command(command)}")
    result = subprocess.run(
        command,
        cwd=cwd,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    output = result.stdout + result.stderr
    if result.returncode == 0:
        raise CheckError(f"{label}: expected command failure")
    if expected not in output:
        details = [
            f"{label}: expected failure output containing {expected!r}",
            f"command: {display_command(command)}",
        ]
        if result.stdout:
            details.append("stdout:\n" + excerpt(result.stdout).rstrip())
        if result.stderr:
            details.append("stderr:\n" + excerpt(result.stderr).rstrip())
        raise CheckError("\n".join(details))
    return result


def load_json(path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise CheckError(f"failed to read JSON from {path}: {exc}") from exc


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")


def sha256_file(path):
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def env_flag_enabled(env, name):
    value = env.get(name)
    return isinstance(value, str) and value.strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


def is_placeholder_text(value):
    stripped = value.strip()
    lower = stripped.lower()
    return (
        not stripped
        or lower in LIVE_CLOUD_APPROVAL_PLACEHOLDERS
        or lower.startswith("placeholder")
        or (stripped.startswith("<") and stripped.endswith(">"))
    )


def is_normalized_relative_path(value):
    if not isinstance(value, str) or value == "":
        return False
    if "\\" in value or value.startswith("/"):
        return False
    parts = value.split("/")
    return not any(part in {"", ".", ".."} for part in parts)


def explicit_text_error(path, value, label):
    if not isinstance(value, str):
        return f"{path}: expected string {label}"
    if is_placeholder_text(value):
        return f"{path}: expected explicit {label}, got placeholder"
    return None


def live_cloud_approval_evidence_errors(evidence):
    errors = []
    if not isinstance(evidence, dict):
        return ["approvalEvidence: expected object"]

    for field in LIVE_CLOUD_APPROVAL_STRING_FIELDS:
        error = explicit_text_error(field, evidence.get(field), field)
        if error is not None:
            errors.append(error)

    prefix_error = explicit_text_error(
        "releaseObjectPrefix",
        evidence.get("releaseObjectPrefix"),
        "releaseObjectPrefix",
    )
    if prefix_error is not None:
        errors.append(prefix_error)
    elif not is_normalized_relative_path(evidence["releaseObjectPrefix"]):
        errors.append("releaseObjectPrefix: expected normalized release-scoped prefix")

    receipt_paths = evidence.get("auditReceiptPaths")
    if not isinstance(receipt_paths, list) or not receipt_paths:
        errors.append("auditReceiptPaths: expected non-empty list")
    else:
        for index, receipt_path in enumerate(receipt_paths):
            error = explicit_text_error(
                f"auditReceiptPaths[{index}]",
                receipt_path,
                "audit receipt path",
            )
            if error is not None:
                errors.append(error)
            elif not is_normalized_relative_path(receipt_path):
                errors.append(
                    f"auditReceiptPaths[{index}]: expected normalized relative path"
                )
    return errors


def sample_live_cloud_approval_evidence():
    return {
        "approvalRecord": "release-approval-2026-06-01",
        "projectAllowlistEntry": "gcp-project:crossgl-release-prod",
        "bucketAllowlistEntry": "gcs-bucket:crossgl-release-artifacts",
        "budgetGuardrail": "budget:crossgl-release-prod:v0",
        "releaseObjectPrefix": "compiler/releases/v0.1.0",
        "lifecyclePolicy": "lifecycle:release-artifacts-retain-90d",
        "auditReceiptPaths": [
            "package-release-publish-upload-batch.json",
            "package-release-publish-upload-receipt.json",
        ],
    }


def release_publish_guardrail_record(
    *,
    operation,
    target_kind,
    dry_run=False,
    local_only=False,
    mock_upload=False,
    allow_live_cloud_upload=False,
    approval_evidence=None,
    env=None,
):
    env = os.environ if env is None else env
    env_allows_live_cloud = env_flag_enabled(env, LIVE_CLOUD_UPLOAD_ENV)
    live_cloud_upload_allowed = bool(allow_live_cloud_upload or env_allows_live_cloud)
    if local_only:
        mode = LOCAL_ONLY_GUARDRAIL_MODE
    elif dry_run:
        mode = DRY_RUN_GUARDRAIL_MODE
    elif mock_upload:
        mode = MOCK_GUARDRAIL_MODE
    else:
        mode = LIVE_CLOUD_GUARDRAIL_MODE

    opt_in = None
    if allow_live_cloud_upload:
        opt_in = "cli-flag"
    elif env_allows_live_cloud:
        opt_in = LIVE_CLOUD_UPLOAD_ENV

    record = {
        "schemaVersion": 1,
        "operation": operation,
        "targetKind": target_kind,
        "mode": mode,
        "dryRun": bool(dry_run),
        "localOnly": bool(local_only),
        "mockUpload": bool(mock_upload),
        "liveCloudUploadAllowed": live_cloud_upload_allowed,
        "liveCloudUploadOptIn": opt_in,
    }
    if approval_evidence is not None:
        record["approvalEvidence"] = approval_evidence
    return record


def require_release_publish_guardrail(record):
    target_kind = record.get("targetKind")
    mode = record.get("mode")
    if target_kind not in {"gcs"}:
        return
    if mode in {
        LOCAL_ONLY_GUARDRAIL_MODE,
        DRY_RUN_GUARDRAIL_MODE,
        MOCK_GUARDRAIL_MODE,
    }:
        return
    if record.get("liveCloudUploadAllowed") is True:
        evidence_errors = live_cloud_approval_evidence_errors(
            record.get("approvalEvidence")
        )
        if not evidence_errors:
            return
        raise CheckError(
            "refusing live cloud release upload without approvalEvidence for "
            "project/bucket allowlist, budget, release prefix, lifecycle, and "
            "audit receipt paths: " + "; ".join(evidence_errors)
        )
    raise CheckError(
        "refusing live cloud release upload without explicit opt-in; "
        f"set {LIVE_CLOUD_UPLOAD_ENV}=1 or pass --allow-cloud-upload"
    )


def record_release_publish_guardrail(path, **kwargs):
    record = release_publish_guardrail_record(**kwargs)
    require_release_publish_guardrail(record)
    payload = load_json(path) if path.exists() else {"schemaVersion": 1, "records": []}
    records = payload.setdefault("records", [])
    if not isinstance(records, list):
        raise CheckError(f"{path}: guardrail records must be a list")
    records.append(record)
    write_json(path, payload)
    return record


def validate_schema(root, label, schema_name, instance):
    run_checked(
        f"schema:{label}",
        [
            sys.executable,
            root / "tools" / "validate_json_schema.py",
            "--schema",
            root / "docs" / "schemas" / schema_name,
            "--instance",
            instance,
        ],
        cwd=root,
    )


def expect_success(label, path):
    payload = load_json(path)
    if payload.get("success") is not True:
        raise CheckError(f"{label}: expected success=true in {path}")
    return payload


def make_fake_gcloud_env(work_dir):
    fake_bin = work_dir / "fake-gcloud-bin"
    fake_bin.mkdir(parents=True, exist_ok=True)
    fake_log = work_dir / "fake-gcloud.log"
    fake_credentials = work_dir / "fake-google-application-credentials.json"
    write_json(
        fake_credentials,
        {"type": "service_account", "project_id": "crossgl-release-flow"},
    )

    if os.name == "nt":
        gcloud = fake_bin / "gcloud.cmd"
        gcloud.write_text(
            "\n".join(
                [
                    "@echo off",
                    "setlocal",
                    'if "%CROSSGL_FAKE_GCLOUD_LOG%"=="" exit /b 30',
                    '>> "%CROSSGL_FAKE_GCLOUD_LOG%" echo %*',
                    'if "%~1"=="--quiet" shift',
                    'if /I not "%~1"=="storage" exit /b 31',
                    'if /I "%~2"=="objects" if /I "%~3"=="describe" goto describe',
                    'if /I not "%~2"=="cp" exit /b 32',
                    "shift",
                    "shift",
                    'set "FOUND_SOURCE="',
                    'set "FOUND_DEST="',
                    ":scan_loop",
                    'if "%~1"=="" goto scan_done',
                    'set "ARG=%~1"',
                    'if exist "%ARG%" set "FOUND_SOURCE=1"',
                    'if /I "%ARG:~0,5%"=="gs://" set "FOUND_DEST=1"',
                    "shift",
                    "goto scan_loop",
                    ":scan_done",
                    "if not defined FOUND_SOURCE exit /b 33",
                    "if not defined FOUND_DEST exit /b 34",
                    "exit /b 0",
                    ":describe",
                    'echo {"generation":"1700000000000000","metageneration":"7","crc32c":"ImIEBA==","md5Hash":"1B2M2Y8AsgTpgAmY7PhCfg=="}',
                    "exit /b 0",
                    "",
                ]
            ),
            encoding="utf-8",
        )
    else:
        gcloud = fake_bin / "gcloud"
        gcloud.write_text(
            "\n".join(
                [
                    "#!/bin/sh",
                    'if [ -z "${CROSSGL_FAKE_GCLOUD_LOG:-}" ]; then exit 30; fi',
                    'printf "%s\\n" "$*" >> "$CROSSGL_FAKE_GCLOUD_LOG"',
                    'if [ "${1:-}" = "--quiet" ]; then shift; fi',
                    '[ "${1:-}" = "storage" ] || exit 31',
                    'if [ "${2:-}" = "objects" ] && [ "${3:-}" = "describe" ]; then',
                    '  case "${4:-}" in gs://*) ;; *) exit 35 ;; esac',
                    "  cat <<'JSON'",
                    '{"generation":"1700000000000000","metageneration":"7","crc32c":"ImIEBA==","md5Hash":"1B2M2Y8AsgTpgAmY7PhCfg=="}',
                    "JSON",
                    "  exit 0",
                    "fi",
                    '[ "${2:-}" = "cp" ] || exit 32',
                    "shift 2",
                    'while [ "${1:-}" = "--if-generation-match=0" ] || '
                    'case "${1:-}" in --custom-metadata=*) true ;; *) false ;; esac; '
                    "do shift; done",
                    '[ -f "${1:-}" ] || exit 33',
                    'case "${2:-}" in gs://*) ;; *) exit 34 ;; esac',
                    "exit 0",
                    "",
                ]
            ),
            encoding="utf-8",
        )
        gcloud.chmod(0o755)

    env = os.environ.copy()
    env["PATH"] = str(fake_bin) + os.pathsep + env.get("PATH", "")
    env["GOOGLE_APPLICATION_CREDENTIALS"] = str(fake_credentials)
    env["CROSSGL_FAKE_GCLOUD_LOG"] = str(fake_log)
    return env, fake_log


def fake_gcloud_log_count(log_text, operation):
    if os.name != "nt":
        return log_text.count(operation)
    quoted_operation = " ".join(f'"{part}"' for part in operation.split())
    return log_text.count(operation) + log_text.count(quoted_operation)


def write_fake_shader_tool(root, tool_dir, tool_name, behavior):
    cmake = shutil.which("cmake")
    if cmake is None:
        raise CheckError("cmake is required to run fake native shader tools")
    fake_tool_script = root / "tests" / "toolchain" / "FakeShaderTool.cmake"
    if not fake_tool_script.exists():
        raise CheckError(f"fake shader tool script not found: {fake_tool_script}")
    tool_log = tool_dir / f"{tool_name}.log"

    if os.name == "nt":
        wrapper = tool_dir / f"{tool_name}.cmd"
        wrapper.write_text(
            "\n".join(
                [
                    "@echo off",
                    f'"{cmake}" -DFAKE_TOOL_NAME={tool_name} '
                    f"-DFAKE_TOOL_BEHAVIOR={behavior} "
                    f'-DFAKE_TOOL_LOG="{tool_log}" '
                    f'-P "{fake_tool_script}" -- %*',
                    "exit /b %ERRORLEVEL%",
                    "",
                ]
            ),
            encoding="utf-8",
        )
    else:
        wrapper = tool_dir / tool_name
        wrapper.write_text(
            "\n".join(
                [
                    "#!/bin/sh",
                    "exec "
                    f"{shlex.quote(cmake)} "
                    f"-DFAKE_TOOL_NAME={shlex.quote(tool_name)} "
                    f"-DFAKE_TOOL_BEHAVIOR={shlex.quote(behavior)} "
                    f"-DFAKE_TOOL_LOG={shlex.quote(str(tool_log))} "
                    f'-P {shlex.quote(str(fake_tool_script))} -- "$@"',
                    "",
                ]
            ),
            encoding="utf-8",
        )
        wrapper.chmod(0o755)
    return tool_log


def release_flow_source_path(root, source_alias_root, fixture):
    source_path = root / fixture["source"]
    module_alias = fixture.get("module_alias")
    if module_alias is None:
        return source_path

    text = source_path.read_text(encoding="utf-8")
    match = SHADER_DECL_RE.search(text)
    if match is None:
        raise CheckError(f"{source_path}: expected shader declaration")

    alias_path = source_alias_root / f"{module_alias}.cgl"
    alias_path.parent.mkdir(parents=True, exist_ok=True)
    alias_text = text[: match.start(1)] + module_alias + text[match.end(1) :]
    alias_path.write_text(alias_text, encoding="utf-8")
    return alias_path


def make_fake_release_package_toolchain_env(root, work_dir):
    tool_dir = work_dir / "fake-release-package-toolchain"
    tool_dir.mkdir(parents=True, exist_ok=True)
    logs = {
        "spirv-as": write_fake_shader_tool(root, tool_dir, "spirv-as", "success"),
        "spirv-val": write_fake_shader_tool(root, tool_dir, "spirv-val", "success"),
        "xcrun": write_fake_shader_tool(root, tool_dir, "xcrun", "success"),
    }
    env = os.environ.copy()
    env["PATH"] = str(tool_dir) + os.pathsep + env.get("PATH", "")
    env["CROSSGL_DISABLE_TOOLCHAIN_FALLBACKS"] = "1"
    return env, logs


def check_fake_native_toolchain_logs(logs):
    for tool_name, log_path in logs.items():
        if not log_path.exists():
            raise CheckError(f"fake {tool_name} log was not written: {log_path}")
        log_text = log_path.read_text(encoding="utf-8")
        if f"{tool_name} success:" not in log_text:
            raise CheckError(f"fake {tool_name} log did not record a success call")


def build_fixture_packages(root, cglc, package_root, env):
    package_root.mkdir(parents=True, exist_ok=True)
    source_alias_root = package_root.parent / "release-flow-sources"
    for fixture in PACKAGE_FIXTURES:
        package_name = fixture["package_name"]
        source_path = release_flow_source_path(root, source_alias_root, fixture)
        run_checked(
            f"build:{package_name}",
            [
                cglc,
                "build",
                source_path,
                "--target",
                fixture["target"],
                "--output",
                package_root / package_name,
                "--debug-ir",
                "--opt-level",
                "O0",
            ],
            cwd=root,
            env=env,
        )


def check_fake_gcloud_log(fake_log, upload_manifest):
    payload = load_json(upload_manifest)
    requests = payload.get("requests")
    if not isinstance(requests, list) or not requests:
        raise CheckError(f"expected upload requests in {upload_manifest}")
    log_text = fake_log.read_text(encoding="utf-8") if fake_log.exists() else ""
    request_count = len(requests)
    if fake_gcloud_log_count(log_text, "storage cp") != request_count:
        raise CheckError("fake gcloud did not receive one storage cp per request")
    if fake_gcloud_log_count(log_text, "storage objects describe") != request_count:
        raise CheckError(
            "fake gcloud did not receive one storage objects describe per request"
        )
    if f"gs://{GCS_BUCKET}/{GCS_PREFIX}" not in log_text:
        raise CheckError("fake gcloud log is missing the expected GCS destination")
    for needle in (
        "--if-generation-match=0",
        "--custom-metadata=",
        "crossgl-sha256=",
        "crossgl-size-bytes=",
        "crossgl-upload-fingerprint=",
    ):
        if needle not in log_text:
            raise CheckError(f"fake gcloud log is missing {needle!r}")


def check_missing_source_hash_blocks_promotion(root, cglc, paths, package_root):
    manifest_path = package_root / PACKAGE_FIXTURES[0]["package_name"] / "manifest.json"
    manifest = load_json(manifest_path)
    manifest.pop("sourceHash", None)
    write_json(manifest_path, manifest)

    bad_promotion = paths["promotion"].with_name(
        "package-release-promotion-manifest-missing-source-hash.json"
    )
    bad_bundle = paths["bundle"].with_name(
        "package-release-bundle-missing-source-hash.json"
    )
    run_expect_failure(
        "promotion-missing-source-hash",
        [
            cglc,
            "package",
            "release",
            "--promotion-summary",
            paths["summary"],
            "--manifest-output",
            bad_promotion,
            "--bundle-output",
            bad_bundle,
            "--json",
        ],
        cwd=root,
        expected="package.release.promotion.invalid-source-hash",
    )

    payload = load_json(bad_promotion)
    if payload.get("releaseEligible") is not False:
        raise CheckError("missing-source-hash promotion should not be eligible")
    blocker_codes = [blocker.get("code") for blocker in payload.get("blockers", [])]
    if "package-inventory-failed" not in blocker_codes:
        raise CheckError(
            "missing-source-hash promotion should record inventory blocker"
        )


def check_package_artifact_requirements_propagate(paths):
    promotion = load_json(paths["promotion"])
    bundle = load_json(paths["bundle"])
    plan = load_json(paths["plan"])

    promotion_requirements = {
        package["packagePath"]: package.get("packageArtifactRequirements")
        for package in promotion.get("packages", [])
    }
    if not promotion_requirements:
        raise CheckError("promotion manifest did not record package requirements")

    for payload_name, payload in (("bundle", bundle), ("publish plan", plan)):
        for package in payload.get("packages", []):
            package_path = package.get("packagePath")
            requirements = package.get("packageArtifactRequirements")
            if requirements is None:
                raise CheckError(
                    f"{payload_name} package {package_path!r} is missing "
                    "packageArtifactRequirements"
                )
            if requirements != promotion_requirements.get(package_path):
                raise CheckError(
                    f"{payload_name} package {package_path!r} requirements "
                    "do not match promotion manifest"
                )
            artifact_names = {
                artifact.get("name") for artifact in package.get("artifacts", [])
            }
            missing = sorted(
                name
                for name in set(requirements.get("requiredPathArtifacts", []))
                - artifact_names
                if not (
                    name == "nativeBinary"
                    and requirements.get("allowsPlannedNativeBinary")
                    and package.get("nativeBinaryStatus") == "planned"
                )
            )
            if missing:
                raise CheckError(
                    f"{payload_name} package {package_path!r} is missing "
                    f"required artifacts {missing!r}"
                )


def check_package_reflection_summary_propagates(paths):
    promotion = load_json(paths["promotion"])
    bundle = load_json(paths["bundle"])
    plan = load_json(paths["plan"])

    promotion_reflections = {
        package["packagePath"]: package.get("reflection")
        for package in promotion.get("packages", [])
    }
    if not promotion_reflections:
        raise CheckError("promotion manifest did not record package reflection")

    saw_target_feature_evidence = False
    for package_path, reflection in promotion_reflections.items():
        if not isinstance(reflection, dict):
            raise CheckError(
                f"promotion package {package_path!r} is missing reflection"
            )
        target_feature_count = reflection.get("targetFeatureCount")
        if not isinstance(target_feature_count, int) or target_feature_count < 0:
            raise CheckError(
                f"promotion package {package_path!r} has invalid "
                "reflection.targetFeatureCount"
            )
        evidence_ids = reflection.get("targetFeatureEvidenceIds")
        if not isinstance(evidence_ids, list):
            raise CheckError(
                f"promotion package {package_path!r} has invalid "
                "reflection.targetFeatureEvidenceIds"
            )
        if evidence_ids:
            saw_target_feature_evidence = True

    if not saw_target_feature_evidence:
        raise CheckError("promotion manifest did not record target feature evidence")

    for payload_name, payload in (("bundle", bundle), ("publish plan", plan)):
        for package in payload.get("packages", []):
            package_path = package.get("packagePath")
            if package.get("reflection") != promotion_reflections.get(package_path):
                raise CheckError(
                    f"{payload_name} package {package_path!r} reflection "
                    "does not match promotion manifest"
                )


def windows_stage_path_text(stage_root, destination_path):
    return str(PureWindowsPath(stage_root, *destination_path.split("/")))


def require_windows_stage_path_budget(destination_paths, *, stage_root, label):
    over_budget = []
    for destination_path in sorted(set(destination_paths)):
        if not is_normalized_relative_path(destination_path):
            raise CheckError(
                f"{label}: destinationPath is not normalized: {destination_path!r}"
            )
        staged_path = windows_stage_path_text(stage_root, destination_path)
        path_length = len(staged_path)
        if path_length > WINDOWS_STAGE_PATH_LIMIT:
            over_budget.append((path_length, destination_path, staged_path))

    if over_budget:
        details = "\n".join(
            f"  {path_length} chars: {destination_path}"
            for path_length, destination_path, _staged_path in over_budget[:5]
        )
        raise CheckError(
            f"{label}: publish stage destinations exceed the Windows path "
            f"budget of {WINDOWS_STAGE_PATH_LIMIT} characters under "
            f"{stage_root}:\n{details}"
        )


def check_publish_plan_windows_stage_path_budget(paths):
    plan = load_json(paths["plan"])
    artifacts = plan.get("artifacts")
    if not isinstance(artifacts, list):
        raise CheckError(f"{paths['plan']}: expected artifacts array")
    destination_paths = [artifact.get("destinationPath") for artifact in artifacts]
    require_windows_stage_path_budget(
        destination_paths,
        stage_root=WINDOWS_CI_STAGE_ROOT,
        label="publish plan Windows stage path budget",
    )


def check_windows_stage_path_budget_self_test():
    old_overlong_destination = (
        "packages/directx/DirectXGraphicsStorageBufferResourceShader/"
        "graphics-stages.directx-storage-buffer-resources-source-package.cglb-"
        "0123456789abcdef/backend/directx/"
        "DirectXGraphicsStorageBufferResourceShader.graphics.hlsl"
    )
    try:
        require_windows_stage_path_budget(
            [old_overlong_destination],
            stage_root=WINDOWS_CI_STAGE_ROOT,
            label="self-test overlong destination",
        )
    except CheckError as exc:
        if "exceed the Windows path budget" not in str(exc):
            raise CheckError(
                "Windows stage path budget self-test reported an unclear error"
            )
    else:
        raise CheckError("Windows stage path budget accepted an overlong destination")

    require_windows_stage_path_budget(
        [
            "packages/directx/DxStorageBufferShader/"
            "gfx-dx-storage.cglb-0123456789abcdef/backend/directx/"
            "DxStorageBufferShader.graphics.hlsl"
        ],
        stage_root=WINDOWS_CI_STAGE_ROOT,
        label="self-test shortened destination",
    )
    print("validated release publish Windows stage path budget")


def check_graphics_conformance_manifest_rows(root):
    manifest_path = root / "tests" / "conformance" / "manifest.v0.json"
    manifest = load_json(manifest_path)
    entries = manifest.get("entries")
    if not isinstance(entries, list):
        raise CheckError(f"{manifest_path}: expected entries array")
    entries_by_id = {
        entry.get("id"): entry
        for entry in entries
        if isinstance(entry, dict) and isinstance(entry.get("id"), str)
    }

    for fixture in GRAPHICS_PACKAGE_FIXTURES:
        entry_id = fixture["manifest_entry_id"]
        entry = entries_by_id.get(entry_id)
        if not isinstance(entry, dict):
            raise CheckError(
                f"{manifest_path}: missing required graphics package row {entry_id!r}"
            )
        for field, expected in (
            ("feature_group", "graphics-stages"),
            ("language_category", "graphics"),
            ("status", "accepted"),
            ("command_profile", fixture["command_profile"]),
            ("target", fixture["target"]),
            ("fixture", fixture["source"]),
        ):
            if entry.get(field) != expected:
                raise CheckError(
                    f"{manifest_path}: {entry_id}.{field} expected "
                    f"{expected!r}, got {entry.get(field)!r}"
                )
        for field in ("evidence_tests", "target_feature_evidence_tests"):
            expected_values = list(fixture.get(field, ()))
            actual_values = entry.get(field, [])
            if actual_values != expected_values:
                raise CheckError(
                    f"{manifest_path}: {entry_id}.{field} expected "
                    f"{expected_values!r}, got {actual_values!r}"
                )


def local_path_matches(value, expected_path):
    if not isinstance(value, str) or value == "":
        return False
    candidate = Path(value)
    if candidate.as_posix() == expected_path.as_posix():
        return True
    try:
        return candidate.resolve() == expected_path.resolve()
    except OSError:
        return False


def graphics_package_expectations(package_root):
    expectations = []
    for fixture in GRAPHICS_PACKAGE_FIXTURES:
        package_path = (package_root / fixture["package_name"]).resolve()
        manifest_path = package_path / "manifest.json"
        manifest = load_json(manifest_path)
        artifacts = manifest.get("artifacts")
        if not isinstance(artifacts, dict):
            raise CheckError(f"{manifest_path}: expected artifacts object")
        requirements = manifest.get("packageArtifactRequirements")
        if not isinstance(requirements, dict):
            raise CheckError(
                f"{manifest_path}: expected packageArtifactRequirements object"
            )

        actual_native_status = artifacts.get("nativeBinaryStatus")
        allowed_native_statuses = fixture["allowed_native_binary_statuses"]
        if actual_native_status not in allowed_native_statuses:
            raise CheckError(
                f"{manifest_path}: nativeBinaryStatus expected one of "
                f"{allowed_native_statuses!r}, got {actual_native_status!r}"
            )
        for field, expected in (
            ("target", fixture["target"]),
            ("packageMode", fixture["package_mode"]),
        ):
            if requirements.get(field) != expected:
                raise CheckError(
                    f"{manifest_path}: packageArtifactRequirements.{field} "
                    f"expected {expected!r}, got {requirements.get(field)!r}"
                )
        if fixture["package_mode"] == "source-package":
            if requirements.get("allowsPlannedNativeBinary") is not True:
                raise CheckError(
                    f"{manifest_path}: source-package row must allow planned "
                    "nativeBinary sentinel"
                )
            if requirements.get("requiresNativeBinaryStatus") is not True:
                raise CheckError(
                    f"{manifest_path}: source-package row must require "
                    "nativeBinaryStatus"
                )
        expected_evidence_ids = expected_package_artifact_requirement_evidence_ids(
            requirements
        )
        if requirements.get("evidenceIds") != expected_evidence_ids:
            raise CheckError(
                f"{manifest_path}: packageArtifactRequirements.evidenceIds "
                f"expected {expected_evidence_ids!r}, "
                f"got {requirements.get('evidenceIds')!r}"
            )

        expected_artifacts = {}
        for name, relative_path in artifacts.items():
            if name == "nativeBinaryStatus":
                continue
            if not isinstance(relative_path, str) or relative_path == "":
                raise CheckError(
                    f"{manifest_path}: artifacts.{name} must be a non-empty path"
                )
            artifact_file = package_path / relative_path
            exists = artifact_file.is_file()
            if name == NATIVE_BINARY and actual_native_status == "planned":
                if exists:
                    raise CheckError(
                        f"{manifest_path}: planned nativeBinary unexpectedly exists"
                    )
            elif not exists:
                raise CheckError(
                    f"{manifest_path}: expected artifact {name!r} at {relative_path}"
                )

            expected_artifacts[name] = {
                "name": name,
                "path": relative_path,
                "exists": exists,
                "sizeBytes": artifact_file.stat().st_size if exists else None,
                "sha256": sha256_file(artifact_file) if exists else None,
            }

        expectations.append(
            {
                "fixture": fixture,
                "package_path": package_path,
                "package_path_text": package_path.as_posix(),
                "module": manifest.get("module"),
                "target": manifest.get("target"),
                "source_hash": manifest.get("sourceHash"),
                "native_binary_status": actual_native_status,
                "requirements": {
                    key: requirements.get(key)
                    for key in (
                        "target",
                        "packageMode",
                        "requiredPathArtifacts",
                        "requiresNativeBinaryStatus",
                        "allowsPlannedNativeBinary",
                        "allowsPlannedNativeSourceEvidence",
                        "evidenceIds",
                    )
                },
                "artifacts": expected_artifacts,
            }
        )
    return expectations


def expected_package_artifact_requirement_evidence_ids(requirements):
    target = requirements["target"]
    evidence_ids = [
        f"target-legalization.v1.{target}.package-artifacts."
        f"{requirements['packageMode']}"
    ]
    evidence_ids.extend(
        f"target-legalization.v1.{target}.package-artifact.required.{name}"
        for name in requirements["requiredPathArtifacts"]
    )
    if requirements["requiresNativeBinaryStatus"]:
        evidence_ids.append(
            f"target-legalization.v1.{target}."
            "package-artifact.native-binary-status.required"
        )
    if requirements["allowsPlannedNativeBinary"]:
        evidence_ids.append(
            f"target-legalization.v1.{target}."
            "package-artifact.planned-native-binary.allowed"
        )
    if requirements["allowsPlannedNativeSourceEvidence"]:
        evidence_ids.append(
            f"target-legalization.v1.{target}."
            "package-artifact.planned-native-source-evidence.allowed"
        )
    return evidence_ids


def artifact_path_from_record(record):
    return record.get("packageArtifactPath", record.get("path"))


def require_artifact_record_evidence(label, record, expected_artifact):
    actual_path = artifact_path_from_record(record)
    if actual_path != expected_artifact["path"]:
        raise CheckError(
            f"{label}: expected artifact path {expected_artifact['path']!r}, "
            f"got {actual_path!r}"
        )

    expected_size = expected_artifact["sizeBytes"]
    expected_sha = expected_artifact["sha256"]
    if expected_artifact["exists"]:
        require_positive_size(f"{label}.sizeBytes", record.get("sizeBytes"))
        require_sha256(f"{label}.sha256", record.get("sha256"))
    if record.get("sizeBytes") != expected_size:
        raise CheckError(
            f"{label}: sizeBytes expected {expected_size!r}, "
            f"got {record.get('sizeBytes')!r}"
        )
    if record.get("sha256") != expected_sha:
        raise CheckError(
            f"{label}: sha256 expected {expected_sha!r}, got {record.get('sha256')!r}"
        )


def record_matches_package(record, expected_package):
    package_path = record.get("packagePath")
    if local_path_matches(package_path, expected_package["package_path"]):
        return True
    if not isinstance(package_path, str) or package_path == "":
        return False
    return Path(package_path).name == expected_package["package_path"].name


def find_graphics_package_record(label, packages, expected_package):
    return find_required_record(
        label,
        packages,
        lambda package: record_matches_package(package, expected_package),
    )


def require_no_record(label, records, predicate):
    matches = [record for record in records if predicate(record)]
    if matches:
        raise CheckError(f"{label}: expected no records, got {len(matches)}")


def require_package_identity(label, package, expected_package):
    for field, expected in (
        ("module", expected_package["module"]),
        ("target", expected_package["target"]),
        ("sourceHash", expected_package["source_hash"]),
        ("nativeBinaryStatus", expected_package["native_binary_status"]),
        ("packageArtifactRequirements", expected_package["requirements"]),
    ):
        if package.get(field) != expected:
            raise CheckError(
                f"{label}.{field}: expected {expected!r}, got {package.get(field)!r}"
            )


def find_named_artifact(label, records, expected_package, name):
    return find_required_record(
        label,
        records,
        lambda artifact: (
            artifact.get("name") == name
            and record_matches_package(artifact, expected_package)
        ),
    )


def check_graphics_package_release_surfaces(paths, package_root):
    bundle = load_json(paths["bundle"])
    plan = load_json(paths["plan"])
    stage = load_json(paths["stage"])
    inventory = load_json(paths["release_inventory"])
    expectations = graphics_package_expectations(package_root)

    for expected_package in expectations:
        entry_id = expected_package["fixture"]["manifest_entry_id"]
        bundle_package = find_graphics_package_record(
            f"release bundle graphics package {entry_id}",
            bundle.get("packages", []),
            expected_package,
        )
        require_package_identity(
            f"release bundle graphics package {entry_id}",
            bundle_package,
            expected_package,
        )
        plan_package = find_graphics_package_record(
            f"publish plan graphics package {entry_id}",
            plan.get("packages", []),
            expected_package,
        )
        require_package_identity(
            f"publish plan graphics package {entry_id}",
            plan_package,
            expected_package,
        )

        for name, expected_artifact in expected_package["artifacts"].items():
            bundle_artifact = find_required_record(
                f"release bundle graphics artifact {entry_id}:{name}",
                bundle_package.get("artifacts", []),
                lambda artifact: artifact.get("name") == name,
            )
            if bundle_artifact.get("exists") != expected_artifact["exists"]:
                raise CheckError(
                    f"release bundle graphics artifact {entry_id}:{name}: "
                    f"exists expected {expected_artifact['exists']!r}, "
                    f"got {bundle_artifact.get('exists')!r}"
                )
            require_artifact_record_evidence(
                f"release bundle graphics artifact {entry_id}:{name}",
                bundle_artifact,
                expected_artifact,
            )

            inventory_bundle_record = find_required_record(
                f"release inventory bundle graphics artifact {entry_id}:{name}",
                inventory.get("records", []),
                lambda record: (
                    record_matches_package(record, expected_package)
                    and record.get("sourceRecordKind") == "release-bundle"
                    and record.get("packageArtifactPath") == expected_artifact["path"]
                ),
            )
            require_artifact_record_evidence(
                f"release inventory bundle graphics artifact {entry_id}:{name}",
                inventory_bundle_record,
                expected_artifact,
            )

            if not expected_artifact["exists"]:
                require_no_record(
                    f"publish plan graphics planned sentinel {entry_id}:{name}",
                    plan_package.get("artifacts", []),
                    lambda artifact: artifact.get("name") == name,
                )
                require_no_record(
                    f"publish plan flattened graphics planned sentinel {entry_id}:{name}",
                    plan.get("artifacts", []),
                    lambda artifact: (
                        artifact.get("name") == name
                        and record_matches_package(artifact, expected_package)
                    ),
                )
                require_no_record(
                    f"publish stage graphics planned sentinel {entry_id}:{name}",
                    stage.get("artifacts", []),
                    lambda artifact: (
                        artifact.get("name") == name
                        and record_matches_package(artifact, expected_package)
                    ),
                )
                continue

            plan_nested_artifact = find_required_record(
                f"publish plan nested graphics artifact {entry_id}:{name}",
                plan_package.get("artifacts", []),
                lambda artifact: artifact.get("name") == name,
            )
            require_artifact_record_evidence(
                f"publish plan nested graphics artifact {entry_id}:{name}",
                plan_nested_artifact,
                expected_artifact,
            )
            plan_flat_artifact = find_named_artifact(
                f"publish plan flattened graphics artifact {entry_id}:{name}",
                plan.get("artifacts", []),
                expected_package,
                name,
            )
            require_artifact_record_evidence(
                f"publish plan flattened graphics artifact {entry_id}:{name}",
                plan_flat_artifact,
                expected_artifact,
            )
            stage_artifact = find_named_artifact(
                f"publish stage graphics artifact {entry_id}:{name}",
                stage.get("artifacts", []),
                expected_package,
                name,
            )
            require_artifact_record_evidence(
                f"publish stage graphics artifact {entry_id}:{name}",
                stage_artifact,
                expected_artifact,
            )
            if stage_artifact.get("staged") is not True:
                raise CheckError(
                    f"publish stage graphics artifact {entry_id}:{name}: not staged"
                )
            if not isinstance(stage_artifact.get("stagedPath"), str):
                raise CheckError(
                    f"publish stage graphics artifact {entry_id}:{name}: "
                    "missing stagedPath"
                )

            for source_kind in ("publish-plan", "publish-stage"):
                inventory_record = find_required_record(
                    f"release inventory {source_kind} graphics artifact "
                    f"{entry_id}:{name}",
                    inventory.get("records", []),
                    lambda record: (
                        record_matches_package(record, expected_package)
                        and record.get("sourceRecordKind") == source_kind
                        and record.get("packageArtifactPath")
                        == expected_artifact["path"]
                    ),
                )
                require_artifact_record_evidence(
                    f"release inventory {source_kind} graphics artifact "
                    f"{entry_id}:{name}",
                    inventory_record,
                    expected_artifact,
                )
                if source_kind == "publish-stage" and not isinstance(
                    inventory_record.get("stagedPath"), str
                ):
                    raise CheckError(
                        f"release inventory publish-stage graphics artifact "
                        f"{entry_id}:{name}: missing stagedPath"
                    )


def expected_existing_graphics_stage_records(paths, package_root):
    stage = load_json(paths["stage"])
    records = []
    for expected_package in graphics_package_expectations(package_root):
        for name, expected_artifact in expected_package["artifacts"].items():
            if not expected_artifact["exists"]:
                continue
            stage_artifact = find_named_artifact(
                "publish stage graphics artifact "
                f"{expected_package['fixture']['manifest_entry_id']}:{name}",
                stage.get("artifacts", []),
                expected_package,
                name,
            )
            records.append((expected_package, name, expected_artifact, stage_artifact))
    return records


def check_graphics_package_publish_receipt(paths, package_root):
    receipt = load_json(paths["receipt"])
    for (
        expected_package,
        name,
        expected_artifact,
        _stage_artifact,
    ) in expected_existing_graphics_stage_records(paths, package_root):
        entry_id = expected_package["fixture"]["manifest_entry_id"]
        receipt_artifact = find_named_artifact(
            f"local publish receipt graphics artifact {entry_id}:{name}",
            receipt.get("artifacts", []),
            expected_package,
            name,
        )
        require_artifact_record_evidence(
            f"local publish receipt graphics artifact {entry_id}:{name}",
            receipt_artifact,
            expected_artifact,
        )
        for field in ("staged", "planned", "published"):
            if receipt_artifact.get(field) is not True:
                raise CheckError(
                    f"local publish receipt graphics artifact {entry_id}:{name}: "
                    f"expected {field}=true"
                )
        if not isinstance(receipt_artifact.get("publishedPath"), str):
            raise CheckError(
                f"local publish receipt graphics artifact {entry_id}:{name}: "
                "missing publishedPath"
            )


def check_graphics_package_upload_manifest(paths, package_root):
    upload_manifest = load_json(paths["upload_manifest"])
    for (
        expected_package,
        name,
        expected_artifact,
        stage_artifact,
    ) in expected_existing_graphics_stage_records(paths, package_root):
        entry_id = expected_package["fixture"]["manifest_entry_id"]
        request = find_required_record(
            f"upload manifest graphics artifact {entry_id}:{name}",
            upload_manifest.get("requests", []),
            lambda candidate: (
                candidate.get("stagedPath") == stage_artifact.get("stagedPath")
                and candidate.get("destinationPath")
                == stage_artifact.get("destinationPath")
            ),
        )
        if request.get("bucket") != GCS_BUCKET:
            raise CheckError(
                f"upload manifest graphics artifact {entry_id}:{name}: "
                f"expected bucket {GCS_BUCKET!r}"
            )
        if request.get("sizeBytes") != expected_artifact["sizeBytes"]:
            raise CheckError(
                f"upload manifest graphics artifact {entry_id}:{name}: "
                "sizeBytes drifted from stage"
            )
        if request.get("sha256") != expected_artifact["sha256"]:
            raise CheckError(
                f"upload manifest graphics artifact {entry_id}:{name}: "
                "sha256 drifted from stage"
            )
        object_name = request.get("objectName")
        if (
            not isinstance(object_name, str)
            or expected_package["fixture"]["package_name"] not in object_name
        ):
            raise CheckError(
                f"upload manifest graphics artifact {entry_id}:{name}: "
                "objectName did not include package identity"
            )


def check_graphics_package_release_provenance(paths, package_root):
    provenance_manifest = load_json(paths["provenance_manifest"])
    for (
        expected_package,
        name,
        expected_artifact,
        stage_artifact,
    ) in expected_existing_graphics_stage_records(paths, package_root):
        entry_id = expected_package["fixture"]["manifest_entry_id"]
        provenance_artifact = find_required_record(
            f"release provenance graphics artifact {entry_id}:{name}",
            provenance_manifest.get("artifacts", []),
            lambda candidate: (
                record_matches_package(candidate, expected_package)
                and candidate.get("packageArtifactPath") == expected_artifact["path"]
            ),
        )
        require_artifact_record_evidence(
            f"release provenance graphics artifact {entry_id}:{name}",
            provenance_artifact,
            expected_artifact,
        )
        destination_path = provenance_artifact.get("destinationPath")
        if destination_path != stage_artifact.get("destinationPath"):
            raise CheckError(
                f"release provenance graphics artifact {entry_id}:{name}: "
                "destinationPath drifted from stage"
            )


def require_sha256(label, value):
    if not isinstance(value, str) or SHA256_RE.fullmatch(value) is None:
        raise CheckError(f"{label}: expected lowercase SHA-256 digest")


def require_positive_size(label, value):
    if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
        raise CheckError(f"{label}: expected positive byte count")


def find_required_record(label, records, predicate):
    matches = [record for record in records if predicate(record)]
    if len(matches) != 1:
        raise CheckError(f"{label}: expected exactly one record, got {len(matches)}")
    return matches[0]


def package_native_descriptor_expectations(bundle):
    expectations = {}
    for package in bundle.get("packages", []):
        package_path = package.get("packagePath")
        if not isinstance(package_path, str) or package_path == "":
            raise CheckError("bundle package is missing packagePath")

        manifest_path = Path(package_path) / "manifest.json"
        manifest = load_json(manifest_path)
        requirements = manifest.get("packageArtifactRequirements", {})
        if requirements.get("packageMode") != "native":
            continue

        manifest_artifacts = manifest.get("artifacts", {})
        descriptor_path = manifest_artifacts.get(NATIVE_ARTIFACT_DESCRIPTOR)
        native_binary_path = manifest_artifacts.get(NATIVE_BINARY)
        if not isinstance(descriptor_path, str) or descriptor_path == "":
            raise CheckError(
                f"{package_path}: native package manifest is missing "
                f"artifacts.{NATIVE_ARTIFACT_DESCRIPTOR}"
            )
        if not isinstance(native_binary_path, str) or native_binary_path == "":
            raise CheckError(
                f"{package_path}: native package manifest is missing "
                f"artifacts.{NATIVE_BINARY}"
            )

        descriptor_file = Path(package_path) / descriptor_path
        descriptor = load_json(descriptor_file)
        if descriptor.get("artifactPath") != native_binary_path:
            raise CheckError(
                f"{package_path}: native descriptor artifactPath "
                f"{descriptor.get('artifactPath')!r} did not match manifest "
                f"nativeBinary {native_binary_path!r}"
            )
        artifact_hash = descriptor.get("artifactHash", {})
        require_sha256(
            f"{package_path}: native descriptor artifactHash.value",
            artifact_hash.get("value") if isinstance(artifact_hash, dict) else None,
        )
        require_positive_size(
            f"{package_path}: native descriptor sizeBytes",
            descriptor.get("sizeBytes"),
        )

        expectations[package_path] = {
            "descriptorPath": descriptor_path,
            "nativeBinaryPath": native_binary_path,
        }

    if not expectations:
        raise CheckError("release flow did not build any native packages")
    return expectations


def descriptor_record_evidence(label, record, expected_path):
    path = record.get("path", record.get("packageArtifactPath"))
    if record.get("name") != NATIVE_ARTIFACT_DESCRIPTOR:
        raise CheckError(
            f"{label}: expected {NATIVE_ARTIFACT_DESCRIPTOR} record, "
            f"got {record.get('name')!r}"
        )
    if path != expected_path:
        raise CheckError(
            f"{label}: expected manifest descriptor path {expected_path!r}, "
            f"got {path!r}"
        )
    require_positive_size(f"{label}.sizeBytes", record.get("sizeBytes"))
    require_sha256(f"{label}.sha256", record.get("sha256"))
    return record["sizeBytes"], record["sha256"]


def check_native_descriptor_report_surfaces(paths):
    bundle = load_json(paths["bundle"])
    plan = load_json(paths["plan"])
    stage = load_json(paths["stage"])
    inventory = load_json(paths["release_inventory"])
    expectations = package_native_descriptor_expectations(bundle)

    for package_path, expected in expectations.items():
        descriptor_path = expected["descriptorPath"]
        bundle_package = find_required_record(
            f"bundle package {package_path}",
            bundle.get("packages", []),
            lambda package: package.get("packagePath") == package_path,
        )
        bundle_descriptor = find_required_record(
            f"bundle descriptor {package_path}",
            bundle_package.get("artifacts", []),
            lambda artifact: artifact.get("name") == NATIVE_ARTIFACT_DESCRIPTOR,
        )
        expected_size, expected_sha = descriptor_record_evidence(
            f"bundle descriptor {package_path}",
            bundle_descriptor,
            descriptor_path,
        )
        if bundle_descriptor.get("exists") is not True:
            raise CheckError(f"bundle descriptor {package_path}: expected exists=true")

        plan_package = find_required_record(
            f"publish plan package {package_path}",
            plan.get("packages", []),
            lambda package: package.get("packagePath") == package_path,
        )
        plan_descriptor = find_required_record(
            f"publish plan nested descriptor {package_path}",
            plan_package.get("artifacts", []),
            lambda artifact: artifact.get("name") == NATIVE_ARTIFACT_DESCRIPTOR,
        )
        plan_size, plan_sha = descriptor_record_evidence(
            f"publish plan nested descriptor {package_path}",
            plan_descriptor,
            descriptor_path,
        )
        if (plan_size, plan_sha) != (expected_size, expected_sha):
            raise CheckError(
                f"publish plan nested descriptor {package_path}: checksum "
                "evidence drifted from bundle"
            )

        flattened_plan_descriptor = find_required_record(
            f"publish plan flattened descriptor {package_path}",
            plan.get("artifacts", []),
            lambda artifact: (
                artifact.get("packagePath") == package_path
                and artifact.get("name") == NATIVE_ARTIFACT_DESCRIPTOR
            ),
        )
        flat_size, flat_sha = descriptor_record_evidence(
            f"publish plan flattened descriptor {package_path}",
            flattened_plan_descriptor,
            descriptor_path,
        )
        if (flat_size, flat_sha) != (expected_size, expected_sha):
            raise CheckError(
                f"publish plan flattened descriptor {package_path}: checksum "
                "evidence drifted from bundle"
            )

        stage_descriptor = find_required_record(
            f"publish stage descriptor {package_path}",
            stage.get("artifacts", []),
            lambda artifact: (
                artifact.get("packagePath") == package_path
                and artifact.get("name") == NATIVE_ARTIFACT_DESCRIPTOR
            ),
        )
        stage_size, stage_sha = descriptor_record_evidence(
            f"publish stage descriptor {package_path}",
            stage_descriptor,
            descriptor_path,
        )
        if (stage_size, stage_sha) != (expected_size, expected_sha):
            raise CheckError(
                f"publish stage descriptor {package_path}: checksum evidence "
                "drifted from bundle"
            )
        if stage_descriptor.get("staged") is not True:
            raise CheckError(f"publish stage descriptor {package_path}: not staged")
        if not isinstance(stage_descriptor.get("stagedPath"), str):
            raise CheckError(
                f"publish stage descriptor {package_path}: missing stagedPath"
            )

        for source_kind in ("release-bundle", "publish-plan", "publish-stage"):
            inventory_record = find_required_record(
                f"release inventory {source_kind} descriptor {package_path}",
                inventory.get("records", []),
                lambda record: (
                    record.get("packagePath") == package_path
                    and record.get("sourceRecordKind") == source_kind
                    and record.get("packageArtifactPath") == descriptor_path
                ),
            )
            require_positive_size(
                f"release inventory {source_kind} descriptor {package_path}.sizeBytes",
                inventory_record.get("sizeBytes"),
            )
            require_sha256(
                f"release inventory {source_kind} descriptor {package_path}.sha256",
                inventory_record.get("sha256"),
            )
            if (
                inventory_record.get("sizeBytes"),
                inventory_record.get("sha256"),
            ) != (expected_size, expected_sha):
                raise CheckError(
                    f"release inventory {source_kind} descriptor "
                    f"{package_path}: checksum evidence drifted from bundle"
                )
            if source_kind == "publish-stage" and not isinstance(
                inventory_record.get("stagedPath"), str
            ):
                raise CheckError(
                    f"release inventory publish-stage descriptor {package_path}: "
                    "missing stagedPath"
                )


def first_native_package(payload, label):
    for package in payload.get("packages", []):
        requirements = package.get("packageArtifactRequirements")
        if (
            isinstance(requirements, dict)
            and requirements.get("packageMode") == "native"
        ):
            return package
    raise CheckError(f"{label}: expected at least one native package")


def recompute_plan_counts(plan):
    total_artifacts = []
    for package in plan.get("packages", []):
        artifacts = package.get("artifacts", [])
        package["artifactCount"] = len(artifacts)
        package["totalArtifactBytes"] = sum(
            artifact.get("sizeBytes", 0) for artifact in artifacts
        )
        total_artifacts.extend(artifacts)
    plan["artifacts"] = sorted(
        total_artifacts, key=lambda artifact: artifact["destinationPath"]
    )
    plan["artifactCount"] = len(plan["artifacts"])
    plan["totalArtifactBytes"] = sum(
        artifact.get("sizeBytes", 0) for artifact in plan["artifacts"]
    )


def remove_native_plan_artifact(paths, work_dir, name):
    plan = load_json(paths["plan"])
    package = first_native_package(plan, f"publish plan remove {name}")
    package_path = package["packagePath"]
    before = len(package.get("artifacts", []))
    package["artifacts"] = [
        artifact
        for artifact in package.get("artifacts", [])
        if artifact.get("name") != name
    ]
    if len(package["artifacts"]) == before:
        raise CheckError(f"publish plan mutation did not remove {name}")
    recompute_plan_counts(plan)
    destination = work_dir / f"package-release-publish-plan-missing-{name}.json"
    write_json(destination, plan)
    return destination, package_path


def set_native_plan_status(paths, work_dir, status):
    plan = load_json(paths["plan"])
    package = first_native_package(plan, f"publish plan status {status}")
    package["nativeBinaryStatus"] = status
    destination = work_dir / f"package-release-publish-plan-native-{status}.json"
    write_json(destination, plan)
    return destination


def check_native_publish_plan_gate(root, cglc, paths, work_dir):
    bad_native_binary_plan, _package_path = remove_native_plan_artifact(
        paths, work_dir, NATIVE_BINARY
    )
    run_expect_failure(
        "stage-publish-native-missing-binary",
        [
            cglc,
            "package",
            "release",
            "--stage-publish",
            bad_native_binary_plan,
            "--stage-output",
            work_dir / "package-release-stage-native-missing-binary",
            "--json",
        ],
        cwd=root,
        expected="native package requires nativeBinary artifact evidence",
    )

    bad_descriptor_plan, _package_path = remove_native_plan_artifact(
        paths, work_dir, NATIVE_ARTIFACT_DESCRIPTOR
    )
    run_expect_failure(
        "stage-publish-native-missing-descriptor",
        [
            cglc,
            "package",
            "release",
            "--stage-publish",
            bad_descriptor_plan,
            "--stage-output",
            work_dir / "package-release-stage-native-missing-descriptor",
            "--json",
        ],
        cwd=root,
        expected="native package requires nativeArtifactDescriptor evidence",
    )

    planned_native_plan = set_native_plan_status(paths, work_dir, "planned")
    run_expect_failure(
        "stage-publish-native-planned-status",
        [
            cglc,
            "package",
            "release",
            "--stage-publish",
            planned_native_plan,
            "--stage-output",
            work_dir / "package-release-stage-native-planned-status",
            "--json",
        ],
        cwd=root,
        expected="not planned nativeBinaryStatus",
    )


def recompute_stage_counts(stage):
    artifacts = stage.get("artifacts", [])
    stage["artifactCount"] = len(artifacts)
    stage["totalArtifactBytes"] = sum(
        artifact.get("sizeBytes", 0) for artifact in artifacts
    )
    staged = [artifact for artifact in artifacts if artifact.get("staged") is True]
    stage["stagedArtifactCount"] = len(staged)
    stage["stagedArtifactBytes"] = sum(
        artifact.get("sizeBytes", 0) for artifact in staged
    )
    identities = {
        (artifact.get("packagePath"), artifact.get("module"), artifact.get("target"))
        for artifact in artifacts
    }
    stage["packageCount"] = len(identities)


def check_native_publish_stage_gate(root, cglc, paths, work_dir):
    plan = load_json(paths["plan"])
    native_package_path = first_native_package(plan, "publish stage mutation")[
        "packagePath"
    ]
    stage = load_json(paths["stage"])
    before = len(stage.get("artifacts", []))
    stage["artifacts"] = [
        artifact
        for artifact in stage.get("artifacts", [])
        if not (
            artifact.get("packagePath") == native_package_path
            and artifact.get("name") == NATIVE_ARTIFACT_DESCRIPTOR
        )
    ]
    if len(stage["artifacts"]) == before:
        raise CheckError("publish stage mutation did not remove native descriptor")
    recompute_stage_counts(stage)
    bad_stage = (
        work_dir / "package-release-publish-stage-missing-native-descriptor.json"
    )
    write_json(bad_stage, stage)

    run_expect_failure(
        "publish-stage-native-missing-descriptor",
        [
            cglc,
            "package",
            "release",
            "--publish-stage",
            bad_stage,
            "--publish-target",
            "local-filesystem",
            "--target-output",
            work_dir / "package-release-published-native-missing-descriptor",
            "--json",
        ],
        cwd=root,
        expected="native package requires staged nativeArtifactDescriptor evidence",
    )


def check_release_report_artifact_inventory(paths):
    bundle = load_json(paths["bundle"])
    plan = load_json(paths["plan"])
    stage = load_json(paths["stage"])
    inventory = load_json(paths["release_inventory"])

    if inventory.get("success") is not True:
        raise CheckError("release report artifact inventory should be successful")
    expected_counts = {
        "bundleArtifactRecordCount": bundle.get("artifactCount"),
        "publishPlanArtifactRecordCount": plan.get("artifactCount"),
        "publishStageArtifactRecordCount": stage.get("artifactCount"),
        "stagedArtifactRecordCount": stage.get("stagedArtifactCount"),
    }
    for field, expected in expected_counts.items():
        if inventory.get(field) != expected:
            raise CheckError(
                f"release report artifact inventory {field} expected "
                f"{expected}, got {inventory.get(field)}"
            )

    expected_total_records = (
        bundle.get("artifactCount", 0)
        + plan.get("artifactCount", 0)
        + stage.get("artifactCount", 0)
    )
    if inventory.get("artifactRecordCount") != expected_total_records:
        raise CheckError("release report artifact inventory record count mismatch")

    expected_total_bytes = (
        bundle.get("totalArtifactBytes", 0)
        + plan.get("totalArtifactBytes", 0)
        + stage.get("totalArtifactBytes", 0)
    )
    if inventory.get("totalArtifactRecordBytes") != expected_total_bytes:
        raise CheckError("release report artifact inventory byte total mismatch")

    records = inventory.get("records", [])
    source_kinds = {record.get("sourceRecordKind") for record in records}
    if source_kinds != {"release-bundle", "publish-plan", "publish-stage"}:
        raise CheckError(
            "release report artifact inventory did not include all source kinds"
        )
    check_native_descriptor_report_surfaces(paths)


def require_local_existing_file(label, value):
    if not isinstance(value, str) or value.strip() == "":
        raise CheckError(f"{label}: expected non-empty local evidence path")
    if URI_LIKE_EVIDENCE_RE.match(value) or value.startswith("//"):
        raise CheckError(f"{label}: expected local path, got provider/network URI")
    path = Path(value)
    if not path.is_file():
        raise CheckError(f"{label}: evidence path does not exist: {value}")


def release_publish_rc_handoff_evidence(work_dir, paths):
    rc_handoff = {
        "provenanceManifestPath": local_evidence_path(paths["provenance_manifest"]),
        "artifactInventoryPath": local_evidence_path(paths["release_inventory"]),
        "guardrailRecordPath": local_evidence_path(paths["guardrails"]),
        "dryRunReceiptPaths": [local_evidence_path(paths["gcs_dry_run"])],
        "uploadManifestPath": local_evidence_path(paths["upload_manifest"]),
        "preflightReportPath": local_evidence_path(paths["preflight"]),
        "mockReceiptPaths": [local_evidence_path(paths["mock_receipt"])],
        "fakeGcloudReceiptPaths": [local_evidence_path(paths["gcs_receipt"])],
    }
    return {
        "schemaVersion": 1,
        "kind": RC_HANDOFF_EVIDENCE_KIND,
        "reportOnly": True,
        "mode": LOCAL_ONLY_GUARDRAIL_MODE,
        "releaseStatus": "not-shipped",
        "liveObjectsCreated": False,
        "localEvidenceRoot": local_evidence_path(work_dir),
        "rcHandoffEvidence": rc_handoff,
        "dryRunArtifactEvidence": {
            "status": "pass",
            "dryRunDefault": True,
            "liveObjectsCreated": False,
            "guardrailRecordPath": rc_handoff["guardrailRecordPath"],
            "dryRunReceiptPaths": rc_handoff["dryRunReceiptPaths"],
            "uploadManifestPath": rc_handoff["uploadManifestPath"],
            "preflightReportPath": rc_handoff["preflightReportPath"],
            "mockReceiptPaths": rc_handoff["mockReceiptPaths"],
            "fakeGcloudReceiptPaths": rc_handoff["fakeGcloudReceiptPaths"],
            "allowedNonLiveModes": sorted(SAFE_GUARDRAIL_MODES),
        },
        "provenanceChecksumEvidence": {
            "provenanceManifestPath": rc_handoff["provenanceManifestPath"],
            "artifactInventoryPath": rc_handoff["artifactInventoryPath"],
        },
        "offlineBoundary": {
            "networkCalls": "not-performed",
            "gcpApiCalls": "not-performed",
            "providerCliCalls": "fake-local-shim-only",
            "liveCloudUploadOptIn": False,
            "liveCloudMode": "rejected",
            "cloudObjectsCreated": False,
        },
    }


def require_release_publish_rc_handoff_evidence(payload):
    if payload.get("schemaVersion") != 1:
        raise CheckError("RC handoff evidence: expected schemaVersion=1")
    if payload.get("kind") != RC_HANDOFF_EVIDENCE_KIND:
        raise CheckError(
            f"RC handoff evidence: expected kind {RC_HANDOFF_EVIDENCE_KIND}"
        )
    if payload.get("reportOnly") is not True:
        raise CheckError("RC handoff evidence: expected reportOnly=true")
    if payload.get("mode") != LOCAL_ONLY_GUARDRAIL_MODE:
        raise CheckError("RC handoff evidence: expected local-only mode")
    if payload.get("releaseStatus") != "not-shipped":
        raise CheckError("RC handoff evidence: expected not-shipped release status")
    if payload.get("liveObjectsCreated") is not False:
        raise CheckError("RC handoff evidence: expected liveObjectsCreated=false")

    handoff = payload.get("rcHandoffEvidence")
    if not isinstance(handoff, dict):
        raise CheckError("RC handoff evidence: missing rcHandoffEvidence object")
    for field in RC_HANDOFF_SCALAR_PATH_FIELDS:
        require_local_existing_file(f"rcHandoffEvidence.{field}", handoff.get(field))
    for field in RC_HANDOFF_LIST_PATH_FIELDS:
        values = handoff.get(field)
        if not isinstance(values, list) or not values:
            raise CheckError(f"rcHandoffEvidence.{field}: expected non-empty list")
        for index, value in enumerate(values):
            require_local_existing_file(f"rcHandoffEvidence.{field}[{index}]", value)

    dry_run = payload.get("dryRunArtifactEvidence")
    if not isinstance(dry_run, dict):
        raise CheckError("RC handoff evidence: missing dryRunArtifactEvidence object")
    if dry_run.get("status") != "pass":
        raise CheckError("RC handoff evidence: expected passing dry-run evidence")
    if dry_run.get("dryRunDefault") is not True:
        raise CheckError("RC handoff evidence: expected dryRunDefault=true")
    if dry_run.get("liveObjectsCreated") is not False:
        raise CheckError(
            "RC handoff evidence: expected dry-run liveObjectsCreated=false"
        )
    if dry_run.get("allowedNonLiveModes") != sorted(SAFE_GUARDRAIL_MODES):
        raise CheckError("RC handoff evidence: unexpected allowed non-live modes")
    for field in (
        "guardrailRecordPath",
        "dryRunReceiptPaths",
        "uploadManifestPath",
        "preflightReportPath",
        "mockReceiptPaths",
        "fakeGcloudReceiptPaths",
    ):
        if dry_run.get(field) != handoff.get(field):
            raise CheckError(
                f"RC handoff evidence: dryRunArtifactEvidence.{field} "
                "does not match rcHandoffEvidence"
            )

    provenance = payload.get("provenanceChecksumEvidence")
    if not isinstance(provenance, dict):
        raise CheckError(
            "RC handoff evidence: missing provenanceChecksumEvidence object"
        )
    for field in ("provenanceManifestPath", "artifactInventoryPath"):
        if provenance.get(field) != handoff.get(field):
            raise CheckError(
                f"RC handoff evidence: provenanceChecksumEvidence.{field} "
                "does not match rcHandoffEvidence"
            )

    boundary = payload.get("offlineBoundary")
    if not isinstance(boundary, dict):
        raise CheckError("RC handoff evidence: missing offlineBoundary object")
    for field in ("networkCalls", "gcpApiCalls"):
        if boundary.get(field) != "not-performed":
            raise CheckError(f"RC handoff evidence: expected {field}=not-performed")
    if boundary.get("providerCliCalls") != "fake-local-shim-only":
        raise CheckError(
            "RC handoff evidence: expected providerCliCalls=fake-local-shim-only"
        )
    if boundary.get("liveCloudUploadOptIn") is not False:
        raise CheckError("RC handoff evidence: expected no live cloud opt-in")
    if boundary.get("liveCloudMode") != "rejected":
        raise CheckError("RC handoff evidence: expected live cloud mode rejection")
    if boundary.get("cloudObjectsCreated") is not False:
        raise CheckError("RC handoff evidence: expected cloudObjectsCreated=false")

    guardrails = load_json(Path(handoff["guardrailRecordPath"]))
    records = guardrails.get("records")
    if not isinstance(records, list) or not records:
        raise CheckError("RC handoff evidence: expected guardrail records")
    modes = {record.get("mode") for record in records}
    if LIVE_CLOUD_GUARDRAIL_MODE in modes:
        raise CheckError(
            "RC handoff evidence: live cloud guardrail mode is not allowed"
        )
    if not modes.issubset(set(SAFE_GUARDRAIL_MODES)):
        raise CheckError(
            "RC handoff evidence: guardrail records must stay dry-run, mock, "
            "or local-only"
        )
    for index, record in enumerate(records):
        if record.get("liveCloudUploadAllowed") is not False:
            raise CheckError(
                "RC handoff evidence: guardrail record "
                f"{index} allows live cloud upload"
            )
        if record.get("liveCloudUploadOptIn") is not None:
            raise CheckError(
                "RC handoff evidence: guardrail record "
                f"{index} has live cloud upload opt-in"
            )


def write_release_publish_rc_handoff_evidence(work_dir, paths):
    payload = release_publish_rc_handoff_evidence(work_dir, paths)
    require_release_publish_rc_handoff_evidence(payload)
    write_json(paths["rc_handoff"], payload)
    return payload


def print_release_publish_rc_handoff_evidence(path, payload):
    handoff = payload["rcHandoffEvidence"]
    print(f"release publish RC handoff evidence: {path}")
    print("release publish RC handoff local paths:")
    for field in RC_HANDOFF_SCALAR_PATH_FIELDS:
        print(f"  {field}: {handoff[field]}")
    for field in RC_HANDOFF_LIST_PATH_FIELDS:
        print(f"  {field}: {', '.join(handoff[field])}")


def check_flow(root, cglc, work_dir, *, allow_live_cloud_upload=False):
    if work_dir.exists():
        shutil.rmtree(work_dir)
    work_dir.mkdir(parents=True)

    package_root = work_dir / "packages"
    check_graphics_conformance_manifest_rows(root)
    native_env, native_tool_logs = make_fake_release_package_toolchain_env(
        root, work_dir
    )
    build_fixture_packages(root, cglc, package_root, native_env)
    check_fake_native_toolchain_logs(native_tool_logs)

    paths = {
        "set": work_dir / "package-set.json",
        "set_stdout": work_dir / "package-set.stdout.json",
        "batch": work_dir / "package-set-verification-batch.json",
        "batch_stdout": work_dir / "package-set-verification-batch.stdout.json",
        "report": work_dir / "package-set-verification-report.json",
        "summary": work_dir / "package-set-verification-summary.json",
        "promotion": work_dir / "package-release-promotion-manifest.json",
        "promotion_stdout": work_dir / "package-release-promotion-manifest.stdout.json",
        "bundle": work_dir / "package-release-bundle.json",
        "bundle_verification": work_dir / "package-release-bundle-verification.json",
        "plan": work_dir / "package-release-publish-plan.json",
        "plan_stdout": work_dir / "package-release-publish-plan.stdout.json",
        "stage_dir": work_dir / "package-release-stage",
        "stage": work_dir / "package-release-publish-stage.json",
        "release_inventory": work_dir / "release-report-artifact-inventory.json",
        "local_target": work_dir / "package-release-published",
        "receipt": work_dir / "package-release-publish-receipt.json",
        "receipt_stdout": work_dir / "package-release-publish-receipt.stdout.json",
        "gcs_target": work_dir / "package-release-gcs-target.json",
        "guardrails": work_dir / "package-release-publish-guardrails.json",
        "gcs_dry_run": work_dir / "package-release-publish-gcs-dry-run.json",
        "upload_manifest": work_dir / "package-release-publish-upload-manifest.json",
        "provenance_manifest": work_dir / "package-release-provenance-manifest.json",
        "rc_handoff": work_dir / "package-release-publish-rc-handoff-evidence.json",
        "preflight": work_dir / "package-release-publish-upload-preflight.json",
        "preflight_stdout": work_dir
        / "package-release-publish-upload-preflight.stdout.json",
        "mock_batch": work_dir / "package-release-publish-upload-batch.json",
        "mock_batch_stdout": work_dir
        / "package-release-publish-upload-batch.stdout.json",
        "mock_receipt": work_dir / "package-release-publish-upload-receipt.json",
        "gcs_batch": work_dir / "package-release-publish-upload-batch-gcs.json",
        "gcs_batch_stdout": work_dir
        / "package-release-publish-upload-batch-gcs.stdout.json",
        "gcs_receipt": work_dir / "package-release-publish-upload-receipt-gcs.json",
    }

    run_checked(
        "export-package-set",
        [
            cglc,
            "package",
            "maintain",
            "--scan",
            package_root,
            "--export-package-set",
            paths["set"],
            "--json",
        ],
        cwd=root,
        stdout_path=paths["set_stdout"],
    )
    validate_schema(
        root,
        "package-set",
        "package-maintenance-set-v1.schema.json",
        paths["set"],
    )

    run_checked(
        "export-verification-batch",
        [
            cglc,
            "package",
            "maintain",
            "--export-package-set-verification-batch",
            paths["batch"],
            "--verification",
            package_root,
            paths["set"],
            "--json",
        ],
        cwd=root,
        stdout_path=paths["batch_stdout"],
    )
    validate_schema(
        root,
        "verification-batch",
        "package-maintenance-set-verification-batch-v1.schema.json",
        paths["batch"],
    )

    run_checked(
        "verify-package-set-batch",
        [
            cglc,
            "package",
            "maintain",
            "--verify-package-set-batch",
            paths["batch"],
            "--summary-output",
            paths["summary"],
            "--json",
        ],
        cwd=root,
        stdout_path=paths["report"],
    )
    validate_schema(
        root,
        "verification-report",
        "package-maintenance-set-verification-batch-report-v1.schema.json",
        paths["report"],
    )
    validate_schema(
        root,
        "verification-summary",
        "package-maintenance-set-verification-batch-summary-v1.schema.json",
        paths["summary"],
    )
    expect_success("verify-package-set-batch", paths["report"])
    expect_success("verify-package-set-batch-summary", paths["summary"])

    run_checked(
        "promotion",
        [
            cglc,
            "package",
            "release",
            "--promotion-summary",
            paths["summary"],
            "--manifest-output",
            paths["promotion"],
            "--bundle-output",
            paths["bundle"],
            "--json",
        ],
        cwd=root,
        stdout_path=paths["promotion_stdout"],
    )
    validate_schema(
        root,
        "promotion-manifest",
        "package-release-promotion-manifest-v1.schema.json",
        paths["promotion"],
    )
    validate_schema(
        root,
        "promotion-stdout",
        "package-release-promotion-manifest-v1.schema.json",
        paths["promotion_stdout"],
    )
    validate_schema(
        root, "bundle", "package-release-bundle-v1.schema.json", paths["bundle"]
    )

    run_checked(
        "verify-bundle",
        [cglc, "package", "release", "--verify-bundle", paths["bundle"], "--json"],
        cwd=root,
        stdout_path=paths["bundle_verification"],
    )
    validate_schema(
        root,
        "bundle-verification",
        "package-release-bundle-verification-v1.schema.json",
        paths["bundle_verification"],
    )
    expect_success("verify-bundle", paths["bundle_verification"])

    run_checked(
        "plan-publish",
        [
            cglc,
            "package",
            "release",
            "--plan-publish",
            paths["bundle"],
            "--plan-output",
            paths["plan"],
            "--json",
        ],
        cwd=root,
        stdout_path=paths["plan_stdout"],
    )
    validate_schema(
        root,
        "publish-plan",
        "package-release-publish-plan-v1.schema.json",
        paths["plan"],
    )
    validate_schema(
        root,
        "publish-plan-stdout",
        "package-release-publish-plan-v1.schema.json",
        paths["plan_stdout"],
    )
    check_package_artifact_requirements_propagate(paths)
    check_package_reflection_summary_propagates(paths)
    check_publish_plan_windows_stage_path_budget(paths)
    check_native_publish_plan_gate(root, cglc, paths, work_dir)

    run_checked(
        "stage-publish",
        [
            cglc,
            "package",
            "release",
            "--stage-publish",
            paths["plan"],
            "--stage-output",
            paths["stage_dir"],
            "--json",
        ],
        cwd=root,
        stdout_path=paths["stage"],
    )
    validate_schema(
        root,
        "publish-stage",
        "package-release-publish-stage-v1.schema.json",
        paths["stage"],
    )
    expect_success("stage-publish", paths["stage"])
    check_native_publish_stage_gate(root, cglc, paths, work_dir)

    run_checked(
        "release-report-artifact-inventory",
        [
            cglc,
            "package",
            "release",
            "--report-artifact-inventory",
            "--report-bundle",
            paths["bundle"],
            "--report-publish-plan",
            paths["plan"],
            "--report-publish-stage",
            paths["stage"],
            "--json",
        ],
        cwd=root,
        stdout_path=paths["release_inventory"],
    )
    validate_schema(
        root,
        "release-report-artifact-inventory",
        "release-report-artifact-inventory-v1.schema.json",
        paths["release_inventory"],
    )
    check_release_report_artifact_inventory(paths)
    check_graphics_package_release_surfaces(paths, package_root)

    run_checked(
        "local-publish",
        [
            cglc,
            "package",
            "release",
            "--publish-stage",
            paths["stage"],
            "--publish-target",
            "local-filesystem",
            "--target-output",
            paths["local_target"],
            "--receipt-output",
            paths["receipt"],
            "--json",
        ],
        cwd=root,
        stdout_path=paths["receipt_stdout"],
    )
    validate_schema(
        root,
        "local-publish-receipt",
        "package-release-publish-receipt-v2.schema.json",
        paths["receipt"],
    )
    validate_schema(
        root,
        "local-publish-stdout",
        "package-release-publish-receipt-v2.schema.json",
        paths["receipt_stdout"],
    )
    expect_success("local-publish", paths["receipt"])
    check_graphics_package_publish_receipt(paths, package_root)

    write_json(
        paths["gcs_target"],
        {
            "schemaVersion": 1,
            "targetKind": "gcs",
            "enabled": False,
            "bucket": GCS_BUCKET,
            "prefix": GCS_PREFIX,
            "credentialsEnv": "GOOGLE_APPLICATION_CREDENTIALS",
        },
    )
    validate_schema(
        root,
        "gcs-target",
        "package-release-publish-target-v1.schema.json",
        paths["gcs_target"],
    )

    record_release_publish_guardrail(
        paths["guardrails"],
        operation="gcs-dry-run-manifest",
        target_kind="gcs",
        dry_run=True,
        allow_live_cloud_upload=allow_live_cloud_upload,
    )
    run_checked(
        "gcs-dry-run-manifest",
        [
            cglc,
            "package",
            "release",
            "--publish-stage",
            paths["stage"],
            "--publish-target",
            "gcs",
            "--target-descriptor",
            paths["gcs_target"],
            "--upload-manifest-output",
            paths["upload_manifest"],
            "--dry-run",
            "--json",
        ],
        cwd=root,
        stdout_path=paths["gcs_dry_run"],
    )
    validate_schema(
        root,
        "gcs-dry-run",
        "package-release-publish-receipt-v2.schema.json",
        paths["gcs_dry_run"],
    )
    validate_schema(
        root,
        "upload-manifest",
        "package-release-publish-upload-manifest-v1.schema.json",
        paths["upload_manifest"],
    )
    expect_success("gcs-dry-run", paths["gcs_dry_run"])
    check_graphics_package_upload_manifest(paths, package_root)

    record_release_publish_guardrail(
        paths["guardrails"],
        operation="upload-preflight",
        target_kind="gcs",
        dry_run=True,
        allow_live_cloud_upload=allow_live_cloud_upload,
    )
    run_checked(
        "upload-preflight",
        [
            cglc,
            "package",
            "release",
            "--upload-manifest",
            paths["upload_manifest"],
            "--upload-report-output",
            paths["preflight"],
            "--dry-run",
            "--json",
        ],
        cwd=root,
        stdout_path=paths["preflight_stdout"],
    )
    validate_schema(
        root,
        "upload-preflight",
        "package-release-publish-upload-preflight-v1.schema.json",
        paths["preflight"],
    )
    validate_schema(
        root,
        "upload-preflight-stdout",
        "package-release-publish-upload-preflight-v1.schema.json",
        paths["preflight_stdout"],
    )
    expect_success("upload-preflight", paths["preflight"])

    record_release_publish_guardrail(
        paths["guardrails"],
        operation="mock-upload",
        target_kind="gcs",
        mock_upload=True,
        allow_live_cloud_upload=allow_live_cloud_upload,
    )
    run_checked(
        "mock-upload",
        [
            cglc,
            "package",
            "release",
            "--upload-manifest",
            paths["upload_manifest"],
            "--mock-upload",
            "--upload-report-output",
            paths["mock_batch"],
            "--upload-receipt-output",
            paths["mock_receipt"],
            "--json",
        ],
        cwd=root,
        stdout_path=paths["mock_batch_stdout"],
    )
    validate_schema(
        root,
        "mock-upload-batch",
        "package-release-publish-upload-batch-v1.schema.json",
        paths["mock_batch"],
    )
    validate_schema(
        root,
        "mock-upload-stdout",
        "package-release-publish-upload-batch-v1.schema.json",
        paths["mock_batch_stdout"],
    )
    validate_schema(
        root,
        "mock-upload-receipt",
        "package-release-publish-upload-receipt-v1.schema.json",
        paths["mock_receipt"],
    )
    expect_success("mock-upload", paths["mock_batch"])

    fake_env, fake_log = make_fake_gcloud_env(work_dir)
    record_release_publish_guardrail(
        paths["guardrails"],
        operation="fake-gcloud-upload",
        target_kind="gcs",
        local_only=True,
        allow_live_cloud_upload=allow_live_cloud_upload,
        env=fake_env,
    )
    run_checked(
        "fake-gcloud-upload",
        [
            cglc,
            "package",
            "release",
            "--upload-manifest",
            paths["upload_manifest"],
            "--gcs-upload",
            "--upload-report-output",
            paths["gcs_batch"],
            "--upload-receipt-output",
            paths["gcs_receipt"],
            "--json",
        ],
        cwd=root,
        env=fake_env,
        stdout_path=paths["gcs_batch_stdout"],
    )
    validate_schema(
        root,
        "fake-gcloud-upload-batch",
        "package-release-publish-upload-batch-v1.schema.json",
        paths["gcs_batch"],
    )
    validate_schema(
        root,
        "fake-gcloud-upload-stdout",
        "package-release-publish-upload-batch-v1.schema.json",
        paths["gcs_batch_stdout"],
    )
    validate_schema(
        root,
        "fake-gcloud-upload-receipt",
        "package-release-publish-upload-receipt-v1.schema.json",
        paths["gcs_receipt"],
    )
    expect_success("fake-gcloud-upload", paths["gcs_batch"])
    check_fake_gcloud_log(fake_log, paths["upload_manifest"])

    run_checked(
        "release-provenance-manifest",
        [
            sys.executable,
            root / "tools" / "check_release_provenance_manifest.py",
            "--root",
            root,
            "--artifact-root",
            root,
            "--from-stage-report",
            paths["stage"],
            "--guardrails",
            paths["guardrails"],
            "--manifest-output",
            paths["provenance_manifest"],
            "--toolchain",
            f"cglc={display_local_path(root, cglc)}",
        ],
        cwd=root,
    )
    validate_schema(
        root,
        "release-provenance-manifest",
        "release-provenance-manifest-v1.schema.json",
        paths["provenance_manifest"],
    )
    check_graphics_package_release_provenance(paths, package_root)
    print(f"release provenance manifest artifact: {paths['provenance_manifest']}")
    rc_handoff = write_release_publish_rc_handoff_evidence(work_dir, paths)
    print_release_publish_rc_handoff_evidence(paths["rc_handoff"], rc_handoff)

    check_missing_source_hash_blocks_promotion(root, cglc, paths, package_root)

    print(f"validated package release publish flow in {work_dir}")


def check_guardrail_self_test():
    check_windows_stage_path_budget_self_test()

    denied = release_publish_guardrail_record(
        operation="future-live-upload",
        target_kind="gcs",
        env={},
    )
    try:
        require_release_publish_guardrail(denied)
    except CheckError as exc:
        if LIVE_CLOUD_UPLOAD_ENV not in str(exc):
            raise CheckError("guardrail denial did not name the opt-in environment")
    else:
        raise CheckError("guardrail allowed live GCS upload without opt-in")

    missing_evidence = release_publish_guardrail_record(
        operation="future-live-upload",
        target_kind="gcs",
        allow_live_cloud_upload=True,
    )
    try:
        require_release_publish_guardrail(missing_evidence)
    except CheckError as exc:
        if "approvalEvidence" not in str(exc):
            raise CheckError("guardrail denial did not name approval evidence")
    else:
        raise CheckError("guardrail allowed live GCS upload without approval evidence")

    placeholder_evidence = sample_live_cloud_approval_evidence()
    placeholder_evidence["budgetGuardrail"] = "<approved-budget-limit>"
    placeholder_record = release_publish_guardrail_record(
        operation="future-live-upload",
        target_kind="gcs",
        allow_live_cloud_upload=True,
        approval_evidence=placeholder_evidence,
    )
    try:
        require_release_publish_guardrail(placeholder_record)
    except CheckError as exc:
        if "placeholder" not in str(exc):
            raise CheckError("guardrail denial did not name placeholder evidence")
    else:
        raise CheckError("guardrail allowed placeholder live GCS approval evidence")

    for label, kwargs in (
        ("dry-run", {"dry_run": True}),
        ("local-only", {"local_only": True}),
        ("mock", {"mock_upload": True}),
        (
            "cli-opt-in",
            {
                "allow_live_cloud_upload": True,
                "approval_evidence": sample_live_cloud_approval_evidence(),
            },
        ),
        (
            "env-opt-in",
            {
                "env": {LIVE_CLOUD_UPLOAD_ENV: "1"},
                "approval_evidence": sample_live_cloud_approval_evidence(),
            },
        ),
    ):
        record = release_publish_guardrail_record(
            operation=f"self-test-{label}",
            target_kind="gcs",
            **kwargs,
        )
        require_release_publish_guardrail(record)

    with tempfile.TemporaryDirectory(prefix="crossgl-release-guardrails-") as tmp:
        guardrails = Path(tmp) / "guardrails.json"
        record_release_publish_guardrail(
            guardrails,
            operation="self-test-dry-run-record",
            target_kind="gcs",
            dry_run=True,
            env={},
        )
        payload = load_json(guardrails)
        records = payload.get("records")
        if not isinstance(records, list) or len(records) != 1:
            raise CheckError("guardrail record file did not capture one record")
        if records[0].get("mode") != DRY_RUN_GUARDRAIL_MODE:
            raise CheckError("guardrail record file did not record dry-run mode")

    print("validated release publish cloud upload guardrails")

    with tempfile.TemporaryDirectory(prefix="crossgl-release-rc-handoff-") as tmp:
        work_dir = Path(tmp)
        paths = {
            "release_inventory": work_dir / "release-report-artifact-inventory.json",
            "guardrails": work_dir / "package-release-publish-guardrails.json",
            "gcs_dry_run": work_dir / "package-release-publish-gcs-dry-run.json",
            "upload_manifest": work_dir
            / "package-release-publish-upload-manifest.json",
            "provenance_manifest": work_dir
            / "package-release-provenance-manifest.json",
            "rc_handoff": work_dir / "package-release-publish-rc-handoff-evidence.json",
            "preflight": work_dir / "package-release-publish-upload-preflight.json",
            "mock_receipt": work_dir / "package-release-publish-upload-receipt.json",
            "gcs_receipt": work_dir / "package-release-publish-upload-receipt-gcs.json",
        }
        for key, path in paths.items():
            if key not in {"guardrails", "rc_handoff"}:
                write_json(path, {"selfTest": key})
        for operation, kwargs in (
            ("self-test-dry-run", {"dry_run": True}),
            ("self-test-mock", {"mock_upload": True}),
            ("self-test-local-only", {"local_only": True}),
        ):
            record_release_publish_guardrail(
                paths["guardrails"],
                operation=operation,
                target_kind="gcs",
                env={},
                **kwargs,
            )
        payload = write_release_publish_rc_handoff_evidence(work_dir, paths)
        if not paths["rc_handoff"].is_file():
            raise CheckError("RC handoff evidence file was not written")
        handoff = payload["rcHandoffEvidence"]
        if handoff["provenanceManifestPath"] != local_evidence_path(
            paths["provenance_manifest"]
        ):
            raise CheckError("RC handoff evidence missed provenance manifest path")
        if handoff["artifactInventoryPath"] != local_evidence_path(
            paths["release_inventory"]
        ):
            raise CheckError("RC handoff evidence missed artifact inventory path")
        for field in (
            "guardrailRecordPath",
            "dryRunReceiptPaths",
            "preflightReportPath",
            "mockReceiptPaths",
            "fakeGcloudReceiptPaths",
        ):
            if field not in handoff:
                raise CheckError(f"RC handoff evidence missed {field}")

        bad_payload = load_json(paths["rc_handoff"])
        bad_payload["rcHandoffEvidence"]["dryRunReceiptPaths"] = [
            "gs://crossgl-release-dry-run/package-release-publish-gcs-dry-run.json"
        ]
        bad_payload["dryRunArtifactEvidence"]["dryRunReceiptPaths"] = bad_payload[
            "rcHandoffEvidence"
        ]["dryRunReceiptPaths"]
        try:
            require_release_publish_rc_handoff_evidence(bad_payload)
        except CheckError as exc:
            if "provider/network URI" not in str(exc):
                raise CheckError("RC handoff URI rejection did not explain the issue")
        else:
            raise CheckError("RC handoff evidence accepted provider URI path")

        live_guardrails = work_dir / "live-guardrails.json"
        write_json(
            live_guardrails,
            {
                "schemaVersion": 1,
                "records": [
                    release_publish_guardrail_record(
                        operation="self-test-live-opt-in",
                        target_kind="gcs",
                        allow_live_cloud_upload=True,
                        approval_evidence=sample_live_cloud_approval_evidence(),
                    )
                ],
            },
        )
        bad_payload = load_json(paths["rc_handoff"])
        bad_payload["rcHandoffEvidence"]["guardrailRecordPath"] = local_evidence_path(
            live_guardrails
        )
        bad_payload["dryRunArtifactEvidence"]["guardrailRecordPath"] = (
            local_evidence_path(live_guardrails)
        )
        try:
            require_release_publish_rc_handoff_evidence(bad_payload)
        except CheckError as exc:
            if "live cloud" not in str(exc):
                raise CheckError("RC handoff live-opt-in rejection was unclear")
        else:
            raise CheckError("RC handoff evidence accepted live cloud opt-in")

    print("validated release publish RC handoff evidence")


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path)
    parser.add_argument("--cglc", type=Path)
    parser.add_argument("--work-dir", type=Path)
    parser.add_argument(
        "--allow-cloud-upload",
        action="store_true",
        help=(
            "Allow a future live cloud release upload path. The default release "
            "flow remains dry-run, mock, or local-only."
        ),
    )
    parser.add_argument(
        "--self-test",
        action="store_true",
        help="Run offline release-flow checks without invoking cglc or cloud tools.",
    )
    return parser.parse_args()


def main():
    args = parse_args()
    if args.self_test:
        check_guardrail_self_test()
        return
    if args.root is None:
        raise CheckError("--root is required unless --self-test is used")
    if args.cglc is None:
        raise CheckError("--cglc is required unless --self-test is used")
    root = args.root.resolve()
    cglc = args.cglc.resolve()
    if not cglc.exists():
        raise CheckError(f"cglc not found: {cglc}")

    if args.work_dir is None:
        with tempfile.TemporaryDirectory(prefix="crossgl-release-flow-") as tmp:
            check_flow(
                root,
                cglc,
                Path(tmp),
                allow_live_cloud_upload=args.allow_cloud_upload,
            )
    else:
        check_flow(
            root,
            cglc,
            args.work_dir.resolve(),
            allow_live_cloud_upload=args.allow_cloud_upload,
        )


if __name__ == "__main__":
    try:
        main()
    except CheckError as exc:
        print(str(exc), file=sys.stderr)
        sys.exit(1)
