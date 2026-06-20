<!-- crossgl-crosstl-language-coverage-matrix-v1 -->

# CrossTL vs. Compiler Language Coverage Matrix

This is a bounded implementation matrix for the native CrossGL-Compiler
frontend and HIR pipeline. The CrossTL frontend/spec is the language authority;
compiler coverage is a versioned implementation matrix that records the
currently supported intersection, target-limited areas, and planned gaps. This
document does not change parser behavior, HIR lowering, target support, or the
shared CrossTL contract manifests.

Read this matrix with:

- `docs/language/crosstl-frontend-language-spec-v0.json`: sealed CrossTL
  frontend/spec snapshot, structurally validated by
  `docs/schemas/crosstl-frontend-language-spec-v0.schema.json`.
- `docs/language/COMPATIBILITY.md`: known CrossTL-vs-native-v0 deltas,
  including the ledger bucket and owner bucket for planned coverage fixtures.
- `docs/language/V0_SUPPORT.md`: fixture-scoped v0 support contract.
- `tools/cross_repo_language_contract.json`: shared CrossTL AST and compiler
  HIR hash contract for accepted cross-repo fixtures.
- `tools/cross_repo_language_spec.json`: shared feature map, structurally
  validated by `docs/schemas/cross-repo-language-spec-v1.schema.json`.

## Status Labels

| Label | Meaning |
| --- | --- |
| Compiler-supported | `cglc check` and post-pass HIR accept the form in current fixtures or the coverage fixture inventory below. Target package support may still be narrower. |
| Target-limited | The compiler frontend/HIR accepts the form, but one or more backend/package paths reject it with target diagnostics or planned-failure evidence. |
| Planned | CrossTL exposes the form, but native-v0 compiler support is intentionally absent until parser, HIR, diagnostics, and target contracts are added. |
| Spec error | Invalid shared CrossGL source that should be rejected before target emission. |

## Coverage Matrix

