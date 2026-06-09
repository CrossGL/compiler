"""Semantic checks for debug-metadata-v11.schema.json."""

from .debug_metadata_v10 import validate_debug_target_capabilities
from .debug_metadata_v10 import validate_debug_target_decision
from .debug_metadata_v10 import validate_debug_target_projection
from .debug_metadata_v10 import validate_debug_source_location_ranges
from .debug_metadata_v10 import validate_manual_kernel_semantics
from .common import add_equal_error
from .common import validate_source_locations
from .target_explanation_v1 import expected_legalization_core_evidence_ids
from .target_explanation_v1 import expected_package_artifact_requirement_evidence_ids
from .target_explanation_v1 import validate_legalization_core_evidence_ids
from .target_explanation_v1 import (
    validate_package_artifact_requirement_evidence_ids,
)
from .target_explanation_v1 import validate_tool_requirement_fields

DEBUG_TARGET_SUMMARY_TARGETS = ("metal", "vulkan", "directx", "opengl")
DEBUG_TARGET_SUMMARY_ORDER = {
    target: index for index, target in enumerate(DEBUG_TARGET_SUMMARY_TARGETS)
}
DEBUG_TARGET_TOOL_REQUIREMENT_FIELDS = (
    "requiredToolCount",
    "missingToolCount",
    "requiredToolIds",
    "missingToolIds",
    "optionalNativeToolMissing",
    "optionalNativeToolStatus",
    "toolRequirementEvidenceIds",
)
DEBUG_TARGET_SELECTED_TOOL_FIELD_PAIRS = (
    ("selectedTargetRequiredToolCount", "requiredToolCount"),
    ("selectedTargetMissingToolCount", "missingToolCount"),
    ("selectedTargetRequiredToolIds", "requiredToolIds"),
    ("selectedTargetMissingToolIds", "missingToolIds"),
    ("selectedTargetOptionalNativeToolMissing", "optionalNativeToolMissing"),
    ("selectedTargetOptionalNativeToolStatus", "optionalNativeToolStatus"),
    ("selectedTargetToolRequirementEvidenceIds", "toolRequirementEvidenceIds"),
)
DEBUG_TARGET_FALLBACK_TOOL_FIELD_PAIRS = (
    ("requiredToolCount", "requiredToolCount"),
    ("missingToolCount", "missingToolCount"),
    ("requiredToolIds", "requiredToolIds"),
    ("missingToolIds", "missingToolIds"),
    ("optionalNativeToolMissing", "optionalNativeToolMissing"),
    ("optionalNativeToolStatus", "optionalNativeToolStatus"),
    ("toolRequirementEvidenceIds", "toolRequirementEvidenceIds"),
)
PACKAGE_ARTIFACT_REQUIREMENT_EVIDENCE_FIELD = "packageArtifactRequirementEvidenceIds"


def validate_manual_kernel_compatibility_alias(errors, instance):
    for index, kernel in enumerate(instance["manualTextureCompareKernels"]):
        add_equal_error(
            errors,
            f"$.manualTextureCompareKernels[{index}].compatibilityAlias",
            kernel["compatibilityAlias"],
            kernel["operation"] != kernel["canonicalOperation"],
            "operation/canonicalOperation alias flag",
        )


def validate_debug_target_capability_summary_order(errors, target_capabilities):
    summaries = target_capabilities["summaries"]
    targets = [summary["target"] for summary in summaries]
    if len(targets) != len(set(targets)):
        return

    expected_targets = list(DEBUG_TARGET_SUMMARY_TARGETS)
    if targets != expected_targets:
        errors.append(
            "$.targetCapabilities.summaries: target summaries must cover "
            f"canonical target set {expected_targets!r}; got {targets!r}"
        )

    target_order = [DEBUG_TARGET_SUMMARY_ORDER[target] for target in targets]
    if target_order != sorted(target_order):
        errors.append(
            "$.targetCapabilities.summaries: target summaries must be in target order"
        )


