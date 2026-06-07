#!/usr/bin/env python3
"""Validate report-only optional MLIR tool evidence.

The checker intentionally does not discover MLIR or invoke mlir-opt. It validates
the committed manifest contract and, when given a configured build-tree evidence
file, verifies that missing MLIR is represented as a clean optional skip.
"""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
from pathlib import Path
from typing import Any


MANIFEST_PATH = Path("experimental/mlir/experiment_manifest.json")
CTEST_PATH = Path("tests/cmake/CrossGLMLIRExperimentTests.cmake")
CMAKE_PATH = Path("CMakeLists.txt")
KIND = "crossgl-mlir-optional-tool-evidence-v0"
GATE_OPTION = "CROSSGL_ENABLE_MLIR_EXPERIMENTAL"
GATE_TARGET = "crossgl_mlir_experiment"
VERIFIER_TEST = "cglc_mlir_experiment_minimal_compute_verifier"
EVIDENCE_TEST = "cglc_mlir_optional_tool_evidence"
VERIFIER_INPUT_LIST = "CROSSGL_MLIR_EXPERIMENT_VERIFIER_INPUTS"
VERIFIER_INPUT = "tests/fixtures/mlir/minimal_compute_builtin_module.mlir"
MINIMAL_FIXTURE = "tests/fixtures/MinimalComputeShader.cgl"
SOURCE_RESOURCE_CATALOG = "experimental/mlir/source_resource_catalog.v0.json"
SOURCE_RESOURCE_CATALOG_KIND = "crossgl-mlir-source-resource-catalog-v0"
SOURCE_RESOURCE_CATALOG_CHECKER = "tools/check_mlir_source_resource_catalog.py"
SOURCE_RESOURCE_PRESERVATION_SECTION = "sourceResourceEntrypointPreservation"
OPTION_DEFAULT = "OFF"
OPTION_ACTUAL_VALUES = ("OFF", "ON")
DEFAULT_OFF_BRANCH = f"if(NOT {GATE_OPTION})"
FIND_PROGRAM_COMMAND = "find_program(CROSSGL_MLIR_OPT NAMES mlir-opt)"
VERSION_PROBE_COMMAND = "mlir-opt --version"
STATUS_VALUES = ("default-off", "toolchain-unavailable", "toolchain-available")
TOOL_DISCOVERY_STATUS_VALUES = (
    "not-run-default-off",
    "not-run-toolchain-incomplete",
    "not-found",
    "probe-failed",
    "available",
)
VERIFIER_REGISTRATION_MODES = ("skipped", "executable")
BASE_SKIP_LABELS = {"mlir", "optional-mlir"}
AVAILABLE_TOOL_LABEL = "mlir-tool-available"
UNAVAILABLE_TOOL_LABEL = "mlir-tool-unavailable"
SKIP_REGEX = "^SKIP:"
DEFAULT_OFF_MISSING_REASON = f"{GATE_OPTION}=OFF"
REQUIRED_GATE_FACTS = (
    f"{GATE_OPTION}=ON",
    "MLIR_FOUND=TRUE",
    f"target {GATE_TARGET}",
    VERIFIER_INPUT,
    "mlir-opt discovery",
    "mlir-opt --version probe",
)
REQUIRED_VERIFIER_MARKERS = (
    f'crossgl_fixture = "{MINIMAL_FIXTURE}"',
    'crossgl_entry_point = "main"',
    "crossgl_source_location_fact_source_file = true",
    "crossgl_source_location_fact_shader_module = true",
    "crossgl_source_location_fact_compute_stage = true",
    "crossgl_source_location_fact_entry_point = true",
    "crossgl_source_location_fact_layout_local_size = true",
    "crossgl_source_location_fact_return_statement = true",
    "crossgl_type_fact_void_entry_point = true",
    "crossgl_resource_count = 0",
    'crossgl_resource_metadata = "target-independent:none"',
    "crossgl_real_mlir_smoke = true",
)
REQUIRED_VERIFIER_FACT_MARKERS = (
    "crossgl_source_location_fact_source_file",
    "crossgl_source_location_fact_shader_module",
    "crossgl_source_location_fact_compute_stage",
    "crossgl_source_location_fact_entry_point",
    "crossgl_source_location_fact_layout_local_size",
    "crossgl_source_location_fact_return_statement",
    "crossgl_type_fact_void_entry_point",
)
FORBIDDEN_VERIFIER_MARKERS = (
    "CrossGL pseudo-MLIR",
    'crossgl.real_mlir = "false"',
    "not a registered MLIR dialect",
)


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def load_json(path: Path) -> Any:
    try:
        return json.loads(read_text(path))
    except json.JSONDecodeError as error:
        raise ValueError(f"invalid JSON: {error}") from error


def require_object(value: object, field: str, errors: list[str]) -> dict[str, Any]:
    if not isinstance(value, dict):
        errors.append(f"{field} must be an object")
        return {}
    return value


def require_string(value: object, field: str, errors: list[str]) -> str | None:
    if not isinstance(value, str) or not value:
        errors.append(f"{field} must be a non-empty string")
        return None
    return value


def require_optional_string(value: object, field: str, errors: list[str]) -> str | None:
    if value is None:
        return None
    if isinstance(value, str):
        return value
    errors.append(f"{field} must be a string or null")
    return None


def require_bool(value: object, field: str, errors: list[str]) -> bool | None:
    if not isinstance(value, bool):
        errors.append(f"{field} must be a boolean")
        return None
    return value


def require_list(value: object, field: str, errors: list[str]) -> list[Any]:
    if not isinstance(value, list) or not value:
        errors.append(f"{field} must be a non-empty list")
        return []
    return value


def require_string_list(value: object, field: str, errors: list[str]) -> list[str]:
    values = require_list(value, field, errors)
    strings: list[str] = []
    for index, item in enumerate(values):
        if isinstance(item, str) and item:
            strings.append(item)
        else:
            errors.append(f"{field}[{index}] must be a non-empty string")
    return strings


def require_string_list_allow_empty(
    value: object, field: str, errors: list[str]
) -> list[str]:
    if not isinstance(value, list):
        errors.append(f"{field} must be a list")
        return []
    strings: list[str] = []
    for index, item in enumerate(value):
        if isinstance(item, str) and item:
            strings.append(item)
        else:
            errors.append(f"{field}[{index}] must be a non-empty string")
    return strings


def validate_relative_path(value: object, field: str, errors: list[str]) -> str | None:
    path_text = require_string(value, field, errors)
    if path_text is None:
        return None
    if "\\" in path_text:
        errors.append(f"{field} must use POSIX separators")
        return None
    path = Path(path_text)
    if path.is_absolute() or any(part in {"", ".", ".."} for part in path.parts):
        errors.append(f"{field} must be repository-relative without dot segments")
        return None
    return path_text


def find_verifier_manifest_record(
    manifest: dict[str, Any], errors: list[str]
) -> dict[str, Any]:
    checks = require_list(
        manifest.get("optionalToolGatedChecks"),
        f"{MANIFEST_PATH}: optionalToolGatedChecks",
        errors,
    )
    for index, item in enumerate(checks):
        record = require_object(
            item, f"{MANIFEST_PATH}: optionalToolGatedChecks[{index}]", errors
        )
        if record.get("name") == VERIFIER_TEST:
            return record
    errors.append(
        f"{MANIFEST_PATH}: optionalToolGatedChecks must include {VERIFIER_TEST!r}"
    )
    return {}


