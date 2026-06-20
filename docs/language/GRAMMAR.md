# CrossGL v0 Grammar Guide

This page is the human-readable v0 grammar guide layered on top of the sealed
CrossTL frontend snapshot in
`docs/language/crosstl-frontend-language-spec-v0.json`. It is deliberately
conservative: the CrossTL grammar surface, the native compiler v0 subset, and
target-specific package support are separate facts.

## Status Tags

| Tag | Meaning |
| --- | --- |
| CrossTL accepted | The v0 CrossTL snapshot exposes this syntax through lexer, parser, AST, or validation data. |
| Native-v0 baseline | The native compiler accepts the form in current shared fixtures or compatibility evidence. |
| Unsupported for native-v0 | CrossTL exposes the form, but the native compiler does not claim support. |
| Deprecated | A compatibility spelling remains visible, but new shared source should avoid it. |
| Target-limited | The frontend may accept the form, but one or more backends reject package emission. |
| Spec error | Invalid shared CrossGL source that should be diagnosed before target emission. |

When this page says "native-v0", it means the fixture-scoped compiler subset
tracked by `docs/language/COMPATIBILITY.md`,
`tools/cross_repo_language_contract.json`, and package evidence in
`docs/SUPPORT_MATRIX_EVIDENCE.md`.

## Notation

The productions below are descriptive, not a new machine grammar. Terminal
spellings are shown in backticks. Nonterminals use angle brackets. Optional
items use `?`; repeated items use `*` or `+`.

```text
<identifier> ::= ordinary CrossTL identifier token
<literal>    ::= number | float-number | hex-number | bin-number
               | oct-number | string-literal | char-literal
```

CrossTL skips whitespace plus single-line and multi-line comments. The lexer
also exposes a preprocessor token, but native-v0 treats preprocessor nodes as
unsupported for native compilation.

## Checked Grammar Surface Contract

The report-only CrossTL grammar surface contract v1 below pins this page to the
sealed CrossTL snapshot inventory, not native compiler parser behavior. It is
not native-v0 support, not a complete grammar-production contract, and not a
claim that the native compiler accepts every inventoried spelling. Real
grammar-production extraction remains a report-only gap until a later slice
extracts productions from CrossTL and wires separate behavior-owning evidence.

The checked scope is exactly:

- `/source/files`
- `/lexical/tokens`
- `/lexical/keywords`
- `/lexical/literalTokens`
- `/lexical/skipTokens`
- `/language/stages`
- `/language/types`
- `/language/qualifiers`
- `/language/resources`

This contract deliberately leaves AST-owned `/ast/*` to
`docs/language/AST_SCHEMA.md` and semantic-baseline-owned `/validation/*` and
`/language/intrinsics` to later semantic-baseline work. It does not authorize
CrossTL source changes, does not authorize native compiler parser changes, HIR
lowering, backend or runtime behavior changes, fixture or conformance manifest
changes, package output changes, fixture hash changes, cross-repo language
contract updates, or generated `SPEC.md` / `SPEC_INDEX.md` edits. Check it
with:

```sh
python3 tools/check_language_grammar_surface_contract.py --root .
```

