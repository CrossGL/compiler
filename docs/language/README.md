# CrossGL Language Spec Snapshots

This directory contains generated seed artifacts for the shared CrossGL language
spec. The first snapshot is extracted from the CrossTL frontend because CrossTL
is the existing CrossGL parser and interchange implementation.

Regenerate the v0 CrossTL frontend snapshot:

```sh
python3 tools/extract_crosstl_language_spec.py \
  --translator-root /path/to/CrossGL-Translator
```

Check that the committed snapshot is current:

```sh
python3 tools/extract_crosstl_language_spec.py \
  --translator-root /path/to/CrossGL-Translator \
  --check
```

When `--output` is supplied as a relative path, the extractor resolves it from
the CrossGL-Compiler repository root (`--root`) rather than the caller's current
working directory. This keeps CI and local regeneration deterministic.

`crosstl-frontend-language-spec-v0.json` is a deterministic machine-readable
inventory of CrossTL lexer tokens, keyword spellings, parsed type/resource
families, shader stage spellings, AST node classes, and validation metadata.
`SPEC.md` is generated from that sealed JSON snapshot and gives compiler work a
prose entry point for the same facts, including native-v0 unsupported and
deprecated distinctions. `SPEC_INDEX.md` is generated from the same snapshot plus
`tools/cross_repo_language_contract.json`; it maps lexical, grammar, AST, and
semantic categories to CrossTL source-file provenance and compatibility fixture
groups, identifies machine-readable inventory versus remaining prose/spec debt,
and records stop conditions for preventing CrossTL/compiler drift.
`SPEC_CHECKLIST.md` is the hand-written human checklist layered over that
generated index; it tells future workers which source files, fixture lanes,
compatibility buckets, refresh triggers, and stop conditions must be reviewed
before parser or contract behavior changes are proposed. Regenerate the
generated docs after intentional snapshot or contract-index changes:

```sh
python3 tools/generate_crosstl_language_spec_docs.py
```

Check that the committed generated artifacts match the snapshot and contract
manifest:

```sh
python3 tools/generate_crosstl_language_spec_docs.py --check
```

Check that the generated spec index covers the major snapshot categories and
contract fixture groups:

```sh
python3 tools/check_language_spec_index.py --root .
```

Check that the v0 support provenance seal still ties the CrossTL snapshot,
cross-repo contract, and conformance manifest together:

```sh
python3 tools/check_language_provenance.py --root .
```

For a machine-readable drift-review summary of the same report-only evidence,
write the optional JSON report after validation succeeds:

```sh
python3 tools/check_language_spec_index.py \
  --root . \
  --drift-report /tmp/crossgl-language-spec-index-drift-report.json
```

This checker also verifies that `tools/cross_repo_language_spec.json` is sealed
to the same CrossTL snapshot and cross-repo contract, and that `V0_SUPPORT.md`
cites known `feature:<group>` tokens and the negative compatibility
classifications from the contract. It also treats the generated
`Shared Spec Checklist` in `SPEC_INDEX.md` as the checked source-of-truth
layer, mapping lexical grammar, grammar productions, AST node families,
semantic checks, compatibility buckets, and cross-repo fixture evidence back
to snapshot refs, source seals, fixture groups, negative cases, and review
routes. The same check validates the merged PR #720 report and follow-on
post-PR720 sealed-source audit against the current CrossTL-derived snapshot, so
those report-only references cannot drift into manual language definitions.
The optional drift report serializes that mapping for future CrossTL
snapshot/source drift review; it does not change accepted syntax, compiler
parser behavior, CrossTL behavior, or conformance expectations. The JSON
snapshot is not yet the full grammar, and `SPEC.md` plus
`SPEC_INDEX.md` must not be edited by hand.

Unsupported native-v0 negative cases are also owner-checked. A
`spec.unsupported-for-native-v0` contract case must cite exactly one of
`compat.language-unsupported-native-v0` or
`compat.frontend-unsupported-native-v0` in its compatibility anchors, and a
`target.unsupported` case must cite `compat.target-legalization-unsupported`.
The generated feature spec exposes this as `native_v0_owner_bucket`, and
`SPEC_INDEX.md` reports owner-bucket counts for negative compatibility groups.
Compiler CI can run the extractor and generated-doc checks to detect CrossTL
frontend drift or stale spec-index/provenance/support links before
CrossGL-Compiler grows a parallel compiler-only dialect.
The cross-repo GitHub workflow keeps push and pull-request validation pinned to
CrossGL/crosstl `main`. Manual `workflow_dispatch` runs may set
`crosstl_ref` to an active CrossTL branch or PR ref for preview-only drift
review; a failed preview run is not permission to refresh the committed
compiler snapshot until that CrossTL ref becomes the agreed authority.

