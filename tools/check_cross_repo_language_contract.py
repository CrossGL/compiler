#!/usr/bin/env python3
"""Validate the CrossGL language contract shared by Translator and Compiler."""

import argparse
import hashlib
import json
import os
import subprocess
import sys
import tempfile
from contextlib import redirect_stderr, redirect_stdout
from enum import Enum
from io import StringIO
from pathlib import Path

from validate_json_schema import (
    SchemaError,
    load_json as load_json_schema,
    validate as validate_json_schema,
)
from json_schema_semantics import validate_semantics as validate_json_semantics


SKIPPED_AST_ATTRIBUTES = {"annotations", "parent", "source_location"}
TRANSLATOR_EXAMPLE_EXCLUSIONS = {
    "examples/advanced/GenericPatternMatching.cgl": (
        "frontends currently accept this by skipping generic/trait/match syntax"
    ),
    "examples/cross_platform/UniversalPBRShader.cgl": (
        "raw switch fallback compatibility is covered by compiler unit tests"
    ),
}
COMPILER_FIXTURE_EXCLUSIONS = {
    "tests/fixtures/RuntimeArrayNestedShader.cgl": (
        "invalid storage-buffer runtime-array shape covered by negative tests"
    ),
    "tests/fixtures/RuntimeArrayNonFinalShader.cgl": (
        "invalid storage-buffer runtime-array shape covered by negative tests"
    ),
}
HASH_FIELDS = ("source_sha256", "translator_ast_sha256", "compiler_hir_sha256")
FEATURE_SPEC_SCHEMA = 1
FEATURE_SPEC_KIND = "crossgl-crosstl-shared-feature-spec"
LANGUAGE_SPEC_ID = "crosstl-frontend-language-spec-v0"
LANGUAGE_SPEC_KIND = "crosstl-frontend-language-spec-snapshot"
LANGUAGE_SPEC_AUTHORITY_MODE = "crosstl-frontend-derived-v0"
LANGUAGE_SPEC_CANONICAL_UNTIL = "shared-spec-package"
LANGUAGE_SPEC_SOURCE_REPOSITORY = "CrossGL-Translator"
LANGUAGE_SPEC_SOURCE_FRONTEND = "crosstl.translator"
LANGUAGE_SPEC_EXTRACTION_TOOL = "python -m crosstl.translator.language_spec"
LANGUAGE_SPEC_AUTHORITY_REFERENCES = (
    {
        "id": "authority.pr720-merged-reference",
        "kind": "merged-pr",
        "repository": "CrossGL/crosstl",
        "url": "https://github.com/CrossGL/crosstl/pull/720",
        "state": "MERGED",
        "headCommit": "19557a4b4e6ccca55622e819c795963d7f3a0a59",
        "languageAuthorityImpact": "no-sealed-source-drift",
    },
    {
        "id": "authority.pr724-project-porting-reference",
        "kind": "merged-pr",
        "repository": "CrossGL/crosstl",
        "url": "https://github.com/CrossGL/crosstl/pull/724",
        "state": "MERGED",
        "headCommit": "ffc1d88519589a7b11c45a18a9c3cac9bddb0604",
        "languageAuthorityImpact": "project-porting-source-remap-contract",
    },
)
LANGUAGE_SPEC_SOURCE_FILES = (
    "crosstl/translator/lexer.py",
    "crosstl/translator/parser.py",
    "crosstl/translator/ast.py",
    "crosstl/translator/validation.py",
)
LANGUAGE_SPEC_JSON_SCHEMA_PATH = Path(
    "docs/schemas/crosstl-frontend-language-spec-v0.schema.json"
)
FEATURE_SPEC_JSON_SCHEMA_PATH = Path(
    "docs/schemas/cross-repo-language-spec-v1.schema.json"
)
FEATURE_SPEC_SELF_TEST_FILES = (
    "tools/cross_repo_language_contract.json",
    "tools/cross_repo_language_spec.json",
    "docs/language/crosstl-frontend-language-spec-v0.json",
    LANGUAGE_SPEC_JSON_SCHEMA_PATH.as_posix(),
    FEATURE_SPEC_JSON_SCHEMA_PATH.as_posix(),
)
PROJECT_PORTING_CONTRACT_SEALS = (
    {
        "path": "docs/schemas/crosstl-project-portability-report-v1.schema.json",
        "sha256": "5bdc77ec1e4de7b80919a6dbdb06e78b3d14fc6dab6c77adb5ae75cab13668df",
    },
    {
        "path": "docs/schemas/source-remap-v1.schema.json",
        "sha256": "b17bf00d269f610906c186abd5b99986ecb441b5ecc89573bfcca1771bfae114",
    },
    {
        "path": "tests/fixtures/crosstl-project-portability-report-v1-pr747-demo.json",
        "sha256": "347c46a31b22ce5028a7bda595ef453a4cb22fdb6ba2cb90110b90aff4e0ef06",
    },
    {
        "path": (
            "tests/fixtures/"
            "crosstl-project-portability-report-v1-source-remap-metadata.json"
        ),
        "sha256": "4b9d3f90360d024b44468242081c48d4832aaa9b59a0bc86080117317fcde6b8",
    },
    {
        "path": (
            "tests/fixtures/"
            "crosstl-project-portability-report-v1-non-cgl-source-remap.json"
        ),
        "sha256": "37e3d8c25e3ff5132ddd92b315ce588202b4c6f1df1ca25b61cb3ccadb673dfa",
    },
    {
        "path": "tests/fixtures/source-remap-v1-crosstl-project-line.json",
        "sha256": "eb7d2b50594a5705cafaf2cf88eccd18975b597eb9e216caea824c63bea9ec92",
    },
    {
        "path": "tests/fixtures/source-remap-v1-crosstl-project-directx-line.json",
        "sha256": "6024fb5f723fb243cd8b261eadda888f68217c8d7436b6c2f163de81b188995a",
    },
    {
        "path": "tests/fixtures/source-remap-v1-crosstl-project-file.json",
        "sha256": "4407a5c48b300fddf048c5b20c1a3527518da4ffdc7caa9eea0457e6ef1036b9",
    },
    {
        "path": "tests/fixtures/source-remap-v1-crosstl-pr747-demo.json",
        "sha256": "757503b78f7d946c9c46c93046a2e7e6f58b4ae955c6ebc5bce80e256be6c233",
    },
)
PROJECT_PORTING_CONTRACT_FILES = tuple(
    seal["path"] for seal in PROJECT_PORTING_CONTRACT_SEALS
)
FEATURE_SPEC_SELF_TEST_FILES = (
    FEATURE_SPEC_SELF_TEST_FILES + PROJECT_PORTING_CONTRACT_FILES
)
NATIVE_V0_OWNER_BUCKETS = (
    "compat.language-unsupported-native-v0",
    "compat.frontend-unsupported-native-v0",
    "compat.target-legalization-unsupported",
)
NATIVE_V0_OWNER_BUCKETS_BY_CLASSIFICATION = {
    "spec.unsupported-for-native-v0": {
        "compat.language-unsupported-native-v0",
        "compat.frontend-unsupported-native-v0",
    },
    "target.unsupported": {"compat.target-legalization-unsupported"},
}


def normalize_text(text):
    return text.replace("\r\n", "\n").replace("\r", "\n")


def sha256_text(text):
    return hashlib.sha256(normalize_text(text).encode("utf-8")).hexdigest()


def canonical_json_sha256(value):
    canonical = json.dumps(value, sort_keys=True, separators=(",", ":"))
    return sha256_text(canonical)


def command_preview(args):
    return " ".join(str(arg) for arg in args)


def resolve_root(path):
    return Path(path).expanduser().resolve()


def relative_message_path(root, path):
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return str(path)


def validate_json_document_schema(document, schema_path, root, document_path):
    try:
        schema = load_json_schema(schema_path)
    except (OSError, json.JSONDecodeError) as exc:
        return [
            "could not load JSON schema {}: {}".format(
                relative_message_path(root, schema_path), exc
            )
        ]

    try:
        validate_json_schema(document, schema, schema)
    except SchemaError as exc:
        return [
            "{} failed structural schema validation against {}: {}".format(
                relative_message_path(root, document_path),
                relative_message_path(root, schema_path),
                exc,
            )
        ]
    return []


def validate_json_document_contract(document, schema_path, root, document_path):
    errors = validate_json_document_schema(document, schema_path, root, document_path)
    if errors:
        return errors

    schema = load_json_schema(schema_path)
    semantic_errors = validate_json_semantics(document, schema)
    return [
        "{} failed semantic validation against {}: {}".format(
            relative_message_path(root, document_path),
            relative_message_path(root, schema_path),
            error,
        )
        for error in semantic_errors
    ]


