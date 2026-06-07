"""Semantic checks for target-legalization-result-v0 schema instances."""

from __future__ import annotations

EVIDENCE_PREFIX = "target-legalization.v1"
TARGETS = {"directx", "metal", "opengl", "vulkan"}
PACKAGE_MODES = {"native", "source-package", "unsupported"}
SOURCE_PACKAGE_TARGETS = {"directx", "opengl"}
PACKAGE_DECISION_PROVENANCES = {
    "native-package-available",
    "source-package-only",
    "unsupported",
    "unsupported-native-form",
    "unsupported-raw-hir",
    "unsupported-source-form",
}
DIAGNOSTIC_SEVERITIES = {"error", "info", "warning"}
TOOL_REQUIREMENT_KINDS = {"native-tool", "toolchain", "validation"}
TOOL_REQUIREMENT_STATUSES = {"missing", "required"}
OPTIONAL_NATIVE_TOOL_STATUSES = {"available", "missing", "not-required"}
SUCCESS_PROVENANCE_BY_PACKAGE_MODE = {
    "native": "native-package-available",
    "source-package": "source-package-only",
}


def evidence_id(target: str, suffix: str) -> str:
    return f"{EVIDENCE_PREFIX}.{target}.{suffix}"


def evidence_suffix(evidence_id_value: str, target: str) -> str | None:
    prefix = f"{EVIDENCE_PREFIX}.{target}."
    if not evidence_id_value.startswith(prefix):
        return None
    return evidence_id_value[len(prefix) :]


def expected_core_evidence_suffixes(
    module_supported: bool | None, package_mode: str | None
) -> tuple[str, str, str] | tuple[()]:
    if module_supported is True and package_mode == "native":
        return ("state.legalized", "support.native", "package-mode.native")
    if module_supported is True and package_mode == "source-package":
        return (
            "state.legalized",
            "support.source-package",
            "package-mode.source-package",
        )
    if module_supported is False and package_mode == "unsupported":
        return ("state.rejected", "support.unsupported", "package-mode.unsupported")
    return ()


def string_values(value) -> list[str]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, str)]


def validate_evidence_ids(
    errors,
    path: str,
    value,
    *,
    target: str,
    top_level_evidence: set[str] | None = None,
) -> list[str]:
    evidence_ids = string_values(value)
    expected_prefix = f"{EVIDENCE_PREFIX}.{target}."
    for item in evidence_ids:
        if not item.startswith(expected_prefix):
            errors.append(
                f"{path}: evidence ID {item!r} must use target prefix "
                f"{expected_prefix!r}"
            )
        if top_level_evidence is not None and item not in top_level_evidence:
            errors.append(
                f"{path}: evidence ID {item!r} is not listed in $.result.evidenceIds"
            )
    return evidence_ids


def validate_capability_ids(errors, path: str, value, *, target: str) -> list[str]:
    capability_ids = string_values(value)
    target_prefix = f"{target}."
    for capability_id in capability_ids:
        if not capability_id.startswith(target_prefix):
            errors.append(
                f"{path}: capability ID {capability_id!r} must use target "
                f"prefix {target!r}"
            )
    return capability_ids


def tool_requirement_suffix(tool_id: str, target: str) -> str | None:
    prefix = f"{target}."
    if not tool_id.startswith(prefix):
        return None
    return tool_id[len(prefix) :]


def validate_tool_ids(errors, path: str, value, *, target: str) -> list[str]:
    tool_ids = validate_capability_ids(errors, path, value, target=target)
    for tool_id in tool_ids:
        suffix = tool_requirement_suffix(tool_id, target)
        if suffix is None:
            continue
        kind = suffix.split(".", 1)[0]
        if kind not in TOOL_REQUIREMENT_KINDS:
            errors.append(
                f"{path}: tool ID {tool_id!r} must use one of "
                f"{sorted(TOOL_REQUIREMENT_KINDS)!r}"
            )
    return tool_ids


