"""Semantic checks for source-remap-provenance-v1.schema.json."""

import re


SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")


def is_stable_relative_path(path):
    if path == "":
        return False
    if "\\" in path:
        return False
    if path.startswith("/") or (
        len(path) >= 2 and path[0].isalpha() and path[1] == ":"
    ):
        return False
    return all(segment not in ("", ".", "..") for segment in path.split("/"))


def validate_semantics(instance):
    errors = []
    if not is_stable_relative_path(instance["generatedFile"]):
        errors.append("$.generatedFile: expected stable relative POSIX source path")

    source_remap = instance["sourceRemap"]
    if not source_remap["path"].strip():
        errors.append("$.sourceRemap.path: expected non-empty remap sidecar path")

    sha256 = source_remap["sha256"]
    if sha256["algorithm"] != "sha256":
        errors.append("$.sourceRemap.sha256.algorithm: expected sha256")
    if not SHA256_PATTERN.match(sha256["value"]):
        errors.append(
            "$.sourceRemap.sha256.value: expected 64 lowercase hexadecimal sha256"
        )
    return errors
