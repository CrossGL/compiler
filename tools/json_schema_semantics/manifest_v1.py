"""Semantic checks for manifest-v1.schema.json."""

import re

from package_target_contracts import (
    PACKAGE_TARGET_CONTRACTS,
    PACKAGE_TARGETS_REQUIRING_NATIVE_STATUS,
    TARGET_REQUIRED_PATH_ARTIFACTS,
)


SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")
WINDOWS_DRIVE_PATH = re.compile(r"^[A-Za-z]:")
TOOL_REQUIREMENT_ID_PATTERN = re.compile(
    r"^(metal|vulkan|directx|opengl)\.(native-tool|toolchain|validation)\."
    r"[A-Za-z0-9_.-]+$"
)


def validate_source_hash(errors, source_hash):
    if source_hash["algorithm"] == "sha256" and not SHA256_PATTERN.match(
        source_hash["value"]
    ):
        errors.append("$.sourceHash.value: expected 64 lowercase hexadecimal sha256")


def validate_artifact_paths(errors, artifacts):
    for name, value in artifacts.items():
        if name == "nativeBinaryStatus":
            continue
        path = f"$.artifacts.{name}"
        if value == "":
            errors.append(f"{path}: artifact path must not be empty")
        if "\\" in value:
            errors.append(f"{path}: artifact paths must use '/' separators")
        if value.startswith("/") or WINDOWS_DRIVE_PATH.match(value):
            errors.append(f"{path}: artifact path must be package-relative")
        if ".." in value.split("/"):
            errors.append(f"{path}: artifact path must stay inside package")


def validate_artifact_path_uniqueness(errors, artifacts):
    seen_paths = {}
    for name, value in artifacts.items():
        if name == "nativeBinaryStatus":
            continue
        previous_name = seen_paths.get(value)
        if previous_name is not None:
            errors.append(
                f"$.artifacts.{name}: "
                f"artifact path duplicates $.artifacts.{previous_name}"
            )
        else:
            seen_paths[value] = name


def validate_debug_artifact_pair(errors, artifacts):
    has_debug_metadata = "debugMetadata" in artifacts
    has_hir_source_map = "hirSourceMap" in artifacts
    if has_debug_metadata != has_hir_source_map:
        errors.append(
            "$.artifacts: debugMetadata and hirSourceMap must be emitted together"
        )
    if "sourceRemap" in artifacts and not (has_debug_metadata and has_hir_source_map):
        errors.append(
            "$.artifacts.sourceRemap: sourceRemap provenance requires "
            "debugMetadata and hirSourceMap"
        )


def validate_target_specific_artifacts(errors, target, artifacts):
    if "nativeProfile" in artifacts and target != "vulkan":
        errors.append(
            "$.artifacts.nativeProfile: nativeProfile is only valid for vulkan packages"
        )


def legacy_package_artifact_requirements(target):
    required_path_artifacts = TARGET_REQUIRED_PATH_ARTIFACTS[target]
    requires_native_status = target in PACKAGE_TARGETS_REQUIRING_NATIVE_STATUS
    return {
        "target": target,
        "packageMode": "source-package" if requires_native_status else "native",
        "requiredPathArtifacts": required_path_artifacts,
        "requiresNativeBinaryStatus": requires_native_status,
        "allowsPlannedNativeBinary": requires_native_status,
        "allowsPlannedNativeSourceEvidence": requires_native_status,
    }


def package_target_contract(target):
    return next(
        (
            contract
            for contract in PACKAGE_TARGET_CONTRACTS
            if contract.target == target
        ),
        None,
    )


