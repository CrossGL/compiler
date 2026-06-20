# Package Recover JSON Schema

`cglc package recover <sidecar.cglb> --promote|--discard --json` emits a
schema-versioned recovery report. The current schema is
[`docs/schemas/package-recover-v1.schema.json`](schemas/package-recover-v1.schema.json).

Top-level fields:

- `schemaVersion`: integer schema version, currently `1`.
- `action`: requested recovery action, either `promote` or `discard`.
- `sidecarPath`: sidecar path as passed to `cglc`, normalized for stable
  separators.
- `requestedPath`: package path that the sidecar maps back to, or `null` when
  the path is not a valid CrossGL sidecar name.
- `backupPath`: `.previous-*` sidecar created for a replaced package, or `null`.
- `success`: `true` when recovery completed.
- `replacedExisting`: `true` exactly when `backupPath` is non-null.
- `message`: human-readable success message, or `null` on failure.
- `diagnosticCounts`: counts for note, warning, and error diagnostics.
- `diagnostics`: standard CrossGL diagnostic records for every recovery finding.

`diagnosticCounts` values match the severities present in `diagnostics`, and
`success` is `true` exactly when no error diagnostics were emitted.

Promotion first validates that the input path is a `.staging-*` or
`.previous-*` sidecar, that it still exists, and that it is a directory. If the
requested package output path already exists and `--replace` was not provided,
promotion fails with `package.recover.output-exists` without promoting or
deleting the sidecar. Otherwise, it runs the same compiler-native integrity
checks as `cglc package verify` before moving the sidecar into the requested
output path. When `--source` is provided, that verification also checks the
package source hash against the source file. DirectX and OpenGL sidecars with
`nativeBinaryStatus: "planned"` must be promoted with `--source`, because the
shared verifier requires source evidence for planned native output.
Promotion moves the package directory without rewriting root metadata documents,
so embedded `reflection.targetFeatures` records such as
`nonuniform-descriptor-index`, Metal texture/sampler family records such as
`nonuniform-texture-descriptor-index` and
`nonuniform-sampler-descriptor-index`, and package `diagnostics.json` records
remain byte-for-byte owned by the promoted sidecar.

If the requested output path already exists, promotion fails unless `--replace`
is passed. Replacement moves the existing package into a fresh `.previous-*`
sidecar before promoting the candidate sidecar. If promotion fails after that
backup move, the recovery command attempts to restore the previous package and
reports any restore failure as an additional diagnostic.

Discard removes the sidecar path recursively and never promotes or backs up a
requested output package.

Recovery-owned diagnostics use the `package.recover.` prefix. Promotion may also
include nested `package.verify.` diagnostics when sidecar integrity verification
fails. The command writes this JSON document on recovery success and recovery
failure. The process exit code remains authoritative for shell workflows: `0`
means recovered, `1` means recovery failed, and `2` is reserved for command-line
errors such as missing action flags.

## Sidecar List JSON

`cglc package recover <package-or-sidecar.cglb> --list --json` emits a
read-only package publication and sidecar discovery report. The current schema
is
[`docs/schemas/package-sidecars-v1.schema.json`](schemas/package-sidecars-v1.schema.json).

Top-level fields:

- `schemaVersion`: integer schema version, currently `1`.
- `packagePath`: queried package or sidecar path as passed to `cglc`,
  normalized for stable separators.
- `requestedExists`: whether the requested output package path currently exists.
- `publication`: the same publication object embedded by
  `cglc package inspect --json`.

The `publication` object contains the requested output path, the current
publication state, optional current-sidecar token data when the queried path is
itself a sidecar, and all sibling `.staging-*` / `.previous-*` sidecars found
next to the requested output path. `siblingSidecars` are sorted by normalized
path and include a `directory` flag so cleanup tools can distinguish complete
package sidecars from leftover files with valid sidecar names.
Each sidecar record path basename must match its fields:
`.<requested-output>.staging-<token>-<attempt>` or
`.<requested-output>.previous-<token>-<attempt>`.

`--list` is mutually exclusive with `--promote`, `--discard`, `--replace`, and
`--source`; it never verifies, promotes, or deletes packages.

## Stale Sidecar Cleanup JSON

`cglc package maintain <package-or-sidecar.cglb> --json` and
`cglc package recover <package-or-sidecar.cglb> --discard-stale --json` emit a
schema-versioned cleanup report. The current schema is
[`docs/schemas/package-stale-sidecars-v1.schema.json`](schemas/package-stale-sidecars-v1.schema.json).

