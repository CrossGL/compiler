"""Semantic checks for graphics-abi-verify-v1.schema.json."""

import re

from .common import add_equal_error
from .common import validate_source_location_span


SEVERITIES = ("note", "warning", "error")
TARGETS = ("metal", "vulkan", "directx", "opengl")
SOURCE_MAP_OWNERS = ("entryPoint", "resource", "abiRecord")
SOURCE_MAP_SUMMARY_COUNT_FIELDS = {
    "entryPoint": "entryPointCount",
    "resource": "resourceCount",
    "abiRecord": "abiRecordCount",
}
TARGET_LEGALIZATION_EVIDENCE_PREFIX = "target-legalization.v1"
TARGET_LEGALIZATION_RESOURCE_BINDING_EVIDENCE_RE = re.compile(
    r"^target-legalization\.v1\."
    r"(?P<target>metal|vulkan|directx|opengl)\."
    r"resource-binding\.[A-Za-z0-9_.-]+$"
)


def validate_normalized_path(errors, path, value):
    if "\\" in value:
        errors.append(f"{path}: expected normalized '/' path separators")


def validate_report_source_location(errors, path, location):
    validate_source_location_span(errors, path, location)
    validate_normalized_path(errors, f"{path}.file", location["file"])


def add_source_location_equal_error(
    errors,
    path,
    actual,
    expected,
    expected_label,
):
    if actual != expected:
        errors.append(
            f"{path}: expected source location matching {expected_label}, "
            f"got {actual!r}"
        )


def validate_resource_binding_evidence_id(errors, path, evidence, seen_evidence_ids):
    evidence_id = evidence.get("evidenceId")
    if evidence_id is None:
        return

    if evidence_id in seen_evidence_ids:
        errors.append(
            f"{path}.evidenceId: duplicate target resource binding evidence id "
            f"{evidence_id!r}"
        )
    seen_evidence_ids.add(evidence_id)

    match = TARGET_LEGALIZATION_RESOURCE_BINDING_EVIDENCE_RE.fullmatch(evidence_id)
    if match is None:
        return

    expected_prefix = (
        f"{TARGET_LEGALIZATION_EVIDENCE_PREFIX}.{evidence['target']}.resource-binding."
    )
    if not evidence_id.startswith(expected_prefix):
        errors.append(
            f"{path}.evidenceId: expected target resource binding evidence prefix "
            f"{expected_prefix!r}, got {evidence_id!r}"
        )


def source_map_expected_anchor_count(owner, summary):
    return summary[SOURCE_MAP_SUMMARY_COUNT_FIELDS[owner]]


def validate_source_map_anchor_index(
    errors,
    path,
    evidence,
    summary,
    seen_source_map_anchors,
):
    owner = evidence["owner"]
    anchor_index = evidence["index"]
    anchor = (owner, anchor_index)
    if anchor in seen_source_map_anchors:
        errors.append(
            f"{path}: duplicate source-map evidence anchor {owner}[{anchor_index}]"
        )
    seen_source_map_anchors.add(anchor)

    expected_count = source_map_expected_anchor_count(owner, summary)
    if anchor_index >= expected_count:
        count_field = SOURCE_MAP_SUMMARY_COUNT_FIELDS[owner]
        errors.append(
            f"{path}.index: expected < $.summary.{count_field} "
            f"{expected_count!r}, got {anchor_index!r}"
        )


def validate_required_source_map_anchors(errors, source_map_anchors, summary):
    for owner in SOURCE_MAP_OWNERS:
        expected_count = source_map_expected_anchor_count(owner, summary)
        for anchor_index in range(expected_count):
            if (owner, anchor_index) not in source_map_anchors:
                errors.append(
                    "$.sourceMapEvidence: missing source-map evidence anchor "
                    f"{owner}[{anchor_index}]"
                )


def validate_source_map_anchor_location(
    errors,
    source_map_anchor_locations,
    source_map_anchor_paths,
    owner,
    anchor_index,
    expected_location,
    expected_label,
):
    anchor = (owner, anchor_index)
    if anchor not in source_map_anchor_locations:
        return
    add_source_location_equal_error(
        errors,
        f"{source_map_anchor_paths[anchor]}.location",
        source_map_anchor_locations[anchor],
        expected_location,
        expected_label,
    )


