#!/usr/bin/env python3
"""Check deterministic v0 package metadata across focused source/native targets."""

import argparse
import copy
import difflib
import hashlib
import json
import os
import platform
import re
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

from check_package_integrity_fixtures import (
    TARGET_ARTIFACT_PATHS as FIXTURE_TARGET_ARTIFACT_PATHS,
    make_package,
    native_artifact_descriptor as make_native_artifact_descriptor,
    write_json as write_fixture_json,
)
from fixture_parallelism import run_fixture_tasks
from package_target_contracts import (
    PACKAGE_DEBUG_ARTIFACTS,
    TARGET_REQUIRED_PATH_ARTIFACTS,
)


FIXTURE = Path("tests/fixtures/SimpleShader.cgl")
MODULE = "SimpleShader"
PACKAGE_NAME = f"{MODULE}.cglb"
REPORT_SCHEMA_VERSION = 3
PACKAGE_DEBUG_SIDECAR_ARTIFACTS = PACKAGE_DEBUG_ARTIFACTS + ("targetExplanation",)
PACKAGE_TARGET_EXPLANATION_ARTIFACT = "targetExplanation"
HIR_PASS_TRACE_SIDECAR_PATH = "ir/hir-pass-trace.json"
REQUIRED_SOURCE_TARGETS = ("directx", "opengl")
REQUIRED_NATIVE_FIXTURE_TARGETS = ("metal", "vulkan")
DEBUG_VARIANTS = (False, True)
CROSSGL_PACKAGE_REPRODUCIBILITY_JOBS = "CROSSGL_PACKAGE_REPRODUCIBILITY_JOBS"
CROSSGL_CI_JOBS = "CROSSGL_CI_JOBS"
NATIVE_ARTIFACT_DESCRIPTOR = "nativeArtifactDescriptor"
WINDOWS_ABSOLUTE_PATH = re.compile(r"^[A-Za-z]:[\\/]")
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
EXPECTED_ROOT_FILE_PATHS = {
    "manifest": "manifest.json",
    "reflection": "reflection.json",
    "diagnostics": "diagnostics.json",
}
NONDETERMINISTIC_REPORT_KEY_RE = re.compile(
    r"(generated|timestamp|created|updated|date|time)", re.IGNORECASE
)


@dataclass(frozen=True)
class BuildSpec:
    target: str
    debug_ir: bool

    @property
    def label(self):
        mode = "debug" if self.debug_ir else "nodebug"
        return f"{self.target}-{mode}"


def run(command, *, cwd):
    return subprocess.run(
        [str(part) for part in command],
        cwd=cwd,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )


def load_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def canonical_json(value):
    return json.dumps(value, indent=2, sort_keys=True) + "\n"


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(canonical_json(value), encoding="utf-8")


