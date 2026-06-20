# Package Inspect JSON Schema

`cglc package inspect <package.cglb> --json` emits a schema-versioned summary
of an emitted CrossGL package. The current schema is
[`docs/schemas/package-inspect-v1.schema.json`](schemas/package-inspect-v1.schema.json).

Top-level fields:

- `schemaVersion`: integer schema version, currently `1`.
- `packagePath`: inspected package path as passed to `cglc`, normalized for
  stable separators.
- `packageFormat`: currently `directory`.
- `success`: present only on failure documents in schema version 1, where it is
  always `false`. Successful inspection preserves the original v1 shape and
  omits this field.
- `summary`: normalized package facts derived from `manifest.json` and package
  artifact evidence, including `module`, `target`, optional
  `nativeBinaryStatus`, artifact count, and whether both debug IR metadata
  artifacts are present.
- `debugArtifacts`: read-only health summary for `artifacts.debugMetadata` and
  `artifacts.hirSourceMap`, including declaration/existence flags and nullable
  boolean checks for source-location parity, unfiltered/unpaged source maps,
  disabled combined records, category-count consistency, and record-total
  consistency. When present, `debugArtifacts.sourceRemap` reports the
  `artifacts.sourceRemap` provenance sidecar path, hash identity, mapping
  summary, and target/contract checks. `health` is `ok`, `drift`, or
  `incomplete`.
- `vulkanNativeProfile`: read-only health summary for the Vulkan
  `artifacts.nativeProfile` sidecar. Non-Vulkan packages report
  `health: not-applicable`; Vulkan packages report declaration/existence, the
  SPIR-V profile fields, and nullable checks that the sidecar target/module and
  `.spv`/`.spvasm` paths match package metadata. When the native profile
  records optional `spirv-dis` evidence, inspection also reports
  `disassemblyStatus`, `disassemblyPath`, and `disassemblyExists`.
  `checks.emittedDisassemblyExists` is `true` only when the profile says the
  sidecar was emitted and the package-relative sidecar exists; it is `null` for
  `failed` and `skipped-tool-missing`, so failed or unavailable disassembly
  remains non-fatal while the native binary/profile health can still be `ok`.
- `nativeArtifactDescriptor`: read-only health summary for optional
  `artifacts.nativeArtifactDescriptor` files using the
  `native-artifact-v0` contract. When present, inspection reports descriptor
  identity, target, binary kind, source/artifact paths, hashes, size,
  optimization level, optional optimization evidence, validation status, native
  binary status, and nullable consistency checks against the package manifest
  and package files.
  `health` is `ok`, `drift`, `invalid`, `incomplete`, or `not-present`.
- `graphicsAbi`: present only when the manifest declares
  `artifacts.graphicsAbi`. It reports the manifest path, whether the sidecar
  exists as a regular file, health, a `lightweight-structural` validation label,
  nullable schema version, nullable module/target/count summary, and local
  diagnostics/counts for unreadable, malformed, or package-mismatched sidecars.
- `artifactRequirementsProjection`: emitted by current successful inspection
  documents. It explicitly labels the report-only basis for artifact requirement
  facts as `recorded-packageArtifactRequirements`,
  `legacy-missing-packageArtifactRequirements`, or
  `recorded-nativeArtifactDescriptor-health`. It also records
  `reportOnly: true`, whether manifest `packageArtifactRequirements` were
  present, the requirement source when present, whether manifest
  `nativeBinaryStatus` satisfies the recorded requirements policy, whether
  inspect is observing legacy manifest absence, and the recorded native artifact
  descriptor
  artifact/health/path facts when available. This object is a metadata
  projection only; it does not make target support decisions.
- `targetLegalizationEvidence`: present when package artifact requirements,
  manifest target-legalization tool requirements, or target-legalization debug
  sidecars are present. It reports `packageMode`/`packageModeSource`, a
  `manifestToolRequirements` record copied from manifest
  `targetLegalizationToolRequirements`, debug-metadata and target-explanation
  sidecar package-mode records, each sidecar's nullable
  `requiredToolCount`, `missingToolCount`, `requiredToolIds`,
  `missingToolIds`, `optionalNativeToolMissing`,
  `optionalNativeToolStatus`, `toolRequirementEvidenceIds`,
  `legalizationCoreEvidenceIds`, each sidecar's nullable
  `packageArtifactRequirementEvidenceIds`, the aggregate nullable
  `packageArtifactRequirementEvidenceIds`, a `missingEvidence` list, and checks
  for target/package-mode agreement with the package, manifest tool evidence-ID
  presence, sidecar-to-manifest tool agreement, and package artifact
  evidence-ID presence. When recorded manifest requirements are present,
  sidecar requirement evidence IDs must agree with the aggregate package
  requirement evidence IDs; inspect does not synthesize those IDs from target
  defaults. When manifest tool requirements are present, readable sidecars must
  agree with the manifest tool counts, tool IDs, optional native-tool status,
  and tool requirement evidence IDs. Missing tool requirement fields from older
  sidecars remain nullable report evidence and do not upgrade package support.
  When the manifest does not record `packageArtifactRequirements`, the aggregate
  `packageArtifactRequirementEvidenceIds` field remains `null` even if legacy or
  debug sidecars contain similarly named IDs; inspect treats those packages as
  legacy/report-only and does not upgrade generated target-contract facts into
  recorded package requirement evidence.
