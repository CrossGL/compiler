"""Semantic checks for target-capability-registry-v1.schema.json."""

from .common import add_equal_error
from .common import validate_unique_values


TARGET_ORDER = ("metal", "vulkan", "directx", "opengl")
DISPLAY_NAMES = {
    "metal": "Metal",
    "vulkan": "Vulkan",
    "directx": "DirectX",
    "opengl": "OpenGL",
}
PACKAGE_MODES = {
    "metal": "native",
    "vulkan": "native",
    "directx": "source-package",
    "opengl": "source-package",
}
NATIVE_ARTIFACT_FORMATS = {
    "metal": "metallib",
    "vulkan": "spirv",
    "directx": "dxil",
    "opengl": "glsl-source",
}
NATIVE_PATH_ARTIFACTS = {
    "metal": ["backendSource", "intermediate", "nativeBinary"],
    "vulkan": ["backendAssembly", "nativeBinary"],
    "directx": ["backendSource", "nativeBinary"],
    "opengl": ["backendSource", "nativeBinary"],
}
NATIVE_SUPPORT_CLASSES = {
    "metal": "native",
    "vulkan": "prototype-native",
    "directx": "planned-native",
    "opengl": "planned-native",
}
BASELINE_BACKEND_CAPABILITIES = {
    "metal": "metal.backend.native-metal-package",
    "vulkan": "vulkan.backend.vulkan-prototype-package",
    "directx": "directx.backend.hlsl-lowering",
    "opengl": "opengl.backend.glsl-lowering",
}
NATIVE_IMPLEMENTED = {
    "metal": True,
    "vulkan": True,
    "directx": False,
    "opengl": False,
}
SOURCE_PACKAGE_SELECTABLE = {
    "metal": False,
    "vulkan": False,
    "directx": True,
    "opengl": True,
}
ADMITTED_PACKAGE_MODES = {
    "metal": ["native"],
    "vulkan": ["native"],
    "directx": ["source-package"],
    "opengl": ["source-package"],
}
PACKAGE_DECISION_REASONS = {
    "metal": "native-package-available",
    "vulkan": "native-package-available",
    "directx": "source-package-available",
    "opengl": "source-package-available",
}
PACKAGE_RANK_SCORES = {
    "metal": 0,
    "vulkan": 0,
    "directx": 1,
    "opengl": 1,
}
NATIVE_BINARY_STATUS_POLICIES = {
    "metal": False,
    "vulkan": False,
    "directx": True,
    "opengl": True,
}
SOURCE_PACKAGE_OPTIONAL_NATIVE_TOOL_REQUIREMENTS = {
    "directx": ["directx.toolchain.dxc", "directx.validation.dxil-validator"],
    "opengl": [
        "opengl.toolchain.opengl-driver",
        "opengl.validation.glsl-program-validation",
    ],
}
TOOL_REQUIREMENT_KINDS = {"toolchain", "validation", "native-tool", "nativeTool"}
OPTIMIZATION_LEVEL_ORDER = ("O0", "O1", "O2")
REQUIRED_PACKAGE_TARGET_CONTRACT_EVIDENCE = (
    "tools/package_target_contracts.json",
    "cglc_package_target_contracts",
)
REQUIRED_PACKAGE_ADMISSION_EVIDENCE = (
    "include/crossgl/Backend/TargetCapabilityInventory.h",
    "src/Backend/TargetCapabilities.cpp",
    "tools/package_target_contracts.json",
    "cglc_package_target_contracts",
)
PACKAGE_ARTIFACT_REQUIREMENTS_SOURCE = "tools/package_target_contracts.json"


def capability_area(capability_id):
    parts = capability_id.split(".")
    if len(parts) < 3:
        return None
    return parts[1]


def capability_kind(capability_id):
    parts = capability_id.split(".")
    if len(parts) < 3:
        return None
    return parts[1]


