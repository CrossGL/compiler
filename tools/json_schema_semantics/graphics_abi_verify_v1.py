"""Semantic checks for graphics-abi-verify-v1.schema.json."""

import re

from .common import add_equal_error
from .common import validate_source_location_span


SEVERITIES = ("note", "warning", "error")
TARGETS = ("metal", "vulkan", "directx", "opengl")
SOURCE_MAP_OWNERS = ("entryPoint", "resource", "abiRecord")
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

    for index, evidence in enumerate(instance["sourceMapEvidence"]):
        evidence_path = f"$.sourceMapEvidence[{index}]"
        if evidence["owner"] not in SOURCE_MAP_OWNERS:
            errors.append(f"{evidence_path}.owner: expected known source-map owner")
        validate_report_source_location(
            errors, f"{evidence_path}.location", evidence["location"]
        )
    return errors
