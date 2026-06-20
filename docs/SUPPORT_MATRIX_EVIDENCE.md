# CrossGL Support-Matrix Evidence

This page records public support-matrix claims that are machine-checkable through
the existing fixture suite. It is intentionally evidence-only: package creation,
verification, backend lowering, upload, and publish behavior are not defined
here.

## How to Read This Page

- A `source-package-build` evidence test means `cglc build` finalizes a `.cglb`
  for a source-package target such as DirectX or OpenGL. It does not prove a
  native package path for that target; optional native artifacts remain a
  separate source-package status detail.
- A `metal-build` or `vulkan-build` evidence test means the row is covered by a
  native package path when the optional platform tools needed by that target are
  available. If those tools are missing, CTest registers the corresponding
  optional-native unavailable row instead of proving native emission locally.
- A `planned-build-failure` evidence test is required rejection coverage, not
  partial support. It asserts that package build fails with diagnostics JSON and
  the named target diagnostic, so package users should treat that path as
  blocked until a successful package evidence row replaces it.
- Runtime descriptor-array evidence is package-mode specific. DirectX rows below
  cover source packages with one unbounded descriptor array when HLSL binding
  metadata is unambiguous. Metal and Vulkan rows below cover native package
  evidence for fixed descriptor arrays or runtime-tail storage-buffer ABI cases;
  they are not evidence for unsized descriptor-resource native packages.
- `tests/conformance/manifest.v0.json` may cite
  `target_feature_evidence_tests` for existing target-capability or
  `explain-targets` CTests that are useful when auditing v0 seed entries. These
  report-only references do not expand the support matrix or promote
  source-package targets to native binary support.

Run focused checks from a configured build directory with:

```sh
jobs="$(getconf _NPROCESSORS_ONLN 2>/dev/null || sysctl -n hw.ncpu 2>/dev/null || echo 2)"
ctest --test-dir build \
  -R 'crossgl_unit_tests|package|schema|explain_targets|doctor|target_decision|install|cpack' \
  --output-on-failure \
  --parallel "${jobs}"
```

Some native rows depend on optional platform tools and are registered only when
those tools are available.
The `cglc_support_matrix_evidence` CTest checks that backticked evidence names
below still exist in the configured CTest inventory.
When an optional-native evidence CTest is registered, it must carry
`optional-native`, the matching `<target>-native` label, and
`native-tool-available`; otherwise the row is not accepted as tool-backed
support evidence.
Without a configured build directory, `tools/check_support_matrix_evidence.py`
still resolves those names against current CMake source declarations and the
explicit unit-test alias list, so stale support evidence fails before CTest
inventory checks run.
`tools/check_v0_support_evidence.py` treats this page as the package-evidence
allow-list for `docs/language/V0_SUPPORT.md`: package-supported rows there must
reuse CTest or unit-test names listed here rather than citing unrelated
registered tests directly.

## Optimization Policy Evidence

- Shared HIR optimization levels are pass-policy evidence, not performance
  parity or native-device execution evidence. `O0` is validation-only, `O1` is
  the default safe cleanup/folding policy, and `O2` runs the `O1` cleanup policy
  plus `hir.optimize.o2.inline-scalar-temporaries` and
  `hir.optimize.o2.inline-literal-vector-temporaries` before storage-buffer
  shape validation.
  Evidence: `cglc_optimizer_opt_level_default_trace_policy` keeps the default
  `O1` trace free of O2-only pass names;
  `cglc_optimizer_opt_level_o0_trace_is_validation_only` keeps `O0` free of
  optimization passes; `cglc_optimizer_opt_level_o2_trace_has_distinct_pass`
  verifies the `O2` pass trace includes both O2 temporary-inlining pass names;
  and `cglc_optimizer_hir_o2_storage_image_nonuniform_literal_vector_temp`
  checks literal-vector temporary inlining in dumped HIR.

## Batch 19 Rows

- DirectX source packages accept one unbounded descriptor array when HLSL
  binding metadata remains unambiguous.
  Evidence: `tests/cmake/CrossGLSourcePackageBuildTests.cmake` registers
  `cglc_build_directx_unsized_storage_buffer_array_source_package` for
  `RWStructuredBuffer<float> values[]` and
  `cglc_build_directx_runtime_texture_resource_array_source_package` for
  `Texture2D<float4> colorMaps[]`; `cglc_build_directx_runtime_texture_resource_array_conflict_planned_failure`
  keeps multiple or ambiguous runtime arrays rejected.

- OpenGL source packages support read-only fixed struct-element helper arrays.
  Evidence: `cglc_build_opengl_function_parameter_struct_array_source_package`
  validates `tests/opengl/fixtures/OpenGLFunctionParameterStructArrayUnsupportedShader.cgl`
  as a source package and checks for
  `float firstWeight(Payload payloads[COUNT])`; resource-array helper arguments
  remain covered by
  `cglc_build_opengl_function_parameter_resource_array_planned_failure`.

- Metal native packages accept folded-zero singleton indexes for direct final
  runtime-tail storage buffers.
  Evidence: `tests/metal/fixtures/MetalRuntimeTailFoldedZeroBlockIndexShader.cgl`
  uses `const int ZERO = 0` for `payloads[ZERO].values[...]`;
  `cglc_build_metal_runtime_tail_folded_zero_block_index_native` checks the
  native package and `cglc_dump_backend_metal_runtime_tail_folded_zero_block_index`
  checks backend source lowering.

- Vulkan native packages support fixed uniform-buffer descriptor arrays and
  provably local-zero runtime-tail singleton indexes.
  Evidence: `cglc_build_vulkan_resource_array_access_native` checks `lights` as
  `VK_DESCRIPTOR_TYPE_UNIFORM_BUFFER` with `arrayElementCount=2`;
  `cglc_build_vulkan_runtime_array_dynamic_outer_index_native` checks
  `tests/fixtures/RuntimeArrayDynamicOuterIndexShader.cgl`, where `int i = 0;
  payloads[i].count` lowers through the singleton runtime-tail path.

- Compiler-local HIR accepts structured `while` control flow without promising
  package backend support.
  Evidence: `tests/frontend/fixtures/WhileControlFlowHIRShader.cgl` is covered
  by `cglc_check_while_control_flow_hir`,
  `cglc_check_while_control_flow_hir_condition`,
  `cglc_check_while_control_flow_hir_scoped_block`,
  `cglc_check_while_control_flow_hir_outer_scope_restored`, and
  `cglc_check_while_control_flow_hir_body_update`.

## Batch 23 Rows

- DirectX and OpenGL source packages have `while` compute package evidence for
  the supported compute storage-buffer subset.
  Evidence: `cglc_build_directx_while_source_package` and
  `cglc_build_opengl_while_source_package`; OpenGL additionally has
  validator-gated evidence in `cglc_build_opengl_while_glsl_validated`.

- Metal native packages have `while` compute native-package evidence for the
  supported compute storage-buffer subset.
  Evidence: `cglc_build_metal_while_compute_native`.

- Vulkan native packages have `while` compute native-package evidence for the
  supported compute storage-buffer subset.
  Evidence: `cglc_build_vulkan_while_native`.

## Batch 24 Rows

- DirectX source packages have intrinsic and vector-swizzle compute package
  evidence for the supported storage-buffer subset.
  Evidence: `cglc_build_directx_intrinsics_source_package` and
  `cglc_build_directx_vector_swizzle_source_package`.

- OpenGL source packages have intrinsic and vector-swizzle compute package
  evidence for the supported storage-buffer subset, with validator-gated GLSL
  coverage when the optional validator is available.
  Evidence: `cglc_build_opengl_intrinsics_source_package`,
  `cglc_build_opengl_vector_swizzle_source_package`,
  `cglc_build_opengl_intrinsics_glsl_validated`, and
  `cglc_build_opengl_vector_swizzle_glsl_validated`.

- Metal native packages have intrinsic and vector-swizzle compute native-package
  evidence for the supported storage-buffer subset.
  Evidence: `cglc_build_metal_intrinsics_native` and
  `cglc_build_metal_vector_swizzle_native`.

- Vulkan native packages have intrinsic and vector-swizzle compute
  native-package evidence for the supported storage-buffer subset.
  Evidence: `cglc_build_vulkan_intrinsics_native` and
  `cglc_build_vulkan_vector_swizzle_native`.

## Batch 25 Rows

- DirectX source packages have structured branch and read-modify compute package
  evidence for the supported storage-buffer subset.
  Evidence: `cglc_build_directx_if_source_package`,
  `cglc_build_directx_nested_if_source_package`,
  `cglc_build_directx_if_return_source_package`, and
  `cglc_build_directx_read_modify_write_source_package`.

- OpenGL source packages have structured branch and read-modify compute package
  evidence for the supported storage-buffer subset, with validator-gated GLSL
  coverage when the optional validator is available.
  Evidence: `cglc_build_opengl_if_source_package`,
  `cglc_build_opengl_nested_if_source_package`,
  `cglc_build_opengl_if_return_source_package`,
  `cglc_build_opengl_read_modify_write_source_package`,
  `cglc_build_opengl_if_glsl_validated`,
  `cglc_build_opengl_nested_if_glsl_validated`,
  `cglc_build_opengl_if_return_glsl_validated`, and
  `cglc_build_opengl_read_modify_write_glsl_validated`.

- Metal native packages have structured branch and read-modify compute
  native-package evidence for the supported storage-buffer subset.
  Evidence: `cglc_build_metal_if_native`,
  `cglc_build_metal_nested_if_native`,
  `cglc_build_metal_if_return_native`, and
  `cglc_build_metal_read_modify_write_native`.

- Vulkan native packages have structured branch and read-modify compute
  native-package evidence for the supported storage-buffer subset.
  Evidence: `cglc_build_vulkan_if_native`,
  `cglc_build_vulkan_nested_if_native`,
  `cglc_build_vulkan_if_return_native`, and
  `cglc_build_vulkan_read_modify_write_native`.

- Shared target-feature metadata for these structured branch and read-modify
  fixtures is covered without introducing a new public feature name.
  Evidence: `testBranchReadModifyTargetFeatureEvidence` pins
  `structured-selection`, `storage-buffer-read`, and `storage-buffer-write`
  metadata across DirectX, OpenGL, Metal, and Vulkan reflection output.

- Frontend HIR branch evidence pins typed `if`/`else` bodies and branch-local
  `return` statements before backend/package lowering.
  Evidence: `cglc_check_if_compute_hir_branch_shape` and
  `cglc_check_if_return_compute_hir_branch_return_shape`.

## Batch 26 Rows

- DirectX source packages have scalar/vector/arithmetic/load-local compute
  package evidence for the supported compute subset.
  Evidence: `cglc_build_directx_arithmetic_source_package`,
  `cglc_build_directx_comparison_source_package`,
  `cglc_build_directx_load_local_source_package`,
  `cglc_build_directx_scalar_constructor_source_package`,
  `cglc_build_directx_vector_local_source_package`,
  `cglc_build_directx_vector_buffer_source_package`, and
  `cglc_build_directx_vector3_buffer_source_package`. These rows assert stable
  HLSL source-package contents, reflection target/resource metadata, and
  reflection feature records for the current dead-code-cleaned fixture output.

- OpenGL source packages have scalar/vector/arithmetic/load-local compute
  package evidence for the supported compute subset, with validator-gated GLSL
  coverage when the optional validator is available.
  Evidence: `cglc_build_opengl_arithmetic_source_package`,
  `cglc_build_opengl_comparison_source_package`,
  `cglc_build_opengl_load_local_source_package`,
  `cglc_build_opengl_scalar_constructor_source_package`,
  `cglc_build_opengl_vector_local_source_package`,
  `cglc_build_opengl_vector_buffer_source_package`,
  `cglc_build_opengl_vector3_buffer_source_package`,
  `cglc_build_opengl_arithmetic_glsl_validated`,
  `cglc_build_opengl_comparison_glsl_validated`,
  `cglc_build_opengl_load_local_glsl_validated`,
  `cglc_build_opengl_scalar_constructor_glsl_validated`,
  `cglc_build_opengl_vector_local_glsl_validated`,
  `cglc_build_opengl_vector_buffer_glsl_validated`, and
  `cglc_build_opengl_vector3_buffer_glsl_validated`.

- Metal native packages have scalar/vector/arithmetic/load-local native-package
  evidence for the supported storage-buffer subset.
  Evidence: new rows `cglc_build_metal_arithmetic_native`,
  `cglc_build_metal_comparison_native`,
  `cglc_build_metal_load_local_native`, and
  `cglc_build_metal_vector_local_native`; strengthened rows
  `cglc_build_metal_scalar_constructor_native`,
  `cglc_build_metal_vector_buffer_native`, and
  `cglc_build_metal_vector3_buffer_native`. These rows assert native metallib
  package/reflection metadata, storage-buffer layout metadata, target feature
  metadata, and empty diagnostics; arithmetic and comparison evidence is scoped
  to the current dead-code-cleaned native output.

- Vulkan native packages have scalar/vector/arithmetic/load-local native-package
  evidence for the supported storage-buffer subset.
  Evidence: new row `cglc_build_vulkan_arithmetic_native`; strengthened rows
  `cglc_build_vulkan_load_local_native`,
  `cglc_build_vulkan_comparison_native`,
  `cglc_build_vulkan_scalar_constructor_native`,
  `cglc_build_vulkan_vector_local_native`,
  `cglc_build_vulkan_vector_buffer_native`, and
  `cglc_build_vulkan_vector3_buffer_native`. These rows assert stable SPIR-V
  operation/layout snippets, resource binding decoration, native package and
  reflection metadata, storage-buffer layout metadata, and target feature
  records for current observable fixture output.

- Frontend HIR and source-map evidence pins scalar/vector fixture shape and
  provenance before backend/package lowering.
  Evidence: `cglc_check_arithmetic_compute_hir_dead_code_cleanup`,
  `cglc_check_comparison_compute_hir_dead_code_cleanup`,
  `cglc_check_load_local_compute_hir_scalar_load_store`,
  `cglc_check_scalar_constructor_compute_hir_casts`,
  `cglc_check_vector_local_compute_hir_construct_vector_arithmetic`,
  `cglc_check_vector_buffer_compute_hir_vec4_load_store`,
  `cglc_check_vector3_buffer_compute_hir_vec3_load_store`,
  `cglc_dump_hir_source_map_arithmetic_return_provenance`,
  `cglc_dump_hir_source_map_comparison_return_provenance`,
  `cglc_dump_hir_source_map_load_local_assign_provenance`,
  `cglc_dump_hir_source_map_scalar_constructor_construct_provenance`,
  `cglc_dump_hir_source_map_vector_local_binary_provenance`,
  `cglc_dump_hir_source_map_vector_buffer_binary_provenance`, and
  `cglc_dump_hir_source_map_vector3_buffer_binary_provenance`.