- `packageArtifactRequirements`: present only when the manifest records
  `packageArtifactRequirements`. It exposes the recorded target, package mode,
  required path artifact names, recorded `evidenceIds` when the manifest
  includes them, native-binary status policy booleans, and source locations for
  tooling. Legacy manifests without the manifest field keep the prior inspect
  shape and omit this top-level field; manifests with a requirements object but
  no `evidenceIds` keep the field omitted rather than synthesizing target
  defaults.
  When present, the record is loaded through package metadata validation before
  inspection succeeds. Malformed JSON records fail closed with
  `package.inspect.invalid-manifest`; only omission is treated as legacy
  compatibility. A present JSON `null` value is malformed and must not be
  interpreted as a legacy manifest. Records that differ from target-default
  expectations remain recorded package facts in inspect and are surfaced as
  report-only drift when recorded sidecar evidence disagrees.
- `publication`: read-only publication state for the inspected package path.
  `state` is `published` for the requested output path, `staged` for a package
  still in a compiler staging sidecar, or `previous` for a replacement backup
  sidecar. It also reports the requested output path and any sibling staging or
  previous sidecars left beside that requested path.
- `rootFiles`: status records for `manifest.json`, `reflection.json`, and
  `diagnostics.json`, including fixed package-root provenance.
- `artifacts`: status records for manifest artifact paths. `nativeBinaryStatus`
  is represented in `summary`, not as a file artifact. Each artifact record
  includes manifest provenance identifying the `manifest.artifacts` key that
  declared it.
- `manifest`, `reflection`, and `diagnostics`: embedded package metadata
  documents for consumers that need the full public package contracts.
  `reflection.targetFeatures` is preserved verbatim for target feature
  requirements such as DirectX `NonUniformResourceIndex`, OpenGL
  `GL_EXT_nonuniform_qualifier`, Vulkan `SPV_EXT_descriptor_indexing` and
  descriptor-indexing capabilities, and any Metal nonuniform target policy
  records emitted by the compiler. `diagnostics` is also embedded verbatim, so
  target-decision diagnostics remain visible to package consumers.
- `diagnosticCounts`: present only on failure documents. Counts inspect command
  diagnostics by severity.

When inspection cannot load package metadata, for example because the package
path is missing, is not a directory package, or contains invalid root metadata
JSON, `--json` still writes a schema-versioned document to stdout and exits
non-zero. Failure documents contain `success: false`, `packageFormat: null`,
`summary: null`, `diagnosticCounts`, and a `diagnostics` array using the
standard CrossGL diagnostic record shape. On success, `diagnostics` remains the
embedded package `diagnostics.json` object described above.

Each file or artifact status record contains the package-relative path,
`provenance`, whether the path exists as a regular file, and required
`sizeBytes` and `sha256` keys. For an existing regular file, `sizeBytes` is the
byte length and `sha256` is a lowercase SHA-256 digest of the file contents.
Schema semantics require both values to be non-null whenever `exists` is `true`.
For a missing artifact, non-regular file, or path outside the package path
contract, both facts are reported as `null`.
Artifact records also expose `packageRelative`, so tools can flag package paths
that should be rejected by package integrity validation. Schema semantics derive
this flag from the artifact path identity: empty paths, backslash separators,
absolute paths, Windows drive paths, and parent-directory traversal are not
package-relative. Non-package-relative artifact records must report
`exists: false`.

