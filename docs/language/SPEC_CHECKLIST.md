# CrossGL Shared Language Spec Checklist v0

This is the stable human-facing checklist for the CrossTL-derived shared
language spec index. It summarizes the generated evidence in `SPEC_INDEX.md`
and the drift workflow in `DRIFT_REVIEW.md`; it is report-only and does not
change accepted syntax, compiler parser behavior, CrossTL behavior, diagnostics,
or conformance expectations.

This checklist does not change accepted syntax.

Use `docs/language/crosstl-frontend-language-spec-v0.json` as the sealed
machine-readable inventory, `tools/cross_repo_language_contract.json` as the
fixture contract, `tests/conformance/manifest.v0.json` as the feature/status
bucket inventory, and `COMPATIBILITY.md` plus `V0_SUPPORT.md` for native-v0
classification. If evidence is missing, document the gap instead of inventing a
grammar rule or support claim.

## Spec Index Map

| Checklist id | Review class | Generated index rows | Snapshot refs | Source files | Fixture or evidence lane |
| --- | --- | --- | --- | --- | --- |
| `check.lexical-grammar` | `lexical-grammar` | `lexical.tokens`, `lexical.keywords`, `lexical.literals-and-skips` | `/lexical/tokens`, `/lexical/keywords`, `/lexical/literalTokens`, `/lexical/skipTokens` | `crosstl/translator/lexer.py` | `control_flow_and_statements` where keywords overlap accepted fixtures; token-only rows may have no fixture and must remain source-seal evidence. |
| `check.grammar-productions` | `grammar-productions` | `grammar.stages`, `grammar.types`, `grammar.qualifiers`, `grammar.resources` | `/language/stages`, `/language/types`, `/language/qualifiers`, `/language/resources` | `crosstl/translator/lexer.py`, `crosstl/translator/parser.py`, `crosstl/translator/ast.py`, `crosstl/translator/validation.py` | `module_stages_and_entry_points`, `types_structs_arrays_and_constants`, `resources_layouts_and_storage`, `descriptor_indexing_and_nonuniform`, and texture/sampler fixture groups where present. |
| `check.ast-nodes` | `ast-nodes` | `ast.class-inventory` | `/ast/classes`, `/ast/classFields`, `/ast/typeNodes`, `/ast/statementNodes`, `/ast/expressionNodes`, `/ast/enums` | `crosstl/translator/ast.py` | Contract AST hashes and fixture groups are evidence only; a CrossTL AST node is not native HIR support by itself. |
| `check.semantic-checks` | `semantic-checks` | `semantics.metadata-and-layout`, `semantics.intrinsics` | `/validation/metadata`, `/validation/stageLayout`, `/language/intrinsics` | `crosstl/translator/parser.py`, `crosstl/translator/validation.py` | Semantic rows map to accepted fixtures when current contracts cover them; uncovered validation facts stay prose/spec debt. |
| `check.compatibility-classifications` | `native-v0-compatibility-bucket` | `grammar.stages`, `grammar.types`, `grammar.resources`, `ast.class-inventory`, `semantics.metadata-and-layout`, `semantics.intrinsics` | `/source/files`, `/notes`, `/language/stages`, `/language/types`, `/language/resources`, `/ast/classes`, `/validation/metadata`, `/language/intrinsics` | `crosstl/translator/lexer.py`, `crosstl/translator/parser.py`, `crosstl/translator/ast.py`, `crosstl/translator/validation.py` | Classify CrossTL acceptance versus native-v0 using `spec.unsupported-for-native-v0`, `spec.deprecated`, `spec.error`, or `target.unsupported`; unsupported owner buckets are `compat.language-unsupported-native-v0`, `compat.frontend-unsupported-native-v0`, and `compat.target-legalization-unsupported`. |
| `check.source-file-anchors` | `cross-repo-fixture-contract-impact` | `provenance.source-seal` | `/source/files`, `/source/extraction` | `crosstl/translator/lexer.py`, `crosstl/translator/parser.py`, `crosstl/translator/ast.py`, `crosstl/translator/validation.py` | Cross-repo evidence lives in `accepted_contracts`, `negative_contracts`, fixture exclusions, CrossTL AST hashes, and compiler HIR hashes. |

