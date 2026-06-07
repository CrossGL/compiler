"""Semantic checks for native-artifact-v0.schema.json."""

from package_target_contracts import PACKAGE_TARGET_CONTRACTS
from package_target_contracts import SOURCE_PACKAGE_TARGETS


PACKAGE_TARGET_NAMES = {contract.target for contract in PACKAGE_TARGET_CONTRACTS}

TARGET_BINARY_KINDS = {
    "metal": {"metal.metallib"},
    "vulkan": {"vulkan.spirv-module"},
    "directx": {"directx.dxil", "directx.dxbc"},
    "opengl": {"opengl.source", "opengl.package"},
}

BINARY_KIND_EXTENSIONS = {
    "metal.metallib": (".metallib",),
    "vulkan.spirv-module": (".spv",),
    "directx.dxil": (".dxil",),
    "directx.dxbc": (".dxbc",),
    "opengl.source": (".glsl",),
    "opengl.package": (".cglb", ".zip", ".tar", ".tar.gz"),
}

BINARY_KIND_REQUIRED_ROLES = {
    "metal.metallib": {"compiler", "linker"},
    "vulkan.spirv-module": {"assembler"},
    "directx.dxil": {"compiler"},
    "directx.dxbc": {"compiler"},
    "opengl.source": {"generator"},
    "opengl.package": {"packager"},
}

PLANNED_SOURCE_PACKAGE_ROLES = {"generator"}
PLANNED_SOURCE_PACKAGE_OPTIMIZATION_LEVEL = "unknown"
PLANNED_SOURCE_PACKAGE_GENERATORS = {
    "directx": "CrossGL DirectX backend",
    "opengl": "CrossGL OpenGL backend",
}
VALIDATION_STATUSES_WITHOUT_VALIDATOR = {"not-run", "unavailable"}
OPTIMIZED_VULKAN_EVIDENCE = {
    "requestedLevel": "O2",
    "effectiveLevel": "O2",
    "policy": "use-when-available",
    "status": "applied",
    "tool": "spirv-opt",
    "toolFlag": "-O",
}


def is_windows_drive_path(path):
    if len(path) < 2:
        return False
    return path[0].isalpha() and path[1] == ":"


def is_source_package_target(target):
    return target in SOURCE_PACKAGE_TARGETS


def tool_roles(instance):
    return {
        tool["role"]
        for tool in instance["toolchainProvenance"]["tools"]
        if isinstance(tool, dict) and "role" in tool
    }


def tools_with_role(instance, role):
    return [
        tool
        for tool in instance["toolchainProvenance"]["tools"]
        if isinstance(tool, dict) and tool.get("role") == role
    ]


def validate_target_contract_alignment(errors):
    matrix_targets = set(TARGET_BINARY_KINDS)
    if matrix_targets != PACKAGE_TARGET_NAMES:
        errors.append(
            "$.target: native artifact targets must match package target "
            f"contracts, got {sorted(matrix_targets)!r}, expected "
            f"{sorted(PACKAGE_TARGET_NAMES)!r}"
        )


def validate_binary_kind(errors, instance):
    target = instance["target"]
    binary_kind = instance["binaryKind"]
    allowed = TARGET_BINARY_KINDS[target]
    if binary_kind not in allowed:
        errors.append(
            f"$.binaryKind: target {target!r} cannot use binaryKind {binary_kind!r}"
        )

    artifact_path = instance.get("artifactPath")
    if artifact_path is None:
        return

    allowed_extensions = BINARY_KIND_EXTENSIONS[binary_kind]
    if not artifact_path.endswith(allowed_extensions):
        errors.append(
            f"$.artifactPath: binaryKind {binary_kind!r} requires extension "
            f"{allowed_extensions!r}"
        )


def validate_normalized_paths(errors, instance):
    for field_name in ("artifactPath", "sourcePath"):
        path = instance.get(field_name)
        if isinstance(path, str) and is_windows_drive_path(path):
            errors.append(
                f"$.{field_name}: normalized paths must not use Windows "
                "drive-prefixed form"
            )