def validate_target_profile(errors, result, *, target: str, package_mode: str) -> None:
    profile = result.get("targetProfile")
    if not isinstance(profile, dict):
        return
    if profile.get("target") != target:
        errors.append(
            "$.result.targetProfile.target: expected "
            f"{target!r}, got {profile.get('target')!r}"
        )
    expected_profile = f"{target}.v0.{package_mode}"
    if profile.get("profile") != expected_profile:
        errors.append(
            "$.result.targetProfile.profile: expected "
            f"{expected_profile!r}, got {profile.get('profile')!r}"
        )
    if profile.get("packageMode") != package_mode:
        errors.append(
            "$.result.targetProfile.packageMode: expected "
            f"{package_mode!r}, got {profile.get('packageMode')!r}"
        )


def validate_core_evidence(
    errors,
    result,
    *,
    target: str,
    package_mode: str | None,
    package_decision_provenance: str | None,
    module_supported: bool | None,
    top_level_evidence: set[str],
) -> None:
    expected_decision_evidence = evidence_id(target, "decision")
    if expected_decision_evidence not in top_level_evidence:
        errors.append(
            "$.result.evidenceIds: missing target decision evidence ID "
            f"{expected_decision_evidence!r}"
        )

    expected_core_suffixes = expected_core_evidence_suffixes(
        module_supported, package_mode
    )
    expected_core = {
        suffix.split(".", 1)[0]: suffix for suffix in expected_core_suffixes
    }
    for suffix in expected_core_suffixes:
        expected = evidence_id(target, suffix)
        if expected not in top_level_evidence:
            errors.append(
                f"$.result.evidenceIds: missing core support evidence ID {expected!r}"
            )

    core_prefixes = {
        "state": "state.",
        "support": "support.",
        "package-mode": "package-mode.",
    }
    for item in sorted(top_level_evidence):
        suffix = evidence_suffix(item, target)
        if suffix is None:
            continue
        for category, prefix in core_prefixes.items():
            expected_suffix = expected_core.get(category)
            if (
                expected_suffix is not None
                and suffix.startswith(prefix)
                and suffix != expected_suffix
            ):
                errors.append(
                    "$.result.evidenceIds: core support evidence ID "
                    f"{item!r} conflicts with expected evidence ID "
                    f"{evidence_id(target, expected_suffix)!r}"
                )

    if package_decision_provenance not in PACKAGE_DECISION_PROVENANCES:
        return

    expected_provenance = evidence_id(
        target, f"package-provenance.{package_decision_provenance}"
    )
    if expected_provenance not in top_level_evidence:
        errors.append(
            "$.result.evidenceIds: missing package decision provenance "
            f"evidence ID {expected_provenance!r}"
        )
    provenance_prefix = f"{EVIDENCE_PREFIX}.{target}.package-provenance."
    for item in sorted(top_level_evidence):
        if item.startswith(provenance_prefix) and item != expected_provenance:
            errors.append(
                "$.result.evidenceIds: package decision provenance evidence ID "
                f"{item!r} conflicts with packageDecisionProvenance "
                f"{package_decision_provenance!r}"
            )


def validate_support_and_package_state(
    errors,
    result,
    *,
    target: str,
    package_mode: str | None,
    package_decision_provenance: str | None,
    module_supported: bool | None,
    missing_capabilities: set[str],
) -> None:
    if module_supported is not None and package_mode is not None:
        if module_supported and package_mode == "unsupported":
            errors.append(
                "$.result.packageMode: supported modules cannot use 'unsupported'"
            )
        if not module_supported and package_mode != "unsupported":
            errors.append(
                "$.result.packageMode: unsupported modules must use 'unsupported'"
            )
        if module_supported and missing_capabilities:
            errors.append(
                "$.result.missingCapabilities: supported modules must not miss "
                "capabilities"
            )
        if not module_supported and not missing_capabilities:
            errors.append(
                "$.result.missingCapabilities: unsupported modules must name at "
                "least one missing capability"
            )

    if package_mode is None or package_decision_provenance is None:
        return

    expected_provenance = SUCCESS_PROVENANCE_BY_PACKAGE_MODE.get(package_mode)
    if (
        expected_provenance is not None
        and package_decision_provenance != expected_provenance
    ):
        errors.append(
            "$.result.packageDecisionProvenance: expected "
            f"{expected_provenance!r} for packageMode {package_mode!r}, got "
            f"{package_decision_provenance!r}"
        )
    if package_mode == "unsupported" and package_decision_provenance in {
        "native-package-available",
        "source-package-only",
    }:
        errors.append(
            "$.result.packageDecisionProvenance: unsupported packageMode cannot "
            f"use available package provenance {package_decision_provenance!r}"
        )
    if package_mode == "source-package" and target not in SOURCE_PACKAGE_TARGETS:
        errors.append(
            "$.result.packageMode: source-package is only valid for "
            f"{sorted(SOURCE_PACKAGE_TARGETS)!r}, got {target!r}"
        )


