"""Semantic checks for package-stale-sidecars-v1.schema.json."""

from collections import Counter
from pathlib import PurePosixPath

from .common import (
    add_equal_error,
    add_length_count_error,
    validate_normalized_package_path,
    validate_source_location_span,
)
from .package_sidecars_v1 import validate_publication, validate_sidecar_name


SEVERITIES = ("note", "warning", "error")


def validate_package_publication_path(errors, package_path, publication):
    requested_path = publication["requestedPath"]
    if package_path == requested_path:
        return

    sidecar_kind = publication["sidecarKind"]
    sidecar_token = publication["sidecarToken"]
    sidecar_attempt = publication["sidecarAttempt"]
    if sidecar_kind is None or sidecar_token is None or sidecar_attempt is None:
        errors.append("$.packagePath: expected requestedPath or publication sidecar")
        return

    requested = PurePosixPath(requested_path)
    queried = PurePosixPath(package_path)
    expected_name = (
        f".{requested.name}.{sidecar_kind}-{sidecar_token}-{sidecar_attempt}"
    )
    add_equal_error(
        errors,
        "$.packagePath",
        queried.name,
        expected_name,
        "publication sidecar basename",
    )
    add_equal_error(
        errors,
        "$.packagePath",
        queried.parent.as_posix(),
        requested.parent.as_posix(),
        "publication sidecar parent directory",
    )


def validate_diagnostic_counts(errors, diagnostic_counts, diagnostics):
    counts = Counter(diagnostic["severity"] for diagnostic in diagnostics)
    for severity in SEVERITIES:
        add_equal_error(
            errors,
            f"$.diagnosticCounts.{severity}",
            diagnostic_counts[severity],
            counts[severity],
            f"{severity} diagnostic count",
        )
    return counts