def validate_artifact_fingerprint(errors, instance):
    has_artifact_path = "artifactPath" in instance
    has_artifact_hash = "artifactHash" in instance
    has_size_bytes = "sizeBytes" in instance
    if has_artifact_path and not has_artifact_hash:
        errors.append("$.artifactHash: produced artifacts require artifactHash")
    if has_artifact_path and not has_size_bytes:
        errors.append("$.sizeBytes: produced artifacts require sizeBytes")
    if has_artifact_hash and not has_artifact_path:
        errors.append("$.artifactHash: artifactHash requires artifactPath")
    if has_size_bytes and not has_artifact_path:
        errors.append("$.sizeBytes: sizeBytes requires artifactPath")
    if has_size_bytes and not has_artifact_hash:
        errors.append("$.sizeBytes: sizeBytes requires artifactHash")


def validate_toolchain_roles(errors, instance):
    roles = tool_roles(instance)
    binary_kind = instance["binaryKind"]
    validation_status = instance["validationStatus"]
    if (
        validation_status in VALIDATION_STATUSES_WITHOUT_VALIDATOR
        and "validator" in roles
    ):
        errors.append(
            "$.toolchainProvenance.tools: "
            f"validationStatus {validation_status!r} must not include "
            "validator tool role"
        )

    if instance.get("nativeBinaryStatus") == "planned":
        if "generator" not in roles:
            errors.append(
                "$.toolchainProvenance.tools: planned source-package "
                "descriptors require a generator tool role"
            )
        unexpected_roles = sorted(roles - PLANNED_SOURCE_PACKAGE_ROLES)
        if unexpected_roles:
            errors.append(
                "$.toolchainProvenance.tools: planned source-package "
                "descriptors must only declare generator tool roles, got "
                f"{unexpected_roles!r}"
            )
        generators = tools_with_role(instance, "generator")
        expected_generator = PLANNED_SOURCE_PACKAGE_GENERATORS.get(instance["target"])
        if expected_generator is None:
            errors.append(
                "$.toolchainProvenance.tools: planned source-package "
                f"descriptors require a generator contract for {instance['target']!r}"
            )
        elif len(generators) != 1 or generators[0].get("name") != expected_generator:
            errors.append(
                "$.toolchainProvenance.tools: planned source-package "
                f"descriptors require exactly one generator named {expected_generator!r}"
            )
        return

    required_roles = BINARY_KIND_REQUIRED_ROLES[binary_kind]
    missing_roles = sorted(required_roles - roles)
    if missing_roles:
        errors.append(
            "$.toolchainProvenance.tools: "
            f"binaryKind {binary_kind!r} requires tool roles {missing_roles!r}"
        )

    if validation_status in {"validated", "failed"} and "validator" not in roles:
        errors.append(
            "$.toolchainProvenance.tools: "
            f"{validation_status} artifacts require a validator tool role"
        )


def validate_native_binary_status(errors, instance):
    target = instance["target"]
    status = instance.get("nativeBinaryStatus")
    artifact_path = instance.get("artifactPath")
    artifact_hash = instance.get("artifactHash")
    size_bytes = instance.get("sizeBytes")
    validation_status = instance["validationStatus"]

    if is_source_package_target(target):
        if status is None:
            errors.append(
                f"$.nativeBinaryStatus: {target} descriptors require nativeBinaryStatus"
            )
            return
    elif status is not None:
        errors.append(
            f"$.nativeBinaryStatus: {target} descriptors must not declare "
            "nativeBinaryStatus"
        )
        return
    else:
        if artifact_path is None and artifact_hash is None and size_bytes is None:
            errors.append(
                "$.artifactPath: produced target descriptors require artifactPath"
            )
            errors.append(
                "$.artifactHash: produced target descriptors require artifactHash"
            )
            errors.append("$.sizeBytes: produced target descriptors require sizeBytes")
        return

    if status == "planned":
        if artifact_path is not None:
            errors.append(
                "$.artifactPath: planned source-package descriptors must not "
                "declare artifactPath"
            )
        if artifact_hash is not None:
            errors.append(
                "$.artifactHash: planned source-package descriptors must not "
                "declare artifactHash"
            )
        if size_bytes is not None:
            errors.append(
                "$.sizeBytes: planned source-package descriptors must not "
                "declare sizeBytes"
            )
        if validation_status != "unavailable":
            errors.append(
                "$.validationStatus: planned source-package descriptors require "
                "validationStatus 'unavailable'"
            )
        optimization_level = instance.get("optimizationLevel")
        if optimization_level != PLANNED_SOURCE_PACKAGE_OPTIMIZATION_LEVEL:
            errors.append(
                "$.optimizationLevel: planned source-package descriptors must "
                f"use {PLANNED_SOURCE_PACKAGE_OPTIMIZATION_LEVEL!r}, got "
                f"{optimization_level!r}"
            )
    else:
        if artifact_path is None:
            errors.append(
                f"$.artifactPath: nativeBinaryStatus {status!r} requires artifactPath"
            )
        if artifact_hash is None:
            errors.append(
                f"$.artifactHash: nativeBinaryStatus {status!r} requires artifactHash"
            )
        if size_bytes is None:
            errors.append(
                f"$.sizeBytes: nativeBinaryStatus {status!r} requires sizeBytes"
            )

    if validation_status == "validated" and status != "validated":
        errors.append(
            "$.nativeBinaryStatus: validationStatus 'validated' requires "
            "nativeBinaryStatus 'validated'"
        )
    if status == "validated" and validation_status != "validated":
        errors.append(
            "$.validationStatus: nativeBinaryStatus 'validated' requires "
            "validationStatus 'validated'"
        )