| Area | Compiler-supported intersection | Planned or outside native-v0 |
| --- | --- | --- |
| Modules and stages | `shader Name { ... }` modules with `vertex`, `fragment`, and `compute` stage blocks. Compute stages may declare `layout(local_size_x = X, local_size_y = Y, local_size_z = Z) in;`. Stage entry functions use C-style declarations such as `void main()` or typed graphics `main` functions. | CrossTL exposes geometry, tessellation, hull/domain, mesh/task/object/amplification, and ray-stage spellings. The `kernel` spelling is a deprecated CrossTL compatibility alias; shared compiler fixtures should use `compute`. |
| Declarations | C-style functions, structs, constants, cbuffers, stage resources, local variables, and C-style parameters. Struct fields may use either `type name;` or `name: type` forms. | `fn` declarations, generic declarations, `where` clauses, traits, impl blocks, imports, source preprocessor nodes, and pattern-bearing declaration forms are planned native-v0 gaps. |
| Scalar, vector, and matrix types | `void`, `bool`, `int`, `uint`, `float`, `double`, `half`; `vec2`/`vec3`/`vec4`; `ivec2`/`ivec3`/`ivec4`; `uvec2`/`uvec3`/`uvec4`; `bvec2`/`bvec3`/`bvec4`; `mat2`/`mat3`/`mat4`; `mat2x2`/`mat3x3`/`mat4x4`; named structs; fixed arrays; documented runtime-tail storage-buffer arrays; `atomic<int>` and `atomic<uint>`. | CrossTL exposes a broader primitive and matrix inventory, pointer/reference/function/generic type nodes, and additional image/texture aliases. These are planned unless compatibility evidence names a compiler-supported subset. |
| Resources | `uniform` and `buffer` resources, cbuffers, `shared`/`var<workgroup>` storage, descriptor arrays with numeric or folded-constant sizes, storage buffers using pointer spelling such as `buffer float* values`, texture resources, sampler resources, and storage images. | Broad HLSL resource-buffer families, UAV aliases, most address spaces other than workgroup/shared spellings, and CrossTL metadata-only resource forms are planned. |
| Texture and sampler types | `sampler`, `comparison_sampler`, `sampler2D`, `sampler2DArray`, `sampler3D`, `samplerCube`, `samplerCubeArray`, shadow sampler variants, signed/unsigned integer sampler variants, and separate texture forms `texture2D`, `texture2DArray`, `texture3D`, `textureCube`, `textureCubeArray`. | CrossTL exposes more texture/image dimensions and aliases, including 1D/MS-style families. Native-v0 only claims the fixture-backed subset above. |
| Storage image types | `image2D`, `iimage2D`, `uimage2D`, `image2DArray`, `iimage2DArray`, and `uimage2DArray`, including descriptor arrays and `readonly`/`writeonly`/`readwrite` qualifiers where covered. | Other CrossTL image dimensions, multisample image families, and unsupported storage-image format metadata are planned. |
| Layout and metadata | Resource layout keys `set`, `group` as a canonical alias for `set`, `binding`, scalar `register` as a canonical alias for `binding`, and storage-image `format`; compute layout keys `local_size_x`, `local_size_y`, `local_size_z`; storage-image formats `rgba32f`, `rgba32i`, `rgba32ui`, `r32f`, `r32i`, and `r32ui`; `readonly`, `writeonly`, and `readwrite`. | CrossTL metadata forms such as HLSL tuple-style `register(...)`, interpolation metadata, HLSL/GLSL semantic metadata, memory-layout metadata, and broad address spaces are planned compiler gaps unless a later row promotes them. |
| Statements and control flow | Blocks, C-style and function-body colon-style local declarations, assignments, expression statements, `if`/`else`, C-style `for`, `while`, `return`, `break`, `continue`, and fragment `discard` where stage-valid. | `match`, patterns, `for name in expr`, `loop`, `do while`, `switch`/`case`/`default`, `let mut`, stage-scope unqualified colon-style `var` declarations, and CrossTL sync/control nodes outside the HIR contract are planned. |
| Expressions | Literals, identifiers, member access, swizzles, array indexing, unary/binary operators, ternary select, constructors/casts, calls, nonuniform descriptor indexing, and read/modify/write assignment forms in current fixtures. | Lambda, range, pattern, wave, ray-query, ray-tracing, mesh operation, and broader resource-operation nodes are CrossTL surface only until native diagnostics and HIR lowering exist. |
| Math intrinsics | `abs`, `atan`, `ceil`, `clamp`, `cos`, `cross`, `distance`, `dot`, `floor`, `fract`, `length`, `max`, `min`, `mix`, `normalize`, `pow`, `reflect`, `sin`, `sqrt`, and `tan` through the HIR intrinsic registry. | CrossTL may expose additional frontend intrinsic names. A name is not compiler-supported until it has HIR inference/validation and fixture evidence. |
| Texture/image intrinsics | `texture`, `textureLod`, `textureCompare`, `textureCompareLod`, `textureCompareLodManual`, `textureCompareLodManualGather2x2`, `textureCompareLodManualKernel`, `textureCompareLodManualKernel4`, `textureCompareLodManualKernel8`, `textureCompareLodManualOffset`, `imageLoad`, `imageStore`, `imageAtomicAdd`, `imageAtomicExchange`, `imageAtomicMin`, `imageAtomicMax`, `imageAtomicAnd`, `imageAtomicOr`, and `imageAtomicXor`. | CrossTL exposes additional image and texture operations such as compare-and-swap and broader coordinate/resource forms. Unsupported arities, operand kinds, formats, and target paths remain diagnostic coverage, not support. |
| Atomic and synchronization intrinsics | `atomicAdd`, `atomicMin`, `atomicMax`, `atomicExchange`, `atomicAnd`, `atomicOr`, `atomicXor`, `workgroupBarrier`, and compatibility `barrier`. | Atomic payloads outside scalar `int`/`uint` storage and CrossTL wave/ray/mesh synchronization families are planned gaps. |

