# Package Maintenance Set JSON Schemas

`cglc package maintain --package-set <set.json>` reads a schema-versioned list
of package output paths and emits a schema-versioned aggregate cleanup report
when `--json` is present.

Input sets use
[`docs/schemas/package-maintenance-set-v1.schema.json`](schemas/package-maintenance-set-v1.schema.json).
JSON reports use
[`docs/schemas/package-maintenance-set-report-v1.schema.json`](schemas/package-maintenance-set-report-v1.schema.json).
Scan verification reports use
[`docs/schemas/package-maintenance-set-verification-v1.schema.json`](schemas/package-maintenance-set-verification-v1.schema.json).
Batch verification inputs use
[`docs/schemas/package-maintenance-set-verification-batch-v1.schema.json`](schemas/package-maintenance-set-verification-batch-v1.schema.json).
Batch verification reports use
[`docs/schemas/package-maintenance-set-verification-batch-report-v1.schema.json`](schemas/package-maintenance-set-verification-batch-report-v1.schema.json).
Batch verification summaries use
[`docs/schemas/package-maintenance-set-verification-batch-summary-v1.schema.json`](schemas/package-maintenance-set-verification-batch-summary-v1.schema.json).
Release promotion manifests use
[`docs/schemas/package-release-promotion-manifest-v1.schema.json`](schemas/package-release-promotion-manifest-v1.schema.json).
Release bundles use
[`docs/schemas/package-release-bundle-v1.schema.json`](schemas/package-release-bundle-v1.schema.json).
Release bundle verification reports use
[`docs/schemas/package-release-bundle-verification-v1.schema.json`](schemas/package-release-bundle-verification-v1.schema.json).

The set file is for automation that already knows the package outputs it wants
to maintain and should not rely on directory discovery. Relative package paths
are resolved relative to the set file's parent directory. Absolute package paths
are used as-is after lexical normalization. Duplicate resolved package paths are
rejected so scheduled cleanup jobs cannot accidentally produce ambiguous reports.

Use `cglc package maintain --scan <dir> --export-package-set <set.json>` to
generate a set from the same non-recursive discovery used by maintenance scans.
The export command writes package paths relative to the set file's parent
directory when possible. Export is discovery-only: cleanup flags such as
`--apply`, `--keep-last`, `--older-than`, and `--policy` are rejected while
`--export-package-set` is present. Add `--json` to print the generated set
document to stdout as well as writing it to disk.

Use `cglc package maintain --scan <dir> --verify-package-set <set.json>` to
check that a committed set still matches the same non-recursive discovery used
by maintenance scans. Verification is discovery-only: cleanup flags such as
`--apply`, `--keep-last`, `--older-than`, and `--policy` are rejected while
`--verify-package-set` is present. Add `--json` to emit a schema-versioned
comparison report. The command exits successfully only when the set loads, the
scan succeeds, and the resolved package paths match exactly.

Use `cglc package maintain --verify-package-set-batch <batch.json>` to run many
scan/set comparisons from one checked-in manifest. Each batch entry resolves
relative `rootPath` and `setPath` values against the batch file's parent
directory, then executes the same verification used by
`--scan <dir> --verify-package-set <set.json>`. Batch verification is
discovery-only and rejects cleanup flags. Add `--json` to emit an aggregate
report that preserves every nested verification report and rolls up matched,
mismatched, and operational failure counts. The command exits successfully only
when the batch loads, every verification completes, and every comparison
matches.
Add `--summary-output <summary.json>` to write a compact release-gate summary
next to the full report. The summary keeps aggregate success and mismatch
counts, per-verification package counts, mismatch lists, and diagnostic code
counts without repeating the complete scanned and set package arrays.

Use `cglc package release --promotion-summary <summary.json> --manifest-output
<manifest.json>` to consume that compact summary and write a release promotion
manifest. Add `--bundle-output <bundle.json>` to also write a compact release
bundle with aggregate artifact counts, byte totals, package file paths, and
hashes for upload or publish automation. The command exits successfully only
when the summary is release eligible. Blocked summaries still write a manifest,
and write a bundle when requested, with sorted blocker codes so CI and release
automation can preserve the gate decision as an artifact. Eligible manifests
also load the package sets named by the summary and include a checksummed
package artifact inventory for the publish step.

