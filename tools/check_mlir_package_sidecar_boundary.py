#!/usr/bin/env python3
"""Validate that production debug packages do not carry real MLIR sidecars.

This checker is intentionally MLIR-toolchain-free. When a cglc executable is
provided or discoverable under build/, it builds one normal package with debug
IR enabled and verifies that the only ``.mlir`` package files are the current
pseudo-MLIR sidecar and its legacy alias. Without cglc it validates the
checked-in package-shaped boundary fixtures. Real MLIR remains limited to the
experimental CMake gate.
"""

from __future__ import annotations

import argparse
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


FIXTURE = Path("tests/fixtures/SimpleShader.cgl")
BOUNDARY_FIXTURE_DIR = Path("tests/mlir-package-sidecar-boundary")
DEFAULT_TARGET = "opengl"
DEFAULT_CGLC_CANDIDATES = (
    Path("build/cglc"),
    Path("build/cglc.exe"),
    Path("build/Debug/cglc"),
    Path("build/Debug/cglc.exe"),
    Path("build/Release/cglc"),
    Path("build/Release/cglc.exe"),
    Path("build/RelWithDebInfo/cglc"),
    Path("build/RelWithDebInfo/cglc.exe"),
)
PSEUDO_MLIR_PATH = Path("ir/pseudo-mlir.mlir")
LEGACY_MLIR_ALIAS_PATH = Path("ir/mlir.mlir")
CROSSGL_DEBUG_MLIR_PATH = Path("ir/crossgl.mlir")
ALLOWED_MLIR_PATHS = {
    CROSSGL_DEBUG_MLIR_PATH,
    PSEUDO_MLIR_PATH,
    LEGACY_MLIR_ALIAS_PATH,
}
PSEUDO_MLIR_MARKERS = (
    "CrossGL pseudo-MLIR",
    "not a registered MLIR dialect",
    'crossgl.ir_kind = "pseudo-mlir"',
    'crossgl.real_mlir = "false"',
)
CROSSGL_DEBUG_MLIR_MARKERS = (
    "CrossGL textual IR: debug projection",
    "not a registered MLIR dialect",
    'crossgl.ir_kind = "crossgl-debug"',
    'crossgl.real_mlir = "false"',
)
REAL_MLIR_EXPERIMENT_PATTERNS = (
    (
        re.compile(r"\bcrossgl_real_mlir_smoke\s*=\s*true\b"),
        "crossgl_real_mlir_smoke = true",
    ),
    (
        re.compile(r"\bcrossgl_real_mlir\s*=\s*true\b"),
        "crossgl_real_mlir = true",
    ),
)
CANONICAL_REAL_HIR_DIALECT_PATTERN = re.compile(r"(?<![A-Za-z0-9_])hir\.")
OPTIONAL_REAL_MLIR_TOOL_MARKERS = (
    "mlir-opt",
    "--verify-diagnostics",
)
FORBIDDEN_PRODUCTION_MLIR_AUTHORITY_MARKERS = (
    "nativeBinary",
    "targetLegalization",
    "target_legalization",
    "target-legalization",
    "target legalization",
    "package verifier",
    "crossgl_mlir_experiment",
    "CROSSGL_ENABLE_MLIR_EXPERIMENTAL=ON",
    "MLIR_FOUND=TRUE",
)
FIXTURE_EXPECTATIONS = {
    "valid-pseudo-sidecars.package": None,
    "reject-registered-hir-dialect-masquerade.package": (
        "canonical real MLIR HIR dialect marker"
    ),
    "reject-real-mlir-smoke-in-pseudo-sidecar.package": ("real MLIR experiment marker"),
    "reject-target-legalization-authority-in-pseudo-sidecar.package": (
        "native compiler, package verifier, or MLIR experiment authority marker"
    ),
}


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def relative_package_files(package: Path) -> list[Path]:
    return sorted(
        path.relative_to(package) for path in package.rglob("*") if path.is_file()
    )


