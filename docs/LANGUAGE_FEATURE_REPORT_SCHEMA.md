# CrossGL Language Feature Report Schema

`docs/schemas/language-feature-report-v1.schema.json` defines the report-only
JSON contract in `docs/language/FEATURE_REPORT.md`.

`cglc language-feature-report <input.cgl>` emits this v1 report for a parsed
source module. Compiler emission is future work for package artifacts and broad
frontend redesign; the current emitter is a focused report-only CLI lane.
The committed canonical example remains a hand-authored schema fixture and must
not be treated as byte-for-byte `cglc` output.

## Contract

The top-level document is a closed object with `schemaVersion: 1`, `kind`,
module identity, language identity, the CrossTL snapshot seal, compatibility
bucket counts, target feature gates, resource/memory/layout feature records,
unsupported/deprecated/error facts, evidence records, and generation metadata.

The schema rejects unknown fields at every defined object boundary. Arrays for
target gates, feature groups, fact groups, and evidence may be empty, but each
reported gate, feature, or fact must include at least one namespaced
`evidenceIds` reference.

## Semantic Checks

`tools/json_schema_semantics/language_feature_report_v1.py` performs checks that
are tied to repository state or cross-field consistency:

- `schemaVersion` and `kind` must identify the v1 language feature report.
- `crossTLSnapshotSeal` must match the committed
  `docs/language/crosstl-frontend-language-spec-v0.json` path, SHA-256 over
  normalized UTF-8 text, and snapshot schema version.
- `module.sourceSha256` is checked for repository-local source files as a
  SHA-256 over UTF-8 source text after CRLF/CR line endings are normalized to
  LF.
- `compatibilityBucketSummary` must match the count of
  `resourceMemoryLayoutFeatures.*[].status` entries plus
  `facts.*[].classification` entries.
- CrossTL snapshot aggregate feature rows use `cross-tl-inventory-only` so
  shared language/spec inventory is not confused with native compiler
  `accepted-source` coverage.
- Every evidence ID referenced by a gate, feature, or fact must appear in the
  top-level `evidence` array.
- Every target feature gate must use the projected legalization package mode,
  carry at least one required or missing capability for unsupported/planned
  limitation statuses, and include corresponding
  `target-contract:<target>.package-support`,
  `target-contract:<target>.package-mode.<mode>`, and
  `target-contract:<target>.support.<status>` evidence IDs.

Target feature gates are target-specific detail rows. They are not counted in
`compatibilityBucketSummary` unless the same limitation is represented by a
feature record or fact.

## Canonical Example

`tests/language-feature-report/canonical.json` is the canonical valid example
for this schema. It mirrors the JSON contract block in
`docs/language/FEATURE_REPORT.md` and is checked against the committed CrossTL
snapshot seal and normalized module source hash by
`tools/check_language_feature_report_plan.py`.

Validate it directly with:

```sh
python tools/validate_json_schema.py \
  --schema docs/schemas/language-feature-report-v1.schema.json \
  --instance tests/language-feature-report/canonical.json
python tools/check_language_feature_report_plan.py --root .
```

## CLI Emission

Generate a module report with:

```sh
cglc language-feature-report tests/fixtures/ResourceShader.cgl
```

The command reads the source through the existing parser/HIR pipeline, computes
the normalized UTF-8 source hash, seals the report against
`docs/language/crosstl-frontend-language-spec-v0.json`, and emits deterministic
JSON using the v1 schema fields only. It reports target limitations as
`targetFeatureGates` and, when a module has target-limited support, as
`facts.unsupported` entries classified as `target.unsupported`.

Feature `sourceLocations` are emitted when the compiler has a real source span
for the contributing feature. Resource and shared-memory records use HIR type
spans, expression-derived records such as barriers, atomics, and nonuniform
descriptor indexes use HIR expression spans, and layout metadata uses the
existing parser layout spans when HIR stores only resolved values or booleans.
Each location `file` is normalized to `module.sourcePath`, arrays are sorted in
source order, and duplicate spans are removed. Empty arrays remain valid for
aggregate feature facts that do not yet carry a precise span.
