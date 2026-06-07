#!/usr/bin/env python3
"""Named build-mode profiles for CrossGL compiler benchmarks.

This module is intentionally independent of the benchmark runner so the runner
can import a stable profile contract without owning the policy for each mode.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import Any


SCHEMA_VERSION = 1
DEFAULT_PROFILE = "release"
PROFILE_ORDER = (
    "debug",
    "release",
    "release-o2",
    "release-o2-debug-ir",
    "native-package",
)
PACKAGE_MODES = ("source", "native")
KNOWN_PROFILE_FIELDS = (
    "name",
    "displayName",
    "description",
    "buildType",
    "compilerConfig",
    "cglcArgs",
    "cmakeArgs",
    "environment",
    "packageMode",
    "nativeValidation",
)
BASELINE_CONTRACT_SCHEMA_VERSION = 1
BASELINE_CONTRACT_KIND = "advisory-baseline-structural-contract"
BASELINE_POLICY_MODE = "report-only"
BASELINE_STRUCTURAL_FAILURE_MODE = "hard-fail"
BASELINE_TIMING_FAILURE_MODE = "report-only"
BASELINE_TOP_LEVEL_FIELDS = (
    "schemaVersion",
    "tool",
    "corpusVersion",
    "cases",
    "summary",
)
BASELINE_CONTEXT_FIELD_PATHS = {
    "hostLabel": (
        ("baselinePolicy", "hostLabel"),
        ("metadata", "hostLabel"),
        ("environment", "hostLabel"),
        ("config", "hostLabel"),
        ("host", "label"),
        ("hostLabel",),
    ),
    "hostClass": (
        ("baselinePolicy", "hostClass"),
        ("metadata", "hostClass"),
        ("environment", "hostClass"),
        ("config", "hostClass"),
        ("host", "class"),
        ("hostClass",),
    ),
    "targetProfile": (
        ("baselinePolicy", "targetProfile"),
        ("metadata", "targetProfile"),
        ("config", "targetProfile"),
        ("targetProfile",),
    ),
    "optLevel": (
        ("baselinePolicy", "optLevel"),
        ("metadata", "optLevel"),
        ("config", "optLevel"),
        ("optLevel",),
    ),
    "comparisonWindow": (
        ("baselinePolicy", "comparisonWindow"),
        ("metadata", "comparisonWindow"),
        ("config", "comparisonWindow"),
        ("comparisonWindow",),
    ),
    "toolchainLabel": (
        ("baselinePolicy", "toolchainLabel"),
        ("metadata", "toolchainLabel"),
        ("config", "toolchainLabel"),
        ("toolchain", "label"),
        ("toolchain", "name"),
        ("toolchainLabel",),
    ),
    "toolchainVersion": (
        ("baselinePolicy", "toolchainVersion"),
        ("metadata", "toolchainVersion"),
        ("config", "toolchainVersion"),
        ("toolchain", "version"),
        ("toolchainVersion",),
    ),
}
BASELINE_REQUIRED_CONTEXT_FIELDS = tuple(BASELINE_CONTEXT_FIELD_PATHS)
BASELINE_CASE_FIELDS = (
    "case",
    "commandProfile",
    "fixtureCategory",
    "profile",
    "target",
)
BASELINE_TIMED_CASE_IDENTITY_FIELDS = (
    "fixtureName",
    "target",
    "profile",
    "optLevel",
)
BASELINE_SUMMARY_FIELDS = (
    "caseCount",
    "caseCategories",
    "caseCountByCategory",
    "caseCountByCommandProfile",
    "caseCountByProfile",
    "caseCountByTarget",
    "commandProfiles",
    "skippedCount",
    "unavailableToolCount",
)
BASELINE_SKIPPED_SUMMARY_FIELDS = (
    "skippedCaseCountByReason",
    "skippedCasesWithUnavailableTools",
    "skippedToolCaseCountByTool",
    "skippedToolCasesByTool",
)


@dataclass(frozen=True)
class BenchmarkBuildProfile:
    name: str
    display_name: str
    description: str
    build_type: str
    compiler_config: str
    cglc_args: tuple[str, ...] = ()
    cmake_args: tuple[str, ...] = ()
    environment: tuple[tuple[str, str], ...] = ()
    package_mode: str = "source"
    native_validation: bool = False

    def to_json(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "displayName": self.display_name,
            "description": self.description,
            "buildType": self.build_type,
            "compilerConfig": self.compiler_config,
            "cglcArgs": list(self.cglc_args),
            "cmakeArgs": list(self.cmake_args),
            "environment": [
                {"name": name, "value": value} for name, value in self.environment
            ],
            "packageMode": self.package_mode,
            "nativeValidation": self.native_validation,
        }


_PROFILE_DEFINITIONS: dict[str, BenchmarkBuildProfile] = {
    "debug": BenchmarkBuildProfile(
        name="debug",
        display_name="Debug",
        description="Compiler benchmark lane using an unoptimized debug build.",
        build_type="Debug",
        compiler_config="Debug",
        cmake_args=("-DCMAKE_BUILD_TYPE=Debug",),
    ),
    "release": BenchmarkBuildProfile(
        name="release",
        display_name="Release",
        description="Default compiler benchmark lane using an optimized build.",
        build_type="Release",
        compiler_config="Release",
        cmake_args=("-DCMAKE_BUILD_TYPE=Release",),
    ),
    "release-o2": BenchmarkBuildProfile(
        name="release-o2",
        display_name="Release O2",
        description=(
            "Release compiler benchmark lane that explicitly requests optimizer "
            "level O2 from cglc."
        ),
        build_type="Release",
        compiler_config="O2",
        cglc_args=("--opt-level", "O2"),
        cmake_args=("-DCMAKE_BUILD_TYPE=Release",),
    ),
    "release-o2-debug-ir": BenchmarkBuildProfile(
        name="release-o2-debug-ir",
        display_name="Release O2 Debug IR",
        description=(
            "Opt-in release compiler benchmark lane that requests optimizer level "
            "O2 plus debug IR/pass-trace sidecar emission from cglc."
        ),
        build_type="Release",
        compiler_config="O2",
        cglc_args=("--opt-level", "O2", "--debug-ir"),
        cmake_args=("-DCMAKE_BUILD_TYPE=Release",),
    ),
    "native-package": BenchmarkBuildProfile(
        name="native-package",
        display_name="Native Package",
        description=(
            "Package benchmark lane that requests native package artifacts when "
            "the configured native toolchain is available."
        ),
        build_type="Release",
        compiler_config="Release",
        cmake_args=("-DCMAKE_BUILD_TYPE=Release",),
        package_mode="native",
        native_validation=True,
    ),
}
PROFILES: Mapping[str, BenchmarkBuildProfile] = MappingProxyType(_PROFILE_DEFINITIONS)


def profile_contract_errors(
    profiles: Mapping[str, BenchmarkBuildProfile] = PROFILES,
    profile_order: Sequence[str] = PROFILE_ORDER,
    default_profile: str = DEFAULT_PROFILE,
) -> list[str]:
    errors: list[str] = []
    ordered_names = tuple(profile_order)
    profile_names = tuple(profiles.keys())

    duplicate_names = sorted(
        {name for name in ordered_names if ordered_names.count(name) > 1}
    )
    if duplicate_names:
        errors.append(
            "PROFILE_ORDER contains duplicate profile(s): " + ", ".join(duplicate_names)
        )

    unknown_names = sorted(set(ordered_names) - set(profile_names))
    if unknown_names:
        errors.append(
            "PROFILE_ORDER contains unknown profile(s): " + ", ".join(unknown_names)
        )

    unordered_names = sorted(set(profile_names) - set(ordered_names))
    if unordered_names:
        errors.append(
            "PROFILES contains profile(s) missing from PROFILE_ORDER: "
            + ", ".join(unordered_names)
        )

    if not unknown_names and not unordered_names and profile_names != ordered_names:
        errors.append(
            "PROFILES registry order must match PROFILE_ORDER: "
            f"{profile_names!r} != {ordered_names!r}"
        )

    if default_profile not in profiles:
        errors.append(f"DEFAULT_PROFILE {default_profile!r} is not defined")

    for registry_name, profile in profiles.items():
        if not isinstance(profile, BenchmarkBuildProfile):
            errors.append(
                f"{registry_name}: expected BenchmarkBuildProfile, "
                f"got {type(profile).__name__}"
            )
            continue

        if profile.name != registry_name:
            errors.append(
                f"{registry_name}: name {profile.name!r} does not match registry key"
            )

        fields = tuple(profile.to_json().keys())
        if fields != KNOWN_PROFILE_FIELDS:
            errors.append(
                f"{registry_name}: JSON fields changed: "
                f"{fields!r} != {KNOWN_PROFILE_FIELDS!r}"
            )

        if profile.package_mode not in PACKAGE_MODES:
            errors.append(
                f"{registry_name}: unsupported packageMode {profile.package_mode!r}; "
                f"choose {', '.join(PACKAGE_MODES)}"
            )

        if profile.package_mode == "native" and not profile.native_validation:
            errors.append(
                f"{registry_name}: native package profiles must request native validation"
            )
        if profile.package_mode == "source" and profile.native_validation:
            errors.append(
                f"{registry_name}: source package profiles must not request native validation"
            )

    return errors


def validate_profile_contract() -> None:
    errors = profile_contract_errors()
    if errors:
        raise ValueError(
            "invalid benchmark build profile contract:\n- " + "\n- ".join(errors)
        )


validate_profile_contract()


def ordered_profiles() -> list[BenchmarkBuildProfile]:
    return [PROFILES[name] for name in PROFILE_ORDER]


def get_profile(name: str) -> BenchmarkBuildProfile:
    try:
        return PROFILES[name]
    except KeyError as error:
        choices = ", ".join(PROFILE_ORDER)
        raise ValueError(
            f"unknown benchmark build profile {name!r}; choose {choices}"
        ) from error


def profile_document(profile_names: list[str] | None = None) -> dict[str, Any]:
    names = list(profile_names) if profile_names is not None else list(PROFILE_ORDER)
    profiles = [get_profile(name).to_json() for name in names]
    return {
        "schemaVersion": SCHEMA_VERSION,
        "defaultProfile": DEFAULT_PROFILE,
        "profileFields": list(KNOWN_PROFILE_FIELDS),
        "profiles": profiles,
    }


def dotted_path(path: Sequence[str]) -> str:
    return ".".join(path)


def value_at_path(payload: Mapping[str, Any], path: Sequence[str]) -> Any:
    value: Any = payload
    for key in path:
        if not isinstance(value, Mapping) or key not in value:
            return None
        value = value[key]
    return value


def non_empty_string(value: Any) -> str | None:
    if isinstance(value, str) and value:
        return value
    return None


def nonnegative_int(value: Any) -> int | None:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        return None
    return value


def toolchain_labels(report: Mapping[str, Any]) -> set[str]:
    labels: set[str] = set()
    toolchain = report.get("toolchain")
    if isinstance(toolchain, Mapping):
        label = non_empty_string(toolchain.get("label")) or non_empty_string(
            toolchain.get("name")
        )
        if label is not None:
            labels.add(label)

    toolchains = report.get("toolchains")
    if isinstance(toolchains, Mapping):
        labels.update(label for label in toolchains if isinstance(label, str) and label)
    elif isinstance(toolchains, list):
        for entry in toolchains:
            if not isinstance(entry, Mapping):
                continue
            label = non_empty_string(entry.get("label")) or non_empty_string(
                entry.get("name")
            )
            if label is not None:
                labels.add(label)

    tool_availability = report.get("toolAvailability")
    if isinstance(tool_availability, Mapping):
        labels.update(
            label for label in tool_availability if isinstance(label, str) and label
        )
    return labels


def toolchain_versions(report: Mapping[str, Any]) -> set[str]:
    versions: set[str] = set()
    toolchain = report.get("toolchain")
    if isinstance(toolchain, Mapping):
        version = non_empty_string(toolchain.get("version"))
        if version is not None:
            versions.add(version)

    toolchains = report.get("toolchains")
    if isinstance(toolchains, Mapping):
        for entry in toolchains.values():
            if isinstance(entry, Mapping):
                version = non_empty_string(entry.get("version"))
            else:
                version = non_empty_string(entry)
            if version is not None:
                versions.add(version)
    elif isinstance(toolchains, list):
        for entry in toolchains:
            if not isinstance(entry, Mapping):
                continue
            version = non_empty_string(entry.get("version"))
            if version is not None:
                versions.add(version)

    tool_availability = report.get("toolAvailability")
    if isinstance(tool_availability, Mapping):
        for entry in tool_availability.values():
            if not isinstance(entry, Mapping):
                continue
            version = non_empty_string(entry.get("version"))
            if version is not None:
                versions.add(version)
    return versions


def context_field_present(report: Mapping[str, Any], field: str) -> bool:
    if field == "toolchainLabel" and toolchain_labels(report):
        return True
    if field == "toolchainVersion" and toolchain_versions(report):
        return True

    for path in BASELINE_CONTEXT_FIELD_PATHS[field]:
        value = value_at_path(report, path)
        if field == "comparisonWindow":
            if isinstance(value, Mapping) and value:
                return True
        elif non_empty_string(value) is not None:
            return True
    return False


def baseline_contract_document() -> dict[str, Any]:
    return {
        "schemaVersion": BASELINE_CONTRACT_SCHEMA_VERSION,
        "tool": "benchmark_build_modes",
        "kind": BASELINE_CONTRACT_KIND,
        "policy": {
            "mode": BASELINE_POLICY_MODE,
            "structural": {"mode": BASELINE_STRUCTURAL_FAILURE_MODE},
            "timing": {
                "mode": BASELINE_TIMING_FAILURE_MODE,
                "thresholds": "advisory/report-only",
            },
        },
        "requiredContextFields": list(BASELINE_REQUIRED_CONTEXT_FIELDS),
        "recognizedContextFieldPaths": {
            field: [dotted_path(path) for path in paths]
            for field, paths in BASELINE_CONTEXT_FIELD_PATHS.items()
        },
        "derivedContextFields": {
            "toolchainLabel": [
                "toolchain.label",
                "toolchain.name",
                "toolchains.<label>",
                "toolchains[].label",
                "toolchains[].name",
                "toolAvailability.<label>",
            ],
            "toolchainVersion": [
                "toolchain.version",
                "toolchains.<label>.version",
                "toolchains.<label>",
                "toolchains[].version",
                "toolAvailability.<label>.version",
            ],
        },
        "requiredTopLevelFields": list(BASELINE_TOP_LEVEL_FIELDS),
        "requiredCaseFields": list(BASELINE_CASE_FIELDS),
        "requiredTimedCaseIdentityFields": list(BASELINE_TIMED_CASE_IDENTITY_FIELDS),
        "requiredSummaryFields": list(BASELINE_SUMMARY_FIELDS),
        "requiredSkippedSummaryFields": list(BASELINE_SKIPPED_SUMMARY_FIELDS),
        "missingFieldFailureMode": BASELINE_STRUCTURAL_FAILURE_MODE,
        "timingDeltaFailureMode": BASELINE_TIMING_FAILURE_MODE,
    }


def command_profile_name(case: Mapping[str, Any]) -> str | None:
    command_profile = case.get("commandProfile")
    if isinstance(command_profile, Mapping):
        return non_empty_string(command_profile.get("name"))
    return None


def case_is_skipped(case: Mapping[str, Any]) -> bool:
    skipped = case.get("skipped")
    if isinstance(skipped, bool):
        return skipped
    return case.get("status") == "skipped"


def case_is_timed(case: Mapping[str, Any]) -> bool:
    timing = case.get("timing")
    if not isinstance(timing, Mapping):
        return False
    return nonnegative_int(timing.get("elapsedNs")) is not None


def unavailable_tools(case: Mapping[str, Any]) -> list[str]:
    values = case.get("unavailableTools")
    if not isinstance(values, list):
        return []
    return sorted({value for value in values if isinstance(value, str) and value})


def case_counts(cases: Sequence[Mapping[str, Any]], field: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for case in cases:
        if field == "commandProfile":
            value = command_profile_name(case)
        else:
            value = non_empty_string(case.get(field))
        if value is None:
            continue
        counts[value] = counts.get(value, 0) + 1
    return dict(sorted(counts.items()))


def summary_mapping_issue(
    summary: Mapping[str, Any],
    field: str,
    expected: Mapping[str, int],
    label: str,
) -> str | None:
    value = summary.get(field)
    if not isinstance(value, Mapping):
        return f"{label}.summary.{field} must be an object"
    if dict(value) != dict(expected):
        return (
            f"{label}.summary.{field}={dict(value)!r} does not match cases "
            f"({dict(expected)!r})"
        )
    return None


def summary_list_issue(
    summary: Mapping[str, Any],
    field: str,
    expected: Sequence[str],
    label: str,
) -> str | None:
    value = summary.get(field)
    if not isinstance(value, list) or any(
        not isinstance(entry, str) or not entry for entry in value
    ):
        return f"{label}.summary.{field} must be a list of strings"
    if value != list(expected):
        return (
            f"{label}.summary.{field}={value!r} does not match cases "
            f"({list(expected)!r})"
        )
    return None


def baseline_report_contract_errors(
    report: Mapping[str, Any], *, label: str = "report"
) -> list[str]:
    errors: list[str] = []

    for field in BASELINE_TOP_LEVEL_FIELDS:
        if field not in report:
            errors.append(f"{label}.{field} is required")

    missing_context_fields = [
        field
        for field in BASELINE_REQUIRED_CONTEXT_FIELDS
        if not context_field_present(report, field)
    ]
    for field in missing_context_fields:
        paths = ", ".join(
            dotted_path(path) for path in BASELINE_CONTEXT_FIELD_PATHS[field]
        )
        errors.append(
            f"{label} missing baseline context field {field!r}; recognized paths: "
            f"{paths}"
        )

    comparison_window = None
    for path in BASELINE_CONTEXT_FIELD_PATHS["comparisonWindow"]:
        value = value_at_path(report, path)
        if value is not None:
            comparison_window = value
            break
    if comparison_window is not None:
        if not isinstance(comparison_window, Mapping):
            errors.append(f"{label}.comparisonWindow must be an object")
        else:
            for field in ("sampleCount", "warmupCount"):
                if (
                    field in comparison_window
                    and nonnegative_int(comparison_window[field]) is None
                ):
                    errors.append(
                        f"{label}.comparisonWindow.{field} must be a non-negative "
                        "integer when present"
                    )

    cases_value = report.get("cases")
    cases: list[Mapping[str, Any]] = []
    if not isinstance(cases_value, list):
        errors.append(f"{label}.cases must be an array")
    else:
        for index, case in enumerate(cases_value):
            case_label = f"{label}.cases[{index}]"
            if not isinstance(case, Mapping):
                errors.append(f"{case_label} must be an object")
                continue
            cases.append(case)
            for field in BASELINE_CASE_FIELDS:
                if field == "commandProfile":
                    if not isinstance(case.get(field), Mapping):
                        errors.append(f"{case_label}.commandProfile must be an object")
                    elif command_profile_name(case) is None:
                        errors.append(
                            f"{case_label}.commandProfile.name must be a "
                            "non-empty string"
                        )
                    continue
                if non_empty_string(case.get(field)) is None:
                    errors.append(f"{case_label}.{field} must be a non-empty string")
            if case_is_timed(case):
                for field in BASELINE_TIMED_CASE_IDENTITY_FIELDS:
                    if non_empty_string(case.get(field)) is None:
                        errors.append(
                            f"{case_label}.{field} is required for timed baseline cases"
                        )
            if case_is_skipped(case):
                if non_empty_string(case.get("skipReason")) is None:
                    errors.append(
                        f"{case_label}.skipReason must be a non-empty string for "
                        "skipped cases"
                    )
                if not unavailable_tools(case):
                    errors.append(
                        f"{case_label}.unavailableTools must name at least one "
                        "unavailable tool for skipped cases"
                    )

    summary = report.get("summary")
    if not isinstance(summary, Mapping):
        errors.append(f"{label}.summary must be an object")
        summary = {}

    for field in BASELINE_SUMMARY_FIELDS:
        if field not in summary:
            errors.append(f"{label}.summary.{field} is required")

    if isinstance(summary, Mapping):
        expected_case_count = len(cases)
        case_count = summary.get("caseCount")
        if (
            isinstance(case_count, bool)
            or not isinstance(case_count, int)
            or case_count != expected_case_count
        ):
            errors.append(
                f"{label}.summary.caseCount={case_count!r} does not match cases "
                f"({expected_case_count})"
            )

        skipped_count = summary.get("skippedCount")
        expected_skipped_count = sum(1 for case in cases if case_is_skipped(case))
        if skipped_count is not None and (
            isinstance(skipped_count, bool)
            or not isinstance(skipped_count, int)
            or skipped_count != expected_skipped_count
        ):
            errors.append(
                f"{label}.summary.skippedCount={skipped_count!r} does not match "
                f"cases ({expected_skipped_count})"
            )

        expected_unavailable_count = len(
            {tool for case in cases for tool in unavailable_tools(case)}
        )
        unavailable_count = summary.get("unavailableToolCount")
        if unavailable_count is not None and (
            isinstance(unavailable_count, bool)
            or not isinstance(unavailable_count, int)
            or unavailable_count != expected_unavailable_count
        ):
            errors.append(
                f"{label}.summary.unavailableToolCount={unavailable_count!r} "
                f"does not match cases ({expected_unavailable_count})"
            )

        category_counts = case_counts(cases, "fixtureCategory")
        command_profile_counts = case_counts(cases, "commandProfile")
        profile_counts = case_counts(cases, "profile")
        target_counts = case_counts(cases, "target")
        for issue in (
            summary_list_issue(
                summary, "caseCategories", sorted(category_counts), label
            ),
            summary_list_issue(
                summary, "commandProfiles", sorted(command_profile_counts), label
            ),
            summary_mapping_issue(
                summary, "caseCountByCategory", category_counts, label
            ),
            summary_mapping_issue(
                summary,
                "caseCountByCommandProfile",
                command_profile_counts,
                label,
            ),
            summary_mapping_issue(summary, "caseCountByProfile", profile_counts, label),
            summary_mapping_issue(summary, "caseCountByTarget", target_counts, label),
        ):
            if issue is not None:
                errors.append(issue)

        if expected_skipped_count:
            for field in BASELINE_SKIPPED_SUMMARY_FIELDS:
                if field not in summary:
                    errors.append(f"{label}.summary.{field} is required")

    skipped_tools = sorted({tool for case in cases for tool in unavailable_tools(case)})
    if skipped_tools:
        tool_availability = report.get("toolAvailability")
        if not isinstance(tool_availability, Mapping):
            errors.append(f"{label}.toolAvailability must describe skipped tools")
        else:
            for tool in skipped_tools:
                value = tool_availability.get(tool)
                if not isinstance(value, Mapping):
                    errors.append(
                        f"{label}.toolAvailability.{tool} must describe skipped tool"
                    )
                    continue
                if (
                    value.get("available") is not False
                    and value.get("status") != "unavailable"
                ):
                    errors.append(
                        f"{label}.toolAvailability.{tool} must mark skipped tool "
                        "unavailable"
                    )

    return errors


def validate_baseline_report_contract(report: Mapping[str, Any]) -> None:
    errors = baseline_report_contract_errors(report)
    if errors:
        raise ValueError(
            "invalid advisory baseline report contract:\n- " + "\n- ".join(errors)
        )


def load_json_payload(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, dict):
        raise ValueError(f"{path}: expected a JSON object")
    return payload


def write_json(payload: dict[str, Any]) -> None:
    sys.stdout.write(json.dumps(payload, indent=2, sort_keys=True) + "\n")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Emit named CrossGL benchmark build-mode profiles as JSON."
    )
    parser.add_argument(
        "--profile",
        action="append",
        choices=PROFILE_ORDER,
        help=(
            "Profile to emit. May be passed more than once. Defaults to all "
            "profiles in stable order."
        ),
    )
    parser.add_argument(
        "--list-names",
        action="store_true",
        help="Print known profile names, one per line.",
    )
    parser.add_argument(
        "--baseline-contract",
        action="store_true",
        help=(
            "Emit the advisory baseline report structural contract. Timing "
            "thresholds remain report-only; missing structural metadata is the "
            "hard-fail surface."
        ),
    )
    parser.add_argument(
        "--list-baseline-fields",
        action="store_true",
        help="Print required advisory baseline context fields, one per line.",
    )
    parser.add_argument(
        "--check-baseline-report",
        action="append",
        type=Path,
        help=(
            "Validate a saved benchmark report against the advisory baseline "
            "structural contract. May be passed more than once."
        ),
    )
    args = parser.parse_args()

    if args.list_names:
        sys.stdout.write("\n".join(PROFILE_ORDER) + "\n")
        return 0
    if args.list_baseline_fields:
        sys.stdout.write("\n".join(BASELINE_REQUIRED_CONTEXT_FIELDS) + "\n")
        return 0
    if args.baseline_contract:
        write_json(baseline_contract_document())
        return 0
    if args.check_baseline_report:
        all_errors: list[str] = []
        for path in args.check_baseline_report:
            payload = load_json_payload(path)
            all_errors.extend(baseline_report_contract_errors(payload, label=str(path)))
        if all_errors:
            sys.stderr.write(
                "invalid advisory baseline report contract:\n- "
                + "\n- ".join(all_errors)
                + "\n"
            )
            return 1
        for path in args.check_baseline_report:
            sys.stdout.write(f"validated advisory baseline report: {path}\n")
        return 0

    write_json(profile_document(args.profile))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
