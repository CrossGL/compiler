#!/usr/bin/env python3
"""Validate v0 target-independent optimizer evidence from HIR pass traces."""

from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path
from typing import Any


VALIDATION_FIXTURE = Path(
    "tests/optimizer/fixtures/WorkgroupBarrierOptimizerBoundaryShader.cgl"
)
O2_INLINE_FIXTURE = Path(
    "tests/optimizer/fixtures/O2TemporaryInliningOptimizerShader.cgl"
)

O0_PASS_IDS = [
    "hir.validate.module-shape",
    "hir.validate.typed-symbols",
    "hir.validate.storage-buffer-shapes",
]

O1_PASS_IDS = [
    "hir.validate.module-shape",
    "hir.validate.typed-symbols",
    "hir.optimize.fold-constant-intrinsics",
    "hir.optimize.simplify-algebraic",
    "hir.optimize.propagate-local-scalars",
    "hir.optimize.cleanup-constant-branches",
    "hir.optimize.cleanup-unreachable-statements",
    "hir.optimize.cleanup-dead-local-declarations",
    "hir.optimize.cleanup-dead-local-stores",
    "hir.validate.storage-buffer-shapes",
]

O2_ONLY_PASS_IDS = [
    "hir.optimize.o2.inline-scalar-temporaries",
    "hir.optimize.o2.inline-literal-vector-temporaries",
]
O2_PASS_IDS = O1_PASS_IDS[:-1] + O2_ONLY_PASS_IDS + O1_PASS_IDS[-1:]
HIR_MODULE_STAT_FIELDS = (
    "structCount",
    "constantCount",
    "stageCount",
    "resourceCount",
    "functionCount",
    "statementCount",
    "expressionCount",
)

EXPECTED_POLICIES = {
    "O0": {
        "id": "hir-o0-validation-only",
        "name": "O0 validation-only",
        "description_fragment": "no optimization transforms are scheduled",
        "passes": O0_PASS_IDS,
    },
    "O1": {
        "id": "hir-o1-safe-cleanup",
        "name": "O1 safe cleanup",
        "description_fragment": "Default safe HIR cleanup and folding policy",
        "passes": O1_PASS_IDS,
    },
    "O2": {
        "id": "hir-o2-conservative-inline",
        "name": "O2 conservative inline",
        "description_fragment": "conservative temporary inlining",
        "passes": O2_PASS_IDS,
    },
}

CLAIM_FIXTURES = [
    {
        "claim": "v0.optimizer.o0.validation_only",
        "fixture": VALIDATION_FIXTURE,
        "level": "O0",
        "reason": "O0 schedules validation passes only and reports no changes.",
    },
    {
        "claim": "v0.optimizer.o2.distinct_pass_trace",
        "fixture": O2_INLINE_FIXTURE,
        "level": "O2",
        "reason": "O2 schedules and changes its conservative inline passes.",
    },
]


class CheckError(RuntimeError):
    """Raised when optimizer evidence does not satisfy the v0 contract."""


