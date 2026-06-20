"""Semantic checks for doctor-v1.schema.json."""

from .common import add_equal_error
from .common import validate_target_explanation_document
from .target_explanation_v1 import (
    SOURCE_PACKAGE_OPTIONAL_NATIVE_EVIDENCE,
    validate_source_package_support_consistency,
    validate_target_explanation_consumer_context,
    validate_target_explanation_legalization_core_evidence,
)
from .target_explanation_v1 import validate_source_package_optional_native_evidence


OPTIONAL_NATIVE_TOOL_NAMES = (
    "dxc",
    "glslangValidator",
    "spirv-as",
    "spirv-val",
    "spirv-opt",
    "spirv-dis",
    "metal",
    "metallib",
)

# Only map capabilities represented directly by a doctor tool row here.
# OpenGL program validation is native/runtime evidence, not glslang source validation.
OPTIONAL_NATIVE_TOOL_CAPABILITIES = {
    "directx.toolchain.dxc": "dxc",
}


def validate_tool_record(errors, path, tool):
    name = tool["name"]
    available = tool["available"]
    evidence_status = tool.get("evidenceStatus")
    source = tool["source"]
    path_value = tool["path"]
    resolved_path = tool["resolvedPath"]
    probe_status = tool["probeStatus"]
    version = tool["version"]
    version_detail = tool["versionDetail"]

    if available:
        if source == "not-found":
            errors.append(f"{path}.source: available tool {name!r} cannot be not-found")
        if not resolved_path:
            errors.append(
                f"{path}.resolvedPath: available tool {name!r} requires a path"
            )
        add_equal_error(
            errors,
            f"{path}.path",
            path_value,
            resolved_path,
            "resolvedPath",
        )
    else:
        add_equal_error(errors, f"{path}.path", path_value, "", "unavailable path")
        add_equal_error(
            errors,
            f"{path}.resolvedPath",
            resolved_path,
            "",
            "unavailable resolvedPath",
        )
        if evidence_status is not None:
            add_equal_error(
                errors,
                f"{path}.evidenceStatus",
                evidence_status,
                "tool-missing",
                "unavailable evidenceStatus",
            )
        add_equal_error(
            errors,
            f"{path}.probeStatus",
            probe_status,
            "unavailable",
            "unavailable probeStatus",
        )

    if probe_status == "unavailable":
        if available:
            errors.append(f"{path}.probeStatus: available tool {name!r} was not probed")
        if evidence_status is not None:
            add_equal_error(
                errors,
                f"{path}.evidenceStatus",
                evidence_status,
                "tool-missing",
                "unavailable evidenceStatus",
            )
        add_equal_error(errors, f"{path}.version", version, "", "unavailable version")
        add_equal_error(
            errors,
            f"{path}.versionDetail",
            version_detail,
            "",
            "unavailable versionDetail",
        )
    elif not available:
        errors.append(
            f"{path}.probeStatus: unavailable tool {name!r} must be unavailable"
        )
    elif probe_status == "succeeded":
        if evidence_status is not None:
            add_equal_error(
                errors,
                f"{path}.evidenceStatus",
                evidence_status,
                "version-captured",
                "succeeded evidenceStatus",
            )
        if not version:
            errors.append(
                f"{path}.version: succeeded probe for tool {name!r} "
                "requires captured version text"
            )
        add_equal_error(
            errors,
            f"{path}.versionDetail",
            version_detail,
            "",
            "succeeded versionDetail",
        )
    elif probe_status == "version-unknown":
        if evidence_status is not None:
            add_equal_error(
                errors,
                f"{path}.evidenceStatus",
                evidence_status,
                "version-unknown",
                "version-unknown evidenceStatus",
            )
        add_equal_error(
            errors,
            f"{path}.version",
            version,
            "",
            "version-unknown version",
        )
        if not version_detail:
            errors.append(
                f"{path}.versionDetail: version-unknown probe for tool "
                f"{name!r} requires detail"
            )
    elif probe_status in ("failed", "not-started"):
        if evidence_status is not None:
            add_equal_error(
                errors,
                f"{path}.evidenceStatus",
                evidence_status,
                "probe-failed",
                f"{probe_status} evidenceStatus",
            )
        add_equal_error(
            errors,
            f"{path}.version",
            version,
            "",
            f"{probe_status} version",
        )
        if not version_detail:
            errors.append(
                f"{path}.versionDetail: {probe_status} probe for tool "
                f"{name!r} requires detail"
            )