<!-- crossgl-crosstl-grammar-surface-contract-v1:begin -->
```json
{
  "claims": {
    "ast": "owned-by-report-only-ast-contract",
    "behavior": "no-crosstl-source-native-parser-hir-backend-runtime-fixture-conformance-package-hash-contract-or-generated-spec-change",
    "grammarProductions": "not-sealed-by-this-contract",
    "nativeCompilerParserBehavior": "not-claimed",
    "nativeV0Support": "not-claimed-by-grammar-surface-inventory",
    "validationAndIntrinsics": "owned-by-later-semantic-baseline-work"
  },
  "inventory": {
    "language": {
      "qualifiersKeys": [
        "parameterPrimitiveQualifierNames",
        "parameterQualifierTokens",
        "variableQualifierNames",
        "variableQualifierTokens"
      ],
      "qualifiersSha256": "d573698796ff3d761aed88fdb3183703059432940d7cb37fc253340bef7b6331",
      "resourcesKeys": [
        "addressSpaceMetadata",
        "builtinSemanticMetadata",
        "descriptorIndexMetadata",
        "imageFormatMetadataNames",
        "memoryLayoutMetadata",
        "resourceAccessMetadata",
        "resourceBufferTypeNames",
        "samplerStateTypeNames",
        "storageImageTypeNames",
        "uavResourceBufferTypeNames"
      ],
      "resourcesSha256": "bcedb3a056053d5f5a107c2ecb79ded662e476bcdc8ae4e4b3e9fe3b1c220972",
      "stagesKeys": [
        "canonical",
        "keywordSpellings",
        "parserStageTokens"
      ],
      "stagesSha256": "1c46f70749c184ce215e373568e4385aafee2ff357b77a728cfaf4a110d75497",
      "typesKeys": [
        "arrayForms",
        "matrices",
        "namedTypeFallback",
        "postfixTypeOperators",
        "primitive",
        "samplersAndImages",
        "textures",
        "vectors"
      ],
      "typesSha256": "b7ea742b0d785e528792b73caf49a6d274d1406da1d2a416977ccfaafbc9695e"
    },
    "lexical": {
      "keywordCount": 183,
      "keywordsSha256": "f7007c96d91d1b986ae340040e182e6e2d057a8e4203fe48552dfb52b90b5f49",
      "literalTokenCount": 7,
      "literalTokensSha256": "423d54e430da3c49a38ef075ebc14bc5f0d34f74e280fda34450caf25c19b26b",
      "skipTokenCount": 3,
      "skipTokensSha256": "9b2259349cbd1e82cd4460c93aa77af59d10d7e45cf0631d2d7ab76b6c1fb62f",
      "tokenCount": 239,
      "tokensSha256": "c3b168a21bfa5216e8bbdea43d4c1e60511d64a3fd3b12ac0403564335e81ef6"
    },
    "pointerSummaries": {
      "/language/qualifiers": {
        "keys": [
          "parameterPrimitiveQualifierNames",
          "parameterQualifierTokens",
          "variableQualifierNames",
          "variableQualifierTokens"
        ],
        "sha256": "d573698796ff3d761aed88fdb3183703059432940d7cb37fc253340bef7b6331"
      },
      "/language/resources": {
        "keys": [
          "addressSpaceMetadata",
          "builtinSemanticMetadata",
          "descriptorIndexMetadata",
          "imageFormatMetadataNames",
          "memoryLayoutMetadata",
          "resourceAccessMetadata",
          "resourceBufferTypeNames",
          "samplerStateTypeNames",
          "storageImageTypeNames",
          "uavResourceBufferTypeNames"
        ],
        "sha256": "bcedb3a056053d5f5a107c2ecb79ded662e476bcdc8ae4e4b3e9fe3b1c220972"
      },
      "/language/stages": {
        "keys": [
          "canonical",
          "keywordSpellings",
          "parserStageTokens"
        ],
        "sha256": "1c46f70749c184ce215e373568e4385aafee2ff357b77a728cfaf4a110d75497"
      },
      "/language/types": {
        "keys": [
          "arrayForms",
          "matrices",
          "namedTypeFallback",
          "postfixTypeOperators",
          "primitive",
          "samplersAndImages",
          "textures",
          "vectors"
        ],
        "sha256": "b7ea742b0d785e528792b73caf49a6d274d1406da1d2a416977ccfaafbc9695e"
      },
      "/lexical/keywords": {
        "count": 183,
        "sha256": "f7007c96d91d1b986ae340040e182e6e2d057a8e4203fe48552dfb52b90b5f49"
      },
      "/lexical/literalTokens": {
        "count": 7,
        "sha256": "423d54e430da3c49a38ef075ebc14bc5f0d34f74e280fda34450caf25c19b26b"
      },
      "/lexical/skipTokens": {
        "count": 3,
        "sha256": "9b2259349cbd1e82cd4460c93aa77af59d10d7e45cf0631d2d7ab76b6c1fb62f"
      },
      "/lexical/tokens": {
        "count": 239,
        "sha256": "c3b168a21bfa5216e8bbdea43d4c1e60511d64a3fd3b12ac0403564335e81ef6"
      },
      "/source/files": {
        "count": 4,
        "sha256": "fca09ce8e6f22197c6286f5e880d2020f9437cd6de2bcfae640511ed20b48784"
      }
    },
    "source": {
      "fileCount": 4,
      "files": [
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
      "filesSha256": "fca09ce8e6f22197c6286f5e880d2020f9437cd6de2bcfae640511ed20b48784"
    }
  },
  "kind": "crossgl-crosstl-grammar-surface-contract",
  "outOfScope": [
    "/ast/*",
    "/validation/*",
    "/language/intrinsics"
  ],
  "pointers": [
    "/source/files",
    "/lexical/tokens",
    "/lexical/keywords",
    "/lexical/literalTokens",
    "/lexical/skipTokens",
    "/language/stages",
    "/language/types",
    "/language/qualifiers",
    "/language/resources"
  ],
  "snapshot": "docs/language/crosstl-frontend-language-spec-v0.json",
  "status": "report-only-snapshot-inventory",
  "version": 1
}
```
<!-- crossgl-crosstl-grammar-surface-contract-v1:end -->

