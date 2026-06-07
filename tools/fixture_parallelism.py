"""Bounded deterministic parallelism for fixture validators."""

from __future__ import annotations

from collections.abc import Callable, Iterable
from concurrent.futures import ThreadPoolExecutor
import os
from typing import TypeVar


DEFAULT_JOBS_ENV_VAR = "CROSSGL_CI_JOBS"

T = TypeVar("T")
R = TypeVar("R")


def _positive_job_count(value: object) -> int:
    try:
        parsed = int(str(value))
    except (TypeError, ValueError):
        return 1
    return max(1, parsed)


def fixture_job_count(env_var: str | None = None) -> int:
    """Return the requested fixture job count, defaulting to serial execution."""
    env_vars = (env_var, DEFAULT_JOBS_ENV_VAR) if env_var else (DEFAULT_JOBS_ENV_VAR,)
    for candidate in env_vars:
        if not candidate:
            continue
        value = os.environ.get(candidate)
        if value is None or not value.strip():
            continue
        return _positive_job_count(value)
    return 1


def run_fixture_tasks(
    items: Iterable[T],
    worker: Callable[[T], R],
    *,
    env_var: str | None = None,
    jobs: int | None = None,
) -> list[R]:
    """Run independent fixture tasks with deterministic result ordering."""
    task_items = tuple(items)
    if not task_items:
        return []

    max_workers = jobs if jobs is not None else fixture_job_count(env_var)
    max_workers = min(_positive_job_count(max_workers), len(task_items))
    if max_workers == 1:
        return [worker(item) for item in task_items]

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = [executor.submit(worker, item) for item in task_items]
        return [future.result() for future in futures]


def extend_errors_from_fixture_tasks(
    errors: list[str],
    items: Iterable[T],
    worker: Callable[[T], Iterable[str]],
    *,
    env_var: str | None = None,
    jobs: int | None = None,
) -> None:
    """Append per-task error lists in the same order as the input items."""
    for task_errors in run_fixture_tasks(
        items,
        worker,
        env_var=env_var,
        jobs=jobs,
    ):
        errors.extend(task_errors)
