#!/usr/bin/env python3
"""Check real package debug/provenance cross-file consistency."""

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from package_target_contracts import (
    PACKAGE_TARGETS_REQUIRING_NATIVE_STATUS,
    SOURCE_PACKAGE_TARGETS,
    TARGET_REQUIRED_PATH_ARTIFACTS,
)


MODULE = "SimpleShader"
FIXTURE = Path("tests/fixtures/SimpleShader.cgl")
REQUIRED_TARGETS = ("directx", "opengl")
OPTIONAL_TARGETS = ("vulkan", "metal")
TARGETS = REQUIRED_TARGETS + OPTIONAL_TARGETS
DEBUG_ARTIFACT_PATHS = {
    "debugMetadata": "ir/debug-metadata.json",
    "hirSourceMap": "ir/hir-source-map.json",
}
TARGET_EXPLANATION_ARTIFACT_PATH = "ir/target-explanation.json"
HIR_PASS_TRACE_SIDECAR_PATH = "ir/hir-pass-trace.json"
HIR_PASS_TRACE_SCHEMA_VERSION = 1
HIR_PASS_TRACE_KIND = "hir-pass-trace"
HIR_PASS_TRACE_OPTIMIZATION_LEVELS = ("O0", "O1", "O2")
HIR_PASS_TRACE_PASS_STATUSES = ("completed", "failed")
HIR_PASS_TRACE_FINGERPRINT_POLICY = "scheduled-pass-ids-v1"
HIR_PASS_TRACE_SCHEDULE_STABILITIES = (
    "stable-opt-level-policy",
    "caller-defined",
)
HIR_PASS_TRACE_STOP_REASONS = (
    "none",
    "missing-runner",
    "unnamed-pass",
    "diagnostics",
    "pass-error",
)
HIR_PASS_TRACE_MODULE_STATS_GROUPS = ("before", "after", "delta")
HIR_PASS_TRACE_MODULE_STATS_FIELDS = (
    "structCount",
    "constantCount",
    "stageCount",
    "resourceCount",
    "functionCount",
    "statementCount",
    "expressionCount",
)
PSEUDO_MLIR_PATH = "ir/pseudo-mlir.mlir"
LEGACY_PSEUDO_MLIR_ALIAS_PATH = "ir/mlir.mlir"
PSEUDO_MLIR_MARKERS = (
    "CrossGL pseudo-MLIR",
    "not a registered MLIR dialect",
    'crossgl.ir_kind = "pseudo-mlir"',
    'crossgl.real_mlir = "false"',
)
LOCATION_KINDS = ("expressions", "types", "statements")


def run(command, *, cwd=None):
    return subprocess.run(
        [str(arg) for arg in command],
        cwd=cwd,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )


def fail(errors, case_name, message):
    errors.append(f"{case_name}: {message}")


def load_json(path, errors, case_name):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except OSError as exc:
        fail(errors, case_name, f"failed to read {path}: {exc}")
    except json.JSONDecodeError as exc:
        fail(errors, case_name, f"{path} is not JSON: {exc}")
    return {}


def validate_json_schema(root, tmp_dir, errors, case_name, schema_name, document):
    instance_path = tmp_dir / f"{case_name}.{schema_name}.json"
    instance_path.write_text(json.dumps(document, sort_keys=True), encoding="utf-8")
    result = run(
        [
            sys.executable,
            root / "tools" / "validate_json_schema.py",
            "--schema",
            root / "docs" / "schemas" / f"{schema_name}.schema.json",
            "--instance",
            instance_path,
        ]
    )
    if result.returncode != 0:
        fail(
            errors,
            case_name,
            f"{schema_name} schema validation failed: "
            f"{result.stderr}{result.stdout}".strip(),
        )


