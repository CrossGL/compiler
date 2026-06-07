add_test(NAME cglc_dump_backend_metal
  COMMAND cglc dump-ir ${CROSSGL_SIMPLE_SHADER} --stage backend --target metal)
set(CROSSGL_SOURCE_FOR_OMITTED_HEADER_REGEX [=[for \(; true; \) \{.*for \(; value < 4; \) \{.*for \(int i = 0; true; i\+\+\) \{]=])
add_test(NAME cglc_dump_backend_metal_for_omitted_header
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_FOR_OMITTED_HEADER_COMPUTE_SHADER}
    -DTARGET=metal
    -DMODE=dump-backend
    "-DMUST_CONTAIN=${CROSSGL_SOURCE_FOR_OMITTED_HEADER_REGEX}"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
set(CROSSGL_METAL_FLOAT_EQUALITY_NEGATION_REGEX [=[bool equalityNegationFloat = \(dynamicFloat != 31\.0\);.*bool inequalityNegationFloat = \(dynamicFloat == 32\.0\);]=])
add_test(NAME cglc_dump_backend_metal_float_equality_negation
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_FLOAT_EQUALITY_NEGATION_BACKEND_SHADER}
    -DTARGET=metal
    -DMODE=dump-backend
    "-DMUST_CONTAIN=${CROSSGL_METAL_FLOAT_EQUALITY_NEGATION_REGEX}"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
set(CROSSGL_METAL_BOOLEAN_DE_MORGAN_REGEX [=[bool deMorganAnd = \(!base \|\| dynamicIndex <= 17\);.*bool deMorganOr = \(!base && dynamicIndex <= 18\);.*bool deMorganComparisonAnd = \(dynamicIndex >= 19 \|\| dynamicIndex <= 20\);.*bool deMorganComparisonOr = \(dynamicIndex >= 21 && dynamicIndex <= 22\);]=])
add_test(NAME cglc_dump_backend_metal_boolean_de_morgan
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_BOOLEAN_DE_MORGAN_BACKEND_SHADER}
    -DTARGET=metal
    -DMODE=dump-backend
    "-DMUST_CONTAIN=${CROSSGL_METAL_BOOLEAN_DE_MORGAN_REGEX}"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
set(CROSSGL_METAL_SELECT_EXPRESSION_REGEX [=[int selectedInt = base \? dynamicIndex \+ 1 : dynamicIndex \+ 2;.*bool selectedBool = base \? dynamicIndex > 3 : dynamicIndex > 4;.*values\[2\] = selectedBool \? 1 : 0;]=])
add_test(NAME cglc_dump_backend_metal_select_expression
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_SELECT_EXPRESSION_BACKEND_SHADER}
    -DTARGET=metal
    -DMODE=dump-backend
    "-DMUST_CONTAIN=${CROSSGL_METAL_SELECT_EXPRESSION_REGEX}"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
set(CROSSGL_METAL_GRAPHICS_STAGE_ENTRYPOINTS_REGEX [=[vertex RasterPayload vertex_main\(MeshVertex input \[\[stage_in\]\], constant FrameParams& frame \[\[buffer\(0\)\]\]\) \{
  RasterPayload output;.*fragment ColorTarget fragment_main\(FragmentPayload input \[\[stage_in\]\], texture2d<float> colorMap \[\[texture\(2\)\]\], sampler linearSampler \[\[sampler\(3\)\]\]\) \{
  ColorTarget output;]=])
add_test(NAME cglc_dump_backend_metal_graphics_stage_entrypoints
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CMAKE_CURRENT_SOURCE_DIR}/tests/metal/fixtures/MetalGraphicsStageResourcesShader.cgl
    -DTARGET=metal
    -DMODE=dump-backend
    "-DMUST_CONTAIN=${CROSSGL_METAL_GRAPHICS_STAGE_ENTRYPOINTS_REGEX}"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
set(CROSSGL_METAL_GRAPHICS_VARYING_PACK_REGEX [=[struct PackedVertex \{
  float3 position \[\[attribute\(0\)\]\];
  float3 normal \[\[attribute\(1\)\]\];
  float2 texCoord \[\[attribute\(2\)\]\];
  float weight \[\[attribute\(3\)\]\];
\};

struct VertexPayload \{
  float2 uv;
  float4 position \[\[position\]\];
  float3 lighting;
  float weight;
\};

struct FragmentPayload \{
  float2 uv;
  float3 lighting;
  float weight;
\};]=])
add_test(NAME cglc_dump_backend_metal_graphics_vertex_attribute_varying_shape
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_METAL_GRAPHICS_VARYING_PACK_SHADER}
    -DTARGET=metal
    -DMODE=dump-backend
    "-DMUST_CONTAIN=${CROSSGL_METAL_GRAPHICS_VARYING_PACK_REGEX}"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_dump_backend_metal_graphics_vertex_uniform_resource
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CMAKE_CURRENT_SOURCE_DIR}/tests/metal/fixtures/MetalGraphicsStageResourcesShader.cgl
    -DTARGET=metal
    -DMODE=dump-backend
    "-DMUST_CONTAIN=constant FrameParams& frame \\[\\[buffer\\(0\\)\\]\\]"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_dump_backend_metal_graphics_texture_sampler_resources
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CMAKE_CURRENT_SOURCE_DIR}/tests/metal/fixtures/MetalGraphicsStageResourcesShader.cgl
    -DTARGET=metal
    -DMODE=dump-backend
    "-DMUST_CONTAIN=texture2d<float> colorMap \\[\\[texture\\(2\\)\\]\\], sampler linearSampler \\[\\[sampler\\(3\\)\\]\\]"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_dump_backend_metal_graphics_shadow_depth_resource
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CMAKE_CURRENT_SOURCE_DIR}/tests/metal/fixtures/MetalGraphicsShadowCompareLodShader.cgl
    -DTARGET=metal
    -DMODE=dump-backend
    "-DMUST_CONTAIN=depth2d<float> shadowMap \\[\\[texture\\(2\\)\\]\\], sampler shadowCompareSampler \\[\\[sampler\\(5\\)\\]\\]"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_dump_backend_metal_graphics_shadow_compare_lod_call
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CMAKE_CURRENT_SOURCE_DIR}/tests/metal/fixtures/MetalGraphicsShadowCompareLodShader.cgl
    -DTARGET=metal
    -DMODE=dump-backend
    "-DMUST_CONTAIN=shadowMap\\.sample_compare\\(shadowCompareSampler, input\\.uv, input\\.shadowDepth, level\\(2\\.0\\)\\)"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_dump_backend_metal_runtime_tail_folded_zero_block_index
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CMAKE_CURRENT_SOURCE_DIR}/tests/metal/fixtures/MetalRuntimeTailFoldedZeroBlockIndexShader.cgl
    -DTARGET=metal
    -DMODE=dump-backend
    "-DMUST_CONTAIN=reinterpret_cast<device float4\\*>"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
set(CROSSGL_METAL_WORKGROUP_BARRIER_WORKGROUP_REGEX [=[tile\[0\] = values\[0\];
  threadgroup_barrier\(mem_flags::mem_threadgroup\);
  float first = tile\[0\];]=])
add_test(NAME cglc_dump_backend_metal_workgroup_barrier_call
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CMAKE_CURRENT_SOURCE_DIR}/tests/metal/fixtures/MetalWorkgroupBarrierShader.cgl
    -DTARGET=metal
    -DMODE=dump-backend
    "-DMUST_CONTAIN=${CROSSGL_METAL_WORKGROUP_BARRIER_WORKGROUP_REGEX}"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
set(CROSSGL_METAL_WORKGROUP_BARRIER_ALIAS_REGEX [=[tile\[1\] = first \+ 1\.0;
  threadgroup_barrier\(mem_flags::mem_threadgroup\);
  values\[1\] = tile\[1\];]=])
add_test(NAME cglc_dump_backend_metal_barrier_alias_call
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CMAKE_CURRENT_SOURCE_DIR}/tests/metal/fixtures/MetalWorkgroupBarrierShader.cgl
    -DTARGET=metal
    -DMODE=dump-backend
    "-DMUST_CONTAIN=${CROSSGL_METAL_WORKGROUP_BARRIER_ALIAS_REGEX}"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
set(CROSSGL_METAL_ATOMIC_ADD_REGEX [=[kernel void compute_main\(uint3 gl_LocalInvocationID \[\[thread_position_in_threadgroup\]\], device atomic_int\* counters \[\[buffer\(0\)\]\], device atomic_uint\* unsignedCounters \[\[buffer\(1\)\]\]\) \{
  threadgroup atomic_int tile\[GROUP_SIZE\];
  threadgroup atomic_uint unsignedTile\[GROUP_SIZE\];
  uint index = gl_LocalInvocationID\.x;
  uint unsignedDelta = gl_LocalInvocationID\.x;
  atomic_fetch_add_explicit\(&counters\[index\], 1, memory_order_relaxed\);
  atomic_fetch_add_explicit\(&unsignedCounters\[index\], unsignedDelta, memory_order_relaxed\);
  atomic_fetch_add_explicit\(&tile\[index\], 1, memory_order_relaxed\);
  atomic_fetch_add_explicit\(&unsignedTile\[index\], unsignedDelta, memory_order_relaxed\);]=])
add_test(NAME cglc_dump_backend_metal_atomic_add_lowering
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CMAKE_CURRENT_SOURCE_DIR}/tests/metal/fixtures/MetalAtomicAddShader.cgl
    -DTARGET=metal
    -DMODE=dump-backend
    "-DMUST_CONTAIN=${CROSSGL_METAL_ATOMIC_ADD_REGEX}"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
set(CROSSGL_METAL_ATOMIC_ADD_RETURN_REGEX [=[kernel void compute_main\(uint3 gl_GlobalInvocationID \[\[thread_position_in_grid\]\], uint3 gl_LocalInvocationID \[\[thread_position_in_threadgroup\]\], device atomic_int\* counters \[\[buffer\(0\)\]\], device atomic_uint\* unsignedCounters \[\[buffer\(1\)\]\], device CompatCounters\* compatCounters \[\[buffer\(2\)\]\], device int\* values \[\[buffer\(3\)\]\], device uint\* unsignedValues \[\[buffer\(4\)\]\]\) \{
  threadgroup atomic_int tile\[GROUP_SIZE\];
  threadgroup atomic_uint unsignedTile\[GROUP_SIZE\];
  uint index = gl_LocalInvocationID\.x;
  uint globalIndex = gl_GlobalInvocationID\.x;
  uint unsignedDelta = globalIndex \+ 1;
  atomic_fetch_add_explicit\(&counters\[index\], 1, memory_order_relaxed\);
  int oldStorage = atomic_fetch_add_explicit\(&counters\[index\], 2, memory_order_relaxed\);
  oldStorage = atomic_fetch_add_explicit\(&counters\[index\], 3, memory_order_relaxed\);
  uint oldUnsigned = atomic_fetch_add_explicit\(&unsignedCounters\[index\], unsignedDelta, memory_order_relaxed\);
  int oldShared = atomic_fetch_add_explicit\(&tile\[index\], 1, memory_order_relaxed\);
  uint oldUnsignedShared = atomic_fetch_add_explicit\(&unsignedTile\[index\], unsignedDelta, memory_order_relaxed\);
  int oldCompat = atomic_fetch_add_explicit\(reinterpret_cast<device atomic_int\*>\(&compatCounters->active_count\), 1, memory_order_relaxed\);
  uint oldUnsignedCompat = atomic_fetch_add_explicit\(reinterpret_cast<device atomic_uint\*>\(&compatCounters->spawn_count\), unsignedDelta, memory_order_relaxed\);]=])
add_test(NAME cglc_dump_backend_metal_atomic_add_return_capture_lowering
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CMAKE_CURRENT_SOURCE_DIR}/tests/metal/fixtures/MetalAtomicAddReturnShader.cgl
    -DTARGET=metal
    -DMODE=dump-backend
    "-DMUST_CONTAIN=${CROSSGL_METAL_ATOMIC_ADD_RETURN_REGEX}"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
set(CROSSGL_METAL_ATOMIC_MINMAX_REGEX [=[kernel void compute_main\(uint3 gl_GlobalInvocationID \[\[thread_position_in_grid\]\], uint3 gl_LocalInvocationID \[\[thread_position_in_threadgroup\]\], device atomic_int\* counters \[\[buffer\(0\)\]\], device atomic_uint\* unsignedCounters \[\[buffer\(1\)\]\], device CompatCounters\* compatCounters \[\[buffer\(2\)\]\], device int\* values \[\[buffer\(3\)\]\], device uint\* unsignedValues \[\[buffer\(4\)\]\]\) \{
  threadgroup atomic_int tile\[GROUP_SIZE\];
  threadgroup atomic_uint unsignedTile\[GROUP_SIZE\];
  uint index = gl_LocalInvocationID\.x;
  uint globalIndex = gl_GlobalInvocationID\.x;
  int value = values\[index\];
  uint unsignedValue = globalIndex \+ 1;
  atomic_fetch_min_explicit\(&counters\[index\], value, memory_order_relaxed\);
  atomic_fetch_max_explicit\(&unsignedCounters\[index\], unsignedValue, memory_order_relaxed\);
  int oldMin = atomic_fetch_min_explicit\(&counters\[index\], value, memory_order_relaxed\);
  int oldMax = atomic_fetch_max_explicit\(&counters\[index\], 1, memory_order_relaxed\);
  oldMin = atomic_fetch_min_explicit\(&counters\[index\], 1, memory_order_relaxed\);
  uint oldMaxU = atomic_fetch_max_explicit\(&unsignedCounters\[index\], unsignedValue, memory_order_relaxed\);
  int oldShared = atomic_fetch_min_explicit\(&tile\[index\], value, memory_order_relaxed\);
  uint oldSharedU = atomic_fetch_max_explicit\(&unsignedTile\[index\], unsignedValue, memory_order_relaxed\);
  int oldCompat = atomic_fetch_max_explicit\(reinterpret_cast<device atomic_int\*>\(&compatCounters->active_count\), 1, memory_order_relaxed\);
  uint oldCompatU = atomic_fetch_min_explicit\(reinterpret_cast<device atomic_uint\*>\(&compatCounters->spawn_count\), unsignedValue, memory_order_relaxed\);]=])
add_test(NAME cglc_dump_backend_metal_atomic_minmax_lowering
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CMAKE_CURRENT_SOURCE_DIR}/tests/metal/fixtures/MetalAtomicMinMaxShader.cgl
    -DTARGET=metal
    -DMODE=dump-backend
    "-DMUST_CONTAIN=${CROSSGL_METAL_ATOMIC_MINMAX_REGEX}"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
set(CROSSGL_METAL_ATOMIC_EXCHANGE_REGEX [=[kernel void compute_main\(uint3 gl_GlobalInvocationID \[\[thread_position_in_grid\]\], uint3 gl_LocalInvocationID \[\[thread_position_in_threadgroup\]\], device atomic_int\* counters \[\[buffer\(0\)\]\], device atomic_uint\* unsignedCounters \[\[buffer\(1\)\]\], device CompatCounters\* compatCounters \[\[buffer\(2\)\]\], device int\* values \[\[buffer\(3\)\]\], device uint\* unsignedValues \[\[buffer\(4\)\]\]\) \{
  threadgroup atomic_int tile\[GROUP_SIZE\];
  threadgroup atomic_uint unsignedTile\[GROUP_SIZE\];
  uint index = gl_LocalInvocationID\.x;
  uint globalIndex = gl_GlobalInvocationID\.x;
  int value = values\[index\];
  uint unsignedValue = globalIndex \+ 1;
  atomic_exchange_explicit\(&counters\[index\], value, memory_order_relaxed\);
  atomic_exchange_explicit\(&unsignedCounters\[index\], unsignedValue, memory_order_relaxed\);
  atomic_exchange_explicit\(&tile\[index\], value, memory_order_relaxed\);
  atomic_exchange_explicit\(&unsignedTile\[index\], unsignedValue, memory_order_relaxed\);
  int oldStorage = atomic_exchange_explicit\(&counters\[index\], 1, memory_order_relaxed\);
  oldStorage = atomic_exchange_explicit\(&counters\[index\], value, memory_order_relaxed\);
  uint oldUnsigned = atomic_exchange_explicit\(&unsignedCounters\[index\], unsignedValue, memory_order_relaxed\);
  int oldShared = atomic_exchange_explicit\(&tile\[index\], value, memory_order_relaxed\);
  uint oldSharedU = atomic_exchange_explicit\(&unsignedTile\[index\], unsignedValue, memory_order_relaxed\);
  int oldCompat = atomic_exchange_explicit\(reinterpret_cast<device atomic_int\*>\(&compatCounters->active_count\), 1, memory_order_relaxed\);
  uint oldCompatU = atomic_exchange_explicit\(reinterpret_cast<device atomic_uint\*>\(&compatCounters->spawn_count\), unsignedValue, memory_order_relaxed\);]=])
add_test(NAME cglc_dump_backend_metal_atomic_exchange_lowering
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CMAKE_CURRENT_SOURCE_DIR}/tests/metal/fixtures/MetalAtomicExchangeShader.cgl
    -DTARGET=metal
    -DMODE=dump-backend
    "-DMUST_CONTAIN=${CROSSGL_METAL_ATOMIC_EXCHANGE_REGEX}"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
set(CROSSGL_METAL_ATOMIC_BITWISE_REGEX [=[kernel void compute_main\(uint3 gl_LocalInvocationID \[\[thread_position_in_threadgroup\]\], device atomic_int\* counters \[\[buffer\(0\)\]\], device atomic_uint\* unsignedCounters \[\[buffer\(1\)\]\], device CompatCounters\* compatCounters \[\[buffer\(2\)\]\], device int\* values \[\[buffer\(3\)\]\], device uint\* unsignedValues \[\[buffer\(4\)\]\]\) \{
  threadgroup atomic_int tile\[GROUP_SIZE\];
  threadgroup atomic_uint unsignedTile\[GROUP_SIZE\];
  uint index = gl_LocalInvocationID\.x;
  int mask = values\[index\] \+ 1;
  uint unsignedMask = index \+ 1;
  atomic_fetch_and_explicit\(&counters\[index\], mask, memory_order_relaxed\);
  atomic_fetch_or_explicit\(&unsignedCounters\[index\], unsignedMask, memory_order_relaxed\);
  atomic_fetch_xor_explicit\(&tile\[index\], mask, memory_order_relaxed\);
  atomic_fetch_and_explicit\(&unsignedTile\[index\], unsignedMask, memory_order_relaxed\);
  int oldAnd = atomic_fetch_and_explicit\(&counters\[index\], mask, memory_order_relaxed\);
  int oldOr = atomic_fetch_or_explicit\(&counters\[index\], 1, memory_order_relaxed\);
  oldAnd = atomic_fetch_xor_explicit\(&counters\[index\], 1, memory_order_relaxed\);
  uint oldOrU = atomic_fetch_or_explicit\(&unsignedCounters\[index\], unsignedMask, memory_order_relaxed\);
  uint oldXorU = atomic_fetch_xor_explicit\(&unsignedCounters\[index\], unsignedMask, memory_order_relaxed\);
  int oldShared = atomic_fetch_or_explicit\(&tile\[index\], mask, memory_order_relaxed\);
  uint oldSharedU = atomic_fetch_xor_explicit\(&unsignedTile\[index\], unsignedMask, memory_order_relaxed\);
  int oldCompat = atomic_fetch_and_explicit\(reinterpret_cast<device atomic_int\*>\(&compatCounters->active_count\), 1, memory_order_relaxed\);
  uint oldCompatU = atomic_fetch_or_explicit\(reinterpret_cast<device atomic_uint\*>\(&compatCounters->spawn_count\), unsignedMask, memory_order_relaxed\);]=])
add_test(NAME cglc_dump_backend_metal_atomic_bitwise_lowering
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CMAKE_CURRENT_SOURCE_DIR}/tests/metal/fixtures/MetalAtomicBitwiseShader.cgl
    -DTARGET=metal
    -DMODE=dump-backend
    "-DMUST_CONTAIN=${CROSSGL_METAL_ATOMIC_BITWISE_REGEX}"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_dump_backend_vulkan
  COMMAND cglc dump-ir ${CROSSGL_SIMPLE_SHADER} --stage backend --target vulkan)
add_test(NAME cglc_dump_backend_vulkan_for_omitted_header_debug_projection
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_FOR_OMITTED_HEADER_COMPUTE_SHADER}
    -DTARGET=vulkan
    -DMODE=dump-backend
    "-DMUST_CONTAIN=crossgl.for condition \"true\"[^\n]*\n        crossgl.assign \"value\" = \"value \\+ 1\"[^\n]*\n.*crossgl.for condition \"value < 4\"[^\n]*\n        crossgl.assign \"value\" = \"value \\+ 1\"[^\n]*\n.*crossgl.for condition \"true\" update \"i\\+\\+\""
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_dump_backend_vulkan_resources
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_RESOURCE_SHADER}
    -DTARGET=vulkan
    -DMODE=dump-backend
    -DMUST_CONTAIN=VK_DESCRIPTOR_TYPE_SAMPLED_IMAGE
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_dump_backend_vulkan_resource_arrays
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_RESOURCE_ARRAY_SHADER}
    -DTARGET=vulkan
    -DMODE=dump-backend
    -DMUST_CONTAIN=descriptor_array_size
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_dump_backend_vulkan_spirv_skeleton
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_RESOURCE_SHADER}
    -DTARGET=vulkan
    -DMODE=dump-backend
    -DMUST_CONTAIN=LocalSize
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_dump_backend_vulkan_minimal_compute
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_MINIMAL_COMPUTE_SHADER}
    -DTARGET=vulkan
    -DMODE=dump-backend
    -DMUST_CONTAIN=spirv.EntryPoint
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_dump_backend_vulkan_graphics_stage_io
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_VULKAN_GRAPHICS_TEXTURE_SAMPLER_SHADER}
    -DTARGET=vulkan
    -DMODE=dump-backend
    "-DMUST_CONTAIN=spirv.EntryPoint Vertex @vertex_main \"main\"[^\n\r]*[\n\r]+  spirv.EntryPoint Fragment @fragment_main \"main\""
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_dump_backend_vulkan_graphics_sampled_image_descriptor
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_VULKAN_GRAPHICS_TEXTURE_SAMPLER_SHADER}
    -DTARGET=vulkan
    -DMODE=dump-backend
    "-DMUST_CONTAIN=vulkan.descriptor @albedo set 0 binding 1 descriptor_type \"VK_DESCRIPTOR_TYPE_SAMPLED_IMAGE\" storage_class \"UniformConstant\" binding_class \"sampledImage\" spirv_type \"OpTypeImage<float, 2D, sampled=1>\""
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_dump_backend_vulkan_graphics_sampler_descriptor
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_VULKAN_GRAPHICS_TEXTURE_SAMPLER_SHADER}
    -DTARGET=vulkan
    -DMODE=dump-backend
    "-DMUST_CONTAIN=vulkan.descriptor @linearSampler set 0 binding 2 descriptor_type \"VK_DESCRIPTOR_TYPE_SAMPLER\" storage_class \"UniformConstant\" binding_class \"sampler\" spirv_type \"OpTypeSampler\""
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_dump_backend_vulkan_graphics_texture_sampler_descriptor_array
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_VULKAN_GRAPHICS_TEXTURE_SAMPLER_DESCRIPTOR_ARRAY_SHADER}
    -DTARGET=vulkan
    -DMODE=dump-backend
    "-DMUST_CONTAIN=vulkan.descriptor @albedoMaps set 0 binding 1 descriptor_type \"VK_DESCRIPTOR_TYPE_SAMPLED_IMAGE\".*spirv_type \"OpTypeArray<OpTypeImage<float, 2D, sampled=1>, 2>\" descriptor_array_size \"2\".*vulkan.descriptor @linearSamplers set 0 binding 2 descriptor_type \"VK_DESCRIPTOR_TYPE_SAMPLER\".*spirv_type \"OpTypeArray<OpTypeSampler, 2>\" descriptor_array_size \"2\""
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_dump_backend_vulkan_graphics_vertex_uniform_descriptor
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_VULKAN_GRAPHICS_UNIFORM_BUFFER_SHADER}
    -DTARGET=vulkan
    -DMODE=dump-backend
    "-DMUST_CONTAIN=vulkan.descriptor @vertexParams set 0 binding 0 descriptor_type \"VK_DESCRIPTOR_TYPE_UNIFORM_BUFFER\" storage_class \"Uniform\" binding_class \"uniformBuffer\" spirv_type \"OpTypeStruct<VertexParams>\""
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_dump_backend_vulkan_graphics_fragment_uniform_descriptor
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_VULKAN_GRAPHICS_UNIFORM_BUFFER_SHADER}
    -DTARGET=vulkan
    -DMODE=dump-backend
    "-DMUST_CONTAIN=vulkan.descriptor @fragmentParams set 0 binding 1 descriptor_type \"VK_DESCRIPTOR_TYPE_UNIFORM_BUFFER\" storage_class \"Uniform\" binding_class \"uniformBuffer\" spirv_type \"OpTypeStruct<FragmentParams>\""
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_dump_backend_vulkan_graphics_shadow_depth_descriptor
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_VULKAN_GRAPHICS_SHADOW_COMPARE_LOD_SHADER}
    -DTARGET=vulkan
    -DMODE=dump-backend
    "-DMUST_CONTAIN=vulkan.descriptor @shadowMap set 0 binding 2 descriptor_type \"VK_DESCRIPTOR_TYPE_SAMPLED_IMAGE\" storage_class \"UniformConstant\" binding_class \"sampledImage\" spirv_type \"OpTypeImage<depth_compare, 2D, sampled=1>\""
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_dump_backend_vulkan_graphics_shadow_compare_lod_call
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_VULKAN_GRAPHICS_SHADOW_COMPARE_LOD_SHADER}
    -DTARGET=vulkan
    -DMODE=dump-backend
    "-DMUST_CONTAIN=crossgl\\.decl %visibility : !crossgl\\.f32 = \"texture_compare_lod\\(shadowMap, shadowSampler, input\\.uv, 0\\.5, 2\\.0\\)\""
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_dump_backend_vulkan_graphics_shadow_descriptor_array
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_VULKAN_GRAPHICS_SHADOW_DESCRIPTOR_ARRAY_SHADER}
    -DTARGET=vulkan
    -DMODE=dump-backend
    "-DMUST_CONTAIN=vulkan.descriptor @shadowMaps set 0 binding 2 descriptor_type \"VK_DESCRIPTOR_TYPE_SAMPLED_IMAGE\".*spirv_type \"OpTypeArray<OpTypeImage<depth_compare, 2D, sampled=1>, 2>\" descriptor_array_size \"2\".*vulkan.descriptor @shadowSamplers set 0 binding 3 descriptor_type \"VK_DESCRIPTOR_TYPE_SAMPLER\".*spirv_type \"OpTypeArray<OpTypeSampler, 2>\" descriptor_array_size \"2\".*texture_compare_lod\\(shadowMaps\\[1\\], shadowSamplers\\[0\\], input\\.uv, 0\\.5, 2\\.0\\)"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