def expected_native_status(native_artifact):
    if native_artifact["allowsPlannedNativeBinary"]:
        return "planned"
    return "supported"


def expected_package_artifact_evidence_ids(target, requirements):
    evidence_ids = [
        f"target-legalization.v1.{target}.package-artifacts."
        f"{requirements['packageMode']}"
    ]
    evidence_ids.extend(
        f"target-legalization.v1.{target}.package-artifact.required.{artifact}"
        for artifact in requirements["requiredPathArtifacts"]
    )
    if requirements["requiresNativeBinaryStatus"]:
        evidence_ids.append(
            f"target-legalization.v1.{target}."
            "package-artifact.native-binary-status.required"
        )
    if requirements["allowsPlannedNativeBinary"]:
        evidence_ids.append(
            f"target-legalization.v1.{target}."
            "package-artifact.planned-native-binary.allowed"
        )
    if requirements["allowsPlannedNativeSourceEvidence"]:
        evidence_ids.append(
            f"target-legalization.v1.{target}."
            "package-artifact.planned-native-source-evidence.allowed"
        )
    return evidence_ids


def validate_capability_link(errors, path, capability, expected_area, records):
    record = records.get(capability)
    if record is None:
        errors.append(f"{path}.capability: expected {capability!r} in capabilities")
        return
    add_equal_error(
        errors,
        f"{path}.capability area",
        record["area"],
        expected_area,
        "linked capability area",
    )


def validate_capability_evidence_mirror(
    errors,
    path,
    capability,
    expected_area,
    expected_evidence,
    records,
    record_paths,
):
    record = records.get(capability)
    if record is None:
        return
    add_equal_error(
        errors,
        f"{record_paths[capability]}.evidence",
        record["evidence"],
        expected_evidence,
        f"flattened evidence to mirror structured {expected_area} evidence",
    )


def validate_required_package_contract_evidence(errors, path, evidence):
    for required in REQUIRED_PACKAGE_TARGET_CONTRACT_EVIDENCE:
        if required not in evidence:
            errors.append(
                f"{path}.evidence: expected required package target contract "
                f"evidence {required!r}"
            )


def validate_required_package_admission_evidence(errors, path, evidence):
    for required in REQUIRED_PACKAGE_ADMISSION_EVIDENCE:
        if required not in evidence:
            errors.append(
                f"{path}.evidence: expected required package admission "
                f"evidence {required!r}"
            )