def sha256_file(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_source_text_preserving_newlines(path):
    return path.read_bytes().decode("utf-8")


def read_text(path, errors, case_name):
    try:
        return path.read_text(encoding="utf-8")
    except OSError as exc:
        fail(errors, case_name, f"failed to read {path}: {exc}")
    return ""


def normalize_source_location_path(path):
    if not isinstance(path, str):
        return path
    return path.replace("\\", "/")


def expect_equal(errors, case_name, path, actual, expected):
    if actual != expected:
        fail(errors, case_name, f"expected {path}={expected!r}, got {actual!r}")


def expect_true(errors, case_name, path, value):
    if value is not True:
        fail(errors, case_name, f"expected {path}=True, got {value!r}")


def expected_summary_native_binary_status(manifest, package):
    artifacts = manifest.get("artifacts", {})
    if not isinstance(artifacts, dict):
        return None

    manifest_status = artifacts.get("nativeBinaryStatus")
    if manifest_status is not None:
        return manifest_status

    if isinstance(manifest.get("packageArtifactRequirements"), dict):
        return None

    if manifest.get("target") == "metal":
        intermediate = artifacts.get("intermediate")
        native_binary = artifacts.get("nativeBinary")
        if (
            isinstance(intermediate, str)
            and isinstance(native_binary, str)
            and (package / intermediate).is_file()
            and (package / native_binary).is_file()
        ):
            return "emitted"
    return None


def record_by_name(records, name):
    if not isinstance(records, list):
        return None
    for record in records:
        if isinstance(record, dict) and record.get("name") == name:
            return record
    return None


def has_xcrun_tool(tool):
    xcrun = shutil.which("xcrun")
    if not xcrun:
        return False
    result = run([xcrun, "-find", tool])
    return result.returncode == 0 and bool(result.stdout.strip())


def target_available(target):
    if target in REQUIRED_TARGETS:
        return True
    if target == "vulkan":
        return all(shutil.which(tool) for tool in ("spirv-as", "spirv-val"))
    if target == "metal":
        return sys.platform == "darwin" and all(
            has_xcrun_tool(tool) for tool in ("metal", "metallib")
        )
    return False


def expect_artifact_file_state(errors, case_name, package, name, path, manifest):
    if name == "nativeBinary":
        status = manifest.get("artifacts", {}).get("nativeBinaryStatus")
        exists = (package / path).is_file()
        if status == "planned":
            expect_equal(errors, case_name, "nativeBinary file exists", exists, False)
            return
        if status not in (None, "emitted", "validated"):
            fail(errors, case_name, f"unexpected nativeBinaryStatus {status!r}")
            return
    if not (package / path).is_file():
        fail(errors, case_name, f"expected artifact file {path!r}")


def expect_manifest_consistency(
    errors, case_name, source, package, target, manifest, reflection
):
    expect_equal(
        errors, case_name, "manifest.schemaVersion", manifest.get("schemaVersion"), 1
    )
    expect_equal(errors, case_name, "manifest.module", manifest.get("module"), MODULE)
    expect_equal(errors, case_name, "manifest.target", manifest.get("target"), target)
    source_hash = manifest.get("sourceHash", {})
    expect_equal(
        errors,
        case_name,
        "manifest.sourceHash.algorithm",
        source_hash.get("algorithm"),
        "sha256",
    )
    expect_equal(
        errors,
        case_name,
        "manifest.sourceHash.value",
        source_hash.get("value"),
        sha256_file(source),
    )

    artifacts = manifest.get("artifacts")
    if not isinstance(artifacts, dict):
        fail(errors, case_name, "manifest.artifacts must be an object")
        return

    for name in TARGET_REQUIRED_PATH_ARTIFACTS[target]:
        path = artifacts.get(name)
        if not isinstance(path, str) or not path:
            fail(errors, case_name, f"manifest.artifacts.{name} must be a path string")
            continue
        expect_artifact_file_state(errors, case_name, package, name, path, manifest)

    for name, expected_path in DEBUG_ARTIFACT_PATHS.items():
        expect_equal(
            errors,
            case_name,
            f"manifest.artifacts.{name}",
            artifacts.get(name),
            expected_path,
        )
        expect_artifact_file_state(
            errors, case_name, package, name, expected_path, manifest
        )
    expect_equal(
        errors,
        case_name,
        "manifest.artifacts.targetExplanation",
        artifacts.get("targetExplanation"),
        TARGET_EXPLANATION_ARTIFACT_PATH,
    )
    expect_artifact_file_state(
        errors,
        case_name,
        package,
        "targetExplanation",
        TARGET_EXPLANATION_ARTIFACT_PATH,
        manifest,
    )

    if target in PACKAGE_TARGETS_REQUIRING_NATIVE_STATUS:
        if artifacts.get("nativeBinaryStatus") not in (
            "planned",
            "emitted",
            "validated",
        ):
            fail(
                errors,
                case_name,
                "source package target must record a concrete nativeBinaryStatus",
            )
    elif "nativeBinaryStatus" in artifacts:
        fail(errors, case_name, "native target must not record nativeBinaryStatus")

    expect_equal(
        errors,
        case_name,
        "reflection.schemaVersion",
        reflection.get("schemaVersion"),
        1,
    )
    expect_equal(
        errors,
        case_name,
        "reflection.module",
        reflection.get("module"),
        manifest.get("module"),
    )
    expect_equal(
        errors,
        case_name,
        "reflection.target",
        reflection.get("target"),
        manifest.get("target"),
    )
    expect_equal(
        errors,
        case_name,
        "reflection.nativeBinary",
        reflection.get("nativeBinary"),
        artifacts.get("nativeBinary"),
    )


def expect_debug_decision_consistency(errors, case_name, target, debug):
    expect_equal(
        errors, case_name, "debugMetadata.schemaVersion", debug.get("schemaVersion"), 11
    )
    decision = debug.get("targetDecision", {})
    expect_equal(
        errors,
        case_name,
        "targetDecision.requestedTarget",
        decision.get("requestedTarget"),
        target,
    )
    expect_equal(
        errors,
        case_name,
        "targetDecision.selectedTarget",
        decision.get("selectedTarget"),
        target,
    )
    expect_true(
        errors,
        case_name,
        "targetDecision.selectedTargetPackageBuildSupported",
        decision.get("selectedTargetPackageBuildSupported"),
    )
    expect_equal(
        errors,
        case_name,
        "targetDecision.selectedTargetSourcePackageSupported",
        decision.get("selectedTargetSourcePackageSupported"),
        target in SOURCE_PACKAGE_TARGETS,
    )

    summaries = debug.get("targetCapabilities", {}).get("summaries")
    selected_summary = None
    if isinstance(summaries, list):
        selected_summary = next(
            (
                summary
                for summary in summaries
                if isinstance(summary, dict) and summary.get("target") == target
            ),
            None,
        )
    if selected_summary is None:
        fail(errors, case_name, "targetCapabilities.summaries missing selected target")
        return

    field_pairs = (
        ("selectedTargetNativeImplemented", "nativeImplemented"),
        ("selectedTargetSourcePackageSupported", "sourcePackageSupported"),
        ("selectedTargetPackageBuildSupported", "packageBuildSupported"),
        ("selectedTargetPackageMode", "packageMode"),
        ("selectedTargetMissingCapabilityCount", "missingCapabilityCount"),
        ("selectedTargetMissingCapabilities", "missingCapabilities"),
        ("selectedTargetMissingCapabilityGroups", "missingCapabilityGroups"),
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
            selected_summary.get(summary_field),
        )


def load_target_explanation(errors, case_name, root, cglc):
    result = run([cglc, "explain-targets", FIXTURE], cwd=root)
    if result.returncode != 0:
        fail(
            errors,
            case_name,
            f"explain-targets failed: {result.stderr}{result.stdout}".strip(),
        )
        return {}
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        fail(errors, case_name, f"explain-targets output is not JSON: {exc}")
    return {}


def expect_target_explanation_sidecar_consistency(
    root, tmp_dir, errors, case_name, sidecar_explanation, cli_explanation
):
    validate_json_schema(
        root,
        tmp_dir,
        errors,
        case_name,
        "target-explanation-v1",
        sidecar_explanation,
    )
    expect_equal(
        errors,
        case_name,
        "targetExplanation sidecar",
        sidecar_explanation,
        cli_explanation,
    )


def expect_debug_legalization_projection_consistency(
    errors, case_name, debug, explanation
):
    summaries = debug.get("targetCapabilities", {}).get("summaries")
    targets = explanation.get("targets")
    if not isinstance(summaries, list):
        fail(errors, case_name, "debugMetadata.targetCapabilities.summaries missing")
        return
    if not isinstance(targets, list):
        fail(errors, case_name, "explainTargets.targets missing")
        return

    expect_equal(
        errors,
        case_name,
        "debugMetadata.targetCapabilities.defaultTarget",
        debug.get("targetCapabilities", {}).get("defaultTarget"),
        explanation.get("defaultTarget"),
    )
    expect_equal(
        errors,
        case_name,
        "debugMetadata target summary order",
        [summary.get("target") for summary in summaries if isinstance(summary, dict)],
        [target.get("target") for target in targets if isinstance(target, dict)],
    )

    explanation_by_target = {
        target.get("target"): target for target in targets if isinstance(target, dict)
    }
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
        "requiredCapabilities",
        "missingCapabilities",
        "requiredToolCount",
        "missingToolCount",
        "requiredToolIds",
        "missingToolIds",
        "optionalNativeToolMissing",
        "optionalNativeToolStatus",
        "toolRequirementEvidenceIds",
    )
    for summary in summaries:
        if not isinstance(summary, dict):
            continue
        target_name = summary.get("target")
        explanation_record = explanation_by_target.get(target_name)
        if explanation_record is None:
            fail(
                errors,
                case_name,
                f"explainTargets.targets missing debug target {target_name!r}",
            )
            continue
        for field in shared_fields:
            actual = summary.get(field)
            expected = explanation_record.get(field)
            if field in (
                "requiredCapabilities",
                "missingCapabilities",
                "requiredToolIds",
                "missingToolIds",
            ):
                actual = sorted(actual) if isinstance(actual, list) else actual
                expected = sorted(expected) if isinstance(expected, list) else expected
            expect_equal(
                errors,
                case_name,
                f"debugMetadata.targetCapabilities.summaries[{target_name}].{field}",
                actual,
                expected,
            )

    buildable_targets = [
        target["target"]
        for target in targets
        if isinstance(target, dict) and target.get("packageBuildSupported")
    ]
    non_buildable_targets = [
        target["target"]
        for target in targets
        if isinstance(target, dict) and not target.get("packageBuildSupported")
    ]
    decision = debug.get("targetDecision", {})
    expect_equal(
        errors,
        case_name,
        "targetDecision.viableTargets",
        decision.get("viableTargets"),
        buildable_targets,
    )
    expect_equal(
        errors,
        case_name,
        "targetDecision.nonViableTargets",
        decision.get("nonViableTargets"),
        non_buildable_targets,
    )
    expect_equal(
        errors,
        case_name,
        "explainTargets.buildableTargetCount",
        explanation.get("buildableTargetCount"),
        len(buildable_targets),
    )

    selected_target = decision.get("selectedTarget")
    fallback_records = [
        target
        for target in targets
        if isinstance(target, dict)
        and target.get("packageBuildSupported")
        and target.get("target") != selected_target
    ]
    fallback_records.sort(key=lambda target: target.get("packageRankScore", 0))
    expect_equal(
        errors,
        case_name,
        "targetDecision.fallbackTargets",
        decision.get("fallbackTargets"),
        [target["target"] for target in fallback_records],
    )


