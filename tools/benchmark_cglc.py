#!/usr/bin/env python3
"""Run local cglc workflow benchmarks over CrossGL source fixtures."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import stat
import subprocess
import sys
import tempfile
from pathlib import Path
from time import perf_counter_ns


SCHEMA_VERSION = 1
DEFAULT_MODES = ("check",)

MODE_COMMANDS = {
    "check": ("check", "{input}"),
    "check-json": ("check", "{input}", "--diagnostics-json"),
    "dump-hir": ("dump-ir", "{input}", "--stage", "hir"),
    "dump-debug": ("dump-ir", "{input}", "--stage", "debug"),
    "dump-hir-source-map": ("dump-ir", "{input}", "--stage", "hir-source-map"),
}


class BenchmarkError(RuntimeError):
    """Raised for user-facing benchmark configuration failures."""


def parse_non_negative_int(value):
    try:
        parsed = int(value, 10)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(f"expected integer, got {value!r}") from exc
    if parsed < 0:
        raise argparse.ArgumentTypeError(f"expected non-negative integer, got {value}")
    return parsed


def parse_positive_int(value):
    parsed = parse_non_negative_int(value)
    if parsed == 0:
        raise argparse.ArgumentTypeError("expected positive integer, got 0")
    return parsed


def path_text(path):
    return path.as_posix()


def display_path(path, root):
    resolved = path.resolve()
    try:
        return path_text(resolved.relative_to(root))
    except ValueError:
        return path_text(resolved)


def resolve_existing_path(path, root):
    candidate = Path(path).expanduser()
    if not candidate.is_absolute():
        candidate = root / candidate
    return candidate.resolve()


def expand_inputs(inputs, root):
    if not inputs:
        raise BenchmarkError("at least one input file or directory is required")

    selected = []
    seen = set()
    for input_arg in inputs:
        path = resolve_existing_path(input_arg, root)
        if not path.exists():
            raise BenchmarkError(f"input does not exist: {input_arg}")
        if path.is_dir():
            candidates = sorted(
                candidate.resolve()
                for candidate in path.rglob("*.cgl")
                if candidate.is_file()
            )
            if not candidates:
                raise BenchmarkError(
                    f"input directory contains no .cgl files: {input_arg}"
                )
        elif path.is_file():
            if path.suffix != ".cgl":
                raise BenchmarkError(f"input file is not a .cgl fixture: {input_arg}")
            candidates = [path]
        else:
            raise BenchmarkError(f"input is not a file or directory: {input_arg}")

        for candidate in candidates:
            key = candidate.resolve()
            if key in seen:
                continue
            seen.add(key)
            selected.append(key)

    selected.sort(key=lambda item: display_path(item, root))
    return selected


def looks_like_path(value):
    return Path(value).is_absolute() or any(
        separator and separator in value for separator in (os.sep, os.altsep)
    )


def resolve_cglc(value, root):
    requested = value or os.environ.get("CGLC") or "cglc"
    if looks_like_path(requested):
        candidate = Path(requested).expanduser()
        if not candidate.is_absolute():
            candidate = root / candidate
        path = candidate.resolve()
    else:
        found = shutil.which(requested)
        if found is None:
            raise BenchmarkError(
                f"missing cglc executable {requested!r}; pass --cglc /path/to/cglc "
                "or add cglc to PATH"
            )
        path = Path(found).resolve()

    if not path.is_file():
        raise BenchmarkError(
            f"missing cglc executable: {path}; pass --cglc /path/to/cglc"
        )
    if not os.access(path, os.X_OK):
        raise BenchmarkError(f"cglc is not executable: {path}")
    return path


def command_for_mode(mode, input_arg, cglc):
    try:
        template = MODE_COMMANDS[mode]
    except KeyError as exc:
        raise BenchmarkError(f"unsupported mode: {mode}") from exc
    return [
        path_text(cglc),
        *(part if part != "{input}" else input_arg for part in template),
    ]


def display_command_for_mode(mode, input_arg):
    try:
        template = MODE_COMMANDS[mode]
    except KeyError as exc:
        raise BenchmarkError(f"unsupported mode: {mode}") from exc
    return ["<cglc>", *(part if part != "{input}" else input_arg for part in template)]


def run_once(command, root, iteration):
    started_ns = perf_counter_ns()
    try:
        result = subprocess.run(
            command,
            cwd=root,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        exit_status = result.returncode
        stdout_bytes = len(result.stdout)
        stderr_bytes = len(result.stderr)
    finally:
        duration_ns = perf_counter_ns() - started_ns

    return {
        "durationNs": duration_ns,
        "exitStatus": exit_status,
        "iteration": iteration,
        "outputBytes": stdout_bytes + stderr_bytes,
        "stderrBytes": stderr_bytes,
        "stdoutBytes": stdout_bytes,
    }


def summarize_runs(runs):
    durations = sorted(run["durationNs"] for run in runs)
    stdout_sizes = sorted({run["stdoutBytes"] for run in runs})
    stderr_sizes = sorted({run["stderrBytes"] for run in runs})
    output_sizes = sorted({run["outputBytes"] for run in runs})
    exit_statuses = sorted({run["exitStatus"] for run in runs})
    return {
        "exitStatuses": exit_statuses,
        "maxNs": durations[-1],
        "meanNs": sum(durations) // len(durations),
        "medianNs": durations[len(durations) // 2],
        "minNs": durations[0],
        "outputBytes": output_sizes,
        "stderrBytes": stderr_sizes,
        "stdoutBytes": stdout_sizes,
    }


def run_case(cglc, root, mode, input_path, warmup, repeat):
    input_display = display_path(input_path, root)
    command = command_for_mode(mode, input_display, cglc)
    display_command = display_command_for_mode(mode, input_display)

    warmups = [run_once(command, root, iteration) for iteration in range(1, warmup + 1)]
    runs = [run_once(command, root, iteration) for iteration in range(1, repeat + 1)]

    return {
        "case": f"{input_display}::{mode}",
        "command": display_command,
        "input": input_display,
        "mode": mode,
        "runs": runs,
        "summary": summarize_runs(runs),
        "warmups": warmups,
    }


def count_command_failures(cases):
    return sum(
        1
        for case in cases
        for run in [*case["warmups"], *case["runs"]]
        if run["exitStatus"] != 0
    )


def build_report(cglc, root, inputs, modes, warmup, repeat):
    cases = [
        run_case(cglc, root, mode, input_path, warmup, repeat)
        for input_path in inputs
        for mode in modes
    ]
    failure_count = count_command_failures(cases)
    return {
        "cases": cases,
        "config": {
            "cglc": path_text(cglc),
            "inputs": [display_path(input_path, root) for input_path in inputs],
            "modes": list(modes),
            "repeat": repeat,
            "root": path_text(root),
            "warmup": warmup,
        },
        "schemaVersion": SCHEMA_VERSION,
        "summary": {
            "caseCount": len(cases),
            "commandFailureCount": failure_count,
            "inputCount": len(inputs),
            "measuredRunCount": len(cases) * repeat,
            "modeCount": len(modes),
            "warmupRunCount": len(cases) * warmup,
        },
        "tool": "benchmark_cglc",
    }


def format_duration(ns):
    if ns >= 1_000_000_000:
        return f"{ns / 1_000_000_000:.3f}s"
    if ns >= 1_000_000:
        return f"{ns / 1_000_000:.3f}ms"
    if ns >= 1_000:
        return f"{ns / 1_000:.3f}us"
    return f"{ns}ns"


def format_sizes(values):
    if len(values) == 1:
        return str(values[0])
    return f"{values[0]}..{values[-1]}"


def write_summary(report, stream):
    config = report["config"]
    summary = report["summary"]
    print(
        "cglc benchmark: "
        f"{summary['measuredRunCount']} measured run(s), "
        f"{summary['warmupRunCount']} warmup run(s), "
        f"{summary['caseCount']} case(s)",
        file=stream,
    )
    print(
        "config: "
        f"modes={','.join(config['modes'])} "
        f"warmup={config['warmup']} repeat={config['repeat']}",
        file=stream,
    )
    for case in report["cases"]:
        case_summary = case["summary"]
        status = ",".join(str(value) for value in case_summary["exitStatuses"])
        print(
            f"{case['input']} [{case['mode']}]: "
            f"min={format_duration(case_summary['minNs'])} "
            f"median={format_duration(case_summary['medianNs'])} "
            f"mean={format_duration(case_summary['meanNs'])} "
            f"max={format_duration(case_summary['maxNs'])} "
            f"exit={status} "
            f"stdout={format_sizes(case_summary['stdoutBytes'])}B "
            f"stderr={format_sizes(case_summary['stderrBytes'])}B",
            file=stream,
        )
    if summary["commandFailureCount"]:
        print(
            f"command failures recorded: {summary['commandFailureCount']}",
            file=stream,
        )


def parse_modes(values):
    modes = []
    seen = set()
    for value in values or DEFAULT_MODES:
        for mode in value.split(","):
            mode = mode.strip()
            if not mode:
                continue
            if mode not in MODE_COMMANDS:
                supported = ", ".join(sorted(MODE_COMMANDS))
                raise BenchmarkError(
                    f"unsupported mode {mode!r}; supported: {supported}"
                )
            if mode in seen:
                continue
            seen.add(mode)
            modes.append(mode)
    return modes


def write_json_report(report, output_path):
    text = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if output_path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(text, encoding="utf-8")
    else:
        sys.stdout.write(text)


def parse_args(argv):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "inputs",
        nargs="*",
        help="One or more .cgl files or directories scanned recursively for .cgl files.",
    )
    parser.add_argument(
        "--root",
        type=Path,
        default=Path.cwd(),
        help="Repository/root directory used for relative paths and command cwd.",
    )
    parser.add_argument(
        "--cglc",
        help="Path to a built cglc executable. Defaults to CGLC or cglc on PATH.",
    )
    parser.add_argument(
        "--mode",
        action="append",
        help=(
            "Benchmark mode. Repeat or comma-separate values. Supported: "
            + ", ".join(sorted(MODE_COMMANDS))
            + ". Default: check."
        ),
    )
    parser.add_argument(
        "--warmup",
        type=parse_non_negative_int,
        default=1,
        help="Warmup command runs per input/mode before measured repeats.",
    )
    parser.add_argument(
        "--repeat",
        type=parse_positive_int,
        default=3,
        help="Measured command runs per input/mode.",
    )
    parser.add_argument(
        "--json-output",
        type=Path,
        help=(
            "Write JSON to this path and print the readable summary to stdout. "
            "Without this, JSON is written to stdout and the summary to stderr."
        ),
    )
    parser.add_argument(
        "--allow-command-failures",
        action="store_true",
        help="Return success even when benchmarked cglc commands exit non-zero.",
    )
    parser.add_argument(
        "--self-test",
        action="store_true",
        help="Run the harness self-test with a fake local cglc.",
    )
    return parser.parse_args(argv)


def make_fake_cglc(root):
    script = root / "fake_cglc.py"
    script.write_text(
        """\
