#!/usr/bin/env python3
"""Check cross-repo contract helper behavior."""

import argparse
import importlib.util
import json
import sys
import tempfile
from pathlib import Path


def load_contract_tool(root):
    tool_path = root / "tools" / "check_cross_repo_language_contract.py"
    spec = importlib.util.spec_from_file_location("crossgl_contract_tool", tool_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"could not import {tool_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def write_file(path):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("", encoding="utf-8")
    return path


SELF_TEST_SOURCE_FILES = [
    {
        "path": "crosstl/translator/lexer.py",
        "sha256": "1" * 64,
    },
    {
        "path": "crosstl/translator/parser.py",
        "sha256": "2" * 64,
    },
    {
        "path": "crosstl/translator/ast.py",
        "sha256": "3" * 64,
    },
    {
        "path": "crosstl/translator/validation.py",
        "sha256": "4" * 64,
    },
]


def self_test_language_spec_document(contract_tool):
    return {
        "schemaVersion": 0,
        "kind": contract_tool.LANGUAGE_SPEC_KIND,
        "source": {
            "repository": contract_tool.LANGUAGE_SPEC_SOURCE_REPOSITORY,
            "frontend": contract_tool.LANGUAGE_SPEC_SOURCE_FRONTEND,
            "authorityReferences": [
                dict(reference)
                for reference in contract_tool.LANGUAGE_SPEC_AUTHORITY_REFERENCES
            ],
            "extraction": {
                "tool": contract_tool.LANGUAGE_SPEC_EXTRACTION_TOOL,
                "method": "static Python AST extraction",
            },
            "files": SELF_TEST_SOURCE_FILES,
        },
    }


def self_test_language_spec_text(contract_tool):
    return json.dumps(self_test_language_spec_document(contract_tool), indent=2) + "\n"


def self_test_language_spec_manifest_entry(contract_tool, spec_text):
    return {
        "id": contract_tool.LANGUAGE_SPEC_ID,
        "path": "docs/language/spec.json",
        "schema_version": 0,
        "sha256": contract_tool.sha256_text(spec_text),
        "source_authority": {
            "mode": contract_tool.LANGUAGE_SPEC_AUTHORITY_MODE,
            "canonical_until": contract_tool.LANGUAGE_SPEC_CANONICAL_UNTIL,
            "source_repository": contract_tool.LANGUAGE_SPEC_SOURCE_REPOSITORY,
            "source_frontend": contract_tool.LANGUAGE_SPEC_SOURCE_FRONTEND,
            "extraction_tool": contract_tool.LANGUAGE_SPEC_EXTRACTION_TOOL,
            "authority_references": [
                dict(reference)
                for reference in contract_tool.LANGUAGE_SPEC_AUTHORITY_REFERENCES
            ],
            "source_files": SELF_TEST_SOURCE_FILES,
        },
    }


def expect_found(contract_tool, compiler_root, expected, explicit_path=None):
    found = contract_tool.find_cglc(compiler_root, explicit_path)
    if found != expected.resolve():
        raise AssertionError(f"expected {expected.resolve()}, found {found}")


def expect_missing(contract_tool, compiler_root, explicit_path=None):
    found = contract_tool.find_cglc(compiler_root, explicit_path)
    if found is not None:
        raise AssertionError(f"expected no cglc match, found {found}")


def check_find_cglc(contract_tool):
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)

        single_config = write_file(root / "single-config" / "build" / "cglc")
        expect_found(contract_tool, single_config.parents[1], single_config)

        release_config = write_file(
            root / "multi-config" / "build" / "Release" / "cglc.exe"
        )
        expect_found(contract_tool, release_config.parents[2], release_config)

        nested_release = write_file(
            root / "nested-config" / "build" / "tools" / "cglc" / "Release" / "cglc.exe"
        )
        expect_found(contract_tool, nested_release.parents[4], nested_release)

        explicit_exe = write_file(root / "explicit" / "build" / "Release" / "cglc.exe")
        expect_found(
            contract_tool,
            explicit_exe.parents[2],
            explicit_exe,
            explicit_exe.with_suffix(""),
        )

        directory_candidate = (
            root / "directory-candidate" / "build" / "Release" / "cglc"
        )
        directory_candidate.mkdir(parents=True)
        expect_missing(contract_tool, directory_candidate.parents[2])


