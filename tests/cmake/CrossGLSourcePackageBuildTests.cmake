set(CROSSGL_FAKE_SHADER_TOOL_SCRIPT
  "${CMAKE_CURRENT_SOURCE_DIR}/tests/toolchain/FakeShaderTool.cmake")

function(crossgl_configure_fake_shader_tool out_dir tool_name behavior)
  set(tool_instance "")
  if(ARGC GREATER 3)
    set(tool_instance "-${ARGV3}")
  endif()
  set(tool_dir
      "${CMAKE_CURRENT_BINARY_DIR}/fake-toolchain/${tool_name}-${behavior}${tool_instance}")
  file(MAKE_DIRECTORY "${tool_dir}")
  set(tool_log "${tool_dir}/${tool_name}.log")
  file(REMOVE "${tool_log}")

  if(WIN32)
    file(TO_NATIVE_PATH "${CMAKE_COMMAND}" native_cmake_command)
    file(TO_NATIVE_PATH "${CROSSGL_FAKE_SHADER_TOOL_SCRIPT}"
         native_fake_tool_script)
    file(WRITE "${tool_dir}/${tool_name}.cmd"
         "@echo off\n"
         "\"${native_cmake_command}\" -DFAKE_TOOL_NAME=${tool_name} -DFAKE_TOOL_BEHAVIOR=${behavior} -DFAKE_TOOL_LOG=\"${tool_log}\" -P \"${native_fake_tool_script}\" -- %*\n"
         "exit /b %ERRORLEVEL%\n")
  else()
    file(WRITE "${tool_dir}/${tool_name}"
         "#!/bin/sh\n"
         "exec \"${CMAKE_COMMAND}\" -DFAKE_TOOL_NAME=${tool_name} -DFAKE_TOOL_BEHAVIOR=${behavior} -DFAKE_TOOL_LOG=\"${tool_log}\" -P \"${CROSSGL_FAKE_SHADER_TOOL_SCRIPT}\" -- \"$@\"\n")
    file(CHMOD "${tool_dir}/${tool_name}"
         PERMISSIONS
           OWNER_READ OWNER_WRITE OWNER_EXECUTE
           GROUP_READ GROUP_EXECUTE
           WORLD_READ WORLD_EXECUTE)
  endif()

  set(${out_dir} "${tool_dir}" PARENT_SCOPE)
endfunction()

crossgl_configure_fake_shader_tool(CROSSGL_FAKE_DXC_SUCCESS_DIR dxc success)
crossgl_configure_fake_shader_tool(CROSSGL_FAKE_DXC_FAILURE_DIR dxc failure)
crossgl_configure_fake_shader_tool(CROSSGL_FAKE_DXC_O0_SUCCESS_DIR dxc
                                   success o0)
crossgl_configure_fake_shader_tool(CROSSGL_FAKE_DXC_O2_SUCCESS_DIR dxc
                                   success o2)
crossgl_configure_fake_shader_tool(CROSSGL_FAKE_DXC_GRAPHICS_SUCCESS_DIR dxc
                                   success graphics)
crossgl_configure_fake_shader_tool(CROSSGL_FAKE_DXC_GRAPHICS_FAILURE_DIR dxc
                                   failure graphics)
crossgl_configure_fake_shader_tool(CROSSGL_FAKE_GLSLANG_SUCCESS_DIR
                                   glslangValidator success)
crossgl_configure_fake_shader_tool(CROSSGL_FAKE_GLSLANG_FAILURE_DIR
                                   glslangValidator failure)
crossgl_configure_fake_shader_tool(CROSSGL_FAKE_GLSLANG_FRAGMENT_FAILURE_DIR
                                   glslangValidator fragment-failure)
set(CROSSGL_FAKE_TOOL_UNAVAILABLE_DIR
    "${CMAKE_CURRENT_BINARY_DIR}/fake-toolchain/unavailable")
file(MAKE_DIRECTORY "${CROSSGL_FAKE_TOOL_UNAVAILABLE_DIR}")

add_test(NAME cglc_build_directx_storage_buffer_source_package
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_STORAGE_BUFFER_COMPUTE_SHADER}
    -DTARGET=directx
    -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-directx-storage-buffer-source.cglb
    -DMODE=source-package-build
    -DEXPECTED_SOURCE=backend/directx/StorageBufferComputeShader.hlsl
    -DEXPECTED_SOURCE_SNIPPET=RWStructuredBuffer
    "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=directx|module=StorageBufferComputeShader|nativeBinary=backend/directx/StorageBufferComputeShader.dxil"
    "-DEXPECTED_REFLECTION_TARGET_FIELDS=values.sourceType=float*|values.hlslType=RWStructuredBuffer<float>|values.bindingClass=uav|values.descriptorType=UAV|values.argumentIndex=0"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_build_directx_resource_group_layout_alias_source_package
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_RESOURCE_GROUP_ALIAS_SHADER}
    -DTARGET=directx
    -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-directx-resource-group-alias-source.cglb
    -DMODE=source-package-build
    -DEXPECTED_SOURCE=backend/directx/ResourceGroupAliasShader.hlsl
    "-DEXPECTED_SOURCE_SNIPPET=register(b2, space1)"
    "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=directx|module=ResourceGroupAliasShader|nativeBinary=backend/directx/ResourceGroupAliasShader.dxil|resources.0.name=materialParams|resources.0.kind=uniform|resources.0.type=Params|resources.0.set=1|resources.0.binding=2|resources.1.name=values|resources.1.kind=buffer|resources.1.type=float*|resources.1.set=0|resources.1.binding=0"
    "-DEXPECTED_REFLECTION_JSON_ARRAY_LENGTHS=resources=2|targetResourceBindings=2|workgroupSizes=1"
    "-DEXPECTED_REFLECTION_TARGET_FIELDS=materialParams.sourceType=Params|materialParams.hlslType=ConstantBuffer<Params>|materialParams.bindingClass=constant-buffer|materialParams.descriptorType=CBV|materialParams.argumentIndex=2|materialParams.set=1|materialParams.binding=2|values.sourceType=float*|values.hlslType=RWStructuredBuffer<float>|values.bindingClass=uav|values.descriptorType=UAV|values.argumentIndex=0|values.set=0|values.binding=0"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_build_directx_resource_register_layout_alias_source_package
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_RESOURCE_REGISTER_ALIAS_SHADER}
    -DTARGET=directx
    -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-directx-resource-register-alias-source.cglb
    -DMODE=source-package-build
    -DEXPECTED_SOURCE=backend/directx/ResourceRegisterAliasShader.hlsl
    "-DEXPECTED_SOURCE_SNIPPET=register(b3, space1)"
    "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=directx|module=ResourceRegisterAliasShader|nativeBinary=backend/directx/ResourceRegisterAliasShader.dxil|resources.0.name=materialParams|resources.0.kind=uniform|resources.0.type=Params|resources.0.set=1|resources.0.binding=2|resources.1.name=fallbackParams|resources.1.kind=uniform|resources.1.type=Params|resources.1.set=1|resources.1.binding=3|resources.2.name=values|resources.2.kind=buffer|resources.2.type=float*|resources.2.set=0|resources.2.binding=0"
    "-DEXPECTED_REFLECTION_JSON_ARRAY_LENGTHS=resources=3|targetResourceBindings=3|workgroupSizes=1"
    "-DEXPECTED_REFLECTION_TARGET_FIELDS=materialParams.sourceType=Params|materialParams.hlslType=ConstantBuffer<Params>|materialParams.bindingClass=constant-buffer|materialParams.descriptorType=CBV|materialParams.argumentIndex=2|materialParams.set=1|materialParams.binding=2|fallbackParams.sourceType=Params|fallbackParams.hlslType=ConstantBuffer<Params>|fallbackParams.bindingClass=constant-buffer|fallbackParams.descriptorType=CBV|fallbackParams.argumentIndex=3|fallbackParams.set=1|fallbackParams.binding=3|values.sourceType=float*|values.hlslType=RWStructuredBuffer<float>|values.bindingClass=uav|values.descriptorType=UAV|values.argumentIndex=0|values.set=0|values.binding=0"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_build_directx_resource_location_layout_alias_source_package
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_RESOURCE_LOCATION_ALIAS_SHADER}
    -DTARGET=directx
    -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-directx-resource-location-alias-source.cglb
    -DMODE=source-package-build
    -DEXPECTED_SOURCE=backend/directx/ResourceLocationAliasShader.hlsl
    "-DEXPECTED_SOURCE_SNIPPET=register(b2, space1)"
    "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=directx|module=ResourceLocationAliasShader|nativeBinary=backend/directx/ResourceLocationAliasShader.dxil|resources.0.name=materialParams|resources.0.kind=uniform|resources.0.type=Params|resources.0.set=1|resources.0.binding=2|resources.1.name=values|resources.1.kind=buffer|resources.1.type=float*|resources.1.set=0|resources.1.binding=0"
    "-DEXPECTED_REFLECTION_JSON_ARRAY_LENGTHS=resources=2|targetResourceBindings=2|workgroupSizes=1"
    "-DEXPECTED_REFLECTION_TARGET_FIELDS=materialParams.sourceType=Params|materialParams.hlslType=ConstantBuffer<Params>|materialParams.bindingClass=constant-buffer|materialParams.descriptorType=CBV|materialParams.argumentIndex=2|materialParams.set=1|materialParams.binding=2|values.sourceType=float*|values.hlslType=RWStructuredBuffer<float>|values.bindingClass=uav|values.descriptorType=UAV|values.argumentIndex=0|values.set=0|values.binding=0"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_build_directx_source_package_fake_dxc_success
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_STORAGE_BUFFER_COMPUTE_SHADER}
    -DTARGET=directx
    -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-directx-fake-dxc-success.cglb
    -DMODE=source-package-build
    -DTOOLCHAIN_PATH=${CROSSGL_FAKE_DXC_SUCCESS_DIR}
    -DTOOLCHAIN_DISABLE_FALLBACK=ON
    -DEXPECTED_SOURCE=backend/directx/StorageBufferComputeShader.hlsl
    -DEXPECTED_NATIVE_BINARY=backend/directx/StorageBufferComputeShader.dxil
    -DEXPECTED_NATIVE_BINARY_STATUS=emitted
    "-DEXPECTED_DIAGNOSTICS_JSON_FIELDS=diagnostics.0.severity=note|diagnostics.0.code=directx.source-package-emitted|diagnostics.1.severity=note|diagnostics.1.code=directx.dxil-emitted"
    "-DEXPECTED_DIAGNOSTICS_JSON_FIELD_CONTAINS=diagnostics.0.message=CrossGL opt-level O1 maps to DXC -O3|diagnostics.0.message=compute=cs_6_0|diagnostics.1.message=CrossGL opt-level O1 maps to DXC -O3|diagnostics.1.message=compute=cs_6_0"
    "-DEXPECTED_DIAGNOSTICS_JSON_ARRAY_LENGTHS=diagnostics=2"
    "-DEXPECTED_NATIVE_ARTIFACT_DESCRIPTOR_JSON_FIELDS=target=directx|binaryKind=directx.dxil|sourcePath=backend/directx/StorageBufferComputeShader.hlsl|sourceHash.algorithm=sha256|artifactPath=backend/directx/StorageBufferComputeShader.dxil|artifactHash.algorithm=sha256|optimizationLevel=O1|optimizationEvidence.requestedLevel=O1|optimizationEvidence.effectiveLevel=O3|optimizationEvidence.policy=crossgl-to-dxc-optimization-map|optimizationEvidence.status=applied|optimizationEvidence.tool=dxc|optimizationEvidence.toolFlag=-O3|validationStatus=not-run|nativeBinaryStatus=emitted"
    "-DEXPECTED_NATIVE_ARTIFACT_DESCRIPTOR_JSON_PATHS=sourceHash.value|artifactHash.value|sizeBytes"
    "-DEXPECTED_NATIVE_ARTIFACT_DESCRIPTOR_JSON_ARRAY_LENGTHS=toolchainProvenance.tools=2|validationDiagnostics=0"
    -DEXPECTED_TOOL_LOG=${CROSSGL_FAKE_DXC_SUCCESS_DIR}/dxc.log
    "-DEXPECTED_TOOL_LOG_CONTAINS=-O3 -T cs_6_0 -E compute_main -Fo|backend/directx/StorageBufferComputeShader.dxil|backend/directx/StorageBufferComputeShader.hlsl"
    -DEXPECTED_SECOND_TOOL_LOG=${CROSSGL_FAKE_DXC_SUCCESS_DIR}/dxc.log
    "-DEXPECTED_SECOND_TOOL_LOG_CONTAINS=backend/directx/StorageBufferComputeShader.dxil"
    -DEXPECTED_THIRD_TOOL_LOG=${CROSSGL_FAKE_DXC_SUCCESS_DIR}/dxc.log
    "-DEXPECTED_THIRD_TOOL_LOG_CONTAINS=backend/directx/StorageBufferComputeShader.hlsl"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_build_directx_source_package_opt_level_o0_fake_dxc
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_STORAGE_BUFFER_COMPUTE_SHADER}
    -DTARGET=directx
    -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-directx-fake-dxc-o0.cglb
    -DMODE=source-package-build
    -DTOOLCHAIN_PATH=${CROSSGL_FAKE_DXC_O0_SUCCESS_DIR}
    -DTOOLCHAIN_DISABLE_FALLBACK=ON
    -DOPT_LEVEL=O0
    -DEXPECTED_SOURCE=backend/directx/StorageBufferComputeShader.hlsl
    -DEXPECTED_NATIVE_BINARY=backend/directx/StorageBufferComputeShader.dxil
    -DEXPECTED_NATIVE_BINARY_STATUS=emitted
    "-DEXPECTED_DIAGNOSTICS_JSON_FIELD_CONTAINS=diagnostics.0.message=uses -O0|diagnostics.0.message=CrossGL opt-level O0 maps to DXC -O0|diagnostics.1.message=CrossGL opt-level O0 maps to DXC -O0|diagnostics.1.message=command profile: dxc -O0 -T cs_6_0 -E compute_main -Fo backend/directx/StorageBufferComputeShader.dxil backend/directx/StorageBufferComputeShader.hlsl"
    "-DEXPECTED_DIAGNOSTICS_JSON_ARRAY_LENGTHS=diagnostics=2"
    "-DEXPECTED_NATIVE_ARTIFACT_DESCRIPTOR_JSON_FIELDS=target=directx|binaryKind=directx.dxil|sourcePath=backend/directx/StorageBufferComputeShader.hlsl|artifactPath=backend/directx/StorageBufferComputeShader.dxil|optimizationLevel=O0|optimizationEvidence.requestedLevel=O0|optimizationEvidence.effectiveLevel=O0|optimizationEvidence.policy=crossgl-to-dxc-optimization-map|optimizationEvidence.status=applied|optimizationEvidence.tool=dxc|optimizationEvidence.toolFlag=-O0|validationStatus=not-run|nativeBinaryStatus=emitted"
    "-DEXPECTED_NATIVE_ARTIFACT_DESCRIPTOR_JSON_ARRAY_LENGTHS=toolchainProvenance.tools=2|validationDiagnostics=0"
    -DEXPECTED_TOOL_LOG=${CROSSGL_FAKE_DXC_O0_SUCCESS_DIR}/dxc.log
    "-DEXPECTED_TOOL_LOG_CONTAINS=-O0 -T cs_6_0 -E compute_main -Fo|backend/directx/StorageBufferComputeShader.dxil|backend/directx/StorageBufferComputeShader.hlsl"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_build_directx_source_package_opt_level_o2_fake_dxc
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_STORAGE_BUFFER_COMPUTE_SHADER}
    -DTARGET=directx
    -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-directx-fake-dxc-o2.cglb
    -DMODE=source-package-build
    -DTOOLCHAIN_PATH=${CROSSGL_FAKE_DXC_O2_SUCCESS_DIR}
    -DTOOLCHAIN_DISABLE_FALLBACK=ON
    -DOPT_LEVEL=O2
    -DEXPECTED_SOURCE=backend/directx/StorageBufferComputeShader.hlsl
    -DEXPECTED_NATIVE_BINARY=backend/directx/StorageBufferComputeShader.dxil
    -DEXPECTED_NATIVE_BINARY_STATUS=emitted
    "-DEXPECTED_DIAGNOSTICS_JSON_FIELD_CONTAINS=diagnostics.0.message=uses -O3|diagnostics.0.message=CrossGL opt-level O2 maps to DXC -O3|diagnostics.1.message=CrossGL opt-level O2 maps to DXC -O3|diagnostics.1.message=command profile: dxc -O3 -T cs_6_0 -E compute_main -Fo backend/directx/StorageBufferComputeShader.dxil backend/directx/StorageBufferComputeShader.hlsl"
    "-DEXPECTED_DIAGNOSTICS_JSON_ARRAY_LENGTHS=diagnostics=2"
    "-DEXPECTED_NATIVE_ARTIFACT_DESCRIPTOR_JSON_FIELDS=target=directx|binaryKind=directx.dxil|sourcePath=backend/directx/StorageBufferComputeShader.hlsl|artifactPath=backend/directx/StorageBufferComputeShader.dxil|optimizationLevel=O2|optimizationEvidence.requestedLevel=O2|optimizationEvidence.effectiveLevel=O3|optimizationEvidence.policy=crossgl-to-dxc-optimization-map|optimizationEvidence.status=applied|optimizationEvidence.tool=dxc|optimizationEvidence.toolFlag=-O3|validationStatus=not-run|nativeBinaryStatus=emitted"
    "-DEXPECTED_NATIVE_ARTIFACT_DESCRIPTOR_JSON_ARRAY_LENGTHS=toolchainProvenance.tools=2|validationDiagnostics=0"
    -DEXPECTED_TOOL_LOG=${CROSSGL_FAKE_DXC_O2_SUCCESS_DIR}/dxc.log
    "-DEXPECTED_TOOL_LOG_CONTAINS=-O3 -T cs_6_0 -E compute_main -Fo|backend/directx/StorageBufferComputeShader.dxil|backend/directx/StorageBufferComputeShader.hlsl"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_build_directx_source_package_fake_dxc_tool_failure
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_STORAGE_BUFFER_COMPUTE_SHADER}
    -DTARGET=directx
    -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-directx-fake-dxc-failure.cglb
    -DMODE=source-package-build
    -DTOOLCHAIN_PATH=${CROSSGL_FAKE_DXC_FAILURE_DIR}
    -DTOOLCHAIN_DISABLE_FALLBACK=ON
    -DEXPECTED_SOURCE=backend/directx/StorageBufferComputeShader.hlsl
    -DEXPECTED_NATIVE_BINARY_ABSENT=backend/directx/StorageBufferComputeShader.dxil
    -DEXPECTED_NATIVE_BINARY_STATUS=planned
    "-DEXPECTED_DIAGNOSTICS_JSON_FIELDS=diagnostics.0.severity=note|diagnostics.0.code=directx.source-package-emitted|diagnostics.1.severity=warning|diagnostics.1.code=directx.dxc-failed|diagnostics.2.severity=warning|diagnostics.2.code=directx.source-package-only"
    "-DEXPECTED_DIAGNOSTICS_JSON_FIELD_CONTAINS=diagnostics.0.message=CrossGL opt-level O1 maps to DXC -O3|diagnostics.0.message=compute=cs_6_0|diagnostics.1.message=compute=cs_6_0|diagnostics.1.message=exit status:|diagnostics.1.message=CrossGL opt-level O1 maps to DXC -O3|diagnostics.1.message=command profile: dxc -O3 -T cs_6_0 -E compute_main -Fo backend/directx/StorageBufferComputeShader.dxil backend/directx/StorageBufferComputeShader.hlsl|diagnostics.1.message=dxc diagnostics: stderr:|diagnostics.1.message=fake dxc failure|diagnostics.1.message=partial DXIL output was discarded|diagnostics.2.message=compute=cs_6_0|diagnostics.2.message=planned native binary artifact: backend/directx/StorageBufferComputeShader.dxil"
    "-DEXPECTED_DIAGNOSTICS_JSON_ARRAY_LENGTHS=diagnostics=3"
    -DEXPECTED_TOOL_LOG=${CROSSGL_FAKE_DXC_FAILURE_DIR}/dxc.log
    "-DEXPECTED_TOOL_LOG_CONTAINS=-O3 -T cs_6_0 -E compute_main -Fo|backend/directx/StorageBufferComputeShader.dxil|backend/directx/StorageBufferComputeShader.hlsl"
    -DEXPECTED_SECOND_TOOL_LOG=${CROSSGL_FAKE_DXC_FAILURE_DIR}/dxc.log
    "-DEXPECTED_SECOND_TOOL_LOG_CONTAINS=backend/directx/StorageBufferComputeShader.dxil"
    -DEXPECTED_THIRD_TOOL_LOG=${CROSSGL_FAKE_DXC_FAILURE_DIR}/dxc.log
    "-DEXPECTED_THIRD_TOOL_LOG_CONTAINS=backend/directx/StorageBufferComputeShader.hlsl"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_build_directx_source_package_fake_dxc_unavailable
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_STORAGE_BUFFER_COMPUTE_SHADER}
    -DTARGET=directx
    -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-directx-fake-dxc-unavailable.cglb
    -DMODE=source-package-build
    -DTOOLCHAIN_PATH=${CROSSGL_FAKE_TOOL_UNAVAILABLE_DIR}
    -DTOOLCHAIN_DISABLE_FALLBACK=ON
    -DEXPECTED_SOURCE=backend/directx/StorageBufferComputeShader.hlsl
    -DEXPECTED_NATIVE_BINARY_ABSENT=backend/directx/StorageBufferComputeShader.dxil
    -DEXPECTED_NATIVE_BINARY_STATUS=planned
    "-DEXPECTED_DIAGNOSTICS_JSON_FIELDS=diagnostics.0.severity=note|diagnostics.0.code=directx.source-package-emitted|diagnostics.1.severity=warning|diagnostics.1.code=directx.source-package-only"
    "-DEXPECTED_DIAGNOSTICS_JSON_FIELD_CONTAINS=diagnostics.0.message=CrossGL opt-level O1 maps to DXC -O3|diagnostics.0.message=compute=cs_6_0|diagnostics.1.message=dxc was not found|diagnostics.1.message=no dxc command was invoked|diagnostics.1.message=CrossGL opt-level O1 maps to DXC -O3|diagnostics.1.message=compute=cs_6_0"
    "-DEXPECTED_DIAGNOSTICS_JSON_ARRAY_LENGTHS=diagnostics=2"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
crossgl_label_optional_native_policy_test(
  cglc_build_directx_source_package_fake_dxc_tool_failure directx)
crossgl_label_optional_native_policy_test(
  cglc_build_directx_source_package_fake_dxc_unavailable directx)
set(CROSSGL_DIRECTX_COMPUTE_INVOCATION_BUILTIN_SOURCE_SNIPPET [=[RWStructuredBuffer<uint3> ids : register(u0, space0);

[numthreads(4, 2, 1)]
void compute_main(uint3 crossgl_GlobalInvocationID : SV_DispatchThreadID, uint3 crossgl_LocalInvocationID : SV_GroupThreadID, uint3 crossgl_WorkGroupID : SV_GroupID) {
  uint3 globalId = crossgl_GlobalInvocationID;
  uint3 localId = crossgl_LocalInvocationID;
  uint3 groupId = crossgl_WorkGroupID;
  ids[0] = globalId;]=])
add_test(NAME cglc_build_directx_compute_invocation_builtins_source_package
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CMAKE_CURRENT_SOURCE_DIR}/tests/directx/fixtures/DirectXComputeInvocationBuiltinShader.cgl
    -DTARGET=directx
    -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-directx-compute-invocation-builtin-source.cglb
    -DMODE=source-package-build
    -DEXPECTED_SOURCE=backend/directx/DirectXComputeInvocationBuiltinShader.hlsl
    "-DEXPECTED_SOURCE_SNIPPET=${CROSSGL_DIRECTX_COMPUTE_INVOCATION_BUILTIN_SOURCE_SNIPPET}"
    "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=directx|module=DirectXComputeInvocationBuiltinShader|nativeBinary=backend/directx/DirectXComputeInvocationBuiltinShader.dxil|resources.0.name=ids|resources.0.kind=buffer|resources.0.type=uvec3*|resources.0.binding=0|workgroupSizes.0.entryPoint=compute_main|workgroupSizes.0.x=4|workgroupSizes.0.y=2|workgroupSizes.0.z=1"
    "-DEXPECTED_REFLECTION_JSON_ARRAY_LENGTHS=resources=1|targetResourceBindings=1|workgroupSizes=1"
    "-DEXPECTED_REFLECTION_TARGET_FIELDS=ids.stage=compute|ids.entryPoint=compute_main|ids.sourceType=uvec3*|ids.hlslType=RWStructuredBuffer<uint3>|ids.bindingClass=uav|ids.descriptorType=UAV|ids.argumentIndex=0"
    "-DEXPECTED_REFLECTION_FEATURE_FIELDS=hlsl-lowering.kind=backend|native-dxil-package.kind=backend|dxc.kind=toolchain|dxil-validator.kind=validation|compute-kernel.kind=stage|workgroup-size.kind=execution|storage-buffer.kind=resource|vector-storage-buffer.kind=layout|local-declaration.kind=operation|index-access.kind=operation|storage-buffer-write.kind=operation"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
set(CROSSGL_DIRECTX_WORKGROUP_SHARED_SOURCE_SNIPPET [=[groupshared float tile[TILE_SIZE];

[numthreads(8, 2, 1)]
void compute_main(uint3 crossgl_GlobalInvocationID : SV_DispatchThreadID) {
  tile[0] = 1.0;
  float first = tile[0];
  tile[1] = first + 1.0;]=])
add_test(NAME cglc_build_directx_workgroup_shared_source_package
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CMAKE_CURRENT_SOURCE_DIR}/tests/directx/fixtures/DirectXWorkgroupSharedShader.cgl
    -DTARGET=directx
    -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-directx-workgroup-shared.cglb
    -DMODE=source-package-build
    -DEXPECTED_SOURCE=backend/directx/DirectXWorkgroupSharedShader.hlsl
    "-DEXPECTED_SOURCE_SNIPPET=${CROSSGL_DIRECTX_WORKGROUP_SHARED_SOURCE_SNIPPET}"
    "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=directx|module=DirectXWorkgroupSharedShader|nativeBinary=backend/directx/DirectXWorkgroupSharedShader.dxil|functionConstants.0.name=TILE_SIZE|functionConstants.0.value=8|resources.0.name=tile|resources.0.kind=shared|resources.0.type=float[TILE_SIZE]|resources.0.addressSpace=shared|resources.0.arrayDimensions.0.source=TILE_SIZE|resources.0.arrayDimensions.0.elementCount=8|workgroupSizes.0.entryPoint=compute_main|workgroupSizes.0.x=8|workgroupSizes.0.y=2|workgroupSizes.0.z=1|workgroupSizes.0.sourceX=TILE_SIZE|workgroupSizes.0.sourceY=2|workgroupSizes.0.sourceZ=1"
    "-DEXPECTED_REFLECTION_JSON_ARRAY_LENGTHS=resources=1|targetResourceBindings=1|functionConstants=1|workgroupSizes=1"
    "-DEXPECTED_REFLECTION_TARGET_FIELDS=tile.stage=compute|tile.entryPoint=compute_main|tile.sourceType=float[TILE_SIZE]|tile.hlslType=float|tile.addressSpace=groupshared|tile.abi=groupsharedLocal|tile.bindingClass=groupshared|tile.arraySize=TILE_SIZE|tile.arrayElementCount=8|tile.arrayDimensions.0.source=TILE_SIZE|tile.arrayDimensions.0.elementCount=8"
    "-DEXPECTED_REFLECTION_FEATURE_FIELDS=hlsl-lowering.kind=backend|native-dxil-package.kind=backend|dxc.kind=toolchain|dxil-validator.kind=validation|compute-kernel.kind=stage|workgroup-size.kind=execution|workgroup-shared-memory.kind=resource|fixed-array.kind=layout|scalar-vector-elements.kind=array|index-access.kind=operation|local-declaration.kind=operation|scalar-arithmetic.kind=operation"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
set(CROSSGL_DIRECTX_WORKGROUP_BARRIER_SOURCE_SNIPPET [=[RWStructuredBuffer<float> values : register(u0, space0);
groupshared float tile[4];

[numthreads(4, 1, 1)]
void compute_main(uint3 crossgl_GlobalInvocationID : SV_DispatchThreadID) {
  tile[0] = values[0];
  GroupMemoryBarrierWithGroupSync();
  tile[1] = tile[0] + 1.0;
  GroupMemoryBarrierWithGroupSync();
  values[0] = tile[1];]=])
add_test(NAME cglc_build_directx_workgroup_barrier_source_package
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CMAKE_CURRENT_SOURCE_DIR}/tests/directx/fixtures/DirectXWorkgroupBarrierShader.cgl
    -DTARGET=directx
    -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-directx-workgroup-barrier.cglb
    -DMODE=source-package-build
    -DEXPECTED_SOURCE=backend/directx/DirectXWorkgroupBarrierShader.hlsl
    "-DEXPECTED_SOURCE_SNIPPET=${CROSSGL_DIRECTX_WORKGROUP_BARRIER_SOURCE_SNIPPET}"
    "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=directx|module=DirectXWorkgroupBarrierShader|nativeBinary=backend/directx/DirectXWorkgroupBarrierShader.dxil|resources.0.name=values|resources.0.kind=buffer|resources.0.type=float*|resources.0.binding=0|resources.1.name=tile|resources.1.kind=shared|resources.1.type=float[4]|resources.1.addressSpace=shared|resources.1.arrayDimensions.0.source=4|resources.1.arrayDimensions.0.elementCount=4|workgroupSizes.0.entryPoint=compute_main|workgroupSizes.0.x=4|workgroupSizes.0.y=1|workgroupSizes.0.z=1"
    "-DEXPECTED_REFLECTION_JSON_ARRAY_LENGTHS=resources=2|targetResourceBindings=2|workgroupSizes=1"
    "-DEXPECTED_REFLECTION_TARGET_FIELDS=values.stage=compute|values.entryPoint=compute_main|values.sourceType=float*|values.hlslType=RWStructuredBuffer<float>|values.bindingClass=uav|values.descriptorType=UAV|values.argumentIndex=0|tile.stage=compute|tile.entryPoint=compute_main|tile.sourceType=float[4]|tile.hlslType=float|tile.addressSpace=groupshared|tile.abi=groupsharedLocal|tile.bindingClass=groupshared|tile.arraySize=4|tile.arrayElementCount=4|tile.arrayDimensions.0.source=4|tile.arrayDimensions.0.elementCount=4"
    "-DEXPECTED_REFLECTION_FEATURE_FIELDS=hlsl-lowering.kind=backend|native-dxil-package.kind=backend|dxc.kind=toolchain|dxil-validator.kind=validation|compute-kernel.kind=stage|workgroup-size.kind=execution|storage-buffer.kind=resource|workgroup-shared-memory.kind=resource|fixed-array.kind=layout|scalar-vector-elements.kind=array|index-access.kind=operation|storage-buffer-read.kind=operation|storage-buffer-write.kind=operation|scalar-arithmetic.kind=operation"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
set(CROSSGL_DIRECTX_ATOMIC_ADD_SOURCE_SNIPPET [=[RWStructuredBuffer<int> counters : register(u0, space0);
groupshared uint tile[GROUP_SIZE];

[numthreads(4, 1, 1)]
void compute_main(uint3 crossgl_GlobalInvocationID : SV_DispatchThreadID, uint3 crossgl_LocalInvocationID : SV_GroupThreadID) {
  int index = int(crossgl_GlobalInvocationID.x);
  int delta = int(crossgl_LocalInvocationID.x) + 1;
  InterlockedAdd(counters[index], delta);
  InterlockedAdd(tile[crossgl_LocalInvocationID.x], crossgl_LocalInvocationID.x);]=])
add_test(NAME cglc_build_directx_atomic_add_source_package
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CMAKE_CURRENT_SOURCE_DIR}/tests/directx/fixtures/DirectXAtomicAddShader.cgl
    -DTARGET=directx
    -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-directx-atomic-add.cglb
    -DMODE=source-package-build
    -DEXPECTED_SOURCE=backend/directx/DirectXAtomicAddShader.hlsl
    "-DEXPECTED_SOURCE_SNIPPET=${CROSSGL_DIRECTX_ATOMIC_ADD_SOURCE_SNIPPET}"
    "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=directx|module=DirectXAtomicAddShader|nativeBinary=backend/directx/DirectXAtomicAddShader.dxil|functionConstants.0.name=GROUP_SIZE|functionConstants.0.value=4|resources.0.name=counters|resources.0.kind=buffer|resources.0.type=atomic<int>*|resources.0.binding=0|resources.1.name=tile|resources.1.kind=shared|resources.1.type=atomic<uint>[GROUP_SIZE]|resources.1.addressSpace=shared|resources.1.arrayDimensions.0.source=GROUP_SIZE|resources.1.arrayDimensions.0.elementCount=4|workgroupSizes.0.entryPoint=compute_main|workgroupSizes.0.x=4|workgroupSizes.0.y=1|workgroupSizes.0.z=1|workgroupSizes.0.sourceX=GROUP_SIZE|workgroupSizes.0.sourceY=1|workgroupSizes.0.sourceZ=1"
    "-DEXPECTED_REFLECTION_JSON_ARRAY_LENGTHS=resources=2|targetResourceBindings=2|functionConstants=1|workgroupSizes=1"
    "-DEXPECTED_REFLECTION_TARGET_FIELDS=counters.stage=compute|counters.entryPoint=compute_main|counters.sourceType=atomic<int>*|counters.hlslType=RWStructuredBuffer<int>|counters.addressSpace=unordered-access|counters.abi=registerBinding|counters.bindingClass=uav|counters.descriptorType=UAV|counters.argumentIndex=0|counters.set=0|counters.binding=0|tile.stage=compute|tile.entryPoint=compute_main|tile.sourceType=atomic<uint>[GROUP_SIZE]|tile.hlslType=uint|tile.addressSpace=groupshared|tile.abi=groupsharedLocal|tile.bindingClass=groupshared|tile.arraySize=GROUP_SIZE|tile.arrayElementCount=4|tile.arrayDimensions.0.source=GROUP_SIZE|tile.arrayDimensions.0.elementCount=4"
    "-DEXPECTED_REFLECTION_FEATURE_FIELDS=hlsl-lowering.kind=backend|native-dxil-package.kind=backend|dxc.kind=toolchain|dxil-validator.kind=validation|compute-kernel.kind=stage|workgroup-size.kind=execution|storage-buffer.kind=resource|atomic-integer.kind=type|workgroup-shared-memory.kind=resource|fixed-array.kind=layout|descriptor-array.kind=resource|local-declaration.kind=operation|scalar-constructor.kind=operation|scalar-arithmetic.kind=operation|atomic-add.kind=operation|index-access.kind=operation"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
set(CROSSGL_DIRECTX_ATOMIC_ADD_RETURN_SOURCE_SNIPPET [=[int oldCounter;
  InterlockedAdd(counters[index], delta, oldCounter);
  InterlockedAdd(counters[index], 1, oldCounter);
  uint oldUnsigned;
  InterlockedAdd(unsignedCounters[unsignedIndex], unsignedDelta, oldUnsigned);
  int oldShared;
  InterlockedAdd(tile[index], 1, oldShared);
  uint oldUnsignedShared;
  InterlockedAdd(unsignedTile[unsignedIndex], unsignedDelta, oldUnsignedShared);
  InterlockedAdd(counters[index], delta);]=])
add_test(NAME cglc_build_directx_atomic_add_return_source_package
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CMAKE_CURRENT_SOURCE_DIR}/tests/directx/fixtures/DirectXAtomicAddReturnShader.cgl
    -DTARGET=directx
    -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-directx-atomic-add-return.cglb
    -DMODE=source-package-build
    -DEXPECTED_SOURCE=backend/directx/DirectXAtomicAddReturnShader.hlsl
    "-DEXPECTED_SOURCE_SNIPPET=${CROSSGL_DIRECTX_ATOMIC_ADD_RETURN_SOURCE_SNIPPET}"
    "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=directx|module=DirectXAtomicAddReturnShader|nativeBinary=backend/directx/DirectXAtomicAddReturnShader.dxil|functionConstants.0.name=GROUP_SIZE|functionConstants.0.value=4|resources.0.name=counters|resources.0.kind=buffer|resources.0.type=atomic<int>*|resources.0.binding=0|resources.1.name=unsignedCounters|resources.1.kind=buffer|resources.1.type=atomic<uint>*|resources.1.binding=1|resources.2.name=observed|resources.2.kind=buffer|resources.2.type=int*|resources.2.binding=2|resources.3.name=unsignedObserved|resources.3.kind=buffer|resources.3.type=uint*|resources.3.binding=3|resources.4.name=tile|resources.4.kind=shared|resources.4.type=atomic<int>[GROUP_SIZE]|resources.4.addressSpace=shared|resources.5.name=unsignedTile|resources.5.kind=shared|resources.5.type=atomic<uint>[GROUP_SIZE]|resources.5.addressSpace=shared|workgroupSizes.0.entryPoint=compute_main|workgroupSizes.0.x=4|workgroupSizes.0.y=1|workgroupSizes.0.z=1|workgroupSizes.0.sourceX=GROUP_SIZE|workgroupSizes.0.sourceY=1|workgroupSizes.0.sourceZ=1"
    "-DEXPECTED_REFLECTION_TARGET_FIELDS=counters.hlslType=RWStructuredBuffer<int>|counters.bindingClass=uav|counters.argumentIndex=0|unsignedCounters.hlslType=RWStructuredBuffer<uint>|unsignedCounters.bindingClass=uav|unsignedCounters.argumentIndex=1|observed.hlslType=RWStructuredBuffer<int>|observed.bindingClass=uav|observed.argumentIndex=2|unsignedObserved.hlslType=RWStructuredBuffer<uint>|unsignedObserved.bindingClass=uav|unsignedObserved.argumentIndex=3|tile.hlslType=int|tile.bindingClass=groupshared|tile.arrayElementCount=4|unsignedTile.hlslType=uint|unsignedTile.bindingClass=groupshared|unsignedTile.arrayElementCount=4"
    "-DEXPECTED_REFLECTION_JSON_ARRAY_LENGTHS=resources=6|targetResourceBindings=6|functionConstants=1|workgroupSizes=1"
    "-DEXPECTED_REFLECTION_FEATURE_FIELDS=hlsl-lowering.kind=backend|native-dxil-package.kind=backend|dxc.kind=toolchain|dxil-validator.kind=validation|compute-kernel.kind=stage|workgroup-size.kind=execution|storage-buffer.kind=resource|atomic-integer.kind=type|workgroup-shared-memory.kind=resource|fixed-array.kind=layout|descriptor-array.kind=resource|local-declaration.kind=operation|scalar-constructor.kind=operation|scalar-arithmetic.kind=operation|storage-buffer-read.kind=operation|atomic-add.kind=operation|index-access.kind=operation|storage-buffer-write.kind=operation"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
set(CROSSGL_DIRECTX_ATOMIC_MINMAX_SOURCE_SNIPPET [=[RWStructuredBuffer<int> counters : register(u0, space0);
RWStructuredBuffer<uint> unsignedCounters : register(u1, space0);
groupshared int tile[GROUP_SIZE];
groupshared uint unsignedTile[GROUP_SIZE];

[numthreads(4, 1, 1)]
void compute_main(uint3 crossgl_GlobalInvocationID : SV_DispatchThreadID, uint3 crossgl_LocalInvocationID : SV_GroupThreadID) {
  int index = int(crossgl_GlobalInvocationID.x);
  uint unsignedIndex = crossgl_LocalInvocationID.x;
  int value = int(crossgl_LocalInvocationID.x) + 1;
  uint unsignedValue = unsignedIndex + 1;
  InterlockedMin(counters[index], value);
  InterlockedMax(counters[index], value);
  InterlockedMin(unsignedCounters[unsignedIndex], unsignedValue);
  InterlockedMax(unsignedCounters[unsignedIndex], unsignedValue);
  InterlockedMin(tile[index], value);
  InterlockedMax(unsignedTile[unsignedIndex], unsignedValue);]=])
add_test(NAME cglc_build_directx_atomic_minmax_source_package
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CMAKE_CURRENT_SOURCE_DIR}/tests/directx/fixtures/DirectXAtomicMinMaxShader.cgl
    -DTARGET=directx
    -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-directx-atomic-minmax.cglb
    -DMODE=source-package-build
    -DEXPECTED_SOURCE=backend/directx/DirectXAtomicMinMaxShader.hlsl
    "-DEXPECTED_SOURCE_SNIPPET=${CROSSGL_DIRECTX_ATOMIC_MINMAX_SOURCE_SNIPPET}"
    "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=directx|module=DirectXAtomicMinMaxShader|nativeBinary=backend/directx/DirectXAtomicMinMaxShader.dxil|functionConstants.0.name=GROUP_SIZE|functionConstants.0.value=4|resources.0.name=counters|resources.0.kind=buffer|resources.0.type=atomic<int>*|resources.0.binding=0|resources.1.name=unsignedCounters|resources.1.kind=buffer|resources.1.type=atomic<uint>*|resources.1.binding=1|resources.2.name=tile|resources.2.kind=shared|resources.2.type=atomic<int>[GROUP_SIZE]|resources.2.addressSpace=shared|resources.3.name=unsignedTile|resources.3.kind=shared|resources.3.type=atomic<uint>[GROUP_SIZE]|resources.3.addressSpace=shared|workgroupSizes.0.entryPoint=compute_main|workgroupSizes.0.x=4|workgroupSizes.0.y=1|workgroupSizes.0.z=1|workgroupSizes.0.sourceX=GROUP_SIZE|workgroupSizes.0.sourceY=1|workgroupSizes.0.sourceZ=1"
    "-DEXPECTED_REFLECTION_JSON_ARRAY_LENGTHS=resources=4|targetResourceBindings=4|functionConstants=1|workgroupSizes=1"
    "-DEXPECTED_REFLECTION_TARGET_FIELDS=counters.hlslType=RWStructuredBuffer<int>|counters.bindingClass=uav|counters.argumentIndex=0|unsignedCounters.hlslType=RWStructuredBuffer<uint>|unsignedCounters.bindingClass=uav|unsignedCounters.argumentIndex=1|tile.hlslType=int|tile.bindingClass=groupshared|tile.arrayElementCount=4|unsignedTile.hlslType=uint|unsignedTile.bindingClass=groupshared|unsignedTile.arrayElementCount=4"
    "-DEXPECTED_REFLECTION_FEATURE_FIELDS=hlsl-lowering.kind=backend|native-dxil-package.kind=backend|dxc.kind=toolchain|dxil-validator.kind=validation|compute-kernel.kind=stage|workgroup-size.kind=execution|storage-buffer.kind=resource|atomic-integer.kind=type|workgroup-shared-memory.kind=resource|fixed-array.kind=layout|descriptor-array.kind=resource|local-declaration.kind=operation|scalar-constructor.kind=operation|scalar-arithmetic.kind=operation|atomic-min.kind=operation|index-access.kind=operation|atomic-max.kind=operation"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
set(CROSSGL_DIRECTX_ATOMIC_MINMAX_RETURN_SOURCE_SNIPPET [=[int oldMin;
  InterlockedMin(counters[index], value, oldMin);
  int oldMax;
  InterlockedMax(counters[index], value, oldMax);
  InterlockedMin(counters[index], 1, oldMin);
  InterlockedMax(counters[index], 2, oldMax);
  uint oldUnsignedMin;
  InterlockedMin(unsignedCounters[unsignedIndex], unsignedValue, oldUnsignedMin);
  uint oldUnsignedMax;
  InterlockedMax(unsignedCounters[unsignedIndex], unsignedValue, oldUnsignedMax);
  int oldShared;
  InterlockedMin(tile[index], value, oldShared);
  uint oldUnsignedShared;
  InterlockedMax(unsignedTile[unsignedIndex], unsignedValue, oldUnsignedShared);
  InterlockedMin(counters[index], value);
  InterlockedMax(unsignedCounters[unsignedIndex], unsignedValue);]=])
add_test(NAME cglc_build_directx_atomic_minmax_return_source_package
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CMAKE_CURRENT_SOURCE_DIR}/tests/directx/fixtures/DirectXAtomicMinMaxReturnShader.cgl
    -DTARGET=directx
    -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-directx-atomic-minmax-return.cglb
    -DMODE=source-package-build
    -DEXPECTED_SOURCE=backend/directx/DirectXAtomicMinMaxReturnShader.hlsl
    "-DEXPECTED_SOURCE_SNIPPET=${CROSSGL_DIRECTX_ATOMIC_MINMAX_RETURN_SOURCE_SNIPPET}"
    "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=directx|module=DirectXAtomicMinMaxReturnShader|nativeBinary=backend/directx/DirectXAtomicMinMaxReturnShader.dxil|functionConstants.0.name=GROUP_SIZE|functionConstants.0.value=4|resources.0.name=counters|resources.0.kind=buffer|resources.0.type=atomic<int>*|resources.0.binding=0|resources.1.name=unsignedCounters|resources.1.kind=buffer|resources.1.type=atomic<uint>*|resources.1.binding=1|resources.2.name=observed|resources.2.kind=buffer|resources.2.type=int*|resources.2.binding=2|resources.3.name=unsignedObserved|resources.3.kind=buffer|resources.3.type=uint*|resources.3.binding=3|resources.4.name=tile|resources.4.kind=shared|resources.4.type=atomic<int>[GROUP_SIZE]|resources.4.addressSpace=shared|resources.5.name=unsignedTile|resources.5.kind=shared|resources.5.type=atomic<uint>[GROUP_SIZE]|resources.5.addressSpace=shared|workgroupSizes.0.entryPoint=compute_main|workgroupSizes.0.x=4|workgroupSizes.0.y=1|workgroupSizes.0.z=1|workgroupSizes.0.sourceX=GROUP_SIZE|workgroupSizes.0.sourceY=1|workgroupSizes.0.sourceZ=1"
    "-DEXPECTED_REFLECTION_TARGET_FIELDS=counters.hlslType=RWStructuredBuffer<int>|counters.bindingClass=uav|counters.argumentIndex=0|unsignedCounters.hlslType=RWStructuredBuffer<uint>|unsignedCounters.bindingClass=uav|unsignedCounters.argumentIndex=1|observed.hlslType=RWStructuredBuffer<int>|observed.bindingClass=uav|observed.argumentIndex=2|unsignedObserved.hlslType=RWStructuredBuffer<uint>|unsignedObserved.bindingClass=uav|unsignedObserved.argumentIndex=3|tile.hlslType=int|tile.bindingClass=groupshared|tile.arrayElementCount=4|unsignedTile.hlslType=uint|unsignedTile.bindingClass=groupshared|unsignedTile.arrayElementCount=4"
    "-DEXPECTED_REFLECTION_JSON_ARRAY_LENGTHS=resources=6|targetResourceBindings=6|functionConstants=1|workgroupSizes=1"
    "-DEXPECTED_REFLECTION_FEATURE_FIELDS=hlsl-lowering.kind=backend|native-dxil-package.kind=backend|dxc.kind=toolchain|dxil-validator.kind=validation|compute-kernel.kind=stage|workgroup-size.kind=execution|storage-buffer.kind=resource|atomic-integer.kind=type|workgroup-shared-memory.kind=resource|fixed-array.kind=layout|descriptor-array.kind=resource|local-declaration.kind=operation|scalar-constructor.kind=operation|scalar-arithmetic.kind=operation|storage-buffer-read.kind=operation|atomic-min.kind=operation|index-access.kind=operation|atomic-max.kind=operation|storage-buffer-write.kind=operation"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
set(CROSSGL_DIRECTX_ATOMIC_EXCHANGE_SOURCE_SNIPPET [=[RWStructuredBuffer<int> counters : register(u0, space0);
RWStructuredBuffer<uint> unsignedCounters : register(u1, space0);
RWStructuredBuffer<int> observed : register(u2, space0);
RWStructuredBuffer<uint> unsignedObserved : register(u3, space0);
groupshared int tile[GROUP_SIZE];
groupshared uint unsignedTile[GROUP_SIZE];

[numthreads(4, 1, 1)]
void compute_main(uint3 crossgl_GlobalInvocationID : SV_DispatchThreadID, uint3 crossgl_LocalInvocationID : SV_GroupThreadID) {
  int index = int(crossgl_GlobalInvocationID.x);
  uint unsignedIndex = crossgl_LocalInvocationID.x;
  int value = int(crossgl_LocalInvocationID.x) + 1;
  uint unsignedValue = unsignedIndex + 1;
  {
    int crossgl_atomic_exchange_old_value;
    InterlockedExchange(counters[index], value, crossgl_atomic_exchange_old_value);
  }
  {
    uint crossgl_atomic_exchange_old_value;
    InterlockedExchange(unsignedCounters[unsignedIndex], unsignedValue, crossgl_atomic_exchange_old_value);
  }
  {
    int crossgl_atomic_exchange_old_value;
    InterlockedExchange(tile[index], value, crossgl_atomic_exchange_old_value);
  }
  int oldCounter;
  InterlockedExchange(counters[index], 1, oldCounter);
  InterlockedExchange(counters[index], value, oldCounter);
  uint oldUnsigned;
  InterlockedExchange(unsignedCounters[unsignedIndex], unsignedValue, oldUnsigned);
  int oldShared;
  InterlockedExchange(tile[index], value, oldShared);
  uint oldUnsignedShared;
  InterlockedExchange(unsignedTile[unsignedIndex], unsignedValue, oldUnsignedShared);]=])
add_test(NAME cglc_build_directx_atomic_exchange_source_package
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CMAKE_CURRENT_SOURCE_DIR}/tests/directx/fixtures/DirectXAtomicExchangeShader.cgl
    -DTARGET=directx
    -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-directx-atomic-exchange.cglb
    -DMODE=source-package-build
    -DEXPECTED_SOURCE=backend/directx/DirectXAtomicExchangeShader.hlsl
    "-DEXPECTED_SOURCE_SNIPPET=${CROSSGL_DIRECTX_ATOMIC_EXCHANGE_SOURCE_SNIPPET}"
    "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=directx|module=DirectXAtomicExchangeShader|nativeBinary=backend/directx/DirectXAtomicExchangeShader.dxil|functionConstants.0.name=GROUP_SIZE|functionConstants.0.value=4|resources.0.name=counters|resources.0.kind=buffer|resources.0.type=atomic<int>*|resources.0.binding=0|resources.1.name=unsignedCounters|resources.1.kind=buffer|resources.1.type=atomic<uint>*|resources.1.binding=1|resources.2.name=observed|resources.2.kind=buffer|resources.2.type=int*|resources.2.binding=2|resources.3.name=unsignedObserved|resources.3.kind=buffer|resources.3.type=uint*|resources.3.binding=3|resources.4.name=tile|resources.4.kind=shared|resources.4.type=atomic<int>[GROUP_SIZE]|resources.4.addressSpace=shared|resources.5.name=unsignedTile|resources.5.kind=shared|resources.5.type=atomic<uint>[GROUP_SIZE]|resources.5.addressSpace=shared|workgroupSizes.0.entryPoint=compute_main|workgroupSizes.0.x=4|workgroupSizes.0.y=1|workgroupSizes.0.z=1|workgroupSizes.0.sourceX=GROUP_SIZE|workgroupSizes.0.sourceY=1|workgroupSizes.0.sourceZ=1"
    "-DEXPECTED_REFLECTION_TARGET_FIELDS=counters.hlslType=RWStructuredBuffer<int>|counters.bindingClass=uav|counters.argumentIndex=0|unsignedCounters.hlslType=RWStructuredBuffer<uint>|unsignedCounters.bindingClass=uav|unsignedCounters.argumentIndex=1|observed.hlslType=RWStructuredBuffer<int>|observed.bindingClass=uav|observed.argumentIndex=2|unsignedObserved.hlslType=RWStructuredBuffer<uint>|unsignedObserved.bindingClass=uav|unsignedObserved.argumentIndex=3|tile.hlslType=int|tile.bindingClass=groupshared|tile.arrayElementCount=4|unsignedTile.hlslType=uint|unsignedTile.bindingClass=groupshared|unsignedTile.arrayElementCount=4"
    "-DEXPECTED_REFLECTION_JSON_ARRAY_LENGTHS=resources=6|targetResourceBindings=6|functionConstants=1|workgroupSizes=1"
    "-DEXPECTED_REFLECTION_FEATURE_FIELDS=hlsl-lowering.kind=backend|native-dxil-package.kind=backend|dxc.kind=toolchain|dxil-validator.kind=validation|compute-kernel.kind=stage|workgroup-size.kind=execution|storage-buffer.kind=resource|atomic-integer.kind=type|workgroup-shared-memory.kind=resource|fixed-array.kind=layout|descriptor-array.kind=resource|local-declaration.kind=operation|scalar-constructor.kind=operation|scalar-arithmetic.kind=operation|atomic-exchange.kind=operation|index-access.kind=operation|storage-buffer-read.kind=operation|storage-buffer-write.kind=operation"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
set(CROSSGL_DIRECTX_ATOMIC_BITWISE_SOURCE_SNIPPET [=[RWStructuredBuffer<int> signedMasks : register(u0, space0);
RWStructuredBuffer<uint> unsignedMasks : register(u1, space0);
RWStructuredBuffer<int> observed : register(u2, space0);
RWStructuredBuffer<uint> unsignedObserved : register(u3, space0);
groupshared int signedTile[GROUP_SIZE];
groupshared uint unsignedTile[GROUP_SIZE];

[numthreads(4, 1, 1)]
void compute_main(uint3 crossgl_GlobalInvocationID : SV_DispatchThreadID, uint3 crossgl_LocalInvocationID : SV_GroupThreadID) {
  int index = int(crossgl_GlobalInvocationID.x);
  uint unsignedIndex = crossgl_LocalInvocationID.x;
  int signedMask = int(crossgl_LocalInvocationID.x) + 1;
  uint unsignedMask = unsignedIndex + 1;
  InterlockedAnd(signedMasks[index], signedMask);
  InterlockedOr(unsignedMasks[unsignedIndex], unsignedMask);
  InterlockedXor(unsignedTile[unsignedIndex], unsignedMask);
  InterlockedAnd(signedTile[index], signedMask);
  int oldAnd;
  InterlockedAnd(signedMasks[index], signedMask, oldAnd);
  InterlockedOr(signedMasks[index], 1, oldAnd);
  uint oldOr;
  InterlockedOr(unsignedMasks[unsignedIndex], unsignedMask, oldOr);
  uint oldXor;
  InterlockedXor(unsignedMasks[unsignedIndex], unsignedMask, oldXor);
  int oldShared;
  InterlockedXor(signedTile[index], signedMask, oldShared);
  uint oldUnsignedShared;
  InterlockedAnd(unsignedTile[unsignedIndex], unsignedMask, oldUnsignedShared);]=])
add_test(NAME cglc_build_directx_atomic_bitwise_source_package
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CMAKE_CURRENT_SOURCE_DIR}/tests/directx/fixtures/DirectXAtomicBitwiseShader.cgl
    -DTARGET=directx
    -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-directx-atomic-bitwise.cglb
    -DMODE=source-package-build
    -DEXPECTED_SOURCE=backend/directx/DirectXAtomicBitwiseShader.hlsl
    "-DEXPECTED_SOURCE_SNIPPET=${CROSSGL_DIRECTX_ATOMIC_BITWISE_SOURCE_SNIPPET}"
    "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=directx|module=DirectXAtomicBitwiseShader|nativeBinary=backend/directx/DirectXAtomicBitwiseShader.dxil|functionConstants.0.name=GROUP_SIZE|functionConstants.0.value=4|resources.0.name=signedMasks|resources.0.kind=buffer|resources.0.type=atomic<int>*|resources.0.binding=0|resources.1.name=unsignedMasks|resources.1.kind=buffer|resources.1.type=atomic<uint>*|resources.1.binding=1|resources.2.name=observed|resources.2.kind=buffer|resources.2.type=int*|resources.2.binding=2|resources.3.name=unsignedObserved|resources.3.kind=buffer|resources.3.type=uint*|resources.3.binding=3|resources.4.name=signedTile|resources.4.kind=shared|resources.4.type=atomic<int>[GROUP_SIZE]|resources.4.addressSpace=shared|resources.5.name=unsignedTile|resources.5.kind=shared|resources.5.type=atomic<uint>[GROUP_SIZE]|resources.5.addressSpace=shared|workgroupSizes.0.entryPoint=compute_main|workgroupSizes.0.x=4|workgroupSizes.0.y=1|workgroupSizes.0.z=1|workgroupSizes.0.sourceX=GROUP_SIZE|workgroupSizes.0.sourceY=1|workgroupSizes.0.sourceZ=1"
    "-DEXPECTED_REFLECTION_TARGET_FIELDS=signedMasks.hlslType=RWStructuredBuffer<int>|signedMasks.bindingClass=uav|signedMasks.argumentIndex=0|unsignedMasks.hlslType=RWStructuredBuffer<uint>|unsignedMasks.bindingClass=uav|unsignedMasks.argumentIndex=1|observed.hlslType=RWStructuredBuffer<int>|observed.bindingClass=uav|observed.argumentIndex=2|unsignedObserved.hlslType=RWStructuredBuffer<uint>|unsignedObserved.bindingClass=uav|unsignedObserved.argumentIndex=3|signedTile.hlslType=int|signedTile.bindingClass=groupshared|signedTile.arrayElementCount=4|unsignedTile.hlslType=uint|unsignedTile.bindingClass=groupshared|unsignedTile.arrayElementCount=4"
    "-DEXPECTED_REFLECTION_JSON_ARRAY_LENGTHS=resources=6|targetResourceBindings=6|functionConstants=1|workgroupSizes=1"
    "-DEXPECTED_REFLECTION_FEATURE_FIELDS=hlsl-lowering.kind=backend|native-dxil-package.kind=backend|dxc.kind=toolchain|dxil-validator.kind=validation|compute-kernel.kind=stage|workgroup-size.kind=execution|storage-buffer.kind=resource|atomic-integer.kind=type|workgroup-shared-memory.kind=resource|fixed-array.kind=layout|descriptor-array.kind=resource|local-declaration.kind=operation|scalar-constructor.kind=operation|scalar-arithmetic.kind=operation|atomic-and.kind=operation|index-access.kind=operation|atomic-or.kind=operation|atomic-xor.kind=operation|storage-buffer-read.kind=operation|storage-buffer-write.kind=operation"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
crossgl_add_python_expect_test(
  NAME cglc_manifest_json_schema_source_package
  DEFINITIONS
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_STORAGE_BUFFER_COMPUTE_SHADER}
    -DTARGET=directx
    -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-directx-manifest-schema.cglb
    -DMODE=source-package-build
    -DEXPECTED_SOURCE=backend/directx/StorageBufferComputeShader.hlsl
    -DEXPECTED_SOURCE_SNIPPET=RWStructuredBuffer
    "-DEXPECTED_MANIFEST_JSON_FIELDS=schemaVersion=1|target=directx|module=StorageBufferComputeShader|artifacts.backendSource=backend/directx/StorageBufferComputeShader.hlsl|artifacts.nativeBinary=backend/directx/StorageBufferComputeShader.dxil|artifacts.nativeArtifactDescriptor=backend/directx/StorageBufferComputeShader.native-artifact.json"
    "-DEXPECTED_NATIVE_ARTIFACT_DESCRIPTOR_JSON_FIELDS=target=directx|binaryKind=directx.dxil|sourcePath=backend/directx/StorageBufferComputeShader.hlsl|nativeBinaryStatus=planned|validationStatus=unavailable|toolchainProvenance.tools.0.name=CrossGL DirectX backend|toolchainProvenance.tools.0.role=generator"
    "-DEXPECTED_NATIVE_ARTIFACT_DESCRIPTOR_JSON_ARRAY_LENGTHS=toolchainProvenance.tools=1|validationDiagnostics=0"
    -DMANIFEST_JSON_SCHEMA=${CMAKE_CURRENT_SOURCE_DIR}/docs/schemas/manifest-v1.schema.json
    -DNATIVE_ARTIFACT_JSON_SCHEMA=${CMAKE_CURRENT_SOURCE_DIR}/docs/schemas/native-artifact-v0.schema.json
    -DPACKAGE_SCHEMA_ROOT=${CMAKE_CURRENT_SOURCE_DIR}/docs/schemas
    -DJSON_SCHEMA_VALIDATOR=${CMAKE_CURRENT_SOURCE_DIR}/tools/validate_json_schema.py
    -DPACKAGE_INTEGRITY_VALIDATOR=${CMAKE_CURRENT_SOURCE_DIR}/tools/validate_package_integrity.py)
set(CROSSGL_SOURCE_REMAP_FULL_FILE
    "${CMAKE_CURRENT_SOURCE_DIR}/tests/fixtures/source-remap-v1-full-file.json")
file(SHA256 "${CROSSGL_SOURCE_REMAP_FULL_FILE}"
     CROSSGL_SOURCE_REMAP_FULL_FILE_SHA256)
file(SIZE "${CROSSGL_SOURCE_REMAP_FULL_FILE}"
     CROSSGL_SOURCE_REMAP_FULL_FILE_SIZE_BYTES)
crossgl_add_python_expect_test(
  NAME cglc_build_directx_source_package_logical_source_remap
  DEFINITIONS
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_STORAGE_BUFFER_COMPUTE_SHADER}
    -DLOGICAL_INPUT=generated/from-translator.cgl
    -DSOURCE_REMAP=${CROSSGL_SOURCE_REMAP_FULL_FILE}
    -DTARGET=directx
    -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-directx-source-remap-debug.cglb
    -DMODE=source-package-build
    -DEXPECTED_SOURCE=backend/directx/StorageBufferComputeShader.hlsl
    -DEXPECTED_SOURCE_SNIPPET=RWStructuredBuffer
    "-DEXPECTED_MANIFEST_JSON_FIELDS=schemaVersion=1|target=directx|module=StorageBufferComputeShader|artifacts.sourceRemap=ir/source-remap-provenance.json"
    "-DEXPECTED_SOURCE_REMAP_PROVENANCE_JSON_FIELDS=schemaVersion=1|kind=crossgl.sourceRemapProvenance|contractVersion=source-remap-provenance-v1|target=directx|generatedFile=generated/from-translator.cgl|mappingGranularity=source-span|mappingCount=1|sourceRemap.sha256.algorithm=sha256|sourceRemap.sha256.value=${CROSSGL_SOURCE_REMAP_FULL_FILE_SHA256}|sourceRemap.sizeBytes=${CROSSGL_SOURCE_REMAP_FULL_FILE_SIZE_BYTES}"
    "-DEXPECTED_DEBUG_METADATA_JSON_FIELDS=hirSourceLocations.types.0.location.file=generated/from-translator.cgl|hirSourceLocations.types.0.originalLocation.file=shaders/original.crossgl"
    "-DEXPECTED_HIR_SOURCE_MAP_JSON_FIELDS=hirSourceLocations.types.0.location.file=generated/from-translator.cgl|hirSourceLocations.types.0.originalLocation.file=shaders/original.crossgl"
    "-DEXPECTED_PACKAGE_INSPECT_JSON_FIELDS=summary.artifactCount=7|debugArtifacts.health=ok|debugArtifacts.sourceRemap.artifactPresent=true|debugArtifacts.sourceRemap.exists=true|debugArtifacts.sourceRemap.health=ok|debugArtifacts.sourceRemap.path=ir/source-remap-provenance.json|debugArtifacts.sourceRemap.target=directx|debugArtifacts.sourceRemap.generatedFile=generated/from-translator.cgl|debugArtifacts.sourceRemap.mappingCount=1|debugArtifacts.sourceRemap.sourceSha256=${CROSSGL_SOURCE_REMAP_FULL_FILE_SHA256}|debugArtifacts.sourceRemap.sourceSizeBytes=${CROSSGL_SOURCE_REMAP_FULL_FILE_SIZE_BYTES}|debugArtifacts.sourceRemap.checks.identityMatchesContract=true|debugArtifacts.sourceRemap.checks.targetMatchesPackage=true|debugArtifacts.sourceRemap.checks.sourceHashPresent=true"
    -DDEBUG_METADATA_JSON_SCHEMA=${CMAKE_CURRENT_SOURCE_DIR}/docs/schemas/debug-metadata-v11.schema.json
    -DHIR_SOURCE_MAP_JSON_SCHEMA=${CMAKE_CURRENT_SOURCE_DIR}/docs/schemas/hir-source-map-v7.schema.json
    -DSOURCE_REMAP_PROVENANCE_JSON_SCHEMA=${CMAKE_CURRENT_SOURCE_DIR}/docs/schemas/source-remap-provenance-v1.schema.json
    -DPACKAGE_INSPECT_JSON_SCHEMA=${CMAKE_CURRENT_SOURCE_DIR}/docs/schemas/package-inspect-v1.schema.json
    -DJSON_SCHEMA_VALIDATOR=${CMAKE_CURRENT_SOURCE_DIR}/tools/validate_json_schema.py
    -DPACKAGE_INTEGRITY_VALIDATOR=${CMAKE_CURRENT_SOURCE_DIR}/tools/validate_package_integrity.py)
crossgl_add_python_expect_test(
  NAME cglc_reflection_json_schema_source_package
  DEFINITIONS
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_STORAGE_BUFFER_COMPUTE_SHADER}
    -DTARGET=directx
    -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-directx-reflection-schema.cglb
    -DMODE=source-package-build
    -DEXPECTED_SOURCE=backend/directx/StorageBufferComputeShader.hlsl
    -DEXPECTED_SOURCE_SNIPPET=RWStructuredBuffer
    "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=directx|module=StorageBufferComputeShader|nativeBinary=backend/directx/StorageBufferComputeShader.dxil"
    "-DEXPECTED_REFLECTION_TARGET_FIELDS=values.hlslType=RWStructuredBuffer<float>|values.descriptorType=UAV|values.bindingClass=uav"
    -DREFLECTION_JSON_SCHEMA=${CMAKE_CURRENT_SOURCE_DIR}/docs/schemas/reflection-v1.schema.json
    -DJSON_SCHEMA_VALIDATOR=${CMAKE_CURRENT_SOURCE_DIR}/tools/validate_json_schema.py)
crossgl_add_python_expect_test(
  NAME cglc_debug_metadata_json_schema_source_package
  DEFINITIONS
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_TEXTURE_2D_SHADOW_COMPARE_LOD_MANUAL_KERNEL_LIST_SHADER}
    -DTARGET=directx
    -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-directx-debug-metadata-schema.cglb
    -DMODE=source-package-build
    "-DEXPECTED_MANIFEST_JSON_FIELDS=schemaVersion=1|target=directx|module=Texture2DShadowCompareLodManualKernelListShader"
    "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=directx|module=Texture2DShadowCompareLodManualKernelListShader"
    -DDEBUG_METADATA_JSON_SCHEMA=${CMAKE_CURRENT_SOURCE_DIR}/docs/schemas/debug-metadata-v11.schema.json
    -DHIR_SOURCE_MAP_JSON_SCHEMA=${CMAKE_CURRENT_SOURCE_DIR}/docs/schemas/hir-source-map-v7.schema.json
    -DJSON_SCHEMA_VALIDATOR=${CMAKE_CURRENT_SOURCE_DIR}/tools/validate_json_schema.py
    -DPACKAGE_INTEGRITY_VALIDATOR=${CMAKE_CURRENT_SOURCE_DIR}/tools/validate_package_integrity.py)
crossgl_add_python_expect_test(
  NAME cglc_package_inspect_json_schema_source_package
  DEFINITIONS
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_STORAGE_BUFFER_COMPUTE_SHADER}
    -DTARGET=directx
    -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-directx-package-inspect.cglb
    -DMODE=package-inspect-source-package
    "-DEXPECTED_JSON_FIELDS=schemaVersion=1|packageFormat=directory|summary.module=StorageBufferComputeShader|summary.target=directx|summary.artifactCount=6|summary.debugArtifactsPresent=true|rootFiles.0.name=manifest|rootFiles.0.exists=true|rootFiles.1.name=reflection|rootFiles.1.exists=true|rootFiles.2.name=diagnostics|rootFiles.2.exists=true|artifacts.0.name=backendSource|artifacts.0.exists=true|artifacts.1.name=nativeBinary|artifacts.2.name=debugMetadata|artifacts.2.exists=true|artifacts.3.name=hirSourceMap|artifacts.3.exists=true|artifacts.4.name=nativeArtifactDescriptor|artifacts.4.path=backend/directx/StorageBufferComputeShader.native-artifact.json|artifacts.4.exists=true|manifest.target=directx|manifest.artifacts.nativeArtifactDescriptor=backend/directx/StorageBufferComputeShader.native-artifact.json|nativeArtifactDescriptor.health=ok|nativeArtifactDescriptor.target=directx|nativeArtifactDescriptor.binaryKind=directx.dxil|nativeArtifactDescriptor.sourcePath=backend/directx/StorageBufferComputeShader.hlsl|nativeArtifactDescriptor.nativeBinaryStatus=planned|nativeArtifactDescriptor.validationStatus=unavailable|nativeArtifactDescriptor.checks.sourcePathMatchesManifest=true|nativeArtifactDescriptor.checks.sourceHashMatchesFile=true|nativeArtifactDescriptor.checks.artifactPathMatchesManifest=true|reflection.target=directx|diagnostics.schemaVersion=1"
    "-DEXPECTED_NATIVE_ARTIFACT_DESCRIPTOR_JSON_FIELDS=target=directx|binaryKind=directx.dxil|sourcePath=backend/directx/StorageBufferComputeShader.hlsl|nativeBinaryStatus=planned|validationStatus=unavailable|toolchainProvenance.tools.0.name=CrossGL DirectX backend|toolchainProvenance.tools.0.role=generator"
    "-DEXPECTED_NATIVE_ARTIFACT_DESCRIPTOR_JSON_ARRAY_LENGTHS=toolchainProvenance.tools=1|validationDiagnostics=0"
    -DJSON_SCHEMA=${CMAKE_CURRENT_SOURCE_DIR}/docs/schemas/package-inspect-v1.schema.json
    -DNATIVE_ARTIFACT_JSON_SCHEMA=${CMAKE_CURRENT_SOURCE_DIR}/docs/schemas/native-artifact-v0.schema.json
    -DJSON_SCHEMA_VALIDATOR=${CMAKE_CURRENT_SOURCE_DIR}/tools/validate_json_schema.py)

function(crossgl_add_directx_compute_fake_dxc_package_inspect_test)
  set(options TOOLCHAIN_DISABLE_FALLBACK)
  set(one_value_args
    NAME
    TOOLCHAIN_PATH
    EXPECTED_NATIVE_BINARY_STATUS
    EXPECTED_NATIVE_BINARY_EXISTS
    EXPECTED_DIAGNOSTIC_FIELDS
    EXPECTED_DIAGNOSTICS_ARRAY_LENGTHS
    EXPECTED_TOOL_LOG
    EXPECTED_TOOL_LOG_CONTAINS)
  cmake_parse_arguments(CROSSGL_DIRECTX_FAKE_DXC_INSPECT
    "${options}" "${one_value_args}" "" ${ARGN})
  if(NOT CROSSGL_DIRECTX_FAKE_DXC_INSPECT_NAME)
    message(FATAL_ERROR
      "crossgl_add_directx_compute_fake_dxc_package_inspect_test requires NAME")
  endif()
  if(NOT CROSSGL_DIRECTX_FAKE_DXC_INSPECT_TOOLCHAIN_PATH)
    message(FATAL_ERROR
      "crossgl_add_directx_compute_fake_dxc_package_inspect_test requires TOOLCHAIN_PATH")
  endif()
  if(NOT DEFINED CROSSGL_DIRECTX_FAKE_DXC_INSPECT_EXPECTED_NATIVE_BINARY_EXISTS)
    message(FATAL_ERROR
      "crossgl_add_directx_compute_fake_dxc_package_inspect_test requires EXPECTED_NATIVE_BINARY_EXISTS")
  endif()

  set(directx_fake_dxc_inspect_extra_json_paths "")
  set(directx_fake_dxc_inspect_extra_json_fields "")
  set(directx_fake_dxc_inspect_extra_native_descriptor_paths "")
  set(directx_fake_dxc_inspect_extra_native_descriptor_fields
    "|toolchainProvenance.tools.0.name=CrossGL DirectX backend|toolchainProvenance.tools.0.role=generator|validationStatus=unavailable")
  set(directx_fake_dxc_inspect_extra_native_descriptor_array_lengths
    "toolchainProvenance.tools=1|validationDiagnostics=0")
  if(CROSSGL_DIRECTX_FAKE_DXC_INSPECT_EXPECTED_NATIVE_BINARY_STATUS STREQUAL
     "emitted")
    set(directx_fake_dxc_inspect_extra_json_paths
      "artifacts.1.sizeBytes|artifacts.1.sha256|nativeArtifactDescriptor.sourceHash|nativeArtifactDescriptor.artifactHash|nativeArtifactDescriptor.sizeBytes")
    set(directx_fake_dxc_inspect_extra_json_fields
      "|nativeArtifactDescriptor.artifactPath=backend/directx/StorageBufferComputeShader.dxil|nativeArtifactDescriptor.optimizationLevel=O1|nativeArtifactDescriptor.optimizationEvidence.requestedLevel=O1|nativeArtifactDescriptor.optimizationEvidence.effectiveLevel=O3|nativeArtifactDescriptor.optimizationEvidence.policy=crossgl-to-dxc-optimization-map|nativeArtifactDescriptor.optimizationEvidence.status=applied|nativeArtifactDescriptor.optimizationEvidence.tool=dxc|nativeArtifactDescriptor.optimizationEvidence.toolFlag=-O3|nativeArtifactDescriptor.validationStatus=not-run|nativeArtifactDescriptor.checks.nativeBinaryStatusMatchesPackage=true|nativeArtifactDescriptor.checks.artifactHashMatchesFile=true|nativeArtifactDescriptor.checks.sizeBytesMatchesFile=true|nativeArtifactDescriptor.checks.validationStatusMatchesNativeStatus=true")
    set(directx_fake_dxc_inspect_extra_native_descriptor_paths
      "sourceHash.value|artifactHash.value|sizeBytes")
    set(directx_fake_dxc_inspect_extra_native_descriptor_fields
      "|sourceHash.algorithm=sha256|artifactPath=backend/directx/StorageBufferComputeShader.dxil|artifactHash.algorithm=sha256|optimizationLevel=O1|optimizationEvidence.requestedLevel=O1|optimizationEvidence.effectiveLevel=O3|optimizationEvidence.policy=crossgl-to-dxc-optimization-map|optimizationEvidence.status=applied|optimizationEvidence.tool=dxc|optimizationEvidence.toolFlag=-O3|validationStatus=not-run")
    set(directx_fake_dxc_inspect_extra_native_descriptor_array_lengths
      "toolchainProvenance.tools=2|validationDiagnostics=0")
  endif()

  set(inspect_definitions
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_STORAGE_BUFFER_COMPUTE_SHADER}
    -DTARGET=directx
    -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/${CROSSGL_DIRECTX_FAKE_DXC_INSPECT_NAME}.cglb
    -DMODE=package-inspect-source-package
    "-DTOOLCHAIN_PATH=${CROSSGL_DIRECTX_FAKE_DXC_INSPECT_TOOLCHAIN_PATH}"
    "-DEXPECTED_JSON_FIELDS=schemaVersion=1|packageFormat=directory|summary.module=StorageBufferComputeShader|summary.target=directx|summary.nativeBinaryStatus=${CROSSGL_DIRECTX_FAKE_DXC_INSPECT_EXPECTED_NATIVE_BINARY_STATUS}|summary.artifactCount=6|summary.debugArtifactsPresent=true|artifacts.0.name=backendSource|artifacts.0.path=backend/directx/StorageBufferComputeShader.hlsl|artifacts.0.exists=true|artifacts.1.name=nativeBinary|artifacts.1.path=backend/directx/StorageBufferComputeShader.dxil|artifacts.1.exists=${CROSSGL_DIRECTX_FAKE_DXC_INSPECT_EXPECTED_NATIVE_BINARY_EXISTS}|artifacts.2.name=debugMetadata|artifacts.2.path=ir/debug-metadata.json|artifacts.2.exists=true|artifacts.3.name=hirSourceMap|artifacts.3.path=ir/hir-source-map.json|artifacts.3.exists=true|artifacts.4.name=nativeArtifactDescriptor|artifacts.4.path=backend/directx/StorageBufferComputeShader.native-artifact.json|artifacts.4.exists=true|manifest.target=directx|manifest.module=StorageBufferComputeShader|manifest.artifacts.backendSource=backend/directx/StorageBufferComputeShader.hlsl|manifest.artifacts.nativeBinary=backend/directx/StorageBufferComputeShader.dxil|manifest.artifacts.nativeBinaryStatus=${CROSSGL_DIRECTX_FAKE_DXC_INSPECT_EXPECTED_NATIVE_BINARY_STATUS}|manifest.artifacts.nativeArtifactDescriptor=backend/directx/StorageBufferComputeShader.native-artifact.json|nativeArtifactDescriptor.health=ok|nativeArtifactDescriptor.target=directx|nativeArtifactDescriptor.binaryKind=directx.dxil|nativeArtifactDescriptor.sourcePath=backend/directx/StorageBufferComputeShader.hlsl|nativeArtifactDescriptor.nativeBinaryStatus=${CROSSGL_DIRECTX_FAKE_DXC_INSPECT_EXPECTED_NATIVE_BINARY_STATUS}|nativeArtifactDescriptor.checks.sourcePathMatchesManifest=true|nativeArtifactDescriptor.checks.sourceHashMatchesFile=true|nativeArtifactDescriptor.checks.artifactPathMatchesManifest=true|reflection.target=directx|reflection.module=StorageBufferComputeShader|reflection.nativeBinary=backend/directx/StorageBufferComputeShader.dxil|diagnostics.schemaVersion=1|${CROSSGL_DIRECTX_FAKE_DXC_INSPECT_EXPECTED_DIAGNOSTIC_FIELDS}${directx_fake_dxc_inspect_extra_json_fields}"
    "-DEXPECTED_NATIVE_ARTIFACT_DESCRIPTOR_JSON_FIELDS=target=directx|binaryKind=directx.dxil|sourcePath=backend/directx/StorageBufferComputeShader.hlsl|nativeBinaryStatus=${CROSSGL_DIRECTX_FAKE_DXC_INSPECT_EXPECTED_NATIVE_BINARY_STATUS}${directx_fake_dxc_inspect_extra_native_descriptor_fields}"
      "-DEXPECTED_JSON_ARRAY_LENGTHS=rootFiles=3|artifacts=6|${CROSSGL_DIRECTX_FAKE_DXC_INSPECT_EXPECTED_DIAGNOSTICS_ARRAY_LENGTHS}"
    -DJSON_SCHEMA=${CMAKE_CURRENT_SOURCE_DIR}/docs/schemas/package-inspect-v1.schema.json
    -DNATIVE_ARTIFACT_JSON_SCHEMA=${CMAKE_CURRENT_SOURCE_DIR}/docs/schemas/native-artifact-v0.schema.json
    -DJSON_SCHEMA_VALIDATOR=${CMAKE_CURRENT_SOURCE_DIR}/tools/validate_json_schema.py)
  if(directx_fake_dxc_inspect_extra_json_paths)
    list(APPEND inspect_definitions
      "-DEXPECTED_JSON_PATHS=${directx_fake_dxc_inspect_extra_json_paths}")
  endif()
  if(directx_fake_dxc_inspect_extra_native_descriptor_paths)
    list(APPEND inspect_definitions
      "-DEXPECTED_NATIVE_ARTIFACT_DESCRIPTOR_JSON_PATHS=${directx_fake_dxc_inspect_extra_native_descriptor_paths}")
  endif()
  if(directx_fake_dxc_inspect_extra_native_descriptor_array_lengths)
    list(APPEND inspect_definitions
      "-DEXPECTED_NATIVE_ARTIFACT_DESCRIPTOR_JSON_ARRAY_LENGTHS=${directx_fake_dxc_inspect_extra_native_descriptor_array_lengths}")
  endif()
  if(CROSSGL_DIRECTX_FAKE_DXC_INSPECT_TOOLCHAIN_DISABLE_FALLBACK)
    list(APPEND inspect_definitions -DTOOLCHAIN_DISABLE_FALLBACK=ON)
  endif()
  if(CROSSGL_DIRECTX_FAKE_DXC_INSPECT_EXPECTED_TOOL_LOG)
    list(APPEND inspect_definitions
      "-DEXPECTED_TOOL_LOG=${CROSSGL_DIRECTX_FAKE_DXC_INSPECT_EXPECTED_TOOL_LOG}")
  endif()
  if(CROSSGL_DIRECTX_FAKE_DXC_INSPECT_EXPECTED_TOOL_LOG_CONTAINS)
    list(APPEND inspect_definitions
      "-DEXPECTED_TOOL_LOG_CONTAINS=${CROSSGL_DIRECTX_FAKE_DXC_INSPECT_EXPECTED_TOOL_LOG_CONTAINS}")
  endif()

  crossgl_add_python_expect_test(
    NAME "${CROSSGL_DIRECTX_FAKE_DXC_INSPECT_NAME}"
    DEFINITIONS ${inspect_definitions})
endfunction()

crossgl_add_directx_compute_fake_dxc_package_inspect_test(
  NAME cglc_package_inspect_directx_compute_fake_dxc_success
  TOOLCHAIN_PATH ${CROSSGL_FAKE_DXC_SUCCESS_DIR}
  TOOLCHAIN_DISABLE_FALLBACK
  EXPECTED_NATIVE_BINARY_STATUS emitted
  EXPECTED_NATIVE_BINARY_EXISTS true
  EXPECTED_DIAGNOSTIC_FIELDS "diagnostics.diagnostics.0.severity=note|diagnostics.diagnostics.0.code=directx.source-package-emitted|diagnostics.diagnostics.1.severity=note|diagnostics.diagnostics.1.code=directx.dxil-emitted"
  EXPECTED_DIAGNOSTICS_ARRAY_LENGTHS "diagnostics.diagnostics=2"
  EXPECTED_TOOL_LOG ${CROSSGL_FAKE_DXC_SUCCESS_DIR}/dxc.log
  EXPECTED_TOOL_LOG_CONTAINS "-T cs_6_0 -E compute_main -Fo")

crossgl_add_directx_compute_fake_dxc_package_inspect_test(
  NAME cglc_package_inspect_directx_compute_fake_dxc_tool_failure
  TOOLCHAIN_PATH ${CROSSGL_FAKE_DXC_FAILURE_DIR}
  TOOLCHAIN_DISABLE_FALLBACK
  EXPECTED_NATIVE_BINARY_STATUS planned
  EXPECTED_NATIVE_BINARY_EXISTS false
  EXPECTED_DIAGNOSTIC_FIELDS "diagnostics.diagnostics.0.severity=note|diagnostics.diagnostics.0.code=directx.source-package-emitted|diagnostics.diagnostics.1.severity=warning|diagnostics.diagnostics.1.code=directx.dxc-failed|diagnostics.diagnostics.2.severity=warning|diagnostics.diagnostics.2.code=directx.source-package-only"
  EXPECTED_DIAGNOSTICS_ARRAY_LENGTHS "diagnostics.diagnostics=3"
  EXPECTED_TOOL_LOG ${CROSSGL_FAKE_DXC_FAILURE_DIR}/dxc.log
  EXPECTED_TOOL_LOG_CONTAINS "-T cs_6_0 -E compute_main -Fo")

crossgl_add_directx_compute_fake_dxc_package_inspect_test(
  NAME cglc_package_inspect_directx_compute_fake_dxc_unavailable
  TOOLCHAIN_PATH ${CROSSGL_FAKE_TOOL_UNAVAILABLE_DIR}
  TOOLCHAIN_DISABLE_FALLBACK
  EXPECTED_NATIVE_BINARY_STATUS planned
  EXPECTED_NATIVE_BINARY_EXISTS false
  EXPECTED_DIAGNOSTIC_FIELDS "diagnostics.diagnostics.0.severity=note|diagnostics.diagnostics.0.code=directx.source-package-emitted|diagnostics.diagnostics.1.severity=warning|diagnostics.diagnostics.1.code=directx.source-package-only"
  EXPECTED_DIAGNOSTICS_ARRAY_LENGTHS "diagnostics.diagnostics=2")

if(CROSSGL_HAS_DIRECTX_NATIVE_VALIDATOR)
  set(CROSSGL_DIRECTX_GRAPHICS_SOURCE_PACKAGE_NATIVE_BINARY_STATUS emitted)
  set(CROSSGL_DIRECTX_GRAPHICS_SOURCE_PACKAGE_NATIVE_BINARY_EXISTS true)
else()
  set(CROSSGL_DIRECTX_GRAPHICS_SOURCE_PACKAGE_NATIVE_BINARY_STATUS planned)
  set(CROSSGL_DIRECTX_GRAPHICS_SOURCE_PACKAGE_NATIVE_BINARY_EXISTS false)
endif()
crossgl_add_python_expect_test(
  NAME cglc_package_inspect_json_schema_directx_graphics_resources_source_package
  DEFINITIONS
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_DIRECTX_GRAPHICS_RESOURCE_SHADER}
    -DTARGET=directx
    -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-directx-graphics-resources-package-inspect.cglb
    -DMODE=package-inspect-source-package
    "-DEXPECTED_JSON_FIELDS=schemaVersion=1|packageFormat=directory|summary.module=DirectXGraphicsResourceShader|summary.target=directx|summary.nativeBinaryStatus=${CROSSGL_DIRECTX_GRAPHICS_SOURCE_PACKAGE_NATIVE_BINARY_STATUS}|summary.artifactCount=7|summary.debugArtifactsPresent=true|debugArtifacts.debugMetadataArtifactPresent=true|debugArtifacts.hirSourceMapArtifactPresent=true|debugArtifacts.debugMetadataExists=true|debugArtifacts.hirSourceMapExists=true|debugArtifacts.health=ok|debugArtifacts.checks.hirSourceLocationsMatch=true|debugArtifacts.checks.sourceMapUnfiltered=true|debugArtifacts.checks.sourceMapUnpaged=true|debugArtifacts.checks.sourceMapRecordsDisabled=true|rootFiles.0.name=manifest|rootFiles.0.exists=true|rootFiles.1.name=reflection|rootFiles.1.exists=true|rootFiles.2.name=diagnostics|rootFiles.2.exists=true|artifacts.0.name=backendSource|artifacts.0.path=backend/directx/DirectXGraphicsResourceShader.graphics.hlsl|artifacts.0.exists=true|artifacts.1.name=nativeBinary|artifacts.1.path=backend/directx/DirectXGraphicsResourceShader.dxil|artifacts.1.exists=${CROSSGL_DIRECTX_GRAPHICS_SOURCE_PACKAGE_NATIVE_BINARY_EXISTS}|artifacts.2.name=debugMetadata|artifacts.2.path=ir/debug-metadata.json|artifacts.2.exists=true|artifacts.3.name=hirSourceMap|artifacts.3.path=ir/hir-source-map.json|artifacts.3.exists=true|artifacts.6.name=graphicsAbi|artifacts.6.path=backend/directx/DirectXGraphicsResourceShader.graphics-abi.json|artifacts.6.exists=true|manifest.target=directx|manifest.module=DirectXGraphicsResourceShader|manifest.artifacts.backendSource=backend/directx/DirectXGraphicsResourceShader.graphics.hlsl|manifest.artifacts.nativeBinary=backend/directx/DirectXGraphicsResourceShader.dxil|manifest.artifacts.nativeBinaryStatus=${CROSSGL_DIRECTX_GRAPHICS_SOURCE_PACKAGE_NATIVE_BINARY_STATUS}|manifest.artifacts.debugMetadata=ir/debug-metadata.json|manifest.artifacts.hirSourceMap=ir/hir-source-map.json|manifest.artifacts.graphicsAbi=backend/directx/DirectXGraphicsResourceShader.graphics-abi.json|reflection.target=directx|reflection.module=DirectXGraphicsResourceShader|reflection.nativeBinary=backend/directx/DirectXGraphicsResourceShader.dxil|reflection.entryPoints.0.stage=vertex|reflection.entryPoints.0.backendName=vertex_main|reflection.entryPoints.1.stage=fragment|reflection.entryPoints.1.backendName=fragment_main|reflection.resources.0.stage=vertex|reflection.resources.0.name=transform|reflection.resources.0.kind=uniform|reflection.resources.0.type=Transform|reflection.resources.0.set=0|reflection.resources.0.binding=0|reflection.resources.1.stage=fragment|reflection.resources.1.name=material|reflection.resources.1.kind=uniform|reflection.resources.1.type=Material|reflection.resources.1.set=0|reflection.resources.1.binding=1|reflection.resources.2.stage=fragment|reflection.resources.2.name=colorMap|reflection.resources.2.kind=texture|reflection.resources.2.type=sampler2D|reflection.resources.2.set=0|reflection.resources.2.binding=2|reflection.resources.3.stage=fragment|reflection.resources.3.name=linearSampler|reflection.resources.3.kind=sampler|reflection.resources.3.type=sampler|reflection.resources.3.set=0|reflection.resources.3.binding=3|reflection.targetResourceBindings.0.target=directx|reflection.targetResourceBindings.0.stage=vertex|reflection.targetResourceBindings.0.entryPoint=vertex_main|reflection.targetResourceBindings.0.name=transform|reflection.targetResourceBindings.0.kind=uniform|reflection.targetResourceBindings.0.sourceType=Transform|reflection.targetResourceBindings.0.hlslType=ConstantBuffer<Transform>|reflection.targetResourceBindings.0.addressSpace=constant-buffer|reflection.targetResourceBindings.0.abi=registerBinding|reflection.targetResourceBindings.0.bindingClass=constant-buffer|reflection.targetResourceBindings.0.descriptorType=CBV|reflection.targetResourceBindings.0.argumentIndex=0|reflection.targetResourceBindings.0.set=0|reflection.targetResourceBindings.0.binding=0|reflection.targetResourceBindings.1.target=directx|reflection.targetResourceBindings.1.stage=fragment|reflection.targetResourceBindings.1.entryPoint=fragment_main|reflection.targetResourceBindings.1.name=material|reflection.targetResourceBindings.1.kind=uniform|reflection.targetResourceBindings.1.sourceType=Material|reflection.targetResourceBindings.1.hlslType=ConstantBuffer<Material>|reflection.targetResourceBindings.1.addressSpace=constant-buffer|reflection.targetResourceBindings.1.abi=registerBinding|reflection.targetResourceBindings.1.bindingClass=constant-buffer|reflection.targetResourceBindings.1.descriptorType=CBV|reflection.targetResourceBindings.1.argumentIndex=1|reflection.targetResourceBindings.1.set=0|reflection.targetResourceBindings.1.binding=1|reflection.targetResourceBindings.2.target=directx|reflection.targetResourceBindings.2.stage=fragment|reflection.targetResourceBindings.2.entryPoint=fragment_main|reflection.targetResourceBindings.2.name=colorMap|reflection.targetResourceBindings.2.kind=texture|reflection.targetResourceBindings.2.sourceType=sampler2D|reflection.targetResourceBindings.2.hlslType=Texture2D<float4>|reflection.targetResourceBindings.2.addressSpace=shader-resource|reflection.targetResourceBindings.2.abi=registerBinding|reflection.targetResourceBindings.2.bindingClass=srv|reflection.targetResourceBindings.2.descriptorType=SRV|reflection.targetResourceBindings.2.argumentIndex=2|reflection.targetResourceBindings.2.set=0|reflection.targetResourceBindings.2.binding=2|reflection.targetResourceBindings.3.target=directx|reflection.targetResourceBindings.3.stage=fragment|reflection.targetResourceBindings.3.entryPoint=fragment_main|reflection.targetResourceBindings.3.name=linearSampler|reflection.targetResourceBindings.3.kind=sampler|reflection.targetResourceBindings.3.sourceType=sampler|reflection.targetResourceBindings.3.hlslType=SamplerState|reflection.targetResourceBindings.3.addressSpace=sampler|reflection.targetResourceBindings.3.abi=registerBinding|reflection.targetResourceBindings.3.bindingClass=sampler|reflection.targetResourceBindings.3.descriptorType=Sampler|reflection.targetResourceBindings.3.argumentIndex=3|reflection.targetResourceBindings.3.set=0|reflection.targetResourceBindings.3.binding=3|diagnostics.schemaVersion=1"
    "-DEXPECTED_JSON_ARRAY_LENGTHS=rootFiles=3|artifacts=7|reflection.entryPoints=2|reflection.resources=4|reflection.targetResourceBindings=4|reflection.vertexLayouts=1|reflection.vertexLayouts.0.attributes=2|reflection.workgroupSizes=0|reflection.manualTextureCompareKernels=0"
    -DJSON_SCHEMA=${CMAKE_CURRENT_SOURCE_DIR}/docs/schemas/package-inspect-v1.schema.json
    -DJSON_SCHEMA_VALIDATOR=${CMAKE_CURRENT_SOURCE_DIR}/tools/validate_json_schema.py)
crossgl_add_python_expect_test(
  NAME cglc_package_inspect_json_schema_directx_graphics_storage_buffer_resources_source_package
  DEFINITIONS
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_DIRECTX_GRAPHICS_STORAGE_BUFFER_RESOURCE_SHADER}
    -DTARGET=directx
    -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-directx-graphics-storage-buffer-resources-package-inspect.cglb
    -DMODE=package-inspect-source-package
    "-DEXPECTED_JSON_FIELDS=schemaVersion=1|packageFormat=directory|summary.module=DirectXGraphicsStorageBufferResourceShader|summary.target=directx|summary.nativeBinaryStatus=${CROSSGL_DIRECTX_GRAPHICS_SOURCE_PACKAGE_NATIVE_BINARY_STATUS}|summary.artifactCount=7|summary.debugArtifactsPresent=true|artifacts.0.name=backendSource|artifacts.0.path=backend/directx/DirectXGraphicsStorageBufferResourceShader.graphics.hlsl|artifacts.0.exists=true|artifacts.1.name=nativeBinary|artifacts.1.path=backend/directx/DirectXGraphicsStorageBufferResourceShader.dxil|artifacts.1.exists=${CROSSGL_DIRECTX_GRAPHICS_SOURCE_PACKAGE_NATIVE_BINARY_EXISTS}|artifacts.6.name=graphicsAbi|artifacts.6.path=backend/directx/DirectXGraphicsStorageBufferResourceShader.graphics-abi.json|artifacts.6.exists=true|manifest.target=directx|manifest.module=DirectXGraphicsStorageBufferResourceShader|manifest.artifacts.backendSource=backend/directx/DirectXGraphicsStorageBufferResourceShader.graphics.hlsl|manifest.artifacts.nativeBinary=backend/directx/DirectXGraphicsStorageBufferResourceShader.dxil|manifest.artifacts.nativeBinaryStatus=${CROSSGL_DIRECTX_GRAPHICS_SOURCE_PACKAGE_NATIVE_BINARY_STATUS}|manifest.artifacts.graphicsAbi=backend/directx/DirectXGraphicsStorageBufferResourceShader.graphics-abi.json|reflection.target=directx|reflection.module=DirectXGraphicsStorageBufferResourceShader|reflection.nativeBinary=backend/directx/DirectXGraphicsStorageBufferResourceShader.dxil|reflection.resources.0.stage=vertex|reflection.resources.0.name=vertexOffsets|reflection.resources.0.kind=buffer|reflection.resources.1.stage=vertex|reflection.resources.1.name=drawData|reflection.resources.2.stage=fragment|reflection.resources.2.name=drawData|reflection.resources.3.stage=fragment|reflection.resources.3.name=fragmentScales|reflection.targetResourceBindings.0.stage=vertex|reflection.targetResourceBindings.0.name=vertexOffsets|reflection.targetResourceBindings.0.hlslType=RWStructuredBuffer<float4>|reflection.targetResourceBindings.1.stage=vertex|reflection.targetResourceBindings.1.name=drawData|reflection.targetResourceBindings.1.hlslType=RWStructuredBuffer<DrawData>|reflection.targetResourceBindings.2.stage=fragment|reflection.targetResourceBindings.2.name=drawData|reflection.targetResourceBindings.2.hlslType=RWStructuredBuffer<DrawData>|reflection.targetResourceBindings.3.stage=fragment|reflection.targetResourceBindings.3.name=fragmentScales|reflection.targetResourceBindings.3.hlslType=RWStructuredBuffer<float4>"
    "-DEXPECTED_JSON_ARRAY_LENGTHS=rootFiles=3|artifacts=7|reflection.entryPoints=2|reflection.resources=4|reflection.targetResourceBindings=4|reflection.vertexLayouts=1|reflection.vertexLayouts.0.attributes=2|reflection.workgroupSizes=0|reflection.manualTextureCompareKernels=0"
    -DJSON_SCHEMA=${CMAKE_CURRENT_SOURCE_DIR}/docs/schemas/package-inspect-v1.schema.json
    -DJSON_SCHEMA_VALIDATOR=${CMAKE_CURRENT_SOURCE_DIR}/tools/validate_json_schema.py)
if(CROSSGL_HAS_OPENGL_NATIVE_VALIDATOR)
  set(CROSSGL_OPENGL_PACKAGE_INSPECT_NATIVE_BINARY_EXISTS true)
  set(CROSSGL_OPENGL_PACKAGE_INSPECT_NATIVE_BINARY_STATUS validated)
  set(CROSSGL_OPENGL_PACKAGE_INSPECT_VALIDATION_STATUS validated)
else()
  set(CROSSGL_OPENGL_PACKAGE_INSPECT_NATIVE_BINARY_EXISTS false)
  set(CROSSGL_OPENGL_PACKAGE_INSPECT_NATIVE_BINARY_STATUS planned)
  set(CROSSGL_OPENGL_PACKAGE_INSPECT_VALIDATION_STATUS skipped-tool-missing)
endif()
crossgl_add_python_expect_test(
  NAME cglc_package_inspect_json_schema_opengl_source_package
  DEFINITIONS
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_STORAGE_BUFFER_COMPUTE_SHADER}
    -DTARGET=opengl
    -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-opengl-package-inspect.cglb
    -DMODE=package-inspect-source-package
    "-DEXPECTED_JSON_FIELDS=schemaVersion=1|packageFormat=directory|summary.module=StorageBufferComputeShader|summary.target=opengl|summary.nativeBinaryStatus=${CROSSGL_OPENGL_PACKAGE_INSPECT_NATIVE_BINARY_STATUS}|summary.artifactCount=6|summary.debugArtifactsPresent=true|rootFiles.0.name=manifest|rootFiles.0.exists=true|rootFiles.1.name=reflection|rootFiles.1.exists=true|rootFiles.2.name=diagnostics|rootFiles.2.exists=true|artifacts.0.name=backendSource|artifacts.0.path=backend/opengl/StorageBufferComputeShader.comp.glsl|artifacts.0.exists=true|artifacts.1.name=nativeBinary|artifacts.1.path=backend/opengl/StorageBufferComputeShader.glsl|artifacts.1.exists=${CROSSGL_OPENGL_PACKAGE_INSPECT_NATIVE_BINARY_EXISTS}|artifacts.2.name=debugMetadata|artifacts.2.exists=true|artifacts.3.name=hirSourceMap|artifacts.3.exists=true|artifacts.4.name=nativeArtifactDescriptor|artifacts.4.path=backend/opengl/StorageBufferComputeShader.native-artifact.json|artifacts.4.exists=true|manifest.target=opengl|manifest.module=StorageBufferComputeShader|manifest.artifacts.nativeBinaryStatus=${CROSSGL_OPENGL_PACKAGE_INSPECT_NATIVE_BINARY_STATUS}|manifest.artifacts.nativeArtifactDescriptor=backend/opengl/StorageBufferComputeShader.native-artifact.json|targetLegalizationEvidence.manifestToolRequirements.present=true|targetLegalizationEvidence.manifestToolRequirements.target=opengl|targetLegalizationEvidence.manifestToolRequirements.packageMode=source-package|targetLegalizationEvidence.manifestToolRequirements.requiredToolCount=2|targetLegalizationEvidence.manifestToolRequirements.missingToolCount=2|targetLegalizationEvidence.manifestToolRequirements.optionalNativeToolMissing=true|targetLegalizationEvidence.manifestToolRequirements.optionalNativeToolStatus=missing|targetLegalizationEvidence.checks.manifestToolRequirementsTargetMatchesPackage=true|targetLegalizationEvidence.checks.manifestToolRequirementsPackageModeMatchesRequirements=true|targetLegalizationEvidence.checks.manifestToolRequirementEvidenceIdsPresent=true|targetLegalizationEvidence.checks.debugMetadataToolRequirementsMatchManifest=true|nativeArtifactDescriptor.health=ok|nativeArtifactDescriptor.target=opengl|nativeArtifactDescriptor.binaryKind=opengl.source|nativeArtifactDescriptor.sourcePath=backend/opengl/StorageBufferComputeShader.comp.glsl|nativeArtifactDescriptor.nativeBinaryStatus=${CROSSGL_OPENGL_PACKAGE_INSPECT_NATIVE_BINARY_STATUS}|nativeArtifactDescriptor.checks.sourcePathMatchesManifest=true|nativeArtifactDescriptor.checks.sourceHashMatchesFile=true|nativeArtifactDescriptor.checks.artifactPathMatchesManifest=true|reflection.target=opengl|reflection.module=StorageBufferComputeShader|reflection.nativeBinary=backend/opengl/StorageBufferComputeShader.glsl|diagnostics.schemaVersion=1"
    "-DEXPECTED_JSON_FIELD_ONE_OF=targetLegalizationEvidence.checks.targetExplanationToolRequirementsMatchManifest=null,true"
    "-DEXPECTED_JSON_ARRAY_LENGTHS=targetLegalizationEvidence.manifestToolRequirements.requiredToolIds=2|targetLegalizationEvidence.manifestToolRequirements.missingToolIds=2|targetLegalizationEvidence.manifestToolRequirements.toolRequirementEvidenceIds=5"
    "-DEXPECTED_NATIVE_ARTIFACT_DESCRIPTOR_JSON_FIELDS=target=opengl|binaryKind=opengl.source|sourcePath=backend/opengl/StorageBufferComputeShader.comp.glsl|nativeBinaryStatus=${CROSSGL_OPENGL_PACKAGE_INSPECT_NATIVE_BINARY_STATUS}"
    "-DEXPECTED_DEBUG_METADATA_JSON_FIELDS=sourcePackageValidation.target=opengl|sourcePackageValidation.tool=glslangValidator|sourcePackageValidation.policy=use-when-available|sourcePackageValidation.status=${CROSSGL_OPENGL_PACKAGE_INSPECT_VALIDATION_STATUS}"
    -DJSON_SCHEMA=${CMAKE_CURRENT_SOURCE_DIR}/docs/schemas/package-inspect-v1.schema.json
    -DNATIVE_ARTIFACT_JSON_SCHEMA=${CMAKE_CURRENT_SOURCE_DIR}/docs/schemas/native-artifact-v0.schema.json
    -DJSON_SCHEMA_VALIDATOR=${CMAKE_CURRENT_SOURCE_DIR}/tools/validate_json_schema.py)

function(crossgl_add_opengl_compute_fake_glslang_package_inspect_test)
  set(options TOOLCHAIN_DISABLE_FALLBACK)
  set(one_value_args
    NAME
    TOOLCHAIN_PATH
    EXPECTED_NATIVE_BINARY_STATUS
    EXPECTED_NATIVE_BINARY_EXISTS
    EXPECTED_VALIDATION_STATUS
    EXPECTED_DIAGNOSTIC_FIELDS
    EXPECTED_DIAGNOSTICS_ARRAY_LENGTHS
    EXPECTED_TOOL_LOG
    EXPECTED_TOOL_LOG_CONTAINS)
  cmake_parse_arguments(CROSSGL_OPENGL_FAKE_GLSLANG_INSPECT
    "${options}" "${one_value_args}" "" ${ARGN})
  if(NOT CROSSGL_OPENGL_FAKE_GLSLANG_INSPECT_NAME)
    message(FATAL_ERROR
      "crossgl_add_opengl_compute_fake_glslang_package_inspect_test requires NAME")
  endif()
  if(NOT CROSSGL_OPENGL_FAKE_GLSLANG_INSPECT_TOOLCHAIN_PATH)
    message(FATAL_ERROR
      "crossgl_add_opengl_compute_fake_glslang_package_inspect_test requires TOOLCHAIN_PATH")
  endif()
  if(NOT DEFINED CROSSGL_OPENGL_FAKE_GLSLANG_INSPECT_EXPECTED_NATIVE_BINARY_EXISTS)
    message(FATAL_ERROR
      "crossgl_add_opengl_compute_fake_glslang_package_inspect_test requires EXPECTED_NATIVE_BINARY_EXISTS")
  endif()

  set(opengl_fake_glslang_inspect_extra_json_paths "")
  set(opengl_fake_glslang_inspect_extra_json_fields
    "|nativeArtifactDescriptor.validationStatus=unavailable")
  set(opengl_fake_glslang_inspect_extra_native_descriptor_paths
    "sourceHash.value")
  set(opengl_fake_glslang_inspect_extra_native_descriptor_fields
    "|sourceHash.algorithm=sha256|toolchainProvenance.tools.0.name=CrossGL OpenGL backend|toolchainProvenance.tools.0.role=generator|validationStatus=unavailable")
  set(opengl_fake_glslang_inspect_extra_native_descriptor_array_lengths
    "toolchainProvenance.tools=1|validationDiagnostics=0")
  if(CROSSGL_OPENGL_FAKE_GLSLANG_INSPECT_EXPECTED_NATIVE_BINARY_STATUS
     STREQUAL "validated")
    set(opengl_fake_glslang_inspect_extra_json_paths
      "artifacts.1.sizeBytes|artifacts.1.sha256|nativeArtifactDescriptor.sourceHash|nativeArtifactDescriptor.artifactHash|nativeArtifactDescriptor.sizeBytes")
    set(opengl_fake_glslang_inspect_extra_json_fields
      "|nativeArtifactDescriptor.artifactPath=backend/opengl/StorageBufferComputeShader.glsl|nativeArtifactDescriptor.validationStatus=validated|nativeArtifactDescriptor.checks.nativeBinaryStatusMatchesPackage=true|nativeArtifactDescriptor.checks.artifactHashMatchesFile=true|nativeArtifactDescriptor.checks.sizeBytesMatchesFile=true|nativeArtifactDescriptor.checks.validationStatusMatchesNativeStatus=true")
    set(opengl_fake_glslang_inspect_extra_native_descriptor_paths
      "sourceHash.value|artifactHash.value|sizeBytes")
    set(opengl_fake_glslang_inspect_extra_native_descriptor_fields
      "|sourceHash.algorithm=sha256|artifactPath=backend/opengl/StorageBufferComputeShader.glsl|artifactHash.algorithm=sha256|validationStatus=validated")
    set(opengl_fake_glslang_inspect_extra_native_descriptor_array_lengths
      "toolchainProvenance.tools=2|validationDiagnostics=0")
  endif()

  set(inspect_definitions
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_STORAGE_BUFFER_COMPUTE_SHADER}
    -DTARGET=opengl
    -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/${CROSSGL_OPENGL_FAKE_GLSLANG_INSPECT_NAME}.cglb
    -DMODE=package-inspect-source-package
    "-DTOOLCHAIN_PATH=${CROSSGL_OPENGL_FAKE_GLSLANG_INSPECT_TOOLCHAIN_PATH}"
    "-DEXPECTED_JSON_FIELDS=schemaVersion=1|packageFormat=directory|summary.module=StorageBufferComputeShader|summary.target=opengl|summary.nativeBinaryStatus=${CROSSGL_OPENGL_FAKE_GLSLANG_INSPECT_EXPECTED_NATIVE_BINARY_STATUS}|summary.artifactCount=6|summary.debugArtifactsPresent=true|artifacts.0.name=backendSource|artifacts.0.path=backend/opengl/StorageBufferComputeShader.comp.glsl|artifacts.0.exists=true|artifacts.1.name=nativeBinary|artifacts.1.path=backend/opengl/StorageBufferComputeShader.glsl|artifacts.1.exists=${CROSSGL_OPENGL_FAKE_GLSLANG_INSPECT_EXPECTED_NATIVE_BINARY_EXISTS}|artifacts.2.name=debugMetadata|artifacts.2.path=ir/debug-metadata.json|artifacts.2.exists=true|artifacts.3.name=hirSourceMap|artifacts.3.path=ir/hir-source-map.json|artifacts.3.exists=true|artifacts.4.name=nativeArtifactDescriptor|artifacts.4.path=backend/opengl/StorageBufferComputeShader.native-artifact.json|artifacts.4.exists=true|manifest.target=opengl|manifest.module=StorageBufferComputeShader|manifest.artifacts.backendSource=backend/opengl/StorageBufferComputeShader.comp.glsl|manifest.artifacts.nativeBinary=backend/opengl/StorageBufferComputeShader.glsl|manifest.artifacts.nativeBinaryStatus=${CROSSGL_OPENGL_FAKE_GLSLANG_INSPECT_EXPECTED_NATIVE_BINARY_STATUS}|manifest.artifacts.nativeArtifactDescriptor=backend/opengl/StorageBufferComputeShader.native-artifact.json|nativeArtifactDescriptor.health=ok|nativeArtifactDescriptor.target=opengl|nativeArtifactDescriptor.binaryKind=opengl.source|nativeArtifactDescriptor.sourcePath=backend/opengl/StorageBufferComputeShader.comp.glsl|nativeArtifactDescriptor.nativeBinaryStatus=${CROSSGL_OPENGL_FAKE_GLSLANG_INSPECT_EXPECTED_NATIVE_BINARY_STATUS}|nativeArtifactDescriptor.checks.sourcePathMatchesManifest=true|nativeArtifactDescriptor.checks.sourceHashMatchesFile=true|nativeArtifactDescriptor.checks.artifactPathMatchesManifest=true|reflection.target=opengl|reflection.module=StorageBufferComputeShader|reflection.nativeBinary=backend/opengl/StorageBufferComputeShader.glsl|diagnostics.schemaVersion=1|${CROSSGL_OPENGL_FAKE_GLSLANG_INSPECT_EXPECTED_DIAGNOSTIC_FIELDS}${opengl_fake_glslang_inspect_extra_json_fields}"
    "-DEXPECTED_NATIVE_ARTIFACT_DESCRIPTOR_JSON_FIELDS=target=opengl|binaryKind=opengl.source|sourcePath=backend/opengl/StorageBufferComputeShader.comp.glsl|nativeBinaryStatus=${CROSSGL_OPENGL_FAKE_GLSLANG_INSPECT_EXPECTED_NATIVE_BINARY_STATUS}${opengl_fake_glslang_inspect_extra_native_descriptor_fields}"
    "-DEXPECTED_DEBUG_METADATA_JSON_FIELDS=sourcePackageValidation.target=opengl|sourcePackageValidation.tool=glslangValidator|sourcePackageValidation.policy=use-when-available|sourcePackageValidation.status=${CROSSGL_OPENGL_FAKE_GLSLANG_INSPECT_EXPECTED_VALIDATION_STATUS}"
    "-DEXPECTED_JSON_ARRAY_LENGTHS=rootFiles=3|artifacts=6|${CROSSGL_OPENGL_FAKE_GLSLANG_INSPECT_EXPECTED_DIAGNOSTICS_ARRAY_LENGTHS}"
    -DJSON_SCHEMA=${CMAKE_CURRENT_SOURCE_DIR}/docs/schemas/package-inspect-v1.schema.json
    -DNATIVE_ARTIFACT_JSON_SCHEMA=${CMAKE_CURRENT_SOURCE_DIR}/docs/schemas/native-artifact-v0.schema.json
    -DJSON_SCHEMA_VALIDATOR=${CMAKE_CURRENT_SOURCE_DIR}/tools/validate_json_schema.py)
  if(opengl_fake_glslang_inspect_extra_json_paths)
    list(APPEND inspect_definitions
      "-DEXPECTED_JSON_PATHS=${opengl_fake_glslang_inspect_extra_json_paths}")
  endif()
  if(opengl_fake_glslang_inspect_extra_native_descriptor_paths)
    list(APPEND inspect_definitions
      "-DEXPECTED_NATIVE_ARTIFACT_DESCRIPTOR_JSON_PATHS=${opengl_fake_glslang_inspect_extra_native_descriptor_paths}")
  endif()
  if(opengl_fake_glslang_inspect_extra_native_descriptor_array_lengths)
    list(APPEND inspect_definitions
      "-DEXPECTED_NATIVE_ARTIFACT_DESCRIPTOR_JSON_ARRAY_LENGTHS=${opengl_fake_glslang_inspect_extra_native_descriptor_array_lengths}")
  endif()
  if(CROSSGL_OPENGL_FAKE_GLSLANG_INSPECT_TOOLCHAIN_DISABLE_FALLBACK)
    list(APPEND inspect_definitions -DTOOLCHAIN_DISABLE_FALLBACK=ON)
  endif()
  if(CROSSGL_OPENGL_FAKE_GLSLANG_INSPECT_EXPECTED_TOOL_LOG)
    list(APPEND inspect_definitions
      "-DEXPECTED_TOOL_LOG=${CROSSGL_OPENGL_FAKE_GLSLANG_INSPECT_EXPECTED_TOOL_LOG}")
  endif()
  if(CROSSGL_OPENGL_FAKE_GLSLANG_INSPECT_EXPECTED_TOOL_LOG_CONTAINS)
    list(APPEND inspect_definitions
      "-DEXPECTED_TOOL_LOG_CONTAINS=${CROSSGL_OPENGL_FAKE_GLSLANG_INSPECT_EXPECTED_TOOL_LOG_CONTAINS}")
  endif()

  crossgl_add_python_expect_test(
    NAME "${CROSSGL_OPENGL_FAKE_GLSLANG_INSPECT_NAME}"
    DEFINITIONS ${inspect_definitions})
endfunction()

crossgl_add_opengl_compute_fake_glslang_package_inspect_test(
  NAME cglc_package_inspect_opengl_compute_fake_glslang_success
  TOOLCHAIN_PATH ${CROSSGL_FAKE_GLSLANG_SUCCESS_DIR}
  TOOLCHAIN_DISABLE_FALLBACK
  EXPECTED_NATIVE_BINARY_STATUS validated
  EXPECTED_NATIVE_BINARY_EXISTS true
  EXPECTED_VALIDATION_STATUS validated
  EXPECTED_DIAGNOSTIC_FIELDS "diagnostics.diagnostics.0.severity=note|diagnostics.diagnostics.0.code=opengl.glsl-validated"
  EXPECTED_DIAGNOSTICS_ARRAY_LENGTHS "diagnostics.diagnostics=1"
  EXPECTED_TOOL_LOG ${CROSSGL_FAKE_GLSLANG_SUCCESS_DIR}/glslangValidator.log
  EXPECTED_TOOL_LOG_CONTAINS "glslangValidator success: -S comp")

crossgl_add_opengl_compute_fake_glslang_package_inspect_test(
  NAME cglc_package_inspect_opengl_compute_fake_glslang_tool_failure
  TOOLCHAIN_PATH ${CROSSGL_FAKE_GLSLANG_FAILURE_DIR}
  TOOLCHAIN_DISABLE_FALLBACK
  EXPECTED_NATIVE_BINARY_STATUS planned
  EXPECTED_NATIVE_BINARY_EXISTS false
  EXPECTED_VALIDATION_STATUS failed
  EXPECTED_DIAGNOSTIC_FIELDS "diagnostics.diagnostics.0.severity=warning|diagnostics.diagnostics.0.code=opengl.glslang-failed|diagnostics.diagnostics.1.severity=warning|diagnostics.diagnostics.1.code=opengl.source-package-only"
  EXPECTED_DIAGNOSTICS_ARRAY_LENGTHS "diagnostics.diagnostics=2|diagnostics.diagnostics.0.missingCapabilities=2"
  EXPECTED_TOOL_LOG ${CROSSGL_FAKE_GLSLANG_FAILURE_DIR}/glslangValidator.log
  EXPECTED_TOOL_LOG_CONTAINS "glslangValidator failure: -S comp")

crossgl_add_opengl_compute_fake_glslang_package_inspect_test(
  NAME cglc_package_inspect_opengl_compute_fake_glslang_unavailable
  TOOLCHAIN_PATH ${CROSSGL_FAKE_TOOL_UNAVAILABLE_DIR}
  TOOLCHAIN_DISABLE_FALLBACK
  EXPECTED_NATIVE_BINARY_STATUS planned
  EXPECTED_NATIVE_BINARY_EXISTS false
  EXPECTED_VALIDATION_STATUS skipped-tool-missing
  EXPECTED_DIAGNOSTIC_FIELDS "diagnostics.diagnostics.0.severity=warning|diagnostics.diagnostics.0.code=opengl.source-package-only"
  EXPECTED_DIAGNOSTICS_ARRAY_LENGTHS "diagnostics.diagnostics=1")
if(CROSSGL_HAS_OPENGL_NATIVE_VALIDATOR)
  set(CROSSGL_OPENGL_SOURCE_PACKAGE_NATIVE_BINARY_STATUS validated)
  set(CROSSGL_OPENGL_SOURCE_PACKAGE_NATIVE_BINARY_EXISTS true)
  set(CROSSGL_OPENGL_SHADOW_LOD_NATIVE_DIAGNOSTIC
      -DEXPECTED_DIAGNOSTIC=opengl.glsl-validated)
  set(CROSSGL_OPENGL_TEXTURE_COMPARE_LOD_NATIVE_BINARY
      -DEXPECTED_NATIVE_BINARY=backend/opengl/TextureCompareLodShader.glsl)
  set(CROSSGL_OPENGL_TEXTURE_ARRAY_SHADOW_COMPARE_LOD_NATIVE_BINARY
      -DEXPECTED_NATIVE_BINARY=backend/opengl/TextureArrayShadowCompareLodUnsupportedShader.glsl)
  set(CROSSGL_OPENGL_TEXTURE_2D_ARRAY_SHADOW_COMPARE_LOD_NATIVE_BINARY
      -DEXPECTED_NATIVE_BINARY=backend/opengl/Texture2DArrayShadowCompareLodUnsupportedShader.glsl)
  set(CROSSGL_OPENGL_TEXTURE_CUBE_SHADOW_COMPARE_LOD_NATIVE_BINARY
      -DEXPECTED_NATIVE_BINARY=backend/opengl/TextureCubeShadowCompareLodUnsupportedShader.glsl)
  set(CROSSGL_OPENGL_TEXTURE_CUBE_ARRAY_SHADOW_COMPARE_LOD_NATIVE_BINARY
      -DEXPECTED_NATIVE_BINARY=backend/opengl/TextureCubeArrayShadowCompareLodUnsupportedShader.glsl)
else()
  set(CROSSGL_OPENGL_SOURCE_PACKAGE_NATIVE_BINARY_STATUS planned)
  set(CROSSGL_OPENGL_SOURCE_PACKAGE_NATIVE_BINARY_EXISTS false)
  set(CROSSGL_OPENGL_SHADOW_LOD_NATIVE_DIAGNOSTIC
      "-DEXPECTED_DIAGNOSTICS_JSON_FIELDS=diagnostics.0.severity=warning|diagnostics.0.code=opengl.source-package-only"
      "-DEXPECTED_DIAGNOSTICS_JSON_FIELD_CONTAINS=diagnostics.0.message=glslangValidator was not found"
      "-DEXPECTED_DIAGNOSTICS_JSON_ARRAY_LENGTHS=diagnostics=1")
  set(CROSSGL_OPENGL_TEXTURE_COMPARE_LOD_NATIVE_BINARY)
  set(CROSSGL_OPENGL_TEXTURE_ARRAY_SHADOW_COMPARE_LOD_NATIVE_BINARY)
  set(CROSSGL_OPENGL_TEXTURE_2D_ARRAY_SHADOW_COMPARE_LOD_NATIVE_BINARY)
  set(CROSSGL_OPENGL_TEXTURE_CUBE_SHADOW_COMPARE_LOD_NATIVE_BINARY)
  set(CROSSGL_OPENGL_TEXTURE_CUBE_ARRAY_SHADOW_COMPARE_LOD_NATIVE_BINARY)
endif()
crossgl_add_python_expect_test(
  NAME cglc_package_inspect_json_schema_opengl_graphics_resources_source_package
  DEFINITIONS
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_OPENGL_GRAPHICS_RESOURCES_SHADER}
    -DTARGET=opengl
    -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-opengl-graphics-resources-package-inspect.cglb
    -DMODE=package-inspect-source-package
    "-DEXPECTED_JSON_FIELDS=schemaVersion=1|packageFormat=directory|summary.module=OpenGLGraphicsResourcesShader|summary.target=opengl|summary.nativeBinaryStatus=${CROSSGL_OPENGL_SOURCE_PACKAGE_NATIVE_BINARY_STATUS}|summary.artifactCount=7|summary.debugArtifactsPresent=true|rootFiles.0.name=manifest|rootFiles.0.exists=true|rootFiles.1.name=reflection|rootFiles.1.exists=true|rootFiles.2.name=diagnostics|rootFiles.2.exists=true|artifacts.0.name=backendSource|artifacts.0.path=backend/opengl/OpenGLGraphicsResourcesShader.graphics.glsl|artifacts.0.exists=true|artifacts.1.name=nativeBinary|artifacts.1.path=backend/opengl/OpenGLGraphicsResourcesShader.glsl|artifacts.1.exists=${CROSSGL_OPENGL_SOURCE_PACKAGE_NATIVE_BINARY_EXISTS}|artifacts.2.name=debugMetadata|artifacts.2.path=ir/debug-metadata.json|artifacts.2.exists=true|artifacts.3.name=hirSourceMap|artifacts.3.path=ir/hir-source-map.json|artifacts.3.exists=true|artifacts.6.name=graphicsAbi|artifacts.6.path=backend/opengl/OpenGLGraphicsResourcesShader.graphics-abi.json|artifacts.6.exists=true|manifest.target=opengl|manifest.module=OpenGLGraphicsResourcesShader|manifest.artifacts.backendSource=backend/opengl/OpenGLGraphicsResourcesShader.graphics.glsl|manifest.artifacts.nativeBinary=backend/opengl/OpenGLGraphicsResourcesShader.glsl|manifest.artifacts.nativeBinaryStatus=${CROSSGL_OPENGL_SOURCE_PACKAGE_NATIVE_BINARY_STATUS}|manifest.artifacts.debugMetadata=ir/debug-metadata.json|manifest.artifacts.hirSourceMap=ir/hir-source-map.json|manifest.artifacts.graphicsAbi=backend/opengl/OpenGLGraphicsResourcesShader.graphics-abi.json|reflection.target=opengl|reflection.module=OpenGLGraphicsResourcesShader|reflection.nativeBinary=backend/opengl/OpenGLGraphicsResourcesShader.glsl|reflection.entryPoints.0.stage=vertex|reflection.entryPoints.0.backendName=vertex_main|reflection.entryPoints.1.stage=fragment|reflection.entryPoints.1.backendName=fragment_main|reflection.resources.0.stage=vertex|reflection.resources.0.name=vertexParams|reflection.resources.0.kind=uniform|reflection.resources.0.set=0|reflection.resources.0.binding=0|reflection.resources.1.stage=fragment|reflection.resources.1.name=fragmentParams|reflection.resources.1.kind=uniform|reflection.resources.1.set=0|reflection.resources.1.binding=1|reflection.targetResourceBindings.0.target=opengl|reflection.targetResourceBindings.0.entryPoint=vertex_main|reflection.targetResourceBindings.0.bindingClass=uniform-buffer|reflection.targetResourceBindings.0.argumentIndex=0|reflection.targetResourceBindings.1.target=opengl|reflection.targetResourceBindings.1.entryPoint=fragment_main|reflection.targetResourceBindings.1.bindingClass=uniform-buffer|reflection.targetResourceBindings.1.argumentIndex=1|diagnostics.schemaVersion=1"
    "-DEXPECTED_JSON_ARRAY_LENGTHS=rootFiles=3|artifacts=7|reflection.entryPoints=2|reflection.resources=2|reflection.targetResourceBindings=2|reflection.vertexLayouts=1|reflection.workgroupSizes=0"
    -DJSON_SCHEMA=${CMAKE_CURRENT_SOURCE_DIR}/docs/schemas/package-inspect-v1.schema.json
    -DJSON_SCHEMA_VALIDATOR=${CMAKE_CURRENT_SOURCE_DIR}/tools/validate_json_schema.py)
add_test(NAME cglc_build_opengl_storage_buffer_source_package
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_STORAGE_BUFFER_COMPUTE_SHADER}
    -DTARGET=opengl
    -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-opengl-storage-buffer-source.cglb
    -DMODE=source-package-build
    -DEXPECTED_SOURCE=backend/opengl/StorageBufferComputeShader.comp.glsl
    -DEXPECTED_SOURCE_SNIPPET=std430
    "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=opengl|module=StorageBufferComputeShader"
    "-DEXPECTED_REFLECTION_TARGET_FIELDS=values.sourceType=float*|values.bindingClass=storage-buffer|values.argumentIndex=0|values.storageBufferLayout.layout=std430|values.storageBufferLayout.elementType=float"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_build_opengl_source_package_fake_glslang_success
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_STORAGE_BUFFER_COMPUTE_SHADER}
    -DTARGET=opengl
    -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-opengl-fake-glslang-success.cglb
    -DMODE=source-package-build
    -DTOOLCHAIN_PATH=${CROSSGL_FAKE_GLSLANG_SUCCESS_DIR}
    -DTOOLCHAIN_DISABLE_FALLBACK=ON
    -DEXPECTED_SOURCE=backend/opengl/StorageBufferComputeShader.comp.glsl
    -DEXPECTED_NATIVE_BINARY=backend/opengl/StorageBufferComputeShader.glsl
    -DEXPECTED_NATIVE_BINARY_STATUS=validated
    "-DEXPECTED_DEBUG_METADATA_JSON_FIELDS=sourcePackageValidation.target=opengl|sourcePackageValidation.tool=glslangValidator|sourcePackageValidation.policy=use-when-available|sourcePackageValidation.status=validated"
    "-DEXPECTED_DIAGNOSTICS_JSON_FIELDS=diagnostics.0.severity=note|diagnostics.0.code=opengl.glsl-validated"
    -DEXPECTED_DIAGNOSTIC=opengl.glsl-validated
    "-DEXPECTED_DIAGNOSTIC_FIELD_CONTAINS=message=GLSL 450"
    "-DEXPECTED_DIAGNOSTICS_JSON_ARRAY_LENGTHS=diagnostics=1"
    "-DEXPECTED_NATIVE_ARTIFACT_DESCRIPTOR_JSON_FIELDS=target=opengl|binaryKind=opengl.source|sourcePath=backend/opengl/StorageBufferComputeShader.comp.glsl|sourceHash.algorithm=sha256|artifactPath=backend/opengl/StorageBufferComputeShader.glsl|artifactHash.algorithm=sha256|validationStatus=validated|nativeBinaryStatus=validated"
    "-DEXPECTED_NATIVE_ARTIFACT_DESCRIPTOR_JSON_PATHS=sourceHash.value|artifactHash.value|sizeBytes"
    "-DEXPECTED_NATIVE_ARTIFACT_DESCRIPTOR_JSON_ARRAY_LENGTHS=toolchainProvenance.tools=2|validationDiagnostics=0"
    -DEXPECTED_TOOL_LOG=${CROSSGL_FAKE_GLSLANG_SUCCESS_DIR}/glslangValidator.log
    "-DEXPECTED_TOOL_LOG_CONTAINS=glslangValidator success: -S comp"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_build_opengl_source_package_fake_glslang_tool_failure
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_STORAGE_BUFFER_COMPUTE_SHADER}
    -DTARGET=opengl
    -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-opengl-fake-glslang-failure.cglb
    -DMODE=source-package-build
    -DTOOLCHAIN_PATH=${CROSSGL_FAKE_GLSLANG_FAILURE_DIR}
    -DTOOLCHAIN_DISABLE_FALLBACK=ON
    -DEXPECTED_SOURCE=backend/opengl/StorageBufferComputeShader.comp.glsl
    -DEXPECTED_NATIVE_BINARY_ABSENT=backend/opengl/StorageBufferComputeShader.glsl
    -DEXPECTED_NATIVE_BINARY_STATUS=planned
    "-DEXPECTED_DEBUG_METADATA_JSON_FIELDS=sourcePackageValidation.target=opengl|sourcePackageValidation.tool=glslangValidator|sourcePackageValidation.policy=use-when-available|sourcePackageValidation.status=failed"
    -DEXPECTED_DIAGNOSTIC=opengl.glslang-failed
    "-DEXPECTED_DIAGNOSTICS_JSON_FIELDS=diagnostics.0.severity=warning|diagnostics.0.code=opengl.glslang-failed|diagnostics.0.target=opengl|diagnostics.1.severity=warning|diagnostics.1.code=opengl.source-package-only"
    "-DEXPECTED_DIAGNOSTIC_FIELD_CONTAINS=message=GLSL 450"
    "-DEXPECTED_DIAGNOSTIC_ARRAY_CONTAINS=missingCapabilities=opengl.backend.native-glsl-package|missingCapabilities=opengl.validation.glsl-program-validation"
    "-DEXPECTED_DIAGNOSTICS_JSON_ARRAY_LENGTHS=diagnostics=2|diagnostics.0.missingCapabilities=2"
    "-DEXPECTED_NATIVE_ARTIFACT_DESCRIPTOR_JSON_FIELDS=target=opengl|binaryKind=opengl.source|sourcePath=backend/opengl/StorageBufferComputeShader.comp.glsl|sourceHash.algorithm=sha256|nativeBinaryStatus=planned|validationStatus=unavailable|toolchainProvenance.tools.0.name=CrossGL OpenGL backend|toolchainProvenance.tools.0.role=generator"
    "-DEXPECTED_NATIVE_ARTIFACT_DESCRIPTOR_JSON_PATHS=sourceHash.value"
    "-DEXPECTED_NATIVE_ARTIFACT_DESCRIPTOR_JSON_ARRAY_LENGTHS=toolchainProvenance.tools=1|validationDiagnostics=0"
    -DEXPECTED_TOOL_LOG=${CROSSGL_FAKE_GLSLANG_FAILURE_DIR}/glslangValidator.log
    "-DEXPECTED_TOOL_LOG_CONTAINS=glslangValidator failure: -S comp"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_build_opengl_source_package_fake_glslang_unavailable
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_STORAGE_BUFFER_COMPUTE_SHADER}
    -DTARGET=opengl
    -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-opengl-fake-glslang-unavailable.cglb
    -DMODE=source-package-build
    -DTOOLCHAIN_PATH=${CROSSGL_FAKE_TOOL_UNAVAILABLE_DIR}
    -DTOOLCHAIN_DISABLE_FALLBACK=ON
    -DEXPECTED_SOURCE=backend/opengl/StorageBufferComputeShader.comp.glsl
    -DEXPECTED_NATIVE_BINARY_ABSENT=backend/opengl/StorageBufferComputeShader.glsl
    -DEXPECTED_NATIVE_BINARY_STATUS=planned
    "-DEXPECTED_DEBUG_METADATA_JSON_FIELDS=sourcePackageValidation.target=opengl|sourcePackageValidation.tool=glslangValidator|sourcePackageValidation.policy=use-when-available|sourcePackageValidation.status=skipped-tool-missing"
    "-DEXPECTED_DIAGNOSTICS_JSON_FIELDS=diagnostics.0.severity=warning|diagnostics.0.code=opengl.source-package-only"
    "-DEXPECTED_DIAGNOSTICS_JSON_FIELD_CONTAINS=diagnostics.0.message=glslangValidator was not found"
    -DEXPECTED_DIAGNOSTIC=opengl.source-package-only
    "-DEXPECTED_DIAGNOSTIC_FIELD_CONTAINS=message=GLSL 450"
    "-DEXPECTED_DIAGNOSTICS_JSON_ARRAY_LENGTHS=diagnostics=1"
    "-DEXPECTED_NATIVE_ARTIFACT_DESCRIPTOR_JSON_FIELDS=target=opengl|binaryKind=opengl.source|sourcePath=backend/opengl/StorageBufferComputeShader.comp.glsl|sourceHash.algorithm=sha256|nativeBinaryStatus=planned|validationStatus=unavailable|toolchainProvenance.tools.0.name=CrossGL OpenGL backend|toolchainProvenance.tools.0.role=generator"
    "-DEXPECTED_NATIVE_ARTIFACT_DESCRIPTOR_JSON_PATHS=sourceHash.value"
    "-DEXPECTED_NATIVE_ARTIFACT_DESCRIPTOR_JSON_ARRAY_LENGTHS=toolchainProvenance.tools=1|validationDiagnostics=0"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
crossgl_label_optional_native_policy_test(
  cglc_build_opengl_source_package_fake_glslang_tool_failure opengl)
crossgl_label_optional_native_policy_test(
  cglc_build_opengl_source_package_fake_glslang_unavailable opengl)
if(CROSSGL_HAS_OPENGL_NATIVE_VALIDATOR)
  add_test(NAME cglc_opengl_toolchain_native_smoke
    COMMAND ${CMAKE_COMMAND}
      -DCGLC=$<TARGET_FILE:cglc>
      -DINPUT=${CROSSGL_STORAGE_BUFFER_COMPUTE_SHADER}
      -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-opengl-real-glslang-smoke.cglb
      -DEXPECTED_MODULE=StorageBufferComputeShader
      -DGLSLANG_VALIDATOR=${CROSSGL_GLSLANG_VALIDATOR}
      -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/OpenGLToolchainSmoke.cmake)
  crossgl_label_optional_native_test(cglc_opengl_toolchain_native_smoke opengl)
else()
  crossgl_add_optional_native_skip_test(
    NAME cglc_opengl_toolchain_native_smoke_unavailable
    TARGET opengl
    REQUIRED_VARS CROSSGL_GLSLANG_VALIDATOR
    REASON "OpenGL glslangValidator smoke skipped")
endif()
set(CROSSGL_OPENGL_WORKGROUP_SHARED_SOURCE_SNIPPET [=[layout(local_size_x = 8, local_size_y = 2, local_size_z = 1) in;

shared float tile[TILE_SIZE];

void main() {
  tile[0] = 1.0;
  float first = tile[0];
  tile[1] = first + 1.0;]=])
set(CROSSGL_OPENGL_WORKGROUP_SHARED_FEATURE_FIELDS
    "glsl-lowering.kind=backend|compute-kernel.kind=stage|workgroup-size.kind=execution|workgroup-shared-memory.kind=resource|fixed-array.kind=layout|scalar-vector-elements.kind=array|index-access.kind=operation|local-declaration.kind=operation|scalar-arithmetic.kind=operation")
set(CROSSGL_OPENGL_WORKGROUP_SHARED_VALIDATED_FEATURE_FIELDS
    "native-glsl-package.kind=backend|glsl-program-validation.kind=validation|compute-kernel.kind=stage|workgroup-size.kind=execution|workgroup-shared-memory.kind=resource|fixed-array.kind=layout|scalar-vector-elements.kind=array|index-access.kind=operation|local-declaration.kind=operation|scalar-arithmetic.kind=operation")
set(CROSSGL_OPENGL_WORKGROUP_BARRIER_SOURCE_SNIPPET [=[layout(local_size_x = 4, local_size_y = 1, local_size_z = 1) in;

shared float tile[4];

void main() {
  tile[0] = 1.0;
  barrier();
  float first = tile[0];
  barrier();
  tile[1] = first + 1.0;]=])
set(CROSSGL_OPENGL_WORKGROUP_BARRIER_FEATURE_FIELDS
    "${CROSSGL_OPENGL_WORKGROUP_SHARED_FEATURE_FIELDS}")
set(CROSSGL_OPENGL_WORKGROUP_BARRIER_VALIDATED_FEATURE_FIELDS
    "${CROSSGL_OPENGL_WORKGROUP_SHARED_VALIDATED_FEATURE_FIELDS}")
set(CROSSGL_OPENGL_COMPUTE_INVOCATION_BUILTIN_SOURCE_SNIPPET [=[layout(local_size_x = 4, local_size_y = 2, local_size_z = 1) in;

// CrossGL set 0, binding 0
layout(binding = 0, std430) buffer values_Buffer {
  uint values[];
};

void main() {
  uint globalX = gl_GlobalInvocationID.x;
  uint localY = gl_LocalInvocationID.y;
  uint groupZ = gl_WorkGroupID.z;
  values[0] = globalX + localY + groupZ;]=])
set(CROSSGL_OPENGL_COMPUTE_INVOCATION_BUILTIN_FEATURE_FIELDS
    "glsl-lowering.kind=backend|compute-kernel.kind=stage|workgroup-size.kind=execution|storage-buffer.kind=resource|local-declaration.kind=operation|index-access.kind=operation|scalar-arithmetic.kind=operation|storage-buffer-write.kind=operation")
set(CROSSGL_OPENGL_COMPUTE_INVOCATION_BUILTIN_VALIDATED_FEATURE_FIELDS
    "native-glsl-package.kind=backend|glsl-program-validation.kind=validation|compute-kernel.kind=stage|workgroup-size.kind=execution|storage-buffer.kind=resource|local-declaration.kind=operation|index-access.kind=operation|scalar-arithmetic.kind=operation|storage-buffer-write.kind=operation")
set(CROSSGL_OPENGL_ATOMIC_ADD_SOURCE_SNIPPET [=[layout(local_size_x = 4, local_size_y = 1, local_size_z = 1) in;

// CrossGL set 0, binding 0
layout(binding = 0, std430) buffer counters_Buffer {
  int counters[];
};

// CrossGL set 0, binding 1
layout(binding = 1, std430) buffer unsignedCounters_Buffer {
  uint unsignedCounters[];
};

shared int tile[GROUP_SIZE];

shared uint unsignedTile[GROUP_SIZE];

void main() {
  uint index = gl_LocalInvocationID.x;
  uint unsignedDelta = index;
  atomicAdd(counters[index], 1);
  atomicAdd(unsignedCounters[index], unsignedDelta);
  atomicAdd(tile[index], 1);
  atomicAdd(unsignedTile[index], unsignedDelta);]=])
set(CROSSGL_OPENGL_ATOMIC_ADD_FEATURE_FIELDS
    "glsl-lowering.kind=backend|compute-kernel.kind=stage|workgroup-size.kind=execution|storage-buffer.kind=resource|workgroup-shared-memory.kind=resource|fixed-array.kind=layout|index-access.kind=operation|local-declaration.kind=operation")
set(CROSSGL_OPENGL_ATOMIC_ADD_VALIDATED_FEATURE_FIELDS
    "native-glsl-package.kind=backend|glsl-program-validation.kind=validation|compute-kernel.kind=stage|workgroup-size.kind=execution|storage-buffer.kind=resource|workgroup-shared-memory.kind=resource|fixed-array.kind=layout|index-access.kind=operation|local-declaration.kind=operation")
set(CROSSGL_OPENGL_ATOMIC_ADD_RETURN_SOURCE_SNIPPET [=[atomicAdd(counters[index], 1);
  int oldStorage = atomicAdd(counters[index], 2);
  oldStorage = atomicAdd(counters[index], 3);
  uint oldUnsigned = atomicAdd(unsignedCounters[index], unsignedDelta);
  int oldShared = atomicAdd(tile[index], 1);
  uint oldUnsignedShared = atomicAdd(unsignedTile[index], unsignedDelta);
  int oldCompat = atomicAdd(compatCounters[index].active_count, 1);
  uint oldCompatUnsigned = atomicAdd(compatCounters[index].spawn_count, unsignedDelta);]=])
set(CROSSGL_OPENGL_ATOMIC_ADD_RETURN_FEATURE_FIELDS
    "glsl-lowering.kind=backend|compute-kernel.kind=stage|workgroup-size.kind=execution|storage-buffer.kind=resource|workgroup-shared-memory.kind=resource|fixed-array.kind=layout|index-access.kind=operation|local-declaration.kind=operation|storage-buffer-write.kind=operation|scalar-arithmetic.kind=operation|atomic-add.kind=operation|atomic-integer.kind=type")
set(CROSSGL_OPENGL_ATOMIC_ADD_RETURN_VALIDATED_FEATURE_FIELDS
    "native-glsl-package.kind=backend|glsl-program-validation.kind=validation|compute-kernel.kind=stage|workgroup-size.kind=execution|storage-buffer.kind=resource|workgroup-shared-memory.kind=resource|fixed-array.kind=layout|index-access.kind=operation|local-declaration.kind=operation|storage-buffer-write.kind=operation|scalar-arithmetic.kind=operation|atomic-add.kind=operation|atomic-integer.kind=type")
set(CROSSGL_OPENGL_ATOMIC_MINMAX_RETURN_SOURCE_SNIPPET [=[atomicMin(counters[index], value);
  atomicMax(counters[index], value);
  int oldMin = atomicMin(counters[index], value);
  int oldMax = atomicMax(counters[index], 1);
  oldMin = atomicMin(counters[index], 1);
  uint oldMaxU = atomicMax(unsignedCounters[index], unsignedValue);
  int oldShared = atomicMin(tile[index], value);
  uint oldSharedU = atomicMax(unsignedTile[index], unsignedValue);
  int oldCompat = atomicMax(compatCounters[index].active_count, 1);
  uint oldCompatU = atomicMin(compatCounters[index].spawn_count, unsignedValue);]=])
set(CROSSGL_OPENGL_ATOMIC_MINMAX_RETURN_FEATURE_FIELDS
    "glsl-lowering.kind=backend|compute-kernel.kind=stage|workgroup-size.kind=execution|storage-buffer.kind=resource|workgroup-shared-memory.kind=resource|fixed-array.kind=layout|index-access.kind=operation|local-declaration.kind=operation|storage-buffer-write.kind=operation|scalar-arithmetic.kind=operation|atomic-integer.kind=type")
set(CROSSGL_OPENGL_ATOMIC_MINMAX_RETURN_VALIDATED_FEATURE_FIELDS
    "native-glsl-package.kind=backend|glsl-program-validation.kind=validation|compute-kernel.kind=stage|workgroup-size.kind=execution|storage-buffer.kind=resource|workgroup-shared-memory.kind=resource|fixed-array.kind=layout|index-access.kind=operation|local-declaration.kind=operation|storage-buffer-write.kind=operation|scalar-arithmetic.kind=operation|atomic-integer.kind=type")
set(CROSSGL_OPENGL_ATOMIC_EXCHANGE_RETURN_SOURCE_SNIPPET [=[atomicExchange(counters[index], value);
  atomicExchange(unsignedCounters[index], unsignedValue);
  atomicExchange(tile[index], value);
  atomicExchange(unsignedTile[index], unsignedValue);
  int oldStorage = atomicExchange(counters[index], value);
  oldStorage = atomicExchange(counters[index], 1);
  uint oldUnsigned = atomicExchange(unsignedCounters[index], unsignedValue);
  int oldShared = atomicExchange(tile[index], value);
  uint oldUnsignedShared = atomicExchange(unsignedTile[index], unsignedValue);
  int oldCompat = atomicExchange(compatCounters[index].active_count, 1);
  uint oldCompatUnsigned = atomicExchange(compatCounters[index].spawn_count, unsignedValue);]=])
set(CROSSGL_OPENGL_ATOMIC_EXCHANGE_RETURN_FEATURE_FIELDS
    "${CROSSGL_OPENGL_ATOMIC_MINMAX_RETURN_FEATURE_FIELDS}")
set(CROSSGL_OPENGL_ATOMIC_EXCHANGE_RETURN_VALIDATED_FEATURE_FIELDS
    "${CROSSGL_OPENGL_ATOMIC_MINMAX_RETURN_VALIDATED_FEATURE_FIELDS}")
set(CROSSGL_OPENGL_ATOMIC_BITWISE_RETURN_SOURCE_SNIPPET [=[atomicAnd(counters[index], mask);
  atomicOr(unsignedCounters[index], unsignedMask);
  atomicXor(tile[index], mask);
  atomicAnd(unsignedTile[index], unsignedMask);
  int oldAnd = atomicAnd(counters[index], mask);
  int oldOr = atomicOr(counters[index], 1);
  oldAnd = atomicXor(counters[index], 1);
  uint oldUnsignedAnd = atomicAnd(unsignedCounters[index], unsignedMask);
  uint oldUnsignedOr = atomicOr(unsignedTile[index], unsignedMask);
  int oldSharedXor = atomicXor(tile[index], mask);
  int oldCompatOr = atomicOr(compatCounters[index].active_count, 1);
  uint oldCompatXor = atomicXor(compatCounters[index].spawn_count, unsignedMask);]=])
set(CROSSGL_OPENGL_ATOMIC_BITWISE_RETURN_FEATURE_FIELDS
    "${CROSSGL_OPENGL_ATOMIC_MINMAX_RETURN_FEATURE_FIELDS}")
set(CROSSGL_OPENGL_ATOMIC_BITWISE_RETURN_VALIDATED_FEATURE_FIELDS
    "${CROSSGL_OPENGL_ATOMIC_MINMAX_RETURN_VALIDATED_FEATURE_FIELDS}")
add_test(NAME cglc_build_opengl_workgroup_shared_source_package
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CMAKE_CURRENT_SOURCE_DIR}/tests/opengl/fixtures/OpenGLWorkgroupSharedMemoryShader.cgl
    -DTARGET=opengl
    -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-opengl-workgroup-shared-source.cglb
    -DMODE=source-package-build
    -DEXPECTED_SOURCE=backend/opengl/OpenGLWorkgroupSharedMemoryShader.comp.glsl
    "-DEXPECTED_SOURCE_SNIPPET=${CROSSGL_OPENGL_WORKGROUP_SHARED_SOURCE_SNIPPET}"
    "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=opengl|module=OpenGLWorkgroupSharedMemoryShader|resources.0.name=tile|resources.0.kind=shared|resources.0.type=float[TILE_SIZE]|resources.0.addressSpace=shared|workgroupSizes.0.entryPoint=compute_main|workgroupSizes.0.x=8|workgroupSizes.0.y=2|workgroupSizes.0.z=1|workgroupSizes.0.sourceX=TILE_SIZE"
    "-DEXPECTED_REFLECTION_JSON_ARRAY_LENGTHS=resources=1|targetResourceBindings=1|workgroupSizes=1"
    "-DEXPECTED_REFLECTION_TARGET_FIELDS=tile.sourceType=float[TILE_SIZE]|tile.addressSpace=shared|tile.abi=workgroupLocal|tile.bindingClass=shared|tile.arraySize=TILE_SIZE|tile.arrayElementCount=8"
    "-DEXPECTED_REFLECTION_FEATURE_FIELDS=${CROSSGL_OPENGL_WORKGROUP_SHARED_FEATURE_FIELDS}"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_build_opengl_workgroup_barrier_source_package
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CMAKE_CURRENT_SOURCE_DIR}/tests/opengl/fixtures/OpenGLWorkgroupBarrierShader.cgl
    -DTARGET=opengl
    -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-opengl-workgroup-barrier-source.cglb
    -DMODE=source-package-build
    -DEXPECTED_SOURCE=backend/opengl/OpenGLWorkgroupBarrierShader.comp.glsl
    "-DEXPECTED_SOURCE_SNIPPET=${CROSSGL_OPENGL_WORKGROUP_BARRIER_SOURCE_SNIPPET}"
    "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=opengl|module=OpenGLWorkgroupBarrierShader|resources.0.name=tile|resources.0.kind=shared|resources.0.type=float[4]|resources.0.addressSpace=shared|workgroupSizes.0.entryPoint=compute_main|workgroupSizes.0.x=4|workgroupSizes.0.y=1|workgroupSizes.0.z=1|workgroupSizes.0.sourceX=4|workgroupSizes.0.sourceY=1|workgroupSizes.0.sourceZ=1"
    "-DEXPECTED_REFLECTION_JSON_ARRAY_LENGTHS=resources=1|targetResourceBindings=1|workgroupSizes=1"
    "-DEXPECTED_REFLECTION_TARGET_FIELDS=tile.sourceType=float[4]|tile.addressSpace=shared|tile.abi=workgroupLocal|tile.bindingClass=shared|tile.arraySize=4|tile.arrayElementCount=4"
    "-DEXPECTED_REFLECTION_FEATURE_FIELDS=${CROSSGL_OPENGL_WORKGROUP_BARRIER_FEATURE_FIELDS}"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_build_opengl_compute_invocation_builtin_source_package
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CMAKE_CURRENT_SOURCE_DIR}/tests/opengl/fixtures/OpenGLComputeInvocationBuiltinShader.cgl
    -DTARGET=opengl
    -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-opengl-compute-invocation-builtin-source.cglb
    -DMODE=source-package-build
    -DEXPECTED_SOURCE=backend/opengl/OpenGLComputeInvocationBuiltinShader.comp.glsl
    "-DEXPECTED_SOURCE_SNIPPET=${CROSSGL_OPENGL_COMPUTE_INVOCATION_BUILTIN_SOURCE_SNIPPET}"
    "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=opengl|module=OpenGLComputeInvocationBuiltinShader|resources.0.name=values|resources.0.kind=buffer|resources.0.type=uint*|resources.0.binding=0|workgroupSizes.0.entryPoint=compute_main|workgroupSizes.0.x=4|workgroupSizes.0.y=2|workgroupSizes.0.z=1|workgroupSizes.0.sourceX=4|workgroupSizes.0.sourceY=2|workgroupSizes.0.sourceZ=1"
    "-DEXPECTED_REFLECTION_JSON_ARRAY_LENGTHS=resources=1|targetResourceBindings=1|workgroupSizes=1"
    "-DEXPECTED_REFLECTION_TARGET_FIELDS=values.sourceType=uint*|values.bindingClass=storage-buffer|values.argumentIndex=0|values.storageBufferLayout.layout=std430|values.storageBufferLayout.elementType=uint|values.storageBufferLayout.arrayStrideBytes=4"
    "-DEXPECTED_REFLECTION_FEATURE_FIELDS=${CROSSGL_OPENGL_COMPUTE_INVOCATION_BUILTIN_FEATURE_FIELDS}"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_build_opengl_atomic_add_source_package
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CMAKE_CURRENT_SOURCE_DIR}/tests/opengl/fixtures/OpenGLAtomicAddShader.cgl
    -DTARGET=opengl
    -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-opengl-atomic-add-source.cglb
    -DMODE=source-package-build
    -DEXPECTED_SOURCE=backend/opengl/OpenGLAtomicAddShader.comp.glsl
    "-DEXPECTED_SOURCE_SNIPPET=${CROSSGL_OPENGL_ATOMIC_ADD_SOURCE_SNIPPET}"
    "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=opengl|module=OpenGLAtomicAddShader|functionConstants.0.name=GROUP_SIZE|functionConstants.0.value=4|resources.0.name=counters|resources.0.kind=buffer|resources.0.type=atomic<int>*|resources.0.binding=0|resources.1.name=unsignedCounters|resources.1.kind=buffer|resources.1.type=atomic<uint>*|resources.1.binding=1|resources.2.name=tile|resources.2.kind=shared|resources.2.type=atomic<int>[GROUP_SIZE]|resources.2.addressSpace=shared|resources.3.name=unsignedTile|resources.3.kind=shared|resources.3.type=atomic<uint>[GROUP_SIZE]|resources.3.addressSpace=shared|workgroupSizes.0.entryPoint=compute_main|workgroupSizes.0.x=4|workgroupSizes.0.y=1|workgroupSizes.0.z=1|workgroupSizes.0.sourceX=GROUP_SIZE|workgroupSizes.0.sourceY=1|workgroupSizes.0.sourceZ=1"
    "-DEXPECTED_REFLECTION_JSON_ARRAY_LENGTHS=resources=4|targetResourceBindings=4|functionConstants=1|workgroupSizes=1"
    "-DEXPECTED_REFLECTION_TARGET_FIELDS=counters.sourceType=atomic<int>*|counters.bindingClass=storage-buffer|counters.argumentIndex=0|unsignedCounters.sourceType=atomic<uint>*|unsignedCounters.bindingClass=storage-buffer|unsignedCounters.argumentIndex=1|tile.sourceType=atomic<int>[GROUP_SIZE]|tile.addressSpace=shared|tile.abi=workgroupLocal|tile.bindingClass=shared|tile.arraySize=GROUP_SIZE|tile.arrayElementCount=4|unsignedTile.sourceType=atomic<uint>[GROUP_SIZE]|unsignedTile.addressSpace=shared|unsignedTile.abi=workgroupLocal|unsignedTile.bindingClass=shared|unsignedTile.arraySize=GROUP_SIZE|unsignedTile.arrayElementCount=4"
    "-DEXPECTED_REFLECTION_FEATURE_FIELDS=${CROSSGL_OPENGL_ATOMIC_ADD_FEATURE_FIELDS}"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_build_opengl_atomic_add_return_source_package
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CMAKE_CURRENT_SOURCE_DIR}/tests/opengl/fixtures/OpenGLAtomicAddReturnShader.cgl
    -DTARGET=opengl
    -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-opengl-atomic-add-return-source.cglb
    -DMODE=source-package-build
    -DEXPECTED_SOURCE=backend/opengl/OpenGLAtomicAddReturnShader.comp.glsl
    "-DEXPECTED_SOURCE_SNIPPET=${CROSSGL_OPENGL_ATOMIC_ADD_RETURN_SOURCE_SNIPPET}"
    "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=opengl|module=OpenGLAtomicAddReturnShader|functionConstants.0.name=GROUP_SIZE|functionConstants.0.value=4|resources.0.name=counters|resources.0.kind=buffer|resources.0.type=atomic<int>*|resources.0.binding=0|resources.1.name=unsignedCounters|resources.1.kind=buffer|resources.1.type=atomic<uint>*|resources.1.binding=1|resources.2.name=compatCounters|resources.2.kind=buffer|resources.2.type=CompatCounters*|resources.2.binding=2|resources.3.name=values|resources.3.kind=buffer|resources.3.type=int*|resources.3.binding=3|resources.4.name=unsignedValues|resources.4.kind=buffer|resources.4.type=uint*|resources.4.binding=4|resources.5.name=tile|resources.5.kind=shared|resources.5.type=atomic<int>[GROUP_SIZE]|resources.5.addressSpace=shared|resources.6.name=unsignedTile|resources.6.kind=shared|resources.6.type=atomic<uint>[GROUP_SIZE]|resources.6.addressSpace=shared|workgroupSizes.0.entryPoint=compute_main|workgroupSizes.0.x=4|workgroupSizes.0.y=1|workgroupSizes.0.z=1|workgroupSizes.0.sourceX=GROUP_SIZE|workgroupSizes.0.sourceY=1|workgroupSizes.0.sourceZ=1"
    "-DEXPECTED_REFLECTION_JSON_ARRAY_LENGTHS=resources=7|targetResourceBindings=7|functionConstants=1|workgroupSizes=1"
    "-DEXPECTED_REFLECTION_TARGET_FIELDS=counters.sourceType=atomic<int>*|counters.bindingClass=storage-buffer|counters.argumentIndex=0|unsignedCounters.sourceType=atomic<uint>*|unsignedCounters.bindingClass=storage-buffer|unsignedCounters.argumentIndex=1|compatCounters.sourceType=CompatCounters*|compatCounters.bindingClass=storage-buffer|compatCounters.argumentIndex=2|values.sourceType=int*|values.bindingClass=storage-buffer|values.argumentIndex=3|unsignedValues.sourceType=uint*|unsignedValues.bindingClass=storage-buffer|unsignedValues.argumentIndex=4|tile.sourceType=atomic<int>[GROUP_SIZE]|tile.addressSpace=shared|tile.abi=workgroupLocal|tile.bindingClass=shared|tile.arraySize=GROUP_SIZE|tile.arrayElementCount=4|unsignedTile.sourceType=atomic<uint>[GROUP_SIZE]|unsignedTile.addressSpace=shared|unsignedTile.abi=workgroupLocal|unsignedTile.bindingClass=shared|unsignedTile.arraySize=GROUP_SIZE|unsignedTile.arrayElementCount=4"
    "-DEXPECTED_REFLECTION_FEATURE_FIELDS=${CROSSGL_OPENGL_ATOMIC_ADD_RETURN_FEATURE_FIELDS}"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_build_opengl_atomic_minmax_return_source_package
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CMAKE_CURRENT_SOURCE_DIR}/tests/opengl/fixtures/OpenGLAtomicMinMaxReturnShader.cgl
    -DTARGET=opengl
    -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-opengl-atomic-minmax-return-source.cglb
    -DMODE=source-package-build
    -DEXPECTED_SOURCE=backend/opengl/OpenGLAtomicMinMaxReturnShader.comp.glsl
    "-DEXPECTED_SOURCE_SNIPPET=${CROSSGL_OPENGL_ATOMIC_MINMAX_RETURN_SOURCE_SNIPPET}"
    "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=opengl|module=OpenGLAtomicMinMaxReturnShader|functionConstants.0.name=GROUP_SIZE|functionConstants.0.value=4|resources.0.name=counters|resources.0.kind=buffer|resources.0.type=atomic<int>*|resources.0.binding=0|resources.1.name=unsignedCounters|resources.1.kind=buffer|resources.1.type=atomic<uint>*|resources.1.binding=1|resources.2.name=compatCounters|resources.2.kind=buffer|resources.2.type=CompatCounters*|resources.2.binding=2|resources.3.name=values|resources.3.kind=buffer|resources.3.type=int*|resources.3.binding=3|resources.4.name=unsignedValues|resources.4.kind=buffer|resources.4.type=uint*|resources.4.binding=4|resources.5.name=tile|resources.5.kind=shared|resources.5.type=atomic<int>[GROUP_SIZE]|resources.5.addressSpace=shared|resources.6.name=unsignedTile|resources.6.kind=shared|resources.6.type=atomic<uint>[GROUP_SIZE]|resources.6.addressSpace=shared|workgroupSizes.0.entryPoint=compute_main|workgroupSizes.0.x=4|workgroupSizes.0.y=1|workgroupSizes.0.z=1|workgroupSizes.0.sourceX=GROUP_SIZE|workgroupSizes.0.sourceY=1|workgroupSizes.0.sourceZ=1"
    "-DEXPECTED_REFLECTION_JSON_ARRAY_LENGTHS=resources=7|targetResourceBindings=7|functionConstants=1|workgroupSizes=1"
    "-DEXPECTED_REFLECTION_TARGET_FIELDS=counters.sourceType=atomic<int>*|counters.bindingClass=storage-buffer|counters.argumentIndex=0|unsignedCounters.sourceType=atomic<uint>*|unsignedCounters.bindingClass=storage-buffer|unsignedCounters.argumentIndex=1|compatCounters.sourceType=CompatCounters*|compatCounters.bindingClass=storage-buffer|compatCounters.argumentIndex=2|values.sourceType=int*|values.bindingClass=storage-buffer|values.argumentIndex=3|unsignedValues.sourceType=uint*|unsignedValues.bindingClass=storage-buffer|unsignedValues.argumentIndex=4|tile.sourceType=atomic<int>[GROUP_SIZE]|tile.addressSpace=shared|tile.abi=workgroupLocal|tile.bindingClass=shared|tile.arraySize=GROUP_SIZE|tile.arrayElementCount=4|unsignedTile.sourceType=atomic<uint>[GROUP_SIZE]|unsignedTile.addressSpace=shared|unsignedTile.abi=workgroupLocal|unsignedTile.bindingClass=shared|unsignedTile.arraySize=GROUP_SIZE|unsignedTile.arrayElementCount=4"
    "-DEXPECTED_REFLECTION_FEATURE_FIELDS=${CROSSGL_OPENGL_ATOMIC_MINMAX_RETURN_FEATURE_FIELDS}"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_build_opengl_atomic_exchange_return_source_package
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CMAKE_CURRENT_SOURCE_DIR}/tests/opengl/fixtures/OpenGLAtomicExchangeReturnShader.cgl
    -DTARGET=opengl
    -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-opengl-atomic-exchange-return-source.cglb
    -DMODE=source-package-build
    -DEXPECTED_SOURCE=backend/opengl/OpenGLAtomicExchangeReturnShader.comp.glsl
    "-DEXPECTED_SOURCE_SNIPPET=${CROSSGL_OPENGL_ATOMIC_EXCHANGE_RETURN_SOURCE_SNIPPET}"
    "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=opengl|module=OpenGLAtomicExchangeReturnShader|functionConstants.0.name=GROUP_SIZE|functionConstants.0.value=4|resources.0.name=counters|resources.0.kind=buffer|resources.0.type=atomic<int>*|resources.0.binding=0|resources.1.name=unsignedCounters|resources.1.kind=buffer|resources.1.type=atomic<uint>*|resources.1.binding=1|resources.2.name=compatCounters|resources.2.kind=buffer|resources.2.type=CompatCounters*|resources.2.binding=2|resources.3.name=values|resources.3.kind=buffer|resources.3.type=int*|resources.3.binding=3|resources.4.name=unsignedValues|resources.4.kind=buffer|resources.4.type=uint*|resources.4.binding=4|resources.5.name=tile|resources.5.kind=shared|resources.5.type=atomic<int>[GROUP_SIZE]|resources.5.addressSpace=shared|resources.6.name=unsignedTile|resources.6.kind=shared|resources.6.type=atomic<uint>[GROUP_SIZE]|resources.6.addressSpace=shared|workgroupSizes.0.entryPoint=compute_main|workgroupSizes.0.x=4|workgroupSizes.0.y=1|workgroupSizes.0.z=1|workgroupSizes.0.sourceX=GROUP_SIZE|workgroupSizes.0.sourceY=1|workgroupSizes.0.sourceZ=1"
    "-DEXPECTED_REFLECTION_JSON_ARRAY_LENGTHS=resources=7|targetResourceBindings=7|functionConstants=1|workgroupSizes=1"
    "-DEXPECTED_REFLECTION_TARGET_FIELDS=counters.sourceType=atomic<int>*|counters.bindingClass=storage-buffer|counters.argumentIndex=0|unsignedCounters.sourceType=atomic<uint>*|unsignedCounters.bindingClass=storage-buffer|unsignedCounters.argumentIndex=1|compatCounters.sourceType=CompatCounters*|compatCounters.bindingClass=storage-buffer|compatCounters.argumentIndex=2|values.sourceType=int*|values.bindingClass=storage-buffer|values.argumentIndex=3|unsignedValues.sourceType=uint*|unsignedValues.bindingClass=storage-buffer|unsignedValues.argumentIndex=4|tile.sourceType=atomic<int>[GROUP_SIZE]|tile.addressSpace=shared|tile.abi=workgroupLocal|tile.bindingClass=shared|tile.arraySize=GROUP_SIZE|tile.arrayElementCount=4|unsignedTile.sourceType=atomic<uint>[GROUP_SIZE]|unsignedTile.addressSpace=shared|unsignedTile.abi=workgroupLocal|unsignedTile.bindingClass=shared|unsignedTile.arraySize=GROUP_SIZE|unsignedTile.arrayElementCount=4"
    "-DEXPECTED_REFLECTION_FEATURE_FIELDS=${CROSSGL_OPENGL_ATOMIC_EXCHANGE_RETURN_FEATURE_FIELDS}"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_build_opengl_atomic_bitwise_return_source_package
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CMAKE_CURRENT_SOURCE_DIR}/tests/opengl/fixtures/OpenGLAtomicBitwiseReturnShader.cgl
    -DTARGET=opengl
    -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-opengl-atomic-bitwise-return-source.cglb
    -DMODE=source-package-build
    -DEXPECTED_SOURCE=backend/opengl/OpenGLAtomicBitwiseReturnShader.comp.glsl
    "-DEXPECTED_SOURCE_SNIPPET=${CROSSGL_OPENGL_ATOMIC_BITWISE_RETURN_SOURCE_SNIPPET}"
    "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=opengl|module=OpenGLAtomicBitwiseReturnShader|functionConstants.0.name=GROUP_SIZE|functionConstants.0.value=4|resources.0.name=counters|resources.0.kind=buffer|resources.0.type=atomic<int>*|resources.0.binding=0|resources.1.name=unsignedCounters|resources.1.kind=buffer|resources.1.type=atomic<uint>*|resources.1.binding=1|resources.2.name=compatCounters|resources.2.kind=buffer|resources.2.type=CompatCounters*|resources.2.binding=2|resources.3.name=values|resources.3.kind=buffer|resources.3.type=int*|resources.3.binding=3|resources.4.name=unsignedValues|resources.4.kind=buffer|resources.4.type=uint*|resources.4.binding=4|resources.5.name=tile|resources.5.kind=shared|resources.5.type=atomic<int>[GROUP_SIZE]|resources.5.addressSpace=shared|resources.6.name=unsignedTile|resources.6.kind=shared|resources.6.type=atomic<uint>[GROUP_SIZE]|resources.6.addressSpace=shared|workgroupSizes.0.entryPoint=compute_main|workgroupSizes.0.x=4|workgroupSizes.0.y=1|workgroupSizes.0.z=1|workgroupSizes.0.sourceX=GROUP_SIZE|workgroupSizes.0.sourceY=1|workgroupSizes.0.sourceZ=1"
    "-DEXPECTED_REFLECTION_JSON_ARRAY_LENGTHS=resources=7|targetResourceBindings=7|functionConstants=1|workgroupSizes=1"
    "-DEXPECTED_REFLECTION_TARGET_FIELDS=counters.sourceType=atomic<int>*|counters.bindingClass=storage-buffer|counters.argumentIndex=0|unsignedCounters.sourceType=atomic<uint>*|unsignedCounters.bindingClass=storage-buffer|unsignedCounters.argumentIndex=1|compatCounters.sourceType=CompatCounters*|compatCounters.bindingClass=storage-buffer|compatCounters.argumentIndex=2|values.sourceType=int*|values.bindingClass=storage-buffer|values.argumentIndex=3|unsignedValues.sourceType=uint*|unsignedValues.bindingClass=storage-buffer|unsignedValues.argumentIndex=4|tile.sourceType=atomic<int>[GROUP_SIZE]|tile.addressSpace=shared|tile.abi=workgroupLocal|tile.bindingClass=shared|tile.arraySize=GROUP_SIZE|tile.arrayElementCount=4|unsignedTile.sourceType=atomic<uint>[GROUP_SIZE]|unsignedTile.addressSpace=shared|unsignedTile.abi=workgroupLocal|unsignedTile.bindingClass=shared|unsignedTile.arraySize=GROUP_SIZE|unsignedTile.arrayElementCount=4"
    "-DEXPECTED_REFLECTION_FEATURE_FIELDS=${CROSSGL_OPENGL_ATOMIC_BITWISE_RETURN_FEATURE_FIELDS}"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
set(CROSSGL_DIRECTX_FUNCTION_PARAMETER_ARRAY_SOURCE_SNIPPET [=[void storeFirstWeight(float weights[WEIGHT_COUNT]) {
  float firstWeight = weights[0];
  particles[1].mass = firstWeight;
  return;
}

void storeForwardedWeight(float forwardedWeights[WEIGHT_COUNT]) {
  storeFirstWeight(forwardedWeights);
  return;
}]=])
add_test(NAME cglc_build_directx_function_parameter_array_source_package
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_DIRECTX_FUNCTION_PARAMETER_ARRAY_SHADER}
    -DTARGET=directx
    -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-directx-function-parameter-array-source.cglb
    -DMODE=source-package-build
    -DEXPECTED_SOURCE=backend/directx/DirectXFunctionParameterArrayShader.hlsl
    "-DEXPECTED_SOURCE_SNIPPET=${CROSSGL_DIRECTX_FUNCTION_PARAMETER_ARRAY_SOURCE_SNIPPET}"
    "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=directx|module=DirectXFunctionParameterArrayShader|nativeBinary=backend/directx/DirectXFunctionParameterArrayShader.dxil|functionConstants.0.name=WEIGHT_COUNT|functionConstants.0.value=4|resources.0.name=particles|resources.0.kind=buffer|resources.0.type=Particle*|resources.0.binding=0|workgroupSizes.0.entryPoint=compute_main|workgroupSizes.0.x=1|workgroupSizes.0.y=1|workgroupSizes.0.z=1"
    "-DEXPECTED_REFLECTION_JSON_ARRAY_LENGTHS=resources=1|targetResourceBindings=1|workgroupSizes=1"
    "-DEXPECTED_REFLECTION_TARGET_FIELDS=particles.stage=compute|particles.entryPoint=compute_main|particles.sourceType=Particle*|particles.hlslType=RWStructuredBuffer<Particle>|particles.addressSpace=unordered-access|particles.abi=registerBinding|particles.bindingClass=uav|particles.descriptorType=UAV|particles.argumentIndex=0|particles.set=0|particles.binding=0"
    "-DEXPECTED_REFLECTION_FEATURE_FIELDS=hlsl-lowering.kind=backend|fixed-array.kind=layout|fixed-array-field.kind=layout|compute-kernel.kind=stage|workgroup-size.kind=execution|storage-buffer.kind=resource|local-declaration.kind=operation|index-access.kind=operation|storage-buffer-write.kind=operation"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_build_directx_void_parameter_list_source_package
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_VOID_PARAMETER_LIST_SHADER}
    -DTARGET=directx
    -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-directx-void-parameter-list-source.cglb
    -DMODE=source-package-build
    -DEXPECTED_SOURCE=backend/directx/VoidParameterListShader.hlsl
    "-DEXPECTED_SOURCE_SNIPPET=float helper()"
    "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=directx|module=VoidParameterListShader|nativeBinary=backend/directx/VoidParameterListShader.dxil|workgroupSizes.0.entryPoint=compute_main|workgroupSizes.0.x=1|workgroupSizes.0.y=1|workgroupSizes.0.z=1"
    "-DEXPECTED_REFLECTION_JSON_ARRAY_LENGTHS=resources=0|targetResourceBindings=0|workgroupSizes=1"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
set(CROSSGL_DIRECTX_MATRIX_FUNCTION_PARAMETER_ARRAY_SOURCE_SNIPPET [=[void touchTransform(float2x2 transforms[COUNT]) {
  return;
}

[numthreads(1, 1, 1)]
void compute_main(uint3 crossgl_GlobalInvocationID : SV_DispatchThreadID) {
  float2x2 localTransforms[COUNT];]=])
add_test(NAME cglc_build_directx_matrix_function_parameter_array_source_package
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_DIRECTX_MATRIX_FUNCTION_PARAMETER_ARRAY_SHADER}
    -DTARGET=directx
    -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-directx-matrix-function-parameter-array-source.cglb
    -DMODE=source-package-build
    -DEXPECTED_SOURCE=backend/directx/DirectXMatrixFunctionParameterArrayShader.hlsl
    "-DEXPECTED_SOURCE_SNIPPET=${CROSSGL_DIRECTX_MATRIX_FUNCTION_PARAMETER_ARRAY_SOURCE_SNIPPET}"
    "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=directx|module=DirectXMatrixFunctionParameterArrayShader|nativeBinary=backend/directx/DirectXMatrixFunctionParameterArrayShader.dxil|functionConstants.0.name=COUNT|functionConstants.0.value=2|workgroupSizes.0.entryPoint=compute_main|workgroupSizes.0.x=1|workgroupSizes.0.y=1|workgroupSizes.0.z=1"
    "-DEXPECTED_REFLECTION_JSON_ARRAY_LENGTHS=resources=0|targetResourceBindings=0|workgroupSizes=1"
    "-DEXPECTED_REFLECTION_FEATURE_FIELDS=hlsl-lowering.kind=backend|compute-kernel.kind=stage|workgroup-size.kind=execution|local-declaration.kind=operation|index-access.kind=operation"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
set(CROSSGL_DIRECTX_FOLDED_NESTED_FUNCTION_PARAMETER_ARRAY_SOURCE_SNIPPET [=[void storeGrid(float grid[ROWS][COLS]) {
  float nestedTotal = grid[0][1] + grid[1][2];
  particles[2].mass = nestedTotal;
  return;
}]=])
add_test(NAME cglc_build_directx_folded_nested_function_parameter_array_source_package
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_DIRECTX_FOLDED_NESTED_FUNCTION_PARAMETER_ARRAY_SHADER}
    -DTARGET=directx
    -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-directx-folded-nested-function-parameter-array-source.cglb
    -DMODE=source-package-build
    -DEXPECTED_SOURCE=backend/directx/DirectXFoldedNestedFunctionParameterArrayShader.hlsl
    "-DEXPECTED_SOURCE_SNIPPET=${CROSSGL_DIRECTX_FOLDED_NESTED_FUNCTION_PARAMETER_ARRAY_SOURCE_SNIPPET}"
    "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=directx|module=DirectXFoldedNestedFunctionParameterArrayShader|nativeBinary=backend/directx/DirectXFoldedNestedFunctionParameterArrayShader.dxil|functionConstants.0.name=ROWS|functionConstants.0.value=2|functionConstants.1.name=COLS|functionConstants.1.value=3|resources.0.name=particles|resources.0.kind=buffer|resources.0.type=Particle*|resources.0.binding=0|workgroupSizes.0.entryPoint=compute_main|workgroupSizes.0.x=1|workgroupSizes.0.y=1|workgroupSizes.0.z=1"
    "-DEXPECTED_REFLECTION_JSON_ARRAY_LENGTHS=resources=1|targetResourceBindings=1|workgroupSizes=1"
    "-DEXPECTED_REFLECTION_TARGET_FIELDS=particles.stage=compute|particles.entryPoint=compute_main|particles.sourceType=Particle*|particles.hlslType=RWStructuredBuffer<Particle>|particles.addressSpace=unordered-access|particles.abi=registerBinding|particles.bindingClass=uav|particles.descriptorType=UAV|particles.argumentIndex=0|particles.set=0|particles.binding=0"
    "-DEXPECTED_REFLECTION_FEATURE_FIELDS=hlsl-lowering.kind=backend|fixed-array.kind=layout|fixed-array-field.kind=layout|compute-kernel.kind=stage|workgroup-size.kind=execution|storage-buffer.kind=resource|scalar-arithmetic.kind=operation|index-access.kind=operation|local-declaration.kind=operation|storage-buffer-read.kind=operation|storage-buffer-write.kind=operation"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
set(CROSSGL_DIRECTX_NESTED_LOCAL_FUNCTION_PARAMETER_ARRAY_SOURCE_SNIPPET [=[float readGrid(float grid[ROWS][COLS]) {
  return grid[1][2];
}]=])
add_test(NAME cglc_build_directx_nested_local_function_parameter_array_source_package
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_DIRECTX_NESTED_LOCAL_FUNCTION_PARAMETER_ARRAY_SHADER}
    -DTARGET=directx
    -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-directx-nested-local-function-parameter-array-source.cglb
    -DMODE=source-package-build
    -DEXPECTED_SOURCE=backend/directx/DirectXNestedLocalFunctionParameterArrayShader.hlsl
    "-DEXPECTED_SOURCE_SNIPPET=${CROSSGL_DIRECTX_NESTED_LOCAL_FUNCTION_PARAMETER_ARRAY_SOURCE_SNIPPET}"
    "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=directx|module=DirectXNestedLocalFunctionParameterArrayShader|nativeBinary=backend/directx/DirectXNestedLocalFunctionParameterArrayShader.dxil|functionConstants.0.name=ROWS|functionConstants.0.value=2|functionConstants.1.name=COLS|functionConstants.1.value=3|resources.0.name=values|resources.0.kind=buffer|resources.0.type=float*|resources.0.binding=0|workgroupSizes.0.entryPoint=compute_main|workgroupSizes.0.x=1|workgroupSizes.0.y=1|workgroupSizes.0.z=1"
    "-DEXPECTED_REFLECTION_JSON_ARRAY_LENGTHS=resources=1|targetResourceBindings=1|workgroupSizes=1"
    "-DEXPECTED_REFLECTION_TARGET_FIELDS=values.stage=compute|values.entryPoint=compute_main|values.sourceType=float*|values.hlslType=RWStructuredBuffer<float>|values.addressSpace=unordered-access|values.abi=registerBinding|values.bindingClass=uav|values.descriptorType=UAV|values.argumentIndex=0|values.set=0|values.binding=0"
    "-DEXPECTED_REFLECTION_FEATURE_FIELDS=hlsl-lowering.kind=backend|compute-kernel.kind=stage|workgroup-size.kind=execution|storage-buffer.kind=resource|index-access.kind=operation|local-declaration.kind=operation|storage-buffer-read.kind=operation|storage-buffer-write.kind=operation"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
set(CROSSGL_DIRECTX_DYNAMIC_NESTED_FUNCTION_PARAMETER_ARRAY_READ_SOURCE_SNIPPET [=[float readGrid(float grid[ROWS][COLS], int row, int col) {
  return grid[row][col];
}]=])
add_test(NAME cglc_build_directx_dynamic_nested_function_parameter_array_read_source_package
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_DIRECTX_DYNAMIC_NESTED_FUNCTION_PARAMETER_ARRAY_READ_UNSUPPORTED_SHADER}
    -DTARGET=directx
    -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-directx-dynamic-nested-function-parameter-array-read-source.cglb
    -DMODE=source-package-build
    -DEXPECTED_SOURCE=backend/directx/DirectXDynamicNestedFunctionParameterArrayReadUnsupportedShader.hlsl
    "-DEXPECTED_SOURCE_SNIPPET=${CROSSGL_DIRECTX_DYNAMIC_NESTED_FUNCTION_PARAMETER_ARRAY_READ_SOURCE_SNIPPET}"
    "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=directx|module=DirectXDynamicNestedFunctionParameterArrayReadUnsupportedShader|nativeBinary=backend/directx/DirectXDynamicNestedFunctionParameterArrayReadUnsupportedShader.dxil|functionConstants.0.name=ROWS|functionConstants.0.value=2|functionConstants.1.name=COLS|functionConstants.1.value=3|resources.0.name=values|resources.0.kind=buffer|resources.0.type=float*|resources.0.binding=0|workgroupSizes.0.entryPoint=compute_main|workgroupSizes.0.x=1|workgroupSizes.0.y=1|workgroupSizes.0.z=1"
    "-DEXPECTED_REFLECTION_JSON_ARRAY_LENGTHS=resources=1|targetResourceBindings=1|workgroupSizes=1"
    "-DEXPECTED_REFLECTION_TARGET_FIELDS=values.stage=compute|values.entryPoint=compute_main|values.sourceType=float*|values.hlslType=RWStructuredBuffer<float>|values.addressSpace=unordered-access|values.abi=registerBinding|values.bindingClass=uav|values.descriptorType=UAV|values.argumentIndex=0|values.set=0|values.binding=0"
    "-DEXPECTED_REFLECTION_FEATURE_FIELDS=hlsl-lowering.kind=backend|compute-kernel.kind=stage|workgroup-size.kind=execution|storage-buffer.kind=resource|index-access.kind=operation|local-declaration.kind=operation|storage-buffer-read.kind=operation|scalar-constructor.kind=operation|storage-buffer-write.kind=operation"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
set(CROSSGL_DIRECTX_NESTED_FUNCTION_PARAMETER_ARRAY_WRITE_SOURCE_SNIPPET [=[float rewriteGrid(float grid[ROWS][COLS]) {
  grid[1][2] = 1.0;
  return grid[1][2];
}]=])
add_test(NAME cglc_build_directx_nested_function_parameter_array_write_source_package
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_DIRECTX_NESTED_FUNCTION_PARAMETER_ARRAY_WRITE_UNSUPPORTED_SHADER}
    -DTARGET=directx
    -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-directx-nested-function-parameter-array-write-source.cglb
    -DMODE=source-package-build
    -DEXPECTED_SOURCE=backend/directx/DirectXNestedFunctionParameterArrayWriteUnsupportedShader.hlsl
    "-DEXPECTED_SOURCE_SNIPPET=${CROSSGL_DIRECTX_NESTED_FUNCTION_PARAMETER_ARRAY_WRITE_SOURCE_SNIPPET}"
    "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=directx|module=DirectXNestedFunctionParameterArrayWriteUnsupportedShader|nativeBinary=backend/directx/DirectXNestedFunctionParameterArrayWriteUnsupportedShader.dxil|functionConstants.0.name=ROWS|functionConstants.0.value=2|functionConstants.1.name=COLS|functionConstants.1.value=3|resources.0.name=values|resources.0.kind=buffer|resources.0.type=float*|resources.0.binding=0|workgroupSizes.0.entryPoint=compute_main|workgroupSizes.0.x=1|workgroupSizes.0.y=1|workgroupSizes.0.z=1"
    "-DEXPECTED_REFLECTION_JSON_ARRAY_LENGTHS=resources=1|targetResourceBindings=1|workgroupSizes=1"
    "-DEXPECTED_REFLECTION_TARGET_FIELDS=values.stage=compute|values.entryPoint=compute_main|values.sourceType=float*|values.hlslType=RWStructuredBuffer<float>|values.addressSpace=unordered-access|values.abi=registerBinding|values.bindingClass=uav|values.descriptorType=UAV|values.argumentIndex=0|values.set=0|values.binding=0"
    "-DEXPECTED_REFLECTION_FEATURE_FIELDS=hlsl-lowering.kind=backend|compute-kernel.kind=stage|workgroup-size.kind=execution|storage-buffer.kind=resource|index-access.kind=operation|local-declaration.kind=operation|storage-buffer-read.kind=operation|storage-buffer-write.kind=operation"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
set(CROSSGL_OPENGL_PARAM_ARRAY_RESOURCE_FEATURE_FIELDS
    "glsl-lowering.kind=backend|compute-kernel.kind=stage|workgroup-size.kind=execution|fixed-array.kind=layout|fixed-array-field.kind=layout|storage-buffer.kind=resource|local-declaration.kind=operation|index-access.kind=operation|storage-buffer-write.kind=operation")
set(CROSSGL_OPENGL_PARAM_ARRAY_LOCAL_FEATURE_FIELDS
    "glsl-lowering.kind=backend|compute-kernel.kind=stage|workgroup-size.kind=execution|index-access.kind=operation|local-declaration.kind=operation|scalar-arithmetic.kind=operation")
set(CROSSGL_OPENGL_PARAM_ARRAY_DYNAMIC_FEATURE_FIELDS
    "glsl-lowering.kind=backend|compute-kernel.kind=stage|workgroup-size.kind=execution|storage-buffer.kind=resource|index-access.kind=operation|local-declaration.kind=operation|storage-buffer-read.kind=operation|scalar-constructor.kind=operation|storage-buffer-write.kind=operation")
set(CROSSGL_OPENGL_PARAM_ARRAY_WRITE_RESOURCE_FEATURE_FIELDS
    "glsl-lowering.kind=backend|compute-kernel.kind=stage|workgroup-size.kind=execution|fixed-array.kind=layout|fixed-array-field.kind=layout|storage-buffer.kind=resource|function-parameter-array.kind=array|scalar-vector-elements.kind=array|local-declaration.kind=operation|index-access.kind=operation|storage-buffer-read.kind=operation|storage-buffer-write.kind=operation")
set(CROSSGL_OPENGL_PARAM_ARRAY_WRITE_LOCAL_FEATURE_FIELDS
    "glsl-lowering.kind=backend|compute-kernel.kind=stage|workgroup-size.kind=execution|fixed-array.kind=layout|function-parameter-array.kind=array|scalar-vector-elements.kind=array|local-array.kind=array|index-access.kind=operation|scalar-arithmetic.kind=operation|local-declaration.kind=operation|storage-buffer-read.kind=operation|storage-buffer-write.kind=operation")
set(CROSSGL_OPENGL_PARAM_ARRAY_VALIDATED_RESOURCE_FEATURE_FIELDS
    "native-glsl-package.kind=backend|glsl-program-validation.kind=validation|fixed-array.kind=layout|fixed-array-field.kind=layout|storage-buffer.kind=resource|local-declaration.kind=operation|index-access.kind=operation|storage-buffer-write.kind=operation")
set(CROSSGL_OPENGL_PARAM_ARRAY_VALIDATED_LOCAL_FEATURE_FIELDS
    "native-glsl-package.kind=backend|glsl-program-validation.kind=validation|index-access.kind=operation|local-declaration.kind=operation|scalar-arithmetic.kind=operation")
set(CROSSGL_OPENGL_PARAM_ARRAY_VALIDATED_DYNAMIC_FEATURE_FIELDS
    "native-glsl-package.kind=backend|glsl-program-validation.kind=validation|storage-buffer.kind=resource|index-access.kind=operation|local-declaration.kind=operation|storage-buffer-read.kind=operation|scalar-constructor.kind=operation|storage-buffer-write.kind=operation")
set(CROSSGL_OPENGL_PARAM_ARRAY_VALIDATED_WRITE_RESOURCE_FEATURE_FIELDS
    "native-glsl-package.kind=backend|glsl-program-validation.kind=validation|fixed-array.kind=layout|fixed-array-field.kind=layout|storage-buffer.kind=resource|function-parameter-array.kind=array|scalar-vector-elements.kind=array|local-declaration.kind=operation|index-access.kind=operation|storage-buffer-read.kind=operation|storage-buffer-write.kind=operation")
set(CROSSGL_OPENGL_PARAM_ARRAY_VALIDATED_WRITE_LOCAL_FEATURE_FIELDS
    "native-glsl-package.kind=backend|glsl-program-validation.kind=validation|fixed-array.kind=layout|function-parameter-array.kind=array|scalar-vector-elements.kind=array|local-array.kind=array|index-access.kind=operation|scalar-arithmetic.kind=operation|local-declaration.kind=operation|storage-buffer-read.kind=operation|storage-buffer-write.kind=operation")
add_test(NAME cglc_build_opengl_function_parameter_array_source_package
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_OPENGL_FUNCTION_PARAMETER_ARRAY_SHADER}
    -DTARGET=opengl
    -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-opengl-function-parameter-array-source.cglb
    -DMODE=source-package-build
    -DEXPECTED_SOURCE=backend/opengl/OpenGLFunctionParameterArrayShader.comp.glsl
    "-DEXPECTED_SOURCE_SNIPPET=void relayVelocity(vec3 velocities[COUNT])"
    "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=opengl|module=OpenGLFunctionParameterArrayShader"
    "-DEXPECTED_REFLECTION_TARGET_FIELDS=particles.sourceType=Particle*|particles.bindingClass=storage-buffer|particles.argumentIndex=0|particles.storageBufferLayout.elementType=Particle|particles.storageBufferLayout.arrayStrideBytes=48|particles.storageBufferLayout.layout=std430|particles.storageBufferLayout.fields.0.name=weights|particles.storageBufferLayout.fields.0.arrayElementCount=2|particles.storageBufferLayout.fields.1.name=velocities|particles.storageBufferLayout.fields.1.arrayStrideBytes=16"
    "-DEXPECTED_REFLECTION_FEATURE_FIELDS=${CROSSGL_OPENGL_PARAM_ARRAY_RESOURCE_FEATURE_FIELDS}"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_build_directx_atan_intrinsic_source_package
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_ATAN_INTRINSIC_COMPUTE_SHADER}
    -DTARGET=directx
    -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-directx-atan-intrinsic-source.cglb
    -DMODE=source-package-build
    -DEXPECTED_SOURCE=backend/directx/AtanIntrinsicComputeShader.hlsl
    "-DEXPECTED_SOURCE_SNIPPET=float angle = atan2(scalars[0], scalars[1]);"
    "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=directx|module=AtanIntrinsicComputeShader"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
set(CROSSGL_DIRECTX_INTRINSIC_SOURCE_SNIPPET [=[float frac = frac(upper);
  float scalarLength = length(frac);
  float vectorLength = length(vectors[0]);
  float alignment = dot(vectors[0], vectors[1]);
  float4 direction = normalize(vectors[0]);
  float4 reflected = reflect(direction, normalize(vectors[1]));
  float4 mixed = lerp(direction, reflected, 0.25);
  scalars[2] = scalarLength + vectorLength + alignment;
  vectors[2] = mixed;]=])
add_test(NAME cglc_build_directx_intrinsics_source_package
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_INTRINSIC_COMPUTE_SHADER}
    -DTARGET=directx
    -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-directx-intrinsic-source.cglb
    -DMODE=source-package-build
    -DEXPECTED_SOURCE=backend/directx/IntrinsicComputeShader.hlsl
    "-DEXPECTED_SOURCE_SNIPPET=${CROSSGL_DIRECTX_INTRINSIC_SOURCE_SNIPPET}"
    "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=directx|module=IntrinsicComputeShader|nativeBinary=backend/directx/IntrinsicComputeShader.dxil"
    "-DEXPECTED_REFLECTION_TARGET_FIELDS=scalars.sourceType=float*|scalars.hlslType=RWStructuredBuffer<float>|scalars.bindingClass=uav|scalars.descriptorType=UAV|vectors.sourceType=vec4*|vectors.hlslType=RWStructuredBuffer<float4>|vectors.bindingClass=uav|vectors.descriptorType=UAV"
    "-DEXPECTED_REFLECTION_FEATURE_FIELDS=storage-buffer-write.kind=operation"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
set(CROSSGL_DIRECTX_VECTOR_SWIZZLE_SOURCE_SNIPPET [=[float3 rgb = color.rgb;
  float2 rg = color.xy;
  float4 rgba = color.rgba;
  values[0] = rgb.z;
  values[1] = rg.y;
  values[2] = rgba.b;]=])
add_test(NAME cglc_build_directx_vector_swizzle_source_package
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_VECTOR_SWIZZLE_COMPUTE_SHADER}
    -DTARGET=directx
    -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-directx-vector-swizzle-source.cglb
    -DMODE=source-package-build
    -DEXPECTED_SOURCE=backend/directx/VectorSwizzleComputeShader.hlsl
    "-DEXPECTED_SOURCE_SNIPPET=${CROSSGL_DIRECTX_VECTOR_SWIZZLE_SOURCE_SNIPPET}"
    "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=directx|module=VectorSwizzleComputeShader|nativeBinary=backend/directx/VectorSwizzleComputeShader.dxil"
    "-DEXPECTED_REFLECTION_TARGET_FIELDS=values.sourceType=float*|values.hlslType=RWStructuredBuffer<float>|values.bindingClass=uav|values.descriptorType=UAV"
    "-DEXPECTED_REFLECTION_FEATURE_FIELDS=hlsl-lowering.kind=backend|compute-kernel.kind=stage|workgroup-size.kind=execution|storage-buffer.kind=resource|local-declaration.kind=operation|storage-buffer-read.kind=operation|vector-constructor.kind=operation|index-access.kind=operation|storage-buffer-write.kind=operation"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
set(CROSSGL_DIRECTX_ARITHMETIC_SOURCE_SNIPPET "[numthreads(2, 1, 1)]")
add_test(NAME cglc_build_directx_arithmetic_source_package
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_ARITHMETIC_COMPUTE_SHADER}
    -DTARGET=directx
    -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-directx-arithmetic-source.cglb
    -DMODE=source-package-build
    -DEXPECTED_SOURCE=backend/directx/ArithmeticComputeShader.hlsl
    "-DEXPECTED_SOURCE_SNIPPET=${CROSSGL_DIRECTX_ARITHMETIC_SOURCE_SNIPPET}"
    "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=directx|module=ArithmeticComputeShader|nativeBinary=backend/directx/ArithmeticComputeShader.dxil|workgroupSizes.0.entryPoint=compute_main|workgroupSizes.0.x=2"
    "-DEXPECTED_REFLECTION_JSON_ARRAY_LENGTHS=resources=0|targetResourceBindings=0"
    "-DEXPECTED_REFLECTION_FEATURE_FIELDS=hlsl-lowering.kind=backend|compute-kernel.kind=stage|workgroup-size.kind=execution"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_build_directx_comparison_source_package
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_COMPARISON_COMPUTE_SHADER}
    -DTARGET=directx
    -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-directx-comparison-source.cglb
    -DMODE=source-package-build
    -DEXPECTED_SOURCE=backend/directx/ComparisonComputeShader.hlsl
    "-DEXPECTED_SOURCE_SNIPPET=RWStructuredBuffer<float> values : register(u0, space0);"
    "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=directx|module=ComparisonComputeShader|nativeBinary=backend/directx/ComparisonComputeShader.dxil"
    "-DEXPECTED_REFLECTION_JSON_ARRAY_LENGTHS=resources=1|targetResourceBindings=1"
    "-DEXPECTED_REFLECTION_TARGET_FIELDS=values.sourceType=float*|values.hlslType=RWStructuredBuffer<float>|values.bindingClass=uav|values.descriptorType=UAV|values.argumentIndex=0"
    "-DEXPECTED_REFLECTION_FEATURE_FIELDS=storage-buffer.kind=resource|compute-kernel.kind=stage"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
set(CROSSGL_DIRECTX_FLOAT_EQUALITY_NEGATION_SOURCE_SNIPPET [=[bool equalityNegationFloat = (dynamicFloat != 31.0);
  bool inequalityNegationFloat = (dynamicFloat == 32.0);]=])
add_test(NAME cglc_build_directx_float_equality_negation_source_package
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_FLOAT_EQUALITY_NEGATION_BACKEND_SHADER}
    -DTARGET=directx
    -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-directx-float-equality-negation-source.cglb
    -DMODE=source-package-build
    -DEXPECTED_SOURCE=backend/directx/FloatEqualityNegationBackendShader.hlsl
    "-DEXPECTED_SOURCE_SNIPPET=${CROSSGL_DIRECTX_FLOAT_EQUALITY_NEGATION_SOURCE_SNIPPET}"
    "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=directx|module=FloatEqualityNegationBackendShader|nativeBinary=backend/directx/FloatEqualityNegationBackendShader.dxil|workgroupSizes.0.entryPoint=compute_main"
    "-DEXPECTED_REFLECTION_JSON_ARRAY_LENGTHS=resources=1|targetResourceBindings=1"
    "-DEXPECTED_REFLECTION_TARGET_FIELDS=values.sourceType=int*|values.hlslType=RWStructuredBuffer<int>|values.bindingClass=uav|values.descriptorType=UAV|values.argumentIndex=0"
    "-DEXPECTED_REFLECTION_FEATURE_FIELDS=hlsl-lowering.kind=backend|compute-kernel.kind=stage|storage-buffer.kind=resource|scalar-comparison.kind=operation"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
set(CROSSGL_DIRECTX_BOOLEAN_DE_MORGAN_SOURCE_SNIPPET [=[bool deMorganAnd = (!base || dynamicIndex <= 17);
  bool deMorganOr = (!base && dynamicIndex <= 18);
  bool deMorganComparisonAnd = (dynamicIndex >= 19 || dynamicIndex <= 20);
  bool deMorganComparisonOr = (dynamicIndex >= 21 && dynamicIndex <= 22);]=])
add_test(NAME cglc_build_directx_boolean_de_morgan_source_package
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_BOOLEAN_DE_MORGAN_BACKEND_SHADER}
    -DTARGET=directx
    -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-directx-boolean-de-morgan-source.cglb
    -DMODE=source-package-build
    -DEXPECTED_SOURCE=backend/directx/BooleanDeMorganBackendShader.hlsl
    "-DEXPECTED_SOURCE_SNIPPET=${CROSSGL_DIRECTX_BOOLEAN_DE_MORGAN_SOURCE_SNIPPET}"
    "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=directx|module=BooleanDeMorganBackendShader|nativeBinary=backend/directx/BooleanDeMorganBackendShader.dxil|workgroupSizes.0.entryPoint=compute_main"
    "-DEXPECTED_REFLECTION_JSON_ARRAY_LENGTHS=resources=1|targetResourceBindings=1"
    "-DEXPECTED_REFLECTION_TARGET_FIELDS=values.sourceType=int*|values.hlslType=RWStructuredBuffer<int>|values.bindingClass=uav|values.descriptorType=UAV|values.argumentIndex=0"
    "-DEXPECTED_REFLECTION_FEATURE_FIELDS=hlsl-lowering.kind=backend|compute-kernel.kind=stage|storage-buffer.kind=resource|scalar-comparison.kind=operation"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
set(CROSSGL_DIRECTX_SELECT_EXPRESSION_SOURCE_SNIPPET [=[int selectedInt = (base ? dynamicIndex + 1 : dynamicIndex + 2);
  bool selectedBool = (base ? dynamicIndex > 3 : dynamicIndex > 4);
  values[1] = selectedInt;
  values[2] = (selectedBool ? 1 : 0);]=])
add_test(NAME cglc_build_directx_select_expression_source_package
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_SELECT_EXPRESSION_BACKEND_SHADER}
    -DTARGET=directx
    -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-directx-select-expression-source.cglb
    -DMODE=source-package-build
    -DEXPECTED_SOURCE=backend/directx/SelectExpressionBackendShader.hlsl
    "-DEXPECTED_SOURCE_SNIPPET=${CROSSGL_DIRECTX_SELECT_EXPRESSION_SOURCE_SNIPPET}"
    "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=directx|module=SelectExpressionBackendShader|nativeBinary=backend/directx/SelectExpressionBackendShader.dxil|workgroupSizes.0.entryPoint=compute_main"
    "-DEXPECTED_REFLECTION_JSON_ARRAY_LENGTHS=resources=1|targetResourceBindings=1"
    "-DEXPECTED_REFLECTION_TARGET_FIELDS=values.sourceType=int*|values.hlslType=RWStructuredBuffer<int>|values.bindingClass=uav|values.descriptorType=UAV|values.argumentIndex=0"
    "-DEXPECTED_REFLECTION_FEATURE_FIELDS=hlsl-lowering.kind=backend|compute-kernel.kind=stage|storage-buffer.kind=resource|scalar-comparison.kind=operation|select-expression.kind=operation"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
set(CROSSGL_DIRECTX_LOAD_LOCAL_SOURCE_SNIPPET [=[float x = values[0];
  values[1] = x + 1.0;]=])
add_test(NAME cglc_build_directx_load_local_source_package
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_LOAD_LOCAL_COMPUTE_SHADER}
    -DTARGET=directx
    -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-directx-load-local-source.cglb
    -DMODE=source-package-build
    -DEXPECTED_SOURCE=backend/directx/LoadLocalComputeShader.hlsl
    "-DEXPECTED_SOURCE_SNIPPET=${CROSSGL_DIRECTX_LOAD_LOCAL_SOURCE_SNIPPET}"
    "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=directx|module=LoadLocalComputeShader|nativeBinary=backend/directx/LoadLocalComputeShader.dxil"
    "-DEXPECTED_REFLECTION_JSON_ARRAY_LENGTHS=resources=1|targetResourceBindings=1"
    "-DEXPECTED_REFLECTION_TARGET_FIELDS=values.sourceType=float*|values.hlslType=RWStructuredBuffer<float>|values.bindingClass=uav|values.descriptorType=UAV|values.argumentIndex=0"
    "-DEXPECTED_REFLECTION_FEATURE_FIELDS=local-declaration.kind=operation|storage-buffer-read.kind=operation|index-access.kind=operation|storage-buffer-write.kind=operation|scalar-arithmetic.kind=operation"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
set(CROSSGL_DIRECTX_SCALAR_CONSTRUCTOR_SOURCE_SNIPPET [=[int signedValue = int(source);
  uint unsignedValue = uint(source);
  float signedBack = float(signedValue);
  float unsignedBack = float(unsignedValue);
  values[1] = signedBack + unsignedBack;]=])
add_test(NAME cglc_build_directx_scalar_constructor_source_package
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_SCALAR_CONSTRUCTOR_COMPUTE_SHADER}
    -DTARGET=directx
    -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-directx-scalar-constructor-source.cglb
    -DMODE=source-package-build
    -DEXPECTED_SOURCE=backend/directx/ScalarConstructorComputeShader.hlsl
    "-DEXPECTED_SOURCE_SNIPPET=${CROSSGL_DIRECTX_SCALAR_CONSTRUCTOR_SOURCE_SNIPPET}"
    "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=directx|module=ScalarConstructorComputeShader|nativeBinary=backend/directx/ScalarConstructorComputeShader.dxil"
    "-DEXPECTED_REFLECTION_JSON_ARRAY_LENGTHS=resources=1|targetResourceBindings=1"
    "-DEXPECTED_REFLECTION_TARGET_FIELDS=values.sourceType=float*|values.hlslType=RWStructuredBuffer<float>|values.bindingClass=uav|values.descriptorType=UAV|values.argumentIndex=0"
    "-DEXPECTED_REFLECTION_FEATURE_FIELDS=local-declaration.kind=operation|storage-buffer-read.kind=operation|index-access.kind=operation|scalar-constructor.kind=operation|storage-buffer-write.kind=operation|scalar-arithmetic.kind=operation"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
set(CROSSGL_DIRECTX_MATRIX_CONSTRUCTOR_SOURCE_SNIPPET [=[float2x2 flattened = float2x2(1.0, 3.0, 2.0, 4.0);
  float2x2 diagonal = float2x2(5.0, 0.0, 0.0, 5.0);
  float3x3 expanded = float3x3(flattened[0][0], flattened[0][1], 0.0, flattened[1][0], flattened[1][1], 0.0, 0.0, 0.0, 1.0);
  float3 c0 = float3(1.0, 2.0, 3.0);
  float3 c1 = float3(4.0, 5.0, 6.0);
  float3 c2 = float3(7.0, 8.0, 9.0);
  float3x3 basis = float3x3(c0[0], c1[0], c2[0], c0[1], c1[1], c2[1], c0[2], c1[2], c2[2]);]=])
add_test(NAME cglc_build_directx_matrix_constructor_source_package
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_MATRIX_CONSTRUCTOR_COMPUTE_SHADER}
    -DTARGET=directx
    -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-directx-matrix-constructor-source.cglb
    -DMODE=source-package-build
    -DEXPECTED_SOURCE=backend/directx/MatrixConstructorComputeShader.hlsl
    "-DEXPECTED_SOURCE_SNIPPET=${CROSSGL_DIRECTX_MATRIX_CONSTRUCTOR_SOURCE_SNIPPET}"
    "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=directx|module=MatrixConstructorComputeShader|nativeBinary=backend/directx/MatrixConstructorComputeShader.dxil|resources.0.name=values|resources.0.kind=buffer|resources.0.type=float*|workgroupSizes.0.entryPoint=compute_main|workgroupSizes.0.x=1|workgroupSizes.0.y=1|workgroupSizes.0.z=1"
    "-DEXPECTED_REFLECTION_JSON_ARRAY_LENGTHS=resources=1|targetResourceBindings=1|workgroupSizes=1"
    "-DEXPECTED_REFLECTION_TARGET_FIELDS=values.sourceType=float*|values.hlslType=RWStructuredBuffer<float>|values.bindingClass=uav|values.descriptorType=UAV|values.argumentIndex=0|values.set=0|values.binding=0"
    "-DEXPECTED_REFLECTION_FEATURE_FIELDS=hlsl-lowering.kind=backend|compute-kernel.kind=stage|workgroup-size.kind=execution|storage-buffer.kind=resource|storage-buffer-write.kind=operation|index-access.kind=operation|local-declaration.kind=operation|vector-constructor.kind=operation|matrix-constructor.kind=operation"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
set(CROSSGL_DIRECTX_MATRIX_STORAGE_BUFFER_SOURCE_SNIPPET [=[float4x4 transform = transforms[0];
  transforms[1] = transform;
  values[0] = 1.0;]=])
add_test(NAME cglc_build_directx_matrix_storage_buffer_source_package
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_DIRECTX_MATRIX_STORAGE_BUFFER_SHADER}
    -DTARGET=directx
    -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-directx-matrix-storage-buffer-source.cglb
    -DMODE=source-package-build
    -DEXPECTED_SOURCE=backend/directx/DirectXMatrixStorageBufferShader.hlsl
    "-DEXPECTED_SOURCE_SNIPPET=${CROSSGL_DIRECTX_MATRIX_STORAGE_BUFFER_SOURCE_SNIPPET}"
    "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=directx|module=DirectXMatrixStorageBufferShader|nativeBinary=backend/directx/DirectXMatrixStorageBufferShader.dxil|resources.0.name=transforms|resources.0.kind=buffer|resources.0.type=mat4*|resources.1.name=values|resources.1.kind=buffer|resources.1.type=float*|workgroupSizes.0.entryPoint=compute_main|workgroupSizes.0.x=1|workgroupSizes.0.y=1|workgroupSizes.0.z=1"
    "-DEXPECTED_REFLECTION_JSON_ARRAY_LENGTHS=resources=2|targetResourceBindings=2|workgroupSizes=1"
    "-DEXPECTED_REFLECTION_TARGET_FIELDS=transforms.sourceType=mat4*|transforms.hlslType=RWStructuredBuffer<float4x4>|transforms.bindingClass=uav|transforms.descriptorType=UAV|transforms.argumentIndex=0|transforms.set=0|transforms.binding=0|values.sourceType=float*|values.hlslType=RWStructuredBuffer<float>|values.bindingClass=uav|values.descriptorType=UAV|values.argumentIndex=1|values.set=0|values.binding=1"
    "-DEXPECTED_REFLECTION_FEATURE_FIELDS=hlsl-lowering.kind=backend|compute-kernel.kind=stage|workgroup-size.kind=execution|storage-buffer.kind=resource|storage-buffer-read.kind=operation|storage-buffer-write.kind=operation|index-access.kind=operation|local-declaration.kind=operation"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
set(CROSSGL_OPENGL_MATRIX_STORAGE_BUFFER_SOURCE_SNIPPET [=[mat4 transform = transforms[0];
  transforms[1] = transform;
  values[0] = 1.0;]=])
add_test(NAME cglc_build_opengl_matrix_storage_buffer_source_package
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_OPENGL_MATRIX_STORAGE_BUFFER_SHADER}
    -DTARGET=opengl
    -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-opengl-matrix-storage-buffer-source.cglb
    -DMODE=source-package-build
    -DEXPECTED_SOURCE=backend/opengl/OpenGLMatrixStorageBufferShader.comp.glsl
    "-DEXPECTED_SOURCE_SNIPPET=${CROSSGL_OPENGL_MATRIX_STORAGE_BUFFER_SOURCE_SNIPPET}"
    "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=opengl|module=OpenGLMatrixStorageBufferShader|nativeBinary=backend/opengl/OpenGLMatrixStorageBufferShader.glsl|resources.0.name=transforms|resources.0.kind=buffer|resources.0.type=mat4*|resources.1.name=values|resources.1.kind=buffer|resources.1.type=float*|workgroupSizes.0.entryPoint=compute_main|workgroupSizes.0.x=1|workgroupSizes.0.y=1|workgroupSizes.0.z=1"
    "-DEXPECTED_REFLECTION_JSON_ARRAY_LENGTHS=resources=2|targetResourceBindings=2|workgroupSizes=1"
    "-DEXPECTED_REFLECTION_TARGET_FIELDS=transforms.sourceType=mat4*|transforms.bindingClass=storage-buffer|transforms.argumentIndex=0|transforms.set=0|transforms.binding=0|transforms.storageBufferLayout.elementType=mat4|transforms.storageBufferLayout.elementSizeBytes=64|transforms.storageBufferLayout.arrayStrideBytes=64|transforms.storageBufferLayout.alignmentBytes=16|transforms.storageBufferLayout.layout=std430|values.sourceType=float*|values.bindingClass=storage-buffer|values.argumentIndex=1|values.set=0|values.binding=1|values.storageBufferLayout.elementType=float|values.storageBufferLayout.arrayStrideBytes=4|values.storageBufferLayout.layout=std430"
    "-DEXPECTED_REFLECTION_FEATURE_FIELDS=glsl-lowering.kind=backend|compute-kernel.kind=stage|workgroup-size.kind=execution|storage-buffer.kind=resource|storage-buffer-read.kind=operation|storage-buffer-write.kind=operation|index-access.kind=operation|local-declaration.kind=operation"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
set(CROSSGL_DIRECTX_MATRIX_VECTOR_ARITHMETIC_SOURCE_SNIPPET [=[float3 columnProduct = mul(transform, source);
  float3 rowProduct = mul(source, transform);
  float3x3 composed = mul(transform, basis);
  float3 projected = mul(composed, rowProduct);]=])
add_test(NAME cglc_build_directx_matrix_vector_arithmetic_source_package
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_MATRIX_VECTOR_ARITHMETIC_COMPUTE_SHADER}
    -DTARGET=directx
    -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-directx-matrix-vector-arithmetic-source.cglb
    -DMODE=source-package-build
    -DEXPECTED_SOURCE=backend/directx/MatrixVectorArithmeticComputeShader.hlsl
    "-DEXPECTED_SOURCE_SNIPPET=${CROSSGL_DIRECTX_MATRIX_VECTOR_ARITHMETIC_SOURCE_SNIPPET}"
    "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=directx|module=MatrixVectorArithmeticComputeShader|nativeBinary=backend/directx/MatrixVectorArithmeticComputeShader.dxil|resources.0.name=values|resources.0.kind=buffer|resources.0.type=float*|workgroupSizes.0.entryPoint=compute_main|workgroupSizes.0.x=1|workgroupSizes.0.y=1|workgroupSizes.0.z=1"
    "-DEXPECTED_REFLECTION_JSON_ARRAY_LENGTHS=resources=1|targetResourceBindings=1|workgroupSizes=1"
    "-DEXPECTED_REFLECTION_TARGET_FIELDS=values.sourceType=float*|values.hlslType=RWStructuredBuffer<float>|values.bindingClass=uav|values.descriptorType=UAV|values.argumentIndex=0|values.set=0|values.binding=0"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
set(CROSSGL_DIRECTX_MATRIX_SCALAR_ARITHMETIC_SOURCE_SNIPPET [=[float3x3 scaled = transform * 2.0;
  float3x3 rescaled = 0.5 * transform;
  float3x3 inferred = transform * 0.25;
  inferred = inferred * 4.0;]=])
add_test(NAME cglc_build_directx_matrix_scalar_arithmetic_source_package
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_MATRIX_SCALAR_ARITHMETIC_COMPUTE_SHADER}
    -DTARGET=directx
    -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-directx-matrix-scalar-arithmetic-source.cglb
    -DMODE=source-package-build
    -DEXPECTED_SOURCE=backend/directx/MatrixScalarArithmeticComputeShader.hlsl
    "-DEXPECTED_SOURCE_SNIPPET=${CROSSGL_DIRECTX_MATRIX_SCALAR_ARITHMETIC_SOURCE_SNIPPET}"
    "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=directx|module=MatrixScalarArithmeticComputeShader|nativeBinary=backend/directx/MatrixScalarArithmeticComputeShader.dxil|resources.0.name=values|resources.0.kind=buffer|resources.0.type=float*|workgroupSizes.0.entryPoint=compute_main|workgroupSizes.0.x=1|workgroupSizes.0.y=1|workgroupSizes.0.z=1"
    "-DEXPECTED_REFLECTION_JSON_ARRAY_LENGTHS=resources=1|targetResourceBindings=1|workgroupSizes=1"
    "-DEXPECTED_REFLECTION_TARGET_FIELDS=values.sourceType=float*|values.hlslType=RWStructuredBuffer<float>|values.bindingClass=uav|values.descriptorType=UAV|values.argumentIndex=0|values.set=0|values.binding=0"
    "-DEXPECTED_REFLECTION_FEATURE_FIELDS=hlsl-lowering.kind=backend|compute-kernel.kind=stage|workgroup-size.kind=execution|storage-buffer.kind=resource|storage-buffer-write.kind=operation|index-access.kind=operation|local-declaration.kind=operation|matrix-constructor.kind=operation|scalar-arithmetic.kind=operation"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
set(CROSSGL_DIRECTX_VECTOR_LOCAL_SOURCE_SNIPPET [=[float4 color = float4(values[0], values[1], values[2], 1.0);
  float4 lifted = color + float4(0.5, 0.5, 0.5, 0.0);
  values[0] = lifted.x;]=])
add_test(NAME cglc_build_directx_vector_local_source_package
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_VECTOR_LOCAL_COMPUTE_SHADER}
    -DTARGET=directx
    -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-directx-vector-local-source.cglb
    -DMODE=source-package-build
    -DEXPECTED_SOURCE=backend/directx/VectorLocalComputeShader.hlsl
    "-DEXPECTED_SOURCE_SNIPPET=${CROSSGL_DIRECTX_VECTOR_LOCAL_SOURCE_SNIPPET}"
    "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=directx|module=VectorLocalComputeShader|nativeBinary=backend/directx/VectorLocalComputeShader.dxil"
    "-DEXPECTED_REFLECTION_JSON_ARRAY_LENGTHS=resources=1|targetResourceBindings=1"
    "-DEXPECTED_REFLECTION_TARGET_FIELDS=values.sourceType=float*|values.hlslType=RWStructuredBuffer<float>|values.bindingClass=uav|values.descriptorType=UAV|values.argumentIndex=0"
    "-DEXPECTED_REFLECTION_FEATURE_FIELDS=local-declaration.kind=operation|storage-buffer-read.kind=operation|vector-constructor.kind=operation|index-access.kind=operation|vector-arithmetic.kind=operation|storage-buffer-write.kind=operation"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
set(CROSSGL_DIRECTX_VECTOR_SCALAR_SOURCE_SNIPPET [=[float4 color = values[0];
  float4 scaled = color * 0.5;
  float4 biased = 0.25 + scaled;
  float4 inverted = 1.0 - biased;
  float4 normalized = inverted / 2.0;
  values[1] = normalized;]=])
add_test(NAME cglc_build_directx_vector_scalar_source_package
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_VECTOR_SCALAR_COMPUTE_SHADER}
    -DTARGET=directx
    -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-directx-vector-scalar-source.cglb
    -DMODE=source-package-build
    -DEXPECTED_SOURCE=backend/directx/VectorScalarComputeShader.hlsl
    "-DEXPECTED_SOURCE_SNIPPET=${CROSSGL_DIRECTX_VECTOR_SCALAR_SOURCE_SNIPPET}"
    "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=directx|module=VectorScalarComputeShader|nativeBinary=backend/directx/VectorScalarComputeShader.dxil"
    "-DEXPECTED_REFLECTION_JSON_ARRAY_LENGTHS=resources=1|targetResourceBindings=1"
    "-DEXPECTED_REFLECTION_TARGET_FIELDS=values.sourceType=vec4*|values.hlslType=RWStructuredBuffer<float4>|values.bindingClass=uav|values.descriptorType=UAV|values.argumentIndex=0"
    "-DEXPECTED_REFLECTION_FEATURE_FIELDS=hlsl-lowering.kind=backend|storage-buffer.kind=resource|vector-storage-buffer.kind=layout|local-declaration.kind=operation|storage-buffer-read.kind=operation|index-access.kind=operation|vector-arithmetic.kind=operation|storage-buffer-write.kind=operation"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
set(CROSSGL_DIRECTX_VECTOR_SCALAR_CAST_SOURCE_SNIPPET [=[static const int OFFSET = 1;

RWStructuredBuffer<float4> values : register(u0, space0);

[numthreads(1, 1, 1)]
void compute_main(uint3 crossgl_GlobalInvocationID : SV_DispatchThreadID) {
  float4 color = values[0];
  float4 scaled = color * float(2);
  float4 biased = float(1) + scaled;
  values[1] = biased;]=])
add_test(NAME cglc_build_directx_vector_scalar_cast_source_package
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_VECTOR_SCALAR_CAST_COMPUTE_SHADER}
    -DTARGET=directx
    -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-directx-vector-scalar-cast-source.cglb
    -DMODE=source-package-build
    -DEXPECTED_SOURCE=backend/directx/VectorScalarCastComputeShader.hlsl
    "-DEXPECTED_SOURCE_SNIPPET=${CROSSGL_DIRECTX_VECTOR_SCALAR_CAST_SOURCE_SNIPPET}"
    "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=directx|module=VectorScalarCastComputeShader|nativeBinary=backend/directx/VectorScalarCastComputeShader.dxil"
    "-DEXPECTED_REFLECTION_JSON_ARRAY_LENGTHS=resources=1|targetResourceBindings=1"
    "-DEXPECTED_REFLECTION_TARGET_FIELDS=values.sourceType=vec4*|values.hlslType=RWStructuredBuffer<float4>|values.bindingClass=uav|values.descriptorType=UAV|values.argumentIndex=0"
    "-DEXPECTED_REFLECTION_FEATURE_FIELDS=hlsl-lowering.kind=backend|storage-buffer.kind=resource|vector-storage-buffer.kind=layout|local-declaration.kind=operation|storage-buffer-read.kind=operation|index-access.kind=operation|vector-arithmetic.kind=operation|scalar-constructor.kind=operation|storage-buffer-write.kind=operation"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
set(CROSSGL_DIRECTX_VECTOR_BUFFER_SOURCE_SNIPPET [=[RWStructuredBuffer<float4> values : register(u0, space0);

[numthreads(1, 1, 1)]
void compute_main(uint3 crossgl_GlobalInvocationID : SV_DispatchThreadID) {
  float4 color = values[0];
  float4 lifted = color + float4(0.5, 0.5, 0.5, 0.0);
  values[1] = lifted;]=])
add_test(NAME cglc_build_directx_vector_buffer_source_package
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_VECTOR_BUFFER_COMPUTE_SHADER}
    -DTARGET=directx
    -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-directx-vector-buffer-source.cglb
    -DMODE=source-package-build
    -DEXPECTED_SOURCE=backend/directx/VectorBufferComputeShader.hlsl
    "-DEXPECTED_SOURCE_SNIPPET=${CROSSGL_DIRECTX_VECTOR_BUFFER_SOURCE_SNIPPET}"
    "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=directx|module=VectorBufferComputeShader|nativeBinary=backend/directx/VectorBufferComputeShader.dxil"
    "-DEXPECTED_REFLECTION_JSON_ARRAY_LENGTHS=resources=1|targetResourceBindings=1"
    "-DEXPECTED_REFLECTION_TARGET_FIELDS=values.sourceType=vec4*|values.hlslType=RWStructuredBuffer<float4>|values.bindingClass=uav|values.descriptorType=UAV|values.argumentIndex=0"
    "-DEXPECTED_REFLECTION_FEATURE_FIELDS=vector-storage-buffer.kind=layout|local-declaration.kind=operation|storage-buffer-read.kind=operation|index-access.kind=operation|vector-arithmetic.kind=operation|vector-constructor.kind=operation|storage-buffer-write.kind=operation"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
set(CROSSGL_DIRECTX_VECTOR3_BUFFER_SOURCE_SNIPPET [=[RWStructuredBuffer<float3> values : register(u0, space0);

[numthreads(1, 1, 1)]
void compute_main(uint3 crossgl_GlobalInvocationID : SV_DispatchThreadID) {
  float3 color = values[0];
  float3 lifted = color + float3(0.5, 0.5, 0.0);
  values[1] = lifted;]=])
add_test(NAME cglc_build_directx_vector3_buffer_source_package
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_VECTOR3_BUFFER_COMPUTE_SHADER}
    -DTARGET=directx
    -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-directx-vector3-buffer-source.cglb
    -DMODE=source-package-build
    -DEXPECTED_SOURCE=backend/directx/Vector3BufferComputeShader.hlsl
    "-DEXPECTED_SOURCE_SNIPPET=${CROSSGL_DIRECTX_VECTOR3_BUFFER_SOURCE_SNIPPET}"
    "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=directx|module=Vector3BufferComputeShader|nativeBinary=backend/directx/Vector3BufferComputeShader.dxil"
    "-DEXPECTED_REFLECTION_JSON_ARRAY_LENGTHS=resources=1|targetResourceBindings=1"
    "-DEXPECTED_REFLECTION_TARGET_FIELDS=values.sourceType=vec3*|values.hlslType=RWStructuredBuffer<float3>|values.bindingClass=uav|values.descriptorType=UAV|values.argumentIndex=0"
    "-DEXPECTED_REFLECTION_FEATURE_FIELDS=vector-storage-buffer.kind=layout|local-declaration.kind=operation|storage-buffer-read.kind=operation|index-access.kind=operation|vector-arithmetic.kind=operation|vector-constructor.kind=operation|storage-buffer-write.kind=operation"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_build_opengl_atan_intrinsic_source_package
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_ATAN_INTRINSIC_COMPUTE_SHADER}
    -DTARGET=opengl
    -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-opengl-atan-intrinsic-source.cglb
    -DMODE=source-package-build
    -DEXPECTED_SOURCE=backend/opengl/AtanIntrinsicComputeShader.comp.glsl
    "-DEXPECTED_SOURCE_SNIPPET=float angle = atan(scalars[0], scalars[1]);"
    "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=opengl|module=AtanIntrinsicComputeShader"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
set(CROSSGL_OPENGL_INTRINSIC_SOURCE_SNIPPET [=[layout(binding = 0, std430) buffer scalars_Buffer {
  float scalars[];
};

// CrossGL set 0, binding 1
layout(binding = 1, std430) buffer vectors_Buffer {
  vec4 vectors[];
};

void main() {
  float scalarAbs = abs(scalars[0]);
  float sine = sin(scalarAbs);
  float root = sqrt(sine + 1.0);
  float curved = pow(root, scalars[1]);
  float lower = min(curved, 1.0);
  float upper = max(lower, 0.0);
  float frac = fract(upper);
  float scalarLength = length(frac);
  float vectorLength = length(vectors[0]);
  float alignment = dot(vectors[0], vectors[1]);
  vec4 direction = normalize(vectors[0]);
  vec4 reflected = reflect(direction, normalize(vectors[1]));
  vec4 mixed = mix(direction, reflected, 0.25);
  scalars[2] = scalarLength + vectorLength + alignment;
  vectors[2] = mixed;]=])
add_test(NAME cglc_build_opengl_intrinsics_source_package
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_INTRINSIC_COMPUTE_SHADER}
    -DTARGET=opengl
    -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-opengl-intrinsics-source.cglb
    -DMODE=source-package-build
    -DEXPECTED_SOURCE=backend/opengl/IntrinsicComputeShader.comp.glsl
    "-DEXPECTED_SOURCE_SNIPPET=${CROSSGL_OPENGL_INTRINSIC_SOURCE_SNIPPET}"
    "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=opengl|module=IntrinsicComputeShader"
    "-DEXPECTED_REFLECTION_TARGET_FIELDS=scalars.sourceType=float*|scalars.bindingClass=storage-buffer|scalars.argumentIndex=0|scalars.storageBufferLayout.layout=std430|vectors.sourceType=vec4*|vectors.bindingClass=storage-buffer|vectors.argumentIndex=1|vectors.storageBufferLayout.layout=std430|vectors.storageBufferLayout.elementType=vec4"
    "-DEXPECTED_REFLECTION_FEATURE_FIELDS=storage-buffer-write.kind=operation"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
set(CROSSGL_OPENGL_VECTOR_SWIZZLE_SOURCE_SNIPPET [=[layout(binding = 0, std430) buffer values_Buffer {
  float values[];
};

void main() {
  vec4 color = vec4(values[0], values[1], values[2], values[3]);
  vec3 rgb = color.rgb;
  vec2 rg = color.xy;
  vec4 rgba = color.rgba;
  values[0] = rgb.z;
  values[1] = rg.y;
  values[2] = rgba.b;]=])
add_test(NAME cglc_build_opengl_vector_swizzle_source_package
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_VECTOR_SWIZZLE_COMPUTE_SHADER}
    -DTARGET=opengl
    -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-opengl-vector-swizzle-source.cglb
    -DMODE=source-package-build
    -DEXPECTED_SOURCE=backend/opengl/VectorSwizzleComputeShader.comp.glsl
    "-DEXPECTED_SOURCE_SNIPPET=${CROSSGL_OPENGL_VECTOR_SWIZZLE_SOURCE_SNIPPET}"
    "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=opengl|module=VectorSwizzleComputeShader"
    "-DEXPECTED_REFLECTION_TARGET_FIELDS=values.sourceType=float*|values.bindingClass=storage-buffer|values.argumentIndex=0|values.storageBufferLayout.layout=std430|values.storageBufferLayout.elementType=float"
    "-DEXPECTED_REFLECTION_FEATURE_FIELDS=glsl-lowering.kind=backend|compute-kernel.kind=stage|workgroup-size.kind=execution|storage-buffer.kind=resource|local-declaration.kind=operation|storage-buffer-read.kind=operation|vector-constructor.kind=operation|index-access.kind=operation|storage-buffer-write.kind=operation"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
set(CROSSGL_OPENGL_ARITHMETIC_SOURCE_SNIPPET [=[layout(local_size_x = 2, local_size_y = 1, local_size_z = 1) in;

void main() {
  return;
}]=])
add_test(NAME cglc_build_opengl_arithmetic_source_package
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_ARITHMETIC_COMPUTE_SHADER}
    -DTARGET=opengl
    -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-opengl-arithmetic-source.cglb
    -DMODE=source-package-build
    -DEXPECTED_SOURCE=backend/opengl/ArithmeticComputeShader.comp.glsl
    "-DEXPECTED_SOURCE_SNIPPET=${CROSSGL_OPENGL_ARITHMETIC_SOURCE_SNIPPET}"
    "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=opengl|module=ArithmeticComputeShader"
    "-DEXPECTED_REFLECTION_FEATURE_FIELDS=glsl-lowering.kind=backend|compute-kernel.kind=stage|workgroup-size.kind=execution"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
set(CROSSGL_OPENGL_COMPARISON_SOURCE_SNIPPET [=[layout(binding = 0, std430) buffer values_Buffer {
  float values[];
};

void main() {
  return;
}]=])
add_test(NAME cglc_build_opengl_comparison_source_package
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_COMPARISON_COMPUTE_SHADER}
    -DTARGET=opengl
    -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-opengl-comparison-source.cglb
    -DMODE=source-package-build
    -DEXPECTED_SOURCE=backend/opengl/ComparisonComputeShader.comp.glsl
    "-DEXPECTED_SOURCE_SNIPPET=${CROSSGL_OPENGL_COMPARISON_SOURCE_SNIPPET}"
    "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=opengl|module=ComparisonComputeShader"
    "-DEXPECTED_REFLECTION_TARGET_FIELDS=values.sourceType=float*|values.bindingClass=storage-buffer|values.argumentIndex=0|values.storageBufferLayout.layout=std430|values.storageBufferLayout.elementType=float"
    "-DEXPECTED_REFLECTION_FEATURE_FIELDS=storage-buffer.kind=resource"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
set(CROSSGL_OPENGL_FLOAT_EQUALITY_NEGATION_SOURCE_SNIPPET [=[bool equalityNegationFloat = (dynamicFloat != 31.0);
  bool inequalityNegationFloat = (dynamicFloat == 32.0);]=])
add_test(NAME cglc_build_opengl_float_equality_negation_source_package
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_FLOAT_EQUALITY_NEGATION_BACKEND_SHADER}
    -DTARGET=opengl
    -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-opengl-float-equality-negation-source.cglb
    -DMODE=source-package-build
    -DEXPECTED_SOURCE=backend/opengl/FloatEqualityNegationBackendShader.comp.glsl
    "-DEXPECTED_SOURCE_SNIPPET=${CROSSGL_OPENGL_FLOAT_EQUALITY_NEGATION_SOURCE_SNIPPET}"
    "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=opengl|module=FloatEqualityNegationBackendShader|workgroupSizes.0.entryPoint=compute_main"
    "-DEXPECTED_REFLECTION_JSON_ARRAY_LENGTHS=resources=1|targetResourceBindings=1"
    "-DEXPECTED_REFLECTION_TARGET_FIELDS=values.sourceType=int*|values.bindingClass=storage-buffer|values.argumentIndex=0|values.storageBufferLayout.layout=std430|values.storageBufferLayout.elementType=int"
    "-DEXPECTED_REFLECTION_FEATURE_FIELDS=glsl-lowering.kind=backend|compute-kernel.kind=stage|storage-buffer.kind=resource|scalar-comparison.kind=operation"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
set(CROSSGL_OPENGL_BOOLEAN_DE_MORGAN_SOURCE_SNIPPET [=[bool deMorganAnd = (!base || dynamicIndex <= 17);
  bool deMorganOr = (!base && dynamicIndex <= 18);
  bool deMorganComparisonAnd = (dynamicIndex >= 19 || dynamicIndex <= 20);
  bool deMorganComparisonOr = (dynamicIndex >= 21 && dynamicIndex <= 22);]=])
add_test(NAME cglc_build_opengl_boolean_de_morgan_source_package
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_BOOLEAN_DE_MORGAN_BACKEND_SHADER}
    -DTARGET=opengl
    -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-opengl-boolean-de-morgan-source.cglb
    -DMODE=source-package-build
    -DEXPECTED_SOURCE=backend/opengl/BooleanDeMorganBackendShader.comp.glsl
    "-DEXPECTED_SOURCE_SNIPPET=${CROSSGL_OPENGL_BOOLEAN_DE_MORGAN_SOURCE_SNIPPET}"
    "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=opengl|module=BooleanDeMorganBackendShader|workgroupSizes.0.entryPoint=compute_main"
    "-DEXPECTED_REFLECTION_JSON_ARRAY_LENGTHS=resources=1|targetResourceBindings=1"
    "-DEXPECTED_REFLECTION_TARGET_FIELDS=values.sourceType=int*|values.bindingClass=storage-buffer|values.argumentIndex=0|values.storageBufferLayout.layout=std430|values.storageBufferLayout.elementType=int"
    "-DEXPECTED_REFLECTION_FEATURE_FIELDS=glsl-lowering.kind=backend|compute-kernel.kind=stage|storage-buffer.kind=resource|scalar-comparison.kind=operation"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
set(CROSSGL_OPENGL_SELECT_EXPRESSION_SOURCE_SNIPPET [=[int selectedInt = (base ? dynamicIndex + 1 : dynamicIndex + 2);
  bool selectedBool = (base ? dynamicIndex > 3 : dynamicIndex > 4);
  values[1] = selectedInt;
  values[2] = (selectedBool ? 1 : 0);]=])
add_test(NAME cglc_build_opengl_select_expression_source_package
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_SELECT_EXPRESSION_BACKEND_SHADER}
    -DTARGET=opengl
    -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-opengl-select-expression-source.cglb
    -DMODE=source-package-build
    -DEXPECTED_SOURCE=backend/opengl/SelectExpressionBackendShader.comp.glsl
    "-DEXPECTED_SOURCE_SNIPPET=${CROSSGL_OPENGL_SELECT_EXPRESSION_SOURCE_SNIPPET}"
    "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=opengl|module=SelectExpressionBackendShader|workgroupSizes.0.entryPoint=compute_main"
    "-DEXPECTED_REFLECTION_JSON_ARRAY_LENGTHS=resources=1|targetResourceBindings=1"
    "-DEXPECTED_REFLECTION_TARGET_FIELDS=values.sourceType=int*|values.bindingClass=storage-buffer|values.argumentIndex=0|values.storageBufferLayout.layout=std430|values.storageBufferLayout.elementType=int"
    "-DEXPECTED_REFLECTION_FEATURE_FIELDS=glsl-lowering.kind=backend|compute-kernel.kind=stage|storage-buffer.kind=resource|scalar-comparison.kind=operation|select-expression.kind=operation"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
set(CROSSGL_OPENGL_LOAD_LOCAL_SOURCE_SNIPPET [=[float x = values[0];
  values[1] = x + 1.0;
  return;]=])
add_test(NAME cglc_build_opengl_load_local_source_package
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_LOAD_LOCAL_COMPUTE_SHADER}
    -DTARGET=opengl
    -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-opengl-load-local-source.cglb
    -DMODE=source-package-build
    -DEXPECTED_SOURCE=backend/opengl/LoadLocalComputeShader.comp.glsl
    "-DEXPECTED_SOURCE_SNIPPET=${CROSSGL_OPENGL_LOAD_LOCAL_SOURCE_SNIPPET}"
    "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=opengl|module=LoadLocalComputeShader"
    "-DEXPECTED_REFLECTION_TARGET_FIELDS=values.sourceType=float*|values.bindingClass=storage-buffer|values.argumentIndex=0|values.storageBufferLayout.layout=std430|values.storageBufferLayout.elementType=float"
    "-DEXPECTED_REFLECTION_FEATURE_FIELDS=storage-buffer.kind=resource|local-declaration.kind=operation|storage-buffer-read.kind=operation|storage-buffer-write.kind=operation|scalar-arithmetic.kind=operation"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
set(CROSSGL_OPENGL_SCALAR_CONSTRUCTOR_SOURCE_SNIPPET [=[int signedValue = int(source);
  uint unsignedValue = uint(source);
  float signedBack = float(signedValue);
  float unsignedBack = float(unsignedValue);
  values[1] = signedBack + unsignedBack;]=])
add_test(NAME cglc_build_opengl_scalar_constructor_source_package
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_SCALAR_CONSTRUCTOR_COMPUTE_SHADER}
    -DTARGET=opengl
    -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-opengl-scalar-constructor-source.cglb
    -DMODE=source-package-build
    -DEXPECTED_SOURCE=backend/opengl/ScalarConstructorComputeShader.comp.glsl
    "-DEXPECTED_SOURCE_SNIPPET=${CROSSGL_OPENGL_SCALAR_CONSTRUCTOR_SOURCE_SNIPPET}"
    "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=opengl|module=ScalarConstructorComputeShader"
    "-DEXPECTED_REFLECTION_TARGET_FIELDS=values.sourceType=float*|values.bindingClass=storage-buffer|values.argumentIndex=0|values.storageBufferLayout.layout=std430|values.storageBufferLayout.elementType=float"
    "-DEXPECTED_REFLECTION_FEATURE_FIELDS=storage-buffer.kind=resource|local-declaration.kind=operation|storage-buffer-read.kind=operation|index-access.kind=operation|scalar-constructor.kind=operation|storage-buffer-write.kind=operation|scalar-arithmetic.kind=operation"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
set(CROSSGL_OPENGL_MATRIX_CONSTRUCTOR_SOURCE_SNIPPET [=[mat2 flattened = mat2(1.0, 2.0, 3.0, 4.0);
  mat2 diagonal = mat2(5.0);
  mat3 expanded = mat3(flattened);
  vec3 c0 = vec3(1.0, 2.0, 3.0);
  vec3 c1 = vec3(4.0, 5.0, 6.0);
  vec3 c2 = vec3(7.0, 8.0, 9.0);
  mat3 basis = mat3(c0, c1, c2);]=])
add_test(NAME cglc_build_opengl_matrix_constructor_source_package
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_MATRIX_CONSTRUCTOR_COMPUTE_SHADER}
    -DTARGET=opengl
    -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-opengl-matrix-constructor-source.cglb
    -DMODE=source-package-build
    -DEXPECTED_SOURCE=backend/opengl/MatrixConstructorComputeShader.comp.glsl
    "-DEXPECTED_SOURCE_SNIPPET=${CROSSGL_OPENGL_MATRIX_CONSTRUCTOR_SOURCE_SNIPPET}"
    "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=opengl|module=MatrixConstructorComputeShader|nativeBinary=backend/opengl/MatrixConstructorComputeShader.glsl|resources.0.name=values|resources.0.kind=buffer|resources.0.type=float*|workgroupSizes.0.entryPoint=compute_main|workgroupSizes.0.x=1|workgroupSizes.0.y=1|workgroupSizes.0.z=1"
    "-DEXPECTED_REFLECTION_JSON_ARRAY_LENGTHS=resources=1|targetResourceBindings=1|workgroupSizes=1"
    "-DEXPECTED_REFLECTION_TARGET_FIELDS=values.sourceType=float*|values.bindingClass=storage-buffer|values.argumentIndex=0|values.set=0|values.binding=0|values.storageBufferLayout.elementType=float|values.storageBufferLayout.arrayStrideBytes=4|values.storageBufferLayout.layout=std430"
    "-DEXPECTED_REFLECTION_FEATURE_FIELDS=glsl-lowering.kind=backend|compute-kernel.kind=stage|workgroup-size.kind=execution|storage-buffer.kind=resource|storage-buffer-write.kind=operation|index-access.kind=operation|local-declaration.kind=operation|vector-constructor.kind=operation|matrix-constructor.kind=operation"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
set(CROSSGL_OPENGL_MATRIX_VECTOR_ARITHMETIC_SOURCE_SNIPPET [=[vec3 columnProduct = transform * source;
  vec3 rowProduct = source * transform;
  mat3 composed = transform * basis;
  vec3 projected = composed * rowProduct;]=])
add_test(NAME cglc_build_opengl_matrix_vector_arithmetic_source_package
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_MATRIX_VECTOR_ARITHMETIC_COMPUTE_SHADER}
    -DTARGET=opengl
    -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-opengl-matrix-vector-arithmetic-source.cglb
    -DMODE=source-package-build
    -DEXPECTED_SOURCE=backend/opengl/MatrixVectorArithmeticComputeShader.comp.glsl
    "-DEXPECTED_SOURCE_SNIPPET=${CROSSGL_OPENGL_MATRIX_VECTOR_ARITHMETIC_SOURCE_SNIPPET}"
    "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=opengl|module=MatrixVectorArithmeticComputeShader|nativeBinary=backend/opengl/MatrixVectorArithmeticComputeShader.glsl|resources.0.name=values|resources.0.kind=buffer|resources.0.type=float*|workgroupSizes.0.entryPoint=compute_main|workgroupSizes.0.x=1|workgroupSizes.0.y=1|workgroupSizes.0.z=1"
    "-DEXPECTED_REFLECTION_JSON_ARRAY_LENGTHS=resources=1|targetResourceBindings=1|workgroupSizes=1"
    "-DEXPECTED_REFLECTION_TARGET_FIELDS=values.sourceType=float*|values.bindingClass=storage-buffer|values.argumentIndex=0|values.set=0|values.binding=0|values.storageBufferLayout.elementType=float|values.storageBufferLayout.arrayStrideBytes=4|values.storageBufferLayout.layout=std430"
    "-DEXPECTED_REFLECTION_FEATURE_FIELDS=glsl-lowering.kind=backend|compute-kernel.kind=stage|workgroup-size.kind=execution|storage-buffer.kind=resource|storage-buffer-read.kind=operation|storage-buffer-write.kind=operation|index-access.kind=operation|local-declaration.kind=operation|vector-constructor.kind=operation|matrix-constructor.kind=operation|vector-arithmetic.kind=operation|scalar-arithmetic.kind=operation"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
set(CROSSGL_OPENGL_MATRIX_SCALAR_ARITHMETIC_SOURCE_SNIPPET [=[mat3 scaled = transform * 2.0;
  mat3 rescaled = 0.5 * transform;
  mat3 inferred = transform * 0.25;
  inferred = inferred * 4.0;]=])
add_test(NAME cglc_build_opengl_matrix_scalar_arithmetic_source_package
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_MATRIX_SCALAR_ARITHMETIC_COMPUTE_SHADER}
    -DTARGET=opengl
    -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-opengl-matrix-scalar-arithmetic-source.cglb
    -DMODE=source-package-build
    -DEXPECTED_SOURCE=backend/opengl/MatrixScalarArithmeticComputeShader.comp.glsl
    "-DEXPECTED_SOURCE_SNIPPET=${CROSSGL_OPENGL_MATRIX_SCALAR_ARITHMETIC_SOURCE_SNIPPET}"
    "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=opengl|module=MatrixScalarArithmeticComputeShader|nativeBinary=backend/opengl/MatrixScalarArithmeticComputeShader.glsl|resources.0.name=values|resources.0.kind=buffer|resources.0.type=float*|workgroupSizes.0.entryPoint=compute_main|workgroupSizes.0.x=1|workgroupSizes.0.y=1|workgroupSizes.0.z=1"
    "-DEXPECTED_REFLECTION_JSON_ARRAY_LENGTHS=resources=1|targetResourceBindings=1|workgroupSizes=1"
    "-DEXPECTED_REFLECTION_TARGET_FIELDS=values.sourceType=float*|values.bindingClass=storage-buffer|values.argumentIndex=0|values.set=0|values.binding=0|values.storageBufferLayout.elementType=float|values.storageBufferLayout.arrayStrideBytes=4|values.storageBufferLayout.layout=std430"
    "-DEXPECTED_REFLECTION_FEATURE_FIELDS=glsl-lowering.kind=backend|compute-kernel.kind=stage|workgroup-size.kind=execution|storage-buffer.kind=resource|storage-buffer-write.kind=operation|index-access.kind=operation|local-declaration.kind=operation|matrix-constructor.kind=operation|scalar-arithmetic.kind=operation"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
set(CROSSGL_OPENGL_VECTOR_LOCAL_SOURCE_SNIPPET [=[vec4 color = vec4(values[0], values[1], values[2], 1.0);
  vec4 lifted = color + vec4(0.5, 0.5, 0.5, 0.0);
  values[0] = lifted.x;
  values[1] = lifted.y;]=])
add_test(NAME cglc_build_opengl_vector_local_source_package
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_VECTOR_LOCAL_COMPUTE_SHADER}
    -DTARGET=opengl
    -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-opengl-vector-local-source.cglb
    -DMODE=source-package-build
    -DEXPECTED_SOURCE=backend/opengl/VectorLocalComputeShader.comp.glsl
    "-DEXPECTED_SOURCE_SNIPPET=${CROSSGL_OPENGL_VECTOR_LOCAL_SOURCE_SNIPPET}"
    "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=opengl|module=VectorLocalComputeShader"
    "-DEXPECTED_REFLECTION_TARGET_FIELDS=values.sourceType=float*|values.bindingClass=storage-buffer|values.argumentIndex=0|values.storageBufferLayout.layout=std430|values.storageBufferLayout.elementType=float"
    "-DEXPECTED_REFLECTION_FEATURE_FIELDS=storage-buffer.kind=resource|local-declaration.kind=operation|vector-constructor.kind=operation|vector-arithmetic.kind=operation|storage-buffer-write.kind=operation"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
set(CROSSGL_OPENGL_VECTOR_SCALAR_SOURCE_SNIPPET [=[vec4 color = values[0];
  vec4 scaled = color * 0.5;
  vec4 biased = 0.25 + scaled;
  vec4 inverted = 1.0 - biased;
  vec4 normalized = inverted / 2.0;
  values[1] = normalized;]=])
add_test(NAME cglc_build_opengl_vector_scalar_source_package
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_VECTOR_SCALAR_COMPUTE_SHADER}
    -DTARGET=opengl
    -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-opengl-vector-scalar-source.cglb
    -DMODE=source-package-build
    -DEXPECTED_SOURCE=backend/opengl/VectorScalarComputeShader.comp.glsl
    "-DEXPECTED_SOURCE_SNIPPET=${CROSSGL_OPENGL_VECTOR_SCALAR_SOURCE_SNIPPET}"
    "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=opengl|module=VectorScalarComputeShader"
    "-DEXPECTED_REFLECTION_JSON_ARRAY_LENGTHS=resources=1|targetResourceBindings=1"
    "-DEXPECTED_REFLECTION_TARGET_FIELDS=values.sourceType=vec4*|values.bindingClass=storage-buffer|values.argumentIndex=0|values.storageBufferLayout.layout=std430|values.storageBufferLayout.elementType=vec4|values.storageBufferLayout.arrayStrideBytes=16"
    "-DEXPECTED_REFLECTION_FEATURE_FIELDS=glsl-lowering.kind=backend|storage-buffer.kind=resource|vector-storage-buffer.kind=layout|local-declaration.kind=operation|storage-buffer-read.kind=operation|index-access.kind=operation|vector-arithmetic.kind=operation|storage-buffer-write.kind=operation"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
set(CROSSGL_OPENGL_VECTOR_SCALAR_CAST_SOURCE_SNIPPET [=[const int OFFSET = 1;

layout(local_size_x = 1, local_size_y = 1, local_size_z = 1) in;

// CrossGL set 0, binding 0
layout(binding = 0, std430) buffer values_Buffer {
  vec4 values[];
};

void main() {
  vec4 color = values[0];
  vec4 scaled = color * float(2);
  vec4 biased = float(1) + scaled;
  values[1] = biased;]=])
add_test(NAME cglc_build_opengl_vector_scalar_cast_source_package
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_VECTOR_SCALAR_CAST_COMPUTE_SHADER}
    -DTARGET=opengl
    -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-opengl-vector-scalar-cast-source.cglb
    -DMODE=source-package-build
    -DEXPECTED_SOURCE=backend/opengl/VectorScalarCastComputeShader.comp.glsl
    "-DEXPECTED_SOURCE_SNIPPET=${CROSSGL_OPENGL_VECTOR_SCALAR_CAST_SOURCE_SNIPPET}"
    "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=opengl|module=VectorScalarCastComputeShader"
    "-DEXPECTED_REFLECTION_JSON_ARRAY_LENGTHS=resources=1|targetResourceBindings=1"
    "-DEXPECTED_REFLECTION_TARGET_FIELDS=values.sourceType=vec4*|values.bindingClass=storage-buffer|values.argumentIndex=0|values.storageBufferLayout.layout=std430|values.storageBufferLayout.elementType=vec4|values.storageBufferLayout.arrayStrideBytes=16"
    "-DEXPECTED_REFLECTION_FEATURE_FIELDS=glsl-lowering.kind=backend|storage-buffer.kind=resource|vector-storage-buffer.kind=layout|local-declaration.kind=operation|storage-buffer-read.kind=operation|index-access.kind=operation|vector-arithmetic.kind=operation|scalar-constructor.kind=operation|storage-buffer-write.kind=operation"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
set(CROSSGL_OPENGL_VECTOR_BUFFER_SOURCE_SNIPPET [=[vec4 color = values[0];
  vec4 lifted = color + vec4(0.5, 0.5, 0.5, 0.0);
  values[1] = lifted;]=])
add_test(NAME cglc_build_opengl_vector_buffer_source_package
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_VECTOR_BUFFER_COMPUTE_SHADER}
    -DTARGET=opengl
    -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-opengl-vector-buffer-source.cglb
    -DMODE=source-package-build
    -DEXPECTED_SOURCE=backend/opengl/VectorBufferComputeShader.comp.glsl
    "-DEXPECTED_SOURCE_SNIPPET=${CROSSGL_OPENGL_VECTOR_BUFFER_SOURCE_SNIPPET}"
    "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=opengl|module=VectorBufferComputeShader"
    "-DEXPECTED_REFLECTION_TARGET_FIELDS=values.sourceType=vec4*|values.bindingClass=storage-buffer|values.argumentIndex=0|values.storageBufferLayout.layout=std430|values.storageBufferLayout.elementType=vec4|values.storageBufferLayout.arrayStrideBytes=16"
    "-DEXPECTED_REFLECTION_FEATURE_FIELDS=storage-buffer.kind=resource|vector-storage-buffer.kind=layout|vector-arithmetic.kind=operation|vector-constructor.kind=operation|storage-buffer-write.kind=operation"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
set(CROSSGL_OPENGL_VECTOR3_BUFFER_SOURCE_SNIPPET [=[vec3 color = values[0];
  vec3 lifted = color + vec3(0.5, 0.5, 0.0);
  values[1] = lifted;]=])
add_test(NAME cglc_build_opengl_vector3_buffer_source_package
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_VECTOR3_BUFFER_COMPUTE_SHADER}
    -DTARGET=opengl
    -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-opengl-vector3-buffer-source.cglb
    -DMODE=source-package-build
    -DEXPECTED_SOURCE=backend/opengl/Vector3BufferComputeShader.comp.glsl
    "-DEXPECTED_SOURCE_SNIPPET=${CROSSGL_OPENGL_VECTOR3_BUFFER_SOURCE_SNIPPET}"
    "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=opengl|module=Vector3BufferComputeShader"
    "-DEXPECTED_REFLECTION_TARGET_FIELDS=values.sourceType=vec3*|values.bindingClass=storage-buffer|values.argumentIndex=0|values.storageBufferLayout.layout=std430|values.storageBufferLayout.elementType=vec3|values.storageBufferLayout.arrayStrideBytes=16"
    "-DEXPECTED_REFLECTION_FEATURE_FIELDS=storage-buffer.kind=resource|vector-storage-buffer.kind=layout|vector-arithmetic.kind=operation|vector-constructor.kind=operation|storage-buffer-write.kind=operation"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
set(CROSSGL_DIRECTX_IF_SOURCE_SNIPPET [=[if (x > 0.0) {
    y = x;
  } else {
    y = -x;
  }
  values[1] = y;]=])
add_test(NAME cglc_build_directx_if_source_package
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_IF_COMPUTE_SHADER}
    -DTARGET=directx
    -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-directx-if-source.cglb
    -DMODE=source-package-build
    -DEXPECTED_SOURCE=backend/directx/IfComputeShader.hlsl
    "-DEXPECTED_SOURCE_SNIPPET=${CROSSGL_DIRECTX_IF_SOURCE_SNIPPET}"
    "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=directx|module=IfComputeShader|nativeBinary=backend/directx/IfComputeShader.dxil"
    "-DEXPECTED_REFLECTION_TARGET_FIELDS=values.sourceType=float*|values.hlslType=RWStructuredBuffer<float>|values.bindingClass=uav|values.descriptorType=UAV|values.argumentIndex=0"
    "-DEXPECTED_REFLECTION_FEATURE_FIELDS=structured-selection.kind=controlFlow|storage-buffer-read.kind=operation|storage-buffer-write.kind=operation"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
set(CROSSGL_DIRECTX_IF_SCOPED_SOURCE_SNIPPET [=[if (x > 0.0) {
    float scaled = x * 2.0;
    y = scaled;
  } else {
    float scaled = -x;
    y = scaled;
  }
  values[1] = y;]=])
add_test(NAME cglc_build_directx_if_scoped_source_package
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_IF_SCOPED_COMPUTE_SHADER}
    -DTARGET=directx
    -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-directx-if-scoped-source.cglb
    -DMODE=source-package-build
    -DEXPECTED_SOURCE=backend/directx/IfScopedComputeShader.hlsl
    "-DEXPECTED_SOURCE_SNIPPET=${CROSSGL_DIRECTX_IF_SCOPED_SOURCE_SNIPPET}"
    "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=directx|module=IfScopedComputeShader|nativeBinary=backend/directx/IfScopedComputeShader.dxil"
    "-DEXPECTED_REFLECTION_JSON_ARRAY_LENGTHS=resources=1|targetResourceBindings=1"
    "-DEXPECTED_REFLECTION_TARGET_FIELDS=values.sourceType=float*|values.hlslType=RWStructuredBuffer<float>|values.bindingClass=uav|values.descriptorType=UAV|values.argumentIndex=0"
    "-DEXPECTED_REFLECTION_FEATURE_FIELDS=hlsl-lowering.kind=backend|storage-buffer.kind=resource|local-declaration.kind=operation|storage-buffer-read.kind=operation|index-access.kind=operation|structured-selection.kind=controlFlow|scalar-arithmetic.kind=operation|scalar-comparison.kind=operation|storage-buffer-write.kind=operation"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
set(CROSSGL_DIRECTX_NESTED_IF_SOURCE_SNIPPET [=[if (x > 0.0) {
    float scaled = x * 2.0;
    if (scaled > 3.0) {
      y = scaled;
    } else {
      y = x;
    }
  } else {
    y = -x;
  }
  values[1] = y;]=])
add_test(NAME cglc_build_directx_nested_if_source_package
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_NESTED_IF_COMPUTE_SHADER}
    -DTARGET=directx
    -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-directx-nested-if-source.cglb
    -DMODE=source-package-build
    -DEXPECTED_SOURCE=backend/directx/NestedIfComputeShader.hlsl
    "-DEXPECTED_SOURCE_SNIPPET=${CROSSGL_DIRECTX_NESTED_IF_SOURCE_SNIPPET}"
    "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=directx|module=NestedIfComputeShader|nativeBinary=backend/directx/NestedIfComputeShader.dxil"
    "-DEXPECTED_REFLECTION_TARGET_FIELDS=values.sourceType=float*|values.hlslType=RWStructuredBuffer<float>|values.bindingClass=uav|values.descriptorType=UAV|values.argumentIndex=0"
    "-DEXPECTED_REFLECTION_FEATURE_FIELDS=structured-selection.kind=controlFlow|local-declaration.kind=operation|storage-buffer-read.kind=operation|storage-buffer-write.kind=operation"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
set(CROSSGL_DIRECTX_IF_RETURN_SOURCE_SNIPPET [=[if (x > 0.0) {
    values[1] = x;
    return;
  } else {
    values[1] = -x;
    return;
  }]=])
add_test(NAME cglc_build_directx_if_return_source_package
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_IF_RETURN_COMPUTE_SHADER}
    -DTARGET=directx
    -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-directx-if-return-source.cglb
    -DMODE=source-package-build
    -DEXPECTED_SOURCE=backend/directx/IfReturnComputeShader.hlsl
    "-DEXPECTED_SOURCE_SNIPPET=${CROSSGL_DIRECTX_IF_RETURN_SOURCE_SNIPPET}"
    "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=directx|module=IfReturnComputeShader|nativeBinary=backend/directx/IfReturnComputeShader.dxil"
    "-DEXPECTED_REFLECTION_TARGET_FIELDS=values.sourceType=float*|values.hlslType=RWStructuredBuffer<float>|values.bindingClass=uav|values.descriptorType=UAV|values.argumentIndex=0"
    "-DEXPECTED_REFLECTION_FEATURE_FIELDS=structured-selection.kind=controlFlow|storage-buffer-read.kind=operation|storage-buffer-write.kind=operation"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_build_directx_read_modify_write_source_package
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_READ_MODIFY_WRITE_COMPUTE_SHADER}
    -DTARGET=directx
    -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-directx-read-modify-write-source.cglb
    -DMODE=source-package-build
    -DEXPECTED_SOURCE=backend/directx/ReadModifyWriteComputeShader.hlsl
    "-DEXPECTED_SOURCE_SNIPPET=values[0] = values[0] + 1.0;"
    "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=directx|module=ReadModifyWriteComputeShader|nativeBinary=backend/directx/ReadModifyWriteComputeShader.dxil"
    "-DEXPECTED_REFLECTION_TARGET_FIELDS=values.sourceType=float*|values.hlslType=RWStructuredBuffer<float>|values.bindingClass=uav|values.descriptorType=UAV|values.argumentIndex=0"
    "-DEXPECTED_REFLECTION_FEATURE_FIELDS=storage-buffer-read.kind=operation|storage-buffer-write.kind=operation"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_build_opengl_if_source_package
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_IF_COMPUTE_SHADER}
    -DTARGET=opengl
    -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-opengl-if-source.cglb
    -DMODE=source-package-build
    -DEXPECTED_SOURCE=backend/opengl/IfComputeShader.comp.glsl
    "-DEXPECTED_SOURCE_SNIPPET=if (x > 0.0)"
    "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=opengl|module=IfComputeShader"
    "-DEXPECTED_REFLECTION_TARGET_FIELDS=values.sourceType=float*|values.bindingClass=storage-buffer|values.argumentIndex=0|values.storageBufferLayout.layout=std430|values.storageBufferLayout.elementType=float"
    "-DEXPECTED_REFLECTION_FEATURE_FIELDS=structured-selection.kind=controlFlow|storage-buffer-read.kind=operation|storage-buffer-write.kind=operation"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
set(CROSSGL_OPENGL_IF_SCOPED_SOURCE_SNIPPET [=[if (x > 0.0) {
    float scaled = x * 2.0;
    y = scaled;
  } else {
    float scaled = -x;
    y = scaled;
  }
  values[1] = y;]=])
add_test(NAME cglc_build_opengl_if_scoped_source_package
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_IF_SCOPED_COMPUTE_SHADER}
    -DTARGET=opengl
    -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-opengl-if-scoped-source.cglb
    -DMODE=source-package-build
    -DEXPECTED_SOURCE=backend/opengl/IfScopedComputeShader.comp.glsl
    "-DEXPECTED_SOURCE_SNIPPET=${CROSSGL_OPENGL_IF_SCOPED_SOURCE_SNIPPET}"
    "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=opengl|module=IfScopedComputeShader"
    "-DEXPECTED_REFLECTION_JSON_ARRAY_LENGTHS=resources=1|targetResourceBindings=1"
    "-DEXPECTED_REFLECTION_TARGET_FIELDS=values.sourceType=float*|values.bindingClass=storage-buffer|values.argumentIndex=0|values.storageBufferLayout.layout=std430|values.storageBufferLayout.elementType=float|values.storageBufferLayout.arrayStrideBytes=4"
    "-DEXPECTED_REFLECTION_FEATURE_FIELDS=glsl-lowering.kind=backend|storage-buffer.kind=resource|local-declaration.kind=operation|storage-buffer-read.kind=operation|index-access.kind=operation|structured-selection.kind=controlFlow|scalar-arithmetic.kind=operation|scalar-comparison.kind=operation|storage-buffer-write.kind=operation"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_build_opengl_nested_if_source_package
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_NESTED_IF_COMPUTE_SHADER}
    -DTARGET=opengl
    -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-opengl-nested-if-source.cglb
    -DMODE=source-package-build
    -DEXPECTED_SOURCE=backend/opengl/NestedIfComputeShader.comp.glsl
    "-DEXPECTED_SOURCE_SNIPPET=if (scaled > 3.0)"
    "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=opengl|module=NestedIfComputeShader"
    "-DEXPECTED_REFLECTION_TARGET_FIELDS=values.sourceType=float*|values.bindingClass=storage-buffer|values.argumentIndex=0|values.storageBufferLayout.layout=std430|values.storageBufferLayout.elementType=float"
    "-DEXPECTED_REFLECTION_FEATURE_FIELDS=structured-selection.kind=controlFlow|storage-buffer-read.kind=operation|storage-buffer-write.kind=operation"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
set(CROSSGL_OPENGL_IF_RETURN_SOURCE_SNIPPET [=[values[1] = x;
    return;]=])
add_test(NAME cglc_build_opengl_if_return_source_package
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_IF_RETURN_COMPUTE_SHADER}
    -DTARGET=opengl
    -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-opengl-if-return-source.cglb
    -DMODE=source-package-build
    -DEXPECTED_SOURCE=backend/opengl/IfReturnComputeShader.comp.glsl
    "-DEXPECTED_SOURCE_SNIPPET=${CROSSGL_OPENGL_IF_RETURN_SOURCE_SNIPPET}"
    "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=opengl|module=IfReturnComputeShader"
    "-DEXPECTED_REFLECTION_TARGET_FIELDS=values.sourceType=float*|values.bindingClass=storage-buffer|values.argumentIndex=0|values.storageBufferLayout.layout=std430|values.storageBufferLayout.elementType=float"
    "-DEXPECTED_REFLECTION_FEATURE_FIELDS=structured-selection.kind=controlFlow|storage-buffer-read.kind=operation|storage-buffer-write.kind=operation"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_build_opengl_read_modify_write_source_package
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_READ_MODIFY_WRITE_COMPUTE_SHADER}
    -DTARGET=opengl
    -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-opengl-read-modify-write-source.cglb
    -DMODE=source-package-build
    -DEXPECTED_SOURCE=backend/opengl/ReadModifyWriteComputeShader.comp.glsl
    "-DEXPECTED_SOURCE_SNIPPET=values[0] = values[0] + 1.0;"
    "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=opengl|module=ReadModifyWriteComputeShader"
    "-DEXPECTED_REFLECTION_TARGET_FIELDS=values.sourceType=float*|values.bindingClass=storage-buffer|values.argumentIndex=0|values.storageBufferLayout.layout=std430|values.storageBufferLayout.elementType=float"
    "-DEXPECTED_REFLECTION_FEATURE_FIELDS=storage-buffer-write.kind=operation|storage-buffer-read.kind=operation|scalar-arithmetic.kind=operation"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_build_opengl_while_source_package
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_WHILE_COMPUTE_SHADER}
    -DTARGET=opengl
    -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-opengl-while-source.cglb
    -DMODE=source-package-build
    -DEXPECTED_SOURCE=backend/opengl/WhileComputeShader.comp.glsl
    "-DEXPECTED_SOURCE_SNIPPET=for (; i < 4; )"
    "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=opengl|module=WhileComputeShader"
    "-DEXPECTED_REFLECTION_TARGET_FIELDS=values.sourceType=float*|values.bindingClass=storage-buffer|values.argumentIndex=0|values.storageBufferLayout.layout=std430|values.storageBufferLayout.elementType=float"
    "-DEXPECTED_REFLECTION_FEATURE_FIELDS=structured-loop.kind=controlFlow|storage-buffer-write.kind=operation"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
set(CROSSGL_DIRECTX_FOR_SOURCE_SNIPPET [=[for (int i = 0; i < 4; i++) {
    float x = values[i];
    values[i] = x + 1.0;]=])
add_test(NAME cglc_build_directx_for_source_package
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_FOR_COMPUTE_SHADER}
    -DTARGET=directx
    -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-directx-for-source.cglb
    -DMODE=source-package-build
    -DEXPECTED_SOURCE=backend/directx/ForComputeShader.hlsl
    "-DEXPECTED_SOURCE_SNIPPET=${CROSSGL_DIRECTX_FOR_SOURCE_SNIPPET}"
    "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=directx|module=ForComputeShader|nativeBinary=backend/directx/ForComputeShader.dxil|workgroupSizes.0.x=1"
    "-DEXPECTED_REFLECTION_JSON_ARRAY_LENGTHS=resources=1|targetResourceBindings=1"
    "-DEXPECTED_REFLECTION_TARGET_FIELDS=values.sourceType=float*|values.hlslType=RWStructuredBuffer<float>|values.bindingClass=uav|values.descriptorType=UAV|values.argumentIndex=0"
    "-DEXPECTED_REFLECTION_FEATURE_FIELDS=structured-loop.kind=controlFlow|storage-buffer.kind=resource|storage-buffer-read.kind=operation|storage-buffer-write.kind=operation|scalar-arithmetic.kind=operation"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
set(CROSSGL_DIRECTX_FOR_STRIDE_SOURCE_SNIPPET [=[for (int i = 0; i < 8; i+=2) {
    float x = values[i];
    values[i] = x + 1.0;]=])
add_test(NAME cglc_build_directx_for_stride_source_package
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_FOR_STRIDE_COMPUTE_SHADER}
    -DTARGET=directx
    -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-directx-for-stride-source.cglb
    -DMODE=source-package-build
    -DEXPECTED_SOURCE=backend/directx/ForStrideComputeShader.hlsl
    "-DEXPECTED_SOURCE_SNIPPET=${CROSSGL_DIRECTX_FOR_STRIDE_SOURCE_SNIPPET}"
    "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=directx|module=ForStrideComputeShader|nativeBinary=backend/directx/ForStrideComputeShader.dxil|workgroupSizes.0.x=1"
    "-DEXPECTED_REFLECTION_JSON_ARRAY_LENGTHS=resources=1|targetResourceBindings=1"
    "-DEXPECTED_REFLECTION_TARGET_FIELDS=values.sourceType=float*|values.hlslType=RWStructuredBuffer<float>|values.bindingClass=uav|values.descriptorType=UAV|values.argumentIndex=0"
    "-DEXPECTED_REFLECTION_FEATURE_FIELDS=structured-loop.kind=controlFlow|storage-buffer.kind=resource|storage-buffer-read.kind=operation|storage-buffer-write.kind=operation|scalar-arithmetic.kind=operation"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
set(CROSSGL_DIRECTX_NESTED_FOR_SOURCE_SNIPPET [=[for (int i = 0; i < 2; i++) {
    for (int j = 0; j < 2; j++) {
      int index = i * 2 + j;
      float x = values[index];
      values[index] = x + 1.0;
    }
    values[i] = values[i] + 2.0;]=])
add_test(NAME cglc_build_directx_nested_for_source_package
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_NESTED_FOR_COMPUTE_SHADER}
    -DTARGET=directx
    -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-directx-nested-for-source.cglb
    -DMODE=source-package-build
    -DEXPECTED_SOURCE=backend/directx/NestedForComputeShader.hlsl
    "-DEXPECTED_SOURCE_SNIPPET=${CROSSGL_DIRECTX_NESTED_FOR_SOURCE_SNIPPET}"
    "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=directx|module=NestedForComputeShader|nativeBinary=backend/directx/NestedForComputeShader.dxil|workgroupSizes.0.x=1"
    "-DEXPECTED_REFLECTION_JSON_ARRAY_LENGTHS=resources=1|targetResourceBindings=1"
    "-DEXPECTED_REFLECTION_TARGET_FIELDS=values.sourceType=float*|values.hlslType=RWStructuredBuffer<float>|values.bindingClass=uav|values.descriptorType=UAV|values.argumentIndex=0"
    "-DEXPECTED_REFLECTION_FEATURE_FIELDS=structured-loop.kind=controlFlow|storage-buffer.kind=resource|local-declaration.kind=operation|storage-buffer-read.kind=operation|storage-buffer-write.kind=operation|scalar-arithmetic.kind=operation"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
set(CROSSGL_DIRECTX_FOR_DYNAMIC_STRIDE_SOURCE_SNIPPET [=[int stride = 2;
  for (int i = 0; i < 8; i+=stride) {
    float x = values[i];
    values[i] = x + 1.0;]=])
add_test(NAME cglc_build_directx_for_dynamic_stride_source_package
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_FOR_DYNAMIC_STRIDE_COMPUTE_SHADER}
    -DTARGET=directx
    -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-directx-for-dynamic-stride-source.cglb
    -DMODE=source-package-build
    -DEXPECTED_SOURCE=backend/directx/ForDynamicStrideComputeShader.hlsl
    "-DEXPECTED_SOURCE_SNIPPET=${CROSSGL_DIRECTX_FOR_DYNAMIC_STRIDE_SOURCE_SNIPPET}"
    "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=directx|module=ForDynamicStrideComputeShader|nativeBinary=backend/directx/ForDynamicStrideComputeShader.dxil|workgroupSizes.0.x=1"
    "-DEXPECTED_REFLECTION_JSON_ARRAY_LENGTHS=resources=1|targetResourceBindings=1"
    "-DEXPECTED_REFLECTION_TARGET_FIELDS=values.sourceType=float*|values.hlslType=RWStructuredBuffer<float>|values.bindingClass=uav|values.descriptorType=UAV|values.argumentIndex=0"
    "-DEXPECTED_REFLECTION_FEATURE_FIELDS=structured-loop.kind=controlFlow|storage-buffer.kind=resource|local-declaration.kind=operation|storage-buffer-read.kind=operation|storage-buffer-write.kind=operation|scalar-arithmetic.kind=operation"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
set(CROSSGL_DIRECTX_WHILE_SOURCE_SNIPPET [=[for (; i < 4; ) {
    values[i] = values[i] + 1.0;]=])
add_test(NAME cglc_build_directx_while_source_package
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_WHILE_COMPUTE_SHADER}
    -DTARGET=directx
    -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-directx-while-source.cglb
    -DMODE=source-package-build
    -DEXPECTED_SOURCE=backend/directx/WhileComputeShader.hlsl
    "-DEXPECTED_SOURCE_SNIPPET=${CROSSGL_DIRECTX_WHILE_SOURCE_SNIPPET}"
    "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=directx|module=WhileComputeShader|nativeBinary=backend/directx/WhileComputeShader.dxil"
    "-DEXPECTED_REFLECTION_TARGET_FIELDS=values.sourceType=float*|values.hlslType=RWStructuredBuffer<float>|values.bindingClass=uav|values.descriptorType=UAV|values.argumentIndex=0"
    "-DEXPECTED_REFLECTION_FEATURE_FIELDS=structured-loop.kind=controlFlow|storage-buffer-write.kind=operation"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
set(CROSSGL_OPENGL_LOOP_REFLECTION_TARGET_FIELDS
  "values.sourceType=float*|values.bindingClass=storage-buffer|values.argumentIndex=0|values.storageBufferLayout.layout=std430|values.storageBufferLayout.elementType=float")
set(CROSSGL_OPENGL_LOOP_REFLECTION_FEATURE_FIELDS
  "storage-buffer.kind=resource|structured-loop.kind=controlFlow|scalar-arithmetic.kind=operation|scalar-comparison.kind=operation|local-declaration.kind=operation|storage-buffer-read.kind=operation|index-access.kind=operation|storage-buffer-write.kind=operation")
set(CROSSGL_OPENGL_VALIDATED_LOOP_REFLECTION_FEATURE_FIELDS
  "native-glsl-package.kind=backend|glsl-program-validation.kind=validation|storage-buffer.kind=resource|structured-loop.kind=controlFlow|scalar-arithmetic.kind=operation|scalar-comparison.kind=operation|local-declaration.kind=operation|storage-buffer-read.kind=operation|index-access.kind=operation|storage-buffer-write.kind=operation")
add_test(NAME cglc_build_opengl_for_source_package
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_FOR_COMPUTE_SHADER}
    -DTARGET=opengl
    -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-opengl-for-source.cglb
    -DMODE=source-package-build
    -DEXPECTED_SOURCE=backend/opengl/ForComputeShader.comp.glsl
    "-DEXPECTED_SOURCE_SNIPPET=for (int i = 0; i < 4; i++)"
    "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=opengl|module=ForComputeShader"
    "-DEXPECTED_REFLECTION_JSON_ARRAY_LENGTHS=resources=1|targetResourceBindings=1"
    "-DEXPECTED_REFLECTION_TARGET_FIELDS=${CROSSGL_OPENGL_LOOP_REFLECTION_TARGET_FIELDS}"
    "-DEXPECTED_REFLECTION_FEATURE_FIELDS=${CROSSGL_OPENGL_LOOP_REFLECTION_FEATURE_FIELDS}"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_build_opengl_for_stride_source_package
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_FOR_STRIDE_COMPUTE_SHADER}
    -DTARGET=opengl
    -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-opengl-for-stride-source.cglb
    -DMODE=source-package-build
    -DEXPECTED_SOURCE=backend/opengl/ForStrideComputeShader.comp.glsl
    "-DEXPECTED_SOURCE_SNIPPET=for (int i = 0; i < 8; i+=2)"
    "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=opengl|module=ForStrideComputeShader"
    "-DEXPECTED_REFLECTION_JSON_ARRAY_LENGTHS=resources=1|targetResourceBindings=1"
    "-DEXPECTED_REFLECTION_TARGET_FIELDS=${CROSSGL_OPENGL_LOOP_REFLECTION_TARGET_FIELDS}"
    "-DEXPECTED_REFLECTION_FEATURE_FIELDS=${CROSSGL_OPENGL_LOOP_REFLECTION_FEATURE_FIELDS}"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_build_opengl_nested_for_source_package
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_NESTED_FOR_COMPUTE_SHADER}
    -DTARGET=opengl
    -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-opengl-nested-for-source.cglb
    -DMODE=source-package-build
    -DEXPECTED_SOURCE=backend/opengl/NestedForComputeShader.comp.glsl
    "-DEXPECTED_SOURCE_SNIPPET=for (int j = 0; j < 2; j++)"
    "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=opengl|module=NestedForComputeShader"
    "-DEXPECTED_REFLECTION_JSON_ARRAY_LENGTHS=resources=1|targetResourceBindings=1"
    "-DEXPECTED_REFLECTION_TARGET_FIELDS=${CROSSGL_OPENGL_LOOP_REFLECTION_TARGET_FIELDS}"
    "-DEXPECTED_REFLECTION_FEATURE_FIELDS=${CROSSGL_OPENGL_LOOP_REFLECTION_FEATURE_FIELDS}"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_build_opengl_for_dynamic_stride_source_package
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_FOR_DYNAMIC_STRIDE_COMPUTE_SHADER}
    -DTARGET=opengl
    -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-opengl-for-dynamic-stride-source.cglb
    -DMODE=source-package-build
    -DEXPECTED_SOURCE=backend/opengl/ForDynamicStrideComputeShader.comp.glsl
    "-DEXPECTED_SOURCE_SNIPPET=for (int i = 0; i < 8; i+=stride)"
    "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=opengl|module=ForDynamicStrideComputeShader"
    "-DEXPECTED_REFLECTION_JSON_ARRAY_LENGTHS=resources=1|targetResourceBindings=1"
    "-DEXPECTED_REFLECTION_TARGET_FIELDS=${CROSSGL_OPENGL_LOOP_REFLECTION_TARGET_FIELDS}"
    "-DEXPECTED_REFLECTION_FEATURE_FIELDS=${CROSSGL_OPENGL_LOOP_REFLECTION_FEATURE_FIELDS}"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
set(CROSSGL_DIRECTX_FOR_CONSTANT_STRIDE_SOURCE_SNIPPET [=[static const int TILE_SIZE = 2;

RWStructuredBuffer<float> values : register(u0, space0);

[numthreads(1, 1, 1)]
void compute_main(uint3 crossgl_GlobalInvocationID : SV_DispatchThreadID) {
  for (int i = 0; i < 8; i+=TILE_SIZE) {
    float x = values[i];
    values[i] = x + 1.0;]=])
add_test(NAME cglc_build_directx_for_constant_stride_source_package
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_FOR_CONSTANT_STRIDE_COMPUTE_SHADER}
    -DTARGET=directx
    -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-directx-for-constant-source.cglb
    -DMODE=source-package-build
    -DEXPECTED_SOURCE=backend/directx/ForConstantStrideComputeShader.hlsl
    "-DEXPECTED_SOURCE_SNIPPET=${CROSSGL_DIRECTX_FOR_CONSTANT_STRIDE_SOURCE_SNIPPET}"
    "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=directx|module=ForConstantStrideComputeShader|nativeBinary=backend/directx/ForConstantStrideComputeShader.dxil|workgroupSizes.0.x=1"
    "-DEXPECTED_REFLECTION_JSON_ARRAY_LENGTHS=resources=1|targetResourceBindings=1"
    "-DEXPECTED_REFLECTION_TARGET_FIELDS=values.sourceType=float*|values.hlslType=RWStructuredBuffer<float>|values.bindingClass=uav|values.descriptorType=UAV|values.argumentIndex=0"
    "-DEXPECTED_REFLECTION_FEATURE_FIELDS=structured-loop.kind=controlFlow|storage-buffer.kind=resource|storage-buffer-read.kind=operation|storage-buffer-write.kind=operation|scalar-arithmetic.kind=operation"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_build_opengl_for_constant_stride_source_package
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_FOR_CONSTANT_STRIDE_COMPUTE_SHADER}
    -DTARGET=opengl
    -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-opengl-for-constant-source.cglb
    -DMODE=source-package-build
    -DEXPECTED_SOURCE=backend/opengl/ForConstantStrideComputeShader.comp.glsl
    "-DEXPECTED_SOURCE_SNIPPET=for (int i = 0; i < 8; i+=TILE_SIZE)"
    "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=opengl|module=ForConstantStrideComputeShader"
    "-DEXPECTED_REFLECTION_JSON_ARRAY_LENGTHS=resources=1|targetResourceBindings=1"
    "-DEXPECTED_REFLECTION_TARGET_FIELDS=${CROSSGL_OPENGL_LOOP_REFLECTION_TARGET_FIELDS}"
    "-DEXPECTED_REFLECTION_FEATURE_FIELDS=${CROSSGL_OPENGL_LOOP_REFLECTION_FEATURE_FIELDS}"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
set(CROSSGL_DIRECTX_FOR_FOLDED_UPDATE_SOURCE_SNIPPET [=[for (int i = 0; i < 8; i = i + (3)) {
    float x = values[i];
    values[i] = x + 1.0;]=])
add_test(NAME cglc_build_directx_for_folded_update_source_package
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_FOR_FOLDED_UPDATE_COMPUTE_SHADER}
    -DTARGET=directx
    -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-directx-for-folded-update-source.cglb
    -DMODE=source-package-build
    -DEXPECTED_SOURCE=backend/directx/ForFoldedUpdateComputeShader.hlsl
    "-DEXPECTED_SOURCE_SNIPPET=${CROSSGL_DIRECTX_FOR_FOLDED_UPDATE_SOURCE_SNIPPET}"
    "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=directx|module=ForFoldedUpdateComputeShader|nativeBinary=backend/directx/ForFoldedUpdateComputeShader.dxil|workgroupSizes.0.x=1"
    "-DEXPECTED_REFLECTION_JSON_ARRAY_LENGTHS=resources=1|targetResourceBindings=1"
    "-DEXPECTED_REFLECTION_TARGET_FIELDS=values.sourceType=float*|values.hlslType=RWStructuredBuffer<float>|values.bindingClass=uav|values.descriptorType=UAV|values.argumentIndex=0"
    "-DEXPECTED_REFLECTION_FEATURE_FIELDS=structured-loop.kind=controlFlow|storage-buffer.kind=resource|storage-buffer-read.kind=operation|storage-buffer-write.kind=operation|scalar-arithmetic.kind=operation"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_build_opengl_for_folded_update_source_package
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_FOR_FOLDED_UPDATE_COMPUTE_SHADER}
    -DTARGET=opengl
    -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-opengl-for-folded-update-source.cglb
    -DMODE=source-package-build
    -DEXPECTED_SOURCE=backend/opengl/ForFoldedUpdateComputeShader.comp.glsl
    "-DEXPECTED_SOURCE_SNIPPET=for (int i = 0; i < 8; i = i + (3))"
    "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=opengl|module=ForFoldedUpdateComputeShader"
    "-DEXPECTED_REFLECTION_JSON_ARRAY_LENGTHS=resources=1|targetResourceBindings=1"
    "-DEXPECTED_REFLECTION_TARGET_FIELDS=${CROSSGL_OPENGL_LOOP_REFLECTION_TARGET_FIELDS}"
    "-DEXPECTED_REFLECTION_FEATURE_FIELDS=${CROSSGL_OPENGL_LOOP_REFLECTION_FEATURE_FIELDS}"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_build_directx_texture_sampler_lod_source_package
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_VULKAN_TEXTURE_SAMPLER_LOD_SHADER}
    -DTARGET=directx
    -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-directx-texture-sampler-lod-source.cglb
    -DMODE=source-package-build
    -DEXPECTED_SOURCE=backend/directx/VulkanTextureSamplerLodShader.hlsl
    "-DEXPECTED_SOURCE_SNIPPET=SampleLevel(comparisonSampler"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_build_opengl_texture_sampler_lod_source_package
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_VULKAN_TEXTURE_SAMPLER_LOD_SHADER}
    -DTARGET=opengl
    -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-opengl-texture-sampler-lod-source.cglb
    -DMODE=source-package-build
    -DEXPECTED_SOURCE=backend/opengl/VulkanTextureSamplerLodShader.comp.glsl
    "-DEXPECTED_SOURCE_SNIPPET=textureLod(sampler2D(shadowMap, comparisonSampler)"
    "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=opengl|module=VulkanTextureSamplerLodShader"
    "-DEXPECTED_REFLECTION_TARGET_FIELDS=shadowMap.sourceType=sampler2D|shadowMap.bindingClass=texture|shadowMap.argumentIndex=2|comparisonSampler.sourceType=sampler|comparisonSampler.bindingClass=sampler|values.storageBufferLayout.layout=std430"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_build_directx_integer_texture_sampler_lod_source_package
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_VULKAN_INTEGER_TEXTURE_SAMPLER_LOD_SHADER}
    -DTARGET=directx
    -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-directx-integer-texture-sampler-lod-source.cglb
    -DMODE=source-package-build
    -DEXPECTED_SOURCE=backend/directx/VulkanIntegerTextureSamplerLodShader.hlsl
    "-DEXPECTED_SOURCE_SNIPPET=Texture2D<int4> labelMap"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_build_opengl_integer_texture_sampler_lod_source_package
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_VULKAN_INTEGER_TEXTURE_SAMPLER_LOD_SHADER}
    -DTARGET=opengl
    -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-opengl-integer-texture-sampler-lod-source.cglb
    -DMODE=source-package-build
    -DEXPECTED_SOURCE=backend/opengl/VulkanIntegerTextureSamplerLodShader.comp.glsl
    "-DEXPECTED_SOURCE_SNIPPET=textureLod(isampler2D(labelMap, labelSampler)"
    "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=opengl|module=VulkanIntegerTextureSamplerLodShader"
    "-DEXPECTED_REFLECTION_TARGET_FIELDS=labelMap.sourceType=isampler2D|labelMap.bindingClass=texture|maskMap.sourceType=usamplerCube|maskMap.bindingClass=texture|labelSampler.bindingClass=sampler|maskSampler.bindingClass=sampler|values.storageBufferLayout.layout=std430|masks.storageBufferLayout.layout=std430"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
set(CROSSGL_OPENGL_STRUCT_STORAGE_FEATURE_FIELDS
    "glsl-lowering.kind=backend|compute-kernel.kind=stage|workgroup-size.kind=execution|storage-buffer.kind=resource|index-access.kind=operation|local-declaration.kind=operation|storage-buffer-read.kind=operation|storage-buffer-write.kind=operation")
set(CROSSGL_OPENGL_STRUCT_STORAGE_VECTOR_FEATURE_FIELDS
    "${CROSSGL_OPENGL_STRUCT_STORAGE_FEATURE_FIELDS}|vector-arithmetic.kind=operation|vector-constructor.kind=operation")
set(CROSSGL_OPENGL_STRUCT_STORAGE_AGGREGATE_ARRAY_FIELD_FEATURE_FIELDS
    "${CROSSGL_OPENGL_STRUCT_STORAGE_FEATURE_FIELDS}|fixed-array.kind=layout|fixed-array-field.kind=layout")
set(CROSSGL_OPENGL_STRUCT_STORAGE_ARRAY_FIELD_FEATURE_FIELDS
    "${CROSSGL_OPENGL_STRUCT_STORAGE_AGGREGATE_ARRAY_FIELD_FEATURE_FIELDS}|scalar-vector-elements.kind=array")
set(CROSSGL_OPENGL_STRUCT_STORAGE_DESCRIPTOR_ARRAY_FEATURE_FIELDS
    "${CROSSGL_OPENGL_STRUCT_STORAGE_FEATURE_FIELDS}|descriptor-array.kind=resource|fixed-array.kind=layout")
set(CROSSGL_OPENGL_RUNTIME_STRUCT_ARRAY_FEATURE_FIELDS
    "${CROSSGL_OPENGL_STRUCT_STORAGE_VECTOR_FEATURE_FIELDS}|runtime-array.kind=layout|runtime-array-field.kind=layout|scalar-arithmetic.kind=operation")
set(CROSSGL_OPENGL_STRUCT_STORAGE_VALIDATED_FEATURE_FIELDS
    "native-glsl-package.kind=backend|glsl-program-validation.kind=validation|compute-kernel.kind=stage|workgroup-size.kind=execution|storage-buffer.kind=resource|index-access.kind=operation|local-declaration.kind=operation|storage-buffer-read.kind=operation|storage-buffer-write.kind=operation")
set(CROSSGL_OPENGL_STRUCT_STORAGE_VECTOR_VALIDATED_FEATURE_FIELDS
    "${CROSSGL_OPENGL_STRUCT_STORAGE_VALIDATED_FEATURE_FIELDS}|vector-arithmetic.kind=operation|vector-constructor.kind=operation")
set(CROSSGL_OPENGL_STRUCT_STORAGE_AGGREGATE_ARRAY_FIELD_VALIDATED_FEATURE_FIELDS
    "${CROSSGL_OPENGL_STRUCT_STORAGE_VALIDATED_FEATURE_FIELDS}|fixed-array.kind=layout|fixed-array-field.kind=layout")
set(CROSSGL_OPENGL_STRUCT_STORAGE_ARRAY_FIELD_VALIDATED_FEATURE_FIELDS
    "${CROSSGL_OPENGL_STRUCT_STORAGE_AGGREGATE_ARRAY_FIELD_VALIDATED_FEATURE_FIELDS}|scalar-vector-elements.kind=array")
set(CROSSGL_OPENGL_STRUCT_STORAGE_DESCRIPTOR_ARRAY_VALIDATED_FEATURE_FIELDS
    "${CROSSGL_OPENGL_STRUCT_STORAGE_VALIDATED_FEATURE_FIELDS}|descriptor-array.kind=resource|fixed-array.kind=layout")
set(CROSSGL_OPENGL_RUNTIME_STRUCT_ARRAY_VALIDATED_FEATURE_FIELDS
    "${CROSSGL_OPENGL_STRUCT_STORAGE_VECTOR_VALIDATED_FEATURE_FIELDS}|runtime-array.kind=layout|runtime-array-field.kind=layout|scalar-arithmetic.kind=operation")
if(CROSSGL_HAS_OPENGL_NATIVE_VALIDATOR)
  add_test(NAME cglc_build_opengl_storage_buffer_glsl_validated
    COMMAND ${CMAKE_COMMAND}
      -DCGLC=$<TARGET_FILE:cglc>
      -DINPUT=${CROSSGL_STORAGE_BUFFER_COMPUTE_SHADER}
      -DTARGET=opengl
      -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-opengl-storage-buffer-validated.cglb
      -DMODE=source-package-build
      -DEXPECTED_SOURCE=backend/opengl/StorageBufferComputeShader.comp.glsl
      -DEXPECTED_SOURCE_SNIPPET=std430
      -DEXPECTED_NATIVE_BINARY=backend/opengl/StorageBufferComputeShader.glsl
      -DEXPECTED_NATIVE_BINARY_STATUS=validated
      -DEXPECTED_DIAGNOSTIC=opengl.glsl-validated
      "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=opengl|module=StorageBufferComputeShader"
      "-DEXPECTED_REFLECTION_TARGET_FIELDS=values.sourceType=float*|values.bindingClass=storage-buffer|values.argumentIndex=0|values.storageBufferLayout.layout=std430"
      -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
  add_test(NAME cglc_build_opengl_workgroup_shared_glsl_validated
    COMMAND ${CMAKE_COMMAND}
      -DCGLC=$<TARGET_FILE:cglc>
      -DINPUT=${CMAKE_CURRENT_SOURCE_DIR}/tests/opengl/fixtures/OpenGLWorkgroupSharedMemoryShader.cgl
      -DTARGET=opengl
      -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-opengl-workgroup-shared-validated.cglb
      -DMODE=source-package-build
      -DEXPECTED_SOURCE=backend/opengl/OpenGLWorkgroupSharedMemoryShader.comp.glsl
      "-DEXPECTED_SOURCE_SNIPPET=${CROSSGL_OPENGL_WORKGROUP_SHARED_SOURCE_SNIPPET}"
      -DEXPECTED_NATIVE_BINARY=backend/opengl/OpenGLWorkgroupSharedMemoryShader.glsl
      -DEXPECTED_NATIVE_BINARY_STATUS=validated
      -DEXPECTED_DIAGNOSTIC=opengl.glsl-validated
      "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=opengl|module=OpenGLWorkgroupSharedMemoryShader|nativeBinary=backend/opengl/OpenGLWorkgroupSharedMemoryShader.glsl|resources.0.name=tile|resources.0.kind=shared|resources.0.addressSpace=shared|workgroupSizes.0.entryPoint=compute_main|workgroupSizes.0.x=8|workgroupSizes.0.y=2|workgroupSizes.0.z=1"
      "-DEXPECTED_REFLECTION_JSON_ARRAY_LENGTHS=resources=1|targetResourceBindings=1|workgroupSizes=1"
      "-DEXPECTED_REFLECTION_TARGET_FIELDS=tile.sourceType=float[TILE_SIZE]|tile.addressSpace=shared|tile.abi=workgroupLocal|tile.bindingClass=shared|tile.arraySize=TILE_SIZE|tile.arrayElementCount=8"
      "-DEXPECTED_REFLECTION_FEATURE_FIELDS=${CROSSGL_OPENGL_WORKGROUP_SHARED_VALIDATED_FEATURE_FIELDS}"
      -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
  add_test(NAME cglc_build_opengl_workgroup_barrier_glsl_validated
    COMMAND ${CMAKE_COMMAND}
      -DCGLC=$<TARGET_FILE:cglc>
      -DINPUT=${CMAKE_CURRENT_SOURCE_DIR}/tests/opengl/fixtures/OpenGLWorkgroupBarrierShader.cgl
      -DTARGET=opengl
      -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-opengl-workgroup-barrier-validated.cglb
      -DMODE=source-package-build
      -DEXPECTED_SOURCE=backend/opengl/OpenGLWorkgroupBarrierShader.comp.glsl
      "-DEXPECTED_SOURCE_SNIPPET=${CROSSGL_OPENGL_WORKGROUP_BARRIER_SOURCE_SNIPPET}"
      -DEXPECTED_NATIVE_BINARY=backend/opengl/OpenGLWorkgroupBarrierShader.glsl
      -DEXPECTED_NATIVE_BINARY_STATUS=validated
      -DEXPECTED_DIAGNOSTIC=opengl.glsl-validated
      "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=opengl|module=OpenGLWorkgroupBarrierShader|nativeBinary=backend/opengl/OpenGLWorkgroupBarrierShader.glsl|resources.0.name=tile|resources.0.kind=shared|resources.0.addressSpace=shared|workgroupSizes.0.entryPoint=compute_main|workgroupSizes.0.x=4|workgroupSizes.0.y=1|workgroupSizes.0.z=1"
      "-DEXPECTED_REFLECTION_JSON_ARRAY_LENGTHS=resources=1|targetResourceBindings=1|workgroupSizes=1"
      "-DEXPECTED_REFLECTION_TARGET_FIELDS=tile.sourceType=float[4]|tile.addressSpace=shared|tile.abi=workgroupLocal|tile.bindingClass=shared|tile.arraySize=4|tile.arrayElementCount=4"
      "-DEXPECTED_REFLECTION_FEATURE_FIELDS=${CROSSGL_OPENGL_WORKGROUP_BARRIER_VALIDATED_FEATURE_FIELDS}"
      -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
  add_test(NAME cglc_build_opengl_compute_invocation_builtin_glsl_validated
    COMMAND ${CMAKE_COMMAND}
      -DCGLC=$<TARGET_FILE:cglc>
      -DINPUT=${CMAKE_CURRENT_SOURCE_DIR}/tests/opengl/fixtures/OpenGLComputeInvocationBuiltinShader.cgl
      -DTARGET=opengl
      -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-opengl-compute-invocation-builtin-validated.cglb
      -DMODE=source-package-build
      -DEXPECTED_SOURCE=backend/opengl/OpenGLComputeInvocationBuiltinShader.comp.glsl
      "-DEXPECTED_SOURCE_SNIPPET=${CROSSGL_OPENGL_COMPUTE_INVOCATION_BUILTIN_SOURCE_SNIPPET}"
      -DEXPECTED_NATIVE_BINARY=backend/opengl/OpenGLComputeInvocationBuiltinShader.glsl
      -DEXPECTED_NATIVE_BINARY_STATUS=validated
      -DEXPECTED_DIAGNOSTIC=opengl.glsl-validated
      "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=opengl|module=OpenGLComputeInvocationBuiltinShader|nativeBinary=backend/opengl/OpenGLComputeInvocationBuiltinShader.glsl|resources.0.name=values|resources.0.kind=buffer|resources.0.type=uint*|resources.0.binding=0|workgroupSizes.0.entryPoint=compute_main|workgroupSizes.0.x=4|workgroupSizes.0.y=2|workgroupSizes.0.z=1|workgroupSizes.0.sourceX=4|workgroupSizes.0.sourceY=2|workgroupSizes.0.sourceZ=1"
      "-DEXPECTED_REFLECTION_JSON_ARRAY_LENGTHS=resources=1|targetResourceBindings=1|workgroupSizes=1"
      "-DEXPECTED_REFLECTION_TARGET_FIELDS=values.sourceType=uint*|values.bindingClass=storage-buffer|values.argumentIndex=0|values.storageBufferLayout.layout=std430|values.storageBufferLayout.elementType=uint|values.storageBufferLayout.arrayStrideBytes=4"
      "-DEXPECTED_REFLECTION_FEATURE_FIELDS=${CROSSGL_OPENGL_COMPUTE_INVOCATION_BUILTIN_VALIDATED_FEATURE_FIELDS}"
      -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
  add_test(NAME cglc_build_opengl_atomic_add_glsl_validated
    COMMAND ${CMAKE_COMMAND}
      -DCGLC=$<TARGET_FILE:cglc>
      -DINPUT=${CMAKE_CURRENT_SOURCE_DIR}/tests/opengl/fixtures/OpenGLAtomicAddShader.cgl
      -DTARGET=opengl
      -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-opengl-atomic-add-validated.cglb
      -DMODE=source-package-build
      -DEXPECTED_SOURCE=backend/opengl/OpenGLAtomicAddShader.comp.glsl
      "-DEXPECTED_SOURCE_SNIPPET=${CROSSGL_OPENGL_ATOMIC_ADD_SOURCE_SNIPPET}"
      -DEXPECTED_NATIVE_BINARY=backend/opengl/OpenGLAtomicAddShader.glsl
      -DEXPECTED_NATIVE_BINARY_STATUS=validated
      -DEXPECTED_DIAGNOSTIC=opengl.glsl-validated
      "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=opengl|module=OpenGLAtomicAddShader|nativeBinary=backend/opengl/OpenGLAtomicAddShader.glsl|functionConstants.0.name=GROUP_SIZE|functionConstants.0.value=4|resources.0.name=counters|resources.0.kind=buffer|resources.0.type=atomic<int>*|resources.0.binding=0|resources.1.name=unsignedCounters|resources.1.kind=buffer|resources.1.type=atomic<uint>*|resources.1.binding=1|resources.2.name=tile|resources.2.kind=shared|resources.2.type=atomic<int>[GROUP_SIZE]|resources.2.addressSpace=shared|resources.3.name=unsignedTile|resources.3.kind=shared|resources.3.type=atomic<uint>[GROUP_SIZE]|resources.3.addressSpace=shared|workgroupSizes.0.entryPoint=compute_main|workgroupSizes.0.x=4|workgroupSizes.0.y=1|workgroupSizes.0.z=1|workgroupSizes.0.sourceX=GROUP_SIZE|workgroupSizes.0.sourceY=1|workgroupSizes.0.sourceZ=1"
      "-DEXPECTED_REFLECTION_JSON_ARRAY_LENGTHS=resources=4|targetResourceBindings=4|functionConstants=1|workgroupSizes=1"
      "-DEXPECTED_REFLECTION_TARGET_FIELDS=counters.sourceType=atomic<int>*|counters.bindingClass=storage-buffer|counters.argumentIndex=0|unsignedCounters.sourceType=atomic<uint>*|unsignedCounters.bindingClass=storage-buffer|unsignedCounters.argumentIndex=1|tile.sourceType=atomic<int>[GROUP_SIZE]|tile.addressSpace=shared|tile.abi=workgroupLocal|tile.bindingClass=shared|tile.arraySize=GROUP_SIZE|tile.arrayElementCount=4|unsignedTile.sourceType=atomic<uint>[GROUP_SIZE]|unsignedTile.addressSpace=shared|unsignedTile.abi=workgroupLocal|unsignedTile.bindingClass=shared|unsignedTile.arraySize=GROUP_SIZE|unsignedTile.arrayElementCount=4"
      "-DEXPECTED_REFLECTION_FEATURE_FIELDS=${CROSSGL_OPENGL_ATOMIC_ADD_VALIDATED_FEATURE_FIELDS}"
      -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
  add_test(NAME cglc_build_opengl_atomic_add_return_glsl_validated
    COMMAND ${CMAKE_COMMAND}
      -DCGLC=$<TARGET_FILE:cglc>
      -DINPUT=${CMAKE_CURRENT_SOURCE_DIR}/tests/opengl/fixtures/OpenGLAtomicAddReturnShader.cgl
      -DTARGET=opengl
      -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-opengl-atomic-add-return-validated.cglb
      -DMODE=source-package-build
      -DEXPECTED_SOURCE=backend/opengl/OpenGLAtomicAddReturnShader.comp.glsl
      "-DEXPECTED_SOURCE_SNIPPET=${CROSSGL_OPENGL_ATOMIC_ADD_RETURN_SOURCE_SNIPPET}"
      -DEXPECTED_NATIVE_BINARY=backend/opengl/OpenGLAtomicAddReturnShader.glsl
      -DEXPECTED_NATIVE_BINARY_STATUS=validated
      -DEXPECTED_DIAGNOSTIC=opengl.glsl-validated
      "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=opengl|module=OpenGLAtomicAddReturnShader|nativeBinary=backend/opengl/OpenGLAtomicAddReturnShader.glsl|functionConstants.0.name=GROUP_SIZE|functionConstants.0.value=4|resources.0.name=counters|resources.0.kind=buffer|resources.0.type=atomic<int>*|resources.0.binding=0|resources.1.name=unsignedCounters|resources.1.kind=buffer|resources.1.type=atomic<uint>*|resources.1.binding=1|resources.2.name=compatCounters|resources.2.kind=buffer|resources.2.type=CompatCounters*|resources.2.binding=2|resources.3.name=values|resources.3.kind=buffer|resources.3.type=int*|resources.3.binding=3|resources.4.name=unsignedValues|resources.4.kind=buffer|resources.4.type=uint*|resources.4.binding=4|resources.5.name=tile|resources.5.kind=shared|resources.5.type=atomic<int>[GROUP_SIZE]|resources.5.addressSpace=shared|resources.6.name=unsignedTile|resources.6.kind=shared|resources.6.type=atomic<uint>[GROUP_SIZE]|resources.6.addressSpace=shared|workgroupSizes.0.entryPoint=compute_main|workgroupSizes.0.x=4|workgroupSizes.0.y=1|workgroupSizes.0.z=1|workgroupSizes.0.sourceX=GROUP_SIZE|workgroupSizes.0.sourceY=1|workgroupSizes.0.sourceZ=1"
      "-DEXPECTED_REFLECTION_JSON_ARRAY_LENGTHS=resources=7|targetResourceBindings=7|functionConstants=1|workgroupSizes=1"
      "-DEXPECTED_REFLECTION_TARGET_FIELDS=counters.sourceType=atomic<int>*|counters.bindingClass=storage-buffer|counters.argumentIndex=0|unsignedCounters.sourceType=atomic<uint>*|unsignedCounters.bindingClass=storage-buffer|unsignedCounters.argumentIndex=1|compatCounters.sourceType=CompatCounters*|compatCounters.bindingClass=storage-buffer|compatCounters.argumentIndex=2|values.sourceType=int*|values.bindingClass=storage-buffer|values.argumentIndex=3|unsignedValues.sourceType=uint*|unsignedValues.bindingClass=storage-buffer|unsignedValues.argumentIndex=4|tile.sourceType=atomic<int>[GROUP_SIZE]|tile.addressSpace=shared|tile.abi=workgroupLocal|tile.bindingClass=shared|tile.arraySize=GROUP_SIZE|tile.arrayElementCount=4|unsignedTile.sourceType=atomic<uint>[GROUP_SIZE]|unsignedTile.addressSpace=shared|unsignedTile.abi=workgroupLocal|unsignedTile.bindingClass=shared|unsignedTile.arraySize=GROUP_SIZE|unsignedTile.arrayElementCount=4"
      "-DEXPECTED_REFLECTION_FEATURE_FIELDS=${CROSSGL_OPENGL_ATOMIC_ADD_RETURN_VALIDATED_FEATURE_FIELDS}"
      -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
  add_test(NAME cglc_build_opengl_atomic_minmax_return_glsl_validated
    COMMAND ${CMAKE_COMMAND}
      -DCGLC=$<TARGET_FILE:cglc>
      -DINPUT=${CMAKE_CURRENT_SOURCE_DIR}/tests/opengl/fixtures/OpenGLAtomicMinMaxReturnShader.cgl
      -DTARGET=opengl
      -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-opengl-atomic-minmax-return-validated.cglb
      -DMODE=source-package-build
      -DEXPECTED_SOURCE=backend/opengl/OpenGLAtomicMinMaxReturnShader.comp.glsl
      "-DEXPECTED_SOURCE_SNIPPET=${CROSSGL_OPENGL_ATOMIC_MINMAX_RETURN_SOURCE_SNIPPET}"
      -DEXPECTED_NATIVE_BINARY=backend/opengl/OpenGLAtomicMinMaxReturnShader.glsl
      -DEXPECTED_NATIVE_BINARY_STATUS=validated
      -DEXPECTED_DIAGNOSTIC=opengl.glsl-validated
      "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=opengl|module=OpenGLAtomicMinMaxReturnShader|nativeBinary=backend/opengl/OpenGLAtomicMinMaxReturnShader.glsl|functionConstants.0.name=GROUP_SIZE|functionConstants.0.value=4|resources.0.name=counters|resources.0.kind=buffer|resources.0.type=atomic<int>*|resources.0.binding=0|resources.1.name=unsignedCounters|resources.1.kind=buffer|resources.1.type=atomic<uint>*|resources.1.binding=1|resources.2.name=compatCounters|resources.2.kind=buffer|resources.2.type=CompatCounters*|resources.2.binding=2|resources.3.name=values|resources.3.kind=buffer|resources.3.type=int*|resources.3.binding=3|resources.4.name=unsignedValues|resources.4.kind=buffer|resources.4.type=uint*|resources.4.binding=4|resources.5.name=tile|resources.5.kind=shared|resources.5.type=atomic<int>[GROUP_SIZE]|resources.5.addressSpace=shared|resources.6.name=unsignedTile|resources.6.kind=shared|resources.6.type=atomic<uint>[GROUP_SIZE]|resources.6.addressSpace=shared|workgroupSizes.0.entryPoint=compute_main|workgroupSizes.0.x=4|workgroupSizes.0.y=1|workgroupSizes.0.z=1|workgroupSizes.0.sourceX=GROUP_SIZE|workgroupSizes.0.sourceY=1|workgroupSizes.0.sourceZ=1"
      "-DEXPECTED_REFLECTION_JSON_ARRAY_LENGTHS=resources=7|targetResourceBindings=7|functionConstants=1|workgroupSizes=1"
      "-DEXPECTED_REFLECTION_TARGET_FIELDS=counters.sourceType=atomic<int>*|counters.bindingClass=storage-buffer|counters.argumentIndex=0|unsignedCounters.sourceType=atomic<uint>*|unsignedCounters.bindingClass=storage-buffer|unsignedCounters.argumentIndex=1|compatCounters.sourceType=CompatCounters*|compatCounters.bindingClass=storage-buffer|compatCounters.argumentIndex=2|values.sourceType=int*|values.bindingClass=storage-buffer|values.argumentIndex=3|unsignedValues.sourceType=uint*|unsignedValues.bindingClass=storage-buffer|unsignedValues.argumentIndex=4|tile.sourceType=atomic<int>[GROUP_SIZE]|tile.addressSpace=shared|tile.abi=workgroupLocal|tile.bindingClass=shared|tile.arraySize=GROUP_SIZE|tile.arrayElementCount=4|unsignedTile.sourceType=atomic<uint>[GROUP_SIZE]|unsignedTile.addressSpace=shared|unsignedTile.abi=workgroupLocal|unsignedTile.bindingClass=shared|unsignedTile.arraySize=GROUP_SIZE|unsignedTile.arrayElementCount=4"
      "-DEXPECTED_REFLECTION_FEATURE_FIELDS=${CROSSGL_OPENGL_ATOMIC_MINMAX_RETURN_VALIDATED_FEATURE_FIELDS}"
      -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
  add_test(NAME cglc_build_opengl_atomic_exchange_return_glsl_validated
    COMMAND ${CMAKE_COMMAND}
      -DCGLC=$<TARGET_FILE:cglc>
      -DINPUT=${CMAKE_CURRENT_SOURCE_DIR}/tests/opengl/fixtures/OpenGLAtomicExchangeReturnShader.cgl
      -DTARGET=opengl
      -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-opengl-atomic-exchange-return-validated.cglb
      -DMODE=source-package-build
      -DEXPECTED_SOURCE=backend/opengl/OpenGLAtomicExchangeReturnShader.comp.glsl
      "-DEXPECTED_SOURCE_SNIPPET=${CROSSGL_OPENGL_ATOMIC_EXCHANGE_RETURN_SOURCE_SNIPPET}"
      -DEXPECTED_NATIVE_BINARY=backend/opengl/OpenGLAtomicExchangeReturnShader.glsl
      -DEXPECTED_NATIVE_BINARY_STATUS=validated
      -DEXPECTED_DIAGNOSTIC=opengl.glsl-validated
      "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=opengl|module=OpenGLAtomicExchangeReturnShader|nativeBinary=backend/opengl/OpenGLAtomicExchangeReturnShader.glsl|functionConstants.0.name=GROUP_SIZE|functionConstants.0.value=4|resources.0.name=counters|resources.0.kind=buffer|resources.0.type=atomic<int>*|resources.0.binding=0|resources.1.name=unsignedCounters|resources.1.kind=buffer|resources.1.type=atomic<uint>*|resources.1.binding=1|resources.2.name=compatCounters|resources.2.kind=buffer|resources.2.type=CompatCounters*|resources.2.binding=2|resources.3.name=values|resources.3.kind=buffer|resources.3.type=int*|resources.3.binding=3|resources.4.name=unsignedValues|resources.4.kind=buffer|resources.4.type=uint*|resources.4.binding=4|resources.5.name=tile|resources.5.kind=shared|resources.5.type=atomic<int>[GROUP_SIZE]|resources.5.addressSpace=shared|resources.6.name=unsignedTile|resources.6.kind=shared|resources.6.type=atomic<uint>[GROUP_SIZE]|resources.6.addressSpace=shared|workgroupSizes.0.entryPoint=compute_main|workgroupSizes.0.x=4|workgroupSizes.0.y=1|workgroupSizes.0.z=1|workgroupSizes.0.sourceX=GROUP_SIZE|workgroupSizes.0.sourceY=1|workgroupSizes.0.sourceZ=1"
      "-DEXPECTED_REFLECTION_JSON_ARRAY_LENGTHS=resources=7|targetResourceBindings=7|functionConstants=1|workgroupSizes=1"
      "-DEXPECTED_REFLECTION_TARGET_FIELDS=counters.sourceType=atomic<int>*|counters.bindingClass=storage-buffer|counters.argumentIndex=0|unsignedCounters.sourceType=atomic<uint>*|unsignedCounters.bindingClass=storage-buffer|unsignedCounters.argumentIndex=1|compatCounters.sourceType=CompatCounters*|compatCounters.bindingClass=storage-buffer|compatCounters.argumentIndex=2|values.sourceType=int*|values.bindingClass=storage-buffer|values.argumentIndex=3|unsignedValues.sourceType=uint*|unsignedValues.bindingClass=storage-buffer|unsignedValues.argumentIndex=4|tile.sourceType=atomic<int>[GROUP_SIZE]|tile.addressSpace=shared|tile.abi=workgroupLocal|tile.bindingClass=shared|tile.arraySize=GROUP_SIZE|tile.arrayElementCount=4|unsignedTile.sourceType=atomic<uint>[GROUP_SIZE]|unsignedTile.addressSpace=shared|unsignedTile.abi=workgroupLocal|unsignedTile.bindingClass=shared|unsignedTile.arraySize=GROUP_SIZE|unsignedTile.arrayElementCount=4"
      "-DEXPECTED_REFLECTION_FEATURE_FIELDS=${CROSSGL_OPENGL_ATOMIC_EXCHANGE_RETURN_VALIDATED_FEATURE_FIELDS}"
      -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
  add_test(NAME cglc_build_opengl_atomic_bitwise_return_glsl_validated
    COMMAND ${CMAKE_COMMAND}
      -DCGLC=$<TARGET_FILE:cglc>
      -DINPUT=${CMAKE_CURRENT_SOURCE_DIR}/tests/opengl/fixtures/OpenGLAtomicBitwiseReturnShader.cgl
      -DTARGET=opengl
      -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-opengl-atomic-bitwise-return-validated.cglb
      -DMODE=source-package-build
      -DEXPECTED_SOURCE=backend/opengl/OpenGLAtomicBitwiseReturnShader.comp.glsl
      "-DEXPECTED_SOURCE_SNIPPET=${CROSSGL_OPENGL_ATOMIC_BITWISE_RETURN_SOURCE_SNIPPET}"
      -DEXPECTED_NATIVE_BINARY=backend/opengl/OpenGLAtomicBitwiseReturnShader.glsl
      -DEXPECTED_NATIVE_BINARY_STATUS=validated
      -DEXPECTED_DIAGNOSTIC=opengl.glsl-validated
      "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=opengl|module=OpenGLAtomicBitwiseReturnShader|nativeBinary=backend/opengl/OpenGLAtomicBitwiseReturnShader.glsl|functionConstants.0.name=GROUP_SIZE|functionConstants.0.value=4|resources.0.name=counters|resources.0.kind=buffer|resources.0.type=atomic<int>*|resources.0.binding=0|resources.1.name=unsignedCounters|resources.1.kind=buffer|resources.1.type=atomic<uint>*|resources.1.binding=1|resources.2.name=compatCounters|resources.2.kind=buffer|resources.2.type=CompatCounters*|resources.2.binding=2|resources.3.name=values|resources.3.kind=buffer|resources.3.type=int*|resources.3.binding=3|resources.4.name=unsignedValues|resources.4.kind=buffer|resources.4.type=uint*|resources.4.binding=4|resources.5.name=tile|resources.5.kind=shared|resources.5.type=atomic<int>[GROUP_SIZE]|resources.5.addressSpace=shared|resources.6.name=unsignedTile|resources.6.kind=shared|resources.6.type=atomic<uint>[GROUP_SIZE]|resources.6.addressSpace=shared|workgroupSizes.0.entryPoint=compute_main|workgroupSizes.0.x=4|workgroupSizes.0.y=1|workgroupSizes.0.z=1|workgroupSizes.0.sourceX=GROUP_SIZE|workgroupSizes.0.sourceY=1|workgroupSizes.0.sourceZ=1"
      "-DEXPECTED_REFLECTION_JSON_ARRAY_LENGTHS=resources=7|targetResourceBindings=7|functionConstants=1|workgroupSizes=1"
      "-DEXPECTED_REFLECTION_TARGET_FIELDS=counters.sourceType=atomic<int>*|counters.bindingClass=storage-buffer|counters.argumentIndex=0|unsignedCounters.sourceType=atomic<uint>*|unsignedCounters.bindingClass=storage-buffer|unsignedCounters.argumentIndex=1|compatCounters.sourceType=CompatCounters*|compatCounters.bindingClass=storage-buffer|compatCounters.argumentIndex=2|values.sourceType=int*|values.bindingClass=storage-buffer|values.argumentIndex=3|unsignedValues.sourceType=uint*|unsignedValues.bindingClass=storage-buffer|unsignedValues.argumentIndex=4|tile.sourceType=atomic<int>[GROUP_SIZE]|tile.addressSpace=shared|tile.abi=workgroupLocal|tile.bindingClass=shared|tile.arraySize=GROUP_SIZE|tile.arrayElementCount=4|unsignedTile.sourceType=atomic<uint>[GROUP_SIZE]|unsignedTile.addressSpace=shared|unsignedTile.abi=workgroupLocal|unsignedTile.bindingClass=shared|unsignedTile.arraySize=GROUP_SIZE|unsignedTile.arrayElementCount=4"
      "-DEXPECTED_REFLECTION_FEATURE_FIELDS=${CROSSGL_OPENGL_ATOMIC_BITWISE_RETURN_VALIDATED_FEATURE_FIELDS}"
      -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
  add_test(NAME cglc_build_opengl_function_parameter_array_glsl_validated
    COMMAND ${CMAKE_COMMAND}
      -DCGLC=$<TARGET_FILE:cglc>
      -DINPUT=${CROSSGL_OPENGL_FUNCTION_PARAMETER_ARRAY_SHADER}
      -DTARGET=opengl
      -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-opengl-function-parameter-array-validated.cglb
      -DMODE=source-package-build
      -DEXPECTED_SOURCE=backend/opengl/OpenGLFunctionParameterArrayShader.comp.glsl
      "-DEXPECTED_SOURCE_SNIPPET=void relayVelocity(vec3 velocities[COUNT])"
      -DEXPECTED_NATIVE_BINARY=backend/opengl/OpenGLFunctionParameterArrayShader.glsl
      -DEXPECTED_NATIVE_BINARY_STATUS=validated
      -DEXPECTED_DIAGNOSTIC=opengl.glsl-validated
      "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=opengl|module=OpenGLFunctionParameterArrayShader"
      "-DEXPECTED_REFLECTION_TARGET_FIELDS=particles.sourceType=Particle*|particles.bindingClass=storage-buffer|particles.argumentIndex=0|particles.storageBufferLayout.elementType=Particle|particles.storageBufferLayout.arrayStrideBytes=48|particles.storageBufferLayout.layout=std430|particles.storageBufferLayout.fields.0.name=weights|particles.storageBufferLayout.fields.0.arrayElementCount=2|particles.storageBufferLayout.fields.1.name=velocities|particles.storageBufferLayout.fields.1.arrayStrideBytes=16"
      "-DEXPECTED_REFLECTION_FEATURE_FIELDS=${CROSSGL_OPENGL_PARAM_ARRAY_VALIDATED_RESOURCE_FEATURE_FIELDS}"
      -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
  add_test(NAME cglc_build_opengl_local_function_parameter_array_glsl_validated
    COMMAND ${CMAKE_COMMAND}
      -DCGLC=$<TARGET_FILE:cglc>
      -DINPUT=${CROSSGL_OPENGL_LOCAL_FUNCTION_PARAMETER_ARRAY_SHADER}
      -DTARGET=opengl
      -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-opengl-local-function-parameter-array-validated.cglb
      -DMODE=source-package-build
      -DEXPECTED_SOURCE=backend/opengl/OpenGLLocalFunctionParameterArrayShader.comp.glsl
      "-DEXPECTED_SOURCE_SNIPPET=float first = readWeight(weights, 1);"
      -DEXPECTED_NATIVE_BINARY=backend/opengl/OpenGLLocalFunctionParameterArrayShader.glsl
      -DEXPECTED_NATIVE_BINARY_STATUS=validated
      -DEXPECTED_DIAGNOSTIC=opengl.glsl-validated
      "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=opengl|module=OpenGLLocalFunctionParameterArrayShader"
      "-DEXPECTED_REFLECTION_FEATURE_FIELDS=${CROSSGL_OPENGL_PARAM_ARRAY_VALIDATED_LOCAL_FEATURE_FIELDS}"
      -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
  add_test(NAME cglc_build_opengl_folded_local_function_parameter_array_glsl_validated
    COMMAND ${CMAKE_COMMAND}
      -DCGLC=$<TARGET_FILE:cglc>
      -DINPUT=${CROSSGL_OPENGL_FOLDED_LOCAL_FUNCTION_PARAMETER_ARRAY_SHADER}
      -DTARGET=opengl
      -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-opengl-folded-local-function-parameter-array-validated.cglb
      -DMODE=source-package-build
      -DEXPECTED_SOURCE=backend/opengl/OpenGLFoldedLocalFunctionParameterArrayShader.comp.glsl
      "-DEXPECTED_SOURCE_SNIPPET=float sampled = sampleWeight(weights, 2);"
      -DEXPECTED_NATIVE_BINARY=backend/opengl/OpenGLFoldedLocalFunctionParameterArrayShader.glsl
      -DEXPECTED_NATIVE_BINARY_STATUS=validated
      -DEXPECTED_DIAGNOSTIC=opengl.glsl-validated
      "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=opengl|module=OpenGLFoldedLocalFunctionParameterArrayShader"
      "-DEXPECTED_REFLECTION_FEATURE_FIELDS=${CROSSGL_OPENGL_PARAM_ARRAY_VALIDATED_LOCAL_FEATURE_FIELDS}"
      -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
  add_test(NAME cglc_build_opengl_nested_local_function_parameter_array_glsl_validated
    COMMAND ${CMAKE_COMMAND}
      -DCGLC=$<TARGET_FILE:cglc>
      -DINPUT=${CROSSGL_OPENGL_NESTED_LOCAL_FUNCTION_PARAMETER_ARRAY_SHADER}
      -DTARGET=opengl
      -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-opengl-nested-local-function-parameter-array-validated.cglb
      -DMODE=source-package-build
      -DEXPECTED_SOURCE=backend/opengl/OpenGLNestedLocalFunctionParameterArrayShader.comp.glsl
      "-DEXPECTED_SOURCE_SNIPPET=float selected = readGrid(grid);"
      -DEXPECTED_NATIVE_BINARY=backend/opengl/OpenGLNestedLocalFunctionParameterArrayShader.glsl
      -DEXPECTED_NATIVE_BINARY_STATUS=validated
      -DEXPECTED_DIAGNOSTIC=opengl.glsl-validated
      "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=opengl|module=OpenGLNestedLocalFunctionParameterArrayShader"
      "-DEXPECTED_REFLECTION_FEATURE_FIELDS=${CROSSGL_OPENGL_PARAM_ARRAY_VALIDATED_LOCAL_FEATURE_FIELDS}"
      -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
  add_test(NAME cglc_build_opengl_dynamic_nested_local_function_parameter_array_glsl_validated
    COMMAND ${CMAKE_COMMAND}
      -DCGLC=$<TARGET_FILE:cglc>
      -DINPUT=${CROSSGL_OPENGL_DYNAMIC_NESTED_LOCAL_FUNCTION_PARAMETER_ARRAY_UNSUPPORTED_SHADER}
      -DTARGET=opengl
      -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-opengl-dynamic-nested-local-function-parameter-array-validated.cglb
      -DMODE=source-package-build
      -DEXPECTED_SOURCE=backend/opengl/OpenGLDynamicNestedLocalFunctionParameterArrayUnsupportedShader.comp.glsl
      "-DEXPECTED_SOURCE_SNIPPET=return grid[row][2];"
      -DEXPECTED_NATIVE_BINARY=backend/opengl/OpenGLDynamicNestedLocalFunctionParameterArrayUnsupportedShader.glsl
      -DEXPECTED_NATIVE_BINARY_STATUS=validated
      -DEXPECTED_DIAGNOSTIC=opengl.glsl-validated
      "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=opengl|module=OpenGLDynamicNestedLocalFunctionParameterArrayUnsupportedShader"
      "-DEXPECTED_REFLECTION_TARGET_FIELDS=values.sourceType=float*|values.bindingClass=storage-buffer|values.argumentIndex=0|values.storageBufferLayout.elementType=float|values.storageBufferLayout.arrayStrideBytes=4|values.storageBufferLayout.layout=std430"
      "-DEXPECTED_REFLECTION_FEATURE_FIELDS=${CROSSGL_OPENGL_PARAM_ARRAY_VALIDATED_DYNAMIC_FEATURE_FIELDS}"
      -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
  add_test(NAME cglc_build_opengl_local_function_parameter_array_write_glsl_validated
    COMMAND ${CMAKE_COMMAND}
      -DCGLC=$<TARGET_FILE:cglc>
      -DINPUT=${CROSSGL_OPENGL_LOCAL_FUNCTION_PARAMETER_ARRAY_WRITE_SHADER}
      -DTARGET=opengl
      -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-opengl-local-function-parameter-array-write-validated.cglb
      -DMODE=source-package-build
      -DEXPECTED_SOURCE=backend/opengl/OpenGLLocalFunctionParameterArrayWriteShader.comp.glsl
      "-DEXPECTED_SOURCE_SNIPPET=values[1] = rewriteLocal(weights, 1);"
      -DEXPECTED_NATIVE_BINARY=backend/opengl/OpenGLLocalFunctionParameterArrayWriteShader.glsl
      -DEXPECTED_NATIVE_BINARY_STATUS=validated
      -DEXPECTED_DIAGNOSTIC=opengl.glsl-validated
      "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=opengl|module=OpenGLLocalFunctionParameterArrayWriteShader|nativeBinary=backend/opengl/OpenGLLocalFunctionParameterArrayWriteShader.glsl|functionConstants.0.name=COUNT|functionConstants.0.value=3|resources.0.name=values|resources.0.kind=buffer|resources.0.type=float*|resources.0.binding=0|workgroupSizes.0.entryPoint=compute_main|workgroupSizes.0.x=1|workgroupSizes.0.y=1|workgroupSizes.0.z=1"
      "-DEXPECTED_REFLECTION_TARGET_FIELDS=values.sourceType=float*|values.bindingClass=storage-buffer|values.argumentIndex=0|values.storageBufferLayout.elementType=float|values.storageBufferLayout.arrayStrideBytes=4|values.storageBufferLayout.layout=std430"
      "-DEXPECTED_REFLECTION_FEATURE_FIELDS=${CROSSGL_OPENGL_PARAM_ARRAY_VALIDATED_WRITE_LOCAL_FEATURE_FIELDS}"
      -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
  add_test(NAME cglc_build_opengl_nested_function_parameter_array_write_glsl_validated
    COMMAND ${CMAKE_COMMAND}
      -DCGLC=$<TARGET_FILE:cglc>
      -DINPUT=${CROSSGL_OPENGL_NESTED_FUNCTION_PARAMETER_ARRAY_WRITE_UNSUPPORTED_SHADER}
      -DTARGET=opengl
      -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-opengl-nested-function-parameter-array-write-validated.cglb
      -DMODE=source-package-build
      -DEXPECTED_SOURCE=backend/opengl/OpenGLNestedFunctionParameterArrayWriteUnsupportedShader.comp.glsl
      "-DEXPECTED_SOURCE_SNIPPET=grid[1][2] = grid[0][0] + 1.0;"
      -DEXPECTED_NATIVE_BINARY=backend/opengl/OpenGLNestedFunctionParameterArrayWriteUnsupportedShader.glsl
      -DEXPECTED_NATIVE_BINARY_STATUS=validated
      -DEXPECTED_DIAGNOSTIC=opengl.glsl-validated
      "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=opengl|module=OpenGLNestedFunctionParameterArrayWriteUnsupportedShader|nativeBinary=backend/opengl/OpenGLNestedFunctionParameterArrayWriteUnsupportedShader.glsl|functionConstants.0.name=ROWS|functionConstants.0.value=2|functionConstants.1.name=COLS|functionConstants.1.value=3|resources.0.name=values|resources.0.kind=buffer|resources.0.type=float*|resources.0.binding=0|workgroupSizes.0.entryPoint=compute_main|workgroupSizes.0.x=1|workgroupSizes.0.y=1|workgroupSizes.0.z=1"
      "-DEXPECTED_REFLECTION_TARGET_FIELDS=values.sourceType=float*|values.bindingClass=storage-buffer|values.argumentIndex=0|values.storageBufferLayout.elementType=float|values.storageBufferLayout.arrayStrideBytes=4|values.storageBufferLayout.layout=std430"
      "-DEXPECTED_REFLECTION_FEATURE_FIELDS=${CROSSGL_OPENGL_PARAM_ARRAY_VALIDATED_WRITE_LOCAL_FEATURE_FIELDS}"
      -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
  add_test(NAME cglc_build_opengl_struct_buffer_glsl_validated
    COMMAND ${CMAKE_COMMAND}
      -DCGLC=$<TARGET_FILE:cglc>
      -DINPUT=${CROSSGL_STRUCT_BUFFER_COMPUTE_SHADER}
      -DTARGET=opengl
      -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-opengl-struct-buffer-validated.cglb
      -DMODE=source-package-build
      -DEXPECTED_SOURCE=backend/opengl/StructBufferComputeShader.comp.glsl
      "-DEXPECTED_SOURCE_SNIPPET=particles[1].mass = mass + 1.0;"
      -DEXPECTED_NATIVE_BINARY=backend/opengl/StructBufferComputeShader.glsl
      -DEXPECTED_NATIVE_BINARY_STATUS=validated
      -DEXPECTED_DIAGNOSTIC=opengl.glsl-validated
      "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=opengl|module=StructBufferComputeShader|nativeBinary=backend/opengl/StructBufferComputeShader.glsl"
      "-DEXPECTED_REFLECTION_TARGET_FIELDS=particles.sourceType=Particle*|particles.bindingClass=storage-buffer|particles.argumentIndex=0|particles.storageBufferLayout.elementType=Particle|particles.storageBufferLayout.layout=std430|particles.storageBufferLayout.arrayStrideBytes=32"
      "-DEXPECTED_REFLECTION_FEATURE_FIELDS=${CROSSGL_OPENGL_STRUCT_STORAGE_VALIDATED_FEATURE_FIELDS}|scalar-arithmetic.kind=operation"
      -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
  add_test(NAME cglc_build_opengl_struct_vector_buffer_glsl_validated
    COMMAND ${CMAKE_COMMAND}
      -DCGLC=$<TARGET_FILE:cglc>
      -DINPUT=${CROSSGL_STRUCT_VECTOR_BUFFER_COMPUTE_SHADER}
      -DTARGET=opengl
      -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-opengl-struct-vector-buffer-validated.cglb
      -DMODE=source-package-build
      -DEXPECTED_SOURCE=backend/opengl/StructVectorBufferComputeShader.comp.glsl
      "-DEXPECTED_SOURCE_SNIPPET=particles[1].position = lifted;"
      -DEXPECTED_NATIVE_BINARY=backend/opengl/StructVectorBufferComputeShader.glsl
      -DEXPECTED_NATIVE_BINARY_STATUS=validated
      -DEXPECTED_DIAGNOSTIC=opengl.glsl-validated
      "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=opengl|module=StructVectorBufferComputeShader|nativeBinary=backend/opengl/StructVectorBufferComputeShader.glsl"
      "-DEXPECTED_REFLECTION_TARGET_FIELDS=particles.sourceType=Particle*|particles.bindingClass=storage-buffer|particles.argumentIndex=0|particles.storageBufferLayout.elementType=Particle|particles.storageBufferLayout.layout=std430|particles.storageBufferLayout.arrayStrideBytes=32"
      "-DEXPECTED_REFLECTION_FEATURE_FIELDS=${CROSSGL_OPENGL_STRUCT_STORAGE_VECTOR_VALIDATED_FEATURE_FIELDS}"
      -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
  add_test(NAME cglc_build_opengl_struct_nested_field_glsl_validated
    COMMAND ${CMAKE_COMMAND}
      -DCGLC=$<TARGET_FILE:cglc>
      -DINPUT=${CROSSGL_STRUCT_NESTED_FIELD_COMPUTE_SHADER}
      -DTARGET=opengl
      -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-opengl-struct-nested-field-validated.cglb
      -DMODE=source-package-build
      -DEXPECTED_SOURCE=backend/opengl/StructNestedFieldComputeShader.comp.glsl
      "-DEXPECTED_SOURCE_SNIPPET=particles[1].transform.position = lifted;"
      -DEXPECTED_NATIVE_BINARY=backend/opengl/StructNestedFieldComputeShader.glsl
      -DEXPECTED_NATIVE_BINARY_STATUS=validated
      -DEXPECTED_DIAGNOSTIC=opengl.glsl-validated
      "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=opengl|module=StructNestedFieldComputeShader|nativeBinary=backend/opengl/StructNestedFieldComputeShader.glsl"
      "-DEXPECTED_REFLECTION_TARGET_FIELDS=particles.sourceType=Particle*|particles.bindingClass=storage-buffer|particles.argumentIndex=0|particles.storageBufferLayout.elementType=Particle|particles.storageBufferLayout.layout=std430|particles.storageBufferLayout.fields.0.name=transform|particles.storageBufferLayout.fields.0.type=Transform"
      "-DEXPECTED_REFLECTION_FEATURE_FIELDS=${CROSSGL_OPENGL_STRUCT_STORAGE_VECTOR_VALIDATED_FEATURE_FIELDS}"
      -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
  add_test(NAME cglc_build_opengl_struct_array_field_glsl_validated
    COMMAND ${CMAKE_COMMAND}
      -DCGLC=$<TARGET_FILE:cglc>
      -DINPUT=${CROSSGL_STRUCT_ARRAY_FIELD_COMPUTE_SHADER}
      -DTARGET=opengl
      -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-opengl-struct-array-field-validated.cglb
      -DMODE=source-package-build
      -DEXPECTED_SOURCE=backend/opengl/StructArrayFieldComputeShader.comp.glsl
      "-DEXPECTED_SOURCE_SNIPPET=particles[1].mass = firstWeight;"
      -DEXPECTED_NATIVE_BINARY=backend/opengl/StructArrayFieldComputeShader.glsl
      -DEXPECTED_NATIVE_BINARY_STATUS=validated
      -DEXPECTED_DIAGNOSTIC=opengl.glsl-validated
      "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=opengl|module=StructArrayFieldComputeShader|nativeBinary=backend/opengl/StructArrayFieldComputeShader.glsl"
      "-DEXPECTED_REFLECTION_TARGET_FIELDS=particles.sourceType=Particle*|particles.bindingClass=storage-buffer|particles.argumentIndex=0|particles.storageBufferLayout.elementType=Particle|particles.storageBufferLayout.layout=std430|particles.storageBufferLayout.fields.0.name=weights|particles.storageBufferLayout.fields.0.arrayElementCount=4"
      "-DEXPECTED_REFLECTION_FEATURE_FIELDS=${CROSSGL_OPENGL_STRUCT_STORAGE_ARRAY_FIELD_VALIDATED_FEATURE_FIELDS}"
      -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
  add_test(NAME cglc_build_opengl_struct_constant_array_field_glsl_validated
    COMMAND ${CMAKE_COMMAND}
      -DCGLC=$<TARGET_FILE:cglc>
      -DINPUT=${CROSSGL_STRUCT_CONSTANT_ARRAY_FIELD_COMPUTE_SHADER}
      -DTARGET=opengl
      -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-opengl-struct-constant-array-field-validated.cglb
      -DMODE=source-package-build
      -DEXPECTED_SOURCE=backend/opengl/StructConstantArrayFieldComputeShader.comp.glsl
      "-DEXPECTED_SOURCE_SNIPPET=float weights[WEIGHT_COUNT];"
      -DEXPECTED_NATIVE_BINARY=backend/opengl/StructConstantArrayFieldComputeShader.glsl
      -DEXPECTED_NATIVE_BINARY_STATUS=validated
      -DEXPECTED_DIAGNOSTIC=opengl.glsl-validated
      "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=opengl|module=StructConstantArrayFieldComputeShader|nativeBinary=backend/opengl/StructConstantArrayFieldComputeShader.glsl"
      "-DEXPECTED_REFLECTION_TARGET_FIELDS=particles.sourceType=Particle*|particles.bindingClass=storage-buffer|particles.argumentIndex=0|particles.storageBufferLayout.elementType=Particle|particles.storageBufferLayout.layout=std430|particles.storageBufferLayout.fields.0.name=weights|particles.storageBufferLayout.fields.0.arrayDimensions.0.source=WEIGHT_COUNT"
      "-DEXPECTED_REFLECTION_FEATURE_FIELDS=${CROSSGL_OPENGL_STRUCT_STORAGE_ARRAY_FIELD_VALIDATED_FEATURE_FIELDS}"
      -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
  add_test(NAME cglc_build_opengl_struct_vector_array_field_glsl_validated
    COMMAND ${CMAKE_COMMAND}
      -DCGLC=$<TARGET_FILE:cglc>
      -DINPUT=${CROSSGL_STRUCT_VECTOR_ARRAY_FIELD_COMPUTE_SHADER}
      -DTARGET=opengl
      -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-opengl-struct-vector-array-field-validated.cglb
      -DMODE=source-package-build
      -DEXPECTED_SOURCE=backend/opengl/StructVectorArrayFieldComputeShader.comp.glsl
      "-DEXPECTED_SOURCE_SNIPPET=particles[1].positions[0] = lifted;"
      -DEXPECTED_NATIVE_BINARY=backend/opengl/StructVectorArrayFieldComputeShader.glsl
      -DEXPECTED_NATIVE_BINARY_STATUS=validated
      -DEXPECTED_DIAGNOSTIC=opengl.glsl-validated
      "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=opengl|module=StructVectorArrayFieldComputeShader|nativeBinary=backend/opengl/StructVectorArrayFieldComputeShader.glsl"
      "-DEXPECTED_REFLECTION_TARGET_FIELDS=particles.sourceType=Particle*|particles.bindingClass=storage-buffer|particles.argumentIndex=0|particles.storageBufferLayout.elementType=Particle|particles.storageBufferLayout.layout=std430|particles.storageBufferLayout.fields.0.name=positions|particles.storageBufferLayout.fields.0.arrayStrideBytes=16"
      "-DEXPECTED_REFLECTION_FEATURE_FIELDS=${CROSSGL_OPENGL_STRUCT_STORAGE_ARRAY_FIELD_VALIDATED_FEATURE_FIELDS}"
      -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
  add_test(NAME cglc_build_opengl_struct_nested_array_field_glsl_validated
    COMMAND ${CMAKE_COMMAND}
      -DCGLC=$<TARGET_FILE:cglc>
      -DINPUT=${CROSSGL_STRUCT_NESTED_ARRAY_FIELD_COMPUTE_SHADER}
      -DTARGET=opengl
      -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-opengl-struct-nested-array-field-validated.cglb
      -DMODE=source-package-build
      -DEXPECTED_SOURCE=backend/opengl/StructNestedArrayFieldComputeShader.comp.glsl
      "-DEXPECTED_SOURCE_SNIPPET=particles[1].history[0].position = previous;"
      -DEXPECTED_NATIVE_BINARY=backend/opengl/StructNestedArrayFieldComputeShader.glsl
      -DEXPECTED_NATIVE_BINARY_STATUS=validated
      -DEXPECTED_DIAGNOSTIC=opengl.glsl-validated
      "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=opengl|module=StructNestedArrayFieldComputeShader|nativeBinary=backend/opengl/StructNestedArrayFieldComputeShader.glsl"
      "-DEXPECTED_REFLECTION_TARGET_FIELDS=particles.sourceType=Particle*|particles.bindingClass=storage-buffer|particles.argumentIndex=0|particles.storageBufferLayout.elementType=Particle|particles.storageBufferLayout.layout=std430|particles.storageBufferLayout.fields.0.name=history|particles.storageBufferLayout.fields.0.arrayElementCount=2"
      "-DEXPECTED_REFLECTION_FEATURE_FIELDS=${CROSSGL_OPENGL_STRUCT_STORAGE_AGGREGATE_ARRAY_FIELD_VALIDATED_FEATURE_FIELDS}"
      -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
  add_test(NAME cglc_build_opengl_runtime_struct_array_glsl_validated
    COMMAND ${CMAKE_COMMAND}
      -DCGLC=$<TARGET_FILE:cglc>
      -DINPUT=${CROSSGL_RUNTIME_STRUCT_ARRAY_SHADER}
      -DTARGET=opengl
      -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-opengl-runtime-struct-array-validated.cglb
      -DMODE=source-package-build
      -DEXPECTED_SOURCE=backend/opengl/RuntimeStructArrayShader.comp.glsl
      "-DEXPECTED_SOURCE_SNIPPET=TailParticle particles[];"
      -DEXPECTED_NATIVE_BINARY=backend/opengl/RuntimeStructArrayShader.glsl
      -DEXPECTED_NATIVE_BINARY_STATUS=validated
      -DEXPECTED_DIAGNOSTIC=opengl.glsl-validated
      "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=opengl|module=RuntimeStructArrayShader|nativeBinary=backend/opengl/RuntimeStructArrayShader.glsl"
      "-DEXPECTED_REFLECTION_TARGET_FIELDS=payloads.sourceType=RuntimeStructPayload*|payloads.bindingClass=storage-buffer|payloads.storageBufferLayout.elementType=RuntimeStructPayload|payloads.storageBufferLayout.layout=std430|payloads.storageBufferLayout.fields.1.name=particles"
      "-DEXPECTED_REFLECTION_FEATURE_FIELDS=${CROSSGL_OPENGL_RUNTIME_STRUCT_ARRAY_VALIDATED_FEATURE_FIELDS}"
      -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
  add_test(NAME cglc_build_opengl_struct_storage_buffer_array_glsl_validated
    COMMAND ${CMAKE_COMMAND}
      -DCGLC=$<TARGET_FILE:cglc>
      -DINPUT=${CROSSGL_STORAGE_BUFFER_STRUCT_ARRAY_ACCESS_SHADER}
      -DTARGET=opengl
      -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-opengl-struct-storage-buffer-array-validated.cglb
      -DMODE=source-package-build
      -DEXPECTED_SOURCE=backend/opengl/StorageBufferStructArrayAccessShader.comp.glsl
      "-DEXPECTED_SOURCE_SNIPPET=particles_Buffers[0].particles[1].mass = mass + 1.0;"
      -DEXPECTED_NATIVE_BINARY=backend/opengl/StorageBufferStructArrayAccessShader.glsl
      -DEXPECTED_NATIVE_BINARY_STATUS=validated
      -DEXPECTED_DIAGNOSTIC=opengl.glsl-validated
      "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=opengl|module=StorageBufferStructArrayAccessShader|nativeBinary=backend/opengl/StorageBufferStructArrayAccessShader.glsl"
      "-DEXPECTED_REFLECTION_TARGET_FIELDS=particles.sourceType=Particle*[2]|particles.bindingClass=storage-buffer|particles.arraySize=2|particles.arrayElementCount=2|particles.storageBufferLayout.elementType=Particle|particles.storageBufferLayout.layout=std430|particles.storageBufferLayout.arrayStrideBytes=16"
      "-DEXPECTED_REFLECTION_FEATURE_FIELDS=${CROSSGL_OPENGL_STRUCT_STORAGE_DESCRIPTOR_ARRAY_VALIDATED_FEATURE_FIELDS}|scalar-arithmetic.kind=operation"
      -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
  add_test(NAME cglc_build_opengl_struct_storage_buffer_array_field_descriptor_array_glsl_validated
    COMMAND ${CMAKE_COMMAND}
      -DCGLC=$<TARGET_FILE:cglc>
      -DINPUT=${CROSSGL_STORAGE_BUFFER_STRUCT_ARRAY_FIELD_DESCRIPTOR_ARRAY_SHADER}
      -DTARGET=opengl
      -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-opengl-struct-storage-buffer-array-field-descriptor-array-validated.cglb
      -DMODE=source-package-build
      -DEXPECTED_SOURCE=backend/opengl/StorageBufferStructArrayFieldDescriptorArrayShader.comp.glsl
      "-DEXPECTED_SOURCE_SNIPPET=particles_Buffers[0].particles[1].history[0].position = previousPosition;"
      -DEXPECTED_NATIVE_BINARY=backend/opengl/StorageBufferStructArrayFieldDescriptorArrayShader.glsl
      -DEXPECTED_NATIVE_BINARY_STATUS=validated
      -DEXPECTED_DIAGNOSTIC=opengl.glsl-validated
      "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=opengl|module=StorageBufferStructArrayFieldDescriptorArrayShader|nativeBinary=backend/opengl/StorageBufferStructArrayFieldDescriptorArrayShader.glsl"
      "-DEXPECTED_REFLECTION_TARGET_FIELDS=particles.sourceType=Particle*[2]|particles.bindingClass=storage-buffer|particles.arraySize=2|particles.arrayElementCount=2|particles.storageBufferLayout.elementType=Particle|particles.storageBufferLayout.layout=std430|particles.storageBufferLayout.arrayStrideBytes=48|particles.storageBufferLayout.fields.0.name=weights|particles.storageBufferLayout.fields.1.name=history"
      "-DEXPECTED_REFLECTION_FEATURE_FIELDS=${CROSSGL_OPENGL_STRUCT_STORAGE_DESCRIPTOR_ARRAY_VALIDATED_FEATURE_FIELDS}|fixed-array-field.kind=layout|scalar-vector-elements.kind=array|scalar-arithmetic.kind=operation"
      -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
  add_test(NAME cglc_build_opengl_function_parameter_struct_array_glsl_validated
    COMMAND ${CMAKE_COMMAND}
      -DCGLC=$<TARGET_FILE:cglc>
      -DINPUT=${CMAKE_CURRENT_SOURCE_DIR}/tests/opengl/fixtures/OpenGLFunctionParameterStructArrayUnsupportedShader.cgl
      -DTARGET=opengl
      -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-opengl-function-parameter-struct-array-validated.cglb
      -DMODE=source-package-build
      -DEXPECTED_SOURCE=backend/opengl/OpenGLFunctionParameterStructArrayUnsupportedShader.comp.glsl
      "-DEXPECTED_SOURCE_SNIPPET=float firstWeight(Payload payloads[COUNT])"
      -DEXPECTED_NATIVE_BINARY=backend/opengl/OpenGLFunctionParameterStructArrayUnsupportedShader.glsl
      -DEXPECTED_NATIVE_BINARY_STATUS=validated
      -DEXPECTED_DIAGNOSTIC=opengl.glsl-validated
      "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=opengl|module=OpenGLFunctionParameterStructArrayUnsupportedShader|nativeBinary=backend/opengl/OpenGLFunctionParameterStructArrayUnsupportedShader.glsl"
      "-DEXPECTED_REFLECTION_TARGET_FIELDS=particles.sourceType=Particle*|particles.bindingClass=storage-buffer|particles.storageBufferLayout.elementType=Particle|particles.storageBufferLayout.layout=std430|particles.storageBufferLayout.fields.0.name=payloads|particles.storageBufferLayout.fields.0.arrayElementCount=2"
      "-DEXPECTED_REFLECTION_FEATURE_FIELDS=${CROSSGL_OPENGL_STRUCT_STORAGE_AGGREGATE_ARRAY_FIELD_VALIDATED_FEATURE_FIELDS}|function-parameter-array.kind=array"
      -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
  add_test(NAME cglc_build_opengl_while_glsl_validated
    COMMAND ${CMAKE_COMMAND}
      -DCGLC=$<TARGET_FILE:cglc>
      -DINPUT=${CROSSGL_WHILE_COMPUTE_SHADER}
      -DTARGET=opengl
      -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-opengl-while-validated.cglb
      -DMODE=source-package-build
      -DEXPECTED_SOURCE=backend/opengl/WhileComputeShader.comp.glsl
      "-DEXPECTED_SOURCE_SNIPPET=values[i] = values[i] + 1.0;"
      -DEXPECTED_NATIVE_BINARY=backend/opengl/WhileComputeShader.glsl
      -DEXPECTED_NATIVE_BINARY_STATUS=validated
      -DEXPECTED_DIAGNOSTIC=opengl.glsl-validated
      "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=opengl|module=WhileComputeShader"
      "-DEXPECTED_REFLECTION_TARGET_FIELDS=values.sourceType=float*|values.bindingClass=storage-buffer|values.argumentIndex=0|values.storageBufferLayout.layout=std430"
      "-DEXPECTED_REFLECTION_FEATURE_FIELDS=structured-loop.kind=controlFlow|storage-buffer-write.kind=operation"
      -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
  add_test(NAME cglc_build_opengl_for_glsl_validated
    COMMAND ${CMAKE_COMMAND}
      -DCGLC=$<TARGET_FILE:cglc>
      -DINPUT=${CROSSGL_FOR_COMPUTE_SHADER}
      -DTARGET=opengl
      -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-opengl-for-validated.cglb
      -DMODE=source-package-build
      -DEXPECTED_SOURCE=backend/opengl/ForComputeShader.comp.glsl
      "-DEXPECTED_SOURCE_SNIPPET=for (int i = 0; i < 4; i++)"
      -DEXPECTED_NATIVE_BINARY=backend/opengl/ForComputeShader.glsl
      -DEXPECTED_NATIVE_BINARY_STATUS=validated
      -DEXPECTED_DIAGNOSTIC=opengl.glsl-validated
      "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=opengl|module=ForComputeShader|nativeBinary=backend/opengl/ForComputeShader.glsl"
      "-DEXPECTED_REFLECTION_JSON_ARRAY_LENGTHS=resources=1|targetResourceBindings=1"
      "-DEXPECTED_REFLECTION_TARGET_FIELDS=${CROSSGL_OPENGL_LOOP_REFLECTION_TARGET_FIELDS}"
      "-DEXPECTED_REFLECTION_FEATURE_FIELDS=${CROSSGL_OPENGL_VALIDATED_LOOP_REFLECTION_FEATURE_FIELDS}"
      -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
  add_test(NAME cglc_build_opengl_for_stride_glsl_validated
    COMMAND ${CMAKE_COMMAND}
      -DCGLC=$<TARGET_FILE:cglc>
      -DINPUT=${CROSSGL_FOR_STRIDE_COMPUTE_SHADER}
      -DTARGET=opengl
      -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-opengl-for-stride-validated.cglb
      -DMODE=source-package-build
      -DEXPECTED_SOURCE=backend/opengl/ForStrideComputeShader.comp.glsl
      "-DEXPECTED_SOURCE_SNIPPET=for (int i = 0; i < 8; i+=2)"
      -DEXPECTED_NATIVE_BINARY=backend/opengl/ForStrideComputeShader.glsl
      -DEXPECTED_NATIVE_BINARY_STATUS=validated
      -DEXPECTED_DIAGNOSTIC=opengl.glsl-validated
      "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=opengl|module=ForStrideComputeShader|nativeBinary=backend/opengl/ForStrideComputeShader.glsl"
      "-DEXPECTED_REFLECTION_JSON_ARRAY_LENGTHS=resources=1|targetResourceBindings=1"
      "-DEXPECTED_REFLECTION_TARGET_FIELDS=${CROSSGL_OPENGL_LOOP_REFLECTION_TARGET_FIELDS}"
      "-DEXPECTED_REFLECTION_FEATURE_FIELDS=${CROSSGL_OPENGL_VALIDATED_LOOP_REFLECTION_FEATURE_FIELDS}"
      -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
  add_test(NAME cglc_build_opengl_nested_for_glsl_validated
    COMMAND ${CMAKE_COMMAND}
      -DCGLC=$<TARGET_FILE:cglc>
      -DINPUT=${CROSSGL_NESTED_FOR_COMPUTE_SHADER}
      -DTARGET=opengl
      -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-opengl-nested-for-validated.cglb
      -DMODE=source-package-build
      -DEXPECTED_SOURCE=backend/opengl/NestedForComputeShader.comp.glsl
      "-DEXPECTED_SOURCE_SNIPPET=for (int j = 0; j < 2; j++)"
      -DEXPECTED_NATIVE_BINARY=backend/opengl/NestedForComputeShader.glsl
      -DEXPECTED_NATIVE_BINARY_STATUS=validated
      -DEXPECTED_DIAGNOSTIC=opengl.glsl-validated
      "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=opengl|module=NestedForComputeShader|nativeBinary=backend/opengl/NestedForComputeShader.glsl"
      "-DEXPECTED_REFLECTION_JSON_ARRAY_LENGTHS=resources=1|targetResourceBindings=1"
      "-DEXPECTED_REFLECTION_TARGET_FIELDS=${CROSSGL_OPENGL_LOOP_REFLECTION_TARGET_FIELDS}"
      "-DEXPECTED_REFLECTION_FEATURE_FIELDS=${CROSSGL_OPENGL_VALIDATED_LOOP_REFLECTION_FEATURE_FIELDS}"
      -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
  add_test(NAME cglc_build_opengl_for_dynamic_stride_glsl_validated
    COMMAND ${CMAKE_COMMAND}
      -DCGLC=$<TARGET_FILE:cglc>
      -DINPUT=${CROSSGL_FOR_DYNAMIC_STRIDE_COMPUTE_SHADER}
      -DTARGET=opengl
      -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-opengl-for-dynamic-stride-validated.cglb
      -DMODE=source-package-build
      -DEXPECTED_SOURCE=backend/opengl/ForDynamicStrideComputeShader.comp.glsl
      "-DEXPECTED_SOURCE_SNIPPET=for (int i = 0; i < 8; i+=stride)"
      -DEXPECTED_NATIVE_BINARY=backend/opengl/ForDynamicStrideComputeShader.glsl
      -DEXPECTED_NATIVE_BINARY_STATUS=validated
      -DEXPECTED_DIAGNOSTIC=opengl.glsl-validated
      "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=opengl|module=ForDynamicStrideComputeShader|nativeBinary=backend/opengl/ForDynamicStrideComputeShader.glsl"
      "-DEXPECTED_REFLECTION_JSON_ARRAY_LENGTHS=resources=1|targetResourceBindings=1"
      "-DEXPECTED_REFLECTION_TARGET_FIELDS=${CROSSGL_OPENGL_LOOP_REFLECTION_TARGET_FIELDS}"
      "-DEXPECTED_REFLECTION_FEATURE_FIELDS=${CROSSGL_OPENGL_VALIDATED_LOOP_REFLECTION_FEATURE_FIELDS}"
      -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
  add_test(NAME cglc_build_opengl_for_constant_stride_glsl_validated
    COMMAND ${CMAKE_COMMAND}
      -DCGLC=$<TARGET_FILE:cglc>
      -DINPUT=${CROSSGL_FOR_CONSTANT_STRIDE_COMPUTE_SHADER}
      -DTARGET=opengl
      -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-opengl-for-constant-stride-validated.cglb
      -DMODE=source-package-build
      -DEXPECTED_SOURCE=backend/opengl/ForConstantStrideComputeShader.comp.glsl
      "-DEXPECTED_SOURCE_SNIPPET=for (int i = 0; i < 8; i+=TILE_SIZE)"
      -DEXPECTED_NATIVE_BINARY=backend/opengl/ForConstantStrideComputeShader.glsl
      -DEXPECTED_NATIVE_BINARY_STATUS=validated
      -DEXPECTED_DIAGNOSTIC=opengl.glsl-validated
      "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=opengl|module=ForConstantStrideComputeShader|nativeBinary=backend/opengl/ForConstantStrideComputeShader.glsl"
      "-DEXPECTED_REFLECTION_JSON_ARRAY_LENGTHS=resources=1|targetResourceBindings=1"
      "-DEXPECTED_REFLECTION_TARGET_FIELDS=${CROSSGL_OPENGL_LOOP_REFLECTION_TARGET_FIELDS}"
      "-DEXPECTED_REFLECTION_FEATURE_FIELDS=${CROSSGL_OPENGL_VALIDATED_LOOP_REFLECTION_FEATURE_FIELDS}"
      -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
  add_test(NAME cglc_build_opengl_for_folded_update_glsl_validated
    COMMAND ${CMAKE_COMMAND}
      -DCGLC=$<TARGET_FILE:cglc>
      -DINPUT=${CROSSGL_FOR_FOLDED_UPDATE_COMPUTE_SHADER}
      -DTARGET=opengl
      -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-opengl-for-folded-update-validated.cglb
      -DMODE=source-package-build
      -DEXPECTED_SOURCE=backend/opengl/ForFoldedUpdateComputeShader.comp.glsl
      "-DEXPECTED_SOURCE_SNIPPET=for (int i = 0; i < 8; i = i + (3))"
      -DEXPECTED_NATIVE_BINARY=backend/opengl/ForFoldedUpdateComputeShader.glsl
      -DEXPECTED_NATIVE_BINARY_STATUS=validated
      -DEXPECTED_DIAGNOSTIC=opengl.glsl-validated
      "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=opengl|module=ForFoldedUpdateComputeShader|nativeBinary=backend/opengl/ForFoldedUpdateComputeShader.glsl"
      "-DEXPECTED_REFLECTION_JSON_ARRAY_LENGTHS=resources=1|targetResourceBindings=1"
      "-DEXPECTED_REFLECTION_TARGET_FIELDS=${CROSSGL_OPENGL_LOOP_REFLECTION_TARGET_FIELDS}"
      "-DEXPECTED_REFLECTION_FEATURE_FIELDS=${CROSSGL_OPENGL_VALIDATED_LOOP_REFLECTION_FEATURE_FIELDS}"
      -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
  add_test(NAME cglc_build_opengl_if_glsl_validated
    COMMAND ${CMAKE_COMMAND}
      -DCGLC=$<TARGET_FILE:cglc>
      -DINPUT=${CROSSGL_IF_COMPUTE_SHADER}
      -DTARGET=opengl
      -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-opengl-if-validated.cglb
      -DMODE=source-package-build
      -DEXPECTED_SOURCE=backend/opengl/IfComputeShader.comp.glsl
      "-DEXPECTED_SOURCE_SNIPPET=if (x > 0.0)"
      -DEXPECTED_NATIVE_BINARY=backend/opengl/IfComputeShader.glsl
      -DEXPECTED_NATIVE_BINARY_STATUS=validated
      -DEXPECTED_DIAGNOSTIC=opengl.glsl-validated
      "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=opengl|module=IfComputeShader|nativeBinary=backend/opengl/IfComputeShader.glsl"
      "-DEXPECTED_REFLECTION_TARGET_FIELDS=values.sourceType=float*|values.bindingClass=storage-buffer|values.argumentIndex=0|values.storageBufferLayout.layout=std430|values.storageBufferLayout.elementType=float"
      "-DEXPECTED_REFLECTION_FEATURE_FIELDS=native-glsl-package.kind=backend|glsl-program-validation.kind=validation|structured-selection.kind=controlFlow|storage-buffer-read.kind=operation|storage-buffer-write.kind=operation"
      -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
  add_test(NAME cglc_build_opengl_if_scoped_glsl_validated
    COMMAND ${CMAKE_COMMAND}
      -DCGLC=$<TARGET_FILE:cglc>
      -DINPUT=${CROSSGL_IF_SCOPED_COMPUTE_SHADER}
      -DTARGET=opengl
      -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-opengl-if-scoped-validated.cglb
      -DMODE=source-package-build
      -DEXPECTED_SOURCE=backend/opengl/IfScopedComputeShader.comp.glsl
      "-DEXPECTED_SOURCE_SNIPPET=${CROSSGL_OPENGL_IF_SCOPED_SOURCE_SNIPPET}"
      -DEXPECTED_NATIVE_BINARY=backend/opengl/IfScopedComputeShader.glsl
      -DEXPECTED_NATIVE_BINARY_STATUS=validated
      -DEXPECTED_DIAGNOSTIC=opengl.glsl-validated
      "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=opengl|module=IfScopedComputeShader|nativeBinary=backend/opengl/IfScopedComputeShader.glsl"
      "-DEXPECTED_REFLECTION_JSON_ARRAY_LENGTHS=resources=1|targetResourceBindings=1"
      "-DEXPECTED_REFLECTION_TARGET_FIELDS=values.sourceType=float*|values.bindingClass=storage-buffer|values.argumentIndex=0|values.storageBufferLayout.layout=std430|values.storageBufferLayout.elementType=float|values.storageBufferLayout.arrayStrideBytes=4"
      "-DEXPECTED_REFLECTION_FEATURE_FIELDS=native-glsl-package.kind=backend|glsl-program-validation.kind=validation|local-declaration.kind=operation|storage-buffer-read.kind=operation|index-access.kind=operation|structured-selection.kind=controlFlow|scalar-arithmetic.kind=operation|scalar-comparison.kind=operation|storage-buffer-write.kind=operation"
      -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
  add_test(NAME cglc_build_opengl_nested_if_glsl_validated
    COMMAND ${CMAKE_COMMAND}
      -DCGLC=$<TARGET_FILE:cglc>
      -DINPUT=${CROSSGL_NESTED_IF_COMPUTE_SHADER}
      -DTARGET=opengl
      -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-opengl-nested-if-validated.cglb
      -DMODE=source-package-build
      -DEXPECTED_SOURCE=backend/opengl/NestedIfComputeShader.comp.glsl
      "-DEXPECTED_SOURCE_SNIPPET=if (scaled > 3.0)"
      -DEXPECTED_NATIVE_BINARY=backend/opengl/NestedIfComputeShader.glsl
      -DEXPECTED_NATIVE_BINARY_STATUS=validated
      -DEXPECTED_DIAGNOSTIC=opengl.glsl-validated
      "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=opengl|module=NestedIfComputeShader|nativeBinary=backend/opengl/NestedIfComputeShader.glsl"
      "-DEXPECTED_REFLECTION_TARGET_FIELDS=values.sourceType=float*|values.bindingClass=storage-buffer|values.argumentIndex=0|values.storageBufferLayout.layout=std430|values.storageBufferLayout.elementType=float"
      "-DEXPECTED_REFLECTION_FEATURE_FIELDS=native-glsl-package.kind=backend|glsl-program-validation.kind=validation|structured-selection.kind=controlFlow|storage-buffer-read.kind=operation|storage-buffer-write.kind=operation"
      -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
  add_test(NAME cglc_build_opengl_if_return_glsl_validated
    COMMAND ${CMAKE_COMMAND}
      -DCGLC=$<TARGET_FILE:cglc>
      -DINPUT=${CROSSGL_IF_RETURN_COMPUTE_SHADER}
      -DTARGET=opengl
      -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-opengl-if-return-validated.cglb
      -DMODE=source-package-build
      -DEXPECTED_SOURCE=backend/opengl/IfReturnComputeShader.comp.glsl
      "-DEXPECTED_SOURCE_SNIPPET=${CROSSGL_OPENGL_IF_RETURN_SOURCE_SNIPPET}"
      -DEXPECTED_NATIVE_BINARY=backend/opengl/IfReturnComputeShader.glsl
      -DEXPECTED_NATIVE_BINARY_STATUS=validated
      -DEXPECTED_DIAGNOSTIC=opengl.glsl-validated
      "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=opengl|module=IfReturnComputeShader|nativeBinary=backend/opengl/IfReturnComputeShader.glsl"
      "-DEXPECTED_REFLECTION_TARGET_FIELDS=values.sourceType=float*|values.bindingClass=storage-buffer|values.argumentIndex=0|values.storageBufferLayout.layout=std430|values.storageBufferLayout.elementType=float"
      "-DEXPECTED_REFLECTION_FEATURE_FIELDS=native-glsl-package.kind=backend|glsl-program-validation.kind=validation|structured-selection.kind=controlFlow|storage-buffer-read.kind=operation|storage-buffer-write.kind=operation"
      -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
  add_test(NAME cglc_build_opengl_read_modify_write_glsl_validated
    COMMAND ${CMAKE_COMMAND}
      -DCGLC=$<TARGET_FILE:cglc>
      -DINPUT=${CROSSGL_READ_MODIFY_WRITE_COMPUTE_SHADER}
      -DTARGET=opengl
      -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-opengl-read-modify-write-validated.cglb
      -DMODE=source-package-build
      -DEXPECTED_SOURCE=backend/opengl/ReadModifyWriteComputeShader.comp.glsl
      "-DEXPECTED_SOURCE_SNIPPET=values[0] = values[0] + 1.0;"
      -DEXPECTED_NATIVE_BINARY=backend/opengl/ReadModifyWriteComputeShader.glsl
      -DEXPECTED_NATIVE_BINARY_STATUS=validated
      -DEXPECTED_DIAGNOSTIC=opengl.glsl-validated
      "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=opengl|module=ReadModifyWriteComputeShader|nativeBinary=backend/opengl/ReadModifyWriteComputeShader.glsl"
      "-DEXPECTED_REFLECTION_TARGET_FIELDS=values.sourceType=float*|values.bindingClass=storage-buffer|values.argumentIndex=0|values.storageBufferLayout.layout=std430|values.storageBufferLayout.elementType=float"
      "-DEXPECTED_REFLECTION_FEATURE_FIELDS=native-glsl-package.kind=backend|glsl-program-validation.kind=validation|storage-buffer-write.kind=operation|storage-buffer-read.kind=operation|scalar-arithmetic.kind=operation"
      -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
  add_test(NAME cglc_build_opengl_intrinsics_glsl_validated
    COMMAND ${CMAKE_COMMAND}
      -DCGLC=$<TARGET_FILE:cglc>
      -DINPUT=${CROSSGL_INTRINSIC_COMPUTE_SHADER}
      -DTARGET=opengl
      -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-opengl-intrinsics-validated.cglb
      -DMODE=source-package-build
      -DEXPECTED_SOURCE=backend/opengl/IntrinsicComputeShader.comp.glsl
      "-DEXPECTED_SOURCE_SNIPPET=${CROSSGL_OPENGL_INTRINSIC_SOURCE_SNIPPET}"
      -DEXPECTED_NATIVE_BINARY=backend/opengl/IntrinsicComputeShader.glsl
      -DEXPECTED_NATIVE_BINARY_STATUS=validated
      -DEXPECTED_DIAGNOSTIC=opengl.glsl-validated
      "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=opengl|module=IntrinsicComputeShader|nativeBinary=backend/opengl/IntrinsicComputeShader.glsl"
      "-DEXPECTED_REFLECTION_TARGET_FIELDS=scalars.sourceType=float*|scalars.bindingClass=storage-buffer|scalars.argumentIndex=0|scalars.storageBufferLayout.layout=std430|vectors.sourceType=vec4*|vectors.bindingClass=storage-buffer|vectors.argumentIndex=1|vectors.storageBufferLayout.layout=std430|vectors.storageBufferLayout.elementType=vec4"
      "-DEXPECTED_REFLECTION_FEATURE_FIELDS=native-glsl-package.kind=backend|glsl-program-validation.kind=validation|storage-buffer-write.kind=operation"
      -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
  add_test(NAME cglc_build_opengl_vector_swizzle_glsl_validated
    COMMAND ${CMAKE_COMMAND}
      -DCGLC=$<TARGET_FILE:cglc>
      -DINPUT=${CROSSGL_VECTOR_SWIZZLE_COMPUTE_SHADER}
      -DTARGET=opengl
      -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-opengl-vector-swizzle-validated.cglb
      -DMODE=source-package-build
      -DEXPECTED_SOURCE=backend/opengl/VectorSwizzleComputeShader.comp.glsl
      "-DEXPECTED_SOURCE_SNIPPET=${CROSSGL_OPENGL_VECTOR_SWIZZLE_SOURCE_SNIPPET}"
      -DEXPECTED_NATIVE_BINARY=backend/opengl/VectorSwizzleComputeShader.glsl
      -DEXPECTED_NATIVE_BINARY_STATUS=validated
      -DEXPECTED_DIAGNOSTIC=opengl.glsl-validated
      "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=opengl|module=VectorSwizzleComputeShader|nativeBinary=backend/opengl/VectorSwizzleComputeShader.glsl"
      "-DEXPECTED_REFLECTION_TARGET_FIELDS=values.sourceType=float*|values.bindingClass=storage-buffer|values.argumentIndex=0|values.storageBufferLayout.layout=std430|values.storageBufferLayout.elementType=float"
      "-DEXPECTED_REFLECTION_FEATURE_FIELDS=native-glsl-package.kind=backend|glsl-program-validation.kind=validation|compute-kernel.kind=stage|workgroup-size.kind=execution|storage-buffer.kind=resource|local-declaration.kind=operation|storage-buffer-read.kind=operation|vector-constructor.kind=operation|index-access.kind=operation|storage-buffer-write.kind=operation"
      -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
  add_test(NAME cglc_build_opengl_arithmetic_glsl_validated
    COMMAND ${CMAKE_COMMAND}
      -DCGLC=$<TARGET_FILE:cglc>
      -DINPUT=${CROSSGL_ARITHMETIC_COMPUTE_SHADER}
      -DTARGET=opengl
      -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-opengl-arithmetic-validated.cglb
      -DMODE=source-package-build
      -DEXPECTED_SOURCE=backend/opengl/ArithmeticComputeShader.comp.glsl
      "-DEXPECTED_SOURCE_SNIPPET=${CROSSGL_OPENGL_ARITHMETIC_SOURCE_SNIPPET}"
      -DEXPECTED_NATIVE_BINARY=backend/opengl/ArithmeticComputeShader.glsl
      -DEXPECTED_NATIVE_BINARY_STATUS=validated
      -DEXPECTED_DIAGNOSTIC=opengl.glsl-validated
      "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=opengl|module=ArithmeticComputeShader|nativeBinary=backend/opengl/ArithmeticComputeShader.glsl"
      "-DEXPECTED_REFLECTION_FEATURE_FIELDS=native-glsl-package.kind=backend|glsl-program-validation.kind=validation|compute-kernel.kind=stage|workgroup-size.kind=execution"
      -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
  add_test(NAME cglc_build_opengl_comparison_glsl_validated
    COMMAND ${CMAKE_COMMAND}
      -DCGLC=$<TARGET_FILE:cglc>
      -DINPUT=${CROSSGL_COMPARISON_COMPUTE_SHADER}
      -DTARGET=opengl
      -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-opengl-comparison-validated.cglb
      -DMODE=source-package-build
      -DEXPECTED_SOURCE=backend/opengl/ComparisonComputeShader.comp.glsl
      "-DEXPECTED_SOURCE_SNIPPET=${CROSSGL_OPENGL_COMPARISON_SOURCE_SNIPPET}"
      -DEXPECTED_NATIVE_BINARY=backend/opengl/ComparisonComputeShader.glsl
      -DEXPECTED_NATIVE_BINARY_STATUS=validated
      -DEXPECTED_DIAGNOSTIC=opengl.glsl-validated
      "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=opengl|module=ComparisonComputeShader|nativeBinary=backend/opengl/ComparisonComputeShader.glsl"
      "-DEXPECTED_REFLECTION_TARGET_FIELDS=values.sourceType=float*|values.bindingClass=storage-buffer|values.argumentIndex=0|values.storageBufferLayout.layout=std430|values.storageBufferLayout.elementType=float"
      "-DEXPECTED_REFLECTION_FEATURE_FIELDS=native-glsl-package.kind=backend|glsl-program-validation.kind=validation|storage-buffer.kind=resource"
      -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
  add_test(NAME cglc_build_opengl_load_local_glsl_validated
    COMMAND ${CMAKE_COMMAND}
      -DCGLC=$<TARGET_FILE:cglc>
      -DINPUT=${CROSSGL_LOAD_LOCAL_COMPUTE_SHADER}
      -DTARGET=opengl
      -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-opengl-load-local-validated.cglb
      -DMODE=source-package-build
      -DEXPECTED_SOURCE=backend/opengl/LoadLocalComputeShader.comp.glsl
      "-DEXPECTED_SOURCE_SNIPPET=${CROSSGL_OPENGL_LOAD_LOCAL_SOURCE_SNIPPET}"
      -DEXPECTED_NATIVE_BINARY=backend/opengl/LoadLocalComputeShader.glsl
      -DEXPECTED_NATIVE_BINARY_STATUS=validated
      -DEXPECTED_DIAGNOSTIC=opengl.glsl-validated
      "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=opengl|module=LoadLocalComputeShader|nativeBinary=backend/opengl/LoadLocalComputeShader.glsl"
      "-DEXPECTED_REFLECTION_TARGET_FIELDS=values.sourceType=float*|values.bindingClass=storage-buffer|values.argumentIndex=0|values.storageBufferLayout.layout=std430|values.storageBufferLayout.elementType=float"
      "-DEXPECTED_REFLECTION_FEATURE_FIELDS=native-glsl-package.kind=backend|glsl-program-validation.kind=validation|storage-buffer.kind=resource|local-declaration.kind=operation|storage-buffer-read.kind=operation|storage-buffer-write.kind=operation|scalar-arithmetic.kind=operation"
      -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
  add_test(NAME cglc_build_opengl_scalar_constructor_glsl_validated
    COMMAND ${CMAKE_COMMAND}
      -DCGLC=$<TARGET_FILE:cglc>
      -DINPUT=${CROSSGL_SCALAR_CONSTRUCTOR_COMPUTE_SHADER}
      -DTARGET=opengl
      -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-opengl-scalar-constructor-validated.cglb
      -DMODE=source-package-build
      -DEXPECTED_SOURCE=backend/opengl/ScalarConstructorComputeShader.comp.glsl
      "-DEXPECTED_SOURCE_SNIPPET=${CROSSGL_OPENGL_SCALAR_CONSTRUCTOR_SOURCE_SNIPPET}"
      -DEXPECTED_NATIVE_BINARY=backend/opengl/ScalarConstructorComputeShader.glsl
      -DEXPECTED_NATIVE_BINARY_STATUS=validated
      -DEXPECTED_DIAGNOSTIC=opengl.glsl-validated
      "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=opengl|module=ScalarConstructorComputeShader|nativeBinary=backend/opengl/ScalarConstructorComputeShader.glsl"
      "-DEXPECTED_REFLECTION_TARGET_FIELDS=values.sourceType=float*|values.bindingClass=storage-buffer|values.argumentIndex=0|values.storageBufferLayout.layout=std430|values.storageBufferLayout.elementType=float"
      "-DEXPECTED_REFLECTION_FEATURE_FIELDS=native-glsl-package.kind=backend|glsl-program-validation.kind=validation|storage-buffer.kind=resource|local-declaration.kind=operation|storage-buffer-read.kind=operation|index-access.kind=operation|scalar-constructor.kind=operation|storage-buffer-write.kind=operation|scalar-arithmetic.kind=operation"
      -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
  add_test(NAME cglc_build_opengl_vector_local_glsl_validated
    COMMAND ${CMAKE_COMMAND}
      -DCGLC=$<TARGET_FILE:cglc>
      -DINPUT=${CROSSGL_VECTOR_LOCAL_COMPUTE_SHADER}
      -DTARGET=opengl
      -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-opengl-vector-local-validated.cglb
      -DMODE=source-package-build
      -DEXPECTED_SOURCE=backend/opengl/VectorLocalComputeShader.comp.glsl
      "-DEXPECTED_SOURCE_SNIPPET=${CROSSGL_OPENGL_VECTOR_LOCAL_SOURCE_SNIPPET}"
      -DEXPECTED_NATIVE_BINARY=backend/opengl/VectorLocalComputeShader.glsl
      -DEXPECTED_NATIVE_BINARY_STATUS=validated
      -DEXPECTED_DIAGNOSTIC=opengl.glsl-validated
      "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=opengl|module=VectorLocalComputeShader|nativeBinary=backend/opengl/VectorLocalComputeShader.glsl"
      "-DEXPECTED_REFLECTION_TARGET_FIELDS=values.sourceType=float*|values.bindingClass=storage-buffer|values.argumentIndex=0|values.storageBufferLayout.layout=std430|values.storageBufferLayout.elementType=float"
      "-DEXPECTED_REFLECTION_FEATURE_FIELDS=native-glsl-package.kind=backend|glsl-program-validation.kind=validation|storage-buffer.kind=resource|local-declaration.kind=operation|vector-constructor.kind=operation|vector-arithmetic.kind=operation|storage-buffer-write.kind=operation"
      -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
  add_test(NAME cglc_build_opengl_vector_buffer_glsl_validated
    COMMAND ${CMAKE_COMMAND}
      -DCGLC=$<TARGET_FILE:cglc>
      -DINPUT=${CROSSGL_VECTOR_BUFFER_COMPUTE_SHADER}
      -DTARGET=opengl
      -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-opengl-vector-buffer-validated.cglb
      -DMODE=source-package-build
      -DEXPECTED_SOURCE=backend/opengl/VectorBufferComputeShader.comp.glsl
      "-DEXPECTED_SOURCE_SNIPPET=${CROSSGL_OPENGL_VECTOR_BUFFER_SOURCE_SNIPPET}"
      -DEXPECTED_NATIVE_BINARY=backend/opengl/VectorBufferComputeShader.glsl
      -DEXPECTED_NATIVE_BINARY_STATUS=validated
      -DEXPECTED_DIAGNOSTIC=opengl.glsl-validated
      "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=opengl|module=VectorBufferComputeShader|nativeBinary=backend/opengl/VectorBufferComputeShader.glsl"
      "-DEXPECTED_REFLECTION_TARGET_FIELDS=values.sourceType=vec4*|values.bindingClass=storage-buffer|values.argumentIndex=0|values.storageBufferLayout.layout=std430|values.storageBufferLayout.elementType=vec4|values.storageBufferLayout.arrayStrideBytes=16"
      "-DEXPECTED_REFLECTION_FEATURE_FIELDS=native-glsl-package.kind=backend|glsl-program-validation.kind=validation|storage-buffer.kind=resource|vector-storage-buffer.kind=layout|vector-arithmetic.kind=operation|vector-constructor.kind=operation|storage-buffer-write.kind=operation"
      -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
  add_test(NAME cglc_build_opengl_vector3_buffer_glsl_validated
    COMMAND ${CMAKE_COMMAND}
      -DCGLC=$<TARGET_FILE:cglc>
      -DINPUT=${CROSSGL_VECTOR3_BUFFER_COMPUTE_SHADER}
      -DTARGET=opengl
      -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-opengl-vector3-buffer-validated.cglb
      -DMODE=source-package-build
      -DEXPECTED_SOURCE=backend/opengl/Vector3BufferComputeShader.comp.glsl
      "-DEXPECTED_SOURCE_SNIPPET=${CROSSGL_OPENGL_VECTOR3_BUFFER_SOURCE_SNIPPET}"
      -DEXPECTED_NATIVE_BINARY=backend/opengl/Vector3BufferComputeShader.glsl
      -DEXPECTED_NATIVE_BINARY_STATUS=validated
      -DEXPECTED_DIAGNOSTIC=opengl.glsl-validated
      "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=opengl|module=Vector3BufferComputeShader|nativeBinary=backend/opengl/Vector3BufferComputeShader.glsl"
      "-DEXPECTED_REFLECTION_TARGET_FIELDS=values.sourceType=vec3*|values.bindingClass=storage-buffer|values.argumentIndex=0|values.storageBufferLayout.layout=std430|values.storageBufferLayout.elementType=vec3|values.storageBufferLayout.arrayStrideBytes=16"
      "-DEXPECTED_REFLECTION_FEATURE_FIELDS=native-glsl-package.kind=backend|glsl-program-validation.kind=validation|storage-buffer.kind=resource|vector-storage-buffer.kind=layout|vector-arithmetic.kind=operation|vector-constructor.kind=operation|storage-buffer-write.kind=operation"
      -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
  crossgl_label_optional_native_test(
    cglc_build_opengl_storage_buffer_glsl_validated opengl)
  crossgl_label_optional_native_test(
    cglc_build_opengl_workgroup_shared_glsl_validated opengl)
  crossgl_label_optional_native_test(
    cglc_build_opengl_workgroup_barrier_glsl_validated opengl)
  crossgl_label_optional_native_test(
    cglc_build_opengl_compute_invocation_builtin_glsl_validated opengl)
  crossgl_label_optional_native_test(
    cglc_build_opengl_atomic_add_glsl_validated opengl)
  crossgl_label_optional_native_test(
    cglc_build_opengl_atomic_add_return_glsl_validated opengl)
  crossgl_label_optional_native_test(
    cglc_build_opengl_atomic_minmax_return_glsl_validated opengl)
  crossgl_label_optional_native_test(
    cglc_build_opengl_atomic_exchange_return_glsl_validated opengl)
  crossgl_label_optional_native_test(
    cglc_build_opengl_atomic_bitwise_return_glsl_validated opengl)
  crossgl_label_optional_native_test(
    cglc_build_opengl_function_parameter_array_glsl_validated opengl)
  crossgl_label_optional_native_test(
    cglc_build_opengl_local_function_parameter_array_glsl_validated opengl)
  crossgl_label_optional_native_test(
    cglc_build_opengl_folded_local_function_parameter_array_glsl_validated
    opengl)
  crossgl_label_optional_native_test(
    cglc_build_opengl_nested_local_function_parameter_array_glsl_validated
    opengl)
  crossgl_label_optional_native_test(
    cglc_build_opengl_dynamic_nested_local_function_parameter_array_glsl_validated
    opengl)
  crossgl_label_optional_native_test(
    cglc_build_opengl_local_function_parameter_array_write_glsl_validated
    opengl)
  crossgl_label_optional_native_test(
    cglc_build_opengl_nested_function_parameter_array_write_glsl_validated
    opengl)
  crossgl_label_optional_native_test(
    cglc_build_opengl_struct_buffer_glsl_validated opengl)
  crossgl_label_optional_native_test(
    cglc_build_opengl_struct_vector_buffer_glsl_validated opengl)
  crossgl_label_optional_native_test(
    cglc_build_opengl_struct_nested_field_glsl_validated opengl)
  crossgl_label_optional_native_test(
    cglc_build_opengl_struct_array_field_glsl_validated opengl)
  crossgl_label_optional_native_test(
    cglc_build_opengl_struct_constant_array_field_glsl_validated opengl)
  crossgl_label_optional_native_test(
    cglc_build_opengl_struct_vector_array_field_glsl_validated opengl)
  crossgl_label_optional_native_test(
    cglc_build_opengl_struct_nested_array_field_glsl_validated opengl)
  crossgl_label_optional_native_test(
    cglc_build_opengl_runtime_struct_array_glsl_validated opengl)
  crossgl_label_optional_native_test(
    cglc_build_opengl_struct_storage_buffer_array_glsl_validated opengl)
  crossgl_label_optional_native_test(
    cglc_build_opengl_struct_storage_buffer_array_field_descriptor_array_glsl_validated
    opengl)
  crossgl_label_optional_native_test(
    cglc_build_opengl_function_parameter_struct_array_glsl_validated opengl)
  crossgl_label_optional_native_test(cglc_build_opengl_while_glsl_validated
    opengl)
  crossgl_label_optional_native_test(cglc_build_opengl_for_glsl_validated
    opengl)
  crossgl_label_optional_native_test(
    cglc_build_opengl_for_stride_glsl_validated opengl)
  crossgl_label_optional_native_test(
    cglc_build_opengl_nested_for_glsl_validated opengl)
  crossgl_label_optional_native_test(
    cglc_build_opengl_for_dynamic_stride_glsl_validated opengl)
  crossgl_label_optional_native_test(
    cglc_build_opengl_for_constant_stride_glsl_validated opengl)
  crossgl_label_optional_native_test(
    cglc_build_opengl_for_folded_update_glsl_validated opengl)
  crossgl_label_optional_native_test(cglc_build_opengl_if_glsl_validated
    opengl)
  crossgl_label_optional_native_test(
    cglc_build_opengl_nested_if_glsl_validated opengl)
  crossgl_label_optional_native_test(
    cglc_build_opengl_if_return_glsl_validated opengl)
  crossgl_label_optional_native_test(
    cglc_build_opengl_read_modify_write_glsl_validated opengl)
  crossgl_label_optional_native_test(
    cglc_build_opengl_intrinsics_glsl_validated opengl)
  crossgl_label_optional_native_test(
    cglc_build_opengl_vector_swizzle_glsl_validated opengl)
  crossgl_label_optional_native_test(
    cglc_build_opengl_arithmetic_glsl_validated opengl)
  crossgl_label_optional_native_test(
    cglc_build_opengl_comparison_glsl_validated opengl)
  crossgl_label_optional_native_test(
    cglc_build_opengl_load_local_glsl_validated opengl)
  crossgl_label_optional_native_test(
    cglc_build_opengl_scalar_constructor_glsl_validated opengl)
  crossgl_label_optional_native_test(
    cglc_build_opengl_vector_local_glsl_validated opengl)
  crossgl_label_optional_native_test(
    cglc_build_opengl_vector_buffer_glsl_validated opengl)
  crossgl_label_optional_native_test(
    cglc_build_opengl_vector3_buffer_glsl_validated opengl)
else()
  crossgl_add_optional_native_skip_test(
    NAME cglc_build_opengl_storage_buffer_glsl_validator_unavailable
    TARGET opengl
    REQUIRED_VARS CROSSGL_GLSLANG_VALIDATOR)
endif()
if(CROSSGL_HAS_DIRECTX_NATIVE_VALIDATOR)
  set(CROSSGL_DIRECTX_NATIVE_DXC_TEST_ENV
    "-DTOOLCHAIN_PATH_PREPEND=${CROSSGL_DXC_DIR}"
    -DTOOLCHAIN_DISABLE_FALLBACK=ON)
  add_test(NAME cglc_directx_toolchain_native_smoke
    COMMAND ${CMAKE_COMMAND}
      -DCGLC=$<TARGET_FILE:cglc>
      -DINPUT=${CROSSGL_STORAGE_BUFFER_COMPUTE_SHADER}
      -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-directx-toolchain-smoke.cglb
      -DEXPECTED_MODULE=StorageBufferComputeShader
      "-DDXC=${CROSSGL_DXC}"
      -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/DirectXToolchainSmoke.cmake)
  add_test(NAME cglc_build_directx_storage_buffer_dxil_native
    COMMAND ${CMAKE_COMMAND}
      -DCGLC=$<TARGET_FILE:cglc>
      -DINPUT=${CROSSGL_STORAGE_BUFFER_COMPUTE_SHADER}
      -DTARGET=directx
      -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-directx-storage-buffer-dxil.cglb
      -DMODE=source-package-build
      -DEXPECTED_SOURCE=backend/directx/StorageBufferComputeShader.hlsl
      -DEXPECTED_SOURCE_SNIPPET=RWStructuredBuffer
      -DEXPECTED_NATIVE_BINARY=backend/directx/StorageBufferComputeShader.dxil
      -DEXPECTED_NATIVE_BINARY_STATUS=emitted
      -DEXPECTED_DIAGNOSTIC=directx.dxil-emitted
      "-DEXPECTED_DIAGNOSTICS_JSON_FIELDS=diagnostics.0.severity=note|diagnostics.0.code=directx.source-package-emitted|diagnostics.1.severity=note|diagnostics.1.code=directx.dxil-emitted"
      "-DEXPECTED_DIAGNOSTICS_JSON_FIELD_CONTAINS=diagnostics.0.message=compute=cs_6_0|diagnostics.1.message=compute=cs_6_0"
      "-DEXPECTED_DIAGNOSTICS_JSON_ARRAY_LENGTHS=diagnostics=2"
      ${CROSSGL_DIRECTX_NATIVE_DXC_TEST_ENV}
      -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
  add_test(NAME cglc_build_directx_function_parameter_array_dxil_native
    COMMAND ${CMAKE_COMMAND}
      -DCGLC=$<TARGET_FILE:cglc>
      -DINPUT=${CROSSGL_DIRECTX_FUNCTION_PARAMETER_ARRAY_SHADER}
      -DTARGET=directx
      -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-directx-function-parameter-array-dxil.cglb
      -DMODE=source-package-build
      -DEXPECTED_SOURCE=backend/directx/DirectXFunctionParameterArrayShader.hlsl
      "-DEXPECTED_SOURCE_SNIPPET=storeFirstWeight(forwardedWeights);"
      -DEXPECTED_NATIVE_BINARY=backend/directx/DirectXFunctionParameterArrayShader.dxil
      -DEXPECTED_NATIVE_BINARY_STATUS=emitted
      -DEXPECTED_DIAGNOSTIC=directx.dxil-emitted
      "-DEXPECTED_DIAGNOSTICS_JSON_FIELDS=diagnostics.0.severity=note|diagnostics.0.code=directx.source-package-emitted|diagnostics.1.severity=note|diagnostics.1.code=directx.dxil-emitted"
      "-DEXPECTED_DIAGNOSTICS_JSON_FIELD_CONTAINS=diagnostics.0.message=compute=cs_6_0|diagnostics.1.message=compute=cs_6_0"
      "-DEXPECTED_DIAGNOSTICS_JSON_ARRAY_LENGTHS=diagnostics=2"
      ${CROSSGL_DIRECTX_NATIVE_DXC_TEST_ENV}
      -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
  add_test(NAME cglc_build_directx_graphics_hlsl_validated
    COMMAND ${CMAKE_COMMAND}
      -DCGLC=$<TARGET_FILE:cglc>
      -DINPUT=${CROSSGL_SIMPLE_SHADER}
      -DTARGET=directx
      -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-directx-graphics-validated.cglb
      -DMODE=source-package-build
      -DEXPECTED_SOURCE=backend/directx/SimpleShader.graphics.hlsl
      -DEXPECTED_SOURCE_SNIPPET=crossgl_user_vertex_main
      "-DEXPECTED_MANIFEST_JSON_FIELDS=schemaVersion=1|target=directx|module=SimpleShader|artifacts.backendSource=backend/directx/SimpleShader.graphics.hlsl|artifacts.nativeBinary=backend/directx/SimpleShader.dxil"
      "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=directx|module=SimpleShader|nativeBinary=backend/directx/SimpleShader.dxil|entryPoints.0.stage=vertex|entryPoints.0.backendName=vertex_main|entryPoints.1.stage=fragment|entryPoints.1.backendName=fragment_main|vertexLayouts.0.entryPoint=vertex_main"
      "-DEXPECTED_REFLECTION_JSON_ARRAY_LENGTHS=entryPoints=2|vertexLayouts=1|workgroupSizes=0"
      "-DEXPECTED_REFLECTION_FEATURE_FIELDS=hlsl-lowering.kind=backend|native-dxil-package.kind=backend|dxc.kind=toolchain|dxil-validator.kind=validation|vertex-shader.kind=stage|fragment-shader.kind=stage|local-declaration.kind=operation|vector-constructor.kind=operation"
      -DEXPECTED_NATIVE_BINARY=backend/directx/SimpleShader.dxil
      -DEXPECTED_NATIVE_BINARY_STATUS=emitted
      -DEXPECTED_DIAGNOSTIC=directx.dxil-emitted
      "-DEXPECTED_DIAGNOSTICS_JSON_FIELDS=diagnostics.0.severity=note|diagnostics.0.code=directx.source-package-emitted|diagnostics.1.severity=note|diagnostics.1.code=directx.dxil-emitted"
      "-DEXPECTED_DIAGNOSTICS_JSON_FIELD_CONTAINS=diagnostics.0.message=vertex=vs_6_0|diagnostics.0.message=fragment=ps_6_0|diagnostics.1.message=vertex=vs_6_0|diagnostics.1.message=fragment=ps_6_0"
      "-DEXPECTED_DIAGNOSTICS_JSON_ARRAY_LENGTHS=diagnostics=2"
      ${CROSSGL_DIRECTX_NATIVE_DXC_TEST_ENV}
      -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
  set(CROSSGL_DIRECTX_GRAPHICS_RESOURCE_SOURCE_SNIPPET [=[cbuffer transform_Buffer : register(b0, space0) {
  Transform transform;
};
cbuffer material_Buffer : register(b1, space0) {
  Material material;
};
Texture2D<float4> colorMap : register(t2, space0);
SamplerState linearSampler : register(s3, space0);]=])
  set(CROSSGL_DIRECTX_GRAPHICS_STORAGE_BUFFER_RESOURCE_SOURCE_SNIPPET [=[RWStructuredBuffer<float4> vertexOffsets : register(u0, space0);
RWStructuredBuffer<DrawData> drawData : register(u1, space0);
RWStructuredBuffer<float4> fragmentScales : register(u2, space0);]=])
  add_test(NAME cglc_build_directx_graphics_resources_hlsl_validated
    COMMAND ${CMAKE_COMMAND}
      -DCGLC=$<TARGET_FILE:cglc>
      -DINPUT=${CROSSGL_DIRECTX_GRAPHICS_RESOURCE_SHADER}
      -DTARGET=directx
      -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-directx-graphics-resources-validated.cglb
      -DMODE=source-package-build
      -DEXPECTED_SOURCE=backend/directx/DirectXGraphicsResourceShader.graphics.hlsl
      "-DEXPECTED_SOURCE_SNIPPET=${CROSSGL_DIRECTX_GRAPHICS_RESOURCE_SOURCE_SNIPPET}"
      "-DEXPECTED_MANIFEST_JSON_FIELDS=schemaVersion=1|target=directx|module=DirectXGraphicsResourceShader|artifacts.backendSource=backend/directx/DirectXGraphicsResourceShader.graphics.hlsl|artifacts.nativeBinary=backend/directx/DirectXGraphicsResourceShader.dxil"
      "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=directx|module=DirectXGraphicsResourceShader|nativeBinary=backend/directx/DirectXGraphicsResourceShader.dxil|resources.0.name=transform|resources.0.kind=uniform|resources.0.type=Transform|resources.0.binding=0|resources.1.name=material|resources.1.kind=uniform|resources.1.type=Material|resources.1.binding=1|resources.2.name=colorMap|resources.2.kind=texture|resources.2.type=sampler2D|resources.2.binding=2|resources.3.name=linearSampler|resources.3.kind=sampler|resources.3.type=sampler|resources.3.binding=3|entryPoints.0.stage=vertex|entryPoints.1.stage=fragment|vertexLayouts.0.entryPoint=vertex_main"
      "-DEXPECTED_REFLECTION_JSON_ARRAY_LENGTHS=resources=4|targetResourceBindings=4|entryPoints=2|vertexLayouts=1|workgroupSizes=0"
      "-DEXPECTED_REFLECTION_FEATURE_FIELDS=hlsl-lowering.kind=backend|native-dxil-package.kind=backend|dxc.kind=toolchain|dxil-validator.kind=validation|vertex-shader.kind=stage|fragment-shader.kind=stage|uniform-buffer.kind=resource|sampled-texture.kind=resource|sampler-state.kind=resource|texture-sample.kind=operation|texture-explicit-lod.kind=operation"
      -DEXPECTED_NATIVE_BINARY=backend/directx/DirectXGraphicsResourceShader.dxil
      -DEXPECTED_NATIVE_BINARY_STATUS=emitted
      -DEXPECTED_DIAGNOSTIC=directx.dxil-emitted
      "-DEXPECTED_DIAGNOSTICS_JSON_FIELDS=diagnostics.0.severity=note|diagnostics.0.code=directx.source-package-emitted|diagnostics.1.severity=note|diagnostics.1.code=directx.dxil-emitted"
      "-DEXPECTED_DIAGNOSTICS_JSON_FIELD_CONTAINS=diagnostics.0.message=vertex=vs_6_0|diagnostics.0.message=fragment=ps_6_0|diagnostics.1.message=vertex=vs_6_0|diagnostics.1.message=fragment=ps_6_0"
      "-DEXPECTED_DIAGNOSTICS_JSON_ARRAY_LENGTHS=diagnostics=2"
      ${CROSSGL_DIRECTX_NATIVE_DXC_TEST_ENV}
      -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
  add_test(NAME cglc_build_directx_graphics_storage_buffer_resources_hlsl_validated
    COMMAND ${CMAKE_COMMAND}
      -DCGLC=$<TARGET_FILE:cglc>
      -DINPUT=${CROSSGL_DIRECTX_GRAPHICS_STORAGE_BUFFER_RESOURCE_SHADER}
      -DTARGET=directx
      -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-directx-graphics-storage-buffer-resources-validated.cglb
      -DMODE=source-package-build
      -DEXPECTED_SOURCE=backend/directx/DirectXGraphicsStorageBufferResourceShader.graphics.hlsl
      "-DEXPECTED_SOURCE_SNIPPET=${CROSSGL_DIRECTX_GRAPHICS_STORAGE_BUFFER_RESOURCE_SOURCE_SNIPPET}"
      "-DEXPECTED_MANIFEST_JSON_FIELDS=schemaVersion=1|target=directx|module=DirectXGraphicsStorageBufferResourceShader|artifacts.backendSource=backend/directx/DirectXGraphicsStorageBufferResourceShader.graphics.hlsl|artifacts.nativeBinary=backend/directx/DirectXGraphicsStorageBufferResourceShader.dxil"
      "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=directx|module=DirectXGraphicsStorageBufferResourceShader|nativeBinary=backend/directx/DirectXGraphicsStorageBufferResourceShader.dxil|resources.0.stage=vertex|resources.0.name=vertexOffsets|resources.0.kind=buffer|resources.0.type=vec4*|resources.0.binding=0|resources.1.stage=vertex|resources.1.name=drawData|resources.1.kind=buffer|resources.1.type=DrawData*|resources.1.binding=1|resources.2.stage=fragment|resources.2.name=drawData|resources.2.kind=buffer|resources.2.type=DrawData*|resources.2.binding=1|resources.3.stage=fragment|resources.3.name=fragmentScales|resources.3.kind=buffer|resources.3.type=vec4*|resources.3.binding=2|targetResourceBindings.1.stage=vertex|targetResourceBindings.1.name=drawData|targetResourceBindings.1.hlslType=RWStructuredBuffer<DrawData>|targetResourceBindings.2.stage=fragment|targetResourceBindings.2.name=drawData|targetResourceBindings.2.hlslType=RWStructuredBuffer<DrawData>|entryPoints.0.stage=vertex|entryPoints.1.stage=fragment|vertexLayouts.0.entryPoint=vertex_main"
      "-DEXPECTED_REFLECTION_JSON_ARRAY_LENGTHS=resources=4|targetResourceBindings=4|entryPoints=2|vertexLayouts=1|workgroupSizes=0"
      "-DEXPECTED_REFLECTION_TARGET_FIELDS=vertexOffsets.stage=vertex|vertexOffsets.entryPoint=vertex_main|vertexOffsets.sourceType=vec4*|vertexOffsets.hlslType=RWStructuredBuffer<float4>|vertexOffsets.addressSpace=unordered-access|vertexOffsets.abi=registerBinding|vertexOffsets.bindingClass=uav|vertexOffsets.descriptorType=UAV|vertexOffsets.argumentIndex=0|vertexOffsets.set=0|vertexOffsets.binding=0|fragmentScales.stage=fragment|fragmentScales.entryPoint=fragment_main|fragmentScales.sourceType=vec4*|fragmentScales.hlslType=RWStructuredBuffer<float4>|fragmentScales.addressSpace=unordered-access|fragmentScales.abi=registerBinding|fragmentScales.bindingClass=uav|fragmentScales.descriptorType=UAV|fragmentScales.argumentIndex=2|fragmentScales.set=0|fragmentScales.binding=2"
      "-DEXPECTED_REFLECTION_FEATURE_FIELDS=hlsl-lowering.kind=backend|native-dxil-package.kind=backend|dxc.kind=toolchain|dxil-validator.kind=validation|vertex-shader.kind=stage|fragment-shader.kind=stage|storage-buffer.kind=resource|vector-storage-buffer.kind=layout|index-access.kind=operation|storage-buffer-read.kind=operation|storage-buffer-write.kind=operation"
      -DEXPECTED_NATIVE_BINARY=backend/directx/DirectXGraphicsStorageBufferResourceShader.dxil
      -DEXPECTED_NATIVE_BINARY_STATUS=emitted
      -DEXPECTED_DIAGNOSTIC=directx.dxil-emitted
      "-DEXPECTED_DIAGNOSTICS_JSON_FIELDS=diagnostics.0.severity=note|diagnostics.0.code=directx.source-package-emitted|diagnostics.1.severity=note|diagnostics.1.code=directx.dxil-emitted"
      "-DEXPECTED_DIAGNOSTICS_JSON_FIELD_CONTAINS=diagnostics.0.message=vertex=vs_6_0|diagnostics.0.message=fragment=ps_6_0|diagnostics.1.message=vertex=vs_6_0|diagnostics.1.message=fragment=ps_6_0"
      "-DEXPECTED_DIAGNOSTICS_JSON_ARRAY_LENGTHS=diagnostics=2"
      ${CROSSGL_DIRECTX_NATIVE_DXC_TEST_ENV}
      -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
  set(CROSSGL_DIRECTX_GRAPHICS_SHADOW_COMPARE_SOURCE_SNIPPET [=[float visibility = shadowMap.SampleCmpLevelZero(shadowSampler, input.uv, 0.5);]=])
  add_test(NAME cglc_build_directx_graphics_shadow_compare_hlsl_validated
    COMMAND ${CMAKE_COMMAND}
      -DCGLC=$<TARGET_FILE:cglc>
      -DINPUT=${CROSSGL_DIRECTX_GRAPHICS_SHADOW_COMPARE_SHADER}
      -DTARGET=directx
      -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-directx-graphics-shadow-compare-validated.cglb
      -DMODE=source-package-build
      -DEXPECTED_SOURCE=backend/directx/DirectXGraphicsShadowCompareShader.graphics.hlsl
      "-DEXPECTED_SOURCE_SNIPPET=${CROSSGL_DIRECTX_GRAPHICS_SHADOW_COMPARE_SOURCE_SNIPPET}"
      "-DEXPECTED_MANIFEST_JSON_FIELDS=schemaVersion=1|target=directx|module=DirectXGraphicsShadowCompareShader|artifacts.backendSource=backend/directx/DirectXGraphicsShadowCompareShader.graphics.hlsl|artifacts.nativeBinary=backend/directx/DirectXGraphicsShadowCompareShader.dxil"
      "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=directx|module=DirectXGraphicsShadowCompareShader|nativeBinary=backend/directx/DirectXGraphicsShadowCompareShader.dxil|resources.0.name=shadowMap|resources.0.kind=texture|resources.0.type=sampler2DShadow|resources.0.set=1|resources.0.binding=2|resources.1.name=shadowSampler|resources.1.kind=sampler|resources.1.type=comparison_sampler|resources.1.set=1|resources.1.binding=3|entryPoints.0.stage=vertex|entryPoints.1.stage=fragment|vertexLayouts.0.entryPoint=vertex_main"
      "-DEXPECTED_REFLECTION_JSON_ARRAY_LENGTHS=resources=2|targetResourceBindings=2|entryPoints=2|vertexLayouts=1|workgroupSizes=0"
      "-DEXPECTED_REFLECTION_TARGET_FIELDS=shadowMap.stage=fragment|shadowMap.entryPoint=fragment_main|shadowMap.sourceType=sampler2DShadow|shadowMap.hlslType=Texture2D<float>|shadowMap.addressSpace=shader-resource|shadowMap.abi=registerBinding|shadowMap.bindingClass=srv|shadowMap.descriptorType=SRV|shadowMap.argumentIndex=2|shadowMap.set=1|shadowMap.binding=2|shadowSampler.stage=fragment|shadowSampler.entryPoint=fragment_main|shadowSampler.sourceType=comparison_sampler|shadowSampler.hlslType=SamplerComparisonState|shadowSampler.addressSpace=sampler|shadowSampler.abi=registerBinding|shadowSampler.bindingClass=sampler|shadowSampler.descriptorType=Sampler|shadowSampler.argumentIndex=3|shadowSampler.set=1|shadowSampler.binding=3"
      "-DEXPECTED_REFLECTION_FEATURE_FIELDS=hlsl-lowering.kind=backend|native-dxil-package.kind=backend|dxc.kind=toolchain|dxil-validator.kind=validation|vertex-shader.kind=stage|fragment-shader.kind=stage|sampled-texture.kind=resource|depth-compare-format.kind=texture|sampler-state.kind=resource|texture-shadow-compare.kind=operation"
      -DEXPECTED_NATIVE_BINARY=backend/directx/DirectXGraphicsShadowCompareShader.dxil
      -DEXPECTED_NATIVE_BINARY_STATUS=emitted
      -DEXPECTED_DIAGNOSTIC=directx.dxil-emitted
      "-DEXPECTED_DIAGNOSTICS_JSON_FIELDS=diagnostics.0.severity=note|diagnostics.0.code=directx.source-package-emitted|diagnostics.1.severity=note|diagnostics.1.code=directx.dxil-emitted"
      "-DEXPECTED_DIAGNOSTICS_JSON_FIELD_CONTAINS=diagnostics.0.message=vertex=vs_6_0|diagnostics.0.message=fragment=ps_6_0|diagnostics.1.message=vertex=vs_6_0|diagnostics.1.message=fragment=ps_6_0"
      "-DEXPECTED_DIAGNOSTICS_JSON_ARRAY_LENGTHS=diagnostics=2"
      ${CROSSGL_DIRECTX_NATIVE_DXC_TEST_ENV}
      -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
  set(CROSSGL_DIRECTX_GRAPHICS_SHADOW_COMPARE_LOD_SOURCE_SNIPPET [=[float visibility = shadowMap.SampleCmpLevel(shadowSampler, input.uv, 0.5, 2.0);]=])
  add_test(NAME cglc_build_directx_graphics_shadow_compare_lod_hlsl_validated
    COMMAND ${CMAKE_COMMAND}
      -DCGLC=$<TARGET_FILE:cglc>
      -DINPUT=${CROSSGL_DIRECTX_GRAPHICS_SHADOW_COMPARE_LOD_SHADER}
      -DTARGET=directx
      -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-directx-graphics-shadow-compare-lod-validated.cglb
      -DMODE=source-package-build
      -DEXPECTED_SOURCE=backend/directx/DirectXGraphicsShadowCompareLodShader.graphics.hlsl
      "-DEXPECTED_SOURCE_SNIPPET=${CROSSGL_DIRECTX_GRAPHICS_SHADOW_COMPARE_LOD_SOURCE_SNIPPET}"
      "-DEXPECTED_MANIFEST_JSON_FIELDS=schemaVersion=1|target=directx|module=DirectXGraphicsShadowCompareLodShader|artifacts.backendSource=backend/directx/DirectXGraphicsShadowCompareLodShader.graphics.hlsl|artifacts.nativeBinary=backend/directx/DirectXGraphicsShadowCompareLodShader.dxil"
      "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=directx|module=DirectXGraphicsShadowCompareLodShader|nativeBinary=backend/directx/DirectXGraphicsShadowCompareLodShader.dxil|resources.0.stage=fragment|resources.0.name=shadowMap|resources.0.kind=texture|resources.0.type=sampler2DShadow|resources.0.set=1|resources.0.binding=2|resources.1.stage=fragment|resources.1.name=shadowSampler|resources.1.kind=sampler|resources.1.type=comparison_sampler|resources.1.set=1|resources.1.binding=3|entryPoints.0.stage=vertex|entryPoints.1.stage=fragment|vertexLayouts.0.entryPoint=vertex_main|manualTextureCompareKernelSummary.totalCount=0"
      "-DEXPECTED_REFLECTION_JSON_ARRAY_LENGTHS=resources=2|targetResourceBindings=2|entryPoints=2|vertexLayouts=1|workgroupSizes=0|manualTextureCompareKernels=0"
      "-DEXPECTED_REFLECTION_TARGET_FIELDS=shadowMap.stage=fragment|shadowMap.entryPoint=fragment_main|shadowMap.sourceType=sampler2DShadow|shadowMap.hlslType=Texture2D<float>|shadowMap.addressSpace=shader-resource|shadowMap.abi=registerBinding|shadowMap.bindingClass=srv|shadowMap.descriptorType=SRV|shadowMap.argumentIndex=2|shadowMap.set=1|shadowMap.binding=2|shadowSampler.stage=fragment|shadowSampler.entryPoint=fragment_main|shadowSampler.sourceType=comparison_sampler|shadowSampler.hlslType=SamplerComparisonState|shadowSampler.addressSpace=sampler|shadowSampler.abi=registerBinding|shadowSampler.bindingClass=sampler|shadowSampler.descriptorType=Sampler|shadowSampler.argumentIndex=3|shadowSampler.set=1|shadowSampler.binding=3"
      "-DEXPECTED_REFLECTION_FEATURE_FIELDS=hlsl-lowering.kind=backend|native-dxil-package.kind=backend|dxc.kind=toolchain|dxil-validator.kind=validation|vertex-shader.kind=stage|fragment-shader.kind=stage|sampled-texture.kind=resource|depth-compare-format.kind=texture|sampler-state.kind=resource|texture-shadow-compare.kind=operation|texture-shadow-compare-explicit-lod.kind=operation"
      -DEXPECTED_NATIVE_BINARY=backend/directx/DirectXGraphicsShadowCompareLodShader.dxil
      -DEXPECTED_NATIVE_BINARY_STATUS=emitted
      -DEXPECTED_DIAGNOSTIC=directx.dxil-emitted
      "-DEXPECTED_DIAGNOSTICS_JSON_FIELDS=diagnostics.0.severity=note|diagnostics.0.code=directx.source-package-emitted|diagnostics.1.severity=note|diagnostics.1.code=directx.dxil-emitted"
      "-DEXPECTED_DIAGNOSTICS_JSON_FIELD_CONTAINS=diagnostics.0.message=vertex=vs_6_7|diagnostics.0.message=fragment=ps_6_7|diagnostics.1.message=vertex=vs_6_7|diagnostics.1.message=fragment=ps_6_7"
      "-DEXPECTED_DIAGNOSTICS_JSON_ARRAY_LENGTHS=diagnostics=2"
      ${CROSSGL_DIRECTX_NATIVE_DXC_TEST_ENV}
      -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
  crossgl_label_optional_native_test(cglc_directx_toolchain_native_smoke
    directx)
  crossgl_label_optional_native_test(
    cglc_build_directx_storage_buffer_dxil_native directx)
  crossgl_label_optional_native_test(
    cglc_build_directx_function_parameter_array_dxil_native directx)
  crossgl_label_optional_native_test(
    cglc_build_directx_graphics_hlsl_validated directx)
  crossgl_label_optional_native_test(
    cglc_build_directx_graphics_resources_hlsl_validated directx)
  crossgl_label_optional_native_test(
    cglc_build_directx_graphics_storage_buffer_resources_hlsl_validated directx)
  crossgl_label_optional_native_test(
    cglc_build_directx_graphics_shadow_compare_hlsl_validated directx)
  crossgl_label_optional_native_test(
    cglc_build_directx_graphics_shadow_compare_lod_hlsl_validated directx)
else()
  crossgl_add_optional_native_skip_test(
    NAME cglc_directx_toolchain_native_smoke_unavailable
    TARGET directx
    REASON "optional DirectX/DXC toolchain smoke requires dxc"
    REQUIRED_VARS CROSSGL_DXC)
  crossgl_add_optional_native_skip_test(
    NAME cglc_build_directx_storage_buffer_dxc_unavailable
    TARGET directx
    REQUIRED_VARS CROSSGL_DXC)
endif()
if(CROSSGL_HAS_VULKAN_NATIVE_TOOLS)
  set(CROSSGL_VULKAN_COMPUTE_BARRIER_FIRST_SPVASM [=[OpStore %tmp_0 %const_float__1_0
OpControlBarrier %const_uint__2 %const_uint__2 %const_uint__264
%tmp_1 = OpAccessChain]=])
  set(CROSSGL_VULKAN_COMPUTE_BARRIER_SECOND_SPVASM [=[OpStore %tmp_1 %const_float__2_0
OpControlBarrier %const_uint__2 %const_uint__2 %const_uint__264
%tmp_2 = OpAccessChain]=])
  set(CROSSGL_VULKAN_ATOMIC_ADD_RETURN_DECL_SPVASM [=[%tmp_1 = OpAccessChain %ptr_StorageBuffer_atomic_int_ %resource_counters %const_int__0 %const_int__0
%tmp_2 = OpAtomicIAdd %int %tmp_1 %const_uint__1 %const_uint__0 %const_int__1
OpStore %var_oldBuffer %tmp_2]=])
  set(CROSSGL_VULKAN_ATOMIC_ADD_RETURN_WORKGROUP_SPVASM [=[%tmp_3 = OpAccessChain %ptr_Workgroup_atomic_int_ %resource_tile %const_int__0
%tmp_4 = OpAtomicIAdd %int %tmp_3 %const_uint__2 %const_uint__0 %const_int__2
OpStore %var_oldShared %tmp_4]=])
  set(CROSSGL_VULKAN_ATOMIC_ADD_RETURN_UNSIGNED_SPVASM [=[%tmp_5 = OpAccessChain %ptr_StorageBuffer_atomic_uint_ %resource_unsignedCounters %const_int__0 %const_int__0
%tmp_6 = OpLoad %uint %var_localDelta
%tmp_7 = OpAtomicIAdd %uint %tmp_5 %const_uint__1 %const_uint__0 %tmp_6
OpStore %var_oldUnsigned %tmp_7]=])
  set(CROSSGL_VULKAN_ATOMIC_ADD_RETURN_COMPAT_SPVASM [=[%tmp_8 = OpAccessChain %ptr_StorageBuffer_int %resource_compat %const_int__0 %const_int__0 %const_int__0
%tmp_9 = OpAtomicIAdd %int %tmp_8 %const_uint__1 %const_uint__0 %const_int__1
OpStore %var_oldCompat %tmp_9]=])
  set(CROSSGL_VULKAN_ATOMIC_ADD_RETURN_ASSIGN_SPVASM [=[%tmp_10 = OpAccessChain %ptr_StorageBuffer_atomic_int_ %resource_counters %const_int__0 %const_int__0
%tmp_11 = OpAtomicIAdd %int %tmp_10 %const_uint__1 %const_uint__0 %const_int__1
OpStore %var_assignedOld %tmp_11]=])
  set(CROSSGL_VULKAN_ATOMIC_ADD_RETURN_WORKGROUP_ASSIGN_SPVASM [=[%tmp_12 = OpAccessChain %ptr_Workgroup_atomic_uint_ %resource_unsignedTile %const_int__0
%tmp_13 = OpLoad %uint %var_localDelta
%tmp_14 = OpAtomicIAdd %uint %tmp_12 %const_uint__2 %const_uint__0 %tmp_13
OpStore %var_assignedUnsigned %tmp_14]=])
  set(CROSSGL_VULKAN_ATOMIC_ADD_RETURN_COMPAT_UNSIGNED_SPVASM [=[%tmp_15 = OpAccessChain %ptr_StorageBuffer_uint %resource_compat %const_int__0 %const_int__0 %const_int__1
%tmp_16 = OpLoad %uint %var_localDelta
%tmp_17 = OpAtomicIAdd %uint %tmp_15 %const_uint__1 %const_uint__0 %tmp_16
OpStore %var_assignedCompat %tmp_17]=])
  set(CROSSGL_VULKAN_ATOMIC_ADD_RETURN_STATEMENT_SPVASM [=[%tmp_18 = OpAccessChain %ptr_StorageBuffer_atomic_int_ %resource_counters %const_int__0 %const_int__0
%tmp_19 = OpAtomicIAdd %int %tmp_18 %const_uint__1 %const_uint__0 %const_int__1
%tmp_20 = OpAccessChain]=])
  set(CROSSGL_VULKAN_ATOMIC_MINMAX_STATEMENT_SMIN_SPVASM [=[%tmp_1 = OpAccessChain %ptr_StorageBuffer_atomic_int_ %resource_counters %const_int__0 %const_int__0
%tmp_2 = OpAtomicSMin %int %tmp_1 %const_uint__1 %const_uint__0 %const_int__1
%tmp_3 = OpAccessChain]=])
  set(CROSSGL_VULKAN_ATOMIC_MINMAX_STATEMENT_SMAX_SPVASM [=[%tmp_3 = OpAccessChain %ptr_StorageBuffer_atomic_int_ %resource_counters %const_int__0 %const_int__0
%tmp_4 = OpAtomicSMax %int %tmp_3 %const_uint__1 %const_uint__0 %const_int__2
%tmp_5 = OpAccessChain]=])
  set(CROSSGL_VULKAN_ATOMIC_MINMAX_STATEMENT_UMIN_SPVASM [=[%tmp_5 = OpAccessChain %ptr_StorageBuffer_atomic_uint_ %resource_unsignedCounters %const_int__0 %const_int__0
%tmp_6 = OpLoad %uint %var_localValue
%tmp_7 = OpAtomicUMin %uint %tmp_5 %const_uint__1 %const_uint__0 %tmp_6
%tmp_8 = OpAccessChain]=])
  set(CROSSGL_VULKAN_ATOMIC_MINMAX_STATEMENT_UMAX_SPVASM [=[%tmp_8 = OpAccessChain %ptr_Workgroup_atomic_uint_ %resource_unsignedTile %const_int__0
%tmp_9 = OpLoad %uint %var_localValue
%tmp_10 = OpAtomicUMax %uint %tmp_8 %const_uint__2 %const_uint__0 %tmp_9
%tmp_11 = OpAccessChain]=])
  set(CROSSGL_VULKAN_ATOMIC_MINMAX_DECL_SMIN_SPVASM [=[%tmp_11 = OpAccessChain %ptr_StorageBuffer_atomic_int_ %resource_counters %const_int__0 %const_int__0
%tmp_12 = OpAtomicSMin %int %tmp_11 %const_uint__1 %const_uint__0 %const_int__1
OpStore %var_oldMin %tmp_12]=])
  set(CROSSGL_VULKAN_ATOMIC_MINMAX_DECL_SMAX_SPVASM [=[%tmp_13 = OpAccessChain %ptr_Workgroup_atomic_int_ %resource_tile %const_int__0
%tmp_14 = OpAtomicSMax %int %tmp_13 %const_uint__2 %const_uint__0 %const_int__2
OpStore %var_oldMax %tmp_14]=])
  set(CROSSGL_VULKAN_ATOMIC_MINMAX_DECL_UMIN_SPVASM [=[%tmp_15 = OpAccessChain %ptr_StorageBuffer_atomic_uint_ %resource_unsignedCounters %const_int__0 %const_int__0
%tmp_16 = OpLoad %uint %var_localValue
%tmp_17 = OpAtomicUMin %uint %tmp_15 %const_uint__1 %const_uint__0 %tmp_16
OpStore %var_oldUnsignedMin %tmp_17]=])
  set(CROSSGL_VULKAN_ATOMIC_MINMAX_DECL_UMAX_SPVASM [=[%tmp_18 = OpAccessChain %ptr_Workgroup_atomic_uint_ %resource_unsignedTile %const_int__0
%tmp_19 = OpLoad %uint %var_localValue
%tmp_20 = OpAtomicUMax %uint %tmp_18 %const_uint__2 %const_uint__0 %tmp_19
OpStore %var_oldUnsignedMax %tmp_20]=])
  set(CROSSGL_VULKAN_ATOMIC_MINMAX_COMPAT_SPVASM [=[%tmp_21 = OpAccessChain %ptr_StorageBuffer_int %resource_compat %const_int__0 %const_int__0 %const_int__0
%tmp_22 = OpAtomicSMax %int %tmp_21 %const_uint__1 %const_uint__0 %const_int__1
OpStore %var_oldCompat %tmp_22]=])
  set(CROSSGL_VULKAN_ATOMIC_MINMAX_COMPAT_UNSIGNED_SPVASM [=[%tmp_23 = OpAccessChain %ptr_StorageBuffer_uint %resource_compat %const_int__0 %const_int__0 %const_int__1
%tmp_24 = OpLoad %uint %var_localValue
%tmp_25 = OpAtomicUMin %uint %tmp_23 %const_uint__1 %const_uint__0 %tmp_24
OpStore %var_oldCompatUnsigned %tmp_25]=])
  set(CROSSGL_VULKAN_ATOMIC_MINMAX_ASSIGN_SMIN_SPVASM [=[%tmp_26 = OpAccessChain %ptr_Workgroup_atomic_int_ %resource_tile %const_int__0
%tmp_27 = OpAtomicSMin %int %tmp_26 %const_uint__2 %const_uint__0 %const_int__1
OpStore %var_assignedMin %tmp_27]=])
  set(CROSSGL_VULKAN_ATOMIC_MINMAX_ASSIGN_UMAX_SPVASM [=[%tmp_28 = OpAccessChain %ptr_StorageBuffer_atomic_uint_ %resource_unsignedCounters %const_int__0 %const_int__0
%tmp_29 = OpLoad %uint %var_localValue
%tmp_30 = OpAtomicUMax %uint %tmp_28 %const_uint__1 %const_uint__0 %tmp_29
OpStore %var_assignedMax %tmp_30]=])
  set(CROSSGL_VULKAN_ATOMIC_EXCHANGE_STATEMENT_STORAGE_SPVASM [=[%tmp_1 = OpAccessChain %ptr_StorageBuffer_atomic_int_ %resource_counters %const_int__0 %const_int__0
%tmp_2 = OpAtomicExchange %int %tmp_1 %const_uint__1 %const_uint__0 %const_int__1
%tmp_3 = OpAccessChain]=])
  set(CROSSGL_VULKAN_ATOMIC_EXCHANGE_STATEMENT_WORKGROUP_SPVASM [=[%tmp_3 = OpAccessChain %ptr_Workgroup_atomic_int_ %resource_tile %const_int__0
%tmp_4 = OpAtomicExchange %int %tmp_3 %const_uint__2 %const_uint__0 %const_int__2
%tmp_5 = OpAccessChain]=])
  set(CROSSGL_VULKAN_ATOMIC_EXCHANGE_DECL_STORAGE_SPVASM [=[%tmp_5 = OpAccessChain %ptr_StorageBuffer_atomic_int_ %resource_counters %const_int__0 %const_int__0
%tmp_6 = OpAtomicExchange %int %tmp_5 %const_uint__1 %const_uint__0 %const_int__3
OpStore %var_oldBuffer %tmp_6]=])
  set(CROSSGL_VULKAN_ATOMIC_EXCHANGE_DECL_WORKGROUP_SPVASM [=[%tmp_7 = OpAccessChain %ptr_Workgroup_atomic_int_ %resource_tile %const_int__0
%tmp_8 = OpAtomicExchange %int %tmp_7 %const_uint__2 %const_uint__0 %const_int__4
OpStore %var_oldShared %tmp_8]=])
  set(CROSSGL_VULKAN_ATOMIC_EXCHANGE_DECL_UNSIGNED_SPVASM [=[%tmp_9 = OpAccessChain %ptr_StorageBuffer_atomic_uint_ %resource_unsignedCounters %const_int__0 %const_int__0
%tmp_10 = OpLoad %uint %var_replacement
%tmp_11 = OpAtomicExchange %uint %tmp_9 %const_uint__1 %const_uint__0 %tmp_10
OpStore %var_oldUnsigned %tmp_11]=])
  set(CROSSGL_VULKAN_ATOMIC_EXCHANGE_COMPAT_SPVASM [=[%tmp_12 = OpAccessChain %ptr_StorageBuffer_int %resource_compat %const_int__0 %const_int__0 %const_int__0
%tmp_13 = OpAtomicExchange %int %tmp_12 %const_uint__1 %const_uint__0 %const_int__5
OpStore %var_oldCompat %tmp_13]=])
  set(CROSSGL_VULKAN_ATOMIC_EXCHANGE_ASSIGN_STORAGE_SPVASM [=[%tmp_14 = OpAccessChain %ptr_StorageBuffer_atomic_int_ %resource_counters %const_int__0 %const_int__0
%tmp_15 = OpAtomicExchange %int %tmp_14 %const_uint__1 %const_uint__0 %const_int__6
OpStore %var_assignedOld %tmp_15]=])
  set(CROSSGL_VULKAN_ATOMIC_EXCHANGE_ASSIGN_WORKGROUP_UNSIGNED_SPVASM [=[%tmp_16 = OpAccessChain %ptr_Workgroup_atomic_uint_ %resource_unsignedTile %const_int__0
%tmp_17 = OpLoad %uint %var_replacement
%tmp_18 = OpAtomicExchange %uint %tmp_16 %const_uint__2 %const_uint__0 %tmp_17
OpStore %var_assignedUnsigned %tmp_18]=])
  set(CROSSGL_VULKAN_ATOMIC_EXCHANGE_COMPAT_UNSIGNED_SPVASM [=[%tmp_19 = OpAccessChain %ptr_StorageBuffer_uint %resource_compat %const_int__0 %const_int__0 %const_int__1
%tmp_20 = OpLoad %uint %var_replacement
%tmp_21 = OpAtomicExchange %uint %tmp_19 %const_uint__1 %const_uint__0 %tmp_20
OpStore %var_assignedCompat %tmp_21]=])
  set(CROSSGL_VULKAN_ATOMIC_EXCHANGE_STATEMENT_UNSIGNED_SPVASM [=[%tmp_22 = OpAccessChain %ptr_StorageBuffer_atomic_uint_ %resource_unsignedCounters %const_int__0 %const_int__0
%tmp_23 = OpLoad %uint %var_replacement
%tmp_24 = OpAtomicExchange %uint %tmp_22 %const_uint__1 %const_uint__0 %tmp_23
%tmp_25 = OpAccessChain]=])
  set(CROSSGL_VULKAN_ATOMIC_BITWISE_STATEMENT_AND_SPVASM [=[%tmp_1 = OpAccessChain %ptr_StorageBuffer_atomic_int_ %resource_counters %const_int__0 %const_int__0
%tmp_2 = OpAtomicAnd %int %tmp_1 %const_uint__1 %const_uint__0 %const_int__1
%tmp_3 = OpAccessChain]=])
  set(CROSSGL_VULKAN_ATOMIC_BITWISE_STATEMENT_OR_SPVASM [=[%tmp_3 = OpAccessChain %ptr_Workgroup_atomic_int_ %resource_tile %const_int__0
%tmp_4 = OpAtomicOr %int %tmp_3 %const_uint__2 %const_uint__0 %const_int__2
%tmp_5 = OpAccessChain]=])
  set(CROSSGL_VULKAN_ATOMIC_BITWISE_STATEMENT_XOR_SPVASM [=[%tmp_5 = OpAccessChain %ptr_StorageBuffer_atomic_uint_ %resource_unsignedCounters %const_int__0 %const_int__0
%tmp_6 = OpLoad %uint %var_mask
%tmp_7 = OpAtomicXor %uint %tmp_5 %const_uint__1 %const_uint__0 %tmp_6
%tmp_8 = OpAccessChain]=])
  set(CROSSGL_VULKAN_ATOMIC_BITWISE_STATEMENT_WORKGROUP_UNSIGNED_AND_SPVASM [=[%tmp_8 = OpAccessChain %ptr_Workgroup_atomic_uint_ %resource_unsignedTile %const_int__0
%tmp_9 = OpLoad %uint %var_mask
%tmp_10 = OpAtomicAnd %uint %tmp_8 %const_uint__2 %const_uint__0 %tmp_9
%tmp_11 = OpAccessChain]=])
  set(CROSSGL_VULKAN_ATOMIC_BITWISE_DECL_AND_SPVASM [=[%tmp_11 = OpAccessChain %ptr_StorageBuffer_atomic_int_ %resource_counters %const_int__0 %const_int__0
%tmp_12 = OpAtomicAnd %int %tmp_11 %const_uint__1 %const_uint__0 %const_int__1
OpStore %var_oldAnd %tmp_12]=])
  set(CROSSGL_VULKAN_ATOMIC_BITWISE_DECL_OR_SPVASM [=[%tmp_13 = OpAccessChain %ptr_Workgroup_atomic_int_ %resource_tile %const_int__0
%tmp_14 = OpAtomicOr %int %tmp_13 %const_uint__2 %const_uint__0 %const_int__2
OpStore %var_oldOr %tmp_14]=])
  set(CROSSGL_VULKAN_ATOMIC_BITWISE_DECL_XOR_SPVASM [=[%tmp_15 = OpAccessChain %ptr_StorageBuffer_atomic_uint_ %resource_unsignedCounters %const_int__0 %const_int__0
%tmp_16 = OpLoad %uint %var_mask
%tmp_17 = OpAtomicXor %uint %tmp_15 %const_uint__1 %const_uint__0 %tmp_16
OpStore %var_oldXor %tmp_17]=])
  set(CROSSGL_VULKAN_ATOMIC_BITWISE_DECL_WORKGROUP_UNSIGNED_AND_SPVASM [=[%tmp_18 = OpAccessChain %ptr_Workgroup_atomic_uint_ %resource_unsignedTile %const_int__0
%tmp_19 = OpLoad %uint %var_mask
%tmp_20 = OpAtomicAnd %uint %tmp_18 %const_uint__2 %const_uint__0 %tmp_19
OpStore %var_oldSharedAnd %tmp_20]=])
  set(CROSSGL_VULKAN_ATOMIC_BITWISE_COMPAT_OR_SPVASM [=[%tmp_21 = OpAccessChain %ptr_StorageBuffer_int %resource_compat %const_int__0 %const_int__0 %const_int__0
%tmp_22 = OpAtomicOr %int %tmp_21 %const_uint__1 %const_uint__0 %const_int__1
OpStore %var_oldCompatOr %tmp_22]=])
  set(CROSSGL_VULKAN_ATOMIC_BITWISE_COMPAT_XOR_SPVASM [=[%tmp_23 = OpAccessChain %ptr_StorageBuffer_uint %resource_compat %const_int__0 %const_int__0 %const_int__1
%tmp_24 = OpLoad %uint %var_mask
%tmp_25 = OpAtomicXor %uint %tmp_23 %const_uint__1 %const_uint__0 %tmp_24
OpStore %var_oldCompatXor %tmp_25]=])
  set(CROSSGL_VULKAN_ATOMIC_BITWISE_ASSIGN_AND_SPVASM [=[%tmp_26 = OpAccessChain %ptr_Workgroup_atomic_int_ %resource_tile %const_int__0
%tmp_27 = OpAtomicAnd %int %tmp_26 %const_uint__2 %const_uint__0 %const_int__1
OpStore %var_assignedAnd %tmp_27]=])
  set(CROSSGL_VULKAN_ATOMIC_BITWISE_ASSIGN_OR_SPVASM [=[%tmp_28 = OpAccessChain %ptr_StorageBuffer_atomic_uint_ %resource_unsignedCounters %const_int__0 %const_int__0
%tmp_29 = OpLoad %uint %var_mask
%tmp_30 = OpAtomicOr %uint %tmp_28 %const_uint__1 %const_uint__0 %tmp_29
OpStore %var_assignedOr %tmp_30]=])
  add_test(NAME cglc_build_vulkan_compute_barrier_native
    COMMAND ${CMAKE_COMMAND}
      -DCGLC=$<TARGET_FILE:cglc>
      -DINPUT=${CMAKE_CURRENT_SOURCE_DIR}/tests/vulkan/fixtures/VulkanComputeBarrierShader.cgl
      -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-vulkan-compute-barrier.cglb
      -DEXPECTED_MODULE=VulkanComputeBarrierShader
      -DEXPECTED_STORAGE_ELEMENT=float
      -DEXPECTED_STORAGE_STRIDE=4
      "-DEXPECTED_MANIFEST_JSON_FIELDS=schemaVersion=1|target=vulkan|module=VulkanComputeBarrierShader|artifacts.backendAssembly=backend/vulkan/VulkanComputeBarrierShader.spvasm|artifacts.nativeBinary=backend/vulkan/VulkanComputeBarrierShader.spv"
      "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=vulkan|module=VulkanComputeBarrierShader|nativeBinary=backend/vulkan/VulkanComputeBarrierShader.spv|workgroupSizes.0.entryPoint=compute_main|workgroupSizes.0.x=4|workgroupSizes.0.y=1|workgroupSizes.0.z=1"
      "-DEXPECTED_REFLECTION_JSON_ARRAY_LENGTHS=resources=2|targetResourceBindings=2|workgroupSizes=1|manualTextureCompareKernels=0"
      "-DEXPECTED_REFLECTION_TARGET_FIELDS=values.sourceType=float*|values.bindingClass=storageBuffer|values.descriptorType=VK_DESCRIPTOR_TYPE_STORAGE_BUFFER|values.storageClass=StorageBuffer|values.set=0|values.binding=0|values.storageBufferLayout.elementType=float|values.storageBufferLayout.layout=std430|values.storageBufferLayout.arrayStrideBytes=4|scratch.kind=shared|scratch.abi=workgroupLocal|scratch.bindingClass=workgroup|scratch.storageClass=Workgroup|scratch.spirvType=OpVariable<Workgroup, float[4]>|scratch.arrayElementCount=4|scratch.arrayDimensions.0.elementCount=4"
      "-DEXPECTED_REFLECTION_FEATURE_FIELDS=vulkan-prototype-package.kind=backend|compute-kernel.kind=stage|workgroup-size.kind=execution|storage-buffer.kind=resource|workgroup-shared-memory.kind=resource|index-access.kind=operation|storage-buffer-write.kind=operation"
      "-DEXPECTED_DIAGNOSTICS_JSON_ARRAY_LENGTHS=diagnostics=0"
      "-DEXPECTED_SPVASM_SNIPPET=OpControlBarrier %const_uint__2 %const_uint__2 %const_uint__264"
      -DMODE=vulkan-build
      -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
  add_test(NAME cglc_build_vulkan_compute_barrier_spvasm_native
    COMMAND ${CMAKE_COMMAND}
      -DCGLC=$<TARGET_FILE:cglc>
      -DINPUT=${CMAKE_CURRENT_SOURCE_DIR}/tests/vulkan/fixtures/VulkanComputeBarrierShader.cgl
      -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-vulkan-compute-barrier-spvasm.cglb
      -DEXPECTED_MODULE=VulkanComputeBarrierShader
      "-DEXPECTED_SPVASM_CONTAINS=%const_uint__2 = OpConstant %uint 2|%const_uint__264 = OpConstant %uint 264|${CROSSGL_VULKAN_COMPUTE_BARRIER_FIRST_SPVASM}|${CROSSGL_VULKAN_COMPUTE_BARRIER_SECOND_SPVASM}"
      "-DUNEXPECTED_SPVASM_CONTAINS=OpMemoryBarrier|OpControlBarrier %const_uint__1|OpControlBarrier %const_uint__3|OpControlBarrier %const_uint__2 %const_uint__1|OpControlBarrier %const_uint__2 %const_uint__3"
      -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectVulkanSpvasmSnippets.cmake)
  add_test(NAME cglc_build_vulkan_atomic_add_native
    COMMAND ${CMAKE_COMMAND}
      -DCGLC=$<TARGET_FILE:cglc>
      -DINPUT=${CMAKE_CURRENT_SOURCE_DIR}/tests/vulkan/fixtures/VulkanAtomicAddNativeShader.cgl
      -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-vulkan-atomic-add.cglb
      -DEXPECTED_MODULE=VulkanAtomicAddNativeShader
      -DEXPECTED_STORAGE_BUFFER_METADATA=OFF
      "-DEXPECTED_MANIFEST_JSON_FIELDS=schemaVersion=1|target=vulkan|module=VulkanAtomicAddNativeShader|artifacts.backendAssembly=backend/vulkan/VulkanAtomicAddNativeShader.spvasm|artifacts.nativeBinary=backend/vulkan/VulkanAtomicAddNativeShader.spv"
      "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=vulkan|module=VulkanAtomicAddNativeShader|nativeBinary=backend/vulkan/VulkanAtomicAddNativeShader.spv|workgroupSizes.0.entryPoint=compute_main|workgroupSizes.0.x=4|workgroupSizes.0.y=1|workgroupSizes.0.z=1"
      "-DEXPECTED_REFLECTION_JSON_ARRAY_LENGTHS=resources=4|targetResourceBindings=4|functionConstants=1|workgroupSizes=1|manualTextureCompareKernels=0"
      "-DEXPECTED_REFLECTION_TARGET_FIELDS=counters.sourceType=atomic<int>*|counters.bindingClass=storageBuffer|counters.descriptorType=VK_DESCRIPTOR_TYPE_STORAGE_BUFFER|counters.storageClass=StorageBuffer|counters.spirvType=OpTypeRuntimeArray<int>|unsignedCounters.sourceType=atomic<uint>*|unsignedCounters.binding=1|unsignedCounters.spirvType=OpTypeRuntimeArray<uint>|tile.sourceType=atomic<int>[GROUP_SIZE]|tile.bindingClass=workgroup|tile.storageClass=Workgroup|tile.spirvType=OpVariable<Workgroup, int[GROUP_SIZE]>|unsignedTile.sourceType=atomic<uint>[GROUP_SIZE]|unsignedTile.spirvType=OpVariable<Workgroup, uint[GROUP_SIZE]>"
      "-DEXPECTED_REFLECTION_FEATURE_FIELDS=vulkan-prototype-package.kind=backend|compute-kernel.kind=stage|workgroup-size.kind=execution|storage-buffer.kind=resource|workgroup-shared-memory.kind=resource|index-access.kind=operation|scalar-constructor.kind=operation"
      "-DEXPECTED_SPVASM_SNIPPET=%tmp_2 = OpAtomicIAdd %int %tmp_1 %const_uint__1 %const_uint__0 %const_int__1"
      -DMODE=vulkan-build
      -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
  add_test(NAME cglc_build_vulkan_atomic_add_spvasm_native
    COMMAND ${CMAKE_COMMAND}
      -DCGLC=$<TARGET_FILE:cglc>
      -DINPUT=${CMAKE_CURRENT_SOURCE_DIR}/tests/vulkan/fixtures/VulkanAtomicAddNativeShader.cgl
      -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-vulkan-atomic-add-spvasm.cglb
      -DEXPECTED_MODULE=VulkanAtomicAddNativeShader
      "-DEXPECTED_SPVASM_CONTAINS=OpEntryPoint GLCompute %compute_main \"main\" %resource_counters %resource_unsignedCounters %resource_tile %resource_unsignedTile|%ptr_StorageBuffer_atomic_int_ = OpTypePointer StorageBuffer %int|%ptr_StorageBuffer_atomic_uint_ = OpTypePointer StorageBuffer %uint|%ptr_Workgroup_atomic_int_ = OpTypePointer Workgroup %int|%ptr_Workgroup_atomic_uint_ = OpTypePointer Workgroup %uint|%const_uint__0 = OpConstant %uint 0|%const_uint__1 = OpConstant %uint 1|%const_uint__2 = OpConstant %uint 2|%tmp_2 = OpAtomicIAdd %int %tmp_1 %const_uint__1 %const_uint__0 %const_int__1|%tmp_4 = OpAtomicIAdd %int %tmp_3 %const_uint__2 %const_uint__0 %const_int__2|%tmp_7 = OpAtomicIAdd %uint %tmp_5 %const_uint__1 %const_uint__0 %tmp_6|%tmp_10 = OpAtomicIAdd %uint %tmp_8 %const_uint__2 %const_uint__0 %tmp_9"
      "-DUNEXPECTED_SPVASM_CONTAINS=OpAtomicFAdd|OpAtomicSMin|OpAtomicUMin|OpAtomicAnd|OpAtomicOr|OpAtomicXor|OpAtomicCompareExchange|OpAtomicExchange|OpAtomicLoad|OpAtomicStore|OpMemoryBarrier|OpControlBarrier"
      -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectVulkanSpvasmSnippets.cmake)
  add_test(NAME cglc_build_vulkan_atomic_add_return_native
    COMMAND ${CMAKE_COMMAND}
      -DCGLC=$<TARGET_FILE:cglc>
      -DINPUT=${CMAKE_CURRENT_SOURCE_DIR}/tests/vulkan/fixtures/VulkanAtomicAddReturnNativeShader.cgl
      -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-vulkan-atomic-add-return.cglb
      -DEXPECTED_MODULE=VulkanAtomicAddReturnNativeShader
      -DEXPECTED_STORAGE_BUFFER_METADATA=OFF
      "-DEXPECTED_MANIFEST_JSON_FIELDS=schemaVersion=1|target=vulkan|module=VulkanAtomicAddReturnNativeShader|artifacts.backendAssembly=backend/vulkan/VulkanAtomicAddReturnNativeShader.spvasm|artifacts.nativeBinary=backend/vulkan/VulkanAtomicAddReturnNativeShader.spv"
      "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=vulkan|module=VulkanAtomicAddReturnNativeShader|nativeBinary=backend/vulkan/VulkanAtomicAddReturnNativeShader.spv|functionConstants.0.name=GROUP_SIZE|functionConstants.0.value=4|workgroupSizes.0.entryPoint=compute_main|workgroupSizes.0.x=4|workgroupSizes.0.y=1|workgroupSizes.0.z=1|workgroupSizes.0.sourceX=GROUP_SIZE"
      "-DEXPECTED_REFLECTION_JSON_ARRAY_LENGTHS=resources=7|targetResourceBindings=7|functionConstants=1|workgroupSizes=1|manualTextureCompareKernels=0"
      "-DEXPECTED_REFLECTION_TARGET_FIELDS=counters.sourceType=atomic<int>*|counters.bindingClass=storageBuffer|unsignedCounters.sourceType=atomic<uint>*|values.sourceType=int*|unsignedValues.sourceType=uint*|compat.sourceType=CompatCounters|compat.storageBufferLayout.elementType=CompatCounters|compat.storageBufferLayout.arrayStrideBytes=8|tile.sourceType=atomic<int>[GROUP_SIZE]|tile.storageClass=Workgroup|unsignedTile.sourceType=atomic<uint>[GROUP_SIZE]|unsignedTile.storageClass=Workgroup"
      "-DEXPECTED_REFLECTION_FEATURE_FIELDS=vulkan-prototype-package.kind=backend|compute-kernel.kind=stage|workgroup-size.kind=execution|storage-buffer.kind=resource|atomic-integer.kind=type|workgroup-shared-memory.kind=resource|local-declaration.kind=operation|atomic-add.kind=operation|storage-buffer-write.kind=operation"
      "-DEXPECTED_SPVASM_SNIPPET=${CROSSGL_VULKAN_ATOMIC_ADD_RETURN_DECL_SPVASM}"
      -DMODE=vulkan-build
      -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
  add_test(NAME cglc_build_vulkan_atomic_add_return_spvasm_native
    COMMAND ${CMAKE_COMMAND}
      -DCGLC=$<TARGET_FILE:cglc>
      -DINPUT=${CMAKE_CURRENT_SOURCE_DIR}/tests/vulkan/fixtures/VulkanAtomicAddReturnNativeShader.cgl
      -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-vulkan-atomic-add-return-spvasm.cglb
      -DEXPECTED_MODULE=VulkanAtomicAddReturnNativeShader
      "-DEXPECTED_SPVASM_CONTAINS=OpEntryPoint GLCompute %compute_main \"main\" %resource_counters %resource_unsignedCounters %resource_values %resource_unsignedValues %resource_compat %resource_tile %resource_unsignedTile|%ptr_StorageBuffer_atomic_int_ = OpTypePointer StorageBuffer %int|%ptr_StorageBuffer_atomic_uint_ = OpTypePointer StorageBuffer %uint|%ptr_Workgroup_atomic_int_ = OpTypePointer Workgroup %int|%ptr_Workgroup_atomic_uint_ = OpTypePointer Workgroup %uint|%ptr_StorageBuffer_int = OpTypePointer StorageBuffer %int|%ptr_StorageBuffer_uint = OpTypePointer StorageBuffer %uint|${CROSSGL_VULKAN_ATOMIC_ADD_RETURN_DECL_SPVASM}|${CROSSGL_VULKAN_ATOMIC_ADD_RETURN_WORKGROUP_SPVASM}|${CROSSGL_VULKAN_ATOMIC_ADD_RETURN_UNSIGNED_SPVASM}|${CROSSGL_VULKAN_ATOMIC_ADD_RETURN_COMPAT_SPVASM}|${CROSSGL_VULKAN_ATOMIC_ADD_RETURN_ASSIGN_SPVASM}|${CROSSGL_VULKAN_ATOMIC_ADD_RETURN_WORKGROUP_ASSIGN_SPVASM}|${CROSSGL_VULKAN_ATOMIC_ADD_RETURN_COMPAT_UNSIGNED_SPVASM}|${CROSSGL_VULKAN_ATOMIC_ADD_RETURN_STATEMENT_SPVASM}"
      "-DUNEXPECTED_SPVASM_CONTAINS=OpAtomicFAdd|OpAtomicSMin|OpAtomicUMin|OpAtomicAnd|OpAtomicOr|OpAtomicXor|OpAtomicCompareExchange|OpAtomicExchange|OpAtomicLoad|OpAtomicStore|OpMemoryBarrier|OpControlBarrier"
      -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectVulkanSpvasmSnippets.cmake)
  add_test(NAME cglc_build_vulkan_atomic_minmax_native
    COMMAND ${CMAKE_COMMAND}
      -DCGLC=$<TARGET_FILE:cglc>
      -DINPUT=${CMAKE_CURRENT_SOURCE_DIR}/tests/vulkan/fixtures/VulkanAtomicMinMaxNativeShader.cgl
      -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-vulkan-atomic-minmax.cglb
      -DEXPECTED_MODULE=VulkanAtomicMinMaxNativeShader
      -DEXPECTED_STORAGE_BUFFER_METADATA=OFF
      "-DEXPECTED_MANIFEST_JSON_FIELDS=schemaVersion=1|target=vulkan|module=VulkanAtomicMinMaxNativeShader|artifacts.backendAssembly=backend/vulkan/VulkanAtomicMinMaxNativeShader.spvasm|artifacts.nativeBinary=backend/vulkan/VulkanAtomicMinMaxNativeShader.spv"
      "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=vulkan|module=VulkanAtomicMinMaxNativeShader|nativeBinary=backend/vulkan/VulkanAtomicMinMaxNativeShader.spv|functionConstants.0.name=GROUP_SIZE|functionConstants.0.value=4|workgroupSizes.0.entryPoint=compute_main|workgroupSizes.0.x=4|workgroupSizes.0.y=1|workgroupSizes.0.z=1|workgroupSizes.0.sourceX=GROUP_SIZE"
      "-DEXPECTED_REFLECTION_JSON_ARRAY_LENGTHS=resources=7|targetResourceBindings=7|functionConstants=1|workgroupSizes=1|manualTextureCompareKernels=0"
      "-DEXPECTED_REFLECTION_TARGET_FIELDS=counters.sourceType=atomic<int>*|counters.bindingClass=storageBuffer|unsignedCounters.sourceType=atomic<uint>*|values.sourceType=int*|unsignedValues.sourceType=uint*|compat.sourceType=CompatCounters|compat.storageBufferLayout.elementType=CompatCounters|compat.storageBufferLayout.arrayStrideBytes=8|tile.sourceType=atomic<int>[GROUP_SIZE]|tile.storageClass=Workgroup|unsignedTile.sourceType=atomic<uint>[GROUP_SIZE]|unsignedTile.storageClass=Workgroup"
      "-DEXPECTED_REFLECTION_FEATURE_FIELDS=vulkan-prototype-package.kind=backend|compute-kernel.kind=stage|workgroup-size.kind=execution|storage-buffer.kind=resource|atomic-integer.kind=type|workgroup-shared-memory.kind=resource|local-declaration.kind=operation|storage-buffer-write.kind=operation"
      "-DEXPECTED_SPVASM_SNIPPET=${CROSSGL_VULKAN_ATOMIC_MINMAX_DECL_SMIN_SPVASM}"
      -DMODE=vulkan-build
      -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
  add_test(NAME cglc_build_vulkan_atomic_minmax_spvasm_native
    COMMAND ${CMAKE_COMMAND}
      -DCGLC=$<TARGET_FILE:cglc>
      -DINPUT=${CMAKE_CURRENT_SOURCE_DIR}/tests/vulkan/fixtures/VulkanAtomicMinMaxNativeShader.cgl
      -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-vulkan-atomic-minmax-spvasm.cglb
      -DEXPECTED_MODULE=VulkanAtomicMinMaxNativeShader
      "-DEXPECTED_SPVASM_CONTAINS=OpEntryPoint GLCompute %compute_main \"main\" %resource_counters %resource_unsignedCounters %resource_values %resource_unsignedValues %resource_compat %resource_unsignedTile %resource_tile|%ptr_StorageBuffer_atomic_int_ = OpTypePointer StorageBuffer %int|%ptr_StorageBuffer_atomic_uint_ = OpTypePointer StorageBuffer %uint|%ptr_Workgroup_atomic_int_ = OpTypePointer Workgroup %int|%ptr_Workgroup_atomic_uint_ = OpTypePointer Workgroup %uint|%ptr_StorageBuffer_int = OpTypePointer StorageBuffer %int|%ptr_StorageBuffer_uint = OpTypePointer StorageBuffer %uint|${CROSSGL_VULKAN_ATOMIC_MINMAX_STATEMENT_SMIN_SPVASM}|${CROSSGL_VULKAN_ATOMIC_MINMAX_STATEMENT_SMAX_SPVASM}|${CROSSGL_VULKAN_ATOMIC_MINMAX_STATEMENT_UMIN_SPVASM}|${CROSSGL_VULKAN_ATOMIC_MINMAX_STATEMENT_UMAX_SPVASM}|${CROSSGL_VULKAN_ATOMIC_MINMAX_DECL_SMIN_SPVASM}|${CROSSGL_VULKAN_ATOMIC_MINMAX_DECL_SMAX_SPVASM}|${CROSSGL_VULKAN_ATOMIC_MINMAX_DECL_UMIN_SPVASM}|${CROSSGL_VULKAN_ATOMIC_MINMAX_DECL_UMAX_SPVASM}|${CROSSGL_VULKAN_ATOMIC_MINMAX_COMPAT_SPVASM}|${CROSSGL_VULKAN_ATOMIC_MINMAX_COMPAT_UNSIGNED_SPVASM}|${CROSSGL_VULKAN_ATOMIC_MINMAX_ASSIGN_SMIN_SPVASM}|${CROSSGL_VULKAN_ATOMIC_MINMAX_ASSIGN_UMAX_SPVASM}"
      "-DUNEXPECTED_SPVASM_CONTAINS=OpAtomicIAdd|OpAtomicFAdd|OpAtomicAnd|OpAtomicOr|OpAtomicXor|OpAtomicCompareExchange|OpAtomicExchange|OpAtomicLoad|OpAtomicStore|OpMemoryBarrier|OpControlBarrier"
      -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectVulkanSpvasmSnippets.cmake)
  add_test(NAME cglc_build_vulkan_atomic_exchange_native
    COMMAND ${CMAKE_COMMAND}
      -DCGLC=$<TARGET_FILE:cglc>
      -DINPUT=${CMAKE_CURRENT_SOURCE_DIR}/tests/vulkan/fixtures/VulkanAtomicExchangeNativeShader.cgl
      -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-vulkan-atomic-exchange.cglb
      -DEXPECTED_MODULE=VulkanAtomicExchangeNativeShader
      -DEXPECTED_STORAGE_BUFFER_METADATA=OFF
      "-DEXPECTED_MANIFEST_JSON_FIELDS=schemaVersion=1|target=vulkan|module=VulkanAtomicExchangeNativeShader|artifacts.backendAssembly=backend/vulkan/VulkanAtomicExchangeNativeShader.spvasm|artifacts.nativeBinary=backend/vulkan/VulkanAtomicExchangeNativeShader.spv"
      "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=vulkan|module=VulkanAtomicExchangeNativeShader|nativeBinary=backend/vulkan/VulkanAtomicExchangeNativeShader.spv|functionConstants.0.name=GROUP_SIZE|functionConstants.0.value=4|workgroupSizes.0.entryPoint=compute_main|workgroupSizes.0.x=4|workgroupSizes.0.y=1|workgroupSizes.0.z=1|workgroupSizes.0.sourceX=GROUP_SIZE"
      "-DEXPECTED_REFLECTION_JSON_ARRAY_LENGTHS=resources=7|targetResourceBindings=7|functionConstants=1|workgroupSizes=1|manualTextureCompareKernels=0"
      "-DEXPECTED_REFLECTION_TARGET_FIELDS=counters.sourceType=atomic<int>*|counters.bindingClass=storageBuffer|unsignedCounters.sourceType=atomic<uint>*|values.sourceType=int*|unsignedValues.sourceType=uint*|compat.sourceType=CompatCounters|compat.storageBufferLayout.elementType=CompatCounters|compat.storageBufferLayout.arrayStrideBytes=8|tile.sourceType=atomic<int>[GROUP_SIZE]|tile.storageClass=Workgroup|unsignedTile.sourceType=atomic<uint>[GROUP_SIZE]|unsignedTile.storageClass=Workgroup"
      "-DEXPECTED_REFLECTION_FEATURE_FIELDS=vulkan-prototype-package.kind=backend|compute-kernel.kind=stage|workgroup-size.kind=execution|storage-buffer.kind=resource|atomic-integer.kind=type|workgroup-shared-memory.kind=resource|local-declaration.kind=operation|storage-buffer-write.kind=operation"
      "-DEXPECTED_SPVASM_SNIPPET=${CROSSGL_VULKAN_ATOMIC_EXCHANGE_DECL_STORAGE_SPVASM}"
      -DMODE=vulkan-build
      -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
  add_test(NAME cglc_build_vulkan_atomic_exchange_spvasm_native
    COMMAND ${CMAKE_COMMAND}
      -DCGLC=$<TARGET_FILE:cglc>
      -DINPUT=${CMAKE_CURRENT_SOURCE_DIR}/tests/vulkan/fixtures/VulkanAtomicExchangeNativeShader.cgl
      -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-vulkan-atomic-exchange-spvasm.cglb
      -DEXPECTED_MODULE=VulkanAtomicExchangeNativeShader
      "-DEXPECTED_SPVASM_CONTAINS=OpEntryPoint GLCompute %compute_main \"main\" %resource_counters %resource_unsignedCounters %resource_values %resource_unsignedValues %resource_compat %resource_tile %resource_unsignedTile|%ptr_StorageBuffer_atomic_int_ = OpTypePointer StorageBuffer %int|%ptr_StorageBuffer_atomic_uint_ = OpTypePointer StorageBuffer %uint|%ptr_Workgroup_atomic_int_ = OpTypePointer Workgroup %int|%ptr_Workgroup_atomic_uint_ = OpTypePointer Workgroup %uint|%ptr_StorageBuffer_int = OpTypePointer StorageBuffer %int|%ptr_StorageBuffer_uint = OpTypePointer StorageBuffer %uint|${CROSSGL_VULKAN_ATOMIC_EXCHANGE_STATEMENT_STORAGE_SPVASM}|${CROSSGL_VULKAN_ATOMIC_EXCHANGE_STATEMENT_WORKGROUP_SPVASM}|${CROSSGL_VULKAN_ATOMIC_EXCHANGE_DECL_STORAGE_SPVASM}|${CROSSGL_VULKAN_ATOMIC_EXCHANGE_DECL_WORKGROUP_SPVASM}|${CROSSGL_VULKAN_ATOMIC_EXCHANGE_DECL_UNSIGNED_SPVASM}|${CROSSGL_VULKAN_ATOMIC_EXCHANGE_COMPAT_SPVASM}|${CROSSGL_VULKAN_ATOMIC_EXCHANGE_ASSIGN_STORAGE_SPVASM}|${CROSSGL_VULKAN_ATOMIC_EXCHANGE_ASSIGN_WORKGROUP_UNSIGNED_SPVASM}|${CROSSGL_VULKAN_ATOMIC_EXCHANGE_COMPAT_UNSIGNED_SPVASM}|${CROSSGL_VULKAN_ATOMIC_EXCHANGE_STATEMENT_UNSIGNED_SPVASM}"
      "-DUNEXPECTED_SPVASM_CONTAINS=OpAtomicIAdd|OpAtomicFAdd|OpAtomicSMin|OpAtomicUMin|OpAtomicSMax|OpAtomicUMax|OpAtomicAnd|OpAtomicOr|OpAtomicXor|OpAtomicCompareExchange|OpAtomicLoad|OpAtomicStore|OpMemoryBarrier|OpControlBarrier|atomicSub"
      -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectVulkanSpvasmSnippets.cmake)
  add_test(NAME cglc_build_vulkan_atomic_bitwise_native
    COMMAND ${CMAKE_COMMAND}
      -DCGLC=$<TARGET_FILE:cglc>
      -DINPUT=${CMAKE_CURRENT_SOURCE_DIR}/tests/vulkan/fixtures/VulkanAtomicBitwiseNativeShader.cgl
      -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-vulkan-atomic-bitwise.cglb
      -DEXPECTED_MODULE=VulkanAtomicBitwiseNativeShader
      -DEXPECTED_STORAGE_BUFFER_METADATA=OFF
      "-DEXPECTED_MANIFEST_JSON_FIELDS=schemaVersion=1|target=vulkan|module=VulkanAtomicBitwiseNativeShader|artifacts.backendAssembly=backend/vulkan/VulkanAtomicBitwiseNativeShader.spvasm|artifacts.nativeBinary=backend/vulkan/VulkanAtomicBitwiseNativeShader.spv"
      "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=vulkan|module=VulkanAtomicBitwiseNativeShader|nativeBinary=backend/vulkan/VulkanAtomicBitwiseNativeShader.spv|functionConstants.0.name=GROUP_SIZE|functionConstants.0.value=4|workgroupSizes.0.entryPoint=compute_main|workgroupSizes.0.x=4|workgroupSizes.0.y=1|workgroupSizes.0.z=1|workgroupSizes.0.sourceX=GROUP_SIZE"
      "-DEXPECTED_REFLECTION_JSON_ARRAY_LENGTHS=resources=7|targetResourceBindings=7|functionConstants=1|workgroupSizes=1|manualTextureCompareKernels=0"
      "-DEXPECTED_REFLECTION_TARGET_FIELDS=counters.sourceType=atomic<int>*|counters.bindingClass=storageBuffer|unsignedCounters.sourceType=atomic<uint>*|values.sourceType=int*|unsignedValues.sourceType=uint*|compat.sourceType=CompatCounters|compat.storageBufferLayout.elementType=CompatCounters|compat.storageBufferLayout.arrayStrideBytes=8|tile.sourceType=atomic<int>[GROUP_SIZE]|tile.storageClass=Workgroup|unsignedTile.sourceType=atomic<uint>[GROUP_SIZE]|unsignedTile.storageClass=Workgroup"
      "-DEXPECTED_REFLECTION_FEATURE_FIELDS=vulkan-prototype-package.kind=backend|compute-kernel.kind=stage|workgroup-size.kind=execution|storage-buffer.kind=resource|atomic-integer.kind=type|workgroup-shared-memory.kind=resource|local-declaration.kind=operation|storage-buffer-write.kind=operation"
      "-DEXPECTED_SPVASM_SNIPPET=${CROSSGL_VULKAN_ATOMIC_BITWISE_DECL_AND_SPVASM}"
      -DMODE=vulkan-build
      -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
  add_test(NAME cglc_build_vulkan_atomic_bitwise_spvasm_native
    COMMAND ${CMAKE_COMMAND}
      -DCGLC=$<TARGET_FILE:cglc>
      -DINPUT=${CMAKE_CURRENT_SOURCE_DIR}/tests/vulkan/fixtures/VulkanAtomicBitwiseNativeShader.cgl
      -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-vulkan-atomic-bitwise-spvasm.cglb
      -DEXPECTED_MODULE=VulkanAtomicBitwiseNativeShader
      "-DEXPECTED_SPVASM_CONTAINS=OpEntryPoint GLCompute %compute_main \"main\" %resource_counters %resource_unsignedCounters %resource_values %resource_unsignedValues %resource_compat %resource_tile %resource_unsignedTile|%ptr_StorageBuffer_atomic_int_ = OpTypePointer StorageBuffer %int|%ptr_StorageBuffer_atomic_uint_ = OpTypePointer StorageBuffer %uint|%ptr_Workgroup_atomic_int_ = OpTypePointer Workgroup %int|%ptr_Workgroup_atomic_uint_ = OpTypePointer Workgroup %uint|%ptr_StorageBuffer_int = OpTypePointer StorageBuffer %int|%ptr_StorageBuffer_uint = OpTypePointer StorageBuffer %uint|${CROSSGL_VULKAN_ATOMIC_BITWISE_STATEMENT_AND_SPVASM}|${CROSSGL_VULKAN_ATOMIC_BITWISE_STATEMENT_OR_SPVASM}|${CROSSGL_VULKAN_ATOMIC_BITWISE_STATEMENT_XOR_SPVASM}|${CROSSGL_VULKAN_ATOMIC_BITWISE_STATEMENT_WORKGROUP_UNSIGNED_AND_SPVASM}|${CROSSGL_VULKAN_ATOMIC_BITWISE_DECL_AND_SPVASM}|${CROSSGL_VULKAN_ATOMIC_BITWISE_DECL_OR_SPVASM}|${CROSSGL_VULKAN_ATOMIC_BITWISE_DECL_XOR_SPVASM}|${CROSSGL_VULKAN_ATOMIC_BITWISE_DECL_WORKGROUP_UNSIGNED_AND_SPVASM}|${CROSSGL_VULKAN_ATOMIC_BITWISE_COMPAT_OR_SPVASM}|${CROSSGL_VULKAN_ATOMIC_BITWISE_COMPAT_XOR_SPVASM}|${CROSSGL_VULKAN_ATOMIC_BITWISE_ASSIGN_AND_SPVASM}|${CROSSGL_VULKAN_ATOMIC_BITWISE_ASSIGN_OR_SPVASM}"
      "-DUNEXPECTED_SPVASM_CONTAINS=OpAtomicIAdd|OpAtomicFAdd|OpAtomicSMin|OpAtomicUMin|OpAtomicSMax|OpAtomicUMax|OpAtomicCompareExchange|OpAtomicExchange|OpAtomicLoad|OpAtomicStore|OpMemoryBarrier|OpControlBarrier|atomicSub"
      -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectVulkanSpvasmSnippets.cmake)
  crossgl_label_optional_native_test(cglc_build_vulkan_compute_barrier_native
    vulkan)
  crossgl_label_optional_native_test(
    cglc_build_vulkan_compute_barrier_spvasm_native vulkan)
  crossgl_label_optional_native_test(cglc_build_vulkan_atomic_add_native
    vulkan)
  crossgl_label_optional_native_test(
    cglc_build_vulkan_atomic_add_spvasm_native vulkan)
  crossgl_label_optional_native_test(cglc_build_vulkan_atomic_add_return_native
    vulkan)
  crossgl_label_optional_native_test(
    cglc_build_vulkan_atomic_add_return_spvasm_native vulkan)
  crossgl_label_optional_native_test(cglc_build_vulkan_atomic_minmax_native
    vulkan)
  crossgl_label_optional_native_test(
    cglc_build_vulkan_atomic_minmax_spvasm_native vulkan)
  crossgl_label_optional_native_test(
    cglc_build_vulkan_atomic_exchange_native vulkan)
  crossgl_label_optional_native_test(
    cglc_build_vulkan_atomic_exchange_spvasm_native vulkan)
  crossgl_label_optional_native_test(
    cglc_build_vulkan_atomic_bitwise_native vulkan)
  crossgl_label_optional_native_test(
    cglc_build_vulkan_atomic_bitwise_spvasm_native vulkan)
endif()

set(CROSSGL_SINGLE_PLANNED_DIAGNOSTIC_EXPECTATIONS
    "-DEXPECTED_DIAGNOSTICS_JSON_ARRAY_LENGTHS=diagnostics=1"
    "-DEXPECTED_DIAGNOSTIC_FIELDS=severity=error|location.line=1|location.column=1")
set(CROSSGL_TARGET_NOT_IMPLEMENTED_DIAGNOSTIC_EXPECTATIONS
    -DEXPECTED_DIAGNOSTIC=target.unsupported
    "-DEXPECTED_DIAGNOSTICS_JSON_PATHS=diagnostics.0.missingCapabilities"
    ${CROSSGL_SINGLE_PLANNED_DIAGNOSTIC_EXPECTATIONS})
set(CROSSGL_DIRECTX_SOURCE_UNSUPPORTED_DIAGNOSTIC_EXPECTATIONS
    -DEXPECTED_DIAGNOSTIC=directx.source-unsupported
    ${CROSSGL_SINGLE_PLANNED_DIAGNOSTIC_EXPECTATIONS})
set(CROSSGL_OPENGL_SOURCE_UNSUPPORTED_DIAGNOSTIC_EXPECTATIONS
    -DEXPECTED_DIAGNOSTIC=opengl.source-unsupported
    ${CROSSGL_SINGLE_PLANNED_DIAGNOSTIC_EXPECTATIONS})

if(CROSSGL_HAS_VULKAN_NATIVE_TOOLS)
  add_test(NAME cglc_build_vulkan_graphics_native
    COMMAND ${CMAKE_COMMAND}
      -DCGLC=$<TARGET_FILE:cglc>
      -DINPUT=${CROSSGL_SIMPLE_SHADER}
      -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-vulkan-graphics.cglb
      -DEXPECTED_MODULE=SimpleShader
      "-DEXPECTED_MANIFEST_JSON_FIELDS=schemaVersion=1|target=vulkan|module=SimpleShader|artifacts.backendAssembly=backend/vulkan/SimpleShader.spvasm|artifacts.nativeBinary=backend/vulkan/SimpleShader.spv"
      "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=vulkan|module=SimpleShader|nativeBinary=backend/vulkan/SimpleShader.spv|entryPoints.0.stage=vertex|entryPoints.0.backendName=vertex_main|entryPoints.1.stage=fragment|entryPoints.1.backendName=fragment_main|vertexLayouts.0.entryPoint=vertex_main"
      "-DEXPECTED_REFLECTION_JSON_ARRAY_LENGTHS=entryPoints=2|vertexLayouts=1|workgroupSizes=0"
      "-DEXPECTED_REFLECTION_FEATURE_FIELDS=vulkan-prototype-package.kind=backend|vertex-shader.kind=stage|fragment-shader.kind=stage|local-declaration.kind=operation|vector-constructor.kind=operation"
      "-DEXPECTED_SPVASM_SNIPPET=OpEntryPoint Fragment"
      -DEXPECTED_VULKAN_NO_DESCRIPTOR_METADATA=TRUE
      -DEXPECTED_STORAGE_BUFFER_METADATA=FALSE
      -DMODE=vulkan-build
      -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
  add_test(NAME cglc_build_vulkan_graphics_uniform_buffer_native
    COMMAND ${CMAKE_COMMAND}
      -DCGLC=$<TARGET_FILE:cglc>
      -DINPUT=${CROSSGL_VULKAN_GRAPHICS_UNIFORM_BUFFER_SHADER}
      -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-vulkan-graphics-uniform-buffer.cglb
      -DEXPECTED_MODULE=VulkanGraphicsUniformBufferShader
      -DEXPECTED_DESCRIPTOR_TYPE=VK_DESCRIPTOR_TYPE_UNIFORM_BUFFER
      "-DEXPECTED_MANIFEST_JSON_FIELDS=schemaVersion=1|target=vulkan|module=VulkanGraphicsUniformBufferShader|artifacts.backendAssembly=backend/vulkan/VulkanGraphicsUniformBufferShader.spvasm|artifacts.nativeBinary=backend/vulkan/VulkanGraphicsUniformBufferShader.spv"
      "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=vulkan|module=VulkanGraphicsUniformBufferShader|nativeBinary=backend/vulkan/VulkanGraphicsUniformBufferShader.spv|resources.0.name=vertexParams|resources.0.kind=uniform|resources.0.type=VertexParams|resources.0.binding=0|resources.1.name=fragmentParams|resources.1.kind=uniform|resources.1.type=FragmentParams|resources.1.binding=1|entryPoints.0.stage=vertex|entryPoints.0.backendName=vertex_main|entryPoints.1.stage=fragment|entryPoints.1.backendName=fragment_main|vertexLayouts.0.entryPoint=vertex_main"
      "-DEXPECTED_REFLECTION_JSON_ARRAY_LENGTHS=entryPoints=2|resources=2|targetResourceBindings=2|vertexLayouts=1|workgroupSizes=0"
      "-DEXPECTED_REFLECTION_TARGET_FIELDS=vertexParams.stage=vertex|vertexParams.bindingClass=uniformBuffer|vertexParams.descriptorType=VK_DESCRIPTOR_TYPE_UNIFORM_BUFFER|vertexParams.storageClass=Uniform|vertexParams.set=0|vertexParams.binding=0|fragmentParams.stage=fragment|fragmentParams.bindingClass=uniformBuffer|fragmentParams.descriptorType=VK_DESCRIPTOR_TYPE_UNIFORM_BUFFER|fragmentParams.storageClass=Uniform|fragmentParams.set=0|fragmentParams.binding=1"
      "-DEXPECTED_REFLECTION_FEATURE_FIELDS=vulkan-prototype-package.kind=backend|vertex-shader.kind=stage|fragment-shader.kind=stage|uniform-buffer.kind=resource|local-declaration.kind=operation|vector-constructor.kind=operation"
      "-DEXPECTED_SPVASM_SNIPPET=OpDecorate %resource_vertex_vertexParams Binding 0"
      -DEXPECTED_STORAGE_BUFFER_METADATA=FALSE
      -DMODE=vulkan-build
      -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
  add_test(NAME cglc_build_vulkan_graphics_uniform_buffer_spvasm_native
    COMMAND ${CMAKE_COMMAND}
      -DCGLC=$<TARGET_FILE:cglc>
      -DINPUT=${CROSSGL_VULKAN_GRAPHICS_UNIFORM_BUFFER_SHADER}
      -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-vulkan-graphics-uniform-buffer-spvasm.cglb
      -DEXPECTED_MODULE=VulkanGraphicsUniformBufferShader
      "-DEXPECTED_SPVASM_CONTAINS=OpDecorate %resource_vertex_vertexParams DescriptorSet 0|OpDecorate %resource_vertex_vertexParams Binding 0|OpDecorate %resource_fragment_fragmentParams DescriptorSet 0|OpDecorate %resource_fragment_fragmentParams Binding 1|%resource_vertex_vertexParams = OpVariable|%resource_fragment_fragmentParams = OpVariable|OpVectorShuffle"
      "-DUNEXPECTED_SPVASM_CONTAINS=OpTypeImage|OpTypeSampler|OpTypeRuntimeArray"
      -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectVulkanSpvasmSnippets.cmake)
  add_test(NAME cglc_build_vulkan_graphics_math_intrinsic_spvasm_native
    COMMAND ${CMAKE_COMMAND}
      -DCGLC=$<TARGET_FILE:cglc>
      -DINPUT=${CROSSGL_VULKAN_GRAPHICS_MATH_INTRINSIC_SHADER}
      -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-vulkan-graphics-math-intrinsic-spvasm.cglb
      -DEXPECTED_MODULE=VulkanGraphicsMathIntrinsicShader
      "-DEXPECTED_SPVASM_CONTAINS=OpExtInstImport \"GLSL.std.450\"|Normalize|Length|Reflect|FMix|FMin|FMax|OpDot"
      "-DUNEXPECTED_SPVASM_CONTAINS=OpTypeImage|OpTypeSampler|OpTypeRuntimeArray"
      -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectVulkanSpvasmSnippets.cmake)
  add_test(NAME cglc_build_vulkan_graphics_math_intrinsic_native
    COMMAND ${CMAKE_COMMAND}
      -DCGLC=$<TARGET_FILE:cglc>
      -DINPUT=${CROSSGL_VULKAN_GRAPHICS_MATH_INTRINSIC_SHADER}
      -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-vulkan-graphics-math-intrinsic.cglb
      -DEXPECTED_MODULE=VulkanGraphicsMathIntrinsicShader
      "-DEXPECTED_MANIFEST_JSON_FIELDS=schemaVersion=1|target=vulkan|module=VulkanGraphicsMathIntrinsicShader|artifacts.backendAssembly=backend/vulkan/VulkanGraphicsMathIntrinsicShader.spvasm|artifacts.nativeBinary=backend/vulkan/VulkanGraphicsMathIntrinsicShader.spv"
      "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=vulkan|module=VulkanGraphicsMathIntrinsicShader|nativeBinary=backend/vulkan/VulkanGraphicsMathIntrinsicShader.spv|entryPoints.0.stage=vertex|entryPoints.0.backendName=vertex_main|entryPoints.1.stage=fragment|entryPoints.1.backendName=fragment_main|vertexLayouts.0.entryPoint=vertex_main"
      "-DEXPECTED_REFLECTION_JSON_ARRAY_LENGTHS=entryPoints=2|resources=0|targetResourceBindings=0|vertexLayouts=1|workgroupSizes=0"
      "-DEXPECTED_REFLECTION_FEATURE_FIELDS=vulkan-prototype-package.kind=backend|vertex-shader.kind=stage|fragment-shader.kind=stage|local-declaration.kind=operation|vector-constructor.kind=operation"
      "-DEXPECTED_SPVASM_SNIPPET=OpExtInstImport \"GLSL.std.450\""
      -DEXPECTED_VULKAN_NO_DESCRIPTOR_METADATA=TRUE
      -DEXPECTED_STORAGE_BUFFER_METADATA=FALSE
      -DMODE=vulkan-build
      -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
  add_test(NAME cglc_build_vulkan_graphics_loop_native
    COMMAND ${CMAKE_COMMAND}
      -DCGLC=$<TARGET_FILE:cglc>
      -DINPUT=${CROSSGL_VULKAN_GRAPHICS_LOOP_SHADER}
      -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-vulkan-graphics-loop.cglb
      -DEXPECTED_MODULE=VulkanGraphicsLoopShader
      "-DEXPECTED_MANIFEST_JSON_FIELDS=schemaVersion=1|target=vulkan|module=VulkanGraphicsLoopShader|artifacts.backendAssembly=backend/vulkan/VulkanGraphicsLoopShader.spvasm|artifacts.nativeBinary=backend/vulkan/VulkanGraphicsLoopShader.spv"
      "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=vulkan|module=VulkanGraphicsLoopShader|nativeBinary=backend/vulkan/VulkanGraphicsLoopShader.spv|entryPoints.0.stage=vertex|entryPoints.0.backendName=vertex_main|entryPoints.1.stage=fragment|entryPoints.1.backendName=fragment_main|vertexLayouts.0.entryPoint=vertex_main"
      "-DEXPECTED_REFLECTION_JSON_ARRAY_LENGTHS=entryPoints=2|resources=0|targetResourceBindings=0|vertexLayouts=1|workgroupSizes=0"
      "-DEXPECTED_REFLECTION_FEATURE_FIELDS=vulkan-prototype-package.kind=backend|vertex-shader.kind=stage|fragment-shader.kind=stage|structured-loop.kind=controlFlow|scalar-comparison.kind=operation|scalar-arithmetic.kind=operation|vector-arithmetic.kind=operation|vector-constructor.kind=operation|local-declaration.kind=operation"
      "-DEXPECTED_SPVASM_SNIPPET=OpLoopMerge"
      -DEXPECTED_VULKAN_NO_DESCRIPTOR_METADATA=TRUE
      -DEXPECTED_STORAGE_BUFFER_METADATA=FALSE
      -DMODE=vulkan-build
      -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
  add_test(NAME cglc_build_vulkan_graphics_loop_spvasm_native
    COMMAND ${CMAKE_COMMAND}
      -DCGLC=$<TARGET_FILE:cglc>
      -DINPUT=${CROSSGL_VULKAN_GRAPHICS_LOOP_SHADER}
      -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-vulkan-graphics-loop-spvasm.cglb
      -DEXPECTED_MODULE=VulkanGraphicsLoopShader
      "-DEXPECTED_SPVASM_CONTAINS=OpLoopMerge|OpBranchConditional|OpSLessThan|OpIAdd|OpFAdd|OpReturn"
      "-DUNEXPECTED_SPVASM_CONTAINS=OpTypeImage|OpTypeSampler|OpTypeRuntimeArray|NonUniformEXT"
      -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectVulkanSpvasmSnippets.cmake)
  add_test(NAME cglc_build_vulkan_graphics_loop_control_native
    COMMAND ${CMAKE_COMMAND}
      -DCGLC=$<TARGET_FILE:cglc>
      -DINPUT=${CROSSGL_VULKAN_GRAPHICS_LOOP_CONTROL_SHADER}
      -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-vulkan-graphics-loop-control.cglb
      -DEXPECTED_MODULE=VulkanGraphicsLoopControlShader
      "-DEXPECTED_MANIFEST_JSON_FIELDS=schemaVersion=1|target=vulkan|module=VulkanGraphicsLoopControlShader|artifacts.backendAssembly=backend/vulkan/VulkanGraphicsLoopControlShader.spvasm|artifacts.nativeBinary=backend/vulkan/VulkanGraphicsLoopControlShader.spv"
      "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=vulkan|module=VulkanGraphicsLoopControlShader|nativeBinary=backend/vulkan/VulkanGraphicsLoopControlShader.spv|entryPoints.0.stage=vertex|entryPoints.0.backendName=vertex_main|entryPoints.1.stage=fragment|entryPoints.1.backendName=fragment_main|vertexLayouts.0.entryPoint=vertex_main"
      "-DEXPECTED_REFLECTION_JSON_ARRAY_LENGTHS=entryPoints=2|resources=0|targetResourceBindings=0|vertexLayouts=1|workgroupSizes=0"
      "-DEXPECTED_REFLECTION_FEATURE_FIELDS=vulkan-prototype-package.kind=backend|vertex-shader.kind=stage|fragment-shader.kind=stage|structured-loop.kind=controlFlow|structured-selection.kind=controlFlow|scalar-comparison.kind=operation|scalar-arithmetic.kind=operation|vector-arithmetic.kind=operation|vector-constructor.kind=operation|local-declaration.kind=operation"
      "-DEXPECTED_SPVASM_SNIPPET=OpLoopMerge"
      -DEXPECTED_VULKAN_NO_DESCRIPTOR_METADATA=TRUE
      -DEXPECTED_STORAGE_BUFFER_METADATA=FALSE
      -DMODE=vulkan-build
      -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
  add_test(NAME cglc_build_vulkan_graphics_loop_control_spvasm_native
    COMMAND ${CMAKE_COMMAND}
      -DCGLC=$<TARGET_FILE:cglc>
      -DINPUT=${CROSSGL_VULKAN_GRAPHICS_LOOP_CONTROL_SHADER}
      -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-vulkan-graphics-loop-control-spvasm.cglb
      -DEXPECTED_MODULE=VulkanGraphicsLoopControlShader
      "-DEXPECTED_SPVASM_CONTAINS=OpLoopMerge|OpSelectionMerge|OpBranchConditional|OpBranch|OpIEqual|OpSLessThan|OpIAdd|OpFAdd|OpReturn"
      "-DUNEXPECTED_SPVASM_CONTAINS=OpTypeImage|OpTypeSampler|OpTypeRuntimeArray|NonUniformEXT"
      -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectVulkanSpvasmSnippets.cmake)
  add_test(NAME cglc_build_vulkan_graphics_helper_function_native
    COMMAND ${CMAKE_COMMAND}
      -DCGLC=$<TARGET_FILE:cglc>
      -DINPUT=${CROSSGL_VULKAN_GRAPHICS_HELPER_FUNCTION_SHADER}
      -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-vulkan-graphics-helper-function.cglb
      -DEXPECTED_MODULE=VulkanGraphicsHelperFunctionShader
      "-DEXPECTED_MANIFEST_JSON_FIELDS=schemaVersion=1|target=vulkan|module=VulkanGraphicsHelperFunctionShader|artifacts.backendAssembly=backend/vulkan/VulkanGraphicsHelperFunctionShader.spvasm|artifacts.nativeBinary=backend/vulkan/VulkanGraphicsHelperFunctionShader.spv"
      "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=vulkan|module=VulkanGraphicsHelperFunctionShader|nativeBinary=backend/vulkan/VulkanGraphicsHelperFunctionShader.spv|entryPoints.0.stage=vertex|entryPoints.0.backendName=vertex_main|entryPoints.1.stage=fragment|entryPoints.1.backendName=fragment_main|vertexLayouts.0.entryPoint=vertex_main"
      "-DEXPECTED_REFLECTION_JSON_ARRAY_LENGTHS=entryPoints=2|resources=0|targetResourceBindings=0|vertexLayouts=1|workgroupSizes=0"
      "-DEXPECTED_REFLECTION_FEATURE_FIELDS=vulkan-prototype-package.kind=backend|vertex-shader.kind=stage|fragment-shader.kind=stage|scalar-arithmetic.kind=operation|vector-arithmetic.kind=operation|vector-constructor.kind=operation|local-declaration.kind=operation"
      "-DEXPECTED_SPVASM_SNIPPET=OpFunctionCall"
      -DEXPECTED_VULKAN_NO_DESCRIPTOR_METADATA=TRUE
      -DEXPECTED_STORAGE_BUFFER_METADATA=FALSE
      -DMODE=vulkan-build
      -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
  add_test(NAME cglc_build_vulkan_graphics_helper_function_spvasm_native
    COMMAND ${CMAKE_COMMAND}
      -DCGLC=$<TARGET_FILE:cglc>
      -DINPUT=${CROSSGL_VULKAN_GRAPHICS_HELPER_FUNCTION_SHADER}
      -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-vulkan-graphics-helper-function-spvasm.cglb
      -DEXPECTED_MODULE=VulkanGraphicsHelperFunctionShader
      "-DEXPECTED_SPVASM_CONTAINS=%func_fragment_tint = OpFunction|%func_fragment_shade = OpFunction|OpFunctionParameter|OpReturnValue|OpFunctionCall"
      "-DUNEXPECTED_SPVASM_CONTAINS=OpTypeImage|OpTypeSampler|OpTypeRuntimeArray|NonUniformEXT"
      -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectVulkanSpvasmSnippets.cmake)
  add_test(NAME cglc_build_vulkan_graphics_texture_sampler_native
    COMMAND ${CMAKE_COMMAND}
      -DCGLC=$<TARGET_FILE:cglc>
      -DINPUT=${CROSSGL_VULKAN_GRAPHICS_TEXTURE_SAMPLER_SHADER}
      -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-vulkan-graphics-texture-sampler.cglb
      -DEXPECTED_MODULE=VulkanGraphicsTextureSamplerShader
      -DEXPECTED_DESCRIPTOR_TYPE=VK_DESCRIPTOR_TYPE_SAMPLED_IMAGE
      "-DEXPECTED_MANIFEST_JSON_FIELDS=schemaVersion=1|target=vulkan|module=VulkanGraphicsTextureSamplerShader|artifacts.backendAssembly=backend/vulkan/VulkanGraphicsTextureSamplerShader.spvasm|artifacts.nativeBinary=backend/vulkan/VulkanGraphicsTextureSamplerShader.spv"
      "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=vulkan|module=VulkanGraphicsTextureSamplerShader|nativeBinary=backend/vulkan/VulkanGraphicsTextureSamplerShader.spv|resources.0.name=albedo|resources.0.kind=texture|resources.0.type=sampler2D|resources.0.binding=1|resources.1.name=linearSampler|resources.1.kind=sampler|resources.1.type=sampler|resources.1.binding=2|entryPoints.0.stage=vertex|entryPoints.1.stage=fragment"
      "-DEXPECTED_REFLECTION_JSON_ARRAY_LENGTHS=entryPoints=2|resources=2|targetResourceBindings=2|vertexLayouts=1|workgroupSizes=0"
      "-DEXPECTED_REFLECTION_TARGET_FIELDS=albedo.stage=fragment|albedo.bindingClass=sampledImage|albedo.descriptorType=VK_DESCRIPTOR_TYPE_SAMPLED_IMAGE|albedo.storageClass=UniformConstant|albedo.set=0|albedo.binding=1|linearSampler.stage=fragment|linearSampler.bindingClass=sampler|linearSampler.descriptorType=VK_DESCRIPTOR_TYPE_SAMPLER|linearSampler.storageClass=UniformConstant|linearSampler.set=0|linearSampler.binding=2"
      "-DEXPECTED_REFLECTION_FEATURE_FIELDS=vulkan-prototype-package.kind=backend|vertex-shader.kind=stage|fragment-shader.kind=stage|sampled-texture.kind=resource|sampler-state.kind=resource|texture-sample.kind=operation|local-declaration.kind=operation|vector-constructor.kind=operation"
      "-DEXPECTED_SPVASM_SNIPPET=OpImageSampleImplicitLod"
      -DEXPECTED_STORAGE_BUFFER_METADATA=FALSE
      -DMODE=vulkan-build
      -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
  add_test(NAME cglc_build_vulkan_graphics_texture_sampler_spvasm_native
    COMMAND ${CMAKE_COMMAND}
      -DCGLC=$<TARGET_FILE:cglc>
      -DINPUT=${CROSSGL_VULKAN_GRAPHICS_TEXTURE_SAMPLER_SHADER}
      -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-vulkan-graphics-texture-sampler-spvasm.cglb
      -DEXPECTED_MODULE=VulkanGraphicsTextureSamplerShader
      "-DEXPECTED_SPVASM_CONTAINS=OpDecorate %resource_fragment_albedo DescriptorSet 0|OpDecorate %resource_fragment_albedo Binding 1|OpDecorate %resource_fragment_linearSampler DescriptorSet 0|OpDecorate %resource_fragment_linearSampler Binding 2|OpTypeImage|OpTypeSampler|OpTypeSampledImage|%resource_fragment_albedo = OpVariable|%resource_fragment_linearSampler = OpVariable|OpSampledImage|OpImageSampleImplicitLod"
      "-DUNEXPECTED_SPVASM_CONTAINS=OpTypeRuntimeArray|OpCapability SampledImageArrayNonUniformIndexingEXT|NonUniformEXT"
      -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectVulkanSpvasmSnippets.cmake)
  add_test(NAME cglc_build_vulkan_graphics_resource_native
    COMMAND ${CMAKE_COMMAND}
      -DCGLC=$<TARGET_FILE:cglc>
      -DINPUT=${CROSSGL_VULKAN_GRAPHICS_RESOURCE_UNSUPPORTED_SHADER}
      -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-vulkan-graphics-resource.cglb
      -DEXPECTED_MODULE=VulkanGraphicsResourceUnsupportedShader
      -DEXPECTED_DESCRIPTOR_TYPE=VK_DESCRIPTOR_TYPE_SAMPLED_IMAGE
      "-DEXPECTED_MANIFEST_JSON_FIELDS=schemaVersion=1|target=vulkan|module=VulkanGraphicsResourceUnsupportedShader|artifacts.backendAssembly=backend/vulkan/VulkanGraphicsResourceUnsupportedShader.spvasm|artifacts.nativeBinary=backend/vulkan/VulkanGraphicsResourceUnsupportedShader.spv"
      "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=vulkan|module=VulkanGraphicsResourceUnsupportedShader|nativeBinary=backend/vulkan/VulkanGraphicsResourceUnsupportedShader.spv|resources.0.stage=vertex|resources.0.name=camera|resources.0.kind=uniform|resources.0.type=Camera|resources.0.binding=0|resources.1.stage=fragment|resources.1.name=albedo|resources.1.kind=texture|resources.1.type=sampler2D|resources.1.binding=1|resources.2.stage=fragment|resources.2.name=linearSampler|resources.2.kind=sampler|resources.2.type=sampler|resources.2.binding=2|entryPoints.0.stage=vertex|entryPoints.1.stage=fragment"
      "-DEXPECTED_REFLECTION_JSON_ARRAY_LENGTHS=entryPoints=2|resources=3|targetResourceBindings=3|vertexLayouts=1|workgroupSizes=0"
      "-DEXPECTED_REFLECTION_TARGET_FIELDS=camera.stage=vertex|camera.bindingClass=uniformBuffer|camera.descriptorType=VK_DESCRIPTOR_TYPE_UNIFORM_BUFFER|camera.storageClass=Uniform|camera.set=0|camera.binding=0|albedo.stage=fragment|albedo.bindingClass=sampledImage|albedo.descriptorType=VK_DESCRIPTOR_TYPE_SAMPLED_IMAGE|albedo.storageClass=UniformConstant|albedo.set=0|albedo.binding=1|linearSampler.stage=fragment|linearSampler.bindingClass=sampler|linearSampler.descriptorType=VK_DESCRIPTOR_TYPE_SAMPLER|linearSampler.storageClass=UniformConstant|linearSampler.set=0|linearSampler.binding=2"
      "-DEXPECTED_REFLECTION_FEATURE_FIELDS=vulkan-prototype-package.kind=backend|vertex-shader.kind=stage|fragment-shader.kind=stage|uniform-buffer.kind=resource|sampled-texture.kind=resource|sampler-state.kind=resource|local-declaration.kind=operation|vector-constructor.kind=operation"
      "-DEXPECTED_SPVASM_CONTAINS=OpDecorate %resource_vertex_camera DescriptorSet 0|OpDecorate %resource_vertex_camera Binding 0|OpDecorate %resource_fragment_albedo DescriptorSet 0|OpDecorate %resource_fragment_albedo Binding 1|OpDecorate %resource_fragment_linearSampler DescriptorSet 0|OpDecorate %resource_fragment_linearSampler Binding 2|OpTypeImage|OpTypeSampler|%resource_vertex_camera = OpVariable|%resource_fragment_albedo = OpVariable|%resource_fragment_linearSampler = OpVariable"
      -DEXPECTED_STORAGE_BUFFER_METADATA=FALSE
      -DMODE=vulkan-build
      -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
  add_test(NAME cglc_build_vulkan_graphics_texture_array_resource_native
    COMMAND ${CMAKE_COMMAND}
      -DCGLC=$<TARGET_FILE:cglc>
      -DINPUT=${CROSSGL_VULKAN_GRAPHICS_TEXTURE_ARRAY_UNSUPPORTED_SHADER}
      -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-vulkan-graphics-texture-array-resource.cglb
      -DEXPECTED_MODULE=VulkanGraphicsTextureArrayUnsupportedShader
      -DEXPECTED_DESCRIPTOR_TYPE=VK_DESCRIPTOR_TYPE_SAMPLED_IMAGE
      -DEXPECTED_RESOURCE_ARRAY_COUNT=2
      "-DEXPECTED_MANIFEST_JSON_FIELDS=schemaVersion=1|target=vulkan|module=VulkanGraphicsTextureArrayUnsupportedShader|artifacts.backendAssembly=backend/vulkan/VulkanGraphicsTextureArrayUnsupportedShader.spvasm|artifacts.nativeBinary=backend/vulkan/VulkanGraphicsTextureArrayUnsupportedShader.spv"
      "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=vulkan|module=VulkanGraphicsTextureArrayUnsupportedShader|nativeBinary=backend/vulkan/VulkanGraphicsTextureArrayUnsupportedShader.spv|resources.0.stage=fragment|resources.0.name=albedo|resources.0.kind=texture|resources.0.type=sampler2D[2]|resources.0.binding=1|resources.1.stage=fragment|resources.1.name=linearSampler|resources.1.kind=sampler|resources.1.type=sampler|resources.1.binding=2|entryPoints.0.stage=vertex|entryPoints.1.stage=fragment"
      "-DEXPECTED_REFLECTION_JSON_ARRAY_LENGTHS=entryPoints=2|resources=2|targetResourceBindings=2|vertexLayouts=1|workgroupSizes=0"
      "-DEXPECTED_REFLECTION_TARGET_FIELDS=albedo.stage=fragment|albedo.bindingClass=sampledImage|albedo.descriptorType=VK_DESCRIPTOR_TYPE_SAMPLED_IMAGE|albedo.storageClass=UniformConstant|albedo.set=0|albedo.binding=1|albedo.arrayElementCount=2|linearSampler.stage=fragment|linearSampler.bindingClass=sampler|linearSampler.descriptorType=VK_DESCRIPTOR_TYPE_SAMPLER|linearSampler.storageClass=UniformConstant|linearSampler.set=0|linearSampler.binding=2"
      "-DEXPECTED_REFLECTION_FEATURE_FIELDS=vulkan-prototype-package.kind=backend|vertex-shader.kind=stage|fragment-shader.kind=stage|sampled-texture.kind=resource|sampler-state.kind=resource|local-declaration.kind=operation|vector-constructor.kind=operation"
      "-DEXPECTED_SPVASM_CONTAINS=OpDecorate %resource_fragment_albedo DescriptorSet 0|OpDecorate %resource_fragment_albedo Binding 1|OpDecorate %resource_fragment_linearSampler DescriptorSet 0|OpDecorate %resource_fragment_linearSampler Binding 2|OpTypeArray|OpTypeImage|OpTypeSampler|%resource_fragment_albedo = OpVariable|%resource_fragment_linearSampler = OpVariable"
      -DEXPECTED_STORAGE_BUFFER_METADATA=FALSE
      -DMODE=vulkan-build
      -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
  add_test(NAME cglc_build_vulkan_graphics_vertex_texture_sampler_native
    COMMAND ${CMAKE_COMMAND}
      -DCGLC=$<TARGET_FILE:cglc>
      -DINPUT=${CROSSGL_VULKAN_GRAPHICS_VERTEX_TEXTURE_SAMPLER_SHADER}
      -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-vulkan-graphics-vertex-texture-sampler.cglb
      -DEXPECTED_MODULE=VulkanGraphicsVertexTextureSamplerShader
      -DEXPECTED_DESCRIPTOR_TYPE=VK_DESCRIPTOR_TYPE_SAMPLED_IMAGE
      "-DEXPECTED_MANIFEST_JSON_FIELDS=schemaVersion=1|target=vulkan|module=VulkanGraphicsVertexTextureSamplerShader|artifacts.backendAssembly=backend/vulkan/VulkanGraphicsVertexTextureSamplerShader.spvasm|artifacts.nativeBinary=backend/vulkan/VulkanGraphicsVertexTextureSamplerShader.spv"
      "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=vulkan|module=VulkanGraphicsVertexTextureSamplerShader|nativeBinary=backend/vulkan/VulkanGraphicsVertexTextureSamplerShader.spv|resources.0.stage=vertex|resources.0.name=heightMap|resources.0.kind=texture|resources.0.type=sampler2D|resources.0.binding=1|resources.1.stage=vertex|resources.1.name=linearSampler|resources.1.kind=sampler|resources.1.type=sampler|resources.1.binding=2|entryPoints.0.stage=vertex|entryPoints.1.stage=fragment"
      "-DEXPECTED_REFLECTION_JSON_ARRAY_LENGTHS=entryPoints=2|resources=2|targetResourceBindings=2|vertexLayouts=1|workgroupSizes=0"
      "-DEXPECTED_REFLECTION_TARGET_FIELDS=heightMap.stage=vertex|heightMap.bindingClass=sampledImage|heightMap.descriptorType=VK_DESCRIPTOR_TYPE_SAMPLED_IMAGE|heightMap.storageClass=UniformConstant|heightMap.set=0|heightMap.binding=1|linearSampler.stage=vertex|linearSampler.bindingClass=sampler|linearSampler.descriptorType=VK_DESCRIPTOR_TYPE_SAMPLER|linearSampler.storageClass=UniformConstant|linearSampler.set=0|linearSampler.binding=2"
      "-DEXPECTED_REFLECTION_FEATURE_FIELDS=vulkan-prototype-package.kind=backend|vertex-shader.kind=stage|fragment-shader.kind=stage|sampled-texture.kind=resource|sampler-state.kind=resource|texture-sample.kind=operation|texture-explicit-lod.kind=operation|local-declaration.kind=operation|vector-constructor.kind=operation"
      "-DEXPECTED_SPVASM_SNIPPET=OpImageSampleExplicitLod"
      -DEXPECTED_STORAGE_BUFFER_METADATA=FALSE
      -DMODE=vulkan-build
      -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
  add_test(NAME cglc_build_vulkan_graphics_vertex_texture_sampler_spvasm_native
    COMMAND ${CMAKE_COMMAND}
      -DCGLC=$<TARGET_FILE:cglc>
      -DINPUT=${CROSSGL_VULKAN_GRAPHICS_VERTEX_TEXTURE_SAMPLER_SHADER}
      -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-vulkan-graphics-vertex-texture-sampler-spvasm.cglb
      -DEXPECTED_MODULE=VulkanGraphicsVertexTextureSamplerShader
      "-DEXPECTED_SPVASM_CONTAINS=OpDecorate %resource_vertex_heightMap DescriptorSet 0|OpDecorate %resource_vertex_heightMap Binding 1|OpDecorate %resource_vertex_linearSampler DescriptorSet 0|OpDecorate %resource_vertex_linearSampler Binding 2|OpEntryPoint Vertex|%resource_vertex_heightMap = OpVariable|%resource_vertex_linearSampler = OpVariable|OpSampledImage|OpImageSampleExplicitLod|Lod %"
      "-DUNEXPECTED_SPVASM_CONTAINS=OpImageSampleImplicitLod|OpTypeRuntimeArray|OpCapability SampledImageArrayNonUniformIndexingEXT|NonUniformEXT"
      -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectVulkanSpvasmSnippets.cmake)
  add_test(NAME cglc_build_vulkan_graphics_vertex_shadow_compare_native
    COMMAND ${CMAKE_COMMAND}
      -DCGLC=$<TARGET_FILE:cglc>
      -DINPUT=${CROSSGL_VULKAN_GRAPHICS_VERTEX_SHADOW_COMPARE_SHADER}
      -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-vulkan-graphics-vertex-shadow-compare.cglb
      -DEXPECTED_MODULE=VulkanGraphicsVertexShadowCompareShader
      -DEXPECTED_DESCRIPTOR_TYPE=VK_DESCRIPTOR_TYPE_SAMPLED_IMAGE
      "-DEXPECTED_MANIFEST_JSON_FIELDS=schemaVersion=1|target=vulkan|module=VulkanGraphicsVertexShadowCompareShader|artifacts.backendAssembly=backend/vulkan/VulkanGraphicsVertexShadowCompareShader.spvasm|artifacts.nativeBinary=backend/vulkan/VulkanGraphicsVertexShadowCompareShader.spv"
      "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=vulkan|module=VulkanGraphicsVertexShadowCompareShader|nativeBinary=backend/vulkan/VulkanGraphicsVertexShadowCompareShader.spv|resources.0.stage=vertex|resources.0.name=shadowMap|resources.0.kind=texture|resources.0.type=sampler2DShadow|resources.0.binding=3|resources.1.stage=vertex|resources.1.name=shadowSampler|resources.1.kind=sampler|resources.1.type=comparison_sampler|resources.1.binding=4|entryPoints.0.stage=vertex|entryPoints.1.stage=fragment"
      "-DEXPECTED_REFLECTION_JSON_ARRAY_LENGTHS=entryPoints=2|resources=2|targetResourceBindings=2|vertexLayouts=1|workgroupSizes=0"
      "-DEXPECTED_REFLECTION_TARGET_FIELDS=shadowMap.stage=vertex|shadowMap.bindingClass=sampledImage|shadowMap.descriptorType=VK_DESCRIPTOR_TYPE_SAMPLED_IMAGE|shadowMap.storageClass=UniformConstant|shadowMap.set=0|shadowMap.binding=3|shadowSampler.stage=vertex|shadowSampler.bindingClass=sampler|shadowSampler.descriptorType=VK_DESCRIPTOR_TYPE_SAMPLER|shadowSampler.storageClass=UniformConstant|shadowSampler.set=0|shadowSampler.binding=4"
      "-DEXPECTED_REFLECTION_FEATURE_FIELDS=vulkan-prototype-package.kind=backend|vertex-shader.kind=stage|fragment-shader.kind=stage|sampled-texture.kind=resource|sampler-state.kind=resource|depth-compare-format.kind=texture|texture-shadow-compare-explicit-lod.kind=operation|local-declaration.kind=operation|vector-constructor.kind=operation"
      "-DEXPECTED_SPVASM_SNIPPET=OpImageSampleDrefExplicitLod"
      -DEXPECTED_STORAGE_BUFFER_METADATA=FALSE
      -DMODE=vulkan-build
      -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
  add_test(NAME cglc_build_vulkan_graphics_vertex_shadow_compare_spvasm_native
    COMMAND ${CMAKE_COMMAND}
      -DCGLC=$<TARGET_FILE:cglc>
      -DINPUT=${CROSSGL_VULKAN_GRAPHICS_VERTEX_SHADOW_COMPARE_SHADER}
      -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-vulkan-graphics-vertex-shadow-compare-spvasm.cglb
      -DEXPECTED_MODULE=VulkanGraphicsVertexShadowCompareShader
      "-DEXPECTED_SPVASM_CONTAINS=OpDecorate %resource_vertex_shadowMap DescriptorSet 0|OpDecorate %resource_vertex_shadowMap Binding 3|OpDecorate %resource_vertex_shadowSampler DescriptorSet 0|OpDecorate %resource_vertex_shadowSampler Binding 4|OpEntryPoint Vertex|2D 1 0 0 1 Unknown|%resource_vertex_shadowMap = OpVariable|%resource_vertex_shadowSampler = OpVariable|OpSampledImage|OpImageSampleDrefExplicitLod|Lod %"
      "-DUNEXPECTED_SPVASM_CONTAINS=OpImageSampleDrefImplicitLod|OpTypeRuntimeArray|OpCapability SampledImageArrayNonUniformIndexingEXT|NonUniformEXT"
      -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectVulkanSpvasmSnippets.cmake)
  add_test(NAME cglc_build_vulkan_graphics_texture_sampler_descriptor_array_native
    COMMAND ${CMAKE_COMMAND}
      -DCGLC=$<TARGET_FILE:cglc>
      -DINPUT=${CROSSGL_VULKAN_GRAPHICS_TEXTURE_SAMPLER_DESCRIPTOR_ARRAY_SHADER}
      -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-vulkan-graphics-texture-sampler-descriptor-array.cglb
      -DEXPECTED_MODULE=VulkanGraphicsTextureSamplerDescriptorArrayShader
      -DEXPECTED_DESCRIPTOR_TYPE=VK_DESCRIPTOR_TYPE_SAMPLED_IMAGE
      "-DEXPECTED_MANIFEST_JSON_FIELDS=schemaVersion=1|target=vulkan|module=VulkanGraphicsTextureSamplerDescriptorArrayShader|artifacts.backendAssembly=backend/vulkan/VulkanGraphicsTextureSamplerDescriptorArrayShader.spvasm|artifacts.nativeBinary=backend/vulkan/VulkanGraphicsTextureSamplerDescriptorArrayShader.spv"
      "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=vulkan|module=VulkanGraphicsTextureSamplerDescriptorArrayShader|nativeBinary=backend/vulkan/VulkanGraphicsTextureSamplerDescriptorArrayShader.spv|resources.0.name=albedoMaps|resources.0.kind=texture|resources.0.type=sampler2D[2]|resources.0.binding=1|resources.1.name=linearSamplers|resources.1.kind=sampler|resources.1.type=sampler[2]|resources.1.binding=2|entryPoints.0.stage=vertex|entryPoints.1.stage=fragment"
      "-DEXPECTED_REFLECTION_JSON_ARRAY_LENGTHS=entryPoints=2|resources=2|targetResourceBindings=2|vertexLayouts=1|workgroupSizes=0"
      "-DEXPECTED_REFLECTION_TARGET_FIELDS=albedoMaps.stage=fragment|albedoMaps.bindingClass=sampledImage|albedoMaps.descriptorType=VK_DESCRIPTOR_TYPE_SAMPLED_IMAGE|albedoMaps.storageClass=UniformConstant|albedoMaps.set=0|albedoMaps.binding=1|albedoMaps.arrayElementCount=2|linearSamplers.stage=fragment|linearSamplers.bindingClass=sampler|linearSamplers.descriptorType=VK_DESCRIPTOR_TYPE_SAMPLER|linearSamplers.storageClass=UniformConstant|linearSamplers.set=0|linearSamplers.binding=2|linearSamplers.arrayElementCount=2"
      "-DEXPECTED_REFLECTION_FEATURE_FIELDS=vulkan-prototype-package.kind=backend|vertex-shader.kind=stage|fragment-shader.kind=stage|sampled-texture.kind=resource|sampler-state.kind=resource|texture-sample.kind=operation|local-declaration.kind=operation|index-access.kind=operation"
      "-DEXPECTED_SPVASM_SNIPPET=OpTypeArray"
      -DEXPECTED_STORAGE_BUFFER_METADATA=FALSE
      -DMODE=vulkan-build
      -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
  add_test(NAME cglc_build_vulkan_graphics_texture_sampler_descriptor_array_spvasm_native
    COMMAND ${CMAKE_COMMAND}
      -DCGLC=$<TARGET_FILE:cglc>
      -DINPUT=${CROSSGL_VULKAN_GRAPHICS_TEXTURE_SAMPLER_DESCRIPTOR_ARRAY_SHADER}
      -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-vulkan-graphics-texture-sampler-descriptor-array-spvasm.cglb
      -DEXPECTED_MODULE=VulkanGraphicsTextureSamplerDescriptorArrayShader
      "-DEXPECTED_SPVASM_CONTAINS=OpDecorate %resource_fragment_albedoMaps DescriptorSet 0|OpDecorate %resource_fragment_albedoMaps Binding 1|OpDecorate %resource_fragment_linearSamplers DescriptorSet 0|OpDecorate %resource_fragment_linearSamplers Binding 2|OpTypeArray|%resource_fragment_albedoMaps = OpVariable|%resource_fragment_linearSamplers = OpVariable|OpAccessChain|OpSampledImage|OpImageSampleImplicitLod"
      "-DUNEXPECTED_SPVASM_CONTAINS=OpTypeRuntimeArray|OpCapability SampledImageArrayNonUniformIndexingEXT|NonUniformEXT"
      -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectVulkanSpvasmSnippets.cmake)
  add_test(NAME cglc_build_vulkan_graphics_nonuniform_descriptor_array_native
    COMMAND ${CMAKE_COMMAND}
      -DCGLC=$<TARGET_FILE:cglc>
      -DINPUT=${CROSSGL_VULKAN_GRAPHICS_NONUNIFORM_DESCRIPTOR_ARRAY_SHADER}
      -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-vulkan-graphics-nonuniform-descriptor-array.cglb
      -DEXPECTED_MODULE=VulkanGraphicsNonUniformDescriptorArrayShader
      -DEXPECTED_DESCRIPTOR_TYPE=VK_DESCRIPTOR_TYPE_SAMPLED_IMAGE
      "-DEXPECTED_MANIFEST_JSON_FIELDS=schemaVersion=1|target=vulkan|module=VulkanGraphicsNonUniformDescriptorArrayShader|artifacts.backendAssembly=backend/vulkan/VulkanGraphicsNonUniformDescriptorArrayShader.spvasm|artifacts.nativeBinary=backend/vulkan/VulkanGraphicsNonUniformDescriptorArrayShader.spv"
      "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=vulkan|module=VulkanGraphicsNonUniformDescriptorArrayShader|nativeBinary=backend/vulkan/VulkanGraphicsNonUniformDescriptorArrayShader.spv|resources.0.name=colorMaps|resources.0.kind=texture|resources.0.type=sampler2D[2]|resources.0.binding=2|resources.1.name=linearSamplers|resources.1.kind=sampler|resources.1.type=sampler[2]|resources.1.binding=5|entryPoints.0.stage=vertex|entryPoints.1.stage=fragment"
      "-DEXPECTED_REFLECTION_JSON_ARRAY_LENGTHS=entryPoints=2|resources=2|targetResourceBindings=2|vertexLayouts=1|workgroupSizes=0"
      "-DEXPECTED_REFLECTION_TARGET_FIELDS=colorMaps.stage=fragment|colorMaps.bindingClass=sampledImage|colorMaps.descriptorType=VK_DESCRIPTOR_TYPE_SAMPLED_IMAGE|colorMaps.storageClass=UniformConstant|colorMaps.set=0|colorMaps.binding=2|colorMaps.arrayElementCount=2|linearSamplers.stage=fragment|linearSamplers.bindingClass=sampler|linearSamplers.descriptorType=VK_DESCRIPTOR_TYPE_SAMPLER|linearSamplers.storageClass=UniformConstant|linearSamplers.set=0|linearSamplers.binding=5|linearSamplers.arrayElementCount=2"
      "-DEXPECTED_REFLECTION_FEATURE_FIELDS=vulkan-prototype-package.kind=backend|vertex-shader.kind=stage|fragment-shader.kind=stage|sampled-texture.kind=resource|sampler-state.kind=resource|texture-sample.kind=operation|nonuniform-descriptor-index.kind=operation|nonuniform-texture-descriptor-index.kind=operation|nonuniform-sampler-descriptor-index.kind=operation|index-access.kind=operation"
      "-DEXPECTED_SPVASM_SNIPPET=NonUniformEXT"
      -DEXPECTED_STORAGE_BUFFER_METADATA=FALSE
      -DMODE=vulkan-build
      -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
  add_test(NAME cglc_build_vulkan_graphics_nonuniform_descriptor_array_spvasm_native
    COMMAND ${CMAKE_COMMAND}
      -DCGLC=$<TARGET_FILE:cglc>
      -DINPUT=${CROSSGL_VULKAN_GRAPHICS_NONUNIFORM_DESCRIPTOR_ARRAY_SHADER}
      -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-vulkan-graphics-nonuniform-descriptor-array-spvasm.cglb
      -DEXPECTED_MODULE=VulkanGraphicsNonUniformDescriptorArrayShader
      "-DEXPECTED_SPVASM_CONTAINS=OpExtension \"SPV_EXT_descriptor_indexing\"|OpCapability ShaderNonUniformEXT|OpCapability SampledImageArrayNonUniformIndexingEXT|OpDecorate %resource_fragment_colorMaps DescriptorSet 0|OpDecorate %resource_fragment_colorMaps Binding 2|OpDecorate %resource_fragment_linearSamplers DescriptorSet 0|OpDecorate %resource_fragment_linearSamplers Binding 5|OpDecorate %|NonUniformEXT|OpTypeArray|%resource_fragment_colorMaps = OpVariable|%resource_fragment_linearSamplers = OpVariable|OpAccessChain|OpSampledImage|OpImageSampleImplicitLod"
      "-DUNEXPECTED_SPVASM_CONTAINS=OpTypeRuntimeArray|OpCapability StorageBufferArrayNonUniformIndexingEXT"
      -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectVulkanSpvasmSnippets.cmake)
  add_test(NAME cglc_build_vulkan_graphics_shadow_compare_native
    COMMAND ${CMAKE_COMMAND}
      -DCGLC=$<TARGET_FILE:cglc>
      -DINPUT=${CROSSGL_VULKAN_GRAPHICS_SHADOW_COMPARE_SHADER}
      -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-vulkan-graphics-shadow-compare.cglb
      -DEXPECTED_MODULE=VulkanGraphicsShadowCompareShader
      -DEXPECTED_DESCRIPTOR_TYPE=VK_DESCRIPTOR_TYPE_SAMPLED_IMAGE
      "-DEXPECTED_MANIFEST_JSON_FIELDS=schemaVersion=1|target=vulkan|module=VulkanGraphicsShadowCompareShader|artifacts.backendAssembly=backend/vulkan/VulkanGraphicsShadowCompareShader.spvasm|artifacts.nativeBinary=backend/vulkan/VulkanGraphicsShadowCompareShader.spv"
      "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=vulkan|module=VulkanGraphicsShadowCompareShader|nativeBinary=backend/vulkan/VulkanGraphicsShadowCompareShader.spv|resources.0.name=shadowMap|resources.0.kind=texture|resources.0.type=sampler2DShadow|resources.0.binding=2|resources.1.name=shadowSampler|resources.1.kind=sampler|resources.1.type=comparison_sampler|resources.1.binding=3|entryPoints.0.stage=vertex|entryPoints.1.stage=fragment"
      "-DEXPECTED_REFLECTION_JSON_ARRAY_LENGTHS=entryPoints=2|resources=2|targetResourceBindings=2|vertexLayouts=1|workgroupSizes=0"
      "-DEXPECTED_REFLECTION_TARGET_FIELDS=shadowMap.stage=fragment|shadowMap.bindingClass=sampledImage|shadowMap.descriptorType=VK_DESCRIPTOR_TYPE_SAMPLED_IMAGE|shadowMap.storageClass=UniformConstant|shadowMap.set=0|shadowMap.binding=2|shadowSampler.stage=fragment|shadowSampler.bindingClass=sampler|shadowSampler.descriptorType=VK_DESCRIPTOR_TYPE_SAMPLER|shadowSampler.storageClass=UniformConstant|shadowSampler.set=0|shadowSampler.binding=3"
      "-DEXPECTED_REFLECTION_FEATURE_FIELDS=vulkan-prototype-package.kind=backend|vertex-shader.kind=stage|fragment-shader.kind=stage|sampled-texture.kind=resource|sampler-state.kind=resource|depth-compare-format.kind=texture|texture-shadow-compare.kind=operation|local-declaration.kind=operation|vector-constructor.kind=operation"
      "-DEXPECTED_SPVASM_SNIPPET=OpImageSampleDrefImplicitLod"
      -DEXPECTED_STORAGE_BUFFER_METADATA=FALSE
      -DMODE=vulkan-build
      -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
  add_test(NAME cglc_build_vulkan_graphics_shadow_compare_spvasm_native
    COMMAND ${CMAKE_COMMAND}
      -DCGLC=$<TARGET_FILE:cglc>
      -DINPUT=${CROSSGL_VULKAN_GRAPHICS_SHADOW_COMPARE_SHADER}
      -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-vulkan-graphics-shadow-compare-spvasm.cglb
      -DEXPECTED_MODULE=VulkanGraphicsShadowCompareShader
      "-DEXPECTED_SPVASM_CONTAINS=OpDecorate %resource_fragment_shadowMap DescriptorSet 0|OpDecorate %resource_fragment_shadowMap Binding 2|OpDecorate %resource_fragment_shadowSampler DescriptorSet 0|OpDecorate %resource_fragment_shadowSampler Binding 3|OpTypeImage|2D 1 0 0 1 Unknown|OpTypeSampler|OpTypeSampledImage|%resource_fragment_shadowMap = OpVariable|%resource_fragment_shadowSampler = OpVariable|OpSampledImage|OpImageSampleDrefImplicitLod"
      "-DUNEXPECTED_SPVASM_CONTAINS=OpImageSampleDrefExplicitLod|OpTypeRuntimeArray|OpCapability SampledImageArrayNonUniformIndexingEXT|NonUniformEXT"
      -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectVulkanSpvasmSnippets.cmake)
  add_test(NAME cglc_build_vulkan_graphics_shadow_compare_lod_native
    COMMAND ${CMAKE_COMMAND}
      -DCGLC=$<TARGET_FILE:cglc>
      -DINPUT=${CROSSGL_VULKAN_GRAPHICS_SHADOW_COMPARE_LOD_SHADER}
      -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-vulkan-graphics-shadow-compare-lod.cglb
      -DEXPECTED_MODULE=VulkanGraphicsShadowCompareLodShader
      -DEXPECTED_DESCRIPTOR_TYPE=VK_DESCRIPTOR_TYPE_SAMPLED_IMAGE
      "-DEXPECTED_MANIFEST_JSON_FIELDS=schemaVersion=1|target=vulkan|module=VulkanGraphicsShadowCompareLodShader|artifacts.backendAssembly=backend/vulkan/VulkanGraphicsShadowCompareLodShader.spvasm|artifacts.nativeBinary=backend/vulkan/VulkanGraphicsShadowCompareLodShader.spv"
      "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=vulkan|module=VulkanGraphicsShadowCompareLodShader|nativeBinary=backend/vulkan/VulkanGraphicsShadowCompareLodShader.spv|resources.0.name=shadowMap|resources.0.kind=texture|resources.0.type=sampler2DShadow|resources.0.binding=2|resources.1.name=shadowSampler|resources.1.kind=sampler|resources.1.type=comparison_sampler|resources.1.binding=3|entryPoints.0.stage=vertex|entryPoints.1.stage=fragment"
      "-DEXPECTED_REFLECTION_JSON_ARRAY_LENGTHS=entryPoints=2|resources=2|targetResourceBindings=2|vertexLayouts=1|workgroupSizes=0"
      "-DEXPECTED_REFLECTION_TARGET_FIELDS=shadowMap.stage=fragment|shadowMap.bindingClass=sampledImage|shadowMap.descriptorType=VK_DESCRIPTOR_TYPE_SAMPLED_IMAGE|shadowMap.storageClass=UniformConstant|shadowMap.set=0|shadowMap.binding=2|shadowSampler.stage=fragment|shadowSampler.bindingClass=sampler|shadowSampler.descriptorType=VK_DESCRIPTOR_TYPE_SAMPLER|shadowSampler.storageClass=UniformConstant|shadowSampler.set=0|shadowSampler.binding=3"
      "-DEXPECTED_REFLECTION_FEATURE_FIELDS=vulkan-prototype-package.kind=backend|vertex-shader.kind=stage|fragment-shader.kind=stage|sampled-texture.kind=resource|sampler-state.kind=resource|depth-compare-format.kind=texture|texture-shadow-compare.kind=operation|texture-shadow-compare-explicit-lod.kind=operation|local-declaration.kind=operation|vector-constructor.kind=operation"
      "-DEXPECTED_SPVASM_SNIPPET=OpImageSampleDrefExplicitLod"
      -DEXPECTED_STORAGE_BUFFER_METADATA=FALSE
      -DMODE=vulkan-build
      -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
  add_test(NAME cglc_build_vulkan_graphics_shadow_compare_lod_spvasm_native
    COMMAND ${CMAKE_COMMAND}
      -DCGLC=$<TARGET_FILE:cglc>
      -DINPUT=${CROSSGL_VULKAN_GRAPHICS_SHADOW_COMPARE_LOD_SHADER}
      -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-vulkan-graphics-shadow-compare-lod-spvasm.cglb
      -DEXPECTED_MODULE=VulkanGraphicsShadowCompareLodShader
      "-DEXPECTED_SPVASM_CONTAINS=OpDecorate %resource_fragment_shadowMap DescriptorSet 0|OpDecorate %resource_fragment_shadowMap Binding 2|OpDecorate %resource_fragment_shadowSampler DescriptorSet 0|OpDecorate %resource_fragment_shadowSampler Binding 3|OpTypeImage|2D 1 0 0 1 Unknown|OpTypeSampler|OpTypeSampledImage|%resource_fragment_shadowMap = OpVariable|%resource_fragment_shadowSampler = OpVariable|OpSampledImage|OpImageSampleDrefExplicitLod|Lod %"
      "-DUNEXPECTED_SPVASM_CONTAINS=OpImageSampleDrefImplicitLod|OpTypeRuntimeArray|OpCapability SampledImageArrayNonUniformIndexingEXT|NonUniformEXT"
      -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectVulkanSpvasmSnippets.cmake)
  add_test(NAME cglc_build_vulkan_graphics_shadow_array_native
    COMMAND ${CMAKE_COMMAND}
      -DCGLC=$<TARGET_FILE:cglc>
      -DINPUT=${CROSSGL_VULKAN_GRAPHICS_SHADOW_ARRAY_UNSUPPORTED_SHADER}
      -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-vulkan-graphics-shadow-array.cglb
      -DEXPECTED_MODULE=VulkanGraphicsShadowArrayUnsupportedShader
      -DEXPECTED_DESCRIPTOR_TYPE=VK_DESCRIPTOR_TYPE_SAMPLED_IMAGE
      "-DEXPECTED_MANIFEST_JSON_FIELDS=schemaVersion=1|target=vulkan|module=VulkanGraphicsShadowArrayUnsupportedShader|artifacts.backendAssembly=backend/vulkan/VulkanGraphicsShadowArrayUnsupportedShader.spvasm|artifacts.nativeBinary=backend/vulkan/VulkanGraphicsShadowArrayUnsupportedShader.spv"
      "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=vulkan|module=VulkanGraphicsShadowArrayUnsupportedShader|nativeBinary=backend/vulkan/VulkanGraphicsShadowArrayUnsupportedShader.spv|resources.0.name=shadowAtlas|resources.0.kind=texture|resources.0.type=sampler2DArrayShadow|resources.0.binding=2|resources.1.name=shadowSampler|resources.1.kind=sampler|resources.1.type=comparison_sampler|resources.1.binding=3|entryPoints.0.stage=vertex|entryPoints.1.stage=fragment"
      "-DEXPECTED_REFLECTION_JSON_ARRAY_LENGTHS=entryPoints=2|resources=2|targetResourceBindings=2|vertexLayouts=1|workgroupSizes=0"
      "-DEXPECTED_REFLECTION_TARGET_FIELDS=shadowAtlas.stage=fragment|shadowAtlas.bindingClass=sampledImage|shadowAtlas.descriptorType=VK_DESCRIPTOR_TYPE_SAMPLED_IMAGE|shadowAtlas.storageClass=UniformConstant|shadowAtlas.set=0|shadowAtlas.binding=2|shadowSampler.stage=fragment|shadowSampler.bindingClass=sampler|shadowSampler.descriptorType=VK_DESCRIPTOR_TYPE_SAMPLER|shadowSampler.storageClass=UniformConstant|shadowSampler.set=0|shadowSampler.binding=3"
      "-DEXPECTED_REFLECTION_FEATURE_FIELDS=vulkan-prototype-package.kind=backend|vertex-shader.kind=stage|fragment-shader.kind=stage|sampled-texture.kind=resource|sampler-state.kind=resource|depth-compare-format.kind=texture|texture-shadow-compare.kind=operation|local-declaration.kind=operation|vector-constructor.kind=operation"
      "-DEXPECTED_SPVASM_SNIPPET=OpImageSampleDrefImplicitLod"
      -DEXPECTED_STORAGE_BUFFER_METADATA=FALSE
      -DMODE=vulkan-build
      -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
  add_test(NAME cglc_build_vulkan_graphics_shadow_array_spvasm_native
    COMMAND ${CMAKE_COMMAND}
      -DCGLC=$<TARGET_FILE:cglc>
      -DINPUT=${CROSSGL_VULKAN_GRAPHICS_SHADOW_ARRAY_UNSUPPORTED_SHADER}
      -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-vulkan-graphics-shadow-array-spvasm.cglb
      -DEXPECTED_MODULE=VulkanGraphicsShadowArrayUnsupportedShader
      "-DEXPECTED_SPVASM_CONTAINS=OpDecorate %resource_fragment_shadowAtlas DescriptorSet 0|OpDecorate %resource_fragment_shadowAtlas Binding 2|OpDecorate %resource_fragment_shadowSampler DescriptorSet 0|OpDecorate %resource_fragment_shadowSampler Binding 3|OpTypeImage|2D 1 1 0 1 Unknown|OpTypeSampler|OpTypeSampledImage|%resource_fragment_shadowAtlas = OpVariable|%resource_fragment_shadowSampler = OpVariable|OpSampledImage|OpImageSampleDrefImplicitLod"
      "-DUNEXPECTED_SPVASM_CONTAINS=OpImageSampleDrefExplicitLod|OpTypeRuntimeArray|OpCapability SampledImageArrayNonUniformIndexingEXT|NonUniformEXT"
      -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectVulkanSpvasmSnippets.cmake)
  add_test(NAME cglc_build_vulkan_graphics_shadow_array_lod_native
    COMMAND ${CMAKE_COMMAND}
      -DCGLC=$<TARGET_FILE:cglc>
      -DINPUT=${CROSSGL_VULKAN_GRAPHICS_SHADOW_ARRAY_LOD_UNSUPPORTED_SHADER}
      -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-vulkan-graphics-shadow-array-lod.cglb
      -DEXPECTED_MODULE=VulkanGraphicsShadowArrayLodUnsupportedShader
      -DEXPECTED_DESCRIPTOR_TYPE=VK_DESCRIPTOR_TYPE_SAMPLED_IMAGE
      "-DEXPECTED_MANIFEST_JSON_FIELDS=schemaVersion=1|target=vulkan|module=VulkanGraphicsShadowArrayLodUnsupportedShader|artifacts.backendAssembly=backend/vulkan/VulkanGraphicsShadowArrayLodUnsupportedShader.spvasm|artifacts.nativeBinary=backend/vulkan/VulkanGraphicsShadowArrayLodUnsupportedShader.spv"
      "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=vulkan|module=VulkanGraphicsShadowArrayLodUnsupportedShader|nativeBinary=backend/vulkan/VulkanGraphicsShadowArrayLodUnsupportedShader.spv|resources.0.name=shadowAtlas|resources.0.kind=texture|resources.0.type=sampler2DArrayShadow|resources.0.binding=2|resources.1.name=shadowSampler|resources.1.kind=sampler|resources.1.type=comparison_sampler|resources.1.binding=3|entryPoints.0.stage=vertex|entryPoints.1.stage=fragment"
      "-DEXPECTED_REFLECTION_JSON_ARRAY_LENGTHS=entryPoints=2|resources=2|targetResourceBindings=2|vertexLayouts=1|workgroupSizes=0"
      "-DEXPECTED_REFLECTION_TARGET_FIELDS=shadowAtlas.stage=fragment|shadowAtlas.bindingClass=sampledImage|shadowAtlas.descriptorType=VK_DESCRIPTOR_TYPE_SAMPLED_IMAGE|shadowAtlas.storageClass=UniformConstant|shadowAtlas.set=0|shadowAtlas.binding=2|shadowSampler.stage=fragment|shadowSampler.bindingClass=sampler|shadowSampler.descriptorType=VK_DESCRIPTOR_TYPE_SAMPLER|shadowSampler.storageClass=UniformConstant|shadowSampler.set=0|shadowSampler.binding=3"
      "-DEXPECTED_REFLECTION_FEATURE_FIELDS=vulkan-prototype-package.kind=backend|vertex-shader.kind=stage|fragment-shader.kind=stage|sampled-texture.kind=resource|sampler-state.kind=resource|depth-compare-format.kind=texture|texture-shadow-compare.kind=operation|texture-shadow-compare-explicit-lod.kind=operation|local-declaration.kind=operation|vector-constructor.kind=operation"
      "-DEXPECTED_SPVASM_SNIPPET=OpImageSampleDrefExplicitLod"
      -DEXPECTED_STORAGE_BUFFER_METADATA=FALSE
      -DMODE=vulkan-build
      -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
  add_test(NAME cglc_build_vulkan_graphics_shadow_array_lod_spvasm_native
    COMMAND ${CMAKE_COMMAND}
      -DCGLC=$<TARGET_FILE:cglc>
      -DINPUT=${CROSSGL_VULKAN_GRAPHICS_SHADOW_ARRAY_LOD_UNSUPPORTED_SHADER}
      -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-vulkan-graphics-shadow-array-lod-spvasm.cglb
      -DEXPECTED_MODULE=VulkanGraphicsShadowArrayLodUnsupportedShader
      "-DEXPECTED_SPVASM_CONTAINS=OpDecorate %resource_fragment_shadowAtlas DescriptorSet 0|OpDecorate %resource_fragment_shadowAtlas Binding 2|OpDecorate %resource_fragment_shadowSampler DescriptorSet 0|OpDecorate %resource_fragment_shadowSampler Binding 3|OpTypeImage|2D 1 1 0 1 Unknown|OpTypeSampler|OpTypeSampledImage|%resource_fragment_shadowAtlas = OpVariable|%resource_fragment_shadowSampler = OpVariable|OpSampledImage|OpImageSampleDrefExplicitLod|Lod %"
      "-DUNEXPECTED_SPVASM_CONTAINS=OpImageSampleDrefImplicitLod|OpTypeRuntimeArray|OpCapability SampledImageArrayNonUniformIndexingEXT|NonUniformEXT"
      -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectVulkanSpvasmSnippets.cmake)
  add_test(NAME cglc_build_vulkan_graphics_shadow_descriptor_array_native
    COMMAND ${CMAKE_COMMAND}
      -DCGLC=$<TARGET_FILE:cglc>
      -DINPUT=${CROSSGL_VULKAN_GRAPHICS_SHADOW_DESCRIPTOR_ARRAY_SHADER}
      -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-vulkan-graphics-shadow-descriptor-array.cglb
      -DEXPECTED_MODULE=VulkanGraphicsShadowDescriptorArrayShader
      -DEXPECTED_DESCRIPTOR_TYPE=VK_DESCRIPTOR_TYPE_SAMPLED_IMAGE
      "-DEXPECTED_MANIFEST_JSON_FIELDS=schemaVersion=1|target=vulkan|module=VulkanGraphicsShadowDescriptorArrayShader|artifacts.backendAssembly=backend/vulkan/VulkanGraphicsShadowDescriptorArrayShader.spvasm|artifacts.nativeBinary=backend/vulkan/VulkanGraphicsShadowDescriptorArrayShader.spv"
      "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=vulkan|module=VulkanGraphicsShadowDescriptorArrayShader|nativeBinary=backend/vulkan/VulkanGraphicsShadowDescriptorArrayShader.spv|resources.0.name=shadowMaps|resources.0.kind=texture|resources.0.type=sampler2DShadow[2]|resources.0.binding=2|resources.1.name=shadowSamplers|resources.1.kind=sampler|resources.1.type=comparison_sampler[2]|resources.1.binding=3|entryPoints.0.stage=vertex|entryPoints.1.stage=fragment"
      "-DEXPECTED_REFLECTION_JSON_ARRAY_LENGTHS=entryPoints=2|resources=2|targetResourceBindings=2|vertexLayouts=1|workgroupSizes=0"
      "-DEXPECTED_REFLECTION_TARGET_FIELDS=shadowMaps.stage=fragment|shadowMaps.bindingClass=sampledImage|shadowMaps.descriptorType=VK_DESCRIPTOR_TYPE_SAMPLED_IMAGE|shadowMaps.storageClass=UniformConstant|shadowMaps.set=0|shadowMaps.binding=2|shadowMaps.arrayElementCount=2|shadowSamplers.stage=fragment|shadowSamplers.bindingClass=sampler|shadowSamplers.descriptorType=VK_DESCRIPTOR_TYPE_SAMPLER|shadowSamplers.storageClass=UniformConstant|shadowSamplers.set=0|shadowSamplers.binding=3|shadowSamplers.arrayElementCount=2"
      "-DEXPECTED_REFLECTION_FEATURE_FIELDS=vulkan-prototype-package.kind=backend|vertex-shader.kind=stage|fragment-shader.kind=stage|sampled-texture.kind=resource|sampler-state.kind=resource|depth-compare-format.kind=texture|texture-shadow-compare.kind=operation|texture-shadow-compare-explicit-lod.kind=operation|local-declaration.kind=operation|index-access.kind=operation"
      "-DEXPECTED_SPVASM_SNIPPET=OpImageSampleDrefExplicitLod"
      -DEXPECTED_STORAGE_BUFFER_METADATA=FALSE
      -DMODE=vulkan-build
      -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
  add_test(NAME cglc_build_vulkan_graphics_shadow_descriptor_array_spvasm_native
    COMMAND ${CMAKE_COMMAND}
      -DCGLC=$<TARGET_FILE:cglc>
      -DINPUT=${CROSSGL_VULKAN_GRAPHICS_SHADOW_DESCRIPTOR_ARRAY_SHADER}
      -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-vulkan-graphics-shadow-descriptor-array-spvasm.cglb
      -DEXPECTED_MODULE=VulkanGraphicsShadowDescriptorArrayShader
      "-DEXPECTED_SPVASM_CONTAINS=OpDecorate %resource_fragment_shadowMaps DescriptorSet 0|OpDecorate %resource_fragment_shadowMaps Binding 2|OpDecorate %resource_fragment_shadowSamplers DescriptorSet 0|OpDecorate %resource_fragment_shadowSamplers Binding 3|OpTypeArray|2D 1 0 0 1 Unknown|OpTypeSampledImage|%resource_fragment_shadowMaps = OpVariable|%resource_fragment_shadowSamplers = OpVariable|OpAccessChain|OpSampledImage|OpImageSampleDrefExplicitLod|Lod %"
      "-DUNEXPECTED_SPVASM_CONTAINS=OpImageSampleDrefImplicitLod|OpTypeRuntimeArray|OpCapability SampledImageArrayNonUniformIndexingEXT|NonUniformEXT"
      -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectVulkanSpvasmSnippets.cmake)
  crossgl_label_optional_native_test(cglc_build_vulkan_graphics_native vulkan)
  crossgl_label_optional_native_test(
    cglc_build_vulkan_graphics_uniform_buffer_native vulkan)
  crossgl_label_optional_native_test(
    cglc_build_vulkan_graphics_uniform_buffer_spvasm_native vulkan)
  crossgl_label_optional_native_test(
    cglc_build_vulkan_graphics_math_intrinsic_spvasm_native vulkan)
  crossgl_label_optional_native_test(
    cglc_build_vulkan_graphics_math_intrinsic_native vulkan)
  crossgl_label_optional_native_test(cglc_build_vulkan_graphics_loop_native
                                     vulkan)
  crossgl_label_optional_native_test(
    cglc_build_vulkan_graphics_loop_spvasm_native vulkan)
  crossgl_label_optional_native_test(
    cglc_build_vulkan_graphics_loop_control_native vulkan)
  crossgl_label_optional_native_test(
    cglc_build_vulkan_graphics_loop_control_spvasm_native vulkan)
  crossgl_label_optional_native_test(
    cglc_build_vulkan_graphics_helper_function_native vulkan)
  crossgl_label_optional_native_test(
    cglc_build_vulkan_graphics_helper_function_spvasm_native vulkan)
  crossgl_label_optional_native_test(
    cglc_build_vulkan_graphics_texture_sampler_native vulkan)
  crossgl_label_optional_native_test(
    cglc_build_vulkan_graphics_texture_sampler_spvasm_native vulkan)
  crossgl_label_optional_native_test(
    cglc_build_vulkan_graphics_resource_native vulkan)
  crossgl_label_optional_native_test(
    cglc_build_vulkan_graphics_texture_array_resource_native vulkan)
  crossgl_label_optional_native_test(
    cglc_build_vulkan_graphics_vertex_texture_sampler_native vulkan)
  crossgl_label_optional_native_test(
    cglc_build_vulkan_graphics_vertex_texture_sampler_spvasm_native vulkan)
  crossgl_label_optional_native_test(
    cglc_build_vulkan_graphics_vertex_shadow_compare_native vulkan)
  crossgl_label_optional_native_test(
    cglc_build_vulkan_graphics_vertex_shadow_compare_spvasm_native vulkan)
  crossgl_label_optional_native_test(
    cglc_build_vulkan_graphics_texture_sampler_descriptor_array_native vulkan)
  crossgl_label_optional_native_test(
    cglc_build_vulkan_graphics_texture_sampler_descriptor_array_spvasm_native vulkan)
  crossgl_label_optional_native_test(
    cglc_build_vulkan_graphics_nonuniform_descriptor_array_native vulkan)
  crossgl_label_optional_native_test(
    cglc_build_vulkan_graphics_nonuniform_descriptor_array_spvasm_native vulkan)
  crossgl_label_optional_native_test(
    cglc_build_vulkan_graphics_shadow_compare_native vulkan)
  crossgl_label_optional_native_test(
    cglc_build_vulkan_graphics_shadow_compare_spvasm_native vulkan)
  crossgl_label_optional_native_test(
    cglc_build_vulkan_graphics_shadow_compare_lod_native vulkan)
  crossgl_label_optional_native_test(
    cglc_build_vulkan_graphics_shadow_compare_lod_spvasm_native vulkan)
  crossgl_label_optional_native_test(
    cglc_build_vulkan_graphics_shadow_array_native vulkan)
  crossgl_label_optional_native_test(
    cglc_build_vulkan_graphics_shadow_array_spvasm_native vulkan)
  crossgl_label_optional_native_test(
    cglc_build_vulkan_graphics_shadow_array_lod_native vulkan)
  crossgl_label_optional_native_test(
    cglc_build_vulkan_graphics_shadow_array_lod_spvasm_native vulkan)
  crossgl_label_optional_native_test(
    cglc_build_vulkan_graphics_shadow_descriptor_array_native vulkan)
  crossgl_label_optional_native_test(
    cglc_build_vulkan_graphics_shadow_descriptor_array_spvasm_native vulkan)
endif()
add_test(NAME cglc_build_vulkan_function_parameter_array_planned_failure
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_VULKAN_FUNCTION_PARAMETER_ARRAY_UNSUPPORTED_SHADER}
    -DTARGET=vulkan
    -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-vulkan-function-parameter-array.cglb
    -DMODE=planned-build-failure
    ${CROSSGL_TARGET_NOT_IMPLEMENTED_DIAGNOSTIC_EXPECTATIONS}
    "-DEXPECTED_DIAGNOSTICS_JSON_FIELDS=diagnostics.0.target=vulkan"
    "-DEXPECTED_DIAGNOSTIC_ARRAY_CONTAINS=missingCapabilities=vulkan.backend.vulkan-prototype-package|missingCapabilities=vulkan.diagnostic.vulkan.prototype-unsupported-function-parameter-array"
    "-DEXPECTED_DIAGNOSTIC_FIELD_CONTAINS=message=target 'vulkan' cannot build a package for this module|message=vulkan.backend.vulkan-prototype-package|message=vulkan.diagnostic.vulkan.prototype-unsupported-function-parameter-array"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
set(CROSSGL_DIRECTX_FUNCTION_PARAMETER_STRUCT_ARRAY_SOURCE_SNIPPET [=[void consumePayloads(Payload payloads[COUNT]) {
  float weight = payloads[0].weights[0];
  particles[1].mass = weight;
  return;
}

void consumeMaps(Texture2D<float4> maps[COUNT]) {
  return;
}

[numthreads(1, 1, 1)]
void compute_main(uint3 crossgl_GlobalInvocationID : SV_DispatchThreadID) {
  consumePayloads(particles[0].payloads);
  consumeMaps(colorMaps);
  return;]=])
add_test(NAME cglc_build_directx_function_parameter_struct_array_source_package
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_DIRECTX_FUNCTION_PARAMETER_ARRAY_UNSUPPORTED_SHADER}
    -DTARGET=directx
    -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-directx-function-parameter-struct-array.cglb
    -DMODE=source-package-build
    -DEXPECTED_SOURCE=backend/directx/DirectXFunctionParameterArrayUnsupportedShader.hlsl
    "-DEXPECTED_SOURCE_SNIPPET=${CROSSGL_DIRECTX_FUNCTION_PARAMETER_STRUCT_ARRAY_SOURCE_SNIPPET}"
    "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=directx|module=DirectXFunctionParameterArrayUnsupportedShader|nativeBinary=backend/directx/DirectXFunctionParameterArrayUnsupportedShader.dxil|functionConstants.0.name=COUNT|functionConstants.0.value=2|resources.0.name=particles|resources.0.kind=buffer|resources.0.type=Particle*|resources.0.binding=0|resources.1.name=colorMaps|resources.1.kind=texture|resources.1.type=sampler2D[COUNT]|resources.1.arrayDimensions.0.kind=fixed|resources.1.arrayDimensions.0.elementCount=2|workgroupSizes.0.entryPoint=compute_main|workgroupSizes.0.x=1|workgroupSizes.0.y=1|workgroupSizes.0.z=1"
    "-DEXPECTED_REFLECTION_JSON_ARRAY_LENGTHS=resources=2|targetResourceBindings=2|functionConstants=1|workgroupSizes=1"
    "-DEXPECTED_REFLECTION_TARGET_FIELDS=particles.stage=compute|particles.entryPoint=compute_main|particles.sourceType=Particle*|particles.hlslType=RWStructuredBuffer<Particle>|particles.addressSpace=unordered-access|particles.abi=registerBinding|particles.bindingClass=uav|particles.descriptorType=UAV|particles.argumentIndex=0|particles.set=0|particles.binding=0|colorMaps.stage=compute|colorMaps.entryPoint=compute_main|colorMaps.sourceType=sampler2D[COUNT]|colorMaps.hlslType=Texture2D<float4>|colorMaps.addressSpace=shader-resource|colorMaps.abi=registerBinding|colorMaps.bindingClass=srv|colorMaps.descriptorType=SRV|colorMaps.argumentIndex=2|colorMaps.set=0|colorMaps.binding=2|colorMaps.arraySize=COUNT|colorMaps.arrayElementCount=2"
    "-DEXPECTED_REFLECTION_FEATURE_FIELDS=hlsl-lowering.kind=backend|fixed-array.kind=layout|fixed-array-field.kind=layout|descriptor-array.kind=resource|function-parameter-array.kind=array|compute-kernel.kind=stage|workgroup-size.kind=execution|storage-buffer.kind=resource|sampled-texture.kind=resource|storage-buffer-write.kind=operation|index-access.kind=operation"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
set(CROSSGL_DIRECTX_FUNCTION_PARAMETER_RESOURCE_ARRAY_SOURCE_SNIPPET [=[void consumeMaps(Texture2D<float4> maps[COUNT]) {
  return;
}

[numthreads(1, 1, 1)]
void compute_main(uint3 crossgl_GlobalInvocationID : SV_DispatchThreadID) {
  consumeMaps(colorMaps);
  values[0] = float4(1.0, 0.0, 0.0, 1.0);]=])
add_test(NAME cglc_build_directx_function_parameter_resource_array_source_package
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_DIRECTX_FUNCTION_PARAMETER_RESOURCE_ARRAY_SHADER}
    -DTARGET=directx
    -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-directx-function-parameter-resource-array.cglb
    -DMODE=source-package-build
    -DEXPECTED_SOURCE=backend/directx/DirectXFunctionParameterResourceArrayShader.hlsl
    "-DEXPECTED_SOURCE_SNIPPET=${CROSSGL_DIRECTX_FUNCTION_PARAMETER_RESOURCE_ARRAY_SOURCE_SNIPPET}"
    "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=directx|module=DirectXFunctionParameterResourceArrayShader|nativeBinary=backend/directx/DirectXFunctionParameterResourceArrayShader.dxil|functionConstants.0.name=COUNT|functionConstants.0.value=2|resources.0.name=values|resources.0.kind=buffer|resources.0.type=vec4*|resources.1.name=colorMaps|resources.1.kind=texture|resources.1.type=sampler2D[COUNT]|resources.1.arrayDimensions.0.kind=fixed|resources.1.arrayDimensions.0.elementCount=2|workgroupSizes.0.entryPoint=compute_main"
    "-DEXPECTED_REFLECTION_JSON_ARRAY_LENGTHS=resources=2|targetResourceBindings=2|functionConstants=1|workgroupSizes=1"
    "-DEXPECTED_REFLECTION_TARGET_FIELDS=values.sourceType=vec4*|values.hlslType=RWStructuredBuffer<float4>|values.bindingClass=uav|values.descriptorType=UAV|values.argumentIndex=0|values.set=0|values.binding=0|colorMaps.sourceType=sampler2D[COUNT]|colorMaps.hlslType=Texture2D<float4>|colorMaps.bindingClass=srv|colorMaps.descriptorType=SRV|colorMaps.argumentIndex=2|colorMaps.set=0|colorMaps.binding=2|colorMaps.arraySize=COUNT|colorMaps.arrayElementCount=2"
    "-DEXPECTED_REFLECTION_FEATURE_FIELDS=hlsl-lowering.kind=backend|compute-kernel.kind=stage|workgroup-size.kind=execution|storage-buffer.kind=resource|sampled-texture.kind=resource|fixed-array.kind=layout|descriptor-array.kind=resource|function-parameter-array.kind=array|storage-buffer-write.kind=operation|index-access.kind=operation|vector-constructor.kind=operation"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_build_directx_graphics_resource_unsupported_planned_failure
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_DIRECTX_GRAPHICS_RESOURCE_UNSUPPORTED_SHADER}
    -DTARGET=directx
    -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-directx-graphics-resource-unsupported.cglb
    -DMODE=planned-build-failure
    -DEXPECTED_DIAGNOSTIC=directx.unsupported-graphics-resource
    ${CROSSGL_SINGLE_PLANNED_DIAGNOSTIC_EXPECTATIONS}
    "-DEXPECTED_DIAGNOSTIC_FIELD_CONTAINS=message=DirectX graphics source package supports only fixed-size uniform buffers, non-array storage buffers, and texture/sampler resources|message=stage 'vertex' resource 'debugMatrices'|message=kind storage-buffer|message=type mat4*|message=stage 'fragment' resource 'debugValues'|message=type vec4*[]|message=runtime storage-buffer descriptor arrays are not supported|message=register conflict for register(u4, space0)"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
set(CROSSGL_DIRECTX_LOCAL_FUNCTION_PARAMETER_ARRAY_SOURCE_SNIPPET [=[float sumWeights(float weights[COUNT]) {
  return weights[0] + weights[1];
}

[numthreads(1, 1, 1)]
void compute_main(uint3 crossgl_GlobalInvocationID : SV_DispatchThreadID) {
  float localWeights[COUNT];]=])
add_test(NAME cglc_build_directx_local_function_parameter_array_source_package
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_DIRECTX_LOCAL_FUNCTION_PARAMETER_ARRAY_SHADER}
    -DTARGET=directx
    -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-directx-local-function-parameter-array-source.cglb
    -DMODE=source-package-build
    -DEXPECTED_SOURCE=backend/directx/DirectXLocalFunctionParameterArrayShader.hlsl
    "-DEXPECTED_SOURCE_SNIPPET=${CROSSGL_DIRECTX_LOCAL_FUNCTION_PARAMETER_ARRAY_SOURCE_SNIPPET}"
    "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=directx|module=DirectXLocalFunctionParameterArrayShader|nativeBinary=backend/directx/DirectXLocalFunctionParameterArrayShader.dxil|functionConstants.0.name=COUNT|functionConstants.0.value=2|resources.0.name=particles|resources.0.kind=buffer|resources.0.type=Particle*|resources.0.binding=0|workgroupSizes.0.entryPoint=compute_main|workgroupSizes.0.x=1|workgroupSizes.0.y=1|workgroupSizes.0.z=1"
    "-DEXPECTED_REFLECTION_JSON_ARRAY_LENGTHS=resources=1|targetResourceBindings=1|workgroupSizes=1"
    "-DEXPECTED_REFLECTION_TARGET_FIELDS=particles.stage=compute|particles.entryPoint=compute_main|particles.sourceType=Particle*|particles.hlslType=RWStructuredBuffer<Particle>|particles.addressSpace=unordered-access|particles.abi=registerBinding|particles.bindingClass=uav|particles.descriptorType=UAV|particles.argumentIndex=0|particles.set=0|particles.binding=0"
    "-DEXPECTED_REFLECTION_FEATURE_FIELDS=hlsl-lowering.kind=backend|fixed-array.kind=layout|fixed-array-field.kind=layout|compute-kernel.kind=stage|workgroup-size.kind=execution|storage-buffer.kind=resource|scalar-arithmetic.kind=operation|index-access.kind=operation|local-declaration.kind=operation|storage-buffer-read.kind=operation|storage-buffer-write.kind=operation"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
crossgl_add_python_expect_test(
  NAME cglc_diagnostics_json_schema_target_failure
  DEFINITIONS
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_DIRECTX_GRAPHICS_RESOURCE_UNSUPPORTED_SHADER}
    -DTARGET=directx
    -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-directx-diagnostics-schema.cglb
    -DMODE=planned-build-failure
    -DEXPECTED_DIAGNOSTIC=directx.unsupported-graphics-resource
    ${CROSSGL_SINGLE_PLANNED_DIAGNOSTIC_EXPECTATIONS}
    -DJSON_SCHEMA=${CMAKE_CURRENT_SOURCE_DIR}/docs/schemas/diagnostics-v1.schema.json
    -DJSON_SCHEMA_VALIDATOR=${CMAKE_CURRENT_SOURCE_DIR}/tools/validate_json_schema.py
    "-DEXPECTED_DIAGNOSTICS_JSON_FIELDS=schemaVersion=1|diagnostics.0.target=directx"
    "-DEXPECTED_DIAGNOSTIC_FIELD_CONTAINS=message=DirectX graphics source package supports only fixed-size uniform buffers, non-array storage buffers, and texture/sampler resources|message=runtime storage-buffer descriptor arrays are not supported")
add_test(NAME cglc_build_vulkan_diagnostics_json_target_capability_planned_failure
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_VULKAN_RUNTIME_TEXTURE_DESCRIPTOR_ARRAY_CONFLICT_SHADER}
    -DTARGET=vulkan
    -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-vulkan-diagnostics-json-target-capability.cglb
    -DMODE=planned-build-failure
    ${CROSSGL_TARGET_NOT_IMPLEMENTED_DIAGNOSTIC_EXPECTATIONS}
    "-DEXPECTED_DIAGNOSTICS_JSON_FIELDS=schemaVersion=1|diagnostics.0.target=vulkan"
    "-DEXPECTED_DIAGNOSTIC_ARRAY_CONTAINS=missingCapabilities=vulkan.backend.vulkan-prototype-package|missingCapabilities=vulkan.diagnostic.vulkan.prototype-unsupported-runtime-resource-array"
    "-DEXPECTED_DIAGNOSTIC_FIELD_CONTAINS=message=target 'vulkan' cannot build a package for this module|message=vulkan.backend.vulkan-prototype-package|message=vulkan.diagnostic.vulkan.prototype-unsupported-runtime-resource-array"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
set(CROSSGL_DIRECTX_GRAPHICS_SOURCE_SNIPPET [=[struct crossgl_vertex_input {
  float3 position : POSITION0;
  float2 texCoord : TEXCOORD1;
};
struct crossgl_vertex_output {
  float2 uv : TEXCOORD0;
  float4 position : SV_Position;
};
struct crossgl_fragment_input {
  float2 uv : TEXCOORD0;
};
struct crossgl_fragment_output {
  float4 color : SV_Target0;
};

VertexOutput crossgl_user_vertex_main(VertexInput input) {]=])
add_test(NAME cglc_build_directx_graphics_source_package
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_SIMPLE_SHADER}
    -DTARGET=directx
    -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-directx-graphics-source.cglb
    -DMODE=source-package-build
    -DEXPECTED_SOURCE=backend/directx/SimpleShader.graphics.hlsl
    "-DEXPECTED_SOURCE_SNIPPET=${CROSSGL_DIRECTX_GRAPHICS_SOURCE_SNIPPET}"
    "-DEXPECTED_MANIFEST_JSON_FIELDS=schemaVersion=1|target=directx|module=SimpleShader|artifacts.backendSource=backend/directx/SimpleShader.graphics.hlsl|artifacts.nativeBinary=backend/directx/SimpleShader.dxil"
    "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=directx|module=SimpleShader|nativeBinary=backend/directx/SimpleShader.dxil|entryPoints.0.stage=vertex|entryPoints.0.backendName=vertex_main|entryPoints.1.stage=fragment|entryPoints.1.backendName=fragment_main|vertexLayouts.0.entryPoint=vertex_main"
    "-DEXPECTED_REFLECTION_JSON_ARRAY_LENGTHS=entryPoints=2|vertexLayouts=1|workgroupSizes=0"
    "-DEXPECTED_REFLECTION_FEATURE_FIELDS=hlsl-lowering.kind=backend|native-dxil-package.kind=backend|dxc.kind=toolchain|dxil-validator.kind=validation|vertex-shader.kind=stage|fragment-shader.kind=stage|local-declaration.kind=operation|vector-constructor.kind=operation"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
if(NOT DEFINED CROSSGL_DIRECTX_GRAPHICS_RESOURCE_SOURCE_SNIPPET)
  set(CROSSGL_DIRECTX_GRAPHICS_RESOURCE_SOURCE_SNIPPET [=[cbuffer transform_Buffer : register(b0, space0) {
  Transform transform;
};
cbuffer material_Buffer : register(b1, space0) {
  Material material;
};
Texture2D<float4> colorMap : register(t2, space0);
SamplerState linearSampler : register(s3, space0);]=])
endif()
if(NOT DEFINED CROSSGL_DIRECTX_GRAPHICS_STORAGE_BUFFER_RESOURCE_SOURCE_SNIPPET)
  set(CROSSGL_DIRECTX_GRAPHICS_STORAGE_BUFFER_RESOURCE_SOURCE_SNIPPET [=[RWStructuredBuffer<float4> vertexOffsets : register(u0, space0);
RWStructuredBuffer<DrawData> drawData : register(u1, space0);
RWStructuredBuffer<float4> fragmentScales : register(u2, space0);]=])
endif()
add_test(NAME cglc_build_directx_graphics_resources_source_package
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_DIRECTX_GRAPHICS_RESOURCE_SHADER}
    -DTARGET=directx
    -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-directx-graphics-resources-source.cglb
    -DMODE=source-package-build
    -DEXPECTED_SOURCE=backend/directx/DirectXGraphicsResourceShader.graphics.hlsl
    "-DEXPECTED_SOURCE_SNIPPET=${CROSSGL_DIRECTX_GRAPHICS_RESOURCE_SOURCE_SNIPPET}"
    "-DEXPECTED_MANIFEST_JSON_FIELDS=schemaVersion=1|target=directx|module=DirectXGraphicsResourceShader|artifacts.backendSource=backend/directx/DirectXGraphicsResourceShader.graphics.hlsl|artifacts.nativeBinary=backend/directx/DirectXGraphicsResourceShader.dxil"
    "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=directx|module=DirectXGraphicsResourceShader|nativeBinary=backend/directx/DirectXGraphicsResourceShader.dxil|resources.0.name=transform|resources.0.kind=uniform|resources.0.type=Transform|resources.0.binding=0|resources.1.name=material|resources.1.kind=uniform|resources.1.type=Material|resources.1.binding=1|resources.2.name=colorMap|resources.2.kind=texture|resources.2.type=sampler2D|resources.2.binding=2|resources.3.name=linearSampler|resources.3.kind=sampler|resources.3.type=sampler|resources.3.binding=3|entryPoints.0.stage=vertex|entryPoints.1.stage=fragment|vertexLayouts.0.entryPoint=vertex_main"
    "-DEXPECTED_REFLECTION_JSON_ARRAY_LENGTHS=resources=4|targetResourceBindings=4|entryPoints=2|vertexLayouts=1|workgroupSizes=0"
    "-DEXPECTED_REFLECTION_FEATURE_FIELDS=hlsl-lowering.kind=backend|native-dxil-package.kind=backend|dxc.kind=toolchain|dxil-validator.kind=validation|vertex-shader.kind=stage|fragment-shader.kind=stage|uniform-buffer.kind=resource|sampled-texture.kind=resource|sampler-state.kind=resource|texture-sample.kind=operation|texture-explicit-lod.kind=operation"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_build_directx_graphics_storage_buffer_resources_source_package
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_DIRECTX_GRAPHICS_STORAGE_BUFFER_RESOURCE_SHADER}
    -DTARGET=directx
    -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-directx-graphics-storage-buffer-resources-source.cglb
    -DMODE=source-package-build
    -DEXPECTED_SOURCE=backend/directx/DirectXGraphicsStorageBufferResourceShader.graphics.hlsl
    "-DEXPECTED_SOURCE_SNIPPET=${CROSSGL_DIRECTX_GRAPHICS_STORAGE_BUFFER_RESOURCE_SOURCE_SNIPPET}"
    "-DEXPECTED_MANIFEST_JSON_FIELDS=schemaVersion=1|target=directx|module=DirectXGraphicsStorageBufferResourceShader|artifacts.backendSource=backend/directx/DirectXGraphicsStorageBufferResourceShader.graphics.hlsl|artifacts.nativeBinary=backend/directx/DirectXGraphicsStorageBufferResourceShader.dxil"
    "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=directx|module=DirectXGraphicsStorageBufferResourceShader|nativeBinary=backend/directx/DirectXGraphicsStorageBufferResourceShader.dxil|resources.0.stage=vertex|resources.0.name=vertexOffsets|resources.0.kind=buffer|resources.0.type=vec4*|resources.0.binding=0|resources.1.stage=vertex|resources.1.name=drawData|resources.1.kind=buffer|resources.1.type=DrawData*|resources.1.binding=1|resources.2.stage=fragment|resources.2.name=drawData|resources.2.kind=buffer|resources.2.type=DrawData*|resources.2.binding=1|resources.3.stage=fragment|resources.3.name=fragmentScales|resources.3.kind=buffer|resources.3.type=vec4*|resources.3.binding=2|targetResourceBindings.1.stage=vertex|targetResourceBindings.1.name=drawData|targetResourceBindings.1.hlslType=RWStructuredBuffer<DrawData>|targetResourceBindings.2.stage=fragment|targetResourceBindings.2.name=drawData|targetResourceBindings.2.hlslType=RWStructuredBuffer<DrawData>|entryPoints.0.stage=vertex|entryPoints.1.stage=fragment|vertexLayouts.0.entryPoint=vertex_main"
    "-DEXPECTED_REFLECTION_JSON_ARRAY_LENGTHS=resources=4|targetResourceBindings=4|entryPoints=2|vertexLayouts=1|workgroupSizes=0"
    "-DEXPECTED_REFLECTION_TARGET_FIELDS=vertexOffsets.stage=vertex|vertexOffsets.entryPoint=vertex_main|vertexOffsets.sourceType=vec4*|vertexOffsets.hlslType=RWStructuredBuffer<float4>|vertexOffsets.addressSpace=unordered-access|vertexOffsets.abi=registerBinding|vertexOffsets.bindingClass=uav|vertexOffsets.descriptorType=UAV|vertexOffsets.argumentIndex=0|vertexOffsets.set=0|vertexOffsets.binding=0|fragmentScales.stage=fragment|fragmentScales.entryPoint=fragment_main|fragmentScales.sourceType=vec4*|fragmentScales.hlslType=RWStructuredBuffer<float4>|fragmentScales.addressSpace=unordered-access|fragmentScales.abi=registerBinding|fragmentScales.bindingClass=uav|fragmentScales.descriptorType=UAV|fragmentScales.argumentIndex=2|fragmentScales.set=0|fragmentScales.binding=2"
    "-DEXPECTED_REFLECTION_FEATURE_FIELDS=hlsl-lowering.kind=backend|native-dxil-package.kind=backend|dxc.kind=toolchain|dxil-validator.kind=validation|vertex-shader.kind=stage|fragment-shader.kind=stage|storage-buffer.kind=resource|vector-storage-buffer.kind=layout|index-access.kind=operation|storage-buffer-read.kind=operation|storage-buffer-write.kind=operation"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
if(NOT DEFINED CROSSGL_DIRECTX_GRAPHICS_SHADOW_COMPARE_SOURCE_SNIPPET)
  set(CROSSGL_DIRECTX_GRAPHICS_SHADOW_COMPARE_SOURCE_SNIPPET [=[float visibility = shadowMap.SampleCmpLevelZero(shadowSampler, input.uv, 0.5);]=])
endif()
add_test(NAME cglc_build_directx_graphics_shadow_compare_source_package
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_DIRECTX_GRAPHICS_SHADOW_COMPARE_SHADER}
    -DTARGET=directx
    -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-directx-graphics-shadow-compare-source.cglb
    -DMODE=source-package-build
    -DEXPECTED_SOURCE=backend/directx/DirectXGraphicsShadowCompareShader.graphics.hlsl
    "-DEXPECTED_SOURCE_SNIPPET=${CROSSGL_DIRECTX_GRAPHICS_SHADOW_COMPARE_SOURCE_SNIPPET}"
    "-DEXPECTED_MANIFEST_JSON_FIELDS=schemaVersion=1|target=directx|module=DirectXGraphicsShadowCompareShader|artifacts.backendSource=backend/directx/DirectXGraphicsShadowCompareShader.graphics.hlsl|artifacts.nativeBinary=backend/directx/DirectXGraphicsShadowCompareShader.dxil"
    "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=directx|module=DirectXGraphicsShadowCompareShader|nativeBinary=backend/directx/DirectXGraphicsShadowCompareShader.dxil|resources.0.name=shadowMap|resources.0.kind=texture|resources.0.type=sampler2DShadow|resources.0.set=1|resources.0.binding=2|resources.1.name=shadowSampler|resources.1.kind=sampler|resources.1.type=comparison_sampler|resources.1.set=1|resources.1.binding=3|entryPoints.0.stage=vertex|entryPoints.1.stage=fragment|vertexLayouts.0.entryPoint=vertex_main"
    "-DEXPECTED_REFLECTION_JSON_ARRAY_LENGTHS=resources=2|targetResourceBindings=2|entryPoints=2|vertexLayouts=1|workgroupSizes=0"
    "-DEXPECTED_REFLECTION_TARGET_FIELDS=shadowMap.stage=fragment|shadowMap.entryPoint=fragment_main|shadowMap.sourceType=sampler2DShadow|shadowMap.hlslType=Texture2D<float>|shadowMap.addressSpace=shader-resource|shadowMap.abi=registerBinding|shadowMap.bindingClass=srv|shadowMap.descriptorType=SRV|shadowMap.argumentIndex=2|shadowMap.set=1|shadowMap.binding=2|shadowSampler.stage=fragment|shadowSampler.entryPoint=fragment_main|shadowSampler.sourceType=comparison_sampler|shadowSampler.hlslType=SamplerComparisonState|shadowSampler.addressSpace=sampler|shadowSampler.abi=registerBinding|shadowSampler.bindingClass=sampler|shadowSampler.descriptorType=Sampler|shadowSampler.argumentIndex=3|shadowSampler.set=1|shadowSampler.binding=3"
    "-DEXPECTED_REFLECTION_FEATURE_FIELDS=hlsl-lowering.kind=backend|native-dxil-package.kind=backend|dxc.kind=toolchain|dxil-validator.kind=validation|vertex-shader.kind=stage|fragment-shader.kind=stage|sampled-texture.kind=resource|depth-compare-format.kind=texture|sampler-state.kind=resource|texture-shadow-compare.kind=operation"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
if(NOT DEFINED CROSSGL_DIRECTX_GRAPHICS_SHADOW_COMPARE_LOD_SOURCE_SNIPPET)
  set(CROSSGL_DIRECTX_GRAPHICS_SHADOW_COMPARE_LOD_SOURCE_SNIPPET [=[float visibility = shadowMap.SampleCmpLevel(shadowSampler, input.uv, 0.5, 2.0);]=])
endif()
add_test(NAME cglc_build_directx_graphics_shadow_compare_lod_source_package
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_DIRECTX_GRAPHICS_SHADOW_COMPARE_LOD_SHADER}
    -DTARGET=directx
    -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-directx-graphics-shadow-compare-lod-source.cglb
    -DMODE=source-package-build
    -DEXPECTED_SOURCE=backend/directx/DirectXGraphicsShadowCompareLodShader.graphics.hlsl
    "-DEXPECTED_SOURCE_SNIPPET=${CROSSGL_DIRECTX_GRAPHICS_SHADOW_COMPARE_LOD_SOURCE_SNIPPET}"
    "-DEXPECTED_MANIFEST_JSON_FIELDS=schemaVersion=1|target=directx|module=DirectXGraphicsShadowCompareLodShader|artifacts.backendSource=backend/directx/DirectXGraphicsShadowCompareLodShader.graphics.hlsl|artifacts.nativeBinary=backend/directx/DirectXGraphicsShadowCompareLodShader.dxil"
    "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=directx|module=DirectXGraphicsShadowCompareLodShader|nativeBinary=backend/directx/DirectXGraphicsShadowCompareLodShader.dxil|resources.0.stage=fragment|resources.0.name=shadowMap|resources.0.kind=texture|resources.0.type=sampler2DShadow|resources.0.set=1|resources.0.binding=2|resources.1.stage=fragment|resources.1.name=shadowSampler|resources.1.kind=sampler|resources.1.type=comparison_sampler|resources.1.set=1|resources.1.binding=3|entryPoints.0.stage=vertex|entryPoints.1.stage=fragment|vertexLayouts.0.entryPoint=vertex_main|manualTextureCompareKernelSummary.totalCount=0"
    "-DEXPECTED_REFLECTION_JSON_ARRAY_LENGTHS=resources=2|targetResourceBindings=2|entryPoints=2|vertexLayouts=1|workgroupSizes=0|manualTextureCompareKernels=0"
    "-DEXPECTED_REFLECTION_TARGET_FIELDS=shadowMap.stage=fragment|shadowMap.entryPoint=fragment_main|shadowMap.sourceType=sampler2DShadow|shadowMap.hlslType=Texture2D<float>|shadowMap.addressSpace=shader-resource|shadowMap.abi=registerBinding|shadowMap.bindingClass=srv|shadowMap.descriptorType=SRV|shadowMap.argumentIndex=2|shadowMap.set=1|shadowMap.binding=2|shadowSampler.stage=fragment|shadowSampler.entryPoint=fragment_main|shadowSampler.sourceType=comparison_sampler|shadowSampler.hlslType=SamplerComparisonState|shadowSampler.addressSpace=sampler|shadowSampler.abi=registerBinding|shadowSampler.bindingClass=sampler|shadowSampler.descriptorType=Sampler|shadowSampler.argumentIndex=3|shadowSampler.set=1|shadowSampler.binding=3"
    "-DEXPECTED_REFLECTION_FEATURE_FIELDS=hlsl-lowering.kind=backend|native-dxil-package.kind=backend|dxc.kind=toolchain|dxil-validator.kind=validation|vertex-shader.kind=stage|fragment-shader.kind=stage|sampled-texture.kind=resource|depth-compare-format.kind=texture|sampler-state.kind=resource|texture-shadow-compare.kind=operation|texture-shadow-compare-explicit-lod.kind=operation"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_build_directx_graphics_resources_fake_dxc_success
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_DIRECTX_GRAPHICS_RESOURCE_SHADER}
    -DTARGET=directx
    -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-directx-graphics-resources-fake-dxc-success.cglb
    -DMODE=source-package-build
    -DTOOLCHAIN_PATH=${CROSSGL_FAKE_DXC_GRAPHICS_SUCCESS_DIR}
    -DTOOLCHAIN_DISABLE_FALLBACK=ON
    -DEXPECTED_SOURCE=backend/directx/DirectXGraphicsResourceShader.graphics.hlsl
    "-DEXPECTED_SOURCE_SNIPPET=${CROSSGL_DIRECTX_GRAPHICS_RESOURCE_SOURCE_SNIPPET}"
    "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=directx|module=DirectXGraphicsResourceShader|nativeBinary=backend/directx/DirectXGraphicsResourceShader.dxil|entryPoints.0.stage=vertex|entryPoints.0.backendName=vertex_main|entryPoints.1.stage=fragment|entryPoints.1.backendName=fragment_main|vertexLayouts.0.entryPoint=vertex_main"
    "-DEXPECTED_REFLECTION_JSON_ARRAY_LENGTHS=resources=4|targetResourceBindings=4|entryPoints=2|vertexLayouts=1|workgroupSizes=0"
    -DEXPECTED_NATIVE_BINARY=backend/directx/DirectXGraphicsResourceShader.dxil
    -DEXPECTED_NATIVE_BINARY_STATUS=emitted
    "-DEXPECTED_DIAGNOSTICS_JSON_FIELDS=diagnostics.0.severity=note|diagnostics.0.code=directx.source-package-emitted|diagnostics.1.severity=note|diagnostics.1.code=directx.dxil-emitted"
    "-DEXPECTED_DIAGNOSTICS_JSON_FIELD_CONTAINS=diagnostics.0.message=vertex=vs_6_0|diagnostics.0.message=fragment=ps_6_0|diagnostics.1.message=vertex=vs_6_0|diagnostics.1.message=fragment=ps_6_0"
    "-DEXPECTED_DIAGNOSTICS_JSON_ARRAY_LENGTHS=diagnostics=2"
    -DEXPECTED_TOOL_LOG=${CROSSGL_FAKE_DXC_GRAPHICS_SUCCESS_DIR}/dxc.log
    "-DEXPECTED_TOOL_LOG_CONTAINS=-O3 -T vs_6_0 -E vertex_main -Fo|backend/directx/DirectXGraphicsResourceShader.vertex.dxil|backend/directx/DirectXGraphicsResourceShader.graphics.hlsl"
    -DEXPECTED_SECOND_TOOL_LOG=${CROSSGL_FAKE_DXC_GRAPHICS_SUCCESS_DIR}/dxc.log
    "-DEXPECTED_SECOND_TOOL_LOG_CONTAINS=-O3 -T ps_6_0 -E fragment_main -Fo|backend/directx/DirectXGraphicsResourceShader.fragment.dxil|backend/directx/DirectXGraphicsResourceShader.graphics.hlsl"
    -DEXPECTED_THIRD_TOOL_LOG=${CROSSGL_FAKE_DXC_GRAPHICS_SUCCESS_DIR}/dxc.log
    "-DEXPECTED_THIRD_TOOL_LOG_CONTAINS=backend/directx/DirectXGraphicsResourceShader.fragment.dxil"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_build_directx_graphics_storage_buffer_resources_fake_dxc_success
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_DIRECTX_GRAPHICS_STORAGE_BUFFER_RESOURCE_SHADER}
    -DTARGET=directx
    -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-directx-graphics-storage-buffer-resources-fake-dxc-success.cglb
    -DMODE=source-package-build
    -DTOOLCHAIN_PATH=${CROSSGL_FAKE_DXC_GRAPHICS_SUCCESS_DIR}
    -DTOOLCHAIN_DISABLE_FALLBACK=ON
    -DEXPECTED_SOURCE=backend/directx/DirectXGraphicsStorageBufferResourceShader.graphics.hlsl
    "-DEXPECTED_SOURCE_SNIPPET=${CROSSGL_DIRECTX_GRAPHICS_STORAGE_BUFFER_RESOURCE_SOURCE_SNIPPET}"
    "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=directx|module=DirectXGraphicsStorageBufferResourceShader|nativeBinary=backend/directx/DirectXGraphicsStorageBufferResourceShader.dxil|resources.0.stage=vertex|resources.0.name=vertexOffsets|resources.0.kind=buffer|resources.1.name=drawData|resources.2.stage=fragment|resources.2.name=drawData|resources.3.name=fragmentScales|targetResourceBindings.0.hlslType=RWStructuredBuffer<float4>|targetResourceBindings.1.hlslType=RWStructuredBuffer<DrawData>|targetResourceBindings.2.hlslType=RWStructuredBuffer<DrawData>|targetResourceBindings.3.hlslType=RWStructuredBuffer<float4>|entryPoints.0.stage=vertex|entryPoints.1.stage=fragment|vertexLayouts.0.entryPoint=vertex_main"
    "-DEXPECTED_REFLECTION_JSON_ARRAY_LENGTHS=resources=4|targetResourceBindings=4|entryPoints=2|vertexLayouts=1|workgroupSizes=0"
    -DEXPECTED_NATIVE_BINARY=backend/directx/DirectXGraphicsStorageBufferResourceShader.dxil
    -DEXPECTED_NATIVE_BINARY_STATUS=emitted
    "-DEXPECTED_DIAGNOSTICS_JSON_FIELDS=diagnostics.0.severity=note|diagnostics.0.code=directx.source-package-emitted|diagnostics.1.severity=note|diagnostics.1.code=directx.dxil-emitted"
    "-DEXPECTED_DIAGNOSTICS_JSON_FIELD_CONTAINS=diagnostics.0.message=vertex=vs_6_0|diagnostics.0.message=fragment=ps_6_0|diagnostics.1.message=vertex=vs_6_0|diagnostics.1.message=fragment=ps_6_0"
    "-DEXPECTED_DIAGNOSTICS_JSON_ARRAY_LENGTHS=diagnostics=2"
    -DEXPECTED_TOOL_LOG=${CROSSGL_FAKE_DXC_GRAPHICS_SUCCESS_DIR}/dxc.log
    "-DEXPECTED_TOOL_LOG_CONTAINS=-O3 -T vs_6_0 -E vertex_main -Fo|backend/directx/DirectXGraphicsStorageBufferResourceShader.vertex.dxil|backend/directx/DirectXGraphicsStorageBufferResourceShader.graphics.hlsl"
    -DEXPECTED_SECOND_TOOL_LOG=${CROSSGL_FAKE_DXC_GRAPHICS_SUCCESS_DIR}/dxc.log
    "-DEXPECTED_SECOND_TOOL_LOG_CONTAINS=-O3 -T ps_6_0 -E fragment_main -Fo|backend/directx/DirectXGraphicsStorageBufferResourceShader.fragment.dxil|backend/directx/DirectXGraphicsStorageBufferResourceShader.graphics.hlsl"
    -DEXPECTED_THIRD_TOOL_LOG=${CROSSGL_FAKE_DXC_GRAPHICS_SUCCESS_DIR}/dxc.log
    "-DEXPECTED_THIRD_TOOL_LOG_CONTAINS=backend/directx/DirectXGraphicsStorageBufferResourceShader.fragment.dxil"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_build_directx_graphics_shadow_compare_lod_fake_dxc_success
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_DIRECTX_GRAPHICS_SHADOW_COMPARE_LOD_SHADER}
    -DTARGET=directx
    -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-directx-graphics-shadow-compare-lod-fake-dxc-success.cglb
    -DMODE=source-package-build
    -DTOOLCHAIN_PATH=${CROSSGL_FAKE_DXC_GRAPHICS_SUCCESS_DIR}
    -DTOOLCHAIN_DISABLE_FALLBACK=ON
    -DEXPECTED_SOURCE=backend/directx/DirectXGraphicsShadowCompareLodShader.graphics.hlsl
    "-DEXPECTED_SOURCE_SNIPPET=${CROSSGL_DIRECTX_GRAPHICS_SHADOW_COMPARE_LOD_SOURCE_SNIPPET}"
    "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=directx|module=DirectXGraphicsShadowCompareLodShader|nativeBinary=backend/directx/DirectXGraphicsShadowCompareLodShader.dxil|resources.0.stage=fragment|resources.0.name=shadowMap|resources.0.kind=texture|resources.0.type=sampler2DShadow|resources.0.set=1|resources.0.binding=2|resources.1.stage=fragment|resources.1.name=shadowSampler|resources.1.kind=sampler|resources.1.type=comparison_sampler|resources.1.set=1|resources.1.binding=3|entryPoints.0.stage=vertex|entryPoints.0.backendName=vertex_main|entryPoints.1.stage=fragment|entryPoints.1.backendName=fragment_main|vertexLayouts.0.entryPoint=vertex_main|manualTextureCompareKernelSummary.totalCount=0"
    "-DEXPECTED_REFLECTION_JSON_ARRAY_LENGTHS=resources=2|targetResourceBindings=2|entryPoints=2|vertexLayouts=1|workgroupSizes=0|manualTextureCompareKernels=0"
    -DEXPECTED_NATIVE_BINARY=backend/directx/DirectXGraphicsShadowCompareLodShader.dxil
    -DEXPECTED_NATIVE_BINARY_STATUS=emitted
    "-DEXPECTED_DIAGNOSTICS_JSON_FIELDS=diagnostics.0.severity=note|diagnostics.0.code=directx.source-package-emitted|diagnostics.1.severity=note|diagnostics.1.code=directx.dxil-emitted"
    "-DEXPECTED_DIAGNOSTICS_JSON_FIELD_CONTAINS=diagnostics.0.message=vertex=vs_6_7|diagnostics.0.message=fragment=ps_6_7|diagnostics.1.message=vertex=vs_6_7|diagnostics.1.message=fragment=ps_6_7"
    "-DEXPECTED_DIAGNOSTICS_JSON_ARRAY_LENGTHS=diagnostics=2"
    -DEXPECTED_TOOL_LOG=${CROSSGL_FAKE_DXC_GRAPHICS_SUCCESS_DIR}/dxc.log
    "-DEXPECTED_TOOL_LOG_CONTAINS=-O3 -T vs_6_7 -E vertex_main -Fo|backend/directx/DirectXGraphicsShadowCompareLodShader.vertex.dxil|backend/directx/DirectXGraphicsShadowCompareLodShader.graphics.hlsl"
    -DEXPECTED_SECOND_TOOL_LOG=${CROSSGL_FAKE_DXC_GRAPHICS_SUCCESS_DIR}/dxc.log
    "-DEXPECTED_SECOND_TOOL_LOG_CONTAINS=-O3 -T ps_6_7 -E fragment_main -Fo|backend/directx/DirectXGraphicsShadowCompareLodShader.fragment.dxil|backend/directx/DirectXGraphicsShadowCompareLodShader.graphics.hlsl"
    -DEXPECTED_THIRD_TOOL_LOG=${CROSSGL_FAKE_DXC_GRAPHICS_SUCCESS_DIR}/dxc.log
    "-DEXPECTED_THIRD_TOOL_LOG_CONTAINS=backend/directx/DirectXGraphicsShadowCompareLodShader.fragment.dxil"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_build_directx_graphics_resources_fake_dxc_tool_failure
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_DIRECTX_GRAPHICS_RESOURCE_SHADER}
    -DTARGET=directx
    -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-directx-graphics-resources-fake-dxc-failure.cglb
    -DMODE=source-package-build
    -DTOOLCHAIN_PATH=${CROSSGL_FAKE_DXC_GRAPHICS_FAILURE_DIR}
    -DTOOLCHAIN_DISABLE_FALLBACK=ON
    -DEXPECTED_SOURCE=backend/directx/DirectXGraphicsResourceShader.graphics.hlsl
    "-DEXPECTED_SOURCE_SNIPPET=${CROSSGL_DIRECTX_GRAPHICS_RESOURCE_SOURCE_SNIPPET}"
    -DEXPECTED_NATIVE_BINARY_ABSENT=backend/directx/DirectXGraphicsResourceShader.dxil
    -DEXPECTED_NATIVE_BINARY_STATUS=planned
    "-DEXPECTED_DIAGNOSTICS_JSON_FIELDS=diagnostics.0.severity=note|diagnostics.0.code=directx.source-package-emitted|diagnostics.1.severity=warning|diagnostics.1.code=directx.dxc-failed|diagnostics.2.severity=warning|diagnostics.2.code=directx.source-package-only"
    "-DEXPECTED_DIAGNOSTICS_JSON_FIELD_CONTAINS=diagnostics.0.message=CrossGL opt-level O1 maps to DXC -O3|diagnostics.0.message=vertex=vs_6_0|diagnostics.0.message=fragment=ps_6_0|diagnostics.1.message=CrossGL opt-level O1 maps to DXC -O3|diagnostics.1.message=vertex=vs_6_0|diagnostics.1.message=fragment=ps_6_0|diagnostics.1.message=vertex command profile: dxc -O3 -T vs_6_0 -E vertex_main -Fo backend/directx/DirectXGraphicsResourceShader.vertex.dxil backend/directx/DirectXGraphicsResourceShader.graphics.hlsl|diagnostics.1.message=fragment command profile: dxc -O3 -T ps_6_0 -E fragment_main -Fo backend/directx/DirectXGraphicsResourceShader.fragment.dxil backend/directx/DirectXGraphicsResourceShader.graphics.hlsl|diagnostics.1.message=vertex dxc diagnostics: stderr:|diagnostics.1.message=fragment dxc diagnostics: stderr:|diagnostics.1.message=fake dxc failure|diagnostics.1.message=partial DXIL outputs were discarded|diagnostics.2.message=vertex=vs_6_0|diagnostics.2.message=fragment=ps_6_0|diagnostics.2.message=planned native binary artifact: backend/directx/DirectXGraphicsResourceShader.dxil"
    "-DEXPECTED_DIAGNOSTICS_JSON_ARRAY_LENGTHS=diagnostics=3"
    -DEXPECTED_TOOL_LOG=${CROSSGL_FAKE_DXC_GRAPHICS_FAILURE_DIR}/dxc.log
    "-DEXPECTED_TOOL_LOG_CONTAINS=-O3 -T vs_6_0 -E vertex_main -Fo|backend/directx/DirectXGraphicsResourceShader.vertex.dxil|backend/directx/DirectXGraphicsResourceShader.graphics.hlsl"
    -DEXPECTED_SECOND_TOOL_LOG=${CROSSGL_FAKE_DXC_GRAPHICS_FAILURE_DIR}/dxc.log
    "-DEXPECTED_SECOND_TOOL_LOG_CONTAINS=-O3 -T ps_6_0 -E fragment_main -Fo|backend/directx/DirectXGraphicsResourceShader.fragment.dxil|backend/directx/DirectXGraphicsResourceShader.graphics.hlsl"
    -DEXPECTED_THIRD_TOOL_LOG=${CROSSGL_FAKE_DXC_GRAPHICS_FAILURE_DIR}/dxc.log
    "-DEXPECTED_THIRD_TOOL_LOG_CONTAINS=backend/directx/DirectXGraphicsResourceShader.fragment.dxil"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_build_directx_graphics_resources_fake_dxc_unavailable
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_DIRECTX_GRAPHICS_RESOURCE_SHADER}
    -DTARGET=directx
    -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-directx-graphics-resources-fake-dxc-unavailable.cglb
    -DMODE=source-package-build
    -DTOOLCHAIN_PATH=${CROSSGL_FAKE_TOOL_UNAVAILABLE_DIR}
    -DTOOLCHAIN_DISABLE_FALLBACK=ON
    -DEXPECTED_SOURCE=backend/directx/DirectXGraphicsResourceShader.graphics.hlsl
    "-DEXPECTED_SOURCE_SNIPPET=${CROSSGL_DIRECTX_GRAPHICS_RESOURCE_SOURCE_SNIPPET}"
    -DEXPECTED_NATIVE_BINARY_ABSENT=backend/directx/DirectXGraphicsResourceShader.dxil
    -DEXPECTED_NATIVE_BINARY_STATUS=planned
    "-DEXPECTED_DIAGNOSTICS_JSON_FIELDS=diagnostics.0.severity=note|diagnostics.0.code=directx.source-package-emitted|diagnostics.1.severity=warning|diagnostics.1.code=directx.source-package-only"
    "-DEXPECTED_DIAGNOSTICS_JSON_FIELD_CONTAINS=diagnostics.0.message=vertex=vs_6_0|diagnostics.0.message=fragment=ps_6_0|diagnostics.1.message=dxc was not found|diagnostics.1.message=no dxc command was invoked|diagnostics.1.message=vertex=vs_6_0|diagnostics.1.message=fragment=ps_6_0"
    "-DEXPECTED_DIAGNOSTICS_JSON_ARRAY_LENGTHS=diagnostics=2"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
crossgl_label_optional_native_policy_test(
  cglc_build_directx_graphics_resources_fake_dxc_tool_failure directx)
crossgl_label_optional_native_policy_test(
  cglc_build_directx_graphics_resources_fake_dxc_unavailable directx)
set(CROSSGL_OPENGL_GRAPHICS_SOURCE_SNIPPET [=[#if defined(CROSSGL_STAGE_VERTEX)
layout(location = 0) in vec3 crossgl_attr_position;
layout(location = 1) in vec2 crossgl_attr_texCoord;
layout(location = 0) out vec2 crossgl_varying_uv;

VertexOutput vertex_main(VertexInput crossgl_user_input) {
  VertexOutput crossgl_user_output;
  crossgl_user_output.uv = crossgl_user_input.texCoord;
  crossgl_user_output.position = vec4(crossgl_user_input.position, 1.0);
  return crossgl_user_output;
}

void main() {
  VertexInput crossgl_vertex_input;
  crossgl_vertex_input.position = crossgl_attr_position;
  crossgl_vertex_input.texCoord = crossgl_attr_texCoord;
  VertexOutput crossgl_vertex_output = vertex_main(crossgl_vertex_input);
  crossgl_varying_uv = crossgl_vertex_output.uv;
  gl_Position = crossgl_vertex_output.position;
}
#endif

#if defined(CROSSGL_STAGE_FRAGMENT)
layout(location = 0) in vec2 crossgl_varying_uv;
layout(location = 0) out vec4 crossgl_out_color;

FragmentOutput fragment_main(FragmentInput crossgl_user_input) {]=])
add_test(NAME cglc_build_opengl_graphics_source_package
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_SIMPLE_SHADER}
    -DTARGET=opengl
    -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-opengl-graphics-source.cglb
    -DMODE=source-package-build
    -DEXPECTED_SOURCE=backend/opengl/SimpleShader.graphics.glsl
    "-DEXPECTED_SOURCE_SNIPPET=${CROSSGL_OPENGL_GRAPHICS_SOURCE_SNIPPET}"
    "-DEXPECTED_MANIFEST_JSON_FIELDS=schemaVersion=1|target=opengl|module=SimpleShader|artifacts.backendSource=backend/opengl/SimpleShader.graphics.glsl|artifacts.nativeBinary=backend/opengl/SimpleShader.glsl"
    "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=opengl|module=SimpleShader|nativeBinary=backend/opengl/SimpleShader.glsl|entryPoints.0.stage=vertex|entryPoints.0.backendName=vertex_main|entryPoints.1.stage=fragment|entryPoints.1.backendName=fragment_main|vertexLayouts.0.entryPoint=vertex_main"
    "-DEXPECTED_REFLECTION_JSON_ARRAY_LENGTHS=entryPoints=2|vertexLayouts=1|workgroupSizes=0"
    "-DEXPECTED_REFLECTION_FEATURE_FIELDS=glsl-lowering.kind=backend|vertex-shader.kind=stage|fragment-shader.kind=stage|local-declaration.kind=operation|vector-constructor.kind=operation"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_build_opengl_graphics_fake_glslang_success
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_SIMPLE_SHADER}
    -DTARGET=opengl
    -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-opengl-graphics-fake-glslang-success.cglb
    -DMODE=source-package-build
    -DTOOLCHAIN_PATH=${CROSSGL_FAKE_GLSLANG_SUCCESS_DIR}
    -DTOOLCHAIN_DISABLE_FALLBACK=ON
    -DEXPECTED_SOURCE=backend/opengl/SimpleShader.graphics.glsl
    "-DEXPECTED_SOURCE_SNIPPET=${CROSSGL_OPENGL_GRAPHICS_SOURCE_SNIPPET}"
    "-DEXPECTED_MANIFEST_JSON_FIELDS=schemaVersion=1|target=opengl|module=SimpleShader|artifacts.backendSource=backend/opengl/SimpleShader.graphics.glsl|artifacts.nativeBinary=backend/opengl/SimpleShader.glsl"
    "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=opengl|module=SimpleShader|nativeBinary=backend/opengl/SimpleShader.glsl|entryPoints.0.stage=vertex|entryPoints.0.backendName=vertex_main|entryPoints.1.stage=fragment|entryPoints.1.backendName=fragment_main|vertexLayouts.0.entryPoint=vertex_main"
    "-DEXPECTED_REFLECTION_JSON_ARRAY_LENGTHS=entryPoints=2|vertexLayouts=1|workgroupSizes=0"
    "-DEXPECTED_REFLECTION_FEATURE_FIELDS=native-glsl-package.kind=backend|glsl-program-validation.kind=validation|vertex-shader.kind=stage|fragment-shader.kind=stage|local-declaration.kind=operation|vector-constructor.kind=operation"
    -DEXPECTED_NATIVE_BINARY=backend/opengl/SimpleShader.glsl
    -DEXPECTED_NATIVE_BINARY_STATUS=validated
    "-DEXPECTED_DIAGNOSTICS_JSON_FIELDS=diagnostics.0.severity=note|diagnostics.0.code=opengl.glsl-validated"
    -DEXPECTED_DIAGNOSTIC=opengl.glsl-validated
    "-DEXPECTED_DIAGNOSTIC_FIELD_CONTAINS=message=GLSL 450"
    "-DEXPECTED_DIAGNOSTICS_JSON_ARRAY_LENGTHS=diagnostics=1"
    -DEXPECTED_TOOL_LOG=${CROSSGL_FAKE_GLSLANG_SUCCESS_DIR}/glslangValidator.log
    "-DEXPECTED_TOOL_LOG_CONTAINS=glslangValidator success: -l -S vert -DCROSSGL_STAGE_VERTEX=1"
    -DEXPECTED_SECOND_TOOL_LOG=${CROSSGL_FAKE_GLSLANG_SUCCESS_DIR}/glslangValidator.log
    "-DEXPECTED_SECOND_TOOL_LOG_CONTAINS=glslangValidator success: -l -S frag -DCROSSGL_STAGE_FRAGMENT=1"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_build_opengl_graphics_fake_glslang_fragment_tool_failure
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_SIMPLE_SHADER}
    -DTARGET=opengl
    -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-opengl-graphics-fake-glslang-fragment-failure.cglb
    -DMODE=source-package-build
    -DTOOLCHAIN_PATH=${CROSSGL_FAKE_GLSLANG_FRAGMENT_FAILURE_DIR}
    -DTOOLCHAIN_DISABLE_FALLBACK=ON
    -DEXPECTED_SOURCE=backend/opengl/SimpleShader.graphics.glsl
    "-DEXPECTED_SOURCE_SNIPPET=${CROSSGL_OPENGL_GRAPHICS_SOURCE_SNIPPET}"
    "-DEXPECTED_MANIFEST_JSON_FIELDS=schemaVersion=1|target=opengl|module=SimpleShader|artifacts.backendSource=backend/opengl/SimpleShader.graphics.glsl|artifacts.nativeBinary=backend/opengl/SimpleShader.glsl|artifacts.nativeBinaryStatus=planned"
    "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=opengl|module=SimpleShader|nativeBinary=backend/opengl/SimpleShader.glsl|entryPoints.0.stage=vertex|entryPoints.0.backendName=vertex_main|entryPoints.1.stage=fragment|entryPoints.1.backendName=fragment_main|vertexLayouts.0.entryPoint=vertex_main"
    "-DEXPECTED_REFLECTION_JSON_ARRAY_LENGTHS=entryPoints=2|vertexLayouts=1|workgroupSizes=0"
    "-DEXPECTED_REFLECTION_FEATURE_FIELDS=glsl-lowering.kind=backend|vertex-shader.kind=stage|fragment-shader.kind=stage|local-declaration.kind=operation|vector-constructor.kind=operation"
    -DEXPECTED_NATIVE_BINARY_ABSENT=backend/opengl/SimpleShader.glsl
    -DEXPECTED_NATIVE_BINARY_STATUS=planned
    "-DEXPECTED_DEBUG_METADATA_JSON_FIELDS=sourcePackageValidation.target=opengl|sourcePackageValidation.tool=glslangValidator|sourcePackageValidation.policy=use-when-available|sourcePackageValidation.status=failed"
    -DEXPECTED_DIAGNOSTIC=opengl.glslang-failed
    "-DEXPECTED_DIAGNOSTICS_JSON_FIELDS=diagnostics.0.severity=warning|diagnostics.0.code=opengl.glslang-failed|diagnostics.0.target=opengl|diagnostics.1.severity=warning|diagnostics.1.code=opengl.source-package-only"
    "-DEXPECTED_DIAGNOSTIC_FIELD_CONTAINS=message=GLSL 450"
    "-DEXPECTED_DIAGNOSTIC_ARRAY_CONTAINS=missingCapabilities=opengl.backend.native-glsl-package|missingCapabilities=opengl.validation.glsl-program-validation"
    "-DEXPECTED_DIAGNOSTICS_JSON_ARRAY_LENGTHS=diagnostics=2|diagnostics.0.missingCapabilities=2"
    "-DEXPECTED_NATIVE_ARTIFACT_DESCRIPTOR_JSON_FIELDS=target=opengl|binaryKind=opengl.source|sourcePath=backend/opengl/SimpleShader.graphics.glsl|sourceHash.algorithm=sha256|nativeBinaryStatus=planned|validationStatus=unavailable|toolchainProvenance.tools.0.name=CrossGL OpenGL backend|toolchainProvenance.tools.0.role=generator"
    "-DEXPECTED_NATIVE_ARTIFACT_DESCRIPTOR_JSON_PATHS=sourceHash.value"
    "-DEXPECTED_NATIVE_ARTIFACT_DESCRIPTOR_JSON_ARRAY_LENGTHS=toolchainProvenance.tools=1|validationDiagnostics=0"
    -DEXPECTED_TOOL_LOG=${CROSSGL_FAKE_GLSLANG_FRAGMENT_FAILURE_DIR}/glslangValidator.log
    "-DEXPECTED_TOOL_LOG_CONTAINS=glslangValidator fragment-failure: -l -S vert -DCROSSGL_STAGE_VERTEX=1"
    -DEXPECTED_SECOND_TOOL_LOG=${CROSSGL_FAKE_GLSLANG_FRAGMENT_FAILURE_DIR}/glslangValidator.log
    "-DEXPECTED_SECOND_TOOL_LOG_CONTAINS=glslangValidator fragment-failure: -l -S frag -DCROSSGL_STAGE_FRAGMENT=1"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
crossgl_label_optional_native_policy_test(
  cglc_build_opengl_graphics_fake_glslang_fragment_tool_failure opengl)
if(CROSSGL_HAS_OPENGL_NATIVE_VALIDATOR)
  add_test(NAME cglc_build_opengl_graphics_glsl_validated
    COMMAND ${CMAKE_COMMAND}
      -DCGLC=$<TARGET_FILE:cglc>
      -DINPUT=${CROSSGL_SIMPLE_SHADER}
      -DTARGET=opengl
      -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-opengl-graphics-validated.cglb
      -DMODE=source-package-build
      -DEXPECTED_SOURCE=backend/opengl/SimpleShader.graphics.glsl
      "-DEXPECTED_SOURCE_SNIPPET=${CROSSGL_OPENGL_GRAPHICS_SOURCE_SNIPPET}"
      "-DEXPECTED_MANIFEST_JSON_FIELDS=schemaVersion=1|target=opengl|module=SimpleShader|artifacts.backendSource=backend/opengl/SimpleShader.graphics.glsl|artifacts.nativeBinary=backend/opengl/SimpleShader.glsl"
      "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=opengl|module=SimpleShader|nativeBinary=backend/opengl/SimpleShader.glsl|entryPoints.0.stage=vertex|entryPoints.0.backendName=vertex_main|entryPoints.1.stage=fragment|entryPoints.1.backendName=fragment_main|vertexLayouts.0.entryPoint=vertex_main"
      "-DEXPECTED_REFLECTION_JSON_ARRAY_LENGTHS=entryPoints=2|vertexLayouts=1|workgroupSizes=0"
      "-DEXPECTED_REFLECTION_FEATURE_FIELDS=native-glsl-package.kind=backend|glsl-program-validation.kind=validation|vertex-shader.kind=stage|fragment-shader.kind=stage|local-declaration.kind=operation|vector-constructor.kind=operation"
      -DEXPECTED_NATIVE_BINARY=backend/opengl/SimpleShader.glsl
      -DEXPECTED_NATIVE_BINARY_STATUS=validated
      -DEXPECTED_DIAGNOSTIC=opengl.glsl-validated
      -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
  crossgl_label_optional_native_test(cglc_build_opengl_graphics_glsl_validated
    opengl)
endif()
set(CROSSGL_OPENGL_GRAPHICS_RESOURCES_SOURCE_SNIPPET [=[#if defined(CROSSGL_STAGE_VERTEX)
// CrossGL set 0, binding 0
layout(binding = 0, std140) uniform vertexParams_Uniform {
  vec4 tint;
  float zBias;
} vertexParams;

layout(location = 0) in vec3 crossgl_attr_position;]=])
add_test(NAME cglc_build_opengl_graphics_resources_source_package
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_OPENGL_GRAPHICS_RESOURCES_SHADER}
    -DTARGET=opengl
    -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-opengl-graphics-resources-source.cglb
    -DMODE=source-package-build
    -DEXPECTED_SOURCE=backend/opengl/OpenGLGraphicsResourcesShader.graphics.glsl
    "-DEXPECTED_SOURCE_SNIPPET=${CROSSGL_OPENGL_GRAPHICS_RESOURCES_SOURCE_SNIPPET}"
    "-DEXPECTED_MANIFEST_JSON_FIELDS=schemaVersion=1|target=opengl|module=OpenGLGraphicsResourcesShader|artifacts.backendSource=backend/opengl/OpenGLGraphicsResourcesShader.graphics.glsl|artifacts.nativeBinary=backend/opengl/OpenGLGraphicsResourcesShader.glsl"
    "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=opengl|module=OpenGLGraphicsResourcesShader|nativeBinary=backend/opengl/OpenGLGraphicsResourcesShader.glsl|entryPoints.0.stage=vertex|entryPoints.0.backendName=vertex_main|entryPoints.1.stage=fragment|entryPoints.1.backendName=fragment_main|resources.0.name=vertexParams|resources.0.kind=uniform|resources.1.name=fragmentParams|resources.1.kind=uniform|targetResourceBindings.0.bindingClass=uniform-buffer|targetResourceBindings.1.bindingClass=uniform-buffer"
    "-DEXPECTED_REFLECTION_JSON_ARRAY_LENGTHS=entryPoints=2|resources=2|targetResourceBindings=2|vertexLayouts=1|workgroupSizes=0"
    "-DEXPECTED_REFLECTION_FEATURE_FIELDS=glsl-lowering.kind=backend|vertex-shader.kind=stage|fragment-shader.kind=stage|uniform-buffer.kind=resource|local-declaration.kind=operation|vector-constructor.kind=operation"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
if(CROSSGL_HAS_OPENGL_NATIVE_VALIDATOR)
  add_test(NAME cglc_build_opengl_graphics_resources_glsl_validated
    COMMAND ${CMAKE_COMMAND}
      -DCGLC=$<TARGET_FILE:cglc>
      -DINPUT=${CROSSGL_OPENGL_GRAPHICS_RESOURCES_SHADER}
      -DTARGET=opengl
      -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-opengl-graphics-resources-validated.cglb
      -DMODE=source-package-build
      -DEXPECTED_SOURCE=backend/opengl/OpenGLGraphicsResourcesShader.graphics.glsl
      "-DEXPECTED_SOURCE_SNIPPET=${CROSSGL_OPENGL_GRAPHICS_RESOURCES_SOURCE_SNIPPET}"
      "-DEXPECTED_MANIFEST_JSON_FIELDS=schemaVersion=1|target=opengl|module=OpenGLGraphicsResourcesShader|artifacts.backendSource=backend/opengl/OpenGLGraphicsResourcesShader.graphics.glsl|artifacts.nativeBinary=backend/opengl/OpenGLGraphicsResourcesShader.glsl"
      "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=opengl|module=OpenGLGraphicsResourcesShader|nativeBinary=backend/opengl/OpenGLGraphicsResourcesShader.glsl|entryPoints.0.stage=vertex|entryPoints.0.backendName=vertex_main|entryPoints.1.stage=fragment|entryPoints.1.backendName=fragment_main|resources.0.name=vertexParams|resources.0.kind=uniform|resources.1.name=fragmentParams|resources.1.kind=uniform"
      "-DEXPECTED_REFLECTION_JSON_ARRAY_LENGTHS=entryPoints=2|resources=2|targetResourceBindings=2|vertexLayouts=1|workgroupSizes=0"
      "-DEXPECTED_REFLECTION_FEATURE_FIELDS=native-glsl-package.kind=backend|glsl-program-validation.kind=validation|vertex-shader.kind=stage|fragment-shader.kind=stage|uniform-buffer.kind=resource|local-declaration.kind=operation|vector-constructor.kind=operation"
      -DEXPECTED_NATIVE_BINARY=backend/opengl/OpenGLGraphicsResourcesShader.glsl
      -DEXPECTED_NATIVE_BINARY_STATUS=validated
      -DEXPECTED_DIAGNOSTIC=opengl.glsl-validated
      -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
  crossgl_label_optional_native_test(
    cglc_build_opengl_graphics_resources_glsl_validated opengl)
endif()
set(CROSSGL_OPENGL_GRAPHICS_TEXTURE_SAMPLER_RESOURCES_SOURCE_SNIPPET [=[#if defined(CROSSGL_STAGE_FRAGMENT)
// CrossGL set 0, binding 1
layout(binding = 1, std140) uniform material_Uniform {
  vec4 baseColor;
} material;

// CrossGL set 0, binding 2
layout(binding = 2) uniform sampler2D colorMap;

// CrossGL set 0, binding 3
// sampler linearSampler is represented by OpenGL combined sampler uniforms.]=])
add_test(NAME cglc_build_opengl_graphics_texture_sampler_resources_source_package
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_OPENGL_GRAPHICS_TEXTURE_SAMPLER_RESOURCES_SHADER}
    -DTARGET=opengl
    -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-opengl-graphics-texture-sampler-resources-source.cglb
    -DMODE=source-package-build
    -DEXPECTED_SOURCE=backend/opengl/OpenGLGraphicsTextureSamplerResourcesShader.graphics.glsl
    "-DEXPECTED_SOURCE_SNIPPET=${CROSSGL_OPENGL_GRAPHICS_TEXTURE_SAMPLER_RESOURCES_SOURCE_SNIPPET}"
    "-DEXPECTED_MANIFEST_JSON_FIELDS=schemaVersion=1|target=opengl|module=OpenGLGraphicsTextureSamplerResourcesShader|artifacts.backendSource=backend/opengl/OpenGLGraphicsTextureSamplerResourcesShader.graphics.glsl|artifacts.nativeBinary=backend/opengl/OpenGLGraphicsTextureSamplerResourcesShader.glsl"
    "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=opengl|module=OpenGLGraphicsTextureSamplerResourcesShader|nativeBinary=backend/opengl/OpenGLGraphicsTextureSamplerResourcesShader.glsl|entryPoints.0.stage=vertex|entryPoints.0.backendName=vertex_main|entryPoints.1.stage=fragment|entryPoints.1.backendName=fragment_main|resources.0.name=transform|resources.0.kind=uniform|resources.1.name=material|resources.1.kind=uniform|resources.2.name=colorMap|resources.2.kind=texture|resources.2.type=sampler2D|resources.3.name=linearSampler|resources.3.kind=sampler|resources.3.type=sampler|targetResourceBindings.0.bindingClass=uniform-buffer|targetResourceBindings.1.bindingClass=uniform-buffer|targetResourceBindings.2.bindingClass=texture|targetResourceBindings.3.bindingClass=sampler"
    "-DEXPECTED_REFLECTION_JSON_ARRAY_LENGTHS=entryPoints=2|resources=4|targetResourceBindings=4|vertexLayouts=1|workgroupSizes=0"
    "-DEXPECTED_REFLECTION_TARGET_FIELDS=colorMap.sourceType=sampler2D|colorMap.bindingClass=texture|colorMap.abi=programResourceBinding|colorMap.argumentIndex=2|linearSampler.sourceType=sampler|linearSampler.bindingClass=sampler|linearSampler.abi=programResourceBinding|linearSampler.argumentIndex=3"
    "-DEXPECTED_REFLECTION_FEATURE_FIELDS=glsl-lowering.kind=backend|vertex-shader.kind=stage|fragment-shader.kind=stage|uniform-buffer.kind=resource|sampled-texture.kind=resource|sampler-state.kind=resource|texture-sample.kind=operation|texture-explicit-lod.kind=operation"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
if(CROSSGL_HAS_OPENGL_NATIVE_VALIDATOR)
  add_test(NAME cglc_build_opengl_graphics_texture_sampler_resources_glsl_validated
    COMMAND ${CMAKE_COMMAND}
      -DCGLC=$<TARGET_FILE:cglc>
      -DINPUT=${CROSSGL_OPENGL_GRAPHICS_TEXTURE_SAMPLER_RESOURCES_SHADER}
      -DTARGET=opengl
      -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-opengl-graphics-texture-sampler-resources-validated.cglb
      -DMODE=source-package-build
      -DEXPECTED_SOURCE=backend/opengl/OpenGLGraphicsTextureSamplerResourcesShader.graphics.glsl
      "-DEXPECTED_SOURCE_SNIPPET=${CROSSGL_OPENGL_GRAPHICS_TEXTURE_SAMPLER_RESOURCES_SOURCE_SNIPPET}"
      "-DEXPECTED_MANIFEST_JSON_FIELDS=schemaVersion=1|target=opengl|module=OpenGLGraphicsTextureSamplerResourcesShader|artifacts.backendSource=backend/opengl/OpenGLGraphicsTextureSamplerResourcesShader.graphics.glsl|artifacts.nativeBinary=backend/opengl/OpenGLGraphicsTextureSamplerResourcesShader.glsl"
      "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=opengl|module=OpenGLGraphicsTextureSamplerResourcesShader|nativeBinary=backend/opengl/OpenGLGraphicsTextureSamplerResourcesShader.glsl|entryPoints.0.stage=vertex|entryPoints.0.backendName=vertex_main|entryPoints.1.stage=fragment|entryPoints.1.backendName=fragment_main|resources.0.name=transform|resources.0.kind=uniform|resources.1.name=material|resources.1.kind=uniform|resources.2.name=colorMap|resources.2.kind=texture|resources.3.name=linearSampler|resources.3.kind=sampler"
      "-DEXPECTED_REFLECTION_JSON_ARRAY_LENGTHS=entryPoints=2|resources=4|targetResourceBindings=4|vertexLayouts=1|workgroupSizes=0"
      "-DEXPECTED_REFLECTION_TARGET_FIELDS=colorMap.sourceType=sampler2D|colorMap.bindingClass=texture|linearSampler.sourceType=sampler|linearSampler.bindingClass=sampler"
      "-DEXPECTED_REFLECTION_FEATURE_FIELDS=native-glsl-package.kind=backend|glsl-program-validation.kind=validation|vertex-shader.kind=stage|fragment-shader.kind=stage|uniform-buffer.kind=resource|sampled-texture.kind=resource|sampler-state.kind=resource|texture-sample.kind=operation|texture-explicit-lod.kind=operation"
      -DEXPECTED_NATIVE_BINARY=backend/opengl/OpenGLGraphicsTextureSamplerResourcesShader.glsl
      -DEXPECTED_NATIVE_BINARY_STATUS=validated
      -DEXPECTED_DIAGNOSTIC=opengl.glsl-validated
      -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
  crossgl_label_optional_native_test(
    cglc_build_opengl_graphics_texture_sampler_resources_glsl_validated opengl)
endif()
set(CROSSGL_OPENGL_GRAPHICS_DESCRIPTOR_ARRAY_RESOURCES_SOURCE_SNIPPET [=[#if defined(CROSSGL_STAGE_VERTEX)
// CrossGL set 0, binding 2
layout(binding = 2) uniform sampler2D heightMaps[RESOURCE_COUNT];

// CrossGL set 0, binding 3
// sampler vertexSamplers is represented by OpenGL combined sampler uniforms.]=])
add_test(NAME cglc_build_opengl_graphics_descriptor_array_resources_source_package
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_OPENGL_GRAPHICS_DESCRIPTOR_ARRAY_RESOURCES_SHADER}
    -DTARGET=opengl
    -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-opengl-graphics-descriptor-array-resources-source.cglb
    -DMODE=source-package-build
    -DEXPECTED_SOURCE=backend/opengl/OpenGLGraphicsDescriptorArrayResourcesShader.graphics.glsl
    "-DEXPECTED_SOURCE_SNIPPET=${CROSSGL_OPENGL_GRAPHICS_DESCRIPTOR_ARRAY_RESOURCES_SOURCE_SNIPPET}"
    "-DEXPECTED_MANIFEST_JSON_FIELDS=schemaVersion=1|target=opengl|module=OpenGLGraphicsDescriptorArrayResourcesShader|artifacts.backendSource=backend/opengl/OpenGLGraphicsDescriptorArrayResourcesShader.graphics.glsl|artifacts.nativeBinary=backend/opengl/OpenGLGraphicsDescriptorArrayResourcesShader.glsl"
    "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=opengl|module=OpenGLGraphicsDescriptorArrayResourcesShader|nativeBinary=backend/opengl/OpenGLGraphicsDescriptorArrayResourcesShader.glsl|entryPoints.0.stage=vertex|entryPoints.0.backendName=vertex_main|entryPoints.1.stage=fragment|entryPoints.1.backendName=fragment_main|resources.0.stage=vertex|resources.0.name=heightMaps|resources.0.kind=texture|resources.0.type=sampler2D[RESOURCE_COUNT]|resources.1.stage=vertex|resources.1.name=vertexSamplers|resources.1.kind=sampler|resources.1.type=sampler[RESOURCE_COUNT]|resources.2.stage=fragment|resources.2.name=colorMaps|resources.2.kind=texture|resources.2.type=sampler2D[RESOURCE_COUNT]|resources.3.stage=fragment|resources.3.name=linearSamplers|resources.3.kind=sampler|resources.3.type=sampler[RESOURCE_COUNT]"
    "-DEXPECTED_REFLECTION_JSON_ARRAY_LENGTHS=entryPoints=2|resources=4|targetResourceBindings=4|vertexLayouts=1|workgroupSizes=0"
    "-DEXPECTED_REFLECTION_TARGET_FIELDS=heightMaps.stage=vertex|heightMaps.entryPoint=vertex_main|heightMaps.sourceType=sampler2D[RESOURCE_COUNT]|heightMaps.bindingClass=texture|heightMaps.abi=programResourceBinding|heightMaps.argumentIndex=2|heightMaps.arraySize=RESOURCE_COUNT|heightMaps.arrayElementCount=2|vertexSamplers.stage=vertex|vertexSamplers.entryPoint=vertex_main|vertexSamplers.sourceType=sampler[RESOURCE_COUNT]|vertexSamplers.bindingClass=sampler|vertexSamplers.argumentIndex=3|vertexSamplers.arrayElementCount=2|colorMaps.stage=fragment|colorMaps.entryPoint=fragment_main|colorMaps.sourceType=sampler2D[RESOURCE_COUNT]|colorMaps.bindingClass=texture|colorMaps.argumentIndex=4|colorMaps.arrayElementCount=2|linearSamplers.stage=fragment|linearSamplers.entryPoint=fragment_main|linearSamplers.sourceType=sampler[RESOURCE_COUNT]|linearSamplers.bindingClass=sampler|linearSamplers.argumentIndex=5|linearSamplers.arrayElementCount=2"
    "-DEXPECTED_REFLECTION_FEATURE_FIELDS=glsl-lowering.kind=backend|vertex-shader.kind=stage|fragment-shader.kind=stage|sampled-texture.kind=resource|sampler-state.kind=resource|descriptor-array.kind=resource|texture-sample.kind=operation|texture-explicit-lod.kind=operation|index-access.kind=operation"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
if(CROSSGL_HAS_OPENGL_NATIVE_VALIDATOR)
  add_test(NAME cglc_build_opengl_graphics_descriptor_array_resources_glsl_validated
    COMMAND ${CMAKE_COMMAND}
      -DCGLC=$<TARGET_FILE:cglc>
      -DINPUT=${CROSSGL_OPENGL_GRAPHICS_DESCRIPTOR_ARRAY_RESOURCES_SHADER}
      -DTARGET=opengl
      -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-opengl-graphics-descriptor-array-resources-validated.cglb
      -DMODE=source-package-build
      -DEXPECTED_SOURCE=backend/opengl/OpenGLGraphicsDescriptorArrayResourcesShader.graphics.glsl
      "-DEXPECTED_SOURCE_SNIPPET=${CROSSGL_OPENGL_GRAPHICS_DESCRIPTOR_ARRAY_RESOURCES_SOURCE_SNIPPET}"
      "-DEXPECTED_MANIFEST_JSON_FIELDS=schemaVersion=1|target=opengl|module=OpenGLGraphicsDescriptorArrayResourcesShader|artifacts.backendSource=backend/opengl/OpenGLGraphicsDescriptorArrayResourcesShader.graphics.glsl|artifacts.nativeBinary=backend/opengl/OpenGLGraphicsDescriptorArrayResourcesShader.glsl"
      "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=opengl|module=OpenGLGraphicsDescriptorArrayResourcesShader|nativeBinary=backend/opengl/OpenGLGraphicsDescriptorArrayResourcesShader.glsl|entryPoints.0.stage=vertex|entryPoints.1.stage=fragment|resources.0.name=heightMaps|resources.1.name=vertexSamplers|resources.2.name=colorMaps|resources.3.name=linearSamplers"
      "-DEXPECTED_REFLECTION_JSON_ARRAY_LENGTHS=entryPoints=2|resources=4|targetResourceBindings=4|vertexLayouts=1|workgroupSizes=0"
      "-DEXPECTED_REFLECTION_TARGET_FIELDS=heightMaps.stage=vertex|heightMaps.sourceType=sampler2D[RESOURCE_COUNT]|heightMaps.bindingClass=texture|heightMaps.arrayElementCount=2|vertexSamplers.stage=vertex|vertexSamplers.sourceType=sampler[RESOURCE_COUNT]|vertexSamplers.bindingClass=sampler|vertexSamplers.arrayElementCount=2|colorMaps.stage=fragment|colorMaps.sourceType=sampler2D[RESOURCE_COUNT]|colorMaps.bindingClass=texture|colorMaps.arrayElementCount=2|linearSamplers.stage=fragment|linearSamplers.sourceType=sampler[RESOURCE_COUNT]|linearSamplers.bindingClass=sampler|linearSamplers.arrayElementCount=2"
      "-DEXPECTED_REFLECTION_FEATURE_FIELDS=native-glsl-package.kind=backend|glsl-program-validation.kind=validation|vertex-shader.kind=stage|fragment-shader.kind=stage|sampled-texture.kind=resource|sampler-state.kind=resource|descriptor-array.kind=resource|texture-sample.kind=operation|texture-explicit-lod.kind=operation|index-access.kind=operation"
      -DEXPECTED_NATIVE_BINARY=backend/opengl/OpenGLGraphicsDescriptorArrayResourcesShader.glsl
      -DEXPECTED_NATIVE_BINARY_STATUS=validated
      -DEXPECTED_DIAGNOSTIC=opengl.glsl-validated
      -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
  crossgl_label_optional_native_test(
    cglc_build_opengl_graphics_descriptor_array_resources_glsl_validated opengl)
endif()
set(CROSSGL_OPENGL_GRAPHICS_SHADOW_COMPARE_RESOURCES_SOURCE_SNIPPET [=[#if defined(CROSSGL_STAGE_FRAGMENT)
// CrossGL set 0, binding 2
layout(binding = 2) uniform sampler2DShadow shadowMap;

// CrossGL set 0, binding 3
// sampler shadowSampler is represented by OpenGL combined sampler uniforms.

layout(location = 0) in vec2 crossgl_varying_uv;
layout(location = 0) out vec4 crossgl_out_color;

FragmentOutput fragment_main(FragmentInput crossgl_user_input) {
  FragmentOutput crossgl_user_output;
  float visibility = texture(shadowMap, vec3(crossgl_user_input.uv, 0.5));]=])
add_test(NAME cglc_build_opengl_graphics_shadow_compare_resources_source_package
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_OPENGL_GRAPHICS_SHADOW_COMPARE_RESOURCES_SHADER}
    -DTARGET=opengl
    -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-opengl-graphics-shadow-compare-resources-source.cglb
    -DMODE=source-package-build
    -DEXPECTED_SOURCE=backend/opengl/OpenGLGraphicsShadowCompareResourcesShader.graphics.glsl
    "-DEXPECTED_SOURCE_SNIPPET=${CROSSGL_OPENGL_GRAPHICS_SHADOW_COMPARE_RESOURCES_SOURCE_SNIPPET}"
    "-DEXPECTED_MANIFEST_JSON_FIELDS=schemaVersion=1|target=opengl|module=OpenGLGraphicsShadowCompareResourcesShader|artifacts.backendSource=backend/opengl/OpenGLGraphicsShadowCompareResourcesShader.graphics.glsl|artifacts.nativeBinary=backend/opengl/OpenGLGraphicsShadowCompareResourcesShader.glsl"
    "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=opengl|module=OpenGLGraphicsShadowCompareResourcesShader|nativeBinary=backend/opengl/OpenGLGraphicsShadowCompareResourcesShader.glsl|entryPoints.0.stage=vertex|entryPoints.0.backendName=vertex_main|entryPoints.1.stage=fragment|entryPoints.1.backendName=fragment_main|resources.0.name=shadowMap|resources.0.kind=texture|resources.0.type=sampler2DShadow|resources.1.name=shadowSampler|resources.1.kind=sampler|resources.1.type=comparison_sampler|targetResourceBindings.0.bindingClass=texture|targetResourceBindings.1.bindingClass=sampler"
    "-DEXPECTED_REFLECTION_JSON_ARRAY_LENGTHS=entryPoints=2|resources=2|targetResourceBindings=2|vertexLayouts=1|workgroupSizes=0|manualTextureCompareKernels=0"
    "-DEXPECTED_REFLECTION_TARGET_FIELDS=shadowMap.sourceType=sampler2DShadow|shadowMap.bindingClass=texture|shadowMap.abi=programResourceBinding|shadowMap.argumentIndex=2|shadowSampler.sourceType=comparison_sampler|shadowSampler.bindingClass=sampler|shadowSampler.abi=programResourceBinding|shadowSampler.argumentIndex=3"
    "-DEXPECTED_REFLECTION_FEATURE_FIELDS=glsl-lowering.kind=backend|vertex-shader.kind=stage|fragment-shader.kind=stage|sampled-texture.kind=resource|depth-compare-format.kind=texture|sampler-state.kind=resource|texture-shadow-compare.kind=operation"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
if(CROSSGL_HAS_OPENGL_NATIVE_VALIDATOR)
  add_test(NAME cglc_build_opengl_graphics_shadow_compare_resources_glsl_validated
    COMMAND ${CMAKE_COMMAND}
      -DCGLC=$<TARGET_FILE:cglc>
      -DINPUT=${CROSSGL_OPENGL_GRAPHICS_SHADOW_COMPARE_RESOURCES_SHADER}
      -DTARGET=opengl
      -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-opengl-graphics-shadow-compare-resources-validated.cglb
      -DMODE=source-package-build
      -DEXPECTED_SOURCE=backend/opengl/OpenGLGraphicsShadowCompareResourcesShader.graphics.glsl
      "-DEXPECTED_SOURCE_SNIPPET=${CROSSGL_OPENGL_GRAPHICS_SHADOW_COMPARE_RESOURCES_SOURCE_SNIPPET}"
      "-DEXPECTED_MANIFEST_JSON_FIELDS=schemaVersion=1|target=opengl|module=OpenGLGraphicsShadowCompareResourcesShader|artifacts.backendSource=backend/opengl/OpenGLGraphicsShadowCompareResourcesShader.graphics.glsl|artifacts.nativeBinary=backend/opengl/OpenGLGraphicsShadowCompareResourcesShader.glsl"
      "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=opengl|module=OpenGLGraphicsShadowCompareResourcesShader|nativeBinary=backend/opengl/OpenGLGraphicsShadowCompareResourcesShader.glsl|entryPoints.0.stage=vertex|entryPoints.0.backendName=vertex_main|entryPoints.1.stage=fragment|entryPoints.1.backendName=fragment_main|resources.0.name=shadowMap|resources.0.kind=texture|resources.1.name=shadowSampler|resources.1.kind=sampler"
      "-DEXPECTED_REFLECTION_JSON_ARRAY_LENGTHS=entryPoints=2|resources=2|targetResourceBindings=2|vertexLayouts=1|workgroupSizes=0|manualTextureCompareKernels=0"
      "-DEXPECTED_REFLECTION_TARGET_FIELDS=shadowMap.sourceType=sampler2DShadow|shadowMap.bindingClass=texture|shadowSampler.sourceType=comparison_sampler|shadowSampler.bindingClass=sampler"
      "-DEXPECTED_REFLECTION_FEATURE_FIELDS=native-glsl-package.kind=backend|glsl-program-validation.kind=validation|vertex-shader.kind=stage|fragment-shader.kind=stage|sampled-texture.kind=resource|depth-compare-format.kind=texture|sampler-state.kind=resource|texture-shadow-compare.kind=operation"
      -DEXPECTED_NATIVE_BINARY=backend/opengl/OpenGLGraphicsShadowCompareResourcesShader.glsl
      -DEXPECTED_NATIVE_BINARY_STATUS=validated
      -DEXPECTED_DIAGNOSTIC=opengl.glsl-validated
      -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
  crossgl_label_optional_native_test(
    cglc_build_opengl_graphics_shadow_compare_resources_glsl_validated opengl)
endif()
set(CROSSGL_OPENGL_GRAPHICS_SHADOW_COMPARE_LOD_RESOURCES_SOURCE_SNIPPET [=[#if defined(CROSSGL_STAGE_FRAGMENT)
// CrossGL set 0, binding 2
layout(binding = 2) uniform sampler2DShadow shadowMap;

// CrossGL set 0, binding 3
// sampler shadowSampler is represented by OpenGL combined sampler uniforms.

layout(location = 0) in vec2 crossgl_varying_uv;
layout(location = 0) out vec4 crossgl_out_color;

FragmentOutput fragment_main(FragmentInput crossgl_user_input) {
  FragmentOutput crossgl_user_output;
  float visibility = textureLod(shadowMap, vec3(crossgl_user_input.uv, 0.5), 1.5);]=])
add_test(NAME cglc_build_opengl_graphics_shadow_compare_lod_resources_source_package
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_OPENGL_GRAPHICS_SHADOW_COMPARE_LOD_RESOURCES_SHADER}
    -DTARGET=opengl
    -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-opengl-graphics-shadow-compare-lod-resources-source.cglb
    -DMODE=source-package-build
    -DEXPECTED_SOURCE=backend/opengl/OpenGLGraphicsShadowCompareLodResourcesShader.graphics.glsl
    "-DEXPECTED_SOURCE_SNIPPET=${CROSSGL_OPENGL_GRAPHICS_SHADOW_COMPARE_LOD_RESOURCES_SOURCE_SNIPPET}"
    "-DEXPECTED_MANIFEST_JSON_FIELDS=schemaVersion=1|target=opengl|module=OpenGLGraphicsShadowCompareLodResourcesShader|artifacts.backendSource=backend/opengl/OpenGLGraphicsShadowCompareLodResourcesShader.graphics.glsl|artifacts.nativeBinary=backend/opengl/OpenGLGraphicsShadowCompareLodResourcesShader.glsl"
    "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=opengl|module=OpenGLGraphicsShadowCompareLodResourcesShader|nativeBinary=backend/opengl/OpenGLGraphicsShadowCompareLodResourcesShader.glsl|entryPoints.0.stage=vertex|entryPoints.0.backendName=vertex_main|entryPoints.1.stage=fragment|entryPoints.1.backendName=fragment_main|resources.0.stage=fragment|resources.0.name=shadowMap|resources.0.kind=texture|resources.0.type=sampler2DShadow|resources.0.set=0|resources.0.binding=2|resources.1.stage=fragment|resources.1.name=shadowSampler|resources.1.kind=sampler|resources.1.type=comparison_sampler|resources.1.set=0|resources.1.binding=3|targetResourceBindings.0.bindingClass=texture|targetResourceBindings.1.bindingClass=sampler|manualTextureCompareKernelSummary.totalCount=0"
    "-DEXPECTED_REFLECTION_JSON_ARRAY_LENGTHS=entryPoints=2|resources=2|targetResourceBindings=2|vertexLayouts=1|workgroupSizes=0|manualTextureCompareKernels=0"
    "-DEXPECTED_REFLECTION_TARGET_FIELDS=shadowMap.stage=fragment|shadowMap.entryPoint=fragment_main|shadowMap.sourceType=sampler2DShadow|shadowMap.addressSpace=texture|shadowMap.bindingClass=texture|shadowMap.abi=programResourceBinding|shadowMap.argumentIndex=2|shadowMap.set=0|shadowMap.binding=2|shadowSampler.stage=fragment|shadowSampler.entryPoint=fragment_main|shadowSampler.sourceType=comparison_sampler|shadowSampler.addressSpace=sampler|shadowSampler.bindingClass=sampler|shadowSampler.abi=programResourceBinding|shadowSampler.argumentIndex=3|shadowSampler.set=0|shadowSampler.binding=3"
    "-DEXPECTED_REFLECTION_FEATURE_FIELDS=glsl-lowering.kind=backend|vertex-shader.kind=stage|fragment-shader.kind=stage|sampled-texture.kind=resource|depth-compare-format.kind=texture|sampler-state.kind=resource|texture-shadow-compare.kind=operation|texture-shadow-compare-explicit-lod.kind=operation"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_build_opengl_graphics_shadow_compare_lod_resources_fake_glslang_success
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_OPENGL_GRAPHICS_SHADOW_COMPARE_LOD_RESOURCES_SHADER}
    -DTARGET=opengl
    -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-opengl-graphics-shadow-compare-lod-resources-fake-validated.cglb
    -DMODE=source-package-build
    -DTOOLCHAIN_PATH=${CROSSGL_FAKE_GLSLANG_SUCCESS_DIR}
    -DTOOLCHAIN_DISABLE_FALLBACK=ON
    -DEXPECTED_SOURCE=backend/opengl/OpenGLGraphicsShadowCompareLodResourcesShader.graphics.glsl
    "-DEXPECTED_SOURCE_SNIPPET=#extension GL_EXT_texture_shadow_lod : require"
    "-DEXPECTED_MANIFEST_JSON_FIELDS=schemaVersion=1|target=opengl|module=OpenGLGraphicsShadowCompareLodResourcesShader|artifacts.backendSource=backend/opengl/OpenGLGraphicsShadowCompareLodResourcesShader.graphics.glsl|artifacts.nativeBinary=backend/opengl/OpenGLGraphicsShadowCompareLodResourcesShader.glsl"
    "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=opengl|module=OpenGLGraphicsShadowCompareLodResourcesShader|nativeBinary=backend/opengl/OpenGLGraphicsShadowCompareLodResourcesShader.glsl|entryPoints.0.stage=vertex|entryPoints.1.stage=fragment"
    "-DEXPECTED_REFLECTION_FEATURE_FIELDS=native-glsl-package.kind=backend|glsl-program-validation.kind=validation|texture-shadow-compare-explicit-lod.kind=operation"
    -DEXPECTED_NATIVE_BINARY=backend/opengl/OpenGLGraphicsShadowCompareLodResourcesShader.glsl
    -DEXPECTED_NATIVE_BINARY_STATUS=validated
    "-DEXPECTED_DIAGNOSTICS_JSON_FIELDS=diagnostics.0.severity=note|diagnostics.0.code=opengl.glsl-validated"
    -DEXPECTED_DIAGNOSTIC=opengl.glsl-validated
    "-DEXPECTED_DIAGNOSTIC_FIELD_CONTAINS=message=GLSL 450|message=GL_EXT_texture_shadow_lod"
    "-DEXPECTED_DIAGNOSTICS_JSON_ARRAY_LENGTHS=diagnostics=1"
    -DEXPECTED_TOOL_LOG=${CROSSGL_FAKE_GLSLANG_SUCCESS_DIR}/glslangValidator.log
    "-DEXPECTED_TOOL_LOG_CONTAINS=glslangValidator success: -l -S vert -DCROSSGL_STAGE_VERTEX=1"
    -DEXPECTED_SECOND_TOOL_LOG=${CROSSGL_FAKE_GLSLANG_SUCCESS_DIR}/glslangValidator.log
    "-DEXPECTED_SECOND_TOOL_LOG_CONTAINS=glslangValidator success: -l -S frag -DCROSSGL_STAGE_FRAGMENT=1"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
if(CROSSGL_HAS_OPENGL_NATIVE_VALIDATOR)
  add_test(NAME cglc_build_opengl_graphics_shadow_compare_lod_resources_glsl_validated
    COMMAND ${CMAKE_COMMAND}
      -DCGLC=$<TARGET_FILE:cglc>
      -DINPUT=${CROSSGL_OPENGL_GRAPHICS_SHADOW_COMPARE_LOD_RESOURCES_SHADER}
      -DTARGET=opengl
      -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-opengl-graphics-shadow-compare-lod-resources-validated.cglb
      -DMODE=source-package-build
      -DEXPECTED_SOURCE=backend/opengl/OpenGLGraphicsShadowCompareLodResourcesShader.graphics.glsl
      "-DEXPECTED_SOURCE_SNIPPET=${CROSSGL_OPENGL_GRAPHICS_SHADOW_COMPARE_LOD_RESOURCES_SOURCE_SNIPPET}"
      "-DEXPECTED_MANIFEST_JSON_FIELDS=schemaVersion=1|target=opengl|module=OpenGLGraphicsShadowCompareLodResourcesShader|artifacts.backendSource=backend/opengl/OpenGLGraphicsShadowCompareLodResourcesShader.graphics.glsl|artifacts.nativeBinary=backend/opengl/OpenGLGraphicsShadowCompareLodResourcesShader.glsl"
      "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=opengl|module=OpenGLGraphicsShadowCompareLodResourcesShader|nativeBinary=backend/opengl/OpenGLGraphicsShadowCompareLodResourcesShader.glsl|entryPoints.0.stage=vertex|entryPoints.0.backendName=vertex_main|entryPoints.1.stage=fragment|entryPoints.1.backendName=fragment_main|resources.0.stage=fragment|resources.0.name=shadowMap|resources.0.kind=texture|resources.0.type=sampler2DShadow|resources.0.set=0|resources.0.binding=2|resources.1.stage=fragment|resources.1.name=shadowSampler|resources.1.kind=sampler|resources.1.type=comparison_sampler|resources.1.set=0|resources.1.binding=3|targetResourceBindings.0.bindingClass=texture|targetResourceBindings.1.bindingClass=sampler|manualTextureCompareKernelSummary.totalCount=0"
      "-DEXPECTED_REFLECTION_JSON_ARRAY_LENGTHS=entryPoints=2|resources=2|targetResourceBindings=2|vertexLayouts=1|workgroupSizes=0|manualTextureCompareKernels=0"
      "-DEXPECTED_REFLECTION_TARGET_FIELDS=shadowMap.stage=fragment|shadowMap.entryPoint=fragment_main|shadowMap.sourceType=sampler2DShadow|shadowMap.addressSpace=texture|shadowMap.bindingClass=texture|shadowMap.abi=programResourceBinding|shadowMap.argumentIndex=2|shadowMap.set=0|shadowMap.binding=2|shadowSampler.stage=fragment|shadowSampler.entryPoint=fragment_main|shadowSampler.sourceType=comparison_sampler|shadowSampler.addressSpace=sampler|shadowSampler.bindingClass=sampler|shadowSampler.abi=programResourceBinding|shadowSampler.argumentIndex=3|shadowSampler.set=0|shadowSampler.binding=3"
      "-DEXPECTED_REFLECTION_FEATURE_FIELDS=native-glsl-package.kind=backend|glsl-program-validation.kind=validation|vertex-shader.kind=stage|fragment-shader.kind=stage|sampled-texture.kind=resource|depth-compare-format.kind=texture|sampler-state.kind=resource|texture-shadow-compare.kind=operation|texture-shadow-compare-explicit-lod.kind=operation"
      -DEXPECTED_NATIVE_BINARY=backend/opengl/OpenGLGraphicsShadowCompareLodResourcesShader.glsl
      -DEXPECTED_NATIVE_BINARY_STATUS=validated
      -DEXPECTED_DIAGNOSTIC=opengl.glsl-validated
      -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
  crossgl_label_optional_native_test(
    cglc_build_opengl_graphics_shadow_compare_lod_resources_glsl_validated opengl)
endif()
set(CROSSGL_OPENGL_GRAPHICS_SHADOW_DESCRIPTOR_ARRAY_SOURCE_SNIPPET [=[#extension GL_EXT_texture_shadow_lod : require
const int SHADOW_COUNT = 2;

struct VertexInput {
  vec3 position;
  vec2 texCoord;
};
struct VertexOutput {
  vec2 uv;
  vec4 position;
};
struct FragmentInput {
  vec2 uv;
};
struct FragmentOutput {
  vec4 color;
};

#if defined(CROSSGL_STAGE_VERTEX)
// CrossGL set 0, binding 6
layout(binding = 6) uniform sampler2DShadow vertexShadowMaps[SHADOW_COUNT];]=])
add_test(NAME cglc_build_opengl_graphics_shadow_descriptor_array_source_package
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_OPENGL_GRAPHICS_SHADOW_DESCRIPTOR_ARRAY_SHADER}
    -DTARGET=opengl
    -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-opengl-graphics-shadow-descriptor-array-source.cglb
    -DMODE=source-package-build
    -DEXPECTED_SOURCE=backend/opengl/OpenGLGraphicsShadowDescriptorArrayShader.graphics.glsl
    "-DEXPECTED_SOURCE_SNIPPET=${CROSSGL_OPENGL_GRAPHICS_SHADOW_DESCRIPTOR_ARRAY_SOURCE_SNIPPET}"
    "-DEXPECTED_MANIFEST_JSON_FIELDS=schemaVersion=1|target=opengl|module=OpenGLGraphicsShadowDescriptorArrayShader|artifacts.backendSource=backend/opengl/OpenGLGraphicsShadowDescriptorArrayShader.graphics.glsl|artifacts.nativeBinary=backend/opengl/OpenGLGraphicsShadowDescriptorArrayShader.glsl"
    "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=opengl|module=OpenGLGraphicsShadowDescriptorArrayShader|nativeBinary=backend/opengl/OpenGLGraphicsShadowDescriptorArrayShader.glsl|entryPoints.0.stage=vertex|entryPoints.0.backendName=vertex_main|entryPoints.1.stage=fragment|entryPoints.1.backendName=fragment_main|resources.0.stage=vertex|resources.0.name=vertexShadowMaps|resources.0.kind=texture|resources.0.type=sampler2DShadow[SHADOW_COUNT]|resources.1.stage=vertex|resources.1.name=vertexShadowSamplers|resources.1.kind=sampler|resources.1.type=comparison_sampler[SHADOW_COUNT]|resources.2.stage=fragment|resources.2.name=shadowAtlases|resources.2.kind=texture|resources.2.type=sampler2DArrayShadow[SHADOW_COUNT]|resources.3.stage=fragment|resources.3.name=atlasSamplers|resources.3.kind=sampler|resources.3.type=comparison_sampler[SHADOW_COUNT]|manualTextureCompareKernelSummary.totalCount=0"
    "-DEXPECTED_REFLECTION_JSON_ARRAY_LENGTHS=entryPoints=2|resources=4|targetResourceBindings=4|vertexLayouts=1|workgroupSizes=0|manualTextureCompareKernels=0"
    "-DEXPECTED_REFLECTION_TARGET_FIELDS=vertexShadowMaps.stage=vertex|vertexShadowMaps.entryPoint=vertex_main|vertexShadowMaps.sourceType=sampler2DShadow[SHADOW_COUNT]|vertexShadowMaps.bindingClass=texture|vertexShadowMaps.argumentIndex=6|vertexShadowMaps.arrayElementCount=2|vertexShadowSamplers.stage=vertex|vertexShadowSamplers.entryPoint=vertex_main|vertexShadowSamplers.sourceType=comparison_sampler[SHADOW_COUNT]|vertexShadowSamplers.bindingClass=sampler|vertexShadowSamplers.argumentIndex=7|vertexShadowSamplers.arrayElementCount=2|shadowAtlases.stage=fragment|shadowAtlases.entryPoint=fragment_main|shadowAtlases.sourceType=sampler2DArrayShadow[SHADOW_COUNT]|shadowAtlases.bindingClass=texture|shadowAtlases.argumentIndex=8|shadowAtlases.arrayElementCount=2|atlasSamplers.stage=fragment|atlasSamplers.entryPoint=fragment_main|atlasSamplers.sourceType=comparison_sampler[SHADOW_COUNT]|atlasSamplers.bindingClass=sampler|atlasSamplers.argumentIndex=9|atlasSamplers.arrayElementCount=2"
    "-DEXPECTED_REFLECTION_FEATURE_FIELDS=glsl-lowering.kind=backend|vertex-shader.kind=stage|fragment-shader.kind=stage|sampled-texture.kind=resource|depth-compare-format.kind=texture|array-dimension.kind=texture|sampler-state.kind=resource|descriptor-array.kind=resource|texture-shadow-compare.kind=operation|texture-shadow-compare-explicit-lod.kind=operation|index-access.kind=operation"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
if(CROSSGL_HAS_OPENGL_NATIVE_VALIDATOR)
  add_test(NAME cglc_build_opengl_graphics_shadow_descriptor_array_glsl_validated
    COMMAND ${CMAKE_COMMAND}
      -DCGLC=$<TARGET_FILE:cglc>
      -DINPUT=${CROSSGL_OPENGL_GRAPHICS_SHADOW_DESCRIPTOR_ARRAY_SHADER}
      -DTARGET=opengl
      -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-opengl-graphics-shadow-descriptor-array-validated.cglb
      -DMODE=source-package-build
      -DEXPECTED_SOURCE=backend/opengl/OpenGLGraphicsShadowDescriptorArrayShader.graphics.glsl
      "-DEXPECTED_SOURCE_SNIPPET=${CROSSGL_OPENGL_GRAPHICS_SHADOW_DESCRIPTOR_ARRAY_SOURCE_SNIPPET}"
      "-DEXPECTED_MANIFEST_JSON_FIELDS=schemaVersion=1|target=opengl|module=OpenGLGraphicsShadowDescriptorArrayShader|artifacts.backendSource=backend/opengl/OpenGLGraphicsShadowDescriptorArrayShader.graphics.glsl|artifacts.nativeBinary=backend/opengl/OpenGLGraphicsShadowDescriptorArrayShader.glsl"
      "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=opengl|module=OpenGLGraphicsShadowDescriptorArrayShader|nativeBinary=backend/opengl/OpenGLGraphicsShadowDescriptorArrayShader.glsl|entryPoints.0.stage=vertex|entryPoints.1.stage=fragment|resources.0.name=vertexShadowMaps|resources.1.name=vertexShadowSamplers|resources.2.name=shadowAtlases|resources.3.name=atlasSamplers"
      "-DEXPECTED_REFLECTION_JSON_ARRAY_LENGTHS=entryPoints=2|resources=4|targetResourceBindings=4|vertexLayouts=1|workgroupSizes=0|manualTextureCompareKernels=0"
      "-DEXPECTED_REFLECTION_TARGET_FIELDS=vertexShadowMaps.stage=vertex|vertexShadowMaps.sourceType=sampler2DShadow[SHADOW_COUNT]|vertexShadowMaps.bindingClass=texture|vertexShadowMaps.arrayElementCount=2|vertexShadowSamplers.stage=vertex|vertexShadowSamplers.sourceType=comparison_sampler[SHADOW_COUNT]|vertexShadowSamplers.bindingClass=sampler|vertexShadowSamplers.arrayElementCount=2|shadowAtlases.stage=fragment|shadowAtlases.sourceType=sampler2DArrayShadow[SHADOW_COUNT]|shadowAtlases.bindingClass=texture|shadowAtlases.arrayElementCount=2|atlasSamplers.stage=fragment|atlasSamplers.sourceType=comparison_sampler[SHADOW_COUNT]|atlasSamplers.bindingClass=sampler|atlasSamplers.arrayElementCount=2"
      "-DEXPECTED_REFLECTION_FEATURE_FIELDS=native-glsl-package.kind=backend|glsl-program-validation.kind=validation|vertex-shader.kind=stage|fragment-shader.kind=stage|sampled-texture.kind=resource|depth-compare-format.kind=texture|array-dimension.kind=texture|sampler-state.kind=resource|descriptor-array.kind=resource|texture-shadow-compare.kind=operation|texture-shadow-compare-explicit-lod.kind=operation|index-access.kind=operation"
      -DEXPECTED_NATIVE_BINARY=backend/opengl/OpenGLGraphicsShadowDescriptorArrayShader.glsl
      -DEXPECTED_NATIVE_BINARY_STATUS=validated
      -DEXPECTED_DIAGNOSTIC=opengl.glsl-validated
      -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
  crossgl_label_optional_native_test(
    cglc_build_opengl_graphics_shadow_descriptor_array_glsl_validated opengl)
endif()
set(CROSSGL_OPENGL_GRAPHICS_RESERVED_IDENTIFIERS_SOURCE_SNIPPET [=[struct VertexInput {
  vec3 position;
  vec2 crossgl_user_sample;
  float crossgl_user_smooth;
};
struct VertexOutput {
  vec2 crossgl_user_sample;
  float crossgl_user_smooth;
  vec4 position;
};
struct FragmentInput {
  vec2 crossgl_user_sample;
  float crossgl_user_smooth;
};
struct FragmentOutput {
  vec4 crossgl_user_sample;
};

#if defined(CROSSGL_STAGE_VERTEX)
layout(location = 0) in vec3 crossgl_attr_position;
layout(location = 1) in vec2 crossgl_attr_sample;
layout(location = 2) in float crossgl_attr_smooth;
layout(location = 0) out vec2 crossgl_varying_sample;
layout(location = 1) out float crossgl_varying_smooth;

vec2 lift(vec2 crossgl_user_sample, float crossgl_user_smooth);

vec2 lift(vec2 crossgl_user_sample, float crossgl_user_smooth) {
  vec2 crossgl_user_centroid = crossgl_user_sample + vec2(crossgl_user_smooth, crossgl_user_smooth);
  return crossgl_user_centroid;
}]=])
add_test(NAME cglc_build_opengl_graphics_reserved_identifiers_source_package
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_OPENGL_GRAPHICS_RESERVED_IDENTIFIERS_SHADER}
    -DTARGET=opengl
    -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-opengl-graphics-reserved-identifiers-source.cglb
    -DMODE=source-package-build
    -DEXPECTED_SOURCE=backend/opengl/OpenGLGraphicsReservedIdentifiersShader.graphics.glsl
    "-DEXPECTED_SOURCE_SNIPPET=${CROSSGL_OPENGL_GRAPHICS_RESERVED_IDENTIFIERS_SOURCE_SNIPPET}"
    "-DEXPECTED_MANIFEST_JSON_FIELDS=schemaVersion=1|target=opengl|module=OpenGLGraphicsReservedIdentifiersShader|artifacts.backendSource=backend/opengl/OpenGLGraphicsReservedIdentifiersShader.graphics.glsl|artifacts.nativeBinary=backend/opengl/OpenGLGraphicsReservedIdentifiersShader.glsl"
    "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=opengl|module=OpenGLGraphicsReservedIdentifiersShader|nativeBinary=backend/opengl/OpenGLGraphicsReservedIdentifiersShader.glsl|entryPoints.0.stage=vertex|entryPoints.0.backendName=vertex_main|entryPoints.1.stage=fragment|entryPoints.1.backendName=fragment_main|vertexLayouts.0.attributes.1.name=sample|vertexLayouts.0.attributes.2.name=smooth"
    "-DEXPECTED_REFLECTION_JSON_ARRAY_LENGTHS=entryPoints=2|vertexLayouts=1|vertexLayouts.0.attributes=3|workgroupSizes=0"
    "-DEXPECTED_REFLECTION_FEATURE_FIELDS=glsl-lowering.kind=backend|vertex-shader.kind=stage|fragment-shader.kind=stage|local-declaration.kind=operation|vector-constructor.kind=operation|scalar-arithmetic.kind=operation"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
if(CROSSGL_HAS_OPENGL_NATIVE_VALIDATOR)
  add_test(NAME cglc_build_opengl_graphics_reserved_identifiers_glsl_validated
    COMMAND ${CMAKE_COMMAND}
      -DCGLC=$<TARGET_FILE:cglc>
      -DINPUT=${CROSSGL_OPENGL_GRAPHICS_RESERVED_IDENTIFIERS_SHADER}
      -DTARGET=opengl
      -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-opengl-graphics-reserved-identifiers-validated.cglb
      -DMODE=source-package-build
      -DEXPECTED_SOURCE=backend/opengl/OpenGLGraphicsReservedIdentifiersShader.graphics.glsl
      "-DEXPECTED_SOURCE_SNIPPET=${CROSSGL_OPENGL_GRAPHICS_RESERVED_IDENTIFIERS_SOURCE_SNIPPET}"
      "-DEXPECTED_MANIFEST_JSON_FIELDS=schemaVersion=1|target=opengl|module=OpenGLGraphicsReservedIdentifiersShader|artifacts.backendSource=backend/opengl/OpenGLGraphicsReservedIdentifiersShader.graphics.glsl|artifacts.nativeBinary=backend/opengl/OpenGLGraphicsReservedIdentifiersShader.glsl"
      "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=opengl|module=OpenGLGraphicsReservedIdentifiersShader|nativeBinary=backend/opengl/OpenGLGraphicsReservedIdentifiersShader.glsl|entryPoints.0.stage=vertex|entryPoints.0.backendName=vertex_main|entryPoints.1.stage=fragment|entryPoints.1.backendName=fragment_main|vertexLayouts.0.attributes.1.name=sample|vertexLayouts.0.attributes.2.name=smooth"
      "-DEXPECTED_REFLECTION_JSON_ARRAY_LENGTHS=entryPoints=2|vertexLayouts=1|vertexLayouts.0.attributes=3|workgroupSizes=0"
      "-DEXPECTED_REFLECTION_FEATURE_FIELDS=native-glsl-package.kind=backend|glsl-program-validation.kind=validation|vertex-shader.kind=stage|fragment-shader.kind=stage|local-declaration.kind=operation|vector-constructor.kind=operation|scalar-arithmetic.kind=operation"
      -DEXPECTED_NATIVE_BINARY=backend/opengl/OpenGLGraphicsReservedIdentifiersShader.glsl
      -DEXPECTED_NATIVE_BINARY_STATUS=validated
      -DEXPECTED_DIAGNOSTIC=opengl.glsl-validated
      -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
  crossgl_label_optional_native_test(
    cglc_build_opengl_graphics_reserved_identifiers_glsl_validated opengl)
endif()
add_test(NAME cglc_build_directx_resource_array_access_source_package
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_RESOURCE_ARRAY_ACCESS_SHADER}
    -DTARGET=directx
    -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-directx-resource-array-access.cglb
    -DMODE=source-package-build
    -DEXPECTED_SOURCE=backend/directx/ResourceArrayAccessShader.hlsl
    "-DEXPECTED_SOURCE_SNIPPET=shadowMaps[1].SampleLevel(comparisonSamplers[0], float2(0.5, 0.5), 0.0);"
    "-DEXPECTED_MANIFEST_JSON_FIELDS=schemaVersion=1|target=directx|module=ResourceArrayAccessShader|artifacts.backendSource=backend/directx/ResourceArrayAccessShader.hlsl|artifacts.nativeBinary=backend/directx/ResourceArrayAccessShader.dxil"
    "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=directx|module=ResourceArrayAccessShader|nativeBinary=backend/directx/ResourceArrayAccessShader.dxil|functionConstants.0.name=MAP_COUNT|functionConstants.0.value=3|resources.0.name=lights|resources.0.kind=uniform|resources.0.type=Light[2]|resources.1.name=values|resources.1.kind=buffer|resources.1.type=vec4*|resources.2.name=shadowMaps|resources.2.kind=texture|resources.2.type=sampler2D[MAP_COUNT]|resources.3.name=comparisonSamplers|resources.3.kind=sampler|resources.3.type=sampler[2]|workgroupSizes.0.entryPoint=compute_main|workgroupSizes.0.x=1|workgroupSizes.0.y=1|workgroupSizes.0.z=1"
    "-DEXPECTED_REFLECTION_JSON_ARRAY_LENGTHS=resources=4|targetResourceBindings=4|functionConstants=1|workgroupSizes=1"
    "-DEXPECTED_REFLECTION_TARGET_FIELDS=lights.stage=compute|lights.entryPoint=compute_main|lights.sourceType=Light[2]|lights.hlslType=ConstantBuffer<Light>|lights.addressSpace=constant-buffer|lights.abi=registerBinding|lights.bindingClass=constant-buffer|lights.descriptorType=CBV|lights.argumentIndex=0|lights.set=0|lights.binding=0|lights.arraySize=2|lights.arrayElementCount=2|values.sourceType=vec4*|values.hlslType=RWStructuredBuffer<float4>|values.addressSpace=unordered-access|values.abi=registerBinding|values.bindingClass=uav|values.descriptorType=UAV|values.argumentIndex=1|values.set=0|values.binding=1|shadowMaps.sourceType=sampler2D[MAP_COUNT]|shadowMaps.hlslType=Texture2D<float4>|shadowMaps.addressSpace=shader-resource|shadowMaps.abi=registerBinding|shadowMaps.bindingClass=srv|shadowMaps.descriptorType=SRV|shadowMaps.argumentIndex=2|shadowMaps.set=0|shadowMaps.binding=2|shadowMaps.arraySize=MAP_COUNT|shadowMaps.arrayElementCount=3|comparisonSamplers.sourceType=sampler[2]|comparisonSamplers.hlslType=SamplerState|comparisonSamplers.addressSpace=sampler|comparisonSamplers.abi=registerBinding|comparisonSamplers.bindingClass=sampler|comparisonSamplers.descriptorType=Sampler|comparisonSamplers.argumentIndex=5|comparisonSamplers.set=0|comparisonSamplers.binding=5|comparisonSamplers.arraySize=2|comparisonSamplers.arrayElementCount=2"
    "-DEXPECTED_REFLECTION_FEATURE_FIELDS=hlsl-lowering.kind=backend|native-dxil-package.kind=backend|dxc.kind=toolchain|dxil-validator.kind=validation|compute-kernel.kind=stage|workgroup-size.kind=execution|uniform-buffer.kind=resource|fixed-array.kind=layout|descriptor-array.kind=resource|storage-buffer.kind=resource|vector-storage-buffer.kind=layout|sampled-texture.kind=resource|sampler-state.kind=resource|local-declaration.kind=operation|texture-sample.kind=operation|index-access.kind=operation|vector-constructor.kind=operation|storage-buffer-write.kind=operation|vector-arithmetic.kind=operation"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_build_opengl_resource_array_access_source_package
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_RESOURCE_ARRAY_ACCESS_SHADER}
    -DTARGET=opengl
    -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-opengl-resource-array-access.cglb
    -DMODE=source-package-build
    -DEXPECTED_SOURCE=backend/opengl/ResourceArrayAccessShader.comp.glsl
    "-DEXPECTED_SOURCE_SNIPPET=textureLod(sampler2D(shadowMaps[1], comparisonSamplers[0]), vec2(0.5, 0.5), 0.0);"
    "-DEXPECTED_MANIFEST_JSON_FIELDS=schemaVersion=1|target=opengl|module=ResourceArrayAccessShader|artifacts.backendSource=backend/opengl/ResourceArrayAccessShader.comp.glsl|artifacts.nativeBinary=backend/opengl/ResourceArrayAccessShader.glsl|artifacts.nativeBinaryStatus=planned"
    "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=opengl|module=ResourceArrayAccessShader|nativeBinary=backend/opengl/ResourceArrayAccessShader.glsl|functionConstants.0.name=MAP_COUNT|functionConstants.0.value=3|resources.0.name=lights|resources.0.kind=uniform|resources.0.type=Light[2]|resources.1.name=values|resources.1.kind=buffer|resources.1.type=vec4*|resources.2.name=shadowMaps|resources.2.kind=texture|resources.2.type=sampler2D[MAP_COUNT]|resources.3.name=comparisonSamplers|resources.3.kind=sampler|resources.3.type=sampler[2]|workgroupSizes.0.entryPoint=compute_main"
    "-DEXPECTED_REFLECTION_JSON_ARRAY_LENGTHS=resources=4|targetResourceBindings=4|functionConstants=1|workgroupSizes=1"
    "-DEXPECTED_REFLECTION_TARGET_FIELDS=lights.bindingClass=uniform-buffer|lights.arraySize=2|lights.arrayElementCount=2|values.bindingClass=storage-buffer|shadowMaps.bindingClass=texture|shadowMaps.arraySize=MAP_COUNT|shadowMaps.arrayElementCount=3|comparisonSamplers.bindingClass=sampler|comparisonSamplers.arraySize=2|comparisonSamplers.arrayElementCount=2"
    "-DEXPECTED_REFLECTION_FEATURE_FIELDS=glsl-lowering.kind=backend|native-glsl-package.kind=backend|compute-kernel.kind=stage|workgroup-size.kind=execution|uniform-buffer.kind=resource|fixed-array.kind=layout|descriptor-array.kind=resource|storage-buffer.kind=resource|vector-storage-buffer.kind=layout|sampled-texture.kind=resource|sampler-state.kind=resource|local-declaration.kind=operation|texture-sample.kind=operation|index-access.kind=operation|vector-constructor.kind=operation|storage-buffer-write.kind=operation|vector-arithmetic.kind=operation"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_build_directx_texture_compare_source_package
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_TEXTURE_COMPARE_SHADOW_SHADER}
    -DTARGET=directx
    -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-directx-texture-compare.cglb
    -DMODE=source-package-build
    -DEXPECTED_SOURCE=backend/directx/TextureCompareShadowShader.hlsl
    "-DEXPECTED_SOURCE_SNIPPET=SampleCmpLevelZero(shadowSampler"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_build_opengl_texture_compare_source_package
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_TEXTURE_COMPARE_SHADOW_SHADER}
    -DTARGET=opengl
    -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-opengl-texture-compare.cglb
    -DMODE=source-package-build
    -DEXPECTED_SOURCE=backend/opengl/TextureCompareShadowShader.comp.glsl
    "-DEXPECTED_SOURCE_SNIPPET=sampler2DShadow(shadowMap, shadowSampler)"
    "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=opengl|module=TextureCompareShadowShader"
    "-DEXPECTED_REFLECTION_TARGET_FIELDS=shadowMap.sourceType=sampler2DShadow|shadowMap.bindingClass=texture|cubeShadow.sourceType=samplerCubeShadow|cubeShadow.bindingClass=texture|shadowSampler.bindingClass=sampler|values.storageBufferLayout.layout=std430"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_build_directx_comparison_sampler_role_source_package
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_COMPARISON_SAMPLER_ROLE_SHADER}
    -DTARGET=directx
    -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-directx-comparison-sampler-role.cglb
    -DMODE=source-package-build
    -DEXPECTED_SOURCE=backend/directx/ComparisonSamplerRoleShader.hlsl
    "-DEXPECTED_SOURCE_SNIPPET=SamplerComparisonState shadowCompareSamplers[2] : register(s4, space0);"
    "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=directx|module=ComparisonSamplerRoleShader"
    "-DEXPECTED_REFLECTION_TARGET_FIELDS=shadowCompareSamplers.sourceType=comparison_sampler[2]|shadowCompareSamplers.hlslType=SamplerComparisonState|shadowCompareSamplers.bindingClass=sampler|shadowCompareSamplers.descriptorType=Sampler|shadowCompareSamplers.arraySize=2|shadowCompareSamplers.arrayElementCount=2"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_build_opengl_comparison_sampler_role_source_package
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_COMPARISON_SAMPLER_ROLE_SHADER}
    -DTARGET=opengl
    -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-opengl-comparison-sampler-role.cglb
    -DMODE=source-package-build
    -DEXPECTED_SOURCE=backend/opengl/ComparisonSamplerRoleShader.comp.glsl
    "-DEXPECTED_SOURCE_SNIPPET=sampler2DShadow(shadowMap, shadowCompareSamplers[0])"
    "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=opengl|module=ComparisonSamplerRoleShader"
    "-DEXPECTED_REFLECTION_TARGET_FIELDS=shadowCompareSamplers.sourceType=comparison_sampler[2]|shadowCompareSamplers.bindingClass=sampler|shadowCompareSamplers.abi=programResourceBinding|shadowCompareSamplers.arraySize=2|shadowCompareSamplers.arrayElementCount=2|values.storageBufferLayout.layout=std430"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_build_directx_texture_only_compare_descriptor_array_source_package
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_TEXTURE_ONLY_COMPARE_DESCRIPTOR_ARRAY_SHADER}
    -DTARGET=directx
    -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-directx-texture-only-compare-descriptor-array.cglb
    -DMODE=source-package-build
    -DEXPECTED_SOURCE=backend/directx/TextureOnlyCompareDescriptorArrayShader.hlsl
    "-DEXPECTED_SOURCE_SNIPPET=shadowMaps[1].SampleCmpLevelZero(shadowSampler"
    "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=directx|module=TextureOnlyCompareDescriptorArrayShader"
    "-DEXPECTED_REFLECTION_TARGET_FIELDS=shadowMaps.hlslType=Texture2D<float>|shadowMaps.bindingClass=srv|shadowMaps.descriptorType=SRV|shadowMaps.arraySize=SHADOW_COUNT|shadowMaps.arrayElementCount=2|shadowSampler.hlslType=SamplerComparisonState|shadowSampler.bindingClass=sampler|shadowSampler.descriptorType=Sampler"
    "-DEXPECTED_REFLECTION_FEATURE_FIELDS=sampled-texture.kind=resource|fixed-array.kind=layout|descriptor-array.kind=resource|depth-compare-format.kind=texture|sampler-state.kind=resource|texture-shadow-compare.kind=operation|index-access.kind=operation|storage-buffer-write.kind=operation"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_build_opengl_texture_only_compare_descriptor_array_source_package
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_TEXTURE_ONLY_COMPARE_DESCRIPTOR_ARRAY_SHADER}
    -DTARGET=opengl
    -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-opengl-texture-only-compare-descriptor-array.cglb
    -DMODE=source-package-build
    -DEXPECTED_SOURCE=backend/opengl/TextureOnlyCompareDescriptorArrayShader.comp.glsl
    "-DEXPECTED_SOURCE_SNIPPET=sampler2DShadow(shadowMaps[1], shadowSampler)"
    "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=opengl|module=TextureOnlyCompareDescriptorArrayShader"
    "-DEXPECTED_REFLECTION_TARGET_FIELDS=shadowMaps.sourceType=sampler2DShadow[SHADOW_COUNT]|shadowMaps.bindingClass=texture|shadowMaps.arraySize=SHADOW_COUNT|shadowMaps.arrayElementCount=2|shadowSampler.bindingClass=sampler|values.storageBufferLayout.layout=std430"
    "-DEXPECTED_REFLECTION_FEATURE_FIELDS=sampled-texture.kind=resource|fixed-array.kind=layout|descriptor-array.kind=resource|depth-compare-format.kind=texture|sampler-state.kind=resource|texture-shadow-compare.kind=operation|index-access.kind=operation|storage-buffer-write.kind=operation"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_build_directx_sampler_only_compare_descriptor_array_source_package
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_SAMPLER_ONLY_COMPARE_DESCRIPTOR_ARRAY_SHADER}
    -DTARGET=directx
    -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-directx-sampler-only-compare-descriptor-array.cglb
    -DMODE=source-package-build
    -DEXPECTED_SOURCE=backend/directx/SamplerOnlyCompareDescriptorArrayShader.hlsl
    "-DEXPECTED_SOURCE_SNIPPET=shadowMap.SampleCmpLevelZero(shadowSamplers[1]"
    "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=directx|module=SamplerOnlyCompareDescriptorArrayShader"
    "-DEXPECTED_REFLECTION_TARGET_FIELDS=shadowMap.hlslType=Texture2D<float>|shadowMap.bindingClass=srv|shadowSamplers.hlslType=SamplerComparisonState|shadowSamplers.bindingClass=sampler|shadowSamplers.descriptorType=Sampler|shadowSamplers.arraySize=SAMPLER_COUNT|shadowSamplers.arrayElementCount=2"
    "-DEXPECTED_REFLECTION_FEATURE_FIELDS=sampled-texture.kind=resource|fixed-array.kind=layout|descriptor-array.kind=resource|depth-compare-format.kind=texture|sampler-state.kind=resource|texture-shadow-compare.kind=operation|index-access.kind=operation|storage-buffer-write.kind=operation"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_build_opengl_sampler_only_compare_descriptor_array_source_package
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_SAMPLER_ONLY_COMPARE_DESCRIPTOR_ARRAY_SHADER}
    -DTARGET=opengl
    -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-opengl-sampler-only-compare-descriptor-array.cglb
    -DMODE=source-package-build
    -DEXPECTED_SOURCE=backend/opengl/SamplerOnlyCompareDescriptorArrayShader.comp.glsl
    "-DEXPECTED_SOURCE_SNIPPET=sampler2DShadow(shadowMap, shadowSamplers[1])"
    "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=opengl|module=SamplerOnlyCompareDescriptorArrayShader"
    "-DEXPECTED_REFLECTION_TARGET_FIELDS=shadowMap.bindingClass=texture|shadowSamplers.sourceType=sampler[SAMPLER_COUNT]|shadowSamplers.bindingClass=sampler|shadowSamplers.arraySize=SAMPLER_COUNT|shadowSamplers.arrayElementCount=2|values.storageBufferLayout.layout=std430"
    "-DEXPECTED_REFLECTION_FEATURE_FIELDS=sampled-texture.kind=resource|fixed-array.kind=layout|descriptor-array.kind=resource|depth-compare-format.kind=texture|sampler-state.kind=resource|texture-shadow-compare.kind=operation|index-access.kind=operation|storage-buffer-write.kind=operation"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_build_directx_texture_compare_descriptor_array_source_package
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_TEXTURE_COMPARE_DESCRIPTOR_ARRAY_SHADER}
    -DTARGET=directx
    -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-directx-texture-compare-descriptor-array.cglb
    -DMODE=source-package-build
    -DEXPECTED_SOURCE=backend/directx/TextureCompareDescriptorArrayShader.hlsl
    "-DEXPECTED_SOURCE_SNIPPET=shadowMaps[1].SampleCmpLevelZero(shadowSamplers[0]"
    "-DEXPECTED_MANIFEST_JSON_FIELDS=schemaVersion=1|target=directx|module=TextureCompareDescriptorArrayShader|artifacts.backendSource=backend/directx/TextureCompareDescriptorArrayShader.hlsl|artifacts.nativeBinary=backend/directx/TextureCompareDescriptorArrayShader.dxil"
    "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=directx|module=TextureCompareDescriptorArrayShader|nativeBinary=backend/directx/TextureCompareDescriptorArrayShader.dxil|manualTextureCompareKernelSummary.totalCount=0"
    "-DEXPECTED_REFLECTION_JSON_ARRAY_LENGTHS=resources=3|targetResourceBindings=3|manualTextureCompareKernels=0|workgroupSizes=1"
    "-DEXPECTED_REFLECTION_TARGET_FIELDS=values.hlslType=RWStructuredBuffer<float>|values.bindingClass=uav|values.descriptorType=UAV|shadowMaps.sourceType=sampler2DShadow[SHADOW_COUNT]|shadowMaps.hlslType=Texture2D<float>|shadowMaps.addressSpace=shader-resource|shadowMaps.abi=registerBinding|shadowMaps.bindingClass=srv|shadowMaps.descriptorType=SRV|shadowMaps.argumentIndex=2|shadowMaps.arraySize=SHADOW_COUNT|shadowMaps.arrayElementCount=2|shadowSamplers.sourceType=sampler[2]|shadowSamplers.hlslType=SamplerComparisonState|shadowSamplers.addressSpace=sampler|shadowSamplers.abi=registerBinding|shadowSamplers.bindingClass=sampler|shadowSamplers.descriptorType=Sampler|shadowSamplers.argumentIndex=5|shadowSamplers.arraySize=2|shadowSamplers.arrayElementCount=2"
    "-DEXPECTED_REFLECTION_FEATURE_FIELDS=hlsl-lowering.kind=backend|compute-kernel.kind=stage|workgroup-size.kind=execution|storage-buffer.kind=resource|sampled-texture.kind=resource|fixed-array.kind=layout|descriptor-array.kind=resource|depth-compare-format.kind=texture|sampler-state.kind=resource|texture-shadow-compare.kind=operation|index-access.kind=operation|storage-buffer-write.kind=operation"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_build_opengl_texture_compare_descriptor_array_source_package
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_TEXTURE_COMPARE_DESCRIPTOR_ARRAY_SHADER}
    -DTARGET=opengl
    -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-opengl-texture-compare-descriptor-array.cglb
    -DMODE=source-package-build
    -DEXPECTED_SOURCE=backend/opengl/TextureCompareDescriptorArrayShader.comp.glsl
    "-DEXPECTED_SOURCE_SNIPPET=texture(sampler2DShadow(shadowMaps[1], shadowSamplers[0]), vec3(vec2(0.5, 0.5), 0.25))"
    "-DEXPECTED_MANIFEST_JSON_FIELDS=schemaVersion=1|target=opengl|module=TextureCompareDescriptorArrayShader|artifacts.nativeBinaryStatus=planned"
    "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=opengl|module=TextureCompareDescriptorArrayShader|manualTextureCompareKernelSummary.totalCount=0"
    "-DEXPECTED_REFLECTION_JSON_ARRAY_LENGTHS=resources=3|targetResourceBindings=3|manualTextureCompareKernels=0"
    "-DEXPECTED_REFLECTION_TARGET_FIELDS=shadowMaps.sourceType=sampler2DShadow[SHADOW_COUNT]|shadowMaps.bindingClass=texture|shadowMaps.argumentIndex=2|shadowMaps.arraySize=SHADOW_COUNT|shadowMaps.arrayElementCount=2|shadowMaps.arrayDimensions.0.elementCount=2|shadowSamplers.sourceType=sampler[2]|shadowSamplers.bindingClass=sampler|shadowSamplers.argumentIndex=5|shadowSamplers.arraySize=2|shadowSamplers.arrayElementCount=2|values.storageBufferLayout.layout=std430"
    "-DEXPECTED_REFLECTION_FEATURE_FIELDS=sampled-texture.kind=resource|descriptor-array.kind=resource|depth-compare-format.kind=texture|sampler-state.kind=resource|texture-shadow-compare.kind=operation|index-access.kind=operation|storage-buffer-write.kind=operation"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_build_directx_texture_array_compare_descriptor_array_source_package
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_TEXTURE_ARRAY_COMPARE_DESCRIPTOR_ARRAY_SHADER}
    -DTARGET=directx
    -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-directx-texture-array-compare-descriptor-array.cglb
    -DMODE=source-package-build
    -DEXPECTED_SOURCE=backend/directx/TextureArrayCompareDescriptorArrayShader.hlsl
    "-DEXPECTED_SOURCE_SNIPPET=shadowAtlases[1].SampleCmpLevelZero(shadowSamplers[0]"
    "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=directx|module=TextureArrayCompareDescriptorArrayShader"
    "-DEXPECTED_REFLECTION_TARGET_FIELDS=shadowAtlases.hlslType=Texture2DArray<float>|shadowAtlases.bindingClass=srv|shadowAtlases.arraySize=SHADOW_COUNT|shadowAtlases.arrayElementCount=2|shadowSamplers.hlslType=SamplerComparisonState|shadowSamplers.bindingClass=sampler|shadowSamplers.arraySize=2|shadowSamplers.arrayElementCount=2"
    "-DEXPECTED_REFLECTION_FEATURE_FIELDS=sampled-texture.kind=resource|fixed-array.kind=layout|descriptor-array.kind=resource|array-dimension.kind=texture|depth-compare-format.kind=texture|sampler-state.kind=resource|texture-shadow-compare.kind=operation|index-access.kind=operation|storage-buffer-write.kind=operation"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_build_opengl_texture_array_compare_descriptor_array_source_package
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_TEXTURE_ARRAY_COMPARE_DESCRIPTOR_ARRAY_SHADER}
    -DTARGET=opengl
    -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-opengl-texture-array-compare-descriptor-array.cglb
    -DMODE=source-package-build
    -DEXPECTED_SOURCE=backend/opengl/TextureArrayCompareDescriptorArrayShader.comp.glsl
    "-DEXPECTED_SOURCE_SNIPPET=sampler2DArrayShadow(shadowAtlases[1], shadowSamplers[0])"
    "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=opengl|module=TextureArrayCompareDescriptorArrayShader"
    "-DEXPECTED_REFLECTION_TARGET_FIELDS=shadowAtlases.sourceType=sampler2DArrayShadow[SHADOW_COUNT]|shadowAtlases.bindingClass=texture|shadowAtlases.arraySize=SHADOW_COUNT|shadowAtlases.arrayElementCount=2|shadowSamplers.bindingClass=sampler|shadowSamplers.arraySize=2|shadowSamplers.arrayElementCount=2|values.storageBufferLayout.layout=std430"
    "-DEXPECTED_REFLECTION_FEATURE_FIELDS=sampled-texture.kind=resource|fixed-array.kind=layout|descriptor-array.kind=resource|array-dimension.kind=texture|depth-compare-format.kind=texture|sampler-state.kind=resource|texture-shadow-compare.kind=operation|index-access.kind=operation|storage-buffer-write.kind=operation"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_build_directx_texture_cube_compare_descriptor_array_source_package
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_TEXTURE_CUBE_COMPARE_DESCRIPTOR_ARRAY_SHADER}
    -DTARGET=directx
    -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-directx-texture-cube-compare-descriptor-array.cglb
    -DMODE=source-package-build
    -DEXPECTED_SOURCE=backend/directx/TextureCubeCompareDescriptorArrayShader.hlsl
    "-DEXPECTED_SOURCE_SNIPPET=shadowCubeArrays[1].SampleCmpLevelZero(shadowSamplers[0]"
    "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=directx|module=TextureCubeCompareDescriptorArrayShader"
    "-DEXPECTED_REFLECTION_TARGET_FIELDS=shadowCubes.hlslType=TextureCube<float>|shadowCubes.bindingClass=srv|shadowCubes.arraySize=SHADOW_COUNT|shadowCubes.arrayElementCount=2|shadowCubeArrays.hlslType=TextureCubeArray<float>|shadowCubeArrays.bindingClass=srv|shadowCubeArrays.arraySize=SHADOW_COUNT|shadowCubeArrays.arrayElementCount=2|shadowSamplers.hlslType=SamplerComparisonState|shadowSamplers.bindingClass=sampler|shadowSamplers.arraySize=2|shadowSamplers.arrayElementCount=2"
    "-DEXPECTED_REFLECTION_FEATURE_FIELDS=sampled-texture.kind=resource|fixed-array.kind=layout|descriptor-array.kind=resource|cube-dimension.kind=texture|array-dimension.kind=texture|depth-compare-format.kind=texture|sampler-state.kind=resource|texture-shadow-compare.kind=operation|index-access.kind=operation|scalar-arithmetic.kind=operation|storage-buffer-write.kind=operation"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_build_opengl_texture_cube_compare_descriptor_array_source_package
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_TEXTURE_CUBE_COMPARE_DESCRIPTOR_ARRAY_SHADER}
    -DTARGET=opengl
    -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-opengl-texture-cube-compare-descriptor-array.cglb
    -DMODE=source-package-build
    -DEXPECTED_SOURCE=backend/opengl/TextureCubeCompareDescriptorArrayShader.comp.glsl
    "-DEXPECTED_SOURCE_SNIPPET=samplerCubeArrayShadow(shadowCubeArrays[1], shadowSamplers[0])"
    "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=opengl|module=TextureCubeCompareDescriptorArrayShader"
    "-DEXPECTED_REFLECTION_TARGET_FIELDS=shadowCubes.sourceType=samplerCubeShadow[SHADOW_COUNT]|shadowCubes.bindingClass=texture|shadowCubes.arraySize=SHADOW_COUNT|shadowCubes.arrayElementCount=2|shadowCubeArrays.sourceType=samplerCubeArrayShadow[SHADOW_COUNT]|shadowCubeArrays.bindingClass=texture|shadowCubeArrays.arraySize=SHADOW_COUNT|shadowCubeArrays.arrayElementCount=2|shadowSamplers.bindingClass=sampler|shadowSamplers.arraySize=2|shadowSamplers.arrayElementCount=2|values.storageBufferLayout.layout=std430"
    "-DEXPECTED_REFLECTION_FEATURE_FIELDS=sampled-texture.kind=resource|fixed-array.kind=layout|descriptor-array.kind=resource|cube-dimension.kind=texture|array-dimension.kind=texture|depth-compare-format.kind=texture|sampler-state.kind=resource|texture-shadow-compare.kind=operation|index-access.kind=operation|scalar-arithmetic.kind=operation|storage-buffer-write.kind=operation"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_build_directx_storage_buffer_array_source_package
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_STORAGE_BUFFER_ARRAY_ACCESS_SHADER}
    -DTARGET=directx
    -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-directx-storage-buffer-array.cglb
    -DMODE=source-package-build
    -DEXPECTED_SOURCE=backend/directx/StorageBufferArrayAccessShader.hlsl
    "-DEXPECTED_SOURCE_SNIPPET=RWStructuredBuffer<float> values[2] : register(u0, space0);"
    "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=directx|module=StorageBufferArrayAccessShader"
    "-DEXPECTED_REFLECTION_TARGET_FIELDS=values.sourceType=float*[2]|values.hlslType=RWStructuredBuffer<float>|values.bindingClass=uav|values.descriptorType=UAV|values.arraySize=2|values.arrayElementCount=2"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_build_directx_uniform_buffer_descriptor_array_source_package
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CMAKE_CURRENT_SOURCE_DIR}/tests/directx/fixtures/DirectXUniformBufferDescriptorArrayShader.cgl
    -DTARGET=directx
    -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-directx-uniform-buffer-descriptor-array.cglb
    -DMODE=source-package-build
    -DEXPECTED_SOURCE=backend/directx/DirectXUniformBufferDescriptorArrayShader.hlsl
    "-DEXPECTED_SOURCE_SNIPPET=ConstantBuffer<Light> lights[LIGHT_COUNT] : register(b0, space0);"
    "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=directx|module=DirectXUniformBufferDescriptorArrayShader|nativeBinary=backend/directx/DirectXUniformBufferDescriptorArrayShader.dxil|resources.0.name=lights|resources.0.kind=uniform|resources.0.type=Light[LIGHT_COUNT]|resources.0.arrayDimensions.0.kind=fixed|resources.0.arrayDimensions.0.elementCount=2"
    "-DEXPECTED_REFLECTION_JSON_ARRAY_LENGTHS=resources=2|targetResourceBindings=2|functionConstants=1|workgroupSizes=1"
    "-DEXPECTED_REFLECTION_TARGET_FIELDS=lights.stage=compute|lights.entryPoint=compute_main|lights.sourceType=Light[LIGHT_COUNT]|lights.hlslType=ConstantBuffer<Light>|lights.addressSpace=constant-buffer|lights.abi=registerBinding|lights.bindingClass=constant-buffer|lights.descriptorType=CBV|lights.argumentIndex=0|lights.set=0|lights.binding=0|lights.arraySize=LIGHT_COUNT|lights.arrayElementCount=2|values.hlslType=RWStructuredBuffer<float4>|values.bindingClass=uav"
    "-DEXPECTED_REFLECTION_FEATURE_FIELDS=hlsl-lowering.kind=backend|native-dxil-package.kind=backend|dxc.kind=toolchain|dxil-validator.kind=validation|compute-kernel.kind=stage|workgroup-size.kind=execution|uniform-buffer.kind=resource|descriptor-array.kind=resource|fixed-array.kind=layout|nonuniform-descriptor-index.kind=operation|nonuniform-uniform-buffer-descriptor-index.kind=operation|NonUniformResourceIndex.kind=intrinsic|storage-buffer.kind=resource|storage-buffer-write.kind=operation"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_build_opengl_uniform_buffer_descriptor_array_source_package
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_OPENGL_UNIFORM_BUFFER_DESCRIPTOR_ARRAY_SHADER}
    -DTARGET=opengl
    -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-opengl-uniform-buffer-descriptor-array.cglb
    -DMODE=source-package-build
    -DEXPECTED_SOURCE=backend/opengl/OpenGLUniformBufferDescriptorArrayShader.comp.glsl
    "-DEXPECTED_SOURCE_SNIPPET=} lights[LIGHT_COUNT];"
    "-DEXPECTED_MANIFEST_JSON_FIELDS=schemaVersion=1|target=opengl|module=OpenGLUniformBufferDescriptorArrayShader|artifacts.backendSource=backend/opengl/OpenGLUniformBufferDescriptorArrayShader.comp.glsl|artifacts.nativeBinary=backend/opengl/OpenGLUniformBufferDescriptorArrayShader.glsl"
    "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=opengl|module=OpenGLUniformBufferDescriptorArrayShader|nativeBinary=backend/opengl/OpenGLUniformBufferDescriptorArrayShader.glsl|resources.0.name=lights|resources.0.kind=uniform|resources.0.type=Light[LIGHT_COUNT]|resources.0.arrayDimensions.0.kind=fixed|resources.0.arrayDimensions.0.elementCount=2"
    "-DEXPECTED_REFLECTION_JSON_ARRAY_LENGTHS=resources=2|targetResourceBindings=2|functionConstants=1|workgroupSizes=1"
    "-DEXPECTED_REFLECTION_TARGET_FIELDS=lights.stage=compute|lights.entryPoint=compute_main|lights.sourceType=Light[LIGHT_COUNT]|lights.addressSpace=uniform|lights.abi=programResourceBinding|lights.bindingClass=uniform-buffer|lights.argumentIndex=0|lights.set=0|lights.binding=0|lights.arraySize=LIGHT_COUNT|lights.arrayElementCount=2|values.bindingClass=storage-buffer|values.storageBufferLayout.layout=std430"
    "-DEXPECTED_REFLECTION_FEATURE_FIELDS=glsl-lowering.kind=backend|native-glsl-package.kind=backend|compute-kernel.kind=stage|workgroup-size.kind=execution|uniform-buffer.kind=resource|descriptor-array.kind=resource|fixed-array.kind=layout|storage-buffer.kind=resource|vector-storage-buffer.kind=layout|local-declaration.kind=operation|vector-arithmetic.kind=operation|index-access.kind=operation|storage-buffer-write.kind=operation"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
if(CROSSGL_HAS_OPENGL_NATIVE_VALIDATOR)
  add_test(NAME cglc_build_opengl_uniform_buffer_descriptor_array_glsl_validated
    COMMAND ${CMAKE_COMMAND}
      -DCGLC=$<TARGET_FILE:cglc>
      -DINPUT=${CROSSGL_OPENGL_UNIFORM_BUFFER_DESCRIPTOR_ARRAY_SHADER}
      -DTARGET=opengl
      -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-opengl-uniform-buffer-descriptor-array-validated.cglb
      -DMODE=source-package-build
      -DEXPECTED_SOURCE=backend/opengl/OpenGLUniformBufferDescriptorArrayShader.comp.glsl
      "-DEXPECTED_SOURCE_SNIPPET=} lights[LIGHT_COUNT];"
      "-DEXPECTED_MANIFEST_JSON_FIELDS=schemaVersion=1|target=opengl|module=OpenGLUniformBufferDescriptorArrayShader|artifacts.backendSource=backend/opengl/OpenGLUniformBufferDescriptorArrayShader.comp.glsl|artifacts.nativeBinary=backend/opengl/OpenGLUniformBufferDescriptorArrayShader.glsl|artifacts.nativeBinaryStatus=validated"
      "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=opengl|module=OpenGLUniformBufferDescriptorArrayShader|nativeBinary=backend/opengl/OpenGLUniformBufferDescriptorArrayShader.glsl|resources.0.name=lights|resources.0.kind=uniform|resources.0.type=Light[LIGHT_COUNT]"
      "-DEXPECTED_REFLECTION_TARGET_FIELDS=lights.bindingClass=uniform-buffer|lights.arraySize=LIGHT_COUNT|lights.arrayElementCount=2|values.bindingClass=storage-buffer"
      -DEXPECTED_NATIVE_BINARY=backend/opengl/OpenGLUniformBufferDescriptorArrayShader.glsl
      -DEXPECTED_NATIVE_BINARY_STATUS=validated
      -DEXPECTED_DIAGNOSTIC=opengl.glsl-validated
      -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
  crossgl_label_optional_native_test(
    cglc_build_opengl_uniform_buffer_descriptor_array_glsl_validated opengl)
endif()
add_test(NAME cglc_build_directx_uniform_buffer_descriptor_array_fake_dxc_success
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CMAKE_CURRENT_SOURCE_DIR}/tests/directx/fixtures/DirectXUniformBufferDescriptorArrayShader.cgl
    -DTARGET=directx
    -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-directx-uniform-buffer-descriptor-array-fake-dxc.cglb
    -DMODE=source-package-build
    -DTOOLCHAIN_PATH=${CROSSGL_FAKE_DXC_SUCCESS_DIR}
    -DTOOLCHAIN_DISABLE_FALLBACK=ON
    -DEXPECTED_SOURCE=backend/directx/DirectXUniformBufferDescriptorArrayShader.hlsl
    -DEXPECTED_NATIVE_BINARY=backend/directx/DirectXUniformBufferDescriptorArrayShader.dxil
    -DEXPECTED_NATIVE_BINARY_STATUS=emitted
    "-DEXPECTED_SOURCE_SNIPPET=lights[NonUniformResourceIndex(slot)].color"
    "-DEXPECTED_DIAGNOSTICS_JSON_FIELDS=diagnostics.0.severity=note|diagnostics.0.code=directx.source-package-emitted|diagnostics.1.severity=note|diagnostics.1.code=directx.dxil-emitted"
    "-DEXPECTED_DIAGNOSTICS_JSON_FIELD_CONTAINS=diagnostics.0.message=compute=cs_6_0|diagnostics.1.message=compute=cs_6_0"
    "-DEXPECTED_DIAGNOSTICS_JSON_ARRAY_LENGTHS=diagnostics=2"
    -DEXPECTED_TOOL_LOG=${CROSSGL_FAKE_DXC_SUCCESS_DIR}/dxc.log
    "-DEXPECTED_TOOL_LOG_CONTAINS=-T cs_6_0 -E compute_main -Fo"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_build_opengl_storage_buffer_array_source_package
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_STORAGE_BUFFER_ARRAY_ACCESS_SHADER}
    -DTARGET=opengl
    -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-opengl-storage-buffer-array.cglb
    -DMODE=source-package-build
    -DEXPECTED_SOURCE=backend/opengl/StorageBufferArrayAccessShader.comp.glsl
    "-DEXPECTED_SOURCE_SNIPPET=values_Buffers[0].values[1] = first + 1.0;"
    "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=opengl|module=StorageBufferArrayAccessShader"
    "-DEXPECTED_REFLECTION_TARGET_FIELDS=values.sourceType=float*[2]|values.bindingClass=storage-buffer|values.abi=programResourceBinding|values.arraySize=2|values.arrayElementCount=2|values.storageBufferLayout.elementType=float|values.storageBufferLayout.layout=std430|values.storageBufferLayout.arrayStrideBytes=4"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_build_directx_struct_storage_buffer_array_source_package
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_STORAGE_BUFFER_STRUCT_ARRAY_ACCESS_SHADER}
    -DTARGET=directx
    -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-directx-struct-storage-buffer-array.cglb
    -DMODE=source-package-build
    -DEXPECTED_SOURCE=backend/directx/StorageBufferStructArrayAccessShader.hlsl
    "-DEXPECTED_SOURCE_SNIPPET=float mass = particles[1][0].mass;"
    "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=directx|module=StorageBufferStructArrayAccessShader|nativeBinary=backend/directx/StorageBufferStructArrayAccessShader.dxil|resources.0.name=particles|resources.0.kind=buffer|resources.0.type=Particle*[2]|resources.0.arrayDimensions.0.elementCount=2|structs.0.name=Particle|structs.0.fields.0.name=position|structs.0.fields.0.type=vec3|structs.0.fields.1.name=mass|structs.0.fields.1.type=float|workgroupSizes.0.entryPoint=compute_main|workgroupSizes.0.x=1|workgroupSizes.0.y=1|workgroupSizes.0.z=1"
    "-DEXPECTED_REFLECTION_JSON_ARRAY_LENGTHS=resources=1|targetResourceBindings=1|workgroupSizes=1"
    "-DEXPECTED_REFLECTION_TARGET_FIELDS=particles.stage=compute|particles.entryPoint=compute_main|particles.sourceType=Particle*[2]|particles.hlslType=RWStructuredBuffer<Particle>|particles.addressSpace=unordered-access|particles.abi=registerBinding|particles.bindingClass=uav|particles.descriptorType=UAV|particles.argumentIndex=0|particles.set=0|particles.binding=0|particles.arraySize=2|particles.arrayElementCount=2"
    "-DEXPECTED_REFLECTION_FEATURE_FIELDS=hlsl-lowering.kind=backend|native-dxil-package.kind=backend|dxc.kind=toolchain|dxil-validator.kind=validation|compute-kernel.kind=stage|workgroup-size.kind=execution|storage-buffer.kind=resource|fixed-array.kind=layout|descriptor-array.kind=resource|local-declaration.kind=operation|storage-buffer-read.kind=operation|index-access.kind=operation|storage-buffer-write.kind=operation|scalar-arithmetic.kind=operation"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_build_directx_struct_array_field_descriptor_array_source_package
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_STORAGE_BUFFER_STRUCT_ARRAY_FIELD_DESCRIPTOR_ARRAY_SHADER}
    -DTARGET=directx
    -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-directx-struct-array-field-descriptor-array.cglb
    -DMODE=source-package-build
    -DEXPECTED_SOURCE=backend/directx/StorageBufferStructArrayFieldDescriptorArrayShader.hlsl
    "-DEXPECTED_SOURCE_SNIPPET=RWStructuredBuffer<Particle> particles[2] : register(u0, space0);"
    "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=directx|module=StorageBufferStructArrayFieldDescriptorArrayShader|nativeBinary=backend/directx/StorageBufferStructArrayFieldDescriptorArrayShader.dxil|resources.0.name=particles|resources.0.kind=buffer|resources.0.type=Particle*[2]|resources.0.arrayDimensions.0.elementCount=2|structs.0.name=Transform|structs.1.name=Particle|structs.1.fields.0.name=weights|structs.1.fields.0.type=float[4]|structs.1.fields.0.arrayDimensions.0.elementCount=4|structs.1.fields.1.name=history|structs.1.fields.1.type=Transform[2]|structs.1.fields.1.arrayDimensions.0.elementCount=2|workgroupSizes.0.entryPoint=compute_main|workgroupSizes.0.x=1|workgroupSizes.0.y=1|workgroupSizes.0.z=1"
    "-DEXPECTED_REFLECTION_JSON_ARRAY_LENGTHS=resources=1|targetResourceBindings=1|workgroupSizes=1"
    "-DEXPECTED_REFLECTION_TARGET_FIELDS=particles.stage=compute|particles.entryPoint=compute_main|particles.sourceType=Particle*[2]|particles.hlslType=RWStructuredBuffer<Particle>|particles.addressSpace=unordered-access|particles.abi=registerBinding|particles.bindingClass=uav|particles.descriptorType=UAV|particles.argumentIndex=0|particles.set=0|particles.binding=0|particles.arraySize=2|particles.arrayElementCount=2"
    "-DEXPECTED_REFLECTION_FEATURE_FIELDS=hlsl-lowering.kind=backend|native-dxil-package.kind=backend|dxc.kind=toolchain|dxil-validator.kind=validation|fixed-array.kind=layout|fixed-array-field.kind=layout|scalar-vector-elements.kind=array|compute-kernel.kind=stage|workgroup-size.kind=execution|storage-buffer.kind=resource|descriptor-array.kind=resource|local-declaration.kind=operation|storage-buffer-read.kind=operation|index-access.kind=operation|storage-buffer-write.kind=operation|scalar-arithmetic.kind=operation"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_build_opengl_struct_storage_buffer_array_source_package
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_STORAGE_BUFFER_STRUCT_ARRAY_ACCESS_SHADER}
    -DTARGET=opengl
    -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-opengl-struct-storage-buffer-array.cglb
    -DMODE=source-package-build
    -DEXPECTED_SOURCE=backend/opengl/StorageBufferStructArrayAccessShader.comp.glsl
    "-DEXPECTED_SOURCE_SNIPPET=particles_Buffers[0].particles[1].mass = mass + 1.0;"
    "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=opengl|module=StorageBufferStructArrayAccessShader"
    "-DEXPECTED_REFLECTION_TARGET_FIELDS=particles.sourceType=Particle*[2]|particles.bindingClass=storage-buffer|particles.arraySize=2|particles.arrayElementCount=2|particles.storageBufferLayout.elementType=Particle|particles.storageBufferLayout.layout=std430|particles.storageBufferLayout.arrayStrideBytes=16"
    "-DEXPECTED_REFLECTION_FEATURE_FIELDS=${CROSSGL_OPENGL_STRUCT_STORAGE_DESCRIPTOR_ARRAY_FEATURE_FIELDS}|scalar-arithmetic.kind=operation"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_build_directx_mixed_resource_descriptor_array_source_package
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_MIXED_RESOURCE_DESCRIPTOR_ARRAY_SHADER}
    -DTARGET=directx
    -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-directx-mixed-resource-descriptor-array.cglb
    -DMODE=source-package-build
    -DEXPECTED_SOURCE=backend/directx/MixedResourceDescriptorArrayShader.hlsl
    "-DEXPECTED_SOURCE_SNIPPET=Texture2D<float4> colorMaps[2] : register(t2, space0);"
    "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=directx|module=MixedResourceDescriptorArrayShader"
    "-DEXPECTED_REFLECTION_TARGET_FIELDS=particles.hlslType=RWStructuredBuffer<Particle>|particles.bindingClass=uav|particles.arraySize=2|particles.arrayElementCount=2|colorMaps.hlslType=Texture2D<float4>|colorMaps.bindingClass=srv|colorMaps.arraySize=2|colorMaps.arrayElementCount=2|linearSamplers.hlslType=SamplerState|linearSamplers.bindingClass=sampler|linearSamplers.arraySize=2|linearSamplers.arrayElementCount=2"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_build_opengl_mixed_resource_descriptor_array_source_package
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_MIXED_RESOURCE_DESCRIPTOR_ARRAY_SHADER}
    -DTARGET=opengl
    -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-opengl-mixed-resource-descriptor-array.cglb
    -DMODE=source-package-build
    -DEXPECTED_SOURCE=backend/opengl/MixedResourceDescriptorArrayShader.comp.glsl
    "-DEXPECTED_SOURCE_SNIPPET=textureLod(sampler2D(colorMaps[1], linearSamplers[0]), uv, 0.5);"
    "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=opengl|module=MixedResourceDescriptorArrayShader"
    "-DEXPECTED_REFLECTION_TARGET_FIELDS=particles.bindingClass=storage-buffer|particles.arraySize=2|particles.arrayElementCount=2|particles.storageBufferLayout.elementType=Particle|particles.storageBufferLayout.layout=std430|colorMaps.bindingClass=texture|colorMaps.arraySize=2|colorMaps.arrayElementCount=2|linearSamplers.bindingClass=sampler|linearSamplers.arraySize=2|linearSamplers.arrayElementCount=2"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_build_directx_nonuniform_descriptor_array_index_source_package
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_VULKAN_NONUNIFORM_DESCRIPTOR_ARRAY_INDEX_SHADER}
    -DTARGET=directx
    -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-directx-nonuniform-descriptor-array-index.cglb
    -DMODE=source-package-build
    -DEXPECTED_SOURCE=backend/directx/VulkanNonUniformDescriptorArrayIndexShader.hlsl
    "-DEXPECTED_SOURCE_SNIPPET=NonUniformResourceIndex(descriptor)"
    "-DEXPECTED_REFLECTION_FEATURE_FIELDS=nonuniform-descriptor-index.kind=operation|NonUniformResourceIndex.kind=intrinsic"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_build_opengl_nonuniform_descriptor_array_index_source_package
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_VULKAN_NONUNIFORM_DESCRIPTOR_ARRAY_INDEX_SHADER}
    -DTARGET=opengl
    -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-opengl-nonuniform-descriptor-array-index.cglb
    -DMODE=source-package-build
    -DEXPECTED_SOURCE=backend/opengl/VulkanNonUniformDescriptorArrayIndexShader.comp.glsl
    "-DEXPECTED_SOURCE_SNIPPET=#extension GL_EXT_nonuniform_qualifier : require"
    "-DEXPECTED_REFLECTION_FEATURE_FIELDS=nonuniform-descriptor-index.kind=operation|GL_EXT_nonuniform_qualifier.kind=extension"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_build_directx_mixed_resource_symbolic_descriptor_array_source_package
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_MIXED_RESOURCE_SYMBOLIC_DESCRIPTOR_ARRAY_SHADER}
    -DTARGET=directx
    -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-directx-mixed-resource-symbolic-descriptor-array.cglb
    -DMODE=source-package-build
    -DEXPECTED_SOURCE=backend/directx/MixedResourceSymbolicDescriptorArrayShader.hlsl
    "-DEXPECTED_SOURCE_SNIPPET=Texture2D<float4> colorMaps[RESOURCE_COUNT] : register(t2, space0);"
    "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=directx|module=MixedResourceSymbolicDescriptorArrayShader"
    "-DEXPECTED_REFLECTION_TARGET_FIELDS=particles.hlslType=RWStructuredBuffer<Particle>|particles.bindingClass=uav|particles.arraySize=RESOURCE_COUNT|particles.arrayElementCount=2|colorMaps.hlslType=Texture2D<float4>|colorMaps.bindingClass=srv|colorMaps.arraySize=RESOURCE_COUNT|colorMaps.arrayElementCount=2|linearSamplers.hlslType=SamplerState|linearSamplers.bindingClass=sampler|linearSamplers.arraySize=RESOURCE_COUNT|linearSamplers.arrayElementCount=2"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_build_opengl_mixed_resource_symbolic_descriptor_array_source_package
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_MIXED_RESOURCE_SYMBOLIC_DESCRIPTOR_ARRAY_SHADER}
    -DTARGET=opengl
    -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-opengl-mixed-resource-symbolic-descriptor-array.cglb
    -DMODE=source-package-build
    -DEXPECTED_SOURCE=backend/opengl/MixedResourceSymbolicDescriptorArrayShader.comp.glsl
    "-DEXPECTED_SOURCE_SNIPPET=particles_Buffers[RESOURCE_COUNT];"
    "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=opengl|module=MixedResourceSymbolicDescriptorArrayShader"
    "-DEXPECTED_REFLECTION_TARGET_FIELDS=particles.bindingClass=storage-buffer|particles.arraySize=RESOURCE_COUNT|particles.arrayElementCount=2|particles.storageBufferLayout.elementType=Particle|particles.storageBufferLayout.layout=std430|colorMaps.bindingClass=texture|colorMaps.arraySize=RESOURCE_COUNT|colorMaps.arrayElementCount=2|linearSamplers.bindingClass=sampler|linearSamplers.arraySize=RESOURCE_COUNT|linearSamplers.arrayElementCount=2"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
crossgl_capture_current_tests(CROSSGL_SOURCE_PACKAGE_METAL_NATIVE_TESTS_BEFORE)

if(CROSSGL_HAS_METAL_NATIVE_TOOLS)
  set(CROSSGL_METAL_WORKGROUP_BARRIER_PACKAGE_SOURCE_SNIPPET [=[kernel void compute_main(device float* values [[buffer(0)]]) {
  threadgroup float tile[GROUP_SIZE];
  tile[0] = values[0];
  threadgroup_barrier(mem_flags::mem_threadgroup);
  float first = tile[0];
  tile[1] = first + 1.0;
  threadgroup_barrier(mem_flags::mem_threadgroup);
  values[1] = tile[1];]=])
  add_test(NAME cglc_build_metal_workgroup_barrier_source_package
    COMMAND ${CMAKE_COMMAND}
      -DCGLC=$<TARGET_FILE:cglc>
      -DINPUT=${CMAKE_CURRENT_SOURCE_DIR}/tests/metal/fixtures/MetalWorkgroupBarrierShader.cgl
      -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-metal-workgroup-barrier-source.cglb
      -DEXPECTED_MODULE=MetalWorkgroupBarrierShader
      -DMODE=metal-build
      "-DEXPECTED_METAL_SOURCE_SNIPPET=${CROSSGL_METAL_WORKGROUP_BARRIER_PACKAGE_SOURCE_SNIPPET}"
      "-DEXPECTED_MANIFEST_JSON_FIELDS=schemaVersion=1|target=metal|module=MetalWorkgroupBarrierShader|artifacts.backendSource=backend/metal/MetalWorkgroupBarrierShader.metal|artifacts.intermediate=backend/metal/MetalWorkgroupBarrierShader.air|artifacts.nativeBinary=backend/metal/MetalWorkgroupBarrierShader.metallib"
      "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=metal|module=MetalWorkgroupBarrierShader|nativeBinary=backend/metal/MetalWorkgroupBarrierShader.metallib|functionConstants.0.name=GROUP_SIZE|functionConstants.0.value=4|workgroupSizes.0.entryPoint=compute_main|workgroupSizes.0.x=4|workgroupSizes.0.y=1|workgroupSizes.0.z=1|workgroupSizes.0.sourceX=GROUP_SIZE|workgroupSizes.0.sourceY=1|workgroupSizes.0.sourceZ=1|manualTextureCompareKernelSummary.totalCount=0"
      "-DEXPECTED_REFLECTION_JSON_ARRAY_LENGTHS=resources=2|targetResourceBindings=2|functionConstants=1|workgroupSizes=1|manualTextureCompareKernels=0"
      "-DEXPECTED_REFLECTION_TARGET_FIELDS=values.sourceType=float*|values.metalType=device float*|values.addressSpace=device|values.abi=kernelArgument|values.bindingClass=buffer|values.argumentIndex=0|values.storageBufferLayout.layout=metal-device|tile.sourceType=float[GROUP_SIZE]|tile.metalType=threadgroup float|tile.addressSpace=threadgroup|tile.abi=threadgroupLocal|tile.bindingClass=threadgroup|tile.arraySize=GROUP_SIZE|tile.arrayElementCount=4|tile.arrayDimensions.0.source=GROUP_SIZE|tile.arrayDimensions.0.elementCount=4"
      "-DEXPECTED_REFLECTION_FEATURE_FIELDS=native-metal-package.kind=backend|MSL.kind=sourceLanguage|metallib.kind=binaryFormat|xcrun-metal.kind=toolchain|xcrun-metallib.kind=toolchain|compute-kernel.kind=stage|workgroup-size.kind=execution|storage-buffer.kind=resource|workgroup-shared-memory.kind=resource|fixed-array.kind=layout|storage-buffer-read.kind=operation|index-access.kind=operation|local-declaration.kind=operation|scalar-arithmetic.kind=operation|storage-buffer-write.kind=operation"
      "-DEXPECTED_DIAGNOSTICS_JSON_ARRAY_LENGTHS=diagnostics=0"
      -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
  set(CROSSGL_METAL_ATOMIC_ADD_PACKAGE_SOURCE_SNIPPET [=[kernel void compute_main(uint3 gl_LocalInvocationID [[thread_position_in_threadgroup]], device atomic_int* counters [[buffer(0)]], device atomic_uint* unsignedCounters [[buffer(1)]]) {
  threadgroup atomic_int tile[GROUP_SIZE];
  threadgroup atomic_uint unsignedTile[GROUP_SIZE];
  uint index = gl_LocalInvocationID.x;
  uint unsignedDelta = gl_LocalInvocationID.x;
  atomic_fetch_add_explicit(&counters[index], 1, memory_order_relaxed);
  atomic_fetch_add_explicit(&unsignedCounters[index], unsignedDelta, memory_order_relaxed);
  atomic_fetch_add_explicit(&tile[index], 1, memory_order_relaxed);
  atomic_fetch_add_explicit(&unsignedTile[index], unsignedDelta, memory_order_relaxed);]=])
  add_test(NAME cglc_build_metal_atomic_add_source_package
    COMMAND ${CMAKE_COMMAND}
      -DCGLC=$<TARGET_FILE:cglc>
      -DINPUT=${CMAKE_CURRENT_SOURCE_DIR}/tests/metal/fixtures/MetalAtomicAddShader.cgl
      -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-metal-atomic-add-source.cglb
      -DEXPECTED_MODULE=MetalAtomicAddShader
      -DMODE=metal-build
      "-DEXPECTED_METAL_SOURCE_SNIPPET=${CROSSGL_METAL_ATOMIC_ADD_PACKAGE_SOURCE_SNIPPET}"
      "-DEXPECTED_MANIFEST_JSON_FIELDS=schemaVersion=1|target=metal|module=MetalAtomicAddShader|artifacts.backendSource=backend/metal/MetalAtomicAddShader.metal|artifacts.intermediate=backend/metal/MetalAtomicAddShader.air|artifacts.nativeBinary=backend/metal/MetalAtomicAddShader.metallib"
      "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=metal|module=MetalAtomicAddShader|nativeBinary=backend/metal/MetalAtomicAddShader.metallib|functionConstants.0.name=GROUP_SIZE|functionConstants.0.value=4|workgroupSizes.0.entryPoint=compute_main|workgroupSizes.0.x=4|workgroupSizes.0.y=1|workgroupSizes.0.z=1|workgroupSizes.0.sourceX=GROUP_SIZE|manualTextureCompareKernelSummary.totalCount=0"
      "-DEXPECTED_REFLECTION_JSON_ARRAY_LENGTHS=resources=4|targetResourceBindings=4|functionConstants=1|workgroupSizes=1|manualTextureCompareKernels=0"
      "-DEXPECTED_REFLECTION_TARGET_FIELDS=counters.sourceType=atomic<int>*|counters.metalType=device atomic_int*|counters.addressSpace=device|counters.abi=kernelArgument|counters.bindingClass=buffer|counters.argumentIndex=0|unsignedCounters.sourceType=atomic<uint>*|unsignedCounters.metalType=device atomic_uint*|unsignedCounters.addressSpace=device|unsignedCounters.abi=kernelArgument|unsignedCounters.bindingClass=buffer|unsignedCounters.argumentIndex=1|tile.sourceType=atomic<int>[GROUP_SIZE]|tile.metalType=threadgroup atomic_int|tile.addressSpace=threadgroup|tile.abi=threadgroupLocal|tile.bindingClass=threadgroup|tile.arraySize=GROUP_SIZE|tile.arrayElementCount=4|unsignedTile.sourceType=atomic<uint>[GROUP_SIZE]|unsignedTile.metalType=threadgroup atomic_uint|unsignedTile.addressSpace=threadgroup|unsignedTile.abi=threadgroupLocal|unsignedTile.bindingClass=threadgroup|unsignedTile.arraySize=GROUP_SIZE|unsignedTile.arrayElementCount=4"
      "-DEXPECTED_REFLECTION_FEATURE_FIELDS=native-metal-package.kind=backend|MSL.kind=sourceLanguage|metallib.kind=binaryFormat|xcrun-metal.kind=toolchain|xcrun-metallib.kind=toolchain|compute-kernel.kind=stage|workgroup-size.kind=execution|storage-buffer.kind=resource|workgroup-shared-memory.kind=resource|fixed-array.kind=layout|index-access.kind=operation"
      -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
  set(CROSSGL_METAL_ATOMIC_ADD_RETURN_PACKAGE_SOURCE_SNIPPET [=[uint index = gl_LocalInvocationID.x;
  uint globalIndex = gl_GlobalInvocationID.x;
  uint unsignedDelta = globalIndex + 1;
  atomic_fetch_add_explicit(&counters[index], 1, memory_order_relaxed);
  int oldStorage = atomic_fetch_add_explicit(&counters[index], 2, memory_order_relaxed);
  oldStorage = atomic_fetch_add_explicit(&counters[index], 3, memory_order_relaxed);
  uint oldUnsigned = atomic_fetch_add_explicit(&unsignedCounters[index], unsignedDelta, memory_order_relaxed);
  int oldShared = atomic_fetch_add_explicit(&tile[index], 1, memory_order_relaxed);
  uint oldUnsignedShared = atomic_fetch_add_explicit(&unsignedTile[index], unsignedDelta, memory_order_relaxed);
  int oldCompat = atomic_fetch_add_explicit(reinterpret_cast<device atomic_int*>(&compatCounters->active_count), 1, memory_order_relaxed);
  uint oldUnsignedCompat = atomic_fetch_add_explicit(reinterpret_cast<device atomic_uint*>(&compatCounters->spawn_count), unsignedDelta, memory_order_relaxed);]=])
  add_test(NAME cglc_build_metal_atomic_add_return_source_package
    COMMAND ${CMAKE_COMMAND}
      -DCGLC=$<TARGET_FILE:cglc>
      -DINPUT=${CMAKE_CURRENT_SOURCE_DIR}/tests/metal/fixtures/MetalAtomicAddReturnShader.cgl
      -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-metal-atomic-add-return-source.cglb
      -DEXPECTED_MODULE=MetalAtomicAddReturnShader
      -DMODE=metal-build
      "-DEXPECTED_METAL_SOURCE_SNIPPET=${CROSSGL_METAL_ATOMIC_ADD_RETURN_PACKAGE_SOURCE_SNIPPET}"
      "-DEXPECTED_MANIFEST_JSON_FIELDS=schemaVersion=1|target=metal|module=MetalAtomicAddReturnShader|artifacts.backendSource=backend/metal/MetalAtomicAddReturnShader.metal|artifacts.intermediate=backend/metal/MetalAtomicAddReturnShader.air|artifacts.nativeBinary=backend/metal/MetalAtomicAddReturnShader.metallib"
      "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=metal|module=MetalAtomicAddReturnShader|nativeBinary=backend/metal/MetalAtomicAddReturnShader.metallib|functionConstants.0.name=GROUP_SIZE|functionConstants.0.value=4|resources.0.name=counters|resources.0.kind=buffer|resources.0.type=atomic<int>*|resources.1.name=unsignedCounters|resources.1.type=atomic<uint>*|resources.2.name=compatCounters|resources.2.type=CompatCounters|resources.5.name=tile|resources.5.kind=shared|resources.5.type=atomic<int>[GROUP_SIZE]|resources.6.name=unsignedTile|resources.6.type=atomic<uint>[GROUP_SIZE]|workgroupSizes.0.entryPoint=compute_main|workgroupSizes.0.x=4|workgroupSizes.0.y=1|workgroupSizes.0.z=1|workgroupSizes.0.sourceX=GROUP_SIZE|manualTextureCompareKernelSummary.totalCount=0"
      "-DEXPECTED_REFLECTION_JSON_ARRAY_LENGTHS=resources=7|targetResourceBindings=7|functionConstants=1|workgroupSizes=1|manualTextureCompareKernels=0"
      "-DEXPECTED_REFLECTION_TARGET_FIELDS=counters.sourceType=atomic<int>*|counters.metalType=device atomic_int*|counters.addressSpace=device|counters.bindingClass=buffer|unsignedCounters.sourceType=atomic<uint>*|unsignedCounters.metalType=device atomic_uint*|compatCounters.sourceType=CompatCounters|compatCounters.metalType=device CompatCounters*|compatCounters.storageBufferLayout.fields.0.name=active_count|compatCounters.storageBufferLayout.fields.0.offsetBytes=0|compatCounters.storageBufferLayout.fields.1.name=spawn_count|compatCounters.storageBufferLayout.fields.1.offsetBytes=4|tile.sourceType=atomic<int>[GROUP_SIZE]|tile.metalType=threadgroup atomic_int|tile.addressSpace=threadgroup|tile.bindingClass=threadgroup|unsignedTile.sourceType=atomic<uint>[GROUP_SIZE]|unsignedTile.metalType=threadgroup atomic_uint|unsignedTile.addressSpace=threadgroup|unsignedTile.bindingClass=threadgroup"
      "-DEXPECTED_REFLECTION_FEATURE_FIELDS=native-metal-package.kind=backend|MSL.kind=sourceLanguage|metallib.kind=binaryFormat|xcrun-metal.kind=toolchain|xcrun-metallib.kind=toolchain|compute-kernel.kind=stage|workgroup-size.kind=execution|storage-buffer.kind=resource|atomic-integer.kind=type|workgroup-shared-memory.kind=resource|fixed-array.kind=layout|local-declaration.kind=operation|scalar-arithmetic.kind=operation|atomic-add.kind=operation|index-access.kind=operation|storage-buffer-read.kind=operation|storage-buffer-write.kind=operation"
      "-DEXPECTED_DIAGNOSTICS_JSON_ARRAY_LENGTHS=diagnostics=0"
      -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
  set(CROSSGL_METAL_ATOMIC_MINMAX_PACKAGE_SOURCE_SNIPPET [=[uint index = gl_LocalInvocationID.x;
  uint globalIndex = gl_GlobalInvocationID.x;
  int value = values[index];
  uint unsignedValue = globalIndex + 1;
  atomic_fetch_min_explicit(&counters[index], value, memory_order_relaxed);
  atomic_fetch_max_explicit(&unsignedCounters[index], unsignedValue, memory_order_relaxed);
  int oldMin = atomic_fetch_min_explicit(&counters[index], value, memory_order_relaxed);
  int oldMax = atomic_fetch_max_explicit(&counters[index], 1, memory_order_relaxed);
  oldMin = atomic_fetch_min_explicit(&counters[index], 1, memory_order_relaxed);
  uint oldMaxU = atomic_fetch_max_explicit(&unsignedCounters[index], unsignedValue, memory_order_relaxed);
  int oldShared = atomic_fetch_min_explicit(&tile[index], value, memory_order_relaxed);
  uint oldSharedU = atomic_fetch_max_explicit(&unsignedTile[index], unsignedValue, memory_order_relaxed);
  int oldCompat = atomic_fetch_max_explicit(reinterpret_cast<device atomic_int*>(&compatCounters->active_count), 1, memory_order_relaxed);
  uint oldCompatU = atomic_fetch_min_explicit(reinterpret_cast<device atomic_uint*>(&compatCounters->spawn_count), unsignedValue, memory_order_relaxed);]=])
  add_test(NAME cglc_build_metal_atomic_minmax_source_package
    COMMAND ${CMAKE_COMMAND}
      -DCGLC=$<TARGET_FILE:cglc>
      -DINPUT=${CMAKE_CURRENT_SOURCE_DIR}/tests/metal/fixtures/MetalAtomicMinMaxShader.cgl
      -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-metal-atomic-minmax-source.cglb
      -DEXPECTED_MODULE=MetalAtomicMinMaxShader
      -DMODE=metal-build
      "-DEXPECTED_METAL_SOURCE_SNIPPET=${CROSSGL_METAL_ATOMIC_MINMAX_PACKAGE_SOURCE_SNIPPET}"
      "-DEXPECTED_MANIFEST_JSON_FIELDS=schemaVersion=1|target=metal|module=MetalAtomicMinMaxShader|artifacts.backendSource=backend/metal/MetalAtomicMinMaxShader.metal|artifacts.intermediate=backend/metal/MetalAtomicMinMaxShader.air|artifacts.nativeBinary=backend/metal/MetalAtomicMinMaxShader.metallib"
      "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=metal|module=MetalAtomicMinMaxShader|nativeBinary=backend/metal/MetalAtomicMinMaxShader.metallib|functionConstants.0.name=GROUP_SIZE|functionConstants.0.value=4|resources.0.name=counters|resources.0.kind=buffer|resources.0.type=atomic<int>*|resources.1.name=unsignedCounters|resources.1.type=atomic<uint>*|resources.2.name=compatCounters|resources.2.type=CompatCounters|resources.5.name=tile|resources.5.kind=shared|resources.5.type=atomic<int>[GROUP_SIZE]|resources.6.name=unsignedTile|resources.6.type=atomic<uint>[GROUP_SIZE]|workgroupSizes.0.entryPoint=compute_main|workgroupSizes.0.x=4|workgroupSizes.0.y=1|workgroupSizes.0.z=1|workgroupSizes.0.sourceX=GROUP_SIZE|manualTextureCompareKernelSummary.totalCount=0"
      "-DEXPECTED_REFLECTION_JSON_ARRAY_LENGTHS=resources=7|targetResourceBindings=7|functionConstants=1|workgroupSizes=1|manualTextureCompareKernels=0"
      "-DEXPECTED_REFLECTION_TARGET_FIELDS=counters.sourceType=atomic<int>*|counters.metalType=device atomic_int*|counters.addressSpace=device|counters.bindingClass=buffer|unsignedCounters.sourceType=atomic<uint>*|unsignedCounters.metalType=device atomic_uint*|compatCounters.sourceType=CompatCounters|compatCounters.metalType=device CompatCounters*|compatCounters.storageBufferLayout.fields.0.name=active_count|compatCounters.storageBufferLayout.fields.0.offsetBytes=0|compatCounters.storageBufferLayout.fields.1.name=spawn_count|compatCounters.storageBufferLayout.fields.1.offsetBytes=4|tile.sourceType=atomic<int>[GROUP_SIZE]|tile.metalType=threadgroup atomic_int|tile.addressSpace=threadgroup|tile.bindingClass=threadgroup|unsignedTile.sourceType=atomic<uint>[GROUP_SIZE]|unsignedTile.metalType=threadgroup atomic_uint|unsignedTile.addressSpace=threadgroup|unsignedTile.bindingClass=threadgroup"
      "-DEXPECTED_DIAGNOSTICS_JSON_ARRAY_LENGTHS=diagnostics=0"
      -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
  set(CROSSGL_METAL_ATOMIC_EXCHANGE_PACKAGE_SOURCE_SNIPPET [=[uint index = gl_LocalInvocationID.x;
  uint globalIndex = gl_GlobalInvocationID.x;
  int value = values[index];
  uint unsignedValue = globalIndex + 1;
  atomic_exchange_explicit(&counters[index], value, memory_order_relaxed);
  atomic_exchange_explicit(&unsignedCounters[index], unsignedValue, memory_order_relaxed);
  atomic_exchange_explicit(&tile[index], value, memory_order_relaxed);
  atomic_exchange_explicit(&unsignedTile[index], unsignedValue, memory_order_relaxed);
  int oldStorage = atomic_exchange_explicit(&counters[index], 1, memory_order_relaxed);
  oldStorage = atomic_exchange_explicit(&counters[index], value, memory_order_relaxed);
  uint oldUnsigned = atomic_exchange_explicit(&unsignedCounters[index], unsignedValue, memory_order_relaxed);
  int oldShared = atomic_exchange_explicit(&tile[index], value, memory_order_relaxed);
  uint oldSharedU = atomic_exchange_explicit(&unsignedTile[index], unsignedValue, memory_order_relaxed);
  int oldCompat = atomic_exchange_explicit(reinterpret_cast<device atomic_int*>(&compatCounters->active_count), 1, memory_order_relaxed);
  uint oldCompatU = atomic_exchange_explicit(reinterpret_cast<device atomic_uint*>(&compatCounters->spawn_count), unsignedValue, memory_order_relaxed);]=])
  add_test(NAME cglc_build_metal_atomic_exchange_source_package
    COMMAND ${CMAKE_COMMAND}
      -DCGLC=$<TARGET_FILE:cglc>
      -DINPUT=${CMAKE_CURRENT_SOURCE_DIR}/tests/metal/fixtures/MetalAtomicExchangeShader.cgl
      -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-metal-atomic-exchange-source.cglb
      -DEXPECTED_MODULE=MetalAtomicExchangeShader
      -DMODE=metal-build
      "-DEXPECTED_METAL_SOURCE_SNIPPET=${CROSSGL_METAL_ATOMIC_EXCHANGE_PACKAGE_SOURCE_SNIPPET}"
      "-DEXPECTED_MANIFEST_JSON_FIELDS=schemaVersion=1|target=metal|module=MetalAtomicExchangeShader|artifacts.backendSource=backend/metal/MetalAtomicExchangeShader.metal|artifacts.intermediate=backend/metal/MetalAtomicExchangeShader.air|artifacts.nativeBinary=backend/metal/MetalAtomicExchangeShader.metallib"
      "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=metal|module=MetalAtomicExchangeShader|nativeBinary=backend/metal/MetalAtomicExchangeShader.metallib|functionConstants.0.name=GROUP_SIZE|functionConstants.0.value=4|resources.0.name=counters|resources.0.kind=buffer|resources.0.type=atomic<int>*|resources.1.name=unsignedCounters|resources.1.type=atomic<uint>*|resources.2.name=compatCounters|resources.2.type=CompatCounters|resources.5.name=tile|resources.5.kind=shared|resources.5.type=atomic<int>[GROUP_SIZE]|resources.6.name=unsignedTile|resources.6.type=atomic<uint>[GROUP_SIZE]|workgroupSizes.0.entryPoint=compute_main|workgroupSizes.0.x=4|workgroupSizes.0.y=1|workgroupSizes.0.z=1|workgroupSizes.0.sourceX=GROUP_SIZE|manualTextureCompareKernelSummary.totalCount=0"
      "-DEXPECTED_REFLECTION_JSON_ARRAY_LENGTHS=resources=7|targetResourceBindings=7|functionConstants=1|workgroupSizes=1|manualTextureCompareKernels=0"
      "-DEXPECTED_REFLECTION_TARGET_FIELDS=counters.sourceType=atomic<int>*|counters.metalType=device atomic_int*|counters.addressSpace=device|counters.bindingClass=buffer|unsignedCounters.sourceType=atomic<uint>*|unsignedCounters.metalType=device atomic_uint*|compatCounters.sourceType=CompatCounters|compatCounters.metalType=device CompatCounters*|compatCounters.storageBufferLayout.fields.0.name=active_count|compatCounters.storageBufferLayout.fields.0.offsetBytes=0|compatCounters.storageBufferLayout.fields.1.name=spawn_count|compatCounters.storageBufferLayout.fields.1.offsetBytes=4|tile.sourceType=atomic<int>[GROUP_SIZE]|tile.metalType=threadgroup atomic_int|tile.addressSpace=threadgroup|tile.bindingClass=threadgroup|unsignedTile.sourceType=atomic<uint>[GROUP_SIZE]|unsignedTile.metalType=threadgroup atomic_uint|unsignedTile.addressSpace=threadgroup|unsignedTile.bindingClass=threadgroup"
      "-DEXPECTED_DIAGNOSTICS_JSON_ARRAY_LENGTHS=diagnostics=0"
      -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
  set(CROSSGL_METAL_ATOMIC_BITWISE_PACKAGE_SOURCE_SNIPPET [=[uint index = gl_LocalInvocationID.x;
  int mask = values[index] + 1;
  uint unsignedMask = index + 1;
  atomic_fetch_and_explicit(&counters[index], mask, memory_order_relaxed);
  atomic_fetch_or_explicit(&unsignedCounters[index], unsignedMask, memory_order_relaxed);
  atomic_fetch_xor_explicit(&tile[index], mask, memory_order_relaxed);
  atomic_fetch_and_explicit(&unsignedTile[index], unsignedMask, memory_order_relaxed);
  int oldAnd = atomic_fetch_and_explicit(&counters[index], mask, memory_order_relaxed);
  int oldOr = atomic_fetch_or_explicit(&counters[index], 1, memory_order_relaxed);
  oldAnd = atomic_fetch_xor_explicit(&counters[index], 1, memory_order_relaxed);
  uint oldOrU = atomic_fetch_or_explicit(&unsignedCounters[index], unsignedMask, memory_order_relaxed);
  uint oldXorU = atomic_fetch_xor_explicit(&unsignedCounters[index], unsignedMask, memory_order_relaxed);
  int oldShared = atomic_fetch_or_explicit(&tile[index], mask, memory_order_relaxed);
  uint oldSharedU = atomic_fetch_xor_explicit(&unsignedTile[index], unsignedMask, memory_order_relaxed);
  int oldCompat = atomic_fetch_and_explicit(reinterpret_cast<device atomic_int*>(&compatCounters->active_count), 1, memory_order_relaxed);
  uint oldCompatU = atomic_fetch_or_explicit(reinterpret_cast<device atomic_uint*>(&compatCounters->spawn_count), unsignedMask, memory_order_relaxed);]=])
  add_test(NAME cglc_build_metal_atomic_bitwise_source_package
    COMMAND ${CMAKE_COMMAND}
      -DCGLC=$<TARGET_FILE:cglc>
      -DINPUT=${CMAKE_CURRENT_SOURCE_DIR}/tests/metal/fixtures/MetalAtomicBitwiseShader.cgl
      -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-metal-atomic-bitwise-source.cglb
      -DEXPECTED_MODULE=MetalAtomicBitwiseShader
      -DMODE=metal-build
      "-DEXPECTED_METAL_SOURCE_SNIPPET=${CROSSGL_METAL_ATOMIC_BITWISE_PACKAGE_SOURCE_SNIPPET}"
      "-DEXPECTED_MANIFEST_JSON_FIELDS=schemaVersion=1|target=metal|module=MetalAtomicBitwiseShader|artifacts.backendSource=backend/metal/MetalAtomicBitwiseShader.metal|artifacts.intermediate=backend/metal/MetalAtomicBitwiseShader.air|artifacts.nativeBinary=backend/metal/MetalAtomicBitwiseShader.metallib"
      "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=metal|module=MetalAtomicBitwiseShader|nativeBinary=backend/metal/MetalAtomicBitwiseShader.metallib|functionConstants.0.name=GROUP_SIZE|functionConstants.0.value=4|resources.0.name=counters|resources.0.kind=buffer|resources.0.type=atomic<int>*|resources.1.name=unsignedCounters|resources.1.type=atomic<uint>*|resources.2.name=compatCounters|resources.2.type=CompatCounters|resources.5.name=tile|resources.5.kind=shared|resources.5.type=atomic<int>[GROUP_SIZE]|resources.6.name=unsignedTile|resources.6.type=atomic<uint>[GROUP_SIZE]|workgroupSizes.0.entryPoint=compute_main|workgroupSizes.0.x=4|workgroupSizes.0.y=1|workgroupSizes.0.z=1|workgroupSizes.0.sourceX=GROUP_SIZE|manualTextureCompareKernelSummary.totalCount=0"
      "-DEXPECTED_REFLECTION_JSON_ARRAY_LENGTHS=resources=7|targetResourceBindings=7|functionConstants=1|workgroupSizes=1|manualTextureCompareKernels=0"
      "-DEXPECTED_REFLECTION_TARGET_FIELDS=counters.sourceType=atomic<int>*|counters.metalType=device atomic_int*|counters.addressSpace=device|counters.bindingClass=buffer|unsignedCounters.sourceType=atomic<uint>*|unsignedCounters.metalType=device atomic_uint*|compatCounters.sourceType=CompatCounters|compatCounters.metalType=device CompatCounters*|compatCounters.storageBufferLayout.fields.0.name=active_count|compatCounters.storageBufferLayout.fields.0.offsetBytes=0|compatCounters.storageBufferLayout.fields.1.name=spawn_count|compatCounters.storageBufferLayout.fields.1.offsetBytes=4|tile.sourceType=atomic<int>[GROUP_SIZE]|tile.metalType=threadgroup atomic_int|tile.addressSpace=threadgroup|tile.bindingClass=threadgroup|unsignedTile.sourceType=atomic<uint>[GROUP_SIZE]|unsignedTile.metalType=threadgroup atomic_uint|unsignedTile.addressSpace=threadgroup|unsignedTile.bindingClass=threadgroup"
      "-DEXPECTED_DIAGNOSTICS_JSON_ARRAY_LENGTHS=diagnostics=0"
      -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
  add_test(NAME cglc_build_metal_storage_buffer_array_native
    COMMAND ${CMAKE_COMMAND}
      -DCGLC=$<TARGET_FILE:cglc>
      -DINPUT=${CROSSGL_STORAGE_BUFFER_ARRAY_ACCESS_SHADER}
      -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-metal-storage-buffer-array.cglb
      -DEXPECTED_MODULE=StorageBufferArrayAccessShader
      -DMODE=metal-build
      "-DEXPECTED_METAL_SOURCE_SNIPPET=values_0[1] = first + 1.0;"
      "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=metal|module=StorageBufferArrayAccessShader"
      "-DEXPECTED_REFLECTION_TARGET_FIELDS=values.sourceType=float*[2]|values.metalType=device float*|values.bindingClass=buffer|values.arraySize=2|values.arrayElementCount=2|values.storageBufferLayout.elementType=float|values.storageBufferLayout.layout=metal-device"
      -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
  add_test(NAME cglc_build_metal_storage_buffer_folded_descriptor_array_native
    COMMAND ${CMAKE_COMMAND}
      -DCGLC=$<TARGET_FILE:cglc>
      -DINPUT=${CROSSGL_METAL_STORAGE_BUFFER_FOLDED_DESCRIPTOR_ARRAY_SHADER}
      -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-metal-storage-buffer-folded-descriptor-array.cglb
      -DEXPECTED_MODULE=MetalStorageBufferFoldedDescriptorArrayShader
      -DMODE=metal-build
      "-DEXPECTED_METAL_SOURCE_SNIPPET=float first = values_1[0];"
      "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=metal|module=MetalStorageBufferFoldedDescriptorArrayShader"
      "-DEXPECTED_REFLECTION_TARGET_FIELDS=values.sourceType=float*[DESCRIPTOR_COUNT]|values.metalType=device float*|values.bindingClass=buffer|values.arraySize=DESCRIPTOR_COUNT|values.arrayElementCount=2|values.storageBufferLayout.elementType=float|values.storageBufferLayout.layout=metal-device"
      -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
  add_test(NAME cglc_build_metal_mixed_resource_descriptor_array_native
    COMMAND ${CMAKE_COMMAND}
      -DCGLC=$<TARGET_FILE:cglc>
      -DINPUT=${CROSSGL_MIXED_RESOURCE_DESCRIPTOR_ARRAY_SHADER}
      -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-metal-mixed-resource-descriptor-array.cglb
      -DEXPECTED_MODULE=MixedResourceDescriptorArrayShader
      -DMODE=metal-build
      "-DEXPECTED_METAL_SOURCE_SNIPPET=device Particle* particles_1 [[buffer(1)]], array<texture2d<float>, 2> colorMaps [[texture(2)]], array<sampler, 2> linearSamplers [[sampler(5)]]"
      "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=metal|module=MixedResourceDescriptorArrayShader"
      "-DEXPECTED_REFLECTION_TARGET_FIELDS=particles.metalType=device Particle*|particles.bindingClass=buffer|particles.arraySize=2|particles.arrayElementCount=2|particles.storageBufferLayout.elementType=Particle|particles.storageBufferLayout.layout=metal-device|colorMaps.metalType=array<texture2d<float>, 2>|colorMaps.bindingClass=texture|colorMaps.arraySize=2|colorMaps.arrayElementCount=2|linearSamplers.metalType=array<sampler, 2>|linearSamplers.bindingClass=sampler|linearSamplers.arraySize=2|linearSamplers.arrayElementCount=2"
      -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
  add_test(NAME cglc_build_metal_mixed_resource_symbolic_descriptor_array_native
    COMMAND ${CMAKE_COMMAND}
      -DCGLC=$<TARGET_FILE:cglc>
      -DINPUT=${CROSSGL_MIXED_RESOURCE_SYMBOLIC_DESCRIPTOR_ARRAY_SHADER}
      -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-metal-mixed-resource-symbolic-descriptor-array.cglb
      -DEXPECTED_MODULE=MixedResourceSymbolicDescriptorArrayShader
      -DMODE=metal-build
      "-DEXPECTED_METAL_SOURCE_SNIPPET=device Particle* particles_1 [[buffer(1)]], array<texture2d<float>, RESOURCE_COUNT> colorMaps [[texture(2)]], array<sampler, RESOURCE_COUNT> linearSamplers [[sampler(5)]]"
      "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=metal|module=MixedResourceSymbolicDescriptorArrayShader"
      "-DEXPECTED_REFLECTION_TARGET_FIELDS=particles.metalType=device Particle*|particles.bindingClass=buffer|particles.arraySize=RESOURCE_COUNT|particles.arrayElementCount=2|particles.storageBufferLayout.elementType=Particle|particles.storageBufferLayout.layout=metal-device|colorMaps.metalType=array<texture2d<float>, RESOURCE_COUNT>|colorMaps.bindingClass=texture|colorMaps.arraySize=RESOURCE_COUNT|colorMaps.arrayElementCount=2|linearSamplers.metalType=array<sampler, RESOURCE_COUNT>|linearSamplers.bindingClass=sampler|linearSamplers.arraySize=RESOURCE_COUNT|linearSamplers.arrayElementCount=2"
      -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
  add_test(NAME cglc_build_metal_nonuniform_descriptor_array_index_native
    COMMAND ${CMAKE_COMMAND}
      -DCGLC=$<TARGET_FILE:cglc>
      -DINPUT=${CROSSGL_VULKAN_NONUNIFORM_DESCRIPTOR_ARRAY_INDEX_SHADER}
      -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-metal-nonuniform-descriptor-array-index.cglb
      -DEXPECTED_MODULE=VulkanNonUniformDescriptorArrayIndexShader
      -DMODE=metal-build
      "-DEXPECTED_METAL_SOURCE_SNIPPET=device Particle* particles_1 [[buffer(1)]], device int* descriptors [[buffer(2)]], array<texture2d<float>, 2> colorMaps [[texture(2)]], array<sampler, 2> linearSamplers [[sampler(5)]]"
      "-DEXPECTED_MANIFEST_JSON_FIELDS=schemaVersion=1|target=metal|module=VulkanNonUniformDescriptorArrayIndexShader|artifacts.backendSource=backend/metal/VulkanNonUniformDescriptorArrayIndexShader.metal|artifacts.intermediate=backend/metal/VulkanNonUniformDescriptorArrayIndexShader.air|artifacts.nativeBinary=backend/metal/VulkanNonUniformDescriptorArrayIndexShader.metallib"
      "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=metal|module=VulkanNonUniformDescriptorArrayIndexShader|nativeBinary=backend/metal/VulkanNonUniformDescriptorArrayIndexShader.metallib|resources.0.name=particles|resources.0.type=Particle*[2]|resources.1.name=descriptors|resources.2.name=colorMaps|resources.2.type=sampler2D[2]|resources.3.name=linearSamplers|resources.3.type=sampler[2]"
      "-DEXPECTED_REFLECTION_JSON_ARRAY_LENGTHS=resources=4|targetResourceBindings=4|workgroupSizes=1"
      "-DEXPECTED_REFLECTION_TARGET_FIELDS=particles.sourceType=Particle*[2]|particles.metalType=device Particle*|particles.bindingClass=buffer|particles.argumentIndex=0|particles.arrayElementCount=2|descriptors.sourceType=int*|descriptors.bindingClass=buffer|descriptors.argumentIndex=2|colorMaps.metalType=array<texture2d<float>, 2>|colorMaps.bindingClass=texture|colorMaps.argumentIndex=2|colorMaps.arrayElementCount=2|linearSamplers.metalType=array<sampler, 2>|linearSamplers.bindingClass=sampler|linearSamplers.argumentIndex=5|linearSamplers.arrayElementCount=2"
      "-DEXPECTED_REFLECTION_FEATURE_FIELDS=native-metal-package.kind=backend|descriptor-array.kind=resource|nonuniform-descriptor-index.kind=operation|nonuniform-storage-buffer-descriptor-index.kind=operation|nonuniform-texture-descriptor-index.kind=operation|nonuniform-sampler-descriptor-index.kind=operation"
      "-DEXPECTED_DIAGNOSTICS_JSON_ARRAY_LENGTHS=diagnostics=0"
      -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
  add_test(NAME cglc_build_metal_texture_compare_nonuniform_descriptor_array_source_package
    COMMAND ${CMAKE_COMMAND}
      -DCGLC=$<TARGET_FILE:cglc>
      -DINPUT=${CROSSGL_TEXTURE_COMPARE_NONUNIFORM_DESCRIPTOR_ARRAY_SHADER}
      -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-metal-texture-compare-nonuniform-descriptor-array-source.cglb
      -DEXPECTED_MODULE=TextureCompareNonUniformDescriptorArrayShader
      -DMODE=metal-build
      "-DEXPECTED_METAL_SOURCE_SNIPPET=shadowMaps[descriptor].sample_compare(shadowSamplers[descriptor]"
      "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=metal|module=TextureCompareNonUniformDescriptorArrayShader"
      "-DEXPECTED_REFLECTION_TARGET_FIELDS=shadowMaps.bindingClass=texture|shadowMaps.arrayElementCount=2|shadowSamplers.bindingClass=sampler|shadowSamplers.arrayElementCount=2|descriptors.storageBufferLayout.layout=metal-device"
      "-DEXPECTED_REFLECTION_FEATURE_FIELDS=nonuniform-descriptor-index.kind=operation|nonuniform-texture-descriptor-index.kind=operation|nonuniform-sampler-descriptor-index.kind=operation"
      -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
  add_test(NAME cglc_build_metal_texture_compare_nonuniform_descriptor_array_lod_source_package
    COMMAND ${CMAKE_COMMAND}
      -DCGLC=$<TARGET_FILE:cglc>
      -DINPUT=${CROSSGL_TEXTURE_COMPARE_NONUNIFORM_DESCRIPTOR_ARRAY_LOD_SHADER}
      -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-metal-texture-compare-nonuniform-descriptor-array-lod-source.cglb
      -DEXPECTED_MODULE=TextureCompareNonUniformDescriptorArrayLodShader
      -DMODE=metal-build
      "-DEXPECTED_METAL_SOURCE_SNIPPET=shadowMaps[descriptor].sample_compare(shadowSamplers[descriptor], float2(0.5, 0.5), 0.25, level(2.0))"
      "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=metal|module=TextureCompareNonUniformDescriptorArrayLodShader"
      "-DEXPECTED_REFLECTION_TARGET_FIELDS=shadowMaps.bindingClass=texture|shadowMaps.arrayElementCount=2|shadowSamplers.bindingClass=sampler|shadowSamplers.arrayElementCount=2|descriptors.storageBufferLayout.layout=metal-device"
      "-DEXPECTED_REFLECTION_FEATURE_FIELDS=nonuniform-descriptor-index.kind=operation|nonuniform-texture-descriptor-index.kind=operation|nonuniform-sampler-descriptor-index.kind=operation"
      -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
  add_test(NAME cglc_build_metal_texture_compare_lod_manual_nonuniform_descriptor_array_source_package
    COMMAND ${CMAKE_COMMAND}
      -DCGLC=$<TARGET_FILE:cglc>
      -DINPUT=${CROSSGL_TEXTURE_COMPARE_LOD_MANUAL_NONUNIFORM_DESCRIPTOR_ARRAY_SHADER}
      -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-metal-texture-compare-lod-manual-nonuniform-descriptor-array-source.cglb
      -DEXPECTED_MODULE=TextureCompareLodManualNonUniformDescriptorArrayShader
      -DMODE=metal-build
      "-DEXPECTED_METAL_SOURCE_SNIPPET=cglCompareDepth(shadowAtlases[descriptor].sample(rawShadowSamplers[descriptor], float2(0.25, 0.5), uint(1.0), level(2.0)), 0.33, CGL_COMPARE_LESS_EQUAL)"
      "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=metal|module=TextureCompareLodManualNonUniformDescriptorArrayShader|manualTextureCompareKernelSummary.totalCount=0"
      "-DEXPECTED_REFLECTION_TARGET_FIELDS=shadowAtlases.bindingClass=texture|shadowAtlases.arrayElementCount=2|rawShadowSamplers.bindingClass=sampler|rawShadowSamplers.arrayElementCount=2|descriptors.storageBufferLayout.layout=metal-device"
      "-DEXPECTED_REFLECTION_TARGET_ARRAY_CONTAINS=shadowAtlases.usageRoles=manual-depth-texture|rawShadowSamplers.usageRoles=manual-raw-sampler"
      "-DEXPECTED_REFLECTION_FEATURE_FIELDS=nonuniform-descriptor-index.kind=operation|nonuniform-texture-descriptor-index.kind=operation|nonuniform-sampler-descriptor-index.kind=operation"
      -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
  add_test(NAME cglc_build_metal_texture_only_nonuniform_compare_descriptor_array_source_package
    COMMAND ${CMAKE_COMMAND}
      -DCGLC=$<TARGET_FILE:cglc>
      -DINPUT=${CROSSGL_TEXTURE_ONLY_NONUNIFORM_COMPARE_DESCRIPTOR_ARRAY_SHADER}
      -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-metal-texture-only-nonuniform-compare-descriptor-array-source.cglb
      -DEXPECTED_MODULE=TextureOnlyNonUniformCompareDescriptorArrayShader
      -DMODE=metal-build
      "-DEXPECTED_METAL_SOURCE_SNIPPET=shadowMaps[descriptor].sample_compare(shadowSampler"
      "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=metal|module=TextureOnlyNonUniformCompareDescriptorArrayShader"
      "-DEXPECTED_REFLECTION_TARGET_FIELDS=shadowMaps.bindingClass=texture|shadowMaps.arrayElementCount=2|shadowSampler.bindingClass=sampler|descriptors.storageBufferLayout.layout=metal-device"
      "-DEXPECTED_REFLECTION_FEATURE_FIELDS=nonuniform-descriptor-index.kind=operation|nonuniform-texture-descriptor-index.kind=operation"
      -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
  add_test(NAME cglc_build_metal_sampler_only_nonuniform_compare_descriptor_array_source_package
    COMMAND ${CMAKE_COMMAND}
      -DCGLC=$<TARGET_FILE:cglc>
      -DINPUT=${CROSSGL_SAMPLER_ONLY_NONUNIFORM_COMPARE_DESCRIPTOR_ARRAY_SHADER}
      -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-metal-sampler-only-nonuniform-compare-descriptor-array-source.cglb
      -DEXPECTED_MODULE=SamplerOnlyNonUniformCompareDescriptorArrayShader
      -DMODE=metal-build
      "-DEXPECTED_METAL_SOURCE_SNIPPET=shadowMap.sample_compare(shadowSamplers[descriptor]"
      "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=metal|module=SamplerOnlyNonUniformCompareDescriptorArrayShader"
      "-DEXPECTED_REFLECTION_TARGET_FIELDS=shadowMap.bindingClass=texture|shadowSamplers.bindingClass=sampler|shadowSamplers.arrayElementCount=2|descriptors.storageBufferLayout.layout=metal-device"
      "-DEXPECTED_REFLECTION_FEATURE_FIELDS=nonuniform-descriptor-index.kind=operation|nonuniform-sampler-descriptor-index.kind=operation"
      -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
  add_test(NAME cglc_build_metal_texture_only_nonuniform_compare_descriptor_array_lod_source_package
    COMMAND ${CMAKE_COMMAND}
      -DCGLC=$<TARGET_FILE:cglc>
      -DINPUT=${CROSSGL_TEXTURE_ONLY_NONUNIFORM_COMPARE_DESCRIPTOR_ARRAY_LOD_SHADER}
      -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-metal-texture-only-nonuniform-compare-descriptor-array-lod-source.cglb
      -DEXPECTED_MODULE=TextureOnlyNonUniformCompareDescriptorArrayLodShader
      -DMODE=metal-build
      "-DEXPECTED_METAL_SOURCE_SNIPPET=shadowMaps[descriptor].sample_compare(shadowSampler, float2(0.5, 0.5), 0.25, level(2.0))"
      "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=metal|module=TextureOnlyNonUniformCompareDescriptorArrayLodShader"
      "-DEXPECTED_REFLECTION_TARGET_FIELDS=shadowMaps.bindingClass=texture|shadowMaps.arrayElementCount=2|shadowSampler.bindingClass=sampler|descriptors.storageBufferLayout.layout=metal-device"
      "-DEXPECTED_REFLECTION_FEATURE_FIELDS=nonuniform-descriptor-index.kind=operation|nonuniform-texture-descriptor-index.kind=operation"
      -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
  add_test(NAME cglc_build_metal_sampler_only_nonuniform_compare_descriptor_array_lod_source_package
    COMMAND ${CMAKE_COMMAND}
      -DCGLC=$<TARGET_FILE:cglc>
      -DINPUT=${CROSSGL_SAMPLER_ONLY_NONUNIFORM_COMPARE_DESCRIPTOR_ARRAY_LOD_SHADER}
      -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-metal-sampler-only-nonuniform-compare-descriptor-array-lod-source.cglb
      -DEXPECTED_MODULE=SamplerOnlyNonUniformCompareDescriptorArrayLodShader
      -DMODE=metal-build
      "-DEXPECTED_METAL_SOURCE_SNIPPET=shadowMap.sample_compare(shadowSamplers[descriptor], float2(0.5, 0.5), 0.25, level(2.0))"
      "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=metal|module=SamplerOnlyNonUniformCompareDescriptorArrayLodShader"
      "-DEXPECTED_REFLECTION_TARGET_FIELDS=shadowMap.bindingClass=texture|shadowSamplers.bindingClass=sampler|shadowSamplers.arrayElementCount=2|descriptors.storageBufferLayout.layout=metal-device"
      "-DEXPECTED_REFLECTION_FEATURE_FIELDS=nonuniform-descriptor-index.kind=operation|nonuniform-sampler-descriptor-index.kind=operation"
      -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
  add_test(NAME cglc_build_metal_texture_only_nonuniform_compare_lod_manual_descriptor_array_source_package
    COMMAND ${CMAKE_COMMAND}
      -DCGLC=$<TARGET_FILE:cglc>
      -DINPUT=${CROSSGL_TEXTURE_ONLY_NONUNIFORM_COMPARE_LOD_MANUAL_DESCRIPTOR_ARRAY_SHADER}
      -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-metal-texture-only-nonuniform-compare-lod-manual-descriptor-array-source.cglb
      -DEXPECTED_MODULE=TextureOnlyNonUniformCompareLodManualDescriptorArrayShader
      -DMODE=metal-build
      "-DEXPECTED_METAL_SOURCE_SNIPPET=cglCompareDepth(shadowAtlases[descriptor].sample(rawShadowSampler, float2(0.25, 0.5), uint(1.0), level(2.0)), 0.33, CGL_COMPARE_LESS_EQUAL)"
      "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=metal|module=TextureOnlyNonUniformCompareLodManualDescriptorArrayShader|manualTextureCompareKernelSummary.totalCount=0"
      "-DEXPECTED_REFLECTION_TARGET_FIELDS=shadowAtlases.bindingClass=texture|shadowAtlases.arrayElementCount=2|rawShadowSampler.bindingClass=sampler|descriptors.storageBufferLayout.layout=metal-device"
      "-DEXPECTED_REFLECTION_TARGET_ARRAY_CONTAINS=shadowAtlases.usageRoles=manual-depth-texture|rawShadowSampler.usageRoles=manual-raw-sampler"
      "-DEXPECTED_REFLECTION_FEATURE_FIELDS=nonuniform-descriptor-index.kind=operation|nonuniform-texture-descriptor-index.kind=operation"
      -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
  add_test(NAME cglc_build_metal_sampler_only_nonuniform_compare_lod_manual_descriptor_array_source_package
    COMMAND ${CMAKE_COMMAND}
      -DCGLC=$<TARGET_FILE:cglc>
      -DINPUT=${CROSSGL_SAMPLER_ONLY_NONUNIFORM_COMPARE_LOD_MANUAL_DESCRIPTOR_ARRAY_SHADER}
      -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-metal-sampler-only-nonuniform-compare-lod-manual-descriptor-array-source.cglb
      -DEXPECTED_MODULE=SamplerOnlyNonUniformCompareLodManualDescriptorArrayShader
      -DMODE=metal-build
      "-DEXPECTED_METAL_SOURCE_SNIPPET=cglCompareDepth(shadowAtlas.sample(rawShadowSamplers[descriptor], float2(0.25, 0.5), uint(1.0), level(2.0)), 0.33, CGL_COMPARE_LESS_EQUAL)"
      "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=metal|module=SamplerOnlyNonUniformCompareLodManualDescriptorArrayShader|manualTextureCompareKernelSummary.totalCount=0"
      "-DEXPECTED_REFLECTION_TARGET_FIELDS=shadowAtlas.bindingClass=texture|rawShadowSamplers.bindingClass=sampler|rawShadowSamplers.arrayElementCount=2|descriptors.storageBufferLayout.layout=metal-device"
      "-DEXPECTED_REFLECTION_TARGET_ARRAY_CONTAINS=shadowAtlas.usageRoles=manual-depth-texture|rawShadowSamplers.usageRoles=manual-raw-sampler"
      "-DEXPECTED_REFLECTION_FEATURE_FIELDS=nonuniform-descriptor-index.kind=operation|nonuniform-sampler-descriptor-index.kind=operation"
      -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
  add_test(NAME cglc_build_metal_texture_cube_family_compare_lod_manual_nonuniform_descriptor_array_source_package
    COMMAND ${CMAKE_COMMAND}
      -DCGLC=$<TARGET_FILE:cglc>
      -DINPUT=${CROSSGL_TEXTURE_CUBE_FAMILY_COMPARE_LOD_MANUAL_NONUNIFORM_DESCRIPTOR_ARRAY_SHADER}
      -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-metal-texture-cube-family-compare-lod-manual-nonuniform-descriptor-array-source.cglb
      -DEXPECTED_MODULE=TextureCubeFamilyCompareLodManualNonUniformDescriptorArrayShader
      -DMODE=metal-build
      "-DEXPECTED_METAL_SOURCE_SNIPPET=cglCompareDepth(shadowCubeArrays[descriptor].sample(rawShadowSamplers[descriptor], float3(0.0, 1.0, 0.0), uint(2.0), level(3.0)), 0.75, CGL_COMPARE_GREATER)"
      "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=metal|module=TextureCubeFamilyCompareLodManualNonUniformDescriptorArrayShader|manualTextureCompareKernelSummary.totalCount=0"
      "-DEXPECTED_REFLECTION_TARGET_FIELDS=shadowCubes.bindingClass=texture|shadowCubes.arrayElementCount=2|shadowCubeArrays.bindingClass=texture|shadowCubeArrays.arrayElementCount=2|rawShadowSamplers.bindingClass=sampler|rawShadowSamplers.arrayElementCount=2|descriptors.storageBufferLayout.layout=metal-device"
      "-DEXPECTED_REFLECTION_TARGET_ARRAY_CONTAINS=shadowCubes.usageRoles=manual-depth-texture|shadowCubeArrays.usageRoles=manual-depth-texture|rawShadowSamplers.usageRoles=manual-raw-sampler"
      "-DEXPECTED_REFLECTION_FEATURE_FIELDS=nonuniform-descriptor-index.kind=operation|nonuniform-texture-descriptor-index.kind=operation|nonuniform-sampler-descriptor-index.kind=operation"
      -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
  add_test(NAME cglc_build_metal_texture_cube_family_only_nonuniform_compare_lod_manual_descriptor_array_source_package
    COMMAND ${CMAKE_COMMAND}
      -DCGLC=$<TARGET_FILE:cglc>
      -DINPUT=${CROSSGL_TEXTURE_CUBE_FAMILY_ONLY_NONUNIFORM_COMPARE_LOD_MANUAL_DESCRIPTOR_ARRAY_SHADER}
      -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-metal-texture-cube-family-only-nonuniform-compare-lod-manual-descriptor-array-source.cglb
      -DEXPECTED_MODULE=TextureCubeFamilyOnlyNonUniformCompareLodManualDescriptorArrayShader
      -DMODE=metal-build
      "-DEXPECTED_METAL_SOURCE_SNIPPET=cglCompareDepth(shadowCubeArrays[descriptor].sample(rawShadowSampler, float3(0.0, 1.0, 0.0), uint(2.0), level(3.0)), 0.75, CGL_COMPARE_GREATER)"
      "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=metal|module=TextureCubeFamilyOnlyNonUniformCompareLodManualDescriptorArrayShader|manualTextureCompareKernelSummary.totalCount=0"
      "-DEXPECTED_REFLECTION_TARGET_FIELDS=shadowCubes.bindingClass=texture|shadowCubes.arrayElementCount=2|shadowCubeArrays.bindingClass=texture|shadowCubeArrays.arrayElementCount=2|rawShadowSampler.bindingClass=sampler|descriptors.storageBufferLayout.layout=metal-device"
      "-DEXPECTED_REFLECTION_TARGET_ARRAY_CONTAINS=shadowCubes.usageRoles=manual-depth-texture|shadowCubeArrays.usageRoles=manual-depth-texture|rawShadowSampler.usageRoles=manual-raw-sampler"
      "-DEXPECTED_REFLECTION_FEATURE_FIELDS=nonuniform-descriptor-index.kind=operation|nonuniform-texture-descriptor-index.kind=operation"
      -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
  add_test(NAME cglc_build_metal_sampler_cube_family_only_nonuniform_compare_lod_manual_descriptor_array_source_package
    COMMAND ${CMAKE_COMMAND}
      -DCGLC=$<TARGET_FILE:cglc>
      -DINPUT=${CROSSGL_SAMPLER_CUBE_FAMILY_ONLY_NONUNIFORM_COMPARE_LOD_MANUAL_DESCRIPTOR_ARRAY_SHADER}
      -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-metal-sampler-cube-family-only-nonuniform-compare-lod-manual-descriptor-array-source.cglb
      -DEXPECTED_MODULE=SamplerCubeFamilyOnlyNonUniformCompareLodManualDescriptorArrayShader
      -DMODE=metal-build
      "-DEXPECTED_METAL_SOURCE_SNIPPET=cglCompareDepth(shadowCubeArray.sample(rawShadowSamplers[descriptor], float3(0.0, 1.0, 0.0), uint(2.0), level(3.0)), 0.75, CGL_COMPARE_GREATER)"
      "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=metal|module=SamplerCubeFamilyOnlyNonUniformCompareLodManualDescriptorArrayShader|manualTextureCompareKernelSummary.totalCount=0"
      "-DEXPECTED_REFLECTION_TARGET_FIELDS=shadowCube.bindingClass=texture|shadowCubeArray.bindingClass=texture|rawShadowSamplers.bindingClass=sampler|rawShadowSamplers.arrayElementCount=2|descriptors.storageBufferLayout.layout=metal-device"
      "-DEXPECTED_REFLECTION_TARGET_ARRAY_CONTAINS=shadowCube.usageRoles=manual-depth-texture|shadowCubeArray.usageRoles=manual-depth-texture|rawShadowSamplers.usageRoles=manual-raw-sampler"
      "-DEXPECTED_REFLECTION_FEATURE_FIELDS=nonuniform-descriptor-index.kind=operation|nonuniform-sampler-descriptor-index.kind=operation"
      -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
  add_test(NAME cglc_build_metal_texture_family_only_nonuniform_compare_descriptor_array_source_package
    COMMAND ${CMAKE_COMMAND}
      -DCGLC=$<TARGET_FILE:cglc>
      -DINPUT=${CROSSGL_TEXTURE_FAMILY_ONLY_NONUNIFORM_COMPARE_DESCRIPTOR_ARRAY_SHADER}
      -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-metal-texture-family-only-nonuniform-compare-descriptor-array-source.cglb
      -DEXPECTED_MODULE=TextureFamilyOnlyNonUniformCompareDescriptorArrayShader
      -DMODE=metal-build
      "-DEXPECTED_METAL_SOURCE_SNIPPET=shadowCubeArrays[descriptor].sample_compare(shadowSampler, float3(0.0, 1.0, 0.0), uint(2.0), 0.5)"
      "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=metal|module=TextureFamilyOnlyNonUniformCompareDescriptorArrayShader"
      "-DEXPECTED_REFLECTION_TARGET_FIELDS=shadowAtlases.bindingClass=texture|shadowAtlases.arrayElementCount=2|shadowCubes.bindingClass=texture|shadowCubes.arrayElementCount=2|shadowCubeArrays.bindingClass=texture|shadowCubeArrays.arrayElementCount=2|shadowSampler.bindingClass=sampler|descriptors.storageBufferLayout.layout=metal-device"
      "-DEXPECTED_REFLECTION_FEATURE_FIELDS=nonuniform-descriptor-index.kind=operation|nonuniform-texture-descriptor-index.kind=operation"
      -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
  add_test(NAME cglc_build_metal_sampler_family_only_nonuniform_compare_descriptor_array_source_package
    COMMAND ${CMAKE_COMMAND}
      -DCGLC=$<TARGET_FILE:cglc>
      -DINPUT=${CROSSGL_SAMPLER_FAMILY_ONLY_NONUNIFORM_COMPARE_DESCRIPTOR_ARRAY_SHADER}
      -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-metal-sampler-family-only-nonuniform-compare-descriptor-array-source.cglb
      -DEXPECTED_MODULE=SamplerFamilyOnlyNonUniformCompareDescriptorArrayShader
      -DMODE=metal-build
      "-DEXPECTED_METAL_SOURCE_SNIPPET=shadowCubeArray.sample_compare(shadowSamplers[descriptor], float3(0.0, 1.0, 0.0), uint(2.0), 0.5)"
      "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=metal|module=SamplerFamilyOnlyNonUniformCompareDescriptorArrayShader"
      "-DEXPECTED_REFLECTION_TARGET_FIELDS=shadowAtlas.bindingClass=texture|shadowCube.bindingClass=texture|shadowCubeArray.bindingClass=texture|shadowSamplers.bindingClass=sampler|shadowSamplers.arrayElementCount=2|descriptors.storageBufferLayout.layout=metal-device"
      "-DEXPECTED_REFLECTION_FEATURE_FIELDS=nonuniform-descriptor-index.kind=operation|nonuniform-sampler-descriptor-index.kind=operation"
      -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
  add_test(NAME cglc_build_metal_struct_storage_buffer_array_native
    COMMAND ${CMAKE_COMMAND}
      -DCGLC=$<TARGET_FILE:cglc>
      -DINPUT=${CROSSGL_STORAGE_BUFFER_STRUCT_ARRAY_ACCESS_SHADER}
      -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-metal-struct-storage-buffer-array.cglb
      -DEXPECTED_MODULE=StorageBufferStructArrayAccessShader
      -DMODE=metal-build
      "-DEXPECTED_METAL_SOURCE_SNIPPET=device Particle* particles_1 [[buffer(1)]]"
      "-DEXPECTED_MANIFEST_JSON_FIELDS=schemaVersion=1|target=metal|module=StorageBufferStructArrayAccessShader|artifacts.backendSource=backend/metal/StorageBufferStructArrayAccessShader.metal|artifacts.intermediate=backend/metal/StorageBufferStructArrayAccessShader.air|artifacts.nativeBinary=backend/metal/StorageBufferStructArrayAccessShader.metallib"
      "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=metal|module=StorageBufferStructArrayAccessShader|nativeBinary=backend/metal/StorageBufferStructArrayAccessShader.metallib|workgroupSizes.0.entryPoint=compute_main|workgroupSizes.0.x=1|workgroupSizes.0.y=1|workgroupSizes.0.z=1"
      "-DEXPECTED_REFLECTION_JSON_ARRAY_LENGTHS=resources=1|targetResourceBindings=1|workgroupSizes=1"
      "-DEXPECTED_REFLECTION_TARGET_FIELDS=particles.sourceType=Particle*[2]|particles.metalType=device Particle*|particles.addressSpace=device|particles.bindingClass=buffer|particles.argumentIndex=0|particles.set=0|particles.binding=0|particles.abi=kernelArgument|particles.arraySize=2|particles.arrayElementCount=2|particles.arrayDimensions.0.source=2|particles.arrayDimensions.0.elementCount=2|particles.storageBufferLayout.elementType=Particle|particles.storageBufferLayout.elementSizeBytes=20|particles.storageBufferLayout.arrayStrideBytes=32|particles.storageBufferLayout.layout=metal-device|particles.storageBufferLayout.fields.0.name=position|particles.storageBufferLayout.fields.0.offsetBytes=0|particles.storageBufferLayout.fields.0.storageSizeBytes=16|particles.storageBufferLayout.fields.1.name=mass|particles.storageBufferLayout.fields.1.offsetBytes=16"
      "-DEXPECTED_REFLECTION_FEATURE_FIELDS=native-metal-package.kind=backend|MSL.kind=sourceLanguage|metallib.kind=binaryFormat|xcrun-metal.kind=toolchain|xcrun-metallib.kind=toolchain|compute-kernel.kind=stage|workgroup-size.kind=execution|storage-buffer.kind=resource|fixed-array.kind=layout|descriptor-array.kind=resource|storage-buffer-read.kind=operation|storage-buffer-write.kind=operation|scalar-arithmetic.kind=operation"
      "-DEXPECTED_DIAGNOSTICS_JSON_ARRAY_LENGTHS=diagnostics=0"
      -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
  add_test(NAME cglc_build_metal_storage_image_atomic_source_package
    COMMAND ${CMAKE_COMMAND}
      -DCGLC=$<TARGET_FILE:cglc>
      -DINPUT=${CROSSGL_STORAGE_IMAGE_ATOMIC_SHADER}
      -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-metal-storage-image-atomic-source.cglb
      -DEXPECTED_MODULE=StorageImageAtomicShader
      -DMODE=metal-build
      "-DEXPECTED_METAL_SOURCE_SNIPPET=uint unsignedMax = unsignedAtlas.atomic_fetch_max(uint2(atlasPixel.xy), uint(atlasPixel.z), uint4(unsignedMin)).x;"
      "-DEXPECTED_MANIFEST_JSON_FIELDS=schemaVersion=1|target=metal|module=StorageImageAtomicShader|artifacts.backendSource=backend/metal/StorageImageAtomicShader.metal|artifacts.intermediate=backend/metal/StorageImageAtomicShader.air|artifacts.nativeBinary=backend/metal/StorageImageAtomicShader.metallib"
      "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=metal|module=StorageImageAtomicShader|nativeBinary=backend/metal/StorageImageAtomicShader.metallib|resources.0.kind=storage_image|resources.0.type=iimage2D|resources.0.storageImageFormat=r32i|resources.1.type=uimage2D|resources.1.storageImageFormat=r32ui|resources.2.type=iimage2DArray|resources.3.type=uimage2DArray|resources.3.storageImageFormat=r32ui|workgroupSizes.0.entryPoint=compute_main|workgroupSizes.0.x=4|workgroupSizes.0.y=4|workgroupSizes.0.z=2"
      "-DEXPECTED_REFLECTION_JSON_ARRAY_LENGTHS=resources=6|targetResourceBindings=6|workgroupSizes=1"
      "-DEXPECTED_REFLECTION_TARGET_FIELDS=signedCounters.sourceType=iimage2D|signedCounters.metalType=texture2d<int, access::read_write>|signedCounters.bindingClass=texture|signedCounters.argumentIndex=0|signedCounters.storageImageFormat=r32i|unsignedCounters.sourceType=uimage2D|unsignedCounters.metalType=texture2d<uint, access::read_write>|unsignedCounters.storageImageFormat=r32ui|signedAtlas.sourceType=iimage2DArray|signedAtlas.metalType=texture2d_array<int, access::read_write>|signedAtlas.storageImageFormat=r32i|unsignedAtlas.sourceType=uimage2DArray|unsignedAtlas.metalType=texture2d_array<uint, access::read_write>|unsignedAtlas.storageImageFormat=r32ui"
      "-DEXPECTED_REFLECTION_FEATURE_FIELDS=native-metal-package.kind=backend|MSL.kind=sourceLanguage|metallib.kind=binaryFormat|xcrun-metal.kind=toolchain|xcrun-metallib.kind=toolchain|storage-image.kind=resource|read-write.kind=storageImage|2d-dimension.kind=storageImage|2d_array-dimension.kind=storageImage|array-dimension.kind=storageImage|r32i-format.kind=storageImage|r32ui-format.kind=storageImage|storage-buffer.kind=resource|storage-image-read.kind=operation|storage-image-write.kind=operation|storage-image-atomic-add.kind=operation|storage-image-atomic-exchange.kind=operation|storage-image-atomic-min.kind=operation|storage-image-atomic-max.kind=operation|storage-image-atomic-and.kind=operation|storage-image-atomic-or.kind=operation|storage-image-atomic-xor.kind=operation"
      "-DEXPECTED_DIAGNOSTICS_JSON_ARRAY_LENGTHS=diagnostics=0"
      -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
  add_test(NAME cglc_build_metal_storage_image_explicit_format_descriptor_array_native
    COMMAND ${CMAKE_COMMAND}
      -DCGLC=$<TARGET_FILE:cglc>
      -DINPUT=${CROSSGL_STORAGE_IMAGE_EXPLICIT_FORMAT_DESCRIPTOR_ARRAY_SHADER}
      -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-metal-storage-image-explicit-format-descriptor-array.cglb
      -DEXPECTED_MODULE=StorageImageExplicitFormatDescriptorArrayShader
      -DMODE=metal-build
      "-DEXPECTED_METAL_SOURCE_SNIPPET=array<texture2d<float, access::read>, IMAGE_COUNT> colorImages [[texture(0)]], array<texture2d<int, access::read>, IMAGE_COUNT> labelImages [[texture(2)]], array<texture2d_array<uint, access::read>, ATLAS_COUNT> maskAtlases [[texture(4)]], array<texture2d_array<uint, access::write>, ATLAS_COUNT> outputAtlases [[texture(6)]]"
      "-DEXPECTED_MANIFEST_JSON_FIELDS=schemaVersion=1|target=metal|module=StorageImageExplicitFormatDescriptorArrayShader|artifacts.backendSource=backend/metal/StorageImageExplicitFormatDescriptorArrayShader.metal|artifacts.intermediate=backend/metal/StorageImageExplicitFormatDescriptorArrayShader.air|artifacts.nativeBinary=backend/metal/StorageImageExplicitFormatDescriptorArrayShader.metallib"
      "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=metal|module=StorageImageExplicitFormatDescriptorArrayShader|nativeBinary=backend/metal/StorageImageExplicitFormatDescriptorArrayShader.metallib|resources.0.kind=storage_image|resources.0.type=image2D[IMAGE_COUNT]|resources.0.storageImageFormat=r32f|resources.1.type=iimage2D[IMAGE_COUNT]|resources.1.storageImageFormat=r32i|resources.2.type=uimage2DArray[ATLAS_COUNT]|resources.2.storageImageFormat=r32ui|resources.3.type=uimage2DArray[ATLAS_COUNT]|resources.3.storageImageFormat=r32ui|workgroupSizes.0.entryPoint=compute_main"
      "-DEXPECTED_REFLECTION_JSON_ARRAY_LENGTHS=resources=8|targetResourceBindings=8|functionConstants=2|workgroupSizes=1"
      "-DEXPECTED_REFLECTION_TARGET_FIELDS=colorImages.metalType=array<texture2d<float, access::read>, IMAGE_COUNT>|colorImages.bindingClass=texture|colorImages.storageImageFormat=r32f|colorImages.argumentIndex=0|colorImages.arrayElementCount=2|labelImages.metalType=array<texture2d<int, access::read>, IMAGE_COUNT>|labelImages.storageImageFormat=r32i|labelImages.argumentIndex=2|maskAtlases.metalType=array<texture2d_array<uint, access::read>, ATLAS_COUNT>|maskAtlases.storageImageFormat=r32ui|maskAtlases.argumentIndex=4|outputAtlases.metalType=array<texture2d_array<uint, access::write>, ATLAS_COUNT>|outputAtlases.storageImageFormat=r32ui|outputAtlases.argumentIndex=6|slots.bindingClass=buffer|slots.argumentIndex=4|colors.argumentIndex=5|labels.argumentIndex=6|masks.argumentIndex=7"
      "-DEXPECTED_REFLECTION_FEATURE_FIELDS=native-metal-package.kind=backend|storage-image.kind=resource|read-only.kind=storageImage|write-only.kind=storageImage|descriptor-array.kind=resource|fixed-array.kind=layout|r32f-format.kind=storageImage|r32i-format.kind=storageImage|r32ui-format.kind=storageImage|nonuniform-descriptor-index.kind=operation|nonuniform-storage-image-descriptor-index.kind=operation|storage-image-read.kind=operation|storage-image-write.kind=operation"
      "-DEXPECTED_DIAGNOSTICS_JSON_ARRAY_LENGTHS=diagnostics=0"
      -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
  add_test(NAME cglc_build_metal_storage_image_atomic_descriptor_array_source_package
    COMMAND ${CMAKE_COMMAND}
      -DCGLC=$<TARGET_FILE:cglc>
      -DINPUT=${CROSSGL_METAL_STORAGE_IMAGE_ATOMIC_DESCRIPTOR_ARRAY_SHADER}
      -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-metal-storage-image-atomic-descriptor-array-source.cglb
      -DEXPECTED_MODULE=MetalStorageImageAtomicDescriptorArrayShader
      -DMODE=metal-build
      "-DEXPECTED_METAL_SOURCE_SNIPPET=array<texture2d<int, access::read_write>, IMAGE_COUNT> signedCounters [[texture(1)]]"
      "-DEXPECTED_MANIFEST_JSON_FIELDS=schemaVersion=1|target=metal|module=MetalStorageImageAtomicDescriptorArrayShader|artifacts.backendSource=backend/metal/MetalStorageImageAtomicDescriptorArrayShader.metal|artifacts.intermediate=backend/metal/MetalStorageImageAtomicDescriptorArrayShader.air|artifacts.nativeBinary=backend/metal/MetalStorageImageAtomicDescriptorArrayShader.metallib"
      "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=metal|module=MetalStorageImageAtomicDescriptorArrayShader|nativeBinary=backend/metal/MetalStorageImageAtomicDescriptorArrayShader.metallib|functionConstants.0.name=IMAGE_COUNT|functionConstants.0.value=2|resources.1.kind=storage_image|resources.1.type=iimage2D[IMAGE_COUNT]|resources.1.storageImageFormat=r32i|resources.2.type=uimage2D[IMAGE_COUNT]|resources.2.storageImageFormat=r32ui|resources.3.type=iimage2DArray[IMAGE_COUNT]|resources.4.type=uimage2DArray[IMAGE_COUNT]|resources.4.storageImageFormat=r32ui|workgroupSizes.0.entryPoint=compute_main|workgroupSizes.0.x=2|workgroupSizes.0.y=2|workgroupSizes.0.z=2"
      "-DEXPECTED_REFLECTION_JSON_ARRAY_LENGTHS=resources=7|targetResourceBindings=7|functionConstants=1|workgroupSizes=1"
      "-DEXPECTED_REFLECTION_TARGET_FIELDS=signedCounters.sourceType=iimage2D[IMAGE_COUNT]|signedCounters.metalType=array<texture2d<int, access::read_write>, IMAGE_COUNT>|signedCounters.bindingClass=texture|signedCounters.argumentIndex=1|signedCounters.arraySize=IMAGE_COUNT|signedCounters.arrayElementCount=2|unsignedCounters.metalType=array<texture2d<uint, access::read_write>, IMAGE_COUNT>|unsignedCounters.argumentIndex=3|signedAtlases.metalType=array<texture2d_array<int, access::read_write>, IMAGE_COUNT>|signedAtlases.argumentIndex=5|unsignedAtlases.metalType=array<texture2d_array<uint, access::read_write>, IMAGE_COUNT>|unsignedAtlases.argumentIndex=7"
      "-DEXPECTED_REFLECTION_FEATURE_FIELDS=native-metal-package.kind=backend|MSL.kind=sourceLanguage|metallib.kind=binaryFormat|xcrun-metal.kind=toolchain|xcrun-metallib.kind=toolchain|storage-image.kind=resource|descriptor-array.kind=resource|fixed-array.kind=layout|read-write.kind=storageImage|2d-dimension.kind=storageImage|2d_array-dimension.kind=storageImage|array-dimension.kind=storageImage|r32i-format.kind=storageImage|r32ui-format.kind=storageImage|storage-buffer.kind=resource|nonuniform-descriptor-index.kind=operation|nonuniform-storage-image-descriptor-index.kind=operation|storage-image-read.kind=operation|storage-image-write.kind=operation|storage-image-atomic-add.kind=operation|storage-image-atomic-exchange.kind=operation|storage-image-atomic-min.kind=operation|storage-image-atomic-max.kind=operation|storage-image-atomic-and.kind=operation|storage-image-atomic-or.kind=operation|storage-image-atomic-xor.kind=operation"
      "-DEXPECTED_DIAGNOSTICS_JSON_ARRAY_LENGTHS=diagnostics=0"
      -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
  set(CROSSGL_METAL_FUNCTION_PARAMETER_RESOURCE_ARRAY_SOURCE_SNIPPET [=[float4 sampleFirst(array<texture2d<float>, COUNT> maps, array<sampler, COUNT> samplers) {
  return maps[0].sample(samplers[0], float2(0.5, 0.5), level(0.0));
}

kernel void compute_main(device float4* values [[buffer(0)]], array<texture2d<float>, COUNT> colorMaps [[texture(2)]], array<sampler, COUNT> linearSamplers [[sampler(5)]]) {
  float4 color = sampleFirst(colorMaps, linearSamplers);
  values[0] = color;]=])
  add_test(NAME cglc_build_metal_function_parameter_resource_array_native
    COMMAND ${CMAKE_COMMAND}
      -DCGLC=$<TARGET_FILE:cglc>
      -DINPUT=${CROSSGL_METAL_FUNCTION_PARAMETER_RESOURCE_ARRAY_SHADER}
      -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-metal-function-parameter-resource-array.cglb
      -DEXPECTED_MODULE=MetalFunctionParameterResourceArrayShader
      -DMODE=metal-build
      "-DEXPECTED_METAL_SOURCE_SNIPPET=${CROSSGL_METAL_FUNCTION_PARAMETER_RESOURCE_ARRAY_SOURCE_SNIPPET}"
      "-DEXPECTED_MANIFEST_JSON_FIELDS=schemaVersion=1|target=metal|module=MetalFunctionParameterResourceArrayShader|artifacts.backendSource=backend/metal/MetalFunctionParameterResourceArrayShader.metal|artifacts.intermediate=backend/metal/MetalFunctionParameterResourceArrayShader.air|artifacts.nativeBinary=backend/metal/MetalFunctionParameterResourceArrayShader.metallib"
      "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=metal|module=MetalFunctionParameterResourceArrayShader|nativeBinary=backend/metal/MetalFunctionParameterResourceArrayShader.metallib|functionConstants.0.name=COUNT|functionConstants.0.value=2|resources.0.name=values|resources.0.kind=buffer|resources.0.type=vec4*|resources.1.name=colorMaps|resources.1.kind=texture|resources.1.type=sampler2D[COUNT]|resources.2.name=linearSamplers|resources.2.kind=sampler|resources.2.type=sampler[COUNT]|workgroupSizes.0.entryPoint=compute_main"
      "-DEXPECTED_REFLECTION_JSON_ARRAY_LENGTHS=resources=3|targetResourceBindings=3|functionConstants=1|workgroupSizes=1|manualTextureCompareKernels=0"
      "-DEXPECTED_REFLECTION_TARGET_FIELDS=values.sourceType=vec4*|values.metalType=device float4*|values.bindingClass=buffer|values.argumentIndex=0|values.storageBufferLayout.elementType=vec4|values.storageBufferLayout.layout=metal-device|colorMaps.sourceType=sampler2D[COUNT]|colorMaps.metalType=array<texture2d<float>, COUNT>|colorMaps.bindingClass=texture|colorMaps.argumentIndex=2|colorMaps.arraySize=COUNT|colorMaps.arrayElementCount=2|linearSamplers.sourceType=sampler[COUNT]|linearSamplers.metalType=array<sampler, COUNT>|linearSamplers.bindingClass=sampler|linearSamplers.argumentIndex=5|linearSamplers.arraySize=COUNT|linearSamplers.arrayElementCount=2"
      "-DEXPECTED_REFLECTION_FEATURE_FIELDS=native-metal-package.kind=backend|MSL.kind=sourceLanguage|metallib.kind=binaryFormat|xcrun-metal.kind=toolchain|xcrun-metallib.kind=toolchain|compute-kernel.kind=stage|workgroup-size.kind=execution|storage-buffer.kind=resource|vector-storage-buffer.kind=layout|sampled-texture.kind=resource|sampler-state.kind=resource|fixed-array.kind=layout|descriptor-array.kind=resource|function-parameter-array.kind=array|texture-sample.kind=operation|texture-explicit-lod.kind=operation|index-access.kind=operation|vector-constructor.kind=operation|local-declaration.kind=operation|storage-buffer-write.kind=operation"
      "-DEXPECTED_DIAGNOSTICS_JSON_ARRAY_LENGTHS=diagnostics=0"
      -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
  add_test(NAME cglc_build_metal_function_parameter_array_write_source_package
    COMMAND ${CMAKE_COMMAND}
      -DCGLC=$<TARGET_FILE:cglc>
      -DINPUT=${CMAKE_CURRENT_SOURCE_DIR}/tests/metal/fixtures/MetalFunctionParameterArrayWriteUnsupportedShader.cgl
      -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-metal-function-parameter-array-write-source.cglb
      -DEXPECTED_MODULE=MetalFunctionParameterArrayWriteUnsupportedShader
      -DMODE=metal-build
      "-DEXPECTED_METAL_SOURCE_SNIPPET=weights[0] = 1.0;"
      "-DEXPECTED_MANIFEST_JSON_FIELDS=schemaVersion=1|target=metal|module=MetalFunctionParameterArrayWriteUnsupportedShader|artifacts.backendSource=backend/metal/MetalFunctionParameterArrayWriteUnsupportedShader.metal|artifacts.intermediate=backend/metal/MetalFunctionParameterArrayWriteUnsupportedShader.air|artifacts.nativeBinary=backend/metal/MetalFunctionParameterArrayWriteUnsupportedShader.metallib"
      "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=metal|module=MetalFunctionParameterArrayWriteUnsupportedShader|nativeBinary=backend/metal/MetalFunctionParameterArrayWriteUnsupportedShader.metallib|functionConstants.0.name=COUNT|functionConstants.0.value=2|resources.0.name=particles|resources.0.kind=buffer|resources.0.type=Particle*|resources.0.binding=0|workgroupSizes.0.entryPoint=compute_main"
      "-DEXPECTED_REFLECTION_TARGET_FIELDS=particles.sourceType=Particle*|particles.metalType=device Particle*|particles.bindingClass=buffer|particles.argumentIndex=0|particles.storageBufferLayout.elementType=Particle|particles.storageBufferLayout.layout=metal-device|particles.storageBufferLayout.fields.0.name=weights|particles.storageBufferLayout.fields.0.arrayElementCount=2"
      "-DEXPECTED_REFLECTION_FEATURE_FIELDS=native-metal-package.kind=backend|MSL.kind=sourceLanguage|metallib.kind=binaryFormat|xcrun-metal.kind=toolchain|xcrun-metallib.kind=toolchain|compute-kernel.kind=stage|workgroup-size.kind=execution|storage-buffer.kind=resource|fixed-array.kind=layout|fixed-array-field.kind=layout|index-access.kind=operation|storage-buffer-read.kind=operation|storage-buffer-write.kind=operation"
      "-DEXPECTED_DIAGNOSTICS_JSON_ARRAY_LENGTHS=diagnostics=0"
      -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
  add_test(NAME cglc_build_metal_nested_function_parameter_array_write_source_package
    COMMAND ${CMAKE_COMMAND}
      -DCGLC=$<TARGET_FILE:cglc>
      -DINPUT=${CMAKE_CURRENT_SOURCE_DIR}/tests/metal/fixtures/MetalNestedFunctionParameterArrayWriteUnsupportedShader.cgl
      -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-metal-nested-function-parameter-array-write-source.cglb
      -DEXPECTED_MODULE=MetalNestedFunctionParameterArrayWriteUnsupportedShader
      -DMODE=metal-build
      "-DEXPECTED_METAL_SOURCE_SNIPPET=grid[1][2] = grid[0][0] + 1.0;"
      "-DEXPECTED_MANIFEST_JSON_FIELDS=schemaVersion=1|target=metal|module=MetalNestedFunctionParameterArrayWriteUnsupportedShader|artifacts.backendSource=backend/metal/MetalNestedFunctionParameterArrayWriteUnsupportedShader.metal|artifacts.intermediate=backend/metal/MetalNestedFunctionParameterArrayWriteUnsupportedShader.air|artifacts.nativeBinary=backend/metal/MetalNestedFunctionParameterArrayWriteUnsupportedShader.metallib"
      "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=metal|module=MetalNestedFunctionParameterArrayWriteUnsupportedShader|nativeBinary=backend/metal/MetalNestedFunctionParameterArrayWriteUnsupportedShader.metallib|functionConstants.0.name=ROWS|functionConstants.0.value=2|functionConstants.1.name=COLS|functionConstants.1.value=3|resources.0.name=values|resources.0.kind=buffer|resources.0.type=float*|resources.0.binding=0|workgroupSizes.0.entryPoint=compute_main"
      "-DEXPECTED_REFLECTION_TARGET_FIELDS=values.sourceType=float*|values.metalType=device float*|values.bindingClass=buffer|values.argumentIndex=0|values.storageBufferLayout.elementType=float|values.storageBufferLayout.layout=metal-device"
      "-DEXPECTED_REFLECTION_FEATURE_FIELDS=native-metal-package.kind=backend|MSL.kind=sourceLanguage|metallib.kind=binaryFormat|xcrun-metal.kind=toolchain|xcrun-metallib.kind=toolchain|compute-kernel.kind=stage|workgroup-size.kind=execution|storage-buffer.kind=resource|fixed-array.kind=layout|index-access.kind=operation|scalar-arithmetic.kind=operation|storage-buffer-read.kind=operation|storage-buffer-write.kind=operation"
      "-DEXPECTED_DIAGNOSTICS_JSON_ARRAY_LENGTHS=diagnostics=0"
      -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
  crossgl_label_new_optional_native_tests(metal
    "${CROSSGL_SOURCE_PACKAGE_METAL_NATIVE_TESTS_BEFORE}")
else()
  crossgl_add_optional_native_skip_test(
    NAME cglc_build_metal_source_package_native_tools_unavailable
    TARGET metal
    REQUIRED_VARS CROSSGL_XCRUN CROSSGL_METAL CROSSGL_METALLIB)
endif()
add_test(NAME cglc_build_directx_unsized_storage_buffer_array_source_package
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_STORAGE_BUFFER_UNSIZED_DESCRIPTOR_ARRAY_UNSUPPORTED_SHADER}
    -DTARGET=directx
    -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-directx-unsized-storage-buffer-array.cglb
    -DMODE=source-package-build
    -DEXPECTED_SOURCE=backend/directx/StorageBufferUnsizedDescriptorArrayUnsupportedShader.hlsl
    "-DEXPECTED_SOURCE_SNIPPET=RWStructuredBuffer<float> values[] : register(u0, space0);"
    "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=directx|module=StorageBufferUnsizedDescriptorArrayUnsupportedShader"
    "-DEXPECTED_REFLECTION_TARGET_FIELDS=values.sourceType=float*[]|values.hlslType=RWStructuredBuffer<float>|values.bindingClass=uav|values.descriptorType=UAV|values.arraySize=|values.arrayDimensions.0.kind=runtime"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_build_directx_runtime_texture_resource_array_source_package
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CMAKE_CURRENT_SOURCE_DIR}/tests/directx/fixtures/DirectXRuntimeTextureResourceArrayShader.cgl
    -DTARGET=directx
    -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-directx-runtime-texture-resource-array.cglb
    -DMODE=source-package-build
    -DEXPECTED_SOURCE=backend/directx/DirectXRuntimeTextureResourceArrayShader.hlsl
    "-DEXPECTED_SOURCE_SNIPPET=Texture2D<float4> colorMaps[] : register(t1, space0);"
    "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=directx|module=DirectXRuntimeTextureResourceArrayShader"
    "-DEXPECTED_REFLECTION_TARGET_FIELDS=values.hlslType=RWStructuredBuffer<float4>|colorMaps.sourceType=sampler2D[]|colorMaps.hlslType=Texture2D<float4>|colorMaps.bindingClass=srv|colorMaps.descriptorType=SRV|colorMaps.arraySize=|colorMaps.arrayDimensions.0.kind=runtime|linearSampler.hlslType=SamplerState|linearSampler.bindingClass=sampler"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_build_directx_runtime_texture_resource_array_sampler_source_package
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CMAKE_CURRENT_SOURCE_DIR}/tests/directx/fixtures/DirectXRuntimeTextureSamplerResourceArrayShader.cgl
    -DTARGET=directx
    -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-directx-runtime-texture-resource-array-sampler.cglb
    -DMODE=source-package-build
    -DEXPECTED_SOURCE=backend/directx/DirectXRuntimeTextureSamplerResourceArrayShader.hlsl
    "-DEXPECTED_SOURCE_SNIPPET=colorMaps[0].SampleLevel(linearSamplers[0]"
    "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=directx|module=DirectXRuntimeTextureSamplerResourceArrayShader"
    "-DEXPECTED_REFLECTION_TARGET_FIELDS=values.hlslType=RWStructuredBuffer<float4>|colorMaps.sourceType=sampler2D[]|colorMaps.hlslType=Texture2D<float4>|colorMaps.bindingClass=srv|colorMaps.descriptorType=SRV|colorMaps.arraySize=|colorMaps.arrayDimensions.0.kind=runtime|linearSamplers.sourceType=sampler[]|linearSamplers.hlslType=SamplerState|linearSamplers.bindingClass=sampler|linearSamplers.descriptorType=Sampler|linearSamplers.arraySize=|linearSamplers.arrayDimensions.0.kind=runtime"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_build_directx_runtime_texture_resource_array_sampler_fake_dxc_success
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CMAKE_CURRENT_SOURCE_DIR}/tests/directx/fixtures/DirectXRuntimeTextureSamplerResourceArrayShader.cgl
    -DTARGET=directx
    -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-directx-runtime-texture-resource-array-sampler-fake-dxc.cglb
    -DMODE=source-package-build
    -DTOOLCHAIN_PATH=${CROSSGL_FAKE_DXC_SUCCESS_DIR}
    -DTOOLCHAIN_DISABLE_FALLBACK=ON
    -DEXPECTED_SOURCE=backend/directx/DirectXRuntimeTextureSamplerResourceArrayShader.hlsl
    -DEXPECTED_NATIVE_BINARY=backend/directx/DirectXRuntimeTextureSamplerResourceArrayShader.dxil
    -DEXPECTED_NATIVE_BINARY_STATUS=emitted
    "-DEXPECTED_SOURCE_SNIPPET=colorMaps[0].SampleLevel(linearSamplers[0]"
    "-DEXPECTED_DIAGNOSTICS_JSON_FIELDS=diagnostics.0.severity=note|diagnostics.0.code=directx.source-package-emitted|diagnostics.1.severity=note|diagnostics.1.code=directx.dxil-emitted"
    "-DEXPECTED_DIAGNOSTICS_JSON_FIELD_CONTAINS=diagnostics.0.message=compute=cs_6_0|diagnostics.1.message=compute=cs_6_0"
    "-DEXPECTED_DIAGNOSTICS_JSON_ARRAY_LENGTHS=diagnostics=2"
    -DEXPECTED_TOOL_LOG=${CROSSGL_FAKE_DXC_SUCCESS_DIR}/dxc.log
    "-DEXPECTED_TOOL_LOG_CONTAINS=-T cs_6_0 -E compute_main -Fo"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_build_directx_runtime_texture_resource_array_conflict_planned_failure
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_DIRECTX_RUNTIME_TEXTURE_RESOURCE_ARRAY_CONFLICT_SHADER}
    -DTARGET=directx
    -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-directx-runtime-texture-resource-array-conflict.cglb
    -DMODE=planned-build-failure
    -DEXPECTED_DIAGNOSTIC=directx.unsupported-runtime-resource-array
    ${CROSSGL_SINGLE_PLANNED_DIAGNOSTIC_EXPECTATIONS}
    "-DEXPECTED_DIAGNOSTIC_FIELD_CONTAINS=message=DirectX source package requires fixed-size descriptor arrays|message=detailMaps (texture)|message=maps (texture)|message=per register class"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_build_directx_runtime_uniform_buffer_descriptor_array
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CMAKE_CURRENT_SOURCE_DIR}/tests/directx/fixtures/DirectXRuntimeUniformBufferDescriptorArrayShader.cgl
    -DTARGET=directx
    -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-directx-runtime-uniform-buffer-descriptor-array.cglb
    -DMODE=source-package-build
    -DEXPECTED_SOURCE=backend/directx/DirectXRuntimeUniformBufferDescriptorArrayShader.hlsl
    "-DEXPECTED_SOURCE_SNIPPET=ConstantBuffer<Light> lights[] : register(b0, space0);"
    "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=directx|module=DirectXRuntimeUniformBufferDescriptorArrayShader|nativeBinary=backend/directx/DirectXRuntimeUniformBufferDescriptorArrayShader.dxil|resources.0.name=lights|resources.0.kind=uniform|resources.0.type=Light[]|resources.0.arrayDimensions.0.kind=runtime"
    "-DEXPECTED_REFLECTION_TARGET_FIELDS=lights.stage=compute|lights.entryPoint=compute_main|lights.sourceType=Light[]|lights.hlslType=ConstantBuffer<Light>|lights.addressSpace=constant-buffer|lights.abi=registerBinding|lights.bindingClass=constant-buffer|lights.descriptorType=CBV|lights.argumentIndex=0|lights.set=0|lights.binding=0|lights.arraySize=|lights.arrayDimensions.0.kind=runtime|values.hlslType=RWStructuredBuffer<float4>|values.bindingClass=uav"
    "-DEXPECTED_REFLECTION_FEATURE_FIELDS=hlsl-lowering.kind=backend|native-dxil-package.kind=backend|dxc.kind=toolchain|dxil-validator.kind=validation|compute-kernel.kind=stage|workgroup-size.kind=execution|uniform-buffer.kind=resource|descriptor-array.kind=resource|runtime-array.kind=layout|runtime-descriptor-array.kind=resource|runtime-uniform-descriptor-array.kind=resource|storage-buffer.kind=resource|storage-buffer-write.kind=operation"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_build_directx_runtime_resource_array_source_package
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_RUNTIME_RESOURCE_ARRAY_UNSUPPORTED_SHADER}
    -DTARGET=directx
    -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-directx-runtime-resource-array.cglb
    -DMODE=source-package-build
    -DEXPECTED_SOURCE=backend/directx/RuntimeResourceArrayUnsupportedShader.hlsl
    "-DEXPECTED_SOURCE_SNIPPET=SamplerState linearSamplers[] : register(s2, space0);"
    "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=directx|module=RuntimeResourceArrayUnsupportedShader"
    "-DEXPECTED_REFLECTION_TARGET_FIELDS=values.hlslType=RWStructuredBuffer<float4>|maps.sourceType=sampler2D[]|maps.hlslType=Texture2D<float4>|maps.bindingClass=srv|maps.descriptorType=SRV|maps.arraySize=|maps.arrayDimensions.0.kind=runtime|linearSamplers.sourceType=sampler[]|linearSamplers.hlslType=SamplerState|linearSamplers.bindingClass=sampler|linearSamplers.descriptorType=Sampler|linearSamplers.arraySize=|linearSamplers.arrayDimensions.0.kind=runtime"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_build_opengl_unsized_storage_buffer_array_source_package
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_STORAGE_BUFFER_UNSIZED_DESCRIPTOR_ARRAY_UNSUPPORTED_SHADER}
    -DTARGET=opengl
    -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-opengl-unsized-storage-buffer-array.cglb
    -DMODE=source-package-build
    -DEXPECTED_SOURCE=backend/opengl/StorageBufferUnsizedDescriptorArrayUnsupportedShader.comp.glsl
    "-DEXPECTED_SOURCE_SNIPPET=values_Buffers[0].values[1] = first + 1.0;"
    "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=opengl|module=StorageBufferUnsizedDescriptorArrayUnsupportedShader"
    "-DEXPECTED_REFLECTION_TARGET_FIELDS=values.sourceType=float*[]|values.bindingClass=storage-buffer|values.abi=programResourceBinding|values.arraySize=|values.arrayDimensions.0.kind=runtime|values.storageBufferLayout.elementType=float|values.storageBufferLayout.layout=std430|values.storageBufferLayout.arrayStrideBytes=4"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
if(CROSSGL_HAS_OPENGL_NATIVE_VALIDATOR)
  add_test(NAME cglc_build_opengl_unsized_storage_buffer_array_glsl_validated
    COMMAND ${CMAKE_COMMAND}
      -DCGLC=$<TARGET_FILE:cglc>
      -DINPUT=${CROSSGL_STORAGE_BUFFER_UNSIZED_DESCRIPTOR_ARRAY_UNSUPPORTED_SHADER}
      -DTARGET=opengl
      -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-opengl-unsized-storage-buffer-array-validated.cglb
      -DMODE=source-package-build
      -DEXPECTED_SOURCE=backend/opengl/StorageBufferUnsizedDescriptorArrayUnsupportedShader.comp.glsl
      "-DEXPECTED_SOURCE_SNIPPET=} values_Buffers[];"
      "-DEXPECTED_MANIFEST_JSON_FIELDS=schemaVersion=1|target=opengl|module=StorageBufferUnsizedDescriptorArrayUnsupportedShader|artifacts.backendSource=backend/opengl/StorageBufferUnsizedDescriptorArrayUnsupportedShader.comp.glsl|artifacts.nativeBinary=backend/opengl/StorageBufferUnsizedDescriptorArrayUnsupportedShader.glsl|artifacts.nativeBinaryStatus=validated"
      "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=opengl|module=StorageBufferUnsizedDescriptorArrayUnsupportedShader|nativeBinary=backend/opengl/StorageBufferUnsizedDescriptorArrayUnsupportedShader.glsl"
      "-DEXPECTED_REFLECTION_TARGET_FIELDS=values.sourceType=float*[]|values.bindingClass=storage-buffer|values.arraySize=|values.arrayDimensions.0.kind=runtime|values.storageBufferLayout.layout=std430"
      -DEXPECTED_NATIVE_BINARY=backend/opengl/StorageBufferUnsizedDescriptorArrayUnsupportedShader.glsl
      -DEXPECTED_NATIVE_BINARY_STATUS=validated
      -DEXPECTED_DIAGNOSTIC=opengl.glsl-validated
      -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
  crossgl_label_optional_native_test(
    cglc_build_opengl_unsized_storage_buffer_array_glsl_validated opengl)
endif()
add_test(NAME cglc_build_opengl_runtime_resource_array_planned_failure
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_RUNTIME_RESOURCE_ARRAY_UNSUPPORTED_SHADER}
    -DTARGET=opengl
    -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-opengl-runtime-resource-array.cglb
    -DMODE=planned-build-failure
    -DEXPECTED_DIAGNOSTIC=opengl.unsupported-runtime-resource-array
    ${CROSSGL_SINGLE_PLANNED_DIAGNOSTIC_EXPECTATIONS}
    "-DEXPECTED_DIAGNOSTIC_FIELD_CONTAINS=message=OpenGL source package requires fixed-size descriptor arrays|message=maps (texture)|message=linearSamplers (sampler)"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_build_opengl_runtime_texture_descriptor_array_policy_planned_failure
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_OPENGL_RUNTIME_TEXTURE_DESCRIPTOR_ARRAY_POLICY_SHADER}
    -DTARGET=opengl
    -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-opengl-runtime-texture-descriptor-array-policy.cglb
    -DMODE=planned-build-failure
    -DEXPECTED_DIAGNOSTIC=opengl.unsupported-runtime-resource-array
    ${CROSSGL_SINGLE_PLANNED_DIAGNOSTIC_EXPECTATIONS}
    "-DEXPECTED_DIAGNOSTIC_FIELD_CONTAINS=message=OpenGL source package requires fixed-size descriptor arrays|message=maps (texture)"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_build_opengl_function_parameter_struct_array_source_package
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CMAKE_CURRENT_SOURCE_DIR}/tests/opengl/fixtures/OpenGLFunctionParameterStructArrayUnsupportedShader.cgl
    -DTARGET=opengl
    -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-opengl-function-parameter-struct-array.cglb
    -DMODE=source-package-build
    -DEXPECTED_SOURCE=backend/opengl/OpenGLFunctionParameterStructArrayUnsupportedShader.comp.glsl
    "-DEXPECTED_SOURCE_SNIPPET=float firstWeight(Payload payloads[COUNT])"
    "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=opengl|module=OpenGLFunctionParameterStructArrayUnsupportedShader"
    "-DEXPECTED_REFLECTION_TARGET_FIELDS=particles.sourceType=Particle*|particles.bindingClass=storage-buffer|particles.storageBufferLayout.elementType=Particle|particles.storageBufferLayout.layout=std430|particles.storageBufferLayout.arrayStrideBytes=48|particles.storageBufferLayout.fields.0.name=payloads|particles.storageBufferLayout.fields.0.arrayElementCount=2|particles.storageBufferLayout.fields.0.arrayStrideBytes=16"
    "-DEXPECTED_REFLECTION_FEATURE_FIELDS=${CROSSGL_OPENGL_STRUCT_STORAGE_AGGREGATE_ARRAY_FIELD_FEATURE_FIELDS}|function-parameter-array.kind=array"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
set(CROSSGL_OPENGL_FUNCTION_PARAMETER_RESOURCE_ARRAY_SOURCE_SNIPPET [=[vec4 sampleFirst(texture2D maps[COUNT], sampler samplers[COUNT]) {
  return textureLod(sampler2D(maps[0], samplers[0]), vec2(0.5, 0.5), 0.0);
}

void main() {
  vec4 color = sampleFirst(colorMaps, linearSamplers);
  values[0] = color;]=])
add_test(NAME cglc_build_opengl_function_parameter_resource_array_source_package
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_OPENGL_FUNCTION_PARAMETER_RESOURCE_ARRAY_SHADER}
    -DTARGET=opengl
    -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-opengl-function-parameter-resource-array.cglb
    -DMODE=source-package-build
    -DEXPECTED_SOURCE=backend/opengl/OpenGLFunctionParameterResourceArrayShader.comp.glsl
    "-DEXPECTED_SOURCE_SNIPPET=${CROSSGL_OPENGL_FUNCTION_PARAMETER_RESOURCE_ARRAY_SOURCE_SNIPPET}"
    "-DEXPECTED_MANIFEST_JSON_FIELDS=schemaVersion=1|target=opengl|module=OpenGLFunctionParameterResourceArrayShader|artifacts.backendSource=backend/opengl/OpenGLFunctionParameterResourceArrayShader.comp.glsl|artifacts.nativeBinary=backend/opengl/OpenGLFunctionParameterResourceArrayShader.glsl|artifacts.nativeBinaryStatus=planned"
    "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=opengl|module=OpenGLFunctionParameterResourceArrayShader|nativeBinary=backend/opengl/OpenGLFunctionParameterResourceArrayShader.glsl|functionConstants.0.name=COUNT|functionConstants.0.value=2|resources.0.name=values|resources.0.kind=buffer|resources.0.type=vec4*|resources.1.name=colorMaps|resources.1.kind=texture|resources.1.type=sampler2D[COUNT]|resources.2.name=linearSamplers|resources.2.kind=sampler|resources.2.type=sampler[COUNT]|workgroupSizes.0.entryPoint=compute_main"
    "-DEXPECTED_REFLECTION_JSON_ARRAY_LENGTHS=resources=3|targetResourceBindings=3|functionConstants=1|workgroupSizes=1"
    "-DEXPECTED_REFLECTION_TARGET_FIELDS=values.bindingClass=storage-buffer|colorMaps.bindingClass=texture|colorMaps.arraySize=COUNT|colorMaps.arrayElementCount=2|linearSamplers.bindingClass=sampler|linearSamplers.arraySize=COUNT|linearSamplers.arrayElementCount=2"
    "-DEXPECTED_REFLECTION_FEATURE_FIELDS=glsl-lowering.kind=backend|native-glsl-package.kind=backend|compute-kernel.kind=stage|workgroup-size.kind=execution|storage-buffer.kind=resource|vector-storage-buffer.kind=layout|sampled-texture.kind=resource|sampler-state.kind=resource|fixed-array.kind=layout|descriptor-array.kind=resource|function-parameter-array.kind=array|texture-sample.kind=operation|index-access.kind=operation|vector-constructor.kind=operation|storage-buffer-write.kind=operation"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_build_opengl_local_function_parameter_array_source_package
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_OPENGL_LOCAL_FUNCTION_PARAMETER_ARRAY_SHADER}
    -DTARGET=opengl
    -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-opengl-local-function-parameter-array.cglb
    -DMODE=source-package-build
    -DEXPECTED_SOURCE=backend/opengl/OpenGLLocalFunctionParameterArrayShader.comp.glsl
    "-DEXPECTED_SOURCE_SNIPPET=weights[1] = weights[0] + 2.0;"
    "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=opengl|module=OpenGLLocalFunctionParameterArrayShader"
    "-DEXPECTED_REFLECTION_FEATURE_FIELDS=${CROSSGL_OPENGL_PARAM_ARRAY_LOCAL_FEATURE_FIELDS}"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_build_opengl_folded_local_function_parameter_array_source_package
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_OPENGL_FOLDED_LOCAL_FUNCTION_PARAMETER_ARRAY_SHADER}
    -DTARGET=opengl
    -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-opengl-folded-local-function-parameter-array.cglb
    -DMODE=source-package-build
    -DEXPECTED_SOURCE=backend/opengl/OpenGLFoldedLocalFunctionParameterArrayShader.comp.glsl
    "-DEXPECTED_SOURCE_SNIPPET=float sampleWeight(float weights[COUNT], int index)"
    "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=opengl|module=OpenGLFoldedLocalFunctionParameterArrayShader"
    "-DEXPECTED_REFLECTION_FEATURE_FIELDS=${CROSSGL_OPENGL_PARAM_ARRAY_LOCAL_FEATURE_FIELDS}"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_build_opengl_nested_local_function_parameter_array_source_package
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_OPENGL_NESTED_LOCAL_FUNCTION_PARAMETER_ARRAY_SHADER}
    -DTARGET=opengl
    -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-opengl-nested-local-function-parameter-array.cglb
    -DMODE=source-package-build
    -DEXPECTED_SOURCE=backend/opengl/OpenGLNestedLocalFunctionParameterArrayShader.comp.glsl
    "-DEXPECTED_SOURCE_SNIPPET=float readGrid(float grid[ROWS][COLS])"
    "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=opengl|module=OpenGLNestedLocalFunctionParameterArrayShader"
    "-DEXPECTED_REFLECTION_FEATURE_FIELDS=${CROSSGL_OPENGL_PARAM_ARRAY_LOCAL_FEATURE_FIELDS}"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_build_opengl_dynamic_nested_local_function_parameter_array_source_package
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_OPENGL_DYNAMIC_NESTED_LOCAL_FUNCTION_PARAMETER_ARRAY_UNSUPPORTED_SHADER}
    -DTARGET=opengl
    -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-opengl-dynamic-nested-local-function-parameter-array.cglb
    -DMODE=source-package-build
    -DEXPECTED_SOURCE=backend/opengl/OpenGLDynamicNestedLocalFunctionParameterArrayUnsupportedShader.comp.glsl
    "-DEXPECTED_SOURCE_SNIPPET=return grid[row][2];"
    "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=opengl|module=OpenGLDynamicNestedLocalFunctionParameterArrayUnsupportedShader"
    "-DEXPECTED_REFLECTION_TARGET_FIELDS=values.sourceType=float*|values.bindingClass=storage-buffer|values.argumentIndex=0|values.storageBufferLayout.elementType=float|values.storageBufferLayout.arrayStrideBytes=4|values.storageBufferLayout.layout=std430"
    "-DEXPECTED_REFLECTION_FEATURE_FIELDS=${CROSSGL_OPENGL_PARAM_ARRAY_DYNAMIC_FEATURE_FIELDS}"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_build_opengl_local_function_parameter_array_write_source_package
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_OPENGL_LOCAL_FUNCTION_PARAMETER_ARRAY_WRITE_SHADER}
    -DTARGET=opengl
    -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-opengl-local-function-parameter-array-write.cglb
    -DMODE=source-package-build
    -DEXPECTED_SOURCE=backend/opengl/OpenGLLocalFunctionParameterArrayWriteShader.comp.glsl
    "-DEXPECTED_SOURCE_SNIPPET=values[1] = rewriteLocal(weights, 1);"
    "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=opengl|module=OpenGLLocalFunctionParameterArrayWriteShader|functionConstants.0.name=COUNT|functionConstants.0.value=3|resources.0.name=values|resources.0.kind=buffer|resources.0.type=float*|resources.0.binding=0|workgroupSizes.0.entryPoint=compute_main|workgroupSizes.0.x=1|workgroupSizes.0.y=1|workgroupSizes.0.z=1"
    "-DEXPECTED_REFLECTION_TARGET_FIELDS=values.sourceType=float*|values.bindingClass=storage-buffer|values.argumentIndex=0|values.storageBufferLayout.elementType=float|values.storageBufferLayout.arrayStrideBytes=4|values.storageBufferLayout.layout=std430"
    "-DEXPECTED_REFLECTION_FEATURE_FIELDS=${CROSSGL_OPENGL_PARAM_ARRAY_WRITE_LOCAL_FEATURE_FIELDS}"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
set(CROSSGL_OPENGL_FUNCTION_PARAMETER_ARRAY_WRITE_SOURCE_SNIPPET [=[float crossgl_param_array_writeback_0_rewriteWeight_weights[COUNT];
  for (int crossgl_param_array_writeback_0_rewriteWeight_weights_i = 0; crossgl_param_array_writeback_0_rewriteWeight_weights_i < COUNT; ++crossgl_param_array_writeback_0_rewriteWeight_weights_i) {
    crossgl_param_array_writeback_0_rewriteWeight_weights[crossgl_param_array_writeback_0_rewriteWeight_weights_i] = particles[0].weights[crossgl_param_array_writeback_0_rewriteWeight_weights_i];
  }
  float value = rewriteWeight(crossgl_param_array_writeback_0_rewriteWeight_weights);
  for (int crossgl_param_array_writeback_0_rewriteWeight_weights_i = 0; crossgl_param_array_writeback_0_rewriteWeight_weights_i < COUNT; ++crossgl_param_array_writeback_0_rewriteWeight_weights_i) {
    particles[0].weights[crossgl_param_array_writeback_0_rewriteWeight_weights_i] = crossgl_param_array_writeback_0_rewriteWeight_weights[crossgl_param_array_writeback_0_rewriteWeight_weights_i];
  }]=])
add_test(NAME cglc_build_opengl_function_parameter_array_write_source_package
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_OPENGL_FUNCTION_PARAMETER_ARRAY_WRITE_SHADER}
    -DTARGET=opengl
    -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-opengl-function-parameter-array-write.cglb
    -DMODE=source-package-build
    -DEXPECTED_SOURCE=backend/opengl/OpenGLFunctionParameterArrayWriteShader.comp.glsl
    "-DEXPECTED_SOURCE_SNIPPET=${CROSSGL_OPENGL_FUNCTION_PARAMETER_ARRAY_WRITE_SOURCE_SNIPPET}"
    "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=opengl|module=OpenGLFunctionParameterArrayWriteShader|functionConstants.0.name=COUNT|functionConstants.0.value=2|resources.0.name=particles|resources.0.kind=buffer|resources.0.type=Particle*|resources.0.binding=0|workgroupSizes.0.entryPoint=compute_main|workgroupSizes.0.x=1|workgroupSizes.0.y=1|workgroupSizes.0.z=1"
    "-DEXPECTED_REFLECTION_TARGET_FIELDS=particles.sourceType=Particle*|particles.bindingClass=storage-buffer|particles.argumentIndex=0|particles.storageBufferLayout.elementType=Particle|particles.storageBufferLayout.arrayStrideBytes=8|particles.storageBufferLayout.layout=std430|particles.storageBufferLayout.fields.0.name=weights|particles.storageBufferLayout.fields.0.arrayElementCount=2|particles.storageBufferLayout.fields.0.arrayStrideBytes=4"
    "-DEXPECTED_REFLECTION_FEATURE_FIELDS=${CROSSGL_OPENGL_PARAM_ARRAY_WRITE_RESOURCE_FEATURE_FIELDS}"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_build_opengl_forwarded_function_parameter_array_write_planned_failure
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_OPENGL_FORWARDED_FUNCTION_PARAMETER_ARRAY_WRITE_UNSUPPORTED_SHADER}
    -DTARGET=opengl
    -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-opengl-forwarded-function-parameter-array-write.cglb
    -DMODE=planned-build-failure
    -DEXPECTED_DIAGNOSTIC=opengl.unsupported-function-parameter-array-write
    ${CROSSGL_SINGLE_PLANNED_DIAGNOSTIC_EXPECTATIONS}
    "-DEXPECTED_DIAGNOSTIC_FIELD_CONTAINS=message=rewrite.values|message=forwarded helper parameter"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_build_opengl_aliased_function_parameter_array_write_planned_failure
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_OPENGL_ALIASED_FUNCTION_PARAMETER_ARRAY_WRITE_UNSUPPORTED_SHADER}
    -DTARGET=opengl
    -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-opengl-aliased-function-parameter-array-write.cglb
    -DMODE=planned-build-failure
    -DEXPECTED_DIAGNOSTIC=opengl.unsupported-function-parameter-array-write
    ${CROSSGL_SINGLE_PLANNED_DIAGNOSTIC_EXPECTATIONS}
    "-DEXPECTED_DIAGNOSTIC_FIELD_CONTAINS=message=blendAliased.left|message=aliased helper array"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_build_opengl_nested_function_parameter_array_write_source_package
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_OPENGL_NESTED_FUNCTION_PARAMETER_ARRAY_WRITE_UNSUPPORTED_SHADER}
    -DTARGET=opengl
    -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-opengl-nested-function-parameter-array-write.cglb
    -DMODE=source-package-build
    -DEXPECTED_SOURCE=backend/opengl/OpenGLNestedFunctionParameterArrayWriteUnsupportedShader.comp.glsl
    "-DEXPECTED_SOURCE_SNIPPET=grid[1][2] = grid[0][0] + 1.0;"
    "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=opengl|module=OpenGLNestedFunctionParameterArrayWriteUnsupportedShader|functionConstants.0.name=ROWS|functionConstants.0.value=2|functionConstants.1.name=COLS|functionConstants.1.value=3|resources.0.name=values|resources.0.kind=buffer|resources.0.type=float*|resources.0.binding=0|workgroupSizes.0.entryPoint=compute_main|workgroupSizes.0.x=1|workgroupSizes.0.y=1|workgroupSizes.0.z=1"
    "-DEXPECTED_REFLECTION_TARGET_FIELDS=values.sourceType=float*|values.bindingClass=storage-buffer|values.argumentIndex=0|values.storageBufferLayout.elementType=float|values.storageBufferLayout.arrayStrideBytes=4|values.storageBufferLayout.layout=std430"
    "-DEXPECTED_REFLECTION_FEATURE_FIELDS=${CROSSGL_OPENGL_PARAM_ARRAY_WRITE_LOCAL_FEATURE_FIELDS}"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
set(CROSSGL_OPENGL_NESTED_STORAGE_FUNCTION_PARAMETER_ARRAY_WRITE_SOURCE_SNIPPET [=[float crossgl_param_array_writeback_0_rewriteGrid_grid[ROWS][COLS];
  for (int crossgl_param_array_writeback_0_rewriteGrid_grid_i0 = 0; crossgl_param_array_writeback_0_rewriteGrid_grid_i0 < ROWS; ++crossgl_param_array_writeback_0_rewriteGrid_grid_i0) {
    for (int crossgl_param_array_writeback_0_rewriteGrid_grid_i1 = 0; crossgl_param_array_writeback_0_rewriteGrid_grid_i1 < COLS; ++crossgl_param_array_writeback_0_rewriteGrid_grid_i1) {
      crossgl_param_array_writeback_0_rewriteGrid_grid[crossgl_param_array_writeback_0_rewriteGrid_grid_i0][crossgl_param_array_writeback_0_rewriteGrid_grid_i1] = tiles[0].grid[crossgl_param_array_writeback_0_rewriteGrid_grid_i0][crossgl_param_array_writeback_0_rewriteGrid_grid_i1];
    }
  }
  float selected = rewriteGrid(crossgl_param_array_writeback_0_rewriteGrid_grid);
  for (int crossgl_param_array_writeback_0_rewriteGrid_grid_i0 = 0; crossgl_param_array_writeback_0_rewriteGrid_grid_i0 < ROWS; ++crossgl_param_array_writeback_0_rewriteGrid_grid_i0) {
    for (int crossgl_param_array_writeback_0_rewriteGrid_grid_i1 = 0; crossgl_param_array_writeback_0_rewriteGrid_grid_i1 < COLS; ++crossgl_param_array_writeback_0_rewriteGrid_grid_i1) {
      tiles[0].grid[crossgl_param_array_writeback_0_rewriteGrid_grid_i0][crossgl_param_array_writeback_0_rewriteGrid_grid_i1] = crossgl_param_array_writeback_0_rewriteGrid_grid[crossgl_param_array_writeback_0_rewriteGrid_grid_i0][crossgl_param_array_writeback_0_rewriteGrid_grid_i1];
    }
  }]=])
add_test(NAME cglc_build_opengl_nested_storage_function_parameter_array_write_source_package
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_OPENGL_NESTED_STORAGE_FUNCTION_PARAMETER_ARRAY_WRITE_SHADER}
    -DTARGET=opengl
    -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-opengl-nested-storage-function-parameter-array-write.cglb
    -DMODE=source-package-build
    -DEXPECTED_SOURCE=backend/opengl/OpenGLNestedStorageFunctionParameterArrayWriteShader.comp.glsl
    "-DEXPECTED_SOURCE_SNIPPET=${CROSSGL_OPENGL_NESTED_STORAGE_FUNCTION_PARAMETER_ARRAY_WRITE_SOURCE_SNIPPET}"
    "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=opengl|module=OpenGLNestedStorageFunctionParameterArrayWriteShader|functionConstants.0.name=ROWS|functionConstants.0.value=2|functionConstants.1.name=COLS|functionConstants.1.value=3|resources.0.name=tiles|resources.0.kind=buffer|resources.0.type=Tile*|resources.0.binding=0|workgroupSizes.0.entryPoint=compute_main|workgroupSizes.0.x=1|workgroupSizes.0.y=1|workgroupSizes.0.z=1"
    "-DEXPECTED_REFLECTION_TARGET_FIELDS=tiles.sourceType=Tile*|tiles.bindingClass=storage-buffer|tiles.argumentIndex=0|tiles.storageBufferLayout.elementType=Tile|tiles.storageBufferLayout.layout=std430|tiles.storageBufferLayout.fields.0.name=grid|tiles.storageBufferLayout.fields.0.type=float[ROWS][COLS]|tiles.storageBufferLayout.fields.0.arrayElementCount=6|tiles.storageBufferLayout.fields.0.arrayDimensions.0.source=ROWS|tiles.storageBufferLayout.fields.0.arrayDimensions.0.elementCount=2|tiles.storageBufferLayout.fields.0.arrayDimensions.1.source=COLS|tiles.storageBufferLayout.fields.0.arrayDimensions.1.elementCount=3"
    "-DEXPECTED_REFLECTION_FEATURE_FIELDS=${CROSSGL_OPENGL_PARAM_ARRAY_WRITE_RESOURCE_FEATURE_FIELDS}|fixed-nested-arrays.kind=array"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_build_metal_unsized_storage_buffer_array_planned_failure
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_METAL_STORAGE_BUFFER_ARRAY_UNSUPPORTED_SHADER}
    -DTARGET=metal
    -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-metal-unsized-storage-buffer-array.cglb
    -DMODE=planned-build-failure
    ${CROSSGL_TARGET_NOT_IMPLEMENTED_DIAGNOSTIC_EXPECTATIONS}
    "-DEXPECTED_DIAGNOSTICS_JSON_FIELDS=diagnostics.0.target=metal"
    "-DEXPECTED_DIAGNOSTIC_ARRAY_CONTAINS=missingCapabilities=metal.backend.native-metal-package|missingCapabilities=metal.diagnostic.metal.unsupported-storage-buffer-array"
    "-DEXPECTED_DIAGNOSTIC_FIELD_CONTAINS=message=target 'metal' cannot build a package for this module|message=metal.backend.native-metal-package|message=metal.diagnostic.metal.unsupported-storage-buffer-array"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_build_metal_runtime_resource_array_planned_failure
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_RUNTIME_RESOURCE_ARRAY_UNSUPPORTED_SHADER}
    -DTARGET=metal
    -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-metal-runtime-resource-array.cglb
    -DMODE=planned-build-failure
    ${CROSSGL_TARGET_NOT_IMPLEMENTED_DIAGNOSTIC_EXPECTATIONS}
    "-DEXPECTED_DIAGNOSTICS_JSON_FIELDS=diagnostics.0.target=metal"
    "-DEXPECTED_DIAGNOSTIC_ARRAY_CONTAINS=missingCapabilities=metal.backend.native-metal-package|missingCapabilities=metal.diagnostic.metal.unsupported-runtime-resource-array"
    "-DEXPECTED_DIAGNOSTIC_FIELD_CONTAINS=message=target 'metal' cannot build a package for this module|message=metal.backend.native-metal-package|message=metal.diagnostic.metal.unsupported-runtime-resource-array"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_build_metal_runtime_texture_descriptor_array_policy_planned_failure
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_METAL_RUNTIME_TEXTURE_DESCRIPTOR_ARRAY_POLICY_SHADER}
    -DTARGET=metal
    -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-metal-runtime-texture-descriptor-array-policy.cglb
    -DMODE=planned-build-failure
    ${CROSSGL_TARGET_NOT_IMPLEMENTED_DIAGNOSTIC_EXPECTATIONS}
    "-DEXPECTED_DIAGNOSTICS_JSON_FIELDS=diagnostics.0.target=metal"
    "-DEXPECTED_DIAGNOSTIC_ARRAY_CONTAINS=missingCapabilities=metal.backend.native-metal-package|missingCapabilities=metal.diagnostic.metal.unsupported-runtime-resource-array"
    "-DEXPECTED_DIAGNOSTIC_FIELD_CONTAINS=message=target 'metal' cannot build a package for this module|message=metal.backend.native-metal-package|message=metal.diagnostic.metal.unsupported-runtime-resource-array"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_build_vulkan_runtime_texture_descriptor_array_conflict_source_planned_failure
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_VULKAN_RUNTIME_TEXTURE_DESCRIPTOR_ARRAY_CONFLICT_SHADER}
    -DTARGET=vulkan
    -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-vulkan-runtime-texture-descriptor-array-conflict-source.cglb
    -DMODE=planned-build-failure
    ${CROSSGL_TARGET_NOT_IMPLEMENTED_DIAGNOSTIC_EXPECTATIONS}
    "-DEXPECTED_DIAGNOSTICS_JSON_FIELDS=diagnostics.0.target=vulkan"
    "-DEXPECTED_DIAGNOSTIC_ARRAY_CONTAINS=missingCapabilities=vulkan.backend.vulkan-prototype-package|missingCapabilities=vulkan.diagnostic.vulkan.prototype-unsupported-runtime-resource-array"
    "-DEXPECTED_DIAGNOSTIC_FIELD_CONTAINS=message=target 'vulkan' cannot build a package for this module|message=vulkan.backend.vulkan-prototype-package|message=vulkan.diagnostic.vulkan.prototype-unsupported-runtime-resource-array"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_build_metal_storage_buffer_out_of_range_descriptor_array_planned_failure
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_METAL_STORAGE_BUFFER_OUT_OF_RANGE_DESCRIPTOR_ARRAY_UNSUPPORTED_SHADER}
    -DTARGET=metal
    -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-metal-storage-buffer-out-of-range-descriptor-array.cglb
    -DMODE=planned-build-failure
    ${CROSSGL_TARGET_NOT_IMPLEMENTED_DIAGNOSTIC_EXPECTATIONS}
    "-DEXPECTED_DIAGNOSTICS_JSON_FIELDS=diagnostics.0.target=metal"
    "-DEXPECTED_DIAGNOSTIC_ARRAY_CONTAINS=missingCapabilities=metal.backend.native-metal-package|missingCapabilities=metal.diagnostic.metal.unsupported-storage-buffer-array-index"
    "-DEXPECTED_DIAGNOSTIC_FIELD_CONTAINS=message=target 'metal' cannot build a package for this module|message=metal.backend.native-metal-package|message=metal.diagnostic.metal.unsupported-storage-buffer-array-index"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_dump_metal_texture_only_nonuniform_descriptor_array_sample_backend
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_TEXTURE_ONLY_NONUNIFORM_DESCRIPTOR_ARRAY_SAMPLE_SHADER}
    -DTARGET=metal
    -DMODE=dump-backend
    "-DMUST_CONTAIN=colorMaps\\[descriptor\\]\\.sample\\(linearSampler"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_dump_metal_sampler_only_nonuniform_descriptor_array_sample_backend
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_SAMPLER_ONLY_NONUNIFORM_DESCRIPTOR_ARRAY_SAMPLE_SHADER}
    -DTARGET=metal
    -DMODE=dump-backend
    "-DMUST_CONTAIN=colorMap\\.sample\\(linearSamplers\\[descriptor\\]"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_dump_metal_texture_only_nonuniform_compare_descriptor_array_backend
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_TEXTURE_ONLY_NONUNIFORM_COMPARE_DESCRIPTOR_ARRAY_SHADER}
    -DTARGET=metal
    -DMODE=dump-backend
    "-DMUST_CONTAIN=shadowMaps\\[descriptor\\]\\.sample_compare\\(shadowSampler"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_dump_metal_sampler_only_nonuniform_compare_descriptor_array_backend
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_SAMPLER_ONLY_NONUNIFORM_COMPARE_DESCRIPTOR_ARRAY_SHADER}
    -DTARGET=metal
    -DMODE=dump-backend
    "-DMUST_CONTAIN=shadowMap\\.sample_compare\\(shadowSamplers\\[descriptor\\]"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_dump_metal_texture_only_nonuniform_compare_descriptor_array_lod_backend
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_TEXTURE_ONLY_NONUNIFORM_COMPARE_DESCRIPTOR_ARRAY_LOD_SHADER}
    -DTARGET=metal
    -DMODE=dump-backend
    "-DMUST_CONTAIN=shadowMaps\\[descriptor\\]\\.sample_compare\\(shadowSampler"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_dump_metal_sampler_only_nonuniform_compare_descriptor_array_lod_backend
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_SAMPLER_ONLY_NONUNIFORM_COMPARE_DESCRIPTOR_ARRAY_LOD_SHADER}
    -DTARGET=metal
    -DMODE=dump-backend
    "-DMUST_CONTAIN=shadowMap\\.sample_compare\\(shadowSamplers\\[descriptor\\]"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_dump_metal_texture_only_nonuniform_compare_lod_manual_descriptor_array_backend
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_TEXTURE_ONLY_NONUNIFORM_COMPARE_LOD_MANUAL_DESCRIPTOR_ARRAY_SHADER}
    -DTARGET=metal
    -DMODE=dump-backend
    "-DMUST_CONTAIN=shadowAtlases\\[descriptor\\]\\.sample\\(rawShadowSampler"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_dump_metal_sampler_only_nonuniform_compare_lod_manual_descriptor_array_backend
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_SAMPLER_ONLY_NONUNIFORM_COMPARE_LOD_MANUAL_DESCRIPTOR_ARRAY_SHADER}
    -DTARGET=metal
    -DMODE=dump-backend
    "-DMUST_CONTAIN=shadowAtlas\\.sample\\(rawShadowSamplers\\[descriptor\\]"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_dump_metal_texture_cube_family_only_nonuniform_compare_lod_manual_descriptor_array_backend
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_TEXTURE_CUBE_FAMILY_ONLY_NONUNIFORM_COMPARE_LOD_MANUAL_DESCRIPTOR_ARRAY_SHADER}
    -DTARGET=metal
    -DMODE=dump-backend
    "-DMUST_CONTAIN=shadowCubes\\[descriptor\\]\\.sample\\(rawShadowSampler"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_dump_metal_sampler_cube_family_only_nonuniform_compare_lod_manual_descriptor_array_backend
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_SAMPLER_CUBE_FAMILY_ONLY_NONUNIFORM_COMPARE_LOD_MANUAL_DESCRIPTOR_ARRAY_SHADER}
    -DTARGET=metal
    -DMODE=dump-backend
    "-DMUST_CONTAIN=shadowCube\\.sample\\(rawShadowSamplers\\[descriptor\\]"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_dump_metal_texture_family_only_nonuniform_compare_descriptor_array_backend
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_TEXTURE_FAMILY_ONLY_NONUNIFORM_COMPARE_DESCRIPTOR_ARRAY_SHADER}
    -DTARGET=metal
    -DMODE=dump-backend
    "-DMUST_CONTAIN=shadowAtlases\\[descriptor\\]\\.sample_compare\\(shadowSampler"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_dump_metal_sampler_family_only_nonuniform_compare_descriptor_array_backend
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_SAMPLER_FAMILY_ONLY_NONUNIFORM_COMPARE_DESCRIPTOR_ARRAY_SHADER}
    -DTARGET=metal
    -DMODE=dump-backend
    "-DMUST_CONTAIN=shadowAtlas\\.sample_compare\\(shadowSamplers\\[descriptor\\]"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_dump_metal_texture_compare_nonuniform_descriptor_array_backend
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_TEXTURE_COMPARE_NONUNIFORM_DESCRIPTOR_ARRAY_SHADER}
    -DTARGET=metal
    -DMODE=dump-backend
    "-DMUST_CONTAIN=shadowMaps\\[descriptor\\]\\.sample_compare\\(shadowSamplers\\[descriptor\\]"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_dump_metal_texture_compare_nonuniform_descriptor_array_lod_backend
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_TEXTURE_COMPARE_NONUNIFORM_DESCRIPTOR_ARRAY_LOD_SHADER}
    -DTARGET=metal
    -DMODE=dump-backend
    "-DMUST_CONTAIN=shadowMaps\\[descriptor\\]\\.sample_compare\\(shadowSamplers\\[descriptor\\]"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_dump_metal_texture_compare_lod_manual_nonuniform_descriptor_array_backend
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_TEXTURE_COMPARE_LOD_MANUAL_NONUNIFORM_DESCRIPTOR_ARRAY_SHADER}
    -DTARGET=metal
    -DMODE=dump-backend
    "-DMUST_CONTAIN=shadowAtlases\\[descriptor\\]\\.sample\\(rawShadowSamplers\\[descriptor\\]"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_dump_metal_texture_cube_family_compare_lod_manual_nonuniform_descriptor_array_backend
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_TEXTURE_CUBE_FAMILY_COMPARE_LOD_MANUAL_NONUNIFORM_DESCRIPTOR_ARRAY_SHADER}
    -DTARGET=metal
    -DMODE=dump-backend
    "-DMUST_CONTAIN=shadowCubes\\[descriptor\\]\\.sample\\(rawShadowSamplers\\[descriptor\\]"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_build_vulkan_runtime_array_non_final_planned_failure
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_RUNTIME_ARRAY_NON_FINAL_SHADER}
    -DTARGET=vulkan
    -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-vulkan-runtime-array-non-final.cglb
    -DMODE=planned-build-failure
    -DEXPECTED_DIAGNOSTIC=opt.hir-storage-buffer-runtime-array-field
    "-DEXPECTED_DIAGNOSTICS_JSON_ARRAY_LENGTHS=diagnostics=1"
    "-DEXPECTED_DIAGNOSTIC_FIELD_CONTAINS=message=payloads.values|message=direct final field"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_build_vulkan_runtime_array_nested_planned_failure
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_RUNTIME_ARRAY_NESTED_SHADER}
    -DTARGET=vulkan
    -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-vulkan-runtime-array-nested.cglb
    -DMODE=planned-build-failure
    -DEXPECTED_DIAGNOSTIC=opt.hir-storage-buffer-runtime-array-field
    "-DEXPECTED_DIAGNOSTICS_JSON_ARRAY_LENGTHS=diagnostics=1"
    "-DEXPECTED_DIAGNOSTIC_FIELD_CONTAINS=message=payloads.tail.values|message=direct final field"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_build_metal_runtime_array_non_final_planned_failure
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_RUNTIME_ARRAY_NON_FINAL_SHADER}
    -DTARGET=metal
    -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-metal-runtime-array-non-final.cglb
    -DMODE=planned-build-failure
    -DEXPECTED_DIAGNOSTIC=opt.hir-storage-buffer-runtime-array-field
    "-DEXPECTED_DIAGNOSTICS_JSON_ARRAY_LENGTHS=diagnostics=1"
    "-DEXPECTED_DIAGNOSTIC_FIELD_CONTAINS=message=payloads.values|message=direct final field"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_build_metal_runtime_array_nested_planned_failure
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_RUNTIME_ARRAY_NESTED_SHADER}
    -DTARGET=metal
    -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-metal-runtime-array-nested.cglb
    -DMODE=planned-build-failure
    -DEXPECTED_DIAGNOSTIC=opt.hir-storage-buffer-runtime-array-field
    "-DEXPECTED_DIAGNOSTICS_JSON_ARRAY_LENGTHS=diagnostics=1"
    "-DEXPECTED_DIAGNOSTIC_FIELD_CONTAINS=message=payloads.tail.values|message=direct final field"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_build_metal_runtime_array_dynamic_outer_index_planned_failure
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_RUNTIME_ARRAY_DYNAMIC_OUTER_INDEX_UNSUPPORTED_SHADER}
    -DTARGET=metal
    -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-metal-runtime-array-dynamic-outer-index.cglb
    -DMODE=planned-build-failure
    ${CROSSGL_TARGET_NOT_IMPLEMENTED_DIAGNOSTIC_EXPECTATIONS}
    "-DEXPECTED_DIAGNOSTICS_JSON_FIELDS=diagnostics.0.target=metal"
    "-DEXPECTED_DIAGNOSTIC_ARRAY_CONTAINS=missingCapabilities=metal.backend.native-metal-package|missingCapabilities=metal.diagnostic.metal.unsupported-runtime-array-block-index"
    "-DEXPECTED_DIAGNOSTIC_FIELD_CONTAINS=message=target 'metal' cannot build a package for this module|message=metal.backend.native-metal-package|message=metal.diagnostic.metal.unsupported-runtime-array-block-index"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_build_opengl_runtime_array_source_package
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_RUNTIME_ARRAY_SHADER}
    -DTARGET=opengl
    -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-opengl-runtime-array.cglb
    -DMODE=source-package-build
    -DEXPECTED_SOURCE=backend/opengl/RuntimeArrayShader.comp.glsl
    "-DEXPECTED_SOURCE_SNIPPET=payloads.values[1] = payloads.count;"
    "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=opengl|module=RuntimeArrayShader"
    "-DEXPECTED_REFLECTION_TARGET_FIELDS=payloads.sourceType=RuntimePayload*|payloads.bindingClass=storage-buffer|payloads.storageBufferLayout.elementType=RuntimePayload|payloads.storageBufferLayout.layout=std430"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_build_opengl_runtime_tail_folded_zero_block_index_source_package
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_OPENGL_RUNTIME_TAIL_FOLDED_ZERO_BLOCK_INDEX_SHADER}
    -DTARGET=opengl
    -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-opengl-runtime-tail-folded-zero-block-index.cglb
    -DMODE=source-package-build
    -DEXPECTED_SOURCE=backend/opengl/OpenGLRuntimeTailFoldedZeroBlockIndexShader.comp.glsl
    "-DEXPECTED_SOURCE_SNIPPET=payloads.values[1] = first + vec4(payloads.count, 0.0, 0.0, 0.0);"
    "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=opengl|module=OpenGLRuntimeTailFoldedZeroBlockIndexShader"
    "-DEXPECTED_REFLECTION_TARGET_FIELDS=payloads.sourceType=RuntimePayload*|payloads.bindingClass=storage-buffer|payloads.storageBufferLayout.elementType=RuntimePayload|payloads.storageBufferLayout.layout=std430|outputs.sourceType=vec4*|outputs.bindingClass=storage-buffer|outputs.storageBufferLayout.elementType=vec4|outputs.storageBufferLayout.layout=std430"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_build_opengl_runtime_vector_array_source_package
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_RUNTIME_VECTOR_ARRAY_SHADER}
    -DTARGET=opengl
    -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-opengl-runtime-vector-array.cglb
    -DMODE=source-package-build
    -DEXPECTED_SOURCE=backend/opengl/RuntimeVectorArrayShader.comp.glsl
    "-DEXPECTED_SOURCE_SNIPPET=vec4 first = payloads.values[0];"
    "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=opengl|module=RuntimeVectorArrayShader"
    "-DEXPECTED_REFLECTION_TARGET_FIELDS=payloads.sourceType=RuntimeVectorPayload*|payloads.bindingClass=storage-buffer|payloads.storageBufferLayout.elementType=RuntimeVectorPayload|payloads.storageBufferLayout.layout=std430"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_build_opengl_runtime_struct_array_source_package
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_RUNTIME_STRUCT_ARRAY_SHADER}
    -DTARGET=opengl
    -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-opengl-runtime-struct-array.cglb
    -DMODE=source-package-build
    -DEXPECTED_SOURCE=backend/opengl/RuntimeStructArrayShader.comp.glsl
    "-DEXPECTED_SOURCE_SNIPPET=TailParticle particles[];"
    "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=opengl|module=RuntimeStructArrayShader"
    "-DEXPECTED_REFLECTION_TARGET_FIELDS=payloads.sourceType=RuntimeStructPayload*|payloads.bindingClass=storage-buffer|payloads.storageBufferLayout.elementType=RuntimeStructPayload|payloads.storageBufferLayout.layout=std430"
    "-DEXPECTED_REFLECTION_FEATURE_FIELDS=${CROSSGL_OPENGL_RUNTIME_STRUCT_ARRAY_FEATURE_FIELDS}"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_build_opengl_runtime_array_non_final_planned_failure
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_RUNTIME_ARRAY_NON_FINAL_SHADER}
    -DTARGET=opengl
    -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-opengl-runtime-array-non-final.cglb
    -DMODE=planned-build-failure
    -DEXPECTED_DIAGNOSTIC=opt.hir-storage-buffer-runtime-array-field
    "-DEXPECTED_DIAGNOSTICS_JSON_ARRAY_LENGTHS=diagnostics=1"
    "-DEXPECTED_DIAGNOSTIC_FIELD_CONTAINS=message=payloads.values|message=direct final field"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_build_opengl_runtime_array_nested_planned_failure
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_RUNTIME_ARRAY_NESTED_SHADER}
    -DTARGET=opengl
    -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-opengl-runtime-array-nested.cglb
    -DMODE=planned-build-failure
    -DEXPECTED_DIAGNOSTIC=opt.hir-storage-buffer-runtime-array-field
    "-DEXPECTED_DIAGNOSTICS_JSON_ARRAY_LENGTHS=diagnostics=1"
    "-DEXPECTED_DIAGNOSTIC_FIELD_CONTAINS=message=payloads.tail.values|message=direct final field"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_build_opengl_runtime_array_dynamic_outer_index_planned_failure
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_RUNTIME_ARRAY_DYNAMIC_OUTER_INDEX_UNSUPPORTED_SHADER}
    -DTARGET=opengl
    -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-opengl-runtime-array-dynamic-outer-index.cglb
    -DMODE=planned-build-failure
    -DEXPECTED_DIAGNOSTIC=opengl.unsupported-runtime-array-block-index
    ${CROSSGL_SINGLE_PLANNED_DIAGNOSTIC_EXPECTATIONS}
    "-DEXPECTED_DIAGNOSTIC_FIELD_CONTAINS=message=payloads|message=index the runtime array field instead"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_build_opengl_runtime_array_nonzero_outer_index_planned_failure
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CMAKE_CURRENT_SOURCE_DIR}/tests/opengl/fixtures/OpenGLRuntimeArrayNonzeroOuterIndexShader.cgl
    -DTARGET=opengl
    -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-opengl-runtime-array-nonzero-outer-index.cglb
    -DMODE=planned-build-failure
    -DEXPECTED_DIAGNOSTIC=opengl.unsupported-runtime-array-block-index
    ${CROSSGL_SINGLE_PLANNED_DIAGNOSTIC_EXPECTATIONS}
    "-DEXPECTED_DIAGNOSTIC_FIELD_CONTAINS=message=payloads|message=index the runtime array field instead"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_build_directx_texture_array_dimensions_source_package
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_TEXTURE_ARRAY_DIMENSION_SHADER}
    -DTARGET=directx
    -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-directx-texture-array-dimensions.cglb
    -DMODE=source-package-build
    -DEXPECTED_SOURCE=backend/directx/TextureArrayDimensionShader.hlsl
    "-DEXPECTED_SOURCE_SNIPPET=TextureCubeArray<float4> environmentMaps"
    "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=directx|module=TextureArrayDimensionShader"
    "-DEXPECTED_REFLECTION_TARGET_FIELDS=atlas.sourceType=sampler2DArray|atlas.hlslType=Texture2DArray<float4>|atlas.bindingClass=srv|atlas.descriptorType=SRV|environmentMaps.sourceType=samplerCubeArray|environmentMaps.hlslType=TextureCubeArray<float4>|environmentMaps.bindingClass=srv|environmentMaps.descriptorType=SRV|linearSampler.hlslType=SamplerState|linearSampler.bindingClass=sampler"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_build_opengl_texture_array_dimensions_source_package
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_TEXTURE_ARRAY_DIMENSION_SHADER}
    -DTARGET=opengl
    -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-opengl-texture-array-dimensions.cglb
    -DMODE=source-package-build
    -DEXPECTED_SOURCE=backend/opengl/TextureArrayDimensionShader.comp.glsl
    "-DEXPECTED_SOURCE_SNIPPET=textureLod(sampler2DArray(atlas, linearSampler)"
    "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=opengl|module=TextureArrayDimensionShader"
    "-DEXPECTED_REFLECTION_TARGET_FIELDS=atlas.sourceType=sampler2DArray|atlas.bindingClass=texture|atlas.abi=programResourceBinding|environmentMaps.sourceType=samplerCubeArray|environmentMaps.bindingClass=texture|linearSampler.bindingClass=sampler|values.storageBufferLayout.layout=std430"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_build_directx_integer_texture_array_sampler_lod_source_package
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_VULKAN_INTEGER_TEXTURE_ARRAY_SAMPLER_LOD_SHADER}
    -DTARGET=directx
    -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-directx-integer-texture-array-sampler-lod.cglb
    -DMODE=source-package-build
    -DEXPECTED_SOURCE=backend/directx/VulkanIntegerTextureArraySamplerLodShader.hlsl
    "-DEXPECTED_SOURCE_SNIPPET=Texture2DArray<int4> labelAtlas"
    "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=directx|module=VulkanIntegerTextureArraySamplerLodShader"
    "-DEXPECTED_REFLECTION_TARGET_FIELDS=labelAtlas.sourceType=isampler2DArray|labelAtlas.hlslType=Texture2DArray<int4>|labelAtlas.bindingClass=srv|labelAtlas.descriptorType=SRV|maskCubes.sourceType=usamplerCubeArray|maskCubes.hlslType=TextureCubeArray<uint4>|maskCubes.bindingClass=srv|labelSampler.hlslType=SamplerState|maskSampler.hlslType=SamplerState"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_build_opengl_integer_texture_array_sampler_lod_source_package
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_VULKAN_INTEGER_TEXTURE_ARRAY_SAMPLER_LOD_SHADER}
    -DTARGET=opengl
    -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-opengl-integer-texture-array-sampler-lod.cglb
    -DMODE=source-package-build
    -DEXPECTED_SOURCE=backend/opengl/VulkanIntegerTextureArraySamplerLodShader.comp.glsl
    "-DEXPECTED_SOURCE_SNIPPET=textureLod(isampler2DArray(labelAtlas, labelSampler)"
    "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=opengl|module=VulkanIntegerTextureArraySamplerLodShader"
    "-DEXPECTED_REFLECTION_TARGET_FIELDS=labelAtlas.sourceType=isampler2DArray|labelAtlas.bindingClass=texture|maskCubes.sourceType=usamplerCubeArray|maskCubes.bindingClass=texture|labelSampler.bindingClass=sampler|maskSampler.bindingClass=sampler|values.storageBufferLayout.elementType=ivec4|masks.storageBufferLayout.elementType=uvec4"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_build_directx_texture_descriptor_array_source_package
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_TEXTURE_DESCRIPTOR_ARRAY_SHADER}
    -DTARGET=directx
    -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-directx-texture-descriptor-array.cglb
    -DMODE=source-package-build
    -DEXPECTED_SOURCE=backend/directx/TextureDescriptorArrayShader.hlsl
    "-DEXPECTED_SOURCE_SNIPPET=Texture2D<float4> colorMaps[TEXTURE_COUNT] : register(t2, space0);"
    "-DEXPECTED_MANIFEST_JSON_FIELDS=schemaVersion=1|target=directx|module=TextureDescriptorArrayShader|artifacts.backendSource=backend/directx/TextureDescriptorArrayShader.hlsl|artifacts.nativeBinary=backend/directx/TextureDescriptorArrayShader.dxil"
    "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=directx|module=TextureDescriptorArrayShader|nativeBinary=backend/directx/TextureDescriptorArrayShader.dxil|manualTextureCompareKernelSummary.totalCount=0"
    "-DEXPECTED_REFLECTION_JSON_ARRAY_LENGTHS=resources=1|targetResourceBindings=1|manualTextureCompareKernels=0|workgroupSizes=1"
    "-DEXPECTED_REFLECTION_TARGET_FIELDS=colorMaps.stage=compute|colorMaps.entryPoint=compute_main|colorMaps.sourceType=sampler2D[TEXTURE_COUNT]|colorMaps.hlslType=Texture2D<float4>|colorMaps.addressSpace=shader-resource|colorMaps.abi=registerBinding|colorMaps.bindingClass=srv|colorMaps.descriptorType=SRV|colorMaps.argumentIndex=2|colorMaps.set=0|colorMaps.binding=2|colorMaps.arraySize=TEXTURE_COUNT|colorMaps.arrayElementCount=2"
    "-DEXPECTED_REFLECTION_FEATURE_FIELDS=hlsl-lowering.kind=backend|compute-kernel.kind=stage|workgroup-size.kind=execution|sampled-texture.kind=resource|fixed-array.kind=layout|descriptor-array.kind=resource"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_build_opengl_texture_descriptor_array_source_package
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_TEXTURE_DESCRIPTOR_ARRAY_SHADER}
    -DTARGET=opengl
    -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-opengl-texture-descriptor-array.cglb
    -DMODE=source-package-build
    -DEXPECTED_SOURCE=backend/opengl/TextureDescriptorArrayShader.comp.glsl
    "-DEXPECTED_SOURCE_SNIPPET=uniform texture2D colorMaps[TEXTURE_COUNT]"
    "-DEXPECTED_MANIFEST_JSON_FIELDS=schemaVersion=1|target=opengl|module=TextureDescriptorArrayShader|artifacts.nativeBinaryStatus=planned"
    "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=opengl|module=TextureDescriptorArrayShader|manualTextureCompareKernelSummary.totalCount=0"
    "-DEXPECTED_REFLECTION_JSON_ARRAY_LENGTHS=resources=1|targetResourceBindings=1|manualTextureCompareKernels=0"
    "-DEXPECTED_REFLECTION_TARGET_FIELDS=colorMaps.sourceType=sampler2D[TEXTURE_COUNT]|colorMaps.bindingClass=texture|colorMaps.abi=programResourceBinding|colorMaps.argumentIndex=2|colorMaps.set=0|colorMaps.binding=2|colorMaps.arraySize=TEXTURE_COUNT|colorMaps.arrayElementCount=2|colorMaps.arrayDimensions.0.source=TEXTURE_COUNT|colorMaps.arrayDimensions.0.kind=fixed|colorMaps.arrayDimensions.0.elementCount=2"
    "-DEXPECTED_REFLECTION_FEATURE_FIELDS=sampled-texture.kind=resource|fixed-array.kind=layout|descriptor-array.kind=resource"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_build_directx_sampler_descriptor_array_source_package
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_SAMPLER_DESCRIPTOR_ARRAY_SHADER}
    -DTARGET=directx
    -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-directx-sampler-descriptor-array.cglb
    -DMODE=source-package-build
    -DEXPECTED_SOURCE=backend/directx/SamplerDescriptorArrayShader.hlsl
    "-DEXPECTED_SOURCE_SNIPPET=SamplerState linearSamplers[SAMPLER_COUNT] : register(s5, space0);"
    "-DEXPECTED_MANIFEST_JSON_FIELDS=schemaVersion=1|target=directx|module=SamplerDescriptorArrayShader|artifacts.backendSource=backend/directx/SamplerDescriptorArrayShader.hlsl|artifacts.nativeBinary=backend/directx/SamplerDescriptorArrayShader.dxil"
    "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=directx|module=SamplerDescriptorArrayShader|nativeBinary=backend/directx/SamplerDescriptorArrayShader.dxil|manualTextureCompareKernelSummary.totalCount=0"
    "-DEXPECTED_REFLECTION_JSON_ARRAY_LENGTHS=resources=1|targetResourceBindings=1|manualTextureCompareKernels=0|workgroupSizes=1"
    "-DEXPECTED_REFLECTION_TARGET_FIELDS=linearSamplers.stage=compute|linearSamplers.entryPoint=compute_main|linearSamplers.sourceType=sampler[SAMPLER_COUNT]|linearSamplers.hlslType=SamplerState|linearSamplers.addressSpace=sampler|linearSamplers.abi=registerBinding|linearSamplers.bindingClass=sampler|linearSamplers.descriptorType=Sampler|linearSamplers.argumentIndex=5|linearSamplers.set=0|linearSamplers.binding=5|linearSamplers.arraySize=SAMPLER_COUNT|linearSamplers.arrayElementCount=2"
    "-DEXPECTED_REFLECTION_FEATURE_FIELDS=hlsl-lowering.kind=backend|compute-kernel.kind=stage|workgroup-size.kind=execution|sampler-state.kind=resource|fixed-array.kind=layout|descriptor-array.kind=resource"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_build_opengl_sampler_descriptor_array_source_package
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_SAMPLER_DESCRIPTOR_ARRAY_SHADER}
    -DTARGET=opengl
    -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-opengl-sampler-descriptor-array.cglb
    -DMODE=source-package-build
    -DEXPECTED_SOURCE=backend/opengl/SamplerDescriptorArrayShader.comp.glsl
    "-DEXPECTED_SOURCE_SNIPPET=uniform sampler linearSamplers[SAMPLER_COUNT]"
    "-DEXPECTED_MANIFEST_JSON_FIELDS=schemaVersion=1|target=opengl|module=SamplerDescriptorArrayShader|artifacts.nativeBinaryStatus=planned"
    "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=opengl|module=SamplerDescriptorArrayShader|manualTextureCompareKernelSummary.totalCount=0"
    "-DEXPECTED_REFLECTION_JSON_ARRAY_LENGTHS=resources=1|targetResourceBindings=1|manualTextureCompareKernels=0"
    "-DEXPECTED_REFLECTION_TARGET_FIELDS=linearSamplers.sourceType=sampler[SAMPLER_COUNT]|linearSamplers.bindingClass=sampler|linearSamplers.abi=programResourceBinding|linearSamplers.argumentIndex=5|linearSamplers.set=0|linearSamplers.binding=5|linearSamplers.arraySize=SAMPLER_COUNT|linearSamplers.arrayElementCount=2|linearSamplers.arrayDimensions.0.source=SAMPLER_COUNT|linearSamplers.arrayDimensions.0.kind=fixed|linearSamplers.arrayDimensions.0.elementCount=2"
    "-DEXPECTED_REFLECTION_FEATURE_FIELDS=sampler-state.kind=resource|fixed-array.kind=layout|descriptor-array.kind=resource"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_build_directx_texture_only_descriptor_array_sample_source_package
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_TEXTURE_ONLY_DESCRIPTOR_ARRAY_SAMPLE_SHADER}
    -DTARGET=directx
    -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-directx-texture-only-descriptor-array-sample.cglb
    -DMODE=source-package-build
    -DEXPECTED_SOURCE=backend/directx/TextureOnlyDescriptorArraySampleShader.hlsl
    "-DEXPECTED_SOURCE_SNIPPET=colorMaps[1].SampleLevel(linearSampler"
    "-DEXPECTED_MANIFEST_JSON_FIELDS=schemaVersion=1|target=directx|module=TextureOnlyDescriptorArraySampleShader|artifacts.backendSource=backend/directx/TextureOnlyDescriptorArraySampleShader.hlsl|artifacts.nativeBinary=backend/directx/TextureOnlyDescriptorArraySampleShader.dxil"
    "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=directx|module=TextureOnlyDescriptorArraySampleShader|nativeBinary=backend/directx/TextureOnlyDescriptorArraySampleShader.dxil|manualTextureCompareKernelSummary.totalCount=0"
    "-DEXPECTED_REFLECTION_JSON_ARRAY_LENGTHS=resources=3|targetResourceBindings=3|manualTextureCompareKernels=0|workgroupSizes=1"
    "-DEXPECTED_REFLECTION_TARGET_FIELDS=values.hlslType=RWStructuredBuffer<float4>|values.bindingClass=uav|values.descriptorType=UAV|colorMaps.sourceType=sampler2D[TEXTURE_COUNT]|colorMaps.hlslType=Texture2D<float4>|colorMaps.addressSpace=shader-resource|colorMaps.abi=registerBinding|colorMaps.bindingClass=srv|colorMaps.descriptorType=SRV|colorMaps.argumentIndex=2|colorMaps.arraySize=TEXTURE_COUNT|colorMaps.arrayElementCount=2|linearSampler.sourceType=sampler|linearSampler.hlslType=SamplerState|linearSampler.addressSpace=sampler|linearSampler.abi=registerBinding|linearSampler.bindingClass=sampler|linearSampler.descriptorType=Sampler|linearSampler.argumentIndex=5"
    "-DEXPECTED_REFLECTION_FEATURE_FIELDS=hlsl-lowering.kind=backend|compute-kernel.kind=stage|workgroup-size.kind=execution|storage-buffer.kind=resource|vector-storage-buffer.kind=layout|sampled-texture.kind=resource|fixed-array.kind=layout|descriptor-array.kind=resource|sampler-state.kind=resource|texture-sample.kind=operation|texture-explicit-lod.kind=operation|index-access.kind=operation|storage-buffer-write.kind=operation"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_build_opengl_texture_only_descriptor_array_sample_source_package
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_TEXTURE_ONLY_DESCRIPTOR_ARRAY_SAMPLE_SHADER}
    -DTARGET=opengl
    -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-opengl-texture-only-descriptor-array-sample.cglb
    -DMODE=source-package-build
    -DEXPECTED_SOURCE=backend/opengl/TextureOnlyDescriptorArraySampleShader.comp.glsl
    "-DEXPECTED_SOURCE_SNIPPET=textureLod(sampler2D(colorMaps[1], linearSampler)"
    "-DEXPECTED_MANIFEST_JSON_FIELDS=schemaVersion=1|target=opengl|module=TextureOnlyDescriptorArraySampleShader|artifacts.nativeBinaryStatus=planned"
    "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=opengl|module=TextureOnlyDescriptorArraySampleShader|manualTextureCompareKernelSummary.totalCount=0"
    "-DEXPECTED_REFLECTION_JSON_ARRAY_LENGTHS=resources=3|targetResourceBindings=3|manualTextureCompareKernels=0"
    "-DEXPECTED_REFLECTION_TARGET_FIELDS=colorMaps.sourceType=sampler2D[TEXTURE_COUNT]|colorMaps.bindingClass=texture|colorMaps.argumentIndex=2|colorMaps.arraySize=TEXTURE_COUNT|colorMaps.arrayElementCount=2|colorMaps.arrayDimensions.0.elementCount=2|linearSampler.bindingClass=sampler|linearSampler.argumentIndex=5|linearSampler.sourceType=sampler|values.storageBufferLayout.layout=std430|values.storageBufferLayout.elementType=vec4"
    "-DEXPECTED_REFLECTION_FEATURE_FIELDS=sampled-texture.kind=resource|sampler-state.kind=resource|descriptor-array.kind=resource|texture-sample.kind=operation|texture-explicit-lod.kind=operation|index-access.kind=operation|storage-buffer-write.kind=operation"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_build_directx_sampler_only_descriptor_array_sample_source_package
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_SAMPLER_ONLY_DESCRIPTOR_ARRAY_SAMPLE_SHADER}
    -DTARGET=directx
    -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-directx-sampler-only-descriptor-array-sample.cglb
    -DMODE=source-package-build
    -DEXPECTED_SOURCE=backend/directx/SamplerOnlyDescriptorArraySampleShader.hlsl
    "-DEXPECTED_SOURCE_SNIPPET=colorMap.SampleLevel(linearSamplers[1]"
    "-DEXPECTED_MANIFEST_JSON_FIELDS=schemaVersion=1|target=directx|module=SamplerOnlyDescriptorArraySampleShader|artifacts.backendSource=backend/directx/SamplerOnlyDescriptorArraySampleShader.hlsl|artifacts.nativeBinary=backend/directx/SamplerOnlyDescriptorArraySampleShader.dxil"
    "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=directx|module=SamplerOnlyDescriptorArraySampleShader|nativeBinary=backend/directx/SamplerOnlyDescriptorArraySampleShader.dxil|manualTextureCompareKernelSummary.totalCount=0"
    "-DEXPECTED_REFLECTION_JSON_ARRAY_LENGTHS=resources=3|targetResourceBindings=3|manualTextureCompareKernels=0|workgroupSizes=1"
    "-DEXPECTED_REFLECTION_TARGET_FIELDS=values.hlslType=RWStructuredBuffer<float4>|values.bindingClass=uav|values.descriptorType=UAV|colorMap.sourceType=sampler2D|colorMap.hlslType=Texture2D<float4>|colorMap.addressSpace=shader-resource|colorMap.abi=registerBinding|colorMap.bindingClass=srv|colorMap.descriptorType=SRV|colorMap.argumentIndex=2|linearSamplers.sourceType=sampler[SAMPLER_COUNT]|linearSamplers.hlslType=SamplerState|linearSamplers.addressSpace=sampler|linearSamplers.abi=registerBinding|linearSamplers.bindingClass=sampler|linearSamplers.descriptorType=Sampler|linearSamplers.argumentIndex=5|linearSamplers.arraySize=SAMPLER_COUNT|linearSamplers.arrayElementCount=2"
    "-DEXPECTED_REFLECTION_FEATURE_FIELDS=hlsl-lowering.kind=backend|compute-kernel.kind=stage|workgroup-size.kind=execution|storage-buffer.kind=resource|vector-storage-buffer.kind=layout|sampled-texture.kind=resource|sampler-state.kind=resource|fixed-array.kind=layout|descriptor-array.kind=resource|texture-sample.kind=operation|texture-explicit-lod.kind=operation|index-access.kind=operation|storage-buffer-write.kind=operation"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_build_opengl_sampler_only_descriptor_array_sample_source_package
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_SAMPLER_ONLY_DESCRIPTOR_ARRAY_SAMPLE_SHADER}
    -DTARGET=opengl
    -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-opengl-sampler-only-descriptor-array-sample.cglb
    -DMODE=source-package-build
    -DEXPECTED_SOURCE=backend/opengl/SamplerOnlyDescriptorArraySampleShader.comp.glsl
    "-DEXPECTED_SOURCE_SNIPPET=textureLod(sampler2D(colorMap, linearSamplers[1])"
    "-DEXPECTED_MANIFEST_JSON_FIELDS=schemaVersion=1|target=opengl|module=SamplerOnlyDescriptorArraySampleShader|artifacts.nativeBinaryStatus=planned"
    "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=opengl|module=SamplerOnlyDescriptorArraySampleShader|manualTextureCompareKernelSummary.totalCount=0"
    "-DEXPECTED_REFLECTION_JSON_ARRAY_LENGTHS=resources=3|targetResourceBindings=3|manualTextureCompareKernels=0"
    "-DEXPECTED_REFLECTION_TARGET_FIELDS=colorMap.sourceType=sampler2D|colorMap.bindingClass=texture|colorMap.argumentIndex=2|linearSamplers.sourceType=sampler[SAMPLER_COUNT]|linearSamplers.bindingClass=sampler|linearSamplers.argumentIndex=5|linearSamplers.arraySize=SAMPLER_COUNT|linearSamplers.arrayElementCount=2|linearSamplers.arrayDimensions.0.elementCount=2|values.storageBufferLayout.layout=std430|values.storageBufferLayout.elementType=vec4"
    "-DEXPECTED_REFLECTION_FEATURE_FIELDS=sampled-texture.kind=resource|sampler-state.kind=resource|descriptor-array.kind=resource|texture-sample.kind=operation|texture-explicit-lod.kind=operation|index-access.kind=operation|storage-buffer-write.kind=operation"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_build_directx_texture_only_nonuniform_descriptor_array_sample_source_package
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_TEXTURE_ONLY_NONUNIFORM_DESCRIPTOR_ARRAY_SAMPLE_SHADER}
    -DTARGET=directx
    -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-directx-texture-only-nonuniform-descriptor-array-sample.cglb
    -DMODE=source-package-build
    -DEXPECTED_SOURCE=backend/directx/TextureOnlyNonUniformDescriptorArraySampleShader.hlsl
    "-DEXPECTED_SOURCE_SNIPPET=colorMaps[NonUniformResourceIndex(descriptor)].SampleLevel(linearSampler"
    "-DEXPECTED_REFLECTION_FEATURE_FIELDS=nonuniform-descriptor-index.kind=operation|NonUniformResourceIndex.kind=intrinsic"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_build_opengl_texture_only_nonuniform_descriptor_array_sample_source_package
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_TEXTURE_ONLY_NONUNIFORM_DESCRIPTOR_ARRAY_SAMPLE_SHADER}
    -DTARGET=opengl
    -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-opengl-texture-only-nonuniform-descriptor-array-sample.cglb
    -DMODE=source-package-build
    -DEXPECTED_SOURCE=backend/opengl/TextureOnlyNonUniformDescriptorArraySampleShader.comp.glsl
    "-DEXPECTED_SOURCE_SNIPPET=textureLod(sampler2D(colorMaps[nonuniformEXT(descriptor)], linearSampler)"
    "-DEXPECTED_REFLECTION_FEATURE_FIELDS=nonuniform-descriptor-index.kind=operation|GL_EXT_nonuniform_qualifier.kind=extension"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_build_directx_sampler_only_nonuniform_descriptor_array_sample_source_package
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_SAMPLER_ONLY_NONUNIFORM_DESCRIPTOR_ARRAY_SAMPLE_SHADER}
    -DTARGET=directx
    -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-directx-sampler-only-nonuniform-descriptor-array-sample.cglb
    -DMODE=source-package-build
    -DEXPECTED_SOURCE=backend/directx/SamplerOnlyNonUniformDescriptorArraySampleShader.hlsl
    "-DEXPECTED_SOURCE_SNIPPET=colorMap.SampleLevel(linearSamplers[NonUniformResourceIndex(descriptor)]"
    "-DEXPECTED_REFLECTION_FEATURE_FIELDS=nonuniform-descriptor-index.kind=operation|NonUniformResourceIndex.kind=intrinsic"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_build_opengl_sampler_only_nonuniform_descriptor_array_sample_source_package
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_SAMPLER_ONLY_NONUNIFORM_DESCRIPTOR_ARRAY_SAMPLE_SHADER}
    -DTARGET=opengl
    -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-opengl-sampler-only-nonuniform-descriptor-array-sample.cglb
    -DMODE=source-package-build
    -DEXPECTED_SOURCE=backend/opengl/SamplerOnlyNonUniformDescriptorArraySampleShader.comp.glsl
    "-DEXPECTED_SOURCE_SNIPPET=textureLod(sampler2D(colorMap, linearSamplers[nonuniformEXT(descriptor)])"
    "-DEXPECTED_REFLECTION_FEATURE_FIELDS=nonuniform-descriptor-index.kind=operation|GL_EXT_nonuniform_qualifier.kind=extension"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_build_directx_texture_only_nonuniform_compare_descriptor_array_source_package
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_TEXTURE_ONLY_NONUNIFORM_COMPARE_DESCRIPTOR_ARRAY_SHADER}
    -DTARGET=directx
    -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-directx-texture-only-nonuniform-compare-descriptor-array.cglb
    -DMODE=source-package-build
    -DEXPECTED_SOURCE=backend/directx/TextureOnlyNonUniformCompareDescriptorArrayShader.hlsl
    "-DEXPECTED_SOURCE_SNIPPET=shadowMaps[NonUniformResourceIndex(descriptor)].SampleCmpLevelZero(shadowSampler"
    "-DEXPECTED_REFLECTION_FEATURE_FIELDS=nonuniform-descriptor-index.kind=operation|NonUniformResourceIndex.kind=intrinsic"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_build_opengl_texture_only_nonuniform_compare_descriptor_array_source_package
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_TEXTURE_ONLY_NONUNIFORM_COMPARE_DESCRIPTOR_ARRAY_SHADER}
    -DTARGET=opengl
    -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-opengl-texture-only-nonuniform-compare-descriptor-array.cglb
    -DMODE=source-package-build
    -DEXPECTED_SOURCE=backend/opengl/TextureOnlyNonUniformCompareDescriptorArrayShader.comp.glsl
    "-DEXPECTED_SOURCE_SNIPPET=sampler2DShadow(shadowMaps[nonuniformEXT(descriptor)], shadowSampler)"
    "-DEXPECTED_REFLECTION_FEATURE_FIELDS=nonuniform-descriptor-index.kind=operation|GL_EXT_nonuniform_qualifier.kind=extension"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_build_directx_sampler_only_nonuniform_compare_descriptor_array_source_package
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_SAMPLER_ONLY_NONUNIFORM_COMPARE_DESCRIPTOR_ARRAY_SHADER}
    -DTARGET=directx
    -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-directx-sampler-only-nonuniform-compare-descriptor-array.cglb
    -DMODE=source-package-build
    -DEXPECTED_SOURCE=backend/directx/SamplerOnlyNonUniformCompareDescriptorArrayShader.hlsl
    "-DEXPECTED_SOURCE_SNIPPET=shadowMap.SampleCmpLevelZero(shadowSamplers[NonUniformResourceIndex(descriptor)]"
    "-DEXPECTED_REFLECTION_FEATURE_FIELDS=nonuniform-descriptor-index.kind=operation|NonUniformResourceIndex.kind=intrinsic"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_build_opengl_sampler_only_nonuniform_compare_descriptor_array_source_package
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_SAMPLER_ONLY_NONUNIFORM_COMPARE_DESCRIPTOR_ARRAY_SHADER}
    -DTARGET=opengl
    -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-opengl-sampler-only-nonuniform-compare-descriptor-array.cglb
    -DMODE=source-package-build
    -DEXPECTED_SOURCE=backend/opengl/SamplerOnlyNonUniformCompareDescriptorArrayShader.comp.glsl
    "-DEXPECTED_SOURCE_SNIPPET=sampler2DShadow(shadowMap, shadowSamplers[nonuniformEXT(descriptor)])"
    "-DEXPECTED_REFLECTION_FEATURE_FIELDS=nonuniform-descriptor-index.kind=operation|GL_EXT_nonuniform_qualifier.kind=extension"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_build_directx_texture_only_nonuniform_compare_descriptor_array_lod_source_package
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_TEXTURE_ONLY_NONUNIFORM_COMPARE_DESCRIPTOR_ARRAY_LOD_SHADER}
    -DTARGET=directx
    -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-directx-texture-only-nonuniform-compare-descriptor-array-lod.cglb
    -DMODE=source-package-build
    -DEXPECTED_SOURCE=backend/directx/TextureOnlyNonUniformCompareDescriptorArrayLodShader.hlsl
    "-DEXPECTED_SOURCE_SNIPPET=shadowMaps[NonUniformResourceIndex(descriptor)].SampleCmpLevel(shadowSampler"
    "-DEXPECTED_REFLECTION_FEATURE_FIELDS=nonuniform-descriptor-index.kind=operation|NonUniformResourceIndex.kind=intrinsic"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_build_opengl_texture_only_nonuniform_compare_descriptor_array_lod_source_package
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_TEXTURE_ONLY_NONUNIFORM_COMPARE_DESCRIPTOR_ARRAY_LOD_SHADER}
    -DTARGET=opengl
    -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-opengl-texture-only-nonuniform-compare-descriptor-array-lod.cglb
    -DMODE=source-package-build
    -DEXPECTED_SOURCE=backend/opengl/TextureOnlyNonUniformCompareDescriptorArrayLodShader.comp.glsl
    "-DEXPECTED_SOURCE_SNIPPET=textureLod(sampler2DShadow(shadowMaps[nonuniformEXT(descriptor)], shadowSampler)"
    "-DEXPECTED_REFLECTION_FEATURE_FIELDS=nonuniform-descriptor-index.kind=operation|GL_EXT_nonuniform_qualifier.kind=extension"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_build_directx_sampler_only_nonuniform_compare_descriptor_array_lod_source_package
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_SAMPLER_ONLY_NONUNIFORM_COMPARE_DESCRIPTOR_ARRAY_LOD_SHADER}
    -DTARGET=directx
    -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-directx-sampler-only-nonuniform-compare-descriptor-array-lod.cglb
    -DMODE=source-package-build
    -DEXPECTED_SOURCE=backend/directx/SamplerOnlyNonUniformCompareDescriptorArrayLodShader.hlsl
    "-DEXPECTED_SOURCE_SNIPPET=shadowMap.SampleCmpLevel(shadowSamplers[NonUniformResourceIndex(descriptor)]"
    "-DEXPECTED_REFLECTION_FEATURE_FIELDS=nonuniform-descriptor-index.kind=operation|NonUniformResourceIndex.kind=intrinsic"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_build_opengl_sampler_only_nonuniform_compare_descriptor_array_lod_source_package
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_SAMPLER_ONLY_NONUNIFORM_COMPARE_DESCRIPTOR_ARRAY_LOD_SHADER}
    -DTARGET=opengl
    -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-opengl-sampler-only-nonuniform-compare-descriptor-array-lod.cglb
    -DMODE=source-package-build
    -DEXPECTED_SOURCE=backend/opengl/SamplerOnlyNonUniformCompareDescriptorArrayLodShader.comp.glsl
    "-DEXPECTED_SOURCE_SNIPPET=textureLod(sampler2DShadow(shadowMap, shadowSamplers[nonuniformEXT(descriptor)])"
    "-DEXPECTED_REFLECTION_FEATURE_FIELDS=nonuniform-descriptor-index.kind=operation|GL_EXT_nonuniform_qualifier.kind=extension"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_build_directx_texture_only_nonuniform_compare_lod_manual_descriptor_array_source_package
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_TEXTURE_ONLY_NONUNIFORM_COMPARE_LOD_MANUAL_DESCRIPTOR_ARRAY_SHADER}
    -DTARGET=directx
    -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-directx-texture-only-nonuniform-compare-lod-manual-descriptor-array.cglb
    -DMODE=source-package-build
    -DEXPECTED_SOURCE=backend/directx/TextureOnlyNonUniformCompareLodManualDescriptorArrayShader.hlsl
    "-DEXPECTED_SOURCE_SNIPPET=cglCompareDepth(shadowAtlases[NonUniformResourceIndex(descriptor)].SampleLevel(rawShadowSampler, float3(0.25, 0.5, 1.0), 2.0), 0.33, CGL_COMPARE_LESS_EQUAL)"
    "-DEXPECTED_REFLECTION_FEATURE_FIELDS=nonuniform-descriptor-index.kind=operation|NonUniformResourceIndex.kind=intrinsic"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_build_opengl_texture_only_nonuniform_compare_lod_manual_descriptor_array_source_package
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_TEXTURE_ONLY_NONUNIFORM_COMPARE_LOD_MANUAL_DESCRIPTOR_ARRAY_SHADER}
    -DTARGET=opengl
    -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-opengl-texture-only-nonuniform-compare-lod-manual-descriptor-array.cglb
    -DMODE=source-package-build
    -DEXPECTED_SOURCE=backend/opengl/TextureOnlyNonUniformCompareLodManualDescriptorArrayShader.comp.glsl
    "-DEXPECTED_SOURCE_SNIPPET=cglCompareDepth(textureLod(sampler2DArray(shadowAtlases[nonuniformEXT(descriptor)], rawShadowSampler), vec3(0.25, 0.5, 1.0), 2.0).r, 0.33, CGL_COMPARE_LESS_EQUAL)"
    "-DEXPECTED_REFLECTION_FEATURE_FIELDS=nonuniform-descriptor-index.kind=operation|GL_EXT_nonuniform_qualifier.kind=extension"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_build_directx_sampler_only_nonuniform_compare_lod_manual_descriptor_array_source_package
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_SAMPLER_ONLY_NONUNIFORM_COMPARE_LOD_MANUAL_DESCRIPTOR_ARRAY_SHADER}
    -DTARGET=directx
    -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-directx-sampler-only-nonuniform-compare-lod-manual-descriptor-array.cglb
    -DMODE=source-package-build
    -DEXPECTED_SOURCE=backend/directx/SamplerOnlyNonUniformCompareLodManualDescriptorArrayShader.hlsl
    "-DEXPECTED_SOURCE_SNIPPET=cglCompareDepth(shadowAtlas.SampleLevel(rawShadowSamplers[NonUniformResourceIndex(descriptor)], float3(0.25, 0.5, 1.0), 2.0), 0.33, CGL_COMPARE_LESS_EQUAL)"
    "-DEXPECTED_REFLECTION_FEATURE_FIELDS=nonuniform-descriptor-index.kind=operation|NonUniformResourceIndex.kind=intrinsic"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_build_opengl_sampler_only_nonuniform_compare_lod_manual_descriptor_array_source_package
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_SAMPLER_ONLY_NONUNIFORM_COMPARE_LOD_MANUAL_DESCRIPTOR_ARRAY_SHADER}
    -DTARGET=opengl
    -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-opengl-sampler-only-nonuniform-compare-lod-manual-descriptor-array.cglb
    -DMODE=source-package-build
    -DEXPECTED_SOURCE=backend/opengl/SamplerOnlyNonUniformCompareLodManualDescriptorArrayShader.comp.glsl
    "-DEXPECTED_SOURCE_SNIPPET=cglCompareDepth(textureLod(sampler2DArray(shadowAtlas, rawShadowSamplers[nonuniformEXT(descriptor)]), vec3(0.25, 0.5, 1.0), 2.0).r, 0.33, CGL_COMPARE_LESS_EQUAL)"
    "-DEXPECTED_REFLECTION_FEATURE_FIELDS=nonuniform-descriptor-index.kind=operation|GL_EXT_nonuniform_qualifier.kind=extension"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_build_directx_texture_cube_family_only_nonuniform_compare_lod_manual_descriptor_array_source_package
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_TEXTURE_CUBE_FAMILY_ONLY_NONUNIFORM_COMPARE_LOD_MANUAL_DESCRIPTOR_ARRAY_SHADER}
    -DTARGET=directx
    -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-directx-texture-cube-family-only-nonuniform-compare-lod-manual-descriptor-array.cglb
    -DMODE=source-package-build
    -DEXPECTED_SOURCE=backend/directx/TextureCubeFamilyOnlyNonUniformCompareLodManualDescriptorArrayShader.hlsl
    "-DEXPECTED_SOURCE_SNIPPET=cglCompareDepth(shadowCubeArrays[NonUniformResourceIndex(descriptor)].SampleLevel(rawShadowSampler, float4(0.0, 1.0, 0.0, 2.0), 3.0), 0.75, CGL_COMPARE_GREATER)"
    "-DEXPECTED_REFLECTION_FEATURE_FIELDS=nonuniform-descriptor-index.kind=operation|NonUniformResourceIndex.kind=intrinsic"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_build_opengl_texture_cube_family_only_nonuniform_compare_lod_manual_descriptor_array_source_package
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_TEXTURE_CUBE_FAMILY_ONLY_NONUNIFORM_COMPARE_LOD_MANUAL_DESCRIPTOR_ARRAY_SHADER}
    -DTARGET=opengl
    -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-opengl-texture-cube-family-only-nonuniform-compare-lod-manual-descriptor-array.cglb
    -DMODE=source-package-build
    -DEXPECTED_SOURCE=backend/opengl/TextureCubeFamilyOnlyNonUniformCompareLodManualDescriptorArrayShader.comp.glsl
    "-DEXPECTED_SOURCE_SNIPPET=cglCompareDepth(textureLod(samplerCubeArray(shadowCubeArrays[nonuniformEXT(descriptor)], rawShadowSampler), vec4(0.0, 1.0, 0.0, 2.0), 3.0).r, 0.75, CGL_COMPARE_GREATER)"
    "-DEXPECTED_REFLECTION_FEATURE_FIELDS=nonuniform-descriptor-index.kind=operation|GL_EXT_nonuniform_qualifier.kind=extension"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_build_directx_sampler_cube_family_only_nonuniform_compare_lod_manual_descriptor_array_source_package
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_SAMPLER_CUBE_FAMILY_ONLY_NONUNIFORM_COMPARE_LOD_MANUAL_DESCRIPTOR_ARRAY_SHADER}
    -DTARGET=directx
    -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-directx-sampler-cube-family-only-nonuniform-compare-lod-manual-descriptor-array.cglb
    -DMODE=source-package-build
    -DEXPECTED_SOURCE=backend/directx/SamplerCubeFamilyOnlyNonUniformCompareLodManualDescriptorArrayShader.hlsl
    "-DEXPECTED_SOURCE_SNIPPET=cglCompareDepth(shadowCubeArray.SampleLevel(rawShadowSamplers[NonUniformResourceIndex(descriptor)], float4(0.0, 1.0, 0.0, 2.0), 3.0), 0.75, CGL_COMPARE_GREATER)"
    "-DEXPECTED_REFLECTION_FEATURE_FIELDS=nonuniform-descriptor-index.kind=operation|NonUniformResourceIndex.kind=intrinsic"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_build_opengl_sampler_cube_family_only_nonuniform_compare_lod_manual_descriptor_array_source_package
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_SAMPLER_CUBE_FAMILY_ONLY_NONUNIFORM_COMPARE_LOD_MANUAL_DESCRIPTOR_ARRAY_SHADER}
    -DTARGET=opengl
    -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-opengl-sampler-cube-family-only-nonuniform-compare-lod-manual-descriptor-array.cglb
    -DMODE=source-package-build
    -DEXPECTED_SOURCE=backend/opengl/SamplerCubeFamilyOnlyNonUniformCompareLodManualDescriptorArrayShader.comp.glsl
    "-DEXPECTED_SOURCE_SNIPPET=cglCompareDepth(textureLod(samplerCubeArray(shadowCubeArray, rawShadowSamplers[nonuniformEXT(descriptor)]), vec4(0.0, 1.0, 0.0, 2.0), 3.0).r, 0.75, CGL_COMPARE_GREATER)"
    "-DEXPECTED_REFLECTION_FEATURE_FIELDS=nonuniform-descriptor-index.kind=operation|GL_EXT_nonuniform_qualifier.kind=extension"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_build_directx_texture_family_only_nonuniform_compare_descriptor_array_source_package
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_TEXTURE_FAMILY_ONLY_NONUNIFORM_COMPARE_DESCRIPTOR_ARRAY_SHADER}
    -DTARGET=directx
    -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-directx-texture-family-only-nonuniform-compare-descriptor-array.cglb
    -DMODE=source-package-build
    -DEXPECTED_SOURCE=backend/directx/TextureFamilyOnlyNonUniformCompareDescriptorArrayShader.hlsl
    "-DEXPECTED_SOURCE_SNIPPET=shadowCubeArrays[NonUniformResourceIndex(descriptor)].SampleCmpLevelZero(shadowSampler"
    "-DEXPECTED_REFLECTION_FEATURE_FIELDS=nonuniform-descriptor-index.kind=operation|NonUniformResourceIndex.kind=intrinsic"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_build_opengl_texture_family_only_nonuniform_compare_descriptor_array_source_package
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_TEXTURE_FAMILY_ONLY_NONUNIFORM_COMPARE_DESCRIPTOR_ARRAY_SHADER}
    -DTARGET=opengl
    -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-opengl-texture-family-only-nonuniform-compare-descriptor-array.cglb
    -DMODE=source-package-build
    -DEXPECTED_SOURCE=backend/opengl/TextureFamilyOnlyNonUniformCompareDescriptorArrayShader.comp.glsl
    "-DEXPECTED_SOURCE_SNIPPET=samplerCubeArrayShadow(shadowCubeArrays[nonuniformEXT(descriptor)], shadowSampler)"
    "-DEXPECTED_REFLECTION_FEATURE_FIELDS=nonuniform-descriptor-index.kind=operation|GL_EXT_nonuniform_qualifier.kind=extension"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_build_directx_sampler_family_only_nonuniform_compare_descriptor_array_source_package
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_SAMPLER_FAMILY_ONLY_NONUNIFORM_COMPARE_DESCRIPTOR_ARRAY_SHADER}
    -DTARGET=directx
    -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-directx-sampler-family-only-nonuniform-compare-descriptor-array.cglb
    -DMODE=source-package-build
    -DEXPECTED_SOURCE=backend/directx/SamplerFamilyOnlyNonUniformCompareDescriptorArrayShader.hlsl
    "-DEXPECTED_SOURCE_SNIPPET=shadowCubeArray.SampleCmpLevelZero(shadowSamplers[NonUniformResourceIndex(descriptor)]"
    "-DEXPECTED_REFLECTION_FEATURE_FIELDS=nonuniform-descriptor-index.kind=operation|NonUniformResourceIndex.kind=intrinsic"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_build_opengl_sampler_family_only_nonuniform_compare_descriptor_array_source_package
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_SAMPLER_FAMILY_ONLY_NONUNIFORM_COMPARE_DESCRIPTOR_ARRAY_SHADER}
    -DTARGET=opengl
    -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-opengl-sampler-family-only-nonuniform-compare-descriptor-array.cglb
    -DMODE=source-package-build
    -DEXPECTED_SOURCE=backend/opengl/SamplerFamilyOnlyNonUniformCompareDescriptorArrayShader.comp.glsl
    "-DEXPECTED_SOURCE_SNIPPET=samplerCubeArrayShadow(shadowCubeArray, shadowSamplers[nonuniformEXT(descriptor)])"
    "-DEXPECTED_REFLECTION_FEATURE_FIELDS=nonuniform-descriptor-index.kind=operation|GL_EXT_nonuniform_qualifier.kind=extension"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_build_directx_texture_compare_nonuniform_descriptor_array_source_package
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_TEXTURE_COMPARE_NONUNIFORM_DESCRIPTOR_ARRAY_SHADER}
    -DTARGET=directx
    -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-directx-texture-compare-nonuniform-descriptor-array.cglb
    -DMODE=source-package-build
    -DEXPECTED_SOURCE=backend/directx/TextureCompareNonUniformDescriptorArrayShader.hlsl
    "-DEXPECTED_SOURCE_SNIPPET=shadowMaps[NonUniformResourceIndex(descriptor)].SampleCmpLevelZero(shadowSamplers[NonUniformResourceIndex(descriptor)]"
    "-DEXPECTED_REFLECTION_FEATURE_FIELDS=nonuniform-descriptor-index.kind=operation|NonUniformResourceIndex.kind=intrinsic"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_build_opengl_texture_compare_nonuniform_descriptor_array_source_package
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_TEXTURE_COMPARE_NONUNIFORM_DESCRIPTOR_ARRAY_SHADER}
    -DTARGET=opengl
    -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-opengl-texture-compare-nonuniform-descriptor-array.cglb
    -DMODE=source-package-build
    -DEXPECTED_SOURCE=backend/opengl/TextureCompareNonUniformDescriptorArrayShader.comp.glsl
    "-DEXPECTED_SOURCE_SNIPPET=sampler2DShadow(shadowMaps[nonuniformEXT(descriptor)], shadowSamplers[nonuniformEXT(descriptor)])"
    "-DEXPECTED_REFLECTION_FEATURE_FIELDS=nonuniform-descriptor-index.kind=operation|GL_EXT_nonuniform_qualifier.kind=extension"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_build_directx_texture_compare_nonuniform_descriptor_array_lod_source_package
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_TEXTURE_COMPARE_NONUNIFORM_DESCRIPTOR_ARRAY_LOD_SHADER}
    -DTARGET=directx
    -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-directx-texture-compare-nonuniform-descriptor-array-lod.cglb
    -DMODE=source-package-build
    -DEXPECTED_SOURCE=backend/directx/TextureCompareNonUniformDescriptorArrayLodShader.hlsl
    "-DEXPECTED_SOURCE_SNIPPET=shadowMaps[NonUniformResourceIndex(descriptor)].SampleCmpLevel(shadowSamplers[NonUniformResourceIndex(descriptor)]"
    "-DEXPECTED_REFLECTION_FEATURE_FIELDS=nonuniform-descriptor-index.kind=operation|NonUniformResourceIndex.kind=intrinsic"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_build_opengl_texture_compare_nonuniform_descriptor_array_lod_source_package
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_TEXTURE_COMPARE_NONUNIFORM_DESCRIPTOR_ARRAY_LOD_SHADER}
    -DTARGET=opengl
    -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-opengl-texture-compare-nonuniform-descriptor-array-lod.cglb
    -DMODE=source-package-build
    -DEXPECTED_SOURCE=backend/opengl/TextureCompareNonUniformDescriptorArrayLodShader.comp.glsl
    "-DEXPECTED_SOURCE_SNIPPET=textureLod(sampler2DShadow(shadowMaps[nonuniformEXT(descriptor)], shadowSamplers[nonuniformEXT(descriptor)])"
    "-DEXPECTED_MANIFEST_JSON_FIELDS=schemaVersion=1|target=opengl|module=TextureCompareNonUniformDescriptorArrayLodShader|artifacts.nativeBinaryStatus=planned"
    "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=opengl|module=TextureCompareNonUniformDescriptorArrayLodShader|manualTextureCompareKernelSummary.totalCount=0"
    "-DEXPECTED_REFLECTION_JSON_ARRAY_LENGTHS=resources=4|targetResourceBindings=4|manualTextureCompareKernels=0"
    "-DEXPECTED_REFLECTION_TARGET_FIELDS=shadowMaps.sourceType=sampler2DShadow[SHADOW_COUNT]|shadowMaps.bindingClass=texture|shadowMaps.argumentIndex=2|shadowMaps.arraySize=SHADOW_COUNT|shadowMaps.arrayElementCount=2|shadowSamplers.sourceType=sampler[SHADOW_COUNT]|shadowSamplers.bindingClass=sampler|shadowSamplers.argumentIndex=5|shadowSamplers.arraySize=SHADOW_COUNT|shadowSamplers.arrayElementCount=2|descriptors.storageBufferLayout.layout=std430|values.storageBufferLayout.layout=std430"
    "-DEXPECTED_REFLECTION_FEATURE_FIELDS=descriptor-array.kind=resource|depth-compare-format.kind=texture|texture-shadow-compare-explicit-lod.kind=operation|nonuniform-descriptor-index.kind=operation|nonuniform-texture-descriptor-index.kind=operation|nonuniform-sampler-descriptor-index.kind=operation|GL_EXT_nonuniform_qualifier.kind=extension"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_build_directx_texture_compare_lod_manual_nonuniform_descriptor_array_source_package
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_TEXTURE_COMPARE_LOD_MANUAL_NONUNIFORM_DESCRIPTOR_ARRAY_SHADER}
    -DTARGET=directx
    -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-directx-texture-compare-lod-manual-nonuniform-descriptor-array.cglb
    -DMODE=source-package-build
    -DEXPECTED_SOURCE=backend/directx/TextureCompareLodManualNonUniformDescriptorArrayShader.hlsl
    "-DEXPECTED_SOURCE_SNIPPET=cglCompareDepth(shadowAtlases[NonUniformResourceIndex(descriptor)].SampleLevel(rawShadowSamplers[NonUniformResourceIndex(descriptor)], float3(0.25, 0.5, 1.0), 2.0), 0.33, CGL_COMPARE_LESS_EQUAL)"
    "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=directx|module=TextureCompareLodManualNonUniformDescriptorArrayShader|manualTextureCompareKernelSummary.totalCount=0"
    "-DEXPECTED_REFLECTION_TARGET_FIELDS=shadowAtlases.bindingClass=srv|shadowAtlases.descriptorType=SRV|shadowAtlases.arrayElementCount=2|rawShadowSamplers.bindingClass=sampler|rawShadowSamplers.descriptorType=Sampler|rawShadowSamplers.arrayElementCount=2"
    "-DEXPECTED_REFLECTION_TARGET_ARRAY_CONTAINS=shadowAtlases.usageRoles=manual-depth-texture|rawShadowSamplers.usageRoles=manual-raw-sampler"
    "-DEXPECTED_REFLECTION_FEATURE_FIELDS=nonuniform-descriptor-index.kind=operation|NonUniformResourceIndex.kind=intrinsic"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_build_opengl_texture_compare_lod_manual_nonuniform_descriptor_array_source_package
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_TEXTURE_COMPARE_LOD_MANUAL_NONUNIFORM_DESCRIPTOR_ARRAY_SHADER}
    -DTARGET=opengl
    -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-opengl-texture-compare-lod-manual-nonuniform-descriptor-array.cglb
    -DMODE=source-package-build
    -DEXPECTED_SOURCE=backend/opengl/TextureCompareLodManualNonUniformDescriptorArrayShader.comp.glsl
    "-DEXPECTED_SOURCE_SNIPPET=cglCompareDepth(textureLod(sampler2DArray(shadowAtlases[nonuniformEXT(descriptor)], rawShadowSamplers[nonuniformEXT(descriptor)]), vec3(0.25, 0.5, 1.0), 2.0).r, 0.33, CGL_COMPARE_LESS_EQUAL)"
    "-DEXPECTED_MANIFEST_JSON_FIELDS=schemaVersion=1|target=opengl|module=TextureCompareLodManualNonUniformDescriptorArrayShader|artifacts.nativeBinaryStatus=planned"
    "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=opengl|module=TextureCompareLodManualNonUniformDescriptorArrayShader|manualTextureCompareKernelSummary.totalCount=0"
    "-DEXPECTED_REFLECTION_JSON_ARRAY_LENGTHS=resources=4|targetResourceBindings=4|manualTextureCompareKernels=0"
    "-DEXPECTED_REFLECTION_TARGET_FIELDS=shadowAtlases.sourceType=sampler2DArrayShadow[SHADOW_COUNT]|shadowAtlases.bindingClass=texture|shadowAtlases.argumentIndex=2|shadowAtlases.arraySize=SHADOW_COUNT|shadowAtlases.arrayElementCount=2|rawShadowSamplers.sourceType=sampler[RAW_SAMPLER_COUNT]|rawShadowSamplers.bindingClass=sampler|rawShadowSamplers.argumentIndex=5|rawShadowSamplers.arraySize=RAW_SAMPLER_COUNT|rawShadowSamplers.arrayElementCount=2|descriptors.storageBufferLayout.layout=std430|values.storageBufferLayout.layout=std430"
    "-DEXPECTED_REFLECTION_TARGET_ARRAY_CONTAINS=shadowAtlases.usageRoles=manual-depth-texture|rawShadowSamplers.usageRoles=manual-raw-sampler"
    "-DEXPECTED_REFLECTION_FEATURE_FIELDS=descriptor-array.kind=resource|array-dimension.kind=texture|depth-compare-format.kind=texture|texture-shadow-compare-explicit-lod-manual.kind=operation|nonuniform-descriptor-index.kind=operation|nonuniform-texture-descriptor-index.kind=operation|nonuniform-sampler-descriptor-index.kind=operation|GL_EXT_nonuniform_qualifier.kind=extension"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_build_directx_texture_cube_family_compare_lod_manual_nonuniform_descriptor_array_source_package
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_TEXTURE_CUBE_FAMILY_COMPARE_LOD_MANUAL_NONUNIFORM_DESCRIPTOR_ARRAY_SHADER}
    -DTARGET=directx
    -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-directx-texture-cube-family-compare-lod-manual-nonuniform-descriptor-array.cglb
    -DMODE=source-package-build
    -DEXPECTED_SOURCE=backend/directx/TextureCubeFamilyCompareLodManualNonUniformDescriptorArrayShader.hlsl
    "-DEXPECTED_SOURCE_SNIPPET=cglCompareDepth(shadowCubeArrays[NonUniformResourceIndex(descriptor)].SampleLevel(rawShadowSamplers[NonUniformResourceIndex(descriptor)], float4(0.0, 1.0, 0.0, 2.0), 3.0), 0.75, CGL_COMPARE_GREATER)"
    "-DEXPECTED_MANIFEST_JSON_FIELDS=schemaVersion=1|target=directx|module=TextureCubeFamilyCompareLodManualNonUniformDescriptorArrayShader|artifacts.backendSource=backend/directx/TextureCubeFamilyCompareLodManualNonUniformDescriptorArrayShader.hlsl|artifacts.nativeBinary=backend/directx/TextureCubeFamilyCompareLodManualNonUniformDescriptorArrayShader.dxil"
    "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=directx|module=TextureCubeFamilyCompareLodManualNonUniformDescriptorArrayShader|nativeBinary=backend/directx/TextureCubeFamilyCompareLodManualNonUniformDescriptorArrayShader.dxil|manualTextureCompareKernelSummary.totalCount=0"
    "-DEXPECTED_REFLECTION_JSON_ARRAY_LENGTHS=resources=5|targetResourceBindings=5|manualTextureCompareKernels=0|workgroupSizes=1"
    "-DEXPECTED_REFLECTION_TARGET_FIELDS=values.hlslType=RWStructuredBuffer<float>|values.bindingClass=uav|values.descriptorType=UAV|descriptors.hlslType=RWStructuredBuffer<int>|descriptors.bindingClass=uav|descriptors.descriptorType=UAV|shadowCubes.sourceType=samplerCubeShadow[SHADOW_COUNT]|shadowCubes.hlslType=TextureCube<float>|shadowCubes.bindingClass=srv|shadowCubes.descriptorType=SRV|shadowCubes.argumentIndex=2|shadowCubes.arraySize=SHADOW_COUNT|shadowCubes.arrayElementCount=2|shadowCubeArrays.sourceType=samplerCubeArrayShadow[SHADOW_COUNT]|shadowCubeArrays.hlslType=TextureCubeArray<float>|shadowCubeArrays.bindingClass=srv|shadowCubeArrays.descriptorType=SRV|shadowCubeArrays.argumentIndex=4|shadowCubeArrays.arraySize=SHADOW_COUNT|shadowCubeArrays.arrayElementCount=2|rawShadowSamplers.sourceType=sampler[RAW_SAMPLER_COUNT]|rawShadowSamplers.hlslType=SamplerState|rawShadowSamplers.bindingClass=sampler|rawShadowSamplers.descriptorType=Sampler|rawShadowSamplers.argumentIndex=9|rawShadowSamplers.arraySize=RAW_SAMPLER_COUNT|rawShadowSamplers.arrayElementCount=2"
    "-DEXPECTED_REFLECTION_TARGET_ARRAY_CONTAINS=shadowCubes.usageRoles=manual-depth-texture|shadowCubeArrays.usageRoles=manual-depth-texture|rawShadowSamplers.usageRoles=manual-raw-sampler"
    "-DEXPECTED_REFLECTION_FEATURE_FIELDS=hlsl-lowering.kind=backend|compute-kernel.kind=stage|workgroup-size.kind=execution|storage-buffer.kind=resource|sampled-texture.kind=resource|fixed-array.kind=layout|descriptor-array.kind=resource|cube-dimension.kind=texture|array-dimension.kind=texture|depth-compare-format.kind=texture|sampler-state.kind=resource|storage-buffer-read.kind=operation|texture-shadow-compare-explicit-lod-manual.kind=operation|nonuniform-descriptor-index.kind=operation|nonuniform-texture-descriptor-index.kind=operation|nonuniform-sampler-descriptor-index.kind=operation|NonUniformResourceIndex.kind=intrinsic|storage-buffer-write.kind=operation"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_build_opengl_texture_cube_family_compare_lod_manual_nonuniform_descriptor_array_source_package
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_TEXTURE_CUBE_FAMILY_COMPARE_LOD_MANUAL_NONUNIFORM_DESCRIPTOR_ARRAY_SHADER}
    -DTARGET=opengl
    -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-opengl-texture-cube-family-compare-lod-manual-nonuniform-descriptor-array.cglb
    -DMODE=source-package-build
    -DEXPECTED_SOURCE=backend/opengl/TextureCubeFamilyCompareLodManualNonUniformDescriptorArrayShader.comp.glsl
    "-DEXPECTED_SOURCE_SNIPPET=cglCompareDepth(textureLod(samplerCubeArray(shadowCubeArrays[nonuniformEXT(descriptor)], rawShadowSamplers[nonuniformEXT(descriptor)]), vec4(0.0, 1.0, 0.0, 2.0), 3.0).r, 0.75, CGL_COMPARE_GREATER)"
    "-DEXPECTED_REFLECTION_FEATURE_FIELDS=nonuniform-descriptor-index.kind=operation|GL_EXT_nonuniform_qualifier.kind=extension"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_build_directx_texture_sampler_descriptor_array_size_mismatch_source_package
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_TEXTURE_SAMPLER_DESCRIPTOR_ARRAY_SIZE_MISMATCH_SHADER}
    -DTARGET=directx
    -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-directx-texture-sampler-descriptor-array-size-mismatch.cglb
    -DMODE=source-package-build
    -DEXPECTED_SOURCE=backend/directx/TextureSamplerDescriptorArraySizeMismatchShader.hlsl
    "-DEXPECTED_SOURCE_SNIPPET=colorMaps[1].SampleLevel(linearSamplers[2]"
    "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=directx|module=TextureSamplerDescriptorArraySizeMismatchShader|manualTextureCompareKernelSummary.totalCount=0"
    "-DEXPECTED_REFLECTION_TARGET_FIELDS=colorMaps.bindingClass=srv|colorMaps.arraySize=TEXTURE_COUNT|colorMaps.arrayElementCount=2|linearSamplers.bindingClass=sampler|linearSamplers.arraySize=SAMPLER_COUNT|linearSamplers.arrayElementCount=3"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_build_opengl_texture_sampler_descriptor_array_size_mismatch_source_package
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_TEXTURE_SAMPLER_DESCRIPTOR_ARRAY_SIZE_MISMATCH_SHADER}
    -DTARGET=opengl
    -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-opengl-texture-sampler-descriptor-array-size-mismatch.cglb
    -DMODE=source-package-build
    -DEXPECTED_SOURCE=backend/opengl/TextureSamplerDescriptorArraySizeMismatchShader.comp.glsl
    "-DEXPECTED_SOURCE_SNIPPET=textureLod(sampler2D(colorMaps[1], linearSamplers[2])"
    "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=opengl|module=TextureSamplerDescriptorArraySizeMismatchShader|manualTextureCompareKernelSummary.totalCount=0"
    "-DEXPECTED_REFLECTION_TARGET_FIELDS=colorMaps.bindingClass=texture|colorMaps.arraySize=TEXTURE_COUNT|colorMaps.arrayElementCount=2|linearSamplers.bindingClass=sampler|linearSamplers.arraySize=SAMPLER_COUNT|linearSamplers.arrayElementCount=3|values.storageBufferLayout.layout=std430"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_build_directx_texture_sampler_array_descriptor_source_package
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_VULKAN_TEXTURE_SAMPLER_ARRAY_DESCRIPTOR_SHADER}
    -DTARGET=directx
    -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-directx-texture-sampler-array-descriptor.cglb
    -DMODE=source-package-build
    -DEXPECTED_SOURCE=backend/directx/VulkanTextureSamplerArrayDescriptorShader.hlsl
    "-DEXPECTED_SOURCE_SNIPPET=Texture2D<float4> shadowMaps[MAP_COUNT]"
    "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=directx|module=VulkanTextureSamplerArrayDescriptorShader"
    "-DEXPECTED_REFLECTION_TARGET_FIELDS=shadowMaps.sourceType=sampler2D[MAP_COUNT]|shadowMaps.hlslType=Texture2D<float4>|shadowMaps.bindingClass=srv|shadowMaps.descriptorType=SRV|shadowMaps.arraySize=MAP_COUNT|shadowMaps.arrayElementCount=2|comparisonSamplers.sourceType=sampler[2]|comparisonSamplers.hlslType=SamplerState|comparisonSamplers.bindingClass=sampler|comparisonSamplers.arraySize=2|comparisonSamplers.arrayElementCount=2"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_build_opengl_texture_sampler_array_descriptor_source_package
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_VULKAN_TEXTURE_SAMPLER_ARRAY_DESCRIPTOR_SHADER}
    -DTARGET=opengl
    -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-opengl-texture-sampler-array-descriptor.cglb
    -DMODE=source-package-build
    -DEXPECTED_SOURCE=backend/opengl/VulkanTextureSamplerArrayDescriptorShader.comp.glsl
    "-DEXPECTED_SOURCE_SNIPPET=uniform texture2D shadowMaps[MAP_COUNT]"
    "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=opengl|module=VulkanTextureSamplerArrayDescriptorShader"
    "-DEXPECTED_REFLECTION_TARGET_FIELDS=shadowMaps.sourceType=sampler2D[MAP_COUNT]|shadowMaps.bindingClass=texture|shadowMaps.arraySize=MAP_COUNT|shadowMaps.arrayElementCount=2|comparisonSamplers.sourceType=sampler[2]|comparisonSamplers.bindingClass=sampler|comparisonSamplers.arraySize=2|comparisonSamplers.arrayElementCount=2"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_build_directx_texture_sampler_array_lod_source_package
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_VULKAN_TEXTURE_SAMPLER_ARRAY_LOD_SHADER}
    -DTARGET=directx
    -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-directx-texture-sampler-array-lod.cglb
    -DMODE=source-package-build
    -DEXPECTED_SOURCE=backend/directx/VulkanTextureSamplerArrayLodShader.hlsl
    "-DEXPECTED_SOURCE_SNIPPET=shadowMaps[0].SampleLevel(comparisonSamplers[0]"
    "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=directx|module=VulkanTextureSamplerArrayLodShader"
    "-DEXPECTED_REFLECTION_TARGET_FIELDS=shadowMaps.sourceType=sampler2D[2]|shadowMaps.hlslType=Texture2D<float4>|shadowMaps.bindingClass=srv|shadowMaps.arraySize=2|shadowMaps.arrayElementCount=2|comparisonSamplers.sourceType=sampler[2]|comparisonSamplers.hlslType=SamplerState|comparisonSamplers.bindingClass=sampler|comparisonSamplers.arraySize=2|comparisonSamplers.arrayElementCount=2"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_build_opengl_texture_sampler_array_lod_source_package
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_VULKAN_TEXTURE_SAMPLER_ARRAY_LOD_SHADER}
    -DTARGET=opengl
    -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-opengl-texture-sampler-array-lod.cglb
    -DMODE=source-package-build
    -DEXPECTED_SOURCE=backend/opengl/VulkanTextureSamplerArrayLodShader.comp.glsl
    "-DEXPECTED_SOURCE_SNIPPET=sampler2D(shadowMaps[0], comparisonSamplers[0])"
    "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=opengl|module=VulkanTextureSamplerArrayLodShader"
    "-DEXPECTED_REFLECTION_TARGET_FIELDS=shadowMaps.sourceType=sampler2D[2]|shadowMaps.bindingClass=texture|shadowMaps.arraySize=2|shadowMaps.arrayElementCount=2|comparisonSamplers.sourceType=sampler[2]|comparisonSamplers.bindingClass=sampler|comparisonSamplers.arraySize=2|comparisonSamplers.arrayElementCount=2|values.storageBufferLayout.layout=std430"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_build_directx_texture_sampler_3d_array_lod_source_package
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_VULKAN_TEXTURE_SAMPLER_3D_ARRAY_LOD_SHADER}
    -DTARGET=directx
    -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-directx-texture-sampler-3d-array-lod.cglb
    -DMODE=source-package-build
    -DEXPECTED_SOURCE=backend/directx/VulkanTextureSampler3DArrayLodShader.hlsl
    "-DEXPECTED_SOURCE_SNIPPET=volumeMaps[1].SampleLevel(volumeSamplers[0]"
    "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=directx|module=VulkanTextureSampler3DArrayLodShader"
    "-DEXPECTED_REFLECTION_TARGET_FIELDS=volumeMaps.sourceType=sampler3D[2]|volumeMaps.hlslType=Texture3D<float4>|volumeMaps.bindingClass=srv|volumeMaps.arraySize=2|volumeMaps.arrayElementCount=2|volumeSamplers.sourceType=sampler[2]|volumeSamplers.hlslType=SamplerState|volumeSamplers.bindingClass=sampler|volumeSamplers.arraySize=2|volumeSamplers.arrayElementCount=2"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_build_opengl_texture_sampler_3d_array_lod_source_package
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_VULKAN_TEXTURE_SAMPLER_3D_ARRAY_LOD_SHADER}
    -DTARGET=opengl
    -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-opengl-texture-sampler-3d-array-lod.cglb
    -DMODE=source-package-build
    -DEXPECTED_SOURCE=backend/opengl/VulkanTextureSampler3DArrayLodShader.comp.glsl
    "-DEXPECTED_SOURCE_SNIPPET=sampler3D(volumeMaps[1], volumeSamplers[0])"
    "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=opengl|module=VulkanTextureSampler3DArrayLodShader"
    "-DEXPECTED_REFLECTION_TARGET_FIELDS=volumeMaps.sourceType=sampler3D[2]|volumeMaps.bindingClass=texture|volumeMaps.arraySize=2|volumeMaps.arrayElementCount=2|volumeSamplers.sourceType=sampler[2]|volumeSamplers.bindingClass=sampler|volumeSamplers.arraySize=2|volumeSamplers.arrayElementCount=2|values.storageBufferLayout.layout=std430"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_build_directx_texture_sampler_cube_array_lod_source_package
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_VULKAN_TEXTURE_SAMPLER_CUBE_ARRAY_LOD_SHADER}
    -DTARGET=directx
    -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-directx-texture-sampler-cube-array-lod.cglb
    -DMODE=source-package-build
    -DEXPECTED_SOURCE=backend/directx/VulkanTextureSamplerCubeArrayLodShader.hlsl
    "-DEXPECTED_SOURCE_SNIPPET=skyMaps[1].SampleLevel(skySamplers[0]"
    "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=directx|module=VulkanTextureSamplerCubeArrayLodShader"
    "-DEXPECTED_REFLECTION_TARGET_FIELDS=skyMaps.sourceType=samplerCube[2]|skyMaps.hlslType=TextureCube<float4>|skyMaps.bindingClass=srv|skyMaps.arraySize=2|skyMaps.arrayElementCount=2|skySamplers.sourceType=sampler[2]|skySamplers.hlslType=SamplerState|skySamplers.bindingClass=sampler|skySamplers.arraySize=2|skySamplers.arrayElementCount=2"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_build_opengl_texture_sampler_cube_array_lod_source_package
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_VULKAN_TEXTURE_SAMPLER_CUBE_ARRAY_LOD_SHADER}
    -DTARGET=opengl
    -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-opengl-texture-sampler-cube-array-lod.cglb
    -DMODE=source-package-build
    -DEXPECTED_SOURCE=backend/opengl/VulkanTextureSamplerCubeArrayLodShader.comp.glsl
    "-DEXPECTED_SOURCE_SNIPPET=samplerCube(skyMaps[1], skySamplers[0])"
    "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=opengl|module=VulkanTextureSamplerCubeArrayLodShader"
    "-DEXPECTED_REFLECTION_TARGET_FIELDS=skyMaps.sourceType=samplerCube[2]|skyMaps.bindingClass=texture|skyMaps.arraySize=2|skyMaps.arrayElementCount=2|skySamplers.sourceType=sampler[2]|skySamplers.bindingClass=sampler|skySamplers.arraySize=2|skySamplers.arrayElementCount=2|values.storageBufferLayout.layout=std430"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_build_directx_texture_array_shadow_compare_source_package
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_TEXTURE_ARRAY_SHADOW_COMPARE_SHADER}
    -DTARGET=directx
    -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-directx-texture-array-shadow-compare.cglb
    -DMODE=source-package-build
    -DEXPECTED_SOURCE=backend/directx/TextureArrayShadowCompareShader.hlsl
    "-DEXPECTED_SOURCE_SNIPPET=TextureCubeArray<float> shadowCubes"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_build_opengl_texture_array_shadow_compare_source_package
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_TEXTURE_ARRAY_SHADOW_COMPARE_SHADER}
    -DTARGET=opengl
    -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-opengl-texture-array-shadow-compare.cglb
    -DMODE=source-package-build
    -DEXPECTED_SOURCE=backend/opengl/TextureArrayShadowCompareShader.comp.glsl
    "-DEXPECTED_SOURCE_SNIPPET=samplerCubeArrayShadow(shadowCubes, shadowSampler)"
    "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=opengl|module=TextureArrayShadowCompareShader"
    "-DEXPECTED_REFLECTION_TARGET_FIELDS=shadowAtlas.sourceType=sampler2DArrayShadow|shadowAtlas.bindingClass=texture|shadowCubes.sourceType=samplerCubeArrayShadow|shadowCubes.bindingClass=texture|shadowSampler.bindingClass=sampler|values.storageBufferLayout.layout=std430"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_build_directx_texture_compare_lod_source_package
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_TEXTURE_COMPARE_LOD_SHADER}
    -DTARGET=directx
    -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-directx-texture-compare-lod.cglb
    -DMODE=source-package-build
    -DEXPECTED_SOURCE=backend/directx/TextureCompareLodShader.hlsl
    "-DEXPECTED_SOURCE_SNIPPET=SampleCmpLevel(shadowSampler"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_build_opengl_texture_compare_lod_source_package
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_TEXTURE_COMPARE_LOD_SHADER}
    -DTARGET=opengl
    -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-opengl-texture-compare-lod.cglb
    -DMODE=source-package-build
    -DEXPECTED_SOURCE=backend/opengl/TextureCompareLodShader.comp.glsl
    "-DEXPECTED_SOURCE_SNIPPET=textureLod(shadowCubes, vec4(0.0, 1.0, 0.0, 2.0), 0.75, 3.0)"
    "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=opengl|module=TextureCompareLodShader|nativeBinary=backend/opengl/TextureCompareLodShader.glsl"
    "-DEXPECTED_REFLECTION_TARGET_FIELDS=shadowMap.sourceType=sampler2DShadow|shadowMap.bindingClass=texture|shadowCubes.sourceType=samplerCubeArrayShadow|shadowCubes.bindingClass=texture|shadowSampler.bindingClass=sampler|values.storageBufferLayout.layout=std430"
    -DEXPECTED_NATIVE_BINARY_STATUS=${CROSSGL_OPENGL_SOURCE_PACKAGE_NATIVE_BINARY_STATUS}
    ${CROSSGL_OPENGL_TEXTURE_COMPARE_LOD_NATIVE_BINARY}
    ${CROSSGL_OPENGL_SHADOW_LOD_NATIVE_DIAGNOSTIC}
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_build_opengl_texture_compare_2d_lod_source_package
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_TEXTURE_COMPARE_2D_LOD_SHADER}
    -DTARGET=opengl
    -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-opengl-texture-compare-2d-lod.cglb
    -DMODE=source-package-build
    -DEXPECTED_SOURCE=backend/opengl/TextureCompare2DLodShader.comp.glsl
    "-DEXPECTED_SOURCE_SNIPPET=textureLod(shadowMap, vec3(vec2(0.5, 0.5), 0.25), 2.0)"
    "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=opengl|module=TextureCompare2DLodShader"
    "-DEXPECTED_REFLECTION_TARGET_FIELDS=shadowMap.sourceType=sampler2DShadow|shadowMap.bindingClass=texture|shadowSampler.bindingClass=sampler|values.storageBufferLayout.layout=std430"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_build_directx_texture_array_shadow_compare_lod_source_package
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_TEXTURE_ARRAY_SHADOW_COMPARE_LOD_UNSUPPORTED_SHADER}
    -DTARGET=directx
    -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-directx-texture-array-shadow-compare-lod.cglb
    -DMODE=source-package-build
    -DEXPECTED_SOURCE=backend/directx/TextureArrayShadowCompareLodUnsupportedShader.hlsl
    "-DEXPECTED_SOURCE_SNIPPET=shadowAtlas.SampleCmpLevel(shadowSampler"
    "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=directx|module=TextureArrayShadowCompareLodUnsupportedShader"
    "-DEXPECTED_REFLECTION_TARGET_FIELDS=shadowAtlas.sourceType=sampler2DArrayShadow|shadowAtlas.hlslType=Texture2DArray<float>|shadowAtlas.bindingClass=srv|shadowAtlas.descriptorType=SRV|shadowCube.sourceType=samplerCubeShadow|shadowCube.hlslType=TextureCube<float>|shadowCube.bindingClass=srv|shadowSampler.hlslType=SamplerComparisonState|shadowSampler.bindingClass=sampler"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_build_directx_texture_2d_shadow_compare_lod_manual_source_package
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_TEXTURE_2D_SHADOW_COMPARE_LOD_MANUAL_SHADER}
    -DTARGET=directx
    -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-directx-texture-2d-shadow-compare-lod-manual.cglb
    -DMODE=source-package-build
    -DEXPECTED_SOURCE=backend/directx/Texture2DShadowCompareLodManualShader.hlsl
    "-DEXPECTED_SOURCE_SNIPPET=cglCompareDepth(shadowMap.SampleLevel(rawShadowSampler, float2(0.5, 0.5), 2.0), 0.25, CGL_COMPARE_LESS)"
    "-DEXPECTED_REFLECTION_TARGET_ARRAY_CONTAINS=shadowMap.usageRoles=manual-depth-texture|rawShadowSampler.usageRoles=manual-raw-sampler"
    "-DEXPECTED_REFLECTION_FEATURE_FIELDS=sampled-texture.kind=resource|depth-compare-format.kind=texture|sampler-state.kind=resource|texture-shadow-compare-explicit-lod-manual.kind=operation|index-access.kind=operation|storage-buffer-write.kind=operation"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_build_directx_texture_2d_array_shadow_compare_lod_manual_source_package
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_TEXTURE_2D_ARRAY_SHADOW_COMPARE_LOD_MANUAL_SHADER}
    -DTARGET=directx
    -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-directx-texture-2d-array-shadow-compare-lod-manual.cglb
    -DMODE=source-package-build
    -DEXPECTED_SOURCE=backend/directx/Texture2DArrayShadowCompareLodManualShader.hlsl
    "-DEXPECTED_SOURCE_SNIPPET=cglCompareDepth(shadowAtlas.SampleLevel(rawShadowSampler, float3(0.25, 0.5, 1.0), 2.0), 0.33, CGL_COMPARE_LESS_EQUAL)"
    "-DEXPECTED_REFLECTION_TARGET_ARRAY_CONTAINS=shadowAtlas.usageRoles=manual-depth-texture|rawShadowSampler.usageRoles=manual-raw-sampler"
    "-DEXPECTED_REFLECTION_FEATURE_FIELDS=sampled-texture.kind=resource|array-dimension.kind=texture|depth-compare-format.kind=texture|sampler-state.kind=resource|texture-shadow-compare-explicit-lod-manual.kind=operation|index-access.kind=operation|storage-buffer-write.kind=operation"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_build_directx_texture_2d_shadow_compare_lod_manual_offset_source_package
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_TEXTURE_2D_SHADOW_COMPARE_LOD_MANUAL_OFFSET_SHADER}
    -DTARGET=directx
    -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-directx-texture-2d-shadow-compare-lod-manual-offset.cglb
    -DMODE=source-package-build
    -DEXPECTED_SOURCE=backend/directx/Texture2DShadowCompareLodManualOffsetShader.hlsl
    "-DEXPECTED_SOURCE_SNIPPET=cglCompareDepth(shadowMap.SampleLevel(rawShadowSampler, float2(0.5, 0.5), 2.0, int2(1, -1)), 0.25, CGL_COMPARE_LESS)"
    "-DEXPECTED_REFLECTION_TARGET_ARRAY_CONTAINS=shadowMap.usageRoles=manual-depth-texture|rawShadowSampler.usageRoles=manual-raw-sampler"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_build_directx_texture_2d_array_shadow_compare_lod_manual_offset_source_package
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_TEXTURE_2D_ARRAY_SHADOW_COMPARE_LOD_MANUAL_OFFSET_SHADER}
    -DTARGET=directx
    -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-directx-texture-2d-array-shadow-compare-lod-manual-offset.cglb
    -DMODE=source-package-build
    -DEXPECTED_SOURCE=backend/directx/Texture2DArrayShadowCompareLodManualOffsetShader.hlsl
    "-DEXPECTED_SOURCE_SNIPPET=cglCompareDepth(shadowAtlas.SampleLevel(rawShadowSampler, float3(0.25, 0.5, 1.0), 2.0, int2(-1, 1)), 0.33, CGL_COMPARE_LESS_EQUAL)"
    "-DEXPECTED_REFLECTION_TARGET_ARRAY_CONTAINS=shadowAtlas.usageRoles=manual-depth-texture|rawShadowSampler.usageRoles=manual-raw-sampler"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_build_directx_texture_2d_shadow_compare_lod_manual_gather_2x2_source_package
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_TEXTURE_2D_SHADOW_COMPARE_LOD_MANUAL_GATHER_2X2_SHADER}
    -DTARGET=directx
    -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-directx-texture-2d-shadow-compare-lod-manual-gather-2x2.cglb
    -DMODE=source-package-build
    -DEXPECTED_SOURCE=backend/directx/Texture2DShadowCompareLodManualGather2x2Shader.hlsl
    "-DEXPECTED_SOURCE_SNIPPET=cglCompareDepth(shadowMap.SampleLevel(rawShadowSampler, float2(0.5, 0.5), 2.0, int2(1, 1)), 0.25, CGL_COMPARE_LESS)"
    "-DEXPECTED_REFLECTION_TARGET_ARRAY_CONTAINS=shadowMap.usageRoles=manual-depth-texture|rawShadowSampler.usageRoles=manual-raw-sampler"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_build_directx_texture_2d_array_shadow_compare_lod_manual_gather_2x2_source_package
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_TEXTURE_2D_ARRAY_SHADOW_COMPARE_LOD_MANUAL_GATHER_2X2_SHADER}
    -DTARGET=directx
    -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-directx-texture-2d-array-shadow-compare-lod-manual-gather-2x2.cglb
    -DMODE=source-package-build
    -DEXPECTED_SOURCE=backend/directx/Texture2DArrayShadowCompareLodManualGather2x2Shader.hlsl
    "-DEXPECTED_SOURCE_SNIPPET=cglCompareDepth(shadowAtlas.SampleLevel(rawShadowSampler, float3(0.25, 0.5, 1.0), 2.0, int2(1, 1)), 0.33, CGL_COMPARE_LESS_EQUAL)"
    "-DEXPECTED_REFLECTION_TARGET_ARRAY_CONTAINS=shadowAtlas.usageRoles=manual-depth-texture|rawShadowSampler.usageRoles=manual-raw-sampler"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_build_directx_texture_2d_shadow_compare_lod_manual_kernel_4_source_package
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_TEXTURE_2D_SHADOW_COMPARE_LOD_MANUAL_KERNEL_4_SHADER}
    -DTARGET=directx
    -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-directx-texture-2d-shadow-compare-lod-manual-kernel-4.cglb
    -DMODE=source-package-build
    -DEXPECTED_SOURCE=backend/directx/Texture2DShadowCompareLodManualKernel4Shader.hlsl
    "-DEXPECTED_SOURCE_SNIPPET=cglCompareDepth(shadowMap.SampleLevel(rawShadowSampler, float2(0.5, 0.5), 2.0, int2(1, 0)), 0.25, CGL_COMPARE_LESS) * 0.375"
    "-DEXPECTED_REFLECTION_TARGET_ARRAY_CONTAINS=shadowMap.usageRoles=manual-depth-texture|rawShadowSampler.usageRoles=manual-raw-sampler"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_build_directx_texture_2d_array_shadow_compare_lod_manual_kernel_4_source_package
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_TEXTURE_2D_ARRAY_SHADOW_COMPARE_LOD_MANUAL_KERNEL_4_SHADER}
    -DTARGET=directx
    -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-directx-texture-2d-array-shadow-compare-lod-manual-kernel-4.cglb
    -DMODE=source-package-build
    -DEXPECTED_SOURCE=backend/directx/Texture2DArrayShadowCompareLodManualKernel4Shader.hlsl
    "-DEXPECTED_SOURCE_SNIPPET=cglCompareDepth(shadowAtlas.SampleLevel(rawShadowSampler, float3(0.25, 0.5, 1.0), 2.0, int2(-1, 0)), 0.33, CGL_COMPARE_LESS_EQUAL) * 0.30"
    "-DEXPECTED_MANIFEST_JSON_FIELDS=schemaVersion=1|target=directx|module=Texture2DArrayShadowCompareLodManualKernel4Shader|artifacts.backendSource=backend/directx/Texture2DArrayShadowCompareLodManualKernel4Shader.hlsl|artifacts.nativeBinary=backend/directx/Texture2DArrayShadowCompareLodManualKernel4Shader.dxil"
    "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=directx|module=Texture2DArrayShadowCompareLodManualKernel4Shader|nativeBinary=backend/directx/Texture2DArrayShadowCompareLodManualKernel4Shader.dxil|manualTextureCompareKernelSummary.totalCount=1|manualTextureCompareKernelSummary.staticNormalizedCount=1|manualTextureCompareKernels.0.tapCount=4|manualTextureCompareKernels.0.weightClass=static-normalized|manualTextureCompareKernels.0.sourceKind=fixed4|manualTextureCompareKernels.0.compatibilityAlias=true"
    "-DEXPECTED_REFLECTION_JSON_ARRAY_LENGTHS=resources=3|targetResourceBindings=3|manualTextureCompareKernels=1|workgroupSizes=1"
    "-DEXPECTED_REFLECTION_TARGET_FIELDS=values.hlslType=RWStructuredBuffer<float>|values.bindingClass=uav|values.descriptorType=UAV|shadowAtlas.sourceType=sampler2DArrayShadow|shadowAtlas.hlslType=Texture2DArray<float>|shadowAtlas.bindingClass=srv|shadowAtlas.descriptorType=SRV|shadowAtlas.argumentIndex=2|rawShadowSampler.sourceType=sampler|rawShadowSampler.hlslType=SamplerState|rawShadowSampler.bindingClass=sampler|rawShadowSampler.descriptorType=Sampler|rawShadowSampler.argumentIndex=5"
    "-DEXPECTED_REFLECTION_TARGET_ARRAY_CONTAINS=shadowAtlas.usageRoles=manual-depth-texture|rawShadowSampler.usageRoles=manual-raw-sampler"
    "-DEXPECTED_REFLECTION_FEATURE_FIELDS=hlsl-lowering.kind=backend|compute-kernel.kind=stage|workgroup-size.kind=execution|storage-buffer.kind=resource|sampled-texture.kind=resource|array-dimension.kind=texture|depth-compare-format.kind=texture|sampler-state.kind=resource|texture-shadow-compare-explicit-lod-manual.kind=operation|texture-shadow-compare-explicit-lod-manual-kernel-list.kind=operation|index-access.kind=operation|storage-buffer-write.kind=operation"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_build_directx_texture_2d_shadow_compare_lod_manual_kernel_8_source_package
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_TEXTURE_2D_SHADOW_COMPARE_LOD_MANUAL_KERNEL_8_SHADER}
    -DTARGET=directx
    -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-directx-texture-2d-shadow-compare-lod-manual-kernel-8.cglb
    -DMODE=source-package-build
    -DEXPECTED_SOURCE=backend/directx/Texture2DShadowCompareLodManualKernel8Shader.hlsl
    "-DEXPECTED_SOURCE_SNIPPET=cglCompareDepth(shadowMap.SampleLevel(rawShadowSampler, float2(0.5, 0.5), 2.0, int2(1, 1)), 0.25, CGL_COMPARE_LESS) * 0.3125"
    "-DEXPECTED_REFLECTION_TARGET_ARRAY_CONTAINS=shadowMap.usageRoles=manual-depth-texture|rawShadowSampler.usageRoles=manual-raw-sampler"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_build_directx_texture_2d_array_shadow_compare_lod_manual_kernel_8_source_package
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_TEXTURE_2D_ARRAY_SHADOW_COMPARE_LOD_MANUAL_KERNEL_8_SHADER}
    -DTARGET=directx
    -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-directx-texture-2d-array-shadow-compare-lod-manual-kernel-8.cglb
    -DMODE=source-package-build
    -DEXPECTED_SOURCE=backend/directx/Texture2DArrayShadowCompareLodManualKernel8Shader.hlsl
    "-DEXPECTED_SOURCE_SNIPPET=cglCompareDepth(shadowAtlas.SampleLevel(rawShadowSampler, float3(0.25, 0.5, 1.0), 2.0, int2(1, 1)), 0.33, CGL_COMPARE_LESS_EQUAL) * 0.10"
    "-DEXPECTED_REFLECTION_TARGET_ARRAY_CONTAINS=shadowAtlas.usageRoles=manual-depth-texture|rawShadowSampler.usageRoles=manual-raw-sampler"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_build_directx_texture_2d_shadow_compare_lod_manual_kernel_list_source_package
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_TEXTURE_2D_SHADOW_COMPARE_LOD_MANUAL_KERNEL_LIST_SHADER}
    -DTARGET=directx
    -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-directx-texture-2d-shadow-compare-lod-manual-kernel-list.cglb
    -DMODE=source-package-build
    -DEXPECTED_SOURCE=backend/directx/Texture2DShadowCompareLodManualKernelListShader.hlsl
    "-DEXPECTED_SOURCE_SNIPPET=cglCompareDepth(shadowMap.SampleLevel(rawShadowSampler, float2(0.5, 0.5), 2.0, int2(0, -1)), 0.25, CGL_COMPARE_LESS_EQUAL) * 0.15"
    "-DEXPECTED_MANIFEST_JSON_FIELDS=schemaVersion=1|target=directx|module=Texture2DShadowCompareLodManualKernelListShader|artifacts.backendSource=backend/directx/Texture2DShadowCompareLodManualKernelListShader.hlsl|artifacts.nativeBinary=backend/directx/Texture2DShadowCompareLodManualKernelListShader.dxil"
    "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=directx|module=Texture2DShadowCompareLodManualKernelListShader|nativeBinary=backend/directx/Texture2DShadowCompareLodManualKernelListShader.dxil|manualTextureCompareKernelSummary.totalCount=1|manualTextureCompareKernelSummary.staticNormalizedCount=1|manualTextureCompareKernels.0.tapCount=5|manualTextureCompareKernels.0.weightClass=static-normalized|manualTextureCompareKernels.0.sourceKind=tap-list|manualTextureCompareKernels.0.compatibilityAlias=false"
    "-DEXPECTED_REFLECTION_JSON_ARRAY_LENGTHS=resources=3|targetResourceBindings=3|manualTextureCompareKernels=1|workgroupSizes=1"
    "-DEXPECTED_REFLECTION_TARGET_FIELDS=values.hlslType=RWStructuredBuffer<float>|values.bindingClass=uav|values.descriptorType=UAV|shadowMap.sourceType=sampler2DShadow|shadowMap.hlslType=Texture2D<float>|shadowMap.bindingClass=srv|shadowMap.descriptorType=SRV|shadowMap.argumentIndex=2|rawShadowSampler.sourceType=sampler|rawShadowSampler.hlslType=SamplerState|rawShadowSampler.bindingClass=sampler|rawShadowSampler.descriptorType=Sampler|rawShadowSampler.argumentIndex=6"
    "-DEXPECTED_REFLECTION_TARGET_ARRAY_CONTAINS=shadowMap.usageRoles=manual-depth-texture|rawShadowSampler.usageRoles=manual-raw-sampler"
    "-DEXPECTED_REFLECTION_FEATURE_FIELDS=hlsl-lowering.kind=backend|compute-kernel.kind=stage|workgroup-size.kind=execution|storage-buffer.kind=resource|sampled-texture.kind=resource|depth-compare-format.kind=texture|sampler-state.kind=resource|texture-shadow-compare-explicit-lod-manual.kind=operation|texture-shadow-compare-explicit-lod-manual-kernel-list.kind=operation|index-access.kind=operation|storage-buffer-write.kind=operation"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_build_directx_texture_cube_shadow_compare_lod_manual_source_package
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_TEXTURE_CUBE_SHADOW_COMPARE_LOD_MANUAL_SHADER}
    -DTARGET=directx
    -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-directx-texture-cube-shadow-compare-lod-manual.cglb
    -DMODE=source-package-build
    -DEXPECTED_SOURCE=backend/directx/TextureCubeShadowCompareLodManualShader.hlsl
    "-DEXPECTED_SOURCE_SNIPPET=cglCompareDepth(shadowCube.SampleLevel(rawShadowSampler, float3(0.0, 1.0, 0.0), 1.0), 0.5, CGL_COMPARE_GREATER_EQUAL)"
    "-DEXPECTED_REFLECTION_TARGET_ARRAY_CONTAINS=shadowCube.usageRoles=manual-depth-texture|rawShadowSampler.usageRoles=manual-raw-sampler"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_build_directx_texture_cube_array_shadow_compare_lod_manual_source_package
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_TEXTURE_CUBE_ARRAY_SHADOW_COMPARE_LOD_MANUAL_SHADER}
    -DTARGET=directx
    -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-directx-texture-cube-array-shadow-compare-lod-manual.cglb
    -DMODE=source-package-build
    -DEXPECTED_SOURCE=backend/directx/TextureCubeArrayShadowCompareLodManualShader.hlsl
    "-DEXPECTED_SOURCE_SNIPPET=cglCompareDepth(shadowCubes.SampleLevel(rawShadowSampler, float4(0.0, 1.0, 0.0, 2.0), 3.0), 0.75, CGL_COMPARE_GREATER)"
    "-DEXPECTED_REFLECTION_TARGET_ARRAY_CONTAINS=shadowCubes.usageRoles=manual-depth-texture|rawShadowSampler.usageRoles=manual-raw-sampler"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_build_directx_texture_compare_lod_manual_descriptor_array_source_package
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_TEXTURE_COMPARE_LOD_MANUAL_DESCRIPTOR_ARRAY_SHADER}
    -DTARGET=directx
    -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-directx-texture-compare-lod-manual-descriptor-array.cglb
    -DMODE=source-package-build
    -DEXPECTED_SOURCE=backend/directx/TextureCompareLodManualDescriptorArrayShader.hlsl
    "-DEXPECTED_SOURCE_SNIPPET=cglCompareDepth(shadowAtlases[1].SampleLevel(rawShadowSamplers[0], float3(0.25, 0.5, 1.0), 2.0), 0.33, CGL_COMPARE_LESS_EQUAL)"
    "-DEXPECTED_MANIFEST_JSON_FIELDS=schemaVersion=1|target=directx|module=TextureCompareLodManualDescriptorArrayShader|artifacts.backendSource=backend/directx/TextureCompareLodManualDescriptorArrayShader.hlsl|artifacts.nativeBinary=backend/directx/TextureCompareLodManualDescriptorArrayShader.dxil"
    "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=directx|module=TextureCompareLodManualDescriptorArrayShader|nativeBinary=backend/directx/TextureCompareLodManualDescriptorArrayShader.dxil|manualTextureCompareKernelSummary.totalCount=0"
    "-DEXPECTED_REFLECTION_JSON_ARRAY_LENGTHS=resources=3|targetResourceBindings=3|manualTextureCompareKernels=0|workgroupSizes=1"
    "-DEXPECTED_REFLECTION_TARGET_FIELDS=values.hlslType=RWStructuredBuffer<float>|values.bindingClass=uav|values.descriptorType=UAV|shadowAtlases.sourceType=sampler2DArrayShadow[SHADOW_COUNT]|shadowAtlases.hlslType=Texture2DArray<float>|shadowAtlases.bindingClass=srv|shadowAtlases.descriptorType=SRV|shadowAtlases.argumentIndex=2|shadowAtlases.arraySize=SHADOW_COUNT|shadowAtlases.arrayElementCount=2|rawShadowSamplers.sourceType=sampler[RAW_SAMPLER_COUNT]|rawShadowSamplers.hlslType=SamplerState|rawShadowSamplers.bindingClass=sampler|rawShadowSamplers.descriptorType=Sampler|rawShadowSamplers.argumentIndex=5|rawShadowSamplers.arraySize=RAW_SAMPLER_COUNT|rawShadowSamplers.arrayElementCount=2"
    "-DEXPECTED_REFLECTION_TARGET_ARRAY_CONTAINS=shadowAtlases.usageRoles=manual-depth-texture|rawShadowSamplers.usageRoles=manual-raw-sampler"
    "-DEXPECTED_REFLECTION_FEATURE_FIELDS=hlsl-lowering.kind=backend|compute-kernel.kind=stage|workgroup-size.kind=execution|storage-buffer.kind=resource|sampled-texture.kind=resource|fixed-array.kind=layout|descriptor-array.kind=resource|array-dimension.kind=texture|depth-compare-format.kind=texture|sampler-state.kind=resource|texture-shadow-compare-explicit-lod-manual.kind=operation|index-access.kind=operation|storage-buffer-write.kind=operation"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_build_opengl_texture_array_shadow_compare_lod_source_package
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_TEXTURE_ARRAY_SHADOW_COMPARE_LOD_UNSUPPORTED_SHADER}
    -DTARGET=opengl
    -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-opengl-texture-array-shadow-compare-lod.cglb
    -DMODE=source-package-build
    -DEXPECTED_SOURCE=backend/opengl/TextureArrayShadowCompareLodUnsupportedShader.comp.glsl
    "-DEXPECTED_SOURCE_SNIPPET=textureLod(shadowCube, vec4(vec3(0.0, 1.0, 0.0), 0.75), 3.0)"
    "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=opengl|module=TextureArrayShadowCompareLodUnsupportedShader|nativeBinary=backend/opengl/TextureArrayShadowCompareLodUnsupportedShader.glsl"
    "-DEXPECTED_REFLECTION_TARGET_FIELDS=shadowAtlas.sourceType=sampler2DArrayShadow|shadowAtlas.bindingClass=texture|shadowCube.sourceType=samplerCubeShadow|shadowCube.bindingClass=texture|shadowSampler.bindingClass=sampler|values.storageBufferLayout.layout=std430"
    -DEXPECTED_NATIVE_BINARY_STATUS=${CROSSGL_OPENGL_SOURCE_PACKAGE_NATIVE_BINARY_STATUS}
    ${CROSSGL_OPENGL_TEXTURE_ARRAY_SHADOW_COMPARE_LOD_NATIVE_BINARY}
    ${CROSSGL_OPENGL_SHADOW_LOD_NATIVE_DIAGNOSTIC}
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_build_opengl_texture_2d_array_shadow_compare_lod_source_package
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_TEXTURE_2D_ARRAY_SHADOW_COMPARE_LOD_UNSUPPORTED_SHADER}
    -DTARGET=opengl
    -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-opengl-texture-2d-array-shadow-compare-lod.cglb
    -DMODE=source-package-build
    -DEXPECTED_SOURCE=backend/opengl/Texture2DArrayShadowCompareLodUnsupportedShader.comp.glsl
    "-DEXPECTED_SOURCE_SNIPPET=textureLod(shadowAtlas, vec4(vec3(0.25, 0.5, 1.0), 0.33), 2.0)"
    "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=opengl|module=Texture2DArrayShadowCompareLodUnsupportedShader|nativeBinary=backend/opengl/Texture2DArrayShadowCompareLodUnsupportedShader.glsl"
    "-DEXPECTED_REFLECTION_TARGET_FIELDS=shadowAtlas.sourceType=sampler2DArrayShadow|shadowAtlas.bindingClass=texture|shadowSampler.bindingClass=sampler|values.storageBufferLayout.layout=std430"
    -DEXPECTED_NATIVE_BINARY_STATUS=${CROSSGL_OPENGL_SOURCE_PACKAGE_NATIVE_BINARY_STATUS}
    ${CROSSGL_OPENGL_TEXTURE_2D_ARRAY_SHADOW_COMPARE_LOD_NATIVE_BINARY}
    ${CROSSGL_OPENGL_SHADOW_LOD_NATIVE_DIAGNOSTIC}
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_build_opengl_texture_cube_shadow_compare_lod_source_package
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_TEXTURE_CUBE_SHADOW_COMPARE_LOD_UNSUPPORTED_SHADER}
    -DTARGET=opengl
    -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-opengl-texture-cube-shadow-compare-lod.cglb
    -DMODE=source-package-build
    -DEXPECTED_SOURCE=backend/opengl/TextureCubeShadowCompareLodUnsupportedShader.comp.glsl
    "-DEXPECTED_SOURCE_SNIPPET=textureLod(shadowCube, vec4(vec3(0.0, 1.0, 0.0), 0.75), 3.0)"
    "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=opengl|module=TextureCubeShadowCompareLodUnsupportedShader|nativeBinary=backend/opengl/TextureCubeShadowCompareLodUnsupportedShader.glsl"
    "-DEXPECTED_REFLECTION_TARGET_FIELDS=shadowCube.sourceType=samplerCubeShadow|shadowCube.bindingClass=texture|shadowSampler.bindingClass=sampler|values.storageBufferLayout.layout=std430"
    -DEXPECTED_NATIVE_BINARY_STATUS=${CROSSGL_OPENGL_SOURCE_PACKAGE_NATIVE_BINARY_STATUS}
    ${CROSSGL_OPENGL_TEXTURE_CUBE_SHADOW_COMPARE_LOD_NATIVE_BINARY}
    ${CROSSGL_OPENGL_SHADOW_LOD_NATIVE_DIAGNOSTIC}
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_build_opengl_texture_cube_array_shadow_compare_lod_source_package
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_TEXTURE_CUBE_ARRAY_SHADOW_COMPARE_LOD_UNSUPPORTED_SHADER}
    -DTARGET=opengl
    -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-opengl-texture-cube-array-shadow-compare-lod.cglb
    -DMODE=source-package-build
    -DEXPECTED_SOURCE=backend/opengl/TextureCubeArrayShadowCompareLodUnsupportedShader.comp.glsl
    "-DEXPECTED_SOURCE_SNIPPET=textureLod(shadowCubes, vec4(0.0, 1.0, 0.0, 2.0), 0.75, 3.0)"
    "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=opengl|module=TextureCubeArrayShadowCompareLodUnsupportedShader|nativeBinary=backend/opengl/TextureCubeArrayShadowCompareLodUnsupportedShader.glsl"
    "-DEXPECTED_REFLECTION_TARGET_FIELDS=shadowCubes.sourceType=samplerCubeArrayShadow|shadowCubes.bindingClass=texture|shadowSampler.bindingClass=sampler|values.storageBufferLayout.layout=std430"
    -DEXPECTED_NATIVE_BINARY_STATUS=${CROSSGL_OPENGL_SOURCE_PACKAGE_NATIVE_BINARY_STATUS}
    ${CROSSGL_OPENGL_TEXTURE_CUBE_ARRAY_SHADOW_COMPARE_LOD_NATIVE_BINARY}
    ${CROSSGL_OPENGL_SHADOW_LOD_NATIVE_DIAGNOSTIC}
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_build_opengl_texture_2d_shadow_compare_lod_manual_source_package
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_TEXTURE_2D_SHADOW_COMPARE_LOD_MANUAL_SHADER}
    -DTARGET=opengl
    -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-opengl-texture-2d-shadow-compare-lod-manual.cglb
    -DMODE=source-package-build
    -DEXPECTED_SOURCE=backend/opengl/Texture2DShadowCompareLodManualShader.comp.glsl
    "-DEXPECTED_SOURCE_SNIPPET=cglCompareDepth(textureLod(sampler2D(shadowMap, rawShadowSampler), vec2(0.5, 0.5), 2.0).r, 0.25, CGL_COMPARE_LESS)"
    "-DEXPECTED_REFLECTION_TARGET_ARRAY_CONTAINS=shadowMap.usageRoles=manual-depth-texture|rawShadowSampler.usageRoles=manual-raw-sampler"
    "-DEXPECTED_REFLECTION_FEATURE_FIELDS=sampled-texture.kind=resource|depth-compare-format.kind=texture|sampler-state.kind=resource|texture-shadow-compare-explicit-lod-manual.kind=operation|index-access.kind=operation|storage-buffer-write.kind=operation"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_build_opengl_texture_2d_array_shadow_compare_lod_manual_source_package
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_TEXTURE_2D_ARRAY_SHADOW_COMPARE_LOD_MANUAL_SHADER}
    -DTARGET=opengl
    -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-opengl-texture-2d-array-shadow-compare-lod-manual.cglb
    -DMODE=source-package-build
    -DEXPECTED_SOURCE=backend/opengl/Texture2DArrayShadowCompareLodManualShader.comp.glsl
    "-DEXPECTED_SOURCE_SNIPPET=cglCompareDepth(textureLod(sampler2DArray(shadowAtlas, rawShadowSampler), vec3(0.25, 0.5, 1.0), 2.0).r, 0.33, CGL_COMPARE_LESS_EQUAL)"
    "-DEXPECTED_REFLECTION_TARGET_ARRAY_CONTAINS=shadowAtlas.usageRoles=manual-depth-texture|rawShadowSampler.usageRoles=manual-raw-sampler"
    "-DEXPECTED_REFLECTION_FEATURE_FIELDS=sampled-texture.kind=resource|array-dimension.kind=texture|depth-compare-format.kind=texture|sampler-state.kind=resource|texture-shadow-compare-explicit-lod-manual.kind=operation|index-access.kind=operation|storage-buffer-write.kind=operation"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_build_opengl_texture_2d_shadow_compare_lod_manual_offset_source_package
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_TEXTURE_2D_SHADOW_COMPARE_LOD_MANUAL_OFFSET_SHADER}
    -DTARGET=opengl
    -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-opengl-texture-2d-shadow-compare-lod-manual-offset.cglb
    -DMODE=source-package-build
    -DEXPECTED_SOURCE=backend/opengl/Texture2DShadowCompareLodManualOffsetShader.comp.glsl
    "-DEXPECTED_SOURCE_SNIPPET=cglCompareDepth(textureLodOffset(sampler2D(shadowMap, rawShadowSampler), vec2(0.5, 0.5), 2.0, ivec2(1, -1)).r, 0.25, CGL_COMPARE_LESS)"
    "-DEXPECTED_REFLECTION_TARGET_ARRAY_CONTAINS=shadowMap.usageRoles=manual-depth-texture|rawShadowSampler.usageRoles=manual-raw-sampler"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_build_opengl_texture_2d_array_shadow_compare_lod_manual_offset_source_package
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_TEXTURE_2D_ARRAY_SHADOW_COMPARE_LOD_MANUAL_OFFSET_SHADER}
    -DTARGET=opengl
    -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-opengl-texture-2d-array-shadow-compare-lod-manual-offset.cglb
    -DMODE=source-package-build
    -DEXPECTED_SOURCE=backend/opengl/Texture2DArrayShadowCompareLodManualOffsetShader.comp.glsl
    "-DEXPECTED_SOURCE_SNIPPET=cglCompareDepth(textureLodOffset(sampler2DArray(shadowAtlas, rawShadowSampler), vec3(0.25, 0.5, 1.0), 2.0, ivec2(-1, 1)).r, 0.33, CGL_COMPARE_LESS_EQUAL)"
    "-DEXPECTED_REFLECTION_TARGET_ARRAY_CONTAINS=shadowAtlas.usageRoles=manual-depth-texture|rawShadowSampler.usageRoles=manual-raw-sampler"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_build_opengl_texture_2d_shadow_compare_lod_manual_gather_2x2_source_package
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_TEXTURE_2D_SHADOW_COMPARE_LOD_MANUAL_GATHER_2X2_SHADER}
    -DTARGET=opengl
    -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-opengl-texture-2d-shadow-compare-lod-manual-gather-2x2.cglb
    -DMODE=source-package-build
    -DEXPECTED_SOURCE=backend/opengl/Texture2DShadowCompareLodManualGather2x2Shader.comp.glsl
    "-DEXPECTED_SOURCE_SNIPPET=cglCompareDepth(textureLodOffset(sampler2D(shadowMap, rawShadowSampler), vec2(0.5, 0.5), 2.0, ivec2(1, 1)).r, 0.25, CGL_COMPARE_LESS)"
    "-DEXPECTED_REFLECTION_TARGET_ARRAY_CONTAINS=shadowMap.usageRoles=manual-depth-texture|rawShadowSampler.usageRoles=manual-raw-sampler"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_build_opengl_texture_2d_array_shadow_compare_lod_manual_gather_2x2_source_package
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_TEXTURE_2D_ARRAY_SHADOW_COMPARE_LOD_MANUAL_GATHER_2X2_SHADER}
    -DTARGET=opengl
    -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-opengl-texture-2d-array-shadow-compare-lod-manual-gather-2x2.cglb
    -DMODE=source-package-build
    -DEXPECTED_SOURCE=backend/opengl/Texture2DArrayShadowCompareLodManualGather2x2Shader.comp.glsl
    "-DEXPECTED_SOURCE_SNIPPET=cglCompareDepth(textureLodOffset(sampler2DArray(shadowAtlas, rawShadowSampler), vec3(0.25, 0.5, 1.0), 2.0, ivec2(1, 1)).r, 0.33, CGL_COMPARE_LESS_EQUAL)"
    "-DEXPECTED_REFLECTION_TARGET_ARRAY_CONTAINS=shadowAtlas.usageRoles=manual-depth-texture|rawShadowSampler.usageRoles=manual-raw-sampler"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_build_opengl_texture_2d_shadow_compare_lod_manual_kernel_4_source_package
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_TEXTURE_2D_SHADOW_COMPARE_LOD_MANUAL_KERNEL_4_SHADER}
    -DTARGET=opengl
    -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-opengl-texture-2d-shadow-compare-lod-manual-kernel-4.cglb
    -DMODE=source-package-build
    -DEXPECTED_SOURCE=backend/opengl/Texture2DShadowCompareLodManualKernel4Shader.comp.glsl
    "-DEXPECTED_SOURCE_SNIPPET=cglCompareDepth(textureLodOffset(sampler2D(shadowMap, rawShadowSampler), vec2(0.5, 0.5), 2.0, ivec2(1, 0)).r, 0.25, CGL_COMPARE_LESS) * 0.375"
    "-DEXPECTED_REFLECTION_TARGET_ARRAY_CONTAINS=shadowMap.usageRoles=manual-depth-texture|rawShadowSampler.usageRoles=manual-raw-sampler"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_build_opengl_texture_2d_array_shadow_compare_lod_manual_kernel_4_source_package
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_TEXTURE_2D_ARRAY_SHADOW_COMPARE_LOD_MANUAL_KERNEL_4_SHADER}
    -DTARGET=opengl
    -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-opengl-texture-2d-array-shadow-compare-lod-manual-kernel-4.cglb
    -DMODE=source-package-build
    -DEXPECTED_SOURCE=backend/opengl/Texture2DArrayShadowCompareLodManualKernel4Shader.comp.glsl
    "-DEXPECTED_SOURCE_SNIPPET=cglCompareDepth(textureLodOffset(sampler2DArray(shadowAtlas, rawShadowSampler), vec3(0.25, 0.5, 1.0), 2.0, ivec2(-1, 0)).r, 0.33, CGL_COMPARE_LESS_EQUAL) * 0.30"
    "-DEXPECTED_REFLECTION_TARGET_ARRAY_CONTAINS=shadowAtlas.usageRoles=manual-depth-texture|rawShadowSampler.usageRoles=manual-raw-sampler"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_build_opengl_texture_2d_shadow_compare_lod_manual_kernel_8_source_package
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_TEXTURE_2D_SHADOW_COMPARE_LOD_MANUAL_KERNEL_8_SHADER}
    -DTARGET=opengl
    -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-opengl-texture-2d-shadow-compare-lod-manual-kernel-8.cglb
    -DMODE=source-package-build
    -DEXPECTED_SOURCE=backend/opengl/Texture2DShadowCompareLodManualKernel8Shader.comp.glsl
    "-DEXPECTED_SOURCE_SNIPPET=cglCompareDepth(textureLodOffset(sampler2D(shadowMap, rawShadowSampler), vec2(0.5, 0.5), 2.0, ivec2(1, 1)).r, 0.25, CGL_COMPARE_LESS) * 0.3125"
    "-DEXPECTED_REFLECTION_TARGET_ARRAY_CONTAINS=shadowMap.usageRoles=manual-depth-texture|rawShadowSampler.usageRoles=manual-raw-sampler"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_build_opengl_texture_2d_array_shadow_compare_lod_manual_kernel_8_source_package
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_TEXTURE_2D_ARRAY_SHADOW_COMPARE_LOD_MANUAL_KERNEL_8_SHADER}
    -DTARGET=opengl
    -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-opengl-texture-2d-array-shadow-compare-lod-manual-kernel-8.cglb
    -DMODE=source-package-build
    -DEXPECTED_SOURCE=backend/opengl/Texture2DArrayShadowCompareLodManualKernel8Shader.comp.glsl
    "-DEXPECTED_SOURCE_SNIPPET=cglCompareDepth(textureLodOffset(sampler2DArray(shadowAtlas, rawShadowSampler), vec3(0.25, 0.5, 1.0), 2.0, ivec2(1, 1)).r, 0.33, CGL_COMPARE_LESS_EQUAL) * 0.10"
    "-DEXPECTED_REFLECTION_TARGET_ARRAY_CONTAINS=shadowAtlas.usageRoles=manual-depth-texture|rawShadowSampler.usageRoles=manual-raw-sampler"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_build_opengl_texture_2d_shadow_compare_lod_manual_kernel_list_source_package
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_TEXTURE_2D_SHADOW_COMPARE_LOD_MANUAL_KERNEL_LIST_SHADER}
    -DTARGET=opengl
    -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-opengl-texture-2d-shadow-compare-lod-manual-kernel-list.cglb
    -DMODE=source-package-build
    -DEXPECTED_SOURCE=backend/opengl/Texture2DShadowCompareLodManualKernelListShader.comp.glsl
    "-DEXPECTED_SOURCE_SNIPPET=cglCompareDepth(textureLodOffset(sampler2D(shadowMap, rawShadowSampler), vec2(0.5, 0.5), 2.0, ivec2(0, -1)).r, 0.25, CGL_COMPARE_LESS_EQUAL) * 0.15"
    "-DEXPECTED_MANIFEST_JSON_FIELDS=schemaVersion=1|target=opengl|module=Texture2DShadowCompareLodManualKernelListShader|artifacts.nativeBinaryStatus=planned"
    "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=opengl|module=Texture2DShadowCompareLodManualKernelListShader|manualTextureCompareKernelSummary.totalCount=1|manualTextureCompareKernelSummary.staticNormalizedCount=1|manualTextureCompareKernels.0.tapCount=5|manualTextureCompareKernels.0.weightClass=static-normalized|manualTextureCompareKernels.0.weightsStatic=true|manualTextureCompareKernels.0.weightsNormalized=true"
    "-DEXPECTED_REFLECTION_JSON_ARRAY_LENGTHS=resources=3|targetResourceBindings=3|manualTextureCompareKernels=1"
    "-DEXPECTED_REFLECTION_TARGET_FIELDS=shadowMap.sourceType=sampler2DShadow|shadowMap.bindingClass=texture|shadowMap.argumentIndex=2|rawShadowSampler.sourceType=sampler|rawShadowSampler.bindingClass=sampler|rawShadowSampler.abi=programResourceBinding|rawShadowSampler.argumentIndex=6|values.storageBufferLayout.layout=std430"
    "-DEXPECTED_REFLECTION_TARGET_ARRAY_CONTAINS=shadowMap.usageRoles=manual-depth-texture|rawShadowSampler.usageRoles=manual-raw-sampler"
    "-DEXPECTED_REFLECTION_FEATURE_FIELDS=sampled-texture.kind=resource|depth-compare-format.kind=texture|sampler-state.kind=resource|texture-shadow-compare-explicit-lod-manual.kind=operation|texture-shadow-compare-explicit-lod-manual-kernel-list.kind=operation|index-access.kind=operation|storage-buffer-write.kind=operation"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_build_opengl_texture_cube_shadow_compare_lod_manual_source_package
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_TEXTURE_CUBE_SHADOW_COMPARE_LOD_MANUAL_SHADER}
    -DTARGET=opengl
    -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-opengl-texture-cube-shadow-compare-lod-manual.cglb
    -DMODE=source-package-build
    -DEXPECTED_SOURCE=backend/opengl/TextureCubeShadowCompareLodManualShader.comp.glsl
    "-DEXPECTED_SOURCE_SNIPPET=cglCompareDepth(textureLod(samplerCube(shadowCube, rawShadowSampler), vec3(0.0, 1.0, 0.0), 1.0).r, 0.5, CGL_COMPARE_GREATER_EQUAL)"
    "-DEXPECTED_REFLECTION_TARGET_ARRAY_CONTAINS=shadowCube.usageRoles=manual-depth-texture|rawShadowSampler.usageRoles=manual-raw-sampler"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_build_opengl_texture_cube_array_shadow_compare_lod_manual_source_package
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_TEXTURE_CUBE_ARRAY_SHADOW_COMPARE_LOD_MANUAL_SHADER}
    -DTARGET=opengl
    -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-opengl-texture-cube-array-shadow-compare-lod-manual.cglb
    -DMODE=source-package-build
    -DEXPECTED_SOURCE=backend/opengl/TextureCubeArrayShadowCompareLodManualShader.comp.glsl
    "-DEXPECTED_SOURCE_SNIPPET=cglCompareDepth(textureLod(samplerCubeArray(shadowCubes, rawShadowSampler), vec4(0.0, 1.0, 0.0, 2.0), 3.0).r, 0.75, CGL_COMPARE_GREATER)"
    "-DEXPECTED_REFLECTION_TARGET_ARRAY_CONTAINS=shadowCubes.usageRoles=manual-depth-texture|rawShadowSampler.usageRoles=manual-raw-sampler"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_build_opengl_texture_compare_lod_manual_descriptor_array_source_package
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_TEXTURE_COMPARE_LOD_MANUAL_DESCRIPTOR_ARRAY_SHADER}
    -DTARGET=opengl
    -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-opengl-texture-compare-lod-manual-descriptor-array.cglb
    -DMODE=source-package-build
    -DEXPECTED_SOURCE=backend/opengl/TextureCompareLodManualDescriptorArrayShader.comp.glsl
    "-DEXPECTED_SOURCE_SNIPPET=cglCompareDepth(textureLod(sampler2DArray(shadowAtlases[1], rawShadowSamplers[0]), vec3(0.25, 0.5, 1.0), 2.0).r, 0.33, CGL_COMPARE_LESS_EQUAL)"
    "-DEXPECTED_MANIFEST_JSON_FIELDS=schemaVersion=1|target=opengl|module=TextureCompareLodManualDescriptorArrayShader|artifacts.nativeBinaryStatus=planned"
    "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=opengl|module=TextureCompareLodManualDescriptorArrayShader|manualTextureCompareKernelSummary.totalCount=0"
    "-DEXPECTED_REFLECTION_JSON_ARRAY_LENGTHS=resources=3|targetResourceBindings=3|manualTextureCompareKernels=0"
    "-DEXPECTED_REFLECTION_TARGET_FIELDS=shadowAtlases.sourceType=sampler2DArrayShadow[SHADOW_COUNT]|shadowAtlases.bindingClass=texture|shadowAtlases.argumentIndex=2|shadowAtlases.arraySize=SHADOW_COUNT|shadowAtlases.arrayElementCount=2|shadowAtlases.arrayDimensions.0.elementCount=2|rawShadowSamplers.sourceType=sampler[RAW_SAMPLER_COUNT]|rawShadowSamplers.bindingClass=sampler|rawShadowSamplers.argumentIndex=5|rawShadowSamplers.arraySize=RAW_SAMPLER_COUNT|rawShadowSamplers.arrayElementCount=2|rawShadowSamplers.arrayDimensions.0.elementCount=2|values.storageBufferLayout.layout=std430"
    "-DEXPECTED_REFLECTION_TARGET_ARRAY_CONTAINS=shadowAtlases.usageRoles=manual-depth-texture|rawShadowSamplers.usageRoles=manual-raw-sampler"
    "-DEXPECTED_REFLECTION_FEATURE_FIELDS=sampled-texture.kind=resource|descriptor-array.kind=resource|array-dimension.kind=texture|depth-compare-format.kind=texture|sampler-state.kind=resource|texture-shadow-compare-explicit-lod-manual.kind=operation|index-access.kind=operation|storage-buffer-write.kind=operation"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_build_directx_texture_compare_descriptor_array_lod_source_package
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_TEXTURE_COMPARE_DESCRIPTOR_ARRAY_LOD_SHADER}
    -DTARGET=directx
    -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-directx-texture-compare-descriptor-array-lod.cglb
    -DMODE=source-package-build
    -DEXPECTED_SOURCE=backend/directx/TextureCompareDescriptorArrayLodShader.hlsl
    "-DEXPECTED_SOURCE_SNIPPET=shadowMaps[1].SampleCmpLevel(shadowSamplers[0]"
    "-DEXPECTED_MANIFEST_JSON_FIELDS=schemaVersion=1|target=directx|module=TextureCompareDescriptorArrayLodShader|artifacts.backendSource=backend/directx/TextureCompareDescriptorArrayLodShader.hlsl|artifacts.nativeBinary=backend/directx/TextureCompareDescriptorArrayLodShader.dxil"
    "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=directx|module=TextureCompareDescriptorArrayLodShader|nativeBinary=backend/directx/TextureCompareDescriptorArrayLodShader.dxil|manualTextureCompareKernelSummary.totalCount=0"
    "-DEXPECTED_REFLECTION_JSON_ARRAY_LENGTHS=resources=3|targetResourceBindings=3|manualTextureCompareKernels=0|workgroupSizes=1"
    "-DEXPECTED_REFLECTION_TARGET_FIELDS=values.hlslType=RWStructuredBuffer<float>|values.bindingClass=uav|values.descriptorType=UAV|shadowMaps.sourceType=sampler2DShadow[2]|shadowMaps.hlslType=Texture2D<float>|shadowMaps.addressSpace=shader-resource|shadowMaps.abi=registerBinding|shadowMaps.bindingClass=srv|shadowMaps.descriptorType=SRV|shadowMaps.argumentIndex=2|shadowMaps.arraySize=2|shadowMaps.arrayElementCount=2|shadowSamplers.sourceType=sampler[2]|shadowSamplers.hlslType=SamplerComparisonState|shadowSamplers.addressSpace=sampler|shadowSamplers.abi=registerBinding|shadowSamplers.bindingClass=sampler|shadowSamplers.descriptorType=Sampler|shadowSamplers.argumentIndex=5|shadowSamplers.arraySize=2|shadowSamplers.arrayElementCount=2"
    "-DEXPECTED_REFLECTION_FEATURE_FIELDS=hlsl-lowering.kind=backend|compute-kernel.kind=stage|workgroup-size.kind=execution|storage-buffer.kind=resource|sampled-texture.kind=resource|fixed-array.kind=layout|descriptor-array.kind=resource|depth-compare-format.kind=texture|sampler-state.kind=resource|texture-shadow-compare.kind=operation|texture-shadow-compare-explicit-lod.kind=operation|index-access.kind=operation|storage-buffer-write.kind=operation"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_build_opengl_texture_compare_descriptor_array_lod_source_package
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_TEXTURE_COMPARE_DESCRIPTOR_ARRAY_LOD_SHADER}
    -DTARGET=opengl
    -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-opengl-texture-compare-descriptor-array-lod.cglb
    -DMODE=source-package-build
    -DEXPECTED_SOURCE=backend/opengl/TextureCompareDescriptorArrayLodShader.comp.glsl
    "-DEXPECTED_SOURCE_SNIPPET=textureLod(sampler2DShadow(shadowMaps[1], shadowSamplers[0])"
    "-DEXPECTED_MANIFEST_JSON_FIELDS=schemaVersion=1|target=opengl|module=TextureCompareDescriptorArrayLodShader|artifacts.nativeBinaryStatus=planned"
    "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=opengl|module=TextureCompareDescriptorArrayLodShader|manualTextureCompareKernelSummary.totalCount=0"
    "-DEXPECTED_REFLECTION_JSON_ARRAY_LENGTHS=resources=3|targetResourceBindings=3|manualTextureCompareKernels=0"
    "-DEXPECTED_REFLECTION_TARGET_FIELDS=shadowMaps.sourceType=sampler2DShadow[2]|shadowMaps.bindingClass=texture|shadowMaps.argumentIndex=2|shadowMaps.arraySize=2|shadowMaps.arrayElementCount=2|shadowMaps.arrayDimensions.0.source=2|shadowMaps.arrayDimensions.0.kind=fixed|shadowMaps.arrayDimensions.0.elementCount=2|shadowSamplers.sourceType=sampler[2]|shadowSamplers.bindingClass=sampler|shadowSamplers.argumentIndex=5|shadowSamplers.arraySize=2|shadowSamplers.arrayElementCount=2|values.storageBufferLayout.layout=std430"
    "-DEXPECTED_REFLECTION_FEATURE_FIELDS=sampled-texture.kind=resource|descriptor-array.kind=resource|depth-compare-format.kind=texture|sampler-state.kind=resource|texture-shadow-compare.kind=operation|texture-shadow-compare-explicit-lod.kind=operation|index-access.kind=operation|storage-buffer-write.kind=operation"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_build_directx_texture_array_compare_descriptor_array_lod_source_package
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_TEXTURE_ARRAY_COMPARE_DESCRIPTOR_ARRAY_LOD_SHADER}
    -DTARGET=directx
    -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-directx-texture-array-compare-descriptor-array-lod.cglb
    -DMODE=source-package-build
    -DEXPECTED_SOURCE=backend/directx/TextureArrayCompareDescriptorArrayLodShader.hlsl
    "-DEXPECTED_SOURCE_SNIPPET=shadowAtlases[1].SampleCmpLevel(shadowSamplers[0]"
    "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=directx|module=TextureArrayCompareDescriptorArrayLodShader"
    "-DEXPECTED_REFLECTION_TARGET_FIELDS=shadowAtlases.sourceType=sampler2DArrayShadow[SHADOW_COUNT]|shadowAtlases.hlslType=Texture2DArray<float>|shadowAtlases.bindingClass=srv|shadowAtlases.descriptorType=SRV|shadowAtlases.arraySize=SHADOW_COUNT|shadowAtlases.arrayElementCount=2|shadowSamplers.hlslType=SamplerComparisonState|shadowSamplers.bindingClass=sampler|shadowSamplers.arrayElementCount=2"
    "-DEXPECTED_REFLECTION_FEATURE_FIELDS=sampled-texture.kind=resource|fixed-array.kind=layout|descriptor-array.kind=resource|array-dimension.kind=texture|depth-compare-format.kind=texture|sampler-state.kind=resource|texture-shadow-compare.kind=operation|texture-shadow-compare-explicit-lod.kind=operation|index-access.kind=operation|storage-buffer-write.kind=operation"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_build_opengl_texture_array_compare_descriptor_array_lod_source_package
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_TEXTURE_ARRAY_COMPARE_DESCRIPTOR_ARRAY_LOD_SHADER}
    -DTARGET=opengl
    -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-opengl-texture-array-compare-descriptor-array-lod.cglb
    -DMODE=source-package-build
    -DEXPECTED_SOURCE=backend/opengl/TextureArrayCompareDescriptorArrayLodShader.comp.glsl
    "-DEXPECTED_SOURCE_SNIPPET=textureLod(sampler2DArrayShadow(shadowAtlases[1], shadowSamplers[0]), vec4(vec3(0.25, 0.5, 1.0), 0.33), 2.0)"
    "-DEXPECTED_MANIFEST_JSON_FIELDS=schemaVersion=1|target=opengl|module=TextureArrayCompareDescriptorArrayLodShader|artifacts.nativeBinaryStatus=planned"
    "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=opengl|module=TextureArrayCompareDescriptorArrayLodShader|manualTextureCompareKernelSummary.totalCount=0"
    "-DEXPECTED_REFLECTION_JSON_ARRAY_LENGTHS=resources=3|targetResourceBindings=3|manualTextureCompareKernels=0"
    "-DEXPECTED_REFLECTION_TARGET_FIELDS=shadowAtlases.sourceType=sampler2DArrayShadow[SHADOW_COUNT]|shadowAtlases.bindingClass=texture|shadowAtlases.argumentIndex=2|shadowAtlases.arraySize=SHADOW_COUNT|shadowAtlases.arrayElementCount=2|shadowAtlases.arrayDimensions.0.elementCount=2|shadowSamplers.sourceType=sampler[2]|shadowSamplers.bindingClass=sampler|shadowSamplers.argumentIndex=5|shadowSamplers.arraySize=2|shadowSamplers.arrayElementCount=2|values.storageBufferLayout.layout=std430"
    "-DEXPECTED_REFLECTION_FEATURE_FIELDS=sampled-texture.kind=resource|fixed-array.kind=layout|descriptor-array.kind=resource|array-dimension.kind=texture|depth-compare-format.kind=texture|sampler-state.kind=resource|texture-shadow-compare.kind=operation|texture-shadow-compare-explicit-lod.kind=operation|index-access.kind=operation|storage-buffer-write.kind=operation"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_build_directx_texture_cube_compare_descriptor_array_lod_source_package
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_TEXTURE_CUBE_COMPARE_DESCRIPTOR_ARRAY_LOD_SHADER}
    -DTARGET=directx
    -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-directx-texture-cube-compare-descriptor-array-lod.cglb
    -DMODE=source-package-build
    -DEXPECTED_SOURCE=backend/directx/TextureCubeCompareDescriptorArrayLodShader.hlsl
    "-DEXPECTED_SOURCE_SNIPPET=shadowCubeArrays[1].SampleCmpLevel(shadowSamplers[0]"
    "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=directx|module=TextureCubeCompareDescriptorArrayLodShader"
    "-DEXPECTED_REFLECTION_TARGET_FIELDS=shadowCubeArrays.sourceType=samplerCubeArrayShadow[SHADOW_COUNT]|shadowCubeArrays.hlslType=TextureCubeArray<float>|shadowCubeArrays.bindingClass=srv|shadowCubeArrays.descriptorType=SRV|shadowCubeArrays.arraySize=SHADOW_COUNT|shadowCubeArrays.arrayElementCount=2|shadowSamplers.hlslType=SamplerComparisonState|shadowSamplers.bindingClass=sampler|shadowSamplers.arrayElementCount=2"
    "-DEXPECTED_REFLECTION_FEATURE_FIELDS=sampled-texture.kind=resource|fixed-array.kind=layout|descriptor-array.kind=resource|cube-dimension.kind=texture|array-dimension.kind=texture|depth-compare-format.kind=texture|sampler-state.kind=resource|texture-shadow-compare.kind=operation|texture-shadow-compare-explicit-lod.kind=operation|index-access.kind=operation|scalar-arithmetic.kind=operation|storage-buffer-write.kind=operation"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_build_opengl_texture_cube_compare_descriptor_array_lod_source_package
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_TEXTURE_CUBE_COMPARE_DESCRIPTOR_ARRAY_LOD_SHADER}
    -DTARGET=opengl
    -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-opengl-texture-cube-compare-descriptor-array-lod.cglb
    -DMODE=source-package-build
    -DEXPECTED_SOURCE=backend/opengl/TextureCubeCompareDescriptorArrayLodShader.comp.glsl
    "-DEXPECTED_SOURCE_SNIPPET=textureLod(samplerCubeArrayShadow(shadowCubeArrays[1], shadowSamplers[0]), vec4(0.0, 1.0, 0.0, 2.0), 0.5, 4.0)"
    "-DEXPECTED_MANIFEST_JSON_FIELDS=schemaVersion=1|target=opengl|module=TextureCubeCompareDescriptorArrayLodShader|artifacts.nativeBinaryStatus=planned"
    "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=opengl|module=TextureCubeCompareDescriptorArrayLodShader|manualTextureCompareKernelSummary.totalCount=0"
    "-DEXPECTED_REFLECTION_JSON_ARRAY_LENGTHS=resources=4|targetResourceBindings=4|manualTextureCompareKernels=0"
    "-DEXPECTED_REFLECTION_TARGET_FIELDS=shadowCubes.sourceType=samplerCubeShadow[SHADOW_COUNT]|shadowCubes.bindingClass=texture|shadowCubes.argumentIndex=2|shadowCubes.arraySize=SHADOW_COUNT|shadowCubes.arrayElementCount=2|shadowCubeArrays.sourceType=samplerCubeArrayShadow[SHADOW_COUNT]|shadowCubeArrays.bindingClass=texture|shadowCubeArrays.argumentIndex=4|shadowCubeArrays.arraySize=SHADOW_COUNT|shadowCubeArrays.arrayElementCount=2|shadowSamplers.sourceType=sampler[2]|shadowSamplers.bindingClass=sampler|shadowSamplers.argumentIndex=5|shadowSamplers.arraySize=2|shadowSamplers.arrayElementCount=2|values.storageBufferLayout.layout=std430"
    "-DEXPECTED_REFLECTION_FEATURE_FIELDS=sampled-texture.kind=resource|fixed-array.kind=layout|descriptor-array.kind=resource|cube-dimension.kind=texture|array-dimension.kind=texture|depth-compare-format.kind=texture|sampler-state.kind=resource|texture-shadow-compare.kind=operation|texture-shadow-compare-explicit-lod.kind=operation|index-access.kind=operation|scalar-arithmetic.kind=operation|storage-buffer-write.kind=operation"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_build_directx_mixed_texture_compare_descriptor_array_source_package
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_MIXED_TEXTURE_COMPARE_DESCRIPTOR_ARRAY_SHADER}
    -DTARGET=directx
    -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-directx-mixed-texture-compare-descriptor-array.cglb
    -DMODE=source-package-build
    -DEXPECTED_SOURCE=backend/directx/MixedTextureCompareDescriptorArrayShader.hlsl
    "-DEXPECTED_SOURCE_SNIPPET=SamplerComparisonState shadowSamplers[2]"
    "-DEXPECTED_MANIFEST_JSON_FIELDS=schemaVersion=1|target=directx|module=MixedTextureCompareDescriptorArrayShader|artifacts.backendSource=backend/directx/MixedTextureCompareDescriptorArrayShader.hlsl|artifacts.nativeBinary=backend/directx/MixedTextureCompareDescriptorArrayShader.dxil"
    "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=directx|module=MixedTextureCompareDescriptorArrayShader|nativeBinary=backend/directx/MixedTextureCompareDescriptorArrayShader.dxil|manualTextureCompareKernelSummary.totalCount=0"
    "-DEXPECTED_REFLECTION_JSON_ARRAY_LENGTHS=resources=5|targetResourceBindings=5|manualTextureCompareKernels=0|workgroupSizes=1"
    "-DEXPECTED_REFLECTION_TARGET_FIELDS=values.hlslType=RWStructuredBuffer<float4>|values.bindingClass=uav|values.descriptorType=UAV|colorMaps.sourceType=sampler2D[RESOURCE_COUNT]|colorMaps.hlslType=Texture2D<float4>|colorMaps.bindingClass=srv|colorMaps.descriptorType=SRV|colorMaps.argumentIndex=2|colorMaps.arraySize=RESOURCE_COUNT|colorMaps.arrayElementCount=2|shadowMaps.sourceType=sampler2DShadow[RESOURCE_COUNT]|shadowMaps.hlslType=Texture2D<float>|shadowMaps.bindingClass=srv|shadowMaps.descriptorType=SRV|shadowMaps.argumentIndex=3|shadowMaps.arraySize=RESOURCE_COUNT|shadowMaps.arrayElementCount=2|linearSamplers.sourceType=sampler[2]|linearSamplers.hlslType=SamplerState|linearSamplers.bindingClass=sampler|linearSamplers.descriptorType=Sampler|linearSamplers.argumentIndex=5|linearSamplers.arraySize=2|linearSamplers.arrayElementCount=2|shadowSamplers.sourceType=sampler[2]|shadowSamplers.hlslType=SamplerComparisonState|shadowSamplers.bindingClass=sampler|shadowSamplers.descriptorType=Sampler|shadowSamplers.argumentIndex=6|shadowSamplers.arraySize=2|shadowSamplers.arrayElementCount=2"
    "-DEXPECTED_REFLECTION_FEATURE_FIELDS=hlsl-lowering.kind=backend|compute-kernel.kind=stage|workgroup-size.kind=execution|storage-buffer.kind=resource|vector-storage-buffer.kind=layout|sampled-texture.kind=resource|fixed-array.kind=layout|descriptor-array.kind=resource|depth-compare-format.kind=texture|sampler-state.kind=resource|texture-sample.kind=operation|texture-explicit-lod.kind=operation|texture-shadow-compare.kind=operation|texture-shadow-compare-explicit-lod.kind=operation|index-access.kind=operation|storage-buffer-write.kind=operation|vector-arithmetic.kind=operation"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_build_opengl_mixed_texture_compare_descriptor_array_source_package
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_MIXED_TEXTURE_COMPARE_DESCRIPTOR_ARRAY_SHADER}
    -DTARGET=opengl
    -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-opengl-mixed-texture-compare-descriptor-array.cglb
    -DMODE=source-package-build
    -DEXPECTED_SOURCE=backend/opengl/MixedTextureCompareDescriptorArrayShader.comp.glsl
    "-DEXPECTED_SOURCE_SNIPPET=textureLod(sampler2DShadow(shadowMaps[0], shadowSamplers[1])"
    "-DEXPECTED_MANIFEST_JSON_FIELDS=schemaVersion=1|target=opengl|module=MixedTextureCompareDescriptorArrayShader|artifacts.nativeBinaryStatus=planned"
    "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=opengl|module=MixedTextureCompareDescriptorArrayShader|manualTextureCompareKernelSummary.totalCount=0"
    "-DEXPECTED_REFLECTION_JSON_ARRAY_LENGTHS=resources=5|targetResourceBindings=5|manualTextureCompareKernels=0"
    "-DEXPECTED_REFLECTION_TARGET_FIELDS=colorMaps.sourceType=sampler2D[RESOURCE_COUNT]|colorMaps.bindingClass=texture|colorMaps.argumentIndex=2|colorMaps.arraySize=RESOURCE_COUNT|colorMaps.arrayElementCount=2|shadowMaps.sourceType=sampler2DShadow[RESOURCE_COUNT]|shadowMaps.bindingClass=texture|shadowMaps.argumentIndex=3|shadowMaps.arraySize=RESOURCE_COUNT|shadowMaps.arrayElementCount=2|linearSamplers.sourceType=sampler[2]|linearSamplers.bindingClass=sampler|linearSamplers.argumentIndex=5|linearSamplers.arrayElementCount=2|shadowSamplers.sourceType=sampler[2]|shadowSamplers.bindingClass=sampler|shadowSamplers.argumentIndex=6|shadowSamplers.arrayElementCount=2|values.storageBufferLayout.layout=std430|values.storageBufferLayout.elementType=vec4"
    "-DEXPECTED_REFLECTION_FEATURE_FIELDS=sampled-texture.kind=resource|descriptor-array.kind=resource|depth-compare-format.kind=texture|sampler-state.kind=resource|texture-sample.kind=operation|texture-explicit-lod.kind=operation|texture-shadow-compare.kind=operation|texture-shadow-compare-explicit-lod.kind=operation|vector-arithmetic.kind=operation|storage-buffer-write.kind=operation"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_build_directx_mixed_texture_manual_compare_descriptor_array_source_package
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_MIXED_TEXTURE_MANUAL_COMPARE_DESCRIPTOR_ARRAY_SHADER}
    -DTARGET=directx
    -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-directx-mixed-texture-manual-compare-descriptor-array.cglb
    -DMODE=source-package-build
    -DEXPECTED_SOURCE=backend/directx/MixedTextureManualCompareDescriptorArrayShader.hlsl
    "-DEXPECTED_SOURCE_SNIPPET=cglCompareDepth(shadowAtlases[1].SampleLevel(rawShadowSamplers[0], float3(0.25, 0.5, 1.0), 2.0), 0.33, CGL_COMPARE_LESS_EQUAL)"
    "-DEXPECTED_MANIFEST_JSON_FIELDS=schemaVersion=1|target=directx|module=MixedTextureManualCompareDescriptorArrayShader|artifacts.backendSource=backend/directx/MixedTextureManualCompareDescriptorArrayShader.hlsl|artifacts.nativeBinary=backend/directx/MixedTextureManualCompareDescriptorArrayShader.dxil"
    "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=directx|module=MixedTextureManualCompareDescriptorArrayShader|nativeBinary=backend/directx/MixedTextureManualCompareDescriptorArrayShader.dxil|manualTextureCompareKernelSummary.totalCount=0"
    "-DEXPECTED_REFLECTION_JSON_ARRAY_LENGTHS=resources=7|targetResourceBindings=7|manualTextureCompareKernels=0|workgroupSizes=1"
    "-DEXPECTED_REFLECTION_TARGET_FIELDS=values.hlslType=RWStructuredBuffer<float4>|values.bindingClass=uav|values.descriptorType=UAV|colorMaps.sourceType=sampler2D[RESOURCE_COUNT]|colorMaps.hlslType=Texture2D<float4>|colorMaps.bindingClass=srv|colorMaps.descriptorType=SRV|colorMaps.argumentIndex=2|colorMaps.arrayElementCount=2|shadowMaps.sourceType=sampler2DShadow[RESOURCE_COUNT]|shadowMaps.hlslType=Texture2D<float>|shadowMaps.bindingClass=srv|shadowMaps.descriptorType=SRV|shadowMaps.argumentIndex=4|shadowMaps.arrayElementCount=2|shadowAtlases.sourceType=sampler2DArrayShadow[RESOURCE_COUNT]|shadowAtlases.hlslType=Texture2DArray<float>|shadowAtlases.bindingClass=srv|shadowAtlases.descriptorType=SRV|shadowAtlases.argumentIndex=6|shadowAtlases.arrayElementCount=2|linearSamplers.hlslType=SamplerState|linearSamplers.bindingClass=sampler|linearSamplers.arrayElementCount=2|shadowSamplers.hlslType=SamplerComparisonState|shadowSamplers.bindingClass=sampler|shadowSamplers.arrayElementCount=2|rawShadowSamplers.sourceType=sampler[RAW_SAMPLER_COUNT]|rawShadowSamplers.hlslType=SamplerState|rawShadowSamplers.bindingClass=sampler|rawShadowSamplers.descriptorType=Sampler|rawShadowSamplers.argumentIndex=14|rawShadowSamplers.arrayElementCount=2"
    "-DEXPECTED_REFLECTION_TARGET_ARRAY_CONTAINS=shadowAtlases.usageRoles=manual-depth-texture|rawShadowSamplers.usageRoles=manual-raw-sampler"
    "-DEXPECTED_REFLECTION_FEATURE_FIELDS=hlsl-lowering.kind=backend|compute-kernel.kind=stage|workgroup-size.kind=execution|storage-buffer.kind=resource|vector-storage-buffer.kind=layout|sampled-texture.kind=resource|fixed-array.kind=layout|descriptor-array.kind=resource|array-dimension.kind=texture|depth-compare-format.kind=texture|sampler-state.kind=resource|texture-sample.kind=operation|texture-explicit-lod.kind=operation|texture-shadow-compare.kind=operation|texture-shadow-compare-explicit-lod.kind=operation|texture-shadow-compare-explicit-lod-manual.kind=operation|index-access.kind=operation|storage-buffer-write.kind=operation|vector-arithmetic.kind=operation"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_build_opengl_mixed_texture_manual_compare_descriptor_array_source_package
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_MIXED_TEXTURE_MANUAL_COMPARE_DESCRIPTOR_ARRAY_SHADER}
    -DTARGET=opengl
    -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-opengl-mixed-texture-manual-compare-descriptor-array.cglb
    -DMODE=source-package-build
    -DEXPECTED_SOURCE=backend/opengl/MixedTextureManualCompareDescriptorArrayShader.comp.glsl
    "-DEXPECTED_SOURCE_SNIPPET=cglCompareDepth(textureLod(sampler2DArray(shadowAtlases[1], rawShadowSamplers[0]), vec3(0.25, 0.5, 1.0), 2.0).r, 0.33, CGL_COMPARE_LESS_EQUAL)"
    "-DEXPECTED_MANIFEST_JSON_FIELDS=schemaVersion=1|target=opengl|module=MixedTextureManualCompareDescriptorArrayShader|artifacts.nativeBinaryStatus=planned"
    "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=opengl|module=MixedTextureManualCompareDescriptorArrayShader|manualTextureCompareKernelSummary.totalCount=0"
    "-DEXPECTED_REFLECTION_JSON_ARRAY_LENGTHS=resources=7|targetResourceBindings=7|manualTextureCompareKernels=0"
    "-DEXPECTED_REFLECTION_TARGET_FIELDS=colorMaps.sourceType=sampler2D[RESOURCE_COUNT]|colorMaps.bindingClass=texture|colorMaps.argumentIndex=2|colorMaps.arrayElementCount=2|shadowMaps.sourceType=sampler2DShadow[RESOURCE_COUNT]|shadowMaps.bindingClass=texture|shadowMaps.argumentIndex=4|shadowMaps.arrayElementCount=2|shadowAtlases.sourceType=sampler2DArrayShadow[RESOURCE_COUNT]|shadowAtlases.bindingClass=texture|shadowAtlases.argumentIndex=6|shadowAtlases.arraySize=RESOURCE_COUNT|shadowAtlases.arrayElementCount=2|linearSamplers.sourceType=sampler[RESOURCE_COUNT]|linearSamplers.bindingClass=sampler|linearSamplers.argumentIndex=10|linearSamplers.arrayElementCount=2|shadowSamplers.sourceType=sampler[RESOURCE_COUNT]|shadowSamplers.bindingClass=sampler|shadowSamplers.argumentIndex=12|shadowSamplers.arrayElementCount=2|rawShadowSamplers.sourceType=sampler[RAW_SAMPLER_COUNT]|rawShadowSamplers.bindingClass=sampler|rawShadowSamplers.argumentIndex=14|rawShadowSamplers.arrayElementCount=2|values.storageBufferLayout.layout=std430|values.storageBufferLayout.elementType=vec4"
    "-DEXPECTED_REFLECTION_TARGET_ARRAY_CONTAINS=shadowAtlases.usageRoles=manual-depth-texture|rawShadowSamplers.usageRoles=manual-raw-sampler"
    "-DEXPECTED_REFLECTION_FEATURE_FIELDS=sampled-texture.kind=resource|descriptor-array.kind=resource|depth-compare-format.kind=texture|array-dimension.kind=texture|sampler-state.kind=resource|texture-sample.kind=operation|texture-explicit-lod.kind=operation|texture-shadow-compare.kind=operation|texture-shadow-compare-explicit-lod.kind=operation|texture-shadow-compare-explicit-lod-manual.kind=operation|vector-arithmetic.kind=operation|storage-buffer-write.kind=operation"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_build_directx_mixed_sampler_usage_source_package
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_DIRECTX_MIXED_SAMPLER_USAGE_UNSUPPORTED_SHADER}
    -DTARGET=directx
    -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-directx-mixed-sampler-usage.cglb
    -DMODE=source-package-build
    -DEXPECTED_SOURCE=backend/directx/DirectXMixedSamplerUsageUnsupportedShader.hlsl
    "-DEXPECTED_SOURCE_SNIPPET=SamplerComparisonState sharedSampler_cglComparison : register(s5, space0);"
    "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=directx|module=DirectXMixedSamplerUsageUnsupportedShader"
    "-DEXPECTED_REFLECTION_TARGET_FIELDS=colorMap.hlslType=Texture2D<float4>|colorMap.bindingClass=srv|shadowMap.hlslType=Texture2D<float>|shadowMap.bindingClass=srv|sharedSampler.sourceType=sampler|sharedSampler.hlslType=SamplerState|sharedSampler.bindingClass=sampler|sharedSampler.descriptorType=Sampler"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_build_opengl_mixed_sampler_usage_source_package
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_DIRECTX_MIXED_SAMPLER_USAGE_UNSUPPORTED_SHADER}
    -DTARGET=opengl
    -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-opengl-mixed-sampler-usage.cglb
    -DMODE=source-package-build
    -DEXPECTED_SOURCE=backend/opengl/DirectXMixedSamplerUsageUnsupportedShader.comp.glsl
    "-DEXPECTED_SOURCE_SNIPPET=texture(sampler2DShadow(shadowMap, sharedSampler)"
    "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=opengl|module=DirectXMixedSamplerUsageUnsupportedShader"
    "-DEXPECTED_REFLECTION_TARGET_FIELDS=colorMap.bindingClass=texture|shadowMap.bindingClass=texture|sharedSampler.sourceType=sampler|sharedSampler.bindingClass=sampler|sharedSampler.abi=programResourceBinding|values.storageBufferLayout.layout=std430"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_build_directx_mixed_manual_sampler_usage_source_package
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_DIRECTX_MIXED_MANUAL_SAMPLER_USAGE_UNSUPPORTED_SHADER}
    -DTARGET=directx
    -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-directx-mixed-manual-sampler-usage.cglb
    -DMODE=source-package-build
    -DEXPECTED_SOURCE=backend/directx/DirectXMixedManualSamplerUsageUnsupportedShader.hlsl
    "-DEXPECTED_SOURCE_SNIPPET=SamplerComparisonState sharedShadowSampler_cglComparison : register(s5, space0);"
    "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=directx|module=DirectXMixedManualSamplerUsageUnsupportedShader|manualTextureCompareKernelSummary.totalCount=0"
    "-DEXPECTED_REFLECTION_TARGET_FIELDS=shadowMap.hlslType=Texture2D<float>|shadowMap.bindingClass=srv|shadowAtlas.hlslType=Texture2DArray<float>|shadowAtlas.bindingClass=srv|sharedShadowSampler.hlslType=SamplerState|sharedShadowSampler.bindingClass=sampler|sharedShadowSampler.descriptorType=Sampler"
    "-DEXPECTED_REFLECTION_TARGET_ARRAY_CONTAINS=shadowAtlas.usageRoles=manual-depth-texture|sharedShadowSampler.usageRoles=manual-raw-sampler"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_build_opengl_mixed_manual_sampler_usage_source_package
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_DIRECTX_MIXED_MANUAL_SAMPLER_USAGE_UNSUPPORTED_SHADER}
    -DTARGET=opengl
    -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-opengl-mixed-manual-sampler-usage.cglb
    -DMODE=source-package-build
    -DEXPECTED_SOURCE=backend/opengl/DirectXMixedManualSamplerUsageUnsupportedShader.comp.glsl
    "-DEXPECTED_SOURCE_SNIPPET=cglCompareDepth(textureLod(sampler2DArray(shadowAtlas, sharedShadowSampler), vec3(0.25, 0.5, 1.0), 2.0).r, 0.33, CGL_COMPARE_LESS_EQUAL)"
    "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=opengl|module=DirectXMixedManualSamplerUsageUnsupportedShader"
    "-DEXPECTED_REFLECTION_TARGET_FIELDS=shadowAtlas.bindingClass=texture|sharedShadowSampler.bindingClass=sampler|sharedShadowSampler.abi=programResourceBinding|values.storageBufferLayout.layout=std430"
    "-DEXPECTED_REFLECTION_TARGET_ARRAY_CONTAINS=shadowAtlas.usageRoles=manual-depth-texture|sharedShadowSampler.usageRoles=manual-raw-sampler"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_build_directx_mixed_sampler_array_usage_source_package
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_DIRECTX_MIXED_SAMPLER_ARRAY_USAGE_UNSUPPORTED_SHADER}
    -DTARGET=directx
    -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-directx-mixed-sampler-array-usage.cglb
    -DMODE=source-package-build
    -DEXPECTED_SOURCE=backend/directx/DirectXMixedSamplerArrayUsageUnsupportedShader.hlsl
    "-DEXPECTED_SOURCE_SNIPPET=SamplerComparisonState sharedSamplers_cglComparison[SAMPLER_COUNT] : register(s5, space0);"
    "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=directx|module=DirectXMixedSamplerArrayUsageUnsupportedShader"
    "-DEXPECTED_REFLECTION_TARGET_FIELDS=colorMap.hlslType=Texture2D<float4>|colorMap.bindingClass=srv|shadowMap.hlslType=Texture2D<float>|shadowMap.bindingClass=srv|sharedSamplers.sourceType=sampler[SAMPLER_COUNT]|sharedSamplers.bindingClass=sampler|sharedSamplers.descriptorType=Sampler|sharedSamplers.arraySize=SAMPLER_COUNT|sharedSamplers.arrayElementCount=2"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_build_opengl_mixed_sampler_array_usage_source_package
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_DIRECTX_MIXED_SAMPLER_ARRAY_USAGE_UNSUPPORTED_SHADER}
    -DTARGET=opengl
    -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-opengl-mixed-sampler-array-usage.cglb
    -DMODE=source-package-build
    -DEXPECTED_SOURCE=backend/opengl/DirectXMixedSamplerArrayUsageUnsupportedShader.comp.glsl
    "-DEXPECTED_SOURCE_SNIPPET=texture(sampler2DShadow(shadowMap, sharedSamplers[1])"
    "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=opengl|module=DirectXMixedSamplerArrayUsageUnsupportedShader"
    "-DEXPECTED_REFLECTION_TARGET_FIELDS=colorMap.bindingClass=texture|shadowMap.bindingClass=texture|sharedSamplers.sourceType=sampler[SAMPLER_COUNT]|sharedSamplers.bindingClass=sampler|sharedSamplers.arraySize=SAMPLER_COUNT|sharedSamplers.arrayElementCount=2|values.storageBufferLayout.layout=std430"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_build_directx_struct_buffer_source_package
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_STRUCT_BUFFER_COMPUTE_SHADER}
    -DTARGET=directx
    -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-directx-struct-buffer.cglb
    -DMODE=source-package-build
    -DEXPECTED_SOURCE=backend/directx/StructBufferComputeShader.hlsl
    "-DEXPECTED_SOURCE_SNIPPET=RWStructuredBuffer<Particle> particles : register(u0, space0);"
    "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=directx|module=StructBufferComputeShader|nativeBinary=backend/directx/StructBufferComputeShader.dxil|resources.0.name=particles|resources.0.kind=buffer|resources.0.type=Particle*|structs.0.name=Particle|structs.0.fields.0.name=position|structs.0.fields.0.type=vec3|structs.0.fields.1.name=mass|structs.0.fields.1.type=float|structs.0.fields.2.name=velocity|structs.0.fields.2.type=vec4|workgroupSizes.0.entryPoint=compute_main|workgroupSizes.0.x=1|workgroupSizes.0.y=1|workgroupSizes.0.z=1"
    "-DEXPECTED_REFLECTION_JSON_ARRAY_LENGTHS=resources=1|targetResourceBindings=1|workgroupSizes=1"
    "-DEXPECTED_REFLECTION_TARGET_FIELDS=particles.stage=compute|particles.entryPoint=compute_main|particles.sourceType=Particle*|particles.hlslType=RWStructuredBuffer<Particle>|particles.addressSpace=unordered-access|particles.abi=registerBinding|particles.bindingClass=uav|particles.descriptorType=UAV|particles.argumentIndex=0|particles.set=0|particles.binding=0"
    "-DEXPECTED_REFLECTION_FEATURE_FIELDS=hlsl-lowering.kind=backend|native-dxil-package.kind=backend|dxc.kind=toolchain|dxil-validator.kind=validation|compute-kernel.kind=stage|workgroup-size.kind=execution|storage-buffer.kind=resource|local-declaration.kind=operation|storage-buffer-read.kind=operation|index-access.kind=operation|storage-buffer-write.kind=operation|scalar-arithmetic.kind=operation"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_build_opengl_struct_buffer_source_package
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_STRUCT_BUFFER_COMPUTE_SHADER}
    -DTARGET=opengl
    -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-opengl-struct-buffer.cglb
    -DMODE=source-package-build
    -DEXPECTED_SOURCE=backend/opengl/StructBufferComputeShader.comp.glsl
    "-DEXPECTED_SOURCE_SNIPPET=particles[1].mass = mass + 1.0;"
    "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=opengl|module=StructBufferComputeShader"
    "-DEXPECTED_REFLECTION_TARGET_FIELDS=particles.sourceType=Particle*|particles.bindingClass=storage-buffer|particles.abi=programResourceBinding|particles.argumentIndex=0|particles.storageBufferLayout.elementType=Particle|particles.storageBufferLayout.layout=std430|particles.storageBufferLayout.elementSizeBytes=32|particles.storageBufferLayout.arrayStrideBytes=32|particles.storageBufferLayout.fields.0.name=position|particles.storageBufferLayout.fields.0.type=vec3|particles.storageBufferLayout.fields.1.name=mass|particles.storageBufferLayout.fields.1.offsetBytes=12|particles.storageBufferLayout.fields.2.name=velocity|particles.storageBufferLayout.fields.2.offsetBytes=16"
    "-DEXPECTED_REFLECTION_FEATURE_FIELDS=${CROSSGL_OPENGL_STRUCT_STORAGE_FEATURE_FIELDS}|scalar-arithmetic.kind=operation"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_build_directx_struct_vector_buffer_source_package
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_STRUCT_VECTOR_BUFFER_COMPUTE_SHADER}
    -DTARGET=directx
    -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-directx-struct-vector-buffer.cglb
    -DMODE=source-package-build
    -DEXPECTED_SOURCE=backend/directx/StructVectorBufferComputeShader.hlsl
    "-DEXPECTED_SOURCE_SNIPPET=float3 lifted = position + float3(1.0, 0.0, 0.0);"
    "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=directx|module=StructVectorBufferComputeShader|nativeBinary=backend/directx/StructVectorBufferComputeShader.dxil|resources.0.name=particles|resources.0.kind=buffer|resources.0.type=Particle*|structs.0.name=Particle|structs.0.fields.0.name=position|structs.0.fields.0.type=vec3|structs.0.fields.1.name=mass|structs.0.fields.1.type=float|structs.0.fields.2.name=velocity|structs.0.fields.2.type=vec4|workgroupSizes.0.entryPoint=compute_main|workgroupSizes.0.x=1|workgroupSizes.0.y=1|workgroupSizes.0.z=1"
    "-DEXPECTED_REFLECTION_JSON_ARRAY_LENGTHS=resources=1|targetResourceBindings=1|workgroupSizes=1"
    "-DEXPECTED_REFLECTION_TARGET_FIELDS=particles.stage=compute|particles.entryPoint=compute_main|particles.sourceType=Particle*|particles.hlslType=RWStructuredBuffer<Particle>|particles.addressSpace=unordered-access|particles.abi=registerBinding|particles.bindingClass=uav|particles.descriptorType=UAV|particles.argumentIndex=0|particles.set=0|particles.binding=0"
    "-DEXPECTED_REFLECTION_FEATURE_FIELDS=hlsl-lowering.kind=backend|native-dxil-package.kind=backend|dxc.kind=toolchain|dxil-validator.kind=validation|compute-kernel.kind=stage|workgroup-size.kind=execution|storage-buffer.kind=resource|local-declaration.kind=operation|storage-buffer-read.kind=operation|index-access.kind=operation|vector-arithmetic.kind=operation|vector-constructor.kind=operation|storage-buffer-write.kind=operation"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_build_opengl_struct_vector_buffer_source_package
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_STRUCT_VECTOR_BUFFER_COMPUTE_SHADER}
    -DTARGET=opengl
    -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-opengl-struct-vector-buffer.cglb
    -DMODE=source-package-build
    -DEXPECTED_SOURCE=backend/opengl/StructVectorBufferComputeShader.comp.glsl
    "-DEXPECTED_SOURCE_SNIPPET=particles[1].position = lifted;"
    "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=opengl|module=StructVectorBufferComputeShader"
    "-DEXPECTED_REFLECTION_TARGET_FIELDS=particles.sourceType=Particle*|particles.bindingClass=storage-buffer|particles.abi=programResourceBinding|particles.argumentIndex=0|particles.storageBufferLayout.elementType=Particle|particles.storageBufferLayout.layout=std430|particles.storageBufferLayout.elementSizeBytes=32|particles.storageBufferLayout.arrayStrideBytes=32|particles.storageBufferLayout.fields.0.name=position|particles.storageBufferLayout.fields.0.type=vec3|particles.storageBufferLayout.fields.1.name=mass|particles.storageBufferLayout.fields.1.offsetBytes=12|particles.storageBufferLayout.fields.2.name=velocity|particles.storageBufferLayout.fields.2.offsetBytes=16"
    "-DEXPECTED_REFLECTION_FEATURE_FIELDS=${CROSSGL_OPENGL_STRUCT_STORAGE_VECTOR_FEATURE_FIELDS}"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_build_directx_struct_nested_field_source_package
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_STRUCT_NESTED_FIELD_COMPUTE_SHADER}
    -DTARGET=directx
    -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-directx-struct-nested-field.cglb
    -DMODE=source-package-build
    -DEXPECTED_SOURCE=backend/directx/StructNestedFieldComputeShader.hlsl
    "-DEXPECTED_SOURCE_SNIPPET=particles[1].transform.position = lifted;"
    "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=directx|module=StructNestedFieldComputeShader|nativeBinary=backend/directx/StructNestedFieldComputeShader.dxil|resources.0.name=particles|resources.0.kind=buffer|resources.0.type=Particle*|structs.0.name=Transform|structs.0.fields.0.name=position|structs.0.fields.0.type=vec3|structs.1.name=Particle|structs.1.fields.0.name=transform|structs.1.fields.0.type=Transform|structs.1.fields.1.name=mass|structs.1.fields.1.type=float|workgroupSizes.0.entryPoint=compute_main|workgroupSizes.0.x=1|workgroupSizes.0.y=1|workgroupSizes.0.z=1"
    "-DEXPECTED_REFLECTION_JSON_ARRAY_LENGTHS=resources=1|targetResourceBindings=1|workgroupSizes=1"
    "-DEXPECTED_REFLECTION_TARGET_FIELDS=particles.stage=compute|particles.entryPoint=compute_main|particles.sourceType=Particle*|particles.hlslType=RWStructuredBuffer<Particle>|particles.addressSpace=unordered-access|particles.abi=registerBinding|particles.bindingClass=uav|particles.descriptorType=UAV|particles.argumentIndex=0|particles.set=0|particles.binding=0"
    "-DEXPECTED_REFLECTION_FEATURE_FIELDS=hlsl-lowering.kind=backend|native-dxil-package.kind=backend|dxc.kind=toolchain|dxil-validator.kind=validation|compute-kernel.kind=stage|workgroup-size.kind=execution|storage-buffer.kind=resource|local-declaration.kind=operation|storage-buffer-read.kind=operation|index-access.kind=operation|vector-arithmetic.kind=operation|vector-constructor.kind=operation|storage-buffer-write.kind=operation"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_build_opengl_struct_nested_field_source_package
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_STRUCT_NESTED_FIELD_COMPUTE_SHADER}
    -DTARGET=opengl
    -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-opengl-struct-nested-field.cglb
    -DMODE=source-package-build
    -DEXPECTED_SOURCE=backend/opengl/StructNestedFieldComputeShader.comp.glsl
    "-DEXPECTED_SOURCE_SNIPPET=particles[1].transform.position = lifted;"
    "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=opengl|module=StructNestedFieldComputeShader"
    "-DEXPECTED_REFLECTION_TARGET_FIELDS=particles.sourceType=Particle*|particles.bindingClass=storage-buffer|particles.abi=programResourceBinding|particles.argumentIndex=0|particles.storageBufferLayout.elementType=Particle|particles.storageBufferLayout.layout=std430|particles.storageBufferLayout.elementSizeBytes=20|particles.storageBufferLayout.arrayStrideBytes=32|particles.storageBufferLayout.fields.0.name=transform|particles.storageBufferLayout.fields.0.type=Transform|particles.storageBufferLayout.fields.0.storageSizeBytes=16|particles.storageBufferLayout.fields.1.name=mass|particles.storageBufferLayout.fields.1.offsetBytes=16"
    "-DEXPECTED_REFLECTION_FEATURE_FIELDS=${CROSSGL_OPENGL_STRUCT_STORAGE_VECTOR_FEATURE_FIELDS}"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_build_directx_struct_array_field_source_package
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_STRUCT_ARRAY_FIELD_COMPUTE_SHADER}
    -DTARGET=directx
    -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-directx-struct-array-field.cglb
    -DMODE=source-package-build
    -DEXPECTED_SOURCE=backend/directx/StructArrayFieldComputeShader.hlsl
    "-DEXPECTED_SOURCE_SNIPPET=float weights[4];"
    "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=directx|module=StructArrayFieldComputeShader|nativeBinary=backend/directx/StructArrayFieldComputeShader.dxil|resources.0.name=particles|resources.0.kind=buffer|resources.0.type=Particle*|structs.0.name=Particle|structs.0.fields.0.name=weights|structs.0.fields.0.type=float[4]|structs.0.fields.0.arrayDimensions.0.elementCount=4|structs.0.fields.1.name=mass|structs.0.fields.1.type=float|workgroupSizes.0.entryPoint=compute_main|workgroupSizes.0.x=1|workgroupSizes.0.y=1|workgroupSizes.0.z=1"
    "-DEXPECTED_REFLECTION_JSON_ARRAY_LENGTHS=resources=1|targetResourceBindings=1|workgroupSizes=1"
    "-DEXPECTED_REFLECTION_TARGET_FIELDS=particles.stage=compute|particles.entryPoint=compute_main|particles.sourceType=Particle*|particles.hlslType=RWStructuredBuffer<Particle>|particles.addressSpace=unordered-access|particles.abi=registerBinding|particles.bindingClass=uav|particles.descriptorType=UAV|particles.argumentIndex=0|particles.set=0|particles.binding=0"
    "-DEXPECTED_REFLECTION_FEATURE_FIELDS=hlsl-lowering.kind=backend|native-dxil-package.kind=backend|dxc.kind=toolchain|dxil-validator.kind=validation|fixed-array.kind=layout|fixed-array-field.kind=layout|scalar-vector-elements.kind=array|compute-kernel.kind=stage|workgroup-size.kind=execution|storage-buffer.kind=resource|local-declaration.kind=operation|storage-buffer-read.kind=operation|index-access.kind=operation|storage-buffer-write.kind=operation"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_build_opengl_struct_array_field_source_package
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_STRUCT_ARRAY_FIELD_COMPUTE_SHADER}
    -DTARGET=opengl
    -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-opengl-struct-array-field.cglb
    -DMODE=source-package-build
    -DEXPECTED_SOURCE=backend/opengl/StructArrayFieldComputeShader.comp.glsl
    "-DEXPECTED_SOURCE_SNIPPET=particles[1].mass = firstWeight;"
    "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=opengl|module=StructArrayFieldComputeShader"
    "-DEXPECTED_REFLECTION_TARGET_FIELDS=particles.sourceType=Particle*|particles.bindingClass=storage-buffer|particles.abi=programResourceBinding|particles.argumentIndex=0|particles.storageBufferLayout.elementType=Particle|particles.storageBufferLayout.layout=std430|particles.storageBufferLayout.elementSizeBytes=20|particles.storageBufferLayout.arrayStrideBytes=20|particles.storageBufferLayout.fields.0.name=weights|particles.storageBufferLayout.fields.0.type=float[4]|particles.storageBufferLayout.fields.0.arrayElementCount=4|particles.storageBufferLayout.fields.0.arrayStrideBytes=4|particles.storageBufferLayout.fields.1.name=mass|particles.storageBufferLayout.fields.1.offsetBytes=16"
    "-DEXPECTED_REFLECTION_FEATURE_FIELDS=${CROSSGL_OPENGL_STRUCT_STORAGE_ARRAY_FIELD_FEATURE_FIELDS}"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_build_directx_struct_constant_array_field_source_package
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_STRUCT_CONSTANT_ARRAY_FIELD_COMPUTE_SHADER}
    -DTARGET=directx
    -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-directx-struct-constant-array-field.cglb
    -DMODE=source-package-build
    -DEXPECTED_SOURCE=backend/directx/StructConstantArrayFieldComputeShader.hlsl
    "-DEXPECTED_SOURCE_SNIPPET=float weights[WEIGHT_COUNT];"
    "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=directx|module=StructConstantArrayFieldComputeShader|nativeBinary=backend/directx/StructConstantArrayFieldComputeShader.dxil|functionConstants.0.name=WEIGHT_COUNT|functionConstants.0.value=4|resources.0.name=particles|resources.0.kind=buffer|resources.0.type=Particle*|structs.0.name=Particle|structs.0.fields.0.name=weights|structs.0.fields.0.type=float[WEIGHT_COUNT]|structs.0.fields.0.arrayDimensions.0.source=WEIGHT_COUNT|structs.0.fields.0.arrayDimensions.0.elementCount=4|structs.0.fields.1.name=mass|structs.0.fields.1.type=float|workgroupSizes.0.entryPoint=compute_main|workgroupSizes.0.x=1|workgroupSizes.0.y=1|workgroupSizes.0.z=1"
    "-DEXPECTED_REFLECTION_JSON_ARRAY_LENGTHS=resources=1|targetResourceBindings=1|functionConstants=1|workgroupSizes=1"
    "-DEXPECTED_REFLECTION_TARGET_FIELDS=particles.stage=compute|particles.entryPoint=compute_main|particles.sourceType=Particle*|particles.hlslType=RWStructuredBuffer<Particle>|particles.addressSpace=unordered-access|particles.abi=registerBinding|particles.bindingClass=uav|particles.descriptorType=UAV|particles.argumentIndex=0|particles.set=0|particles.binding=0"
    "-DEXPECTED_REFLECTION_FEATURE_FIELDS=hlsl-lowering.kind=backend|native-dxil-package.kind=backend|dxc.kind=toolchain|dxil-validator.kind=validation|fixed-array.kind=layout|fixed-array-field.kind=layout|scalar-vector-elements.kind=array|compute-kernel.kind=stage|workgroup-size.kind=execution|storage-buffer.kind=resource|local-declaration.kind=operation|storage-buffer-read.kind=operation|index-access.kind=operation|storage-buffer-write.kind=operation"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_build_opengl_struct_constant_array_field_source_package
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_STRUCT_CONSTANT_ARRAY_FIELD_COMPUTE_SHADER}
    -DTARGET=opengl
    -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-opengl-struct-constant-array-field.cglb
    -DMODE=source-package-build
    -DEXPECTED_SOURCE=backend/opengl/StructConstantArrayFieldComputeShader.comp.glsl
    "-DEXPECTED_SOURCE_SNIPPET=float weights[WEIGHT_COUNT];"
    "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=opengl|module=StructConstantArrayFieldComputeShader"
    "-DEXPECTED_REFLECTION_TARGET_FIELDS=particles.sourceType=Particle*|particles.bindingClass=storage-buffer|particles.abi=programResourceBinding|particles.argumentIndex=0|particles.storageBufferLayout.elementType=Particle|particles.storageBufferLayout.layout=std430|particles.storageBufferLayout.elementSizeBytes=20|particles.storageBufferLayout.arrayStrideBytes=20|particles.storageBufferLayout.fields.0.name=weights|particles.storageBufferLayout.fields.0.type=float[WEIGHT_COUNT]|particles.storageBufferLayout.fields.0.arrayElementCount=4|particles.storageBufferLayout.fields.0.arrayStrideBytes=4|particles.storageBufferLayout.fields.0.arrayDimensions.0.source=WEIGHT_COUNT|particles.storageBufferLayout.fields.1.name=mass|particles.storageBufferLayout.fields.1.offsetBytes=16"
    "-DEXPECTED_REFLECTION_FEATURE_FIELDS=${CROSSGL_OPENGL_STRUCT_STORAGE_ARRAY_FIELD_FEATURE_FIELDS}"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_build_directx_struct_vector_array_field_source_package
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_STRUCT_VECTOR_ARRAY_FIELD_COMPUTE_SHADER}
    -DTARGET=directx
    -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-directx-struct-vector-array-field.cglb
    -DMODE=source-package-build
    -DEXPECTED_SOURCE=backend/directx/StructVectorArrayFieldComputeShader.hlsl
    "-DEXPECTED_SOURCE_SNIPPET=float3 positions[2];"
    "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=directx|module=StructVectorArrayFieldComputeShader|nativeBinary=backend/directx/StructVectorArrayFieldComputeShader.dxil|resources.0.name=particles|resources.0.kind=buffer|resources.0.type=Particle*|structs.0.name=Particle|structs.0.fields.0.name=positions|structs.0.fields.0.type=vec3[2]|structs.0.fields.0.arrayDimensions.0.elementCount=2|structs.0.fields.1.name=mass|structs.0.fields.1.type=float|workgroupSizes.0.entryPoint=compute_main|workgroupSizes.0.x=1|workgroupSizes.0.y=1|workgroupSizes.0.z=1"
    "-DEXPECTED_REFLECTION_JSON_ARRAY_LENGTHS=resources=1|targetResourceBindings=1|workgroupSizes=1"
    "-DEXPECTED_REFLECTION_TARGET_FIELDS=particles.stage=compute|particles.entryPoint=compute_main|particles.sourceType=Particle*|particles.hlslType=RWStructuredBuffer<Particle>|particles.addressSpace=unordered-access|particles.abi=registerBinding|particles.bindingClass=uav|particles.descriptorType=UAV|particles.argumentIndex=0|particles.set=0|particles.binding=0"
    "-DEXPECTED_REFLECTION_FEATURE_FIELDS=hlsl-lowering.kind=backend|native-dxil-package.kind=backend|dxc.kind=toolchain|dxil-validator.kind=validation|fixed-array.kind=layout|fixed-array-field.kind=layout|scalar-vector-elements.kind=array|compute-kernel.kind=stage|workgroup-size.kind=execution|storage-buffer.kind=resource|local-declaration.kind=operation|storage-buffer-read.kind=operation|index-access.kind=operation|storage-buffer-write.kind=operation"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_build_opengl_struct_vector_array_field_source_package
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_STRUCT_VECTOR_ARRAY_FIELD_COMPUTE_SHADER}
    -DTARGET=opengl
    -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-opengl-struct-vector-array-field.cglb
    -DMODE=source-package-build
    -DEXPECTED_SOURCE=backend/opengl/StructVectorArrayFieldComputeShader.comp.glsl
    "-DEXPECTED_SOURCE_SNIPPET=particles[1].positions[0] = lifted;"
    "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=opengl|module=StructVectorArrayFieldComputeShader"
    "-DEXPECTED_REFLECTION_TARGET_FIELDS=particles.sourceType=Particle*|particles.bindingClass=storage-buffer|particles.abi=programResourceBinding|particles.argumentIndex=0|particles.storageBufferLayout.elementType=Particle|particles.storageBufferLayout.layout=std430|particles.storageBufferLayout.elementSizeBytes=36|particles.storageBufferLayout.arrayStrideBytes=48|particles.storageBufferLayout.fields.0.name=positions|particles.storageBufferLayout.fields.0.type=vec3[2]|particles.storageBufferLayout.fields.0.arrayElementCount=2|particles.storageBufferLayout.fields.0.arrayStrideBytes=16|particles.storageBufferLayout.fields.1.name=mass|particles.storageBufferLayout.fields.1.offsetBytes=32"
    "-DEXPECTED_REFLECTION_FEATURE_FIELDS=${CROSSGL_OPENGL_STRUCT_STORAGE_ARRAY_FIELD_FEATURE_FIELDS}"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_build_opengl_struct_multidim_vector_array_field_source_package
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_STRUCT_MULTIDIM_VECTOR_ARRAY_FIELD_COMPUTE_SHADER}
    -DTARGET=opengl
    -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-opengl-struct-multidim-vector-array-field.cglb
    -DMODE=source-package-build
    -DEXPECTED_SOURCE=backend/opengl/StructMultidimVectorArrayFieldComputeShader.comp.glsl
    "-DEXPECTED_SOURCE_SNIPPET=vec3 positions[ROWS][COLS];"
    "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=opengl|module=StructMultidimVectorArrayFieldComputeShader|functionConstants.0.name=ROWS|functionConstants.0.value=2|functionConstants.1.name=COLS|functionConstants.1.value=3|structs.0.fields.0.arrayDimensions.0.elementCount=2|structs.0.fields.0.arrayDimensions.1.elementCount=3"
    "-DEXPECTED_REFLECTION_TARGET_FIELDS=particles.sourceType=Particle*|particles.bindingClass=storage-buffer|particles.abi=programResourceBinding|particles.argumentIndex=0|particles.storageBufferLayout.elementType=Particle|particles.storageBufferLayout.layout=std430|particles.storageBufferLayout.elementSizeBytes=100|particles.storageBufferLayout.arrayStrideBytes=112|particles.storageBufferLayout.fields.0.name=positions|particles.storageBufferLayout.fields.0.type=vec3[ROWS][COLS]|particles.storageBufferLayout.fields.0.arrayElementCount=6|particles.storageBufferLayout.fields.0.arrayStrideBytes=16|particles.storageBufferLayout.fields.0.arrayDimensions.0.source=ROWS|particles.storageBufferLayout.fields.0.arrayDimensions.0.elementCount=2|particles.storageBufferLayout.fields.0.arrayDimensions.1.source=COLS|particles.storageBufferLayout.fields.0.arrayDimensions.1.elementCount=3|particles.storageBufferLayout.fields.1.name=mass|particles.storageBufferLayout.fields.1.offsetBytes=96"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_build_directx_struct_nested_array_field_source_package
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_STRUCT_NESTED_ARRAY_FIELD_COMPUTE_SHADER}
    -DTARGET=directx
    -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-directx-struct-nested-array-field.cglb
    -DMODE=source-package-build
    -DEXPECTED_SOURCE=backend/directx/StructNestedArrayFieldComputeShader.hlsl
    "-DEXPECTED_SOURCE_SNIPPET=Transform history[2];"
    "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=directx|module=StructNestedArrayFieldComputeShader|nativeBinary=backend/directx/StructNestedArrayFieldComputeShader.dxil|resources.0.name=particles|resources.0.kind=buffer|resources.0.type=Particle*|structs.0.name=Transform|structs.0.fields.0.name=position|structs.0.fields.0.type=vec3|structs.0.fields.1.name=weight|structs.0.fields.1.type=float|structs.1.name=Particle|structs.1.fields.0.name=history|structs.1.fields.0.type=Transform[2]|structs.1.fields.0.arrayDimensions.0.elementCount=2|structs.1.fields.1.name=mass|structs.1.fields.1.type=float|workgroupSizes.0.entryPoint=compute_main|workgroupSizes.0.x=1|workgroupSizes.0.y=1|workgroupSizes.0.z=1"
    "-DEXPECTED_REFLECTION_JSON_ARRAY_LENGTHS=resources=1|targetResourceBindings=1|workgroupSizes=1"
    "-DEXPECTED_REFLECTION_TARGET_FIELDS=particles.stage=compute|particles.entryPoint=compute_main|particles.sourceType=Particle*|particles.hlslType=RWStructuredBuffer<Particle>|particles.addressSpace=unordered-access|particles.abi=registerBinding|particles.bindingClass=uav|particles.descriptorType=UAV|particles.argumentIndex=0|particles.set=0|particles.binding=0"
    "-DEXPECTED_REFLECTION_FEATURE_FIELDS=hlsl-lowering.kind=backend|native-dxil-package.kind=backend|dxc.kind=toolchain|dxil-validator.kind=validation|fixed-array.kind=layout|fixed-array-field.kind=layout|compute-kernel.kind=stage|workgroup-size.kind=execution|storage-buffer.kind=resource|local-declaration.kind=operation|storage-buffer-read.kind=operation|index-access.kind=operation|storage-buffer-write.kind=operation"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_build_opengl_struct_nested_array_field_source_package
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_STRUCT_NESTED_ARRAY_FIELD_COMPUTE_SHADER}
    -DTARGET=opengl
    -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-opengl-struct-nested-array-field.cglb
    -DMODE=source-package-build
    -DEXPECTED_SOURCE=backend/opengl/StructNestedArrayFieldComputeShader.comp.glsl
    "-DEXPECTED_SOURCE_SNIPPET=particles[1].history[0].position = previous;"
    "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=opengl|module=StructNestedArrayFieldComputeShader"
    "-DEXPECTED_REFLECTION_TARGET_FIELDS=particles.sourceType=Particle*|particles.bindingClass=storage-buffer|particles.abi=programResourceBinding|particles.argumentIndex=0|particles.storageBufferLayout.elementType=Particle|particles.storageBufferLayout.layout=std430|particles.storageBufferLayout.elementSizeBytes=36|particles.storageBufferLayout.arrayStrideBytes=48|particles.storageBufferLayout.fields.0.name=history|particles.storageBufferLayout.fields.0.type=Transform[2]|particles.storageBufferLayout.fields.0.arrayElementCount=2|particles.storageBufferLayout.fields.0.arrayStrideBytes=16|particles.storageBufferLayout.fields.1.name=mass|particles.storageBufferLayout.fields.1.offsetBytes=32"
    "-DEXPECTED_REFLECTION_FEATURE_FIELDS=${CROSSGL_OPENGL_STRUCT_STORAGE_AGGREGATE_ARRAY_FIELD_FEATURE_FIELDS}"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_build_opengl_struct_storage_buffer_array_field_descriptor_array_source_package
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_STORAGE_BUFFER_STRUCT_ARRAY_FIELD_DESCRIPTOR_ARRAY_SHADER}
    -DTARGET=opengl
    -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-opengl-struct-storage-buffer-array-field-descriptor-array.cglb
    -DMODE=source-package-build
    -DEXPECTED_SOURCE=backend/opengl/StorageBufferStructArrayFieldDescriptorArrayShader.comp.glsl
    "-DEXPECTED_SOURCE_SNIPPET=particles_Buffers[0].particles[1].history[0].position = previousPosition;"
    "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=opengl|module=StorageBufferStructArrayFieldDescriptorArrayShader"
    "-DEXPECTED_REFLECTION_TARGET_FIELDS=particles.sourceType=Particle*[2]|particles.bindingClass=storage-buffer|particles.arraySize=2|particles.arrayElementCount=2|particles.storageBufferLayout.elementType=Particle|particles.storageBufferLayout.layout=std430|particles.storageBufferLayout.arrayStrideBytes=48|particles.storageBufferLayout.fields.0.name=weights|particles.storageBufferLayout.fields.0.arrayElementCount=4|particles.storageBufferLayout.fields.1.name=history|particles.storageBufferLayout.fields.1.arrayElementCount=2|particles.storageBufferLayout.fields.1.arrayStrideBytes=16"
    "-DEXPECTED_REFLECTION_FEATURE_FIELDS=${CROSSGL_OPENGL_STRUCT_STORAGE_DESCRIPTOR_ARRAY_FEATURE_FIELDS}|fixed-array-field.kind=layout|scalar-vector-elements.kind=array|scalar-arithmetic.kind=operation"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)

add_test(NAME cglc_build_directx_storage_image_2d_source_package
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_DIRECTX_STORAGE_IMAGE_2D_SHADER}
    -DTARGET=directx
    -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-directx-storage-image-2d.cglb
    -DMODE=source-package-build
    -DEXPECTED_SOURCE=backend/directx/DirectXStorageImage2DShader.hlsl
    "-DEXPECTED_SOURCE_SNIPPET=RWTexture2D<float4> colorImage : register(u0, space0)"
    "-DEXPECTED_MANIFEST_JSON_FIELDS=schemaVersion=1|target=directx|module=DirectXStorageImage2DShader|artifacts.backendSource=backend/directx/DirectXStorageImage2DShader.hlsl|artifacts.nativeBinary=backend/directx/DirectXStorageImage2DShader.dxil"
    "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=directx|module=DirectXStorageImage2DShader|nativeBinary=backend/directx/DirectXStorageImage2DShader.dxil|resources.0.kind=storage_image|resources.0.type=image2D|resources.1.type=iimage2D|resources.2.type=uimage2D|workgroupSizes.0.entryPoint=compute_main|workgroupSizes.0.x=8|workgroupSizes.0.y=8|workgroupSizes.0.z=1"
    "-DEXPECTED_REFLECTION_JSON_ARRAY_LENGTHS=resources=3|targetResourceBindings=3|workgroupSizes=1"
    "-DEXPECTED_REFLECTION_TARGET_FIELDS=colorImage.sourceType=image2D|colorImage.hlslType=RWTexture2D<float4>|colorImage.bindingClass=uav|colorImage.descriptorType=UAV|colorImage.argumentIndex=0|labelImage.hlslType=RWTexture2D<int4>|maskImage.hlslType=RWTexture2D<uint4>"
    "-DEXPECTED_REFLECTION_FEATURE_FIELDS=storage-image.kind=resource|read-write.kind=storageImage|2d-dimension.kind=storageImage|rgba32f-format.kind=storageImage|rgba32i-format.kind=storageImage|rgba32ui-format.kind=storageImage|storage-image-read.kind=operation|storage-image-write.kind=operation"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_build_directx_storage_image_2d_array_source_package
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_DIRECTX_STORAGE_IMAGE_2D_ARRAY_SHADER}
    -DTARGET=directx
    -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-directx-storage-image-2d-array.cglb
    -DMODE=source-package-build
    -DEXPECTED_SOURCE=backend/directx/DirectXStorageImage2DArrayShader.hlsl
    "-DEXPECTED_SOURCE_SNIPPET=RWTexture2DArray<float4> colorAtlas : register(u3, space0)"
    "-DEXPECTED_MANIFEST_JSON_FIELDS=schemaVersion=1|target=directx|module=DirectXStorageImage2DArrayShader|artifacts.backendSource=backend/directx/DirectXStorageImage2DArrayShader.hlsl|artifacts.nativeBinary=backend/directx/DirectXStorageImage2DArrayShader.dxil"
    "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=directx|module=DirectXStorageImage2DArrayShader|nativeBinary=backend/directx/DirectXStorageImage2DArrayShader.dxil|resources.0.kind=storage_image|resources.0.type=image2DArray|resources.1.type=iimage2DArray|resources.2.type=uimage2DArray|workgroupSizes.0.entryPoint=compute_main|workgroupSizes.0.x=4|workgroupSizes.0.y=4|workgroupSizes.0.z=4"
    "-DEXPECTED_REFLECTION_JSON_ARRAY_LENGTHS=resources=3|targetResourceBindings=3|workgroupSizes=1"
    "-DEXPECTED_REFLECTION_TARGET_FIELDS=colorAtlas.sourceType=image2DArray|colorAtlas.hlslType=RWTexture2DArray<float4>|colorAtlas.bindingClass=uav|colorAtlas.argumentIndex=3|labelAtlas.hlslType=RWTexture2DArray<int4>|maskAtlas.hlslType=RWTexture2DArray<uint4>"
    "-DEXPECTED_REFLECTION_FEATURE_FIELDS=storage-image.kind=resource|read-write.kind=storageImage|2d_array-dimension.kind=storageImage|array-dimension.kind=storageImage|rgba32f-format.kind=storageImage|rgba32i-format.kind=storageImage|rgba32ui-format.kind=storageImage|storage-image-read.kind=operation|storage-image-write.kind=operation"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_build_directx_storage_image_read_write_source_package
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_DIRECTX_STORAGE_IMAGE_READ_WRITE_SHADER}
    -DTARGET=directx
    -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-directx-storage-image-read-write.cglb
    -DMODE=source-package-build
    -DEXPECTED_SOURCE=backend/directx/DirectXStorageImageReadWriteShader.hlsl
    "-DEXPECTED_SOURCE_SNIPPET=RWTexture2DArray<uint4> maskAtlas : register(u5, space0)"
    "-DEXPECTED_MANIFEST_JSON_FIELDS=schemaVersion=1|target=directx|module=DirectXStorageImageReadWriteShader|artifacts.backendSource=backend/directx/DirectXStorageImageReadWriteShader.hlsl|artifacts.nativeBinary=backend/directx/DirectXStorageImageReadWriteShader.dxil"
    "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=directx|module=DirectXStorageImageReadWriteShader|nativeBinary=backend/directx/DirectXStorageImageReadWriteShader.dxil|resources.0.kind=storage_image|resources.0.type=image2D|resources.1.type=iimage2D|resources.2.type=uimage2D|resources.3.type=image2DArray|resources.4.type=iimage2DArray|resources.5.type=uimage2DArray|workgroupSizes.0.entryPoint=compute_main|workgroupSizes.0.x=4|workgroupSizes.0.y=4|workgroupSizes.0.z=1"
    "-DEXPECTED_REFLECTION_JSON_ARRAY_LENGTHS=resources=6|targetResourceBindings=6|workgroupSizes=1"
    "-DEXPECTED_REFLECTION_TARGET_FIELDS=colorImage.sourceType=image2D|colorImage.hlslType=RWTexture2D<float4>|colorImage.bindingClass=uav|colorImage.descriptorType=UAV|colorImage.argumentIndex=0|labelImage.hlslType=RWTexture2D<int4>|maskImage.hlslType=RWTexture2D<uint4>|colorAtlas.sourceType=image2DArray|colorAtlas.hlslType=RWTexture2DArray<float4>|colorAtlas.argumentIndex=3|labelAtlas.hlslType=RWTexture2DArray<int4>|maskAtlas.sourceType=uimage2DArray|maskAtlas.hlslType=RWTexture2DArray<uint4>|maskAtlas.binding=5"
    "-DEXPECTED_REFLECTION_FEATURE_FIELDS=storage-image.kind=resource|read-write.kind=storageImage|2d-dimension.kind=storageImage|2d_array-dimension.kind=storageImage|array-dimension.kind=storageImage|rgba32f-format.kind=storageImage|rgba32i-format.kind=storageImage|rgba32ui-format.kind=storageImage|storage-image-read.kind=operation|storage-image-write.kind=operation"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_build_directx_storage_image_access_qualifier_source_package
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_DIRECTX_STORAGE_IMAGE_ACCESS_QUALIFIER_SHADER}
    -DTARGET=directx
    -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-directx-storage-image-access-qualifier.cglb
    -DMODE=source-package-build
    -DEXPECTED_SOURCE=backend/directx/DirectXStorageImageAccessQualifierShader.hlsl
    "-DEXPECTED_SOURCE_SNIPPET=RWTexture2DArray<float4> writeAtlas : register(u4, space0)"
    "-DEXPECTED_MANIFEST_JSON_FIELDS=schemaVersion=1|target=directx|module=DirectXStorageImageAccessQualifierShader|artifacts.backendSource=backend/directx/DirectXStorageImageAccessQualifierShader.hlsl|artifacts.nativeBinary=backend/directx/DirectXStorageImageAccessQualifierShader.dxil"
    "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=directx|module=DirectXStorageImageAccessQualifierShader|nativeBinary=backend/directx/DirectXStorageImageAccessQualifierShader.dxil|resources.0.kind=storage_image|resources.0.type=image2D|resources.5.type=image2DArray|workgroupSizes.0.entryPoint=compute_main|workgroupSizes.0.x=4|workgroupSizes.0.y=4|workgroupSizes.0.z=2"
    "-DEXPECTED_REFLECTION_JSON_ARRAY_LENGTHS=resources=6|targetResourceBindings=6|workgroupSizes=1"
    "-DEXPECTED_REFLECTION_TARGET_FIELDS=readColor.sourceType=image2D|readColor.hlslType=RWTexture2D<float4>|readColor.bindingClass=uav|writeColor.descriptorType=UAV|readAtlas.hlslType=RWTexture2DArray<float4>|writeAtlas.argumentIndex=4|readWriteAtlas.sourceType=image2DArray"
    "-DEXPECTED_REFLECTION_FEATURE_FIELDS=storage-image.kind=resource|read-only.kind=storageImage|write-only.kind=storageImage|read-write.kind=storageImage|2d-dimension.kind=storageImage|2d_array-dimension.kind=storageImage|array-dimension.kind=storageImage|rgba32f-format.kind=storageImage|storage-image-read.kind=operation|storage-image-write.kind=operation"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_build_opengl_storage_image_source_package
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_OPENGL_STORAGE_IMAGE_SHADER}
    -DTARGET=opengl
    -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-opengl-storage-image.cglb
    -DMODE=source-package-build
    -DEXPECTED_SOURCE=backend/opengl/OpenGLStorageImageShader.comp.glsl
    "-DEXPECTED_SOURCE_SNIPPET=layout(binding = 5, rgba32ui) uniform uimage2DArray maskAtlas"
    "-DEXPECTED_MANIFEST_JSON_FIELDS=schemaVersion=1|target=opengl|module=OpenGLStorageImageShader|artifacts.backendSource=backend/opengl/OpenGLStorageImageShader.comp.glsl|artifacts.nativeBinary=backend/opengl/OpenGLStorageImageShader.glsl"
    "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=opengl|module=OpenGLStorageImageShader|nativeBinary=backend/opengl/OpenGLStorageImageShader.glsl|resources.0.kind=storage_image|resources.0.type=image2D|resources.5.type=uimage2DArray|workgroupSizes.0.entryPoint=compute_main|workgroupSizes.0.x=8|workgroupSizes.0.y=8|workgroupSizes.0.z=1"
    "-DEXPECTED_REFLECTION_JSON_ARRAY_LENGTHS=resources=6|targetResourceBindings=6|workgroupSizes=1"
    "-DEXPECTED_REFLECTION_TARGET_FIELDS=colorImage.sourceType=image2D|colorImage.bindingClass=image|colorImage.abi=programResourceBinding|colorImage.argumentIndex=0|colorAtlas.sourceType=image2DArray|colorAtlas.bindingClass=image|maskAtlas.sourceType=uimage2DArray|maskAtlas.binding=5"
    "-DEXPECTED_REFLECTION_FEATURE_FIELDS=storage-image.kind=resource|read-write.kind=storageImage|2d-dimension.kind=storageImage|2d_array-dimension.kind=storageImage|array-dimension.kind=storageImage|rgba32f-format.kind=storageImage|rgba32i-format.kind=storageImage|rgba32ui-format.kind=storageImage|storage-image-read.kind=operation|storage-image-write.kind=operation"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_build_opengl_storage_image_access_qualifier_source_package
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_OPENGL_STORAGE_IMAGE_ACCESS_QUALIFIER_SHADER}
    -DTARGET=opengl
    -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-opengl-storage-image-access-qualifier.cglb
    -DMODE=source-package-build
    -DEXPECTED_SOURCE=backend/opengl/OpenGLStorageImageAccessQualifierShader.comp.glsl
    "-DEXPECTED_SOURCE_SNIPPET=layout(binding = 4, rgba32f) writeonly uniform image2DArray writeAtlas;"
    "-DEXPECTED_MANIFEST_JSON_FIELDS=schemaVersion=1|target=opengl|module=OpenGLStorageImageAccessQualifierShader|artifacts.backendSource=backend/opengl/OpenGLStorageImageAccessQualifierShader.comp.glsl|artifacts.nativeBinary=backend/opengl/OpenGLStorageImageAccessQualifierShader.glsl"
    "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=opengl|module=OpenGLStorageImageAccessQualifierShader|nativeBinary=backend/opengl/OpenGLStorageImageAccessQualifierShader.glsl|resources.0.kind=storage_image|resources.0.type=image2D|resources.5.type=image2DArray|workgroupSizes.0.entryPoint=compute_main|workgroupSizes.0.x=4|workgroupSizes.0.y=4|workgroupSizes.0.z=2"
    "-DEXPECTED_REFLECTION_JSON_ARRAY_LENGTHS=resources=6|targetResourceBindings=6|workgroupSizes=1"
    "-DEXPECTED_REFLECTION_TARGET_FIELDS=readColor.sourceType=image2D|readColor.bindingClass=image|readColor.abi=programResourceBinding|writeColor.argumentIndex=1|readAtlas.sourceType=image2DArray|writeAtlas.binding=4|readWriteAtlas.sourceType=image2DArray"
    "-DEXPECTED_REFLECTION_FEATURE_FIELDS=storage-image.kind=resource|read-only.kind=storageImage|write-only.kind=storageImage|read-write.kind=storageImage|2d-dimension.kind=storageImage|2d_array-dimension.kind=storageImage|array-dimension.kind=storageImage|rgba32f-format.kind=storageImage|storage-image-read.kind=operation|storage-image-write.kind=operation"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_build_opengl_storage_image_atomic_source_package
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_OPENGL_STORAGE_IMAGE_ATOMIC_SHADER}
    -DTARGET=opengl
    -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-opengl-storage-image-atomic.cglb
    -DMODE=source-package-build
    -DEXPECTED_SOURCE=backend/opengl/OpenGLStorageImageAtomicShader.comp.glsl
    "-DEXPECTED_SOURCE_SNIPPET=uint unsignedAtlasOld = imageAtomicExchange(unsignedAtlas, atlasPixel, unsignedOr);"
    "-DEXPECTED_MANIFEST_JSON_FIELDS=schemaVersion=1|target=opengl|module=OpenGLStorageImageAtomicShader|artifacts.backendSource=backend/opengl/OpenGLStorageImageAtomicShader.comp.glsl|artifacts.nativeBinary=backend/opengl/OpenGLStorageImageAtomicShader.glsl"
    "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=opengl|module=OpenGLStorageImageAtomicShader|nativeBinary=backend/opengl/OpenGLStorageImageAtomicShader.glsl|resources.0.kind=storage_image|resources.0.type=iimage2D|resources.0.storageImageFormat=r32i|resources.1.type=uimage2D|resources.1.storageImageFormat=r32ui|resources.2.type=iimage2DArray|resources.3.type=uimage2DArray|resources.3.storageImageFormat=r32ui|workgroupSizes.0.entryPoint=compute_main|workgroupSizes.0.x=8|workgroupSizes.0.y=8|workgroupSizes.0.z=2"
    "-DEXPECTED_REFLECTION_JSON_ARRAY_LENGTHS=resources=6|targetResourceBindings=6|workgroupSizes=1"
    "-DEXPECTED_REFLECTION_TARGET_FIELDS=signedCounters.sourceType=iimage2D|signedCounters.bindingClass=image|signedCounters.abi=programResourceBinding|signedCounters.storageImageFormat=r32i|unsignedCounters.sourceType=uimage2D|unsignedCounters.storageImageFormat=r32ui|signedAtlas.sourceType=iimage2DArray|signedAtlas.storageImageFormat=r32i|unsignedAtlas.sourceType=uimage2DArray|unsignedAtlas.binding=3|unsignedAtlas.storageImageFormat=r32ui"
    "-DEXPECTED_REFLECTION_FEATURE_FIELDS=storage-image.kind=resource|read-write.kind=storageImage|2d-dimension.kind=storageImage|2d_array-dimension.kind=storageImage|array-dimension.kind=storageImage|r32i-format.kind=storageImage|r32ui-format.kind=storageImage|storage-buffer.kind=resource|storage-image-read.kind=operation|storage-image-write.kind=operation|storage-image-atomic-add.kind=operation|storage-image-atomic-exchange.kind=operation|storage-image-atomic-min.kind=operation|storage-image-atomic-max.kind=operation|storage-image-atomic-and.kind=operation|storage-image-atomic-or.kind=operation|storage-image-atomic-xor.kind=operation"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_build_directx_storage_image_atomic_source_package
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_STORAGE_IMAGE_ATOMIC_SHADER}
    -DTARGET=directx
    -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-directx-storage-image-atomic.cglb
    -DMODE=source-package-build
    -DEXPECTED_SOURCE=backend/directx/StorageImageAtomicShader.hlsl
    "-DEXPECTED_SOURCE_SNIPPET=InterlockedMax(unsignedAtlas[atlasPixel], unsignedMin, unsignedMax);"
    "-DEXPECTED_MANIFEST_JSON_FIELDS=schemaVersion=1|target=directx|module=StorageImageAtomicShader|artifacts.backendSource=backend/directx/StorageImageAtomicShader.hlsl|artifacts.nativeBinary=backend/directx/StorageImageAtomicShader.dxil"
    "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=directx|module=StorageImageAtomicShader|nativeBinary=backend/directx/StorageImageAtomicShader.dxil|resources.0.kind=storage_image|resources.0.type=iimage2D|resources.0.storageImageFormat=r32i|resources.1.type=uimage2D|resources.1.storageImageFormat=r32ui|resources.2.type=iimage2DArray|resources.3.type=uimage2DArray|resources.3.storageImageFormat=r32ui|workgroupSizes.0.entryPoint=compute_main|workgroupSizes.0.x=4|workgroupSizes.0.y=4|workgroupSizes.0.z=2"
    "-DEXPECTED_REFLECTION_JSON_ARRAY_LENGTHS=resources=6|targetResourceBindings=6|workgroupSizes=1"
    "-DEXPECTED_REFLECTION_TARGET_FIELDS=signedCounters.sourceType=iimage2D|signedCounters.hlslType=RWTexture2D<int>|signedCounters.bindingClass=uav|signedCounters.descriptorType=UAV|signedCounters.storageImageFormat=r32i|unsignedCounters.sourceType=uimage2D|unsignedCounters.hlslType=RWTexture2D<uint>|unsignedCounters.storageImageFormat=r32ui|signedAtlas.sourceType=iimage2DArray|signedAtlas.hlslType=RWTexture2DArray<int>|signedAtlas.storageImageFormat=r32i|unsignedAtlas.sourceType=uimage2DArray|unsignedAtlas.hlslType=RWTexture2DArray<uint>|unsignedAtlas.storageImageFormat=r32ui"
    "-DEXPECTED_REFLECTION_FEATURE_FIELDS=storage-image.kind=resource|read-write.kind=storageImage|2d-dimension.kind=storageImage|2d_array-dimension.kind=storageImage|array-dimension.kind=storageImage|r32i-format.kind=storageImage|r32ui-format.kind=storageImage|storage-buffer.kind=resource|storage-image-read.kind=operation|storage-image-write.kind=operation|storage-image-atomic-add.kind=operation|storage-image-atomic-exchange.kind=operation|storage-image-atomic-min.kind=operation|storage-image-atomic-max.kind=operation|storage-image-atomic-and.kind=operation|storage-image-atomic-or.kind=operation|storage-image-atomic-xor.kind=operation"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
set(CROSSGL_DIRECTX_MIXED_STORAGE_IMAGE_ATOMIC_ACCESS_SOURCE_SNIPPET [=[  int oldValue;
  InterlockedAdd(counters[pixel], 1, oldValue);
  int4 loaded = int4(counters.Load(pixel), 0, 0, 1);
  counters[pixel] = (loaded).x;]=])
add_test(NAME cglc_build_directx_mixed_storage_image_atomic_access_source_package
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_DIRECTX_MIXED_STORAGE_IMAGE_ATOMIC_ACCESS_SHADER}
    -DTARGET=directx
    -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-directx-mixed-storage-image-atomic-access.cglb
    -DMODE=source-package-build
    -DEXPECTED_SOURCE=backend/directx/DirectXMixedStorageImageAtomicAccessShader.hlsl
    "-DEXPECTED_SOURCE_SNIPPET=${CROSSGL_DIRECTX_MIXED_STORAGE_IMAGE_ATOMIC_ACCESS_SOURCE_SNIPPET}"
    "-DEXPECTED_MANIFEST_JSON_FIELDS=schemaVersion=1|target=directx|module=DirectXMixedStorageImageAtomicAccessShader|artifacts.backendSource=backend/directx/DirectXMixedStorageImageAtomicAccessShader.hlsl|artifacts.nativeBinary=backend/directx/DirectXMixedStorageImageAtomicAccessShader.dxil"
    "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=directx|module=DirectXMixedStorageImageAtomicAccessShader|nativeBinary=backend/directx/DirectXMixedStorageImageAtomicAccessShader.dxil|resources.0.kind=storage_image|resources.0.type=iimage2D|resources.0.storageImageFormat=r32i|resources.1.kind=buffer|resources.1.type=int*|workgroupSizes.0.entryPoint=compute_main|workgroupSizes.0.x=1|workgroupSizes.0.y=1|workgroupSizes.0.z=1"
    "-DEXPECTED_REFLECTION_JSON_ARRAY_LENGTHS=resources=2|targetResourceBindings=2|workgroupSizes=1"
    "-DEXPECTED_REFLECTION_TARGET_FIELDS=counters.sourceType=iimage2D|counters.hlslType=RWTexture2D<int>|counters.bindingClass=uav|counters.descriptorType=UAV|counters.storageImageFormat=r32i|results.hlslType=RWStructuredBuffer<int>|results.binding=1"
    "-DEXPECTED_REFLECTION_FEATURE_FIELDS=storage-image.kind=resource|read-write.kind=storageImage|2d-dimension.kind=storageImage|r32i-format.kind=storageImage|storage-buffer.kind=resource|storage-image-read.kind=operation|storage-image-write.kind=operation|storage-image-atomic-add.kind=operation"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
set(CROSSGL_DIRECTX_STORAGE_IMAGE_EXPLICIT_FORMAT_SOURCE_SNIPPET [=[RWTexture2D<float4> readColor : register(u0, space0);
RWTexture2D<int4> readLabel : register(u1, space0);
RWTexture2D<uint4> readMask : register(u2, space0);
RWTexture2D<uint4> writeMask : register(u3, space0);]=])
add_test(NAME cglc_build_directx_storage_image_explicit_format_source_package
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_STORAGE_IMAGE_EXPLICIT_FORMAT_SHADER}
    -DTARGET=directx
    -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-directx-storage-image-explicit-format.cglb
    -DMODE=source-package-build
    -DEXPECTED_SOURCE=backend/directx/StorageImageExplicitFormatShader.hlsl
    "-DEXPECTED_SOURCE_SNIPPET=${CROSSGL_DIRECTX_STORAGE_IMAGE_EXPLICIT_FORMAT_SOURCE_SNIPPET}"
    "-DEXPECTED_MANIFEST_JSON_FIELDS=schemaVersion=1|target=directx|module=StorageImageExplicitFormatShader|artifacts.backendSource=backend/directx/StorageImageExplicitFormatShader.hlsl|artifacts.nativeBinary=backend/directx/StorageImageExplicitFormatShader.dxil"
    "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=directx|module=StorageImageExplicitFormatShader|nativeBinary=backend/directx/StorageImageExplicitFormatShader.dxil|resources.0.kind=storage_image|resources.0.type=image2D|resources.0.storageImageFormat=r32f|resources.1.type=iimage2D|resources.1.storageImageFormat=r32i|resources.2.type=uimage2D|resources.2.storageImageFormat=r32ui|resources.3.type=uimage2D|resources.3.storageImageFormat=r32ui|resources.4.kind=buffer|resources.5.type=ivec4*|workgroupSizes.0.entryPoint=compute_main|workgroupSizes.0.x=2|workgroupSizes.0.y=2|workgroupSizes.0.z=1"
    "-DEXPECTED_REFLECTION_JSON_ARRAY_LENGTHS=resources=6|targetResourceBindings=6|workgroupSizes=1"
    "-DEXPECTED_REFLECTION_TARGET_FIELDS=readColor.sourceType=image2D|readColor.hlslType=RWTexture2D<float4>|readColor.bindingClass=uav|readColor.descriptorType=UAV|readColor.storageImageFormat=r32f|readColor.argumentIndex=0|readLabel.sourceType=iimage2D|readLabel.hlslType=RWTexture2D<int4>|readLabel.storageImageFormat=r32i|readMask.sourceType=uimage2D|readMask.hlslType=RWTexture2D<uint4>|readMask.storageImageFormat=r32ui|writeMask.sourceType=uimage2D|writeMask.hlslType=RWTexture2D<uint4>|writeMask.storageImageFormat=r32ui|writeMask.argumentIndex=3|colors.hlslType=RWStructuredBuffer<float4>|labels.hlslType=RWStructuredBuffer<int4>"
    "-DEXPECTED_REFLECTION_FEATURE_FIELDS=storage-image.kind=resource|read-only.kind=storageImage|write-only.kind=storageImage|2d-dimension.kind=storageImage|r32f-format.kind=storageImage|r32i-format.kind=storageImage|r32ui-format.kind=storageImage|storage-buffer.kind=resource|vector-storage-buffer.kind=layout|storage-image-read.kind=operation|storage-image-write.kind=operation"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
set(CROSSGL_OPENGL_STORAGE_IMAGE_EXPLICIT_FORMAT_SOURCE_SNIPPET [=[layout(binding = 0, r32f) readonly uniform image2D readColor;

// CrossGL set 0, binding 1
layout(binding = 1, r32i) readonly uniform iimage2D readLabel;

// CrossGL set 0, binding 2
layout(binding = 2, r32ui) readonly uniform uimage2D readMask;

// CrossGL set 0, binding 3
layout(binding = 3, r32ui) writeonly uniform uimage2D writeMask;]=])
add_test(NAME cglc_build_opengl_storage_image_explicit_format_source_package
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_STORAGE_IMAGE_EXPLICIT_FORMAT_SHADER}
    -DTARGET=opengl
    -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-opengl-storage-image-explicit-format.cglb
    -DMODE=source-package-build
    -DEXPECTED_SOURCE=backend/opengl/StorageImageExplicitFormatShader.comp.glsl
    "-DEXPECTED_SOURCE_SNIPPET=${CROSSGL_OPENGL_STORAGE_IMAGE_EXPLICIT_FORMAT_SOURCE_SNIPPET}"
    "-DEXPECTED_MANIFEST_JSON_FIELDS=schemaVersion=1|target=opengl|module=StorageImageExplicitFormatShader|artifacts.backendSource=backend/opengl/StorageImageExplicitFormatShader.comp.glsl|artifacts.nativeBinary=backend/opengl/StorageImageExplicitFormatShader.glsl"
    "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=opengl|module=StorageImageExplicitFormatShader|nativeBinary=backend/opengl/StorageImageExplicitFormatShader.glsl|resources.0.kind=storage_image|resources.0.type=image2D|resources.0.storageImageFormat=r32f|resources.1.type=iimage2D|resources.1.storageImageFormat=r32i|resources.2.type=uimage2D|resources.2.storageImageFormat=r32ui|resources.3.type=uimage2D|resources.3.storageImageFormat=r32ui|resources.4.kind=buffer|resources.5.type=ivec4*|workgroupSizes.0.entryPoint=compute_main|workgroupSizes.0.x=2|workgroupSizes.0.y=2|workgroupSizes.0.z=1"
    "-DEXPECTED_REFLECTION_JSON_ARRAY_LENGTHS=resources=6|targetResourceBindings=6|workgroupSizes=1"
    "-DEXPECTED_REFLECTION_TARGET_FIELDS=readColor.sourceType=image2D|readColor.bindingClass=image|readColor.abi=programResourceBinding|readColor.storageImageFormat=r32f|readColor.argumentIndex=0|readLabel.sourceType=iimage2D|readLabel.storageImageFormat=r32i|readMask.sourceType=uimage2D|readMask.storageImageFormat=r32ui|writeMask.sourceType=uimage2D|writeMask.storageImageFormat=r32ui|writeMask.binding=3|colors.bindingClass=storage-buffer|colors.storageBufferLayout.elementType=vec4|labels.bindingClass=storage-buffer|labels.storageBufferLayout.elementType=ivec4"
    "-DEXPECTED_REFLECTION_FEATURE_FIELDS=storage-image.kind=resource|read-only.kind=storageImage|write-only.kind=storageImage|2d-dimension.kind=storageImage|r32f-format.kind=storageImage|r32i-format.kind=storageImage|r32ui-format.kind=storageImage|storage-buffer.kind=resource|vector-storage-buffer.kind=layout|storage-image-read.kind=operation|storage-image-write.kind=operation"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)

add_test(NAME cglc_build_directx_storage_image_descriptor_array_source_package
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_DIRECTX_STORAGE_IMAGE_DESCRIPTOR_ARRAY_SHADER}
    -DTARGET=directx
    -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-directx-storage-image-descriptor-array.cglb
    -DMODE=source-package-build
    -DEXPECTED_SOURCE=backend/directx/DirectXStorageImageDescriptorArrayShader.hlsl
    "-DEXPECTED_SOURCE_SNIPPET=RWTexture2DArray<uint4> maskAtlases[N] : register(u2, space0)"
    "-DEXPECTED_MANIFEST_JSON_FIELDS=schemaVersion=1|target=directx|module=DirectXStorageImageDescriptorArrayShader|artifacts.backendSource=backend/directx/DirectXStorageImageDescriptorArrayShader.hlsl|artifacts.nativeBinary=backend/directx/DirectXStorageImageDescriptorArrayShader.dxil"
    "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=directx|module=DirectXStorageImageDescriptorArrayShader|nativeBinary=backend/directx/DirectXStorageImageDescriptorArrayShader.dxil|resources.0.kind=storage_image|resources.0.type=image2D[COUNT]|resources.1.type=iimage2D[N]|resources.2.type=uimage2DArray[N]|workgroupSizes.0.entryPoint=compute_main|workgroupSizes.0.x=4|workgroupSizes.0.y=4|workgroupSizes.0.z=2"
    "-DEXPECTED_REFLECTION_JSON_ARRAY_LENGTHS=resources=3|targetResourceBindings=3|functionConstants=2|workgroupSizes=1"
    "-DEXPECTED_REFLECTION_TARGET_FIELDS=colorImages.sourceType=image2D[COUNT]|colorImages.hlslType=RWTexture2D<float4>|colorImages.bindingClass=uav|colorImages.descriptorType=UAV|colorImages.arraySize=COUNT|colorImages.arrayElementCount=2|labelImages.hlslType=RWTexture2D<int4>|maskAtlases.hlslType=RWTexture2DArray<uint4>|maskAtlases.arraySize=N|maskAtlases.arrayElementCount=2"
    "-DEXPECTED_REFLECTION_FEATURE_FIELDS=storage-image.kind=resource|descriptor-array.kind=resource|fixed-array.kind=layout|2d-dimension.kind=storageImage|2d_array-dimension.kind=storageImage|storage-image-read.kind=operation|storage-image-write.kind=operation"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_build_directx_storage_image_nonuniform_descriptor_array_source_package
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_DIRECTX_STORAGE_IMAGE_NONUNIFORM_DESCRIPTOR_ARRAY_SHADER}
    -DTARGET=directx
    -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-directx-storage-image-nonuniform-descriptor-array.cglb
    -DMODE=source-package-build
    -DEXPECTED_SOURCE=backend/directx/DirectXStorageImageNonUniformDescriptorArrayShader.hlsl
    "-DEXPECTED_SOURCE_SNIPPET=NonUniformResourceIndex(slot)"
    "-DEXPECTED_MANIFEST_JSON_FIELDS=schemaVersion=1|target=directx|module=DirectXStorageImageNonUniformDescriptorArrayShader|artifacts.backendSource=backend/directx/DirectXStorageImageNonUniformDescriptorArrayShader.hlsl|artifacts.nativeBinary=backend/directx/DirectXStorageImageNonUniformDescriptorArrayShader.dxil"
    "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=directx|module=DirectXStorageImageNonUniformDescriptorArrayShader|nativeBinary=backend/directx/DirectXStorageImageNonUniformDescriptorArrayShader.dxil|resources.0.kind=storage_image|resources.0.type=image2D[IMAGE_COUNT]|resources.2.type=uimage2DArray[IMAGE_COUNT]|workgroupSizes.0.entryPoint=compute_main|workgroupSizes.0.x=4|workgroupSizes.0.y=4|workgroupSizes.0.z=2"
    "-DEXPECTED_REFLECTION_JSON_ARRAY_LENGTHS=resources=3|targetResourceBindings=3|functionConstants=1|workgroupSizes=1"
    "-DEXPECTED_REFLECTION_TARGET_FIELDS=colorImages.sourceType=image2D[IMAGE_COUNT]|colorImages.hlslType=RWTexture2D<float4>|colorImages.bindingClass=uav|colorImages.arraySize=IMAGE_COUNT|colorImages.arrayElementCount=2|labelImages.hlslType=RWTexture2D<int4>|maskAtlases.hlslType=RWTexture2DArray<uint4>|maskAtlases.arrayElementCount=2"
    "-DEXPECTED_REFLECTION_FEATURE_FIELDS=storage-image.kind=resource|descriptor-array.kind=resource|fixed-array.kind=layout|nonuniform-descriptor-index.kind=operation|nonuniform-storage-image-descriptor-index.kind=operation|NonUniformResourceIndex.kind=intrinsic|storage-image-read.kind=operation|storage-image-write.kind=operation"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_build_directx_storage_image_explicit_format_descriptor_array_source_package
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_STORAGE_IMAGE_EXPLICIT_FORMAT_DESCRIPTOR_ARRAY_SHADER}
    -DTARGET=directx
    -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-directx-storage-image-explicit-format-descriptor-array.cglb
    -DMODE=source-package-build
    -DEXPECTED_SOURCE=backend/directx/StorageImageExplicitFormatDescriptorArrayShader.hlsl
    "-DEXPECTED_SOURCE_SNIPPET=RWTexture2DArray<uint4> outputAtlases[ATLAS_COUNT] : register(u3, space0)"
    "-DEXPECTED_MANIFEST_JSON_FIELDS=schemaVersion=1|target=directx|module=StorageImageExplicitFormatDescriptorArrayShader|artifacts.backendSource=backend/directx/StorageImageExplicitFormatDescriptorArrayShader.hlsl|artifacts.nativeBinary=backend/directx/StorageImageExplicitFormatDescriptorArrayShader.dxil"
    "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=directx|module=StorageImageExplicitFormatDescriptorArrayShader|nativeBinary=backend/directx/StorageImageExplicitFormatDescriptorArrayShader.dxil|resources.0.kind=storage_image|resources.0.type=image2D[IMAGE_COUNT]|resources.0.storageImageFormat=r32f|resources.1.storageImageFormat=r32i|resources.2.storageImageFormat=r32ui|resources.3.storageImageFormat=r32ui|workgroupSizes.0.entryPoint=compute_main|workgroupSizes.0.x=2|workgroupSizes.0.y=2|workgroupSizes.0.z=1"
    "-DEXPECTED_REFLECTION_JSON_ARRAY_LENGTHS=resources=8|targetResourceBindings=8|functionConstants=2|workgroupSizes=1"
    "-DEXPECTED_REFLECTION_TARGET_FIELDS=colorImages.sourceType=image2D[IMAGE_COUNT]|colorImages.hlslType=RWTexture2D<float4>|colorImages.bindingClass=uav|colorImages.arraySize=IMAGE_COUNT|colorImages.arrayElementCount=2|colorImages.storageImageFormat=r32f|labelImages.hlslType=RWTexture2D<int4>|labelImages.storageImageFormat=r32i|maskAtlases.hlslType=RWTexture2DArray<uint4>|maskAtlases.storageImageFormat=r32ui|outputAtlases.hlslType=RWTexture2DArray<uint4>|outputAtlases.storageImageFormat=r32ui|slots.sourceType=int*|slots.bindingClass=uav"
    "-DEXPECTED_REFLECTION_FEATURE_FIELDS=storage-image.kind=resource|read-only.kind=storageImage|write-only.kind=storageImage|descriptor-array.kind=resource|fixed-array.kind=layout|2d-dimension.kind=storageImage|2d_array-dimension.kind=storageImage|array-dimension.kind=storageImage|r32f-format.kind=storageImage|r32i-format.kind=storageImage|r32ui-format.kind=storageImage|nonuniform-descriptor-index.kind=operation|nonuniform-storage-image-descriptor-index.kind=operation|NonUniformResourceIndex.kind=intrinsic|storage-image-read.kind=operation|storage-image-write.kind=operation"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_build_directx_storage_image_atomic_descriptor_array_source_package
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_STORAGE_IMAGE_ATOMIC_DESCRIPTOR_ARRAY_SHADER}
    -DTARGET=directx
    -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-directx-storage-image-atomic-descriptor-array.cglb
    -DMODE=source-package-build
    -DEXPECTED_SOURCE=backend/directx/StorageImageAtomicDescriptorArrayShader.hlsl
    "-DEXPECTED_SOURCE_SNIPPET=InterlockedAdd(signedCounters[NonUniformResourceIndex(slot)][pixel], 1, signedOld);"
    "-DEXPECTED_MANIFEST_JSON_FIELDS=schemaVersion=1|target=directx|module=StorageImageAtomicDescriptorArrayShader|artifacts.backendSource=backend/directx/StorageImageAtomicDescriptorArrayShader.hlsl|artifacts.nativeBinary=backend/directx/StorageImageAtomicDescriptorArrayShader.dxil"
    "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=directx|module=StorageImageAtomicDescriptorArrayShader|nativeBinary=backend/directx/StorageImageAtomicDescriptorArrayShader.dxil|resources.0.kind=buffer|resources.1.kind=storage_image|resources.1.type=iimage2D[IMAGE_COUNT]|resources.1.storageImageFormat=r32i|resources.2.storageImageFormat=r32ui|resources.3.type=iimage2DArray[IMAGE_COUNT]|resources.4.type=uimage2DArray[IMAGE_COUNT]|resources.4.storageImageFormat=r32ui|workgroupSizes.0.entryPoint=compute_main|workgroupSizes.0.x=2|workgroupSizes.0.y=2|workgroupSizes.0.z=2"
    "-DEXPECTED_REFLECTION_JSON_ARRAY_LENGTHS=resources=7|targetResourceBindings=7|functionConstants=1|workgroupSizes=1"
    "-DEXPECTED_REFLECTION_TARGET_FIELDS=signedCounters.sourceType=iimage2D[IMAGE_COUNT]|signedCounters.hlslType=RWTexture2D<int>|signedCounters.arraySize=IMAGE_COUNT|signedCounters.arrayElementCount=2|signedCounters.storageImageFormat=r32i|unsignedCounters.sourceType=uimage2D[IMAGE_COUNT]|unsignedCounters.hlslType=RWTexture2D<uint>|unsignedCounters.storageImageFormat=r32ui|signedAtlases.sourceType=iimage2DArray[IMAGE_COUNT]|signedAtlases.hlslType=RWTexture2DArray<int>|signedAtlases.storageImageFormat=r32i|unsignedAtlases.sourceType=uimage2DArray[IMAGE_COUNT]|unsignedAtlases.hlslType=RWTexture2DArray<uint>|unsignedAtlases.storageImageFormat=r32ui"
    "-DEXPECTED_REFLECTION_FEATURE_FIELDS=storage-image.kind=resource|read-write.kind=storageImage|descriptor-array.kind=resource|fixed-array.kind=layout|2d-dimension.kind=storageImage|2d_array-dimension.kind=storageImage|array-dimension.kind=storageImage|r32i-format.kind=storageImage|r32ui-format.kind=storageImage|nonuniform-descriptor-index.kind=operation|nonuniform-storage-image-descriptor-index.kind=operation|NonUniformResourceIndex.kind=intrinsic|storage-buffer.kind=resource|storage-image-read.kind=operation|storage-image-write.kind=operation|storage-image-atomic-add.kind=operation|storage-image-atomic-exchange.kind=operation|storage-image-atomic-min.kind=operation|storage-image-atomic-max.kind=operation|storage-image-atomic-and.kind=operation|storage-image-atomic-or.kind=operation|storage-image-atomic-xor.kind=operation"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_build_opengl_storage_image_descriptor_array_source_package
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_OPENGL_STORAGE_IMAGE_DESCRIPTOR_ARRAY_SHADER}
    -DTARGET=opengl
    -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-opengl-storage-image-descriptor-array.cglb
    -DMODE=source-package-build
    -DEXPECTED_SOURCE=backend/opengl/OpenGLStorageImageDescriptorArrayShader.comp.glsl
    "-DEXPECTED_SOURCE_SNIPPET=layout(binding = 5, rgba32ui) uniform uimage2DArray maskAtlases[2];"
    "-DEXPECTED_MANIFEST_JSON_FIELDS=schemaVersion=1|target=opengl|module=OpenGLStorageImageDescriptorArrayShader|artifacts.backendSource=backend/opengl/OpenGLStorageImageDescriptorArrayShader.comp.glsl|artifacts.nativeBinary=backend/opengl/OpenGLStorageImageDescriptorArrayShader.glsl"
    "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=opengl|module=OpenGLStorageImageDescriptorArrayShader|nativeBinary=backend/opengl/OpenGLStorageImageDescriptorArrayShader.glsl|resources.0.kind=storage_image|resources.0.type=image2D[COUNT]|resources.5.type=uimage2DArray[2]|workgroupSizes.0.entryPoint=compute_main|workgroupSizes.0.x=8|workgroupSizes.0.y=8|workgroupSizes.0.z=1"
    "-DEXPECTED_REFLECTION_JSON_ARRAY_LENGTHS=resources=6|targetResourceBindings=6|functionConstants=1|workgroupSizes=1"
    "-DEXPECTED_REFLECTION_TARGET_FIELDS=colorImages.sourceType=image2D[COUNT]|colorImages.bindingClass=image|colorImages.argumentIndex=0|colorImages.arraySize=COUNT|labelImages.sourceType=iimage2D[2]|maskImages.sourceType=uimage2D[COUNT]|colorAtlases.sourceType=image2DArray[2]|labelAtlases.sourceType=iimage2DArray[COUNT]|maskAtlases.sourceType=uimage2DArray[2]|maskAtlases.arrayElementCount=2"
    "-DEXPECTED_REFLECTION_FEATURE_FIELDS=storage-image.kind=resource|descriptor-array.kind=resource|fixed-array.kind=layout|2d-dimension.kind=storageImage|2d_array-dimension.kind=storageImage|array-dimension.kind=storageImage|storage-image-read.kind=operation|storage-image-write.kind=operation"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_build_opengl_storage_image_nonuniform_descriptor_array_source_package
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_OPENGL_STORAGE_IMAGE_NONUNIFORM_DESCRIPTOR_ARRAY_SHADER}
    -DTARGET=opengl
    -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-opengl-storage-image-nonuniform-descriptor-array.cglb
    -DMODE=source-package-build
    -DEXPECTED_SOURCE=backend/opengl/OpenGLStorageImageNonUniformDescriptorArrayShader.comp.glsl
    "-DEXPECTED_SOURCE_SNIPPET=GL_EXT_nonuniform_qualifier"
    "-DEXPECTED_MANIFEST_JSON_FIELDS=schemaVersion=1|target=opengl|module=OpenGLStorageImageNonUniformDescriptorArrayShader|artifacts.backendSource=backend/opengl/OpenGLStorageImageNonUniformDescriptorArrayShader.comp.glsl|artifacts.nativeBinary=backend/opengl/OpenGLStorageImageNonUniformDescriptorArrayShader.glsl"
    "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=opengl|module=OpenGLStorageImageNonUniformDescriptorArrayShader|nativeBinary=backend/opengl/OpenGLStorageImageNonUniformDescriptorArrayShader.glsl|resources.0.kind=storage_image|resources.0.type=image2D[COUNT]|resources.5.type=uimage2DArray[2]|workgroupSizes.0.entryPoint=compute_main|workgroupSizes.0.x=8|workgroupSizes.0.y=8|workgroupSizes.0.z=1"
    "-DEXPECTED_REFLECTION_JSON_ARRAY_LENGTHS=resources=6|targetResourceBindings=6|functionConstants=1|workgroupSizes=1"
    "-DEXPECTED_REFLECTION_TARGET_FIELDS=colorImages.sourceType=image2D[COUNT]|colorImages.bindingClass=image|colorImages.arraySize=COUNT|labelImages.sourceType=iimage2D[2]|maskImages.sourceType=uimage2D[COUNT]|colorAtlases.sourceType=image2DArray[2]|labelAtlases.sourceType=iimage2DArray[COUNT]|maskAtlases.sourceType=uimage2DArray[2]|maskAtlases.arrayElementCount=2"
    "-DEXPECTED_REFLECTION_FEATURE_FIELDS=storage-image.kind=resource|descriptor-array.kind=resource|fixed-array.kind=layout|GL_EXT_nonuniform_qualifier.kind=extension|nonuniform-descriptor-index.kind=operation|nonuniform-storage-image-descriptor-index.kind=operation|storage-image-read.kind=operation|storage-image-write.kind=operation"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_build_opengl_storage_image_explicit_format_descriptor_array_source_package
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_STORAGE_IMAGE_EXPLICIT_FORMAT_DESCRIPTOR_ARRAY_SHADER}
    -DTARGET=opengl
    -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-opengl-storage-image-explicit-format-descriptor-array.cglb
    -DMODE=source-package-build
    -DEXPECTED_SOURCE=backend/opengl/StorageImageExplicitFormatDescriptorArrayShader.comp.glsl
    "-DEXPECTED_SOURCE_SNIPPET=layout(binding = 0, r32f) readonly uniform image2D colorImages[IMAGE_COUNT];"
    "-DEXPECTED_MANIFEST_JSON_FIELDS=schemaVersion=1|target=opengl|module=StorageImageExplicitFormatDescriptorArrayShader|artifacts.backendSource=backend/opengl/StorageImageExplicitFormatDescriptorArrayShader.comp.glsl|artifacts.nativeBinary=backend/opengl/StorageImageExplicitFormatDescriptorArrayShader.glsl"
    "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=opengl|module=StorageImageExplicitFormatDescriptorArrayShader|nativeBinary=backend/opengl/StorageImageExplicitFormatDescriptorArrayShader.glsl|resources.0.kind=storage_image|resources.0.type=image2D[IMAGE_COUNT]|resources.0.storageImageFormat=r32f|resources.1.storageImageFormat=r32i|resources.2.storageImageFormat=r32ui|resources.3.storageImageFormat=r32ui|workgroupSizes.0.entryPoint=compute_main|workgroupSizes.0.x=2|workgroupSizes.0.y=2|workgroupSizes.0.z=1"
    "-DEXPECTED_REFLECTION_JSON_ARRAY_LENGTHS=resources=8|targetResourceBindings=8|functionConstants=2|workgroupSizes=1"
    "-DEXPECTED_REFLECTION_TARGET_FIELDS=colorImages.sourceType=image2D[IMAGE_COUNT]|colorImages.bindingClass=image|colorImages.argumentIndex=0|colorImages.arraySize=IMAGE_COUNT|colorImages.storageImageFormat=r32f|labelImages.sourceType=iimage2D[IMAGE_COUNT]|labelImages.storageImageFormat=r32i|maskAtlases.sourceType=uimage2DArray[ATLAS_COUNT]|maskAtlases.storageImageFormat=r32ui|outputAtlases.sourceType=uimage2DArray[ATLAS_COUNT]|outputAtlases.storageImageFormat=r32ui"
    "-DEXPECTED_REFLECTION_FEATURE_FIELDS=storage-image.kind=resource|read-only.kind=storageImage|write-only.kind=storageImage|descriptor-array.kind=resource|fixed-array.kind=layout|2d-dimension.kind=storageImage|2d_array-dimension.kind=storageImage|array-dimension.kind=storageImage|r32f-format.kind=storageImage|r32i-format.kind=storageImage|r32ui-format.kind=storageImage|GL_EXT_nonuniform_qualifier.kind=extension|nonuniform-descriptor-index.kind=operation|nonuniform-storage-image-descriptor-index.kind=operation|storage-image-read.kind=operation|storage-image-write.kind=operation"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_build_opengl_storage_image_atomic_descriptor_array_source_package
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_STORAGE_IMAGE_ATOMIC_DESCRIPTOR_ARRAY_SHADER}
    -DTARGET=opengl
    -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-opengl-storage-image-atomic-descriptor-array.cglb
    -DMODE=source-package-build
    -DEXPECTED_SOURCE=backend/opengl/StorageImageAtomicDescriptorArrayShader.comp.glsl
    "-DEXPECTED_SOURCE_SNIPPET=imageAtomicAdd(signedCounters[nonuniformEXT(slot)], pixel, 1)"
    "-DEXPECTED_MANIFEST_JSON_FIELDS=schemaVersion=1|target=opengl|module=StorageImageAtomicDescriptorArrayShader|artifacts.backendSource=backend/opengl/StorageImageAtomicDescriptorArrayShader.comp.glsl|artifacts.nativeBinary=backend/opengl/StorageImageAtomicDescriptorArrayShader.glsl"
    "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=opengl|module=StorageImageAtomicDescriptorArrayShader|nativeBinary=backend/opengl/StorageImageAtomicDescriptorArrayShader.glsl|resources.0.kind=buffer|resources.1.kind=storage_image|resources.1.type=iimage2D[IMAGE_COUNT]|resources.1.storageImageFormat=r32i|resources.2.storageImageFormat=r32ui|resources.3.type=iimage2DArray[IMAGE_COUNT]|resources.4.type=uimage2DArray[IMAGE_COUNT]|resources.4.storageImageFormat=r32ui|workgroupSizes.0.entryPoint=compute_main|workgroupSizes.0.x=2|workgroupSizes.0.y=2|workgroupSizes.0.z=2"
    "-DEXPECTED_REFLECTION_JSON_ARRAY_LENGTHS=resources=7|targetResourceBindings=7|functionConstants=1|workgroupSizes=1"
    "-DEXPECTED_REFLECTION_TARGET_FIELDS=signedCounters.sourceType=iimage2D[IMAGE_COUNT]|signedCounters.bindingClass=image|signedCounters.arraySize=IMAGE_COUNT|signedCounters.arrayElementCount=2|signedCounters.storageImageFormat=r32i|unsignedCounters.sourceType=uimage2D[IMAGE_COUNT]|unsignedCounters.storageImageFormat=r32ui|signedAtlases.sourceType=iimage2DArray[IMAGE_COUNT]|signedAtlases.storageImageFormat=r32i|unsignedAtlases.sourceType=uimage2DArray[IMAGE_COUNT]|unsignedAtlases.storageImageFormat=r32ui"
    "-DEXPECTED_REFLECTION_FEATURE_FIELDS=storage-image.kind=resource|read-write.kind=storageImage|descriptor-array.kind=resource|fixed-array.kind=layout|2d-dimension.kind=storageImage|2d_array-dimension.kind=storageImage|array-dimension.kind=storageImage|r32i-format.kind=storageImage|r32ui-format.kind=storageImage|GL_EXT_nonuniform_qualifier.kind=extension|nonuniform-descriptor-index.kind=operation|nonuniform-storage-image-descriptor-index.kind=operation|storage-buffer.kind=resource|storage-image-read.kind=operation|storage-image-write.kind=operation|storage-image-atomic-add.kind=operation|storage-image-atomic-exchange.kind=operation|storage-image-atomic-min.kind=operation|storage-image-atomic-max.kind=operation|storage-image-atomic-and.kind=operation|storage-image-atomic-or.kind=operation|storage-image-atomic-xor.kind=operation"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
