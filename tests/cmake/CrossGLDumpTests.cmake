add_test(NAME cglc_dump_hir_simple
  COMMAND cglc dump-ir ${CROSSGL_SIMPLE_SHADER} --stage hir)
add_test(NAME cglc_dump_hir_resources
  COMMAND cglc dump-ir ${CROSSGL_RESOURCE_SHADER} --stage hir)
add_test(NAME cglc_dump_pseudo_mlir_simple
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_SIMPLE_SHADER}
    -DSTAGE=pseudo-mlir
    -DMODE=dump-stage
    "-DMUST_CONTAIN=no CrossGL MLIR dialect is registered, and this is not verifier-ready real MLIR"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_dump_legacy_mlir_alias_emits_pseudo_mlir
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_SIMPLE_SHADER}
    -DSTAGE=mlir
    -DMODE=dump-stage
    "-DMUST_CONTAIN=crossgl.real_mlir = \"false\""
    "-DEXPECTED_STDERR_FRAGMENT=--stage mlir is a compatibility alias for --stage pseudo-mlir"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
set(CROSSGL_SPECIALIZATION_CONSTANTS_COMPUTE_SHADER ${CMAKE_CURRENT_SOURCE_DIR}/tests/fixtures/SpecializationConstantsComputeShader.cgl)
add_test(NAME cglc_dump_crossgl_specialization_constants
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_SPECIALIZATION_CONSTANTS_COMPUTE_SHADER}
    -DSTAGE=crossgl
    -DMODE=dump-stage
    "-DMUST_CONTAIN=crossgl.constant @TILE_SIZE : !crossgl.i32 = \"16\" attributes \\{folded = \"16\", specialization_id = 7\\}"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_dump_pseudo_mlir_specialization_constants
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_SPECIALIZATION_CONSTANTS_COMPUTE_SHADER}
    -DSTAGE=pseudo-mlir
    -DMODE=dump-stage
    "-DMUST_CONTAIN=// crossgl.constant @TILE_SIZE : !crossgl.i32 = \"16\" attributes \\{folded = \"16\", specialization_id = 7\\}"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
set(CROSSGL_WHILE_CONTROL_FLOW_HIR_SHADER ${CMAKE_CURRENT_SOURCE_DIR}/tests/frontend/fixtures/WhileControlFlowHIRShader.cgl)
set(CROSSGL_FOR_INCREMENT_DECREMENT_HIR_SHADER ${CMAKE_CURRENT_SOURCE_DIR}/tests/frontend/fixtures/ForIncrementDecrementHIRShader.cgl)
set(CROSSGL_WORKGROUP_SHARED_MEMORY_HIR_SHADER ${CMAKE_CURRENT_SOURCE_DIR}/tests/frontend/fixtures/WorkgroupSharedMemoryHIRShader.cgl)
set(CROSSGL_WORKGROUP_BARRIER_HIR_SHADER ${CMAKE_CURRENT_SOURCE_DIR}/tests/frontend/fixtures/WorkgroupBarrierHIRShader.cgl)
set(CROSSGL_GRAPHICS_PROVENANCE_HIR_SHADER ${CMAKE_CURRENT_SOURCE_DIR}/tests/frontend/fixtures/GraphicsProvenanceHIRShader.cgl)
set(CROSSGL_HIR_CONTROL_TRANSFER_SHADER ${CMAKE_CURRENT_SOURCE_DIR}/tests/frontend/fixtures/HIRControlTransferShader.cgl)
set(CROSSGL_COMPUTE_INVOCATION_BUILTIN_HIR_SHADER ${CMAKE_CURRENT_SOURCE_DIR}/tests/frontend/fixtures/ComputeInvocationBuiltinHIRShader.cgl)
set(CROSSGL_COMPUTE_INVOCATION_BUILTIN_CAST_HIR_SHADER ${CMAKE_CURRENT_SOURCE_DIR}/tests/frontend/fixtures/ComputeInvocationBuiltinCastHIRShader.cgl)
set(CROSSGL_ATOMIC_ADD_HIR_SHADER ${CMAKE_CURRENT_SOURCE_DIR}/tests/frontend/fixtures/AtomicAddHIRShader.cgl)
set(CROSSGL_ATOMIC_ADD_RETURN_HIR_SHADER ${CMAKE_CURRENT_SOURCE_DIR}/tests/frontend/fixtures/AtomicAddReturnHIRShader.cgl)
set(CROSSGL_ATOMIC_MINMAX_HIR_SHADER ${CMAKE_CURRENT_SOURCE_DIR}/tests/frontend/fixtures/AtomicMinMaxHIRShader.cgl)
set(CROSSGL_ATOMIC_EXCHANGE_HIR_SHADER ${CMAKE_CURRENT_SOURCE_DIR}/tests/frontend/fixtures/AtomicExchangeHIRShader.cgl)
set(CROSSGL_ATOMIC_BITWISE_HIR_SHADER ${CMAKE_CURRENT_SOURCE_DIR}/tests/frontend/fixtures/AtomicBitwiseHIRShader.cgl)
add_test(NAME cglc_dump_hir_compute_invocation_builtin_types
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_COMPUTE_INVOCATION_BUILTIN_HIR_SHADER}
    -DSTAGE=hir
    -DMODE=dump-stage
    "-DMUST_CONTAIN=decl uint globalX = gl_GlobalInvocationID\\.x : uint[^\n\r]*[\n\r]+      decl uint localY = gl_LocalInvocationID\\.y : uint[^\n\r]*[\n\r]+      decl uint groupZ = gl_WorkGroupID\\.z : uint[^\n\r]*[\n\r]+      assign values\\[globalX\\] : uint = globalX \\+ localY \\+ groupZ : uint"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_dump_hir_source_map_compute_invocation_builtin_identifier_provenance
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_COMPUTE_INVOCATION_BUILTIN_HIR_SHADER}
    -DSTAGE=hir-source-map
    -DMODE=dump-stage
    "-DSOURCE_MAP_FILTER_ARGS=--source-map-expression-kind|identifier"
    "-DEXPECTED_JSON_PATHS=hirSourceLocations.expressions.0.location.file|hirSourceLocations.expressions.2.location.endOffset"
    "-DEXPECTED_JSON_ARRAY_LENGTHS=hirSourceLocations.expressions=8|hirSourceLocations.types=0|hirSourceLocations.statements=0|categoryCounts.expressionKinds=1"
    "-DEXPECTED_JSON_FIELDS=schemaVersion=7|filters.activeCount=1|filters.expressionKind=identifier|pagination.activeCount=0|categoryCounts.expressionTotalCount=8|categoryCounts.recordTotalCount=8|categoryCounts.expressionKinds.0.name=identifier|categoryCounts.expressionKinds.0.count=8|records.enabled=false|records.totalCount=8|hirSourceLocations.expressionCount=8|hirSourceLocations.expressionWithLocationCount=8|hirSourceLocations.expressions.0.index=1|hirSourceLocations.expressions.0.stage=compute|hirSourceLocations.expressions.0.function=main|hirSourceLocations.expressions.0.statementKind=decl|hirSourceLocations.expressions.0.kind=identifier|hirSourceLocations.expressions.0.value=gl_GlobalInvocationID|hirSourceLocations.expressions.0.type=uvec3|hirSourceLocations.expressions.0.location.line=7|hirSourceLocations.expressions.0.location.column=28|hirSourceLocations.expressions.0.location.length=21|hirSourceLocations.expressions.1.value=gl_LocalInvocationID|hirSourceLocations.expressions.1.type=uvec3|hirSourceLocations.expressions.1.location.line=8|hirSourceLocations.expressions.1.location.column=27|hirSourceLocations.expressions.1.location.length=20|hirSourceLocations.expressions.2.value=gl_WorkGroupID|hirSourceLocations.expressions.2.type=uvec3|hirSourceLocations.expressions.2.location.line=9|hirSourceLocations.expressions.2.location.column=27|hirSourceLocations.expressions.2.location.length=14|hirSourceLocations.expressions.3.value=values|hirSourceLocations.expressions.3.type=uint*|hirSourceLocations.expressions.4.value=globalX|hirSourceLocations.expressions.4.type=uint"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_dump_hir_graphics_provenance_stage_shapes
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_GRAPHICS_PROVENANCE_HIR_SHADER}
    -DSTAGE=hir
    -DMODE=dump-stage
    "-DMUST_CONTAIN=stage vertex entry main[^\n\r]*[\n\r]+    fn main\\(VertexInput input\\) -> VertexOutput[^\n\r]*[\n\r]+      decl VertexOutput output[^\n\r]*[\n\r]+      assign output\\.position : vec4 = vec4\\(input\\.position, 1\\.0\\) : vec4[^\n\r]*[\n\r]+      assign output\\.uv : vec2 = input\\.texCoord : vec2[^\n\r]*[\n\r]+      assign output\\.tint : vec4 = input\\.color : vec4[^\n\r]*[\n\r]+      return output : VertexOutput[^\n\r]*[\n\r]+  stage fragment entry main[^\n\r]*[\n\r]+    fn main\\(FragmentInput input\\) -> FragmentOutput[^\n\r]*[\n\r]+      decl FragmentOutput output[^\n\r]*[\n\r]+      assign output\\.color : vec4 = vec4\\(input\\.uv\\.x, input\\.uv\\.y, input\\.tint\\.z, 1\\.0\\) : vec4"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_dump_hir_source_map_graphics_field_type_provenance
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_GRAPHICS_PROVENANCE_HIR_SHADER}
    -DSTAGE=hir-source-map
    -DMODE=dump-stage
    "-DSOURCE_MAP_FILTER_ARGS=--source-map-owner-kind|field-type"
    "-DEXPECTED_JSON_PATHS=hirSourceLocations.types.0.location.file|hirSourceLocations.types.8.location.endOffset"
    "-DEXPECTED_JSON_ARRAY_LENGTHS=hirSourceLocations.expressions=0|hirSourceLocations.types=9|hirSourceLocations.statements=0|categoryCounts.typeOwnerKinds=1"
    "-DEXPECTED_JSON_FIELDS=schemaVersion=7|filters.activeCount=1|filters.ownerKind=field-type|pagination.activeCount=0|categoryCounts.expressionTotalCount=0|categoryCounts.typeTotalCount=9|categoryCounts.statementTotalCount=0|categoryCounts.recordTotalCount=9|categoryCounts.typeOwnerKinds.0.name=field-type|categoryCounts.typeOwnerKinds.0.count=9|records.enabled=false|records.totalCount=9|hirSourceLocations.typeCount=9|hirSourceLocations.typeWithLocationCount=9|hirSourceLocations.types.0.ownerName=VertexInput.position|hirSourceLocations.types.0.type=vec3|hirSourceLocations.types.0.location.line=3|hirSourceLocations.types.0.location.column=9|hirSourceLocations.types.1.ownerName=VertexInput.texCoord|hirSourceLocations.types.1.type=vec2|hirSourceLocations.types.2.ownerName=VertexInput.color|hirSourceLocations.types.2.type=vec4|hirSourceLocations.types.3.ownerName=VertexOutput.position|hirSourceLocations.types.3.type=vec4|hirSourceLocations.types.4.ownerName=VertexOutput.uv|hirSourceLocations.types.4.type=vec2|hirSourceLocations.types.5.ownerName=VertexOutput.tint|hirSourceLocations.types.5.type=vec4|hirSourceLocations.types.6.ownerName=FragmentInput.uv|hirSourceLocations.types.6.type=vec2|hirSourceLocations.types.7.ownerName=FragmentInput.tint|hirSourceLocations.types.7.type=vec4|hirSourceLocations.types.8.ownerName=FragmentOutput.color|hirSourceLocations.types.8.type=vec4|hirSourceLocations.types.8.location.line=20"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_dump_hir_source_map_graphics_vertex_member_provenance
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_GRAPHICS_PROVENANCE_HIR_SHADER}
    -DSTAGE=hir-source-map
    -DMODE=dump-stage
    "-DSOURCE_MAP_FILTER_ARGS=--source-map-stage|vertex|--source-map-expression-kind|member"
    "-DEXPECTED_JSON_PATHS=hirSourceLocations.expressions.0.location.file|hirSourceLocations.expressions.5.location.endOffset"
    "-DEXPECTED_JSON_ARRAY_LENGTHS=hirSourceLocations.expressions=6|hirSourceLocations.types=0|hirSourceLocations.statements=0|categoryCounts.expressionKinds=1|categoryCounts.typeOwnerKinds=0"
    "-DEXPECTED_JSON_FIELDS=schemaVersion=7|filters.activeCount=2|filters.stage=vertex|filters.expressionKind=member|pagination.activeCount=0|categoryCounts.expressionTotalCount=6|categoryCounts.typeTotalCount=0|categoryCounts.statementTotalCount=0|categoryCounts.recordTotalCount=6|categoryCounts.expressionKinds.0.name=member|categoryCounts.expressionKinds.0.count=6|records.enabled=false|records.totalCount=6|hirSourceLocations.expressionCount=6|hirSourceLocations.expressionWithLocationCount=6|hirSourceLocations.typeCount=0|hirSourceLocations.typeWithLocationCount=0|hirSourceLocations.expressions.0.stage=vertex|hirSourceLocations.expressions.0.entryPoint=main|hirSourceLocations.expressions.0.function=main|hirSourceLocations.expressions.0.statementKind=assign|hirSourceLocations.expressions.0.kind=member|hirSourceLocations.expressions.0.value=position|hirSourceLocations.expressions.0.type=vec4|hirSourceLocations.expressions.0.location.line=26|hirSourceLocations.expressions.0.location.column=20|hirSourceLocations.expressions.1.value=position|hirSourceLocations.expressions.1.type=vec3|hirSourceLocations.expressions.1.location.line=26|hirSourceLocations.expressions.1.location.column=42|hirSourceLocations.expressions.2.value=uv|hirSourceLocations.expressions.2.type=vec2|hirSourceLocations.expressions.2.location.line=27|hirSourceLocations.expressions.3.value=texCoord|hirSourceLocations.expressions.3.type=vec2|hirSourceLocations.expressions.3.location.line=27|hirSourceLocations.expressions.4.value=tint|hirSourceLocations.expressions.4.type=vec4|hirSourceLocations.expressions.4.location.line=28|hirSourceLocations.expressions.5.value=color|hirSourceLocations.expressions.5.type=vec4|hirSourceLocations.expressions.5.location.line=28"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_dump_hir_source_map_graphics_fragment_member_provenance
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_GRAPHICS_PROVENANCE_HIR_SHADER}
    -DSTAGE=hir-source-map
    -DMODE=dump-stage
    "-DSOURCE_MAP_FILTER_ARGS=--source-map-stage|fragment|--source-map-expression-kind|member"
    "-DEXPECTED_JSON_PATHS=hirSourceLocations.expressions.0.location.file|hirSourceLocations.expressions.6.location.endOffset"
    "-DEXPECTED_JSON_ARRAY_LENGTHS=hirSourceLocations.expressions=7|hirSourceLocations.types=0|hirSourceLocations.statements=0|categoryCounts.expressionKinds=1|categoryCounts.typeOwnerKinds=0"
    "-DEXPECTED_JSON_FIELDS=schemaVersion=7|filters.activeCount=2|filters.stage=fragment|filters.expressionKind=member|pagination.activeCount=0|categoryCounts.expressionTotalCount=7|categoryCounts.typeTotalCount=0|categoryCounts.statementTotalCount=0|categoryCounts.recordTotalCount=7|categoryCounts.expressionKinds.0.name=member|categoryCounts.expressionKinds.0.count=7|records.enabled=false|records.totalCount=7|hirSourceLocations.expressionCount=7|hirSourceLocations.expressionWithLocationCount=7|hirSourceLocations.typeCount=0|hirSourceLocations.typeWithLocationCount=0|hirSourceLocations.expressions.0.stage=fragment|hirSourceLocations.expressions.0.entryPoint=main|hirSourceLocations.expressions.0.function=main|hirSourceLocations.expressions.0.statementKind=assign|hirSourceLocations.expressions.0.kind=member|hirSourceLocations.expressions.0.value=color|hirSourceLocations.expressions.0.type=vec4|hirSourceLocations.expressions.0.location.line=36|hirSourceLocations.expressions.0.location.column=20|hirSourceLocations.expressions.1.value=x|hirSourceLocations.expressions.1.type=float|hirSourceLocations.expressions.1.location.line=36|hirSourceLocations.expressions.2.value=uv|hirSourceLocations.expressions.2.type=vec2|hirSourceLocations.expressions.2.location.line=36|hirSourceLocations.expressions.3.value=y|hirSourceLocations.expressions.3.type=float|hirSourceLocations.expressions.4.value=uv|hirSourceLocations.expressions.4.type=vec2|hirSourceLocations.expressions.5.value=z|hirSourceLocations.expressions.5.type=float|hirSourceLocations.expressions.6.value=tint|hirSourceLocations.expressions.6.type=vec4"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
set(CROSSGL_VULKAN_CROSSTL_STORAGE_BUFFER_OVERLOAD_HIR_REGEX [=[struct Particle.*resource buffer float\* scalars set 0 binding 0.*resource buffer vec4\* vectors set 0 binding 1.*resource buffer Particle\* particles set 0 binding 2.*fn crosstl_select_scalar\(int index\) -> float.*return scalars\[index\] : float.*fn crosstl_select_vector\(int index\) -> vec4.*return vectors\[index\] : vec4.*fn crosstl_select_particle\(int index\) -> vec4.*return particles\[index\]\.position \+ particles\[index\]\.velocity : vec4.*decl float scalar = crosstl_select_scalar\(0\) : float.*decl vec4 vectorValue = crosstl_select_vector\(0\) : vec4.*decl vec4 particleValue = crosstl_select_particle\(0\) : vec4.*assign vectors\[1\] : vec4 = vec4\(scalar, scalar, scalar, 1\.0\) \+ vectorValue \+ particleValue : vec4]=])
add_test(NAME cglc_dump_hir_vulkan_crosstl_storage_buffer_overload_selection
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_VULKAN_CROSSTL_STORAGE_BUFFER_OVERLOAD_SELECTION_SHADER}
    -DSTAGE=hir
    -DMODE=dump-stage
    "-DMUST_CONTAIN=${CROSSGL_VULKAN_CROSSTL_STORAGE_BUFFER_OVERLOAD_HIR_REGEX}"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
set(CROSSGL_OPENGL_CROSSTL_RESERVED_IDENTIFIERS_HIR_REGEX [=[struct CrossTLVertexInput.*vec2 sample.*float smooth.*struct CrossTLFragmentTarget.*vec4 sample.*stage vertex entry main.*fn lift\(vec2 sample, float smooth\) -> vec2.*decl vec2 centroid = sample \+ vec2\(smooth, smooth\) : vec2.*fn main\(CrossTLVertexInput input\) -> CrossTLVertexOutput.*decl CrossTLVertexOutput output.*decl vec2 sample = lift\(input\.sample, input\.smooth\) : vec2.*assign output\.sample : vec2 = sample : vec2.*stage fragment entry main.*fn shade\(vec2 sample, float smooth\) -> vec4.*decl float centroid = sample\.x \+ smooth : float.*fn main\(CrossTLFragmentInput input\) -> CrossTLFragmentTarget.*decl CrossTLFragmentTarget output.*decl vec4 sample = shade\(input\.sample, input\.smooth\) : vec4.*assign output\.sample : vec4 = sample : vec4]=])
add_test(NAME cglc_dump_hir_opengl_crosstl_reserved_identifiers_preserved
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_OPENGL_CROSSTL_RESERVED_IDENTIFIERS_SHADER}
    -DSTAGE=hir
    -DMODE=dump-stage
    "-DMUST_CONTAIN=${CROSSGL_OPENGL_CROSSTL_RESERVED_IDENTIFIERS_HIR_REGEX}"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
