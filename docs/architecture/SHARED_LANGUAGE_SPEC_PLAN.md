# Shared CrossGL Language Specification Plan

CrossGL-Compiler and CrossGL-Translator must share one language specification.
The compiler is allowed to become stricter than the translator where native
compilation requires stronger semantics, but those differences must be tracked
as spec work and CrossTL frontend work, not as accidental dialect drift.

## Source of Truth

The initial spec should be extracted from CrossTL because CrossTL is the
existing CrossGL parser and interchange implementation.

Primary extraction sources:

- `CrossGL-Translator/crosstl/translator/lexer.py`: tokens, keywords,
  operators, literals, type spellings, resource spellings, and annotations.
- `CrossGL-Translator/crosstl/translator/parser.py`: grammar accepted by the
  current CrossGL frontend.
- `CrossGL-Translator/crosstl/translator/ast.py`: canonical translation AST and
  stage/type/resource concepts.
- `CrossGL-Translator/crosstl/translator/validation.py`: semantic validation
  already enforced during translation.
- `CrossGL-Translator/examples`: accepted source examples.
- `CrossGL-Compiler/tools/cross_repo_language_contract.json`: shared fixtures
  that already pin compiler HIR and translator AST compatibility.

The extracted spec becomes the contract both repositories work against.

## Extraction Deliverables

The first spec extraction batch should produce:

- Lexical grammar: comments, identifiers, literals, reserved words, operators,
  punctuation, attributes, and layout syntax.
- Module grammar: shader declarations, imports, preprocessors, structs,
  constants, cbuffers, stages, functions, and global declarations.
- Type grammar: scalar, vector, matrix, array, pointer/reference, named,
  generic, texture, sampler, storage image, buffer, and shared memory forms.
- Statement grammar: declarations, assignments, expression statements, returns,
  branches, loops, switch/match forms, break/continue/discard, and raw fallback
  forms.
- Expression grammar: literals, identifiers, constructors, calls, member
  access, indexing, unary/binary/ternary operators, ranges, patterns, and
  texture/image intrinsics.
- AST schema: stable node names, fields, required invariants, and source
  location expectations.
- Semantic baseline: current CrossTL validation plus explicit gaps where the
  compiler needs stronger native-compiler semantics.

## Compatibility Policy

Every language change should follow this sequence:

1. Update the shared spec.
2. Update CrossTL lexer/parser/AST/validation if the accepted language changes.
3. Update CrossGL-Compiler frontend/HIR/diagnostics.
4. Add or update cross-repo language contract fixtures.
5. Add compiler support-matrix evidence or planned-failure diagnostics.

If the compiler rejects a source form that CrossTL accepts, the rejection must
be documented as one of:

- `spec.unsupported-for-native-v0`: accepted language, not yet native compiler
  support.
- `spec.deprecated`: accepted for compatibility but no longer preferred.
- `spec.error`: CrossTL should be changed to reject or diagnose it.
- `target.unsupported`: legal language, unsupported on the selected backend.

## Shared Spec Artifacts

Recommended repository layout:

```text
CrossGL-Compiler/docs/language/
  SPEC.md
  GRAMMAR.md
  AST_SCHEMA.md
  SEMANTICS.md
  COMPATIBILITY.md

CrossGL-Translator/docs/source/language/
  SPEC.md or generated link/copy to the same versioned content
```

The exact storage can change, but both projects must expose the same versioned
spec. Long term, the spec may move to its own package or be generated into both
repositories.

## CrossTL Frontend Evolution

CrossTL's frontend can and should change when the compiler design requires a
stronger language. Examples:

- Tighten ambiguous grammar.
- Add source locations where compiler diagnostics need them.
- Split syntax-level AST nodes from semantic annotations.
- Add validation hooks for shared type/resource rules.
- Mark compatibility-only constructs as deprecated or feature-gated.

Those changes should remain backwards-aware because CrossTL is also a
translator. The compiler can reject native-unsupported constructs while CrossTL
continues to translate them if the shared spec says they remain legal.

## Compiler Integration

CrossGL-Compiler should consume the shared spec through tests and contracts:

- Cross-repo fixture hashes for accepted programs.
- Negative fixtures for syntax or semantic errors.
- HIR source-map checks that prove compiler diagnostics point to spec-defined
  source constructs.
- Support-matrix rows that map language features to target capabilities.
- Tooling that detects when CrossTL parser behavior changes without a spec or
  contract update.

