#!/usr/bin/env python3
"""Check doctor target summaries against explain-targets and legalization records.

This is a report-only guard. It validates committed fixtures that carry the
three consumer views involved in the doctor target summary contract:

* `doctor --json` output
* `explain-targets` output
* target legalization contract projection records

The checker intentionally does not run the compiler or define new production
fields. It proves that doctor remains an embedding consumer of target
explanation, and that the target explanation fields still line up with the
legalization projection fields used by package-mode, support-state,
optional-native-tool, and diagnostic/evidence consumers.
"""

from __future__ import annotations

import argparse
import copy
import json
import sys
from pathlib import Path
from typing import Any, Callable

from json_schema_semantics import doctor_v1
from json_schema_semantics import target_explanation_v1


FIXTURE_ROOT = Path("tests/target-explanation-doctor-alignment/valid")
REQUIRED_VALID_FIXTURES = {"package-mode-support-optional-diagnostic.json"}
REQUIRED_PACKAGE_MODES = {"native", "source-package", "unsupported"}


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def expect_object(value: Any, path: str, errors: list[str]) -> dict[str, Any]:
    if not isinstance(value, dict):
        errors.append(f"{path}: expected object")
        return {}
    return value


def expect_list(value: Any, path: str, errors: list[str]) -> list[Any]:
    if not isinstance(value, list):
        errors.append(f"{path}: expected array")
        return []
    return value


def string_list(value: Any, path: str, errors: list[str]) -> list[str]:
    values = expect_list(value, path, errors)
    result: list[str] = []
    for index, item in enumerate(values):
        if not isinstance(item, str):
            errors.append(f"{path}[{index}]: expected string")
            continue
        result.append(item)
    return result


def prefix_errors(prefix: str, messages: list[str]) -> list[str]:
    return [f"{prefix}: {message}" for message in messages]


def projection_support_status(projection: dict[str, Any]) -> str:
    if not projection.get("supportsPackage"):
        return "unsupported"
    if projection.get("packageMode") == "native":
        return "native"
    if projection.get("packageMode") == "source-package":
        return "source-package"
    return "unsupported"


def projection_state(projection: dict[str, Any]) -> str:
    return "legalized" if projection.get("supportsPackage") else "rejected"


def records_by_target(
    targets: list[Any], path: str, errors: list[str]
) -> dict[str, dict[str, Any]]:
    records: dict[str, dict[str, Any]] = {}
    for index, value in enumerate(targets):
        record_path = f"{path}[{index}]"
        record = expect_object(value, record_path, errors)
        target = record.get("target")
        if not isinstance(target, str) or not target:
            errors.append(f"{record_path}.target: expected target name")
            continue
        if target in records:
            errors.append(f"{path}: duplicate target record {target!r}")
            continue
        records[target] = record
    return records


def projection_target(
    projection: dict[str, Any], path: str, errors: list[str]
) -> str | None:
    target_profile = expect_object(
        projection.get("targetProfile"),
        f"{path}.targetProfile",
        errors,
    )
    target = target_profile.get("resolvedTarget")
    if not isinstance(target, str) or not target:
        errors.append(f"{path}.targetProfile.resolvedTarget: expected target name")
        return None
    return target


def projections_by_target(
    projections: list[Any], path: str, errors: list[str]
) -> dict[str, dict[str, Any]]:
    records: dict[str, dict[str, Any]] = {}
    for index, value in enumerate(projections):
        projection_path = f"{path}[{index}]"
        projection = expect_object(value, projection_path, errors)
        target = projection_target(projection, projection_path, errors)
        if target is None:
            continue
        if target in records:
            errors.append(f"{path}: duplicate legalization projection {target!r}")
            continue
        records[target] = projection
    return records


def compare_value(
    errors: list[str],
    path: str,
    actual: Any,
    expected: Any,
    expected_label: str,
) -> None:
    if actual != expected:
        errors.append(f"{path}: expected {expected_label} {expected!r}, got {actual!r}")


