# HIR Source-Map Schema

`cglc dump-ir --stage hir-source-map` emits a compact JSON document for editor
and tooling consumers that need source provenance for HIR expressions, types,
and statements without the full debug metadata payload. Debug packages also
write the same document to `ir/hir-source-map.json` when `--debug-ir` is
enabled.

## Compatibility Policy

- `schemaVersion` is a required integer. The default compiler-emitted version
  is `7`.
- The default machine-readable schema is
  [`docs/schemas/hir-source-map-v7.schema.json`](schemas/hir-source-map-v7.schema.json).
- Schema `8` is an opt-in resource source-location lane described by
  [`docs/schemas/hir-source-map-v8.schema.json`](schemas/hir-source-map-v8.schema.json).
  The C++ `DebugMetadata` source-map builder can emit it when explicitly
  requested with `DebugMetadataHIRSourceMapOptions::schemaVersion == 8`.
- `cglc dump-ir --stage hir-source-map` emits schema 7 by default. Callers may
  request schema 8 with `--source-map-schema-version 8` or the compatibility
  alias `--hir-source-map-schema-version 8`.
- `--debug-ir` package artifacts intentionally continue to emit schema 7 until
  package writing is explicitly promoted to schema 8. Package source maps must
  therefore remain valid v7 documents unless a future package contract says
  otherwise.
- Package integrity options such as `--hir-source-map-schema` and
  `--schema-root` select validation schemas for already-emitted artifacts; they
  do not select compiler output schema versions.
- Treat unknown future versions as incompatible unless the consumer explicitly
  uses best-effort feature detection.
- A schema version is bumped whenever a required top-level object is added,
  removed, renamed, or its meaning changes.
- A schema version is bumped whenever a required record field is added,
  removed, renamed, or its meaning changes.
- Existing fields in a published schema are not repurposed within the same
  version.
- Arrays preserve deterministic compiler traversal order. Record `index`
  fields preserve the original pre-filter/pre-pagination record index.
- Filters are applied before pagination.
- Package artifacts are complete by default: they use the current schema with
  `filters.activeCount == 0`, `pagination.activeCount == 0`, and
  `records.enabled == false`.
- Package source-map artifacts are canonical companions to
  `artifacts.debugMetadata` and must carry the same `hirSourceLocations`
  payload.
- Generated-to-original source remapping layers optional `originalLocation`
  metadata around stable generated-source `location` records instead of
  changing package defaults or repurposing v7/v8 fields. For generated
  single-file workflows, `cglc dump-ir --logical-input <path>` can change the
  reported compiler-input path while preserving generated-source coordinates;
  `--source-remap <remap.json>` can additionally attach original-source spans
  using [SOURCE_REMAP_SCHEMA.md](SOURCE_REMAP_SCHEMA.md). Package
  `ir/hir-source-map.json` sidecars can also include these fields when
  `cglc build --debug-ir --source-remap` is used.
- Package integrity validation can run this schema with
  `--hir-source-map-schema` or `--schema-root` against the manifest
  `artifacts.hirSourceMap` package artifact when present.

## Version History

| Version | Change |
| --- | --- |
| 1 | Initial compact source-map document with `schemaVersion` and `hirSourceLocations`. |
| 2 | Added the required `filters` object. |
| 3 | Added source span fields to each `location`: `length`, `endLine`, `endColumn`, and `endOffset`. |
| 4 | Added the required `pagination` object for expression/type stream paging. |
| 5 | Added the required `records` object for optional combined expression/type cursor paging. |
| 6 | Added the required `categoryCounts` object for cheap post-filter source-map summaries. |
| 7 | Added first-class statement source locations, statement pagination, statement category totals, and `recordKind: "statement"` combined records. Previous schema: [`hir-source-map-v6.schema.json`](schemas/hir-source-map-v6.schema.json). |
| 8 | Opt-in lane for resource source-location records. Adds `resources[]`, resource pagination/filter/category counts, and `recordKind: "resource"` combined records. The default emitted CLI/package schema remains v7. |

## Schema 7 Shape

Top-level fields:

```json
{
  "schemaVersion": 7,
  "filters": {},
  "pagination": {},
  "categoryCounts": {},
  "records": {},
  "hirSourceLocations": {}
}
```

### Filters

`filters.activeCount` is always present. All other fields are present only when
that filter is active.

```json
{
  "activeCount": 0,
  "stage": "compute",
  "entryPoint": "main",
  "function": "main",
  "statementKind": "decl",
  "expressionKind": "texture_compare_lod_manual",
  "expressionValue": "textureCompareLodManualKernel",
  "ownerKind": "resource-type",
  "ownerName": "values"
}
```

