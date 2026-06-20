# CrossTL Language Change Policy

This is a report-only policy for CrossTL language changes after the v0
snapshot. It explains how lexer, parser, AST, and validation changes in the
CrossTL frontend become shared CrossGL language facts. It does not authorize
accepted syntax changes, parser behavior changes, CrossTL checkout edits,
compiler frontend behavior changes, generated language-doc edits, or new
conformance expectations.

Agents must stop before inventing a compiler-only dialect. A source form is
not shared just because the native compiler can parse it, and a source form is
not native-supported just because it appears in the CrossTL AST inventory.

<!-- crossgl-language-change-policy-v1:begin -->
```json
{
  "schema": 1,
  "source_seal": {
    "snapshot_path": "docs/language/crosstl-frontend-language-spec-v0.json",
    "snapshot_sha256": "86b133c7da54ac206972d452a9a48419dccb00420875e06cc1a51cbbb0109d35",
    "snapshot_schema_version": 0,
    "generated_spec_docs": [
      "docs/language/SPEC.md",
      "docs/language/SPEC_INDEX.md"
    ],
    "compatibility_path": "docs/language/COMPATIBILITY.md",
    "contract_manifest_path": "tools/cross_repo_language_contract.json",
    "support_contract_path": "docs/language/V0_SUPPORT.md"
  },
  "flow_steps": [
    "crosstl-change-intake",
    "snapshot-refresh",
    "generated-spec-docs",
    "compatibility-ledger",
    "cross-repo-contract",
    "native-support-buckets",
    "report-only-closeout"
  ],
  "native_support_buckets": [
    "cross-tl-inventory-only",
    "shared-positive-contract",
    "native-v0-supported",
    "compatibility-only",
    "language-error",
    "target-limited",
    "planned-no-claim"
  ],
  "stop_conditions": [
    "compiler-only-dialect",
    "accepted-syntax-change",
    "parser-or-ast-behavior-change",
    "generated-doc-manual-edit",
    "missing-compatibility-ledger-entry",
    "missing-cross-repo-contract-evidence",
    "native-support-claim-without-evidence",
    "requires-crosstl-checkout-edit"
  ],
  "change_requirements": [
    {
      "id": "syntax-tightening",
      "required_classification": "spec.error",
      "required_evidence": [
        "compatibility-ledger-row",
        "negative-contract-or-diagnostic-fixture",
        "v0-support-planned-or-unsupported-row"
      ],
      "stop_condition": "accepted-syntax-change",
      "affected_docs": [
        "docs/language/COMPATIBILITY.md",
        "docs/language/V0_SUPPORT.md",
        "docs/language/DRIFT_REVIEW.md"
      ]
    },
    {
      "id": "deprecation",
      "required_classification": "spec.deprecated",
      "required_evidence": [
        "canonical-spelling",
        "compatibility-ledger-row",
        "no-new-shared-positive-fixture"
      ],
      "stop_condition": "missing-compatibility-ledger-entry",
      "affected_docs": [
        "docs/language/COMPATIBILITY.md",
        "docs/language/V0_SUPPORT.md"
      ]
    },
    {
      "id": "source-location-requirements",
      "required_classification": "report-only",
      "required_evidence": [
        "drift-review-source-location-note",
        "ast-schema-source-location-note",
        "native-source-map-evidence-before-support-claim"
      ],
      "stop_condition": "parser-or-ast-behavior-change",
      "affected_docs": [
        "docs/language/AST_SCHEMA.md",
        "docs/language/DRIFT_REVIEW.md",
        "docs/language/V0_SUPPORT.md"
      ]
    }
  ]
}
```
<!-- crossgl-language-change-policy-v1:end -->

## Policy Scope

Use this policy when a proposed or observed CrossTL change affects lexer token
names, keyword spellings, parser productions, AST node classes or fields,
validation metadata, source-location expectations, examples, or fixtures.

This page is a coordination artifact. It can ask for a snapshot refresh,
compatibility-ledger decision, generated-doc regeneration, or cross-repo
contract update, but it cannot perform or imply those behavior changes.
`docs/language/DRIFT_REVIEW.md` remains the checklist for reviewing a concrete
drift report; this policy defines the order that turns intentional CrossTL
changes into shared spec and native-support claims.
The drift checklist classifies each report as `informational`,
`requires-shared-spec-update`, `requires-crosstl-frontend-change`, or
`requires-cross-repo-contract-fixture-update` before any owner starts an
implementation slice.
When intake names one of the sealed CrossTL frontend source files, use the
drift checklist `source_review_map` to attach impacted `facet.*` entries,
reviewer/owner buckets, required local commands, and stop conditions to the
handoff before requesting a behavior-owning slice.
Parser and AST drift also must use `parser-drift-review` or
`ast-drift-review` from the drift checklist before any parser, AST,
source-location, fixture, or accepted-syntax behavior change is proposed.

## Change Flow