def validate_candidates(errors, instance):
    candidates = instance["candidates"]
    retained = instance["retained"]
    add_length_count_error(
        errors,
        "$.candidateCount",
        instance["candidateCount"],
        candidates,
        "cleanup candidates length",
    )
    add_equal_error(
        errors,
        "$.discardedCount",
        instance["discardedCount"],
        sum(1 for candidate in candidates if candidate["action"] == "discarded"),
        "discarded candidate count",
    )
    add_equal_error(
        errors,
        "$.failedCount",
        instance["failedCount"],
        sum(1 for candidate in candidates if candidate["action"] == "failed"),
        "failed candidate count",
    )
    add_length_count_error(
        errors,
        "$.retainedCount",
        instance["retainedCount"],
        retained,
        "retained sidecars length",
    )

    paths = []
    for index, candidate in enumerate(candidates):
        path = f"$.candidates[{index}]"
        validate_normalized_package_path(errors, f"{path}.path", candidate["path"])
        validate_sidecar_name(
            errors,
            path,
            instance["publication"]["requestedPath"],
            candidate,
        )
        paths.append(candidate["path"])
        if not candidate["token"]:
            errors.append(f"{path}.token: expected non-empty sidecar token")
        if instance["dryRun"] and candidate["action"] != "would-discard":
            errors.append(f"{path}.action: dry run must only report would-discard")
        if not instance["dryRun"] and candidate["action"] == "would-discard":
            errors.append(
                f"{path}.action: applied cleanup must not report would-discard"
            )
        add_equal_error(
            errors,
            f"{path}.success",
            candidate["success"],
            candidate["action"] != "failed",
            "non-failed action success",
        )
        if candidate["reason"] == "not-directory" and candidate["directory"]:
            errors.append(f"{path}.directory: not-directory reason requires false")
        if candidate["reason"] == "previous-backup" and candidate["kind"] != "previous":
            errors.append(f"{path}.kind: previous-backup reason requires previous")
        if (
            candidate["reason"] == "staging-with-published-output"
            and not instance["requestedExists"]
        ):
            errors.append(
                f"{path}.reason: staging-with-published-output requires requestedExists"
            )

    if paths != sorted(paths):
        errors.append("$.candidates: expected sorted candidate paths")
    if len(paths) != len(set(paths)):
        errors.append("$.candidates: duplicate candidate paths")

    retained_paths = []
    for index, retained_sidecar in enumerate(retained):
        path = f"$.retained[{index}]"
        validate_normalized_package_path(
            errors,
            f"{path}.path",
            retained_sidecar["path"],
        )
        validate_sidecar_name(
            errors,
            path,
            instance["publication"]["requestedPath"],
            retained_sidecar,
        )
        retained_paths.append(retained_sidecar["path"])
        if not retained_sidecar["token"]:
            errors.append(f"{path}.token: expected non-empty sidecar token")
        if retained_sidecar["action"] != "kept":
            errors.append(f"{path}.action: retained sidecars must report kept")
        if not retained_sidecar["success"]:
            errors.append(f"{path}.success: retained sidecars must succeed")
        if (
            retained_sidecar["reason"] == "not-directory"
            and retained_sidecar["directory"]
        ):
            errors.append(f"{path}.directory: not-directory reason requires false")
        if not retained_sidecar["directory"] and instance["olderThanSeconds"] is None:
            errors.append(
                f"{path}.directory: non-directory retention requires olderThanSeconds"
            )
        if retained_sidecar["retainedBy"] == "keep-last":
            if instance["keepLast"] is None:
                errors.append(f"{path}.retainedBy: keep-last requires keepLast")
            if not retained_sidecar["directory"]:
                errors.append(f"{path}.retainedBy: keep-last requires directory")
        if (
            retained_sidecar["retainedBy"] in ("younger-than", "age-unknown")
            and instance["olderThanSeconds"] is None
        ):
            errors.append(f"{path}.retainedBy: age retention requires olderThanSeconds")
        if (
            retained_sidecar["reason"] == "previous-backup"
            and retained_sidecar["kind"] != "previous"
        ):
            errors.append(f"{path}.kind: previous-backup reason requires previous")
        if (
            retained_sidecar["reason"] == "staging-with-published-output"
            and not instance["requestedExists"]
        ):
            errors.append(
                f"{path}.reason: staging-with-published-output requires requestedExists"
            )

    if retained_paths != sorted(retained_paths):
        errors.append("$.retained: expected sorted retained sidecar paths")
    if len(retained_paths) != len(set(retained_paths)):
        errors.append("$.retained: duplicate retained sidecar paths")
    overlap = set(paths).intersection(retained_paths)
    if overlap:
        errors.append(
            "$.retained: retained sidecars must not also be cleanup candidates"
        )
    if (
        instance["keepLast"] is None
        and instance["olderThanSeconds"] is None
        and retained
    ):
        errors.append("$.retained: retention disabled must not retain sidecars")
    if (
        instance["keepLast"] is not None
        and sum(
            1
            for retained_sidecar in retained
            if retained_sidecar["retainedBy"] == "keep-last"
        )
        > instance["keepLast"]
    ):
        errors.append("$.retainedCount: retained sidecars exceed keepLast")
    if any(
        retained_sidecar["retainedBy"] == "age-unknown" for retained_sidecar in retained
    ):
        has_warning = any(
            diagnostic["code"] == "package.recover.retention-age-unknown"
            for diagnostic in instance["diagnostics"]
        )
        if not has_warning:
            errors.append(
                "$.retained: age-unknown retention requires matching diagnostic"
            )


def validate_diagnostics(errors, diagnostics):
    for index, diagnostic in enumerate(diagnostics):
        path = f"$.diagnostics[{index}]"
        if not diagnostic["code"].startswith("package.recover."):
            errors.append(f"{path}.code: expected package.recover. prefix")
        validate_source_location_span(
            errors, f"{path}.location", diagnostic["location"]
        )


def validate_semantics(instance):
    errors = []
    diagnostics = instance["diagnostics"]
    counts = validate_diagnostic_counts(
        errors,
        instance["diagnosticCounts"],
        diagnostics,
    )
    validate_normalized_package_path(errors, "$.packagePath", instance["packagePath"])
    validate_publication(errors, instance["publication"])
    validate_package_publication_path(
        errors,
        instance["packagePath"],
        instance["publication"],
    )
    validate_candidates(errors, instance)
    validate_diagnostics(errors, diagnostics)
    add_equal_error(
        errors,
        "$.success",
        instance["success"],
        counts["error"] == 0 and instance["failedCount"] == 0,
        "no-error cleanup status",
    )
    return errors