def sha256_file(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def display_local_path(root, path):
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return path.name


def toolchain_summary(root, cglc):
    return dict(
        sorted(
            {
                "cglc": display_local_path(root, cglc),
                "cglcSha256": sha256_file(cglc),
                "platform": platform.platform(),
                "python": platform.python_version(),
            }.items()
        )
    )


def unified_diff(label, left, right):
    return "".join(
        difflib.unified_diff(
            left.splitlines(keepends=True),
            right.splitlines(keepends=True),
            fromfile=f"{label}.first",
            tofile=f"{label}.second",
        )
    )


def normalize_cli_payload(payload, package, root):
    package_text = package.as_posix()
    root_text = root.as_posix()

    def normalize(value):
        if isinstance(value, dict):
            return {key: normalize(child) for key, child in value.items()}
        if isinstance(value, list):
            return [normalize(child) for child in value]
        if isinstance(value, str):
            # CLI package commands report the requested package path. Normalize
            # per-run temp roots while retaining package-relative suffixes.
            if value == package_text:
                return "<PACKAGE>"
            if value.startswith(package_text + "/"):
                return "<PACKAGE>/" + value[len(package_text) + 1 :]
            if value == root_text:
                return "<OUTPUT_ROOT>"
            if value.startswith(root_text + "/"):
                return "<OUTPUT_ROOT>/" + value[len(root_text) + 1 :]
        return value

    return normalize(payload)


def package_inventory(package):
    records = []
    for path in sorted(package.rglob("*")):
        if path.is_file():
            records.append(
                {
                    "path": path.relative_to(package).as_posix(),
                    "sizeBytes": path.stat().st_size,
                    "sha256": sha256_file(path),
                }
            )
    return records


def package_json_documents(package):
    documents = {}
    for path in sorted(package.rglob("*.json")):
        documents[path.relative_to(package).as_posix()] = load_json(path)
    return documents


def package_json_inventory(package):
    records = []
    for path in sorted(package.rglob("*.json")):
        records.append(
            {
                "path": path.relative_to(package).as_posix(),
                "sizeBytes": path.stat().st_size,
                "sha256": sha256_file(path),
            }
        )
    return records


def assert_debug_hir_pass_trace_contract(errors, case):
    case_name = case["caseLabel"]
    trace = case["jsonDocuments"].get(HIR_PASS_TRACE_SIDECAR_PATH)
    if not case["spec"].debug_ir:
        if trace is not None:
            errors.append(
                f"{case_name}: non-debug package unexpectedly includes "
                f"{HIR_PASS_TRACE_SIDECAR_PATH}"
            )
        return
    if not isinstance(trace, dict):
        errors.append(
            f"{case_name}: debug package must include JSON sidecar "
            f"{HIR_PASS_TRACE_SIDECAR_PATH}"
        )
        return
    passes = trace.get("passes")
    if not isinstance(passes, list) or not passes:
        errors.append(f"{case_name}: HIR pass trace must contain pass records")
        return
    for index, pass_record in enumerate(passes):
        if not isinstance(pass_record, dict):
            errors.append(f"{case_name}: HIR pass trace pass {index} must be object")
            continue
        if "elapsedTimeMicroseconds" in pass_record:
            errors.append(
                f"{case_name}: packaged HIR pass trace pass {index} must not "
                "seal elapsedTimeMicroseconds"
            )
        if not isinstance(pass_record.get("moduleStats"), dict):
            errors.append(
                f"{case_name}: packaged HIR pass trace pass {index} must retain "
                "deterministic moduleStats"
            )


def read_backend_source(package, manifest):
    artifacts = manifest.get("artifacts")
    if not isinstance(artifacts, dict):
        raise ValueError("manifest.artifacts must be an object")
    backend_source = artifacts.get("backendSource")
    if not isinstance(backend_source, str):
        raise ValueError("manifest.artifacts.backendSource must be a string")
    path = package / backend_source
    return backend_source, path.read_text(encoding="utf-8")


def iter_json_strings(value, path="$"):
    if isinstance(value, dict):
        for key, child in value.items():
            yield from iter_json_strings(child, f"{path}.{key}")
    elif isinstance(value, list):
        for index, child in enumerate(value):
            yield from iter_json_strings(child, f"{path}[{index}]")
    elif isinstance(value, str):
        yield path, value


def iter_json_dicts(value, path="$"):
    if isinstance(value, dict):
        yield path, value
        for key, child in value.items():
            yield from iter_json_dicts(child, f"{path}.{key}")
    elif isinstance(value, list):
        for index, child in enumerate(value):
            yield from iter_json_dicts(child, f"{path}[{index}]")


def iter_json_keys(value, path="$"):
    if isinstance(value, dict):
        for key, child in value.items():
            key_path = f"{path}.{key}"
            yield key_path, key
            yield from iter_json_keys(child, key_path)
    elif isinstance(value, list):
        for index, child in enumerate(value):
            yield from iter_json_keys(child, f"{path}[{index}]")


def path_text_is_absolute(value):
    return (
        value.startswith("/")
        or value.startswith("\\")
        or WINDOWS_ABSOLUTE_PATH.match(value) is not None
    )


def assert_relative_package_path(errors, case_name, label, value):
    if not isinstance(value, str) or not value:
        errors.append(f"{case_name}: {label} must be a non-empty relative path string")
        return False
    failed = False
    if "\\" in value:
        errors.append(f"{case_name}: {label} uses backslashes: {value!r}")
        failed = True
    if path_text_is_absolute(value):
        errors.append(f"{case_name}: {label} must be relative, got {value!r}")
        failed = True
    if ".." in PurePosixPath(value).parts:
        errors.append(f"{case_name}: {label} must not escape package root: {value!r}")
        failed = True
    return not failed


def assert_source_location_files_relative(errors, case_name, document_name, payload):
    location_keys = {
        "file",
        "line",
        "column",
        "offset",
        "length",
        "endLine",
        "endColumn",
        "endOffset",
    }
    for json_path, record in iter_json_dicts(payload):
        if not location_keys.issubset(record):
            continue
        location_file = record.get("file")
        if not isinstance(location_file, str):
            errors.append(
                f"{case_name}: {document_name}{json_path}.file must be a string"
            )
            continue
        if location_file:
            assert_relative_package_path(
                errors,
                case_name,
                f"{document_name}{json_path}.file",
                location_file,
            )


def is_native_artifact_descriptor_summary(record):
    return {
        "artifactPresent",
        "descriptorExists",
        "health",
        "checks",
        "path",
    }.issubset(record)


def is_source_remap_provenance_summary(record):
    return {
        "artifactPresent",
        "exists",
        "health",
        "checks",
        "path",
    }.issubset(record)


def assert_path_fields_relative(errors, case_name, document_name, payload):
    for json_path, record in iter_json_dicts(payload):
        if "path" not in record:
            continue
        path_value = record.get("path")
        if is_native_artifact_descriptor_summary(record):
            if (
                record.get("artifactPresent") is False
                and record.get("descriptorExists") is False
                and record.get("health") == "not-present"
                and path_value is None
            ):
                continue
            if record.get("artifactPresent") is True:
                assert_relative_package_path(
                    errors,
                    case_name,
                    f"{document_name}{json_path}.path",
                    path_value,
                )
                continue
        if is_source_remap_provenance_summary(record):
            if (
                record.get("artifactPresent") is False
                and record.get("exists") is False
                and record.get("health") == "not-present"
                and path_value is None
            ):
                continue
            if record.get("artifactPresent") is True:
                assert_relative_package_path(
                    errors,
                    case_name,
                    f"{document_name}{json_path}.path",
                    path_value,
                )
                continue
        assert_relative_package_path(
            errors,
            case_name,
            f"{document_name}{json_path}.path",
            path_value,
        )


def assert_no_path_leaks(errors, case_name, package, forbidden_paths):
    needles = [path.as_posix().encode("utf-8") for path in forbidden_paths]
    for file_path in sorted(path for path in package.rglob("*") if path.is_file()):
        data = file_path.read_bytes()
        for needle, forbidden in zip(needles, forbidden_paths):
            if needle and needle in data:
                rel = file_path.relative_to(package).as_posix()
                errors.append(
                    f"{case_name}: package file {rel} contains absolute path "
                    f"{forbidden.as_posix()!r}"
                )


def assert_metadata_no_path_leaks(errors, case_name, documents, forbidden_paths):
    forbidden = [path.as_posix() for path in forbidden_paths]
    for document_name, payload in documents.items():
        for json_path, value in iter_json_strings(payload):
            normalized = value.replace("\\", "/")
            for forbidden_path in forbidden:
                if forbidden_path and forbidden_path in normalized:
                    errors.append(
                        f"{case_name}: {document_name}{json_path} contains "
                        f"absolute path {forbidden_path!r}"
                    )


def assert_manifest_contract_paths(
    errors, case_name, package, spec, manifest, reflection
):
    artifacts = manifest.get("artifacts")
    if not isinstance(artifacts, dict):
        errors.append(f"{case_name}: manifest.artifacts must be an object")
        return

    required_paths = TARGET_REQUIRED_PATH_ARTIFACTS[spec.target]
    for artifact_name in required_paths:
        artifact_path = artifacts.get(artifact_name)
        if not assert_relative_package_path(
            errors,
            case_name,
            f"manifest.artifacts.{artifact_name}",
            artifact_path,
        ):
            continue
        if (
            artifact_name != "nativeBinary"
            or artifacts.get("nativeBinaryStatus") != "planned"
        ) and not (package / artifact_path).is_file():
            errors.append(
                f"{case_name}: manifest artifact {artifact_name!r} "
                f"does not exist at {artifact_path!r}"
            )

    for artifact_name, artifact_path in artifacts.items():
        if artifact_name == "nativeBinaryStatus":
            continue
        assert_relative_package_path(
            errors,
            case_name,
            f"manifest.artifacts.{artifact_name}",
            artifact_path,
        )

    native_status = artifacts.get("nativeBinaryStatus")
    if native_status not in ("planned", "emitted", "validated"):
        errors.append(
            f"{case_name}: source package must record nativeBinaryStatus, "
            f"got {native_status!r}"
        )

    for debug_artifact in PACKAGE_DEBUG_SIDECAR_ARTIFACTS:
        debug_path = artifacts.get(debug_artifact)
        if spec.debug_ir:
            if not assert_relative_package_path(
                errors,
                case_name,
                f"manifest.artifacts.{debug_artifact}",
                debug_path,
            ):
                continue
            if not (package / debug_path).is_file():
                errors.append(
                    f"{case_name}: debug artifact {debug_artifact!r} "
                    f"does not exist at {debug_path!r}"
                )
        elif debug_artifact in artifacts:
            errors.append(
                f"{case_name}: non-debug package unexpectedly records "
                f"manifest.artifacts.{debug_artifact}"
            )

    manifest_native = artifacts.get("nativeBinary")
    reflection_native = reflection.get("nativeBinary")
    if reflection_native != manifest_native:
        errors.append(
            f"{case_name}: reflection.nativeBinary {reflection_native!r} "
            f"does not match manifest.artifacts.nativeBinary {manifest_native!r}"
        )
    assert_relative_package_path(
        errors, case_name, "reflection.nativeBinary", reflection_native
    )


def assert_cli_path_contracts(errors, case_name, payload):
    for section in ("rootFiles", "artifacts"):
        records = payload.get(section, [])
        if not isinstance(records, list):
            errors.append(f"{case_name}: inspect.{section} must be an array")
            continue
        for index, record in enumerate(records):
            if not isinstance(record, dict):
                errors.append(f"{case_name}: inspect.{section}[{index}] must be object")
                continue
            assert_relative_package_path(
                errors,
                case_name,
                f"inspect.{section}[{index}].path",
                record.get("path"),
            )
            if section == "artifacts" and record.get("packageRelative") is not True:
                errors.append(
                    f"{case_name}: inspect.artifacts[{index}].packageRelative "
                    f"must be True"
                )


def inspect_record_report(record):
    result = {}
    for key in (
        "name",
        "path",
        "exists",
        "packageRelative",
        "sizeBytes",
        "sha256",
        "provenance",
    ):
        if key in record:
            result[key] = record[key]
    return result


def manifest_artifact_paths(manifest):
    artifacts = manifest.get("artifacts")
    if not isinstance(artifacts, dict):
        return {}
    return {
        name: path for name, path in artifacts.items() if name != "nativeBinaryStatus"
    }


def safe_package_file(package, value):
    if not isinstance(value, str) or not value:
        return None
    if "\\" in value or path_text_is_absolute(value):
        return None
    if ".." in PurePosixPath(value).parts:
        return None
    return package / value


def package_file_facts(package, value):
    path = safe_package_file(package, value)
    exists = path.is_file() if path is not None else False
    return {
        "path": value if isinstance(value, str) else None,
        "exists": exists,
        "sizeBytes": path.stat().st_size if exists else None,
        "sha256": sha256_file(path) if exists else None,
    }


def inspect_artifact_record(inspect, name):
    artifacts = inspect.get("artifacts", [])
    if not isinstance(artifacts, list):
        return None
    for record in artifacts:
        if isinstance(record, dict) and record.get("name") == name:
            return record
    return None


def inspect_native_artifact_descriptor_report(inspect):
    descriptor = inspect.get("nativeArtifactDescriptor")
    if not isinstance(descriptor, dict):
        return None
    return {
        "path": descriptor.get("path"),
        "descriptorExists": descriptor.get("descriptorExists"),
        "health": descriptor.get("health"),
        "optimizationLevel": descriptor.get("optimizationLevel"),
        "optimizationEvidence": copy.deepcopy(descriptor.get("optimizationEvidence")),
    }


def native_artifact_descriptor_required(case):
    artifacts = case["manifest"].get("artifacts")
    if not isinstance(artifacts, dict):
        return False

    native_status = artifacts.get("nativeBinaryStatus")
    if native_status == "planned":
        return False
    if native_status in ("emitted", "validated"):
        return True

    native_binary = safe_package_file(case["package"], artifacts.get("nativeBinary"))
    return native_binary.is_file() if native_binary is not None else False


def native_artifact_descriptor_evidence(case):
    artifacts = case["manifest"].get("artifacts")
    if not isinstance(artifacts, dict):
        artifacts = {}
    descriptor_path = artifacts.get(NATIVE_ARTIFACT_DESCRIPTOR)
    declared = isinstance(descriptor_path, str)
    facts = (
        package_file_facts(case["package"], descriptor_path)
        if declared
        else {
            "path": None,
            "exists": False,
            "sizeBytes": None,
            "sha256": None,
        }
    )
    inspect_record = (
        inspect_artifact_record(case["inspect"], NATIVE_ARTIFACT_DESCRIPTOR)
        if declared
        else None
    )
    descriptor_payload = (
        load_json(case["package"] / descriptor_path) if facts["exists"] else {}
    )
    return {
        "required": native_artifact_descriptor_required(case),
        "manifestDeclared": declared,
        "manifestKey": NATIVE_ARTIFACT_DESCRIPTOR,
        "path": facts["path"],
        "exists": facts["exists"],
        "sizeBytes": facts["sizeBytes"],
        "sha256": facts["sha256"],
        "optimizationLevel": descriptor_payload.get("optimizationLevel"),
        "optimizationEvidence": copy.deepcopy(
            descriptor_payload.get("optimizationEvidence")
        ),
        "inspectArtifact": (
            inspect_record_report(inspect_record)
            if isinstance(inspect_record, dict)
            else None
        ),
        "inspectDescriptor": inspect_native_artifact_descriptor_report(case["inspect"]),
    }


def manifest_artifact_report(package, artifacts):
    records = []
    for name, value in artifacts.items():
        if name == "nativeBinaryStatus":
            continue
        record = {
            "name": name,
            "path": value,
        }
        if isinstance(value, str):
            path = package / value
            exists = path.is_file()
            record["exists"] = exists
            record["sizeBytes"] = path.stat().st_size if exists else None
            record["sha256"] = sha256_file(path) if exists else None
        records.append(record)
    return records


def compiler_identity(manifest):
    compiler = manifest.get("compiler")
    if not isinstance(compiler, dict):
        return {}
    return {
        key: compiler.get(key)
        for key in ("name", "version", "llvmVersion")
        if key in compiler
    }


def source_hash_record(manifest):
    source_hash = manifest.get("sourceHash")
    if not isinstance(source_hash, dict):
        return {"algorithm": None, "manifestSha256": None}
    return {
        "algorithm": source_hash.get("algorithm"),
        "manifestSha256": source_hash.get("value"),
    }


def source_hash_evidence(case):
    evidence = source_hash_record(case["manifest"])
    source = case.get("source")
    input_sha = (
        sha256_file(source) if isinstance(source, Path) and source.is_file() else None
    )
    evidence.update(
        {
            "inputSha256": input_sha,
            "matchesInput": (
                evidence.get("algorithm") == "sha256"
                and evidence.get("manifestSha256") == input_sha
            ),
        }
    )
    return evidence


def metadata_report(case):
    manifest = case["manifest"]
    artifacts = manifest.get("artifacts", {})
    if not isinstance(artifacts, dict):
        artifacts = {}
    inspect = case["inspect"]
    verify = case.get("verify")
    report = {
        "case": case["caseLabel"],
        "packageKind": case["packageKind"],
        "module": manifest.get("module"),
        "target": manifest.get("target"),
        "manifestCompiler": compiler_identity(manifest),
        "sourceHashEvidence": source_hash_evidence(case),
        "debugIr": case.get("debugIr"),
        "nativeBinaryStatus": artifacts.get("nativeBinaryStatus"),
        "summary": inspect.get("summary"),
        "manifestArtifactOrder": [
            name for name in artifacts if name != "nativeBinaryStatus"
        ],
        "manifestArtifacts": manifest_artifact_report(case["package"], artifacts),
        "nativeArtifactDescriptorEvidence": native_artifact_descriptor_evidence(case),
        "inspectRootFileOrder": [
            record.get("name") for record in inspect.get("rootFiles", [])
        ],
        "inspectRootFiles": [
            inspect_record_report(record) for record in inspect.get("rootFiles", [])
        ],
        "inspectArtifactOrder": [
            record.get("name") for record in inspect.get("artifacts", [])
        ],
        "inspectArtifacts": [
            inspect_record_report(record) for record in inspect.get("artifacts", [])
        ],
        "metadataFiles": package_json_inventory(case["package"]),
    }
    if isinstance(verify, dict):
        diagnostics = verify.get("diagnostics", [])
        if not isinstance(diagnostics, list):
            diagnostics = []
        report.update(
            {
                "verifySuccess": verify.get("success"),
                "verifyDiagnosticCounts": verify.get("diagnosticCounts"),
                "verifyDiagnosticOrder": [
                    diagnostic.get("code")
                    for diagnostic in diagnostics
                    if isinstance(diagnostic, dict)
                ],
                "verifyReportSha256": report_digest(verify),
            }
        )
    return report


def report_digest(report):
    return hashlib.sha256(canonical_json(report).encode("utf-8")).hexdigest()


def expected_source_case_labels():
    return [spec.label for spec in build_specs()]


def expected_native_fixture_case_labels():
    return [f"{target}-native-fixture" for target in REQUIRED_NATIVE_FIXTURE_TARGETS]


def validate_report_document_summary(report):
    errors = []
    expected_keys = {
        "schemaVersion",
        "toolchainSummary",
        "fixture",
        "sourceCases",
        "nativeFixtureCases",
        "cases",
    }
    if not isinstance(report, dict):
        return ["report: expected object"]

    actual_keys = set(report)
    if actual_keys != expected_keys:
        errors.append(
            "report: top-level keys must be "
            f"{sorted(expected_keys)!r}, got {sorted(actual_keys)!r}"
        )

    for json_path, key in iter_json_keys(report):
        if NONDETERMINISTIC_REPORT_KEY_RE.search(key):
            errors.append(f"report: {json_path} uses nondeterministic key {key!r}")

    if report.get("schemaVersion") != REPORT_SCHEMA_VERSION:
        errors.append(
            "report: schemaVersion must be "
            f"{REPORT_SCHEMA_VERSION}, got {report.get('schemaVersion')!r}"
        )

    toolchain = report.get("toolchainSummary")
    if not isinstance(toolchain, dict) or not toolchain:
        errors.append("report: toolchainSummary must be a non-empty object")
    else:
        for key, value in toolchain.items():
            if not isinstance(key, str) or not isinstance(value, str) or not value:
                errors.append(
                    "report: toolchainSummary entries must have non-empty "
                    "string keys and values"
                )
                break
        cglc_sha = toolchain.get("cglcSha256")
        if not isinstance(cglc_sha, str) or not SHA256_RE.fullmatch(cglc_sha):
            errors.append(
                "report: toolchainSummary.cglcSha256 must be a lowercase SHA-256 digest"
            )

    if report.get("fixture") != FIXTURE.as_posix():
        errors.append(
            f"report: fixture must be {FIXTURE.as_posix()!r}, "
            f"got {report.get('fixture')!r}"
        )

    source_labels = expected_source_case_labels()
    native_labels = expected_native_fixture_case_labels()
    if report.get("sourceCases") != source_labels:
        errors.append(
            f"report: sourceCases must preserve build order {source_labels!r}, "
            f"got {report.get('sourceCases')!r}"
        )
    if report.get("nativeFixtureCases") != native_labels:
        errors.append(
            "report: nativeFixtureCases must preserve fixture order "
            f"{native_labels!r}, got {report.get('nativeFixtureCases')!r}"
        )

    cases = report.get("cases")
    if not isinstance(cases, list):
        errors.append("report: cases must be an array")
        return errors

    expected_labels = source_labels + native_labels
    actual_labels = [
        case.get("case") if isinstance(case, dict) else None for case in cases
    ]
    if actual_labels != expected_labels:
        errors.append(
            f"report: cases must be ordered as {expected_labels!r}, "
            f"got {actual_labels!r}"
        )

    for index, case_report in enumerate(cases):
        if not isinstance(case_report, dict):
            errors.append(f"report: cases[{index}] must be an object")
            continue
        digest = case_report.get("metadataReportSha256")
        if not isinstance(digest, str) or not SHA256_RE.fullmatch(digest):
            errors.append(
                f"report: cases[{index}].metadataReportSha256 must be a "
                "lowercase SHA-256 digest"
            )
            continue
        report_without_digest = dict(case_report)
        report_without_digest.pop("metadataReportSha256", None)
        expected_digest = report_digest(report_without_digest)
        if digest != expected_digest:
            errors.append(
                f"report: cases[{index}].metadataReportSha256 must digest "
                f"the case metadata report, got {digest!r}, "
                f"expected {expected_digest!r}"
            )
    return errors


def self_test_report_document():
    toolchain = {
        "cglc": "self-test-cglc",
        "cglcSha256": "0" * 64,
        "platform": "self-test-platform",
        "python": "self-test-python",
    }
    cases = []
    for label in expected_source_case_labels() + expected_native_fixture_case_labels():
        case = {"case": label, "packageKind": "self-test"}
        cases.append({**case, "metadataReportSha256": report_digest(case)})
    return {
        "schemaVersion": REPORT_SCHEMA_VERSION,
        "toolchainSummary": toolchain,
        "fixture": FIXTURE.as_posix(),
        "sourceCases": expected_source_case_labels(),
        "nativeFixtureCases": expected_native_fixture_case_labels(),
        "cases": cases,
    }


def expected_root_file_order():
    return ["manifest", "reflection", "diagnostics"]


def expected_summary_native_binary_status(manifest):
    artifacts = manifest.get("artifacts", {})
    if not isinstance(artifacts, dict):
        return None
    status = artifacts.get("nativeBinaryStatus")
    if status is not None:
        return status
    if isinstance(manifest.get("packageArtifactRequirements"), dict):
        return None
    if (
        manifest.get("target") == "metal"
        and "intermediate" in artifacts
        and "nativeBinary" in artifacts
    ):
        return "emitted"
    return None


def assert_inspect_record_file_facts(
    errors, case_name, section, index, record, package
):
    path = record.get("path")
    exists = record.get("exists")
    if not isinstance(path, str):
        return

    file_path = package / path
    expected_exists = file_path.is_file()
    if exists != expected_exists:
        errors.append(
            f"{case_name}: inspect.{section}[{index}].exists must be "
            f"{expected_exists}, got {exists!r}"
        )
    expected_size = file_path.stat().st_size if expected_exists else None
    expected_sha = sha256_file(file_path) if expected_exists else None
    if record.get("sizeBytes") != expected_size:
        errors.append(
            f"{case_name}: inspect.{section}[{index}].sizeBytes must be "
            f"{expected_size!r}, got {record.get('sizeBytes')!r}"
        )
    if record.get("sha256") != expected_sha:
        errors.append(
            f"{case_name}: inspect.{section}[{index}].sha256 must be "
            f"{expected_sha!r}, got {record.get('sha256')!r}"
        )


def assert_inspect_record_provenance(
    errors, case_name, label, record, expected_provenance
):
    provenance = record.get("provenance")
    if not isinstance(provenance, dict):
        errors.append(f"{case_name}: {label}.provenance must be an object")
        return
    for key, expected in expected_provenance.items():
        actual = provenance.get(key)
        if actual != expected:
            errors.append(
                f"{case_name}: {label}.provenance.{key} must be "
                f"{expected!r}, got {actual!r}"
            )


def assert_root_file_record_contract(errors, case_name, index, record):
    name = record.get("name")
    label = f"inspect.rootFiles[{index}]"
    expected_path = EXPECTED_ROOT_FILE_PATHS.get(name)
    if expected_path is None:
        errors.append(f"{case_name}: {label}.name is unexpected: {name!r}")
    elif record.get("path") != expected_path:
        errors.append(
            f"{case_name}: {label}.path must match root file {name!r} "
            f"path {expected_path!r}, got {record.get('path')!r}"
        )
    assert_inspect_record_provenance(
        errors,
        case_name,
        label,
        record,
        {
            "kind": "packageRootFile",
            "source": "packageRoot",
        },
    )


def assert_artifact_record_contract(errors, case_name, index, record, manifest_paths):
    name = record.get("name")
    label = f"inspect.artifacts[{index}]"
    expected_path = manifest_paths.get(name)
    if expected_path is None:
        errors.append(f"{case_name}: {label}.name is not a manifest artifact: {name!r}")
    elif record.get("path") != expected_path:
        errors.append(
            f"{case_name}: {label}.path must match manifest.artifacts.{name} "
            f"{expected_path!r}, got {record.get('path')!r}"
        )
    assert_inspect_record_provenance(
        errors,
        case_name,
        label,
        record,
        {
            "kind": "manifestArtifact",
            "source": "manifest.artifacts",
            "manifestKey": name,
        },
    )


def assert_metadata_report_contract(errors, case):
    case_name = case["caseLabel"]
    report = case["metadataReport"]

    expected_compiler = compiler_identity(case["manifest"])
    if report.get("manifestCompiler") != expected_compiler:
        errors.append(
            f"{case_name}: manifestCompiler must match manifest.compiler, "
            f"got {report.get('manifestCompiler')!r}, "
            f"expected {expected_compiler!r}"
        )
    for key in ("name", "version", "llvmVersion"):
        value = expected_compiler.get(key)
        if not isinstance(value, str) or not value:
            errors.append(
                f"{case_name}: manifestCompiler.{key} must be a non-empty string"
            )

    expected_source_hash = source_hash_record(case["manifest"])
    actual_source_hash = report.get("sourceHashEvidence")
    if not isinstance(actual_source_hash, dict):
        errors.append(f"{case_name}: sourceHashEvidence must be an object")
    else:
        for key, expected in expected_source_hash.items():
            if actual_source_hash.get(key) != expected:
                errors.append(
                    f"{case_name}: sourceHashEvidence.{key} must match "
                    f"manifest.sourceHash.{key}, got "
                    f"{actual_source_hash.get(key)!r}, expected {expected!r}"
                )
        source = case.get("source")
        expected_input_sha = (
            sha256_file(source)
            if isinstance(source, Path) and source.is_file()
            else None
        )
        if actual_source_hash.get("inputSha256") != expected_input_sha:
            errors.append(
                f"{case_name}: sourceHashEvidence.inputSha256 must match "
                f"source file SHA-256 {expected_input_sha!r}, "
                f"got {actual_source_hash.get('inputSha256')!r}"
            )
        if actual_source_hash.get("algorithm") != "sha256":
            errors.append(f"{case_name}: sourceHashEvidence.algorithm must be 'sha256'")
        manifest_sha = actual_source_hash.get("manifestSha256")
        if not isinstance(manifest_sha, str) or not SHA256_RE.fullmatch(manifest_sha):
            errors.append(
                f"{case_name}: sourceHashEvidence.manifestSha256 must be a "
                "lowercase SHA-256 digest"
            )
        if actual_source_hash.get("matchesInput") is not True:
            errors.append(f"{case_name}: sourceHashEvidence.matchesInput must be True")

    root_file_order = report["inspectRootFileOrder"]
    expected_root_order = expected_root_file_order()
    if root_file_order != expected_root_order:
        errors.append(
            f"{case_name}: inspect root file order must be {expected_root_order!r}, "
            f"got {root_file_order!r}"
        )

    artifact_order = report["inspectArtifactOrder"]
    manifest_order = report["manifestArtifactOrder"]
    if artifact_order != manifest_order:
        errors.append(
            f"{case_name}: inspect artifact order must match manifest artifact "
            f"order {manifest_order!r}, got {artifact_order!r}"
        )

    expected_descriptor_evidence = native_artifact_descriptor_evidence(case)
    actual_descriptor_evidence = report.get("nativeArtifactDescriptorEvidence")
    if actual_descriptor_evidence != expected_descriptor_evidence:
        errors.append(
            f"{case_name}: nativeArtifactDescriptorEvidence must match "
            f"manifest-declared descriptor file facts, got "
            f"{actual_descriptor_evidence!r}, expected "
            f"{expected_descriptor_evidence!r}"
        )
    if (
        expected_descriptor_evidence["required"]
        and not expected_descriptor_evidence["manifestDeclared"]
    ):
        errors.append(
            f"{case_name}: nativeArtifactDescriptorEvidence requires "
            "manifest.artifacts.nativeArtifactDescriptor when a native binary "
            "artifact is present"
        )
    if expected_descriptor_evidence["manifestDeclared"]:
        descriptor_path = expected_descriptor_evidence["path"]
        if not expected_descriptor_evidence["exists"]:
            errors.append(
                f"{case_name}: manifest-declared nativeArtifactDescriptor "
                f"must exist at {descriptor_path!r}"
            )
        descriptor_size = expected_descriptor_evidence["sizeBytes"]
        if expected_descriptor_evidence["exists"] and not isinstance(
            descriptor_size, int
        ):
            errors.append(
                f"{case_name}: nativeArtifactDescriptorEvidence.sizeBytes "
                "must record descriptor bytes"
            )
        descriptor_sha = expected_descriptor_evidence["sha256"]
        if expected_descriptor_evidence["exists"] and (
            not isinstance(descriptor_sha, str)
            or not SHA256_RE.fullmatch(descriptor_sha)
        ):
            errors.append(
                f"{case_name}: nativeArtifactDescriptorEvidence.sha256 "
                "must be a lowercase SHA-256 digest"
            )
        inspect_descriptor = expected_descriptor_evidence["inspectArtifact"]
        if not isinstance(inspect_descriptor, dict):
            errors.append(
                f"{case_name}: inspect artifacts must record "
                "nativeArtifactDescriptor provenance"
            )
        else:
            for key in ("path", "exists", "sizeBytes", "sha256"):
                if inspect_descriptor.get(key) != expected_descriptor_evidence[key]:
                    errors.append(
                        f"{case_name}: inspect nativeArtifactDescriptor {key} "
                        f"must match descriptor evidence "
                        f"{expected_descriptor_evidence[key]!r}, got "
                        f"{inspect_descriptor.get(key)!r}"
                    )
        if expected_descriptor_evidence["exists"]:
            optimization_level = expected_descriptor_evidence.get("optimizationLevel")
            if not isinstance(optimization_level, str) or not optimization_level:
                errors.append(
                    f"{case_name}: nativeArtifactDescriptorEvidence.optimizationLevel "
                    "must expose the descriptor optimizationLevel"
                )
            inspect_descriptor_content = expected_descriptor_evidence.get(
                "inspectDescriptor"
            )
            if not isinstance(inspect_descriptor_content, dict):
                errors.append(
                    f"{case_name}: package inspect must expose "
                    "nativeArtifactDescriptor optimizer evidence"
                )
            else:
                for key in ("path", "descriptorExists", "health"):
                    expected = {
                        "path": expected_descriptor_evidence["path"],
                        "descriptorExists": True,
                        "health": "ok",
                    }[key]
                    if inspect_descriptor_content.get(key) != expected:
                        errors.append(
                            f"{case_name}: inspect nativeArtifactDescriptor {key} "
                            f"must be {expected!r}, got "
                            f"{inspect_descriptor_content.get(key)!r}"
                        )
                for key in ("optimizationLevel", "optimizationEvidence"):
                    if inspect_descriptor_content.get(
                        key
                    ) != expected_descriptor_evidence.get(key):
                        errors.append(
                            f"{case_name}: inspect nativeArtifactDescriptor {key} "
                            "must match descriptor file evidence, got "
                            f"{inspect_descriptor_content.get(key)!r}, expected "
                            f"{expected_descriptor_evidence.get(key)!r}"
                        )

    for section in ("rootFiles", "artifacts"):
        records = case["inspect"].get(section, [])
        if not isinstance(records, list):
            continue
        manifest_paths = manifest_artifact_paths(case["manifest"])
        for index, record in enumerate(records):
            if not isinstance(record, dict):
                continue
            if section == "rootFiles":
                assert_root_file_record_contract(errors, case_name, index, record)
            else:
                assert_artifact_record_contract(
                    errors, case_name, index, record, manifest_paths
                )
            assert_inspect_record_file_facts(
                errors, case_name, section, index, record, case["package"]
            )

    summary = case["inspect"].get("summary")
    if not isinstance(summary, dict):
        errors.append(f"{case_name}: inspect.summary must be an object")
        return
    if summary.get("artifactCount") != len(artifact_order):
        errors.append(
            f"{case_name}: inspect.summary.artifactCount must equal emitted "
            f"artifact record count {len(artifact_order)}, "
            f"got {summary.get('artifactCount')!r}"
        )
    expected_debug = {"debugMetadata", "hirSourceMap"}.issubset(artifact_order)
    if summary.get("debugArtifactsPresent") != expected_debug:
        errors.append(
            f"{case_name}: inspect.summary.debugArtifactsPresent must be "
            f"{expected_debug}, got {summary.get('debugArtifactsPresent')!r}"
        )
    expected_native_status = expected_summary_native_binary_status(case["manifest"])
    if summary.get("nativeBinaryStatus") != expected_native_status:
        errors.append(
            f"{case_name}: inspect.summary.nativeBinaryStatus must match "
            f"package contract {expected_native_status!r}, "
            f"got {summary.get('nativeBinaryStatus')!r}"
        )

    verify = case.get("verify")
    if isinstance(verify, dict):
        expected_verify_digest = report_digest(verify)
        if report.get("verifyReportSha256") != expected_verify_digest:
            errors.append(
                f"{case_name}: verifyReportSha256 must digest normalized "
                f"package verify JSON, got {report.get('verifyReportSha256')!r}, "
                f"expected {expected_verify_digest!r}"
            )
        if report.get("verifySuccess") != verify.get("success"):
            errors.append(
                f"{case_name}: verifySuccess must match package verify JSON, "
                f"got {report.get('verifySuccess')!r}, "
                f"expected {verify.get('success')!r}"
            )
        if report.get("verifyDiagnosticCounts") != verify.get("diagnosticCounts"):
            errors.append(
                f"{case_name}: verifyDiagnosticCounts must match package verify "
                f"JSON, got {report.get('verifyDiagnosticCounts')!r}, "
                f"expected {verify.get('diagnosticCounts')!r}"
            )

        diagnostics = verify.get("diagnostics", [])
        if not isinstance(diagnostics, list):
            diagnostics = []
        expected_diagnostic_order = [
            diagnostic.get("code")
            for diagnostic in diagnostics
            if isinstance(diagnostic, dict)
        ]
        if report.get("verifyDiagnosticOrder") != expected_diagnostic_order:
            errors.append(
                f"{case_name}: verifyDiagnosticOrder must preserve package "
                f"verify diagnostic order {expected_diagnostic_order!r}, "
                f"got {report.get('verifyDiagnosticOrder')!r}"
            )


def assert_report_document_contract(
    errors, report, source_pairs, native_pairs, expected_toolchain_summary
):
    summary_errors = validate_report_document_summary(report)
    allowed_summary_errors = {
        "report: sourceCases must preserve build order "
        f"{expected_source_case_labels()!r}, got "
        f"{[first['caseLabel'] for first, _second in source_pairs]!r}",
        "report: nativeFixtureCases must preserve fixture order "
        f"{expected_native_fixture_case_labels()!r}, got "
        f"{[first['caseLabel'] for first, _second in native_pairs]!r}",
        "report: cases must be ordered as "
        f"{(expected_source_case_labels() + expected_native_fixture_case_labels())!r}, "
        f"got "
        f"{[first['caseLabel'] for first, _second in source_pairs + native_pairs]!r}",
    }
    errors.extend(
        error for error in summary_errors if error not in allowed_summary_errors
    )

    expected_keys = {
        "schemaVersion",
        "toolchainSummary",
        "fixture",
        "sourceCases",
        "nativeFixtureCases",
        "cases",
    }
    actual_keys = set(report)
    if actual_keys != expected_keys:
        errors.append(
            "report: top-level keys must be "
            f"{sorted(expected_keys)!r}, got {sorted(actual_keys)!r}"
        )

    for json_path, key in iter_json_keys(report):
        if NONDETERMINISTIC_REPORT_KEY_RE.search(key):
            errors.append(f"report: {json_path} uses nondeterministic key {key!r}")

    if report.get("schemaVersion") != REPORT_SCHEMA_VERSION:
        errors.append(
            "report: schemaVersion must be "
            f"{REPORT_SCHEMA_VERSION}, got {report.get('schemaVersion')!r}"
        )
    toolchain = report.get("toolchainSummary")
    if toolchain != expected_toolchain_summary:
        errors.append(
            "report: toolchainSummary must match the checker toolchain "
            f"summary {expected_toolchain_summary!r}, got {toolchain!r}"
        )
    if not isinstance(toolchain, dict) or not toolchain:
        errors.append("report: toolchainSummary must be a non-empty object")
    else:
        for key, value in toolchain.items():
            if not isinstance(key, str) or not isinstance(value, str) or not value:
                errors.append(
                    "report: toolchainSummary entries must have non-empty "
                    "string keys and values"
                )
                break
        cglc_sha = toolchain.get("cglcSha256")
        if not isinstance(cglc_sha, str) or not SHA256_RE.fullmatch(cglc_sha):
            errors.append(
                "report: toolchainSummary.cglcSha256 must be a lowercase SHA-256 digest"
            )
    if report.get("fixture") != FIXTURE.as_posix():
        errors.append(
            f"report: fixture must be {FIXTURE.as_posix()!r}, "
            f"got {report.get('fixture')!r}"
        )

    source_labels = [first["caseLabel"] for first, _second in source_pairs]
    native_labels = [first["caseLabel"] for first, _second in native_pairs]
    if report.get("sourceCases") != source_labels:
        errors.append(
            f"report: sourceCases must preserve build order {source_labels!r}, "
            f"got {report.get('sourceCases')!r}"
        )
    if report.get("nativeFixtureCases") != native_labels:
        errors.append(
            "report: nativeFixtureCases must preserve fixture order "
            f"{native_labels!r}, got {report.get('nativeFixtureCases')!r}"
        )

    cases = report.get("cases")
    if not isinstance(cases, list):
        errors.append("report: cases must be an array")
        return

    expected_labels = source_labels + native_labels
    actual_labels = [
        case.get("case") if isinstance(case, dict) else None for case in cases
    ]
    if actual_labels != expected_labels:
        errors.append(
            f"report: cases must be ordered as {expected_labels!r}, "
            f"got {actual_labels!r}"
        )

    for index, case_report in enumerate(cases):
        if not isinstance(case_report, dict):
            errors.append(f"report: cases[{index}] must be an object")
            continue
        digest = case_report.get("metadataReportSha256")
        report_without_digest = dict(case_report)
        report_without_digest.pop("metadataReportSha256", None)
        expected_digest = report_digest(report_without_digest)
        if digest != expected_digest:
            errors.append(
                f"report: cases[{index}].metadataReportSha256 must digest "
                f"the case metadata report, got {digest!r}, "
                f"expected {expected_digest!r}"
            )


def assert_case_path_contracts(errors, case, forbidden_paths):
    case_name = case["spec"].label
    assert_manifest_contract_paths(
        errors,
        case_name,
        case["package"],
        case["spec"],
        case["manifest"],
        case["reflection"],
    )
    assert_cli_path_contracts(errors, case_name, case["inspect"])
    assert_metadata_no_path_leaks(
        errors, case_name, case["jsonDocuments"], forbidden_paths
    )
    assert_no_path_leaks(errors, case_name, case["package"], forbidden_paths)
    assert_debug_hir_pass_trace_contract(errors, case)

    for document_name, payload in case["jsonDocuments"].items():
        assert_path_fields_relative(errors, case_name, document_name, payload)
        assert_source_location_files_relative(errors, case_name, document_name, payload)

    for cli_name in ("inspect", "verify"):
        assert_path_fields_relative(
            errors, case_name, f"{cli_name}.json", case[cli_name]
        )
        assert_source_location_files_relative(
            errors, case_name, f"{cli_name}.json", case[cli_name]
        )

    assert_metadata_report_contract(errors, case)


def assert_native_fixture_path_contracts(errors, case, forbidden_paths):
    case_name = case["caseLabel"]
    artifacts = case["manifest"].get("artifacts")
    if not isinstance(artifacts, dict):
        errors.append(f"{case_name}: manifest.artifacts must be an object")
        return

    required_order = (
        tuple(FIXTURE_TARGET_ARTIFACT_PATHS[case["manifest"]["target"]])
        + tuple(PACKAGE_DEBUG_ARTIFACTS)
        + (NATIVE_ARTIFACT_DESCRIPTOR,)
        + (PACKAGE_TARGET_EXPLANATION_ARTIFACT,)
    )
    actual_order = tuple(artifacts)
    if actual_order != required_order:
        errors.append(
            f"{case_name}: manifest artifact order must be {required_order!r}, "
            f"got {actual_order!r}"
        )

    for artifact_name, artifact_path in artifacts.items():
        assert_relative_package_path(
            errors,
            case_name,
            f"manifest.artifacts.{artifact_name}",
            artifact_path,
        )
        if not (case["package"] / artifact_path).is_file():
            errors.append(
                f"{case_name}: manifest artifact {artifact_name!r} "
                f"does not exist at {artifact_path!r}"
            )

    reflection_native = case["reflection"].get("nativeBinary")
    manifest_native = artifacts.get("nativeBinary")
    if reflection_native != manifest_native:
        errors.append(
            f"{case_name}: reflection.nativeBinary {reflection_native!r} "
            f"does not match manifest.artifacts.nativeBinary {manifest_native!r}"
        )
    assert_relative_package_path(
        errors, case_name, "reflection.nativeBinary", reflection_native
    )

    assert_cli_path_contracts(errors, case_name, case["inspect"])
    assert_metadata_no_path_leaks(
        errors, case_name, case["jsonDocuments"], forbidden_paths
    )
    assert_no_path_leaks(errors, case_name, case["package"], forbidden_paths)

    for document_name, payload in case["jsonDocuments"].items():
        assert_path_fields_relative(errors, case_name, document_name, payload)
        assert_source_location_files_relative(errors, case_name, document_name, payload)

    for cli_name in ("inspect", "verify"):
        assert_path_fields_relative(
            errors, case_name, f"{cli_name}.json", case[cli_name]
        )
        assert_source_location_files_relative(
            errors, case_name, f"{cli_name}.json", case[cli_name]
        )

    assert_metadata_report_contract(errors, case)


def build_case(root, cglc, tmp_dir, spec, name):
    output_root = tmp_dir / f"{spec.label}-{name}"
    package = output_root / PACKAGE_NAME
    command = [
        cglc,
        "build",
        FIXTURE,
        "--target",
        spec.target,
        "--output",
        package,
    ]
    if spec.debug_ir:
        command.append("--debug-ir")

    result = run(command, cwd=root)
    if result.returncode != 0:
        raise RuntimeError(
            f"{spec.label}/{name}: build failed: {result.stderr}{result.stdout}".strip()
        )

    inspect = run([cglc, "package", "inspect", package, "--json"], cwd=root)
    if inspect.returncode != 0:
        raise RuntimeError(
            f"{spec.label}/{name}: package inspect failed: "
            f"{inspect.stderr}{inspect.stdout}".strip()
        )

    verify = run(
        [cglc, "package", "verify", package, "--source", FIXTURE, "--json"],
        cwd=root,
    )
    if verify.returncode != 0:
        raise RuntimeError(
            f"{spec.label}/{name}: package verify failed: "
            f"{verify.stderr}{verify.stdout}".strip()
        )

    verify_payload = json.loads(verify.stdout)
    if verify_payload.get("success") is not True:
        raise RuntimeError(
            f"{spec.label}/{name}: package verify did not report success"
        )

    documents = package_json_documents(package)
    manifest = documents.get("manifest.json")
    reflection = documents.get("reflection.json")
    if not isinstance(manifest, dict):
        raise ValueError(f"{spec.label}/{name}: manifest.json must be an object")
    if not isinstance(reflection, dict):
        raise ValueError(f"{spec.label}/{name}: reflection.json must be an object")

    backend_source_path, backend_source = read_backend_source(package, manifest)
    case = {
        "caseLabel": spec.label,
        "packageKind": "source-package",
        "debugIr": spec.debug_ir,
        "spec": spec,
        "outputRoot": output_root,
        "package": package,
        "source": root / FIXTURE,
        "manifest": manifest,
        "reflection": reflection,
        "jsonDocuments": documents,
        "inspect": normalize_cli_payload(
            json.loads(inspect.stdout), package, output_root
        ),
        "verify": normalize_cli_payload(verify_payload, package, output_root),
        "inventory": package_inventory(package),
        "backendSourcePath": backend_source_path,
        "backendSource": backend_source,
    }
    case["metadataReport"] = metadata_report(case)
    return case


def inspect_existing_package(root, cglc, package, source, case_label, package_kind):
    inspect = run([cglc, "package", "inspect", package, "--json"], cwd=root)
    if inspect.returncode != 0:
        raise RuntimeError(
            f"{case_label}: package inspect failed: "
            f"{inspect.stderr}{inspect.stdout}".strip()
        )

    verify = run(
        [cglc, "package", "verify", package, "--source", source, "--json"],
        cwd=root,
    )
    if verify.returncode != 0:
        raise RuntimeError(
            f"{case_label}: package verify failed: "
            f"{verify.stderr}{verify.stdout}".strip()
        )

    verify_payload = json.loads(verify.stdout)
    if verify_payload.get("success") is not True:
        raise RuntimeError(f"{case_label}: package verify did not report success")

    documents = package_json_documents(package)
    manifest = documents.get("manifest.json")
    reflection = documents.get("reflection.json")
    if not isinstance(manifest, dict):
        raise ValueError(f"{case_label}: manifest.json must be an object")
    if not isinstance(reflection, dict):
        raise ValueError(f"{case_label}: reflection.json must be an object")

    case = {
        "caseLabel": case_label,
        "packageKind": package_kind,
        "debugIr": None,
        "outputRoot": package.parent,
        "package": package,
        "source": source,
        "manifest": manifest,
        "reflection": reflection,
        "jsonDocuments": documents,
        "inspect": normalize_cli_payload(
            json.loads(inspect.stdout), package, package.parent
        ),
        "verify": normalize_cli_payload(verify_payload, package, package.parent),
        "inventory": package_inventory(package),
    }
    case["metadataReport"] = metadata_report(case)
    return case


def attach_native_fixture_descriptor(package, manifest):
    descriptor_path = (
        f"backend/{manifest['target']}/{manifest['module']}.native-artifact.json"
    )
    reordered_artifacts = {}
    descriptor_inserted = False
    for artifact_name, artifact_value in manifest["artifacts"].items():
        if (
            artifact_name == PACKAGE_TARGET_EXPLANATION_ARTIFACT
            and not descriptor_inserted
        ):
            reordered_artifacts[NATIVE_ARTIFACT_DESCRIPTOR] = descriptor_path
            descriptor_inserted = True
        reordered_artifacts[artifact_name] = artifact_value
    if not descriptor_inserted:
        reordered_artifacts[NATIVE_ARTIFACT_DESCRIPTOR] = descriptor_path
    manifest["artifacts"] = reordered_artifacts

    descriptor = make_native_artifact_descriptor(package, manifest)
    write_fixture_json(package / descriptor_path, descriptor)
    write_fixture_json(package / "manifest.json", manifest)


def native_fixture_case(root, cglc, tmp_dir, target, name):
    case_label = f"{target}-native-fixture"
    fixture_root = tmp_dir / f"{case_label}-{name}"
    package, source, manifest = make_package(
        fixture_root,
        case_label,
        target=target,
    )
    attach_native_fixture_descriptor(package, manifest)
    return inspect_existing_package(
        root,
        cglc,
        package,
        source,
        case_label,
        "native-package-fixture",
    )


def compare_records(errors, label, first, second):
    left = canonical_json(first)
    right = canonical_json(second)
    if left != right:
        errors.append(f"{label} differs:\n{unified_diff(label, left, right)}")


def compare_metadata_reports(errors, first, second):
    first_report = first["metadataReport"]
    second_report = second["metadataReport"]
    compare_records(
        errors,
        f"{first['caseLabel']}/metadata-report.json",
        first_report,
        second_report,
    )
    if report_digest(first_report) != report_digest(second_report):
        errors.append(
            f"{first['caseLabel']}: metadata report digest differs: "
            f"{report_digest(first_report)} != {report_digest(second_report)}"
        )


def compare_cases(first, second):
    errors = []
    label = first["spec"].label
    if first["spec"] != second["spec"]:
        errors.append(f"{label}: compared mismatched build specs")
        return errors

    compare_metadata_reports(errors, first, second)

    if sorted(first["jsonDocuments"]) != sorted(second["jsonDocuments"]):
        errors.append(
            f"{label}: JSON metadata set differs: "
            f"{sorted(first['jsonDocuments'])!r} != "
            f"{sorted(second['jsonDocuments'])!r}"
        )
    for document in sorted(set(first["jsonDocuments"]) & set(second["jsonDocuments"])):
        compare_records(
            errors,
            f"{label}/{document}",
            first["jsonDocuments"][document],
            second["jsonDocuments"][document],
        )

    compare_records(
        errors, f"{label}/package-inspect.json", first["inspect"], second["inspect"]
    )
    compare_records(
        errors, f"{label}/package-verify.json", first["verify"], second["verify"]
    )
    compare_records(
        errors, f"{label}/package-inventory", first["inventory"], second["inventory"]
    )

    if first["backendSourcePath"] != second["backendSourcePath"]:
        errors.append(
            f"{label}: backend source artifact path differs: "
            f"{first['backendSourcePath']!r} != {second['backendSourcePath']!r}"
        )
    if first["backendSource"] != second["backendSource"]:
        errors.append(
            f"{label}: generated backend source differs:\n"
            + unified_diff(
                f"{label}/{first['backendSourcePath']}",
                first["backendSource"],
                second["backendSource"],
            )
        )
    return errors


def compare_native_fixture_cases(first, second):
    errors = []
    if first["caseLabel"] != second["caseLabel"]:
        errors.append(
            f"{first['caseLabel']}: compared mismatched native fixture cases "
            f"{first['caseLabel']!r} != {second['caseLabel']!r}"
        )
        return errors

    compare_metadata_reports(errors, first, second)
    for label, key in (
        ("JSON metadata set", "jsonDocuments"),
        ("package inventory", "inventory"),
        ("package-inspect.json", "inspect"),
        ("package-verify.json", "verify"),
    ):
        compare_records(
            errors,
            f"{first['caseLabel']}/{label}",
            first[key],
            second[key],
        )
    return errors


def build_specs():
    return [
        BuildSpec(target=target, debug_ir=debug_ir)
        for target in REQUIRED_SOURCE_TARGETS
        for debug_ir in DEBUG_VARIANTS
    ]


def build_case_pair(root, cglc, tmp_dir, spec):
    first = build_case(root, cglc, tmp_dir, spec, "first")
    second = build_case(root, cglc, tmp_dir, spec, "second")
    return first, second


def native_fixture_case_pair(root, cglc, tmp_dir, target):
    first = native_fixture_case(root, cglc, tmp_dir, target, "first")
    second = native_fixture_case(root, cglc, tmp_dir, target, "second")
    return first, second


def report_document(source_pairs, native_pairs, toolchain):
    cases = []
    for first, _second in source_pairs + native_pairs:
        report = first["metadataReport"]
        cases.append(
            {
                **report,
                "metadataReportSha256": report_digest(report),
            }
        )
    return {
        "schemaVersion": REPORT_SCHEMA_VERSION,
        "toolchainSummary": toolchain,
        "fixture": FIXTURE.as_posix(),
        "sourceCases": [first["caseLabel"] for first, _second in source_pairs],
        "nativeFixtureCases": [first["caseLabel"] for first, _second in native_pairs],
        "cases": cases,
    }


def self_test_file_record(package, name, relative_path, provenance):
    path = package / relative_path
    return {
        "name": name,
        "path": relative_path,
        "provenance": provenance,
        "exists": path.is_file(),
        "sizeBytes": path.stat().st_size if path.is_file() else None,
        "sha256": sha256_file(path) if path.is_file() else None,
    }


def self_test_case(tmp_dir):
    package = tmp_dir / "SelfTest.cglb"
    input_source = tmp_dir / "SelfTest.cgl"
    input_source.write_text("shader SelfTest { }\n", encoding="utf-8")
    backend_source_path = "targets/directx/SelfTest.hlsl"
    native_binary_path = "targets/directx/SelfTest.dxil"
    descriptor_path = "targets/directx/SelfTest.native-artifact.json"
    manifest = {
        "schemaVersion": 1,
        "compiler": {
            "name": "CrossGL-Compiler",
            "version": "self-test",
            "llvmVersion": "self-test",
        },
        "module": "SelfTest",
        "target": "directx",
        "sourceHash": {
            "algorithm": "sha256",
            "value": sha256_file(input_source),
        },
        "artifacts": {
            "backendSource": backend_source_path,
            "nativeBinary": native_binary_path,
            "nativeBinaryStatus": "emitted",
            NATIVE_ARTIFACT_DESCRIPTOR: descriptor_path,
        },
    }
    write_json(package / "reflection.json", {"module": "SelfTest"})
    write_json(package / "diagnostics.json", {"diagnostics": []})
    source = package / backend_source_path
    source.parent.mkdir(parents=True, exist_ok=True)
    source.write_text("// deterministic fixture\n", encoding="utf-8")
    native_binary = package / native_binary_path
    native_binary.write_bytes(b"self-test dxil fixture\n")
    descriptor = {
        "schemaVersion": 1,
        "kind": "crossgl.nativeArtifact",
        "contractVersion": "native-artifact-v0",
        "target": "directx",
        "binaryKind": "directx.dxil",
        "sourcePath": backend_source_path,
        "sourceHash": {
            "algorithm": "sha256",
            "value": sha256_file(source),
        },
        "artifactPath": native_binary_path,
        "artifactHash": {
            "algorithm": "sha256",
            "value": sha256_file(native_binary),
        },
        "sizeBytes": native_binary.stat().st_size,
        "nativeBinaryStatus": "emitted",
        "toolchainProvenance": {
            "producer": "package reproducibility self-test",
            "tools": [
                {
                    "name": "self-test directx backend",
                    "role": "compiler",
                    "version": "self-test",
                    "executable": "cglc",
                }
            ],
            "invocation": {
                "commandLineSha256": "1" * 64,
                "environmentSha256": "2" * 64,
            },
        },
        "optimizationLevel": "O0",
        "optimizationEvidence": {
            "requestedLevel": "O0",
            "effectiveLevel": "O0",
            "policy": "crossgl-to-dxc-optimization-map",
            "status": "metadata-only",
            "tool": "dxc",
            "toolFlag": "-Od",
            "debugInfo": False,
            "flags": ["-Od"],
            "evidenceSource": {
                "kind": "compiler-policy",
            },
        },
        "validationStatus": "unavailable",
        "validationDiagnostics": [],
    }
    write_json(package / descriptor_path, descriptor)
    write_json(package / "manifest.json", manifest)

    root_files = [
        self_test_file_record(
            package,
            name,
            relative_path,
            {"kind": "packageRootFile", "source": "packageRoot"},
        )
        for name, relative_path in EXPECTED_ROOT_FILE_PATHS.items()
    ]
    artifacts = []
    for artifact_name, artifact_path in manifest["artifacts"].items():
        if artifact_name == "nativeBinaryStatus":
            continue
        artifacts.append(
            {
                **self_test_file_record(
                    package,
                    artifact_name,
                    artifact_path,
                    {
                        "kind": "manifestArtifact",
                        "source": "manifest.artifacts",
                        "manifestKey": artifact_name,
                    },
                ),
                "packageRelative": True,
            }
        )
    inspect = {
        "summary": {
            "module": "SelfTest",
            "target": "directx",
            "nativeBinaryStatus": "emitted",
            "artifactCount": len(artifacts),
            "debugArtifactsPresent": False,
        },
        "rootFiles": root_files,
        "artifacts": artifacts,
        "nativeArtifactDescriptor": {
            "artifactPresent": True,
            "descriptorExists": True,
            "health": "ok",
            "path": descriptor_path,
            "schemaVersion": 1,
            "kind": "crossgl.nativeArtifact",
            "contractVersion": "native-artifact-v0",
            "target": "directx",
            "binaryKind": "directx.dxil",
            "sourcePath": backend_source_path,
            "sourceHash": sha256_file(source),
            "artifactPath": native_binary_path,
            "artifactHash": sha256_file(native_binary),
            "sizeBytes": native_binary.stat().st_size,
            "optimizationLevel": descriptor["optimizationLevel"],
            "optimizationEvidence": descriptor["optimizationEvidence"],
            "validationStatus": "unavailable",
            "nativeBinaryStatus": "emitted",
            "checks": {
                "descriptorIdentityMatchesContract": True,
                "targetMatchesPackage": True,
                "nativeBinaryStatusMatchesPackage": True,
                "sourcePathMatchesManifest": True,
                "sourceHashMatchesFile": True,
                "artifactPathMatchesManifest": True,
                "artifactHashMatchesFile": True,
                "sizeBytesMatchesFile": True,
                "validationStatusMatchesNativeStatus": True,
            },
        },
    }
    verify = {
        "schemaVersion": 1,
        "packagePath": "<PACKAGE>",
        "success": True,
        "diagnosticCounts": {"note": 1, "warning": 0, "error": 0},
        "diagnostics": [
            {
                "severity": "note",
                "code": "package.verify.self-test",
                "message": "self-test verifier note",
            }
        ],
        "summary": inspect["summary"],
    }
    case = {
        "caseLabel": "self-test-directx-nodebug",
        "packageKind": "source-package",
        "debugIr": False,
        "package": package,
        "source": input_source,
        "manifest": manifest,
        "inspect": inspect,
        "verify": verify,
    }
    case["metadataReport"] = metadata_report(case)
    return case


def refresh_self_test_metadata(case):
    case["metadataReport"] = metadata_report(case)
    return case


def assert_self_test_failure(label, mutator, expected_fragment, base_case):
    case = copy.deepcopy(base_case)
    mutator(case)
    refresh_self_test_metadata(case)
    errors = []
    assert_metadata_report_contract(errors, case)
    if not any(expected_fragment in error for error in errors):
        raise AssertionError(
            f"{label}: expected failure containing {expected_fragment!r}, "
            f"got {errors!r}"
        )


def run_self_test():
    with tempfile.TemporaryDirectory(prefix="crossgl-package-repro-self-test-") as tmp:
        base_case = self_test_case(Path(tmp))
        test_toolchain = {
            "cglc": "self-test-cglc",
            "cglcSha256": "0" * 64,
            "platform": "self-test-platform",
            "python": "self-test-python",
        }

        errors = []
        assert_metadata_report_contract(errors, base_case)
        if errors:
            raise AssertionError(f"valid metadata fixture failed: {errors!r}")

        def rewrite_artifact_path(case):
            other_path = "targets/directx/Other.hlsl"
            other = case["package"] / other_path
            other.write_text("// alternate fixture\n", encoding="utf-8")
            record = case["inspect"]["artifacts"][0]
            record["path"] = other_path
            record["sizeBytes"] = other.stat().st_size
            record["sha256"] = sha256_file(other)

        assert_self_test_failure(
            "artifact path provenance",
            rewrite_artifact_path,
            "path must match manifest.artifacts.backendSource",
            base_case,
        )

        def rewrite_artifact_provenance(case):
            case["inspect"]["artifacts"][0]["provenance"]["manifestKey"] = "other"

        assert_self_test_failure(
            "artifact manifest key provenance",
            rewrite_artifact_provenance,
            "provenance.manifestKey must be 'backendSource'",
            base_case,
        )

        def rewrite_root_provenance(case):
            case["inspect"]["rootFiles"][0]["provenance"]["source"] = "generated"

        assert_self_test_failure(
            "root file provenance",
            rewrite_root_provenance,
            "provenance.source must be 'packageRoot'",
            base_case,
        )

        def rewrite_source_hash(case):
            case["manifest"]["sourceHash"]["value"] = "0" * 64

        assert_self_test_failure(
            "manifest source hash",
            rewrite_source_hash,
            "sourceHashEvidence.matchesInput must be True",
            base_case,
        )

        def clear_compiler_version(case):
            case["manifest"]["compiler"]["version"] = ""

        assert_self_test_failure(
            "manifest compiler identity",
            clear_compiler_version,
            "manifestCompiler.version must be a non-empty string",
            base_case,
        )

        def point_descriptor_to_missing_file(case):
            missing_path = "targets/directx/Missing.native-artifact.json"
            case["manifest"]["artifacts"][NATIVE_ARTIFACT_DESCRIPTOR] = missing_path
            for record in case["inspect"]["artifacts"]:
                if record["name"] == NATIVE_ARTIFACT_DESCRIPTOR:
                    record["path"] = missing_path
                    record["exists"] = False
                    record["sizeBytes"] = None
                    record["sha256"] = None

        assert_self_test_failure(
            "missing native artifact descriptor",
            point_descriptor_to_missing_file,
            "manifest-declared nativeArtifactDescriptor must exist",
            base_case,
        )

        def remove_manifest_descriptor_keep_legacy_file(case):
            legacy_path = case["package"] / "metadata/native-artifact.json"
            legacy_path.parent.mkdir(parents=True, exist_ok=True)
            legacy_path.write_text(
                canonical_json({"legacy": "not manifest-declared"}),
                encoding="utf-8",
            )
            case["manifest"]["artifacts"].pop(NATIVE_ARTIFACT_DESCRIPTOR)
            case["inspect"]["artifacts"] = [
                record
                for record in case["inspect"]["artifacts"]
                if record["name"] != NATIVE_ARTIFACT_DESCRIPTOR
            ]
            case["inspect"]["summary"]["artifactCount"] = len(
                case["inspect"]["artifacts"]
            )

        assert_self_test_failure(
            "legacy descriptor path ignored",
            remove_manifest_descriptor_keep_legacy_file,
            "requires manifest.artifacts.nativeArtifactDescriptor",
            base_case,
        )

        descriptor_digest_case = copy.deepcopy(base_case)
        descriptor_digest_case["metadataReport"]["nativeArtifactDescriptorEvidence"][
            "sha256"
        ] = "0" * 64
        errors = []
        assert_metadata_report_contract(errors, descriptor_digest_case)
        if not any(
            "nativeArtifactDescriptorEvidence must match" in error for error in errors
        ):
            raise AssertionError(
                f"descriptor digest negative case did not fail: {errors!r}"
            )

        digest_case = copy.deepcopy(base_case)
        digest_case["metadataReport"]["verifyReportSha256"] = "0" * 64
        errors = []
        assert_metadata_report_contract(errors, digest_case)
        if not any("verifyReportSha256 must digest" in error for error in errors):
            raise AssertionError(
                f"verify digest negative case did not fail: {errors!r}"
            )

        order_case = copy.deepcopy(base_case)
        order_case["metadataReport"]["verifyDiagnosticOrder"] = ["package.verify.other"]
        errors = []
        assert_metadata_report_contract(errors, order_case)
        if not any("verifyDiagnosticOrder must preserve" in error for error in errors):
            raise AssertionError(
                f"verify diagnostic order negative case did not fail: {errors!r}"
            )

        source_pairs = [(base_case, base_case)]
        report = report_document(source_pairs, [], test_toolchain)
        report_errors = []
        assert_report_document_contract(
            report_errors, report, source_pairs, [], test_toolchain
        )
        if report_errors:
            raise AssertionError(f"valid report fixture failed: {report_errors!r}")

        mutated_report = copy.deepcopy(report)
        mutated_report["generatedAt"] = "2026-06-01T00:00:00Z"
        report_errors = []
        assert_report_document_contract(
            report_errors, mutated_report, source_pairs, [], test_toolchain
        )
        if not any("nondeterministic key" in error for error in report_errors):
            raise AssertionError(
                f"report timestamp negative case did not fail: {report_errors!r}"
            )

        mutated_report = copy.deepcopy(report)
        mutated_report["toolchainSummary"]["cglcSha256"] = "not-a-sha"
        report_errors = []
        assert_report_document_contract(
            report_errors, mutated_report, source_pairs, [], test_toolchain
        )
        if not any("toolchainSummary.cglcSha256" in error for error in report_errors):
            raise AssertionError(
                f"toolchain digest negative case did not fail: {report_errors!r}"
            )

        mutated_report = copy.deepcopy(report)
        mutated_report["cases"][0]["metadataReportSha256"] = "0" * 64
        report_errors = []
        assert_report_document_contract(
            report_errors, mutated_report, source_pairs, [], test_toolchain
        )
        if not any(
            "metadataReportSha256 must digest" in error for error in report_errors
        ):
            raise AssertionError(
                f"report digest negative case did not fail: {report_errors!r}"
            )

        summary_report = self_test_report_document()
        summary_errors = validate_report_document_summary(summary_report)
        if summary_errors:
            raise AssertionError(
                f"valid summary report fixture failed: {summary_errors!r}"
            )

        summary_missing_case = copy.deepcopy(summary_report)
        summary_missing_case["cases"] = summary_missing_case["cases"][:-1]
        summary_missing_case_errors = validate_report_document_summary(
            summary_missing_case
        )
        if not any(
            "cases must be ordered" in error for error in summary_missing_case_errors
        ):
            raise AssertionError(
                "summary report missing case negative did not fail: "
                f"{summary_missing_case_errors!r}"
            )

        summary_bad_digest = copy.deepcopy(summary_report)
        summary_bad_digest["cases"][0]["metadataReportSha256"] = "0" * 64
        summary_bad_digest_errors = validate_report_document_summary(summary_bad_digest)
        if not any(
            "metadataReportSha256 must digest" in error
            for error in summary_bad_digest_errors
        ):
            raise AssertionError(
                "summary report bad digest negative did not fail: "
                f"{summary_bad_digest_errors!r}"
            )


def positive_int(value):
    try:
        parsed = int(value)
    except (TypeError, ValueError) as exc:
        raise argparse.ArgumentTypeError("must be a positive integer") from exc
    if parsed < 1:
        raise argparse.ArgumentTypeError("must be a positive integer")
    return parsed


def jobs_from_environment(parser):
    for name in (CROSSGL_PACKAGE_REPRODUCIBILITY_JOBS, CROSSGL_CI_JOBS):
        value = os.environ.get(name)
        if value is None or not value.strip():
            continue
        try:
            return positive_int(value)
        except argparse.ArgumentTypeError:
            parser.error(f"{name} must be a positive integer")
    return 1


def parse_args(argv):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path)
    parser.add_argument("--cglc", type=Path)
    parser.add_argument(
        "--jobs",
        type=positive_int,
        help=(
            "run independent build/setup pairs in parallel; defaults to "
            f"${CROSSGL_PACKAGE_REPRODUCIBILITY_JOBS}, then ${CROSSGL_CI_JOBS}, "
            "then 1"
        ),
    )
    parser.add_argument(
        "--report",
        type=Path,
        help="write deterministic package metadata reproducibility report JSON",
    )
    parser.add_argument(
        "--self-test",
        action="store_true",
        help="run checker self-tests without invoking cglc",
    )
    args = parser.parse_args(argv)
    if args.jobs is None:
        args.jobs = jobs_from_environment(parser)
    if not args.self_test:
        if args.root is None:
            parser.error("--root is required unless --self-test is used")
        if args.cglc is None:
            parser.error("--cglc is required unless --self-test is used")
    return args