def compare_string_sets(
    errors: list[str],
    path: str,
    actual: list[str],
    expected: list[str],
    expected_label: str,
) -> None:
    if sorted(actual) != sorted(expected):
        errors.append(
            f"{path}: expected {expected_label} {sorted(expected)!r}, "
            f"got {sorted(actual)!r}"
        )


def source_package_optional_native_missing(record: dict[str, Any]) -> bool:
    if record.get("packageMode") != "source-package":
        return False
    target = record.get("target")
    evidence_capabilities = (
        target_explanation_v1.SOURCE_PACKAGE_OPTIONAL_NATIVE_EVIDENCE.get(target)
    )
    if evidence_capabilities is None:
        return False
    missing = set(record.get("missingCapabilities", []))
    return any(capability in missing for capability in evidence_capabilities)


def tool_requirement_evidence_ids(
    target: str, required_tools: list[str], missing_tools: list[str]
) -> list[str]:
    evidence_ids = [
        "target-legalization.v1."
        + target
        + ".tool-requirements."
        + ("present" if required_tools or missing_tools else "empty")
    ]
    for role, tool_ids in (("required", required_tools), ("missing", missing_tools)):
        for tool_id in tool_ids:
            _, kind, name = tool_id.split(".", 2)
            evidence_ids.append(
                "target-legalization.v1."
                + target
                + ".tool-requirement."
                + role
                + "."
                + kind
                + "."
                + name
            )
    return evidence_ids