Use `cglc package release --verify-bundle <bundle.json>` before upload or
publish to validate a saved release bundle. The verifier checks the bundle's
internal counts, status, blocker ordering, package ordering, artifact ordering,
and declared package artifact sizes and hashes against the files on disk.
Blocked bundles remain valid audit artifacts but fail the command as a publish
gate. Add `--json` to emit a schema-versioned verification report.

Use `cglc package release --plan-publish <bundle.json> --plan-output
<plan.json>` after bundle verification to write a deterministic publish plan
without uploading anything. The command first runs the same bundle verifier and
only writes a plan for eligible bundles whose existing artifact files still
match their declared sizes and SHA-256 hashes. Add `--json` to print the plan
to stdout as well as writing it to disk.

Use `cglc package release --stage-publish <plan.json> --stage-output <dir>` to
materialize a verified publish plan into a local staging directory. Staging
rechecks source artifact sizes and SHA-256 hashes before it creates the stage
tree, copies each artifact to its deterministic destination path, and verifies
the staged copy. Add `--json` to emit a schema-versioned staging report.

Use `cglc package release --report-artifact-inventory` with any non-empty
subset of `--report-bundle <bundle.json>`, `--report-publish-plan <plan.json>`,
and `--report-publish-stage <stage-report.json>` to emit a deterministic
release report artifact inventory. The command only reads existing report
artifacts and has no staging, publishing, upload, mutation, or cloud side
effects. Add `--json` to emit the schema-versioned inventory report.

Use `cglc package release --publish-stage <stage-report.json> --publish-target
local-filesystem --target-output <dir>` to publish a successful local staging
report into an explicit filesystem target. The v2 executor also accepts
`--dry-run` to verify staged artifacts and report planned destinations without
writing the target tree. Add `--target-descriptor <target.json>` to provide a
[`schemas/package-release-publish-target-v1.schema.json`](schemas/package-release-publish-target-v1.schema.json)
target descriptor. `gcs` descriptors are validation-only in this release: they
must set `enabled=false`, must be paired with `--dry-run`, and never perform
network or credential access during publish planning. Use
`--upload-manifest-output` and the separate `--gcs-upload` command only after a
release owner approves a live remote publish record with project and budget
allowlist approval, explicit credentials, a scoped object prefix,
lifecycle/retention expectations, and audit receipt paths. The executor
rechecks each staged artifact before copying, refuses to overwrite existing
destinations, verifies every published artifact, and emits a schema-versioned
receipt. Add
`--receipt-output <receipt.json>` to persist that receipt in addition to
`--json` stdout.

Publish targets are resolved through a small backend capability layer before
artifact planning. `local-filesystem` advertises local path destinations and
direct copy support. `gcs` advertises URI destinations, a required descriptor,
disabled credentials during planning, and manifest-backed upload execution via
`--gcs-upload`.

Use `cglc package maintain --export-package-set-verification-batch <batch.json>`
to generate the batch manifest from command-line root/set pairs. Each repeated
`--verification <root> <set.json>` adds one batch entry. At least one
verification is required, duplicate resolved root/set pairs are rejected, and
paths are written relative to the batch file's parent directory when possible.
Add `--json` to print the generated batch manifest to stdout as well as writing
it to disk. Export is manifest-only: cleanup flags such as `--apply`,
`--keep-last`, `--older-than`, and `--policy` are rejected while
`--export-package-set-verification-batch` is present.

Input fields:

- `schemaVersion`: currently `1`.
- `packages`: non-empty array of package output paths. Each path should name a
  requested `.cglb` package output. Entries are sorted lexically and unique so
  generated set documents remain deterministic; the runtime still accepts
  missing requested outputs so stale previous sidecars can be cleaned while
  recoverable staging sidecars remain available.

Report top-level fields:

