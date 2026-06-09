"""Semantic checks for crosstl-project-portability-report-v1.schema.json."""

from .common import add_equal_error


CROSSGL_TARGETS = frozenset(("cgl", "crossgl"))


def _increment(counter, key):
    counter[key] = counter.get(key, 0) + 1


def _increment_nested(counter, outer_key, inner_key):
    row = counter.setdefault(outer_key, {})
    _increment(row, inner_key)


def _validate_summary_count_map(errors, path, actual, expected, label):
    if actual != expected:
        errors.append(f"{path}: expected {label} counts {expected!r}, got {actual!r}")


def _provenance_pipeline_key(provenance):
    if not isinstance(provenance, dict):
        return "unknown"
    pipeline = provenance.get("pipeline")
    return pipeline if pipeline is not None else "unknown"


def _provenance_intermediate_key(provenance):
    if not isinstance(provenance, dict):
        return "unknown"
    intermediate = provenance.get("intermediate")
    if intermediate is None:
        return "none"
    return intermediate


def _expected_intermediate(source_backend, target):
    if source_backend is None or target is None:
        return None
    if source_backend not in CROSSGL_TARGETS and target not in CROSSGL_TARGETS:
        return "crossgl"
    return None


def _diagnostic_counts(diagnostics):
    counts = {"note": 0, "warning": 0, "error": 0}
    for diagnostic in diagnostics:
        severity = diagnostic["severity"]
        counts[severity] = counts.get(severity, 0) + 1
    return counts


def _diagnostic_counts_by_field(diagnostics, field_name):
    counts = {}
    for diagnostic in diagnostics:
        value = diagnostic.get(field_name)
        if value:
            _increment(counts, value)
    return dict(sorted(counts.items()))


def _diagnostic_counts_by_missing_capability(diagnostics):
    counts = {}
    for diagnostic in diagnostics:
        for capability in diagnostic.get("missingCapabilities", []):
            _increment(counts, capability)
    return dict(sorted(counts.items()))


