# CrossGL v0 Language and Support Contract

This page is the v0 alpha freeze point for language and package-support claims.
It turns the CrossTL-derived snapshot, compatibility ledger, cross-repo fixture
contract, and package evidence into one readable contract. It is intentionally
fixture-scoped: a source form is v0-supported only when this page points to
positive parser/HIR evidence and, for package claims, target evidence in
`docs/SUPPORT_MATRIX_EVIDENCE.md`.

## Source of Truth

- Shared language inventory:
  `docs/language/crosstl-frontend-language-spec-v0.json`. This is the
  deterministic CrossTL frontend snapshot and remains the shared
  CrossTL/CrossGL language inventory until a prose grammar replaces it.
- Shared positive and negative fixtures:
  `tools/cross_repo_language_contract.json`. It pins CrossTL AST hashes,
  compiler HIR hashes, grouped feature metadata, and the small negative
  `spec.error` set.
- Shared feature map:
  `tools/cross_repo_language_spec.json`. Accepted source rows cite
  `feature:<group>` evidence tokens from this CrossTL-derived artifact so
  compiler-facing language claims stay reconciled with the shared frontend
  feature groups.
- Compiler compatibility policy:
  `docs/language/COMPATIBILITY.md`. It classifies deltas as
  `spec.unsupported-for-native-v0`, `spec.deprecated`, `spec.error`, or
  `target.unsupported`.
- Package evidence:
  `docs/SUPPORT_MATRIX_EVIDENCE.md`. It records concrete CTest names and
  whether a row proves a source package, native package, frontend/HIR behavior,
  or a planned build failure.
- HIR verifier coverage:
  `tests/conformance/hir-verifier-v0-coverage.json` and
  `tools/check_hir_verifier_v0_coverage.py` gate the required native-v0 HIR
  families against support-matrix evidence or explicit diagnostic rejection
  rows. Use `--report-output` to emit a deterministic JSON audit summary with
  required-family status and per-family evidence counts.
- Conformance seed:
  `tests/conformance/manifest.v0.json`, checked by
  `tools/check_conformance_manifest.py`. Each case names a fixture, v0
  classification buckets, the deterministic command profile that would exercise
  it, and CTest evidence or a planned native-v0 diagnostic. The manifest also
  pins required v0 feature/status coverage and classifies report-only target
  feature evidence as either planned-unsupported or target metadata.
- Support trace tokens:
  `tools/check_v0_support_evidence.py` resolves `manifest:<feature-group>`
  and `manifest:<entry-id>` tokens against
  `tests/conformance/manifest.v0.json` and `hir:<family>` tokens against
  `tests/conformance/hir-verifier-v0-coverage.json`. It also resolves
  `feature:<group>` tokens against `tools/cross_repo_language_spec.json`.
  This page intentionally carries trace tokens for every required v0 manifest
  feature/status bucket: `manifest:atomics`, `manifest:compute-basics`,
  `manifest:control-flow`, `manifest:graphics-stages`,
  `manifest:known-native-v0-unsupported`, `manifest:resources`,
  `manifest:storage-images`, and `manifest:texture-sampling`.
  Package-supported rows must cite CTest or unit-test evidence that is already
  listed in `docs/SUPPORT_MATRIX_EVIDENCE.md`; arbitrary registered tests are
  not accepted as package-support evidence from this page alone. For
  fixture-scoped graphics only, the checker also accepts registered CTests when
  they are the `evidence_tests` of the concrete package-backed manifest entry
  ids listed in that row; those tests are not accepted without the matching
  manifest ids. The checker verifies the manifest entries' accepted status,
  target, package mode, and registered CTest evidence.
  Planned unsupported rows must cite compatibility ids whose `Bucket`,
  `Owner bucket`, and `Classification` fields in
  `docs/language/COMPATIBILITY.md` satisfy the native-v0 unsupported bucket
  contract. The checker requires explicit evidence for language-level,
  compiler-frontend, and target-legalization unsupported buckets.
  These tokens are evidence pointers only; they do not broaden source syntax or
  backend support.
- Language spec trace audit:
  `docs/language/SPEC_TRACE.md`, checked by
  `tools/check_language_spec_trace.py`, maps the sealed CrossTL snapshot and
  source files to spec-index rows, compatibility buckets, support sections, and
  fixture groups. Its trace ids and source seal are pinned in the provenance
  block below so the support page cannot silently drift from the trace audit.
