# CrossGL v0 Release Artifact Policy

This operator-owned policy defines what CrossGL Compiler v0 may publish, which
evidence must exist before promotion, and which cloud actions are allowed in
routine validation. It is a release gate scaffold, not live deployment
automation.

## Operator Ownership

- This is an operator-owned release surface: a release operator owns every
  publish decision for v0 artifacts. Automation can prepare plans, stages,
  manifests, receipts, and verification reports, but it must not promote or
  upload artifacts without an operator-approved release record.
- The operator must keep the release bundle, promotion manifest, staged publish
  report, upload manifest, upload receipts, and package verification outputs
  together as one auditable release record.
- The stable policy anchor for operator approvals, provenance manifests, upload
  receipts, and gate output is `crossgl-v0-release-artifact-policy`; release
  records must cite this anchor when recording why a v0 artifact set was
  accepted or rejected.
- The operator must reject any artifact set whose target support claim conflicts
  with `tools/package_target_contracts.json`, `docs/package-targets.md`, or the
  current v0 readiness page.

## Publishable v0 Artifact Set

The only publishable v0 artifacts are compiler-generated `.cglb` package
directories and release metadata derived from those packages. Source packages
for DirectX and OpenGL may be published as source-package artifacts; native
packages for Metal and Vulkan may be published only when the matching native
toolchain has produced and validated the expected binary artifacts.

The policy references these public schema surfaces:

- `docs/JSON_SCHEMAS.md`
- `docs/MANIFEST_JSON_SCHEMA.md`
- `docs/PACKAGE_VERIFY_SCHEMA.md`
- `docs/PACKAGE_MAINTENANCE_SET_SCHEMA.md`
- `docs/PACKAGE_INSPECT_SCHEMA.md`
- `docs/DEBUG_METADATA_SCHEMA.md`
- `docs/HIR_SOURCE_MAP_SCHEMA.md`
- `docs/schemas/package-release-bundle-v1.schema.json`
- `docs/schemas/package-release-bundle-verification-v1.schema.json`
- `docs/schemas/package-release-promotion-manifest-v1.schema.json`
- `docs/schemas/package-release-publish-plan-v1.schema.json`
- `docs/schemas/package-release-publish-stage-v1.schema.json`
- `docs/schemas/package-release-publish-target-v1.schema.json`
- `docs/schemas/package-release-publish-receipt-v2.schema.json`
- `docs/schemas/package-release-publish-upload-manifest-v1.schema.json`
- `docs/schemas/package-release-publish-upload-preflight-v1.schema.json`
- `docs/schemas/package-release-publish-upload-batch-v1.schema.json`
- `docs/schemas/package-release-publish-upload-receipt-v1.schema.json`
- `docs/schemas/release-report-artifact-inventory-v1.schema.json`
- `docs/RELEASE_REPORT_ARTIFACT_INVENTORY_SCHEMA.md`

Earlier `package-release-publish-receipt-v1.schema.json` receipts remain
historical compatibility records only; new v0 publishing must use receipt v2.

## Required Dry-Run Behavior

Routine validation must be offline and deterministic. Dry-run is the default
for any remote-capable publish path until a release owner approves a live
release record. The default release gate is
`tools/check_package_release_publish_flow.py`, which exercises local publish,
GCS dry-run, upload preflight, mock upload, and fake `gcloud` upload paths
without writing to real cloud storage.

Allowed non-live modes are:

- `local-only`
- `dry-run`
- `mock`

The helper must continue to emit `package-release-publish-guardrails.json` so
operators can prove which actions were dry-run, mock, or local-only. Each
guardrail record must name an `operation`, a `targetKind`, and a known `mode`.
For GCS records, the mode-specific guardrail flags must match the recorded mode:
`dry-run` records set only `dryRun`, `local-only` records set only `localOnly`,
and `mock` records set only `mockUpload`. Normal CI, pre-commit, and readiness
checks must not bind live-upload opt-in environment variables, pass live upload
flags, or attach GCP credential environment variables; equivalently, routine
automation must not set live-upload opt-ins.