## Checked Declaration/Name Grammar-Production Alignment Contract

The report-only declaration/name grammar-production alignment contract v1 is a
bounded pilot slice for `decl.colon-var` plus `input/output name-token
compatibility`. It checks that function-body `var name: Type` local
declarations keep HIR evidence, that stage-scope unqualified `var name: Type`
remains unsupported with diagnostic evidence, and that the native
`input`/`output` name-token compatibility remains explicit and does not
silently widen shared source.

This is not a complete grammar-production extraction. It does not authorize
parser behavior changes, CrossTL source changes, backend or target behavior
changes, cross-repo contract updates, or new shared source that depends on
deprecated name-token compatibility. It also does not authorize fixture hash
updates. Check it with:

```sh
python3 tools/check_language_grammar_production_contract.py --root .
```

<!-- crossgl-language-grammar-production-alignment-contract-v1:begin -->
```json
{
  "claims": {
    "backendTargetBehavior": "not-authorized",
    "nativeV0Support": "fixture-scoped-positive-and-negative-evidence-only",
    "parserBehaviorChanges": "not-authorized",
    "reportOnly": true,
    "sharedSourceWidening": "not-authorized"
  },
  "kind": "crossgl-language-grammar-production-alignment-contract",
  "productions": {
    "compat.input-output-names": {
      "compatibility": {
        "bucket": "compat.deprecated-crosstl-spelling",
        "classification": "spec.deprecated",
        "ownerBucket": "owner.language-compatibility-policy",
        "row": "compat.input-output-names",
        "sharedSourcePolicy": "explicit-compatibility-only-no-shared-source-widening"
      },
      "crosstlEvidence": {
        "inputIsKeyword": false,
        "keywordPointer": "/lexical/keywords",
        "outputIsKeyword": false,
        "qualifierPointer": "/language/qualifiers/variableQualifierNames",
        "snapshot": "docs/language/crosstl-frontend-language-spec-v0.json",
        "variableQualifierNames": [
          "input",
          "output"
        ]
      },
      "nativeEvidence": {
        "lexer": "src/Frontend/Lexer.cpp",
        "parserNameTokenHook": "src/Frontend/Parser.cpp::isNameToken",
        "tokenKinds": [
          "KeywordInput",
          "KeywordOutput"
        ]
      },
      "sourceForm": "input/output declaration names"
    },
    "decl.colon-var": {
      "acceptedNativeV0Scope": {
        "conformance": {
          "evidenceTests": [
            "cglc_check_colon_var_compute_hir_canonical_declaration"
          ],
          "id": "control-flow.colon-var-local-declaration",
          "status": "accepted"
        },
        "contract": {
          "compilerHirSha256": "86d444b64d3e31eb22f6f1f16b334443003e9761a22257a03f5f66f6ec48c7b9",
          "key": "compiler/tests/fixtures/ColonVarComputeShader.cgl",
          "sourceSha256": "461bd00eac3dd95d5029042d241baa9f58340cfe9237ae54d8e6899e808cdf43",
          "translatorAstSha256": "fec407cbcb49872d98c23f10970b30cee2142d722a66d83be456fb143907cae6"
        },
        "ctest": "cglc_check_colon_var_compute_hir_canonical_declaration",
        "fixture": "tests/fixtures/ColonVarComputeShader.cgl",
        "fixtureSha256": "461bd00eac3dd95d5029042d241baa9f58340cfe9237ae54d8e6899e808cdf43",
        "hirEvidenceContains": [
          "decl float base = values[1] : float",
          "decl float scaled = base * 2.0 : float"
        ],
        "scope": "function-body-local-declaration"
      },
      "compatibility": {
        "bucket": "compat.frontend-unsupported-native-v0",
        "classification": "spec.unsupported-for-native-v0",
        "ownerBucket": "owner.compiler-frontend-subset-limit",
        "row": "decl.colon-var"
      },
      "crosstlEvidence": {
        "pointers": [
          "/ast/classes",
          "/language/types"
        ],
        "requiredAstClass": "VariableNode",
        "snapshot": "docs/language/crosstl-frontend-language-spec-v0.json"
      },
      "sourceForm": "var name: Type",
      "unsupportedNativeV0Scope": {
        "conformance": {
          "evidenceTests": [
            "cglc_check_unsupported_native_v0_colon_var_failure"
          ],
          "expectedDiagnostic": "spec.unsupported-for-native-v0",
          "id": "native-v0-unsupported.colon-var",
          "status": "unsupported"
        },
        "contract": {
          "classification": "spec.unsupported-for-native-v0",
          "compatibilityAnchors": [
            "compat.frontend-unsupported-native-v0",
            "decl.colon-var"
          ],
          "compilerStatus": "rejects",
          "diagnosticSubstrings": [
            "spec.unsupported-for-native-v0",
            "decl.colon-var"
          ],
          "id": "compiler/tests/check-failures/BadUnsupportedColonVarShader.cgl"
        },
        "ctest": "cglc_check_unsupported_native_v0_colon_var_failure",
        "diagnostic": {
          "code": "spec.unsupported-for-native-v0",
          "column": 5,
          "line": 3,
          "messageContains": [
            "colon-style variable declarations",
            "native v0",
            "decl.colon-var"
          ]
        },
        "fixture": "tests/check-failures/BadUnsupportedColonVarShader.cgl",
        "fixtureSha256": "85ac8c6b0fd0503822b17ab72adbabe32078a6856580826bb320b2528256f88e",
        "scope": "stage-scope-unqualified-var"
      }
    }
  },
  "scope": {
    "boundedTo": [
      "function-body-colon-var-local-declarations",
      "stage-scope-unqualified-colon-var-diagnostic",
      "input-output-name-token-compatibility-policy"
    ],
    "families": [
      "declaration-productions",
      "name-token-compatibility"
    ],
    "outOfScope": [
      "complete-crosstl-production-extraction",
      "parser-behavior-changes",
      "shared-source-syntax-widening",
      "backend-or-target-support",
      "fixture-hash-updates"
    ],
    "pilot": "decl.colon-var"
  },
  "status": "report-only-declaration-name-productions",
  "version": 1
}
```
<!-- crossgl-language-grammar-production-alignment-contract-v1:end -->

