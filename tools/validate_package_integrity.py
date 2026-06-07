#!/usr/bin/env python3
"""Validate CrossGL package metadata and artifact integrity."""

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path, PureWindowsPath

from package_target_contracts import (
    PACKAGE_TARGETS_REQUIRING_NATIVE_STATUS,
    TARGET_REQUIRED_PATH_ARTIFACTS,
)


ROOT_PACKAGE_FILES = ["manifest.json", "reflection.json", "diagnostics.json"]
ARTIFACT_STATUS_FIELD = "nativeBinaryStatus"
ALLOWED_NATIVE_BINARY_STATUSES = ("planned", "emitted", "validated")
SCHEMA_ARTIFACTS = [
    ("debugMetadata", "debug_metadata_schema", "--debug-metadata-schema"),
    ("hirSourceMap", "hir_source_map_schema", "--hir-source-map-schema"),
    (
        "targetExplanation",
        "target_explanation_schema",
        "--target-explanation-schema",
    ),
    (
        "nativeProfile",
        "vulkan_native_profile_schema",
        "--vulkan-native-profile-schema",
    ),
]
SCHEMA_ROOT_DEFAULTS = {
    "manifest_schema": "manifest-v1.schema.json",
    "reflection_schema": "reflection-v1.schema.json",
    "diagnostics_schema": "diagnostics-v1.schema.json",
    "debug_metadata_schema": "debug-metadata-v11.schema.json",
    "hir_source_map_schema": "hir-source-map-v7.schema.json",
    "target_explanation_schema": "target-explanation-v1.schema.json",
    "vulkan_native_profile_schema": "vulkan-native-profile-v1.schema.json",
}
DEBUG_IR_ARTIFACTS = ("debugMetadata", "hirSourceMap")
PACKAGE_ARTIFACT_REQUIREMENT_KEYS = {
    "target",
    "packageMode",
    "requiredPathArtifacts",
    "requiresNativeBinaryStatus",
    "allowsPlannedNativeBinary",
    "allowsPlannedNativeSourceEvidence",
}
OPTIONAL_PACKAGE_ARTIFACT_REQUIREMENT_KEYS = {
    "evidenceIds",
}
PACKAGE_PATH_ARTIFACTS = {
    "backendSource",
    "backendAssembly",
    "intermediate",
    "nativeBinary",
}


class DuplicateCheckingDict(dict):
    def __init__(self, pairs):
        super().__init__()
        self.duplicate_keys = []
        for key, value in pairs:
            if key in self:
                self.duplicate_keys.append(key)
            self[key] = value


def json_path_for_key(parent, key):
    if isinstance(key, str) and key.isidentifier():
        return f"{parent}.{key}"
    escaped = str(key).replace("\\", "\\\\").replace('"', '\\"')
    return f'{parent}["{escaped}"]'


def collect_duplicate_key_errors(value, path, errors, file_name):
    if isinstance(value, DuplicateCheckingDict):
        for key in value.duplicate_keys:
            errors.append(
                f"{file_name}: duplicate JSON object key {json_path_for_key(path, key)}"
            )
        for key, child in value.items():
            collect_duplicate_key_errors(
                child,
                json_path_for_key(path, key),
                errors,
                file_name,
            )
    elif isinstance(value, list):
        for index, child in enumerate(value):
            collect_duplicate_key_errors(
                child,
                f"{path}[{index}]",
                errors,
                file_name,
            )


def load_json(path, errors, label=None):
    file_label = label or path.name
    try:
        with path.open("r", encoding="utf-8") as handle:
            document = json.load(handle, object_pairs_hook=DuplicateCheckingDict)
            collect_duplicate_key_errors(document, "$", errors, file_label)
            return document
    except (OSError, json.JSONDecodeError) as exc:
        errors.append(f"{file_label}: failed to read JSON: {exc}")
        return None


def path_relative_to(path, root):
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


def is_absolute_artifact_path(value):
    windows_path = PureWindowsPath(value)
    return (
        Path(value).is_absolute()
        or windows_path.is_absolute()
        or bool(windows_path.drive)
    )


def resolve_artifact_path(package_root, raw_path):
    return (package_root / raw_path).resolve(strict=False)