set(CROSSGL_VULKAN_RUNTIME_TEXTURE_DESCRIPTOR_ARRAY_REGEX [=[vulkan.descriptor @maps set 0 binding 1 descriptor_type "VK_DESCRIPTOR_TYPE_SAMPLED_IMAGE" storage_class "UniformConstant" binding_class "sampledImage" spirv_type "OpTypeRuntimeArray<OpTypeImage<float, 2D, sampled=1>>" descriptor_array_size "".*vulkan.descriptor @linearSampler set 0 binding 2 descriptor_type "VK_DESCRIPTOR_TYPE_SAMPLER" storage_class "UniformConstant" binding_class "sampler" spirv_type "OpTypeSampler".*crossgl\.resource @maps : !crossgl\.array<!crossgl\.texture<2d, f32>, >.*texture_sample_lod\(maps\[0\], linearSampler, vec2\(0\.25, 0\.75\), 0\.0\)]=])
add_test(NAME cglc_dump_backend_vulkan_runtime_texture_descriptor_array
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_VULKAN_RUNTIME_TEXTURE_DESCRIPTOR_ARRAY_POLICY_SHADER}
    -DTARGET=vulkan
    -DMODE=dump-backend
    "-DMUST_CONTAIN=${CROSSGL_VULKAN_RUNTIME_TEXTURE_DESCRIPTOR_ARRAY_REGEX}"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
set(CROSSGL_VULKAN_RUNTIME_SAMPLER_DESCRIPTOR_ARRAY_REGEX [=[vulkan.descriptor @map set 0 binding 1 descriptor_type "VK_DESCRIPTOR_TYPE_SAMPLED_IMAGE" storage_class "UniformConstant" binding_class "sampledImage" spirv_type "OpTypeImage<float, 2D, sampled=1>".*vulkan.descriptor @linearSamplers set 0 binding 2 descriptor_type "VK_DESCRIPTOR_TYPE_SAMPLER" storage_class "UniformConstant" binding_class "sampler" spirv_type "OpTypeRuntimeArray<OpTypeSampler>" descriptor_array_size "".*crossgl\.resource @linearSamplers : !crossgl\.array<!crossgl\.sampler, >.*texture_sample_lod\(map, linearSamplers\[0\], vec2\(0\.25, 0\.75\), 0\.0\)]=])
add_test(NAME cglc_dump_backend_vulkan_runtime_sampler_descriptor_array
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_VULKAN_RUNTIME_SAMPLER_DESCRIPTOR_ARRAY_POLICY_SHADER}
    -DTARGET=vulkan
    -DMODE=dump-backend
    "-DMUST_CONTAIN=${CROSSGL_VULKAN_RUNTIME_SAMPLER_DESCRIPTOR_ARRAY_REGEX}"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
set(CROSSGL_VULKAN_RUNTIME_TEXTURE_SAMPLER_DESCRIPTOR_ARRAY_REGEX [=[vulkan.descriptor @maps set 0 binding 1 descriptor_type "VK_DESCRIPTOR_TYPE_SAMPLED_IMAGE" storage_class "UniformConstant" binding_class "sampledImage" spirv_type "OpTypeRuntimeArray<OpTypeImage<float, 2D, sampled=1>>" descriptor_array_size "".*vulkan.descriptor @linearSamplers set 0 binding 2 descriptor_type "VK_DESCRIPTOR_TYPE_SAMPLER" storage_class "UniformConstant" binding_class "sampler" spirv_type "OpTypeRuntimeArray<OpTypeSampler>" descriptor_array_size "".*crossgl\.resource @maps : !crossgl\.array<!crossgl\.texture<2d, f32>, >.*crossgl\.resource @linearSamplers : !crossgl\.array<!crossgl\.sampler, >.*texture_sample_lod\(maps\[0\], linearSamplers\[0\], vec2\(0\.25, 0\.75\), 0\.0\)]=])
add_test(NAME cglc_dump_backend_vulkan_runtime_texture_sampler_descriptor_array
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_VULKAN_RUNTIME_TEXTURE_SAMPLER_DESCRIPTOR_ARRAY_POLICY_SHADER}
    -DTARGET=vulkan
    -DMODE=dump-backend
    "-DMUST_CONTAIN=${CROSSGL_VULKAN_RUNTIME_TEXTURE_SAMPLER_DESCRIPTOR_ARRAY_REGEX}"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
set(CROSSGL_VULKAN_RUNTIME_TEXTURE_SAMPLER_NONUNIFORM_DESCRIPTOR_ARRAY_REGEX [=[vulkan.descriptor @maps set 0 binding 1 descriptor_type "VK_DESCRIPTOR_TYPE_SAMPLED_IMAGE" storage_class "UniformConstant" binding_class "sampledImage" spirv_type "OpTypeRuntimeArray<OpTypeImage<float, 2D, sampled=1>>" descriptor_array_size "".*vulkan.descriptor @linearSamplers set 0 binding 2 descriptor_type "VK_DESCRIPTOR_TYPE_SAMPLER" storage_class "UniformConstant" binding_class "sampler" spirv_type "OpTypeRuntimeArray<OpTypeSampler>" descriptor_array_size "".*vulkan.descriptor @descriptors set 0 binding 3 descriptor_type "VK_DESCRIPTOR_TYPE_STORAGE_BUFFER" storage_class "StorageBuffer" binding_class "storageBuffer" spirv_type "OpTypeRuntimeArray<int>".*crossgl\.resource @maps : !crossgl\.array<!crossgl\.texture<2d, f32>, >.*crossgl\.resource @linearSamplers : !crossgl\.array<!crossgl\.sampler, >.*crossgl\.resource @descriptors : !crossgl\.ptr<!crossgl\.i32>.*texture_sample_lod\(maps\[nonuniform\(descriptor\)\], linearSamplers\[nonuniform\(descriptor\)\], vec2\(0\.25, 0\.75\), 0\.0\)]=])
add_test(NAME cglc_dump_backend_vulkan_runtime_texture_sampler_nonuniform_descriptor_array
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_VULKAN_RUNTIME_TEXTURE_SAMPLER_NONUNIFORM_DESCRIPTOR_ARRAY_SHADER}
    -DTARGET=vulkan
    -DMODE=dump-backend
    "-DMUST_CONTAIN=${CROSSGL_VULKAN_RUNTIME_TEXTURE_SAMPLER_NONUNIFORM_DESCRIPTOR_ARRAY_REGEX}"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
