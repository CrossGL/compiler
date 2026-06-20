# Package Verify JSON Schema

`cglc package verify <package.cglb> [--source <input.cgl>] --json` emits a
schema-versioned package integrity report. The current schema is
[`docs/schemas/package-verify-v1.schema.json`](schemas/package-verify-v1.schema.json).

## Compatibility Policy

- `schemaVersion` is required and is currently `1`.
- Consumers should branch on `schemaVersion` before reading nested fields.
- Unknown future versions should be treated as incompatible unless the consumer
  explicitly opts into a newer contract.
- The M1 v0 verify boundary freezes the v1 required top-level result shape,
  nullable summary shape, diagnostic count fields, and verifier diagnostic
  record shape.
- Verifier diagnostic codes remain open-ended but continue to use the
  `package.verify.` prefix.
- The compiler emits only the current schema.

Current compiler-emitted package manifests include
`packageArtifactRequirements`. During package verification, that recorded view is
authoritative for native-only versus source-package targets, required artifact
minimums, planned native binary policy, and manifest `nativeBinaryStatus`
placement. Present requirements are fail-closed metadata: malformed objects,
unknown or duplicate required path artifact keys, target mismatches, and
requirements that conflict with the manifest target contract reject the package
before artifact verification continues. A present JSON `null` value is malformed;
only field omission enters the legacy path.
When recorded requirements require manifest `nativeBinaryStatus` but set
`allowsPlannedNativeBinary: false`, a manifest status of `planned` rejects the
package even if the native binary path currently exists.

Manifests that omit `packageArtifactRequirements` are accepted only through the
legacy compatibility path. The verifier emits a
`package.verify.legacy-artifact-requirements-fallback` note that says the
manifest is using legacy compatibility defaults for package verification only.
Consumers must treat that visible JSON note as compatibility evidence for an old
manifest, not as a current native support claim. The generated target contract
gate in `tools/package_target_contracts.json` remains the source for those
legacy defaults and is checked by `tools/check_package_target_contracts.py`.
`docs/architecture/TARGET_LEGALIZATION_CONSUMER_AUDIT.md` and
`tools/check_target_legalization_consumer_audit.py` pin the allowed driver and
runtime generated-contract fallback token inventory, compatibility boundary, and
retirement guard; new verifier-facing fallback call sites require an updated
report-only audit row before they are accepted.

Top-level fields:

- `schemaVersion`: integer schema version, currently `1`.
- `packagePath`: verified package path as passed to `cglc`, normalized for
  stable separators.
- `success`: `true` when the package passed compiler-native integrity checks.
- `summary`: normalized package facts copied from `manifest.json` when package
  metadata could be loaded; otherwise `null`.
- `graphicsAbi`: present only when the manifest declares
  `artifacts.graphicsAbi`. It reports read-only sidecar health, the manifest
  path, existence, a `lightweight-structural` validation label, nullable schema
  version, nullable module/target/count summary, and local diagnostics/counts.
- `diagnosticCounts`: counts for note, warning, and error diagnostics.
- `diagnostics`: standard CrossGL diagnostic records for every verifier finding.