def check_manifest_contract(root: Path, errors: list[str]) -> None:
    path = root / MANIFEST_PATH
    if not path.exists():
        errors.append(f"missing {MANIFEST_PATH}")
        return
    try:
        manifest = load_json(path)
    except ValueError as error:
        errors.append(f"{MANIFEST_PATH}: {error}")
        return
    if not isinstance(manifest, dict):
        errors.append(f"{MANIFEST_PATH}: manifest must be an object")
        return

    record = find_verifier_manifest_record(manifest, errors)
    evidence = require_object(
        record.get("evidenceRecord"),
        f"{MANIFEST_PATH}: optionalToolGatedChecks[{VERIFIER_TEST}].evidenceRecord",
        errors,
    )
    expected_scalars: dict[str, object] = {
        "kind": KIND,
        "generatedPath": "mlir/optional_tool_evidence.v0.json",
        "generatedBy": CTEST_PATH.as_posix(),
        "checker": "tools/check_mlir_optional_tool_evidence.py",
        "normalBuildRequired": False,
        "productionLinked": False,
    }
    for key, expected in expected_scalars.items():
        if evidence.get(key) != expected:
            errors.append(
                f"{MANIFEST_PATH}: {VERIFIER_TEST}.evidenceRecord.{key} "
                f"must be {expected!r}"
            )

    status_values = require_string_list(
        evidence.get("statusValues"),
        f"{MANIFEST_PATH}: {VERIFIER_TEST}.evidenceRecord.statusValues",
        errors,
    )
    if status_values != list(STATUS_VALUES):
        errors.append(
            f"{MANIFEST_PATH}: {VERIFIER_TEST}.evidenceRecord.statusValues "
            f"must be {list(STATUS_VALUES)!r}"
        )

    records = set(
        require_string_list(
            evidence.get("records"),
            f"{MANIFEST_PATH}: {VERIFIER_TEST}.evidenceRecord.records",
            errors,
        )
    )
    required_records = {
        f"{GATE_OPTION} default",
        f"{GATE_OPTION} actual",
        "MLIR_FOUND",
        f"target {GATE_TARGET}",
        VERIFIER_INPUT_LIST,
        "mlir-opt discovery",
        "default-off no mlir-opt probe proof",
        "CTest skip labels and regex",
        "structured verifier skip diagnostics",
        "report-only source/resource catalog",
        "source/resource/entrypoint preservation fields",
    }
    missing = sorted(required_records - records)
    if missing:
        errors.append(
            f"{MANIFEST_PATH}: {VERIFIER_TEST}.evidenceRecord.records "
            "missing " + ", ".join(missing)
        )


def check_cmake_metadata_contract(root: Path, errors: list[str]) -> None:
    ctest_path = root / CTEST_PATH
    cmake_path = root / CMAKE_PATH
    if not ctest_path.exists():
        errors.append(f"missing {CTEST_PATH}")
        return
    if not cmake_path.exists():
        errors.append(f"missing {CMAKE_PATH}")
        return
    ctest_text = read_text(ctest_path)
    cmake_text = read_text(cmake_path)
    for token in (
        "CROSSGL_MLIR_EXPERIMENT_OPTIONAL_TOOL_EVIDENCE",
        "optional_tool_evidence.v0.json",
        KIND,
        "mlirDiscovery",
        "optionDefault",
        "optionActual",
        "verifierInput",
        "verifierTool",
        "verifierRegistration",
        "invokesMlirOpt",
        "usesVerifyDiagnostics",
        "buildsExperimentTarget",
        "requiredFiles",
        "reportOnlyCatalogs",
        "sourceResourceCatalog",
        SOURCE_RESOURCE_CATALOG,
        SOURCE_RESOURCE_CATALOG_CHECKER,
        SOURCE_RESOURCE_PRESERVATION_SECTION,
        "toolProbeEvidence",
        "defaultOffMayRunFindProgram",
        "defaultOffMayRunVersionProbe",
        "skipEvidence",
        "skipDiagnostics",
        "missingReasons",
        "findProgramAttempted",
        "versionProbeAttempted",
        "CROSSGL_MLIR_EXPERIMENT_MINIMAL_VERIFY_REQUIRED_MARKERS",
        "CROSSGL_MLIR_EXPERIMENT_MINIMAL_VERIFY_OUTPUT_MARKERS",
        "crossgl_mlir_json_string_list",
        "tools/check_mlir_optional_tool_evidence.py",
        EVIDENCE_TEST,
        "--evidence",
        AVAILABLE_TOOL_LABEL,
        UNAVAILABLE_TOOL_LABEL,
    ):
        if token not in ctest_text:
            errors.append(
                f"{CTEST_PATH}: missing optional-tool evidence token {token!r}"
            )

    default_condition = f"if(NOT {GATE_OPTION})"
    default_start = ctest_text.find(default_condition)
    default_else = ctest_text.find("\nelse()", default_start)
    if default_start == -1 or default_else == -1:
        errors.append(f"{CTEST_PATH}: missing default-off verifier branch")
    else:
        default_body = ctest_text[default_start:default_else]
        for forbidden in ("find_program(", "mlir-opt", "MLIR_OPT"):
            if forbidden in default_body:
                errors.append(
                    f"{CTEST_PATH}: default-off branch must not probe optional "
                    f"MLIR tooling via {forbidden!r}"
                )

    for token in (
        f"set({VERIFIER_INPUT_LIST}",
        VERIFIER_INPUT,
    ):
        if token not in cmake_text:
            errors.append(f"{CMAKE_PATH}: missing verifier input authority {token!r}")

    for token in REQUIRED_VERIFIER_FACT_MARKERS:
        if token not in ctest_text:
            errors.append(
                f"{CTEST_PATH}: missing fact-preservation verifier token {token!r}"
            )


def check_verifier_input_markers(root: Path, errors: list[str]) -> None:
    path = root / VERIFIER_INPUT
    if not path.exists():
        errors.append(f"missing MLIR verifier input {VERIFIER_INPUT}")
        return
    text = read_text(path)
    for marker in REQUIRED_VERIFIER_MARKERS:
        if marker not in text:
            errors.append(
                f"{VERIFIER_INPUT}: missing required fact-preservation marker "
                f"{marker!r}"
            )
    for marker in FORBIDDEN_VERIFIER_MARKERS:
        if marker in text:
            errors.append(f"{VERIFIER_INPUT}: contains pseudo-MLIR marker {marker!r}")