set(CROSSGL_VULKAN_RUNTIME_SHADOW_DESCRIPTOR_ARRAY_REGEX [=[vulkan.descriptor @shadowMaps set 0 binding 1 descriptor_type "VK_DESCRIPTOR_TYPE_SAMPLED_IMAGE" storage_class "UniformConstant" binding_class "sampledImage" spirv_type "OpTypeRuntimeArray<OpTypeImage<depth_compare, 2D, sampled=1>>" descriptor_array_size "".*vulkan.descriptor @shadowSamplers set 0 binding 2 descriptor_type "VK_DESCRIPTOR_TYPE_SAMPLER" storage_class "UniformConstant" binding_class "sampler" spirv_type "OpTypeRuntimeArray<OpTypeSampler>" descriptor_array_size "".*crossgl\.resource @shadowMaps : !crossgl\.array<!crossgl\.texture<2d, depth_compare>, >.*crossgl\.resource @shadowSamplers : !crossgl\.array<!crossgl\.comparison_sampler, >.*texture_compare_lod\(shadowMaps\[0\], shadowSamplers\[0\], vec2\(0\.5, 0\.5\), 0\.25, 0\.0\)]=])
add_test(NAME cglc_dump_backend_vulkan_runtime_shadow_descriptor_array
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_VULKAN_RUNTIME_SHADOW_DESCRIPTOR_ARRAY_SHADER}
    -DTARGET=vulkan
    -DMODE=dump-backend
    "-DMUST_CONTAIN=${CROSSGL_VULKAN_RUNTIME_SHADOW_DESCRIPTOR_ARRAY_REGEX}"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_dump_backend_vulkan_compute_workgroup_barrier_call
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CMAKE_CURRENT_SOURCE_DIR}/tests/vulkan/fixtures/VulkanComputeBarrierShader.cgl
    -DTARGET=vulkan
    -DMODE=dump-backend
    "-DMUST_CONTAIN=crossgl\\.expr \"workgroupBarrier\\(\\)\""
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_dump_backend_vulkan_compute_barrier_alias_call
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CMAKE_CURRENT_SOURCE_DIR}/tests/vulkan/fixtures/VulkanComputeBarrierShader.cgl
    -DTARGET=vulkan
    -DMODE=dump-backend
    "-DMUST_CONTAIN=crossgl\\.expr \"barrier\\(\\)\""
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
if(CROSSGL_HAS_VULKAN_NATIVE_TOOLS)
  add_test(NAME cglc_dump_backend_vulkan_atomic_add_native
    COMMAND ${CMAKE_COMMAND}
      -DCGLC=$<TARGET_FILE:cglc>
      -DINPUT=${CMAKE_CURRENT_SOURCE_DIR}/tests/vulkan/fixtures/VulkanAtomicAddNativeShader.cgl
      -DTARGET=vulkan
      -DMODE=dump-backend
      "-DMUST_CONTAIN=spirv_type \"OpTypeRuntimeArray<int>\""
      -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
  add_test(NAME cglc_dump_backend_vulkan_atomic_add_return_capture
    COMMAND ${CMAKE_COMMAND}
      -DCGLC=$<TARGET_FILE:cglc>
      -DINPUT=${CMAKE_CURRENT_SOURCE_DIR}/tests/vulkan/fixtures/VulkanAtomicAddReturnNativeShader.cgl
      -DTARGET=vulkan
      -DMODE=dump-backend
      "-DMUST_CONTAIN=crossgl\\.decl %oldCompat : !crossgl\\.i32 = \"atomicAdd\\(compat\\[0\\]\\.active_count, 1\\)\""
      -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
  add_test(NAME cglc_dump_backend_vulkan_atomic_minmax_native
    COMMAND ${CMAKE_COMMAND}
      -DCGLC=$<TARGET_FILE:cglc>
      -DINPUT=${CMAKE_CURRENT_SOURCE_DIR}/tests/vulkan/fixtures/VulkanAtomicMinMaxNativeShader.cgl
      -DTARGET=vulkan
      -DMODE=dump-backend
      "-DMUST_CONTAIN=crossgl\\.decl %oldCompatUnsigned : !crossgl\\.u32 = \"atomicMin\\(compat\\[0\\]\\.spawn_count, localValue\\)\""
      -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
  add_test(NAME cglc_dump_backend_vulkan_atomic_exchange_native
    COMMAND ${CMAKE_COMMAND}
      -DCGLC=$<TARGET_FILE:cglc>
      -DINPUT=${CMAKE_CURRENT_SOURCE_DIR}/tests/vulkan/fixtures/VulkanAtomicExchangeNativeShader.cgl
      -DTARGET=vulkan
      -DMODE=dump-backend
      "-DMUST_CONTAIN=crossgl\\.decl %oldCompat : !crossgl\\.i32 = \"atomicExchange\\(compat\\[0\\]\\.active_count, 5\\)\""
      -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
  add_test(NAME cglc_dump_backend_vulkan_atomic_bitwise_native
    COMMAND ${CMAKE_COMMAND}
      -DCGLC=$<TARGET_FILE:cglc>
      -DINPUT=${CMAKE_CURRENT_SOURCE_DIR}/tests/vulkan/fixtures/VulkanAtomicBitwiseNativeShader.cgl
      -DTARGET=vulkan
      -DMODE=dump-backend
      "-DMUST_CONTAIN=crossgl\\.assign \"assignedOr\" = \"atomicOr\\(unsignedCounters\\[0\\], mask\\)\""
      -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
  crossgl_label_optional_native_test(cglc_dump_backend_vulkan_atomic_add_native
    vulkan)
  crossgl_label_optional_native_test(
    cglc_dump_backend_vulkan_atomic_add_return_capture vulkan)
  crossgl_label_optional_native_test(
    cglc_dump_backend_vulkan_atomic_minmax_native vulkan)
  crossgl_label_optional_native_test(
    cglc_dump_backend_vulkan_atomic_exchange_native vulkan)
  crossgl_label_optional_native_test(
    cglc_dump_backend_vulkan_atomic_bitwise_native vulkan)
endif()
add_test(NAME cglc_dump_backend_directx
  COMMAND cglc dump-ir ${CROSSGL_SIMPLE_SHADER} --stage backend --target directx)
add_test(NAME cglc_dump_backend_directx_for_omitted_header
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_FOR_OMITTED_HEADER_COMPUTE_SHADER}
    -DTARGET=directx
    -DMODE=dump-backend
    "-DMUST_CONTAIN=${CROSSGL_SOURCE_FOR_OMITTED_HEADER_REGEX}"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
set(CROSSGL_DIRECTX_FLOAT_EQUALITY_NEGATION_REGEX [=[bool equalityNegationFloat = \(dynamicFloat != 31\.0\);.*bool inequalityNegationFloat = \(dynamicFloat == 32\.0\);]=])
add_test(NAME cglc_dump_backend_directx_float_equality_negation
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_FLOAT_EQUALITY_NEGATION_BACKEND_SHADER}
    -DTARGET=directx
    -DMODE=dump-backend
    "-DMUST_CONTAIN=${CROSSGL_DIRECTX_FLOAT_EQUALITY_NEGATION_REGEX}"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
set(CROSSGL_DIRECTX_BOOLEAN_DE_MORGAN_REGEX [=[bool deMorganAnd = \(!base \|\| dynamicIndex <= 17\);.*bool deMorganOr = \(!base && dynamicIndex <= 18\);.*bool deMorganComparisonAnd = \(dynamicIndex >= 19 \|\| dynamicIndex <= 20\);.*bool deMorganComparisonOr = \(dynamicIndex >= 21 && dynamicIndex <= 22\);]=])
add_test(NAME cglc_dump_backend_directx_boolean_de_morgan
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_BOOLEAN_DE_MORGAN_BACKEND_SHADER}
    -DTARGET=directx
    -DMODE=dump-backend
    "-DMUST_CONTAIN=${CROSSGL_DIRECTX_BOOLEAN_DE_MORGAN_REGEX}"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
set(CROSSGL_DIRECTX_SELECT_EXPRESSION_REGEX [=[int selectedInt = \(base \? dynamicIndex \+ 1 : dynamicIndex \+ 2\);.*bool selectedBool = \(base \? dynamicIndex > 3 : dynamicIndex > 4\);.*values\[2\] = \(selectedBool \? 1 : 0\);]=])
add_test(NAME cglc_dump_backend_directx_select_expression
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_SELECT_EXPRESSION_BACKEND_SHADER}
    -DTARGET=directx
    -DMODE=dump-backend
    "-DMUST_CONTAIN=${CROSSGL_DIRECTX_SELECT_EXPRESSION_REGEX}"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
set(CROSSGL_DIRECTX_GRAPHICS_STAGE_ENTRYPOINTS_REGEX [=[VertexOutput crossgl_user_vertex_main\(VertexInput input\) \{
  VertexOutput output;.*FragmentOutput crossgl_user_fragment_main\(FragmentInput input\) \{
  FragmentOutput output;.*crossgl_vertex_output vertex_main\(crossgl_vertex_input crossgl_input\) \{
  VertexInput crossgl_user_input;.*crossgl_fragment_output fragment_main\(crossgl_fragment_input crossgl_input\) \{
  FragmentInput crossgl_user_input;]=])
add_test(NAME cglc_dump_backend_directx_graphics_stage_entrypoints
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_DIRECTX_GRAPHICS_RESOURCE_SHADER}
    -DTARGET=directx
    -DMODE=dump-backend
    "-DMUST_CONTAIN=${CROSSGL_DIRECTX_GRAPHICS_STAGE_ENTRYPOINTS_REGEX}"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
set(CROSSGL_DIRECTX_GRAPHICS_IO_SHAPE_REGEX [=[struct crossgl_vertex_input \{
  float3 position : POSITION0;
  float2 texCoord : TEXCOORD1;
\};
struct crossgl_vertex_output \{
  float2 uv : TEXCOORD0;
  float4 tint : TEXCOORD1;
  float4 position : SV_Position;
\};
struct crossgl_fragment_input \{
  float2 uv : TEXCOORD0;
  float4 tint : TEXCOORD1;
\};
struct crossgl_fragment_output \{
  float4 color : SV_Target0;
\};]=])
add_test(NAME cglc_dump_backend_directx_graphics_vertex_input_output_varying_shape
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_DIRECTX_GRAPHICS_RESOURCE_SHADER}
    -DTARGET=directx
    -DMODE=dump-backend
    "-DMUST_CONTAIN=${CROSSGL_DIRECTX_GRAPHICS_IO_SHAPE_REGEX}"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
set(CROSSGL_DIRECTX_GRAPHICS_RESOURCES_REGEX [=[cbuffer transform_Buffer : register\(b0, space0\) \{
  Transform transform;
\};
cbuffer material_Buffer : register\(b1, space0\) \{
  Material material;
\};
Texture2D<float4> colorMap : register\(t2, space0\);
SamplerState linearSampler : register\(s3, space0\);]=])
add_test(NAME cglc_dump_backend_directx_graphics_resource_declarations
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_DIRECTX_GRAPHICS_RESOURCE_SHADER}
    -DTARGET=directx
    -DMODE=dump-backend
    "-DMUST_CONTAIN=${CROSSGL_DIRECTX_GRAPHICS_RESOURCES_REGEX}"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
set(CROSSGL_DIRECTX_GRAPHICS_SHADOW_COMPARE_LOD_REGEX [=[Texture2D<float> shadowMap : register\(t2, space1\);
SamplerComparisonState shadowSampler : register\(s3, space1\);.*float visibility = shadowMap\.SampleCmpLevel\(shadowSampler, input\.uv, 0\.5, 2\.0\);]=])
add_test(NAME cglc_dump_backend_directx_graphics_shadow_compare_lod
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_DIRECTX_GRAPHICS_SHADOW_COMPARE_LOD_SHADER}
    -DTARGET=directx
    -DMODE=dump-backend
    "-DMUST_CONTAIN=${CROSSGL_DIRECTX_GRAPHICS_SHADOW_COMPARE_LOD_REGEX}"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_dump_backend_directx_compute_invocation_builtins_signature
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CMAKE_CURRENT_SOURCE_DIR}/tests/directx/fixtures/DirectXComputeInvocationBuiltinShader.cgl
    -DTARGET=directx
    -DMODE=dump-backend
    "-DMUST_CONTAIN=void compute_main\\(uint3 crossgl_GlobalInvocationID : SV_DispatchThreadID, uint3 crossgl_LocalInvocationID : SV_GroupThreadID, uint3 crossgl_WorkGroupID : SV_GroupID\\)"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_dump_backend_directx_compute_invocation_builtins_aliases
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CMAKE_CURRENT_SOURCE_DIR}/tests/directx/fixtures/DirectXComputeInvocationBuiltinShader.cgl
    -DTARGET=directx
    -DMODE=dump-backend
    "-DMUST_CONTAIN=uint3 localId = crossgl_LocalInvocationID;"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_dump_backend_directx_workgroup_shared_scaffold
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CMAKE_CURRENT_SOURCE_DIR}/tests/directx/fixtures/DirectXWorkgroupSharedShader.cgl
    -DTARGET=directx
    -DMODE=dump-backend
    "-DMUST_CONTAIN=groupshared float tile\\[TILE_SIZE\\];"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_dump_backend_directx_workgroup_shared_read_write_scaffold
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CMAKE_CURRENT_SOURCE_DIR}/tests/directx/fixtures/DirectXWorkgroupSharedShader.cgl
    -DTARGET=directx
    -DMODE=dump-backend
    "-DMUST_CONTAIN=tile\\[1\\] = first \\+ 1\\.0;"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_dump_backend_directx_workgroup_barrier_lowering
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CMAKE_CURRENT_SOURCE_DIR}/tests/directx/fixtures/DirectXWorkgroupBarrierShader.cgl
    -DTARGET=directx
    -DMODE=dump-backend
    "-DMUST_CONTAIN=GroupMemoryBarrierWithGroupSync\\(\\);"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_dump_backend_directx_workgroup_barrier_alias_scaffold
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CMAKE_CURRENT_SOURCE_DIR}/tests/directx/fixtures/DirectXWorkgroupBarrierShader.cgl
    -DTARGET=directx
    -DMODE=dump-backend
    "-DMUST_CONTAIN=tile\\[1\\] = tile\\[0\\] \\+ 1\\.0;"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_dump_backend_directx_atomic_add_storage_buffer_lowering
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CMAKE_CURRENT_SOURCE_DIR}/tests/directx/fixtures/DirectXAtomicAddShader.cgl
    -DTARGET=directx
    -DMODE=dump-backend
    "-DMUST_CONTAIN=RWStructuredBuffer<int> counters : register\\(u0, space0\\);"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_dump_backend_directx_atomic_add_groupshared_lowering
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CMAKE_CURRENT_SOURCE_DIR}/tests/directx/fixtures/DirectXAtomicAddShader.cgl
    -DTARGET=directx
    -DMODE=dump-backend
    "-DMUST_CONTAIN=groupshared uint tile\\[GROUP_SIZE\\];"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_dump_backend_directx_atomic_add_interlocked_lowering
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CMAKE_CURRENT_SOURCE_DIR}/tests/directx/fixtures/DirectXAtomicAddShader.cgl
    -DTARGET=directx
    -DMODE=dump-backend
    "-DMUST_CONTAIN=InterlockedAdd\\(counters\\[index\\], delta\\);"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_dump_backend_directx_atomic_add_groupshared_interlocked_lowering
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CMAKE_CURRENT_SOURCE_DIR}/tests/directx/fixtures/DirectXAtomicAddShader.cgl
    -DTARGET=directx
    -DMODE=dump-backend
    "-DMUST_CONTAIN=InterlockedAdd\\(tile\\[crossgl_LocalInvocationID\\.x\\], crossgl_LocalInvocationID\\.x\\);"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_dump_backend_directx_atomic_add_return_declaration_capture
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CMAKE_CURRENT_SOURCE_DIR}/tests/directx/fixtures/DirectXAtomicAddReturnShader.cgl
    -DTARGET=directx
    -DMODE=dump-backend
    "-DMUST_CONTAIN=int oldCounter;[^\n\r]*[\n\r]+  InterlockedAdd\\(counters\\[index\\], delta, oldCounter\\);"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_dump_backend_directx_atomic_add_return_assignment_capture
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CMAKE_CURRENT_SOURCE_DIR}/tests/directx/fixtures/DirectXAtomicAddReturnShader.cgl
    -DTARGET=directx
    -DMODE=dump-backend
    "-DMUST_CONTAIN=InterlockedAdd\\(counters\\[index\\], 1, oldCounter\\);"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_dump_backend_directx_atomic_add_return_unsigned_capture
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CMAKE_CURRENT_SOURCE_DIR}/tests/directx/fixtures/DirectXAtomicAddReturnShader.cgl
    -DTARGET=directx
    -DMODE=dump-backend
    "-DMUST_CONTAIN=InterlockedAdd\\(unsignedCounters\\[unsignedIndex\\], unsignedDelta, oldUnsigned\\);"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_dump_backend_directx_atomic_add_return_groupshared_capture
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CMAKE_CURRENT_SOURCE_DIR}/tests/directx/fixtures/DirectXAtomicAddReturnShader.cgl
    -DTARGET=directx
    -DMODE=dump-backend
    "-DMUST_CONTAIN=InterlockedAdd\\(tile\\[index\\], 1, oldShared\\);"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_dump_backend_directx_atomic_add_return_statement_unchanged
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CMAKE_CURRENT_SOURCE_DIR}/tests/directx/fixtures/DirectXAtomicAddReturnShader.cgl
    -DTARGET=directx
    -DMODE=dump-backend
    "-DMUST_CONTAIN=InterlockedAdd\\(counters\\[index\\], delta\\);"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_dump_backend_directx_atomic_minmax_statement_min_lowering
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CMAKE_CURRENT_SOURCE_DIR}/tests/directx/fixtures/DirectXAtomicMinMaxShader.cgl
    -DTARGET=directx
    -DMODE=dump-backend
    "-DMUST_CONTAIN=InterlockedMin\\(counters\\[index\\], value\\);"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_dump_backend_directx_atomic_minmax_statement_max_lowering
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CMAKE_CURRENT_SOURCE_DIR}/tests/directx/fixtures/DirectXAtomicMinMaxShader.cgl
    -DTARGET=directx
    -DMODE=dump-backend
    "-DMUST_CONTAIN=InterlockedMax\\(counters\\[index\\], value\\);"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_dump_backend_directx_atomic_minmax_unsigned_statement_lowering
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CMAKE_CURRENT_SOURCE_DIR}/tests/directx/fixtures/DirectXAtomicMinMaxShader.cgl
    -DTARGET=directx
    -DMODE=dump-backend
    "-DMUST_CONTAIN=InterlockedMax\\(unsignedCounters\\[unsignedIndex\\], unsignedValue\\);"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_dump_backend_directx_atomic_minmax_groupshared_statement_lowering
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CMAKE_CURRENT_SOURCE_DIR}/tests/directx/fixtures/DirectXAtomicMinMaxShader.cgl
    -DTARGET=directx
    -DMODE=dump-backend
    "-DMUST_CONTAIN=InterlockedMin\\(tile\\[index\\], value\\);"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_dump_backend_directx_atomic_minmax_return_declaration_capture
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CMAKE_CURRENT_SOURCE_DIR}/tests/directx/fixtures/DirectXAtomicMinMaxReturnShader.cgl
    -DTARGET=directx
    -DMODE=dump-backend
    "-DMUST_CONTAIN=int oldMin;[^\n\r]*[\n\r]+  InterlockedMin\\(counters\\[index\\], value, oldMin\\);"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_dump_backend_directx_atomic_minmax_return_assignment_capture
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CMAKE_CURRENT_SOURCE_DIR}/tests/directx/fixtures/DirectXAtomicMinMaxReturnShader.cgl
    -DTARGET=directx
    -DMODE=dump-backend
    "-DMUST_CONTAIN=InterlockedMax\\(counters\\[index\\], 2, oldMax\\);"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_dump_backend_directx_atomic_minmax_return_unsigned_capture
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CMAKE_CURRENT_SOURCE_DIR}/tests/directx/fixtures/DirectXAtomicMinMaxReturnShader.cgl
    -DTARGET=directx
    -DMODE=dump-backend
    "-DMUST_CONTAIN=InterlockedMin\\(unsignedCounters\\[unsignedIndex\\], unsignedValue, oldUnsignedMin\\);"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_dump_backend_directx_atomic_minmax_return_groupshared_capture
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CMAKE_CURRENT_SOURCE_DIR}/tests/directx/fixtures/DirectXAtomicMinMaxReturnShader.cgl
    -DTARGET=directx
    -DMODE=dump-backend
    "-DMUST_CONTAIN=InterlockedMax\\(unsignedTile\\[unsignedIndex\\], unsignedValue, oldUnsignedShared\\);"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_dump_backend_directx_atomic_exchange_statement_scratch
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CMAKE_CURRENT_SOURCE_DIR}/tests/directx/fixtures/DirectXAtomicExchangeShader.cgl
    -DTARGET=directx
    -DMODE=dump-backend
    "-DMUST_CONTAIN=int crossgl_atomic_exchange_old_value;[^\n\r]*[\n\r]+    InterlockedExchange\\(counters\\[index\\], value, crossgl_atomic_exchange_old_value\\);"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_dump_backend_directx_atomic_exchange_unsigned_statement_scratch
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CMAKE_CURRENT_SOURCE_DIR}/tests/directx/fixtures/DirectXAtomicExchangeShader.cgl
    -DTARGET=directx
    -DMODE=dump-backend
    "-DMUST_CONTAIN=uint crossgl_atomic_exchange_old_value;[^\n\r]*[\n\r]+    InterlockedExchange\\(unsignedCounters\\[unsignedIndex\\], unsignedValue, crossgl_atomic_exchange_old_value\\);"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_dump_backend_directx_atomic_exchange_declaration_capture
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CMAKE_CURRENT_SOURCE_DIR}/tests/directx/fixtures/DirectXAtomicExchangeShader.cgl
    -DTARGET=directx
    -DMODE=dump-backend
    "-DMUST_CONTAIN=int oldCounter;[^\n\r]*[\n\r]+  InterlockedExchange\\(counters\\[index\\], 1, oldCounter\\);"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_dump_backend_directx_atomic_exchange_assignment_capture
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CMAKE_CURRENT_SOURCE_DIR}/tests/directx/fixtures/DirectXAtomicExchangeShader.cgl
    -DTARGET=directx
    -DMODE=dump-backend
    "-DMUST_CONTAIN=InterlockedExchange\\(counters\\[index\\], value, oldCounter\\);"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_dump_backend_directx_atomic_exchange_groupshared_capture
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CMAKE_CURRENT_SOURCE_DIR}/tests/directx/fixtures/DirectXAtomicExchangeShader.cgl
    -DTARGET=directx
    -DMODE=dump-backend
    "-DMUST_CONTAIN=InterlockedExchange\\(unsignedTile\\[unsignedIndex\\], unsignedValue, oldUnsignedShared\\);"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_dump_backend_directx_atomic_bitwise_statement_and_lowering
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CMAKE_CURRENT_SOURCE_DIR}/tests/directx/fixtures/DirectXAtomicBitwiseShader.cgl
    -DTARGET=directx
    -DMODE=dump-backend
    "-DMUST_CONTAIN=InterlockedAnd\\(signedMasks\\[index\\], signedMask\\);"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_dump_backend_directx_atomic_bitwise_unsigned_statement_or_lowering
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CMAKE_CURRENT_SOURCE_DIR}/tests/directx/fixtures/DirectXAtomicBitwiseShader.cgl
    -DTARGET=directx
    -DMODE=dump-backend
    "-DMUST_CONTAIN=InterlockedOr\\(unsignedMasks\\[unsignedIndex\\], unsignedMask\\);"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_dump_backend_directx_atomic_bitwise_groupshared_statement_xor_lowering
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CMAKE_CURRENT_SOURCE_DIR}/tests/directx/fixtures/DirectXAtomicBitwiseShader.cgl
    -DTARGET=directx
    -DMODE=dump-backend
    "-DMUST_CONTAIN=InterlockedXor\\(unsignedTile\\[unsignedIndex\\], unsignedMask\\);"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_dump_backend_directx_atomic_bitwise_declaration_capture
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CMAKE_CURRENT_SOURCE_DIR}/tests/directx/fixtures/DirectXAtomicBitwiseShader.cgl
    -DTARGET=directx
    -DMODE=dump-backend
    "-DMUST_CONTAIN=uint oldXor;[^\n\r]*[\n\r]+  InterlockedXor\\(unsignedMasks\\[unsignedIndex\\], unsignedMask, oldXor\\);"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_dump_backend_directx_atomic_bitwise_assignment_capture
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CMAKE_CURRENT_SOURCE_DIR}/tests/directx/fixtures/DirectXAtomicBitwiseShader.cgl
    -DTARGET=directx
    -DMODE=dump-backend
    "-DMUST_CONTAIN=InterlockedOr\\(signedMasks\\[index\\], 1, oldAnd\\);"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_dump_backend_directx_atomic_bitwise_groupshared_capture
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CMAKE_CURRENT_SOURCE_DIR}/tests/directx/fixtures/DirectXAtomicBitwiseShader.cgl
    -DTARGET=directx
    -DMODE=dump-backend
    "-DMUST_CONTAIN=InterlockedAnd\\(unsignedTile\\[unsignedIndex\\], unsignedMask, oldUnsignedShared\\);"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_dump_backend_opengl
  COMMAND cglc dump-ir ${CROSSGL_SIMPLE_SHADER} --stage backend --target opengl)