The publish-flow helper must also emit
`package-release-publish-rc-handoff-evidence.json` as a local-only index for
release-candidate handoff. That handoff record must include
`rcHandoffEvidence` with local filesystem paths for `provenanceManifestPath`,
`artifactInventoryPath`, `guardrailRecordPath`, `dryRunReceiptPaths`,
`uploadManifestPath`, `preflightReportPath`, `mockReceiptPaths`, and
`fakeGcloudReceiptPaths`. The same record must mirror the dry-run path fields in
`dryRunArtifactEvidence` and the provenance paths in
`provenanceChecksumEvidence` so the RC report reviewer can find the release
publish evidence without using provider URLs or live cloud credentials.

## Provenance and Checksums

Every publishable package must have deterministic provenance and checksum
evidence:

- `tools/check_release_provenance_manifest.py` writes and validates the
  `release-provenance-manifest-v1` dry-run manifest for staged release
  artifacts before upload. The record must include `sourceCommit`,
  `toolchainSummary`, artifact paths, `sizeBytes`, and `sha256` for every file.
  Artifact paths are validated relative to `--artifact-root`, which defaults to
  the repository root for local checks and can be the release work directory for
  staged publish flows.
- When a release record preserves report-only promotion, rollback, and cost
  evidence, pass that JSON record to
  `tools/check_release_provenance_manifest.py` with
  `--release-evidence-report`. The checker verifies that the report itself is a
  checksummed `artifacts[].path` entry and that the report preserves
  `projectAllowlistEntry`, `bucketAllowlistEntry`, `budgetGuardrail`,
  `releaseObjectPrefix`, `promotionManifestPath`, `rollbackPlanPath`,
  `uploadReceiptPaths`, `dryRunReceiptPaths`, `failedAttemptReceiptPaths`,
  `preflightReportPath`, and provider object metadata. This check is local and
  does not call cloud providers.
- `manifest.json` records module, target, artifact paths, compiler identity,
  and `sourceHash` using `sha256`.
- `cglc package verify --json` must succeed for each package that enters a
  release bundle.
- `tools/check_package_reproducibility.py --report` must keep first-class
  evidence for manifest `sourceHash` parity with the source input, manifest
  compiler identity, the local `cglc` toolchain fingerprint, package inspect
  provenance, manifest-declared `nativeArtifactDescriptor` path/`sizeBytes`/
  `sha256` facts when native package artifacts are present, descriptor
  `optimizationLevel` and optional `optimizationEvidence` when the descriptor
  exists, and the normalized package verify digest. Descriptor evidence is read only from
  `manifest.artifacts.nativeArtifactDescriptor`; `metadata/native-artifact.json`
  is not an implicit fallback.
- Release bundle and bundle verification records must bind the package set,
  promotion manifest, and package verification results.
- Release report artifact inventories using `release-report-artifact-inventory-v1`
  must record `nativeArtifactDescriptor` evidence at the package-relative path
  listed by `manifest.artifacts.nativeArtifactDescriptor` whenever native
  package artifacts are present. Compiler-produced descriptor paths use the
  `.native-artifact.json` suffix, for example
  `backend/<target>/<module>.native-artifact.json`. Descriptor inventory records
  must include `sizeBytes` and `sha256`; absent or stale descriptor evidence is
  a release blocker.
- Optional debug artifacts, including `ir/debug-metadata.json`,
  `ir/hir-source-map.json`, and `ir/target-explanation.json`, must be present
  when debug IR is advertised by the package manifest. Debug metadata and the
  HIR source map remain the validated pair; target explanations use the
  target-explanation v1 schema.
- Upload receipts must include provider object metadata, checksum fields, and
  generation or equivalent object identity when an upload mode records them.

No operator should promote artifacts whose manifest checksum, release bundle
checksum, upload receipt checksum, or package verification summary is missing,
stale, or mismatched.

### Release record evidence checklist

