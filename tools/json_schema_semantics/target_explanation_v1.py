"""Semantic checks for target-explanation-v1.schema.json."""

from .common import expected_package_mode
from .common import validate_target_explanation_document


TARGET_LEGALIZATION_EVIDENCE_PREFIX = "target-legalization.v1"
TOOL_REQUIREMENT_KINDS = {"native-tool", "toolchain", "validation"}
OPTIONAL_NATIVE_TOOL_STATUSES = {"available", "missing", "not-required"}
SUPPORT_STATUSES = {"native", "source-package", "unsupported"}
LEGALIZATION_STATES = {"legalized", "rejected"}
PACKAGE_DECISION_PROVENANCES = {
    "native-package-available",
    "source-package-only",
    "unsupported",
    "unsupported-source-form",
    "unsupported-native-form",
    "unsupported-raw-hir",
}

TOOL_REQUIREMENT_FIELDS = {
    "requiredToolCount",
    "missingToolCount",
    "requiredToolIds",
    "missingToolIds",
    "optionalNativeToolMissing",
    "optionalNativeToolStatus",
    "toolRequirementEvidenceIds",
}

NATIVE_PACKAGE_TOOL_REQUIREMENTS = {
    "metal": (
        "metal.toolchain.xcrun-metal",
        "metal.toolchain.xcrun-metallib",
    ),
    "vulkan": (
        "vulkan.toolchain.spirv-as",
        "vulkan.validation.spirv-val",
    ),
}

SOURCE_PACKAGE_OPTIONAL_NATIVE_EVIDENCE = {
    "directx": (
        "directx.backend.native-dxil-package",
        "directx.toolchain.dxc",
        "directx.validation.dxil-validator",
    ),
    "opengl": (
        "opengl.backend.native-glsl-package",
        "opengl.toolchain.opengl-driver",
        "opengl.validation.glsl-program-validation",
    ),
}


def target_legalization_evidence_id(target, suffix):
    return f"{TARGET_LEGALIZATION_EVIDENCE_PREFIX}.{target}.{suffix}"


def tool_requirement_id_from_capability(capability):
    parts = capability.split(".", 2)
    if len(parts) != 3:
        return None
    target, kind, name = parts
    if kind == "nativeTool":
        kind = "native-tool"
    if kind not in TOOL_REQUIREMENT_KINDS:
        return None
    return f"{target}.{kind}.{name}"


def tool_requirement_suffix(tool_id, target):
    prefix = f"{target}."
    if not tool_id.startswith(prefix):
        return None
    return tool_id[len(prefix) :]


def string_list(value):
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, str)]


def expected_required_tool_ids(record):
    ids = {
        tool_id
        for tool_id in (
            tool_requirement_id_from_capability(capability)
            for capability in record["requiredCapabilities"]
        )
        if tool_id is not None
    }
    if record["packageMode"] == "native":
        ids.update(NATIVE_PACKAGE_TOOL_REQUIREMENTS.get(record["target"], ()))
    return sorted(ids)


def expected_missing_tool_ids(record):
    return sorted(
        {
            tool_id
            for tool_id in (
                tool_requirement_id_from_capability(capability)
                for capability in record["missingCapabilities"]
            )
            if tool_id is not None
        }
    )


def expected_optional_native_tool_status(record, required_ids, missing_ids):
    if record["packageMode"] != "source-package":
        return "not-required"
    if missing_ids:
        return "missing"
    if required_ids:
        return "available"
    return "not-required"


def expected_tool_requirement_evidence_ids(record, required_ids, missing_ids):
    target = record["target"]
    evidence_ids = [
        target_legalization_evidence_id(
            target,
            "tool-requirements.present"
            if required_ids or missing_ids
            else "tool-requirements.empty",
        )
    ]
    for role, tool_ids in (("required", required_ids), ("missing", missing_ids)):
        for tool_id in tool_ids:
            suffix = tool_requirement_suffix(tool_id, target)
            if suffix is None:
                continue
            evidence_ids.append(
                target_legalization_evidence_id(
                    target,
                    f"tool-requirement.{role}.{suffix}",
                )
            )
    return evidence_ids