def validate_debug_target_legalization_evidence(errors, decision, target_capabilities):
    summaries = target_capabilities["summaries"]
    for index, summary in enumerate(summaries):
        validate_legalization_core_evidence_ids(
            errors,
            f"$.targetCapabilities.summaries[{index}]",
            summary,
        )

    summary_targets = [summary["target"] for summary in summaries]
    if len(summary_targets) != len(set(summary_targets)):
        return

    summaries_by_target = {summary["target"]: summary for summary in summaries}
    selected_summary = summaries_by_target.get(decision["selectedTarget"])
    if selected_summary is not None:
        add_equal_error(
            errors,
            "$.targetDecision.selectedTargetLegalizationCoreEvidenceIds",
            decision["selectedTargetLegalizationCoreEvidenceIds"],
            selected_summary["legalizationCoreEvidenceIds"],
            "selected target summary legalizationCoreEvidenceIds",
        )

    for index, diagnostic in enumerate(decision["diagnostics"]):
        diagnostic_path = f"$.targetDecision.diagnostics[{index}]"
        diagnostic_summary = summaries_by_target.get(diagnostic["target"])
        if diagnostic_summary is None:
            continue
        expected_ids = expected_legalization_core_evidence_ids(diagnostic_summary)
        add_equal_error(
            errors,
            f"{diagnostic_path}.legalizationCoreEvidenceIds",
            diagnostic["legalizationCoreEvidenceIds"],
            expected_ids,
            "diagnostic target legalizationCoreEvidenceIds",
        )

    for index, record in enumerate(decision["fallbackTargetRecords"]):
        record_summary = summaries_by_target.get(record["target"])
        if record_summary is None:
            continue
        add_equal_error(
            errors,
            f"$.targetDecision.fallbackTargetRecords[{index}].legalizationCoreEvidenceIds",
            record["legalizationCoreEvidenceIds"],
            record_summary["legalizationCoreEvidenceIds"],
            "fallback target summary legalizationCoreEvidenceIds",
        )


def tool_fields_present(record, fields):
    return any(field in record for field in fields)


def validate_debug_target_tool_requirements(errors, decision, target_capabilities):
    summaries = target_capabilities["summaries"]
    for index, summary in enumerate(summaries):
        validate_tool_requirement_fields(
            errors,
            f"$.targetCapabilities.summaries[{index}]",
            summary,
        )

    summary_targets = [summary["target"] for summary in summaries]
    if len(summary_targets) != len(set(summary_targets)):
        return

    summaries_by_target = {summary["target"]: summary for summary in summaries}
    selected_summary = summaries_by_target.get(decision["selectedTarget"])
    if selected_summary is not None:
        for decision_field, summary_field in DEBUG_TARGET_SELECTED_TOOL_FIELD_PAIRS:
            if decision_field not in decision and summary_field not in selected_summary:
                continue
            add_equal_error(
                errors,
                f"$.targetDecision.{decision_field}",
                decision.get(decision_field),
                selected_summary.get(summary_field),
                f"selected target summary {summary_field}",
            )

    for index, record in enumerate(decision["fallbackTargetRecords"]):
        record_summary = summaries_by_target.get(record["target"])
        if record_summary is None:
            continue
        if not tool_fields_present(record, DEBUG_TARGET_TOOL_REQUIREMENT_FIELDS) and (
            not tool_fields_present(
                record_summary, DEBUG_TARGET_TOOL_REQUIREMENT_FIELDS
            )
        ):
            continue
        for record_field, summary_field in DEBUG_TARGET_FALLBACK_TOOL_FIELD_PAIRS:
            add_equal_error(
                errors,
                f"$.targetDecision.fallbackTargetRecords[{index}].{record_field}",
                record.get(record_field),
                record_summary.get(summary_field),
                f"fallback target summary {summary_field}",
            )


