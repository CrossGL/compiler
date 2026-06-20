# CrossGL Language Spec Trace Audit

This report-only audit maps sealed CrossTL snapshot/source evidence to the v0
language support and compatibility buckets used by the compiler docs. It is a
review gate only: it does not authorize parser, compiler, backend, generated
snapshot, or CrossGL-Translator changes.

Runtime package-loader admission, runtime compatibility checks, and native
artifact selection are not language trace inputs. Trace entries must remain
grounded in the CrossTL frontend snapshot and shared language contract.
The runtime architecture/package docs own loader admission and native artifact
selection.

<!-- crossgl-language-spec-trace-v1:begin -->
```json
{
  "bucket_order": [
    "accepted-source",
    "package-supported",
    "compatibility-only",
    "compat.language-unsupported-native-v0",
    "compat.frontend-unsupported-native-v0",
    "compat.target-legalization-unsupported",
    "compat.deprecated-crosstl-spelling",
    "compat.true-spec-error"
  ],
  "kind": "crossgl-language-spec-trace",
  "required_trace_ids": [
    "trace.accepted.modules-stages-entry",
    "trace.package.resources-storage-images",
    "trace.compatibility.crosstl-examples-backend-policy",
    "trace.unsupported.extended-stages",
    "trace.unsupported.fn-style",
    "trace.unsupported.pattern-control",
    "trace.frontend.metadata-aliases",
    "trace.accepted.float-literal-forms",
    "trace.target.resource-arrays",
    "trace.deprecated.kernel-alias",
    "trace.error.no-stage-or-entry"
  ],
  "schema": 1,
  "source_seal": {
    "checker_path": "tools/check_language_spec_trace.py",
    "compatibility_path": "docs/language/COMPATIBILITY.md",
    "contract_manifest_path": "tools/cross_repo_language_contract.json",
    "contract_manifest_snapshot_sha256": "86b133c7da54ac206972d452a9a48419dccb00420875e06cc1a51cbbb0109d35",
    "feature_spec_path": "tools/cross_repo_language_spec.json",
    "snapshot_path": "docs/language/crosstl-frontend-language-spec-v0.json",
    "snapshot_schema_version": 0,
    "snapshot_sha256": "86b133c7da54ac206972d452a9a48419dccb00420875e06cc1a51cbbb0109d35",
    "source_files": [
      {
        "path": "crosstl/translator/lexer.py",
        "sha256": "e5c2c18870bcd14eecb4b2e1db301d9f8e98af3a8a51acbf4c46b84df9548986"
      },
      {
        "path": "crosstl/translator/parser.py",
        "sha256": "2a30ce24a4f5acf48025efbaef780c06f2bfc71de299ddd91b6cf4d02485f2ca"
      },
      {
        "path": "crosstl/translator/ast.py",
        "sha256": "9ce23e8e1612235a46241aa7ebc3bd4ae9912ef38e9a50a5f9384060955701c0"
      },
      {
        "path": "crosstl/translator/validation.py",
        "sha256": "a05fa68e4dd910b6dc05be44e0d5293b6887b6eca2b29218f27e9a08bdf5ddf2"
      }
    ],
    "spec_index_path": "docs/language/SPEC_INDEX.md",
    "support_contract_path": "docs/language/V0_SUPPORT.md"
  },
  "traces": [
    {
      "bucket": "accepted-source",
      "compatibility_classification": null,
      "compatibility_id": null,
      "contract_groups": [
        "accepted_contracts.module_stages_and_entry_points"
      ],
      "feature_groups": [
        "module_stages_and_entry_points"
      ],
      "id": "trace.accepted.modules-stages-entry",
      "snapshot_refs": [
        "/language/stages",
        "/ast/enums/ShaderStage"
      ],
      "source_files": [
        "crosstl/translator/lexer.py",
        "crosstl/translator/parser.py",
        "crosstl/translator/ast.py"
      ],
      "spec_index_id": "grammar.stages",
      "support_sections": [
        "Accepted Source Forms"
      ]
    },
    {
      "bucket": "package-supported",
      "compatibility_classification": null,
      "compatibility_id": null,
      "contract_groups": [
        "accepted_contracts.resources_layouts_and_storage"
      ],
      "feature_groups": [
        "resources_layouts_and_storage"
      ],
      "id": "trace.package.resources-storage-images",
      "snapshot_refs": [
        "/language/resources",
        "/validation/metadata"
      ],
      "source_files": [
        "crosstl/translator/lexer.py",
        "crosstl/translator/parser.py",
        "crosstl/translator/validation.py"
      ],
      "spec_index_id": "grammar.resources",
      "support_sections": [
        "v0 Package-Supported Subset"
      ]
    },
    {
      "bucket": "compatibility-only",
      "compatibility_classification": null,
      "compatibility_id": null,
      "contract_groups": [
        "accepted_contracts.crosstl_examples_and_backend_policy"
      ],
      "feature_groups": [
        "crosstl_examples_and_backend_policy"
      ],
      "id": "trace.compatibility.crosstl-examples-backend-policy",
      "snapshot_refs": [
        "/notes",
        "/source/files"
      ],
      "source_files": [
        "crosstl/translator/lexer.py",
        "crosstl/translator/parser.py",
        "crosstl/translator/ast.py",
        "crosstl/translator/validation.py"
      ],
      "spec_index_id": "provenance.source-seal",
      "support_sections": [
        "Compatibility-Only HIR and Raw Forms"
      ]
    },
    {
      "bucket": "compat.language-unsupported-native-v0",
      "compatibility_classification": "spec.unsupported-for-native-v0",
      "compatibility_id": "stage.extended-graphics",
      "contract_groups": [
        "negative_contracts.spec_unsupported_for_native_v0"
      ],
      "feature_groups": [
        "module_stages_and_entry_points"
      ],
      "id": "trace.unsupported.extended-stages",
      "snapshot_refs": [
        "/language/stages"
      ],
      "source_files": [
        "crosstl/translator/lexer.py",
        "crosstl/translator/parser.py",
        "crosstl/translator/ast.py"
      ],
      "spec_index_id": "grammar.stages",
      "support_sections": [
        "Planned or Unsupported Forms"
      ]
    },
    {
      "bucket": "compat.language-unsupported-native-v0",
      "compatibility_classification": "spec.unsupported-for-native-v0",
      "compatibility_id": "decl.fn-style",
      "contract_groups": [
        "negative_contracts.spec_unsupported_for_native_v0"
      ],
      "feature_groups": [
        "types_structs_arrays_and_constants"
      ],
      "id": "trace.unsupported.fn-style",
      "snapshot_refs": [
        "/ast/classes"
      ],
      "source_files": [
        "crosstl/translator/ast.py"
      ],
      "spec_index_id": "ast.class-inventory",
      "support_sections": [
        "Planned or Unsupported Forms"
      ]
    },
    {
      "bucket": "compat.language-unsupported-native-v0",
      "compatibility_classification": "spec.unsupported-for-native-v0",
      "compatibility_id": "stmt.pattern-control",
      "contract_groups": [
        "negative_contracts.spec_unsupported_for_native_v0"
      ],
      "feature_groups": [
        "control_flow_and_statements"
      ],
      "id": "trace.unsupported.pattern-control",
      "snapshot_refs": [
        "/ast/statementNodes",
        "/ast/classes"
      ],
      "source_files": [
        "crosstl/translator/ast.py"
      ],
      "spec_index_id": "ast.class-inventory",
      "support_sections": [
        "Planned or Unsupported Forms"
      ]
    },
    {
      "bucket": "compat.frontend-unsupported-native-v0",
      "compatibility_classification": "spec.unsupported-for-native-v0",
      "compatibility_id": "resource.metadata-aliases",
      "contract_groups": [
        "negative_contracts.spec_unsupported_for_native_v0"
      ],
      "feature_groups": [
        "resources_layouts_and_storage"
      ],
      "id": "trace.frontend.metadata-aliases",
      "snapshot_refs": [
        "/validation/metadata"
      ],
      "source_files": [
        "crosstl/translator/validation.py"
      ],
      "spec_index_id": "semantics.metadata-and-layout",
      "support_sections": [
        "Planned or Unsupported Forms"
      ]
    },
    {
      "bucket": "accepted-source",
      "compatibility_classification": null,
      "compatibility_id": null,
      "contract_groups": [
        "accepted_contracts.expressions_operators_and_intrinsics"
      ],
      "feature_groups": [
        "expressions_operators_and_intrinsics"
      ],
      "id": "trace.accepted.float-literal-forms",
      "snapshot_refs": [
        "/lexical/tokens"
      ],
      "source_files": [
        "crosstl/translator/lexer.py"
      ],
      "spec_index_id": "lexical.tokens",
      "support_sections": [
        "Accepted Source Forms"
      ]
    },
    {
      "bucket": "compat.target-legalization-unsupported",
      "compatibility_classification": "target.unsupported",
      "compatibility_id": "target.resource-arrays",
      "contract_groups": [
        "accepted_contracts.crosstl_examples_and_backend_policy"
      ],
      "feature_groups": [
        "crosstl_examples_and_backend_policy"
      ],
      "id": "trace.target.resource-arrays",
      "snapshot_refs": [
        "/language/resources"
      ],
      "source_files": [
        "crosstl/translator/parser.py",
        "crosstl/translator/validation.py"
      ],
      "spec_index_id": "grammar.resources",
      "support_sections": [
        "Planned or Unsupported Forms"
      ]
    },
    {
      "bucket": "compat.deprecated-crosstl-spelling",
      "compatibility_classification": "spec.deprecated",
      "compatibility_id": "stage.kernel-alias",
      "contract_groups": [
        "accepted_contracts.module_stages_and_entry_points"
      ],
      "feature_groups": [
        "module_stages_and_entry_points"
      ],
      "id": "trace.deprecated.kernel-alias",
      "snapshot_refs": [
        "/language/stages"
      ],
      "source_files": [
        "crosstl/translator/lexer.py",
        "crosstl/translator/parser.py"
      ],
      "spec_index_id": "grammar.stages",
      "support_sections": [
        "Planned or Unsupported Forms"
      ]
    },
    {
      "bucket": "compat.true-spec-error",
      "compatibility_classification": "spec.error",
      "compatibility_id": "sema.no-stage-or-entry",
      "contract_groups": [
        "negative_contracts.spec_error"
      ],
      "feature_groups": [
        "module_stages_and_entry_points"
      ],
      "id": "trace.error.no-stage-or-entry",
      "snapshot_refs": [
        "/language/stages"
      ],
      "source_files": [
        "crosstl/translator/parser.py",
        "crosstl/translator/ast.py"
      ],
      "spec_index_id": "grammar.stages",
      "support_sections": [
        "Planned or Unsupported Forms"
      ]
    }
  ]
}
```
<!-- crossgl-language-spec-trace-v1:end -->

