#!/usr/bin/env python3
"""Check read-only target legalization consumer alignment.

This audit intentionally compares only fields already emitted by the CLI.  It
keeps `explain-targets`, `doctor --json`, and debug metadata aligned on the
shared DirectX/OpenGL source-package legalization projection without asserting a
new JSON shape.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any


SOURCE_PACKAGE_OPTIONAL_NATIVE_CAPABILITIES = {
    "directx": (
        "directx.backend.native-dxil-package",
        "directx.toolchain.dxc",
        "directx.validation.dxil-validator",
    ),
    "opengl": (
        "opengl.backend.native-glsl-package",
        "opengl.toolchain.opengl-driver",
        "opengl.validation.glsl-program-validation",
    ),
}


@dataclass(frozen=True)
class TargetExpectation:
    target: str
    package_build_supported: bool
    source_package_supported: bool
    package_mode: str
    missing_capabilities: tuple[str, ...]
    required_capabilities: tuple[str, ...] = ()


@dataclass(frozen=True)
class AlignmentCase:
    name: str
    fixture: Path
    targets: tuple[TargetExpectation, ...]
    recommended_target: str | None = None
    recommended_package_mode: str | None = None
    package_readonly_target: str | None = None


def run(command: list[Path | str], cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [str(arg) for arg in command],
        cwd=cwd,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )


def fail(errors: list[str], case_name: str, message: str) -> None:
    errors.append(f"{case_name}: {message}")


def load_cli_json(
    errors: list[str], case_name: str, root: Path, command: list[Path | str]
) -> dict[str, Any]:
    result = run(command, root)
    if result.returncode != 0:
        fail(
            errors,
            case_name,
            f"{' '.join(str(arg) for arg in command)} failed with "
            f"{result.returncode}: {result.stderr}{result.stdout}".strip(),
        )
        return {}
    try:
        parsed = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        fail(
            errors,
            case_name,
            f"{' '.join(str(arg) for arg in command)} did not emit JSON: {exc}",
        )
        return {}
    if not isinstance(parsed, dict):
        fail(errors, case_name, "CLI JSON root must be an object")
        return {}
    return parsed


def expect_equal(
    errors: list[str],
    case_name: str,
    path: str,
    actual: Any,
    expected: Any,
) -> None:
    if actual != expected:
        fail(errors, case_name, f"expected {path}={expected!r}, got {actual!r}")


def expect_contains(
    errors: list[str],
    case_name: str,
    path: str,
    actual: Any,
    expected_values: tuple[str, ...],
) -> None:
    if not isinstance(actual, list):
        fail(errors, case_name, f"{path} must be an array, got {actual!r}")
        return
    missing = [value for value in expected_values if value not in actual]
    if missing:
        fail(errors, case_name, f"{path} missing expected values {missing!r}")


def records_by_target(records: Any) -> dict[str, dict[str, Any]]:
    if not isinstance(records, list):
        return {}
    return {
        record["target"]: record
        for record in records
        if isinstance(record, dict) and isinstance(record.get("target"), str)
    }


def projection_backed_buildable_record(record: dict[str, Any]) -> bool:
    evidence = record.get("legalizationCoreEvidenceIds")
    return (
        bool(record.get("packageBuildSupported"))
        and isinstance(evidence, list)
        and bool(evidence)
    )


def recommended_projection_record(document: dict[str, Any]) -> dict[str, Any] | None:
    records = document.get("targets")
    if not isinstance(records, list):
        return None
    default_target = document.get("defaultTarget")
    recommended: dict[str, Any] | None = None
    for record in records:
        if not isinstance(record, dict):
            continue
        if not projection_backed_buildable_record(record):
            continue
        rank = record.get("packageRankScore")
        recommended_rank = (
            recommended.get("packageRankScore") if recommended is not None else None
        )
        if (
            recommended is None
            or rank < recommended_rank
            or (
                rank == recommended_rank
                and record.get("target") == default_target
                and recommended.get("target") != default_target
            )
        ):
            recommended = record
    return recommended


def check_projection_backed_recommendation(
    errors: list[str], case_name: str, document: dict[str, Any]
) -> None:
    records = document.get("targets")
    if not isinstance(records, list):
        fail(errors, case_name, "targetExplanation.targets must be an array")
        return
    expected_buildable_count = sum(
        1
        for record in records
        if isinstance(record, dict) and projection_backed_buildable_record(record)
    )
    expect_equal(
        errors,
        case_name,
        "targetExplanation.buildableTargetCount",
        document.get("buildableTargetCount"),
        expected_buildable_count,
    )

    recommended = recommended_projection_record(document)
    if recommended is None:
        expect_equal(
            errors,
            case_name,
            "targetExplanation.recommendedTarget",
            document.get("recommendedTarget"),
            None,
        )
        expect_equal(
            errors,
            case_name,
            "targetExplanation.recommendedPackageMode",
            document.get("recommendedPackageMode"),
            None,
        )
        return

    expect_equal(
        errors,
        case_name,
        "targetExplanation.recommendedTarget",
        document.get("recommendedTarget"),
        recommended.get("target"),
    )
    expect_equal(
        errors,
        case_name,
        "targetExplanation.recommendedPackageMode",
        document.get("recommendedPackageMode"),
        recommended.get("packageMode"),
    )


def target_record(
    errors: list[str],
    case_name: str,
    document: dict[str, Any],
    records_path: str,
    target: str,
) -> dict[str, Any]:
    records: Any = document
    for part in records_path.split("."):
        records = records.get(part) if isinstance(records, dict) else None
    by_target = records_by_target(records)
    record = by_target.get(target)
    if record is None:
        fail(errors, case_name, f"{records_path} missing target {target!r}")
        return {}
    return record


def package_decision_provenance(record: dict[str, Any]) -> str:
    mode = record.get("packageMode")
    if mode == "native":
        return "native-package-available"
    if mode == "source-package":
        return "source-package-only"
    if record.get("target") in SOURCE_PACKAGE_OPTIONAL_NATIVE_CAPABILITIES:
        if not record.get("sourcePackageSupported"):
            return "unsupported-source-form"
    if record.get("nativeImplemented"):
        return "unsupported-native-form"
    return "unsupported"


def optional_native_tool_missing(record: dict[str, Any]) -> bool:
    if record.get("packageMode") != "source-package":
        return False
    optional_capabilities = SOURCE_PACKAGE_OPTIONAL_NATIVE_CAPABILITIES.get(
        record.get("target")
    )
    if optional_capabilities is None:
        return False
    missing_capabilities = set(record.get("missingCapabilities", []))
    return any(
        capability in missing_capabilities for capability in optional_capabilities
    )


def expected_core_evidence(record: dict[str, Any]) -> list[str]:
    target = record["target"]
    mode = record["packageMode"]
    state = "legalized" if record["packageBuildSupported"] else "rejected"
    support_status = mode if record["packageBuildSupported"] else "unsupported"
    reason = record.get("packageDecisionReason")
    if not isinstance(reason, str) or not reason:
        reason = "source-package-available" if mode == "source-package" else mode
    prefix = f"target-legalization.v1.{target}"
    evidence = [
        f"{prefix}.decision",
        f"{prefix}.state.{state}",
        f"{prefix}.support.{support_status}",
        f"{prefix}.package-mode.{mode}",
        f"{prefix}.package-provenance.{package_decision_provenance(record)}",
    ]
    if optional_native_tool_missing(record):
        evidence.append(f"{prefix}.optional-native-tool.missing")
    evidence.append(f"{prefix}.package-reason.{reason}")
    return evidence


def flattened_group_capabilities(groups: Any) -> list[str]:
    if not isinstance(groups, list):
        return []
    capabilities: list[str] = []
    for group in groups:
        if isinstance(group, dict) and isinstance(group.get("capabilities"), list):
            capabilities.extend(
                value for value in group["capabilities"] if isinstance(value, str)
            )
    return capabilities


def compare_target_record_to_expectation(
    errors: list[str],
    case_name: str,
    path: str,
    record: dict[str, Any],
    expected: TargetExpectation,
) -> None:
    expect_equal(
        errors,
        case_name,
        f"{path}.sourcePackageSupported",
        record.get("sourcePackageSupported"),
        expected.source_package_supported,
    )
    expect_equal(
        errors,
        case_name,
        f"{path}.packageBuildSupported",
        record.get("packageBuildSupported"),
        expected.package_build_supported,
    )
    expect_equal(
        errors,
        case_name,
        f"{path}.packageMode",
        record.get("packageMode"),
        expected.package_mode,
    )
    expect_contains(
        errors,
        case_name,
        f"{path}.missingCapabilities",
        record.get("missingCapabilities"),
        expected.missing_capabilities,
    )
    expect_contains(
        errors,
        case_name,
        f"{path}.requiredCapabilities",
        record.get("requiredCapabilities"),
        expected.required_capabilities,
    )
    expected_evidence = expected_core_evidence(record)
    expect_equal(
        errors,
        case_name,
        f"{path}.legalizationCoreEvidenceIds",
        record.get("legalizationCoreEvidenceIds"),
        expected_evidence,
    )
    if expected.package_mode == "source-package":
        expect_contains(
            errors,
            case_name,
            f"{path}.missingCapabilities",
            record.get("missingCapabilities"),
            SOURCE_PACKAGE_OPTIONAL_NATIVE_CAPABILITIES[expected.target],
        )


def compare_records(
    errors: list[str],
    case_name: str,
    actual_path: str,
    actual: dict[str, Any],
    expected_path: str,
    expected: dict[str, Any],
) -> None:
    shared_fields = (
        "target",
        "nativeImplemented",
        "sourcePackageSupported",
        "packageBuildSupported",
        "packageMode",
        "packageDecisionReason",
        "packageRankScore",
        "requiredCapabilityCount",
        "missingCapabilityCount",
        "legalizationCoreEvidenceIds",
        "requiredToolCount",
        "missingToolCount",
        "optionalNativeToolMissing",
        "optionalNativeToolStatus",
        "toolRequirementEvidenceIds",
    )
    for field in shared_fields:
        expect_equal(
            errors,
            case_name,
            f"{actual_path}.{field}",
            actual.get(field),
            expected.get(field),
        )
    for field in (
        "requiredCapabilities",
        "missingCapabilities",
        "requiredToolIds",
        "missingToolIds",
    ):
        actual_values = actual.get(field)
        expected_values = expected.get(field)
        if isinstance(actual_values, list):
            actual_values = sorted(actual_values)
        if isinstance(expected_values, list):
            expected_values = sorted(expected_values)
        expect_equal(
            errors,
            case_name,
            f"{actual_path}.{field}",
            actual_values,
            expected_values,
        )


def compare_selected_target_to_summary(
    errors: list[str],
    case_name: str,
    decision: dict[str, Any],
    summary: dict[str, Any],
) -> None:
    field_pairs = (
        ("selectedTargetNativeImplemented", "nativeImplemented"),
        ("selectedTargetSourcePackageSupported", "sourcePackageSupported"),
        ("selectedTargetPackageBuildSupported", "packageBuildSupported"),
        ("selectedTargetPackageMode", "packageMode"),
        ("selectedTargetMissingCapabilityCount", "missingCapabilityCount"),
        ("selectedTargetLegalizationCoreEvidenceIds", "legalizationCoreEvidenceIds"),
        ("selectedTargetRequiredToolCount", "requiredToolCount"),
        ("selectedTargetMissingToolCount", "missingToolCount"),
        ("selectedTargetRequiredToolIds", "requiredToolIds"),
        ("selectedTargetMissingToolIds", "missingToolIds"),
        ("selectedTargetOptionalNativeToolMissing", "optionalNativeToolMissing"),
        ("selectedTargetOptionalNativeToolStatus", "optionalNativeToolStatus"),
        (
            "selectedTargetToolRequirementEvidenceIds",
            "toolRequirementEvidenceIds",
        ),
    )
    for decision_field, summary_field in field_pairs:
        expect_equal(
            errors,
            case_name,
            f"targetDecision.{decision_field}",
            decision.get(decision_field),
            summary.get(summary_field),
        )
    expect_equal(
        errors,
        case_name,
        "targetDecision.selectedTargetMissingCapabilities",
        sorted(decision.get("selectedTargetMissingCapabilities", [])),
        sorted(summary.get("missingCapabilities", [])),
    )
    expect_equal(
        errors,
        case_name,
        "targetDecision.selectedTargetMissingCapabilityGroups",
        sorted(
            flattened_group_capabilities(
                decision.get("selectedTargetMissingCapabilityGroups")
            )
        ),
        sorted(summary.get("missingCapabilities", [])),
    )


def required_path_artifact_names(records: Any) -> list[str]:
    if not isinstance(records, list):
        return []
    names: list[str] = []
    for record in records:
        if isinstance(record, str):
            names.append(record)
        elif isinstance(record, dict) and isinstance(record.get("name"), str):
            names.append(record["name"])
    return names


def check_package_readonly_alignment(
    errors: list[str],
    root: Path,
    cglc: Path,
    case_name: str,
    target: str,
    explanation_record: dict[str, Any],
    auto_decision: dict[str, Any],
) -> None:
    from check_package_integrity_fixtures import (
        TARGET_REQUIRED_PATH_ARTIFACTS,
        make_package,
    )

    with tempfile.TemporaryDirectory(prefix=f"{case_name}-") as tmp:
        package, _source, _manifest = make_package(
            Path(tmp), f"{case_name}-{target}", status="planned", target=target
        )
        inspect = load_cli_json(
            errors,
            case_name,
            root,
            [cglc, "package", "inspect", package, "--json"],
        )

    summary = inspect.get("summary", {})
    requirements = inspect.get("packageArtifactRequirements", {})
    manifest = inspect.get("manifest", {})
    manifest_requirements = manifest.get("packageArtifactRequirements", {})
    manifest_artifacts = manifest.get("artifacts", {})
    expected_path_artifacts = list(TARGET_REQUIRED_PATH_ARTIFACTS[target])
    expected_provenance_id = (
        f"target-legalization.v1.{target}.package-provenance."
        f"{package_decision_provenance(explanation_record)}"
    )

    expect_equal(
        errors,
        case_name,
        "package inspect summary.target",
        summary.get("target"),
        target,
    )
    expect_equal(
        errors,
        case_name,
        "package inspect packageArtifactRequirements.target",
        requirements.get("target"),
        target,
    )
    expect_equal(
        errors,
        case_name,
        "package inspect manifest.packageArtifactRequirements.target",
        manifest_requirements.get("target"),
        target,
    )
    expect_equal(
        errors,
        case_name,
        "package inspect packageArtifactRequirements.packageMode",
        requirements.get("packageMode"),
        explanation_record.get("packageMode"),
    )
    expect_equal(
        errors,
        case_name,
        "package inspect packageArtifactRequirements.packageMode",
        requirements.get("packageMode"),
        auto_decision.get("selectedTargetPackageMode"),
    )
    expect_equal(
        errors,
        case_name,
        "package inspect manifest.packageArtifactRequirements.packageMode",
        manifest_requirements.get("packageMode"),
        explanation_record.get("packageMode"),
    )
    expect_equal(
        errors,
        case_name,
        "package inspect packageArtifactRequirements.requiredPathArtifacts",
        required_path_artifact_names(requirements.get("requiredPathArtifacts")),
        expected_path_artifacts,
    )
    expect_equal(
        errors,
        case_name,
        "package inspect manifest.packageArtifactRequirements.requiredPathArtifacts",
        required_path_artifact_names(
            manifest_requirements.get("requiredPathArtifacts")
        ),
        expected_path_artifacts,
    )
    for artifact_name in expected_path_artifacts:
        if artifact_name not in manifest_artifacts:
            fail(
                errors,
                case_name,
                "package inspect manifest.artifacts missing required "
                f"artifact {artifact_name!r}",
            )
    expect_equal(
        errors,
        case_name,
        "package inspect summary.nativeBinaryStatus",
        summary.get("nativeBinaryStatus"),
        "planned",
    )
    expect_equal(
        errors,
        case_name,
        "package inspect manifest.artifacts.nativeBinaryStatus",
        manifest_artifacts.get("nativeBinaryStatus"),
        "planned",
    )
    expect_equal(
        errors,
        case_name,
        "package inspect packageArtifactRequirements.requiresNativeBinaryStatus",
        requirements.get("requiresNativeBinaryStatus"),
        True,
    )
    expect_equal(
        errors,
        case_name,
        "package inspect manifest.packageArtifactRequirements.requiresNativeBinaryStatus",
        manifest_requirements.get("requiresNativeBinaryStatus"),
        True,
    )
    expect_equal(
        errors,
        case_name,
        "package inspect packageArtifactRequirements.allowsPlannedNativeBinary",
        requirements.get("allowsPlannedNativeBinary"),
        True,
    )
    expect_equal(
        errors,
        case_name,
        "package inspect manifest.packageArtifactRequirements.allowsPlannedNativeBinary",
        manifest_requirements.get("allowsPlannedNativeBinary"),
        True,
    )
    expect_equal(
        errors,
        case_name,
        "package inspect packageArtifactRequirements.allowsPlannedNativeSourceEvidence",
        requirements.get("allowsPlannedNativeSourceEvidence"),
        True,
    )
    expect_equal(
        errors,
        case_name,
        "package inspect manifest.packageArtifactRequirements.allowsPlannedNativeSourceEvidence",
        manifest_requirements.get("allowsPlannedNativeSourceEvidence"),
        True,
    )
    expect_contains(
        errors,
        case_name,
        "explain-targets packageDecisionProvenance evidence",
        explanation_record.get("legalizationCoreEvidenceIds"),
        (expected_provenance_id,),
    )
    expect_contains(
        errors,
        case_name,
        "auto debug selectedTarget packageDecisionProvenance evidence",
        auto_decision.get("selectedTargetLegalizationCoreEvidenceIds"),
        (expected_provenance_id,),
    )


def check_alignment_case(
    errors: list[str], root: Path, cglc: Path, case: AlignmentCase
) -> None:
    fixture = root / case.fixture
    explanation = load_cli_json(
        errors, case.name, root, [cglc, "explain-targets", fixture]
    )
    check_projection_backed_recommendation(errors, case.name, explanation)
    doctor = load_cli_json(errors, case.name, root, [cglc, "doctor", "--json", fixture])
    doctor_explanation = doctor.get("targetExplanation")
    expect_equal(
        errors,
        case.name,
        "doctor.targetExplanation",
        doctor_explanation,
        explanation,
    )
    if isinstance(doctor_explanation, dict):
        check_projection_backed_recommendation(errors, case.name, doctor_explanation)

    auto_decision: dict[str, Any] = {}
    if case.recommended_target is not None:
        expect_equal(
            errors,
            case.name,
            "targetExplanation.recommendedTarget",
            explanation.get("recommendedTarget"),
            case.recommended_target,
        )
        expect_equal(
            errors,
            case.name,
            "targetExplanation.recommendedPackageMode",
            explanation.get("recommendedPackageMode"),
            case.recommended_package_mode,
        )
        auto_debug = load_cli_json(
            errors,
            case.name,
            root,
            [cglc, "dump-ir", fixture, "--stage", "debug", "--target", "auto"],
        )
        auto_decision = auto_debug.get("targetDecision", {})
        expect_equal(
            errors,
            case.name,
            "auto debug selectedTarget",
            auto_decision.get("selectedTarget"),
            case.recommended_target,
        )
        expect_equal(
            errors,
            case.name,
            "auto debug selectedTargetPackageMode",
            auto_decision.get("selectedTargetPackageMode"),
            case.recommended_package_mode,
        )
        expect_contains(
            errors,
            case.name,
            "auto debug viableTargets",
            auto_decision.get("viableTargets"),
            tuple(
                target.target
                for target in case.targets
                if target.package_build_supported
            ),
        )
        expect_contains(
            errors,
            case.name,
            "auto debug nonViableTargets",
            auto_decision.get("nonViableTargets"),
            tuple(
                target.target
                for target in case.targets
                if not target.package_build_supported
            ),
        )

    for target_expectation in case.targets:
        target = target_expectation.target
        explanation_record = target_record(
            errors, case.name, explanation, "targets", target
        )
        compare_target_record_to_expectation(
            errors,
            case.name,
            f"explain-targets.targets[{target}]",
            explanation_record,
            target_expectation,
        )

        debug = load_cli_json(
            errors,
            case.name,
            root,
            [cglc, "dump-ir", fixture, "--stage", "debug", "--target", target],
        )
        summary = target_record(
            errors,
            case.name,
            debug,
            "targetCapabilities.summaries",
            target,
        )
        compare_records(
            errors,
            case.name,
            f"debug.targetCapabilities.summaries[{target}]",
            summary,
            f"explain-targets.targets[{target}]",
            explanation_record,
        )
        compare_target_record_to_expectation(
            errors,
            case.name,
            f"debug.targetCapabilities.summaries[{target}]",
            summary,
            target_expectation,
        )

        decision = debug.get("targetDecision", {})
        expect_equal(
            errors,
            case.name,
            "targetDecision.requestedTarget",
            decision.get("requestedTarget"),
            target,
        )
        expect_equal(
            errors,
            case.name,
            "targetDecision.selectedTarget",
            decision.get("selectedTarget"),
            target,
        )
        compare_selected_target_to_summary(errors, case.name, decision, summary)

        if not target_expectation.package_build_supported:
            diagnostics = decision.get("diagnostics", [])
            if not diagnostics:
                fail(
                    errors,
                    case.name,
                    f"targetDecision.diagnostics missing rejected {target} record",
                )
            for index, diagnostic in enumerate(diagnostics):
                if not isinstance(diagnostic, dict):
                    continue
                if diagnostic.get("target") != target:
                    continue
                expect_equal(
                    errors,
                    case.name,
                    f"targetDecision.diagnostics[{index}].legalizationCoreEvidenceIds",
                    diagnostic.get("legalizationCoreEvidenceIds"),
                    summary.get("legalizationCoreEvidenceIds"),
                )
                expect_contains(
                    errors,
                    case.name,
                    f"targetDecision.diagnostics[{index}].capabilities",
                    diagnostic.get("capabilities"),
                    target_expectation.missing_capabilities,
                )

    if case.package_readonly_target is not None:
        if not auto_decision:
            fail(
                errors,
                case.name,
                "package-readonly alignment requires an auto target decision",
            )
        package_record = target_record(
            errors, case.name, explanation, "targets", case.package_readonly_target
        )
        check_package_readonly_alignment(
            errors,
            root,
            cglc,
            case.name,
            case.package_readonly_target,
            package_record,
            auto_decision,
        )


def alignment_cases() -> tuple[AlignmentCase, ...]:
    runtime_texture_capabilities = (
        "{target}.resource.runtime-descriptor-array",
        "{target}.resource.runtime-texture-descriptor-array",
        "{target}.layout.runtime-array",
    )
    runtime_texture_sampler_capabilities = (
        "{target}.resource.runtime-descriptor-array",
        "{target}.resource.runtime-texture-descriptor-array",
        "{target}.resource.runtime-sampler-descriptor-array",
        "{target}.layout.runtime-array",
    )

    def required_runtime_capabilities(
        target: str, capabilities: tuple[str, ...]
    ) -> tuple[str, ...]:
        return tuple(capability.format(target=target) for capability in capabilities)

    return (
        AlignmentCase(
            name="simple-source-packages",
            fixture=Path("tests/fixtures/SimpleShader.cgl"),
            targets=(
                TargetExpectation(
                    target="directx",
                    package_build_supported=True,
                    source_package_supported=True,
                    package_mode="source-package",
                    missing_capabilities=SOURCE_PACKAGE_OPTIONAL_NATIVE_CAPABILITIES[
                        "directx"
                    ],
                ),
                TargetExpectation(
                    target="opengl",
                    package_build_supported=True,
                    source_package_supported=True,
                    package_mode="source-package",
                    missing_capabilities=SOURCE_PACKAGE_OPTIONAL_NATIVE_CAPABILITIES[
                        "opengl"
                    ],
                ),
            ),
        ),
        AlignmentCase(
            name="runtime-resource-array-rejections",
            fixture=Path(
                "tests/directx/fixtures/"
                "DirectXRuntimeTextureResourceArrayConflictShader.cgl"
            ),
            targets=(
                TargetExpectation(
                    target="directx",
                    package_build_supported=False,
                    source_package_supported=False,
                    package_mode="unsupported",
                    missing_capabilities=(
                        "directx.backend.hlsl-lowering",
                        "directx.diagnostic.directx.unsupported-runtime-resource-array",
                    ),
                    required_capabilities=required_runtime_capabilities(
                        "directx", runtime_texture_capabilities
                    ),
                ),
                TargetExpectation(
                    target="opengl",
                    package_build_supported=False,
                    source_package_supported=False,
                    package_mode="unsupported",
                    missing_capabilities=(
                        "opengl.backend.glsl-lowering",
                        "opengl.diagnostic.opengl.unsupported-runtime-resource-array",
                    ),
                    required_capabilities=required_runtime_capabilities(
                        "opengl", runtime_texture_capabilities
                    ),
                ),
            ),
        ),
        AlignmentCase(
            name="runtime-texture-sampler-array-support-and-rejections",
            fixture=Path(
                "tests/directx/fixtures/"
                "DirectXRuntimeTextureSamplerResourceArrayShader.cgl"
            ),
            targets=(
                TargetExpectation(
                    target="metal",
                    package_build_supported=False,
                    source_package_supported=False,
                    package_mode="unsupported",
                    missing_capabilities=(
                        "metal.backend.native-metal-package",
                        "metal.diagnostic.metal.unsupported-runtime-resource-array",
                    ),
                    required_capabilities=required_runtime_capabilities(
                        "metal", runtime_texture_sampler_capabilities
                    ),
                ),
                TargetExpectation(
                    target="vulkan",
                    package_build_supported=True,
                    source_package_supported=False,
                    package_mode="native",
                    missing_capabilities=(),
                    required_capabilities=required_runtime_capabilities(
                        "vulkan", runtime_texture_sampler_capabilities
                    ),
                ),
                TargetExpectation(
                    target="directx",
                    package_build_supported=True,
                    source_package_supported=True,
                    package_mode="source-package",
                    missing_capabilities=SOURCE_PACKAGE_OPTIONAL_NATIVE_CAPABILITIES[
                        "directx"
                    ],
                    required_capabilities=required_runtime_capabilities(
                        "directx", runtime_texture_sampler_capabilities
                    ),
                ),
                TargetExpectation(
                    target="opengl",
                    package_build_supported=False,
                    source_package_supported=False,
                    package_mode="unsupported",
                    missing_capabilities=(
                        "opengl.backend.glsl-lowering",
                        "opengl.diagnostic.opengl.unsupported-runtime-resource-array",
                    ),
                    required_capabilities=required_runtime_capabilities(
                        "opengl", runtime_texture_sampler_capabilities
                    ),
                ),
            ),
            recommended_target="vulkan",
            recommended_package_mode="native",
        ),
        AlignmentCase(
            name="native-target-fallback-source-package-recommendation",
            fixture=Path("tests/fixtures/MetalStorageBufferArrayUnsupportedShader.cgl"),
            targets=(
                TargetExpectation(
                    target="metal",
                    package_build_supported=False,
                    source_package_supported=False,
                    package_mode="unsupported",
                    missing_capabilities=(
                        "metal.backend.native-metal-package",
                        "metal.diagnostic.metal.unsupported-storage-buffer-array",
                    ),
                ),
                TargetExpectation(
                    target="vulkan",
                    package_build_supported=False,
                    source_package_supported=False,
                    package_mode="unsupported",
                    missing_capabilities=(
                        "vulkan.backend.vulkan-prototype-package",
                        "vulkan.diagnostic.vulkan.prototype-unsupported-runtime-resource-array",
                    ),
                ),
                TargetExpectation(
                    target="directx",
                    package_build_supported=True,
                    source_package_supported=True,
                    package_mode="source-package",
                    missing_capabilities=SOURCE_PACKAGE_OPTIONAL_NATIVE_CAPABILITIES[
                        "directx"
                    ],
                ),
                TargetExpectation(
                    target="opengl",
                    package_build_supported=True,
                    source_package_supported=True,
                    package_mode="source-package",
                    missing_capabilities=SOURCE_PACKAGE_OPTIONAL_NATIVE_CAPABILITIES[
                        "opengl"
                    ],
                ),
            ),
            recommended_target="directx",
            recommended_package_mode="source-package",
            package_readonly_target="directx",
        ),
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--cglc", type=Path, required=True)
    args = parser.parse_args()

    root = args.root.resolve()
    cglc = args.cglc.resolve()
    errors: list[str] = []
    for case in alignment_cases():
        check_alignment_case(errors, root, cglc, case)

    if errors:
        print("target read-only consumer alignment failed:", file=sys.stderr)
        for error in errors:
            print(f"- {error}", file=sys.stderr)
        return 1

    print("validated target read-only consumer alignment")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