This keeps CrossGL a single language with two coordinated implementations:
CrossTL as translator/interchange frontend, and CrossGL-Compiler as native
compiler/package producer.

The language contract checker's `--report <path>` option is the lightweight
drift-audit artifact for this policy. It writes JSON with the shared spec
snapshot id/path/hash, CrossGL-Translator and CrossGL-Compiler roots, accepted
and negative fixture counts by group/classification, intentional exclusions with
reasons, dry-run hash drift totals, and the `cglc` executable used. The option
is intentionally non-invasive: default checker behavior is unchanged, and
manifest hashes are rewritten only when `--update-manifest` is supplied.

The report-only `docs/language/SPEC_TRACE.md` audit is the prose traceability
gate for the same source-of-truth policy. Its checked coverage checklist maps
the sealed CrossTL lexical surface, grammar-production families, AST node
inventory, validation hooks, compatibility classifications, source-file seals,
and contract fixture groups back to `docs/language/SPEC_INDEX.md`,
`docs/language/COMPATIBILITY.md`, and
`tools/cross_repo_language_contract.json`. Changes to those facets should fail
`tools/check_language_spec_trace.py --root .` until the shared spec artifacts
are reviewed, without authorizing any parser or CrossTL behavior change.
The same checker can emit `--anchor-report` JSON for one or more changed
CrossTL frontend source paths, giving reviewers a non-mutating map from the
changed source file to affected snapshot refs, prose anchors, compatibility
buckets, and fixture groups.

The report-only `tools/check_language_spec_index.py --root .` gate keeps the
generated spec index, `tools/cross_repo_language_spec.json`, and
`docs/language/V0_SUPPORT.md` tied to the same CrossTL snapshot and
cross-repo language contract. It rejects stale feature-map snapshot seals,
missing accepted contract feature groups, stale negative-case counts, unknown
`feature:<group>` support tokens, and missing v0 support references to the
contract's negative compatibility classifications.

The report-only CrossTL AST schema contract v1 is checked by
`tools/check_language_ast_schema_contract.py --root .`. It pins
`docs/language/AST_SCHEMA.md` to `/ast/classes`, `/ast/classFields`, AST
node-family arrays, enum values, unsupported-node guidance, and source-location
non-claims in the sealed CrossTL snapshot. This is a report-only handoff for
shared spec formalization without changing compiler parser behavior, CrossTL
sources, HIR lowering, or native compiler support claims.

The report-only source-location requirements contract is checked by
`tools/check_language_source_location_requirements.py --root .`. It keeps the
CrossTL `source_location` field inventory separate from native source-map and
diagnostic-span evidence, and native source-map and diagnostic-span support
claims require separate evidence before becoming shared language support claims.
The contract does not authorize parser recovery, HIR lowering, diagnostics,
package output, fixture hashes, or compiler behavior changes.

The report-only CrossTL grammar surface contract v1 is checked by
`tools/check_language_grammar_surface_contract.py --root .`. It pins
`docs/language/GRAMMAR.md` to the sealed CrossTL snapshot inventory for source
files, lexical tokens, keywords, literal/skip tokens, stages, types,
qualifiers, and resources without changing compiler parser behavior. Real
grammar-production extraction remains a report-only gap; AST facts stay with
the AST contract, while validation metadata and intrinsics stay with later
semantic-baseline work.

The report-only semantic-baseline checklist is checked by
`tools/check_language_compatibility.py --root .`. It keeps the CrossTL
validation/source semantics inventory mapped to exactly one native-v0 owner
bucket before implementation work starts: language-level shared-spec gaps use
`compat.language-unsupported-native-v0`, native compiler frontend subset gaps
use `compat.frontend-unsupported-native-v0`, and target/package legalization
gaps use `compat.target-legalization-unsupported`. The checklist is a planning
gate only; it does not authorize parser, CrossTL, HIR, backend, fixture-hash,
target-contract, or package behavior changes.

PR720-style frontend definition updates must also complete the checked
`pr720-style-source-seal-handoff` in `docs/language/DRIFT_REVIEW.md`. That
machine-readable handoff records the required flow into the CrossTL snapshot
and generated spec docs, the compatibility/conformance/native-v0 support
buckets, and the cross-repo accepted or negative fixture contract. The
`tools/check_language_drift_review.py --root .` self-test mutates that handoff
so missing snapshot, support-bucket, or contract lanes fail without changing
compiler syntax or conformance behavior.