Every auditable release record must keep these machine-readable evidence fields
with the bundle, promotion manifest, staged publish report, upload manifest,
upload receipts, and package verification output:

| Field group | Required evidence fields | Audit purpose |
| --- | --- | --- |
| Policy anchor | `policyAnchor` set to `crossgl-v0-release-artifact-policy` | Binds the release decision to this operator-owned policy. |
| Source commit | `sourceCommit` as a 40-character lowercase hexadecimal Git commit | Identifies the exact repository source used to produce the artifact set. |
| Toolchain summary | `toolchainSummary` as a non-empty key/value object | Records the local compiler, Python, platform, and native-tool context used by the dry-run release check. |
| Artifact inventory | `artifactCount`, `artifactBytes`, `artifacts[].path`, and `artifacts[].sizeBytes` | Lets auditors compare the release bundle with the staged files that were hashed. |
| Artifact checksum | `artifacts[].sha256` as a SHA-256 digest for every file | Proves artifact bytes have not drifted between staging, verification, and receipt capture. |
| Native descriptor inventory | `nativeArtifactDescriptor`, `manifest.artifacts.nativeArtifactDescriptor`, `.native-artifact.json`, `release-report-artifact-inventory-v1`, `sizeBytes`, `sha256`, descriptor `optimizationLevel`, and optional descriptor `optimizationEvidence` whenever native package artifacts are present | Proves native binary packages retained descriptor byte and optimizer evidence through package inspect, bundle, plan, and stage inventory reports. |
| Package verification | `packageVerification`, `cglc package verify --json`, and the verification digest | Links each package in the bundle to the package verifier result that accepted it. |
| Receipt paths | `provenanceManifestPath`, `promotionManifestPath`, `uploadReceiptPaths`, `dryRunReceiptPaths`, `failedAttemptReceiptPaths`, `preflightReportPath`, and `rollbackPlanPath` | Makes the provenance, promotion, upload, preflight, failed-attempt, and rollback evidence discoverable from the release record. |
| Cloud upload guardrails | `cloudUpload.mode`, `cloudUpload.modes`, and `approvalEvidence` | Shows that validation stayed dry-run/mock/local-only, or that live-cloud evidence had explicit approval. |

The provenance manifest checker is local-only by default. It may cite GCS
dry-run/mock/local-only guardrail records, but it must reject live cloud modes
unless the operator passes `--allow-cloud-upload` or sets
`CROSSGL_ALLOW_LIVE_CLOUD_RELEASE_UPLOAD=1`. Even with that opt-in, a live
cloud provenance manifest or guardrail record must carry an `approvalEvidence`
object with explicit project/bucket allowlist, budget, release prefix,
lifecycle, and audit receipt path evidence, plus a `liveCloudUploadOptIn` source.
The manifest `cloudUpload.mode` value must be known and must be included in
`cloudUpload.modes`. The checker rejects placeholder values such as
`<approved-gcp-project-id>`. The checker does not perform uploads or call cloud
provider tools.

## Promotion and Rollback

Promotion is a two-step operator action:

1. Accept a verified package release bundle and
   `package-release-promotion-manifest-v1.schema.json` record.
2. Publish the staged artifact set only after the operator compares the plan,
   stage report, target descriptor, upload manifest, and receipt paths.

Promotion, bundle verification, and publish planning consume
`packages[].packageArtifactRequirements` copied from each package manifest. They
must reject records whose required artifacts or native-binary status disagree
with that recorded package contract instead of re-inferring requirements from
the release target name.
Promotion manifest evidence pointers such as `summaryPath`, `manifestPath`, and
`batchPath` must remain normalized relative paths so dry-run promotion evidence
can be replayed from the release bundle without relying on workstation absolute
paths.

rollback must be metadata-first. The operator should retain the previous
promotion manifest and published object generation identifiers, then promote the
previous verified bundle rather than mutating an existing bundle in place. A
failed publish attempt must preserve its dry-run or upload receipts so future
operators can distinguish skipped, staged, uploaded, and rolled-back objects.