- `setPath`: package-set file used for the run.
- `dryRun`: `true` unless the command included `--apply`.
- `keepLast`: newest stale sidecar directory retention count, or `null`.
- `olderThanSeconds`: age threshold in seconds, or `null`.
- `success`: aggregate command success.
- `packageCount`: number of package paths loaded from the set.
- `retainedCount`, `candidateCount`, `discardedCount`, `failedCount`: aggregate
  counts across every package result.
- `packages`: sorted per-package stale sidecar cleanup results. Each item has
  the same shape as the single-package stale sidecar cleanup report documented
  in [`docs/PACKAGE_RECOVER_SCHEMA.md`](PACKAGE_RECOVER_SCHEMA.md).
- `diagnosticCounts` and `diagnostics`: aggregate diagnostics. Per-package
  diagnostics are also preserved in each `packages` item.

Verification report top-level fields:

- `rootPath`: scan root used for discovery.
- `setPath`: package-set file compared against the scan.
- `success`: `true` only when verification completed with no error diagnostics
  and the path lists match.
- `matches`: `true` when verification completes with no error diagnostics and
  `missingFromSet` and `extraInSet` are both empty.
- `scannedPackageCount`, `setPackageCount`, `missingFromSetCount`, and
  `extraInSetCount`: lengths of the corresponding path arrays.
- `scannedPackages`: sorted package output paths discovered from the scan root.
- `setPackages`: sorted resolved package output paths loaded from the set file.
- `missingFromSet`: sorted scan-discovered paths absent from the set.
- `extraInSet`: sorted set paths absent from scan discovery.
- `diagnosticCounts` and `diagnostics`: verification diagnostics. Diagnostic
  `code` and `message` fields must be non-empty so failed verification evidence
  remains actionable. A mismatch is reported as
  `package.maintain.set.verify.mismatch`.

Batch verification input fields:

- `schemaVersion`: currently `1`.
- `verifications`: non-empty array of scan/set comparison entries.
- `verifications[].rootPath`: scan root for one comparison. Relative paths are
  resolved against the batch file's parent directory.
- `verifications[].setPath`: package-set file for one comparison. Relative
  paths are resolved against the batch file's parent directory.

Batch verification report top-level fields:

- `batchPath`: batch manifest used for the run.
- `success`: `true` only when the batch loads, all nested verifications
  complete with no error diagnostics, and all nested path lists match.
- `matches`: `true` only when `success` is `true` and every nested
  verification reports `matches: true`.
- `verificationCount`: number of nested verification reports.
- `matchedCount`: number of nested verifications that matched.
- `mismatchedCount`: number of nested verifications with non-empty
  `missingFromSet` or `extraInSet`.
- `failedCount`: number of nested verifications that failed for reasons other
  than path-list mismatch, such as unreadable roots or malformed set files.
- `verifications`: nested verification reports using the single verification
  schema shape.
- `diagnosticCounts` and `diagnostics`: aggregate batch diagnostics. Nested
  verification diagnostics are preserved in the aggregate list.

Batch verification summary top-level fields:

- `batchPath`: batch manifest used for the run.
- `success`, `matches`: same aggregate booleans as the full batch report.
- `releaseEligible`: `true` only when `success` and `matches` are both `true`.
- `verificationCount`, `matchedCount`, `mismatchedCount`, and `failedCount`:
  same aggregate counters as the full batch report.
- `scannedPackageCount`, `setPackageCount`, `missingFromSetCount`, and
  `extraInSetCount`: sums of the corresponding per-verification counts.
- `verifications`: compact per-verification summaries with root/set paths,
  success booleans, package counts, mismatch lists, and diagnostic code counts.
  Each per-verification `scannedPackageCount` must equal `setPackageCount` plus
  `missingFromSetCount` minus `extraInSetCount`.
- `diagnosticCounts` and `diagnosticCodeCounts`: aggregate diagnostic counts for
  CI dashboards and release promotion checks.

Release promotion manifest top-level fields:

- `summaryPath`: verification summary consumed by the release gate.
- `manifestPath`: manifest path written by `cglc package release`.
- `batchPath`: batch manifest path copied from the verification summary.
- `status`: `eligible` or `blocked`.
- `releaseEligible`: `true` only when the summary is eligible, successful,
  matching, has no error diagnostics, and no blockers were generated.
