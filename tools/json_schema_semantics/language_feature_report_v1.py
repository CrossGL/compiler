"""Semantic checks for language-feature-report-v1.schema.json."""

from collections import Counter
import hashlib
import json
from pathlib import Path

from .common import add_equal_error, validate_source_location_span


SCHEMA_VERSION = 1
REPORT_KIND = "crossgl.languageFeatureReport"

SNAPSHOT_ID = "crosstl-frontend-language-spec-v0"
SNAPSHOT_PATH = "docs/language/crosstl-frontend-language-spec-v0.json"

COMPATIBILITY_BUCKETS = (
    "cross-tl-inventory-only",
    "accepted-source",
    "package-supported",
    "compatibility-only",
    "spec.unsupported-for-native-v0",
    "spec.deprecated",
    "spec.error",
    "target.unsupported",
)

FEATURE_GROUPS = ("resources", "memory", "layout")
FACT_GROUPS = ("unsupported", "deprecated", "error")
EVIDENCE_POINTER_FIELDS = (
    "path",
    "anchor",
    "ctestName",
    "fixture",
    "diagnosticCode",
    "schemaPath",
)

REPORT_PACKAGE_MODE_BY_CONTRACT_MODE = {
    "native": "native",
    "source-package": "source",
    "unsupported": "unavailable",
}

LIMITATION_GATE_STATUSES = {"planned-failure", "unavailable", "unsupported"}

SNAPSHOT_FEATURE_FACETS = {
    "resources": (
        (
            "resource.storage-image-types",
            ("language", "resources", "storageImageTypeNames"),
        ),
        ("resource.buffer-types", ("language", "resources", "resourceBufferTypeNames")),
        (
            "resource.uav-buffer-types",
            ("language", "resources", "uavResourceBufferTypeNames"),
        ),
        (
            "resource.sampler-state-types",
            ("language", "resources", "samplerStateTypeNames"),
        ),
        (
            "resource.access-metadata",
            ("language", "resources", "resourceAccessMetadata"),
        ),
        (
            "resource.descriptor-index-metadata",
            ("language", "resources", "descriptorIndexMetadata"),
        ),
        (
            "resource.image-format-metadata",
            ("language", "resources", "imageFormatMetadataNames"),
        ),
    ),
    "memory": (
        ("memory.address-spaces", ("language", "resources", "addressSpaceMetadata")),
        ("memory.layout-metadata", ("language", "resources", "memoryLayoutMetadata")),
    ),
    "layout": (
        (
            "layout.builtin-semantics",
            ("language", "resources", "builtinSemanticMetadata"),
        ),
        (
            "layout.metadata-single-values",
            ("validation", "metadata", "singleValueNames"),
        ),
        ("layout.metadata-aliases", ("validation", "metadata", "singleValueAliases")),
        ("layout.metadata-multi-values", ("validation", "metadata", "multiValueNames")),
        (
            "layout.interpolation-metadata",
            ("validation", "metadata", "interpolationModes"),
        ),
        (
            "layout.stage-layout-entries",
            ("validation", "stageLayout", "directionRequirements"),
        ),
    ),
}


def repo_root():
    return Path(__file__).resolve().parents[2]


def normalize_text(text):
    return text.replace("\r\n", "\n").replace("\r", "\n")


def is_windows_drive_path(path):
    return len(path) >= 2 and path[0].isalpha() and path[1] == ":"


def is_normalized_repo_relative_posix_path(path):
    if not isinstance(path, str) or path == "":
        return False
    if "\\" in path or path.startswith("/") or is_windows_drive_path(path):
        return False
    return not any(part in {"", ".", ".."} for part in path.split("/"))


def read_text(path):
    return normalize_text(path.read_text(encoding="utf-8"))


def sha256_text(text):
    return hashlib.sha256(normalize_text(text).encode("utf-8")).hexdigest()


def committed_snapshot_seal():
    snapshot_path = repo_root() / SNAPSHOT_PATH
    snapshot_text = read_text(snapshot_path)
    snapshot = json.loads(snapshot_text)
    return {
        "snapshotId": SNAPSHOT_ID,
        "snapshotPath": SNAPSHOT_PATH,
        "snapshotSha256": sha256_text(snapshot_text),
        "snapshotSchemaVersion": snapshot["schemaVersion"],
    }


def committed_snapshot():
    return json.loads(read_text(repo_root() / SNAPSHOT_PATH))


def snapshot_pointer_value(snapshot, path):
    value = snapshot
    for part in path:
        if not isinstance(value, dict) or part not in value:
            return None
        value = value[part]
    return value


def has_snapshot_content(value):
    return isinstance(value, (dict, list, str)) and bool(value)


