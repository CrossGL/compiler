# CrossGL Language Source-Location Requirements

This is a checked, report-only contract for source-location requirements in the
shared CrossGL language handoff. CrossTL AST `source_location` fields are
inventory only. They record current CrossTL object shape in the sealed frontend
snapshot, but they are not a native-v0 diagnostic range or source-map support
claim.

CrossTL `ASTNode.source_location` is frontend metadata. It is excluded from
structural AST compatibility and structural AST hashing, and its presence does
not prove compiler HIR source-map spans. Structural compatibility and hash
comparisons must continue to use the canonical AST/HIR fixture contracts without
promoting or normalizing CrossTL `source_location` metadata into the structural
key.

Native compiler source-map records, diagnostic spans, feature-report
`sourceLocations`, or target/package debug locations require separate native
source-map evidence before support claim. Diagnostic span evidence before
support claim must identify the compiler-owned source construct, the diagnostic
or HIR/source-map record that carries it, and the support bucket that owns the
claim. support-bucket-evidence-before-native-v0-claim is required before any
native-v0 support text can rely on source-location facts. This page does not
authorize syntax, parser recovery, CrossTL behavior, HIR lowering, diagnostics,
package output, fixture hashes, or compiler behavior changes.

Inventory-only rows must keep `sourceLocations` empty. Non-empty
`sourceLocations` require native compiler span evidence through compiler-owned
HIR source-map provenance, CTest, support-matrix, or conformance records.
Diagnostic-span evidence stays diagnostic-owned and separate. CrossTL AST
`source_location` inventory cannot populate feature-report spans.

Compiler resource provenance must come from compiler-owned C++ `SourceLocation`
capture and HIR lowering evidence. CrossTL AST metadata cannot populate, prove,
or stand in for HIR resource declaration, layout, or access spans, and this
report does not claim new compiler source-map support for those spans.

## Checked Manifest

The manifest below records the current CrossTL AST source-location inventory and
the evidence gates that must stay visible before any shared language support
claim can mention native source maps or diagnostic spans.

<!-- crossgl-language-source-location-requirements-v1:begin -->
```json
{
  "kind": "crossgl-language-source-location-requirements",
  "version": 1,
  "status": "report-only-evidence-gate",
  "snapshot": "docs/language/crosstl-frontend-language-spec-v0.json",
  "snapshotRefs": [
    "/ast/classFields"
  ],
  "inventory": [
    {
      "class": "ASTNode",
      "constructorParameters": [
        {
          "annotation": null,
          "default": "None",
          "kind": "positional-or-keyword",
          "name": "source_location",
          "optional": true,
          "required": false
        }
      ],
      "fields": [
        {
          "annotation": null,
          "default": "None",
          "initializer": "source_location",
          "name": "source_location",
          "optional": true,
          "parameter": "source_location",
          "required": false,
          "source": "parameter"
        }
      ]
    }
  ],
  "inventorySha256": "138322d369f568884604d84dccfd052ff30ef50c281a8b724c998f6336e3c8c5",
  "claims": {
    "crosstlAstSourceLocation": "inventory-only",
    "nativeSourceMap": "requires-separate-native-source-map-evidence",
    "diagnosticSpans": "requires-separate-diagnostic-span-evidence",
    "nativeV0Support": "not-claimed-by-source-location-inventory",
    "structuralAstCompatibility": "source-location-excluded-from-structural-ast-hashing",
    "resourceProvenance": "requires-compiler-owned-cpp-sourcelocation-and-hir-lowering",
    "behavior": "no-syntax-parser-crosstl-hir-diagnostic-package-fixture-or-compiler-behavior-change"
  },
  "requiredEvidenceBeforeSharedSupportClaim": [
    "native-source-map-evidence-before-support-claim",
    "diagnostic-span-evidence-before-support-claim",
    "support-bucket-evidence-before-native-v0-claim"
  ],
  "referenceDocs": [
    "docs/language/AST_SCHEMA.md",
    "docs/language/DRIFT_REVIEW.md",
    "docs/language/CHANGE_POLICY.md",
    "docs/language/V0_SUPPORT.md",
    "docs/language/FEATURE_REPORT.md",
    "docs/language/COMPATIBILITY.md",
    "docs/language/SEMANTICS.md",
    "docs/architecture/SHARED_LANGUAGE_SPEC_PLAN.md"
  ]
}
```
<!-- crossgl-language-source-location-requirements-v1:end -->

## Evidence Boundaries

| Evidence lane | Current status | Requirement before a support claim |
| --- | --- | --- |
| CrossTL AST field inventory | `docs/language/crosstl-frontend-language-spec-v0.json` records `ASTNode.source_location` under `/ast/classFields`. | Treat as CrossTL object-shape inventory only. |
| Structural AST compatibility and hashing | CrossTL `ASTNode.source_location` is frontend metadata, not a structural AST field for compatibility or canonical hash decisions. | Exclude it from structural compatibility and structural AST hashes; do not use it to prove compiler HIR source-map spans. |
| AST schema prose | `docs/language/AST_SCHEMA.md` says source locations are not sealed by the current snapshot and compiler diagnostics must keep using native source-map evidence. | Keep source-location requirements separate from the AST field inventory. |
| Drift review | `docs/language/DRIFT_REVIEW.md` routes `source-location-expectations` through report-only review inputs and source-location notes. | Stop before parser, AST, source-location propagation, fixture, or accepted-syntax behavior changes. |
| Change policy | `docs/language/CHANGE_POLICY.md` keeps `source-location-requirements` report-only and requires `native-source-map-evidence-before-support-claim`. | Do not promote inventory to `native-v0-supported` without evidence. |
| v0 support | `docs/language/V0_SUPPORT.md` states that CrossTL AST `source_location` inventory alone is not native-v0 diagnostic range or source-map support. | Cite fixture, HIR/source-map, CTest, diagnostic, target, package, or conformance evidence before support text changes. |
| Feature reports | `docs/language/FEATURE_REPORT.md` allows `sourceLocations` only when a contributing feature has a real compiler span. | Keep CrossTL inventory rows location-empty, name the native span source, and keep unsupported facts separate from diagnostics. |
| Resource provenance | Resource declaration, layout, and access spans belong to compiler-owned C++ `SourceLocation` capture and HIR lowering evidence. | Do not populate or prove HIR resource spans from CrossTL AST metadata, and do not describe this report as new compiler source-map support. |
| Architecture plan | `docs/architecture/SHARED_LANGUAGE_SPEC_PLAN.md` identifies HIR source-map checks as the proof lane for diagnostics. | Use compiler-owned source-map evidence, not CrossTL inventory, for diagnostic-span claims. |

## Review Rule

When a report or implementation proposal mentions source locations, classify the
statement first:

1. CrossTL `source_location` field in `/ast/classFields`: inventory-only.
2. Native HIR source-map location: evidence candidate, not a support claim until
   tied to the relevant support bucket.
3. Diagnostic location or span: evidence candidate, not a shared language claim
   until the diagnostic code and source construct are named.
4. Package/debug source location: package/debug evidence only; it does not
   expand accepted syntax or parser behavior.
5. Resource declaration, layout, or access span: compiler-owned C++
   `SourceLocation` and HIR lowering evidence only; CrossTL AST metadata is not
   evidence for these spans.

If the next step would change accepted syntax, parser recovery, CrossTL AST
construction, HIR lowering, diagnostics, package output, fixture hashes, or
compiler behavior, stop and move the work to the behavior-owning slice. The
checked command for this report-only contract is:

```sh
python3 tools/check_language_source_location_requirements.py --root .
```