#!/usr/bin/env python3
import pathlib
import sys

args = sys.argv[1:]
if len(args) >= 2 and args[0] == "check":
    print(f"check passed: {pathlib.Path(args[1]).name}")
    raise SystemExit(0)
if len(args) >= 4 and args[0] == "dump-ir" and args[2:] == ["--stage", "hir"]:
    print(f"HIR for {pathlib.Path(args[1]).name}")
    raise SystemExit(0)
print("unexpected fake cglc invocation: " + " ".join(args), file=sys.stderr)
raise SystemExit(9)
""",
        encoding="utf-8",
    )
    script.chmod(script.stat().st_mode | stat.S_IXUSR)

    if os.name == "nt":
        wrapper = root / "fake-cglc.cmd"
        wrapper.write_text(
            f'@echo off\n"{sys.executable}" "%~dp0{script.name}" %*\n',
            encoding="utf-8",
        )
        return wrapper
    return script


def run_self_test():
    with tempfile.TemporaryDirectory(prefix="crossgl-cglc-bench-self-test-") as tmp:
        root = Path(tmp)
        fixtures = root / "fixtures"
        fixtures.mkdir()
        (fixtures / "B.cgl").write_text("// fixture B\n", encoding="utf-8")
        (fixtures / "A.cgl").write_text("// fixture A\n", encoding="utf-8")
        fake_cglc = make_fake_cglc(root)
        report_path = root / "result.json"

        result = subprocess.run(
            [
                sys.executable,
                __file__,
                "--root",
                str(root),
                "--cglc",
                str(fake_cglc),
                "--mode",
                "check,dump-hir",
                "--warmup",
                "1",
                "--repeat",
                "2",
                "--json-output",
                str(report_path),
                "fixtures",
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=False,
        )
        if result.returncode != 0:
            raise BenchmarkError(
                "self-test benchmark run failed: "
                + (result.stderr or result.stdout).strip()
            )
        report = json.loads(report_path.read_text(encoding="utf-8"))
        if report["summary"]["caseCount"] != 4:
            raise BenchmarkError("self-test expected four input/mode cases")
        if report["summary"]["measuredRunCount"] != 8:
            raise BenchmarkError("self-test expected eight measured runs")
        if report["summary"]["warmupRunCount"] != 4:
            raise BenchmarkError("self-test expected four warmup runs")
        if report["config"]["inputs"] != ["fixtures/A.cgl", "fixtures/B.cgl"]:
            raise BenchmarkError("self-test input expansion was not deterministic")
        dump_cases = [case for case in report["cases"] if case["mode"] == "dump-hir"]
        if not all(
            case["command"][1:] == ["dump-ir", case["input"], "--stage", "hir"]
            for case in dump_cases
        ):
            raise BenchmarkError("self-test dump-hir command mapping is invalid")
        if report["summary"]["commandFailureCount"] != 0:
            raise BenchmarkError("self-test recorded unexpected command failures")

        missing = subprocess.run(
            [
                sys.executable,
                __file__,
                "--root",
                str(root),
                "--cglc",
                str(root / "missing-cglc"),
                "fixtures/A.cgl",
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=False,
        )
        if missing.returncode != 2 or "missing cglc executable" not in missing.stderr:
            raise BenchmarkError("self-test missing-cglc failure was not clear")

    print("benchmark_cglc self-test passed")
    return 0


def main(argv=None):
    args = parse_args(argv or sys.argv[1:])
    if args.self_test:
        try:
            return run_self_test()
        except (BenchmarkError, OSError, subprocess.SubprocessError) as exc:
            print(f"benchmark_cglc self-test failed: {exc}", file=sys.stderr)
            return 1

    root = args.root.expanduser().resolve()
    try:
        if not root.is_dir():
            raise BenchmarkError(f"root directory does not exist: {root}")
        modes = parse_modes(args.mode)
        cglc = resolve_cglc(args.cglc, root)
        inputs = expand_inputs(args.inputs, root)
        report = build_report(cglc, root, inputs, modes, args.warmup, args.repeat)
        write_json_report(report, args.json_output)
        write_summary(report, sys.stdout if args.json_output else sys.stderr)
    except (BenchmarkError, OSError, subprocess.SubprocessError) as exc:
        print(f"cglc benchmark failed: {exc}", file=sys.stderr)
        return 2

    if report["summary"]["commandFailureCount"] and not args.allow_command_failures:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