add_test(NAME cglc_dump_backend_opengl_for_omitted_header
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_FOR_OMITTED_HEADER_COMPUTE_SHADER}
    -DTARGET=opengl
    -DMODE=dump-backend
    "-DMUST_CONTAIN=${CROSSGL_SOURCE_FOR_OMITTED_HEADER_REGEX}"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
set(CROSSGL_OPENGL_FLOAT_EQUALITY_NEGATION_REGEX [=[bool equalityNegationFloat = \(dynamicFloat != 31\.0\);.*bool inequalityNegationFloat = \(dynamicFloat == 32\.0\);]=])
add_test(NAME cglc_dump_backend_opengl_float_equality_negation
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_FLOAT_EQUALITY_NEGATION_BACKEND_SHADER}
    -DTARGET=opengl
    -DMODE=dump-backend
    "-DMUST_CONTAIN=${CROSSGL_OPENGL_FLOAT_EQUALITY_NEGATION_REGEX}"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
set(CROSSGL_OPENGL_BOOLEAN_DE_MORGAN_REGEX [=[bool deMorganAnd = \(!base \|\| dynamicIndex <= 17\);.*bool deMorganOr = \(!base && dynamicIndex <= 18\);.*bool deMorganComparisonAnd = \(dynamicIndex >= 19 \|\| dynamicIndex <= 20\);.*bool deMorganComparisonOr = \(dynamicIndex >= 21 && dynamicIndex <= 22\);]=])
add_test(NAME cglc_dump_backend_opengl_boolean_de_morgan
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_BOOLEAN_DE_MORGAN_BACKEND_SHADER}
    -DTARGET=opengl
    -DMODE=dump-backend
    "-DMUST_CONTAIN=${CROSSGL_OPENGL_BOOLEAN_DE_MORGAN_REGEX}"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
set(CROSSGL_OPENGL_SELECT_EXPRESSION_REGEX [=[int selectedInt = \(base \? dynamicIndex \+ 1 : dynamicIndex \+ 2\);.*bool selectedBool = \(base \? dynamicIndex > 3 : dynamicIndex > 4\);.*values\[2\] = \(selectedBool \? 1 : 0\);]=])
add_test(NAME cglc_dump_backend_opengl_select_expression
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_SELECT_EXPRESSION_BACKEND_SHADER}
    -DTARGET=opengl
    -DMODE=dump-backend
    "-DMUST_CONTAIN=${CROSSGL_OPENGL_SELECT_EXPRESSION_REGEX}"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_dump_backend_opengl_graphics_stage_entrypoints
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_OPENGL_GRAPHICS_RESOURCES_SHADER}
    -DTARGET=opengl
    -DMODE=dump-backend
    "-DMUST_CONTAIN=VertexOutput vertex_main\\(VertexInput crossgl_user_input\\).*FragmentOutput fragment_main\\(FragmentInput crossgl_user_input\\)"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
set(CROSSGL_OPENGL_GRAPHICS_VARYING_PACK_REGEX [=[layout\(location = 0\) in vec3 crossgl_attr_position;
layout\(location = 1\) in vec2 crossgl_attr_texCoord;
layout\(location = 0\) out vec2 crossgl_varying_uv;
layout\(location = 1\) out vec4 crossgl_varying_tint;.*layout\(location = 0\) in vec2 crossgl_varying_uv;
layout\(location = 1\) in vec4 crossgl_varying_tint;
layout\(location = 0\) out vec4 crossgl_out_color;]=])
add_test(NAME cglc_dump_backend_opengl_graphics_vertex_attribute_varying_shape
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_OPENGL_GRAPHICS_TEXTURE_SAMPLER_RESOURCES_SHADER}
    -DTARGET=opengl
    -DMODE=dump-backend
    "-DMUST_CONTAIN=${CROSSGL_OPENGL_GRAPHICS_VARYING_PACK_REGEX}"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_dump_backend_opengl_graphics_vertex_uniform_resource
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_OPENGL_GRAPHICS_TEXTURE_SAMPLER_RESOURCES_SHADER}
    -DTARGET=opengl
    -DMODE=dump-backend
    "-DMUST_CONTAIN=layout\\(binding = 0, std140\\) uniform transform_Uniform \\{[^\n\r]*[\n\r]+  vec4 offset;[^\n\r]*[\n\r]+  vec4 tint;[^\n\r]*[\n\r]+\\} transform;"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
set(CROSSGL_OPENGL_GRAPHICS_TEXTURE_SAMPLER_REGEX [=[layout\(binding = 1, std140\) uniform material_Uniform \{
  vec4 baseColor;
\} material;.*layout\(binding = 2\) uniform sampler2D colorMap;.*sampler linearSampler is represented by OpenGL combined sampler uniforms\.]=])
add_test(NAME cglc_dump_backend_opengl_graphics_texture_sampler_uniform_resources
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_OPENGL_GRAPHICS_TEXTURE_SAMPLER_RESOURCES_SHADER}
    -DTARGET=opengl
    -DMODE=dump-backend
    "-DMUST_CONTAIN=${CROSSGL_OPENGL_GRAPHICS_TEXTURE_SAMPLER_REGEX}"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_dump_backend_opengl_graphics_texture_sampler_lod_call
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_OPENGL_GRAPHICS_TEXTURE_SAMPLER_RESOURCES_SHADER}
    -DTARGET=opengl
    -DMODE=dump-backend
    "-DMUST_CONTAIN=vec4 sampled = textureLod\\(colorMap, crossgl_user_input\\.uv, 0\\.0\\);"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
set(CROSSGL_OPENGL_GRAPHICS_DESCRIPTOR_ARRAY_REGEX [=[layout\(binding = 2\) uniform sampler2D heightMaps\[RESOURCE_COUNT\];.*sampler vertexSamplers is represented by OpenGL combined sampler uniforms\..*vec4 height = textureLod\(heightMaps\[1\], crossgl_user_input\.texCoord, 0\.0\);.*layout\(binding = 4\) uniform sampler2D colorMaps\[RESOURCE_COUNT\];.*vec4 sampled = textureLod\(colorMaps\[1\], crossgl_user_input\.uv, 0\.0\);]=])
add_test(NAME cglc_dump_backend_opengl_graphics_descriptor_array_resources
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_OPENGL_GRAPHICS_DESCRIPTOR_ARRAY_RESOURCES_SHADER}
    -DTARGET=opengl
    -DMODE=dump-backend
    "-DMUST_CONTAIN=${CROSSGL_OPENGL_GRAPHICS_DESCRIPTOR_ARRAY_REGEX}"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
set(CROSSGL_OPENGL_GRAPHICS_SHADOW_COMPARE_LOD_REGEX [=[layout\(binding = 2\) uniform sampler2DShadow shadowMap;.*sampler shadowSampler is represented by OpenGL combined sampler uniforms\..*float visibility = textureLod\(shadowMap, vec3\(crossgl_user_input\.uv, 0\.5\), 1\.5\);]=])
add_test(NAME cglc_dump_backend_opengl_graphics_shadow_compare_lod_resources
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_OPENGL_GRAPHICS_SHADOW_COMPARE_LOD_RESOURCES_SHADER}
    -DTARGET=opengl
    -DMODE=dump-backend
    "-DMUST_CONTAIN=${CROSSGL_OPENGL_GRAPHICS_SHADOW_COMPARE_LOD_REGEX}"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