def expect_pseudo_mlir_package_sidecars(errors, case_name, package):
    pseudo_path = package / PSEUDO_MLIR_PATH
    legacy_path = package / LEGACY_PSEUDO_MLIR_ALIAS_PATH
    if not pseudo_path.is_file():
        fail(errors, case_name, f"expected pseudo-MLIR sidecar {PSEUDO_MLIR_PATH!r}")
        return
    if not legacy_path.is_file():
        fail(
            errors,
            case_name,
            f"expected legacy pseudo-MLIR alias {LEGACY_PSEUDO_MLIR_ALIAS_PATH!r}",
        )
        return

    pseudo_text = read_text(pseudo_path, errors, case_name)
    legacy_text = read_text(legacy_path, errors, case_name)
    expect_equal(
        errors,
        case_name,
        "legacy pseudo-MLIR alias contents",
        legacy_text,
        pseudo_text,
    )
    for marker in PSEUDO_MLIR_MARKERS:
        if marker not in pseudo_text:
            fail(
                errors,
                case_name,
                f"expected {PSEUDO_MLIR_PATH!r} to contain {marker!r}",
            )


def expect_hir_pass_trace_pass(
    errors,
    case_name,
    path,
    actual,
    expected_index,
    expected_name,
    expected_changed,
    expected_status,
    expected_diagnostic_count,
    expected_error_count,
):
    expected = {
        "index": expected_index,
        "name": expected_name,
        "changed": expected_changed,
        "status": expected_status,
        "diagnosticCount": expected_diagnostic_count,
        "errorCount": expected_error_count,
    }
    actual_core = (
        {key: actual.get(key) for key in expected}
        if isinstance(actual, dict)
        else actual
    )
    expect_equal(errors, case_name, path, actual_core, expected)


def is_non_negative_int(value):
    return type(value) is int and value >= 0


def expect_non_negative_int(errors, case_name, path, value):
    if not is_non_negative_int(value):
        fail(errors, case_name, f"{path} must be a non-negative integer")
        return False
    return True