def package_decision_provenance(record, mode):
    if mode == "native":
        return "native-package-available"
    if mode == "source-package":
        return "source-package-only"
    if record["target"] in SOURCE_PACKAGE_OPTIONAL_NATIVE_EVIDENCE:
        if not record["sourcePackageSupported"]:
            return "unsupported-source-form"
    if record["nativeImplemented"]:
        return "unsupported-native-form"
    return "unsupported"


def optional_native_tool_missing(record, mode):
    if mode != "source-package":
        return False
    optional_evidence = SOURCE_PACKAGE_OPTIONAL_NATIVE_EVIDENCE.get(record["target"])
    if optional_evidence is None:
        return False
    missing_capabilities = set(record["missingCapabilities"])
    return any(capability in missing_capabilities for capability in optional_evidence)


def unexpected_source_package_missing_capabilities(record):
    if record.get("packageMode") != "source-package" or not record.get(
        "packageBuildSupported"
    ):
        return []
    optional_evidence = SOURCE_PACKAGE_OPTIONAL_NATIVE_EVIDENCE.get(
        record.get("target")
    )
    optional_evidence_set = set(optional_evidence or ())
    missing_capabilities = record.get("missingCapabilities", [])
    if not isinstance(missing_capabilities, list):
        return []
    return [
        capability
        for capability in missing_capabilities
        if isinstance(capability, str) and capability not in optional_evidence_set
    ]


def expected_decision_reason_codes(record):
    codes = [
        f"package-mode:{record['packageMode']}",
        f"package-reason:{record['packageDecisionReason']}",
    ]
    if optional_native_tool_missing(record, record["packageMode"]):
        codes.append("optional-native-tool:missing")
    if not record["packageBuildSupported"]:
        codes.append("unsupported:missing-capabilities")
    return codes


def validate_normalized_legalization_fields(errors, path, record):
    mode = expected_package_mode(record)
    expected_support_status = mode if record["packageBuildSupported"] else "unsupported"
    expected_state = "legalized" if record["packageBuildSupported"] else "rejected"
    expected_provenance = package_decision_provenance(record, mode)

    support_status = record.get("supportStatus")
    if support_status is not None:
        if support_status not in SUPPORT_STATUSES:
            errors.append(
                f"{path}.supportStatus: expected one of "
                f"{sorted(SUPPORT_STATUSES)!r}, got {support_status!r}"
            )
        elif support_status != expected_support_status:
            errors.append(
                f"{path}.supportStatus: expected {expected_support_status!r}, "
                f"got {support_status!r}"
            )

    legalization_state = record.get("legalizationState")
    if legalization_state is not None:
        if legalization_state not in LEGALIZATION_STATES:
            errors.append(
                f"{path}.legalizationState: expected one of "
                f"{sorted(LEGALIZATION_STATES)!r}, got {legalization_state!r}"
            )
        elif legalization_state != expected_state:
            errors.append(
                f"{path}.legalizationState: expected {expected_state!r}, "
                f"got {legalization_state!r}"
            )

    provenance = record.get("packageDecisionProvenance")
    if provenance is not None:
        if provenance not in PACKAGE_DECISION_PROVENANCES:
            errors.append(
                f"{path}.packageDecisionProvenance: expected one of "
                f"{sorted(PACKAGE_DECISION_PROVENANCES)!r}, got {provenance!r}"
            )
        elif provenance != expected_provenance:
            errors.append(
                f"{path}.packageDecisionProvenance: expected "
                f"{expected_provenance!r}, got {provenance!r}"
            )


def expected_legalization_core_evidence_ids(record):
    target = record["target"]
    mode = expected_package_mode(record)
    reason = {
        "native": "native-package-available",
        "source-package": "source-package-available",
        "unsupported": "unsupported",
    }[mode]
    state = "legalized" if record["packageBuildSupported"] else "rejected"
    support_status = mode if record["packageBuildSupported"] else "unsupported"
    evidence_ids = [
        target_legalization_evidence_id(target, "decision"),
        target_legalization_evidence_id(target, f"state.{state}"),
        target_legalization_evidence_id(target, f"support.{support_status}"),
        target_legalization_evidence_id(target, f"package-mode.{mode}"),
        target_legalization_evidence_id(
            target,
            f"package-provenance.{package_decision_provenance(record, mode)}",
        ),
    ]
    if optional_native_tool_missing(record, mode):
        evidence_ids.append(
            target_legalization_evidence_id(target, "optional-native-tool.missing")
        )
    if reason:
        evidence_ids.append(
            target_legalization_evidence_id(
                target,
                f"package-reason.{reason}",
            )
        )
    return evidence_ids