def check_package_mlir_boundary(package: Path) -> list[str]:
    errors: list[str] = []
    if not package.is_dir():
        return [f"package directory does not exist: {package}"]

    mlir_files = [
        path for path in relative_package_files(package) if path.suffix == ".mlir"
    ]
    extra_mlir_files = sorted(set(mlir_files) - ALLOWED_MLIR_PATHS)
    missing_mlir_files = sorted(ALLOWED_MLIR_PATHS - set(mlir_files))
    if extra_mlir_files:
        errors.append(
            "production package must not carry real or experimental MLIR sidecars: "
            + ", ".join(path.as_posix() for path in extra_mlir_files)
        )
    if missing_mlir_files:
        errors.append(
            "production debug package is missing pseudo-MLIR sidecar(s): "
            + ", ".join(path.as_posix() for path in missing_mlir_files)
        )
        return errors

    pseudo_text = read_text(package / PSEUDO_MLIR_PATH)
    legacy_text = read_text(package / LEGACY_MLIR_ALIAS_PATH)
    if legacy_text != pseudo_text:
        errors.append("legacy ir/mlir.mlir alias must match ir/pseudo-mlir.mlir")

    for marker in PSEUDO_MLIR_MARKERS:
        if marker not in pseudo_text:
            errors.append(
                f"{PSEUDO_MLIR_PATH.as_posix()} must contain pseudo-MLIR marker "
                f"{marker!r}"
            )
    for pattern, marker in REAL_MLIR_EXPERIMENT_PATTERNS:
        if pattern.search(pseudo_text) or pattern.search(legacy_text):
            errors.append(
                "production pseudo-MLIR sidecars must not contain real MLIR "
                f"experiment marker {marker!r}"
            )
    crossgl_text = read_text(package / CROSSGL_DEBUG_MLIR_PATH)
    for marker in CROSSGL_DEBUG_MLIR_MARKERS:
        if marker not in crossgl_text:
            errors.append(
                f"{CROSSGL_DEBUG_MLIR_PATH.as_posix()} must contain debug-only "
                f"MLIR boundary marker {marker!r}"
            )
    for pattern, marker in REAL_MLIR_EXPERIMENT_PATTERNS:
        if pattern.search(crossgl_text):
            errors.append(
                "production CrossGL debug sidecar must not contain real MLIR "
                f"experiment marker {marker!r}"
            )
    for path, text in (
        (PSEUDO_MLIR_PATH, pseudo_text),
        (LEGACY_MLIR_ALIAS_PATH, legacy_text),
        (CROSSGL_DEBUG_MLIR_PATH, crossgl_text),
    ):
        if CANONICAL_REAL_HIR_DIALECT_PATTERN.search(text):
            errors.append(
                f"{path.as_posix()} must not contain canonical real MLIR "
                "HIR dialect marker 'hir.'; pseudo-MLIR sidecars cannot "
                "masquerade as registered hir.* dialect output"
            )
        for marker in OPTIONAL_REAL_MLIR_TOOL_MARKERS:
            if marker in text:
                errors.append(
                    f"{path.as_posix()} must not contain optional MLIR tool "
                    f"execution marker {marker!r}; real MLIR verification "
                    "stays experiment-gated"
                )
        for marker in FORBIDDEN_PRODUCTION_MLIR_AUTHORITY_MARKERS:
            if marker in text:
                errors.append(
                    f"{path.as_posix()} must not contain native compiler, "
                    "package verifier, or MLIR experiment authority marker "
                    f"{marker!r}"
                )
    return errors