def hir_pass_schedule_fingerprint(pass_ids):
    hash_value = 14695981039346656037

    def update_byte(byte):
        nonlocal hash_value
        hash_value ^= byte
        hash_value = (hash_value * 1099511628211) & 0xFFFFFFFFFFFFFFFF

    def update_string(value):
        encoded = value.encode("utf-8")
        size = len(encoded)
        for shift in range(0, 64, 8):
            update_byte((size >> shift) & 0xFF)
        for byte in encoded:
            update_byte(byte)

    update_string(HIR_PASS_TRACE_FINGERPRINT_POLICY)
    for pass_id in pass_ids:
        update_string(pass_id)
    return f"fnv1a64:{hash_value:016x}"


def is_hir_pass_schedule_fingerprint(value):
    if not isinstance(value, str) or len(value) != len("fnv1a64:") + 16:
        return False
    if not value.startswith("fnv1a64:"):
        return False
    return all(character in "0123456789abcdef" for character in value[8:])


def expect_hir_pass_trace_module_stats(errors, case_name, path, actual):
    if not isinstance(actual, dict):
        fail(errors, case_name, f"{path} must be an object")
        return
    for group in HIR_PASS_TRACE_MODULE_STATS_GROUPS:
        group_value = actual.get(group)
        if not isinstance(group_value, dict):
            fail(errors, case_name, f"{path}.{group} must be an object")
            continue
        for field in HIR_PASS_TRACE_MODULE_STATS_FIELDS:
            expect_non_negative_int(
                errors,
                case_name,
                f"{path}.{group}.{field}",
                group_value.get(field),
            )


def expect_hir_pass_trace_pass_metadata(
    errors,
    case_name,
    path,
    actual,
    index,
    *,
    allow_elapsed_time=True,
    require_module_stats=False,
):
    if not isinstance(actual, dict):
        fail(errors, case_name, f"{path} must be an object")
        return
    actual_index = actual.get("index")
    if not is_non_negative_int(actual_index) or actual_index != index:
        fail(
            errors,
            case_name,
            f"{path}.index must be the zero-based pass index {index}",
        )
    pass_id = actual.get("id")
    if not isinstance(pass_id, str) or not pass_id:
        fail(errors, case_name, f"{path}.id must be a non-empty string")
    name = actual.get("name")
    if not isinstance(name, str) or not name:
        fail(errors, case_name, f"{path}.name must be a non-empty string")
    category = actual.get("category")
    if not isinstance(category, str) or not category:
        fail(errors, case_name, f"{path}.category must be a non-empty string")
    changed = actual.get("changed")
    if not isinstance(changed, bool):
        fail(errors, case_name, f"{path}.changed must be a boolean")
    status = actual.get("status")
    if status not in HIR_PASS_TRACE_PASS_STATUSES:
        fail(
            errors,
            case_name,
            f"{path}.status must be one of {HIR_PASS_TRACE_PASS_STATUSES}",
        )
    diagnostic_count = actual.get("diagnosticCount")
    error_count = actual.get("errorCount")
    if not expect_non_negative_int(
        errors, case_name, f"{path}.diagnosticCount", diagnostic_count
    ):
        return
    if not expect_non_negative_int(
        errors, case_name, f"{path}.errorCount", error_count
    ):
        return
    if error_count > diagnostic_count:
        fail(
            errors,
            case_name,
            f"{path}.errorCount must not exceed diagnosticCount",
        )
    if status == "completed" and error_count != 0:
        fail(errors, case_name, f"{path}.completed pass must have zero errors")
    if status == "failed" and error_count == 0:
        fail(errors, case_name, f"{path}.failed pass must have at least one error")
    if "elapsedTimeMicroseconds" in actual:
        if allow_elapsed_time:
            expect_non_negative_int(
                errors,
                case_name,
                f"{path}.elapsedTimeMicroseconds",
                actual.get("elapsedTimeMicroseconds"),
            )
        else:
            fail(
                errors,
                case_name,
                f"{path}.elapsedTimeMicroseconds must not be sealed in package traces",
            )
    module_stats = actual.get("moduleStats")
    if module_stats is not None:
        expect_hir_pass_trace_module_stats(
            errors, case_name, f"{path}.moduleStats", module_stats
        )
    elif require_module_stats:
        fail(errors, case_name, f"{path}.moduleStats must be present")


def expect_hir_pass_trace_schedule(
    errors,
    case_name,
    trace,
    passes,
    scheduled_pass_count,
):
    schedule = trace.get("passSchedule")
    if not isinstance(schedule, dict):
        fail(errors, case_name, "hirPassTrace.passSchedule must be an object")
        return
    fingerprint = schedule.get("fingerprint")
    if not is_hir_pass_schedule_fingerprint(fingerprint):
        fail(
            errors,
            case_name,
            "hirPassTrace.passSchedule.fingerprint must be an fnv1a64 fingerprint",
        )
    fingerprint_policy = schedule.get("fingerprintPolicy")
    expect_equal(
        errors,
        case_name,
        "hirPassTrace.passSchedule.fingerprintPolicy",
        fingerprint_policy,
        HIR_PASS_TRACE_FINGERPRINT_POLICY,
    )
    stability = schedule.get("stability")
    if stability not in HIR_PASS_TRACE_SCHEDULE_STABILITIES:
        fail(
            errors,
            case_name,
            "hirPassTrace.passSchedule.stability must be one of "
            f"{HIR_PASS_TRACE_SCHEDULE_STABILITIES}",
        )

    pass_ids = []
    for pass_record in passes:
        if not isinstance(pass_record, dict):
            return
        pass_id = pass_record.get("id")
        if not isinstance(pass_id, str) or not pass_id:
            return
        pass_ids.append(pass_id)
    if is_non_negative_int(scheduled_pass_count) and scheduled_pass_count == len(
        passes
    ):
        expect_equal(
            errors,
            case_name,
            "hirPassTrace.passSchedule.fingerprint",
            fingerprint,
            hir_pass_schedule_fingerprint(pass_ids),
        )