- `blockerCount` and `blockers`: sorted blocker records explaining why
  promotion is blocked. Each blocker has `code`, `message`, and `count`.
- `packageCount` and `packages`: sorted package artifact inventory collected
  from existing outputs in eligible package sets. Requested outputs that are
  absent but represented by recoverable sidecars are skipped. Blocked summaries
  leave this list empty. Each package record includes `packagePath`, `module`,
  `target`, `sourceHash`, `nativeBinaryStatus`, `artifactCount`, and
  `artifacts`.
- `packages[].sourceHash`: source digest copied from the package
  `manifest.json`. Promotion inventory treats missing, unsupported, or
  non-lowercase SHA-256 source hashes as release blockers. The v1 schema still
  accepts `null` so older blocked manifests can be read, but eligible manifests,
  bundles, and publish plans fail semantic validation without this provenance.
- `packages[].packageArtifactRequirements`: artifact and native-status
  requirements copied from the package manifest. Release promotion, bundle
  verification, and publish planning validate required artifacts against this
  recorded package contract rather than deriving requirements from the target
  name.
- `packages[].artifacts`: sorted manifest artifact records with package-relative
  `name` and `path`, `exists`, `sizeBytes`, and per-file `sha256`. Planned
  source-package native binaries may be listed with `exists: false`,
  `sizeBytes: null`, and `sha256: null`; emitted or validated native binary
  status requires an existing `nativeBinary` artifact.
- `summary`: compact copy of the release-gate summary counts consumed by the
  command.
- `diagnosticCounts`: aggregate diagnostic counts copied from the summary.

Release bundle top-level fields:

- `bundlePath`: bundle path written by `cglc package release`.
- `promotionManifestPath`: promotion manifest that produced the bundle.
- `summaryPath` and `batchPath`: release-gate summary and batch manifest paths.
- `status`, `releaseEligible`, `blockerCount`, and `blockers`: same gate
  decision fields as the promotion manifest.
- `packageCount` and `packages`: sorted package inventory copied from the
  promotion manifest.
- `artifactCount`, `existingArtifactCount`, `missingArtifactCount`, and
  `totalArtifactBytes`: aggregate package artifact totals for release artifact
  uploads and provenance checks.
- `packages[].artifactCount`, `packages[].existingArtifactCount`,
  `packages[].missingArtifactCount`, and `packages[].totalArtifactBytes`:
  per-package totals matching each package's `artifacts` array.

Release bundle verification report top-level fields:

- `bundlePath`: bundle path passed to `--verify-bundle`.
- `success`: `true` only when the bundle is release eligible and verification
  emits no error diagnostics.
- `status` and `releaseEligible`: status copied from the bundle, or `invalid`
  when the bundle could not be parsed.
- `blockerCount`, `packageCount`, `artifactCount`, `existingArtifactCount`,
  `missingArtifactCount`, and `totalArtifactBytes`: counts copied from a valid
  bundle.
- `verifiedArtifactCount`: existing artifact files whose size and SHA-256 digest
  matched the bundle.
- `diagnosticCounts` and `diagnostics`: bundle parse, consistency, and artifact
  verification diagnostics. Artifact mismatches use the
  `package.release.bundle.*` diagnostic prefix.

Release publish plan top-level fields are covered by
[`schemas/package-release-publish-plan-v1.schema.json`](schemas/package-release-publish-plan-v1.schema.json):

- `bundlePath`: verified release bundle used as the plan source.
- `planPath`: publish plan path written by `cglc package release`.
- `releaseEligible`: always `true`; blocked bundles do not produce publish
  plans.
- `packageCount` and `packages`: sorted package records carried from the bundle
  with only existing publishable artifacts.
- `artifactCount`, `artifacts`, and `totalArtifactBytes`: flattened,
  destination-sorted artifact upload plan and byte total.
- `packages[].packageArtifactRequirements`: recorded package artifact
  requirements copied through from the bundle and revalidated before staging or
  publishing.
- `packages[].artifacts[]`: per-package copy of the flattened artifact records,
  including `sourcePath`, package-relative `packageArtifactPath`,
  deterministic `destinationPath`, `sizeBytes`, and `sha256`.

