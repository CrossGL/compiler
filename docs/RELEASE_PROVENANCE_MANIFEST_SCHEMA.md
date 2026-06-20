# Release Provenance Manifest JSON Schema

`tools/check_release_provenance_manifest.py` writes and validates the offline
release provenance manifest described by
[`docs/schemas/release-provenance-manifest-v1.schema.json`](schemas/release-provenance-manifest-v1.schema.json).
The manifest is a public release record contract for local checksums,
source provenance, toolchain summary data, and cloud-upload guardrail evidence.
It does not upload artifacts or call cloud provider tools.

## Contract

Top-level fields:

- `schemaVersion`: currently `1`.
- `kind`: `crossgl-release-provenance-manifest-v1`.
- `sourceCommit`: 40-character lowercase hexadecimal Git commit recorded for
  the release artifact set.
- `toolchainSummary`: non-empty object of string toolchain keys and non-empty
  string values. The checker records `python` and `platform` by default and
  accepts additional `KEY=VALUE` entries.
- `cloudUpload`: cost-control and upload-mode summary copied from release
  guardrail records.
- `artifactCount`: number of artifact records.
- `artifactBytes`: sum of `artifacts[].sizeBytes`.
- `artifacts`: sorted non-empty list of checksummed local artifact records.

Artifact fields:

- `path`: artifact-root-relative POSIX path to the file that was hashed.
- `sizeBytes`: non-negative byte size.
- `sha256`: lowercase SHA-256 digest.
- `destinationPath`: optional staged or publish destination path.
- `packagePath`: optional artifact-root-relative package path, recorded with
  `packageArtifactPath` when package input traceability is available.
- `packageArtifactPath`: optional package-relative artifact path, recorded with
  `packagePath` when package input traceability is available.

All artifact paths are normalized POSIX paths. They must not be absolute, use
Windows drive prefixes, use URI schemes, contain backslashes, or contain empty,
`.` or `..` path components. `path` values are unique. Non-empty
`destinationPath` values are unique. `packagePath` and `packageArtifactPath`
are both empty or both non-empty. Non-empty `(packagePath, packageArtifactPath)`
pairs are unique.

## Cloud Upload Guardrails

`cloudUpload.mode` and every value in `cloudUpload.modes` must be one of:

- `local-only`
- `dry-run`
- `mock`
- `live-cloud`

`cloudUpload.mode` must appear in `cloudUpload.modes`, and `modes` is sorted
and unique in generated manifests. Routine validation records only safe modes:
`local-only`, `dry-run`, and `mock`.

If any mode is `live-cloud`, the record must set
`liveCloudUploadAllowed=true`, set `liveCloudUploadOptIn` to either `cli-flag`
or `CROSSGL_ALLOW_LIVE_CLOUD_RELEASE_UPLOAD`, and include an
`approvalEvidence` object. Approval evidence must use explicit non-placeholder
values for:

- `approvalRecord`
- `projectAllowlistEntry`
- `bucketAllowlistEntry`
- `budgetGuardrail`
- `releaseObjectPrefix`
- `lifecyclePolicy`
- `auditReceiptPaths`

`releaseObjectPrefix` and every audit receipt path use normalized relative path
rules. `releaseObjectPrefix` must also be scoped to a concrete release namespace
or release identifier; bucket-root, shared scratch, temporary, or generic upload
prefixes are rejected. Placeholder values such as `tbd`, `todo`, `none`, `n/a`,
`placeholder`, and bracketed values like `<approved-gcp-project-id>` are
rejected.

## Report-Only Promotion, Rollback, and Cost Evidence

The manifest schema does not add promotion or rollback fields. Instead, release
operators may preserve a separate report artifact, then pass it to the checker
with `--release-evidence-report <report.json>`. The checker verifies that the
report path is present in `artifacts[].path`, so the provenance manifest hashes
and preserves the report bytes with the release artifact set.

The report-only evidence object is expected to contain a
`rollbackPromotionAudit` object with these fields:

- `dryRunDefault`: `true`, proving the planning run stayed offline.
- `promotionDecision`, `promotionManifestPath`,
  `releaseBundleVerificationPath`, `packageVerification`, `sourceCommit`,
  `toolchainSummary`, `operatorIdentity`, `decisionTime`, and
  `rejectionReason` when the decision is not `promote`.
- `rollbackInputs.previousPromotionManifestPath`,
  `rollbackInputs.previousVerifiedBundlePath`,
  `rollbackInputs.publishedObjectGenerations`,
  `rollbackInputs.rollbackPlanPath`, and `rollbackInputs.rollbackHorizon`.
- `releaseObjectPrefix`, validated with the same release-scoped prefix rules as
  live approval evidence.
- `receiptPaths.uploadReceiptPaths`, `receiptPaths.dryRunReceiptPaths`,
  `receiptPaths.failedAttemptReceiptPaths`,
  `receiptPaths.preflightReportPath`, and
  `receiptPaths.providerObjectMetadata`.
- Provider object metadata fields `generation`, `metageneration`, `crc32c`,
  `md5`, `sha256`, and `sizeBytes`.
- `allowlistReferences.projectAllowlistEntry`,
  `allowlistReferences.bucketAllowlistEntry`,
  `allowlistReferences.budgetGuardrail`,
  `allowlistReferences.credentialsEnv`, and
  `allowlistReferences.liveCloudUploadOptInState`.
- `retentionReview.lifecyclePolicy`, `retentionReview.retentionReview`,
  `retentionReview.cleanupOwner`, and `retentionReview.rollbackHorizon`.

This report-only check is deterministic and local. It does not upload artifacts,
read GCP credentials, invoke `gcloud` or `gsutil`, or call cloud APIs.

## Validation

Use the checker for end-to-end validation because it also verifies artifact file
existence, byte sizes, and SHA-256 checksums against the chosen artifact root:

```sh
python3 tools/check_release_provenance_manifest.py --manifest <manifest.json> --artifact-root <dir>
```

Validate a manifest plus a preserved promotion/rollback/cost evidence report:

```sh
python3 tools/check_release_provenance_manifest.py \
  --manifest <manifest.json> \
  --artifact-root <dir> \
  --release-evidence-report <dir>/release/rollback-promotion-audit.json
```

Run the root audit and offline self-test:

```sh
python3 tools/check_release_provenance_manifest.py --root .
python3 tools/check_release_provenance_manifest.py --self-test
```

Use the generic schema validator for shape and semantic contract validation:

```sh
python3 tools/validate_json_schema.py \
  --schema docs/schemas/release-provenance-manifest-v1.schema.json \
  --instance <manifest.json>
```