- Shared backend target-feature and reflection metadata is covered across
  DirectX, OpenGL, Metal, and Vulkan for the Batch 26 scalar/vector fixtures.
  Evidence: `testScalarVectorFixtureTargetFeatureEvidence` pins
  `storage-buffer`, `vector-storage-buffer`, `storage-buffer-read`,
  `storage-buffer-write`, `scalar-arithmetic`, `vector-arithmetic`,
  `scalar-comparison`, `scalar-constructor`, and `vector-constructor` metadata
  in target features and reflection output, while preserving DirectX/OpenGL
  source-package capability satisfaction for required fixture features.

## Batch 27 Rows

- DirectX source packages have structured `for` loop compute package evidence
  for the supported storage-buffer subset.
  Evidence: `cglc_build_directx_for_source_package`,
  `cglc_build_directx_for_stride_source_package`,
  `cglc_build_directx_nested_for_source_package`,
  `cglc_build_directx_for_dynamic_stride_source_package`,
  `cglc_build_directx_for_constant_stride_source_package`, and
  `cglc_build_directx_for_folded_update_source_package`.

- OpenGL source packages have structured `for` loop compute package evidence
  for the supported storage-buffer subset, with validator-gated GLSL coverage
  when the optional validator is available.
  Evidence: `cglc_build_opengl_for_source_package`,
  `cglc_build_opengl_for_stride_source_package`,
  `cglc_build_opengl_nested_for_source_package`,
  `cglc_build_opengl_for_dynamic_stride_source_package`,
  `cglc_build_opengl_for_constant_stride_source_package`,
  `cglc_build_opengl_for_folded_update_source_package`,
  `cglc_build_opengl_for_glsl_validated`,
  `cglc_build_opengl_for_stride_glsl_validated`,
  `cglc_build_opengl_nested_for_glsl_validated`,
  `cglc_build_opengl_for_dynamic_stride_glsl_validated`,
  `cglc_build_opengl_for_constant_stride_glsl_validated`, and
  `cglc_build_opengl_for_folded_update_glsl_validated`.

- Metal native packages have structured `for` loop native-package evidence for
  the supported storage-buffer subset.
  Evidence: `cglc_build_metal_for_native`,
  `cglc_build_metal_for_stride_native`,
  `cglc_build_metal_nested_for_native`,
  `cglc_build_metal_for_dynamic_stride_native`,
  `cglc_build_metal_for_constant_stride_native`, and
  `cglc_build_metal_for_folded_update_native`.

- Vulkan native packages have structured `for` loop native-package evidence for
  the supported storage-buffer subset.
  Evidence: `cglc_build_vulkan_for_native`,
  `cglc_build_vulkan_for_stride_native`,
  `cglc_build_vulkan_nested_for_native`,
  `cglc_build_vulkan_for_dynamic_stride_native`,
  `cglc_build_vulkan_for_constant_stride_native`, and
  `cglc_build_vulkan_for_folded_update_native`.

- Shared backend target-feature and reflection metadata is covered across
  DirectX, OpenGL, Metal, and Vulkan for the Batch 27 loop fixtures.
  Evidence: `testLoopTargetFeatureEvidence` pins `structured-loop`,
  `storage-buffer`, `storage-buffer-read`, `storage-buffer-write`,
  `index-access`, `scalar-arithmetic`, and `scalar-comparison` metadata in
  target features and reflection output for the six loop fixture shapes.

- Frontend HIR/source-map loop provenance is covered for the shared loop
  fixtures and increment/decrement update forms before backend/package
  lowering.
  Evidence: `cglc_check_for_compute_hir_loop_contract`,
  `cglc_check_for_stride_compute_hir_update_contract`,
  `cglc_check_nested_for_compute_hir_body_placement`,
  `cglc_check_for_dynamic_stride_compute_hir_update_contract`,
  `cglc_check_for_constant_stride_compute_hir_update_contract`,
  `cglc_check_for_folded_update_compute_hir_simplified_update`,
  `cglc_check_for_increment_decrement_hir_updates`,
  `cglc_check_for_prefix_increment_hir_update`,
  `cglc_check_for_postfix_decrement_hir_update`,
  `cglc_check_for_prefix_decrement_hir_update`,
  `cglc_dump_hir_source_map_for_compute_provenance`,
  `cglc_dump_hir_source_map_for_stride_update_provenance`,
  `cglc_dump_hir_source_map_nested_for_provenance`,
  `cglc_dump_hir_source_map_for_dynamic_stride_identifier_provenance`,
  `cglc_dump_hir_source_map_for_constant_stride_identifier_provenance`,
  `cglc_dump_hir_source_map_for_folded_update_literal_provenance`,
  `cglc_dump_hir_source_map_for_increment_decrement_provenance`, and
  `cglc_dump_hir_source_map_for_increment_decrement_update_provenance`.

- Optimizer loop boundary evidence covers loop-carried storage writes, nested
  index arithmetic, dynamic stride preservation, folded update simplification,
  and dead local cleanup without a source optimizer change.
  Evidence: `cglc_check_for_optimizer_boundary_hir_loop_carried_storage_write`,
  `cglc_check_for_optimizer_boundary_hir_nested_index_arithmetic`,
  `cglc_check_for_optimizer_boundary_hir_dynamic_stride_preserved`,
  `cglc_check_for_optimizer_boundary_hir_folded_update_simplified`, and
  `cglc_check_for_optimizer_boundary_hir_dead_local_cleanup`.

- Registration-health evidence is covered on the integrated Batch 27 tree.
  Evidence: `cglc_ctest_registration_health` and the coordinator registration
  pass reported 1046 registered tests with 36 planned-failure tests after the
  DirectX, OpenGL, Metal, Vulkan, frontend, optimizer, and docs rows were
  merged together.

## Batch 28 Rows

- DirectX source packages have function-parameter array, local array, nested
  array, matrix array, folded nested array, dynamic nested read, and nested
  helper write package evidence for the supported compute storage-buffer
  subset.
  Evidence: `cglc_build_directx_function_parameter_array_source_package`,
  `cglc_build_directx_local_function_parameter_array_source_package`,
  `cglc_build_directx_nested_local_function_parameter_array_source_package`,
  `cglc_build_directx_matrix_function_parameter_array_source_package`,
  `cglc_build_directx_folded_nested_function_parameter_array_source_package`,
  `cglc_build_directx_dynamic_nested_function_parameter_array_read_source_package`,
  and `cglc_build_directx_nested_function_parameter_array_write_source_package`.

- OpenGL source packages have function-parameter array, local array, folded
  local array, nested local array, and dynamic nested local array evidence, with
  validator-gated GLSL coverage when the optional validator is available.
  Evidence: `cglc_build_opengl_function_parameter_array_source_package`,
  `cglc_build_opengl_local_function_parameter_array_source_package`,
  `cglc_build_opengl_folded_local_function_parameter_array_source_package`,
  `cglc_build_opengl_nested_local_function_parameter_array_source_package`,
  `cglc_build_opengl_dynamic_nested_local_function_parameter_array_source_package`,
  `cglc_build_opengl_function_parameter_array_glsl_validated`,
  `cglc_build_opengl_local_function_parameter_array_glsl_validated`,
  `cglc_build_opengl_folded_local_function_parameter_array_glsl_validated`,
  `cglc_build_opengl_nested_local_function_parameter_array_glsl_validated`, and
  `cglc_build_opengl_dynamic_nested_local_function_parameter_array_glsl_validated`.

- OpenGL helper array parameter writes remain planned unsupported diagnostics,
  not package support. Evidence:
  `cglc_build_opengl_function_parameter_array_write_planned_failure`,
  `cglc_build_opengl_forwarded_function_parameter_array_write_planned_failure`,
  and `cglc_build_opengl_aliased_function_parameter_array_write_planned_failure`
  assert `opengl.unsupported-function-parameter-array-write`.

- Metal native packages have function-parameter array, local array argument,
  local dynamic vector array, dynamic nested scalar read, and dynamic nested
  vector read native-package evidence.
  Evidence: `cglc_build_metal_function_parameter_array_native`,
  `cglc_build_metal_local_array_argument_native`,
  `cglc_build_metal_local_array_dynamic_vector_native`,
  `cglc_build_metal_dynamic_nested_function_parameter_array_read_native`, and
  `cglc_build_metal_dynamic_nested_vector_function_parameter_array_read_native`.

- Vulkan native packages have function-parameter array, local array, writable
  local array, vector writable local array, folded writable local array, folded
  nested local array, and dynamic nested local array evidence.
  Evidence: `cglc_build_vulkan_function_parameter_array_native`,
  `cglc_build_vulkan_local_function_parameter_array_native`,
  `cglc_build_vulkan_writable_local_function_parameter_array_native`,
  `cglc_build_vulkan_vector_writable_local_function_parameter_array_native`,
  `cglc_build_vulkan_folded_writable_local_function_parameter_array_native`,
  `cglc_build_vulkan_folded_nested_local_function_parameter_array_native`, and
  `cglc_build_vulkan_dynamic_nested_local_function_parameter_array_native`.

- Shared backend target-feature and reflection metadata is covered across
  DirectX, OpenGL, Metal, and Vulkan for fixed-size function parameter arrays,
  local arrays, nested arrays, scalar/vector elements, matrix elements, storage
  buffer array fields, storage-buffer reads/writes, and index access.
  Evidence: `testFunctionParameterArrayTargetFeatureEvidence`.

- Optimizer boundary evidence covers folded array dimensions, helper parameter
  writes, local array writes, dynamic nested parameter reads, storage-buffer
  side effects, and dead local cleanup around array-heavy HIR.
  Evidence: `cglc_check_array_optimizer_boundary_hir`,
  `cglc_check_array_optimizer_boundary_hir_folded_dimensions`,
  `cglc_check_array_optimizer_boundary_hir_helper_parameter_write`,
  `cglc_check_array_optimizer_boundary_hir_local_array_writes`,
  `cglc_check_array_optimizer_boundary_hir_dynamic_nested_read`,
  `cglc_check_array_optimizer_boundary_hir_storage_side_effects`, and
  `cglc_check_array_optimizer_boundary_hir_dead_local_cleanup`.

## Batch 29 Rows

- DirectX source packages have storage-buffer struct, vector field, nested
  field, fixed array field, constant array field, vector array field, nested
  array field, storage-buffer struct array, and struct storage-buffer
  descriptor-array field evidence. Runtime struct arrays are not claimed for
  DirectX by this row.
  Evidence: `cglc_build_directx_struct_buffer_source_package`,
  `cglc_build_directx_struct_vector_buffer_source_package`,
  `cglc_build_directx_struct_nested_field_source_package`,
  `cglc_build_directx_struct_array_field_source_package`,
  `cglc_build_directx_struct_constant_array_field_source_package`,
  `cglc_build_directx_struct_vector_array_field_source_package`,
  `cglc_build_directx_struct_nested_array_field_source_package`,
  `cglc_build_directx_struct_storage_buffer_array_source_package`, and
  `cglc_build_directx_struct_array_field_descriptor_array_source_package`.

- OpenGL source packages have storage-buffer struct, vector field, nested
  field, fixed array field, constant array field, vector array field, nested
  array field, runtime struct array, storage-buffer struct array,
  struct-storage-buffer descriptor-array field, and function-parameter struct
  array evidence, with validator-gated GLSL coverage when the optional
  validator is available.
  Evidence: `cglc_build_opengl_struct_buffer_source_package`,
  `cglc_build_opengl_struct_vector_buffer_source_package`,
  `cglc_build_opengl_struct_nested_field_source_package`,
  `cglc_build_opengl_struct_array_field_source_package`,
  `cglc_build_opengl_struct_constant_array_field_source_package`,
  `cglc_build_opengl_struct_vector_array_field_source_package`,
  `cglc_build_opengl_struct_nested_array_field_source_package`,
  `cglc_build_opengl_runtime_struct_array_source_package`,
  `cglc_build_opengl_struct_storage_buffer_array_source_package`,
  `cglc_build_opengl_struct_storage_buffer_array_field_descriptor_array_source_package`,
  `cglc_build_opengl_function_parameter_struct_array_source_package`,
  `cglc_build_opengl_struct_buffer_glsl_validated`,
  `cglc_build_opengl_struct_vector_buffer_glsl_validated`,
  `cglc_build_opengl_struct_nested_field_glsl_validated`,
  `cglc_build_opengl_struct_array_field_glsl_validated`,
  `cglc_build_opengl_struct_constant_array_field_glsl_validated`,
  `cglc_build_opengl_struct_vector_array_field_glsl_validated`,
  `cglc_build_opengl_struct_nested_array_field_glsl_validated`,
  `cglc_build_opengl_runtime_struct_array_glsl_validated`,
  `cglc_build_opengl_struct_storage_buffer_array_glsl_validated`,
  `cglc_build_opengl_struct_storage_buffer_array_field_descriptor_array_glsl_validated`,
  and `cglc_build_opengl_function_parameter_struct_array_glsl_validated`.

- Metal native packages have storage-buffer struct, vector field, fixed array
  field, constant array field, vector array field, nested array field, runtime
  struct array, and storage-buffer struct array native evidence. This row does
  not claim Metal native support for struct descriptor-array packages.
  Evidence: `cglc_build_metal_struct_buffer_native`,
  `cglc_build_metal_struct_vector_buffer_native`,
  `cglc_build_metal_struct_array_field_native`,
  `cglc_build_metal_struct_constant_array_field_native`,
  `cglc_build_metal_struct_vector_array_field_native`,
  `cglc_build_metal_struct_nested_array_field_native`,
  `cglc_build_metal_runtime_struct_array_native`, and
  `cglc_build_metal_struct_storage_buffer_array_native`.

- Vulkan native packages have storage-buffer struct, vector field, nested field,
  fixed array field, constant array field, vector array field, nested array
  field, runtime struct array, storage-buffer struct array, and
  struct-storage-buffer descriptor-array field native evidence.
  Evidence: `cglc_build_vulkan_struct_buffer_native`,
  `cglc_build_vulkan_struct_vector_buffer_native`,
  `cglc_build_vulkan_struct_nested_field_native`,
  `cglc_build_vulkan_struct_array_field_native`,
  `cglc_build_vulkan_struct_constant_array_field_native`,
  `cglc_build_vulkan_struct_vector_array_field_native`,
  `cglc_build_vulkan_struct_nested_array_field_native`,
  `cglc_build_vulkan_runtime_struct_array_native`,
  `cglc_build_vulkan_struct_storage_buffer_array_native`, and
  `cglc_build_vulkan_struct_storage_buffer_array_field_native`.

