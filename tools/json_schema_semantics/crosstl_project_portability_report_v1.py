"""Semantic checks for crosstl-project-portability-report-v1.schema.json."""

from .common import add_equal_error


def _increment(counter, key):
    counter[key] = counter.get(key, 0) + 1


def _validate_summary_count_map(errors, path, actual, expected):
    if actual != expected:
        errors.append(
            f"{path}: expected sourceRemap counts {expected!r}, got {actual!r}"
        )


def validate_semantics(instance):
    errors = []
    artifacts = instance["artifacts"]
    summary = instance["summary"]

    source_remap_count = 0
    source_remap_mapping_count = 0
    source_remap_paths = set()
    source_remaps_by_granularity = {}
    source_remaps_by_target = {}
    source_remaps_by_source_backend = {}

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
        source_backend = artifact.get("sourceBackend")
        generated_path = artifact.get("path")
        source_remap = artifact.get("sourceRemap")

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
        )
    if "sourceRemapsByTarget" in summary:
        _validate_summary_count_map(
            errors,
            "$.summary.sourceRemapsByTarget",
            summary["sourceRemapsByTarget"],
            source_remaps_by_target,
        )
    if "sourceRemapsBySourceBackend" in summary:
        _validate_summary_count_map(
            errors,
            "$.summary.sourceRemapsBySourceBackend",
            summary["sourceRemapsBySourceBackend"],
            source_remaps_by_source_backend,
        )

    return errors
