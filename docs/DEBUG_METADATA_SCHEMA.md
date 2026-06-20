# CrossGL Debug Metadata Schema

`cglc dump-ir --stage debug` emits the full debug metadata document to stdout.
Every `cglc build --debug-ir` package writes the same document to
`ir/debug-metadata.json`. The document records target selection decisions,
target capability summaries, HIR source-location provenance, and manual
texture-compare kernel analysis.

## Compatibility Policy

- `schemaVersion` is required and is currently `11`.
- Consumers should branch on `schemaVersion` before reading nested fields.
- Unknown future versions should be treated as incompatible unless the consumer
  explicitly opts into best-effort feature detection.
- Adding optional debug metadata fields is compatible within schema version 11.
- Removing required fields, changing field types, renaming fields, or changing
  required target/source-location/manual-kernel semantics requires a
  schema-version bump.
- The compiler emits only the current schema.
- The current machine-readable schema is
  [`docs/schemas/debug-metadata-v11.schema.json`](schemas/debug-metadata-v11.schema.json).
- Schema `12` is a planned/future companion to HIR source-map schema 8:
  [`docs/schemas/debug-metadata-v12.schema.json`](schemas/debug-metadata-v12.schema.json).
  It is not emitted by the compiler yet.

## Version 11

Top-level fields:

- `schemaVersion`: integer schema version, currently `11`.
- `targetDecision`: requested/selected target, package viability, selected
  target diagnostics, fallback target ranking, and target buckets.
- `targetCapabilities`: host default target and per-target package/capability
  summaries.
- `hirSourceLocations`: compact HIR expression/type/statement provenance with
  source spans.
- `manualTextureCompareKernelSummary`: manual shadow compare bucket counts.
- `manualTextureCompareKernelBuckets`: per-bucket manual kernel indexes.
- `manualTextureCompareKernels`: per-occurrence manual shadow compare records.

Target capability records intentionally keep capability ids as strings. The
schema pins the stable envelope fields, target names, package modes, package
decision reasons, and diagnostic severities while leaving capability taxonomies
free to grow as backend support expands.
Target decision and fallback records follow the same module-specific package
decision model as `explain-targets`. A predicate-rejected DirectX/OpenGL source
package records `unsupported` package mode, backend marker capabilities such as
`directx.backend.hlsl-lowering` or `opengl.backend.glsl-lowering`, and
predicate diagnostic capabilities on the selected-target diagnostic. A module
that passes the DirectX/OpenGL source preflight remains a buildable
`source-package` decision.
The target decision block is a deterministic projection of
`targetCapabilities.summaries`: summaries cover the complete canonical target
set in registry order (`metal`, `vulkan`, `directx`, `opengl`), selected-target
fields mirror the selected summary, `viableTargets` and `nonViableTargets`
preserve summary order, and fallback records contain every buildable
non-selected target sorted by `packageRankScore` with stable tie ordering.
Semantic schema validation rejects projection drift before a fixture or package
artifact is accepted. The package debug provenance checker also compares the
shared target summary fields with `cglc explain-targets`, keeping the debug
projection aligned with the separate legalization-fed target explanation
surface.
`legalizationCoreEvidenceIds` uses the same deterministic evidence IDs as
target explanation records. Each target capability summary carries the canonical
ID list for that target, `selectedTargetLegalizationCoreEvidenceIds` mirrors the
selected summary, selected-target diagnostics carry the selected target's IDs,
and fallback target records mirror the IDs for their ranked fallback target.
Target capability summaries also expose the normalized optional native-tool
projection from target legalization: `requiredToolCount`, `missingToolCount`,
`requiredToolIds`, `missingToolIds`, `optionalNativeToolMissing`,
`optionalNativeToolStatus`, and `toolRequirementEvidenceIds`. The selected
target and fallback records mirror those summary fields, and semantic validation
uses the same tool-requirement rules as target explanation records so debug
metadata cannot invent a separate tool availability policy.
For `cglc build --target auto`, `targetDecision.requestedTarget` remains
`auto`, while `targetDecision.selectedTarget` records the concrete target chosen
by auto selection. Auto selection uses
`selectionReason: "auto-host-default"` when the host default stays selected,
including the no-buildable-target case used for concrete unsupported-target
diagnostics, and `selectionReason: "auto-recommended-target"` when auto selects
a non-default recommended target. Explicit concrete requests use
`selectionReason: "explicit-target"`.