## Grammar Claim Trace Map

Every grammar-claim section below separates CrossTL frontend evidence from the
compiler-v0 subset evidence. CrossTL evidence is tied to the sealed snapshot
and source hashes; compiler-v0 evidence is a support bucket, compatibility row,
fixture contract group, and checked fixture/case count, and does not widen
accepted syntax.

| Grammar section | CrossTL frontend trace | Compiler-v0 subset trace |
| --- | --- | --- |
| `Checked Grammar Surface Contract` | `/source/files`, `/lexical/tokens`, `/lexical/keywords`, `/lexical/literalTokens`, `/lexical/skipTokens`, `/language/stages`, `/language/types`, `/language/qualifiers`, `/language/resources`, `crosstl/translator/lexer.py@e5c2c18870bc`, `crosstl/translator/parser.py@2a30ce24a4f5`, `crosstl/translator/ast.py@9ce23e8e1612`, `crosstl/translator/validation.py@a05fa68e4dd9` | `none` |
| `Checked Declaration/Name Grammar-Production Alignment Contract` | `facet.grammar-productions`, `facet.compatibility-classifications`, `ast.class-inventory`, `grammar.types`, `grammar.qualifiers`, `/ast/classes`, `/language/types`, `/lexical/keywords`, `/language/qualifiers/variableQualifierNames`, `crosstl/translator/lexer.py@e5c2c18870bc`, `crosstl/translator/parser.py@2a30ce24a4f5`, `crosstl/translator/ast.py@9ce23e8e1612` | `bucket:accepted-source`, `bucket:compat.frontend-unsupported-native-v0`, `bucket:compat.deprecated-crosstl-spelling`, `compatibility:decl.colon-var`, `compatibility:compat.input-output-names`, `contract:accepted_contracts.control_flow_and_statements`, `contract:negative_contracts.spec_unsupported_for_native_v0`, `fixture-count:10`, `case-count:26` |
| `Notation` | `facet.lexical-grammar`, `lexical.tokens`, `lexical.literals-and-skips`, `/lexical/tokens`, `/lexical/literalTokens`, `/lexical/skipTokens`, `crosstl/translator/lexer.py@e5c2c18870bc` | `contract:accepted_contracts.control_flow_and_statements`, `contract:accepted_contracts.module_stages_and_entry_points`, `fixture-count:14` |
| `Translation Unit` | `facet.grammar-productions`, `ast.class-inventory`, `/ast/classes`, `/source/files`, `crosstl/translator/parser.py@2a30ce24a4f5`, `crosstl/translator/ast.py@9ce23e8e1612` | `bucket:accepted-source`, `bucket:compat.language-unsupported-native-v0`, `contract:accepted_contracts.module_stages_and_entry_points`, `contract:negative_contracts.spec_unsupported_for_native_v0`, `fixture-count:4`, `case-count:26` |
| `Shader Modules and Stages` | `trace.accepted.modules-stages-entry`, `trace.unsupported.extended-stages`, `trace.deprecated.kernel-alias`, `trace.error.no-stage-or-entry`, `grammar.stages`, `/language/stages`, `crosstl/translator/lexer.py@e5c2c18870bc`, `crosstl/translator/parser.py@2a30ce24a4f5`, `crosstl/translator/ast.py@9ce23e8e1612` | `bucket:accepted-source`, `bucket:compat.language-unsupported-native-v0`, `bucket:compat.deprecated-crosstl-spelling`, `bucket:compat.true-spec-error`, `compatibility:stage.extended-graphics`, `compatibility:stage.kernel-alias`, `compatibility:sema.no-stage-or-entry`, `contract:accepted_contracts.module_stages_and_entry_points`, `contract:negative_contracts.spec_error`, `contract:negative_contracts.spec_unsupported_for_native_v0`, `fixture-count:4`, `case-count:30` |
| `Declarations` | `trace.unsupported.fn-style`, `ast.class-inventory`, `grammar.types`, `/ast/classes`, `/language/types`, `crosstl/translator/parser.py@2a30ce24a4f5`, `crosstl/translator/ast.py@9ce23e8e1612` | `bucket:accepted-source`, `bucket:compat.language-unsupported-native-v0`, `compatibility:decl.colon-var`, `compatibility:decl.fn-style`, `contract:accepted_contracts.types_structs_arrays_and_constants`, `contract:negative_contracts.spec_unsupported_for_native_v0`, `fixture-count:7`, `case-count:26` |
| `Types` | `facet.grammar-productions`, `grammar.types`, `ast.class-inventory`, `/language/types`, `/ast/typeNodes`, `crosstl/translator/lexer.py@e5c2c18870bc`, `crosstl/translator/parser.py@2a30ce24a4f5`, `crosstl/translator/ast.py@9ce23e8e1612` | `bucket:accepted-source`, `bucket:compat.true-spec-error`, `compatibility:sema.array-shape`, `contract:accepted_contracts.types_structs_arrays_and_constants`, `contract:accepted_contracts.descriptor_indexing_and_nonuniform`, `contract:accepted_contracts.textures_samplers_images_and_intrinsics`, `contract:negative_contracts.spec_error`, `fixture-count:28`, `case-count:4` |
| `Resources and Layout` | `trace.package.resources-storage-images`, `trace.frontend.metadata-aliases`, `trace.target.resource-arrays`, `grammar.resources`, `grammar.qualifiers`, `/language/resources`, `/language/qualifiers`, `/validation/metadata`, `crosstl/translator/lexer.py@e5c2c18870bc`, `crosstl/translator/parser.py@2a30ce24a4f5`, `crosstl/translator/validation.py@a05fa68e4dd9` | `bucket:package-supported`, `bucket:compat.frontend-unsupported-native-v0`, `bucket:compat.target-legalization-unsupported`, `compatibility:resource.metadata-aliases`, `compatibility:target.resource-arrays`, `contract:accepted_contracts.resources_layouts_and_storage`, `contract:accepted_contracts.descriptor_indexing_and_nonuniform`, `contract:negative_contracts.spec_unsupported_for_native_v0`, `fixture-count:22`, `case-count:26` |
| `Statements` | `trace.unsupported.pattern-control`, `facet.ast-nodes`, `lexical.keywords`, `/ast/statementNodes`, `/lexical/keywords`, `crosstl/translator/lexer.py@e5c2c18870bc`, `crosstl/translator/parser.py@2a30ce24a4f5`, `crosstl/translator/ast.py@9ce23e8e1612` | `bucket:accepted-source`, `bucket:compat.language-unsupported-native-v0`, `bucket:compat.true-spec-error`, `compatibility:stmt.pattern-control`, `contract:accepted_contracts.control_flow_and_statements`, `contract:negative_contracts.spec_error`, `contract:negative_contracts.spec_unsupported_for_native_v0`, `fixture-count:10`, `case-count:30` |
| `Expressions` | `trace.accepted.float-literal-forms`, `facet.semantic-checks`, `lexical.tokens`, `ast.class-inventory`, `semantics.intrinsics`, `/lexical/tokens`, `/ast/expressionNodes`, `/language/intrinsics`, `crosstl/translator/lexer.py@e5c2c18870bc`, `crosstl/translator/parser.py@2a30ce24a4f5`, `crosstl/translator/ast.py@9ce23e8e1612`, `crosstl/translator/validation.py@a05fa68e4dd9` | `bucket:accepted-source`, `bucket:compat.target-legalization-unsupported`, `compatibility:target.texture-shadow-lod`, `contract:accepted_contracts.expressions_operators_and_intrinsics`, `contract:accepted_contracts.textures_samplers_images_and_intrinsics`, `contract:accepted_contracts.crosstl_examples_and_backend_policy`, `fixture-count:27` |
| `Accepted But Unsupported for Native-v0` | `trace.unsupported.extended-stages`, `trace.unsupported.fn-style`, `trace.unsupported.pattern-control`, `trace.frontend.metadata-aliases`, `facet.compatibility-classifications`, `/notes`, `/source/files`, `crosstl/translator/lexer.py@e5c2c18870bc`, `crosstl/translator/parser.py@2a30ce24a4f5`, `crosstl/translator/ast.py@9ce23e8e1612`, `crosstl/translator/validation.py@a05fa68e4dd9` | `bucket:compat.language-unsupported-native-v0`, `bucket:compat.frontend-unsupported-native-v0`, `bucket:compat.target-legalization-unsupported`, `support:Planned or Unsupported Forms`, `compatibility:decl.colon-var`, `compatibility:decl.import-preprocessor`, `compatibility:decl.line-splicing-preprocessor`, `compatibility:resource.var-address-space`, `contract:negative_contracts.spec_unsupported_for_native_v0`, `case-count:26` |