def validate_projection_alignment(
    errors: list[str],
    record: dict[str, Any],
    record_path: str,
    projection: dict[str, Any],
    projection_path: str,
) -> dict[str, bool]:
    coverage = {
        "optional_native": False,
        "diagnostic_evidence": False,
    }
    target = record["target"]
    projection_profile = expect_object(
        projection.get("targetProfile"),
        f"{projection_path}.targetProfile",
        errors,
    )
    compare_value(
        errors,
        f"{projection_path}.targetProfile.resolvedTarget",
        projection_profile.get("resolvedTarget"),
        target,
        "target record target",
    )

    scalar_field_pairs = (
        ("nativeImplemented", "nativeImplemented"),
        ("sourcePackageSupported", "sourcePackageSupported"),
        ("packageBuildSupported", "supportsPackage"),
        ("packageMode", "packageMode"),
        ("packageDecisionReason", "reason"),
        ("packageRankScore", "packageRankScore"),
        ("requiredCapabilityCount", "requiredCapabilityCount"),
        ("missingCapabilityCount", "missingCapabilityCount"),
        ("requiredToolCount", "requiredToolCount"),
        ("missingToolCount", "missingToolCount"),
        ("optionalNativeToolMissing", "optionalNativeToolMissing"),
        ("optionalNativeToolStatus", "optionalNativeToolStatus"),
    )
    for target_field, projection_field in scalar_field_pairs:
        if target_field not in record and projection_field not in projection:
            continue
        compare_value(
            errors,
            f"{record_path}.{target_field}",
            record.get(target_field),
            projection.get(projection_field),
            f"legalization projection {projection_field}",
        )

    compare_value(
        errors,
        f"{projection_path}.supportStatus",
        projection.get("supportStatus"),
        projection_support_status(projection),
        "legalization projection support evidence",
    )
    compare_value(
        errors,
        f"{projection_path}.state",
        projection.get("state"),
        projection_state(projection),
        "legalization projection package support evidence",
    )

    record_required = string_list(
        record.get("requiredCapabilities"),
        f"{record_path}.requiredCapabilities",
        errors,
    )
    projection_required = string_list(
        projection.get("requiredCapabilityIds"),
        f"{projection_path}.requiredCapabilityIds",
        errors,
    )
    compare_string_sets(
        errors,
        f"{record_path}.requiredCapabilities",
        record_required,
        projection_required,
        "legalization projection requiredCapabilityIds",
    )

    record_missing = string_list(
        record.get("missingCapabilities"),
        f"{record_path}.missingCapabilities",
        errors,
    )
    projection_missing = string_list(
        projection.get("missingCapabilityIds"),
        f"{projection_path}.missingCapabilityIds",
        errors,
    )
    compare_string_sets(
        errors,
        f"{record_path}.missingCapabilities",
        record_missing,
        projection_missing,
        "legalization projection missingCapabilityIds",
    )
    unexpected_missing = (
        target_explanation_v1.unexpected_source_package_missing_capabilities(record)
    )
    if unexpected_missing:
        errors.append(
            f"{record_path}.missingCapabilities: buildable source-package target "
            "may only report optional native evidence missing capabilities, "
            f"got {unexpected_missing!r}"
        )

    record_core_evidence = string_list(
        record.get("legalizationCoreEvidenceIds"),
        f"{record_path}.legalizationCoreEvidenceIds",
        errors,
    )
    projection_core_evidence = string_list(
        projection.get("coreEvidenceIds"),
        f"{projection_path}.coreEvidenceIds",
        errors,
    )
    compare_value(
        errors,
        f"{record_path}.legalizationCoreEvidenceIds",
        record_core_evidence,
        projection_core_evidence,
        "legalization projection coreEvidenceIds",
    )

    projection_evidence = set(
        string_list(
            projection.get("evidenceIds"),
            f"{projection_path}.evidenceIds",
            errors,
        )
    )
    missing_core_ids = [
        evidence_id
        for evidence_id in record_core_evidence
        if evidence_id not in projection_evidence
    ]
    if missing_core_ids:
        errors.append(
            f"{projection_path}.evidenceIds: missing core evidence ID(s) "
            f"{missing_core_ids!r}"
        )

    required_tools = string_list(
        projection.get("requiredToolIds"),
        f"{projection_path}.requiredToolIds",
        errors,
    )
    missing_tools = string_list(
        projection.get("missingToolIds"),
        f"{projection_path}.missingToolIds",
        errors,
    )
    tool_evidence = string_list(
        projection.get("toolRequirementEvidenceIds"),
        f"{projection_path}.toolRequirementEvidenceIds",
        errors,
    )
    package_artifact_evidence = string_list(
        projection.get("packageArtifactRequirementEvidenceIds"),
        f"{projection_path}.packageArtifactRequirementEvidenceIds",
        errors,
    )
    expected_required_tools = target_explanation_v1.expected_required_tool_ids(record)
    expected_missing_tools = target_explanation_v1.expected_missing_tool_ids(record)
    compare_string_sets(
        errors,
        f"{projection_path}.requiredToolIds",
        required_tools,
        expected_required_tools,
        "required tool capability IDs",
    )
    compare_string_sets(
        errors,
        f"{projection_path}.missingToolIds",
        missing_tools,
        expected_missing_tools,
        "missing tool capability IDs",
    )
    compare_value(
        errors,
        f"{projection_path}.requiredToolCount",
        projection.get("requiredToolCount"),
        len(required_tools),
        "requiredToolIds length",
    )
    compare_value(
        errors,
        f"{projection_path}.missingToolCount",
        projection.get("missingToolCount"),
        len(missing_tools),
        "missingToolIds length",
    )
    compare_string_sets(
        errors,
        f"{projection_path}.toolRequirementEvidenceIds",
        tool_evidence,
        tool_requirement_evidence_ids(
            target,
            expected_required_tools,
            expected_missing_tools,
        ),
        "tool requirement evidence IDs",
    )
    compare_value(
        errors,
        f"{projection_path}.packageArtifactRequirementEvidenceIds",
        package_artifact_evidence,
        target_explanation_v1.expected_package_artifact_requirement_evidence_ids(
            record
        ),
        "package artifact requirement evidence IDs",
    )

    record_required_tools = string_list(
        record.get("requiredToolIds"),
        f"{record_path}.requiredToolIds",
        errors,
    )
    record_missing_tools = string_list(
        record.get("missingToolIds"),
        f"{record_path}.missingToolIds",
        errors,
    )
    record_tool_evidence = string_list(
        record.get("toolRequirementEvidenceIds"),
        f"{record_path}.toolRequirementEvidenceIds",
        errors,
    )
    record_package_artifact_evidence = string_list(
        record.get("packageArtifactRequirementEvidenceIds"),
        f"{record_path}.packageArtifactRequirementEvidenceIds",
        errors,
    )
    if record_required_tools or "requiredToolIds" in record:
        compare_string_sets(
            errors,
            f"{record_path}.requiredToolIds",
            record_required_tools,
            required_tools,
            "legalization projection requiredToolIds",
        )
    if record_missing_tools or "missingToolIds" in record:
        compare_string_sets(
            errors,
            f"{record_path}.missingToolIds",
            record_missing_tools,
            missing_tools,
            "legalization projection missingToolIds",
        )
    if record_tool_evidence or "toolRequirementEvidenceIds" in record:
        compare_value(
            errors,
            f"{record_path}.toolRequirementEvidenceIds",
            record_tool_evidence,
            tool_evidence,
            "legalization projection toolRequirementEvidenceIds",
        )
    if (
        record_package_artifact_evidence
        or "packageArtifactRequirementEvidenceIds" in record
    ):
        compare_value(
            errors,
            f"{record_path}.packageArtifactRequirementEvidenceIds",
            record_package_artifact_evidence,
            package_artifact_evidence,
            "legalization projection packageArtifactRequirementEvidenceIds",
        )

    if source_package_optional_native_missing(record):
        compare_value(
            errors,
            f"{projection_path}.optionalNativeToolMissing",
            projection.get("optionalNativeToolMissing"),
            True,
            "source-package optional native tool state",
        )
        if (
            "target-legalization.v1." + target + ".optional-native-tool.missing"
            not in record_core_evidence
        ):
            errors.append(
                f"{record_path}.legalizationCoreEvidenceIds: missing optional "
                "native tool evidence ID"
            )
        if not missing_tools:
            errors.append(
                f"{projection_path}.missingToolIds: source-package optional "
                "native fallback must preserve missing tool IDs"
            )
        if not tool_evidence:
            errors.append(
                f"{projection_path}.toolRequirementEvidenceIds: "
                "source-package optional native fallback must preserve tool "
                "evidence IDs"
            )
        coverage["optional_native"] = (
            projection.get("optionalNativeToolMissing") is True
            and bool(missing_tools)
            and bool(tool_evidence)
        )

    expected_required_tool_set = set(expected_required_tools)
    expected_missing_tool_set = set(expected_missing_tools)
    for tool_id in required_tools:
        if tool_id not in expected_required_tool_set:
            errors.append(
                f"{projection_path}.requiredToolIds: tool ID {tool_id!r} is "
                "not expected from target required capabilities or native "
                "package requirements"
            )
    for tool_id in missing_tools:
        if tool_id not in expected_missing_tool_set:
            errors.append(
                f"{projection_path}.missingToolIds: tool ID {tool_id!r} is "
                "not listed in expected target missing tool requirements"
            )
    for evidence_id in tool_evidence:
        if evidence_id not in projection_evidence:
            errors.append(
                f"{projection_path}.toolRequirementEvidenceIds: evidence ID "
                f"{evidence_id!r} is not listed in projection evidenceIds"
            )
    for evidence_id in package_artifact_evidence:
        if evidence_id not in projection_evidence:
            errors.append(
                f"{projection_path}.packageArtifactRequirementEvidenceIds: "
                f"evidence ID {evidence_id!r} is not listed in projection "
                "evidenceIds"
            )

    diagnostic_evidence = string_list(
        projection.get("diagnosticEvidenceIds"),
        f"{projection_path}.diagnosticEvidenceIds",
        errors,
    )
    record_diagnostic_evidence = string_list(
        record.get("diagnosticEvidenceIds"),
        f"{record_path}.diagnosticEvidenceIds",
        errors,
    )
    compare_value(
        errors,
        f"{record_path}.diagnosticEvidenceIds",
        record_diagnostic_evidence,
        diagnostic_evidence,
        "legalization projection diagnosticEvidenceIds",
    )
    diagnostic_summary = expect_object(
        projection.get("diagnosticSummary"),
        f"{projection_path}.diagnosticSummary",
        errors,
    )
    summary_evidence = string_list(
        diagnostic_summary.get("evidenceIds"),
        f"{projection_path}.diagnosticSummary.evidenceIds",
        errors,
    )
    compare_value(
        errors,
        f"{projection_path}.diagnosticEvidenceIds",
        diagnostic_evidence,
        summary_evidence,
        "diagnosticSummary.evidenceIds",
    )
    for evidence_id in diagnostic_evidence:
        if evidence_id not in projection_evidence:
            errors.append(
                f"{projection_path}.diagnosticEvidenceIds: evidence ID "
                f"{evidence_id!r} is not listed in projection evidenceIds"
            )

    if not record.get("packageBuildSupported"):
        if not diagnostic_evidence:
            errors.append(
                f"{projection_path}.diagnosticEvidenceIds: unsupported target "
                "must preserve diagnostic evidence IDs"
            )
        compare_value(
            errors,
            f"{projection_path}.diagnosticSummary.hasErrors",
            diagnostic_summary.get("hasErrors"),
            True,
            "unsupported target diagnostic error state",
        )
        coverage["diagnostic_evidence"] = bool(diagnostic_evidence)

    return coverage