def validate_diagnostics(
    errors,
    result,
    *,
    target: str,
    module_supported: bool | None,
    missing_capabilities: set[str],
    top_level_evidence: set[str],
) -> None:
    diagnostics = result.get("diagnostics")
    if not isinstance(diagnostics, list):
        return

    has_error = False
    diagnostic_missing_capabilities: set[str] = set()
    for index, diagnostic in enumerate(diagnostics):
        path = f"$.result.diagnostics[{index}]"
        if not isinstance(diagnostic, dict):
            continue
        severity = diagnostic.get("severity")
        if severity == "error":
            has_error = True
        elif severity not in DIAGNOSTIC_SEVERITIES:
            errors.append(
                f"{path}.severity: unsupported diagnostic severity {severity!r}"
            )

        if diagnostic.get("target") != target:
            errors.append(
                f"{path}.target: expected {target!r}, got {diagnostic.get('target')!r}"
            )

        diagnostic_missing = validate_capability_ids(
            errors,
            f"{path}.missingCapabilities",
            diagnostic.get("missingCapabilities"),
            target=target,
        )
        for capability in diagnostic_missing:
            diagnostic_missing_capabilities.add(capability)
            if capability not in missing_capabilities:
                errors.append(
                    f"{path}.missingCapabilities: capability {capability!r} is "
                    "not listed in $.result.missingCapabilities"
                )

        evidence_ids = validate_evidence_ids(
            errors,
            f"{path}.evidenceIds",
            diagnostic.get("evidenceIds"),
            target=target,
            top_level_evidence=top_level_evidence,
        )
        if not any(
            suffix is not None and suffix.startswith("diagnostic.")
            for suffix in (evidence_suffix(item, target) for item in evidence_ids)
        ):
            errors.append(
                f"{path}.evidenceIds: expected at least one diagnostic evidence ID"
            )

    if module_supported is True and has_error:
        errors.append("$.result.diagnostics: supported modules must not have errors")
    if module_supported is False and not has_error:
        errors.append(
            "$.result.diagnostics: unsupported modules require an error diagnostic"
        )
    uncovered_missing = sorted(missing_capabilities - diagnostic_missing_capabilities)
    if module_supported is False and uncovered_missing:
        errors.append(
            "$.result.diagnostics: missing capability ID(s) lack diagnostic "
            f"coverage: {', '.join(uncovered_missing)}"
        )