- Architecture rule:
  `docs/architecture/ARCHITECTURE_V2.md` requires support claims to be backed
  by spec, HIR, diagnostics, target capability, package/reflection, and native
  or validator evidence where applicable.

## Provenance Boundary

The block below is a report-only seal checked by
`tools/check_language_provenance.py`. It ties this support page to the extracted
CrossTL frontend snapshot, the cross-repo fixture contract, the spec trace
audit, and the v0 conformance seed. It is not an acceptance rule and must not
be used to broaden syntax, parser, HIR, backend, package, or target support.

<!-- crossgl-language-provenance-boundary-v1:begin -->
```json
{
  "boundary": "report-only-static-provenance",
  "conformance_manifest": {
    "path": "tests/conformance/manifest.v0.json",
    "required_feature_statuses": [
      "atomics:accepted",
      "compute-basics:accepted",
      "control-flow:accepted",
      "graphics-stages:accepted",
      "known-native-v0-unsupported:unsupported",
      "resources:accepted",
      "storage-images:accepted",
      "texture-sampling:accepted"
    ],
    "schema_version": "crossgl-conformance-manifest-v0",
    "suite": "crossgl-language-1.0-seed"
  },
  "contract": {
    "accepted_contract_groups": [
      "control_flow_and_statements",
      "crosstl_examples_and_backend_policy",
      "descriptor_indexing_and_nonuniform",
      "expressions_operators_and_intrinsics",
      "module_stages_and_entry_points",
      "resources_layouts_and_storage",
      "textures_samplers_images_and_intrinsics",
      "types_structs_arrays_and_constants"
    ],
    "language_spec_id": "crosstl-frontend-language-spec-v0",
    "path": "tools/cross_repo_language_contract.json"
  },
  "kind": "crossgl-language-provenance-boundary-v1",
  "language_spec": {
    "id": "crosstl-frontend-language-spec-v0",
    "path": "docs/language/crosstl-frontend-language-spec-v0.json",
    "schema_version": 0,
    "sha256": "86b133c7da54ac206972d452a9a48419dccb00420875e06cc1a51cbbb0109d35",
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
    ]
  },
  "spec_trace": {
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
    "path": "docs/language/SPEC_TRACE.md",
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
    }
  }
}
```
<!-- crossgl-language-provenance-boundary-v1:end -->

## Accepted Source Forms

Accepted v0 source forms are the shared forms in
`tools/cross_repo_language_contract.json` plus the native-v0 baseline in
`docs/language/COMPATIBILITY.md`. The contract accepts these source families:

| Family | Accepted forms | Evidence |
| --- | --- | --- |
| Modules and stages | `shader Name { ... }` modules with `vertex`, `fragment`, and `compute` stage blocks; compute stages may use named entry points when covered by fixtures. | `feature:module_stages_and_entry_points`; `MinimalComputeShader.cgl`, `SimpleShader.cgl`, `translator/examples/graphics/SimpleShader.cgl`, `translator/examples/gpu_computing/MatrixMultiplication.cgl`; trace: `manifest:compute-basics`, `manifest:graphics-stages`, `hir:stage-coverage` |
| Entry functions | C-style functions such as `void main() { ... }`. | `feature:module_stages_and_entry_points`; `MinimalComputeShader.cgl`; `docs/language/COMPATIBILITY.md` shared baseline; trace: `manifest:compute-basics`, `hir:stage-coverage` |
| Types, structs, arrays, constants | Primitive, vector, matrix, named, struct, constant, fixed-array, folded constant-array, and documented runtime-tail forms. | `feature:types_structs_arrays_and_constants`; `ScalarConstructorComputeShader.cgl`, `VectorSwizzleComputeShader.cgl`, `StructBufferComputeShader.cgl`, `StructConstantArrayFieldComputeShader.cgl`, `RuntimeStructArrayShader.cgl`; trace: `hir:arrays`, `hir:constants`, `hir:storage-buffers` |
| Statements and expressions | Scoped declarations, assignments, calls, `if`, `for`, `while`, early `return`, arithmetic/comparison operators, casts, constructors, swizzles, and scalar/vector intrinsics. | `feature:control_flow_and_statements`, `feature:expressions_operators_and_intrinsics`; `IfComputeShader.cgl`, `ForComputeShader.cgl`, `WhileComputeShader.cgl`, `ArithmeticComputeShader.cgl`, `IntrinsicComputeShader.cgl`, `ReadModifyWriteComputeShader.cgl`; trace: `manifest:control-flow`, `hir:control-flow` |
| Numeric float literals | Decimal exponent forms such as `1e-3`, `2.0E+4`, and `.5e+2f`, plus hexadecimal float forms such as `0x1.8p+2` and `0x1p-2f`. | `feature:expressions_operators_and_intrinsics`; `NumericFloatLiteralShader.cgl`, `coverage_numeric_literals.cgl`, `cglc_check_numeric_float_literals`, `cglc_dump_hir_numeric_float_literals`; trace: `manifest:compute-basics` |
| Resources and layout | `layout(set = N, binding = M[, format = F])`, `layout(group = N, binding = M)` as a canonical `set` alias, `layout(register = M)` as a canonical `binding` alias, cbuffers, storage buffers, storage images, textures, samplers, descriptor arrays, and `layout(local_size_*) in;` where fixture coverage exists. | `feature:resources_layouts_and_storage`, `feature:textures_samplers_images_and_intrinsics`; `ResourceShader.cgl`, `ResourceGroupAliasShader.cgl`, `ResourceRegisterAliasShader.cgl`, `StorageBufferComputeShader.cgl`, `StorageImageExplicitFormatShader.cgl`, `TextureDescriptorArrayShader.cgl`, `SamplerDescriptorArrayShader.cgl`; trace: `manifest:resources`, `manifest:storage-images`, `manifest:texture-sampling`, `hir:resources`, `hir:storage-images`, `hir:textures-samplers` |
| Workgroup compute forms | Workgroup size metadata, `var<workgroup>`/shared memory where covered, compute invocation builtins, `workgroupBarrier()`, and compatibility `barrier()`. | `feature:resources_layouts_and_storage`, `feature:expressions_operators_and_intrinsics`; `cglc_build_directx_workgroup_shared_source_package`, `cglc_build_metal_workgroup_shared_memory_native`, `cglc_build_vulkan_compute_barrier_native`, `testComputeInvocationBuiltinSharedABI` |
| Atomics | Scalar integer storage-buffer/workgroup atomics and storage-image atomics only in the exact forms documented by the Batch 34-47 evidence rows. | `feature:resources_layouts_and_storage`, `feature:expressions_operators_and_intrinsics`; `StorageImageAtomicShader.cgl`, `StorageImageAtomicDescriptorArrayShader.cgl`, `testAtomicExchangeBitwiseSharedABI`, `testStorageImageDiagnostics`; trace: `manifest:atomics` |

Accepted does not always mean package-supported for every target. Target status
is controlled by the package evidence and package mode rules below.

## v0 Package-Supported Subset

The public v0 package-supported subset is the compute-heavy, fixture-scoped
subset with named source-package or native-package evidence:

| Feature area | v0 package support |
| --- | --- |
| Scalar/vector compute | DirectX and OpenGL source packages; Metal and Vulkan native packages for arithmetic, comparison, constructors, loads/stores, swizzles, intrinsics, structured `if`, `for`, `while`, and read-modify/write fixtures. Evidence: `cglc_build_directx_arithmetic_source_package`, `cglc_build_opengl_vector_buffer_source_package`, `cglc_build_metal_arithmetic_native`, `cglc_build_vulkan_arithmetic_native`, and `testScalarVectorFixtureTargetFeatureEvidence`. |
| Fixed arrays, structs, storage buffers | Fixture-scoped function-parameter arrays, local arrays, nested arrays, struct fields, fixed array fields, storage-buffer struct arrays, and selected runtime-tail cases. Evidence: `cglc_build_directx_function_parameter_array_source_package`, `cglc_build_opengl_struct_storage_buffer_array_source_package`, `cglc_build_metal_struct_storage_buffer_array_native`, `cglc_build_vulkan_struct_storage_buffer_array_native`, `cglc_build_opengl_function_parameter_array_write_planned_failure`, and `testFunctionParameterArrayTargetFeatureEvidence`. |
| Textures and samplers | Descriptor arrays, comparison sampler roles, explicit LOD, manual shadow-compare kernels, mixed manual compare forms, and nonuniform descriptor-index forms where each target row names support. Evidence: `cglc_build_directx_texture_descriptor_array_source_package`, `cglc_build_opengl_texture_compare_descriptor_array_lod_source_package`, `cglc_build_metal_texture_compare_lod_manual_descriptor_array_native`, `cglc_build_vulkan_texture_compare_lod_manual_descriptor_array_native`, `testTextureAndSamplerDescriptorArraySplitABI`, and `testNonUniformDescriptorIndexFamilyTargetCapabilities`. |
| Workgroup and compute builtins | Workgroup size metadata, shared/workgroup memory where target rows name support, compute invocation builtins, and compute workgroup barriers. Evidence: `cglc_build_directx_workgroup_shared_source_package`, `cglc_build_metal_workgroup_shared_memory_native`, `cglc_build_vulkan_compute_barrier_native`, `testComputeInvocationBuiltinSharedABI`, and `testComputeWorkgroupBarrierSharedABI`. |
| Scalar integer atomics | `atomicAdd`, returned old-value capture for exact declaration/assignment contexts, `atomicMin`/`atomicMax`, `atomicExchange`, `atomicAnd`, `atomicOr`, and `atomicXor` for the scoped scalar integer targets. Evidence: `cglc_build_directx_atomic_add_source_package`, `cglc_build_opengl_atomic_exchange_return_source_package`, `cglc_build_metal_atomic_minmax_source_package`, `cglc_build_vulkan_atomic_exchange_native`, and `testAtomicExchangeBitwiseSharedABI`. |
| Storage images | Direct and fixed-size descriptor-array 2D/2D-array storage images, access qualifiers, explicit `r32*` formats, storage-image atomics, and nonuniform descriptor indexing where documented. Evidence: `cglc_build_directx_storage_image_atomic_descriptor_array_source_package`, `cglc_build_opengl_storage_image_explicit_format_descriptor_array_source_package`, `cglc_build_metal_storage_image_atomic_descriptor_array_native`, `cglc_build_vulkan_storage_image_atomic_descriptor_array_native`, and `testStorageImageHIRABI`. |
| Fixture-scoped graphics | Only the package-backed manifest entries named here are package claims: DirectX/OpenGL source-package rows and Metal/Vulkan native-package rows. They are fixture-scoped graphics evidence, not a broad graphics ABI claim. Evidence: `manifest:graphics-stages.directx-basic-source-package`, `cglc_build_directx_graphics_source_package`; `manifest:graphics-stages.directx-storage-buffer-resources-source-package`, `cglc_build_directx_graphics_storage_buffer_resources_source_package`; `manifest:graphics-stages.opengl-basic-source-package`, `cglc_build_opengl_graphics_source_package`; `manifest:graphics-stages.opengl-descriptor-array-resources-source-package`, `cglc_build_opengl_graphics_descriptor_array_resources_source_package`; `manifest:graphics-stages.metal-descriptor-array-native`, `cglc_build_metal_graphics_descriptor_array_native`; `manifest:graphics-stages.vulkan-helper-function-native`, `cglc_build_vulkan_graphics_helper_function_native`; `manifest:graphics-stages.vulkan-loop-control-native`, `cglc_build_vulkan_graphics_loop_control_native`; `manifest:graphics-stages.vulkan-loop-native`, `cglc_build_vulkan_graphics_loop_native`; `manifest:graphics-stages.vulkan-math-intrinsic-native`, `cglc_build_vulkan_graphics_math_intrinsic_native`; `manifest:graphics-stages.vulkan-nonuniform-descriptor-array-native`, `cglc_build_vulkan_graphics_nonuniform_descriptor_array_native`; `manifest:graphics-stages.vulkan-shadow-array-lod-native`, `cglc_build_vulkan_graphics_shadow_array_lod_native`; `manifest:graphics-stages.vulkan-shadow-array-native`, `cglc_build_vulkan_graphics_shadow_array_native`; `manifest:graphics-stages.vulkan-shadow-compare-lod-native`, `cglc_build_vulkan_graphics_shadow_compare_lod_native`; `manifest:graphics-stages.vulkan-shadow-compare-native`, `cglc_build_vulkan_graphics_shadow_compare_native`; `manifest:graphics-stages.vulkan-shadow-descriptor-array-native`, `cglc_build_vulkan_graphics_shadow_descriptor_array_native`; `manifest:graphics-stages.vulkan-texture-sampler-descriptor-array-native`, `cglc_build_vulkan_graphics_texture_sampler_descriptor_array_native`; `manifest:graphics-stages.vulkan-texture-sampler-native`, `cglc_build_vulkan_graphics_texture_sampler_native`; `manifest:graphics-stages.vulkan-uniform-buffer-native`, `cglc_build_vulkan_graphics_uniform_buffer_native`; `manifest:graphics-stages.vulkan-vertex-shadow-compare-native`, `cglc_build_vulkan_graphics_vertex_shadow_compare_native`; `manifest:graphics-stages.vulkan-vertex-texture-sampler-native`, `cglc_build_vulkan_graphics_vertex_texture_sampler_native`. |