## Reading the Trace

Each row starts from one generated `docs/language/SPEC_INDEX.md` category, names
the exact JSON pointers in
`docs/language/crosstl-frontend-language-spec-v0.json`, and ties those facts to
CrossTL source files sealed in the snapshot. The final bucket is either a v0
support bucket (`accepted-source`, `package-supported`, or
`compatibility-only`) or one of the report-only compatibility buckets from
`docs/language/COMPATIBILITY.md`. The checker also resolves support sections in
`docs/language/V0_SUPPORT.md`, feature groups in
`tools/cross_repo_language_spec.json`, and fixture groups in
`tools/cross_repo_language_contract.json`.

The human grammar guide in `docs/language/GRAMMAR.md` carries a checked
grammar-claim trace map. It keeps CrossTL frontend extraction evidence separate
from compiler-v0 subset evidence for each grammar section, including
`fixture-count:*` and `case-count:*` tokens derived from
`tools/cross_repo_language_contract.json`.

The single-source traceability checklist below is the stable audit surface for
the shared language contract. It makes the CrossTL-derived snapshot the root for
lexical grammar, grammar-production families, AST node inventory, semantic
checks, compatibility classifications, source-file provenance, and contract
fixture coverage. A row may cite a category even when the row is report-only;
that citation records where drift must be reviewed before any parser or
translator behavior changes.