def check_evidence_file(root: Path, evidence_path: Path, errors: list[str]) -> None:
    if not evidence_path.exists():
        errors.append(f"optional MLIR evidence file missing: {evidence_path}")
        return
    try:
        evidence = load_json(evidence_path)
    except ValueError as error:
        errors.append(f"{evidence_path}: {error}")
        return
    evidence = require_object(evidence, str(evidence_path), errors)
    if evidence.get("schemaVersion") != 1:
        errors.append(f"{evidence_path}: schemaVersion must be 1")
    if evidence.get("kind") != KIND:
        errors.append(f"{evidence_path}: kind must be {KIND!r}")
    status = require_string(evidence.get("status"), f"{evidence_path}: status", errors)
    if status is not None and status not in STATUS_VALUES:
        errors.append(
            f"{evidence_path}: status must be one of {', '.join(STATUS_VALUES)}"
        )
    if evidence.get("normalBuildRequired") is not False:
        errors.append(f"{evidence_path}: normalBuildRequired must be false")
    if evidence.get("productionLinked") is not False:
        errors.append(f"{evidence_path}: productionLinked must be false")

    discovery = require_object(
        evidence.get("mlirDiscovery"), f"{evidence_path}: mlirDiscovery", errors
    )
    option_enabled = require_bool(
        discovery.get("optionEnabled"),
        f"{evidence_path}: mlirDiscovery.optionEnabled",
        errors,
    )
    option_default = require_string(
        discovery.get("optionDefault"),
        f"{evidence_path}: mlirDiscovery.optionDefault",
        errors,
    )
    option_actual = require_string(
        discovery.get("optionActual"),
        f"{evidence_path}: mlirDiscovery.optionActual",
        errors,
    )
    mlir_found = require_bool(
        discovery.get("mlirFound"), f"{evidence_path}: mlirDiscovery.mlirFound", errors
    )
    target_created = require_bool(
        discovery.get("targetCreated"),
        f"{evidence_path}: mlirDiscovery.targetCreated",
        errors,
    )
    expected_discovery: dict[str, object] = {
        "cmakeOption": GATE_OPTION,
        "cmakePackage": "MLIR",
        "target": GATE_TARGET,
    }
    for key, expected in expected_discovery.items():
        if discovery.get(key) != expected:
            errors.append(f"{evidence_path}: mlirDiscovery.{key} must be {expected!r}")
    if option_default is not None and option_default != OPTION_DEFAULT:
        errors.append(
            f"{evidence_path}: mlirDiscovery.optionDefault must be {OPTION_DEFAULT!r}"
        )
    if option_actual is not None and option_actual not in OPTION_ACTUAL_VALUES:
        errors.append(
            f"{evidence_path}: mlirDiscovery.optionActual must be one of "
            f"{', '.join(OPTION_ACTUAL_VALUES)}"
        )
    if option_enabled is not None and option_actual is not None:
        expected_actual = "ON" if option_enabled else "OFF"
        if option_actual != expected_actual:
            errors.append(
                f"{evidence_path}: mlirDiscovery.optionActual must match "
                "mlirDiscovery.optionEnabled"
            )

    verifier_input = require_object(
        evidence.get("verifierInput"), f"{evidence_path}: verifierInput", errors
    )
    input_path = validate_relative_path(
        verifier_input.get("path"), f"{evidence_path}: verifierInput.path", errors
    )
    if input_path != VERIFIER_INPUT:
        errors.append(f"{evidence_path}: verifierInput.path must be {VERIFIER_INPUT!r}")
    if verifier_input.get("fixture") != MINIMAL_FIXTURE:
        errors.append(
            f"{evidence_path}: verifierInput.fixture must be {MINIMAL_FIXTURE!r}"
        )
    if verifier_input.get("sourceList") != VERIFIER_INPUT_LIST:
        errors.append(
            f"{evidence_path}: verifierInput.sourceList must be {VERIFIER_INPUT_LIST!r}"
        )
    input_present = require_bool(
        verifier_input.get("present"),
        f"{evidence_path}: verifierInput.present",
        errors,
    )
    if input_path is not None and input_present != (root / input_path).exists():
        errors.append(
            f"{evidence_path}: verifierInput.present must match repository fixture "
            f"presence for {input_path}"
        )

    tool = require_object(
        evidence.get("verifierTool"), f"{evidence_path}: verifierTool", errors
    )
    tool_found = require_bool(
        tool.get("found"), f"{evidence_path}: verifierTool.found", errors
    )
    discovery_status = require_string(
        tool.get("discoveryStatus"),
        f"{evidence_path}: verifierTool.discoveryStatus",
        errors,
    )
    if (
        discovery_status is not None
        and discovery_status not in TOOL_DISCOVERY_STATUS_VALUES
    ):
        errors.append(
            f"{evidence_path}: verifierTool.discoveryStatus must be one of "
            + ", ".join(TOOL_DISCOVERY_STATUS_VALUES)
        )
    if tool.get("name") != "mlir-opt":
        errors.append(f"{evidence_path}: verifierTool.name must be 'mlir-opt'")
    if tool.get("requiredForNormalBuild") is not False:
        errors.append(
            f"{evidence_path}: verifierTool.requiredForNormalBuild must be false"
        )
    tool_path = require_optional_string(
        tool.get("path"), f"{evidence_path}: verifierTool.path", errors
    )
    if tool_found is False and tool_path is not None:
        errors.append(f"{evidence_path}: verifierTool.path must be null when not found")
    if tool_found is True and not tool_path:
        errors.append(f"{evidence_path}: verifierTool.path must be recorded when found")

    registration = require_object(
        evidence.get("verifierRegistration"),
        f"{evidence_path}: verifierRegistration",
        errors,
    )
    if registration.get("ctest") != VERIFIER_TEST:
        errors.append(
            f"{evidence_path}: verifierRegistration.ctest must be {VERIFIER_TEST!r}"
        )
    registration_mode = require_string(
        registration.get("mode"),
        f"{evidence_path}: verifierRegistration.mode",
        errors,
    )
    if (
        registration_mode is not None
        and registration_mode not in VERIFIER_REGISTRATION_MODES
    ):
        errors.append(
            f"{evidence_path}: verifierRegistration.mode must be one of "
            + ", ".join(VERIFIER_REGISTRATION_MODES)
        )
    invokes_mlir_opt = require_bool(
        registration.get("invokesMlirOpt"),
        f"{evidence_path}: verifierRegistration.invokesMlirOpt",
        errors,
    )
    uses_verify_diagnostics = require_bool(
        registration.get("usesVerifyDiagnostics"),
        f"{evidence_path}: verifierRegistration.usesVerifyDiagnostics",
        errors,
    )
    builds_experiment_target = require_bool(
        registration.get("buildsExperimentTarget"),
        f"{evidence_path}: verifierRegistration.buildsExperimentTarget",
        errors,
    )
    build_target = require_optional_string(
        registration.get("buildTarget"),
        f"{evidence_path}: verifierRegistration.buildTarget",
        errors,
    )
    registration_input = validate_relative_path(
        registration.get("input"),
        f"{evidence_path}: verifierRegistration.input",
        errors,
    )
    if registration_input != VERIFIER_INPUT:
        errors.append(
            f"{evidence_path}: verifierRegistration.input must be {VERIFIER_INPUT!r}"
        )
    required_files = require_string_list_allow_empty(
        registration.get("requiredFiles"),
        f"{evidence_path}: verifierRegistration.requiredFiles",
        errors,
    )
    if registration.get("normalBuildRequired") is not False:
        errors.append(
            f"{evidence_path}: verifierRegistration.normalBuildRequired must be false"
        )
    if registration.get("productionLinked") is not False:
        errors.append(
            f"{evidence_path}: verifierRegistration.productionLinked must be false"
        )

    report_only_catalogs = require_object(
        evidence.get("reportOnlyCatalogs"),
        f"{evidence_path}: reportOnlyCatalogs",
        errors,
    )
    source_resource_catalog = require_object(
        report_only_catalogs.get("sourceResourceCatalog"),
        f"{evidence_path}: reportOnlyCatalogs.sourceResourceCatalog",
        errors,
    )
    catalog_path = validate_relative_path(
        source_resource_catalog.get("path"),
        f"{evidence_path}: reportOnlyCatalogs.sourceResourceCatalog.path",
        errors,
    )
    expected_catalog_scalars: dict[str, object] = {
        "checker": SOURCE_RESOURCE_CATALOG_CHECKER,
        "requiredFixtureSection": SOURCE_RESOURCE_PRESERVATION_SECTION,
        "optionalMlirToolingRequired": False,
        "normalBuildRequired": False,
        "productionLinked": False,
    }
    for key, expected in expected_catalog_scalars.items():
        if source_resource_catalog.get(key) != expected:
            errors.append(
                f"{evidence_path}: reportOnlyCatalogs.sourceResourceCatalog.{key} "
                f"must be {expected!r}"
            )
    if catalog_path != SOURCE_RESOURCE_CATALOG:
        errors.append(
            f"{evidence_path}: reportOnlyCatalogs.sourceResourceCatalog.path "
            f"must be {SOURCE_RESOURCE_CATALOG!r}"
        )
    if catalog_path is not None:
        full_catalog_path = root / catalog_path
        if not full_catalog_path.exists():
            errors.append(
                f"{evidence_path}: reportOnlyCatalogs.sourceResourceCatalog.path "
                f"does not exist: {catalog_path}"
            )
        else:
            try:
                catalog = load_json(full_catalog_path)
            except ValueError as error:
                errors.append(f"{catalog_path}: {error}")
                catalog = {}
            catalog = require_object(catalog, str(catalog_path), errors)
            if catalog.get("kind") != SOURCE_RESOURCE_CATALOG_KIND:
                errors.append(
                    f"{catalog_path}: kind must be {SOURCE_RESOURCE_CATALOG_KIND!r}"
                )
            fixtures = require_list(
                catalog.get("fixtures"), f"{catalog_path}: fixtures", errors
            )
            for index, item in enumerate(fixtures):
                fixture = require_object(
                    item, f"{catalog_path}: fixtures[{index}]", errors
                )
                preservation = require_object(
                    fixture.get(SOURCE_RESOURCE_PRESERVATION_SECTION),
                    f"{catalog_path}: fixtures[{index}]."
                    f"{SOURCE_RESOURCE_PRESERVATION_SECTION}",
                    errors,
                )
                if preservation.get("missingManifestFields") != []:
                    errors.append(
                        f"{catalog_path}: fixtures[{index}]."
                        f"{SOURCE_RESOURCE_PRESERVATION_SECTION}."
                        "missingManifestFields must be empty"
                    )

    tool_probe = require_object(
        evidence.get("toolProbeEvidence"),
        f"{evidence_path}: toolProbeEvidence",
        errors,
    )
    if tool_probe.get("defaultOffBranch") != DEFAULT_OFF_BRANCH:
        errors.append(
            f"{evidence_path}: toolProbeEvidence.defaultOffBranch must be "
            f"{DEFAULT_OFF_BRANCH!r}"
        )
    if tool_probe.get("findProgramCommand") != FIND_PROGRAM_COMMAND:
        errors.append(
            f"{evidence_path}: toolProbeEvidence.findProgramCommand must be "
            f"{FIND_PROGRAM_COMMAND!r}"
        )
    if tool_probe.get("versionProbeCommand") != VERSION_PROBE_COMMAND:
        errors.append(
            f"{evidence_path}: toolProbeEvidence.versionProbeCommand must be "
            f"{VERSION_PROBE_COMMAND!r}"
        )
    if tool_probe.get("defaultOffMayRunFindProgram") is not False:
        errors.append(
            f"{evidence_path}: toolProbeEvidence.defaultOffMayRunFindProgram "
            "must be false"
        )
    if tool_probe.get("defaultOffMayRunVersionProbe") is not False:
        errors.append(
            f"{evidence_path}: toolProbeEvidence.defaultOffMayRunVersionProbe "
            "must be false"
        )
    tool_probe_find_program_attempted = require_bool(
        tool_probe.get("findProgramAttempted"),
        f"{evidence_path}: toolProbeEvidence.findProgramAttempted",
        errors,
    )
    tool_probe_version_probe_attempted = require_bool(
        tool_probe.get("versionProbeAttempted"),
        f"{evidence_path}: toolProbeEvidence.versionProbeAttempted",
        errors,
    )

    skip = require_object(
        evidence.get("skipEvidence"), f"{evidence_path}: skipEvidence", errors
    )
    skip_registered = require_bool(
        skip.get("skipRegistered"),
        f"{evidence_path}: skipEvidence.skipRegistered",
        errors,
    )
    labels = set(
        require_string_list(
            skip.get("labels"), f"{evidence_path}: skipEvidence.labels", errors
        )
    )
    if BASE_SKIP_LABELS - labels:
        errors.append(
            f"{evidence_path}: skipEvidence.labels must include mlir and optional-mlir"
        )
    if AVAILABLE_TOOL_LABEL in labels and UNAVAILABLE_TOOL_LABEL in labels:
        errors.append(
            f"{evidence_path}: skipEvidence.labels must not mix "
            f"{AVAILABLE_TOOL_LABEL} and {UNAVAILABLE_TOOL_LABEL}"
        )
    if skip.get("ctest") != VERIFIER_TEST:
        errors.append(f"{evidence_path}: skipEvidence.ctest must be {VERIFIER_TEST!r}")
    reason = require_optional_string(
        skip.get("reason"), f"{evidence_path}: skipEvidence.reason", errors
    )
    skip_regex = require_optional_string(
        skip.get("skipRegularExpression"),
        f"{evidence_path}: skipEvidence.skipRegularExpression",
        errors,
    )
    if skip_registered is True and skip_regex != SKIP_REGEX:
        errors.append(
            f"{evidence_path}: skipped optional MLIR verifier evidence must use "
            f"skip regex {SKIP_REGEX!r}"
        )
    if skip_registered is False and skip_regex not in (None, ""):
        errors.append(
            f"{evidence_path}: available optional MLIR verifier evidence must not "
            "carry a skip regex"
        )

    skip_diagnostics = require_object(
        evidence.get("skipDiagnostics"), f"{evidence_path}: skipDiagnostics", errors
    )
    diagnostics_status = require_string(
        skip_diagnostics.get("status"),
        f"{evidence_path}: skipDiagnostics.status",
        errors,
    )
    if (
        status is not None
        and diagnostics_status is not None
        and diagnostics_status != status
    ):
        errors.append(
            f"{evidence_path}: skipDiagnostics.status must match top-level status"
        )
    if skip_diagnostics.get("reportOnly") is not True:
        errors.append(f"{evidence_path}: skipDiagnostics.reportOnly must be true")
    required_gate_facts = require_string_list(
        skip_diagnostics.get("requiredGateFacts"),
        f"{evidence_path}: skipDiagnostics.requiredGateFacts",
        errors,
    )
    if required_gate_facts != list(REQUIRED_GATE_FACTS):
        errors.append(
            f"{evidence_path}: skipDiagnostics.requiredGateFacts must be "
            f"{list(REQUIRED_GATE_FACTS)!r}"
        )
    missing_reasons = require_string_list_allow_empty(
        skip_diagnostics.get("missingReasons"),
        f"{evidence_path}: skipDiagnostics.missingReasons",
        errors,
    )
    find_program_attempted = require_bool(
        skip_diagnostics.get("findProgramAttempted"),
        f"{evidence_path}: skipDiagnostics.findProgramAttempted",
        errors,
    )
    version_probe_attempted = require_bool(
        skip_diagnostics.get("versionProbeAttempted"),
        f"{evidence_path}: skipDiagnostics.versionProbeAttempted",
        errors,
    )
    if (
        tool_probe_find_program_attempted is not None
        and find_program_attempted is not None
        and tool_probe_find_program_attempted != find_program_attempted
    ):
        errors.append(
            f"{evidence_path}: toolProbeEvidence.findProgramAttempted must match "
            "skipDiagnostics.findProgramAttempted"
        )
    if (
        tool_probe_version_probe_attempted is not None
        and version_probe_attempted is not None
        and tool_probe_version_probe_attempted != version_probe_attempted
    ):
        errors.append(
            f"{evidence_path}: toolProbeEvidence.versionProbeAttempted must match "
            "skipDiagnostics.versionProbeAttempted"
        )
    if version_probe_attempted is True and find_program_attempted is not True:
        errors.append(
            f"{evidence_path}: skipDiagnostics.versionProbeAttempted requires "
            "findProgramAttempted=true"
        )
    if skip_registered is True:
        if not missing_reasons:
            errors.append(
                f"{evidence_path}: skipped optional MLIR verifier evidence must "
                "record missing reasons"
            )
        if reason is not None:
            for missing_reason in missing_reasons:
                if missing_reason not in reason:
                    errors.append(
                        f"{evidence_path}: skipDiagnostics.missingReasons item "
                        f"{missing_reason!r} must appear in skipEvidence.reason"
                    )
    if skip_registered is False and missing_reasons:
        errors.append(
            f"{evidence_path}: available optional MLIR verifier evidence must not "
            "record missing reasons"
        )
    if registration_mode == "skipped":
        if skip_registered is not True:
            errors.append(
                f"{evidence_path}: skipped verifier registration must match "
                "skipRegistered=true"
            )
        if invokes_mlir_opt is not False:
            errors.append(
                f"{evidence_path}: skipped verifier registration must not invoke "
                "mlir-opt"
            )
        if uses_verify_diagnostics is not False:
            errors.append(
                f"{evidence_path}: skipped verifier registration must not use "
                "--verify-diagnostics"
            )
        if builds_experiment_target is not False:
            errors.append(
                f"{evidence_path}: skipped verifier registration must not build "
                f"{GATE_TARGET}"
            )
        if build_target is not None:
            errors.append(
                f"{evidence_path}: skipped verifier registration buildTarget "
                "must be null"
            )
        if required_files:
            errors.append(
                f"{evidence_path}: skipped verifier registration requiredFiles "
                "must be empty"
            )
    elif registration_mode == "executable":
        if skip_registered is not False:
            errors.append(
                f"{evidence_path}: executable verifier registration must match "
                "skipRegistered=false"
            )
        if invokes_mlir_opt is not True:
            errors.append(
                f"{evidence_path}: executable verifier registration must invoke "
                "mlir-opt"
            )
        if uses_verify_diagnostics is not True:
            errors.append(
                f"{evidence_path}: executable verifier registration must use "
                "--verify-diagnostics"
            )
        if builds_experiment_target is not True:
            errors.append(
                f"{evidence_path}: executable verifier registration must build "
                f"{GATE_TARGET}"
            )
        if build_target != GATE_TARGET:
            errors.append(
                f"{evidence_path}: executable verifier registration buildTarget "
                f"must be {GATE_TARGET!r}"
            )
        if required_files != [VERIFIER_INPUT]:
            errors.append(
                f"{evidence_path}: executable verifier registration requiredFiles "
                f"must be {[VERIFIER_INPUT]!r}"
            )

    if status == "default-off":
        if option_enabled is not False:
            errors.append(
                f"{evidence_path}: default-off status requires optionEnabled=false"
            )
        if target_created is not False:
            errors.append(
                f"{evidence_path}: default-off status must not create {GATE_TARGET}"
            )
        if discovery_status != "not-run-default-off":
            errors.append(
                f"{evidence_path}: default-off status must record not-run-default-off"
            )
        if skip_registered is not True:
            errors.append(f"{evidence_path}: default-off status must register a skip")
        if reason is None or f"{GATE_OPTION}=OFF" not in reason:
            errors.append(
                f"{evidence_path}: default-off skip must report {GATE_OPTION}=OFF"
            )
        if missing_reasons != [DEFAULT_OFF_MISSING_REASON]:
            errors.append(
                f"{evidence_path}: default-off skip diagnostics must record only "
                f"{DEFAULT_OFF_MISSING_REASON!r}"
            )
        if find_program_attempted is not False:
            errors.append(
                f"{evidence_path}: default-off skip diagnostics must not run "
                "find_program"
            )
        if tool_probe_find_program_attempted is not False:
            errors.append(
                f"{evidence_path}: default-off tool probe evidence must not run "
                "find_program"
            )
        if version_probe_attempted is not False:
            errors.append(
                f"{evidence_path}: default-off skip diagnostics must not probe "
                "mlir-opt --version"
            )
        if tool_probe_version_probe_attempted is not False:
            errors.append(
                f"{evidence_path}: default-off tool probe evidence must not probe "
                "mlir-opt --version"
            )
        if UNAVAILABLE_TOOL_LABEL not in labels:
            errors.append(
                f"{evidence_path}: default-off labels must include "
                f"{UNAVAILABLE_TOOL_LABEL}"
            )
        if AVAILABLE_TOOL_LABEL in labels:
            errors.append(
                f"{evidence_path}: default-off labels must not include "
                f"{AVAILABLE_TOOL_LABEL}"
            )
        if registration_mode != "skipped":
            errors.append(
                f"{evidence_path}: default-off status must record skipped verifier "
                "registration"
            )
    elif status == "toolchain-unavailable":
        if option_enabled is not True:
            errors.append(
                f"{evidence_path}: toolchain-unavailable requires optionEnabled=true"
            )
        if skip_registered is not True:
            errors.append(
                f"{evidence_path}: toolchain-unavailable status must register a skip"
            )
        if reason is None or not reason:
            errors.append(
                f"{evidence_path}: toolchain-unavailable skip must explain why"
            )
        if not missing_reasons:
            errors.append(
                f"{evidence_path}: toolchain-unavailable skip diagnostics must "
                "record missing reasons"
            )
        if DEFAULT_OFF_MISSING_REASON in missing_reasons:
            errors.append(
                f"{evidence_path}: toolchain-unavailable skip diagnostics must not "
                f"record {DEFAULT_OFF_MISSING_REASON!r}"
            )
        if discovery_status == "not-run-toolchain-incomplete":
            if find_program_attempted is not False:
                errors.append(
                    f"{evidence_path}: incomplete toolchain skip must not probe "
                    "mlir-opt"
                )
            if version_probe_attempted is not False:
                errors.append(
                    f"{evidence_path}: incomplete toolchain skip must not probe "
                    "mlir-opt --version"
                )
        if discovery_status in {"not-found", "probe-failed"}:
            if find_program_attempted is not True:
                errors.append(
                    f"{evidence_path}: mlir-opt unavailable diagnostics must record "
                    "findProgramAttempted=true"
                )
        if discovery_status == "not-found" and version_probe_attempted is not False:
            errors.append(
                f"{evidence_path}: mlir-opt not-found diagnostics must not record "
                "versionProbeAttempted=true"
            )
        if discovery_status == "probe-failed" and version_probe_attempted is not True:
            errors.append(
                f"{evidence_path}: mlir-opt probe-failed diagnostics must record "
                "versionProbeAttempted=true"
            )
        if discovery_status == "available":
            errors.append(
                f"{evidence_path}: toolchain-unavailable cannot record available tool"
            )
        if UNAVAILABLE_TOOL_LABEL not in labels:
            errors.append(
                f"{evidence_path}: toolchain-unavailable labels must include "
                f"{UNAVAILABLE_TOOL_LABEL}"
            )
        if AVAILABLE_TOOL_LABEL in labels:
            errors.append(
                f"{evidence_path}: toolchain-unavailable labels must not include "
                f"{AVAILABLE_TOOL_LABEL}"
            )
        if registration_mode != "skipped":
            errors.append(
                f"{evidence_path}: toolchain-unavailable status must record skipped "
                "verifier registration"
            )
    elif status == "toolchain-available":
        if not (option_enabled and mlir_found and target_created and input_present):
            errors.append(
                f"{evidence_path}: toolchain-available requires enabled option, "
                "MLIR_FOUND, target creation, and verifier input"
            )
        if tool_found is not True or discovery_status != "available":
            errors.append(
                f"{evidence_path}: toolchain-available requires mlir-opt availability"
            )
        if skip_registered is not False:
            errors.append(
                f"{evidence_path}: toolchain-available must not register a skip"
            )
        if reason not in (None, ""):
            errors.append(
                f"{evidence_path}: toolchain-available must not carry a skip reason"
            )
        if missing_reasons:
            errors.append(
                f"{evidence_path}: toolchain-available skip diagnostics must have "
                "no missing reasons"
            )
        if find_program_attempted is not True:
            errors.append(
                f"{evidence_path}: toolchain-available diagnostics must record "
                "findProgramAttempted=true"
            )
        if version_probe_attempted is not True:
            errors.append(
                f"{evidence_path}: toolchain-available diagnostics must record "
                "versionProbeAttempted=true"
            )
        if AVAILABLE_TOOL_LABEL not in labels:
            errors.append(
                f"{evidence_path}: toolchain-available labels must include "
                f"{AVAILABLE_TOOL_LABEL}"
            )
        if UNAVAILABLE_TOOL_LABEL in labels:
            errors.append(
                f"{evidence_path}: toolchain-available labels must not include "
                f"{UNAVAILABLE_TOOL_LABEL}"
            )
        if registration_mode != "executable":
            errors.append(
                f"{evidence_path}: toolchain-available status must record "
                "executable verifier registration"
            )