def validate_alignment(
    document: dict[str, Any],
    path: str,
    *,
    validate_schema_semantics: bool,
) -> list[str]:
    errors: list[str] = []
    doctor = expect_object(document.get("doctor"), f"{path}: $.doctor", errors)
    explain_targets = expect_object(
        document.get("explainTargets"),
        f"{path}: $.explainTargets",
        errors,
    )
    projections = expect_list(
        document.get("legalizationProjections"),
        f"{path}: $.legalizationProjections",
        errors,
    )
    if errors:
        return errors

    if validate_schema_semantics:
        errors.extend(
            prefix_errors(
                f"{path}: $.doctor",
                doctor_v1.validate_semantics(doctor),
            )
        )
        errors.extend(
            prefix_errors(
                f"{path}: $.explainTargets",
                target_explanation_v1.validate_semantics(explain_targets),
            )
        )

    doctor_target_explanation = doctor.get("targetExplanation")
    if doctor_target_explanation is None:
        errors.append(f"{path}: $.doctor.targetExplanation must not be null")
    elif doctor_target_explanation != explain_targets:
        errors.append(
            f"{path}: $.doctor.targetExplanation must exactly match $.explainTargets"
        )

    target_records = records_by_target(
        expect_list(
            explain_targets.get("targets"), f"{path}: $.explainTargets.targets", errors
        ),
        f"{path}: $.explainTargets.targets",
        errors,
    )
    legalization_records = projections_by_target(
        projections,
        f"{path}: $.legalizationProjections",
        errors,
    )

    modes: set[str] = set()
    optional_native_covered = False
    diagnostic_evidence_covered = False

    for index, record_value in enumerate(explain_targets.get("targets", [])):
        record = expect_object(
            record_value,
            f"{path}: $.explainTargets.targets[{index}]",
            errors,
        )
        target = record.get("target")
        if target not in target_records:
            continue
        if isinstance(record.get("packageMode"), str):
            modes.add(record["packageMode"])
        projection = legalization_records.get(target)
        if projection is None:
            errors.append(
                f"{path}: $.legalizationProjections missing target {target!r}"
            )
            continue
        coverage = validate_projection_alignment(
            errors,
            record,
            f"{path}: $.explainTargets.targets[{index}]",
            projection,
            f"{path}: $.legalizationProjections[{target}]",
        )
        optional_native_covered = optional_native_covered or coverage["optional_native"]
        diagnostic_evidence_covered = (
            diagnostic_evidence_covered or coverage["diagnostic_evidence"]
        )

    extra_projection_targets = sorted(set(legalization_records) - set(target_records))
    if extra_projection_targets:
        errors.append(
            f"{path}: legalization projection target(s) missing from "
            f"explainTargets: {extra_projection_targets!r}"
        )

    missing_modes = sorted(REQUIRED_PACKAGE_MODES - modes)
    if missing_modes:
        errors.append(f"{path}: fixture must cover package mode(s): {missing_modes!r}")
    if not optional_native_covered:
        errors.append(
            f"{path}: fixture must cover source-package optional native tool evidence"
        )
    if not diagnostic_evidence_covered:
        errors.append(
            f"{path}: fixture must cover unsupported target diagnostic evidence"
        )
    return errors


