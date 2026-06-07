"""Shared JSON contract assertions for package fixture checks."""


def expect_equal(errors, case_name, path, actual, expected):
    if actual != expected:
        errors.append(
            f"{case_name}: expected {path} to equal {expected!r}, got {actual!r}"
        )


def expect_object(errors, case_name, path, value):
    if not isinstance(value, dict):
        errors.append(f"{case_name}: expected {path} to be an object")
        return {}
    return value


def expect_array(errors, case_name, path, value):
    if not isinstance(value, list):
        errors.append(f"{case_name}: expected {path} to be an array")
        return []
    return value


def expect_package_path_contract(errors, case_name, package_path, package=None):
    if not isinstance(package_path, str):
        errors.append(f"{case_name}: expected packagePath to be a string")
        return
    if "\\" in package_path:
        errors.append(f"{case_name}: expected packagePath to use '/' separators")
    if package is not None:
        expect_equal(
            errors,
            case_name,
            "packagePath",
            package_path,
            package.as_posix(),
        )


def manifest_artifacts(manifest):
    artifacts = manifest.get("artifacts", {})
    if not isinstance(artifacts, dict):
        return {}
    return artifacts


def expected_manifest_artifact_names(manifest):
    return {
        name for name in manifest_artifacts(manifest) if name != "nativeBinaryStatus"
    }


def expected_summary_native_binary_status(manifest):
    artifacts = manifest_artifacts(manifest)
    status = artifacts.get("nativeBinaryStatus")
    if status is not None:
        return status
    if isinstance(manifest.get("packageArtifactRequirements"), dict):
        return None
    if (
        manifest.get("target") == "metal"
        and "intermediate" in artifacts
        and "nativeBinary" in artifacts
    ):
        return "emitted"
    return None


def expect_package_summary_manifest_contract(
    errors,
    case_name,
    summary,
    manifest,
    *,
    artifact_count=None,
    debug_artifact_names=None,
):
    summary = expect_object(errors, case_name, "summary", summary)
    artifacts = manifest_artifacts(manifest)

    if "module" in manifest:
        expect_equal(
            errors,
            case_name,
            "summary.module",
            summary.get("module"),
            manifest["module"],
        )
    if "target" in manifest:
        expect_equal(
            errors,
            case_name,
            "summary.target",
            summary.get("target"),
            manifest["target"],
        )
    expect_equal(
        errors,
        case_name,
        "summary.nativeBinaryStatus",
        summary.get("nativeBinaryStatus"),
        expected_summary_native_binary_status(manifest),
    )

    if artifact_count is None:
        artifact_count = len(expected_manifest_artifact_names(manifest))
    expect_equal(
        errors,
        case_name,
        "summary.artifactCount",
        summary.get("artifactCount"),
        artifact_count,
    )

    if debug_artifact_names is None:
        debug_artifact_names = artifacts
    expect_equal(
        errors,
        case_name,
        "summary.debugArtifactsPresent",
        summary.get("debugArtifactsPresent"),
        {"debugMetadata", "hirSourceMap"}.issubset(debug_artifact_names),
    )