def run_checks(root: Path, evidence: Path | None) -> list[str]:
    errors: list[str] = []
    check_manifest_contract(root, errors)
    check_cmake_metadata_contract(root, errors)
    check_verifier_input_markers(root, errors)
    if evidence is not None:
        check_evidence_file(root, evidence, errors)
    return errors


def minimal_verifier_input_text() -> str:
    return (
        "// Builtin-MLIR verifier smoke fixture for the optional CrossGL MLIR "
        "experiment.\n"
        "// It intentionally uses only builtin module syntax and metadata "
        "attributes.\n"
        "module attributes {\n  "
        + ",\n  ".join(REQUIRED_VERIFIER_MARKERS)
        + "\n} {\n}\n"
    )


def cmake_quote(value: str) -> str:
    return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'


def cmake_string_list(name: str, values: tuple[str, ...]) -> str:
    lines = [f"set({name}"]
    lines.extend(f"  {cmake_quote(value)}" for value in values)
    lines.append(")")
    return "\n".join(lines)


def write_minimal_repo(root: Path) -> Path:
    (root / MANIFEST_PATH.parent).mkdir(parents=True, exist_ok=True)
    (root / CTEST_PATH.parent).mkdir(parents=True, exist_ok=True)
    (root / VERIFIER_INPUT).parent.mkdir(parents=True, exist_ok=True)
    (root / VERIFIER_INPUT).write_text(minimal_verifier_input_text(), encoding="utf-8")
    (root / SOURCE_RESOURCE_CATALOG).parent.mkdir(parents=True, exist_ok=True)
    (root / SOURCE_RESOURCE_CATALOG).write_text(
        json.dumps(
            {
                "kind": SOURCE_RESOURCE_CATALOG_KIND,
                "fixtures": [
                    {
                        "sourceResourceEntrypointPreservation": {
                            "missingManifestFields": []
                        }
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    (root / CMAKE_PATH).write_text(
        f"""
set({VERIFIER_INPUT_LIST}
  {VERIFIER_INPUT}
)
""",
        encoding="utf-8",
    )
    (root / MANIFEST_PATH).write_text(
        json.dumps(
            {
                "optionalToolGatedChecks": [
                    {
                        "name": VERIFIER_TEST,
                        "evidenceRecord": {
                            "kind": KIND,
                            "generatedPath": "mlir/optional_tool_evidence.v0.json",
                            "generatedBy": CTEST_PATH.as_posix(),
                            "checker": "tools/check_mlir_optional_tool_evidence.py",
                            "statusValues": list(STATUS_VALUES),
                            "records": [
                                GATE_OPTION,
                                f"{GATE_OPTION} default",
                                f"{GATE_OPTION} actual",
                                "MLIR_FOUND",
                                f"target {GATE_TARGET}",
                                VERIFIER_INPUT_LIST,
                                "mlir-opt discovery",
                                "default-off no mlir-opt probe proof",
                                "CTest skip labels and regex",
                                "structured verifier skip diagnostics",
                                "report-only source/resource catalog",
                                "source/resource/entrypoint preservation fields",
                            ],
                            "normalBuildRequired": False,
                            "productionLinked": False,
                        },
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    output_markers = (
        "crossgl_fixture",
        MINIMAL_FIXTURE,
        "crossgl_entry_point",
        *REQUIRED_VERIFIER_FACT_MARKERS,
        "crossgl_resource_count",
        "target-independent:none",
        "crossgl_real_mlir_smoke",
    )
    ctest_text = (
        cmake_string_list(
            "CROSSGL_MLIR_EXPERIMENT_MINIMAL_VERIFY_REQUIRED_MARKERS",
            REQUIRED_VERIFIER_MARKERS,
        )
        + "\n"
        + cmake_string_list(
            "CROSSGL_MLIR_EXPERIMENT_MINIMAL_VERIFY_OUTPUT_MARKERS",
            output_markers,
        )
        + f"""
set(CROSSGL_MLIR_EXPERIMENT_OPTIONAL_TOOL_EVIDENCE
  "${{CMAKE_CURRENT_BINARY_DIR}}/mlir/optional_tool_evidence.v0.json")
function(crossgl_mlir_json_string_list out)
endfunction()
set(CROSSGL_MLIR_EXPERIMENT_VERIFIER_SKIP_LABELS_JSON
  "[\\"mlir\\", \\"optional-mlir\\", \\"{UNAVAILABLE_TOOL_LABEL}\\"]")
if(NOT {GATE_OPTION})
  set(CROSSGL_MLIR_EXPERIMENT_VERIFIER_STATUS "default-off")
else()
  find_program(CROSSGL_MLIR_OPT NAMES mlir-opt)
  set(CROSSGL_MLIR_EXPERIMENT_VERIFIER_SKIP_LABELS_JSON
    "[\\"mlir\\", \\"optional-mlir\\", \\"{AVAILABLE_TOOL_LABEL}\\"]")
endif()
file(WRITE "${{CROSSGL_MLIR_EXPERIMENT_OPTIONAL_TOOL_EVIDENCE}}"
  "{{\\"kind\\": \\"{KIND}\\", \\"mlirDiscovery\\": "
  "{{\\"optionDefault\\": \\"OFF\\", \\"optionActual\\": \\"OFF\\"}}, "
  "\\"verifierInput\\": {{}}, \\"verifierTool\\": {{}}, "
  "\\"verifierRegistration\\": {{\\"mode\\": \\"skipped\\", "
  "\\"invokesMlirOpt\\": false, \\"usesVerifyDiagnostics\\": false, "
  "\\"buildsExperimentTarget\\": false, \\"requiredFiles\\": []}}, "
  "\\"reportOnlyCatalogs\\": {{\\"sourceResourceCatalog\\": "
  "{{\\"path\\": \\"{SOURCE_RESOURCE_CATALOG}\\", "
  "\\"checker\\": \\"{SOURCE_RESOURCE_CATALOG_CHECKER}\\", "
  "\\"requiredFixtureSection\\": "
  "\\"{SOURCE_RESOURCE_PRESERVATION_SECTION}\\", "
  "\\"optionalMlirToolingRequired\\": false, "
  "\\"normalBuildRequired\\": false, \\"productionLinked\\": false}}}}, "
  "\\"toolProbeEvidence\\": {{\\"defaultOffMayRunFindProgram\\": false, "
  "\\"defaultOffMayRunVersionProbe\\": false}}, "
  "\\"skipEvidence\\": {{}}, \\"skipDiagnostics\\": "
  "{{\\"missingReasons\\": [], \\"findProgramAttempted\\": false, "
  "\\"versionProbeAttempted\\": false}}}}")
add_test(NAME {EVIDENCE_TEST}
  COMMAND python tools/check_mlir_optional_tool_evidence.py
    --evidence "${{CROSSGL_MLIR_EXPERIMENT_OPTIONAL_TOOL_EVIDENCE}}")
"""
    )
    (root / CTEST_PATH).write_text(ctest_text, encoding="utf-8")
    evidence_path = root / "mlir/optional_tool_evidence.v0.json"
    evidence_path.parent.mkdir(parents=True, exist_ok=True)
    evidence_path.write_text(
        json.dumps(
            {
                "schemaVersion": 1,
                "kind": KIND,
                "status": "default-off",
                "normalBuildRequired": False,
                "productionLinked": False,
                "mlirDiscovery": {
                    "cmakeOption": GATE_OPTION,
                    "optionDefault": OPTION_DEFAULT,
                    "optionActual": "OFF",
                    "optionEnabled": False,
                    "cmakePackage": "MLIR",
                    "mlirFound": False,
                    "target": GATE_TARGET,
                    "targetCreated": False,
                },
                "verifierInput": {
                    "sourceList": VERIFIER_INPUT_LIST,
                    "path": VERIFIER_INPUT,
                    "fixture": MINIMAL_FIXTURE,
                    "present": True,
                },
                "verifierTool": {
                    "name": "mlir-opt",
                    "requiredForNormalBuild": False,
                    "found": False,
                    "path": None,
                    "discoveryStatus": "not-run-default-off",
                },
                "verifierRegistration": {
                    "ctest": VERIFIER_TEST,
                    "mode": "skipped",
                    "invokesMlirOpt": False,
                    "usesVerifyDiagnostics": False,
                    "buildsExperimentTarget": False,
                    "buildTarget": None,
                    "input": VERIFIER_INPUT,
                    "requiredFiles": [],
                    "normalBuildRequired": False,
                    "productionLinked": False,
                },
                "reportOnlyCatalogs": {
                    "sourceResourceCatalog": {
                        "path": SOURCE_RESOURCE_CATALOG,
                        "checker": SOURCE_RESOURCE_CATALOG_CHECKER,
                        "requiredFixtureSection": SOURCE_RESOURCE_PRESERVATION_SECTION,
                        "optionalMlirToolingRequired": False,
                        "normalBuildRequired": False,
                        "productionLinked": False,
                    }
                },
                "toolProbeEvidence": {
                    "defaultOffBranch": DEFAULT_OFF_BRANCH,
                    "findProgramCommand": FIND_PROGRAM_COMMAND,
                    "versionProbeCommand": VERSION_PROBE_COMMAND,
                    "defaultOffMayRunFindProgram": False,
                    "defaultOffMayRunVersionProbe": False,
                    "findProgramAttempted": False,
                    "versionProbeAttempted": False,
                },
                "skipEvidence": {
                    "ctest": VERIFIER_TEST,
                    "skipRegistered": True,
                    "reason": (
                        f"{GATE_OPTION}=OFF; real MLIR verifier disabled by default"
                    ),
                    "labels": ["mlir", "optional-mlir", UNAVAILABLE_TOOL_LABEL],
                    "skipRegularExpression": SKIP_REGEX,
                },
                "skipDiagnostics": {
                    "status": "default-off",
                    "reportOnly": True,
                    "requiredGateFacts": list(REQUIRED_GATE_FACTS),
                    "missingReasons": [DEFAULT_OFF_MISSING_REASON],
                    "findProgramAttempted": False,
                    "versionProbeAttempted": False,
                },
            }
        ),
        encoding="utf-8",
    )
    return evidence_path


def run_self_test() -> list[str]:
    errors: list[str] = []
    with tempfile.TemporaryDirectory() as temp_dir:
        root = Path(temp_dir)
        evidence_path = write_minimal_repo(root)
        if run_checks(root, evidence_path):
            errors.append("self-test: valid optional-tool evidence was rejected")

        data = load_json(evidence_path)
        data["skipEvidence"]["skipRegistered"] = False
        evidence_path.write_text(json.dumps(data), encoding="utf-8")
        if not any(
            "must register a skip" in error for error in run_checks(root, evidence_path)
        ):
            errors.append("self-test: default-off non-skip evidence was accepted")

        evidence_path = write_minimal_repo(root)
        data = load_json(evidence_path)
        data["skipDiagnostics"]["missingReasons"] = []
        evidence_path.write_text(json.dumps(data), encoding="utf-8")
        if not any(
            "must record missing reasons" in error
            or "default-off skip diagnostics" in error
            for error in run_checks(root, evidence_path)
        ):
            errors.append("self-test: missing skip diagnostics reasons were accepted")

        evidence_path = write_minimal_repo(root)
        data = load_json(evidence_path)
        data["mlirDiscovery"]["optionDefault"] = "ON"
        evidence_path.write_text(json.dumps(data), encoding="utf-8")
        if not any(
            "mlirDiscovery.optionDefault" in error
            for error in run_checks(root, evidence_path)
        ):
            errors.append("self-test: changed MLIR option default was accepted")

        evidence_path = write_minimal_repo(root)
        data = load_json(evidence_path)
        data["toolProbeEvidence"]["findProgramAttempted"] = True
        evidence_path.write_text(json.dumps(data), encoding="utf-8")
        if not any(
            "toolProbeEvidence.findProgramAttempted" in error
            or "default-off tool probe evidence" in error
            for error in run_checks(root, evidence_path)
        ):
            errors.append("self-test: default-off tool probe evidence was accepted")

        evidence_path = write_minimal_repo(root)
        data = load_json(evidence_path)
        data["reportOnlyCatalogs"]["sourceResourceCatalog"][
            "requiredFixtureSection"
        ] = "sourceLocations"
        evidence_path.write_text(json.dumps(data), encoding="utf-8")
        if not any(
            "requiredFixtureSection" in error
            for error in run_checks(root, evidence_path)
        ):
            errors.append(
                "self-test: stale source/resource catalog section was accepted"
            )

        evidence_path = write_minimal_repo(root)
        catalog = load_json(root / SOURCE_RESOURCE_CATALOG)
        catalog["fixtures"][0][SOURCE_RESOURCE_PRESERVATION_SECTION][
            "missingManifestFields"
        ] = ["sourceLocationFacts.entry_point"]
        (root / SOURCE_RESOURCE_CATALOG).write_text(
            json.dumps(catalog), encoding="utf-8"
        )
        if not any(
            "missingManifestFields must be empty" in error
            for error in run_checks(root, evidence_path)
        ):
            errors.append(
                "self-test: incomplete source/resource catalog evidence was accepted"
            )

        evidence_path = write_minimal_repo(root)
        data = load_json(evidence_path)
        data["status"] = "toolchain-available"
        data["mlirDiscovery"]["optionEnabled"] = True
        data["mlirDiscovery"]["optionActual"] = "ON"
        data["mlirDiscovery"]["mlirFound"] = True
        data["mlirDiscovery"]["targetCreated"] = True
        data["verifierTool"]["found"] = True
        data["verifierTool"]["path"] = "/opt/mlir/bin/mlir-opt"
        data["verifierTool"]["discoveryStatus"] = "available"
        data["verifierRegistration"]["mode"] = "executable"
        data["verifierRegistration"]["invokesMlirOpt"] = True
        data["verifierRegistration"]["usesVerifyDiagnostics"] = True
        data["verifierRegistration"]["buildsExperimentTarget"] = True
        data["verifierRegistration"]["buildTarget"] = GATE_TARGET
        data["verifierRegistration"]["requiredFiles"] = [VERIFIER_INPUT]
        data["toolProbeEvidence"]["findProgramAttempted"] = True
        data["toolProbeEvidence"]["versionProbeAttempted"] = True
        data["skipEvidence"]["skipRegistered"] = False
        data["skipEvidence"]["reason"] = ""
        data["skipEvidence"]["labels"] = [
            "mlir",
            "optional-mlir",
            AVAILABLE_TOOL_LABEL,
        ]
        data["skipEvidence"]["skipRegularExpression"] = ""
        data["skipDiagnostics"]["status"] = "toolchain-available"
        data["skipDiagnostics"]["missingReasons"] = []
        data["skipDiagnostics"]["findProgramAttempted"] = True
        data["skipDiagnostics"]["versionProbeAttempted"] = True
        evidence_path.write_text(json.dumps(data), encoding="utf-8")
        if run_checks(root, evidence_path):
            errors.append("self-test: valid toolchain-available evidence was rejected")

        data["skipEvidence"]["skipRegularExpression"] = SKIP_REGEX
        evidence_path.write_text(json.dumps(data), encoding="utf-8")
        if not any(
            "must not carry a skip regex" in error
            for error in run_checks(root, evidence_path)
        ):
            errors.append("self-test: tool-available skip regex was accepted")

        evidence_path = write_minimal_repo(root)
        data = load_json(evidence_path)
        data["verifierRegistration"]["mode"] = "executable"
        data["verifierRegistration"]["invokesMlirOpt"] = True
        evidence_path.write_text(json.dumps(data), encoding="utf-8")
        if not any(
            "executable verifier registration" in error
            or "default-off status must record skipped verifier registration" in error
            for error in run_checks(root, evidence_path)
        ):
            errors.append(
                "self-test: contradictory default-off executable verifier "
                "registration was accepted"
            )

        evidence_path = write_minimal_repo(root)
        manifest = load_json(root / MANIFEST_PATH)
        del manifest["optionalToolGatedChecks"][0]["evidenceRecord"]
        (root / MANIFEST_PATH).write_text(json.dumps(manifest), encoding="utf-8")
        if not any(
            "evidenceRecord" in error for error in run_checks(root, evidence_path)
        ):
            errors.append("self-test: manifest without evidenceRecord was accepted")

        evidence_path = write_minimal_repo(root)
        data = load_json(evidence_path)
        data["skipEvidence"]["labels"].append(AVAILABLE_TOOL_LABEL)
        evidence_path.write_text(json.dumps(data), encoding="utf-8")
        if not any(
            "must not mix" in error for error in run_checks(root, evidence_path)
        ):
            errors.append("self-test: mixed tool availability labels were accepted")

        evidence_path = write_minimal_repo(root)
        ctest_text = read_text(root / CTEST_PATH).replace(
            f"if(NOT {GATE_OPTION})\n",
            f"if(NOT {GATE_OPTION})\n  find_program(CROSSGL_MLIR_OPT NAMES mlir-opt)\n",
        )
        (root / CTEST_PATH).write_text(ctest_text, encoding="utf-8")
        if not any(
            "default-off branch" in error for error in run_checks(root, evidence_path)
        ):
            errors.append("self-test: default-off mlir-opt probe was accepted")

        evidence_path = write_minimal_repo(root)
        verifier_input = read_text(root / VERIFIER_INPUT).replace(
            "  crossgl_type_fact_void_entry_point = true,\n", ""
        )
        (root / VERIFIER_INPUT).write_text(verifier_input, encoding="utf-8")
        if not any(
            "missing required fact-preservation marker" in error
            for error in run_checks(root, evidence_path)
        ):
            errors.append("self-test: verifier input missing fact marker was accepted")

        evidence_path = write_minimal_repo(root)
        ctest_text = read_text(root / CTEST_PATH).replace(
            "crossgl_source_location_fact_layout_local_size",
            "crossgl_source_location_fact_missing_local_size",
        )
        (root / CTEST_PATH).write_text(ctest_text, encoding="utf-8")
        if not any(
            "missing fact-preservation verifier token" in error
            for error in run_checks(root, evidence_path)
        ):
            errors.append("self-test: CMake verifier missing fact marker was accepted")
    return errors


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--root",
        type=Path,
        default=Path("."),
        help="Repository root to validate.",
    )
    parser.add_argument(
        "--evidence",
        type=Path,
        help="Configured build-tree optional-tool evidence JSON to validate.",
    )
    parser.add_argument("--self-test", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    errors = run_self_test() if args.self_test else run_checks(args.root, args.evidence)
    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1
    if args.self_test:
        print("MLIR optional-tool evidence checker self-test passed")
    else:
        print("MLIR optional-tool evidence is consistent")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