`hirSourceLocations` uses the same source-location record shapes as
[`docs/HIR_SOURCE_MAP_SCHEMA.md`](HIR_SOURCE_MAP_SCHEMA.md), but the full debug
metadata document does not include the source-map filter, pagination,
category-count, or combined-record envelopes. Packages that need editor/indexer
pagination should use `ir/hir-source-map.json` alongside this document.
Package debug metadata can include optional `originalLocation` fields when
`cglc build --debug-ir --source-remap <remap.json>` is used; generated
`location` records remain the required stable compiler-input anchors.
The same original-location projection is available for
`cglc dump-ir --stage debug --source-remap <remap.json>`.
Debug metadata semantic validation uses the same source-span consistency rules
for expression, type, and statement records. It also requires source-location
`index` values to be strictly increasing within each emitted record array, which
preserves compiler traversal order while allowing filtered or paged source maps
to skip original indexes. Emitted source locations are real source spans:
`file` must be non-empty, `length` must be positive,
`line`/`column`/`endLine`/`endColumn` are 1-based positive positions, and
same-line spans must advance `endColumn`. Debug metadata must emit at least one
source anchor, and at least one emitted anchor must carry both non-empty `stage`
and `entryPoint` so native binary debug provenance can be linked to the compiled
entrypoint. A non-empty `entryPoint` without `stage` is rejected.

Manual texture-compare kernel `weightSum` is optional and only appears when the
compiler can compute the sum statically. For each manual kernel,
`compatibilityAlias` is true exactly when `operation` differs from
`canonicalOperation`, which preserves the source spelling while keeping a stable
canonical operation name for grouping and audits.

`tools/validate_json_schema.py` performs debug-metadata semantic validation after
the structural schema pass. It treats `*Count` fields as consistency fields:
capability group counts must match their capability arrays, target decision
diagnostic/fallback counts must match emitted arrays, source-location
with-location counts must match emitted records, emitted source anchors must not
be empty, and manual texture-compare summary/bucket counts must partition
`manualTextureCompareKernels`.
It also checks target legalization projection consistency across
`targetDecision` and `targetCapabilities`, including selected summary fields,
viable/non-viable buckets, fallback rank order, fallback record payloads, and
optional native-tool requirement mirrors. For schema version 11 this includes
the target-explanation legalization evidence and tool-requirement semantics, so
debug metadata selected and fallback target diagnostics cannot drift from
`explain-targets` evidence IDs.

## Planned Version 12 Resource Lane

Debug metadata schema 12 prepares the embedded resource source-location stream
that matches HIR source-map schema 8. It adds
`hirSourceLocations.resourceCount`, `resourceWithLocationCount`, and
`resources[]` using the same strict resource record shape documented in
[HIR_SOURCE_MAP_SCHEMA.md](HIR_SOURCE_MAP_SCHEMA.md). This is a planned/future
lane only: `cglc dump-ir --stage debug` and package `ir/debug-metadata.json`
continue to emit schema 11 until DebugMetadata emission is updated.

The v12 semantic validator checks resource span validity, resource index
ordering, `resourceWithLocationCount == resources.length`, staged
`entryPoint`/`stage` context, and access-only context placement. It cannot
compare a debug metadata document with a separate HIR source-map document during
standalone schema validation; package integrity remains the layer that compares
the companion artifacts once both are emitted with the same schema lane.

Package integrity validation can run this schema with `--debug-metadata-schema`
or `--schema-root` against the manifest `artifacts.debugMetadata` package
artifact when present. When a package also includes `artifacts.hirSourceMap`,
the integrity validator requires that companion source map to be unfiltered,
unpaged, have combined records disabled, and carry the same
`hirSourceLocations` payload as the debug metadata artifact.
For `--debug-ir` packages, `manifest.artifacts.targetExplanation` points at
`ir/target-explanation.json`, the same target-explanation v1 document emitted
by `cglc explain-targets <input.cgl>`. The package debug provenance checker
compares that sidecar with the CLI explanation and with the target summaries in
debug metadata so target-package decision evidence stays aligned across all
debug package surfaces.

Previous schema: [`debug-metadata-v10.schema.json`](schemas/debug-metadata-v10.schema.json).