def expect_hir_pass_trace_document(
    errors,
    case_name,
    trace,
    *,
    allow_elapsed_time=True,
    require_module_stats=False,
):
    if not isinstance(trace, dict):
        fail(errors, case_name, "hirPassTrace must be an object")
        return

    expect_equal(
        errors,
        case_name,
        "hirPassTrace.schemaVersion",
        trace.get("schemaVersion"),
        HIR_PASS_TRACE_SCHEMA_VERSION,
    )
    expect_equal(
        errors, case_name, "hirPassTrace.kind", trace.get("kind"), HIR_PASS_TRACE_KIND
    )
    if trace.get("optimizationLevel") not in HIR_PASS_TRACE_OPTIMIZATION_LEVELS:
        fail(
            errors,
            case_name,
            "hirPassTrace.optimizationLevel must be one of "
            f"{HIR_PASS_TRACE_OPTIMIZATION_LEVELS}",
        )

    passes = trace.get("passes")
    if not isinstance(passes, list):
        fail(errors, case_name, "hirPassTrace.passes must be an array")
        return

    for index, pass_record in enumerate(passes):
        expect_hir_pass_trace_pass_metadata(
            errors,
            case_name,
            f"hirPassTrace.passes[{index}]",
            pass_record,
            index,
            allow_elapsed_time=allow_elapsed_time,
            require_module_stats=require_module_stats,
        )

    pass_count = trace.get("passCount")
    if expect_non_negative_int(errors, case_name, "hirPassTrace.passCount", pass_count):
        expect_equal(
            errors,
            case_name,
            "hirPassTrace.passCount",
            pass_count,
            len(passes),
        )

    scheduled_pass_count = trace.get("scheduledPassCount")
    if expect_non_negative_int(
        errors,
        case_name,
        "hirPassTrace.scheduledPassCount",
        scheduled_pass_count,
    ) and is_non_negative_int(pass_count):
        if scheduled_pass_count < pass_count:
            fail(
                errors,
                case_name,
                "hirPassTrace.scheduledPassCount must not be less than passCount",
            )
    expect_hir_pass_trace_schedule(
        errors,
        case_name,
        trace,
        passes,
        scheduled_pass_count,
    )

    changed_passes = sum(
        1
        for pass_record in passes
        if isinstance(pass_record, dict) and pass_record.get("changed") is True
    )
    diagnostic_passes = sum(
        1
        for pass_record in passes
        if isinstance(pass_record, dict)
        and is_non_negative_int(pass_record.get("diagnosticCount"))
        and pass_record.get("diagnosticCount") > 0
    )
    error_passes = sum(
        1
        for pass_record in passes
        if isinstance(pass_record, dict)
        and is_non_negative_int(pass_record.get("errorCount"))
        and pass_record.get("errorCount") > 0
    )
    expect_equal(
        errors,
        case_name,
        "hirPassTrace.changedPassCount",
        trace.get("changedPassCount"),
        changed_passes,
    )
    expect_equal(
        errors,
        case_name,
        "hirPassTrace.diagnosticPassCount",
        trace.get("diagnosticPassCount"),
        diagnostic_passes,
    )
    expect_equal(
        errors,
        case_name,
        "hirPassTrace.errorPassCount",
        trace.get("errorPassCount"),
        error_passes,
    )

    changed = trace.get("changed")
    if not isinstance(changed, bool):
        fail(errors, case_name, "hirPassTrace.changed must be a boolean")
    else:
        expect_equal(
            errors,
            case_name,
            "hirPassTrace.changed",
            changed,
            changed_passes != 0,
        )

    completed = trace.get("completed")
    if not isinstance(completed, bool):
        fail(errors, case_name, "hirPassTrace.completed must be a boolean")
        return
    stop_reason = trace.get("stopReason")
    if stop_reason not in HIR_PASS_TRACE_STOP_REASONS:
        fail(
            errors,
            case_name,
            f"hirPassTrace.stopReason must be one of {HIR_PASS_TRACE_STOP_REASONS}",
        )
        return
    failed_pass_count = sum(
        1
        for pass_record in passes
        if isinstance(pass_record, dict) and pass_record.get("status") == "failed"
    )
    if completed:
        if stop_reason != "none":
            fail(
                errors,
                case_name,
                "hirPassTrace.completed=true requires stopReason='none'",
            )
        if is_non_negative_int(scheduled_pass_count) and scheduled_pass_count != len(
            passes
        ):
            fail(
                errors,
                case_name,
                "hirPassTrace.completed=true requires every scheduled pass to run",
            )
        if failed_pass_count != 0:
            fail(errors, case_name, "hirPassTrace.completed trace has failed passes")
    else:
        if stop_reason == "none":
            fail(
                errors,
                case_name,
                "hirPassTrace.completed=false requires a non-none stopReason",
            )
    if stop_reason == "pass-error" and failed_pass_count == 0:
        fail(
            errors,
            case_name,
            "hirPassTrace.stopReason='pass-error' requires a failed pass",
        )