## Compatibility-Only HIR and Raw Forms

These forms may parse, appear in compatibility fixtures, or be represented in
compiler-local HIR, but they are not broad v0 package support:

- Compiler-local HIR `while` evidence originally proved frontend/HIR behavior
  before package rows were added. Package support is limited to the later Batch
  23 target rows.
- Raw-token or malformed-HIR fallback shapes are source-preservation artifacts.
  Batch 66-67 records fail-closed expression and statement shape validation;
  these forms must not become backend-ready HIR.
- `input` and `output` used as declaration names are native compatibility
  spellings and are deprecated for new shared source.
- CrossTL examples in the `crosstl_examples_and_backend_policy` group remain
  compatibility fixtures unless package evidence also names the target/form.

## Planned or Unsupported Forms

The CrossTL snapshot is larger than the v0 package-supported compiler subset.
The following forms remain unsupported, deprecated, target-limited, or invalid
for v0:

Rows in this section cite compatibility row ids, fixtures, diagnostic/failure
CTests, or planned-failure package evidence. Successful source-package, native,
validator/DXIL, or fake-tool-success package CTests belong in the
package-supported subset or support matrix instead, because citing them here
would make the unsupported claim ambiguous.

Planned unsupported compatibility ids must resolve to report-only Compatibility
`Bucket` values that distinguish language, frontend, and target-legalization
gaps: `compat.language-unsupported-native-v0`,
`compat.frontend-unsupported-native-v0`, or
`compat.target-legalization-unsupported`. The same ledger rows must also name
the report-only owner bucket that routes planned work to one of
`owner.language-future-feature`,
`owner.compiler-frontend-subset-limit`, or
`owner.target-legalization-limit`.
The conformance seed traces this bucket with
`manifest:known-native-v0-unsupported`.

The bucket split is machine-checked:

- Language-level unsupported forms cite
  `compat.language-unsupported-native-v0`,
  `owner.language-future-feature`, and
  `spec.unsupported-for-native-v0`. Future changes start in the shared
  language/spec contract before any native compiler behavior is treated as
  accepted.
- Compiler-frontend unsupported forms cite
  `compat.frontend-unsupported-native-v0`,
  `owner.compiler-frontend-subset-limit`, and
  `spec.unsupported-for-native-v0`. Future changes belong to native
  parser/HIR acceptance evidence before package support can be claimed.
- Target-legalization unsupported forms cite
  `compat.target-legalization-unsupported`,
  `owner.target-legalization-limit`, and `target.unsupported`. Future changes
  belong to target legalization/package evidence; the frontend acceptance claim
  is not broadened by a target planned-failure row.

Language change-policy slices are evidence gates for this section:

- `syntax-tightening` must land here as a
  `v0-support-planned-or-unsupported-row` tied to a compatibility row and
  diagnostic or negative-contract evidence before any accepted-source text is
  narrowed.
- `deprecation` requires `no-new-shared-positive-fixture` for the deprecated
  spelling; support rows should point users to the canonical spelling instead.
- `source-location-requirements` require
  `native-source-map-evidence-before-support-claim`; CrossTL AST
  `source_location` inventory alone is not a native-v0 diagnostic range or
  source-map support claim.