Runtime package-loader admission, runtime compatibility checks, and native
artifact selection are outside this CrossTL-derived language spec. Language
entries in this directory and `tools/cross_repo_language_spec.json` must be
sourced from the CrossTL frontend snapshot or the shared language contract;
runtime architecture/package docs own loader admission and native artifact
selection.

Hand-written v0 prose is layered on top of the generated snapshot:

- [GRAMMAR.md](GRAMMAR.md) describes the accepted CrossTL grammar surface and
  the narrower native-v0 grammar subset.
- [AST_SCHEMA.md](AST_SCHEMA.md) documents the CrossTL AST schema seed and
  calls out where node presence is not native compiler support.
- [SOURCE_LOCATION_REQUIREMENTS.md](SOURCE_LOCATION_REQUIREMENTS.md) is the
  `docs/language/SOURCE_LOCATION_REQUIREMENTS.md` report-only evidence gate for
  source-location claims. CrossTL AST
  `source_location` fields are inventory only; native source-map and diagnostic
  spans require separate evidence before becoming shared language support
  claims.
- [SEMANTICS.md](SEMANTICS.md) records the v0 semantic baseline, invalid
  source classes, accepted-but-unsupported forms, and target-specific package
  rules.
- [COMPATIBILITY.md](COMPATIBILITY.md) is the delta ledger that every prose page
  uses to separate CrossTL acceptance from native-v0 support, including
  report-only owner buckets for language-future-feature,
  compiler-frontend-subset-limit, and target-legalization-limit roadmap work.
- [DRIFT_REVIEW.md](DRIFT_REVIEW.md) is the report-only checklist for reviewing
  CrossTL lexical, grammar, AST, semantic, compatibility, and fixture-contract
  drift before compiler behavior changes are proposed; its checked
  `pr720-style-source-seal-handoff` records the snapshot, support-bucket, and
  cross-repo contract lanes for PR720-style frontend definition updates.
- [SPEC_CHECKLIST.md](SPEC_CHECKLIST.md) is the stable human-facing shared
  language index/checklist slice. It summarizes `SPEC_INDEX.md` into review
  rows for lexical grammar, parser productions, AST node families, semantic
  hooks, compatibility classifications, source-file anchors, and parser-change
  drift triggers without changing the generated snapshot or accepted syntax.
- [CROSSTL_PR720_LANGUAGE_DELTA_AUDIT_20260602.md](CROSSTL_PR720_LANGUAGE_DELTA_AUDIT_20260602.md)
  is the report-only compiler-side delta audit for CrossGL/crosstl PR #720
  against the sealed language snapshot and contract docs.
- [CROSSTL_PR720_NEXT_LANGUAGE_DELTA_AUDIT_20260604.md](CROSSTL_PR720_NEXT_LANGUAGE_DELTA_AUDIT_20260604.md)
  is the report-only follow-on audit for the local CrossTL `integration-fixes`
  head after merged PR #720; it pins the narrow float-literal frontend delta
  already present in the compiler snapshot.
- [CROSSTL_POST_SNAPSHOT_REFRESH_DECISION_20260605.md](CROSSTL_POST_SNAPSHOT_REFRESH_DECISION_20260605.md)
  is the report-only shared-language-spec owner decision for the later
  post-snapshot CrossTL lexer/parser source-seal drift; it rejects a snapshot
  refresh until compatibility, conformance, generated provenance, and
  cross-repo contract evidence are updated in a coordinated owner task.
- [SPEC_TRACE.md](SPEC_TRACE.md) is the report-only audit that maps sealed
  CrossTL snapshot/source evidence to v0 support and compatibility buckets;
  its checked traceability checklist is the stable prose index for lexical,
  grammar, AST, semantic, compatibility, source-provenance, and fixture facets.
- [CHANGE_POLICY.md](CHANGE_POLICY.md) is the report-only policy for moving
  intentional CrossTL lexer, parser, AST, and validation changes through the
  shared snapshot, generated docs, compatibility ledger, cross-repo contract,
  and native compiler support buckets.
- [FEATURE_REPORT.md](FEATURE_REPORT.md) is the report-only planning contract
  for the future per-module language/version feature report.

Check that the handwritten compatibility ledger keeps stable report-only
classification and bucket references:

```sh
python3 tools/check_language_compatibility.py --root .
```

