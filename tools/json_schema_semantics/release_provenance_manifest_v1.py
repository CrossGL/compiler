"""Semantic checks for release-provenance-manifest-v1.schema.json."""

import re
from pathlib import PurePosixPath

from .common import add_equal_error, add_length_count_error


SAFE_CLOUD_MODES = ("dry-run", "local-only", "mock")
LIVE_CLOUD_MODE = "live-cloud"
KNOWN_CLOUD_MODES = tuple(sorted((*SAFE_CLOUD_MODES, LIVE_CLOUD_MODE)))
LIVE_CLOUD_OPT_IN_SOURCES = (
    "CROSSGL_ALLOW_LIVE_CLOUD_RELEASE_UPLOAD",
    "cli-flag",
)
LOCAL_ARTIFACT_PATH_FIELDS = ("path", "packagePath", "packageArtifactPath")
ARTIFACT_RELATIVE_PATH_FIELDS = (
    *LOCAL_ARTIFACT_PATH_FIELDS,
    "destinationPath",
)
LIVE_APPROVAL_STRING_FIELDS = (
    "approvalRecord",
    "projectAllowlistEntry",
    "bucketAllowlistEntry",
    "budgetGuardrail",
    "lifecyclePolicy",
)
LIVE_APPROVAL_PLACEHOLDERS = {"", "tbd", "todo", "none", "n/a", "placeholder"}
URI_SCHEME_PATH_RE = re.compile(r"^[A-Za-z][A-Za-z0-9+.-]*:")
WINDOWS_DRIVE_PATH_RE = re.compile(r"^[A-Za-z]:")


def is_placeholder_text(value):
    stripped = value.strip()
    lower = stripped.lower()
    return (
        not stripped
        or lower in LIVE_APPROVAL_PLACEHOLDERS
        or lower.startswith("placeholder")
        or (stripped.startswith("<") and stripped.endswith(">"))
    )


def validate_explicit_text(errors, path, value, label):
    if is_placeholder_text(value):
        errors.append(f"{path}: expected explicit {label}, got placeholder")
        return None
    return value


def validate_relative_path(errors, path, value, *, allow_empty=False):
    if value == "" and allow_empty:
        return
    if value == "":
        errors.append(f"{path}: expected non-empty path")
        return
    stripped = value.strip()
    if stripped == "":
        errors.append(f"{path}: expected non-blank path")
        return
    if stripped != value:
        errors.append(f"{path}: expected no leading or trailing whitespace")
        return
    if "\\" in value:
        errors.append(f"{path}: expected normalized '/' separators")
    if WINDOWS_DRIVE_PATH_RE.match(value):
        errors.append(f"{path}: expected no Windows drive prefix")
    if URI_SCHEME_PATH_RE.match(value):
        errors.append(f"{path}: expected no URI scheme")
    if value.startswith("/"):
        errors.append(f"{path}: expected relative path")
    parts = value.split("/")
    if any(part in ("", ".", "..") for part in parts):
        errors.append(f"{path}: expected normalized relative path")
    if PurePosixPath(value).is_absolute():
        errors.append(f"{path}: expected artifact-root-relative path")


def validate_live_approval_evidence(errors, path, evidence):
    for field in LIVE_APPROVAL_STRING_FIELDS:
        validate_explicit_text(errors, f"{path}.{field}", evidence[field], field)

    release_prefix = validate_explicit_text(
        errors,
        f"{path}.releaseObjectPrefix",
        evidence["releaseObjectPrefix"],
        "releaseObjectPrefix",
    )
    if release_prefix is not None:
        validate_relative_path(errors, f"{path}.releaseObjectPrefix", release_prefix)

    for index, receipt_path in enumerate(evidence["auditReceiptPaths"]):
        receipt_path_path = f"{path}.auditReceiptPaths[{index}]"
        if validate_explicit_text(
            errors, receipt_path_path, receipt_path, "audit receipt path"
        ):
            validate_relative_path(errors, receipt_path_path, receipt_path)


def validate_toolchain_summary(errors, toolchain):
    if not toolchain:
        errors.append("$.toolchainSummary: expected non-empty object")
        return
    for key, value in toolchain.items():
        if not isinstance(key, str) or key == "":
            errors.append("$.toolchainSummary: expected non-empty string keys")
        if not isinstance(value, str) or value == "":
            errors.append(f"$.toolchainSummary.{key}: expected non-empty string value")