set(CROSSGL_METAL_CROSSTL_VERTEX_RETURN_STRUCT_HIR_REGEX [=[struct CrossTLVertexOutput.*vec2 uv.*vec4 position.*vec4 color.*float fog.*struct CrossTLFragmentTarget.*vec4 color.*stage vertex entry main.*fn main\(CrossTLVertexInput input\) -> CrossTLVertexOutput.*decl CrossTLVertexOutput output.*assign output\.uv : vec2 = input\.texCoord : vec2.*assign output\.position : vec4 = vec4\(input\.position, 1\.0\) : vec4.*assign output\.color : vec4 = input\.color : vec4.*assign output\.fog : float = input\.position\.z : float.*return output : CrossTLVertexOutput.*stage fragment entry main.*fn main\(CrossTLVertexOutput input\) -> CrossTLFragmentTarget]=])
add_test(NAME cglc_dump_hir_metal_crosstl_vertex_return_struct_preserved
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_METAL_CROSSTL_VERTEX_RETURN_STRUCT_SHADER}
    -DSTAGE=hir
    -DMODE=dump-stage
    "-DMUST_CONTAIN=${CROSSGL_METAL_CROSSTL_VERTEX_RETURN_STRUCT_HIR_REGEX}"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_dump_hir_source_map_control_transfer_statement_provenance
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_HIR_CONTROL_TRANSFER_SHADER}
    -DSTAGE=hir-source-map
    -DMODE=dump-stage
    "-DEXPECTED_JSON_PATHS=hirSourceLocations.statements.10.location.file|hirSourceLocations.statements.15.location.endOffset"
    "-DEXPECTED_JSON_ARRAY_LENGTHS=hirSourceLocations.statements=17|categoryCounts.statementKinds=8"
    "-DEXPECTED_JSON_FIELDS=schemaVersion=7|filters.activeCount=0|pagination.activeCount=0|categoryCounts.statementTotalCount=17|categoryCounts.statementKinds.1.name=break|categoryCounts.statementKinds.1.count=1|categoryCounts.statementKinds.2.name=continue|categoryCounts.statementKinds.2.count=1|categoryCounts.statementKinds.4.name=discard|categoryCounts.statementKinds.4.count=1|hirSourceLocations.statementCount=17|hirSourceLocations.statementWithLocationCount=17|hirSourceLocations.statements.10.stage=fragment|hirSourceLocations.statements.10.function=main|hirSourceLocations.statements.10.statementKind=continue|hirSourceLocations.statements.10.location.line=35|hirSourceLocations.statements.10.location.column=11|hirSourceLocations.statements.10.location.length=8|hirSourceLocations.statements.12.statementKind=break|hirSourceLocations.statements.12.location.line=39|hirSourceLocations.statements.12.location.column=11|hirSourceLocations.statements.12.location.length=5|hirSourceLocations.statements.15.statementKind=discard|hirSourceLocations.statements.15.location.line=45|hirSourceLocations.statements.15.location.column=9|hirSourceLocations.statements.15.location.length=7"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_dump_debug_control_transfer_statement_metadata
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_HIR_CONTROL_TRANSFER_SHADER}
    -DSTAGE=debug
    -DMODE=dump-stage
    "-DEXPECTED_JSON_PATHS=hirSourceLocations.statements.10.location.file|hirSourceLocations.statements.15.location.endOffset"
    "-DEXPECTED_JSON_ARRAY_LENGTHS=hirSourceLocations.statements=17"
    "-DEXPECTED_JSON_FIELDS=schemaVersion=11|hirSourceLocations.statementCount=17|hirSourceLocations.statementWithLocationCount=17|hirSourceLocations.statements.10.stage=fragment|hirSourceLocations.statements.10.function=main|hirSourceLocations.statements.10.statementKind=continue|hirSourceLocations.statements.10.location.line=35|hirSourceLocations.statements.10.location.column=11|hirSourceLocations.statements.10.location.length=8|hirSourceLocations.statements.12.statementKind=break|hirSourceLocations.statements.12.location.line=39|hirSourceLocations.statements.12.location.column=11|hirSourceLocations.statements.12.location.length=5|hirSourceLocations.statements.15.statementKind=discard|hirSourceLocations.statements.15.location.line=45|hirSourceLocations.statements.15.location.column=9|hirSourceLocations.statements.15.location.length=7"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_dump_debug_compute_invocation_builtin_target_capabilities
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_COMPUTE_INVOCATION_BUILTIN_HIR_SHADER}
    -DSTAGE=debug
    -DMODE=dump-stage
    "-DEXPECTED_JSON_FIELDS=schemaVersion=11|hirSourceLocations.expressions.1.value=gl_GlobalInvocationID|hirSourceLocations.expressions.1.type=uvec3|hirSourceLocations.expressions.3.value=gl_LocalInvocationID|hirSourceLocations.expressions.3.type=uvec3|hirSourceLocations.expressions.5.value=gl_WorkGroupID|hirSourceLocations.expressions.5.type=uvec3|hirSourceLocations.expressions.9.kind=binary|hirSourceLocations.expressions.9.type=uint"
    -DTARGET_EXPLANATION_ROOT=targetCapabilities
    -DTARGET_RECORD_ARRAY_FIELD=summaries
    "-DEXPECTED_TARGET_ARRAY_CONTAINS=metal.requiredCapabilities=metal.execution.workgroup-size|metal.requiredCapabilities=metal.operation.storage-buffer-write|vulkan.requiredCapabilities=vulkan.execution.workgroup-size|directx.requiredCapabilities=directx.resource.storage-buffer|opengl.requiredCapabilities=opengl.operation.scalar-arithmetic"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_dump_hir_compute_invocation_builtin_int_casts
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_COMPUTE_INVOCATION_BUILTIN_CAST_HIR_SHADER}
    -DSTAGE=hir
    -DMODE=dump-stage
    "-DMUST_CONTAIN=decl int globalX = int\\(gl_GlobalInvocationID\\.x\\) : int[^\n\r]*[\n\r]+      decl int localX = int\\(gl_LocalInvocationID\\.x\\) : int[^\n\r]*[\n\r]+      decl int localY = int\\(gl_LocalInvocationID\\.y\\) : int[^\n\r]*[\n\r]+      decl int groupX = int\\(gl_WorkGroupID\\.x\\) : int[^\n\r]*[\n\r]+      decl int groupY = int\\(gl_WorkGroupID\\.y\\) : int[^\n\r]*[\n\r]+      assign values\\[globalX\\] : int = localX \\+ localY \\+ groupX \\+ groupY : int"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_dump_hir_workgroup_shared_memory_folded_source_values
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_WORKGROUP_SHARED_MEMORY_HIR_SHADER}
    -DSTAGE=hir
    -DMODE=dump-stage
    "-DMUST_CONTAIN=workgroup_size 8, 4, 1 source GROUP_WIDTH, GROUP_HEIGHT, 1[^\n\r]*[\n\r]+    resource shared float\\[GROUP_WIDTH\\] tile local[^\n\r]*[\n\r]+    fn main\\(\\) -> void[^\n\r]*[\n\r]+      assign tile\\[0\\] : float = 1\\.0 : float[^\n\r]*[\n\r]+      decl float cached = tile\\[0\\] : float[^\n\r]*[\n\r]+      assign tile\\[1\\] : float = cached \\+ 2\\.0 : float"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_dump_hir_source_map_workgroup_shared_resource_type_provenance
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_WORKGROUP_SHARED_MEMORY_HIR_SHADER}
    -DSTAGE=hir-source-map
    -DMODE=dump-stage
    "-DSOURCE_MAP_FILTER_ARGS=--source-map-owner-kind|resource-type"
    "-DEXPECTED_JSON_PATHS=hirSourceLocations.types.0.location.file|hirSourceLocations.types.0.location.endOffset"
    "-DEXPECTED_JSON_ARRAY_LENGTHS=hirSourceLocations.expressions=0|hirSourceLocations.types=1|hirSourceLocations.statements=0|categoryCounts.typeOwnerKinds=1"
    "-DEXPECTED_JSON_FIELDS=schemaVersion=7|filters.activeCount=1|filters.ownerKind=resource-type|pagination.activeCount=0|categoryCounts.expressionTotalCount=0|categoryCounts.typeTotalCount=1|categoryCounts.statementTotalCount=0|categoryCounts.recordTotalCount=1|categoryCounts.typeOwnerKinds.0.name=resource-type|categoryCounts.typeOwnerKinds.0.count=1|records.enabled=false|records.totalCount=1|hirSourceLocations.typeCount=1|hirSourceLocations.typeWithLocationCount=1|hirSourceLocations.types.0.index=6|hirSourceLocations.types.0.stage=compute|hirSourceLocations.types.0.entryPoint=main|hirSourceLocations.types.0.ownerKind=resource-type|hirSourceLocations.types.0.ownerName=tile|hirSourceLocations.types.0.type=float[GROUP_WIDTH]|hirSourceLocations.types.0.location.line=9|hirSourceLocations.types.0.location.column=9|hirSourceLocations.types.0.location.length=12"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_dump_hir_source_map_workgroup_shared_assign_statement_provenance
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_WORKGROUP_SHARED_MEMORY_HIR_SHADER}
    -DSTAGE=hir-source-map
    -DMODE=dump-stage
    "-DSOURCE_MAP_FILTER_ARGS=--source-map-statement-kind|assign"
    "-DEXPECTED_JSON_PATHS=hirSourceLocations.statements.0.location.file|hirSourceLocations.expressions.5.location.endOffset"
    "-DEXPECTED_JSON_ARRAY_LENGTHS=hirSourceLocations.expressions=10|hirSourceLocations.types=0|hirSourceLocations.statements=2|categoryCounts.expressionKinds=4|categoryCounts.statementKinds=1|categoryCounts.typeOwnerKinds=0"
    "-DEXPECTED_JSON_FIELDS=schemaVersion=7|filters.activeCount=1|filters.statementKind=assign|pagination.activeCount=0|categoryCounts.expressionTotalCount=10|categoryCounts.typeTotalCount=0|categoryCounts.statementTotalCount=2|categoryCounts.recordTotalCount=12|categoryCounts.expressionKinds.0.name=binary|categoryCounts.expressionKinds.0.count=1|categoryCounts.expressionKinds.1.name=identifier|categoryCounts.expressionKinds.1.count=3|categoryCounts.expressionKinds.2.name=index|categoryCounts.expressionKinds.2.count=2|categoryCounts.expressionKinds.3.name=literal|categoryCounts.expressionKinds.3.count=4|categoryCounts.statementKinds.0.name=assign|categoryCounts.statementKinds.0.count=2|records.enabled=false|records.totalCount=12|hirSourceLocations.expressionCount=10|hirSourceLocations.expressionWithLocationCount=10|hirSourceLocations.statementCount=2|hirSourceLocations.statementWithLocationCount=2|hirSourceLocations.statements.0.statementKind=assign|hirSourceLocations.statements.0.name=1.0|hirSourceLocations.statements.0.location.line=12|hirSourceLocations.statements.0.location.column=13|hirSourceLocations.statements.1.name=+|hirSourceLocations.statements.1.location.line=14|hirSourceLocations.expressions.1.kind=identifier|hirSourceLocations.expressions.1.value=tile|hirSourceLocations.expressions.1.type=float[GROUP_WIDTH]|hirSourceLocations.expressions.1.location.line=12|hirSourceLocations.expressions.5.kind=identifier|hirSourceLocations.expressions.5.value=tile|hirSourceLocations.expressions.5.location.line=14|hirSourceLocations.expressions.8.kind=identifier|hirSourceLocations.expressions.8.value=cached|hirSourceLocations.expressions.8.type=float"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_dump_hir_source_map_workgroup_shared_read_write_expression_provenance
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_WORKGROUP_SHARED_MEMORY_HIR_SHADER}
    -DSTAGE=hir-source-map
    -DMODE=dump-stage
    "-DSOURCE_MAP_FILTER_ARGS=--source-map-expression-kind|identifier|--source-map-operation|tile"
    "-DEXPECTED_JSON_PATHS=hirSourceLocations.expressions.0.location.file|hirSourceLocations.expressions.2.location.endOffset"
    "-DEXPECTED_JSON_ARRAY_LENGTHS=hirSourceLocations.expressions=3|hirSourceLocations.types=0|hirSourceLocations.statements=0|categoryCounts.expressionKinds=1|categoryCounts.statementKinds=0|categoryCounts.typeOwnerKinds=0"
    "-DEXPECTED_JSON_FIELDS=schemaVersion=7|filters.activeCount=2|filters.expressionKind=identifier|filters.expressionValue=tile|pagination.activeCount=0|categoryCounts.expressionTotalCount=3|categoryCounts.typeTotalCount=0|categoryCounts.statementTotalCount=0|categoryCounts.recordTotalCount=3|categoryCounts.expressionKinds.0.name=identifier|categoryCounts.expressionKinds.0.count=3|records.enabled=false|records.totalCount=3|hirSourceLocations.expressionCount=3|hirSourceLocations.expressionWithLocationCount=3|hirSourceLocations.expressions.0.index=4|hirSourceLocations.expressions.0.statementKind=assign|hirSourceLocations.expressions.0.value=tile|hirSourceLocations.expressions.0.type=float[GROUP_WIDTH]|hirSourceLocations.expressions.0.location.line=12|hirSourceLocations.expressions.0.location.column=13|hirSourceLocations.expressions.1.index=8|hirSourceLocations.expressions.1.statementKind=decl|hirSourceLocations.expressions.1.value=tile|hirSourceLocations.expressions.1.location.line=13|hirSourceLocations.expressions.1.location.column=28|hirSourceLocations.expressions.2.index=11|hirSourceLocations.expressions.2.statementKind=assign|hirSourceLocations.expressions.2.value=tile|hirSourceLocations.expressions.2.location.line=14|hirSourceLocations.expressions.2.location.column=13"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_dump_debug_workgroup_shared_resource_metadata
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_WORKGROUP_SHARED_MEMORY_HIR_SHADER}
    -DSTAGE=debug
    -DMODE=dump-stage
    "-DEXPECTED_JSON_FIELDS=schemaVersion=11|hirSourceLocations.types.6.ownerKind=resource-type|hirSourceLocations.types.6.ownerName=tile|hirSourceLocations.types.6.type=float[GROUP_WIDTH]|hirSourceLocations.types.6.location.line=9|hirSourceLocations.expressions.4.value=tile|hirSourceLocations.expressions.8.value=tile|hirSourceLocations.expressions.11.value=tile"
    -DTARGET_EXPLANATION_ROOT=targetCapabilities
    -DTARGET_RECORD_ARRAY_FIELD=summaries
    "-DEXPECTED_TARGET_ARRAY_CONTAINS=metal.requiredCapabilities=metal.resource.workgroup-shared-memory|vulkan.requiredCapabilities=vulkan.resource.workgroup-shared-memory|directx.requiredCapabilities=directx.resource.workgroup-shared-memory|opengl.requiredCapabilities=opengl.resource.workgroup-shared-memory"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_dump_hir_workgroup_barrier_expression_statements
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_WORKGROUP_BARRIER_HIR_SHADER}
    -DSTAGE=hir
    -DMODE=dump-stage
    "-DMUST_CONTAIN=workgroup_size 4, 1, 1 source GROUP_SIZE, 1, 1[^\n\r]*[\n\r]+    resource buffer int\\* values set 0 binding 0[^\n\r]*[\n\r]+    resource shared int\\[GROUP_SIZE\\] tile local[^\n\r]*[\n\r]+    fn main\\(\\) -> void[^\n\r]*[\n\r]+      decl int local = int\\(gl_LocalInvocationID\\.x\\) : int[^\n\r]*[\n\r]+      assign tile\\[local\\] : int = local \\+ 1 : int[^\n\r]*[\n\r]+      expr workgroupBarrier\\(\\) : void[^\n\r]*[\n\r]+      decl int left = tile\\[0\\] : int[^\n\r]*[\n\r]+      expr barrier\\(\\) : void[^\n\r]*[\n\r]+      decl int total = left \\+ tile\\[local\\] : int[^\n\r]*[\n\r]+      assign values\\[local\\] : int = total : int"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_dump_hir_source_map_workgroup_barrier_call_provenance
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_WORKGROUP_BARRIER_HIR_SHADER}
    -DSTAGE=hir-source-map
    -DMODE=dump-stage
    "-DSOURCE_MAP_FILTER_ARGS=--source-map-expression-kind|call"
    "-DEXPECTED_JSON_PATHS=hirSourceLocations.expressions.0.location.file|hirSourceLocations.expressions.1.location.endOffset"
    "-DEXPECTED_JSON_ARRAY_LENGTHS=hirSourceLocations.expressions=2|hirSourceLocations.types=0|hirSourceLocations.statements=0|categoryCounts.expressionKinds=1|categoryCounts.statementKinds=0|categoryCounts.typeOwnerKinds=0"
    "-DEXPECTED_JSON_FIELDS=schemaVersion=7|filters.activeCount=1|filters.expressionKind=call|pagination.activeCount=0|categoryCounts.expressionTotalCount=2|categoryCounts.recordTotalCount=2|categoryCounts.expressionKinds.0.name=call|categoryCounts.expressionKinds.0.count=2|records.enabled=false|records.totalCount=2|hirSourceLocations.expressionCount=2|hirSourceLocations.expressionWithLocationCount=2|hirSourceLocations.expressions.0.index=10|hirSourceLocations.expressions.0.stage=compute|hirSourceLocations.expressions.0.function=main|hirSourceLocations.expressions.0.statementKind=expr|hirSourceLocations.expressions.0.kind=call|hirSourceLocations.expressions.0.value=workgroupBarrier|hirSourceLocations.expressions.0.type=void|hirSourceLocations.expressions.0.location.line=13|hirSourceLocations.expressions.0.location.column=13|hirSourceLocations.expressions.0.location.length=16|hirSourceLocations.expressions.1.index=14|hirSourceLocations.expressions.1.value=barrier|hirSourceLocations.expressions.1.type=void|hirSourceLocations.expressions.1.location.line=15|hirSourceLocations.expressions.1.location.column=13|hirSourceLocations.expressions.1.location.length=7"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_dump_hir_source_map_workgroup_barrier_expr_statement_provenance
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_WORKGROUP_BARRIER_HIR_SHADER}
    -DSTAGE=hir-source-map
    -DMODE=dump-stage
    "-DSOURCE_MAP_FILTER_ARGS=--source-map-statement-kind|expr"
    "-DEXPECTED_JSON_PATHS=hirSourceLocations.statements.0.location.file|hirSourceLocations.expressions.1.location.endOffset"
    "-DEXPECTED_JSON_ARRAY_LENGTHS=hirSourceLocations.expressions=2|hirSourceLocations.types=0|hirSourceLocations.statements=2|categoryCounts.expressionKinds=1|categoryCounts.statementKinds=1|categoryCounts.typeOwnerKinds=0"
    "-DEXPECTED_JSON_FIELDS=schemaVersion=7|filters.activeCount=1|filters.statementKind=expr|pagination.activeCount=0|categoryCounts.expressionTotalCount=2|categoryCounts.statementTotalCount=2|categoryCounts.recordTotalCount=4|categoryCounts.expressionKinds.0.name=call|categoryCounts.expressionKinds.0.count=2|categoryCounts.statementKinds.0.name=expr|categoryCounts.statementKinds.0.count=2|records.enabled=false|records.totalCount=4|hirSourceLocations.expressionCount=2|hirSourceLocations.expressionWithLocationCount=2|hirSourceLocations.statementCount=2|hirSourceLocations.statementWithLocationCount=2|hirSourceLocations.expressions.0.value=workgroupBarrier|hirSourceLocations.expressions.0.type=void|hirSourceLocations.expressions.0.location.line=13|hirSourceLocations.expressions.1.value=barrier|hirSourceLocations.expressions.1.type=void|hirSourceLocations.expressions.1.location.line=15|hirSourceLocations.statements.0.index=2|hirSourceLocations.statements.0.statementKind=expr|hirSourceLocations.statements.0.name=workgroupBarrier|hirSourceLocations.statements.0.location.line=13|hirSourceLocations.statements.0.location.length=19|hirSourceLocations.statements.1.index=4|hirSourceLocations.statements.1.name=barrier|hirSourceLocations.statements.1.location.line=15|hirSourceLocations.statements.1.location.length=10"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_dump_debug_workgroup_barrier_metadata
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_WORKGROUP_BARRIER_HIR_SHADER}
    -DSTAGE=debug
    -DMODE=dump-stage
    "-DEXPECTED_JSON_FIELDS=schemaVersion=11|hirSourceLocations.types.3.ownerKind=resource-type|hirSourceLocations.types.3.ownerName=tile|hirSourceLocations.types.3.type=int[GROUP_SIZE]|hirSourceLocations.types.3.location.line=8|hirSourceLocations.types.3.location.column=9|hirSourceLocations.expressions.10.kind=call|hirSourceLocations.expressions.10.value=workgroupBarrier|hirSourceLocations.expressions.10.type=void|hirSourceLocations.expressions.10.location.line=13|hirSourceLocations.expressions.14.kind=call|hirSourceLocations.expressions.14.value=barrier|hirSourceLocations.expressions.14.type=void|hirSourceLocations.expressions.14.location.line=15|hirSourceLocations.statements.2.statementKind=expr|hirSourceLocations.statements.2.name=workgroupBarrier|hirSourceLocations.statements.4.name=barrier"
    -DTARGET_EXPLANATION_ROOT=targetCapabilities
    -DTARGET_RECORD_ARRAY_FIELD=summaries
    "-DEXPECTED_TARGET_ARRAY_CONTAINS=metal.requiredCapabilities=metal.execution.workgroup-size|metal.requiredCapabilities=metal.resource.workgroup-shared-memory|metal.requiredCapabilities=metal.operation.storage-buffer-write|vulkan.requiredCapabilities=vulkan.resource.workgroup-shared-memory|directx.requiredCapabilities=directx.resource.workgroup-shared-memory|opengl.requiredCapabilities=opengl.resource.workgroup-shared-memory"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_dump_hir_atomic_add_expression_statements
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_ATOMIC_ADD_HIR_SHADER}
    -DSTAGE=hir
    -DMODE=dump-stage
    "-DMUST_CONTAIN=workgroup_size 8, 1, 1 source GROUP_SIZE, 1, 1[^\n\r]*[\n\r]+    resource buffer atomic<int>\\* counters set 0 binding 0[^\n\r]*[\n\r]+    resource buffer int\\* deltas set 0 binding 1[^\n\r]*[\n\r]+    resource shared atomic<int>\\[GROUP_SIZE\\] tile local[^\n\r]*[\n\r]+    fn main\\(\\) -> void[^\n\r]*[\n\r]+      decl int globalIndex = int\\(gl_GlobalInvocationID\\.x\\) : int[^\n\r]*[\n\r]+      decl int localIndex = int\\(gl_LocalInvocationID\\.x\\) : int[^\n\r]*[\n\r]+      decl int delta = deltas\\[globalIndex\\] : int[^\n\r]*[\n\r]+      expr atomicAdd\\(counters\\[globalIndex\\], delta\\) : int[^\n\r]*[\n\r]+      expr atomicAdd\\(tile\\[localIndex\\], 1\\) : int"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_dump_hir_source_map_atomic_add_resource_type_provenance
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_ATOMIC_ADD_HIR_SHADER}
    -DSTAGE=hir-source-map
    -DMODE=dump-stage
    "-DSOURCE_MAP_FILTER_ARGS=--source-map-owner-kind|resource-type"
    "-DEXPECTED_JSON_PATHS=hirSourceLocations.types.0.location.file|hirSourceLocations.types.2.location.endOffset"
    "-DEXPECTED_JSON_ARRAY_LENGTHS=hirSourceLocations.expressions=0|hirSourceLocations.types=3|hirSourceLocations.statements=0|categoryCounts.typeOwnerKinds=1"
    "-DEXPECTED_JSON_FIELDS=schemaVersion=7|filters.activeCount=1|filters.ownerKind=resource-type|pagination.activeCount=0|categoryCounts.expressionTotalCount=0|categoryCounts.typeTotalCount=3|categoryCounts.statementTotalCount=0|categoryCounts.recordTotalCount=3|categoryCounts.typeOwnerKinds.0.name=resource-type|categoryCounts.typeOwnerKinds.0.count=3|records.enabled=false|records.totalCount=3|hirSourceLocations.typeCount=3|hirSourceLocations.typeWithLocationCount=3|hirSourceLocations.types.0.index=2|hirSourceLocations.types.0.stage=compute|hirSourceLocations.types.0.entryPoint=main|hirSourceLocations.types.0.ownerKind=resource-type|hirSourceLocations.types.0.ownerName=counters|hirSourceLocations.types.0.type=atomic<int>*|hirSourceLocations.types.0.location.line=6|hirSourceLocations.types.0.location.column=34|hirSourceLocations.types.0.location.length=19|hirSourceLocations.types.2.index=4|hirSourceLocations.types.2.ownerName=tile|hirSourceLocations.types.2.type=atomic<int>[GROUP_SIZE]|hirSourceLocations.types.2.location.line=9|hirSourceLocations.types.2.location.column=5|hirSourceLocations.types.2.location.length=51"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_dump_hir_source_map_atomic_add_call_provenance
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_ATOMIC_ADD_HIR_SHADER}
    -DSTAGE=hir-source-map
    -DMODE=dump-stage
    "-DSOURCE_MAP_FILTER_ARGS=--source-map-expression-kind|call"
    "-DEXPECTED_JSON_PATHS=hirSourceLocations.expressions.0.location.file|hirSourceLocations.expressions.1.location.endOffset"
    "-DEXPECTED_JSON_ARRAY_LENGTHS=hirSourceLocations.expressions=2|hirSourceLocations.types=0|hirSourceLocations.statements=0|categoryCounts.expressionKinds=1|categoryCounts.statementKinds=0|categoryCounts.typeOwnerKinds=0"
    "-DEXPECTED_JSON_FIELDS=schemaVersion=7|filters.activeCount=1|filters.expressionKind=call|pagination.activeCount=0|categoryCounts.expressionTotalCount=2|categoryCounts.recordTotalCount=2|categoryCounts.expressionKinds.0.name=call|categoryCounts.expressionKinds.0.count=2|records.enabled=false|records.totalCount=2|hirSourceLocations.expressionCount=2|hirSourceLocations.expressionWithLocationCount=2|hirSourceLocations.expressions.0.index=10|hirSourceLocations.expressions.0.stage=compute|hirSourceLocations.expressions.0.function=main|hirSourceLocations.expressions.0.statementKind=expr|hirSourceLocations.expressions.0.kind=call|hirSourceLocations.expressions.0.value=atomicAdd|hirSourceLocations.expressions.0.type=int|hirSourceLocations.expressions.0.location.line=15|hirSourceLocations.expressions.0.location.column=7|hirSourceLocations.expressions.0.location.length=9|hirSourceLocations.expressions.1.index=15|hirSourceLocations.expressions.1.value=atomicAdd|hirSourceLocations.expressions.1.type=int|hirSourceLocations.expressions.1.location.line=16|hirSourceLocations.expressions.1.location.column=7|hirSourceLocations.expressions.1.location.length=9"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_dump_hir_source_map_atomic_add_expr_statement_provenance
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_ATOMIC_ADD_HIR_SHADER}
    -DSTAGE=hir-source-map
    -DMODE=dump-stage
    "-DSOURCE_MAP_FILTER_ARGS=--source-map-statement-kind|expr"
    "-DEXPECTED_JSON_PATHS=hirSourceLocations.statements.0.location.file|hirSourceLocations.expressions.9.location.endOffset"
    "-DEXPECTED_JSON_ARRAY_LENGTHS=hirSourceLocations.expressions=10|hirSourceLocations.types=0|hirSourceLocations.statements=2|categoryCounts.expressionKinds=4|categoryCounts.statementKinds=1|categoryCounts.typeOwnerKinds=0"
    "-DEXPECTED_JSON_FIELDS=schemaVersion=7|filters.activeCount=1|filters.statementKind=expr|pagination.activeCount=0|categoryCounts.expressionTotalCount=10|categoryCounts.statementTotalCount=2|categoryCounts.recordTotalCount=12|categoryCounts.expressionKinds.0.name=call|categoryCounts.expressionKinds.0.count=2|categoryCounts.expressionKinds.1.name=identifier|categoryCounts.expressionKinds.1.count=5|categoryCounts.expressionKinds.2.name=index|categoryCounts.expressionKinds.2.count=2|categoryCounts.expressionKinds.3.name=literal|categoryCounts.expressionKinds.3.count=1|categoryCounts.statementKinds.0.name=expr|categoryCounts.statementKinds.0.count=2|records.enabled=false|records.totalCount=12|hirSourceLocations.expressionCount=10|hirSourceLocations.expressionWithLocationCount=10|hirSourceLocations.statementCount=2|hirSourceLocations.statementWithLocationCount=2|hirSourceLocations.expressions.0.kind=call|hirSourceLocations.expressions.0.value=atomicAdd|hirSourceLocations.expressions.0.type=int|hirSourceLocations.expressions.1.kind=index|hirSourceLocations.expressions.1.type=atomic<int>|hirSourceLocations.expressions.2.value=counters|hirSourceLocations.expressions.2.type=atomic<int>*|hirSourceLocations.expressions.5.value=atomicAdd|hirSourceLocations.expressions.5.type=int|hirSourceLocations.expressions.5.location.line=16|hirSourceLocations.expressions.6.kind=index|hirSourceLocations.expressions.6.type=atomic<int>|hirSourceLocations.expressions.7.value=tile|hirSourceLocations.expressions.7.type=atomic<int>[GROUP_SIZE]|hirSourceLocations.statements.0.index=3|hirSourceLocations.statements.0.statementKind=expr|hirSourceLocations.statements.0.name=atomicAdd|hirSourceLocations.statements.0.location.line=15|hirSourceLocations.statements.0.location.length=40|hirSourceLocations.statements.1.index=4|hirSourceLocations.statements.1.name=atomicAdd|hirSourceLocations.statements.1.location.line=16|hirSourceLocations.statements.1.location.length=31"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_dump_debug_atomic_add_metadata
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_ATOMIC_ADD_HIR_SHADER}
    -DSTAGE=debug
    -DMODE=dump-stage
    "-DEXPECTED_JSON_FIELDS=schemaVersion=11|hirSourceLocations.types.2.ownerKind=resource-type|hirSourceLocations.types.2.ownerName=counters|hirSourceLocations.types.2.type=atomic<int>*|hirSourceLocations.types.4.ownerKind=resource-type|hirSourceLocations.types.4.ownerName=tile|hirSourceLocations.types.4.type=atomic<int>[GROUP_SIZE]|hirSourceLocations.expressions.10.kind=call|hirSourceLocations.expressions.10.value=atomicAdd|hirSourceLocations.expressions.10.type=int|hirSourceLocations.expressions.10.location.line=15|hirSourceLocations.expressions.11.kind=index|hirSourceLocations.expressions.11.type=atomic<int>|hirSourceLocations.expressions.15.kind=call|hirSourceLocations.expressions.15.value=atomicAdd|hirSourceLocations.expressions.15.type=int|hirSourceLocations.expressions.15.location.line=16|hirSourceLocations.statements.3.statementKind=expr|hirSourceLocations.statements.3.name=atomicAdd|hirSourceLocations.statements.4.statementKind=expr|hirSourceLocations.statements.4.name=atomicAdd"
    -DTARGET_EXPLANATION_ROOT=targetCapabilities
    -DTARGET_RECORD_ARRAY_FIELD=summaries
    "-DEXPECTED_TARGET_ARRAY_CONTAINS=metal.requiredCapabilities=metal.resource.storage-buffer|metal.requiredCapabilities=metal.resource.workgroup-shared-memory|metal.requiredCapabilities=metal.operation.storage-buffer-read|vulkan.requiredCapabilities=vulkan.resource.storage-buffer|directx.requiredCapabilities=directx.resource.workgroup-shared-memory|opengl.requiredCapabilities=opengl.resource.storage-buffer"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_dump_hir_atomic_add_return_capture_contexts
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_ATOMIC_ADD_RETURN_HIR_SHADER}
    -DSTAGE=hir
    -DMODE=dump-stage
    "-DMUST_CONTAIN=expr atomicAdd\\(counters\\[index\\], delta\\) : int[^\n\r]*[\n\r]+      decl int oldDeclared = atomicAdd\\(counters\\[index\\], delta\\) : int[^\n\r]*[\n\r]+      decl int oldAssigned[^\n\r]*[\n\r]+      assign oldAssigned : int = atomicAdd\\(counters\\[index\\], 1\\) : int[^\n\r]*[\n\r]+      decl uint oldUnsigned = atomicAdd\\(unsignedCounters\\[index\\], index\\) : uint[^\n\r]*[\n\r]+      decl int oldShared = atomicAdd\\(tile\\[index\\], 1\\) : int[^\n\r]*[\n\r]+      decl int oldCompat = atomicAdd\\(compat[.]active_count, 1\\) : int"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_dump_hir_source_map_atomic_add_return_call_provenance
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_ATOMIC_ADD_RETURN_HIR_SHADER}
    -DSTAGE=hir-source-map
    -DMODE=dump-stage
    "-DSOURCE_MAP_FILTER_ARGS=--source-map-expression-kind|call|--source-map-operation|atomicAdd"
    "-DEXPECTED_JSON_PATHS=hirSourceLocations.expressions.0.location.file|hirSourceLocations.expressions.5.location.endOffset"
    "-DEXPECTED_JSON_ARRAY_LENGTHS=hirSourceLocations.expressions=6|hirSourceLocations.types=0|hirSourceLocations.statements=0|categoryCounts.expressionKinds=1|categoryCounts.statementKinds=0|categoryCounts.typeOwnerKinds=0"
    "-DEXPECTED_JSON_FIELDS=schemaVersion=7|filters.activeCount=2|filters.expressionKind=call|filters.expressionValue=atomicAdd|pagination.activeCount=0|categoryCounts.expressionTotalCount=6|categoryCounts.recordTotalCount=6|categoryCounts.expressionKinds.0.name=call|categoryCounts.expressionKinds.0.count=6|records.enabled=false|records.totalCount=6|hirSourceLocations.expressionCount=6|hirSourceLocations.expressionWithLocationCount=6|hirSourceLocations.expressions.0.index=6|hirSourceLocations.expressions.0.stage=compute|hirSourceLocations.expressions.0.function=main|hirSourceLocations.expressions.0.statementKind=expr|hirSourceLocations.expressions.0.kind=call|hirSourceLocations.expressions.0.value=atomicAdd|hirSourceLocations.expressions.0.type=int|hirSourceLocations.expressions.0.location.line=23|hirSourceLocations.expressions.0.location.column=7|hirSourceLocations.expressions.0.location.length=9|hirSourceLocations.expressions.1.index=11|hirSourceLocations.expressions.1.statementKind=decl|hirSourceLocations.expressions.1.value=atomicAdd|hirSourceLocations.expressions.1.type=int|hirSourceLocations.expressions.1.location.line=24|hirSourceLocations.expressions.1.location.column=25|hirSourceLocations.expressions.1.location.length=9|hirSourceLocations.expressions.2.index=17|hirSourceLocations.expressions.2.statementKind=assign|hirSourceLocations.expressions.2.value=atomicAdd|hirSourceLocations.expressions.2.type=int|hirSourceLocations.expressions.2.location.line=26|hirSourceLocations.expressions.2.location.column=21|hirSourceLocations.expressions.2.location.length=9|hirSourceLocations.expressions.3.index=22|hirSourceLocations.expressions.3.statementKind=decl|hirSourceLocations.expressions.3.value=atomicAdd|hirSourceLocations.expressions.3.type=uint|hirSourceLocations.expressions.3.location.line=27|hirSourceLocations.expressions.4.index=27|hirSourceLocations.expressions.4.value=atomicAdd|hirSourceLocations.expressions.4.type=int|hirSourceLocations.expressions.4.location.line=28|hirSourceLocations.expressions.5.index=32|hirSourceLocations.expressions.5.value=atomicAdd|hirSourceLocations.expressions.5.type=int|hirSourceLocations.expressions.5.location.line=29"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_dump_debug_atomic_add_return_metadata
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_ATOMIC_ADD_RETURN_HIR_SHADER}
    -DSTAGE=debug
    -DMODE=dump-stage
    "-DSOURCE_MAP_FILTER_ARGS=--source-map-expression-kind|call|--source-map-operation|atomicAdd"
    "-DEXPECTED_JSON_FIELDS=schemaVersion=11|hirSourceLocations.expressions.6.value=atomicAdd|hirSourceLocations.expressions.6.type=int|hirSourceLocations.expressions.6.location.line=23|hirSourceLocations.expressions.11.value=atomicAdd|hirSourceLocations.expressions.11.type=int|hirSourceLocations.expressions.11.location.line=24|hirSourceLocations.expressions.17.value=atomicAdd|hirSourceLocations.expressions.17.type=int|hirSourceLocations.expressions.17.location.line=26|hirSourceLocations.expressions.22.value=atomicAdd|hirSourceLocations.expressions.22.type=uint|hirSourceLocations.expressions.22.location.line=27|hirSourceLocations.expressions.27.value=atomicAdd|hirSourceLocations.expressions.27.type=int|hirSourceLocations.expressions.27.location.line=28|hirSourceLocations.expressions.32.value=atomicAdd|hirSourceLocations.expressions.32.type=int|hirSourceLocations.expressions.32.location.line=29|hirSourceLocations.statements.2.statementKind=expr|hirSourceLocations.statements.2.name=atomicAdd|hirSourceLocations.statements.3.statementKind=decl|hirSourceLocations.statements.3.name=oldDeclared|hirSourceLocations.statements.5.statementKind=assign|hirSourceLocations.statements.5.name=oldAssigned|hirSourceLocations.statements.6.statementKind=decl|hirSourceLocations.statements.6.name=oldUnsigned|hirSourceLocations.statements.7.statementKind=decl|hirSourceLocations.statements.7.name=oldShared|hirSourceLocations.statements.8.statementKind=decl|hirSourceLocations.statements.8.name=oldCompat"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_dump_hir_atomic_minmax_capture_contexts
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_ATOMIC_MINMAX_HIR_SHADER}
    -DSTAGE=hir
    -DMODE=dump-stage
    "-DMUST_CONTAIN=expr atomicMin\\(counters\\[index\\], value\\) : int[^\n\r]*[\n\r]+      expr atomicMax\\(counters\\[index\\], value\\) : int[^\n\r]*[\n\r]+      expr atomicMin\\(unsignedCounters\\[index\\], unsignedValue\\) : uint[^\n\r]*[\n\r]+      expr atomicMax\\(unsignedCounters\\[index\\], unsignedValue\\) : uint[^\n\r]*[\n\r]+      decl int oldMin = atomicMin\\(counters\\[index\\], value\\) : int[^\n\r]*[\n\r]+      decl int oldMax = atomicMax\\(counters\\[index\\], value\\) : int[^\n\r]*[\n\r]+      assign oldMin : int = atomicMin\\(counters\\[index\\], 1\\) : int[^\n\r]*[\n\r]+      decl uint oldMaxU = atomicMax\\(unsignedCounters\\[index\\], unsignedValue\\) : uint[^\n\r]*[\n\r]+      decl int oldShared = atomicMin\\(tile\\[index\\], value\\) : int[^\n\r]*[\n\r]+      decl int oldCompat = atomicMax\\(compat[.]active_count, 1\\) : int"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_dump_hir_source_map_atomic_minmax_min_call_provenance
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_ATOMIC_MINMAX_HIR_SHADER}
    -DSTAGE=hir-source-map
    -DMODE=dump-stage
    "-DSOURCE_MAP_FILTER_ARGS=--source-map-expression-kind|call|--source-map-operation|atomicMin"
    "-DEXPECTED_JSON_PATHS=hirSourceLocations.expressions.0.location.file|hirSourceLocations.expressions.4.location.endOffset"
    "-DEXPECTED_JSON_ARRAY_LENGTHS=hirSourceLocations.expressions=5|hirSourceLocations.types=0|hirSourceLocations.statements=0|categoryCounts.expressionKinds=1"
    "-DEXPECTED_JSON_FIELDS=schemaVersion=7|filters.activeCount=2|filters.expressionKind=call|filters.expressionValue=atomicMin|pagination.activeCount=0|categoryCounts.expressionTotalCount=5|categoryCounts.recordTotalCount=5|categoryCounts.expressionKinds.0.name=call|categoryCounts.expressionKinds.0.count=5|records.enabled=false|records.totalCount=5|hirSourceLocations.expressionCount=5|hirSourceLocations.expressionWithLocationCount=5|hirSourceLocations.expressions.0.stage=compute|hirSourceLocations.expressions.0.function=main|hirSourceLocations.expressions.0.statementKind=expr|hirSourceLocations.expressions.0.kind=call|hirSourceLocations.expressions.0.value=atomicMin|hirSourceLocations.expressions.0.type=int|hirSourceLocations.expressions.0.location.line=23|hirSourceLocations.expressions.0.location.column=7|hirSourceLocations.expressions.0.location.length=9|hirSourceLocations.expressions.1.statementKind=expr|hirSourceLocations.expressions.1.value=atomicMin|hirSourceLocations.expressions.1.type=uint|hirSourceLocations.expressions.1.location.line=25|hirSourceLocations.expressions.1.location.column=7|hirSourceLocations.expressions.2.statementKind=decl|hirSourceLocations.expressions.2.value=atomicMin|hirSourceLocations.expressions.2.type=int|hirSourceLocations.expressions.2.location.line=27|hirSourceLocations.expressions.2.location.column=20|hirSourceLocations.expressions.3.statementKind=assign|hirSourceLocations.expressions.3.value=atomicMin|hirSourceLocations.expressions.3.type=int|hirSourceLocations.expressions.3.location.line=29|hirSourceLocations.expressions.3.location.column=16|hirSourceLocations.expressions.4.statementKind=decl|hirSourceLocations.expressions.4.value=atomicMin|hirSourceLocations.expressions.4.type=int|hirSourceLocations.expressions.4.location.line=31|hirSourceLocations.expressions.4.location.column=23"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_dump_hir_source_map_atomic_minmax_max_call_provenance
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_ATOMIC_MINMAX_HIR_SHADER}
    -DSTAGE=hir-source-map
    -DMODE=dump-stage
    "-DSOURCE_MAP_FILTER_ARGS=--source-map-expression-kind|call|--source-map-operation|atomicMax"
    "-DEXPECTED_JSON_PATHS=hirSourceLocations.expressions.0.location.file|hirSourceLocations.expressions.4.location.endOffset"
    "-DEXPECTED_JSON_ARRAY_LENGTHS=hirSourceLocations.expressions=5|hirSourceLocations.types=0|hirSourceLocations.statements=0|categoryCounts.expressionKinds=1"
    "-DEXPECTED_JSON_FIELDS=schemaVersion=7|filters.activeCount=2|filters.expressionKind=call|filters.expressionValue=atomicMax|pagination.activeCount=0|categoryCounts.expressionTotalCount=5|categoryCounts.recordTotalCount=5|categoryCounts.expressionKinds.0.name=call|categoryCounts.expressionKinds.0.count=5|records.enabled=false|records.totalCount=5|hirSourceLocations.expressionCount=5|hirSourceLocations.expressionWithLocationCount=5|hirSourceLocations.expressions.0.stage=compute|hirSourceLocations.expressions.0.function=main|hirSourceLocations.expressions.0.statementKind=expr|hirSourceLocations.expressions.0.kind=call|hirSourceLocations.expressions.0.value=atomicMax|hirSourceLocations.expressions.0.type=int|hirSourceLocations.expressions.0.location.line=24|hirSourceLocations.expressions.0.location.column=7|hirSourceLocations.expressions.0.location.length=9|hirSourceLocations.expressions.1.statementKind=expr|hirSourceLocations.expressions.1.value=atomicMax|hirSourceLocations.expressions.1.type=uint|hirSourceLocations.expressions.1.location.line=26|hirSourceLocations.expressions.1.location.column=7|hirSourceLocations.expressions.2.statementKind=decl|hirSourceLocations.expressions.2.value=atomicMax|hirSourceLocations.expressions.2.type=int|hirSourceLocations.expressions.2.location.line=28|hirSourceLocations.expressions.2.location.column=20|hirSourceLocations.expressions.3.statementKind=decl|hirSourceLocations.expressions.3.value=atomicMax|hirSourceLocations.expressions.3.type=uint|hirSourceLocations.expressions.3.location.line=30|hirSourceLocations.expressions.3.location.column=22|hirSourceLocations.expressions.4.statementKind=decl|hirSourceLocations.expressions.4.value=atomicMax|hirSourceLocations.expressions.4.type=int|hirSourceLocations.expressions.4.location.line=32|hirSourceLocations.expressions.4.location.column=23"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_dump_debug_atomic_minmax_metadata
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_ATOMIC_MINMAX_HIR_SHADER}
    -DSTAGE=debug
    -DMODE=dump-stage
    "-DEXPECTED_JSON_FIELDS=schemaVersion=11|hirSourceLocations.expressions.9.value=atomicMin|hirSourceLocations.expressions.9.type=int|hirSourceLocations.expressions.9.location.line=23|hirSourceLocations.expressions.14.value=atomicMax|hirSourceLocations.expressions.14.type=int|hirSourceLocations.expressions.14.location.line=24|hirSourceLocations.expressions.19.value=atomicMin|hirSourceLocations.expressions.19.type=uint|hirSourceLocations.expressions.19.location.line=25|hirSourceLocations.expressions.24.value=atomicMax|hirSourceLocations.expressions.24.type=uint|hirSourceLocations.expressions.24.location.line=26|hirSourceLocations.expressions.29.value=atomicMin|hirSourceLocations.expressions.29.type=int|hirSourceLocations.expressions.29.location.line=27|hirSourceLocations.expressions.34.value=atomicMax|hirSourceLocations.expressions.34.type=int|hirSourceLocations.expressions.34.location.line=28|hirSourceLocations.expressions.40.value=atomicMin|hirSourceLocations.expressions.40.type=int|hirSourceLocations.expressions.40.location.line=29|hirSourceLocations.expressions.45.value=atomicMax|hirSourceLocations.expressions.45.type=uint|hirSourceLocations.expressions.45.location.line=30|hirSourceLocations.expressions.50.value=atomicMin|hirSourceLocations.expressions.50.type=int|hirSourceLocations.expressions.50.location.line=31|hirSourceLocations.expressions.55.value=atomicMax|hirSourceLocations.expressions.55.type=int|hirSourceLocations.expressions.55.location.line=32|hirSourceLocations.statements.3.statementKind=expr|hirSourceLocations.statements.3.name=atomicMin|hirSourceLocations.statements.4.statementKind=expr|hirSourceLocations.statements.4.name=atomicMax|hirSourceLocations.statements.7.statementKind=decl|hirSourceLocations.statements.7.name=oldMin|hirSourceLocations.statements.8.statementKind=decl|hirSourceLocations.statements.8.name=oldMax|hirSourceLocations.statements.9.statementKind=assign|hirSourceLocations.statements.9.name=oldMin|hirSourceLocations.statements.10.statementKind=decl|hirSourceLocations.statements.10.name=oldMaxU|hirSourceLocations.statements.11.statementKind=decl|hirSourceLocations.statements.11.name=oldShared|hirSourceLocations.statements.12.statementKind=decl|hirSourceLocations.statements.12.name=oldCompat"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_dump_hir_atomic_exchange_capture_contexts
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_ATOMIC_EXCHANGE_HIR_SHADER}
    -DSTAGE=hir
    -DMODE=dump-stage
    "-DMUST_CONTAIN=expr atomicExchange\\(counters\\[index\\], value\\) : int[^\n\r]*[\n\r]+      expr atomicExchange\\(unsignedCounters\\[index\\], unsignedValue\\) : uint[^\n\r]*[\n\r]+      expr atomicExchange\\(compat[.]active_count, value\\) : int[^\n\r]*[\n\r]+      expr atomicExchange\\(compat[.]spawn_count, unsignedValue\\) : uint[^\n\r]*[\n\r]+      decl int oldStorage = atomicExchange\\(counters\\[index\\], value\\) : int[^\n\r]*[\n\r]+      assign oldStorage : int = atomicExchange\\(counters\\[index\\], 1\\) : int[^\n\r]*[\n\r]+      decl uint oldUnsigned = atomicExchange\\(unsignedCounters\\[index\\], unsignedValue\\) : uint[^\n\r]*[\n\r]+      decl int oldShared = atomicExchange\\(tile\\[index\\], value\\) : int[^\n\r]*[\n\r]+      decl uint oldSharedU = atomicExchange\\(unsignedTile\\[index\\], unsignedValue\\) : uint[^\n\r]*[\n\r]+      decl int oldCompat = atomicExchange\\(compat[.]active_count, 1\\) : int[^\n\r]*[\n\r]+      decl uint oldCompatU = atomicExchange\\(compat[.]spawn_count, unsignedValue\\) : uint"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_dump_hir_source_map_atomic_exchange_call_provenance
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_ATOMIC_EXCHANGE_HIR_SHADER}
    -DSTAGE=hir-source-map
    -DMODE=dump-stage
    "-DSOURCE_MAP_FILTER_ARGS=--source-map-expression-kind|call|--source-map-operation|atomicExchange"
    "-DEXPECTED_JSON_PATHS=hirSourceLocations.expressions.0.location.file|hirSourceLocations.expressions.10.location.endOffset"
    "-DEXPECTED_JSON_ARRAY_LENGTHS=hirSourceLocations.expressions=11|hirSourceLocations.types=0|hirSourceLocations.statements=0|categoryCounts.expressionKinds=1"
    "-DEXPECTED_JSON_FIELDS=schemaVersion=7|filters.activeCount=2|filters.expressionKind=call|filters.expressionValue=atomicExchange|pagination.activeCount=0|categoryCounts.expressionTotalCount=11|categoryCounts.recordTotalCount=11|categoryCounts.expressionKinds.0.name=call|categoryCounts.expressionKinds.0.count=11|records.enabled=false|records.totalCount=11|hirSourceLocations.expressionCount=11|hirSourceLocations.expressionWithLocationCount=11|hirSourceLocations.expressions.0.stage=compute|hirSourceLocations.expressions.0.function=main|hirSourceLocations.expressions.0.statementKind=expr|hirSourceLocations.expressions.0.kind=call|hirSourceLocations.expressions.0.value=atomicExchange|hirSourceLocations.expressions.0.type=int|hirSourceLocations.expressions.0.location.line=25|hirSourceLocations.expressions.0.location.column=7|hirSourceLocations.expressions.0.location.length=14|hirSourceLocations.expressions.1.statementKind=expr|hirSourceLocations.expressions.1.value=atomicExchange|hirSourceLocations.expressions.1.type=uint|hirSourceLocations.expressions.1.location.line=26|hirSourceLocations.expressions.2.statementKind=expr|hirSourceLocations.expressions.2.type=int|hirSourceLocations.expressions.2.location.line=27|hirSourceLocations.expressions.3.statementKind=expr|hirSourceLocations.expressions.3.type=uint|hirSourceLocations.expressions.3.location.line=28|hirSourceLocations.expressions.4.statementKind=decl|hirSourceLocations.expressions.4.type=int|hirSourceLocations.expressions.4.location.line=29|hirSourceLocations.expressions.5.statementKind=assign|hirSourceLocations.expressions.5.type=int|hirSourceLocations.expressions.5.location.line=30|hirSourceLocations.expressions.6.statementKind=decl|hirSourceLocations.expressions.6.type=uint|hirSourceLocations.expressions.6.location.line=31|hirSourceLocations.expressions.7.statementKind=decl|hirSourceLocations.expressions.7.type=int|hirSourceLocations.expressions.7.location.line=32|hirSourceLocations.expressions.8.statementKind=decl|hirSourceLocations.expressions.8.type=uint|hirSourceLocations.expressions.8.location.line=33|hirSourceLocations.expressions.9.statementKind=decl|hirSourceLocations.expressions.9.type=int|hirSourceLocations.expressions.9.location.line=34|hirSourceLocations.expressions.10.statementKind=decl|hirSourceLocations.expressions.10.type=uint|hirSourceLocations.expressions.10.location.line=35"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_dump_hir_source_map_atomic_exchange_expr_statement_provenance
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_ATOMIC_EXCHANGE_HIR_SHADER}
    -DSTAGE=hir-source-map
    -DMODE=dump-stage
    "-DSOURCE_MAP_FILTER_ARGS=--source-map-statement-kind|expr"
    "-DEXPECTED_JSON_PATHS=hirSourceLocations.statements.0.location.file|hirSourceLocations.statements.3.location.endOffset"
    "-DEXPECTED_JSON_ARRAY_LENGTHS=hirSourceLocations.statements=4|categoryCounts.statementKinds=1"
    "-DEXPECTED_JSON_FIELDS=schemaVersion=7|filters.activeCount=1|filters.statementKind=expr|pagination.activeCount=0|categoryCounts.statementTotalCount=4|categoryCounts.statementKinds.0.name=expr|categoryCounts.statementKinds.0.count=4|records.enabled=false|hirSourceLocations.statementCount=4|hirSourceLocations.statementWithLocationCount=4|hirSourceLocations.statements.0.stage=compute|hirSourceLocations.statements.0.function=main|hirSourceLocations.statements.0.statementKind=expr|hirSourceLocations.statements.0.name=atomicExchange|hirSourceLocations.statements.0.location.line=25|hirSourceLocations.statements.1.statementKind=expr|hirSourceLocations.statements.1.name=atomicExchange|hirSourceLocations.statements.1.location.line=26|hirSourceLocations.statements.2.statementKind=expr|hirSourceLocations.statements.2.name=atomicExchange|hirSourceLocations.statements.2.location.line=27|hirSourceLocations.statements.3.statementKind=expr|hirSourceLocations.statements.3.name=atomicExchange|hirSourceLocations.statements.3.location.line=28"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_dump_debug_atomic_exchange_metadata
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_ATOMIC_EXCHANGE_HIR_SHADER}
    -DSTAGE=debug
    -DMODE=dump-stage
    "-DEXPECTED_JSON_FIELDS=schemaVersion=11"
    -DTARGET_EXPLANATION_ROOT=targetCapabilities
    -DTARGET_RECORD_ARRAY_FIELD=summaries
    "-DEXPECTED_TARGET_ARRAY_CONTAINS=metal.requiredCapabilities=metal.resource.storage-buffer|metal.requiredCapabilities=metal.resource.workgroup-shared-memory|metal.requiredCapabilities=metal.operation.storage-buffer-read|vulkan.requiredCapabilities=vulkan.resource.storage-buffer|directx.requiredCapabilities=directx.resource.workgroup-shared-memory|opengl.requiredCapabilities=opengl.resource.storage-buffer"
    -DMUST_CONTAIN=atomicExchange
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_dump_hir_atomic_bitwise_capture_contexts
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_ATOMIC_BITWISE_HIR_SHADER}
    -DSTAGE=hir
    -DMODE=dump-stage
    "-DMUST_CONTAIN=expr atomicAnd\\(counters\\[index\\], mask\\) : int[^\n\r]*[\n\r]+      expr atomicOr\\(unsignedCounters\\[index\\], unsignedMask\\) : uint[^\n\r]*[\n\r]+      expr atomicXor\\(compat[.]active_count, mask\\) : int[^\n\r]*[\n\r]+      decl int oldAnd = atomicAnd\\(counters\\[index\\], mask\\) : int[^\n\r]*[\n\r]+      assign oldAnd : int = atomicAnd\\(tile\\[index\\], 1\\) : int[^\n\r]*[\n\r]+      decl uint oldAndCompat = atomicAnd\\(compat[.]spawn_count, unsignedMask\\) : uint[^\n\r]*[\n\r]+      decl int oldOr = atomicOr\\(counters\\[index\\], mask\\) : int[^\n\r]*[\n\r]+      assign oldOr : int = atomicOr\\(tile\\[index\\], 1\\) : int[^\n\r]*[\n\r]+      decl uint oldOrU = atomicOr\\(unsignedCounters\\[index\\], unsignedMask\\) : uint[^\n\r]*[\n\r]+      decl int oldXor = atomicXor\\(counters\\[index\\], mask\\) : int[^\n\r]*[\n\r]+      assign oldXor : int = atomicXor\\(counters\\[index\\], 1\\) : int[^\n\r]*[\n\r]+      decl uint oldXorShared = atomicXor\\(unsignedTile\\[index\\], unsignedMask\\) : uint"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_dump_hir_source_map_atomic_bitwise_and_call_provenance
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_ATOMIC_BITWISE_HIR_SHADER}
    -DSTAGE=hir-source-map
    -DMODE=dump-stage
    "-DSOURCE_MAP_FILTER_ARGS=--source-map-expression-kind|call|--source-map-operation|atomicAnd"
    "-DEXPECTED_JSON_PATHS=hirSourceLocations.expressions.0.location.file|hirSourceLocations.expressions.3.location.endOffset"
    "-DEXPECTED_JSON_ARRAY_LENGTHS=hirSourceLocations.expressions=4|hirSourceLocations.types=0|hirSourceLocations.statements=0|categoryCounts.expressionKinds=1"
    "-DEXPECTED_JSON_FIELDS=schemaVersion=7|filters.activeCount=2|filters.expressionKind=call|filters.expressionValue=atomicAnd|pagination.activeCount=0|categoryCounts.expressionTotalCount=4|categoryCounts.recordTotalCount=4|categoryCounts.expressionKinds.0.name=call|categoryCounts.expressionKinds.0.count=4|records.enabled=false|records.totalCount=4|hirSourceLocations.expressionCount=4|hirSourceLocations.expressionWithLocationCount=4|hirSourceLocations.expressions.0.statementKind=expr|hirSourceLocations.expressions.0.kind=call|hirSourceLocations.expressions.0.value=atomicAnd|hirSourceLocations.expressions.0.type=int|hirSourceLocations.expressions.0.location.line=25|hirSourceLocations.expressions.0.location.column=7|hirSourceLocations.expressions.0.location.length=9|hirSourceLocations.expressions.1.statementKind=decl|hirSourceLocations.expressions.1.value=atomicAnd|hirSourceLocations.expressions.1.type=int|hirSourceLocations.expressions.1.location.line=28|hirSourceLocations.expressions.2.statementKind=assign|hirSourceLocations.expressions.2.type=int|hirSourceLocations.expressions.2.location.line=29|hirSourceLocations.expressions.3.statementKind=decl|hirSourceLocations.expressions.3.type=uint|hirSourceLocations.expressions.3.location.line=30"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_dump_hir_source_map_atomic_bitwise_or_call_provenance
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_ATOMIC_BITWISE_HIR_SHADER}
    -DSTAGE=hir-source-map
    -DMODE=dump-stage
    "-DSOURCE_MAP_FILTER_ARGS=--source-map-expression-kind|call|--source-map-operation|atomicOr"
    "-DEXPECTED_JSON_PATHS=hirSourceLocations.expressions.0.location.file|hirSourceLocations.expressions.3.location.endOffset"
    "-DEXPECTED_JSON_ARRAY_LENGTHS=hirSourceLocations.expressions=4|hirSourceLocations.types=0|hirSourceLocations.statements=0|categoryCounts.expressionKinds=1"
    "-DEXPECTED_JSON_FIELDS=schemaVersion=7|filters.activeCount=2|filters.expressionKind=call|filters.expressionValue=atomicOr|pagination.activeCount=0|categoryCounts.expressionTotalCount=4|categoryCounts.recordTotalCount=4|categoryCounts.expressionKinds.0.name=call|categoryCounts.expressionKinds.0.count=4|records.enabled=false|records.totalCount=4|hirSourceLocations.expressionCount=4|hirSourceLocations.expressionWithLocationCount=4|hirSourceLocations.expressions.0.statementKind=expr|hirSourceLocations.expressions.0.kind=call|hirSourceLocations.expressions.0.value=atomicOr|hirSourceLocations.expressions.0.type=uint|hirSourceLocations.expressions.0.location.line=26|hirSourceLocations.expressions.0.location.column=7|hirSourceLocations.expressions.0.location.length=8|hirSourceLocations.expressions.1.statementKind=decl|hirSourceLocations.expressions.1.value=atomicOr|hirSourceLocations.expressions.1.type=int|hirSourceLocations.expressions.1.location.line=31|hirSourceLocations.expressions.2.statementKind=assign|hirSourceLocations.expressions.2.type=int|hirSourceLocations.expressions.2.location.line=32|hirSourceLocations.expressions.3.statementKind=decl|hirSourceLocations.expressions.3.type=uint|hirSourceLocations.expressions.3.location.line=33"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_dump_hir_source_map_atomic_bitwise_xor_call_provenance
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_ATOMIC_BITWISE_HIR_SHADER}
    -DSTAGE=hir-source-map
    -DMODE=dump-stage
    "-DSOURCE_MAP_FILTER_ARGS=--source-map-expression-kind|call|--source-map-operation|atomicXor"
    "-DEXPECTED_JSON_PATHS=hirSourceLocations.expressions.0.location.file|hirSourceLocations.expressions.3.location.endOffset"
    "-DEXPECTED_JSON_ARRAY_LENGTHS=hirSourceLocations.expressions=4|hirSourceLocations.types=0|hirSourceLocations.statements=0|categoryCounts.expressionKinds=1"
    "-DEXPECTED_JSON_FIELDS=schemaVersion=7|filters.activeCount=2|filters.expressionKind=call|filters.expressionValue=atomicXor|pagination.activeCount=0|categoryCounts.expressionTotalCount=4|categoryCounts.recordTotalCount=4|categoryCounts.expressionKinds.0.name=call|categoryCounts.expressionKinds.0.count=4|records.enabled=false|records.totalCount=4|hirSourceLocations.expressionCount=4|hirSourceLocations.expressionWithLocationCount=4|hirSourceLocations.expressions.0.statementKind=expr|hirSourceLocations.expressions.0.kind=call|hirSourceLocations.expressions.0.value=atomicXor|hirSourceLocations.expressions.0.type=int|hirSourceLocations.expressions.0.location.line=27|hirSourceLocations.expressions.0.location.column=7|hirSourceLocations.expressions.0.location.length=9|hirSourceLocations.expressions.1.statementKind=decl|hirSourceLocations.expressions.1.value=atomicXor|hirSourceLocations.expressions.1.type=int|hirSourceLocations.expressions.1.location.line=34|hirSourceLocations.expressions.2.statementKind=assign|hirSourceLocations.expressions.2.type=int|hirSourceLocations.expressions.2.location.line=35|hirSourceLocations.expressions.3.statementKind=decl|hirSourceLocations.expressions.3.type=uint|hirSourceLocations.expressions.3.location.line=36"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_dump_hir_source_map_atomic_bitwise_expr_statement_provenance
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_ATOMIC_BITWISE_HIR_SHADER}
    -DSTAGE=hir-source-map
    -DMODE=dump-stage
    "-DSOURCE_MAP_FILTER_ARGS=--source-map-statement-kind|expr"
    "-DEXPECTED_JSON_PATHS=hirSourceLocations.statements.0.location.file|hirSourceLocations.statements.2.location.endOffset"
    "-DEXPECTED_JSON_ARRAY_LENGTHS=hirSourceLocations.statements=3|categoryCounts.statementKinds=1"
    "-DEXPECTED_JSON_FIELDS=schemaVersion=7|filters.activeCount=1|filters.statementKind=expr|pagination.activeCount=0|categoryCounts.statementTotalCount=3|categoryCounts.statementKinds.0.name=expr|categoryCounts.statementKinds.0.count=3|records.enabled=false|hirSourceLocations.statementCount=3|hirSourceLocations.statementWithLocationCount=3|hirSourceLocations.statements.0.statementKind=expr|hirSourceLocations.statements.0.name=atomicAnd|hirSourceLocations.statements.0.location.line=25|hirSourceLocations.statements.1.statementKind=expr|hirSourceLocations.statements.1.name=atomicOr|hirSourceLocations.statements.1.location.line=26|hirSourceLocations.statements.2.statementKind=expr|hirSourceLocations.statements.2.name=atomicXor|hirSourceLocations.statements.2.location.line=27"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_dump_debug_atomic_bitwise_metadata
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_ATOMIC_BITWISE_HIR_SHADER}
    -DSTAGE=debug
    -DMODE=dump-stage
    "-DEXPECTED_JSON_FIELDS=schemaVersion=11"
    -DTARGET_EXPLANATION_ROOT=targetCapabilities
    -DTARGET_RECORD_ARRAY_FIELD=summaries
    "-DEXPECTED_TARGET_ARRAY_CONTAINS=metal.requiredCapabilities=metal.resource.storage-buffer|metal.requiredCapabilities=metal.resource.workgroup-shared-memory|metal.requiredCapabilities=metal.operation.storage-buffer-read|vulkan.requiredCapabilities=vulkan.resource.storage-buffer|directx.requiredCapabilities=directx.resource.workgroup-shared-memory|opengl.requiredCapabilities=opengl.resource.storage-buffer"
    -DMUST_CONTAIN=atomicAnd
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_dump_hir_while_lowered_for_shape
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_WHILE_CONTROL_FLOW_HIR_SHADER}
    -DSTAGE=hir
    -DMODE=dump-stage
    "-DMUST_CONTAIN=for i < 4 : bool"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_dump_debug_manual_kernel
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_TEXTURE_2D_SHADOW_COMPARE_LOD_MANUAL_KERNEL_LIST_SHADER}
    -DSTAGE=debug
    -DMODE=dump-stage
    -DMUST_CONTAIN=manualTextureCompareKernelSummary
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_dump_hir_texture_compare_lod_manual_compare_op_operand
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_TEXTURE_2D_SHADOW_COMPARE_LOD_MANUAL_KERNEL_LIST_SHADER}
    -DSTAGE=hir
    -DMODE=dump-stage
    "-DMUST_CONTAIN=less_equal, texture_compare_kernel"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_dump_hir_texture_only_nonuniform_descriptor_array_sample_path
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_TEXTURE_ONLY_NONUNIFORM_DESCRIPTOR_ARRAY_SAMPLE_SHADER}
    -DSTAGE=hir
    -DMODE=dump-stage
    "-DMUST_CONTAIN=texture_sample_lod.colorMaps.nonuniform.descriptor.*linearSampler.*0.0"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_dump_hir_sampler_only_nonuniform_descriptor_array_sample_path
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_SAMPLER_ONLY_NONUNIFORM_DESCRIPTOR_ARRAY_SAMPLE_SHADER}
    -DSTAGE=hir
    -DMODE=dump-stage
    "-DMUST_CONTAIN=texture_sample_lod.colorMap.*linearSamplers.nonuniform.descriptor.*0.0"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_dump_hir_texture_compare_nonuniform_descriptor_array_paths
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_TEXTURE_COMPARE_NONUNIFORM_DESCRIPTOR_ARRAY_SHADER}
    -DSTAGE=hir
    -DMODE=dump-stage
    "-DMUST_CONTAIN=texture_compare.shadowMaps.nonuniform.descriptor.*shadowSamplers.nonuniform.descriptor.*0.25"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_dump_hir_texture_compare_lod_nonuniform_descriptor_array_paths
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_TEXTURE_COMPARE_NONUNIFORM_DESCRIPTOR_ARRAY_LOD_SHADER}
    -DSTAGE=hir
    -DMODE=dump-stage
    "-DMUST_CONTAIN=texture_compare_lod.shadowMaps.nonuniform.descriptor.*shadowSamplers.nonuniform.descriptor.*0.25.*2.0"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_dump_hir_texture_compare_lod_manual_nonuniform_descriptor_array_operands
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_TEXTURE_COMPARE_LOD_MANUAL_NONUNIFORM_DESCRIPTOR_ARRAY_SHADER}
    -DSTAGE=hir
    -DMODE=dump-stage
    "-DMUST_CONTAIN=texture_compare_lod_manual.shadowAtlases.nonuniform.descriptor.*rawShadowSamplers.nonuniform.descriptor.*0.33.*2.0.*less_equal"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_dump_debug_texture_compare_lod_manual_kernel_tap_summary_provenance
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_TEXTURE_2D_SHADOW_COMPARE_LOD_MANUAL_KERNEL_LIST_SHADER}
    -DSTAGE=debug
    -DMODE=dump-stage
    "-DEXPECTED_JSON_FIELDS=schemaVersion=11|manualTextureCompareKernelSummary.totalCount=1|manualTextureCompareKernelSummary.staticNormalizedCount=1|manualTextureCompareKernels.0.operation=textureCompareLodManualKernel|manualTextureCompareKernels.0.sourceKind=tap-list|manualTextureCompareKernels.0.canonicalOperation=textureCompareLodManualKernel|manualTextureCompareKernels.0.tapCount=5|manualTextureCompareKernels.0.weightClass=static-normalized|manualTextureCompareKernels.0.weightsStatic=true|manualTextureCompareKernels.0.weightsNormalized=true|manualTextureCompareKernels.0.weightSum=1"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_dump_debug_comparison_sampler_role_source_locations
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_COMPARISON_SAMPLER_ROLE_SHADER}
    -DSTAGE=debug
    -DMODE=dump-stage
    "-DEXPECTED_JSON_PATHS=hirSourceLocations.types.2.location.file|hirSourceLocations.types.4.location.endOffset|hirSourceLocations.expressions.16.location.file"
    "-DEXPECTED_JSON_FIELDS=schemaVersion=11|hirSourceLocations.types.2.ownerKind=resource-type|hirSourceLocations.types.2.ownerName=shadowCompareSamplers|hirSourceLocations.types.2.type=comparison_sampler[2]|hirSourceLocations.types.4.ownerKind=resource-type|hirSourceLocations.types.4.ownerName=linearSampler|hirSourceLocations.types.4.type=sampler|hirSourceLocations.expressions.0.kind=texture_sample|hirSourceLocations.expressions.0.value=textureLod|hirSourceLocations.expressions.2.value=linearSampler|hirSourceLocations.expressions.2.type=sampler|hirSourceLocations.expressions.7.kind=texture_compare|hirSourceLocations.expressions.7.value=textureCompare|hirSourceLocations.expressions.9.type=comparison_sampler|hirSourceLocations.expressions.16.value=textureCompareLod|hirSourceLocations.expressions.18.type=comparison_sampler"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_dump_debug_target_capabilities
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_TEXTURE_2D_SHADOW_COMPARE_LOD_MANUAL_KERNEL_LIST_SHADER}
    -DSTAGE=debug
    -DMODE=dump-stage
    "-DEXPECTED_JSON_FIELDS=schemaVersion=11"
    -DTARGET_EXPLANATION_ROOT=targetCapabilities
    -DTARGET_RECORD_ARRAY_FIELD=summaries
    "-DEXPECTED_TARGET_FIELDS=metal.nativeImplemented=true|metal.packageBuildSupported=true|metal.packageMode=native|metal.packageDecisionReason=native-package-available|metal.packageRankScore=0|vulkan.nativeImplemented=true|vulkan.packageBuildSupported=true|vulkan.packageMode=native|vulkan.packageDecisionReason=native-package-available|vulkan.packageRankScore=0|directx.packageMode=source-package|directx.packageDecisionReason=source-package-available|directx.packageBuildSupported=true|opengl.packageMode=source-package"
    "-DEXPECTED_TARGET_ARRAY_CONTAINS=directx.missingCapabilities=directx.backend.native-dxil-package|opengl.missingCapabilities=opengl.backend.native-glsl-package"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_dump_debug_vulkan_storage_image_access_qualifier_target_capabilities
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_VULKAN_STORAGE_IMAGE_ACCESS_QUALIFIER_SHADER}
    -DSTAGE=debug
    -DMODE=dump-stage
    "-DEXPECTED_JSON_FIELDS=schemaVersion=11"
    -DTARGET_EXPLANATION_ROOT=targetCapabilities
    -DTARGET_RECORD_ARRAY_FIELD=summaries
    "-DEXPECTED_TARGET_ARRAY_CONTAINS=vulkan.requiredCapabilities=vulkan.storageImage.read-only|vulkan.requiredCapabilities=vulkan.storageImage.write-only|vulkan.requiredCapabilities=vulkan.storageImage.read-write|vulkan.requiredCapabilities=vulkan.resource.storage-image|vulkan.requiredCapabilities=vulkan.capability.StorageImageArrayNonUniformIndexingEXT|vulkan.requiredCapabilities=vulkan.extension.SPV_EXT_descriptor_indexing|vulkan.requiredCapabilities=vulkan.operation.storage-image-read|vulkan.requiredCapabilities=vulkan.operation.storage-image-write"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