## Translation Unit

```text
<translation-unit> ::= <top-level-item>*

<top-level-item> ::= <shader-decl>
                   | <struct-decl>
                   | <constant-decl>
                   | <global-var-decl>
                   | <cbuffer-decl>
                   | <function-decl>
                   | <unsupported-crosstl-item>
```

Native-v0 source should use `shader` modules with supported stage blocks and
C-style functions. CrossTL also exposes import, preprocessor, enum, trait,
impl, generic, and Rust-like function nodes; those are unsupported for
native-v0 unless a future compatibility row moves them into the baseline.
Backslash-newline physical line splicing is classified as preprocessor/importer
tolerance in `decl.line-splicing-preprocessor`; it is not a shared `.cgl`
grammar production and does not make preprocessor directives, includes, macros,
or foreign source files native-v0 syntax.

## Shader Modules and Stages

```text
<shader-decl> ::= `shader` <identifier> `{` <shader-item>* `}`

<shader-item> ::= <stage-block>
                | <struct-decl>
                | <constant-decl>
                | <resource-decl>
                | <function-decl>

<stage-block> ::= <stage-keyword> `{` <stage-item>* `}`
```

Native-v0 baseline stage spellings are:

```text
<stage-keyword> ::= `vertex` | `fragment` | `compute`
```