set(CROSSGL_OPENGL_GRAPHICS_SHADOW_DESCRIPTOR_ARRAY_REGEX [=[#extension GL_EXT_texture_shadow_lod : require.*layout\(binding = 6\) uniform sampler2DShadow vertexShadowMaps\[SHADOW_COUNT\];.*float visibility = textureLod\(vertexShadowMaps\[1\], vec3\(crossgl_user_input\.texCoord, 0\.5\), 0\.0\);.*layout\(binding = 8\) uniform sampler2DArrayShadow shadowAtlases\[SHADOW_COUNT\];.*float atlasVisibility = texture\(shadowAtlases\[1\], vec4\(vec3\(crossgl_user_input\.uv, 0\.0\), 0\.5\)\);]=])
add_test(NAME cglc_dump_backend_opengl_graphics_shadow_descriptor_array_resources
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_OPENGL_GRAPHICS_SHADOW_DESCRIPTOR_ARRAY_SHADER}
    -DTARGET=opengl
    -DMODE=dump-backend
    "-DMUST_CONTAIN=${CROSSGL_OPENGL_GRAPHICS_SHADOW_DESCRIPTOR_ARRAY_REGEX}"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_dump_backend_directx_storage_buffer_scaffold
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_STORAGE_BUFFER_COMPUTE_SHADER}
    -DTARGET=directx
    -DMODE=dump-backend
    -DMUST_CONTAIN=RWStructuredBuffer
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_dump_backend_opengl_storage_buffer_scaffold
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_STORAGE_BUFFER_COMPUTE_SHADER}
    -DTARGET=opengl
    -DMODE=dump-backend
    -DMUST_CONTAIN=std430
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_dump_backend_opengl_workgroup_shared_local_size_scaffold
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CMAKE_CURRENT_SOURCE_DIR}/tests/opengl/fixtures/OpenGLWorkgroupSharedMemoryShader.cgl
    -DTARGET=opengl
    -DMODE=dump-backend
    "-DMUST_CONTAIN=layout\\(local_size_x = 8, local_size_y = 2, local_size_z = 1\\) in;"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_dump_backend_opengl_workgroup_shared_declaration_scaffold
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CMAKE_CURRENT_SOURCE_DIR}/tests/opengl/fixtures/OpenGLWorkgroupSharedMemoryShader.cgl
    -DTARGET=opengl
    -DMODE=dump-backend
    "-DMUST_CONTAIN=shared float tile\\[TILE_SIZE\\];"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_dump_backend_opengl_workgroup_barrier_lowering
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CMAKE_CURRENT_SOURCE_DIR}/tests/opengl/fixtures/OpenGLWorkgroupBarrierShader.cgl
    -DTARGET=opengl
    -DMODE=dump-backend
    "-DMUST_CONTAIN=barrier\\(\\);"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_dump_backend_opengl_atomic_add_storage_buffer_lowering
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CMAKE_CURRENT_SOURCE_DIR}/tests/opengl/fixtures/OpenGLAtomicAddShader.cgl
    -DTARGET=opengl
    -DMODE=dump-backend
    "-DMUST_CONTAIN=int counters\\[\\];"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_dump_backend_opengl_atomic_add_unsigned_storage_buffer_lowering
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CMAKE_CURRENT_SOURCE_DIR}/tests/opengl/fixtures/OpenGLAtomicAddShader.cgl
    -DTARGET=opengl
    -DMODE=dump-backend
    "-DMUST_CONTAIN=uint unsignedCounters\\[\\];"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_dump_backend_opengl_atomic_add_shared_lowering
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CMAKE_CURRENT_SOURCE_DIR}/tests/opengl/fixtures/OpenGLAtomicAddShader.cgl
    -DTARGET=opengl
    -DMODE=dump-backend
    "-DMUST_CONTAIN=shared int tile\\[GROUP_SIZE\\];"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_dump_backend_opengl_atomic_add_call_lowering
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CMAKE_CURRENT_SOURCE_DIR}/tests/opengl/fixtures/OpenGLAtomicAddShader.cgl
    -DTARGET=opengl
    -DMODE=dump-backend
    "-DMUST_CONTAIN=atomicAdd\\(unsignedTile\\[index\\], unsignedDelta\\);"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_dump_backend_opengl_atomic_add_return_declaration_lowering
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CMAKE_CURRENT_SOURCE_DIR}/tests/opengl/fixtures/OpenGLAtomicAddReturnShader.cgl
    -DTARGET=opengl
    -DMODE=dump-backend
    "-DMUST_CONTAIN=int oldStorage = atomicAdd\\(counters\\[index\\], 2\\);"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_dump_backend_opengl_atomic_add_return_assignment_lowering
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CMAKE_CURRENT_SOURCE_DIR}/tests/opengl/fixtures/OpenGLAtomicAddReturnShader.cgl
    -DTARGET=opengl
    -DMODE=dump-backend
    "-DMUST_CONTAIN=oldStorage = atomicAdd\\(counters\\[index\\], 3\\);"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_dump_backend_opengl_atomic_add_return_compat_lowering
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CMAKE_CURRENT_SOURCE_DIR}/tests/opengl/fixtures/OpenGLAtomicAddReturnShader.cgl
    -DTARGET=opengl
    -DMODE=dump-backend
    "-DMUST_CONTAIN=uint oldCompatUnsigned = atomicAdd\\(compatCounters\\[index\\]\\.spawn_count, unsignedDelta\\);"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_dump_backend_opengl_atomic_minmax_statement_lowering
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CMAKE_CURRENT_SOURCE_DIR}/tests/opengl/fixtures/OpenGLAtomicMinMaxReturnShader.cgl
    -DTARGET=opengl
    -DMODE=dump-backend
    "-DMUST_CONTAIN=atomicMin\\(counters\\[index\\], value\\);[^\n\r]*[\n\r]+  atomicMax\\(counters\\[index\\], value\\);"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_dump_backend_opengl_atomic_minmax_return_declaration_lowering
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CMAKE_CURRENT_SOURCE_DIR}/tests/opengl/fixtures/OpenGLAtomicMinMaxReturnShader.cgl
    -DTARGET=opengl
    -DMODE=dump-backend
    "-DMUST_CONTAIN=int oldMin = atomicMin\\(counters\\[index\\], value\\);[^\n\r]*[\n\r]+  int oldMax = atomicMax\\(counters\\[index\\], 1\\);"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_dump_backend_opengl_atomic_minmax_return_assignment_lowering
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CMAKE_CURRENT_SOURCE_DIR}/tests/opengl/fixtures/OpenGLAtomicMinMaxReturnShader.cgl
    -DTARGET=opengl
    -DMODE=dump-backend
    "-DMUST_CONTAIN=oldMin = atomicMin\\(counters\\[index\\], 1\\);"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_dump_backend_opengl_atomic_minmax_unsigned_lowering
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CMAKE_CURRENT_SOURCE_DIR}/tests/opengl/fixtures/OpenGLAtomicMinMaxReturnShader.cgl
    -DTARGET=opengl
    -DMODE=dump-backend
    "-DMUST_CONTAIN=uint oldMaxU = atomicMax\\(unsignedCounters\\[index\\], unsignedValue\\);"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_dump_backend_opengl_atomic_minmax_shared_lowering
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CMAKE_CURRENT_SOURCE_DIR}/tests/opengl/fixtures/OpenGLAtomicMinMaxReturnShader.cgl
    -DTARGET=opengl
    -DMODE=dump-backend
    "-DMUST_CONTAIN=int oldShared = atomicMin\\(tile\\[index\\], value\\);[^\n\r]*[\n\r]+  uint oldSharedU = atomicMax\\(unsignedTile\\[index\\], unsignedValue\\);"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_dump_backend_opengl_atomic_minmax_compat_lowering
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CMAKE_CURRENT_SOURCE_DIR}/tests/opengl/fixtures/OpenGLAtomicMinMaxReturnShader.cgl
    -DTARGET=opengl
    -DMODE=dump-backend
    "-DMUST_CONTAIN=int oldCompat = atomicMax\\(compatCounters\\[index\\]\\.active_count, 1\\);[^\n\r]*[\n\r]+  uint oldCompatU = atomicMin\\(compatCounters\\[index\\]\\.spawn_count, unsignedValue\\);"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_dump_backend_opengl_atomic_exchange_statement_lowering
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CMAKE_CURRENT_SOURCE_DIR}/tests/opengl/fixtures/OpenGLAtomicExchangeReturnShader.cgl
    -DTARGET=opengl
    -DMODE=dump-backend
    "-DMUST_CONTAIN=atomicExchange\\(counters\\[index\\], value\\);[^\n\r]*[\n\r]+  atomicExchange\\(unsignedCounters\\[index\\], unsignedValue\\);[^\n\r]*[\n\r]+  atomicExchange\\(tile\\[index\\], value\\);[^\n\r]*[\n\r]+  atomicExchange\\(unsignedTile\\[index\\], unsignedValue\\);"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_dump_backend_opengl_atomic_exchange_return_declaration_lowering
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CMAKE_CURRENT_SOURCE_DIR}/tests/opengl/fixtures/OpenGLAtomicExchangeReturnShader.cgl
    -DTARGET=opengl
    -DMODE=dump-backend
    "-DMUST_CONTAIN=int oldStorage = atomicExchange\\(counters\\[index\\], value\\);"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_dump_backend_opengl_atomic_exchange_return_assignment_lowering
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CMAKE_CURRENT_SOURCE_DIR}/tests/opengl/fixtures/OpenGLAtomicExchangeReturnShader.cgl
    -DTARGET=opengl
    -DMODE=dump-backend
    "-DMUST_CONTAIN=oldStorage = atomicExchange\\(counters\\[index\\], 1\\);"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_dump_backend_opengl_atomic_exchange_unsigned_lowering
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CMAKE_CURRENT_SOURCE_DIR}/tests/opengl/fixtures/OpenGLAtomicExchangeReturnShader.cgl
    -DTARGET=opengl
    -DMODE=dump-backend
    "-DMUST_CONTAIN=uint oldUnsigned = atomicExchange\\(unsignedCounters\\[index\\], unsignedValue\\);"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_dump_backend_opengl_atomic_exchange_shared_lowering
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CMAKE_CURRENT_SOURCE_DIR}/tests/opengl/fixtures/OpenGLAtomicExchangeReturnShader.cgl
    -DTARGET=opengl
    -DMODE=dump-backend
    "-DMUST_CONTAIN=int oldShared = atomicExchange\\(tile\\[index\\], value\\);[^\n\r]*[\n\r]+  uint oldUnsignedShared = atomicExchange\\(unsignedTile\\[index\\], unsignedValue\\);"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_dump_backend_opengl_atomic_exchange_compat_lowering
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CMAKE_CURRENT_SOURCE_DIR}/tests/opengl/fixtures/OpenGLAtomicExchangeReturnShader.cgl
    -DTARGET=opengl
    -DMODE=dump-backend
    "-DMUST_CONTAIN=int oldCompat = atomicExchange\\(compatCounters\\[index\\]\\.active_count, 1\\);[^\n\r]*[\n\r]+  uint oldCompatUnsigned = atomicExchange\\(compatCounters\\[index\\]\\.spawn_count, unsignedValue\\);"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_dump_backend_opengl_atomic_bitwise_statement_lowering
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CMAKE_CURRENT_SOURCE_DIR}/tests/opengl/fixtures/OpenGLAtomicBitwiseReturnShader.cgl
    -DTARGET=opengl
    -DMODE=dump-backend
    "-DMUST_CONTAIN=atomicAnd\\(counters\\[index\\], mask\\);[^\n\r]*[\n\r]+  atomicOr\\(unsignedCounters\\[index\\], unsignedMask\\);[^\n\r]*[\n\r]+  atomicXor\\(tile\\[index\\], mask\\);[^\n\r]*[\n\r]+  atomicAnd\\(unsignedTile\\[index\\], unsignedMask\\);"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_dump_backend_opengl_atomic_bitwise_return_declaration_lowering
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CMAKE_CURRENT_SOURCE_DIR}/tests/opengl/fixtures/OpenGLAtomicBitwiseReturnShader.cgl
    -DTARGET=opengl
    -DMODE=dump-backend
    "-DMUST_CONTAIN=int oldAnd = atomicAnd\\(counters\\[index\\], mask\\);[^\n\r]*[\n\r]+  int oldOr = atomicOr\\(counters\\[index\\], 1\\);"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_dump_backend_opengl_atomic_bitwise_return_assignment_lowering
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CMAKE_CURRENT_SOURCE_DIR}/tests/opengl/fixtures/OpenGLAtomicBitwiseReturnShader.cgl
    -DTARGET=opengl
    -DMODE=dump-backend
    "-DMUST_CONTAIN=oldAnd = atomicXor\\(counters\\[index\\], 1\\);"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_dump_backend_opengl_atomic_bitwise_unsigned_lowering
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CMAKE_CURRENT_SOURCE_DIR}/tests/opengl/fixtures/OpenGLAtomicBitwiseReturnShader.cgl
    -DTARGET=opengl
    -DMODE=dump-backend
    "-DMUST_CONTAIN=uint oldUnsignedAnd = atomicAnd\\(unsignedCounters\\[index\\], unsignedMask\\);"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_dump_backend_opengl_atomic_bitwise_shared_lowering
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CMAKE_CURRENT_SOURCE_DIR}/tests/opengl/fixtures/OpenGLAtomicBitwiseReturnShader.cgl
    -DTARGET=opengl
    -DMODE=dump-backend
    "-DMUST_CONTAIN=uint oldUnsignedOr = atomicOr\\(unsignedTile\\[index\\], unsignedMask\\);[^\n\r]*[\n\r]+  int oldSharedXor = atomicXor\\(tile\\[index\\], mask\\);"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_dump_backend_opengl_atomic_bitwise_compat_lowering
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CMAKE_CURRENT_SOURCE_DIR}/tests/opengl/fixtures/OpenGLAtomicBitwiseReturnShader.cgl
    -DTARGET=opengl
    -DMODE=dump-backend
    "-DMUST_CONTAIN=int oldCompatOr = atomicOr\\(compatCounters\\[index\\]\\.active_count, 1\\);[^\n\r]*[\n\r]+  uint oldCompatXor = atomicXor\\(compatCounters\\[index\\]\\.spawn_count, unsignedMask\\);"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_dump_backend_opengl_compute_global_invocation_builtin
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CMAKE_CURRENT_SOURCE_DIR}/tests/opengl/fixtures/OpenGLComputeInvocationBuiltinShader.cgl
    -DTARGET=opengl
    -DMODE=dump-backend
    "-DMUST_CONTAIN=uint globalX = gl_GlobalInvocationID\\.x;"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_dump_backend_opengl_compute_local_invocation_builtin
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CMAKE_CURRENT_SOURCE_DIR}/tests/opengl/fixtures/OpenGLComputeInvocationBuiltinShader.cgl
    -DTARGET=opengl
    -DMODE=dump-backend
    "-DMUST_CONTAIN=uint localY = gl_LocalInvocationID\\.y;"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_dump_backend_opengl_compute_workgroup_builtin
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CMAKE_CURRENT_SOURCE_DIR}/tests/opengl/fixtures/OpenGLComputeInvocationBuiltinShader.cgl
    -DTARGET=opengl
    -DMODE=dump-backend
    "-DMUST_CONTAIN=uint groupZ = gl_WorkGroupID\\.z;"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_dump_backend_directx_load_local_scaffold
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_LOAD_LOCAL_COMPUTE_SHADER}
    -DTARGET=directx
    -DMODE=dump-backend
    "-DMUST_CONTAIN=float x = values"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_dump_backend_opengl_load_local_scaffold
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_LOAD_LOCAL_COMPUTE_SHADER}
    -DTARGET=opengl
    -DMODE=dump-backend
    "-DMUST_CONTAIN=float x = values"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_dump_backend_directx_read_modify_scaffold
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_READ_MODIFY_WRITE_COMPUTE_SHADER}
    -DTARGET=directx
    -DMODE=dump-backend
    "-DMUST_CONTAIN=values\\[0\\] = values\\[0\\]"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_dump_backend_opengl_read_modify_scaffold
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_READ_MODIFY_WRITE_COMPUTE_SHADER}
    -DTARGET=opengl
    -DMODE=dump-backend
    "-DMUST_CONTAIN=values\\[0\\] = values\\[0\\]"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_dump_backend_directx_vector_buffer_scaffold
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_VECTOR_BUFFER_COMPUTE_SHADER}
    -DTARGET=directx
    -DMODE=dump-backend
    -DMUST_CONTAIN=float4
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_dump_backend_opengl_vector_buffer_scaffold
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_VECTOR_BUFFER_COMPUTE_SHADER}
    -DTARGET=opengl
    -DMODE=dump-backend
    -DMUST_CONTAIN=vec4
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_dump_backend_directx_if_scaffold
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_IF_COMPUTE_SHADER}
    -DTARGET=directx
    -DMODE=dump-backend
    "-DMUST_CONTAIN=if \\(x > 0.0\\)"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_dump_backend_opengl_if_scaffold
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_IF_COMPUTE_SHADER}
    -DTARGET=opengl
    -DMODE=dump-backend
    "-DMUST_CONTAIN=if \\(x > 0.0\\)"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_dump_backend_directx_if_scoped_scaffold
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_IF_SCOPED_COMPUTE_SHADER}
    -DTARGET=directx
    -DMODE=dump-backend
    "-DMUST_CONTAIN=float scaled = x \\* 2.0"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_dump_backend_opengl_if_scoped_scaffold
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_IF_SCOPED_COMPUTE_SHADER}
    -DTARGET=opengl
    -DMODE=dump-backend
    "-DMUST_CONTAIN=float scaled = x \\* 2.0"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_dump_backend_directx_nested_if_scaffold
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_NESTED_IF_COMPUTE_SHADER}
    -DTARGET=directx
    -DMODE=dump-backend
    "-DMUST_CONTAIN=if \\(scaled > 3.0\\)"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_dump_backend_opengl_nested_if_scaffold
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_NESTED_IF_COMPUTE_SHADER}
    -DTARGET=opengl
    -DMODE=dump-backend
    "-DMUST_CONTAIN=if \\(scaled > 3.0\\)"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_dump_backend_directx_if_return_scaffold
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_IF_RETURN_COMPUTE_SHADER}
    -DTARGET=directx
    -DMODE=dump-backend
    "-DMUST_CONTAIN=return;"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_dump_backend_opengl_if_return_scaffold
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_IF_RETURN_COMPUTE_SHADER}
    -DTARGET=opengl
    -DMODE=dump-backend
    "-DMUST_CONTAIN=return;"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_dump_backend_directx_for_scaffold
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_FOR_COMPUTE_SHADER}
    -DTARGET=directx
    -DMODE=dump-backend
    "-DMUST_CONTAIN=for \\(int i = 0; i < 4; i\\+\\+\\)"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_dump_backend_opengl_for_scaffold
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_FOR_COMPUTE_SHADER}
    -DTARGET=opengl
    -DMODE=dump-backend
    "-DMUST_CONTAIN=for \\(int i = 0; i < 4; i\\+\\+\\)"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_dump_backend_directx_for_stride_scaffold
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_FOR_STRIDE_COMPUTE_SHADER}
    -DTARGET=directx
    -DMODE=dump-backend
    "-DMUST_CONTAIN=for \\(int i = 0; i < 8; i\\+=2\\)"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_dump_backend_opengl_for_stride_scaffold
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_FOR_STRIDE_COMPUTE_SHADER}
    -DTARGET=opengl
    -DMODE=dump-backend
    "-DMUST_CONTAIN=for \\(int i = 0; i < 8; i\\+=2\\)"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_dump_backend_directx_nested_for_scaffold
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_NESTED_FOR_COMPUTE_SHADER}
    -DTARGET=directx
    -DMODE=dump-backend
    "-DMUST_CONTAIN=for \\(int j = 0; j < 2; j\\+\\+\\)"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_dump_backend_opengl_nested_for_scaffold
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_NESTED_FOR_COMPUTE_SHADER}
    -DTARGET=opengl
    -DMODE=dump-backend
    "-DMUST_CONTAIN=for \\(int j = 0; j < 2; j\\+\\+\\)"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_dump_backend_directx_for_dynamic_stride_scaffold
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_FOR_DYNAMIC_STRIDE_COMPUTE_SHADER}
    -DTARGET=directx
    -DMODE=dump-backend
    "-DMUST_CONTAIN=for \\(int i = 0; i < 8; i\\+=stride\\)"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_dump_backend_opengl_for_dynamic_stride_scaffold
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_FOR_DYNAMIC_STRIDE_COMPUTE_SHADER}
    -DTARGET=opengl
    -DMODE=dump-backend
    "-DMUST_CONTAIN=for \\(int i = 0; i < 8; i\\+=stride\\)"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_dump_backend_directx_for_constant_stride_scaffold
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_FOR_CONSTANT_STRIDE_COMPUTE_SHADER}
    -DTARGET=directx
    -DMODE=dump-backend
    "-DMUST_CONTAIN=static const int TILE_SIZE = 2;"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_dump_backend_opengl_for_constant_stride_scaffold
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_FOR_CONSTANT_STRIDE_COMPUTE_SHADER}
    -DTARGET=opengl
    -DMODE=dump-backend
    "-DMUST_CONTAIN=const int TILE_SIZE = 2;"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_dump_backend_directx_for_folded_update_scaffold
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_FOR_FOLDED_UPDATE_COMPUTE_SHADER}
    -DTARGET=directx
    -DMODE=dump-backend
    "-DMUST_CONTAIN=for \\(int i = 0; i < 8; i = i \\+ \\(3\\)\\)"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_dump_backend_opengl_for_folded_update_scaffold
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_FOR_FOLDED_UPDATE_COMPUTE_SHADER}
    -DTARGET=opengl
    -DMODE=dump-backend
    "-DMUST_CONTAIN=for \\(int i = 0; i < 8; i = i \\+ \\(3\\)\\)"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_dump_backend_metal_for_folded_update_scaffold
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_FOR_FOLDED_UPDATE_COMPUTE_SHADER}
    -DTARGET=metal
    -DMODE=dump-backend
    "-DMUST_CONTAIN=for \\(int i = 0; i < 8; i = i \\+ \\(3\\)\\)"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_dump_backend_directx_texture_sampler_lod_scaffold
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_VULKAN_TEXTURE_SAMPLER_LOD_SHADER}
    -DTARGET=directx
    -DMODE=dump-backend
    "-DMUST_CONTAIN=SampleLevel\\(comparisonSampler"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_dump_backend_opengl_texture_sampler_lod_scaffold
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_VULKAN_TEXTURE_SAMPLER_LOD_SHADER}
    -DTARGET=opengl
    -DMODE=dump-backend
    "-DMUST_CONTAIN=textureLod\\(sampler2D\\(shadowMap, comparisonSampler\\)"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_dump_backend_metal_texture_sampler_lod_scaffold
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_VULKAN_TEXTURE_SAMPLER_LOD_SHADER}
    -DTARGET=metal
    -DMODE=dump-backend
    "-DMUST_CONTAIN=shadowMap\\.sample\\(comparisonSampler, float2\\(0\\.25, 0\\.75\\), level\\(1\\.0\\)\\)"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_dump_backend_vulkan_texture_sampler_lod_scaffold
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_VULKAN_TEXTURE_SAMPLER_LOD_SHADER}
    -DTARGET=vulkan
    -DMODE=dump-backend
    "-DMUST_CONTAIN=texture_sample_lod\\(shadowMap, comparisonSampler"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_dump_backend_directx_texture_sampler_array_descriptor_scaffold
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_VULKAN_TEXTURE_SAMPLER_ARRAY_DESCRIPTOR_SHADER}
    -DTARGET=directx
    -DMODE=dump-backend
    "-DMUST_CONTAIN=Texture2D<float4> shadowMaps\\[MAP_COUNT\\]"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_dump_backend_opengl_texture_sampler_array_descriptor_scaffold
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_VULKAN_TEXTURE_SAMPLER_ARRAY_DESCRIPTOR_SHADER}
    -DTARGET=opengl
    -DMODE=dump-backend
    "-DMUST_CONTAIN=uniform texture2D shadowMaps\\[MAP_COUNT\\]"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_dump_backend_directx_texture_sampler_array_lod_scaffold
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_VULKAN_TEXTURE_SAMPLER_ARRAY_LOD_SHADER}
    -DTARGET=directx
    -DMODE=dump-backend
    "-DMUST_CONTAIN=shadowMaps\\[0\\]\\.SampleLevel\\(comparisonSamplers\\[0\\]"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_dump_backend_opengl_texture_sampler_array_lod_scaffold
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_VULKAN_TEXTURE_SAMPLER_ARRAY_LOD_SHADER}
    -DTARGET=opengl
    -DMODE=dump-backend
    "-DMUST_CONTAIN=sampler2D\\(shadowMaps\\[0\\], comparisonSamplers\\[0\\]\\)"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_dump_backend_directx_texture_sampler_3d_lod_scaffold
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_VULKAN_TEXTURE_SAMPLER_3D_LOD_SHADER}
    -DTARGET=directx
    -DMODE=dump-backend
    "-DMUST_CONTAIN=Texture3D<float4> volumeMap"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_dump_backend_opengl_texture_sampler_3d_lod_scaffold
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_VULKAN_TEXTURE_SAMPLER_3D_LOD_SHADER}
    -DTARGET=opengl
    -DMODE=dump-backend
    "-DMUST_CONTAIN=sampler3D\\(volumeMap, volumeSampler\\)"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_dump_backend_directx_texture_sampler_3d_array_lod_scaffold
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_VULKAN_TEXTURE_SAMPLER_3D_ARRAY_LOD_SHADER}
    -DTARGET=directx
    -DMODE=dump-backend
    "-DMUST_CONTAIN=volumeMaps\\[1\\]\\.SampleLevel\\(volumeSamplers\\[0\\]"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_dump_backend_opengl_texture_sampler_3d_array_lod_scaffold
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_VULKAN_TEXTURE_SAMPLER_3D_ARRAY_LOD_SHADER}
    -DTARGET=opengl
    -DMODE=dump-backend
    "-DMUST_CONTAIN=sampler3D\\(volumeMaps\\[1\\], volumeSamplers\\[0\\]\\)"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_dump_backend_directx_texture_sampler_cube_lod_scaffold
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_VULKAN_TEXTURE_SAMPLER_CUBE_LOD_SHADER}
    -DTARGET=directx
    -DMODE=dump-backend
    "-DMUST_CONTAIN=TextureCube<float4> skyMap"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_dump_backend_opengl_texture_sampler_cube_lod_scaffold
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_VULKAN_TEXTURE_SAMPLER_CUBE_LOD_SHADER}
    -DTARGET=opengl
    -DMODE=dump-backend
    "-DMUST_CONTAIN=samplerCube\\(skyMap, skySampler\\)"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_dump_backend_directx_texture_sampler_cube_array_lod_scaffold
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_VULKAN_TEXTURE_SAMPLER_CUBE_ARRAY_LOD_SHADER}
    -DTARGET=directx
    -DMODE=dump-backend
    "-DMUST_CONTAIN=skyMaps\\[1\\]\\.SampleLevel\\(skySamplers\\[0\\]"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_dump_backend_opengl_texture_sampler_cube_array_lod_scaffold
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_VULKAN_TEXTURE_SAMPLER_CUBE_ARRAY_LOD_SHADER}
    -DTARGET=opengl
    -DMODE=dump-backend
    "-DMUST_CONTAIN=samplerCube\\(skyMaps\\[1\\], skySamplers\\[0\\]\\)"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_dump_backend_directx_integer_texture_sampler_lod_scaffold
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_VULKAN_INTEGER_TEXTURE_SAMPLER_LOD_SHADER}
    -DTARGET=directx
    -DMODE=dump-backend
    "-DMUST_CONTAIN=Texture2D<int4> labelMap"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_dump_backend_opengl_integer_texture_sampler_lod_scaffold
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_VULKAN_INTEGER_TEXTURE_SAMPLER_LOD_SHADER}
    -DTARGET=opengl
    -DMODE=dump-backend
    "-DMUST_CONTAIN=itexture2D labelMap"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_dump_backend_directx_texture_array_dimensions_scaffold
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_TEXTURE_ARRAY_DIMENSION_SHADER}
    -DTARGET=directx
    -DMODE=dump-backend
    "-DMUST_CONTAIN=Texture2DArray<float4> atlas"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_dump_backend_opengl_texture_array_dimensions_scaffold
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_TEXTURE_ARRAY_DIMENSION_SHADER}
    -DTARGET=opengl
    -DMODE=dump-backend
    "-DMUST_CONTAIN=samplerCubeArray\\(environmentMaps, linearSampler\\)"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_dump_backend_directx_integer_texture_array_sampler_lod_scaffold
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_VULKAN_INTEGER_TEXTURE_ARRAY_SAMPLER_LOD_SHADER}
    -DTARGET=directx
    -DMODE=dump-backend
    "-DMUST_CONTAIN=TextureCubeArray<uint4> maskCubes"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_dump_backend_opengl_integer_texture_array_sampler_lod_scaffold
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_VULKAN_INTEGER_TEXTURE_ARRAY_SAMPLER_LOD_SHADER}
    -DTARGET=opengl
    -DMODE=dump-backend
    "-DMUST_CONTAIN=usamplerCubeArray\\(maskCubes, maskSampler\\)"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_dump_backend_directx_texture_compare_shadow_scaffold
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_TEXTURE_COMPARE_SHADOW_SHADER}
    -DTARGET=directx
    -DMODE=dump-backend
    "-DMUST_CONTAIN=SampleCmpLevelZero\\(shadowSampler"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_dump_backend_opengl_texture_compare_shadow_scaffold
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_TEXTURE_COMPARE_SHADOW_SHADER}
    -DTARGET=opengl
    -DMODE=dump-backend
    "-DMUST_CONTAIN=sampler2DShadow\\(shadowMap, shadowSampler\\)"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_dump_backend_directx_texture_compare_descriptor_array_scaffold
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_TEXTURE_COMPARE_DESCRIPTOR_ARRAY_SHADER}
    -DTARGET=directx
    -DMODE=dump-backend
    "-DMUST_CONTAIN=shadowMaps\\[1\\]\\.SampleCmpLevelZero\\(shadowSamplers\\[0\\]"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_dump_backend_directx_runtime_texture_resource_array_sampler_scaffold
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CMAKE_CURRENT_SOURCE_DIR}/tests/directx/fixtures/DirectXRuntimeTextureSamplerResourceArrayShader.cgl
    -DTARGET=directx
    -DMODE=dump-backend
    "-DMUST_CONTAIN=Texture2D<float4> colorMaps\\[\\] : register\\(t1, space0\\);.*SamplerState linearSamplers\\[\\] : register\\(s2, space0\\);.*colorMaps\\[0\\]\\.SampleLevel\\(linearSamplers\\[0\\]"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_dump_backend_directx_uniform_buffer_descriptor_array_scaffold
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CMAKE_CURRENT_SOURCE_DIR}/tests/directx/fixtures/DirectXUniformBufferDescriptorArrayShader.cgl
    -DTARGET=directx
    -DMODE=dump-backend
    "-DMUST_CONTAIN=ConstantBuffer<Light> lights\\[LIGHT_COUNT\\] : register\\(b0, space0\\);.*lights\\[NonUniformResourceIndex\\(slot\\)\\]\\.color.*lights\\[slot\\]\\.intensity"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_dump_backend_opengl_texture_compare_descriptor_array_scaffold
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_TEXTURE_COMPARE_DESCRIPTOR_ARRAY_SHADER}
    -DTARGET=opengl
    -DMODE=dump-backend
    "-DMUST_CONTAIN=sampler2DShadow\\(shadowMaps\\[1\\], shadowSamplers\\[0\\]\\)"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_dump_backend_directx_texture_array_compare_descriptor_array_scaffold
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_TEXTURE_ARRAY_COMPARE_DESCRIPTOR_ARRAY_SHADER}
    -DTARGET=directx
    -DMODE=dump-backend
    "-DMUST_CONTAIN=shadowAtlases\\[1\\]\\.SampleCmpLevelZero\\(shadowSamplers\\[0\\]"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_dump_backend_opengl_texture_array_compare_descriptor_array_scaffold
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_TEXTURE_ARRAY_COMPARE_DESCRIPTOR_ARRAY_SHADER}
    -DTARGET=opengl
    -DMODE=dump-backend
    "-DMUST_CONTAIN=sampler2DArrayShadow\\(shadowAtlases\\[1\\], shadowSamplers\\[0\\]\\)"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_dump_backend_directx_texture_cube_compare_descriptor_array_scaffold
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_TEXTURE_CUBE_COMPARE_DESCRIPTOR_ARRAY_SHADER}
    -DTARGET=directx
    -DMODE=dump-backend
    "-DMUST_CONTAIN=shadowCubes\\[1\\]\\.SampleCmpLevelZero\\(shadowSamplers\\[0\\]"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_dump_backend_opengl_texture_cube_compare_descriptor_array_scaffold
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_TEXTURE_CUBE_COMPARE_DESCRIPTOR_ARRAY_SHADER}
    -DTARGET=opengl
    -DMODE=dump-backend
    "-DMUST_CONTAIN=samplerCubeArrayShadow\\(shadowCubeArrays\\[1\\], shadowSamplers\\[0\\]\\)"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_dump_backend_directx_texture_array_shadow_compare_scaffold
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_TEXTURE_ARRAY_SHADOW_COMPARE_SHADER}
    -DTARGET=directx
    -DMODE=dump-backend
    "-DMUST_CONTAIN=TextureCubeArray<float> shadowCubes"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_dump_backend_opengl_texture_array_shadow_compare_scaffold
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_TEXTURE_ARRAY_SHADOW_COMPARE_SHADER}
    -DTARGET=opengl
    -DMODE=dump-backend
    "-DMUST_CONTAIN=samplerCubeArrayShadow\\(shadowCubes, shadowSampler\\)"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_dump_backend_directx_texture_compare_lod_scaffold
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_TEXTURE_COMPARE_LOD_SHADER}
    -DTARGET=directx
    -DMODE=dump-backend
    "-DMUST_CONTAIN=SampleCmpLevel\\(shadowSampler"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_dump_backend_opengl_texture_compare_2d_lod_scaffold
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_TEXTURE_COMPARE_2D_LOD_SHADER}
    -DTARGET=opengl
    -DMODE=dump-backend
    "-DMUST_CONTAIN=textureLod\\(shadowMap, vec3\\(vec2\\(0\\.5, 0\\.5\\), 0\\.25\\), 2\\.0\\)"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_dump_backend_metal_texture_compare_lod_scaffold
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_TEXTURE_COMPARE_LOD_SHADER}
    -DTARGET=metal
    -DMODE=dump-backend
    "-DMUST_CONTAIN=shadowMap\\.sample_compare\\(shadowSampler, float2\\(0\\.5, 0\\.5\\), 0\\.25, level\\(2\\.0\\)\\).*shadowCubes\\.sample_compare\\(shadowSampler"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_dump_backend_vulkan_texture_compare_lod_scaffold
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_TEXTURE_COMPARE_LOD_SHADER}
    -DTARGET=vulkan
    -DMODE=dump-backend
    "-DMUST_CONTAIN=texture_compare_lod\\(shadowMap, shadowSampler.*texture_compare_lod\\(shadowCubes, shadowSampler"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_dump_backend_directx_texture_array_shadow_compare_lod_scaffold
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_TEXTURE_ARRAY_SHADOW_COMPARE_LOD_UNSUPPORTED_SHADER}
    -DTARGET=directx
    -DMODE=dump-backend
    "-DMUST_CONTAIN=shadowAtlas\\.SampleCmpLevel\\(shadowSampler"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_dump_backend_opengl_texture_array_shadow_compare_lod_scaffold
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_TEXTURE_ARRAY_SHADOW_COMPARE_LOD_UNSUPPORTED_SHADER}
    -DTARGET=opengl
    -DMODE=dump-backend
    "-DMUST_CONTAIN=textureLod\\(shadowAtlas, vec4\\(vec3\\(0\\.25, 0\\.5, 1\\.0\\), 0\\.33\\), 2\\.0\\).*textureLod\\(shadowCube, vec4\\(vec3\\(0\\.0, 1\\.0, 0\\.0\\), 0\\.75\\), 3\\.0\\)"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_dump_backend_opengl_texture_2d_array_shadow_compare_lod_scaffold
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_TEXTURE_2D_ARRAY_SHADOW_COMPARE_LOD_UNSUPPORTED_SHADER}
    -DTARGET=opengl
    -DMODE=dump-backend
    "-DMUST_CONTAIN=textureLod\\(shadowAtlas, vec4\\(vec3\\(0\\.25, 0\\.5, 1\\.0\\), 0\\.33\\), 2\\.0\\)"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_dump_backend_opengl_texture_cube_shadow_compare_lod_scaffold
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_TEXTURE_CUBE_SHADOW_COMPARE_LOD_UNSUPPORTED_SHADER}
    -DTARGET=opengl
    -DMODE=dump-backend
    "-DMUST_CONTAIN=textureLod\\(shadowCube, vec4\\(vec3\\(0\\.0, 1\\.0, 0\\.0\\), 0\\.75\\), 3\\.0\\)"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_dump_backend_opengl_texture_cube_array_shadow_compare_lod_scaffold
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_TEXTURE_CUBE_ARRAY_SHADOW_COMPARE_LOD_UNSUPPORTED_SHADER}
    -DTARGET=opengl
    -DMODE=dump-backend
    "-DMUST_CONTAIN=textureLod\\(shadowCubes, vec4\\(0\\.0, 1\\.0, 0\\.0, 2\\.0\\), 0\\.75, 3\\.0\\)"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_dump_backend_directx_texture_2d_shadow_compare_lod_manual_scaffold
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_TEXTURE_2D_SHADOW_COMPARE_LOD_MANUAL_SHADER}
    -DTARGET=directx
    -DMODE=dump-backend
    "-DMUST_CONTAIN=cglCompareDepth\\(shadowMap\\.SampleLevel\\(rawShadowSampler"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_dump_backend_directx_texture_2d_array_shadow_compare_lod_manual_scaffold
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_TEXTURE_2D_ARRAY_SHADOW_COMPARE_LOD_MANUAL_SHADER}
    -DTARGET=directx
    -DMODE=dump-backend
    "-DMUST_CONTAIN=cglCompareDepth\\(shadowAtlas\\.SampleLevel\\(rawShadowSampler"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_dump_backend_directx_texture_2d_shadow_compare_lod_manual_offset_scaffold
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_TEXTURE_2D_SHADOW_COMPARE_LOD_MANUAL_OFFSET_SHADER}
    -DTARGET=directx
    -DMODE=dump-backend
    "-DMUST_CONTAIN=cglCompareDepth\\(shadowMap\\.SampleLevel\\(rawShadowSampler, float2\\(0\\.5, 0\\.5\\), 2\\.0, int2\\(1, -1\\)\\)"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_dump_backend_directx_texture_2d_array_shadow_compare_lod_manual_offset_scaffold
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_TEXTURE_2D_ARRAY_SHADOW_COMPARE_LOD_MANUAL_OFFSET_SHADER}
    -DTARGET=directx
    -DMODE=dump-backend
    "-DMUST_CONTAIN=cglCompareDepth\\(shadowAtlas\\.SampleLevel\\(rawShadowSampler, float3\\(0\\.25, 0\\.5, 1\\.0\\), 2\\.0, int2\\(-1, 1\\)\\)"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_dump_backend_directx_texture_cube_shadow_compare_lod_manual_scaffold
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_TEXTURE_CUBE_SHADOW_COMPARE_LOD_MANUAL_SHADER}
    -DTARGET=directx
    -DMODE=dump-backend
    "-DMUST_CONTAIN=cglCompareDepth\\(shadowCube\\.SampleLevel\\(rawShadowSampler"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_dump_backend_directx_texture_cube_array_shadow_compare_lod_manual_scaffold
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_TEXTURE_CUBE_ARRAY_SHADOW_COMPARE_LOD_MANUAL_SHADER}
    -DTARGET=directx
    -DMODE=dump-backend
    "-DMUST_CONTAIN=cglCompareDepth\\(shadowCubes\\.SampleLevel\\(rawShadowSampler"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_dump_backend_metal_texture_2d_shadow_compare_lod_manual_scaffold
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_TEXTURE_2D_SHADOW_COMPARE_LOD_MANUAL_SHADER}
    -DTARGET=metal
    -DMODE=dump-backend
    "-DMUST_CONTAIN=cglCompareDepth\\(shadowMap\\.sample\\(rawShadowSampler, float2\\(0\\.5, 0\\.5\\), level\\(2\\.0\\)\\), 0\\.25, CGL_COMPARE_LESS\\)"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_dump_backend_metal_texture_2d_shadow_compare_lod_manual_offset_scaffold
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_TEXTURE_2D_SHADOW_COMPARE_LOD_MANUAL_OFFSET_SHADER}
    -DTARGET=metal
    -DMODE=dump-backend
    "-DMUST_CONTAIN=cglCompareDepth\\(shadowMap\\.sample\\(rawShadowSampler, float2\\(0\\.5, 0\\.5\\), level\\(2\\.0\\), int2\\(1, -1\\)\\), 0\\.25, CGL_COMPARE_LESS\\)"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_dump_backend_metal_texture_2d_array_shadow_compare_lod_manual_offset_scaffold
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_TEXTURE_2D_ARRAY_SHADOW_COMPARE_LOD_MANUAL_OFFSET_SHADER}
    -DTARGET=metal
    -DMODE=dump-backend
    "-DMUST_CONTAIN=cglCompareDepth\\(shadowAtlas\\.sample\\(rawShadowSampler, float2\\(0\\.25, 0\\.5\\), uint\\(1\\.0\\), level\\(2\\.0\\), int2\\(-1, 1\\)\\), 0\\.33, CGL_COMPARE_LESS_EQUAL\\)"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_dump_backend_vulkan_texture_2d_shadow_compare_lod_manual_scaffold
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_TEXTURE_2D_SHADOW_COMPARE_LOD_MANUAL_SHADER}
    -DTARGET=vulkan
    -DMODE=dump-backend
    "-DMUST_CONTAIN=texture_compare_lod_manual\\(shadowMap, rawShadowSampler, vec2\\(0\\.5, 0\\.5\\), 0\\.25, 2\\.0, less\\)"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_dump_backend_opengl_texture_2d_shadow_compare_lod_manual_scaffold
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_TEXTURE_2D_SHADOW_COMPARE_LOD_MANUAL_SHADER}
    -DTARGET=opengl
    -DMODE=dump-backend
    "-DMUST_CONTAIN=cglCompareDepth\\(textureLod\\(sampler2D\\(shadowMap, rawShadowSampler\\)"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_dump_backend_opengl_texture_2d_array_shadow_compare_lod_manual_scaffold
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_TEXTURE_2D_ARRAY_SHADOW_COMPARE_LOD_MANUAL_SHADER}
    -DTARGET=opengl
    -DMODE=dump-backend
    "-DMUST_CONTAIN=cglCompareDepth\\(textureLod\\(sampler2DArray\\(shadowAtlas, rawShadowSampler\\)"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_dump_backend_opengl_texture_2d_shadow_compare_lod_manual_offset_scaffold
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_TEXTURE_2D_SHADOW_COMPARE_LOD_MANUAL_OFFSET_SHADER}
    -DTARGET=opengl
    -DMODE=dump-backend
    "-DMUST_CONTAIN=cglCompareDepth\\(textureLodOffset\\(sampler2D\\(shadowMap, rawShadowSampler\\), vec2\\(0\\.5, 0\\.5\\), 2\\.0, ivec2\\(1, -1\\)\\)"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_dump_backend_opengl_texture_2d_array_shadow_compare_lod_manual_offset_scaffold
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_TEXTURE_2D_ARRAY_SHADOW_COMPARE_LOD_MANUAL_OFFSET_SHADER}
    -DTARGET=opengl
    -DMODE=dump-backend
    "-DMUST_CONTAIN=cglCompareDepth\\(textureLodOffset\\(sampler2DArray\\(shadowAtlas, rawShadowSampler\\), vec3\\(0\\.25, 0\\.5, 1\\.0\\), 2\\.0, ivec2\\(-1, 1\\)\\)"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_dump_backend_opengl_texture_cube_shadow_compare_lod_manual_scaffold
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_TEXTURE_CUBE_SHADOW_COMPARE_LOD_MANUAL_SHADER}
    -DTARGET=opengl
    -DMODE=dump-backend
    "-DMUST_CONTAIN=cglCompareDepth\\(textureLod\\(samplerCube\\(shadowCube, rawShadowSampler\\)"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_dump_backend_opengl_texture_cube_array_shadow_compare_lod_manual_scaffold
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_TEXTURE_CUBE_ARRAY_SHADOW_COMPARE_LOD_MANUAL_SHADER}
    -DTARGET=opengl
    -DMODE=dump-backend
    "-DMUST_CONTAIN=cglCompareDepth\\(textureLod\\(samplerCubeArray\\(shadowCubes, rawShadowSampler\\)"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_dump_backend_directx_texture_compare_descriptor_array_lod_scaffold
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_TEXTURE_COMPARE_DESCRIPTOR_ARRAY_LOD_SHADER}
    -DTARGET=directx
    -DMODE=dump-backend
    "-DMUST_CONTAIN=shadowMaps\\[1\\]\\.SampleCmpLevel\\(shadowSamplers\\[0\\]"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_dump_backend_opengl_texture_compare_descriptor_array_lod_scaffold
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_TEXTURE_COMPARE_DESCRIPTOR_ARRAY_LOD_SHADER}
    -DTARGET=opengl
    -DMODE=dump-backend
    "-DMUST_CONTAIN=textureLod\\(sampler2DShadow\\(shadowMaps\\[1\\], shadowSamplers\\[0\\]\\)"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_dump_backend_directx_texture_array_compare_descriptor_array_lod_scaffold
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_TEXTURE_ARRAY_COMPARE_DESCRIPTOR_ARRAY_LOD_SHADER}
    -DTARGET=directx
    -DMODE=dump-backend
    "-DMUST_CONTAIN=shadowAtlases\\[1\\]\\.SampleCmpLevel\\(shadowSamplers\\[0\\]"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_dump_backend_opengl_texture_array_compare_descriptor_array_lod_scaffold
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_TEXTURE_ARRAY_COMPARE_DESCRIPTOR_ARRAY_LOD_SHADER}
    -DTARGET=opengl
    -DMODE=dump-backend
    "-DMUST_CONTAIN=textureLod\\(sampler2DArrayShadow\\(shadowAtlases\\[1\\], shadowSamplers\\[0\\]\\), vec4\\(vec3\\(0\\.25, 0\\.5, 1\\.0\\), 0\\.33\\), 2\\.0\\)"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_dump_backend_directx_texture_cube_compare_descriptor_array_lod_scaffold
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_TEXTURE_CUBE_COMPARE_DESCRIPTOR_ARRAY_LOD_SHADER}
    -DTARGET=directx
    -DMODE=dump-backend
    "-DMUST_CONTAIN=shadowCubeArrays\\[1\\]\\.SampleCmpLevel\\(shadowSamplers\\[0\\]"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_dump_backend_opengl_texture_cube_compare_descriptor_array_lod_scaffold
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_TEXTURE_CUBE_COMPARE_DESCRIPTOR_ARRAY_LOD_SHADER}
    -DTARGET=opengl
    -DMODE=dump-backend
    "-DMUST_CONTAIN=textureLod\\(samplerCubeArrayShadow\\(shadowCubeArrays\\[1\\], shadowSamplers\\[0\\]\\), vec4\\(0\\.0, 1\\.0, 0\\.0, 2\\.0\\), 0\\.5, 4\\.0\\)"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_dump_backend_directx_mixed_texture_compare_descriptor_array_scaffold
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_MIXED_TEXTURE_COMPARE_DESCRIPTOR_ARRAY_SHADER}
    -DTARGET=directx
    -DMODE=dump-backend
    "-DMUST_CONTAIN=SamplerComparisonState shadowSamplers\\[2\\]"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_dump_backend_opengl_mixed_texture_compare_descriptor_array_scaffold
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_MIXED_TEXTURE_COMPARE_DESCRIPTOR_ARRAY_SHADER}
    -DTARGET=opengl
    -DMODE=dump-backend
    "-DMUST_CONTAIN=textureLod\\(sampler2DShadow\\(shadowMaps\\[0\\], shadowSamplers\\[1\\]\\)"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_dump_backend_directx_mixed_sampler_usage_scaffold
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_DIRECTX_MIXED_SAMPLER_USAGE_UNSUPPORTED_SHADER}
    -DTARGET=directx
    -DMODE=dump-backend
    "-DMUST_CONTAIN=SamplerComparisonState sharedSampler_cglComparison : register\\(s5, space0\\);"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_dump_backend_opengl_mixed_sampler_usage_scaffold
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_DIRECTX_MIXED_SAMPLER_USAGE_UNSUPPORTED_SHADER}
    -DTARGET=opengl
    -DMODE=dump-backend
    "-DMUST_CONTAIN=texture\\(sampler2DShadow\\(shadowMap, sharedSampler\\)"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_dump_backend_directx_mixed_sampler_array_usage_scaffold
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_DIRECTX_MIXED_SAMPLER_ARRAY_USAGE_UNSUPPORTED_SHADER}
    -DTARGET=directx
    -DMODE=dump-backend
    "-DMUST_CONTAIN=SamplerComparisonState sharedSamplers_cglComparison\\[SAMPLER_COUNT\\] : register\\(s5, space0\\);"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_dump_backend_directx_function_parameter_array_unsupported_scaffold
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_DIRECTX_FUNCTION_PARAMETER_ARRAY_UNSUPPORTED_SHADER}
    -DTARGET=directx
    -DSTAGE=backend
    -DMODE=dump-stage-failure
    -DEXPECTED_DIAGNOSTIC=directx.unsupported-function-parameter-array-call-feature
    "-DEXPECTED_STDERR_FRAGMENT=TargetLegalizationResult: state=rejected"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_dump_backend_opengl_function_parameter_struct_array_scaffold
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CMAKE_CURRENT_SOURCE_DIR}/tests/opengl/fixtures/OpenGLFunctionParameterStructArrayUnsupportedShader.cgl
    -DTARGET=opengl
    -DMODE=dump-backend
    "-DMUST_CONTAIN=float firstWeight\\(Payload payloads\\[COUNT\\]\\)"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_dump_backend_directx_local_function_parameter_array_scaffold
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_DIRECTX_LOCAL_FUNCTION_PARAMETER_ARRAY_SHADER}
    -DTARGET=directx
    -DMODE=dump-backend
    "-DMUST_CONTAIN=sumWeights\\(localWeights\\)"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_dump_backend_directx_matrix_function_parameter_array_scaffold
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_DIRECTX_MATRIX_FUNCTION_PARAMETER_ARRAY_SHADER}
    -DTARGET=directx
    -DMODE=dump-backend
    "-DMUST_CONTAIN=float2x2 localTransforms\\[COUNT\\]"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_dump_backend_directx_folded_nested_function_parameter_array_scaffold
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_DIRECTX_FOLDED_NESTED_FUNCTION_PARAMETER_ARRAY_SHADER}
    -DTARGET=directx
    -DMODE=dump-backend
    "-DMUST_CONTAIN=float weights\\[ROWS\\]\\[COLS\\]"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_dump_backend_directx_nested_local_function_parameter_array_scaffold
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_DIRECTX_NESTED_LOCAL_FUNCTION_PARAMETER_ARRAY_SHADER}
    -DTARGET=directx
    -DMODE=dump-backend
    "-DMUST_CONTAIN=float localGrid\\[ROWS\\]\\[COLS\\]"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_dump_backend_directx_nested_function_parameter_array_write_scaffold
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_DIRECTX_NESTED_FUNCTION_PARAMETER_ARRAY_WRITE_UNSUPPORTED_SHADER}
    -DTARGET=directx
    -DMODE=dump-backend
    "-DMUST_CONTAIN=grid\\[1\\]\\[2\\] = 1\\.0;"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_dump_backend_directx_dynamic_nested_function_parameter_array_read_scaffold
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_DIRECTX_DYNAMIC_NESTED_FUNCTION_PARAMETER_ARRAY_READ_UNSUPPORTED_SHADER}
    -DTARGET=directx
    -DMODE=dump-backend
    "-DMUST_CONTAIN=return grid\\[row\\]\\[col\\];"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_dump_backend_opengl_nested_local_function_parameter_array_scaffold
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_OPENGL_NESTED_LOCAL_FUNCTION_PARAMETER_ARRAY_SHADER}
    -DTARGET=opengl
    -DMODE=dump-backend
    "-DMUST_CONTAIN=float grid\\[ROWS\\]\\[COLS\\]"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_dump_backend_opengl_dynamic_nested_local_function_parameter_array_scaffold
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_OPENGL_DYNAMIC_NESTED_LOCAL_FUNCTION_PARAMETER_ARRAY_UNSUPPORTED_SHADER}
    -DTARGET=opengl
    -DMODE=dump-backend
    "-DMUST_CONTAIN=return grid\\[row\\]\\[2\\];"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_dump_backend_opengl_function_parameter_array_write_scaffold
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_OPENGL_FUNCTION_PARAMETER_ARRAY_WRITE_UNSUPPORTED_SHADER}
    -DTARGET=opengl
    -DSTAGE=backend
    -DMODE=dump-stage-failure
    -DEXPECTED_DIAGNOSTIC=opengl.unsupported-function-parameter-array-write
    "-DEXPECTED_STDERR_FRAGMENT=TargetLegalizationResult: state=rejected"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_dump_backend_opengl_nested_function_parameter_array_write_scaffold
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_OPENGL_NESTED_FUNCTION_PARAMETER_ARRAY_WRITE_UNSUPPORTED_SHADER}
    -DTARGET=opengl
    -DMODE=dump-backend
    "-DMUST_CONTAIN=float rewriteGrid\\(float grid\\[ROWS\\]\\[COLS\\]\\).*grid\\[1\\]\\[2\\] = grid\\[0\\]\\[0\\] \\+ 1\\.0;"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_dump_backend_metal_function_parameter_array_write_scaffold
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CMAKE_CURRENT_SOURCE_DIR}/tests/metal/fixtures/MetalFunctionParameterArrayWriteUnsupportedShader.cgl
    -DTARGET=metal
    -DMODE=dump-backend
    "-DMUST_CONTAIN=float rewriteWeight\\(array<float, COUNT> weights\\).*weights\\[0\\] = 1\\.0;"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_dump_backend_metal_nested_function_parameter_array_write_scaffold
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CMAKE_CURRENT_SOURCE_DIR}/tests/metal/fixtures/MetalNestedFunctionParameterArrayWriteUnsupportedShader.cgl
    -DTARGET=metal
    -DMODE=dump-backend
    "-DMUST_CONTAIN=float rewriteGrid\\(array<array<float, COLS>, ROWS> grid\\).*grid\\[1\\]\\[2\\] = grid\\[0\\]\\[0\\] \\+ 1\\.0;"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_dump_backend_opengl_mixed_sampler_array_usage_scaffold
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_DIRECTX_MIXED_SAMPLER_ARRAY_USAGE_UNSUPPORTED_SHADER}
    -DTARGET=opengl
    -DMODE=dump-backend
    "-DMUST_CONTAIN=texture\\(sampler2DShadow\\(shadowMap, sharedSamplers\\[1\\]\\)"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)

