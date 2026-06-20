"""Semantic checks for debug-metadata-v12.schema.json."""

from .common import validate_source_locations
from .debug_metadata_v10 import validate_debug_source_location_ranges
from .debug_metadata_v11 import validate_debug_target_capabilities
from .debug_metadata_v11 import validate_debug_target_capability_summary_order
from .debug_metadata_v11 import validate_debug_target_decision
from .debug_metadata_v11 import validate_debug_target_legalization_evidence
from .debug_metadata_v11 import validate_debug_target_projection
from .debug_metadata_v11 import validate_manual_kernel_compatibility_alias
from .debug_metadata_v11 import validate_manual_kernel_semantics
from .hir_source_map_v8 import validate_resource_location_ranges
from .hir_source_map_v8 import validate_resource_source_location_context


def validate_debug_resource_location_contexts(errors, locations):
    records = (
        list(locations["expressions"])
        + list(locations["types"])
        + list(locations["statements"])
        + list(locations["resources"])
    )
    if not records:
        errors.append(
            "$.hirSourceLocations: debug metadata must emit at least one source anchor"
        )
        return

    has_entrypoint_stage_anchor = False
    for resource_index, resource in enumerate(locations["resources"]):
        path = f"$.hirSourceLocations.resources[{resource_index}]"
        validate_resource_source_location_context(errors, path, resource)
        if resource["entryPoint"] and resource["stage"]:
            has_entrypoint_stage_anchor = True

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
    validate_source_locations(
        errors,
        "$.hirSourceLocations",
        instance["hirSourceLocations"],
        require_statements=True,
        include_resources=True,
    )
    validate_debug_source_location_ranges(
        errors,
        instance["hirSourceLocations"],
        include_statements=True,
    )
    validate_resource_location_ranges(
        errors,
        "$.hirSourceLocations",
        instance["hirSourceLocations"],
    )
    validate_debug_resource_location_contexts(errors, instance["hirSourceLocations"])
    validate_manual_kernel_semantics(errors, instance)
    validate_manual_kernel_compatibility_alias(errors, instance)
    return errors