set(CROSSGL_STORAGE_IMAGE_ACCESS_QUALIFIER_TARGET_CAPABILITIES "metal.requiredCapabilities=metal.storageImage.read-only|metal.requiredCapabilities=metal.storageImage.write-only|metal.requiredCapabilities=metal.storageImage.read-write|metal.requiredCapabilities=metal.resource.descriptor-array|vulkan.requiredCapabilities=vulkan.storageImage.read-only|vulkan.requiredCapabilities=vulkan.storageImage.write-only|vulkan.requiredCapabilities=vulkan.storageImage.read-write|vulkan.requiredCapabilities=vulkan.resource.descriptor-array|directx.requiredCapabilities=directx.storageImage.read-only|directx.requiredCapabilities=directx.storageImage.write-only|directx.requiredCapabilities=directx.storageImage.read-write|directx.requiredCapabilities=directx.resource.descriptor-array|opengl.requiredCapabilities=opengl.storageImage.read-only|opengl.requiredCapabilities=opengl.storageImage.write-only|opengl.requiredCapabilities=opengl.storageImage.read-write|opengl.requiredCapabilities=opengl.resource.descriptor-array")
set(CROSSGL_STORAGE_IMAGE_EXPLICIT_FORMAT_DESCRIPTOR_ARRAY_TARGET_CAPABILITIES "metal.requiredCapabilities=metal.resource.descriptor-array|metal.requiredCapabilities=metal.storageImage.r32f-format|metal.requiredCapabilities=metal.storageImage.r32i-format|metal.requiredCapabilities=metal.storageImage.r32ui-format|metal.requiredCapabilities=metal.operation.nonuniform-storage-image-descriptor-index|vulkan.requiredCapabilities=vulkan.resource.descriptor-array|vulkan.requiredCapabilities=vulkan.storageImage.r32f-format|vulkan.requiredCapabilities=vulkan.storageImage.r32i-format|vulkan.requiredCapabilities=vulkan.storageImage.r32ui-format|vulkan.requiredCapabilities=vulkan.operation.nonuniform-storage-image-descriptor-index|vulkan.requiredCapabilities=vulkan.extension.SPV_EXT_descriptor_indexing|vulkan.requiredCapabilities=vulkan.capability.StorageImageArrayNonUniformIndexingEXT|directx.requiredCapabilities=directx.resource.descriptor-array|directx.requiredCapabilities=directx.storageImage.r32f-format|directx.requiredCapabilities=directx.storageImage.r32i-format|directx.requiredCapabilities=directx.storageImage.r32ui-format|directx.requiredCapabilities=directx.operation.nonuniform-storage-image-descriptor-index|directx.requiredCapabilities=directx.intrinsic.NonUniformResourceIndex|opengl.requiredCapabilities=opengl.resource.descriptor-array|opengl.requiredCapabilities=opengl.storageImage.r32f-format|opengl.requiredCapabilities=opengl.storageImage.r32i-format|opengl.requiredCapabilities=opengl.storageImage.r32ui-format|opengl.requiredCapabilities=opengl.operation.nonuniform-storage-image-descriptor-index|opengl.requiredCapabilities=opengl.extension.GL_EXT_nonuniform_qualifier")
set(CROSSGL_STORAGE_IMAGE_ATOMIC_DESCRIPTOR_ARRAY_TARGET_CAPABILITIES "metal.requiredCapabilities=metal.resource.descriptor-array|metal.requiredCapabilities=metal.storageImage.read-write|metal.requiredCapabilities=metal.storageImage.r32i-format|metal.requiredCapabilities=metal.storageImage.r32ui-format|metal.requiredCapabilities=metal.operation.storage-image-atomic-add|metal.requiredCapabilities=metal.operation.storage-image-atomic-min|metal.requiredCapabilities=metal.operation.storage-image-atomic-max|metal.requiredCapabilities=metal.operation.storage-image-atomic-and|metal.requiredCapabilities=metal.operation.storage-image-atomic-or|metal.requiredCapabilities=metal.operation.storage-image-atomic-exchange|metal.requiredCapabilities=metal.operation.storage-image-atomic-xor|metal.requiredCapabilities=metal.operation.nonuniform-storage-image-descriptor-index|vulkan.requiredCapabilities=vulkan.resource.descriptor-array|vulkan.requiredCapabilities=vulkan.storageImage.read-write|vulkan.requiredCapabilities=vulkan.storageImage.r32i-format|vulkan.requiredCapabilities=vulkan.storageImage.r32ui-format|vulkan.requiredCapabilities=vulkan.operation.storage-image-atomic-add|vulkan.requiredCapabilities=vulkan.operation.storage-image-atomic-min|vulkan.requiredCapabilities=vulkan.operation.storage-image-atomic-max|vulkan.requiredCapabilities=vulkan.operation.storage-image-atomic-and|vulkan.requiredCapabilities=vulkan.operation.storage-image-atomic-or|vulkan.requiredCapabilities=vulkan.operation.storage-image-atomic-exchange|vulkan.requiredCapabilities=vulkan.operation.storage-image-atomic-xor|vulkan.requiredCapabilities=vulkan.operation.nonuniform-storage-image-descriptor-index|vulkan.requiredCapabilities=vulkan.extension.SPV_EXT_descriptor_indexing|vulkan.requiredCapabilities=vulkan.capability.StorageImageArrayNonUniformIndexingEXT|directx.requiredCapabilities=directx.resource.descriptor-array|directx.requiredCapabilities=directx.storageImage.read-write|directx.requiredCapabilities=directx.storageImage.r32i-format|directx.requiredCapabilities=directx.storageImage.r32ui-format|directx.requiredCapabilities=directx.operation.storage-image-atomic-add|directx.requiredCapabilities=directx.operation.storage-image-atomic-min|directx.requiredCapabilities=directx.operation.storage-image-atomic-max|directx.requiredCapabilities=directx.operation.storage-image-atomic-and|directx.requiredCapabilities=directx.operation.storage-image-atomic-or|directx.requiredCapabilities=directx.operation.storage-image-atomic-exchange|directx.requiredCapabilities=directx.operation.storage-image-atomic-xor|directx.requiredCapabilities=directx.operation.nonuniform-storage-image-descriptor-index|directx.requiredCapabilities=directx.intrinsic.NonUniformResourceIndex|opengl.requiredCapabilities=opengl.resource.descriptor-array|opengl.requiredCapabilities=opengl.storageImage.read-write|opengl.requiredCapabilities=opengl.storageImage.r32i-format|opengl.requiredCapabilities=opengl.storageImage.r32ui-format|opengl.requiredCapabilities=opengl.operation.storage-image-atomic-add|opengl.requiredCapabilities=opengl.operation.storage-image-atomic-min|opengl.requiredCapabilities=opengl.operation.storage-image-atomic-max|opengl.requiredCapabilities=opengl.operation.storage-image-atomic-and|opengl.requiredCapabilities=opengl.operation.storage-image-atomic-or|opengl.requiredCapabilities=opengl.operation.storage-image-atomic-exchange|opengl.requiredCapabilities=opengl.operation.storage-image-atomic-xor|opengl.requiredCapabilities=opengl.operation.nonuniform-storage-image-descriptor-index|opengl.requiredCapabilities=opengl.extension.GL_EXT_nonuniform_qualifier")
add_test(NAME cglc_dump_debug_storage_image_access_qualifier_descriptor_array_target_capabilities
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_STORAGE_IMAGE_ACCESS_QUALIFIER_HIR_SHADER}
    -DSTAGE=debug
    -DMODE=dump-stage
    "-DEXPECTED_JSON_FIELDS=schemaVersion=11"
    -DTARGET_EXPLANATION_ROOT=targetCapabilities
    -DTARGET_RECORD_ARRAY_FIELD=summaries
    "-DEXPECTED_TARGET_ARRAY_CONTAINS=${CROSSGL_STORAGE_IMAGE_ACCESS_QUALIFIER_TARGET_CAPABILITIES}"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_dump_debug_storage_image_explicit_format_nonuniform_descriptor_array_target_capabilities
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_STORAGE_IMAGE_EXPLICIT_FORMAT_DESCRIPTOR_ARRAY_SHADER}
    -DSTAGE=debug
    -DMODE=dump-stage
    "-DEXPECTED_JSON_FIELDS=schemaVersion=11"
    -DTARGET_EXPLANATION_ROOT=targetCapabilities
    -DTARGET_RECORD_ARRAY_FIELD=summaries
    "-DEXPECTED_TARGET_ARRAY_CONTAINS=${CROSSGL_STORAGE_IMAGE_EXPLICIT_FORMAT_DESCRIPTOR_ARRAY_TARGET_CAPABILITIES}"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_dump_debug_storage_image_atomic_nonuniform_descriptor_array_target_capabilities
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_STORAGE_IMAGE_ATOMIC_DESCRIPTOR_ARRAY_SHADER}
    -DSTAGE=debug
    -DMODE=dump-stage
    "-DEXPECTED_JSON_FIELDS=schemaVersion=11"
    -DTARGET_EXPLANATION_ROOT=targetCapabilities
    -DTARGET_RECORD_ARRAY_FIELD=summaries
    "-DEXPECTED_TARGET_ARRAY_CONTAINS=${CROSSGL_STORAGE_IMAGE_ATOMIC_DESCRIPTOR_ARRAY_TARGET_CAPABILITIES}"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
