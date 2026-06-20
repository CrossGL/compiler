#!/usr/bin/env python3
"""Exercise release provenance manifest generation from a publish stage report."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any


FIXTURE_COMMIT = "1234567890abcdef1234567890abcdef12345678"
FIXTURE_TOOLCHAIN = {
    "cglc": "stage-report-fixture-cglc",
    "python": "stage-report-fixture-python",
}
FIXTURE_ARTIFACT_BYTES = b"crossgl-release-provenance-stage-artifact\n"
FIXTURE_DESCRIPTOR_BYTES = (
    json.dumps(
        {
            "schemaVersion": 1,
            "kind": "native-artifact-v0",
            "target": "directx",
            "artifact": "SimpleShader.dxil",
        },
        sort_keys=True,
    ).encode("utf-8")
    + b"\n"
)


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, dict):
        raise AssertionError(f"{path}: expected JSON object")
    return payload


def validate_schema(root: Path, manifest: dict[str, Any]) -> None:
    sys.path.insert(0, str(root / "tools"))
    from json_schema_semantics import validate_semantics
    from validate_json_schema import SchemaError
    from validate_json_schema import validate as validate_json_schema

    schema = load_json(root / "docs/schemas/release-provenance-manifest-v1.schema.json")
    try:
        validate_json_schema(manifest, schema, schema)
    except SchemaError as exc:
        raise AssertionError(f"schema validation failed: {exc}") from exc

    semantic_errors = validate_semantics(manifest, schema)
    if semantic_errors:
        raise AssertionError(
            "semantic validation failed:\n" + "\n".join(semantic_errors)
        )


def expect_equal(label: str, actual: Any, expected: Any) -> None:
    if actual != expected:
        raise AssertionError(f"{label}: expected {expected!r}, got {actual!r}")


def run_producer(root: Path, work_dir: Path) -> dict[str, Any]:
    artifact_root = work_dir / "artifact-root"
    staged_artifact = artifact_root / "package-release-stage" / "SimpleShader.dxil"
    staged_descriptor = (
        artifact_root / "package-release-stage" / "SimpleShader.native-artifact.json"
    )
    staged_artifact.parent.mkdir(parents=True)
    staged_artifact.write_bytes(FIXTURE_ARTIFACT_BYTES)
    staged_descriptor.write_bytes(FIXTURE_DESCRIPTOR_BYTES)

    artifact_sha = sha256_bytes(FIXTURE_ARTIFACT_BYTES)
    descriptor_sha = sha256_bytes(FIXTURE_DESCRIPTOR_BYTES)
    package_root = artifact_root / "packages" / "SimpleShader.cglb"
    package_root.mkdir(parents=True)

    stage_report = work_dir / "package-release-publish-stage.json"
    write_json(
        stage_report,
        {
            "schemaVersion": 1,
            "stagePath": str(staged_artifact.parent),
            "artifacts": [
                {
                    "stagedPath": str(staged_artifact),
                    "destinationPath": "release/v0.0.0/SimpleShader.dxil",
                    "packagePath": str(package_root),
                    "packageArtifactPath": "native/directx/SimpleShader.dxil",
                    "sizeBytes": len(FIXTURE_ARTIFACT_BYTES),
                    "sha256": artifact_sha,
                },
                {
                    "stagedPath": str(staged_descriptor),
                    "destinationPath": (
                        "release/v0.0.0/SimpleShader.native-artifact.json"
                    ),
                    "packagePath": str(package_root),
                    "packageArtifactPath": (
                        "native/directx/SimpleShader.native-artifact.json"
                    ),
                    "sizeBytes": len(FIXTURE_DESCRIPTOR_BYTES),
                    "sha256": descriptor_sha,
                },
            ],
        },
    )

    guardrails = work_dir / "package-release-publish-guardrails.json"
    write_json(
        guardrails,
        {
            "schemaVersion": 1,
            "records": [
                {
                    "operation": "stage-report-fixture-dry-run",
                    "targetKind": "gcs",
                    "mode": "dry-run",
                    "dryRun": True,
                    "localOnly": False,
                    "mockUpload": False,
                    "liveCloudUploadAllowed": False,
                    "liveCloudUploadOptIn": None,
                }
            ],
        },
    )

    manifest_output = work_dir / "release-provenance-manifest.json"
    command = [
        sys.executable,
        str(root / "tools/check_release_provenance_manifest.py"),
        "--root",
        str(root),
        "--artifact-root",
        str(artifact_root),
        "--from-stage-report",
        str(stage_report),
        "--guardrails",
        str(guardrails),
        "--manifest-output",
        str(manifest_output),
        "--source-commit",
        FIXTURE_COMMIT,
    ]
    for key, value in FIXTURE_TOOLCHAIN.items():
        command.extend(["--toolchain", f"{key}={value}"])

    result = subprocess.run(
        command,
        cwd=root,
        text=True,
        capture_output=True,
        check=False,
    )
    if result.returncode != 0:
        raise AssertionError(
            "release provenance manifest producer failed with "
            f"{result.returncode}\nstdout:\n{result.stdout}\nstderr:\n{result.stderr}"
        )
    return load_json(manifest_output)


def validate_manifest(root: Path, manifest: dict[str, Any]) -> None:
    validate_schema(root, manifest)

    expect_equal("schemaVersion", manifest.get("schemaVersion"), 1)
    expect_equal(
        "kind",
        manifest.get("kind"),
        "crossgl-release-provenance-manifest-v1",
    )
    expect_equal("sourceCommit", manifest.get("sourceCommit"), FIXTURE_COMMIT)
    toolchain = manifest.get("toolchainSummary")
    if not isinstance(toolchain, dict):
        raise AssertionError("$.toolchainSummary: expected object")
    for key, value in FIXTURE_TOOLCHAIN.items():
        expect_equal(f"toolchainSummary.{key}", toolchain.get(key), value)
    if not isinstance(toolchain.get("platform"), str) or not toolchain["platform"]:
        raise AssertionError("$.toolchainSummary.platform: expected non-empty string")
    expected_artifact_bytes = len(FIXTURE_ARTIFACT_BYTES) + len(
        FIXTURE_DESCRIPTOR_BYTES
    )
    expect_equal("artifactCount", manifest.get("artifactCount"), 2)
    expect_equal(
        "artifactBytes",
        manifest.get("artifactBytes"),
        expected_artifact_bytes,
    )

    artifacts = manifest.get("artifacts")
    if not isinstance(artifacts, list) or len(artifacts) != 2:
        raise AssertionError("$.artifacts: expected two artifacts")
    artifacts_by_path = {
        artifact.get("path"): artifact
        for artifact in artifacts
        if isinstance(artifact, dict)
    }
    expected_artifacts = {
        "package-release-stage/SimpleShader.dxil": {
            "destinationPath": "release/v0.0.0/SimpleShader.dxil",
            "packageArtifactPath": "native/directx/SimpleShader.dxil",
            "sizeBytes": len(FIXTURE_ARTIFACT_BYTES),
            "sha256": sha256_bytes(FIXTURE_ARTIFACT_BYTES),
        },
        "package-release-stage/SimpleShader.native-artifact.json": {
            "destinationPath": ("release/v0.0.0/SimpleShader.native-artifact.json"),
            "packageArtifactPath": ("native/directx/SimpleShader.native-artifact.json"),
            "sizeBytes": len(FIXTURE_DESCRIPTOR_BYTES),
            "sha256": sha256_bytes(FIXTURE_DESCRIPTOR_BYTES),
        },
    }
    expect_equal(
        "artifact paths",
        sorted(artifacts_by_path),
        sorted(expected_artifacts),
    )
    for artifact_path, expected in expected_artifacts.items():
        artifact = artifacts_by_path[artifact_path]
        expect_equal(
            f"{artifact_path}.destinationPath",
            artifact.get("destinationPath"),
            expected["destinationPath"],
        )
        expect_equal(
            f"{artifact_path}.packagePath",
            artifact.get("packagePath"),
            "packages/SimpleShader.cglb",
        )
        expect_equal(
            f"{artifact_path}.packageArtifactPath",
            artifact.get("packageArtifactPath"),
            expected["packageArtifactPath"],
        )
        expect_equal(
            f"{artifact_path}.sizeBytes",
            artifact.get("sizeBytes"),
            expected["sizeBytes"],
        )
        expect_equal(
            f"{artifact_path}.sha256",
            artifact.get("sha256"),
            expected["sha256"],
        )

    cloud_upload = manifest.get("cloudUpload")
    if not isinstance(cloud_upload, dict):
        raise AssertionError("$.cloudUpload: expected object")
    expect_equal("cloudUpload.mode", cloud_upload.get("mode"), "dry-run")
    expect_equal("cloudUpload.modes", cloud_upload.get("modes"), ["dry-run"])
    expect_equal(
        "cloudUpload.liveCloudUploadAllowed",
        cloud_upload.get("liveCloudUploadAllowed"),
        False,
    )
    expect_equal(
        "cloudUpload.liveCloudUploadOptIn",
        cloud_upload.get("liveCloudUploadOptIn"),
        None,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    args = parser.parse_args()

    root = args.root.resolve()
    with tempfile.TemporaryDirectory(
        prefix="crossgl-release-provenance-stage-report-"
    ) as tmp:
        manifest = run_producer(root, Path(tmp).resolve())
        validate_manifest(root, manifest)

    print("validated release provenance manifest generation from stage report")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