- Frontend HIR/source-map evidence pins struct declarations, storage-buffer
  field access, nested fields, fixed and symbolic array fields, vector and
  nested array fields, descriptor-array member paths, and runtime struct-array
  member paths before backend/package lowering.
  Evidence: `cglc_check_struct_buffer_compute_hir_struct_field_access`,
  `cglc_check_struct_array_field_compute_hir_fixed_array_field`,
  `cglc_check_struct_constant_array_field_compute_hir_symbolic_array_field`,
  `cglc_check_struct_vector_array_field_compute_hir_vector_array_field`,
  `cglc_check_struct_nested_field_compute_hir_nested_field_access`,
  `cglc_check_struct_nested_array_field_compute_hir_nested_array_field`,
  `cglc_check_storage_buffer_struct_array_field_descriptor_array_hir_field_paths`,
  `cglc_check_runtime_struct_array_hir_runtime_struct_array_refs`,
  `cglc_dump_hir_source_map_struct_field_type_provenance`,
  `cglc_dump_hir_source_map_struct_constant_array_field_type_provenance`,
  `cglc_dump_hir_source_map_struct_descriptor_array_member_provenance`,
  `cglc_dump_hir_source_map_runtime_struct_array_field_type_provenance`, and
  `cglc_dump_hir_source_map_runtime_struct_array_member_provenance`.

- Shared ABI/reflection evidence covers struct field array dimensions,
  descriptor-array resource shape, target binding metadata, and native
  storage-buffer layout metadata for the backends that publish native layout
  data. DirectX source packages keep HLSL binding and descriptor-array shape
  reflection without native storage layout metadata.
  Evidence: `testStructStorageBufferDescriptorArraySourceAndReflection`,
  `testVulkanStructStorageBufferDescriptorArrayFieldPaths`,
  `testRuntimeStructArrayTailNativePaths`, and
  `testStructStorageBufferLayoutReflectionAndMetalNativePath`.

- Optimizer boundary evidence covers struct-field reads, nested field
  read/write access, folded array-field indexing, dynamic nested field access,
  runtime struct-array access, storage-buffer struct side effects, and dead
  local cleanup around struct-heavy HIR.
  Evidence: `cglc_check_struct_optimizer_boundary_hir`,
  `cglc_check_struct_optimizer_boundary_hir_folded_array_field_index`,
  `cglc_check_struct_optimizer_boundary_hir_dynamic_nested_field`,
  `cglc_check_struct_optimizer_boundary_hir_runtime_struct_array`, and
  `cglc_check_struct_optimizer_boundary_hir_storage_side_effects`.

## Batch 30 Rows

- DirectX source packages have texture and sampler descriptor-array,
  comparison-sampler role, `textureLod`, `textureCompareLod`, manual
  explicit-LOD shadow-compare, mixed texture/compare and mixed manual
  texture/compare descriptor, fixed resource-array access across uniform
  buffers, storage buffers, textures, and samplers, and nonuniform
  descriptor-index evidence. This is source-package evidence only, not DirectX
  native-tool evidence.
  Evidence: `cglc_build_directx_texture_descriptor_array_source_package`,
  `cglc_build_directx_sampler_descriptor_array_source_package`,
  `cglc_build_directx_texture_only_descriptor_array_sample_source_package`,
  `cglc_build_directx_sampler_only_descriptor_array_sample_source_package`,
  `cglc_build_directx_resource_array_access_source_package`,
  `cglc_build_directx_comparison_sampler_role_source_package`,
  `cglc_build_directx_texture_sampler_lod_source_package`,
  `cglc_build_directx_texture_sampler_array_lod_source_package`,
  `cglc_build_directx_texture_compare_descriptor_array_source_package`,
  `cglc_build_directx_texture_compare_descriptor_array_lod_source_package`,
  `cglc_build_directx_texture_compare_lod_manual_descriptor_array_source_package`,
  `cglc_build_directx_texture_2d_shadow_compare_lod_manual_kernel_list_source_package`,
  `cglc_build_directx_mixed_texture_compare_descriptor_array_source_package`,
  `cglc_build_directx_mixed_texture_manual_compare_descriptor_array_source_package`,
  `cglc_build_directx_texture_compare_nonuniform_descriptor_array_lod_source_package`,
  and
  `cglc_build_directx_texture_compare_lod_manual_nonuniform_descriptor_array_source_package`.

- OpenGL source packages have texture and sampler descriptor-array,
  fixed uniform-buffer descriptor-array, comparison-sampler role,
  `textureLod`, `textureCompareLod`, manual explicit-LOD shadow-compare,
  mixed texture/compare and mixed manual texture/compare descriptor, fixed
  resource-array access across uniform buffers, storage buffers, textures, and
  samplers, and nonuniform descriptor-index evidence.
  Evidence: `cglc_build_opengl_texture_descriptor_array_source_package`,
  `cglc_build_opengl_sampler_descriptor_array_source_package`,
  `cglc_build_opengl_uniform_buffer_descriptor_array_source_package`,
  `cglc_build_opengl_uniform_buffer_descriptor_array_glsl_validated`,
  `cglc_build_opengl_texture_only_descriptor_array_sample_source_package`,
  `cglc_build_opengl_sampler_only_descriptor_array_sample_source_package`,
  `cglc_build_opengl_resource_array_access_source_package`,
  `cglc_build_opengl_comparison_sampler_role_source_package`,
  `cglc_build_opengl_texture_sampler_lod_source_package`,
  `cglc_build_opengl_texture_sampler_array_lod_source_package`,
  `cglc_build_opengl_texture_compare_descriptor_array_source_package`,
  `cglc_build_opengl_texture_compare_descriptor_array_lod_source_package`,
  `cglc_build_opengl_texture_array_compare_descriptor_array_lod_source_package`,
  `cglc_build_opengl_texture_cube_compare_descriptor_array_lod_source_package`,
  `cglc_build_opengl_texture_compare_lod_manual_descriptor_array_source_package`,
  `cglc_build_opengl_texture_2d_shadow_compare_lod_manual_kernel_list_source_package`,
  `cglc_build_opengl_mixed_texture_compare_descriptor_array_source_package`,
  `cglc_build_opengl_mixed_texture_manual_compare_descriptor_array_source_package`,
  `cglc_build_opengl_texture_compare_nonuniform_descriptor_array_lod_source_package`,
  and
  `cglc_build_opengl_texture_compare_lod_manual_nonuniform_descriptor_array_source_package`.

- Metal native packages have fixed texture and sampler descriptor-array,
  comparison-sampler role, `textureCompareLod`, manual explicit-LOD
  shadow-compare, supported nonuniform descriptor-index, and mixed manual
  texture/compare descriptor evidence. This row does not claim Metal native
  success for `MixedTextureCompareDescriptorArrayShader.cgl`; that non-manual
  mixed compare descriptor path remains unsupported by current predicates due
  `metal.diagnostic.metal.argument-slot-collision`.
  Evidence: `cglc_build_metal_texture_descriptor_array_native`,
  `cglc_build_metal_sampler_descriptor_array_native`,
  `cglc_build_metal_texture_only_descriptor_array_sample_native`,
  `cglc_build_metal_sampler_only_descriptor_array_sample_native`,
  `cglc_build_metal_comparison_sampler_role_native`,
  `cglc_build_metal_texture_compare_descriptor_array_native`,
  `cglc_build_metal_texture_compare_descriptor_array_lod_native`,
  `cglc_build_metal_texture_compare_lod_manual_descriptor_array_native`,
  `cglc_build_metal_texture_2d_shadow_compare_lod_manual_kernel_list_native`,
  `cglc_build_metal_texture_2d_array_shadow_compare_lod_manual_kernel_4_native`,
  `cglc_build_metal_texture_compare_nonuniform_descriptor_array_native`,
  `cglc_build_metal_texture_compare_nonuniform_descriptor_array_lod_native`,
  `cglc_build_metal_texture_compare_lod_manual_nonuniform_descriptor_array_native`,
  `cglc_build_metal_texture_cube_family_compare_lod_manual_nonuniform_descriptor_array_native`,
  and `cglc_build_metal_mixed_texture_manual_compare_descriptor_array_native`.

- Vulkan native packages have texture and sampler descriptor-array,
  comparison-sampler role, `textureCompareLod`, manual explicit-LOD
  shadow-compare, mixed manual texture/compare descriptor, and nonuniform
  descriptor-index capability/decorate evidence.
  Evidence: `cglc_build_vulkan_texture_descriptor_array_native`,
  `cglc_build_vulkan_sampler_descriptor_array_native`,
  `cglc_build_vulkan_texture_only_descriptor_array_sample_native`,
  `cglc_build_vulkan_sampler_only_descriptor_array_sample_native`,
  `cglc_build_vulkan_comparison_sampler_role_native`,
  `cglc_build_vulkan_texture_compare_descriptor_array_native`,
  `cglc_build_vulkan_texture_compare_descriptor_array_lod_native`,
  `cglc_build_vulkan_texture_compare_lod_manual_descriptor_array_native`,
  `cglc_build_vulkan_texture_2d_shadow_compare_lod_manual_kernel_list_native`,
  `cglc_build_vulkan_texture_2d_array_shadow_compare_lod_manual_kernel_4_native`,
  `cglc_build_vulkan_texture_compare_nonuniform_descriptor_array_native`,
  `cglc_build_vulkan_texture_compare_nonuniform_descriptor_array_parity_native`,
  `cglc_build_vulkan_texture_compare_lod_manual_nonuniform_descriptor_array_native`,
  `cglc_build_vulkan_texture_compare_lod_manual_nonuniform_descriptor_array_parity_native`,
  and `cglc_build_vulkan_mixed_texture_manual_compare_descriptor_array_native`.

- Frontend HIR/source-map evidence pins descriptor-array paths, nonuniform
  source-map markers, explicit LOD operands, comparison sampler resource roles,
  manual compare-op operands, and manual kernel tap-list summaries before
  backend/package lowering.
  Evidence: `cglc_dump_hir_texture_only_nonuniform_descriptor_array_sample_path`,
  `cglc_dump_hir_sampler_only_nonuniform_descriptor_array_sample_path`,
  `cglc_dump_hir_texture_compare_nonuniform_descriptor_array_paths`,
  `cglc_dump_hir_texture_compare_lod_nonuniform_descriptor_array_paths`,
  `cglc_dump_hir_texture_compare_lod_manual_nonuniform_descriptor_array_operands`,
  `cglc_dump_debug_texture_compare_lod_manual_kernel_tap_summary_provenance`,
  `cglc_dump_debug_comparison_sampler_role_source_locations`,
  `cglc_dump_hir_source_map_texture_sample_explicit_lod_operand_provenance`,
  `cglc_dump_hir_source_map_texture_only_nonuniform_descriptor_index_marker_provenance`,
  `cglc_dump_hir_source_map_sampler_only_nonuniform_descriptor_index_marker_provenance`,
  `cglc_dump_hir_source_map_texture_compare_nonuniform_descriptor_markers_provenance`,
  `cglc_dump_hir_source_map_texture_compare_lod_explicit_lod_operand_provenance`,
  `cglc_dump_hir_source_map_texture_compare_lod_manual_nonuniform_descriptor_markers_provenance`,
  `cglc_dump_hir_source_map_texture_compare_lod_manual_explicit_lod_operand_provenance`,
  `cglc_dump_hir_source_map_texture_compare_lod_manual_compare_op_provenance`,
  `cglc_dump_hir_source_map_texture_compare_lod_manual_descriptor_array_compare_op_provenance`,
  `cglc_dump_hir_source_map_texture_compare_lod_manual_kernel_tap_list_operand_provenance`,
  and
  `cglc_dump_hir_source_map_comparison_sampler_role_resource_type_provenance`.

- Shared ABI/reflection evidence covers runtime and fixed texture/sampler
  descriptor-array metadata, comparison-sampler resource-role separation,
  manual Kernel8 summary metadata, and nonuniform descriptor-index target,
  reflection, and debug metadata across the backends named by the unit tests.
  Evidence: `testRuntimeDescriptorArrayPolicyHelper`,
  `testTextureAndSamplerDescriptorArraySplitABI`,
  `testComparisonSamplerResourceRoleBackends`,
  `testTextureCompareLodManualKernel8Backends`,
  `testNonUniformDescriptorIndexFamilyTargetCapabilities`,
  `testVulkanNonUniformDescriptorIndexSourceAndReflection`,
  `testOneSidedNonUniformDescriptorArraySamples`, and
  `testNonUniformTextureCompareDescriptorArrays`.

- Optimizer boundary evidence covers texture sample/compare operations, manual
  compare kernels, compare-op symbolic operands, explicit LOD operands,
  nonuniform descriptor-index markers, storage writes, and dead local cleanup
  without claiming a new optimizer source change.
  Evidence: `cglc_check_texture_optimizer_boundary_hir`,
  `cglc_check_texture_optimizer_boundary_hir_sample_lod`,
  `cglc_check_texture_optimizer_boundary_hir_compare_markers`,
  `cglc_check_texture_optimizer_boundary_hir_manual_kernel4`,
  `cglc_check_texture_optimizer_boundary_hir_manual_kernel_list`, and
  `cglc_check_texture_optimizer_boundary_hir_storage_and_cleanup`.

## Batch 31 Rows

- DirectX source packages have workgroup-size metadata and `groupshared`
  shared-memory read/write evidence for the supported compute source-package
  path.
  Evidence: `cglc_dump_backend_directx_workgroup_shared_scaffold`,
  `cglc_dump_backend_directx_workgroup_shared_read_write_scaffold`, and
  `cglc_build_directx_workgroup_shared_source_package`.

- OpenGL source packages have local-size metadata and shared-memory
  declaration/read/write evidence for the supported compute source-package
  path, with validator-gated GLSL coverage when the optional validator is
  available.
  Evidence: `cglc_dump_backend_opengl_workgroup_shared_local_size_scaffold`,
  `cglc_dump_backend_opengl_workgroup_shared_declaration_scaffold`,
  `cglc_build_opengl_workgroup_shared_source_package`, and
  `cglc_build_opengl_workgroup_shared_glsl_validated`.

- Metal native packages have ResourceShader metadata and `threadgroup`
  shared-memory read/write native-package evidence.
  Evidence: `cglc_build_metal_resources_native` and
  `cglc_build_metal_workgroup_shared_memory_native`.

- Vulkan native packages have Workgroup storage-class declaration and metadata
  evidence only. These rows do not claim Vulkan shared-memory read/write
  package support.
  Evidence: `cglc_build_vulkan_resource_shader_workgroup_shared_native`,
  `cglc_build_vulkan_workgroup_shared_declaration_native`, and
  `cglc_build_vulkan_workgroup_shared_declaration_spvasm_native`.

- Frontend HIR/source-map/debug evidence pins folded workgroup-size source
  values, workgroup/shared resource type provenance, shared-memory assignment
  and read/write expression provenance, and debug resource metadata before
  backend/package lowering.
  Evidence: `cglc_dump_hir_workgroup_shared_memory_folded_source_values`,
  `cglc_dump_hir_source_map_workgroup_shared_resource_type_provenance`,
  `cglc_dump_hir_source_map_workgroup_shared_assign_statement_provenance`,
  `cglc_dump_hir_source_map_workgroup_shared_read_write_expression_provenance`,
  and `cglc_dump_debug_workgroup_shared_resource_metadata`.

- Shared ABI/reflection evidence covers stage-resource HIR metadata for
  workgroup sizes and workgroup/shared resources.
  Evidence: `testStageResourceHIR`.