def validate_tool_records(
    errors,
    result,
    *,
    required_ids: set[str],
    missing_ids: set[str],
    parent_evidence: set[str],
    top_level_evidence: set[str],
) -> None:
    target = result.get("target")
    tool_requirements = result.get("toolRequirements")
    if not isinstance(target, str) or not isinstance(tool_requirements, dict):
        return

    records = tool_requirements.get("records")
    if not isinstance(records, list):
        return

    required_record_ids = set()
    missing_record_ids = set()
    seen = set()
    for index, record in enumerate(records):
        path = f"$.result.toolRequirements.records[{index}]"
        if not isinstance(record, dict):
            continue
        record_id = record.get("id")
        kind = record.get("kind")
        name = record.get("name")
        status = record.get("status")
        if (
            not isinstance(record_id, str)
            or not isinstance(kind, str)
            or not isinstance(name, str)
            or not isinstance(status, str)
        ):
            continue

        expected_id = f"{target}.{kind}.{name}"
        if record_id != expected_id:
            errors.append(f"{path}.id: expected {expected_id!r}, got {record_id!r}")
        if kind not in TOOL_REQUIREMENT_KINDS:
            errors.append(f"{path}.kind: unsupported tool requirement kind {kind!r}")
            kind_supported = False
        else:
            kind_supported = True
        if status not in TOOL_REQUIREMENT_STATUSES:
            errors.append(
                f"{path}.status: unsupported tool requirement status {status!r}"
            )
            status_supported = False
        else:
            status_supported = True
        if record.get("target") != target:
            errors.append(
                f"{path}.target: expected {target!r}, got {record.get('target')!r}"
            )

        record_evidence = set(
            validate_evidence_ids(
                errors,
                f"{path}.evidenceIds",
                record.get("evidenceIds"),
                target=target,
                top_level_evidence=top_level_evidence,
            )
        )
        if kind_supported and status_supported:
            expected_evidence = evidence_id(
                target, f"tool-requirement.{status}.{kind}.{name}"
            )
        else:
            expected_evidence = None
        if expected_evidence is not None and expected_evidence not in record_evidence:
            errors.append(
                f"{path}.evidenceIds: missing expected evidence ID "
                f"{expected_evidence!r}"
            )
        for item in record_evidence:
            if item not in parent_evidence:
                errors.append(
                    f"{path}.evidenceIds: evidence ID {item!r} is not listed "
                    "in $.result.toolRequirements.evidenceIds"
                )
            if item not in top_level_evidence:
                errors.append(
                    f"{path}.evidenceIds: evidence ID {item!r} is not listed "
                    "in $.result.evidenceIds"
                )

        if not status_supported:
            continue
        key = (status, record_id)
        if key in seen:
            errors.append(f"{path}: duplicate {status} tool record {record_id!r}")
        seen.add(key)
        if status == "required":
            required_record_ids.add(record_id)
        elif status == "missing":
            missing_record_ids.add(record_id)

    if required_record_ids != required_ids:
        errors.append(
            "$.result.toolRequirements.records: required records disagree with "
            "$.result.toolRequirements.requiredToolIds"
        )
    if missing_record_ids != missing_ids:
        errors.append(
            "$.result.toolRequirements.records: missing records disagree with "
            "$.result.toolRequirements.missingToolIds"
        )


def expected_optional_native_tool_status(
    *, package_mode: str | None, required_ids: set[str], missing_ids: set[str]
) -> str:
    if package_mode != "source-package":
        return "not-required"
    if missing_ids:
        return "missing"
    if required_ids:
        return "available"
    return "not-required"