Release publish stage report top-level fields are covered by
[`schemas/package-release-publish-stage-v1.schema.json`](schemas/package-release-publish-stage-v1.schema.json):

- `planPath`: publish plan consumed by the stage command.
- `stagePath`: local staging directory.
- `success`: `true` only when every planned artifact was copied and verified.
- `packageCount`, `artifactCount`, and `totalArtifactBytes`: counts copied from
  the publish plan.
- `stagedArtifactCount` and `stagedArtifactBytes`: artifacts that were copied
  and verified in the staging directory.
- `artifacts[]`: flattened destination-sorted stage records with source,
  package-relative, destination, staged path, size, digest, and staged status.
- `diagnosticCounts` and `diagnostics`: plan parsing, source verification, copy,
  and staged artifact verification diagnostics.

Release report artifact inventory top-level fields are covered by
[`schemas/release-report-artifact-inventory-v1.schema.json`](schemas/release-report-artifact-inventory-v1.schema.json):

- `bundlePath`, `publishPlanPath`, and `stageReportPath`: report artifact paths
  read by the inventory command, or `null` when omitted.
- `artifactRecordCount`, source-kind counts, `stagedArtifactRecordCount`, and
  `totalArtifactRecordBytes`: deterministic counts and byte totals derived from
  the flattened `records` array.
- `records[]`: sorted `release-bundle`, `publish-plan`, and `publish-stage`
  artifact records with package path, package-relative artifact path, optional
  staged path, optional publish destination, byte size, and SHA-256 evidence.
- `diagnosticCounts` and `diagnostics`: report loading diagnostics under the
  `package.release.report.*` diagnostic prefix.

Release publish receipt top-level fields are covered by
[`schemas/package-release-publish-receipt-v2.schema.json`](schemas/package-release-publish-receipt-v2.schema.json).
Previous local-only receipt artifacts remain described by
[`schemas/package-release-publish-receipt-v1.schema.json`](schemas/package-release-publish-receipt-v1.schema.json):

- `stageReportPath`: successful staging report consumed by the publish command.
- `targetDescriptorPath`: optional target descriptor consumed by the publish
  command.
- `receiptPath` and `receiptWritten`: optional persisted receipt path and write
  status.
- `dryRun`: `true` when the command verified the stage and planned target
  destinations without writing artifacts.
- `targetKind`, `targetPath`, `targetUri`, and `targetEnabled`: resolved target
  identity. Local publishes mirror the normalized `targetPath` in `targetUri`;
  GCS dry-runs use a `gs://` target URI and require `targetEnabled=false`.
- `success`: `true` only when all staged artifacts were planned with no errors
  in dry-run mode, or copied and verified with no errors in publish mode.
- `packageCount`, `artifactCount`, and `totalArtifactBytes`: counts copied from
  the staging report.
- `plannedArtifactCount` and `plannedArtifactBytes`: artifacts whose staged
  copies were reverified and mapped to target destinations.
- `publishedArtifactCount` and `publishedArtifactBytes`: artifacts copied and
  verified in the publish target.
- `artifacts[]`: destination-sorted publish records with source, package,
  staged, planned, published, size, digest, and status fields.
- `diagnosticCounts` and `diagnostics`: stage report parsing, staged artifact
  verification, target creation, copy, and published verification diagnostics.

Release publish upload manifests are covered by
[`schemas/package-release-publish-upload-manifest-v1.schema.json`](schemas/package-release-publish-upload-manifest-v1.schema.json):

- `requestCount` and `requestBytes`: number of planned upload requests and their
  byte total.
- `requests[]`: destination-sorted upload requests. GCS requests include the
  local staged source path, package destination path, bucket, object name,
  `gs://` upload URI, required credential environment variable name, size, and
  SHA-256 digest. Standalone manifest validation rejects bucket-root object
  names and requires each object name to end with the package destination path;
  the release record must still compare those object names with the approved
  target descriptor prefix before treating a dry-run as live-readiness evidence.
  The real GCS upload command treats `credentialsEnv` as the name of the
  environment variable that must be set before upload; credential values are not
  written to reports. Live upload manifests must not rely on implicit
  application-default credentials, ambient `gcloud` accounts, metadata service
  credentials, or developer workstation credential discovery.

