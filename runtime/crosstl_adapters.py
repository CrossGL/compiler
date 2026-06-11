"""Read-only CrossTL runtime adapter descriptor package checks."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import re
from typing import Any


CROSSTL_RUNTIME_ADAPTER_PACKAGE_KIND = "crosstl-runtime-adapter-package"
CROSSTL_RUNTIME_ADAPTER_DESCRIPTOR_KIND = "crosstl-runtime-adapter-descriptor"
CROSSTL_RUNTIME_ADAPTER_PLAN_KIND = "crosstl-runtime-adapter-plan"
CROSSTL_RUNTIME_ADAPTER_PLAN_SCOPE = "runtime-adapter-integration-planning"
CROSSTL_RUNTIME_ADAPTER_PACKAGE_SCOPE = "runtime-adapter-descriptor-package"
SUPPORTED_COMPILER_TARGETS = frozenset({"directx", "metal", "opengl", "vulkan"})
LOWERCASE_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
BACKEND_SOURCE_ARTIFACT_FORMATS = frozenset(
    {
        "backend-source",
        "glsl source",
        "glsl-source",
        "hlsl source",
        "hlsl-source",
        "metal source",
        "msl source",
        "msl-source",
        "spir-v source",
        "spirv source",
        "vulkan-targeted shader source",
        "wgsl source",
        "wgsl-source",
    }
)
NATIVE_BINARY_ARTIFACT_FORMATS = frozenset(
    {
        "dxbc",
        "dxil",
        "dxil binary",
        "metallib",
        "metallib binary",
        "native-binary",
        "spir-v",
        "spir-v binary",
        "spir-v module",
        "spirv",
        "spirv binary",
        "spirv module",
    }
)


@dataclass(frozen=True)
class CrossTLAdapterDiagnostic:
    severity: str
    code: str
    message: str
    path: str


@dataclass(frozen=True)
class CrossTLAdapterDescriptor:
    id: str | None
    target: str | None
    adapter_kind: str | None
    artifact_format: str | None
    package_path: str | None
    descriptor_path: str
    host_interface_status: str | None
    required_tools: tuple[str, ...]
    document: dict[str, Any] | None


@dataclass(frozen=True)
class CrossTLAdapterPackageReport:
    manifest_path: Path
    package_kind: str | None
    source_package: str | None
    adapter_manifest: str | None
    valid: bool
    compiler_supported: bool
    descriptor_count: int
    supported_targets: tuple[str, ...]
    unsupported_targets: tuple[str, ...]
    descriptors: tuple[CrossTLAdapterDescriptor, ...]
    diagnostics: tuple[CrossTLAdapterDiagnostic, ...]


@dataclass(frozen=True)
class CrossTLRuntimeAdapterCandidate:
    id: str
    target: str
    artifact_name: str
    adapter_kind: str
    artifact_format: str
    package_path: str
    descriptor_path: str
    producer_adapter_kind: str
    producer_artifact_format: str
    host_interface_status: str | None
    load_ready: bool
    required_tools: tuple[str, ...]
    host_responsibilities: tuple[str, ...]
    source_remap: dict[str, Any] | None


def read_crosstl_runtime_adapter_package(
    manifest_path: str | Path,
) -> CrossTLAdapterPackageReport:
    """Read a CrossTL ``runtime-adapters.json`` descriptor package manifest."""

    path = Path(manifest_path)
    diagnostics: list[CrossTLAdapterDiagnostic] = []
    document = _read_json_object(path, "$", diagnostics)
    if document is None:
        return _empty_report(path, diagnostics)

    _validate_package_header(document, diagnostics)
    descriptors = _read_descriptors(path.parent, document, diagnostics)
    supported_targets = sorted(
        {
            descriptor.target
            for descriptor in descriptors
            if descriptor.target in SUPPORTED_COMPILER_TARGETS
        }
    )
    unsupported_targets = sorted(
        {
            descriptor.target
            for descriptor in descriptors
            if descriptor.target and descriptor.target not in SUPPORTED_COMPILER_TARGETS
        }
    )
    for target in unsupported_targets:
        diagnostics.append(
            CrossTLAdapterDiagnostic(
                severity="warning",
                code="crosstl.adapter.unsupported_target",
                message=(
                    f"CrossTL runtime adapter target {target!r} is outside the "
                    "compiler runtime target set"
                ),
                path="$.descriptors[].target",
            )
        )

    errors = [
        diagnostic for diagnostic in diagnostics if diagnostic.severity == "error"
    ]
    return CrossTLAdapterPackageReport(
        manifest_path=path,
        package_kind=_optional_str(document.get("kind")),
        source_package=_optional_str(document.get("sourcePackage")),
        adapter_manifest=_optional_str(document.get("adapterManifest")),
        valid=not errors and document.get("success") is True,
        compiler_supported=not errors and not unsupported_targets,
        descriptor_count=len(descriptors),
        supported_targets=tuple(supported_targets),
        unsupported_targets=tuple(unsupported_targets),
        descriptors=tuple(descriptors),
        diagnostics=tuple(diagnostics),
    )


def normalize_crosstl_runtime_adapter_candidates(
    report: CrossTLAdapterPackageReport,
) -> tuple[CrossTLRuntimeAdapterCandidate, ...]:
    """Return compiler runtime-loader candidates for supported CrossTL adapters."""

    if not report.valid:
        return ()

    candidates = []
    for descriptor in report.descriptors:
        if (
            descriptor.target not in SUPPORTED_COMPILER_TARGETS
            or descriptor.package_path is None
            or descriptor.adapter_kind is None
            or descriptor.artifact_format is None
            or descriptor.document is None
        ):
            continue

        compiler_artifact_format = _compiler_artifact_format(descriptor.artifact_format)
        if compiler_artifact_format is None:
            continue
        candidates.append(
            CrossTLRuntimeAdapterCandidate(
                id=_runtime_loader_candidate_id(descriptor),
                target=descriptor.target,
                artifact_name=(
                    "nativeBinary"
                    if compiler_artifact_format == "native-binary"
                    else "backendSource"
                ),
                adapter_kind=(
                    "native-binary-loader"
                    if compiler_artifact_format == "native-binary"
                    else "backend-source-loader"
                ),
                artifact_format=compiler_artifact_format,
                package_path=descriptor.package_path,
                descriptor_path=descriptor.descriptor_path,
                producer_adapter_kind=descriptor.adapter_kind,
                producer_artifact_format=descriptor.artifact_format,
                host_interface_status=descriptor.host_interface_status,
                load_ready=descriptor.host_interface_status == "ready",
                required_tools=descriptor.required_tools,
                host_responsibilities=tuple(
                    _string_list(descriptor.document.get("hostResponsibilities"))
                ),
                source_remap=_optional_object(descriptor.document.get("sourceRemap")),
            )
        )
    return tuple(candidates)


def _empty_report(
    path: Path, diagnostics: list[CrossTLAdapterDiagnostic]
) -> CrossTLAdapterPackageReport:
    return CrossTLAdapterPackageReport(
        manifest_path=path,
        package_kind=None,
        source_package=None,
        adapter_manifest=None,
        valid=False,
        compiler_supported=False,
        descriptor_count=0,
        supported_targets=(),
        unsupported_targets=(),
        descriptors=(),
        diagnostics=tuple(diagnostics),
    )


def _read_json_object(
    path: Path,
    json_path: str,
    diagnostics: list[CrossTLAdapterDiagnostic],
) -> dict[str, Any] | None:
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        diagnostics.append(
            CrossTLAdapterDiagnostic(
                severity="error",
                code="crosstl.adapter.unreadable_json",
                message=f"failed to read JSON object: {exc}",
                path=json_path,
            )
        )
        return None
    if not isinstance(document, dict):
        diagnostics.append(
            CrossTLAdapterDiagnostic(
                severity="error",
                code="crosstl.adapter.expected_object",
                message="expected JSON object",
                path=json_path,
            )
        )
        return None
    return document


def _validate_package_header(
    document: dict[str, Any],
    diagnostics: list[CrossTLAdapterDiagnostic],
) -> None:
    _expect_equal(
        diagnostics,
        "$.schemaVersion",
        document.get("schemaVersion"),
        1,
        "crosstl.adapter.invalid_schema_version",
    )
    _expect_equal(
        diagnostics,
        "$.kind",
        document.get("kind"),
        CROSSTL_RUNTIME_ADAPTER_PACKAGE_KIND,
        "crosstl.adapter.invalid_kind",
    )
    _expect_equal(
        diagnostics,
        "$.scope",
        document.get("scope"),
        CROSSTL_RUNTIME_ADAPTER_PACKAGE_SCOPE,
        "crosstl.adapter.invalid_scope",
    )
    _expect_equal(
        diagnostics,
        "$.adapterManifest",
        document.get("adapterManifest"),
        "runtime-adapters.json",
        "crosstl.adapter.invalid_manifest_name",
    )
    adapter_plan = document.get("adapterPlan")
    if isinstance(adapter_plan, dict):
        _expect_equal(
            diagnostics,
            "$.adapterPlan.kind",
            adapter_plan.get("kind"),
            CROSSTL_RUNTIME_ADAPTER_PLAN_KIND,
            "crosstl.adapter.invalid_plan_kind",
        )
    else:
        diagnostics.append(
            CrossTLAdapterDiagnostic(
                severity="error",
                code="crosstl.adapter.missing_plan",
                message="expected adapterPlan object",
                path="$.adapterPlan",
            )
        )


def _read_descriptors(
    root: Path,
    document: dict[str, Any],
    diagnostics: list[CrossTLAdapterDiagnostic],
) -> list[CrossTLAdapterDescriptor]:
    records = document.get("descriptors")
    if not isinstance(records, list):
        diagnostics.append(
            CrossTLAdapterDiagnostic(
                severity="error",
                code="crosstl.adapter.invalid_descriptor_records",
                message="expected descriptors array",
                path="$.descriptors",
            )
        )
        return []

    descriptors: list[CrossTLAdapterDescriptor] = []
    seen_paths: set[str] = set()
    for index, record in enumerate(records):
        record_path = f"$.descriptors[{index}]"
        if not isinstance(record, dict):
            diagnostics.append(
                CrossTLAdapterDiagnostic(
                    severity="error",
                    code="crosstl.adapter.invalid_descriptor_record",
                    message="expected descriptor record object",
                    path=record_path,
                )
            )
            continue

        descriptor_path = _optional_str(record.get("descriptorPath"))
        if descriptor_path is None:
            diagnostics.append(
                CrossTLAdapterDiagnostic(
                    severity="error",
                    code="crosstl.adapter.missing_descriptor_path",
                    message="expected descriptorPath string",
                    path=f"{record_path}.descriptorPath",
                )
            )
            continue
        descriptor_path_valid = _validate_descriptor_path(
            descriptor_path, f"{record_path}.descriptorPath", seen_paths, diagnostics
        )
        descriptor_file = root / descriptor_path
        descriptor_document = None
        if descriptor_path_valid:
            descriptor_document = _read_json_object(
                descriptor_file,
                f"{record_path}.descriptorPath",
                diagnostics,
            )
        if descriptor_document is not None:
            _validate_descriptor_document(
                descriptor_document,
                record,
                record_path,
                diagnostics,
            )
            _validate_descriptor_file_identity(
                descriptor_file,
                record,
                record_path,
                diagnostics,
            )

        descriptors.append(
            CrossTLAdapterDescriptor(
                id=_optional_str(record.get("id")),
                target=_optional_str(record.get("target")),
                adapter_kind=_optional_str(record.get("adapterKind")),
                artifact_format=_optional_str(record.get("artifactFormat")),
                package_path=_optional_str(record.get("packagePath")),
                descriptor_path=descriptor_path,
                host_interface_status=_optional_str(record.get("hostInterfaceStatus")),
                required_tools=tuple(_string_list(record.get("requiredTools"))),
                document=descriptor_document,
            )
        )

    _validate_package_summary(document, descriptors, diagnostics)
    _validate_package_targets(document, descriptors, diagnostics)
    return descriptors


def _validate_descriptor_path(
    descriptor_path: str,
    json_path: str,
    seen_paths: set[str],
    diagnostics: list[CrossTLAdapterDiagnostic],
) -> bool:
    valid = True
    if not descriptor_path.endswith(
        ".adapter.json"
    ) or not _is_normalized_relative_path(descriptor_path):
        valid = False
        diagnostics.append(
            CrossTLAdapterDiagnostic(
                severity="error",
                code="crosstl.adapter.invalid_descriptor_path",
                message="expected normalized relative *.adapter.json path",
                path=json_path,
            )
        )
    if descriptor_path in seen_paths:
        valid = False
        diagnostics.append(
            CrossTLAdapterDiagnostic(
                severity="error",
                code="crosstl.adapter.duplicate_descriptor_path",
                message=f"duplicate descriptor path {descriptor_path!r}",
                path=json_path,
            )
        )
    seen_paths.add(descriptor_path)
    return valid


def _validate_descriptor_document(
    document: dict[str, Any],
    record: dict[str, Any],
    record_path: str,
    diagnostics: list[CrossTLAdapterDiagnostic],
) -> None:
    _expect_equal(
        diagnostics,
        f"{record_path}.descriptor.schemaVersion",
        document.get("schemaVersion"),
        1,
        "crosstl.adapter.invalid_descriptor_schema_version",
    )
    _expect_equal(
        diagnostics,
        f"{record_path}.descriptor.kind",
        document.get("kind"),
        CROSSTL_RUNTIME_ADAPTER_DESCRIPTOR_KIND,
        "crosstl.adapter.invalid_descriptor_kind",
    )
    adapter_plan = document.get("adapterPlan")
    if isinstance(adapter_plan, dict):
        _expect_equal(
            diagnostics,
            f"{record_path}.descriptor.adapterPlan.kind",
            adapter_plan.get("kind"),
            CROSSTL_RUNTIME_ADAPTER_PLAN_KIND,
            "crosstl.adapter.invalid_descriptor_plan_kind",
        )
        _expect_equal(
            diagnostics,
            f"{record_path}.descriptor.adapterPlan.scope",
            adapter_plan.get("scope"),
            CROSSTL_RUNTIME_ADAPTER_PLAN_SCOPE,
            "crosstl.adapter.invalid_descriptor_plan_scope",
        )
    else:
        diagnostics.append(
            CrossTLAdapterDiagnostic(
                severity="error",
                code="crosstl.adapter.invalid_descriptor_plan",
                message="expected descriptor adapterPlan object",
                path=f"{record_path}.descriptor.adapterPlan",
            )
        )

    for field in ("id", "target", "adapterKind", "artifactFormat", "packagePath"):
        _expect_equal(
            diagnostics,
            f"{record_path}.descriptor.{field}",
            document.get(field),
            record.get(field),
            "crosstl.adapter.descriptor_record_drift",
        )

    adapter_kind = _optional_str(document.get("adapterKind"))
    if adapter_kind is None:
        diagnostics.append(
            CrossTLAdapterDiagnostic(
                severity="error",
                code="crosstl.adapter.missing_adapter_kind",
                message="expected non-empty descriptor adapterKind",
                path=f"{record_path}.descriptor.adapterKind",
            )
        )
    artifact_format = _optional_str(document.get("artifactFormat"))
    if (
        artifact_format is not None
        and _compiler_artifact_format(artifact_format) is None
    ):
        diagnostics.append(
            CrossTLAdapterDiagnostic(
                severity="warning",
                code="crosstl.adapter.unsupported_artifact_format",
                message=(
                    f"CrossTL runtime adapter artifact format {artifact_format!r} "
                    "has no compiler runtime-loader mapping"
                ),
                path=f"{record_path}.descriptor.artifactFormat",
            )
        )
    host_interface = document.get("hostInterface")
    validation = document.get("validation")
    if isinstance(host_interface, dict) and isinstance(validation, dict):
        _validate_host_interface_status(
            host_interface,
            validation,
            f"{record_path}.descriptor",
            diagnostics,
        )


def _validate_descriptor_file_identity(
    path: Path,
    record: dict[str, Any],
    record_path: str,
    diagnostics: list[CrossTLAdapterDiagnostic],
) -> None:
    descriptor_hash = record.get("descriptorHash")
    expected_hash = (
        descriptor_hash.get("value") if isinstance(descriptor_hash, dict) else None
    )
    if (
        not isinstance(descriptor_hash, dict)
        or descriptor_hash.get("algorithm") != "sha256"
        or not isinstance(expected_hash, str)
        or LOWERCASE_SHA256_RE.fullmatch(expected_hash) is None
    ):
        diagnostics.append(
            CrossTLAdapterDiagnostic(
                severity="error",
                code="crosstl.adapter.invalid_descriptor_hash",
                message="expected descriptorHash sha256 lowercase value",
                path=f"{record_path}.descriptorHash",
            )
        )
    else:
        actual_hash = _file_sha256(path)
        _expect_equal(
            diagnostics,
            f"{record_path}.descriptorHash.value",
            expected_hash,
            actual_hash,
            "crosstl.adapter.descriptor_hash_drift",
        )

    size_bytes = record.get("descriptorSizeBytes")
    if not isinstance(size_bytes, int) or size_bytes < 0:
        diagnostics.append(
            CrossTLAdapterDiagnostic(
                severity="error",
                code="crosstl.adapter.invalid_descriptor_size",
                message="expected non-negative descriptorSizeBytes",
                path=f"{record_path}.descriptorSizeBytes",
            )
        )
    else:
        _expect_equal(
            diagnostics,
            f"{record_path}.descriptorSizeBytes",
            size_bytes,
            path.stat().st_size,
            "crosstl.adapter.descriptor_size_drift",
        )


def _validate_host_interface_status(
    host_interface: dict[str, Any],
    validation: dict[str, Any],
    json_path: str,
    diagnostics: list[CrossTLAdapterDiagnostic],
) -> None:
    status = host_interface.get("status")
    load_ready = validation.get("loadReady")
    if isinstance(status, str) and isinstance(load_ready, bool):
        expected_statuses = ("ready",) if load_ready else ("blocked", "unavailable")
        if status not in expected_statuses:
            diagnostics.append(
                CrossTLAdapterDiagnostic(
                    severity="error",
                    code="crosstl.adapter.host_interface_status_drift",
                    message=(
                        f"expected hostInterface.status in {expected_statuses!r} "
                        f"for validation.loadReady {load_ready!r}"
                    ),
                    path=f"{json_path}.hostInterface.status",
                )
            )


def _validate_package_summary(
    document: dict[str, Any],
    descriptors: list[CrossTLAdapterDescriptor],
    diagnostics: list[CrossTLAdapterDiagnostic],
) -> None:
    summary = document.get("summary")
    if not isinstance(summary, dict):
        diagnostics.append(
            CrossTLAdapterDiagnostic(
                severity="error",
                code="crosstl.adapter.invalid_summary",
                message="expected summary object",
                path="$.summary",
            )
        )
        return

    targets = document.get("targets")
    actions = document.get("actions")
    target_count = len(targets) if isinstance(targets, list) else 0
    action_count = len(actions) if isinstance(actions, list) else 0
    ready_count = sum(
        1 for descriptor in descriptors if descriptor.host_interface_status == "ready"
    )
    _expect_equal(
        diagnostics,
        "$.summary.targetCount",
        summary.get("targetCount"),
        target_count,
        "crosstl.adapter.summary_count_drift",
    )
    _expect_equal(
        diagnostics,
        "$.summary.descriptorCount",
        summary.get("descriptorCount"),
        len(descriptors),
        "crosstl.adapter.summary_count_drift",
    )
    _expect_equal(
        diagnostics,
        "$.summary.readyDescriptorCount",
        summary.get("readyDescriptorCount"),
        ready_count,
        "crosstl.adapter.summary_count_drift",
    )
    _expect_equal(
        diagnostics,
        "$.summary.blockedDescriptorCount",
        summary.get("blockedDescriptorCount"),
        len(descriptors) - ready_count,
        "crosstl.adapter.summary_count_drift",
    )
    _expect_equal(
        diagnostics,
        "$.summary.actionCount",
        summary.get("actionCount"),
        action_count,
        "crosstl.adapter.summary_count_drift",
    )
    adapter_plan = document.get("adapterPlan")
    if isinstance(adapter_plan, dict):
        adapter_count = adapter_plan.get("adapterCount")
        if adapter_count is not None:
            _expect_equal(
                diagnostics,
                "$.adapterPlan.adapterCount",
                adapter_count,
                summary.get("adapterCount"),
                "crosstl.adapter.summary_adapter_count",
            )


def _validate_package_targets(
    document: dict[str, Any],
    descriptors: list[CrossTLAdapterDescriptor],
    diagnostics: list[CrossTLAdapterDiagnostic],
) -> None:
    targets = document.get("targets")
    if not isinstance(targets, list):
        diagnostics.append(
            CrossTLAdapterDiagnostic(
                severity="error",
                code="crosstl.adapter.invalid_targets",
                message="expected targets array",
                path="$.targets",
            )
        )
        return

    for index, target in enumerate(targets):
        target_path = f"$.targets[{index}]"
        if not isinstance(target, dict):
            diagnostics.append(
                CrossTLAdapterDiagnostic(
                    severity="error",
                    code="crosstl.adapter.invalid_target",
                    message="expected target object",
                    path=target_path,
                )
            )
            continue
        target_name = target.get("target")
        matching_descriptors = [
            descriptor for descriptor in descriptors if descriptor.target == target_name
        ]
        ready_count = sum(
            1
            for descriptor in matching_descriptors
            if descriptor.host_interface_status == "ready"
        )
        _expect_equal(
            diagnostics,
            f"{target_path}.descriptorCount",
            target.get("descriptorCount"),
            len(matching_descriptors),
            "crosstl.adapter.target_descriptor_count",
        )
        _expect_equal(
            diagnostics,
            f"{target_path}.readyDescriptorCount",
            target.get("readyDescriptorCount"),
            ready_count,
            "crosstl.adapter.target_ready_count",
        )
        _expect_equal(
            diagnostics,
            f"{target_path}.blockedDescriptorCount",
            target.get("blockedDescriptorCount"),
            len(matching_descriptors) - ready_count,
            "crosstl.adapter.target_blocked_count",
        )
        _expect_equal(
            diagnostics,
            f"{target_path}.descriptors",
            target.get("descriptors"),
            [descriptor.id for descriptor in matching_descriptors],
            "crosstl.adapter.target_descriptor_ids",
        )
        _expect_equal(
            diagnostics,
            f"{target_path}.packagePaths",
            target.get("packagePaths"),
            [
                descriptor.package_path
                for descriptor in matching_descriptors
                if descriptor.package_path
            ],
            "crosstl.adapter.target_package_paths",
        )


def _expect_equal(
    diagnostics: list[CrossTLAdapterDiagnostic],
    path: str,
    actual: Any,
    expected: Any,
    code: str,
) -> None:
    if actual != expected:
        diagnostics.append(
            CrossTLAdapterDiagnostic(
                severity="error",
                code=code,
                message=f"expected {expected!r}, got {actual!r}",
                path=path,
            )
        )


def _optional_str(value: Any) -> str | None:
    return value if isinstance(value, str) and value else None


def _optional_object(value: Any) -> dict[str, Any] | None:
    return dict(value) if isinstance(value, dict) else None


def _string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, str)]


def _is_normalized_relative_path(path: str) -> bool:
    if not path or path.startswith("/") or "\\" in path:
        return False
    if re.match(r"^[A-Za-z]:", path):
        return False
    return all(part not in ("", ".", "..") for part in path.split("/"))


def _compiler_artifact_format(producer_artifact_format: str) -> str | None:
    normalized = _normalize_artifact_format_alias(producer_artifact_format)
    if normalized in BACKEND_SOURCE_ARTIFACT_FORMATS:
        return "backend-source"
    if normalized in NATIVE_BINARY_ARTIFACT_FORMATS:
        return "native-binary"
    return None


def _normalize_artifact_format_alias(value: str) -> str:
    return re.sub(r"\s+", " ", value.strip().lower())


def _runtime_loader_candidate_id(descriptor: CrossTLAdapterDescriptor) -> str:
    target = descriptor.target or "unknown"
    seed = descriptor.id or descriptor.package_path or descriptor.descriptor_path
    return f"runtime-loader.{target}.{_runtime_loader_member_name(seed)}"


def _runtime_loader_member_name(value: str) -> str:
    parts = [part for part in re.split(r"[^A-Za-z0-9]+", value) if part]
    if not parts:
        return "Adapter"
    member = "".join(part[:1].upper() + part[1:] for part in parts)
    if not member[0].isalpha():
        member = f"Adapter{member}"
    return member


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()
