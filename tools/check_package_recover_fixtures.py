#!/usr/bin/env python3
"""Check package sidecar recovery behavior with synthetic packages."""

import argparse
import hashlib
import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path, PureWindowsPath

from check_package_integrity_fixtures import (
    MODULE_NAME,
    add_native_artifact_descriptor,
    make_package,
    mark_native_artifact_validated,
    nonuniform_target_features,
    package_path,
    rewrite_manifest,
    write_nonuniform_diagnostics,
    write_nonuniform_reflection,
)
from package_fixture_json_contracts import (
    expect_array,
    expect_equal,
    expect_object,
)
from source_location_fixture_checks import expect_location_span_coherent


SEVERITIES = ("note", "warning", "error")
RECOVERY_DIAGNOSTIC_PREFIXES = ("package.recover.", "package.verify.")


def run_recover(cglc, package, *args, source=None, json_output=False):
    command = [str(cglc), "package", "recover", str(package), *args]
    if source is not None:
        command.extend(["--source", str(source)])
    if json_output:
        command.append("--json")
    return subprocess.run(
        command,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )


def run_maintain(cglc, package, *args, json_output=False):
    command = [str(cglc), "package", "maintain", str(package), *args]
    if json_output:
        command.append("--json")
    return subprocess.run(
        command,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )


def run_maintain_scan(cglc, scan_dir, *args, json_output=False):
    command = [str(cglc), "package", "maintain", "--scan", str(scan_dir), *args]
    if json_output:
        command.append("--json")
    return subprocess.run(
        command,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )


def run_maintain_package_set(cglc, set_path, *args, json_output=False):
    command = [
        str(cglc),
        "package",
        "maintain",
        "--package-set",
        str(set_path),
        *args,
    ]
    if json_output:
        command.append("--json")
    return subprocess.run(
        command,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )


def run_maintain_verification_batch(cglc, batch_path, *args, json_output=False):
    command = [
        str(cglc),
        "package",
        "maintain",
        "--verify-package-set-batch",
        str(batch_path),
        *args,
    ]
    if json_output:
        command.append("--json")
    return subprocess.run(
        command,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )


def run_maintain_export_verification_batch(
    cglc,
    batch_path,
    *args,
    json_output=False,
):
    command = [
        str(cglc),
        "package",
        "maintain",
        "--export-package-set-verification-batch",
        str(batch_path),
        *args,
    ]
    if json_output:
        command.append("--json")
    return subprocess.run(
        command,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )


def run_package_release(cglc, *args, json_output=False, env=None):
    command = [str(cglc), "package", "release", *args]
    if json_output:
        command.append("--json")
    return subprocess.run(
        command,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=env,
    )