def fixture_paths(root: Path) -> list[Path]:
    return sorted((root / FIXTURE_ROOT).glob("*.json"))


def check(root: Path) -> list[str]:
    errors: list[str] = []
    paths = fixture_paths(root)
    names = {path.name for path in paths}
    missing = sorted(REQUIRED_VALID_FIXTURES - names)
    if missing:
        errors.append(
            f"{FIXTURE_ROOT}: missing required fixture(s): {', '.join(missing)}"
        )
    if not paths:
        errors.append(f"{FIXTURE_ROOT}: no fixture JSON files found")
        return errors

    for fixture_path in paths:
        relative = fixture_path.relative_to(root).as_posix()
        try:
            document = read_json(fixture_path)
        except (OSError, json.JSONDecodeError) as exc:
            errors.append(f"{relative}: {exc}")
            continue
        case_errors = validate_alignment(
            expect_object(document, relative, errors),
            relative,
            validate_schema_semantics=True,
        )
        errors.extend(case_errors)
    return errors


def target_record(
    document: dict[str, Any], surface: str, target: str
) -> dict[str, Any]:
    records = document[surface]["targets"]
    for record in records:
        if record["target"] == target:
            return record
    raise KeyError(target)


def doctor_target_record(document: dict[str, Any], target: str) -> dict[str, Any]:
    return target_record(document["doctor"], "targetExplanation", target)