CrossTL accepted but unsupported for native-v0 stage spellings include
`geometry`, `task`, `amplification`, `object`, `mesh`,
`tessellation_control`, `tessellation_evaluation`, `hull`, `domain`,
`ray_generation`, `ray_intersection`, `ray_closest_hit`, `ray_miss`,
`ray_any_hit`, `ray_callable`, and their short ray aliases. The `kernel`
spelling is deprecated; use `compute`.

Native-v0 rejects modules with no supported stage or a supported stage that has
no entry function as `spec.error`.

## Declarations

```text
<function-decl> ::= <type> <identifier> `(` <parameter-list>? `)` <block>

<parameter-list> ::= <parameter> (`,` <parameter>)*
<parameter>      ::= <qualifier>* <type> <identifier>

<struct-decl>    ::= `struct` <identifier> `{` <struct-member>* `}` `;`?
<struct-member>  ::= <type> <identifier> <array-suffix>* `;`

<constant-decl>  ::= `const` <type> <identifier> `=` <expr> `;`
<global-var-decl>::= <qualifier>* <type> <identifier> <array-suffix>* (`=` <expr>)? `;`
```

Native-v0 baseline declarations are C-style functions, structs, constants,
cbuffers, resource declarations, and local/global variables covered by the
contract fixtures. CrossTL function declarations with `fn`, generic parameter
lists, `where` clauses, traits, impls, pattern parameters, and imports are
unsupported for native-v0.

