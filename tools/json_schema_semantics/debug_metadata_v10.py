"""Semantic checks for debug-metadata-v10.schema.json."""

from .common import add_equal_error
from .common import add_length_count_error
from .common import expected_package_mode
from .common import validate_capability_groups
from .common import validate_source_locations
from .common import validate_unique_values


def is_predicate_capability_id(capability):
    parts = capability.split(".", 2)
    return len(parts) == 3 and parts[1] in {"backend", "diagnostic"}


def expected_package_rank_score(record):
    return {
        "native": 0,
        "source-package": 1,
        "unsupported": 2,
    }[expected_package_mode(record)]


def validate_debug_target_decision(errors, decision):
    selected_record = {
        "packageBuildSupported": decision["selectedTargetPackageBuildSupported"],
        "nativeImplemented": decision["selectedTargetNativeImplemented"],
        "sourcePackageSupported": decision["selectedTargetSourcePackageSupported"],
    }
    add_equal_error(
        errors,
        "$.targetDecision.selectedTargetPackageMode",
        decision["selectedTargetPackageMode"],
        expected_package_mode(selected_record),
        "selected target package flags",
    )

    missing = decision["selectedTargetMissingCapabilities"]
    add_length_count_error(
        errors,
        "$.targetDecision.selectedTargetMissingCapabilityCount",
        decision["selectedTargetMissingCapabilityCount"],
        missing,
        "$.targetDecision.selectedTargetMissingCapabilities length",
    )
    validate_capability_groups(
        errors,
        "$.targetDecision.selectedTargetMissingCapabilityGroups",
        decision["selectedTargetMissingCapabilityGroups"],
        missing,
    )

    diagnostics = decision["diagnostics"]
    add_length_count_error(
        errors,
        "$.targetDecision.selectedTargetDiagnosticCount",
        decision["selectedTargetDiagnosticCount"],
        diagnostics,
        "$.targetDecision.diagnostics length",
    )
    for index, diagnostic in enumerate(diagnostics):
        validate_capability_groups(
            errors,
            f"$.targetDecision.diagnostics[{index}].capabilityGroups",
            diagnostic["capabilityGroups"],
            diagnostic["capabilities"],
        )

    fallback_records = decision["fallbackTargetRecords"]
    add_length_count_error(
        errors,
        "$.targetDecision.fallbackTargetRecordCount",
        decision["fallbackTargetRecordCount"],
        fallback_records,
        "$.targetDecision.fallbackTargetRecords length",
    )
    add_length_count_error(
        errors,
        "$.targetDecision.fallbackTargets",
        len(decision["fallbackTargets"]),
        fallback_records,
        "$.targetDecision.fallbackTargetRecords length",
    )
    for index, record in enumerate(fallback_records):
        record_path = f"$.targetDecision.fallbackTargetRecords[{index}]"
        fallback_mode = expected_package_mode(record)
        fallback_reason = {
            "native": "native-package-available",
            "source-package": "source-package-available",
            "unsupported": "unsupported",
        }[fallback_mode]
        add_equal_error(
            errors,
            f"{record_path}.packageMode",
            record["packageMode"],
            fallback_mode,
            "fallback package flags",
        )
        add_equal_error(
            errors,
            f"{record_path}.rankReason",
            record["rankReason"],
            fallback_reason,
            "fallback package mode reason",
        )
        add_equal_error(
            errors,
            f"{record_path}.rank",
            record["rank"],
            index + 1,
            "1-based fallback rank",
        )
        add_equal_error(
            errors,
            f"{record_path}.target",
            record["target"],
            decision["fallbackTargets"][index],
            "$.targetDecision.fallbackTargets entry",
        )
        validate_capability_groups(
            errors,
            f"{record_path}.missingCapabilityGroups",
            record["missingCapabilityGroups"],
            record["missingCapabilities"],
        )
        add_length_count_error(
            errors,
            f"{record_path}.missingCapabilityCount",
            record["missingCapabilityCount"],
            record["missingCapabilities"],
            f"{record_path}.missingCapabilities length",
        )