def validate_toolchain_configuration(errors, toolchain):
    if "hasLLVM" in toolchain and "llvmConfigured" in toolchain:
        add_equal_error(
            errors,
            "$.toolchain.hasLLVM",
            toolchain["hasLLVM"],
            toolchain["llvmConfigured"],
            "llvmConfigured",
        )

    if "mlirConfigured" in toolchain:
        add_equal_error(
            errors,
            "$.toolchain.hasMLIR",
            toolchain["hasMLIR"],
            toolchain["mlirConfigured"],
            "mlirConfigured",
        )

    if toolchain.get("mlirNativePipelineAvailable") is True:
        if "mlirConfigured" in toolchain:
            if not toolchain["mlirConfigured"]:
                errors.append(
                    "$.toolchain.mlirNativePipelineAvailable: "
                    "requires mlirConfigured true"
                )
        elif not toolchain["hasMLIR"]:
            errors.append(
                "$.toolchain.mlirNativePipelineAvailable: requires hasMLIR true"
            )


def validate_toolchain(errors, toolchain):
    tools = toolchain["tools"]
    seen_names = {}
    for index, tool in enumerate(tools):
        name = tool["name"]
        path = f"$.toolchain.tools[{index}]"
        validate_tool_record(errors, path, tool)
        if name in seen_names:
            errors.append(
                f"$.toolchain.tools: duplicate tool name {name!r} at indexes "
                f"{seen_names[name]} and {index}"
            )
        else:
            seen_names[name] = index

    for name in OPTIONAL_NATIVE_TOOL_NAMES:
        if name not in seen_names:
            errors.append(f"$.toolchain.tools: missing optional native tool {name!r}")


def validate_target_explanation_toolchain_evidence(
    errors, toolchain, target_explanation
):
    tools_by_name = {
        tool["name"]: (index, tool) for index, tool in enumerate(toolchain["tools"])
    }
    for target_index, record in enumerate(target_explanation["targets"]):
        if record["packageMode"] != "source-package":
            continue
        evidence_capabilities = SOURCE_PACKAGE_OPTIONAL_NATIVE_EVIDENCE.get(
            record["target"]
        )
        if evidence_capabilities is None:
            continue
        missing_capabilities = set(record["missingCapabilities"])
        for capability in evidence_capabilities:
            tool_name = OPTIONAL_NATIVE_TOOL_CAPABILITIES.get(capability)
            if tool_name is None or capability not in missing_capabilities:
                continue
            tool_entry = tools_by_name.get(tool_name)
            if tool_entry is None:
                continue
            tool_index, tool = tool_entry
            if tool["available"]:
                errors.append(
                    f"$.targetExplanation.targets[{target_index}].missingCapabilities: "
                    f"optional native tool capability {capability!r} cannot be "
                    f"missing when $.toolchain.tools[{tool_index}].available is true"
                )


def validate_semantics(instance):
    errors = []
    toolchain = instance["toolchain"]
    validate_toolchain_configuration(errors, toolchain)
    target_explanation = instance["targetExplanation"]
    if target_explanation is not None:
        validate_target_explanation_document(
            errors,
            "$.targetExplanation",
            target_explanation,
        )
        validate_target_explanation_legalization_core_evidence(
            errors,
            "$.targetExplanation",
            target_explanation,
        )
        validate_target_explanation_consumer_context(
            errors,
            "$.targetExplanation",
            target_explanation,
        )
        validate_source_package_support_consistency(
            errors,
            "$.targetExplanation",
            target_explanation,
        )
        add_equal_error(
            errors,
            "$.targetExplanation.defaultTarget",
            target_explanation["defaultTarget"],
            toolchain["defaultTarget"],
            "toolchain defaultTarget",
        )
        validate_source_package_optional_native_evidence(
            errors,
            "$.targetExplanation",
            target_explanation,
        )
        validate_target_explanation_toolchain_evidence(
            errors,
            toolchain,
            target_explanation,
        )
    validate_toolchain(errors, toolchain)
    return errors
