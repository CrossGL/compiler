"""Semantic checks for release-report-artifact-inventory-v1.schema.json."""

from collections import Counter
import posixpath
import re

from .common import (
    add_equal_error,
    add_length_count_error,
    validate_source_location_span,
)


SEVERITIES = ("note", "warning", "error")
SOURCE_INPUT_FIELD = {
    "release-bundle": "bundlePath",
    "publish-plan": "publishPlanPath",
    "publish-stage": "stageReportPath",
}
SOURCE_COUNT_FIELD = {
    "release-bundle": "bundleArtifactRecordCount",
    "publish-plan": "publishPlanArtifactRecordCount",
    "publish-stage": "publishStageArtifactRecordCount",
}
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
NATIVE_ARTIFACT_DESCRIPTOR_SUFFIX = ".native-artifact.json"
NATIVE_BINARY_PATH_RE = re.compile(
    r"^backend/(?:directx|metal|opengl|vulkan)/[^/]+\.(?:dxbc|dxil|glsl|metallib|spv)$"
)
BACKEND_NATIVE_BINARY_PATH_RE = re.compile(
    r"^backend/(?P<target>directx|metal|opengl|vulkan)/"
    r"(?P<stem>[^/]+)\.(?:dxbc|dxil|glsl|metallib|spv)$"
)
BACKEND_NATIVE_ARTIFACT_DESCRIPTOR_PATH_RE = re.compile(
    r"^backend/(?P<target>directx|metal|opengl|vulkan)/"
    r"(?P<stem>[^/]+)\.native-artifact\.json$"
)


def is_native_binary_path(value):
    if value.endswith(".comp.glsl"):
        return False
    return NATIVE_BINARY_PATH_RE.fullmatch(value) is not None


def is_native_artifact_descriptor_path(value):
    normalized = normalized_path(value)
    return (
        normalized.endswith(NATIVE_ARTIFACT_DESCRIPTOR_SUFFIX)
        or posixpath.basename(normalized) == "native-artifact.json"
    )


def is_backend_native_artifact_descriptor_path(value):
    return (
        BACKEND_NATIVE_ARTIFACT_DESCRIPTOR_PATH_RE.fullmatch(normalized_path(value))
        is not None
    )


def backend_descriptor_path_for_native_binary(value):
    normalized = normalized_path(value)
    if normalized.endswith(".comp.glsl"):
        return None
    match = BACKEND_NATIVE_BINARY_PATH_RE.fullmatch(normalized)
    if match is None:
        return None
    return (
        f"backend/{match.group('target')}/"
        f"{match.group('stem')}{NATIVE_ARTIFACT_DESCRIPTOR_SUFFIX}"
    )


def normalized_path(value):
    if value is None:
        return ""
    return posixpath.normpath(value)


def validate_filesystem_path(errors, path, value):
    if value.strip() == "":
        errors.append(f"{path}: expected non-empty path")
        return
    if "\\" in value:
        errors.append(f"{path}: expected normalized '/' separators")
    parts = value.split("/")
    if value.startswith("/"):
        parts = parts[1:]
    if any(part in ("", ".", "..") for part in parts):
        errors.append(f"{path}: expected normalized path")


def validate_relative_path(errors, path, value):
    if value.strip() == "":
        errors.append(f"{path}: expected non-empty path")
        return
    if "\\" in value:
        errors.append(f"{path}: expected normalized '/' separators")
    if value.startswith("/"):
        errors.append(f"{path}: expected relative path")
    parts = value.split("/")
    if any(part in ("", ".", "..") for part in parts):
        errors.append(f"{path}: expected normalized relative path")


def staged_path_matches_destination(staged_path, destination_path):
    normalized_staged_path = normalized_path(staged_path)
    normalized_destination_path = normalized_path(destination_path)
    return normalized_staged_path == normalized_destination_path or (
        normalized_destination_path != ""
        and normalized_staged_path.endswith(f"/{normalized_destination_path}")
    )