def validate_tool_requirements(
    errors,
    result,
    *,
    target: str,
    package_mode: str | None,
    top_level_evidence: set[str],
) -> None:
    tool_requirements = result.get("toolRequirements")
    if not isinstance(tool_requirements, dict):
        return

    required_ids = set(
        validate_tool_ids(
            errors,
            "$.result.toolRequirements.requiredToolIds",
            tool_requirements.get("requiredToolIds"),
            target=target,
        )
    )
    missing_ids = set(
        validate_tool_ids(
            errors,
            "$.result.toolRequirements.missingToolIds",
            tool_requirements.get("missingToolIds"),
            target=target,
        )
    )
    outside_required = sorted(missing_ids - required_ids)
    if outside_required:
        errors.append(
            "$.result.toolRequirements.missingToolIds: tool ID(s) are not "
            f"required: {', '.join(outside_required)}"
        )

    parent_evidence = set(
        validate_evidence_ids(
            errors,
            "$.result.toolRequirements.evidenceIds",
            tool_requirements.get("evidenceIds"),
            target=target,
            top_level_evidence=top_level_evidence,
        )
    )
    expected_summary = evidence_id(
        target,
        "tool-requirements.present"
        if required_ids or missing_ids
        else "tool-requirements.empty",
    )
    summary_evidence = {
        evidence_id(target, "tool-requirements.empty"),
        evidence_id(target, "tool-requirements.present"),
    }
    if expected_summary not in parent_evidence:
        errors.append(
            "$.result.toolRequirements.evidenceIds: missing tool requirement "
            f"summary evidence ID {expected_summary!r}"
        )
    for unexpected_summary in sorted(summary_evidence - {expected_summary}):
        if unexpected_summary in parent_evidence:
            errors.append(
                "$.result.toolRequirements.evidenceIds: tool requirement "
                f"summary evidence ID {unexpected_summary!r} conflicts with "
                f"expected summary evidence ID {expected_summary!r}"
            )

    for role, tool_ids in (("required", required_ids), ("missing", missing_ids)):
        for tool_id in sorted(tool_ids):
            suffix = tool_requirement_suffix(tool_id, target)
            if suffix is None:
                continue
            expected_evidence = evidence_id(target, f"tool-requirement.{role}.{suffix}")
            if expected_evidence not in parent_evidence:
                errors.append(
                    "$.result.toolRequirements.evidenceIds: missing "
                    f"{role} tool requirement evidence ID {expected_evidence!r}"
                )

    optional_native_tool_missing = tool_requirements.get("optionalNativeToolMissing")
    expected_optional = package_mode == "source-package" and bool(missing_ids)
    if (
        isinstance(optional_native_tool_missing, bool)
        and optional_native_tool_missing != expected_optional
    ):
        errors.append(
            "$.result.toolRequirements.optionalNativeToolMissing: expected "
            f"{expected_optional!r} for packageMode {package_mode!r} and "
            f"{len(missing_ids)} missing tool ID(s), got "
            f"{optional_native_tool_missing!r}"
        )
    optional_native_tool_status = tool_requirements.get("optionalNativeToolStatus")
    expected_optional_status = expected_optional_native_tool_status(
        package_mode=package_mode,
        required_ids=required_ids,
        missing_ids=missing_ids,
    )
    if optional_native_tool_status not in OPTIONAL_NATIVE_TOOL_STATUSES:
        errors.append(
            "$.result.toolRequirements.optionalNativeToolStatus: unsupported "
            f"optional native tool status {optional_native_tool_status!r}"
        )
    elif optional_native_tool_status != expected_optional_status:
        errors.append(
            "$.result.toolRequirements.optionalNativeToolStatus: expected "
            f"{expected_optional_status!r} for packageMode {package_mode!r}, "
            f"{len(required_ids)} required tool ID(s), and "
            f"{len(missing_ids)} missing tool ID(s), got "
            f"{optional_native_tool_status!r}"
        )
    optional_evidence = evidence_id(target, "optional-native-tool.missing")
    if expected_optional:
        if optional_evidence not in parent_evidence:
            errors.append(
                "$.result.toolRequirements.evidenceIds: missing optional native "
                f"tool evidence ID {optional_evidence!r}"
            )
        if optional_evidence not in top_level_evidence:
            errors.append(
                "$.result.toolRequirements.evidenceIds: optional native tool "
                f"evidence ID {optional_evidence!r} is not listed in "
                "$.result.evidenceIds"
            )
    elif optional_evidence in parent_evidence:
        errors.append(
            "$.result.toolRequirements.evidenceIds: optional native tool "
            f"evidence ID {optional_evidence!r} requires "
            "optionalNativeToolMissing true"
        )

    validate_tool_records(
        errors,
        result,
        required_ids=required_ids,
        missing_ids=missing_ids,
        parent_evidence=parent_evidence,
        top_level_evidence=top_level_evidence,
    )