- Optimizer boundary evidence covers workgroup-size metadata preservation,
  workgroup/shared resource preservation, shared-memory side-effect boundaries,
  and dead local cleanup around workgroup/shared HIR.
  Evidence: `cglc_check_workgroup_shared_optimizer_boundary_hir`,
  `cglc_check_workgroup_shared_optimizer_boundary_hir_metadata`,
  `cglc_check_workgroup_shared_optimizer_boundary_hir_resource`, and
  `cglc_check_workgroup_shared_optimizer_boundary_hir_side_effects`.

## Batch 32 Rows

- DirectX source packages have compute invocation builtin source-package
  evidence for `gl_GlobalInvocationID`, `gl_LocalInvocationID`, and
  `gl_WorkGroupID`, including backend signature and alias lowering evidence.
  Evidence: `cglc_dump_backend_directx_compute_invocation_builtins_signature`,
  `cglc_dump_backend_directx_compute_invocation_builtins_aliases`, and
  `cglc_build_directx_compute_invocation_builtins_source_package`.

- OpenGL source packages have compute invocation builtin source-package
  evidence for `gl_GlobalInvocationID`, `gl_LocalInvocationID`, and
  `gl_WorkGroupID`, with validator-gated GLSL coverage when the optional
  validator is available.
  Evidence: `cglc_dump_backend_opengl_compute_global_invocation_builtin`,
  `cglc_dump_backend_opengl_compute_local_invocation_builtin`,
  `cglc_dump_backend_opengl_compute_workgroup_builtin`,
  `cglc_build_opengl_compute_invocation_builtin_source_package`, and
  `cglc_build_opengl_compute_invocation_builtin_glsl_validated`.

- Metal native packages have compute invocation builtin native-package
  evidence for the supported compute path.
  Evidence: `cglc_build_metal_compute_invocation_builtin_native`.

- Vulkan native packages have compute invocation builtin native-package and
  SPVASM native evidence for the supported compute path.
  Evidence: `cglc_build_vulkan_compute_invocation_builtin_native` and
  `cglc_build_vulkan_compute_invocation_builtin_spvasm_native`.

- Frontend HIR/source-map/debug evidence pins compute invocation builtin
  typing, integer-cast handling, identifier provenance, and target capability
  debug metadata before backend/package lowering.
  Evidence: `cglc_dump_hir_compute_invocation_builtin_types`,
  `cglc_dump_hir_source_map_compute_invocation_builtin_identifier_provenance`,
  `cglc_dump_debug_compute_invocation_builtin_target_capabilities`, and
  `cglc_dump_hir_compute_invocation_builtin_int_casts`.

- Shared ABI/reflection/debug evidence covers compute invocation builtin
  target-feature and reflection metadata across the supported backend evidence
  paths.
  Evidence: `testComputeInvocationBuiltinSharedABI`.

- Optimizer boundary evidence covers compute invocation builtin HIR
  preservation through live locals and live writes while unrelated dead locals
  are cleaned up.
  Evidence: `cglc_check_compute_builtin_optimizer_boundary_hir`,
  `cglc_check_compute_builtin_optimizer_boundary_hir_live_locals`,
  `cglc_check_compute_builtin_optimizer_boundary_hir_live_writes`, and
  `cglc_check_compute_builtin_optimizer_boundary_hir_dead_cleanup`.

## Batch 33 Rows

These rows cover compute workgroup synchronization barriers only: canonical
`workgroupBarrier()` and compatibility alias `barrier()`. They do not claim
device/global barriers, subgroup/wave barriers, atomics, or non-compute-stage
barriers.

- DirectX source packages have compute workgroup barrier source-package
  evidence for `workgroupBarrier()` and `barrier()`.
  Evidence: `cglc_dump_backend_directx_workgroup_barrier_lowering`,
  `cglc_dump_backend_directx_workgroup_barrier_alias_scaffold`, and
  `cglc_build_directx_workgroup_barrier_source_package`.

- OpenGL source packages have compute workgroup barrier source-package
  evidence for `workgroupBarrier()` and `barrier()`, with validator-gated GLSL
  coverage when the optional validator is available.
  Evidence: `cglc_dump_backend_opengl_workgroup_barrier_lowering`,
  `cglc_build_opengl_workgroup_barrier_source_package`, and
  `cglc_build_opengl_workgroup_barrier_glsl_validated`.

- Metal packages have compute workgroup barrier backend-dump and metal-build
  package evidence for `workgroupBarrier()` and `barrier()` when the optional
  Metal tools are available.
  Evidence: `cglc_dump_backend_metal_workgroup_barrier_call`,
  `cglc_dump_backend_metal_barrier_alias_call`, and
  `cglc_build_metal_workgroup_barrier_source_package`.

- Vulkan native packages have compute workgroup barrier native-package and
  SPVASM evidence for `workgroupBarrier()` and `barrier()` when the optional
  Vulkan tools are available.
  Evidence: `cglc_dump_backend_vulkan_compute_workgroup_barrier_call`,
  `cglc_dump_backend_vulkan_compute_barrier_alias_call`,
  `cglc_build_vulkan_compute_barrier_native`, and
  `cglc_build_vulkan_compute_barrier_spvasm_native`.

- Frontend HIR/source-map/debug evidence pins compute workgroup barrier call
  expression statements, call provenance, statement provenance, and debug
  metadata before backend/package lowering.
  Evidence: `cglc_dump_hir_workgroup_barrier_expression_statements`,
  `cglc_dump_hir_source_map_workgroup_barrier_call_provenance`,
  `cglc_dump_hir_source_map_workgroup_barrier_expr_statement_provenance`, and
  `cglc_dump_debug_workgroup_barrier_metadata`.

- Shared ABI/unit evidence covers compute workgroup barrier registration and
  side-effect metadata for the supported backend evidence paths.
  Evidence: `testComputeWorkgroupBarrierSharedABI`,
  `testHIRIntrinsicRegistry`, and `testHIRSideEffectSummaries`.

- Optimizer boundary evidence covers compute workgroup barrier ordering,
  side-effect boundaries, and dead local cleanup around barrier calls.
  Evidence: `cglc_optimizer_workgroup_barrier_boundary_check`,
  `cglc_optimizer_hir_workgroup_barrier_order`, and
  `cglc_optimizer_hir_workgroup_barrier_dead_cleanup`.

- Registration-health evidence is covered on integrated scratch commit
  `96b04c9d0`: registration health passed for 1192 tests with 38 planned
  failures, and the focused Batch 33 selector registered and passed 20/20
  tests.

## Batch 34 Rows

These rows cover scalar integer statement-form `atomicAdd(target, delta)` only.
Supported targets are explicit scalar `atomic<int>` / `atomic<uint>`
storage-buffer targets, explicit scalar workgroup/shared `atomic<int>` /
`atomic<uint>` targets, and compatibility scalar `int` / `uint` lvalue counter
fields used by the existing CrossGL-Translator contract. They do not claim
returned old-value atomics, nested atomic expression use, compare-exchange,
min/max/and/or/xor atomics, floating atomics, direct atomic loads/stores,
nested atomic struct fields, device/global barriers, subgroup/wave operations,
or broader memory-model guarantees.

- DirectX source packages have scalar integer `atomicAdd` source-package
  evidence for storage-buffer and `groupshared` targets lowered to
  `InterlockedAdd`.
  Evidence: `cglc_dump_backend_directx_atomic_add_storage_buffer_lowering`,
  `cglc_dump_backend_directx_atomic_add_groupshared_lowering`,
  `cglc_dump_backend_directx_atomic_add_interlocked_lowering`,
  `cglc_dump_backend_directx_atomic_add_groupshared_interlocked_lowering`, and
  `cglc_build_directx_atomic_add_source_package`.

- OpenGL source packages have scalar integer `atomicAdd` source-package
  evidence for signed and unsigned storage-buffer targets and shared targets,
  with validator-gated GLSL coverage when the optional validator is available.
  Evidence: `cglc_dump_backend_opengl_atomic_add_storage_buffer_lowering`,
  `cglc_dump_backend_opengl_atomic_add_unsigned_storage_buffer_lowering`,
  `cglc_dump_backend_opengl_atomic_add_shared_lowering`,
  `cglc_dump_backend_opengl_atomic_add_call_lowering`,
  `cglc_build_opengl_atomic_add_source_package`, and
  `cglc_build_opengl_atomic_add_glsl_validated`.

- Metal packages have scalar integer `atomicAdd` backend-dump and metal-build
  package evidence for emission as `atomic_fetch_add_explicit(...,
  memory_order_relaxed)` over `atomic_int` / `atomic_uint` when the optional
  Metal tools are available.
  Evidence: `cglc_dump_backend_metal_atomic_add_lowering` and
  `cglc_build_metal_atomic_add_source_package`.

- Vulkan native packages have scalar integer `atomicAdd` native-package and
  SPVASM evidence for `OpAtomicIAdd` when the optional Vulkan tools are
  available.
  Evidence: `cglc_dump_backend_vulkan_atomic_add_native`,
  `cglc_build_vulkan_atomic_add_native`, and
  `cglc_build_vulkan_atomic_add_spvasm_native`.

- Frontend HIR/source-map/debug evidence pins scalar integer `atomicAdd` call
  expression statements, resource type provenance, call provenance, expression
  statement provenance, and debug metadata before backend/package lowering.
  Evidence: `cglc_dump_hir_atomic_add_expression_statements`,
  `cglc_dump_hir_source_map_atomic_add_resource_type_provenance`,
  `cglc_dump_hir_source_map_atomic_add_call_provenance`,
  `cglc_dump_hir_source_map_atomic_add_expr_statement_provenance`, and
  `cglc_dump_debug_atomic_add_metadata`.

- Shared ABI/unit evidence covers HIR scalar atomic type semantics, intrinsic
  registration, side-effect summaries, and the scalar integer atomic-add shared
  ABI contract.
  Evidence: `testHIRTypeSemanticsHelpers`, `testHIRIntrinsicRegistry`,
  `testHIRSideEffectSummaries`, and `testAtomicAddSharedABI`.

- Optimizer boundary evidence covers scalar integer atomic-add ordering,
  side-effect boundaries, and dead local cleanup for explicit storage-buffer
  atomic targets, compatibility lvalue counter fields, and workgroup/shared
  atomic targets.
  Evidence: `cglc_optimizer_atomic_storage_buffer_boundary_check`,
  `cglc_optimizer_hir_atomic_storage_buffer_order`,
  `cglc_optimizer_hir_atomic_storage_buffer_dead_cleanup`,
  `cglc_optimizer_atomic_compat_counter_boundary_check`,
  `cglc_optimizer_hir_atomic_compat_counter_order`,
  `cglc_optimizer_hir_atomic_compat_counter_dead_cleanup`,
  `cglc_optimizer_atomic_workgroup_barrier_boundary_check`,
  `cglc_optimizer_hir_atomic_workgroup_barrier_order`, and
  `cglc_optimizer_hir_atomic_workgroup_barrier_dead_cleanup`.

## Batch 35 Rows

These rows extend Batch 34 scalar integer `atomicAdd(target, delta)` support to
returned old-value capture only when the whole returned value is captured by a
declaration initializer or by a simple assignment RHS. Statement-form
`atomicAdd(target, delta);` remains supported and side-effecting. Arbitrary
nested returned-value expression use remains out of scope, including
`atomicAdd(...) + 1`, function-call arguments, ternaries, loop conditions,
return expressions, and array indices. The same non-goals from Batch 34 still
apply: compare-exchange, min/max/and/or/xor atomics, floating atomics, direct
atomic loads/stores, nested atomic struct fields, device/global barriers,
subgroup/wave operations, and broader memory-model guarantees are not claimed
by these rows.

- DirectX source packages have returned old-value capture evidence for
  declaration initializers and simple assignment RHS. Capture lowers through
  `InterlockedAdd(target, delta, oldValue);`, while statement-form calls keep
  the Batch 34 `InterlockedAdd(target, delta);` lowering.
  Evidence: `cglc_dump_backend_directx_atomic_add_return_declaration_capture`,
  `cglc_dump_backend_directx_atomic_add_return_assignment_capture`,
  `cglc_dump_backend_directx_atomic_add_return_unsigned_capture`,
  `cglc_dump_backend_directx_atomic_add_return_groupshared_capture`,
  `cglc_dump_backend_directx_atomic_add_return_statement_unchanged`, and
  `cglc_build_directx_atomic_add_return_source_package`.

- OpenGL source packages have returned old-value capture evidence for
  declaration initializers, simple assignment RHS, compatibility scalar integer
  counters, signed and unsigned storage-buffer atomics, and shared atomics.
  Capture lowers through GLSL expression-returning `atomicAdd`, with
  validator-gated GLSL coverage when the optional validator is available.
  Evidence: `cglc_dump_backend_opengl_atomic_add_return_declaration_lowering`,
  `cglc_dump_backend_opengl_atomic_add_return_assignment_lowering`,
  `cglc_dump_backend_opengl_atomic_add_return_compat_lowering`,
  `cglc_build_opengl_atomic_add_return_source_package`, and
  `cglc_build_opengl_atomic_add_return_glsl_validated`.

- Metal packages have returned old-value capture backend-dump and metal-build
  package evidence when the optional Metal tools are available. Capture uses
  the old value returned by
  `atomic_fetch_add_explicit(..., memory_order_relaxed)` for storage-buffer
  atomics, threadgroup atomics, and compatibility scalar integer counter
  fields; statement-form calls still discard the returned value operationally.
  Evidence: `cglc_dump_backend_metal_atomic_add_return_capture_lowering` and
  `cglc_build_metal_atomic_add_return_source_package`.

- Vulkan native packages have returned old-value capture native-package and
  SPVASM evidence when the optional Vulkan tools are available. Capture
  preserves the `OpAtomicIAdd` result id for declaration initializers and
  simple assignment RHS, while statement-form calls emit `OpAtomicIAdd` and
  leave the old-value result unused.
  Evidence: `cglc_dump_backend_vulkan_atomic_add_return_capture`,
  `cglc_build_vulkan_atomic_add_return_native`, and
  `cglc_build_vulkan_atomic_add_return_spvasm_native`.

- Frontend HIR/source-map/debug evidence pins returned old-value `atomicAdd`
  capture contexts before backend/package lowering: storage-buffer
  `atomic<int>` and `atomic<uint>`, workgroup/shared `atomic<int>`,
  compatibility scalar integer counter fields, declaration initializer
  capture, assignment RHS capture, and preserved statement-form calls.
  Evidence: `cglc_dump_hir_atomic_add_return_capture_contexts`,
  `cglc_dump_hir_source_map_atomic_add_return_call_provenance`, and
  `cglc_dump_debug_atomic_add_return_metadata`.