def record_order_key(record):
    return (
        normalized_path(record["packagePath"]),
        record["packageArtifactPath"],
        record["sourceRecordKind"],
        record["destinationPath"] or "",
        normalized_path(record["stagedPath"]) if record["stagedPath"] else "",
    )


def record_identity(record):
    return (
        record["sourceRecordKind"],
        normalized_path(record["packagePath"]),
        record["packageArtifactPath"],
    )


def artifact_identity(record):
    return (normalized_path(record["packagePath"]), record["packageArtifactPath"])


def validate_cross_source_record_consistency(errors, records):
    records_by_artifact = {}
    paths_by_record = {}
    for index, record in enumerate(records):
        identity = artifact_identity(record)
        records_by_artifact.setdefault(identity, []).append(record)
        paths_by_record[id(record)] = f"$.records[{index}]"

    for identity, artifact_records in records_by_artifact.items():
        if len(artifact_records) < 2:
            continue
        source_kinds = {record["sourceRecordKind"] for record in artifact_records}
        if len(source_kinds) < 2:
            continue

        reference = artifact_records[0]
        reference_path = paths_by_record[id(reference)]
        for record in artifact_records[1:]:
            record_path = paths_by_record[id(record)]
            for field in ("sizeBytes", "sha256"):
                if record[field] != reference[field]:
                    errors.append(
                        f"{record_path}.{field}: expected artifact evidence to match "
                        f"{reference_path}.{field} for package artifact {identity!r}"
                    )

        publish_records = [
            record
            for record in artifact_records
            if record["sourceRecordKind"] in ("publish-plan", "publish-stage")
        ]
        if len(publish_records) < 2:
            continue
        reference = publish_records[0]
        reference_path = paths_by_record[id(reference)]
        for record in publish_records[1:]:
            if record["destinationPath"] != reference["destinationPath"]:
                errors.append(
                    f"{paths_by_record[id(record)]}.destinationPath: expected "
                    f"publish destination to match {reference_path}.destinationPath "
                    f"for package artifact {identity!r}"
                )


def validate_native_descriptor_provenance_window(errors, records):
    records_by_package = {}
    paths_by_record = {}
    for index, record in enumerate(records):
        package_path = normalized_path(record["packagePath"])
        records_by_package.setdefault(package_path, []).append((index, record))
        paths_by_record[id(record)] = f"$.records[{index}]"

    for package_path, indexed_package_records in records_by_package.items():
        native_source_kinds = {
            record["sourceRecordKind"]
            for _, record in indexed_package_records
            if is_native_binary_path(record["packageArtifactPath"])
        }
        descriptor_records = [
            (index, record)
            for index, record in indexed_package_records
            if is_native_artifact_descriptor_path(record["packageArtifactPath"])
        ]
        if native_source_kinds and not descriptor_records:
            errors.append(
                "$.records: package "
                f"{package_path!r} reports native binary artifact provenance "
                f"from {', '.join(sorted(native_source_kinds))} but omits "
                "required nativeArtifactDescriptor descriptor provenance"
            )
            continue

        descriptor_source_kinds = {
            record["sourceRecordKind"] for _, record in descriptor_records
        }
        missing_source_kinds = sorted(native_source_kinds - descriptor_source_kinds)
        for source_kind in missing_source_kinds:
            errors.append(
                "$.records: package "
                f"{package_path!r} reports {source_kind} native binary artifact "
                f"but omits {source_kind} nativeArtifactDescriptor descriptor "
                "provenance"
            )

        if native_source_kinds and descriptor_records:
            reference_index, reference_record = descriptor_records[0]
            reference_path = normalized_path(reference_record["packageArtifactPath"])
            reference_record_path = paths_by_record[id(reference_record)]
            for index, record in descriptor_records[1:]:
                if normalized_path(record["packageArtifactPath"]) != reference_path:
                    errors.append(
                        f"$.records[{index}].packageArtifactPath: expected "
                        "nativeArtifactDescriptor path to match "
                        f"{reference_record_path}.packageArtifactPath for package "
                        f"{package_path!r}"
                    )

        expected_backend_descriptor_paths = {
            descriptor_path
            for _, record in indexed_package_records
            for descriptor_path in (
                backend_descriptor_path_for_native_binary(
                    record["packageArtifactPath"]
                ),
            )
            if descriptor_path is not None
        }
        if expected_backend_descriptor_paths:
            sorted_expected_paths = sorted(expected_backend_descriptor_paths)
            for index, record in descriptor_records:
                descriptor_path = normalized_path(record["packageArtifactPath"])
                if not is_backend_native_artifact_descriptor_path(descriptor_path):
                    continue
                if descriptor_path in expected_backend_descriptor_paths:
                    continue
                if len(sorted_expected_paths) == 1:
                    errors.append(
                        f"$.records[{index}].packageArtifactPath: expected backend "
                        "nativeArtifactDescriptor path to match native "
                        "binary-derived descriptor path "
                        f"{sorted_expected_paths[0]!r} for package "
                        f"{package_path!r}, got {descriptor_path!r}"
                    )
                else:
                    errors.append(
                        f"$.records[{index}].packageArtifactPath: expected backend "
                        "nativeArtifactDescriptor path to match one of native "
                        "binary-derived descriptor paths "
                        f"{sorted_expected_paths!r} for package {package_path!r}, "
                        f"got {descriptor_path!r}"
                    )

        for index, record in descriptor_records:
            if record["sizeBytes"] is None:
                errors.append(
                    f"$.records[{index}].sizeBytes: nativeArtifactDescriptor "
                    "release records require descriptor byte provenance"
                )
            if record["sha256"] is None:
                errors.append(
                    f"$.records[{index}].sha256: nativeArtifactDescriptor "
                    "release records require descriptor checksum provenance"
                )