def validate_target_record(errors, path, record):
    target = record["target"]
    target_prefix = f"{target}."
    add_equal_error(
        errors,
        f"{path}.packageMode",
        record["packageMode"],
        PACKAGE_MODES[target],
        "registry v0 target package mode",
    )
    add_equal_error(
        errors,
        f"{path}.displayName",
        record["displayName"],
        DISPLAY_NAMES[target],
        "registry v0 target display name",
    )

    capability_ids = [capability["id"] for capability in record["capabilities"]]
    validate_unique_values(
        errors,
        f"{path}.capabilities",
        capability_ids,
        "capability id",
    )
    sorted_capability_ids = sorted(capability_ids)
    add_equal_error(
        errors,
        f"{path}.capabilities",
        capability_ids,
        sorted_capability_ids,
        "sorted capability ids",
    )

    records_by_id = {
        capability["id"]: capability for capability in record["capabilities"]
    }
    record_paths_by_id = {
        capability["id"]: f"{path}.capabilities[{index}]"
        for index, capability in enumerate(record["capabilities"])
    }
    expected_optimization_capability = f"{target}.optimization.hir-pipeline"
    expected_native_capability = (
        f"{target}.native-artifact.{NATIVE_ARTIFACT_FORMATS[target]}"
    )
    expected_package_admission_capability = (
        f"{target}.package-admission.native-source-package"
    )
    expected_capability_ids = sorted(
        [
            expected_native_capability,
            expected_optimization_capability,
            expected_package_admission_capability,
        ]
    )
    add_equal_error(
        errors,
        f"{path}.capabilities",
        sorted_capability_ids,
        expected_capability_ids,
        "registry v0 flattened capability ids",
    )
    for index, capability_id in enumerate(record["emittedBaselineCapabilities"]):
        if not capability_id.startswith(target_prefix):
            errors.append(
                f"{path}.emittedBaselineCapabilities[{index}]: "
                f"expected target prefix {target_prefix!r}"
            )
    emitted_tool_requirements = [
        capability_id
        for capability_id in record["emittedBaselineCapabilities"]
        if capability_kind(capability_id) in TOOL_REQUIREMENT_KINDS
    ]
    if record["packageMode"] == "source-package":
        expected_tool_requirements = (
            SOURCE_PACKAGE_OPTIONAL_NATIVE_TOOL_REQUIREMENTS.get(target)
        )
        if expected_tool_requirements is None:
            errors.append(
                f"{path}.emittedBaselineCapabilities: source-package target "
                f"{target!r} has no optional native tool requirement policy"
            )
        else:
            add_equal_error(
                errors,
                f"{path}.emittedBaselineCapabilities",
                emitted_tool_requirements,
                expected_tool_requirements,
                "source-package optional native tool requirements",
            )

    for index, capability in enumerate(record["capabilities"]):
        capability_path = f"{path}.capabilities[{index}]"
        if not capability["id"].startswith(target_prefix):
            errors.append(
                f"{capability_path}.id: expected target prefix {target_prefix!r}"
            )
        add_equal_error(
            errors,
            f"{capability_path}.area",
            capability["area"],
            capability_area(capability["id"]),
            "capability id area",
        )

    optimization = record["optimization"]
    add_equal_error(
        errors,
        f"{path}.optimization.capability",
        optimization["capability"],
        expected_optimization_capability,
        "registry v0 optimization capability",
    )
    validate_capability_link(
        errors,
        f"{path}.optimization",
        optimization["capability"],
        "optimization",
        records_by_id,
    )
    add_equal_error(
        errors,
        f"{path}.optimization.supported",
        optimization["supported"],
        True,
        "registry v0 optimization support",
    )
    expected_optimization_status = (
        "supported" if optimization["supported"] else "unsupported"
    )
    if optimization["capability"] in records_by_id:
        add_equal_error(
            errors,
            f"{path}.optimization.capability status",
            records_by_id[optimization["capability"]]["status"],
            expected_optimization_status,
            "optimization supported flag",
        )
    validate_capability_evidence_mirror(
        errors,
        path,
        optimization["capability"],
        "optimization",
        optimization["evidence"],
        records_by_id,
        record_paths_by_id,
    )
    validate_required_package_contract_evidence(
        errors, f"{path}.optimization", optimization["evidence"]
    )
    add_equal_error(
        errors,
        f"{path}.optimization.levels",
        optimization["levels"],
        list(OPTIMIZATION_LEVEL_ORDER),
        "registry v0 optimization levels",
    )

    native_artifact = record["nativeArtifact"]
    add_equal_error(
        errors,
        f"{path}.nativeArtifact.capability",
        native_artifact["capability"],
        expected_native_capability,
        "registry v0 native artifact capability",
    )
    validate_capability_link(
        errors,
        f"{path}.nativeArtifact",
        native_artifact["capability"],
        "native-artifact",
        records_by_id,
    )
    add_equal_error(
        errors,
        f"{path}.nativeArtifact.artifactFormat",
        native_artifact["artifactFormat"],
        NATIVE_ARTIFACT_FORMATS[target],
        "target native artifact format",
    )
    add_equal_error(
        errors,
        f"{path}.nativeArtifact.pathArtifacts",
        native_artifact["pathArtifacts"],
        NATIVE_PATH_ARTIFACTS[target],
        "target native artifact path artifacts",
    )
    native_status = expected_native_status(native_artifact)
    add_equal_error(
        errors,
        f"{path}.nativeArtifact.status",
        native_artifact["status"],
        native_status,
        "planned-native policy",
    )
    if native_artifact["capability"] in records_by_id:
        add_equal_error(
            errors,
            f"{path}.nativeArtifact.capability status",
            records_by_id[native_artifact["capability"]]["status"],
            native_artifact["status"],
            "native artifact status",
        )
    validate_capability_evidence_mirror(
        errors,
        path,
        native_artifact["capability"],
        "native-artifact",
        native_artifact["evidence"],
        records_by_id,
        record_paths_by_id,
    )
    validate_required_package_contract_evidence(
        errors, f"{path}.nativeArtifact", native_artifact["evidence"]
    )
    requires_native_binary_status = NATIVE_BINARY_STATUS_POLICIES[target]
    add_equal_error(
        errors,
        f"{path}.nativeArtifact.requiresNativeBinaryStatus",
        native_artifact["requiresNativeBinaryStatus"],
        requires_native_binary_status,
        "registry v0 native-binary-status policy",
    )
    add_equal_error(
        errors,
        f"{path}.nativeArtifact.allowsPlannedNativeBinary",
        native_artifact["allowsPlannedNativeBinary"],
        requires_native_binary_status,
        "registry v0 planned-native policy",
    )

    package_admission = record["packageAdmission"]
    add_equal_error(
        errors,
        f"{path}.packageAdmission.capability",
        package_admission["capability"],
        expected_package_admission_capability,
        "registry v0 package admission capability",
    )
    validate_capability_link(
        errors,
        f"{path}.packageAdmission",
        package_admission["capability"],
        "package-admission",
        records_by_id,
    )
    add_equal_error(
        errors,
        f"{path}.packageAdmission.packageMode",
        package_admission["packageMode"],
        record["packageMode"],
        "target package mode",
    )
    add_equal_error(
        errors,
        f"{path}.packageAdmission.nativeSupportClass",
        package_admission["nativeSupportClass"],
        NATIVE_SUPPORT_CLASSES[target],
        "registry v0 native support class",
    )
    add_equal_error(
        errors,
        f"{path}.packageAdmission.nativeImplemented",
        package_admission["nativeImplemented"],
        NATIVE_IMPLEMENTED[target],
        "registry v0 native implementation flag",
    )
    add_equal_error(
        errors,
        f"{path}.packageAdmission.sourcePackageSelectable",
        package_admission["sourcePackageSelectable"],
        SOURCE_PACKAGE_SELECTABLE[target],
        "registry v0 source package selectable flag",
    )
    add_equal_error(
        errors,
        f"{path}.packageAdmission.packageBuildSupported",
        package_admission["packageBuildSupported"],
        bool(ADMITTED_PACKAGE_MODES[target]),
        "registry v0 package build support flag",
    )
    add_equal_error(
        errors,
        f"{path}.packageAdmission.admittedPackageModes",
        package_admission["admittedPackageModes"],
        ADMITTED_PACKAGE_MODES[target],
        "registry v0 admitted package modes",
    )
    add_equal_error(
        errors,
        f"{path}.packageAdmission.baselineBackendCapability",
        package_admission["baselineBackendCapability"],
        BASELINE_BACKEND_CAPABILITIES[target],
        "registry v0 baseline backend capability",
    )
    if (
        package_admission["baselineBackendCapability"]
        not in record["emittedBaselineCapabilities"]
    ):
        errors.append(
            f"{path}.packageAdmission.baselineBackendCapability: expected "
            "capability to appear in emittedBaselineCapabilities"
        )
    add_equal_error(
        errors,
        f"{path}.packageAdmission.nativeArtifactCapability",
        package_admission["nativeArtifactCapability"],
        native_artifact["capability"],
        "native artifact capability link",
    )
    add_equal_error(
        errors,
        f"{path}.packageAdmission.packageDecisionReason",
        package_admission["packageDecisionReason"],
        PACKAGE_DECISION_REASONS[target],
        "registry v0 package decision reason",
    )
    add_equal_error(
        errors,
        f"{path}.packageAdmission.packageRankScore",
        package_admission["packageRankScore"],
        PACKAGE_RANK_SCORES[target],
        "registry v0 package rank score",
    )
    if package_admission["capability"] in records_by_id:
        expected_status = (
            "supported" if package_admission["packageBuildSupported"] else "unsupported"
        )
        add_equal_error(
            errors,
            f"{path}.packageAdmission.capability status",
            records_by_id[package_admission["capability"]]["status"],
            expected_status,
            "package build support flag",
        )
    validate_capability_evidence_mirror(
        errors,
        path,
        package_admission["capability"],
        "package-admission",
        package_admission["evidence"],
        records_by_id,
        record_paths_by_id,
    )
    validate_required_package_admission_evidence(
        errors, f"{path}.packageAdmission", package_admission["evidence"]
    )
    add_equal_error(
        errors,
        f"{path}.packageAdmission.packageArtifactRequirementsSource",
        package_admission["packageArtifactRequirementsSource"],
        PACKAGE_ARTIFACT_REQUIREMENTS_SOURCE,
        "registry v0 package artifact requirements source",
    )

    requirements = package_admission["packageArtifactRequirements"]
    requirements_path = f"{path}.packageAdmission.packageArtifactRequirements"
    add_equal_error(
        errors,
        f"{requirements_path}.packageMode",
        requirements["packageMode"],
        package_admission["packageMode"],
        "package admission mode",
    )
    add_equal_error(
        errors,
        f"{requirements_path}.requiredPathArtifacts",
        requirements["requiredPathArtifacts"],
        native_artifact["pathArtifacts"],
        "native artifact path artifacts",
    )
    add_equal_error(
        errors,
        f"{requirements_path}.requiresNativeBinaryStatus",
        requirements["requiresNativeBinaryStatus"],
        native_artifact["requiresNativeBinaryStatus"],
        "native artifact native-binary-status policy",
    )
    add_equal_error(
        errors,
        f"{requirements_path}.allowsPlannedNativeBinary",
        requirements["allowsPlannedNativeBinary"],
        native_artifact["allowsPlannedNativeBinary"],
        "native artifact planned native binary policy",
    )
    add_equal_error(
        errors,
        f"{requirements_path}.allowsPlannedNativeSourceEvidence",
        requirements["allowsPlannedNativeSourceEvidence"],
        native_artifact["allowsPlannedNativeBinary"],
        "planned native source evidence policy",
    )
    add_equal_error(
        errors,
        f"{requirements_path}.evidenceIds",
        requirements["evidenceIds"],
        expected_package_artifact_evidence_ids(target, requirements),
        "target legalization package artifact requirement evidence IDs",
    )


def validate_semantics(instance):
    errors = []
    targets = instance["targets"]
    target_names = [record["target"] for record in targets]
    add_equal_error(
        errors,
        "$.targetCount",
        instance["targetCount"],
        len(targets),
        "targets length",
    )
    add_equal_error(
        errors,
        "$.capabilityCount",
        instance["capabilityCount"],
        sum(len(record["capabilities"]) for record in targets),
        "flattened capability length",
    )
    validate_unique_values(errors, "$.targets", target_names, "target record")
    add_equal_error(
        errors,
        "$.targets",
        target_names,
        list(TARGET_ORDER),
        "registry v0 target order",
    )

    all_capability_ids = []
    for index, record in enumerate(targets):
        validate_target_record(errors, f"$.targets[{index}]", record)
        all_capability_ids.extend(
            capability["id"] for capability in record["capabilities"]
        )
    validate_unique_values(
        errors,
        "$.targets.capabilities",
        all_capability_ids,
        "capability id",
    )
    return errors
