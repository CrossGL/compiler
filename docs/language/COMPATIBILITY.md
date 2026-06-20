# Compiler vs. CrossTL Compatibility Ledger

This ledger classifies known source-form differences between the native
CrossGL-Compiler frontend and the CrossTL frontend surface captured in
`docs/language/crosstl-frontend-language-spec-v0.json`.

The CrossTL v0 snapshot is the source of truth for CrossTL's language surface.
The compiler side records what `cglc check` and the native HIR path currently
accept for the native-v0 compiler. The goal of this ledger is to make deltas
explicit, not to promote a compiler-only dialect.

Read this ledger with the prose artifacts in this directory:

- [GRAMMAR.md](GRAMMAR.md) gives the human-readable grammar guide.
- [AST_SCHEMA.md](AST_SCHEMA.md) documents the CrossTL AST schema seed.
- [SEMANTICS.md](SEMANTICS.md) explains the native-v0 semantic and target
  support layers.
- [V0_SUPPORT.md](V0_SUPPORT.md) is the fixture-scoped language/support
  contract.

## Report-only Classification Layers

`Classification` is the broad policy class consumed by existing prose and
support-evidence checks. `Bucket` is the narrower report-only compatibility
bucket used to keep CrossTL language exposure, native compiler frontend gaps,
target legalization gaps, deprecated spellings, and invalid source errors from
being collapsed into one native-v0 unsupported pile. `Owner bucket` is a
report-only routing label for roadmap work; it does not change accepted syntax,
fixture expectations, parser behavior, or backend legality.

### Classifications

| Classification | Meaning |
| --- | --- |
| `spec.unsupported-for-native-v0` | CrossTL v0 exposes the source form, but the native compiler frontend does not support it yet. The compiler may reject it or recover by skipping it. |
| `spec.deprecated` | The source form is a legacy or compatibility spelling. Prefer the non-deprecated spelling in shared source. |
| `spec.error` | The source form is invalid for shared CrossGL and should be rejected before target emission. |
| `target.unsupported` | The shared frontend accepts the source form, but one or more backend targets cannot emit it yet. |

### Compatibility Buckets

| Bucket | Compatible classification | Meaning |
| --- | --- | --- |
| `compat.language-unsupported-native-v0` | `spec.unsupported-for-native-v0` | CrossTL exposes the language form, but native-v0 does not include it in the shared compiler language subset. |
| `compat.frontend-unsupported-native-v0` | `spec.unsupported-for-native-v0` | The native-v0 subset has a narrower accepted form, but the current compiler frontend rejects, skips, or warns on the broader CrossTL spelling. |
| `compat.target-legalization-unsupported` | `target.unsupported` | The shared frontend/HIR path can accept the source form, but one or more target legalization or backend package paths cannot emit it yet. |
| `compat.deprecated-crosstl-spelling` | `spec.deprecated` | A CrossTL or native compatibility spelling remains visible for legacy source, but new shared fixtures should use the canonical spelling. |
| `compat.true-spec-error` | `spec.error` | The source form is invalid shared CrossGL, not an accepted CrossTL/native-v0 delta. |

### Owner Buckets

| Owner bucket | Meaning |
| --- | --- |
| `owner.language-future-feature` | Language-level future feature owned by the shared language roadmap. CrossTL may expose the form in the sealed snapshot, but native-v0 does not claim it as part of the compiler language subset yet. |
| `owner.compiler-frontend-subset-limit` | Native compiler frontend subset limit. The shared language surface or snapshot names the form, but the current native frontend only accepts a narrower spelling or intentionally reports/skips the broader spelling. |
| `owner.target-legalization-limit` | Target/legalization limit. Frontend and HIR evidence can exist, but one or more backend legalization or package paths must reject or downgrade the form until target support is added. |
| `owner.language-compatibility-policy` | Language compatibility policy item, usually a deprecated spelling that remains documented but should not gain new shared fixtures. |
| `owner.language-error` | Shared language error owned by diagnostics and semantic validation rather than future feature or target work. |

### Unsupported Gap Bucket Contract

Every unsupported source-form row must be routed through exactly one report-only
gap bucket before any compiler work is proposed:

- `compat.language-unsupported-native-v0` is a language-level gap. CrossTL v0
  exposes the form, but native-v0 does not claim it as part of the shared
  compiler language subset.
