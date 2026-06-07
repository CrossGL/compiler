"""Semantic checks for package-sidecars-v1.schema.json."""

from pathlib import PurePosixPath

from .common import (
    add_equal_error,
    add_length_count_error,
    validate_normalized_package_path,
)


def validate_sidecar_name(errors, path, requested_path, sidecar):
    requested = PurePosixPath(requested_path)
    sidecar_path = PurePosixPath(sidecar["path"])
    requested_name = requested.name
    sidecar_name = sidecar_path.name
    expected_name = (
        f".{requested_name}.{sidecar['kind']}-{sidecar['token']}-{sidecar['attempt']}"
    )
    add_equal_error(
        errors,
        f"{path}.path",
        sidecar_name,
        expected_name,
        "sidecar basename from kind/token/attempt",
    )
    add_equal_error(
        errors,
        f"{path}.path",
        sidecar_path.parent.as_posix(),
        requested.parent.as_posix(),
        "sidecar parent directory",
    )


def validate_publication(errors, publication):
    validate_normalized_package_path(
        errors,
        "$.publication.requestedPath",
        publication["requestedPath"],
    )
    sidecars = publication["siblingSidecars"]
    add_length_count_error(
        errors,
        "$.publication.siblingSidecarCount",
        publication["siblingSidecarCount"],
        sidecars,
        "sibling sidecars length",
    )

    state = publication["state"]
    sidecar_kind = publication["sidecarKind"]
    sidecar_token = publication["sidecarToken"]
    sidecar_attempt = publication["sidecarAttempt"]
    if state == "published":
        if sidecar_kind is not None:
            errors.append("$.publication.sidecarKind: expected null when published")
        if sidecar_token is not None:
            errors.append("$.publication.sidecarToken: expected null when published")
        if sidecar_attempt is not None:
            errors.append("$.publication.sidecarAttempt: expected null when published")
    else:
        add_equal_error(
            errors,
            "$.publication.sidecarKind",
            sidecar_kind,
            "staging" if state == "staged" else state,
            "publication sidecar kind",
        )
        if not sidecar_token:
            errors.append(
                "$.publication.sidecarToken: expected non-empty sidecar token"
            )
        if sidecar_attempt is None:
            errors.append("$.publication.sidecarAttempt: expected sidecar attempt")

    paths = []
    for index, sidecar in enumerate(sidecars):
        path = f"$.publication.siblingSidecars[{index}]"
        validate_normalized_package_path(errors, f"{path}.path", sidecar["path"])
        validate_sidecar_name(errors, path, publication["requestedPath"], sidecar)
        if not sidecar["token"]:
            errors.append(f"{path}.token: expected non-empty sidecar token")
        paths.append(sidecar["path"])

    if paths != sorted(paths):
        errors.append("$.publication.siblingSidecars: expected sorted sidecar paths")
    if len(paths) != len(set(paths)):
        errors.append("$.publication.siblingSidecars: duplicate sidecar paths")


def validate_semantics(instance):
    errors = []
    validate_normalized_package_path(errors, "$.packagePath", instance["packagePath"])
    validate_publication(errors, instance["publication"])
    if instance["publication"]["state"] == "published":
        add_equal_error(
            errors,
            "$.publication.requestedPath",
            instance["publication"]["requestedPath"],
            instance["packagePath"],
            "packagePath for published package",
        )
    return errors
