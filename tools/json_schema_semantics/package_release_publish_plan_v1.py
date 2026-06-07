"""Semantic checks for package-release-publish-plan-v1.schema.json."""

from package_target_contracts import TARGET_REQUIRED_PATH_ARTIFACTS

from .common import (
    add_equal_error,
    add_length_count_error,
    validate_release_package_artifacts_against_requirements,
)


def validate_publish_artifact(errors, path, artifact):
    for field in (
        "name",
        "packagePath",
        "module",
        "sourcePath",
        "packageArtifactPath",
        "destinationPath",
    ):
        if artifact[field] == "":
            errors.append(f"{path}.{field}: expected non-empty value")
    if "\\" in artifact["destinationPath"]:
        errors.append(f"{path}.destinationPath: expected normalized '/' separators")
    if artifact["destinationPath"].startswith("/"):
        errors.append(f"{path}.destinationPath: expected relative path")
    parts = artifact["destinationPath"].split("/")
    if any(part in ("", ".", "..") for part in parts):
        errors.append(f"{path}.destinationPath: expected normalized relative path")
    if artifact["packageArtifactPath"].startswith("/"):
        errors.append(f"{path}.packageArtifactPath: expected package-relative path")
    if ".." in artifact["packageArtifactPath"].split("/"):
        errors.append(
            f"{path}.packageArtifactPath: expected no parent directory traversal"
        )
    if artifact["sourcePath"].endswith("/" + artifact["packageArtifactPath"]):
        return
    if (
        artifact["sourcePath"]
        != artifact["packagePath"] + "/" + artifact["packageArtifactPath"]
    ):
        errors.append(f"{path}.sourcePath: expected packagePath/packageArtifactPath")


def validate_publish_native_binary_state(errors, path, package):
    if package["nativeBinaryStatus"] != "planned":
        return

    requirements = package["packageArtifactRequirements"]
    if not requirements["allowsPlannedNativeBinary"]:
        errors.append(
            f"{path}.nativeBinaryStatus: planned nativeBinaryStatus "
            "requires allowsPlannedNativeBinary"
        )

    if any(artifact["name"] == "nativeBinary" for artifact in package["artifacts"]):
        errors.append(
            f"{path}.artifacts.nativeBinary: planned nativeBinaryStatus "
            "must not publish nativeBinary artifact"
        )


def validate_publish_required_path_artifacts(errors, path, package):
    expected_artifacts = TARGET_REQUIRED_PATH_ARTIFACTS.get(package["target"])
    if expected_artifacts is None:
        return

    required_artifacts = package["packageArtifactRequirements"]["requiredPathArtifacts"]
    expected_artifacts = list(expected_artifacts)
    if required_artifacts != expected_artifacts:
        errors.append(
            f"{path}.packageArtifactRequirements.requiredPathArtifacts: "
            f"expected target contract artifacts {expected_artifacts!r}, "
            f"got {required_artifacts!r}"
        )


def validate_semantics(instance):
    errors = []

    for field in ("bundlePath", "planPath"):
        if instance[field] == "":
            errors.append(f"$.{field}: expected non-empty path")

    add_length_count_error(
        errors,
        "$.packageCount",
        instance["packageCount"],
        instance["packages"],
        "package length",
    )
    add_length_count_error(
        errors,
        "$.artifactCount",
        instance["artifactCount"],
        instance["artifacts"],
        "artifact length",
    )

    package_paths = [package["packagePath"] for package in instance["packages"]]
    if package_paths != sorted(package_paths):
        errors.append("$.packages: package paths must be sorted")
    if len(package_paths) != len(set(package_paths)):
        errors.append("$.packages: duplicate package paths")

    destination_paths = [
        artifact["destinationPath"] for artifact in instance["artifacts"]
    ]
    if destination_paths != sorted(destination_paths):
        errors.append("$.artifacts: destination paths must be sorted")
    if len(destination_paths) != len(set(destination_paths)):
        errors.append("$.artifacts: duplicate destination paths")

    flattened_by_destination = {
        artifact["destinationPath"]: artifact for artifact in instance["artifacts"]
    }

    artifact_count = 0
    total_artifact_bytes = 0
    for package_index, package in enumerate(instance["packages"]):
        package_path = f"$.packages[{package_index}]"
        if package["packagePath"] == "":
            errors.append(f"{package_path}.packagePath: expected non-empty path")
        if package["module"] == "":
            errors.append(f"{package_path}.module: expected non-empty module")
        if package["sourceHash"] is None:
            errors.append(
                f"{package_path}.sourceHash: publish plan requires sourceHash"
            )
        validate_release_package_artifacts_against_requirements(
            errors, package_path, package, require_existing=False
        )
        validate_publish_required_path_artifacts(errors, package_path, package)
        validate_publish_native_binary_state(errors, package_path, package)
        package_destination_paths = [
            artifact["destinationPath"] for artifact in package["artifacts"]
        ]
        if package_destination_paths != sorted(package_destination_paths):
            errors.append(f"{package_path}.artifacts: destination paths must be sorted")
        if len(package_destination_paths) != len(set(package_destination_paths)):
            errors.append(f"{package_path}.artifacts: duplicate destination paths")
        add_length_count_error(
            errors,
            f"{package_path}.artifactCount",
            package["artifactCount"],
            package["artifacts"],
            "artifact length",
        )
        package_bytes = sum(artifact["sizeBytes"] for artifact in package["artifacts"])
        add_equal_error(
            errors,
            f"{package_path}.totalArtifactBytes",
            package["totalArtifactBytes"],
            package_bytes,
            "artifact byte sum",
        )
        for artifact_index, artifact in enumerate(package["artifacts"]):
            artifact_path = f"{package_path}.artifacts[{artifact_index}]"
            validate_publish_artifact(errors, artifact_path, artifact)
            for field in ("packagePath", "module", "target"):
                add_equal_error(
                    errors,
                    f"{artifact_path}.{field}",
                    artifact[field],
                    package[field],
                    f"package {field}",
                )
            flattened = flattened_by_destination.get(artifact["destinationPath"])
            if flattened != artifact:
                errors.append(
                    f"{artifact_path}: expected matching flattened artifact record"
                )

        artifact_count += len(package["artifacts"])
        total_artifact_bytes += package_bytes

    for artifact_index, artifact in enumerate(instance["artifacts"]):
        validate_publish_artifact(errors, f"$.artifacts[{artifact_index}]", artifact)

    add_equal_error(
        errors,
        "$.artifactCount",
        instance["artifactCount"],
        artifact_count,
        "nested artifact length",
    )
    add_equal_error(
        errors,
        "$.totalArtifactBytes",
        instance["totalArtifactBytes"],
        total_artifact_bytes,
        "artifact byte sum",
    )

    return errors