Current accepted fixture groups to review when a snapshot facet overlaps
contract evidence are `control_flow_and_statements`,
`crosstl_examples_and_backend_policy`, `descriptor_indexing_and_nonuniform`,
`expressions_operators_and_intrinsics`, `module_stages_and_entry_points`,
`resources_layouts_and_storage`, `textures_samplers_images_and_intrinsics`,
and `types_structs_arrays_and_constants`. These names come from the contract
manifest; if a snapshot row has no matching group, keep it as source-seal
evidence and record the gap.

Current conformance buckets used by this checklist are `atomics:accepted`,
`compute-basics:accepted`, `control-flow:accepted`,
`graphics-stages:accepted`, `known-native-v0-unsupported:unsupported`,
`resources:accepted`, `storage-images:accepted`, and
`texture-sampling:accepted`.

## Parser-Change Drift Review

Before a parser-owner task changes accepted source, parser recovery, AST
construction, fixture expectations, source-location propagation, or native
compiler behavior, a report-only handoff must satisfy `parser-drift-review` for
`crosstl/translator/parser.py`.

Required parser-change evidence:

- `source-seal-hash-comparison`: compare the observed CrossTL parser source
  hash with the sealed `/source/files` entry and the snapshot SHA-256.
- `drift-class-assignment`: choose `lexical-grammar-drift`,
  `grammar-productions-drift`, `ast-nodes-drift`, or
  `semantic-checks-drift`, then map it back to the generated review class.
- `compatibility-bucket-assignment`: assign one `COMPATIBILITY.md`
  classification before recommending compiler action. Stop on
  `missing-compatibility-bucket` when no existing row fits.
- `conformance-bucket-review`: name a feature/status bucket such as
  `compute-basics:accepted`, `resources:accepted`, or
  `known-native-v0-unsupported:unsupported`.
- `cross-repo-fixture-update-decision`: choose
  `no-current-fixture-impact`, `requires-accepted-contract-fixture`,
  `requires-negative-contract-fixture`, or
  `requires-fixture-exclusion-or-hash-refresh`.
- `source-location-impact`: state whether `source_location` inventory,
  diagnostic spans, and native source-map expectations remain report-only, or
  name the owning behavior slice.
- `stop-condition-before-behavior-change`: name the stop condition that blocks
  parser or fixture changes in this report-only slice.

Refresh `docs/language/crosstl-frontend-language-spec-v0.json`,
`docs/language/SPEC.md`, and `docs/language/SPEC_INDEX.md` only after a sealed
source change is accepted as shared language authority. Use these trigger
tokens in the handoff: `sealed-source-hash-changed`,
`lexical-grammar-drift`, `grammar-productions-drift`, `ast-nodes-drift`, and
`semantic-checks-drift`.

Update the cross-repo contract only in a behavior-owning contract slice when
the fixture meaning changes. Use these trigger tokens:
`accepted-source-form-added-or-removed`,
`negative-source-form-added-or-removed`, `canonical-ast-hash-changed`,
`compiler-hir-hash-changed`, and `fixture-bucket-changed`.

## Stop Conditions

Stop and report the blocker instead of updating syntax, snapshots, fixtures, or
compiler behavior when any of these applies:

| Stop id | Meaning |
| --- | --- |
| `requires-translator-change` | The source of truth must change in CrossTL before compiler work can be justified. |
| `changes-accepted-syntax` | The task would change accepted syntax, parser recovery, AST lowering, diagnostics, source locations, or native behavior. |
| `requires-language-design-decision` | The drift exposes an undecided language rule, interpretation, compatibility bucket, or native-v0 support claim. |
| `stale-generated-artifacts` | Generated spec artifacts would need regeneration after an intentional source/snapshot update. |
| `missing-compatibility-bucket` | No current compatibility classification fits the observed delta. |
| `missing-contract-evidence` | No accepted fixture, negative fixture, CrossTL example, CTest, or planned exclusion pins the drift. |

## Validation

Run the report-only checks that match the changed surface:

```sh
python3 tools/generate_crosstl_language_spec_docs.py --check
python3 tools/check_language_spec_index.py --root .
python3 tools/check_language_spec_trace.py --root .
python3 tools/check_language_drift_review.py --root .
python3 tools/check_language_compatibility.py --root .
git diff --check
```

Do not refresh `accepted_contracts`, `negative_contracts`, CrossTL AST hashes,
compiler HIR hashes, snapshots, or conformance expectations in a report-only
checklist update.