def validate_semantics(instance):
    errors = []
    validate_normalized_path(errors, "$.inputPath", instance["inputPath"])
    actual_counts = {severity: 0 for severity in SEVERITIES}
    for index, diagnostic in enumerate(instance["diagnostics"]):
        diagnostic_path = f"$.diagnostics[{index}]"
        severity = diagnostic["severity"]
        actual_counts[severity] += 1
        if not diagnostic["code"].startswith("graphics.abi."):
            errors.append(
                f"{diagnostic_path}.code: expected graphics.abi. diagnostic prefix"
            )
        validate_report_source_location(
            errors, f"{diagnostic_path}.location", diagnostic["location"]
        )
        add_equal_error(
            errors,
            f"{diagnostic_path}.location.file",
            diagnostic["location"]["file"],
            instance["inputPath"],
            "$.inputPath",
        )
        if "target" in diagnostic and diagnostic["target"] not in TARGETS:
            errors.append(f"{diagnostic_path}.target: expected known graphics target")

    source_map_anchor_locations = {}
    source_map_anchor_paths = {}
    seen_source_map_anchors = set()
    for index, evidence in enumerate(instance["sourceMapEvidence"]):
        evidence_path = f"$.sourceMapEvidence[{index}]"
        if evidence["owner"] not in SOURCE_MAP_OWNERS:
            errors.append(f"{evidence_path}.owner: expected known source-map owner")
        validate_report_source_location(
            errors, f"{evidence_path}.location", evidence["location"]
        )
        anchor = (evidence["owner"], evidence["index"])
        source_map_anchor_locations.setdefault(anchor, evidence["location"])
        source_map_anchor_paths.setdefault(anchor, evidence_path)

    for severity, count in actual_counts.items():
        add_equal_error(
            errors,
            f"$.diagnosticCounts.{severity}",
            instance["diagnosticCounts"][severity],
            count,
            f"{severity} diagnostics",
        )
    add_equal_error(
        errors,
        "$.success",
        instance["success"],
        actual_counts["error"] == 0,
        "zero error diagnostics",
    )
    if instance["success"] and instance["summary"] is None:
        errors.append("$.summary: successful reports require a summary")
    if instance["success"] and instance["summary"] is not None:
        summary = instance["summary"]
        if summary["abiRecordCount"] < summary["resourceCount"]:
            errors.append(
                "$.summary.abiRecordCount: successful reports require at "
                "least one ABI record per source resource"
            )
        add_equal_error(
            errors,
            "$.entryPointEvidence",
            len(instance["entryPointEvidence"]),
            summary["entryPointCount"],
            "$.summary.entryPointCount",
        )
        add_equal_error(
            errors,
            "$.resourceBindingEvidence",
            len(instance["resourceBindingEvidence"]),
            summary["abiRecordCount"],
            "$.summary.abiRecordCount",
        )
        expected_anchor_count = (
            summary["entryPointCount"]
            + summary["resourceCount"]
            + summary["abiRecordCount"]
        )
        add_equal_error(
            errors,
            "$.sourceMapEvidence",
            len(instance["sourceMapEvidence"]),
            expected_anchor_count,
            "entry point, source resource, and ABI record source-map anchors",
        )
        for index, evidence in enumerate(instance["sourceMapEvidence"]):
            validate_source_map_anchor_index(
                errors,
                f"$.sourceMapEvidence[{index}]",
                evidence,
                summary,
                seen_source_map_anchors,
            )
        validate_required_source_map_anchors(
            errors,
            seen_source_map_anchors,
            summary,
        )

    for index, evidence in enumerate(instance["entryPointEvidence"]):
        evidence_path = f"$.entryPointEvidence[{index}]"
        add_equal_error(
            errors,
            f"{evidence_path}.entryPointIndex",
            evidence["entryPointIndex"],
            index,
            "entry point evidence order",
        )
        validate_report_source_location(
            errors, f"{evidence_path}.sourceMapRef", evidence["sourceMapRef"]
        )
        if instance["success"] and instance["summary"] is not None:
            validate_source_map_anchor_location(
                errors,
                source_map_anchor_locations,
                source_map_anchor_paths,
                "entryPoint",
                evidence["entryPointIndex"],
                evidence["sourceMapRef"],
                f"{evidence_path}.sourceMapRef",
            )

    seen_resource_binding_evidence_ids = set()
    for index, evidence in enumerate(instance["resourceBindingEvidence"]):
        evidence_path = f"$.resourceBindingEvidence[{index}]"
        add_equal_error(
            errors,
            f"{evidence_path}.abiRecordIndex",
            evidence["abiRecordIndex"],
            index,
            "ABI record evidence order",
        )
        if instance["success"]:
            validate_resource_binding_evidence_id(
                errors,
                evidence_path,
                evidence,
                seen_resource_binding_evidence_ids,
            )
        if evidence["sourceMapRef"] is None:
            if instance["success"]:
                errors.append(
                    f"{evidence_path}.sourceMapRef: successful reports require "
                    "linked source resource evidence"
                )
        else:
            validate_report_source_location(
                errors, f"{evidence_path}.sourceMapRef", evidence["sourceMapRef"]
            )
        validate_report_source_location(
            errors, f"{evidence_path}.abiSourceMapRef", evidence["abiSourceMapRef"]
        )
        if instance["success"] and instance["summary"] is not None:
            summary = instance["summary"]
            if evidence["entryPointIndex"] is None:
                errors.append(
                    f"{evidence_path}.entryPointIndex: successful reports require "
                    "linked entry point evidence"
                )
            elif evidence["entryPointIndex"] >= summary["entryPointCount"]:
                errors.append(
                    f"{evidence_path}.entryPointIndex: expected < "
                    f"$.summary.entryPointCount {summary['entryPointCount']!r}, "
                    f"got {evidence['entryPointIndex']!r}"
                )

            if evidence["sourceResourceIndex"] is None:
                errors.append(
                    f"{evidence_path}.sourceResourceIndex: successful reports "
                    "require linked source resource evidence"
                )
            elif evidence["sourceResourceIndex"] >= summary["resourceCount"]:
                errors.append(
                    f"{evidence_path}.sourceResourceIndex: expected < "
                    f"$.summary.resourceCount {summary['resourceCount']!r}, "
                    f"got {evidence['sourceResourceIndex']!r}"
                )
            elif evidence["sourceMapRef"] is not None:
                validate_source_map_anchor_location(
                    errors,
                    source_map_anchor_locations,
                    source_map_anchor_paths,
                    "resource",
                    evidence["sourceResourceIndex"],
                    evidence["sourceMapRef"],
                    f"{evidence_path}.sourceMapRef",
                )

            validate_source_map_anchor_location(
                errors,
                source_map_anchor_locations,
                source_map_anchor_paths,
                "abiRecord",
                evidence["abiRecordIndex"],
                evidence["abiSourceMapRef"],
                f"{evidence_path}.abiSourceMapRef",
            )
    return errors