def make_fake_gcloud_env(scan_dir):
    fake_bin = scan_dir / "fake-gcloud-bin"
    fake_bin.mkdir(parents=True, exist_ok=True)
    fake_log = scan_dir / "fake-gcloud.log"
    fake_credentials = scan_dir / "fake-google-application-credentials.json"
    fake_credentials.write_text(
        json.dumps({"type": "service_account", "project_id": "crossgl-test"}),
        encoding="utf-8",
    )

    if os.name == "nt":
        gcloud_path = fake_bin / "gcloud.cmd"
        gcloud_path.write_text(
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
                    ":scan_args",
                    'if not "%CROSSGL_FAKE_GCLOUD_FAIL_CP%"=="" goto fail_cp',
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
                    ":fail_cp",
                    "echo captured fake gcloud upload failure 1>&2",
                    "exit /b 41",
                    ":describe",
                    'echo {"generation":"1700000000000000","metageneration":"7","crc32c":"ImIEBA==","md5Hash":"1B2M2Y8AsgTpgAmY7PhCfg=="}',
                    "exit /b 0",
                    "",
                ]
            ),
            encoding="utf-8",
        )
    else:
        gcloud_path = fake_bin / "gcloud"
        gcloud_path.write_text(
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
                    'if [ -n "${CROSSGL_FAKE_GCLOUD_FAIL_CP:-}" ]; then',
                    '  echo "captured fake gcloud upload failure" >&2',
                    "  exit 41",
                    "fi",
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
        gcloud_path.chmod(0o755)

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


def run_verify(cglc, package, source=None):
    command = [str(cglc), "package", "verify", str(package)]
    if source is not None:
        command.extend(["--source", str(source)])
    return subprocess.run(
        command,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )


def expect_success(result, case_name, expected_stdout):
    errors = []
    if result.returncode != 0:
        errors.append(
            f"{case_name}: expected success, got {result.stderr}{result.stdout}".strip()
        )
    if expected_stdout not in result.stdout:
        errors.append(
            f"{case_name}: expected stdout substring {expected_stdout!r}; "
            f"got {result.stdout.strip()!r}"
        )
    if result.stderr:
        errors.append(f"{case_name}: expected no diagnostics, got {result.stderr!r}")
    return errors


def expect_failure(result, case_name, expected_output):
    output = result.stderr + result.stdout
    errors = []
    if result.returncode == 0:
        errors.append(f"{case_name}: expected failure")
    if expected_output not in output:
        errors.append(
            f"{case_name}: expected output substring {expected_output!r}; "
            f"got {output.strip()!r}"
        )
    return errors


def expect_verified(cglc, case_name, package, source):
    result = run_verify(cglc, package, source=source)
    if result.returncode == 0:
        return []
    return [
        f"{case_name}: expected recovered package to verify, got "
        f"{result.stderr}{result.stdout}".strip()
    ]


def expect_nonuniform_metadata_preserved(
    case_name,
    package,
    target,
    expected_diagnostics,
):
    errors = []
    try:
        reflection = json.loads(
            (package / "reflection.json").read_text(encoding="utf-8")
        )
        diagnostics = json.loads(
            (package / "diagnostics.json").read_text(encoding="utf-8")
        )
    except (OSError, json.JSONDecodeError) as exc:
        return [f"{case_name}: failed to read promoted metadata: {exc}"]
    expected_features = nonuniform_target_features(target)
    if reflection.get("targetFeatures") != expected_features:
        errors.append(
            f"{case_name}: expected promoted reflection.targetFeatures "
            f"{expected_features!r}, got {reflection.get('targetFeatures')!r}"
        )
    if diagnostics != expected_diagnostics:
        errors.append(
            f"{case_name}: expected promoted diagnostics {expected_diagnostics!r}, "
            f"got {diagnostics!r}"
        )
    return errors


def validate_schema(root, tmp_dir, case_name, recovery_json):
    instance_path = tmp_dir / f"{case_name}.package-recover.json"
    instance_path.write_text(recovery_json, encoding="utf-8")
    result = subprocess.run(
        [
            sys.executable,
            str(root / "tools" / "validate_json_schema.py"),
            "--schema",
            str(root / "docs" / "schemas" / "package-recover-v1.schema.json"),
            "--instance",
            str(instance_path),
        ],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if result.returncode != 0:
        return [
            f"{case_name}: package recover JSON failed schema validation: "
            f"{result.stderr}{result.stdout}".strip()
        ]
    return []


def validate_sidecar_schema(root, tmp_dir, case_name, sidecars_json):
    instance_path = tmp_dir / f"{case_name}.package-sidecars.json"
    instance_path.write_text(sidecars_json, encoding="utf-8")
    result = subprocess.run(
        [
            sys.executable,
            str(root / "tools" / "validate_json_schema.py"),
            "--schema",
            str(root / "docs" / "schemas" / "package-sidecars-v1.schema.json"),
            "--instance",
            str(instance_path),
        ],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if result.returncode != 0:
        return [
            f"{case_name}: package sidecars JSON failed schema validation: "
            f"{result.stderr}{result.stdout}".strip()
        ]
    return []


def validate_stale_cleanup_schema(root, tmp_dir, case_name, cleanup_json):
    instance_path = tmp_dir / f"{case_name}.package-stale-sidecars.json"
    instance_path.write_text(cleanup_json, encoding="utf-8")
    result = subprocess.run(
        [
            sys.executable,
            str(root / "tools" / "validate_json_schema.py"),
            "--schema",
            str(root / "docs" / "schemas" / "package-stale-sidecars-v1.schema.json"),
            "--instance",
            str(instance_path),
        ],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if result.returncode != 0:
        return [
            f"{case_name}: stale sidecar cleanup JSON failed schema validation: "
            f"{result.stderr}{result.stdout}".strip()
        ]
    return []


def validate_policy_schema(root, case_name, policy_path):
    result = subprocess.run(
        [
            sys.executable,
            str(root / "tools" / "validate_json_schema.py"),
            "--schema",
            str(
                root / "docs" / "schemas" / "package-maintenance-policy-v1.schema.json"
            ),
            "--instance",
            str(policy_path),
        ],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if result.returncode != 0:
        return [
            f"{case_name}: package maintenance policy JSON failed schema "
            f"validation: {result.stderr}{result.stdout}".strip()
        ]
    return []


def validate_maintenance_report_schema(root, tmp_dir, case_name, report_json):
    instance_path = tmp_dir / f"{case_name}.package-maintenance-report.json"
    instance_path.write_text(report_json, encoding="utf-8")
    result = subprocess.run(
        [
            sys.executable,
            str(root / "tools" / "validate_json_schema.py"),
            "--schema",
            str(
                root / "docs" / "schemas" / "package-maintenance-report-v1.schema.json"
            ),
            "--instance",
            str(instance_path),
        ],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if result.returncode != 0:
        return [
            f"{case_name}: package maintenance report JSON failed schema "
            f"validation: {result.stderr}{result.stdout}".strip()
        ]
    return []


def validate_maintenance_set_schema(root, case_name, set_path):
    result = subprocess.run(
        [
            sys.executable,
            str(root / "tools" / "validate_json_schema.py"),
            "--schema",
            str(root / "docs" / "schemas" / "package-maintenance-set-v1.schema.json"),
            "--instance",
            str(set_path),
        ],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if result.returncode != 0:
        return [
            f"{case_name}: package maintenance set JSON failed schema "
            f"validation: {result.stderr}{result.stdout}".strip()
        ]
    return []


def validate_maintenance_set_report_schema(root, tmp_dir, case_name, report_json):
    instance_path = tmp_dir / f"{case_name}.package-maintenance-set-report.json"
    instance_path.write_text(report_json, encoding="utf-8")
    result = subprocess.run(
        [
            sys.executable,
            str(root / "tools" / "validate_json_schema.py"),
            "--schema",
            str(
                root
                / "docs"
                / "schemas"
                / "package-maintenance-set-report-v1.schema.json"
            ),
            "--instance",
            str(instance_path),
        ],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if result.returncode != 0:
        return [
            f"{case_name}: package maintenance set report JSON failed schema "
            f"validation: {result.stderr}{result.stdout}".strip()
        ]
    return []


def validate_maintenance_set_verification_schema(
    root,
    tmp_dir,
    case_name,
    verification_json,
):
    instance_path = tmp_dir / f"{case_name}.package-maintenance-set-verification.json"
    instance_path.write_text(verification_json, encoding="utf-8")
    result = subprocess.run(
        [
            sys.executable,
            str(root / "tools" / "validate_json_schema.py"),
            "--schema",
            str(
                root
                / "docs"
                / "schemas"
                / "package-maintenance-set-verification-v1.schema.json"
            ),
            "--instance",
            str(instance_path),
        ],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if result.returncode != 0:
        return [
            f"{case_name}: package maintenance set verification JSON failed "
            f"schema validation: {result.stderr}{result.stdout}".strip()
        ]
    return []


def validate_maintenance_set_verification_batch_schema(root, case_name, batch_path):
    result = subprocess.run(
        [
            sys.executable,
            str(root / "tools" / "validate_json_schema.py"),
            "--schema",
            str(
                root
                / "docs"
                / "schemas"
                / "package-maintenance-set-verification-batch-v1.schema.json"
            ),
            "--instance",
            str(batch_path),
        ],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if result.returncode != 0:
        return [
            f"{case_name}: package maintenance set verification batch JSON "
            f"failed schema validation: {result.stderr}{result.stdout}".strip()
        ]
    return []


def validate_maintenance_set_verification_batch_report_schema(
    root,
    tmp_dir,
    case_name,
    batch_json,
):
    instance_path = (
        tmp_dir / f"{case_name}.package-maintenance-set-verification-batch-report.json"
    )
    instance_path.write_text(batch_json, encoding="utf-8")
    result = subprocess.run(
        [
            sys.executable,
            str(root / "tools" / "validate_json_schema.py"),
            "--schema",
            str(
                root
                / "docs"
                / "schemas"
                / "package-maintenance-set-verification-batch-report-v1.schema.json"
            ),
            "--instance",
            str(instance_path),
        ],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if result.returncode != 0:
        return [
            f"{case_name}: package maintenance set verification batch report "
            f"JSON failed schema validation: {result.stderr}{result.stdout}".strip()
        ]
    return []


def validate_maintenance_set_verification_batch_summary_schema(
    root,
    case_name,
    summary_path,
):
    result = subprocess.run(
        [
            sys.executable,
            str(root / "tools" / "validate_json_schema.py"),
            "--schema",
            str(
                root
                / "docs"
                / "schemas"
                / "package-maintenance-set-verification-batch-summary-v1.schema.json"
            ),
            "--instance",
            str(summary_path),
        ],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if result.returncode != 0:
        return [
            f"{case_name}: package maintenance set verification batch summary "
            f"JSON failed schema validation: {result.stderr}{result.stdout}".strip()
        ]
    return []


def validate_release_promotion_manifest_schema(root, case_name, manifest_path):
    result = subprocess.run(
        [
            sys.executable,
            str(root / "tools" / "validate_json_schema.py"),
            "--schema",
            str(
                root
                / "docs"
                / "schemas"
                / "package-release-promotion-manifest-v1.schema.json"
            ),
            "--instance",
            str(manifest_path),
        ],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if result.returncode != 0:
        return [
            f"{case_name}: package release promotion manifest JSON failed "
            f"schema validation: {result.stderr}{result.stdout}".strip()
        ]
    return []


def validate_release_bundle_schema(root, case_name, bundle_path):
    result = subprocess.run(
        [
            sys.executable,
            str(root / "tools" / "validate_json_schema.py"),
            "--schema",
            str(root / "docs" / "schemas" / "package-release-bundle-v1.schema.json"),
            "--instance",
            str(bundle_path),
        ],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if result.returncode != 0:
        return [
            f"{case_name}: package release bundle JSON failed schema "
            f"validation: {result.stderr}{result.stdout}".strip()
        ]
    return []


def validate_release_bundle_verification_schema(
    root,
    tmp_dir,
    case_name,
    report_text,
):
    report_path = tmp_dir / f"{case_name}-release-bundle-verification.json"
    report_path.write_text(report_text, encoding="utf-8")
    result = subprocess.run(
        [
            sys.executable,
            str(root / "tools" / "validate_json_schema.py"),
            "--schema",
            str(
                root
                / "docs"
                / "schemas"
                / "package-release-bundle-verification-v1.schema.json"
            ),
            "--instance",
            str(report_path),
        ],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if result.returncode != 0:
        return [
            f"{case_name}: package release bundle verification JSON failed "
            f"schema validation: {result.stderr}{result.stdout}".strip()
        ]
    return []


def expect_release_bundle_verification_bundle_path(
    errors,
    case_name,
    actual,
    expected_bundle_path,
):
    if not isinstance(actual, str):
        errors.append(f"{case_name}: expected bundlePath string, got {actual!r}")
        return
    if actual.strip() != actual or actual == "":
        errors.append(
            f"{case_name}: expected bundlePath to be a non-empty normalized "
            f"relative path, got {actual!r}"
        )
        return
    if "\\" in actual:
        errors.append(
            f"{case_name}: expected bundlePath to use '/' separators, got {actual!r}"
        )
        return
    if actual.startswith("/"):
        errors.append(
            f"{case_name}: expected bundlePath to be relative, got {actual!r}"
        )
        return
    windows_path = PureWindowsPath(actual)
    if windows_path.drive or windows_path.root:
        errors.append(
            f"{case_name}: expected bundlePath to be drive-free and relative, "
            f"got {actual!r}"
        )
        return
    parts = actual.split("/")
    if any(part in ("", ".", "..") for part in parts):
        errors.append(
            f"{case_name}: expected bundlePath to be normalized and relative, "
            f"got {actual!r}"
        )
        return
    referenced_path = Path(actual)
    resolved_path = (expected_bundle_path.parent / referenced_path).resolve(
        strict=False
    )
    expected_path = expected_bundle_path.resolve(strict=False)
    if resolved_path != expected_path:
        errors.append(
            f"{case_name}: expected bundlePath {actual!r} to resolve under "
            f"{expected_bundle_path.parent.as_posix()} to "
            f"{expected_bundle_path.as_posix()}, got {resolved_path.as_posix()}"
        )


def validate_release_publish_plan_schema(root, case_name, plan_path):
    result = subprocess.run(
        [
            sys.executable,
            str(root / "tools" / "validate_json_schema.py"),
            "--schema",
            str(
                root
                / "docs"
                / "schemas"
                / "package-release-publish-plan-v1.schema.json"
            ),
            "--instance",
            str(plan_path),
        ],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if result.returncode != 0:
        return [
            f"{case_name}: package release publish plan JSON failed schema "
            f"validation: {result.stderr}{result.stdout}".strip()
        ]
    return []


def validate_release_publish_stage_schema(root, tmp_dir, case_name, report_text):
    report_path = tmp_dir / f"{case_name}-release-publish-stage.json"
    report_path.write_text(report_text, encoding="utf-8")
    result = subprocess.run(
        [
            sys.executable,
            str(root / "tools" / "validate_json_schema.py"),
            "--schema",
            str(
                root
                / "docs"
                / "schemas"
                / "package-release-publish-stage-v1.schema.json"
            ),
            "--instance",
            str(report_path),
        ],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if result.returncode != 0:
        return [
            f"{case_name}: package release publish stage JSON failed schema "
            f"validation: {result.stderr}{result.stdout}".strip()
        ]
    return []


def validate_release_publish_receipt_schema(root, tmp_dir, case_name, report_text):
    report_path = tmp_dir / f"{case_name}-release-publish-receipt.json"
    report_path.write_text(report_text, encoding="utf-8")
    result = subprocess.run(
        [
            sys.executable,
            str(root / "tools" / "validate_json_schema.py"),
            "--schema",
            str(
                root
                / "docs"
                / "schemas"
                / "package-release-publish-receipt-v2.schema.json"
            ),
            "--instance",
            str(report_path),
        ],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if result.returncode != 0:
        return [
            f"{case_name}: package release publish receipt JSON failed schema "
            f"validation: {result.stderr}{result.stdout}".strip()
        ]
    return []


def validate_release_publish_upload_manifest_schema(root, case_name, manifest_path):
    result = subprocess.run(
        [
            sys.executable,
            str(root / "tools" / "validate_json_schema.py"),
            "--schema",
            str(
                root
                / "docs"
                / "schemas"
                / "package-release-publish-upload-manifest-v1.schema.json"
            ),
            "--instance",
            str(manifest_path),
        ],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if result.returncode != 0:
        return [
            f"{case_name}: package release publish upload manifest JSON "
            f"failed schema validation: {result.stderr}{result.stdout}".strip()
        ]
    return []


def validate_release_publish_upload_preflight_schema(
    root, tmp_dir, case_name, report_text
):
    report_path = tmp_dir / f"{case_name}-release-publish-upload-preflight.json"
    report_path.write_text(report_text, encoding="utf-8")
    return validate_release_publish_upload_preflight_file_schema(
        root, case_name, report_path
    )


def validate_release_publish_upload_preflight_file_schema(root, case_name, report_path):
    result = subprocess.run(
        [
            sys.executable,
            str(root / "tools" / "validate_json_schema.py"),
            "--schema",
            str(
                root
                / "docs"
                / "schemas"
                / "package-release-publish-upload-preflight-v1.schema.json"
            ),
            "--instance",
            str(report_path),
        ],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if result.returncode != 0:
        return [
            f"{case_name}: package release publish upload preflight JSON "
            f"failed schema validation: {result.stderr}{result.stdout}".strip()
        ]
    return []


def validate_release_publish_upload_batch_schema(root, tmp_dir, case_name, report_text):
    report_path = tmp_dir / f"{case_name}-release-publish-upload-batch.json"
    report_path.write_text(report_text, encoding="utf-8")
    return validate_release_publish_upload_batch_file_schema(
        root, case_name, report_path
    )


def validate_release_publish_upload_batch_file_schema(root, case_name, report_path):
    result = subprocess.run(
        [
            sys.executable,
            str(root / "tools" / "validate_json_schema.py"),
            "--schema",
            str(
                root
                / "docs"
                / "schemas"
                / "package-release-publish-upload-batch-v1.schema.json"
            ),
            "--instance",
            str(report_path),
        ],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if result.returncode != 0:
        return [
            f"{case_name}: package release publish upload batch JSON failed "
            f"schema validation: {result.stderr}{result.stdout}".strip()
        ]
    return []


def validate_release_publish_upload_receipt_file_schema(root, case_name, receipt_path):
    result = subprocess.run(
        [
            sys.executable,
            str(root / "tools" / "validate_json_schema.py"),
            "--schema",
            str(
                root
                / "docs"
                / "schemas"
                / "package-release-publish-upload-receipt-v1.schema.json"
            ),
            "--instance",
            str(receipt_path),
        ],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if result.returncode != 0:
        return [
            f"{case_name}: package release publish upload receipt JSON failed "
            f"schema validation: {result.stderr}{result.stdout}".strip()
        ]
    return []


def validate_release_publish_target_schema(root, case_name, target_path):
    result = subprocess.run(
        [
            sys.executable,
            str(root / "tools" / "validate_json_schema.py"),
            "--schema",
            str(
                root
                / "docs"
                / "schemas"
                / "package-release-publish-target-v1.schema.json"
            ),
            "--instance",
            str(target_path),
        ],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if result.returncode != 0:
        return [
            f"{case_name}: package release publish target JSON failed schema "
            f"validation: {result.stderr}{result.stdout}".strip()
        ]
    return []


def parse_json_payload(errors, result, case_name):
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        errors.append(
            f"{case_name}: expected JSON stdout, got {result.stdout!r}: {exc}"
        )
        return {}


def file_sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def expect_recovery_json(
    errors,
    root,
    tmp_dir,
    case_name,
    result,
    *,
    action,
    sidecar,
    requested=None,
    success,
    backup_present=False,
    message_substring=None,
    diagnostic_code=None,
):
    if result.stderr:
        errors.append(f"{case_name}: expected JSON mode to keep stderr empty")
    errors.extend(validate_schema(root, tmp_dir, case_name, result.stdout))
    payload = parse_json_payload(errors, result, case_name)
    if not isinstance(payload, dict):
        errors.append(f"{case_name}: expected recovery JSON output to be an object")
        return {}

    expect_equal(errors, case_name, "schemaVersion", payload.get("schemaVersion"), 1)
    expect_equal(errors, case_name, "action", payload.get("action"), action)
    expect_equal(errors, case_name, "success", payload.get("success"), success)
    expect_equal(
        errors,
        case_name,
        "sidecarPath",
        payload.get("sidecarPath"),
        sidecar.as_posix(),
    )
    expect_equal(
        errors,
        case_name,
        "requestedPath",
        payload.get("requestedPath"),
        None if requested is None else requested.as_posix(),
    )
    if backup_present:
        if not isinstance(payload.get("backupPath"), str):
            errors.append(f"{case_name}: expected backupPath string")
    else:
        expect_equal(errors, case_name, "backupPath", payload.get("backupPath"), None)
    expect_equal(
        errors,
        case_name,
        "replacedExisting",
        payload.get("replacedExisting"),
        backup_present,
    )

    if message_substring is not None:
        message = payload.get("message")
        if not isinstance(message, str) or message_substring not in message:
            errors.append(
                f"{case_name}: expected message containing "
                f"{message_substring!r}, got {message!r}"
            )
    elif success:
        if not isinstance(payload.get("message"), str):
            errors.append(f"{case_name}: expected successful recovery message")
    else:
        expect_equal(errors, case_name, "message", payload.get("message"), None)

    diagnostic_counts = expect_object(
        errors,
        case_name,
        "diagnosticCounts",
        payload.get("diagnosticCounts"),
    )
    diagnostics = expect_array(
        errors,
        case_name,
        "diagnostics",
        payload.get("diagnostics"),
    )
    actual_counts = {severity: 0 for severity in SEVERITIES}
    for index, diagnostic in enumerate(diagnostics):
        diagnostic_path = f"diagnostics[{index}]"
        if not isinstance(diagnostic, dict):
            errors.append(f"{case_name}: expected {diagnostic_path} to be an object")
            continue
        severity = diagnostic.get("severity")
        if severity in actual_counts:
            actual_counts[severity] += 1
        else:
            errors.append(
                f"{case_name}: expected {diagnostic_path}.severity to be one "
                f"of {SEVERITIES!r}, got {severity!r}"
            )
        code = diagnostic.get("code")
        if not isinstance(code, str) or not code.startswith(
            RECOVERY_DIAGNOSTIC_PREFIXES
        ):
            errors.append(
                f"{case_name}: expected {diagnostic_path}.code to start with "
                f"{RECOVERY_DIAGNOSTIC_PREFIXES!r}, got {code!r}"
            )
        expect_location_span_coherent(
            errors,
            case_name,
            f"{diagnostic_path}.location",
            diagnostic.get("location"),
        )

    for severity in SEVERITIES:
        expect_equal(
            errors,
            case_name,
            f"diagnosticCounts.{severity}",
            diagnostic_counts.get(severity),
            actual_counts[severity],
        )
    expect_equal(
        errors,
        case_name,
        "success",
        payload.get("success"),
        actual_counts["error"] == 0,
    )
    if diagnostic_code is not None and not any(
        diagnostic.get("code") == diagnostic_code
        for diagnostic in diagnostics
        if isinstance(diagnostic, dict)
    ):
        errors.append(
            f"{case_name}: expected diagnostic code {diagnostic_code!r}; "
            f"got {[diagnostic.get('code') for diagnostic in diagnostics if isinstance(diagnostic, dict)]!r}"
        )
    return payload


def expect_recovery_diagnostic(
    errors,
    case_name,
    payload,
    code,
    message_substring=None,
):
    diagnostics = payload.get("diagnostics")
    if not isinstance(diagnostics, list):
        errors.append(f"{case_name}: expected diagnostics array")
        return
    for diagnostic in diagnostics:
        if not isinstance(diagnostic, dict) or diagnostic.get("code") != code:
            continue
        if message_substring is not None:
            message = diagnostic.get("message")
            if not isinstance(message, str) or message_substring not in message:
                errors.append(
                    f"{case_name}: expected diagnostic {code!r} message "
                    f"containing {message_substring!r}, got {message!r}"
                )
        return
    errors.append(
        f"{case_name}: expected diagnostic code {code!r}; "
        f"got "
        f"{[diagnostic.get('code') for diagnostic in diagnostics if isinstance(diagnostic, dict)]!r}"
    )


def expect_sidecar_list_json(
    errors,
    root,
    tmp_dir,
    case_name,
    result,
    *,
    queried,
    requested,
    state,
    requested_exists=True,
    sidecar_kind=None,
    sidecar_token=None,
    sidecar_attempt=None,
    expected_sidecars=(),
):
    if result.stderr:
        errors.append(f"{case_name}: expected JSON mode to keep stderr empty")
    errors.extend(validate_sidecar_schema(root, tmp_dir, case_name, result.stdout))
    payload = parse_json_payload(errors, result, case_name)
    if not isinstance(payload, dict):
        errors.append(f"{case_name}: expected sidecar list JSON output to be an object")
        return {}

    expect_equal(errors, case_name, "schemaVersion", payload.get("schemaVersion"), 1)
    expect_equal(
        errors,
        case_name,
        "packagePath",
        payload.get("packagePath"),
        queried.as_posix(),
    )
    expect_equal(
        errors,
        case_name,
        "requestedExists",
        payload.get("requestedExists"),
        requested_exists,
    )
    publication = expect_object(
        errors,
        case_name,
        "publication",
        payload.get("publication"),
    )
    expect_equal(
        errors,
        case_name,
        "publication.state",
        publication.get("state"),
        state,
    )
    expect_equal(
        errors,
        case_name,
        "publication.requestedPath",
        publication.get("requestedPath"),
        requested.as_posix(),
    )
    expect_equal(
        errors,
        case_name,
        "publication.sidecarKind",
        publication.get("sidecarKind"),
        sidecar_kind,
    )
    expect_equal(
        errors,
        case_name,
        "publication.sidecarToken",
        publication.get("sidecarToken"),
        sidecar_token,
    )
    expect_equal(
        errors,
        case_name,
        "publication.sidecarAttempt",
        publication.get("sidecarAttempt"),
        sidecar_attempt,
    )

    sidecars = expect_array(
        errors,
        case_name,
        "publication.siblingSidecars",
        publication.get("siblingSidecars"),
    )
    expect_equal(
        errors,
        case_name,
        "publication.siblingSidecarCount",
        publication.get("siblingSidecarCount"),
        len(expected_sidecars),
    )

    expected_by_path = {entry["path"].as_posix(): entry for entry in expected_sidecars}
    actual_paths = []
    for index, sidecar in enumerate(sidecars):
        sidecar_path = f"publication.siblingSidecars[{index}]"
        if not isinstance(sidecar, dict):
            errors.append(f"{case_name}: expected {sidecar_path} to be an object")
            continue
        path = sidecar.get("path")
        actual_paths.append(path)
        expected = expected_by_path.get(path)
        if expected is None:
            errors.append(f"{case_name}: unexpected sidecar record {path!r}")
            continue
        for field in ("kind", "token", "attempt", "directory"):
            expect_equal(
                errors,
                case_name,
                f"{sidecar_path}.{field}",
                sidecar.get(field),
                expected[field],
            )

    expected_paths = sorted(expected_by_path)
    if actual_paths != expected_paths:
        errors.append(
            f"{case_name}: expected sorted sidecar paths {expected_paths!r}, "
            f"got {actual_paths!r}"
        )
    return payload


def expect_stale_cleanup_json(
    errors,
    root,
    tmp_dir,
    case_name,
    result,
    *,
    queried,
    requested,
    dry_run,
    requested_exists,
    keep_last=None,
    older_than_seconds=None,
    expected_candidates=(),
    expected_retained=(),
    success=True,
):
    if result.stderr:
        errors.append(f"{case_name}: expected JSON mode to keep stderr empty")
    errors.extend(
        validate_stale_cleanup_schema(root, tmp_dir, case_name, result.stdout)
    )
    payload = parse_json_payload(errors, result, case_name)
    if not isinstance(payload, dict):
        errors.append(
            f"{case_name}: expected stale cleanup JSON output to be an object"
        )
        return {}

    expect_equal(errors, case_name, "schemaVersion", payload.get("schemaVersion"), 1)
    expect_equal(
        errors,
        case_name,
        "packagePath",
        payload.get("packagePath"),
        queried.as_posix(),
    )
    expect_equal(errors, case_name, "dryRun", payload.get("dryRun"), dry_run)
    expect_equal(
        errors,
        case_name,
        "requestedExists",
        payload.get("requestedExists"),
        requested_exists,
    )
    expect_equal(errors, case_name, "keepLast", payload.get("keepLast"), keep_last)
    expect_equal(
        errors,
        case_name,
        "olderThanSeconds",
        payload.get("olderThanSeconds"),
        older_than_seconds,
    )
    expect_equal(errors, case_name, "success", payload.get("success"), success)
    publication = expect_object(
        errors,
        case_name,
        "publication",
        payload.get("publication"),
    )
    expect_equal(
        errors,
        case_name,
        "publication.requestedPath",
        publication.get("requestedPath"),
        requested.as_posix(),
    )

    candidates = expect_array(
        errors,
        case_name,
        "candidates",
        payload.get("candidates"),
    )
    expect_equal(
        errors,
        case_name,
        "candidateCount",
        payload.get("candidateCount"),
        len(expected_candidates),
    )
    expect_equal(
        errors,
        case_name,
        "discardedCount",
        payload.get("discardedCount"),
        sum(
            1 for candidate in expected_candidates if candidate["action"] == "discarded"
        ),
    )
    expect_equal(
        errors,
        case_name,
        "failedCount",
        payload.get("failedCount"),
        sum(1 for candidate in expected_candidates if candidate["action"] == "failed"),
    )
    retained = expect_array(
        errors,
        case_name,
        "retained",
        payload.get("retained"),
    )
    expect_equal(
        errors,
        case_name,
        "retainedCount",
        payload.get("retainedCount"),
        len(expected_retained),
    )

    expected_by_path = {
        candidate["path"].as_posix(): candidate for candidate in expected_candidates
    }
    actual_paths = []
    for index, candidate in enumerate(candidates):
        candidate_path = f"candidates[{index}]"
        if not isinstance(candidate, dict):
            errors.append(f"{case_name}: expected {candidate_path} to be an object")
            continue
        path = candidate.get("path")
        actual_paths.append(path)
        expected = expected_by_path.get(path)
        if expected is None:
            errors.append(f"{case_name}: unexpected cleanup candidate {path!r}")
            continue
        for field in (
            "kind",
            "token",
            "attempt",
            "directory",
            "reason",
            "action",
            "success",
        ):
            expect_equal(
                errors,
                case_name,
                f"{candidate_path}.{field}",
                candidate.get(field),
                expected[field],
            )

    expected_paths = sorted(expected_by_path)
    if actual_paths != expected_paths:
        errors.append(
            f"{case_name}: expected sorted cleanup paths {expected_paths!r}, "
            f"got {actual_paths!r}"
        )

    expected_retained_by_path = {
        candidate["path"].as_posix(): candidate for candidate in expected_retained
    }
    actual_retained_paths = []
    for index, candidate in enumerate(retained):
        candidate_path = f"retained[{index}]"
        if not isinstance(candidate, dict):
            errors.append(f"{case_name}: expected {candidate_path} to be an object")
            continue
        path = candidate.get("path")
        actual_retained_paths.append(path)
        expected = expected_retained_by_path.get(path)
        if expected is None:
            errors.append(f"{case_name}: unexpected retained sidecar {path!r}")
            continue
        for field in (
            "kind",
            "token",
            "attempt",
            "directory",
            "reason",
            "retainedBy",
            "action",
            "success",
        ):
            expect_equal(
                errors,
                case_name,
                f"{candidate_path}.{field}",
                candidate.get(field),
                expected[field],
            )

    expected_retained_paths = sorted(expected_retained_by_path)
    if actual_retained_paths != expected_retained_paths:
        errors.append(
            f"{case_name}: expected sorted retained paths "
            f"{expected_retained_paths!r}, got {actual_retained_paths!r}"
        )
    return payload


def expect_maintenance_report_json(
    errors,
    root,
    tmp_dir,
    case_name,
    result,
    *,
    scan_root=None,
    set_path=None,
    dry_run,
    keep_last=None,
    older_than_seconds=None,
    expected_packages=(),
    success=True,
):
    if result.stderr:
        errors.append(f"{case_name}: expected JSON mode to keep stderr empty")
    if set_path is None:
        errors.extend(
            validate_maintenance_report_schema(root, tmp_dir, case_name, result.stdout)
        )
        source_field = "rootPath"
        source_value = scan_root
    else:
        errors.extend(
            validate_maintenance_set_report_schema(
                root,
                tmp_dir,
                case_name,
                result.stdout,
            )
        )
        source_field = "setPath"
        source_value = set_path
    payload = parse_json_payload(errors, result, case_name)
    if not isinstance(payload, dict):
        errors.append(
            f"{case_name}: expected maintenance report JSON output to be an object"
        )
        return {}

    expect_equal(errors, case_name, "schemaVersion", payload.get("schemaVersion"), 1)
    expect_equal(
        errors,
        case_name,
        source_field,
        payload.get(source_field),
        source_value.as_posix(),
    )
    expect_equal(errors, case_name, "dryRun", payload.get("dryRun"), dry_run)
    expect_equal(errors, case_name, "keepLast", payload.get("keepLast"), keep_last)
    expect_equal(
        errors,
        case_name,
        "olderThanSeconds",
        payload.get("olderThanSeconds"),
        older_than_seconds,
    )
    expect_equal(errors, case_name, "success", payload.get("success"), success)
    packages = expect_array(errors, case_name, "packages", payload.get("packages"))
    expect_equal(
        errors,
        case_name,
        "packageCount",
        payload.get("packageCount"),
        len(expected_packages),
    )
    expect_equal(
        errors,
        case_name,
        "candidateCount",
        payload.get("candidateCount"),
        sum(len(package["expected_candidates"]) for package in expected_packages),
    )
    expect_equal(
        errors,
        case_name,
        "retainedCount",
        payload.get("retainedCount"),
        sum(len(package.get("expected_retained", ())) for package in expected_packages),
    )

    expected_by_path = {
        package["package"].as_posix(): package for package in expected_packages
    }
    actual_paths = []
    for package in packages:
        if not isinstance(package, dict):
            errors.append(f"{case_name}: expected packages item to be an object")
            continue
        package_path = package.get("packagePath")
        actual_paths.append(package_path)
        expected = expected_by_path.get(package_path)
        if expected is None:
            errors.append(f"{case_name}: unexpected package result {package_path!r}")
            continue
        expect_equal(
            errors,
            case_name,
            f"packages[{package_path}].publication.requestedPath",
            package.get("publication", {}).get("requestedPath"),
            expected["package"].as_posix(),
        )
        expect_equal(
            errors,
            case_name,
            f"packages[{package_path}].requestedExists",
            package.get("requestedExists"),
            expected["requested_exists"],
        )
        expect_equal(
            errors,
            case_name,
            f"packages[{package_path}].candidateCount",
            package.get("candidateCount"),
            len(expected["expected_candidates"]),
        )
        expect_equal(
            errors,
            case_name,
            f"packages[{package_path}].retainedCount",
            package.get("retainedCount"),
            len(expected.get("expected_retained", ())),
        )
        candidate_paths = [candidate.get("path") for candidate in package["candidates"]]
        expected_candidate_paths = sorted(
            candidate["path"].as_posix()
            for candidate in expected["expected_candidates"]
        )
        if candidate_paths != expected_candidate_paths:
            errors.append(
                f"{case_name}: expected cleanup paths {expected_candidate_paths!r} "
                f"for {package_path}, got {candidate_paths!r}"
            )
        retained_paths = [candidate.get("path") for candidate in package["retained"]]
        expected_retained_paths = sorted(
            candidate["path"].as_posix()
            for candidate in expected.get("expected_retained", ())
        )
        if retained_paths != expected_retained_paths:
            errors.append(
                f"{case_name}: expected retained paths {expected_retained_paths!r} "
                f"for {package_path}, got {retained_paths!r}"
            )

    expected_paths = sorted(expected_by_path)
    if actual_paths != expected_paths:
        errors.append(
            f"{case_name}: expected sorted package paths {expected_paths!r}, "
            f"got {actual_paths!r}"
        )
    return payload


def expect_package_set_document(
    errors,
    root,
    case_name,
    set_path,
    *,
    expected_packages,
    stdout_json=None,
):
    errors.extend(validate_maintenance_set_schema(root, case_name, set_path))
    try:
        payload = json.loads(set_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        errors.append(f"{case_name}: expected package set JSON file: {exc}")
        return {}

    expect_equal(errors, case_name, "schemaVersion", payload.get("schemaVersion"), 1)
    expect_equal(
        errors,
        case_name,
        "packages",
        payload.get("packages"),
        list(expected_packages),
    )
    if stdout_json is not None:
        try:
            stdout_payload = json.loads(stdout_json)
        except json.JSONDecodeError as exc:
            errors.append(f"{case_name}: expected package set JSON stdout: {exc}")
        else:
            expect_equal(
                errors,
                case_name,
                "stdout",
                stdout_payload,
                payload,
            )
    return payload


def expect_package_set_verification_batch_document(
    errors,
    root,
    case_name,
    batch_path,
    *,
    expected_verifications,
    stdout_json=None,
):
    errors.extend(
        validate_maintenance_set_verification_batch_schema(
            root,
            case_name,
            batch_path,
        )
    )
    try:
        payload = json.loads(batch_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        errors.append(
            f"{case_name}: expected package set verification batch JSON file: {exc}"
        )
        return {}

    expected_payload = {
        "schemaVersion": 1,
        "verifications": [
            {
                "rootPath": verification["root_path"],
                "setPath": verification["set_path"],
            }
            for verification in expected_verifications
        ],
    }
    expect_equal(errors, case_name, "document", payload, expected_payload)
    if stdout_json is not None:
        try:
            stdout_payload = json.loads(stdout_json)
        except json.JSONDecodeError as exc:
            errors.append(
                f"{case_name}: expected verification batch JSON stdout: {exc}"
            )
        else:
            expect_equal(
                errors,
                case_name,
                "stdout",
                stdout_payload,
                payload,
            )
    return payload


def package_path_strings(paths):
    return [path.as_posix() if isinstance(path, Path) else str(path) for path in paths]


def release_output_relative_path(path, output_path):
    return Path(
        os.path.relpath(
            os.path.abspath(path),
            os.path.abspath(output_path.parent),
        )
    ).as_posix()


def expect_package_set_verification_payload(
    errors,
    case_name,
    payload,
    *,
    scan_root,
    set_path,
    success,
    matches,
    scanned_packages,
    set_packages,
    missing_from_set=(),
    extra_in_set=(),
    diagnostic_code=None,
):
    if not isinstance(payload, dict):
        errors.append(
            f"{case_name}: expected package set verification JSON output "
            "to be an object"
        )
        return {}

    expected_scanned = package_path_strings(scanned_packages)
    expected_set = package_path_strings(set_packages)
    expected_missing = package_path_strings(missing_from_set)
    expected_extra = package_path_strings(extra_in_set)
    expect_equal(errors, case_name, "schemaVersion", payload.get("schemaVersion"), 1)
    expect_equal(
        errors,
        case_name,
        "rootPath",
        payload.get("rootPath"),
        scan_root.as_posix(),
    )
    expect_equal(
        errors,
        case_name,
        "setPath",
        payload.get("setPath"),
        set_path.as_posix(),
    )
    expect_equal(errors, case_name, "success", payload.get("success"), success)
    expect_equal(errors, case_name, "matches", payload.get("matches"), matches)
    expect_equal(
        errors,
        case_name,
        "scannedPackageCount",
        payload.get("scannedPackageCount"),
        len(expected_scanned),
    )
    expect_equal(
        errors,
        case_name,
        "setPackageCount",
        payload.get("setPackageCount"),
        len(expected_set),
    )
    expect_equal(
        errors,
        case_name,
        "missingFromSetCount",
        payload.get("missingFromSetCount"),
        len(expected_missing),
    )
    expect_equal(
        errors,
        case_name,
        "extraInSetCount",
        payload.get("extraInSetCount"),
        len(expected_extra),
    )
    expect_equal(
        errors,
        case_name,
        "scannedPackages",
        payload.get("scannedPackages"),
        expected_scanned,
    )
    expect_equal(
        errors,
        case_name,
        "setPackages",
        payload.get("setPackages"),
        expected_set,
    )
    expect_equal(
        errors,
        case_name,
        "missingFromSet",
        payload.get("missingFromSet"),
        expected_missing,
    )
    expect_equal(
        errors,
        case_name,
        "extraInSet",
        payload.get("extraInSet"),
        expected_extra,
    )

    diagnostic_counts = expect_object(
        errors,
        case_name,
        "diagnosticCounts",
        payload.get("diagnosticCounts"),
    )
    diagnostics = expect_array(
        errors,
        case_name,
        "diagnostics",
        payload.get("diagnostics"),
    )
    actual_counts = {severity: 0 for severity in SEVERITIES}
    diagnostic_codes = []
    for diagnostic in diagnostics:
        if not isinstance(diagnostic, dict):
            continue
        severity = diagnostic.get("severity")
        if severity in actual_counts:
            actual_counts[severity] += 1
        diagnostic_codes.append(diagnostic.get("code"))
    for severity, count in actual_counts.items():
        expect_equal(
            errors,
            case_name,
            f"diagnosticCounts.{severity}",
            diagnostic_counts.get(severity),
            count,
        )
    if diagnostic_code is not None and diagnostic_code not in diagnostic_codes:
        errors.append(
            f"{case_name}: expected diagnostic code {diagnostic_code!r}, "
            f"got {diagnostic_codes!r}"
        )
    return payload


def expect_package_set_verification_json(
    errors,
    root,
    tmp_dir,
    case_name,
    result,
    *,
    scan_root,
    set_path,
    success,
    matches,
    scanned_packages,
    set_packages,
    missing_from_set=(),
    extra_in_set=(),
    diagnostic_code=None,
):
    if result.stderr:
        errors.append(f"{case_name}: expected JSON mode to keep stderr empty")
    errors.extend(
        validate_maintenance_set_verification_schema(
            root,
            tmp_dir,
            case_name,
            result.stdout,
        )
    )
    payload = parse_json_payload(errors, result, case_name)
    return expect_package_set_verification_payload(
        errors,
        case_name,
        payload,
        scan_root=scan_root,
        set_path=set_path,
        success=success,
        matches=matches,
        scanned_packages=scanned_packages,
        set_packages=set_packages,
        missing_from_set=missing_from_set,
        extra_in_set=extra_in_set,
        diagnostic_code=diagnostic_code,
    )


def expect_package_set_verification_batch_json(
    errors,
    root,
    tmp_dir,
    case_name,
    result,
    *,
    batch_path,
    success,
    matches,
    expected_verifications,
    diagnostic_code=None,
):
    if result.stderr:
        errors.append(f"{case_name}: expected JSON mode to keep stderr empty")
    errors.extend(
        validate_maintenance_set_verification_batch_report_schema(
            root,
            tmp_dir,
            case_name,
            result.stdout,
        )
    )
    payload = parse_json_payload(errors, result, case_name)
    if not isinstance(payload, dict):
        errors.append(
            f"{case_name}: expected package set verification batch JSON "
            "output to be an object"
        )
        return {}

    matched_count = sum(
        1 for verification in expected_verifications if verification["matches"]
    )
    mismatched_count = sum(
        1
        for verification in expected_verifications
        if verification.get("missing_from_set") or verification.get("extra_in_set")
    )
    failed_count = sum(
        1
        for verification in expected_verifications
        if not verification["success"]
        and not (
            verification.get("missing_from_set") or verification.get("extra_in_set")
        )
    )
    expect_equal(errors, case_name, "schemaVersion", payload.get("schemaVersion"), 1)
    expect_equal(
        errors,
        case_name,
        "batchPath",
        payload.get("batchPath"),
        batch_path.as_posix(),
    )
    expect_equal(errors, case_name, "success", payload.get("success"), success)
    expect_equal(errors, case_name, "matches", payload.get("matches"), matches)
    expect_equal(
        errors,
        case_name,
        "verificationCount",
        payload.get("verificationCount"),
        len(expected_verifications),
    )
    expect_equal(
        errors,
        case_name,
        "matchedCount",
        payload.get("matchedCount"),
        matched_count,
    )
    expect_equal(
        errors,
        case_name,
        "mismatchedCount",
        payload.get("mismatchedCount"),
        mismatched_count,
    )
    expect_equal(
        errors,
        case_name,
        "failedCount",
        payload.get("failedCount"),
        failed_count,
    )

    verifications = expect_array(
        errors,
        case_name,
        "verifications",
        payload.get("verifications"),
    )
    expect_equal(
        errors,
        case_name,
        "verifications length",
        len(verifications),
        len(expected_verifications),
    )
    for index, (verification, expected) in enumerate(
        zip(verifications, expected_verifications)
    ):
        expect_package_set_verification_payload(
            errors,
            f"{case_name}.verifications[{index}]",
            verification,
            **expected,
        )

    diagnostic_counts = expect_object(
        errors,
        case_name,
        "diagnosticCounts",
        payload.get("diagnosticCounts"),
    )
    diagnostics = expect_array(
        errors,
        case_name,
        "diagnostics",
        payload.get("diagnostics"),
    )
    actual_counts = {severity: 0 for severity in SEVERITIES}
    diagnostic_codes = []
    for diagnostic in diagnostics:
        if not isinstance(diagnostic, dict):
            continue
        severity = diagnostic.get("severity")
        if severity in actual_counts:
            actual_counts[severity] += 1
        diagnostic_codes.append(diagnostic.get("code"))
    for severity, count in actual_counts.items():
        expect_equal(
            errors,
            case_name,
            f"diagnosticCounts.{severity}",
            diagnostic_counts.get(severity),
            count,
        )
    if diagnostic_code is not None and diagnostic_code not in diagnostic_codes:
        errors.append(
            f"{case_name}: expected diagnostic code {diagnostic_code!r}, "
            f"got {diagnostic_codes!r}"
        )
    return payload


def expect_diagnostic_code_counts(
    errors,
    case_name,
    path,
    entries,
    expected_codes=(),
):
    codes = [entry.get("code") for entry in entries if isinstance(entry, dict)]
    if codes != sorted(codes):
        errors.append(f"{case_name}: expected sorted {path} diagnostic codes")
    for code in expected_codes:
        if code not in codes:
            errors.append(
                f"{case_name}: expected {path} diagnostic code {code!r}, got {codes!r}"
            )


def expect_package_set_verification_batch_summary_file(
    errors,
    root,
    case_name,
    summary_path,
    *,
    batch_path,
    success,
    matches,
    expected_verifications,
    diagnostic_code=None,
):
    errors.extend(
        validate_maintenance_set_verification_batch_summary_schema(
            root,
            case_name,
            summary_path,
        )
    )
    try:
        payload = json.loads(summary_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        errors.append(
            f"{case_name}: expected package set verification batch summary "
            f"JSON file: {exc}"
        )
        return {}

    matched_count = sum(
        1 for verification in expected_verifications if verification["matches"]
    )
    mismatched_count = sum(
        1
        for verification in expected_verifications
        if verification.get("missing_from_set") or verification.get("extra_in_set")
    )
    failed_count = sum(
        1
        for verification in expected_verifications
        if not verification["success"]
        and not (
            verification.get("missing_from_set") or verification.get("extra_in_set")
        )
    )
    expect_equal(errors, case_name, "schemaVersion", payload.get("schemaVersion"), 1)
    expect_equal(
        errors,
        case_name,
        "batchPath",
        payload.get("batchPath"),
        batch_path.as_posix(),
    )
    expect_equal(errors, case_name, "success", payload.get("success"), success)
    expect_equal(errors, case_name, "matches", payload.get("matches"), matches)
    expect_equal(
        errors,
        case_name,
        "releaseEligible",
        payload.get("releaseEligible"),
        success and matches,
    )
    expect_equal(
        errors,
        case_name,
        "verificationCount",
        payload.get("verificationCount"),
        len(expected_verifications),
    )
    expect_equal(
        errors,
        case_name,
        "matchedCount",
        payload.get("matchedCount"),
        matched_count,
    )
    expect_equal(
        errors,
        case_name,
        "mismatchedCount",
        payload.get("mismatchedCount"),
        mismatched_count,
    )
    expect_equal(
        errors,
        case_name,
        "failedCount",
        payload.get("failedCount"),
        failed_count,
    )
    expect_equal(
        errors,
        case_name,
        "scannedPackageCount",
        payload.get("scannedPackageCount"),
        sum(
            len(verification["scanned_packages"])
            for verification in expected_verifications
        ),
    )
    expect_equal(
        errors,
        case_name,
        "setPackageCount",
        payload.get("setPackageCount"),
        sum(
            len(verification["set_packages"]) for verification in expected_verifications
        ),
    )
    expect_equal(
        errors,
        case_name,
        "missingFromSetCount",
        payload.get("missingFromSetCount"),
        sum(
            len(verification.get("missing_from_set", ()))
            for verification in expected_verifications
        ),
    )
    expect_equal(
        errors,
        case_name,
        "extraInSetCount",
        payload.get("extraInSetCount"),
        sum(
            len(verification.get("extra_in_set", ()))
            for verification in expected_verifications
        ),
    )

    verifications = expect_array(
        errors,
        case_name,
        "verifications",
        payload.get("verifications"),
    )
    expect_equal(
        errors,
        case_name,
        "verifications length",
        len(verifications),
        len(expected_verifications),
    )
    for index, (verification, expected) in enumerate(
        zip(verifications, expected_verifications)
    ):
        expected_missing = package_path_strings(expected.get("missing_from_set", ()))
        expected_extra = package_path_strings(expected.get("extra_in_set", ()))
        expect_equal(
            errors,
            case_name,
            f"verifications[{index}].rootPath",
            verification.get("rootPath"),
            expected["scan_root"].as_posix(),
        )
        expect_equal(
            errors,
            case_name,
            f"verifications[{index}].setPath",
            verification.get("setPath"),
            expected["set_path"].as_posix(),
        )
        expect_equal(
            errors,
            case_name,
            f"verifications[{index}].success",
            verification.get("success"),
            expected["success"],
        )
        expect_equal(
            errors,
            case_name,
            f"verifications[{index}].matches",
            verification.get("matches"),
            expected["matches"],
        )
        expect_equal(
            errors,
            case_name,
            f"verifications[{index}].missingFromSet",
            verification.get("missingFromSet"),
            expected_missing,
        )
        expect_equal(
            errors,
            case_name,
            f"verifications[{index}].extraInSet",
            verification.get("extraInSet"),
            expected_extra,
        )
        expected_code = expected.get("diagnostic_code")
        if expected_code is not None:
            expect_diagnostic_code_counts(
                errors,
                case_name,
                f"verifications[{index}].diagnosticCodeCounts",
                expect_array(
                    errors,
                    case_name,
                    f"verifications[{index}].diagnosticCodeCounts",
                    verification.get("diagnosticCodeCounts"),
                ),
                expected_codes=(expected_code,),
            )

    aggregate_codes = expect_array(
        errors,
        case_name,
        "diagnosticCodeCounts",
        payload.get("diagnosticCodeCounts"),
    )
    expected_codes = (diagnostic_code,) if diagnostic_code is not None else ()
    expect_diagnostic_code_counts(
        errors,
        case_name,
        "diagnosticCodeCounts",
        aggregate_codes,
        expected_codes=expected_codes,
    )
    return payload


def expect_release_promotion_manifest_file(
    errors,
    root,
    case_name,
    manifest_path,
    *,
    summary_path,
    batch_path,
    release_eligible,
    stdout_json=None,
    expected_blocker_codes=(),
    expected_package_paths=None,
):
    errors.extend(
        validate_release_promotion_manifest_schema(root, case_name, manifest_path)
    )
    try:
        payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        errors.append(
            f"{case_name}: expected package release promotion manifest JSON file: {exc}"
        )
        return {}

    if stdout_json is not None:
        try:
            stdout_payload = json.loads(stdout_json)
        except json.JSONDecodeError as exc:
            errors.append(f"{case_name}: expected JSON stdout: {exc}")
        else:
            expect_equal(
                errors,
                case_name,
                "stdout manifest",
                stdout_payload,
                payload,
            )

    expect_equal(errors, case_name, "schemaVersion", payload.get("schemaVersion"), 1)
    expect_equal(
        errors,
        case_name,
        "summaryPath",
        payload.get("summaryPath"),
        release_output_relative_path(summary_path, manifest_path),
    )
    expect_equal(
        errors,
        case_name,
        "manifestPath",
        payload.get("manifestPath"),
        release_output_relative_path(manifest_path, manifest_path),
    )
    expect_equal(
        errors,
        case_name,
        "batchPath",
        payload.get("batchPath"),
        release_output_relative_path(batch_path, manifest_path),
    )
    expect_equal(
        errors,
        case_name,
        "status",
        payload.get("status"),
        "eligible" if release_eligible else "blocked",
    )
    expect_equal(
        errors,
        case_name,
        "releaseEligible",
        payload.get("releaseEligible"),
        release_eligible,
    )

    summary = expect_object(errors, case_name, "summary", payload.get("summary"))
    expect_equal(
        errors,
        case_name,
        "summary.summaryPath",
        summary.get("summaryPath"),
        release_output_relative_path(summary_path, manifest_path),
    )
    expect_equal(
        errors,
        case_name,
        "summary.batchPath",
        summary.get("batchPath"),
        release_output_relative_path(batch_path, manifest_path),
    )
    blockers = expect_array(errors, case_name, "blockers", payload.get("blockers"))
    expect_equal(
        errors,
        case_name,
        "blockerCount",
        payload.get("blockerCount"),
        len(blockers),
    )
    blocker_codes = [
        blocker.get("code") for blocker in blockers if isinstance(blocker, dict)
    ]
    if blocker_codes != sorted(blocker_codes):
        errors.append(f"{case_name}: expected sorted blocker codes")
    expect_equal(
        errors,
        case_name,
        "blocker codes",
        blocker_codes,
        list(expected_blocker_codes),
    )
    packages = expect_array(errors, case_name, "packages", payload.get("packages"))
    expect_equal(
        errors,
        case_name,
        "packageCount",
        payload.get("packageCount"),
        len(packages),
    )
    package_paths = [
        package.get("packagePath") for package in packages if isinstance(package, dict)
    ]
    if package_paths != sorted(package_paths):
        errors.append(f"{case_name}: expected sorted package paths")
    if expected_package_paths is not None:
        expect_equal(
            errors,
            case_name,
            "package paths",
            package_paths,
            [package.as_posix() for package in expected_package_paths],
        )
    for package in packages:
        if not isinstance(package, dict):
            errors.append(f"{case_name}: expected package item to be an object")
            continue
        package_path_value = package.get("packagePath")
        if not isinstance(package_path_value, str):
            errors.append(f"{case_name}: expected packagePath string")
            continue
        package_path_object = Path(package_path_value)
        expect_equal(
            errors, case_name, "package.module", package.get("module"), MODULE_NAME
        )
        source_hash = expect_object(
            errors,
            case_name,
            "package.sourceHash",
            package.get("sourceHash"),
        )
        expect_equal(
            errors,
            case_name,
            "package.sourceHash.algorithm",
            source_hash.get("algorithm"),
            "sha256",
        )
        source_hash_value = source_hash.get("value")
        if not isinstance(source_hash_value, str) or len(source_hash_value) != 64:
            errors.append(f"{case_name}: expected 64-character source hash")
        artifacts = expect_array(
            errors,
            case_name,
            "package.artifacts",
            package.get("artifacts"),
        )
        expect_equal(
            errors,
            case_name,
            "package.artifactCount",
            package.get("artifactCount"),
            len(artifacts),
        )
        artifact_names = [
            artifact.get("name") for artifact in artifacts if isinstance(artifact, dict)
        ]
        if artifact_names != sorted(artifact_names):
            errors.append(f"{case_name}: expected sorted artifact names")
        for artifact in artifacts:
            if not isinstance(artifact, dict):
                errors.append(f"{case_name}: expected artifact item to be an object")
                continue
            artifact_path_value = artifact.get("path")
            if not isinstance(artifact_path_value, str):
                errors.append(f"{case_name}: expected artifact path string")
                continue
            artifact_path = package_path_object / Path(artifact_path_value)
            exists = artifact_path.is_file()
            expect_equal(
                errors,
                case_name,
                f"artifact {artifact.get('name')}.exists",
                artifact.get("exists"),
                exists,
            )
            if exists:
                expect_equal(
                    errors,
                    case_name,
                    f"artifact {artifact.get('name')}.sizeBytes",
                    artifact.get("sizeBytes"),
                    artifact_path.stat().st_size,
                )
                expect_equal(
                    errors,
                    case_name,
                    f"artifact {artifact.get('name')}.sha256",
                    artifact.get("sha256"),
                    file_sha256(artifact_path),
                )
            else:
                expect_equal(
                    errors,
                    case_name,
                    f"artifact {artifact.get('name')}.sizeBytes",
                    artifact.get("sizeBytes"),
                    None,
                )
                expect_equal(
                    errors,
                    case_name,
                    f"artifact {artifact.get('name')}.sha256",
                    artifact.get("sha256"),
                    None,
                )
    return payload


def expect_release_bundle_file(
    errors,
    root,
    case_name,
    bundle_path,
    *,
    promotion_manifest_path,
    summary_path,
    batch_path,
    release_eligible,
    expected_blocker_codes=(),
    expected_package_paths=None,
):
    errors.extend(validate_release_bundle_schema(root, case_name, bundle_path))
    try:
        payload = json.loads(bundle_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        errors.append(f"{case_name}: expected package release bundle JSON file: {exc}")
        return {}

    expect_equal(errors, case_name, "schemaVersion", payload.get("schemaVersion"), 1)
    expect_equal(
        errors,
        case_name,
        "bundlePath",
        payload.get("bundlePath"),
        bundle_path.as_posix(),
    )
    expect_equal(
        errors,
        case_name,
        "promotionManifestPath",
        payload.get("promotionManifestPath"),
        promotion_manifest_path.as_posix(),
    )
    expect_equal(
        errors,
        case_name,
        "summaryPath",
        payload.get("summaryPath"),
        summary_path.as_posix(),
    )
    expect_equal(
        errors,
        case_name,
        "batchPath",
        payload.get("batchPath"),
        batch_path.as_posix(),
    )
    expect_equal(
        errors,
        case_name,
        "status",
        payload.get("status"),
        "eligible" if release_eligible else "blocked",
    )
    expect_equal(
        errors,
        case_name,
        "releaseEligible",
        payload.get("releaseEligible"),
        release_eligible,
    )

    blockers = expect_array(errors, case_name, "blockers", payload.get("blockers"))
    expect_equal(
        errors,
        case_name,
        "blockerCount",
        payload.get("blockerCount"),
        len(blockers),
    )
    blocker_codes = [
        blocker.get("code") for blocker in blockers if isinstance(blocker, dict)
    ]
    if blocker_codes != sorted(blocker_codes):
        errors.append(f"{case_name}: expected sorted blocker codes")
    expect_equal(
        errors,
        case_name,
        "blocker codes",
        blocker_codes,
        list(expected_blocker_codes),
    )

    packages = expect_array(errors, case_name, "packages", payload.get("packages"))
    expect_equal(
        errors,
        case_name,
        "packageCount",
        payload.get("packageCount"),
        len(packages),
    )
    package_paths = [
        package.get("packagePath") for package in packages if isinstance(package, dict)
    ]
    if package_paths != sorted(package_paths):
        errors.append(f"{case_name}: expected sorted package paths")
    if expected_package_paths is not None:
        expect_equal(
            errors,
            case_name,
            "package paths",
            package_paths,
            [package.as_posix() for package in expected_package_paths],
        )

    aggregate_artifact_count = 0
    aggregate_existing_artifact_count = 0
    aggregate_missing_artifact_count = 0
    aggregate_total_artifact_bytes = 0
    for package in packages:
        if not isinstance(package, dict):
            errors.append(f"{case_name}: expected package item to be an object")
            continue
        package_path_value = package.get("packagePath")
        if not isinstance(package_path_value, str):
            errors.append(f"{case_name}: expected packagePath string")
            continue
        package_path_object = Path(package_path_value)
        expect_equal(
            errors, case_name, "package.module", package.get("module"), MODULE_NAME
        )
        source_hash = expect_object(
            errors,
            case_name,
            "package.sourceHash",
            package.get("sourceHash"),
        )
        expect_equal(
            errors,
            case_name,
            "package.sourceHash.algorithm",
            source_hash.get("algorithm"),
            "sha256",
        )
        source_hash_value = source_hash.get("value")
        if not isinstance(source_hash_value, str) or len(source_hash_value) != 64:
            errors.append(f"{case_name}: expected 64-character source hash")
        artifacts = expect_array(
            errors,
            case_name,
            "package.artifacts",
            package.get("artifacts"),
        )
        requirements = expect_object(
            errors,
            case_name,
            "package.packageArtifactRequirements",
            package.get("packageArtifactRequirements"),
        )
        expect_equal(
            errors,
            case_name,
            "package.packageArtifactRequirements.target",
            requirements.get("target"),
            package.get("target"),
        )
        existing_count = 0
        missing_count = 0
        package_bytes = 0
        artifact_names = [
            artifact.get("name") for artifact in artifacts if isinstance(artifact, dict)
        ]
        if artifact_names != sorted(artifact_names):
            errors.append(f"{case_name}: expected sorted artifact names")
        for artifact in artifacts:
            if not isinstance(artifact, dict):
                errors.append(f"{case_name}: expected artifact item to be an object")
                continue
            artifact_path_value = artifact.get("path")
            if not isinstance(artifact_path_value, str):
                errors.append(f"{case_name}: expected artifact path string")
                continue
            artifact_path = package_path_object / Path(artifact_path_value)
            exists = artifact_path.is_file()
            expect_equal(
                errors,
                case_name,
                f"artifact {artifact.get('name')}.exists",
                artifact.get("exists"),
                exists,
            )
            if exists:
                existing_count += 1
                artifact_size = artifact_path.stat().st_size
                package_bytes += artifact_size
                expect_equal(
                    errors,
                    case_name,
                    f"artifact {artifact.get('name')}.sizeBytes",
                    artifact.get("sizeBytes"),
                    artifact_size,
                )
                expect_equal(
                    errors,
                    case_name,
                    f"artifact {artifact.get('name')}.sha256",
                    artifact.get("sha256"),
                    file_sha256(artifact_path),
                )
            else:
                missing_count += 1
                expect_equal(
                    errors,
                    case_name,
                    f"artifact {artifact.get('name')}.sizeBytes",
                    artifact.get("sizeBytes"),
                    None,
                )
                expect_equal(
                    errors,
                    case_name,
                    f"artifact {artifact.get('name')}.sha256",
                    artifact.get("sha256"),
                    None,
                )
        artifacts_by_name = {
            artifact.get("name"): artifact
            for artifact in artifacts
            if isinstance(artifact, dict)
        }
        for required_name in requirements.get("requiredPathArtifacts", []):
            artifact = artifacts_by_name.get(required_name)
            if artifact is None:
                errors.append(
                    f"{case_name}: expected required release artifact {required_name!r}"
                )
            elif not artifact.get("exists") and not (
                required_name == "nativeBinary"
                and requirements.get("allowsPlannedNativeBinary")
                and package.get("nativeBinaryStatus") == "planned"
            ):
                errors.append(
                    f"{case_name}: expected required release artifact "
                    f"{required_name!r} to exist"
                )
        expect_equal(
            errors,
            case_name,
            "package.artifactCount",
            package.get("artifactCount"),
            len(artifacts),
        )
        expect_equal(
            errors,
            case_name,
            "package.existingArtifactCount",
            package.get("existingArtifactCount"),
            existing_count,
        )
        expect_equal(
            errors,
            case_name,
            "package.missingArtifactCount",
            package.get("missingArtifactCount"),
            missing_count,
        )
        expect_equal(
            errors,
            case_name,
            "package.totalArtifactBytes",
            package.get("totalArtifactBytes"),
            package_bytes,
        )
        aggregate_artifact_count += len(artifacts)
        aggregate_existing_artifact_count += existing_count
        aggregate_missing_artifact_count += missing_count
        aggregate_total_artifact_bytes += package_bytes

    expect_equal(
        errors,
        case_name,
        "artifactCount",
        payload.get("artifactCount"),
        aggregate_artifact_count,
    )
    expect_equal(
        errors,
        case_name,
        "existingArtifactCount",
        payload.get("existingArtifactCount"),
        aggregate_existing_artifact_count,
    )
    expect_equal(
        errors,
        case_name,
        "missingArtifactCount",
        payload.get("missingArtifactCount"),
        aggregate_missing_artifact_count,
    )
    expect_equal(
        errors,
        case_name,
        "totalArtifactBytes",
        payload.get("totalArtifactBytes"),
        aggregate_total_artifact_bytes,
    )
    return payload


def expect_release_bundle_verification_json(
    errors,
    root,
    tmp_dir,
    case_name,
    result,
    *,
    bundle_path,
    success,
    release_eligible,
    status,
    expected_bundle_payload=None,
    diagnostic_code=None,
):
    if result.stderr:
        errors.append(f"{case_name}: expected JSON mode to keep stderr empty")
    errors.extend(
        validate_release_bundle_verification_schema(
            root,
            tmp_dir,
            case_name,
            result.stdout,
        )
    )
    payload = parse_json_payload(errors, result, case_name)
    if not isinstance(payload, dict):
        errors.append(f"{case_name}: expected release bundle verification JSON object")
        return {}

    expect_equal(errors, case_name, "schemaVersion", payload.get("schemaVersion"), 1)
    expect_release_bundle_verification_bundle_path(
        errors,
        case_name,
        payload.get("bundlePath"),
        bundle_path,
    )
    expect_equal(errors, case_name, "success", payload.get("success"), success)
    expect_equal(
        errors,
        case_name,
        "releaseEligible",
        payload.get("releaseEligible"),
        release_eligible,
    )
    expect_equal(errors, case_name, "status", payload.get("status"), status)

    if expected_bundle_payload is not None:
        for key in (
            "blockerCount",
            "packageCount",
            "artifactCount",
            "existingArtifactCount",
            "missingArtifactCount",
            "totalArtifactBytes",
        ):
            expect_equal(
                errors,
                case_name,
                key,
                payload.get(key),
                expected_bundle_payload.get(key),
            )
        expected_verified = (
            expected_bundle_payload.get("existingArtifactCount")
            if success
            else payload.get("verifiedArtifactCount")
        )
        expect_equal(
            errors,
            case_name,
            "verifiedArtifactCount",
            payload.get("verifiedArtifactCount"),
            expected_verified,
        )

    diagnostic_counts = expect_object(
        errors,
        case_name,
        "diagnosticCounts",
        payload.get("diagnosticCounts"),
    )
    diagnostics = expect_array(
        errors,
        case_name,
        "diagnostics",
        payload.get("diagnostics"),
    )
    actual_counts = {severity: 0 for severity in SEVERITIES}
    diagnostic_codes = []
    for diagnostic in diagnostics:
        if not isinstance(diagnostic, dict):
            continue
        severity = diagnostic.get("severity")
        if severity in actual_counts:
            actual_counts[severity] += 1
        diagnostic_codes.append(diagnostic.get("code"))
    for severity, count in actual_counts.items():
        expect_equal(
            errors,
            case_name,
            f"diagnosticCounts.{severity}",
            diagnostic_counts.get(severity),
            count,
        )
    if diagnostic_code is not None and diagnostic_code not in diagnostic_codes:
        errors.append(
            f"{case_name}: expected diagnostic code {diagnostic_code!r}, "
            f"got {diagnostic_codes!r}"
        )
    if diagnostic_code is None and diagnostic_codes:
        errors.append(f"{case_name}: expected no diagnostics, got {diagnostic_codes!r}")
    return payload


def expect_release_publish_plan_file(
    errors,
    root,
    case_name,
    plan_path,
    *,
    bundle_path,
    expected_bundle_payload,
    stdout_json=None,
):
    errors.extend(validate_release_publish_plan_schema(root, case_name, plan_path))
    try:
        payload = json.loads(plan_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        errors.append(f"{case_name}: expected package release publish plan JSON: {exc}")
        return {}
    if stdout_json is not None:
        try:
            stdout_payload = json.loads(stdout_json)
        except json.JSONDecodeError as exc:
            errors.append(f"{case_name}: expected publish plan JSON stdout: {exc}")
        else:
            expect_equal(
                errors,
                case_name,
                "stdout publish plan",
                stdout_payload,
                payload,
            )

    expect_equal(errors, case_name, "schemaVersion", payload.get("schemaVersion"), 1)
    expect_equal(
        errors,
        case_name,
        "bundlePath",
        payload.get("bundlePath"),
        bundle_path.as_posix(),
    )
    expect_equal(
        errors,
        case_name,
        "planPath",
        payload.get("planPath"),
        plan_path.as_posix(),
    )
    expect_equal(
        errors, case_name, "releaseEligible", payload.get("releaseEligible"), True
    )

    packages = expect_array(errors, case_name, "packages", payload.get("packages"))
    artifacts = expect_array(errors, case_name, "artifacts", payload.get("artifacts"))
    expect_equal(
        errors,
        case_name,
        "packageCount",
        payload.get("packageCount"),
        len(packages),
    )
    expect_equal(
        errors,
        case_name,
        "artifactCount",
        payload.get("artifactCount"),
        len(artifacts),
    )
    expect_equal(
        errors,
        case_name,
        "artifactCount",
        payload.get("artifactCount"),
        expected_bundle_payload.get("existingArtifactCount"),
    )

    package_paths = [
        package.get("packagePath") for package in packages if isinstance(package, dict)
    ]
    if package_paths != sorted(package_paths):
        errors.append(f"{case_name}: expected sorted publish plan package paths")

    destination_paths = [
        artifact.get("destinationPath")
        for artifact in artifacts
        if isinstance(artifact, dict)
    ]
    if destination_paths != sorted(destination_paths):
        errors.append(f"{case_name}: expected sorted publish plan destinations")
    if len(destination_paths) != len(set(destination_paths)):
        errors.append(f"{case_name}: expected unique publish plan destinations")

    flattened_by_destination = {
        artifact.get("destinationPath"): artifact
        for artifact in artifacts
        if isinstance(artifact, dict)
    }
    total_bytes = 0
    expected_existing_artifacts = {}
    expected_requirements_by_package = {}
    for bundle_package in expected_bundle_payload.get("packages", []):
        package_path = Path(bundle_package.get("packagePath", ""))
        expected_requirements_by_package[package_path.as_posix()] = bundle_package.get(
            "packageArtifactRequirements"
        )
        for artifact in bundle_package.get("artifacts", []):
            if not artifact.get("exists"):
                continue
            source_path = (package_path / artifact.get("path", "")).as_posix()
            expected_existing_artifacts[source_path] = artifact

    planned_source_paths = []
    for package in packages:
        if not isinstance(package, dict):
            errors.append(f"{case_name}: expected publish plan package object")
            continue
        package_artifacts = expect_array(
            errors,
            case_name,
            "package.artifacts",
            package.get("artifacts"),
        )
        expect_equal(
            errors,
            case_name,
            "package.packageArtifactRequirements",
            package.get("packageArtifactRequirements"),
            expected_requirements_by_package.get(package.get("packagePath")),
        )
        package_bytes = 0
        for artifact in package_artifacts:
            if not isinstance(artifact, dict):
                errors.append(f"{case_name}: expected publish plan artifact object")
                continue
            destination = artifact.get("destinationPath")
            if flattened_by_destination.get(destination) != artifact:
                errors.append(
                    f"{case_name}: expected package artifact to match flattened "
                    f"record for {destination!r}"
                )
            for field in ("packagePath", "module", "target"):
                expect_equal(
                    errors,
                    case_name,
                    f"artifact.{field}",
                    artifact.get(field),
                    package.get(field),
                )
            source_path = artifact.get("sourcePath")
            expected_artifact = expected_existing_artifacts.get(source_path)
            if expected_artifact is None:
                errors.append(
                    f"{case_name}: unexpected publish plan artifact source "
                    f"{source_path!r}"
                )
                continue
            expect_equal(
                errors,
                case_name,
                "artifact.packageArtifactPath",
                artifact.get("packageArtifactPath"),
                expected_artifact.get("path"),
            )
            expect_equal(
                errors,
                case_name,
                "artifact.sizeBytes",
                artifact.get("sizeBytes"),
                expected_artifact.get("sizeBytes"),
            )
            expect_equal(
                errors,
                case_name,
                "artifact.sha256",
                artifact.get("sha256"),
                expected_artifact.get("sha256"),
            )
            package_bytes += artifact.get("sizeBytes", 0)
            planned_source_paths.append(source_path)
        expect_equal(
            errors,
            case_name,
            "package.artifactCount",
            package.get("artifactCount"),
            len(package_artifacts),
        )
        expect_equal(
            errors,
            case_name,
            "package.totalArtifactBytes",
            package.get("totalArtifactBytes"),
            package_bytes,
        )
        total_bytes += package_bytes

    expect_equal(
        errors,
        case_name,
        "planned source paths",
        sorted(planned_source_paths),
        sorted(expected_existing_artifacts.keys()),
    )
    expect_equal(
        errors,
        case_name,
        "totalArtifactBytes",
        payload.get("totalArtifactBytes"),
        total_bytes,
    )
    expect_equal(
        errors,
        case_name,
        "totalArtifactBytes",
        payload.get("totalArtifactBytes"),
        expected_bundle_payload.get("totalArtifactBytes"),
    )
    return payload


def expect_release_publish_stage_json(
    errors,
    root,
    tmp_dir,
    case_name,
    result,
    *,
    plan_path,
    stage_path,
    expected_stage_path_json=None,
    expected_plan_payload=None,
    success,
    diagnostic_code=None,
):
    if result.stderr:
        errors.append(f"{case_name}: expected JSON mode to keep stderr empty")
    errors.extend(
        validate_release_publish_stage_schema(
            root,
            tmp_dir,
            case_name,
            result.stdout,
        )
    )
    payload = parse_json_payload(errors, result, case_name)
    if not isinstance(payload, dict):
        errors.append(f"{case_name}: expected release publish stage JSON object")
        return {}

    expect_equal(errors, case_name, "schemaVersion", payload.get("schemaVersion"), 1)
    expect_equal(
        errors,
        case_name,
        "planPath",
        payload.get("planPath"),
        plan_path.as_posix(),
    )
    expect_equal(
        errors,
        case_name,
        "stagePath",
        payload.get("stagePath"),
        expected_stage_path_json
        if expected_stage_path_json is not None
        else stage_path.as_posix(),
    )
    expect_equal(errors, case_name, "success", payload.get("success"), success)

    artifacts = expect_array(errors, case_name, "artifacts", payload.get("artifacts"))
    expect_equal(
        errors,
        case_name,
        "artifactCount",
        payload.get("artifactCount"),
        len(artifacts),
    )
    destination_paths = [
        artifact.get("destinationPath")
        for artifact in artifacts
        if isinstance(artifact, dict)
    ]
    if destination_paths != sorted(destination_paths):
        errors.append(f"{case_name}: expected sorted stage destinations")
    if len(destination_paths) != len(set(destination_paths)):
        errors.append(f"{case_name}: expected unique stage destinations")

    total_bytes = 0
    staged_count = 0
    staged_bytes = 0
    for artifact in artifacts:
        if not isinstance(artifact, dict):
            errors.append(f"{case_name}: expected stage artifact object")
            continue
        staged_path = stage_path / artifact.get("destinationPath", "")
        expect_equal(
            errors,
            case_name,
            "artifact.stagedPath",
            artifact.get("stagedPath"),
            staged_path.as_posix(),
        )
        total_bytes += artifact.get("sizeBytes", 0)
        if artifact.get("staged"):
            staged_count += 1
            staged_bytes += artifact.get("sizeBytes", 0)
            if not staged_path.is_file():
                errors.append(
                    f"{case_name}: expected staged artifact file {staged_path}"
                )
                continue
            expect_equal(
                errors,
                case_name,
                f"staged {artifact.get('name')}.sizeBytes",
                staged_path.stat().st_size,
                artifact.get("sizeBytes"),
            )
            expect_equal(
                errors,
                case_name,
                f"staged {artifact.get('name')}.sha256",
                file_sha256(staged_path),
                artifact.get("sha256"),
            )
    expect_equal(
        errors,
        case_name,
        "totalArtifactBytes",
        payload.get("totalArtifactBytes"),
        total_bytes,
    )
    expect_equal(
        errors,
        case_name,
        "stagedArtifactCount",
        payload.get("stagedArtifactCount"),
        staged_count,
    )
    expect_equal(
        errors,
        case_name,
        "stagedArtifactBytes",
        payload.get("stagedArtifactBytes"),
        staged_bytes,
    )

    if expected_plan_payload is not None:
        for key in ("packageCount", "artifactCount", "totalArtifactBytes"):
            expect_equal(
                errors,
                case_name,
                key,
                payload.get(key),
                expected_plan_payload.get(key),
            )
        expected_artifacts = {
            artifact.get("destinationPath"): artifact
            for artifact in expected_plan_payload.get("artifacts", [])
            if isinstance(artifact, dict)
        }
        for artifact in artifacts:
            if not isinstance(artifact, dict):
                continue
            expected_artifact = expected_artifacts.get(artifact.get("destinationPath"))
            if expected_artifact is None:
                errors.append(
                    f"{case_name}: unexpected staged destination "
                    f"{artifact.get('destinationPath')!r}"
                )
                continue
            for field in (
                "name",
                "packagePath",
                "module",
                "target",
                "sourcePath",
                "packageArtifactPath",
                "destinationPath",
                "sizeBytes",
                "sha256",
            ):
                expect_equal(
                    errors,
                    case_name,
                    f"artifact.{field}",
                    artifact.get(field),
                    expected_artifact.get(field),
                )

    diagnostic_counts = expect_object(
        errors,
        case_name,
        "diagnosticCounts",
        payload.get("diagnosticCounts"),
    )
    diagnostics = expect_array(
        errors,
        case_name,
        "diagnostics",
        payload.get("diagnostics"),
    )
    actual_counts = {severity: 0 for severity in SEVERITIES}
    diagnostic_codes = []
    for diagnostic in diagnostics:
        if not isinstance(diagnostic, dict):
            continue
        severity = diagnostic.get("severity")
        if severity in actual_counts:
            actual_counts[severity] += 1
        diagnostic_codes.append(diagnostic.get("code"))
    for severity, count in actual_counts.items():
        expect_equal(
            errors,
            case_name,
            f"diagnosticCounts.{severity}",
            diagnostic_counts.get(severity),
            count,
        )
    if diagnostic_code is not None and diagnostic_code not in diagnostic_codes:
        errors.append(
            f"{case_name}: expected diagnostic code {diagnostic_code!r}, "
            f"got {diagnostic_codes!r}"
        )
    if diagnostic_code is None and diagnostic_codes:
        errors.append(f"{case_name}: expected no diagnostics, got {diagnostic_codes!r}")
    return payload


def expect_release_publish_receipt_json(
    errors,
    root,
    tmp_dir,
    case_name,
    result,
    *,
    stage_report_path,
    target_path=None,
    target_uri=None,
    target_descriptor_path=None,
    receipt_path=None,
    expected_stage_payload=None,
    expected_target_kind="local-filesystem",
    dry_run=False,
    expected_target_enabled=None,
    success,
    diagnostic_code=None,
):
    if result.stderr:
        errors.append(f"{case_name}: expected JSON mode to keep stderr empty")
    errors.extend(
        validate_release_publish_receipt_schema(
            root,
            tmp_dir,
            case_name,
            result.stdout,
        )
    )
    payload = parse_json_payload(errors, result, case_name)
    if not isinstance(payload, dict):
        errors.append(f"{case_name}: expected release publish receipt JSON object")
        return {}

    expect_equal(errors, case_name, "schemaVersion", payload.get("schemaVersion"), 2)
    expect_equal(
        errors,
        case_name,
        "stageReportPath",
        payload.get("stageReportPath"),
        stage_report_path.as_posix(),
    )
    expect_equal(
        errors,
        case_name,
        "targetDescriptorPath",
        payload.get("targetDescriptorPath"),
        "" if target_descriptor_path is None else target_descriptor_path.as_posix(),
    )
    expect_equal(
        errors,
        case_name,
        "dryRun",
        payload.get("dryRun"),
        dry_run,
    )
    expect_equal(
        errors,
        case_name,
        "targetKind",
        payload.get("targetKind"),
        expected_target_kind,
    )
    expected_target_path = "" if target_path is None else target_path.as_posix()
    expect_equal(
        errors,
        case_name,
        "targetPath",
        payload.get("targetPath"),
        expected_target_path,
    )
    if target_uri is None:
        target_uri = expected_target_path
    expect_equal(
        errors,
        case_name,
        "targetUri",
        payload.get("targetUri"),
        target_uri,
    )
    if expected_target_enabled is None:
        expected_target_enabled = expected_target_kind == "local-filesystem"
    expect_equal(
        errors,
        case_name,
        "targetEnabled",
        payload.get("targetEnabled"),
        expected_target_enabled,
    )
    expect_equal(errors, case_name, "success", payload.get("success"), success)
    if receipt_path is None:
        expect_equal(errors, case_name, "receiptPath", payload.get("receiptPath"), "")
        expect_equal(
            errors,
            case_name,
            "receiptWritten",
            payload.get("receiptWritten"),
            False,
        )
    else:
        expect_equal(
            errors,
            case_name,
            "receiptPath",
            payload.get("receiptPath"),
            receipt_path.as_posix(),
        )
        expect_equal(
            errors,
            case_name,
            "receiptWritten",
            payload.get("receiptWritten"),
            success,
        )
        if success and not receipt_path.is_file():
            errors.append(f"{case_name}: expected receipt file {receipt_path}")

    artifacts = expect_array(errors, case_name, "artifacts", payload.get("artifacts"))
    expect_equal(
        errors,
        case_name,
        "artifactCount",
        payload.get("artifactCount"),
        len(artifacts),
    )
    destination_paths = [
        artifact.get("destinationPath")
        for artifact in artifacts
        if isinstance(artifact, dict)
    ]
    if destination_paths != sorted(destination_paths):
        errors.append(f"{case_name}: expected sorted publish destinations")
    if len(destination_paths) != len(set(destination_paths)):
        errors.append(f"{case_name}: expected unique publish destinations")

    total_bytes = 0
    planned_count = 0
    planned_bytes = 0
    published_count = 0
    published_bytes = 0
    for artifact in artifacts:
        if not isinstance(artifact, dict):
            errors.append(f"{case_name}: expected publish artifact object")
            continue
        destination_path = artifact.get("destinationPath", "")
        if expected_target_kind == "gcs":
            expected_published_path = f"{target_uri.rstrip('/')}/{destination_path}"
            published_path = None
        else:
            published_path = target_path / destination_path
            expected_published_path = published_path.as_posix()
        expect_equal(
            errors,
            case_name,
            "artifact.publishedPath",
            artifact.get("publishedPath"),
            expected_published_path,
        )
        total_bytes += artifact.get("sizeBytes", 0)
        if artifact.get("planned"):
            planned_count += 1
            planned_bytes += artifact.get("sizeBytes", 0)
        if artifact.get("published"):
            published_count += 1
            published_bytes += artifact.get("sizeBytes", 0)
            if published_path is None:
                errors.append(
                    f"{case_name}: expected no direct file assertion for "
                    "non-local published artifact"
                )
                continue
            if not published_path.is_file():
                errors.append(
                    f"{case_name}: expected published artifact file {published_path}"
                )
                continue
            expect_equal(
                errors,
                case_name,
                f"published {artifact.get('name')}.sizeBytes",
                published_path.stat().st_size,
                artifact.get("sizeBytes"),
            )
            expect_equal(
                errors,
                case_name,
                f"published {artifact.get('name')}.sha256",
                file_sha256(published_path),
                artifact.get("sha256"),
            )
    expect_equal(
        errors,
        case_name,
        "totalArtifactBytes",
        payload.get("totalArtifactBytes"),
        total_bytes,
    )
    expect_equal(
        errors,
        case_name,
        "plannedArtifactCount",
        payload.get("plannedArtifactCount"),
        planned_count,
    )
    expect_equal(
        errors,
        case_name,
        "plannedArtifactBytes",
        payload.get("plannedArtifactBytes"),
        planned_bytes,
    )
    expect_equal(
        errors,
        case_name,
        "publishedArtifactCount",
        payload.get("publishedArtifactCount"),
        published_count,
    )
    expect_equal(
        errors,
        case_name,
        "publishedArtifactBytes",
        payload.get("publishedArtifactBytes"),
        published_bytes,
    )

    if expected_stage_payload is not None:
        for key in ("packageCount", "artifactCount", "totalArtifactBytes"):
            expect_equal(
                errors,
                case_name,
                key,
                payload.get(key),
                expected_stage_payload.get(key),
            )
        expected_artifacts = {
            artifact.get("destinationPath"): artifact
            for artifact in expected_stage_payload.get("artifacts", [])
            if isinstance(artifact, dict)
        }
        for artifact in artifacts:
            if not isinstance(artifact, dict):
                continue
            expected_artifact = expected_artifacts.get(artifact.get("destinationPath"))
            if expected_artifact is None:
                errors.append(
                    f"{case_name}: unexpected published destination "
                    f"{artifact.get('destinationPath')!r}"
                )
                continue
            for field in (
                "name",
                "packagePath",
                "module",
                "target",
                "sourcePath",
                "packageArtifactPath",
                "destinationPath",
                "stagedPath",
                "sizeBytes",
                "sha256",
                "staged",
            ):
                expect_equal(
                    errors,
                    case_name,
                    f"artifact.{field}",
                    artifact.get(field),
                    expected_artifact.get(field),
                )

    diagnostic_counts = expect_object(
        errors,
        case_name,
        "diagnosticCounts",
        payload.get("diagnosticCounts"),
    )
    diagnostics = expect_array(
        errors,
        case_name,
        "diagnostics",
        payload.get("diagnostics"),
    )
    actual_counts = {severity: 0 for severity in SEVERITIES}
    diagnostic_codes = []
    for diagnostic in diagnostics:
        if not isinstance(diagnostic, dict):
            continue
        severity = diagnostic.get("severity")
        if severity in actual_counts:
            actual_counts[severity] += 1
        diagnostic_codes.append(diagnostic.get("code"))
    for severity, count in actual_counts.items():
        expect_equal(
            errors,
            case_name,
            f"diagnosticCounts.{severity}",
            diagnostic_counts.get(severity),
            count,
        )
    if diagnostic_code is not None and diagnostic_code not in diagnostic_codes:
        errors.append(
            f"{case_name}: expected diagnostic code {diagnostic_code!r}, "
            f"got {diagnostic_codes!r}"
        )
    if diagnostic_code is None and diagnostic_codes:
        errors.append(f"{case_name}: expected no diagnostics, got {diagnostic_codes!r}")
    return payload


def expect_release_publish_upload_manifest_json(
    errors,
    root,
    case_name,
    manifest_path,
    receipt_payload,
    *,
    expected_credentials_env=None,
):
    if not manifest_path.is_file():
        errors.append(f"{case_name}: expected upload manifest file {manifest_path}")
        return {}
    errors.extend(
        validate_release_publish_upload_manifest_schema(
            root,
            case_name,
            manifest_path,
        )
    )
    try:
        payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        errors.append(f"{case_name}: expected JSON upload manifest: {exc}")
        return {}
    if not isinstance(payload, dict):
        errors.append(f"{case_name}: expected upload manifest JSON object")
        return {}

    expect_equal(errors, case_name, "schemaVersion", payload.get("schemaVersion"), 1)
    requests = expect_array(errors, case_name, "requests", payload.get("requests"))
    expect_equal(
        errors,
        case_name,
        "requestCount",
        payload.get("requestCount"),
        len(requests),
    )
    request_bytes = sum(
        request.get("sizeBytes", 0) for request in requests if isinstance(request, dict)
    )
    expect_equal(
        errors,
        case_name,
        "requestBytes",
        payload.get("requestBytes"),
        request_bytes,
    )

    planned_artifacts = [
        artifact
        for artifact in receipt_payload.get("artifacts", [])
        if isinstance(artifact, dict) and artifact.get("planned")
    ]
    expect_equal(
        errors,
        case_name,
        "planned request count",
        len(requests),
        len(planned_artifacts),
    )

    request_destinations = [
        request.get("destinationPath")
        for request in requests
        if isinstance(request, dict)
    ]
    if request_destinations != sorted(request_destinations):
        errors.append(f"{case_name}: expected sorted upload destinations")
    if len(request_destinations) != len(set(request_destinations)):
        errors.append(f"{case_name}: expected unique upload destinations")

    expected_by_destination = {
        artifact.get("destinationPath"): artifact for artifact in planned_artifacts
    }
    for request in requests:
        if not isinstance(request, dict):
            errors.append(f"{case_name}: expected upload request object")
            continue
        destination_path = request.get("destinationPath")
        expected_artifact = expected_by_destination.get(destination_path)
        if expected_artifact is None:
            errors.append(
                f"{case_name}: unexpected upload destination {destination_path!r}"
            )
            continue
        expected_upload_uri = expected_artifact.get("publishedPath")
        expect_equal(
            errors,
            case_name,
            "request.targetKind",
            request.get("targetKind"),
            receipt_payload.get("targetKind"),
        )
        expect_equal(
            errors,
            case_name,
            "request.stagedPath",
            request.get("stagedPath"),
            expected_artifact.get("stagedPath"),
        )
        expect_equal(
            errors,
            case_name,
            "request.uploadUri",
            request.get("uploadUri"),
            expected_upload_uri,
        )
        expect_equal(
            errors,
            case_name,
            "request.sizeBytes",
            request.get("sizeBytes"),
            expected_artifact.get("sizeBytes"),
        )
        expect_equal(
            errors,
            case_name,
            "request.sha256",
            request.get("sha256"),
            expected_artifact.get("sha256"),
        )
        if isinstance(expected_upload_uri, str) and expected_upload_uri.startswith(
            "gs://"
        ):
            bucket_and_object = expected_upload_uri[len("gs://") :]
            bucket, _, object_name = bucket_and_object.partition("/")
            expect_equal(
                errors,
                case_name,
                "request.bucket",
                request.get("bucket"),
                bucket,
            )
            expect_equal(
                errors,
                case_name,
                "request.objectName",
                request.get("objectName"),
                object_name,
            )
        if expected_credentials_env is not None:
            expect_equal(
                errors,
                case_name,
                "request.credentialsEnv",
                request.get("credentialsEnv"),
                expected_credentials_env,
            )
    return payload


def expect_release_publish_upload_preflight_json(
    errors,
    root,
    tmp_dir,
    case_name,
    result,
    *,
    manifest_path,
    manifest_payload,
    report_path=None,
    success=True,
    diagnostic_code=None,
    expected_report_written=None,
):
    if result.stderr:
        errors.append(f"{case_name}: expected JSON mode to keep stderr empty")
    errors.extend(
        validate_release_publish_upload_preflight_schema(
            root,
            tmp_dir,
            case_name,
            result.stdout,
        )
    )
    payload = parse_json_payload(errors, result, case_name)
    if not isinstance(payload, dict):
        errors.append(f"{case_name}: expected upload preflight JSON object")
        return {}

    if report_path is None:
        expected_report_path = ""
    else:
        expected_report_path = report_path.as_posix()
        if not report_path.is_file():
            errors.append(f"{case_name}: expected upload preflight report file")
        else:
            errors.extend(
                validate_release_publish_upload_preflight_file_schema(
                    root,
                    case_name,
                    report_path,
                )
            )
            try:
                report_payload = json.loads(report_path.read_text(encoding="utf-8"))
            except json.JSONDecodeError as exc:
                errors.append(f"{case_name}: expected JSON preflight report: {exc}")
                report_payload = None
            if report_payload is not None:
                expect_equal(
                    errors,
                    case_name,
                    "persisted upload preflight report",
                    report_payload,
                    payload,
                )

    expect_equal(errors, case_name, "schemaVersion", payload.get("schemaVersion"), 1)
    expect_equal(
        errors,
        case_name,
        "manifestPath",
        payload.get("manifestPath"),
        manifest_path.as_posix(),
    )
    expect_equal(
        errors,
        case_name,
        "reportPath",
        payload.get("reportPath"),
        expected_report_path,
    )
    if expected_report_written is None:
        expected_report_written = report_path is not None
    expect_equal(
        errors,
        case_name,
        "reportWritten",
        payload.get("reportWritten"),
        expected_report_written,
    )
    expect_equal(errors, case_name, "dryRun", payload.get("dryRun"), True)
    expect_equal(errors, case_name, "success", payload.get("success"), success)
    expect_equal(
        errors,
        case_name,
        "requestCount",
        payload.get("requestCount"),
        manifest_payload.get("requestCount"),
    )
    expect_equal(
        errors,
        case_name,
        "requestBytes",
        payload.get("requestBytes"),
        manifest_payload.get("requestBytes"),
    )

    requests = expect_array(
        errors,
        case_name,
        "validatedRequests",
        payload.get("validatedRequests"),
    )
    request_bytes = sum(
        request.get("sizeBytes", 0) for request in requests if isinstance(request, dict)
    )
    expect_equal(
        errors,
        case_name,
        "validatedRequestCount",
        payload.get("validatedRequestCount"),
        len(requests),
    )
    expect_equal(
        errors,
        case_name,
        "validatedRequestBytes",
        payload.get("validatedRequestBytes"),
        request_bytes,
    )
    request_destinations = [
        request.get("destinationPath")
        for request in requests
        if isinstance(request, dict)
    ]
    if request_destinations != sorted(request_destinations):
        errors.append(f"{case_name}: expected sorted validated upload destinations")
    if len(request_destinations) != len(set(request_destinations)):
        errors.append(f"{case_name}: expected unique validated upload destinations")
    if success:
        expect_equal(
            errors,
            case_name,
            "validatedRequests",
            requests,
            manifest_payload.get("requests", []),
        )

    diagnostic_counts = expect_object(
        errors,
        case_name,
        "diagnosticCounts",
        payload.get("diagnosticCounts"),
    )
    diagnostics = expect_array(
        errors,
        case_name,
        "diagnostics",
        payload.get("diagnostics"),
    )
    actual_counts = {severity: 0 for severity in SEVERITIES}
    diagnostic_codes = []
    for diagnostic in diagnostics:
        if not isinstance(diagnostic, dict):
            continue
        severity = diagnostic.get("severity")
        if severity in actual_counts:
            actual_counts[severity] += 1
        diagnostic_codes.append(diagnostic.get("code"))
    for severity, count in actual_counts.items():
        expect_equal(
            errors,
            case_name,
            f"diagnosticCounts.{severity}",
            diagnostic_counts.get(severity),
            count,
        )
    if diagnostic_code is not None and diagnostic_code not in diagnostic_codes:
        errors.append(
            f"{case_name}: expected diagnostic code {diagnostic_code!r}, "
            f"got {diagnostic_codes!r}"
        )
    if diagnostic_code is None and diagnostic_codes:
        errors.append(f"{case_name}: expected no diagnostics, got {diagnostic_codes!r}")
    return payload


def expect_release_publish_upload_batch_json(
    errors,
    root,
    tmp_dir,
    case_name,
    result,
    *,
    manifest_path,
    manifest_payload,
    report_path=None,
    upload_mode="mock",
    success=True,
    diagnostic_code=None,
):
    if result.stderr:
        errors.append(f"{case_name}: expected JSON mode to keep stderr empty")
    errors.extend(
        validate_release_publish_upload_batch_schema(
            root,
            tmp_dir,
            case_name,
            result.stdout,
        )
    )
    payload = parse_json_payload(errors, result, case_name)
    if not isinstance(payload, dict):
        errors.append(f"{case_name}: expected upload batch JSON object")
        return {}

    if report_path is None:
        expected_report_path = ""
    else:
        expected_report_path = report_path.as_posix()
        if not report_path.is_file():
            errors.append(f"{case_name}: expected upload batch report file")
        else:
            errors.extend(
                validate_release_publish_upload_batch_file_schema(
                    root,
                    case_name,
                    report_path,
                )
            )
            try:
                report_payload = json.loads(report_path.read_text(encoding="utf-8"))
            except json.JSONDecodeError as exc:
                errors.append(f"{case_name}: expected JSON upload batch report: {exc}")
                report_payload = None
            if report_payload is not None:
                expect_equal(
                    errors,
                    case_name,
                    "persisted upload batch report",
                    report_payload,
                    payload,
                )

    expect_equal(errors, case_name, "schemaVersion", payload.get("schemaVersion"), 1)
    expect_equal(
        errors,
        case_name,
        "manifestPath",
        payload.get("manifestPath"),
        manifest_path.as_posix(),
    )
    expect_equal(
        errors,
        case_name,
        "reportPath",
        payload.get("reportPath"),
        expected_report_path,
    )
    expect_equal(
        errors,
        case_name,
        "reportWritten",
        payload.get("reportWritten"),
        report_path is not None,
    )
    expect_equal(
        errors, case_name, "uploadMode", payload.get("uploadMode"), upload_mode
    )
    expect_equal(errors, case_name, "success", payload.get("success"), success)
    expect_equal(
        errors,
        case_name,
        "requestCount",
        payload.get("requestCount"),
        manifest_payload.get("requestCount"),
    )
    expect_equal(
        errors,
        case_name,
        "requestBytes",
        payload.get("requestBytes"),
        manifest_payload.get("requestBytes"),
    )

    requests = expect_array(
        errors,
        case_name,
        "uploadedRequests",
        payload.get("uploadedRequests"),
    )
    request_bytes = sum(
        request.get("sizeBytes", 0) for request in requests if isinstance(request, dict)
    )
    expect_equal(
        errors,
        case_name,
        "uploadedArtifactCount",
        payload.get("uploadedArtifactCount"),
        len(requests),
    )
    expect_equal(
        errors,
        case_name,
        "uploadedArtifactBytes",
        payload.get("uploadedArtifactBytes"),
        request_bytes,
    )
    request_destinations = [
        request.get("destinationPath")
        for request in requests
        if isinstance(request, dict)
    ]
    if request_destinations != sorted(request_destinations):
        errors.append(f"{case_name}: expected sorted uploaded destinations")
    if len(request_destinations) != len(set(request_destinations)):
        errors.append(f"{case_name}: expected unique uploaded destinations")
    if success:
        expect_equal(
            errors,
            case_name,
            "uploadedRequests",
            requests,
            manifest_payload.get("requests", []),
        )

    diagnostic_counts = expect_object(
        errors,
        case_name,
        "diagnosticCounts",
        payload.get("diagnosticCounts"),
    )
    diagnostics = expect_array(
        errors,
        case_name,
        "diagnostics",
        payload.get("diagnostics"),
    )
    actual_counts = {severity: 0 for severity in SEVERITIES}
    diagnostic_codes = []
    for diagnostic in diagnostics:
        if not isinstance(diagnostic, dict):
            continue
        severity = diagnostic.get("severity")
        if severity in actual_counts:
            actual_counts[severity] += 1
        diagnostic_codes.append(diagnostic.get("code"))
    for severity, count in actual_counts.items():
        expect_equal(
            errors,
            case_name,
            f"diagnosticCounts.{severity}",
            diagnostic_counts.get(severity),
            count,
        )
    if diagnostic_code is not None and diagnostic_code not in diagnostic_codes:
        errors.append(
            f"{case_name}: expected diagnostic code {diagnostic_code!r}, "
            f"got {diagnostic_codes!r}"
        )
    if diagnostic_code is None and diagnostic_codes:
        errors.append(f"{case_name}: expected no diagnostics, got {diagnostic_codes!r}")
    if "attempts" in payload:
        errors.append(f"{case_name}: upload batch v1 JSON must not expose attempts")
    return payload


def expect_release_publish_upload_receipt_json(
    errors,
    root,
    case_name,
    receipt_path,
    *,
    manifest_path,
    manifest_payload,
    upload_mode="mock",
    success=True,
    provider=None,
    overwrite=None,
    precondition_kind=None,
    precondition_value=None,
    generation=None,
    metageneration=None,
    crc32c=None,
    md5_hash=None,
    diagnostic_code=None,
):
    if not receipt_path.is_file():
        errors.append(f"{case_name}: expected upload receipt file {receipt_path}")
        return {}
    errors.extend(
        validate_release_publish_upload_receipt_file_schema(
            root,
            case_name,
            receipt_path,
        )
    )
    try:
        payload = json.loads(receipt_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        errors.append(f"{case_name}: expected JSON upload receipt: {exc}")
        return {}
    if not isinstance(payload, dict):
        errors.append(f"{case_name}: expected upload receipt JSON object")
        return {}

    expect_equal(errors, case_name, "schemaVersion", payload.get("schemaVersion"), 1)
    expect_equal(
        errors,
        case_name,
        "manifestPath",
        payload.get("manifestPath"),
        manifest_path.as_posix(),
    )
    expect_equal(
        errors,
        case_name,
        "receiptPath",
        payload.get("receiptPath"),
        receipt_path.as_posix(),
    )
    expect_equal(
        errors, case_name, "receiptWritten", payload.get("receiptWritten"), True
    )
    expect_equal(
        errors, case_name, "uploadMode", payload.get("uploadMode"), upload_mode
    )
    expect_equal(errors, case_name, "success", payload.get("success"), success)
    expect_equal(
        errors,
        case_name,
        "requestCount",
        payload.get("requestCount"),
        manifest_payload.get("requestCount"),
    )
    expect_equal(
        errors,
        case_name,
        "requestBytes",
        payload.get("requestBytes"),
        manifest_payload.get("requestBytes"),
    )

    attempts = expect_array(errors, case_name, "attempts", payload.get("attempts"))
    expect_equal(
        errors,
        case_name,
        "attemptCount",
        payload.get("attemptCount"),
        len(attempts),
    )
    attempt_bytes = sum(
        attempt.get("request", {}).get("sizeBytes", 0)
        for attempt in attempts
        if isinstance(attempt, dict)
    )
    expect_equal(
        errors,
        case_name,
        "attemptBytes",
        payload.get("attemptBytes"),
        attempt_bytes,
    )
    completed_attempts = [
        attempt
        for attempt in attempts
        if isinstance(attempt, dict)
        and attempt.get("status") in ("uploaded", "already-present")
    ]
    completed_bytes = sum(
        attempt.get("request", {}).get("sizeBytes", 0) for attempt in completed_attempts
    )
    expect_equal(
        errors,
        case_name,
        "completedAttemptCount",
        payload.get("completedAttemptCount"),
        len(completed_attempts),
    )
    expect_equal(
        errors,
        case_name,
        "completedAttemptBytes",
        payload.get("completedAttemptBytes"),
        completed_bytes,
    )
    request_destinations = [
        attempt.get("request", {}).get("destinationPath")
        for attempt in attempts
        if isinstance(attempt, dict)
    ]
    if request_destinations != sorted(request_destinations):
        errors.append(f"{case_name}: expected sorted upload receipt destinations")
    if len(request_destinations) != len(set(request_destinations)):
        errors.append(f"{case_name}: expected unique upload receipt destinations")
    if success:
        attempt_requests = [
            attempt.get("request") for attempt in attempts if isinstance(attempt, dict)
        ]
        expect_equal(
            errors,
            case_name,
            "attempt requests",
            attempt_requests,
            manifest_payload.get("requests", []),
        )

    for attempt in attempts:
        if not isinstance(attempt, dict):
            errors.append(f"{case_name}: expected upload receipt attempt object")
            continue
        if provider is not None:
            expect_equal(
                errors,
                case_name,
                "attempt.provider",
                attempt.get("provider"),
                provider,
            )
        if overwrite is not None:
            expect_equal(
                errors,
                case_name,
                "attempt.overwrite",
                attempt.get("overwrite"),
                overwrite,
            )
        if precondition_kind is not None:
            expect_equal(
                errors,
                case_name,
                "attempt.preconditionKind",
                attempt.get("preconditionKind"),
                precondition_kind,
            )
        if precondition_value is not None:
            expect_equal(
                errors,
                case_name,
                "attempt.preconditionValue",
                attempt.get("preconditionValue"),
                precondition_value,
            )
        if provider in ("mock", "gcs") and not attempt.get("idempotencyKey"):
            errors.append(f"{case_name}: expected attempt idempotency key")
        if generation is not None:
            expect_equal(
                errors,
                case_name,
                "attempt.generation",
                attempt.get("generation"),
                generation,
            )
        if metageneration is not None:
            expect_equal(
                errors,
                case_name,
                "attempt.metageneration",
                attempt.get("metageneration"),
                metageneration,
            )
        if crc32c is not None:
            expect_equal(
                errors,
                case_name,
                "attempt.crc32c",
                attempt.get("crc32c"),
                crc32c,
            )
        if md5_hash is not None:
            expect_equal(
                errors,
                case_name,
                "attempt.md5Hash",
                attempt.get("md5Hash"),
                md5_hash,
            )

    diagnostic_counts = expect_object(
        errors,
        case_name,
        "diagnosticCounts",
        payload.get("diagnosticCounts"),
    )
    diagnostics = expect_array(
        errors,
        case_name,
        "diagnostics",
        payload.get("diagnostics"),
    )
    actual_counts = {severity: 0 for severity in SEVERITIES}
    diagnostic_codes = []
    for diagnostic in diagnostics:
        if not isinstance(diagnostic, dict):
            continue
        severity = diagnostic.get("severity")
        if severity in actual_counts:
            actual_counts[severity] += 1
        diagnostic_codes.append(diagnostic.get("code"))
    for severity, count in actual_counts.items():
        expect_equal(
            errors,
            case_name,
            f"diagnosticCounts.{severity}",
            diagnostic_counts.get(severity),
            count,
        )
    if diagnostic_code is not None and diagnostic_code not in diagnostic_codes:
        errors.append(
            f"{case_name}: expected diagnostic code {diagnostic_code!r}, "
            f"got {diagnostic_codes!r}"
        )
    if diagnostic_code is None and diagnostic_codes:
        errors.append(f"{case_name}: expected no diagnostics, got {diagnostic_codes!r}")
    return payload


def expected_sidecar(path, kind, token, attempt, directory=True):
    return {
        "path": path,
        "kind": kind,
        "token": token,
        "attempt": attempt,
        "directory": directory,
    }


def expected_cleanup_candidate(
    path,
    kind,
    token,
    attempt,
    *,
    directory,
    reason,
    action,
    success=True,
    retained_by=None,
):
    candidate = {
        "path": path,
        "kind": kind,
        "token": token,
        "attempt": attempt,
        "directory": directory,
        "reason": reason,
        "action": action,
        "success": success,
    }
    if retained_by is not None:
        candidate["retainedBy"] = retained_by
    return candidate


def set_fixture_mtime(path, seconds_ago):
    timestamp = time.time() - seconds_ago
    os.utime(path, (timestamp, timestamp))


def previous_sidecars(requested):
    prefix = f".{requested.name}.previous-"
    return sorted(
        path
        for path in requested.parent.iterdir()
        if path.name.startswith(prefix) and path.is_dir()
    )


def run_cases(root, cglc):
    errors = []
    with tempfile.TemporaryDirectory() as tmp:
        tmp_dir = Path(tmp)

        package, source, _manifest = make_package(tmp_dir, "recover-promote")
        sidecar = tmp_dir / ".recover-promote.cglb.staging-111-0"
        package.rename(sidecar)
        result = run_recover(cglc, sidecar, "--promote", source=source)
        errors.extend(
            expect_success(result, "recover-promote", "promoted package sidecar")
        )
        if not package.is_dir():
            errors.append("recover-promote: expected requested package directory")
        if sidecar.exists():
            errors.append("recover-promote: expected staging sidecar to be removed")
        errors.extend(expect_verified(cglc, "recover-promote", package, source))

        json_package, json_source, _manifest = make_package(
            tmp_dir,
            "recover-promote-json",
        )
        json_sidecar = tmp_dir / ".recover-promote-json.cglb.staging-111-json-0"
        json_package.rename(json_sidecar)
        result = run_recover(
            cglc,
            json_sidecar,
            "--promote",
            source=json_source,
            json_output=True,
        )
        if result.returncode != 0:
            errors.append(
                "recover-promote-json: expected success, got "
                f"{result.stderr}{result.stdout}".strip()
            )
        expect_recovery_json(
            errors,
            root,
            tmp_dir,
            "recover-promote-json",
            result,
            action="promote",
            sidecar=json_sidecar,
            requested=json_package,
            success=True,
            message_substring="promoted package sidecar",
        )
        errors.extend(
            expect_verified(cglc, "recover-promote-json", json_package, json_source)
        )

        nonuniform_package, nonuniform_source, nonuniform_manifest = make_package(
            tmp_dir,
            "recover-promote-nonuniform-metadata",
            target="metal",
        )
        add_native_artifact_descriptor(
            nonuniform_package,
            nonuniform_manifest,
            mutate=mark_native_artifact_validated,
        )
        write_nonuniform_reflection(nonuniform_package, nonuniform_manifest)
        nonuniform_diagnostics = write_nonuniform_diagnostics(
            nonuniform_package,
            nonuniform_manifest["target"],
        )
        nonuniform_sidecar = (
            tmp_dir / ".recover-promote-nonuniform-metadata.cglb.staging-nonuniform-0"
        )
        nonuniform_package.rename(nonuniform_sidecar)
        result = run_recover(
            cglc,
            nonuniform_sidecar,
            "--promote",
            source=nonuniform_source,
            json_output=True,
        )
        if result.returncode != 0:
            errors.append(
                "recover-promote-nonuniform-metadata: expected success, got "
                f"{result.stderr}{result.stdout}".strip()
            )
        expect_recovery_json(
            errors,
            root,
            tmp_dir,
            "recover-promote-nonuniform-metadata",
            result,
            action="promote",
            sidecar=nonuniform_sidecar,
            requested=nonuniform_package,
            success=True,
            message_substring="promoted package sidecar",
        )
        errors.extend(
            expect_verified(
                cglc,
                "recover-promote-nonuniform-metadata",
                nonuniform_package,
                nonuniform_source,
            )
        )
        errors.extend(
            expect_nonuniform_metadata_preserved(
                "recover-promote-nonuniform-metadata",
                nonuniform_package,
                nonuniform_manifest["target"],
                nonuniform_diagnostics,
            )
        )

        opengl_package, opengl_source, opengl_manifest = make_package(
            tmp_dir,
            "recover-promote-opengl-planned-native",
            target="opengl",
        )
        opengl_native_binary = package_path(
            opengl_package,
            opengl_manifest["artifacts"]["nativeBinary"],
        )
        if opengl_native_binary.exists():
            errors.append(
                "recover-promote-opengl-planned-native: expected planned native "
                "binary to be absent before promotion"
            )
        opengl_sidecar = (
            tmp_dir / ".recover-promote-opengl-planned-native.cglb.staging-opengl-0"
        )
        opengl_package.rename(opengl_sidecar)
        result = run_recover(
            cglc,
            opengl_sidecar,
            "--promote",
            source=opengl_source,
            json_output=True,
        )
        if result.returncode != 0:
            errors.append(
                "recover-promote-opengl-planned-native: expected success, got "
                f"{result.stderr}{result.stdout}".strip()
            )
        expect_recovery_json(
            errors,
            root,
            tmp_dir,
            "recover-promote-opengl-planned-native",
            result,
            action="promote",
            sidecar=opengl_sidecar,
            requested=opengl_package,
            success=True,
            message_substring="promoted package sidecar",
        )
        errors.extend(
            expect_verified(
                cglc,
                "recover-promote-opengl-planned-native",
                opengl_package,
                opengl_source,
            )
        )
        if opengl_native_binary.exists():
            errors.append(
                "recover-promote-opengl-planned-native: expected planned native "
                "binary to remain absent after promotion"
            )

        published, _source, _manifest = make_package(tmp_dir, "recover-existing")
        staged, staged_source, _manifest = make_package(tmp_dir, "recover-stage")
        existing_sidecar = tmp_dir / ".recover-existing.cglb.staging-222-0"
        staged.rename(existing_sidecar)
        result = run_recover(cglc, existing_sidecar, "--promote")
        errors.extend(
            expect_failure(
                result,
                "recover-existing",
                "package.recover.output-exists",
            )
        )
        if not published.is_dir() or not existing_sidecar.is_dir():
            errors.append(
                "recover-existing: expected published package and sidecar to survive"
            )

        result = run_recover(cglc, existing_sidecar, "--promote", json_output=True)
        if result.returncode == 0:
            errors.append("recover-existing-json: expected failure")
        expect_recovery_json(
            errors,
            root,
            tmp_dir,
            "recover-existing-json",
            result,
            action="promote",
            sidecar=existing_sidecar,
            requested=published,
            success=False,
            diagnostic_code="package.recover.output-exists",
        )

        result = run_recover(
            cglc,
            existing_sidecar,
            "--promote",
            "--replace",
            source=staged_source,
            json_output=True,
        )
        if result.returncode != 0:
            errors.append(
                "recover-replace-json: expected success, got "
                f"{result.stderr}{result.stdout}".strip()
            )
        payload = expect_recovery_json(
            errors,
            root,
            tmp_dir,
            "recover-replace-json",
            result,
            action="promote",
            sidecar=existing_sidecar,
            requested=published,
            success=True,
            backup_present=True,
            message_substring="previous package moved to",
        )
        errors.extend(
            expect_success(result, "recover-replace-json", "previous package moved to")
        )
        if existing_sidecar.exists():
            errors.append("recover-replace: expected staging sidecar to be promoted")
        backups = previous_sidecars(published)
        if len(backups) != 1:
            errors.append(
                f"recover-replace: expected one previous sidecar, got {backups!r}"
            )
        elif payload.get("backupPath") != backups[0].as_posix():
            errors.append(
                "recover-replace-json: expected JSON backupPath to match "
                f"{backups[0].as_posix()!r}, got {payload.get('backupPath')!r}"
            )
        errors.extend(
            expect_verified(cglc, "recover-replace", published, staged_source)
        )

        list_package, _source, _manifest = make_package(tmp_dir, "recover-list")
        list_staging_package, _source, _manifest = make_package(
            tmp_dir,
            "recover-list-staged",
        )
        list_previous_package, _source, _manifest = make_package(
            tmp_dir,
            "recover-list-previous",
        )
        list_staging_sidecar = tmp_dir / ".recover-list.cglb.staging-list-2"
        list_previous_sidecar = tmp_dir / ".recover-list.cglb.previous-old-1"
        list_file_sidecar = tmp_dir / ".recover-list.cglb.staging-file-3"
        list_staging_package.rename(list_staging_sidecar)
        list_previous_package.rename(list_previous_sidecar)
        list_file_sidecar.write_text("not a package directory\n", encoding="utf-8")
        expected_list_sidecars = (
            expected_sidecar(list_previous_sidecar, "previous", "old", 1),
            expected_sidecar(list_file_sidecar, "staging", "file", 3, directory=False),
            expected_sidecar(list_staging_sidecar, "staging", "list", 2),
        )

        result = run_recover(cglc, list_package, "--list", json_output=True)
        if result.returncode != 0:
            errors.append(
                "recover-list-json: expected success, got "
                f"{result.stderr}{result.stdout}".strip()
            )
        expect_sidecar_list_json(
            errors,
            root,
            tmp_dir,
            "recover-list-json",
            result,
            queried=list_package,
            requested=list_package,
            state="published",
            expected_sidecars=expected_list_sidecars,
        )

        result = run_recover(cglc, list_staging_sidecar, "--list", json_output=True)
        if result.returncode != 0:
            errors.append(
                "recover-list-current-sidecar-json: expected success, got "
                f"{result.stderr}{result.stdout}".strip()
            )
        expect_sidecar_list_json(
            errors,
            root,
            tmp_dir,
            "recover-list-current-sidecar-json",
            result,
            queried=list_staging_sidecar,
            requested=list_package,
            state="staged",
            sidecar_kind="staging",
            sidecar_token="list",
            sidecar_attempt=2,
            expected_sidecars=expected_list_sidecars,
        )

        missing_requested = tmp_dir / "recover-list-missing.cglb"
        missing_sidecar_package, _source, _manifest = make_package(
            tmp_dir,
            "recover-list-missing-staged",
        )
        missing_sidecar = tmp_dir / ".recover-list-missing.cglb.staging-new-0"
        missing_sidecar_package.rename(missing_sidecar)
        result = run_recover(cglc, missing_requested, "--list", json_output=True)
        if result.returncode != 0:
            errors.append(
                "recover-list-missing-json: expected success, got "
                f"{result.stderr}{result.stdout}".strip()
            )
        expect_sidecar_list_json(
            errors,
            root,
            tmp_dir,
            "recover-list-missing-json",
            result,
            queried=missing_requested,
            requested=missing_requested,
            state="published",
            requested_exists=False,
            expected_sidecars=(expected_sidecar(missing_sidecar, "staging", "new", 0),),
        )

        result = run_recover(cglc, list_package, "--list")
        errors.extend(
            expect_success(result, "recover-list-text", "package sidecars for")
        )
        if list_previous_sidecar.as_posix() not in result.stdout:
            errors.append("recover-list-text: expected previous sidecar path")
        if "directory=false" not in result.stdout:
            errors.append("recover-list-text: expected non-directory sidecar marker")

        result = run_recover(cglc, list_package, "--list", "--promote")
        errors.extend(
            expect_failure(
                result,
                "recover-list-action-conflict",
                "package recover --list cannot be combined",
            )
        )

        expected_stale_dry_run = (
            expected_cleanup_candidate(
                list_previous_sidecar,
                "previous",
                "old",
                1,
                directory=True,
                reason="previous-backup",
                action="would-discard",
            ),
            expected_cleanup_candidate(
                list_file_sidecar,
                "staging",
                "file",
                3,
                directory=False,
                reason="not-directory",
                action="would-discard",
            ),
            expected_cleanup_candidate(
                list_staging_sidecar,
                "staging",
                "list",
                2,
                directory=True,
                reason="staging-with-published-output",
                action="would-discard",
            ),
        )
        result = run_recover(
            cglc,
            list_package,
            "--discard-stale",
            json_output=True,
        )
        if result.returncode != 0:
            errors.append(
                "recover-discard-stale-json: expected success, got "
                f"{result.stderr}{result.stdout}".strip()
            )
        expect_stale_cleanup_json(
            errors,
            root,
            tmp_dir,
            "recover-discard-stale-json",
            result,
            queried=list_package,
            requested=list_package,
            dry_run=True,
            requested_exists=True,
            expected_candidates=expected_stale_dry_run,
        )
        for stale_path in (
            list_previous_sidecar,
            list_file_sidecar,
            list_staging_sidecar,
        ):
            if not stale_path.exists():
                errors.append(
                    "recover-discard-stale-json: expected dry run to keep "
                    f"{stale_path.as_posix()}"
                )

        result = run_recover(cglc, list_package, "--discard-stale")
        errors.extend(
            expect_success(
                result,
                "recover-discard-stale-text",
                "stale package sidecar dry run",
            )
        )
        if "would-discard" not in result.stdout:
            errors.append(
                "recover-discard-stale-text: expected dry-run action in stdout"
            )

        expected_stale_applied = tuple(
            {
                **candidate,
                "action": "discarded",
            }
            for candidate in expected_stale_dry_run
        )
        result = run_recover(
            cglc,
            list_package,
            "--discard-stale",
            "--apply",
            json_output=True,
        )
        if result.returncode != 0:
            errors.append(
                "recover-discard-stale-apply-json: expected success, got "
                f"{result.stderr}{result.stdout}".strip()
            )
        expect_stale_cleanup_json(
            errors,
            root,
            tmp_dir,
            "recover-discard-stale-apply-json",
            result,
            queried=list_package,
            requested=list_package,
            dry_run=False,
            requested_exists=True,
            expected_candidates=expected_stale_applied,
        )
        for stale_path in (
            list_previous_sidecar,
            list_file_sidecar,
            list_staging_sidecar,
        ):
            if stale_path.exists():
                errors.append(
                    "recover-discard-stale-apply-json: expected stale sidecar "
                    f"to be discarded: {stale_path.as_posix()}"
                )

        maintain_package, _source, _manifest = make_package(tmp_dir, "maintain")
        maintain_previous_package, _source, _manifest = make_package(
            tmp_dir,
            "maintain-previous",
        )
        maintain_staging_package, _source, _manifest = make_package(
            tmp_dir,
            "maintain-staging",
        )
        maintain_previous = tmp_dir / ".maintain.cglb.previous-cli-0"
        maintain_staging = tmp_dir / ".maintain.cglb.staging-cli-1"
        maintain_previous_package.rename(maintain_previous)
        maintain_staging_package.rename(maintain_staging)
        expected_maintain_dry_run = (
            expected_cleanup_candidate(
                maintain_previous,
                "previous",
                "cli",
                0,
                directory=True,
                reason="previous-backup",
                action="would-discard",
            ),
            expected_cleanup_candidate(
                maintain_staging,
                "staging",
                "cli",
                1,
                directory=True,
                reason="staging-with-published-output",
                action="would-discard",
            ),
        )
        result = run_maintain(cglc, maintain_package, json_output=True)
        if result.returncode != 0:
            errors.append(
                "package-maintain-json: expected success, got "
                f"{result.stderr}{result.stdout}".strip()
            )
        expect_stale_cleanup_json(
            errors,
            root,
            tmp_dir,
            "package-maintain-json",
            result,
            queried=maintain_package,
            requested=maintain_package,
            dry_run=True,
            requested_exists=True,
            expected_candidates=expected_maintain_dry_run,
        )

        result = run_maintain(cglc, maintain_package)
        errors.extend(
            expect_success(
                result,
                "package-maintain-text",
                "stale package sidecar dry run",
            )
        )
        if "would-discard" not in result.stdout:
            errors.append("package-maintain-text: expected dry-run action in stdout")

        result = run_maintain(cglc, maintain_package, "--dry-run", "--apply")
        errors.extend(
            expect_failure(
                result,
                "package-maintain-mode-conflict",
                "package maintain accepts only one of --dry-run or --apply",
            )
        )

        result = run_maintain(cglc, maintain_package, "--promote")
        errors.extend(
            expect_failure(
                result,
                "package-maintain-recover-flag-conflict",
                "package maintain does not accept",
            )
        )

        result = run_maintain(cglc, maintain_package, "--discard-stale")
        errors.extend(
            expect_failure(
                result,
                "package-maintain-discard-stale-conflict",
                "package maintain does not accept",
            )
        )

        expected_maintain_applied = tuple(
            {
                **candidate,
                "action": "discarded",
            }
            for candidate in expected_maintain_dry_run
        )
        result = run_maintain(
            cglc,
            maintain_package,
            "--apply",
            json_output=True,
        )
        if result.returncode != 0:
            errors.append(
                "package-maintain-apply-json: expected success, got "
                f"{result.stderr}{result.stdout}".strip()
            )
        expect_stale_cleanup_json(
            errors,
            root,
            tmp_dir,
            "package-maintain-apply-json",
            result,
            queried=maintain_package,
            requested=maintain_package,
            dry_run=False,
            requested_exists=True,
            expected_candidates=expected_maintain_applied,
        )
        for stale_path in (maintain_previous, maintain_staging):
            if stale_path.exists():
                errors.append(
                    "package-maintain-apply-json: expected stale sidecar to "
                    f"be discarded: {stale_path.as_posix()}"
                )

        policy_package, _source, _manifest = make_package(
            tmp_dir,
            "maintain-policy",
        )
        policy_previous_old_package, _source, _manifest = make_package(
            tmp_dir,
            "maintain-policy-previous-old",
        )
        policy_previous_new_package, _source, _manifest = make_package(
            tmp_dir,
            "maintain-policy-previous-new",
        )
        policy_staging_package, _source, _manifest = make_package(
            tmp_dir,
            "maintain-policy-staging",
        )
        policy_previous_old = tmp_dir / ".maintain-policy.cglb.previous-100-0"
        policy_previous_new = tmp_dir / ".maintain-policy.cglb.previous-300-0"
        policy_staging = tmp_dir / ".maintain-policy.cglb.staging-200-0"
        policy_file = tmp_dir / ".maintain-policy.cglb.staging-400-0"
        policy_previous_old_package.rename(policy_previous_old)
        policy_previous_new_package.rename(policy_previous_new)
        policy_staging_package.rename(policy_staging)
        policy_file.write_text("not a package directory\n", encoding="utf-8")
        policy_path = tmp_dir / "maintain-policy.json"
        policy_path.write_text(
            "{\n"
            '  "schemaVersion": 1,\n'
            '  "staleSidecars": {\n'
            '    "keepLast": 1\n'
            "  }\n"
            "}\n",
            encoding="utf-8",
        )
        errors.extend(
            validate_policy_schema(root, "package-maintain-policy-schema", policy_path)
        )
        expected_policy_candidates = (
            expected_cleanup_candidate(
                policy_previous_old,
                "previous",
                "100",
                0,
                directory=True,
                reason="previous-backup",
                action="would-discard",
            ),
            expected_cleanup_candidate(
                policy_file,
                "staging",
                "400",
                0,
                directory=False,
                reason="not-directory",
                action="would-discard",
            ),
            expected_cleanup_candidate(
                policy_staging,
                "staging",
                "200",
                0,
                directory=True,
                reason="staging-with-published-output",
                action="would-discard",
            ),
        )
        expected_policy_retained = (
            expected_cleanup_candidate(
                policy_previous_new,
                "previous",
                "300",
                0,
                directory=True,
                reason="previous-backup",
                action="kept",
                retained_by="keep-last",
            ),
        )
        result = run_maintain(
            cglc,
            policy_package,
            "--policy",
            policy_path,
            json_output=True,
        )
        if result.returncode != 0:
            errors.append(
                "package-maintain-policy-json: expected success, got "
                f"{result.stderr}{result.stdout}".strip()
            )
        expect_stale_cleanup_json(
            errors,
            root,
            tmp_dir,
            "package-maintain-policy-json",
            result,
            queried=policy_package,
            requested=policy_package,
            dry_run=True,
            requested_exists=True,
            keep_last=1,
            expected_candidates=expected_policy_candidates,
            expected_retained=expected_policy_retained,
        )

        result = run_recover(
            cglc,
            policy_package,
            "--discard-stale",
            "--policy",
            policy_path,
            json_output=True,
        )
        if result.returncode != 0:
            errors.append(
                "recover-discard-stale-policy-json: expected success, got "
                f"{result.stderr}{result.stdout}".strip()
            )
        expect_stale_cleanup_json(
            errors,
            root,
            tmp_dir,
            "recover-discard-stale-policy-json",
            result,
            queried=policy_package,
            requested=policy_package,
            dry_run=True,
            requested_exists=True,
            keep_last=1,
            expected_candidates=expected_policy_candidates,
            expected_retained=expected_policy_retained,
        )

        expected_policy_override_candidates = (
            *expected_policy_candidates,
            expected_cleanup_candidate(
                policy_previous_new,
                "previous",
                "300",
                0,
                directory=True,
                reason="previous-backup",
                action="would-discard",
            ),
        )
        result = run_maintain(
            cglc,
            policy_package,
            "--policy",
            policy_path,
            "--keep-last",
            "0",
            json_output=True,
        )
        if result.returncode != 0:
            errors.append(
                "package-maintain-policy-override-json: expected success, got "
                f"{result.stderr}{result.stdout}".strip()
            )
        expect_stale_cleanup_json(
            errors,
            root,
            tmp_dir,
            "package-maintain-policy-override-json",
            result,
            queried=policy_package,
            requested=policy_package,
            dry_run=True,
            requested_exists=True,
            keep_last=0,
            expected_candidates=expected_policy_override_candidates,
        )

        invalid_policy_path = tmp_dir / "maintain-policy-invalid.json"
        invalid_policy_path.write_text(
            "{\n"
            '  "schemaVersion": 1,\n'
            '  "staleSidecars": {\n'
            '    "keepLast": "one"\n'
            "  }\n"
            "}\n",
            encoding="utf-8",
        )
        result = run_maintain(
            cglc,
            policy_package,
            "--policy",
            invalid_policy_path,
        )
        errors.extend(
            expect_failure(
                result,
                "package-maintain-policy-invalid",
                "package.maintain.policy.invalid-keep-last",
            )
        )

        scan_dir = tmp_dir / "maintain-scan"
        scan_dir.mkdir()
        scan_package, _source, scan_manifest = make_package(scan_dir, "scan-a")
        add_native_artifact_descriptor(scan_package, scan_manifest)
        scan_previous_package, _source, _manifest = make_package(
            scan_dir,
            "scan-a-previous",
        )
        scan_staging_package, _source, _manifest = make_package(
            scan_dir,
            "scan-a-staging",
        )
        scan_missing_previous_package, _source, _manifest = make_package(
            scan_dir,
            "scan-missing-previous",
        )
        scan_missing_staging_package, _source, _manifest = make_package(
            scan_dir,
            "scan-missing-staging",
        )
        scan_previous = scan_dir / ".scan-a.cglb.previous-100-0"
        scan_staging = scan_dir / ".scan-a.cglb.staging-200-0"
        scan_missing = scan_dir / "scan-missing.cglb"
        scan_missing_previous = scan_dir / ".scan-missing.cglb.previous-300-0"
        scan_missing_staging = scan_dir / ".scan-missing.cglb.staging-400-0"
        scan_previous_package.rename(scan_previous)
        scan_staging_package.rename(scan_staging)
        scan_missing_previous_package.rename(scan_missing_previous)
        scan_missing_staging_package.rename(scan_missing_staging)
        (scan_dir / "notes.txt").write_text("ignored\n", encoding="utf-8")
        nested_scan_dir = scan_dir / "nested"
        nested_scan_dir.mkdir()
        nested_scan_package, _nested_source, _nested_manifest = make_package(
            nested_scan_dir,
            "nested-package",
        )

        expected_scan_packages = (
            {
                "package": scan_package,
                "requested_exists": True,
                "expected_candidates": (
                    expected_cleanup_candidate(
                        scan_previous,
                        "previous",
                        "100",
                        0,
                        directory=True,
                        reason="previous-backup",
                        action="would-discard",
                    ),
                    expected_cleanup_candidate(
                        scan_staging,
                        "staging",
                        "200",
                        0,
                        directory=True,
                        reason="staging-with-published-output",
                        action="would-discard",
                    ),
                ),
            },
            {
                "package": scan_missing,
                "requested_exists": False,
                "expected_candidates": (
                    expected_cleanup_candidate(
                        scan_missing_previous,
                        "previous",
                        "300",
                        0,
                        directory=True,
                        reason="previous-backup",
                        action="would-discard",
                    ),
                ),
            },
        )
        result = run_maintain_scan(
            cglc,
            scan_dir,
            "--keep-last",
            "0",
            json_output=True,
        )
        if result.returncode != 0:
            errors.append(
                "package-maintain-scan-json: expected success, got "
                f"{result.stderr}{result.stdout}".strip()
            )
        expect_maintenance_report_json(
            errors,
            root,
            tmp_dir,
            "package-maintain-scan-json",
            result,
            scan_root=scan_dir,
            dry_run=True,
            keep_last=0,
            expected_packages=expected_scan_packages,
        )

        result = run_maintain_scan(cglc, scan_dir)
        errors.extend(
            expect_success(
                result,
                "package-maintain-scan-text",
                "package maintenance scan dry run",
            )
        )

        exported_set_path = scan_dir / "exported-package-set.json"
        result = run_maintain_scan(
            cglc,
            scan_dir,
            "--export-package-set",
            exported_set_path,
            json_output=True,
        )
        if result.returncode != 0:
            errors.append(
                "package-maintain-scan-export-set-json: expected success, got "
                f"{result.stderr}{result.stdout}".strip()
            )
        if result.stderr:
            errors.append(
                "package-maintain-scan-export-set-json: expected no diagnostics"
            )
        expect_package_set_document(
            errors,
            root,
            "package-maintain-scan-export-set-json",
            exported_set_path,
            expected_packages=("scan-a.cglb", "scan-missing.cglb"),
            stdout_json=result.stdout,
        )

        result = run_maintain_scan(
            cglc,
            scan_dir,
            "--export-package-set",
            exported_set_path,
        )
        errors.extend(
            expect_success(
                result,
                "package-maintain-scan-export-set-text",
                "exported package maintenance set",
            )
        )

        result = run_maintain_scan(
            cglc,
            scan_dir,
            "--verify-package-set",
            exported_set_path,
            json_output=True,
        )
        if result.returncode != 0:
            errors.append(
                "package-maintain-scan-verify-set-json: expected success, got "
                f"{result.stderr}{result.stdout}".strip()
            )
        expect_package_set_verification_json(
            errors,
            root,
            tmp_dir,
            "package-maintain-scan-verify-set-json",
            result,
            scan_root=scan_dir,
            set_path=exported_set_path,
            success=True,
            matches=True,
            scanned_packages=(scan_package, scan_missing),
            set_packages=(scan_package, scan_missing),
        )

        result = run_maintain_scan(
            cglc,
            scan_dir,
            "--verify-package-set",
            exported_set_path,
        )
        errors.extend(
            expect_success(
                result,
                "package-maintain-scan-verify-set-text",
                "package maintenance set matches scan",
            )
        )

        verification_batch_path = scan_dir / "package-set-verification-batch.json"
        verification_batch_path.write_text(
            json.dumps(
                {
                    "schemaVersion": 1,
                    "verifications": [
                        {
                            "rootPath": ".",
                            "setPath": "exported-package-set.json",
                        }
                    ],
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        errors.extend(
            validate_maintenance_set_verification_batch_schema(
                root,
                "package-maintain-verify-set-batch-schema",
                verification_batch_path,
            )
        )
        expected_matching_verification = {
            "scan_root": scan_dir,
            "set_path": exported_set_path,
            "success": True,
            "matches": True,
            "scanned_packages": (scan_package, scan_missing),
            "set_packages": (scan_package, scan_missing),
        }
        verification_summary_path = scan_dir / "package-set-verification-summary.json"
        result = run_maintain_verification_batch(
            cglc,
            verification_batch_path,
            "--summary-output",
            verification_summary_path,
            json_output=True,
        )
        if result.returncode != 0:
            errors.append(
                "package-maintain-verify-set-batch-json: expected success, got "
                f"{result.stderr}{result.stdout}".strip()
            )
        expect_package_set_verification_batch_json(
            errors,
            root,
            tmp_dir,
            "package-maintain-verify-set-batch-json",
            result,
            batch_path=verification_batch_path,
            success=True,
            matches=True,
            expected_verifications=(expected_matching_verification,),
        )
        expect_package_set_verification_batch_summary_file(
            errors,
            root,
            "package-maintain-verify-set-batch-summary-json",
            verification_summary_path,
            batch_path=verification_batch_path,
            success=True,
            matches=True,
            expected_verifications=(expected_matching_verification,),
        )
        release_manifest_path = scan_dir / "package-release-promotion-manifest.json"
        release_bundle_path = scan_dir / "package-release-bundle.json"
        result = run_package_release(
            cglc,
            "--promotion-summary",
            verification_summary_path,
            "--manifest-output",
            release_manifest_path,
            "--bundle-output",
            release_bundle_path,
            json_output=True,
        )
        if result.returncode != 0:
            errors.append(
                "package-release-promotion-manifest-json: expected success, got "
                f"{result.stderr}{result.stdout}".strip()
            )
        if result.stderr:
            errors.append(
                "package-release-promotion-manifest-json: expected no diagnostics"
            )
        expect_release_promotion_manifest_file(
            errors,
            root,
            "package-release-promotion-manifest-json",
            release_manifest_path,
            summary_path=verification_summary_path,
            batch_path=verification_batch_path,
            release_eligible=True,
            stdout_json=result.stdout,
            expected_blocker_codes=(),
            expected_package_paths=(scan_package,),
        )
        release_bundle_payload = expect_release_bundle_file(
            errors,
            root,
            "package-release-bundle-json",
            release_bundle_path,
            promotion_manifest_path=release_manifest_path,
            summary_path=verification_summary_path,
            batch_path=verification_batch_path,
            release_eligible=True,
            expected_blocker_codes=(),
            expected_package_paths=(scan_package,),
        )
        result = run_package_release(
            cglc,
            "--verify-bundle",
            release_bundle_path,
            json_output=True,
        )
        if result.returncode != 0:
            errors.append(
                "package-release-bundle-verify-json: expected success, got "
                f"{result.stderr}{result.stdout}".strip()
            )
        expect_release_bundle_verification_json(
            errors,
            root,
            tmp_dir,
            "package-release-bundle-verify-json",
            result,
            bundle_path=release_bundle_path,
            success=True,
            release_eligible=True,
            status="eligible",
            expected_bundle_payload=release_bundle_payload,
        )
        release_publish_plan_path = scan_dir / "package-release-publish-plan.json"
        result = run_package_release(
            cglc,
            "--plan-publish",
            release_bundle_path,
            "--plan-output",
            release_publish_plan_path,
            json_output=True,
        )
        if result.returncode != 0:
            errors.append(
                "package-release-publish-plan-json: expected success, got "
                f"{result.stderr}{result.stdout}".strip()
            )
        if result.stderr:
            errors.append("package-release-publish-plan-json: expected no diagnostics")
        release_publish_plan_payload = expect_release_publish_plan_file(
            errors,
            root,
            "package-release-publish-plan-json",
            release_publish_plan_path,
            bundle_path=release_bundle_path,
            expected_bundle_payload=release_bundle_payload,
            stdout_json=result.stdout,
        )
        release_publish_stage_path = scan_dir / "package-release-stage"
        result = run_package_release(
            cglc,
            "--stage-publish",
            release_publish_plan_path,
            "--stage-output",
            release_publish_stage_path,
            json_output=True,
        )
        if result.returncode != 0:
            errors.append(
                "package-release-publish-stage-json: expected success, got "
                f"{result.stderr}{result.stdout}".strip()
            )
        release_publish_stage_payload = expect_release_publish_stage_json(
            errors,
            root,
            tmp_dir,
            "package-release-publish-stage-json",
            result,
            plan_path=release_publish_plan_path,
            stage_path=release_publish_stage_path,
            expected_plan_payload=release_publish_plan_payload,
            success=True,
        )
        release_publish_stage_report_path = (
            scan_dir / "package-release-publish-stage.json"
        )
        release_publish_stage_report_path.write_text(
            result.stdout,
            encoding="utf-8",
        )

        release_publish_target_path = scan_dir / "package-release-published"
        release_publish_receipt_path = scan_dir / "package-release-publish-receipt.json"
        result = run_package_release(
            cglc,
            "--publish-stage",
            release_publish_stage_report_path,
            "--publish-target",
            "local-filesystem",
            "--target-output",
            release_publish_target_path,
            "--receipt-output",
            release_publish_receipt_path,
            json_output=True,
        )
        if result.returncode != 0:
            errors.append(
                "package-release-publish-receipt-json: expected success, got "
                f"{result.stderr}{result.stdout}".strip()
            )
        expect_release_publish_receipt_json(
            errors,
            root,
            tmp_dir,
            "package-release-publish-receipt-json",
            result,
            stage_report_path=release_publish_stage_report_path,
            target_path=release_publish_target_path,
            receipt_path=release_publish_receipt_path,
            expected_stage_payload=release_publish_stage_payload,
            success=True,
        )

        result = run_package_release(
            cglc,
            "--publish-stage",
            release_publish_stage_report_path,
            "--publish-target",
            "local-filesystem",
            "--target-output",
            release_publish_target_path,
            json_output=True,
        )
        if result.returncode == 0:
            errors.append("package-release-publish-existing-json: expected failure")
        expect_release_publish_receipt_json(
            errors,
            root,
            tmp_dir,
            "package-release-publish-existing-json",
            result,
            stage_report_path=release_publish_stage_report_path,
            target_path=release_publish_target_path,
            expected_stage_payload=release_publish_stage_payload,
            success=False,
            diagnostic_code="package.release.publish.destination-exists",
        )

        release_publish_dry_run_target_path = (
            scan_dir / "package-release-published-dry-run"
        )
        result = run_package_release(
            cglc,
            "--publish-stage",
            release_publish_stage_report_path,
            "--publish-target",
            "local-filesystem",
            "--target-output",
            release_publish_dry_run_target_path,
            "--dry-run",
            json_output=True,
        )
        if result.returncode != 0:
            errors.append(
                "package-release-publish-dry-run-json: expected success, got "
                f"{result.stderr}{result.stdout}".strip()
            )
        if release_publish_dry_run_target_path.exists():
            errors.append(
                "package-release-publish-dry-run-json: expected no target directory"
            )
        expect_release_publish_receipt_json(
            errors,
            root,
            tmp_dir,
            "package-release-publish-dry-run-json",
            result,
            stage_report_path=release_publish_stage_report_path,
            target_path=release_publish_dry_run_target_path,
            expected_stage_payload=release_publish_stage_payload,
            dry_run=True,
            success=True,
        )

        local_target_descriptor_path = scan_dir / "package-release-local-target.json"
        local_descriptor_target_path = scan_dir / "package-release-published-descriptor"
        local_target_descriptor_path.write_text(
            json.dumps(
                {
                    "schemaVersion": 1,
                    "targetKind": "local-filesystem",
                    "enabled": True,
                    "targetPath": local_descriptor_target_path.as_posix(),
                },
                indent=2,
            ),
            encoding="utf-8",
        )
        errors.extend(
            validate_release_publish_target_schema(
                root,
                "package-release-publish-local-target-json",
                local_target_descriptor_path,
            )
        )
        result = run_package_release(
            cglc,
            "--publish-stage",
            release_publish_stage_report_path,
            "--publish-target",
            "local-filesystem",
            "--target-descriptor",
            local_target_descriptor_path,
            json_output=True,
        )
        if result.returncode != 0:
            errors.append(
                "package-release-publish-local-descriptor-json: expected "
                f"success, got {result.stderr}{result.stdout}".strip()
            )
        expect_release_publish_receipt_json(
            errors,
            root,
            tmp_dir,
            "package-release-publish-local-descriptor-json",
            result,
            stage_report_path=release_publish_stage_report_path,
            target_path=local_descriptor_target_path,
            target_descriptor_path=local_target_descriptor_path,
            expected_stage_payload=release_publish_stage_payload,
            expected_target_enabled=True,
            success=True,
        )

        disabled_local_target_descriptor_path = (
            scan_dir / "package-release-local-target-disabled.json"
        )
        disabled_local_descriptor_target_path = (
            scan_dir / "package-release-published-disabled"
        )
        disabled_local_target_descriptor_path.write_text(
            json.dumps(
                {
                    "schemaVersion": 1,
                    "targetKind": "local-filesystem",
                    "enabled": False,
                    "targetPath": disabled_local_descriptor_target_path.as_posix(),
                },
                indent=2,
            ),
            encoding="utf-8",
        )
        errors.extend(
            validate_release_publish_target_schema(
                root,
                "package-release-publish-local-target-disabled-json",
                disabled_local_target_descriptor_path,
            )
        )
        result = run_package_release(
            cglc,
            "--publish-stage",
            release_publish_stage_report_path,
            "--publish-target",
            "local-filesystem",
            "--target-descriptor",
            disabled_local_target_descriptor_path,
            json_output=True,
        )
        if result.returncode == 0:
            errors.append(
                "package-release-publish-local-disabled-json: expected failure"
            )
        if disabled_local_descriptor_target_path.exists():
            errors.append(
                "package-release-publish-local-disabled-json: expected no "
                "target directory"
            )
        expect_release_publish_receipt_json(
            errors,
            root,
            tmp_dir,
            "package-release-publish-local-disabled-json",
            result,
            stage_report_path=release_publish_stage_report_path,
            target_path=disabled_local_descriptor_target_path,
            target_descriptor_path=disabled_local_target_descriptor_path,
            expected_stage_payload=release_publish_stage_payload,
            expected_target_enabled=False,
            success=False,
            diagnostic_code="package.release.publish.target-disabled",
        )

        disabled_local_dry_run_target_path = (
            scan_dir / "package-release-published-disabled-dry-run"
        )
        disabled_local_dry_run_descriptor_path = (
            scan_dir / "package-release-local-target-disabled-dry-run.json"
        )
        disabled_local_dry_run_descriptor_path.write_text(
            json.dumps(
                {
                    "schemaVersion": 1,
                    "targetKind": "local-filesystem",
                    "enabled": False,
                    "targetPath": disabled_local_dry_run_target_path.as_posix(),
                },
                indent=2,
            ),
            encoding="utf-8",
        )
        errors.extend(
            validate_release_publish_target_schema(
                root,
                "package-release-publish-local-target-disabled-dry-run-json",
                disabled_local_dry_run_descriptor_path,
            )
        )
        result = run_package_release(
            cglc,
            "--publish-stage",
            release_publish_stage_report_path,
            "--publish-target",
            "local-filesystem",
            "--target-descriptor",
            disabled_local_dry_run_descriptor_path,
            "--dry-run",
            json_output=True,
        )
        if result.returncode != 0:
            errors.append(
                "package-release-publish-local-disabled-dry-run-json: expected "
                f"success, got {result.stderr}{result.stdout}".strip()
            )
        if disabled_local_dry_run_target_path.exists():
            errors.append(
                "package-release-publish-local-disabled-dry-run-json: expected "
                "no target directory"
            )
        expect_release_publish_receipt_json(
            errors,
            root,
            tmp_dir,
            "package-release-publish-local-disabled-dry-run-json",
            result,
            stage_report_path=release_publish_stage_report_path,
            target_path=disabled_local_dry_run_target_path,
            target_descriptor_path=disabled_local_dry_run_descriptor_path,
            expected_stage_payload=release_publish_stage_payload,
            dry_run=True,
            expected_target_enabled=False,
            success=True,
        )

        gcs_target_descriptor_path = scan_dir / "package-release-gcs-target.json"
        gcs_target_descriptor_path.write_text(
            json.dumps(
                {
                    "schemaVersion": 1,
                    "targetKind": "gcs",
                    "enabled": False,
                    "bucket": "crossgl-release-dry-run",
                    "prefix": "compiler/packages",
                    "credentialsEnv": "GOOGLE_APPLICATION_CREDENTIALS",
                },
                indent=2,
            ),
            encoding="utf-8",
        )
        errors.extend(
            validate_release_publish_target_schema(
                root,
                "package-release-publish-gcs-target-json",
                gcs_target_descriptor_path,
            )
        )
        gcs_upload_manifest_path = (
            scan_dir / "package-release-publish-upload-manifest.json"
        )
        result = run_package_release(
            cglc,
            "--publish-stage",
            release_publish_stage_report_path,
            "--publish-target",
            "gcs",
            "--target-descriptor",
            gcs_target_descriptor_path,
            "--upload-manifest-output",
            gcs_upload_manifest_path,
            "--dry-run",
            json_output=True,
        )
        if result.returncode != 0:
            errors.append(
                "package-release-publish-gcs-dry-run-json: expected success, "
                f"got {result.stderr}{result.stdout}".strip()
            )
        gcs_receipt_payload = expect_release_publish_receipt_json(
            errors,
            root,
            tmp_dir,
            "package-release-publish-gcs-dry-run-json",
            result,
            stage_report_path=release_publish_stage_report_path,
            target_path=None,
            target_uri="gs://crossgl-release-dry-run/compiler/packages",
            target_descriptor_path=gcs_target_descriptor_path,
            expected_stage_payload=release_publish_stage_payload,
            expected_target_kind="gcs",
            dry_run=True,
            expected_target_enabled=False,
            success=True,
        )
        gcs_upload_manifest_payload = expect_release_publish_upload_manifest_json(
            errors,
            root,
            "package-release-publish-gcs-upload-manifest-json",
            gcs_upload_manifest_path,
            gcs_receipt_payload,
            expected_credentials_env="GOOGLE_APPLICATION_CREDENTIALS",
        )
        gcs_upload_preflight_report_path = (
            scan_dir / "package-release-publish-upload-preflight.json"
        )
        result = run_package_release(
            cglc,
            "--upload-manifest",
            gcs_upload_manifest_path,
            "--upload-report-output",
            gcs_upload_preflight_report_path,
            "--dry-run",
            json_output=True,
        )
        if result.returncode != 0:
            errors.append(
                "package-release-publish-gcs-upload-preflight-json: expected "
                f"success, got {result.stderr}{result.stdout}".strip()
            )
        expect_release_publish_upload_preflight_json(
            errors,
            root,
            tmp_dir,
            "package-release-publish-gcs-upload-preflight-json",
            result,
            manifest_path=gcs_upload_manifest_path,
            manifest_payload=gcs_upload_manifest_payload,
            report_path=gcs_upload_preflight_report_path,
            success=True,
        )
        gcs_upload_batch_report_path = (
            scan_dir / "package-release-publish-upload-batch.json"
        )
        gcs_upload_receipt_path = (
            scan_dir / "package-release-publish-upload-receipt.json"
        )
        result = run_package_release(
            cglc,
            "--upload-manifest",
            gcs_upload_manifest_path,
            "--mock-upload",
            "--upload-report-output",
            gcs_upload_batch_report_path,
            "--upload-receipt-output",
            gcs_upload_receipt_path,
            json_output=True,
        )
        if result.returncode != 0:
            errors.append(
                "package-release-publish-gcs-mock-upload-json: expected "
                f"success, got {result.stderr}{result.stdout}".strip()
            )
        expect_release_publish_upload_batch_json(
            errors,
            root,
            tmp_dir,
            "package-release-publish-gcs-mock-upload-json",
            result,
            manifest_path=gcs_upload_manifest_path,
            manifest_payload=gcs_upload_manifest_payload,
            report_path=gcs_upload_batch_report_path,
            upload_mode="mock",
            success=True,
        )
        expect_release_publish_upload_receipt_json(
            errors,
            root,
            "package-release-publish-gcs-mock-upload-receipt-json",
            gcs_upload_receipt_path,
            manifest_path=gcs_upload_manifest_path,
            manifest_payload=gcs_upload_manifest_payload,
            upload_mode="mock",
            provider="mock",
            overwrite=False,
            precondition_kind="",
            precondition_value="",
            success=True,
        )
        fake_gcloud_env, fake_gcloud_log = make_fake_gcloud_env(scan_dir)
        gcs_upload_batch_report_path = (
            scan_dir / "package-release-publish-upload-batch-gcs.json"
        )
        gcs_upload_receipt_path = (
            scan_dir / "package-release-publish-upload-receipt-gcs.json"
        )
        result = run_package_release(
            cglc,
            "--upload-manifest",
            gcs_upload_manifest_path,
            "--gcs-upload",
            "--upload-report-output",
            gcs_upload_batch_report_path,
            "--upload-receipt-output",
            gcs_upload_receipt_path,
            json_output=True,
            env=fake_gcloud_env,
        )
        if result.returncode != 0:
            errors.append(
                "package-release-publish-gcs-upload-json: expected success, "
                f"got {result.stderr}{result.stdout}".strip()
            )
        expect_release_publish_upload_batch_json(
            errors,
            root,
            tmp_dir,
            "package-release-publish-gcs-upload-json",
            result,
            manifest_path=gcs_upload_manifest_path,
            manifest_payload=gcs_upload_manifest_payload,
            report_path=gcs_upload_batch_report_path,
            upload_mode="gcs",
            success=True,
        )
        expect_release_publish_upload_receipt_json(
            errors,
            root,
            "package-release-publish-gcs-upload-receipt-json",
            gcs_upload_receipt_path,
            manifest_path=gcs_upload_manifest_path,
            manifest_payload=gcs_upload_manifest_payload,
            upload_mode="gcs",
            provider="gcs",
            overwrite=False,
            precondition_kind="ifGenerationMatch",
            precondition_value="0",
            generation="1700000000000000",
            metageneration="7",
            crc32c="ImIEBA==",
            md5_hash="1B2M2Y8AsgTpgAmY7PhCfg==",
            success=True,
        )
        fake_gcloud_log_text = (
            fake_gcloud_log.read_text(encoding="utf-8")
            if fake_gcloud_log.exists()
            else ""
        )
        if fake_gcloud_log_count(fake_gcloud_log_text, "storage cp") != len(
            gcs_upload_manifest_payload.get("requests", [])
        ):
            errors.append(
                "package-release-publish-gcs-upload-json: expected fake "
                "gcloud invocation for every upload request"
            )
        if fake_gcloud_log_count(
            fake_gcloud_log_text, "storage objects describe"
        ) != len(gcs_upload_manifest_payload.get("requests", [])):
            errors.append(
                "package-release-publish-gcs-upload-json: expected fake "
                "gcloud object describe invocation for every upload request"
            )
        if "gs://crossgl-release-dry-run/compiler/packages" not in fake_gcloud_log_text:
            errors.append(
                "package-release-publish-gcs-upload-json: expected fake "
                "gcloud log to include destination URI"
            )
        if "--if-generation-match=0" not in fake_gcloud_log_text:
            errors.append(
                "package-release-publish-gcs-upload-json: expected fake "
                "gcloud log to include create-only generation precondition"
            )
        if "--custom-metadata=" not in fake_gcloud_log_text:
            errors.append(
                "package-release-publish-gcs-upload-json: expected fake "
                "gcloud log to include CrossGL custom metadata"
            )
        request_count = len(gcs_upload_manifest_payload.get("requests", []))
        for metadata_key in (
            "crossgl-sha256=",
            "crossgl-size-bytes=",
            "crossgl-upload-fingerprint=",
        ):
            if fake_gcloud_log_text.count(metadata_key) != request_count:
                errors.append(
                    "package-release-publish-gcs-upload-json: expected fake "
                    f"gcloud log to include {metadata_key!r} for every request"
                )
        fake_gcloud_log.unlink(missing_ok=True)
        fake_gcloud_failure_env = dict(fake_gcloud_env)
        fake_gcloud_failure_env["CROSSGL_FAKE_GCLOUD_FAIL_CP"] = "1"
        gcs_upload_failure_report_path = (
            scan_dir / "package-release-publish-upload-batch-gcs-failure.json"
        )
        result = run_package_release(
            cglc,
            "--upload-manifest",
            gcs_upload_manifest_path,
            "--gcs-upload",
            "--upload-report-output",
            gcs_upload_failure_report_path,
            json_output=True,
            env=fake_gcloud_failure_env,
        )
        if result.returncode == 0:
            errors.append(
                "package-release-publish-gcs-upload-failure-json: expected failure"
            )
        gcs_upload_failure_payload = expect_release_publish_upload_batch_json(
            errors,
            root,
            tmp_dir,
            "package-release-publish-gcs-upload-failure-json",
            result,
            manifest_path=gcs_upload_manifest_path,
            manifest_payload=gcs_upload_manifest_payload,
            report_path=gcs_upload_failure_report_path,
            upload_mode="gcs",
            success=False,
            diagnostic_code="package.release.publish.upload-failed",
        )
        gcs_upload_failure_messages = [
            diagnostic.get("message", "")
            for diagnostic in gcs_upload_failure_payload.get("diagnostics", [])
            if isinstance(diagnostic, dict)
        ]
        if not any(
            "captured fake gcloud upload failure" in message
            for message in gcs_upload_failure_messages
        ):
            errors.append(
                "package-release-publish-gcs-upload-failure-json: expected "
                "captured fake gcloud stderr in upload-failed diagnostic"
            )
        fake_gcloud_log.unlink(missing_ok=True)
        gcs_upload_overwrite_batch_report_path = (
            scan_dir / "package-release-publish-upload-batch-gcs-overwrite.json"
        )
        gcs_upload_overwrite_receipt_path = (
            scan_dir / "package-release-publish-upload-receipt-gcs-overwrite.json"
        )
        result = run_package_release(
            cglc,
            "--upload-manifest",
            gcs_upload_manifest_path,
            "--gcs-upload",
            "--gcs-upload-overwrite",
            "--upload-report-output",
            gcs_upload_overwrite_batch_report_path,
            "--upload-receipt-output",
            gcs_upload_overwrite_receipt_path,
            json_output=True,
            env=fake_gcloud_env,
        )
        if result.returncode != 0:
            errors.append(
                "package-release-publish-gcs-upload-overwrite-json: expected "
                f"success, got {result.stderr}{result.stdout}".strip()
            )
        expect_release_publish_upload_batch_json(
            errors,
            root,
            tmp_dir,
            "package-release-publish-gcs-upload-overwrite-json",
            result,
            manifest_path=gcs_upload_manifest_path,
            manifest_payload=gcs_upload_manifest_payload,
            report_path=gcs_upload_overwrite_batch_report_path,
            upload_mode="gcs",
            success=True,
        )
        expect_release_publish_upload_receipt_json(
            errors,
            root,
            "package-release-publish-gcs-upload-overwrite-receipt-json",
            gcs_upload_overwrite_receipt_path,
            manifest_path=gcs_upload_manifest_path,
            manifest_payload=gcs_upload_manifest_payload,
            upload_mode="gcs",
            provider="gcs",
            overwrite=True,
            precondition_kind="",
            precondition_value="",
            generation="1700000000000000",
            metageneration="7",
            crc32c="ImIEBA==",
            md5_hash="1B2M2Y8AsgTpgAmY7PhCfg==",
            success=True,
        )
        fake_gcloud_overwrite_log_text = (
            fake_gcloud_log.read_text(encoding="utf-8")
            if fake_gcloud_log.exists()
            else ""
        )
        if "--if-generation-match=0" in fake_gcloud_overwrite_log_text:
            errors.append(
                "package-release-publish-gcs-upload-overwrite-json: expected "
                "overwrite mode to omit create-only generation precondition"
            )
        if "--custom-metadata=" not in fake_gcloud_overwrite_log_text:
            errors.append(
                "package-release-publish-gcs-upload-overwrite-json: expected "
                "overwrite mode to keep CrossGL custom metadata"
            )
        if fake_gcloud_log_count(
            fake_gcloud_overwrite_log_text, "storage objects describe"
        ) != len(gcs_upload_manifest_payload.get("requests", [])):
            errors.append(
                "package-release-publish-gcs-upload-overwrite-json: expected "
                "fake gcloud object describe invocation for every upload "
                "request"
            )
        missing_credentials_env = dict(fake_gcloud_env)
        missing_credentials_env.pop("GOOGLE_APPLICATION_CREDENTIALS", None)
        gcs_missing_credentials_report_path = (
            scan_dir
            / "package-release-publish-upload-batch-gcs-missing-credentials.json"
        )
        result = run_package_release(
            cglc,
            "--upload-manifest",
            gcs_upload_manifest_path,
            "--gcs-upload",
            "--upload-report-output",
            gcs_missing_credentials_report_path,
            json_output=True,
            env=missing_credentials_env,
        )
        if result.returncode == 0:
            errors.append(
                "package-release-publish-gcs-upload-missing-credentials-json: "
                "expected failure"
            )
        expect_release_publish_upload_batch_json(
            errors,
            root,
            tmp_dir,
            "package-release-publish-gcs-upload-missing-credentials-json",
            result,
            manifest_path=gcs_upload_manifest_path,
            manifest_payload=gcs_upload_manifest_payload,
            report_path=gcs_missing_credentials_report_path,
            upload_mode="gcs",
            success=False,
            diagnostic_code="package.release.publish.upload-failed",
        )
        result = run_package_release(
            cglc,
            "--mock-upload",
            json_output=True,
        )
        if result.returncode == 0:
            errors.append(
                "package-release-publish-mock-upload-missing-manifest: expected failure"
            )
        result = run_package_release(
            cglc,
            "--upload-manifest",
            gcs_upload_manifest_path,
            "--mock-upload",
            "--dry-run",
            json_output=True,
        )
        if result.returncode == 0:
            errors.append(
                "package-release-publish-mock-upload-dry-run-json: expected failure"
            )
        result = run_package_release(
            cglc,
            "--gcs-upload",
            json_output=True,
        )
        if result.returncode == 0:
            errors.append(
                "package-release-publish-gcs-upload-missing-manifest: expected failure"
            )
        result = run_package_release(
            cglc,
            "--upload-manifest",
            gcs_upload_manifest_path,
            "--gcs-upload",
            "--dry-run",
            json_output=True,
        )
        if result.returncode == 0:
            errors.append(
                "package-release-publish-gcs-upload-dry-run-json: expected failure"
            )
        result = run_package_release(
            cglc,
            "--upload-manifest",
            gcs_upload_manifest_path,
            "--mock-upload",
            "--gcs-upload",
            json_output=True,
        )
        if result.returncode == 0:
            errors.append(
                "package-release-publish-gcs-upload-mock-upload-json: expected failure"
            )
        result = run_package_release(
            cglc,
            "--upload-manifest",
            gcs_upload_manifest_path,
            "--gcs-upload-overwrite",
            json_output=True,
        )
        if result.returncode == 0:
            errors.append(
                "package-release-publish-gcs-upload-overwrite-no-upload-json: "
                "expected failure"
            )
        result = run_package_release(
            cglc,
            "--upload-manifest",
            gcs_upload_manifest_path,
            json_output=True,
        )
        if result.returncode == 0:
            errors.append(
                "package-release-publish-upload-manifest-no-mode-json: expected failure"
            )
        missing_upload_manifest_path = (
            scan_dir / "package-release-publish-upload-manifest-missing-source.json"
        )
        missing_upload_preflight_report_path = (
            scan_dir / "package-release-publish-upload-preflight-missing-source.json"
        )
        missing_upload_manifest_payload = dict(gcs_upload_manifest_payload)
        missing_upload_requests = [
            dict(request)
            for request in gcs_upload_manifest_payload.get("requests", [])
            if isinstance(request, dict)
        ]
        if not missing_upload_requests:
            errors.append(
                "package-release-publish-gcs-upload-preflight-missing-source-json: "
                "expected at least one upload request"
            )
        else:
            missing_upload_requests[0]["stagedPath"] = (
                scan_dir / "missing-upload-source.metallib"
            ).as_posix()
        missing_upload_manifest_payload["requests"] = missing_upload_requests
        missing_upload_manifest_path.write_text(
            json.dumps(missing_upload_manifest_payload, indent=2),
            encoding="utf-8",
        )
        errors.extend(
            validate_release_publish_upload_manifest_schema(
                root,
                "package-release-publish-gcs-upload-manifest-missing-source-json",
                missing_upload_manifest_path,
            )
        )
        result = run_package_release(
            cglc,
            "--upload-manifest",
            missing_upload_manifest_path,
            "--upload-report-output",
            missing_upload_preflight_report_path,
            "--dry-run",
            json_output=True,
        )
        if result.returncode == 0:
            errors.append(
                "package-release-publish-gcs-upload-preflight-missing-source-json: "
                "expected failure"
            )
        expect_release_publish_upload_preflight_json(
            errors,
            root,
            tmp_dir,
            "package-release-publish-gcs-upload-preflight-missing-source-json",
            result,
            manifest_path=missing_upload_manifest_path,
            manifest_payload=missing_upload_manifest_payload,
            report_path=missing_upload_preflight_report_path,
            success=False,
            diagnostic_code="package.release.publish.upload-source-missing",
        )
        missing_upload_batch_report_path = (
            scan_dir / "package-release-publish-upload-batch-missing-source.json"
        )
        result = run_package_release(
            cglc,
            "--upload-manifest",
            missing_upload_manifest_path,
            "--mock-upload",
            "--upload-report-output",
            missing_upload_batch_report_path,
            json_output=True,
        )
        if result.returncode == 0:
            errors.append(
                "package-release-publish-gcs-mock-upload-missing-source-json: "
                "expected failure"
            )
        expect_release_publish_upload_batch_json(
            errors,
            root,
            tmp_dir,
            "package-release-publish-gcs-mock-upload-missing-source-json",
            result,
            manifest_path=missing_upload_manifest_path,
            manifest_payload=missing_upload_manifest_payload,
            report_path=missing_upload_batch_report_path,
            upload_mode="mock",
            success=False,
            diagnostic_code="package.release.publish.upload-source-missing",
        )

        result = run_package_release(
            cglc,
            "--publish-stage",
            release_publish_stage_report_path,
            "--publish-target",
            "gcs",
            "--target-descriptor",
            gcs_target_descriptor_path,
            json_output=True,
        )
        if result.returncode == 0:
            errors.append(
                "package-release-publish-gcs-no-dry-run-json: expected failure"
            )
        expect_release_publish_receipt_json(
            errors,
            root,
            tmp_dir,
            "package-release-publish-gcs-no-dry-run-json",
            result,
            stage_report_path=release_publish_stage_report_path,
            target_path=None,
            target_uri="gs://crossgl-release-dry-run/compiler/packages",
            target_descriptor_path=gcs_target_descriptor_path,
            expected_stage_payload=release_publish_stage_payload,
            expected_target_kind="gcs",
            dry_run=True,
            expected_target_enabled=False,
            success=False,
            diagnostic_code="package.release.publish.dry-run-required",
        )

        unsupported_publish_target_path = (
            scan_dir / "package-release-published-unsupported"
        )
        result = run_package_release(
            cglc,
            "--publish-stage",
            release_publish_stage_report_path,
            "--publish-target",
            "gcs",
            "--target-output",
            unsupported_publish_target_path,
            json_output=True,
        )
        if result.returncode == 0:
            errors.append("package-release-publish-unsupported-json: expected failure")
        if unsupported_publish_target_path.exists():
            errors.append(
                "package-release-publish-unsupported-json: expected no target directory"
            )
        expect_release_publish_receipt_json(
            errors,
            root,
            tmp_dir,
            "package-release-publish-unsupported-json",
            result,
            stage_report_path=release_publish_stage_report_path,
            target_path=unsupported_publish_target_path,
            target_uri="",
            expected_stage_payload=release_publish_stage_payload,
            expected_target_kind="gcs",
            dry_run=True,
            success=False,
            diagnostic_code="package.release.publish.target-descriptor-required",
        )

        release_publish_stage_slash_path = scan_dir / "package-release-stage-slash"
        release_publish_stage_slash_arg = (
            release_publish_stage_slash_path.as_posix() + "/"
        )
        result = run_package_release(
            cglc,
            "--stage-publish",
            release_publish_plan_path,
            "--stage-output",
            release_publish_stage_slash_arg,
            json_output=True,
        )
        if result.returncode != 0:
            errors.append(
                "package-release-publish-stage-trailing-slash-json: expected "
                f"success, got {result.stderr}{result.stdout}".strip()
            )
        expect_release_publish_stage_json(
            errors,
            root,
            tmp_dir,
            "package-release-publish-stage-trailing-slash-json",
            result,
            plan_path=release_publish_plan_path,
            stage_path=release_publish_stage_slash_path,
            expected_stage_path_json=release_publish_stage_slash_arg,
            expected_plan_payload=release_publish_plan_payload,
            success=True,
        )

        tampered_release_publish_plan_path = (
            scan_dir / "package-release-publish-plan-source-tampered.json"
        )
        tampered_release_publish_plan_payload = json.loads(
            release_publish_plan_path.read_text(encoding="utf-8")
        )
        tampered_plan_artifact = tampered_release_publish_plan_payload["artifacts"][0]
        tampered_plan_artifact["sha256"] = (
            "f" * 64 if tampered_plan_artifact["sha256"] != "f" * 64 else "0" * 64
        )
        for package in tampered_release_publish_plan_payload["packages"]:
            for artifact in package["artifacts"]:
                if (
                    artifact["destinationPath"]
                    == tampered_plan_artifact["destinationPath"]
                ):
                    artifact["sha256"] = tampered_plan_artifact["sha256"]
        tampered_release_publish_plan_path.write_text(
            json.dumps(tampered_release_publish_plan_payload, indent=2) + "\n",
            encoding="utf-8",
        )
        tampered_release_publish_stage_path = (
            scan_dir / "package-release-stage-tampered"
        )
        result = run_package_release(
            cglc,
            "--stage-publish",
            tampered_release_publish_plan_path,
            "--stage-output",
            tampered_release_publish_stage_path,
            json_output=True,
        )
        if result.returncode == 0:
            errors.append(
                "package-release-publish-stage-tampered-json: expected failure"
            )
        if tampered_release_publish_stage_path.exists():
            errors.append(
                "package-release-publish-stage-tampered-json: expected no stage "
                "directory"
            )
        expect_release_publish_stage_json(
            errors,
            root,
            tmp_dir,
            "package-release-publish-stage-tampered-json",
            result,
            plan_path=tampered_release_publish_plan_path,
            stage_path=tampered_release_publish_stage_path,
            expected_plan_payload=tampered_release_publish_plan_payload,
            success=False,
            diagnostic_code="package.release.publish.source-hash-mismatch",
        )

        tampered_release_bundle_path = scan_dir / "package-release-bundle-tampered.json"
        tampered_release_bundle_payload = json.loads(
            release_bundle_path.read_text(encoding="utf-8")
        )
        tampered_artifact = next(
            artifact
            for package in tampered_release_bundle_payload["packages"]
            for artifact in package["artifacts"]
            if artifact["exists"]
        )
        tampered_artifact["sha256"] = (
            "f" * 64 if tampered_artifact["sha256"] != "f" * 64 else "0" * 64
        )
        tampered_release_bundle_path.write_text(
            json.dumps(tampered_release_bundle_payload, indent=2) + "\n",
            encoding="utf-8",
        )
        result = run_package_release(
            cglc,
            "--verify-bundle",
            tampered_release_bundle_path,
            json_output=True,
        )
        if result.returncode == 0:
            errors.append(
                "package-release-bundle-verify-tampered-json: "
                "expected hash mismatch failure"
            )
        expect_release_bundle_verification_json(
            errors,
            root,
            tmp_dir,
            "package-release-bundle-verify-tampered-json",
            result,
            bundle_path=tampered_release_bundle_path,
            success=False,
            release_eligible=True,
            status="eligible",
            expected_bundle_payload=tampered_release_bundle_payload,
            diagnostic_code="package.release.bundle.artifact-hash-mismatch",
        )
        tampered_publish_plan_path = (
            scan_dir / "package-release-publish-plan-tampered.json"
        )
        result = run_package_release(
            cglc,
            "--plan-publish",
            tampered_release_bundle_path,
            "--plan-output",
            tampered_publish_plan_path,
            json_output=True,
        )
        if result.returncode == 0:
            errors.append(
                "package-release-publish-plan-tampered-json: expected failure"
            )
        if tampered_publish_plan_path.exists():
            errors.append(
                "package-release-publish-plan-tampered-json: expected no plan file"
            )
        if "package.release.bundle.artifact-hash-mismatch" not in result.stderr:
            errors.append(
                "package-release-publish-plan-tampered-json: expected hash "
                "mismatch diagnostic"
            )

        verification_summary_text_path = (
            scan_dir / "package-set-verification-summary-text.json"
        )
        result = run_maintain_verification_batch(
            cglc,
            verification_batch_path,
            "--summary-output",
            verification_summary_text_path,
        )
        errors.extend(
            expect_success(
                result,
                "package-maintain-verify-set-batch-text",
                "exported package maintenance set verification batch summary",
            )
        )

        nested_set_path = scan_dir / "nested-package-set.json"
        nested_set_path.write_text(
            json.dumps(
                {
                    "schemaVersion": 1,
                    "packages": ["nested/nested-package.cglb"],
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        errors.extend(
            validate_maintenance_set_schema(
                root,
                "package-maintain-export-verify-set-batch-nested-set-schema",
                nested_set_path,
            )
        )
        exported_verification_batch_path = (
            scan_dir / "exported-package-set-verification-batch.json"
        )
        result = run_maintain_export_verification_batch(
            cglc,
            exported_verification_batch_path,
            "--verification",
            scan_dir,
            exported_set_path,
            "--verification",
            nested_scan_dir,
            nested_set_path,
            json_output=True,
        )
        if result.returncode != 0:
            errors.append(
                "package-maintain-export-verify-set-batch-json: expected "
                f"success, got {result.stderr}{result.stdout}".strip()
            )
        if result.stderr:
            errors.append(
                "package-maintain-export-verify-set-batch-json: expected no diagnostics"
            )
        expect_package_set_verification_batch_document(
            errors,
            root,
            "package-maintain-export-verify-set-batch-json",
            exported_verification_batch_path,
            expected_verifications=(
                {
                    "root_path": ".",
                    "set_path": "exported-package-set.json",
                },
                {
                    "root_path": "nested",
                    "set_path": "nested-package-set.json",
                },
            ),
            stdout_json=result.stdout,
        )
        expected_exported_nested_verification = {
            "scan_root": nested_scan_dir,
            "set_path": nested_set_path,
            "success": True,
            "matches": True,
            "scanned_packages": (nested_scan_package,),
            "set_packages": (nested_scan_package,),
        }
        result = run_maintain_verification_batch(
            cglc,
            exported_verification_batch_path,
            json_output=True,
        )
        if result.returncode != 0:
            errors.append(
                "package-maintain-export-verify-set-batch-rerun-json: "
                f"expected success, got {result.stderr}{result.stdout}".strip()
            )
        expect_package_set_verification_batch_json(
            errors,
            root,
            tmp_dir,
            "package-maintain-export-verify-set-batch-rerun-json",
            result,
            batch_path=exported_verification_batch_path,
            success=True,
            matches=True,
            expected_verifications=(
                expected_matching_verification,
                expected_exported_nested_verification,
            ),
        )

        duplicate_exported_verification_batch_path = (
            scan_dir / "duplicate-package-set-verification-batch.json"
        )
        result = run_maintain_export_verification_batch(
            cglc,
            duplicate_exported_verification_batch_path,
            "--verification",
            scan_dir,
            exported_set_path,
            "--verification",
            scan_dir,
            exported_set_path,
        )
        errors.extend(
            expect_failure(
                result,
                "package-maintain-export-verify-set-batch-duplicate",
                "duplicate",
            )
        )

        result = run_maintain_export_verification_batch(
            cglc,
            exported_verification_batch_path,
            "--verification",
            scan_dir,
            exported_set_path,
            "--apply",
        )
        errors.extend(
            expect_failure(
                result,
                "package-maintain-export-verify-set-batch-apply-conflict",
                "does not accept --dry-run, --apply",
            )
        )

        stale_set_path = scan_dir / "stale-package-set.json"
        scan_extra = scan_dir / "scan-extra.cglb"
        stale_set_path.write_text(
            json.dumps(
                {
                    "schemaVersion": 1,
                    "packages": ["scan-a.cglb", "scan-extra.cglb"],
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        result = run_maintain_scan(
            cglc,
            scan_dir,
            "--verify-package-set",
            stale_set_path,
            json_output=True,
        )
        if result.returncode == 0:
            errors.append(
                "package-maintain-scan-verify-set-mismatch-json: "
                "expected mismatch failure"
            )
        expect_package_set_verification_json(
            errors,
            root,
            tmp_dir,
            "package-maintain-scan-verify-set-mismatch-json",
            result,
            scan_root=scan_dir,
            set_path=stale_set_path,
            success=False,
            matches=False,
            scanned_packages=(scan_package, scan_missing),
            set_packages=(scan_package, scan_extra),
            missing_from_set=(scan_missing,),
            extra_in_set=(scan_extra,),
            diagnostic_code="package.maintain.set.verify.mismatch",
        )

        mixed_verification_batch_path = (
            scan_dir / "mixed-package-set-verification-batch.json"
        )
        mixed_verification_batch_path.write_text(
            json.dumps(
                {
                    "schemaVersion": 1,
                    "verifications": [
                        {
                            "rootPath": ".",
                            "setPath": "exported-package-set.json",
                        },
                        {
                            "rootPath": ".",
                            "setPath": "stale-package-set.json",
                        },
                    ],
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        errors.extend(
            validate_maintenance_set_verification_batch_schema(
                root,
                "package-maintain-verify-set-batch-mixed-schema",
                mixed_verification_batch_path,
            )
        )
        expected_mismatching_verification = {
            "scan_root": scan_dir,
            "set_path": stale_set_path,
            "success": False,
            "matches": False,
            "scanned_packages": (scan_package, scan_missing),
            "set_packages": (scan_package, scan_extra),
            "missing_from_set": (scan_missing,),
            "extra_in_set": (scan_extra,),
            "diagnostic_code": "package.maintain.set.verify.mismatch",
        }
        mixed_summary_path = scan_dir / "mixed-package-set-verification-summary.json"
        result = run_maintain_verification_batch(
            cglc,
            mixed_verification_batch_path,
            "--summary-output",
            mixed_summary_path,
            json_output=True,
        )
        if result.returncode == 0:
            errors.append(
                "package-maintain-verify-set-batch-mixed-json: "
                "expected mismatch failure"
            )
        expect_package_set_verification_batch_json(
            errors,
            root,
            tmp_dir,
            "package-maintain-verify-set-batch-mixed-json",
            result,
            batch_path=mixed_verification_batch_path,
            success=False,
            matches=False,
            expected_verifications=(
                expected_matching_verification,
                expected_mismatching_verification,
            ),
            diagnostic_code="package.maintain.set.verify.mismatch",
        )
        expect_package_set_verification_batch_summary_file(
            errors,
            root,
            "package-maintain-verify-set-batch-mixed-summary-json",
            mixed_summary_path,
            batch_path=mixed_verification_batch_path,
            success=False,
            matches=False,
            expected_verifications=(
                expected_matching_verification,
                expected_mismatching_verification,
            ),
            diagnostic_code="package.maintain.set.verify.mismatch",
        )
        mixed_release_manifest_path = (
            scan_dir / "mixed-package-release-promotion-manifest.json"
        )
        mixed_release_bundle_path = scan_dir / "mixed-package-release-bundle.json"
        result = run_package_release(
            cglc,
            "--promotion-summary",
            mixed_summary_path,
            "--manifest-output",
            mixed_release_manifest_path,
            "--bundle-output",
            mixed_release_bundle_path,
            json_output=True,
        )
        if result.returncode == 0:
            errors.append(
                "package-release-promotion-manifest-blocked-json: "
                "expected blocked release failure"
            )
        if result.stderr:
            errors.append(
                "package-release-promotion-manifest-blocked-json: expected no "
                "diagnostics"
            )
        expect_release_promotion_manifest_file(
            errors,
            root,
            "package-release-promotion-manifest-blocked-json",
            mixed_release_manifest_path,
            summary_path=mixed_summary_path,
            batch_path=mixed_verification_batch_path,
            release_eligible=False,
            stdout_json=result.stdout,
            expected_blocker_codes=(
                "error-diagnostics",
                "extra-in-set",
                "missing-from-set",
                "verification-summary-failed",
                "verification-summary-mismatch",
            ),
            expected_package_paths=(),
        )
        mixed_release_bundle_payload = expect_release_bundle_file(
            errors,
            root,
            "package-release-bundle-blocked-json",
            mixed_release_bundle_path,
            promotion_manifest_path=mixed_release_manifest_path,
            summary_path=mixed_summary_path,
            batch_path=mixed_verification_batch_path,
            release_eligible=False,
            expected_blocker_codes=(
                "error-diagnostics",
                "extra-in-set",
                "missing-from-set",
                "verification-summary-failed",
                "verification-summary-mismatch",
            ),
            expected_package_paths=(),
        )
        result = run_package_release(
            cglc,
            "--verify-bundle",
            mixed_release_bundle_path,
            json_output=True,
        )
        if result.returncode == 0:
            errors.append(
                "package-release-bundle-verify-blocked-json: "
                "expected blocked bundle failure"
            )
        expect_release_bundle_verification_json(
            errors,
            root,
            tmp_dir,
            "package-release-bundle-verify-blocked-json",
            result,
            bundle_path=mixed_release_bundle_path,
            success=False,
            release_eligible=False,
            status="blocked",
            expected_bundle_payload=mixed_release_bundle_payload,
        )
        blocked_publish_plan_path = scan_dir / "mixed-package-release-publish-plan.json"
        result = run_package_release(
            cglc,
            "--plan-publish",
            mixed_release_bundle_path,
            "--plan-output",
            blocked_publish_plan_path,
            json_output=True,
        )
        if result.returncode == 0:
            errors.append("package-release-publish-plan-blocked-json: expected failure")
        if blocked_publish_plan_path.exists():
            errors.append(
                "package-release-publish-plan-blocked-json: expected no plan file"
            )
        if "package.release.publish.bundle-not-eligible" not in result.stderr:
            errors.append(
                "package-release-publish-plan-blocked-json: expected publish "
                "gate diagnostic"
            )

        empty_verification_batch_path = (
            scan_dir / "empty-package-set-verification-batch.json"
        )
        empty_verification_batch_path.write_text(
            json.dumps(
                {
                    "schemaVersion": 1,
                    "verifications": [],
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        result = run_maintain_verification_batch(
            cglc,
            empty_verification_batch_path,
            json_output=True,
        )
        if result.returncode == 0:
            errors.append(
                "package-maintain-verify-set-batch-empty-json: "
                "expected invalid batch failure"
            )
        expect_package_set_verification_batch_json(
            errors,
            root,
            tmp_dir,
            "package-maintain-verify-set-batch-empty-json",
            result,
            batch_path=empty_verification_batch_path,
            success=False,
            matches=False,
            expected_verifications=(),
            diagnostic_code="package.maintain.set.verify.batch.empty-verifications",
        )

        result = run_maintain_scan(
            cglc,
            scan_dir,
            "--export-package-set",
            exported_set_path,
            "--apply",
        )
        errors.extend(
            expect_failure(
                result,
                "package-maintain-scan-export-set-apply-conflict",
                "does not accept --dry-run, --apply",
            )
        )

        result = run_maintain_scan(
            cglc,
            scan_dir,
            "--verify-package-set",
            exported_set_path,
            "--apply",
        )
        errors.extend(
            expect_failure(
                result,
                "package-maintain-scan-verify-set-apply-conflict",
                "does not accept --dry-run, --apply",
            )
        )

        result = run_maintain_verification_batch(
            cglc,
            verification_batch_path,
            "--apply",
        )
        errors.extend(
            expect_failure(
                result,
                "package-maintain-verify-set-batch-apply-conflict",
                "does not accept --dry-run, --apply",
            )
        )

        result = run_package_release(
            cglc,
            "--promotion-summary",
            verification_summary_path,
            "--manifest-output",
            release_manifest_path,
            "--apply",
        )
        errors.extend(
            expect_failure(
                result,
                "package-release-promotion-apply-conflict",
                "accepts only --promotion-summary",
            )
        )

        result = run_package_release(
            cglc,
            "--plan-publish",
            release_bundle_path,
        )
        errors.extend(
            expect_failure(
                result,
                "package-release-publish-plan-missing-output",
                "requires --plan-output",
            )
        )

        result = run_package_release(
            cglc,
            "--stage-publish",
            release_publish_plan_path,
        )
        errors.extend(
            expect_failure(
                result,
                "package-release-publish-stage-missing-output",
                "requires --stage-output",
            )
        )

        result = run_package_release(
            cglc,
            "--stage-output",
            scan_dir / "invalid-package-release-stage",
        )
        errors.extend(
            expect_failure(
                result,
                "package-release-publish-stage-missing-input",
                "requires --stage-publish",
            )
        )

        result = run_package_release(
            cglc,
            "--publish-stage",
            scan_dir / "package-release-publish-stage.json",
            "--target-output",
            scan_dir / "invalid-package-release-published",
        )
        errors.extend(
            expect_failure(
                result,
                "package-release-publish-missing-target",
                "requires --publish-target",
            )
        )

        result = run_package_release(
            cglc,
            "--publish-stage",
            scan_dir / "package-release-publish-stage.json",
            "--publish-target",
            "local-filesystem",
        )
        errors.extend(
            expect_failure(
                result,
                "package-release-publish-missing-output",
                "requires --target-output",
            )
        )

        result = run_package_release(
            cglc,
            "--publish-target",
            "local-filesystem",
            "--target-output",
            scan_dir / "invalid-package-release-published",
        )
        errors.extend(
            expect_failure(
                result,
                "package-release-publish-target-without-stage",
                "require --publish-stage",
            )
        )

        result = run_package_release(
            cglc,
            "--plan-output",
            scan_dir / "invalid-package-release-publish-plan.json",
        )
        errors.extend(
            expect_failure(
                result,
                "package-release-publish-plan-missing-input",
                "requires --plan-publish",
            )
        )

        result = run_package_release(
            cglc,
            "--publish-stage",
            scan_dir / "package-release-publish-stage.json",
            "--publish-target",
            "local-filesystem",
            "--target-output",
            scan_dir / "invalid-package-release-published",
            "--apply",
        )
        errors.extend(
            expect_failure(
                result,
                "package-release-publish-apply-conflict",
                "accepts only --publish-stage",
            )
        )

        result = run_package_release(
            cglc,
            "--stage-publish",
            release_publish_plan_path,
            "--stage-output",
            scan_dir / "invalid-package-release-stage",
            "--apply",
        )
        errors.extend(
            expect_failure(
                result,
                "package-release-publish-stage-apply-conflict",
                "accepts only --stage-publish",
            )
        )

        result = run_package_release(
            cglc,
            "--plan-publish",
            release_bundle_path,
            "--plan-output",
            scan_dir / "invalid-package-release-publish-plan.json",
            "--apply",
        )
        errors.extend(
            expect_failure(
                result,
                "package-release-publish-plan-apply-conflict",
                "accepts only --plan-publish",
            )
        )

        invalid_release_summary_path = scan_dir / "invalid-release-summary.json"
        invalid_release_summary_path.write_text(
            json.dumps(
                {
                    "schemaVersion": 2,
                    "batchPath": "package-set-verification-batch.json",
                    "success": True,
                    "matches": True,
                    "releaseEligible": True,
                    "verificationCount": 1,
                    "matchedCount": 1,
                    "mismatchedCount": 0,
                    "failedCount": 0,
                    "scannedPackageCount": 2,
                    "setPackageCount": 2,
                    "missingFromSetCount": 0,
                    "extraInSetCount": 0,
                    "diagnosticCounts": {"note": 0, "warning": 0, "error": 0},
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        result = run_package_release(
            cglc,
            "--promotion-summary",
            invalid_release_summary_path,
            "--manifest-output",
            scan_dir / "invalid-package-release-promotion-manifest.json",
        )
        errors.extend(
            expect_failure(
                result,
                "package-release-promotion-invalid-summary",
                "schemaVersion must be 1",
            )
        )

        result = run_maintain_scan(
            cglc,
            scan_dir,
            "--summary-output",
            verification_summary_path,
        )
        errors.extend(
            expect_failure(
                result,
                "package-maintain-summary-output-requires-batch",
                "--summary-output requires --verify-package-set-batch",
            )
        )

        result = run_maintain_scan(
            cglc,
            scan_dir,
            "--verify-package-set-batch",
            verification_batch_path,
        )
        errors.extend(
            expect_failure(
                result,
                "package-maintain-verify-set-batch-scan-conflict",
                "accepts exactly one of a package path, --scan, --package-set",
            )
        )

        result = run_maintain(
            cglc,
            scan_package,
            "--verify-package-set-batch",
            verification_batch_path,
        )
        errors.extend(
            expect_failure(
                result,
                "package-maintain-verify-set-batch-package-conflict",
                "accepts exactly one of a package path, --scan, --package-set",
            )
        )

        result = run_maintain_scan(
            cglc,
            scan_dir,
            "--export-package-set",
            exported_set_path,
            "--verify-package-set",
            exported_set_path,
        )
        errors.extend(
            expect_failure(
                result,
                "package-maintain-scan-export-verify-conflict",
                "accepts only one of --export-package-set or --verify-package-set",
            )
        )

        result = run_maintain(
            cglc,
            scan_package,
            "--verify-package-set",
            exported_set_path,
        )
        errors.extend(
            expect_failure(
                result,
                "package-maintain-verify-set-requires-scan",
                "--verify-package-set requires --scan",
            )
        )

        result = subprocess.run(
            [
                str(cglc),
                "package",
                "maintain",
                "--verify-package-set",
                str(exported_set_path),
            ],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        errors.extend(
            expect_failure(
                result,
                "package-maintain-verify-set-requires-scan-no-package",
                "--verify-package-set requires --scan",
            )
        )

        result = run_maintain(cglc, scan_package, "--scan", scan_dir)
        errors.extend(
            expect_failure(
                result,
                "package-maintain-scan-package-conflict",
                "accepts exactly one of a package path, --scan, --package-set",
            )
        )

        expected_scan_apply_packages = tuple(
            {
                **package,
                "expected_candidates": tuple(
                    {**candidate, "action": "discarded"}
                    for candidate in package["expected_candidates"]
                ),
            }
            for package in expected_scan_packages
        )
        result = run_maintain_scan(
            cglc,
            scan_dir,
            "--keep-last",
            "0",
            "--apply",
            json_output=True,
        )
        if result.returncode != 0:
            errors.append(
                "package-maintain-scan-apply-json: expected success, got "
                f"{result.stderr}{result.stdout}".strip()
            )
        expect_maintenance_report_json(
            errors,
            root,
            tmp_dir,
            "package-maintain-scan-apply-json",
            result,
            scan_root=scan_dir,
            dry_run=False,
            keep_last=0,
            expected_packages=expected_scan_apply_packages,
        )
        for stale_path in (scan_previous, scan_staging, scan_missing_previous):
            if stale_path.exists():
                errors.append(
                    "package-maintain-scan-apply-json: expected stale sidecar "
                    f"to be discarded: {stale_path.as_posix()}"
                )
        if not scan_missing_staging.is_dir():
            errors.append(
                "package-maintain-scan-apply-json: expected missing-output "
                "staging sidecar to remain recoverable"
            )

        set_dir = tmp_dir / "maintain-set"
        set_dir.mkdir()
        set_package, _source, _manifest = make_package(set_dir, "set-a")
        set_previous_package, _source, _manifest = make_package(
            set_dir,
            "set-a-previous",
        )
        set_staging_package, _source, _manifest = make_package(
            set_dir,
            "set-a-staging",
        )
        set_missing_previous_package, _source, _manifest = make_package(
            set_dir,
            "set-missing-previous",
        )
        set_missing_staging_package, _source, _manifest = make_package(
            set_dir,
            "set-missing-staging",
        )
        set_previous = set_dir / ".set-a.cglb.previous-100-0"
        set_staging = set_dir / ".set-a.cglb.staging-200-0"
        set_missing = set_dir / "set-missing.cglb"
        set_missing_previous = set_dir / ".set-missing.cglb.previous-300-0"
        set_missing_staging = set_dir / ".set-missing.cglb.staging-400-0"
        set_previous_package.rename(set_previous)
        set_staging_package.rename(set_staging)
        set_missing_previous_package.rename(set_missing_previous)
        set_missing_staging_package.rename(set_missing_staging)
        package_set_path = set_dir / "package-set.json"
        package_set_path.write_text(
            json.dumps(
                {
                    "schemaVersion": 1,
                    "packages": ["set-a.cglb", "set-missing.cglb"],
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        errors.extend(
            validate_maintenance_set_schema(
                root,
                "package-maintain-set-schema",
                package_set_path,
            )
        )
        expected_set_packages = (
            {
                "package": set_package,
                "requested_exists": True,
                "expected_candidates": (
                    expected_cleanup_candidate(
                        set_previous,
                        "previous",
                        "100",
                        0,
                        directory=True,
                        reason="previous-backup",
                        action="would-discard",
                    ),
                    expected_cleanup_candidate(
                        set_staging,
                        "staging",
                        "200",
                        0,
                        directory=True,
                        reason="staging-with-published-output",
                        action="would-discard",
                    ),
                ),
            },
            {
                "package": set_missing,
                "requested_exists": False,
                "expected_candidates": (
                    expected_cleanup_candidate(
                        set_missing_previous,
                        "previous",
                        "300",
                        0,
                        directory=True,
                        reason="previous-backup",
                        action="would-discard",
                    ),
                ),
            },
        )
        result = run_maintain_package_set(
            cglc,
            package_set_path,
            "--keep-last",
            "0",
            json_output=True,
        )
        if result.returncode != 0:
            errors.append(
                "package-maintain-set-json: expected success, got "
                f"{result.stderr}{result.stdout}".strip()
            )
        expect_maintenance_report_json(
            errors,
            root,
            tmp_dir,
            "package-maintain-set-json",
            result,
            set_path=package_set_path,
            dry_run=True,
            keep_last=0,
            expected_packages=expected_set_packages,
        )

        result = run_maintain_package_set(cglc, package_set_path)
        errors.extend(
            expect_success(
                result,
                "package-maintain-set-text",
                "package maintenance set dry run",
            )
        )

        result = run_maintain(cglc, set_package, "--package-set", package_set_path)
        errors.extend(
            expect_failure(
                result,
                "package-maintain-set-package-conflict",
                "accepts exactly one of a package path, --scan, --package-set",
            )
        )

        result = run_recover(cglc, set_package, "--package-set", package_set_path)
        errors.extend(
            expect_failure(
                result,
                "package-recover-set-conflict",
                "package recover does not accept --package-set",
            )
        )

        duplicate_set_path = set_dir / "package-set-duplicate.json"
        duplicate_set_path.write_text(
            json.dumps(
                {
                    "schemaVersion": 1,
                    "packages": ["set-a.cglb", "./set-a.cglb"],
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        result = run_maintain_package_set(cglc, duplicate_set_path)
        errors.extend(
            expect_failure(
                result,
                "package-maintain-set-duplicate",
                "package.maintain.set.duplicate-package",
            )
        )

        expected_set_apply_packages = tuple(
            {
                **package,
                "expected_candidates": tuple(
                    {**candidate, "action": "discarded"}
                    for candidate in package["expected_candidates"]
                ),
            }
            for package in expected_set_packages
        )
        result = run_maintain_package_set(
            cglc,
            package_set_path,
            "--keep-last",
            "0",
            "--apply",
            json_output=True,
        )
        if result.returncode != 0:
            errors.append(
                "package-maintain-set-apply-json: expected success, got "
                f"{result.stderr}{result.stdout}".strip()
            )
        expect_maintenance_report_json(
            errors,
            root,
            tmp_dir,
            "package-maintain-set-apply-json",
            result,
            set_path=package_set_path,
            dry_run=False,
            keep_last=0,
            expected_packages=expected_set_apply_packages,
        )
        for stale_path in (set_previous, set_staging, set_missing_previous):
            if stale_path.exists():
                errors.append(
                    "package-maintain-set-apply-json: expected stale sidecar "
                    f"to be discarded: {stale_path.as_posix()}"
                )
        if not set_missing_staging.is_dir():
            errors.append(
                "package-maintain-set-apply-json: expected missing-output "
                "staging sidecar to remain recoverable"
            )

        result = run_maintain_scan(cglc, scan_dir / "notes.txt")
        errors.extend(
            expect_failure(
                result,
                "package-maintain-scan-invalid-root",
                "package.maintain.scan.invalid-root",
            )
        )

        result = run_recover(
            cglc,
            missing_requested,
            "--discard-stale",
            "--apply",
            json_output=True,
        )
        if result.returncode != 0:
            errors.append(
                "recover-discard-stale-missing-json: expected success, got "
                f"{result.stderr}{result.stdout}".strip()
            )
        expect_stale_cleanup_json(
            errors,
            root,
            tmp_dir,
            "recover-discard-stale-missing-json",
            result,
            queried=missing_requested,
            requested=missing_requested,
            dry_run=False,
            requested_exists=False,
            expected_candidates=(),
        )
        if not missing_sidecar.is_dir():
            errors.append(
                "recover-discard-stale-missing-json: expected recoverable "
                "staging sidecar to survive when output is missing"
            )

        result = run_recover(
            cglc,
            list_package,
            "--discard-stale",
            "--dry-run",
            "--apply",
        )
        errors.extend(
            expect_failure(
                result,
                "recover-discard-stale-mode-conflict",
                "accepts only one of --dry-run or --apply",
            )
        )

        result = run_recover(cglc, list_package, "--discard-stale", "--promote")
        errors.extend(
            expect_failure(
                result,
                "recover-discard-stale-action-conflict",
                "package recover --discard-stale cannot be combined",
            )
        )

        result = run_recover(cglc, list_package, "--list", "--keep-last", "1")
        errors.extend(
            expect_failure(
                result,
                "recover-list-retention-conflict",
                "package recover --list does not accept",
            )
        )

        retention_package, _source, _manifest = make_package(
            tmp_dir,
            "recover-retention",
        )
        retention_previous_old_package, _source, _manifest = make_package(
            tmp_dir,
            "recover-retention-previous-old",
        )
        retention_staging_package, _source, _manifest = make_package(
            tmp_dir,
            "recover-retention-staging",
        )
        retention_previous_new_package, _source, _manifest = make_package(
            tmp_dir,
            "recover-retention-previous-new",
        )
        retention_previous_old = tmp_dir / ".recover-retention.cglb.previous-100-0"
        retention_staging = tmp_dir / ".recover-retention.cglb.staging-200-0"
        retention_previous_new = tmp_dir / ".recover-retention.cglb.previous-300-0"
        retention_file = tmp_dir / ".recover-retention.cglb.staging-400-0"
        retention_previous_old_package.rename(retention_previous_old)
        retention_staging_package.rename(retention_staging)
        retention_previous_new_package.rename(retention_previous_new)
        retention_file.write_text("not a package directory\n", encoding="utf-8")
        expected_retention_dry_run = (
            expected_cleanup_candidate(
                retention_previous_old,
                "previous",
                "100",
                0,
                directory=True,
                reason="previous-backup",
                action="would-discard",
            ),
            expected_cleanup_candidate(
                retention_file,
                "staging",
                "400",
                0,
                directory=False,
                reason="not-directory",
                action="would-discard",
            ),
        )
        expected_retained = (
            expected_cleanup_candidate(
                retention_previous_new,
                "previous",
                "300",
                0,
                directory=True,
                reason="previous-backup",
                action="kept",
                retained_by="keep-last",
            ),
            expected_cleanup_candidate(
                retention_staging,
                "staging",
                "200",
                0,
                directory=True,
                reason="staging-with-published-output",
                action="kept",
                retained_by="keep-last",
            ),
        )
        result = run_recover(
            cglc,
            retention_package,
            "--discard-stale",
            "--keep-last",
            "2",
            json_output=True,
        )
        if result.returncode != 0:
            errors.append(
                "recover-discard-stale-keep-last-json: expected success, got "
                f"{result.stderr}{result.stdout}".strip()
            )
        expect_stale_cleanup_json(
            errors,
            root,
            tmp_dir,
            "recover-discard-stale-keep-last-json",
            result,
            queried=retention_package,
            requested=retention_package,
            dry_run=True,
            requested_exists=True,
            keep_last=2,
            expected_candidates=expected_retention_dry_run,
            expected_retained=expected_retained,
        )
        for retained_path in (retention_previous_new, retention_staging):
            if not retained_path.is_dir():
                errors.append(
                    "recover-discard-stale-keep-last-json: expected retained "
                    f"sidecar to survive dry run: {retained_path.as_posix()}"
                )

        result = run_recover(
            cglc,
            retention_package,
            "--discard-stale",
            "--keep-last",
            "not-a-number",
        )
        errors.extend(
            expect_failure(
                result,
                "recover-discard-stale-keep-last-invalid",
                "expected non-negative integer for --keep-last",
            )
        )

        expected_retention_applied = tuple(
            {
                **candidate,
                "action": "discarded",
            }
            for candidate in expected_retention_dry_run
        )
        result = run_recover(
            cglc,
            retention_package,
            "--discard-stale",
            "--keep-last",
            "2",
            "--apply",
            json_output=True,
        )
        if result.returncode != 0:
            errors.append(
                "recover-discard-stale-keep-last-apply-json: expected success, got "
                f"{result.stderr}{result.stdout}".strip()
            )
        expect_stale_cleanup_json(
            errors,
            root,
            tmp_dir,
            "recover-discard-stale-keep-last-apply-json",
            result,
            queried=retention_package,
            requested=retention_package,
            dry_run=False,
            requested_exists=True,
            keep_last=2,
            expected_candidates=expected_retention_applied,
            expected_retained=expected_retained,
        )
        for discarded_path in (retention_previous_old, retention_file):
            if discarded_path.exists():
                errors.append(
                    "recover-discard-stale-keep-last-apply-json: expected "
                    f"discarded path to be removed: {discarded_path.as_posix()}"
                )
        for retained_path in (retention_previous_new, retention_staging):
            if not retained_path.is_dir():
                errors.append(
                    "recover-discard-stale-keep-last-apply-json: expected "
                    f"retained sidecar to survive apply: {retained_path.as_posix()}"
                )

        age_package, _source, _manifest = make_package(tmp_dir, "recover-age")
        age_previous_old_package, _source, _manifest = make_package(
            tmp_dir,
            "recover-age-previous-old",
        )
        age_previous_keep_package, _source, _manifest = make_package(
            tmp_dir,
            "recover-age-previous-keep",
        )
        age_previous_recent_package, _source, _manifest = make_package(
            tmp_dir,
            "recover-age-previous-recent",
        )
        age_previous_old = tmp_dir / ".recover-age.cglb.previous-100-0"
        age_previous_keep = tmp_dir / ".recover-age.cglb.previous-200-0"
        age_previous_recent = tmp_dir / ".recover-age.cglb.previous-300-0"
        age_file_old = tmp_dir / ".recover-age.cglb.staging-400-0"
        age_file_recent = tmp_dir / ".recover-age.cglb.staging-500-0"
        age_previous_old_package.rename(age_previous_old)
        age_previous_keep_package.rename(age_previous_keep)
        age_previous_recent_package.rename(age_previous_recent)
        age_file_old.write_text("old sidecar-named file\n", encoding="utf-8")
        age_file_recent.write_text("recent sidecar-named file\n", encoding="utf-8")
        for old_path in (age_previous_old, age_previous_keep, age_file_old):
            set_fixture_mtime(old_path, seconds_ago=7200)
        for recent_path in (age_previous_recent, age_file_recent):
            set_fixture_mtime(recent_path, seconds_ago=0)

        expected_age_applied = (
            expected_cleanup_candidate(
                age_previous_old,
                "previous",
                "100",
                0,
                directory=True,
                reason="previous-backup",
                action="discarded",
            ),
            expected_cleanup_candidate(
                age_file_old,
                "staging",
                "400",
                0,
                directory=False,
                reason="not-directory",
                action="discarded",
            ),
        )
        expected_age_retained = (
            expected_cleanup_candidate(
                age_previous_keep,
                "previous",
                "200",
                0,
                directory=True,
                reason="previous-backup",
                action="kept",
                retained_by="keep-last",
            ),
            expected_cleanup_candidate(
                age_previous_recent,
                "previous",
                "300",
                0,
                directory=True,
                reason="previous-backup",
                action="kept",
                retained_by="younger-than",
            ),
            expected_cleanup_candidate(
                age_file_recent,
                "staging",
                "500",
                0,
                directory=False,
                reason="not-directory",
                action="kept",
                retained_by="younger-than",
            ),
        )
        result = run_recover(
            cglc,
            age_package,
            "--discard-stale",
            "--older-than",
            "1h",
            "--keep-last",
            "1",
            "--apply",
            json_output=True,
        )
        if result.returncode != 0:
            errors.append(
                "recover-discard-stale-older-than-json: expected success, got "
                f"{result.stderr}{result.stdout}".strip()
            )
        expect_stale_cleanup_json(
            errors,
            root,
            tmp_dir,
            "recover-discard-stale-older-than-json",
            result,
            queried=age_package,
            requested=age_package,
            dry_run=False,
            requested_exists=True,
            keep_last=1,
            older_than_seconds=3600,
            expected_candidates=expected_age_applied,
            expected_retained=expected_age_retained,
        )
        for discarded_path in (age_previous_old, age_file_old):
            if discarded_path.exists():
                errors.append(
                    "recover-discard-stale-older-than-json: expected old path "
                    f"to be removed: {discarded_path.as_posix()}"
                )
        for retained_path in (
            age_previous_keep,
            age_previous_recent,
            age_file_recent,
        ):
            if not retained_path.exists():
                errors.append(
                    "recover-discard-stale-older-than-json: expected retained "
                    f"path to survive: {retained_path.as_posix()}"
                )

        result = run_recover(
            cglc,
            age_package,
            "--discard-stale",
            "--older-than",
            "invalid-duration",
        )
        errors.extend(
            expect_failure(
                result,
                "recover-discard-stale-older-than-invalid",
                "expected duration for --older-than",
            )
        )

        discard_package, _source, _manifest = make_package(tmp_dir, "recover-discard")
        discard_sidecar = tmp_dir / ".recover-discard.cglb.staging-333-0"
        discard_package.rename(discard_sidecar)
        result = run_recover(cglc, discard_sidecar, "--discard")
        errors.extend(
            expect_success(result, "recover-discard", "discarded package sidecar")
        )
        if discard_sidecar.exists():
            errors.append("recover-discard: expected sidecar to be removed")
        if discard_package.exists():
            errors.append("recover-discard: expected requested package to stay absent")

        discard_json_package, _source, _manifest = make_package(
            tmp_dir,
            "recover-discard-json",
        )
        discard_json_sidecar = tmp_dir / ".recover-discard-json.cglb.staging-333-json-0"
        discard_json_package.rename(discard_json_sidecar)
        result = run_recover(
            cglc,
            discard_json_sidecar,
            "--discard",
            json_output=True,
        )
        if result.returncode != 0:
            errors.append(
                "recover-discard-json: expected success, got "
                f"{result.stderr}{result.stdout}".strip()
            )
        expect_recovery_json(
            errors,
            root,
            tmp_dir,
            "recover-discard-json",
            result,
            action="discard",
            sidecar=discard_json_sidecar,
            requested=discard_json_package,
            success=True,
            message_substring="discarded package sidecar",
        )

        invalid_package, _source, manifest = make_package(tmp_dir, "recover-invalid")
        invalid_sidecar = tmp_dir / ".recover-invalid.cglb.staging-444-0"
        invalid_package.rename(invalid_sidecar)
        package_path(invalid_sidecar, manifest["artifacts"]["backendSource"]).unlink()
        result = run_recover(cglc, invalid_sidecar, "--promote")
        errors.extend(
            expect_failure(
                result,
                "recover-invalid",
                "package.recover.verify-failed",
            )
        )
        if not invalid_sidecar.is_dir() or invalid_package.exists():
            errors.append(
                "recover-invalid: expected invalid sidecar to remain unpromoted"
            )

        result = run_recover(cglc, invalid_sidecar, "--promote", json_output=True)
        if result.returncode == 0:
            errors.append("recover-invalid-json: expected failure")
        expect_recovery_json(
            errors,
            root,
            tmp_dir,
            "recover-invalid-json",
            result,
            action="promote",
            sidecar=invalid_sidecar,
            requested=invalid_package,
            success=False,
            diagnostic_code="package.recover.verify-failed",
        )

        corrupt_manifest_package, _source, _manifest = make_package(
            tmp_dir,
            "recover-corrupt-manifest",
        )
        corrupt_manifest_sidecar = (
            tmp_dir / ".recover-corrupt-manifest.cglb.staging-manifest-0"
        )
        corrupt_manifest_package.rename(corrupt_manifest_sidecar)
        (corrupt_manifest_sidecar / "manifest.json").write_text(
            "{not valid json",
            encoding="utf-8",
        )
        result = run_recover(
            cglc,
            corrupt_manifest_sidecar,
            "--promote",
            json_output=True,
        )
        if result.returncode == 0:
            errors.append("recover-corrupt-manifest-json: expected failure")
        payload = expect_recovery_json(
            errors,
            root,
            tmp_dir,
            "recover-corrupt-manifest-json",
            result,
            action="promote",
            sidecar=corrupt_manifest_sidecar,
            requested=corrupt_manifest_package,
            success=False,
            diagnostic_code="package.recover.verify-failed",
        )
        expect_recovery_diagnostic(
            errors,
            "recover-corrupt-manifest-json",
            payload,
            "package.verify.invalid-json",
            "package manifest is not a valid JSON object",
        )
        if not corrupt_manifest_sidecar.is_dir() or corrupt_manifest_package.exists():
            errors.append(
                "recover-corrupt-manifest-json: expected corrupt sidecar to "
                "remain unpromoted"
            )

        null_requirements_package, _source, null_requirements_manifest = make_package(
            tmp_dir,
            "recover-null-artifact-requirements",
        )
        null_requirements_manifest["packageArtifactRequirements"] = None
        rewrite_manifest(null_requirements_package, null_requirements_manifest)
        null_requirements_sidecar = (
            tmp_dir / ".recover-null-artifact-requirements.cglb.staging-null-0"
        )
        null_requirements_package.rename(null_requirements_sidecar)
        result = run_recover(
            cglc,
            null_requirements_sidecar,
            "--promote",
            json_output=True,
        )
        if result.returncode == 0:
            errors.append("recover-null-artifact-requirements-json: expected failure")
        payload = expect_recovery_json(
            errors,
            root,
            tmp_dir,
            "recover-null-artifact-requirements-json",
            result,
            action="promote",
            sidecar=null_requirements_sidecar,
            requested=null_requirements_package,
            success=False,
            diagnostic_code="package.recover.verify-failed",
        )
        expect_recovery_diagnostic(
            errors,
            "recover-null-artifact-requirements-json",
            payload,
            "package.verify.invalid-manifest",
            "package manifest packageArtifactRequirements is invalid",
        )
        if not null_requirements_sidecar.is_dir() or null_requirements_package.exists():
            errors.append(
                "recover-null-artifact-requirements-json: expected invalid sidecar "
                "to remain unpromoted"
            )

        vulkan_package, _source, vulkan_manifest = make_package(
            tmp_dir,
            "recover-vulkan-missing-assembly",
            target="vulkan",
        )
        vulkan_sidecar = (
            tmp_dir / ".recover-vulkan-missing-assembly.cglb.staging-vulkan-0"
        )
        vulkan_package.rename(vulkan_sidecar)
        package_path(
            vulkan_sidecar,
            vulkan_manifest["artifacts"]["backendAssembly"],
        ).unlink()
        result = run_recover(
            cglc,
            vulkan_sidecar,
            "--promote",
            json_output=True,
        )
        if result.returncode == 0:
            errors.append("recover-vulkan-missing-assembly-json: expected failure")
        payload = expect_recovery_json(
            errors,
            root,
            tmp_dir,
            "recover-vulkan-missing-assembly-json",
            result,
            action="promote",
            sidecar=vulkan_sidecar,
            requested=vulkan_package,
            success=False,
            diagnostic_code="package.recover.verify-failed",
        )
        expect_recovery_diagnostic(
            errors,
            "recover-vulkan-missing-assembly-json",
            payload,
            "package.verify.missing-artifact",
            "package artifact 'backendAssembly' does not exist",
        )
        if not vulkan_sidecar.is_dir() or vulkan_package.exists():
            errors.append(
                "recover-vulkan-missing-assembly-json: expected invalid sidecar "
                "to remain unpromoted"
            )

        metal_package, _source, metal_manifest = make_package(
            tmp_dir,
            "recover-metal-missing-debug-metadata",
            target="metal",
        )
        metal_sidecar = (
            tmp_dir / ".recover-metal-missing-debug-metadata.cglb.staging-metal-0"
        )
        metal_package.rename(metal_sidecar)
        package_path(
            metal_sidecar,
            metal_manifest["artifacts"]["debugMetadata"],
        ).unlink()
        result = run_recover(
            cglc,
            metal_sidecar,
            "--promote",
            json_output=True,
        )
        if result.returncode == 0:
            errors.append("recover-metal-missing-debug-metadata-json: expected failure")
        payload = expect_recovery_json(
            errors,
            root,
            tmp_dir,
            "recover-metal-missing-debug-metadata-json",
            result,
            action="promote",
            sidecar=metal_sidecar,
            requested=metal_package,
            success=False,
            diagnostic_code="package.recover.verify-failed",
        )
        expect_recovery_diagnostic(
            errors,
            "recover-metal-missing-debug-metadata-json",
            payload,
            "package.verify.missing-artifact",
            "package artifact 'debugMetadata' does not exist",
        )
        if not metal_sidecar.is_dir() or metal_package.exists():
            errors.append(
                "recover-metal-missing-debug-metadata-json: expected invalid "
                "sidecar to remain unpromoted"
            )

        missing_sidecar_path = tmp_dir / ".recover-missing.cglb.staging-missing-0"
        missing_requested_path = tmp_dir / "recover-missing.cglb"
        result = run_recover(
            cglc,
            missing_sidecar_path,
            "--promote",
        )
        errors.extend(
            expect_failure(
                result,
                "recover-missing-sidecar",
                "package.recover.missing-sidecar",
            )
        )

        result = run_recover(
            cglc,
            missing_sidecar_path,
            "--promote",
            json_output=True,
        )
        if result.returncode == 0:
            errors.append("recover-missing-sidecar-json: expected failure")
        expect_recovery_json(
            errors,
            root,
            tmp_dir,
            "recover-missing-sidecar-json",
            result,
            action="promote",
            sidecar=missing_sidecar_path,
            requested=missing_requested_path,
            success=False,
            diagnostic_code="package.recover.missing-sidecar",
        )

        file_sidecar_path = tmp_dir / ".recover-file.cglb.staging-file-0"
        file_requested_path = tmp_dir / "recover-file.cglb"
        file_sidecar_path.write_text("not a package directory\n", encoding="utf-8")
        result = run_recover(
            cglc,
            file_sidecar_path,
            "--promote",
        )
        errors.extend(
            expect_failure(
                result,
                "recover-file-sidecar",
                "package.recover.invalid-sidecar",
            )
        )
        if not file_sidecar_path.is_file() or file_requested_path.exists():
            errors.append(
                "recover-file-sidecar: expected invalid sidecar file to remain "
                "unpromoted"
            )

        result = run_recover(
            cglc,
            file_sidecar_path,
            "--promote",
            json_output=True,
        )
        if result.returncode == 0:
            errors.append("recover-file-sidecar-json: expected failure")
        expect_recovery_json(
            errors,
            root,
            tmp_dir,
            "recover-file-sidecar-json",
            result,
            action="promote",
            sidecar=file_sidecar_path,
            requested=file_requested_path,
            success=False,
            diagnostic_code="package.recover.invalid-sidecar",
        )
        if not file_sidecar_path.is_file() or file_requested_path.exists():
            errors.append(
                "recover-file-sidecar-json: expected invalid sidecar file to "
                "remain unpromoted"
            )

        invalid_sidecar_path = tmp_dir / "not-a-sidecar.cglb"
        result = run_recover(
            cglc,
            invalid_sidecar_path,
            "--promote",
        )
        errors.extend(
            expect_failure(
                result,
                "recover-invalid-sidecar",
                "package.recover.invalid-sidecar",
            )
        )

        result = run_recover(
            cglc,
            invalid_sidecar_path,
            "--promote",
            json_output=True,
        )
        if result.returncode == 0:
            errors.append("recover-invalid-sidecar: expected failure")
        expect_recovery_json(
            errors,
            root,
            tmp_dir,
            "recover-invalid-sidecar-json",
            result,
            action="promote",
            sidecar=invalid_sidecar_path,
            requested=None,
            success=False,
            diagnostic_code="package.recover.invalid-sidecar",
        )

        result = subprocess.run(
            [str(cglc), "package", "recover", str(sidecar)],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        errors.extend(
            expect_failure(
                result,
                "recover-action-required",
                "package recover requires exactly one",
            )
        )

    return errors


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--root",
        default=Path(__file__).resolve().parents[1],
        type=Path,
        help="CrossGL-Compiler repository root",
    )
    parser.add_argument("--cglc", required=True, help="path to cglc executable")
    args = parser.parse_args()

    errors = run_cases(args.root.resolve(), Path(args.cglc).resolve())
    if errors:
        for error in errors:
            print(f"package recover fixture check failed: {error}", file=sys.stderr)
        return 1

    print("validated package recover fixtures")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
