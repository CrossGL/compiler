"""Semantic checks for package-release-bundle-v1.schema.json."""

from collections import Counter

from .common import (
    add_equal_error,
    add_length_count_error,
    validate_native_binary_state,
    validate_release_package_artifacts_against_requirements,
    validate_target_feature_reflection_summary,
)


def artifact_size_for_total(artifact):
    if artifact["exists"] and artifact["sizeBytes"] is not None:
        return artifact["sizeBytes"]
    return 0


def validate_package_relative_artifact_path(errors, path, value):
    if value == "":
        errors.append(f"{path}: expected non-empty path")
    if "\\" in value:
        errors.append(f"{path}: expected normalized '/' separators")
    if value.startswith("/"):
        errors.append(f"{path}: expected package-relative path")
    parts = value.split("/")
    if any(part in ("", ".", "..") for part in parts):
        errors.append(f"{path}: expected normalized package-relative path")


def validate_artifacts(errors, package_path, artifacts):
    artifact_names = [artifact["name"] for artifact in artifacts]
    if artifact_names != sorted(artifact_names):
        errors.append(f"{package_path}.artifacts: artifact names must be sorted")
    if len(artifact_names) != len(set(artifact_names)):
        errors.append(f"{package_path}.artifacts: duplicate artifact names")

    for artifact_index, artifact in enumerate(artifacts):
        artifact_path = f"{package_path}.artifacts[{artifact_index}]"
        if artifact["name"] == "":
            errors.append(f"{artifact_path}.name: expected non-empty name")
        validate_package_relative_artifact_path(
            errors, f"{artifact_path}.path", artifact["path"]
        )
        if artifact["exists"]:
            if artifact["sizeBytes"] is None:
                errors.append(
                    f"{artifact_path}.sizeBytes: existing artifact requires size"
                )
            if artifact["sha256"] is None:
                errors.append(
                    f"{artifact_path}.sha256: existing artifact requires digest"
                )
        else:
            if artifact["sizeBytes"] is not None:
                errors.append(
                    f"{artifact_path}.sizeBytes: missing artifact must use null"
                )
            if artifact["sha256"] is not None:
                errors.append(f"{artifact_path}.sha256: missing artifact must use null")


def validate_semantics(instance):
    errors = []

    for field in ("bundlePath", "promotionManifestPath", "summaryPath", "batchPath"):
        if instance[field] == "":
            errors.append(f"$.{field}: expected non-empty path")

    add_length_count_error(
        errors,
        "$.blockerCount",
        instance["blockerCount"],
        instance["blockers"],
        "blocker length",
    )
    add_length_count_error(
        errors,
        "$.packageCount",
        instance["packageCount"],
        instance["packages"],
        "package length",
    )

    blocker_codes = [blocker["code"] for blocker in instance["blockers"]]
    if blocker_codes != sorted(blocker_codes):
        errors.append("$.blockers: blocker codes must be sorted")
    if len(blocker_codes) != len(set(blocker_codes)):
        errors.append("$.blockers: duplicate blocker codes")
    for index, blocker in enumerate(instance["blockers"]):
        if blocker["code"] == "":
            errors.append(f"$.blockers[{index}].code: expected non-empty code")
        if blocker["message"] == "":
            errors.append(f"$.blockers[{index}].message: expected non-empty message")
        if blocker["count"] <= 0:
            errors.append(f"$.blockers[{index}].count: expected positive count")

    package_paths = [package["packagePath"] for package in instance["packages"]]
    if package_paths != sorted(package_paths):
        errors.append("$.packages: package paths must be sorted")
    if len(package_paths) != len(set(package_paths)):
        errors.append("$.packages: duplicate package paths")
    package_targets = [
        (package["module"], package["target"]) for package in instance["packages"]
    ]
    package_target_counts = Counter(package_targets)
    if len(package_targets) != len(package_target_counts):
        duplicates = sorted(
            package_target
            for package_target, count in package_target_counts.items()
            if count > 1
        )
        errors.append(f"$.packages: duplicate package target record {duplicates[0]!r}")

    artifact_count = 0
    existing_artifact_count = 0
    missing_artifact_count = 0
    total_artifact_bytes = 0
    for package_index, package in enumerate(instance["packages"]):
        package_path = f"$.packages[{package_index}]"
        if package["packagePath"] == "":
            errors.append(f"{package_path}.packagePath: expected non-empty path")
        if package["module"] == "":
            errors.append(f"{package_path}.module: expected non-empty module")
        if instance["releaseEligible"] and package["sourceHash"] is None:
            errors.append(
                f"{package_path}.sourceHash: release eligible bundle requires sourceHash"
            )
        validate_release_package_artifacts_against_requirements(
            errors, package_path, package
        )
        validate_target_feature_reflection_summary(
            errors,
            f"{package_path}.reflection",
            package["target"],
            package["reflection"],
        )
        validate_native_binary_state(errors, package_path, package)

        artifacts = package["artifacts"]
        existing = [artifact for artifact in artifacts if artifact["exists"]]
        missing = [artifact for artifact in artifacts if not artifact["exists"]]
        bytes_total = sum(artifact_size_for_total(artifact) for artifact in artifacts)
        add_length_count_error(
            errors,
            f"{package_path}.artifactCount",
            package["artifactCount"],
            artifacts,
            "artifact length",
        )
        add_equal_error(
            errors,
            f"{package_path}.existingArtifactCount",
            package["existingArtifactCount"],
            len(existing),
            "existing artifact length",
        )
        add_equal_error(
            errors,
            f"{package_path}.missingArtifactCount",
            package["missingArtifactCount"],
            len(missing),
            "missing artifact length",
        )
        add_equal_error(
            errors,
            f"{package_path}.totalArtifactBytes",
            package["totalArtifactBytes"],
            bytes_total,
            "artifact byte sum",
        )
        validate_artifacts(errors, package_path, artifacts)

        artifact_count += len(artifacts)
        existing_artifact_count += len(existing)
        missing_artifact_count += len(missing)
        total_artifact_bytes += bytes_total

    add_equal_error(
        errors,
        "$.artifactCount",
        instance["artifactCount"],
        artifact_count,
        "artifact length",
    )
    add_equal_error(
        errors,
        "$.existingArtifactCount",
        instance["existingArtifactCount"],
        existing_artifact_count,
        "existing artifact length",
    )
    add_equal_error(
        errors,
        "$.missingArtifactCount",
        instance["missingArtifactCount"],
        missing_artifact_count,
        "missing artifact length",
    )
    add_equal_error(
        errors,
        "$.totalArtifactBytes",
        instance["totalArtifactBytes"],
        total_artifact_bytes,
        "artifact byte sum",
    )
    add_equal_error(
        errors,
        "$.status",
        instance["status"],
        "eligible" if instance["releaseEligible"] else "blocked",
        "release status",
    )

    if instance["releaseEligible"] and instance["blockers"]:
        errors.append("$.blockers: release eligible bundle must not have blockers")
    if not instance["releaseEligible"] and not instance["blockers"]:
        errors.append("$.blockers: blocked bundle requires at least one blocker")

    return errors