def validate_semantics(instance):
    errors = []
    artifacts = instance["artifacts"]
    summary = instance["summary"]
    diagnostics = instance.get("diagnostics", [])

    artifact_provenance_by_pipeline = {}
    artifact_provenance_by_intermediate = {}
    artifact_provenance_intermediate_by_source_backend = {}
    artifact_provenance_intermediate_by_target = {}
    artifact_provenance_intermediate_by_variant = {}
    source_map_count = 0
    fine_grained_source_map_count = 0
    source_maps_by_granularity = {}
    source_maps_by_target = {}
    source_maps_by_source_backend = {}
    source_maps_by_variant = {}
    source_remap_count = 0
    source_remap_mapping_count = 0
    source_remap_paths = set()
    source_remaps_by_granularity = {}
    source_remaps_by_target = {}
    source_remaps_by_source_backend = {}
    source_remaps_by_variant = {}

    add_equal_error(
        errors,
        "$.summary.artifactCount",
        summary["artifactCount"],
        len(artifacts),
        "artifacts length",
    )

    for index, artifact in enumerate(artifacts):
        artifact_path = f"$.artifacts[{index}]"
        target = artifact.get("target")
        status = artifact.get("status")
        source = artifact.get("source")
        source_backend = artifact.get("sourceBackend")
        variant = artifact.get("variant")
        generated_path = artifact.get("path")
        provenance = artifact.get("provenance")
        source_map = artifact.get("sourceMap")
        source_remap = artifact.get("sourceRemap")

        provenance_pipeline = _provenance_pipeline_key(provenance)
        provenance_intermediate = _provenance_intermediate_key(provenance)
        _increment(artifact_provenance_by_pipeline, provenance_pipeline)
        _increment(artifact_provenance_by_intermediate, provenance_intermediate)
        _increment_nested(
            artifact_provenance_intermediate_by_source_backend,
            source_backend if source_backend is not None else "unknown",
            provenance_intermediate,
        )
        _increment_nested(
            artifact_provenance_intermediate_by_target,
            target if target is not None else "unknown",
            provenance_intermediate,
        )
        if variant is not None:
            _increment_nested(
                artifact_provenance_intermediate_by_variant,
                variant,
                provenance_intermediate,
            )
        if isinstance(provenance, dict):
            expected_intermediate = _expected_intermediate(source_backend, target)
            if provenance["intermediate"] != expected_intermediate:
                errors.append(
                    f"{artifact_path}.provenance.intermediate: expected "
                    f"{expected_intermediate!r} for sourceBackend {source_backend!r} "
                    f"and target {target!r}"
                )

        if source_map is not None:
            source_map_count += 1
            source_map_granularity = source_map["mappingGranularity"]
            if source_map_granularity != "file":
                fine_grained_source_map_count += 1
            _increment(source_maps_by_granularity, source_map_granularity)
            _increment(
                source_maps_by_target, target if target is not None else "unknown"
            )
            _increment(
                source_maps_by_source_backend,
                source_backend if source_backend is not None else "unknown",
            )
            if variant is not None:
                _increment(source_maps_by_variant, variant)

            if target is not None and source_map["target"] != target:
                errors.append(
                    f"{artifact_path}.sourceMap.target: expected to match artifact "
                    f"target {target!r}"
                )
            source_span = source_map["source"]
            if source is not None and source_span["file"] != source:
                errors.append(
                    f"{artifact_path}.sourceMap.source.file: expected to match "
                    f"artifact source {source!r}"
                )
            generated_span = source_map["generated"]
            if generated_path is not None and generated_span["file"] != generated_path:
                errors.append(
                    f"{artifact_path}.sourceMap.generated.file: expected to match "
                    f"artifact path {generated_path!r}"
                )

        if target == "cgl" and status == "translated" and source_remap is None:
            errors.append(
                f"{artifact_path}.sourceRemap: expected translated cgl artifact "
                "to record sourceRemap metadata"
            )
            continue
        if source_remap is None:
            continue

        source_remap_count += 1
        source_remap_mapping_count += source_remap["mappingCount"]
        _increment(source_remaps_by_granularity, source_remap["mappingGranularity"])
        _increment(source_remaps_by_target, source_remap["target"])
        if source_backend is not None:
            _increment(source_remaps_by_source_backend, source_backend)
        if variant is not None:
            _increment(source_remaps_by_variant, variant)

        source_remap_path = source_remap["path"]
        if source_remap_path in source_remap_paths:
            errors.append(
                f"{artifact_path}.sourceRemap.path: duplicate sourceRemap path"
            )
        source_remap_paths.add(source_remap_path)

        if target is not None and target != "cgl":
            errors.append(
                f"{artifact_path}.sourceRemap: expected only for cgl target artifacts"
            )
        if target is not None and source_remap["target"] != target:
            errors.append(
                f"{artifact_path}.sourceRemap.target: expected to match artifact "
                f"target {target!r}"
            )
        if generated_path is not None:
            if source_remap["generatedFile"] != generated_path:
                errors.append(
                    f"{artifact_path}.sourceRemap.generatedFile: expected to match "
                    f"artifact path {generated_path!r}"
                )
            if source_remap_path == generated_path:
                errors.append(
                    f"{artifact_path}.sourceRemap.path: expected sidecar path, "
                    "not generated artifact path"
                )
        if source_remap["mappingCount"] <= 0:
            errors.append(f"{artifact_path}.sourceRemap.mappingCount: expected > 0")

    if "diagnostics" in instance:
        diagnostic_counts = _diagnostic_counts(diagnostics)
        diagnostics_by_code = _diagnostic_counts_by_field(diagnostics, "code")
        diagnostics_by_target = _diagnostic_counts_by_field(diagnostics, "target")
        diagnostics_by_source_backend = _diagnostic_counts_by_field(
            diagnostics, "sourceBackend"
        )
        diagnostics_by_variant = _diagnostic_counts_by_field(diagnostics, "variant")
        missing_capability_counts = _diagnostic_counts_by_missing_capability(
            diagnostics
        )

        if "diagnosticCounts" in instance:
            _validate_summary_count_map(
                errors,
                "$.diagnosticCounts",
                instance["diagnosticCounts"],
                diagnostic_counts,
                "diagnostic",
            )
        if "diagnosticCounts" in summary:
            _validate_summary_count_map(
                errors,
                "$.summary.diagnosticCounts",
                summary["diagnosticCounts"],
                diagnostic_counts,
                "diagnostic",
            )
        if "diagnosticsByCode" in summary:
            _validate_summary_count_map(
                errors,
                "$.summary.diagnosticsByCode",
                summary["diagnosticsByCode"],
                diagnostics_by_code,
                "diagnostic",
            )
        if "diagnosticsByTarget" in summary:
            _validate_summary_count_map(
                errors,
                "$.summary.diagnosticsByTarget",
                summary["diagnosticsByTarget"],
                diagnostics_by_target,
                "diagnostic",
            )
        if "diagnosticsBySourceBackend" in summary:
            _validate_summary_count_map(
                errors,
                "$.summary.diagnosticsBySourceBackend",
                summary["diagnosticsBySourceBackend"],
                diagnostics_by_source_backend,
                "diagnostic",
            )
        if "diagnosticsByVariant" in summary:
            _validate_summary_count_map(
                errors,
                "$.summary.diagnosticsByVariant",
                summary["diagnosticsByVariant"],
                diagnostics_by_variant,
                "diagnostic",
            )
        if "missingCapabilityCounts" in summary:
            _validate_summary_count_map(
                errors,
                "$.summary.missingCapabilityCounts",
                summary["missingCapabilityCounts"],
                missing_capability_counts,
                "diagnostic",
            )

    if "artifactProvenanceByPipeline" in summary:
        _validate_summary_count_map(
            errors,
            "$.summary.artifactProvenanceByPipeline",
            summary["artifactProvenanceByPipeline"],
            artifact_provenance_by_pipeline,
            "artifact provenance",
        )
    if "artifactProvenanceByIntermediate" in summary:
        _validate_summary_count_map(
            errors,
            "$.summary.artifactProvenanceByIntermediate",
            summary["artifactProvenanceByIntermediate"],
            artifact_provenance_by_intermediate,
            "artifact provenance",
        )
    if "artifactProvenanceIntermediateBySourceBackend" in summary:
        _validate_summary_count_map(
            errors,
            "$.summary.artifactProvenanceIntermediateBySourceBackend",
            summary["artifactProvenanceIntermediateBySourceBackend"],
            artifact_provenance_intermediate_by_source_backend,
            "artifact provenance",
        )
    if "artifactProvenanceIntermediateByTarget" in summary:
        _validate_summary_count_map(
            errors,
            "$.summary.artifactProvenanceIntermediateByTarget",
            summary["artifactProvenanceIntermediateByTarget"],
            artifact_provenance_intermediate_by_target,
            "artifact provenance",
        )
    if "artifactProvenanceIntermediateByVariant" in summary:
        _validate_summary_count_map(
            errors,
            "$.summary.artifactProvenanceIntermediateByVariant",
            summary["artifactProvenanceIntermediateByVariant"],
            artifact_provenance_intermediate_by_variant,
            "artifact provenance",
        )

    if "sourceMapCount" in summary:
        add_equal_error(
            errors,
            "$.summary.sourceMapCount",
            summary["sourceMapCount"],
            source_map_count,
            "sourceMap artifact count",
        )
    if "fineGrainedSourceMapCount" in summary:
        add_equal_error(
            errors,
            "$.summary.fineGrainedSourceMapCount",
            summary["fineGrainedSourceMapCount"],
            fine_grained_source_map_count,
            "fine-grained sourceMap artifact count",
        )
    if "sourceMapsByGranularity" in summary:
        _validate_summary_count_map(
            errors,
            "$.summary.sourceMapsByGranularity",
            summary["sourceMapsByGranularity"],
            source_maps_by_granularity,
            "sourceMap",
        )
    if "sourceMapsByTarget" in summary:
        _validate_summary_count_map(
            errors,
            "$.summary.sourceMapsByTarget",
            summary["sourceMapsByTarget"],
            source_maps_by_target,
            "sourceMap",
        )
    if "sourceMapsBySourceBackend" in summary:
        _validate_summary_count_map(
            errors,
            "$.summary.sourceMapsBySourceBackend",
            summary["sourceMapsBySourceBackend"],
            source_maps_by_source_backend,
            "sourceMap",
        )
    if "sourceMapsByVariant" in summary:
        _validate_summary_count_map(
            errors,
            "$.summary.sourceMapsByVariant",
            summary["sourceMapsByVariant"],
            source_maps_by_variant,
            "sourceMap",
        )

    add_equal_error(
        errors,
        "$.summary.sourceRemapCount",
        summary["sourceRemapCount"],
        source_remap_count,
        "sourceRemap artifact count",
    )
    add_equal_error(
        errors,
        "$.summary.sourceRemapMappingCount",
        summary["sourceRemapMappingCount"],
        source_remap_mapping_count,
        "sourceRemap mapping total",
    )

    if "sourceRemapsByGranularity" in summary:
        _validate_summary_count_map(
            errors,
            "$.summary.sourceRemapsByGranularity",
            summary["sourceRemapsByGranularity"],
            source_remaps_by_granularity,
            "sourceRemap",
        )
    if "sourceRemapsByTarget" in summary:
        _validate_summary_count_map(
            errors,
            "$.summary.sourceRemapsByTarget",
            summary["sourceRemapsByTarget"],
            source_remaps_by_target,
            "sourceRemap",
        )
    if "sourceRemapsBySourceBackend" in summary:
        _validate_summary_count_map(
            errors,
            "$.summary.sourceRemapsBySourceBackend",
            summary["sourceRemapsBySourceBackend"],
            source_remaps_by_source_backend,
            "sourceRemap",
        )
    if "sourceRemapsByVariant" in summary:
        _validate_summary_count_map(
            errors,
            "$.summary.sourceRemapsByVariant",
            summary["sourceRemapsByVariant"],
            source_remaps_by_variant,
            "sourceRemap",
        )

    return errors