crossgl_add_python_expect_test(
  NAME cglc_dump_debug_json_schema
  DEFINITIONS
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_TEXTURE_2D_SHADOW_COMPARE_LOD_MANUAL_KERNEL_LIST_SHADER}
    -DTARGET=directx
    -DSTAGE=debug
    -DMODE=dump-stage
    -DJSON_SCHEMA=${CMAKE_CURRENT_SOURCE_DIR}/docs/schemas/debug-metadata-v11.schema.json
    -DJSON_SCHEMA_VALIDATOR=${CMAKE_CURRENT_SOURCE_DIR}/tools/validate_json_schema.py
    "-DEXPECTED_JSON_FIELDS=schemaVersion=11|targetDecision.requestedTarget=directx|targetDecision.selectedTargetPackageMode=source-package|targetDecision.selectedTargetMissingCapabilityCount=3|targetDecision.selectedTargetRequiredToolCount=2|targetDecision.selectedTargetMissingToolCount=2|targetDecision.selectedTargetOptionalNativeToolMissing=true|targetDecision.selectedTargetOptionalNativeToolStatus=missing|targetCapabilities.summaries.2.requiredToolCount=2|targetCapabilities.summaries.2.missingToolCount=2|targetCapabilities.summaries.2.optionalNativeToolMissing=true|targetCapabilities.summaries.2.optionalNativeToolStatus=missing|targetDecision.fallbackTargetRecords.2.requiredToolCount=2|targetDecision.fallbackTargetRecords.2.missingToolCount=2|targetDecision.fallbackTargetRecords.2.optionalNativeToolMissing=true|targetDecision.fallbackTargetRecords.2.optionalNativeToolStatus=missing|manualTextureCompareKernelSummary.totalCount=1|manualTextureCompareKernels.0.weightClass=static-normalized"
    "-DEXPECTED_JSON_ARRAY_CONTAINS=targetDecision.selectedTargetRequiredToolIds=directx.toolchain.dxc|targetDecision.selectedTargetMissingToolIds=directx.validation.dxil-validator|targetDecision.selectedTargetToolRequirementEvidenceIds=target-legalization.v1.directx.tool-requirement.missing.validation.dxil-validator|targetDecision.packageArtifactRequirementEvidenceIds=target-legalization.v1.directx.package-artifacts.source-package|targetCapabilities.summaries.2.requiredToolIds=directx.toolchain.dxc|targetCapabilities.summaries.2.missingToolIds=directx.validation.dxil-validator|targetCapabilities.summaries.2.toolRequirementEvidenceIds=target-legalization.v1.directx.tool-requirement.missing.validation.dxil-validator|targetCapabilities.summaries.2.packageArtifactRequirementEvidenceIds=target-legalization.v1.directx.package-artifact.planned-native-source-evidence.allowed|targetDecision.fallbackTargetRecords.2.requiredToolIds=opengl.toolchain.opengl-driver|targetDecision.fallbackTargetRecords.2.missingToolIds=opengl.validation.glsl-program-validation|targetDecision.fallbackTargetRecords.2.toolRequirementEvidenceIds=target-legalization.v1.opengl.tool-requirement.missing.validation.glsl-program-validation|targetDecision.fallbackTargetRecords.2.packageArtifactRequirementEvidenceIds=target-legalization.v1.opengl.package-artifact.planned-native-source-evidence.allowed")
add_test(NAME cglc_dump_debug_hir_source_locations
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_TEXTURE_2D_SHADOW_COMPARE_LOD_MANUAL_KERNEL_LIST_SHADER}
    -DSTAGE=debug
    -DMODE=dump-stage
    "-DEXPECTED_JSON_PATHS=hirSourceLocations.expressions|hirSourceLocations.types|hirSourceLocations.statements|hirSourceLocations.expressions.0.location.file|hirSourceLocations.expressions.0.location.endOffset|hirSourceLocations.types.0.location.file|hirSourceLocations.types.0.location.endOffset|hirSourceLocations.statements.0.location.file|hirSourceLocations.statements.0.location.endOffset"
    "-DEXPECTED_JSON_FIELDS=hirSourceLocations.expressions.0.stage=compute|hirSourceLocations.expressions.0.function=main|hirSourceLocations.expressions.0.kind=texture_compare_lod_manual|hirSourceLocations.expressions.0.value=textureCompareLodManualKernel|hirSourceLocations.types.0.ownerKind=resource-type|hirSourceLocations.statements.0.statementKind=decl|hirSourceLocations.statements.0.name=visibility|hirSourceLocations.statements.0.location.line=9|hirSourceLocations.statements.0.location.endLine=17"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
crossgl_add_python_expect_test(
  NAME cglc_dump_debug_logical_source_remap
  DEFINITIONS
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_TEXTURE_2D_SHADOW_COMPARE_LOD_MANUAL_KERNEL_LIST_SHADER}
    -DSTAGE=debug
    -DMODE=dump-stage
    "-DSOURCE_MAP_FILTER_ARGS=--logical-input|generated/from-translator.cgl|--source-remap|${CMAKE_CURRENT_SOURCE_DIR}/tests/fixtures/source-remap-v1-full-file.json"
    "-DEXPECTED_JSON_FIELDS=schemaVersion=11|hirSourceLocations.expressions.0.location.file=generated/from-translator.cgl|hirSourceLocations.expressions.0.originalLocation.file=shaders/original.crossgl|hirSourceLocations.types.0.location.file=generated/from-translator.cgl|hirSourceLocations.types.0.originalLocation.file=shaders/original.crossgl|hirSourceLocations.statements.0.location.file=generated/from-translator.cgl|hirSourceLocations.statements.0.originalLocation.file=shaders/original.crossgl"
    -DJSON_SCHEMA=${CMAKE_CURRENT_SOURCE_DIR}/docs/schemas/debug-metadata-v11.schema.json
    -DJSON_SCHEMA_VALIDATOR=${CMAKE_CURRENT_SOURCE_DIR}/tools/validate_json_schema.py)
add_test(NAME cglc_dump_debug_texture_compare_lod_manual_compare_op_provenance
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_TEXTURE_2D_SHADOW_COMPARE_LOD_MANUAL_KERNEL_LIST_SHADER}
    -DSTAGE=debug
    -DMODE=dump-stage
    "-DEXPECTED_JSON_PATHS=hirSourceLocations.expressions.8.location.file|hirSourceLocations.expressions.8.location.endOffset"
    "-DEXPECTED_JSON_FIELDS=hirSourceLocations.expressions.8.index=8|hirSourceLocations.expressions.8.stage=compute|hirSourceLocations.expressions.8.function=main|hirSourceLocations.expressions.8.statementKind=decl|hirSourceLocations.expressions.8.kind=identifier|hirSourceLocations.expressions.8.value=less_equal|hirSourceLocations.expressions.8.location.line=12|hirSourceLocations.expressions.8.location.column=15|hirSourceLocations.expressions.8.location.length=10|hirSourceLocations.expressions.8.location.endLine=12|hirSourceLocations.expressions.8.location.endColumn=25"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_dump_debug_while_lowered_for_source_location
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_WHILE_CONTROL_FLOW_HIR_SHADER}
    -DSTAGE=debug
    -DMODE=dump-stage
    "-DEXPECTED_JSON_FIELDS=hirSourceLocations.statements.3.stage=compute|hirSourceLocations.statements.3.function=main|hirSourceLocations.statements.3.statementKind=for|hirSourceLocations.statements.3.name=<|hirSourceLocations.statements.3.location.line=11|hirSourceLocations.statements.3.location.column=7|hirSourceLocations.statements.3.location.endLine=21|hirSourceLocations.statements.3.location.endColumn=8|hirSourceLocations.expressions.2.statementKind=for|hirSourceLocations.expressions.2.kind=binary|hirSourceLocations.expressions.2.value=<|hirSourceLocations.expressions.2.location.line=11|hirSourceLocations.expressions.2.location.column=16"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_dump_hir_source_map
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_TEXTURE_2D_SHADOW_COMPARE_LOD_MANUAL_KERNEL_LIST_SHADER}
    -DSTAGE=hir-source-map
    -DMODE=dump-stage
    "-DEXPECTED_JSON_PATHS=hirSourceLocations.expressions|hirSourceLocations.types|hirSourceLocations.statements|hirSourceLocations.expressions.0.location.file|hirSourceLocations.expressions.0.location.endOffset|hirSourceLocations.types.0.location.file|hirSourceLocations.types.0.location.endOffset|hirSourceLocations.statements.0.location.file|hirSourceLocations.statements.0.location.endOffset"
    "-DEXPECTED_JSON_FIELDS=schemaVersion=7|filters.activeCount=0|pagination.activeCount=0|categoryCounts.expressionTotalCount=36|categoryCounts.typeTotalCount=10|categoryCounts.statementTotalCount=3|categoryCounts.recordTotalCount=49|categoryCounts.expressionKinds.4.name=literal|categoryCounts.expressionKinds.4.count=20|categoryCounts.statementKinds.1.name=decl|categoryCounts.statementKinds.1.count=1|categoryCounts.typeOwnerKinds.0.name=expression-type|categoryCounts.typeOwnerKinds.0.count=5|records.enabled=false|records.activeCount=0|records.totalCount=49|records.emittedCount=0|hirSourceLocations.expressions.0.kind=texture_compare_lod_manual|hirSourceLocations.expressions.0.value=textureCompareLodManualKernel|hirSourceLocations.types.0.ownerKind=resource-type|hirSourceLocations.statements.0.statementKind=decl|hirSourceLocations.statements.0.location.line=9|hirSourceLocations.statements.0.location.endLine=17"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_dump_hir_source_map_logical_input_path
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_TEXTURE_2D_SHADOW_COMPARE_LOD_MANUAL_KERNEL_LIST_SHADER}
    -DSTAGE=hir-source-map
    -DMODE=dump-stage
    "-DSOURCE_MAP_FILTER_ARGS=--logical-input|generated/from-translator.cgl|--source-map-limit|1"
    "-DEXPECTED_JSON_ARRAY_LENGTHS=hirSourceLocations.expressions=1|hirSourceLocations.types=1|hirSourceLocations.statements=1"
    "-DEXPECTED_JSON_FIELDS=schemaVersion=7|pagination.activeCount=3|hirSourceLocations.expressions.0.location.file=generated/from-translator.cgl|hirSourceLocations.types.0.location.file=generated/from-translator.cgl|hirSourceLocations.statements.0.location.file=generated/from-translator.cgl"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
crossgl_add_python_expect_test(
  NAME cglc_dump_hir_source_map_logical_source_remap
  DEFINITIONS
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_TEXTURE_2D_SHADOW_COMPARE_LOD_MANUAL_KERNEL_LIST_SHADER}
    -DSTAGE=hir-source-map
    -DMODE=dump-stage
    "-DSOURCE_MAP_FILTER_ARGS=--logical-input|generated/from-translator.cgl|--source-remap|${CMAKE_CURRENT_SOURCE_DIR}/tests/fixtures/source-remap-v1-full-file.json|--source-map-limit|1"
    "-DEXPECTED_JSON_ARRAY_LENGTHS=hirSourceLocations.expressions=1|hirSourceLocations.types=1|hirSourceLocations.statements=1"
    "-DEXPECTED_JSON_FIELDS=schemaVersion=7|pagination.activeCount=3|hirSourceLocations.expressions.0.location.file=generated/from-translator.cgl|hirSourceLocations.expressions.0.originalLocation.file=shaders/original.crossgl|hirSourceLocations.types.0.location.file=generated/from-translator.cgl|hirSourceLocations.types.0.originalLocation.file=shaders/original.crossgl|hirSourceLocations.statements.0.location.file=generated/from-translator.cgl|hirSourceLocations.statements.0.originalLocation.file=shaders/original.crossgl"
    -DJSON_SCHEMA=${CMAKE_CURRENT_SOURCE_DIR}/docs/schemas/hir-source-map-v7.schema.json
    -DJSON_SCHEMA_VALIDATOR=${CMAKE_CURRENT_SOURCE_DIR}/tools/validate_json_schema.py)
crossgl_add_python_expect_test(
  NAME cglc_dump_backend_source_map_directx_logical_source_remap
  DEFINITIONS
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_STORAGE_BUFFER_COMPUTE_SHADER}
    -DTARGET=directx
    -DSTAGE=backend-source-map
    -DMODE=dump-stage
    "-DSOURCE_MAP_FILTER_ARGS=--logical-input|generated/from-translator.cgl|--source-remap|${CMAKE_CURRENT_SOURCE_DIR}/tests/fixtures/source-remap-v1-full-file.json"
    "-DEXPECTED_JSON_ARRAY_LENGTHS=mappings=2"
    "-DEXPECTED_JSON_FIELDS=schemaVersion=1|kind=crossgl.backendSourceMap|target=directx|module=StorageBufferComputeShader|mappingGranularity=statement|sourceBackend=crossgl-hir|targetBackend=hlsl|backend.language=hlsl|backend.lineCount=7|sourceRemap.generatedFile=generated/from-translator.cgl|sourceRemap.mappingCount=1|sourceRemap.sizeBytes=592|mappingCount=2|mappings.0.stage=compute|mappings.0.entryPoint=main|mappings.0.function=main|mappings.0.statementKind=assign|mappings.0.name=values[0]|mappings.0.backend.startLine=5|mappings.0.backend.endLine=5|mappings.0.location.file=generated/from-translator.cgl|mappings.0.location.line=8|mappings.0.originalLocation.file=shaders/original.crossgl|mappings.0.originalLocation.line=47|mappings.1.statementKind=return|mappings.1.backend.startLine=6|mappings.1.originalLocation.line=48"
    -DJSON_SCHEMA=${CMAKE_CURRENT_SOURCE_DIR}/docs/schemas/backend-source-map-v1.schema.json
    -DJSON_SCHEMA_VALIDATOR=${CMAKE_CURRENT_SOURCE_DIR}/tools/validate_json_schema.py)
crossgl_add_python_expect_test(
  NAME cglc_dump_backend_source_map_directx_crosstl_metadata_source_remap
  DEFINITIONS
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_STORAGE_BUFFER_COMPUTE_SHADER}
    -DTARGET=directx
    -DSTAGE=backend-source-map
    -DMODE=dump-stage
    "-DSOURCE_MAP_FILTER_ARGS=--logical-input|generated/from-translator.cgl|--source-remap|${CMAKE_CURRENT_SOURCE_DIR}/tests/fixtures/source-remap-v1-full-file-report-metadata.json"
    "-DEXPECTED_JSON_ARRAY_LENGTHS=mappings=2"
    "-DEXPECTED_JSON_FIELDS=schemaVersion=1|kind=crossgl.backendSourceMap|target=directx|module=StorageBufferComputeShader|mappingGranularity=statement|sourceBackend=crossgl-hir|targetBackend=hlsl|backend.language=hlsl|backend.lineCount=7|sourceRemap.target=cgl|sourceRemap.generatedFile=generated/from-translator.cgl|sourceRemap.mappingGranularity=file|sourceRemap.mappingCount=1|sourceRemap.sizeBytes=592|sourceRemap.sourceBackend=cgl|sourceRemap.variant=debug|mappings.0.originalLocation.file=shaders/original.crossgl|mappings.1.originalLocation.line=48"
    -DJSON_SCHEMA=${CMAKE_CURRENT_SOURCE_DIR}/docs/schemas/backend-source-map-v1.schema.json
    -DJSON_SCHEMA_VALIDATOR=${CMAKE_CURRENT_SOURCE_DIR}/tools/validate_json_schema.py)
crossgl_add_python_expect_test(
  NAME cglc_dump_backend_source_map_opengl_logical_source_remap
  DEFINITIONS
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_STORAGE_BUFFER_COMPUTE_SHADER}
    -DTARGET=opengl
    -DSTAGE=backend-source-map
    -DMODE=dump-stage
    "-DSOURCE_MAP_FILTER_ARGS=--logical-input|generated/from-translator.cgl|--source-remap|${CMAKE_CURRENT_SOURCE_DIR}/tests/fixtures/source-remap-v1-full-file-report-metadata.json"
    "-DEXPECTED_JSON_ARRAY_LENGTHS=mappings=2"
    "-DEXPECTED_JSON_FIELDS=schemaVersion=1|kind=crossgl.backendSourceMap|target=opengl|module=StorageBufferComputeShader|mappingGranularity=statement|sourceBackend=crossgl-hir|targetBackend=glsl|backend.language=glsl|backend.lineCount=13|sourceRemap.target=cgl|sourceRemap.generatedFile=generated/from-translator.cgl|sourceRemap.mappingGranularity=file|sourceRemap.mappingCount=1|sourceRemap.sizeBytes=592|sourceRemap.sourceBackend=cgl|sourceRemap.variant=debug|mappingCount=2|mappings.0.stage=compute|mappings.0.entryPoint=compute_main|mappings.0.function=main|mappings.0.statementKind=assign|mappings.0.name=values[0]|mappings.0.backend.startLine=10|mappings.0.backend.endLine=10|mappings.0.location.file=generated/from-translator.cgl|mappings.0.location.line=8|mappings.0.originalLocation.file=shaders/original.crossgl|mappings.0.originalLocation.line=47|mappings.1.statementKind=return|mappings.1.backend.startLine=11|mappings.1.backend.endLine=11|mappings.1.originalLocation.line=48"
    -DJSON_SCHEMA=${CMAKE_CURRENT_SOURCE_DIR}/docs/schemas/backend-source-map-v1.schema.json
    -DJSON_SCHEMA_VALIDATOR=${CMAKE_CURRENT_SOURCE_DIR}/tools/validate_json_schema.py)
crossgl_add_python_expect_test(
  NAME cglc_dump_backend_source_map_metal_logical_source_remap
  DEFINITIONS
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_STORAGE_BUFFER_COMPUTE_SHADER}
    -DTARGET=metal
    -DSTAGE=backend-source-map
    -DMODE=dump-stage
    "-DSOURCE_MAP_FILTER_ARGS=--logical-input|generated/from-translator.cgl|--source-remap|${CMAKE_CURRENT_SOURCE_DIR}/tests/fixtures/source-remap-v1-full-file-report-metadata.json"
    "-DEXPECTED_JSON_ARRAY_LENGTHS=mappings=2"
    "-DEXPECTED_JSON_FIELDS=schemaVersion=1|kind=crossgl.backendSourceMap|target=metal|module=StorageBufferComputeShader|mappingGranularity=statement|sourceBackend=crossgl-hir|targetBackend=msl|backend.language=msl|backend.lineCount=8|sourceRemap.target=cgl|sourceRemap.generatedFile=generated/from-translator.cgl|sourceRemap.mappingGranularity=file|sourceRemap.mappingCount=1|sourceRemap.sizeBytes=592|sourceRemap.sourceBackend=cgl|sourceRemap.variant=debug|mappingCount=2|mappings.0.stage=compute|mappings.0.entryPoint=compute_main|mappings.0.function=main|mappings.0.statementKind=assign|mappings.0.name=values[0]|mappings.0.backend.startLine=5|mappings.0.backend.endLine=5|mappings.0.location.file=generated/from-translator.cgl|mappings.0.location.line=8|mappings.0.originalLocation.file=shaders/original.crossgl|mappings.0.originalLocation.line=47|mappings.1.statementKind=return|mappings.1.backend.startLine=6|mappings.1.backend.endLine=6|mappings.1.originalLocation.line=48"
    -DJSON_SCHEMA=${CMAKE_CURRENT_SOURCE_DIR}/docs/schemas/backend-source-map-v1.schema.json
    -DJSON_SCHEMA_VALIDATOR=${CMAKE_CURRENT_SOURCE_DIR}/tools/validate_json_schema.py)