add_test(NAME cglc_dump_backend_directx_storage_image_2d
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_DIRECTX_STORAGE_IMAGE_2D_SHADER}
    -DTARGET=directx
    -DMODE=dump-backend
    "-DMUST_CONTAIN=RWTexture2D<float4> colorImage : register\\(u0, space0\\).*RWTexture2D<int4> labelImage : register\\(u1, space0\\).*RWTexture2D<uint4> maskImage : register\\(u2, space0\\).*float4 color = colorImage\\.Load\\(pixel\\).*colorImage\\[pixel\\] = color"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_dump_backend_directx_storage_image_2d_array
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_DIRECTX_STORAGE_IMAGE_2D_ARRAY_SHADER}
    -DTARGET=directx
    -DMODE=dump-backend
    "-DMUST_CONTAIN=RWTexture2DArray<float4> colorAtlas : register\\(u3, space0\\).*RWTexture2DArray<int4> labelAtlas : register\\(u4, space0\\).*RWTexture2DArray<uint4> maskAtlas : register\\(u5, space0\\).*float4 color = colorAtlas\\.Load\\(texel\\).*colorAtlas\\[texel\\] = color"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_dump_backend_directx_storage_image_read_write
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_DIRECTX_STORAGE_IMAGE_READ_WRITE_SHADER}
    -DTARGET=directx
    -DMODE=dump-backend
    "-DMUST_CONTAIN=RWTexture2D<float4> colorImage : register\\(u0, space0\\).*RWTexture2D<int4> labelImage : register\\(u1, space0\\).*RWTexture2D<uint4> maskImage : register\\(u2, space0\\).*RWTexture2DArray<float4> colorAtlas : register\\(u3, space0\\).*RWTexture2DArray<int4> labelAtlas : register\\(u4, space0\\).*RWTexture2DArray<uint4> maskAtlas : register\\(u5, space0\\).*float4 color = colorImage\\.Load\\(pixel\\).*colorImage\\[pixel\\] = color.*uint4 atlasMask = maskAtlas\\.Load\\(atlasPixel\\).*maskAtlas\\[atlasPixel\\] = atlasMask"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_dump_backend_directx_storage_image_access_qualifier
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_DIRECTX_STORAGE_IMAGE_ACCESS_QUALIFIER_SHADER}
    -DTARGET=directx
    -DMODE=dump-backend
    "-DMUST_CONTAIN=RWTexture2D<float4> readColor : register\\(u0, space0\\).*RWTexture2D<float4> writeColor : register\\(u1, space0\\).*RWTexture2D<float4> readWriteColor : register\\(u2, space0\\).*RWTexture2DArray<float4> readAtlas : register\\(u3, space0\\).*RWTexture2DArray<float4> writeAtlas : register\\(u4, space0\\).*RWTexture2DArray<float4> readWriteAtlas : register\\(u5, space0\\).*float4 color = readColor\\.Load\\(pixel\\).*writeColor\\[pixel\\] = color.*float4 readWriteAtlasValue = readWriteAtlas\\.Load\\(texel\\).*readWriteAtlas\\[texel\\] = readWriteAtlasValue \\+ atlasColor"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_dump_backend_directx_storage_image_descriptor_array
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_DIRECTX_STORAGE_IMAGE_DESCRIPTOR_ARRAY_SHADER}
    -DTARGET=directx
    -DMODE=dump-backend
    "-DMUST_CONTAIN=RWTexture2D<float4> colorImages\\[COUNT\\] : register\\(u0, space0\\).*RWTexture2D<int4> labelImages\\[N\\] : register\\(u1, space0\\).*RWTexture2DArray<uint4> maskAtlases\\[N\\] : register\\(u2, space0\\).*float4 color = colorImages\\[descriptor\\]\\.Load\\(pixel\\).*maskAtlases\\[descriptor\\]\\[texel\\] = mask"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_dump_backend_directx_storage_image_nonuniform_descriptor_array
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_DIRECTX_STORAGE_IMAGE_NONUNIFORM_DESCRIPTOR_ARRAY_SHADER}
    -DTARGET=directx
    -DMODE=dump-backend
    "-DMUST_CONTAIN=RWTexture2D<float4> colorImages\\[IMAGE_COUNT\\] : register\\(u0, space0\\).*float4 color = colorImages\\[NonUniformResourceIndex\\(slot\\)\\]\\.Load\\(pixel\\).*maskAtlases\\[NonUniformResourceIndex\\(slot\\)\\]\\[texel\\] = mask"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_dump_backend_directx_storage_image_explicit_format_descriptor_array
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_STORAGE_IMAGE_EXPLICIT_FORMAT_DESCRIPTOR_ARRAY_SHADER}
    -DTARGET=directx
    -DMODE=dump-backend
    "-DMUST_CONTAIN=RWTexture2D<float4> colorImages\\[IMAGE_COUNT\\] : register\\(u0, space0\\).*RWTexture2D<int4> labelImages\\[IMAGE_COUNT\\] : register\\(u1, space0\\).*RWTexture2DArray<uint4> outputAtlases\\[ATLAS_COUNT\\] : register\\(u3, space0\\).*float4 color = colorImages\\[NonUniformResourceIndex\\(imageSlot\\)\\]\\.Load\\(pixel\\).*outputAtlases\\[NonUniformResourceIndex\\(atlasSlot\\)\\]\\[atlasPixel\\] = mask"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_dump_backend_directx_storage_image_atomic
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_STORAGE_IMAGE_ATOMIC_SHADER}
    -DTARGET=directx
    -DMODE=dump-backend
    "-DMUST_CONTAIN=RWTexture2D<int> signedCounters : register\\(u0, space0\\).*RWTexture2DArray<uint> unsignedAtlas : register\\(u3, space0\\).*InterlockedAdd\\(signedCounters\\[pixel\\], 1, signedOld\\).*InterlockedMin\\(signedCounters\\[pixel \\+ int2\\(1, 0\\)\\], signedOld, signedMin\\).*InterlockedExchange\\(unsignedCounters\\[pixel \\+ int2\\(0, 1\\)\\], unsignedAtlasOld, crossgl_atomic_exchange_old_value\\).*InterlockedXor\\(unsignedCounters\\[pixel\\], unsignedAtlasOld\\)"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_dump_backend_directx_storage_image_atomic_descriptor_array
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_STORAGE_IMAGE_ATOMIC_DESCRIPTOR_ARRAY_SHADER}
    -DTARGET=directx
    -DMODE=dump-backend
    "-DMUST_CONTAIN=RWTexture2D<int> signedCounters\\[IMAGE_COUNT\\] : register\\(u1, space0\\).*RWTexture2DArray<uint> unsignedAtlases\\[IMAGE_COUNT\\] : register\\(u4, space0\\).*InterlockedAdd\\(signedCounters\\[NonUniformResourceIndex\\(slot\\)\\]\\[pixel\\], 1, signedOld\\).*InterlockedAnd\\(signedAtlases\\[NonUniformResourceIndex\\(slot\\)\\]\\[atlasPixel\\], signedMin, atlasAnd\\).*InterlockedXor\\(unsignedCounters\\[NonUniformResourceIndex\\(slot\\)\\]\\[pixel\\], unsignedAtlasOld\\)"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_dump_backend_opengl_storage_image
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_OPENGL_STORAGE_IMAGE_SHADER}
    -DTARGET=opengl
    -DMODE=dump-backend
    "-DMUST_CONTAIN=layout\\(binding = 0, rgba32f\\) uniform image2D colorImage;.*layout\\(binding = 5, rgba32ui\\) uniform uimage2DArray maskAtlas;.*vec4 color = imageLoad\\(colorImage, pixel\\);.*imageStore\\(colorAtlas, atlasPixel, atlasColor\\);"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_dump_backend_opengl_storage_image_access_qualifier
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_OPENGL_STORAGE_IMAGE_ACCESS_QUALIFIER_SHADER}
    -DTARGET=opengl
    -DMODE=dump-backend
    "-DMUST_CONTAIN=layout\\(binding = 0, rgba32f\\) readonly uniform image2D readColor;.*layout\\(binding = 1, rgba32f\\) writeonly uniform image2D writeColor;.*layout\\(binding = 2, rgba32f\\) uniform image2D readWriteColor;.*layout\\(binding = 3, rgba32f\\) readonly uniform image2DArray readAtlas;.*layout\\(binding = 4, rgba32f\\) writeonly uniform image2DArray writeAtlas;.*layout\\(binding = 5, rgba32f\\) uniform image2DArray readWriteAtlas;.*vec4 color = imageLoad\\(readColor, pixel\\);.*imageStore\\(writeAtlas, texel, atlasColor\\);"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_dump_backend_opengl_storage_image_descriptor_array
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_OPENGL_STORAGE_IMAGE_DESCRIPTOR_ARRAY_SHADER}
    -DTARGET=opengl
    -DMODE=dump-backend
    "-DMUST_CONTAIN=layout\\(binding = 0, rgba32f\\) uniform image2D colorImages\\[COUNT\\];.*layout\\(binding = 5, rgba32ui\\) uniform uimage2DArray maskAtlases\\[2\\];.*vec4 color = imageLoad\\(colorImages\\[slot\\], pixel\\);.*imageStore\\(maskAtlases\\[0\\], atlasPixel, atlasMask\\);"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_dump_backend_opengl_storage_image_nonuniform_descriptor_array
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_OPENGL_STORAGE_IMAGE_NONUNIFORM_DESCRIPTOR_ARRAY_SHADER}
    -DTARGET=opengl
    -DMODE=dump-backend
    "-DMUST_CONTAIN=#extension GL_EXT_nonuniform_qualifier : require.*layout\\(binding = 0, rgba32f\\) uniform image2D colorImages\\[COUNT\\];.*vec4 color = imageLoad\\(colorImages\\[nonuniformEXT\\(slot\\)\\], pixel\\);.*imageStore\\(maskAtlases\\[nonuniformEXT\\(writeSlot\\)\\], atlasPixel, atlasMask\\);"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_dump_backend_opengl_storage_image_explicit_format_descriptor_array
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_STORAGE_IMAGE_EXPLICIT_FORMAT_DESCRIPTOR_ARRAY_SHADER}
    -DTARGET=opengl
    -DMODE=dump-backend
    "-DMUST_CONTAIN=#extension GL_EXT_nonuniform_qualifier : require.*layout\\(binding = 0, r32f\\) readonly uniform image2D colorImages\\[IMAGE_COUNT\\];.*layout\\(binding = 1, r32i\\) readonly uniform iimage2D labelImages\\[IMAGE_COUNT\\];.*layout\\(binding = 3, r32ui\\) writeonly uniform uimage2DArray outputAtlases\\[ATLAS_COUNT\\];.*imageLoad\\(colorImages\\[nonuniformEXT\\(imageSlot\\)\\], pixel\\).*imageStore\\(outputAtlases\\[nonuniformEXT\\(atlasSlot\\)\\], atlasPixel, mask\\);"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_dump_backend_opengl_storage_image_atomic
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_OPENGL_STORAGE_IMAGE_ATOMIC_SHADER}
    -DTARGET=opengl
    -DMODE=dump-backend
    "-DMUST_CONTAIN=layout\\(binding = 0, r32i\\) uniform iimage2D signedCounters;.*layout\\(binding = 1, r32ui\\) uniform uimage2D unsignedCounters;.*layout\\(binding = 2, r32i\\) uniform iimage2DArray signedAtlas;.*int signedMin = imageAtomicMin\\(signedCounters, pixel \\+ ivec2\\(1, 0\\), signedOld\\);.*uint unsignedMax = imageAtomicMax\\(unsignedAtlas, atlasPixel, unsignedMin\\);.*uint unsignedAtlasOld = imageAtomicExchange\\(unsignedAtlas, atlasPixel, unsignedOr\\);.*imageAtomicXor\\(unsignedCounters, pixel, unsignedAtlasOld\\);"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_dump_backend_opengl_storage_image_atomic_descriptor_array
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_STORAGE_IMAGE_ATOMIC_DESCRIPTOR_ARRAY_SHADER}
    -DTARGET=opengl
    -DMODE=dump-backend
    "-DMUST_CONTAIN=#extension GL_EXT_nonuniform_qualifier : require.*layout\\(binding = 1, r32i\\) uniform iimage2D signedCounters\\[IMAGE_COUNT\\];.*layout\\(binding = 4, r32ui\\) uniform uimage2DArray unsignedAtlases\\[IMAGE_COUNT\\];.*imageAtomicMin\\(signedCounters\\[nonuniformEXT\\(slot\\)\\], pixel, signedOld\\).*imageAtomicOr\\(unsignedAtlases\\[nonuniformEXT\\(slot\\)\\], atlasPixel, unsignedMax\\).*imageAtomicXor\\(unsignedCounters\\[nonuniformEXT\\(slot\\)\\], pixel, unsignedAtlasOld\\)"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_dump_backend_metal_storage_image
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_METAL_STORAGE_IMAGE_SHADER}
    -DTARGET=metal
    -DMODE=dump-backend
    "-DMUST_CONTAIN=texture2d<float, access::read_write> colorImage \\[\\[texture\\(0\\)\\]\\].*texture2d_array<uint, access::read_write> maskAtlas \\[\\[texture\\(5\\)\\]\\].*float4 color = colorImage\\.read\\(uint2\\(pixel\\)\\).*colorImage\\.write\\(color, uint2\\(pixel\\)\\)"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_dump_backend_metal_storage_image_access_qualifier
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_METAL_STORAGE_IMAGE_ACCESS_QUALIFIER_SHADER}
    -DTARGET=metal
    -DMODE=dump-backend
    "-DMUST_CONTAIN=texture2d<float, access::read> readColorImage \\[\\[texture\\(0\\)\\]\\].*texture2d<float, access::write> writeColorImage \\[\\[texture\\(1\\)\\]\\].*texture2d<float, access::read_write> readWriteColorImage \\[\\[texture\\(2\\)\\]\\].*texture2d_array<float, access::read> readColorAtlas \\[\\[texture\\(3\\)\\]\\].*texture2d_array<float, access::write> writeColorAtlas \\[\\[texture\\(4\\)\\]\\].*texture2d_array<float, access::read_write> readWriteColorAtlas \\[\\[texture\\(5\\)\\]\\].*float4 color = readColorImage\\.read\\(uint2\\(pixel\\)\\).*writeColorImage\\.write\\(color, uint2\\(pixel\\)\\).*readWriteColorAtlas\\.write\\(readWriteAtlasColor \\+ atlasColor, uint2\\(atlasPixel\\.xy\\), uint\\(atlasPixel\\.z\\)\\)"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_dump_backend_metal_storage_image_access_qualifier_descriptor_array
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_METAL_STORAGE_IMAGE_ACCESS_QUALIFIER_DESCRIPTOR_ARRAY_SHADER}
    -DTARGET=metal
    -DMODE=dump-backend
    "-DMUST_CONTAIN=array<texture2d<float, access::read>, IMAGE_COUNT> readColorImages \\[\\[texture\\(0\\)\\]\\].*array<texture2d<float, access::write>, IMAGE_COUNT> writeColorImages \\[\\[texture\\(2\\)\\]\\].*array<texture2d<float, access::read_write>, IMAGE_COUNT> readWriteColorImages \\[\\[texture\\(4\\)\\]\\].*array<texture2d_array<float, access::read>, ATLAS_COUNT> readColorAtlases \\[\\[texture\\(6\\)\\]\\].*array<texture2d_array<float, access::write>, ATLAS_COUNT> writeColorAtlases \\[\\[texture\\(8\\)\\]\\].*array<texture2d_array<float, access::read_write>, ATLAS_COUNT> readWriteColorAtlases \\[\\[texture\\(10\\)\\]\\].*readColorImages\\[imageDescriptor\\]\\.read\\(uint2\\(pixel\\)\\).*writeColorAtlases\\[atlasDescriptor\\]\\.write\\(atlasColor, uint2\\(atlasPixel\\.xy\\), uint\\(atlasPixel\\.z\\)\\)"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_dump_backend_metal_storage_image_2d_descriptor_array
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_METAL_STORAGE_IMAGE_2D_DESCRIPTOR_ARRAY_SHADER}
    -DTARGET=metal
    -DMODE=dump-backend
    "-DMUST_CONTAIN=array<texture2d<float, access::read_write>, IMAGE_COUNT> colorImages \\[\\[texture\\(0\\)\\]\\].*array<texture2d<int, access::read_write>, IMAGE_COUNT> labelImages \\[\\[texture\\(2\\)\\]\\].*array<texture2d<uint, access::read_write>, IMAGE_COUNT> maskImages \\[\\[texture\\(4\\)\\]\\].*float4 color = colorImages\\[descriptor\\]\\.read\\(uint2\\(pixel\\)\\)"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_dump_backend_metal_storage_image_2d_nonuniform_descriptor_array
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_METAL_STORAGE_IMAGE_2D_NONUNIFORM_DESCRIPTOR_ARRAY_SHADER}
    -DTARGET=metal
    -DMODE=dump-backend
    "-DMUST_CONTAIN=array<texture2d<float, access::read_write>, IMAGE_COUNT> colorImages \\[\\[texture\\(0\\)\\]\\].*array<texture2d<uint, access::read_write>, IMAGE_COUNT> maskImages \\[\\[texture\\(4\\)\\]\\].*float4 color = colorImages\\[descriptor\\]\\.read\\(uint2\\(pixel\\)\\).*maskImages\\[descriptor\\]\\.write\\(mask, uint2\\(pixel\\)\\)"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_dump_backend_metal_storage_image_2d_array_descriptor_array
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_METAL_STORAGE_IMAGE_2D_ARRAY_DESCRIPTOR_ARRAY_SHADER}
    -DTARGET=metal
    -DMODE=dump-backend
    "-DMUST_CONTAIN=array<texture2d_array<float, access::read_write>, ATLAS_COUNT> colorAtlases \\[\\[texture\\(0\\)\\]\\].*array<texture2d_array<uint, access::read_write>, ATLAS_COUNT> maskAtlases \\[\\[texture\\(4\\)\\]\\].*float4 color = colorAtlases\\[descriptor\\]\\.read\\(uint2\\(atlasPixel\\.xy\\), uint\\(atlasPixel\\.z\\)\\)"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_dump_backend_metal_storage_image_2d_array_nonuniform_descriptor_array
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_METAL_STORAGE_IMAGE_2D_ARRAY_NONUNIFORM_DESCRIPTOR_ARRAY_SHADER}
    -DTARGET=metal
    -DMODE=dump-backend
    "-DMUST_CONTAIN=array<texture2d_array<float, access::read_write>, ATLAS_COUNT> colorAtlases \\[\\[texture\\(0\\)\\]\\].*array<texture2d_array<uint, access::read_write>, ATLAS_COUNT> maskAtlases \\[\\[texture\\(4\\)\\]\\].*float4 color = colorAtlases\\[descriptor\\]\\.read\\(uint2\\(atlasPixel\\.xy\\), uint\\(atlasPixel\\.z\\)\\).*maskAtlases\\[descriptor\\]\\.write\\(mask, uint2\\(atlasPixel\\.xy\\), uint\\(atlasPixel\\.z\\)\\)"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_dump_backend_metal_storage_image_explicit_format_descriptor_array
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_STORAGE_IMAGE_EXPLICIT_FORMAT_DESCRIPTOR_ARRAY_SHADER}
    -DTARGET=metal
    -DMODE=dump-backend
    "-DMUST_CONTAIN=array<texture2d<float, access::read>, IMAGE_COUNT> colorImages \\[\\[texture\\(0\\)\\]\\].*array<texture2d<int, access::read>, IMAGE_COUNT> labelImages \\[\\[texture\\(2\\)\\]\\].*array<texture2d_array<uint, access::read>, ATLAS_COUNT> maskAtlases \\[\\[texture\\(4\\)\\]\\].*array<texture2d_array<uint, access::write>, ATLAS_COUNT> outputAtlases \\[\\[texture\\(6\\)\\]\\].*float4 color = colorImages\\[imageSlot\\]\\.read\\(uint2\\(pixel\\)\\).*outputAtlases\\[atlasSlot\\]\\.write\\(mask, uint2\\(atlasPixel\\.xy\\), uint\\(atlasPixel\\.z\\)\\)"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_dump_backend_metal_storage_image_atomic
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_STORAGE_IMAGE_ATOMIC_SHADER}
    -DTARGET=metal
    -DMODE=dump-backend
    "-DMUST_CONTAIN=texture2d<int, access::read_write> signedCounters \\[\\[texture\\(0\\)\\]\\].*texture2d_array<uint, access::read_write> unsignedAtlas \\[\\[texture\\(3\\)\\]\\].*int signedOld = signedCounters\\.atomic_fetch_add\\(uint2\\(pixel\\), int4\\(1\\)\\)\\.x;.*int signedMin = signedCounters\\.atomic_fetch_min\\(uint2\\(pixel \\+ int2\\(1, 0\\)\\), int4\\(signedOld\\)\\)\\.x;.*uint unsignedMax = unsignedAtlas\\.atomic_fetch_max\\(uint2\\(atlasPixel\\.xy\\), uint\\(atlasPixel\\.z\\), uint4\\(unsignedMin\\)\\)\\.x;.*unsignedCounters\\.atomic_exchange\\(uint2\\(pixel \\+ int2\\(0, 1\\)\\), uint4\\(unsignedAtlasOld\\)\\)\\.x;"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_dump_backend_metal_storage_image_atomic_descriptor_array
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_METAL_STORAGE_IMAGE_ATOMIC_DESCRIPTOR_ARRAY_SHADER}
    -DTARGET=metal
    -DMODE=dump-backend
    "-DMUST_CONTAIN=array<texture2d<int, access::read_write>, IMAGE_COUNT> signedCounters \\[\\[texture\\(1\\)\\]\\].*array<texture2d_array<uint, access::read_write>, IMAGE_COUNT> unsignedAtlases \\[\\[texture\\(7\\)\\]\\].*int signedMin = signedCounters\\[slot\\]\\.atomic_fetch_min\\(uint2\\(pixel\\), int4\\(signedOld\\)\\)\\.x;.*uint atlasOr = unsignedAtlases\\[slot\\]\\.atomic_fetch_or\\(uint2\\(atlasPixel\\.xy\\), uint\\(atlasPixel\\.z\\), uint4\\(unsignedMax\\)\\)\\.x;.*unsignedCounters\\[slot\\]\\.atomic_fetch_xor\\(uint2\\(pixel\\), uint4\\(unsignedAtlasOld\\)\\)\\.x;"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_dump_backend_vulkan_storage_image_read_write
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_VULKAN_STORAGE_IMAGE_READ_WRITE_SHADER}
    -DTARGET=vulkan
    -DMODE=dump-backend
    "-DMUST_CONTAIN=VK_DESCRIPTOR_TYPE_STORAGE_IMAGE.*OpTypeImage<float, 2D, sampled=2, format=Rgba32f>.*OpTypeImage<uint, 2DArray, sampled=2, format=Rgba32ui>.*imageStore\\(maskAtlas, atlasPixel, atlasMask\\)"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