## Types

```text
<type> ::= <primitive-type>
         | <vector-type>
         | <matrix-type>
         | <texture-type>
         | <sampler-or-image-type>
         | <buffer-type>
         | <named-type>
         | <array-type>
         | <postfix-type>

<array-type>    ::= `[` <type> <array-size>? `]`
                  | <type> `[` <array-size>? `]`
<postfix-type>  ::= <type> `*`
                  | <type> `&`
                  | <type> `&` `mut`
<array-size>    ::= positive integer constant expression in native-v0 fixed-size contexts
```

CrossTL exposes primitive, vector, matrix, array, pointer, reference, function,
generic, and named type nodes. Native-v0 support is narrower:

| Family | Native-v0 guidance |
| --- | --- |
| Scalars, vectors, matrices, named structs | Baseline when covered by parser/HIR fixtures. |
| Fixed arrays and documented runtime-tail arrays | Baseline only in the fixture-scoped forms named by `V0_SUPPORT.md`. |
| Pointer, reference, function, and generic types | CrossTL surface only unless compatibility evidence names a supported form. |
| Textures, samplers, storage images, buffers | Baseline only for resource shapes and operations covered by the contract and support matrix. |
| Unknown named types | May parse, but native diagnostics and HIR support decide whether the source is valid. |

Zero, negative, boolean, overflowing, unresolved, and expression array sizes in
fixed-size contexts are `spec.error` in native-v0.

## Resources and Layout

```text
<resource-decl> ::= <layout-qualifier>? <qualifier>* <type> <identifier>
                    <array-suffix>* `;`

<layout-qualifier> ::= `layout` `(` <layout-entry> (`,` <layout-entry>)* `)`
<layout-entry>     ::= <identifier> (`=` <literal-or-identifier>)?
```

Native-v0 portable source should prefer:

```text
layout(set = N, binding = M) <resource-type> name;
layout(group = N, binding = M) <resource-type> name;  // canonicalized as set N
layout(set = N, register = M) <resource-type> name;  // canonicalized as binding M
layout(set = N, binding = M, format = F) <storage-image-type> name;
layout(local_size_x = X, local_size_y = Y, local_size_z = Z) in;
```

CrossTL exposes broader metadata aliases such as HLSL/GLSL semantic names,
HLSL tuple-style `register(...)`, interpolation metadata, memory layout metadata, and address-space
aliases. Those are unsupported for native-v0 unless a compatibility row and
fixture name the exact form; `group` is accepted as the canonical `set`
resource-layout alias, and scalar `register = N` is accepted as the canonical
resource `binding` alias. Stage-scope `var<workgroup>`/shared storage is the
only shared `var<...>` family called out as current compiler fixture surface;
other address spaces are unsupported for native-v0.