## Planned Gap Families

These planned rows are not failures in the CrossTL frontend/spec. They are
native-v0 implementation gaps that need explicit compiler work before they move
into the supported intersection.

| Compatibility id | CrossTL form | Native-v0 compiler state |
| --- | --- | --- |
| `stage.extended-graphics` | Geometry, tessellation, mesh/task/object/amplification, and ray stage blocks. | Planned. Current compiler stage keywords are `vertex`, `fragment`, and `compute`. |
| `decl.fn-style` | `fn`, generic functions, trailing return syntax, and Rust-like function forms. | Planned. Current shared source uses C-style functions. |
| `decl.generics-traits` | Generic declarations, traits, impls, and constraints. | Planned. Native-v0 has no monomorphization or trait/impl lowering contract. |
| `stmt.pattern-control` | `match`, patterns, `for in`, `loop`, `do while`, `switch/case/default`, and related control nodes. | Planned. Current HIR supports the C-style control subset above. |
| `decl.import-preprocessor` | `import`, `use`, `from ... import ...`, and preprocessor nodes. | Planned. Native-v0 does not resolve source imports or preserve preprocessor semantics. |
| `decl.line-splicing-preprocessor` | Backslash-newline physical line splicing before preprocessor/importer tokenization. | Planned. Native-v0 reports this as unsupported translator/importer tolerance, not shared `.cgl` syntax. |
| `resource.metadata-aliases` | HLSL tuple-style `register(...)`, interpolation metadata, semantics such as `SV_Position`/`gl_Position`, and memory-layout metadata; `group` is accepted as the `set` resource-layout alias and scalar `register = N` is accepted as the `binding` alias. | Planned for forms beyond `group` and scalar `register`. Portable compiler source should prefer explicit `layout(set = ..., binding = ...)` unless testing alias compatibility. |
| `resource.var-address-space` | Broad `var<address-space>` declarations and address-space aliases. | Planned except for workgroup/shared spellings used as stage-scope shared storage. |
| `target.texture-shadow-lod` | Shadow texture LOD source forms. | Target-limited. Frontend/HIR may accept selected forms while target package paths reject unsupported forms. |
| `target.resource-arrays` | Runtime/unsized resource arrays and backend-specific descriptor-array forms. | Target-limited. Package evidence decides target support. |
| `target.helper-array-params` | Function parameter arrays requiring backend helper lowering. | Target-limited. Some backends reject dynamic nested read/write or resource/struct helper arrays. |

## Fixture Inventory

The fixtures in `tests/language-spec/fixtures/coverage` are documentation
fixtures. The manifest gives each fixture an explicit cross-repo contract
disposition and conformance disposition so documentation coverage cannot drift
outside `tools/cross_repo_language_contract.json` and
`tests/conformance/manifest.v0.json` visibility. Supported coverage fixtures
point at accepted contract and conformance feature buckets. Planned fixtures
point at negative contract/conformance stubs and stay negative-only until
accepted AST/HIR and package evidence exists. The checker below verifies that
every fixture is listed, that every fixture has those dispositions, that the
manifest pins the same CrossTL source-file seal as
`docs/language/crosstl-frontend-language-spec-v0.json`, that each planned
fixture names exactly one compatibility id, records its ledger bucket and owner
bucket, resolves those values to the `docs/language/COMPATIBILITY.md` Delta
Ledger row for that id, and records diagnostic evidence for that id with
severity, code, and message substring.