Release publish upload preflight reports are covered by
[`schemas/package-release-publish-upload-preflight-v1.schema.json`](schemas/package-release-publish-upload-preflight-v1.schema.json):

- `manifestPath`: upload manifest consumed by the preflight command.
- `reportPath` and `reportWritten`: optional persisted report path and write
  status.
- `dryRun`: always `true`; preflight validates local staged sources and request
  consistency without contacting a remote service.
- `requestCount` and `requestBytes`: counts copied from the upload manifest.
- `validatedRequestCount`, `validatedRequestBytes`, and `validatedRequests[]`:
  requests whose local staged source exists, matches the requested byte size,
  matches the requested SHA-256 digest, and remains within one normalized
  release-scoped object prefix.
- `diagnosticCounts` and `diagnostics`: manifest parsing, request consistency,
  local source verification, and report write diagnostics.

Release publish upload batch reports are covered by
[`schemas/package-release-publish-upload-batch-v1.schema.json`](schemas/package-release-publish-upload-batch-v1.schema.json):

- `manifestPath`: upload manifest consumed by a manifest-backed upload command.
- `reportPath` and `reportWritten`: optional persisted report path and write
  status.
- `uploadMode`: upload executor identity. `mock` exercises the validated upload
  boundary without contacting a remote service; `gcs` delegates to Google Cloud
  CLI after local validation; `custom` is used by in-process uploader
  integrations.
- `requestCount` and `requestBytes`: requested upload count and byte total.
- `uploadedArtifactCount`, `uploadedArtifactBytes`, and `uploadedRequests[]`:
  requests accepted by the selected uploader after local size and SHA-256
  verification. Uploaded GCS requests must preserve one release-scoped object
  prefix, matching the upload manifest and preflight evidence.
- `diagnosticCounts` and `diagnostics`: manifest parsing, local source
  verification, uploader failure, and report write diagnostics.

Release publish upload receipts are covered by
[`schemas/package-release-publish-upload-receipt-v1.schema.json`](schemas/package-release-publish-upload-receipt-v1.schema.json):

- `manifestPath`: upload manifest consumed by a manifest-backed upload command.
- `receiptPath` and `receiptWritten`: optional persisted receipt path and write
  status.
- `uploadMode`: upload executor identity, matching the upload batch report.
- `requestCount` and `requestBytes`: requested upload count and byte total.
- `attemptCount`, `attemptBytes`, `completedAttemptCount`, and
  `completedAttemptBytes`: detailed attempt accounting. `uploaded` and
  `already-present` attempts count as completed; `failed` attempts do not.
- `attempts[]`: destination-sorted upload attempts. Each attempt carries the
  full upload request plus provider, overwrite mode, idempotency key,
  precondition metadata, provider object metadata, and failure message. Attempt
  requests must preserve one release-scoped GCS object prefix, matching the
  upload manifest, preflight, and batch evidence.
  Real GCS uploads populate remote generation, metageneration, CRC32C, and MD5
  fields by describing the uploaded object when `--upload-receipt-output` is
  requested; completed GCS receipts used as release evidence must preserve
  non-empty remote metadata.
- Retry and reconciliation tooling can compare attempts without contacting a
  remote service by using the deterministic `idempotencyKey` plus the embedded
  request destination, byte size, and SHA-256. Mock uploads always emit
  `provider=mock`, omit overwrite, precondition, generation, metageneration,
  CRC32C, and MD5 fields, and use the same lowercase SHA-256 fingerprint that
  a GCS upload would use for the same request. GCS receipts use
  `provider=gcs`; create-only attempts record `ifGenerationMatch=0`, while
  overwrite attempts intentionally leave precondition fields empty. `uploaded`
  and `already-present` attempts are both completed outcomes during
  reconciliation.
- `diagnosticCounts` and `diagnostics`: manifest parsing, local source
  verification, uploader failure, and receipt write diagnostics.

Release publish target descriptors are covered by
[`schemas/package-release-publish-target-v1.schema.json`](schemas/package-release-publish-target-v1.schema.json):