Promotion/rollback receipt chain requirements are report-only release policy
controls until live release ownership is assigned. The release record must keep
the promotion receipt, rollback receipt or rollback plan, prior promotion
manifest, failed-attempt upload receipts, and the previous verified bundle
together so auditors can prove whether the operator promoted, skipped,
published, or rolled back each object.

### Rollback/promotion provenance planning checklist

Rollback and promotion planning remains report-only until a release owner
assigns live release ownership. A release may attach a `rollbackPromotionAudit`
object or equivalent table to the release record, but the metadata must not
drive live cloud calls, mutate remote objects, or infer approval. The checklist
below defines the minimum audit shape for dry-run promotion and rollback
planning.

| Control | Required report-only evidence |
| --- | --- |
| Dry-run evidence baseline | Dry-run remains the default; `local-only`, `dry-run`, and `mock` evidence must cover the exact artifact set before review, and the planning record must state that it created no live cloud objects. |
| Release-scoped object prefix | Record `releaseObjectPrefix`, the target-approved prefix, and the release-scoped object prefix used by the target descriptor; bucket-root uploads, parent-directory traversal, shared scratch prefixes, and mixed release-scoped object prefixes remain blockers. |
| Promotion decision evidence | Record `promotionDecision`, `promotionManifestPath`, `releaseBundleVerificationPath`, `packageVerification`, `sourceCommit`, `toolchainSummary`, accepted package set, operator identity, decision time, and rejection reason when the decision is not promote. |
| Rollback inputs | Record `rollbackInputs`, `previousPromotionManifestPath`, `previousVerifiedBundlePath`, `publishedObjectGenerations`, `rollbackPlanPath`, `rollbackHorizon`, and the package/version identity that would become current after rollback. |
| Receipt preservation | Record `uploadReceiptPaths`, `dryRunReceiptPaths`, `preflightReportPath`, `failedAttemptReceiptPaths`, provider object metadata, generation, metageneration, checksum fields, and skipped/staged/uploaded/rolled-back object status. |
| Retention and lifecycle review | Record `lifecyclePolicy`, `retentionReview`, `cleanupOwner`, `rollbackHorizon`, cleanup exception notes, and whether lifecycle rules preserve receipts long enough for the approved rollback window. |
| Project/budget allowlist references | Record `projectAllowlistEntry`, `bucketAllowlistEntry`, `budgetGuardrail`, `credentialsEnv`, and whether `CROSSGL_ALLOW_LIVE_CLOUD_RELEASE_UPLOAD` was absent, present, or forbidden for the planning run. |

The report-only metadata proposal is:

```json
{
  "rollbackPromotionAudit": {
    "dryRunDefault": true,
    "promotionDecision": "promote|reject|hold",
    "rollbackInputs": {
      "previousPromotionManifestPath": "release/previous-promotion.json",
      "previousVerifiedBundlePath": "release/previous-bundle.json",
      "publishedObjectGenerations": []
    },
    "releaseObjectPrefix": "<approved-release-object-prefix>",
    "receiptPaths": {
      "uploadReceiptPaths": [],
      "dryRunReceiptPaths": [],
      "failedAttemptReceiptPaths": []
    },
    "allowlistReferences": {
      "projectAllowlistEntry": "<approved-gcp-project-id>",
      "bucketAllowlistEntry": "<approved-gcp-bucket>",
      "budgetGuardrail": "<approved-budget-limit>"
    }
  }
}
```

The placeholders above are acceptable only for planning records. Before real
binary shipment, the operator owns replacement of every placeholder with an
approved explicit value, review of the lifecycle/retention policy, preservation
of the prior promotion and failed-attempt receipts, and sign-off that rollback
uses a previous verified bundle instead of modifying a published bundle in
place. These controls are operator-owned before real binary shipment.

## GCP Cost Guardrails

