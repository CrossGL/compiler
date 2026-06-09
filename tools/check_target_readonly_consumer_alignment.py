#!/usr/bin/env python3
"""Check read-only target legalization consumer alignment.

This audit intentionally compares only fields already emitted by the CLI.  It
keeps `explain-targets`, `doctor --json`, and debug metadata aligned on the
shared DirectX/OpenGL source-package legalization projection without asserting a
new JSON shape.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import re
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

REGISTRY_PATH = Path("docs/target-capability-registry-v1.json")
CPP_TARGET_CAPABILITIES_PATH = Path("src/Backend/TargetCapabilities.cpp")
PACKAGE_TARGET_CONTRACTS_PATH = Path("tools/package_target_contracts.json")
PACKAGE_ARTIFACT_REQUIREMENTS_SOURCE = "tools/package_target_contracts.json"
TARGET_KIND_NAMES = {
    "Metal": "metal",
    "Vulkan": "vulkan",
    "DirectX": "directx",
    "OpenGL": "opengl",
}
TOOL_REQUIREMENT_KINDS = {"toolchain", "validation", "native-tool", "nativeTool"}

CPP_REGISTRY_CONTRACT_RE = re.compile(
    r"TargetCapabilityRegistryContract\{\s*"
    r"TargetKind::(?P<kind>[A-Za-z0-9_]+)\s*,\s*"
    r'"(?P<package_mode>[^"]+)"\s*,\s*'
    r'"(?P<native_support_class>[^"]+)"\s*,\s*'
    r'"(?P<baseline_backend_capability>[^"]+)"\s*,\s*'
    r'"(?P<native_artifact_capability>[^"]+)"\s*,\s*'
    r"(?P<native_implemented>true|false)\s*,\s*"
    r"(?P<source_package_selectable>true|false)\s*"
    r"\}",
    re.MULTILINE,
)


@dataclass(frozen=True)
class CppTargetRegistryContract:
    target: str
    package_mode: str
    native_support_class: str
    baseline_backend_capability_name: str
    native_artifact_capability: str
    native_implemented: bool
    source_package_selectable: bool

    @property
    def baseline_backend_capability(self) -> str:
        return f"{self.target}.backend.{self.baseline_backend_capability_name}"

    @property
    def package_build_supported(self) -> bool:
        return self.native_implemented or self.source_package_selectable

    @property
    def admitted_package_modes(self) -> list[str]:
        if not self.package_build_supported:
            return []
        return [self.package_mode]

    @property
    def package_decision_reason(self) -> str:
        if self.package_mode == "native":
            return "native-package-available"
        if self.package_mode == "source-package":
            return "source-package-available"
        return "unsupported"

    @property
    def package_rank_score(self) -> int:
        if self.package_mode == "native":
            return 0
        if self.package_mode == "source-package":
            return 1
        return 2


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
    registry_contract_fixture: bool = False


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


def load_json_document(errors: list[str], case_name: str, path: Path) -> dict[str, Any]:
    try:
        with path.open("r", encoding="utf-8") as handle:
            parsed = json.load(handle)
    except OSError as exc:
        fail(errors, case_name, f"{path}: failed to read JSON: {exc}")
        return {}
    except json.JSONDecodeError as exc:
        fail(
            errors,
            case_name,
            f"{path}: invalid JSON at line {exc.lineno}, column {exc.colno}: {exc.msg}",
        )
        return {}
    if not isinstance(parsed, dict):
        fail(errors, case_name, f"{path}: JSON root must be an object")
        return {}
    return parsed


def import_module_from_path(module_name: str, path: Path) -> Any:
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load module {module_name!r} from {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def registry_targets_by_name(
    errors: list[str], case_name: str, registry: dict[str, Any]
) -> dict[str, dict[str, Any]]:
    targets = registry.get("targets")
    if not isinstance(targets, list):
        fail(errors, case_name, "registry.targets must be an array")
        return {}
    by_target: dict[str, dict[str, Any]] = {}
    for index, record in enumerate(targets):
        if not isinstance(record, dict) or not isinstance(record.get("target"), str):
            fail(
                errors, case_name, f"registry.targets[{index}] must be a target object"
            )
            continue
        target = record["target"]
        if target in by_target:
            fail(errors, case_name, f"registry target {target!r} is duplicated")
            continue
        by_target[target] = record
    return by_target


def parse_cpp_registry_contracts(
    errors: list[str], case_name: str, root: Path
) -> dict[str, CppTargetRegistryContract]:
    path = root / CPP_TARGET_CAPABILITIES_PATH
    try:
        source = path.read_text(encoding="utf-8")
    except OSError as exc:
        fail(errors, case_name, f"{path}: failed to read C++ source: {exc}")
        return {}

    contracts: dict[str, CppTargetRegistryContract] = {}
    for match in CPP_REGISTRY_CONTRACT_RE.finditer(source):
        kind = match.group("kind")
        target = TARGET_KIND_NAMES.get(kind)
        if target is None:
            fail(errors, case_name, f"{path}: unknown TargetKind::{kind}")
            continue
        if target in contracts:
            fail(errors, case_name, f"{path}: duplicate C++ contract for {target}")
            continue
        contracts[target] = CppTargetRegistryContract(
            target=target,
            package_mode=match.group("package_mode"),
            native_support_class=match.group("native_support_class"),
            baseline_backend_capability_name=match.group("baseline_backend_capability"),
            native_artifact_capability=match.group("native_artifact_capability"),
            native_implemented=match.group("native_implemented") == "true",
            source_package_selectable=(
                match.group("source_package_selectable") == "true"
            ),
        )
    if not contracts:
        fail(errors, case_name, f"{path}: no C++ target registry contracts found")
    return contracts


def parse_cpp_baseline_capabilities(
    errors: list[str], case_name: str, root: Path
) -> dict[str, list[str]]:
    path = root / CPP_TARGET_CAPABILITIES_PATH
    try:
        source = path.read_text(encoding="utf-8")
    except OSError as exc:
        fail(errors, case_name, f"{path}: failed to read C++ source: {exc}")
        return {}

    baselines: dict[str, list[str]] = {}
    for kind, target in TARGET_KIND_NAMES.items():
        case_match = re.search(
            rf"case TargetKind::{kind}:\s*(?P<body>.*?)\s*return;",
            source,
            re.DOTALL,
        )
        if case_match is None:
            fail(errors, case_name, f"{path}: missing baseline case for {target}")
            continue
        capabilities = [
            f"{target}.{capability_kind}.{capability_name}"
            for capability_kind, capability_name in re.findall(
                r'collector\.add\("([^"]+)"\s*,\s*"([^"]+)"\);',
                case_match.group("body"),
            )
        ]
        if not capabilities:
            fail(errors, case_name, f"{path}: no baseline capabilities for {target}")
            continue
        baselines[target] = capabilities
    return baselines


def normalize_package_contract_entry(entry: Any) -> dict[str, Any]:
    return {
        "target": entry["target"],
        "requiredPathArtifacts": list(entry["requiredPathArtifacts"]),
        "requiresNativeBinaryStatus": bool(entry["requiresNativeBinaryStatus"]),
        "allowsPlannedNativeBinary": bool(entry["allowsPlannedNativeBinary"]),
        "allowsPlannedNativeSourceEvidence": bool(
            entry["allowsPlannedNativeSourceEvidence"]
        ),
    }


def normalize_tool_package_contract(contract: Any) -> dict[str, Any]:
    return {
        "target": contract.target,
        "requiredPathArtifacts": list(contract.required_path_artifacts),
        "requiresNativeBinaryStatus": contract.requires_native_binary_status,
        "allowsPlannedNativeBinary": contract.allows_planned_native_binary,
        "allowsPlannedNativeSourceEvidence": (
            contract.allows_planned_native_source_evidence
        ),
    }


def load_package_contracts(
    errors: list[str], case_name: str, root: Path
) -> tuple[dict[str, dict[str, Any]], dict[str, dict[str, Any]]]:
    try:
        tool_module = import_module_from_path(
            "crossgl_check_package_target_contracts",
            root / "tools" / "package_target_contracts.py",
        )
        runtime_module = import_module_from_path(
            "crossgl_check_runtime_package_target_contracts",
            root / "runtime" / "package_target_contracts.py",
        )
        tool_contracts, _debug_artifacts = tool_module.load_contract_document(
            root / PACKAGE_TARGET_CONTRACTS_PATH,
            label_root=root,
        )
    except (ImportError, OSError, ValueError) as exc:
        fail(errors, case_name, f"failed to load package target contracts: {exc}")
        return {}, {}

    tool_records = {
        contract.target: normalize_tool_package_contract(contract)
        for contract in tool_contracts
    }
    runtime_records = {
        entry["target"]: normalize_package_contract_entry(entry)
        for entry in runtime_module.PACKAGE_TARGET_CONTRACTS
    }
    return tool_records, runtime_records


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


def capability_kind(capability_id: str) -> str:
    parts = capability_id.split(".")
    if len(parts) < 3:
        return ""
    return parts[1]


def expected_package_artifact_evidence_ids(
    target: str, package_mode: str, requirements: dict[str, Any]
) -> list[str]:
    evidence_ids = [
        f"target-legalization.v1.{target}.package-artifacts.{package_mode}",
    ]
    evidence_ids.extend(
        f"target-legalization.v1.{target}.package-artifact.required.{artifact}"
        for artifact in requirements["requiredPathArtifacts"]
    )
    if requirements["requiresNativeBinaryStatus"]:
        evidence_ids.append(
            f"target-legalization.v1.{target}."
            "package-artifact.native-binary-status.required"
        )
    if requirements["allowsPlannedNativeBinary"]:
        evidence_ids.append(
            f"target-legalization.v1.{target}."
            "package-artifact.planned-native-binary.allowed"
        )
    if requirements["allowsPlannedNativeSourceEvidence"]:
        evidence_ids.append(
            f"target-legalization.v1.{target}."
            "package-artifact.planned-native-source-evidence.allowed"
        )
    return evidence_ids


def registry_core_capability_ids(record: dict[str, Any]) -> list[str]:
    capabilities = record.get("capabilities")
    if not isinstance(capabilities, list):
        return []
    return [
        capability["id"]
        for capability in capabilities
        if isinstance(capability, dict) and isinstance(capability.get("id"), str)
    ]


def registry_tool_requirement_capabilities(record: dict[str, Any]) -> list[str]:
    capabilities = record.get("emittedBaselineCapabilities")
    if not isinstance(capabilities, list):
        return []
    return [
        capability
        for capability in capabilities
        if isinstance(capability, str)
        and capability_kind(capability) in TOOL_REQUIREMENT_KINDS
    ]


def check_registry_static_contract_alignment(errors: list[str], root: Path) -> None:
    case_name = "target-capability-registry-contract"
    registry = load_json_document(errors, case_name, root / REGISTRY_PATH)
    if not registry:
        return
    registry_records = registry_targets_by_name(errors, case_name, registry)
    cpp_contracts = parse_cpp_registry_contracts(errors, case_name, root)
    cpp_baselines = parse_cpp_baseline_capabilities(errors, case_name, root)
    tool_contracts, runtime_contracts = load_package_contracts(errors, case_name, root)
    if not registry_records or not cpp_contracts or not cpp_baselines:
        return

    expected_target_order = list(cpp_contracts)
    expect_equal(
        errors,
        case_name,
        "registry.targets",
        list(registry_records),
        expected_target_order,
    )
    expect_equal(
        errors,
        case_name,
        "tools.package_target_contracts targets",
        list(tool_contracts),
        expected_target_order,
    )
    expect_equal(
        errors,
        case_name,
        "runtime.package_target_contracts targets",
        list(runtime_contracts),
        expected_target_order,
    )
    expect_equal(
        errors,
        case_name,
        "runtime.package_target_contracts",
        runtime_contracts,
        tool_contracts,
    )

    for target in expected_target_order:
        registry_record = registry_records.get(target)
        cpp_contract = cpp_contracts[target]
        package_contract = tool_contracts.get(target)
        if registry_record is None or package_contract is None:
            continue

        package_admission = registry_record.get("packageAdmission", {})
        native_artifact = registry_record.get("nativeArtifact", {})
        registry_requirements = package_admission.get("packageArtifactRequirements", {})
        if not isinstance(package_admission, dict):
            fail(errors, case_name, f"registry {target}.packageAdmission invalid")
            continue
        if not isinstance(native_artifact, dict):
            fail(errors, case_name, f"registry {target}.nativeArtifact invalid")
            continue
        if not isinstance(registry_requirements, dict):
            fail(
                errors,
                case_name,
                f"registry {target}.packageAdmission.packageArtifactRequirements invalid",
            )
            continue

        expected_core_capabilities = sorted(
            [
                cpp_contract.native_artifact_capability,
                f"{target}.optimization.hir-pipeline",
                f"{target}.package-admission.native-source-package",
            ]
        )
        expect_equal(
            errors,
            case_name,
            f"registry {target} core capability ids",
            sorted(registry_core_capability_ids(registry_record)),
            expected_core_capabilities,
        )
        expect_equal(
            errors,
            case_name,
            f"registry {target}.emittedBaselineCapabilities",
            registry_record.get("emittedBaselineCapabilities"),
            cpp_baselines.get(target),
        )
        expect_equal(
            errors,
            case_name,
            f"registry {target}.packageMode",
            registry_record.get("packageMode"),
            cpp_contract.package_mode,
        )
        expect_equal(
            errors,
            case_name,
            f"registry {target}.nativeArtifact.capability",
            native_artifact.get("capability"),
            cpp_contract.native_artifact_capability,
        )
        expect_equal(
            errors,
            case_name,
            f"registry {target}.nativeArtifact.pathArtifacts",
            native_artifact.get("pathArtifacts"),
            package_contract["requiredPathArtifacts"],
        )
        expect_equal(
            errors,
            case_name,
            f"registry {target}.nativeArtifact.requiresNativeBinaryStatus",
            native_artifact.get("requiresNativeBinaryStatus"),
            package_contract["requiresNativeBinaryStatus"],
        )
        expect_equal(
            errors,
            case_name,
            f"registry {target}.nativeArtifact.allowsPlannedNativeBinary",
            native_artifact.get("allowsPlannedNativeBinary"),
            package_contract["allowsPlannedNativeBinary"],
        )
        expect_equal(
            errors,
            case_name,
            f"registry {target}.packageAdmission.packageMode",
            package_admission.get("packageMode"),
            cpp_contract.package_mode,
        )
        expect_equal(
            errors,
            case_name,
            f"registry {target}.packageAdmission.nativeSupportClass",
            package_admission.get("nativeSupportClass"),
            cpp_contract.native_support_class,
        )
        expect_equal(
            errors,
            case_name,
            f"registry {target}.packageAdmission.nativeImplemented",
            package_admission.get("nativeImplemented"),
            cpp_contract.native_implemented,
        )
        expect_equal(
            errors,
            case_name,
            f"registry {target}.packageAdmission.sourcePackageSelectable",
            package_admission.get("sourcePackageSelectable"),
            cpp_contract.source_package_selectable,
        )
        expect_equal(
            errors,
            case_name,
            f"registry {target}.packageAdmission.packageBuildSupported",
            package_admission.get("packageBuildSupported"),
            cpp_contract.package_build_supported,
        )
        expect_equal(
            errors,
            case_name,
            f"registry {target}.packageAdmission.admittedPackageModes",
            package_admission.get("admittedPackageModes"),
            cpp_contract.admitted_package_modes,
        )
        expect_equal(
            errors,
            case_name,
            f"registry {target}.packageAdmission.baselineBackendCapability",
            package_admission.get("baselineBackendCapability"),
            cpp_contract.baseline_backend_capability,
        )
        expect_equal(
            errors,
            case_name,
            f"registry {target}.packageAdmission.nativeArtifactCapability",
            package_admission.get("nativeArtifactCapability"),
            cpp_contract.native_artifact_capability,
        )
        expect_equal(
            errors,
            case_name,
            f"registry {target}.packageAdmission.packageDecisionReason",
            package_admission.get("packageDecisionReason"),
            cpp_contract.package_decision_reason,
        )
        expect_equal(
            errors,
            case_name,
            f"registry {target}.packageAdmission.packageRankScore",
            package_admission.get("packageRankScore"),
            cpp_contract.package_rank_score,
        )
        expect_equal(
            errors,
            case_name,
            f"registry {target}.packageAdmission.packageArtifactRequirementsSource",
            package_admission.get("packageArtifactRequirementsSource"),
            PACKAGE_ARTIFACT_REQUIREMENTS_SOURCE,
        )

        expected_requirements = {
            "packageMode": cpp_contract.package_mode,
            **package_contract,
            "evidenceIds": expected_package_artifact_evidence_ids(
                target, cpp_contract.package_mode, package_contract
            ),
        }
        expected_requirements.pop("target")
        for field, expected in expected_requirements.items():
            expect_equal(
                errors,
                case_name,
                f"registry {target}.packageAdmission.packageArtifactRequirements.{field}",
                registry_requirements.get(field),
                expected,
            )


def check_registry_cli_alignment(
    errors: list[str],
    root: Path,
    case_name: str,
    explanation: dict[str, Any],
) -> None:
    registry = load_json_document(errors, case_name, root / REGISTRY_PATH)
    if not registry:
        return
    registry_records = registry_targets_by_name(errors, case_name, registry)
    explanation_records = records_by_target(explanation.get("targets"))
    expect_equal(
        errors,
        case_name,
        "target-capability registry target order",
        list(registry_records),
        list(explanation_records),
    )

    for target, registry_record in registry_records.items():
        explanation_record = explanation_records.get(target)
        if explanation_record is None:
            continue
        package_admission = registry_record.get("packageAdmission", {})
        if not isinstance(package_admission, dict):
            continue
        expect_equal(
            errors,
            case_name,
            f"explain-targets.targets[{target}].nativeImplemented",
            explanation_record.get("nativeImplemented"),
            package_admission.get("nativeImplemented"),
        )
        expect_contains(
            errors,
            case_name,
            f"explain-targets.targets[{target}].requiredCapabilities",
            explanation_record.get("requiredCapabilities"),
            tuple(registry_record.get("emittedBaselineCapabilities", [])),
        )

        if not package_admission.get("sourcePackageSelectable"):
            continue
        for field in (
            "sourcePackageSupported",
            "packageBuildSupported",
            "packageMode",
            "packageDecisionReason",
            "packageRankScore",
        ):
            expected_field = (
                "sourcePackageSelectable"
                if field == "sourcePackageSupported"
                else field
            )
            expect_equal(
                errors,
                case_name,
                f"explain-targets.targets[{target}].{field}",
                explanation_record.get(field),
                package_admission.get(expected_field),
            )
        expect_equal(
            errors,
            case_name,
            f"explain-targets.targets[{target}].requiredToolIds",
            sorted(explanation_record.get("requiredToolIds", [])),
            sorted(registry_tool_requirement_capabilities(registry_record)),
        )


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
    if case.registry_contract_fixture:
        check_registry_cli_alignment(errors, root, case.name, explanation)
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
            registry_contract_fixture=True,
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
                    package_build_supported=True,
                    source_package_supported=False,
                    package_mode="native",
                    missing_capabilities=(),
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
            recommended_target="metal",
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
    parser.add_argument("--cglc", type=Path)
    args = parser.parse_args()

    root = args.root.resolve()
    errors: list[str] = []

    check_registry_static_contract_alignment(errors, root)
    if args.cglc is None:
        if errors:
            print("target read-only consumer alignment failed:", file=sys.stderr)
            for error in errors:
                print(f"- {error}", file=sys.stderr)
            return 1
        print("validated target registry/package contract alignment")
        return 0

    cglc = args.cglc.resolve()
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