def run_cglc(cglc: Path, root: Path, fixture: Path, opt_level: str) -> dict[str, Any]:
    command = [
        str(cglc),
        "dump-ir",
        str(fixture),
        "--stage",
        "hir-pass-trace",
        "--opt-level",
        opt_level,
    ]
    result = subprocess.run(
        command,
        cwd=root,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if result.returncode != 0:
        raise CheckError(
            f"{' '.join(command)} failed with exit code {result.returncode}\n"
            f"stdout:\n{result.stdout}\n"
            f"stderr:\n{result.stderr}"
        )
    try:
        trace = json.loads(result.stdout)
    except json.JSONDecodeError as error:
        raise CheckError(f"{fixture}: pass trace is not valid JSON: {error}") from error
    if not isinstance(trace, dict):
        raise CheckError(f"{fixture}: pass trace root must be a JSON object")
    return trace


def require(condition: bool, message: str) -> None:
    if not condition:
        raise CheckError(message)


def require_object(value: Any, path: str) -> dict[str, Any]:
    require(isinstance(value, dict), f"{path} must be an object")
    return value


def require_nonnegative_int(value: Any, path: str) -> int:
    require(type(value) is int and value >= 0, f"{path} must be a non-negative integer")
    return value


def pass_ids(trace: dict[str, Any]) -> list[str]:
    passes = trace.get("passes")
    require(isinstance(passes, list), "passes must be a list")
    ids: list[str] = []
    for index, pass_record in enumerate(passes):
        require(isinstance(pass_record, dict), f"passes[{index}] must be an object")
        pass_id = pass_record.get("id")
        require(isinstance(pass_id, str), f"passes[{index}].id must be a string")
        ids.append(pass_id)
    return ids


def pass_schedule_fingerprint(ids: list[str]) -> str:
    hash_value = 14695981039346656037

    def update_byte(byte: int) -> None:
        nonlocal hash_value
        hash_value ^= byte
        hash_value = (hash_value * 1099511628211) & 0xFFFFFFFFFFFFFFFF

    def update_string(value: str) -> None:
        encoded = value.encode("utf-8")
        size = len(encoded)
        for shift in range(0, 64, 8):
            update_byte((size >> shift) & 0xFF)
        for byte in encoded:
            update_byte(byte)

    update_string("scheduled-pass-ids-v1")
    for pass_id in ids:
        update_string(pass_id)
    return f"fnv1a64:{hash_value:016x}"


def pass_by_id(trace: dict[str, Any], pass_id: str) -> dict[str, Any]:
    for pass_record in trace.get("passes", []):
        if isinstance(pass_record, dict) and pass_record.get("id") == pass_id:
            return pass_record
    raise CheckError(f"pass trace omitted {pass_id}")


def validate_module_stats(
    pass_record: dict[str, Any], opt_level: str, index: int, pass_id: str
) -> None:
    pass_prefix = f"{opt_level} passes[{index}]"
    require_nonnegative_int(
        pass_record.get("elapsedTimeMicroseconds"),
        f"{pass_prefix}.elapsedTimeMicroseconds",
    )

    module_stats = require_object(
        pass_record.get("moduleStats"), f"{pass_prefix}.moduleStats"
    )
    before = require_object(
        module_stats.get("before"), f"{pass_prefix}.moduleStats.before"
    )
    after = require_object(
        module_stats.get("after"), f"{pass_prefix}.moduleStats.after"
    )
    delta = require_object(
        module_stats.get("delta"), f"{pass_prefix}.moduleStats.delta"
    )

    any_delta = False
    for field in HIR_MODULE_STAT_FIELDS:
        before_value = require_nonnegative_int(
            before.get(field), f"{pass_prefix}.moduleStats.before.{field}"
        )
        after_value = require_nonnegative_int(
            after.get(field), f"{pass_prefix}.moduleStats.after.{field}"
        )
        delta_value = require_nonnegative_int(
            delta.get(field), f"{pass_prefix}.moduleStats.delta.{field}"
        )
        expected_delta = abs(after_value - before_value)
        require(
            delta_value == expected_delta,
            f"{opt_level} pass {pass_id} moduleStats.delta.{field} "
            "must equal abs(after-before)",
        )
        any_delta = any_delta or delta_value != 0

    if pass_record.get("changed") is False:
        require(
            not any_delta,
            f"{opt_level} pass {pass_id} reports changed=false but moduleStats "
            "delta is nonzero",
        )


def validate_common_trace(trace: dict[str, Any], opt_level: str) -> list[str]:
    expected = EXPECTED_POLICIES[opt_level]
    expected_passes = expected["passes"]
    ids = pass_ids(trace)

    require(trace.get("schemaVersion") == 1, "schemaVersion must be 1")
    require(trace.get("kind") == "hir-pass-trace", "kind must be hir-pass-trace")
    require(
        trace.get("optimizationLevel") == opt_level,
        f"optimizationLevel must be {opt_level}",
    )
    require(
        trace.get("scheduledPassCount") == len(expected_passes),
        f"{opt_level} scheduledPassCount must be {len(expected_passes)}",
    )
    require(
        trace.get("passCount") == len(expected_passes),
        f"{opt_level} passCount must be {len(expected_passes)}",
    )
    require(ids == expected_passes, f"{opt_level} pass order drifted: {ids!r}")
    require(trace.get("completed") is True, f"{opt_level} trace must complete")
    require(trace.get("stopReason") == "none", f"{opt_level} stopReason must be none")
    require(
        trace.get("diagnosticPassCount") == 0,
        f"{opt_level} diagnosticPassCount must be 0",
    )
    require(
        trace.get("errorPassCount") == 0,
        f"{opt_level} errorPassCount must be 0",
    )

    policy = trace.get("optimizationPolicy")
    require(isinstance(policy, dict), "optimizationPolicy must be an object")
    require(policy.get("id") == expected["id"], f"{opt_level} policy id drifted")
    require(policy.get("name") == expected["name"], f"{opt_level} policy name drifted")
    description = policy.get("description")
    require(
        isinstance(description, str)
        and expected["description_fragment"] in description,
        f"{opt_level} policy description drifted",
    )
    require(
        policy.get("backendInputMode") == "source-validation",
        f"{opt_level} dump-ir HIR trace must use source-validation mode",
    )
    schedule = trace.get("passSchedule")
    require(isinstance(schedule, dict), "passSchedule must be an object")
    require(
        schedule.get("fingerprint") == pass_schedule_fingerprint(ids),
        f"{opt_level} pass schedule fingerprint drifted",
    )
    require(
        schedule.get("fingerprintPolicy") == "scheduled-pass-ids-v1",
        f"{opt_level} pass schedule fingerprint policy drifted",
    )
    require(
        schedule.get("stability") == "stable-opt-level-policy",
        f"{opt_level} pass schedule stability drifted",
    )

    changed_count = 0
    for index, pass_record in enumerate(trace["passes"]):
        require(
            pass_record.get("index") == index,
            f"{opt_level} pass index drifted at {index}",
        )
        require(
            pass_record.get("name") == ids[index],
            f"{opt_level} pass name must match pass id at {ids[index]}",
        )
        require(
            pass_record.get("status") == "completed",
            f"{opt_level} pass {ids[index]} must complete",
        )
        require(
            pass_record.get("diagnosticCount") == 0,
            f"{opt_level} pass {ids[index]} must not emit diagnostics",
        )
        require(
            pass_record.get("errorCount") == 0,
            f"{opt_level} pass {ids[index]} must not emit errors",
        )
        pass_changed = pass_record.get("changed")
        require(
            isinstance(pass_changed, bool),
            f"{opt_level} pass {ids[index]} changed must be boolean",
        )
        validate_module_stats(pass_record, opt_level, index, ids[index])
        if pass_changed is True:
            changed_count += 1
    require(
        trace.get("changedPassCount") == changed_count,
        f"{opt_level} changedPassCount does not match changed pass records",
    )
    require(
        trace.get("changed") == (changed_count != 0),
        f"{opt_level} changed flag does not match changed pass records",
    )
    return ids


def validate_o0_validation_only(trace: dict[str, Any]) -> None:
    ids = validate_common_trace(trace, "O0")
    require(
        all(not pass_id.startswith("hir.optimize.") for pass_id in ids),
        "O0 must not schedule optimization passes",
    )
    require(trace.get("changedPassCount") == 0, "O0 changedPassCount must be 0")
    require(trace.get("changed") is False, "O0 trace must report changed=false")
    for pass_record in trace["passes"]:
        require(
            pass_record.get("category") == "validation",
            f"O0 pass {pass_record.get('id')} must be categorized as validation",
        )
        require(
            pass_record.get("changed") is False,
            f"O0 pass {pass_record.get('id')} must not mutate HIR",
        )


def validate_o1_baseline(trace: dict[str, Any]) -> None:
    ids = validate_common_trace(trace, "O1")
    require(
        not any(pass_id in ids for pass_id in O2_ONLY_PASS_IDS),
        "O1 must not schedule O2-only inline passes",
    )


def validate_o2_distinct_trace(trace: dict[str, Any]) -> None:
    ids = validate_common_trace(trace, "O2")
    require(
        ids != O1_PASS_IDS,
        "O2 pass trace must be distinct from the O1 pass trace",
    )
    inline_index = ids.index(O2_ONLY_PASS_IDS[0])
    vector_index = ids.index(O2_ONLY_PASS_IDS[1])
    validation_index = ids.index("hir.validate.storage-buffer-shapes")
    require(
        inline_index < vector_index < validation_index,
        "O2 inline passes must run before final target-independent validation",
    )
    for pass_id in O2_ONLY_PASS_IDS:
        pass_record = pass_by_id(trace, pass_id)
        require(
            pass_record.get("category") == "optimization",
            f"{pass_id} must be categorized as optimization",
        )


def validate_o2_inline_fixture_trace(trace: dict[str, Any]) -> None:
    validate_o2_distinct_trace(trace)
    for pass_id in O2_ONLY_PASS_IDS:
        pass_record = pass_by_id(trace, pass_id)
        require(
            pass_record.get("changed") is True,
            f"{pass_id} must change the deterministic O2 inline fixture",
        )


def run_evidence_check(root: Path, cglc: Path) -> list[str]:
    validation_trace = run_cglc(cglc, root, VALIDATION_FIXTURE, "O0")
    validate_o0_validation_only(validation_trace)

    o1_inline_trace = run_cglc(cglc, root, O2_INLINE_FIXTURE, "O1")
    validate_o1_baseline(o1_inline_trace)

    o2_inline_trace = run_cglc(cglc, root, O2_INLINE_FIXTURE, "O2")
    validate_o2_inline_fixture_trace(o2_inline_trace)

    return [
        f"{entry['claim']} -> {entry['fixture']} --opt-level {entry['level']}"
        for entry in CLAIM_FIXTURES
    ]


def make_trace(
    opt_level: str,
    changed_ids: set[str] | None = None,
    override_passes: list[str] | None = None,
) -> dict[str, Any]:
    changed_ids = changed_ids or set()
    expected = EXPECTED_POLICIES[opt_level]
    ids = list(override_passes or expected["passes"])
    passes: list[dict[str, Any]] = []

    def make_module_stats(index: int, changed: bool) -> dict[str, dict[str, int]]:
        before = {
            "structCount": 1,
            "constantCount": 0,
            "stageCount": 1,
            "resourceCount": 1,
            "functionCount": 1,
            "statementCount": 4 + index,
            "expressionCount": 8 + index,
        }
        after = dict(before)
        if changed:
            after["expressionCount"] += 1
        delta = {
            field: abs(after[field] - before[field]) for field in HIR_MODULE_STAT_FIELDS
        }
        return {"before": before, "after": after, "delta": delta}

    for index, pass_id in enumerate(ids):
        if pass_id.startswith("hir.validate."):
            category = "validation"
        elif "cleanup" in pass_id:
            category = "cleanup"
        else:
            category = "optimization"
        changed = pass_id in changed_ids
        passes.append(
            {
                "index": index,
                "id": pass_id,
                "name": pass_id,
                "category": category,
                "changed": changed,
                "status": "completed",
                "diagnosticCount": 0,
                "errorCount": 0,
                "elapsedTimeMicroseconds": 0,
                "moduleStats": make_module_stats(index, changed),
            }
        )
    changed_pass_count = sum(1 for pass_id in ids if pass_id in changed_ids)
    return {
        "schemaVersion": 1,
        "kind": "hir-pass-trace",
        "optimizationLevel": opt_level,
        "optimizationPolicy": {
            "id": expected["id"],
            "name": expected["name"],
            "description": expected["description_fragment"],
            "backendInputMode": "source-validation",
        },
        "passSchedule": {
            "fingerprint": pass_schedule_fingerprint(ids),
            "fingerprintPolicy": "scheduled-pass-ids-v1",
            "stability": "stable-opt-level-policy",
        },
        "scheduledPassCount": len(ids),
        "passCount": len(ids),
        "changedPassCount": changed_pass_count,
        "diagnosticPassCount": 0,
        "errorPassCount": 0,
        "changed": changed_pass_count != 0,
        "completed": True,
        "stopReason": "none",
        "passes": passes,
    }


def expect_failure(label: str, callback: Any, needle: str) -> list[str]:
    try:
        callback()
    except CheckError as error:
        if needle not in str(error):
            return [f"{label}: expected failure containing {needle!r}, got {error}"]
        return []
    return [f"{label}: expected checker failure"]


def run_self_test() -> list[str]:
    errors: list[str] = []
    try:
        validate_o0_validation_only(make_trace("O0"))
        validate_o1_baseline(make_trace("O1", {"hir.optimize.simplify-algebraic"}))
        validate_o2_inline_fixture_trace(make_trace("O2", set(O2_ONLY_PASS_IDS)))
    except CheckError as error:
        errors.append(f"valid synthetic trace failed: {error}")

    o0_with_optimization = make_trace(
        "O0", override_passes=O0_PASS_IDS + ["hir.optimize.simplify-algebraic"]
    )
    errors.extend(
        expect_failure(
            "o0 optimization pass",
            lambda: validate_o0_validation_only(o0_with_optimization),
            "scheduledPassCount",
        )
    )

    o0_changed = make_trace("O0", {"hir.validate.module-shape"})
    errors.extend(
        expect_failure(
            "o0 changed pass",
            lambda: validate_o0_validation_only(o0_changed),
            "O0 changedPassCount must be 0",
        )
    )

    stale_fingerprint = make_trace("O1")
    stale_fingerprint["passSchedule"]["fingerprint"] = "fnv1a64:0000000000000000"
    errors.extend(
        expect_failure(
            "stale pass schedule fingerprint",
            lambda: validate_o1_baseline(stale_fingerprint),
            "pass schedule fingerprint drifted",
        )
    )

    missing_module_stats = make_trace("O1")
    del missing_module_stats["passes"][0]["moduleStats"]
    errors.extend(
        expect_failure(
            "missing module stats",
            lambda: validate_o1_baseline(missing_module_stats),
            "passes[0].moduleStats must be an object",
        )
    )

    corrupt_module_delta = make_trace("O1")
    corrupt_module_delta["passes"][2]["moduleStats"]["delta"]["expressionCount"] = 99
    errors.extend(
        expect_failure(
            "corrupt module stats delta",
            lambda: validate_o1_baseline(corrupt_module_delta),
            "moduleStats.delta.expressionCount",
        )
    )

    unchanged_nonzero_delta = make_trace("O1")
    unchanged_nonzero_delta["passes"][0]["moduleStats"]["after"]["expressionCount"] += 1
    unchanged_nonzero_delta["passes"][0]["moduleStats"]["delta"]["expressionCount"] = 1
    errors.extend(
        expect_failure(
            "unchanged pass nonzero module stats",
            lambda: validate_o1_baseline(unchanged_nonzero_delta),
            "reports changed=false but moduleStats delta is nonzero",
        )
    )

    o2_missing_inline = make_trace(
        "O2",
        override_passes=[
            pass_id
            for pass_id in O2_PASS_IDS
            if pass_id != "hir.optimize.o2.inline-literal-vector-temporaries"
        ],
    )
    errors.extend(
        expect_failure(
            "o2 missing inline pass",
            lambda: validate_o2_distinct_trace(o2_missing_inline),
            "scheduledPassCount",
        )
    )

    o2_inline_unchanged = make_trace(
        "O2", {"hir.optimize.o2.inline-scalar-temporaries"}
    )
    errors.extend(
        expect_failure(
            "o2 inline fixture unchanged",
            lambda: validate_o2_inline_fixture_trace(o2_inline_unchanged),
            "hir.optimize.o2.inline-literal-vector-temporaries must change",
        )
    )

    claim_names = {entry["claim"] for entry in CLAIM_FIXTURES}
    for required_claim in (
        "v0.optimizer.o0.validation_only",
        "v0.optimizer.o2.distinct_pass_trace",
    ):
        if required_claim not in claim_names:
            errors.append(f"self-test: missing claim map entry {required_claim}")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--cglc", type=Path, default=Path("build/cglc"))
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()

    if args.self_test:
        errors = run_self_test()
        if errors:
            for error in errors:
                print(error)
            return 1
        print("v0 optimizer evidence checker self-test passed")
        return 0

    root = args.root.resolve()
    cglc = args.cglc
    if not cglc.is_absolute():
        cglc = root / cglc
    try:
        evidence = run_evidence_check(root, cglc)
    except CheckError as error:
        print(error)
        return 1
    for line in evidence:
        print(line)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