def validate_debug_target_capabilities(errors, target_capabilities):
    summaries = target_capabilities["summaries"]
    default_target = target_capabilities["defaultTarget"]
    validate_unique_values(
        errors,
        "$.targetCapabilities.summaries",
        [summary["target"] for summary in summaries],
        "target summary",
    )
    if default_target not in [summary["target"] for summary in summaries]:
        errors.append(
            "$.targetCapabilities.defaultTarget: expected target to appear in summaries"
        )
    for index, summary in enumerate(summaries):
        path = f"$.targetCapabilities.summaries[{index}]"
        summary_mode = expected_package_mode(summary)
        summary_reason = {
            "native": "native-package-available",
            "source-package": "source-package-available",
            "unsupported": "unsupported",
        }[summary_mode]
        add_equal_error(
            errors,
            f"{path}.packageMode",
            summary["packageMode"],
            summary_mode,
            "target capability package flags",
        )
        add_equal_error(
            errors,
            f"{path}.packageDecisionReason",
            summary["packageDecisionReason"],
            summary_reason,
            "target capability package mode reason",
        )
        add_equal_error(
            errors,
            f"{path}.packageRankScore",
            summary["packageRankScore"],
            expected_package_rank_score(summary),
            "target capability package mode rank",
        )
        required = summary["requiredCapabilities"]
        missing = summary["missingCapabilities"]
        add_length_count_error(
            errors,
            f"{path}.requiredCapabilityCount",
            summary["requiredCapabilityCount"],
            required,
            f"{path}.requiredCapabilities length",
        )
        add_length_count_error(
            errors,
            f"{path}.missingCapabilityCount",
            summary["missingCapabilityCount"],
            missing,
            f"{path}.missingCapabilities length",
        )
        validate_capability_groups(
            errors,
            f"{path}.requiredCapabilityGroups",
            summary["requiredCapabilityGroups"],
            required,
        )
        validate_capability_groups(
            errors,
            f"{path}.missingCapabilityGroups",
            summary["missingCapabilityGroups"],
            missing,
        )
        required_set = set(required)
        for capability in missing:
            if capability not in required_set and not is_predicate_capability_id(
                capability
            ):
                errors.append(
                    f"{path}.missingCapabilities: expected missing capability "
                    f"{capability!r} to appear in requiredCapabilities"
                )


def validate_debug_target_projection(errors, decision, target_capabilities):
    summaries = target_capabilities["summaries"]
    summary_targets = [summary["target"] for summary in summaries]
    if len(summary_targets) != len(set(summary_targets)):
        return

    summaries_by_target = {summary["target"]: summary for summary in summaries}
    selected_summary = summaries_by_target.get(decision["selectedTarget"])
    if selected_summary is None:
        errors.append(
            "$.targetDecision.selectedTarget: expected selected target "
            "to appear in targetCapabilities.summaries"
        )
        return

    selected_field_pairs = (
        ("selectedTargetNativeImplemented", "nativeImplemented"),
        ("selectedTargetSourcePackageSupported", "sourcePackageSupported"),
        ("selectedTargetPackageBuildSupported", "packageBuildSupported"),
        ("selectedTargetPackageMode", "packageMode"),
        ("selectedTargetMissingCapabilityCount", "missingCapabilityCount"),
        ("selectedTargetMissingCapabilities", "missingCapabilities"),
        ("selectedTargetMissingCapabilityGroups", "missingCapabilityGroups"),
    )
    for decision_field, summary_field in selected_field_pairs:
        add_equal_error(
            errors,
            f"$.targetDecision.{decision_field}",
            decision[decision_field],
            selected_summary[summary_field],
            f"selected target summary {summary_field}",
        )

    viable_targets = [
        summary["target"] for summary in summaries if summary["packageBuildSupported"]
    ]
    non_viable_targets = [
        summary["target"]
        for summary in summaries
        if not summary["packageBuildSupported"]
    ]
    add_equal_error(
        errors,
        "$.targetDecision.viableTargets",
        decision["viableTargets"],
        viable_targets,
        "targetCapabilities buildable target order",
    )
    add_equal_error(
        errors,
        "$.targetDecision.nonViableTargets",
        decision["nonViableTargets"],
        non_viable_targets,
        "targetCapabilities non-buildable target order",
    )

    fallback_summaries = [
        summary
        for summary in summaries
        if summary["packageBuildSupported"]
        and summary["target"] != decision["selectedTarget"]
    ]
    fallback_summaries.sort(key=lambda summary: summary["packageRankScore"])
    fallback_targets = [summary["target"] for summary in fallback_summaries]
    add_equal_error(
        errors,
        "$.targetDecision.fallbackTargets",
        decision["fallbackTargets"],
        fallback_targets,
        "targetCapabilities buildable fallback rank order",
    )

    fallback_field_pairs = (
        ("target", "target"),
        ("nativeImplemented", "nativeImplemented"),
        ("sourcePackageSupported", "sourcePackageSupported"),
        ("packageBuildSupported", "packageBuildSupported"),
        ("packageMode", "packageMode"),
        ("rankReason", "packageDecisionReason"),
        ("missingCapabilityCount", "missingCapabilityCount"),
        ("missingCapabilities", "missingCapabilities"),
        ("missingCapabilityGroups", "missingCapabilityGroups"),
    )
    for index, expected_summary in enumerate(fallback_summaries):
        if index >= len(decision["fallbackTargetRecords"]):
            break
        record = decision["fallbackTargetRecords"][index]
        for record_field, summary_field in fallback_field_pairs:
            add_equal_error(
                errors,
                f"$.targetDecision.fallbackTargetRecords[{index}].{record_field}",
                record[record_field],
                expected_summary[summary_field],
                f"fallback target summary {summary_field}",
            )


