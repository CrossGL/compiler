# Package Maintenance Scan Report JSON Schema

`cglc package maintain --scan <dir> --json` emits a schema-versioned aggregate
report for stale package sidecar maintenance across one directory. The current
schema is
[`docs/schemas/package-maintenance-report-v1.schema.json`](schemas/package-maintenance-report-v1.schema.json).

The scan is non-recursive. It discovers published package outputs whose names end
in `.cglb`, plus staging and previous sidecars in the same directory. Sidecars
are grouped by their requested package output path, so a missing requested output
can still have stale previous sidecars cleaned while recoverable staging sidecars
are retained.

Top-level fields:

- `rootPath`: scanned directory.
- `dryRun`: `true` unless the command included `--apply`.
- `keepLast`: newest stale sidecar directory retention count, or `null`.
- `olderThanSeconds`: age threshold in seconds, or `null`.
- `success`: aggregate command success.
- `packageCount`: number of package output groups discovered.
- `retainedCount`, `candidateCount`, `discardedCount`, `failedCount`: aggregate
  counts across every package result.
- `packages`: sorted per-package stale sidecar cleanup results. Each item has
  the same shape as the single-package stale sidecar cleanup report documented
  in [`docs/PACKAGE_RECOVER_SCHEMA.md`](PACKAGE_RECOVER_SCHEMA.md). In aggregate
  maintenance reports, each item is keyed by the requested package output, so
  `publication.requestedPath` must match that item's `packagePath`.
- `diagnosticCounts` and `diagnostics`: aggregate diagnostics. Per-package
  diagnostics are also preserved in each `packages` item.

Example:

```sh
cglc package maintain --scan build/packages --policy cleanup-policy.json --json
```

Use `--apply` to delete selected stale sidecars. Policy files only configure
retention; deletion is still controlled exclusively by the command line.

For automation that already has a concrete package list, use
`cglc package maintain --package-set <set.json> --json` instead. That input and
its report are documented in
[`docs/PACKAGE_MAINTENANCE_SET_SCHEMA.md`](PACKAGE_MAINTENANCE_SET_SCHEMA.md).
Use `cglc package maintain --scan <dir> --export-package-set <set.json>` to
export the scan discovery result as a reviewed package-set input without
running cleanup.