GCP release validation must not create real objects by default. Live GCS upload
paths require an explicit operator opt-in through `--allow-cloud-upload` or
`CROSSGL_ALLOW_LIVE_CLOUD_RELEASE_UPLOAD=1`, and normal CI, pre-commit, or local
readiness gates must never bind that environment variable, pass live upload
flags, or bind `GOOGLE_APPLICATION_CREDENTIALS`.

The release helper may use the dry-run bucket descriptor
`crossgl-release-dry-run` and fake `gcloud` shim only for deterministic tests.
That dry-run bucket must not be reused as a live release target.
Any future live cloud release code must call the guardrail helper in
`tools/check_package_release_publish_flow.py` before invoking provider CLIs or
SDKs.
Routine CI, pre-commit, and release validation must also avoid direct HTTP
cloud access: no `curl`, `wget`, PowerShell web cmdlets, Python HTTP clients,
Google provider SDK imports, or Google API endpoint strings may be added to
release validation paths as a substitute for the dry-run/mock/fake-`gcloud`
contract.
Release-readiness paths must also avoid live package or release publishing
commands and Actions, including registry uploads, GitHub release publishing,
Google cloud auth/setup Actions, and live GitHub billing or organization
setting queries. Cost evidence for v0 readiness remains local/static and
report-only; stop and hand back if a real billing query or organization setting
read is needed.

### Live GCP publish policy gate

Any live GCP release/publish path is blocked unless all rows below are
satisfied by recorded evidence. This is an audited policy gate for the existing
release flow, not a new release mechanism, and the checks remain offline.

| Control | Required policy gate |
| --- | --- |
| Opt-in only | A live GCP release/publish path may record `live-cloud` only after explicit release-owner approval through `--allow-cloud-upload` or `CROSSGL_ALLOW_LIVE_CLOUD_RELEASE_UPLOAD=1`; the record must include `liveCloudUploadOptIn`, and normal CI, pre-commit, and readiness gates must not set opt-ins. |
| Dry-run by default | Dry-run is the default; `dryRunDefault`, `dryRunReceiptPaths`, and `preflightReportPath` evidence must show `local-only`, `dry-run`, and `mock` coverage for the exact artifact set, including GCS dry-run receipt, upload manifest, upload preflight report, and mock or fake `gcloud` receipt, before `live-cloud` can be reviewed; validation must create no live objects. |
| Project/budget allowlisted | `approvalEvidence.projectAllowlistEntry`, `bucketAllowlistEntry`, and `budgetGuardrail` must be explicit non-placeholder values from approved project, bucket, and budget allowlists; `crossgl-release-dry-run` must not be reused as a live release target. |
| Prefix scoped | `approvalEvidence.releaseObjectPrefix` must be a normalized release-scoped object prefix; bucket-root uploads, parent-directory traversal, shared scratch prefixes, mixed release-scoped object prefixes, and names outside the target-approved prefix are blockers. |
| Retention/lifecycle reviewed | `approvalEvidence.lifecyclePolicy`, rollback horizon, cleanup owner, and retention/lifecycle review must be recorded before live upload approval. |
| Receipts/audit preserved | `approvalEvidence.auditReceiptPaths`, upload batch report, upload receipt, dry-run receipts, preflight report, rollback plan, and provider object metadata including generation, metageneration, CRC32C, MD5, byte size, and SHA-256 must be preserved with the release record. |

Before a live remote publish is approved, the release record must include these
cost-control requirements:

- Machine-readable live approval evidence: any provenance manifest or guardrail
  record that records `live-cloud` mode must include `approvalEvidence` with
  non-placeholder `approvalRecord`, `projectAllowlistEntry`,
  `bucketAllowlistEntry`, `budgetGuardrail`, `releaseObjectPrefix`,
  `lifecyclePolicy`, and `auditReceiptPaths` fields. The object is validated by
  `tools/check_release_provenance_manifest.py` and
  `tools/check_package_release_publish_flow.py` before live cloud mode can be
  treated as approved evidence.
- Dry-run default evidence: `dryRunDefault` must be true, and successful
  `dryRunReceiptPaths`, upload manifest, `preflightReportPath`, and mock or
  fake-upload receipt evidence for the exact artifact set must be attached
  before any live operation is considered.
