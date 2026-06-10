"""Semantic checks for crosstl-project-portability-report-v1.schema.json."""

from .common import add_equal_error, validate_source_location_span


CROSSGL_TARGETS = frozenset(("cgl", "crossgl"))


def _increment(counter, key):
    counter[key] = counter.get(key, 0) + 1


def _increment_nested(counter, outer_key, inner_key):
    row = counter.setdefault(outer_key, {})
    _increment(row, inner_key)


def _validate_summary_count_map(errors, path, actual, expected, label):
    if actual != expected:
        errors.append(f"{path}: expected {label} counts {expected!r}, got {actual!r}")


def _validate_declared_target_count_keys(
    errors, path, actual, declared_targets, allow_unknown=False
):
    if declared_targets is None:
        return
    for target in actual:
        if allow_unknown and target == "unknown":
            continue
        if target not in declared_targets:
            errors.append(
                f"{path}[{target!r}]: expected key to be declared in $.project.targets"
            )


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


def _span_identity(span):
    return (
        span["file"],
        span["line"],
        span["column"],
        span["offset"],
        span["length"],
        span["endLine"],
        span["endColumn"],
        span["endOffset"],
    )


def _spans_overlap(left, right):
    if left["file"] != right["file"]:
        return False
    return left["offset"] < right["endOffset"] and right["offset"] < left["endOffset"]


def _span_is_single_line(span):
    return span["line"] == span["endLine"]


def _validate_source_map_span(errors, path, span):
    validate_source_location_span(errors, path, span)
    if span["length"] <= 0:
        errors.append(f"{path}.length: expected > 0")
    if (
        span["length"] > 0
        and span["endLine"] == span["line"]
        and span["endColumn"] <= span["column"]
    ):
        errors.append(f"{path}.endColumn: expected > column for same-line span")


def _validate_span_within_envelope(errors, path, span, envelope, label):
    if span["file"] != envelope["file"]:
        errors.append(f"{path}.file: expected to match {label}.file")
    if span["offset"] < envelope["offset"]:
        errors.append(f"{path}.offset: expected >= {label}.offset")
    if span["endOffset"] > envelope["endOffset"]:
        errors.append(f"{path}.endOffset: expected <= {label}.endOffset")


def _validate_source_map_semantics(
    errors, artifact_path, target, source_map_granularity, source_map
):
    if target not in CROSSGL_TARGETS and source_map_granularity in (
        "statement",
        "token",
    ):
        errors.append(
            f"{artifact_path}.sourceMap.mappingGranularity: expected file or line "
            "for backend-generated artifacts until compiler backend-lowering "
            "source maps are available"
        )

    source_span = source_map["source"]
    generated_span = source_map["generated"]
    _validate_source_map_span(errors, f"{artifact_path}.sourceMap.source", source_span)
    _validate_source_map_span(
        errors, f"{artifact_path}.sourceMap.generated", generated_span
    )

    generated_spans = []
    seen_mappings = set()
    for mapping_index, mapping in enumerate(source_map["mappings"]):
        mapping_path = f"{artifact_path}.sourceMap.mappings[{mapping_index}]"
        mapping_source = mapping["source"]
        mapping_generated = mapping["generated"]
        _validate_source_map_span(errors, f"{mapping_path}.source", mapping_source)
        _validate_source_map_span(
            errors, f"{mapping_path}.generated", mapping_generated
        )
        _validate_span_within_envelope(
            errors,
            f"{mapping_path}.source",
            mapping_source,
            source_span,
            f"{artifact_path}.sourceMap.source",
        )
        _validate_span_within_envelope(
            errors,
            f"{mapping_path}.generated",
            mapping_generated,
            generated_span,
            f"{artifact_path}.sourceMap.generated",
        )
        if source_map_granularity == "line" and not (
            _span_is_single_line(mapping_source)
            and _span_is_single_line(mapping_generated)
        ):
            errors.append(
                f"{mapping_path}: expected single source and generated line "
                "for line granularity"
            )
        for prior_index, prior_generated in generated_spans:
            if _spans_overlap(prior_generated, mapping_generated):
                errors.append(
                    f"{mapping_path}.generated: overlaps "
                    f"{artifact_path}.sourceMap.mappings[{prior_index}].generated"
                )
                break
        generated_spans.append((mapping_index, mapping_generated))
        mapping_identity = (
            _span_identity(mapping_source),
            _span_identity(mapping_generated),
        )
        if mapping_identity in seen_mappings:
            errors.append(f"{mapping_path}: duplicate source/generated span pair")
        seen_mappings.add(mapping_identity)

    if source_map_granularity == "file":
        if len(source_map["mappings"]) != 1:
            errors.append(
                f"{artifact_path}.sourceMap.mappings: expected exactly one "
                "source/generated span pair for file granularity"
            )
            return
        mapping = source_map["mappings"][0]
        if _span_identity(mapping["source"]) != _span_identity(
            source_span
        ) or _span_identity(mapping["generated"]) != _span_identity(generated_span):
            errors.append(
                f"{artifact_path}.sourceMap.mappings[0]: expected "
                "source/generated envelopes for file granularity"
            )