## Statements

```text
<block>     ::= `{` <statement>* `}`
<statement> ::= <block>
              | <decl-statement>
              | <assignment> `;`
              | <expr> `;`
              | <if-statement>
              | <for-statement>
              | <while-statement>
              | <return-statement>
              | `break` `;`
              | `continue` `;`

<if-statement>    ::= `if` `(` <expr> `)` <statement> (`else` <statement>)?
<for-statement>   ::= `for` `(` <for-init>? `;` <expr>? `;` <for-update>? `)` <statement>
<while-statement> ::= `while` `(` <expr> `)` <statement>
<return-statement>::= `return` <expr>? `;`
```

Native-v0 baseline statement forms are scoped declarations, assignments,
expression statements, `if`, C-style `for`, `while`, early `return`,
`break`, and `continue` as covered by fixtures. CrossTL statement nodes also
include `for in`, `loop`, `do while`, `match`, `switch`, `case`, and sync
nodes. Treat those as unsupported for native-v0 until HIR lowering and
diagnostic evidence exist. `break` or `continue` outside a loop is a
`spec.error`.

## Expressions

```text
<expr> ::= <literal>
         | <identifier>
         | <call-expr>
         | <constructor-expr>
         | <member-expr>
         | <index-expr>
         | <swizzle-expr>
         | <cast-expr>
         | <unary-expr>
         | <binary-expr>
         | <ternary-expr>
         | <array-literal>

<call-expr>        ::= <expr> `(` <argument-list>? `)`
<constructor-expr> ::= <type> `(` <argument-list>? `)`
<index-expr>       ::= <expr> `[` <expr> `]`
<swizzle-expr>     ::= <expr> `.` <swizzle-mask>
<cast-expr>        ::= <type> `(` <expr> `)`
```

Native-v0 baseline expressions include literals, identifiers, arithmetic and
comparison operators, assignments and read-modify/write forms, calls, casts,
constructors, member access, array access, scalar/vector intrinsics, texture
and image operations, storage-image atomics, and swizzles where covered by
fixtures. CrossTL additionally exposes lambda, range, pattern, wave, ray,
ray-query, mesh, and broader texture/resource operation nodes. Those broader
nodes are CrossTL surface only unless the native support docs name evidence.

Invalid texture, sampler, storage-image, swizzle, vector/scalar, constructor,
increment/decrement, nonuniform, and array-coordinate shapes are `spec.error`
when covered by native check-failure fixtures.

## Accepted But Unsupported for Native-v0

The following families are accepted or exposed by CrossTL but are not current
native-v0 compiler support:

| Family | Examples |
| --- | --- |
| Extended stages | Geometry, mesh/task/object/amplification, tessellation, and ray stages. |
| Rust-like declarations | `fn`, generics, `where`, traits, impls. |
| Pattern/control extensions | `match`, pattern nodes, `for name in expr`, `loop`, `do while`, `switch/case/default`, `let mut`. |
| Import and preprocessor forms | `import`, `use`, `from ... import ...`, preprocessor nodes. |
| Preprocessor/importer line tolerance | Backslash-newline physical line splicing before directive/importer tokenization. |
| Broad metadata/address spaces | HLSL/GLSL semantic aliases, interpolation aliases, most `var<address-space>` forms. |
| Advanced intrinsic families | Wave, ray tracing, ray query, and mesh operation nodes unless future evidence names them. |

Target-limited forms, such as shadow texture LOD source and some runtime
resource arrays or helper array parameters, are legal frontend forms only when
the selected target has support evidence. Otherwise package builds must fail
with target-specific diagnostics.

## Update Rule

Do not add grammar here as current support unless one of these is true:

1. The CrossTL snapshot exposes it and the compatibility ledger marks it as
   native-v0 baseline or target-limited with evidence.
2. The cross-repo contract records an accepted fixture for both CrossTL and the
   compiler.
3. The support matrix names package or planned-failure evidence for the exact
   source form and target.

Future grammar belongs in `COMPATIBILITY.md` first as an explicit delta, then in
fixtures and support evidence.