| Form | v0 expectation | Evidence |
| --- | --- | --- |
| Extended graphics, tessellation, mesh/task/object, and ray stages | CrossTL snapshot inventory only unless a package evidence row names the exact stage and target. Native-v0 source should not rely on these stage blocks. | `docs/language/COMPATIBILITY.md` rows `stage.extended-graphics`, `stage.tessellation`, `stage.ray`; diagnostic fixture evidence `cglc_check_unsupported_native_v0_extended_stage_failure`, `cglc_check_unsupported_native_v0_tessellation_stage_failure`, `cglc_check_unsupported_native_v0_ray_stage_failure`, `cglc_check_unsupported_native_v0_ray_intersection_stage_failure`, `cglc_check_unsupported_native_v0_ray_closest_hit_stage_failure`, `cglc_check_unsupported_native_v0_ray_miss_stage_failure`, `cglc_check_unsupported_native_v0_ray_any_hit_stage_failure`, `cglc_check_unsupported_native_v0_ray_callable_stage_failure` |
| `kernel { ... }` stage spelling | Deprecated alias; use `compute`. | `stage.kernel-alias` |
| Rust-like functions, generics, traits, impls | Unsupported for native-v0; use C-style functions and concrete types. | `decl.fn-style`, `decl.generics-traits`; diagnostic evidence `cglc_check_unsupported_native_v0_fn_style_failure`, `cglc_check_unsupported_native_v0_generic_failure`, `cglc_check_unsupported_native_v0_trait_failure`, `cglc_check_unsupported_native_v0_impl_failure` |
| Colon-style variable declarations | Function-body `var name: Type` local declarations are accepted and canonicalized to HIR local declarations; stage-scope unqualified colon-style `var` remains unsupported. | `decl.colon-var`; accepted evidence `ColonVarComputeShader.cgl`, `cglc_check_colon_var_compute_hir_canonical_declaration`; diagnostic evidence `BadUnsupportedColonVarShader.cgl`, `cglc_check_unsupported_native_v0_colon_var_failure` |
| Pattern/control extensions | `match`, pattern forms, `for name in expr`, `loop`, `do while`, `switch/case/default`, and `let mut` are CrossTL-only until native HIR lowering and support are added. | `stmt.pattern-control`; diagnostic evidence `cglc_check_unsupported_native_v0_match_failure`, `cglc_check_unsupported_native_v0_switch_failure`, `cglc_check_unsupported_native_v0_for_in_failure`, `cglc_check_unsupported_native_v0_loop_failure`, `cglc_check_unsupported_native_v0_do_while_failure`, `cglc_check_unsupported_native_v0_let_mut_failure`, `cglc_check_unsupported_native_v0_malformed_if_header_failure`, `cglc_check_unsupported_native_v0_malformed_while_header_failure`, `cglc_check_unsupported_native_v0_malformed_for_header_failure` |
| Imports and preprocessor nodes | Not modeled by native package semantics. | `decl.import-preprocessor`; diagnostic evidence `cglc_check_unsupported_native_v0_import_failure`, `cglc_check_unsupported_native_v0_preprocessor_failure` |
| Preprocessor/importer line tolerance | Backslash-newline physical line splicing is translator/importer preprocessing tolerance, not shared native-v0 `.cgl` syntax. | `decl.line-splicing-preprocessor`; diagnostic evidence `BadUnsupportedLineSplicingPreprocessorShader.cgl`, `cglc_check_unsupported_native_v0_line_splicing_preprocessor_failure` |
| Metadata aliases and broad address spaces | `layout(group = ..., binding = ...)` is accepted as a canonical resource-set alias and scalar `layout(register = ...)` is accepted as a canonical resource-binding alias; prefer explicit `layout(set = ..., binding = ...)` in portable source. `var<workgroup>` is the shared compiler fixture form. Other aliases/address spaces are unsupported unless evidence names them. | `resource.metadata-aliases`, `resource.var-address-space`, `ResourceGroupAliasShader.cgl`, `ResourceRegisterAliasShader.cgl`, `BadUnsupportedResourceMetadataAliasShader.cgl`, `BadUnsupportedVarAddressSpaceShader.cgl`, `cglc_check_resource_group_layout_alias_hir_canonical_set`, `cglc_check_resource_register_layout_alias_hir_canonical_binding`, `cglc_check_unsupported_native_v0_resource_metadata_alias_failure`, `cglc_check_unsupported_native_v0_var_address_space_failure` |
| Invalid modules and semantic errors | Must reject with diagnostics. | `BadNoStagesShader.cgl` -> `sema.no-stages`, `BadEmptyStageShader.cgl` -> `sema.empty-stage`, `BadBreakOutsideLoopShader.cgl` -> `sema.break-placement`, `BadDuplicateCBufferFieldShader.cgl` -> `sema.duplicate-cbuffer-field` |
| Invalid array/resource/storage-image shapes | Must reject with targeted check-failure diagnostics. | `BadZeroArraySizeShader.cgl`, `BadNegativeArraySizeShader.cgl`, `DuplicateResourceShader.cgl`, `BadStorageImageFormatLayoutShader.cgl`, `BadStorageImageAtomicShader.cgl` |
| Backend-limited legal source | Frontend may accept the source, but package build must fail with structured target diagnostics when the target lacks support. | `target.texture-shadow-lod`, `target.resource-arrays`, `target.helper-array-params`; fixtures `RuntimeResourceArrayUnsupportedShader.cgl`, `MetalStorageBufferArrayUnsupportedShader.cgl`, `VulkanFunctionParameterArrayUnsupportedShader.cgl`; planned-failure compatibility-row reference `target.texture-shadow-lod`; planned-failure evidence `cglc_build_directx_runtime_texture_resource_array_conflict_planned_failure`, `cglc_build_vulkan_function_parameter_array_planned_failure` |