def validate_consumer_context(errors, path, record):
    target = record["target"]
    expected_artifact_links = [f"ir/target-explanation.json#targets/{target}"]
    expected_report_links = [f"target-explanation-v1#targets/{target}"]

    if record["targetBackend"] != target:
        errors.append(
            f"{path}.targetBackend: expected target backend identity {target!r}, "
            f"got {record['targetBackend']!r}"
        )

    decision_reason_codes = record["decisionReasonCodes"]
    expected_reason_codes = expected_decision_reason_codes(record)
    if decision_reason_codes != expected_reason_codes:
        errors.append(
            f"{path}.decisionReasonCodes: expected decision reason codes "
            f"{expected_reason_codes!r}, got {decision_reason_codes!r}"
        )

    if record["artifactLinks"] != expected_artifact_links:
        errors.append(
            f"{path}.artifactLinks: expected artifact links "
            f"{expected_artifact_links!r}, got {record['artifactLinks']!r}"
        )
    if record["reportLinks"] != expected_report_links:
        errors.append(
            f"{path}.reportLinks: expected report links "
            f"{expected_report_links!r}, got {record['reportLinks']!r}"
        )

    remediation = record["remediation"]
    if not remediation.strip():
        errors.append(f"{path}.remediation: expected non-empty remediation text")
    if record["packageMode"] == "native":
        if "No remediation required" not in remediation:
            errors.append(
                f"{path}.remediation: native package decisions must state that "
                "no remediation is required"
            )
    elif record["packageMode"] == "source-package":
        if record["missingCapabilities"]:
            if "native artifact remediation" not in remediation:
                errors.append(
                    f"{path}.remediation: source-package fallback with missing "
                    "native capabilities must describe native artifact remediation"
                )
        elif "No remediation required" not in remediation:
            errors.append(
                f"{path}.remediation: source-package decisions without missing "
                "capabilities must state that no remediation is required"
            )
    else:
        if "Select a buildable target" not in remediation:
            errors.append(
                f"{path}.remediation: unsupported decisions must tell consumers "
                "to select a buildable target or satisfy missing capabilities"
            )
    for capability in record["missingCapabilities"]:
        if capability not in remediation:
            errors.append(
                f"{path}.remediation: expected missing capability {capability!r} "
                "to appear in remediation"
            )


def validate_legalization_core_evidence_ids(errors, path, record):
    field = "legalizationCoreEvidenceIds"
    if field not in record:
        errors.append(f"{path}: missing required semantic property {field!r}")
        return

    evidence_ids = record[field]
    if not evidence_ids:
        errors.append(f"{path}.{field}: must be a non-empty array")
        return

    seen = set()
    for index, evidence_id in enumerate(evidence_ids):
        item_path = f"{path}.{field}[{index}]"
        if evidence_id in seen:
            errors.append(
                f"{path}.{field}: duplicate legalization core evidence id "
                f"{evidence_id!r}"
            )
        seen.add(evidence_id)

        expected_prefix = f"{TARGET_LEGALIZATION_EVIDENCE_PREFIX}.{record['target']}."
        if not evidence_id.startswith(expected_prefix):
            errors.append(
                f"{item_path}: expected target legalization evidence prefix "
                f"{expected_prefix!r}, got {evidence_id!r}"
            )

    expected_evidence_ids = expected_legalization_core_evidence_ids(record)
    expected_evidence_id_set = set(expected_evidence_ids)
    for index, evidence_id in enumerate(evidence_ids):
        if evidence_id not in expected_evidence_id_set:
            errors.append(
                f"{path}.{field}[{index}]: expected known target legalization "
                f"core evidence id, got {evidence_id!r}"
            )

    if evidence_ids != expected_evidence_ids:
        errors.append(
            f"{path}.{field}: expected target legalization core evidence ids "
            f"{expected_evidence_ids!r}, got {evidence_ids!r}"
        )