def validate_abi_facts(
    errors,
    result,
    *,
    target: str,
    top_level_evidence: set[str],
) -> None:
    abi_facts = result.get("abiFacts")
    if not isinstance(abi_facts, dict):
        return

    parent_evidence = set(
        validate_evidence_ids(
            errors,
            "$.result.abiFacts.evidenceIds",
            abi_facts.get("evidenceIds"),
            target=target,
            top_level_evidence=top_level_evidence,
        )
    )
    has_abi_evidence = False
    for item in sorted(parent_evidence):
        suffix = evidence_suffix(item, target)
        if suffix is not None and suffix.startswith("abi."):
            has_abi_evidence = True
        elif suffix is not None:
            errors.append(
                "$.result.abiFacts.evidenceIds: evidence ID "
                f"{item!r} is not ABI evidence"
            )
    if not has_abi_evidence:
        errors.append(
            "$.result.abiFacts.evidenceIds: expected at least one ABI evidence ID"
        )

    facts = abi_facts.get("facts")
    if not isinstance(facts, list):
        return
    for index, fact in enumerate(facts):
        if not isinstance(fact, dict):
            continue
        fact_evidence = validate_evidence_ids(
            errors,
            f"$.result.abiFacts.facts[{index}].evidenceIds",
            fact.get("evidenceIds"),
            target=target,
            top_level_evidence=top_level_evidence,
        )
        for item in fact_evidence:
            if item not in parent_evidence:
                errors.append(
                    f"$.result.abiFacts.facts[{index}].evidenceIds: evidence ID "
                    f"{item!r} is not listed in $.result.abiFacts.evidenceIds"
                )
            suffix = evidence_suffix(item, target)
            if suffix is not None and not suffix.startswith("abi."):
                errors.append(
                    f"$.result.abiFacts.facts[{index}].evidenceIds: evidence ID "
                    f"{item!r} is not ABI evidence"
                )


def validate_result(errors, result) -> None:
    target = result.get("target")
    if not isinstance(target, str):
        return
    if target not in TARGETS:
        errors.append(f"$.result.target: unsupported target {target!r}")
        return

    package_mode = result.get("packageMode")
    package_mode_value = package_mode if package_mode in PACKAGE_MODES else None
    package_decision_provenance = result.get("packageDecisionProvenance")
    provenance_value = (
        package_decision_provenance
        if package_decision_provenance in PACKAGE_DECISION_PROVENANCES
        else None
    )
    module_supported = result.get("moduleSupported")
    module_supported_value = (
        module_supported if isinstance(module_supported, bool) else None
    )

    top_level_evidence = set(
        validate_evidence_ids(
            errors,
            "$.result.evidenceIds",
            result.get("evidenceIds"),
            target=target,
        )
    )
    validate_core_evidence(
        errors,
        result,
        target=target,
        package_mode=package_mode_value,
        package_decision_provenance=provenance_value,
        module_supported=module_supported_value,
        top_level_evidence=top_level_evidence,
    )

    if package_mode_value is not None:
        validate_target_profile(
            errors,
            result,
            target=target,
            package_mode=package_mode_value,
        )

    required_capabilities = set(
        validate_capability_ids(
            errors,
            "$.result.requiredCapabilities",
            result.get("requiredCapabilities"),
            target=target,
        )
    )
    missing_capabilities = set(
        validate_capability_ids(
            errors,
            "$.result.missingCapabilities",
            result.get("missingCapabilities"),
            target=target,
        )
    )
    outside_required = sorted(missing_capabilities - required_capabilities)
    if outside_required:
        errors.append(
            "$.result.missingCapabilities: capability ID(s) are not required: "
            f"{', '.join(outside_required)}"
        )

    validate_support_and_package_state(
        errors,
        result,
        target=target,
        package_mode=package_mode_value,
        package_decision_provenance=provenance_value,
        module_supported=module_supported_value,
        missing_capabilities=missing_capabilities,
    )
    validate_tool_requirements(
        errors,
        result,
        target=target,
        package_mode=package_mode_value,
        top_level_evidence=top_level_evidence,
    )
    validate_diagnostics(
        errors,
        result,
        target=target,
        module_supported=module_supported_value,
        missing_capabilities=missing_capabilities,
        top_level_evidence=top_level_evidence,
    )
    validate_abi_facts(
        errors,
        result,
        target=target,
        top_level_evidence=top_level_evidence,
    )


def validate_semantics(instance):
    errors = []
    if not isinstance(instance, dict):
        return errors
    result = instance.get("result")
    if isinstance(result, dict):
        validate_result(errors, result)
    return errors
