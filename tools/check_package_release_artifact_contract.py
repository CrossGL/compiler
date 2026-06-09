#!/usr/bin/env python3
"""Exercise package release native artifact contract enforcement."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
import tempfile
from pathlib import Path

from check_package_release_publish_flow import (
    CheckError,
    expect_success,
    load_json,
    run_checked,
    run_expect_failure,
    validate_schema,
    write_json,
)


FIXTURE = "tests/fixtures/SimpleShader.cgl"
PACKAGE_NAME = "SimpleShader.cglb"
DESCRIPTOR_ARTIFACT = "nativeArtifactDescriptor"
DESCRIPTOR_PATH = "metadata/native-artifact.json"
DESCRIPTOR_OPTIMIZATION_EVIDENCE = {
    "requestedLevel": "O2",
    "effectiveLevel": "O2",
    "policy": "crossgl-to-dxc-optimization-map",
    "status": "metadata-only",
    "tool": "dxc",
    "toolFlag": "-O3",
    "debugInfo": False,
    "profile": "cs_6_0",
    "flags": ["-O3"],
    "evidenceSource": {
        "kind": "compiler-policy",
    },
}


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def literal_sha256(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def build_fixture_package(root: Path, cglc: Path, package_root: Path) -> Path:
    package_path = package_root / PACKAGE_NAME
    run_checked(
        "build-directx-package",
        [
            cglc,
            "build",
            root / FIXTURE,
            "--target",
            "directx",
            "--output",
            package_path,
            "--debug-ir",
        ],
        cwd=root,
    )
    return package_path


def add_emitted_native_artifact_descriptor(package_path: Path) -> None:
    manifest_path = package_path / "manifest.json"
    manifest = load_json(manifest_path)
    artifacts = manifest.setdefault("artifacts", {})
    native_binary = artifacts.get("nativeBinary")
    backend_source = artifacts.get("backendSource")
    if not isinstance(native_binary, str) or not isinstance(backend_source, str):
        raise CheckError("fixture package is missing nativeBinary/backendSource paths")

    native_binary_path = package_path / native_binary
    native_binary_path.parent.mkdir(parents=True, exist_ok=True)
    native_binary_path.write_bytes(b"crossgl package artifact contract dxil\n")

    artifacts["nativeBinaryStatus"] = "emitted"
    artifacts[DESCRIPTOR_ARTIFACT] = DESCRIPTOR_PATH

    descriptor = {
        "schemaVersion": 1,
        "kind": "crossgl.nativeArtifact",
        "contractVersion": "native-artifact-v0",
        "target": "directx",
        "binaryKind": "directx.dxil",
        "artifactPath": native_binary,
        "artifactHash": {
            "algorithm": "sha256",
            "value": file_sha256(native_binary_path),
        },
        "sizeBytes": native_binary_path.stat().st_size,
        "sourcePath": backend_source,
        "sourceHash": {
            "algorithm": "sha256",
            "value": file_sha256(package_path / backend_source),
        },
        "toolchainProvenance": {
            "producer": "cglc package build",
            "tools": [
                {
                    "name": "fixture dxc",
                    "role": "compiler",
                    "version": "test",
                    "executable": "dxc",
                }
            ],
            "invocation": {
                "commandLineSha256": literal_sha256("fixture dxc command"),
                "environmentSha256": literal_sha256("fixture dxc environment"),
            },
        },
        "optimizationLevel": "O2",
        "optimizationEvidence": DESCRIPTOR_OPTIMIZATION_EVIDENCE,
        "validationStatus": "unavailable",
        "nativeBinaryStatus": "emitted",
        "validationDiagnostics": [],
    }
    write_json(package_path / DESCRIPTOR_PATH, descriptor)
    write_json(manifest_path, manifest)


def export_verified_package_set(
    root: Path, cglc: Path, work_dir: Path, package_root: Path
):
    paths = {
        "set": work_dir / "package-set.json",
        "batch": work_dir / "package-set-verification-batch.json",
        "report": work_dir / "package-set-verification-report.json",
        "summary": work_dir / "package-set-verification-summary.json",
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
    return paths


def artifact_names(package: dict) -> set[str]:
    return {
        artifact.get("name")
        for artifact in package.get("artifacts", [])
        if isinstance(artifact, dict)
    }


def artifacts_by_name(package: dict) -> dict[str, dict]:
    return {
        artifact.get("name"): artifact
        for artifact in package.get("artifacts", [])
        if isinstance(artifact, dict) and isinstance(artifact.get("name"), str)
    }


def expect_release_eligible(label: str, path: Path) -> dict:
    payload = load_json(path)
    if payload.get("releaseEligible") is not True:
        raise CheckError(f"{label}: expected releaseEligible=true in {path}")
    return payload


def descriptor_file_facts(package_path: Path) -> dict:
    descriptor_path = package_path / DESCRIPTOR_PATH
    return {
        "path": DESCRIPTOR_PATH,
        "exists": descriptor_path.is_file(),
        "sizeBytes": descriptor_path.stat().st_size
        if descriptor_path.is_file()
        else None,
        "sha256": file_sha256(descriptor_path) if descriptor_path.is_file() else None,
    }


def check_descriptor_propagates(payload: dict, label: str, package_path: Path) -> None:
    packages = payload.get("packages")
    if not isinstance(packages, list) or len(packages) != 1:
        raise CheckError(f"{label}: expected one package record")
    package = packages[0]
    if package.get("nativeBinaryStatus") != "emitted":
        raise CheckError(f"{label}: expected emitted nativeBinaryStatus")
    if DESCRIPTOR_ARTIFACT not in artifact_names(package):
        raise CheckError(f"{label}: missing nativeArtifactDescriptor artifact")
    descriptor_record = artifacts_by_name(package).get(DESCRIPTOR_ARTIFACT)
    if not isinstance(descriptor_record, dict):
        raise CheckError(f"{label}: missing nativeArtifactDescriptor artifact record")
    expected = descriptor_file_facts(package_path)
    if "packageArtifactPath" in descriptor_record:
        expected_record = {
            "packageArtifactPath": expected["path"],
            "sourcePath": (package_path / expected["path"]).resolve().as_posix(),
            "sizeBytes": expected["sizeBytes"],
            "sha256": expected["sha256"],
        }
    else:
        expected_record = expected
    for key, expected_value in expected_record.items():
        if key == "sourcePath":
            actual_source = descriptor_record.get(key)
            if (
                not isinstance(actual_source, str)
                or Path(actual_source).resolve() != Path(expected_value).resolve()
            ):
                raise CheckError(
                    f"{label}: nativeArtifactDescriptor artifact sourcePath must "
                    f"resolve to {expected_value!r}, got {actual_source!r}"
                )
            continue
        if descriptor_record.get(key) != expected_value:
            raise CheckError(
                f"{label}: nativeArtifactDescriptor artifact {key} must be "
                f"{expected_value!r}, got {descriptor_record.get(key)!r}"
            )


def check_package_inspect_descriptor_optimizer(
    root: Path, cglc: Path, package_path: Path
) -> None:
    result = run_checked(
        "inspect-descriptor-optimizer",
        [cglc, "package", "inspect", package_path, "--json"],
        cwd=root,
    )
    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise CheckError(f"inspect-descriptor-optimizer: invalid JSON: {exc}") from exc

    descriptor = payload.get("nativeArtifactDescriptor")
    if not isinstance(descriptor, dict):
        raise CheckError("inspect-descriptor-optimizer: missing descriptor view")
    descriptor_payload = load_json(package_path / DESCRIPTOR_PATH)
    for key in ("optimizationLevel", "optimizationEvidence"):
        if descriptor.get(key) != descriptor_payload.get(key):
            raise CheckError(
                f"inspect-descriptor-optimizer: nativeArtifactDescriptor.{key} "
                f"must match descriptor JSON, got {descriptor.get(key)!r}, "
                f"expected {descriptor_payload.get(key)!r}"
            )


def write_package_mode_override(
    source_path: Path, destination_path: Path, package_mode: str
) -> None:
    payload = load_json(source_path)
    packages = payload.get("packages")
    if not isinstance(packages, list) or not packages:
        raise CheckError(f"{source_path}: expected non-empty packages")

    changed = 0
    for package in packages:
        requirements = package.get("packageArtifactRequirements")
        if not isinstance(requirements, dict):
            raise CheckError(
                f"{source_path}: package is missing packageArtifactRequirements"
            )
        if requirements.get("packageMode") != package_mode:
            requirements["packageMode"] = package_mode
            changed += 1

    if changed == 0:
        raise CheckError(
            f"{source_path}: packageArtifactRequirements were already "
            f"packageMode={package_mode!r}"
        )
    write_json(destination_path, payload)


def check_recorded_requirements_reject_target_contract_drift(
    root: Path, cglc: Path, paths: dict, work_dir: Path
) -> None:
    # Release bundle/plan readers reject requirement metadata that drifts from
    # the target contract, even when the release document was produced from a
    # previously valid package.
    paths["bundle_recorded_mode_override"] = (
        work_dir / "package-release-bundle-recorded-mode-override.json"
    )
    paths["bundle_recorded_mode_override_verification"] = (
        work_dir / "package-release-bundle-recorded-mode-override-verification.json"
    )
    write_package_mode_override(
        paths["bundle"], paths["bundle_recorded_mode_override"], "native"
    )
    run_expect_failure(
        "verify-bundle-recorded-mode-override",
        [
            cglc,
            "package",
            "release",
            "--verify-bundle",
            paths["bundle_recorded_mode_override"],
            "--json",
        ],
        cwd=root,
        expected=(
            "packageArtifactRequirements.packageMode must match target "
            "contract"
        ),
    )

    paths["plan_recorded_mode_override"] = (
        work_dir / "package-release-publish-plan-recorded-mode-override.json"
    )
    paths["stage_recorded_mode_override"] = (
        work_dir / "package-release-publish-stage-recorded-mode-override.json"
    )
    paths["stage_recorded_mode_override_dir"] = (
        work_dir / "package-release-stage-recorded-mode-override"
    )
    write_package_mode_override(
        paths["plan"], paths["plan_recorded_mode_override"], "native"
    )
    run_expect_failure(
        "stage-publish-recorded-mode-override",
        [
            cglc,
            "package",
            "release",
            "--stage-publish",
            paths["plan_recorded_mode_override"],
            "--stage-output",
            paths["stage_recorded_mode_override_dir"],
            "--json",
        ],
        cwd=root,
        expected=(
            "packageArtifactRequirements.packageMode must match target "
            "contract"
        ),
    )


def check_positive_release(
    root: Path, cglc: Path, paths: dict, work_dir: Path, package_path: Path
) -> None:
    paths["promotion"] = work_dir / "package-release-promotion-manifest.json"
    paths["bundle"] = work_dir / "package-release-bundle.json"
    paths["bundle_verification"] = work_dir / "package-release-bundle-verification.json"
    paths["plan"] = work_dir / "package-release-publish-plan.json"

    run_checked(
        "promotion-positive",
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
    )
    validate_schema(
        root,
        "promotion-positive",
        "package-release-promotion-manifest-v1.schema.json",
        paths["promotion"],
    )
    validate_schema(
        root,
        "bundle-positive",
        "package-release-bundle-v1.schema.json",
        paths["bundle"],
    )
    promotion = expect_release_eligible("promotion-positive", paths["promotion"])
    bundle = load_json(paths["bundle"])
    if bundle.get("releaseEligible") is not True:
        raise CheckError(
            f"bundle-positive: expected releaseEligible=true in {paths['bundle']}"
        )
    check_descriptor_propagates(promotion, "promotion-positive", package_path)
    check_descriptor_propagates(bundle, "bundle-positive", package_path)

    run_checked(
        "verify-bundle-positive",
        [cglc, "package", "release", "--verify-bundle", paths["bundle"], "--json"],
        cwd=root,
        stdout_path=paths["bundle_verification"],
    )
    validate_schema(
        root,
        "bundle-verification-positive",
        "package-release-bundle-verification-v1.schema.json",
        paths["bundle_verification"],
    )
    expect_success("verify-bundle-positive", paths["bundle_verification"])

    run_checked(
        "plan-publish-positive",
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
    )
    validate_schema(
        root,
        "publish-plan-positive",
        "package-release-publish-plan-v1.schema.json",
        paths["plan"],
    )
    check_descriptor_propagates(
        load_json(paths["plan"]), "publish-plan-positive", package_path
    )
    check_recorded_requirements_reject_target_contract_drift(
        root, cglc, paths, work_dir
    )


def remove_descriptor_manifest_evidence(package_path: Path) -> None:
    manifest_path = package_path / "manifest.json"
    manifest = load_json(manifest_path)
    artifacts = manifest.get("artifacts")
    if not isinstance(artifacts, dict):
        raise CheckError("fixture package manifest artifacts must be an object")
    artifacts.pop(DESCRIPTOR_ARTIFACT, None)
    write_json(manifest_path, manifest)


def check_missing_descriptor_blocks_release(
    root: Path, cglc: Path, paths: dict, work_dir: Path
) -> None:
    bad_promotion = work_dir / "package-release-promotion-missing-descriptor.json"
    bad_bundle = work_dir / "package-release-bundle-missing-descriptor.json"
    run_expect_failure(
        "promotion-missing-descriptor",
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
        expected="nativeArtifactDescriptor artifact evidence",
    )

    payload = load_json(bad_promotion)
    if payload.get("releaseEligible") is not False:
        raise CheckError("missing descriptor promotion should not be eligible")
    blocker_codes = [blocker.get("code") for blocker in payload.get("blockers", [])]
    if "package-inventory-failed" not in blocker_codes:
        raise CheckError("missing descriptor promotion should record inventory blocker")


def check_flow(root: Path, cglc: Path, work_dir: Path) -> None:
    if work_dir.exists():
        shutil.rmtree(work_dir)
    work_dir.mkdir(parents=True)

    package_root = work_dir / "packages"
    package_root.mkdir()
    package_path = build_fixture_package(root, cglc, package_root)
    add_emitted_native_artifact_descriptor(package_path)
    check_package_inspect_descriptor_optimizer(root, cglc, package_path)

    paths = export_verified_package_set(root, cglc, work_dir, package_root)
    check_positive_release(root, cglc, paths, work_dir, package_path)

    remove_descriptor_manifest_evidence(package_path)
    check_missing_descriptor_blocks_release(root, cglc, paths, work_dir)
    print(f"validated package release artifact contract in {work_dir}")


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--cglc", type=Path, required=True)
    parser.add_argument("--work-dir", type=Path)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    root = args.root.resolve()
    cglc = args.cglc.resolve()
    if not cglc.exists():
        raise CheckError(f"cglc not found: {cglc}")
    if args.work_dir is None:
        with tempfile.TemporaryDirectory(
            prefix="crossgl-release-artifact-contract-"
        ) as tmp:
            check_flow(root, cglc, Path(tmp))
    else:
        check_flow(root, cglc, args.work_dir.resolve())


if __name__ == "__main__":
    try:
        main()
    except CheckError as exc:
        print(str(exc), file=sys.stderr)
        sys.exit(1)