add_test(NAME cglc_dump_hir_source_map_while_lowered_for_provenance
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_WHILE_CONTROL_FLOW_HIR_SHADER}
    -DSTAGE=hir-source-map
    -DMODE=dump-stage
    "-DSOURCE_MAP_FILTER_ARGS=--source-map-statement-kind|for"
    "-DEXPECTED_JSON_ARRAY_LENGTHS=hirSourceLocations.expressions=3|hirSourceLocations.types=0|hirSourceLocations.statements=1|categoryCounts.expressionKinds=3|categoryCounts.statementKinds=1|categoryCounts.typeOwnerKinds=0"
    "-DEXPECTED_JSON_FIELDS=schemaVersion=7|filters.activeCount=1|filters.statementKind=for|pagination.activeCount=0|categoryCounts.expressionTotalCount=3|categoryCounts.typeTotalCount=0|categoryCounts.statementTotalCount=1|categoryCounts.recordTotalCount=4|categoryCounts.expressionKinds.0.name=binary|categoryCounts.expressionKinds.0.count=1|categoryCounts.statementKinds.0.name=for|categoryCounts.statementKinds.0.count=1|records.enabled=false|records.totalCount=4|hirSourceLocations.expressionCount=3|hirSourceLocations.expressionWithLocationCount=3|hirSourceLocations.statementCount=1|hirSourceLocations.statementWithLocationCount=1|hirSourceLocations.statements.0.stage=compute|hirSourceLocations.statements.0.function=main|hirSourceLocations.statements.0.statementKind=for|hirSourceLocations.statements.0.name=<|hirSourceLocations.statements.0.location.line=11|hirSourceLocations.statements.0.location.column=7|hirSourceLocations.statements.0.location.endLine=21|hirSourceLocations.statements.0.location.endColumn=8|hirSourceLocations.expressions.0.statementKind=for|hirSourceLocations.expressions.0.kind=binary|hirSourceLocations.expressions.0.value=<|hirSourceLocations.expressions.0.location.line=11|hirSourceLocations.expressions.0.location.column=16"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_dump_hir_source_map_while_contract_lowered_for_provenance
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_WHILE_COMPUTE_SHADER}
    -DSTAGE=hir-source-map
    -DMODE=dump-stage
    "-DSOURCE_MAP_FILTER_ARGS=--source-map-statement-kind|for"
    "-DEXPECTED_JSON_ARRAY_LENGTHS=hirSourceLocations.expressions=3|hirSourceLocations.types=0|hirSourceLocations.statements=1|categoryCounts.expressionKinds=3|categoryCounts.statementKinds=1|categoryCounts.typeOwnerKinds=0"
    "-DEXPECTED_JSON_FIELDS=schemaVersion=7|filters.activeCount=1|filters.statementKind=for|pagination.activeCount=0|categoryCounts.expressionTotalCount=3|categoryCounts.typeTotalCount=0|categoryCounts.statementTotalCount=1|categoryCounts.recordTotalCount=4|categoryCounts.expressionKinds.0.name=binary|categoryCounts.expressionKinds.0.count=1|categoryCounts.statementKinds.0.name=for|categoryCounts.statementKinds.0.count=1|records.enabled=false|records.totalCount=4|hirSourceLocations.expressionCount=3|hirSourceLocations.expressionWithLocationCount=3|hirSourceLocations.statementCount=1|hirSourceLocations.statementWithLocationCount=1|hirSourceLocations.statements.0.stage=compute|hirSourceLocations.statements.0.function=main|hirSourceLocations.statements.0.statementKind=for|hirSourceLocations.statements.0.name=<|hirSourceLocations.statements.0.location.line=8|hirSourceLocations.statements.0.location.column=7|hirSourceLocations.statements.0.location.endLine=11|hirSourceLocations.statements.0.location.endColumn=8|hirSourceLocations.expressions.0.statementKind=for|hirSourceLocations.expressions.0.kind=binary|hirSourceLocations.expressions.0.value=<|hirSourceLocations.expressions.0.location.line=8|hirSourceLocations.expressions.0.location.column=16"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_dump_hir_source_map_for_compute_provenance
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_FOR_COMPUTE_SHADER}
    -DSTAGE=hir-source-map
    -DMODE=dump-stage
    "-DSOURCE_MAP_FILTER_ARGS=--source-map-statement-kind|for"
    "-DEXPECTED_JSON_ARRAY_LENGTHS=hirSourceLocations.expressions=3|hirSourceLocations.types=0|hirSourceLocations.statements=1|categoryCounts.expressionKinds=3|categoryCounts.statementKinds=1|categoryCounts.typeOwnerKinds=0"
    "-DEXPECTED_JSON_FIELDS=schemaVersion=7|filters.activeCount=1|filters.statementKind=for|pagination.activeCount=0|categoryCounts.expressionTotalCount=3|categoryCounts.statementTotalCount=1|categoryCounts.recordTotalCount=4|categoryCounts.expressionKinds.0.name=binary|categoryCounts.expressionKinds.0.count=1|categoryCounts.statementKinds.0.name=for|categoryCounts.statementKinds.0.count=1|records.enabled=false|records.totalCount=4|hirSourceLocations.expressionCount=3|hirSourceLocations.expressionWithLocationCount=3|hirSourceLocations.statementCount=1|hirSourceLocations.statementWithLocationCount=1|hirSourceLocations.statements.0.stage=compute|hirSourceLocations.statements.0.function=main|hirSourceLocations.statements.0.statementKind=for|hirSourceLocations.statements.0.name=<|hirSourceLocations.statements.0.location.line=7|hirSourceLocations.statements.0.location.column=7|hirSourceLocations.statements.0.location.endLine=10|hirSourceLocations.statements.0.location.endColumn=8|hirSourceLocations.expressions.0.statementKind=for|hirSourceLocations.expressions.0.kind=binary|hirSourceLocations.expressions.0.value=<|hirSourceLocations.expressions.0.type=bool|hirSourceLocations.expressions.0.location.line=7|hirSourceLocations.expressions.0.location.column=25"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_dump_hir_source_map_for_stride_update_provenance
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_FOR_STRIDE_COMPUTE_SHADER}
    -DSTAGE=hir-source-map
    -DMODE=dump-stage
    "-DSOURCE_MAP_FILTER_ARGS=--source-map-expression-kind|binary"
    "-DEXPECTED_JSON_ARRAY_LENGTHS=hirSourceLocations.expressions=3|hirSourceLocations.types=0|hirSourceLocations.statements=0|categoryCounts.expressionKinds=1|categoryCounts.statementKinds=0|categoryCounts.typeOwnerKinds=0"
    "-DEXPECTED_JSON_FIELDS=schemaVersion=7|filters.activeCount=1|filters.expressionKind=binary|pagination.activeCount=0|categoryCounts.expressionTotalCount=3|categoryCounts.statementTotalCount=0|categoryCounts.recordTotalCount=3|categoryCounts.expressionKinds.0.name=binary|categoryCounts.expressionKinds.0.count=3|records.enabled=false|records.totalCount=3|hirSourceLocations.expressionCount=3|hirSourceLocations.expressionWithLocationCount=3|hirSourceLocations.expressions.0.statementKind=for|hirSourceLocations.expressions.0.value=<|hirSourceLocations.expressions.0.location.line=7|hirSourceLocations.expressions.0.location.column=25|hirSourceLocations.expressions.1.statementKind=assign|hirSourceLocations.expressions.1.kind=binary|hirSourceLocations.expressions.1.value=+|hirSourceLocations.expressions.1.type=int|hirSourceLocations.expressions.1.location.line=7|hirSourceLocations.expressions.1.location.column=32|hirSourceLocations.expressions.2.statementKind=assign|hirSourceLocations.expressions.2.type=float"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_dump_hir_source_map_nested_for_provenance
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_NESTED_FOR_COMPUTE_SHADER}
    -DSTAGE=hir-source-map
    -DMODE=dump-stage
    "-DSOURCE_MAP_FILTER_ARGS=--source-map-statement-kind|for"
    "-DEXPECTED_JSON_ARRAY_LENGTHS=hirSourceLocations.expressions=6|hirSourceLocations.types=0|hirSourceLocations.statements=2|categoryCounts.expressionKinds=3|categoryCounts.statementKinds=1|categoryCounts.typeOwnerKinds=0"
    "-DEXPECTED_JSON_FIELDS=schemaVersion=7|filters.activeCount=1|filters.statementKind=for|pagination.activeCount=0|categoryCounts.expressionTotalCount=6|categoryCounts.statementTotalCount=2|categoryCounts.recordTotalCount=8|categoryCounts.expressionKinds.0.name=binary|categoryCounts.expressionKinds.0.count=2|categoryCounts.statementKinds.0.name=for|categoryCounts.statementKinds.0.count=2|records.enabled=false|records.totalCount=8|hirSourceLocations.expressionCount=6|hirSourceLocations.statementCount=2|hirSourceLocations.statementWithLocationCount=2|hirSourceLocations.statements.0.statementKind=for|hirSourceLocations.statements.0.location.line=7|hirSourceLocations.statements.0.location.column=7|hirSourceLocations.statements.0.location.endLine=14|hirSourceLocations.statements.1.statementKind=for|hirSourceLocations.statements.1.location.line=8|hirSourceLocations.statements.1.location.column=9|hirSourceLocations.statements.1.location.endLine=12|hirSourceLocations.expressions.3.statementKind=for|hirSourceLocations.expressions.3.value=<|hirSourceLocations.expressions.3.location.line=8|hirSourceLocations.expressions.3.location.column=27"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_dump_hir_source_map_for_dynamic_stride_identifier_provenance
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_FOR_DYNAMIC_STRIDE_COMPUTE_SHADER}
    -DSTAGE=hir-source-map
    -DMODE=dump-stage
    "-DSOURCE_MAP_FILTER_ARGS=--source-map-expression-kind|identifier"
    "-DEXPECTED_JSON_ARRAY_LENGTHS=hirSourceLocations.expressions=9|hirSourceLocations.types=0|hirSourceLocations.statements=0|categoryCounts.expressionKinds=1|categoryCounts.statementKinds=0|categoryCounts.typeOwnerKinds=0"
    "-DEXPECTED_JSON_FIELDS=schemaVersion=7|filters.activeCount=1|filters.expressionKind=identifier|pagination.activeCount=0|categoryCounts.expressionTotalCount=9|categoryCounts.recordTotalCount=9|categoryCounts.expressionKinds.0.name=identifier|categoryCounts.expressionKinds.0.count=9|records.enabled=false|records.totalCount=9|hirSourceLocations.expressionCount=9|hirSourceLocations.expressionWithLocationCount=9|hirSourceLocations.expressions.0.statementKind=for|hirSourceLocations.expressions.0.value=i|hirSourceLocations.expressions.0.location.line=8|hirSourceLocations.expressions.3.statementKind=assign|hirSourceLocations.expressions.3.kind=identifier|hirSourceLocations.expressions.3.value=stride|hirSourceLocations.expressions.3.type=int|hirSourceLocations.expressions.3.location.line=8|hirSourceLocations.expressions.3.location.column=35|hirSourceLocations.expressions.3.location.length=6"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_dump_hir_source_map_for_constant_stride_identifier_provenance
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_FOR_CONSTANT_STRIDE_COMPUTE_SHADER}
    -DSTAGE=hir-source-map
    -DMODE=dump-stage
    "-DSOURCE_MAP_FILTER_ARGS=--source-map-expression-kind|identifier"
    "-DEXPECTED_JSON_ARRAY_LENGTHS=hirSourceLocations.expressions=9|hirSourceLocations.types=0|hirSourceLocations.statements=0|categoryCounts.expressionKinds=1|categoryCounts.statementKinds=0|categoryCounts.typeOwnerKinds=0"
    "-DEXPECTED_JSON_FIELDS=schemaVersion=7|filters.activeCount=1|filters.expressionKind=identifier|pagination.activeCount=0|categoryCounts.expressionTotalCount=9|categoryCounts.recordTotalCount=9|categoryCounts.expressionKinds.0.name=identifier|categoryCounts.expressionKinds.0.count=9|records.enabled=false|records.totalCount=9|hirSourceLocations.expressionCount=9|hirSourceLocations.expressionWithLocationCount=9|hirSourceLocations.expressions.0.statementKind=for|hirSourceLocations.expressions.0.value=i|hirSourceLocations.expressions.0.location.line=9|hirSourceLocations.expressions.3.statementKind=assign|hirSourceLocations.expressions.3.kind=identifier|hirSourceLocations.expressions.3.value=TILE_SIZE|hirSourceLocations.expressions.3.type=int|hirSourceLocations.expressions.3.location.line=9|hirSourceLocations.expressions.3.location.column=35|hirSourceLocations.expressions.3.location.length=9"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_dump_hir_source_map_for_folded_update_literal_provenance
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_FOR_FOLDED_UPDATE_COMPUTE_SHADER}
    -DSTAGE=hir-source-map
    -DMODE=dump-stage
    "-DSOURCE_MAP_FILTER_ARGS=--source-map-expression-kind|literal"
    "-DEXPECTED_JSON_ARRAY_LENGTHS=hirSourceLocations.expressions=4|hirSourceLocations.types=0|hirSourceLocations.statements=0|categoryCounts.expressionKinds=1|categoryCounts.statementKinds=0|categoryCounts.typeOwnerKinds=0"
    "-DEXPECTED_JSON_FIELDS=schemaVersion=7|filters.activeCount=1|filters.expressionKind=literal|pagination.activeCount=0|categoryCounts.expressionTotalCount=4|categoryCounts.recordTotalCount=4|categoryCounts.expressionKinds.0.name=literal|categoryCounts.expressionKinds.0.count=4|records.enabled=false|records.totalCount=4|hirSourceLocations.expressionCount=4|hirSourceLocations.expressionWithLocationCount=4|hirSourceLocations.expressions.0.statementKind=for|hirSourceLocations.expressions.0.value=8|hirSourceLocations.expressions.0.location.line=7|hirSourceLocations.expressions.2.statementKind=assign|hirSourceLocations.expressions.2.kind=literal|hirSourceLocations.expressions.2.value=3|hirSourceLocations.expressions.2.type=int|hirSourceLocations.expressions.2.location.line=7|hirSourceLocations.expressions.2.location.column=41"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_dump_hir_source_map_for_increment_decrement_provenance
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_FOR_INCREMENT_DECREMENT_HIR_SHADER}
    -DSTAGE=hir-source-map
    -DMODE=dump-stage
    "-DSOURCE_MAP_FILTER_ARGS=--source-map-statement-kind|for"
    "-DEXPECTED_JSON_ARRAY_LENGTHS=hirSourceLocations.expressions=12|hirSourceLocations.types=0|hirSourceLocations.statements=4|categoryCounts.expressionKinds=3|categoryCounts.statementKinds=1|categoryCounts.typeOwnerKinds=0"
    "-DEXPECTED_JSON_FIELDS=schemaVersion=7|filters.activeCount=1|filters.statementKind=for|pagination.activeCount=0|categoryCounts.expressionTotalCount=12|categoryCounts.statementTotalCount=4|categoryCounts.recordTotalCount=16|categoryCounts.expressionKinds.0.name=binary|categoryCounts.expressionKinds.0.count=4|categoryCounts.statementKinds.0.name=for|categoryCounts.statementKinds.0.count=4|records.enabled=false|records.totalCount=16|hirSourceLocations.expressionCount=12|hirSourceLocations.statementCount=4|hirSourceLocations.statementWithLocationCount=4|hirSourceLocations.statements.0.statementKind=for|hirSourceLocations.statements.0.name=<|hirSourceLocations.statements.0.location.line=9|hirSourceLocations.statements.1.statementKind=for|hirSourceLocations.statements.1.name=<|hirSourceLocations.statements.1.location.line=13|hirSourceLocations.statements.2.statementKind=for|hirSourceLocations.statements.2.name=>|hirSourceLocations.statements.2.location.line=17|hirSourceLocations.statements.3.statementKind=for|hirSourceLocations.statements.3.name=>|hirSourceLocations.statements.3.location.line=21"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_dump_hir_source_map_for_increment_decrement_update_provenance
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_FOR_INCREMENT_DECREMENT_HIR_SHADER}
    -DSTAGE=hir-source-map
    -DMODE=dump-stage
    "-DSOURCE_MAP_FILTER_ARGS=--source-map-expression-kind|binary"
    "-DEXPECTED_JSON_ARRAY_LENGTHS=hirSourceLocations.expressions=13|hirSourceLocations.types=0|hirSourceLocations.statements=0|categoryCounts.expressionKinds=1|categoryCounts.statementKinds=0|categoryCounts.typeOwnerKinds=0"
    "-DEXPECTED_JSON_FIELDS=schemaVersion=7|filters.activeCount=1|filters.expressionKind=binary|pagination.activeCount=0|categoryCounts.expressionTotalCount=13|categoryCounts.recordTotalCount=13|categoryCounts.expressionKinds.0.name=binary|categoryCounts.expressionKinds.0.count=13|records.enabled=false|records.totalCount=13|hirSourceLocations.expressionCount=13|hirSourceLocations.expressionWithLocationCount=13|hirSourceLocations.expressions.1.statementKind=assign|hirSourceLocations.expressions.1.value=+|hirSourceLocations.expressions.1.type=int|hirSourceLocations.expressions.1.location.line=9|hirSourceLocations.expressions.1.location.column=31|hirSourceLocations.expressions.1.location.length=2|hirSourceLocations.expressions.4.statementKind=assign|hirSourceLocations.expressions.4.value=+|hirSourceLocations.expressions.4.location.line=13|hirSourceLocations.expressions.4.location.column=30|hirSourceLocations.expressions.4.location.length=2|hirSourceLocations.expressions.7.statementKind=assign|hirSourceLocations.expressions.7.value=-|hirSourceLocations.expressions.7.location.line=17|hirSourceLocations.expressions.7.location.column=31|hirSourceLocations.expressions.7.location.length=2|hirSourceLocations.expressions.10.statementKind=assign|hirSourceLocations.expressions.10.value=-|hirSourceLocations.expressions.10.location.line=21|hirSourceLocations.expressions.10.location.column=30|hirSourceLocations.expressions.10.location.length=2"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_dump_hir_source_map_if_branch_provenance
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_IF_COMPUTE_SHADER}
    -DSTAGE=hir-source-map
    -DMODE=dump-stage
    "-DSOURCE_MAP_FILTER_ARGS=--source-map-statement-kind|if"
    "-DEXPECTED_JSON_ARRAY_LENGTHS=hirSourceLocations.expressions=3|hirSourceLocations.types=0|hirSourceLocations.statements=1|categoryCounts.expressionKinds=3|categoryCounts.statementKinds=1|categoryCounts.typeOwnerKinds=0"
    "-DEXPECTED_JSON_FIELDS=schemaVersion=7|filters.activeCount=1|filters.statementKind=if|pagination.activeCount=0|categoryCounts.expressionTotalCount=3|categoryCounts.typeTotalCount=0|categoryCounts.statementTotalCount=1|categoryCounts.recordTotalCount=4|categoryCounts.expressionKinds.0.name=binary|categoryCounts.expressionKinds.0.count=1|categoryCounts.statementKinds.0.name=if|categoryCounts.statementKinds.0.count=1|records.enabled=false|records.totalCount=4|hirSourceLocations.expressionCount=3|hirSourceLocations.expressionWithLocationCount=3|hirSourceLocations.statementCount=1|hirSourceLocations.statementWithLocationCount=1|hirSourceLocations.statements.0.stage=compute|hirSourceLocations.statements.0.function=main|hirSourceLocations.statements.0.statementKind=if|hirSourceLocations.statements.0.name=>|hirSourceLocations.statements.0.location.line=9|hirSourceLocations.statements.0.location.column=7|hirSourceLocations.statements.0.location.endLine=13|hirSourceLocations.statements.0.location.endColumn=8|hirSourceLocations.expressions.0.statementKind=if|hirSourceLocations.expressions.0.kind=binary|hirSourceLocations.expressions.0.value=>|hirSourceLocations.expressions.0.type=bool|hirSourceLocations.expressions.0.location.line=9|hirSourceLocations.expressions.0.location.column=13"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_dump_hir_source_map_nested_if_branch_provenance
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_NESTED_IF_COMPUTE_SHADER}
    -DSTAGE=hir-source-map
    -DMODE=dump-stage
    "-DSOURCE_MAP_FILTER_ARGS=--source-map-statement-kind|if"
    "-DEXPECTED_JSON_ARRAY_LENGTHS=hirSourceLocations.expressions=6|hirSourceLocations.types=0|hirSourceLocations.statements=2|categoryCounts.expressionKinds=3|categoryCounts.statementKinds=1|categoryCounts.typeOwnerKinds=0"
    "-DEXPECTED_JSON_FIELDS=schemaVersion=7|filters.activeCount=1|filters.statementKind=if|pagination.activeCount=0|categoryCounts.expressionTotalCount=6|categoryCounts.typeTotalCount=0|categoryCounts.statementTotalCount=2|categoryCounts.recordTotalCount=8|categoryCounts.expressionKinds.0.name=binary|categoryCounts.expressionKinds.0.count=2|categoryCounts.statementKinds.0.name=if|categoryCounts.statementKinds.0.count=2|records.enabled=false|records.totalCount=8|hirSourceLocations.expressionCount=6|hirSourceLocations.expressionWithLocationCount=6|hirSourceLocations.statementCount=2|hirSourceLocations.statementWithLocationCount=2|hirSourceLocations.statements.0.statementKind=if|hirSourceLocations.statements.0.location.line=9|hirSourceLocations.statements.0.location.endLine=18|hirSourceLocations.statements.1.statementKind=if|hirSourceLocations.statements.1.location.line=11|hirSourceLocations.statements.1.location.column=9|hirSourceLocations.statements.1.location.endLine=15|hirSourceLocations.expressions.3.statementKind=if|hirSourceLocations.expressions.3.kind=binary|hirSourceLocations.expressions.3.value=>|hirSourceLocations.expressions.3.type=bool|hirSourceLocations.expressions.3.location.line=11|hirSourceLocations.expressions.4.kind=identifier|hirSourceLocations.expressions.4.value=scaled|hirSourceLocations.expressions.4.type=float|hirSourceLocations.expressions.4.location.line=11|hirSourceLocations.expressions.5.kind=literal|hirSourceLocations.expressions.5.value=3.0|hirSourceLocations.expressions.5.type=float"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_dump_hir_source_map_if_return_branch_provenance
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_IF_RETURN_COMPUTE_SHADER}
    -DSTAGE=hir-source-map
    -DMODE=dump-stage
    "-DSOURCE_MAP_FILTER_ARGS=--source-map-statement-kind|return"
    "-DEXPECTED_JSON_ARRAY_LENGTHS=hirSourceLocations.expressions=0|hirSourceLocations.types=0|hirSourceLocations.statements=2|categoryCounts.expressionKinds=0|categoryCounts.statementKinds=1|categoryCounts.typeOwnerKinds=0"
    "-DEXPECTED_JSON_FIELDS=schemaVersion=7|filters.activeCount=1|filters.statementKind=return|pagination.activeCount=0|categoryCounts.expressionTotalCount=0|categoryCounts.typeTotalCount=0|categoryCounts.statementTotalCount=2|categoryCounts.recordTotalCount=2|categoryCounts.statementKinds.0.name=return|categoryCounts.statementKinds.0.count=2|records.enabled=false|records.totalCount=2|hirSourceLocations.expressionCount=0|hirSourceLocations.statementCount=2|hirSourceLocations.statementWithLocationCount=2|hirSourceLocations.statements.0.stage=compute|hirSourceLocations.statements.0.function=main|hirSourceLocations.statements.0.statementKind=return|hirSourceLocations.statements.0.location.line=10|hirSourceLocations.statements.0.location.column=9|hirSourceLocations.statements.0.location.endLine=10|hirSourceLocations.statements.0.location.endColumn=16|hirSourceLocations.statements.1.statementKind=return|hirSourceLocations.statements.1.location.line=13|hirSourceLocations.statements.1.location.column=9|hirSourceLocations.statements.1.location.endLine=13|hirSourceLocations.statements.1.location.endColumn=16"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_dump_hir_source_map_read_modify_write_provenance
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_READ_MODIFY_WRITE_COMPUTE_SHADER}
    -DSTAGE=hir-source-map
    -DMODE=dump-stage
    "-DSOURCE_MAP_FILTER_ARGS=--source-map-statement-kind|assign"
    "-DEXPECTED_JSON_ARRAY_LENGTHS=hirSourceLocations.expressions=8|hirSourceLocations.types=0|hirSourceLocations.statements=1|categoryCounts.expressionKinds=4|categoryCounts.statementKinds=1|categoryCounts.typeOwnerKinds=0"
    "-DEXPECTED_JSON_FIELDS=schemaVersion=7|filters.activeCount=1|filters.statementKind=assign|pagination.activeCount=0|categoryCounts.expressionTotalCount=8|categoryCounts.typeTotalCount=0|categoryCounts.statementTotalCount=1|categoryCounts.recordTotalCount=9|categoryCounts.expressionKinds.0.name=binary|categoryCounts.expressionKinds.0.count=1|categoryCounts.expressionKinds.1.name=identifier|categoryCounts.expressionKinds.1.count=2|categoryCounts.expressionKinds.2.name=index|categoryCounts.expressionKinds.2.count=2|categoryCounts.expressionKinds.3.name=literal|categoryCounts.expressionKinds.3.count=3|categoryCounts.statementKinds.0.name=assign|categoryCounts.statementKinds.0.count=1|records.enabled=false|records.totalCount=9|hirSourceLocations.expressionCount=8|hirSourceLocations.expressionWithLocationCount=8|hirSourceLocations.statementCount=1|hirSourceLocations.statementWithLocationCount=1|hirSourceLocations.statements.0.statementKind=assign|hirSourceLocations.statements.0.name=+|hirSourceLocations.statements.0.location.line=7|hirSourceLocations.statements.0.location.column=13|hirSourceLocations.statements.0.location.endColumn=41|hirSourceLocations.expressions.3.statementKind=assign|hirSourceLocations.expressions.3.kind=binary|hirSourceLocations.expressions.3.value=+|hirSourceLocations.expressions.3.type=float|hirSourceLocations.expressions.3.location.line=7|hirSourceLocations.expressions.3.location.column=35|hirSourceLocations.expressions.5.kind=identifier|hirSourceLocations.expressions.5.value=values|hirSourceLocations.expressions.5.type=float*|hirSourceLocations.expressions.7.kind=literal|hirSourceLocations.expressions.7.value=1.0|hirSourceLocations.expressions.7.type=float"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_dump_hir_source_map_arithmetic_return_provenance
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_ARITHMETIC_COMPUTE_SHADER}
    -DSTAGE=hir-source-map
    -DMODE=dump-stage
    "-DSOURCE_MAP_FILTER_ARGS=--source-map-statement-kind|return"
    "-DEXPECTED_JSON_ARRAY_LENGTHS=hirSourceLocations.expressions=0|hirSourceLocations.types=0|hirSourceLocations.statements=1|categoryCounts.expressionKinds=0|categoryCounts.statementKinds=1|categoryCounts.typeOwnerKinds=0"
    "-DEXPECTED_JSON_FIELDS=schemaVersion=7|filters.activeCount=1|filters.statementKind=return|pagination.activeCount=0|categoryCounts.expressionTotalCount=0|categoryCounts.typeTotalCount=0|categoryCounts.statementTotalCount=1|categoryCounts.recordTotalCount=1|categoryCounts.statementKinds.0.name=return|categoryCounts.statementKinds.0.count=1|records.enabled=false|records.totalCount=1|hirSourceLocations.expressionCount=0|hirSourceLocations.statementCount=1|hirSourceLocations.statementWithLocationCount=1|hirSourceLocations.statements.0.stage=compute|hirSourceLocations.statements.0.function=main|hirSourceLocations.statements.0.statementKind=return|hirSourceLocations.statements.0.location.line=11|hirSourceLocations.statements.0.location.column=13|hirSourceLocations.statements.0.location.endLine=11|hirSourceLocations.statements.0.location.endColumn=20"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_dump_hir_source_map_comparison_return_provenance
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_COMPARISON_COMPUTE_SHADER}
    -DSTAGE=hir-source-map
    -DMODE=dump-stage
    "-DSOURCE_MAP_FILTER_ARGS=--source-map-statement-kind|return"
    "-DEXPECTED_JSON_ARRAY_LENGTHS=hirSourceLocations.expressions=0|hirSourceLocations.types=0|hirSourceLocations.statements=1|categoryCounts.expressionKinds=0|categoryCounts.statementKinds=1|categoryCounts.typeOwnerKinds=0"
    "-DEXPECTED_JSON_FIELDS=schemaVersion=7|filters.activeCount=1|filters.statementKind=return|pagination.activeCount=0|categoryCounts.expressionTotalCount=0|categoryCounts.typeTotalCount=0|categoryCounts.statementTotalCount=1|categoryCounts.recordTotalCount=1|categoryCounts.statementKinds.0.name=return|categoryCounts.statementKinds.0.count=1|records.enabled=false|records.totalCount=1|hirSourceLocations.expressionCount=0|hirSourceLocations.statementCount=1|hirSourceLocations.statementWithLocationCount=1|hirSourceLocations.statements.0.stage=compute|hirSourceLocations.statements.0.function=main|hirSourceLocations.statements.0.statementKind=return|hirSourceLocations.statements.0.location.line=12|hirSourceLocations.statements.0.location.column=13|hirSourceLocations.statements.0.location.endLine=12|hirSourceLocations.statements.0.location.endColumn=20"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_dump_hir_source_map_load_local_assign_provenance
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_LOAD_LOCAL_COMPUTE_SHADER}
    -DSTAGE=hir-source-map
    -DMODE=dump-stage
    "-DSOURCE_MAP_FILTER_ARGS=--source-map-statement-kind|assign"
    "-DEXPECTED_JSON_ARRAY_LENGTHS=hirSourceLocations.expressions=6|hirSourceLocations.types=0|hirSourceLocations.statements=1|categoryCounts.expressionKinds=4|categoryCounts.statementKinds=1|categoryCounts.typeOwnerKinds=0"
    "-DEXPECTED_JSON_FIELDS=schemaVersion=7|filters.activeCount=1|filters.statementKind=assign|pagination.activeCount=0|categoryCounts.expressionTotalCount=6|categoryCounts.typeTotalCount=0|categoryCounts.statementTotalCount=1|categoryCounts.recordTotalCount=7|categoryCounts.expressionKinds.0.name=binary|categoryCounts.expressionKinds.0.count=1|categoryCounts.expressionKinds.1.name=identifier|categoryCounts.expressionKinds.1.count=2|categoryCounts.expressionKinds.2.name=index|categoryCounts.expressionKinds.2.count=1|categoryCounts.expressionKinds.3.name=literal|categoryCounts.expressionKinds.3.count=2|categoryCounts.statementKinds.0.name=assign|categoryCounts.statementKinds.0.count=1|records.enabled=false|records.totalCount=7|hirSourceLocations.expressionCount=6|hirSourceLocations.expressionWithLocationCount=6|hirSourceLocations.statementCount=1|hirSourceLocations.statementWithLocationCount=1|hirSourceLocations.statements.0.statementKind=assign|hirSourceLocations.statements.0.name=+|hirSourceLocations.statements.0.location.line=8|hirSourceLocations.statements.0.location.column=13|hirSourceLocations.expressions.3.kind=binary|hirSourceLocations.expressions.3.value=+|hirSourceLocations.expressions.3.type=float|hirSourceLocations.expressions.3.location.line=8|hirSourceLocations.expressions.3.location.column=27|hirSourceLocations.expressions.4.kind=identifier|hirSourceLocations.expressions.4.value=x|hirSourceLocations.expressions.4.type=float|hirSourceLocations.expressions.5.kind=literal|hirSourceLocations.expressions.5.value=1.0|hirSourceLocations.expressions.5.type=float"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_dump_hir_source_map_scalar_constructor_construct_provenance
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_SCALAR_CONSTRUCTOR_COMPUTE_SHADER}
    -DSTAGE=hir-source-map
    -DMODE=dump-stage
    "-DSOURCE_MAP_FILTER_ARGS=--source-map-expression-kind|construct"
    "-DEXPECTED_JSON_ARRAY_LENGTHS=hirSourceLocations.expressions=4|hirSourceLocations.types=0|hirSourceLocations.statements=0|categoryCounts.expressionKinds=1|categoryCounts.statementKinds=0|categoryCounts.typeOwnerKinds=0"
    "-DEXPECTED_JSON_FIELDS=schemaVersion=7|filters.activeCount=1|filters.expressionKind=construct|pagination.activeCount=0|categoryCounts.expressionTotalCount=4|categoryCounts.typeTotalCount=0|categoryCounts.statementTotalCount=0|categoryCounts.recordTotalCount=4|categoryCounts.expressionKinds.0.name=construct|categoryCounts.expressionKinds.0.count=4|records.enabled=false|records.totalCount=4|hirSourceLocations.expressionCount=4|hirSourceLocations.expressionWithLocationCount=4|hirSourceLocations.expressions.0.statementKind=decl|hirSourceLocations.expressions.0.kind=construct|hirSourceLocations.expressions.0.value=int|hirSourceLocations.expressions.0.type=int|hirSourceLocations.expressions.0.location.line=8|hirSourceLocations.expressions.0.location.column=25|hirSourceLocations.expressions.1.value=uint|hirSourceLocations.expressions.1.type=uint|hirSourceLocations.expressions.1.location.line=9|hirSourceLocations.expressions.1.location.column=28|hirSourceLocations.expressions.3.value=float|hirSourceLocations.expressions.3.type=float|hirSourceLocations.expressions.3.location.line=11|hirSourceLocations.expressions.3.location.column=28"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_dump_hir_source_map_scalar_constructor_local_decl_type_provenance
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_SCALAR_CONSTRUCTOR_COMPUTE_SHADER}
    -DSTAGE=hir-source-map
    -DMODE=dump-stage
    "-DSOURCE_MAP_FILTER_ARGS=--source-map-owner-kind|statement-declared-type"
    "-DEXPECTED_JSON_PATHS=hirSourceLocations.types.0.location.file|hirSourceLocations.types.4.location.endOffset"
    "-DEXPECTED_JSON_ARRAY_LENGTHS=hirSourceLocations.expressions=0|hirSourceLocations.types=5|hirSourceLocations.statements=0|categoryCounts.expressionKinds=0|categoryCounts.statementKinds=0|categoryCounts.typeOwnerKinds=1"
    "-DEXPECTED_JSON_FIELDS=schemaVersion=7|filters.activeCount=1|filters.ownerKind=statement-declared-type|pagination.activeCount=0|categoryCounts.expressionTotalCount=0|categoryCounts.typeTotalCount=5|categoryCounts.statementTotalCount=0|categoryCounts.recordTotalCount=5|categoryCounts.typeOwnerKinds.0.name=statement-declared-type|categoryCounts.typeOwnerKinds.0.count=5|records.enabled=false|records.totalCount=5|hirSourceLocations.expressionCount=0|hirSourceLocations.typeCount=5|hirSourceLocations.typeWithLocationCount=5|hirSourceLocations.statementCount=0|hirSourceLocations.types.0.stage=compute|hirSourceLocations.types.0.entryPoint=main|hirSourceLocations.types.0.function=main|hirSourceLocations.types.0.ownerKind=statement-declared-type|hirSourceLocations.types.0.ownerName=source|hirSourceLocations.types.0.type=float|hirSourceLocations.types.0.location.line=7|hirSourceLocations.types.0.location.column=7|hirSourceLocations.types.0.location.length=5|hirSourceLocations.types.1.ownerName=signedValue|hirSourceLocations.types.1.type=int|hirSourceLocations.types.1.location.line=8|hirSourceLocations.types.1.location.column=7|hirSourceLocations.types.2.ownerName=unsignedValue|hirSourceLocations.types.2.type=uint|hirSourceLocations.types.2.location.line=9|hirSourceLocations.types.2.location.column=7|hirSourceLocations.types.2.location.length=4|hirSourceLocations.types.3.ownerName=signedBack|hirSourceLocations.types.3.type=float|hirSourceLocations.types.3.location.line=10|hirSourceLocations.types.4.ownerName=unsignedBack|hirSourceLocations.types.4.type=float|hirSourceLocations.types.4.location.line=11|hirSourceLocations.types.4.location.column=7"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_dump_hir_source_map_vector_local_binary_provenance
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_VECTOR_LOCAL_COMPUTE_SHADER}
    -DSTAGE=hir-source-map
    -DMODE=dump-stage
    "-DSOURCE_MAP_FILTER_ARGS=--source-map-expression-kind|binary"
    "-DEXPECTED_JSON_ARRAY_LENGTHS=hirSourceLocations.expressions=1|hirSourceLocations.types=0|hirSourceLocations.statements=0|categoryCounts.expressionKinds=1|categoryCounts.statementKinds=0|categoryCounts.typeOwnerKinds=0"
    "-DEXPECTED_JSON_FIELDS=schemaVersion=7|filters.activeCount=1|filters.expressionKind=binary|pagination.activeCount=0|categoryCounts.expressionTotalCount=1|categoryCounts.typeTotalCount=0|categoryCounts.statementTotalCount=0|categoryCounts.recordTotalCount=1|categoryCounts.expressionKinds.0.name=binary|categoryCounts.expressionKinds.0.count=1|records.enabled=false|records.totalCount=1|hirSourceLocations.expressionCount=1|hirSourceLocations.expressionWithLocationCount=1|hirSourceLocations.expressions.0.stage=compute|hirSourceLocations.expressions.0.function=main|hirSourceLocations.expressions.0.statementKind=decl|hirSourceLocations.expressions.0.kind=binary|hirSourceLocations.expressions.0.value=+|hirSourceLocations.expressions.0.type=vec4|hirSourceLocations.expressions.0.location.line=8|hirSourceLocations.expressions.0.location.column=27"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_dump_hir_source_map_vector_buffer_binary_provenance
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_VECTOR_BUFFER_COMPUTE_SHADER}
    -DSTAGE=hir-source-map
    -DMODE=dump-stage
    "-DSOURCE_MAP_FILTER_ARGS=--source-map-expression-kind|binary"
    "-DEXPECTED_JSON_ARRAY_LENGTHS=hirSourceLocations.expressions=1|hirSourceLocations.types=0|hirSourceLocations.statements=0|categoryCounts.expressionKinds=1|categoryCounts.statementKinds=0|categoryCounts.typeOwnerKinds=0"
    "-DEXPECTED_JSON_FIELDS=schemaVersion=7|filters.activeCount=1|filters.expressionKind=binary|pagination.activeCount=0|categoryCounts.expressionTotalCount=1|categoryCounts.typeTotalCount=0|categoryCounts.statementTotalCount=0|categoryCounts.recordTotalCount=1|categoryCounts.expressionKinds.0.name=binary|categoryCounts.expressionKinds.0.count=1|records.enabled=false|records.totalCount=1|hirSourceLocations.expressionCount=1|hirSourceLocations.expressionWithLocationCount=1|hirSourceLocations.expressions.0.stage=compute|hirSourceLocations.expressions.0.function=main|hirSourceLocations.expressions.0.statementKind=decl|hirSourceLocations.expressions.0.kind=binary|hirSourceLocations.expressions.0.value=+|hirSourceLocations.expressions.0.type=vec4|hirSourceLocations.expressions.0.location.line=8|hirSourceLocations.expressions.0.location.column=27"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_dump_hir_source_map_vector3_buffer_binary_provenance
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_VECTOR3_BUFFER_COMPUTE_SHADER}
    -DSTAGE=hir-source-map
    -DMODE=dump-stage
    "-DSOURCE_MAP_FILTER_ARGS=--source-map-expression-kind|binary"
    "-DEXPECTED_JSON_ARRAY_LENGTHS=hirSourceLocations.expressions=1|hirSourceLocations.types=0|hirSourceLocations.statements=0|categoryCounts.expressionKinds=1|categoryCounts.statementKinds=0|categoryCounts.typeOwnerKinds=0"
    "-DEXPECTED_JSON_FIELDS=schemaVersion=7|filters.activeCount=1|filters.expressionKind=binary|pagination.activeCount=0|categoryCounts.expressionTotalCount=1|categoryCounts.typeTotalCount=0|categoryCounts.statementTotalCount=0|categoryCounts.recordTotalCount=1|categoryCounts.expressionKinds.0.name=binary|categoryCounts.expressionKinds.0.count=1|records.enabled=false|records.totalCount=1|hirSourceLocations.expressionCount=1|hirSourceLocations.expressionWithLocationCount=1|hirSourceLocations.expressions.0.stage=compute|hirSourceLocations.expressions.0.function=main|hirSourceLocations.expressions.0.statementKind=decl|hirSourceLocations.expressions.0.kind=binary|hirSourceLocations.expressions.0.value=+|hirSourceLocations.expressions.0.type=vec3|hirSourceLocations.expressions.0.location.line=8|hirSourceLocations.expressions.0.location.column=27"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_dump_hir_source_map_struct_field_type_provenance
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_STRUCT_BUFFER_COMPUTE_SHADER}
    -DSTAGE=hir-source-map
    -DMODE=dump-stage
    "-DSOURCE_MAP_FILTER_ARGS=--source-map-owner-kind|field-type"
    "-DEXPECTED_JSON_ARRAY_LENGTHS=hirSourceLocations.expressions=0|hirSourceLocations.types=3|hirSourceLocations.statements=0|categoryCounts.expressionKinds=0|categoryCounts.statementKinds=0|categoryCounts.typeOwnerKinds=1"
    "-DEXPECTED_JSON_FIELDS=schemaVersion=7|filters.activeCount=1|filters.ownerKind=field-type|pagination.activeCount=0|categoryCounts.expressionTotalCount=0|categoryCounts.typeTotalCount=3|categoryCounts.statementTotalCount=0|categoryCounts.recordTotalCount=3|categoryCounts.typeOwnerKinds.0.name=field-type|categoryCounts.typeOwnerKinds.0.count=3|records.enabled=false|records.totalCount=3|hirSourceLocations.expressionCount=0|hirSourceLocations.typeCount=3|hirSourceLocations.typeWithLocationCount=3|hirSourceLocations.statementCount=0|hirSourceLocations.types.0.ownerKind=field-type|hirSourceLocations.types.0.ownerName=Particle.position|hirSourceLocations.types.0.type=vec3|hirSourceLocations.types.0.location.line=3|hirSourceLocations.types.0.location.column=5|hirSourceLocations.types.1.ownerName=Particle.mass|hirSourceLocations.types.1.type=float|hirSourceLocations.types.1.location.line=4|hirSourceLocations.types.2.ownerName=Particle.velocity|hirSourceLocations.types.2.type=vec4|hirSourceLocations.types.2.location.line=5"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_dump_hir_source_map_struct_field_name_provenance
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_STRUCT_NESTED_FIELD_COMPUTE_SHADER}
    -DSTAGE=hir-source-map
    -DMODE=dump-stage
    "-DSOURCE_MAP_FILTER_ARGS=--source-map-owner-kind|field-name|--source-map-owner-name|Particle.transform"
    "-DEXPECTED_JSON_PATHS=hirSourceLocations.types.0.location.file|hirSourceLocations.types.0.location.endOffset"
    "-DEXPECTED_JSON_ARRAY_LENGTHS=hirSourceLocations.expressions=0|hirSourceLocations.types=1|hirSourceLocations.statements=0|categoryCounts.typeOwnerKinds=1"
    "-DEXPECTED_JSON_FIELDS=schemaVersion=7|filters.activeCount=2|filters.ownerKind=field-name|filters.ownerName=Particle.transform|pagination.activeCount=0|categoryCounts.expressionTotalCount=0|categoryCounts.typeTotalCount=1|categoryCounts.statementTotalCount=0|categoryCounts.recordTotalCount=1|categoryCounts.typeOwnerKinds.0.name=field-name|categoryCounts.typeOwnerKinds.0.count=1|records.enabled=false|records.totalCount=1|hirSourceLocations.expressionCount=0|hirSourceLocations.typeCount=1|hirSourceLocations.typeWithLocationCount=1|hirSourceLocations.statementCount=0|hirSourceLocations.types.0.ownerKind=field-name|hirSourceLocations.types.0.ownerName=Particle.transform|hirSourceLocations.types.0.type=Transform|hirSourceLocations.types.0.location.line=7|hirSourceLocations.types.0.location.column=15|hirSourceLocations.types.0.location.length=9"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_dump_hir_source_map_struct_constant_array_field_type_provenance
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_STRUCT_CONSTANT_ARRAY_FIELD_COMPUTE_SHADER}
    -DSTAGE=hir-source-map
    -DMODE=dump-stage
    "-DSOURCE_MAP_FILTER_ARGS=--source-map-owner-kind|field-type|--source-map-owner-name|Particle.weights"
    "-DEXPECTED_JSON_ARRAY_LENGTHS=hirSourceLocations.expressions=0|hirSourceLocations.types=1|hirSourceLocations.statements=0|categoryCounts.typeOwnerKinds=1"
    "-DEXPECTED_JSON_FIELDS=schemaVersion=7|filters.activeCount=2|filters.ownerKind=field-type|filters.ownerName=Particle.weights|pagination.activeCount=0|categoryCounts.expressionTotalCount=0|categoryCounts.typeTotalCount=1|categoryCounts.statementTotalCount=0|categoryCounts.recordTotalCount=1|categoryCounts.typeOwnerKinds.0.name=field-type|categoryCounts.typeOwnerKinds.0.count=1|records.enabled=false|records.totalCount=1|hirSourceLocations.expressionCount=0|hirSourceLocations.typeCount=1|hirSourceLocations.typeWithLocationCount=1|hirSourceLocations.statementCount=0|hirSourceLocations.types.0.ownerKind=field-type|hirSourceLocations.types.0.ownerName=Particle.weights|hirSourceLocations.types.0.type=float[WEIGHT_COUNT]|hirSourceLocations.types.0.location.line=4|hirSourceLocations.types.0.location.column=5|hirSourceLocations.types.0.location.length=5"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_dump_hir_source_map_struct_descriptor_array_member_provenance
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_STORAGE_BUFFER_STRUCT_ARRAY_FIELD_DESCRIPTOR_ARRAY_SHADER}
    -DSTAGE=hir-source-map
    -DMODE=dump-stage
    "-DSOURCE_MAP_FILTER_ARGS=--source-map-expression-kind|member"
    "-DEXPECTED_JSON_ARRAY_LENGTHS=hirSourceLocations.expressions=8|hirSourceLocations.types=0|hirSourceLocations.statements=0|categoryCounts.expressionKinds=1"
    "-DEXPECTED_JSON_FIELDS=schemaVersion=7|filters.activeCount=1|filters.expressionKind=member|pagination.activeCount=0|categoryCounts.expressionTotalCount=8|categoryCounts.typeTotalCount=0|categoryCounts.statementTotalCount=0|categoryCounts.recordTotalCount=8|categoryCounts.expressionKinds.0.name=member|categoryCounts.expressionKinds.0.count=8|records.enabled=false|records.totalCount=8|hirSourceLocations.expressionCount=8|hirSourceLocations.expressionWithLocationCount=8|hirSourceLocations.expressions.0.statementKind=decl|hirSourceLocations.expressions.0.kind=member|hirSourceLocations.expressions.0.value=weights|hirSourceLocations.expressions.0.type=float[4]|hirSourceLocations.expressions.0.location.line=17|hirSourceLocations.expressions.1.value=position|hirSourceLocations.expressions.1.type=vec3|hirSourceLocations.expressions.1.location.line=18|hirSourceLocations.expressions.2.value=history|hirSourceLocations.expressions.2.type=Transform[2]|hirSourceLocations.expressions.2.location.line=18|hirSourceLocations.expressions.4.value=weight|hirSourceLocations.expressions.4.type=float|hirSourceLocations.expressions.4.location.line=20|hirSourceLocations.expressions.6.value=position|hirSourceLocations.expressions.6.statementKind=assign|hirSourceLocations.expressions.6.location.line=21"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_dump_hir_source_map_runtime_struct_array_field_type_provenance
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_RUNTIME_STRUCT_ARRAY_SHADER}
    -DSTAGE=hir-source-map
    -DMODE=dump-stage
    "-DSOURCE_MAP_FILTER_ARGS=--source-map-owner-kind|field-type|--source-map-owner-name|RuntimeStructPayload.particles"
    "-DEXPECTED_JSON_ARRAY_LENGTHS=hirSourceLocations.expressions=0|hirSourceLocations.types=1|hirSourceLocations.statements=0|categoryCounts.typeOwnerKinds=1"
    "-DEXPECTED_JSON_FIELDS=schemaVersion=7|filters.activeCount=2|filters.ownerKind=field-type|filters.ownerName=RuntimeStructPayload.particles|pagination.activeCount=0|categoryCounts.expressionTotalCount=0|categoryCounts.typeTotalCount=1|categoryCounts.statementTotalCount=0|categoryCounts.recordTotalCount=1|categoryCounts.typeOwnerKinds.0.name=field-type|categoryCounts.typeOwnerKinds.0.count=1|records.enabled=false|records.totalCount=1|hirSourceLocations.expressionCount=0|hirSourceLocations.typeCount=1|hirSourceLocations.typeWithLocationCount=1|hirSourceLocations.statementCount=0|hirSourceLocations.types.0.ownerKind=field-type|hirSourceLocations.types.0.ownerName=RuntimeStructPayload.particles|hirSourceLocations.types.0.type=TailParticle[]|hirSourceLocations.types.0.location.line=9|hirSourceLocations.types.0.location.column=5|hirSourceLocations.types.0.location.length=12"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_dump_hir_source_map_runtime_struct_array_member_provenance
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_RUNTIME_STRUCT_ARRAY_SHADER}
    -DSTAGE=hir-source-map
    -DMODE=dump-stage
    "-DSOURCE_MAP_FILTER_ARGS=--source-map-expression-kind|member|--source-map-operation|particles"
    "-DEXPECTED_JSON_ARRAY_LENGTHS=hirSourceLocations.expressions=4|hirSourceLocations.types=0|hirSourceLocations.statements=0|categoryCounts.expressionKinds=1"
    "-DEXPECTED_JSON_FIELDS=schemaVersion=7|filters.activeCount=2|filters.expressionKind=member|filters.expressionValue=particles|pagination.activeCount=0|categoryCounts.expressionTotalCount=4|categoryCounts.typeTotalCount=0|categoryCounts.statementTotalCount=0|categoryCounts.recordTotalCount=4|categoryCounts.expressionKinds.0.name=member|categoryCounts.expressionKinds.0.count=4|records.enabled=false|records.totalCount=4|hirSourceLocations.expressionCount=4|hirSourceLocations.expressionWithLocationCount=4|hirSourceLocations.expressions.0.statementKind=decl|hirSourceLocations.expressions.0.value=particles|hirSourceLocations.expressions.0.type=TailParticle[]|hirSourceLocations.expressions.0.location.line=17|hirSourceLocations.expressions.1.statementKind=decl|hirSourceLocations.expressions.1.value=particles|hirSourceLocations.expressions.1.location.line=18|hirSourceLocations.expressions.2.statementKind=assign|hirSourceLocations.expressions.2.value=particles|hirSourceLocations.expressions.2.location.line=20|hirSourceLocations.expressions.3.statementKind=assign|hirSourceLocations.expressions.3.value=particles|hirSourceLocations.expressions.3.location.line=21"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_dump_hir_source_map_expression_filter
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_TEXTURE_2D_SHADOW_COMPARE_LOD_MANUAL_KERNEL_LIST_SHADER}
    -DSTAGE=hir-source-map
    -DMODE=dump-stage
    "-DSOURCE_MAP_FILTER_ARGS=--source-map-expression-kind|texture_compare_lod_manual|--source-map-operation|textureCompareLodManualKernel"
    "-DEXPECTED_JSON_PATHS=hirSourceLocations.expressions.0.location.length|hirSourceLocations.expressions.0.location.endOffset"
    "-DEXPECTED_JSON_ARRAY_LENGTHS=hirSourceLocations.expressions=1|hirSourceLocations.types=0|hirSourceLocations.statements=0|categoryCounts.statementKinds=0"
    "-DEXPECTED_JSON_FIELDS=schemaVersion=7|filters.activeCount=2|pagination.activeCount=0|categoryCounts.expressionTotalCount=1|categoryCounts.typeTotalCount=0|categoryCounts.statementTotalCount=0|categoryCounts.recordTotalCount=1|categoryCounts.expressionKinds.0.name=texture_compare_lod_manual|categoryCounts.expressionKinds.0.count=1|records.enabled=false|records.totalCount=1|filters.expressionKind=texture_compare_lod_manual|filters.expressionValue=textureCompareLodManualKernel|hirSourceLocations.expressionCount=1|hirSourceLocations.typeCount=0|hirSourceLocations.statementCount=0|hirSourceLocations.expressions.0.kind=texture_compare_lod_manual|hirSourceLocations.expressions.0.value=textureCompareLodManualKernel"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_dump_hir_source_map_texture_compare_lod_manual_compare_op_provenance
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_TEXTURE_2D_SHADOW_COMPARE_LOD_MANUAL_KERNEL_LIST_SHADER}
    -DSTAGE=hir-source-map
    -DMODE=dump-stage
    "-DSOURCE_MAP_FILTER_ARGS=--source-map-expression-kind|identifier|--source-map-operation|less_equal"
    "-DEXPECTED_JSON_PATHS=hirSourceLocations.expressions.0.location.file|hirSourceLocations.expressions.0.location.endOffset"
    "-DEXPECTED_JSON_ARRAY_LENGTHS=hirSourceLocations.expressions=1|hirSourceLocations.types=0|hirSourceLocations.statements=0|categoryCounts.expressionKinds=1|categoryCounts.statementKinds=0|categoryCounts.typeOwnerKinds=0"
    "-DEXPECTED_JSON_FIELDS=schemaVersion=7|filters.activeCount=2|filters.expressionKind=identifier|filters.expressionValue=less_equal|pagination.activeCount=0|categoryCounts.expressionTotalCount=1|categoryCounts.typeTotalCount=0|categoryCounts.statementTotalCount=0|categoryCounts.recordTotalCount=1|categoryCounts.expressionKinds.0.name=identifier|categoryCounts.expressionKinds.0.count=1|records.enabled=false|records.totalCount=1|hirSourceLocations.expressionCount=1|hirSourceLocations.expressionWithLocationCount=1|hirSourceLocations.typeCount=0|hirSourceLocations.statementCount=0|hirSourceLocations.expressions.0.index=8|hirSourceLocations.expressions.0.stage=compute|hirSourceLocations.expressions.0.function=main|hirSourceLocations.expressions.0.statementKind=decl|hirSourceLocations.expressions.0.kind=identifier|hirSourceLocations.expressions.0.value=less_equal|hirSourceLocations.expressions.0.location.line=12|hirSourceLocations.expressions.0.location.column=15|hirSourceLocations.expressions.0.location.length=10|hirSourceLocations.expressions.0.location.endLine=12|hirSourceLocations.expressions.0.location.endColumn=25"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_dump_hir_source_map_texture_only_nonuniform_sample_expression_provenance
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_TEXTURE_ONLY_NONUNIFORM_DESCRIPTOR_ARRAY_SAMPLE_SHADER}
    -DSTAGE=hir-source-map
    -DMODE=dump-stage
    "-DSOURCE_MAP_FILTER_ARGS=--source-map-expression-kind|texture_sample|--source-map-operation|textureLod"
    "-DEXPECTED_JSON_PATHS=hirSourceLocations.expressions.0.location.file|hirSourceLocations.expressions.0.location.endOffset"
    "-DEXPECTED_JSON_ARRAY_LENGTHS=hirSourceLocations.expressions=1|hirSourceLocations.types=0|hirSourceLocations.statements=0|categoryCounts.expressionKinds=1|categoryCounts.statementKinds=0|categoryCounts.typeOwnerKinds=0"
    "-DEXPECTED_JSON_FIELDS=schemaVersion=7|filters.activeCount=2|filters.expressionKind=texture_sample|filters.expressionValue=textureLod|pagination.activeCount=0|categoryCounts.expressionTotalCount=1|categoryCounts.typeTotalCount=0|categoryCounts.statementTotalCount=0|categoryCounts.recordTotalCount=1|categoryCounts.expressionKinds.0.name=texture_sample|categoryCounts.expressionKinds.0.count=1|records.enabled=false|records.totalCount=1|hirSourceLocations.expressionCount=1|hirSourceLocations.expressionWithLocationCount=1|hirSourceLocations.expressions.0.kind=texture_sample|hirSourceLocations.expressions.0.value=textureLod|hirSourceLocations.expressions.0.type=vec4|hirSourceLocations.expressions.0.location.line=12|hirSourceLocations.expressions.0.location.column=20|hirSourceLocations.expressions.0.location.length=10"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_dump_hir_source_map_texture_only_nonuniform_descriptor_index_marker_provenance
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_TEXTURE_ONLY_NONUNIFORM_DESCRIPTOR_ARRAY_SAMPLE_SHADER}
    -DSTAGE=hir-source-map
    -DMODE=dump-stage
    "-DSOURCE_MAP_FILTER_ARGS=--source-map-expression-kind|nonuniform"
    "-DEXPECTED_JSON_PATHS=hirSourceLocations.expressions.0.location.file|hirSourceLocations.expressions.0.location.endOffset"
    "-DEXPECTED_JSON_ARRAY_LENGTHS=hirSourceLocations.expressions=1|hirSourceLocations.types=0|hirSourceLocations.statements=0|categoryCounts.expressionKinds=1|categoryCounts.statementKinds=0|categoryCounts.typeOwnerKinds=0"
    "-DEXPECTED_JSON_FIELDS=schemaVersion=7|filters.activeCount=1|filters.expressionKind=nonuniform|pagination.activeCount=0|categoryCounts.expressionTotalCount=1|categoryCounts.recordTotalCount=1|categoryCounts.expressionKinds.0.name=nonuniform|categoryCounts.expressionKinds.0.count=1|records.enabled=false|records.totalCount=1|hirSourceLocations.expressionCount=1|hirSourceLocations.expressionWithLocationCount=1|hirSourceLocations.expressions.0.index=7|hirSourceLocations.expressions.0.kind=nonuniform|hirSourceLocations.expressions.0.value=nonuniform|hirSourceLocations.expressions.0.type=int|hirSourceLocations.expressions.0.location.line=12|hirSourceLocations.expressions.0.location.column=41|hirSourceLocations.expressions.0.location.length=10"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_dump_hir_source_map_texture_sample_explicit_lod_operand_provenance
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_TEXTURE_ONLY_NONUNIFORM_DESCRIPTOR_ARRAY_SAMPLE_SHADER}
    -DSTAGE=hir-source-map
    -DMODE=dump-stage
    "-DSOURCE_MAP_FILTER_ARGS=--source-map-expression-kind|literal|--source-map-operation|0.0"
    "-DEXPECTED_JSON_PATHS=hirSourceLocations.expressions.0.location.file|hirSourceLocations.expressions.0.location.endOffset"
    "-DEXPECTED_JSON_ARRAY_LENGTHS=hirSourceLocations.expressions=1|hirSourceLocations.types=0|hirSourceLocations.statements=0|categoryCounts.expressionKinds=1|categoryCounts.statementKinds=0|categoryCounts.typeOwnerKinds=0"
    "-DEXPECTED_JSON_FIELDS=schemaVersion=7|filters.activeCount=2|filters.expressionKind=literal|filters.expressionValue=0.0|pagination.activeCount=0|categoryCounts.expressionTotalCount=1|categoryCounts.recordTotalCount=1|categoryCounts.expressionKinds.0.name=literal|categoryCounts.expressionKinds.0.count=1|records.enabled=false|records.totalCount=1|hirSourceLocations.expressionCount=1|hirSourceLocations.expressionWithLocationCount=1|hirSourceLocations.expressions.0.index=13|hirSourceLocations.expressions.0.kind=literal|hirSourceLocations.expressions.0.value=0.0|hirSourceLocations.expressions.0.type=float|hirSourceLocations.expressions.0.location.line=13|hirSourceLocations.expressions.0.location.column=62|hirSourceLocations.expressions.0.location.length=3"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_dump_hir_source_map_sampler_only_nonuniform_descriptor_index_marker_provenance
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_SAMPLER_ONLY_NONUNIFORM_DESCRIPTOR_ARRAY_SAMPLE_SHADER}
    -DSTAGE=hir-source-map
    -DMODE=dump-stage
    "-DSOURCE_MAP_FILTER_ARGS=--source-map-expression-kind|nonuniform"
    "-DEXPECTED_JSON_PATHS=hirSourceLocations.expressions.0.location.file|hirSourceLocations.expressions.0.location.endOffset"
    "-DEXPECTED_JSON_ARRAY_LENGTHS=hirSourceLocations.expressions=1|hirSourceLocations.types=0|hirSourceLocations.statements=0|categoryCounts.expressionKinds=1|categoryCounts.statementKinds=0|categoryCounts.typeOwnerKinds=0"
    "-DEXPECTED_JSON_FIELDS=schemaVersion=7|filters.activeCount=1|filters.expressionKind=nonuniform|pagination.activeCount=0|categoryCounts.expressionTotalCount=1|categoryCounts.recordTotalCount=1|categoryCounts.expressionKinds.0.name=nonuniform|categoryCounts.expressionKinds.0.count=1|records.enabled=false|records.totalCount=1|hirSourceLocations.expressionCount=1|hirSourceLocations.expressionWithLocationCount=1|hirSourceLocations.expressions.0.index=8|hirSourceLocations.expressions.0.kind=nonuniform|hirSourceLocations.expressions.0.value=nonuniform|hirSourceLocations.expressions.0.type=int|hirSourceLocations.expressions.0.location.line=13|hirSourceLocations.expressions.0.location.column=46|hirSourceLocations.expressions.0.location.length=10"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_dump_hir_source_map_texture_compare_nonuniform_descriptor_markers_provenance
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_TEXTURE_COMPARE_NONUNIFORM_DESCRIPTOR_ARRAY_SHADER}
    -DSTAGE=hir-source-map
    -DMODE=dump-stage
    "-DSOURCE_MAP_FILTER_ARGS=--source-map-expression-kind|nonuniform"
    "-DEXPECTED_JSON_PATHS=hirSourceLocations.expressions.0.location.file|hirSourceLocations.expressions.1.location.endOffset"
    "-DEXPECTED_JSON_ARRAY_LENGTHS=hirSourceLocations.expressions=2|hirSourceLocations.types=0|hirSourceLocations.statements=0|categoryCounts.expressionKinds=1|categoryCounts.statementKinds=0|categoryCounts.typeOwnerKinds=0"
    "-DEXPECTED_JSON_FIELDS=schemaVersion=7|filters.activeCount=1|filters.expressionKind=nonuniform|pagination.activeCount=0|categoryCounts.expressionTotalCount=2|categoryCounts.recordTotalCount=2|categoryCounts.expressionKinds.0.name=nonuniform|categoryCounts.expressionKinds.0.count=2|records.enabled=false|records.totalCount=2|hirSourceLocations.expressionCount=2|hirSourceLocations.expressionWithLocationCount=2|hirSourceLocations.expressions.0.index=7|hirSourceLocations.expressions.0.location.line=12|hirSourceLocations.expressions.0.location.column=37|hirSourceLocations.expressions.1.index=11|hirSourceLocations.expressions.1.location.line=13|hirSourceLocations.expressions.1.location.column=41"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_dump_hir_source_map_texture_compare_lod_nonuniform_expression_provenance
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_TEXTURE_COMPARE_NONUNIFORM_DESCRIPTOR_ARRAY_LOD_SHADER}
    -DSTAGE=hir-source-map
    -DMODE=dump-stage
    "-DSOURCE_MAP_FILTER_ARGS=--source-map-expression-kind|texture_compare|--source-map-operation|textureCompareLod"
    "-DEXPECTED_JSON_PATHS=hirSourceLocations.expressions.0.location.file|hirSourceLocations.expressions.0.location.endOffset"
    "-DEXPECTED_JSON_ARRAY_LENGTHS=hirSourceLocations.expressions=1|hirSourceLocations.types=0|hirSourceLocations.statements=0|categoryCounts.expressionKinds=1|categoryCounts.statementKinds=0|categoryCounts.typeOwnerKinds=0"
    "-DEXPECTED_JSON_FIELDS=schemaVersion=7|filters.activeCount=2|filters.expressionKind=texture_compare|filters.expressionValue=textureCompareLod|pagination.activeCount=0|categoryCounts.expressionTotalCount=1|categoryCounts.recordTotalCount=1|categoryCounts.expressionKinds.0.name=texture_compare|categoryCounts.expressionKinds.0.count=1|records.enabled=false|records.totalCount=1|hirSourceLocations.expressionCount=1|hirSourceLocations.expressionWithLocationCount=1|hirSourceLocations.expressions.0.index=4|hirSourceLocations.expressions.0.kind=texture_compare|hirSourceLocations.expressions.0.value=textureCompareLod|hirSourceLocations.expressions.0.type=float|hirSourceLocations.expressions.0.location.line=12|hirSourceLocations.expressions.0.location.column=11|hirSourceLocations.expressions.0.location.length=17"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_dump_hir_source_map_texture_compare_lod_explicit_lod_operand_provenance
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_TEXTURE_COMPARE_NONUNIFORM_DESCRIPTOR_ARRAY_LOD_SHADER}
    -DSTAGE=hir-source-map
    -DMODE=dump-stage
    "-DSOURCE_MAP_FILTER_ARGS=--source-map-expression-kind|literal|--source-map-operation|2.0"
    "-DEXPECTED_JSON_PATHS=hirSourceLocations.expressions.0.location.file|hirSourceLocations.expressions.0.location.endOffset"
    "-DEXPECTED_JSON_ARRAY_LENGTHS=hirSourceLocations.expressions=1|hirSourceLocations.types=0|hirSourceLocations.statements=0|categoryCounts.expressionKinds=1|categoryCounts.statementKinds=0|categoryCounts.typeOwnerKinds=0"
    "-DEXPECTED_JSON_FIELDS=schemaVersion=7|filters.activeCount=2|filters.expressionKind=literal|filters.expressionValue=2.0|pagination.activeCount=0|categoryCounts.expressionTotalCount=1|categoryCounts.recordTotalCount=1|categoryCounts.expressionKinds.0.name=literal|categoryCounts.expressionKinds.0.count=1|records.enabled=false|records.totalCount=1|hirSourceLocations.expressionCount=1|hirSourceLocations.expressionWithLocationCount=1|hirSourceLocations.expressions.0.index=17|hirSourceLocations.expressions.0.kind=literal|hirSourceLocations.expressions.0.value=2.0|hirSourceLocations.expressions.0.type=float|hirSourceLocations.expressions.0.location.line=14|hirSourceLocations.expressions.0.location.column=51|hirSourceLocations.expressions.0.location.length=3"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_dump_hir_source_map_texture_compare_lod_manual_nonuniform_descriptor_markers_provenance
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_TEXTURE_COMPARE_LOD_MANUAL_NONUNIFORM_DESCRIPTOR_ARRAY_SHADER}
    -DSTAGE=hir-source-map
    -DMODE=dump-stage
    "-DSOURCE_MAP_FILTER_ARGS=--source-map-expression-kind|nonuniform"
    "-DEXPECTED_JSON_PATHS=hirSourceLocations.expressions.0.location.file|hirSourceLocations.expressions.1.location.endOffset"
    "-DEXPECTED_JSON_ARRAY_LENGTHS=hirSourceLocations.expressions=2|hirSourceLocations.types=0|hirSourceLocations.statements=0|categoryCounts.expressionKinds=1|categoryCounts.statementKinds=0|categoryCounts.typeOwnerKinds=0"
    "-DEXPECTED_JSON_FIELDS=schemaVersion=7|filters.activeCount=1|filters.expressionKind=nonuniform|pagination.activeCount=0|categoryCounts.expressionTotalCount=2|categoryCounts.recordTotalCount=2|categoryCounts.expressionKinds.0.name=nonuniform|categoryCounts.expressionKinds.0.count=2|records.enabled=false|records.totalCount=2|hirSourceLocations.expressionCount=2|hirSourceLocations.expressionWithLocationCount=2|hirSourceLocations.expressions.0.index=8|hirSourceLocations.expressions.0.location.line=15|hirSourceLocations.expressions.0.location.column=49|hirSourceLocations.expressions.1.index=12|hirSourceLocations.expressions.1.location.line=16|hirSourceLocations.expressions.1.location.column=53"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_dump_hir_source_map_texture_compare_lod_manual_explicit_lod_operand_provenance
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_TEXTURE_COMPARE_LOD_MANUAL_NONUNIFORM_DESCRIPTOR_ARRAY_SHADER}
    -DSTAGE=hir-source-map
    -DMODE=dump-stage
    "-DSOURCE_MAP_FILTER_ARGS=--source-map-expression-kind|literal|--source-map-operation|2.0"
    "-DEXPECTED_JSON_PATHS=hirSourceLocations.expressions.0.location.file|hirSourceLocations.expressions.0.location.endOffset"
    "-DEXPECTED_JSON_ARRAY_LENGTHS=hirSourceLocations.expressions=1|hirSourceLocations.types=0|hirSourceLocations.statements=0|categoryCounts.expressionKinds=1|categoryCounts.statementKinds=0|categoryCounts.typeOwnerKinds=0"
    "-DEXPECTED_JSON_FIELDS=schemaVersion=7|filters.activeCount=2|filters.expressionKind=literal|filters.expressionValue=2.0|pagination.activeCount=0|categoryCounts.expressionTotalCount=1|categoryCounts.recordTotalCount=1|categoryCounts.expressionKinds.0.name=literal|categoryCounts.expressionKinds.0.count=1|records.enabled=false|records.totalCount=1|hirSourceLocations.expressionCount=1|hirSourceLocations.expressionWithLocationCount=1|hirSourceLocations.expressions.0.index=19|hirSourceLocations.expressions.0.kind=literal|hirSourceLocations.expressions.0.value=2.0|hirSourceLocations.expressions.0.type=float|hirSourceLocations.expressions.0.location.line=17|hirSourceLocations.expressions.0.location.column=63|hirSourceLocations.expressions.0.location.length=3"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_dump_hir_source_map_texture_compare_lod_manual_descriptor_array_compare_op_provenance
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_TEXTURE_COMPARE_LOD_MANUAL_DESCRIPTOR_ARRAY_SHADER}
    -DSTAGE=hir-source-map
    -DMODE=dump-stage
    "-DSOURCE_MAP_FILTER_ARGS=--source-map-expression-kind|identifier|--source-map-operation|less_equal"
    "-DEXPECTED_JSON_PATHS=hirSourceLocations.expressions.0.location.file|hirSourceLocations.expressions.0.location.endOffset"
    "-DEXPECTED_JSON_ARRAY_LENGTHS=hirSourceLocations.expressions=1|hirSourceLocations.types=0|hirSourceLocations.statements=0|categoryCounts.expressionKinds=1|categoryCounts.statementKinds=0|categoryCounts.typeOwnerKinds=0"
    "-DEXPECTED_JSON_FIELDS=schemaVersion=7|filters.activeCount=2|filters.expressionKind=identifier|filters.expressionValue=less_equal|pagination.activeCount=0|categoryCounts.expressionTotalCount=1|categoryCounts.recordTotalCount=1|categoryCounts.expressionKinds.0.name=identifier|categoryCounts.expressionKinds.0.count=1|records.enabled=false|records.totalCount=1|hirSourceLocations.expressionCount=1|hirSourceLocations.expressionWithLocationCount=1|hirSourceLocations.expressions.0.index=15|hirSourceLocations.expressions.0.kind=identifier|hirSourceLocations.expressions.0.value=less_equal|hirSourceLocations.expressions.0.location.line=15|hirSourceLocations.expressions.0.location.column=35|hirSourceLocations.expressions.0.location.length=10"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_dump_hir_source_map_texture_compare_lod_manual_kernel_tap_list_operand_provenance
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_TEXTURE_2D_SHADOW_COMPARE_LOD_MANUAL_KERNEL_LIST_SHADER}
    -DSTAGE=hir-source-map
    -DMODE=dump-stage
    "-DSOURCE_MAP_FILTER_ARGS=--source-map-expression-kind|call|--source-map-operation|textureCompareKernel"
    "-DEXPECTED_JSON_PATHS=hirSourceLocations.expressions.0.location.file|hirSourceLocations.expressions.0.location.endOffset"
    "-DEXPECTED_JSON_ARRAY_LENGTHS=hirSourceLocations.expressions=1|hirSourceLocations.types=0|hirSourceLocations.statements=0|categoryCounts.expressionKinds=1|categoryCounts.statementKinds=0|categoryCounts.typeOwnerKinds=0"
    "-DEXPECTED_JSON_FIELDS=schemaVersion=7|filters.activeCount=2|filters.expressionKind=call|filters.expressionValue=textureCompareKernel|pagination.activeCount=0|categoryCounts.expressionTotalCount=1|categoryCounts.recordTotalCount=1|categoryCounts.expressionKinds.0.name=call|categoryCounts.expressionKinds.0.count=1|records.enabled=false|records.totalCount=1|hirSourceLocations.expressionCount=1|hirSourceLocations.expressionWithLocationCount=1|hirSourceLocations.expressions.0.index=9|hirSourceLocations.expressions.0.kind=call|hirSourceLocations.expressions.0.value=textureCompareKernel|hirSourceLocations.expressions.0.location.line=13|hirSourceLocations.expressions.0.location.column=15|hirSourceLocations.expressions.0.location.length=20"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_dump_hir_source_map_comparison_sampler_role_resource_type_provenance
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_COMPARISON_SAMPLER_ROLE_SHADER}
    -DSTAGE=hir-source-map
    -DMODE=dump-stage
    "-DSOURCE_MAP_FILTER_ARGS=--source-map-owner-kind|resource-type"
    "-DEXPECTED_JSON_PATHS=hirSourceLocations.types.2.location.file|hirSourceLocations.types.4.location.endOffset"
    "-DEXPECTED_JSON_ARRAY_LENGTHS=hirSourceLocations.expressions=0|hirSourceLocations.types=5|hirSourceLocations.statements=0|categoryCounts.expressionKinds=0|categoryCounts.statementKinds=0|categoryCounts.typeOwnerKinds=1"
    "-DEXPECTED_JSON_FIELDS=schemaVersion=7|filters.activeCount=1|filters.ownerKind=resource-type|pagination.activeCount=0|categoryCounts.expressionTotalCount=0|categoryCounts.typeTotalCount=5|categoryCounts.statementTotalCount=0|categoryCounts.recordTotalCount=5|categoryCounts.typeOwnerKinds.0.name=resource-type|categoryCounts.typeOwnerKinds.0.count=5|records.enabled=false|records.totalCount=5|hirSourceLocations.typeCount=5|hirSourceLocations.typeWithLocationCount=5|hirSourceLocations.types.1.ownerName=shadowMap|hirSourceLocations.types.1.type=sampler2DShadow|hirSourceLocations.types.2.ownerName=shadowCompareSamplers|hirSourceLocations.types.2.type=comparison_sampler[2]|hirSourceLocations.types.3.ownerName=colorMap|hirSourceLocations.types.3.type=sampler2D|hirSourceLocations.types.4.ownerName=linearSampler|hirSourceLocations.types.4.type=sampler"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_dump_hir_source_map_function_parameter_array_parameter_type_provenance
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_FUNCTION_PARAMETER_ARRAY_SHADER}
    -DSTAGE=hir-source-map
    -DMODE=dump-stage
    "-DSOURCE_MAP_FILTER_ARGS=--source-map-owner-kind|parameter-type|--source-map-owner-name|grid"
    "-DEXPECTED_JSON_PATHS=hirSourceLocations.types.0.location.file|hirSourceLocations.types.0.location.endOffset"
    "-DEXPECTED_JSON_ARRAY_LENGTHS=hirSourceLocations.expressions=0|hirSourceLocations.types=1|hirSourceLocations.statements=0|categoryCounts.expressionKinds=0|categoryCounts.statementKinds=0|categoryCounts.typeOwnerKinds=1"
    "-DEXPECTED_JSON_FIELDS=schemaVersion=7|filters.activeCount=2|filters.ownerKind=parameter-type|filters.ownerName=grid|categoryCounts.expressionTotalCount=0|categoryCounts.typeTotalCount=1|categoryCounts.statementTotalCount=0|categoryCounts.recordTotalCount=1|categoryCounts.typeOwnerKinds.0.name=parameter-type|categoryCounts.typeOwnerKinds.0.count=1|records.enabled=false|records.totalCount=1|hirSourceLocations.expressionCount=0|hirSourceLocations.typeCount=1|hirSourceLocations.typeWithLocationCount=1|hirSourceLocations.statementCount=0|hirSourceLocations.types.0.stage=compute|hirSourceLocations.types.0.function=main|hirSourceLocations.types.0.ownerKind=parameter-type|hirSourceLocations.types.0.ownerName=grid|hirSourceLocations.types.0.type=vec4[ROWS][COLS]|hirSourceLocations.types.0.location.line=36|hirSourceLocations.types.0.location.column=96"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_dump_hir_source_map_function_parameter_array_entry_parameter_name_provenance
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_FUNCTION_PARAMETER_ARRAY_SHADER}
    -DSTAGE=hir-source-map
    -DMODE=dump-stage
    "-DSOURCE_MAP_FILTER_ARGS=--source-map-function|main|--source-map-owner-kind|parameter-name|--source-map-owner-name|grid"
    "-DEXPECTED_JSON_PATHS=hirSourceLocations.types.0.location.file|hirSourceLocations.types.0.location.endOffset"
    "-DEXPECTED_JSON_ARRAY_LENGTHS=hirSourceLocations.expressions=0|hirSourceLocations.types=1|hirSourceLocations.statements=0|categoryCounts.typeOwnerKinds=1"
    "-DEXPECTED_JSON_FIELDS=schemaVersion=7|filters.activeCount=3|filters.function=main|filters.ownerKind=parameter-name|filters.ownerName=grid|categoryCounts.expressionTotalCount=0|categoryCounts.typeTotalCount=1|categoryCounts.statementTotalCount=0|categoryCounts.recordTotalCount=1|categoryCounts.typeOwnerKinds.0.name=parameter-name|categoryCounts.typeOwnerKinds.0.count=1|records.enabled=false|records.totalCount=1|hirSourceLocations.expressionCount=0|hirSourceLocations.typeCount=1|hirSourceLocations.typeWithLocationCount=1|hirSourceLocations.statementCount=0|hirSourceLocations.types.0.stage=compute|hirSourceLocations.types.0.function=main|hirSourceLocations.types.0.ownerKind=parameter-name|hirSourceLocations.types.0.ownerName=grid|hirSourceLocations.types.0.type=vec4[ROWS][COLS]|hirSourceLocations.types.0.location.line=36|hirSourceLocations.types.0.location.column=101|hirSourceLocations.types.0.location.length=4"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_dump_hir_source_map_function_parameter_array_call_provenance
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_FUNCTION_PARAMETER_ARRAY_SHADER}
    -DSTAGE=hir-source-map
    -DMODE=dump-stage
    "-DSOURCE_MAP_FILTER_ARGS=--source-map-expression-kind|call|--source-map-operation|consumeGrid"
    "-DEXPECTED_JSON_PATHS=hirSourceLocations.expressions.0.location.file|hirSourceLocations.expressions.1.location.endOffset"
    "-DEXPECTED_JSON_ARRAY_LENGTHS=hirSourceLocations.expressions=2|hirSourceLocations.types=0|hirSourceLocations.statements=0|categoryCounts.expressionKinds=1|categoryCounts.statementKinds=0|categoryCounts.typeOwnerKinds=0"
    "-DEXPECTED_JSON_FIELDS=schemaVersion=7|filters.activeCount=2|filters.expressionKind=call|filters.expressionValue=consumeGrid|categoryCounts.expressionTotalCount=2|categoryCounts.recordTotalCount=2|categoryCounts.expressionKinds.0.name=call|categoryCounts.expressionKinds.0.count=2|records.enabled=false|records.totalCount=2|hirSourceLocations.expressionCount=2|hirSourceLocations.expressionWithLocationCount=2|hirSourceLocations.typeCount=0|hirSourceLocations.statementCount=0|hirSourceLocations.expressions.0.function=main|hirSourceLocations.expressions.0.statementKind=expr|hirSourceLocations.expressions.0.kind=call|hirSourceLocations.expressions.0.value=consumeGrid|hirSourceLocations.expressions.0.location.line=40|hirSourceLocations.expressions.1.value=consumeGrid|hirSourceLocations.expressions.1.location.line=43"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_dump_hir_source_map_local_function_parameter_array_parameter_type_provenance
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_LOCAL_FUNCTION_PARAMETER_ARRAY_SHADER}
    -DSTAGE=hir-source-map
    -DMODE=dump-stage
    "-DSOURCE_MAP_FILTER_ARGS=--source-map-owner-kind|parameter-type|--source-map-owner-name|values"
    "-DEXPECTED_JSON_PATHS=hirSourceLocations.types.0.location.file|hirSourceLocations.types.0.location.endOffset"
    "-DEXPECTED_JSON_ARRAY_LENGTHS=hirSourceLocations.expressions=0|hirSourceLocations.types=1|hirSourceLocations.statements=0|categoryCounts.typeOwnerKinds=1"
    "-DEXPECTED_JSON_FIELDS=schemaVersion=7|filters.activeCount=2|filters.ownerKind=parameter-type|filters.ownerName=values|categoryCounts.typeTotalCount=1|categoryCounts.recordTotalCount=1|categoryCounts.typeOwnerKinds.0.name=parameter-type|categoryCounts.typeOwnerKinds.0.count=1|records.enabled=false|records.totalCount=1|hirSourceLocations.typeCount=1|hirSourceLocations.typeWithLocationCount=1|hirSourceLocations.types.0.function=readWeight|hirSourceLocations.types.0.ownerKind=parameter-type|hirSourceLocations.types.0.ownerName=values|hirSourceLocations.types.0.type=float[COUNT]|hirSourceLocations.types.0.location.line=7|hirSourceLocations.types.0.location.column=22"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_dump_hir_source_map_function_parameter_array_helper_parameter_name_provenance
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_FUNCTION_PARAMETER_ARRAY_SHADER}
    -DSTAGE=hir-source-map
    -DMODE=dump-stage
    "-DSOURCE_MAP_FILTER_ARGS=--source-map-function|consumeGrid|--source-map-owner-kind|parameter-name|--source-map-owner-name|values"
    "-DEXPECTED_JSON_PATHS=hirSourceLocations.types.0.location.file|hirSourceLocations.types.0.location.endOffset"
    "-DEXPECTED_JSON_ARRAY_LENGTHS=hirSourceLocations.expressions=0|hirSourceLocations.types=1|hirSourceLocations.statements=0|categoryCounts.typeOwnerKinds=1"
    "-DEXPECTED_JSON_FIELDS=schemaVersion=7|filters.activeCount=3|filters.function=consumeGrid|filters.ownerKind=parameter-name|filters.ownerName=values|categoryCounts.typeTotalCount=1|categoryCounts.recordTotalCount=1|categoryCounts.typeOwnerKinds.0.name=parameter-name|categoryCounts.typeOwnerKinds.0.count=1|records.enabled=false|records.totalCount=1|hirSourceLocations.typeCount=1|hirSourceLocations.typeWithLocationCount=1|hirSourceLocations.types.0.function=consumeGrid|hirSourceLocations.types.0.ownerKind=parameter-name|hirSourceLocations.types.0.ownerName=values|hirSourceLocations.types.0.type=vec4[ROWS][COLS]|hirSourceLocations.types.0.location.line=31|hirSourceLocations.types.0.location.column=27|hirSourceLocations.types.0.location.length=6"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_dump_hir_source_map_local_function_parameter_array_decl_call_provenance
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_LOCAL_FUNCTION_PARAMETER_ARRAY_SHADER}
    -DSTAGE=hir-source-map
    -DMODE=dump-stage
    "-DSOURCE_MAP_FILTER_ARGS=--source-map-statement-kind|decl"
    "-DEXPECTED_JSON_PATHS=hirSourceLocations.statements.0.location.file|hirSourceLocations.expressions.2.location.endOffset"
    "-DEXPECTED_JSON_ARRAY_LENGTHS=hirSourceLocations.expressions=5|hirSourceLocations.types=0|hirSourceLocations.statements=2|categoryCounts.expressionKinds=4|categoryCounts.statementKinds=1|categoryCounts.typeOwnerKinds=0"
    "-DEXPECTED_JSON_FIELDS=schemaVersion=7|filters.activeCount=1|filters.statementKind=decl|categoryCounts.expressionTotalCount=5|categoryCounts.statementTotalCount=2|categoryCounts.recordTotalCount=7|categoryCounts.expressionKinds.1.name=call|categoryCounts.expressionKinds.1.count=1|categoryCounts.statementKinds.0.name=decl|categoryCounts.statementKinds.0.count=2|records.enabled=false|records.totalCount=7|hirSourceLocations.expressionCount=5|hirSourceLocations.statementCount=2|hirSourceLocations.statements.0.name=weights|hirSourceLocations.statements.0.location.line=12|hirSourceLocations.statements.1.name=first|hirSourceLocations.statements.1.location.line=13|hirSourceLocations.expressions.1.kind=call|hirSourceLocations.expressions.1.value=readWeight|hirSourceLocations.expressions.1.location.line=13|hirSourceLocations.expressions.2.kind=identifier|hirSourceLocations.expressions.2.value=weights|hirSourceLocations.expressions.2.type=float[COUNT]"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_dump_hir_source_map_local_array_mutation_main_assign_provenance
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_LOCAL_ARRAY_MUTATION_HIR_SHADER}
    -DSTAGE=hir-source-map
    -DMODE=dump-stage
    "-DSOURCE_MAP_FILTER_ARGS=--source-map-function|main|--source-map-statement-kind|assign"
    "-DEXPECTED_JSON_PATHS=hirSourceLocations.statements.0.location.file|hirSourceLocations.expressions.0.location.endOffset"
    "-DEXPECTED_JSON_ARRAY_LENGTHS=hirSourceLocations.expressions=16|hirSourceLocations.types=0|hirSourceLocations.statements=3|categoryCounts.expressionKinds=3|categoryCounts.statementKinds=1|categoryCounts.typeOwnerKinds=0"
    "-DEXPECTED_JSON_FIELDS=schemaVersion=7|filters.activeCount=2|filters.function=main|filters.statementKind=assign|categoryCounts.expressionTotalCount=16|categoryCounts.statementTotalCount=3|categoryCounts.recordTotalCount=19|categoryCounts.expressionKinds.1.name=index|categoryCounts.expressionKinds.1.count=5|categoryCounts.statementKinds.0.name=assign|categoryCounts.statementKinds.0.count=3|records.enabled=false|records.totalCount=19|hirSourceLocations.expressionCount=16|hirSourceLocations.statementCount=3|hirSourceLocations.statements.0.function=main|hirSourceLocations.statements.0.statementKind=assign|hirSourceLocations.statements.0.location.line=15|hirSourceLocations.statements.1.location.line=16|hirSourceLocations.statements.2.name=first|hirSourceLocations.statements.2.location.line=18|hirSourceLocations.expressions.1.kind=identifier|hirSourceLocations.expressions.1.value=weights|hirSourceLocations.expressions.1.type=float[COUNT]|hirSourceLocations.expressions.7.value=weights|hirSourceLocations.expressions.7.type=float[COUNT]"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_dump_hir_source_map_local_array_mutation_helper_assign_provenance
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_LOCAL_ARRAY_MUTATION_HIR_SHADER}
    -DSTAGE=hir-source-map
    -DMODE=dump-stage
    "-DSOURCE_MAP_FILTER_ARGS=--source-map-function|rewriteWeight|--source-map-statement-kind|assign"
    "-DEXPECTED_JSON_PATHS=hirSourceLocations.statements.0.location.file|hirSourceLocations.expressions.5.location.endOffset"
    "-DEXPECTED_JSON_ARRAY_LENGTHS=hirSourceLocations.expressions=6|hirSourceLocations.types=0|hirSourceLocations.statements=1|categoryCounts.expressionKinds=3|categoryCounts.statementKinds=1|categoryCounts.typeOwnerKinds=0"
    "-DEXPECTED_JSON_FIELDS=schemaVersion=7|filters.activeCount=2|filters.function=rewriteWeight|filters.statementKind=assign|categoryCounts.expressionTotalCount=6|categoryCounts.statementTotalCount=1|categoryCounts.recordTotalCount=7|categoryCounts.expressionKinds.0.name=identifier|categoryCounts.expressionKinds.0.count=2|categoryCounts.expressionKinds.1.name=index|categoryCounts.expressionKinds.1.count=2|categoryCounts.statementKinds.0.name=assign|categoryCounts.statementKinds.0.count=1|records.enabled=false|records.totalCount=7|hirSourceLocations.expressionCount=6|hirSourceLocations.statementCount=1|hirSourceLocations.statements.0.function=rewriteWeight|hirSourceLocations.statements.0.statementKind=assign|hirSourceLocations.statements.0.location.line=9|hirSourceLocations.expressions.1.kind=identifier|hirSourceLocations.expressions.1.value=samples|hirSourceLocations.expressions.1.type=float[COUNT]|hirSourceLocations.expressions.4.kind=identifier|hirSourceLocations.expressions.4.value=samples|hirSourceLocations.expressions.4.type=float[COUNT]"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_dump_hir_source_map_folded_nested_array_constants_provenance
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_FOLDED_NESTED_ARRAY_HIR_SHADER}
    -DSTAGE=hir-source-map
    -DMODE=dump-stage
    "-DSOURCE_MAP_FILTER_ARGS=--source-map-owner-kind|constant-type"
    "-DEXPECTED_JSON_PATHS=hirSourceLocations.types.0.location.file|hirSourceLocations.types.2.location.endOffset"
    "-DEXPECTED_JSON_ARRAY_LENGTHS=hirSourceLocations.expressions=0|hirSourceLocations.types=3|hirSourceLocations.statements=0|categoryCounts.expressionKinds=0|categoryCounts.statementKinds=0|categoryCounts.typeOwnerKinds=1"
    "-DEXPECTED_JSON_FIELDS=schemaVersion=7|filters.activeCount=1|filters.ownerKind=constant-type|categoryCounts.expressionTotalCount=0|categoryCounts.typeTotalCount=3|categoryCounts.statementTotalCount=0|categoryCounts.recordTotalCount=3|categoryCounts.typeOwnerKinds.0.name=constant-type|categoryCounts.typeOwnerKinds.0.count=3|records.enabled=false|records.totalCount=3|hirSourceLocations.typeCount=3|hirSourceLocations.typeWithLocationCount=3|hirSourceLocations.types.0.ownerKind=constant-type|hirSourceLocations.types.0.ownerName=BASE_COLS|hirSourceLocations.types.0.type=int|hirSourceLocations.types.0.location.line=2|hirSourceLocations.types.1.ownerName=COLS|hirSourceLocations.types.1.location.line=3|hirSourceLocations.types.2.ownerName=ROWS|hirSourceLocations.types.2.location.line=4"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_dump_hir_source_map_folded_nested_array_helper_index_provenance
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_FOLDED_NESTED_ARRAY_HIR_SHADER}
    -DSTAGE=hir-source-map
    -DMODE=dump-stage
    "-DSOURCE_MAP_FILTER_ARGS=--source-map-function|readGrid|--source-map-expression-kind|index"
    "-DEXPECTED_JSON_PATHS=hirSourceLocations.expressions.0.location.file|hirSourceLocations.expressions.1.location.endOffset"
    "-DEXPECTED_JSON_ARRAY_LENGTHS=hirSourceLocations.expressions=2|hirSourceLocations.types=0|hirSourceLocations.statements=0|categoryCounts.expressionKinds=1|categoryCounts.statementKinds=0|categoryCounts.typeOwnerKinds=0"
    "-DEXPECTED_JSON_FIELDS=schemaVersion=7|filters.activeCount=2|filters.function=readGrid|filters.expressionKind=index|categoryCounts.expressionTotalCount=2|categoryCounts.recordTotalCount=2|categoryCounts.expressionKinds.0.name=index|categoryCounts.expressionKinds.0.count=2|records.enabled=false|records.totalCount=2|hirSourceLocations.expressionCount=2|hirSourceLocations.expressionWithLocationCount=2|hirSourceLocations.expressions.0.function=readGrid|hirSourceLocations.expressions.0.statementKind=return|hirSourceLocations.expressions.0.kind=index|hirSourceLocations.expressions.0.type=float|hirSourceLocations.expressions.0.location.line=11|hirSourceLocations.expressions.0.location.column=23|hirSourceLocations.expressions.1.location.line=11|hirSourceLocations.expressions.1.location.column=18"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_dump_hir_source_map_dynamic_nested_array_helper_index_provenance
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_DYNAMIC_NESTED_ARRAY_HIR_SHADER}
    -DSTAGE=hir-source-map
    -DMODE=dump-stage
    "-DSOURCE_MAP_FILTER_ARGS=--source-map-function|readGrid|--source-map-expression-kind|index"
    "-DEXPECTED_JSON_PATHS=hirSourceLocations.expressions.0.location.file|hirSourceLocations.expressions.1.location.endOffset"
    "-DEXPECTED_JSON_ARRAY_LENGTHS=hirSourceLocations.expressions=2|hirSourceLocations.types=0|hirSourceLocations.statements=0|categoryCounts.expressionKinds=1|categoryCounts.statementKinds=0|categoryCounts.typeOwnerKinds=0"
    "-DEXPECTED_JSON_FIELDS=schemaVersion=7|filters.activeCount=2|filters.function=readGrid|filters.expressionKind=index|categoryCounts.expressionTotalCount=2|categoryCounts.recordTotalCount=2|categoryCounts.expressionKinds.0.name=index|categoryCounts.expressionKinds.0.count=2|records.enabled=false|records.totalCount=2|hirSourceLocations.expressionCount=2|hirSourceLocations.expressionWithLocationCount=2|hirSourceLocations.expressions.0.function=readGrid|hirSourceLocations.expressions.0.statementKind=return|hirSourceLocations.expressions.0.kind=index|hirSourceLocations.expressions.0.type=float|hirSourceLocations.expressions.0.location.line=10|hirSourceLocations.expressions.0.location.column=23|hirSourceLocations.expressions.1.location.line=10|hirSourceLocations.expressions.1.location.column=18"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_dump_hir_source_map_dynamic_nested_array_call_provenance
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_DYNAMIC_NESTED_ARRAY_HIR_SHADER}
    -DSTAGE=hir-source-map
    -DMODE=dump-stage
    "-DSOURCE_MAP_FILTER_ARGS=--source-map-expression-kind|call|--source-map-operation|readGrid"
    "-DEXPECTED_JSON_PATHS=hirSourceLocations.expressions.0.location.file|hirSourceLocations.expressions.0.location.endOffset"
    "-DEXPECTED_JSON_ARRAY_LENGTHS=hirSourceLocations.expressions=1|hirSourceLocations.types=0|hirSourceLocations.statements=0|categoryCounts.expressionKinds=1|categoryCounts.statementKinds=0|categoryCounts.typeOwnerKinds=0"
    "-DEXPECTED_JSON_FIELDS=schemaVersion=7|filters.activeCount=2|filters.expressionKind=call|filters.expressionValue=readGrid|categoryCounts.expressionTotalCount=1|categoryCounts.recordTotalCount=1|categoryCounts.expressionKinds.0.name=call|categoryCounts.expressionKinds.0.count=1|records.enabled=false|records.totalCount=1|hirSourceLocations.expressionCount=1|hirSourceLocations.expressionWithLocationCount=1|hirSourceLocations.expressions.0.function=main|hirSourceLocations.expressions.0.statementKind=decl|hirSourceLocations.expressions.0.kind=call|hirSourceLocations.expressions.0.value=readGrid|hirSourceLocations.expressions.0.location.line=19|hirSourceLocations.expressions.0.location.column=24"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_dump_hir_source_map_intrinsic_call_provenance
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_INTRINSIC_COMPUTE_SHADER}
    -DSTAGE=hir-source-map
    -DMODE=dump-stage
    "-DSOURCE_MAP_FILTER_ARGS=--source-map-expression-kind|call"
    "-DEXPECTED_JSON_PATHS=hirSourceLocations.expressions.0.location.file|hirSourceLocations.expressions.13.location.endOffset"
    "-DEXPECTED_JSON_ARRAY_LENGTHS=hirSourceLocations.expressions=14|hirSourceLocations.types=0|hirSourceLocations.statements=0|categoryCounts.expressionKinds=1|categoryCounts.statementKinds=0|categoryCounts.typeOwnerKinds=0"
    "-DEXPECTED_JSON_FIELDS=schemaVersion=7|filters.activeCount=1|filters.expressionKind=call|pagination.activeCount=0|categoryCounts.expressionTotalCount=14|categoryCounts.typeTotalCount=0|categoryCounts.statementTotalCount=0|categoryCounts.recordTotalCount=14|categoryCounts.expressionKinds.0.name=call|categoryCounts.expressionKinds.0.count=14|records.enabled=false|records.totalCount=14|hirSourceLocations.expressionCount=14|hirSourceLocations.expressionWithLocationCount=14|hirSourceLocations.typeCount=0|hirSourceLocations.statementCount=0|hirSourceLocations.expressions.0.stage=compute|hirSourceLocations.expressions.0.function=main|hirSourceLocations.expressions.0.statementKind=decl|hirSourceLocations.expressions.0.kind=call|hirSourceLocations.expressions.0.value=abs|hirSourceLocations.expressions.0.type=float|hirSourceLocations.expressions.0.location.line=8|hirSourceLocations.expressions.0.location.column=25|hirSourceLocations.expressions.7.value=length|hirSourceLocations.expressions.7.type=float|hirSourceLocations.expressions.7.location.line=15|hirSourceLocations.expressions.8.value=length|hirSourceLocations.expressions.8.type=float|hirSourceLocations.expressions.8.location.line=16|hirSourceLocations.expressions.11.value=reflect|hirSourceLocations.expressions.11.type=vec4|hirSourceLocations.expressions.11.location.line=19|hirSourceLocations.expressions.12.value=normalize|hirSourceLocations.expressions.12.type=vec4|hirSourceLocations.expressions.12.location.column=43|hirSourceLocations.expressions.13.value=mix|hirSourceLocations.expressions.13.type=vec4|hirSourceLocations.expressions.13.location.line=20"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_dump_hir_source_map_intrinsic_call_filtered_pagination
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_INTRINSIC_COMPUTE_SHADER}
    -DSTAGE=hir-source-map
    -DMODE=dump-stage
    "-DSOURCE_MAP_FILTER_ARGS=--source-map-expression-kind|call|--source-map-expression-offset|7|--source-map-expression-limit|3"
    "-DEXPECTED_JSON_PATHS=hirSourceLocations.expressions.0.location.file|hirSourceLocations.expressions.2.location.endOffset"
    "-DEXPECTED_JSON_ARRAY_LENGTHS=hirSourceLocations.expressions=3|hirSourceLocations.types=0|hirSourceLocations.statements=0|categoryCounts.expressionKinds=1|categoryCounts.statementKinds=0|categoryCounts.typeOwnerKinds=0"
    "-DEXPECTED_JSON_FIELDS=schemaVersion=7|filters.activeCount=1|filters.expressionKind=call|pagination.activeCount=2|pagination.expressionOffset=7|pagination.expressionLimit=3|pagination.expressionTotalCount=14|pagination.expressionEmittedCount=3|pagination.expressionHasMore=true|pagination.expressionNextOffset=10|pagination.typeTotalCount=0|pagination.typeEmittedCount=0|pagination.typeHasMore=false|pagination.typeNextOffset=0|pagination.statementTotalCount=0|pagination.statementEmittedCount=0|pagination.statementHasMore=false|pagination.statementNextOffset=0|categoryCounts.expressionTotalCount=14|categoryCounts.recordTotalCount=14|categoryCounts.expressionKinds.0.name=call|categoryCounts.expressionKinds.0.count=14|records.enabled=false|records.totalCount=14|hirSourceLocations.expressionCount=3|hirSourceLocations.expressionWithLocationCount=3|hirSourceLocations.typeCount=0|hirSourceLocations.statementCount=0|hirSourceLocations.expressions.0.index=23|hirSourceLocations.expressions.0.kind=call|hirSourceLocations.expressions.0.value=length|hirSourceLocations.expressions.0.location.line=15|hirSourceLocations.expressions.0.location.column=28|hirSourceLocations.expressions.1.index=25|hirSourceLocations.expressions.1.value=length|hirSourceLocations.expressions.1.location.line=16|hirSourceLocations.expressions.2.index=29|hirSourceLocations.expressions.2.value=dot|hirSourceLocations.expressions.2.location.line=17|hirSourceLocations.expressions.2.location.column=25"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_dump_hir_source_map_vector_swizzle_member_provenance
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_VECTOR_SWIZZLE_COMPUTE_SHADER}
    -DSTAGE=hir-source-map
    -DMODE=dump-stage
    "-DSOURCE_MAP_FILTER_ARGS=--source-map-expression-kind|member"
    "-DEXPECTED_JSON_PATHS=hirSourceLocations.expressions.0.location.file|hirSourceLocations.expressions.5.location.endOffset"
    "-DEXPECTED_JSON_ARRAY_LENGTHS=hirSourceLocations.expressions=6|hirSourceLocations.types=0|hirSourceLocations.statements=0|categoryCounts.expressionKinds=1|categoryCounts.statementKinds=0|categoryCounts.typeOwnerKinds=0"
    "-DEXPECTED_JSON_FIELDS=schemaVersion=7|filters.activeCount=1|filters.expressionKind=member|pagination.activeCount=0|categoryCounts.expressionTotalCount=6|categoryCounts.typeTotalCount=0|categoryCounts.statementTotalCount=0|categoryCounts.recordTotalCount=6|categoryCounts.expressionKinds.0.name=member|categoryCounts.expressionKinds.0.count=6|records.enabled=false|records.totalCount=6|hirSourceLocations.expressionCount=6|hirSourceLocations.expressionWithLocationCount=6|hirSourceLocations.typeCount=0|hirSourceLocations.statementCount=0|hirSourceLocations.expressions.0.stage=compute|hirSourceLocations.expressions.0.function=main|hirSourceLocations.expressions.0.statementKind=decl|hirSourceLocations.expressions.0.kind=member|hirSourceLocations.expressions.0.value=rgb|hirSourceLocations.expressions.0.type=vec3|hirSourceLocations.expressions.0.location.line=8|hirSourceLocations.expressions.0.location.column=24|hirSourceLocations.expressions.1.value=xy|hirSourceLocations.expressions.1.type=vec2|hirSourceLocations.expressions.1.location.line=9|hirSourceLocations.expressions.2.value=rgba|hirSourceLocations.expressions.2.type=vec4|hirSourceLocations.expressions.2.location.line=10|hirSourceLocations.expressions.3.statementKind=assign|hirSourceLocations.expressions.3.value=z|hirSourceLocations.expressions.3.type=float|hirSourceLocations.expressions.3.location.line=11|hirSourceLocations.expressions.4.value=y|hirSourceLocations.expressions.4.type=float|hirSourceLocations.expressions.4.location.line=12|hirSourceLocations.expressions.5.value=b|hirSourceLocations.expressions.5.type=float|hirSourceLocations.expressions.5.location.line=13|hirSourceLocations.expressions.5.location.column=24"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_dump_hir_source_map_limit
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_TEXTURE_2D_SHADOW_COMPARE_LOD_MANUAL_KERNEL_LIST_SHADER}
    -DSTAGE=hir-source-map
    -DMODE=dump-stage
    "-DSOURCE_MAP_FILTER_ARGS=--source-map-limit|1"
    "-DEXPECTED_JSON_ARRAY_LENGTHS=hirSourceLocations.expressions=1|hirSourceLocations.types=1|hirSourceLocations.statements=1"
    "-DEXPECTED_JSON_FIELDS=schemaVersion=7|filters.activeCount=0|pagination.activeCount=3|categoryCounts.expressionTotalCount=36|categoryCounts.typeTotalCount=10|categoryCounts.statementTotalCount=3|categoryCounts.recordTotalCount=49|records.enabled=false|records.totalCount=49|pagination.expressionLimit=1|pagination.typeLimit=1|pagination.statementLimit=1|pagination.expressionEmittedCount=1|pagination.typeEmittedCount=1|pagination.statementEmittedCount=1|pagination.expressionHasMore=true|pagination.typeHasMore=true|pagination.statementHasMore=true|pagination.expressionNextOffset=1|pagination.typeNextOffset=1|pagination.statementNextOffset=1|hirSourceLocations.expressionCount=1|hirSourceLocations.typeCount=1|hirSourceLocations.statementCount=1"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_dump_hir_source_map_schema_contract
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_TEXTURE_2D_SHADOW_COMPARE_LOD_MANUAL_KERNEL_LIST_SHADER}
    -DSTAGE=hir-source-map
    -DMODE=dump-stage
    "-DSOURCE_MAP_FILTER_ARGS=--source-map-expression-kind|texture_compare_lod_manual|--source-map-operation|textureCompareLodManualKernel|--source-map-limit|1"
    "-DEXPECTED_JSON_PATHS=filters|pagination|categoryCounts|records|hirSourceLocations|categoryCounts.expressionKinds.0.name|hirSourceLocations.expressions.0.index|hirSourceLocations.expressions.0.stage|hirSourceLocations.expressions.0.entryPoint|hirSourceLocations.expressions.0.function|hirSourceLocations.expressions.0.statementKind|hirSourceLocations.expressions.0.kind|hirSourceLocations.expressions.0.value|hirSourceLocations.expressions.0.type|hirSourceLocations.expressions.0.location.file|hirSourceLocations.expressions.0.location.line|hirSourceLocations.expressions.0.location.column|hirSourceLocations.expressions.0.location.offset|hirSourceLocations.expressions.0.location.length|hirSourceLocations.expressions.0.location.endLine|hirSourceLocations.expressions.0.location.endColumn|hirSourceLocations.expressions.0.location.endOffset|hirSourceLocations.statements"
    "-DEXPECTED_JSON_ARRAY_LENGTHS=hirSourceLocations.expressions=1|hirSourceLocations.types=0|hirSourceLocations.statements=0|categoryCounts.expressionKinds=1|categoryCounts.statementKinds=0|categoryCounts.typeOwnerKinds=0"
    "-DEXPECTED_JSON_FIELDS=schemaVersion=7|filters.activeCount=2|filters.expressionKind=texture_compare_lod_manual|filters.expressionValue=textureCompareLodManualKernel|pagination.activeCount=3|pagination.expressionOffset=0|pagination.typeOffset=0|pagination.statementOffset=0|pagination.expressionLimit=1|pagination.typeLimit=1|pagination.statementLimit=1|pagination.expressionTotalCount=1|pagination.expressionEmittedCount=1|pagination.expressionHasMore=false|pagination.expressionNextOffset=1|pagination.typeTotalCount=0|pagination.typeEmittedCount=0|pagination.typeHasMore=false|pagination.typeNextOffset=0|pagination.statementTotalCount=0|pagination.statementEmittedCount=0|pagination.statementHasMore=false|pagination.statementNextOffset=0|categoryCounts.expressionTotalCount=1|categoryCounts.typeTotalCount=0|categoryCounts.statementTotalCount=0|categoryCounts.recordTotalCount=1|categoryCounts.expressionKinds.0.name=texture_compare_lod_manual|categoryCounts.expressionKinds.0.count=1|records.enabled=false|records.totalCount=1|records.emittedCount=0|hirSourceLocations.expressionCount=1|hirSourceLocations.expressionWithLocationCount=1|hirSourceLocations.typeCount=0|hirSourceLocations.typeWithLocationCount=0|hirSourceLocations.statementCount=0|hirSourceLocations.statementWithLocationCount=0"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