- `schemaVersion`: `1`.
- `targetKind`: `local-filesystem` or `gcs`.
- `enabled`: whether this descriptor is allowed to perform writes. Local
  descriptors with `enabled=false` are valid for dry-runs only; non-dry-run
  local publishes require `enabled=true`. `gcs` descriptors remain
  `enabled=false` during publish planning; remote writes happen later from the
  upload manifest through `--gcs-upload`.
- `targetPath`: local filesystem target path for `local-filesystem`
  descriptors. It is required for local descriptors and must not be present for
  `gcs` descriptors.
- `bucket`, `prefix`, and `credentialsEnv`: GCS destination metadata used only
  for validation and deterministic `gs://` URI planning in this release. All
  three are required for `gcs`; `prefix` must be a normalized release-scoped
  object prefix and `credentialsEnv` must name the explicit credential
  environment gate. These fields must not be present on `local-filesystem`
  descriptors. Live release descriptors must be backed by an approved GCP
  project and budget allowlist entry, must use a release-scoped object prefix
  rather than a bucket root or shared scratch prefix, and must name an explicit
  `credentialsEnv` gate.

Example set:

```json
{
  "schemaVersion": 1,
  "packages": [
    "build/packages/lighting.cglb",
    "build/packages/postprocess.cglb"
  ]
}
```

Example command:

```sh
cglc package maintain --package-set packages-to-maintain.json --policy cleanup-policy.json --json
```

Example export command:

```sh
cglc package maintain --scan build/packages --export-package-set packages-to-maintain.json --json
```

Example verification command:

```sh
cglc package maintain --scan build/packages --verify-package-set packages-to-maintain.json --json
```

Example batch verification input:

```json
{
  "schemaVersion": 1,
  "verifications": [
    {
      "rootPath": "build/packages",
      "setPath": "packages-to-maintain.json"
    },
    {
      "rootPath": "build/examples",
      "setPath": "example-packages-to-maintain.json"
    }
  ]
}
```

Example batch verification command:

```sh
cglc package maintain --verify-package-set-batch package-set-verifications.json --json
```

Example batch summary command:

```sh
cglc package maintain \
  --verify-package-set-batch package-set-verifications.json \
  --summary-output package-set-verification-summary.json \
  --json
```

The main CI workflow uploads the generated set, batch manifest, full
verification report, summary, release promotion manifest, release bundle, and
release bundle verification report, and stdout mirrors as
`package-maintenance-Linux` and `package-maintenance-macOS` artifacts. Release
promotion jobs should prefer the manifest for the gate decision, prefer the
bundle for publish file lists and hashes, run `--verify-bundle` immediately
before publish, and retain the summary and full report for audit details.

Example release promotion manifest command:

```sh
cglc package release \
  --promotion-summary package-set-verification-summary.json \
  --manifest-output package-release-promotion-manifest.json \
  --bundle-output package-release-bundle.json \
  --json
```

Example release bundle verification command:

```sh
cglc package release \
  --verify-bundle package-release-bundle.json \
  --json
```

Example release publish plan command:

```sh
cglc package release \
  --plan-publish package-release-bundle.json \
  --plan-output package-release-publish-plan.json \
  --json
```

Example release publish stage command:

```sh
cglc package release \
  --stage-publish package-release-publish-plan.json \
  --stage-output package-release-stage \
  --json
```

Example release report artifact inventory command:

```sh
cglc package release \
  --report-artifact-inventory \
  --report-bundle package-release-bundle.json \
  --report-publish-plan package-release-publish-plan.json \
  --report-publish-stage package-release-publish-stage.json \
  --json
```

Example release publish command:

```sh
cglc package release \
  --publish-stage package-release-publish-stage.json \
  --publish-target local-filesystem \
  --target-output package-release-published \
  --receipt-output package-release-publish-receipt.json \
  --json
```

Example GCS validation-only dry-run:

```json
{
  "schemaVersion": 1,
  "targetKind": "gcs",
  "enabled": false,
  "bucket": "crossgl-release-dry-run",
  "prefix": "compiler/packages",
  "credentialsEnv": "GOOGLE_APPLICATION_CREDENTIALS"
}
```