`diagnosticCounts` values match the severities present in `diagnostics`, and
`success` is `true` exactly when no error diagnostics were emitted. Successful
verification reports always include a non-null `summary`. `packagePath` uses
normalized `/` separators, and verifier diagnostic codes use the
`package.verify.` prefix. Diagnostic location spans use the standard
source-location fields and keep `endOffset` equal to `offset + length`.
Verifier diagnostics that include target-specific capability evidence keep
their `target` aligned with `summary.target`, and every `missingCapabilities`
entry uses that target namespace.
For successful source-package summaries, `nativeBinaryStatus` is required for
DirectX and OpenGL. Recorded native package requirements do not require
manifest `nativeBinaryStatus`. When `packageArtifactRequirements` is recorded,
the summary reports only the recorded manifest `nativeBinaryStatus`; if the
manifest omits that status, the summary value is `null`. Legacy manifests
without recorded requirements may still infer Metal `emitted` when intermediate
and native binary artifacts are present, while Vulkan summaries remain `null`.
Every non-null summary also includes a compact
`nativeArtifactDescriptor` object. It reports whether the manifest artifact is
present, whether the descriptor file exists, descriptor health, package-relative
descriptor path, `optimizationLevel`, and `optimizationEvidence`. Packages
without a descriptor keep this object stable with `artifactPresent: false`,
`descriptorExists: false`, `health: "not-present"`, and nullable descriptor
fields set to `null`. When descriptor optimization evidence is present and
object-shaped, `optimizationEvidence` is the canonical descriptor evidence
object; otherwise it is `null`.
Successful native-ready verification requires this descriptor evidence. Native
Metal and Vulkan package summaries, recorded native DirectX/OpenGL summaries,
plus DirectX and OpenGL summaries whose effective `nativeBinaryStatus` is
`emitted` or `validated`, must report
`nativeArtifactDescriptor.artifactPresent: true`, `descriptorExists: true`, and
`health: "ok"`. A missing descriptor fails verification with
`package.verify.native-artifact-descriptor-required` so source-free/native
packages cannot appear verified without descriptor digest and toolchain
provenance evidence.
When package artifact requirements, manifest target-legalization tool
requirements, or target-legalization debug sidecars are present, the summary
also includes `targetLegalizationEvidence`. That object reports `packageMode`,
`packageModeSource`, a `manifestToolRequirements` record copied from manifest
`targetLegalizationToolRequirements`, debug-metadata and target-explanation
sidecar records, each sidecar's nullable
`requiredToolCount`, `missingToolCount`, `requiredToolIds`,
`missingToolIds`, `optionalNativeToolMissing`,
`optionalNativeToolStatus`, `toolRequirementEvidenceIds`,
`legalizationCoreEvidenceIds`, each sidecar's nullable
`packageArtifactRequirementEvidenceIds`, the aggregate nullable
`packageArtifactRequirementEvidenceIds`, `missingEvidence`, and nullable checks
for target/package-mode agreement, manifest tool evidence-ID presence,
sidecar-to-manifest tool agreement, and package artifact evidence-ID presence.
`packageModeSource` is limited to recorded manifest requirements and
target-legalization sidecars; legacy compatibility labels such as
`legacy-v0-target-contract` are invalid here and remain diagnostic/report
evidence only.
Evidence ID arrays and `missingEvidence` entries use non-empty strings; empty
strings are invalid contract evidence.
When recorded manifest requirements are present, sidecar requirement evidence
IDs must agree with the aggregate package requirement evidence IDs. Verification
does not synthesize those IDs from generated target contracts.
Readable sidecar drift is fail-closed: mismatched debug metadata and
target-explanation requirement evidence IDs are reported with
`package.verify.target-legalization-*-requirement-evidence-mismatch`
diagnostics.
Readable sidecar tool requirement drift is also reported in
`targetLegalizationEvidence.health`: readable sidecars must agree with recorded
manifest tool requirements when the manifest carries them, and readable
debug-metadata/target-explanation sidecars must agree with each other when both
provide tool counts, tool IDs, optional native-tool status, or tool requirement
evidence IDs. Missing tool requirement fields from older sidecars remain
nullable report evidence and do not make optional native tool availability a
package-mode upgrade.
Failure reports preserve declared descriptor evidence in the same summary
object. If `manifest.artifacts.nativeArtifactDescriptor` is present but the
descriptor file is missing, `artifactPresent` remains `true`,
`descriptorExists` is `false`, `health` is `"incomplete"`, `path` keeps the
manifest-declared package-relative path, and optimizer fields remain `null`.
When `manifest.artifacts.graphicsAbi` is present, verify emits a top-level
`graphicsAbi` object beside `summary`. This is a reporting slice over package
metadata, not a full semantic ABI verification gate: the C++ package verifier
does not invoke `tools/verify_graphics_abi.py`. It performs only package-local
structural checks against the top-level `graphics-abi-v1` shape, confirms
`schemaVersion`, `module`, `target`, and required array members, and publishes
the count summary only when those checks and package module/target agreement
succeed. Missing or malformed sidecars report `health` other than `ok` and
local `package.graphicsAbi.*` diagnostics in that object; ordinary manifest
artifact path/existence failures continue to use existing package verify
diagnostics.
Verifier JSON does not echo embedded reflection feature records; successful
verification leaves the package files unchanged and reports the target/status
summary needed by release gates. Consumers that need nonuniform descriptor-index
feature details should read `reflection.targetFeatures` through
`cglc package inspect --json`, where DirectX intrinsics, OpenGL extensions,
Vulkan SPIR-V extensions/capabilities, and Metal target policy records remain
available.
The package verify fixture suite also keeps read-only evidence for DirectX and
OpenGL source-package descriptor-array coordinates: storage-image array
fixtures assert that `reflection.resources` and `reflection.targetResourceBindings`
share the source stage/set/binding, that DirectX register and OpenGL
program-resource target coordinates match the source-package binding, and that
the verify summary reports matching debug metadata target/package-mode evidence.
This fixture evidence does not add reflection records to verify JSON.

The verifier always checks that `manifest.json` contains a `sourceHash` record
with `algorithm: "sha256"` and a 64-character lowercase hexadecimal value. When
`--source` is provided, it also reads the source file and compares its SHA-256
digest with `manifest.json` `sourceHash.value`. Hash record errors, hash
mismatches, and source read failures are reported as standard package verify
diagnostics with locations pointing at the relevant manifest field or source
file. DirectX and OpenGL packages that report `nativeBinaryStatus: "planned"`
must be verified with `--source`; otherwise the verifier cannot distinguish a
source-backed planned native package from source-free metadata with only an
unchecked digest.

When a debug package declares `manifest.artifacts.sourceRemap`, verification
checks that the provenance sidecar exists, identifies the package target,
matches the `source-remap-provenance-v1` contract, and records a non-empty
source-remap path plus SHA-256 identity. Invalid remap provenance is reported as
`package.verify.source-remap-provenance-invalid`. The source-remap sidecar hash
does not participate in `manifest.sourceHash`.

