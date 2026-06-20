# Release Report Artifact Inventory JSON Schema

[`docs/schemas/release-report-artifact-inventory-v1.schema.json`](schemas/release-report-artifact-inventory-v1.schema.json)
defines the JSON contract for release report artifact inventory records exposed
by the `PackageReleaseReportArtifactInventory` API and emitted by:

```sh
cglc package release \
  --report-artifact-inventory \
  --report-bundle package-release-bundle.json \
  --report-publish-plan package-release-publish-plan.json \
  --report-publish-stage package-release-publish-stage.json \
  --json
```

The command reads existing release bundle, publish plan, and publish stage
report artifacts. It performs no upload, publish, staging, package mutation, or
cloud access.

The inventory can be built from any non-empty subset of a release bundle,
publish plan, and publish stage report. Missing inputs are represented with
`null` paths:

- `bundlePath`: release bundle path used for `release-bundle` records, or
  `null`.
- `publishPlanPath`: publish plan path used for `publish-plan` records, or
  `null`.
- `stageReportPath`: publish stage report path used for `publish-stage`
  records, or `null`.

A non-null input path is a provenance claim that the corresponding local report
was read into the inventory. Each non-null input must therefore contribute at
least one record of its source kind; otherwise the path must be `null` rather
than an empty placeholder.

Top-level count fields mirror the typed result:

- `artifactRecordCount`: length of `records`.
- `bundleArtifactRecordCount`: number of `release-bundle` records.
- `publishPlanArtifactRecordCount`: number of `publish-plan` records.
- `publishStageArtifactRecordCount`: number of `publish-stage` records.
- `stagedArtifactRecordCount`: number of records with non-null `stagedPath`.
- `totalArtifactRecordBytes`: sum of all non-null record `sizeBytes` values.

Each record carries:

- `sourceRecordKind`: `release-bundle`, `publish-plan`, or `publish-stage`.
- `packagePath`: normalized package path from the source report.
- `packageArtifactPath`: normalized package-relative artifact path.
- `stagedPath`: normalized staged filesystem path for `publish-stage` records,
  otherwise `null`.
- `destinationPath`: normalized publish destination path for `publish-plan` and
  `publish-stage` records, otherwise `null`.
- `sizeBytes`: non-negative byte size, or `null` when a release bundle record
  had no artifact byte evidence.
- `sha256`: lowercase SHA-256 digest, or `null` when the matching byte size is
  absent.

When any record for a package reports a native binary artifact path, the same
package inventory must include the package's manifest-declared
`nativeArtifactDescriptor` artifact path. Compiler-built packages currently use
`backend/<target>/<module>.native-artifact.json`; `metadata/native-artifact.json`
is a conventional fixture/example path, not the only valid descriptor path. Each
source kind that reports native package artifacts must carry matching descriptor
provenance, and every descriptor record must include non-null `sizeBytes` and
`sha256` evidence. When the descriptor path itself is in a compiler-built
`backend/<target>/...` location, semantic validation also checks that the
descriptor stem matches the corresponding native binary stem so a plan and stage
cannot agree on a drifted backend descriptor path. Missing descriptor records,
source-kind gaps, or stale descriptor byte/checksum evidence are semantic
failures.

Semantic validation enforces deterministic inventory behavior that plain JSON
Schema cannot express: at least one input path is present, every non-null input
path contributes records for its source kind, record identities are unique by
`(sourceRecordKind, normalized packagePath, packageArtifactPath)`, records are
sorted by the same key family used by the C++ API, source-kind counts and byte
totals agree with `records`, staged and destination paths match their source
kind, path fields are normalized, SHA-256 and byte-size evidence are present
together, repeated package artifact identities agree on byte size and SHA-256
evidence, publish plan and stage records agree on destination paths, native
descriptor evidence is complete when native package artifacts are present,
diagnostic counts match diagnostics, and `success` is true only when there are
no error diagnostics.