def expect_hir_pass_trace_sidecar(errors, case_name, root, cglc, package, manifest):
    artifacts = manifest.get("artifacts", {})
    if isinstance(artifacts, dict):
        for key in ("hirPassTrace", "passTrace", "hir-pass-trace"):
            if key in artifacts:
                fail(
                    errors,
                    case_name,
                    f"manifest.artifacts must not declare non-manifest pass trace {key}",
                )

    trace_path = package / HIR_PASS_TRACE_SIDECAR_PATH
    if not trace_path.is_file():
        fail(
            errors,
            case_name,
            f"expected non-manifest debug sidecar {HIR_PASS_TRACE_SIDECAR_PATH!r}",
        )
        return

    trace = load_json(trace_path, errors, case_name)
    expect_hir_pass_trace_document(
        errors,
        case_name,
        trace,
        allow_elapsed_time=False,
        require_module_stats=True,
    )
    if not isinstance(trace.get("passes"), list):
        return

    result = run([cglc, "dump-ir", FIXTURE, "--stage", "hir-pass-trace"], cwd=root)
    if result.returncode != 0:
        fail(
            errors,
            case_name,
            f"dump-ir hir-pass-trace failed: {result.stderr}{result.stdout}".strip(),
        )
        return
    try:
        dump_trace = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        fail(errors, case_name, f"dump-ir hir-pass-trace output is not JSON: {exc}")
        return
    trace_passes = trace.get("passes", [])
    dump_passes = dump_trace.get("passes", [])
    trace_passes_without_elapsed = strip_hir_pass_trace_elapsed_time(trace_passes)
    dump_passes_without_elapsed = strip_hir_pass_trace_elapsed_time(dump_passes)
    expect_equal(
        errors,
        case_name,
        "hirPassTrace source-validation prefix",
        trace_passes_without_elapsed[: len(dump_passes_without_elapsed)],
        dump_passes_without_elapsed,
    )
    expect_equal(
        errors,
        case_name,
        "hirPassTrace passCount",
        trace.get("passCount"),
        dump_trace.get("passCount") + 1,
    )
    expect_equal(
        errors,
        case_name,
        "hirPassTrace.scheduledPassCount",
        trace.get("scheduledPassCount"),
        dump_trace.get("scheduledPassCount") + 1,
    )
    expect_true(errors, case_name, "hirPassTrace.completed", trace.get("completed"))
    expect_equal(
        errors,
        case_name,
        "hirPassTrace.stopReason",
        trace.get("stopReason"),
        "none",
    )
    expect_hir_pass_trace_pass(
        errors,
        case_name,
        "hirPassTrace backend-input pass",
        trace_passes[-1] if trace_passes else None,
        dump_trace.get("passCount"),
        "hir.validate.backend-input",
        False,
        "completed",
        0,
        0,
    )


def strip_hir_pass_trace_elapsed_time(value):
    if isinstance(value, dict):
        return {
            key: strip_hir_pass_trace_elapsed_time(child)
            for key, child in value.items()
            if key != "elapsedTimeMicroseconds"
        }
    if isinstance(value, list):
        return [strip_hir_pass_trace_elapsed_time(child) for child in value]
    return value


def expect_hir_locations_consistency(
    errors, case_name, root, source, debug, source_map
):
    debug_locations = debug.get("hirSourceLocations")
    map_locations = source_map.get("hirSourceLocations")
    expect_equal(
        errors,
        case_name,
        "debugMetadata.hirSourceLocations",
        debug_locations,
        map_locations,
    )
    if not isinstance(map_locations, dict):
        fail(errors, case_name, "hirSourceMap.hirSourceLocations must be an object")
        return

    source_text = read_source_text_preserving_newlines(source)
    source_label = source.relative_to(root).as_posix()
    for kind in LOCATION_KINDS:
        records = map_locations.get(kind)
        if not isinstance(records, list) or not records:
            fail(
                errors,
                case_name,
                f"hirSourceLocations.{kind} must be a non-empty array",
            )
            continue
        with_location = 0
        for index, record in enumerate(records):
            location = record.get("location") if isinstance(record, dict) else None
            if not isinstance(location, dict):
                continue
            with_location += 1
            expect_equal(
                errors,
                case_name,
                f"hirSourceLocations.{kind}[{index}].location.file",
                normalize_source_location_path(location.get("file")),
                source_label,
            )
            offset = location.get("offset")
            length = location.get("length")
            end_offset = location.get("endOffset")
            if not all(
                isinstance(value, int) for value in (offset, length, end_offset)
            ):
                fail(
                    errors,
                    case_name,
                    f"hirSourceLocations.{kind}[{index}] has non-integer offsets",
                )
            elif (
                offset < 0
                or length < 0
                or end_offset != offset + length
                or end_offset > len(source_text)
            ):
                fail(
                    errors,
                    case_name,
                    f"hirSourceLocations.{kind}[{index}] has incoherent source span",
                )

        with_location_name = f"{kind[:-1]}WithLocationCount"
        expect_equal(
            errors,
            case_name,
            f"hirSourceLocations.{with_location_name}",
            map_locations.get(with_location_name),
            with_location,
        )
        if kind != "types":
            count_name = f"{kind[:-1]}Count"
            expect_equal(
                errors,
                case_name,
                f"hirSourceLocations.{count_name}",
                map_locations.get(count_name),
                len(records),
            )

    category_counts = source_map.get("categoryCounts", {})
    pagination = source_map.get("pagination", {})
    total = 0
    for stem, kind in (
        ("expression", "expressions"),
        ("type", "types"),
        ("statement", "statements"),
    ):
        records = map_locations.get(kind)
        count = len(records) if isinstance(records, list) else 0
        total += count
        expect_equal(
            errors,
            case_name,
            f"categoryCounts.{stem}TotalCount",
            category_counts.get(f"{stem}TotalCount"),
            count,
        )
        expect_equal(
            errors,
            case_name,
            f"pagination.{stem}TotalCount",
            pagination.get(f"{stem}TotalCount"),
            count,
        )
        expect_equal(
            errors,
            case_name,
            f"pagination.{stem}EmittedCount",
            pagination.get(f"{stem}EmittedCount"),
            count,
        )
        expect_equal(
            errors,
            case_name,
            f"pagination.{stem}HasMore",
            pagination.get(f"{stem}HasMore"),
            False,
        )
    expect_equal(
        errors,
        case_name,
        "categoryCounts.recordTotalCount",
        category_counts.get("recordTotalCount"),
        total,
    )
    expect_equal(
        errors,
        case_name,
        "records.totalCount",
        source_map.get("records", {}).get("totalCount"),
        total,
    )