Filter semantics:

- `stage`, `entryPoint`, and `function` apply to expression, type, and statement
  records.
- `statementKind` applies to expression and statement records.
- `expressionKind` and `expressionValue` apply only to expression records.
- `ownerKind` and `ownerName` apply only to type records.
- Common type `ownerKind` values include `resource-type`, `constant-type`,
  `function-return-type`, `statement-declared-type`, `expression-type`,
  `field-type`, `field-name`, `parameter-type`, and `parameter-name`. Name
  owner kinds reuse the corresponding type spelling and point `location` at
  the identifier token instead of the type token.

Total counts are post-filter. A record-kind-specific filter excludes other
record kinds from totals and emitted records; for example, `expressionKind`
requires type and statement totals to be zero, while `ownerKind` requires
expression and statement totals to be zero.

CLI flags:

```bash
cglc dump-ir input.cgl --stage hir-source-map \
  --source-map-expression-kind texture_compare_lod_manual \
  --source-map-operation textureCompareLodManualKernel
```

### Pagination

`pagination.activeCount` is always present. `expressionLimit`, `typeLimit`, and
`statementLimit` are present only when set by the request.

```json
{
  "activeCount": 0,
  "expressionOffset": 0,
  "typeOffset": 0,
  "statementOffset": 0,
  "expressionLimit": 1,
  "typeLimit": 1,
  "statementLimit": 1,
  "expressionTotalCount": 36,
  "expressionEmittedCount": 1,
  "expressionHasMore": true,
  "expressionNextOffset": 1,
  "typeTotalCount": 10,
  "typeEmittedCount": 1,
  "typeHasMore": true,
  "typeNextOffset": 1,
  "statementTotalCount": 3,
  "statementEmittedCount": 1,
  "statementHasMore": true,
  "statementNextOffset": 1
}
```

Pagination fields are stream-local because expressions, types, and statements
are separate arrays. Total counts are after filtering and before pagination.
Emitted counts match the emitted array lengths.

Shared CLI flags apply to both streams:

```bash
cglc dump-ir input.cgl --stage hir-source-map --source-map-limit 100
```

Per-stream flags override shared values:

```bash
cglc dump-ir input.cgl --stage hir-source-map \
  --source-map-expression-offset 100 \
  --source-map-expression-limit 50 \
  --source-map-type-offset 0 \
  --source-map-type-limit 25 \
  --source-map-statement-offset 0 \
  --source-map-statement-limit 25
```

### Category Counts

`categoryCounts` is always present. It summarizes the filtered source-map
record set before stream-local pagination and before combined record cursor
pagination. This lets editor and indexer clients inspect available categories
without scanning every emitted array item.

```json
{
  "expressionTotalCount": 36,
  "typeTotalCount": 10,
  "statementTotalCount": 3,
  "recordTotalCount": 49,
  "expressionKinds": [
    {
      "name": "literal",
      "count": 20
    }
  ],
  "statementKinds": [
    {
      "name": "decl",
      "count": 1
    }
  ],
  "typeOwnerKinds": [
    {
      "name": "resource-type",
      "count": 3
    }
  ]
}
```

`expressionKinds` counts expression records by `kind`. `statementKinds` counts
statement records by `statementKind`. `typeOwnerKinds` counts type records by
`ownerKind`. Entries are sorted by `name` for stable client-side lookup and
diffs.

Semantic validators should treat these count fields as consistency fields:
`recordTotalCount` must equal `expressionTotalCount + typeTotalCount +
statementTotalCount`, and the per-category `count` values must sum to their
matching total. When a stream-local source-location array is complete for a
category, validators also confirm the category names and counts match the actual
records. JSON Schema validation checks document shape and scalar types; these
cross-field invariants are enforced by `tools/validate_json_schema.py`.
Package integrity validation applies the same complete-array category checks to
`artifacts.hirSourceMap` even when schema validation is not requested.

### Combined Records

`records` is always present. It is disabled by default so package artifacts and
plain source-map dumps do not duplicate every expression, type, and statement
record in a second array. When enabled, the compiler emits a single
cursor-ordered stream across the already filtered expression, type, and
statement records. Stream-local pagination does not affect this combined record
stream.

When `records.enabled` is `false`, the disabled stream shape is stable:
`activeCount == 0`, `offset == 0`, `emittedCount == 0`, `hasMore == false`,
`nextOffset == 0`, no `limit` field is present, and `items` is empty. The
`totalCount` field still reports the filtered combined total for auditability.