Unsupported accepted forms should fail through `cglc check` or `cglc build`
with diagnostics JSON when the relevant command reaches that path. Planned
package failures in `docs/SUPPORT_MATRIX_EVIDENCE.md` are rejection coverage,
not partial support.

## Target-Limited Support and Package Rules

Package mode is part of the v0 contract:

- Metal and Vulkan package support means native package evidence when optional
  native tools are available. Missing tools may register unavailable rows, but
  tool-present validation failures block the affected support claim.
- DirectX and OpenGL support means source-package evidence. Optional `dxc` and
  `glslangValidator` artifacts strengthen evidence when present, but source
  packages remain the baseline package mode.
- `explain-targets`, `doctor --json`, target capability metadata, reflection,
  and debug metadata must agree with the package result for supported rows.
- A feature is not supported just because one backend can print it. The v0
  evidence must name the source form, HIR/frontend behavior, target capability,
  package/reflection status, and native or validator status where applicable.
- Graphics support is limited to the named Batch 66-67 and Batch 75 fixtures.
  Do not generalize those rows into broad vertex/fragment ABI support.

## Updating This Page

When CrossTL, the native frontend, HIR, or target support changes:

1. Regenerate or check `docs/language/crosstl-frontend-language-spec-v0.json`
   with `tools/extract_crosstl_language_spec.py` as described in
   `docs/language/README.md`.
2. Update `docs/language/COMPATIBILITY.md` first when a source form moves
   between accepted, deprecated, unsupported, invalid, or target-limited
   buckets.
3. Update `tools/cross_repo_language_contract.json` with
   `tools/check_cross_repo_language_contract.py --update-manifest` only after
   the fixture is intentionally accepted by both CrossTL and the compiler.
4. Add or update positive package evidence in `docs/SUPPORT_MATRIX_EVIDENCE.md`
   when a target becomes supported. Add planned-failure evidence when a target
   must reject an otherwise accepted source form.
5. Update `tests/conformance/manifest.v0.json` when a fixture becomes part of
   the v0 conformance seed. Do not add cases without a known command profile
   and CTest evidence or a planned unsupported diagnostic.
6. Update this page last, linking the source form to the compatibility row,
   cross-repo contract group, check-failure fixture, and package evidence row.
7. Run `python3 tools/check_conformance_manifest.py --root .`,
   `python3 tools/check_hir_verifier_v0_coverage.py --root .`, and
   `python3 tools/check_v0_support_evidence.py --root .` to verify that
   the conformance seed, HIR coverage manifest, and support prose all cite
   concrete evidence, supported-family trace tokens, and non-ambiguous planned
   unsupported buckets.
8. Run `pre-commit run --all-files`; release-grade updates should also run the
   manual CMake/CTest hooks listed in `docs/V0_READINESS.md`.