def check_discover_contract_input_exclusions(contract_tool):
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        compiler_root = root / "compiler"
        translator_root = root / "translator"

        write_file(compiler_root / "tests" / "fixtures" / "SimpleShader.cgl")
        write_file(
            compiler_root / "tests" / "fixtures" / "RuntimeArrayNestedShader.cgl"
        )
        write_file(
            compiler_root / "tests" / "fixtures" / "RuntimeArrayNonFinalShader.cgl"
        )
        write_file(translator_root / "examples" / "SimpleExample.cgl")

        discovered = {
            item_id
            for item_id, _path in contract_tool.discover_contract_inputs(
                translator_root, compiler_root
            )
        }

        expected = {
            "compiler/tests/fixtures/SimpleShader.cgl",
            "translator/examples/SimpleExample.cgl",
        }
        if discovered != expected:
            raise AssertionError(
                f"expected discovered contract inputs {expected}, found {discovered}"
            )

        discovered_with_exclusions, exclusions = contract_tool.discover_contract_inputs(
            translator_root, compiler_root, include_exclusions=True
        )
        if [item_id for item_id, _path in discovered_with_exclusions] != sorted(
            expected
        ):
            raise AssertionError("include_exclusions changed discovered input order")

        excluded_ids = {entry["id"] for entry in exclusions}
        expected_excluded = {
            "compiler/tests/fixtures/RuntimeArrayNestedShader.cgl",
            "compiler/tests/fixtures/RuntimeArrayNonFinalShader.cgl",
        }
        if excluded_ids != expected_excluded:
            raise AssertionError(
                f"expected excluded fixtures {expected_excluded}, found {excluded_ids}"
            )
        for entry in exclusions:
            if not entry.get("reason"):
                raise AssertionError(f"excluded fixture lacks reason: {entry}")