def validate_exact_header(errors, instance):
    if instance["schemaVersion"] != SCHEMA_VERSION:
        errors.append(
            "$.schemaVersion: expected language feature report schemaVersion "
            f"{SCHEMA_VERSION}, got {instance['schemaVersion']!r}"
        )
    if instance["kind"] != REPORT_KIND:
        errors.append(
            f"$.kind: expected language feature report kind {REPORT_KIND!r}, "
            f"got {instance['kind']!r}"
        )


def validate_snapshot_seal(errors, instance):
    expected = committed_snapshot_seal()
    labels = {
        "snapshotId": "id",
        "snapshotPath": "path",
        "snapshotSha256": "SHA-256",
        "snapshotSchemaVersion": "schemaVersion",
    }
    actual = instance["crossTLSnapshotSeal"]
    for field, expected_value in expected.items():
        if actual[field] != expected_value:
            errors.append(
                f"$.crossTLSnapshotSeal.{field}: expected committed CrossTL "
                f"snapshot {labels[field]} {expected_value!r}, "
                f"got {actual[field]!r}"
            )


def validate_module_source_hash(errors, instance):
    module = instance["module"]
    source_path = module["sourcePath"]
    if not is_normalized_repo_relative_posix_path(source_path):
        return

    absolute_source_path = repo_root() / source_path
    if not absolute_source_path.exists():
        return

    expected = sha256_text(read_text(absolute_source_path))
    actual = module["sourceSha256"]
    if actual != expected:
        errors.append(
            "$.module.sourceSha256: expected normalized UTF-8 source SHA-256 "
            f"{expected!r}, got {actual!r}"
        )


def validate_module_source_path(errors, instance):
    source_path = instance["module"]["sourcePath"]
    if is_normalized_repo_relative_posix_path(source_path):
        return
    errors.append(
        "$.module.sourcePath: expected normalized repo-relative POSIX path "
        "(no backslashes, absolute paths, empty segments, '.', or '..'), "
        f"got {source_path!r}"
    )


def expected_bucket_counts(instance):
    counts = Counter({bucket: 0 for bucket in COMPATIBILITY_BUCKETS})
    features = instance["resourceMemoryLayoutFeatures"]
    for group in FEATURE_GROUPS:
        for feature in features[group]:
            counts[feature["status"]] += 1
    facts = instance["facts"]
    for group in FACT_GROUPS:
        for fact in facts[group]:
            counts[fact["classification"]] += 1
    return counts


def validate_bucket_counts(errors, instance):
    expected = expected_bucket_counts(instance)
    summary = instance["compatibilityBucketSummary"]
    for bucket in COMPATIBILITY_BUCKETS:
        add_equal_error(
            errors,
            f"$.compatibilityBucketSummary.{bucket}",
            summary[bucket],
            expected[bucket],
            "bucket count",
        )


def validate_snapshot_feature_coverage(errors, instance):
    snapshot = committed_snapshot()
    if instance["crossTLSnapshotSeal"] != committed_snapshot_seal():
        return
    features = instance["resourceMemoryLayoutFeatures"]
    for group, facets in SNAPSHOT_FEATURE_FACETS.items():
        reported = {
            feature["featureId"]
            for feature in features[group]
            if isinstance(feature.get("featureId"), str)
        }
        for feature_id, pointer in facets:
            if not has_snapshot_content(snapshot_pointer_value(snapshot, pointer)):
                continue
            if feature_id not in reported:
                errors.append(
                    f"$.resourceMemoryLayoutFeatures.{group}: missing CrossTL "
                    f"snapshot-backed feature {feature_id!r} from "
                    f"/{'/'.join(pointer)}"
                )


def collect_evidence_ids(errors, evidence):
    ids = set()
    for index, record in enumerate(evidence):
        path = f"$.evidence[{index}]"
        evidence_id = record["id"]
        if evidence_id in ids:
            errors.append(f"$.evidence: duplicate evidence id {evidence_id!r}")
        ids.add(evidence_id)

        namespace = evidence_id.split(":", 1)[0]
        if record["kind"] != namespace:
            errors.append(f"{path}.kind: expected id namespace {namespace!r}")
        if not any(field in record for field in EVIDENCE_POINTER_FIELDS):
            errors.append(f"{path}: expected at least one local evidence pointer")
    return ids


def validate_evidence_id_list(errors, path, evidence_ids, defined_ids):
    for index, evidence_id in enumerate(evidence_ids):
        if evidence_id not in defined_ids:
            errors.append(
                f"{path}.evidenceIds[{index}]: expected id to appear in "
                f"$.evidence, got {evidence_id!r}"
            )