- Shared ABI/unit evidence keeps scalar atomic-add calls opaque and
  side-effecting while assigning the returned old-value type in HIR. It covers
  declaration initializer capture, simple assignment RHS capture,
  statement-form result discard, and rejection of nested returned-value
  expression use.
  Evidence: `testAtomicAddSharedABI`, `testHIRIntrinsicRegistry`, and
  `testHIRSideEffectSummaries`.

- Optimizer boundary evidence covers returned old-value `atomicAdd` capture
  without treating the operation as pure math: declaration capture, simple
  assignment RHS capture, unused capture that must remain observable,
  statement-form ordering, compatibility integer counter capture, and dead
  cleanup around unrelated locals.
  Evidence: `cglc_optimizer_atomic_add_return_boundary_check`,
  `cglc_optimizer_hir_atomic_add_return_order`, and
  `cglc_optimizer_hir_atomic_add_return_dead_cleanup`.

- Registration-health evidence for the integrated Batch 35 evidence base is
  covered on scratch commit `6f841efe`: registration health passed for 1244
  tests, the focused `atomic_add_return` selector passed 22 tests, and the
  broader atomic selector passed 52 tests. The toolchain lane owns the final
  registration audit before coordinator drain.

## Batch 36 Rows

These rows extend the Batch 34/35 scalar integer atomic model from
`atomicAdd(target, delta)` to `atomicMin(target, value)` and
`atomicMax(target, value)`. Supported value contexts are statement-form calls
that discard the returned old value, declaration initializers whose initializer
is exactly an `atomicMin` or `atomicMax` call, and simple assignments whose RHS
is exactly an `atomicMin` or `atomicMax` call. Returned old-value capture is
scoped to matching scalar integer payload types for explicit `atomic<int>` /
`atomic<uint>` storage-buffer targets, explicit workgroup/shared atomic
targets, and the Batch 34/35 compatibility scalar integer lvalue counter path
where the backend evidence says that path is supported. Arbitrary nested
returned-value expression use remains out of scope, including
`atomicMin(...) + 1`, `atomicMax(...) + 1`, function-call arguments, ternaries,
loop conditions, return expressions, and array indices. The remaining Batch 34
non-goals still apply: compare-exchange, exchange, and/or/xor atomics,
floating atomics, direct atomic loads/stores, nested atomic struct fields,
device/global barriers, subgroup/wave operations, and broader memory-model
guarantees are not claimed by these rows.

- DirectX source packages have scalar integer `atomicMin` / `atomicMax`
  statement-form and returned old-value capture evidence for storage-buffer and
  `groupshared` targets. Statement-form calls lower to the two-argument
  `InterlockedMin(target, value);` / `InterlockedMax(target, value);` forms.
  Declaration initializer and simple assignment capture lower through the
  three-argument old-value forms,
  `InterlockedMin(target, value, oldValue);` and
  `InterlockedMax(target, value, oldValue);`.
  Evidence: `cglc_dump_backend_directx_atomic_minmax_statement_min_lowering`,
  `cglc_dump_backend_directx_atomic_minmax_statement_max_lowering`,
  `cglc_dump_backend_directx_atomic_minmax_unsigned_statement_lowering`,
  `cglc_dump_backend_directx_atomic_minmax_groupshared_statement_lowering`,
  `cglc_dump_backend_directx_atomic_minmax_return_declaration_capture`,
  `cglc_dump_backend_directx_atomic_minmax_return_assignment_capture`,
  `cglc_dump_backend_directx_atomic_minmax_return_unsigned_capture`,
  `cglc_dump_backend_directx_atomic_minmax_return_groupshared_capture`,
  `cglc_build_directx_atomic_minmax_source_package`, and
  `cglc_build_directx_atomic_minmax_return_source_package`.

- OpenGL source packages have scalar integer `atomicMin` / `atomicMax`
  statement-form and returned old-value capture evidence for signed and
  unsigned storage-buffer atomics, shared atomics, and compatibility scalar
  integer counter fields. Statement form and capture both lower through GLSL
  expression-returning `atomicMin` / `atomicMax`, with validator-gated GLSL
  coverage when the optional validator is available.
  Evidence: `cglc_dump_backend_opengl_atomic_minmax_statement_lowering`,
  `cglc_dump_backend_opengl_atomic_minmax_return_declaration_lowering`,
  `cglc_dump_backend_opengl_atomic_minmax_return_assignment_lowering`,
  `cglc_dump_backend_opengl_atomic_minmax_unsigned_lowering`,
  `cglc_dump_backend_opengl_atomic_minmax_shared_lowering`,
  `cglc_dump_backend_opengl_atomic_minmax_compat_lowering`,
  `cglc_build_opengl_atomic_minmax_return_source_package`, and
  `cglc_build_opengl_atomic_minmax_return_glsl_validated`.

- Metal packages have scalar integer `atomicMin` / `atomicMax` backend-dump
  and metal-build package evidence when the optional Metal tools are available.
  Capture uses the old value returned by
  `atomic_fetch_min_explicit(..., memory_order_relaxed)` /
  `atomic_fetch_max_explicit(..., memory_order_relaxed)` for storage-buffer
  atomics, threadgroup atomics, and compatibility scalar integer counter
  fields; statement-form calls still discard the returned old value.
  Evidence: `cglc_dump_backend_metal_atomic_minmax_lowering` and
  `cglc_build_metal_atomic_minmax_source_package`.

- Vulkan native packages have scalar integer `atomicMin` / `atomicMax`
  native-package and SPVASM evidence when the optional Vulkan tools are
  available. Signed integer min/max lower through `OpAtomicSMin` /
  `OpAtomicSMax`, unsigned integer min/max lower through `OpAtomicUMin` /
  `OpAtomicUMax`, and declaration/assignment capture stores the result id
  returned by the atomic operation while statement form leaves it unused.
  Evidence: `cglc_dump_backend_vulkan_atomic_minmax_native`,
  `cglc_build_vulkan_atomic_minmax_native`, and
  `cglc_build_vulkan_atomic_minmax_spvasm_native`.

- Frontend HIR/source-map/debug evidence pins `atomicMin` / `atomicMax`
  statement-form calls, declaration initializer capture, simple assignment RHS
  capture, signed and unsigned storage-buffer targets, workgroup/shared atomic
  targets, compatibility scalar integer counter fields, call provenance, and
  debug metadata before backend/package lowering.
  Evidence: `cglc_dump_hir_atomic_minmax_capture_contexts`,
  `cglc_dump_hir_source_map_atomic_minmax_min_call_provenance`,
  `cglc_dump_hir_source_map_atomic_minmax_max_call_provenance`, and
  `cglc_dump_debug_atomic_minmax_metadata`.

- Shared ABI/unit evidence keeps `atomicMin` / `atomicMax` exact-arity-2,
  opaque, side-effecting, and typed as returning the old scalar integer payload
  while preserving Batch 34/35 `atomicAdd` statement/capture behavior. It also
  covers rejection of non-integer targets, non-lvalue targets, mismatched value
  or capture types, bad arity, and nested returned-value expression use.
  Evidence: `testAtomicMinMaxSharedABI`, `testHIRIntrinsicRegistry`,
  `testHIRSideEffectSummaries`, and `testAtomicAddSharedABI`.

- Optimizer boundary evidence covers `atomicMin` / `atomicMax` old-value
  capture without treating the calls as pure math: declaration capture, simple
  assignment RHS capture, statement-form calls, unused returned values that
  must remain observable, compatibility integer counter capture, and ordering
  across surrounding reads/writes plus `barrier()` / `workgroupBarrier()`.
  Evidence: `cglc_optimizer_atomic_minmax_return_boundary_check`,
  `cglc_optimizer_hir_atomic_minmax_return_order`, and
  `cglc_optimizer_hir_atomic_minmax_return_dead_cleanup`.

- Registration-health evidence exists on the integrated Batch 36 evidence base
  `cc1f74fb`: the backend integration pass reported registration health for
  1267 tests with 38 planned-failure tests, the integrated frontend selector
  passed `ctest --test-dir build -R 'atomic_minmax'`, and the integrated
  optimizer selector passed
  `cglc_optimizer_atomic_minmax_return_boundary_check`,
  `cglc_optimizer_hir_atomic_minmax_return_order`, and
  `cglc_optimizer_hir_atomic_minmax_return_dead_cleanup`.

## Batch 37 Rows

These rows extend the Batch 34/35 scalar integer atomic old-value model to
`atomicExchange(target, value)`, `atomicAnd(target, value)`,
`atomicOr(target, value)`, and `atomicXor(target, value)`. Supported value
contexts are statement-form calls that discard the returned old value,
declaration initializers whose initializer is exactly one of those calls, and
simple assignments whose RHS is exactly one of those calls. Returned old-value
capture is scoped to matching scalar integer payload types for explicit
`atomic<int>` / `atomic<uint>` storage-buffer targets, explicit
workgroup/shared atomic targets, and the compatibility scalar integer lvalue
counter path where each backend row names support. These rows do not claim
`atomicSub`, compare-exchange, direct atomic load/store, user memory-order or
scope syntax, floating atomics, nested returned-value expression use, device or
global barriers, subgroup/wave operations, CrossGL-Translator edits, or broader
memory-model guarantees. Nested returned-value expressions remain out of scope,
including `atomicExchange(...) + 1`, `atomicAnd(...) + 1`, function-call
arguments, ternaries, loop conditions, return expressions, and array indices.

- DirectX source packages have scalar integer `atomicExchange`, `atomicAnd`,
  `atomicOr`, and `atomicXor` statement-form and returned old-value capture
  evidence for storage-buffer and `groupshared` targets. Statement-form
  bitwise calls lower to the two-argument `InterlockedAnd` / `InterlockedOr` /
  `InterlockedXor` forms. Declaration initializer and simple assignment
  capture lower through the three-argument old-value forms. Statement-form
  `atomicExchange` uses a backend-local scratch old-value variable because the
  HLSL `InterlockedExchange` form requires an out parameter.
  Evidence: `cglc_dump_backend_directx_atomic_exchange_statement_scratch`,
  `cglc_dump_backend_directx_atomic_exchange_unsigned_statement_scratch`,
  `cglc_dump_backend_directx_atomic_exchange_declaration_capture`,
  `cglc_dump_backend_directx_atomic_exchange_assignment_capture`,
  `cglc_dump_backend_directx_atomic_exchange_groupshared_capture`,
  `cglc_dump_backend_directx_atomic_bitwise_statement_and_lowering`,
  `cglc_dump_backend_directx_atomic_bitwise_unsigned_statement_or_lowering`,
  `cglc_dump_backend_directx_atomic_bitwise_groupshared_statement_xor_lowering`,
  `cglc_dump_backend_directx_atomic_bitwise_declaration_capture`,
  `cglc_dump_backend_directx_atomic_bitwise_assignment_capture`,
  `cglc_dump_backend_directx_atomic_bitwise_groupshared_capture`,
  `cglc_build_directx_atomic_exchange_source_package`, and
  `cglc_build_directx_atomic_bitwise_source_package`.

- OpenGL source packages have scalar integer `atomicExchange`, `atomicAnd`,
  `atomicOr`, and `atomicXor` statement-form and returned old-value capture
  evidence for signed and unsigned storage-buffer atomics, shared atomics, and
  compatibility scalar integer counter fields. Statement form and capture both
  lower through GLSL expression-returning atomic calls, with validator-gated
  GLSL coverage when the optional validator is available.
  Evidence: `cglc_dump_backend_opengl_atomic_exchange_statement_lowering`,
  `cglc_dump_backend_opengl_atomic_exchange_return_declaration_lowering`,
  `cglc_dump_backend_opengl_atomic_exchange_return_assignment_lowering`,
  `cglc_dump_backend_opengl_atomic_exchange_unsigned_lowering`,
  `cglc_dump_backend_opengl_atomic_exchange_shared_lowering`,
  `cglc_dump_backend_opengl_atomic_exchange_compat_lowering`,
  `cglc_dump_backend_opengl_atomic_bitwise_statement_lowering`,
  `cglc_dump_backend_opengl_atomic_bitwise_return_declaration_lowering`,
  `cglc_dump_backend_opengl_atomic_bitwise_return_assignment_lowering`,
  `cglc_dump_backend_opengl_atomic_bitwise_unsigned_lowering`,
  `cglc_dump_backend_opengl_atomic_bitwise_shared_lowering`,
  `cglc_dump_backend_opengl_atomic_bitwise_compat_lowering`,
  `cglc_build_opengl_atomic_exchange_return_source_package`,
  `cglc_build_opengl_atomic_bitwise_return_source_package`,
  `cglc_build_opengl_atomic_exchange_return_glsl_validated`, and
  `cglc_build_opengl_atomic_bitwise_return_glsl_validated`.

- Metal packages have scalar integer `atomicExchange`, `atomicAnd`,
  `atomicOr`, and `atomicXor` backend-dump and metal-build package evidence
  when the optional Metal tools are available. Capture uses the old values
  returned by `atomic_exchange_explicit`, `atomic_fetch_and_explicit`,
  `atomic_fetch_or_explicit`, and `atomic_fetch_xor_explicit` over
  storage-buffer atomics, threadgroup atomics, and compatibility scalar integer
  counter fields; statement-form calls still discard the returned old value.
  Evidence: `cglc_dump_backend_metal_atomic_exchange_lowering`,
  `cglc_dump_backend_metal_atomic_bitwise_lowering`,
  `cglc_build_metal_atomic_exchange_source_package`, and
  `cglc_build_metal_atomic_bitwise_source_package`.

- Vulkan native packages have scalar integer `atomicExchange`, `atomicAnd`,
  `atomicOr`, and `atomicXor` native-package and SPVASM evidence when the
  optional Vulkan tools are available. `atomicExchange` lowers through
  `OpAtomicExchange`; bitwise calls lower through `OpAtomicAnd`, `OpAtomicOr`,
  and `OpAtomicXor`; declaration/assignment capture stores the result id while
  statement form leaves the old-value result unused. The SPVASM checks also
  assert absence of unrelated atomics, compare-exchange, atomic load/store,
  barriers, and `atomicSub`.
  Evidence: `cglc_dump_backend_vulkan_atomic_exchange_native`,
  `cglc_dump_backend_vulkan_atomic_bitwise_native`,
  `cglc_build_vulkan_atomic_exchange_native`,
  `cglc_build_vulkan_atomic_exchange_spvasm_native`,
  `cglc_build_vulkan_atomic_bitwise_native`, and
  `cglc_build_vulkan_atomic_bitwise_spvasm_native`.