- Budget and project allowlist: the release owner must approve an allowlisted
  GCP project, bucket, and budget guardrail for the release. Actual budget
  numbers are product decisions; planning records may use placeholders such as
  `<approved-gcp-project-id>`, `<approved-gcp-bucket>`, and
  `<approved-budget-limit>` until the release owner records the approved values,
  but live approval evidence must replace them with explicit non-placeholder
  values.
- No implicit credential use: live upload attempts must use the explicit
  `credentialsEnv` named by every upload-manifest request, fail closed when the
  variable is absent or unset, and must not rely on ambient `gcloud` accounts,
  application-default credentials, metadata service credentials, or credentials
  discovered from a developer workstation. GCS target descriptors and upload
  manifests must carry a non-empty `credentialsEnv` value even during dry-run
  planning so the release record proves which credential gate a future live
  attempt would require.
- Object prefix scoping: every live object must remain under the
  release-owner-approved bucket and release-scoped object prefix for that
  release. Policy records must keep `<approved-release-object-prefix>` as a
  decision placeholder until an owner approves the final namespace. Bucket-root uploads
  are release blockers, as are parent-directory traversal, shared scratch
  prefixes, and prefixes outside the approved release namespace. GCS target
  descriptors must include a non-empty normalized prefix. Standalone upload
  manifest validation must reject bucket-root object names and
  mixed release-scoped object prefixes within a single manifest, and the release
  record must compare each upload object name with the target-approved prefix
  before a dry-run receipt can be treated as live-readiness evidence.
- Lifecycle and retention expectation: the release owner must document the
  bucket or prefix lifecycle/retention policy, rollback horizon, and cleanup owner
  before approving live upload. Policy records must keep placeholders such as
  `<approved-lifecycle-policy-id>` and `<approved-rollback-horizon>` until the
  release owner records the approved values. This policy intentionally does not
  choose retention durations or budget amounts.
- Audit receipt requirements: Preserved upload receipts are mandatory. Every
  live attempt must write the upload batch report and upload receipt, preserve
  provider object metadata such as
  generation, metageneration, CRC32C, MD5, byte size, and SHA-256 when available,
  and store those receipts with the release bundle, promotion manifest, dry-run
  receipts, preflight report, and rollback plan.

Operators must review projected object count, byte size, destination bucket,
approved object prefix, project allowlist entry, budget approval, lifecycle and
retention plan, audit receipt paths, and rollback plan before enabling a live
upload.

## Validation Gate

The policy is checked by `tools/check_release_artifact_policy.py`. The v0 gate
`tools/check_v0_release_gate.py` must continue to require this policy file, the
CTest registration for `cglc_release_artifact_policy`, and the CTest
registration for `cglc_release_provenance_manifest_self_test`.
Focused cloud cost validation also uses the existing CTest registration for
`cglc_release_cloud_guardrails`.

The report-only release-candidate report summary surface is
`tools/check_v0_release_candidate_report.py`, documented in
`docs/V0_RELEASE_CANDIDATE_REPORT.md`. Its JSON kind is
`crossgl-v0-release-candidate-report-v1`; it summarizes local gate status,
artifact policy evidence, provenance/checksum requirements, source-free runtime
status, dry-run artifact evidence, budget/cloud guardrail references, the
report-only `releaseArtifactInventorySeal`, operator sign-off readiness,
held/rejected/approved decision evidence, and remaining operator sign-off fields
without publishing anything. The seal records local generated report artifacts,
their schema/kind/version metadata, and deterministic `sizeBytes`/`sha256`
values where the report bytes can be hashed without circular self-reference.
When an existing report is checked, deterministic seal artifacts are re-hashed
from local bytes only when their paths resolve under the repository root or the
checked report directory; stale or missing deterministic artifact facts fail the
check. The JSON report artifact remains an explicit circular checksum exception
with no embedded final size or SHA-256. It repeats the
no-network/no-GitHub/no-GCP/no-credential/no-publish offline boundary and does
not create live objects. When the report is generated with a local
`release-report-artifact-inventory-v1` input, that input must pass the release
inventory schema and semantic exactness checks before its summary can be treated
as passing evidence, including record counts, `totalArtifactRecordBytes`,
`destinationPath` completeness and plan/stage agreement, per-record
`sizeBytes`/`sha256` consistency, and native descriptor inventory evidence.
Valid reports must keep
`reportOnly: true`, `mode: "report-only"`, and
`releaseStatus: "not-shipped"`, and must record that GitHub calls, GCP calls,
network calls, credential reads, and publishing were `not-performed`. Even an
`approved` operator decision remains report-only evidence and must not automate
promotion, cloud upload, or artifact publication. A report whose
`operatorDecision.promotionDecision` is `missing-signoff` must keep
`operatorIdentity`, `decisionTime`, and `rationale` empty so a dry run cannot
look partially operator-approved.