def projection_record(document: dict[str, Any], target: str) -> dict[str, Any]:
    for projection in document["legalizationProjections"]:
        if projection["targetProfile"]["resolvedTarget"] == target:
            return projection
    raise KeyError(target)


def expect_self_test_failure(
    errors: list[str],
    base_document: dict[str, Any],
    label: str,
    mutate: Callable[[dict[str, Any]], None],
    expected_fragment: str,
) -> None:
    document = copy.deepcopy(base_document)
    mutate(document)
    probe_errors = validate_alignment(
        document,
        f"self-test:{label}",
        validate_schema_semantics=False,
    )
    if not probe_errors:
        errors.append(f"self-test {label}: expected validation failure")
        return
    if not any(expected_fragment in error for error in probe_errors):
        errors.append(
            f"self-test {label}: expected {expected_fragment!r}, got {probe_errors!r}"
        )


def remove_directx_validator_tool_projection(document: dict[str, Any]) -> None:
    projection = projection_record(document, "directx")
    validator_tool = "directx.validation.dxil-validator"
    projection["requiredToolIds"] = [
        tool_id
        for tool_id in projection["requiredToolIds"]
        if tool_id != validator_tool
    ]
    projection["missingToolIds"] = [
        tool_id for tool_id in projection["missingToolIds"] if tool_id != validator_tool
    ]
    projection["requiredToolCount"] = len(projection["requiredToolIds"])
    projection["missingToolCount"] = len(projection["missingToolIds"])
    projection["toolRequirementEvidenceIds"] = [
        evidence_id
        for evidence_id in projection["toolRequirementEvidenceIds"]
        if ".validation.dxil-validator" not in evidence_id
    ]