Validate the trace with `tools/check_language_spec_trace.py`:

```sh
python3 tools/check_language_spec_trace.py --root .
```

## Traceability Coverage Checklist

| Facet id | Spec index ids | Snapshot refs | CrossTL source evidence | Compatibility classifications | Contract fixture groups |
| --- | --- | --- | --- | --- | --- |
| `facet.lexical-grammar` | `lexical.tokens`, `lexical.keywords`, `lexical.literals-and-skips` | `/lexical/tokens`, `/lexical/keywords`, `/lexical/literalTokens`, `/lexical/skipTokens` | `crosstl/translator/lexer.py@e5c2c18870bc` | none | `accepted_contracts.control_flow_and_statements`, `accepted_contracts.module_stages_and_entry_points` |
| `facet.grammar-productions` | `grammar.stages`, `grammar.types`, `grammar.qualifiers`, `grammar.resources` | `/language/stages`, `/language/types`, `/language/qualifiers`, `/language/resources` | `crosstl/translator/lexer.py@e5c2c18870bc`, `crosstl/translator/parser.py@2a30ce24a4f5`, `crosstl/translator/ast.py@9ce23e8e1612`, `crosstl/translator/validation.py@a05fa68e4dd9` | none | `accepted_contracts.control_flow_and_statements`, `accepted_contracts.descriptor_indexing_and_nonuniform`, `accepted_contracts.expressions_operators_and_intrinsics`, `accepted_contracts.module_stages_and_entry_points`, `accepted_contracts.resources_layouts_and_storage`, `accepted_contracts.textures_samplers_images_and_intrinsics`, `accepted_contracts.types_structs_arrays_and_constants` |
| `facet.ast-nodes` | `ast.class-inventory` | `/ast/classes`, `/ast/classFields`, `/ast/typeNodes`, `/ast/statementNodes`, `/ast/expressionNodes`, `/ast/enums` | `crosstl/translator/ast.py@9ce23e8e1612` | none | `accepted_contracts.control_flow_and_statements`, `accepted_contracts.expressions_operators_and_intrinsics`, `accepted_contracts.module_stages_and_entry_points`, `accepted_contracts.types_structs_arrays_and_constants` |
| `facet.semantic-checks` | `semantics.metadata-and-layout`, `semantics.intrinsics` | `/validation/metadata`, `/validation/stageLayout`, `/language/intrinsics` | `crosstl/translator/parser.py@2a30ce24a4f5`, `crosstl/translator/validation.py@a05fa68e4dd9` | none | `accepted_contracts.expressions_operators_and_intrinsics`, `accepted_contracts.module_stages_and_entry_points`, `accepted_contracts.resources_layouts_and_storage`, `accepted_contracts.textures_samplers_images_and_intrinsics` |
| `facet.compatibility-classifications` | `provenance.source-seal` | `/notes`, `/source/files` | `crosstl/translator/lexer.py@e5c2c18870bc`, `crosstl/translator/parser.py@2a30ce24a4f5`, `crosstl/translator/ast.py@9ce23e8e1612`, `crosstl/translator/validation.py@a05fa68e4dd9` | `spec.deprecated`, `spec.error`, `spec.unsupported-for-native-v0`, `target.unsupported` | `accepted_contracts.crosstl_examples_and_backend_policy`, `negative_contracts.spec_error`, `negative_contracts.spec_unsupported_for_native_v0` |
| `facet.source-provenance` | `provenance.source-seal` | `/source/files`, `/source/extraction` | `crosstl/translator/lexer.py@e5c2c18870bc`, `crosstl/translator/parser.py@2a30ce24a4f5`, `crosstl/translator/ast.py@9ce23e8e1612`, `crosstl/translator/validation.py@a05fa68e4dd9` | none | `accepted_contracts.crosstl_examples_and_backend_policy` |
| `facet.contract-fixture-coverage` | `provenance.source-seal` | `/notes`, `/source/files` | none | none | `accepted_contracts.control_flow_and_statements`, `accepted_contracts.crosstl_examples_and_backend_policy`, `accepted_contracts.descriptor_indexing_and_nonuniform`, `accepted_contracts.expressions_operators_and_intrinsics`, `accepted_contracts.module_stages_and_entry_points`, `accepted_contracts.resources_layouts_and_storage`, `accepted_contracts.textures_samplers_images_and_intrinsics`, `accepted_contracts.types_structs_arrays_and_constants`, `negative_contracts.spec_error`, `negative_contracts.spec_unsupported_for_native_v0` |