def main(argv=None):
    args = parse_args(argv or sys.argv[1:])
    if args.self_test:
        try:
            run_self_test()
        except AssertionError as exc:
            print(f"package reproducibility self-test failed: {exc}", file=sys.stderr)
            return 1
        print("validated package reproducibility checker self-test")
        return 0

    root = args.root.resolve()
    cglc = args.cglc.resolve()
    if not (root / FIXTURE).is_file():
        print(f"missing fixture: {root / FIXTURE}", file=sys.stderr)
        return 2
    if not cglc.is_file():
        print(f"missing cglc executable: {cglc}", file=sys.stderr)
        return 2

    with tempfile.TemporaryDirectory(prefix="crossgl-package-repro-") as tmp:
        tmp_dir = Path(tmp)
        try:
            source_pairs = run_fixture_tasks(
                build_specs(),
                lambda spec: build_case_pair(root, cglc, tmp_dir, spec),
                jobs=args.jobs,
            )
            native_pairs = run_fixture_tasks(
                REQUIRED_NATIVE_FIXTURE_TARGETS,
                lambda target: native_fixture_case_pair(root, cglc, tmp_dir, target),
                jobs=args.jobs,
            )
        except (json.JSONDecodeError, OSError, RuntimeError, ValueError) as exc:
            print(f"package reproducibility check failed: {exc}", file=sys.stderr)
            return 1

        errors = []
        build_root = cglc.parent.resolve()
        for first, second in source_pairs:
            forbidden = [
                tmp_dir,
                first["outputRoot"],
                second["outputRoot"],
                first["package"],
                second["package"],
                build_root,
                root,
            ]
            errors.extend(compare_cases(first, second))
            assert_case_path_contracts(errors, first, forbidden)
            assert_case_path_contracts(errors, second, forbidden)
        for first, second in native_pairs:
            forbidden = [
                tmp_dir,
                first["outputRoot"],
                second["outputRoot"],
                first["package"],
                second["package"],
                build_root,
                root,
            ]
            errors.extend(compare_native_fixture_cases(first, second))
            assert_native_fixture_path_contracts(errors, first, forbidden)
            assert_native_fixture_path_contracts(errors, second, forbidden)

        summary = toolchain_summary(root, cglc)
        report = report_document(source_pairs, native_pairs, summary)
        assert_report_document_contract(
            errors, report, source_pairs, native_pairs, summary
        )

        if errors:
            for error in errors:
                print(f"package reproducibility check failed: {error}", file=sys.stderr)
            return 1

        if args.report is not None:
            args.report.parent.mkdir(parents=True, exist_ok=True)
            args.report.write_text(
                canonical_json(report),
                encoding="utf-8",
            )

    labels = ", ".join(
        [spec.label for spec in build_specs()]
        + [f"{target}-native-fixture" for target in REQUIRED_NATIVE_FIXTURE_TARGETS]
    )
    print(f"validated reproducible package metadata for {FIXTURE.as_posix()}: {labels}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