def validate_manual_kernel_semantics(errors, instance):
    summary = instance["manualTextureCompareKernelSummary"]
    buckets = instance["manualTextureCompareKernelBuckets"]
    kernels = instance["manualTextureCompareKernels"]
    add_length_count_error(
        errors,
        "$.manualTextureCompareKernelSummary.totalCount",
        summary["totalCount"],
        kernels,
        "$.manualTextureCompareKernels length",
    )

    bucket_specs = [
        ("staticNormalized", "staticNormalizedCount", "static-normalized"),
        ("staticNonNormalized", "staticNonNormalizedCount", "static-non-normalized"),
        ("staticZeroSum", "staticZeroSumCount", "static-zero-sum"),
        ("dynamic", "dynamicCount", "dynamic"),
    ]
    bucket_indices = []
    for bucket_name, count_name, weight_class in bucket_specs:
        bucket = buckets[bucket_name]
        add_equal_error(
            errors,
            f"$.manualTextureCompareKernelBuckets.{bucket_name}",
            len(bucket),
            summary[count_name],
            f"$.manualTextureCompareKernelSummary.{count_name}",
        )
        for kernel_index in bucket:
            bucket_indices.append(kernel_index)
            if kernel_index >= len(kernels):
                errors.append(
                    f"$.manualTextureCompareKernelBuckets.{bucket_name}: "
                    f"index {kernel_index} is outside manualTextureCompareKernels"
                )
                continue
            add_equal_error(
                errors,
                f"$.manualTextureCompareKernels[{kernel_index}].weightClass",
                kernels[kernel_index]["weightClass"],
                weight_class,
                f"{bucket_name} bucket weight class",
            )

    summary_bucket_total = sum(summary[count_name] for _, count_name, _ in bucket_specs)
    add_equal_error(
        errors,
        "$.manualTextureCompareKernelSummary",
        summary_bucket_total,
        summary["totalCount"],
        "sum of bucket counts",
    )
    if sorted(bucket_indices) != list(range(len(kernels))):
        errors.append(
            "$.manualTextureCompareKernelBuckets: expected bucket indexes to "
            "partition manualTextureCompareKernels"
        )

    for index, kernel in enumerate(kernels):
        kernel_path = f"$.manualTextureCompareKernels[{index}]"
        add_equal_error(
            errors,
            f"{kernel_path}.index",
            kernel["index"],
            index,
            "array index",
        )
        if kernel["weightsStatic"] and "weightSum" not in kernel:
            errors.append(f"{kernel_path}: static weights require weightSum")
        if not kernel["weightsStatic"] and "weightSum" in kernel:
            errors.append(f"{kernel_path}: dynamic weights must omit weightSum")


def validate_source_location_range(errors, path, location):
    if location["length"] <= 0:
        errors.append(f"{path}.length: expected > 0")
    for field in ("line", "column", "endLine", "endColumn"):
        if location[field] <= 0:
            errors.append(f"{path}.{field}: expected > 0")
    if (
        location["length"] > 0
        and location["endLine"] == location["line"]
        and location["endColumn"] <= location["column"]
    ):
        errors.append(f"{path}.endColumn: expected > column for same-line span")


def validate_debug_source_location_ranges(
    errors,
    locations,
    *,
    include_statements=False,
):
    for index, expression in enumerate(locations["expressions"]):
        validate_source_location_range(
            errors,
            f"$.hirSourceLocations.expressions[{index}].location",
            expression["location"],
        )
    for index, type_record in enumerate(locations["types"]):
        validate_source_location_range(
            errors,
            f"$.hirSourceLocations.types[{index}].location",
            type_record["location"],
        )
    if include_statements:
        for index, statement in enumerate(locations["statements"]):
            validate_source_location_range(
                errors,
                f"$.hirSourceLocations.statements[{index}].location",
                statement["location"],
            )


def validate_semantics(instance):
    errors = []
    validate_debug_target_decision(errors, instance["targetDecision"])
    validate_debug_target_capabilities(errors, instance["targetCapabilities"])
    validate_debug_target_projection(
        errors, instance["targetDecision"], instance["targetCapabilities"]
    )
    validate_source_locations(
        errors, "$.hirSourceLocations", instance["hirSourceLocations"]
    )
    validate_debug_source_location_ranges(errors, instance["hirSourceLocations"])
    validate_manual_kernel_semantics(errors, instance)
    return errors