- Frontend HIR/source-map/debug evidence pins `atomicExchange`, `atomicAnd`,
  `atomicOr`, and `atomicXor` statement-form calls, declaration initializer
  capture, simple assignment RHS capture, signed and unsigned storage-buffer
  targets, workgroup/shared atomic targets, compatibility scalar integer
  counter fields, call provenance, expression-statement provenance, and debug
  metadata before backend/package lowering.
  Evidence: `cglc_dump_hir_atomic_exchange_capture_contexts`,
  `cglc_dump_hir_source_map_atomic_exchange_call_provenance`,
  `cglc_dump_hir_source_map_atomic_exchange_expr_statement_provenance`,
  `cglc_dump_debug_atomic_exchange_metadata`,
  `cglc_dump_hir_atomic_bitwise_capture_contexts`,
  `cglc_dump_hir_source_map_atomic_bitwise_and_call_provenance`,
  `cglc_dump_hir_source_map_atomic_bitwise_or_call_provenance`,
  `cglc_dump_hir_source_map_atomic_bitwise_xor_call_provenance`,
  `cglc_dump_hir_source_map_atomic_bitwise_expr_statement_provenance`, and
  `cglc_dump_debug_atomic_bitwise_metadata`.

- Shared ABI/unit evidence keeps `atomicExchange`, `atomicAnd`, `atomicOr`,
  and `atomicXor` exact-arity-2, opaque, side-effecting, and typed as returning
  the old scalar integer payload. It covers statement-form result discard,
  declaration initializer capture, simple assignment RHS capture, explicit
  storage-buffer atomics, workgroup/shared atomics, compatibility scalar
  integer counter fields, target feature metadata, and rejection of
  non-integer targets, non-lvalue targets, mismatched value or capture types,
  bad arity, nested returned-value expression use, and absence of `atomicSub`
  from the intrinsic registry.
  Evidence: `testAtomicExchangeBitwiseSharedABI`,
  `testHIRIntrinsicRegistry`, and `testHIRSideEffectSummaries`.

- Optimizer boundary evidence covers `atomicExchange`, `atomicAnd`,
  `atomicOr`, and `atomicXor` old-value capture without treating the calls as
  pure math: declaration capture, simple assignment RHS capture, statement-form
  calls, unused returned values that must remain observable, compatibility
  integer counter capture, workgroup/shared targets, and ordering across
  surrounding reads/writes plus `barrier()` / `workgroupBarrier()`.
  Evidence: `cglc_optimizer_atomic_exchange_boundary_check`,
  `cglc_optimizer_hir_atomic_exchange_order`,
  `cglc_optimizer_hir_atomic_exchange_dead_cleanup`,
  `cglc_optimizer_atomic_bitwise_boundary_check`,
  `cglc_optimizer_hir_atomic_bitwise_order`, and
  `cglc_optimizer_hir_atomic_bitwise_dead_cleanup`.

- Registration-health evidence exists on integrated draft `4220961c4`: the
  integrated scratch validation reported `cglc_ctest_registration_health` for
  1329 tests with 38 planned-failure tests, the focused Batch 37 selector
  passed 55/55 tests, `crossgl_unit_tests` passed, and `git diff --check`
  passed. The same integrated draft records that the only `atomicSub` matches
  are negative/absence assertions, not support claims.

## Batch 38 Rows

These rows cover the first storage-image resource class for direct compute
resources. The supported source types are `image2D`, `iimage2D`, `uimage2D`,
`image2DArray`, `iimage2DArray`, and `uimage2DArray`; they are classified as
`storage_image`, not sampled textures. Formats are fixed by source type:
`rgba32f` for float images, `rgba32i` for signed integer images, and `rgba32ui`
for unsigned integer images. `imageLoad(image, coordinates)` returns
`vec4`/`ivec4`/`uvec4`; `imageStore(image, coordinates, value)` returns `void`
and requires the matching payload vector. Coordinates are `ivec2` for 2D images
and `ivec3` for 2D-array images.

- DirectX source-package lowering maps storage images to UAV `RWTexture2D` or
  `RWTexture2DArray` resources with `float4`/`int4`/`uint4` payloads.
  `imageLoad` lowers to `.Load(...)`; `imageStore` lowers to indexed writes.
  Reflection records `storage_image` resources with UAV binding metadata and
  `hlslType` values such as `RWTexture2D<float4>` and
  `RWTexture2DArray<uint4>`.
  Evidence: `tests/directx/fixtures/DirectXStorageImage2DShader.cgl`,
  `tests/directx/fixtures/DirectXStorageImage2DArrayShader.cgl`, and
  `cglc_build_directx_storage_image_2d_source_package`,
  `cglc_build_directx_storage_image_2d_array_source_package`,
  `cglc_build_directx_storage_image_read_write_source_package`, and
  `testStorageImageReflectionDocumentModel`.

- OpenGL source-package lowering maps storage images to GLSL image uniforms with
  `layout(binding = N, rgba32*)` qualifiers and direct `imageLoad`/`imageStore`
  calls. Reflection records image address-space and binding-class metadata.
  Evidence: `tests/opengl/fixtures/OpenGLStorageImageShader.cgl`,
  `cglc_build_opengl_storage_image_source_package`, and
  `testStorageImageReflectionDocumentModel`.

- Metal lowering maps storage images to
  `texture2d<scalar, access::read_write>` or
  `texture2d_array<scalar, access::read_write>` kernel texture parameters.
  `imageLoad` lowers to `read(...)`; `imageStore` lowers to `write(...)`.
  Evidence: `tests/metal/fixtures/MetalStorageImageShader.cgl`,
  `cglc_build_metal_storage_image_native`, and
  `testStorageImageReflectionDocumentModel`.

- Vulkan metadata and native lowering model storage images as
  `VK_DESCRIPTOR_TYPE_STORAGE_IMAGE` descriptors in `UniformConstant` storage,
  with `storageImage` binding class and
  `OpTypeImage<scalar, 2D|2DArray, sampled=2, format=Rgba32*>` reflection type
  metadata. Native lowering uses `OpImageRead` and `OpImageWrite`.
  Evidence: `tests/vulkan/fixtures/VulkanStorageImageReadWriteShader.cgl`,
  `cglc_build_vulkan_storage_image_read_write_native`, and
  `testStorageImageReflectionDocumentModel`.

- Shared frontend, target-capability, diagnostics, and optimizer evidence pins
  the storage-image type family, distinct `storage_image` reflection kind,
  `resource.storage-image`, `storageImage.*-dimension`,
  `storageImage.rgba32*-format`, `operation.storage-image-read`, and
  `operation.storage-image-write` capability records, operand arity and
  coordinate/payload diagnostics, and read/write side-effect boundaries.
  Evidence: `tests/frontend/fixtures/StorageImageHIRShader.cgl`,
  `tests/optimizer/fixtures/StorageImageOptimizerBoundaryShader.cgl`,
  `tests/check-failures/BadStorageImageLoadArityShader.cgl`,
  `tests/check-failures/BadStorageImageStoreArityShader.cgl`,
  `tests/check-failures/BadStorageImageLoadCoordinateShapeShader.cgl`,
  `tests/check-failures/BadStorageImageStoreCoordinateShapeShader.cgl`,
  `tests/check-failures/BadStorageImageStorePayloadTypeShader.cgl`,
  `tests/check-failures/BadStorageImageSampledTextureOperandShader.cgl`,
  `tests/check-failures/BadStorageImageValueUseShader.cgl`,
  `testStorageImageHIRABI`, `testStorageImageDiagnostics`,
  `testHIRTypeSemanticsHelpers`, `testHIRSideEffectSummaries`, and
  `testStorageImageReflectionDocumentModel`.

These Batch 38 rows do not claim image atomics, mip/lod/sample operations,
multisample/cube/3D storage images, descriptor-array behavior covered by the
later rows below, bindless or runtime images, coherent storage-image
qualifiers, helper-function image parameters, broader memory-model guarantees,
or CrossGL-Translator changes. Fixed-size storage-image descriptor arrays are
tracked by the Batch 39 rows below; storage-image access qualifiers are tracked
by the Batch 41 rows below; explicit layout format metadata is tracked by the
Batch 42 rows below.

## Batch 39 Rows

These rows extend storage-image support to fixed-size descriptor arrays. The
supported source families are `image2D`, `iimage2D`, `uimage2D`,
`image2DArray`, `iimage2DArray`, and `uimage2DArray` arrays with positive
numeric sizes or folded top-level integer constants. Supported descriptor
indices are static indices, ordinary dynamic uniform indices, and explicit
`nonuniform(...)` indices. Runtime or unsized storage-image descriptor arrays
remain rejected with `sema.storage-image-runtime-descriptor-array`.

- DirectX source-package lowering maps fixed storage-image descriptor arrays to
  HLSL UAV arrays such as `RWTexture2D<float4> colorImages[N]`,
  `RWTexture2D<int4> labelImages[N]`, and
  `RWTexture2DArray<uint4> maskAtlases[N]`. Nonuniform descriptor indices lower
  through `NonUniformResourceIndex(...)`. Reflection preserves the source array
  size and folded element count.
  Evidence: `tests/directx/fixtures/DirectXStorageImageDescriptorArrayShader.cgl`,
  `tests/directx/fixtures/DirectXStorageImageNonUniformDescriptorArrayShader.cgl`,
  `testStorageImageHIRABI`, `testStorageImageReflectionDocumentModel`, and
  `testStorageImageDiagnostics`.

- OpenGL source-package lowering maps fixed storage-image descriptor arrays to
  GLSL image uniform arrays with `layout(binding = N, rgba32*)` qualifiers.
  Indexed `imageLoad`/`imageStore` calls support static, ordinary dynamic
  uniform, and explicit nonuniform descriptor indices. Nonuniform storage-image
  indexing enables `GL_EXT_nonuniform_qualifier` and emits
  `nonuniformEXT(...)`.
  Evidence: `tests/opengl/fixtures/OpenGLStorageImageDescriptorArrayShader.cgl`,
  `tests/opengl/fixtures/OpenGLStorageImageNonUniformDescriptorArrayShader.cgl`,
  `testStorageImageHIRABI`, `testStorageImageReflectionDocumentModel`, and
  `testStorageImageDiagnostics`.

- Metal lowering maps fixed storage-image descriptor arrays to native
  `array<texture2d<..., access::read_write>, N>` or
  `array<texture2d_array<..., access::read_write>, N>` texture arguments.
  Static, ordinary dynamic uniform, and explicit nonuniform indices are
  supported for both 2D and 2D-array storage-image families. The Metal source
  path strips the nonuniform marker into ordinary array indexing.
  Evidence:
  `tests/metal/fixtures/MetalStorageImage2DDescriptorArrayShader.cgl`,
  `tests/metal/fixtures/MetalStorageImage2DArrayDescriptorArrayShader.cgl`, and
  `tests/metal/fixtures/MetalStorageImage2DNonUniformDescriptorArrayShader.cgl`,
  `tests/metal/fixtures/MetalStorageImage2DArrayNonUniformDescriptorArrayShader.cgl`,
  `testStorageImageHIRABI`, `testStorageImageReflectionDocumentModel`, and
  `testStorageImageDiagnostics`.

- Vulkan metadata and native lowering model fixed storage-image descriptor
  arrays as `VK_DESCRIPTOR_TYPE_STORAGE_IMAGE` descriptor arrays in
  `UniformConstant` storage with array-wrapped image types and access-chain
  descriptor selection. Static, folded-constant, ordinary dynamic uniform, and
  explicit `nonuniform(...)` indices are supported. Nonuniform storage-image
  arrays emit `SPV_EXT_descriptor_indexing`, `ShaderNonUniformEXT`,
  `StorageImageArrayNonUniformIndexingEXT`, `NonUniformEXT` decorations,
  `OpImageRead`, and `OpImageWrite`.
  Evidence: `tests/vulkan/fixtures/VulkanStorageImageDescriptorArrayShader.cgl`,
  `tests/vulkan/fixtures/VulkanStorageImageNonUniformDescriptorArrayShader.cgl`,
  `testNonUniformDescriptorIndexFamilyTargetCapabilities`,
  `testVulkanNonUniformDescriptorIndexSourceAndReflection`,
  `testStorageImageHIRABI`, `testStorageImageReflectionDocumentModel`, and
  `testStorageImageDiagnostics`.

- Shared frontend, diagnostics, and optimizer evidence pins the storage-image
  descriptor-array HIR ABI, numeric and folded-constant sizes, dynamic uniform
  and nonuniform index paths, targeted runtime-array diagnostics, reflection
  metadata, target nonuniform capability classification, and optimizer
  side-effect boundaries around indexed
  `imageLoad`/`imageStore`.
  Evidence: `tests/frontend/fixtures/StorageImageDescriptorArrayHIRShader.cgl`,
  `tests/frontend/fixtures/StorageImageNonUniformDescriptorArrayHIRShader.cgl`,
  `tests/optimizer/fixtures/StorageImageArrayOptimizerBoundaryShader.cgl`,
  `tests/optimizer/fixtures/StorageImageNonuniformArrayOptimizerBoundaryShader.cgl`,
  `tests/check-failures/BadRuntimeStorageImageArrayShader.cgl`,
  `testStorageImageHIRABI`, `testStorageImageDiagnostics`,
  `testNonUniformDescriptorIndexFamilyTargetCapabilities`,
  `testVulkanNonUniformDescriptorIndexSourceAndReflection`,
  `testStorageImageReflectionDocumentModel`, and `testHIRSideEffectSummaries`.

These rows do not claim runtime or unsized storage-image descriptor arrays,
bindless storage images, image atomics, mip/lod/sample operands,
multisample/cube/3D storage images, coherent storage-image qualifiers,
helper-function image parameters, broader memory-model guarantees, or
CrossGL-Translator changes. Storage-image access qualifiers are tracked by the
Batch 41 rows below; explicit layout format metadata is tracked by the Batch 42
rows below.

## Batch 41 Rows

These rows extend storage-image support to source-level `readonly`,
`writeonly`, and explicit `readwrite` access qualifiers on the supported
`image2D` and `image2DArray` storage-image families, including fixed-size
descriptor arrays where target lowering has registered evidence. The existing
storage-image scope remains unchanged: runtime or unsized storage-image
descriptor arrays, bindless storage images, image atomics, mip/lod/sample
operands, multisample/cube/3D storage images, coherent storage-image
qualifiers, helper-function image parameters, broader memory-model guarantees,
and CrossGL-Translator changes are still not claimed by these rows. Explicit
layout format metadata is tracked by the Batch 42 rows below.

- Shared frontend, HIR, target-capability, and diagnostics evidence preserves
  the declared access on storage-image resources as read-only, write-only, or
  read-write, emits the access in text HIR and CrossGL IR, classifies
  `storageImage` target capabilities as `read-only`, `write-only`, and
  `read-write`, rejects access qualifiers on non-storage-image resources, and
  rejects stores through read-only images and loads from write-only images,
  including fixed-array element access.
  Evidence: `tests/frontend/fixtures/StorageImageAccessQualifierHIRShader.cgl`,
  `tests/check-failures/BadStorageImageReadWriteAccessShader.cgl`, and
  `testStorageImageAccessQualifiers`.

- DirectX source-package lowering accepts read-only, write-only, and read-write
  storage-image declarations for direct 2D and 2D-array images. The source
  package continues to use HLSL UAV `RWTexture2D*` resources while reflection
  and target capabilities carry the access distinctions.
  Evidence:
  `tests/directx/fixtures/DirectXStorageImageAccessQualifierShader.cgl`,
  `cglc_dump_backend_directx_storage_image_access_qualifier`, and
  `cglc_build_directx_storage_image_access_qualifier_source_package`.