Package metadata documents reject duplicate JSON object keys before verification
continues. Duplicate-key diagnostics point at the repeated key and include a
stable JSON path such as `$.artifacts.backendSource`.

Manifest artifact paths are checked as package-relative file paths. Invalid
paths are reported with separate diagnostics for empty values, backslash
separators, absolute paths, and parent-directory traversal before any artifact
existence checks run. Non-empty `reflection.json` `nativeBinary` values use the
same path classification before the verifier compares them with
`manifest.json` `artifacts.nativeBinary`. Artifact diagnostics point at the
manifest artifact value, while reflection native-binary diagnostics point at the
`reflection.json` `nativeBinary` value when that metadata is available.
Manifest schema semantic fixtures also reject duplicate artifact path values so
artifact keys remain independently auditable evidence.

Valid artifact paths are then checked against the package filesystem. Missing
artifacts and paths that exist but are not regular files are reported with
separate diagnostics. Root package metadata documents such as `manifest.json`,
`reflection.json`, and `diagnostics.json` must also be regular JSON object
files before the verifier loads package metadata.
Target package contracts also validate manifest `nativeBinaryStatus` placement.
DirectX and OpenGL supported source-package targets require it, while
native-only Metal and Vulkan packages reject it because they require an actual
native binary artifact instead of source-package status metadata. The standalone
package integrity validator enforces the same `planned`/`emitted`/`validated`
status domain even when JSON schema validation is not enabled, so an unknown
source-package status cannot substitute for valid native/source artifact
evidence.
Unsupported predicate-gated Metal/Vulkan native decisions and DirectX/OpenGL
source-package decisions do not produce a successful package verification
summary. When verification succeeds for DirectX or OpenGL source packages, the
package has manifest-backed `summary.nativeBinaryStatus`; recorded native
DirectX/OpenGL requirements may verify with `summary.nativeBinaryStatus` set to
`null`. When verification succeeds for recorded Metal native package
requirements without manifest `nativeBinaryStatus`, the summary also keeps
`summary.nativeBinaryStatus` set to `null`; legacy Metal packages without
recorded requirements may report inferred effective artifact evidence as
`"emitted"`. Successful Vulkan native package summaries keep
`summary.nativeBinaryStatus` set to `null`.

When debug IR artifacts are present, the verifier checks that `debugMetadata`
and `hirSourceMap` can be consumed as a coherent package pair. The package
source map must be unfiltered, unpaged, have combined records disabled, carry
category counts and `records.totalCount` that match complete
`hirSourceLocations`, and use the same `hirSourceLocations` payload as
`debugMetadata`. Debug artifact diagnostics name the relevant package-relative
manifest artifact paths, so missing-pair, missing-file, and stale-pair failures
remain distinguishable without changing the v1 JSON shape.
`targetExplanation` is a separate `--debug-ir` manifest artifact using the
target-explanation v1 schema. Package verification treats it as a normal
manifest artifact for path and existence checks; the focused package debug
provenance checker validates its schema and compares it with
`cglc explain-targets`.
If readable `debugMetadata` or `targetExplanation` sidecars contradict the
package target or recorded `packageArtifactRequirements.packageMode`, the
verifier fails closed with `package.verify.target-legalization-*`
diagnostics. When recorded `packageArtifactRequirements` are present, their
`evidenceIds` must also be present and match the recorded package artifact
requirements; missing or stale manifest evidence fails closed before readable
sidecar drift checks.
The same sidecar evidence also preserves the selected target's tool requirement
projection when the package was built with current debug metadata and
target-explanation artifacts. Verification compares readable sidecars for drift
but does not treat optional native tool availability as a native support claim.

When `manifest.artifacts.nativeArtifactDescriptor` is present, the verifier
loads the descriptor from that package-relative manifest path as
`native-artifact-v0` evidence and checks it against the package it describes.
The verifier does not require a fixed descriptor filename such as
`metadata/native-artifact.json`. Target, source path/hash, native artifact
path/hash/size, validation status, and source-package `nativeBinaryStatus`
drift are reported with `package.verify.native-artifact-*` diagnostics. The
summary mirrors descriptor presence, health, path, optimization level, and
optimization evidence without expanding the full descriptor contract into
verify JSON. Tool records inside the descriptor may include resolver/probe
evidence such as `resolvedExecutable`, `executableSource`,
`versionProbeStatus`, and `versionDetail`; verify validates those fields as
descriptor contract evidence. `resolvedExecutable` is host toolchain evidence
and may be absolute; verify does not treat it as a package-relative artifact
path and does not treat optional native tool presence as a package-mode upgrade.
Stale descriptor hashes are fail-closed evidence: a
descriptor whose `sourceHash` or `artifactHash` no longer matches the package
file is a verifier failure, even when the referenced file is present.

The command writes this JSON document on both success and verifier failure. The
process exit code remains authoritative for shell workflows: `0` means verified,
`1` means package integrity failed, and `2` is reserved for command-line errors.
Use `cglc package inspect <package.cglb> --json` when consumers need embedded
manifest, reflection, diagnostics, root-file records, and artifact records.