def validate_package_artifact_requirements(errors, target, manifest):
    if "packageArtifactRequirements" not in manifest:
        return legacy_package_artifact_requirements(target)

    requirements = manifest["packageArtifactRequirements"]
    if not isinstance(requirements, dict):
        errors.append("$.packageArtifactRequirements: expected object")
        return legacy_package_artifact_requirements(target)

    if requirements["target"] != target:
        errors.append(
            "$.packageArtifactRequirements.target: must match manifest target"
        )
    if (
        requirements["allowsPlannedNativeSourceEvidence"]
        and not requirements["allowsPlannedNativeBinary"]
    ):
        errors.append(
            "$.packageArtifactRequirements.allowsPlannedNativeSourceEvidence: "
            "requires allowsPlannedNativeBinary"
        )
    contract = package_target_contract(target)
    if contract is not None:
        expected_mode = (
            "source-package" if contract.requires_native_binary_status else "native"
        )
        if requirements["packageMode"] != expected_mode:
            errors.append(
                "$.packageArtifactRequirements.packageMode: "
                f"expected target contract mode {expected_mode!r}"
            )
        if (
            requirements["requiresNativeBinaryStatus"]
            != contract.requires_native_binary_status
            or requirements["allowsPlannedNativeBinary"]
            != contract.allows_planned_native_binary
            or requirements["allowsPlannedNativeSourceEvidence"]
            != contract.allows_planned_native_source_evidence
        ):
            errors.append(
                "$.packageArtifactRequirements: native binary policy must match "
                "target contract"
            )
        expected_artifacts = list(contract.required_path_artifacts)
        if requirements["requiredPathArtifacts"] != expected_artifacts:
            errors.append(
                "$.packageArtifactRequirements.requiredPathArtifacts: "
                f"expected target contract artifacts {expected_artifacts!r}"
            )
    evidence_ids = requirements.get("evidenceIds")
    if isinstance(evidence_ids, list):
        expected_evidence_ids = [
            f"target-legalization.v1.{target}.package-artifacts."
            f"{requirements['packageMode']}"
        ]
        expected_evidence_ids.extend(
            f"target-legalization.v1.{target}.package-artifact.required.{name}"
            for name in requirements["requiredPathArtifacts"]
        )
        if requirements["requiresNativeBinaryStatus"]:
            expected_evidence_ids.append(
                f"target-legalization.v1.{target}."
                "package-artifact.native-binary-status.required"
            )
        if requirements["allowsPlannedNativeBinary"]:
            expected_evidence_ids.append(
                f"target-legalization.v1.{target}."
                "package-artifact.planned-native-binary.allowed"
            )
        if requirements["allowsPlannedNativeSourceEvidence"]:
            expected_evidence_ids.append(
                f"target-legalization.v1.{target}."
                "package-artifact.planned-native-source-evidence.allowed"
            )
        if evidence_ids != expected_evidence_ids:
            errors.append(
                "$.packageArtifactRequirements.evidenceIds: "
                f"expected package artifact evidence IDs {expected_evidence_ids!r}"
            )
    return requirements


def optional_native_tool_status(package_mode, required_tool_ids, missing_tool_ids):
    if package_mode != "source-package":
        return "not-required"
    if missing_tool_ids:
        return "missing"
    if required_tool_ids:
        return "available"
    return "not-required"


def tool_requirement_evidence_id(target, status, tool_id):
    _tool_target, kind, name = tool_id.split(".", 2)
    return f"target-legalization.v1.{target}.tool-requirement.{status}.{kind}.{name}"


def expected_tool_requirement_evidence_ids(target, required_tool_ids, missing_tool_ids):
    state = "present" if required_tool_ids or missing_tool_ids else "empty"
    evidence_ids = [f"target-legalization.v1.{target}.tool-requirements.{state}"]
    evidence_ids.extend(
        tool_requirement_evidence_id(target, "required", tool_id)
        for tool_id in required_tool_ids
    )
    evidence_ids.extend(
        tool_requirement_evidence_id(target, "missing", tool_id)
        for tool_id in missing_tool_ids
    )
    return evidence_ids