| Step id | Required input | Report-only output |
| --- | --- | --- |
| `crosstl-change-intake` | A named CrossTL lexer, parser, AST, validation, example, or fixture change. | Record the CrossTL source path, observed source form, affected snapshot category, and whether the change is intentional or drift. Do not patch CrossGL-Compiler to compensate first. |
| `snapshot-refresh` | `tools/extract_crosstl_language_spec.py` run against the CrossTL checkout. | Confirm whether `docs/language/crosstl-frontend-language-spec-v0.json` is current. If the snapshot would change, report the new hash and affected categories instead of hand-editing it. |
| `generated-spec-docs` | A reviewed snapshot or contract-manifest change. | Run `tools/generate_crosstl_language_spec_docs.py --check`. If `docs/language/SPEC.md` or `docs/language/SPEC_INDEX.md` is stale, report the regeneration command; do not edit generated docs manually. |
| `compatibility-ledger` | A source-form delta from the snapshot, compiler frontend, or validation layer. | Assign one `docs/language/COMPATIBILITY.md` classification: `spec.unsupported-for-native-v0`, `spec.deprecated`, `spec.error`, or `target.unsupported`. If none fits, stop for a ledger decision. |
| `cross-repo-contract` | A source form with fixture or conformance impact. | Use `tools/check_cross_repo_language_contract.py --report` to describe `accepted_contracts`, `negative_contracts`, source hashes, CrossTL AST hashes, compiler HIR hashes, and fixture grouping impact. Manifest updates require a separate intentional behavior-owning slice. |
| `native-support-buckets` | Compatibility classification plus fixture, HIR, target, package, or diagnostic evidence. | Place the source form in exactly one native compiler support bucket before claiming support or planning implementation. |
| `report-only-closeout` | Completed reports from the preceding steps. | Summarize requested owner action, stop condition, or evidence gap. Do not change accepted syntax, parser behavior, generated docs, conformance expectations, or compiler support claims in the same report-only slice. |

## Shared Artifact Contract

The shared language inventory starts at
`docs/language/crosstl-frontend-language-spec-v0.json` and is extracted from the
CrossTL frontend by `tools/extract_crosstl_language_spec.py`. The prose entry
points `docs/language/SPEC.md` and `docs/language/SPEC_INDEX.md` are generated
from that snapshot and `tools/cross_repo_language_contract.json` by
`tools/generate_crosstl_language_spec_docs.py`.

`docs/language/COMPATIBILITY.md` is the ledger that separates CrossTL
acceptance from native-v0 support. `tools/check_cross_repo_language_contract.py`
is the cross-repo fixture contract tool; its manifest records
`accepted_contracts` and `negative_contracts`. `docs/language/V0_SUPPORT.md`
is the user-facing support contract and must cite concrete evidence before a
bucket becomes native-supported.

Hand-written pages such as `docs/language/GRAMMAR.md`,
`docs/language/AST_SCHEMA.md`, and `docs/language/SEMANTICS.md` may explain the
shared facts, but they do not override the snapshot, generated docs,
compatibility ledger, cross-repo contract, or support evidence.
`docs/language/README.md` is the directory-level entry point and must keep the
checked policy-slice ids visible for reviewers.

## Native Compiler Support Buckets

| Bucket id | Meaning | Minimum evidence before use |
| --- | --- | --- |
| `cross-tl-inventory-only` | CrossTL knows about the token, production, AST node, validation fact, or example, but the native compiler has no support claim. | Snapshot category in `docs/language/SPEC_INDEX.md` and no native support row. |
| `shared-positive-contract` | Both CrossTL and the compiler accept the source form at the shared fixture level. This is parser/HIR compatibility, not a package claim by itself. | `accepted_contracts` group with stable CrossTL AST and compiler HIR hashes. |
| `native-v0-supported` | The source form is part of the native-v0 compiler support contract for named commands and targets. | `docs/language/V0_SUPPORT.md` row plus CTest, HIR, package, conformance, or target evidence. |
| `compatibility-only` | CrossTL accepts the form, but native-v0 does not claim support or treats it as legacy. | `spec.unsupported-for-native-v0` or `spec.deprecated` ledger row and either exclusion, planned diagnostic, or compatibility fixture evidence. |
| `language-error` | The source form is invalid shared CrossGL and should be rejected before target emission. | `spec.error` ledger row plus `negative_contracts` or focused diagnostic fixture evidence. |
| `target-limited` | The frontend accepts the source form, but at least one target must reject or downgrade it. | `target.unsupported` ledger row plus target/package planned-failure or capability evidence. |
| `planned-no-claim` | The source form is future work only. It may be named in a roadmap or backlog but has no acceptance or support effect. | Backlog or report reference that does not alter fixtures, generated docs, conformance, or compiler behavior. |

## Change Requirement Slices

These checked slices pin the report-only policy for future CrossTL/CrossGL
language evolution. They do not change accepted syntax, parser behavior,
CrossTL behavior, compiler parser behavior, or conformance expectations.