```json
{
  "enabled": true,
  "activeCount": 2,
  "offset": 0,
  "limit": 2,
  "totalCount": 49,
  "emittedCount": 2,
  "hasMore": true,
  "nextOffset": 2,
  "items": [
    {
      "cursor": 0,
      "recordKind": "type",
      "type": {}
    },
    {
      "cursor": 1,
      "recordKind": "statement",
      "statement": {}
    }
  ]
}
```

`totalCount` is the combined count after filtering and before record cursor
pagination. `emittedCount` matches `items.length`. `nextOffset` is the offset to
send on the next request when `hasMore` is true. Items wrap the same expression,
type, or statement record shape used under `hirSourceLocations`, so consumers do
not need separate field semantics for the combined stream.

The semantic validator also checks that `records.totalCount` matches
`categoryCounts.recordTotalCount`, emitted record cursors are contiguous from
`offset`, `offset` and `emittedCount` stay within `totalCount`, emitted items
follow the documented combined-record sort order, emitted item kinds do not
exceed their matching category totals, and `hasMore` follows the
`nextOffset < totalCount` comparison. When the stream-local source location
arrays are complete, validation also confirms each emitted combined record
payload matches the source-location record at its sorted cursor.

Records are sorted by source `location.offset`, then `location.endOffset`, then
type records before statement records before expression records for exact
source-span ties, then the record's original `index`.

CLI flags:

```bash
cglc dump-ir input.cgl --stage hir-source-map --source-map-record-limit 100
```

`--source-map-records` emits the complete combined stream. The offset and limit
flags enable the stream automatically:

```bash
cglc dump-ir input.cgl --stage hir-source-map \
  --source-map-record-offset 100 \
  --source-map-record-limit 50
```

### Source Locations

Each emitted record contains a `location` object:

```json
{
  "file": "input.cgl",
  "line": 10,
  "column": 11,
  "offset": 374,
  "length": 29,
  "endLine": 10,
  "endColumn": 40,
  "endOffset": 403
}
```

`file` is a non-empty source path. `offset` and `endOffset` are byte offsets.
End offsets and end columns are exclusive positions. Emitted source locations
are real source spans: `length` must be positive,
`line`/`column`/`endLine`/`endColumn` are 1-based positive positions, and
same-line spans must advance `endColumn`. For single-token spans,
`endOffset == offset + length`.
Statement records use the parsed statement token range, so multi-line
declarations and control-flow statements span the complete statement instead of
only the leading keyword or type token. The semantic validator checks that every
expression, type, statement, and combined-record source span keeps
`endOffset == offset + length`, non-decreasing end line/column positions, and
the positive-range constraints above.

### HIR Source Locations

`hirSourceLocations` contains summary counts and separate expression/type/
statement arrays:

```json
{
  "expressionCount": 1,
  "expressionWithLocationCount": 1,
  "typeCount": 1,
  "typeWithLocationCount": 1,
  "statementCount": 1,
  "statementWithLocationCount": 1,
  "expressions": [],
  "types": [],
  "statements": []
}
```

When pagination is active, these summary counts describe emitted records. Use
the `pagination` totals for pre-page counts.

For every source-map document, `expressionWithLocationCount` must equal
`expressions.length`, `typeWithLocationCount` must equal `types.length`, and
`statementWithLocationCount` must equal `statements.length`. Pagination emitted
counts must match those emitted array lengths. Within each emitted expression,
type, or statement array, `index` values must be strictly increasing. Filtered
and paged results can skip original indexes, but they still preserve compiler
traversal order.

Context fields must remain internally owned: a non-empty `entryPoint` requires
a non-empty `stage`, and statement records plus statement-scoped expression
records require a non-empty `function` whenever `statementKind` is non-empty.
Unfiltered source-map artifacts are a debuggability boundary: they must contain
at least one source anchor, emit at least one source-location record, and include
at least one emitted record with both non-empty `stage` and `entryPoint` so
native artifact provenance can be tied back to a shader entrypoint.

Expression record fields:

```json
{
  "index": 0,
  "stage": "compute",
  "entryPoint": "main",
  "function": "main",
  "statementKind": "decl",
  "kind": "texture_compare_lod_manual",
  "value": "textureCompareLodManualKernel",
  "type": "float",
  "location": {}
}
```

Type record fields:

```json
{
  "index": 0,
  "stage": "compute",
  "entryPoint": "main",
  "function": "",
  "ownerKind": "resource-type",
  "ownerName": "values",
  "type": "float*",
  "location": {}
}
```

Statement record fields:

```json
{
  "index": 0,
  "stage": "compute",
  "entryPoint": "main",
  "function": "main",
  "statementKind": "decl",
  "name": "visibility",
  "location": {}
}
```

