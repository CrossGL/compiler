"""Semantic checks for diagnostics-v1.schema.json."""

import re

from .common import validate_source_location_span


COMPILER_TARGETS = ("metal", "vulkan", "directx", "opengl")

DIAGNOSTIC_CODE_PREFIXES = (
    "artifact.",
    "directx.",
    "io.",
    "lex.",
    "metal.",
    "opengl.",
    "opt.",
    "package.",
    "parse.",
    "project.",
    "sema.",
    "spec.",
    "target.",
    "vulkan.",
)

UNSUPPORTED_NATIVE_V0_CODE = "spec.unsupported-for-native-v0"
PROJECT_CAPABILITY_PATTERN = re.compile(r"^[a-z][a-z0-9]*(?:[.-][a-z0-9]+)+$")


def is_empty_source_file(location):
    return location["file"].strip() == ""


def is_non_empty_source_span(location):
    return location["length"] != 0


def is_normalized_relative_source_file(file):
    if file == "":
        return True
    if "\\" in file:
        return False
    if file.startswith("/") or (
        len(file) >= 2 and file[0].isalpha() and file[1] == ":"
    ):
        return False
    return all(segment not in ("", ".", "..") for segment in file.split("/"))


def is_target_diagnostic_code(code):
    return code.startswith("target.")


def is_project_diagnostic_code(code):
    return code.startswith("project.")


def is_compiler_target(target):
    return target in COMPILER_TARGETS


def is_unsupported_native_v0_diagnostic(code):
    return code == UNSUPPORTED_NATIVE_V0_CODE


def validate_diagnostic_source_location(errors, path, location):
    if is_empty_source_file(location) and is_non_empty_source_span(location):
        errors.append(f"{path}.file: expected non-empty file for non-empty source span")
    if not is_normalized_relative_source_file(location["file"]):
        errors.append(
            f"{path}.file: expected normalized relative POSIX diagnostic file path"
        )
    validate_source_location_span(errors, path, location)


def validate_compiler_target(errors, diagnostic_path, diagnostic):
    if "target" not in diagnostic:
        return
    if is_project_diagnostic_code(diagnostic["code"]):
        return
    if not is_compiler_target(diagnostic["target"]):
        targets = ", ".join(COMPILER_TARGETS)
        errors.append(
            f"{diagnostic_path}.target: expected compiler target ({targets}) "
            "for compiler diagnostic"
        )


def validate_project_capability(errors, diagnostic_path, capability_index, capability):
    if PROJECT_CAPABILITY_PATTERN.fullmatch(capability) is None:
        errors.append(
            f"{diagnostic_path}.missingCapabilities[{capability_index}]: "
            "expected project capability id with non-empty dotted or dashed "
            "lowercase segments"
        )


def validate_compiler_capability(
    errors, diagnostic_path, target, capability_index, capability
):
    target_prefix = f"{target}."
    if not capability.startswith(target_prefix):
        errors.append(
            f"{diagnostic_path}.missingCapabilities"
            f"[{capability_index}]: expected target-prefixed "
            f"capability id starting with {target_prefix!r}"
        )
    elif capability[len(target_prefix) :].strip() == "":
        errors.append(
            f"{diagnostic_path}.missingCapabilities"
            f"[{capability_index}]: expected non-empty "
            f"capability id after target prefix {target_prefix!r}"
        )


def validate_missing_capabilities(errors, diagnostic_path, diagnostic):
    if "missingCapabilities" not in diagnostic:
        return

    if is_project_diagnostic_code(diagnostic["code"]):
        for capability_index, capability in enumerate(
            diagnostic["missingCapabilities"]
        ):
            validate_project_capability(
                errors, diagnostic_path, capability_index, capability
            )
        return

    if "target" not in diagnostic:
        errors.append(
            f"{diagnostic_path}.target: expected target when "
            "missingCapabilities are reported"
        )
        return

    for capability_index, capability in enumerate(diagnostic["missingCapabilities"]):
        validate_compiler_capability(
            errors,
            diagnostic_path,
            diagnostic["target"],
            capability_index,
            capability,
        )


def validate_semantics(instance):
    errors = []
    for index, diagnostic in enumerate(instance["diagnostics"]):
        diagnostic_path = f"$.diagnostics[{index}]"
        location = diagnostic["location"]
        if diagnostic["code"] == "":
            errors.append(f"{diagnostic_path}.code: expected non-empty diagnostic code")
        elif not diagnostic["code"].startswith(DIAGNOSTIC_CODE_PREFIXES):
            prefixes = ", ".join(DIAGNOSTIC_CODE_PREFIXES)
            errors.append(
                f"{diagnostic_path}.code: expected known diagnostic code prefix "
                f"({prefixes})"
            )
        if diagnostic["message"].strip() == "":
            errors.append(
                f"{diagnostic_path}.message: expected non-empty diagnostic message"
            )
        if is_target_diagnostic_code(diagnostic["code"]) and "target" not in diagnostic:
            errors.append(
                f"{diagnostic_path}.target: expected target for target diagnostic code"
            )
        validate_compiler_target(errors, diagnostic_path, diagnostic)
        if is_unsupported_native_v0_diagnostic(diagnostic["code"]) and (
            is_empty_source_file(location) or not is_non_empty_source_span(location)
        ):
            errors.append(
                f"{diagnostic_path}.location: expected non-empty source span for "
                f"{UNSUPPORTED_NATIVE_V0_CODE}"
            )
        validate_missing_capabilities(errors, diagnostic_path, diagnostic)
        validate_diagnostic_source_location(
            errors,
            f"{diagnostic_path}.location",
            location,
        )
        if "originalLocation" in diagnostic:
            validate_diagnostic_source_location(
                errors,
                f"{diagnostic_path}.originalLocation",
                diagnostic["originalLocation"],
            )
    return errors