Runtime consumers should build their load inventory from `rootFiles` and
`artifacts` rather than from target-specific path conventions. `rootFiles`
provides stable package-relative paths for `manifest.json`, `reflection.json`,
and `diagnostics.json`. `artifacts` provides manifest-provenanced paths for
backend source, native binary, debug metadata, HIR source maps, target
explanations, and target sidecars such as Vulkan native profiles. DirectX and
OpenGL source packages always expose the `nativeBinary` package-relative path
even when
`summary.nativeBinaryStatus` is `planned` and the file does not exist yet.
Optional native artifact descriptors remain ordinary manifest artifacts in this
inventory, while the parsed field-level contract is reported through
`nativeArtifactDescriptor`.
Optional graphics ABI sidecars remain ordinary manifest artifacts too. When
`manifest.artifacts.graphicsAbi` is present, inspection adds the concise
`graphicsAbi` health object. The package inspector does not invoke
`tools/verify_graphics_abi.py`; it performs a package-local structural read
consistent with the top-level `graphics-abi-v1` contract, verifies
`schemaVersion`, `module`, `target`, and required array members, and reports the
array counts only when that lightweight check and package module/target
agreement succeed. Full semantic ABI checks still belong to
`tools/verify_graphics_abi.py`.
Vulkan disassembly sidecar discovery is reported through
`vulkanNativeProfile.disassemblyPath` and `disassemblyExists`.
Schema semantic checks also require source-package
`manifest.artifacts.nativeBinaryStatus` metadata to be paired with a
`manifest.artifacts.nativeBinary` path; the status is not counted as an
artifact and cannot substitute for the native-binary artifact record.
For `nativeArtifactDescriptor`, the semantic checker recomputes every
`checks.*` value from the manifest-provenanced `artifacts` records and
`summary.nativeBinaryStatus`. A report cannot claim descriptor/source path,
source hash, native artifact path/hash/size, target, or validation-status parity
unless those flattened descriptor fields agree with the same inventory records
that package loaders consume.
When the descriptor artifact is absent or not readable, parsed descriptor
identity/content fields remain `null`; only inventory fields such as
`artifactPresent`, `descriptorExists`, `health`, `path`, and `checks` report the
inactive state. Reports emitted by current tools may include
`optimizationEvidence: null` in this state, while legacy reports may omit
`optimizationEvidence`; when the field is present as an object it uses the same
strict optimization-evidence shape as the native artifact descriptor contract:
`requestedLevel`, `effectiveLevel`, `policy`, `status`, and optional `tool`,
`toolFlag`, `debugInfo`, `profile`, `flags`, and `evidenceSource`.
For `packageArtifactRequirements`, the semantic checker requires the inspect
projection to match the embedded manifest record exactly. The
`requiredPathArtifacts` projection is an array of records with `name` and
source-location metadata rather than a copy of the manifest string array, so
tools can point users at the exact recorded requirement while preserving the
manifest as the source of truth. When the manifest records requirement
`evidenceIds`, the projection must expose the same IDs and an
`evidenceIdsLocation` span; stale or synthesized evidence IDs are schema drift.
Inspect only emits this projection after the manifest record passes package
metadata validation. Inspect schema semantics require the projection to match
the embedded manifest record and require recorded `requiredPathArtifacts` and
native-binary status policy to be consistent with declared manifest artifacts.
They do not recompute target artifact requirements from target defaults.
`artifactRequirementsProjection.nativeBinaryStatusMatchesRequirements` is
`true` when a recorded requirements object and manifest `nativeBinaryStatus`
agree, `false` when status is missing, unexpected, or `planned` while planned
native binaries are disallowed, and `null` for legacy manifests without recorded
requirements.

`debugArtifacts.checks` fields are `null` when the artifacts cannot be read as a
pair. This keeps inspection read-only and non-fatal for incomplete packages while
still surfacing debug/source-map drift to editor and packaging tools.
`debugArtifacts.sourceRemap.health` is `not-present` when the package does not
declare remap provenance, `ok` when the sidecar matches the package target and
contract, `drift` when readable provenance is inconsistent, and `incomplete`
when the manifest declares the artifact but the sidecar cannot be read.
`targetExplanation` is reported as an ordinary manifest artifact record when a
`--debug-ir` package declares it; consumers that need its field-level contract
should validate the artifact with `target-explanation-v1.schema.json`.
When `targetLegalizationEvidence` is present, inspect reads only the
manifest-provenanced `debugMetadata` and `targetExplanation` artifacts and the
recorded manifest `packageArtifactRequirements`. It does not recompute target
support, infer package artifact evidence IDs, or turn legacy fallback defaults
into support evidence.
The debug-metadata and target-explanation sidecars may also carry the selected
target's tool requirement projection. Inspect exposes those fields as nullable
sidecar evidence and compares readable sidecars for drift, but it does not turn
optional native tool availability into native package support.
For DirectX and OpenGL source-package resource cases, package inspect embeds
the reflection resource and target binding records as the coordinate evidence:
the source `set`/`binding` pair remains in `reflection.resources` and the target
ABI coordinate remains in `reflection.targetResourceBindings`. The debug
metadata sidecar contributes only the selected target, source-package mode, and
legalization evidence IDs that inspect reports through
`targetLegalizationEvidence`.