def validate_record(errors, path, record, instance):
    kind = record["sourceRecordKind"]
    source_field = SOURCE_INPUT_FIELD[kind]
    if instance[source_field] is None:
        errors.append(
            f"{path}.sourceRecordKind: {kind} record requires $.{source_field}"
        )

    validate_filesystem_path(errors, f"{path}.packagePath", record["packagePath"])
    validate_relative_path(
        errors,
        f"{path}.packageArtifactPath",
        record["packageArtifactPath"],
    )

    staged_path = record["stagedPath"]
    if kind == "publish-stage":
        if staged_path is None:
            errors.append(
                f"{path}.stagedPath: publish-stage record requires stagedPath"
            )
        else:
            validate_filesystem_path(errors, f"{path}.stagedPath", staged_path)
    elif staged_path is not None:
        errors.append(f"{path}.stagedPath: {kind} record must use null stagedPath")

    destination_path = record["destinationPath"]
    if kind in ("publish-plan", "publish-stage"):
        if destination_path is None:
            errors.append(
                f"{path}.destinationPath: {kind} record requires destinationPath"
            )
        else:
            validate_relative_path(errors, f"{path}.destinationPath", destination_path)
            if (
                kind == "publish-stage"
                and staged_path is not None
                and staged_path.strip() != ""
                and destination_path.strip() != ""
                and not staged_path_matches_destination(staged_path, destination_path)
            ):
                errors.append(
                    f"{path}.stagedPath: expected staged path to end with "
                    "destinationPath"
                )
    elif destination_path is not None:
        errors.append(
            f"{path}.destinationPath: release-bundle record must use null destinationPath"
        )

    size_bytes = record["sizeBytes"]
    sha256 = record["sha256"]
    if kind in ("publish-plan", "publish-stage"):
        if size_bytes is None:
            errors.append(f"{path}.sizeBytes: {kind} record requires sizeBytes")
        if sha256 is None:
            errors.append(f"{path}.sha256: {kind} record requires sha256")
    elif (size_bytes is None) != (sha256 is None):
        errors.append(f"{path}.sha256: sizeBytes and sha256 must be recorded together")

    if sha256 is not None and SHA256_RE.fullmatch(sha256) is None:
        errors.append(f"{path}.sha256: expected lowercase SHA-256 digest")


