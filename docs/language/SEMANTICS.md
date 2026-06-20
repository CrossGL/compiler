# CrossGL v0 Semantics Guide

This page states the v0 semantic baseline in prose. It is grounded in the
CrossTL frontend snapshot, the native compiler compatibility ledger, the
cross-repo fixture contract, and package support evidence. It does not promote
the full CrossTL surface to native compiler support.

## Layers

| Layer | What it means | Where it is recorded |
| --- | --- | --- |
| CrossTL accepted | The CrossTL lexer/parser/AST/validation surface exposes the form. | `crosstl-frontend-language-spec-v0.json` and generated `SPEC.md`. |
| Native-v0 baseline | The native compiler accepts the form in fixture-scoped HIR/frontend evidence. | `COMPATIBILITY.md`, `V0_SUPPORT.md`, and `tools/cross_repo_language_contract.json`. |
| Accepted but unsupported | CrossTL accepts or exposes the form, but native-v0 does not claim it. | `COMPATIBILITY.md` rows marked `spec.unsupported-for-native-v0`. |
| Target-specific unsupported | The frontend accepts the source, but a backend must reject package emission. | `COMPATIBILITY.md` rows marked `target.unsupported` and support-matrix planned failures. |
| Invalid shared source | The form should be rejected before backend emission. | `COMPATIBILITY.md` rows marked `spec.error` plus check-failure fixtures. |

## Semantic Baseline Checklist

Use this checked checklist before proposing any semantic support change. It is
report-only: it classifies evidence and stop conditions, but it does not
authorize syntax changes, parser recovery changes, fixture-hash changes, target
contract changes, package behavior changes, or CrossTL behavior changes. The
rows use the same machine-readable semantic baseline IDs and compatibility
buckets as `COMPATIBILITY.md`. The compatibility checker command
(`tools/check_language_compatibility.py` with `--root .`) fails closed if this
guide drifts from those owner buckets or stops citing concrete ledger evidence.

| ID | CrossTL validation/source semantics | Native-v0 compatibility bucket | Native-v0 report-only baseline | Evidence / stop condition |
| --- | --- | --- | --- | --- |
| `semantic.language-level-baseline` | CrossTL snapshot facts such as `language.stages.keywordSpellings`, `ast.classes`, `language.types`, and `language.intrinsics` expose the source concept. | `compat.language-unsupported-native-v0` | CrossTL-exposed forms that are not in the native-v0 shared language subset stay report-only rows such as `stage.extended-graphics`, `stage.tessellation`, `stage.ray`, `decl.fn-style`, `decl.generics-traits`, and `stmt.pattern-control`. | Report-only checklist. Stop before any behavior change unless a `docs/language/COMPATIBILITY.md` language-level row, CrossTL/shared grammar update, positive contract fixture, compiler frontend/HIR evidence, and target evidence are updated together. |
| `semantic.compiler-frontend-baseline` | CrossTL validation facts such as `validation.metadata`, `validation.stageLayout`, `ast.classes`, and `language.resources.addressSpaceMetadata` may allow broader spellings. | `compat.frontend-unsupported-native-v0` | Native-v0 keeps narrower accepted spellings or reports/skips broader CrossTL spellings through report-only rows such as stage-scope unqualified `decl.colon-var`, `resource.metadata-aliases`, and `resource.var-address-space`. | Report-only checklist. Stop before any behavior change unless a `docs/language/COMPATIBILITY.md` compiler-frontend row plus focused parser/HIR/diagnostic evidence are updated before promoting the spelling into shared fixtures. |
| `semantic.target-legalization-baseline` | CrossTL and native frontend/HIR source may be legal through resource/type/intrinsic facts such as `language.resources`, `language.types`, and `language.intrinsics` while target-specific package emission still differs by backend. | `compat.target-legalization-unsupported` | Frontend-legal forms that require target diagnostics or planned package failures stay report-only rows such as `target.texture-shadow-lod`, `target.resource-arrays`, and `target.helper-array-params`. | Report-only checklist. Stop before any behavior change unless a `docs/language/COMPATIBILITY.md` target row plus target legalization, support-matrix, package-mode, and diagnostic evidence are updated before claiming backend support. |

## Source-Location Metadata Boundary

CrossTL `ASTNode.source_location` is frontend metadata only. It is excluded from
structural AST compatibility and structural AST hashing, and it does not prove
compiler HIR source-map spans. Native compiler source-map, diagnostic,
feature-report, package/debug, or resource provenance claims require
compiler-owned evidence instead of CrossTL AST metadata.

## Module Semantics

A native-v0 shader module is valid only when it contains at least one supported
stage with an entry function. The baseline supported stages are `vertex`,
`fragment`, and `compute`. The compiler contract is strongest for compute; the
graphics package surface is limited to named fixture rows in
`docs/SUPPORT_MATRIX_EVIDENCE.md`.

CrossTL exposes additional stage concepts for geometry, mesh/task/object,
tessellation, and ray tracing. Those stage blocks are accepted/exposed CrossTL
surface but unsupported for native-v0. A native compiler path must not treat
their presence as backend-ready support unless future HIR and target evidence
are added.

## Declaration and Name Semantics

Native-v0 source uses C-style declarations and functions:

- functions are declared as `<type> name(parameters) { ... }`;
- shader resources and globals use ordinary typed declarations plus optional
  layout metadata;
- structs, constants, cbuffers, and local variables are supported only in the
  forms covered by fixtures and compatibility evidence.