- `compat.frontend-unsupported-native-v0` is a compiler-frontend gap. The
  shared language surface or snapshot names the form, but the current native
  frontend accepts only a narrower spelling or emits an unsupported diagnostic.
- `compat.target-legalization-unsupported` is a target-legalization gap. The
  frontend/HIR path can accept the form, but one or more target legalization or
  backend package paths cannot emit it yet.

Rows in the language-level and compiler-frontend buckets must use
`spec.unsupported-for-native-v0`. Rows in the target-legalization bucket must
use `target.unsupported`. Deprecated spellings and true spec errors are not
unsupported gap buckets, and moving a form between buckets is a documentation
and evidence update only; it does not change accepted syntax, parser behavior,
fixture expectations, or backend legality.

`tools/check_v0_support_evidence.py` enforces the ledger pairing for every
planned native-v0 unsupported row cited by `V0_SUPPORT.md` and for every row in
this ledger:

| Unsupported bucket | Required classification | Required owner bucket | Future-change owner |
| --- | --- | --- | --- |
| `compat.language-unsupported-native-v0` | `spec.unsupported-for-native-v0` | `owner.language-future-feature` | Shared language/spec work. Add CrossTL/shared grammar, positive contract, frontend/HIR, and target evidence before promoting support. |
| `compat.frontend-unsupported-native-v0` | `spec.unsupported-for-native-v0` | `owner.compiler-frontend-subset-limit` | Native compiler frontend work. Add parser/HIR acceptance and diagnostics evidence before any package support claim. |
| `compat.target-legalization-unsupported` | `target.unsupported` | `owner.target-legalization-limit` | Target legalization/package work. Keep frontend acceptance separate from target planned-failure evidence until backend support lands. |

The checker also requires the Planned or Unsupported Forms section in
`V0_SUPPORT.md` to contain explicit evidence for all three unsupported buckets,
so a generic "unsupported for native-v0" row cannot hide which layer owns the
gap.

## Semantic Baseline Checklist

This checklist is a report-only semantic baseline for shared spec
formalization. It ties CrossTL validation/source semantics to the native-v0
compatibility bucket that owns follow-up work. It does not authorize parser,
CrossTL, HIR, backend, fixture-hash, target-contract, or package behavior
changes.

| ID | CrossTL validation/source semantics | Native-v0 compatibility bucket | Native-v0 report-only baseline | Evidence / stop condition |
| --- | --- | --- | --- | --- |
| `semantic.language-level-baseline` | CrossTL exposes source concepts through `language.stages.keywordSpellings`, `ast.classes`, `language.types`, and `language.intrinsics`. | `compat.language-unsupported-native-v0` | Native-v0 support is limited to the shared baseline and explicit language-level rows such as `stage.extended-graphics`, `stage.tessellation`, `stage.ray`, `decl.fn-style`, `decl.generics-traits`, and `stmt.pattern-control`. | Report-only checklist. Stop before any behavior change unless the shared spec, CrossTL snapshot, positive/negative contract fixtures, compiler frontend/HIR evidence, and target evidence are updated together. |
| `semantic.compiler-frontend-baseline` | CrossTL validation/source metadata is represented through `validation.metadata`, `validation.stageLayout`, `ast.classes`, and `language.resources.addressSpaceMetadata`. | `compat.frontend-unsupported-native-v0` | Native-v0 accepts only the documented compiler frontend subset; broader declaration, metadata, and address-space spellings remain rows such as `decl.colon-var`, `resource.metadata-aliases`, and `resource.var-address-space`. | Report-only checklist. Stop before any behavior change unless parser diagnostics, frontend/HIR acceptance evidence, and shared fixtures are updated under the compatibility row. |
| `semantic.target-legalization-baseline` | CrossTL resource/type/intrinsic facts such as `language.resources`, `language.types`, and `language.intrinsics` can describe legal source before target package support exists. | `compat.target-legalization-unsupported` | Native-v0 separates frontend legality from backend package support through rows such as `target.texture-shadow-lod`, `target.resource-arrays`, and `target.helper-array-params`. | Report-only checklist. Stop before any behavior change unless target legalization results, support-matrix planned failures or promotions, package-mode evidence, and diagnostics are updated together. |

### Language Change Policy Slices