def validate_project_porting_contract_files(compiler_root):
    errors = []
    seen_paths = set()
    for seal in PROJECT_PORTING_CONTRACT_SEALS:
        relative = seal["path"]
        if relative in seen_paths:
            errors.append(
                "project-porting source-remap contract lists {} more than once".format(
                    relative
                )
            )
            continue
        seen_paths.add(relative)

        path = compiler_root / relative
        try:
            text = path.read_text(encoding="utf-8")
        except OSError as exc:
            errors.append(
                "project-porting source-remap contract file {} is unavailable: {}".format(
                    relative, exc
                )
            )
            continue
        actual_sha256 = sha256_text(text)
        if actual_sha256 != seal["sha256"]:
            errors.append(
                "project-porting source-remap contract file {} sha256 changed\n"
                "  expected: {}\n"
                "  actual:   {}".format(relative, seal["sha256"], actual_sha256)
            )

    project_report_schema = (
        compiler_root / "docs/schemas/crosstl-project-portability-report-v1.schema.json"
    )
    source_remap_schema = compiler_root / "docs/schemas/source-remap-v1.schema.json"
    fixture_schemas = (
        (
            "tests/fixtures/crosstl-project-portability-report-v1-pr747-demo.json",
            project_report_schema,
        ),
        (
            "tests/fixtures/"
            "crosstl-project-portability-report-v1-source-remap-metadata.json",
            project_report_schema,
        ),
        (
            "tests/fixtures/"
            "crosstl-project-portability-report-v1-non-cgl-source-remap.json",
            project_report_schema,
        ),
        (
            "tests/fixtures/source-remap-v1-crosstl-project-line.json",
            source_remap_schema,
        ),
        (
            "tests/fixtures/source-remap-v1-crosstl-project-directx-line.json",
            source_remap_schema,
        ),
        (
            "tests/fixtures/source-remap-v1-crosstl-project-file.json",
            source_remap_schema,
        ),
        (
            "tests/fixtures/source-remap-v1-crosstl-pr747-demo.json",
            source_remap_schema,
        ),
    )
    for relative, schema_path in fixture_schemas:
        document_path = compiler_root / relative
        try:
            document = json.loads(document_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            errors.append(
                "could not load project-porting contract fixture {}: {}".format(
                    relative, exc
                )
            )
            continue
        errors.extend(
            validate_json_document_contract(
                document, schema_path, compiler_root, document_path
            )
        )

    return errors


def contract_id(prefix, root, path):
    return prefix + "/" + path.resolve().relative_to(root.resolve()).as_posix()


def relative_contract_path(root, path):
    return path.resolve().relative_to(root.resolve()).as_posix()


def git_tracked_files(root, pathspecs):
    command = ["git", "ls-files", "--"] + list(pathspecs)
    process = run_command(command, root)
    if process.returncode != 0:
        return []
    return [
        root / line.strip()
        for line in normalize_text(process.stdout).splitlines()
        if line.strip()
    ]


def git_untracked_files(root, pathspecs):
    command = ["git", "ls-files", "--others", "--exclude-standard", "--"] + list(
        pathspecs
    )
    process = run_command(command, root)
    if process.returncode != 0:
        return []
    return [
        root / line.strip()
        for line in normalize_text(process.stdout).splitlines()
        if line.strip()
    ]


def unique_paths(paths):
    by_resolved = {path.resolve(): path for path in paths}
    return [by_resolved[resolved] for resolved in sorted(by_resolved)]


def discover_contract_inputs(translator_root, compiler_root, include_exclusions=False):
    inputs = []
    exclusions = []

    compiler_pathspecs = [":(glob)tests/fixtures/*.cgl"]
    compiler_fixtures = unique_paths(
        git_tracked_files(compiler_root, compiler_pathspecs)
        + git_untracked_files(compiler_root, compiler_pathspecs)
    )
    if not compiler_fixtures:
        compiler_fixtures = sorted((compiler_root / "tests" / "fixtures").glob("*.cgl"))
    for path in sorted(compiler_fixtures):
        relative = relative_contract_path(compiler_root, path)
        if relative in COMPILER_FIXTURE_EXCLUSIONS:
            exclusions.append(
                {
                    "id": "compiler/" + relative,
                    "root": "compiler",
                    "path": relative,
                    "reason": COMPILER_FIXTURE_EXCLUSIONS[relative],
                }
            )
            continue
        inputs.append((contract_id("compiler", compiler_root, path), path))

    translator_examples = git_tracked_files(
        translator_root, [":(glob)examples/**/*.cgl"]
    )
    if not translator_examples:
        translator_examples = sorted((translator_root / "examples").glob("**/*.cgl"))
    for path in sorted(translator_examples):
        relative_parts = path.resolve().relative_to(translator_root.resolve()).parts
        relative = relative_contract_path(translator_root, path)
        if "output" in relative_parts:
            exclusions.append(
                {
                    "id": "translator/" + relative,
                    "root": "translator",
                    "path": relative,
                    "reason": "generated translator example output",
                }
            )
            continue
        if relative in TRANSLATOR_EXAMPLE_EXCLUSIONS:
            exclusions.append(
                {
                    "id": "translator/" + relative,
                    "root": "translator",
                    "path": relative,
                    "reason": TRANSLATOR_EXAMPLE_EXCLUSIONS[relative],
                }
            )
            continue
        inputs.append((contract_id("translator", translator_root, path), path))

    seen = set()
    deduped = []
    for item_id, path in inputs:
        resolved = str(path.resolve())
        if resolved in seen:
            continue
        seen.add(resolved)
        deduped.append((item_id, path))
    if include_exclusions:
        return deduped, exclusions
    return deduped


def find_cglc(compiler_root, explicit_path):
    names = ["cglc.exe", "cglc"] if os.name == "nt" else ["cglc", "cglc.exe"]
    configurations = ["Release", "RelWithDebInfo", "Debug", "MinSizeRel"]

    if explicit_path:
        explicit = Path(explicit_path).expanduser()
        candidates = [explicit]
        if explicit.suffix.lower() != ".exe":
            candidates.append(explicit.with_name(explicit.name + ".exe"))
        for candidate in candidates:
            if candidate.is_file():
                return candidate.resolve()
        return None

    output_roots = [
        compiler_root / "build",
        compiler_root / "build" / "tools" / "cglc",
        compiler_root / "out" / "build",
    ]
    candidates = []
    for name in names:
        candidates.extend(output_root / name for output_root in output_roots)
        for configuration in configurations:
            candidates.extend(
                output_root / configuration / name for output_root in output_roots
            )

    for candidate in candidates:
        if candidate.is_file():
            return candidate.resolve()
    return None


def run_command(args, cwd):
    return subprocess.run(
        [str(arg) for arg in args],
        cwd=str(cwd),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        encoding="utf-8",
        errors="replace",
    )


def summarize_process_failure(process, args):
    details = [
        "{} exited with {}".format(command_preview(args), process.returncode),
    ]
    for label, stream in (("stdout", process.stdout), ("stderr", process.stderr)):
        text = normalize_text(stream).strip()
        if text:
            lines = text.splitlines()
            details.append("{}:\n{}".format(label, "\n".join(lines[-20:])))
    return "\n".join(details)


def canonical_key(value):
    if isinstance(value, Enum):
        return "{}:{}".format(value.__class__.__name__, value.value)
    return repr(value)


def canonical_ast(value, seen=None):
    if seen is None:
        seen = set()

    if value is None or isinstance(value, (str, int, float, bool)):
        return value

    if isinstance(value, Enum):
        return {
            "enum": value.__class__.__name__,
            "value": value.value,
        }

    if isinstance(value, (list, tuple)):
        return [canonical_ast(item, seen) for item in value]

    if isinstance(value, dict):
        return {
            "dict": [
                [canonical_key(key), canonical_ast(value[key], seen)]
                for key in sorted(value.keys(), key=canonical_key)
            ]
        }

    if isinstance(value, set):
        return {
            "set": [
                canonical_ast(item, seen) for item in sorted(value, key=canonical_key)
            ]
        }

    if hasattr(value, "__dict__"):
        object_id = id(value)
        if object_id in seen:
            return {"ref": value.__class__.__name__}
        seen.add(object_id)
        try:
            attrs = {}
            for name, attr_value in sorted(value.__dict__.items()):
                if name in SKIPPED_AST_ATTRIBUTES:
                    continue
                attrs[name] = canonical_ast(attr_value, seen)
            return {
                "node": value.__class__.__name__,
                "attrs": attrs,
            }
        finally:
            seen.remove(object_id)

    return repr(value)


def translator_ast_hash(parse, source):
    stdout = StringIO()
    stderr = StringIO()
    with redirect_stdout(stdout), redirect_stderr(stderr):
        ast = parse(source)
    diagnostics = normalize_text(stdout.getvalue() + stderr.getvalue()).strip()
    if diagnostics:
        return None, diagnostics
    canonical = json.dumps(canonical_ast(ast), sort_keys=True, separators=(",", ":"))
    return sha256_text(canonical), None


def compiler_hir_hash(cglc, compiler_root, path):
    check_args = [cglc, "check", path]
    check_process = run_command(check_args, compiler_root)
    if check_process.returncode != 0:
        return None, summarize_process_failure(check_process, check_args)
    check_diagnostics = normalize_text(check_process.stderr).strip()
    if check_diagnostics:
        return None, "{} emitted diagnostics:\n{}".format(
            command_preview(check_args), check_diagnostics
        )

    dump_args = [cglc, "dump-ir", path, "--stage", "hir"]
    dump_process = run_command(dump_args, compiler_root)
    if dump_process.returncode != 0:
        return None, summarize_process_failure(dump_process, dump_args)
    dump_diagnostics = normalize_text(dump_process.stderr).strip()
    if dump_diagnostics:
        return None, "{} emitted diagnostics:\n{}".format(
            command_preview(dump_args), dump_diagnostics
        )

    hir = normalize_text(dump_process.stdout).strip()
    if not hir:
        return None, "{} produced an empty HIR dump".format(command_preview(dump_args))

    return sha256_text(hir + "\n"), None


def json_pointer_value(document, pointer):
    if pointer == "":
        return document
    if not isinstance(pointer, str) or not pointer.startswith("/"):
        raise ValueError("JSON pointer must start with '/': {}".format(pointer))

    current = document
    for raw_part in pointer.split("/")[1:]:
        part = raw_part.replace("~1", "/").replace("~0", "~")
        if isinstance(current, dict):
            if part not in current:
                raise KeyError(pointer)
            current = current[part]
        elif isinstance(current, list):
            try:
                index = int(part)
            except ValueError as exc:
                raise KeyError(pointer) from exc
            try:
                current = current[index]
            except IndexError as exc:
                raise KeyError(pointer) from exc
        else:
            raise KeyError(pointer)
    return current


def source_file_seals(spec_document):
    source = spec_document.get("source", {}) if isinstance(spec_document, dict) else {}
    files = source.get("files", []) if isinstance(source, dict) else []
    if not isinstance(files, list):
        return []
    seals = []
    for entry in files:
        if not isinstance(entry, dict):
            continue
        path = entry.get("path")
        sha256 = entry.get("sha256")
        if isinstance(path, str) and isinstance(sha256, str):
            seals.append({"path": path, "sha256": sha256})
    return seals


def language_authority_references(spec_document):
    source = spec_document.get("source", {}) if isinstance(spec_document, dict) else {}
    references = (
        source.get("authorityReferences", []) if isinstance(source, dict) else []
    )
    if not isinstance(references, list):
        return []
    return [dict(reference) for reference in references if isinstance(reference, dict)]


def expected_language_spec_authority(spec_document):
    return {
        "mode": LANGUAGE_SPEC_AUTHORITY_MODE,
        "canonical_until": LANGUAGE_SPEC_CANONICAL_UNTIL,
        "source_repository": LANGUAGE_SPEC_SOURCE_REPOSITORY,
        "source_frontend": LANGUAGE_SPEC_SOURCE_FRONTEND,
        "extraction_tool": LANGUAGE_SPEC_EXTRACTION_TOOL,
        "authority_references": [
            dict(reference) for reference in LANGUAGE_SPEC_AUTHORITY_REFERENCES
        ],
        "source_files": source_file_seals(spec_document),
    }


def validate_language_spec_authority(spec, spec_document, relative_path):
    errors = []

    if spec.get("id") != LANGUAGE_SPEC_ID:
        errors.append(
            "language_spec.id changed\n  expected: {}\n  actual:   {}".format(
                LANGUAGE_SPEC_ID, spec.get("id")
            )
        )
    if spec_document.get("kind") != LANGUAGE_SPEC_KIND:
        errors.append(
            "{} kind changed\n  expected: {}\n  actual:   {}".format(
                relative_path, LANGUAGE_SPEC_KIND, spec_document.get("kind")
            )
        )

    source = spec_document.get("source")
    if not isinstance(source, dict):
        errors.append("{} source must be an object".format(relative_path))
        return errors

    expected_source_scalars = {
        "repository": LANGUAGE_SPEC_SOURCE_REPOSITORY,
        "frontend": LANGUAGE_SPEC_SOURCE_FRONTEND,
    }
    for key, expected in expected_source_scalars.items():
        actual = source.get(key)
        if actual != expected:
            errors.append(
                "{} source.{} changed\n  expected: {}\n  actual:   {}".format(
                    relative_path, key, expected, actual
                )
            )

    actual_references = source.get("authorityReferences")
    expected_references = [
        dict(reference) for reference in LANGUAGE_SPEC_AUTHORITY_REFERENCES
    ]
    if actual_references != expected_references:
        errors.append(
            "{} source.authorityReferences changed\n  expected: {}\n  actual:   {}".format(
                relative_path, expected_references, actual_references
            )
        )

    extraction = source.get("extraction")
    if not isinstance(extraction, dict):
        errors.append("{} source.extraction must be an object".format(relative_path))
    elif extraction.get("tool") != LANGUAGE_SPEC_EXTRACTION_TOOL:
        errors.append(
            "{} source.extraction.tool changed\n  expected: {}\n  actual:   {}".format(
                relative_path,
                LANGUAGE_SPEC_EXTRACTION_TOOL,
                extraction.get("tool"),
            )
        )

    source_files = source_file_seals(spec_document)
    source_paths = [entry["path"] for entry in source_files]
    expected_paths = list(LANGUAGE_SPEC_SOURCE_FILES)
    if source_paths != expected_paths:
        errors.append(
            "{} source.files paths changed\n  expected: {}\n  actual:   {}".format(
                relative_path, expected_paths, source_paths
            )
        )

    authority = spec.get("source_authority")
    expected_authority = expected_language_spec_authority(spec_document)
    if not isinstance(authority, dict):
        errors.append("language_spec.source_authority must be an object")
        return errors

    expected_keys = set(expected_authority)
    for key in sorted(set(authority) - expected_keys):
        errors.append(
            "language_spec.source_authority has unexpected key {}".format(key)
        )
    for key, expected in expected_authority.items():
        actual = authority.get(key)
        if actual != expected:
            errors.append(
                "language_spec.source_authority.{} changed\n  expected: {}\n  actual:   {}".format(
                    key, expected, actual
                )
            )

    return errors


def check_language_spec_reference(manifest, compiler_root):
    spec = manifest.get("language_spec")
    if spec is None:
        return None, []
    if not isinstance(spec, dict):
        return None, ["language_spec must be an object"]

    errors = []
    relative_path = spec.get("path")
    if not isinstance(relative_path, str) or not relative_path:
        errors.append("language_spec.path must be a non-empty string")
        return None, errors

    spec_path = (compiler_root / relative_path).resolve()
    try:
        spec_text = spec_path.read_text(encoding="utf-8")
    except OSError as exc:
        errors.append("could not read language spec {}: {}".format(spec_path, exc))
        return None, errors

    expected_sha = spec.get("sha256")
    if expected_sha:
        actual_sha = sha256_text(spec_text)
        if actual_sha != expected_sha:
            errors.append(
                "{} sha256 changed\n  expected: {}\n  actual:   {}".format(
                    relative_path, expected_sha, actual_sha
                )
            )

    try:
        spec_document = json.loads(spec_text)
    except json.JSONDecodeError as exc:
        errors.append("could not parse language spec {}: {}".format(spec_path, exc))
        return None, errors

    schema_errors = validate_json_document_schema(
        spec_document,
        compiler_root / LANGUAGE_SPEC_JSON_SCHEMA_PATH,
        compiler_root,
        spec_path,
    )
    if schema_errors:
        errors.extend(schema_errors)
        return None, errors

    expected_schema_version = spec.get("schema_version")
    if (
        expected_schema_version is not None
        and spec_document.get("schemaVersion") != expected_schema_version
    ):
        errors.append(
            "{} schemaVersion changed\n  expected: {}\n  actual:   {}".format(
                relative_path,
                expected_schema_version,
                spec_document.get("schemaVersion"),
            )
        )

    errors.extend(validate_language_spec_authority(spec, spec_document, relative_path))

    return spec_document, errors


def validate_feature_groups(manifest, spec_document):
    errors = []
    contracts = manifest.get("contracts", {})
    groups = manifest.get("accepted_contracts", {})
    if groups is None:
        return errors
    if not isinstance(groups, dict):
        return ["accepted_contracts must be an object"]

    for group_name, group in sorted(groups.items()):
        if not isinstance(group, dict):
            errors.append(
                "{}: accepted_contracts group must be an object".format(group_name)
            )
            continue
        fixtures = group.get("fixtures")
        if not isinstance(fixtures, list) or not fixtures:
            errors.append("{}: fixtures must be a non-empty list".format(group_name))
            continue
        for fixture_id in fixtures:
            if fixture_id not in contracts:
                errors.append(
                    "{}: fixture {} is not present in contracts".format(
                        group_name, fixture_id
                    )
                )
        for pointer in group.get("spec_refs", []):
            if spec_document is None:
                errors.append(
                    "{}: spec ref {} has no loaded language_spec".format(
                        group_name, pointer
                    )
                )
                continue
            try:
                json_pointer_value(spec_document, pointer)
            except (KeyError, ValueError):
                errors.append(
                    "{}: spec ref {} does not resolve".format(group_name, pointer)
                )
    return errors


def string_list_field(case, field, case_id):
    value = case.get(field)
    if value is None:
        return None, []
    if not isinstance(value, list) or not value:
        return [], ["{}: {} must be a non-empty string list".format(case_id, field)]
    values = []
    errors = []
    for index, item in enumerate(value):
        if not isinstance(item, str) or not item:
            errors.append(
                "{}: {}[{}] must be a non-empty string".format(case_id, field, index)
            )
        else:
            values.append(item)
    return values, errors


def native_v0_owner_buckets(case):
    anchors = case.get("compatibility_anchors", [])
    if not isinstance(anchors, list):
        return []
    return [
        anchor
        for anchor in anchors
        if isinstance(anchor, str) and anchor in NATIVE_V0_OWNER_BUCKETS
    ]


def validate_negative_contract_anchors(manifest, spec_document, compiler_root):
    _ = compiler_root
    try:
        cases = list(iter_negative_contracts(manifest))
    except ValueError as exc:
        return [str(exc)]

    errors = []
    anchored_groups = set()

    for index, (group_name, case) in enumerate(cases, start=1):
        case_id = case.get("id") or "{}/{}".format(group_name, index)
        spec_refs, field_errors = string_list_field(case, "spec_refs", case_id)
        errors.extend(field_errors)

        if spec_refs:
            if spec_document is None:
                errors.append(
                    "{}: spec_refs require a loaded language_spec".format(case_id)
                )
            else:
                for pointer in spec_refs:
                    try:
                        json_pointer_value(spec_document, pointer)
                    except (KeyError, ValueError):
                        errors.append(
                            "{}: spec ref {} does not resolve".format(case_id, pointer)
                        )
            anchored_groups.add(group_name)

    groups = manifest.get("negative_contracts", {})
    if isinstance(groups, dict):
        for group_name, group in sorted(groups.items()):
            group_cases = group.get("cases", []) if isinstance(group, dict) else group
            if (
                isinstance(group_cases, list)
                and group_cases
                and group_name not in anchored_groups
            ):
                errors.append(
                    "negative_contracts.{} must include at least one case with "
                    "resolving spec_refs".format(group_name)
                )

    return errors


def contract_hashes_for_fixture(contracts, fixture_id):
    fixture = {"id": fixture_id}
    contract = contracts.get(fixture_id, {}) if isinstance(contracts, dict) else {}
    if isinstance(contract, dict):
        for field in HASH_FIELDS:
            value = contract.get(field)
            if isinstance(value, str):
                fixture[field] = value
    return fixture


def snapshot_ref_seals(spec_document, pointers):
    seals = []
    for pointer in pointers:
        if not isinstance(pointer, str):
            continue
        seal = {"ref": pointer}
        try:
            value = json_pointer_value(spec_document, pointer)
        except (KeyError, ValueError):
            seal["status"] = "unresolved"
        else:
            seal["sha256"] = canonical_json_sha256(value)
        seals.append(seal)
    return seals


def build_feature_group_specs(manifest, spec_document):
    contracts = manifest.get("contracts", {})
    groups = manifest.get("accepted_contracts", {})
    if not isinstance(groups, dict):
        return []

    feature_groups = []
    for group_name in sorted(groups):
        group = groups[group_name]
        if not isinstance(group, dict):
            continue
        fixture_ids = [
            fixture_id
            for fixture_id in group.get("fixtures", [])
            if isinstance(fixture_id, str)
        ]
        spec_refs = [
            pointer
            for pointer in group.get("spec_refs", [])
            if isinstance(pointer, str)
        ]
        feature_groups.append(
            {
                "id": group_name,
                "status": "accepted-source",
                "description": group.get("description", ""),
                "snapshot_refs": spec_refs,
                "snapshot_ref_seals": snapshot_ref_seals(spec_document, spec_refs),
                "fixture_count": len(fixture_ids),
                "fixtures": [
                    contract_hashes_for_fixture(contracts, fixture_id)
                    for fixture_id in fixture_ids
                ],
            }
        )
    return feature_groups


def compact_expectation(expectation):
    if not isinstance(expectation, dict):
        return {}

    compact = {}
    status = expectation.get("status")
    if isinstance(status, str):
        compact["status"] = status
    for source_key, output_key in (
        ("ast_sha256", "ast_sha256"),
        ("error_class", "error_class"),
    ):
        value = expectation.get(source_key)
        if isinstance(value, str):
            compact[output_key] = value
    substrings = expectation.get("diagnostic_substrings")
    if isinstance(substrings, list):
        compact["diagnostic_substrings"] = [
            item for item in substrings if isinstance(item, str)
        ]
    return compact


def build_negative_case_specs(manifest):
    cases = []
    try:
        negative_contracts = list(iter_negative_contracts(manifest))
    except ValueError:
        return cases

    for index, (group_name, case) in enumerate(negative_contracts, start=1):
        case_id = case.get("id") or "{}/{}".format(group_name, index)
        entry = {
            "id": case_id,
            "group": group_name,
        }
        for source_key, output_key in (
            ("classification", "classification"),
            ("feature", "feature_group"),
            ("reason", "reason"),
            ("root", "root"),
            ("path", "path"),
            ("source_sha256", "source_sha256"),
        ):
            value = case.get(source_key)
            if isinstance(value, str):
                entry[output_key] = value
        if "source" in case:
            entry["source_kind"] = "inline"
            source = case.get("source")
            if isinstance(source, str):
                entry["source_sha256"] = sha256_text(source)

        translator = compact_expectation(case.get("translator", {}))
        if translator:
            entry["translator"] = translator
        compiler = compact_expectation(case.get("compiler", {}))
        if compiler:
            entry["compiler"] = compiler
        owner_buckets = native_v0_owner_buckets(case)
        if len(owner_buckets) == 1:
            entry["native_v0_owner_bucket"] = owner_buckets[0]
        cases.append(entry)
    return cases


def build_cross_repo_language_feature_spec(manifest, spec_document):
    language_spec = manifest.get("language_spec", {})
    feature_spec = manifest.get("feature_spec", {})
    contracts = manifest.get("contracts", {})
    feature_groups = build_feature_group_specs(manifest, spec_document)
    negative_cases = build_negative_case_specs(manifest)

    return {
        "schemaVersion": FEATURE_SPEC_SCHEMA,
        "schema": FEATURE_SPEC_SCHEMA,
        "kind": FEATURE_SPEC_KIND,
        "description": (
            "Deterministic CrossTL/CrossGL shared feature spec extracted from "
            "the committed CrossTL frontend snapshot and cross-repo language "
            "contract manifest. It is a tooling/spec contract artifact only."
        ),
        "document": {
            "id": feature_spec.get("id"),
            "path": feature_spec.get("path"),
        },
        "source_language_snapshot": {
            "id": language_spec.get("id"),
            "path": language_spec.get("path"),
            "schema_version": language_spec.get("schema_version"),
            "sha256": language_spec.get("sha256"),
            "authority_references": language_authority_references(spec_document),
            "source_files": source_file_seals(spec_document),
        },
        "contract_manifest": {
            "path": "tools/cross_repo_language_contract.json",
            "schema": manifest.get("schema"),
            "contract_count": len(contracts) if isinstance(contracts, dict) else 0,
            "accepted_feature_group_count": len(feature_groups),
            "negative_case_count": len(negative_cases),
            "hash_fields": list(HASH_FIELDS),
        },
        "feature_groups": feature_groups,
        "negative_cases": negative_cases,
    }


def feature_spec_ids(document, key):
    entries = document.get(key, []) if isinstance(document, dict) else []
    if not isinstance(entries, list):
        return []
    ids = []
    for entry in entries:
        if isinstance(entry, dict) and isinstance(entry.get("id"), str):
            ids.append(entry["id"])
    return ids


def entries_by_id(document, key):
    entries = document.get(key, []) if isinstance(document, dict) else []
    if not isinstance(entries, list):
        return {}
    return {
        entry["id"]: entry
        for entry in entries
        if isinstance(entry, dict) and isinstance(entry.get("id"), str)
    }


def project_mapping(value, keys, projectors=None):
    if not isinstance(value, dict):
        return value
    projectors = projectors or {}
    projected = {}
    for key in keys:
        if key not in value:
            continue
        projector = projectors.get(key)
        projected[key] = projector(value[key]) if projector else value[key]
    return projected


def project_list(value, projector):
    if not isinstance(value, list):
        return value
    return [projector(item) for item in value]


def project_document(value):
    return project_mapping(value, ("id", "path"))


def project_authority_reference(value):
    return project_mapping(
        value,
        (
            "id",
            "kind",
            "repository",
            "url",
            "state",
            "headCommit",
            "languageAuthorityImpact",
        ),
    )


def project_source_file(value):
    return project_mapping(value, ("path", "sha256"))


def project_source_language_snapshot(value):
    return project_mapping(
        value,
        (
            "id",
            "path",
            "schema_version",
            "sha256",
            "authority_references",
            "source_files",
        ),
        {
            "authority_references": lambda items: project_list(
                items, project_authority_reference
            ),
            "source_files": lambda items: project_list(items, project_source_file),
        },
    )


def project_contract_manifest(value):
    return project_mapping(
        value,
        (
            "path",
            "schema",
            "contract_count",
            "accepted_feature_group_count",
            "negative_case_count",
            "hash_fields",
        ),
    )


def project_snapshot_ref_seal(value):
    return project_mapping(value, ("ref", "sha256"))


def project_fixture_hash(value):
    return project_mapping(
        value,
        ("id", "source_sha256", "translator_ast_sha256", "compiler_hir_sha256"),
    )


def project_feature_group(value):
    return project_mapping(
        value,
        (
            "id",
            "status",
            "description",
            "snapshot_refs",
            "snapshot_ref_seals",
            "fixture_count",
            "fixtures",
        ),
        {
            "snapshot_ref_seals": lambda items: project_list(
                items, project_snapshot_ref_seal
            ),
            "fixtures": lambda items: project_list(items, project_fixture_hash),
        },
    )


def project_translator_expectation(value):
    return project_mapping(
        value,
        ("status", "ast_sha256", "error_class", "diagnostic_substrings"),
    )


def project_compiler_expectation(value):
    return project_mapping(value, ("status", "diagnostic_substrings"))


def project_negative_case(value):
    return project_mapping(
        value,
        (
            "id",
            "group",
            "classification",
            "feature_group",
            "reason",
            "root",
            "path",
            "source_sha256",
            "native_v0_owner_bucket",
            "translator",
            "compiler",
        ),
        {
            "translator": project_translator_expectation,
            "compiler": project_compiler_expectation,
        },
    )


def project_cross_repo_language_feature_spec(value):
    return project_mapping(
        value,
        (
            "schemaVersion",
            "schema",
            "kind",
            "description",
            "document",
            "source_language_snapshot",
            "contract_manifest",
            "feature_groups",
            "negative_cases",
        ),
        {
            "document": project_document,
            "source_language_snapshot": project_source_language_snapshot,
            "contract_manifest": project_contract_manifest,
            "feature_groups": lambda items: project_list(items, project_feature_group),
            "negative_cases": lambda items: project_list(items, project_negative_case),
        },
    )


def json_pointer_escape(part):
    return str(part).replace("~", "~0").replace("/", "~1")


def json_pointer(parts):
    if not parts:
        return "/"
    return "/" + "/".join(json_pointer_escape(part) for part in parts)


def compact_json(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


def append_json_projection_diffs(expected, actual, path_parts, diffs, limit):
    if len(diffs) >= limit:
        return
    if type(expected) is not type(actual):
        diffs.append(
            "shared spec drift at {}\n  expected: {}\n  actual:   {}".format(
                json_pointer(path_parts), compact_json(expected), compact_json(actual)
            )
        )
        return
    if isinstance(expected, dict):
        expected_keys = list(expected.keys())
        for key in expected_keys:
            if len(diffs) >= limit:
                return
            if key not in actual:
                diffs.append(
                    "shared spec drift at {}\n  expected: {}\n  actual:   <missing>".format(
                        json_pointer(path_parts + [key]), compact_json(expected[key])
                    )
                )
                continue
            append_json_projection_diffs(
                expected[key], actual[key], path_parts + [key], diffs, limit
            )
        for key in sorted(set(actual) - set(expected)):
            if len(diffs) >= limit:
                return
            diffs.append(
                "shared spec drift at {}\n  expected: <missing>\n  actual:   {}".format(
                    json_pointer(path_parts + [key]), compact_json(actual[key])
                )
            )
        return
    if isinstance(expected, list):
        if len(expected) != len(actual):
            diffs.append(
                "shared spec drift at {}\n  expected length: {}\n  actual length:   {}".format(
                    json_pointer(path_parts), len(expected), len(actual)
                )
            )
            if len(diffs) >= limit:
                return
        for index, (expected_item, actual_item) in enumerate(zip(expected, actual)):
            if len(diffs) >= limit:
                return
            append_json_projection_diffs(
                expected_item, actual_item, path_parts + [index], diffs, limit
            )
        return
    if expected != actual:
        diffs.append(
            "shared spec drift at {}\n  expected: {}\n  actual:   {}".format(
                json_pointer(path_parts), compact_json(expected), compact_json(actual)
            )
        )


def describe_shared_feature_spec_projection_drift(relative_path, expected, actual):
    errors = [
        "{} does not match the compiler-generated CrossTL shared feature spec "
        "projection".format(relative_path)
    ]
    diffs = []
    append_json_projection_diffs(expected, actual, [], diffs, limit=12)
    errors.extend(diffs)
    if len(diffs) >= 12:
        errors.append(
            "{}: drift output truncated after {} differences".format(
                relative_path, len(diffs)
            )
        )
    errors.append(
        "This import check ignores unknown optional fields, but known v1 fields "
        "must match the committed CrossTL snapshot and contract manifest. "
        "Regenerate only after the shared language contract source of truth lands."
    )
    return errors


def describe_feature_spec_drift(relative_path, expected, actual):
    errors = [
        "{} is out of date with the CrossTL snapshot or cross-repo language "
        "contract manifest".format(relative_path)
    ]

    for key in ("schema", "kind", "document", "source_language_snapshot"):
        if actual.get(key) != expected.get(key):
            errors.append(
                "{} {} changed\n  expected: {}\n  actual:   {}".format(
                    relative_path, key, expected.get(key), actual.get(key)
                )
            )
    if actual.get("contract_manifest") != expected.get("contract_manifest"):
        errors.append(
            "{} contract_manifest summary changed\n  expected: {}\n  actual:   {}".format(
                relative_path,
                expected.get("contract_manifest"),
                actual.get("contract_manifest"),
            )
        )

    for key, label in (
        ("feature_groups", "feature group"),
        ("negative_cases", "negative case"),
    ):
        expected_ids = feature_spec_ids(expected, key)
        actual_ids = feature_spec_ids(actual, key)
        if actual_ids != expected_ids:
            errors.append(
                "{} {} ids changed\n  expected: {}\n  actual:   {}".format(
                    relative_path, label, expected_ids, actual_ids
                )
            )
            continue

        expected_by_id = entries_by_id(expected, key)
        actual_by_id = entries_by_id(actual, key)
        changed = [
            entry_id
            for entry_id in expected_ids
            if actual_by_id.get(entry_id) != expected_by_id.get(entry_id)
        ]
        for entry_id in changed[:5]:
            errors.append("{} {} {} changed".format(relative_path, label, entry_id))
        if len(changed) > 5:
            errors.append(
                "{}: {} additional {} entries changed".format(
                    relative_path, len(changed) - 5, label
                )
            )

    errors.append(
        "Regenerate after an intentional shared language contract change with "
        "tools/check_cross_repo_language_contract.py --update-feature-spec."
    )
    return errors


def validate_cross_repo_language_feature_spec(
    manifest, compiler_root, spec_document, require_feature_spec=False
):
    feature_spec = manifest.get("feature_spec")
    if feature_spec is None:
        if require_feature_spec:
            return ["feature_spec must be an object"]
        return []
    if not isinstance(feature_spec, dict):
        return ["feature_spec must be an object"]

    errors = []
    relative_path = feature_spec.get("path")
    if not isinstance(relative_path, str) or not relative_path:
        errors.append("feature_spec.path must be a non-empty string")
        return errors
    expected_schema = feature_spec.get("schema")
    if expected_schema != FEATURE_SPEC_SCHEMA:
        errors.append(
            "feature_spec.schema changed\n  expected: {}\n  actual:   {}".format(
                FEATURE_SPEC_SCHEMA, expected_schema
            )
        )
    expected_kind = feature_spec.get("kind")
    if expected_kind != FEATURE_SPEC_KIND:
        errors.append(
            "feature_spec.kind changed\n  expected: {}\n  actual:   {}".format(
                FEATURE_SPEC_KIND, expected_kind
            )
        )

    path = (compiler_root / relative_path).resolve()
    try:
        actual = json.loads(path.read_text(encoding="utf-8"))
    except OSError as exc:
        errors.append("could not read feature spec {}: {}".format(path, exc))
        return errors
    except json.JSONDecodeError as exc:
        errors.append("could not parse feature spec {}: {}".format(path, exc))
        return errors
    if not isinstance(actual, dict):
        errors.append("{} must contain a JSON object".format(relative_path))
        return errors

    schema_errors = validate_json_document_schema(
        actual,
        compiler_root / FEATURE_SPEC_JSON_SCHEMA_PATH,
        compiler_root,
        path,
    )
    if schema_errors:
        errors.extend(schema_errors)
        return errors

    expected = build_cross_repo_language_feature_spec(manifest, spec_document)
    if actual != expected:
        errors.extend(describe_feature_spec_drift(relative_path, expected, actual))
    return errors


def validate_imported_shared_language_spec(
    manifest, compiler_root, spec_document, shared_spec_path
):
    try:
        actual = json.loads(shared_spec_path.read_text(encoding="utf-8"))
    except OSError as exc:
        return [
            "could not read shared CrossTL language spec {}: {}".format(
                shared_spec_path, exc
            )
        ]
    except json.JSONDecodeError as exc:
        return [
            "could not parse shared CrossTL language spec {}: {}".format(
                shared_spec_path, exc
            )
        ]
    if not isinstance(actual, dict):
        return [
            "shared CrossTL language spec {} must contain a JSON object".format(
                shared_spec_path
            )
        ]

    expected = project_cross_repo_language_feature_spec(
        build_cross_repo_language_feature_spec(manifest, spec_document)
    )
    actual_projection = project_cross_repo_language_feature_spec(actual)
    if actual_projection != expected:
        return describe_shared_feature_spec_projection_drift(
            relative_message_path(compiler_root, shared_spec_path),
            expected,
            actual_projection,
        )
    return []


def write_cross_repo_language_feature_spec(manifest, compiler_root, spec_document):
    feature_spec = manifest.get("feature_spec")
    if not isinstance(feature_spec, dict):
        raise ValueError("feature_spec must be an object")
    relative_path = feature_spec.get("path")
    if not isinstance(relative_path, str) or not relative_path:
        raise ValueError("feature_spec.path must be a non-empty string")

    path = (compiler_root / relative_path).resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    document = build_cross_repo_language_feature_spec(manifest, spec_document)
    schema_errors = validate_json_document_schema(
        document,
        compiler_root / FEATURE_SPEC_JSON_SCHEMA_PATH,
        compiler_root,
        path,
    )
    if schema_errors:
        raise ValueError("; ".join(schema_errors))
    path.write_text(json.dumps(document, indent=2) + "\n", encoding="utf-8")
    return path


def iter_negative_contracts(manifest):
    groups = manifest.get("negative_contracts", {})
    if groups is None:
        return
    if not isinstance(groups, dict):
        raise ValueError("negative_contracts must be an object")

    for group_name, group in sorted(groups.items()):
        if isinstance(group, list):
            cases = group
        elif isinstance(group, dict):
            cases = group.get("cases", [])
        else:
            raise ValueError(
                "negative_contracts.{} must be an object or list".format(group_name)
            )
        if not isinstance(cases, list):
            raise ValueError(
                "negative_contracts.{}.cases must be a list".format(group_name)
            )
        for case in cases:
            if not isinstance(case, dict):
                raise ValueError(
                    "negative_contracts.{} contains a non-object case".format(
                        group_name
                    )
                )
            yield group_name, case


def negative_case_source(case, translator_root, compiler_root):
    if "source" in case:
        source = case["source"]
        if not isinstance(source, str):
            raise ValueError("{}: source must be a string".format(case.get("id")))
        return source, None

    relative_path = case.get("path")
    if not isinstance(relative_path, str) or not relative_path:
        raise ValueError("{}: path or source is required".format(case.get("id")))

    root_name = case.get("root", "compiler")
    if root_name == "compiler":
        root = compiler_root
    elif root_name == "translator":
        root = translator_root
    else:
        raise ValueError("{}: unknown root {}".format(case.get("id"), root_name))

    path = (root / relative_path).resolve()
    try:
        return path.read_text(encoding="utf-8"), path
    except OSError as exc:
        raise ValueError("{}: could not read {}: {}".format(case.get("id"), path, exc))


def diagnostic_text_from_exception(exc):
    return "{}: {}".format(exc.__class__.__name__, exc)


def validate_translator_negative_case(parse, case_id, case, source):
    expected = case.get("translator", {})
    if not isinstance(expected, dict):
        return ["{}: translator expectation must be an object".format(case_id)]

    status = expected.get("status")
    if status not in {"accepts", "rejects"}:
        return ["{}: translator.status must be 'accepts' or 'rejects'".format(case_id)]

    failures = []
    source_hash = sha256_text(source)
    expected_source_hash = case.get("source_sha256")
    if expected_source_hash and expected_source_hash != source_hash:
        failures.append(
            "{}: source_sha256 changed\n  expected: {}\n  actual:   {}".format(
                case_id, expected_source_hash, source_hash
            )
        )

    try:
        ast_hash, diagnostics = translator_ast_hash(parse, source)
    except Exception as exc:
        actual_status = "rejects"
        actual_diagnostic = diagnostic_text_from_exception(exc)
        ast_hash = None
    else:
        if diagnostics:
            actual_status = "rejects"
            actual_diagnostic = diagnostics
        else:
            actual_status = "accepts"
            actual_diagnostic = ""

    if actual_status != status:
        failures.append(
            "{}: translator {} but expected {}".format(case_id, actual_status, status)
        )
        if actual_diagnostic:
            failures.append(
                "{}: translator diagnostic:\n{}".format(case_id, actual_diagnostic)
            )
        return failures

    if status == "accepts":
        expected_hash = expected.get("ast_sha256")
        if expected_hash and expected_hash != ast_hash:
            failures.append(
                "{}: translator_ast_sha256 changed\n  expected: {}\n  actual:   {}".format(
                    case_id, expected_hash, ast_hash
                )
            )
    else:
        expected_error = expected.get("error_class")
        if expected_error and not actual_diagnostic.startswith(expected_error + ":"):
            failures.append(
                "{}: translator error class changed\n  expected: {}\n  actual:   {}".format(
                    case_id, expected_error, actual_diagnostic
                )
            )
        for substring in expected.get("diagnostic_substrings", []):
            if substring not in actual_diagnostic:
                failures.append(
                    "{}: translator diagnostic is missing substring {!r}\n{}".format(
                        case_id, substring, actual_diagnostic
                    )
                )

    return failures


def run_compiler_check_for_negative_case(cglc, compiler_root, source, path):
    if path is not None:
        check_args = [cglc, "check", path]
        return run_command(check_args, compiler_root), check_args

    with tempfile.NamedTemporaryFile(
        "w", suffix=".cgl", encoding="utf-8", delete=False
    ) as handle:
        handle.write(source)
        temp_path = Path(handle.name)
    try:
        check_args = [cglc, "check", temp_path]
        return run_command(check_args, compiler_root), check_args
    finally:
        try:
            temp_path.unlink()
        except OSError:
            pass


def validate_compiler_negative_case(cglc, compiler_root, case_id, case, source, path):
    expected = case.get("compiler", {})
    if not isinstance(expected, dict):
        return ["{}: compiler expectation must be an object".format(case_id)]

    status = expected.get("status")
    if status not in {"accepts", "rejects"}:
        return ["{}: compiler.status must be 'accepts' or 'rejects'".format(case_id)]

    failures = []
    process, check_args = run_compiler_check_for_negative_case(
        cglc, compiler_root, source, path
    )
    actual_status = "accepts" if process.returncode == 0 else "rejects"
    if actual_status != status:
        failures.append(
            "{}: compiler {} but expected {}\n{}".format(
                case_id,
                actual_status,
                status,
                summarize_process_failure(process, check_args)
                if process.returncode != 0
                else command_preview(check_args),
            )
        )
        return failures

    diagnostics = normalize_text(process.stdout + process.stderr)
    for substring in expected.get("diagnostic_substrings", []):
        if substring not in diagnostics:
            failures.append(
                "{}: compiler diagnostic is missing substring {!r}\n{}".format(
                    case_id, substring, diagnostics.strip()
                )
            )

    return failures


def validate_negative_contracts(manifest, translator_root, compiler_root, cglc):
    sys.path.insert(0, str(translator_root))
    from crosstl.translator import parse

    failures = []
    count = 0
    for group_name, case in iter_negative_contracts(manifest):
        count += 1
        case_id = case.get("id") or "{}/{}".format(group_name, count)
        try:
            source, path = negative_case_source(case, translator_root, compiler_root)
        except ValueError as exc:
            failures.append(str(exc))
            continue

        failures.extend(validate_translator_negative_case(parse, case_id, case, source))
        failures.extend(
            validate_compiler_negative_case(
                cglc, compiler_root, case_id, case, source, path
            )
        )
    return count, failures


def refresh_negative_contract_hashes(manifest, translator_root, compiler_root):
    sys.path.insert(0, str(translator_root))
    from crosstl.translator import parse

    failures = []
    count = 0
    updated = 0
    for group_name, case in iter_negative_contracts(manifest):
        count += 1
        case_id = case.get("id") or "{}/{}".format(group_name, count)
        try:
            source, _path = negative_case_source(case, translator_root, compiler_root)
        except ValueError as exc:
            failures.append(str(exc))
            continue

        source_hash = sha256_text(source)
        if case.get("source_sha256") != source_hash:
            case["source_sha256"] = source_hash
            updated += 1

        expected = case.get("translator", {})
        if not isinstance(expected, dict):
            failures.append(
                "{}: translator expectation must be an object".format(case_id)
            )
            continue

        status = expected.get("status")
        if status == "accepts":
            try:
                ast_hash, diagnostics = translator_ast_hash(parse, source)
            except Exception as exc:
                failures.append(
                    "{}: translator rejects during hash refresh with {}: {}".format(
                        case_id, exc.__class__.__name__, exc
                    )
                )
                continue
            if diagnostics:
                failures.append(
                    "{}: translator emits diagnostics during hash refresh:\n{}".format(
                        case_id, diagnostics
                    )
                )
                continue
            if expected.get("ast_sha256") != ast_hash:
                expected["ast_sha256"] = ast_hash
                updated += 1
        elif status == "rejects":
            continue
        else:
            failures.append(
                "{}: translator.status must be 'accepts' or 'rejects'".format(case_id)
            )

    return count, updated, failures


def validate_manifest_metadata(manifest, compiler_root, require_feature_spec=False):
    spec_document, errors = check_language_spec_reference(manifest, compiler_root)
    errors.extend(validate_feature_groups(manifest, spec_document))
    errors.extend(
        validate_negative_contract_anchors(manifest, spec_document, compiler_root)
    )
    errors.extend(
        validate_cross_repo_language_feature_spec(
            manifest,
            compiler_root,
            spec_document,
            require_feature_spec=require_feature_spec,
        )
    )
    if require_feature_spec:
        errors.extend(validate_project_porting_contract_files(compiler_root))
    try:
        list(iter_negative_contracts(manifest))
    except ValueError as exc:
        errors.append(str(exc))
    return errors


def check_feature_spec_mode_errors(manifest, compiler_root):
    metadata_errors = validate_manifest_metadata(
        manifest, compiler_root, require_feature_spec=True
    )
    if metadata_errors:
        return "Cross-repo language contract manifest is invalid:", metadata_errors

    spec_document, feature_spec_errors = check_language_spec_reference(
        manifest, compiler_root
    )
    feature_spec_errors.extend(validate_feature_groups(manifest, spec_document))
    feature_spec_errors.extend(
        validate_negative_contract_anchors(manifest, spec_document, compiler_root)
    )
    if feature_spec_errors:
        return (
            "Cross-repo language feature spec inputs are invalid:",
            feature_spec_errors,
        )
    return None, []


def check_imported_shared_spec_errors(manifest, compiler_root, shared_spec_path):
    spec_document, input_errors = check_language_spec_reference(manifest, compiler_root)
    input_errors.extend(validate_feature_groups(manifest, spec_document))
    input_errors.extend(
        validate_negative_contract_anchors(manifest, spec_document, compiler_root)
    )
    try:
        list(iter_negative_contracts(manifest))
    except ValueError as exc:
        input_errors.append(str(exc))
    if input_errors:
        return "Cross-repo language feature spec inputs are invalid:", input_errors

    shared_errors = validate_imported_shared_language_spec(
        manifest, compiler_root, spec_document, shared_spec_path
    )
    if shared_errors:
        return "Imported shared CrossTL language spec drift detected:", shared_errors
    return None, []


def write_json_file(path, document):
    path.write_text(json.dumps(document, indent=2) + "\n", encoding="utf-8")


def copy_feature_spec_self_test_fixture(source_root, fixture_root):
    for relative in FEATURE_SPEC_SELF_TEST_FILES:
        source = source_root / relative
        destination = fixture_root / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(source.read_bytes())


def feature_spec_self_test_errors(fixture_root):
    manifest = load_manifest(
        fixture_root / "tools" / "cross_repo_language_contract.json"
    )
    _heading, errors = check_feature_spec_mode_errors(manifest, fixture_root)
    return errors


def mutate_self_test_language_spec_sha(fixture_root):
    path = fixture_root / "tools" / "cross_repo_language_contract.json"
    manifest = load_manifest(path)
    manifest["language_spec"]["sha256"] = "0" * 64
    write_json_file(path, manifest)


def mutate_self_test_source_authority_sha(fixture_root):
    path = fixture_root / "tools" / "cross_repo_language_contract.json"
    manifest = load_manifest(path)
    manifest["language_spec"]["source_authority"]["source_files"][0]["sha256"] = (
        "0" * 64
    )
    write_json_file(path, manifest)


def mutate_self_test_feature_spec_snapshot(fixture_root):
    path = fixture_root / "tools" / "cross_repo_language_spec.json"
    document = json.loads(path.read_text(encoding="utf-8"))
    document["source_language_snapshot"]["source_files"][0]["sha256"] = "0" * 64
    write_json_file(path, document)


def mutate_self_test_project_porting_fixture(fixture_root):
    path = fixture_root / "tests/fixtures/source-remap-v1-crosstl-project-line.json"
    document = json.loads(path.read_text(encoding="utf-8"))
    document["mappings"][0]["generated"]["length"] += 1
    write_json_file(path, document)


def mutate_self_test_imported_spec_future_fields(fixture_root):
    path = fixture_root / "tools" / "cross_repo_language_spec.json"
    document = json.loads(path.read_text(encoding="utf-8"))
    document["preprocessor"] = {
        "include_paths": [],
        "defines": {},
        "conditional_blocks": {"supported": True},
    }
    document["source_registry"] = {
        "include_paths": [],
        "defines": [],
        "provenance_schema": "crossgl-crosstl-provenance-v1",
    }
    document["opencl_frontend"] = {
        "extension_registry": ["cl_khr_fp16"],
        "unsupported_binary_artifact_diagnostics": True,
    }
    document["source_language_snapshot"]["report_schemas"] = [
        "crosstl-preprocessor-report-v1",
        "crosstl-source-provenance-v1",
    ]
    if document.get("feature_groups"):
        document["feature_groups"][0]["future_fields"] = {
            "statement_attributes": True,
            "threadgroup_imageblock": True,
            "array_suffix_declarators": True,
            "var_address_space": True,
            "callable_function_types": True,
            "square_generic_args": True,
            "expression_generic_args": True,
        }
        fixtures = document["feature_groups"][0].get("fixtures", [])
        if fixtures:
            fixtures[0]["future_ast"] = {
                "StatementNode.attributes": [],
                "comparison_sampler": "sampler",
            }
    if document.get("negative_cases"):
        document["negative_cases"][0]["future_diagnostics"] = {
            "unsupported_binary_artifact": "opencl",
            "lowered_exponentiation": "pow",
        }
    write_json_file(path, document)


def mutate_self_test_imported_spec_known_field_drift(fixture_root):
    mutate_self_test_imported_spec_future_fields(fixture_root)
    path = fixture_root / "tools" / "cross_repo_language_spec.json"
    document = json.loads(path.read_text(encoding="utf-8"))
    document["source_language_snapshot"]["source_files"][0]["sha256"] = "0" * 64
    write_json_file(path, document)


def imported_feature_spec_self_test_errors(fixture_root):
    manifest = load_manifest(
        fixture_root / "tools" / "cross_repo_language_contract.json"
    )
    _heading, errors = check_imported_shared_spec_errors(
        manifest, fixture_root, fixture_root / "tools" / "cross_repo_language_spec.json"
    )
    return errors


def run_feature_spec_self_test(compiler_root):
    cases = (
        (
            "stale language_spec.sha256",
            mutate_self_test_language_spec_sha,
            "sha256 changed",
        ),
        (
            "stale language_spec.source_authority.source_files sha256",
            mutate_self_test_source_authority_sha,
            "language_spec.source_authority.source_files changed",
        ),
        (
            "stale generated feature spec source snapshot",
            mutate_self_test_feature_spec_snapshot,
            "source_language_snapshot changed",
        ),
        (
            "stale project-porting source-remap fixture",
            mutate_self_test_project_porting_fixture,
            "source-remap-v1-crosstl-project-line.json sha256 changed",
        ),
    )

    failures = []
    with tempfile.TemporaryDirectory(
        prefix="crossgl-feature-spec-self-test-"
    ) as temp_dir:
        temp_root = Path(temp_dir)
        baseline_root = temp_root / "baseline"
        copy_feature_spec_self_test_fixture(compiler_root, baseline_root)
        baseline_errors = feature_spec_self_test_errors(baseline_root)
        if baseline_errors:
            failures.append(
                "baseline feature spec fixture was rejected:\n{}".format(
                    "\n".join(baseline_errors)
                )
            )

        for index, (name, mutate, expected_fragment) in enumerate(cases, start=1):
            fixture_root = temp_root / "case-{}".format(index)
            copy_feature_spec_self_test_fixture(compiler_root, fixture_root)
            mutate(fixture_root)
            errors = feature_spec_self_test_errors(fixture_root)
            joined_errors = "\n".join(errors)
            if not errors:
                failures.append("{} was accepted".format(name))
            elif expected_fragment not in joined_errors:
                failures.append(
                    "{} did not report {!r}:\n{}".format(
                        name, expected_fragment, joined_errors
                    )
                )

        future_fixture_root = temp_root / "future-import"
        copy_feature_spec_self_test_fixture(compiler_root, future_fixture_root)
        mutate_self_test_imported_spec_future_fields(future_fixture_root)
        future_errors = imported_feature_spec_self_test_errors(future_fixture_root)
        if future_errors:
            failures.append(
                "imported shared spec with optional future fields was rejected:\n{}".format(
                    "\n".join(future_errors)
                )
            )

        drift_fixture_root = temp_root / "future-import-drift"
        copy_feature_spec_self_test_fixture(compiler_root, drift_fixture_root)
        mutate_self_test_imported_spec_known_field_drift(drift_fixture_root)
        drift_errors = imported_feature_spec_self_test_errors(drift_fixture_root)
        joined_drift_errors = "\n".join(drift_errors)
        expected_drift = "/source_language_snapshot/source_files/0/sha256"
        if not drift_errors:
            failures.append("imported shared spec known-field drift was accepted")
        elif expected_drift not in joined_drift_errors:
            failures.append(
                "imported shared spec drift did not report {}:\n{}".format(
                    expected_drift, joined_drift_errors
                )
            )
    return failures


def build_actual_contract(translator_root, compiler_root, cglc, inputs):
    sys.path.insert(0, str(translator_root))
    from crosstl.translator import parse

    actual = {}
    failures = []
    for item_id, path in inputs:
        source = path.read_text(encoding="utf-8")
        entry = {
            "source_sha256": sha256_text(source),
        }

        try:
            ast_hash, diagnostics = translator_ast_hash(parse, source)
        except Exception as exc:
            failures.append(
                "{}: translator parser failed with {}: {}".format(
                    item_id, exc.__class__.__name__, exc
                )
            )
        else:
            if diagnostics:
                failures.append(
                    "{}: translator parser emitted diagnostics:\n{}".format(
                        item_id, diagnostics
                    )
                )
            else:
                entry["translator_ast_sha256"] = ast_hash

        hir_hash, failure = compiler_hir_hash(cglc, compiler_root, path)
        if failure:
            failures.append("{}: {}".format(item_id, failure))
        else:
            entry["compiler_hir_sha256"] = hir_hash

        actual[item_id] = entry

    return actual, failures


def load_manifest(path):
    with path.open("r", encoding="utf-8") as handle:
        manifest = json.load(handle)
    if manifest.get("schema") != 1:
        raise ValueError(
            "{} uses unsupported schema {}".format(path, manifest.get("schema"))
        )
    contracts = manifest.get("contracts")
    if not isinstance(contracts, dict):
        raise ValueError("{} is missing a contracts object".format(path))
    return manifest


def default_manifest(contracts):
    return {
        "schema": 1,
        "description": (
            "CrossGL Translator and Compiler language/IR contract. "
            "Update with tools/check_cross_repo_language_contract.py --update-manifest "
            "after intentional frontend or HIR changes."
        ),
        "contracts": contracts,
    }


def write_manifest(path, contracts, existing_manifest=None):
    manifest = (
        dict(existing_manifest)
        if isinstance(existing_manifest, dict)
        else default_manifest(contracts)
    )
    manifest["schema"] = 1
    manifest["contracts"] = contracts
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")


def compare_contracts(expected, actual):
    mismatches = []

    for item_id in sorted(actual):
        if item_id not in expected:
            mismatches.append("{}: missing from manifest".format(item_id))
            continue
        for key in sorted(actual[item_id]):
            expected_value = expected[item_id].get(key)
            actual_value = actual[item_id][key]
            if expected_value != actual_value:
                mismatches.append(
                    "{}: {} changed\n  expected: {}\n  actual:   {}".format(
                        item_id, key, expected_value, actual_value
                    )
                )

    for item_id in sorted(set(expected) - set(actual)):
        mismatches.append("{}: present in manifest but not discovered".format(item_id))

    return mismatches


def count_by_root(inputs):
    counts = {}
    for item_id, _path in inputs:
        root = item_id.split("/", 1)[0]
        counts[root] = counts.get(root, 0) + 1
    return counts


def accepted_group_counts(manifest):
    counts = {}
    groups = manifest.get("accepted_contracts", {})
    if not isinstance(groups, dict):
        return counts
    for group_name, group in sorted(groups.items()):
        fixtures = group.get("fixtures", []) if isinstance(group, dict) else []
        counts[group_name] = len(fixtures) if isinstance(fixtures, list) else 0
    return counts


def accepted_grouped_fixture_ids(manifest):
    fixture_ids = set()
    groups = manifest.get("accepted_contracts", {})
    if not isinstance(groups, dict):
        return fixture_ids
    for group in groups.values():
        fixtures = group.get("fixtures", []) if isinstance(group, dict) else []
        if isinstance(fixtures, list):
            fixture_ids.update(
                fixture for fixture in fixtures if isinstance(fixture, str)
            )
    return fixture_ids


def negative_group_counts(manifest):
    counts = {}
    classification_counts = {}
    groups = manifest.get("negative_contracts", {})
    if not isinstance(groups, dict):
        return counts, classification_counts
    for group_name, group in sorted(groups.items()):
        if isinstance(group, list):
            cases = group
        elif isinstance(group, dict):
            cases = group.get("cases", [])
        else:
            cases = []
        if not isinstance(cases, list):
            cases = []
        counts[group_name] = len(cases)
        for case in cases:
            if not isinstance(case, dict):
                continue
            classification = case.get("classification", "unclassified")
            classification_counts[classification] = (
                classification_counts.get(classification, 0) + 1
            )
    return counts, classification_counts


def dry_run_hash_counts(expected, actual):
    counts = {
        "changed_hashes": {field: 0 for field in HASH_FIELDS},
        "missing_hashes_in_manifest": {field: 0 for field in HASH_FIELDS},
        "missing_hashes_in_actual": {field: 0 for field in HASH_FIELDS},
        "contracts_with_hash_changes": 0,
        "new_contracts": 0,
        "removed_contracts": 0,
    }

    changed_contracts = set()
    for item_id, actual_entry in actual.items():
        expected_entry = expected.get(item_id)
        if expected_entry is None:
            counts["new_contracts"] += 1
            changed_contracts.add(item_id)
            for field in HASH_FIELDS:
                if field in actual_entry:
                    counts["missing_hashes_in_manifest"][field] += 1
            continue
        for field in HASH_FIELDS:
            expected_has_field = field in expected_entry
            actual_has_field = field in actual_entry
            if actual_has_field and not expected_has_field:
                counts["missing_hashes_in_manifest"][field] += 1
                changed_contracts.add(item_id)
            elif expected_has_field and not actual_has_field:
                counts["missing_hashes_in_actual"][field] += 1
                changed_contracts.add(item_id)
            elif actual_has_field and expected_entry[field] != actual_entry[field]:
                counts["changed_hashes"][field] += 1
                changed_contracts.add(item_id)

    removed = set(expected) - set(actual)
    counts["removed_contracts"] = len(removed)
    changed_contracts.update(removed)
    counts["contracts_with_hash_changes"] = len(changed_contracts)
    counts["changed_hashes_total"] = sum(counts["changed_hashes"].values())
    counts["would_update_hashes"] = {
        field: counts["changed_hashes"][field]
        + counts["missing_hashes_in_manifest"][field]
        for field in HASH_FIELDS
    }
    counts["would_update_hashes_total"] = sum(counts["would_update_hashes"].values())
    return counts


def language_spec_snapshot(manifest, compiler_root):
    spec = manifest.get("language_spec")
    if not isinstance(spec, dict):
        return None

    relative_path = spec.get("path")
    snapshot = {
        "id": spec.get("id"),
        "path": relative_path,
        "manifest_sha256": spec.get("sha256"),
        "schema_version": spec.get("schema_version"),
    }
    if isinstance(relative_path, str) and relative_path:
        spec_path = (compiler_root / relative_path).resolve()
        snapshot["resolved_path"] = str(spec_path)
        try:
            spec_text = spec_path.read_text(encoding="utf-8")
            snapshot["sha256"] = sha256_text(spec_text)
            spec_document = json.loads(spec_text)
        except OSError as exc:
            snapshot["error"] = str(exc)
        except json.JSONDecodeError as exc:
            snapshot["error"] = "could not parse JSON: {}".format(exc)
        else:
            snapshot["actual_schema_version"] = spec_document.get("schemaVersion")
            snapshot["kind"] = spec_document.get("kind")
            source = spec_document.get("source")
            if isinstance(source, dict):
                source_snapshot = {}
                for key in ("repository", "frontend"):
                    if key in source:
                        source_snapshot[key] = source[key]
                extraction = source.get("extraction")
                if isinstance(extraction, dict):
                    source_snapshot["extraction"] = {
                        key: extraction[key]
                        for key in ("tool", "method")
                        if key in extraction
                    }
                files = source.get("files")
                if isinstance(files, list):
                    source_snapshot["frontend_files"] = [
                        {
                            "path": item.get("path"),
                            "sha256": item.get("sha256"),
                        }
                        for item in files
                        if isinstance(item, dict)
                    ]
                snapshot["source"] = source_snapshot
    return snapshot


def contract_input_source_provenance(inputs):
    provenance = []
    for item_id, path in inputs:
        if "/" in item_id:
            root_name, relative_path = item_id.split("/", 1)
        else:
            root_name, relative_path = None, item_id
        entry = {
            "id": item_id,
            "root": root_name,
            "path": relative_path,
            "resolved_path": str(path.resolve()),
        }
        try:
            entry["source_sha256"] = sha256_text(path.read_text(encoding="utf-8"))
        except OSError as exc:
            entry["error"] = str(exc)
        provenance.append(entry)
    return provenance


def negative_contract_source_provenance(manifest, translator_root, compiler_root):
    provenance = []
    try:
        cases = list(iter_negative_contracts(manifest))
    except ValueError as exc:
        return [{"error": str(exc)}]

    for index, (group_name, case) in enumerate(cases, start=1):
        case_id = case.get("id") or "{}/{}".format(group_name, index)
        entry = {
            "id": case_id,
            "group": group_name,
            "classification": case.get("classification", "unclassified"),
        }
        if "path" in case:
            root_name = case.get("root", "compiler")
            entry["root"] = root_name
            entry["path"] = case.get("path")
        else:
            entry["source_kind"] = "inline"
        try:
            source, path = negative_case_source(case, translator_root, compiler_root)
        except ValueError as exc:
            entry["error"] = str(exc)
        else:
            entry["source_sha256"] = sha256_text(source)
            if path is not None:
                entry["resolved_path"] = str(path.resolve())
        provenance.append(entry)
    return provenance


def build_report(
    *,
    manifest,
    manifest_path,
    translator_root,
    compiler_root,
    cglc,
    inputs,
    exclusions,
    actual=None,
    mode="check",
):
    negative_counts, classification_counts = negative_group_counts(manifest)
    grouped_accepted = accepted_grouped_fixture_ids(manifest)
    accepted_ids = {item_id for item_id, _path in inputs}
    language_snapshot = language_spec_snapshot(manifest, compiler_root)
    report = {
        "schema": 1,
        "mode": mode,
        "language_spec": language_snapshot,
        "manifest": {
            "path": str(manifest_path),
            "contract_count": len(manifest.get("contracts", {})),
        },
        "roots": {
            "translator": str(translator_root),
            "compiler": str(compiler_root),
        },
        "cglc": str(cglc) if cglc is not None else None,
        "fixtures": {
            "accepted": {
                "discovered": len(inputs),
                "by_root": count_by_root(inputs),
                "by_group": accepted_group_counts(manifest),
                "grouped": len(accepted_ids & grouped_accepted),
                "ungrouped": len(accepted_ids - grouped_accepted),
                "by_classification": {"accepted": len(inputs)},
            },
            "negative": {
                "total": sum(negative_counts.values()),
                "by_group": negative_counts,
                "by_classification": classification_counts,
            },
            "excluded": {
                "total": len(exclusions),
                "fixtures": exclusions,
            },
        },
        "source_provenance": {
            "crosstl_frontend": language_snapshot.get("source")
            if isinstance(language_snapshot, dict)
            else None,
            "accepted_inputs": contract_input_source_provenance(inputs),
            "negative_inputs": negative_contract_source_provenance(
                manifest, translator_root, compiler_root
            ),
        },
    }
    if actual is not None:
        report["dry_run_hash_counts"] = dry_run_hash_counts(
            manifest.get("contracts", {}), actual
        )
    return report


def write_report(path, report):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


def parse_args(argv):
    script_root = Path(__file__).resolve().parents[1]
    default_translator_root = script_root.parent / "CrossGL-Translator"
    parser = argparse.ArgumentParser(
        description="Validate CrossGL Translator and Compiler language/IR compatibility."
    )
    parser.add_argument("--translator-root", default=str(default_translator_root))
    parser.add_argument("--compiler-root", default=str(script_root))
    parser.add_argument("--cglc", default=None, help="Path to a built cglc executable")
    parser.add_argument(
        "--manifest",
        default=str(script_root / "tools" / "cross_repo_language_contract.json"),
    )
    parser.add_argument(
        "--update-manifest",
        action="store_true",
        help="Rewrite the manifest with the current parser AST and compiler HIR hashes.",
    )
    parser.add_argument(
        "--check-feature-spec",
        action="store_true",
        help=(
            "Validate the committed shared feature spec artifact and exit without "
            "requiring CrossGL-Translator or cglc."
        ),
    )
    parser.add_argument(
        "--update-feature-spec",
        action="store_true",
        help=(
            "Rewrite the shared feature spec artifact from the committed CrossTL "
            "snapshot and cross-repo contract manifest, then exit."
        ),
    )
    parser.add_argument(
        "--self-test",
        action="store_true",
        help=(
            "Run isolated feature spec drift-detection fixtures and exit without "
            "requiring CrossGL-Translator or cglc."
        ),
    )
    parser.add_argument(
        "--shared-spec",
        default=None,
        help=(
            "Import a shared CrossTL language feature spec JSON artifact and "
            "compare its known v1 projection against the committed compiler "
            "snapshot/contract inputs. Unknown optional fields are ignored."
        ),
    )
    parser.add_argument(
        "--report",
        default=None,
        help="Write a JSON drift report without changing manifest update behavior.",
    )
    return parser.parse_args(argv)


def main(argv=None):
    args = parse_args(argv or sys.argv[1:])
    translator_root = resolve_root(args.translator_root)
    compiler_root = resolve_root(args.compiler_root)
    manifest_path = resolve_root(args.manifest)
    report_path = resolve_root(args.report) if args.report else None
    shared_spec_path = resolve_root(args.shared_spec) if args.shared_spec else None

    if not compiler_root.exists():
        print("Compiler root does not exist: {}".format(compiler_root), file=sys.stderr)
        return 2

    if args.self_test:
        failures = run_feature_spec_self_test(compiler_root)
        if failures:
            print("Cross-repo language feature spec self-test failed:", file=sys.stderr)
            for failure in failures:
                print("\nself-test: {}".format(failure), file=sys.stderr)
            return 1
        print("[contract] Feature spec self-test OK")
        return 0

    manifest = load_manifest(manifest_path)

    if args.update_feature_spec:
        spec_document, feature_spec_errors = check_language_spec_reference(
            manifest, compiler_root
        )
        feature_spec_errors.extend(validate_feature_groups(manifest, spec_document))
        feature_spec_errors.extend(
            validate_negative_contract_anchors(manifest, spec_document, compiler_root)
        )
        try:
            list(iter_negative_contracts(manifest))
        except ValueError as exc:
            feature_spec_errors.append(str(exc))
        if feature_spec_errors:
            print(
                "Cross-repo language feature spec inputs are invalid:",
                file=sys.stderr,
            )
            for error in feature_spec_errors:
                print("\n{}".format(error), file=sys.stderr)
            return 1
        feature_spec_path = write_cross_repo_language_feature_spec(
            manifest, compiler_root, spec_document
        )
        print("[contract] Wrote {}".format(feature_spec_path))
        if not args.check_feature_spec:
            return 0

    if args.check_feature_spec:
        heading, feature_spec_errors = check_feature_spec_mode_errors(
            manifest, compiler_root
        )
        if feature_spec_errors:
            print(heading, file=sys.stderr)
            for error in feature_spec_errors:
                print("\n{}".format(error), file=sys.stderr)
            return 1
        print(
            "[contract] Feature spec OK: {}".format(
                manifest.get("feature_spec", {}).get("path")
            )
        )
        if shared_spec_path is None:
            return 0

    if shared_spec_path is not None:
        heading, shared_spec_errors = check_imported_shared_spec_errors(
            manifest, compiler_root, shared_spec_path
        )
        if shared_spec_errors:
            print(heading, file=sys.stderr)
            for error in shared_spec_errors:
                print("\n{}".format(error), file=sys.stderr)
            return 1
        print("[contract] Shared spec import OK: {}".format(shared_spec_path))
        return 0

    if not translator_root.exists():
        print(
            "Translator root does not exist: {}".format(translator_root),
            file=sys.stderr,
        )
        return 2

    cglc = find_cglc(compiler_root, args.cglc)
    if cglc is None:
        print(
            "Could not find cglc. Build the compiler first or pass --cglc.",
            file=sys.stderr,
        )
        return 2

    inputs, exclusions = discover_contract_inputs(
        translator_root, compiler_root, include_exclusions=True
    )
    if not inputs:
        print("No CrossGL contract inputs were discovered.", file=sys.stderr)
        return 2

    if report_path is not None:
        write_report(
            report_path,
            build_report(
                manifest=manifest,
                manifest_path=manifest_path,
                translator_root=translator_root,
                compiler_root=compiler_root,
                cglc=cglc,
                inputs=inputs,
                exclusions=exclusions,
                mode="update-manifest" if args.update_manifest else "check",
            ),
        )
    metadata_errors = validate_manifest_metadata(
        manifest, compiler_root, require_feature_spec=True
    )
    if metadata_errors:
        print("Cross-repo language contract manifest is invalid:", file=sys.stderr)
        for error in metadata_errors:
            print("\n{}".format(error), file=sys.stderr)
        return 1

    actual, failures = build_actual_contract(
        translator_root, compiler_root, cglc, inputs
    )
    if report_path is not None:
        write_report(
            report_path,
            build_report(
                manifest=manifest,
                manifest_path=manifest_path,
                translator_root=translator_root,
                compiler_root=compiler_root,
                cglc=cglc,
                inputs=inputs,
                exclusions=exclusions,
                actual=actual,
                mode="update-manifest" if args.update_manifest else "check",
            ),
        )
    negative_hash_updates = 0
    if args.update_manifest:
        negative_count, negative_hash_updates, negative_failures = (
            refresh_negative_contract_hashes(manifest, translator_root, compiler_root)
        )
    else:
        negative_count, negative_failures = validate_negative_contracts(
            manifest, translator_root, compiler_root, cglc
        )
    if failures or negative_failures:
        print("Cross-repo language contract failed:", file=sys.stderr)
        for failure in failures:
            print("\n{}".format(failure), file=sys.stderr)
        for failure in negative_failures:
            print("\n{}".format(failure), file=sys.stderr)
        return 1

    if args.update_manifest:
        negative_count, negative_failures = validate_negative_contracts(
            manifest, translator_root, compiler_root, cglc
        )
        if negative_failures:
            print("Cross-repo language contract failed:", file=sys.stderr)
            for failure in negative_failures:
                print("\n{}".format(failure), file=sys.stderr)
            return 1
        write_manifest(manifest_path, actual, manifest)
        print("[contract] Wrote {}".format(manifest_path))
        if negative_hash_updates:
            print(
                "[contract] Refreshed negative hashes: {}".format(negative_hash_updates)
            )
    else:
        expected = manifest["contracts"]
        mismatches = compare_contracts(expected, actual)
        if mismatches:
            print("Cross-repo language contract changed:", file=sys.stderr)
            for mismatch in mismatches:
                print("\n{}".format(mismatch), file=sys.stderr)
            print(
                "\nIf the language/HIR change is intentional, update the manifest with "
                "--update-manifest after validating both repositories.",
                file=sys.stderr,
            )
            return 1

    print("[contract] Inputs: {}".format(len(inputs)))
    print("[contract] Translator AST hashes: {}".format(len(actual)))
    print("[contract] Compiler HIR hashes: {}".format(len(actual)))
    print("[contract] Negative cases: {}".format(negative_count))
    print("[contract] cglc: {}".format(cglc))
    return 0


if __name__ == "__main__":
    sys.exit(main())