def validate_evidence_references(errors, instance):
    defined_ids = collect_evidence_ids(errors, instance["evidence"])

    for index, gate in enumerate(instance["targetFeatureGates"]):
        validate_evidence_id_list(
            errors,
            f"$.targetFeatureGates[{index}]",
            gate["evidenceIds"],
            defined_ids,
        )

    features = instance["resourceMemoryLayoutFeatures"]
    for group in FEATURE_GROUPS:
        for index, feature in enumerate(features[group]):
            feature_path = f"$.resourceMemoryLayoutFeatures.{group}[{index}]"
            validate_evidence_id_list(
                errors,
                feature_path,
                feature["evidenceIds"],
                defined_ids,
            )
            for location_index, location in enumerate(feature["sourceLocations"]):
                validate_source_location_span(
                    errors,
                    f"{feature_path}.sourceLocations[{location_index}]",
                    location,
                )

    facts = instance["facts"]
    for group in FACT_GROUPS:
        for index, fact in enumerate(facts[group]):
            validate_evidence_id_list(
                errors,
                f"$.facts.{group}[{index}]",
                fact["evidenceIds"],
                defined_ids,
            )


def validate_target_feature_gate_identities(errors, instance):
    seen = {}
    for index, gate in enumerate(instance["targetFeatureGates"]):
        identity = (gate["target"], gate["packageMode"], gate["gateId"])
        if identity in seen:
            target, package_mode, gate_id = identity
            errors.append(
                f"$.targetFeatureGates[{index}]: duplicate target feature "
                f"gate identity target={target!r}, packageMode={package_mode!r}, "
                f"gateId={gate_id!r}; first seen at "
                f"$.targetFeatureGates[{seen[identity]}]"
            )
            continue
        seen[identity] = index


def validate_single_target_contract_evidence(
    errors, path, gate, purpose, suffix_prefix
):
    target = gate["target"]
    prefix = f"target-contract:{target}.{suffix_prefix}"
    matches = [
        evidence_id
        for evidence_id in gate["evidenceIds"]
        if isinstance(evidence_id, str) and evidence_id.startswith(prefix)
    ]
    if not matches:
        errors.append(
            f"{path}.evidenceIds: expected legalization {purpose} evidence id "
            f"with prefix {prefix!r}"
        )
        return None
    if len(matches) != 1:
        errors.append(
            f"{path}.evidenceIds: expected exactly one legalization {purpose} "
            f"evidence id with prefix {prefix!r}, got {matches!r}"
        )
        return None
    return matches[0][len(prefix) :]


def validate_target_feature_gate_legalization_evidence(errors, instance):
    for index, gate in enumerate(instance["targetFeatureGates"]):
        path = f"$.targetFeatureGates[{index}]"
        target = gate["target"]
        package_mode = validate_single_target_contract_evidence(
            errors, path, gate, "package mode", "package-mode."
        )
        expected_package_mode = REPORT_PACKAGE_MODE_BY_CONTRACT_MODE.get(package_mode)
        if package_mode is not None and expected_package_mode is None:
            errors.append(
                f"{path}.evidenceIds: unsupported legalization package mode "
                f"evidence suffix {package_mode!r}"
            )
        if (
            expected_package_mode is not None
            and gate["packageMode"] != expected_package_mode
        ):
            errors.append(
                f"{path}.packageMode: expected legalization package mode "
                f"{expected_package_mode!r} from target contract evidence, "
                f"got {gate['packageMode']!r}"
            )

        support_status = validate_single_target_contract_evidence(
            errors, path, gate, "support status", "support."
        )
        if (
            support_status is not None
            and gate["status"] in LIMITATION_GATE_STATUSES
            and support_status != "unsupported"
        ):
            errors.append(
                f"{path}.evidenceIds: expected unsupported target support "
                f"status evidence for gate status {gate['status']!r}, "
                f"got {support_status!r}"
            )

        if gate["status"] in {"planned-failure", "unavailable", "unsupported"}:
            if not gate["requiredCapabilities"]:
                errors.append(
                    f"{path}.requiredCapabilities: expected at least one "
                    "legalization required or missing capability for "
                    f"status {gate['status']!r}"
                )

        target_contract_evidence = f"target-contract:{target}.package-support"
        if target_contract_evidence not in gate["evidenceIds"]:
            errors.append(
                f"{path}.evidenceIds: expected legalization evidence id "
                f"{target_contract_evidence!r}"
            )


def validate_semantics(instance):
    errors = []
    validate_exact_header(errors, instance)
    validate_snapshot_seal(errors, instance)
    validate_module_source_path(errors, instance)
    validate_module_source_hash(errors, instance)
    validate_bucket_counts(errors, instance)
    validate_snapshot_feature_coverage(errors, instance)
    validate_target_feature_gate_identities(errors, instance)
    validate_target_feature_gate_legalization_evidence(errors, instance)
    validate_evidence_references(errors, instance)
    return errors