def validate_package_relative_path(path, value, errors, noun="path"):
    if not isinstance(value, str):
        errors.append(f"{path}: expected string {noun}")
        return False
    if value == "":
        errors.append(f"{path}: {noun} must not be empty")
        return False
    if "\\" in value:
        errors.append(f"{path}: {noun}s must use '/' separators")
        return False
    if is_absolute_artifact_path(value):
        errors.append(f"{path}: {noun} must be package-relative")
        return False
    if ".." in Path(value).parts:
        errors.append(f"{path}: {noun} escapes package: {value}")
        return False
    return True


def validate_schema(schema_path, validator_path, instance_path, label, option, errors):
    if schema_path is None:
        return
    if validator_path is None:
        errors.append(f"--json-schema-validator is required with {option}")
        return

    result = subprocess.run(
        [
            sys.executable,
            str(validator_path),
            "--schema",
            str(schema_path),
            "--instance",
            str(instance_path),
        ],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if result.returncode != 0:
        output = (result.stderr + result.stdout).strip()
        errors.append(f"{label}: schema validation failed: {output}")


def apply_schema_root_defaults(args):
    if args.schema_root is None:
        return
    for attribute, file_name in SCHEMA_ROOT_DEFAULTS.items():
        if getattr(args, attribute) is None:
            setattr(args, attribute, args.schema_root / file_name)


def validate_native_package_integrity(
    package_verifier, package_path, source_path, errors
):
    if package_verifier is None:
        return

    command = [str(package_verifier), "package", "verify", str(package_path)]
    if source_path is not None:
        command.extend(["--source", str(source_path)])
    command.append("--json")

    try:
        result = subprocess.run(
            command,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
    except OSError as exc:
        errors.append(f"--package-verifier: failed to run {package_verifier}: {exc}")
        return

    payload = None
    output = result.stdout.strip()
    if output:
        try:
            payload = json.loads(output)
        except json.JSONDecodeError as exc:
            if result.returncode == 0:
                errors.append(f"package verifier emitted invalid JSON: {exc}")
                return
    elif result.returncode == 0:
        errors.append("package verifier emitted no JSON")
        return

    if payload is not None:
        success = payload.get("success")
        if result.returncode == 0 and success is True:
            diagnostics = payload.get("diagnostics")
            if isinstance(diagnostics, list):
                for diagnostic in diagnostics:
                    if not isinstance(diagnostic, dict):
                        continue
                    severity = diagnostic.get("severity", "diagnostic")
                    if severity == "error":
                        continue
                    code = diagnostic.get("code", "unknown")
                    message = diagnostic.get("message", "")
                    print(
                        f"package verifier {severity}: {code}: {message}",
                        file=sys.stdout,
                    )
            return

        diagnostics = payload.get("diagnostics")
        if isinstance(diagnostics, list) and diagnostics:
            for diagnostic in diagnostics:
                if not isinstance(diagnostic, dict):
                    errors.append(
                        "package verifier failed: malformed diagnostic record"
                    )
                    continue
                severity = diagnostic.get("severity", "diagnostic")
                code = diagnostic.get("code", "unknown")
                message = diagnostic.get("message", "")
                errors.append(f"package verifier failed: {severity} {code}: {message}")
            return
        if result.returncode != 0 or success is not True:
            errors.append("package verifier failed without diagnostics")
            return
        return

    fallback_output = (result.stderr + result.stdout).strip()
    if not fallback_output:
        fallback_output = f"exited with status {result.returncode}"
    for line in fallback_output.splitlines():
        errors.append(f"package verifier failed: {line}")


def resolve_schema_artifact_path(package_root, manifest, name):
    artifacts = manifest.get("artifacts")
    if not isinstance(artifacts, dict):
        return None
    value = artifacts.get(name)
    if not isinstance(value, str):
        return None
    if (
        value == ""
        or "\\" in value
        or is_absolute_artifact_path(value)
        or ".." in Path(value).parts
    ):
        return None

    resolved = resolve_artifact_path(package_root, value)
    if not path_relative_to(resolved, package_root):
        return None
    if not resolved.is_file():
        return None
    return resolved, value


def validate_artifact_schemas(args, package_root, manifest, errors):
    for artifact_name, schema_attr, option in SCHEMA_ARTIFACTS:
        schema_path = getattr(args, schema_attr)
        if schema_path is None:
            continue
        resolved = resolve_schema_artifact_path(package_root, manifest, artifact_name)
        if resolved is None:
            continue
        instance_path, package_path = resolved
        validate_schema(
            schema_path,
            args.json_schema_validator,
            instance_path,
            package_path,
            option,
            errors,
        )


def load_resolved_artifact_json(package_root, manifest, artifact_name, errors):
    resolved = resolve_schema_artifact_path(package_root, manifest, artifact_name)
    if resolved is None:
        return None, None
    artifact_path, package_path = resolved
    return load_json(artifact_path, errors, package_path), package_path


def validate_package_source_map_filters(source_map, package_path, errors):
    if not isinstance(source_map, dict):
        return
    filters = source_map.get("filters")
    if filters != {"activeCount": 0}:
        errors.append(f"{package_path}: package source map must be unfiltered")


def validate_package_source_map_pagination(source_map, package_path, errors):
    if not isinstance(source_map, dict):
        return
    pagination = source_map.get("pagination")
    locations = source_map.get("hirSourceLocations")
    if not isinstance(pagination, dict) or not isinstance(locations, dict):
        return

    limit_fields = [field for field in pagination if field.endswith("Limit")]
    if pagination.get("activeCount") != 0 or limit_fields:
        errors.append(f"{package_path}: package source map pagination must be inactive")
        return

    for kind, array_field in (
        ("expression", "expressions"),
        ("type", "types"),
        ("statement", "statements"),
    ):
        if array_field not in locations:
            continue
        records = locations[array_field]
        if not isinstance(records, list):
            continue
        total = len(records)
        expected = {
            f"{kind}Offset": 0,
            f"{kind}TotalCount": total,
            f"{kind}EmittedCount": total,
            f"{kind}HasMore": False,
            f"{kind}NextOffset": total,
        }
        for field, expected_value in expected.items():
            if pagination.get(field) != expected_value:
                errors.append(
                    f"{package_path}: expected {field} to describe a complete "
                    "unpaged source map"
                )
                return


def count_package_category_entries(records, field):
    counts = {}
    for record in records:
        if not isinstance(record, dict):
            return None
        name = record.get(field)
        if not isinstance(name, str):
            return None
        counts[name] = counts.get(name, 0) + 1
    return [{"name": name, "count": counts[name]} for name in sorted(counts)]


def validate_package_source_map_category_counts(source_map, package_path, errors):
    if not isinstance(source_map, dict):
        return
    categories = source_map.get("categoryCounts")
    locations = source_map.get("hirSourceLocations")
    if not isinstance(categories, dict) or not isinstance(locations, dict):
        return

    total = 0
    complete = True
    for array_field, total_field, category_field, record_field in (
        ("expressions", "expressionTotalCount", "expressionKinds", "kind"),
        ("types", "typeTotalCount", "typeOwnerKinds", "ownerKind"),
        ("statements", "statementTotalCount", "statementKinds", "statementKind"),
    ):
        records = locations.get(array_field)
        if not isinstance(records, list):
            complete = False
            continue

        expected_total = len(records)
        total += expected_total
        if categories.get(total_field) != expected_total:
            errors.append(
                f"{package_path}: expected categoryCounts.{total_field} to "
                "match complete package source map"
            )

        entries = categories.get(category_field)
        expected_entries = count_package_category_entries(records, record_field)
        if (
            isinstance(entries, list)
            and expected_entries is not None
            and entries != expected_entries
        ):
            errors.append(
                f"{package_path}: expected categoryCounts.{category_field} to "
                "match package source map records"
            )

    if complete and categories.get("recordTotalCount") != total:
        errors.append(
            f"{package_path}: expected categoryCounts.recordTotalCount to "
            "match complete package source map"
        )

    records = source_map.get("records")
    if (
        isinstance(records, dict)
        and isinstance(categories.get("recordTotalCount"), int)
        and records.get("totalCount") != categories["recordTotalCount"]
    ):
        errors.append(
            f"{package_path}: expected records.totalCount to match "
            "categoryCounts.recordTotalCount"
        )


def validate_package_source_map_records(source_map, package_path, errors):
    if not isinstance(source_map, dict):
        return
    records = source_map.get("records")
    if not isinstance(records, dict):
        return
    if (
        records.get("enabled") is not False
        or records.get("activeCount") != 0
        or records.get("offset") != 0
        or "limit" in records
        or records.get("emittedCount") != 0
        or records.get("hasMore") is not False
        or records.get("nextOffset") != 0
        or records.get("items") != []
    ):
        errors.append(f"{package_path}: package source map records must be disabled")


def validate_debug_ir_artifact_pair(package_root, manifest, errors):
    debug_metadata, debug_path = load_resolved_artifact_json(
        package_root, manifest, "debugMetadata", errors
    )
    hir_source_map, source_map_path = load_resolved_artifact_json(
        package_root, manifest, "hirSourceMap", errors
    )
    if debug_metadata is None or hir_source_map is None:
        return

    validate_package_source_map_filters(hir_source_map, source_map_path, errors)
    validate_package_source_map_pagination(hir_source_map, source_map_path, errors)
    validate_package_source_map_category_counts(hir_source_map, source_map_path, errors)
    validate_package_source_map_records(hir_source_map, source_map_path, errors)

    debug_locations = debug_metadata.get("hirSourceLocations")
    source_map_locations = hir_source_map.get("hirSourceLocations")
    if (
        isinstance(debug_locations, dict)
        and isinstance(source_map_locations, dict)
        and source_map_locations != debug_locations
    ):
        errors.append(f"{source_map_path}: hirSourceLocations must match {debug_path}")


def validate_source_hash(source_path, manifest, errors):
    if source_path is None:
        return
    try:
        source = source_path.read_bytes()
    except OSError as exc:
        errors.append(f"--source: failed to read {source_path}: {exc}")
        return

    source_hash = manifest.get("sourceHash")
    if not isinstance(source_hash, dict):
        errors.append("$.sourceHash: expected sourceHash object")
        return
    if source_hash.get("algorithm") != "sha256":
        errors.append("$.sourceHash.algorithm: expected sha256")
        return

    expected = hashlib.sha256(source).hexdigest()
    actual = source_hash.get("value")
    if actual != expected:
        errors.append(
            f"$.sourceHash.value: expected source hash {expected}, got {actual!r}"
        )


def validate_root_files(package_root, errors):
    for file_name in ROOT_PACKAGE_FILES:
        path = package_root / file_name
        if not path.exists():
            errors.append(f"$: expected {file_name} in package")
        elif not path.is_file():
            errors.append(f"$: expected {file_name} to be a file")


def validate_artifact_path(package_root, name, value, should_exist, errors):
    path = f"$.artifacts.{name}"
    if not validate_package_relative_path(path, value, errors, "artifact path"):
        return

    resolved = resolve_artifact_path(package_root, value)
    if not path_relative_to(resolved, package_root):
        errors.append(f"{path}: artifact path escapes package: {value}")
        return

    if should_exist:
        if not resolved.exists():
            errors.append(f"{path}: artifact does not exist: {value}")
        elif not resolved.is_file():
            errors.append(f"{path}: artifact is not a file: {value}")


def legacy_package_artifact_requirements(target):
    required_path_artifacts = TARGET_REQUIRED_PATH_ARTIFACTS.get(target)
    if required_path_artifacts is None:
        return None
    requires_native_status = target in PACKAGE_TARGETS_REQUIRING_NATIVE_STATUS
    return {
        "target": target,
        "packageMode": "source-package" if requires_native_status else "native",
        "requiredPathArtifacts": required_path_artifacts,
        "requiresNativeBinaryStatus": requires_native_status,
        "allowsPlannedNativeBinary": requires_native_status,
        "allowsPlannedNativeSourceEvidence": requires_native_status,
    }


def validate_package_artifact_requirements(manifest, errors):
    target = manifest.get("target")
    if not isinstance(target, str):
        return None

    requirements = manifest.get("packageArtifactRequirements")
    if requirements is None:
        return legacy_package_artifact_requirements(target)
    if not isinstance(requirements, dict):
        errors.append("$.packageArtifactRequirements: expected object")
        return None

    allowed_keys = (
        PACKAGE_ARTIFACT_REQUIREMENT_KEYS | OPTIONAL_PACKAGE_ARTIFACT_REQUIREMENT_KEYS
    )
    unknown_keys = sorted(set(requirements) - allowed_keys)
    for key in unknown_keys:
        errors.append(f"$.packageArtifactRequirements.{key}: unexpected property")
    missing_keys = sorted(PACKAGE_ARTIFACT_REQUIREMENT_KEYS - set(requirements))
    for key in missing_keys:
        errors.append(f"$.packageArtifactRequirements.{key}: missing property")
    if unknown_keys or missing_keys:
        return None

    if requirements["target"] != target:
        errors.append(
            "$.packageArtifactRequirements.target: must match manifest target"
        )
    if requirements["packageMode"] not in {"native", "source-package"}:
        errors.append(
            "$.packageArtifactRequirements.packageMode: expected native or "
            "source-package"
        )

    required_path_artifacts = requirements["requiredPathArtifacts"]
    if not isinstance(required_path_artifacts, list) or not required_path_artifacts:
        errors.append(
            "$.packageArtifactRequirements.requiredPathArtifacts: "
            "expected non-empty array"
        )
        return None
    seen = set()
    for index, artifact in enumerate(required_path_artifacts):
        path = f"$.packageArtifactRequirements.requiredPathArtifacts[{index}]"
        if not isinstance(artifact, str) or artifact not in PACKAGE_PATH_ARTIFACTS:
            errors.append(f"{path}: expected known path artifact key")
            continue
        if artifact in seen:
            errors.append(f"{path}: duplicate artifact key")
        seen.add(artifact)

    for key in (
        "requiresNativeBinaryStatus",
        "allowsPlannedNativeBinary",
        "allowsPlannedNativeSourceEvidence",
    ):
        if not isinstance(requirements[key], bool):
            errors.append(f"$.packageArtifactRequirements.{key}: expected boolean")
    if (
        requirements["allowsPlannedNativeSourceEvidence"]
        and not requirements["allowsPlannedNativeBinary"]
    ):
        errors.append(
            "$.packageArtifactRequirements.allowsPlannedNativeSourceEvidence: "
            "requires allowsPlannedNativeBinary"
        )
    evidence_ids = requirements.get("evidenceIds")
    if evidence_ids is not None:
        if not isinstance(evidence_ids, list) or not evidence_ids:
            errors.append(
                "$.packageArtifactRequirements.evidenceIds: expected non-empty array"
            )
        else:
            seen_evidence_ids = set()
            for index, evidence_id in enumerate(evidence_ids):
                path = f"$.packageArtifactRequirements.evidenceIds[{index}]"
                if not isinstance(evidence_id, str) or not evidence_id:
                    errors.append(f"{path}: expected non-empty string")
                    continue
                if evidence_id in seen_evidence_ids:
                    errors.append(f"{path}: duplicate evidence ID")
                seen_evidence_ids.add(evidence_id)

    return requirements


def validate_target_artifacts(target, artifacts, requirements, errors):
    if requirements is None:
        return

    for name in requirements["requiredPathArtifacts"]:
        if name not in artifacts:
            errors.append(f"$.artifacts.{name}: {target} packages require {name}")

    if ARTIFACT_STATUS_FIELD in artifacts:
        native_status = artifacts[ARTIFACT_STATUS_FIELD]
        if native_status not in ALLOWED_NATIVE_BINARY_STATUSES:
            expected = ", ".join(
                repr(status) for status in ALLOWED_NATIVE_BINARY_STATUSES
            )
            errors.append(
                f"$.artifacts.{ARTIFACT_STATUS_FIELD}: expected one of {expected}"
            )

    if (
        ARTIFACT_STATUS_FIELD in artifacts
        and not requirements["requiresNativeBinaryStatus"]
    ):
        errors.append(
            f"$.artifacts.{ARTIFACT_STATUS_FIELD}: "
            f"{target} packages must not declare nativeBinaryStatus"
        )
    elif ARTIFACT_STATUS_FIELD in artifacts and "nativeBinary" not in artifacts:
        errors.append(
            "$.artifacts.nativeBinary: nativeBinaryStatus requires nativeBinary"
        )
    elif (
        requirements["requiresNativeBinaryStatus"]
        and ARTIFACT_STATUS_FIELD not in artifacts
    ):
        errors.append(
            f"$.artifacts.{ARTIFACT_STATUS_FIELD}: "
            f"{target} packages require nativeBinaryStatus"
        )


def validate_artifacts(package_root, manifest, errors):
    artifacts = manifest.get("artifacts")
    if not isinstance(artifacts, dict):
        errors.append("$.artifacts: expected artifacts object")
        return

    present_debug_artifacts = [
        artifact for artifact in DEBUG_IR_ARTIFACTS if artifact in artifacts
    ]
    if len(present_debug_artifacts) == 1:
        errors.append(
            "$.artifacts: debugMetadata and hirSourceMap must be emitted together"
        )

    target = manifest.get("target")
    requirements = validate_package_artifact_requirements(manifest, errors)
    validate_target_artifacts(target, artifacts, requirements, errors)

    native_status = artifacts.get(ARTIFACT_STATUS_FIELD)
    for name, value in artifacts.items():
        if name == ARTIFACT_STATUS_FIELD:
            continue
        planned_native_binary = (
            name == "nativeBinary"
            and native_status == "planned"
            and requirements is not None
            and requirements["allowsPlannedNativeBinary"]
        )
        should_exist = not planned_native_binary
        validate_artifact_path(package_root, name, value, should_exist, errors)


def validate_reflection_native_binary(manifest, reflection, errors):
    if not isinstance(reflection, dict):
        return
    if "nativeBinary" not in reflection:
        return

    native_binary = reflection["nativeBinary"]
    if native_binary == "":
        return
    if not validate_package_relative_path(
        "$.nativeBinary", native_binary, errors, "native binary path"
    ):
        return

    artifacts = manifest.get("artifacts")
    if not isinstance(artifacts, dict):
        return
    manifest_native_binary = artifacts.get("nativeBinary")
    if (
        isinstance(manifest_native_binary, str)
        and native_binary != manifest_native_binary
    ):
        errors.append(
            "$.nativeBinary: expected manifest artifacts.nativeBinary "
            f"{manifest_native_binary!r}, got {native_binary!r}"
        )


def validate_package(args):
    errors = []
    package_root = args.package.resolve(strict=False)
    if not package_root.exists():
        errors.append(f"{package_root}: package directory does not exist")
        return errors
    if not package_root.is_dir():
        errors.append(f"{package_root}: package path is not a directory")
        return errors

    native_integrity_checks = args.package_verifier is not None
    if native_integrity_checks:
        validate_native_package_integrity(
            args.package_verifier, args.package, args.source, errors
        )
    else:
        validate_root_files(package_root, errors)

    manifest_path = package_root / "manifest.json"
    manifest = load_json(manifest_path, errors)
    if manifest is None:
        return errors
    reflection_path = package_root / "reflection.json"
    reflection = load_json(reflection_path, errors)

    validate_schema(
        args.manifest_schema,
        args.json_schema_validator,
        manifest_path,
        "manifest.json",
        "--manifest-schema",
        errors,
    )
    if reflection is not None:
        validate_schema(
            args.reflection_schema,
            args.json_schema_validator,
            reflection_path,
            "reflection.json",
            "--reflection-schema",
            errors,
        )
    diagnostics_path = package_root / "diagnostics.json"
    if diagnostics_path.exists() and diagnostics_path.is_file():
        validate_schema(
            args.diagnostics_schema,
            args.json_schema_validator,
            diagnostics_path,
            "diagnostics.json",
            "--diagnostics-schema",
            errors,
        )
    if not native_integrity_checks:
        validate_source_hash(args.source, manifest, errors)
    if not native_integrity_checks:
        validate_artifacts(package_root, manifest, errors)
    validate_artifact_schemas(args, package_root, manifest, errors)
    validate_debug_ir_artifact_pair(package_root, manifest, errors)
    if not native_integrity_checks:
        validate_reflection_native_binary(manifest, reflection, errors)
    return errors


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--package", required=True, type=Path)
    parser.add_argument("--source", type=Path)
    parser.add_argument("--manifest-schema", type=Path)
    parser.add_argument("--reflection-schema", type=Path)
    parser.add_argument("--diagnostics-schema", type=Path)
    parser.add_argument("--debug-metadata-schema", type=Path)
    parser.add_argument("--hir-source-map-schema", type=Path)
    parser.add_argument("--target-explanation-schema", type=Path)
    parser.add_argument("--vulkan-native-profile-schema", type=Path)
    parser.add_argument("--schema-root", type=Path)
    parser.add_argument("--json-schema-validator", type=Path)
    parser.add_argument(
        "--package-verifier",
        type=Path,
        help="Path to cglc; when set, package root/artifact integrity is "
        "checked with `cglc package verify --json`.",
    )
    args = parser.parse_args()

    apply_schema_root_defaults(args)
    errors = validate_package(args)
    if errors:
        for error in errors:
            print(f"package integrity validation failed: {error}", file=sys.stderr)
        return 1

    print(f"validated package integrity: {args.package}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