def add_non_optional_source_package_missing_capability(
    document: dict[str, Any],
) -> None:
    capability = "directx.feature.extra-blocker"
    records = (
        doctor_target_record(document, "directx"),
        target_record(document, "explainTargets", "directx"),
    )
    for record in records:
        record["requiredCapabilities"].append(capability)
        record["missingCapabilities"].append(capability)
        record["requiredCapabilityCount"] = len(record["requiredCapabilities"])
        record["missingCapabilityCount"] = len(record["missingCapabilities"])
        record["remediation"] = record["remediation"].rstrip(".") + f", {capability}."

    projection = projection_record(document, "directx")
    projection["requiredCapabilityIds"].append(capability)
    projection["missingCapabilityIds"].append(capability)
    projection["requiredCapabilityCount"] = len(projection["requiredCapabilityIds"])
    projection["missingCapabilityCount"] = len(projection["missingCapabilityIds"])


def self_test(root: Path) -> list[str]:
    errors = check(root)
    paths = fixture_paths(root)
    if not paths:
        return errors
    base_document = read_json(paths[0])

    expect_self_test_failure(
        errors,
        base_document,
        "doctor-target-explanation-drift",
        lambda document: doctor_target_record(document, "directx").__setitem__(
            "packageMode", "unsupported"
        ),
        "$.doctor.targetExplanation must exactly match $.explainTargets",
    )
    expect_self_test_failure(
        errors,
        base_document,
        "support-state-drift",
        lambda document: projection_record(document, "directx").__setitem__(
            "supportsPackage", False
        ),
        "packageBuildSupported",
    )
    expect_self_test_failure(
        errors,
        base_document,
        "optional-native-evidence-omitted",
        lambda document: (
            projection_record(document, "directx").__setitem__(
                "optionalNativeToolMissing", False
            ),
            projection_record(document, "directx").__setitem__("missingToolIds", []),
        ),
        "optionalNativeToolMissing",
    )
    expect_self_test_failure(
        errors,
        base_document,
        "optional-native-validator-tool-projection-omitted",
        remove_directx_validator_tool_projection,
        "directx.validation.dxil-validator",
    )
    expect_self_test_failure(
        errors,
        base_document,
        "source-package-extra-missing-capability",
        add_non_optional_source_package_missing_capability,
        "may only report optional native evidence missing capabilities",
    )
    expect_self_test_failure(
        errors,
        base_document,
        "core-evidence-drift",
        lambda document: projection_record(document, "directx").__setitem__(
            "coreEvidenceIds",
            [
                evidence_id
                for evidence_id in projection_record(
                    document,
                    "directx",
                )["coreEvidenceIds"]
                if not evidence_id.endswith(".optional-native-tool.missing")
            ],
        ),
        "legalizationCoreEvidenceIds",
    )
    expect_self_test_failure(
        errors,
        base_document,
        "diagnostic-evidence-omitted",
        lambda document: (
            projection_record(document, "opengl").__setitem__(
                "diagnosticEvidenceIds", []
            ),
            projection_record(document, "opengl")["diagnosticSummary"].__setitem__(
                "evidenceIds", []
            ),
        ),
        "unsupported target must preserve diagnostic evidence IDs",
    )
    return errors


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--root",
        type=Path,
        default=Path(__file__).resolve().parents[1],
        help="repository root",
    )
    parser.add_argument(
        "--self-test",
        action="store_true",
        help="run fixture mutation probes",
    )
    args = parser.parse_args(argv)

    root = args.root.resolve()
    errors = self_test(root) if args.self_test else check(root)
    if errors:
        for error in errors:
            print(error, file=sys.stderr)
        return 1
    if args.self_test:
        print("doctor target explanation alignment self-test OK")
    else:
        print("doctor target explanation alignment OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