def expect_inspect_consistency(errors, case_name, cglc, package, manifest, reflection):
    result = run([cglc, "package", "inspect", package, "--json"])
    if result.returncode != 0:
        fail(
            errors,
            case_name,
            f"package inspect failed: {result.stderr}{result.stdout}".strip(),
        )
        return
    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        fail(errors, case_name, f"package inspect output is not JSON: {exc}")
        return

    summary = payload.get("summary", {})
    expect_equal(
        errors,
        case_name,
        "inspect.summary.module",
        summary.get("module"),
        manifest.get("module"),
    )
    expect_equal(
        errors,
        case_name,
        "inspect.summary.target",
        summary.get("target"),
        manifest.get("target"),
    )
    expect_equal(
        errors,
        case_name,
        "inspect.summary.nativeBinaryStatus",
        summary.get("nativeBinaryStatus"),
        expected_summary_native_binary_status(manifest, package),
    )
    expect_equal(
        errors, case_name, "inspect.manifest", payload.get("manifest"), manifest
    )
    expect_equal(
        errors, case_name, "inspect.reflection", payload.get("reflection"), reflection
    )
    expect_equal(
        errors,
        case_name,
        "inspect.debugArtifacts.health",
        payload.get("debugArtifacts", {}).get("health"),
        "ok",
    )
    for check, value in payload.get("debugArtifacts", {}).get("checks", {}).items():
        expect_true(errors, case_name, f"inspect.debugArtifacts.checks.{check}", value)

    records = payload.get("artifacts")
    if not isinstance(records, list):
        fail(errors, case_name, "inspect.artifacts must be an array")
        return
    for name, path in manifest.get("artifacts", {}).items():
        if name == "nativeBinaryStatus":
            continue
        record = record_by_name(records, name)
        if record is None:
            fail(errors, case_name, f"inspect.artifacts missing {name}")
            continue
        expect_equal(
            errors,
            case_name,
            f"inspect.artifacts.{name}.path",
            record.get("path"),
            path,
        )
        expected_exists = (package / path).is_file()
        expect_equal(
            errors,
            case_name,
            f"inspect.artifacts.{name}.exists",
            record.get("exists"),
            expected_exists,
        )
        expected_hash = sha256_file(package / path) if expected_exists else None
        expect_equal(
            errors,
            case_name,
            f"inspect.artifacts.{name}.sha256",
            record.get("sha256"),
            expected_hash,
        )
    if record_by_name(records, "hirPassTrace") is not None:
        fail(errors, case_name, "inspect.artifacts must not include hirPassTrace")


def expect_verify_success(errors, case_name, cglc, package, source, manifest):
    result = run([cglc, "package", "verify", package, "--source", source, "--json"])
    if result.returncode != 0:
        fail(
            errors,
            case_name,
            f"package verify failed: {result.stderr}{result.stdout}".strip(),
        )
        return
    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        fail(errors, case_name, f"package verify output is not JSON: {exc}")
        return
    expect_equal(errors, case_name, "verify.success", payload.get("success"), True)
    expect_equal(
        errors,
        case_name,
        "verify.diagnosticCounts.error",
        payload.get("diagnosticCounts", {}).get("error"),
        0,
    )
    expect_equal(
        errors, case_name, "verify.diagnostics", payload.get("diagnostics"), []
    )
    summary = payload.get("summary", {})
    expect_equal(
        errors,
        case_name,
        "verify.summary.module",
        summary.get("module"),
        manifest.get("module"),
    )
    expect_equal(
        errors,
        case_name,
        "verify.summary.target",
        summary.get("target"),
        manifest.get("target"),
    )
    expect_equal(
        errors,
        case_name,
        "verify.summary.nativeBinaryStatus",
        summary.get("nativeBinaryStatus"),
        expected_summary_native_binary_status(manifest, package),
    )


def probe_target(root, tmp_dir, cglc, target):
    case_name = f"{target}-debug-provenance"
    package = tmp_dir / f"{target}-{MODULE}.cglb"
    source = root / FIXTURE
    result = run(
        [
            cglc,
            "build",
            FIXTURE,
            "--target",
            target,
            "--output",
            package,
            "--debug-ir",
        ],
        cwd=root,
    )
    if result.returncode != 0:
        return [f"{case_name}: build failed: {result.stderr}{result.stdout}".strip()]

    errors = []
    manifest = load_json(package / "manifest.json", errors, case_name)
    reflection = load_json(package / "reflection.json", errors, case_name)
    debug = load_json(
        package / DEBUG_ARTIFACT_PATHS["debugMetadata"], errors, case_name
    )
    source_map = load_json(
        package / DEBUG_ARTIFACT_PATHS["hirSourceMap"], errors, case_name
    )
    sidecar_explanation = load_json(
        package / TARGET_EXPLANATION_ARTIFACT_PATH, errors, case_name
    )
    explanation = load_target_explanation(errors, case_name, root, cglc)

    expect_manifest_consistency(
        errors, case_name, source, package, target, manifest, reflection
    )
    expect_target_explanation_sidecar_consistency(
        root, tmp_dir, errors, case_name, sidecar_explanation, explanation
    )
    expect_debug_decision_consistency(errors, case_name, target, debug)
    expect_debug_legalization_projection_consistency(
        errors, case_name, debug, explanation
    )
    expect_pseudo_mlir_package_sidecars(errors, case_name, package)
    expect_hir_pass_trace_sidecar(errors, case_name, root, cglc, package, manifest)
    expect_hir_locations_consistency(errors, case_name, root, source, debug, source_map)
    expect_inspect_consistency(errors, case_name, cglc, package, manifest, reflection)
    expect_verify_success(errors, case_name, cglc, package, source, manifest)
    return errors


def valid_self_test_hir_pass_trace():
    pass_ids = [
        "hir.validate.module-shape",
        "hir.optimize.cleanup-dead-local-declarations",
    ]
    return {
        "schemaVersion": HIR_PASS_TRACE_SCHEMA_VERSION,
        "kind": HIR_PASS_TRACE_KIND,
        "optimizationLevel": "O1",
        "passSchedule": {
            "fingerprint": hir_pass_schedule_fingerprint(pass_ids),
            "fingerprintPolicy": HIR_PASS_TRACE_FINGERPRINT_POLICY,
            "stability": "stable-opt-level-policy",
        },
        "scheduledPassCount": 2,
        "passCount": 2,
        "changedPassCount": 1,
        "diagnosticPassCount": 0,
        "errorPassCount": 0,
        "changed": True,
        "completed": True,
        "stopReason": "none",
        "passes": [
            {
                "index": 0,
                "id": pass_ids[0],
                "name": pass_ids[0],
                "category": "validation",
                "changed": False,
                "status": "completed",
                "diagnosticCount": 0,
                "errorCount": 0,
            },
            {
                "index": 1,
                "id": pass_ids[1],
                "name": pass_ids[1],
                "category": "cleanup",
                "changed": True,
                "status": "completed",
                "diagnosticCount": 0,
                "errorCount": 0,
            },
        ],
    }


