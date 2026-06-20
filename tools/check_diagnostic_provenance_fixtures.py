#!/usr/bin/env python3
"""Check source provenance for v0 unsupported diagnostics."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path

from source_location_fixture_checks import (
    expect_location_span_coherent,
    expect_location_text_equals,
)


UNSUPPORTED_NATIVE_V0_CODE = "spec.unsupported-for-native-v0"
SOURCE_REMAP_LOGICAL_INPUT = "generated/from-translator.cgl"
SOURCE_REMAP_ORIGINAL_INPUT = "shaders/original.crossgl"
SOURCE_REMAP_ORIGINAL_LINE = 40
SOURCE_REMAP_ORIGINAL_OFFSET = 900
SOURCE_REMAP_SOURCE = """shader DiagnosticProvenanceShader {
  compute {
    layout(local_size_x = 1, local_size_y = 1, local_size_z = 1) in;

    void main() {
      missingValue = 1.0;
      return;
    }
  }
}
"""


@dataclass(frozen=True)
class DiagnosticCase:
    name: str
    fixture: Path
    expected_span_text: str
    message_fragments: tuple[str, ...]


UNSUPPORTED_NATIVE_V0_CASES = (
    DiagnosticCase(
        "unsupported-extended-stage",
        Path("tests/check-failures/BadUnsupportedExtendedStageShader.cgl"),
        "geometry",
        ("stage 'geometry'", "native v0"),
    ),
    DiagnosticCase(
        "unsupported-enum",
        Path("tests/check-failures/BadUnsupportedEnumShader.cgl"),
        "enum",
        ("enum declarations", "native v0"),
    ),
    DiagnosticCase(
        "unsupported-generic",
        Path("tests/check-failures/BadUnsupportedGenericShader.cgl"),
        "generic",
        ("generic declarations", "native v0"),
    ),
    DiagnosticCase(
        "unsupported-impl",
        Path("tests/check-failures/BadUnsupportedImplShader.cgl"),
        "impl",
        ("impl declarations", "native v0"),
    ),
    DiagnosticCase(
        "unsupported-import",
        Path("tests/check-failures/BadUnsupportedImportShader.cgl"),
        "import",
        ("source import declarations", "native v0"),
    ),
    DiagnosticCase(
        "unsupported-colon-var",
        Path("tests/check-failures/BadUnsupportedColonVarShader.cgl"),
        "var",
        ("colon-style variable declarations", "native v0", "decl.colon-var"),
    ),
    DiagnosticCase(
        "unsupported-match",
        Path("tests/check-failures/BadUnsupportedMatchShader.cgl"),
        "match",
        ("match/pattern control statements", "native v0"),
    ),
    DiagnosticCase(
        "unsupported-preprocessor",
        Path("tests/check-failures/BadUnsupportedPreprocessorShader.cgl"),
        "#",
        ("preprocessor directives", "native v0"),
    ),
    DiagnosticCase(
        "unsupported-line-splicing-preprocessor",
        Path("tests/check-failures/BadUnsupportedLineSplicingPreprocessorShader.cgl"),
        "\\",
        (
            "line-splicing/preprocessor continuation syntax",
            "native v0",
            "decl.line-splicing-preprocessor",
        ),
    ),
    DiagnosticCase(
        "unsupported-trait",
        Path("tests/check-failures/BadUnsupportedTraitShader.cgl"),
        "trait",
        ("trait declarations", "native v0"),
    ),
)


def run_check(cglc: Path, fixture: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [str(cglc), "check", str(fixture), "--diagnostics-json"],
        check=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )


def source_span_for_text(
    file: str,
    text: str,
    *,
    start_line: int = 1,
    start_column: int = 1,
    start_offset: int = 0,
):
    end_line = start_line
    end_column = start_column
    for char in text:
        if char == "\n":
            end_line += 1
            end_column = 1
        else:
            end_column += 1
    return {
        "file": file,
        "line": start_line,
        "column": start_column,
        "offset": start_offset,
        "length": len(text),
        "endLine": end_line,
        "endColumn": end_column,
        "endOffset": start_offset + len(text),
    }


def write_source_remap(tmp_dir: Path, source_text: str) -> Path:
    remap_path = tmp_dir / "diagnostic-source-remap.json"
    remap = {
        "schemaVersion": 1,
        "generatedFile": SOURCE_REMAP_LOGICAL_INPUT,
        "mappings": [
            {
                "generated": source_span_for_text(
                    SOURCE_REMAP_LOGICAL_INPUT,
                    source_text,
                ),
                "original": source_span_for_text(
                    SOURCE_REMAP_ORIGINAL_INPUT,
                    source_text,
                    start_line=SOURCE_REMAP_ORIGINAL_LINE,
                    start_offset=SOURCE_REMAP_ORIGINAL_OFFSET,
                ),
            }
        ],
    }
    remap_path.write_text(json.dumps(remap, indent=2) + "\n", encoding="utf-8")
    return remap_path


def validate_schema(root: Path, tmp_dir: Path, case_name: str, diagnostics_json: str):
    instance_path = tmp_dir / f"{case_name}.diagnostics.json"
    instance_path.write_text(diagnostics_json, encoding="utf-8")
    result = subprocess.run(
        [
            sys.executable,
            str(root / "tools" / "validate_json_schema.py"),
            "--schema",
            str(root / "docs" / "schemas" / "diagnostics-v1.schema.json"),
            "--instance",
            str(instance_path),
        ],
        check=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if result.returncode != 0:
        return [
            f"{case_name}: diagnostics JSON failed schema validation: "
            f"{result.stderr}{result.stdout}".strip()
        ]
    return []


def is_absolute_location_file(location_file: str) -> bool:
    normalized = location_file.replace("\\", "/")
    return normalized.startswith("/") or (
        len(location_file) >= 2
        and location_file[0].isalpha()
        and location_file[1] == ":"
    )


def expect_diagnostic_contract(errors, case, root, payload):
    if not isinstance(payload, dict):
        errors.append(f"{case.name}: expected diagnostics output to be an object")
        return

    if payload.get("schemaVersion") != 1:
        errors.append(
            f"{case.name}: expected schemaVersion 1, got "
            f"{payload.get('schemaVersion')!r}"
        )

    diagnostics = payload.get("diagnostics")
    if not isinstance(diagnostics, list):
        errors.append(f"{case.name}: expected diagnostics array")
        return
    if len(diagnostics) != 1:
        errors.append(f"{case.name}: expected one diagnostic, got {len(diagnostics)!r}")
        return

    diagnostic = diagnostics[0]
    if not isinstance(diagnostic, dict):
        errors.append(f"{case.name}: expected diagnostics[0] to be an object")
        return

    if diagnostic.get("severity") != "error":
        errors.append(
            f"{case.name}: expected diagnostics[0].severity='error', got "
            f"{diagnostic.get('severity')!r}"
        )
    if diagnostic.get("code") != UNSUPPORTED_NATIVE_V0_CODE:
        errors.append(
            f"{case.name}: expected diagnostics[0].code="
            f"{UNSUPPORTED_NATIVE_V0_CODE!r}, got {diagnostic.get('code')!r}"
        )

    message = diagnostic.get("message")
    if not isinstance(message, str):
        errors.append(f"{case.name}: expected diagnostics[0].message to be a string")
    else:
        for fragment in case.message_fragments:
            if fragment not in message:
                errors.append(
                    f"{case.name}: expected diagnostics[0].message to contain "
                    f"{fragment!r}, got {message!r}"
                )

    location = diagnostic.get("location")
    if isinstance(location, dict):
        location_file = str(location.get("file", "")).replace("\\", "/")
        if is_absolute_location_file(str(location.get("file", ""))):
            errors.append(
                f"{case.name}: expected diagnostics[0].location.file to be "
                f"relative, got {location.get('file')!r}"
            )
        if not location_file.endswith(case.fixture.as_posix()):
            errors.append(
                f"{case.name}: expected diagnostics[0].location.file to end "
                f"in {case.fixture.as_posix()!r}, got "
                f"{location.get('file')!r}"
            )
    expect_location_span_coherent(
        errors,
        case.name,
        "diagnostics[0].location",
        location,
    )
    expect_location_text_equals(
        errors,
        case.name,
        "diagnostics[0].location",
        location,
        root / case.fixture,
        case.expected_span_text,
    )


def check_case(root: Path, cglc: Path, tmp_dir: Path, case: DiagnosticCase):
    errors: list[str] = []
    fixture = root / case.fixture
    result = run_check(cglc, fixture)
    if result.returncode == 0:
        errors.append(f"{case.name}: expected cglc check to fail")
    if not result.stdout.strip():
        errors.append(f"{case.name}: expected diagnostics JSON on stdout")
        return errors

    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        return [
            f"{case.name}: failed to parse diagnostics JSON: {exc}; "
            f"stdout={result.stdout!r}; stderr={result.stderr!r}"
        ]

    errors.extend(validate_schema(root, tmp_dir, case.name, result.stdout))
    expect_diagnostic_contract(errors, case, root, payload)
    return errors


def check_source_remap_logical_input(root: Path, cglc: Path, tmp_dir: Path):
    case_name = "source-remap-logical-input"
    errors: list[str] = []
    source_path = tmp_dir / "diagnostic-source-remap-input.cgl"
    source_path.write_text(SOURCE_REMAP_SOURCE, encoding="utf-8")
    remap_path = write_source_remap(tmp_dir, SOURCE_REMAP_SOURCE)

    result = subprocess.run(
        [
            str(cglc),
            "check",
            str(source_path),
            "--logical-input",
            SOURCE_REMAP_LOGICAL_INPUT,
            "--source-remap",
            str(remap_path),
            "--diagnostics-json",
        ],
        check=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if result.returncode == 0:
        errors.append(f"{case_name}: expected cglc check to fail")
    if not result.stdout.strip():
        errors.append(f"{case_name}: expected diagnostics JSON on stdout")
        return errors

    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        return [
            f"{case_name}: failed to parse diagnostics JSON: {exc}; "
            f"stdout={result.stdout!r}; stderr={result.stderr!r}"
        ]

    errors.extend(validate_schema(root, tmp_dir, case_name, result.stdout))
    diagnostics = payload.get("diagnostics")
    if not isinstance(diagnostics, list) or len(diagnostics) != 1:
        diagnostic_count = len(diagnostics) if isinstance(diagnostics, list) else None
        errors.append(f"{case_name}: expected one diagnostic, got {diagnostic_count!r}")
        return errors

    diagnostic = diagnostics[0]
    if not isinstance(diagnostic, dict):
        errors.append(f"{case_name}: expected diagnostics[0] to be an object")
        return errors
    if diagnostic.get("severity") != "error":
        errors.append(
            f"{case_name}: expected diagnostics[0].severity='error', got "
            f"{diagnostic.get('severity')!r}"
        )

    location = diagnostic.get("location")
    original_location = diagnostic.get("originalLocation")
    if isinstance(location, dict):
        if location.get("file") != SOURCE_REMAP_LOGICAL_INPUT:
            errors.append(
                f"{case_name}: expected generated logical location file "
                f"{SOURCE_REMAP_LOGICAL_INPUT!r}, got {location.get('file')!r}"
            )
        if str(source_path) in result.stdout:
            errors.append(
                f"{case_name}: diagnostics JSON leaked physical source path "
                f"{source_path}"
            )
    expect_location_text_equals(
        errors,
        case_name,
        "diagnostics[0].location",
        location,
        source_path,
        "missingValue",
        expected_file_name=Path(SOURCE_REMAP_LOGICAL_INPUT).name,
    )
    expect_location_span_coherent(
        errors,
        case_name,
        "diagnostics[0].originalLocation",
        original_location,
    )
    if not isinstance(original_location, dict):
        return errors
    if original_location.get("file") != SOURCE_REMAP_ORIGINAL_INPUT:
        errors.append(
            f"{case_name}: expected original location file "
            f"{SOURCE_REMAP_ORIGINAL_INPUT!r}, got "
            f"{original_location.get('file')!r}"
        )
        return errors
    if isinstance(location, dict):
        location_fields = (
            "line",
            "column",
            "offset",
            "length",
            "endLine",
            "endColumn",
            "endOffset",
        )
        if not all(isinstance(location.get(field), int) for field in location_fields):
            errors.append(
                f"{case_name}: expected integer generated location fields, "
                f"got {location!r}"
            )
            return errors
        expected_line_delta = SOURCE_REMAP_ORIGINAL_LINE - 1
        translated_fields = {
            "line": location.get("line") + expected_line_delta,
            "column": location.get("column"),
            "offset": location.get("offset") + SOURCE_REMAP_ORIGINAL_OFFSET,
            "length": location.get("length"),
            "endLine": location.get("endLine") + expected_line_delta,
            "endColumn": location.get("endColumn"),
            "endOffset": location.get("endOffset") + SOURCE_REMAP_ORIGINAL_OFFSET,
        }
        for field, expected in translated_fields.items():
            if original_location.get(field) != expected:
                errors.append(
                    f"{case_name}: expected originalLocation.{field}="
                    f"{expected!r}, got {original_location.get(field)!r}"
                )
        stderr_location = (
            f"{SOURCE_REMAP_ORIGINAL_INPUT}:{translated_fields['line']}:"
            f"{translated_fields['column']}: error "
        )
        if stderr_location not in result.stderr:
            errors.append(
                f"{case_name}: expected human diagnostics to use remapped "
                f"location {stderr_location!r}, got {result.stderr!r}"
            )

    return errors


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", required=True, type=Path)
    parser.add_argument("--cglc", required=True, type=Path)
    args = parser.parse_args()

    root = args.root.resolve()
    cglc = args.cglc.resolve()
    errors: list[str] = []
    with tempfile.TemporaryDirectory() as tmp:
        tmp_dir = Path(tmp)
        for case in UNSUPPORTED_NATIVE_V0_CASES:
            errors.extend(check_case(root, cglc, tmp_dir, case))
        errors.extend(check_source_remap_logical_input(root, cglc, tmp_dir))

    if errors:
        for error in errors:
            print(error, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