def validate_target_legalization_tool_requirements(
    errors, target, manifest, requirements
):
    if "targetLegalizationToolRequirements" not in manifest:
        return

    tool_requirements = manifest["targetLegalizationToolRequirements"]
    if tool_requirements["target"] != target:
        errors.append(
            "$.targetLegalizationToolRequirements.target: must match manifest target"
        )

    package_mode = tool_requirements["packageMode"]
    if package_mode != requirements["packageMode"]:
        errors.append(
            "$.targetLegalizationToolRequirements.packageMode: must match "
            "packageArtifactRequirements.packageMode"
        )

    required_tool_ids = tool_requirements["requiredToolIds"]
    missing_tool_ids = tool_requirements["missingToolIds"]
    if tool_requirements["requiredToolCount"] != len(required_tool_ids):
        errors.append(
            "$.targetLegalizationToolRequirements.requiredToolCount: must match "
            "requiredToolIds length"
        )
    if tool_requirements["missingToolCount"] != len(missing_tool_ids):
        errors.append(
            "$.targetLegalizationToolRequirements.missingToolCount: must match "
            "missingToolIds length"
        )

    missing_not_required = sorted(set(missing_tool_ids) - set(required_tool_ids))
    if missing_not_required:
        errors.append(
            "$.targetLegalizationToolRequirements.missingToolIds: must be a "
            f"subset of requiredToolIds, extra IDs {missing_not_required!r}"
        )

    for key in ("requiredToolIds", "missingToolIds"):
        for tool_id in tool_requirements[key]:
            match = TOOL_REQUIREMENT_ID_PATTERN.match(tool_id)
            if match and match.group(1) != target:
                errors.append(
                    f"$.targetLegalizationToolRequirements.{key}: tool ID "
                    f"{tool_id!r} must match manifest target"
                )

    expected_missing = package_mode == "source-package" and bool(missing_tool_ids)
    if tool_requirements["optionalNativeToolMissing"] != expected_missing:
        errors.append(
            "$.targetLegalizationToolRequirements.optionalNativeToolMissing: "
            f"expected {expected_missing!r} for package mode {package_mode!r}"
        )

    expected_status = optional_native_tool_status(
        package_mode, required_tool_ids, missing_tool_ids
    )
    if tool_requirements["optionalNativeToolStatus"] != expected_status:
        errors.append(
            "$.targetLegalizationToolRequirements.optionalNativeToolStatus: "
            f"expected {expected_status!r}"
        )

    expected_evidence_prefix = f"target-legalization.v1.{target}."
    for evidence_id in tool_requirements["toolRequirementEvidenceIds"]:
        if not evidence_id.startswith(expected_evidence_prefix):
            errors.append(
                "$.targetLegalizationToolRequirements.toolRequirementEvidenceIds: "
                f"evidence ID {evidence_id!r} must match manifest target"
            )
    expected_evidence_ids = expected_tool_requirement_evidence_ids(
        target, required_tool_ids, missing_tool_ids
    )
    if tool_requirements["toolRequirementEvidenceIds"] != expected_evidence_ids:
        errors.append(
            "$.targetLegalizationToolRequirements.toolRequirementEvidenceIds: "
            f"expected tool requirement evidence IDs {expected_evidence_ids!r}"
        )


def validate_target_artifacts(errors, target, artifacts, requirements):
    for name in requirements["requiredPathArtifacts"]:
        if name not in artifacts:
            errors.append(f"$.artifacts.{name}: {target} packages require {name}")

    if (
        "nativeBinaryStatus" in artifacts
        and not requirements["requiresNativeBinaryStatus"]
    ):
        errors.append(
            f"$.artifacts.nativeBinaryStatus: "
            f"{target} packages must not declare nativeBinaryStatus"
        )
    elif "nativeBinaryStatus" in artifacts and "nativeBinary" not in artifacts:
        errors.append(
            "$.artifacts.nativeBinary: nativeBinaryStatus requires nativeBinary"
        )
    elif (
        requirements["requiresNativeBinaryStatus"]
        and "nativeBinaryStatus" not in artifacts
    ):
        errors.append(
            f"$.artifacts.nativeBinaryStatus: "
            f"{target} packages require nativeBinaryStatus"
        )


def validate_semantics(instance):
    errors = []
    requirements = validate_package_artifact_requirements(
        errors, instance["target"], instance
    )
    validate_target_legalization_tool_requirements(
        errors, instance["target"], instance, requirements
    )
    validate_source_hash(errors, instance["sourceHash"])
    validate_artifact_paths(errors, instance["artifacts"])
    validate_artifact_path_uniqueness(errors, instance["artifacts"])
    validate_debug_artifact_pair(errors, instance["artifacts"])
    validate_target_specific_artifacts(
        errors, instance["target"], instance["artifacts"]
    )
    validate_target_artifacts(
        errors, instance["target"], instance["artifacts"], requirements
    )
    return errors