`artifactRequirementsProjection` follows the same read-only boundary. Its
`basis` is selected from recorded manifest requirements first; if those are
absent and a native artifact descriptor artifact is declared, inspect reports
the recorded descriptor health as the basis; otherwise it reports legacy
manifest absence. None of these states calls target legalization or upgrades a
legacy package into a support decision.

Native artifact descriptors remain embedded descriptor evidence. Their
`toolchainProvenance.tools[]` records may include resolved executable,
executable source, version probe status, and probe detail fields captured during
package build. `resolvedExecutable` is host toolchain evidence and may be an
absolute host path; it is not interpreted as a package-relative artifact path.
Inspect surfaces descriptor health and inventory records without promoting
those optional native-tool facts into native package support.

`publication.siblingSidecars` records use the same sidecar naming convention as
the build pipeline: `.<output>.staging-<token>-<attempt>` for generated packages
that have not been promoted, and `.<output>.previous-<token>-<attempt>` for
temporary backups made while replacing a published package directory.
Use `cglc package recover <sidecar.cglb> --promote` to verify and promote a
staging or previous sidecar into the requested output path, or
`cglc package recover <sidecar.cglb> --discard` to remove an unwanted sidecar.
Add `--json` for the schema-versioned report documented in
[`docs/PACKAGE_RECOVER_SCHEMA.md`](PACKAGE_RECOVER_SCHEMA.md).
Use `cglc package recover <package-or-sidecar.cglb> --list --json` when a
tool needs the same publication/sidecar discovery object without loading package
metadata.
Use `cglc package maintain <package-or-sidecar.cglb> --json` to preview or
apply conservative stale sidecar cleanup based on this same publication state.
Add `--keep-last <n>` when cleanup should retain the newest stale recovery
sidecar directories, or `--older-than <duration>` when recent stale sidecars
should be left untouched. Use `--policy <policy.json>` to load those retention
settings from the policy schema documented in
[`docs/PACKAGE_MAINTENANCE_POLICY_SCHEMA.md`](PACKAGE_MAINTENANCE_POLICY_SCHEMA.md).
The same report is also available through
`cglc package recover <package-or-sidecar.cglb> --discard-stale --json`.
Use `cglc package maintain --scan <dir> --json` for an aggregate maintenance
report across all package output groups in one directory; that report is
documented in
[`docs/PACKAGE_MAINTENANCE_REPORT_SCHEMA.md`](PACKAGE_MAINTENANCE_REPORT_SCHEMA.md).
Use `cglc package maintain --package-set <set.json> --json` when a tool already
has an explicit package list; the set input and report are documented in
[`docs/PACKAGE_MAINTENANCE_SET_SCHEMA.md`](PACKAGE_MAINTENANCE_SET_SCHEMA.md).

`summary.nativeBinaryStatus` is recorded manifest source-package metadata for
DirectX and OpenGL packages: supported source-package summaries require the
manifest `planned`, `emitted`, or `validated` status. Native-only recorded
packages must not write `manifest.artifacts.nativeBinaryStatus`, so package
inspect reports `null` for recorded Metal/Vulkan native packages unless the
manifest records a native-binary status explicitly.
Predicate-rejected Metal/Vulkan native decisions and DirectX/OpenGL
source-package decisions are visible through embedded diagnostics/debug
metadata rather than through a successful package summary. When a DirectX or
OpenGL package exists, it is a supported source package and
`summary.nativeBinaryStatus` carries its `planned`, `emitted`, or `validated`
status. Old manifests without recorded `packageArtifactRequirements` can still
use the bounded legacy compatibility status, but new recorded packages report
only the manifest facts.

Root file records use `provenance.kind: "packageRootFile"` and
`provenance.source: "packageRoot"` because their paths are fixed by package
layout. They include a `location` object spanning the loaded metadata document.
Artifact records use `provenance.kind: "manifestArtifact"`,
`provenance.source: "manifest.artifacts"`, and
`provenance.manifestKey` matching the artifact name. Their `location` object
spans the manifest string value that declared the artifact path. These locations
use the standard CrossGL source span shape: `file`, `line`, `column`, `offset`,
`length`, `endLine`, `endColumn`, and `endOffset`.

`package inspect` is read-only. Use `cglc package verify <package.cglb>
--json` for compiler-native structural integrity checks, or
`tools/validate_package_integrity.py` when a package must also be rejected on
source-hash mismatches or schema violations.

Like verification, inspection rejects duplicate JSON object keys in package
metadata before emitting a normalized report. This keeps ambiguous manifests,
reflection data, and package diagnostics out of downstream tooling.