def check_report_summary(contract_tool):
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        compiler_root = root / "compiler"
        translator_root = root / "translator"
        spec_path = compiler_root / "docs" / "language" / "spec.json"
        spec_path.parent.mkdir(parents=True)
        spec_text = self_test_language_spec_text(contract_tool)
        spec_path.write_text(spec_text, encoding="utf-8")
        accepted_path = compiler_root / "tests" / "fixtures" / "A.cgl"
        accepted_path.parent.mkdir(parents=True)
        accepted_source = "shader A { compute { } }\n"
        accepted_path.write_bytes(accepted_source.replace("\n", "\r\n").encode("utf-8"))
        negative_source = "shader Bad { geometry { } }\n"

        manifest = {
            "contracts": {
                "compiler/tests/fixtures/A.cgl": {
                    "source_sha256": "old",
                    "translator_ast_sha256": "same",
                    "compiler_hir_sha256": "old-hir",
                },
            },
            "language_spec": self_test_language_spec_manifest_entry(
                contract_tool, spec_text
            ),
            "accepted_contracts": {
                "core": {"fixtures": ["compiler/tests/fixtures/A.cgl"]}
            },
            "negative_contracts": {
                "errors": {
                    "cases": [
                        {
                            "id": "bad",
                            "classification": "spec.error",
                            "source": negative_source.replace("\n", "\r\n"),
                        }
                    ]
                }
            },
        }
        inputs = [("compiler/tests/fixtures/A.cgl", accepted_path)]
        actual = {
            "compiler/tests/fixtures/A.cgl": {
                "source_sha256": "new",
                "translator_ast_sha256": "same",
                "compiler_hir_sha256": "new-hir",
            }
        }
        report = contract_tool.build_report(
            manifest=manifest,
            manifest_path=compiler_root / "tools" / "cross_repo_language_contract.json",
            translator_root=translator_root,
            compiler_root=compiler_root,
            cglc=compiler_root / "build" / "cglc",
            inputs=inputs,
            exclusions=[
                {
                    "id": "compiler/tests/fixtures/Excluded.cgl",
                    "root": "compiler",
                    "path": "tests/fixtures/Excluded.cgl",
                    "reason": "covered elsewhere",
                }
            ],
            actual=actual,
        )

        if report["language_spec"]["sha256"] != contract_tool.sha256_text(spec_text):
            raise AssertionError("report did not record actual spec hash")
        if report["language_spec"]["actual_schema_version"] != 0:
            raise AssertionError("report did not record actual spec schema version")
        source = report["language_spec"]["source"]
        if source["frontend_files"] != SELF_TEST_SOURCE_FILES:
            raise AssertionError("report did not record frontend source file seals")
        if report["source_provenance"]["crosstl_frontend"] != source:
            raise AssertionError("report did not expose CrossTL frontend provenance")
        if report["fixtures"]["accepted"]["by_group"] != {"core": 1}:
            raise AssertionError("report did not count accepted fixture groups")
        if report["fixtures"]["accepted"]["grouped"] != 1:
            raise AssertionError("report did not count grouped accepted fixtures")
        if report["fixtures"]["accepted"]["ungrouped"] != 0:
            raise AssertionError("report did not count ungrouped accepted fixtures")
        if report["fixtures"]["negative"]["by_classification"] != {"spec.error": 1}:
            raise AssertionError("report did not count negative classifications")
        if report["fixtures"]["excluded"]["total"] != 1:
            raise AssertionError("report did not count excluded fixtures")
        accepted_sources = report["source_provenance"]["accepted_inputs"]
        if accepted_sources != [
            {
                "id": "compiler/tests/fixtures/A.cgl",
                "root": "compiler",
                "path": "tests/fixtures/A.cgl",
                "resolved_path": str(accepted_path.resolve()),
                "source_sha256": contract_tool.sha256_text(accepted_source),
            }
        ]:
            raise AssertionError("report did not record accepted input provenance")
        negative_sources = report["source_provenance"]["negative_inputs"]
        if negative_sources != [
            {
                "id": "bad",
                "group": "errors",
                "classification": "spec.error",
                "source_kind": "inline",
                "source_sha256": contract_tool.sha256_text(negative_source),
            }
        ]:
            raise AssertionError("report did not record negative input provenance")
        changed_hashes = report["dry_run_hash_counts"]["changed_hashes"]
        if changed_hashes["source_sha256"] != 1:
            raise AssertionError("report did not count source hash drift")
        if changed_hashes["compiler_hir_sha256"] != 1:
            raise AssertionError("report did not count HIR hash drift")


def check_language_spec_hash_normalizes_newlines(contract_tool):
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        compiler_root = root / "compiler"
        spec_path = compiler_root / "docs" / "language" / "spec.json"
        spec_path.parent.mkdir(parents=True)
        schema_path = compiler_root / contract_tool.LANGUAGE_SPEC_JSON_SCHEMA_PATH
        schema_path.parent.mkdir(parents=True)
        schema_path.write_text(
            "{\n"
            '  "type": "object",\n'
            '  "required": ["schemaVersion"],\n'
            '  "properties": {\n'
            '    "schemaVersion": {"type": "integer", "const": 0}\n'
            "  }\n"
            "}\n",
            encoding="utf-8",
        )
        lf_spec = self_test_language_spec_text(contract_tool)
        spec_path.write_bytes(lf_spec.replace("\n", "\r\n").encode("utf-8"))

        manifest = {
            "language_spec": self_test_language_spec_manifest_entry(
                contract_tool, lf_spec
            )
        }

        errors = contract_tool.validate_manifest_metadata(manifest, compiler_root)
        if errors:
            raise AssertionError(
                "expected CRLF language spec to match LF-normalized hash, got "
                + repr(errors)
            )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--root",
        default=Path(__file__).resolve().parents[1],
        help="CrossGL-Compiler repository root",
    )
    args = parser.parse_args()

    root = Path(args.root).resolve()
    contract_tool = load_contract_tool(root)
    check_find_cglc(contract_tool)
    check_discover_contract_input_exclusions(contract_tool)
    check_language_spec_hash_normalizes_newlines(contract_tool)
    check_report_summary(contract_tool)
    print("validated cross-repo contract tool helpers")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