### Final operator sign-off checklist

Before v0 artifacts are treated as release-ready, the operator sign-off record
must cite each row below. This checklist is an offline policy hook: it documents
the exact evidence bundle a release owner must review, and it does not invoke
cloud providers, GitHub APIs, upload tools, credentials, or scheduled work.

| Control | Required sign-off evidence |
| --- | --- |
| Exact artifact set | Preserve `package-release-bundle.json`, `package-release-publish-plan.json`, `package-release-publish-stage.json`, and `release-report-artifact-inventory-v1` evidence for the same artifact set; compare `artifactCount`, `totalArtifactBytes`, `packageArtifactRequirements`, and every `destinationPath` before sign-off. Preserve `releaseArtifactInventorySeal` from `crossgl-v0-release-candidate-report-v1`, including local generated report artifact paths, artifact schema/kind/version metadata, deterministic `sizeBytes`/`sha256` values where available, and the repeated offline boundary showing no network, GitHub, GCP, credential, or publishing actions. |
| Dry-run evidence | Record `dryRunDefault`, `package-release-publish-guardrails.json`, `dryRunReceiptPaths`, upload manifest, `preflightReportPath`, `mock`, and fake `gcloud` evidence proving the reviewed artifact set created no live cloud objects. |
| Provenance and checksums | Attach the `release-provenance-manifest-v1` record with `sourceCommit`, `toolchainSummary`, `artifacts[].sha256`, `sizeBytes`, `packageVerification`, and the `cglc package verify --json` output used to accept each package. |
| Promotion and rollback receipts | Preserve `promotionManifestPath`, `releaseBundleVerificationPath`, `rollbackPlanPath`, `previousPromotionManifestPath`, `previousVerifiedBundlePath`, `uploadReceiptPaths`, `failedAttemptReceiptPaths`, provider object metadata, generation, and metageneration evidence. |
| Live-cloud opt-in state | State whether `live-cloud` is rejected or approved; approval requires `--allow-cloud-upload` or `CROSSGL_ALLOW_LIVE_CLOUD_RELEASE_UPLOAD=1`, `liveCloudUploadOptIn`, `approvalEvidence`, `projectAllowlistEntry`, `bucketAllowlistEntry`, `budgetGuardrail`, `releaseObjectPrefix`, and `auditReceiptPaths`. |
| Operator decision | Record `policyAnchor` as `crossgl-v0-release-artifact-policy`, `operatorIdentity`, `decisionTime`, `promotionDecision`, and whether the artifact set was approved, rejected, or held. When sign-off is still missing, leave `operatorIdentity`, `decisionTime`, and `rationale` empty. |

### Release publish RC handoff evidence

The package release publish flow writes
`package-release-publish-rc-handoff-evidence.json` with kind
`crossgl-release-publish-rc-handoff-evidence-v1`. This is a local path index for
release-candidate handoff only. It is not a schema for live publishing, does not
approve a release, and must continue to record no live cloud objects.