```sh
cglc package release \
  --publish-stage package-release-publish-stage.json \
  --publish-target gcs \
  --target-descriptor package-release-gcs-target.json \
  --upload-manifest-output package-release-publish-upload-manifest.json \
  --dry-run \
  --json
```

The dry-run bucket descriptor above is for deterministic validation only. A
live remote release must use a release-owner-approved project, bucket, budget
guardrail, lifecycle/retention plan, and release-scoped prefix for the exact
artifact set; actual budget values and retention durations are recorded in the
operator release record, not in this schema guide.

Example upload preflight command:

```sh
cglc package release \
  --upload-manifest package-release-publish-upload-manifest.json \
  --upload-report-output package-release-publish-upload-preflight.json \
  --dry-run \
  --json
```

Example mock upload command:

```sh
cglc package release \
  --upload-manifest package-release-publish-upload-manifest.json \
  --mock-upload \
  --upload-report-output package-release-publish-upload-batch.json \
  --upload-receipt-output package-release-publish-upload-receipt.json \
  --json
```

Operator-approved live GCS upload shape:

Before a live `--gcs-upload`, the release record must include the same
machine-readable approval evidence that the provenance and guardrail checkers
require for `live-cloud` mode. The values must be explicit release-owner
approvals, not placeholders:

```json
{
  "approvalRecord": "release-approval-v0.1.0-20260601",
  "projectAllowlistEntry": "gcp-project:crossgl-release-prod",
  "bucketAllowlistEntry": "gcs-bucket:crossgl-release-artifacts",
  "budgetGuardrail": "budget:crossgl-release-prod:v0",
  "releaseObjectPrefix": "compiler/releases/v0.1.0",
  "lifecyclePolicy": "lifecycle:release-artifacts-retain-90d",
  "auditReceiptPaths": [
    "package-release-publish-upload-batch.json",
    "package-release-publish-upload-receipt.json"
  ]
}
```

```sh
export GOOGLE_APPLICATION_CREDENTIALS=<explicit-release-credential-file>

cglc package release \
  --upload-manifest package-release-publish-upload-manifest.json \
  --gcs-upload \
  --upload-report-output package-release-publish-upload-batch.json \
  --upload-receipt-output package-release-publish-upload-receipt.json \
  --json
```

The command shape above is not a validation command and must not be used by CI,
pre-commit, or readiness gates. Run it only after the release owner has approved
the project allowlist entry, budget guardrail, release-scoped object prefix,
lifecycle/retention expectation, rollback plan, and audit receipt paths for the
exact upload manifest. `tools/check_release_provenance_manifest.py` and
`tools/check_package_release_publish_flow.py` reject `live-cloud` guardrail
records unless this approval evidence is present and non-placeholder.

`--gcs-upload` requires the Google Cloud CLI (`gcloud`) on `PATH` and a
named credential environment variable configured with permission to write only
to the approved bucket and prefix. Each request is locally revalidated for
existence, size, and SHA-256 before a create-only `gcloud storage cp` command
with `--if-generation-match=0` is invoked. This prevents the default upload path
from overwriting an existing object. Add `--gcs-upload-overwrite` only when
replacing existing objects is intentional; overwrite mode omits the generation
precondition. Real GCS uploads also stamp object custom metadata with
`crossgl-sha256`, `crossgl-size-bytes`, and a deterministic
`crossgl-upload-fingerprint`, giving later release tooling a stable identity to
compare during retry or object inspection flows. The command fails closed when a
request omits `credentialsEnv` or the named environment variable is unset; the
value is treated as an explicit credential gate and is never written to reports.
Every live attempt must write an upload batch report and upload receipt that
preserves provider object metadata such as generation, metageneration, CRC32C,
MD5, byte size, and SHA-256 when available.

Example batch export command:

```sh
cglc package maintain \
  --export-package-set-verification-batch package-set-verifications.json \
  --verification build/packages packages-to-maintain.json \
  --verification build/examples example-packages-to-maintain.json \
  --json
```

Use `--apply` to delete selected stale sidecars. Policy files only configure
retention; deletion is still controlled exclusively by the command line.