These report-only slices are checked by
`tools/check_language_change_policy.py`. They keep future CrossTL language
changes from becoming compiler-only compatibility facts.

| Slice id | Compatibility requirement | Evidence rule |
| --- | --- | --- |
| `syntax-tightening` | Use `spec.error` and the `compat.true-spec-error` bucket when a source form becomes invalid shared CrossGL. | Add or cite a compatibility row before any diagnostic or parser behavior change. |
| `deprecation` | Use `spec.deprecated` and the `compat.deprecated-crosstl-spelling` bucket when a legacy spelling remains visible but should not gain new shared source. | Name the canonical spelling and keep the deprecated form out of new positive fixtures. |
| `source-location-requirements` | Treat source-location inventory as report-only until native source-map evidence exists. | Keep source-location handoffs tied to AST/schema and drift-review evidence instead of a compiler support claim. |

Parser and AST drift reports must complete `parser-drift-review` or
`ast-drift-review` in `docs/language/DRIFT_REVIEW.md` before proposing
behavior changes. The compatibility handoff must cite
`crosstl-snapshot-hash`, `cross-repo-fixture-impact`,
`source-location-impact`, exactly one `compatibility-bucket`, and a
`stop-condition-before-behavior-change` so parser/AST drift does not become a
compiler-only accepted syntax or source-location contract.

### CrossTL Source-Location Metadata Boundary

CrossTL `ASTNode.source_location` is frontend metadata, not a structural
compatibility field. It is excluded from structural AST compatibility and
structural AST hashing, so a stable CrossTL AST hash does not prove compiler
HIR source-map spans. Native compiler source-map, diagnostic, feature-report,
or package/debug source-location claims require compiler-owned evidence.

Compiler resource provenance must come from compiler-owned C++ `SourceLocation`
capture and HIR lowering evidence. CrossTL AST metadata cannot populate or
prove HIR resource declaration spans, layout spans, or access spans, and this
ledger does not claim new compiler source-map support for those spans.

## Shared Native-v0 Baseline

The current shared baseline is the set covered by
`tools/cross_repo_language_contract.json`: compiler fixtures in
`tests/fixtures/*.cgl` and CrossTL examples in `CrossGL-Translator/examples`
that both parse successfully, with stable CrossTL AST hashes and compiler HIR
hashes. Keep new shared forms in this positive contract when both frontends
accept them.

Native-v0 source should use these forms when portability matters:

| Source form | CrossTL v0 reference | Compiler evidence |
| --- | --- | --- |
| `shader Name { ... }` modules | `lexical.keywords[shader]`, `ast.classes.ShaderNode` | `tests/fixtures/MinimalComputeShader.cgl` |
| `vertex`, `fragment`, and `compute` stage blocks | `language.stages.keywordSpellings` with `acceptedAsStageBlock=true` | `src/Frontend/Lexer.cpp:isStageKeyword` |
| C-style functions such as `void main() { ... }` | `ast.classes.FunctionNode`, `language.types.primitive` | `tests/fixtures/MinimalComputeShader.cgl` |
| Structs, cbuffers, constants, C-style declarations, and function-body `var name: Type` local declarations | `ast.classes.StructNode`, `ConstantNode`, `VariableNode` | `tests/fixtures/StructBufferComputeShader.cgl`, `tests/fixtures/ResourceShader.cgl`, `tests/fixtures/ColonVarComputeShader.cgl` |
| `layout(set = N, binding = M[, format = F])` resources; `layout(group = N, binding = M)` as a canonical `set` alias; `layout(register = M)` as a canonical `binding` alias | `validation.metadata.singleValueNames`, `validation.metadata.singleValueAliases`, `validation.metadata.multiValueNames`, `language.resources.imageFormatMetadataNames` | `tests/frontend/fixtures/StorageImageHIRShader.cgl`, `tests/fixtures/ResourceGroupAliasShader.cgl`, `tests/fixtures/ResourceRegisterAliasShader.cgl` |
| `layout(local_size_x = ..., local_size_y = ..., local_size_z = ...) in;` | `validation.stageLayout.directionRequirements` | `tests/fixtures/MinimalComputeShader.cgl` |

## Delta Ledger