| Control | Required RC handoff evidence |
| --- | --- |
| Local-only publish-flow handoff | Record `package-release-publish-rc-handoff-evidence.json`, kind `crossgl-release-publish-rc-handoff-evidence-v1`, `reportOnly`, `mode` `local-only`, `releaseStatus` `not-shipped`, and `liveObjectsCreated` `false`. |
| Provenance and inventory paths | Record `rcHandoffEvidence` and `provenanceChecksumEvidence` paths for `provenanceManifestPath` and `artifactInventoryPath`, covering `release-provenance-manifest-v1` and `release-report-artifact-inventory-v1`. |
| Dry-run publish receipt paths | Record `dryRunArtifactEvidence`, `guardrailRecordPath`, `dryRunReceiptPaths`, `uploadManifestPath`, `preflightReportPath`, `mockReceiptPaths`, and `fakeGcloudReceiptPaths` for `package-release-publish-guardrails.json`, `package-release-publish-gcs-dry-run.json`, `package-release-publish-upload-manifest.json`, `package-release-publish-upload-preflight.json`, `package-release-publish-upload-receipt.json`, and `package-release-publish-upload-receipt-gcs.json`. |
| Offline boundary | Record `networkCalls`, `gcpApiCalls`, `providerCliCalls` as `fake-local-shim-only`, `liveCloudUploadOptIn` `false`, `liveCloudMode` `rejected`, and `cloudObjectsCreated` `false`; evidence must be local paths only and must prove no live cloud objects were created. |

Recommended focused validation:

```sh
jobs="$(getconf _NPROCESSORS_ONLN 2>/dev/null || sysctl -n hw.ncpu 2>/dev/null || echo 2)"
pre-commit run --files \
  docs/RELEASE_PROVENANCE_MANIFEST_SCHEMA.md \
  docs/RELEASE_ARTIFACT_POLICY.md \
  tools/check_release_artifact_policy.py \
  tools/check_release_cloud_guardrails.py \
  tools/check_release_provenance_manifest.py
python3 tools/check_release_cloud_guardrails.py --root .
python3 tools/check_release_provenance_manifest.py --root .
python3 tools/check_release_provenance_manifest.py --self-test
python3 tools/check_package_reproducibility.py --self-test
python3 tools/check_release_artifact_policy.py --root .
python3 tools/check_package_release_publish_flow.py --root . \
  --cglc build/cglc \
  --work-dir build/package-release-publish-flow
python3 tools/check_v0_release_candidate_report.py --root . \
  --output build/reports/v0-release-candidate-report.json
python3 tools/check_v0_release_candidate_report.py --self-test
python3 tools/check_v0_release_gate.py --root . --build-dir build
ctest --test-dir build \
  -R 'cglc_(release_artifact_policy|release_cloud_guardrails|release_provenance_manifest_self_test|v0_release_gate)' \
  --output-on-failure \
  --parallel "${jobs}"
```

Pre-push validation must include the policy checker, provenance checker
self-test, and the matching `pre-commit run --files` invocation for touched
release policy files. Pre-release validation must also include the v0 release
gate and focused CTest registration above from a configured build directory.
These commands are report-only for cloud readiness; they must not read GCP
credentials, bind `GOOGLE_APPLICATION_CREDENTIALS`, bind live upload opt-in
environment variables, invoke `gcloud`, invoke `gsutil`, or call cloud APIs. The
static cloud guardrail checker also rejects release-validation HTTP commands,
Python cloud/network client imports, and Google API endpoint strings. The
provenance self-test must continue to prove that a live-cloud mode with only an
opt-in is rejected until `approvalEvidence` is present and non-placeholder, that
`cloudUpload.mode` is present in `cloudUpload.modes`, and that the recorded
dry-run/mock/local-only evidence has matching mode-specific guardrail flags. It
must also prove that report-only promotion/rollback evidence is preserved as a
checksummed provenance artifact and carries allowlist, budget, release prefix,
dry-run receipt, preflight, failed-attempt receipt, rollback plan, and provider
metadata fields.
