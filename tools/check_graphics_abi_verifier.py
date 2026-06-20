#!/usr/bin/env python3
"""Check standalone graphics ABI verifier fixtures and report contracts."""

import argparse
import copy
import json
import subprocess
import sys
import tempfile
from pathlib import Path


EXPECTED_INVALID_CODES = [
    "graphics.abi.target-mismatch",
    "graphics.abi.abi-kind-mismatch",
    "graphics.abi.stage-mismatch",
    "graphics.abi.source-resource-missing",
    "graphics.abi.duplicate-record",
    "graphics.abi.duplicate-coordinate",
    "graphics.abi.unbound-resource",
]

BINDING_IDENTITY_CODES = [
    "graphics.abi.source-binding-mismatch",
]


def run_verifier(root, fixture):
    return subprocess.run(
        [
            sys.executable,
            str(root / "tools" / "verify_graphics_abi.py"),
            "--input",
            str(fixture),
            "--json",
        ],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )


def validate_report_schema(root, tmp_dir, case_name, report_json):
    instance_path = tmp_dir / f"{case_name}.graphics-abi-verify.json"
    instance_path.write_text(report_json, encoding="utf-8")
    result = subprocess.run(
        [
            sys.executable,
            str(root / "tools" / "validate_json_schema.py"),
            "--schema",
            str(root / "docs" / "schemas" / "graphics-abi-verify-v1.schema.json"),
            "--instance",
            str(instance_path),
        ],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if result.returncode != 0:
        return [
            f"{case_name}: report JSON failed schema validation: "
            f"{result.stderr}{result.stdout}".strip()
        ]
    return []


def expect_report_schema_failure(root, tmp_dir, case_name, report):
    instance_path = tmp_dir / f"{case_name}.graphics-abi-verify.json"
    instance_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    result = subprocess.run(
        [
            sys.executable,
            str(root / "tools" / "validate_json_schema.py"),
            "--schema",
            str(root / "docs" / "schemas" / "graphics-abi-verify-v1.schema.json"),
            "--instance",
            str(instance_path),
        ],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if result.returncode == 0:
        return [f"{case_name}: expected report schema validation failure"]
    return []


def expect_counts(errors, case_name, report):
    actual = {"note": 0, "warning": 0, "error": 0}
    for index, diagnostic in enumerate(report.get("diagnostics", [])):
        severity = diagnostic.get("severity")
        if severity not in actual:
            errors.append(
                f"{case_name}: diagnostics[{index}].severity has "
                f"unexpected value {severity!r}"
            )
            continue
        actual[severity] += 1
        code = diagnostic.get("code")
        if not isinstance(code, str) or not code.startswith("graphics.abi."):
            errors.append(
                f"{case_name}: diagnostics[{index}].code has unexpected value {code!r}"
            )

    if report.get("diagnosticCounts") != actual:
        errors.append(
            f"{case_name}: expected diagnosticCounts {actual!r}, "
            f"got {report.get('diagnosticCounts')!r}"
        )
    if report.get("success") != (actual["error"] == 0):
        errors.append(
            f"{case_name}: success does not match error count {actual['error']}"
        )


def check_success(root, tmp_dir):
    fixture = root / "tests" / "graphics-abi" / "valid-minimal.json"
    result = run_verifier(root, fixture)
    errors = []
    if result.returncode != 0:
        return [
            "valid-minimal: expected verifier success, got "
            f"{result.stderr}{result.stdout}".strip()
        ]
    try:
        report = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        return [f"valid-minimal: verifier output is not JSON: {exc}"]

    errors.extend(validate_report_schema(root, tmp_dir, "valid-minimal", result.stdout))
    expect_counts(errors, "valid-minimal", report)
    if report.get("summary") != {
        "module": "GraphicsAbiFixture",
        "target": "vulkan",
        "entryPointCount": 2,
        "vertexInputCount": 1,
        "varyingCount": 1,
        "fragmentOutputCount": 1,
        "builtinCount": 2,
        "resourceCount": 2,
        "abiRecordCount": 2,
    }:
        errors.append(f"valid-minimal: unexpected summary {report.get('summary')!r}")
    if report.get("diagnostics") != []:
        errors.append(
            f"valid-minimal: expected no diagnostics, got {report.get('diagnostics')!r}"
        )
    expected_evidence_ids = [
        "target-legalization.v1.vulkan.resource-binding.vertex.vertex_vs_main.Camera",
        "target-legalization.v1.vulkan.resource-binding.fragment.fragment_fs_main.albedo",
    ]
    try:
        fixture_document = json.loads(fixture.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return [f"valid-minimal: failed to load fixture for evidence check: {exc}"]
    abi_record_evidence_ids = [
        record.get("evidenceId") for record in fixture_document.get("abiRecords", [])
    ]
    if abi_record_evidence_ids != expected_evidence_ids:
        errors.append(
            "valid-minimal: unexpected ABI record evidence IDs "
            f"{abi_record_evidence_ids!r}"
        )
    if len(report.get("entryPointEvidence", [])) != 2:
        errors.append("valid-minimal: expected 2 entry point evidence rows")
    resource_binding_evidence = report.get("resourceBindingEvidence", [])
    if len(resource_binding_evidence) != 2:
        errors.append("valid-minimal: expected 2 resource binding evidence rows")
    report_evidence_ids = [row.get("evidenceId") for row in resource_binding_evidence]
    if report_evidence_ids != expected_evidence_ids:
        errors.append(
            "valid-minimal: unexpected verifier resource binding evidence IDs "
            f"{report_evidence_ids!r}"
        )
    if len(report.get("sourceMapEvidence", [])) != 6:
        errors.append("valid-minimal: expected 6 source-map evidence rows")
    return errors


def check_evidence_target_mismatch(root, tmp_dir):
    valid_fixture = root / "tests" / "graphics-abi" / "valid-minimal.json"
    fixture = tmp_dir / "invalid-evidence-target-mismatch.json"
    document = json.loads(valid_fixture.read_text(encoding="utf-8"))
    document["module"] = "GraphicsAbiEvidenceTargetMismatch"
    document["abiRecords"][0]["evidenceId"] = (
        "target-legalization.v1.directx.resource-binding.vertex.vertex_vs_main.Camera"
    )
    fixture.write_text(json.dumps(document, indent=2), encoding="utf-8")

    result = run_verifier(root, fixture)
    errors = []
    if result.returncode == 0:
        errors.append("invalid-evidence-target-mismatch: expected verifier failure")
    try:
        report = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        return [f"invalid-evidence-target-mismatch: verifier output is not JSON: {exc}"]

    errors.extend(
        validate_report_schema(
            root, tmp_dir, "invalid-evidence-target-mismatch", result.stdout
        )
    )
    expect_counts(errors, "invalid-evidence-target-mismatch", report)
    codes = [diagnostic.get("code") for diagnostic in report.get("diagnostics", [])]
    expected_codes = ["graphics.abi.evidence-target-mismatch"]
    if codes != expected_codes:
        errors.append(
            "invalid-evidence-target-mismatch: expected diagnostic codes "
            f"{expected_codes!r}, got {codes!r}"
        )
    if report.get("summary") != {
        "module": "GraphicsAbiEvidenceTargetMismatch",
        "target": "vulkan",
        "entryPointCount": 2,
        "vertexInputCount": 1,
        "varyingCount": 1,
        "fragmentOutputCount": 1,
        "builtinCount": 2,
        "resourceCount": 2,
        "abiRecordCount": 2,
    }:
        errors.append(
            "invalid-evidence-target-mismatch: unexpected summary "
            f"{report.get('summary')!r}"
        )
    return errors


def check_missing_source_map_ref(root, tmp_dir):
    fixture = root / "tests" / "graphics-abi" / "invalid-missing-source-map-ref.json"
    result = run_verifier(root, fixture)
    errors = []
    if result.returncode == 0:
        errors.append("invalid-missing-source-map-ref: expected verifier failure")
    try:
        report = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        return [f"invalid-missing-source-map-ref: verifier output is not JSON: {exc}"]

    errors.extend(
        validate_report_schema(
            root, tmp_dir, "invalid-missing-source-map-ref", result.stdout
        )
    )
    expect_counts(errors, "invalid-missing-source-map-ref", report)
    codes = [diagnostic.get("code") for diagnostic in report.get("diagnostics", [])]
    expected_codes = ["graphics.abi.schema"]
    if codes != expected_codes:
        errors.append(
            "invalid-missing-source-map-ref: expected diagnostic codes "
            f"{expected_codes!r}, got {codes!r}"
        )
    return errors


def check_entry_point_backend_name_mismatch(root, tmp_dir):
    fixture = root / "tests" / "graphics-abi" / "invalid-entry-point-backend-name.json"
    result = run_verifier(root, fixture)
    errors = []
    if result.returncode == 0:
        errors.append("invalid-entry-point-backend-name: expected verifier failure")
    try:
        report = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        return [f"invalid-entry-point-backend-name: verifier output is not JSON: {exc}"]

    errors.extend(
        validate_report_schema(
            root, tmp_dir, "invalid-entry-point-backend-name", result.stdout
        )
    )
    expect_counts(errors, "invalid-entry-point-backend-name", report)
    codes = [diagnostic.get("code") for diagnostic in report.get("diagnostics", [])]
    expected_codes = ["graphics.abi.entry-point-backend-name-mismatch"]
    if codes != expected_codes:
        errors.append(
            "invalid-entry-point-backend-name: expected diagnostic codes "
            f"{expected_codes!r}, got {codes!r}"
        )
    if report.get("summary") != {
        "module": "GraphicsAbiEntryPointBackendNameMismatch",
        "target": "vulkan",
        "entryPointCount": 1,
        "vertexInputCount": 0,
        "varyingCount": 0,
        "fragmentOutputCount": 0,
        "builtinCount": 0,
        "resourceCount": 0,
        "abiRecordCount": 0,
    }:
        errors.append(
            "invalid-entry-point-backend-name: unexpected summary "
            f"{report.get('summary')!r}"
        )
    return errors


def check_failure(root, tmp_dir):
    fixture = root / "tests" / "graphics-abi" / "invalid-malformed-records.json"
    result = run_verifier(root, fixture)
    errors = []
    if result.returncode == 0:
        errors.append("invalid-malformed-records: expected verifier failure")
    try:
        report = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        return [f"invalid-malformed-records: verifier output is not JSON: {exc}"]

    errors.extend(
        validate_report_schema(
            root, tmp_dir, "invalid-malformed-records", result.stdout
        )
    )
    expect_counts(errors, "invalid-malformed-records", report)
    codes = [diagnostic.get("code") for diagnostic in report.get("diagnostics", [])]
    if codes != EXPECTED_INVALID_CODES:
        errors.append(
            "invalid-malformed-records: expected diagnostic codes "
            f"{EXPECTED_INVALID_CODES!r}, got {codes!r}"
        )
    if report.get("summary") != {
        "module": "GraphicsAbiBrokenFixture",
        "target": "vulkan",
        "entryPointCount": 1,
        "vertexInputCount": 0,
        "varyingCount": 0,
        "fragmentOutputCount": 0,
        "builtinCount": 0,
        "resourceCount": 2,
        "abiRecordCount": 3,
    }:
        errors.append(
            f"invalid-malformed-records: unexpected summary {report.get('summary')!r}"
        )
    return errors


def check_source_binding_mismatch(root, tmp_dir):
    fixture = root / "tests" / "graphics-abi" / "invalid-source-binding-mismatch.json"
    result = run_verifier(root, fixture)
    errors = []
    if result.returncode == 0:
        errors.append("invalid-source-binding-mismatch: expected verifier failure")
    try:
        report = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        return [f"invalid-source-binding-mismatch: verifier output is not JSON: {exc}"]

    errors.extend(
        validate_report_schema(
            root, tmp_dir, "invalid-source-binding-mismatch", result.stdout
        )
    )
    expect_counts(errors, "invalid-source-binding-mismatch", report)
    codes = [diagnostic.get("code") for diagnostic in report.get("diagnostics", [])]
    expected_codes = ["graphics.abi.source-binding-mismatch"]
    if codes != expected_codes:
        errors.append(
            "invalid-source-binding-mismatch: expected diagnostic codes "
            f"{expected_codes!r}, got {codes!r}"
        )
    if report.get("summary") != {
        "module": "GraphicsAbiSourceBindingMismatchFixture",
        "target": "vulkan",
        "entryPointCount": 1,
        "vertexInputCount": 0,
        "varyingCount": 0,
        "fragmentOutputCount": 0,
        "builtinCount": 0,
        "resourceCount": 1,
        "abiRecordCount": 1,
    }:
        errors.append(
            "invalid-source-binding-mismatch: unexpected summary "
            f"{report.get('summary')!r}"
        )
    return errors


def check_binding_identity_failure(root, tmp_dir):
    fixture = root / "tests" / "graphics-abi" / "invalid-binding-identity.json"
    result = run_verifier(root, fixture)
    errors = []
    if result.returncode == 0:
        errors.append("invalid-binding-identity: expected verifier failure")
    try:
        report = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        return [f"invalid-binding-identity: verifier output is not JSON: {exc}"]

    errors.extend(
        validate_report_schema(root, tmp_dir, "invalid-binding-identity", result.stdout)
    )
    expect_counts(errors, "invalid-binding-identity", report)
    codes = [diagnostic.get("code") for diagnostic in report.get("diagnostics", [])]
    if codes != BINDING_IDENTITY_CODES:
        errors.append(
            "invalid-binding-identity: expected diagnostic codes "
            f"{BINDING_IDENTITY_CODES!r}, got {codes!r}"
        )
    if report.get("summary") != {
        "module": "GraphicsAbiBindingIdentityBroken",
        "target": "vulkan",
        "entryPointCount": 1,
        "vertexInputCount": 0,
        "varyingCount": 0,
        "fragmentOutputCount": 0,
        "builtinCount": 0,
        "resourceCount": 1,
        "abiRecordCount": 1,
    }:
        errors.append(
            f"invalid-binding-identity: unexpected summary {report.get('summary')!r}"
        )
    return errors


def check_resource_order_mismatch(root, tmp_dir):
    fixture = root / "tests" / "graphics-abi" / "invalid-resource-order.json"
    result = run_verifier(root, fixture)
    errors = []
    if result.returncode == 0:
        errors.append("invalid-resource-order: expected verifier failure")
    try:
        report = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        return [f"invalid-resource-order: verifier output is not JSON: {exc}"]

    errors.extend(
        validate_report_schema(root, tmp_dir, "invalid-resource-order", result.stdout)
    )
    expect_counts(errors, "invalid-resource-order", report)
    codes = [diagnostic.get("code") for diagnostic in report.get("diagnostics", [])]
    expected_codes = ["graphics.abi.resource-order-mismatch"]
    if codes != expected_codes:
        errors.append(
            "invalid-resource-order: expected diagnostic codes "
            f"{expected_codes!r}, got {codes!r}"
        )
    if report.get("summary") != {
        "module": "GraphicsAbiResourceOrderFixture",
        "target": "vulkan",
        "entryPointCount": 2,
        "vertexInputCount": 0,
        "varyingCount": 0,
        "fragmentOutputCount": 0,
        "builtinCount": 0,
        "resourceCount": 2,
        "abiRecordCount": 2,
    }:
        errors.append(
            f"invalid-resource-order: unexpected summary {report.get('summary')!r}"
        )
    return errors


def check_descriptor_type_mismatch(root, tmp_dir):
    fixture = root / "tests" / "graphics-abi" / "invalid-descriptor-type-mismatch.json"
    result = run_verifier(root, fixture)
    errors = []
    if result.returncode == 0:
        errors.append("invalid-descriptor-type-mismatch: expected verifier failure")
    try:
        report = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        return [f"invalid-descriptor-type-mismatch: verifier output is not JSON: {exc}"]

    errors.extend(
        validate_report_schema(
            root, tmp_dir, "invalid-descriptor-type-mismatch", result.stdout
        )
    )
    expect_counts(errors, "invalid-descriptor-type-mismatch", report)
    codes = [diagnostic.get("code") for diagnostic in report.get("diagnostics", [])]
    expected_codes = [
        "graphics.abi.descriptor-type-mismatch",
        "graphics.abi.binding-class-mismatch",
    ]
    if codes != expected_codes:
        errors.append(
            "invalid-descriptor-type-mismatch: expected diagnostic codes "
            f"{expected_codes!r}, got {codes!r}"
        )
    if report.get("summary") != {
        "module": "GraphicsAbiDescriptorTypeMismatchFixture",
        "target": "vulkan",
        "entryPointCount": 1,
        "vertexInputCount": 0,
        "varyingCount": 0,
        "fragmentOutputCount": 0,
        "builtinCount": 0,
        "resourceCount": 1,
        "abiRecordCount": 1,
    }:
        errors.append(
            "invalid-descriptor-type-mismatch: unexpected summary "
            f"{report.get('summary')!r}"
        )
    return errors


def check_source_array_element_count_mismatch(root, tmp_dir):
    fixture = (
        root
        / "tests"
        / "graphics-abi"
        / "invalid-source-array-element-count-mismatch.json"
    )
    result = run_verifier(root, fixture)
    errors = []
    if result.returncode == 0:
        errors.append(
            "invalid-source-array-element-count-mismatch: expected verifier failure"
        )
    try:
        report = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        return [
            "invalid-source-array-element-count-mismatch: verifier output is not "
            f"JSON: {exc}"
        ]

    errors.extend(
        validate_report_schema(
            root,
            tmp_dir,
            "invalid-source-array-element-count-mismatch",
            result.stdout,
        )
    )
    expect_counts(errors, "invalid-source-array-element-count-mismatch", report)
    codes = [diagnostic.get("code") for diagnostic in report.get("diagnostics", [])]
    expected_codes = ["graphics.abi.source-array-element-count-mismatch"]
    if codes != expected_codes:
        errors.append(
            "invalid-source-array-element-count-mismatch: expected diagnostic codes "
            f"{expected_codes!r}, got {codes!r}"
        )
    if report.get("summary") != {
        "module": "GraphicsAbiSourceArrayElementCountMismatch",
        "target": "vulkan",
        "entryPointCount": 1,
        "vertexInputCount": 0,
        "varyingCount": 0,
        "fragmentOutputCount": 0,
        "builtinCount": 0,
        "resourceCount": 1,
        "abiRecordCount": 1,
    }:
        errors.append(
            "invalid-source-array-element-count-mismatch: unexpected summary "
            f"{report.get('summary')!r}"
        )
    return errors


def check_source_array_element_count_value_mismatch(root, tmp_dir):
    fixture = (
        root
        / "tests"
        / "graphics-abi"
        / "invalid-source-array-element-count-value-mismatch.json"
    )
    result = run_verifier(root, fixture)
    errors = []
    if result.returncode == 0:
        errors.append(
            "invalid-source-array-element-count-value-mismatch: expected verifier "
            "failure"
        )
    try:
        report = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        return [
            "invalid-source-array-element-count-value-mismatch: verifier output is "
            f"not JSON: {exc}"
        ]

    errors.extend(
        validate_report_schema(
            root,
            tmp_dir,
            "invalid-source-array-element-count-value-mismatch",
            result.stdout,
        )
    )
    expect_counts(errors, "invalid-source-array-element-count-value-mismatch", report)
    codes = [diagnostic.get("code") for diagnostic in report.get("diagnostics", [])]
    expected_codes = ["graphics.abi.source-array-element-count-mismatch"]
    if codes != expected_codes:
        errors.append(
            "invalid-source-array-element-count-value-mismatch: expected diagnostic "
            f"codes {expected_codes!r}, got {codes!r}"
        )
    if report.get("summary") != {
        "module": "GraphicsAbiSourceArrayElementCountValueMismatch",
        "target": "vulkan",
        "entryPointCount": 1,
        "vertexInputCount": 0,
        "varyingCount": 0,
        "fragmentOutputCount": 0,
        "builtinCount": 0,
        "resourceCount": 1,
        "abiRecordCount": 1,
    }:
        errors.append(
            "invalid-source-array-element-count-value-mismatch: unexpected summary "
            f"{report.get('summary')!r}"
        )
    return errors


def check_descriptor_metadata_fixture(
    root, tmp_dir, case_name, expected_codes, expected_summary
):
    fixture = root / "tests" / "graphics-abi" / f"{case_name}.json"
    result = run_verifier(root, fixture)
    errors = []
    if result.returncode == 0:
        errors.append(f"{case_name}: expected verifier failure")
    try:
        report = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        return [f"{case_name}: verifier output is not JSON: {exc}"]

    errors.extend(validate_report_schema(root, tmp_dir, case_name, result.stdout))
    expect_counts(errors, case_name, report)
    codes = [diagnostic.get("code") for diagnostic in report.get("diagnostics", [])]
    if codes != expected_codes:
        errors.append(
            f"{case_name}: expected diagnostic codes {expected_codes!r}, got {codes!r}"
        )
    if report.get("summary") != expected_summary:
        errors.append(f"{case_name}: unexpected summary {report.get('summary')!r}")
    return errors


def check_directx_descriptor_metadata_mismatch(root, tmp_dir):
    return check_descriptor_metadata_fixture(
        root,
        tmp_dir,
        "invalid-directx-descriptor-metadata",
        [
            "graphics.abi.descriptor-type-mismatch",
            "graphics.abi.binding-class-mismatch",
        ],
        {
            "module": "GraphicsAbiDirectXDescriptorMetadataMismatch",
            "target": "directx",
            "entryPointCount": 1,
            "vertexInputCount": 0,
            "varyingCount": 0,
            "fragmentOutputCount": 0,
            "builtinCount": 0,
            "resourceCount": 1,
            "abiRecordCount": 1,
        },
    )


def check_metal_binding_class_mismatch(root, tmp_dir):
    return check_descriptor_metadata_fixture(
        root,
        tmp_dir,
        "invalid-metal-binding-class",
        ["graphics.abi.binding-class-mismatch"],
        {
            "module": "GraphicsAbiMetalBindingClassMismatch",
            "target": "metal",
            "entryPointCount": 1,
            "vertexInputCount": 0,
            "varyingCount": 0,
            "fragmentOutputCount": 0,
            "builtinCount": 0,
            "resourceCount": 1,
            "abiRecordCount": 1,
        },
    )


def check_opengl_binding_class_mismatch(root, tmp_dir):
    return check_descriptor_metadata_fixture(
        root,
        tmp_dir,
        "invalid-opengl-binding-class",
        ["graphics.abi.binding-class-mismatch"],
        {
            "module": "GraphicsAbiOpenGLBindingClassMismatch",
            "target": "opengl",
            "entryPointCount": 1,
            "vertexInputCount": 0,
            "varyingCount": 0,
            "fragmentOutputCount": 0,
            "builtinCount": 0,
            "resourceCount": 1,
            "abiRecordCount": 1,
        },
    )


def check_duplicate_source_coordinate(root, tmp_dir):
    fixture = root / "tests" / "graphics-abi" / "invalid-source-coordinate.json"
    result = run_verifier(root, fixture)
    errors = []
    if result.returncode == 0:
        errors.append("invalid-source-coordinate: expected verifier failure")
    try:
        report = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        return [f"invalid-source-coordinate: verifier output is not JSON: {exc}"]

    errors.extend(
        validate_report_schema(
            root, tmp_dir, "invalid-source-coordinate", result.stdout
        )
    )
    expect_counts(errors, "invalid-source-coordinate", report)
    codes = [diagnostic.get("code") for diagnostic in report.get("diagnostics", [])]
    expected_codes = ["graphics.abi.duplicate-source-coordinate"]
    if codes != expected_codes:
        errors.append(
            "invalid-source-coordinate: expected diagnostic codes "
            f"{expected_codes!r}, got {codes!r}"
        )
    if report.get("summary") != {
        "module": "GraphicsAbiDuplicateSourceCoordinateFixture",
        "target": "metal",
        "entryPointCount": 1,
        "vertexInputCount": 0,
        "varyingCount": 0,
        "fragmentOutputCount": 0,
        "builtinCount": 0,
        "resourceCount": 2,
        "abiRecordCount": 2,
    }:
        errors.append(
            f"invalid-source-coordinate: unexpected summary {report.get('summary')!r}"
        )
    return errors


def check_varying_producer_consumer_mismatch(root, tmp_dir):
    fixture = root / "tests" / "graphics-abi" / "invalid-varying-producer-consumer.json"
    result = run_verifier(root, fixture)
    errors = []
    if result.returncode == 0:
        errors.append("invalid-varying-producer-consumer: expected verifier failure")
    try:
        report = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        return [
            f"invalid-varying-producer-consumer: verifier output is not JSON: {exc}"
        ]

    errors.extend(
        validate_report_schema(
            root, tmp_dir, "invalid-varying-producer-consumer", result.stdout
        )
    )
    expect_counts(errors, "invalid-varying-producer-consumer", report)
    codes = [diagnostic.get("code") for diagnostic in report.get("diagnostics", [])]
    expected_codes = ["graphics.abi.varying-producer-consumer-mismatch"]
    if codes != expected_codes:
        errors.append(
            "invalid-varying-producer-consumer: expected diagnostic codes "
            f"{expected_codes!r}, got {codes!r}"
        )
    if report.get("summary") != {
        "module": "GraphicsAbiVaryingMismatchFixture",
        "target": "vulkan",
        "entryPointCount": 2,
        "vertexInputCount": 0,
        "varyingCount": 1,
        "fragmentOutputCount": 0,
        "builtinCount": 0,
        "resourceCount": 0,
        "abiRecordCount": 0,
    }:
        errors.append(
            "invalid-varying-producer-consumer: unexpected summary "
            f"{report.get('summary')!r}"
        )
    return errors


def check_interface_record_failures(root, tmp_dir):
    fixture = root / "tests" / "graphics-abi" / "invalid-interface-records.json"
    result = run_verifier(root, fixture)
    errors = []
    if result.returncode == 0:
        errors.append("invalid-interface-records: expected verifier failure")
    try:
        report = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        return [f"invalid-interface-records: verifier output is not JSON: {exc}"]

    errors.extend(
        validate_report_schema(
            root, tmp_dir, "invalid-interface-records", result.stdout
        )
    )
    expect_counts(errors, "invalid-interface-records", report)
    codes = [diagnostic.get("code") for diagnostic in report.get("diagnostics", [])]
    expected_codes = [
        "graphics.abi.duplicate-vertex-input-location",
        "graphics.abi.duplicate-fragment-output-location",
        "graphics.abi.duplicate-builtin",
    ]
    if codes != expected_codes:
        errors.append(
            "invalid-interface-records: expected diagnostic codes "
            f"{expected_codes!r}, got {codes!r}"
        )
    if report.get("summary") != {
        "module": "GraphicsAbiInterfaceRecordsFixture",
        "target": "vulkan",
        "entryPointCount": 2,
        "vertexInputCount": 2,
        "varyingCount": 0,
        "fragmentOutputCount": 2,
        "builtinCount": 2,
        "resourceCount": 0,
        "abiRecordCount": 0,
    }:
        errors.append(
            f"invalid-interface-records: unexpected summary {report.get('summary')!r}"
        )
    return errors


def check_builtin_contract_failure(root, tmp_dir):
    fixture = root / "tests" / "graphics-abi" / "invalid-builtin-contract.json"
    result = run_verifier(root, fixture)
    errors = []
    if result.returncode == 0:
        errors.append("invalid-builtin-contract: expected verifier failure")
    try:
        report = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        return [f"invalid-builtin-contract: verifier output is not JSON: {exc}"]

    errors.extend(
        validate_report_schema(root, tmp_dir, "invalid-builtin-contract", result.stdout)
    )
    expect_counts(errors, "invalid-builtin-contract", report)
    codes = [diagnostic.get("code") for diagnostic in report.get("diagnostics", [])]
    expected_codes = ["graphics.abi.builtin-contract-mismatch"]
    if codes != expected_codes:
        errors.append(
            "invalid-builtin-contract: expected diagnostic codes "
            f"{expected_codes!r}, got {codes!r}"
        )
    if report.get("summary") != {
        "module": "GraphicsAbiBuiltinContractFixture",
        "target": "vulkan",
        "entryPointCount": 1,
        "vertexInputCount": 0,
        "varyingCount": 0,
        "fragmentOutputCount": 0,
        "builtinCount": 1,
        "resourceCount": 0,
        "abiRecordCount": 0,
    }:
        errors.append(
            f"invalid-builtin-contract: unexpected summary {report.get('summary')!r}"
        )
    return errors


def check_report_schema_semantics(root, tmp_dir):
    valid_fixture = root / "tests" / "graphics-abi" / "valid-minimal.json"
    invalid_fixture = (
        root / "tests" / "graphics-abi" / "invalid-source-binding-mismatch.json"
    )
    valid_result = run_verifier(root, valid_fixture)
    invalid_result = run_verifier(root, invalid_fixture)
    errors = []
    try:
        valid_report = json.loads(valid_result.stdout)
        invalid_report = json.loads(invalid_result.stdout)
    except json.JSONDecodeError as exc:
        return [f"report schema semantics: verifier output is not JSON: {exc}"]

    bad_input_path = copy.deepcopy(valid_report)
    bad_input_path["inputPath"] = "tests\\graphics-abi\\valid-minimal.json"
    errors.extend(
        expect_report_schema_failure(
            root, tmp_dir, "report-unnormalized-input-path", bad_input_path
        )
    )

    bad_location_file = copy.deepcopy(invalid_report)
    bad_location_file["diagnostics"][0]["location"]["file"] = "other.json"
    errors.extend(
        expect_report_schema_failure(
            root, tmp_dir, "report-location-file-mismatch", bad_location_file
        )
    )

    bad_target = copy.deepcopy(invalid_report)
    bad_target["diagnostics"][0]["target"] = "unknown"
    errors.extend(
        expect_report_schema_failure(root, tmp_dir, "report-unknown-target", bad_target)
    )

    missing_entry_point_evidence = copy.deepcopy(valid_report)
    del missing_entry_point_evidence["entryPointEvidence"]
    errors.extend(
        expect_report_schema_failure(
            root,
            tmp_dir,
            "report-missing-entry-point-evidence",
            missing_entry_point_evidence,
        )
    )

    missing_resource_binding_evidence = copy.deepcopy(valid_report)
    del missing_resource_binding_evidence["resourceBindingEvidence"]
    errors.extend(
        expect_report_schema_failure(
            root,
            tmp_dir,
            "report-missing-resource-binding-evidence",
            missing_resource_binding_evidence,
        )
    )

    missing_source_map_evidence = copy.deepcopy(valid_report)
    missing_source_map_evidence["sourceMapEvidence"] = missing_source_map_evidence[
        "sourceMapEvidence"
    ][:-1]
    errors.extend(
        expect_report_schema_failure(
            root,
            tmp_dir,
            "report-source-map-evidence-count-mismatch",
            missing_source_map_evidence,
        )
    )
    bad_resource_binding_evidence_target = copy.deepcopy(valid_report)
    bad_resource_binding_evidence_target["resourceBindingEvidence"][0]["evidenceId"] = (
        "target-legalization.v1.directx.resource-binding.vertex.vertex_vs_main.Camera"
    )
    errors.extend(
        expect_report_schema_failure(
            root,
            tmp_dir,
            "report-resource-binding-evidence-target-mismatch",
            bad_resource_binding_evidence_target,
        )
    )

    duplicate_resource_binding_evidence = copy.deepcopy(valid_report)
    duplicate_resource_binding_evidence["resourceBindingEvidence"][1]["evidenceId"] = (
        duplicate_resource_binding_evidence["resourceBindingEvidence"][0]["evidenceId"]
    )
    errors.extend(
        expect_report_schema_failure(
            root,
            tmp_dir,
            "report-duplicate-resource-binding-evidence",
            duplicate_resource_binding_evidence,
        )
    )
    return errors


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=".", help="CrossGL-Compiler repository root")
    args = parser.parse_args()

    root = Path(args.root).resolve()
    errors = []
    with tempfile.TemporaryDirectory() as tmp:
        tmp_dir = Path(tmp)
        errors.extend(check_success(root, tmp_dir))
        errors.extend(check_evidence_target_mismatch(root, tmp_dir))
        errors.extend(check_missing_source_map_ref(root, tmp_dir))
        errors.extend(check_entry_point_backend_name_mismatch(root, tmp_dir))
        errors.extend(check_failure(root, tmp_dir))
        errors.extend(check_source_binding_mismatch(root, tmp_dir))
        errors.extend(check_binding_identity_failure(root, tmp_dir))
        errors.extend(check_resource_order_mismatch(root, tmp_dir))
        errors.extend(check_descriptor_type_mismatch(root, tmp_dir))
        errors.extend(check_source_array_element_count_mismatch(root, tmp_dir))
        errors.extend(check_source_array_element_count_value_mismatch(root, tmp_dir))
        errors.extend(check_directx_descriptor_metadata_mismatch(root, tmp_dir))
        errors.extend(check_metal_binding_class_mismatch(root, tmp_dir))
        errors.extend(check_opengl_binding_class_mismatch(root, tmp_dir))
        errors.extend(check_duplicate_source_coordinate(root, tmp_dir))
        errors.extend(check_varying_producer_consumer_mismatch(root, tmp_dir))
        errors.extend(check_interface_record_failures(root, tmp_dir))
        errors.extend(check_builtin_contract_failure(root, tmp_dir))
        errors.extend(check_report_schema_semantics(root, tmp_dir))

    if errors:
        for error in errors:
            print(
                f"graphics ABI verifier fixture check failed: {error}", file=sys.stderr
            )
        return 1

    print("validated 18 graphics ABI verifier cases and report semantics")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