crossgl_add_python_expect_test(
  NAME cglc_dump_hir_source_map_json_schema
  DEFINITIONS
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_TEXTURE_2D_SHADOW_COMPARE_LOD_MANUAL_KERNEL_LIST_SHADER}
    -DSTAGE=hir-source-map
    -DMODE=dump-stage
    "-DSOURCE_MAP_FILTER_ARGS=--source-map-record-limit|2"
    -DJSON_SCHEMA=${CMAKE_CURRENT_SOURCE_DIR}/docs/schemas/hir-source-map-v7.schema.json
    -DJSON_SCHEMA_VALIDATOR=${CMAKE_CURRENT_SOURCE_DIR}/tools/validate_json_schema.py
    "-DEXPECTED_JSON_FIELDS=schemaVersion=7|records.enabled=true|records.items.0.recordKind=type")
crossgl_add_python_expect_test(
  NAME cglc_dump_hir_source_map_schema_v8_cli_json_schema
  DEFINITIONS
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_TEXTURE_2D_SHADOW_COMPARE_LOD_MANUAL_KERNEL_LIST_SHADER}
    -DSTAGE=hir-source-map
    -DMODE=dump-stage
    "-DSOURCE_MAP_FILTER_ARGS=--source-map-schema-version|8|--source-map-resource-kind|texture|--source-map-resource-limit|1|--source-map-record-limit|3"
    -DJSON_SCHEMA=${CMAKE_CURRENT_SOURCE_DIR}/docs/schemas/hir-source-map-v8.schema.json
    -DJSON_SCHEMA_VALIDATOR=${CMAKE_CURRENT_SOURCE_DIR}/tools/validate_json_schema.py
    "-DEXPECTED_JSON_ARRAY_LENGTHS=hirSourceLocations.expressions=0|hirSourceLocations.types=0|hirSourceLocations.statements=0|hirSourceLocations.resources=1|categoryCounts.resourceRecordKinds=5|categoryCounts.resourceKinds=1|records.items=3"
    "-DEXPECTED_JSON_FIELDS=schemaVersion=8|filters.activeCount=1|filters.resourceKind=texture|pagination.activeCount=1|pagination.resourceOffset=0|pagination.resourceLimit=1|pagination.resourceTotalCount=5|pagination.resourceEmittedCount=1|pagination.resourceHasMore=true|pagination.resourceNextOffset=1|categoryCounts.resourceTotalCount=5|categoryCounts.recordTotalCount=5|categoryCounts.resourceRecordKinds.0.name=access|categoryCounts.resourceRecordKinds.0.count=1|categoryCounts.resourceRecordKinds.1.name=binding|categoryCounts.resourceRecordKinds.1.count=1|categoryCounts.resourceRecordKinds.2.name=declaration|categoryCounts.resourceRecordKinds.2.count=1|categoryCounts.resourceRecordKinds.3.name=layout|categoryCounts.resourceRecordKinds.3.count=1|categoryCounts.resourceRecordKinds.4.name=set|categoryCounts.resourceRecordKinds.4.count=1|categoryCounts.resourceKinds.0.name=texture|categoryCounts.resourceKinds.0.count=5|records.enabled=true|records.totalCount=5|records.emittedCount=3|records.hasMore=true|records.items.0.recordKind=resource|records.items.0.resource.resourceRecordKind=layout|records.items.0.resource.resourceName=shadowMap|records.items.0.resource.resourceKind=texture|records.items.0.resource.bindingSet=0|records.items.0.resource.binding=2|records.items.1.recordKind=resource|records.items.1.resource.resourceRecordKind=declaration|records.items.2.recordKind=resource|records.items.2.resource.resourceRecordKind=set|records.items.2.resource.resourceName=shadowMap|records.items.2.resource.resourceKind=texture|records.items.2.resource.bindingSet=0|records.items.2.resource.binding=2|hirSourceLocations.resourceCount=1|hirSourceLocations.resourceWithLocationCount=1|hirSourceLocations.resources.0.resourceRecordKind=declaration|hirSourceLocations.resources.0.resourceName=shadowMap|hirSourceLocations.resources.0.resourceKind=texture|hirSourceLocations.resources.0.bindingSet=0|hirSourceLocations.resources.0.binding=2")
