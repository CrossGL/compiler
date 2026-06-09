"""Semantic checks for package-release-publish-upload-manifest-v1.schema.json."""

import re

from .common import add_equal_error, add_length_count_error
from .package_release_publish_target_v1 import is_gcs_bucket_name


SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


def validate_relative_path(errors, path, value):
    if value == "":
        errors.append(f"{path}: expected non-empty path")
    if "\\" in value:
        errors.append(f"{path}: expected normalized '/' separators")
    if value.startswith("/"):
        errors.append(f"{path}: expected relative path")
    parts = value.split("/")
    if any(part in ("", ".", "..") for part in parts):
        errors.append(f"{path}: expected normalized relative path")


def validate_normalized_staged_path(errors, path, value):
    if value == "":
        return
    if value.strip() != value:
        errors.append(f"{path}: expected normalized staged path")
    parts = value.split("/")
    if value.startswith("/"):
        parts = parts[1:]
    if any(part in ("", ".", "..") for part in parts):
        errors.append(f"{path}: expected normalized staged path")


def staged_path_uses_stage_directory(value):
    return any(part == "stage" or part.endswith("-stage") for part in value.split("/"))


def validate_request(errors, path, request):
    if request["stagedPath"] == "":
        errors.append(f"{path}.stagedPath: expected non-empty path")
    if "\\" in request["stagedPath"]:
        errors.append(f"{path}.stagedPath: expected normalized '/' separators")
    validate_normalized_staged_path(errors, f"{path}.stagedPath", request["stagedPath"])
    validate_relative_path(
        errors, f"{path}.destinationPath", request["destinationPath"]
    )
    expected_staged_suffix = f"/{request['destinationPath']}"
    if (
        staged_path_uses_stage_directory(request["stagedPath"])
        and request["stagedPath"] != request["destinationPath"]
        and not request["stagedPath"].endswith(expected_staged_suffix)
    ):
        errors.append(
            f"{path}.stagedPath: expected staged path to end with destinationPath"
        )
    validate_relative_path(errors, f"{path}.objectName", request["objectName"])
    expected_object_suffix = f"/{request['destinationPath']}"
    if request["objectName"] == request["destinationPath"]:
        errors.append(f"{path}.objectName: expected non-root object prefix")
    elif not request["objectName"].endswith(expected_object_suffix):
        errors.append(
            f"{path}.objectName: expected object name to end with destinationPath"
        )
    if request["bucket"] == "":
        errors.append(f"{path}.bucket: expected non-empty bucket")
    elif not is_gcs_bucket_name(request["bucket"]):
        errors.append(f"{path}.bucket: expected valid gcs bucket name")
    if request["credentialsEnv"] == "":
        errors.append(f"{path}.credentialsEnv: expected non-empty value")
    expected_uri = f"gs://{request['bucket']}/{request['objectName']}"
    if request["uploadUri"] != expected_uri:
        errors.append(f"{path}.uploadUri: expected gs:// bucket/object URI")
    if not SHA256_RE.match(request["sha256"]):
        errors.append(f"{path}.sha256: expected lowercase SHA-256 digest")


def request_object_prefix(request):
    expected_suffix = f"/{request['destinationPath']}"
    object_name = request["objectName"]
    if object_name.endswith(expected_suffix):
        return object_name[: -len(expected_suffix)]
    return None


def validate_semantics(instance):
    errors = []

    requests = instance["requests"]
    add_length_count_error(
        errors,
        "$.requestCount",
        instance["requestCount"],
        requests,
        "upload request length",
    )
    request_bytes = sum(request["sizeBytes"] for request in requests)
    add_equal_error(
        errors,
        "$.requestBytes",
        instance["requestBytes"],
        request_bytes,
        "upload request byte sum",
    )

    destination_paths = [request["destinationPath"] for request in requests]
    if destination_paths != sorted(destination_paths):
        errors.append("$.requests: destination paths must be sorted")
    if len(destination_paths) != len(set(destination_paths)):
        errors.append("$.requests: duplicate destination paths")

    buckets = [request["bucket"] for request in requests]
    if len(set(buckets)) > 1:
        errors.append("$.requests: expected one bucket per upload manifest")

    credential_envs = [request["credentialsEnv"] for request in requests]
    if len(set(credential_envs)) > 1:
        errors.append("$.requests: expected one credentialsEnv per upload manifest")

    object_prefixes = [
        prefix for request in requests if (prefix := request_object_prefix(request))
    ]
    if object_prefixes and len(object_prefixes) != len(requests):
        errors.append("$.requests: expected object names with release-scoped prefixes")
    elif len(set(object_prefixes)) > 1:
        errors.append("$.requests: expected one release-scoped object prefix")

    for index, request in enumerate(requests):
        validate_request(errors, f"$.requests[{index}]", request)

    return errors