CrossTL also exposes Rust-like `fn` declarations, generic declarations, traits,
impl blocks, imports, preprocessors, enums, and pattern declarations. These are
not native-v0 compiler semantics. The native compiler may reject or recover
from them, but they must remain out of new shared native-v0 fixtures until the
compatibility ledger is updated.

The names `input` and `output` are deprecated compatibility spellings when used
as declaration names in the native compiler. New shared source should avoid
depending on them as identifiers.

## Type Semantics

Native-v0 type support is fixture scoped:

| Type area | v0 semantics |
| --- | --- |
| Scalars, vectors, matrices | Supported where parser/HIR fixtures and target evidence cover the operations used. |
| Structs | Supported for non-recursive, fixture-covered field shapes and storage-buffer layouts. |
| Fixed arrays | Must have valid positive sizes in contexts that require fixed size. |
| Runtime-tail arrays | Supported only in documented storage-buffer/resource forms with target evidence. |
| Texture/sampler/storage image/buffer types | Supported only for the resource operations and target modes named by fixtures. |
| Pointer, reference, function, and generic types | CrossTL surface only for native-v0 unless future evidence names exact support. |

Invalid array sizes, unresolved fixed sizes, unsupported recursive storage
buffer structs, invalid storage-image coordinate/payload shapes, and invalid
vector/scalar combinations are shared source errors when covered by
check-failure fixtures.

## Resource and Layout Semantics

Portable native-v0 resources should use explicit layout metadata:

```text
layout(set = N, binding = M)
layout(set = N, binding = M, format = F)
layout(local_size_x = X, local_size_y = Y, local_size_z = Z) in;
```

The compiler uses `set` and `binding` for resource identity and storage-image
`format` for explicit storage image layout where required. Duplicate resources,
duplicate bindings, shared resource bindings, invalid storage-image access,
invalid storage-image format, and invalid storage-image operation arity are
`spec.error` in native-v0.

CrossTL exposes broader metadata, including HLSL/GLSL semantic aliases,
interpolation metadata, memory-layout metadata, `group`, and address-space
aliases. Those facts do not imply native-v0 support. `var<workgroup>`/shared
storage is the shared compiler fixture form; other `var<address-space>` forms
remain unsupported for native-v0 unless evidence is added.

Resource declaration, layout, and access provenance must come from
compiler-owned C++ `SourceLocation` capture and HIR lowering. CrossTL
`source_location` metadata cannot populate or prove HIR resource declaration,
layout, or access spans, and this guide does not claim new compiler source-map
support for those spans.

## Statement and Control Semantics

Native-v0 baseline control flow includes:

- lexical blocks and scoped declarations;
- assignments and expression statements;
- `if`/`else`;
- C-style `for`;
- `while`;
- `return`;
- `break` and `continue` inside loops.

`break` and `continue` outside loops are invalid shared source. `discard` is
only valid where the compiler and target evidence support it; top-level or
compute-invalid uses are rejected by current check-failure fixtures.

CrossTL exposes pattern matching, `for in`, `loop`, `do while`,
`switch/case/default`, and broader sync nodes. These are accepted/exposed
CrossTL forms, not native-v0 baseline semantics.

## Expression and Intrinsic Semantics

Native-v0 expression support includes fixture-covered arithmetic, comparisons,
constructors, casts, swizzles, member access, array access, scalar/vector
intrinsics, texture/sample operations, storage-image operations, buffer
operations, and scalar integer atomics.

The following are semantic guardrails:

- constructors must match supported scalar/vector shapes;
- swizzles must use valid component sets and widths;
- texture/sample calls must match texture, sampler, coordinate, compare, LOD,
  offset, and manual-kernel requirements;
- `nonuniform` markers must appear only in accepted descriptor-index contexts;
- storage-image operations must use supported image types, access qualifiers,
  coordinate shapes, payload types, and atomic forms;
- atomic operations are limited to scalar integer storage-buffer/workgroup and
  storage-image forms named by support evidence.

CrossTL exposes wave, ray tracing, ray query, mesh, lambda, pointer-access, and
range expression nodes. These are unsupported for native-v0 unless future
fixture and target evidence names exact semantics.

## Target-Specific Semantics

Frontend acceptance is not package support. Package mode is target-specific:

| Target family | Current v0 package meaning |
| --- | --- |
| DirectX | Source-package support where support rows name the form; optional native validator evidence can strengthen the row. |
| OpenGL | Source-package support where support rows name the form; optional validator evidence can strengthen the row. |
| Metal | Native package support only where native rows and optional tool behavior support the form. |
| Vulkan | Native package support only where native rows and optional tool behavior support the form. |

Target-limited legal source must fail with structured diagnostics for targets
that lack support. Examples include some shadow texture LOD forms, runtime or
unsized resource arrays, and helper array parameter lowering cases. Planned
package failures in support evidence are rejection coverage, not partial
support.

## Error Semantics

The v0 native compiler must reject, warn, or fail package emission according to
the compatibility class:

| Class | Expected behavior |
| --- | --- |
| `spec.error` | Reject before backend emission, typically through `cglc check`. |
| `spec.unsupported-for-native-v0` | Reject or recover with diagnostics; do not silently claim native support. |
| `spec.deprecated` | Accept only for compatibility and avoid in new shared fixtures. |
| `target.unsupported` | Accept frontend source when legal, then reject unsupported target emission with target diagnostics. |

Do not infer native-v0 support from CrossTL acceptance alone. A source form
becomes supported only after the compatibility ledger, cross-repo contract, and
support evidence are updated together.
