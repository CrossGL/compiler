"""Shared package target contracts used by validation tools."""

import json
import re
from dataclasses import dataclass
from pathlib import Path


NATIVE_BINARY_STATUS_ARTIFACT = "nativeBinaryStatus"
PACKAGE_TARGET_CONTRACTS_PATH = Path(__file__).resolve().with_suffix(".json")
PACKAGE_TARGET_CONTRACTS_LABEL_ROOT = PACKAGE_TARGET_CONTRACTS_PATH.parents[1]
CONTRACT_DOCUMENT_KEYS = frozenset(
    {
        "schemaVersion",
        "debugArtifacts",
        "targets",
    }
)
TARGET_CONTRACT_KEYS = frozenset(
    {
        "target",
        "requiredPathArtifacts",
        "requiresNativeBinaryStatus",
        "allowsPlannedNativeBinary",
        "allowsPlannedNativeSourceEvidence",
    }
)
PACKAGE_PATH_ARTIFACTS = frozenset(
    {
        "backendSource",
        "backendAssembly",
        "intermediate",
        "nativeBinary",
    }
)
TARGET_NAME_PATTERN = re.compile(r"^[a-z][a-z0-9-]*$")


@dataclass(frozen=True)
class PackageTargetContract:
    target: str
    required_path_artifacts: tuple[str, ...]
    requires_native_binary_status: bool
    allows_planned_native_binary: bool
    allows_planned_native_source_evidence: bool

    @property
    def required_manifest_artifacts(self):
        if self.requires_native_binary_status:
            return self.required_path_artifacts + (NATIVE_BINARY_STATUS_ARTIFACT,)
        return self.required_path_artifacts


def _contract_path_label(contract_path, label_root):
    contract_path = Path(contract_path).resolve()
    if label_root is not None:
        try:
            return contract_path.relative_to(Path(label_root).resolve()).as_posix()
        except ValueError:
            pass
    return contract_path.as_posix()


def _format_keys(keys):
    return ", ".join(repr(key) for key in keys)


def _load_json_without_duplicate_keys(contract_path, label_root):
    label = _contract_path_label(contract_path, label_root)

    def reject_duplicate_keys(pairs):
        document = {}
        for key, value in pairs:
            if key in document:
                raise ValueError(f"{label}: duplicate JSON object key {key!r}")
            document[key] = value
        return document

    try:
        with contract_path.open("r", encoding="utf-8") as handle:
            return json.load(handle, object_pairs_hook=reject_duplicate_keys)
    except json.JSONDecodeError as exc:
        raise ValueError(
            f"{label}: invalid JSON at line {exc.lineno}, column {exc.colno}: {exc.msg}"
        ) from exc


def _expect(condition, message, contract_path, label_root):
    if not condition:
        raise ValueError(
            f"{_contract_path_label(contract_path, label_root)}: {message}"
        )


def _expect_known_keys(value, allowed_keys, path, contract_path, label_root):
    unknown_keys = sorted(set(value) - allowed_keys)
    _expect(
        not unknown_keys,
        f"{path}: unknown keys {_format_keys(unknown_keys)}",
        contract_path,
        label_root,
    )


def _expect_string_list(value, path, contract_path, label_root):
    _expect(
        isinstance(value, list),
        f"{path}: expected list",
        contract_path,
        label_root,
    )
    normalized = []
    for index, item in enumerate(value):
        _expect(
            isinstance(item, str) and item,
            f"{path}[{index}]: expected non-empty string",
            contract_path,
            label_root,
        )
        normalized.append(item)
    _expect(
        len(normalized) == len(set(normalized)),
        f"{path}: duplicate entries",
        contract_path,
        label_root,
    )
    return tuple(normalized)