| ID | Source form | CrossTL v0 status | Compiler native-v0 status | Bucket | Owner bucket | Classification | Evidence / action |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `stage.extended-graphics` | `geometry`, `task`, `mesh`, `object`, `amplification` stage blocks | Listed in `language.stages.keywordSpellings` with `acceptedAsStageBlock=true`. | Only `vertex`, `fragment`, and `compute` are stage keywords in `src/Frontend/Lexer.cpp:isStageKeyword`; other spellings recover as unsupported shader items and can lead to no-stage errors. | `compat.language-unsupported-native-v0` | `owner.language-future-feature` | `spec.unsupported-for-native-v0` | Diagnostic evidence: `tests/check-failures/BadUnsupportedExtendedStageShader.cgl` and `cglc_check_unsupported_native_v0_extended_stage_failure`. Add frontend, HIR, and target evidence before moving this row into the shared baseline. |
| `stage.tessellation` | `tessellation_control`, `tessellation_evaluation`, plus aliases `hull` and `domain` | Listed in `language.stages.keywordSpellings`. | Not native stage keywords in `src/Frontend/Lexer.cpp:isStageKeyword`. | `compat.language-unsupported-native-v0` | `owner.language-future-feature` | `spec.unsupported-for-native-v0` | Diagnostic evidence: `tests/check-failures/BadUnsupportedTessellationStageShader.cgl` and `cglc_check_unsupported_native_v0_tessellation_stage_failure`. Treat as CrossTL-only until native stage/HIR/target contracts exist. |
| `stage.ray` | `ray_generation`, `ray_intersection`, `ray_closest_hit`, `ray_miss`, `ray_any_hit`, `ray_callable`, plus short aliases | Listed in `language.stages.canonical` and `language.stages.keywordSpellings`. | Not native stage keywords in `src/Frontend/Lexer.cpp:isStageKeyword`; canonical ray spellings recover as unsupported shader items. | `compat.language-unsupported-native-v0` | `owner.language-future-feature` | `spec.unsupported-for-native-v0` | Diagnostic evidence: `tests/check-failures/BadUnsupportedRayStageShader.cgl`, `tests/check-failures/BadUnsupportedRayIntersectionStageShader.cgl`, `tests/check-failures/BadUnsupportedRayClosestHitStageShader.cgl`, `tests/check-failures/BadUnsupportedRayMissStageShader.cgl`, `tests/check-failures/BadUnsupportedRayAnyHitStageShader.cgl`, `tests/check-failures/BadUnsupportedRayCallableStageShader.cgl`, `cglc_check_unsupported_native_v0_ray_stage_failure`, `cglc_check_unsupported_native_v0_ray_intersection_stage_failure`, `cglc_check_unsupported_native_v0_ray_closest_hit_stage_failure`, `cglc_check_unsupported_native_v0_ray_miss_stage_failure`, `cglc_check_unsupported_native_v0_ray_any_hit_stage_failure`, and `cglc_check_unsupported_native_v0_ray_callable_stage_failure`. CrossTL AST and intrinsic metadata exist; native compiler has no ray-stage frontend/HIR lane yet. |
| `stage.kernel-alias` | `kernel { ... }` as a compute-stage spelling | `kernel` is tokenized and canonicalized to `compute` in `language.stages.keywordSpellings`, but the snapshot marks it with `acceptedAsStageBlock=false`. | Not a native stage keyword in `src/Frontend/Lexer.cpp:isStageKeyword`. Use `compute`. | `compat.deprecated-crosstl-spelling` | `owner.language-compatibility-policy` | `spec.deprecated` | Evidence reference: `docs/language/crosstl-frontend-language-spec-v0.json`. Do not add new compiler fixtures with `kernel` stage blocks. |
| `decl.fn-style` | `fn main() { ... }`, `fn name<T>(...) -> T`, async/unsafe function qualifiers | `FUNCTION` token exposure and function AST facts are in `lexical.tokens` and `ast.classes`. | Parser emits `parse.unsupported-rust-function` from `src/Frontend/Parser.cpp` and skips fn-style declarations. | `compat.language-unsupported-native-v0` | `owner.language-future-feature` | `spec.unsupported-for-native-v0` | Diagnostic evidence: `tests/check-failures/BadUnsupportedFnStyleShader.cgl` and `cglc_check_unsupported_native_v0_fn_style_failure`. Use C-style `void main()` in shared fixtures. |
| `decl.colon-var` | `var name: Type` and `var name: Type = expr` variable declarations | Variable declaration AST/type facts are present in `ast.classes` through `VariableNode` and in `language.types`. | Function-body colon-style local declarations are accepted and canonicalized to HIR local declarations; stage-scope unqualified colon-style `var` remains rejected because it does not map to a resource or shared-memory declaration. | `compat.frontend-unsupported-native-v0` | `owner.compiler-frontend-subset-limit` | `spec.unsupported-for-native-v0` | Accepted evidence for function-body locals: `tests/fixtures/ColonVarComputeShader.cgl` and `cglc_check_colon_var_compute_hir_canonical_declaration`. Diagnostic evidence for stage-scope unqualified `var`: `tests/check-failures/BadUnsupportedColonVarShader.cgl` and `cglc_check_unsupported_native_v0_colon_var_failure`. |
| `decl.generics-traits` | `generic`, `<T>`, `where`, `trait`, `impl`, trait constraints | Generic and trait AST facts are present in `ast.classes`. | Generic structs are partially recovered; generic functions, traits, and impl blocks are skipped or unsupported by `src/Frontend/Parser.cpp`. | `compat.language-unsupported-native-v0` | `owner.language-future-feature` | `spec.unsupported-for-native-v0` | Diagnostic evidence: `cglc_check_unsupported_native_v0_generic_failure`, `cglc_check_unsupported_native_v0_trait_failure`, and `cglc_check_unsupported_native_v0_impl_failure`; `tools/check_cross_repo_language_contract.py` records the CrossTL-only generic-pattern example exclusion for this family. |
| `stmt.pattern-control` | `match`, patterns, `for name in expr`, `loop`, `do while`, `switch/case/default`, `let mut` | Statement and pattern AST facts are present in `ast.statementNodes` and `ast.classes`. | Native lowering focuses on C-style declarations, `if`, `for`, `while`, `return`, assignments, and expression calls used by current fixtures. | `compat.language-unsupported-native-v0` | `owner.language-future-feature` | `spec.unsupported-for-native-v0` | Diagnostic evidence: `tests/check-failures/BadUnsupportedMatchShader.cgl`, `tests/check-failures/BadUnsupportedSwitchShader.cgl`, `tests/check-failures/BadUnsupportedForInShader.cgl`, `tests/check-failures/BadUnsupportedLoopShader.cgl`, `tests/check-failures/BadUnsupportedDoWhileShader.cgl`, `tests/check-failures/BadUnsupportedLetMutShader.cgl`, `tests/check-failures/BadMalformedIfHeaderShader.cgl`, `tests/check-failures/BadMalformedWhileHeaderShader.cgl`, `tests/check-failures/BadMalformedForHeaderShader.cgl`, `cglc_check_unsupported_native_v0_match_failure`, `cglc_check_unsupported_native_v0_switch_failure`, `cglc_check_unsupported_native_v0_for_in_failure`, `cglc_check_unsupported_native_v0_loop_failure`, `cglc_check_unsupported_native_v0_do_while_failure`, `cglc_check_unsupported_native_v0_let_mut_failure`, `cglc_check_unsupported_native_v0_malformed_if_header_failure`, `cglc_check_unsupported_native_v0_malformed_while_header_failure`, and `cglc_check_unsupported_native_v0_malformed_for_header_failure`. Keep pattern/control-flow forms CrossTL-only until native HIR lowering and support are added. |
| `decl.import-preprocessor` | `import`, `use`, `from ... import ...`, preprocessor nodes | Import and preprocessor facts are present in `lexical.tokens` and `ast.classes`. | Native compiler does not model imports and only supports comments/ordinary tokens in `.cgl` source. | `compat.language-unsupported-native-v0` | `owner.language-future-feature` | `spec.unsupported-for-native-v0` | Diagnostic evidence: `cglc_check_unsupported_native_v0_import_failure` and `cglc_check_unsupported_native_v0_preprocessor_failure`. Package/import semantics need a separate compiler contract before shared use. |
| `decl.line-splicing-preprocessor` | Backslash-newline physical line splicing before preprocessing, including continued preprocessor directives | The sealed snapshot records the affected lexical inventory through `lexical.tokens` and `lexical.skipTokens`; no standalone shared grammar production or token is sealed for line splicing. | Native `.cgl` does not model preprocessor/importer syntax or promise physical-line splicing as shared source behavior. | `compat.language-unsupported-native-v0` | `owner.language-future-feature` | `spec.unsupported-for-native-v0` | Diagnostic evidence: `tests/check-failures/BadUnsupportedLineSplicingPreprocessorShader.cgl` and `cglc_check_unsupported_native_v0_line_splicing_preprocessor_failure`. Treat backslash-newline continuation as translator/importer preprocessing tolerance until a future shared language slice adds positive fixtures, diagnostics, and frontend/HIR evidence. |
| `resource.metadata-aliases` | `group` as `set`; scalar `register` as `binding`; broader aliases such as HLSL tuple-style `register(...)`, HLSL/GLSL builtins such as `SV_Position`/`gl_Position`, and interpolation aliases | Metadata aliases are listed in `validation.metadata` and `language.resources.builtinSemanticMetadata`. | Native resource layout in `src/Frontend/Parser.cpp` accepts `set`, `group` as `set`, `binding`, scalar `register` as `binding`, and storage-image `format`; unsupported layout keys are ignored with warnings. Conflicting `binding` and `register` values produce `parse.conflicting-resource-binding`. | `compat.frontend-unsupported-native-v0` | `owner.compiler-frontend-subset-limit` | `spec.unsupported-for-native-v0` | Accepted evidence: `tests/fixtures/ResourceGroupAliasShader.cgl`, `tests/fixtures/ResourceRegisterAliasShader.cgl`, `cglc_check_resource_group_layout_alias_hir_canonical_set`, `cglc_check_resource_register_layout_alias_hir_canonical_binding`, and `cglc_build_directx_resource_register_layout_alias_source_package`. Diagnostic evidence for broader aliases and conflicts: `tests/check-failures/BadUnsupportedResourceMetadataAliasShader.cgl`, `tests/check-failures/BadConflictingRegisterBindingShader.cgl`, `tests/check-failures/BadConflictingRegisterBindingReverseShader.cgl`, `cglc_check_unsupported_native_v0_resource_metadata_alias_failure`, `cglc_check_conflicting_register_binding_failure`, and `cglc_check_conflicting_register_binding_reverse_failure`. Prefer explicit `layout(set = ..., binding = ...)` in shared native-v0 source unless testing alias compatibility. |
| `resource.var-address-space` | `var<address-space>` resource declarations and address-space aliases | Address-space metadata is listed in `language.resources.addressSpaceMetadata`. | Native stage-scope `var<...>` accepts only workgroup/shared storage in `src/Frontend/Parser.cpp`; other address spaces produce `parse.unsupported-var-address-space` naming the rejected spelling. | `compat.frontend-unsupported-native-v0` | `owner.compiler-frontend-subset-limit` | `spec.unsupported-for-native-v0` | Diagnostic evidence: `tests/check-failures/BadUnsupportedVarAddressSpaceShader.cgl` and `cglc_check_unsupported_native_v0_var_address_space_failure`. Shared compiler fixtures may use `var<workgroup>` only. |
| `compat.input-output-names` | `input`/`output` used as declaration names | `input` and `output` are not CrossTL keywords in `lexical.keywords`. | Native lexer treats `input` and `output` as keyword-like name tokens in declaration positions in `src/Frontend/Lexer.cpp` for compatibility. | `compat.deprecated-crosstl-spelling` | `owner.language-compatibility-policy` | `spec.deprecated` | Evidence reference: `src/Frontend/Lexer.cpp`. Avoid new shared source that depends on these spellings as identifiers. |
| `sema.no-stage-or-entry` | Shader modules with no supported stages, or stages with no entry function | Invalid shared source; this is not a CrossTL acceptance claim. | Rejected by `cglc check`. | `compat.true-spec-error` | `owner.language-error` | `spec.error` | Covered by `tests/check-failures/BadNoStagesShader.cgl`, `tests/check-failures/BadEmptyStageShader.cgl`, `cglc_check_no_stages_failure`, and `cglc_check_empty_stage_failure`. |
| `sema.array-shape` | Zero, negative, boolean, overflow, expression, or unresolved array sizes where a fixed positive size is required | Invalid shared source for native-v0 HIR; this is not a CrossTL acceptance claim. | Rejected by `cglc check`. | `compat.true-spec-error` | `owner.language-error` | `spec.error` | Covered by `tests/check-failures/BadZeroArraySizeShader.cgl`, `tests/check-failures/BadNegativeArraySizeShader.cgl`, `tests/check-failures/BadBoolArraySizeShader.cgl`, `tests/check-failures/BadOverflowArraySizeShader.cgl`, and `tests/check-failures/BadExpressionArraySizeShader.cgl`. |
| `sema.resource-layout` | Duplicate resources/bindings, shared resource bindings, invalid storage-image format/access/arity | Invalid shared source for native-v0 HIR; this is not a CrossTL acceptance claim. | Rejected by `cglc check`. | `compat.true-spec-error` | `owner.language-error` | `spec.error` | Covered by `tests/check-failures/DuplicateResourceShader.cgl`, `tests/check-failures/DuplicateBindingShader.cgl`, `tests/check-failures/BadSharedResourceBindingShader.cgl`, and `tests/check-failures/BadStorageImageFormatLayoutShader.cgl`. |
| `target.texture-shadow-lod` | Shadow texture LOD source forms | Texture compare and LOD intrinsic facts are represented in `language.intrinsics`. | Frontend source can parse these forms, but target validation policy remains backend-specific where direct native paths require support evidence or manual kernels. | `compat.target-legalization-unsupported` | `owner.target-legalization-limit` | `target.unsupported` | Planned-failure compatibility row: `target.texture-shadow-lod`. Existing fixtures include `TextureArrayShadowCompareLodUnsupportedShader.cgl`, `Texture2DArrayShadowCompareLodUnsupportedShader.cgl`, `TextureCubeShadowCompareLodUnsupportedShader.cgl`, `TextureCubeArrayShadowCompareLodUnsupportedShader.cgl`, `TextureArrayCompareDescriptorArrayLodShader.cgl`, and `TextureCubeCompareDescriptorArrayLodShader.cgl`. OpenGL source-package evidence now covers the descriptor-array slice with `cglc_build_opengl_texture_array_compare_descriptor_array_lod_source_package` and `cglc_build_opengl_texture_cube_compare_descriptor_array_lod_source_package`. |
| `target.resource-arrays` | Runtime/unsized resource arrays and backend-specific descriptor-array forms | Resource and array facts are represented in `language.resources` and `language.types`. | Frontend source can parse supported shapes, but target legality differs by backend. | `compat.target-legalization-unsupported` | `owner.target-legalization-limit` | `target.unsupported` | Existing fixtures include `RuntimeResourceArrayUnsupportedShader.cgl`, `StorageBufferUnsizedDescriptorArrayUnsupportedShader.cgl`, `MetalStorageBufferArrayUnsupportedShader.cgl`, and `VulkanTextureSamplerArrayAccessUnsupportedShader.cgl`. Planned-failure evidence: `cglc_build_directx_runtime_texture_resource_array_conflict_planned_failure`, `cglc_build_opengl_runtime_resource_array_planned_failure`, and `cglc_build_opengl_unsized_storage_buffer_array_planned_failure`. |
| `target.helper-array-params` | Function parameter arrays requiring backend helper lowering | Function and array facts are represented in `ast.classes` and `language.types`. | Frontend source can parse supported shapes, but some backends reject dynamic nested writes/reads or resource/struct helper arrays. | `compat.target-legalization-unsupported` | `owner.target-legalization-limit` | `target.unsupported` | Existing fixtures include `VulkanFunctionParameterArrayUnsupportedShader.cgl`, `DirectXFunctionParameterArrayUnsupportedShader.cgl`, and `OpenGLDynamicNestedLocalFunctionParameterArrayUnsupportedShader.cgl`. Planned-failure evidence: `cglc_build_vulkan_function_parameter_array_planned_failure` and `cglc_build_opengl_function_parameter_resource_array_planned_failure`. |

## Update Rules

When a source form moves between buckets:

1. Update this ledger row first, including the CrossTL spec path and compiler
   fixture or diagnostic evidence.
2. If both frontends accept the form, add or update a positive fixture so
   `tools/cross_repo_language_contract.json` records stable CrossTL AST and
   compiler HIR hashes.
3. If the compiler rejects the form, keep or add a focused `tests/check-failures`
   fixture with an expected diagnostic.
4. If only a backend rejects the form, keep the frontend fixture positive and
   put the failing target in a target-specific unsupported fixture or package
   legality check.