## Schema 8 Resource Lane

Schema 8 exposes the resource source-location contract for callers that opt in
through the C++ DebugMetadata source-map builder. It extends the schema 7 shape
with a fourth
`hirSourceLocations.resources[]` stream, resource pagination fields, resource
category counts, resource filters, and `recordKind: "resource"` entries in the
combined `records.items[]` stream. `cglc dump-ir --stage hir-source-map` and
`--debug-ir` packages continue to emit schema 7 by default; explicit
`dump-ir` callers can request schema 8 with `--source-map-schema-version 8` or
`--hir-source-map-schema-version 8`. If both selector flags are present they
must request the same version, otherwise `cglc` rejects the command with a
usage error. The positive validator fixture is
[`tests/fixtures/hir-source-map-v8-resource-records.json`](../tests/fixtures/hir-source-map-v8-resource-records.json).

Resource records are strict objects. The required fields are:

```json
{
  "index": 0,
  "resourceRecordKind": "declaration",
  "stage": "compute",
  "entryPoint": "main",
  "resourceName": "texture0",
  "resourceKind": "texture",
  "location": {}
}
```

`resourceRecordKind` is closed to `declaration`, `layout`, `set`, `binding`,
and `access`.
`resourceName`, `resourceKind`, `stage`, `entryPoint`, and `location` are
required for every staged resource record. Descriptor resource records may
carry `bindingSet` and `binding` when explicit layout tokens exist. Access
records may also carry optional context such as `function`, `accessKind`,
`accessPath`, `operation`, `memberName`, `indexExpression`, `descriptorSet`,
`registerSpace`, and `registerName`. The schema remains fail-closed:
unknown fields and unknown resource record kinds are rejected.

The semantic validator checks the same source-span rules as expression, type,
and statement records. It also checks `resourceWithLocationCount` against
`resources.length`, resource index ordering, resource filter/category
consistency, resource pagination totals, and combined-record payload
consistency when `records.enabled` is true and all streams are complete.

Resource records preserve the same deterministic stream-local traversal order
as the internal HIR source-location model. Declaration records use
`resourceRecordKind: "declaration"` and layout records use
`resourceRecordKind: "layout"`. Explicit descriptor set and binding token
records use `resourceRecordKind: "set"` and `resourceRecordKind: "binding"`;
the former carries the parsed descriptor set number as `bindingSet`, and the
latter carries the parsed descriptor binding number as `binding`.
Combined schema 8 records sort by source `location.offset`, then
`location.endOffset`, then type records before statement records before
expression records before resource records for exact source-span ties, then the
record's original `index`.

## Report-Only Resource Source-Location Gap Inventory

Publication status note: schema 8 is now a checked-in, validator-backed,
opt-in HIR source-map schema for C++ builder callers and `cglc dump-ir`
callers that pass `--source-map-schema-version 8` (or the
`--hir-source-map-schema-version 8` alias). This report-only block is retained
for the CrossTL separation and default package emission boundary. Package debug
artifacts intentionally continue to emit v7 until promotion is explicitly
requested for package writing.

This section is a report-only checklist for future HIR source-map model work.
It does not change the default compiler-emitted schema, add schema 7 resource
record fields, change package-emitted JSON, or claim complete resource
source-location support. Schema 8 now names and validates the opt-in resource
record envelope, and `cglc dump-ir --stage hir-source-map` can emit the v8
envelope only when explicitly requested. Package output remains on v7.

The boundary is deliberate:

- CrossTL `source_location` inventory is recorded by
  `docs/language/SOURCE_LOCATION_REQUIREMENTS.md` for `ASTNode.source_location`
  under `/ast/classFields`. That inventory is CrossTL object-shape evidence
  only and cannot populate HIR/source-map records.
- Compiler HIR/source-map schema v7 remains the default package/debug artifact
  shape and carries expression, type, and statement locations. Resource entries
  also appear as `ownerKind: "resource-type"` type rows when
  `HIRResource.type.location` is available.
- Compiler HIR/source-map schema v8 is opt-in for `cglc dump-ir` and emits the
  resource lane for HIR-owned declaration, layout, descriptor set/binding, and
  direct resource identifier access spans. This is compiler provenance, not
  CrossTL AST inventory.
- `HIRResource` still does not carry cbuffer declaration/block spans or explicit
  source locations for every lowered resource-use shape. Those remain future
  work before package artifacts can claim complete resource source-map coverage.