def load_contract_document(
    contract_path=PACKAGE_TARGET_CONTRACTS_PATH,
    label_root=PACKAGE_TARGET_CONTRACTS_LABEL_ROOT,
):
    contract_path = Path(contract_path).resolve()
    document = _load_json_without_duplicate_keys(contract_path, label_root)

    _expect(
        isinstance(document, dict),
        "$: expected object",
        contract_path,
        label_root,
    )
    _expect_known_keys(
        document,
        CONTRACT_DOCUMENT_KEYS,
        "$",
        contract_path,
        label_root,
    )
    _expect(
        document.get("schemaVersion") == 1,
        "$.schemaVersion: expected 1",
        contract_path,
        label_root,
    )

    debug_artifacts = _expect_string_list(
        document.get("debugArtifacts"),
        "$.debugArtifacts",
        contract_path,
        label_root,
    )
    _expect(
        debug_artifacts == ("debugMetadata", "hirSourceMap"),
        "$.debugArtifacts: expected debugMetadata and hirSourceMap pair",
        contract_path,
        label_root,
    )

    targets = document.get("targets")
    _expect(
        isinstance(targets, list) and targets,
        "$.targets: expected non-empty list",
        contract_path,
        label_root,
    )

    seen_targets = set()
    seen_source_package_target = False
    contracts = []
    for index, entry in enumerate(targets):
        path = f"$.targets[{index}]"
        _expect(
            isinstance(entry, dict),
            f"{path}: expected object",
            contract_path,
            label_root,
        )
        _expect_known_keys(
            entry,
            TARGET_CONTRACT_KEYS,
            path,
            contract_path,
            label_root,
        )

        target = entry.get("target")
        _expect(
            isinstance(target, str) and target,
            f"{path}.target: expected non-empty string",
            contract_path,
            label_root,
        )
        _expect(
            TARGET_NAME_PATTERN.match(target) is not None,
            f"{path}.target: expected lower-case package target id",
            contract_path,
            label_root,
        )
        _expect(
            target not in seen_targets,
            f"{path}.target: duplicate target {target!r}",
            contract_path,
            label_root,
        )
        seen_targets.add(target)

        required_path_artifacts = _expect_string_list(
            entry.get("requiredPathArtifacts"),
            f"{path}.requiredPathArtifacts",
            contract_path,
            label_root,
        )
        for artifact in required_path_artifacts:
            _expect(
                artifact in PACKAGE_PATH_ARTIFACTS,
                f"{path}.requiredPathArtifacts: unknown path artifact {artifact!r}",
                contract_path,
                label_root,
            )
        _expect(
            NATIVE_BINARY_STATUS_ARTIFACT not in required_path_artifacts,
            f"{path}.requiredPathArtifacts: "
            f"{NATIVE_BINARY_STATUS_ARTIFACT} is not a path artifact",
            contract_path,
            label_root,
        )
        _expect(
            "nativeBinary" in required_path_artifacts,
            f"{path}.requiredPathArtifacts: expected nativeBinary",
            contract_path,
            label_root,
        )

        requires_native_binary_status = entry.get("requiresNativeBinaryStatus")
        _expect(
            isinstance(requires_native_binary_status, bool),
            f"{path}.requiresNativeBinaryStatus: expected boolean",
            contract_path,
            label_root,
        )
        allows_planned_native_binary = entry.get("allowsPlannedNativeBinary")
        _expect(
            isinstance(allows_planned_native_binary, bool),
            f"{path}.allowsPlannedNativeBinary: expected boolean",
            contract_path,
            label_root,
        )
        allows_planned_native_source_evidence = entry.get(
            "allowsPlannedNativeSourceEvidence"
        )
        _expect(
            isinstance(allows_planned_native_source_evidence, bool),
            f"{path}.allowsPlannedNativeSourceEvidence: expected boolean",
            contract_path,
            label_root,
        )
        _expect(
            requires_native_binary_status
            == allows_planned_native_binary
            == allows_planned_native_source_evidence,
            f"{path}: requiresNativeBinaryStatus, allowsPlannedNativeBinary, "
            "and allowsPlannedNativeSourceEvidence must match for v0 package "
            "contracts",
            contract_path,
            label_root,
        )
        is_source_package_target = (
            requires_native_binary_status and allows_planned_native_binary
        )
        _expect(
            is_source_package_target or not seen_source_package_target,
            f"{path}: native package target {target!r} must be listed before "
            "source-package targets",
            contract_path,
            label_root,
        )
        seen_source_package_target = (
            seen_source_package_target or is_source_package_target
        )

        contracts.append(
            PackageTargetContract(
                target=target,
                required_path_artifacts=required_path_artifacts,
                requires_native_binary_status=requires_native_binary_status,
                allows_planned_native_binary=allows_planned_native_binary,
                allows_planned_native_source_evidence=(
                    allows_planned_native_source_evidence
                ),
            )
        )

    return tuple(contracts), debug_artifacts


_DEFAULT_CONSTANTS = None
_DEFAULT_CONSTANT_NAMES = (
    "PACKAGE_TARGET_CONTRACTS",
    "PACKAGE_DEBUG_ARTIFACTS",
    "TARGET_REQUIRED_PATH_ARTIFACTS",
    "TARGET_REQUIRED_ARTIFACTS",
    "PACKAGE_TARGET_MIN_ARTIFACT_COUNTS",
    "SOURCE_PACKAGE_TARGETS",
    "PACKAGE_TARGETS_REQUIRING_NATIVE_STATUS",
    "PACKAGE_DEBUG_ARTIFACT_COUNT",
)


def _build_default_constants():
    contracts, debug_artifacts = load_contract_document()
    target_required_path_artifacts = {
        contract.target: contract.required_path_artifacts for contract in contracts
    }
    target_required_artifacts = {
        contract.target: contract.required_manifest_artifacts for contract in contracts
    }
    package_target_min_artifact_counts = {
        contract.target: len(contract.required_path_artifacts) for contract in contracts
    }
    source_package_targets = frozenset(
        contract.target
        for contract in contracts
        if contract.allows_planned_native_binary
    )
    package_targets_requiring_native_status = frozenset(
        contract.target
        for contract in contracts
        if contract.requires_native_binary_status
    )
    return {
        "PACKAGE_TARGET_CONTRACTS": contracts,
        "PACKAGE_DEBUG_ARTIFACTS": debug_artifacts,
        "TARGET_REQUIRED_PATH_ARTIFACTS": target_required_path_artifacts,
        "TARGET_REQUIRED_ARTIFACTS": target_required_artifacts,
        "PACKAGE_TARGET_MIN_ARTIFACT_COUNTS": package_target_min_artifact_counts,
        "SOURCE_PACKAGE_TARGETS": source_package_targets,
        "PACKAGE_TARGETS_REQUIRING_NATIVE_STATUS": (
            package_targets_requiring_native_status
        ),
        "PACKAGE_DEBUG_ARTIFACT_COUNT": len(debug_artifacts),
    }


def _default_constants():
    global _DEFAULT_CONSTANTS
    if _DEFAULT_CONSTANTS is None:
        _DEFAULT_CONSTANTS = _build_default_constants()
        globals().update(_DEFAULT_CONSTANTS)
    return _DEFAULT_CONSTANTS


def __getattr__(name):
    if name in _DEFAULT_CONSTANT_NAMES:
        return _default_constants()[name]
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = (
    "NATIVE_BINARY_STATUS_ARTIFACT",
    "PACKAGE_TARGET_CONTRACTS_PATH",
    "PackageTargetContract",
    "load_contract_document",
    *_DEFAULT_CONSTANT_NAMES,
)