| Requirement id | Trigger | Required classification | Required evidence | Stop condition |
| --- | --- | --- | --- | --- |
| `syntax-tightening` | A previously tolerated source form becomes invalid shared CrossGL, or a diagnostic boundary narrows accepted source. | `spec.error` in a `compatibility-ledger-row`. | `negative-contract-or-diagnostic-fixture` plus a `v0-support-planned-or-unsupported-row` before any support text changes. | `accepted-syntax-change` |
| `deprecation` | A spelling remains visible only for compatibility while a canonical spelling is preferred. | `spec.deprecated` in a `compatibility-ledger-row`. | `canonical-spelling` plus `no-new-shared-positive-fixture` for the deprecated form. | `missing-compatibility-ledger-entry` |
| `source-location-requirements` | CrossTL AST/source-location fields, native source maps, or diagnostic ranges become part of the handoff. | `report-only`; source-location inventory is not a support claim by itself. | `drift-review-source-location-note`, `ast-schema-source-location-note`, and `native-source-map-evidence-before-support-claim`. | `parser-or-ast-behavior-change` |

Parser/AST drift has a checked report-only review policy in
`docs/language/DRIFT_REVIEW.md`. The `parser-drift-review` and
`ast-drift-review` checklist entries require `crosstl-snapshot-hash`,
`cross-repo-fixture-impact`, `source-location-impact`,
`compatibility-bucket`, and `stop-condition-before-behavior-change` evidence
before a behavior-owning slice may change accepted syntax, parser recovery, AST
shape, fixture expectations, source-location propagation, or conformance
behavior.

PR #720-style CrossTL references that change a sealed frontend file must also
complete the checked `pr720-style-source-seal-handoff` in
`docs/language/DRIFT_REVIEW.md`. That handoff requires a
`source-seal-hash-comparison`, drift-class assignment for lexer/parser/AST or
validation movement, a `compatibility-bucket-assignment`, and a
`cross-repo-fixture-update-decision` before any snapshot regeneration,
contract manifest update, or native compiler behavior change is proposed. Its
checked `handoff_flow` also records the three required lanes: snapshot refresh
and generated-doc regeneration, compatibility/conformance/support bucket
routing, and accepted or negative cross-repo fixture evidence.
If the source form has no compatibility row or fixture lane, the report must
stop on `missing-compatibility-bucket` or `missing-contract-evidence` rather
than editing accepted syntax.

## Stop Conditions

Stop the task and report the blocker when any condition applies.

| Stop id | Stop when | Required report |
| --- | --- | --- |
| `compiler-only-dialect` | A compiler change, fixture, prose page, or support claim would introduce syntax, semantics, AST shape, validation behavior, or conformance expectations that cannot be traced to CrossTL, the shared snapshot, the compatibility ledger, and the contract manifest. | Name the proposed compiler-only fact and the missing shared-spec path. |
| `accepted-syntax-change` | The next step would change accepted syntax, keyword treatment, parser recovery, AST construction, validation diagnostics, or conformance expectations. | State the source form and hand it to a behavior-owning language-change slice. |
| `parser-or-ast-behavior-change` | Completing the report requires editing `src/Frontend`, CrossTL parser/AST code, validation code, or generated HIR behavior. | Identify the required behavior change and stop before patching it. |
| `generated-doc-manual-edit` | `docs/language/SPEC.md` or `docs/language/SPEC_INDEX.md` would need a manual edit. | Report the stale artifact and the `tools/generate_crosstl_language_spec_docs.py --check` result. |
| `missing-compatibility-ledger-entry` | The source form cannot be assigned to `spec.unsupported-for-native-v0`, `spec.deprecated`, `spec.error`, or `target.unsupported`. | Ask for a `docs/language/COMPATIBILITY.md` row or classification decision. |
| `missing-cross-repo-contract-evidence` | No `accepted_contracts` group, `negative_contracts` group, fixture exclusion, diagnostic fixture, or planned contract update pins the source form. | Name the fixture or contract evidence needed before support can move. |
| `native-support-claim-without-evidence` | A native support claim lacks fixture, HIR, target, package, CTest, conformance, or diagnostic evidence. | Keep the form outside `native-v0-supported` and list the missing evidence lane. |
| `requires-crosstl-checkout-edit` | The report cannot be accurate without editing the CrossTL checkout. | Name the CrossTL file or behavior and return it to the CrossTL owner. |

## Report Template

A language-change report should include:

1. Source seal: snapshot path, SHA-256, and CrossTL source path if known.
2. Change flow step: one id from `crosstl-change-intake`,
   `snapshot-refresh`, `generated-spec-docs`, `compatibility-ledger`,
   `cross-repo-contract`, `native-support-buckets`, or
   `report-only-closeout`.
3. Affected artifact: snapshot category, generated doc, compatibility row,
   contract group, or support bucket.
4. Native support bucket: one bucket id from this policy, with evidence.
5. Stop condition: one stop id when the report cannot proceed safely.
6. Requested owner action: regenerate, add ledger row, add fixture evidence,
   run contract report, or open a behavior-owning implementation slice.

Validate this policy manifest and references with
`tools/check_language_change_policy.py`:

```sh
python3 tools/check_language_change_policy.py --root .
```

Validate the concrete drift-review checklist with
`python3 tools/check_language_drift_review.py --root .` before using a drift
report as a handoff artifact.