def valid_empty_self_test_hir_pass_trace():
    return {
        "schemaVersion": HIR_PASS_TRACE_SCHEMA_VERSION,
        "kind": HIR_PASS_TRACE_KIND,
        "optimizationLevel": "O1",
        "passSchedule": {
            "fingerprint": hir_pass_schedule_fingerprint(["hir.validate.module-shape"]),
            "fingerprintPolicy": HIR_PASS_TRACE_FINGERPRINT_POLICY,
            "stability": "caller-defined",
        },
        "scheduledPassCount": 1,
        "passCount": 0,
        "changedPassCount": 0,
        "diagnosticPassCount": 0,
        "errorPassCount": 0,
        "changed": False,
        "completed": False,
        "stopReason": "missing-runner",
        "passes": [],
    }


def cloned_self_test_hir_pass_trace():
    return json.loads(json.dumps(valid_self_test_hir_pass_trace()))


def run_self_test(root):
    del root

    valid_errors = []
    expect_hir_pass_trace_document(
        valid_errors,
        "self-test-valid-hir-pass-trace",
        valid_self_test_hir_pass_trace(),
    )
    failures = []
    if valid_errors:
        failures.extend(valid_errors)
    empty_valid_errors = []
    expect_hir_pass_trace_document(
        empty_valid_errors,
        "self-test-valid-empty-hir-pass-trace",
        valid_empty_self_test_hir_pass_trace(),
    )
    if empty_valid_errors:
        failures.extend(empty_valid_errors)

    negative_cases = []

    def add_negative_case(name, mutate):
        trace = cloned_self_test_hir_pass_trace()
        mutate(trace)
        negative_cases.append((name, trace))

    add_negative_case(
        "schema-version",
        lambda trace: trace.update(
            {"schemaVersion": HIR_PASS_TRACE_SCHEMA_VERSION + 1}
        ),
    )
    add_negative_case(
        "kind",
        lambda trace: trace.update({"kind": "debug-metadata"}),
    )
    add_negative_case(
        "optimization-level",
        lambda trace: trace.update({"optimizationLevel": "O3"}),
    )
    add_negative_case(
        "pass-schedule-fingerprint",
        lambda trace: trace["passSchedule"].update(
            {"fingerprint": "fnv1a64:0000000000000000"}
        ),
    )
    add_negative_case(
        "pass-schedule-fingerprint-policy",
        lambda trace: trace["passSchedule"].update(
            {"fingerprintPolicy": "scheduled-pass-names-v1"}
        ),
    )
    add_negative_case(
        "pass-count",
        lambda trace: trace.update({"passCount": len(trace["passes"]) + 1}),
    )
    add_negative_case(
        "pass-index-order",
        lambda trace: trace["passes"][1].update({"index": 0}),
    )
    add_negative_case(
        "pass-status",
        lambda trace: trace["passes"][0].update({"status": "skipped"}),
    )
    add_negative_case(
        "completed-stop-reason",
        lambda trace: trace.update({"completed": True, "stopReason": "pass-error"}),
    )
    add_negative_case(
        "incomplete-stop-reason",
        lambda trace: trace.update({"completed": False, "stopReason": "none"}),
    )

    for name, trace in negative_cases:
        errors = []
        expect_hir_pass_trace_document(errors, f"self-test-{name}", trace)
        if not errors:
            failures.append(f"self-test-{name}: malformed pass trace was accepted")

    if failures:
        for failure in failures:
            print(
                f"package debug provenance self-test failed: {failure}",
                file=sys.stderr,
            )
        return 1

    print("package debug provenance self-test passed")
    return 0


def parse_args():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", required=True, type=Path)
    parser.add_argument("--cglc", type=Path)
    parser.add_argument(
        "--self-test",
        action="store_true",
        help="run in-memory negative validation tests for checker-owned logic",
    )
    parser.add_argument(
        "--targets",
        nargs="*",
        choices=TARGETS,
        default=TARGETS,
        help="targets to consider; native-only targets are skipped without tools",
    )
    return parser.parse_args()


def main():
    args = parse_args()
    root = args.root.resolve()
    if args.self_test:
        return run_self_test(root)
    if args.cglc is None:
        print(
            "package debug provenance check failed: --cglc is required "
            "unless --self-test is used",
            file=sys.stderr,
        )
        return 2
    cglc = args.cglc.resolve()
    requested_targets = tuple(args.targets)
    errors = []
    probed = []
    skipped = []

    with tempfile.TemporaryDirectory(prefix="crossgl-package-debug-provenance-") as tmp:
        tmp_dir = Path(tmp)
        for target in requested_targets:
            if not target_available(target):
                skipped.append(target)
                continue
            target_errors = probe_target(root, tmp_dir, cglc, target)
            probed.append(target)
            if target_errors:
                errors.extend(target_errors)

    for target in REQUIRED_TARGETS:
        if target in requested_targets and target not in probed:
            fail(errors, "package-debug-provenance", f"did not probe required {target}")

    if errors:
        for error in errors:
            print(f"package debug provenance check failed: {error}", file=sys.stderr)
        if skipped:
            print(
                f"skipped optional native targets: {', '.join(skipped)}",
                file=sys.stderr,
            )
        return 1

    message = f"validated package debug provenance for: {', '.join(probed)}"
    if skipped:
        message += f" (skipped optional native targets: {', '.join(skipped)})"
    print(message)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