def validate_diagnostic_evidence_ids(errors, path, record):
    field = "diagnosticEvidenceIds"
    if field not in record:
        return

    evidence_ids = record[field]
    if not isinstance(evidence_ids, list):
        errors.append(f"{path}.{field}: expected array")
        return

    seen = set()
    expected_prefix = (
        f"{TARGET_LEGALIZATION_EVIDENCE_PREFIX}.{record['target']}.diagnostic."
    )
    for index, evidence_id in enumerate(evidence_ids):
        item_path = f"{path}.{field}[{index}]"
        if not isinstance(evidence_id, str):
            errors.append(f"{item_path}: expected string")
            continue
        if evidence_id in seen:
            errors.append(
                f"{path}.{field}: duplicate diagnostic evidence id {evidence_id!r}"
            )
        seen.add(evidence_id)
        if not evidence_id.startswith(expected_prefix):
            errors.append(
                f"{item_path}: expected target diagnostic evidence prefix "
                f"{expected_prefix!r}, got {evidence_id!r}"
            )

    if record["packageBuildSupported"] and evidence_ids:
        errors.append(
            f"{path}.{field}: buildable target must not report diagnostic evidence"
        )
    if not record["packageBuildSupported"] and not evidence_ids:
        errors.append(
            f"{path}.{field}: unsupported target must preserve diagnostic evidence"
        )


def validate_tool_requirement_fields(errors, path, record):
    present_fields = TOOL_REQUIREMENT_FIELDS.intersection(record)
    if not present_fields:
        return

    missing_fields = sorted(TOOL_REQUIREMENT_FIELDS - present_fields)
    if missing_fields:
        errors.append(
            f"{path}: tool requirement fields must be emitted together, missing "
            f"{missing_fields!r}"
        )
        return

    target = record["target"]
    required_ids = string_list(record["requiredToolIds"])
    missing_ids = string_list(record["missingToolIds"])
    tool_evidence_ids = string_list(record["toolRequirementEvidenceIds"])

    if record["requiredToolCount"] != len(required_ids):
        errors.append(
            f"{path}.requiredToolCount: expected requiredToolIds length "
            f"{len(required_ids)}, got {record['requiredToolCount']!r}"
        )
    if record["missingToolCount"] != len(missing_ids):
        errors.append(
            f"{path}.missingToolCount: expected missingToolIds length "
            f"{len(missing_ids)}, got {record['missingToolCount']!r}"
        )

    expected_required_ids = expected_required_tool_ids(record)
    expected_missing_ids = expected_missing_tool_ids(record)
    if sorted(required_ids) != expected_required_ids:
        errors.append(
            f"{path}.requiredToolIds: expected projected required tool IDs "
            f"{expected_required_ids!r}, got {sorted(required_ids)!r}"
        )
    if sorted(missing_ids) != expected_missing_ids:
        errors.append(
            f"{path}.missingToolIds: expected projected missing tool IDs "
            f"{expected_missing_ids!r}, got {sorted(missing_ids)!r}"
        )

    outside_required = sorted(set(missing_ids) - set(required_ids))
    if outside_required:
        errors.append(
            f"{path}.missingToolIds: tool ID(s) are not required: {outside_required!r}"
        )

    for field, values in (
        ("requiredToolIds", required_ids),
        ("missingToolIds", missing_ids),
    ):
        for index, tool_id in enumerate(values):
            suffix = tool_requirement_suffix(tool_id, target)
            if suffix is None:
                errors.append(
                    f"{path}.{field}[{index}]: expected target tool prefix "
                    f"{target!r}, got {tool_id!r}"
                )
                continue
            kind = suffix.split(".", 1)[0]
            if kind not in TOOL_REQUIREMENT_KINDS:
                errors.append(
                    f"{path}.{field}[{index}]: expected tool kind in "
                    f"{sorted(TOOL_REQUIREMENT_KINDS)!r}, got {tool_id!r}"
                )

    expected_optional_missing = record["packageMode"] == "source-package" and bool(
        missing_ids
    )
    if record["optionalNativeToolMissing"] != expected_optional_missing:
        errors.append(
            f"{path}.optionalNativeToolMissing: expected "
            f"{expected_optional_missing!r} for packageMode "
            f"{record['packageMode']!r} and {len(missing_ids)} missing tool "
            f"ID(s), got {record['optionalNativeToolMissing']!r}"
        )

    expected_status = expected_optional_native_tool_status(
        record,
        required_ids,
        missing_ids,
    )
    if record["optionalNativeToolStatus"] not in OPTIONAL_NATIVE_TOOL_STATUSES:
        errors.append(
            f"{path}.optionalNativeToolStatus: unsupported optional native tool "
            f"status {record['optionalNativeToolStatus']!r}"
        )
    elif record["optionalNativeToolStatus"] != expected_status:
        errors.append(
            f"{path}.optionalNativeToolStatus: expected {expected_status!r}, "
            f"got {record['optionalNativeToolStatus']!r}"
        )

    expected_evidence_ids = expected_tool_requirement_evidence_ids(
        record,
        required_ids,
        missing_ids,
    )
    if tool_evidence_ids != expected_evidence_ids:
        errors.append(
            f"{path}.toolRequirementEvidenceIds: expected "
            f"{expected_evidence_ids!r}, got {tool_evidence_ids!r}"
        )

    expected_prefix = f"{TARGET_LEGALIZATION_EVIDENCE_PREFIX}.{target}."
    for index, evidence_id in enumerate(tool_evidence_ids):
        if not evidence_id.startswith(expected_prefix):
            errors.append(
                f"{path}.toolRequirementEvidenceIds[{index}]: expected target "
                f"legalization evidence prefix {expected_prefix!r}, got "
                f"{evidence_id!r}"
            )