def run_build(root: Path, cglc: Path, package: Path, target: str) -> list[str]:
    fixture = root / FIXTURE
    if not fixture.is_file():
        return [f"fixture missing: {FIXTURE.as_posix()}"]
    result = subprocess.run(
        [
            str(cglc),
            "build",
            str(fixture),
            "--target",
            target,
            "--output",
            str(package),
            "--debug-ir",
        ],
        cwd=root,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if result.returncode != 0:
        return [
            "failed to build production debug package for MLIR sidecar boundary: "
            f"stdout: {result.stdout.strip()} stderr: {result.stderr.strip()}"
        ]
    return []


def discover_cglc(root: Path) -> Path | None:
    for candidate in DEFAULT_CGLC_CANDIDATES:
        path = root / candidate
        if path.is_file():
            return path.resolve()
    return None


def write_valid_package(package: Path) -> None:
    ir_dir = package / "ir"
    ir_dir.mkdir(parents=True)
    pseudo_text = "\n".join(PSEUDO_MLIR_MARKERS) + "\n"
    (package / PSEUDO_MLIR_PATH).write_text(pseudo_text, encoding="utf-8")
    (package / LEGACY_MLIR_ALIAS_PATH).write_text(pseudo_text, encoding="utf-8")
    (package / CROSSGL_DEBUG_MLIR_PATH).write_text(
        "\n".join(CROSSGL_DEBUG_MLIR_MARKERS) + "\n",
        encoding="utf-8",
    )


def check_fixture_packages(root: Path | None = None) -> list[str]:
    failures: list[str] = []
    repo_root = root if root is not None else Path(__file__).resolve().parents[1]
    fixture_root = repo_root / BOUNDARY_FIXTURE_DIR
    if not fixture_root.is_dir():
        return [f"fixture directory missing: {BOUNDARY_FIXTURE_DIR.as_posix()}"]

    actual_cases = {path.name for path in fixture_root.iterdir() if path.is_dir()}
    expected_cases = set(FIXTURE_EXPECTATIONS)
    missing_cases = sorted(expected_cases - actual_cases)
    unexpected_cases = sorted(actual_cases - expected_cases)
    if missing_cases:
        failures.append(
            "missing MLIR package sidecar boundary fixture(s): "
            + ", ".join(missing_cases)
        )
    if unexpected_cases:
        failures.append(
            "unlisted MLIR package sidecar boundary fixture(s): "
            + ", ".join(unexpected_cases)
        )

    for case_name, expected_error in FIXTURE_EXPECTATIONS.items():
        package = fixture_root / case_name
        if not package.is_dir():
            continue
        errors = check_package_mlir_boundary(package)
        if expected_error is None:
            if errors:
                failures.append(
                    f"fixture {case_name} should pass but was rejected: "
                    + "; ".join(errors)
                )
        elif not any(expected_error in error for error in errors):
            failures.append(
                f"fixture {case_name} should be rejected with "
                f"{expected_error!r}, got: "
                + ("; ".join(errors) if errors else "no errors")
            )
    return failures


def run_self_test() -> int:
    failures: list[str] = []
    with tempfile.TemporaryDirectory(
        prefix="crossgl-mlir-sidecar-boundary-self-"
    ) as tmp:
        package = Path(tmp) / "valid.cglb"
        write_valid_package(package)
        errors = check_package_mlir_boundary(package)
        if errors:
            failures.append(
                "valid pseudo-MLIR package was rejected: " + "; ".join(errors)
            )

        extra = Path(tmp) / "extra-real.cglb"
        shutil.copytree(package, extra)
        real_dir = extra / "ir" / "experimental"
        real_dir.mkdir(parents=True)
        (real_dir / "real.mlir").write_text(
            "module attributes {crossgl_real_mlir_smoke = true} {}\n",
            encoding="utf-8",
        )
        errors = check_package_mlir_boundary(extra)
        if not any(
            "must not carry real or experimental MLIR" in error for error in errors
        ):
            failures.append("extra real MLIR sidecar was not rejected")

        missing_marker = Path(tmp) / "missing-marker.cglb"
        shutil.copytree(package, missing_marker)
        (missing_marker / PSEUDO_MLIR_PATH).write_text(
            'crossgl.ir_kind = "pseudo-mlir"\n',
            encoding="utf-8",
        )
        (missing_marker / LEGACY_MLIR_ALIAS_PATH).write_text(
            'crossgl.ir_kind = "pseudo-mlir"\n',
            encoding="utf-8",
        )
        errors = check_package_mlir_boundary(missing_marker)
        if not any("must contain pseudo-MLIR marker" in error for error in errors):
            failures.append("missing pseudo-MLIR marker was not rejected")

        alias_mismatch = Path(tmp) / "alias-mismatch.cglb"
        shutil.copytree(package, alias_mismatch)
        (alias_mismatch / LEGACY_MLIR_ALIAS_PATH).write_text(
            read_text(alias_mismatch / PSEUDO_MLIR_PATH) + "// changed\n",
            encoding="utf-8",
        )
        errors = check_package_mlir_boundary(alias_mismatch)
        if not any("legacy ir/mlir.mlir alias must match" in error for error in errors):
            failures.append("legacy alias mismatch was not rejected")

        unlabeled_crossgl = Path(tmp) / "unlabeled-crossgl.cglb"
        shutil.copytree(package, unlabeled_crossgl)
        (unlabeled_crossgl / CROSSGL_DEBUG_MLIR_PATH).write_text(
            "crossgl.module @Unlabeled {}\n",
            encoding="utf-8",
        )
        errors = check_package_mlir_boundary(unlabeled_crossgl)
        if not any(
            "must contain debug-only MLIR boundary marker" in error for error in errors
        ):
            failures.append("unlabeled CrossGL debug sidecar was not rejected")

        native_authority_marker = Path(tmp) / "native-authority-marker.cglb"
        shutil.copytree(package, native_authority_marker)
        (native_authority_marker / PSEUDO_MLIR_PATH).write_text(
            read_text(native_authority_marker / PSEUDO_MLIR_PATH)
            + "// nativeBinary evidence belongs to package metadata, not MLIR\n",
            encoding="utf-8",
        )
        (native_authority_marker / LEGACY_MLIR_ALIAS_PATH).write_text(
            read_text(native_authority_marker / PSEUDO_MLIR_PATH),
            encoding="utf-8",
        )
        errors = check_package_mlir_boundary(native_authority_marker)
        if not any(
            "native compiler, package verifier, or MLIR experiment authority marker"
            in error
            for error in errors
        ):
            failures.append("native authority marker in pseudo-MLIR was not rejected")

        target_legalization_authority_marker = (
            Path(tmp) / "target-legalization-authority-marker.cglb"
        )
        shutil.copytree(package, target_legalization_authority_marker)
        (target_legalization_authority_marker / PSEUDO_MLIR_PATH).write_text(
            read_text(target_legalization_authority_marker / PSEUDO_MLIR_PATH)
            + (
                "// target_legalization_facts parity belongs to release gates, "
                "not MLIR sidecars\n"
            ),
            encoding="utf-8",
        )
        (target_legalization_authority_marker / LEGACY_MLIR_ALIAS_PATH).write_text(
            read_text(target_legalization_authority_marker / PSEUDO_MLIR_PATH),
            encoding="utf-8",
        )
        errors = check_package_mlir_boundary(target_legalization_authority_marker)
        if not any(
            "native compiler, package verifier, or MLIR experiment authority marker"
            in error
            for error in errors
        ):
            failures.append(
                "target-legalization authority marker in pseudo-MLIR was not rejected"
            )

        registered_hir_dialect = Path(tmp) / "registered-hir-dialect.cglb"
        shutil.copytree(package, registered_hir_dialect)
        (registered_hir_dialect / PSEUDO_MLIR_PATH).write_text(
            read_text(registered_hir_dialect / PSEUDO_MLIR_PATH)
            + "hir.module @Masquerade {}\n",
            encoding="utf-8",
        )
        (registered_hir_dialect / LEGACY_MLIR_ALIAS_PATH).write_text(
            read_text(registered_hir_dialect / PSEUDO_MLIR_PATH),
            encoding="utf-8",
        )
        errors = check_package_mlir_boundary(registered_hir_dialect)
        if not any(
            "canonical real MLIR HIR dialect marker" in error for error in errors
        ):
            failures.append(
                "registered hir.* dialect marker in pseudo-MLIR was not rejected"
            )

        optional_tool_marker = Path(tmp) / "optional-tool-marker.cglb"
        shutil.copytree(package, optional_tool_marker)
        (optional_tool_marker / PSEUDO_MLIR_PATH).write_text(
            read_text(optional_tool_marker / PSEUDO_MLIR_PATH)
            + "// mlir-opt --verify-diagnostics belongs to optional tests\n",
            encoding="utf-8",
        )
        (optional_tool_marker / LEGACY_MLIR_ALIAS_PATH).write_text(
            read_text(optional_tool_marker / PSEUDO_MLIR_PATH),
            encoding="utf-8",
        )
        errors = check_package_mlir_boundary(optional_tool_marker)
        if not any("optional MLIR tool execution marker" in error for error in errors):
            failures.append("optional MLIR tool marker in pseudo-MLIR was not rejected")

    failures.extend(check_fixture_packages())

    if failures:
        for failure in failures:
            print(
                f"MLIR package sidecar boundary self-test failed: {failure}",
                file=sys.stderr,
            )
        return 1
    print("MLIR package sidecar boundary self-test passed")
    return 0


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--cglc", type=Path)
    parser.add_argument("--target", default=DEFAULT_TARGET)
    parser.add_argument("--self-test", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    if args.self_test:
        return run_self_test()

    root = args.root.resolve()
    cglc = args.cglc.resolve() if args.cglc is not None else discover_cglc(root)
    if cglc is None:
        errors = check_fixture_packages(root)
        if errors:
            for error in errors:
                print(
                    f"MLIR package sidecar boundary check failed: {error}",
                    file=sys.stderr,
                )
            return 1
        print(
            "validated checked-in MLIR package sidecar boundary fixtures; "
            "no cglc supplied or autodetected for production package build"
        )
        return 0

    with tempfile.TemporaryDirectory(prefix="crossgl-mlir-sidecar-boundary-") as tmp:
        package = Path(tmp) / "production-debug.cglb"
        errors = run_build(root, cglc, package, args.target)
        if not errors:
            errors = check_package_mlir_boundary(package)

    if errors:
        for error in errors:
            print(
                f"MLIR package sidecar boundary check failed: {error}",
                file=sys.stderr,
            )
        return 1
    print(
        "validated production package MLIR sidecar boundary: "
        f"target={args.target}; allowed=.cglb/{PSEUDO_MLIR_PATH.as_posix()}, "
        f".cglb/{LEGACY_MLIR_ALIAS_PATH.as_posix()}, "
        f".cglb/{CROSSGL_DEBUG_MLIR_PATH.as_posix()}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