crossgl_add_python_expect_test(
  NAME cglc_dump_hir_source_map_schema_v8_alias_json_schema
  DEFINITIONS
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_TEXTURE_2D_SHADOW_COMPARE_LOD_MANUAL_KERNEL_LIST_SHADER}
    -DSTAGE=hir-source-map
    -DMODE=dump-stage
    "-DSOURCE_MAP_FILTER_ARGS=--hir-source-map-schema-version|8|--source-map-resource-kind|texture|--source-map-resource-limit|1"
    -DJSON_SCHEMA=${CMAKE_CURRENT_SOURCE_DIR}/docs/schemas/hir-source-map-v8.schema.json
    -DJSON_SCHEMA_VALIDATOR=${CMAKE_CURRENT_SOURCE_DIR}/tools/validate_json_schema.py
    "-DEXPECTED_JSON_ARRAY_LENGTHS=hirSourceLocations.expressions=0|hirSourceLocations.types=0|hirSourceLocations.statements=0|hirSourceLocations.resources=1"
    "-DEXPECTED_JSON_FIELDS=schemaVersion=8|filters.activeCount=1|filters.resourceKind=texture|pagination.resourceLimit=1|hirSourceLocations.resourceCount=1|hirSourceLocations.resources.0.resourceKind=texture")