Top-level fields:

- `schemaVersion`: integer schema version, currently `1`.
- `packagePath`: queried package or sidecar path as passed to `cglc`,
  normalized for stable separators.
- `dryRun`: `true` when the command only previewed cleanup candidates.
- `requestedExists`: whether the requested output package path currently exists.
- `keepLast`: requested newest-sidecar retention count, or `null` when no
  count retention was requested.
- `olderThanSeconds`: requested age threshold in seconds, or `null` when no age
  retention was requested.
- `retainedCount`: number of stale sidecars retained by `--keep-last`,
  `--older-than`, or both.
- `success`: `true` when all selected stale sidecars were either previewed or
  discarded without errors.
- `candidateCount`, `discardedCount`, and `failedCount`: cleanup result counts.
- `publication`: the same publication object emitted by `--list --json`.
- `candidates`: selected stale sidecars with path, sidecar naming fields,
  `reason`, `action`, and per-candidate `success`.
- `retained`: stale sidecars kept because they were within a retention window.
  Each retained entry includes `retainedBy` with `keep-last`, `younger-than`,
  or `age-unknown` so automation can explain why cleanup skipped it.
- `diagnosticCounts` and `diagnostics`: standard CrossGL diagnostics for cleanup
  failures.

Cleanup is intentionally guarded. `package maintain` and `recover
--discard-stale` default to dry-run mode and only delete files when `--apply` is
passed. `--dry-run` can be passed explicitly, but it cannot be combined with
`--apply`.
Use `--keep-last <n>` to retain the newest `n` stale recovery sidecar
directories by sidecar token, attempt, and path. Retention only applies to
directory sidecars; sidecar-named files remain cleanup candidates. Retained
entries report `retainedBy: "keep-last"`.
Use `--older-than <duration>` to retain stale sidecars whose filesystem
modification time is newer than the threshold. Durations are non-negative whole
numbers with optional `s`, `m`, `h`, or `d` suffixes; a suffixless value is
seconds. If `cglc` cannot inspect a sidecar's modification time, it retains that
sidecar and emits a warning diagnostic. Retained entries report
`retainedBy: "younger-than"` or `retainedBy: "age-unknown"`.
Use `--policy <policy.json>` to load `keepLast` and `olderThanSeconds` from a
schema-versioned policy file documented in
[`docs/PACKAGE_MAINTENANCE_POLICY_SCHEMA.md`](PACKAGE_MAINTENANCE_POLICY_SCHEMA.md).
Command-line `--keep-last` and `--older-than` override policy values.

The stale selection rules are conservative:

- `.previous-*` sidecars are stale backups.
- Sidecar-named paths that are not directories are stale leftovers.
- `.staging-*` sidecars are stale only when the requested output package already
  exists. Staging sidecars next to a missing requested package are left for
  explicit promotion or discard.

Cleanup `candidates` and `retained` entries follow the same sidecar basename
contract as `publication.siblingSidecars`.

`package maintain` is the operator-facing spelling for stale sidecar
maintenance. It emits the same schema as `recover --discard-stale`, accepts the
same retention, policy, and apply/dry-run options, and rejects recovery-only
flags such as `--list`, `--promote`, `--discard`, `--replace`, and `--source`.
Use `cglc package maintain --scan <dir> --json` to run the same stale-sidecar
maintenance across every package output group discovered in one directory. That
aggregate report is documented in
[`docs/PACKAGE_MAINTENANCE_REPORT_SCHEMA.md`](PACKAGE_MAINTENANCE_REPORT_SCHEMA.md)
and validated by
[`docs/schemas/package-maintenance-report-v1.schema.json`](schemas/package-maintenance-report-v1.schema.json).
Use `cglc package maintain --package-set <set.json> --json` when automation
already has an explicit list of package outputs to maintain; the set input and
aggregate report are documented in
[`docs/PACKAGE_MAINTENANCE_SET_SCHEMA.md`](PACKAGE_MAINTENANCE_SET_SCHEMA.md).
`--discard-stale` remains available as the recovery-subcommand spelling and is
mutually exclusive with `--list`, `--promote`, `--discard`, `--replace`, and
`--source`. `--keep-last`, `--older-than`, and `--policy` are accepted by
`package maintain` or by `recover --discard-stale`.