def validate_semantics(instance):
    errors = []
    artifacts = instance["artifacts"]
    summary = instance["summary"]
    diagnostics = instance.get("diagnostics", [])
    artifact_paths = {
        artifact.get("path")
        for artifact in artifacts
        if artifact.get("path") is not None
    }
    project = instance.get("project")
    declared_targets = None
    if isinstance(project, dict) and isinstance(project.get("targets"), list):
        declared_targets = set(project["targets"])

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

        if (
            declared_targets is not None
            and target is not None
            and target not in declared_targets
        ):
            errors.append(
                f"{artifact_path}.target: expected to be declared in $.project.targets"
            )

        if status == "failed" and source_map is not None:
            errors.append(
                f"{artifact_path}.sourceMap: must be omitted for failed artifacts"
            )
        if status == "failed" and source_remap is not None:
            errors.append(
                f"{artifact_path}.sourceRemap: must be omitted for failed artifacts"
            )

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
            if (
                declared_targets is not None
                and source_map["target"] not in declared_targets
            ):
                errors.append(
                    f"{artifact_path}.sourceMap.target: expected to be declared "
                    "in $.project.targets"
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
            _validate_source_map_semantics(
                errors, artifact_path, target, source_map_granularity, source_map
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
        if (
            declared_targets is not None
            and source_remap["target"] not in declared_targets
        ):
            errors.append(
                f"{artifact_path}.sourceRemap.target: expected to be declared "
                "in $.project.targets"
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
        if source_remap_path in artifact_paths and source_remap_path != generated_path:
            errors.append(
                f"{artifact_path}.sourceRemap.path: expected sidecar path, "
                "not artifact path"
            )
        if isinstance(source_map, dict):
            source_map_granularity = source_map.get("mappingGranularity")
            if (
                source_map_granularity is not None
                and source_remap["mappingGranularity"] != source_map_granularity
            ):
                errors.append(
                    f"{artifact_path}.sourceRemap.mappingGranularity: expected "
                    "to match sourceMap.mappingGranularity"
                )
            source_map_mappings = source_map.get("mappings")
            if isinstance(source_map_mappings, list) and source_remap[
                "mappingCount"
            ] != len(source_map_mappings):
                errors.append(
                    f"{artifact_path}.sourceRemap.mappingCount: expected to "
                    "match sourceMap mappings"
                )
        if source_remap["mappingCount"] <= 0:
            errors.append(f"{artifact_path}.sourceRemap.mappingCount: expected > 0")

    for diagnostic_index, diagnostic in enumerate(diagnostics):
        target = diagnostic.get("target")
        if (
            declared_targets is not None
            and target is not None
            and target not in declared_targets
        ):
            errors.append(
                f"$.diagnostics[{diagnostic_index}].target: expected to be "
                "declared in $.project.targets"
            )

    diagnostic_counts = _diagnostic_counts(diagnostics)
    diagnostics_by_code = _diagnostic_counts_by_field(diagnostics, "code")
    diagnostics_by_target = _diagnostic_counts_by_field(diagnostics, "target")
    diagnostics_by_source_backend = _diagnostic_counts_by_field(
        diagnostics, "sourceBackend"
    )
    diagnostics_by_variant = _diagnostic_counts_by_field(diagnostics, "variant")
    missing_capability_counts = _diagnostic_counts_by_missing_capability(diagnostics)

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
        _validate_declared_target_count_keys(
            errors,
            "$.summary.diagnosticsByTarget",
            summary["diagnosticsByTarget"],
            declared_targets,
        )
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
        _validate_declared_target_count_keys(
            errors,
            "$.summary.artifactProvenanceIntermediateByTarget",
            summary["artifactProvenanceIntermediateByTarget"],
            declared_targets,
            allow_unknown=True,
        )
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
        _validate_declared_target_count_keys(
            errors,
            "$.summary.sourceMapsByTarget",
            summary["sourceMapsByTarget"],
            declared_targets,
            allow_unknown=True,
        )
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
        _validate_declared_target_count_keys(
            errors,
            "$.summary.sourceRemapsByTarget",
            summary["sourceRemapsByTarget"],
            declared_targets,
        )
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