add_test(NAME cglc_dump_hir_source_map_schema_alias_disagreement
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_TEXTURE_2D_SHADOW_COMPARE_LOD_MANUAL_KERNEL_LIST_SHADER}
    -DSTAGE=hir-source-map
    -DMODE=dump-stage-failure
    "-DSOURCE_MAP_FILTER_ARGS=--source-map-schema-version|7|--hir-source-map-schema-version|8"
    "-DEXPECTED_DIAGNOSTIC=source-map schema version aliases disagree"
    "-DEXPECTED_STDERR_FRAGMENT=source-map schema version aliases disagree"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_dump_backend_source_map_rejects_unsupported_target
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_SIMPLE_SHADER}
    -DTARGET=vulkan
    -DSTAGE=backend-source-map
    -DMODE=dump-stage-failure
    -DEXPECTED_DIAGNOSTIC=dump.backend-source-map.unsupported-target
    "-DEXPECTED_STDERR_FRAGMENT=backend source maps currently support directx, metal, and opengl only"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_dump_hir_source_map_records
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_TEXTURE_2D_SHADOW_COMPARE_LOD_MANUAL_KERNEL_LIST_SHADER}
    -DSTAGE=hir-source-map
    -DMODE=dump-stage
    "-DSOURCE_MAP_FILTER_ARGS=--source-map-record-limit|2"
    "-DEXPECTED_JSON_PATHS=records.items.0.type.location.endOffset|records.items.1.type.location.endOffset"
    "-DEXPECTED_JSON_ARRAY_LENGTHS=records.items=2"
    "-DEXPECTED_JSON_FIELDS=schemaVersion=7|categoryCounts.recordTotalCount=49|records.enabled=true|records.activeCount=2|records.limit=2|records.totalCount=49|records.emittedCount=2|records.hasMore=true|records.nextOffset=2|records.items.0.cursor=0|records.items.0.recordKind=type|records.items.0.type.ownerName=values|records.items.1.cursor=1|records.items.1.recordKind=type|records.items.1.type.ownerName=index"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_dump_debug_capability_groups
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_TEXTURE_2D_SHADOW_COMPARE_LOD_MANUAL_KERNEL_LIST_SHADER}
    -DSTAGE=debug
    -DMODE=dump-stage
    -DTARGET_EXPLANATION_ROOT=targetCapabilities
    -DTARGET_RECORD_ARRAY_FIELD=summaries
    "-DEXPECTED_TARGET_FIELDS=directx.missingCapabilityGroups.0.kind=backend|directx.missingCapabilityGroups.0.count=1|opengl.missingCapabilityGroups.0.kind=backend"
    "-DEXPECTED_TARGET_ARRAY_CONTAINS=directx.missingCapabilityGroups.0.capabilities=directx.backend.native-dxil-package|opengl.missingCapabilityGroups.0.capabilities=opengl.backend.native-glsl-package"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_dump_debug_target_decision
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_TEXTURE_2D_SHADOW_COMPARE_LOD_MANUAL_KERNEL_LIST_SHADER}
    -DSTAGE=debug
    -DMODE=dump-stage
    -DAUTO_TARGET_DECISION_FROM_CAPABILITIES=ON
    "-DEXPECTED_JSON_FIELDS=targetDecision.selectedTargetDiagnosticCount=0"
    "-DEXPECTED_JSON_ARRAY_CONTAINS=targetDecision.viableTargets=directx|targetDecision.viableTargets=opengl"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
if(APPLE)
  set(CROSSGL_AUTO_TARGET_FALLBACK_SHADER
      ${CROSSGL_METAL_STORAGE_BUFFER_OUT_OF_RANGE_DESCRIPTOR_ARRAY_UNSUPPORTED_SHADER})
  set(CROSSGL_AUTO_TARGET_FALLBACK_MODULE
      MetalStorageBufferOutOfRangeDescriptorArrayUnsupportedShader)
  set(CROSSGL_AUTO_TARGET_FALLBACK_DEFAULT_TARGET metal)
  set(CROSSGL_AUTO_TARGET_FALLBACK_SELECTED_TARGET vulkan)
  set(CROSSGL_AUTO_TARGET_FALLBACK_NONVIABLE_TARGET metal)
  set(CROSSGL_AUTO_TARGET_FALLBACK_BUILDABLE_COUNT 3)
  set(CROSSGL_AUTO_TARGET_FALLBACK_RECORD_COUNT 2)
  set(CROSSGL_AUTO_TARGET_FALLBACK_MISSING_CAPABILITY_TARGET
      ${CROSSGL_AUTO_TARGET_FALLBACK_NONVIABLE_TARGET})
  set(CROSSGL_AUTO_TARGET_FALLBACK_MISSING_CAPABILITY
      metal.backend.native-metal-package)
  set(CROSSGL_AUTO_TARGET_FALLBACK_DECISION_ARRAY_CONTAINS
      "targetDecision.viableTargets=${CROSSGL_AUTO_TARGET_FALLBACK_SELECTED_TARGET}|targetDecision.fallbackTargets=directx|targetDecision.nonViableTargets=${CROSSGL_AUTO_TARGET_FALLBACK_NONVIABLE_TARGET}")
  set(CROSSGL_AUTO_TARGET_FALLBACK_TARGET_FIELDS
      "${CROSSGL_AUTO_TARGET_FALLBACK_SELECTED_TARGET}.packageBuildSupported=true|${CROSSGL_AUTO_TARGET_FALLBACK_SELECTED_TARGET}.packageMode=native|${CROSSGL_AUTO_TARGET_FALLBACK_SELECTED_TARGET}.packageRankScore=0|${CROSSGL_AUTO_TARGET_FALLBACK_NONVIABLE_TARGET}.packageBuildSupported=false|${CROSSGL_AUTO_TARGET_FALLBACK_NONVIABLE_TARGET}.packageMode=unsupported|${CROSSGL_AUTO_TARGET_FALLBACK_NONVIABLE_TARGET}.packageRankScore=2")
else()
  set(CROSSGL_AUTO_TARGET_FALLBACK_SHADER
      ${CROSSGL_VULKAN_TEXTURE_SAMPLER_ARRAY_ACCESS_UNSUPPORTED_SHADER})
  set(CROSSGL_AUTO_TARGET_FALLBACK_MODULE
      VulkanTextureSamplerArrayAccessUnsupportedShader)
  if(WIN32)
    set(CROSSGL_AUTO_TARGET_FALLBACK_DEFAULT_TARGET directx)
    set(CROSSGL_AUTO_TARGET_FALLBACK_SELECTED_TARGET metal)
  else()
    set(CROSSGL_AUTO_TARGET_FALLBACK_DEFAULT_TARGET vulkan)
    set(CROSSGL_AUTO_TARGET_FALLBACK_SELECTED_TARGET vulkan)
  endif()
  set(CROSSGL_AUTO_TARGET_FALLBACK_OPENGL_TARGET opengl)
  set(CROSSGL_AUTO_TARGET_FALLBACK_BUILDABLE_COUNT 4)
  set(CROSSGL_AUTO_TARGET_FALLBACK_RECORD_COUNT 3)
  set(CROSSGL_AUTO_TARGET_FALLBACK_MISSING_CAPABILITY_TARGET
      ${CROSSGL_AUTO_TARGET_FALLBACK_OPENGL_TARGET})
  set(CROSSGL_AUTO_TARGET_FALLBACK_MISSING_CAPABILITY
      opengl.backend.native-glsl-package)
  set(CROSSGL_AUTO_TARGET_FALLBACK_DECISION_ARRAY_CONTAINS
      "targetDecision.viableTargets=${CROSSGL_AUTO_TARGET_FALLBACK_SELECTED_TARGET}|targetDecision.fallbackTargets=directx|targetDecision.fallbackTargets=${CROSSGL_AUTO_TARGET_FALLBACK_OPENGL_TARGET}")
  set(CROSSGL_AUTO_TARGET_FALLBACK_TARGET_FIELDS
      "metal.packageBuildSupported=true|metal.packageMode=native|metal.packageRankScore=0|vulkan.packageBuildSupported=true|vulkan.packageMode=native|vulkan.packageRankScore=0|directx.sourcePackageSupported=true|directx.packageBuildSupported=true|directx.packageMode=source-package|directx.packageDecisionReason=source-package-available|directx.packageRankScore=1|directx.missingCapabilityCount=3|${CROSSGL_AUTO_TARGET_FALLBACK_OPENGL_TARGET}.sourcePackageSupported=true|${CROSSGL_AUTO_TARGET_FALLBACK_OPENGL_TARGET}.packageBuildSupported=true|${CROSSGL_AUTO_TARGET_FALLBACK_OPENGL_TARGET}.packageMode=source-package|${CROSSGL_AUTO_TARGET_FALLBACK_OPENGL_TARGET}.packageDecisionReason=source-package-available|${CROSSGL_AUTO_TARGET_FALLBACK_OPENGL_TARGET}.packageRankScore=1|${CROSSGL_AUTO_TARGET_FALLBACK_OPENGL_TARGET}.missingCapabilityCount=3")
endif()
add_test(NAME cglc_dump_debug_auto_recommended_target_fallback
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_AUTO_TARGET_FALLBACK_SHADER}
    -DSTAGE=debug
    -DMODE=dump-stage
    -DAUTO_TARGET_DECISION_FROM_CAPABILITIES=ON
    "-DEXPECTED_JSON_FIELDS=targetDecision.selectedTargetPackageBuildSupported=true|targetDecision.selectedTargetPackageMode=native|targetDecision.selectedTargetDiagnosticCount=0|targetDecision.fallbackTargetRecordCount=${CROSSGL_AUTO_TARGET_FALLBACK_RECORD_COUNT}"
    "-DEXPECTED_JSON_ARRAY_CONTAINS=${CROSSGL_AUTO_TARGET_FALLBACK_DECISION_ARRAY_CONTAINS}"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_dump_debug_selected_target_mode
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_TEXTURE_2D_SHADOW_COMPARE_LOD_MANUAL_KERNEL_LIST_SHADER}
    -DTARGET=directx
    -DSTAGE=debug
    -DMODE=dump-stage
    "-DEXPECTED_JSON_FIELDS=targetDecision.requestedTarget=directx|targetDecision.selectedTarget=directx|targetDecision.selectedTargetPackageMode=source-package|targetDecision.selectedTargetPackageBuildSupported=true|targetDecision.selectedTargetDiagnosticCount=0"
    "-DEXPECTED_JSON_ARRAY_CONTAINS=targetDecision.selectedTargetMissingCapabilities=directx.backend.native-dxil-package"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_dump_debug_selected_target_diagnostics
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_DIRECTX_RUNTIME_TEXTURE_RESOURCE_ARRAY_CONFLICT_SHADER}
    -DTARGET=directx
    -DSTAGE=debug
    -DMODE=dump-stage
    "-DEXPECTED_JSON_FIELDS=targetDecision.requestedTarget=directx|targetDecision.selectedTarget=directx|targetDecision.selectedTargetSourcePackageSupported=false|targetDecision.selectedTargetPackageMode=unsupported|targetDecision.selectedTargetPackageBuildSupported=false|targetDecision.selectedTargetMissingCapabilityCount=4|targetDecision.selectedTargetDiagnosticCount=1|targetDecision.diagnostics.0.code=directx.unsupported-runtime-resource-array|targetDecision.diagnostics.0.target=directx"
    "-DEXPECTED_JSON_ARRAY_CONTAINS=targetDecision.selectedTargetMissingCapabilities=directx.backend.native-dxil-package|targetDecision.selectedTargetMissingCapabilities=directx.toolchain.dxc|targetDecision.selectedTargetMissingCapabilities=directx.validation.dxil-validator|targetDecision.selectedTargetMissingCapabilities=directx.diagnostic.directx.unsupported-runtime-resource-array|targetDecision.diagnostics.0.capabilities=directx.backend.native-dxil-package|targetDecision.diagnostics.0.capabilities=directx.toolchain.dxc|targetDecision.diagnostics.0.capabilities=directx.validation.dxil-validator|targetDecision.diagnostics.0.capabilities=directx.diagnostic.directx.unsupported-runtime-resource-array"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_dump_backend_unsupported_target_admission
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_DIRECTX_RUNTIME_TEXTURE_RESOURCE_ARRAY_CONFLICT_SHADER}
    -DTARGET=directx
    -DSTAGE=backend
    -DMODE=dump-stage-failure
    -DEXPECTED_DIAGNOSTIC=directx.unsupported-runtime-resource-array
    "-DEXPECTED_STDERR_FRAGMENT=TargetLegalizationResult: state=rejected"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_dump_debug_opengl_selected_target_diagnostics
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_TEXTURE_CUBE_SHADOW_COMPARE_LOD_UNSUPPORTED_SHADER}
    -DTARGET=opengl
    -DSTAGE=debug
    -DMODE=dump-stage
    "-DEXPECTED_JSON_FIELDS=targetDecision.requestedTarget=opengl|targetDecision.selectedTarget=opengl|targetDecision.selectedTargetSourcePackageSupported=true|targetDecision.selectedTargetPackageMode=source-package|targetDecision.selectedTargetPackageBuildSupported=true|targetDecision.selectedTargetMissingCapabilityCount=3|targetDecision.selectedTargetDiagnosticCount=0"
    "-DEXPECTED_JSON_ARRAY_CONTAINS=targetDecision.selectedTargetMissingCapabilities=opengl.backend.native-glsl-package|targetDecision.selectedTargetMissingCapabilities=opengl.toolchain.opengl-driver|targetDecision.selectedTargetMissingCapabilities=opengl.validation.glsl-program-validation"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
crossgl_add_python_expect_test(
  NAME cglc_dump_debug_json_schema_selected_target_diagnostics
  DEFINITIONS
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_DIRECTX_RUNTIME_TEXTURE_RESOURCE_ARRAY_CONFLICT_SHADER}
    -DTARGET=directx
    -DSTAGE=debug
    -DMODE=dump-stage
    -DJSON_SCHEMA=${CMAKE_CURRENT_SOURCE_DIR}/docs/schemas/debug-metadata-v11.schema.json
    -DJSON_SCHEMA_VALIDATOR=${CMAKE_CURRENT_SOURCE_DIR}/tools/validate_json_schema.py
    "-DEXPECTED_JSON_FIELDS=schemaVersion=11|targetDecision.requestedTarget=directx|targetDecision.selectedTarget=directx|targetDecision.selectedTargetSourcePackageSupported=false|targetDecision.selectedTargetPackageMode=unsupported|targetDecision.selectedTargetMissingCapabilityCount=4|targetDecision.selectedTargetDiagnosticCount=1|targetDecision.diagnostics.0.code=directx.unsupported-runtime-resource-array|targetDecision.diagnostics.0.severity=error"
    "-DEXPECTED_JSON_ARRAY_CONTAINS=targetDecision.selectedTargetMissingCapabilities=directx.backend.native-dxil-package|targetDecision.selectedTargetMissingCapabilities=directx.toolchain.dxc|targetDecision.selectedTargetMissingCapabilities=directx.validation.dxil-validator|targetDecision.selectedTargetMissingCapabilities=directx.diagnostic.directx.unsupported-runtime-resource-array|targetDecision.diagnostics.0.capabilities=directx.backend.native-dxil-package|targetDecision.diagnostics.0.capabilities=directx.toolchain.dxc|targetDecision.diagnostics.0.capabilities=directx.validation.dxil-validator|targetDecision.diagnostics.0.capabilities=directx.diagnostic.directx.unsupported-runtime-resource-array")
add_test(NAME cglc_dump_debug_fallback_records
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_TEXTURE_2D_SHADOW_COMPARE_LOD_MANUAL_KERNEL_LIST_SHADER}
    -DTARGET=directx
    -DSTAGE=debug
    -DMODE=dump-stage
    "-DEXPECTED_JSON_FIELDS=targetDecision.requestedTarget=directx|targetDecision.fallbackTargetRecordCount=3"
    -DTARGET_EXPLANATION_ROOT=targetDecision
    -DTARGET_RECORD_ARRAY_FIELD=fallbackTargetRecords
    "-DEXPECTED_TARGET_FIELDS=metal.packageMode=native|vulkan.packageMode=native|opengl.packageMode=source-package"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_dump_debug_package_decision_summary
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_TEXTURE_2D_SHADOW_COMPARE_LOD_MANUAL_KERNEL_LIST_SHADER}
    -DSTAGE=debug
    -DMODE=dump-stage
    -DTARGET_EXPLANATION_ROOT=targetCapabilities
    -DTARGET_RECORD_ARRAY_FIELD=summaries
    "-DEXPECTED_TARGET_FIELDS=directx.packageRankScore=1|directx.missingCapabilityCount=3|opengl.packageRankScore=1|opengl.missingCapabilityCount=3"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_dump_debug_directx_graphics_storage_buffer_target_capabilities_evidence
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_DIRECTX_GRAPHICS_STORAGE_BUFFER_RESOURCE_SHADER}
    -DTARGET=directx
    -DSTAGE=debug
    -DMODE=dump-stage
    "-DEXPECTED_JSON_FIELDS=schemaVersion=11|targetDecision.requestedTarget=directx|targetDecision.selectedTarget=directx|targetDecision.selectedTargetPackageMode=source-package|targetDecision.selectedTargetPackageBuildSupported=true|targetDecision.selectedTargetMissingCapabilityCount=3|targetDecision.selectedTargetDiagnosticCount=0"
    "-DEXPECTED_JSON_ARRAY_CONTAINS=targetDecision.selectedTargetMissingCapabilities=directx.backend.native-dxil-package|targetDecision.selectedTargetMissingCapabilities=directx.toolchain.dxc|targetDecision.selectedTargetMissingCapabilities=directx.validation.dxil-validator"
    -DTARGET_EXPLANATION_ROOT=targetCapabilities
    -DTARGET_RECORD_ARRAY_FIELD=summaries
    "-DEXPECTED_TARGET_FIELDS=directx.sourcePackageSupported=true|directx.packageBuildSupported=true|directx.packageMode=source-package|directx.requiredCapabilityCount=14|directx.missingCapabilityCount=3|directx.requiredCapabilityGroups.4.kind=resource|directx.requiredCapabilityGroups.4.count=1|directx.requiredCapabilityGroups.5.kind=layout|directx.requiredCapabilityGroups.5.count=1|directx.requiredCapabilityGroups.6.kind=operation|directx.requiredCapabilityGroups.6.count=6"
    "-DEXPECTED_TARGET_ARRAY_CONTAINS=directx.requiredCapabilities=directx.resource.storage-buffer|directx.requiredCapabilities=directx.layout.vector-storage-buffer|directx.requiredCapabilities=directx.operation.storage-buffer-read|directx.requiredCapabilities=directx.operation.storage-buffer-write|directx.missingCapabilities=directx.backend.native-dxil-package|directx.requiredCapabilityGroups.4.capabilities=directx.resource.storage-buffer|directx.requiredCapabilityGroups.5.capabilities=directx.layout.vector-storage-buffer"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_dump_debug_metal_graphics_descriptor_array_target_capabilities_evidence
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_METAL_GRAPHICS_DESCRIPTOR_ARRAY_SHADER}
    -DTARGET=metal
    -DSTAGE=debug
    -DMODE=dump-stage
    "-DEXPECTED_JSON_FIELDS=schemaVersion=11|targetDecision.requestedTarget=metal|targetDecision.selectedTarget=metal|targetDecision.selectedTargetPackageMode=native|targetDecision.selectedTargetPackageBuildSupported=true|targetDecision.selectedTargetMissingCapabilityCount=0|targetDecision.selectedTargetDiagnosticCount=0"
    -DTARGET_EXPLANATION_ROOT=targetCapabilities
    -DTARGET_RECORD_ARRAY_FIELD=summaries
    "-DEXPECTED_TARGET_FIELDS=metal.nativeImplemented=true|metal.packageBuildSupported=true|metal.packageMode=native|metal.requiredCapabilityCount=21|metal.missingCapabilityCount=0|metal.requiredCapabilityGroups.5.kind=resource|metal.requiredCapabilityGroups.5.count=3|metal.requiredCapabilityGroups.6.kind=layout|metal.requiredCapabilityGroups.6.count=1|metal.requiredCapabilityGroups.8.kind=texture|metal.requiredCapabilityGroups.8.count=1"
    "-DEXPECTED_TARGET_ARRAY_CONTAINS=metal.requiredCapabilities=metal.resource.sampled-texture|metal.requiredCapabilities=metal.resource.sampler-state|metal.requiredCapabilities=metal.resource.descriptor-array|metal.requiredCapabilities=metal.layout.fixed-array|metal.requiredCapabilities=metal.texture.depth-compare-format|metal.requiredCapabilities=metal.operation.texture-shadow-compare-explicit-lod|metal.requiredCapabilityGroups.5.capabilities=metal.resource.descriptor-array|metal.requiredCapabilityGroups.6.capabilities=metal.layout.fixed-array|metal.requiredCapabilityGroups.8.capabilities=metal.texture.depth-compare-format"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_dump_debug_opengl_graphics_descriptor_array_target_capabilities_evidence
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_OPENGL_GRAPHICS_DESCRIPTOR_ARRAY_RESOURCES_SHADER}
    -DTARGET=opengl
    -DSTAGE=debug
    -DMODE=dump-stage
    "-DEXPECTED_JSON_FIELDS=schemaVersion=11|targetDecision.requestedTarget=opengl|targetDecision.selectedTarget=opengl|targetDecision.selectedTargetPackageMode=source-package|targetDecision.selectedTargetPackageBuildSupported=true|targetDecision.selectedTargetMissingCapabilityCount=3|targetDecision.selectedTargetDiagnosticCount=0"
    "-DEXPECTED_JSON_ARRAY_CONTAINS=targetDecision.selectedTargetMissingCapabilities=opengl.backend.native-glsl-package|targetDecision.selectedTargetMissingCapabilities=opengl.toolchain.opengl-driver|targetDecision.selectedTargetMissingCapabilities=opengl.validation.glsl-program-validation"
    -DTARGET_EXPLANATION_ROOT=targetCapabilities
    -DTARGET_RECORD_ARRAY_FIELD=summaries
    "-DEXPECTED_TARGET_FIELDS=opengl.sourcePackageSupported=true|opengl.packageBuildSupported=true|opengl.packageMode=source-package|opengl.requiredCapabilityCount=16|opengl.missingCapabilityCount=3|opengl.requiredCapabilityGroups.4.kind=resource|opengl.requiredCapabilityGroups.4.count=3|opengl.requiredCapabilityGroups.5.kind=layout|opengl.requiredCapabilityGroups.5.count=1"
    "-DEXPECTED_TARGET_ARRAY_CONTAINS=opengl.requiredCapabilities=opengl.resource.sampled-texture|opengl.requiredCapabilities=opengl.resource.sampler-state|opengl.requiredCapabilities=opengl.resource.descriptor-array|opengl.requiredCapabilities=opengl.layout.fixed-array|opengl.missingCapabilities=opengl.backend.native-glsl-package|opengl.missingCapabilities=opengl.toolchain.opengl-driver|opengl.missingCapabilities=opengl.validation.glsl-program-validation|opengl.requiredCapabilityGroups.4.capabilities=opengl.resource.descriptor-array|opengl.requiredCapabilityGroups.5.capabilities=opengl.layout.fixed-array"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_dump_debug_vulkan_runtime_texture_sampler_descriptor_array_target_capabilities_evidence
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_VULKAN_RUNTIME_TEXTURE_SAMPLER_DESCRIPTOR_ARRAY_POLICY_SHADER}
    -DTARGET=vulkan
    -DSTAGE=debug
    -DMODE=dump-stage
    "-DEXPECTED_JSON_FIELDS=schemaVersion=11|targetDecision.requestedTarget=vulkan|targetDecision.selectedTarget=vulkan|targetDecision.selectedTargetPackageMode=native|targetDecision.selectedTargetPackageBuildSupported=true|targetDecision.selectedTargetMissingCapabilityCount=0|targetDecision.selectedTargetDiagnosticCount=0"
    -DTARGET_EXPLANATION_ROOT=targetCapabilities
    -DTARGET_RECORD_ARRAY_FIELD=summaries
    "-DEXPECTED_TARGET_FIELDS=vulkan.nativeImplemented=true|vulkan.packageBuildSupported=true|vulkan.packageMode=native|vulkan.requiredCapabilityCount=22|vulkan.missingCapabilityCount=0|vulkan.requiredCapabilityGroups.7.kind=resource|vulkan.requiredCapabilityGroups.7.count=7|vulkan.requiredCapabilityGroups.8.kind=layout|vulkan.requiredCapabilityGroups.8.count=2"
    "-DEXPECTED_TARGET_ARRAY_CONTAINS=vulkan.requiredCapabilities=vulkan.resource.runtime-descriptor-array|vulkan.requiredCapabilities=vulkan.resource.runtime-texture-descriptor-array|vulkan.requiredCapabilities=vulkan.resource.runtime-sampler-descriptor-array|vulkan.requiredCapabilities=vulkan.layout.runtime-array|vulkan.requiredCapabilities=vulkan.resource.descriptor-array|vulkan.requiredCapabilityGroups.7.capabilities=vulkan.resource.runtime-descriptor-array|vulkan.requiredCapabilityGroups.7.capabilities=vulkan.resource.runtime-texture-descriptor-array|vulkan.requiredCapabilityGroups.7.capabilities=vulkan.resource.runtime-sampler-descriptor-array|vulkan.requiredCapabilityGroups.8.capabilities=vulkan.layout.runtime-array"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_explain_targets_package_decisions
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_TEXTURE_2D_SHADOW_COMPARE_LOD_MANUAL_KERNEL_LIST_SHADER}
    -DMODE=explain-targets
    "-DEXPECTED_JSON_FIELDS=schemaVersion=1|module=Texture2DShadowCompareLodManualKernelListShader"
    "-DEXPECTED_TARGET_FIELDS=metal.nativeImplemented=true|metal.packageBuildSupported=true|metal.packageMode=native|metal.packageDecisionReason=native-package-available|metal.packageRankScore=0|vulkan.nativeImplemented=true|vulkan.packageBuildSupported=true|vulkan.packageMode=native|vulkan.packageDecisionReason=native-package-available|vulkan.packageRankScore=0|directx.packageMode=source-package|directx.packageDecisionReason=source-package-available|directx.packageBuildSupported=true|opengl.packageMode=source-package"
    "-DEXPECTED_TARGET_ARRAY_CONTAINS=directx.missingCapabilities=directx.backend.native-dxil-package|opengl.missingCapabilities=opengl.backend.native-glsl-package"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_explain_targets_storage_image_access_qualifier_descriptor_array_target_capabilities
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_STORAGE_IMAGE_ACCESS_QUALIFIER_HIR_SHADER}
    -DMODE=explain-targets
    "-DEXPECTED_JSON_FIELDS=schemaVersion=1|module=StorageImageAccessQualifierHIRShader"
    "-DEXPECTED_TARGET_ARRAY_CONTAINS=${CROSSGL_STORAGE_IMAGE_ACCESS_QUALIFIER_TARGET_CAPABILITIES}"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_explain_targets_storage_image_explicit_format_nonuniform_descriptor_array_target_capabilities
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_STORAGE_IMAGE_EXPLICIT_FORMAT_DESCRIPTOR_ARRAY_SHADER}
    -DMODE=explain-targets
    "-DEXPECTED_JSON_FIELDS=schemaVersion=1|module=StorageImageExplicitFormatDescriptorArrayShader"
    "-DEXPECTED_TARGET_ARRAY_CONTAINS=${CROSSGL_STORAGE_IMAGE_EXPLICIT_FORMAT_DESCRIPTOR_ARRAY_TARGET_CAPABILITIES}"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_explain_targets_storage_image_atomic_nonuniform_descriptor_array_target_capabilities
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_STORAGE_IMAGE_ATOMIC_DESCRIPTOR_ARRAY_SHADER}
    -DMODE=explain-targets
    "-DEXPECTED_JSON_FIELDS=schemaVersion=1|module=StorageImageAtomicDescriptorArrayShader"
    "-DEXPECTED_TARGET_ARRAY_CONTAINS=${CROSSGL_STORAGE_IMAGE_ATOMIC_DESCRIPTOR_ARRAY_TARGET_CAPABILITIES}"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_explain_targets_auto_recommended_target_fallback
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_AUTO_TARGET_FALLBACK_SHADER}
    -DMODE=explain-targets
    "-DEXPECTED_JSON_FIELDS=schemaVersion=1|module=${CROSSGL_AUTO_TARGET_FALLBACK_MODULE}|defaultTarget=${CROSSGL_AUTO_TARGET_FALLBACK_DEFAULT_TARGET}|buildableTargetCount=${CROSSGL_AUTO_TARGET_FALLBACK_BUILDABLE_COUNT}|recommendedTarget=${CROSSGL_AUTO_TARGET_FALLBACK_SELECTED_TARGET}|recommendedPackageMode=native"
    "-DEXPECTED_TARGET_FIELDS=${CROSSGL_AUTO_TARGET_FALLBACK_TARGET_FIELDS}"
    "-DEXPECTED_TARGET_ARRAY_CONTAINS=${CROSSGL_AUTO_TARGET_FALLBACK_MISSING_CAPABILITY_TARGET}.missingCapabilities=${CROSSGL_AUTO_TARGET_FALLBACK_MISSING_CAPABILITY}"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_explain_targets_native_predicate_unsupported
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_DIRECTX_RUNTIME_TEXTURE_RESOURCE_ARRAY_CONFLICT_SHADER}
    -DMODE=explain-targets
    "-DEXPECTED_JSON_FIELDS=schemaVersion=1|module=DirectXRuntimeTextureResourceArrayConflictShader|buildableTargetCount=1|recommendedTarget=metal|recommendedPackageMode=native"
    "-DEXPECTED_TARGET_FIELDS=metal.nativeImplemented=true|metal.sourcePackageSupported=false|metal.packageBuildSupported=true|metal.packageMode=native|metal.packageDecisionReason=native-package-available|metal.packageRankScore=0|metal.missingCapabilityCount=0|vulkan.nativeImplemented=true|vulkan.sourcePackageSupported=false|vulkan.packageBuildSupported=false|vulkan.packageMode=unsupported|vulkan.packageDecisionReason=unsupported|vulkan.packageRankScore=2|vulkan.missingCapabilityCount=2|directx.nativeImplemented=true|directx.sourcePackageSupported=false|directx.packageBuildSupported=false|directx.packageMode=unsupported|directx.packageDecisionReason=unsupported|directx.packageRankScore=2|directx.missingCapabilityCount=4|opengl.sourcePackageSupported=false|opengl.packageBuildSupported=false|opengl.packageMode=unsupported|opengl.packageDecisionReason=unsupported|opengl.packageRankScore=2|opengl.missingCapabilityCount=2"
    "-DEXPECTED_TARGET_ARRAY_CONTAINS=metal.requiredCapabilities=metal.backend.native-metal-package|metal.requiredCapabilities=metal.resource.runtime-descriptor-array|metal.requiredCapabilities=metal.resource.runtime-texture-descriptor-array|metal.requiredCapabilities=metal.layout.runtime-array|vulkan.missingCapabilities=vulkan.backend.vulkan-prototype-package|vulkan.missingCapabilities=vulkan.diagnostic.vulkan.prototype-unsupported-runtime-resource-array|directx.missingCapabilities=directx.backend.native-dxil-package|directx.missingCapabilities=directx.toolchain.dxc|directx.missingCapabilities=directx.validation.dxil-validator|directx.missingCapabilities=directx.diagnostic.directx.unsupported-runtime-resource-array|opengl.missingCapabilities=opengl.backend.glsl-lowering|opengl.missingCapabilities=opengl.diagnostic.opengl.unsupported-runtime-resource-array"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_explain_targets_directx_source_package_predicate_supported
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_DIRECTX_MIXED_SAMPLER_USAGE_UNSUPPORTED_SHADER}
    -DMODE=explain-targets
    "-DEXPECTED_JSON_FIELDS=schemaVersion=1|module=DirectXMixedSamplerUsageUnsupportedShader"
    "-DEXPECTED_TARGET_FIELDS=directx.nativeImplemented=true|directx.sourcePackageSupported=true|directx.packageBuildSupported=true|directx.packageMode=source-package|directx.packageDecisionReason=source-package-available|directx.packageRankScore=1|opengl.sourcePackageSupported=true|opengl.packageBuildSupported=true|opengl.packageMode=source-package|opengl.packageDecisionReason=source-package-available|opengl.packageRankScore=1"
    "-DEXPECTED_TARGET_ARRAY_CONTAINS=directx.missingCapabilities=directx.backend.native-dxil-package|opengl.missingCapabilities=opengl.backend.native-glsl-package"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_explain_targets_opengl_source_package_predicate_unsupported
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_TEXTURE_CUBE_SHADOW_COMPARE_LOD_UNSUPPORTED_SHADER}
    -DMODE=explain-targets
    "-DEXPECTED_JSON_FIELDS=schemaVersion=1|module=TextureCubeShadowCompareLodUnsupportedShader"
    "-DEXPECTED_TARGET_FIELDS=directx.sourcePackageSupported=true|directx.packageBuildSupported=true|directx.packageMode=source-package|directx.packageDecisionReason=source-package-available|directx.packageRankScore=1|opengl.nativeImplemented=false|opengl.sourcePackageSupported=true|opengl.packageBuildSupported=true|opengl.packageMode=source-package|opengl.packageDecisionReason=source-package-available|opengl.packageRankScore=1|opengl.missingCapabilityCount=3"
    "-DEXPECTED_TARGET_ARRAY_CONTAINS=directx.missingCapabilities=directx.backend.native-dxil-package|opengl.missingCapabilities=opengl.backend.native-glsl-package|opengl.missingCapabilities=opengl.toolchain.opengl-driver|opengl.missingCapabilities=opengl.validation.glsl-program-validation"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
crossgl_add_python_expect_test(
  NAME cglc_explain_targets_json_schema
  DEFINITIONS
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_TEXTURE_2D_SHADOW_COMPARE_LOD_MANUAL_KERNEL_LIST_SHADER}
    -DMODE=explain-targets
    -DJSON_SCHEMA=${CMAKE_CURRENT_SOURCE_DIR}/docs/schemas/target-explanation-v1.schema.json
    -DJSON_SCHEMA_VALIDATOR=${CMAKE_CURRENT_SOURCE_DIR}/tools/validate_json_schema.py
    "-DEXPECTED_JSON_FIELDS=schemaVersion=1|module=Texture2DShadowCompareLodManualKernelListShader|recommendedPackageMode=native"
    "-DEXPECTED_TARGET_FIELDS=metal.packageMode=native|vulkan.packageMode=native|directx.packageMode=source-package|opengl.packageMode=source-package"
    "-DEXPECTED_TARGET_ARRAY_CONTAINS=directx.missingCapabilities=directx.backend.native-dxil-package|opengl.missingCapabilities=opengl.backend.native-glsl-package")