The concrete v0 alpha language/support contract is
[V0_SUPPORT.md](V0_SUPPORT.md). It maps this CrossTL-derived snapshot and the
cross-repo fixture contract to accepted source forms, package-supported subsets,
compatibility-only forms, unsupported/planned forms, and target-limited package
rules. Keep its table evidence concrete by running:

```sh
python3 tools/check_v0_support_evidence.py --root .
```

The checker is intentionally a support-evidence gate, not a formal language
grammar proof. It verifies that support rows cite local fixtures, registered
CTest names, unit-test functions, compatibility row ids, or planned-failure
evidence instead of batch-only prose.

Check the report-only language change policy manifest and required references:

```sh
python3 tools/check_language_change_policy.py --root .
```

The change-policy checker also pins the report-only policy slices for
`syntax-tightening`, `deprecation`, and `source-location-requirements`. These
slice ids must stay visible in this directory's policy entry points so future
CrossTL syntax tightening, legacy spelling deprecation, or source-location
handoffs are routed through the shared snapshot, compatibility ledger, and
support evidence before any compiler behavior changes.
The drift-review checklist additionally pins `parser-drift-review` and
`ast-drift-review` so parser/AST drift cites snapshot hashes, fixture impact,
source-location impact, a compatibility bucket, and a stop condition before a
behavior-owning parser or AST slice starts.

Check that CrossTL snapshot/source evidence still resolves to the expected v0
support and compatibility buckets. This audit is registered as both CTest
coverage in `tests/cmake/CrossGLPythonTests.cmake` and focused pre-commit
hooks in `.pre-commit-config.yaml`:

```sh
python3 tools/check_language_spec_trace.py --root .
```

Check that the report-only AST schema contract stays tied to the current
CrossTL snapshot class and field inventory:

```sh
python3 tools/check_language_ast_schema_contract.py --root .
```

This report-only AST schema contract validates the `AST_SCHEMA.md` handoff
against `/ast/classes`, `/ast/classFields`, node-family arrays, and enum values
from `crosstl-frontend-language-spec-v0.json`. It does not define a serialized
AST wire format, source-location seal, native compiler parser behavior, HIR
lowering, or native support claim.

Check that the report-only source-location requirements contract keeps CrossTL
AST `source_location` fields as inventory only and keeps native source-map or
diagnostic-span claims evidence-gated:

```sh
python3 tools/check_language_source_location_requirements.py --root .
```

Check that the report-only CrossTL grammar surface contract v1 keeps
`GRAMMAR.md` pinned to the sealed snapshot inventory, not native compiler
parser behavior and not native-v0 support:

```sh
python3 tools/check_language_grammar_surface_contract.py --root .
```

The checker scope is exactly `/source/files`, `/lexical/tokens`,
`/lexical/keywords`, `/lexical/literalTokens`, `/lexical/skipTokens`,
`/language/stages`, `/language/types`, `/language/qualifiers`, and
`/language/resources`. It leaves `/ast/*` to the AST contract and leaves
`/validation/*` and `/language/intrinsics` to semantic-baseline work.

To review a likely CrossTL source change before deciding whether it belongs in
the shared snapshot, emit the report-only anchor map for the changed frontend
files:

```sh
python3 tools/check_language_spec_trace.py \
  --root . \
  --changed-crosstl-source crosstl/translator/lexer.py \
  --anchor-report /tmp/crossgl-language-spec-anchors.json
```

The JSON report maps the affected CrossTL snapshot/source records to
`SPEC_INDEX.md`, `SPEC_TRACE.md`, `GRAMMAR.md`, `COMPATIBILITY.md`,
`V0_SUPPORT.md`, and `tools/cross_repo_language_contract.json` fixture anchors.
Changed paths outside the sealed CrossTL frontend source list are reported as
unmapped inputs so reviewers can triage them manually instead of treating them
as shared language facts.

The cross-repo contract checker can also emit a non-mutating drift report:

```sh
python3 tools/check_cross_repo_language_contract.py \
  --translator-root /path/to/CrossGL-Translator \
  --cglc /path/to/cglc \
  --report /tmp/crossgl-language-contract-report.json
```

`--report` records the spec snapshot, repository roots, fixture grouping and
classification counts, intentional fixture exclusions, source provenance for
the sealed CrossTL frontend files plus accepted/negative fixture inputs, dry-run
hash drift counts, and the `cglc` executable used. It does not update
`tools/cross_repo_language_contract.json`; use `--update-manifest` only after an
intentional language or HIR contract change has been reviewed.