set(CROSSGL_VULKAN_STORAGE_IMAGE_ACCESS_QUALIFIER_BACKEND_REGEX [=[vulkan.descriptor @readOnlyImage set 0 binding 0 descriptor_type "VK_DESCRIPTOR_TYPE_STORAGE_IMAGE".*storage_image_access "read_only" spirv_access_decoration "NonWritable".*vulkan.descriptor @writeOnlyImage set 0 binding 1 descriptor_type "VK_DESCRIPTOR_TYPE_STORAGE_IMAGE".*storage_image_access "write_only" spirv_access_decoration "NonReadable".*vulkan.descriptor @readWriteImage set 0 binding 2 descriptor_type "VK_DESCRIPTOR_TYPE_STORAGE_IMAGE" storage_class "UniformConstant" binding_class "storageImage" spirv_type "OpTypeImage<float, 2D, sampled=2, format=Rgba32f>".*spirv.Decorate @readOnlyImage NonWritable.*spirv.Decorate @writeOnlyImage NonReadable.*spirv.Decorate @readOnlyImages NonWritable.*spirv.Decorate @writeOnlyImages NonReadable.*crossgl.resource @readOnlyImage.*access = "read".*crossgl.resource @writeOnlyImage.*access = "write".*crossgl.resource @readWriteImage.*access = "read_write"]=])
add_test(NAME cglc_dump_backend_vulkan_storage_image_access_qualifier
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_VULKAN_STORAGE_IMAGE_ACCESS_QUALIFIER_SHADER}
    -DTARGET=vulkan
    -DMODE=dump-backend
    "-DMUST_CONTAIN=${CROSSGL_VULKAN_STORAGE_IMAGE_ACCESS_QUALIFIER_BACKEND_REGEX}"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
