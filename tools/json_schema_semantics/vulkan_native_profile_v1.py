"""Semantic checks for vulkan-native-profile-v1.schema.json."""

EXPECTED_TOOL_STATUS_BY_OPTIMIZATION_STATUS = {
    "applied": "available",
    "skipped-disabled": "not-run",
    "skipped-tool-missing": "missing",
}

EXPECTED_OPTIMIZATION_PROFILE_BY_REQUESTED_LEVEL = {
    "O0": {
        "policy": "disabled-by-opt-level",
        "level": "none",
        "statuses": {"skipped-disabled"},
    },
    "O1": {
        "policy": "disabled-by-opt-level",
        "level": "none",
        "statuses": {"skipped-disabled"},
    },
    "O2": {
        "policy": "use-when-available",
        "level": "-O",
        "statuses": {"applied", "skipped-tool-missing"},
    },
}


def contains_whitespace(value):
    return any(char.isspace() for char in value)


def path_has_parent_segment(value):
    return any(part == ".." for part in value.split("/"))


def validate_module_hygiene(errors, module):
    if module.strip() == "":
        errors.append("$.module: expected non-empty module")
    if contains_whitespace(module):
        errors.append("$.module: expected module without whitespace")
    if "/" in module or "\\" in module:
        errors.append("$.module: expected module stem without path separators")
    if module in (".", "..") or path_has_parent_segment(module):
        errors.append("$.module: expected module stem without parent segments")


def validate_package_path_hygiene(errors, path, value):
    if value is None:
        return
    if value.strip() == "":
        errors.append(f"{path}: expected non-empty package-relative path")
    if contains_whitespace(value):
        errors.append(f"{path}: expected path without whitespace")
    if "\\" in value:
        errors.append(f"{path}: expected normalized '/' path separators")
    if value.startswith("/"):
        errors.append(f"{path}: expected package-relative path")
    if len(value) >= 2 and value[1] == ":" and value[0].isalpha():
        errors.append(f"{path}: expected package-relative path")
    parts = value.split("/")
    if any(part in ("", ".", "..") for part in parts):
        errors.append(f"{path}: expected normalized package-relative path")


def canonical_artifact_paths(module):
    base = f"backend/vulkan/{module}"
    return {
        "backendAssembly": f"{base}.spvasm",
        "nativeBinary": f"{base}.spv",
        "disassembly": f"{base}.disassembly.spvasm",
    }


def validate_artifact_identity(errors, instance):
    expected_paths = canonical_artifact_paths(instance["module"])
    artifacts = instance["artifacts"]
    for field in ("backendAssembly", "nativeBinary"):
        actual = artifacts[field]
        validate_package_path_hygiene(errors, f"$.artifacts.{field}", actual)
        expected = expected_paths[field]
        if actual != expected:
            errors.append(
                f"$.artifacts.{field}: expected profile artifact path "
                f"{expected!r}, got {actual!r}"
            )


def validate_disassembly_evidence(errors, instance):
    disassembly = instance["debug"].get("disassembly")
    if not isinstance(disassembly, dict):
        return

    status = disassembly["status"]
    path = disassembly["path"]
    validate_package_path_hygiene(errors, "$.debug.disassembly.path", path)
    expected_path = canonical_artifact_paths(instance["module"])["disassembly"]
    if status == "emitted":
        if path != expected_path:
            errors.append(
                "$.debug.disassembly.path: emitted disassembly requires path "
                f"{expected_path!r}, got {path!r}"
            )
        return

    if path is not None:
        errors.append(f"$.debug.disassembly.path: status {status!r} requires null path")


def validate_optimization_evidence(errors, instance):
    debug = instance["debug"]
    optimization = debug.get("optimization")
    if not isinstance(optimization, dict):
        return

    validation_target_env = debug["validationTargetEnv"]
    requested_level = optimization.get("requestedLevel")
    target_env = optimization.get("targetEnv")
    tool_status = optimization.get("toolStatus")
    status = optimization["status"]

    if requested_level is not None:
        expected_profile = EXPECTED_OPTIMIZATION_PROFILE_BY_REQUESTED_LEVEL[
            requested_level
        ]
        expected_policy = expected_profile["policy"]
        if optimization["policy"] != expected_policy:
            errors.append(
                "$.debug.optimization.policy: requestedLevel "
                f"{requested_level!r} requires {expected_policy!r}, got "
                f"{optimization['policy']!r}"
            )

        expected_level = expected_profile["level"]
        if optimization["level"] != expected_level:
            errors.append(
                "$.debug.optimization.level: requestedLevel "
                f"{requested_level!r} requires {expected_level!r}, got "
                f"{optimization['level']!r}"
            )

        expected_statuses = expected_profile["statuses"]
        if status not in expected_statuses:
            if len(expected_statuses) == 1:
                expected_status = next(iter(expected_statuses))
                expected_status_label = repr(expected_status)
            else:
                expected_status_label = repr(sorted(expected_statuses))
            errors.append(
                "$.debug.optimization.status: requestedLevel "
                f"{requested_level!r} requires {expected_status_label}, got "
                f"{status!r}"
            )

        if target_env is None:
            errors.append(
                "$.debug.optimization.targetEnv: current optimization evidence "
                "requires targetEnv"
            )
        elif target_env != validation_target_env:
            errors.append(
                "$.debug.optimization.targetEnv: expected validation target env "
                f"{validation_target_env!r}, got {target_env!r}"
            )

        expected_tool_status = EXPECTED_TOOL_STATUS_BY_OPTIMIZATION_STATUS[status]
        if tool_status is None:
            errors.append(
                "$.debug.optimization.toolStatus: current optimization evidence "
                "requires toolStatus"
            )
        elif tool_status != expected_tool_status:
            errors.append(
                "$.debug.optimization.toolStatus: status "
                f"{status!r} requires {expected_tool_status!r}, got "
                f"{tool_status!r}"
            )
        return

    if target_env is not None and target_env != validation_target_env:
        errors.append(
            "$.debug.optimization.targetEnv: expected validation target env "
            f"{validation_target_env!r}, got {target_env!r}"
        )
    if tool_status is not None:
        expected_tool_status = EXPECTED_TOOL_STATUS_BY_OPTIMIZATION_STATUS[status]
        if tool_status != expected_tool_status:
            errors.append(
                "$.debug.optimization.toolStatus: status "
                f"{status!r} requires {expected_tool_status!r}, got "
                f"{tool_status!r}"
            )


def validate_semantics(instance):
    errors = []
    validate_module_hygiene(errors, instance["module"])
    validate_artifact_identity(errors, instance)
    validate_optimization_evidence(errors, instance)
    validate_disassembly_evidence(errors, instance)
    return errors