<!-- crossgl-hir-resource-source-location-gap-v1:begin -->
```json
{
  "kind": "crossgl-hir-resource-source-location-gap-inventory",
  "version": 1,
  "status": "report-only-gap-inventory",
  "schemaVersionAffected": "8",
  "claims": {
    "crosstlSourceLocation": "inventory-only-not-hir-source-map-support",
    "compilerHIRResourceSpans": "declaration-layout-set-binding-opt-in-v8",
    "behavior": "schema-8-cli-opt-in-only-package-output-remains-v7"
  },
  "currentInventory": [
    {
      "id": "crosstl.ast-source-location-inventory",
      "status": "inventory-only",
      "evidence": "docs/language/SOURCE_LOCATION_REQUIREMENTS.md records ASTNode.source_location under /ast/classFields.",
      "limitation": "CrossTL source_location inventory cannot populate compiler HIR source-map records."
    },
    {
      "id": "compiler.resource-type-location",
      "status": "partial-current-support",
      "evidence": "buildHIRSourceLocations records HIRResource.type as ownerKind resource-type when HIRResource.type.location is available.",
      "limitation": "This is a type span, not a resource declaration, layout, binding, access, or resource identity span."
    },
    {
      "id": "compiler.resource-declaration-layout-location",
      "status": "opt-in-current-support",
      "evidence": "HIRResource carries declaration, layout, set, and binding spans, and schema 8 emits declaration/layout/set/binding resource records when cglc dump-ir is called with --source-map-schema-version 8.",
      "limitation": "Package artifacts still emit schema 7, and individual storage-image format token spans are not separate resource records."
    }
  ],
  "gapChecklist": [
    {
      "id": "gap.resource-declaration",
      "status": "partial-current-support",
      "futureSpanNeeded": "Schema 8 emits whole declaration spans for HIR-owned resources. Remaining work: resource name token spans and cbuffer-backed uniform resources."
    },
    {
      "id": "gap.resource-layout",
      "status": "partial-current-support",
      "futureSpanNeeded": "Schema 8 emits whole layout clause spans and individual descriptor set/binding token spans. Remaining work: storage-image format key/value spans."
    },
    {
      "id": "gap.resource-access",
      "status": "partial-current-support",
      "futureSpanNeeded": "Schema 8 emits direct resource identifier access spans when HIR expression provenance still matches a staged resource. Remaining work: member/index/nonuniform descriptor index context, texture/sampler operands, storage-image read/write/atomic operands, and buffer/shared memory access expressions with explicit resource identity."
    },
    {
      "id": "gap.cbuffer-resource",
      "status": "gap",
      "futureSpanNeeded": "CBuffer resource declaration and block-name spans; current cbuffer HIRResource.type has no source location."
    },
    {
      "id": "gap.schema-records",
      "status": "partial-current-support",
      "futureSpanNeeded": "Schema 8 emits declaration/layout/set/binding/access resource records through explicit CLI opt-in. Remaining work: package artifact promotion and deeper access-path context."
    },
    {
      "id": "future.hir-resource-model",
      "status": "partial-current-support",
      "futureSpanNeeded": "HIRResource retains declaration and layout source-location fields, and the source-map builder can infer direct access records from HIR expression provenance. Remaining model work: explicit access identity, cbuffer, and individual layout-token spans."
    },
    {
      "id": "future.source-map-schema",
      "status": "partial-current-support",
      "futureSpanNeeded": "HIR source-map schema v8 names and emits the resource evidence lane by explicit dump-ir opt-in. Debug/package artifact promotion remains future work."
    },
    {
      "id": "future.fixtures",
      "status": "future-work",
      "futureSpanNeeded": "Fixture and semantic validation must prove declaration, layout, access, cbuffer, and CrossTL-inventory separation cases."
    }
  ],
  "stopConditions": [
    "do-not-change-parser-recovery",
    "do-not-change-HIRResource-model-in-this-report",
    "do-not-change-hir-source-map-schema-or-emission",
    "do-not-refresh-fixture-hashes",
    "do-not-claim-support-from-CrossTL-source-location-inventory"
  ]
}
```
<!-- crossgl-hir-resource-source-location-gap-v1:end -->

Future implementation workers should treat this inventory as a to-do list for
complete package/default resource provenance, not as evidence for broader
resource coverage. Schema 8 is support evidence only for the explicitly
requested `dump-ir` resource lane documented above. A support claim for complete
resource declaration, layout, or access source locations still needs broader
compiler-owned HIR model fields, package/default emission promotion, fixture
coverage, and validation that CrossTL `source_location` inventory stays
separate from compiler provenance. The checked command for this report-only gap
inventory is:

```sh
python3 tools/check_language_source_location_requirements.py --root .
```
