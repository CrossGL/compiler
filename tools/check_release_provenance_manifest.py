#!/usr/bin/env python3
"""Create and validate a local release provenance/checksum manifest.

The manifest is intentionally offline: it records local artifact paths, file
sizes, SHA-256 hashes, the source commit, a toolchain summary, and the release
publish guardrail modes that were used to prepare artifacts. It never uploads
objects and refuses live cloud modes unless the operator explicitly opts in.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import re
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any


SCHEMA_VERSION = 1
MANIFEST_KIND = "crossgl-release-provenance-manifest-v1"
LIVE_CLOUD_UPLOAD_ENV = "CROSSGL_ALLOW_LIVE_CLOUD_RELEASE_UPLOAD"
SAFE_CLOUD_MODES = {"local-only", "dry-run", "mock"}
LIVE_CLOUD_MODE = "live-cloud"
KNOWN_CLOUD_MODES = SAFE_CLOUD_MODES | {LIVE_CLOUD_MODE}
SAFE_CLOUD_MODE_FLAGS = {
    "dry-run": "dryRun",
    "local-only": "localOnly",
    "mock": "mockUpload",
}
GUARDRAIL_MODE_FLAG_FIELDS = tuple(SAFE_CLOUD_MODE_FLAGS.values())
LIVE_CLOUD_OPT_IN_SOURCES = {"cli-flag", LIVE_CLOUD_UPLOAD_ENV}
CLOUD_URI_PREFIXES = ("gs://", "gcs://", "s3://", "az://", "azure://")
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
COMMIT_RE = re.compile(r"^[0-9a-f]{40}$")
LOCAL_ARTIFACT_PATH_FIELDS = ("path", "packagePath", "packageArtifactPath")
ARTIFACT_RELATIVE_PATH_FIELDS = LOCAL_ARTIFACT_PATH_FIELDS + ("destinationPath",)
URI_SCHEME_PATH_RE = re.compile(r"^[A-Za-z][A-Za-z0-9+.-]*:")
WINDOWS_DRIVE_PATH_RE = re.compile(r"^[A-Za-z]:")
LIVE_APPROVAL_STRING_FIELDS = (
    "approvalRecord",
    "projectAllowlistEntry",
    "bucketAllowlistEntry",
    "budgetGuardrail",
    "lifecyclePolicy",
)
LIVE_APPROVAL_PLACEHOLDERS = {"", "tbd", "todo", "none", "n/a", "placeholder"}
RELEASE_OBJECT_PREFIX_GENERIC_SEGMENTS = {
    "artifact",
    "artifacts",
    "latest",
    "shared",
    "scratch",
    "stage",
    "staging",
    "temp",
    "tmp",
    "upload",
    "uploads",
}
RELEASE_OBJECT_PREFIX_HINT_RE = re.compile(r"(^|/)(releases?|v[0-9][^/]*)($|/)")
REPORT_ONLY_ENV_STATES = {"absent", "forbidden", "present"}
REPORT_ONLY_PROMOTION_DECISIONS = {"hold", "promote", "reject"}
REPORT_ONLY_PROVIDER_METADATA_FIELDS = (
    "generation",
    "metageneration",
    "crc32c",
    "md5",
    "sha256",
    "sizeBytes",
)
REPORT_ONLY_RECEIPT_PATH_GROUPS = (
    "uploadReceiptPaths",
    "dryRunReceiptPaths",
    "failedAttemptReceiptPaths",
)


class CheckError(RuntimeError):
    pass


def load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise CheckError(f"{path}: failed to read JSON: {exc}") from exc


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")


def env_flag_enabled(name: str) -> bool:
    value = os.environ.get(name)
    return isinstance(value, str) and value.strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


def live_cloud_opted_in(allow_cloud_upload: bool) -> bool:
    return bool(allow_cloud_upload or env_flag_enabled(LIVE_CLOUD_UPLOAD_ENV))


def is_live_cloud_mode(mode: object) -> bool:
    return mode == LIVE_CLOUD_MODE


def cloud_mode_list() -> str:
    return ", ".join(repr(mode) for mode in sorted(KNOWN_CLOUD_MODES))


def is_placeholder_text(value: str) -> bool:
    stripped = value.strip()
    lower = stripped.lower()
    return (
        not stripped
        or lower in LIVE_APPROVAL_PLACEHOLDERS
        or lower.startswith("placeholder")
        or (stripped.startswith("<") and stripped.endswith(">"))
    )


def validate_explicit_text(
    errors: list[str], path: str, value: object, label: str
) -> str | None:
    if not isinstance(value, str):
        errors.append(f"{path}: expected string {label}")
        return None
    if is_placeholder_text(value):
        errors.append(f"{path}: expected explicit {label}, got placeholder")
        return None
    return value


def validate_live_approval_evidence(
    errors: list[str], path: str, value: object
) -> None:
    evidence = expect_object(errors, path, value)
    if evidence is None:
        return

    for field in LIVE_APPROVAL_STRING_FIELDS:
        validate_explicit_text(errors, f"{path}.{field}", evidence.get(field), field)

    prefix = validate_explicit_text(
        errors,
        f"{path}.releaseObjectPrefix",
        evidence.get("releaseObjectPrefix"),
        "releaseObjectPrefix",
    )
    if prefix is not None:
        try:
            validate_release_object_prefix_text(prefix)
        except CheckError as exc:
            errors.append(f"{path}.releaseObjectPrefix: {exc}")

    receipt_paths = evidence.get("auditReceiptPaths")
    if not isinstance(receipt_paths, list) or not receipt_paths:
        errors.append(f"{path}.auditReceiptPaths: expected non-empty list")
        return
    for index, receipt_path in enumerate(receipt_paths):
        receipt_text = validate_explicit_text(
            errors,
            f"{path}.auditReceiptPaths[{index}]",
            receipt_path,
            "audit receipt path",
        )
        if receipt_text is None:
            continue
        try:
            validate_artifact_path_text(receipt_text)
        except CheckError as exc:
            errors.append(f"{path}.auditReceiptPaths[{index}]: {exc}")


def validate_live_opt_in_source(errors: list[str], path: str, value: object) -> None:
    if value not in LIVE_CLOUD_OPT_IN_SOURCES:
        errors.append(
            f"{path}: expected explicit live cloud opt-in source one of "
            f"{sorted(LIVE_CLOUD_OPT_IN_SOURCES)!r}"
        )


def validate_report_path(
    errors: list[str], path: str, value: object, label: str
) -> str | None:
    text = validate_explicit_text(errors, path, value, label)
    if text is None:
        return None
    try:
        validate_artifact_path_text(text)
    except CheckError as exc:
        errors.append(f"{path}: {exc}")
        return None
    return text


def validate_report_path_list(
    errors: list[str],
    path: str,
    value: object,
    *,
    allow_empty: bool = False,
) -> list[str]:
    if not isinstance(value, list):
        errors.append(f"{path}: expected list")
        return []
    if not value and not allow_empty:
        errors.append(f"{path}: expected non-empty list")
        return []

    paths: list[str] = []
    for index, item in enumerate(value):
        text = validate_report_path(
            errors, f"{path}[{index}]", item, "release evidence path"
        )
        if text is not None:
            paths.append(text)
    if len(paths) != len(set(paths)):
        errors.append(f"{path}: expected unique paths")
    return paths


def validate_non_empty_report_value(
    errors: list[str], path: str, value: object, label: str
) -> None:
    if isinstance(value, str):
        validate_explicit_text(errors, path, value, label)
    elif isinstance(value, list):
        if not value:
            errors.append(f"{path}: expected non-empty {label}")
    elif isinstance(value, dict):
        if not value:
            errors.append(f"{path}: expected non-empty {label}")
    else:
        errors.append(f"{path}: expected string, list, or object {label}")


def validate_report_metadata_record(
    errors: list[str], path: str, value: object
) -> None:
    metadata = expect_object(errors, path, value)
    if metadata is None:
        return
    for field in REPORT_ONLY_PROVIDER_METADATA_FIELDS:
        field_path = f"{path}.{field}"
        field_value = metadata.get(field)
        if field == "sizeBytes":
            if not isinstance(field_value, int) or field_value < 0:
                errors.append(f"{field_path}: expected non-negative integer")
        elif field == "sha256":
            if not isinstance(field_value, str) or not SHA256_RE.fullmatch(field_value):
                errors.append(f"{field_path}: expected lowercase SHA-256")
        else:
            validate_explicit_text(errors, field_path, field_value, field)


def validate_report_provider_metadata(
    errors: list[str], path: str, value: object
) -> None:
    if isinstance(value, list):
        if not value:
            errors.append(f"{path}: expected non-empty provider object metadata")
            return
        for index, item in enumerate(value):
            validate_report_metadata_record(errors, f"{path}[{index}]", item)
        return
    validate_report_metadata_record(errors, path, value)


def validate_report_object_name(
    errors: list[str], path: str, value: object, release_prefix: str | None
) -> None:
    object_name = validate_explicit_text(errors, path, value, "objectName")
    if object_name is None:
        return
    try:
        validate_artifact_path_text(object_name)
    except CheckError as exc:
        errors.append(f"{path}: {exc}")
        return
    if release_prefix is not None and not (
        object_name == release_prefix or object_name.startswith(f"{release_prefix}/")
    ):
        errors.append(
            f"{path}: expected object under releaseObjectPrefix {release_prefix!r}"
        )


def validate_published_object_generation_record(
    errors: list[str],
    path: str,
    value: object,
    release_prefix: str | None,
) -> None:
    generation = expect_object(errors, path, value)
    if generation is None:
        return
    validate_report_object_name(
        errors,
        f"{path}.objectName",
        generation.get("objectName"),
        release_prefix,
    )
    validate_explicit_text(
        errors,
        f"{path}.generation",
        generation.get("generation"),
        "generation",
    )


def validate_release_evidence_report(report_path: str, value: object) -> list[str]:
    errors: list[str] = []
    payload = expect_object(errors, report_path, value)
    if payload is None:
        return errors

    audit = expect_object(
        errors,
        f"{report_path}.rollbackPromotionAudit",
        payload.get("rollbackPromotionAudit"),
    )
    if audit is None:
        return errors

    if audit.get("dryRunDefault") is not True:
        errors.append(
            f"{report_path}.rollbackPromotionAudit.dryRunDefault: expected true"
        )

    decision = audit.get("promotionDecision")
    if decision not in REPORT_ONLY_PROMOTION_DECISIONS:
        errors.append(
            f"{report_path}.rollbackPromotionAudit.promotionDecision: expected one "
            f"of {sorted(REPORT_ONLY_PROMOTION_DECISIONS)!r}"
        )
    if decision != "promote":
        validate_explicit_text(
            errors,
            f"{report_path}.rollbackPromotionAudit.rejectionReason",
            audit.get("rejectionReason"),
            "rejectionReason",
        )

    for field in ("promotionManifestPath", "releaseBundleVerificationPath"):
        validate_report_path(
            errors,
            f"{report_path}.rollbackPromotionAudit.{field}",
            audit.get(field),
            field,
        )
    validate_non_empty_report_value(
        errors,
        f"{report_path}.rollbackPromotionAudit.packageVerification",
        audit.get("packageVerification"),
        "packageVerification",
    )

    commit = audit.get("sourceCommit")
    if not isinstance(commit, str) or not COMMIT_RE.fullmatch(commit):
        errors.append(
            f"{report_path}.rollbackPromotionAudit.sourceCommit: expected "
            "40-character lowercase hex commit"
        )
    toolchain = audit.get("toolchainSummary")
    if not isinstance(toolchain, dict) or not toolchain:
        errors.append(
            f"{report_path}.rollbackPromotionAudit.toolchainSummary: expected "
            "non-empty object"
        )
    operator = audit.get("operatorIdentity")
    validate_explicit_text(
        errors,
        f"{report_path}.rollbackPromotionAudit.operatorIdentity",
        operator,
        "operatorIdentity",
    )
    validate_explicit_text(
        errors,
        f"{report_path}.rollbackPromotionAudit.decisionTime",
        audit.get("decisionTime"),
        "decisionTime",
    )

    release_prefix = validate_explicit_text(
        errors,
        f"{report_path}.rollbackPromotionAudit.releaseObjectPrefix",
        audit.get("releaseObjectPrefix"),
        "releaseObjectPrefix",
    )
    if release_prefix is not None:
        try:
            validate_release_object_prefix_text(release_prefix)
        except CheckError as exc:
            errors.append(
                f"{report_path}.rollbackPromotionAudit.releaseObjectPrefix: {exc}"
            )

    rollback_inputs = expect_object(
        errors,
        f"{report_path}.rollbackPromotionAudit.rollbackInputs",
        audit.get("rollbackInputs"),
    )
    if rollback_inputs is not None:
        for field in (
            "previousPromotionManifestPath",
            "previousVerifiedBundlePath",
            "rollbackPlanPath",
        ):
            validate_report_path(
                errors,
                f"{report_path}.rollbackPromotionAudit.rollbackInputs.{field}",
                rollback_inputs.get(field),
                field,
            )
        validate_explicit_text(
            errors,
            f"{report_path}.rollbackPromotionAudit.rollbackInputs.rollbackHorizon",
            rollback_inputs.get("rollbackHorizon"),
            "rollbackHorizon",
        )
        generations = rollback_inputs.get("publishedObjectGenerations")
        if not isinstance(generations, list):
            errors.append(
                f"{report_path}.rollbackPromotionAudit.rollbackInputs."
                "publishedObjectGenerations: expected list"
            )
        elif not generations:
            errors.append(
                f"{report_path}.rollbackPromotionAudit.rollbackInputs."
                "publishedObjectGenerations: expected non-empty list"
            )
        else:
            for index, generation in enumerate(generations):
                validate_published_object_generation_record(
                    errors,
                    f"{report_path}.rollbackPromotionAudit.rollbackInputs."
                    f"publishedObjectGenerations[{index}]",
                    generation,
                    release_prefix,
                )

    receipt_paths = expect_object(
        errors,
        f"{report_path}.rollbackPromotionAudit.receiptPaths",
        audit.get("receiptPaths"),
    )
    if receipt_paths is not None:
        for field in REPORT_ONLY_RECEIPT_PATH_GROUPS:
            validate_report_path_list(
                errors,
                f"{report_path}.rollbackPromotionAudit.receiptPaths.{field}",
                receipt_paths.get(field),
                allow_empty=field == "failedAttemptReceiptPaths",
            )
        validate_report_path(
            errors,
            f"{report_path}.rollbackPromotionAudit.receiptPaths.preflightReportPath",
            receipt_paths.get("preflightReportPath"),
            "preflightReportPath",
        )
        validate_report_provider_metadata(
            errors,
            f"{report_path}.rollbackPromotionAudit.receiptPaths.providerObjectMetadata",
            receipt_paths.get("providerObjectMetadata"),
        )

    allowlist_references = expect_object(
        errors,
        f"{report_path}.rollbackPromotionAudit.allowlistReferences",
        audit.get("allowlistReferences"),
    )
    if allowlist_references is not None:
        for field in (
            "projectAllowlistEntry",
            "bucketAllowlistEntry",
            "budgetGuardrail",
            "credentialsEnv",
        ):
            validate_explicit_text(
                errors,
                f"{report_path}.rollbackPromotionAudit.allowlistReferences.{field}",
                allowlist_references.get(field),
                field,
            )
        env_state = allowlist_references.get("liveCloudUploadOptInState")
        if env_state not in REPORT_ONLY_ENV_STATES:
            errors.append(
                f"{report_path}.rollbackPromotionAudit.allowlistReferences."
                "liveCloudUploadOptInState: expected one of "
                f"{sorted(REPORT_ONLY_ENV_STATES)!r}"
            )

    retention_review = expect_object(
        errors,
        f"{report_path}.rollbackPromotionAudit.retentionReview",
        audit.get("retentionReview"),
    )
    if retention_review is not None:
        for field in (
            "lifecyclePolicy",
            "retentionReview",
            "cleanupOwner",
            "rollbackHorizon",
        ):
            validate_explicit_text(
                errors,
                f"{report_path}.rollbackPromotionAudit.retentionReview.{field}",
                retention_review.get(field),
                field,
            )

    return errors


def manifest_artifact_paths(manifest: object) -> set[str]:
    if not isinstance(manifest, dict):
        return set()
    artifacts = manifest.get("artifacts")
    if not isinstance(artifacts, list):
        return set()
    return {
        artifact["path"]
        for artifact in artifacts
        if isinstance(artifact, dict) and isinstance(artifact.get("path"), str)
    }


def validate_release_evidence_reports(
    artifact_root: Path,
    manifest: object,
    report_paths: list[Path],
) -> list[str]:
    errors: list[str] = []
    artifact_paths = manifest_artifact_paths(manifest)
    for report_path in report_paths:
        resolved = report_path.resolve()
        try:
            relative = normalize_relative_path(artifact_root, resolved)
        except CheckError as exc:
            errors.append(f"{report_path}: {exc}")
            continue
        if relative not in artifact_paths:
            errors.append(
                f"{report_path}: release evidence report must be preserved as a "
                f"checksummed manifest artifact ({relative!r})"
            )
        try:
            report = load_json(resolved)
        except CheckError as exc:
            errors.append(str(exc))
            continue
        errors.extend(validate_release_evidence_report(str(report_path), report))
    return errors


def sample_live_approval_evidence() -> dict[str, Any]:
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


def sample_release_evidence_report(commit: str, provider_sha256: str) -> dict[str, Any]:
    return {
        "schemaVersion": 1,
        "kind": "crossgl-release-provenance-report-only-evidence",
        "rollbackPromotionAudit": {
            "dryRunDefault": True,
            "promotionDecision": "hold",
            "rejectionReason": "self-test keeps release promotion report-only",
            "promotionManifestPath": "release/package-release-promotion-manifest.json",
            "releaseBundleVerificationPath": (
                "release/package-release-bundle-verification.json"
            ),
            "packageVerification": {
                "path": "release/package-verify.json",
                "digest": provider_sha256,
            },
            "sourceCommit": commit,
            "toolchainSummary": {"cglc": "self-test", "python": "self-test"},
            "acceptedPackageSet": ["packages/SimpleShader.cglb"],
            "operatorIdentity": "release-operator:self-test",
            "decisionTime": "2026-06-01T00:00:00Z",
            "releaseObjectPrefix": "compiler/releases/v0.1.0",
            "rollbackInputs": {
                "previousPromotionManifestPath": (
                    "release/previous-promotion-manifest.json"
                ),
                "previousVerifiedBundlePath": "release/previous-verified-bundle.json",
                "publishedObjectGenerations": [
                    {
                        "objectName": "compiler/releases/v0.1.0/SimpleShader.dxil",
                        "generation": "1700000000000001",
                        "metageneration": "1",
                    }
                ],
                "rollbackPlanPath": "release/rollback-plan.json",
                "rollbackHorizon": "P14D",
            },
            "receiptPaths": {
                "uploadReceiptPaths": [
                    "release/package-release-publish-upload-batch.json",
                    "release/package-release-publish-upload-receipt.json",
                ],
                "dryRunReceiptPaths": [
                    "release/package-release-publish-gcs-dry-run-receipt.json",
                    "release/package-release-publish-upload-preflight.json",
                ],
                "failedAttemptReceiptPaths": [
                    "release/package-release-publish-failed-attempt-receipt.json"
                ],
                "preflightReportPath": (
                    "release/package-release-publish-upload-preflight.json"
                ),
                "providerObjectMetadata": [
                    {
                        "generation": "1700000000000001",
                        "metageneration": "1",
                        "crc32c": "AAAAAA==",
                        "md5": "1B2M2Y8AsgTpgAmY7PhCfg==",
                        "sha256": provider_sha256,
                        "sizeBytes": 13,
                    }
                ],
            },
            "allowlistReferences": {
                "projectAllowlistEntry": "gcp-project:crossgl-release-prod",
                "bucketAllowlistEntry": "gcs-bucket:crossgl-release-artifacts",
                "budgetGuardrail": "budget:crossgl-release-prod:v0",
                "credentialsEnv": "GOOGLE_APPLICATION_CREDENTIALS",
                "liveCloudUploadOptInState": "absent",
            },
            "retentionReview": {
                "lifecyclePolicy": "lifecycle:release-artifacts-retain-90d",
                "retentionReview": "receipts retained through rollback horizon",
                "cleanupOwner": "release-operator:self-test",
                "rollbackHorizon": "P14D",
            },
        },
    }


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def source_commit(root: Path) -> str:
    result = subprocess.run(
        ["git", "-C", str(root), "rev-parse", "HEAD"],
        check=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if result.returncode != 0:
        raise CheckError(
            "failed to resolve source commit with git rev-parse HEAD:\n"
            + result.stderr.strip()
        )
    commit = result.stdout.strip()
    if not COMMIT_RE.fullmatch(commit):
        raise CheckError(f"git returned invalid source commit {commit!r}")
    return commit


def parse_toolchain_items(items: list[str]) -> dict[str, str]:
    summary = {
        "python": platform.python_version(),
        "platform": platform.platform(),
    }
    for item in items:
        if "=" not in item:
            raise CheckError(f"toolchain entry must be KEY=VALUE: {item!r}")
        key, value = item.split("=", 1)
        key = key.strip()
        value = value.strip()
        if not key or not value:
            raise CheckError(
                f"toolchain entry must have non-empty key and value: {item!r}"
            )
        summary[key] = value
    return dict(sorted(summary.items()))


def normalize_relative_path(root: Path, path: Path) -> str:
    if not path.is_absolute():
        path = (root / path).resolve()
    else:
        path = path.resolve()
    try:
        relative = path.relative_to(root)
    except ValueError as exc:
        raise CheckError(f"artifact path is outside artifact root: {path}") from exc
    text = relative.as_posix()
    validate_artifact_path_text(text)
    return text


def normalize_optional_stage_path(root: Path, value: object) -> str | None:
    if not isinstance(value, str) or not value:
        return None
    path = Path(value)
    try:
        if path.is_absolute():
            return normalize_relative_path(root, path)
        validate_artifact_path_text(value)
        return value
    except CheckError:
        return None


def validate_artifact_path_text(path_text: str) -> None:
    if not path_text:
        raise CheckError("artifact path must not be empty")
    if "\\" in path_text:
        raise CheckError(f"artifact path must use POSIX separators: {path_text!r}")
    if WINDOWS_DRIVE_PATH_RE.match(path_text):
        raise CheckError(
            f"artifact path must not use a Windows drive prefix: {path_text!r}"
        )
    if URI_SCHEME_PATH_RE.match(path_text):
        raise CheckError(f"artifact path must not use a URI scheme: {path_text!r}")
    path = Path(path_text)
    if path.is_absolute():
        raise CheckError(f"artifact path must be artifact-root-relative: {path_text!r}")
    if any(part in {"", ".", ".."} for part in path_text.split("/")):
        raise CheckError(
            f"artifact path must not contain empty/current/parent parts: {path_text!r}"
        )


def validate_release_object_prefix_text(path_text: str) -> None:
    validate_artifact_path_text(path_text)
    parts = path_text.split("/")
    if len(parts) < 2:
        raise CheckError(
            "releaseObjectPrefix must include a namespace and release identifier"
        )
    lower_parts = [part.lower() for part in parts]
    if lower_parts[0] in RELEASE_OBJECT_PREFIX_GENERIC_SEGMENTS:
        raise CheckError(
            "releaseObjectPrefix must not start with a shared or temporary prefix"
        )
    if lower_parts[-1] in RELEASE_OBJECT_PREFIX_GENERIC_SEGMENTS:
        raise CheckError(
            "releaseObjectPrefix must end with a concrete release identifier"
        )
    if RELEASE_OBJECT_PREFIX_HINT_RE.search(path_text.lower()) is None:
        raise CheckError(
            "releaseObjectPrefix must include a release namespace or release id"
        )


def resolve_stage_artifact(
    root: Path, stage_report_path: Path, stage: dict[str, Any], text: str
) -> Path:
    path = Path(text)
    if path.is_absolute():
        return path.resolve()

    candidates = [
        (root / path).resolve(),
        (stage_report_path.parent / path).resolve(),
    ]
    stage_path = stage.get("stagePath")
    if isinstance(stage_path, str) and stage_path:
        stage_root = Path(stage_path)
        if not stage_root.is_absolute():
            stage_root = root / stage_root
        candidates.append((stage_root / path).resolve())

    for candidate in candidates:
        if candidate.exists():
            return candidate
    return candidates[0]


def collect_file_artifacts(root: Path, paths: list[Path]) -> list[dict[str, Any]]:
    artifacts: list[dict[str, Any]] = []
    for path in paths:
        absolute = path if path.is_absolute() else root / path
        absolute = absolute.resolve()
        if absolute.is_dir():
            files = sorted(child for child in absolute.rglob("*") if child.is_file())
        else:
            files = [absolute]
        for file_path in files:
            if not file_path.is_file():
                raise CheckError(f"artifact is not a regular file: {file_path}")
            artifacts.append(
                {
                    "path": normalize_relative_path(root, file_path),
                    "sizeBytes": file_path.stat().st_size,
                    "sha256": sha256_file(file_path),
                }
            )
    return sorted(artifacts, key=lambda artifact: artifact["path"])


def artifacts_from_stage_report(
    root: Path, stage_report_path: Path
) -> list[dict[str, Any]]:
    stage = load_json(stage_report_path)
    if not isinstance(stage, dict):
        raise CheckError(f"{stage_report_path}: stage report must be a JSON object")
    records = stage.get("artifacts")
    if not isinstance(records, list):
        raise CheckError(f"{stage_report_path}: artifacts must be a list")

    artifacts: list[dict[str, Any]] = []
    for index, record in enumerate(records):
        if not isinstance(record, dict):
            raise CheckError(
                f"{stage_report_path}: artifacts[{index}] must be an object"
            )
        staged_path = record.get("stagedPath")
        if not isinstance(staged_path, str) or not staged_path:
            raise CheckError(
                f"{stage_report_path}: artifacts[{index}].stagedPath is required"
            )
        absolute = resolve_stage_artifact(root, stage_report_path, stage, staged_path)
        if not absolute.is_file():
            raise CheckError(
                f"{stage_report_path}: staged artifact is not a file: {staged_path}"
            )
        actual_sha256 = sha256_file(absolute)
        recorded_sha256 = record.get("sha256")
        if recorded_sha256 != actual_sha256:
            raise CheckError(
                f"{stage_report_path}: artifacts[{index}].sha256 does not match {staged_path}"
            )
        recorded_size = record.get("sizeBytes")
        actual_size = absolute.stat().st_size
        if recorded_size != actual_size:
            raise CheckError(
                f"{stage_report_path}: artifacts[{index}].sizeBytes does not match {staged_path}"
            )
        artifact = {
            "path": normalize_relative_path(root, absolute),
            "destinationPath": record.get("destinationPath", ""),
            "packageArtifactPath": record.get("packageArtifactPath", ""),
            "sizeBytes": actual_size,
            "sha256": actual_sha256,
        }
        package_path = normalize_optional_stage_path(root, record.get("packagePath"))
        if package_path is not None:
            artifact["packagePath"] = package_path
        artifacts.append(artifact)
    return sorted(artifacts, key=lambda artifact: artifact["path"])


def validate_guardrail_mode_flags(
    errors: list[str], path: str, record: dict[str, Any], mode: str
) -> None:
    for field in (*GUARDRAIL_MODE_FLAG_FIELDS, "liveCloudUploadAllowed"):
        if field in record and not isinstance(record[field], bool):
            errors.append(f"{path}.{field}: expected boolean")

    if mode in SAFE_CLOUD_MODE_FLAGS:
        expected_field = SAFE_CLOUD_MODE_FLAGS[mode]
        for field in GUARDRAIL_MODE_FLAG_FIELDS:
            if field == expected_field:
                if record.get(field) is not True:
                    errors.append(f"{path}.{field}: expected true for {mode!r} mode")
            elif record.get(field) is True:
                errors.append(f"{path}.{field}: must be false for {mode!r} mode")
        return

    if mode == LIVE_CLOUD_MODE:
        for field in GUARDRAIL_MODE_FLAG_FIELDS:
            if record.get(field) is True:
                errors.append(
                    f"{path}.{field}: must be false for {LIVE_CLOUD_MODE!r} mode"
                )
        if record.get("liveCloudUploadAllowed") is not True:
            errors.append(
                f"{path}.liveCloudUploadAllowed: expected true for "
                f"{LIVE_CLOUD_MODE!r} mode"
            )
        validate_live_opt_in_source(
            errors, f"{path}.liveCloudUploadOptIn", record.get("liveCloudUploadOptIn")
        )


def validate_guardrail_record_shape(
    path: Path, index: int, record: dict[str, Any], allow_cloud_upload: bool
) -> list[str]:
    record_path = f"{path}: records[{index}]"
    errors: list[str] = []

    operation = record.get("operation")
    if not isinstance(operation, str) or not operation:
        errors.append(f"{record_path}.operation: expected non-empty string")

    target_kind = record.get("targetKind")
    if not isinstance(target_kind, str) or not target_kind:
        errors.append(f"{record_path}.targetKind: expected non-empty string")

    mode = record.get("mode")
    if not isinstance(mode, str) or not mode:
        errors.append(f"{record_path}.mode: expected non-empty string")
        return errors

    if target_kind != "gcs":
        return errors

    if mode not in KNOWN_CLOUD_MODES:
        errors.append(
            f"{record_path}.mode: expected one of {cloud_mode_list()}, got {mode!r}"
        )
        return errors

    validate_guardrail_mode_flags(errors, record_path, record, mode)

    if is_live_cloud_mode(mode) and not live_cloud_opted_in(allow_cloud_upload):
        errors.append(
            f"{record_path} requests live cloud mode {mode!r} without "
            f"--allow-cloud-upload or {LIVE_CLOUD_UPLOAD_ENV}=1"
        )
    if is_live_cloud_mode(mode):
        validate_live_approval_evidence(
            errors,
            f"{record_path}.approvalEvidence",
            record.get("approvalEvidence"),
        )
    if record.get("liveCloudUploadAllowed") is True and not live_cloud_opted_in(
        allow_cloud_upload
    ):
        errors.append(
            f"{record_path} allows live cloud upload without --allow-cloud-upload "
            f"or {LIVE_CLOUD_UPLOAD_ENV}=1"
        )

    return errors


def guardrail_modes(path: Path, allow_cloud_upload: bool) -> list[str]:
    payload = load_json(path)
    if not isinstance(payload, dict):
        raise CheckError(f"{path}: guardrail payload must be an object")
    if payload.get("schemaVersion") != 1:
        raise CheckError(f"{path}: schemaVersion must be 1")
    records = payload.get("records")
    if not isinstance(records, list):
        raise CheckError(f"{path}: records must be a list")

    modes: set[str] = set()
    for index, record in enumerate(records):
        if not isinstance(record, dict):
            raise CheckError(f"{path}: records[{index}] must be an object")
        record_errors = validate_guardrail_record_shape(
            path, index, record, allow_cloud_upload
        )
        if record_errors:
            raise CheckError("; ".join(record_errors))
        target_kind = record.get("targetKind")
        mode = record.get("mode")
        if target_kind == "gcs" and isinstance(mode, str) and mode:
            modes.add(mode)
    return sorted(modes)


def manifest_contains_cloud_uri(value: Any) -> bool:
    if isinstance(value, str):
        return value.startswith(CLOUD_URI_PREFIXES)
    if isinstance(value, list):
        return any(manifest_contains_cloud_uri(item) for item in value)
    if isinstance(value, dict):
        return any(manifest_contains_cloud_uri(item) for item in value.values())
    return False


def build_manifest(
    *,
    artifacts: list[dict[str, Any]],
    commit: str,
    toolchain_summary: dict[str, str],
    guardrail_paths: list[Path],
    allow_cloud_upload: bool,
    approval_evidence: dict[str, Any] | None = None,
) -> dict[str, Any]:
    modes: set[str] = set()
    for guardrail_path in guardrail_paths:
        modes.update(guardrail_modes(guardrail_path, allow_cloud_upload))
    if not modes:
        modes.add("local-only")

    artifact_count = len(artifacts)
    artifact_bytes = sum(int(artifact["sizeBytes"]) for artifact in artifacts)
    cloud_upload = {
        "mode": "dry-run" if "dry-run" in modes else sorted(modes)[0],
        "modes": sorted(modes),
        "liveCloudUploadAllowed": live_cloud_opted_in(allow_cloud_upload),
        "liveCloudUploadOptIn": (
            "cli-flag"
            if allow_cloud_upload
            else LIVE_CLOUD_UPLOAD_ENV
            if env_flag_enabled(LIVE_CLOUD_UPLOAD_ENV)
            else None
        ),
    }
    if approval_evidence is not None:
        cloud_upload["approvalEvidence"] = approval_evidence

    return {
        "schemaVersion": SCHEMA_VERSION,
        "kind": MANIFEST_KIND,
        "sourceCommit": commit,
        "toolchainSummary": toolchain_summary,
        "cloudUpload": cloud_upload,
        "artifactCount": artifact_count,
        "artifactBytes": artifact_bytes,
        "artifacts": artifacts,
    }


def expect_object(errors: list[str], path: str, value: Any) -> dict[str, Any] | None:
    if not isinstance(value, dict):
        errors.append(f"{path}: expected object")
        return None
    return value


def validate_manifest(
    root: Path, manifest: Any, *, allow_cloud_upload: bool
) -> list[str]:
    errors: list[str] = []
    payload = expect_object(errors, "$", manifest)
    if payload is None:
        return errors

    if payload.get("schemaVersion") != SCHEMA_VERSION:
        errors.append("$.schemaVersion: expected 1")
    if payload.get("kind") != MANIFEST_KIND:
        errors.append(f"$.kind: expected {MANIFEST_KIND!r}")
    commit = payload.get("sourceCommit")
    if not isinstance(commit, str) or not COMMIT_RE.fullmatch(commit):
        errors.append("$.sourceCommit: expected 40-character lowercase hex commit")

    toolchain = payload.get("toolchainSummary")
    if not isinstance(toolchain, dict) or not toolchain:
        errors.append("$.toolchainSummary: expected non-empty object")
    elif not all(
        isinstance(key, str) and isinstance(value, str) and value
        for key, value in toolchain.items()
    ):
        errors.append(
            "$.toolchainSummary: expected string keys and non-empty string values"
        )

    cloud = expect_object(errors, "$.cloudUpload", payload.get("cloudUpload"))
    if cloud is not None:
        mode = cloud.get("mode")
        live_modes: set[str] = set()
        if not isinstance(mode, str) or not mode:
            errors.append("$.cloudUpload.mode: expected non-empty string")
        elif mode not in KNOWN_CLOUD_MODES:
            errors.append(f"$.cloudUpload.mode: expected one of {cloud_mode_list()}")
        elif is_live_cloud_mode(mode):
            live_modes.add(mode)
            if not live_cloud_opted_in(allow_cloud_upload):
                errors.append(
                    "$.cloudUpload.mode: live cloud mode requires "
                    f"--allow-cloud-upload or {LIVE_CLOUD_UPLOAD_ENV}=1"
                )
        modes = cloud.get("modes")
        if not isinstance(modes, list) or not modes:
            errors.append("$.cloudUpload.modes: expected non-empty list")
        elif any(not isinstance(item, str) or not item for item in modes):
            errors.append("$.cloudUpload.modes: expected non-empty string items")
        else:
            unknown_modes = sorted(
                {item for item in modes if item not in KNOWN_CLOUD_MODES}
            )
            if unknown_modes:
                errors.append(
                    "$.cloudUpload.modes: expected known modes "
                    f"{cloud_mode_list()}, got {unknown_modes!r}"
                )
            if isinstance(mode, str) and mode and mode not in modes:
                errors.append("$.cloudUpload.mode: must be included in modes")
            live_modes.update(item for item in modes if is_live_cloud_mode(item))
            if live_modes and not live_cloud_opted_in(allow_cloud_upload):
                errors.append(
                    "$.cloudUpload.modes: live cloud modes require "
                    f"--allow-cloud-upload or {LIVE_CLOUD_UPLOAD_ENV}=1"
                )
        if cloud.get("liveCloudUploadAllowed") is True and not live_cloud_opted_in(
            allow_cloud_upload
        ):
            errors.append(
                "$.cloudUpload.liveCloudUploadAllowed: must be false unless "
                f"--allow-cloud-upload or {LIVE_CLOUD_UPLOAD_ENV}=1 is set"
            )
        approval_evidence = cloud.get("approvalEvidence")
        if live_modes and approval_evidence is None:
            errors.append(
                "$.cloudUpload.approvalEvidence: required for live cloud modes"
            )
        elif approval_evidence is not None:
            validate_live_approval_evidence(
                errors,
                "$.cloudUpload.approvalEvidence",
                approval_evidence,
            )
        if live_modes:
            if cloud.get("liveCloudUploadAllowed") is not True:
                errors.append(
                    "$.cloudUpload.liveCloudUploadAllowed: expected true for "
                    "live cloud modes"
                )
            validate_live_opt_in_source(
                errors,
                "$.cloudUpload.liveCloudUploadOptIn",
                cloud.get("liveCloudUploadOptIn"),
            )
    if manifest_contains_cloud_uri(payload) and cloud is not None:
        mode = cloud.get("mode")
        if is_live_cloud_mode(mode) and not live_cloud_opted_in(allow_cloud_upload):
            errors.append(
                "cloud URI references require a dry-run/mock/local-only mode or explicit opt-in"
            )

    artifacts = payload.get("artifacts")
    if not isinstance(artifacts, list) or not artifacts:
        errors.append("$.artifacts: expected non-empty list")
        return errors

    seen_paths: set[str] = set()
    seen_destination_paths: set[str] = set()
    seen_package_artifacts: set[tuple[str, str]] = set()
    total_bytes = 0
    for index, artifact in enumerate(artifacts):
        record = expect_object(errors, f"$.artifacts[{index}]", artifact)
        if record is None:
            continue
        path_text = ""
        relative_paths: dict[str, str] = {}
        for field in ARTIFACT_RELATIVE_PATH_FIELDS:
            field_path = record.get(field)
            if field == "path" and not isinstance(field_path, str):
                errors.append(f"$.artifacts[{index}].path: expected string")
                continue
            if field_path in (None, ""):
                continue
            if not isinstance(field_path, str):
                errors.append(f"$.artifacts[{index}].{field}: expected string")
                continue
            try:
                validate_artifact_path_text(field_path)
            except CheckError as exc:
                errors.append(f"$.artifacts[{index}].{field}: {exc}")
                continue
            relative_paths[field] = field_path
            if field == "path":
                path_text = field_path
        if not path_text:
            continue
        if path_text in seen_paths:
            errors.append(
                f"$.artifacts[{index}].path: duplicate artifact path {path_text!r}"
            )
        seen_paths.add(path_text)

        destination_path = relative_paths.get("destinationPath")
        if destination_path is not None:
            if destination_path in seen_destination_paths:
                errors.append(
                    f"$.artifacts[{index}].destinationPath: duplicate artifact "
                    f"destination {destination_path!r}"
                )
            seen_destination_paths.add(destination_path)

        package_path = relative_paths.get("packagePath")
        package_artifact_path = relative_paths.get("packageArtifactPath")
        if package_path is not None and package_artifact_path is not None:
            package_identity = (package_path, package_artifact_path)
            if package_identity in seen_package_artifacts:
                errors.append(
                    f"$.artifacts[{index}].packageArtifactPath: duplicate package "
                    f"artifact identity {(package_path, package_artifact_path)!r}"
                )
            seen_package_artifacts.add(package_identity)

        artifact_path = root / path_text
        if not artifact_path.is_file():
            errors.append(
                f"$.artifacts[{index}].path: file does not exist: {path_text}"
            )
            continue
        actual_size = artifact_path.stat().st_size
        size_bytes = record.get("sizeBytes")
        if not isinstance(size_bytes, int) or size_bytes < 0:
            errors.append(
                f"$.artifacts[{index}].sizeBytes: expected non-negative integer"
            )
        elif size_bytes != actual_size:
            errors.append(f"$.artifacts[{index}].sizeBytes: expected {actual_size}")
        else:
            total_bytes += size_bytes

        digest = record.get("sha256")
        if not isinstance(digest, str) or not SHA256_RE.fullmatch(digest):
            errors.append(f"$.artifacts[{index}].sha256: expected lowercase SHA-256")
        elif digest != sha256_file(artifact_path):
            errors.append(f"$.artifacts[{index}].sha256: does not match {path_text}")

    if payload.get("artifactCount") != len(artifacts):
        errors.append("$.artifactCount: does not match artifacts length")
    if (
        isinstance(payload.get("artifactBytes"), int)
        and payload.get("artifactBytes") != total_bytes
    ):
        errors.append("$.artifactBytes: does not match artifact sizes")
    elif not isinstance(payload.get("artifactBytes"), int):
        errors.append("$.artifactBytes: expected integer")
    return errors


def run_self_test() -> None:
    commit = "0" * 40
    with tempfile.TemporaryDirectory(prefix="crossgl-release-provenance-") as tmp:
        root = Path(tmp).resolve()
        artifact = root / "build" / "release-stage" / "SimpleShader.dxil"
        artifact.parent.mkdir(parents=True)
        artifact.write_bytes(b"shader-bytes\n")
        guardrails = root / "guardrails.json"
        package_root = root / "packages" / "SimpleShader.cglb"
        package_root.mkdir(parents=True)
        stage_report = root / "stage.json"
        release_dir = root / "release"
        evidence_report = release_dir / "rollback-promotion-audit.json"
        for relative_path in (
            "release/package-release-promotion-manifest.json",
            "release/package-release-bundle-verification.json",
            "release/package-verify.json",
            "release/previous-promotion-manifest.json",
            "release/previous-verified-bundle.json",
            "release/rollback-plan.json",
            "release/package-release-publish-upload-manifest.json",
            "release/package-release-publish-gcs-dry-run-receipt.json",
            "release/package-release-publish-upload-preflight.json",
            "release/package-release-publish-upload-batch.json",
            "release/package-release-publish-upload-receipt.json",
            "release/package-release-publish-failed-attempt-receipt.json",
        ):
            write_json(
                root / relative_path,
                {
                    "schemaVersion": 1,
                    "kind": Path(relative_path).stem,
                    "success": True,
                },
            )
        write_json(
            evidence_report,
            sample_release_evidence_report(commit, sha256_file(artifact)),
        )
        write_json(
            guardrails,
            {
                "schemaVersion": 1,
                "records": [
                    {
                        "operation": "self-test-dry-run",
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
        write_json(
            stage_report,
            {
                "schemaVersion": 1,
                "stagePath": str(artifact.parent),
                "artifacts": [
                    {
                        "stagedPath": str(artifact),
                        "destinationPath": "SimpleShader.dxil",
                        "packagePath": str(package_root),
                        "packageArtifactPath": "out/SimpleShader.dxil",
                        "sizeBytes": artifact.stat().st_size,
                        "sha256": sha256_file(artifact),
                    }
                ],
            },
        )
        staged_artifacts = artifacts_from_stage_report(root, stage_report)
        release_artifacts = collect_file_artifacts(root, [release_dir])
        if staged_artifacts[0].get("packagePath") != "packages/SimpleShader.cglb":
            raise CheckError("self-test: absolute packagePath was not normalized")
        manifest = build_manifest(
            artifacts=sorted(
                [*staged_artifacts, *release_artifacts],
                key=lambda artifact: artifact["path"],
            ),
            commit=commit,
            toolchain_summary={"python": "self-test", "cglc": "self-test"},
            guardrail_paths=[guardrails],
            allow_cloud_upload=False,
        )
        errors = validate_manifest(root, manifest, allow_cloud_upload=False)
        if errors:
            raise CheckError("self-test: valid manifest failed: " + "; ".join(errors))
        errors = validate_release_evidence_reports(root, manifest, [evidence_report])
        if errors:
            raise CheckError(
                "self-test: release evidence report failed: " + "; ".join(errors)
            )

        unpreserved_report = json.loads(json.dumps(manifest))
        unpreserved_report["artifacts"] = [
            artifact_record
            for artifact_record in unpreserved_report["artifacts"]
            if artifact_record["path"] != "release/rollback-promotion-audit.json"
        ]
        errors = validate_release_evidence_reports(
            root, unpreserved_report, [evidence_report]
        )
        if not any("checksummed manifest artifact" in error for error in errors):
            raise CheckError(
                "self-test: unpreserved release evidence report was accepted"
            )

        bad_report = load_json(evidence_report)
        del bad_report["rollbackPromotionAudit"]["allowlistReferences"][
            "budgetGuardrail"
        ]
        errors = validate_release_evidence_report("self-test-report", bad_report)
        if not any("budgetGuardrail" in error for error in errors):
            raise CheckError("self-test: missing budget guardrail was accepted")

        bad_report = load_json(evidence_report)
        bad_report["rollbackPromotionAudit"]["releaseObjectPrefix"] = "scratch/latest"
        errors = validate_release_evidence_report("self-test-report", bad_report)
        if not any("releaseObjectPrefix" in error for error in errors):
            raise CheckError("self-test: shared release object prefix was accepted")

        bad_report = load_json(evidence_report)
        bad_report["rollbackPromotionAudit"]["rollbackInputs"][
            "publishedObjectGenerations"
        ][0]["objectName"] = "compiler/releases/v0.2.0/SimpleShader.dxil"
        errors = validate_release_evidence_report("self-test-report", bad_report)
        if not any(
            "expected object under releaseObjectPrefix" in error for error in errors
        ):
            raise CheckError("self-test: out-of-prefix published object was accepted")

        bad_report = load_json(evidence_report)
        del bad_report["rollbackPromotionAudit"]["receiptPaths"]["preflightReportPath"]
        errors = validate_release_evidence_report("self-test-report", bad_report)
        if not any("preflightReportPath" in error for error in errors):
            raise CheckError("self-test: missing preflight report path was accepted")

        bad_report = load_json(evidence_report)
        del bad_report["rollbackPromotionAudit"]["rollbackInputs"]["rollbackPlanPath"]
        errors = validate_release_evidence_report("self-test-report", bad_report)
        if not any("rollbackPlanPath" in error for error in errors):
            raise CheckError("self-test: missing rollback plan path was accepted")

        bad_report = load_json(evidence_report)
        del bad_report["rollbackPromotionAudit"]["receiptPaths"][
            "providerObjectMetadata"
        ][0]["generation"]
        errors = validate_release_evidence_report("self-test-report", bad_report)
        if not any("generation" in error for error in errors):
            raise CheckError(
                "self-test: missing provider metadata generation was accepted"
            )

        bad_hash = json.loads(json.dumps(manifest))
        bad_hash["artifacts"][0]["sha256"] = "1" * 64
        errors = validate_manifest(root, bad_hash, allow_cloud_upload=False)
        if not any("sha256" in error for error in errors):
            raise CheckError("self-test: bad checksum was accepted")

        bad_path = json.loads(json.dumps(manifest))
        bad_path["artifacts"][0]["packagePath"] = str(package_root)
        errors = validate_manifest(root, bad_path, allow_cloud_upload=False)
        if not any("packagePath" in error for error in errors):
            raise CheckError("self-test: absolute packagePath was accepted")

        bad_windows_path = json.loads(json.dumps(manifest))
        bad_windows_path["artifacts"][0]["path"] = "C:/release/SimpleShader.dxil"
        errors = validate_manifest(root, bad_windows_path, allow_cloud_upload=False)
        if not any("Windows drive prefix" in error for error in errors):
            raise CheckError("self-test: Windows drive artifact path was accepted")

        bad_uri_path = json.loads(json.dumps(manifest))
        bad_uri_path["artifacts"][0]["packageArtifactPath"] = (
            "file:out/SimpleShader.dxil"
        )
        errors = validate_manifest(root, bad_uri_path, allow_cloud_upload=False)
        if not any("URI scheme" in error for error in errors):
            raise CheckError("self-test: URI-like package artifact path was accepted")

        duplicate_artifact = root / "build" / "release-stage" / "SimpleShader.map"
        duplicate_artifact.write_bytes(b"shader-map\n")
        duplicate_identity = json.loads(json.dumps(manifest))
        duplicate_record = json.loads(json.dumps(duplicate_identity["artifacts"][0]))
        duplicate_record["path"] = normalize_relative_path(root, duplicate_artifact)
        duplicate_record["sizeBytes"] = duplicate_artifact.stat().st_size
        duplicate_record["sha256"] = sha256_file(duplicate_artifact)
        duplicate_identity["artifacts"].append(duplicate_record)
        duplicate_identity["artifactCount"] = len(duplicate_identity["artifacts"])
        duplicate_identity["artifactBytes"] += duplicate_record["sizeBytes"]
        errors = validate_manifest(root, duplicate_identity, allow_cloud_upload=False)
        if not any("duplicate artifact destination" in error for error in errors):
            raise CheckError("self-test: duplicate destinationPath was accepted")
        if not any("duplicate package artifact identity" in error for error in errors):
            raise CheckError("self-test: duplicate package artifact was accepted")

        bad_cloud = json.loads(json.dumps(manifest))
        bad_cloud["cloudUpload"]["mode"] = LIVE_CLOUD_MODE
        bad_cloud["cloudUpload"]["modes"] = [LIVE_CLOUD_MODE]
        errors = validate_manifest(root, bad_cloud, allow_cloud_upload=False)
        if not any("live cloud mode" in error for error in errors):
            raise CheckError("self-test: live cloud mode was accepted")
        errors = validate_manifest(root, bad_cloud, allow_cloud_upload=True)
        if not any("approvalEvidence" in error for error in errors):
            raise CheckError(
                "self-test: live cloud mode without approval evidence was accepted"
            )

        live_cloud = json.loads(json.dumps(bad_cloud))
        live_cloud["cloudUpload"]["approvalEvidence"] = sample_live_approval_evidence()
        errors = validate_manifest(root, live_cloud, allow_cloud_upload=True)
        if not any("liveCloudUploadOptIn" in error for error in errors):
            raise CheckError(
                "self-test: live cloud mode without opt-in source was accepted"
            )

        missing_allowed_marker = json.loads(json.dumps(live_cloud))
        missing_allowed_marker["cloudUpload"]["liveCloudUploadOptIn"] = "cli-flag"
        errors = validate_manifest(
            root, missing_allowed_marker, allow_cloud_upload=True
        )
        if not any("liveCloudUploadAllowed" in error for error in errors):
            raise CheckError(
                "self-test: live cloud mode without allowed marker was accepted"
            )

        live_cloud["cloudUpload"]["liveCloudUploadAllowed"] = True
        live_cloud["cloudUpload"]["liveCloudUploadOptIn"] = "cli-flag"
        errors = validate_manifest(root, live_cloud, allow_cloud_upload=True)
        if errors:
            raise CheckError(
                "self-test: live cloud mode with approval evidence failed: "
                + "; ".join(errors)
            )

        for field, placeholder in (
            ("projectAllowlistEntry", "<approved-gcp-project-id>"),
            ("bucketAllowlistEntry", "<approved-gcp-bucket>"),
            ("budgetGuardrail", "<approved-budget-limit>"),
            ("lifecyclePolicy", "<approved-lifecycle-policy-id>"),
            ("releaseObjectPrefix", "<approved-release-object-prefix>"),
        ):
            placeholder_evidence = json.loads(json.dumps(live_cloud))
            placeholder_evidence["cloudUpload"]["approvalEvidence"][field] = placeholder
            errors = validate_manifest(
                root, placeholder_evidence, allow_cloud_upload=True
            )
            if not any(field in error and "placeholder" in error for error in errors):
                raise CheckError(
                    f"self-test: placeholder approval evidence field {field} "
                    "was accepted"
                )

        placeholder_receipt = json.loads(json.dumps(live_cloud))
        placeholder_receipt["cloudUpload"]["approvalEvidence"]["auditReceiptPaths"][
            0
        ] = "<approved-audit-receipt>"
        errors = validate_manifest(root, placeholder_receipt, allow_cloud_upload=True)
        if not any(
            "auditReceiptPaths" in error and "placeholder" in error for error in errors
        ):
            raise CheckError("self-test: placeholder audit receipt path was accepted")

        shared_prefix = json.loads(json.dumps(live_cloud))
        shared_prefix["cloudUpload"]["approvalEvidence"]["releaseObjectPrefix"] = (
            "scratch/latest"
        )
        errors = validate_manifest(root, shared_prefix, allow_cloud_upload=True)
        if not any("releaseObjectPrefix" in error for error in errors):
            raise CheckError("self-test: shared release object prefix was accepted")

        missing_budget_evidence = json.loads(json.dumps(live_cloud))
        del missing_budget_evidence["cloudUpload"]["approvalEvidence"][
            "budgetGuardrail"
        ]
        errors = validate_manifest(
            root, missing_budget_evidence, allow_cloud_upload=True
        )
        if not any("budgetGuardrail" in error for error in errors):
            raise CheckError("self-test: missing budget approval evidence was accepted")

        unknown_mode = json.loads(json.dumps(manifest))
        unknown_mode["cloudUpload"]["mode"] = "dryrun"
        unknown_mode["cloudUpload"]["modes"] = ["dryrun"]
        errors = validate_manifest(root, unknown_mode, allow_cloud_upload=True)
        if not any(
            "known modes" in error or "expected one of" in error for error in errors
        ):
            raise CheckError("self-test: unknown cloudUpload mode was accepted")

        missing_mode_membership = json.loads(json.dumps(manifest))
        missing_mode_membership["cloudUpload"]["mode"] = "dry-run"
        missing_mode_membership["cloudUpload"]["modes"] = ["mock"]
        errors = validate_manifest(
            root, missing_mode_membership, allow_cloud_upload=False
        )
        if not any("must be included in modes" in error for error in errors):
            raise CheckError(
                "self-test: cloudUpload primary mode mismatch was accepted"
            )

        write_json(
            guardrails,
            {
                "schemaVersion": 1,
                "records": [
                    {
                        "operation": "self-test-malformed-dry-run",
                        "targetKind": "gcs",
                        "mode": "dry-run",
                        "liveCloudUploadAllowed": False,
                    }
                ],
            },
        )
        try:
            guardrail_modes(guardrails, allow_cloud_upload=False)
        except CheckError as exc:
            if "dryRun" not in str(exc):
                raise CheckError(
                    "self-test: malformed dry-run guardrail did not name dryRun"
                ) from exc
        else:
            raise CheckError("self-test: dry-run guardrail without flag was accepted")

        write_json(
            guardrails,
            {
                "schemaVersion": 1,
                "records": [
                    {
                        "operation": "self-test-conflicting-dry-run",
                        "targetKind": "gcs",
                        "mode": "dry-run",
                        "dryRun": True,
                        "mockUpload": True,
                        "liveCloudUploadAllowed": False,
                    }
                ],
            },
        )
        try:
            guardrail_modes(guardrails, allow_cloud_upload=False)
        except CheckError as exc:
            if "mockUpload" not in str(exc):
                raise CheckError(
                    "self-test: conflicting dry-run guardrail did not name mockUpload"
                ) from exc
        else:
            raise CheckError("self-test: conflicting dry-run guardrail was accepted")

        write_json(
            guardrails,
            {
                "schemaVersion": 1,
                "records": [
                    {
                        "operation": "self-test-live-upload",
                        "targetKind": "gcs",
                        "mode": LIVE_CLOUD_MODE,
                        "dryRun": False,
                        "localOnly": False,
                        "mockUpload": False,
                        "liveCloudUploadAllowed": True,
                        "liveCloudUploadOptIn": "cli-flag",
                    }
                ],
            },
        )
        try:
            guardrail_modes(guardrails, allow_cloud_upload=False)
        except CheckError as exc:
            if LIVE_CLOUD_UPLOAD_ENV not in str(exc):
                raise CheckError(
                    "self-test: guardrail denial did not name opt-in"
                ) from exc
        else:
            raise CheckError("self-test: live guardrail was accepted")

        try:
            guardrail_modes(guardrails, allow_cloud_upload=True)
        except CheckError as exc:
            if "approvalEvidence" not in str(exc):
                raise CheckError(
                    "self-test: guardrail approval denial did not name evidence"
                ) from exc
        else:
            raise CheckError("self-test: live guardrail without evidence was accepted")

        write_json(
            guardrails,
            {
                "schemaVersion": 1,
                "records": [
                    {
                        "operation": "self-test-live-upload-with-evidence",
                        "targetKind": "gcs",
                        "mode": LIVE_CLOUD_MODE,
                        "dryRun": False,
                        "localOnly": False,
                        "mockUpload": False,
                        "liveCloudUploadAllowed": True,
                        "liveCloudUploadOptIn": "cli-flag",
                        "approvalEvidence": sample_live_approval_evidence(),
                    }
                ],
            },
        )
        if guardrail_modes(guardrails, allow_cloud_upload=True) != [LIVE_CLOUD_MODE]:
            raise CheckError("self-test: live guardrail evidence was not preserved")


def validate_root_audit(root: Path) -> list[str]:
    errors: list[str] = []
    try:
        run_self_test()
    except CheckError as exc:
        errors.append(f"checker self-test failed: {exc}")
    return errors


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument(
        "--artifact-root",
        type=Path,
        help="Base directory for manifest artifact paths; defaults to --root",
    )
    parser.add_argument("--manifest", type=Path, help="Existing manifest to validate")
    parser.add_argument(
        "--manifest-output", type=Path, help="Write and validate a manifest"
    )
    parser.add_argument(
        "--from-stage-report",
        type=Path,
        help="Build artifacts from a publish stage report",
    )
    parser.add_argument(
        "--artifact",
        type=Path,
        action="append",
        default=[],
        help="File or directory artifact to hash",
    )
    parser.add_argument(
        "--guardrails",
        type=Path,
        action="append",
        default=[],
        help="Release guardrail JSON to summarize",
    )
    parser.add_argument(
        "--approval-evidence",
        type=Path,
        help=(
            "JSON approval evidence required when a provenance manifest records "
            "a live cloud upload mode."
        ),
    )
    parser.add_argument(
        "--release-evidence-report",
        type=Path,
        action="append",
        default=[],
        help=(
            "Report-only rollback/promotion/cost evidence JSON to validate and "
            "require as a checksummed manifest artifact."
        ),
    )
    parser.add_argument(
        "--source-commit", help="Source commit to record; defaults to git HEAD"
    )
    parser.add_argument(
        "--toolchain",
        action="append",
        default=[],
        help="Toolchain summary entry as KEY=VALUE",
    )
    parser.add_argument(
        "--allow-cloud-upload",
        action="store_true",
        help="Allow a manifest or guardrail record to cite live cloud upload mode.",
    )
    parser.add_argument(
        "--self-test", action="store_true", help="Run offline checker self-tests"
    )
    return parser.parse_args(argv)


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    if args.self_test:
        run_self_test()
        print("validated release provenance manifest checker self-test")
        return 0

    root = args.root.resolve()
    artifact_root = (
        args.artifact_root.resolve() if args.artifact_root is not None else root
    )
    manifest_path = args.manifest
    if args.manifest_output is not None:
        artifact_records: list[dict[str, Any]] = []
        if args.from_stage_report is not None:
            artifact_records.extend(
                artifacts_from_stage_report(
                    artifact_root, args.from_stage_report.resolve()
                )
            )
        if args.artifact:
            artifact_records.extend(
                collect_file_artifacts(artifact_root, args.artifact)
            )
        if not artifact_records:
            raise CheckError(
                "--manifest-output requires --from-stage-report or --artifact"
            )
        manifest = build_manifest(
            artifacts=sorted(artifact_records, key=lambda artifact: artifact["path"]),
            commit=args.source_commit or source_commit(root),
            toolchain_summary=parse_toolchain_items(args.toolchain),
            guardrail_paths=[path.resolve() for path in args.guardrails],
            allow_cloud_upload=args.allow_cloud_upload,
            approval_evidence=(
                load_json(args.approval_evidence.resolve())
                if args.approval_evidence is not None
                else None
            ),
        )
        write_json(args.manifest_output, manifest)
        manifest_path = args.manifest_output

    if manifest_path is None:
        if args.release_evidence_report:
            raise CheckError(
                "--release-evidence-report requires --manifest or --manifest-output"
            )
        errors = validate_root_audit(root)
        if errors:
            print("release provenance root audit failed:", file=sys.stderr)
            for error in errors:
                print(f"- {error}", file=sys.stderr)
            return 1
        print("validated offline release provenance checker root audit")
        return 0

    manifest_payload = load_json(manifest_path.resolve())
    errors = validate_manifest(
        artifact_root,
        manifest_payload,
        allow_cloud_upload=args.allow_cloud_upload,
    )
    if args.release_evidence_report:
        errors.extend(
            validate_release_evidence_reports(
                artifact_root,
                manifest_payload,
                args.release_evidence_report,
            )
        )
    if errors:
        print("release provenance manifest check failed:", file=sys.stderr)
        for error in errors:
            print(f"- {error}", file=sys.stderr)
        return 1

    print(f"validated release provenance manifest: {manifest_path}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main(sys.argv[1:]))
    except CheckError as exc:
        print(str(exc), file=sys.stderr)
        raise SystemExit(1)