def validate_validation_status(errors, instance):
    validation_status = instance["validationStatus"]
    diagnostics = instance["validationDiagnostics"]
    if validation_status == "failed" and not diagnostics:
        errors.append("$.validationDiagnostics: failed artifacts require diagnostics")
    if validation_status != "failed" and diagnostics:
        errors.append(
            "$.validationDiagnostics: non-failed artifacts must not include diagnostics"
        )


def has_produced_artifact(instance):
    return all(
        field in instance for field in ("artifactPath", "artifactHash", "sizeBytes")
    )


def has_toolchain_tool(instance, name):
    return any(
        tool.get("name") == name
        for tool in instance["toolchainProvenance"]["tools"]
        if isinstance(tool, dict)
    )


def validate_optimization_evidence(errors, instance):
    evidence = instance.get("optimizationEvidence")
    if not isinstance(evidence, dict):
        return

    status = evidence.get("status")
    evidence_source = evidence.get("evidenceSource")
    if status == "applied" and not has_produced_artifact(instance):
        errors.append(
            "$.optimizationEvidence.status: applied optimization evidence "
            "requires produced artifact facts"
        )

    if instance.get("nativeBinaryStatus") == "planned" and status == "applied":
        errors.append(
            "$.optimizationEvidence.status: planned source-package descriptors "
            "must not claim applied optimization"
        )

    tool = evidence.get("tool")
    if (
        status == "applied"
        and isinstance(tool, str)
        and (
            not isinstance(evidence_source, dict)
            or evidence_source.get("kind") != "native-profile"
        )
        and not has_toolchain_tool(instance, tool)
    ):
        errors.append(
            "$.optimizationEvidence.tool: applied optimization evidence tool "
            f"{tool!r} must match toolchainProvenance.tools[].name"
        )

    if instance.get("target") == "vulkan" and status == "applied":
        for field, expected in OPTIMIZED_VULKAN_EVIDENCE.items():
            actual = evidence.get(field)
            if actual != expected:
                errors.append(
                    f"$.optimizationEvidence.{field}: optimized-native Vulkan "
                    f"evidence requires {expected!r}, got {actual!r}"
                )
        if not isinstance(evidence_source, dict):
            errors.append(
                "$.optimizationEvidence.evidenceSource: optimized-native Vulkan "
                "evidence requires native-profile evidenceSource path"
            )
        else:
            if evidence_source.get("kind") != "native-profile":
                errors.append(
                    "$.optimizationEvidence.evidenceSource.kind: "
                    "optimized-native Vulkan evidence requires 'native-profile'"
                )
            if not isinstance(evidence_source.get("path"), str):
                errors.append(
                    "$.optimizationEvidence.evidenceSource.path: "
                    "optimized-native Vulkan evidence requires native-profile path"
                )


def validate_duplicate_tools(errors, instance):
    seen = set()
    for index, tool in enumerate(instance["toolchainProvenance"]["tools"]):
        key = (tool["name"], tool["role"])
        if key in seen:
            errors.append(
                f"$.toolchainProvenance.tools[{index}]: duplicate tool role record "
                f"{key!r}"
            )
        seen.add(key)


def validate_semantics(instance):
    errors = []
    validate_target_contract_alignment(errors)
    validate_binary_kind(errors, instance)
    validate_normalized_paths(errors, instance)
    validate_artifact_fingerprint(errors, instance)
    validate_toolchain_roles(errors, instance)
    validate_native_binary_status(errors, instance)
    validate_validation_status(errors, instance)
    validate_optimization_evidence(errors, instance)
    validate_duplicate_tools(errors, instance)
    return errors