set(CROSSGL_VULKAN_STORAGE_IMAGE_EXPLICIT_FORMAT_BACKEND_REGEX [=[vulkan.descriptor @readColor set 0 binding 0 descriptor_type "VK_DESCRIPTOR_TYPE_STORAGE_IMAGE".*spirv_type "OpTypeImage<float, 2D, sampled=2, format=R32f>".*vulkan.descriptor @readLabel set 0 binding 1 descriptor_type "VK_DESCRIPTOR_TYPE_STORAGE_IMAGE".*spirv_type "OpTypeImage<int, 2D, sampled=2, format=R32i>".*vulkan.descriptor @readMask set 0 binding 2 descriptor_type "VK_DESCRIPTOR_TYPE_STORAGE_IMAGE".*spirv_type "OpTypeImage<uint, 2D, sampled=2, format=R32ui>".*spirv.GlobalVariable @readColor : !spirv.ptr<!spirv.image<f32, 2D, storage, R32f>, UniformConstant>.*spirv.GlobalVariable @readLabel : !spirv.ptr<!spirv.image<i32, 2D, storage, R32i>, UniformConstant>.*spirv.GlobalVariable @readMask : !spirv.ptr<!spirv.image<u32, 2D, storage, R32ui>, UniformConstant>.*crossgl.resource @readColor.*format = "r32f".*crossgl.resource @readLabel.*format = "r32i".*crossgl.resource @readMask.*format = "r32ui"]=])
add_test(NAME cglc_dump_backend_vulkan_storage_image_explicit_format
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_STORAGE_IMAGE_EXPLICIT_FORMAT_SHADER}
    -DTARGET=vulkan
    -DMODE=dump-backend
    "-DMUST_CONTAIN=${CROSSGL_VULKAN_STORAGE_IMAGE_EXPLICIT_FORMAT_BACKEND_REGEX}"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
set(CROSSGL_VULKAN_STORAGE_IMAGE_EXPLICIT_FORMAT_DESCRIPTOR_ARRAY_BACKEND_REGEX [=[vulkan.descriptor @colorImages set 0 binding 0 descriptor_type "VK_DESCRIPTOR_TYPE_STORAGE_IMAGE".*spirv_type "OpTypeArray<OpTypeImage<float, 2D, sampled=2, format=R32f>, IMAGE_COUNT>".*storage_image_access "read_only".*vulkan.descriptor @labelImages set 0 binding 1 descriptor_type "VK_DESCRIPTOR_TYPE_STORAGE_IMAGE".*spirv_type "OpTypeArray<OpTypeImage<int, 2D, sampled=2, format=R32i>, IMAGE_COUNT>".*vulkan.descriptor @maskAtlases set 0 binding 2 descriptor_type "VK_DESCRIPTOR_TYPE_STORAGE_IMAGE".*spirv_type "OpTypeArray<OpTypeImage<uint, 2DArray, sampled=2, format=R32ui>, ATLAS_COUNT>".*vulkan.descriptor @outputAtlases set 0 binding 3 descriptor_type "VK_DESCRIPTOR_TYPE_STORAGE_IMAGE".*storage_image_access "write_only".*spirv_access_decoration "NonReadable".*spirv.GlobalVariable @colorImages : !spirv.ptr<!spirv.array<!spirv.image<f32, 2D, storage, R32f>, IMAGE_COUNT>, UniformConstant>.*spirv.GlobalVariable @outputAtlases : !spirv.ptr<!spirv.array<!spirv.image<u32, 2DArray, storage, R32ui>, ATLAS_COUNT>, UniformConstant>.*crossgl.resource @colorImages.*format = "r32f".*crossgl.resource @labelImages.*format = "r32i".*crossgl.resource @maskAtlases.*format = "r32ui".*crossgl.resource @outputAtlases.*format = "r32ui"]=])
add_test(NAME cglc_dump_backend_vulkan_storage_image_explicit_format_descriptor_array
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_STORAGE_IMAGE_EXPLICIT_FORMAT_DESCRIPTOR_ARRAY_SHADER}
    -DTARGET=vulkan
    -DMODE=dump-backend
    "-DMUST_CONTAIN=${CROSSGL_VULKAN_STORAGE_IMAGE_EXPLICIT_FORMAT_DESCRIPTOR_ARRAY_BACKEND_REGEX}"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
set(CROSSGL_VULKAN_STORAGE_IMAGE_ATOMIC_BACKEND_REGEX [=[vulkan.descriptor @signedCounters set 0 binding 0 descriptor_type "VK_DESCRIPTOR_TYPE_STORAGE_IMAGE".*spirv_type "OpTypeImage<int, 2D, sampled=2, format=R32i>".*vulkan.descriptor @unsignedCounters set 0 binding 1 descriptor_type "VK_DESCRIPTOR_TYPE_STORAGE_IMAGE".*spirv_type "OpTypeImage<uint, 2D, sampled=2, format=R32ui>".*vulkan.descriptor @signedAtlas set 0 binding 2 descriptor_type "VK_DESCRIPTOR_TYPE_STORAGE_IMAGE".*spirv_type "OpTypeImage<int, 2DArray, sampled=2, format=R32i>".*crossgl.decl %signedMin : !crossgl.i32 = "imageAtomicMin\(signedCounters, pixel, signedOld\)".*crossgl.decl %unsignedMax : !crossgl.u32 = "imageAtomicMax\(unsignedAtlas, atlasPixel, unsignedMin\)".*crossgl.expr "imageAtomicXor\(unsignedCounters, pixel, unsignedAtlasOld\)"]=])
add_test(NAME cglc_dump_backend_vulkan_storage_image_atomic
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_VULKAN_STORAGE_IMAGE_ATOMIC_SHADER}
    -DTARGET=vulkan
    -DMODE=dump-backend
    "-DMUST_CONTAIN=${CROSSGL_VULKAN_STORAGE_IMAGE_ATOMIC_BACKEND_REGEX}"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
set(CROSSGL_VULKAN_STORAGE_IMAGE_ATOMIC_DESCRIPTOR_ARRAY_BACKEND_REGEX [=[vulkan.descriptor @signedCounters set 0 binding 1 descriptor_type "VK_DESCRIPTOR_TYPE_STORAGE_IMAGE".*spirv_type "OpTypeArray<OpTypeImage<int, 2D, sampled=2, format=R32i>, IMAGE_COUNT>".*descriptor_array_size "IMAGE_COUNT".*vulkan.descriptor @unsignedAtlases set 0 binding 4 descriptor_type "VK_DESCRIPTOR_TYPE_STORAGE_IMAGE".*spirv_type "OpTypeArray<OpTypeImage<uint, 2DArray, sampled=2, format=R32ui>, IMAGE_COUNT>".*crossgl.decl %signedMin : !crossgl.i32 = "imageAtomicMin\(signedCounters\[nonuniform\(slot\)\], pixel, signedOld\)".*crossgl.decl %atlasAnd : !crossgl.i32 = "imageAtomicAnd\(signedAtlases\[nonuniform\(slot\)\], atlasPixel, signedMin\)".*crossgl.expr "imageAtomicXor\(unsignedCounters\[nonuniform\(slot\)\], pixel, unsignedAtlasOld\)"]=])
add_test(NAME cglc_dump_backend_vulkan_storage_image_atomic_descriptor_array
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_STORAGE_IMAGE_ATOMIC_DESCRIPTOR_ARRAY_SHADER}
    -DTARGET=vulkan
    -DMODE=dump-backend
    "-DMUST_CONTAIN=${CROSSGL_VULKAN_STORAGE_IMAGE_ATOMIC_DESCRIPTOR_ARRAY_BACKEND_REGEX}"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_dump_backend_vulkan_storage_image_descriptor_array
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_VULKAN_STORAGE_IMAGE_DESCRIPTOR_ARRAY_SHADER}
    -DTARGET=vulkan
    -DMODE=dump-backend
    "-DMUST_CONTAIN=VK_DESCRIPTOR_TYPE_STORAGE_IMAGE.*OpTypeArray<OpTypeImage<uint, 2DArray, sampled=2, format=Rgba32ui>, MASK_COUNT>.*descriptor_array_size \"MASK_COUNT\".*imageStore\\(maskAtlases\\[1\\], atlasPixel, mask\\)"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_dump_backend_vulkan_storage_image_nonuniform_descriptor_array
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_VULKAN_STORAGE_IMAGE_NONUNIFORM_DESCRIPTOR_ARRAY_SHADER}
    -DTARGET=vulkan
    -DMODE=dump-backend
    "-DMUST_CONTAIN=VK_DESCRIPTOR_TYPE_STORAGE_IMAGE.*OpTypeArray<OpTypeImage<uint, 2DArray, sampled=2, format=Rgba32ui>, IMAGE_COUNT>.*descriptor_array_size \"IMAGE_COUNT\".*imageLoad\\(colorImages\\[nonuniform\\(slot\\)\\], pixel\\).*imageStore\\(maskAtlases\\[nonuniform\\(slot\\)\\], atlasPixel, mask\\)"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