def validate_target_explanation_legalization_core_evidence(errors, path, document):
    for index, record in enumerate(document["targets"]):
        validate_normalized_legalization_fields(
            errors,
            f"{path}.targets[{index}]",
            record,
        )
        validate_legalization_core_evidence_ids(
            errors,
            f"{path}.targets[{index}]",
            record,
        )
        validate_diagnostic_evidence_ids(
            errors,
            f"{path}.targets[{index}]",
            record,
        )
        validate_tool_requirement_fields(
            errors,
            f"{path}.targets[{index}]",
            record,
        )


def validate_target_explanation_consumer_context(errors, path, document):
    for index, record in enumerate(document["targets"]):
        validate_consumer_context(
            errors,
            f"{path}.targets[{index}]",
            record,
        )


def validate_source_package_optional_native_evidence(
    errors,
    path,
    target_explanation,
):
    for index, record in enumerate(target_explanation["targets"]):
        if record["packageMode"] != "source-package":
            continue
        target = record["target"]
        evidence_capabilities = SOURCE_PACKAGE_OPTIONAL_NATIVE_EVIDENCE.get(target)
        if evidence_capabilities is None:
            continue

        record_path = f"{path}.targets[{index}]"
        required_capabilities = set(record["requiredCapabilities"])
        missing_capabilities = set(record["missingCapabilities"])
        for capability in evidence_capabilities:
            if capability not in required_capabilities:
                errors.append(
                    f"{record_path}.requiredCapabilities: source-package "
                    "fallback requires optional native evidence "
                    f"{capability!r}"
                )
            if capability not in missing_capabilities:
                errors.append(
                    f"{record_path}.missingCapabilities: source-package "
                    "fallback requires missing optional native evidence "
                    f"{capability!r}"
                )
        unexpected_capabilities = unexpected_source_package_missing_capabilities(record)
        if unexpected_capabilities:
            errors.append(
                f"{record_path}.missingCapabilities: buildable source-package "
                "target may only report optional native evidence missing "
                f"capabilities, got {unexpected_capabilities!r}"
            )


def validate_source_package_support_consistency(errors, path, target_explanation):
    for index, record in enumerate(target_explanation["targets"]):
        if record["sourcePackageSupported"] and not record["packageBuildSupported"]:
            errors.append(
                f"{path}.targets[{index}].packageBuildSupported: "
                "sourcePackageSupported true requires packageBuildSupported true"
            )


def validate_semantics(instance):
    errors = []
    validate_target_explanation_document(errors, "$", instance)
    validate_target_explanation_legalization_core_evidence(errors, "$", instance)
    validate_target_explanation_consumer_context(errors, "$", instance)
    validate_source_package_support_consistency(errors, "$", instance)
    validate_source_package_optional_native_evidence(errors, "$", instance)
    return errors