def validate_semantics(instance):
    errors = []

    input_fields = ("bundlePath", "publishPlanPath", "stageReportPath")
    if all(instance[field] is None for field in input_fields):
        errors.append("$: expected at least one input path")
    input_path_fields_by_identity = {}
    for field in input_fields:
        value = instance[field]
        if value is not None:
            validate_filesystem_path(errors, f"$.{field}", value)
            if value.strip() != "":
                identity = normalized_path(value)
                previous_field = input_path_fields_by_identity.get(identity)
                if previous_field is not None:
                    errors.append(
                        f"$.{field}: expected distinct input path from "
                        f"$.{previous_field}"
                    )
                else:
                    input_path_fields_by_identity[identity] = field

    diagnostics = instance["diagnostics"]
    counts = Counter(diagnostic["severity"] for diagnostic in diagnostics)
    for severity in SEVERITIES:
        add_equal_error(
            errors,
            f"$.diagnosticCounts.{severity}",
            instance["diagnosticCounts"][severity],
            counts[severity],
            f"{severity} diagnostic count",
        )

    add_length_count_error(
        errors,
        "$.artifactRecordCount",
        instance["artifactRecordCount"],
        instance["records"],
        "record length",
    )

    records = instance["records"]
    record_keys = [record_order_key(record) for record in records]
    if record_keys != sorted(record_keys):
        errors.append(
            "$.records: records must be sorted by packagePath, "
            "packageArtifactPath, sourceRecordKind, destinationPath, stagedPath"
        )

    identities = [record_identity(record) for record in records]
    identity_counts = Counter(identities)
    duplicate_identities = [
        identity for identity, count in identity_counts.items() if count > 1
    ]
    if duplicate_identities:
        errors.append(
            f"$.records: duplicate artifact identity {duplicate_identities[0]!r}"
        )

    source_counts = Counter(record["sourceRecordKind"] for record in records)
    for source_kind, count_field in SOURCE_COUNT_FIELD.items():
        add_equal_error(
            errors,
            f"$.{count_field}",
            instance[count_field],
            source_counts[source_kind],
            f"{source_kind} record length",
        )
        source_field = SOURCE_INPUT_FIELD[source_kind]
        if instance[source_field] is not None and source_counts[source_kind] == 0:
            errors.append(
                f"$.{count_field}: non-null $.{source_field} requires "
                f"at least one {source_kind} record"
            )

    staged_count = sum(1 for record in records if record["stagedPath"] is not None)
    total_bytes = sum(
        record["sizeBytes"] for record in records if record["sizeBytes"] is not None
    )
    add_equal_error(
        errors,
        "$.stagedArtifactRecordCount",
        instance["stagedArtifactRecordCount"],
        staged_count,
        "staged record length",
    )
    add_equal_error(
        errors,
        "$.totalArtifactRecordBytes",
        instance["totalArtifactRecordBytes"],
        total_bytes,
        "artifact byte sum",
    )
    validate_cross_source_record_consistency(errors, records)
    validate_native_descriptor_provenance_window(errors, records)

    expected_success = instance["diagnosticCounts"]["error"] == 0
    add_equal_error(
        errors,
        "$.success",
        instance["success"],
        expected_success,
        "no-error report status",
    )

    for index, record in enumerate(records):
        validate_record(errors, f"$.records[{index}]", record, instance)

    for index, diagnostic in enumerate(diagnostics):
        diagnostic_path = f"$.diagnostics[{index}]"
        if not diagnostic["code"].startswith("package.release.report."):
            errors.append(
                f"{diagnostic_path}.code: expected package.release.report. prefix"
            )
        validate_source_location_span(
            errors,
            f"{diagnostic_path}.location",
            diagnostic["location"],
        )

    return errors