- OpenGL source-package lowering accepts read-only, write-only, and read-write
  storage-image declarations for direct 2D and 2D-array images. GLSL output
  emits `readonly` and `writeonly` image uniform qualifiers, with explicit
  `readwrite` lowered to the ordinary read-write image uniform form.
  Evidence: `tests/opengl/fixtures/OpenGLStorageImageAccessQualifierShader.cgl`,
  `cglc_dump_backend_opengl_storage_image_access_qualifier`, and
  `cglc_build_opengl_storage_image_access_qualifier_source_package`.

- Metal lowering maps read-only, write-only, and read-write storage-image
  resources to `access::read`, `access::write`, and `access::read_write`,
  respectively. Native Metal evidence covers direct 2D/2D-array resources and
  fixed-size descriptor arrays.
  Evidence: `tests/metal/fixtures/MetalStorageImageAccessQualifierShader.cgl`,
  `tests/metal/fixtures/MetalStorageImageAccessQualifierDescriptorArrayShader.cgl`,
  `cglc_dump_backend_metal_storage_image_access_qualifier`,
  `cglc_dump_backend_metal_storage_image_access_qualifier_descriptor_array`,
  `cglc_build_metal_storage_image_access_qualifier_native`, and
  `cglc_build_metal_storage_image_access_qualifier_descriptor_array_native`.

- Vulkan target lowering models read-only storage images with `NonWritable`,
  write-only storage images with `NonReadable`, and read-write storage images
  without either access decoration. The current target fixture covers direct and
  fixed-array 2D storage images, including nonuniform indexed read-only and
  write-only arrays; the shared HIR and diagnostics tests above pin the access
  semantics consumed by the Vulkan lowering path.
  Evidence: `tests/vulkan/fixtures/VulkanStorageImageAccessQualifierShader.cgl`
  and `testStorageImageAccessQualifiers`.

## Batch 42 Rows

These rows extend storage-image declarations with explicit
`layout(..., format = r32f)`, `layout(..., format = r32i)`, and
`layout(..., format = r32ui)` metadata on the supported direct 2D
storage-image families. The explicit format must match the source image
domain: `r32f` for `image2D`, `r32i` for `iimage2D`, and `r32ui` for
`uimage2D`. The metadata does not change the CrossGL source type, `imageLoad`
return vector, or `imageStore` payload vector.

Batch 43 extends the same explicit-format coverage to fixed-size
storage-image descriptor arrays and fixed-size nonuniform storage-image
descriptor arrays using explicit `nonuniform(...)` indices.
Evidence: `tests/fixtures/StorageImageExplicitFormatDescriptorArrayShader.cgl`,
`cglc_check_storage_image_explicit_format_descriptor_array_hir`,
`cglc_check_storage_image_explicit_format_descriptor_array_hir_preserves_format`,
`cglc_build_directx_storage_image_explicit_format_descriptor_array_source_package`,
`cglc_build_opengl_storage_image_explicit_format_descriptor_array_source_package`,
`cglc_dump_backend_directx_storage_image_explicit_format_descriptor_array`,
`cglc_dump_backend_opengl_storage_image_explicit_format_descriptor_array`,
`cglc_dump_backend_metal_storage_image_explicit_format_descriptor_array`,
`cglc_dump_backend_vulkan_storage_image_explicit_format_descriptor_array`,
`cglc_build_vulkan_storage_image_explicit_format_descriptor_array_native`, and
`cglc_build_metal_storage_image_explicit_format_descriptor_array_native`.

- Shared parser, HIR, CrossGL IR, diagnostics, target-capability, schema, and
  reflection evidence preserves the declared `storageImageFormat` metadata from
  layout syntax through resource and target-resource binding reflection, while
  rejecting incompatible formats and format layouts on non-storage-image
  resources.
  Evidence: `tests/fixtures/StorageImageExplicitFormatShader.cgl`,
  `tests/check-failures/BadStorageImageFormatLayoutShader.cgl`,
  `cglc_check_storage_image_explicit_format_hir`,
  `cglc_check_storage_image_explicit_format_hir_preserves_format`,
  `cglc_check_storage_image_format_layout_failure`,
  `testStorageImageReflectionDocumentModel`,
  `docs/schemas/reflection-v1.schema.json`, and
  `tools/json_schema_semantics/reflection_v1.py`.

- OpenGL source-package lowering uses the explicit storage-image format as the
  GLSL image layout qualifier, so `r32f`, `r32i`, and `r32ui` are emitted
  instead of the default `rgba32*` formats when the source layout declares
  them. Access qualifiers continue to lower independently as `readonly`,
  `writeonly`, or the ordinary read-write image uniform form.
  Evidence: `tests/fixtures/StorageImageExplicitFormatShader.cgl`,
  `cglc_check_storage_image_explicit_format_hir_preserves_format`, and
  `cglc_build_opengl_storage_image_explicit_format_source_package`.

- Vulkan native lowering uses the explicit storage-image format in SPIR-V image
  types and reflection metadata, mapping `r32f`, `r32i`, and `r32ui` to
  `R32f`, `R32i`, and `R32ui` respectively while retaining
  `VK_DESCRIPTOR_TYPE_STORAGE_IMAGE`, `UniformConstant`, and image read/write
  lowering.
  Evidence: `tests/fixtures/StorageImageExplicitFormatShader.cgl`,
  `cglc_check_storage_image_explicit_format_hir_preserves_format`,
  `cglc_dump_backend_vulkan_storage_image_explicit_format`, and
  `cglc_build_vulkan_storage_image_explicit_format_native`.

- DirectX and Metal preserve explicit `storageImageFormat` metadata in shared
  reflection and target-capability records, but their API source types remain
  unformatted: HLSL continues to emit `RWTexture2D*` / `RWTexture2DArray*`
  payload types, and MSL continues to emit `texture2d*` / `texture2d_array*`
  access-qualified texture arguments.
  Evidence: `tests/fixtures/StorageImageExplicitFormatShader.cgl`,
  `cglc_check_storage_image_explicit_format_hir_preserves_format`,
  `cglc_build_directx_storage_image_explicit_format_source_package`, and
  `cglc_build_metal_storage_image_explicit_format_native`.

These rows do not claim coherent storage-image qualifiers, image atomics,
mip/lod/sample operands, multisample/cube/3D storage images, helper-function
image parameters, broader memory-model guarantees, or CrossGL-Translator
changes.

## Batch 44-47 Storage-Image Atomics

Batch 44 introduced `imageAtomicAdd(image, coordinates, value)` and
`imageAtomicExchange(image, coordinates, value)`. Batch 45 extends the same
surface to `imageAtomicMin`, `imageAtomicMax`, `imageAtomicAnd`,
`imageAtomicOr`, and `imageAtomicXor` for `iimage2D`, `uimage2D`,
`iimage2DArray`, and `uimage2DArray`, including fixed-size descriptor arrays.
The resource must be read-write and must use explicit `r32i` or `r32ui` format
metadata; default `rgba32i`/`rgba32ui` storage-image formats are not
atomic-capable in this scope. Signed images return and accept `int`; unsigned
images return and accept `uint`. Coordinates remain `ivec2` for 2D images and
`ivec3` for 2D-array images.

- Shared frontend, diagnostics, target-capability, side-effect, optimizer, and
  cross-repo contract coverage pins scalar return typing, explicit-format
  requirements, read-write access requirements, descriptor-array and nonuniform
  descriptor-index paths, optimizer ordering boundaries, and Translator parse
  compatibility for the shared fixtures.
  Evidence: `tests/fixtures/StorageImageAtomicShader.cgl`,
  `tests/fixtures/StorageImageAtomicDescriptorArrayShader.cgl`,
  `tests/check-failures/BadStorageImageAtomicShader.cgl`,
  `tests/optimizer/fixtures/StorageImageAtomicOptimizerBoundaryShader.cgl`,
  `cglc_check_storage_image_atomic_hir`,
  `cglc_check_storage_image_atomic_descriptor_array_hir`,
  `cglc_check_storage_image_atomic_failure`,
  `cglc_optimizer_storage_image_atomic_boundary_check`,
  `cglc_optimizer_hir_storage_image_atomic_order`,
  `testHIRTypeSemanticsHelpers`, `testHIRIntrinsicRegistry`,
  `testHIRSideEffectSummaries`, and
  `tools/cross_repo_language_contract.json`.

- OpenGL source-package lowering preserves `r32i`/`r32ui` image layout
  qualifiers and emits native GLSL storage-image atomic calls for direct and
  fixed-size descriptor-array storage images. Nonuniform descriptor indexing
  continues to enable `GL_EXT_nonuniform_qualifier` and lower through
  `nonuniformEXT(...)`.
  Evidence: `tests/opengl/fixtures/OpenGLStorageImageAtomicShader.cgl`,
  `tests/fixtures/StorageImageAtomicDescriptorArrayShader.cgl`,
  `cglc_dump_backend_opengl_storage_image_atomic`,
  `cglc_dump_backend_opengl_storage_image_atomic_descriptor_array`,
  `cglc_build_opengl_storage_image_atomic_source_package`, and
  `cglc_build_opengl_storage_image_atomic_descriptor_array_source_package`.

- Vulkan native lowering models atomic-capable storage images as
  `VK_DESCRIPTOR_TYPE_STORAGE_IMAGE` descriptors with `R32i` / `R32ui` SPIR-V
  image formats, lowers through `OpImageTexelPointer`, and emits `OpAtomicIAdd`,
  `OpAtomicExchange`, signed/unsigned `OpAtomicSMin` / `OpAtomicUMin`,
  signed/unsigned `OpAtomicSMax` / `OpAtomicUMax`, `OpAtomicAnd`, `OpAtomicOr`,
  and `OpAtomicXor` with the initial relaxed/device-scope semantics used by the
  rest of the prototype atomic lowering.
  Evidence: `tests/vulkan/fixtures/VulkanStorageImageAtomicShader.cgl`,
  `tests/fixtures/StorageImageAtomicDescriptorArrayShader.cgl`,
  `cglc_dump_backend_vulkan_storage_image_atomic`,
  `cglc_dump_backend_vulkan_storage_image_atomic_descriptor_array`,
  `cglc_build_vulkan_storage_image_atomic_native`,
  `cglc_build_vulkan_storage_image_atomic_spvasm_snippets`,
  `cglc_build_vulkan_storage_image_atomic_descriptor_array_native`, and
  `cglc_build_vulkan_storage_image_atomic_descriptor_array_spvasm_snippets`.

- DirectX source-package lowering emits atomic-capable `r32i` / `r32ui`
  storage images as scalar typed UAVs (`RWTexture2D<int>` / `RWTexture2D<uint>`
  and `RWTexture2DArray<int>` / `RWTexture2DArray<uint>`) and lowers
  declaration/assignment capture plus statement-form `imageAtomic*` calls
  through HLSL `InterlockedAdd`, `InterlockedExchange`, `InterlockedMin`,
  `InterlockedMax`, `InterlockedAnd`, `InterlockedOr`, and `InterlockedXor`.
  Fixed descriptor arrays and `nonuniform(...)` indices reuse the existing
  `NonUniformResourceIndex(...)` convention. When the same `r32i` / `r32ui`
  resource is used for scalar image atomics and vector `imageLoad` /
  `imageStore`, DirectX keeps one scalar typed UAV, constructs the CrossGL
  vector load result from the scalar x lane, and stores only the source
  vector's x lane.
  Evidence: `cglc_dump_backend_directx_storage_image_atomic`,
  `cglc_dump_backend_directx_storage_image_atomic_descriptor_array`,
  `cglc_build_directx_storage_image_atomic_source_package`,
  `cglc_build_directx_storage_image_atomic_descriptor_array_source_package`,
  and
  `cglc_build_directx_mixed_storage_image_atomic_access_source_package`.

- Metal native lowering emits atomic-capable `r32i` / `r32ui` storage images
  as scalar `texture2d<int/uint, access::read_write>` and
  `texture2d_array<int/uint, access::read_write>` resources, then lowers
  `imageAtomic*` calls to Metal texture atomic member functions such as
  `atomic_fetch_add`, `atomic_exchange`, `atomic_fetch_min`,
  `atomic_fetch_max`, `atomic_fetch_and`, `atomic_fetch_or`, and
  `atomic_fetch_xor`. Metal returns vector results for texture atomics, so the
  lowering uses scalar payload constructors (`int4(...)` / `uint4(...)`) and
  captures the `.x` lane. A Metal-specific descriptor-array fixture keeps ABI
  slots unique while covering `nonuniform(...)` descriptor indices.
  Evidence: `cglc_dump_backend_metal_storage_image_atomic`,
  `cglc_dump_backend_metal_storage_image_atomic_descriptor_array`,
  `cglc_build_metal_storage_image_atomic_native`,
  `cglc_build_metal_storage_image_atomic_descriptor_array_native`,
  `cglc_build_metal_storage_image_atomic_source_package`, and
  `cglc_build_metal_storage_image_atomic_descriptor_array_source_package`.

These rows do not claim float-image atomics, vector-payload image atomics,
implicit/default storage-image formats for atomics, read-only or write-only
atomic resources, coherent/volatile qualifiers, configurable memory scope or
memory semantics, compare-and-swap image atomics,
multisample/cube/3D image atomics, helper-function image parameters, or
Translator implementation changes beyond parse/contract coverage.

## Batch 66-67 Rows

- Malformed HIR expression and statement shapes fail closed before package or
  backend support predicates can treat partial HIR as supported. Texture
  sample, `textureCompare`, and `textureCompareLod` HIR nodes additionally keep
  typed operand/result verifier coverage before backend/package lowering.
  HIR-only resource shape diagnostics cover unresolved stage entry points,
  duplicate resource names and bindings, resources without types, invalid mixed
  runtime/fixed descriptor arrays, and unsupported runtime storage-image
  descriptor arrays before backend/package lowering.
  Shared Translator contract cases using split hex literals and `else if`
  chains remain accepted after the fail-closed repair.
  Evidence: `testBackendExpressionSupportPolicyHelper`,
  `testHIROptimizationPipelineDuplicateResourceBindingValidation`,
  `testHIROptimizationPipelineDuplicateResourceValidation`,
  `testHIROptimizationPipelineExpressionShapeValidation`,
  `testHIROptimizationPipelineMissingEntryPointValidation`,
  `testHIROptimizationPipelineResourceShapeValidation`,
  `testHIROptimizationPipelineRuntimeResourceArrayShapeValidation`,
  `testHIROptimizationPipelineStatementShapeValidation`,
  `testHIROptimizationPipelineStorageImageRuntimeArrayValidation`,
  `testHIRTextureExpressionTypedValidation`,
  `testExpressionParserRejectsMalformedTokens`,
  `testExpressionParserAcceptsSharedContractConstructs`, and
  `tools/cross_repo_language_contract.json` entries for
  `compiler/tests/fixtures/TextureOnlyNonUniformUintDescriptorArraySampleShader.cgl`
  and `translator/examples/gpu_computing/MatrixMultiplication.cgl`.