def validate_debug_target_package_artifact_requirement_evidence(
    errors, decision, target_capabilities
):
    summaries = target_capabilities["summaries"]
    for index, summary in enumerate(summaries):
        validate_package_artifact_requirement_evidence_ids(
            errors,
            f"$.targetCapabilities.summaries[{index}]",
            summary,
        )

    summary_targets = [summary["target"] for summary in summaries]
    if len(summary_targets) != len(set(summary_targets)):
        return

    summaries_by_target = {summary["target"]: summary for summary in summaries}
    selected_summary = summaries_by_target.get(decision["selectedTarget"])
    if selected_summary is not None:
        summary_ids = selected_summary.get(PACKAGE_ARTIFACT_REQUIREMENT_EVIDENCE_FIELD)
        decision_ids = decision.get(PACKAGE_ARTIFACT_REQUIREMENT_EVIDENCE_FIELD)
        if summary_ids is not None or decision_ids is not None:
            add_equal_error(
                errors,
                f"$.targetDecision.{PACKAGE_ARTIFACT_REQUIREMENT_EVIDENCE_FIELD}",
                decision_ids,
                summary_ids,
                f"selected target summary {PACKAGE_ARTIFACT_REQUIREMENT_EVIDENCE_FIELD}",
            )

    for index, record in enumerate(decision["fallbackTargetRecords"]):
        record_summary = summaries_by_target.get(record["target"])
        if record_summary is None:
            continue
        summary_ids = record_summary.get(PACKAGE_ARTIFACT_REQUIREMENT_EVIDENCE_FIELD)
        record_ids = record.get(PACKAGE_ARTIFACT_REQUIREMENT_EVIDENCE_FIELD)
        if summary_ids is not None or record_ids is not None:
            add_equal_error(
                errors,
                "$.targetDecision.fallbackTargetRecords"
                f"[{index}].{PACKAGE_ARTIFACT_REQUIREMENT_EVIDENCE_FIELD}",
                record_ids,
                summary_ids,
                f"fallback target summary {PACKAGE_ARTIFACT_REQUIREMENT_EVIDENCE_FIELD}",
            )
        validate_package_artifact_requirement_evidence_ids(
            errors,
            f"$.targetDecision.fallbackTargetRecords[{index}]",
            record,
        )

    if PACKAGE_ARTIFACT_REQUIREMENT_EVIDENCE_FIELD not in decision:
        return
    selected_record = {
        "target": decision["selectedTarget"],
        "packageMode": decision["selectedTargetPackageMode"],
        "packageBuildSupported": decision["selectedTargetPackageBuildSupported"],
        PACKAGE_ARTIFACT_REQUIREMENT_EVIDENCE_FIELD: decision[
            PACKAGE_ARTIFACT_REQUIREMENT_EVIDENCE_FIELD
        ],
    }
    expected_ids = expected_package_artifact_requirement_evidence_ids(selected_record)
    decision_ids = decision[PACKAGE_ARTIFACT_REQUIREMENT_EVIDENCE_FIELD]
    if decision_ids != expected_ids:
        errors.append(
            "$.targetDecision.packageArtifactRequirementEvidenceIds: "
            "expected package artifact requirement evidence ids "
            f"{expected_ids!r}, got {decision_ids!r}"
        )


def debug_location_records(locations):
    return (
        list(locations["expressions"])
        + list(locations["types"])
        + list(locations["statements"])
    )


def validate_debug_source_location_contexts(errors, locations):
    records = debug_location_records(locations)
    if not records:
        errors.append(
            "$.hirSourceLocations: debug metadata must emit at least one source anchor"
        )
        return

    has_entrypoint_stage_anchor = False
    for group_name in ("expressions", "types", "statements"):
        for index, record in enumerate(locations[group_name]):
            path = f"$.hirSourceLocations.{group_name}[{index}]"
            if record["entryPoint"] and not record["stage"]:
                errors.append(
                    f"{path}.stage: expected non-empty when entryPoint is non-empty"
                )
            if record["entryPoint"] and record["stage"]:
                has_entrypoint_stage_anchor = True

    if not has_entrypoint_stage_anchor:
        errors.append(
            "$.hirSourceLocations: expected at least one emitted source anchor "
            "with non-empty stage and entryPoint"
        )


def validate_semantics(instance):
    errors = []
    validate_debug_target_decision(errors, instance["targetDecision"])
    validate_debug_target_capabilities(errors, instance["targetCapabilities"])
    validate_debug_target_capability_summary_order(
        errors, instance["targetCapabilities"]
    )
    validate_debug_target_projection(
        errors, instance["targetDecision"], instance["targetCapabilities"]
    )
    validate_debug_target_legalization_evidence(
        errors, instance["targetDecision"], instance["targetCapabilities"]
    )
    validate_debug_target_tool_requirements(
        errors, instance["targetDecision"], instance["targetCapabilities"]
    )
    validate_debug_target_package_artifact_requirement_evidence(
        errors, instance["targetDecision"], instance["targetCapabilities"]
    )
    validate_source_locations(
        errors,
        "$.hirSourceLocations",
        instance["hirSourceLocations"],
        require_statements=True,
    )
    validate_debug_source_location_ranges(
        errors,
        instance["hirSourceLocations"],
        include_statements=True,
    )
    validate_debug_source_location_contexts(errors, instance["hirSourceLocations"])
    validate_manual_kernel_semantics(errors, instance)
    validate_manual_kernel_compatibility_alias(errors, instance)
    return errors