| Fixture | Status | Purpose |
| --- | --- | --- |
| `tests/language-spec/fixtures/coverage/supported/coverage_compute_core.cgl` | Compiler-supported | Compute module with constants, structs, storage buffers, `var<workgroup>`, compute builtins, C-style `if`/`for`/`while`, math intrinsics, and barriers. |
| `tests/language-spec/fixtures/coverage/supported/coverage_graphics_core.cgl` | Compiler-supported | Vertex/fragment stage intersection with structs, typed entry functions, texture/sampler resources, and `texture(...)`. |
| `tests/language-spec/fixtures/coverage/supported/coverage_colon_var.cgl` | Compiler-supported | Function-body `decl.colon-var` local declarations aligned with CrossTL `VariableNode` spelling and accepted compiler HIR evidence in `tests/fixtures/ColonVarComputeShader.cgl`. |
| `tests/language-spec/fixtures/coverage/supported/coverage_numeric_literals.cgl` | Compiler-supported | Scientific decimal float literals and hexadecimal float literals aligned with CrossTL `FLOAT_NUMBER` spellings; accepted contract/conformance evidence is mirrored in `tests/fixtures/NumericFloatLiteralShader.cgl`. |
| `tests/language-spec/fixtures/coverage/supported/coverage_resources_intrinsics.cgl` | Compiler-supported | Descriptor arrays, `group` resource-layout aliasing, storage images, explicit storage-image format metadata, `imageLoad`/`imageStore`, image atomics, storage-buffer atomics, and `textureLod`. |
| `tests/language-spec/fixtures/coverage/supported/coverage_register_layout_alias.cgl` | Compiler-supported | Scalar `layout(register = N)` resource binding alias aligned with accepted compiler HIR evidence in `tests/fixtures/ResourceRegisterAliasShader.cgl`. |
| `tests/language-spec/fixtures/coverage/planned-unsupported/coverage_planned_extended_stage.cgl` | Planned | Documents extended stage spellings as `stage.extended-graphics`. |
| `tests/language-spec/fixtures/coverage/planned-unsupported/coverage_planned_fn_style.cgl` | Planned | Documents `fn` declaration forms as `decl.fn-style`. |
| `tests/language-spec/fixtures/coverage/planned-unsupported/coverage_planned_generics_traits.cgl` | Planned | Documents generic declaration forms as `decl.generics-traits`. |
| `tests/language-spec/fixtures/coverage/planned-unsupported/coverage_planned_import_preprocessor.cgl` | Planned | Documents import and preprocessor forms as `decl.import-preprocessor`. |
| `tests/language-spec/fixtures/coverage/planned-unsupported/coverage_planned_line_splicing_preprocessor.cgl` | Planned | Documents backslash-newline preprocessor/importer tolerance as `decl.line-splicing-preprocessor`. |
| `tests/language-spec/fixtures/coverage/planned-unsupported/coverage_planned_pattern_control.cgl` | Planned | Documents match/pattern forms as `stmt.pattern-control`. |
| `tests/language-spec/fixtures/coverage/planned-unsupported/coverage_planned_metadata_aliases.cgl` | Planned | Documents metadata alias diagnostics as `resource.metadata-aliases`. |
| `tests/language-spec/fixtures/coverage/planned-unsupported/coverage_planned_var_address_space.cgl` | Planned | Documents non-workgroup `var<...>` address spaces as `resource.var-address-space`. |

## Validation

Run the structural checker after editing this matrix or the coverage fixtures:

```sh
python3 tools/check_crosstl_language_coverage.py --root . --fixture-root tests/language-spec/fixtures
```

The `cglc_crosstl_language_coverage` CTest runs the same structural checker and
passes the fixture root explicitly so CTest registration health owns the
`tests/language-spec/fixtures` family.

When a local `cglc` binary is available, the checker can also execute coverage
fixtures:

```sh
python3 tools/check_crosstl_language_coverage.py --root . --fixture-root tests/language-spec/fixtures --cglc build/cglc
```

With `--cglc`, supported fixtures must pass `cglc check` and
`cglc dump-ir --stage hir`. Planned fixtures must emit the manifest-listed
diagnostic evidence for their single compatibility id. Error evidence must make
`cglc check` fail; warning-only evidence must leave `cglc check` passing, so a
separate error cannot mask a warning-only planned gap. Moving any planned
fixture into the supported set requires updating this matrix, the compatibility
ledger, and the appropriate contract or conformance evidence in the same
review.