- Doctor JSON toolchain reporting has hermetic `PATH` probe evidence for both
  available and missing optional tools with fallback disabled. This is discovery
  evidence only; it does not claim the host has native toolchains installed.
  Evidence: `cglc_doctor_json_toolchain_path_tools_available`,
  `cglc_doctor_json_toolchain_path_tools_missing`, and
  `cglc_doctor_json_schema_toolchain`.

- Install/CPack layout and package reproducibility are smoke-covered as release
  hardening, not as new target-language support.
  Evidence: `cglc_install_layout_smoke`, `cglc_cpack_layout_smoke`, and
  `cglc_package_reproducibility`.

- DirectX graphics source packages have fake-`dxc` evidence for bundling a
  `.dxil` `nativeBinary` artifact for vertex/fragment HLSL when the toolchain
  succeeds. The same coverage keeps failing or unavailable `dxc` paths as
  source-package outputs with `nativeBinaryStatus=planned`; fake tool output is
  not evidence that real DXIL validates on the host.
  Evidence: `cglc_build_directx_graphics_resources_fake_dxc_success`,
  `cglc_build_directx_graphics_shadow_compare_lod_fake_dxc_success`,
  `cglc_build_directx_graphics_resources_fake_dxc_tool_failure`,
  `cglc_build_directx_graphics_resources_fake_dxc_unavailable`, and
  `tests/toolchain/FakeShaderTool.cmake` checks for `vs_6_0` / `ps_6_0` and
  `vs_6_7` / `ps_6_7` entry-point invocations.

- Release publish has an end-to-end happy-path checker from package-set export
  through bundle verification, publish planning/staging, local-filesystem
  publish, GCS dry-run manifest generation, upload preflight, mock upload, and
  fake-`gcloud` GCS upload. This is not evidence for live remote publication
  with real credentials.
  Evidence: `cglc_package_release_publish_flow` and
  `tools/check_package_release_publish_flow.py`.

- HIR represents `break`, `continue`, and `discard` as explicit
  control-transfer statements, removes unreachable statements after them, and
  the DirectX, OpenGL, and Metal source backends emit their native source forms
  (`discard_fragment()` for Metal).
  Evidence: `tests/frontend/fixtures/HIRControlTransferShader.cgl`,
  `cglc_check_hir_control_transfer_explicit_statements`,
  `cglc_check_fragment_discard_hir_statement`,
  `cglc_check_hir_control_transfer_unreachable_cleanup`, and
  `testHIRControlTransferStatements`.

- Vulkan graphics now has prototype native-package evidence for structured
  selection, structured loops, and loop-local `break` / `continue` in the
  conservative graphics subset. Unsupported raw graphics body statements remain
  rejection-only via `vulkan.prototype-unsupported-graphics-body`.
  Evidence: `tests/vulkan/fixtures/VulkanGraphicsLoopShader.cgl`,
  `tests/vulkan/fixtures/VulkanGraphicsLoopControlShader.cgl`,
  `cglc_build_vulkan_graphics_loop_native`,
  `cglc_build_vulkan_graphics_loop_spvasm_native`,
  `cglc_build_vulkan_graphics_loop_control_native`,
  `cglc_build_vulkan_graphics_loop_control_spvasm_native`, and
  `testVulkanGraphicsStructuredStatementDiagnostics` for the remaining raw-HIR
  unsupported diagnostic family.

- Vulkan graphics native packages support fixed-size texture/sampler descriptor
  arrays, explicit nonuniform texture/sampler descriptor indexing, vertex-stage
  texture sampling, fragment texture sampling, shadow comparison sampling,
  shadow comparison with explicit LOD, 2D-array shadow comparison resources with
  optional explicit LOD, and shadow descriptor arrays in the fixture-scoped
  graphics subset. The package CTests assert reflection feature
  fields for `resource.descriptor-array`, `layout.fixed-array`,
  `operation.index-access`, `operation.nonuniform-descriptor-index`,
  `operation.nonuniform-texture-descriptor-index`, and
  `operation.nonuniform-sampler-descriptor-index`; no separate
  `explain-targets`, `doctor --json`, or debug-metadata evidence row is claimed
  for these Vulkan graphics fixtures yet.
  Evidence:
  `tests/vulkan/fixtures/VulkanGraphicsTextureSamplerDescriptorArrayShader.cgl`,
  `tests/vulkan/fixtures/VulkanGraphicsNonUniformDescriptorArrayShader.cgl`,
  `tests/vulkan/fixtures/VulkanGraphicsTextureSamplerShader.cgl`,
  `tests/vulkan/fixtures/VulkanGraphicsVertexTextureSamplerShader.cgl`,
  `tests/vulkan/fixtures/VulkanGraphicsVertexShadowCompareShader.cgl`,
  `tests/vulkan/fixtures/VulkanGraphicsShadowCompareShader.cgl`,
  `tests/vulkan/fixtures/VulkanGraphicsShadowCompareLodShader.cgl`,
  `tests/vulkan/fixtures/VulkanGraphicsShadowArrayUnsupportedShader.cgl`,
  `tests/vulkan/fixtures/VulkanGraphicsShadowArrayLodUnsupportedShader.cgl`,
  `tests/vulkan/fixtures/VulkanGraphicsShadowDescriptorArrayShader.cgl`,
  `cglc_build_vulkan_graphics_texture_sampler_descriptor_array_native`,
  `cglc_build_vulkan_graphics_texture_sampler_descriptor_array_spvasm_native`,
  `cglc_build_vulkan_graphics_nonuniform_descriptor_array_native`,
  `cglc_build_vulkan_graphics_nonuniform_descriptor_array_spvasm_native`,
  `cglc_build_vulkan_graphics_texture_sampler_native`,
  `cglc_build_vulkan_graphics_texture_sampler_spvasm_native`,
  `cglc_build_vulkan_graphics_vertex_texture_sampler_native`,
  `cglc_build_vulkan_graphics_vertex_texture_sampler_spvasm_native`,
  `cglc_build_vulkan_graphics_vertex_shadow_compare_native`,
  `cglc_build_vulkan_graphics_vertex_shadow_compare_spvasm_native`,
  `cglc_build_vulkan_graphics_shadow_compare_native`,
  `cglc_build_vulkan_graphics_shadow_compare_spvasm_native`,
  `cglc_build_vulkan_graphics_shadow_compare_lod_native`,
  `cglc_build_vulkan_graphics_shadow_compare_lod_spvasm_native`,
  `cglc_build_vulkan_graphics_shadow_array_native`,
  `cglc_build_vulkan_graphics_shadow_array_spvasm_native`,
  `cglc_build_vulkan_graphics_shadow_array_lod_native`,
  `cglc_build_vulkan_graphics_shadow_array_lod_spvasm_native`,
  `cglc_build_vulkan_graphics_shadow_descriptor_array_native`, and
  `cglc_build_vulkan_graphics_shadow_descriptor_array_spvasm_native`.

- Vulkan graphics native packages support vertex/fragment uniform buffers and
  graphics math intrinsic calls in the fixture-scoped native subset.
  Evidence: `tests/vulkan/fixtures/VulkanGraphicsUniformBufferShader.cgl`,
  `tests/vulkan/fixtures/VulkanGraphicsMathIntrinsicShader.cgl`,
  `cglc_build_vulkan_graphics_uniform_buffer_native`,
  `cglc_build_vulkan_graphics_uniform_buffer_spvasm_native`,
  `cglc_build_vulkan_graphics_math_intrinsic_native`, and
  `cglc_build_vulkan_graphics_math_intrinsic_spvasm_native`.

- Vulkan graphics native packages support same-stage scalar/vector/struct helper
  functions in the conservative graphics subset. The package CTests assert
  SPIR-V `OpFunction`, `OpFunctionParameter`, `OpReturnValue`, and
  `OpFunctionCall` evidence for helper-to-helper and entry-to-helper calls.
  Evidence: `tests/vulkan/fixtures/VulkanGraphicsHelperFunctionShader.cgl`,
  `cglc_build_vulkan_graphics_helper_function_native`,
  `cglc_build_vulkan_graphics_helper_function_spvasm_native`, and
  `testVulkanGraphicsHelperFunctionPrototypeAssembly`.

## Batch 75 Rows

These rows close the public evidence gap for backend support added before this
batch by making the package support visible through `explain-targets`,
`doctor --json`, and debug metadata target-capability summaries. Package target
semantics remain unchanged: DirectX and OpenGL rows are source-package rows,
while Metal and Vulkan rows are native-package rows.

- DirectX graphics source packages support non-array storage-buffer resources
  in vertex and fragment stages, including shared resource names across stages
  when the HLSL register class, set, binding, and resource type are compatible.
  The target explanation and debug metadata expose this as source-package
  support with `resource.storage-buffer`, `layout.vector-storage-buffer`,
  `operation.storage-buffer-read`, and `operation.storage-buffer-write`
  required capabilities; missing capabilities remain limited to the optional
  native DXIL/toolchain evidence.
  Evidence:
  `tests/directx/fixtures/DirectXGraphicsStorageBufferResourceShader.cgl`,
  `cglc_build_directx_graphics_storage_buffer_resources_source_package`,
  `cglc_build_directx_graphics_storage_buffer_resources_fake_dxc_success`,
  `cglc_explain_targets_directx_graphics_storage_buffer_source_package_evidence`,
  `cglc_doctor_json_directx_graphics_storage_buffer_source_package_evidence`,
  and
  `cglc_dump_debug_directx_graphics_storage_buffer_target_capabilities_evidence`.

- Metal native graphics packages support fixed-size texture, sampler, and
  comparison-sampler descriptor arrays in vertex and fragment stages. The
  target explanation and debug metadata expose this as native support with
  `resource.descriptor-array`, `layout.fixed-array`,
  `texture.depth-compare-format`, and texture sampling/explicit-LOD
  capabilities.
  Evidence: `tests/metal/fixtures/MetalGraphicsDescriptorArrayShader.cgl`,
  `cglc_build_metal_graphics_descriptor_array_native`,
  `cglc_build_metal_graphics_descriptor_array_fake_xcrun_success`,
  `cglc_explain_targets_metal_graphics_descriptor_array_native_evidence`,
  `cglc_doctor_json_metal_graphics_descriptor_array_native_evidence`, and
  `cglc_dump_debug_metal_graphics_descriptor_array_target_capabilities_evidence`.

- OpenGL graphics source packages support fixed-size texture and sampler
  descriptor arrays in vertex and fragment stages. The OpenGL source-package
  evidence keeps sampler resources represented through combined sampler uniforms
  while target explanation and debug metadata expose
  `resource.descriptor-array`, `layout.fixed-array`,
  `resource.sampled-texture`, `resource.sampler-state`, and
  texture-sampling capabilities; missing capabilities remain limited to the
  optional native GLSL/toolchain/validation evidence.
  Evidence:
  `tests/opengl/fixtures/OpenGLGraphicsDescriptorArrayResourcesShader.cgl`,
  `cglc_dump_backend_opengl_graphics_descriptor_array_resources`,
  `cglc_build_opengl_graphics_descriptor_array_resources_source_package`,
  `cglc_package_verify_json_schema_opengl_graphics_descriptor_array_source_package`,
  `cglc_explain_targets_opengl_graphics_descriptor_array_source_package_evidence`,
  `cglc_doctor_json_opengl_graphics_descriptor_array_source_package_evidence`,
  and
  `cglc_dump_debug_opengl_graphics_descriptor_array_target_capabilities_evidence`.

- Vulkan native packages support one runtime texture descriptor array and one
  runtime sampler descriptor array per Vulkan descriptor binding class, plus the
  combined texture/sampler fixture and runtime shadow descriptor array fixture.
  The target explanation and debug metadata expose successful native support
  with `resource.runtime-descriptor-array`,
  `resource.runtime-texture-descriptor-array`,
  `resource.runtime-sampler-descriptor-array`, `layout.runtime-array`, and
  `resource.descriptor-array`; conflict coverage still rejects multiple
  unbounded arrays in the same binding class.
  Evidence:
  `tests/vulkan/fixtures/VulkanRuntimeTextureDescriptorArrayPolicyShader.cgl`,
  `tests/vulkan/fixtures/VulkanRuntimeSamplerDescriptorArrayPolicyShader.cgl`,
  `tests/vulkan/fixtures/VulkanRuntimeTextureSamplerDescriptorArrayPolicyShader.cgl`,
  `tests/vulkan/fixtures/VulkanRuntimeShadowDescriptorArrayShader.cgl`,
  `tests/vulkan/fixtures/VulkanRuntimeTextureDescriptorArrayConflictShader.cgl`,
  `cglc_build_vulkan_runtime_texture_descriptor_array_native`,
  `cglc_build_vulkan_runtime_sampler_descriptor_array_native`,
  `cglc_build_vulkan_runtime_texture_sampler_descriptor_array_native`,
  `cglc_build_vulkan_runtime_shadow_descriptor_array_native`,
  `cglc_build_vulkan_runtime_texture_descriptor_array_conflict_planned_failure`,
  `cglc_explain_targets_vulkan_runtime_texture_sampler_descriptor_array_native_evidence`,
  `cglc_doctor_json_vulkan_runtime_texture_sampler_descriptor_array_native_evidence`,
  and
  `cglc_dump_debug_vulkan_runtime_texture_sampler_descriptor_array_target_capabilities_evidence`.

## Native-v0 Unsupported Stage Evidence

- Tessellation and ray stage spellings remain CrossTL-only for v0 native
  compilation. They must produce the planned
  `spec.unsupported-for-native-v0` diagnostic instead of being silently accepted
  as native shader stages or drifting into a no-stage parse fallback.
  Evidence: `tests/check-failures/BadUnsupportedTessellationStageShader.cgl`,
  `tests/check-failures/BadUnsupportedRayStageShader.cgl`,
  `tests/check-failures/BadUnsupportedRayIntersectionStageShader.cgl`,
  `tests/check-failures/BadUnsupportedRayClosestHitStageShader.cgl`,
  `tests/check-failures/BadUnsupportedRayMissStageShader.cgl`,
  `tests/check-failures/BadUnsupportedRayAnyHitStageShader.cgl`,
  `tests/check-failures/BadUnsupportedRayCallableStageShader.cgl`,
  `cglc_check_unsupported_native_v0_tessellation_stage_failure`,
  `cglc_check_unsupported_native_v0_ray_stage_failure`,
  `cglc_check_unsupported_native_v0_ray_intersection_stage_failure`,
  `cglc_check_unsupported_native_v0_ray_closest_hit_stage_failure`,
  `cglc_check_unsupported_native_v0_ray_miss_stage_failure`,
  `cglc_check_unsupported_native_v0_ray_any_hit_stage_failure`, and
  `cglc_check_unsupported_native_v0_ray_callable_stage_failure`.
