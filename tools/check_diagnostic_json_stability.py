#!/usr/bin/env python3
"""Check stable non-package compiler diagnostics JSON contracts."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path

from source_location_fixture_checks import expect_location_span_coherent


GENERATED_BACKEND_INPUT = "generated/backend-diagnostic.cgl"
ORIGINAL_BACKEND_INPUT = "shaders/backend-diagnostic.crossgl"
ORIGINAL_LINE_BASE = 80
ORIGINAL_OFFSET_BASE = 4000


@dataclass(frozen=True)
class DiagnosticExpectation:
    name: str
    command: tuple[str, ...]
    expected_code: str
    expected_file: str
    expected_line: int
    expected_column: int
    message_fragments: tuple[str, ...] = ()
    expected_target: str | None = None
    expected_missing_capabilities: tuple[str, ...] = ()
    expected_original_file: str | None = None
    expected_original_line: int | None = None
    expected_original_column: int | None = None


def run_command(
    cglc: Path,
    command: tuple[str, ...],
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [str(cglc), *command],
        check=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )


def validate_schema(
    root: Path,
    tmp_dir: Path,
    case_name: str,
    stdout: str,
) -> list[str]:
    instance_path = tmp_dir / f"{case_name}.diagnostics.json"
    instance_path.write_text(stdout, encoding="utf-8")
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
    if result.returncode == 0:
        return []
    return [
        f"{case_name}: diagnostics JSON failed schema validation: "
        f"{result.stderr}{result.stdout}".strip()
    ]


def source_span(file: str, text: str, *, line: int, offset: int) -> dict[str, object]:
    end_line = line
    column = 1
    end_column = column
    for char in text:
        if char == "\n":
            end_line += 1
            end_column = 1
        else:
            end_column += 1
    return {
        "file": file,
        "line": line,
        "column": column,
        "offset": offset,
        "length": len(text),
        "endLine": end_line,
        "endColumn": end_column,
        "endOffset": offset + len(text),
    }


def write_full_file_remap(source_path: Path, tmp_dir: Path) -> Path:
    source_text = source_path.read_text(encoding="utf-8")
    remap_path = tmp_dir / "backend-diagnostic-source-remap.json"
    remap = {
        "schemaVersion": 1,
        "generatedFile": GENERATED_BACKEND_INPUT,
        "mappings": [
            {
                "generated": source_span(
                    GENERATED_BACKEND_INPUT,
                    source_text,
                    line=1,
                    offset=0,
                ),
                "original": source_span(
                    ORIGINAL_BACKEND_INPUT,
                    source_text,
                    line=ORIGINAL_LINE_BASE,
                    offset=ORIGINAL_OFFSET_BASE,
                ),
            }
        ],
    }
    remap_path.write_text(json.dumps(remap, indent=2) + "\n", encoding="utf-8")
    return remap_path


def expect_location_fields(
    errors: list[str],
    case: DiagnosticExpectation,
    location: object,
) -> None:
    expect_location_span_coherent(errors, case.name, "diagnostics[0].location", location)
    if not isinstance(location, dict):
        return
    expected_fields = {
        "file": case.expected_file,
        "line": case.expected_line,
        "column": case.expected_column,
    }
    for field, expected in expected_fields.items():
        if location.get(field) != expected:
            errors.append(
                f"{case.name}: expected diagnostics[0].location.{field}="
                f"{expected!r}, got {location.get(field)!r}"
            )
    if not isinstance(location.get("length"), int) or location["length"] <= 0:
        errors.append(
            f"{case.name}: expected diagnostics[0].location.length to be "
            f"positive, got {location.get('length')!r}"
        )


def expect_original_location_fields(
    errors: list[str],
    case: DiagnosticExpectation,
    original_location: object,
) -> None:
    if case.expected_original_file is None:
        if original_location is not None:
            errors.append(
                f"{case.name}: did not expect originalLocation, got "
                f"{original_location!r}"
            )
        return

    expect_location_span_coherent(
        errors,
        case.name,
        "diagnostics[0].originalLocation",
        original_location,
    )
    if not isinstance(original_location, dict):
        return
    expected_fields = {
        "file": case.expected_original_file,
        "line": case.expected_original_line,
        "column": case.expected_original_column,
    }
    for field, expected in expected_fields.items():
        if original_location.get(field) != expected:
            errors.append(
                f"{case.name}: expected diagnostics[0].originalLocation.{field}="
                f"{expected!r}, got {original_location.get(field)!r}"
            )


def check_case(
    root: Path,
    cglc: Path,
    tmp_dir: Path,
    case: DiagnosticExpectation,
) -> list[str]:
    errors: list[str] = []
    result = run_command(cglc, case.command)
    if result.returncode == 0:
        errors.append(f"{case.name}: expected cglc command to fail")
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
    if payload.get("schemaVersion") != 1:
        errors.append(
            f"{case.name}: expected schemaVersion 1, got "
            f"{payload.get('schemaVersion')!r}"
        )

    diagnostics = payload.get("diagnostics")
    if not isinstance(diagnostics, list):
        errors.append(f"{case.name}: expected diagnostics array")
        return errors
    if len(diagnostics) != 1:
        errors.append(f"{case.name}: expected one diagnostic, got {len(diagnostics)}")
        return errors

    diagnostic = diagnostics[0]
    if not isinstance(diagnostic, dict):
        errors.append(f"{case.name}: expected diagnostics[0] to be an object")
        return errors
    if diagnostic.get("severity") != "error":
        errors.append(
            f"{case.name}: expected severity 'error', got "
            f"{diagnostic.get('severity')!r}"
        )
    if diagnostic.get("code") != case.expected_code:
        errors.append(
            f"{case.name}: expected code {case.expected_code!r}, got "
            f"{diagnostic.get('code')!r}"
        )

    message = diagnostic.get("message")
    if not isinstance(message, str):
        errors.append(f"{case.name}: expected diagnostic message string")
    else:
        for fragment in case.message_fragments:
            if fragment not in message:
                errors.append(
                    f"{case.name}: expected message to contain "
                    f"{fragment!r}, got {message!r}"
                )

    if case.expected_target is None:
        if "target" in diagnostic:
            errors.append(
                f"{case.name}: did not expect target, got {diagnostic.get('target')!r}"
            )
    elif diagnostic.get("target") != case.expected_target:
        errors.append(
            f"{case.name}: expected target {case.expected_target!r}, got "
            f"{diagnostic.get('target')!r}"
        )

    missing_capabilities = diagnostic.get("missingCapabilities", [])
    if tuple(missing_capabilities) != case.expected_missing_capabilities:
        errors.append(
            f"{case.name}: expected missingCapabilities "
            f"{case.expected_missing_capabilities!r}, got {missing_capabilities!r}"
        )

    expect_location_fields(errors, case, diagnostic.get("location"))
    expect_original_location_fields(errors, case, diagnostic.get("originalLocation"))
    return errors


def build_cases(root: Path, tmp_dir: Path) -> tuple[DiagnosticExpectation, ...]:
    parse_fixture = (
        root
        / "tests"
        / "frontend"
        / "fixtures"
        / "BadNamedVoidParameterShader.cgl"
    )
    sema_fixture = root / "tests" / "check-failures" / "BadTextureArityShader.cgl"
    opt_fixture = root / "tests" / "fixtures" / "RuntimeArrayNonFinalShader.cgl"
    backend_fixture = (
        root
        / "tests"
        / "vulkan"
        / "fixtures"
        / "VulkanRuntimeTextureDescriptorArrayConflictShader.cgl"
    )
    backend_output = tmp_dir / "backend-diagnostic.cglb"
    backend_remap = write_full_file_remap(backend_fixture, tmp_dir)

    return (
        DiagnosticExpectation(
            name="parse-invalid-void-parameter",
            command=("check", str(parse_fixture), "--diagnostics-json"),
            expected_code="parse.invalid-void-parameter",
            expected_file="tests/frontend/fixtures/BadNamedVoidParameterShader.cgl",
            expected_line=3,
            expected_column=15,
            message_fragments=("void parameter list",),
        ),
        DiagnosticExpectation(
            name="sema-texture-sample-arity",
            command=("check", str(sema_fixture), "--diagnostics-json"),
            expected_code="sema.texture-sample-arity",
            expected_file="tests/check-failures/BadTextureArityShader.cgl",
            expected_line=5,
            expected_column=20,
            message_fragments=("texture sample expects", "got 1 operand"),
        ),
        DiagnosticExpectation(
            name="optimizer-runtime-array-field",
            command=("check", str(opt_fixture), "--diagnostics-json"),
            expected_code="opt.hir-storage-buffer-runtime-array-field",
            expected_file="tests/fixtures/RuntimeArrayNonFinalShader.cgl",
            expected_line=3,
            expected_column=5,
            message_fragments=("payloads.values", "direct final field"),
        ),
        DiagnosticExpectation(
            name="backend-target-unsupported-remapped-location",
            command=(
                "build",
                str(backend_fixture),
                "--target",
                "vulkan",
                "--output",
                str(backend_output),
                "--logical-input",
                GENERATED_BACKEND_INPUT,
                "--source-remap",
                str(backend_remap),
                "--diagnostics-json",
            ),
            expected_code="target.unsupported",
            expected_file=GENERATED_BACKEND_INPUT,
            expected_line=5,
            expected_column=52,
            message_fragments=(
                "target 'vulkan' cannot build a package",
                "runtime descriptor array 'maps'",
                "TargetLegalizationResult: state=rejected",
            ),
            expected_target="vulkan",
            expected_missing_capabilities=(
                "vulkan.backend.vulkan-prototype-package",
                "vulkan.diagnostic.vulkan.prototype-unsupported-runtime-resource-array",
            ),
            expected_original_file=ORIGINAL_BACKEND_INPUT,
            expected_original_line=ORIGINAL_LINE_BASE + 4,
            expected_original_column=52,
        ),
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", required=True, type=Path)
    parser.add_argument("--cglc", required=True, type=Path)
    args = parser.parse_args()

    root = args.root.resolve()
    cglc = args.cglc.resolve()
    errors: list[str] = []
    with tempfile.TemporaryDirectory(prefix="crossgl-diagnostic-json-") as tmp:
        tmp_dir = Path(tmp)
        for case in build_cases(root, tmp_dir):
            errors.extend(check_case(root, cglc, tmp_dir, case))

    if errors:
        for error in errors:
            print(error, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