## Trace Matrix

| Trace id | Spec index id | Snapshot refs | CrossTL source evidence | Bucket | Compatibility row | Evidence |
| --- | --- | --- | --- | --- | --- | --- |
| `trace.accepted.modules-stages-entry` | `grammar.stages` | `/language/stages`, `/ast/enums/ShaderStage` | `crosstl/translator/lexer.py@e5c2c18870bc`, `crosstl/translator/parser.py@2a30ce24a4f5`, `crosstl/translator/ast.py@9ce23e8e1612` | `accepted-source` | `none` | `feature:module_stages_and_entry_points`, `contract:accepted_contracts.module_stages_and_entry_points`, `support:Accepted Source Forms` |
| `trace.package.resources-storage-images` | `grammar.resources` | `/language/resources`, `/validation/metadata` | `crosstl/translator/lexer.py@e5c2c18870bc`, `crosstl/translator/parser.py@2a30ce24a4f5`, `crosstl/translator/validation.py@a05fa68e4dd9` | `package-supported` | `none` | `feature:resources_layouts_and_storage`, `contract:accepted_contracts.resources_layouts_and_storage`, `support:v0 Package-Supported Subset` |
| `trace.compatibility.crosstl-examples-backend-policy` | `provenance.source-seal` | `/notes`, `/source/files` | `crosstl/translator/lexer.py@e5c2c18870bc`, `crosstl/translator/parser.py@2a30ce24a4f5`, `crosstl/translator/ast.py@9ce23e8e1612`, `crosstl/translator/validation.py@a05fa68e4dd9` | `compatibility-only` | `none` | `feature:crosstl_examples_and_backend_policy`, `contract:accepted_contracts.crosstl_examples_and_backend_policy`, `support:Compatibility-Only HIR and Raw Forms` |
| `trace.unsupported.extended-stages` | `grammar.stages` | `/language/stages` | `crosstl/translator/lexer.py@e5c2c18870bc`, `crosstl/translator/parser.py@2a30ce24a4f5`, `crosstl/translator/ast.py@9ce23e8e1612` | `compat.language-unsupported-native-v0` | `stage.extended-graphics` | `compatibility:stage.extended-graphics`, `feature:module_stages_and_entry_points`, `contract:negative_contracts.spec_unsupported_for_native_v0`, `support:Planned or Unsupported Forms` |
| `trace.unsupported.fn-style` | `ast.class-inventory` | `/ast/classes` | `crosstl/translator/ast.py@9ce23e8e1612` | `compat.language-unsupported-native-v0` | `decl.fn-style` | `compatibility:decl.fn-style`, `feature:types_structs_arrays_and_constants`, `contract:negative_contracts.spec_unsupported_for_native_v0`, `support:Planned or Unsupported Forms` |
| `trace.unsupported.pattern-control` | `ast.class-inventory` | `/ast/statementNodes`, `/ast/classes` | `crosstl/translator/ast.py@9ce23e8e1612` | `compat.language-unsupported-native-v0` | `stmt.pattern-control` | `compatibility:stmt.pattern-control`, `feature:control_flow_and_statements`, `contract:negative_contracts.spec_unsupported_for_native_v0`, `support:Planned or Unsupported Forms` |
| `trace.frontend.metadata-aliases` | `semantics.metadata-and-layout` | `/validation/metadata` | `crosstl/translator/validation.py@a05fa68e4dd9` | `compat.frontend-unsupported-native-v0` | `resource.metadata-aliases` | `compatibility:resource.metadata-aliases`, `feature:resources_layouts_and_storage`, `contract:negative_contracts.spec_unsupported_for_native_v0`, `support:Planned or Unsupported Forms` |
| `trace.accepted.float-literal-forms` | `lexical.tokens` | `/lexical/tokens` | `crosstl/translator/lexer.py@e5c2c18870bc` | `accepted-source` | `none` | `feature:expressions_operators_and_intrinsics`, `contract:accepted_contracts.expressions_operators_and_intrinsics`, `support:Accepted Source Forms` |
| `trace.target.resource-arrays` | `grammar.resources` | `/language/resources` | `crosstl/translator/parser.py@2a30ce24a4f5`, `crosstl/translator/validation.py@a05fa68e4dd9` | `compat.target-legalization-unsupported` | `target.resource-arrays` | `compatibility:target.resource-arrays`, `feature:crosstl_examples_and_backend_policy`, `contract:accepted_contracts.crosstl_examples_and_backend_policy`, `support:Planned or Unsupported Forms` |
| `trace.deprecated.kernel-alias` | `grammar.stages` | `/language/stages` | `crosstl/translator/lexer.py@e5c2c18870bc`, `crosstl/translator/parser.py@2a30ce24a4f5` | `compat.deprecated-crosstl-spelling` | `stage.kernel-alias` | `compatibility:stage.kernel-alias`, `feature:module_stages_and_entry_points`, `contract:accepted_contracts.module_stages_and_entry_points`, `support:Planned or Unsupported Forms` |
| `trace.error.no-stage-or-entry` | `grammar.stages` | `/language/stages` | `crosstl/translator/parser.py@2a30ce24a4f5`, `crosstl/translator/ast.py@9ce23e8e1612` | `compat.true-spec-error` | `sema.no-stage-or-entry` | `compatibility:sema.no-stage-or-entry`, `feature:module_stages_and_entry_points`, `contract:negative_contracts.spec_error`, `support:Planned or Unsupported Forms` |

## Bucket Rules

`accepted-source` means the form is in the shared source inventory and positive
cross-repo fixture contract. `package-supported` means the v0 support contract
also points to package or native package evidence for the exact family.
`compatibility-only` means the contract pins the form for interchange or
backend-policy comparison, but it must not be read as broad package support.

Compatibility buckets are narrower report-only labels:
`compat.language-unsupported-native-v0`,
`compat.frontend-unsupported-native-v0`,
`compat.target-legalization-unsupported`,
`compat.deprecated-crosstl-spelling`, and `compat.true-spec-error`. Every row
using one of those buckets must name a concrete `docs/language/COMPATIBILITY.md`
row and resolve to exactly one classification:
`spec.unsupported-for-native-v0`, `spec.deprecated`, `spec.error`, or
`target.unsupported`.

## Review Use

Use this audit before accepting new CrossTL snapshot facts into compiler v0
language docs. A changed CrossTL source hash, snapshot pointer, contract group,
or compatibility bucket should make the checker fail before prose drifts into a
new support claim. If a new form does not fit one row or bucket here, stop the
slice and request a compatibility-ledger decision instead of changing accepted
syntax.