def validate_cloud_upload(errors, cloud):
    mode = cloud["mode"]
    modes = cloud["modes"]

    if modes != sorted(modes):
        errors.append("$.cloudUpload.modes: expected sorted modes")
    if mode not in modes:
        errors.append("$.cloudUpload.mode: must be included in modes")

    live_modes = [item for item in modes if item == LIVE_CLOUD_MODE]
    opt_in = cloud["liveCloudUploadOptIn"]
    allowed = cloud["liveCloudUploadAllowed"]
    if live_modes:
        if allowed is not True:
            errors.append(
                "$.cloudUpload.liveCloudUploadAllowed: expected true for live-cloud mode"
            )
        if opt_in not in LIVE_CLOUD_OPT_IN_SOURCES:
            errors.append(
                "$.cloudUpload.liveCloudUploadOptIn: expected explicit live-cloud opt-in source"
            )
        if "approvalEvidence" not in cloud:
            errors.append(
                "$.cloudUpload.approvalEvidence: required for live cloud modes"
            )
        else:
            validate_live_approval_evidence(
                errors, "$.cloudUpload.approvalEvidence", cloud["approvalEvidence"]
            )
    elif allowed is True:
        errors.append(
            "$.cloudUpload.liveCloudUploadAllowed: must be false unless "
            "live-cloud mode is recorded"
        )
    elif opt_in is not None and allowed is not True:
        errors.append(
            "$.cloudUpload.liveCloudUploadOptIn: expected null unless live cloud upload is allowed"
        )
    elif "approvalEvidence" in cloud:
        validate_live_approval_evidence(
            errors, "$.cloudUpload.approvalEvidence", cloud["approvalEvidence"]
        )


def validate_artifact(errors, path, artifact):
    for field in ARTIFACT_RELATIVE_PATH_FIELDS:
        if field in artifact:
            validate_relative_path(
                errors,
                f"{path}.{field}",
                artifact[field],
                allow_empty=field != "path",
            )
    package_path = artifact.get("packagePath", "")
    package_artifact_path = artifact.get("packageArtifactPath", "")
    if package_path and not package_artifact_path:
        errors.append(
            f"{path}.packageArtifactPath: required when packagePath is non-empty"
        )
    if package_artifact_path and not package_path:
        errors.append(
            f"{path}.packagePath: required when packageArtifactPath is non-empty"
        )


def validate_artifacts(errors, artifacts):
    artifact_paths = [artifact["path"] for artifact in artifacts]
    if artifact_paths != sorted(artifact_paths):
        errors.append("$.artifacts: artifact paths must be sorted")
    if len(artifact_paths) != len(set(artifact_paths)):
        errors.append("$.artifacts: duplicate artifact paths")

    destination_paths = [
        artifact["destinationPath"]
        for artifact in artifacts
        if artifact.get("destinationPath") not in (None, "")
    ]
    if len(destination_paths) != len(set(destination_paths)):
        errors.append("$.artifacts: duplicate artifact destinations")

    package_identities = [
        (artifact["packagePath"], artifact["packageArtifactPath"])
        for artifact in artifacts
        if artifact.get("packagePath") not in (None, "")
        and artifact.get("packageArtifactPath") not in (None, "")
    ]
    if len(package_identities) != len(set(package_identities)):
        errors.append("$.artifacts: duplicate package artifact identities")

    for index, artifact in enumerate(artifacts):
        validate_artifact(errors, f"$.artifacts[{index}]", artifact)


def validate_semantics(instance):
    errors = []

    validate_toolchain_summary(errors, instance["toolchainSummary"])
    validate_cloud_upload(errors, instance["cloudUpload"])

    artifacts = instance["artifacts"]
    add_length_count_error(
        errors,
        "$.artifactCount",
        instance["artifactCount"],
        artifacts,
        "artifact length",
    )
    add_equal_error(
        errors,
        "$.artifactBytes",
        instance["artifactBytes"],
        sum(artifact["sizeBytes"] for artifact in artifacts),
        "artifact byte sum",
    )
    validate_artifacts(errors, artifacts)

    return errors
